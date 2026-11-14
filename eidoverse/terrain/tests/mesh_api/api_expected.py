"""Blender's Terrain API, as fixtures for the mesh and API package's tests (PORT_PLAN.md 7.1-7.4, 8.2 P4).

The Blender edition's own api.py, run by the Blender edition's own Python (Blender 5.2's bundled Python 3.13, numpy
2.3.4: the plan's C6) on Blender Terrain.save files: Terrain.load(build=False) needs no bpy. Per save, into
<out>/<case>/:

  levels      api._level_index for every level spec
  masks       MaskSet.names(), and Mask.at at 300 points (inside the finest level, on the main tile, on the context)
              for a few masks
  viewpoint   Terrain.viewpoint for several targets, distances and options: the Viewpoint, or the error's text
  flatten     api.flatten_fields on copies of the save's h and bed: a disc (median height), a rotated rectangle, an
              area smaller than a cell, a given height: the resolved areas, which levels each changed, and the
              flattened h and bed of every changed level
  save        Terrain.save of the loaded terrain: the sha1 of the npz it wrote (Blender's own load -> save), beside
              the original's
  plants      build/plants.py plan_plants on the terrain (masks alone), saved with PlantSpots.save: the spots files
              a Terrain.save carries (SURFACING_DESIGN.md 4.5), and their sha1

    <Blender's python> -I -B eidoverse/terrain/tests/mesh_api/api_expected.py [--out DIR] [--cases a,b]
        [--save NAME=PATH]...

The Blender edition is found beside eidoverse/ (a merged checkout) or at $EIDO_BLENDER_EDITION. Saves as
mesh_expected.py names them (--save NAME=PATH, else the defaults in that checkout's ignored output folders). -B
keeps Python from writing bytecode into the Blender checkout, which these fixtures only read.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api', 'api_fixtures'))
RECORDED_COMMIT = 'f90c6fc'
DEFAULT_SAVES = [
    ('real_place_film_nofocus', 'blender/tests/terrain/out/surfacing_judge/terrains/real_place'),
    ('lauterbrunnen_film', 'blender/tests/terrain/out/surface_data/snap/lauterbrunnen'),
]


def blender_edition():
    for root in (REPO, os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return os.path.normpath(root)
    sys.exit('api_expected.py: no Blender edition: set EIDO_BLENDER_EDITION to the root of a checkout of the '
             'blender branch')


BLE = blender_edition()
sys.path.insert(0, os.path.join(BLE, 'blender'))
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.core.fields import Fields  # noqa: E402


SOURCES = ['blender/eidoblend/terrain/api.py', 'blender/eidoblend/terrain/build/mesh.py',
           'blender/eidoblend/terrain/core/levels.py', 'blender/eidoblend/terrain/core/grid.py']


def source_state():
    """The Blender checkout's commit and whether the sources these fixtures run differ from the recorded commit."""
    import subprocess

    def git(*a):
        try:
            return subprocess.run(['git', '-C', BLE, *a], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return None
    return dict(head=git('rev-parse', '--short', 'HEAD'), recorded=RECORDED_COMMIT,
                changed_since_recorded={s: bool(git('diff', '--stat', RECORDED_COMMIT, '--', s)) for s in SOURCES})


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            h.update(block)
    return h.hexdigest()


class Dump:
    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.arrays = {}

    def put(self, name, a, dtype):
        a = np.ascontiguousarray(np.asarray(a, dtype))
        fn = name + '.bin'
        a.tofile(os.path.join(self.folder, fn))
        self.arrays[name] = dict(file=fn, dtype={np.float32: 'f32', np.float64: 'f64', np.int32: 'i32',
                                                  np.uint32: 'u32'}[dtype], shape=list(a.shape))


def level_specs(t):
    out = {}
    for spec in ('main', 'context', 'hero', 'first', 'last', 0, 1, -1, len(t.levels) - 1, len(t.levels) + 1):
        try:
            out[str(spec)] = A._level_index(t.levels, spec)
        except KeyError as e:
            out[str(spec)] = dict(error=str(e.args[0]))
    return out


def mask_points(t, rng, n=300):
    """n points: a third in the finest level, a third on the main tile, a third on the whole terrain (the context)."""
    k = n // 3
    wins = [t.levels[-1], t.main, t.levels[0]]
    xs, ys = [], []
    for w in wins:
        xs.append(rng.uniform(w.x0, w.x1, k))
        ys.append(rng.uniform(w.y0, w.y1, k))
    return np.concatenate(xs), np.concatenate(ys)


def viewpoints(t, focus):
    """[(args, the Viewpoint as a dict or the error's text)] for a spread of targets and options."""
    lv = t.main
    cx, cy = lv.x0 + 0.5 * lv.side, lv.y0 + 0.5 * lv.side
    fx, fy = focus if focus is not None else (cx, cy)
    cases = [
        dict(target=(fx, fy), distance=0.15 * lv.side),
        dict(target=(fx, fy), distance=0.15 * lv.side, prefer='low'),
        dict(target=(fx, fy), distance=0.15 * lv.side, prefer='high', heading=200.0),
        dict(target=(cx - 0.21 * lv.side, cy + 0.17 * lv.side), distance=0.1 * lv.side, heading=45.0, eye_height=12.0),
        dict(target=(cx + 0.3 * lv.side, cy - 0.33 * lv.side), distance=0.05 * lv.side, look_dz=40.0, clearance_m=3.0),
        dict(target=(cx + 0.11 * lv.side, cy + 0.07 * lv.side, 5000.0), distance=0.2 * lv.side, max_slope_deg=20.0),
        dict(target=(cx, cy), distance=0.3 * lv.side, within='context', lens_mm=50.0),
        dict(target=(cx, cy), distance=3.0 * lv.side),                      # no candidate inside the level
        dict(target=(fx, fy), distance=0.02 * lv.side, clearance_m=4000.0),  # nothing sees it
    ]
    out = []
    for c in cases:
        kw = {k: v for k, v in c.items() if k not in ('target', 'distance')}
        try:
            vp = t.viewpoint(c['target'], c['distance'], **kw)
            res = dict(vp._asdict())
        except (ValueError, KeyError) as e:
            res = dict(error=str(e.args[0]))
        out.append(dict(args=c, result=res))
    return out


def flatten_case(t, d, focus):
    """api.flatten_fields on copies of the terrain's h and bed. The areas (Blender frame): a disc around the focus
    (or the main tile's centre) whose height is the median under it, a rotated rectangle, an area smaller than a
    cell of the finest level that holds it, and a disc of a given height near the main tile's corner."""
    lv = t.main
    cx, cy = lv.x0 + 0.5 * lv.side, lv.y0 + 0.5 * lv.side
    fx, fy = focus if focus is not None else (cx + 0.06 * lv.side, cy + 0.205 * lv.side)
    fin = t.levels[-1]
    specs = [
        {'at': (fx, fy), 'radius': 15.0 * fin.cell, 'falloff': 5.0 * fin.cell},
        {'at': (cx - 0.1125 * lv.side, cy - 0.3125 * lv.side), 'size': (0.0375 * lv.side, 0.025 * lv.side),
         'angle_deg': 30.0, 'falloff': 0.00375 * lv.side, 'height': None},
        {'at': (cx + 0.2 * lv.side + 0.013, cy + 0.1 * lv.side - 0.021), 'radius': 0.3 * lv.cell,
         'falloff': 2.5 * lv.cell},
        {'at': (lv.x0 + 0.02 * lv.side, lv.y0 + 0.03 * lv.side), 'radius': 0.03 * lv.side, 'falloff': 0.02 * lv.side,
         'height': 1234.5},
    ]
    fields = []
    for i, lvl in enumerate(t.levels):
        f = t.fields(i)
        fields.append(Fields(lvl, {k: np.array(f[k], np.float32) for k in ('h', 'bed') if k in f}))
    before = [{k: v.copy() for k, v in f.items()} for f in fields]
    flats = A.flatten_fields(fields, t.levels, A._check_flatten(specs))
    changed = []
    for i, (f, b) in enumerate(zip(fields, before)):
        ch = {k: bool(not np.array_equal(f[k].view(np.uint32), b[k].view(np.uint32))) for k in f}
        if any(ch.values()):
            changed.append(i)
            for k in f:
                d.put(f'flat_{k}_{i}', f[k], np.float32)
    return dict(specs=json.loads(json.dumps(specs)), flats=json.loads(json.dumps(A._plain(flats))), changed_levels=changed)


def plants_case(t, out_base, focus):
    """plan_plants on the terrain (masks alone), saved by PlantSpots.save: (the record, or why not)."""
    try:
        from eidoblend.terrain.build import plants as PL
    except Exception as e:                                   # the Blender checkout predates the plant layer
        return dict(skipped=f'{type(e).__name__}: {e}')
    try:
        spots = PL.plan_plants(t, focus=focus, radius_m=45.0, seed=3, log=None)
        files = spots.save(out_base)
    except Exception as e:
        return dict(skipped=f'plan_plants: {type(e).__name__}: {e}')
    return dict(format=PL.FORMAT, fields=list(PL.FIELDS), species={n: spots.count(n) for n in spots.names()},
                files=[os.path.basename(p) for p in files], sha1={os.path.basename(p): sha1(p) for p in files[1:]},
                seconds=spots.seconds)


def run_save(label, base, out, base_man):
    t0 = time.perf_counter()
    t = A.Terrain.load(base, build=False)
    d = Dump(os.path.join(out, label))
    rel = os.path.relpath(base, BLE).replace('\\', '/')
    man = dict(base_man, case=label, save=rel, recipe=t.recipe.name, seconds_load=round(time.perf_counter() - t0, 2),
               levels=len(t.levels), triangles=int(t.ring.triangle_count))
    rng = np.random.default_rng(5)
    focus = tuple(t.info['focus'][0]) if t.info.get('focus') else None
    man['level_index'] = level_specs(t)
    man['mask_names'] = t.masks.names()
    x, y = mask_points(t, rng)
    d.put('mask_x', x, np.float64)
    d.put('mask_y', y, np.float64)
    man['masks_at'] = []
    for name in ('slope', 'flow', 'height', 'vegetation', 'curv_plan'):
        if name in t.masks:
            d.put(f'mask_at_{name}', t.mask(name).at(x, y), np.float64)
            man['masks_at'].append(name)
    man['mask_at_scalar'] = dict(x=float(x[0]), y=float(y[0]), slope=float(t.mask('slope').at(float(x[0]), float(y[0]))))
    man['viewpoints'] = json.loads(json.dumps(viewpoints(t, focus)))
    man['flatten'] = flatten_case(t, d, focus)
    with tempfile.TemporaryDirectory() as tmp:
        p = t.save(os.path.join(tmp, 'resaved'))
        with open(os.path.join(tmp, 'resaved.json'), encoding='utf-8') as f:
            resaved = json.load(f)
        man['resave'] = dict(resaved_npz_sha1=sha1(p), original_npz_sha1=sha1(base + '.npz'),
                             bytes=os.path.getsize(p), resaved_json=resaved)
    man['plants'] = plants_case(t, os.path.join(d.folder, 'spots'), focus)
    man['arrays'] = d.arrays
    with open(os.path.join(d.folder, 'manifest.json'), 'w') as f:
        json.dump(man, f, indent=1)
    print(f'[api_expected] {label}: {len(t.levels)} levels; viewpoints '
          f'{sum("error" not in v["result"] for v in man["viewpoints"])} found / {len(man["viewpoints"])}; flatten '
          f'changed levels {man["flatten"]["changed_levels"]}; save byte-identical '
          f'{man["resave"]["resaved_npz_sha1"] == man["resave"]["original_npz_sha1"]}; plants {man["plants"]}', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--cases')
    ap.add_argument('--save', action='append', default=[], help='NAME=PATH of a Blender Terrain.save (no extension)')
    a = ap.parse_args()
    want = set(a.cases.split(',')) if a.cases else None
    base_man = dict(python=platform.python_version(), numpy=np.__version__, zlib=zlib.ZLIB_VERSION,
                    source=source_state(), made=time.strftime('%Y-%m-%d %H:%M:%S'))
    os.makedirs(a.out, exist_ok=True)
    saves = dict((n, os.path.join(BLE, p)) for n, p in DEFAULT_SAVES)
    for s in a.save:
        n, _, p = s.partition('=')
        saves[n] = os.path.splitext(p)[0] if p.endswith('.npz') or p.endswith('.json') else p
    for label, base in saves.items():
        if want is not None and label not in want:
            continue
        if not (os.path.isfile(base + '.npz') and os.path.isfile(base + '.json')):
            print(f'[api_expected] SKIP {label}: no save at {base}.npz; make one with\n    bash run_blender.sh '
                  'blender/eidoblend/terrain/bake.py --recipe real_place --param dem=lauterbrunnen --seed 1 --quality '
                  'film --save --out <dir>\nand pass --save NAME=<dir>/<name>', flush=True)
            continue
        run_save(label, base, a.out, base_man)


if __name__ == '__main__':
    main()
