"""The API's numeric parts: generate() on real_place Lauterbrunnen at draft quality (the level runner's kernels
need Blender: run it through a GPU slot).

Checks
  flatten     a disc and a rotated rectangle: inside each (four cells in from the edge, where the mesh's Catmull-Rom
              vertices read only flattened cells) height_at is exactly the resolved height; beyond the falloff (plus
              three cells) the ground is the unflattened terrain's to the bit; the resolved heights are in t.flats
              and the disc's is the median of the ground under it
  recipe dict recipes.get('real_place').to_dict() through JSON and back gives the same recipe and the same heights
  viewpoint   the standing point is about the distance asked, its footing under the slope limit, and the sight line
              from 1.7 m to the target clears the ground (re-checked here along 400 samples)
  masks       MaskSet.at agrees with the main level's array at cell centres

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/mesh_api/test_api.py
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..')))
from eidoblend.terrain.api import generate, flatten_fields  # noqa: E402,F401
from eidoblend.terrain import recipes  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api'))
quiet = lambda *a: None  # noqa: E731


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {}
    ok = True
    kw = dict(params={'dem': 'lauterbrunnen'}, quality='draft', cache=False, log=quiet)
    t0 = time.perf_counter()
    base = generate('real_place', **kw)
    # draft cells are 16 m and a mesh vertex reads 4 x 4 cells (Catmull-Rom), so exactness starts 4 cells in
    flat = [{'at': (480.0, 1640.0), 'radius': 120.0, 'falloff': 40.0},
            {'at': (-900.0, -2500.0), 'size': (300.0, 200.0), 'angle_deg': 30.0, 'falloff': 30.0, 'height': None}]
    t = generate('real_place', flatten=flat, **kw)
    cell = t.main.cell
    m4 = 4.0 * cell
    rng = np.random.default_rng(3)
    out = {}
    for k, s in enumerate(t.flats):
        z = s['height']
        if s.get('size') is None:
            r = rng.uniform(0, s['radius'] - m4, 500)
            a = rng.uniform(0, 2 * math.pi, 500)
            x, y = s['at'][0] + r * np.cos(a), s['at'][1] + r * np.sin(a)
            # the median of the unflattened ground under the disc (the main level is the finest here)
            X, Y = t.main.xy()
            under = np.hypot(X - s['at'][0], Y - s['at'][1]) <= s['radius']
            med = float(np.median(base.fields('main')['h'][under]))
        else:
            w, l = s['size']
            u = rng.uniform(-w / 2 + m4, w / 2 - m4, 500)
            v = rng.uniform(-l / 2 + m4, l / 2 - m4, 500)
            a = math.radians(s['angle_deg'])
            x = s['at'][0] + u * math.cos(a) - v * math.sin(a)
            y = s['at'][1] + u * math.sin(a) + v * math.cos(a)
            med = None
        inside_err = float(np.abs(t.height_at(x, y) - z).max())
        # beyond the falloff: the terrain without the flat
        ring = s.get('radius', max(s.get('size', (0, 0)))) + s['falloff'] + 3.0 * cell
        a2 = rng.uniform(0, 2 * math.pi, 500)
        r2 = rng.uniform(ring, ring + 300.0, 500)
        x2, y2 = s['at'][0] + r2 * np.cos(a2), s['at'][1] + r2 * np.sin(a2)
        outside_err = float(np.abs(t.height_at(x2, y2) - base.height_at(x2, y2)).max())
        good = inside_err <= 1e-4 and outside_err == 0.0 and (med is None or abs(med - z) < 1e-4)
        ok &= good
        out[k] = dict(flat=s, inside_max_err_m=inside_err, outside_max_err_m=outside_err, median_m=med, pass_=good)
        print(f'[api] flatten {k}: {"PASS" if good else "FAIL"} height {z:.3f} m, inside max |h - height| '
              f'{inside_err:.2e} m, beyond the falloff max |h - unflattened| {outside_err:.2e} m'
              + (f', median of the ground under it {med:.3f} m' if med is not None else ''), flush=True)
    res['flatten'] = out
    # a recipe dict through JSON gives the same recipe and the same terrain (the cache key also hashes the code of
    # core and the solvers, which other packages may be editing between two calls, so it is not compared here)
    d = json.loads(json.dumps(recipes.get('real_place').to_dict()))
    t2 = generate(d, **kw)
    xs = rng.uniform(-4000, 4000, 2000)
    ys = rng.uniform(-4000, 4000, 2000)
    same = (t2.recipe.to_dict() == recipes.get('real_place').to_dict()
            and float(np.abs(t2.height_at(xs, ys) - base.height_at(xs, ys)).max()) == 0.0)
    res['recipe_dict_round_trip'] = bool(same)
    ok &= same
    print(f'[api] recipe dict round trip: {"PASS" if same else "FAIL"} (same recipe dict, same heights)', flush=True)
    # viewpoint
    target = (-382.4, -3558.2)
    vp = base.viewpoint(target, 3000.0, prefer='low')
    ex, ey, ez = vp.eye
    tx, ty, tz = vp.target
    s = np.linspace(3.0 / vp.distance, 0.97, 400)
    lx, ly, lz = ex + (tx - ex) * s, ey + (ty - ey) * s, ez + (tz - ez) * s
    clear = float((lz - base.height_at(lx, ly)).min())
    foot = math.degrees(math.acos(abs(base.normal_at(ex, ey, smooth=False)[2])))
    good = clear > 0.0 and foot <= 30.0 and 0.5 * 3000 <= vp.distance <= 1.6 * 3000
    ok &= good
    res['viewpoint'] = dict(vp._asdict(), recheck_clearance_m=clear, footing_slope_deg=foot, pass_=good)
    print(f'[api] viewpoint: {"PASS" if good else "FAIL"} eye ({ex:.0f}, {ey:.0f}, {ez:.1f}) {vp.distance:.0f} m '
          f'from the target, heading {vp.heading_deg:.0f} deg, footing {foot:.1f} deg, sight line clears by '
          f'{clear:.1f} m', flush=True)
    # MaskSet.at against the level array at cell centres
    lv = base.main
    X, Y = lv.xy()
    j = rng.integers(0, lv.n, 300)
    i = rng.integers(0, lv.n, 300)
    a = base.masks['slope'].array('main')[j, i]
    b = base.mask('slope').at(X[j, i], Y[j, i])
    merr = float(np.abs(a - b).max())
    good = merr <= 1e-4
    ok &= good
    res['mask_at_max_err_deg'] = merr
    print(f'[api] MaskSet.at vs the level array at cell centres: {"PASS" if good else "FAIL"} max {merr:.1e} deg',
          flush=True)
    res['seconds'] = round(time.perf_counter() - t0, 1)
    res['pass'] = bool(ok)
    with open(os.path.join(OUT, 'test_api.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print('[api] ' + ('ALL PASS' if ok else 'FAILURES'), flush=True)
    return ok


main()                          # no sys.exit: under Blender an exit code tears the GPU module down mid-shutdown
