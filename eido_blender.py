#!/usr/bin/env python3
"""eido_blender.py: the Eidoverse runner, Blender 5.2 EEVEE edition. Stdlib only.

Every Blender run is headless, through run_blender.sh (an isolated Blender user folder, so --factory-startup never
touches your real add-ons). Install Blender 5.2 and Git Bash once (docs/SETUP.md), then:

    python eido_blender.py doctor [--no-render]               # Blender, the VRM extension, ffmpeg, a GPU render check
    python eido_blender.py build  <scene.json> [--rebuild] [--force]
    python eido_blender.py render <scene.json>                # the whole film to H.264 (+ 3 probe frames)
    python eido_blender.py render <scene.json> --probe [--frames N]       # the first N frames, probe caps
    python eido_blender.py render <scene.json> --at 12.5 [--at 40 ...]   # PNG stills mid-film, film settings
    python eido_blender.py bench  <scene.json> [--frames 3]   # seconds a frame at film settings, and the film's total
    python eido_blender.py open   <scene.json>                # the built .blend in Blender's own window

A run BUILDS the scene (setup(ctx), render_frame keyed, caches baked, audits) into <out dir>/<scene>.blend, then
renders it. An unchanged build is reused; a .blend edited by hand is rendered as it is and never rebuilt over
without --force. Guide: tools-guides/scene-format.md.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import urllib.request

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'blender'))

from eidoblend.harness import config as cfgmod  # noqa: E402

try:
    # The auto-blender edition ships the container runner (eido_docker.py beside this file, plus docker/): there,
    # build / render / bench / doctor run inside the render image unless --local is given, and bootstrap, shell,
    # agent and cleanup exist. This edition has neither, so everything runs on your machine.
    import eido_docker  # noqa: E402
except ImportError:
    eido_docker = None

RUN_SCENE = 'blender/eidoblend/harness/run_scene.py'
DOCTOR = 'blender/eidoblend/harness/doctor.py'
EXIT_MEANING = {0: 'done', 1: 'failed', 2: 'bad arguments', 3: 'refused (a hand-edited .blend; see the message)'}

for _stream in (sys.stdout, sys.stderr):
    if _stream and _stream.encoding and _stream.encoding.lower() not in ('utf-8', 'utf8'):
        _stream.reconfigure(encoding='utf-8', errors='replace')


# ------------------------------------------------------------------------------------------------ helpers ---

def find_bash():
    """Git Bash on Windows (never WSL's System32 bash, which cannot see Windows paths the same way)."""
    env = os.environ.get('EIDO_BASH')
    if env:
        return env
    if os.name == 'nt':
        for c in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files (x86)\Git\bin\bash.exe',
                  os.path.expanduser(r'~\AppData\Local\Programs\Git\bin\bash.exe')):
            if os.path.isfile(c):
                return c
        git = shutil.which('git')
        if git:
            c = os.path.normpath(os.path.join(os.path.dirname(git), '..', 'bin', 'bash.exe'))
            if os.path.isfile(c):
                return c
    b = shutil.which('bash')
    if b and 'system32' not in b.lower():
        return b
    return None


def find_blender():
    """The same search as run_blender.sh: BLENDER, `blender` on PATH, then install folders, newest first."""
    env = os.environ.get('BLENDER')
    if env:
        return env if os.path.exists(env) else None
    b = shutil.which('blender')
    if b:
        return b
    cands = glob.glob(os.path.expanduser('~/Blender/*/blender.exe')) + \
        glob.glob(r'C:\Program Files\Blender Foundation\*\blender.exe') + \
        ['/Applications/Blender.app/Contents/MacOS/Blender', '/usr/bin/blender', '/snap/bin/blender']
    cands = [c for c in cands if os.path.exists(c)]

    def ver(p):
        import re
        return [int(x) for x in re.findall(r'\d+', p)] or [0]
    return sorted(cands, key=ver, reverse=True)[0] if cands else None


