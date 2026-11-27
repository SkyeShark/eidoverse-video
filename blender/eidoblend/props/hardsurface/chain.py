"""eidoblend.props.hardsurface.chain: an asset's build chain run step by step from plain Python (stdlib only).

    from eidoblend.props.hardsurface import chain
    rc = chain.blender('blender/eidoblend/props/carbine/cli.py', 'high', '--out', 'work/carbine/carbine_high.blend')
    rc = chain.python('blender/tools/gpu_bake.py', '--bake', 'work/carbine/bake', '--name', 'carbine')
    chain.has_warp()          # can this Python bake (warp-lang installed)? chain.has_cuda(): on a GPU?

Every step is its own process, run from the repository root: Blender headless through run_blender.sh (Git Bash on
Windows, never WSL's), plain Python with this interpreter. EIDO_GPU_WRAP, when set, is put in front of every command
(a slot script or a job runner, as blender/tests/_where.py describes); its exit code 75 means "busy, try again later"
and is handed back as it is. Windows children start without a console window.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def find_bash():
    """Git Bash on Windows (never WSL's System32 bash); EIDO_BASH overrides."""
    env = os.environ.get('EIDO_BASH')
    if env:
        return env
    if os.name == 'nt':
        for c in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files (x86)\Git\bin\bash.exe',
                  os.path.expanduser(r'~\AppData\Local\Programs\Git\bin\bash.exe')):
            if os.path.isfile(c):
                return c
    b = shutil.which('bash')
    return b if b and 'system32' not in b.lower() else 'bash'


def run(cmd, log=print, wrap=True) -> int:
    """Run one step (argv) from the repository root, its output passed through; returns its exit code."""
    full = (shlex.split(os.environ.get('EIDO_GPU_WRAP', '')) if wrap else []) + [str(c) for c in cmd]
    t0 = time.time()
    log(f'[chain] {" ".join(full)}')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    rc = subprocess.run(full, cwd=REPO, env=env, creationflags=NO_WINDOW).returncode
    log(f'[chain] exit {rc} after {time.time() - t0:.0f} s')
    return rc


def blender(script, *args, log=print) -> int:
    """A Blender script headless through run_blender.sh (its arguments after Blender's --)."""
    return run([find_bash(), os.path.join(REPO, 'run_blender.sh'), script] + list(args), log=log)


def python(script, *args, log=print, wrap=True) -> int:
    """A plain-Python script with this interpreter."""
    return run([sys.executable, script] + list(args), log=log, wrap=wrap)


def has_warp() -> bool:
    """NVIDIA Warp importable here (the bake's dependency)."""
    import importlib.util
    return importlib.util.find_spec('warp') is not None


def has_cuda() -> bool:
    """A CUDA device Warp can bake on."""
    if not has_warp():
        return False
    r = subprocess.run([sys.executable, '-c', 'import warp as wp; wp.config.quiet = True; wp.init(); print(wp.get_cuda_device_count())'],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    try:
        return int(r.stdout.strip().splitlines()[-1]) > 0
    except (ValueError, IndexError):
        return False
