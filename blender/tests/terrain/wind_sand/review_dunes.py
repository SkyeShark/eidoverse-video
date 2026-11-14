"""The independent review's three dune views, re-planned on the dunes recipe as it stands and rendered beside the
same photographs (in Blender, through a GPU slot):

    bash run_blender.sh blender/tests/terrain/wind_sand/review_dunes.py [--tag name] [--views a,b] [--clay 1] \\
        [--seed 1] [--params '{"kind": "star"}'] [--set '{"hero_winds": "last2"}']
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The plan is the review's (out/review/scripts/plan_views.py, plan_dunes) on this run's own main level: the highest
dune within 2.5 km of the tile centre; 'interdune_floor' from the floor 900 m from it, the lowest spot with an open
view, 1.7 m, 45 mm (photo: Dune 45); 'crest' on that dune at 1.7 m looking out where the field falls away, 28 mm
(photo: a Sossusvlei crest); 'aerial' 3.5 km south-west and 700 m over it, 45 mm (photo: the Great Sand Dunes' star
dune). The render is the review's (review_render.py): make_terrain at the Namib reference's extent, seed 1, film
quality, hero levels on ground cameras, palette 'auto' with rocks (and grey clay with --clay 1), make_sky daylight
with the sun 70 degrees left of the view, 960 x 540, 16 samples, exposure -0.5 textured / +0.5 clay.

Writes out/wind_sand/review<_tag>/<view>[_clay].png, views.json, and board.jpg (photograph | textured | clay).
"""
import gc
import json
import math
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

PHOTOS = os.path.join(TN, 'out', 'integration', 'photos')
EYE = 1.7
W, H = 960, 540
TEX_EXPOSURE = -0.5
SIZE = 8000.0                     # the Namib reference's extent (the review's make_terrain size)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(tag=opt('--tag', ''), views=opt('--views', ''), clay=opt('--clay', '1') == '1',
                seed=int(opt('--seed', '1')), params=json.loads(opt('--params', '{}')),
                samples=int(opt('--samples', '16')), set=json.loads(opt('--set', '{}')))


def recipe_for(stage_set):
    """The dunes recipe, or (with --set) its dict with the dune_field stage's own parameters overridden (as
    dune_lab.py's variants do), to try a setting in the review's views before it becomes the default."""
    if not stage_set:
        return 'dunes'
    from eidoblend.terrain import recipes as R
    d = R.get('dunes').to_dict()
    for st in d['stages']:
        if st['op'] == 'dune_field':
            st['params'].update(stage_set)
    return d


class Field:
    """The main level as plan_views' Field: bilinear height in local metres (tile centre at 0, 0), the context level
    beyond it."""

    def __init__(self, t):
        self.lv = t.main
        self.h = np.asarray(t.fields('main')['h'], np.float64)
        self.c = t.levels[0]
        self.hc = np.asarray(t.fields(0)['h'], np.float64)
        self.cx, self.cy = self.lv.centre

    def _bil(self, h, lv, x, y):
        i = (x - lv.x0) / lv.cell - 0.5
        j = (y - lv.y0) / lv.cell - 0.5
        n = h.shape[0]
        i = min(max(i, 0.0), n - 1.001)
        j = min(max(j, 0.0), n - 1.001)
        i0, j0 = int(i), int(j)
        ti, tj = i - i0, j - j0
        return float(h[j0, i0] * (1 - ti) * (1 - tj) + h[j0, i0 + 1] * ti * (1 - tj) + h[j0 + 1, i0] * (1 - ti) * tj
                     + h[j0 + 1, i0 + 1] * ti * tj)

    def height(self, x, y):
        X, Y = x + self.cx, y + self.cy
        if self.lv.x0 <= X <= self.lv.x1 and self.lv.y0 <= Y <= self.lv.y1:
            return self._bil(self.h, self.lv, X, Y)
        return self._bil(self.hc, self.c, X, Y)

    def inside(self, x, y, margin):
        half = self.lv.side / 2.0
        return abs(x) < half - margin and abs(y) < half - margin


def los(f, eye, target, start=3.0, far=0.97, n=400):
    d = math.dist(eye[:2], target[:2])
    for t in np.geomspace(min(start / max(d, 1.0), 0.5 * far), far, n):
        x = eye[0] + t * (target[0] - eye[0])
        y = eye[1] + t * (target[1] - eye[1])
        z = eye[2] + t * (target[2] - eye[2])
        if f.height(x, y) > z:
            return False
    return True


