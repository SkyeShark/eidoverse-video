"""Run a Blender script of the coast package through a GPU slot (design section 11), retrying while every slot is
busy (60 s apart, up to 60 minutes). From anywhere, in system Python:

    python blender/tests/terrain/coast/slot.py <script.py> [args...]      # log: out/coast/logs/<script>.log

The slot is EIDO_GPU_WRAP's queue when it is set (blender/tests/_where.py; exit 75: not started), else Blender runs
directly. Prints the log's tail.
Every child runs without a console window (CREATE_NO_WINDOW on Windows: a bash started from a windowless Python
otherwise opens a blank console over the desktop).
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))      # blender/tests: _where
import _where  # noqa: E402
LOGS = os.path.normpath(os.path.join(HERE, '..', 'out', 'coast', 'logs'))
NO_WINDOW = {'creationflags': 0x08000000} if os.name == 'nt' else {}


def main():
    script = os.path.abspath(sys.argv[1])
    args = sys.argv[2:]
    os.makedirs(LOGS, exist_ok=True)
    tag = os.path.splitext(os.path.basename(script))[0]
    if '--tag' in args:
        tag += '_' + args[args.index('--tag') + 1]
    log_path = os.path.join(LOGS, tag + '.log')
    env = dict(os.environ, HEAVY_VRAM_GB='4', GPU_MEMCAP_GB='12')       # the job's VRAM estimate and RAM cap
    cmd = _where.blender_cmd(script, *args)
    s = 'EIDO_GPU_WRAP' if os.environ.get('EIDO_GPU_WRAP') else 'direct'
    t_end = time.time() + 3600
    t0 = time.time()
    while True:
        with open(log_path, 'w', encoding='utf-8') as log:
            rc = subprocess.call(cmd, cwd=_where.REPO, env=env, stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, **NO_WINDOW)
        if rc != 75 or s == 'direct':
            break
        if time.time() > t_end:
            print('[slot] every GPU slot stayed busy for 60 minutes', flush=True)
            sys.exit(75)
        print('[slot] every GPU slot is busy: waiting 60 s', flush=True)
        time.sleep(60)
    with open(log_path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    keep = [ln for ln in lines if not ln.startswith(('Read prefs', 'Blender quit', 'Fra:', 'Warning: '))]
    print('\n'.join(keep[-int(os.environ.get('SLOT_TAIL', 60)):]))
    print(f'[slot] {tag}: rc={rc} ({s}) in {time.time() - t0:.0f} s; log {log_path}', flush=True)
    sys.exit(rc)


if __name__ == '__main__':
    main()
