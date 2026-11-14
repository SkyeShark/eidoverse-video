"""The dunes recipe's whole level stack dumped for looking: every level's height, bed and sand, with hero levels on
the highest dune of the main tile's inner 5 km (where the review's crest and interdune views stand). In Blender (the
slab model needs the GPU):

    bash run_blender.sh blender/tests/terrain/wind_sand/dune_lab.py --tag name [--variants <file.json>] [--judge 1] \\
        [--focus x,y] [--seed 1]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

<file.json>: [[label, {"params": {...knobs...}, "set": {...dune_field params...}}], ...] (as judge_dunes.py); without
it one variant, the recipe as it stands, labelled 'base'. Writes out/wind_sand/lab_<tag>/<label>.npz: per level i the
arrays h_i, bed_i, sand_i (row 0 south) and win_i = (x0, y0, cell, n), plus focus; and <label>.json with the levels,
timings, the solver's log and (with --judge 1) the judge's verdict against namib_star_dunes.
look_lab.py draws them.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_TESTS = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TERRAIN_TESTS, 'core'))
sys.path.insert(0, HERE)
sys.path.insert(0, TERRAIN_TESTS)
import plain_import  # noqa: E402
plain_import.install()

import numpy as np  # noqa: E402
from eidoblend.terrain import api  # noqa: E402
from eidoblend.terrain import recipes as R  # noqa: E402

OUT = os.path.join(TERRAIN_TESTS, 'out', 'wind_sand')


def args():
    a = plain_import.script_args()
    opt = dict(tag='lab', seed='1', judge='0', focus='', variants='', quality='film', size='8000')
    i = 0
    while i < len(a):
        opt[a[i].lstrip('-')] = a[i + 1]
        i += 2
    return opt


def recipe_with(stage_set):
    d = R.get('dunes').to_dict()
    for st in d['stages']:
        if st['op'] == 'dune_field':
            st['params'].update(stage_set or {})
    return d


def highest_inner(t, half=2500.0):
    """The highest cell of the main level within `half` metres of the tile centre: (x, y, z)."""
    f = t.fields('main')
    lv = t.main
    h = np.asarray(f['h'], np.float64)
    X, Y = lv.xy()
    cx, cy = lv.centre
    inner = (np.abs(X - cx) < half) & (np.abs(Y - cy) < half)
    k = int(np.argmax(np.where(inner, h, -np.inf)))
    j, i = np.unravel_index(k, h.shape)
    return float(X[j, i]), float(Y[j, i]), float(h[j, i])


def run_variant(label, v, opt, out):
    logs = []

    def log(m):
        logs.append(m)
        print(m, flush=True)
    rec_dict = recipe_with(v.get('set'))
    seed = int(v.get('seed', opt['seed']))
    size = float(v.get('size', opt['size']))
    t0 = time.perf_counter()
    if opt['focus']:
        fx, fy = (float(s) for s in opt['focus'].split(','))
    else:
        t = api.generate(rec_dict, size=size, seed=seed, params=v.get('params'), quality=opt['quality'],
                         cache=False, log=log)
        fx, fy, fz = highest_inner(t)
        log(f'[lab] highest dune of the inner 5 km: ({fx:.0f}, {fy:.0f}) at {fz:.0f} m')
        del t
    t1 = time.perf_counter()
    t = api.generate(rec_dict, size=size, seed=seed, params=v.get('params'), quality=opt['quality'],
                     focus=[(fx, fy)], cache=False, log=log)
    arrays = dict(focus=np.array([fx, fy]))
    for i, lv in enumerate(t.levels):
        f = t.fields(i)
        arrays[f'h_{i}'] = np.asarray(f['h'], np.float32)
        if 'bed' in f:
            arrays[f'bed_{i}'] = np.asarray(f['bed'], np.float32)
        if 'sand' in f:
            arrays[f'sand_{i}'] = np.asarray(f['sand'], np.float32)
        arrays[f'win_{i}'] = np.array([lv.x0, lv.y0, lv.cell, lv.n], np.float64)
    np.savez_compressed(os.path.join(out, f'{label}.npz'), **arrays)
    rec = dict(label=label, variant=v, seconds_first=round(t1 - t0, 2), seconds_focus=round(time.perf_counter() - t1, 2),
               levels=[repr(x) for x in t.levels], focus=[fx, fy], log=[m for m in logs if 'aeolian' in m])
    if opt['judge'] == '1':
        from judge import judge, refs
        from eidoblend.terrain.solvers import aeolian as A
        ref = refs.load('namib_star_dunes')
        _values, stages = t.recipe.resolve(v.get('params'))
        p = A.resolve_params(stages[0].params)
        tj = api.generate(rec_dict, size=ref.extent, seed=seed, params=v.get('params'), quality=opt['quality'],
                          cache=False, log=log)
        verdict = judge(tj, ref, hints={'target_spacing_m': p['spacing_m']}, label=label)
        print(verdict.table(), flush=True)
        rec['verdict'] = verdict.to_dict()
    with open(os.path.join(out, f'{label}.json'), 'w', encoding='utf-8') as fo:
        json.dump(rec, fo, indent=1, default=str)
    print(f'[wind_sand lab] {label}: {rec["seconds_first"]} + {rec["seconds_focus"]} s', flush=True)


def main():
    opt = args()
    variants = json.load(open(opt['variants'], encoding='utf-8')) if opt['variants'] else [['base', {}]]
    out = os.path.join(OUT, 'lab_' + opt['tag'])
    os.makedirs(out, exist_ok=True)
    for label, v in variants:
        try:
            run_variant(label, v, opt, out)
        except Exception:                                          # noqa: BLE001
            print(f'[wind_sand lab] {label} failed:\n{traceback.format_exc()}', flush=True)
    os._exit(0)


main()
