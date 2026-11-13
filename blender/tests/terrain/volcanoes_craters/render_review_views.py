"""The independent review's views of package 9's recipes, re-rendered after the fixes (Blender 5.2, one recipe per
process, through a GPU slot), into out/volcanoes_craters/review_views/<tag>/<recipe>/:

    bash run_blender.sh <this> --recipe impact_crater --tag after [--views a,b] [--clay a,b|all] [--samples 16]

The same cameras, settings and light as the reviewer's renders (out/review/views_plan.json; the reviewer's
scripts/review_render.py): make_terrain at the judge's settings (the place's extent, seed 1, film quality, the
recipe's defaults), hero levels on the camera when it stands in the main tile, the recipe's palette and rocks
('auto'; --clay again in grey clay), the camera at its matched spot aimed so the aim point lands where the photograph
has it, make_sky daylight with the sun 70 degrees left of the view, 960 x 540, 16 samples. Writes
<view>[_clay].png and render.json (camera, levels, build seconds). photo_sheets_after.py sets them beside the
photographs and the reviewer's renders."""
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

import render_references as RR  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

REF = {'stratovolcano': 'mount_fuji', 'caldera': 'crater_lake', 'cinder_cones': 'sp_crater',
       'impact_crater': 'meteor_crater'}
PLAN = os.path.join(TN, 'out', 'review', 'views_plan.json')
OUT = os.path.join(TN, 'out', 'volcanoes_craters', 'review_views')
TEX_EXPOSURE = -0.5
W, H = 960, 540


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(recipe=opt('--recipe'), views=(opt('--views') or ''), clay=(opt('--clay') or ''),
                 samples=int(opt('--samples', '16')), tag=opt('--tag', 'after'))


def aim_camera(cam, eye, target, frame, lens):
    """Point cam from eye so that target lands at frame (0..1 from the left, from the top) (the reviewer's rule)."""
    cam.data.lens = lens
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
    yaw_t = math.atan2(dy, dx)
    pitch_t = math.atan2(dz, math.hypot(dx, dy))
    hf, vf = 36.0, 36.0 * H / W
    u = (frame[0] - 0.5) * hf / lens
    v = (0.5 - frame[1]) * vf / lens
    yaw = yaw_t + math.atan(u)
    pitch = pitch_t - math.atan(v)
    d = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    RR.place_camera(cam, eye, (eye[0] + 1000.0 * d[0], eye[1] + 1000.0 * d[1], eye[2] + 1000.0 * d[2]))
    return (90.0 - math.degrees(yaw)) % 360.0, math.degrees(pitch)


def render(sc, cam, path, sky_root):
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


def main():
    a = args()
    recipe = a['recipe']
    plan = json.load(open(PLAN, encoding='utf-8'))[recipe]
    sel = [s for s in a['views'].split(',') if s]
    clay = [s for s in a['clay'].split(',') if s]
    views = [v for v in plan['views'] if not sel or v['name'] in sel]
    out = os.path.join(OUT, a['tag'], recipe)
    os.makedirs(out, exist_ok=True)
    sky_root = os.path.join(OUT, '_sky', recipe)
    size = refs.load(REF[recipe]).extent
    rec_path = os.path.join(out, 'render.json')
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}
    for v in views:
        for palette, suffix in [('auto', '')] + ([(None, '_clay')] if (v['name'] in clay or 'all' in clay) else []):
            t0 = time.time()
            name = v['name'] + suffix
            try:
                sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE if palette else RR.EXPOSURE)
                focus = [(v['cam'][0], v['cam'][1])] if v['focus'] else None
                t = A.make_terrain(recipe, size=size, seed=1, quality='film', palette=palette,
                                   dress=palette is not None, focus=focus, name=f'{recipe}_after')
                tb = time.time() - t0
                cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
                ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
                kind, dz = v['cam_z']
                ground = float(t.height_at(ex, ey))
                ez = ground + float(dz) if kind == 'ground' else float(dz)
                tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
                cam = bpy.data.objects.new('after_cam', bpy.data.cameras.new('after_cam'))
                sc.collection.objects.link(cam)
                sc.camera = cam
                dist = math.dist((ex, ey, ez), (tx, ty, tz))
                if kind == 'ground':
                    cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.main.side + 40000.0
                else:
                    cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
                heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'])
                path = os.path.join(out, name + '.png')
                render(sc, cam, path, sky_root)
                rec[name] = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], ground=round(ground, 1),
                                 aim=[round(tx, 1), round(ty, 1), round(tz, 1)], lens=v['lens'],
                                 heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), palette=palette,
                                 focus=focus, levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'),
                                 build_s=round(tb, 1), total_s=round(time.time() - t0, 1), caption=v['caption'],
                                 photo=v.get('photo'))
                print(f"[after] {recipe}/{name}: heading {heading:.0f} pitch {pitch:.1f} ground {ground:.0f}; "
                      f"build {tb:.0f} s, total {time.time() - t0:.0f} s", flush=True)
                del t
            except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
                traceback.print_exc()
                rec[name] = dict(error=f'{type(e).__name__}: {e}')
            gc.collect()
            with open(rec_path, 'w', encoding='utf-8') as fh:
                json.dump(rec, fh, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[after] done', flush=True)
    os._exit(0)


main()
