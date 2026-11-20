"""The Blender edition's own runs the glacial package compares the port with, where bake.py cannot make them:
alpine_valley's 'yosemite' preset (recipes/alpine_valley.py PRESETS: a 12 km tile, its base elevation 1100 m, the
upland horseshoe draining west), at draft quality, saved in the Terrain.save format both editions read. Run in
Blender (its GPU kernels), as bake.py runs:

    bash run_blender.sh eidoverse/terrain/tests/glacial/blender_runs.py -- <out folder> [--seeds 1,2,3,4] [--quality draft]

Per seed, <out>/alpine_valley_yosemite_s<seed>.npz + .json (api.generate(...).save, bake.py's call with the preset's
size, knobs and base elevation) and <out>/alpine_valley_yosemite_s<seed>_bake.json (the run record, as bake.py writes
it). A GPU job: on a shared machine behind $EIDO_GPU_WRAP.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

B.import_blender_terrain()
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.recipes import alpine_valley as AV  # noqa: E402

args = B.script_args()
out = args[0]
seeds = [1, 2, 3, 4]
quality = 'draft'
if '--seeds' in args:
    seeds = [int(s) for s in args[args.index('--seeds') + 1].split(',')]
if '--quality' in args:
    quality = args[args.index('--quality') + 1]
os.makedirs(out, exist_ok=True)
for s in seeds:
    p = AV.preset('yosemite')
    name = f'alpine_valley_yosemite_s{s}'
    t0 = time.perf_counter()
    t = A.generate('alpine_valley', size=p['size'], seed=s, params=p['params'], base_elevation_m=p['base_elevation_m'],
                   quality=quality, cache=False)
    t.save(os.path.join(out, name))
    rec = dict(recipe='alpine_valley', preset='yosemite', seed=s, quality=quality, knobs=t.knobs,
               seconds=round(time.perf_counter() - t0, 2), levels=[str(lv) for lv in t.levels],
               skipped_stages=t.info['skipped_stages'], warnings=t.info['warnings'], versions=B.versions())
    with open(os.path.join(out, name + '_bake.json'), 'w', encoding='utf-8') as f:
        json.dump(A._plain(rec), f, indent=1)
    print(f'[glacial] {name}: {rec["seconds"]} s', flush=True)
