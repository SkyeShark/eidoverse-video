"""The surfacing's review videos (SURFACING_DESIGN.md section 6): per recipe a 6 s walk at eye level and an 8 s aerial
orbit, built the way a scene author builds a shot through make_terrain (the surface bake, the per-texel material, the
rocks and the plants, the cameras passed), so the videos show what the stills cannot: shimmer, seams at window edges
and the far hand-off, plants changing their level of detail. One recipe per Blender process, through a GPU slot:

    EIDO_TERRAIN_CACHE_GB=40 bash run_blender.sh blender/tests/terrain/surfacing_judge/video.py --recipe canyon \\
        [--kinds walk,orbit] [--tag t] [--snap <dir>] [--no-plants] [--fps 24] [--samples 16] [--orbit-deg 90]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

walk   the recipe's photographed eye view (WALK; views.json's camera, lens and framing): the camera walks a tenth of
       the way to its aim (10-150 m, shorter where the ground ahead would rise into its sight line: walk_path),
       1.7 m over the ground smoothed over 3 m, looking at the aim; the terrain's hero levels around the camera's
       start (the still's terrain), the plants planned along the walk with the crowns kept off its line (cameras=
       along the path)
orbit  the recipe's aerial view (ORBIT): the camera carried --orbit-deg around the ground it looks at, at its height
       and distance, lifted where the ground or its sight line to the aim needs (orbit_heights); the plants planned
       around that ground; every orbit position passed as a camera (the far material on the rings beyond 1.5 D0 of
       all of them)
Both: 960 x 540, 16 samples, make_sky daylight (the sun 70 degrees left of the first frame's view, where it stays),
AgX at exposure -0.5, H.264 High yuv420p with a silent AAC track and faststart (ordinary players open them), checked
with ffprobe and a full decode. Writes out/surfacing_judge/videos/<recipe>_<kind>[_<tag>].mp4 and videos.json.
"""
import gc
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
for _p in (os.path.normpath(os.path.join(TN, '..', '..')), TN, os.path.join(TN, 'reference')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from judge import refs  # noqa: E402
from judge import video as JV  # noqa: E402
from surfacing_judge import shots as SH  # noqa: E402
from surfacing_judge import views as V  # noqa: E402

OUT = os.path.join(TN, 'out', 'surfacing_judge', 'videos')
WALK = {'fluvial_range': 'canyon_road', 'alpine_valley': 'floor_lischmaad', 'stratovolcano': 'walk_upper_flank',
        'caldera': 'rim_east', 'cinder_cones': 'ground_se', 'impact_crater': 'walk_floor',
        'canyon': 'approach_walk', 'incised_meanders': 'rim_walk', 'mesas_buttes': 'valley_view',
        'badlands': 'prairie_walk', 'dunes': 'interdune_floor', 'tower_karst': 'plain_fields',
        'sea_cliffs': 'clifftop_along', 'rolling_hills': 'hilltop_walk', 'real_place': 'floor_lischmaad',
        'meadow': 'eye_swales'}
ORBIT = {'fluvial_range': 'aerial_range_front', 'alpine_valley': 'aerial_axis', 'stratovolcano': 'aerial_nne',
         'caldera': 'aerial_far', 'cinder_cones': 'aerial_south', 'impact_crater': 'aerial_sse',
         'canyon': 'aerial_down_canyon', 'incised_meanders': 'aerial_loops', 'mesas_buttes': 'aerial',
         'badlands': 'aerial', 'dunes': 'aerial', 'tower_karst': 'aerial', 'sea_cliffs': 'establishing',
         'rolling_hills': 'aerial', 'real_place': 'establishing', 'meadow': 'drone'}
WALK_S, ORBIT_S = 6.0, 8.0
WALK_AHEAD_M = 40.0       # a walk's ground within 40 m ahead may rise into its sight line to the aim at most
WALK_RISE_DEG = 4.0       # 4 degrees further than in the still's own frame (not a gully's far wall in the lens)
WALK_SMOOTH_M = 3.0       # its eye height follows the ground smoothed over 3 m, never under 1.2 m
ORBIT_CLEAR_M, ORBIT_CLEAR_R_M = 40.0, 150.0   # an orbit keeps 40 m of air over the ground within 150 m of it
ORBIT_SIGHT_M = 15.0      # and its sight line to the aim passes 15 m over the ground over the first third of the way
ORBIT_SIGHT_SHARE = 1.0 / 3.0   # (an aim hidden behind a far rim is a view; a slope filling the lens is not)
ORBIT_MAX_LIFT = 0.25     # lifted at most this share of its height over the aim more than the still; past it, it turns less


def _heights(t, x, y):
    return np.asarray(t.height_at(np.asarray(x, np.float64), np.asarray(y, np.float64)), np.float64)


def _sight_need(t, p, aim, s, margin):
    """Per camera position of p (N, 3): the height it needs for its straight line to aim to pass margin over the
    ground at the fractions s of the way (the line's height there is z (1 - s) + s aim_z)."""
    qx = p[:, 0:1] + s[None, :] * (aim[0] - p[:, 0:1])
    qy = p[:, 1:2] + s[None, :] * (aim[1] - p[:, 1:2])
    h = _heights(t, qx.ravel(), qy.ravel()).reshape(qx.shape)
    return np.max((h + margin - s[None, :] * aim[2]) / (1.0 - s[None, :]), axis=1)


def _smooth(z, sigma):
    """A Gaussian of sigma samples along a path, its ends held."""
    if sigma < 0.5:
        return np.asarray(z, np.float64)
    k = np.arange(-int(3 * sigma), int(3 * sigma) + 1)
    w = np.exp(-0.5 * (k / sigma) ** 2)
    return np.convolve(np.pad(z, len(k) // 2, mode='edge'), w / w.sum(), mode='valid')


def _ground_rise(t, p, aim, d):
    """Per camera position of p (N, 3): how far the ground at the distances d ahead (toward the aim, at most 0.8 of
    the way) rises above the sight line to the aim, in degrees of elevation (negative: below it)."""
    dx, dy = aim[0] - p[:, 0:1], aim[1] - p[:, 1:2]
    D = np.hypot(dx, dy)
    dd = np.minimum(d[None, :], 0.8 * D)
    h = _heights(t, (p[:, 0:1] + dx / D * dd).ravel(), (p[:, 1:2] + dy / D * dd).ravel()).reshape(dd.shape)
    return (np.degrees(np.arctan2(h - p[:, 2:3], dd)) - np.degrees(np.arctan2(aim[2] - p[:, 2:3], D))).max(axis=1)


def walk_path(t, start, aim, dz, n, length):
    """The walk's n camera positions from start toward aim: dz over the ground smoothed over WALK_SMOOTH_M (never
    under 1.2 m), over `length` metres, shortened (0.6x at a time, down to 10 m) while the ground within
    WALK_AHEAD_M ahead of a frame rises more than WALK_RISE_DEG further into its sight line to the aim than it does
    at the still's own camera (a gully's far wall in the lens); where no length toward the aim passes, the same
    lengths backing away from it (a dolly out of the still), else the shortest toward it. Returns the positions
    (n, 3), the length walked (negative: backing away) and the lengths tried with their frames over."""
    ex, ey = start
    dist = math.hypot(aim[0] - ex, aim[1] - ey)
    ux, uy = (aim[0] - ex) / dist, (aim[1] - ey) / dist
    d = np.geomspace(1.0, WALK_AHEAD_M, 40)
    tried, first = [], None
    for sign in (1.0, -1.0):
        L = float(length)
        while True:
            s = sign * L * np.arange(n) / max(n - 1, 1)
            px, py = ex + ux * s, ey + uy * s
            g = _heights(t, px, py)
            pz = np.maximum(_smooth(g, WALK_SMOOTH_M * max(n - 1, 1) / L) + dz, g + min(dz, 1.2))
            p = np.stack([px, py, pz], 1)
            rise = _ground_rise(t, p, aim, d)
            over = int(np.count_nonzero(rise[1:] > max(float(rise[0]), 0.0) + WALK_RISE_DEG))
            tried.append([round(sign * L, 1), over])
            if not over:
                return p, sign * L, tried
            if L <= 10.0:
                break
            L = max(10.0, 0.6 * L)
        if first is None:
            first = (p, sign * L)
    return first[0], first[1], tried


def _orbit_need(t, px, py, pz, aim):
    """The lift each orbit position needs: to ORBIT_CLEAR_M of air over the ground within ORBIT_CLEAR_R_M, and for
    its sight line to the aim to pass ORBIT_SIGHT_M over the ground over the first ORBIT_SIGHT_SHARE of the way."""
    ang = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
    rx = px[:, None] + ORBIT_CLEAR_R_M * np.cos(ang)[None, :]
    ry = py[:, None] + ORBIT_CLEAR_R_M * np.sin(ang)[None, :]
    ground = np.maximum(_heights(t, px, py), _heights(t, rx.ravel(), ry.ravel()).reshape(rx.shape).max(axis=1))
    need = np.maximum(ground + ORBIT_CLEAR_M, _sight_need(t, np.stack([px, py, pz], 1), aim,
                                                          np.linspace(0.005, ORBIT_SIGHT_SHARE, 64), ORBIT_SIGHT_M))
    return need - pz


def orbit_path(t, aim, rad, b0, z_at, follows_ground, degrees, n):
    """The orbit's n camera positions around the aim at radius rad: `degrees` of turn from the still's bearing b0,
    lifted where the ground or the sight line to the aim needs more than the still's own camera does; where that
    lift would pass ORBIT_MAX_LIFT of the camera's height over the aim, only the part of a turn either way around
    b0 that stays within it (a valley's floor seen from its side lies behind its walls). z_at(x, y) gives the
    unlifted heights. One height for an orbit at a height, a smoothed lift for one that follows the ground. Returns
    (positions (n, 3), degrees turned, the largest lift)."""
    deg = int(round(degrees))
    th = b0 + np.radians(np.arange(-deg, deg + 1))
    px, py = aim[0] + rad * np.cos(th), aim[1] + rad * np.sin(th)
    z0 = z_at(px, py)
    still = max(float(_orbit_need(t, px[deg:deg + 1], py[deg:deg + 1], z0[deg:deg + 1], aim)[0]), 0.0)
    ok = _orbit_need(t, px, py, z0, aim) - still <= max(ORBIT_CLEAR_M, ORBIT_MAX_LIFT * (float(z0[deg]) - aim[2]))
    lo = hi = deg
    while lo > 0 and ok[lo - 1]:
        lo -= 1
    while hi < 2 * deg and ok[hi + 1]:
        hi += 1
    a0 = max(lo, min(deg, hi - deg)) if hi - lo >= deg else lo
    a1 = min(hi, a0 + deg)
    th = b0 + np.radians(np.linspace(a0 - deg, a1 - deg, n))
    px, py = aim[0] + rad * np.cos(th), aim[1] + rad * np.sin(th)
    z0 = z_at(px, py)
    z = z0 + np.maximum(_orbit_need(t, px, py, z0, aim) - still, 0.0)
    if follows_ground:
        env = np.array([z[max(0, i - 6):i + 7].max() for i in range(n)])
        z = np.maximum(_smooth(env, 4.0), z)
    else:
        z = np.full(n, float(z.max()))
    return np.stack([px, py, z], 1), float(a1 - a0), float((z - z0).max())


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(recipe=opt('--recipe'), kinds=[k for k in opt('--kinds', 'walk,orbit').split(',') if k],
                tag=opt('--tag', ''), snap=opt('--snap'), plants='--no-plants' not in a, fps=int(opt('--fps', '24')),
                samples=int(opt('--samples', '16')), orbit_deg=float(opt('--orbit-deg', '90')))


def mux_aac(raw, final):
    """The video stream as it is, plus a silent stereo AAC track; +faststart."""
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-f', 'lavfi',
                    '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000', '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', final],
                   check=True)


def check(path):
    """ffprobe's view of a finished video and a full decode: ok when it is H.264 High yuv420p 960 x 540 with AAC."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                          'stream=codec_type,codec_name,profile,pix_fmt,width,height,nb_frames:format=duration',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), {})
    au = next((s for s in j['streams'] if s['codec_type'] == 'audio'), {})
    dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    r = dict(video=v.get('codec_name'), profile=v.get('profile'), pix_fmt=v.get('pix_fmt'), width=v.get('width'),
             height=v.get('height'), frames=int(v.get('nb_frames') or 0), audio=au.get('codec_name'),
             duration=round(float(j.get('format', {}).get('duration', 0.0)), 2),
             decodes=dec.returncode == 0 and not dec.stderr.strip(), size_mb=round(os.path.getsize(path) / 1e6, 2))
    r['ok'] = (r['video'] == 'h264' and r['profile'] == 'High' and r['pix_fmt'] == 'yuv420p'
               and (r['width'], r['height']) == (960, 540) and r['audio'] == 'aac' and r['decodes'])
    return r


def key(cam, f):
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)


def render_animation(sc, cam, plant_objects, n, fps, cache, frames, raw, log):
    """make_sky over the frames (the sun fixed where the first frame puts it), the plants bound to its sun, every frame
    rendered and encoded (judge/video.encode: H.264 High yuv420p, CRF 18, faststart)."""
    from eidoblend.sky import make_sky
    RR = SH.rr()
    sc.frame_start, sc.frame_end = 1, n
    sc.render.fps = fps
    sc.frame_set(1)
    bpy.context.view_layer.update()
    os.makedirs(cache, exist_ok=True)
    os.makedirs(frames, exist_ok=True)
    t0 = time.time()
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(SH.sun_xy(cam)))
    sky.bake(frame_start=1, frame_end=n, log=SH.quiet)
    if any(plant_objects.values()):
        from eidoblend.terrain.build import plant_instances as PI
        PI.bind_sun(sky.sun)
    t_sky = time.time() - t0
    sc.render.filepath = os.path.join(frames, 'f')
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    t_render = time.time() - t1
    JV.encode(frames, raw, fps)
    log(f'[video] {os.path.basename(raw)}: sky {t_sky:.0f} s, {n} frames in {t_render:.0f} s ({t_render / n:.2f} s a '
        f'frame)')
    return dict(sky_s=round(t_sky, 1), render_s=round(t_render, 1), frame_s=round(t_render / n, 2))


def release(t):
    """The terrain's plant objects; the numpy side (the levels' fields and masks, the surface maps, the plan's
    working arrays: several GB on a film terrain) let go before the frames, which compile every shader under the
    job's RAM cap."""
    objects = dict(t.plant_objects)
    t.surface = t.plants = None
    return objects


