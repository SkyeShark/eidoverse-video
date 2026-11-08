"""Run several trees2 probe scripts in ONE Blender process (one GPU-slot booking):

    bash run_blender.sh blender/tests/trees2/run_batch.py -- demo_scene.py:oak cards_lod_probe.py forest_export_lod.py

Each item is <script>[:arg,arg...] (relative to this folder or absolute); every script
starts from factory settings itself, gets its own arguments after '--', and its
PASS / FAIL lines are summarized at the end. A script that raises is reported and the
batch goes on.
"""

import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    items = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    items = [i for i in items if i != '--']
    report = []
    base_argv = sys.argv[:sys.argv.index('--')] if '--' in sys.argv else sys.argv[:]
    for item in items:
        script, _, args = item.partition(':')
        path = script if os.path.isabs(script) else os.path.join(HERE, script)
        argv = base_argv + ['--'] + ([a for a in args.split(',') if a] if args else [])
        S = sys.modules.get('_scene')
        if S is not None and hasattr(S, 'RESULTS'):
            S.RESULTS.clear()
        sys.argv = argv
        t0 = time.perf_counter()
        print('\n[batch] ===== %s %s' % (os.path.basename(path), args))
        ok = True
        try:
            code = compile(open(path, encoding='utf-8').read(), path, 'exec')
            exec(code, {'__name__': '__main__', '__file__': path})
        except Exception:
            traceback.print_exc()
            ok = False
        S = sys.modules.get('_scene')
        res = list(S.RESULTS) if S is not None and hasattr(S, 'RESULTS') else []
        bad = [n for n, good in res if not good]
        report.append((item, ok, len(res) - len(bad), len(res), bad, time.perf_counter() - t0))
    print('\n[batch] summary')
    for item, ok, npass, n, bad, dt in report:
        print('[batch] %-40s %s  %d/%d PASS  %.0f s%s' % (item, 'ran' if ok else 'RAISED', npass, n, dt,
                                                         ('  FAIL: ' + ', '.join(bad)) if bad else ''))


main()
