#!/usr/bin/env python3
"""eido.py — the Eidoverse runner. Stdlib-only.

Wraps the Docker render container for both operating modes:

    python eido.py bootstrap [--image TAG] [--build] [--agent FLAVOR] [--local [--fresh]]
    python eido.py doctor    [--image TAG]
    python eido.py render <scene.json> [--probe] [--image TAG] [--local]
    python eido.py shell     [--image TAG]
    python eido.py agent --brief FILE [--context FILE] [--agent claude|codex|opencode]
                     [--image TAG] [--out DIR] [--comfy auto|on|off]
                     [--gpu-adapter NAME] [--timeout-min N]
                     [--system-prompt FILE] [--dry-run]

See docs/SETUP.md, docs/HARNESS_MODE.md, docs/AGENT_LOOP.md.
"""

from __future__ import annotations

import argparse
import datetime
import glob as globmod
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

# Windows Python defaults stdout/stderr to the legacy console code page
# (e.g. cp1252), which lacks glyphs used in our messages (#1).
for _stream in (sys.stdout, sys.stderr):
    if _stream and _stream.encoding and _stream.encoding.lower() not in ("utf-8", "utf8"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- agents ---
# The single place a new agent CLI gets added.
AGENTS = {
    "claude": {
        "image": "eidoverse:claude",
        "auth_mounts": [(os.path.expanduser("~/.claude"), "/home/node/.claude", "ro")],
        "env_passthrough": [],
        # {prompt} is substituted; the CLI runs with cwd /workspace
        "cmd": ["claude", "-p", "--dangerously-skip-permissions", "{prompt}"],
        "doc": "AGENTS.md",
    },
    "codex": {
        "image": "eidoverse:codex",
        "auth_mounts": [(os.path.expanduser("~/.codex"), "/home/node/.codex", "ro")],
        "env_passthrough": [],
        "cmd": ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "{prompt}"],
        "doc": "AGENTS.md",
    },
    "opencode": {
        "image": "eidoverse:opencode",
        # Mount the USER'S own opencode config + auth so `opencode run`
        # uses whatever default provider/model they set on their host —
        # nothing is hardcoded here. (config: ~/.config/opencode,
        # auth store: ~/.local/share/opencode)
        "auth_mounts": [
            (os.path.expanduser("~/.config/opencode"), "/home/node/.config/opencode", "ro"),
            (os.path.expanduser("~/.local/share/opencode"), "/home/node/.local/share/opencode", "ro"),
        ],
        "env_passthrough": ["OPENCODE_API_KEY"],
        "cmd": ["opencode", "run", "{prompt}"],
        "doc": "AGENTS.md",
    },
}

DEFAULT_RENDER_IMAGE = "eidoverse:render"

SYSTEM_PROMPT_TEMPLATE = """\
You are a video-production agent in the Eidoverse render sandbox.
Read /workspace/AGENTS.md COMPLETELY first — it is the full API contract
and production rulebook. Then read /workspace/_brief.txt (and
/workspace/_context.txt if it exists) and produce the video it asks for.
Check /workspace/_capabilities.json before planning audio. Work in
/workspace/work/<short_id>/ and finish with a playable final mp4 there,
or a concrete blocker report. Do not ask questions — interpret and ship.
"""

# ------------------------------------------------------------- utilities ---


def run(cmd, **kw):
    """subprocess.run with echo."""
    print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, **kw)


def find_deno():
    """Host deno binary: PATH first, then the default installer location."""
    p = shutil.which("deno")
    if p:
        return p
    cand = os.path.expanduser("~/.deno/bin/deno.exe" if os.name == "nt" else "~/.deno/bin/deno")
    return cand if os.path.isfile(cand) else None


