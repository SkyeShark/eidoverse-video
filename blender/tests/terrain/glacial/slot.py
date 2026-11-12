"""Run a Blender script of this package through the first free GPU slot (the judge's launcher: heavy.sh, heavy2.sh,
heavy3.sh, retrying every 60 s while all are busy), from system Python:

    python blender/tests/terrain/glacial/slot.py <script.py> [args...]

The log goes to blender/tests/terrain/out/glacial/logs/<script>_<time>.log; its last lines are printed. The exit
code is Blender's (75: no slot within 60 minutes).
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)

from judge.run import run_blender  # noqa: E402

LOGS = os.path.join(TN, 'out', 'glacial', 'logs')


def main():
    script, args = os.path.abspath(sys.argv[1]), sys.argv[2:]
    os.makedirs(LOGS, exist_ok=True)
    log = os.path.join(LOGS, f"{os.path.splitext(os.path.basename(script))[0]}_{time.strftime('%H%M%S')}.log")
    t0 = time.time()
    rc, slot = run_blender(script, args, log)
    with open(log, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    keep = [ln for ln in lines if not ln.startswith(('Read prefs', 'Blender quit', 'Color management'))]
    print('\n'.join(keep[-int(os.environ.get('SLOT_TAIL', '60')):]))
    print(f'[slot] rc={rc} ({slot}) in {time.time() - t0:.0f} s; log {log}', flush=True)
    sys.exit(rc)


main()
