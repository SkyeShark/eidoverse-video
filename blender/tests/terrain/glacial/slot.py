"""Run a Blender script of this package through the first free GPU slot (the main checkout's heavy.sh, heavy2.sh,
heavy3.sh, as the judge's launcher does), retrying every SLOT_RETRY_S seconds (default 15) while all are busy, for up
to 60 minutes, from system Python:

    python blender/tests/terrain/glacial/slot.py <script.py> [args...]
    python blender/tests/terrain/glacial/slot.py <chain.sh> [args...]     # several Blender runs in one slot

A .sh runs as `bash <chain.sh> [args]` in the slot (from the main checkout, where its `bash run_blender.sh ...`
lines find the launcher), so a chain of renders and tests holds one slot instead of queueing for each. The log goes
to blender/tests/terrain/out/glacial/logs/<script>_<time>.log (each attempt's refusal is kept in <log>.wait); its
last lines are printed. The exit code is the run's (75: no slot within 60 minutes).
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)

from judge.run import MAIN, SLOTS, WORKTREE  # noqa: E402

LOGS = os.path.join(TN, 'out', 'glacial', 'logs')
# every program this launcher starts runs without a console window on Windows (CREATE_NO_WINDOW): a console
# program started from a process with no console of its own opens a new window over the desktop
NO_WINDOW = {'creationflags': 0x08000000} if os.name == 'nt' else {}


def run_blender(script, args, log_path, timeout_min=None, retry_s=None):
    """(rc, slot): the first of the slot scripts that starts the job (one that refuses exits 75), retried every
    retry_s seconds (SLOT_RETRY_S, default 15) for up to timeout_min minutes (SLOT_TIMEOUT_MIN, default 60); without
    the main checkout's slot scripts, run_blender.sh here."""
    retry_s = float(retry_s or os.environ.get('SLOT_RETRY_S', '15'))
    timeout_min = float(timeout_min or os.environ.get('SLOT_TIMEOUT_MIN', '60'))
    slot_dir = os.path.join(MAIN, 'work', 'claude_body', 'work', 'tmp')
    env = dict(os.environ, HEAVY_VRAM_GB='4')
    run = ['bash', script] if script.endswith('.sh') else ['bash', 'run_blender.sh', script]
    if not os.path.exists(os.path.join(slot_dir, SLOTS[0])):
        with open(log_path, 'w', encoding='utf-8') as log:
            return subprocess.call(run + args, cwd=WORKTREE, stdout=log, stderr=subprocess.STDOUT,
                                   **NO_WINDOW), 'direct'
    t_end = time.time() + 60 * timeout_min
    while True:
        for s in SLOTS:
            cmd = ['bash', f'work/claude_body/work/tmp/{s}', '12'] + run + args
            with open(log_path, 'w', encoding='utf-8') as log:
                rc = subprocess.call(cmd, cwd=MAIN, env=env, stdout=log, stderr=subprocess.STDOUT, **NO_WINDOW)
            if rc != 75:
                return rc, s
            with open(log_path, encoding='utf-8', errors='replace') as f, \
                    open(log_path + '.wait', 'a', encoding='utf-8') as w:
                said = f.read().strip().splitlines()
                w.write(time.strftime('%H:%M:%S ') + (said[-1][:200] if said else '(no reason given)') + '\n')
        if time.time() > t_end:
            return 75, None
        time.sleep(retry_s)


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
