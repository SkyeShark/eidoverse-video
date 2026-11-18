"""The material's check 4 (SURFACING_DESIGN.md 5.4, package 2): the shimmer probe on a terrain, the per-texel material
beside today's.

    bash run_blender.sh blender/tests/terrain/surfacing/check_shimmer.py [--case canyon] [--view approach_walk]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

The probe is test_shimmer.py's, on a judge view of a terrain with baked data (by default the canyon's approach_walk:
the plateau from 1.7 m, ground from the camera's feet to the horizon): the camera turned about the world's z by 0,
0.5 and 1 pixel, three frames per material at 960 x 540, 16 samples, under make_sky. shimmer_metric.py's measure on
each: the half-pixel frame against the average of its neighbours, as a fraction of the real one-pixel change,
mean |f1 - (f0 + f2) / 2| / mean |f2 - f0| of the blurred luminance (Gaussian, sigma 1.5 px), here per band of view
distance on the ground (an emission render of the view distance): near (under 10 m), middle (10-40 m), distant
(40-400 m) and far (past 400 m). Smooth motion scores near 0, texture aliasing that reshuffles with every sub-pixel
offset near 1. The per-texel material passes when no band scores more than today's material + 0.02.
Writes out/surfacing/material/shimmer/<case>_<view>_<today|per_texel>_<k>.png and shimmer_<case>.json.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import numpy as np  # noqa: E402
from mathutils import Matrix  # noqa: E402

OUT = os.path.join(MS.OUT, 'shimmer')
BANDS = (('near', 0.0, 10.0), ('middle', 10.0, 40.0), ('distant', 40.0, 400.0), ('far', 400.0, 1.0e9))
TOLERANCE = 0.02


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(case=opt('--case', 'canyon'), view=opt('--view', 'approach_walk'))


def blur(a, sigma=1.5):
    """A separable Gaussian blur (edge-clamped)."""
    r = int(math.ceil(3.0 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, ((r, r), (r, r)), mode='edge')
    p = sum(k[i] * p[i:i + a.shape[0], :] for i in range(2 * r + 1))
    return sum(k[i] * p[:, i:i + a.shape[1]] for i in range(2 * r + 1))


def luminance(path):
    px = MS.read_png(path).astype(np.float64)
    return blur(px[..., 0] * 0.2126 + px[..., 1] * 0.7152 + px[..., 2] * 0.0722)


def metric(frames, dist, ground):
    out = {}
    for name, d0, d1 in BANDS:
        sel = ground & (dist >= d0) & (dist < d1)
        if int(sel.sum()) < 200:
            out[name] = None
            continue
        e = np.abs(frames[1][sel] - 0.5 * (frames[0][sel] + frames[2][sel])).mean()
        m = np.abs(frames[2][sel] - frames[0][sel]).mean()
        out[name] = round(float(e / max(m, 1e-9)), 3)
    return out


def main():
    a = args()
    case, view = a['case'], a['view']
    os.makedirs(OUT, exist_ok=True)
    sc = MS.scene(samples=16)
    t, obj = MS.terrain(case)
    sd = MS.surface(t)
    cam = MS.camera(sc, t, case, view)
    sky = os.path.join(OUT, '_sky')
    MS.light(sc, cam, sky)
    import bpy
    bpy.context.view_layer.update()
    m0 = cam.matrix_world.copy()
    loc = m0.translation.copy()
    pixel = (36.0 / cam.data.lens) / MS.W                    # radians a pixel spans at the frame's centre
    region = MS.region_material(sd)
    _outside, dist, ground = MS.region_render(sc, obj.data, region, os.path.join(OUT, f'{case}_{view}_region.exr'))
    rec = dict(case=case, view=view, pixel_rad=pixel, bands=[list(b) for b in BANDS], tolerance=TOLERANCE)
    for label, data in (('today', None), ('per_texel', sd)):
        MS.apply(t, obj, data)
        frames = []
        for k in range(3):
            turn = Matrix.Translation(loc) @ Matrix.Rotation(0.5 * k * pixel, 4, 'Z') @ Matrix.Translation(-loc)
            cam.matrix_world = turn @ m0
            bpy.context.view_layer.update()
            if k == 0:
                MS.frame(sc)                                  # the compile and the images' upload, discarded
            path = os.path.join(OUT, f'{case}_{view}_{label}_{k}.png')
            MS.frame(sc, path)
            frames.append(luminance(path))
        cam.matrix_world = m0
        rec[label] = metric(frames, dist, ground)
        MS.log(f'[shimmer] {case} {view} {label}: {rec[label]}')
    rec['pass'] = all(rec['per_texel'][b] is None or rec['today'][b] is None
                      or rec['per_texel'][b] <= rec['today'][b] + TOLERANCE for b, _lo, _hi in BANDS)
    MS.clean(sky)
    path = os.path.join(MS.OUT, f'shimmer_{case}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    MS.log(f"[shimmer] {'PASS' if rec['pass'] else 'FAIL'} -> {path}")


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