def docker_ok():
    try:
        r = subprocess.run(["docker", "version", "--format", "{{.Server.Os}}"],
                           capture_output=True, text=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def image_exists(tag):
    r = subprocess.run(["docker", "image", "inspect", tag],
                       capture_output=True, text=True)
    return r.returncode == 0


def gpu_flags():
    """GPU device flags: WSL2 (/dev/dxg) on a Windows host, --gpus all otherwise."""
    flags = ["--gpus", "all"]
    if os.name == "nt":
        flags += ["--device", "/dev/dxg"]
    return flags


def base_env_flags(adapter="NVIDIA"):
    return ["-e", "GALLIUM_DRIVER=d3d12",
            "-e", f"MESA_D3D12_DEFAULT_ADAPTER_NAME={adapter}"]


def workspace_mount():
    # The named volume keeps the CONTAINER'S node_modules store separate from
    # the host's: deno stores are platform-specific (symlinks vs junctions
    # don't survive the bind mount in either direction), so each mode owns
    # its own store and they never conflict.
    return ["-v", f"{ROOT}:/workspace",
            "-v", "eidoverse-node-modules:/workspace/node_modules"]


def probe_comfy():
    """Return (reachable, url) for a host ComfyUI: 8188 first (bridge/native),
    then the 8000-8020 roam range ComfyUI Desktop uses."""
    for port in [8188] + list(range(8000, 8021)):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=1.5):
                return True, port
        except Exception:
            continue
    return False, None


