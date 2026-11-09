"""The real ground at the hero levels' cells: swissALTI3D 0.5 m (the 2025 edition, the same edition as the reference
DEM's 2 m tiles) around the Lauterbrunnen eye spot, resampled onto every hero level of real_place's plan, so the
detail stages can be judged against what the place really looks like at 0.5-4 m.

    python -I blender/tests/terrain_new/detail/lauterbrunnen_truth.py        (plain Python; -I: it reads downloads)

The tiles (four 1 km tiles, E 2635-2637 km, N 1159-1161 km in LV95) were fetched with the reference fetch script's
own download function into out/detail/downloads/swissalti3d_05m/ (public elevation data, (c) swisstopo). Each hero
level's cell centres go from the reference's local frame (landform_refs.xy_to_latlon) to LV95 (the fetch script's
wgs84_to_lv95, about 1 m), and the 0.5 m mosaic is low-passed to the level's cell (Gaussian, sigma 0.45 x the ratio,
as the fetch script does) and sampled bilinearly. Heights are relative to the main DEM's lowest point (real_place's
z = 0, 732.95 m). Outside the tiles: NaN.

Writes out/detail/truth/real_L<i>.npz (h, cell, x0, y0, n, covered fraction) and real_L<i>_hillshade.png.
"""
import json
import os
import site
import sys

sys.path.append(site.getusersitepackages())
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.normpath(os.path.join(HERE, '..', 'reference'))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
sys.path.insert(0, REF)
import plain_import  # noqa: E402

plain_import.install()
os.environ.setdefault('OPENCV_LOG_LEVEL', 'ERROR')
import numpy as np  # noqa: E402

from eidoblend.terrain.core import levels as L  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402
# cv2, landform_refs and the fetch script are imported where the tiles are read: Blender's Python (which imports
# focus() and plan() from here) has no cv2

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail'))
TILES = os.path.join(OUT, 'downloads', 'swissalti3d_05m')
TRUTH = os.path.join(OUT, 'truth')
BASE_M = 732.95                                   # real_place's z = 0: the main DEM's lowest point
E0, N1 = 2635000.0, 1161000.0                     # the mosaic's west and north edges (LV95)


def focus():
    """real_place Lauterbrunnen's focus in the mesh-and-API package's render: the reference's eye spot and the
    robot's spot 14 m along the view."""
    with open(os.path.join(REF, 'renders', 'lauterbrunnen_views.json')) as f:
        eye = json.load(f)['eye']
    ex, ey = eye['camera'][:2]
    tx, ty = eye['target'][:2]
    L_ = float(np.hypot(tx - ex, ty - ey))
    ux, uy = (tx - ex) / L_, (ty - ey) / L_
    return [(ex, ey), (ex + 14.0 * ux + 1.6 * uy, ey + 14.0 * uy - 1.6 * ux)], eye


def plan():
    pts, _eye = focus()
    return L.plan_levels(8000.0, 1000, (0.0, 0.0), 4, pts, 0.5, warn=lambda m: print('[plan]', m))


def mosaic():
    import fetch_references as FR
    src = np.full((4000, 4000), np.nan, np.float32)
    with open(os.path.join(TILES, 'tiles.json')) as f:
        tiles = json.load(f)
    for key, (_yr, name, _size) in tiles.items():
        e, n = (int(v) for v in key.split('-'))
        a, g = FR.geotiff(os.path.join(TILES, name))
        assert abs(g['scale'][0] - 0.5) < 1e-6 and abs(g['tie'][3] - e * 1000) < 1e-3, name
        r0, c0 = int(round((N1 - (n + 1) * 1000) / 0.5)), int(round((e * 1000 - E0) / 0.5))
        src[r0:r0 + a.shape[0], c0:c0 + a.shape[1]] = a
    return src


def resample(src, lv):
    import cv2
    import fetch_references as FR
    import landform_refs as R
    X, Y = lv.xy()
    lat, lon = R.xy_to_latlon(46.572, 7.905, X, Y)
    E, N = FR.wgs84_to_lv95(lat, lon)
    col = ((E - E0) / 0.5 - 0.5).astype(np.float32)
    row = ((N1 - N) / 0.5 - 0.5).astype(np.float32)
    ratio = lv.cell / 0.5
    a = src
    if ratio > 1.25:
        filled = np.where(np.isfinite(a), a, 0.0).astype(np.float32)
        w = np.isfinite(a).astype(np.float32)
        s = 0.45 * ratio
        a = cv2.GaussianBlur(filled, (0, 0), s) / np.maximum(cv2.GaussianBlur(w, (0, 0), s), 1e-6)
        a = np.where(cv2.GaussianBlur(w, (0, 0), s) > 0.99, a, np.nan).astype(np.float32)
    out = cv2.remap(np.where(np.isfinite(a), a, -9999.0).astype(np.float32), col, row, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=-9999.0)
    out = np.where(out > -1000.0, out - BASE_M, np.nan)
    return out.astype(np.float32)


def main():
    os.makedirs(TRUTH, exist_ok=True)
    src = mosaic()
    rec = []
    for lv in plan():
        if lv.role != 'hero':
            continue
        h = resample(src, lv)
        cov = float(np.isfinite(h).mean())
        np.savez_compressed(os.path.join(TRUTH, f'real_L{lv.index}.npz'), h=h, cell=lv.cell, x0=lv.x0, y0=lv.y0,
                            n=lv.n, covered=cov)
        hs = IO.hillshade(np.where(np.isfinite(h), h, np.nanmean(h)), lv.cell)
        hs = np.where(np.isfinite(h), hs, 0.0)
        IO.write_png(os.path.join(TRUTH, f'real_L{lv.index}_hillshade.png'), np.ascontiguousarray(IO.to_u8(hs)[::-1]))
        rec.append(dict(level=str(lv), covered=round(cov, 3)))
        print(f'[truth] level {lv.index} {lv}: {cov * 100:.0f} % covered by the 0.5 m tiles', flush=True)
    with open(os.path.join(TRUTH, 'truth.json'), 'w') as f:
        json.dump(dict(levels=rec, base_m=BASE_M, source='swissALTI3D 0.5 m, 2025 edition, (c) swisstopo'), f,
                  indent=1)


if __name__ == '__main__':
    main()
