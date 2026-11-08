"""The map set (export.export_maps) against Ekigar's own bake.js, run under deno with its browser pieces stood in
(bake_dump.mjs): the 16-bit height, the normal, slope and ridge PNGs decode to the same pixels and terrain.json
carries the same values, on a periodic and an open tile.

    python blender/tests/terrain_ekigar/test_bake_parity.py
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

import _ekigar_load

ek = _ekigar_load.load()
HERE = _ekigar_load.HERE
OUT = os.path.join(_ekigar_load.OUT, 'bake')
os.makedirs(OUT, exist_ok=True)
cases = []
for name, op, tile, ws, vs in (('volcano_periodic', 'volcano', {'x': 1, 'y': 1}, 400, 0.3),
                               ('canyon_open', 'canyon', {'x': 0, 'y': 0}, 2000, 0.25),
                               ('erosion_x_only', 'mountainRange', {'x': 1, 'y': 0}, 1000, 0.3)):
    hf = ek.generate(op, resolution=48, world_size=ws, tile=(tile['x'], tile['y']))
    # the browser reads the field target back as float32: the port gets those same values
    h = hf.height.astype(np.float32).astype(np.float64)
    a = hf.aux.astype(np.float32).astype(np.float64)
    cases.append({'name': name, 'size': 48, 'tile': tile, 'worldSize': ws, 'verticalScale': vs,
                  'height': h.ravel().tolist(), 'aux': a.ravel().tolist()})
src = os.path.join(OUT, 'bake_cases.json')
json.dump(cases, open(src, 'w'))
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(HERE, 'bake_dump.mjs'), src, OUT,
                    _ekigar_load.EKIGAR_ROOT], capture_output=True, text=True, timeout=600)
if r.returncode != 0:
    print('FAIL bake dump:', r.stderr[-1500:])
    sys.exit(1)
ok_all = True
for c in cases:
    jsdir = os.path.join(OUT, c['name'])
    N = c['size']
    with tempfile.TemporaryDirectory() as td:
        side = ek.export_maps(np.asarray(c['height']).reshape(N, N), np.asarray(c['aux']).reshape(N, N), td,
                              world_size=c['worldSize'], vertical_scale=c['verticalScale'],
                              tile=(c['tile']['x'], c['tile']['y']))
        rows = []
        same_bytes = 0
        for f in ('ekigar_height16.png', 'ekigar_normal.png', 'ekigar_slope.png', 'ekigar_ridge.png'):
            pb = open(os.path.join(td, f), 'rb').read()
            jb = open(os.path.join(jsdir, f), 'rb').read()
            same_bytes += pb == jb
            dec = ek.decode_png16_gray if f.endswith('16.png') else ek.decode_png
            pa, ja = dec(pb), dec(jb)
            d = np.abs(np.asarray(pa['data'], dtype=np.float64) - np.asarray(ja['data'], dtype=np.float64))
            rows.append((f, float(d.max()), pa['width'] == ja['width']))
        js_side = json.load(open(os.path.join(jsdir, 'terrain.json'), encoding='utf-8'))
        py_side = json.loads(json.dumps(side, default=str))
        side_ok = all(abs(py_side[k] - js_side[k]) < 1e-9 * max(1, abs(js_side[k])) if isinstance(js_side[k], float)
                      else py_side[k] == js_side[k] for k in js_side if k not in ('stack', 'materialLayers'))
    ok = all(mx == 0 and w for _f, mx, w in rows) and side_ok
    ok_all &= ok
    print(f'{"PASS" if ok else "FAIL"} bake {c["name"]:18s} pixels ' + ', '.join(f'{f[7:-4]} {mx:g}' for f, mx, _w in rows)
          + f'; sidecar {"same" if side_ok else "DIFFERS"}; {same_bytes}/4 files byte-identical')
# ops.js's sRGB helpers: SRGB_TO_LINEAR (the EOTF table every 8-bit sRGB read decodes through) and linearToSRGB
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(HERE, 'srgb_dump.mjs'),
                    _ekigar_load.EKIGAR_ROOT], capture_output=True, text=True, timeout=300)
js = json.loads(r.stdout)
d_tab = float(np.abs(np.asarray(js['table']) - ek.SRGB_TO_LINEAR).max())
d_eotf = float(np.abs(ek.srgb_to_linear(np.arange(256) / 255.0) - ek.SRGB_TO_LINEAR).max())
d_oetf = float(np.abs(np.asarray(js['oetf']) - ek.linear_to_srgb(np.asarray(js['xs']))).max())
ok = d_tab < 1e-15 and d_eotf < 1e-15 and d_oetf < 1e-15
ok_all &= ok
print(f'{"PASS" if ok else "FAIL"} ops.js SRGB_TO_LINEAR table and linearToSRGB: table {d_tab:.1e}, '
      f'srgb_to_linear vs table {d_eotf:.1e}, linear_to_srgb {d_oetf:.1e}')
print('bake:', 'the map set matches Ekigar' if ok_all else 'MISMATCH')
sys.exit(0 if ok_all else 1)
