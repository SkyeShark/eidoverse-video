"""The U-shape fit's measures (blender/tests/terrain/glacial/test_gpu.py test_u_fit) on a carved synthetic valley the
port wrote: the Blender judge's own family numbers (judge/family.alpine_valley) before and after the carve, and the
test's four sections across the trunk (box_sections, transcribed from test_gpu.py, which runs its tests on import).

    <Blender's python> -I eidoverse/terrain/tests/glacial/u_fit_judge.py <folder>

<folder> holds before.f32, after.f32 (float32, row 0 south) and meta.json ({n, cell, x0, y0}); writes judge.json there.
numpy only.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

B.bare_terrain_package()
import numpy as np  # noqa: E402
from judge import family as FA  # noqa: E402

d = sys.argv[1]
meta = json.load(open(os.path.join(d, 'meta.json'), encoding='utf-8'))
n, cell, x0, y0 = int(meta['n']), float(meta['cell']), float(meta['x0']), float(meta['y0'])
before = np.fromfile(os.path.join(d, 'before.f32'), '<f4').reshape(n, n)
after = np.fromfile(os.path.join(d, 'after.f32'), '<f4').reshape(n, n)


def box_sections(h, ys=(-1500.0, -1000.0, 1000.0, 1500.0), half=1500.0):
    """test_gpu.py box_sections: per section across the trunk (x = 0) at y, the floor's width (within 10 m of its
    lowest point), the wall's height 250 m out from the floor's edge (the lower side) and the share of the walls'
    height (floor to lip: the first point past the steepest where the slope falls under 30 degrees) at 60 degrees or
    more."""
    xs = x0 + (np.arange(n) + 0.5) * cell
    ycs = y0 + (np.arange(n) + 0.5) * cell
    out = []
    for y in ys:
        j = int(np.argmin(np.abs(ycs - y)))
        sel = np.abs(xs) <= half
        x, z = xs[sel], np.asarray(h, np.float64)[j, sel]
        k0 = int(np.argmin(z))
        zf = float(z[k0])
        lo, hi = k0, k0
        while lo > 0 and z[lo - 1] <= zf + 10.0:
            lo -= 1
        while hi < len(z) - 1 and z[hi + 1] <= zf + 10.0:
            hi += 1
        rise, steep = [], []
        for side, e in ((-1, lo), (1, hi)):
            idx = np.arange(e, -1, -1) if side < 0 else np.arange(e, len(z))
            dd = np.abs(x[idx] - x[e])
            w = z[idx] - zf
            rise.append(float(np.interp(250.0, dd, w)))
            sl = np.degrees(np.arctan(np.gradient(w, dd + 1e-9)))
            km = int(np.argmax(sl))
            after_ = np.nonzero(sl[km:] < 30.0)[0]
            ks = km + int(after_[0]) if after_.size else len(w) - 1
            dz = np.diff(w[:ks + 1])
            steep.append(float(dz[sl[1:ks + 1] >= 60.0].sum() / max(w[ks], 1e-6)))
        out.append(dict(y=y, floor_m=float(x[hi] - x[lo]), rise_250_m=min(rise), steep=min(steep)))
    return out


res = dict(before=FA.alpine_valley(np.asarray(before, np.float64), cell),
           after=FA.alpine_valley(np.asarray(after, np.float64), cell), sections=box_sections(after),
           versions=B.versions())
with open(os.path.join(d, 'judge.json'), 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=1, default=float)
print(json.dumps({k: v for k, v in res['after'].items() if not isinstance(v, list)}))
