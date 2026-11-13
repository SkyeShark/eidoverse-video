"""Photo-matched views of tower_karst (Blender, a GPU slot): the review's three cameras on the generated terrain, each
beside the Li River photograph it stands for (out/integration/photos/guilin_karst/, CC0, Huangdan2060), textured
(the recipe's palette, rocks) and in grey clay, 960 x 540, 16 samples, under make_sky daylight. The terrain is the
recipe at the reference's extent (8 km, film quality, seed 1 by default), with its hero levels on each camera.

    python blender/tests/terrain/coast/slot.py blender/tests/terrain/karst/render_photo_views.py -- \
        [--seed 1] [--tag v1] [--views riverbank,plain_fields,aerial]

The cameras, found on the generated main level the way the review found them (out/review/scripts/plan_views.py):
  riverbank     on the river's bank at 1.7 m, a bank cell beside the water near the tile's centre, looking along
                the river 1.2 km downstream at 60 m above the ground there, 28 mm (photo 01: the towers along the Li)
  plain_fields  on the plain at 1.7 m, open low ground for 450 m ahead and towers 550-850 m off, aimed 50 m under
                their tops, 30 mm (photo 04: the plain under a massif)
  aerial        1800 m south-west of the river's middle and 400 m over the tallest tower, aimed at the river's
                middle, 35 mm (photo 03: the Li between its towers)
Writes out/karst/views/<tag>_<view>_tex.png and _clay.png and <tag>_views.json; sheet_photo_views.py lays them out.
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, os.path.join(TN, 'reference'))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'karst', 'views'))
SIZE = 8000.0
EYE = 1.7
TEX_EXPOSURE = RR.EXPOSURE - 0.5


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(seed=int(opt('--seed', '1')), tag=opt('--tag', 'v1'),
                views=[v for v in (opt('--views') or 'riverbank,plain_fields,aerial').split(',') if v])


def grid(t):
    lv = t.main
    f = t.fields('main')
    h = np.asarray(f['h'], np.float64)
    w = np.asarray(f['water'], np.float64) if 'water' in f else np.zeros_like(h)
    xs = lv.x0 + (np.arange(lv.n) + 0.5) * lv.cell
    return lv, h, w, xs


def hz(t, x, y):
    return float(t.height_at(np.array([x]), np.array([y]))[0])


def clear(t, eye, tgt, margin=0.5, k=200):
    e, g = np.asarray(eye, np.float64), np.asarray(tgt, np.float64)
    s = np.linspace(0.03, 0.97, k)
    P = e[None, :] + (g - e)[None, :] * s[:, None]
    return float((P[:, 2] - np.asarray(t.height_at(P[:, 0], P[:, 1]), np.float64)).min()) >= margin


def river_cells(t):
    lv, h, w, xs = grid(t)
    wet = w > 0.3
    jj, ii = np.nonzero(wet)
    return lv, h, w, xs, wet, jj, ii


def view_riverbank(t):
    lv, h, w, xs, wet, jj, ii = river_cells(t)
    if jj.size == 0:
        raise RuntimeError('no river on the main level')
    X, Y = xs[ii], xs[jj]
    order = np.argsort(np.hypot(X, Y))
    gy, gx = np.gradient(h, lv.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    best = None
    for k in order[:4000:40]:
        px, py = X[k], Y[k]
        # the river's direction here: the principal axis of the wet cells within 300 m
        m = np.hypot(X - px, Y - py) < 300.0
        Q = np.stack([X[m] - X[m].mean(), Y[m] - Y[m].mean()], 1)
        d = np.linalg.svd(Q, full_matrices=False)[2][0]
        nrm = np.array([-d[1], d[0]])
        for side in (1.0, -1.0):
            # the bank: the first dry, gentle cell going out from the water
            for r in np.arange(10.0, 160.0, 4.0):
                bx, by = px + side * r * nrm[0], py + side * r * nrm[1]
                i, j = int((bx - lv.x0) / lv.cell), int((by - lv.y0) / lv.cell)
                if not (0 <= i < lv.n and 0 <= j < lv.n):
                    break
                if not wet[j, i] and w[j, i] == 0 and slope[j, i] < 8.0:
                    break
            else:
                continue
            for sgn in (1.0, -1.0):
                tx, ty = bx + sgn * 1200.0 * d[0], by + sgn * 1200.0 * d[1]
                if max(abs(tx), abs(ty)) > SIZE / 2 - 100:
                    continue
                eye = (bx, by, hz(t, bx, by) + EYE)
                tgt = (tx, ty, hz(t, tx, ty) + 60.0)
                # wet along the sight line: the river ahead
                s = np.linspace(0.05, 0.6, 30)
                qx, qy = bx + (tx - bx) * s, by + (ty - by) * s
                qi = np.clip(((qx - lv.x0) / lv.cell).astype(int), 0, lv.n - 1)
                qj = np.clip(((qy - lv.y0) / lv.cell).astype(int), 0, lv.n - 1)
                score = float(wet[qj, qi].mean()) - float(np.hypot(bx, by)) / 8000.0
                if best is None or score > best[0]:
                    best = (score, eye, tgt)
    if best is None:
        raise RuntimeError('no bank found')
    return best[1], best[2], 28.0


def view_plain_fields(t):
    lv, h, w, xs = grid(t)
    gy, gx = np.gradient(h, lv.cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    rng = np.random.default_rng(1)
    best = None

    def hat(x, y):
        if max(abs(x), abs(y)) > SIZE / 2 - 20:
            return None
        return h[int((y - lv.y0) / lv.cell), int((x - lv.x0) / lv.cell)]
    for _ in range(900):
        j, i = rng.integers(120, lv.n - 120, 2)
        if slope[j, i] > 2.0 or w[j, i] > 0:
            continue
        g0 = h[j, i]
        for az in range(0, 360, 10):
            a = math.radians(az)
            ok = True
            for da in (-14, 0, 14):
                aa = math.radians(az + da)
                for d in range(20, 460, 20):
                    v = hat(xs[i] + d * math.sin(aa), xs[j] + d * math.cos(aa))
                    if v is None or v > g0 + 4.0:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            hh = [hat(xs[i] + d * math.sin(a), xs[j] + d * math.cos(a)) for d in (550, 700, 850)]
            if any(v is None for v in hh):
                continue
            k = int(np.argmax(hh))
            score = max(hh) - g0
            if best is None or score > best[0]:
                d = (550, 700, 850)[k]
                # aimed at the towers' middle height: the photograph frames them over a strip of the plain
                best = (score, (xs[i], xs[j], g0 + EYE), (xs[i] + d * math.sin(a), xs[j] + d * math.cos(a),
                                                         g0 + max(0.45 * score, 25.0)))
    if best is None:
        raise RuntimeError('no plain spot with towers 550-850 m off')
    return best[1], best[2], 30.0


def view_aerial(t):
    lv, h, w, xs, wet, jj, ii = river_cells(t)
    X, Y = xs[ii], xs[jj]
    k = int(np.argmin(np.hypot(X, Y)))
    c = (float(X[k]), float(Y[k]))
    eye = (c[0] - 1800.0, c[1] - 1800.0, float(h.max()) + 400.0)
    tgt = (c[0], c[1], hz(t, *c))
    return eye, tgt, 35.0


FINDERS = {'riverbank': view_riverbank, 'plain_fields': view_plain_fields, 'aerial': view_aerial}


def render(sc, cam, path, sky_dir, sun_xy):
    os.makedirs(sky_dir, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=sky_dir,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    pct = sc.render.resolution_percentage
    sc.render.resolution_percentage = 10
    bpy.ops.render.render(write_still=False)
    sc.render.resolution_percentage = pct
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    base = A.generate('tower_karst', size=SIZE, seed=a['seed'], quality='film', cache=True)
    rec = dict(args=a, views={})
    sky_root = tempfile.mkdtemp(prefix='karst_sky_')
    for name in a['views']:
        try:
            eye, tgt, lens = FINDERS[name](base)
        except Exception as e:                                          # noqa: BLE001 - recorded, the others go on
            rec['views'][name] = dict(error=f'{type(e).__name__}: {e}')
            print(f'[karst.views] {name}: not rendered: {e}', flush=True)
            continue
        tv = time.time()
        RR.new_scene((960, 540), 16, RR.EXPOSURE)
        sc = bpy.context.scene
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_start, cam.data.clip_end = 0.1, 80000.0
        focus = None if name == 'aerial' else [(eye[0], eye[1]), (0.5 * (eye[0] + tgt[0]), 0.5 * (eye[1] + tgt[1]))]
        tt = A.make_terrain('tower_karst', size=SIZE, seed=a['seed'], focus=focus, palette='auto', dress=True,
                            quality='film', cache=True, name='terrain')
        if name != 'aerial':
            g = float(tt.height_at(np.array([eye[0]]), np.array([eye[1]]))[0])
            eye = (eye[0], eye[1], g + EYE)
        RR.place_camera(cam, eye, tgt)
        cam.data.lens = lens
        # the sun behind the camera's left shoulder (the photographs are front-lit, hazy)
        d = np.array(tgt[:2]) - np.array(eye[:2])
        d /= max(float(np.hypot(*d)), 1e-6)
        sun_xy = (-d[0] * 0.8 - d[1] * 0.6, -d[1] * 0.8 + d[0] * 0.6)
        stem = os.path.join(OUT, f"{a['tag']}_{name}")
        sc.view_settings.exposure = TEX_EXPOSURE
        render(sc, cam, stem + '_tex.png', os.path.join(sky_root, name), sun_xy)
        sc.view_settings.exposure = RR.EXPOSURE
        from eidoblend.terrain.build import surfacing as S
        tt.obj.data.materials.clear()
        tt.obj.data.materials.append(S.clay_material('karst_clay'))
        if isinstance(getattr(tt, 'rocks', None), dict) and tt.rocks.get('object') is not None:
            tt.rocks['object'].hide_render = True
        sc.render.filepath = stem + '_clay.png'
        bpy.ops.render.render(write_still=True)
        rec['views'][name] = dict(camera=[round(v, 1) for v in eye], target=[round(v, 1) for v in tgt], lens_mm=lens,
                                  levels=[str(lv) for lv in tt.levels], seconds=round(time.time() - tv, 1))
        print(f"[karst.views] {name}: camera {rec['views'][name]['camera']} -> {rec['views'][name]['target']}, "
              f"{lens} mm, {rec['views'][name]['seconds']} s", flush=True)
    shutil.rmtree(sky_root, ignore_errors=True)
    rec['seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, f"{a['tag']}_views.json"), 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, indent=1, default=str)
    os._exit(0)


main()
