"""Tuning harness (Blender, GPU): the detail ops with parameter variants on the hero levels of a saved upsampled run,
each level on its own (a level starts from the DEM upsampled, not from its detailed parent), written as runs that
sheets.py reads:

    bash run_blender.sh <worktree>/blender/tests/terrain_new/detail/tune.py --src lb1_upsampled --tag t1 \\
        --variants '{"A": {"breakup": {}, "hydraulic": {}}, "B": {"hydraulic": {"qc": 0.5}}}' [--levels 4,5,6]

A variant without a "breakup" key skips the breakup, and likewise "hydraulic". Writes runs/<tag>_<variant>/ (the
source run's other levels copied), so `sheets.py --tag <tag> --variants A,B` compares them with the real ground.
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.core.levels import Level  # noqa: E402
from eidoblend.terrain.solvers import detail as DT  # noqa: E402
from eidoblend.terrain.solvers import hydraulic as HY  # noqa: E402

RUNS = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail', 'runs'))


def main():
    a = plain_import.script_args()
    get = (lambda k, d: a[a.index(k) + 1] if k in a else d)
    src = os.path.join(RUNS, get('--src', 'lb1_upsampled'))
    tag = get('--tag', 't1')
    variants = json.loads(get('--variants', '{"A": {"breakup": {}, "hydraulic": {}}}'))
    with open(os.path.join(src, 'run.json')) as f:
        rec = json.load(f)
    plan = [Level.from_dict(x) for x in rec['plan']]
    levels = [int(v) for v in get('--levels', ','.join(str(lv.index) for lv in plan if lv.role == 'hero')).split(',')]
    for name, var in variants.items():
        d = os.path.join(RUNS, f'{tag}_{name}')
        os.makedirs(d, exist_ok=True)
        times = {}
        for lv in plan:
            p = os.path.join(src, f'L{lv.index}.npz')
            if lv.index not in levels:
                shutil.copyfile(p, os.path.join(d, f'L{lv.index}.npz'))
                continue
            with np.load(p) as z:
                f = Fields(lv, {k: z[k] for k in z.files if k in ('h', 'bed', 'A', 'water')})
            t0 = time.perf_counter()
            if 'breakup' in var:
                DT.op_breakup(f, lv, var['breakup'], seed=1)
            if 'hydraulic' in var:
                HY.op_hydraulic(f, lv, var['hydraulic'], seed=1)
            times[lv.index] = round(time.perf_counter() - t0, 2)
            np.savez_compressed(os.path.join(d, f'L{lv.index}.npz'), **{k: np.asarray(v) for k, v in f.items()})
        with open(os.path.join(d, 'run.json'), 'w') as fo:
            json.dump(dict(rec, variant=name, params=var, seconds=times, tuned_levels=levels), fo, indent=1)
        print(f'[tune] {tag}_{name}: {times}', flush=True)


main()
