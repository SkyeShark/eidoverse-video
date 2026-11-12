"""Run a Blender script of the coast package through a GPU slot (design section 11), retrying while every slot is
busy (60 s apart, up to 60 minutes). From anywhere, in system Python:

    python blender/tests/terrain/coast/slot.py <script.py> [args...]      # log: out/coast/logs/<script>.log

The slots are the main checkout's heavy.sh, heavy2.sh, heavy3.sh (exit 75: not started). Prints the log's tail.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.environ.get('EIDO_MAIN', 'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01')
SLOTS = ('heavy.sh', 'heavy2.sh', 'heavy3.sh')
LOGS = os.path.normpath(os.path.join(HERE, '..', 'out', 'coast', 'logs'))


def main():
    script = os.path.abspath(sys.argv[1])
    args = sys.argv[2:]
    os.makedirs(LOGS, exist_ok=True)
    tag = os.path.splitext(os.path.basename(script))[0]
    if '--tag' in args:
        tag += '_' + args[args.index('--tag') + 1]
    log_path = os.path.join(LOGS, tag + '.log')
    env = dict(os.environ, HEAVY_VRAM_GB='4')
    t_end = time.time() + 3600
    t0 = time.time()
    while True:
        for s in SLOTS:
            cmd = ['bash', f'work/claude_body/work/tmp/{s}', '12', 'bash', 'run_blender.sh', script] + args
            with open(log_path, 'w', encoding='utf-8') as log:
                rc = subprocess.call(cmd, cwd=MAIN, env=env, stdout=log, stderr=subprocess.STDOUT)
            if rc != 75:
                break
        else:
            if time.time() > t_end:
                print('[slot] every GPU slot stayed busy for 60 minutes', flush=True)
                sys.exit(75)
            print('[slot] every GPU slot is busy: waiting 60 s', flush=True)
            time.sleep(60)
            continue
        break
    with open(log_path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    keep = [ln for ln in lines if not ln.startswith(('Read prefs', 'Blender quit', 'Fra:', 'Warning: '))]
    print('\n'.join(keep[-int(os.environ.get('SLOT_TAIL', 60)):]))
    print(f'[slot] {tag}: rc={rc} ({s}) in {time.time() - t0:.0f} s; log {log_path}', flush=True)
    sys.exit(rc)


if __name__ == '__main__':
    main()