def floor_spot_toward(f, target, dist, tz, step_deg=10.0):
    best = None
    for az in np.arange(0.0, 360.0, step_deg):
        a = math.radians(az)
        x, y = target[0] + dist * math.sin(a), target[1] + dist * math.cos(a)
        if not f.inside(x, y, 200.0):
            continue
        z = f.height(x, y)
        if los(f, (x, y, z + EYE), (target[0], target[1], tz)):
            if best is None or z < best[0]:
                best = (z, (x, y))
    return best[1] if best else None


def heading_aim(cam_xy, cam_z, heading_deg, pitch_deg, dist=2000.0):
    a, p = math.radians(heading_deg), math.radians(pitch_deg)
    return [cam_xy[0] + dist * math.sin(a) * math.cos(p), cam_xy[1] + dist * math.cos(a) * math.cos(p),
            cam_z + dist * math.sin(p)]


def plan(f):
    """plan_views.plan_dunes on this field."""
    lv = f.lv
    X = (np.arange(lv.n) + 0.5) * lv.cell - lv.side / 2.0
    XX, YY = np.meshgrid(X, X)
    inner = (np.abs(XX) < 2500) & (np.abs(YY) < 2500)
    k = int(np.argmax(np.where(inner, f.h, -np.inf)))
    j, i = np.unravel_index(k, f.h.shape)
    dx, dy, dz = float(XX[j, i]), float(YY[j, i]), float(f.h[j, i])
    P = os.path.join(PHOTOS, 'namib_star_dunes')
    v = []
    spot = floor_spot_toward(f, (dx, dy), 900.0, dz)
    if spot is not None:
        v.append(dict(name='interdune_floor', cam=list(spot), cam_z=['ground', EYE], aim=[dx, dy, dz - 40.0],
                      lens=45.0, frame=[0.5, 0.55], focus=True, photo=os.path.join(P, 'namib_star_dunes_02.jpg'),
                      caption='from the interdune floor 900 m from the highest star dune, 1.7 m, 45 mm (photo: Dune '
                              '45, Benoit Vicart, CC0)'))
    best = None
    for az in np.arange(0, 360, 15):
        a = math.radians(az)
        g = np.mean([f.height(dx + d * math.sin(a), dy + d * math.cos(a)) for d in np.linspace(800, 4000, 12)])
        if best is None or g < best[0]:
            best = (g, az)
    v.append(dict(name='crest', cam=[dx + 15.0, dy + 15.0], cam_z=['ground', EYE],
                  aim=heading_aim((dx, dy), dz + EYE, best[1], -7.0, 3000.0), lens=28.0, frame=[0.5, 0.5], focus=True,
                  photo=os.path.join(P, 'namib_star_dunes_03.jpg'),
                  caption='on the highest crest at 1.7 m across the field, 28 mm (photo: from a dune crest, Benoit '
                          'Vicart, CC0)'))
    v.append(dict(name='aerial', cam=[dx - 3500.0, dy - 3500.0], cam_z=['abs', dz + 700.0], aim=[dx, dy, dz - 100.0],
                  lens=45.0, frame=[0.5, 0.5], focus=False,
                  photo=os.path.join(PHOTOS, 'great_sand_dunes', 'great_sand_dunes_02.jpg'),
                  caption='a low oblique over the field, 700 m over the top dune, 45 mm (photo: the Star Dune, Great '
                          'Sand Dunes NP, public domain)'))
    return v, (dx, dy, dz)


def aim_camera(cam, eye, target, frame, lens):
    """review_render.aim_camera: point cam from eye so the target lands at frame (0..1 from the left, the top)."""
    cam.data.lens = lens
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
    yaw_t = math.atan2(dy, dx)
    pitch_t = math.atan2(dz, math.hypot(dx, dy))
    hf, vf = 36.0, 36.0 * H / W
    u = (frame[0] - 0.5) * hf / lens
    vv = (0.5 - frame[1]) * vf / lens
    yaw = yaw_t + math.atan(u)
    pitch = pitch_t - math.atan(vv)
    d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))
    return (90.0 - math.degrees(yaw)) % 360.0, math.degrees(pitch)


def render(sc, cam, path, sky_root):
    """review_render.render: make_sky daylight with the sun 70 degrees left of the view."""
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    cache = os.path.join(sky_root, os.path.splitext(os.path.basename(path))[0])
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)