def engine_ro_binds():
    """Per-file read-only binds for every canonical engine/tool file.

    Derived from `git ls-files` so the protection list can never drift from
    the repo contents; glob fallback for non-git checkouts. The whole repo is
    mounted rw at /workspace — these ro binds overlay the files agents must
    not modify. eidoverse/assets is protected as one directory mount.
    """
    patterns = ["eidoverse/*.mjs", "eidoverse/*.js", "eidoverse/*.py",
                "eidoverse/effects_tsl/*", "eidoverse/examples/*",
                "*.py", "AGENTS.md", "deno.lock"]
    files = []
    try:
        r = subprocess.run(["git", "-C", ROOT, "ls-files", "--"] + patterns,
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            files = [f for f in r.stdout.splitlines() if f.strip()]
    except Exception:
        pass
    if not files:
        for pat in patterns:
            files += [os.path.relpath(p, ROOT).replace("\\", "/")
                      for p in globmod.glob(os.path.join(ROOT, pat))]
    binds = []
    for rel in sorted(set(files)):
        absp = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.isfile(absp):
            binds += ["-v", f"{absp}:/workspace/{rel}:ro"]
    binds += ["-v", f"{os.path.join(ROOT, 'eidoverse', 'assets')}:/workspace/eidoverse/assets:ro"]
    return binds


def to_container_path(p):
    """Map a host path inside the repo to its /workspace path."""
    absp = os.path.abspath(p)
    rel = os.path.relpath(absp, ROOT).replace("\\", "/")
    if rel.startswith(".."):
        sys.exit(f"error: {p} is outside the repo ({ROOT}) — put scenes under work/")
    return f"/workspace/{rel}"


# ------------------------------------------------------------ subcommands ---


DENO_CACHE_CMDS = [
    ["cache", "--node-modules-dir=auto", "eidoverse/render_common.mjs", "eidoverse/render_scene.mjs"],
    ["cache", "--node-modules-dir=auto", "npm:@dimforge/rapier3d-compat@0.14.0"],
]


MIN_BUILD_FREE_GB = 60  # each flavor is ~14GB; builds transiently use far more


def check_disk_for_build():
    free_gb = shutil.disk_usage(os.path.expanduser("~")).free / 2**30
    if free_gb < MIN_BUILD_FREE_GB:
        sys.exit(f"error: only {free_gb:.0f} GB free — Docker image builds can balloon the "
                 f"Docker VM disk and it does NOT shrink on its own. Free space or run "
                 f"'python eido.py cleanup' first (need ~{MIN_BUILD_FREE_GB} GB). "
                 "Also set Docker Desktop Settings → Resources → 'Disk usage limit'.")
    return free_gb


def cmd_bootstrap(a):
    if a.local:
        deno = find_deno()
        if not deno:
            sys.exit("error: no host deno found — install 2.8.1 (docs/SETUP.md, Local rendering)")
        if a.fresh and os.path.isdir(os.path.join(ROOT, "node_modules")):
            print("removing node_modules for a fresh host build ...")
            shutil.rmtree(os.path.join(ROOT, "node_modules"))
        # container-built stores contain Linux symlinks Windows can't traverse;
        # .bin is always safe to clear (deno recreates platform-native shims)
        shutil.rmtree(os.path.join(ROOT, "node_modules", ".bin"), ignore_errors=True)
        for args in DENO_CACHE_CMDS:
            r = run([deno] + args, cwd=ROOT)
            if r.returncode:
                sys.exit("bootstrap --local FAILED — if node_modules was built inside the "
                         "container, its Linux symlinks break host deno: re-run with --fresh")
        print("bootstrap complete (host). Container runs keep a separate store "
              "in a Docker volume — run bootstrap without --local once for that mode.")
        return
    tag = a.image or DEFAULT_RENDER_IMAGE
    if a.build:
        check_disk_for_build()
        flavor = a.agent or "none"
        r = run(["docker", "build", "-f", os.path.join(ROOT, "docker", "Dockerfile"),
                 "--build-arg", f"AGENT={flavor}", "-t", tag, os.path.join(ROOT, "docker")])
        if r.returncode:
            sys.exit(r.returncode)
    if not image_exists(tag):
        sys.exit(f"error: image {tag} not found — build it first (docs/SETUP.md §1) or pass --build")
    inner = (
        "set -e; cd /workspace && "
        "deno cache --node-modules-dir=auto eidoverse/render_common.mjs eidoverse/render_scene.mjs && "
        "deno cache --node-modules-dir=auto npm:@dimforge/rapier3d-compat@0.14.0 && "
        "ls node_modules/.deno | grep -q '@dimforge+rapier3d-compat' && echo RAPIER_OK"
    )
    # --user root: the named node_modules volume is created root-owned;
    # populate it as root, then hand it to the runtime user.
    r = run(["docker", "run", "--rm", "--user", "root"] + workspace_mount()
            + [tag, "bash", "-c", inner + " && chown -R node:node /workspace/node_modules"])
    if r.returncode:
        sys.exit("bootstrap FAILED — see output above")
    print("bootstrap complete: node_modules materialized, RAPIER_OK")


def cmd_doctor(a):
    tag = a.image or DEFAULT_RENDER_IMAGE
    ok = True

    def report(label, good, detail=""):
        nonlocal ok
        mark = "ok " if good else "FAIL"
        print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
        ok = ok and good

    report("docker reachable", docker_ok())
    report(f"image {tag}", image_exists(tag), "docker build -f docker/Dockerfile ... (docs/SETUP.md)" if not image_exists(tag) else "")
    nm = os.path.isdir(os.path.join(ROOT, "node_modules", ".deno"))
    rap = bool(globmod.glob(os.path.join(ROOT, "node_modules", ".deno", "@dimforge+rapier3d-compat*")))
    report("node_modules (.deno)", nm, "" if nm else "run: python eido.py bootstrap")
    report("rapier materialized", rap, "" if rap else "run: python eido.py bootstrap")
    if docker_ok() and image_exists(tag):
        r = subprocess.run(["docker", "run", "--rm"] + gpu_flags() + [tag, "bash", "-c",
                           "ls /dev/dxg 2>/dev/null || nvidia-smi -L 2>/dev/null || vulkaninfo --summary 2>/dev/null | head -3 || echo NO_GPU"],
                           capture_output=True, text=True)
        got = (r.stdout or "").strip()
        report("GPU visible in container", "NO_GPU" not in got and got != "", got.splitlines()[0] if got else "")
    deno = find_deno()
    if deno:
        v = subprocess.run([deno, "--version"], capture_output=True, text=True).stdout.split()
        ver = v[1] if len(v) > 1 else "?"
        good = ver.startswith("2.8.")
        print(f"[{'ok ' if good else '-- '}] host deno {ver} " +
              ("— local rendering available" if good else
               "— pin 2.8.1 for local rendering (2.9.x corrupts the effects path)"))
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True).stdout
        nv = "h264_nvenc" in enc
        print(f"[{'ok ' if nv else '-- '}] host ffmpeg " +
              ("with h264_nvenc" if nv else "without nvenc — set RENDER_CODEC=libx264 for local renders"))
    else:
        print("[-- ] host deno not found — local (no-docker) rendering unavailable (optional)")
    dfr = subprocess.run(["docker", "system", "df", "--format", "{{.Type}}: {{.Size}} ({{.Reclaimable}} reclaimable)"],
                         capture_output=True, text=True)
    if dfr.returncode == 0 and dfr.stdout.strip():
        for line in dfr.stdout.strip().splitlines():
            print(f"[df ] {line}")
        print("      (large reclaimable → run: python eido.py cleanup)")
    comfy, port = probe_comfy()
    print(f"[{'ok ' if comfy else '-- '}] ComfyUI backend " +
          (f"(port {port}) — music/SFX generation available" if comfy
           else "not reachable — generate_song/sfx unavailable (optional)"))
    jina = bool(os.environ.get("JINA_AI_KEY") or os.environ.get("EIDOVERSE_EMBED_KEY"))
    print(f"[{'ok ' if jina else '-- '}] embeddings key " +
          ("set — fetch_model theme ranking active" if jina
           else "unset — fetch_model ranks by relevance only (optional)"))
    sys.exit(0 if ok else 1)