def walk(a, recipe, plan, size, params, c0, log):
    v = next(w for w in plan['views'] if w['name'] == WALK[recipe])
    sc = SH.rr().new_scene((SH.W, SH.H), a['samples'], SH.EXPOSURE)
    focus = [(c0[0] + v['cam'][0], c0[1] + v['cam'][1])] if v['focus'] else None
    t, source = SH.terrain_for(recipe, v['name'], size, params, focus, a['snap'])
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
    dz = float(v['cam_z'][1]) if v['cam_z'][0] == 'ground' else 1.7
    n = int(round(WALK_S * a['fps']))
    path, length, tried = walk_path(t, (ex, ey), (tx, ty, tz), dz, n,
                                    min(max(0.1 * math.hypot(tx - ex, ty - ey), 10.0), 150.0))
    if len(tried) > 1:
        log(f'[video] {recipe} walk: [length m (negative: backing away), frames with the ground rising into the '
            f'sight line] {tried}')
    spec = SH.plant_spec(v, (ex, ey), (tx, ty), path=path[::12]) if a['plants'] else None
    t0 = time.time()
    t.build(f'{recipe}_walk', palette=SH.palette_now(recipe), dress=True, plants=spec, cameras=[path],
            mask_attributes=False, log=SH.quiet)
    build_s = time.time() - t0
    cam = bpy.data.objects.new('walk_cam', bpy.data.cameras.new('walk_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.levels[0].side + 40000.0
    for f in range(n):
        SH.aim_camera(cam, tuple(path[f]), (tx, ty, tz), v['frame'], v['lens'])
        key(cam, f + 1)
    info = dict(view=v['name'], terrain=source, build_s=round(build_s, 1), walk_m=round(length, 1),
                walk_tried=tried, start=[round(ex, 1), round(ey, 1)],
                plants=(t.info.get('plants') or {}).get('counts'), far_material=len(t.obj.data.materials) > 1)
    return sc, cam, release(t), n, info


def orbit(a, recipe, plan, size, params, c0, log):
    v = next(w for w in plan['views'] if w['name'] == ORBIT[recipe])
    sc = SH.rr().new_scene((SH.W, SH.H), a['samples'], SH.EXPOSURE)
    focus = [(c0[0] + v['cam'][0], c0[1] + v['cam'][1])] if v['focus'] else None
    t, source = SH.terrain_for(recipe, v['name'], size, params, focus, a['snap'])
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    kind, dz = v['cam_z']
    ez = float(t.height_at(ex, ey)) + float(dz) if kind == 'ground' else float(dz)
    tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
    rad = math.hypot(ex - tx, ey - ty)
    b0 = math.atan2(ey - ty, ex - tx)
    n = int(round(ORBIT_S * a['fps']))
    if kind == 'ground':                                  # a low view keeps its height over the ground it flies over
        def z_at(x, y):
            return _heights(t, x, y) + float(dz)
    else:
        def z_at(x, y):
            return np.full(np.shape(x), ez)
    path, turned, lift = orbit_path(t, (tx, ty, tz), rad, b0, z_at, kind == 'ground', a['orbit_deg'], n)
    if lift > 0.5 or turned < a['orbit_deg'] - 0.5:
        log(f'[video] {recipe} orbit: {turned:.0f} degrees, lifted up to {lift:.0f} m (the ground, or the sight '
            f'line to the aim)')
    spec = SH.plant_spec(v, (ex, ey), (tx, ty)) if a['plants'] else None
    t0 = time.time()
    t.build(f'{recipe}_orbit', palette=SH.palette_now(recipe), dress=True, plants=spec, cameras=[path],
            mask_attributes=False, log=SH.quiet)
    build_s = time.time() - t0
    cam = bpy.data.objects.new('orbit_cam', bpy.data.cameras.new('orbit_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    dist = math.dist((ex, ey, ez), (tx, ty, tz))
    cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 4.0 * t.levels[0].side + 40000.0
    for f in range(n):
        SH.aim_camera(cam, tuple(path[f]), (tx, ty, tz), v['frame'], v['lens'])
        key(cam, f + 1)
    info = dict(view=v['name'], terrain=source, build_s=round(build_s, 1), degrees=round(turned, 1),
                radius_m=round(rad, 1), lift_m=round(lift, 1), plants=(t.info.get('plants') or {}).get('counts'),
                far_material=len(t.obj.data.materials) > 1)
    return sc, cam, release(t), n, info


def main():
    a = args()
    recipe = a['recipe']
    log = lambda *x, **k: print(*x, flush=True)               # noqa: E731
    plan = V.load()[recipe]
    size = refs.load(plan['reference']).extent if plan.get('reference') else None
    params = plan.get('params') or SH.PARAMS.get(recipe)
    c0 = SH.recipe_centre(recipe, params)
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, 'videos.json')
    tag = f"_{a['tag']}" if a['tag'] else ''
    for kind in a['kinds']:
        name = f'{recipe}_{kind}{tag}'
        rec = dict(when=time.strftime('%Y-%m-%d %H:%M'))
        t0 = time.time()
        try:
            sc, cam, plant_objects, n, info = (walk if kind == 'walk' else orbit)(a, recipe, plan, size, params, c0,
                                                                                 log)
            gc.collect()
            rec.update(info)
            work = os.path.join(OUT, f'_{name}')
            raw = os.path.join(work, name + '_raw.mp4')
            rec.update(render_animation(sc, cam, plant_objects, n, a['fps'], os.path.join(work, 'sky'),
                                        os.path.join(work, 'frames'), raw, log))
            final = os.path.join(OUT, name + '.mp4')
            mux_aac(raw, final)
            rec['file'] = os.path.relpath(final, TN).replace(os.sep, '/')
            rec['probe'] = check(final)
            # two frames kept as stills, to look at beside the video (the first and the last)
            for f in (1, n):
                src = os.path.join(work, 'frames', f'f{f:04d}.png')
                if os.path.exists(src):
                    shutil.copyfile(src, os.path.join(OUT, f'{name}_f{f:04d}.png'))
            shutil.rmtree(work, ignore_errors=True)
        except Exception as e:                                   # noqa: BLE001 - recorded, the next video runs
            traceback.print_exc()
            rec['error'] = f'{type(e).__name__}: {e}'
        rec['seconds'] = round(time.time() - t0, 1)
        try:
            index = json.load(open(idx_path, encoding='utf-8'))
        except (OSError, ValueError):
            index = {}
        index[name] = rec
        with open(idx_path + f'.{os.getpid()}.tmp', 'w', encoding='utf-8') as fh:
            json.dump(index, fh, indent=1, default=str)
        os.replace(idx_path + f'.{os.getpid()}.tmp', idx_path)
        log(f"[video] {name}: {'ok' if (rec.get('probe') or {}).get('ok') else 'NOT OK'} in {rec['seconds']:.0f} s"
            + (f"; {rec.get('error')}" if rec.get('error') else ''))
    os._exit(0)


main()
