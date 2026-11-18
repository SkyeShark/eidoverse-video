"""The surfacing's review videos (SURFACING_DESIGN.md section 6): per recipe a 6 s walk at eye level and an 8 s aerial
orbit, built the way a scene author builds a shot through make_terrain (the surface bake, the per-texel material, the
rocks and the plants, the cameras passed), so the videos show what the stills cannot: shimmer, seams at window edges
and the far hand-off, plants changing their level of detail. One recipe per Blender process, through a GPU slot:

    EIDO_TERRAIN_CACHE_GB=40 bash run_blender.sh blender/tests/terrain/surfacing_judge/video.py --recipe canyon \\
        [--kinds walk,orbit] [--tag t] [--snap <dir>] [--no-plants] [--fps 24] [--samples 16] [--orbit-deg 90]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

walk   the recipe's photographed eye view (WALK; views.json's camera, lens and framing): the camera walks a tenth of
       the way to its aim (10-150 m), 1.7 m over the ground every frame, looking at the aim; the terrain's hero
       levels around the camera's start (the still's terrain), the plants planned along the walk with a standing
       corridor kept clear of crowns (cameras= along the path)
orbit  the recipe's aerial view (ORBIT): the camera carried --orbit-deg around the ground it looks at, at its height
       and distance; the plants planned around that ground; every orbit position passed as a camera (the far
       material on the rings beyond 1.5 D0 of all of them)
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
    dist = math.hypot(tx - ex, ty - ey)
    length = min(max(0.1 * dist, 10.0), 150.0)
    ux, uy = (tx - ex) / dist, (ty - ey) / dist
    n = int(round(WALK_S * a['fps']))
    s = length * np.arange(n) / max(n - 1, 1)
    px, py = ex + ux * s, ey + uy * s
    pz = np.asarray(t.height_at(px, py), np.float64) + dz
    path = np.stack([px, py, pz], 1)
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
                start=[round(ex, 1), round(ey, 1)], plants=(t.info.get('plants') or {}).get('counts'),
                far_material=len(t.obj.data.materials) > 1)
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
    ang = b0 + np.radians(a['orbit_deg']) * np.arange(n) / n
    px, py = tx + rad * np.cos(ang), ty + rad * np.sin(ang)
    if kind == 'ground':                                  # a low view keeps its height over the ground it flies over
        pz = np.asarray(t.height_at(px, py), np.float64) + float(dz)
    else:
        pz = np.full(n, ez)
    path = np.stack([px, py, pz], 1)
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
    info = dict(view=v['name'], terrain=source, build_s=round(build_s, 1), degrees=a['orbit_deg'],
                radius_m=round(rad, 1), plants=(t.info.get('plants') or {}).get('counts'),
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
