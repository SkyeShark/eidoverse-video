"""Run a Blender script of this package as a GPU job, queued through EIDO_GPU_WRAP when it is set (as the judge's
launcher does: blender/tests/_where.py), retrying every SLOT_RETRY_S seconds (default 15) while the queue says every
slot is busy, for up to 60 minutes, from system Python:

    python blender/tests/terrain/glacial/slot.py <script.py> [args...]
    python blender/tests/terrain/glacial/slot.py <chain.sh> [args...]     # several Blender runs in one slot

A .sh runs as `bash <chain.sh> [args]` in one job (from a checkout's root, where its `bash run_blender.sh ...`
lines find the launcher), so a chain of renders and tests holds one slot instead of queueing for each. The log goes
to blender/tests/terrain/out/glacial/logs/<script>_<time>.log (each attempt's refusal is kept in <log>.wait); its
last lines are printed. The exit code is the run's (75: no slot within 60 minutes).
"""
import os
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)
sys.path.insert(0, os.path.dirname(TN))                       # blender/tests: _where

import _where  # noqa: E402
from judge.run import WORKTREE  # noqa: E402

LOGS = os.path.join(TN, 'out', 'glacial', 'logs')
# every program this launcher starts runs without a console window on Windows (CREATE_NO_WINDOW): a console
# program started from a process with no console of its own opens a new window over the desktop
NO_WINDOW = {'creationflags': 0x08000000} if os.name == 'nt' else {}


def run_blender(script, args, log_path, timeout_min=None, retry_s=None):
    """(rc, how): the job through $EIDO_GPU_WRAP when it is set (a queue that exits 75 when it did not start the job),
    retried every retry_s seconds (SLOT_RETRY_S, default 15) for up to timeout_min minutes (SLOT_TIMEOUT_MIN, default
    60); without it, run_blender.sh here."""
    retry_s = float(retry_s or os.environ.get('SLOT_RETRY_S', '15'))
    timeout_min = float(timeout_min or os.environ.get('SLOT_TIMEOUT_MIN', '60'))
    env = dict(os.environ, HEAVY_VRAM_GB='4', GPU_MEMCAP_GB='12')       # the job's VRAM estimate and RAM cap
    wrap = shlex.split(os.environ.get('EIDO_GPU_WRAP', ''))            # _where.blender_cmd's prefix, a chain's too
    cmd = (wrap + ['bash', script] + args) if script.endswith('.sh') else _where.blender_cmd(script, *args)
    if not wrap:
        with open(log_path, 'w', encoding='utf-8') as log:
            return subprocess.call(cmd, cwd=WORKTREE, stdout=log, stderr=subprocess.STDOUT,
                                   **NO_WINDOW), 'direct'
    t_end = time.time() + 60 * timeout_min
    while True:
        with open(log_path, 'w', encoding='utf-8') as log:
            rc = subprocess.call(cmd, cwd=WORKTREE, env=env, stdout=log, stderr=subprocess.STDOUT, **NO_WINDOW)
        if rc != 75:
            return rc, 'EIDO_GPU_WRAP'
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
