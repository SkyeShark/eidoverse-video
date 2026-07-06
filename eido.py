#!/usr/bin/env python3
"""eido.py — the Eidoverse runner (local edition). Stdlib-only.

Everything runs directly on your machine: your deno, your ffmpeg, your
GPU. Install the dependencies once (docs/SETUP.md), then:

    python eido.py bootstrap [--fresh]     # materialize node_modules from deno.lock
    python eido.py doctor                  # health check
    python eido.py render <scene.json> [--probe]

The containerized edition of this tool — Docker render image + the
agentic-loop subagent caller — lives on the `auto` branch.
"""

from __future__ import annotations

import argparse
import glob as globmod
import json
import os
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

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


def probe_comfy():
    """Return (reachable, port) for a host ComfyUI: 8188 first (bridge/native),
    then the 8000-8020 roam range ComfyUI Desktop uses."""
    for port in [8188] + list(range(8000, 8021)):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=1.5):
                return True, port
        except Exception:
            continue
    return False, None


def to_repo_rel(p):
    """Map a host path inside the repo to its repo-relative form."""
    absp = os.path.abspath(p)
    rel = os.path.relpath(absp, ROOT).replace("\\", "/")
    if rel.startswith(".."):
        sys.exit(f"error: {p} is outside the repo ({ROOT}) — put scenes under work/")
    return rel


# ------------------------------------------------------------ subcommands ---


DENO_CACHE_CMDS = [
    ["cache", "--node-modules-dir=auto", "eidoverse/render_common.mjs", "eidoverse/render_scene.mjs"],
    ["cache", "--node-modules-dir=auto", "npm:@dimforge/rapier3d-compat@0.14.0"],
]


def cmd_bootstrap(a):
    deno = find_deno()
    if not deno:
        sys.exit("error: no deno found — install 2.8.1 (docs/SETUP.md)")
    if a.fresh and os.path.isdir(os.path.join(ROOT, "node_modules")):
        print("removing node_modules for a fresh build ...")
        shutil.rmtree(os.path.join(ROOT, "node_modules"))
    # a store built elsewhere can contain symlinks this OS can't traverse;
    # .bin is always safe to clear (deno recreates platform-native shims)
    shutil.rmtree(os.path.join(ROOT, "node_modules", ".bin"), ignore_errors=True)
    for args in DENO_CACHE_CMDS:
        r = run([deno] + args, cwd=ROOT)
        if r.returncode:
            sys.exit("bootstrap FAILED — if node_modules came from another "
                     "OS/container, its symlinks break here: re-run with --fresh")
    print("bootstrap complete: node_modules materialized")


def cmd_doctor(a):
    ok = True

    def report(label, good, detail=""):
        nonlocal ok
        mark = "ok " if good else "FAIL"
        print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
        ok = ok and good

    deno = find_deno()
    if deno:
        v = subprocess.run([deno, "--version"], capture_output=True, text=True).stdout.split()
        ver = v[1] if len(v) > 1 else "?"
        report(f"deno {ver}", ver.startswith("2.8."),
               "" if ver.startswith("2.8.") else
               "pin 2.8.1 (2.9.x corrupts the effects path) — docs/SETUP.md")
    else:
        report("deno", False, "install 2.8.1 (docs/SETUP.md)")
    ff = shutil.which("ffmpeg")
    if ff:
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True).stdout
        nv = "h264_nvenc" in enc
        print(f"[{'ok ' if nv else '-- '}] ffmpeg " +
              ("with h264_nvenc" if nv else "without nvenc — set RENDER_CODEC=libx264"))
    else:
        report("ffmpeg", False, "install ffmpeg (docs/SETUP.md)")
    nm = os.path.isdir(os.path.join(ROOT, "node_modules", ".deno"))
    rap = bool(globmod.glob(os.path.join(ROOT, "node_modules", ".deno", "@dimforge+rapier3d-compat*")))
    report("node_modules (.deno)", nm, "" if nm else "run: python eido.py bootstrap")
    report("rapier materialized", rap, "" if rap else "run: python eido.py bootstrap")
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
    cfg_host = os.path.abspath(a.scene)
    if not os.path.isfile(cfg_host):
        sys.exit(f"error: {a.scene} not found")
    rel = to_repo_rel(cfg_host)

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
        rel = to_repo_rel(probe_path)
        print(f"probe config: {probe_path} → {cfg['outputVideo']}")

    deno = find_deno()
    if not deno:
        sys.exit("error: no deno found — install 2.8.1 (docs/SETUP.md)")
    r = run([deno, "run", "--allow-all", "--unstable-webgpu",
             "--node-modules-dir=auto", "eidoverse/render_scene.mjs", rel], cwd=ROOT)
    sys.exit(r.returncode)


# ------------------------------------------------------------------- main ---


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("bootstrap", help="materialize node_modules from deno.lock")
    p.add_argument("--fresh", action="store_true", help="wipe node_modules first")
    p.set_defaults(fn=cmd_bootstrap)

    p = sub.add_parser("doctor", help="health check")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("render", help="render a scene config on this machine")
    p.add_argument("scene")
    p.add_argument("--probe", action="store_true", help="single-frame render for framing checks")
    p.set_defaults(fn=cmd_render)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
