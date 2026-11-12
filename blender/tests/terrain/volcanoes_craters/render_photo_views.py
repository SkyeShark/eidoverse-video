"""Photo-matched renders (judging in 3D): every photograph of a place (fetch_photos.py, sources.json) re-shot on the
real DEM (the real_place recipe) and on the generated recipe, from the same camera relative to the landform - its
distance, direction and height - with the photo's focal length and aspect, grey clay under make_sky daylight (the
reference rig's look: Earth 15:30, cumulus, the sun 70 degrees left of the view), at most 960 x 540, 16 samples.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/volcanoes_craters/render_photo_views.py --place mount_fuji --seed 1 \\
        [--only real|gen] [--textured]

Cameras (VIEWS, set by looking at each photo): `cam` is the camera relative to the landform's centre (metres east,
north), from the photo's recorded location (or the estimated one in sources.json); `cam_z` its height: ['ground', m]
above the ground there, or [ref, m] above the landform's top / the lake; `aim` the point the photo is aimed at
(relative metres, [ref, m] height) and `frame` where that point sits in the photo (0..1 from the left, from the
top); `lens` the 35 mm equivalent. The heading and pitch follow from those, the same for both terrains, so each
pair shows the generated landform where the real one stands in the photograph. The generated landform's centre is
the recipe's (0, 0); the real one's is CENTRES in the reference tile. A generated ground camera stands at the real
one's height relative to the landform; where its spot has no open view of the aim (a generated range or ridge in the
way), it moves round the landform to the nearest open one (open_ground_camera; the sheet's caption says by how
much).

Writes out/volcanoes_craters/photo_views/<place>/<photo>_<real|gen>[_tex].png and views_<place>.json.
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

import landform_refs as LR  # noqa: E402
import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'volcanoes_craters', 'photo_views'))
PHOTOS = os.path.normpath(os.path.join(TN, 'out', 'volcanoes_craters', 'photos'))
RECIPE = {'mount_fuji': 'stratovolcano', 'crater_lake': 'caldera', 'meteor_crater': 'impact_crater',
          'sp_crater': 'cinder_cones'}
# (SP Crater's crater floor in the landform tile, which is centred 1.4 km south of the cone: at (-12, -4), the
# tile's centre, the real renders aimed at the plain and showed the cone far off at the frame's edge)
CENTRES = {'mount_fuji': (300.0, 260.0), 'crater_lake': (95.0, 9.0), 'meteor_crater': (30.0, 0.0),
           'sp_crater': (-175.0, 1390.0)}
TOP_R = {'mount_fuji': 900.0, 'crater_lake': 5500.0, 'meteor_crater': 800.0, 'sp_crater': 600.0}

# per photo file: cam / cam_z / aim / aim_z / frame / lens (see the module doc). Wizard Island stands 13 % nearer the
# centre in the recipe (recipes/caldera.py), so its aim point is given for each terrain.
VIEWS = {
    'mount_fuji': {
        'mount_fuji_01_ground_west.jpg': dict(cam='photo', cam_z=['ground', 1.7], aim=[0.0, 0.0], aim_z=['top', 0.0],
                                              frame=[0.52, 0.34], lens=70.0),
        'mount_fuji_02_ground_north.jpg': dict(cam='photo', cam_z=['ground', 20.0], aim=[0.0, 0.0],
                                               aim_z=['top', 0.0], frame=[0.41, 0.44], lens=34.0),
        'mount_fuji_03_ground_southwest.jpg': dict(cam='photo', cam_z=['ground', 25.0], aim=[0.0, 0.0],
                                                   aim_z=['top', 0.0], frame=[0.31, 0.11], lens=40.0),
        # the file's location is 4.9 km out, but at 88 mm the summit crater would fill the frame from there; the
        # whole upper cone in frame puts the aircraft about 10 km north-north-east, 6 km above the summit
        'mount_fuji_04_aerial_north.jpg': dict(cam=[6020.0, 7990.0], cam_z=['top', 6000.0], aim=[0.0, 0.0],
                                               aim_z=['top', 0.0], frame=[0.66, 0.07], lens=88.0),
    },
    'crater_lake': {
        'crater_lake_01_rim_east.jpg': dict(cam='photo', cam_z=['ground', 1.7], aim=[-2950.0, -280.0],
                                            aim_gen=[-2567.0, -244.0], aim_z=['lake', 100.0], frame=[0.25, 0.6],
                                            lens=48.0),
        'crater_lake_02_rim_down.jpg': dict(cam='photo', cam_z=['ground', 1.7], aim=[-2950.0, -280.0],
                                            aim_gen=[-2567.0, -244.0], aim_z=['lake', 150.0], frame=[0.48, 0.35],
                                            lens=42.0),
        'crater_lake_03_aerial_far.jpg': dict(cam='photo', cam_z=['lake', 10100.0], aim=[0.0, 0.0],
                                              aim_z=['lake', 0.0], frame=[0.5, 0.6], lens=50.0),
    },
    'meteor_crater': {
        'meteor_crater_01_rim_north.jpg': dict(cam='photo', cam_z=['ground', 4.0], aim=[0.0, 0.0],
                                               aim_z=['ground', 0.0], frame=[0.5, 0.66], lens=28.0),
        'meteor_crater_02_plain_north.jpg': dict(cam='photo', cam_z=['ground', 1.7], aim=[0.0, 0.0],
                                                 aim_z=['top', 0.0], frame=[0.45, 0.48], lens=69.0),
        'meteor_crater_03_aerial_southeast.jpg': dict(cam='photo', cam_z=['top', 800.0], aim=[0.0, 0.0],
                                                      aim_z=['ground', 0.0], frame=[0.55, 0.55], lens=35.0),
    },
    'sp_crater': {
        'sp_crater_01_aerial_south.jpg': dict(cam='photo', cam_z=['top', 1400.0], aim=[0.0, 0.0],
                                              aim_z=['top', -90.0], frame=[0.55, 0.62], lens=50.0),
        'sp_crater_02_ground_southeast.jpg': dict(cam='photo', cam_z=['ground', 1.7], aim=[0.0, 0.0],
                                                  aim_z=['top', 0.0], frame=[0.22, 0.2], lens=28.0),
        # sp_crater_03 (an older cone south-east of SP, 195 mm) is not re-shot: which cone it shows, and from
        # where, is not known well enough to aim at; it stays on the sheet as the look of the field's old cones
    },
}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(place=opt('--place', 'mount_fuji'), seed=int(opt('--seed', '1')), only=opt('--only'),
                textured='--textured' in a, quality=opt('--quality', 'film'))


def photo_records(place):
    with open(os.path.join(PHOTOS, place, 'sources.json'), encoding='utf-8') as f:
        return {p['file']: p for p in json.load(f)['photos']}


def scene(w, h):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = RR.new_scene((w, h), 16, RR.EXPOSURE)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.5, 200000.0
    cam.data.sensor_fit = 'AUTO'
    cam.data.sensor_width = 36.0
    return sc, cam


def refs_of(t, centre, top_r):
    """The landform's reference heights on a terrain: its top (highest point within top_r of its centre) and its
    lake (the median water surface on the main level, or the top when there is none)."""
    lv = t.main
    f = t.fields('main')
    h = np.asarray(f['h'], np.float64)
    w = np.asarray(f['water'], np.float64) if 'water' in f else np.zeros_like(h)
    X, Y = lv.xy()
    near = np.hypot(X - centre[0], Y - centre[1]) < top_r
    top = float(np.max((h + w)[near]))
    lake = float(np.median((h + w)[w > 0.01])) if (w > 0.01).any() else top
    return dict(top=top, lake=lake)


def height_of(t, refs, spec, x, y):
    kind, dz = spec
    if kind == 'ground':
        return float(t.height_at(x, y)) + float(dz)
    return refs[kind] + float(dz)


def clear_view(t, eye, target, far=0.95):
    """True when the ground stays under the sight line from eye to target, from 3 m out to `far` of the way (the
    samples spaced geometrically: a rise a few metres in front of an eye 1.7 m up hides as much as a ridge)."""
    d = math.dist(eye[:2], target[:2])
    s = np.geomspace(min(3.0 / max(d, 1.0), 0.5 * far), far, 480)
    x = eye[0] + s * (target[0] - eye[0])
    y = eye[1] + s * (target[1] - eye[1])
    z = eye[2] + s * (target[2] - eye[2])
    return bool(np.all(np.asarray(t.height_at(x, y), np.float64) < z))


def open_ground_camera(t, centre, rel, dz, target, want_z, max_deg=30.0, also=()):
    """A ground camera on the generated terrain with the photo's view open. The generated landform's surroundings
    are another instance of the place's (its ranges, ridges and lakes stand elsewhere), so the photo's own spot can
    lie on a hillside facing away, or behind a ridge: there the view is the nearest spot round the landform (the
    bearing within max_deg, the distance within 10 %) whose sight line to the target is open and whose ground lies
    near the real camera's height relative to the landform (within 150 m, else 400 m, else anywhere open). `also`:
    more (target, far) sight lines that must be open (a lake view: the water in front of the aim). Returns
    ((x, y, z), bearing shift in degrees, distance factor), or None when nothing within reach is open."""
    r0 = math.hypot(rel[0], rel[1])
    b0 = math.atan2(rel[1], rel[0])
    cands = []
    for da in sorted(np.arange(-max_deg, max_deg + 0.01, 1.5), key=lambda a: (abs(a), a)):
        for k in (1.0, 0.95, 1.05, 0.9, 1.1):
            b = b0 + math.radians(float(da))
            x, y = centre[0] + r0 * k * math.cos(b), centre[1] + r0 * k * math.sin(b)
            g = float(t.height_at(x, y))
            cands.append((float(da), k, x, y, g, max(g + dz, want_z)))
    for tol in (150.0, 400.0, 1e9):
        for da, k, x, y, g, ez in cands:
            if abs(g + dz - want_z) <= tol and clear_view(t, (x, y, ez), target) \
                    and all(clear_view(t, (x, y, ez), tg, far) for tg, far in also):
                return (x, y, ez), da, k
    return None


def aim_camera(cam, eye, target, frame, lens, w, h):
    """Point cam from eye so that target lands at frame (0..1 from the left, from the top)."""
    cam.data.lens = lens
    dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
    yaw_t = math.atan2(dy, dx)
    pitch_t = math.atan2(dz, math.hypot(dx, dy))
    hf = 36.0 if w >= h else 36.0 * w / h
    vf = 36.0 * h / w if w >= h else 36.0
    u = (frame[0] - 0.5) * hf / lens
    v = (0.5 - frame[1]) * vf / lens
    yaw = yaw_t + math.atan(u)
    pitch = pitch_t - math.atan(v)
    d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))
    return math.degrees(yaw), math.degrees(pitch)


def render(sc, cam, path, sky_root):
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    cache = os.path.join(sky_root, os.path.basename(path))
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)


def size_for(photo):
    pw, ph = photo['width'], photo['height']
    fw, fh = (960, int(round(960 * ph / pw))) if pw / ph >= 960 / 540 else (int(round(540 * pw / ph)), 540)
    return max(fw - fw % 2, 64), max(fh - fh % 2, 64)


def main():
    a = args()
    place = a['place']
    out = os.path.join(OUT, place)
    os.makedirs(out, exist_ok=True)
    photos = photo_records(place)
    h0, meta = LR.load(place)
    views = VIEWS[place]
    rec = dict(args=a, views={})
    sky_root = tempfile.mkdtemp(prefix='volc_photo_sky_')
    match = {}           # photo -> the real camera's height above the landform's reference height
    real_rel = {}        # photo -> the real camera's place relative to the landform's centre
    runs = []
    if a['only'] in (None, 'real'):
        runs.append(('real', 'real_place', dict(params={'dem': place}), CENTRES[place]))
    if a['only'] in (None, 'gen'):
        runs.append(('gen', RECIPE[place], dict(seed=a['seed']), (0.0, 0.0)))
    for which, recipe, kw, centre in runs:
        for palette, suffix in ((None, ''), ('auto', '_tex')):
            if palette is not None and not a['textured']:
                continue
            sc, cam = scene(960, 540)
            tb = time.time()
            t = A.make_terrain(recipe, palette=palette, dress=False, quality=a['quality'], name='terrain', **kw)
            secs = round(time.time() - tb, 1)
            refs = refs_of(t, centre, TOP_R[place])
            for fname, v in views.items():
                p = photos.get(fname)
                if p is None:
                    continue
                if v['cam'] == 'photo':
                    cx, cy = LR.latlon_to_xy(meta, p['camera_lat'], p['camera_lon'])
                    ox, oy = CENTRES[place]
                    rel = (cx - ox, cy - oy)
                else:                                   # estimated from the image (see VIEWS)
                    rel = (float(v['cam'][0]), float(v['cam'][1]))
                if which == 'gen' and fname in real_rel:
                    rel = real_rel[fname]               # where the real camera stood (moved to an open view or not)
                ex, ey = centre[0] + rel[0], centre[1] + rel[1]
                aim = v.get('aim_gen', v['aim']) if which == 'gen' else v['aim']
                tx, ty = centre[0] + aim[0], centre[1] + aim[1]
                ez = height_of(t, refs, v['cam_z'], ex, ey)
                tz = height_of(t, refs, v['aim_z'], tx, ty)
                # the same camera height relative to the landform on both terrains: a ground camera on the real
                # DEM sets it, and the generated one stands there too (never under its own ground plus the eye):
                # 1.7 m over whatever slope lies at that spot on the generated ground framed a hillside instead
                rk = v['aim_z'][0] if v['aim_z'][0] != 'ground' else 'top'
                moved = None
                # a view aimed over a lake sees the water in front of its aim too (a kilometre short of it: an
                # island's waterline), not only the aim point over a near rise
                far = max(0.5, 1.0 - 1000.0 / max(math.hypot(tx - ex, ty - ey), 1.0))
                also = [((tx, ty, refs['lake']), far)] if v['aim_z'][0] == 'lake' else []
                if which == 'real' and p.get('camera_estimated') and v['cam_z'][0] == 'ground':
                    # a spot estimated from the image can land just behind the rim crest it was taken from: the
                    # nearest open spot at the estimate's height stands for it
                    found = open_ground_camera(t, centre, rel, float(v['cam_z'][1]), (tx, ty, tz), ez, also=also)
                    if found is not None:
                        (ex, ey, ez), da, k = found
                        moved = None if (da == 0.0 and k == 1.0) else dict(bearing_deg=da, distance_factor=k)
                if which == 'real':
                    match[fname] = ez - refs[rk]
                    real_rel[fname] = (ex - centre[0], ey - centre[1])
                elif v['cam_z'][0] == 'ground' and fname in match:
                    want = refs[rk] + match[fname]
                    found = open_ground_camera(t, centre, rel, float(v['cam_z'][1]), (tx, ty, tz), want, also=also)
                    if found is None:
                        ez = max(ez, want)
                    else:
                        (ex, ey, ez), da, k = found
                        moved = None if (da == 0.0 and k == 1.0) else dict(bearing_deg=da, distance_factor=k)
                w, h = size_for(p)
                sc.render.resolution_x, sc.render.resolution_y = w, h
                yaw, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'], w, h)
                path = os.path.join(out, os.path.splitext(fname)[0] + f'_{which}{suffix}.png')
                t0 = time.time()
                render(sc, cam, path, sky_root)
                rec['views'][os.path.basename(path)] = dict(
                    photo=fname, terrain=which, recipe=recipe, camera=[round(ex, 1), round(ey, 1), round(ez, 1)],
                    camera_rel=[round(rel[0], 1), round(rel[1], 1)], camera_estimated=p.get('camera_estimated'),
                    camera_moved=moved,
                    aim=[round(tx, 1), round(ty, 1), round(tz, 1)], heading_deg=round(90.0 - yaw, 1) % 360.0,
                    pitch_deg=round(pitch, 2), lens_mm=v['lens'], size=[w, h], refs=refs,
                    terrain_seconds=secs, render_seconds=round(time.time() - t0, 1))
                print(f'[volc.photo] {os.path.basename(path)}: heading {rec["views"][os.path.basename(path)]["heading_deg"]}'
                      f' pitch {pitch:.1f}, {rec["views"][os.path.basename(path)]["render_seconds"]} s', flush=True)
    shutil.rmtree(sky_root, ignore_errors=True)
    path = os.path.join(out, f'views_{place}_{a["only"] or "both"}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    print('[volc.photo] done', flush=True)
    os._exit(0)


main()