def run_blender(script, args, check_bash=True):
    bash = find_bash()
    if not bash:
        sys.exit('error: no bash found: install Git for Windows (Git Bash), or set EIDO_BASH to its bash.exe')
    cmd = [bash, 'run_blender.sh', script] + [str(a) for a in args]
    print('+', ' '.join(cmd), flush=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def load(scene):
    try:
        cfg = cfgmod.load_config(scene)
    except cfgmod.ConfigError as e:
        sys.exit(f'error: {e}')
    for w in cfg['_warnings']:
        print(f'warning: {w}')
    bad = cfgmod.missing_assets(cfg)
    if bad:
        sys.exit('error: ' + '\n       '.join(bad))
    return cfg


def write_job(cfg, mode, **opts):
    job = {'mode': mode, 'config': cfg}
    job.update({k: v for k, v in opts.items() if v not in (None, False)})
    path = cfg['_job']
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(job, f, indent=1)
    return path


def finish(rc, cfg, mode, expect):
    paths = cfgmod.output_paths(cfg, mode)
    status = None
    try:
        with open(paths['audit_json'], encoding='utf-8') as f:
            status = json.load(f).get('status')
    except (OSError, json.JSONDecodeError):
        pass
    missing = [p for p in expect if not os.path.exists(p)]
    print()
    print(f'eido_blender: Blender exited {rc} ({EXIT_MEANING.get(rc, "?")}); digest status: {status or "MISSING"}')
    if missing:
        print('eido_blender: MISSING outputs (the run did not finish them):')
        for p in missing:
            print('  ' + p)
    else:
        for p in expect:
            print('  ' + p)
    ok = rc == 0 and not missing and status == 'normal completion'
    sys.exit(0 if ok else (rc or 1))


# ------------------------------------------------------------------------------------------------ commands ---

def cmd_doctor(a):
    ok = True

    def report(label, good, detail='', optional=False):
        nonlocal ok
        mark = 'ok ' if good else ('-- ' if optional else 'FAIL')
        print(f'[{mark}] {label}' + (f' - {detail}' if detail else ''))
        if not good and not optional:
            ok = False

    bl = find_blender()
    if bl:
        v = subprocess.run([bl, '--version'], capture_output=True, text=True, timeout=120).stdout.splitlines()
        ver = v[0] if v else '?'
        report(f'Blender: {ver}', '5.2' in ver, bl if '5.2' in ver else f'{bl}: this edition is built and checked on 5.2')
    else:
        report('Blender', False, 'install Blender 5.2 (docs/SETUP.md) or set BLENDER=/path/to/blender')
    bash = find_bash()
    report('bash (runs run_blender.sh)', bool(bash), bash or 'install Git for Windows, or set EIDO_BASH')
    appdata = os.environ.get('APPDATA', '')
    vrm = glob.glob(os.path.join(appdata, 'Blender Foundation', 'Blender', '*', 'extensions', '*', 'vrm',
                                 'blender_manifest.toml')) + \
        glob.glob(os.path.expanduser('~/.config/blender/*/extensions/*/vrm/blender_manifest.toml')) + \
        glob.glob(os.path.expanduser('~/Library/Application Support/Blender/*/extensions/*/vrm/blender_manifest.toml'))
    report('VRM extension', bool(vrm), os.path.dirname(sorted(vrm)[-1]) if vrm else
           'install "VRM format" once from Blender (Edit > Preferences > Get Extensions); only VRM scenes need it',
           optional=True)
    for tool in ('ffmpeg', 'ffprobe'):
        p = shutil.which(tool)
        report(tool, bool(p), p or f'install {tool}: probe frames and checks need it')
    if bl and bash and not a.no_render:
        out = os.path.join(os.environ.get('TMP') or os.environ.get('TEMP') or '/tmp', 'eido_blender_doctor.png')
        rc = run_blender(DOCTOR, [out])
        report('EEVEE renders headless (64x64, 1 sample)', rc == 0 and os.path.exists(out),
               '' if rc == 0 else f'Blender exited {rc}: read the lines above')
    comfy = None
    for port in [8188] + list(range(8000, 8021)):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/system_stats', timeout=1.0):
                comfy = port
                break
        except Exception:                                            # noqa: BLE001
            continue
    report('ComfyUI backend', bool(comfy), f'port {comfy}' if comfy else 'not reachable (optional: music/SFX)',
           optional=True)
    jina = bool(os.environ.get('JINA_AI_KEY') or os.environ.get('EIDOVERSE_EMBED_KEY'))
    report('embeddings key', jina, 'fetch_model theme ranking active' if jina else
           'unset: fetch_model ranks by relevance only (optional)', optional=True)
    sys.exit(0 if ok else 1)


def cmd_build(a):
    cfg = load(a.scene)
    job = write_job(cfg, 'build', rebuild=a.rebuild, force=a.force, no_probe_bake=a.no_probe_bake)
    rc = run_blender(RUN_SCENE, [job])
    finish(rc, cfg, 'build', [cfg['_blend'], cfg['_build_json']])


def cmd_render(a):
    cfg = load(a.scene)
    common = dict(rebuild=a.rebuild, force=a.force, no_probe_bake=a.no_probe_bake)
    if a.jump:
        print('note: --jump changes nothing here: a built scene is keyed and baked, so every frame renders the same '
              'whether the render jumps to it or plays up to it')
    if a.at:
        late = [t for t in a.at if t < 0 or t > cfg['duration']]
        if late:
            sys.exit(f"error: --at {late} outside the film (0 to {cfg['duration']} s)")
        mode = 'capture'
        job = write_job(cfg, mode, at=a.at, preroll=a.preroll, preset=a.preset, **common)
        fps, fs = cfg['fps'], cfg['frame_start']
        last = fs + cfgmod.total_frames(cfg) - 1
        stem = cfgmod.output_paths(cfg, mode)['stem']
        frames = sorted({min(last, max(fs, fs + int(round(t * fps)))) for t in a.at})
        expect = [cfgmod.capture_png(stem, (f - fs) / fps) for f in frames]
        print(f'capture: {len(frames)} still(s) -> {stem}_at<seconds>s.png')
    elif a.probe:
        mode = 'probe'
        job = write_job(cfg, mode, frames=max(1, a.frames), preset=a.preset or 'probe', **common)
        expect = [cfgmod.output_paths(cfg, mode)['video']]
    else:
        mode = 'film'
        job = write_job(cfg, mode, preset=a.preset, **common)
        expect = [cfgmod.output_paths(cfg, mode)['video']]
    rc = run_blender(RUN_SCENE, [job])
    finish(rc, cfg, mode, expect)


def cmd_bench(a):
    cfg = load(a.scene)
    job = write_job(cfg, 'bench', frames=max(1, a.frames), preset=a.preset, rebuild=a.rebuild, force=a.force)
    rc = run_blender(RUN_SCENE, [job])
    finish(rc, cfg, 'bench', [])


def cmd_open(a):
    cfg = load(a.scene)
    if not os.path.exists(cfg['_blend']):
        sys.exit(f"error: {cfg['_blend']} is not built yet: python eido_blender.py build {a.scene}")
    bl = find_blender()
    if not bl:
        sys.exit('error: Blender not found (set BLENDER)')
    print(f"opening {cfg['_blend']} in Blender (your own user settings; save to keep hand edits: the next build "
          'will refuse to overwrite them without --force)')
    subprocess.Popen([bl, cfg['_blend']])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('doctor', help='health check')
    p.add_argument('--no-render', action='store_true', help='skip the 64x64 EEVEE render check')
    p.set_defaults(fn=cmd_doctor)

    def build_flags(p):
        p.add_argument('--rebuild', action='store_true', help='rebuild even if the inputs are unchanged')
        p.add_argument('--force', action='store_true', help='rebuild over a .blend edited by hand (its edits are lost)')
        p.add_argument('--no-probe-bake', action='store_true', help='skip baking volume light probes')

    p = sub.add_parser('build', help='build the scene into its .blend (no render)')
    p.add_argument('scene')
    build_flags(p)
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser('render', help='build (or reuse) and render')
    p.add_argument('scene')
    p.add_argument('--probe', action='store_true', help='the first --frames frames, at the probe caps')
    p.add_argument('--frames', type=int, default=1, help='with --probe: how many frames (default 1)')
    p.add_argument('--at', type=float, action='append', metavar='SECONDS',
                   help='a PNG still of the frame at SECONDS (repeat for several), at the film settings')
    p.add_argument('--preroll', type=float, default=0.0, metavar='SECONDS',
                   help='with --at: step the timeline through SECONDS before each still, unrendered (state that is '
                        'still live at render time, e.g. unbaked spring bones)')
    p.add_argument('--jump', action='store_true', help='accepted for eido.py parity; changes nothing here')
    p.add_argument('--preset', choices=cfgmod.PRESETS, help='override the render preset for this run (not saved)')
    build_flags(p)
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser('bench', help='time frames at the film settings and estimate the whole render')
    p.add_argument('scene')
    p.add_argument('--frames', type=int, default=3)
    p.add_argument('--preset', choices=cfgmod.PRESETS)
    p.add_argument('--rebuild', action='store_true')
    p.add_argument('--force', action='store_true')
    p.set_defaults(fn=cmd_bench)

    p = sub.add_parser('open', help="open the built .blend in Blender's window")
    p.add_argument('scene')
    p.set_defaults(fn=cmd_open)

    if eido_docker:
        for name in ('doctor', 'build', 'render', 'bench'):
            sub.choices[name].add_argument('--local', action='store_true',
                                           help='run on this machine instead of inside the render image')
            sub.choices[name].add_argument('--image', help='render image tag (default: the edition\'s render image)')
        eido_docker.add_commands(sub)

    a = ap.parse_args()
    if eido_docker and a.cmd in ('doctor', 'build', 'render', 'bench') and not a.local:
        sys.exit(eido_docker.run_in_container(sys.argv[1:], a))
    a.fn(a)


if __name__ == '__main__':
    main()