def cmd_render(a):
    tag = a.image or DEFAULT_RENDER_IMAGE
    cfg_host = os.path.abspath(a.scene)
    if not os.path.isfile(cfg_host):
        sys.exit(f"error: {a.scene} not found")
    cfg_container = to_container_path(cfg_host)

    if a.probe:
        # single-frame probe: clone the config with duration = 1 frame
        cfg = json.load(open(cfg_host, encoding="utf-8"))
        fps = cfg.get("fps", 30)
        cfg["duration"] = 1.0 / fps
        out = cfg.get("outputVideo") or "probe.mp4"
        stem, ext = os.path.splitext(out)
        cfg["outputVideo"] = f"{stem}_probe{ext}"
        probe_path = os.path.splitext(cfg_host)[0] + "_probe.json"
        json.dump(cfg, open(probe_path, "w", encoding="utf-8"), indent=2)
        cfg_container = to_container_path(probe_path)
        print(f"probe config: {probe_path} → {cfg['outputVideo']}")

    if a.local:
        deno = find_deno()
        if not deno:
            sys.exit("error: no host deno found — install 2.8.1 (docs/SETUP.md, Local rendering)")
        rel = cfg_container[len("/workspace/"):]
        r = run([deno, "run", "--allow-all", "--unstable-webgpu",
                 "--node-modules-dir=auto", "eidoverse/render_scene.mjs", rel], cwd=ROOT)
        sys.exit(r.returncode)
    inner = ("cd /workspace && deno run --allow-all --unstable-webgpu "
             f"--node-modules-dir=auto eidoverse/render_scene.mjs {cfg_container}")
    r = run(["docker", "run", "--rm"] + gpu_flags() + base_env_flags(a.gpu_adapter)
            + workspace_mount() + [tag, "bash", "-c", inner])
    sys.exit(r.returncode)


def cmd_shell(a):
    tag = a.image or DEFAULT_RENDER_IMAGE
    cmd = (["docker", "run", "--rm", "-it"] + gpu_flags() + base_env_flags(a.gpu_adapter)
           + workspace_mount() + [tag, "bash"])
    print("+", " ".join(cmd), flush=True)
    sys.exit(subprocess.call(cmd))


