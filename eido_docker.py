"""eido_docker.py: the container runner of the auto-blender edition. Stdlib only.

eido_blender.py imports this module when it is present (it ships only on the auto-blender branch, with docker/), and
then:

    python eido_blender.py doctor                              # docker, the image, the GPU inside it, then the in-container doctor
    python eido_blender.py build|render|bench <scene.json> ... # the same commands, run inside the render image
    python eido_blender.py <command> ... --local               # run on this machine instead (eido_blender's own path)
    python eido_blender.py bootstrap [--build] [--agent FLAVOR] [--image TAG]
    python eido_blender.py shell [--image TAG]
    python eido_blender.py agent --brief FILE [--context FILE] [--agent claude|codex|opencode] [--model M]
                                 [--image TAG] [--out DIR] [--comfy auto|on|off] [--gpu-adapter NAME]
                                 [--timeout-min N] [--system-prompt FILE] [--dry-run]
    python eido_blender.py cleanup [--all-cache]

The repo is mounted at /workspace (read-write: scenes, work/, runs/), with the toolkit itself mounted read-only on top
(blender/, eidoverse/, tools-guides/, docs/, the runners, AGENTS.md): a misbehaving agent can fill work/ with
anything, but the kernel rejects writes to the toolkit. Inside, every Blender run goes through xvfb-run, so EEVEE
gets the X display it opens even headless, and Mesa's D3D12 driver carries it to the GPU (docker/Dockerfile).
See docs/SETUP.md, docs/AGENT_LOOP.md and docs/HARNESS_MODE.md.
"""

from __future__ import annotations

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

# The single place a new agent CLI gets added.
AGENTS = {
    'claude': {
        'image': 'eidoverse-blender:claude',
        'auth_mounts': [(os.path.expanduser('~/.claude'), '/home/node/.claude', 'ro')],
        'env_passthrough': [],
        'cmd': ['claude', '-p', '--dangerously-skip-permissions', '{prompt}'],
    },
    'codex': {
        'image': 'eidoverse-blender:codex',
        'auth_mounts': [(os.path.expanduser('~/.codex'), '/home/node/.codex', 'ro')],
        'env_passthrough': [],
        'cmd': ['codex', 'exec', '--dangerously-bypass-approvals-and-sandbox', '{prompt}'],
    },
    'opencode': {
        'image': 'eidoverse-blender:opencode',
        # the USER's own opencode config + auth, so `opencode run` uses whatever provider/model they set on the host
        'auth_mounts': [
            (os.path.expanduser('~/.config/opencode'), '/home/node/.config/opencode', 'ro'),
            (os.path.expanduser('~/.local/share/opencode'), '/home/node/.local/share/opencode', 'ro'),
        ],
        'env_passthrough': ['OPENCODE_API_KEY'],
        'cmd': ['opencode', 'run', '{prompt}'],
    },
}
DEFAULT_RENDER_IMAGE = 'eidoverse-blender:render'
NODE_MODULES_VOLUME = 'eidoverse-blender-node-modules'
XVFB = "xvfb-run -a -s '-screen 0 1280x720x24'"
# the Deno entry points the Blender edition runs (canvas scenes, the book and parole exporters)
DENO_ENTRIES = ['blender/eidoblend/media/js/canvas_bake.mjs', 'blender/eidoblend/media/js/canvas_scenes.mjs',
                'blender/eidoblend/media/js/book_export.mjs', 'blender/eidoblend/media/js/parole_export.mjs']
# toolkit folders and files mounted read-only over the read-write repo (folders protect everything beneath them);
# work/bestiary/ holds Creature Creator v2's shipped assets inside the otherwise writable work/ folder
PROTECTED_DIRS = ['blender', 'eidoverse', 'tools-guides', 'docs', 'docker', 'synthkit', 'voicebox', 'work/bestiary']
PROTECTED_FILE_PATTERNS = ['*.py', '*.sh', 'AGENTS.md', 'CLAUDE.md', 'deno.json', 'deno.lock']
# On Windows every program this runner starts in the background gets a windowless console (CREATE_NO_WINDOW): docker,
# the comfy bridge and the agent's container never open a console window on the desktop. Elsewhere the flag is 0.
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def inside_container():
    """True inside the render image: Docker creates /.dockerenv, and the image sets EIDO_IN_CONTAINER=1. There
    eido_blender.py runs doctor / build / render / bench right where it is."""
    return os.path.exists('/.dockerenv') or os.environ.get('EIDO_IN_CONTAINER') == '1'
