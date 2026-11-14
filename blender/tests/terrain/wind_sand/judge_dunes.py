"""Quick in-process judging of dunes variants (numbers only; the compare sheets come from the judge's own one
command, judge/run.py). In Blender (the slab model needs the GPU):

    bash run_blender.sh blender/tests/terrain/wind_sand/judge_dunes.py --variants <file.json> [--quality film] \\
        [--tag name]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

<file.json>: [[label, {"ref": "namib_star_dunes", "params": {...knobs...}, "set": {...dune_field params...}}], ...]
"set" overrides the dune_field stage's own parameters (solvers/aeolian.FIELD_DEFAULTS / DEFAULTS), through a recipe
dict. Each variant: generate() at the reference's extent, then the judge's judge() (judge/judging.py: matched to the
reference's pixel and source chain, its calibrated bands and the dune family's numbers). Prints each verdict's table
and writes out/wind_sand/variants<tag>/<label>.json and <label>.npz (the main level, row 0 south, and its sand).
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_NEW = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TERRAIN_NEW, 'core'))
sys.path.insert(0, HERE)
sys.path.insert(0, TERRAIN_NEW)
import plain_import  # noqa: E402
plain_import.install()

import numpy as np  # noqa: E402
from eidoblend.terrain import api  # noqa: E402
from eidoblend.terrain import recipes as R  # noqa: E402
from eidoblend.terrain.solvers import aeolian as A  # noqa: E402
from judge import judge, refs  # noqa: E402
import dune_measures as DM  # noqa: E402

OUT = os.path.join(TERRAIN_NEW, 'out', 'wind_sand')


def args():
    a = plain_import.script_args()
    opt = dict(quality='film', tag='', seed='1')
    i = 0
    while i < len(a):
        opt[a[i].lstrip('-')] = a[i + 1]
        i += 2
    return opt


def recipe_with(stage_set):
    """The dunes recipe as a dict with extra dune_field parameters (an agent's way: to_dict, edit, pass back)."""
    d = R.get('dunes').to_dict()
    for st in d['stages']:
        if st['op'] == 'dune_field':
            st['params'].update(stage_set or {})
    return d


def run_variant(label, v, opt, out):
    ref = refs.load(v['ref']) if v.get('ref') else None
    t0 = time.perf_counter()
    logs = []

    def log(m):
        logs.append(m)
        print(m, flush=True)
    t = api.generate(recipe_with(v.get('set')), size=ref.extent if ref else None, seed=int(v.get('seed', opt['seed'])),
                     params=v.get('params'), quality=opt['quality'], cache=False, log=log)
    sec = round(time.perf_counter() - t0, 2)
    f = t.fields('main')
    lv = t.main
    h, sand = np.asarray(f['h'], np.float64), np.asarray(f['sand'], np.float64)
    _values, stages = t.recipe.resolve(v.get('params'))
    p = A.resolve_params(stages[0].params)
    rec = dict(label=label, variant=v, seconds=sec, levels=[repr(x) for x in t.levels],
               log=[m for m in logs if 'aeolian' in m], measures=DM.summary(h, lv.cell, sand, p['winds'], 0.5),
               dune_height_m=A.dune_height(sand), target=dict(spacing_m=p['spacing_m'], height_m=p['target_height_m']))
    if ref is not None:
        verdict = judge(t, ref, hints={'target_spacing_m': p['spacing_m']}, label=label)
        print(verdict.table(), flush=True)
        rec['verdict'] = verdict.to_dict()
    np.savez_compressed(os.path.join(out, f'{label}.npz'), h=h.astype(np.float32), sand=sand.astype(np.float32),
                        cell=lv.cell)
    with open(os.path.join(out, f'{label}.json'), 'w', encoding='utf-8') as fo:
        json.dump(rec, fo, indent=1, default=str)
    print(f'[wind_sand variants] {label}: {sec} s', flush=True)


def main():
    opt = args()
    variants = json.load(open(opt['variants'], encoding='utf-8'))
    out = os.path.join(OUT, 'variants' + (('_' + opt['tag']) if opt['tag'] else ''))
    os.makedirs(out, exist_ok=True)
    for label, v in variants:
        try:
            run_variant(label, v, opt, out)
        except Exception:                                          # noqa: BLE001
            print(f'[wind_sand variants] {label} failed:\n{traceback.format_exc()}', flush=True)


main()
