"""Generate alpine_valley (or any recipe) in Blender (GPU kernels) and save every level's fields, for the numbers
(judged in plain Python by judge_fields.py) and the sheets. No renders (render_photo_views.py renders).

    bash run_blender.sh blender/tests/terrain/glacial/gen.py --job <job.json>
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

job.json: {"out_dir": ..., "items": [{"tag", "recipe" (default alpine_valley), "seed", "params": {...}, "size": m
(default the reference's extent, else the recipe's), "reference": name (default the recipe's first), "resolution":
1024, "focus": [x, y] or null, "hero_cell": 0.5, "stage_params": {op: {...}} (merged into that op's stages after the
knobs resolve: for calibration runs), "defaults": {...} (merged into the recipe's defaults: lakes), "cache": false}]}

Per item, in out_dir: <tag>.npz (the main level: h, cell, frame, water, context_h / context_cell: the judge's field
format), <tag>_levels.npz (every level: L<i>_<field>, and L<i>_window = x0, y0, side, cell, n) and <tag>_record.json
(the plan, the run record, the glacial carve's log).
"""
import copy
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

SAVE = ('h', 'A', 'water', 'wear', 'deposit', 'talus', 'bed', 'Sc', 'ice', 'trough', 'trough_floor', 'trough_wall',
        'ice_q', 'carve', 'valley_fill', 'trunk', 'trough_rho')


def argv():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[a.index('--job') + 1]


def ref_extent(name):
    from judge import refs
    return refs.load(name).extent


def one(item, out_dir):
    R = RG.get(item.get('recipe', 'alpine_valley'))
    if item.get('preset'):                                   # a recipe module's PRESETS entry (alpine_valley)
        import importlib
        pr = importlib.import_module(f"eidoblend.terrain.recipes.{item.get('recipe', 'alpine_valley')}").preset(
            item['preset'], **(item.get('params') or {}))
        item = dict(item, params=pr['params'], **{k: v for k, v in pr.items() if k != 'params' and k not in item})
    if item.get('defaults'):
        R = copy.copy(R)
        R.defaults = dict(R.defaults, **item['defaults'])
    values, stages = R.resolve(item.get('params') or {})
    for op, extra in (item.get('stage_params') or {}).items():
        for s in stages:
            if s.op == op or s.name == op:
                s.params.update(extra)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    ref = item.get('reference') or (R.references[0] if R.references else None)
    size = float(item.get('size') or (ref_extent(ref) if ref else None) or dfl['size'])
    res = int(item.get('resolution', 1024))
    focus = item.get('focus')
    hero = float(item.get('hero_cell', dfl.get('hero_cell', 0.5))) if focus is not None else None
    plan = L.plan_levels(size, res, (0.0, 0.0), item.get('context', dfl.get('context')), focus, hero)
    base = float(item.get('base_elevation_m', dfl.get('base_elevation_m', 0.0)))
    info = {}
    t0 = time.time()
    fields = RUN.run_levels(plan, R, values, stages, seed=int(item.get('seed', 1)), base_elevation_m=base,
                            log=print, cache=bool(item.get('cache', False)), info=info)
    secs = round(time.time() - t0, 2)
    tag = item['tag']
    main = [lv for lv in plan if lv.role == 'main'][0]
    fm = fields[main.index]
    ctx = [lv for lv in plan if lv.role == 'context']
    extra = {}
    if ctx:
        c = ctx[0]
        extra = dict(context_h=np.asarray(fields[c.index]['h'], np.float32), context_cell=c.cell)
    np.savez(os.path.join(out_dir, tag + '.npz'), h=np.asarray(fm['h'], np.float32), cell=main.cell,
             frame='south_up', water=np.asarray(fm.get('water', np.zeros_like(fm['h'])), np.float32),
             base_elevation_m=base, **extra)
    arr = {}
    for lv, f in zip(plan, fields):
        for k in SAVE:
            if k in f:
                arr[f'L{lv.index}_{k}'] = np.asarray(f[k], np.float32)
        arr[f'L{lv.index}_window'] = np.array([lv.x0, lv.y0, lv.side, lv.cell, lv.n], np.float64)
    np.savez_compressed(os.path.join(out_dir, tag + '_levels.npz'), **arr)
    rec = dict(item=item, reference=ref, size=size, resolution=res, seconds=secs, plan=[str(lv) for lv in plan],
               values=values, run=info, glacial=info.get('shared', {}).get('glacial_log'))
    with open(os.path.join(out_dir, tag + '_record.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    print(f'[glacial.gen] {tag}: {len(plan)} levels in {secs} s', flush=True)


def main():
    with open(argv(), encoding='utf-8') as f:
        job = json.load(f)
    os.makedirs(job['out_dir'], exist_ok=True)
    for item in job['items']:
        try:
            one(item, job['out_dir'])
        except Exception:                                              # noqa: BLE001 - the job goes on
            traceback.print_exc()
            print(f"[glacial.gen] {item['tag']}: FAILED", flush=True)
    print('[glacial.gen] done', flush=True)
    os._exit(0)                       # Blender's shader destructors crash at interpreter teardown (core/test_gpu.py)


main()
