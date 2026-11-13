"""The fluvial package's own pass over the independent review's matched views (out/review): the same cameras,
planned by the reviewer's planner on today's fields, rendered beside the same photographs.

  1. plan (plain Python):
         python review_views.py plan --field fluvial_range=<gen>/<tag>.npz --field rolling_hills=<...> [--meadow]
     The reviewer's plan_views.py functions (out/review/scripts) place each view by the same relation to the
     landform as before (the highest summit; the trunk canyon's side 30 m over its floor; the range from the air
     beyond its lowest side; a hilltop; Steptoe Butte's height ...), on the main level gen.py saved. The meadow's
     views are fixed spots. -> out/fluvial/review/views_plan.json
  2. render (Blender, through a GPU slot):
         bash run_blender.sh review_views.py render --recipe fluvial_range [--views a,b] [--clay all]
     The reviewer's review_render.py logic: make_terrain at the judge's settings (the reference's extent, seed 1,
     film quality, the recipe's defaults), hero levels on the camera when it stands in the main tile, the recipe's
     palette and rocks (and grey clay), make_sky daylight with the sun 70 degrees left of the view, 960 x 540,
     16 samples. -> out/fluvial/review/renders/<recipe>/<view>[_clay].png and <recipe>_render.json
  3. boards (plain Python):
         python review_views.py boards [recipe ...]
     photograph | textured | clay per view, with the camera, as the review's boards. -> out/fluvial/review/boards/
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'fluvial', 'review')
REVIEW_SCRIPTS = os.path.join(TN, 'out', 'review', 'scripts')
PLAN = os.path.join(OUT, 'views_plan.json')
REF = {'fluvial_range': 'san_gabriel_mountains', 'rolling_hills': 'palouse_hills', 'meadow': None}
W, H = 960, 540
TEX_EXPOSURE = -0.5


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


# ------------------------------------------------------------------------------------------------- plan ---

def plan(a):
    sys.path.insert(0, REVIEW_SCRIPTS)
    import numpy as np
    import plan_views as PV                       # the reviewer's planner (its main() is not run on import)
    sys.path.insert(0, os.path.join(TN, 'glacial'))
    import photo_views as GP
    fields = dict(s.split('=', 1) for s in [a[i + 1] for i, x in enumerate(a) if x == '--field'])
    out = json.load(open(PLAN, encoding='utf-8')) if os.path.exists(PLAN) else {}
    for recipe, path in fields.items():
        f = GP.gen_field(path)
        views = getattr(PV, 'plan_' + recipe)(f)
        if recipe == 'fluvial_range':
            views = [open_canyon_road(f, PV, GP, v, np) if v['name'] == 'canyon_road' else v for v in views]
        out[recipe] = dict(views=views, size=float(f.h.shape[0] * f.cell), field=path)
        print(recipe, [(v['name'], [round(c) for c in v['cam']], v['cam_z']) for v in views], flush=True)
    if '--meadow' in a:
        # the review's meadow spots, at the headings and pitches its renders had (its aims were absolute heights
        # on the old meadow's ground): the same angles from today's ground (gen.py's main level, if given)
        done = json.load(open(os.path.join(TN, 'out', 'review', 'renders', 'meadow', 'meadow_render.json'),
                              encoding='utf-8'))
        mpath = opt(a, '--meadow')
        f = GP.gen_field(mpath) if mpath and mpath.endswith('.npz') else None
        views = []
        for v in PV.plan_meadow():
            r = done.get(v['name'], {})
            if f is not None and 'heading_deg' in r:
                kind, dz = v['cam_z']
                z = PV.hz(f, *v['cam']) + float(dz)
                v = dict(v, aim=PV.heading_aim(v['cam'], z, r['heading_deg'], r['pitch_deg'], 200.0),
                         frame=[0.5, 0.5])
            views.append(v)
        out['meadow'] = dict(views=views, size=160.0, field=mpath)
    os.makedirs(OUT, exist_ok=True)
    with open(PLAN, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    print(PLAN)


def los_clear(PV, f, eye, target, near_m=400.0, margin_m=3.0, n=600):
    """PV.los with a margin: over the first near_m the ground (the main level's field) stays margin_m under the sight
    line. The hero levels' rock breakup adds a few metres the main level does not hold, and the previous canyon_road
    camera, open on the main level, rendered a slope filling the frame."""
    import numpy as np
    d = math.dist(eye[:2], target[:2])
    for t in np.linspace(2.0 / max(d, 1.0), 0.97, n):
        x = eye[0] + t * (target[0] - eye[0])
        y = eye[1] + t * (target[1] - eye[1])
        z = eye[2] + t * (target[2] - eye[2])
        if PV.hz(f, x, y) + (margin_m if t * d < near_m else 0.0) > z:
            return False
    return True


def open_canyon_road(f, PV, GP, v, np_):
    """The review's canyon_road rule (on the trunk canyon's side 30 m over its floor, looking up-valley at the trunk
    0.2 along it, 250 m up) with the sight line checked: its spot at 0.55 along the trunk can face straight into
    the wall of a bend. The nearest spot along the trunk (0.55, then 0.5, 0.6, 0.45 ... 0.8, either side) whose
    sight line to the target is open with a margin (los_clear); the review's own spot when none is."""
    Pt, s, floor = GP.trunk(f)
    tgt = Pt[PV.along(Pt, s, 0.2)]
    tz = PV.hz(f, *tgt) + 250.0
    for frac in (0.55, 0.5, 0.6, 0.45, 0.65, 0.4, 0.7, 0.75, 0.8, 0.35):
        kk = PV.along(Pt, s, frac)
        pt, up, right = GP.frame_at(Pt, s, s[kk])
        fl = floor[kk]
        for side in (1.0, -1.0):
            q = None
            for a in np_.arange(0.0, 800.0, 4.0):
                q2 = pt + side * a * right
                if PV.hz(f, *q2) - fl >= 30.0:
                    q = q2
                    break
            if q is None or not PV.inside(f, *q):
                continue
            eye = (float(q[0]), float(q[1]), PV.hz(f, *q) + PV.EYE)
            if los_clear(PV, f, eye, (float(tgt[0]), float(tgt[1]), tz)):
                cap = v['caption'] + ('' if frac == 0.55 and side > 0 else
                                      f' (moved to {frac:.2f} along the trunk, {"right" if side > 0 else "left"} '
                                      f'side: the open view)')
                return dict(v, cam=[float(q[0]), float(q[1])], aim=[float(tgt[0]), float(tgt[1]), float(tz)],
                            caption=cap)
    return v


