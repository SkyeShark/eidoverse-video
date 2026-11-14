"""Design probe (PORT_PLAN.md 7.3, the revision), the Python half: Blender's own ring-mesh numbers for fields, for
mesh_f32_device.mjs to compare the GPU against.

    <Blender's python> -I eidoverse/terrain/tests/design_probes/mesh_f32_prep.py <out_dir> <name>=<npz with 'h'> [...]

Per field: <name>_h.bin (n x n float32, row 0 south), <name>_cr.bin ((n+1) x (n+1) float32: build/mesh.py _sample's
Catmull-Rom at every cell corner, in float64 then rounded to float32 once, exactly as _assemble writes Z),
<name>_tap.bin ((n+1)^2 float32: the largest |h| among each corner's 4 x 4 taps, for the error bound). Then lines.bin:
Blender's lattice positions np.float32(origin + xs * unit) for a few real (origin, unit) pairs, which the port computes
as Math.fround(origin + xs * unit) in JavaScript doubles. prep.json describes it all, with numpy's version.

The Blender edition is found at blender/ beside eidoverse/ in this checkout, else at $EIDO_BLENDER_EDITION.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_edition():
    for root in (os.path.normpath(os.path.join(HERE, '..', '..', '..', '..')), os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return root
    sys.exit('mesh_f32_prep: no Blender edition here or at $EIDO_BLENDER_EDITION')


sys.path.insert(0, os.path.join(blender_edition(), 'blender'))
import numpy as np  # noqa: E402

from eidoblend.terrain.build import mesh as ME  # noqa: E402

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
info = {'numpy': np.__version__, 'fields': {}}


class W:                       # a window in integer units: cell m spans [m, m + 1), corners at 0..n
    x0 = 0
    y0 = 0
    ci = 1


for spec in sys.argv[2:]:
    name, path = spec.split('=', 1)
    h = np.load(path)['h'].astype(np.float32)
    n = h.shape[0]
    assert h.shape == (n, n)
    W.n = n
    lines = np.arange(0, n + 1)
    Z = ME._sample(h, W, lines, lines, 'cr')                      # float64 (n+1, n+1), rows (y) first
    h.tofile(os.path.join(out, f'{name}_h.bin'))
    Z.astype(np.float32).tofile(os.path.join(out, f'{name}_cr.bin'))
    a = np.abs(h)
    idx = np.clip(lines[:, None] + np.array([-2, -1, 0, 1])[None, :], 0, n - 1)    # _CR_OFF taps, clamped
    rowmax = np.max(a[idx, :], axis=1)                            # (n+1, n): max over the 4 rows of each corner row
    tap = np.max(rowmax[:, idx], axis=2)                          # (n+1, n+1)
    tap.astype(np.float32).tofile(os.path.join(out, f'{name}_tap.bin'))
    info['fields'][name] = {'n': n, 'h_min': float(h.min()), 'h_max': float(h.max()),
                            'max_grad_per_cell': float(np.hypot(*np.gradient(h.astype(np.float64))).max())}

pairs = [(-20000.0, 78.125), (-8000.0, 15.625), (-5123.4375, 0.48828125), (1234.5678, 0.3125), (-40000.0, 156.25 / 3)]
xs = np.arange(0, 4097)
lines_out = np.stack([np.float32(o + xs * u) for o, u in pairs])
lines_out.astype(np.float32).tofile(os.path.join(out, 'lines.bin'))
info['lines'] = {'pairs': pairs, 'count': int(xs.size)}
json.dump(info, open(os.path.join(out, 'prep.json'), 'w'), indent=1)
print(json.dumps(info, indent=1))
