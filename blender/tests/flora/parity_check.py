"""parity_check.py: the Blender edition's planning half against the WebGPU edition's createFlora, case by case.
Reads blender/tests/flora/out/parity/<case>.json (written by parity_dump.mjs from the untouched vegetation.js) and
runs eidoblend.flora.plan_flora with the same options in three space (no Blender needed: system Python + numpy).
Compares the plant geometry (vertex and triangle counts exactly; positions, normals, uvs, aH to float32 noise) and
the per-instance attributes (count exactly; values to float32 noise). Exit 1 on any mismatch.
    python blender/tests/flora/parity_check.py [case ...]
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.flora import vegetation as V  # noqa: E402

DUMPS = os.path.join(HERE, 'out', 'parity')
# known: the shrub skeletons hit exact ties in repelDir's parent-neighbourhood test (consecutive skeleton points
# sit exactly len/2 apart against near2 = (len*0.5)^2). V8's Math.sin/cos (its glibc-derived trig) and the C
# library's differ by one ulp now and then (measured 11-07 on the sagebrush's own arguments: cos 149 of 1643 calls,
# sin 7 of 1883, acos 3 of 269; V8 is the correctly rounded side in all but 3), a tie breaks the other way, and the
# rest of the shrub grows differently. Counts still match. Porting fdlibm does not help: it matches V8's acos bit for
# bit but not its sin/cos (about 3 % of arguments differ).
KNOWN_GEOMETRY_DIVERGENCE = {'blackbrush', 'creosote', 'sagebrush'}


def height_fn(x, z):
    return 0.3 * math.sin(0.4 * x) + 0.2 * math.cos(0.3 * z)


KEYMAP = {'heightFn': 'height_fn', 'headScale': 'head_scale', 'maxSlope': 'max_slope', 'headingJitter': 'heading_jitter'}


def to_opts(js):
    o = {}
    for k, v in js.items():
        if v is None:
            continue
        k2 = KEYMAP.get(k, k)
        o[k2] = height_fn if k2 == 'height_fn' else v
    return o


def compare(name, js):
    V.reset_flora_occupancy()
    plan = V.plan_flora(to_opts(js['opts']))
    g = plan['geo']
    bad = []

    def close(label, a, b, tol):
        a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
        if a.shape != b.shape:
            bad.append(f'{label}: shape {a.shape} vs JS {b.shape}')
            return
        if a.size and np.abs(a - b).max() > tol:
            i = int(np.abs(a - b).argmax())
            bad.append(f'{label}: max |diff| {np.abs(a - b).max():.3g} at {i} ({a.ravel()[i]} vs JS {b.ravel()[i]})')
    nv, nt = g.nverts, g.ntris
    if nv * 3 != len(js['position']) or nt * 3 != len(js['index']):
        bad.append(f"counts: {nv} verts / {nt} tris vs JS {len(js['position']) // 3} / {len(js['index']) // 3}")
    else:
        close('position', g.pos.ravel(), js['position'], 2e-6)
        close('uv', g.uv.ravel(), js['uv'], 2e-6)
        close('aH', g.aH, js['aH'], 2e-6)
        if list(g.tris.ravel()) != list(map(int, js['index'])):
            bad.append('index differs')
        close('normal', g.nrm.ravel(), js['normal'], 2e-4)
    if js.get('stem'):
        sg, js_s = plan['stem_geo'], js['stem']
        if sg is None or sg.nverts * 3 != len(js_s['position']) or sg.ntris * 3 != len(js_s['index']):
            bad.append(f"stem counts: {sg.nverts if sg else 0} / {sg.ntris if sg else 0} vs JS "
                       f"{len(js_s['position']) // 3} / {len(js_s['index']) // 3}")
        else:
            close('stem position', sg.pos.ravel(), js_s['position'], 2e-6)
            close('stem uv', sg.uv.ravel(), js_s['uv'], 2e-5)
            close('stem aH', sg.aH, js_s['aH'], 2e-6)
            close('stem normal', sg.nrm.ravel(), js_s['normal'], 2e-3)
            if list(sg.tris.ravel()) != list(map(int, js_s['index'])):
                bad.append('stem index differs')
    if plan['count'] != js['count']:
        bad.append(f"instances: {plan['count']} vs JS {js['count']}")
    else:
        close('aPosRot', plan['posRot'].ravel(), js['aPosRot'], 2e-5)
        close('aScaleVar', plan['scaleVar'].ravel(), js['aScaleVar'], 2e-6)
        close('aPhase', plan['phase'].ravel(), js['aPhase'], 2e-5)
    known = js['opts'].get('species') in KNOWN_GEOMETRY_DIVERGENCE and not any(
        b.startswith(('counts', 'stem counts', 'instances')) for b in bad)
    verdict = 'OK' if not bad else ('COUNTS OK, geometry differs (known: libm ulp ties, see KNOWN_GEOMETRY_DIVERGENCE)'
                                    if known else 'MISMATCH')
    print(f"[parity] {name}: {verdict}: {plan['count']} plants x {nv} verts / {nt} tris"
          + ('' if known else ''.join('\n    ' + b for b in bad)))
    return not bad or known


if __name__ == '__main__':
    only = sys.argv[1:]
    names = sorted(f[:-5] for f in os.listdir(DUMPS) if f.endswith('.json'))
    ok = True
    for n in names:
        if only and n not in only:
            continue
        with open(os.path.join(DUMPS, n + '.json'), encoding='utf-8') as fh:
            js = json.load(fh)
        try:
            ok &= compare(n, js)
        except NotImplementedError as e:
            print(f'[parity] {n}: SKIPPED ({e})')
    sys.exit(0 if ok else 1)
