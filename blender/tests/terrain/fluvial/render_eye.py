"""Eye-level renders of the fluvial package's recipes with their hero levels (the package's acceptance is the
eye-level look: design section 12, risk 1), under the reference rig's sky (make_sky, Earth 15:30, cumulus, AgX
Medium High Contrast +0.5, the sun 70 degrees left of the view), 960 x 540, 16 samples.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain/fluvial/render_eye.py --recipe fluvial_range --seed 1 \
        [--params '{"detail": false}'] [--tag r6] [--textured] [--clay] [--view ridge|floor]

fluvial_range  generate() without a focus; on its main level a 30-45 degree hillslope near the centre at mid height
               and a standing point about 500 m across it on a ridge (--view ridge, the default: the San Gabriel
               reference's kind of view) or about 260 m away on lower ground (--view floor: looking up at the
               threshold slopes, the hardest view for planar facets), found by Terrain.viewpoint (a clear line of
               sight); then make_terrain() with the focus on both (hero levels to 0.37 m). Views: <tag>_across (35 mm
               at the slope), <tag>_down (28 mm, the ground 6-60 m ahead), <tag>_hero_aerial (45 degrees down from
               900 m onto the eye: the hero rings and their seams)
rolling_hills  a standing point on high ground looking about 350 m across the hills (the Palouse reference's
               kind of view): <tag>_across, <tag>_down, <tag>_hero_aerial
meadow         the meadow film probe's cameras (eye at (0, -7) 1.6 m up looking north, 'over', 'ground') and its
               8 m clearing (flatten), the meadow palette and the probe's test grass:
               <tag>_eye, <tag>_over, <tag>_ground
--clay renders the clay versions (palette None, the references' grey); --textured the recipe's palette (and rocks
near the focus): <tag>_<view>_tex. Writes into blender/tests/terrain/out/fluvial/renders/ with <tag>_views.json.
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
sys.path.insert(0, TN)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'fluvial', 'renders'))
OLD_TERRAIN_TESTS = os.path.normpath(os.path.join(TN, '..', 'terrain'))


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(recipe=opt('--recipe', 'fluvial_range'), seed=int(opt('--seed', '1')),
                params=json.loads(opt('--params', '{}')), tag=opt('--tag', 'r'), textured='--textured' in a,
                clay='--clay' in a or '--textured' not in a, quality=opt('--quality', 'film'),
                view=opt('--view', 'ridge'))


def pick_slope_view(t, distance=260.0, prefer='low', slope=(28.0, 42.0), height=(35, 70), footing=(30.0, 38.0),
                    look_dz=(8.0, 25.0)):
    """(eye, target): a slope near the main level's centre and a standing point about `distance` across it, with a
    clear sight line (Terrain.viewpoint). A steep range has little ground under 30 degrees and rolling hills block a
    long sight line, so the search widens: the footing allowed, then shorter distances, then a higher aim."""
    lv = t.main
    h = np.asarray(t.fields('main')['h'], np.float64)
    gy, gx = np.gradient(h, lv.cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    X, Y = lv.xy()
    cx, cy = lv.x0 + lv.side / 2, lv.y0 + lv.side / 2
    r = np.hypot(X - cx, Y - cy)
    lo, hi = np.percentile(h, height[0]), np.percentile(h, height[1])
    ok = (s > slope[0]) & (s < slope[1]) & (h > lo) & (h < hi) & (r < 0.25 * lv.side)
    if not ok.any():
        ok = r < 0.3 * lv.side
    idx = np.argsort(r[ok])
    cand = np.stack([X[ok], Y[ok]], 1)[idx]
    cand = cand[:: max(1, len(cand) // 25)][:25]
    for fmax in footing:
        for dist in (distance, 0.6 * distance, 1.5 * distance):
            for dz in look_dz:
                for tx, ty in cand:
                    try:
                        vp = t.viewpoint((float(tx), float(ty)), dist, prefer=prefer, max_slope_deg=fmax,
                                         look_dz=dz)
                        return vp.eye, (float(tx), float(ty))
                    except ValueError:
                        continue
    raise RuntimeError('no view across the slopes near the centre')


def views_for(recipe, a):
    """(generate kwargs, make_terrain kwargs, [(name, eye (x, y, height above ground), target (x, y, dz), lens)],
    focus points, grass)"""
    kw = dict(seed=a['seed'], params=a['params'] or None, quality=a['quality'])
    if recipe == 'meadow':
        flat = [{'at': (0.0, 0.0), 'radius': 8.0, 'falloff': 8.0}]
        views = [('eye', (0.0, -7.0, 1.6), (0.0, 30.0, 0.6), 35.0), ('over', (-26.0, -40.0, None, 18.0),
                                                                     (0.0, 2.0, 0.0), 35.0),
                 ('ground', (1.0, -3.0, 1.0), (2.6, -1.2, 0.0), 35.0)]
        return kw, dict(flatten=flat), views, [(0.0, -7.0), (0.0, 12.0)], True
    t = A.generate(recipe, **kw)
    if recipe == 'rolling_hills':
        eye, tgt = pick_slope_view(t, 350.0, prefer='high', slope=(0.0, 12.0), height=(60, 95), footing=(15.0, 25.0),
                                   look_dz=(2.0, 10.0))
    elif a['view'] == 'floor':
        # the hardest view for planar threshold slopes: from low ground up at a 28-42 degree slope 260 m away
        eye, tgt = pick_slope_view(t, 260.0)
    else:
        # the San Gabriels' reference view: on a ridge, across a valley at the slopes opposite
        eye, tgt = pick_slope_view(t, 500.0, prefer='high', slope=(30.0, 45.0), height=(30, 75), footing=(32.0, 40.0),
                                   look_dz=(10.0, 40.0))
    hx, hy = tgt[0] - eye[0], tgt[1] - eye[1]
    L = math.hypot(hx, hy)
    fx, fy = eye[0] + 22.0 * hx / L, eye[1] + 22.0 * hy / L
    back = 900.0 * math.cos(math.radians(45))
    views = [('across', (eye[0], eye[1], 1.7), (tgt[0], tgt[1], 8.0), 35.0),
             ('down', (eye[0], eye[1], 1.7), (fx, fy, 0.0), 28.0),
             ('hero_aerial', (eye[0] - back * hx / L, eye[1] - back * hy / L, None, 900.0 * math.sin(math.radians(45))),
              (eye[0], eye[1], 1.7), 35.0)]
    return kw, {}, views, [eye[:2], tgt], False


def render(sc, cam, name, sky_root, rec):
    d = Vector(cam.matrix_world.col[2][:3]) * -1.0
    hd = math.atan2(d.y, d.x) + math.radians(RR.SUN_LEFT_DEG)
    cache = os.path.join(sky_root, name)
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    rec[name] = dict(camera=[round(v, 2) for v in cam.location], lens_mm=cam.data.lens,
                     seconds=round(time.time() - t0, 1))
    print(f'[fluvial.render] {name}.png {rec[name]["seconds"]} s', flush=True)


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = RR.new_scene((960, 540), 16, RR.EXPOSURE)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.05, 80000.0
    return sc, cam


def point(tt, p):
    """A view point: (x, y, height above the ground) or (x, y, None, absolute z)."""
    if len(p) == 4:
        return (p[0], p[1], p[3])
    return (p[0], p[1], float(tt.height_at(p[0], p[1])) + p[2])


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    rec = dict(args=a)
    t0 = time.time()
    kw, extra, views, focus, grass = views_for(a['recipe'], a)
    rec['views'] = views
    sky_root = tempfile.mkdtemp(prefix='fluvial_sky_')
    for palette, suffix, on in ((None, '', a['clay']), ('auto', '_tex', a['textured'])):
        if not on:
            continue
        sc, cam = scene()
        tb = time.time()
        tt = A.make_terrain(a['recipe'], focus=focus, palette=palette, dress=palette is not None, name='terrain',
                            **kw, **extra)
        rec['make_terrain' + suffix] = dict(seconds=round(time.time() - tb, 1), levels=[str(lv) for lv in tt.levels],
                                            triangles=tt.ring.triangle_count, info_seconds=tt.info.get('seconds'),
                                            skipped=tt.info.get('skipped_stages'))
        if grass and palette is not None:
            sys.path.insert(0, OLD_TERRAIN_TESTS)
            import _grass_fixture
            _grass_fixture.add_test_grass(tt.obj, clear_radius=8.0, outer_radius=42.0)
        for name, eye, tgt, lens in views:
            if palette is not None and name == 'hero_aerial':
                continue
            RR.place_camera(cam, point(tt, eye), point(tt, tgt))
            cam.data.lens = lens
            render(sc, cam, f"{a['tag']}_{name}{suffix}", sky_root, rec)
    shutil.rmtree(sky_root, ignore_errors=True)
    rec['seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, f"{a['tag']}_views.json"), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    print('[fluvial.render] done', rec['seconds'], 's', flush=True)
    os._exit(0)


main()
