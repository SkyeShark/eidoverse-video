"""The circular local area (local_area.py) against Ekigar's own local_area.js and mixed.js, case by case: the cut
resolved in metres and in fractions (and both, conflicting), a non-square field and world, fade wider than the
radius, a negative and a sub-texel fade, a circle swallowing the tile, a circle off a non-periodic edge (clipped) and
off a periodic one (wrapped, crop origin negative), plus the weight field, the crop, the seam ring, point reads,
area downsampling at whole and fractional ratios, splitField, the local masks and the driver resolution.

    python blender/tests/terrain_ekigar/test_local_area_parity.py
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

import _ekigar_load

ek = _ekigar_load.load()
import importlib  # noqa: E402
la = importlib.import_module(ek.__name__ + '.local_area')
HERE = _ekigar_load.HERE
OUT = _ekigar_load.OUT
os.makedirs(OUT, exist_ok=True)


def make_field(w, h, seed=0):
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    d = (0.5 + 0.2 * np.sin(x * 0.37 + seed) * np.cos(y * 0.23 - seed) + 0.05 * np.sin(x * 1.9 + y * 1.3)
         + 0.03 * np.cos(x * 0.11 * (seed + 1)))
    aux = 0.5 + 0.4 * np.sin(x * 0.5 + y * 0.7)
    return {'data': d.ravel().tolist(), 'width': w, 'height': h, 'aux': aux.ravel().tolist()}


MASKS = ['height', 'slope', 'aspect', 'aspectEast', 'curvProfile', 'curvPlan', 'curvMean', 'ridge']
P = [[0, 0], [12.5, 380.25], [399.9, 0.1], [200, 200], [-15, 410], [123.4, 77.7]]
T = [[0, 0], [5, 7], [-3, 2], [40, 70], [63, 63]]
D = [[16, 16], [10, 7], [64, 64], [37, 23]]
cases = [
    dict(name='fractions_open', geometry={'size': 64, 'worldSize': 400}, cut={'cx': 0.5, 'cy': 0.5, 'radius': 0.28,
                                                                              'fade': 0.07}),
    dict(name='metres', geometry={'size': 64, 'worldSize': 400, 'tile': {'x': 1, 'y': 1}},
         cut={'centreMetres': [120, 260], 'radiusMetres': 90, 'fadeMetres': 25}),
    dict(name='conflict', geometry={'size': 64, 'worldSize': 400},
         cut={'centreMetres': [200, 200], 'cx': 0.25, 'radiusMetres': 100, 'radius': 0.1, 'fade': 0.05}),
    dict(name='non_square', geometry={'width': 64, 'height': 48, 'worldSize': {'x': 400, 'y': 300}},
         cut={'cx': 0.4, 'cy': 0.6, 'radius': 0.2}),
    dict(name='fade_over_radius', geometry={'size': 64, 'worldSize': 400}, cut={'radiusMetres': 40, 'fadeMetres': 70}),
    dict(name='negative_fade', geometry={'size': 64, 'worldSize': 400}, cut={'radiusMetres': 60, 'fadeMetres': -5}),
    dict(name='subtexel_fade', geometry={'size': 64, 'worldSize': 400}, cut={'radiusMetres': 60, 'fadeMetres': 2}),
    dict(name='swallows', geometry={'size': 64, 'worldSize': 400}, cut={'radiusMetres': 400}),
    dict(name='clipped_open_edge', geometry={'size': 64, 'worldSize': 400},
         cut={'centreMetres': [30, 380], 'radiusMetres': 80, 'fadeMetres': 20}),
    dict(name='wrapped_periodic_edge', geometry={'size': 64, 'worldSize': 400, 'tile': {'x': 1, 'y': 1}},
         cut={'centreMetres': [30, 380], 'radiusMetres': 80, 'fadeMetres': 20}),
    dict(name='x_only_periodic', geometry={'width': 64, 'height': 64, 'worldSize': 400, 'tile': {'x': 1, 'y': 0}},
         cut={'centreMetres': [10, 10], 'radiusMetres': 70}),
    dict(name='defaults', geometry={'size': 64, 'worldSize': 1000}, cut={}),
]
for k, c in enumerate(cases):
    g = c['geometry']
    c['field'] = make_field(g.get('width', g.get('size')), g.get('height', g.get('size')), seed=k)
    c['points'] = P
    c['texels'] = T
    c['down'] = D
    c['masks'] = MASKS
src = os.path.join(OUT, 'local_area_cases.json')
dst = os.path.join(OUT, 'local_area_js.json')
json.dump(cases, open(src, 'w'))
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A',
                    f'--import-map={os.path.join(HERE, "import_map.json")}', os.path.join(HERE, 'local_area_dump.mjs'),
                    src, dst, _ekigar_load.EKIGAR_ROOT], capture_output=True, text=True, timeout=300)
if r.returncode != 0:
    print('FAIL local area dump:', r.stderr[-2000:])
    sys.exit(1)
js = json.load(open(dst, encoding='utf-8'))
fails = []


def same(a, b, path, tol=1e-9, u8=False):
    """Recursive comparison: numbers to a relative tolerance, uint8 masks within one step, everything else exact."""
    if isinstance(b, dict):
        if not isinstance(a, dict):
            fails.append(f'{path}: py {type(a).__name__} vs js dict')
            return
        for k in b:
            if k not in a:
                fails.append(f'{path}.{k}: missing in py')
                continue
            same(a[k], b[k], f'{path}.{k}', tol, u8 or k in ('mask',) or path.endswith('masks'))
        for k in a:
            if k not in b:
                fails.append(f'{path}.{k}: extra in py')
        return
    if isinstance(b, list):
        a = list(a) if isinstance(a, (list, tuple, np.ndarray)) else a
        if not isinstance(a, list) or len(a) != len(b):
            fails.append(f'{path}: length {len(a) if isinstance(a, list) else a} vs {len(b)}')
            return
        if b and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in b):
            A = np.asarray(a, dtype=np.float64)
            B = np.asarray(b, dtype=np.float64)
            d = np.abs(A - B)
            if u8:
                if d.max() > 1 or (d > 0).mean() > 0.002:
                    fails.append(f'{path}: uint8 differs at {(d > 0).sum()} of {d.size} (max {d.max()})')
            elif not np.all(d <= tol * np.maximum(1.0, np.abs(B))):
                fails.append(f'{path}: max diff {d.max():.3e}')
            return
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f'{path}[{i}]', tol, u8)
        return
    if isinstance(b, bool) or b is None or isinstance(b, str):
        if a != b and not (isinstance(a, (np.bool_,)) and bool(a) == b):
            fails.append(f'{path}: py {a!r} vs js {b!r}')
        return
    if isinstance(b, (int, float)):
        if not isinstance(a, (int, float, np.floating, np.integer)) or isinstance(a, bool):
            fails.append(f'{path}: py {a!r} vs js {b!r}')
        elif abs(float(a) - b) > tol * max(1.0, abs(b)):
            fails.append(f'{path}: py {a!r} vs js {b!r}')
        return
    fails.append(f'{path}: unhandled {type(b)}')


def as_plain(v):
    if isinstance(v, dict):
        return {k: as_plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [as_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


ok_cases = 0
for c, want in zip(cases, js['cases']):
    n0 = len(fails)
    field = {'data': c['field']['data'], 'width': c['field']['width'], 'height': c['field']['height'],
             'aux': c['field']['aux']}
    got = {'name': c['name']}
    try:
        G = la.resolve_geometry(c['geometry'])
        got['geometry'] = G
        rc = la.resolve_cut(c['cut'], G)
        got['cut'] = rc
        wf = la.weight_field(rc)
        got['weight'] = {k: wf[k] for k in ('data', 'coverage', 'coreCoverage', 'annulusCoverage', 'surroundCoverage')}
        wf2 = la.weight_field(rc, width=17, height=13)
        got['weightSmall'] = {'data': wf2['data'], 'coverage': wf2['coverage']}
        got['crop'] = la.crop_local(field, rc)
        got['seam'] = la.seam_ring(field, rc, 48)
        got['samples'] = [[la.sample_field_metres(field, G, x, y), la.sample_field_nearest_metres(field, G, x, y),
                           la.weight_at_metres(rc, x, y)] for x, y in c['points']]
        got['texelWeights'] = [la.weight_at_texel(rc, i, j) for i, j in c['texels']]
        got['down'] = [la.area_downsample(field, w, h)['data'] for w, h in c['down']]
        sp = la.split_field({'data': field['data'], 'width': field['width'], 'height': field['height']}, c['cut'],
                            world_size=c['geometry']['worldSize'], tile=c['geometry'].get('tile'), seam_samples=32)
        got['split'] = {k: sp[k] for k in ('weight', 'local', 'localMask', 'coverage', 'coreCoverage',
                                           'annulusCoverage', 'surroundCoverage', 'seam', 'warnings')}
        got['masks'] = la.rasterise_local_masks(field, rc, c['masks'], vertical_scale=0.3)
        fd = np.asarray(field['data'])
        got['driver'] = {'number': la.resolve_driver_field(0.25, field)['data'],
                         'implicit': la.resolve_driver_field(None, field)['data'],
                         'array': la.resolve_driver_field(fd * 2, field)['data']}
    except Exception as ex:  # noqa: BLE001
        got = {'name': c['name'], 'error': str(ex)}
    same(as_plain(got), want, c['name'])
    if len(fails) == n0:
        ok_cases += 1
        print(f'PASS local area {c["name"]:24s} warnings: {len(want.get("cut", {}).get("warnings", []))}')
    else:
        print(f'FAIL local area {c["name"]}')
        for f in fails[n0:n0 + 8]:
            print('     ', f)
lw = [[], [{'maskStack': [{'type': 'terrain', 'params': {'source': 'curvPlan'}}, {'type': 'noise'}]}],
      [{'legacy': {'maskStack': [{'type': 'terrain'}, {'type': 'terrain', 'enabled': False, 'params': {'source': 'x'}}]}},
       {'maskStack': [{'type': 'terrain', 'params': {'source': 'aspect'}}]}]]
n0 = len(fails)
same([la.masks_used_by(x) for x in lw], js['usedBy'], 'masksUsedBy')
sc = {'localWeight': [la.local_weight(dx, dy, r_, f_) for dx, dy, r_, f_ in
                      [[0, 0, 10, 2], [8.5, 0, 10, 2], [9, 0, 10, 2], [10, 0, 10, 2], [3, 4, 5, 0], [6, 8, 10, 0]]],
      'wrapDelta': [la.wrap_delta(d, p) for d, p in [[350, 400], [-350, 400], [199, 400], [201, 400], [-201, 400],
                                                      [5, 0], [1234.5, 400]]]}
same(as_plain(sc), js['scalars'], 'scalars', tol=1e-15)
print(('PASS' if len(fails) == n0 else 'FAIL') + ' masksUsedBy, localWeight, wrapDelta')
for f in fails[n0:]:
    print('     ', f)
total = len(cases) + 1
good = ok_cases + (len(fails) == n0)
print(f'local area: {good}/{total} match Ekigar')
sys.exit(0 if not fails else 1)