# ----------------------------------------------------------------------------------------------- render ---

def render_main(a):
    import gc
    import shutil
    import time
    import traceback
    sys.path.insert(0, TN)
    sys.path.insert(0, os.path.join(TN, 'reference'))
    sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))
    import bpy
    import render_references as RR
    from judge import refs
    from eidoblend.sky import make_sky
    from eidoblend.terrain import api as A

    recipe = opt(a, '--recipe')
    samples = int(opt(a, '--samples', '16'))
    sel = [s for s in (opt(a, '--views', '') or '').split(',') if s]
    clay = [s for s in (opt(a, '--clay', '') or '').split(',') if s]
    pl = json.load(open(PLAN, encoding='utf-8'))[recipe]
    views = [v for v in pl['views'] if not sel or v['name'] in sel]
    out = os.path.join(OUT, 'renders', recipe)
    os.makedirs(out, exist_ok=True)
    sky_root = os.path.join(OUT, '_sky', recipe)
    size = refs.load(REF[recipe]).extent if REF[recipe] else None
    rec_path = os.path.join(out, f'{recipe}_render.json')
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}

    def aim_camera(cam, eye, target, frame, lens):
        cam.data.lens = lens
        cam.data.sensor_fit = 'HORIZONTAL'
        cam.data.sensor_width = 36.0
        dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
        yaw_t = math.atan2(dy, dx)
        pitch_t = math.atan2(dz, math.hypot(dx, dy))
        hf, vf = 36.0, 36.0 * H / W
        yaw = yaw_t + math.atan((frame[0] - 0.5) * hf / lens)
        pitch = pitch_t - math.atan((0.5 - frame[1]) * vf / lens)
        d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
        RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))
        return (90.0 - math.degrees(yaw)) % 360.0, math.degrees(pitch)

    def render(sc, cam, path):
        bpy.context.view_layer.update()
        d = cam.matrix_world.col[2][:3]
        hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
        cache = os.path.join(sky_root, os.path.splitext(os.path.basename(path))[0])
        os.makedirs(cache, exist_ok=True)
        sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                       quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
        sky.bake(frame_start=1, frame_end=1, log=lambda *x, **k: None)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        shutil.rmtree(cache, ignore_errors=True)

    from eidoblend.terrain.build import surfacing as SURF
    for v in views:
        passes = [('auto', '')] + ([(None, '_clay')] if (v['name'] in clay or 'all' in clay) else [])
        # one terrain per view: the clay pass swaps the material and hides the rocks (two builds per view were
        # half the run, and with the wide contexts a build takes minutes)
        t = None
        t0 = time.time()
        try:
            sc = RR.new_scene((W, H), samples, TEX_EXPOSURE)
            focus = [(v['cam'][0], v['cam'][1])] if v['focus'] else None
            t = A.make_terrain(recipe, size=size, seed=1, quality='film', palette='auto', dress=True, focus=focus,
                               name=f'{recipe}_review')
            tb = time.time() - t0
        except Exception as e:                                       # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            rec[v['name']] = dict(error=f'{type(e).__name__}: {e}')
            passes = []
        for palette, suffix in passes:
            name = v['name'] + suffix
            t1 = time.time()
            try:
                if palette is None:
                    t.obj.data.materials.clear()
                    t.obj.data.materials.append(SURF.clay_material(f'{recipe}_review_clay'))
                    if isinstance(t.rocks, dict) and t.rocks.get('collection') is not None:
                        t.rocks['collection'].hide_render = True
                    sc.view_settings.exposure = RR.EXPOSURE
                cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
                ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
                kind, dz = v['cam_z']
                if v['name'] == 'summit_over_ridges':
                    # stand on the summit's local top: the plan's highest main-level cell, but on the hero levels a
                    # rock rib a few metres off it rose over the 1.7 m eye and the view looked into the ground
                    best = (float(t.height_at(ex, ey)), ex, ey)
                    for rr in (2.0, 4.0, 7.0, 10.0):
                        for k in range(16):
                            a = 2.0 * math.pi * k / 16.0
                            qx, qy = ex + rr * math.cos(a), ey + rr * math.sin(a)
                            zq = float(t.height_at(qx, qy))
                            if zq > best[0]:
                                best = (zq, qx, qy)
                    ex, ey = best[1], best[2]
                ground = float(t.height_at(ex, ey))
                ez = ground + float(dz) if kind == 'ground' else float(dz)
                tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
                cam = bpy.data.objects.new('review_cam', bpy.data.cameras.new('review_cam'))
                sc.collection.objects.link(cam)
                sc.camera = cam
                dist = math.dist((ex, ey, ez), (tx, ty, tz))
                # out to the outermost context level's edge, so a wide context's far ranges are drawn
                reach = max(4.0 * t.main.side + 40000.0, 0.75 * t.levels[0].side)
                if kind == 'ground':
                    cam.data.clip_start, cam.data.clip_end = 0.1, reach
                else:
                    cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), max(30.0 * dist, reach)
                heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'])
                path = os.path.join(out, name + '.png')
                render(sc, cam, path)
                rec[name] = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], ground=round(ground, 1),
                                 aim=[round(tx, 1), round(ty, 1), round(tz, 1)], lens=v['lens'],
                                 heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), palette=palette,
                                 focus=focus, levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'),
                                 rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None,
                                 build_s=round(tb, 1), total_s=round(time.time() - t1, 1), caption=v['caption'],
                                 photo=v.get('photo'))
                print(f"[review_views] {recipe}/{name}: heading {heading:.0f} pitch {pitch:.1f} ground {ground:.0f} "
                      f"cam z {ez:.0f}; build {tb:.0f} s, render {time.time() - t1:.0f} s", flush=True)
                bpy.data.objects.remove(cam, do_unlink=True)
            except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
                traceback.print_exc()
                rec[name] = dict(error=f'{type(e).__name__}: {e}')
            with open(rec_path, 'w', encoding='utf-8') as fh:
                json.dump(rec, fh, indent=1, default=str)
        del t
        gc.collect()
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[review_views] done', flush=True)
    os._exit(0)