def cmd_agent(a):
    agent = AGENTS.get(a.agent)
    if not agent:
        sys.exit(f"error: unknown agent '{a.agent}' (choose from {', '.join(AGENTS)})")
    tag = a.image or agent["image"]

    # 1. brief / context
    if not os.path.isfile(a.brief):
        sys.exit(f"error: brief file {a.brief} not found")
    shutil.copyfile(a.brief, os.path.join(ROOT, "_brief.txt"))
    ctx_path = os.path.join(ROOT, "_context.txt")
    if a.context:
        shutil.copyfile(a.context, ctx_path)
    elif os.path.exists(ctx_path):
        os.remove(ctx_path)
    os.makedirs(os.path.join(ROOT, "work"), exist_ok=True)

    # 2. capabilities handshake (+ comfy bridge)
    comfy_up, comfy_port = (False, None)
    bridge = None
    if a.comfy != "off":
        comfy_up, comfy_port = probe_comfy()
        if a.comfy == "on" and not comfy_up:
            sys.exit("error: --comfy on but no ComfyUI reachable on 8188/8000-8020")
        if comfy_up and comfy_port != 8188:
            # ComfyUI is on a roaming port — start the stable 8188 bridge
            bridge = subprocess.Popen([sys.executable,
                                       os.path.join(ROOT, "eidoverse", "comfy_bridge.py")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"comfy_bridge started (pid {bridge.pid}) → forwards 8188 → {comfy_port}")
    caps = {
        "comfyui": bool(comfy_up),
        "comfy_url": "http://host.docker.internal:8188" if comfy_up else None,
        "jina_ai": bool(os.environ.get("JINA_AI_KEY") or os.environ.get("EIDOVERSE_EMBED_KEY")),
        "gpu_adapter": a.gpu_adapter,
    }
    json.dump(caps, open(os.path.join(ROOT, "_capabilities.json"), "w", encoding="utf-8"), indent=2)

    # 3. mounts + env
    binds = workspace_mount() + engine_ro_binds()
    for host, cont, mode in agent["auth_mounts"]:
        if os.path.exists(host):
            binds += ["-v", f"{host}:{cont}:{mode}"]
        else:
            print(f"note: auth path {host} not found — skipped "
                  f"(the {a.agent} CLI must then authenticate another way, e.g. an env key)")
    env = base_env_flags(a.gpu_adapter)
    for var in agent["env_passthrough"] + ["JINA_AI_KEY", "EIDOVERSE_EMBED_URL",
                                           "EIDOVERSE_EMBED_MODEL", "EIDOVERSE_EMBED_KEY"]:
        if os.environ.get(var):
            env += ["-e", f"{var}={os.environ[var]}"]
    env += ["-e", "COMFYUI_URL=http://host.docker.internal:8188"]
    env += ["--add-host", "host.docker.internal:host-gateway"]

    # 4. the agent command
    prompt = (open(a.system_prompt, encoding="utf-8").read()
              if a.system_prompt else SYSTEM_PROMPT_TEMPLATE)
    agent_cmd = [part.replace("{prompt}", prompt) for part in agent["cmd"]]
    # Model selection: --model pins any agent per-run (all three CLIs take
    # a --model flag). claude/codex otherwise fall back to their own config
    # defaults; opencode has NO reliable headless default, so warn.
    model = a.model or (os.environ.get("OPENCODE_MODEL") if a.agent == "opencode" else None)
    if model:
        agent_cmd = agent_cmd[:2] + ["--model", model] + agent_cmd[2:]
    elif a.agent == "opencode":
        print("warning: opencode has no reliable headless default model — pass --model "
              "<provider/model>, set OPENCODE_MODEL, or put \"model\" in "
              "~/.config/opencode/opencode.json")
    name = f"eidoverse-{a.agent}-{int(time.time())}"
    docker_cmd = (["docker", "run", "--rm", "--name", name]
                  + gpu_flags() + env + binds + [tag] + agent_cmd)

    if a.dry_run:
        print("---- dry run ----")
        print(" ".join(f'"{c}"' if " " in str(c) else str(c) for c in docker_cmd))
        n_ro = sum(1 for b in binds if str(b).endswith(":ro"))
        print(f"({n_ro} read-only binds protecting engine/tool files)")
        if bridge:
            bridge.terminate()
        return

    # 5. run, with timeout + collection
    out_dir = a.out or os.path.join(
        ROOT, "runs", datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    os.makedirs(out_dir, exist_ok=True)
    started = time.time()
    log_path = os.path.join(out_dir, "agent_stdout.log")
    exit_code = None
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as log:
            print(f"launching {name} (log: {log_path})")
            proc = subprocess.Popen(docker_cmd, stdout=log, stderr=subprocess.STDOUT)
            try:
                exit_code = proc.wait(timeout=a.timeout_min * 60)
            except subprocess.TimeoutExpired:
                print(f"TIMEOUT after {a.timeout_min} min — stopping container")
                subprocess.run(["docker", "kill", name], capture_output=True)
                exit_code = -1
    finally:
        if bridge:
            bridge.terminate()

    # 6. collect artifacts modified after launch
    collected = []
    for pattern in ["work/**/*.mp4", "work/**/*.png", "work/**/scene.js",
                    "work/**/scene.json", "work/**/plan.md", "*.mp4"]:
        for p in globmod.glob(os.path.join(ROOT, pattern), recursive=True):
            try:
                if os.path.getmtime(p) >= started - 2:
                    rel = os.path.relpath(p, ROOT)
                    dest = os.path.join(out_dir, rel.replace(os.sep, "__"))
                    shutil.copyfile(p, dest)
                    collected.append(rel)
            except OSError:
                pass
    json.dump({"agent": a.agent, "image": tag, "exit_code": exit_code,
               "duration_sec": round(time.time() - started), "capabilities": caps,
               "collected": collected},
              open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8"), indent=2)
    print(f"run finished (exit {exit_code}) — {len(collected)} artifact(s) → {out_dir}")
    sys.exit(0 if exit_code == 0 else 1)


def cmd_cleanup(a):
    """Reclaim Docker disk: build cache + dangling images, then report."""
    run(["docker", "builder", "prune", "-f"] + ([] if a.all_cache else ["--keep-storage", "10GB"]))
    run(["docker", "image", "prune", "-f"])
    r = subprocess.run(["docker", "system", "df"], capture_output=True, text=True)
    print(r.stdout)
    print("NOTE: space freed INSIDE the Docker VM does not shrink its disk file")
    print("automatically. If the host drive is still tight: fully quit Docker,")
    print("run 'wsl --shutdown', then compact the VM disk (docs/SETUP.md,")
    print("'Disk hygiene'). Prevent recurrence with Docker Desktop Settings →")
    print("Resources → 'Disk usage limit'.")


# ------------------------------------------------------------------- main ---


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--image", help="image tag override")
        p.add_argument("--gpu-adapter", default="NVIDIA",
                       help="MESA_D3D12_DEFAULT_ADAPTER_NAME (default NVIDIA)")

    p = sub.add_parser("bootstrap", help="materialize node_modules from deno.lock (+ optional --build)")
    common(p)
    p.add_argument("--build", action="store_true", help="docker build the image first")
    p.add_argument("--agent", help="flavor for --build (claude|codex|opencode|none)")
    p.add_argument("--local", action="store_true", help="bootstrap with HOST deno (no docker)")
    p.add_argument("--fresh", action="store_true", help="with --local: wipe node_modules first")
    p.set_defaults(fn=cmd_bootstrap)

    p = sub.add_parser("doctor", help="health check")
    common(p)
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("render", help="render a scene config in the container")
    common(p)
    p.add_argument("scene", help="path to scene.json (inside the repo)")
    p.add_argument("--probe", action="store_true", help="single-frame framing check")
    p.add_argument("--local", action="store_true", help="render with HOST deno + GPU (no docker)")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("shell", help="interactive container shell with production mounts")
    common(p)
    p.set_defaults(fn=cmd_shell)

    p = sub.add_parser("cleanup", help="reclaim Docker build cache + dangling images")
    p.add_argument("--all-cache", action="store_true", help="drop ALL build cache (default keeps 10GB)")
    p.set_defaults(fn=cmd_cleanup)

    p = sub.add_parser("agent", help="run one autonomous production")
    common(p)
    p.add_argument("--brief", required=True, help="brief text file")
    p.add_argument("--context", help="optional context text file")
    p.add_argument("--agent", default="claude", choices=list(AGENTS))
    p.add_argument("--model", help="pin the agent's model for this run (passed as the CLI's --model)")
    p.add_argument("--out", help="output collection dir (default runs/<utc-ts>)")
    p.add_argument("--comfy", default="auto", choices=["auto", "on", "off"])
    p.add_argument("--timeout-min", type=int, default=90)
    p.add_argument("--system-prompt", help="file overriding the built-in prompt")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_agent)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