MIN_BUILD_FREE_GB = 40

SYSTEM_PROMPT_TEMPLATE = """\
You are a video-production agent in the Eidoverse render sandbox, Blender edition.
Read /workspace/docs/AUTONOMOUS.md COMPLETELY first (how this unattended run works),
then /workspace/AGENTS.md (the index of the toolkit's guides; open the guides your
film needs). Then read /workspace/_brief.txt (and /workspace/_context.txt if it
exists) and produce the video it asks for. Check /workspace/_capabilities.json
before planning audio. Work in /workspace/work/<short_id>/, render with
`python3 eido_blender.py render <scene.json>` (inside the render image it renders
right here), and finish with a playable final mp4 there, or a concrete blocker
report. Do not ask questions: interpret and ship.
"""


# ------------------------------------------------------------------------------------------------ helpers ---

def run(cmd, **kw):
    print('+', ' '.join(str(c) for c in cmd), flush=True)
    kw.setdefault('creationflags', NO_WINDOW)
    return subprocess.run(cmd, **kw)


def docker_ok():
    try:
        return subprocess.run(['docker', 'version', '--format', '{{.Server.Version}}'], capture_output=True,
                              text=True, timeout=30, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def image_exists(tag):
    return subprocess.run(['docker', 'image', 'inspect', tag], capture_output=True, text=True,
                          creationflags=NO_WINDOW).returncode == 0


def gpu_flags():
    """--gpus all everywhere; on a Windows host also WSL2's GPU device and its userspace libraries (the D3D12
    driver libraries live in the Docker VM's /usr/lib/wsl and are NOT mounted by --gpus alone: without them Mesa
    silently falls back to software rendering)."""
    flags = ['--gpus', 'all']
    if os.name == 'nt':
        flags += ['--device', '/dev/dxg', '-v', '/usr/lib/wsl:/usr/lib/wsl:ro']
    return flags


def base_env_flags(adapter='NVIDIA'):
    return ['-e', 'GALLIUM_DRIVER=d3d12', '-e', f'MESA_D3D12_DEFAULT_ADAPTER_NAME={adapter}']


def workspace_mount():
    # the named volume keeps the CONTAINER's node_modules store apart from the host's: deno stores are
    # platform-specific (symlinks vs junctions survive the bind mount in neither direction)
    return ['-v', f'{ROOT}:/workspace', '-v', f'{NODE_MODULES_VOLUME}:/workspace/node_modules']


def protected_binds():
    """Read-only mounts over the toolkit. Folders protect everything beneath them in one flag (a per-file list would
    overflow Windows' 32 K command line); root files are listed one by one."""
    binds = []
    for d in PROTECTED_DIRS:
        if os.path.isdir(os.path.join(ROOT, d)):
            binds += ['-v', f'{os.path.join(ROOT, d)}:/workspace/{d}:ro']
    files = set()
    for pat in PROTECTED_FILE_PATTERNS:
        files.update(os.path.basename(p) for p in globmod.glob(os.path.join(ROOT, pat)))
    for f in sorted(files):
        binds += ['-v', f'{os.path.join(ROOT, f)}:/workspace/{f}:ro']
    # the fetched-asset library stays writable inside the read-only eidoverse/ (Docker mounts the deeper path on
    # top), so fetch_model_file / fetch_pbr can add a Poly Haven or AmbientCG set on first use
    cache = os.path.join(ROOT, 'eidoverse', 'assets', 'cache')
    os.makedirs(cache, exist_ok=True)
    binds += ['-v', f'{cache}:/workspace/eidoverse/assets/cache']
    return binds


def to_container_path(p):
    rel = os.path.relpath(os.path.abspath(p), ROOT).replace('\\', '/')
    if rel.startswith('..'):
        sys.exit(f'error: {p} is outside the repo ({ROOT}): put scenes under work/')
    return f'/workspace/{rel}'


def probe_comfy():
    """(reachable, port) for a host ComfyUI: 8188 first (bridge/native), then ComfyUI Desktop's 8000-8020 range."""
    for port in [8188] + list(range(8000, 8021)):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/system_stats', timeout=1.5):
                return True, port
        except Exception:                                            # noqa: BLE001
            continue
    return False, None


def container_cmd(tag, inner, adapter='NVIDIA', interactive=False, extra=()):
    return (['docker', 'run', '--rm'] + (['-it'] if interactive else []) + gpu_flags() + base_env_flags(adapter)
            + workspace_mount() + protected_binds() + list(extra) + [tag, 'bash', '-lc', inner])


# ------------------------------------------------------------------------------------------- in-container ---

def run_in_container(argv, a):
    """eido_blender.py doctor|build|render|bench, run inside the render image (the same command with --local)."""
    if not docker_ok():
        sys.exit('error: docker is not reachable: start Docker Desktop, or add --local to run on this machine')
    tag = getattr(a, 'image', None) or DEFAULT_RENDER_IMAGE
    if not image_exists(tag):
        sys.exit(f'error: image {tag} not found: python eido_blender.py bootstrap --build (docs/SETUP.md), '
                 'or add --local')
    args, skip = [], False
    for i, tok in enumerate(argv):
        if skip:
            skip = False
            continue
        if tok == '--image':                       # host-side option, not for the in-container run
            skip = True
            continue
        if tok.startswith('--image='):
            continue
        if getattr(a, 'scene', None) and tok == a.scene:
            tok = to_container_path(tok)
        args.append(tok)
    if a.cmd == 'doctor':
        r = subprocess.run(container_cmd(tag, f'cd /workspace && {XVFB} blender -b --factory-startup '
                                              '--python docker/blender_gpu_check.py -- /tmp/gpu_check.png'),
                           creationflags=NO_WINDOW)
        print(f"[{'ok ' if r.returncode == 0 else 'FAIL'}] EEVEE on the GPU inside {tag}"
              + ('' if r.returncode == 0 else ': read the [gpu] lines above'))
        if r.returncode:
            return 1
    quoted = ' '.join("'" + t.replace("'", "'\\''") + "'" for t in args)
    inner = f'cd /workspace && {XVFB} python3 eido_blender.py {quoted} --local'
    return run(container_cmd(tag, inner, getattr(a, 'gpu_adapter', 'NVIDIA') or 'NVIDIA')).returncode


# ------------------------------------------------------------------------------------------ the commands ---

def check_disk_for_build():
    free_gb = shutil.disk_usage(os.path.expanduser('~')).free / 2 ** 30
    if free_gb < MIN_BUILD_FREE_GB:
        sys.exit(f'error: only {free_gb:.0f} GB free: image builds grow the Docker VM disk and it does NOT shrink '
                 f"on its own. Free space or run 'python eido_blender.py cleanup' first (need ~{MIN_BUILD_FREE_GB} GB).")


def cmd_bootstrap(a):
    tag = a.image or (AGENTS[a.agent]['image'] if a.agent in AGENTS else DEFAULT_RENDER_IMAGE)
    if a.build:
        check_disk_for_build()
        r = run(['docker', 'build', '-f', os.path.join(ROOT, 'docker', 'Dockerfile'),
                 '--build-arg', f'AGENT={a.agent or "none"}', '-t', tag, os.path.join(ROOT, 'docker')])
        if r.returncode:
            sys.exit(r.returncode)
    if not image_exists(tag):
        sys.exit(f'error: image {tag} not found: build it first (docs/SETUP.md) or pass --build')
    entries = ' '.join(e for e in DENO_ENTRIES if os.path.isfile(os.path.join(ROOT, e)))
    inner = (f'set -e; cd /workspace && deno cache --node-modules-dir=auto {entries} && '
             'chown -R node:node /workspace/node_modules && echo DENO_STORE_OK')
    # --user root: the named node_modules volume is created root-owned; fill it as root, then hand it over
    r = run(['docker', 'run', '--rm', '--user', 'root'] + workspace_mount() + [tag, 'bash', '-lc', inner])
    if r.returncode:
        sys.exit('bootstrap FAILED: see the output above')
    print('bootstrap complete: the container deno store is filled (canvas scenes, book and parole exporters)')


def cmd_shell(a):
    tag = a.image or DEFAULT_RENDER_IMAGE
    cmd = container_cmd(tag, 'cd /workspace && exec bash', a.gpu_adapter, interactive=True)
    print('+', ' '.join(cmd), flush=True)
    sys.exit(subprocess.call(cmd))


def cmd_cleanup(a):
    """Reclaim Docker disk: build cache + dangling images, then report."""
    run(['docker', 'builder', 'prune', '-f'] + ([] if a.all_cache else ['--keep-storage', '10GB']))
    run(['docker', 'image', 'prune', '-f'])
    r = subprocess.run(['docker', 'system', 'df'], capture_output=True, text=True, creationflags=NO_WINDOW)
    print(r.stdout)
    print('NOTE: space freed INSIDE the Docker VM does not shrink its disk file automatically. If the host drive is '
          "still tight: quit Docker, run 'wsl --shutdown', then compact the VM disk (docs/SETUP.md, 'Disk hygiene').")


def cmd_agent(a):
    agent = AGENTS.get(a.agent)
    if not agent:
        sys.exit(f"error: unknown agent '{a.agent}' (choose from {', '.join(AGENTS)})")
    tag = a.image or agent['image']
    if not os.path.isfile(a.brief):
        sys.exit(f'error: brief file {a.brief} not found')
    shutil.copyfile(a.brief, os.path.join(ROOT, '_brief.txt'))
    ctx_path = os.path.join(ROOT, '_context.txt')
    if a.context:
        shutil.copyfile(a.context, ctx_path)
    elif os.path.exists(ctx_path):
        os.remove(ctx_path)
    os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)

    comfy_up, comfy_port, bridge = False, None, None
    if a.comfy != 'off':
        comfy_up, comfy_port = probe_comfy()
        if a.comfy == 'on' and not comfy_up:
            sys.exit('error: --comfy on but no ComfyUI reachable on 8188/8000-8020')
        if comfy_up and comfy_port != 8188:
            bridge = subprocess.Popen([sys.executable, os.path.join(ROOT, 'eidoverse', 'comfy_bridge.py')],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      creationflags=NO_WINDOW)
            print(f'comfy_bridge started (pid {bridge.pid}): forwards 8188 to {comfy_port}')
    caps = {'comfyui': bool(comfy_up), 'comfy_url': 'http://host.docker.internal:8188' if comfy_up else None,
            'jina_ai': bool(os.environ.get('JINA_AI_KEY') or os.environ.get('EIDOVERSE_EMBED_KEY')),
            'gpu_adapter': a.gpu_adapter, 'renderer': 'blender-eevee'}
    with open(os.path.join(ROOT, '_capabilities.json'), 'w', encoding='utf-8') as f:
        json.dump(caps, f, indent=2)

    extra = []
    for host, cont, mode in agent['auth_mounts']:
        if os.path.exists(host):
            extra += ['-v', f'{host}:{cont}:{mode}']
        else:
            print(f'note: auth path {host} not found: skipped (the {a.agent} CLI must authenticate another way)')
    for var in agent['env_passthrough'] + ['JINA_AI_KEY', 'EIDOVERSE_EMBED_URL', 'EIDOVERSE_EMBED_MODEL',
                                           'EIDOVERSE_EMBED_KEY']:
        if os.environ.get(var):
            extra += ['-e', f'{var}={os.environ[var]}']
    extra += ['-e', 'COMFYUI_URL=http://host.docker.internal:8188', '--add-host', 'host.docker.internal:host-gateway']

    prompt = open(a.system_prompt, encoding='utf-8').read() if a.system_prompt else SYSTEM_PROMPT_TEMPLATE
    agent_cmd = [part.replace('{prompt}', prompt) for part in agent['cmd']]
    model = a.model or (os.environ.get('OPENCODE_MODEL') if a.agent == 'opencode' else None)
    if model:
        agent_cmd = agent_cmd[:2] + ['--model', model] + agent_cmd[2:]
    elif a.agent == 'opencode':
        print('warning: opencode has no reliable headless default model: pass --model <provider/model>, set '
              'OPENCODE_MODEL, or put "model" in ~/.config/opencode/opencode.json')
    name = f'eidoverse-blender-{a.agent}-{int(time.time())}'
    # the agent CLI runs under xvfb-run, so every Blender it starts has its display
    quoted = ' '.join("'" + t.replace("'", "'\\''") + "'" for t in agent_cmd)
    docker_cmd = (['docker', 'run', '--rm', '--name', name] + gpu_flags() + base_env_flags(a.gpu_adapter)
                  + workspace_mount() + protected_binds() + extra + [tag, 'bash', '-lc',
                                                                     f'cd /workspace && {XVFB} {quoted}'])
    if a.dry_run:
        print('---- dry run ----')
        print(' '.join(f'"{c}"' if ' ' in str(c) else str(c) for c in docker_cmd))
        print(f"({sum(1 for b in docker_cmd if str(b).endswith(':ro'))} read-only mounts protecting the toolkit)")
        if bridge:
            bridge.terminate()
        return

    out_dir = a.out or os.path.join(ROOT, 'runs', datetime.datetime.now(datetime.timezone.utc)
                                    .strftime('%Y%m%dT%H%M%SZ'))
    os.makedirs(out_dir, exist_ok=True)
    started, exit_code = time.time(), None
    log_path = os.path.join(out_dir, 'agent_stdout.log')
    try:
        with open(log_path, 'w', encoding='utf-8', errors='replace') as log:
            print(f'launching {name} (log: {log_path})')
            proc = subprocess.Popen(docker_cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
            try:
                exit_code = proc.wait(timeout=a.timeout_min * 60)
            except subprocess.TimeoutExpired:
                print(f'TIMEOUT after {a.timeout_min} min: stopping {name}')
                subprocess.run(['docker', 'kill', name], capture_output=True, creationflags=NO_WINDOW)
                exit_code = -1
    finally:
        if bridge:
            bridge.terminate()

    collected = []
    for pattern in ['work/**/*.mp4', 'work/**/*.png', 'work/**/scene.py', 'work/**/scene.json', 'work/**/plan.md',
                    'work/**/*.blend', '*.mp4']:
        for p in globmod.glob(os.path.join(ROOT, pattern), recursive=True):
            try:
                if os.path.getmtime(p) >= started - 2:
                    rel = os.path.relpath(p, ROOT)
                    shutil.copyfile(p, os.path.join(out_dir, rel.replace(os.sep, '__')))
                    collected.append(rel)
            except OSError:
                pass
    with open(os.path.join(out_dir, 'run.json'), 'w', encoding='utf-8') as f:
        json.dump({'agent': a.agent, 'image': tag, 'exit_code': exit_code,
                   'duration_sec': round(time.time() - started), 'capabilities': caps, 'collected': collected},
                  f, indent=2)
    print(f'run finished (exit {exit_code}): {len(collected)} artifact(s) -> {out_dir}')
    sys.exit(0 if exit_code == 0 else 1)


def add_commands(sub):
    """The container-only commands, added to eido_blender.py's parser."""
    def common(p):
        p.add_argument('--image', help='image tag override')
        p.add_argument('--gpu-adapter', default='NVIDIA', help='MESA_D3D12_DEFAULT_ADAPTER_NAME (default NVIDIA)')

    p = sub.add_parser('bootstrap', help='fill the container deno store (+ optional --build of the image)')
    common(p)
    p.add_argument('--build', action='store_true', help='docker build the image first')
    p.add_argument('--agent', help='flavor for --build (claude|codex|opencode|none)')
    p.set_defaults(fn=cmd_bootstrap)

    p = sub.add_parser('shell', help='interactive container shell with the production mounts')
    common(p)
    p.set_defaults(fn=cmd_shell)

    p = sub.add_parser('cleanup', help='reclaim Docker build cache + dangling images')
    p.add_argument('--all-cache', action='store_true', help='drop ALL build cache (default keeps 10GB)')
    p.set_defaults(fn=cmd_cleanup)

    p = sub.add_parser('agent', help='run one autonomous production in the container')
    common(p)
    p.add_argument('--brief', required=True, help='brief text file')
    p.add_argument('--context', help='optional context text file')
    p.add_argument('--agent', default='claude', choices=list(AGENTS))
    p.add_argument('--model', help="pin the agent's model for this run (passed as the CLI's --model)")
    p.add_argument('--out', help='output collection dir (default runs/<utc-ts>)')
    p.add_argument('--comfy', default='auto', choices=['auto', 'on', 'off'])
    p.add_argument('--timeout-min', type=int, default=90)
    p.add_argument('--system-prompt', help='file overriding the built-in prompt')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(fn=cmd_agent)