# ----------------------------------------------------------------------------------------------- boards ---

def boards(a):
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, REVIEW_SCRIPTS)
    import boards as RB                                   # the reviewer's photo fit (16:9 crop)
    TW, TH = RB.TW, RB.TH
    pl = json.load(open(PLAN, encoding='utf-8'))
    font = ImageFont.truetype('arial.ttf', 17)
    small = ImageFont.truetype('arial.ttf', 15)
    os.makedirs(os.path.join(OUT, 'boards'), exist_ok=True)
    for r in (a or list(pl)):
        rd = os.path.join(OUT, 'renders', r)
        recp = os.path.join(rd, f'{r}_render.json')
        rec = json.load(open(recp, encoding='utf-8')) if os.path.exists(recp) else {}
        rows = []
        for v in pl[r]['views']:
            tex = os.path.join(rd, v['name'] + '.png')
            clay = os.path.join(rd, v['name'] + '_clay.png')
            if not os.path.exists(tex):
                continue
            row = Image.new('RGB', (3 * TW, TH + 48), (22, 22, 22))
            row.paste(RB.fit(v.get('photo')), (0, 48))
            row.paste(Image.open(tex).convert('RGB').resize((TW, TH), Image.LANCZOS), (TW, 48))
            if os.path.exists(clay):
                row.paste(Image.open(clay).convert('RGB').resize((TW, TH), Image.LANCZOS), (2 * TW, 48))
            d = ImageDraw.Draw(row)
            d.text((6, 2), f"{r} / {v['name']}: {v['caption']}"[:210], fill=(255, 220, 120), font=font)
            x = rec.get(v['name'], {})
            if x and 'camera' in x:
                d.text((6, 24), f"photograph | {r} textured (hero levels, palette, rocks) | grey clay    camera "
                                f"{x['camera']}, ground {x.get('ground')}, heading {x.get('heading_deg')}, pitch "
                                f"{x.get('pitch_deg')}, {x.get('lens'):.0f} mm, rocks {x.get('rocks')}",
                       fill=(200, 200, 200), font=small)
            rows.append(row)
        if not rows:
            continue
        sheet = Image.new('RGB', (3 * TW, sum(im.height for im in rows)), (0, 0, 0))
        y = 0
        for im in rows:
            sheet.paste(im, (0, y))
            y += im.height
        p = os.path.join(OUT, 'boards', f'{r}.jpg')
        sheet.save(p, quality=88)
        print(p, len(rows))


if __name__ == '__main__' or 'bpy' in sys.modules:
    args = argv()
    mode = args[0] if args else ''
    if mode == 'plan':
        plan(args[1:])
    elif mode == 'render':
        render_main(args[1:])
    elif mode == 'boards':
        boards(args[1:])
    else:
        print(__doc__)
