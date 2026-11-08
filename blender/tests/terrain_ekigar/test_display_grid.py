"""The display grid (display_grid.py) against Ekigar's own terrain_mesh.js, plus the properties terrain_mesh.js
measured for its bilinear field read, checked on the port:

- terrainVertexSide / terrainGeometryCost / buildTerrainGeometry: identical numbers and arrays (positions, uv on
  texel centres, the +z winding, u16 indices up to 65536 vertices, the optional normal);
- fieldHeightBilinear: exact at 1:1 (every vertex reads its own texel), an exact two-tap box average at a whole 2:1
  ratio, wrapping at the far edge, and attenuating a sinusoid by the predicted cos(pi f / R) where a nearest read
  passes it through as an alias;
- Heightfield.height_at(x, y, side=N) reads the display grid build_mesh(side=N) makes.

    python blender/tests/terrain_ekigar/test_display_grid.py
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

import _ekigar_load

ek = _ekigar_load.load()
HERE = _ekigar_load.HERE
OUT = _ekigar_load.OUT
os.makedirs(OUT, exist_ok=True)
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(f'{"PASS" if ok else "FAIL"} {name}{(": " + detail) if detail else ""}')


dst = os.path.join(OUT, 'mesh_js.json')
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A',
                    f'--import-map={os.path.join(HERE, "import_map_mesh.json")}', os.path.join(HERE, 'mesh_dump.mjs'),
                    dst, _ekigar_load.EKIGAR_ROOT], capture_output=True, text=True, timeout=300)
if r.returncode != 0:
    print('FAIL terrain_mesh.js dump:', r.stderr[-1500:])
    sys.exit(1)
js = json.load(open(dst, encoding='utf-8'))
check('VERT_CAP and VERT_FLOOR', js['VERT_CAP'] == ek.VERT_CAP and js['VERT_FLOOR'] == ek.VERT_FLOOR)
sides = [0, None, 1, 100.7, 255, 256, 300, 1024, 2048, 2049, 4096, 8192]
check('terrain_vertex_side matches for every resolution', [ek.terrain_vertex_side(s) for s in sides] == js['side'],
      str([ek.terrain_vertex_side(s) for s in sides]))
check('terrain_vertex_side with a cap', [ek.terrain_vertex_side(s, 512) for s in sides] == js['sideCapped'])
check('terrain_geometry_cost matches', [ek.terrain_geometry_cost(n) for n in [2, 3, 255, 256, 257, 1024, 2048, 4096]]
      == js['cost'])
ok_geo = True
for want in js['geometry']:
    o = want['opts']
    g = ek.build_terrain_geometry(want['res'], cap=o.get('cap', ek.VERT_CAP), side=o.get('side'),
                                  with_normal=o.get('withNormal', False))
    t = g['terrain']
    same = (t == want['terrain']
            and np.array_equal(g['position'].ravel()[:120].astype(np.float32), np.float32(want['position']))
            and np.array_equal(g['position'].ravel()[-6:], np.float32(want['positionLast']))
            and np.array_equal(g['uv'].ravel()[:80], np.float32(want['uv']))
            and np.array_equal(g['uv'].ravel()[-4:], np.float32(want['uvLast']))
            and g['index'].ravel()[:60].tolist() == want['index'] and g['index'][-12:].tolist() == want['indexLast']
            and g['index'].size == want['indexCount']
            and {'Uint16Array': np.uint16, 'Uint32Array': np.uint32}[want['indexKind']] == g['index'].dtype
            and ((want['normal'] is None) == ('normal' not in g))
            and (want['normal'] is None or np.array_equal(g['normal'].ravel()[:9], np.float32(want['normal']))))
    ok_geo &= same
    if not same:
        print(f'     geometry res {want["res"]} {o}: differs (side {t["side"]} vs {want["side"]})')
check('build_terrain_geometry: positions, uv, winding, index width and normal match', ok_geo)

# fieldHeightBilinear's measured properties
rng = np.random.default_rng(7)
f = rng.random((64, 64))
check('bilinear at 1:1 reads every texel exactly', np.array_equal(ek.display_heights(f, 64), f))
d2 = ek.display_heights(f, 32)
box = 0.25 * (f[0::2, 0::2] + f[1::2, 0::2] + f[0::2, 1::2] + f[1::2, 1::2])
check('bilinear at 2:1 is the exact two-tap box average', np.max(np.abs(d2 - box)) < 1e-12,
      f'max {np.max(np.abs(d2 - box)):.1e}')
u = np.array([1.0 - 0.25 / 64])                        # a quarter texel past the last texel centre, toward u = 1
wrapped = ek.field_height_bilinear(f, u, np.array([0.5 / 64]))[0]
check('bilinear wraps at the far edge (the field target repeats)',
      abs(wrapped - (0.75 * f[0, 63] + 0.25 * f[0, 0])) < 1e-12)
R = 256
for cyc in (40, 96):
    x = (np.arange(R) + 0.5) / R
    sig = np.tile(np.sin(2 * math.pi * cyc * x), (R, 1))
    down = ek.display_heights(sig, R // 2)
    amp = np.sqrt(2 * np.mean(down ** 2))
    pred = abs(math.cos(math.pi * cyc / R))
    check(f'a {cyc}-cycle sinusoid read 2:1 is attenuated by cos(pi f / R)', abs(amp - pred) < 0.01,
          f'{amp:.4f} vs predicted {pred:.4f} (nearest would keep 1.0)')

# height_at on display grids
hf = ek.generate('mountainRange', params={'style': 'eroded'}, resolution=128, world_size=1000)
for side in (128, 64, 50, 256):
    xs, ys = hf.grid_xy(side=side)
    z = hf.display_z(side)
    at = hf.height_at(xs.ravel(), ys.ravel(), side=side).reshape(z.shape)
    check(f'height_at(side={side}) equals the display grid at its vertices', np.max(np.abs(at - z)) < 1e-9)
xs, ys = hf.grid_xy(side=64)
mid_x = 0.5 * (xs[10, 20] + xs[10, 21])
want = 0.5 * (hf.display_z(64)[10, 20] + hf.display_z(64)[10, 21])
check('height_at(side=64) is linear along a display-grid edge', abs(hf.height_at(mid_x, ys[10, 20], side=64) - want)
      < 1e-9)
w = hf.world_size
nxh, nyh = hf.resolution
j = nyh // 2
yc = (j + 0.5) / nyh * w - w / 2                     # on a texel row: the quad's bottom edge, linear along x
xq = w / 2 - 0.25 * w / nxh                          # a quarter texel inside the east edge, past the last centre
f = 0.25                                             # of the way from the last texel to the next copy's first
want = hf.heights_m[j, -1] * (1 - f) + hf.heights_m[j, 0] * f
got = hf.height_at(np.array([xq]), np.array([yc]), wrap=True)[0]
clamped = hf.height_at(np.array([xq]), np.array([yc]))[0]
check('height_at(wrap=True) crosses the periodic edge into the next copy', abs(got - want) < 1e-9
      and abs(clamped - hf.heights_m[j, -1]) < 1e-9, f'{got:.4f} m vs {want:.4f} m (clamped {clamped:.4f} m)')
print(f'display grid: {sum(results)}/{len(results)} pass')
sys.exit(0 if all(results) else 1)
