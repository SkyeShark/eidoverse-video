"""The Blender edition's fluvial step, timed as blender/tests/terrain/fluvial/test_kernels.py test_cost times it (the
Blender side of tests/fluvial/bench_interleaved.sh; PORT_PLAN.md 8.2 row P6: the step within 1.25 x Blender's
measured cost):

    bash run_blender.sh eidoverse/terrain/tests/fluvial/bench_blender.py --out <json> [--sizes 512,1024,2048]
         [--steps 200]

One whole step (flow_weights, route_incise, h_keep, creep x1, creep_layers, (threshold_excess, threshold) x2: the
production step with fluvial.py's DEFAULTS), on twins.random_field(n, 0, 2000, 1, smooth=2) at 10 m cells, U 2e-3,
K 1.5e-5, Sc 0.7, G 0.5, the outer ring pinned; without and with the lock (64-cell blocks). 5 steps and a read first,
then `steps` steps and a read, timed: the read waits for the GPU, as test_cost's does. Writes the milliseconds per
step. test_cost's sizes are 1024 and 2048; 512, the size of every level of a draft bake, is measured beside them.
Nothing here changes the Blender edition (the parity helpers import it read-only).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'parity'))
import _blender as B  # noqa: E402

B.import_blender_terrain()
import numpy as np  # noqa: E402

from eidoblend.terrain.core import twins as T  # noqa: E402
from eidoblend.terrain.solvers import fluvial as FL  # noqa: E402

F32 = np.float32


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True)
    ap.add_argument('--sizes', default='512,1024,2048')
    ap.add_argument('--steps', type=int, default=200)
    a = ap.parse_args(B.script_args())
    GPU = FL.device('gpu')
    rec = {'edition': 'blender', 'versions': B.versions(), 'steps': a.steps, 'sizes': {}}
    iters, rate = FL.DEFAULTS['threshold_iters'], FL.THRESHOLD_RATE['iso']
    for n in [int(s) for s in a.sizes.split(',')]:
        h = T.random_field((n, n), 0, 2000, 1, smooth=2).astype(F32)
        z = np.zeros((n, n), F32)
        par = T.rgba(z + 2e-3, z + 1.5e-5, z + 0.7, z + 0.5)
        f = {'h': h}
        pins = FL.edge_pins(n, h)
        out = {}
        for label, lock in (('step_ms', None), ('step_with_lock_ms', h)):
            run = FL.FluvialRun(GPU, 10.0, f, par, pins, FL.PINNED, None, lock, 64 if lock is not None else 2)
            for _ in range(5):
                run.step(130.0, 0.05, 1, iters, rate, 5.0)
            run.height()
            t0 = time.perf_counter()
            for _ in range(a.steps):
                run.step(130.0, 0.05, 1, iters, rate, 5.0)
            run.height()
            out[label] = round((time.perf_counter() - t0) * 1000.0 / a.steps, 4)
        rec['sizes'][str(n)] = out
        print(f'[bench] blender {n}^2: {out}', flush=True)
    with open(a.out, 'w') as fh:
        json.dump(rec, fh, indent=1)


if __name__ == '__main__':
    main()
