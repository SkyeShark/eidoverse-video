"""Blender's real_place recipe, as fixtures for the mesh and API package's tests (PORT_PLAN.md 3.2, 8.2 P4).

The Blender edition's own recipes/real_place.py, run by the Blender edition's own Python (Blender 5.2's bundled
Python 3.13, numpy 2.3.4: the plan's C6): numpy only. Into <out>/:

  recipe.json           REAL_PLACE.to_dict(), dem_names(), the text of the error for an unknown DEM
  <dem>_<quality>/      for each case: the resolved knobs and the `dem` stage's parameters, defaults_for(values),
                        the level plan (api.py's own size, resolution and context), and on every context and main
                        level op_dem's h (and water, where the DEM has water bodies) as float32

    <Blender's python> -I -B eidoverse/terrain/tests/mesh_api/real_place_expected.py [--out DIR] [--cases a,b]

The Blender edition is found beside eidoverse/ (a merged checkout) or at $EIDO_BLENDER_EDITION; the DEMs as
real_place.py finds them (EIDO_TERRAIN_DEMS, then that checkout's reference data). -B keeps Python from writing
bytecode into the Blender checkout, which these fixtures only read.
"""
import argparse
import json
import os
import platform
import sys
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api', 'real_place_fixtures'))
RECORDED_COMMIT = 'f90c6fc'
# (DEM, quality): the main tile as the DEM's own pixels (film), a box average of them (draft), a lake inside the DEM,
# a sea with the surround's sea rule, several lakes with a context of 2
CASES = [('lauterbrunnen', 'film'), ('lauterbrunnen', 'draft'), ('crater_lake', 'film'), ('cliffs_of_moher', 'film'),
         ('mount_fuji', 'film')]


def blender_edition():
    for root in (REPO, os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return os.path.normpath(root)
    sys.exit('real_place_expected.py: no Blender edition: set EIDO_BLENDER_EDITION to the root of a checkout of the '
             'blender branch')


BLE = blender_edition()
sys.path.insert(0, os.path.join(BLE, 'blender'))
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.core import levels as LV  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402
from eidoblend.terrain.recipes import real_place as RP  # noqa: E402


def plain(v):
    return json.loads(json.dumps(A._plain(v)))


def source_state():
    import subprocess

    def git(*a):
        try:
            return subprocess.run(['git', '-C', BLE, *a], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return None
    files = ['blender/eidoblend/terrain/recipes/real_place.py', 'blender/eidoblend/terrain/core/levels.py',
             'blender/eidoblend/terrain/core/io.py', 'blender/eidoblend/terrain/api.py']
    return dict(head=git('rev-parse', '--short', 'HEAD'), recorded=RECORDED_COMMIT,
                changed_since_recorded={s: bool(git('diff', '--stat', RECORDED_COMMIT, '--', s)) for s in files})


def run_case(name, quality, out, base_man):
    t0 = time.perf_counter()
    values, stages = RP.REAL_PLACE.resolve({'dem': name})
    dfl = dict(RP.REAL_PLACE.defaults)
    dfl.update(RP.defaults_for(values))
    Q = LV.QUALITY[quality]
    size = float(dfl['size'])
    res = int(A._scaled_resolution(dfl.get('resolution'), quality) or Q['resolution'])
    plan = LV.plan_levels(size, res, tuple(dfl.get('centre', (0.0, 0.0))), dfl.get('context'), None, None,
                          warn=lambda m: None)
    folder = os.path.join(out, f'{name}_{quality}')
    os.makedirs(folder, exist_ok=True)
    params = stages[0].params
    dem = RP.load(name)
    levels = []
    for lv in plan:
        if lv.role not in ('context', 'main'):
            continue
        f = Fields(lv)
        RP.op_dem(f, lv, params)
        rec = dict(index=lv.index, role=lv.role, n=lv.n, cell=lv.cell, fields=sorted(f), bed_is_h=bool(np.array_equal(f['bed'], f['h'])),
                   h_min=float(f['h'].min()), h_max=float(f['h'].max()))
        f['h'].tofile(os.path.join(folder, f'h_{lv.index}.bin'))
        if 'water' in f:
            f['water'].tofile(os.path.join(folder, f'water_{lv.index}.bin'))
            rec['water_cells'] = int((f['water'] > 0).sum())
            rec['water_max'] = float(f['water'].max())
        levels.append(rec)
    man = dict(base_man, dem=name, quality=quality, values=plain(values), stage_params=plain(params),
               defaults_for=plain(RP.defaults_for(values)), size=size, resolution=res, plan=[lv.to_dict() for lv in plan],
               levels=levels, base=float(dem.base(values.get('base', 'auto'))), water=plain(dem.water),
               dem_pixel=dem.pixel, dem_n=dem.n, context_pixel=(float(dem.ctx[1]) if dem.ctx is not None else None),
               seconds=round(time.perf_counter() - t0, 2))
    with open(os.path.join(folder, 'manifest.json'), 'w') as fh:
        json.dump(man, fh, indent=1)
    print(f'[real_place_expected] {name} {quality}: {len(levels)} levels of {res} cells, base {man["base"]:.3f} m, '
          f'water {[w.get("kind") for w in dem.water]}, {man["seconds"]} s', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--cases', help='<dem>_<quality>, comma-separated')
    a = ap.parse_args()
    want = set(a.cases.split(',')) if a.cases else None
    os.makedirs(a.out, exist_ok=True)
    base_man = dict(python=platform.python_version(), numpy=np.__version__, zlib=zlib.ZLIB_VERSION, source=source_state(),
                    made=time.strftime('%Y-%m-%d %H:%M:%S'))
    try:
        RP.load('lauterbrunen')
        err = None
    except KeyError as e:
        err = str(e.args[0])
    with open(os.path.join(a.out, 'recipe.json'), 'w') as fh:
        json.dump(dict(base_man, recipe=RP.REAL_PLACE.to_dict(), dem_names=RP.dem_names(), unknown_dem_error=err,
                       describe=RP.REAL_PLACE.describe()), fh, indent=1)
    have = set(RP.dem_names())
    for name, quality in CASES:
        if want is not None and f'{name}_{quality}' not in want:
            continue
        if name not in have:
            print(f'[real_place_expected] SKIP {name}: not among the DEMs here ({", ".join(sorted(have)) or "none"}): '
                  'fetch the references (blender/tests/terrain/reference/fetch_references.py) or set EIDO_TERRAIN_DEMS',
                  flush=True)
            continue
        run_case(name, quality, a.out, base_man)


if __name__ == '__main__':
    main()
