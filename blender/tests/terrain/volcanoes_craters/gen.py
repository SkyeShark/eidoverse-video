"""Generate package 9's recipes in Blender (GPU kernels) and save their fields, for the judge's numbers and the sheets
(judged in plain Python by judge_recipes.py). No renders here: render_recipes.py renders.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/volcanoes_craters/gen.py --job <job.json>
    (or: python blender/tests/terrain/volcanoes_craters/vc.py gen ... , which writes the job and finds a slot)

job.json: {"out_dir": ..., "items": [{"tag", "recipe", "seed", "params": {...}, "size": m (default the recipe's
reference extent), "resolution": 1024, "focus": [x, y] or null, "hero_cell": 0.5, "stage_params": {op or name:
{...}} (merged into those stages after the knobs resolve: calibration runs), "cache": false}]}

Per item, in out_dir: <tag>.npz (the main level: h, cell, frame, water, context_h / context_cell: the judge's field
format), <tag>_levels.npz (every level: L<i>_<field>, and L<i>_window = x0, y0, side, cell, n) and
<tag>_record.json (the plan, the knob values, the run record: per-level seconds and stages, fluvial passes, lakes).
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

import numpy as np  # noqa: E402

from eidoblend.terrain import recipes as RG  # noqa: E402
from eidoblend.terrain import run as RUN  # noqa: E402
from eidoblend.terrain.core import levels as L  # noqa: E402

SAVE = ('h', 'A', 'water', 'wear', 'deposit', 'talus', 'bed', 'lava', 'Sc')


def argv():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[a.index('--job') + 1]


def ref_extent(recipe):
    from judge import refs
    names = refs.RECIPE_REFERENCES.get(recipe)
    return refs.load(names[0]).extent if names else None


def one(item, out_dir):
    R = RG.get(item['recipe'])
    values, stages = R.resolve(item.get('params') or {})
    for op, extra in (item.get('stage_params') or {}).items():
        for s in stages:
            if s.op == op or s.name == op:
                s.params.update(extra)
    size = float(item.get('size') or ref_extent(item['recipe']) or R.defaults['size'])
    res = int(item.get('resolution', 1024))
    focus = item.get('focus')
    hero = float(item.get('hero_cell', R.defaults.get('hero_cell', 0.5))) if focus is not None else None
    plan = L.plan_levels(size, res, tuple(R.defaults.get('centre', (0.0, 0.0))),
                         item.get('context', R.defaults.get('context')), focus, hero)
    info = {}
    t0 = time.time()
    fields = RUN.run_levels(plan, R, values, stages, seed=int(item.get('seed', 1)),
                            base_elevation_m=float(R.defaults.get('base_elevation_m', 0.0)), log=print,
                            cache=bool(item.get('cache', False)), info=info)
    secs = round(time.time() - t0, 2)
    tag = item['tag']
    main = [lv for lv in plan if lv.role == 'main'][0]
    fm = fields[main.index]
    ctx = [lv for lv in plan if lv.role == 'context']
    extra = {}
    if ctx:
        c = ctx[-1]                                   # the context level next to the main one
        extra = dict(context_h=np.asarray(fields[c.index]['h'], np.float32), context_cell=c.cell)
    np.savez(os.path.join(out_dir, tag + '.npz'), h=np.asarray(fm['h'], np.float32), cell=main.cell,
             frame='south_up', water=np.asarray(fm.get('water', np.zeros_like(fm['h'])), np.float32), **extra)
    arr = {}
    for lv, f in zip(plan, fields):
        for k in SAVE:
            if k in f:
                arr[f'L{lv.index}_{k}'] = np.asarray(f[k], np.float32)
        arr[f'L{lv.index}_window'] = np.array([lv.x0, lv.y0, lv.side, lv.cell, lv.n], np.float64)
    np.savez_compressed(os.path.join(out_dir, tag + '_levels.npz'), **arr)
    rec = dict(item=item, size=size, resolution=res, seconds=secs, plan=[str(lv) for lv in plan],
               values=values, run=info)
    with open(os.path.join(out_dir, tag + '_record.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    print(f'[volc.gen] {tag}: {len(plan)} levels in {secs} s', flush=True)


def main():
    with open(argv(), encoding='utf-8') as f:
        job = json.load(f)
    os.makedirs(job['out_dir'], exist_ok=True)
    for item in job['items']:
        try:
            one(item, job['out_dir'])
        except Exception:                                              # noqa: BLE001 - the job goes on
            traceback.print_exc()
            print(f"[volc.gen] {item['tag']}: FAILED", flush=True)
    print('[volc.gen] done', flush=True)
    os._exit(0)                       # Blender's shader destructors crash at interpreter teardown (core/test_gpu.py)


main()
