"""The judge's terrains: every recipe as make_terrain makes it today at the judge's settings (its reference's extent,
seed 1, film quality, no focus), saved for the measures and the view check (Blender, for the level runner's
kernels; nothing is built or rendered):

    EIDO_TERRAIN_CACHE_GB=40 bash run_blender.sh blender/tests/terrain/surfacing_judge/make_terrains.py \\
        [--recipes canyon,dunes] [--again]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Writes out/surfacing_judge/terrains/<recipe>.npz and .json (Terrain.save: the context and main levels' fields and
masks) and lists them in out/surfacing_judge/terrains.json, which check_views.py and baseline.py read. A recipe
already saved is skipped unless --again. Set EIDO_TERRAIN_CACHE_GB above the terrain cache's size, so a cache miss
here does not prune terrains other renders are using.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)

from surfacing_judge import OUT  # noqa: E402  (puts blender/ on the path)
from surfacing_judge import views as V  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

FOLDER = os.path.join(OUT, 'terrains')
LIST = os.path.join(OUT, 'terrains.json')


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = set(a[a.index('--recipes') + 1].split(',')) if '--recipes' in a else None
    plan = V.load(a[a.index('--plan') + 1] if '--plan' in a else None)
    os.makedirs(FOLDER, exist_ok=True)
    listed = {}
    if os.path.exists(LIST):
        with open(LIST, encoding='utf-8') as f:
            listed = json.load(f)
    listed.setdefault('note', 'The judge\'s saved terrains (surfacing_judge/make_terrains.py), relative to '
                              'blender/tests/terrain/out/.')
    for recipe, rec in plan.items():
        if only and recipe not in only:
            continue
        path = os.path.join(FOLDER, recipe + '.npz')
        rel = f'surfacing_judge/terrains/{recipe}.npz'
        if os.path.exists(path) and '--again' not in a:
            listed[recipe] = rel
            print(f'[make_terrains] {recipe}: already saved', flush=True)
            continue
        t0 = time.time()
        try:
            size = refs.load(rec['reference']).extent if rec.get('reference') else None
            t = A.generate(recipe, size=size, seed=1, params=rec.get('params'), quality='film', focus=None)
            t.save(path)
            listed[recipe] = rel
            lv = t.main
            print(f"[make_terrains] {recipe}: {len(t.levels)} levels, main {lv.side:g} m @ {lv.cell:.4g} m, cache "
                  f"{'hit' if t.info.get('cache_hit') else 'miss'}, {time.time() - t0:.0f} s -> {rel}", flush=True)
            del t
        except Exception as e:                           # noqa: BLE001 - reported, the run goes on
            traceback.print_exc()
            print(f'[make_terrains] {recipe}: ERROR {type(e).__name__}: {e}', flush=True)
        with open(LIST, 'w', encoding='utf-8') as f:
            json.dump(listed, f, indent=1)
    print('[make_terrains] done', flush=True)
    os._exit(0)


main()
