"""Render photo-matched views TEXTURED: each view's terrain built by make_terrain with its palette and rocks (the
recipe at the reference's extent, or real_place on the real elevation data), hero levels on the camera when it stands
on the main tile, under make_sky daylight with the review's rig (the sun 70 degrees left of the view at 15:30,
exposure -0.5, AgX), 960 x 540.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/terrain/glacial/render_textured.py --job <job.json> [--samples 16]

job.json: {"out_dir": ..., "views": [{"name", "recipe" ('alpine_valley' | 'real_place'), "seed" (1), "params" ({}),
"size" (m; default the recipe's at the judge's extent), "camera": {"x", "y" (metres from the main tile's centre),
"agl" (the camera's height over the ground there, m), "heading_deg" (compass), "pitch_deg", "lens_mm" (36 mm frame)},
"focus" (true: hero levels on the camera), "clay" (true: palette None, the reference rig's grey clay)}].
photo_views.py --textured writes such a job from the photographs' cameras. Writes <out_dir>/<name>.png and
<out_dir>/<job>_record.json (per view: the camera, the ground, the levels, build and render seconds).
"""
import gc
import json
import math
import os
import shutil
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))

import bpy  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402

W, H = 960, 540
TEX_EXPOSURE = -0.5                 # the review's textured exposure (clay: the rig's +0.5)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[a.index('--job') + 1], int(a[a.index('--samples') + 1]) if '--samples' in a else 16


def render_one(v, out_dir, sky_root, samples):
    t0 = time.time()
    clay = bool(v.get('clay'))
    sc = RR.new_scene((W, H), samples, RR.EXPOSURE if clay else TEX_EXPOSURE)
    c = v['camera']
    recipe = v.get('recipe', 'alpine_valley')
    focus = [(float(c['x']), float(c['y']))] if v.get('focus') else None
    t = A.make_terrain(recipe, size=v.get('size'), seed=int(v.get('seed', 1)), params=v.get('params') or None,
                       quality='film', palette=None if clay else 'auto', dress=not clay, focus=focus,
                       name=f"{v['name']}_terrain")
    tb = time.time() - t0
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = cx + float(c['x']), cy + float(c['y'])
    ground = float(t.height_at(ex, ey))
    ez = ground + float(c['agl'])
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    hd, pt = math.radians(float(c['heading_deg'])), math.radians(float(c['pitch_deg']))
    d = (math.sin(hd) * math.cos(pt), math.cos(hd) * math.cos(pt), math.sin(pt))
    cam.data.lens = float(c['lens_mm'])
    cam.data.sensor_width = 36.0
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.clip_start = 0.1 if float(c['agl']) < 10.0 else 1.0
    cam.data.clip_end = 4.0 * t.main.side + 40000.0
    eye = (ex, ey, ez)
    RR.place_camera(cam, eye, (ex + 1000.0 * d[0], ey + 1000.0 * d[1], ez + 1000.0 * d[2]))
    sun_xy = (math.sin(hd - math.radians(RR.SUN_LEFT_DEG)), math.cos(hd - math.radians(RR.SUN_LEFT_DEG)))
    cache = os.path.join(sky_root, v['name'])
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = os.path.join(out_dir, v['name'] + '.png')
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    rec = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], ground=round(ground, 1), heading_deg=c['heading_deg'],
               pitch_deg=c['pitch_deg'], lens_mm=c['lens_mm'], levels=[str(lv) for lv in t.levels],
               rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None, build_s=round(tb, 1),
               total_s=round(time.time() - t0, 1), clay=clay, recipe=recipe)
    print(f"[glacial.textured] {v['name']}: ground {ground:.0f} m, camera z {ez:.0f} m, build {tb:.0f} s, total "
          f"{time.time() - t0:.0f} s", flush=True)
    return rec


def main():
    job_path, samples = args()
    job = json.load(open(job_path, encoding='utf-8'))
    out_dir = job['out_dir']
    os.makedirs(out_dir, exist_ok=True)
    sky_root = tempfile.mkdtemp(prefix='glacial_tex_sky_')
    rec_path = os.path.splitext(job_path)[0] + '_record.json'
    rec = {}
    for v in job['views']:
        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            rec[v['name']] = render_one(v, out_dir, sky_root, samples)
        except Exception as e:                                         # noqa: BLE001 - the job goes on
            traceback.print_exc()
            rec[v['name']] = dict(error=f'{type(e).__name__}: {e}')
        gc.collect()
        with open(rec_path, 'w', encoding='utf-8') as f:
            json.dump(rec, f, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[glacial.textured] done', flush=True)
    os._exit(0)


main()