def board(out, views, rec):
    from PIL import Image, ImageDraw, ImageFont
    TW, TH = 640, 360

    def fit(path):
        if not path or not os.path.exists(path):
            return Image.new('RGB', (TW, TH), (40, 40, 40))
        im = Image.open(path).convert('RGB')
        w, h = im.size
        if w / h > TW / TH:
            nw = int(h * TW / TH)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w * TH / TW)
            top = max(0, min(h - nh, int(0.45 * (h - nh))))
            im = im.crop((0, top, w, top + nh))
        return im.resize((TW, TH), Image.LANCZOS)
    font = ImageFont.truetype('arial.ttf', 17)
    small = ImageFont.truetype('arial.ttf', 15)
    rows = []
    for v in views:
        tex = os.path.join(out, v['name'] + '.png')
        if not os.path.exists(tex):
            continue
        row = Image.new('RGB', (3 * TW, TH + 48), (22, 22, 22))
        row.paste(fit(v.get('photo')), (0, 48))
        row.paste(Image.open(tex).convert('RGB').resize((TW, TH), Image.LANCZOS), (TW, 48))
        clay = os.path.join(out, v['name'] + '_clay.png')
        if os.path.exists(clay):
            row.paste(Image.open(clay).convert('RGB').resize((TW, TH), Image.LANCZOS), (2 * TW, 48))
        d = ImageDraw.Draw(row)
        d.text((6, 2), f"dunes / {v['name']}: {v['caption']}"[:210], fill=(255, 220, 120), font=font)
        x = rec.get(v['name'], {})
        if 'camera' in x:
            d.text((6, 24), f"photograph | dunes textured (hero levels, palette, rocks) | grey clay    camera "
                            f"{x['camera']}, ground {x['ground']}, heading {x['heading_deg']}, pitch {x['pitch_deg']},"
                            f" {x['lens']:.0f} mm", fill=(200, 200, 200), font=small)
        rows.append(row)
    if rows:
        sheet = Image.new('RGB', (3 * TW, sum(im.height for im in rows)), (0, 0, 0))
        y = 0
        for im in rows:
            sheet.paste(im, (0, y))
            y += im.height
        p = os.path.join(out, 'board.jpg')
        sheet.save(p, quality=90)
        print(p, flush=True)


def main():
    a = args()
    out = os.path.join(TN, 'out', 'wind_sand', 'review' + (('_' + a['tag']) if a['tag'] else ''))
    os.makedirs(out, exist_ok=True)
    sky_root = os.path.join(out, '_sky')
    params = a['params'] or None
    recipe = recipe_for(a['set'])
    t = A.generate(recipe, size=SIZE, seed=a['seed'], params=params, quality='film', cache=True)
    views, top = plan(Field(t))
    del t
    sel = [s for s in a['views'].split(',') if s]
    views = [v for v in views if not sel or v['name'] in sel]
    rec = {'top_dune': top}
    for v in views:
        for palette, suffix in [('auto', '')] + ([(None, '_clay')] if a['clay'] else []):
            t0 = time.time()
            name = v['name'] + suffix
            try:
                sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE if palette else RR.EXPOSURE)
                focus = [tuple(v['cam'])] if v['focus'] else None
                t = A.make_terrain(recipe, size=SIZE, seed=a['seed'], params=params, quality='film',
                                   palette=palette, dress=palette is not None, focus=focus, name='dunes_review')
                tb = time.time() - t0
                cx, cy = t.main.centre
                ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
                kind, dz = v['cam_z']
                ground = float(t.height_at(ex, ey))
                ez = ground + float(dz) if kind == 'ground' else float(dz)
                tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
                cam = bpy.data.objects.new('review_cam', bpy.data.cameras.new('review_cam'))
                sc.collection.objects.link(cam)
                sc.camera = cam
                dist = math.dist((ex, ey, ez), (tx, ty, tz))
                if kind == 'ground':
                    cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.main.side + 40000.0
                else:
                    cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
                heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'])
                render(sc, cam, os.path.join(out, name + '.png'), sky_root)
                rec[name] = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], ground=round(ground, 1),
                                 aim=[round(tx, 1), round(ty, 1), round(tz, 1)], lens=v['lens'],
                                 heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), palette=palette,
                                 levels=[str(lv) for lv in t.levels], build_s=round(tb, 1),
                                 total_s=round(time.time() - t0, 1), caption=v['caption'], photo=v.get('photo'))
                print(f"[review dunes] {name}: heading {heading:.0f} pitch {pitch:.1f} ground {ground:.0f}; build "
                      f"{tb:.0f} s, total {time.time() - t0:.0f} s", flush=True)
                del t
            except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
                traceback.print_exc()
                rec[name] = dict(error=f'{type(e).__name__}: {e}')
            gc.collect()
            with open(os.path.join(out, 'views.json'), 'w', encoding='utf-8') as fh:
                json.dump(dict(views=views, renders=rec), fh, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    board(out, views, rec)
    print('[review dunes] done', flush=True)
    os._exit(0)


main()
