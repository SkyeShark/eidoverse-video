"""Plain heightmaps (export.export_heightmap) against Ekigar's own heightmap.js: every format (png16, r32, r16,
raw), flipped and not, an explicit range (with clipping), an explicit metres range, a non-square field. The files
decode to the same samples and the sidecar carries the same values; the two sidecar strings that name Ekigar's
JavaScript (generator, the flipY note) say the Blender edition's own.

    python blender/tests/terrain_ekigar/test_heightmap_parity.py
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
OUT = os.path.join(_ekigar_load.OUT, 'heightmap')
os.makedirs(OUT, exist_ok=True)
hf = ek.generate('mountainRange', resolution=40, world_size=1200)
h = hf.height
cases = [
    dict(name='all_formats', data=h, formats=['png16', 'r32', 'r16', 'raw'], worldSize=1200, verticalScale=0.3),
    dict(name='flipped', data=h, formats=['png16', 'r16'], worldSize=1200, verticalScale=0.3, flipY=True),
    dict(name='pinned_range', data=h, formats=['png16', 'r32'], worldSize=1200, verticalScale=0.3,
         range=[float(h.min()) + 0.02, float(h.max()) - 0.01]),
    dict(name='metres_given', data=h, formats=['r32'], worldSize=1200, verticalScale=0.3, heightRangeMetres=321.5),
    dict(name='non_square', data=h[:24, :], formats=['png16', 'r32'], worldSize=800, verticalScale=0.25),
]
spec = []
for c in cases:
    d = np.asarray(c['data'])
    spec.append(dict({k: v for k, v in c.items() if k != 'data'}, data=d.ravel().tolist(), width=d.shape[1],
                     height=d.shape[0]))
src = os.path.join(OUT, 'heightmap_cases.json')
json.dump(spec, open(src, 'w'))
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', os.path.join(HERE, 'heightmap_dump.mjs'), src,
                    OUT, _ekigar_load.EKIGAR_ROOT], capture_output=True, text=True, timeout=600)
if r.returncode != 0:
    print('FAIL heightmap dump:', r.stderr[-1500:])
    sys.exit(1)
OWN = {'generator', 'rowOrderNote'}
ok_all = True
for c, s in zip(cases, spec):
    jsdir = os.path.join(OUT, c['name'])
    with tempfile.TemporaryDirectory() as td:
        side = ek.export_heightmap(np.asarray(c['data']), td, formats=tuple(c['formats']), world_size=c['worldSize'],
                                   vertical_scale=c['verticalScale'], height_range_metres=c.get('heightRangeMetres'),
                                   range_=c.get('range'), flip_y=c.get('flipY', False), name=c['name'])
        worst = 0.0
        files_ok = True
        for f in sorted(os.listdir(jsdir)):
            if f.endswith('.json'):
                continue
            pb = open(os.path.join(td, f), 'rb').read()
            jb = open(os.path.join(jsdir, f), 'rb').read()
            if f.endswith('.png'):
                pa, ja = ek.decode_png16_gray(pb), ek.decode_png16_gray(jb)
                a, b = np.asarray(pa['data']).ravel(), np.asarray(ja['data']).ravel()
                files_ok &= pa['width'] == ja['width'] and pa['height'] == ja['height']
            else:
                files_ok &= pb == jb                     # raw formats: byte for byte
                dec = ek.decode_r32 if f.endswith('.r32') else ek.decode_r16
                a, b = dec(pb), dec(jb)
            worst = max(worst, float(np.abs(a - b).max()) if a.size == b.size else float('inf'))
        js_side = json.load(open(os.path.join(jsdir, f'{c["name"]}.json'), encoding='utf-8'))
        py_side = json.loads(json.dumps(side))
        diffs = [k for k in js_side if k not in OWN and py_side.get(k) != js_side[k]
                 and not (isinstance(js_side[k], dict) and all(
                     abs(py_side[k][q] - js_side[k][q]) < 1e-12 * max(1, abs(js_side[k][q]))
                     if isinstance(js_side[k][q], float) else py_side[k][q] == js_side[k][q] for q in js_side[k]))]
    ok = files_ok and worst == 0 and not diffs
    ok_all &= ok
    print(f'{"PASS" if ok else "FAIL"} heightmap {c["name"]:14s} {", ".join(c["formats"])}: samples max diff {worst:g}'
          + (f'; sidecar differs in {diffs}' if diffs else '; sidecar same'))
print('heightmap:', 'matches Ekigar' if ok_all else 'MISMATCH')
sys.exit(0 if ok_all else 1)
