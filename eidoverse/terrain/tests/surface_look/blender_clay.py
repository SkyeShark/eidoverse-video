"""A probe of the look package (PORT_PLAN.md 8.2 row P18): judge views in grey clay, rendered by the Blender edition
with the final check's rig, so the light of the two editions' renderers can be compared apart from the surfacing.
views.mjs --clay renders the port's twin of each (the same terrain, camera and light, the ground in clay, no plants or
rocks); a difference between the two clay frames is the renderer's light (the sun's shadows, the sky's light and its
occlusion), and a difference between the two textured frames that the clay frames do not show is the surfacing's.

    EIDO_BLENDER_EDITION=<a checkout or an export of the blender branch> bash <its run_blender.sh> \\
        eidoverse/terrain/tests/surface_look/blender_clay.py -- --views <recipe/view,...> --terrains <plan.json>
        [--plan <views.json>] [--samples 16]
    (a Blender job, behind $EIDO_GPU_WRAP like every Blender run)

The rig is surfacing/review_views.py's at 2cf8c84, transcribed: render_references.new_scene (AgX, its look, the
textured exposure), view_camera and shots.aim_camera, light() (make_sky's earth at 15:30 with cumulus, the sun 70
degrees left of the view), 960 x 540; the terrain is the view's saved one (the port's plan.json names it, as the
port rendered it), built with palette=None (surfacing.clay_material: albedo 0.18, roughness 0.9, no specular), no
surface bake, no rocks, no plants. Writes tests/out/surface_look/clay/<recipe>_<view>_blender.png.
"""
import json
import math
import os
import shutil
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TESTS, 'parity'))
import _blender as B  # noqa: E402

import bpy  # noqa: E402

OUT = os.path.join(TESTS, 'out', 'surface_look', 'clay')


def main():
    a = B.script_args()

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    root = B.import_blender_terrain()
    tn = os.path.join(root, 'blender', 'tests', 'terrain')
    for p in (os.path.join(tn, 'reference'), tn):
        if p not in sys.path:
            sys.path.insert(0, p)
    import render_references as RR
    from surfacing_judge import shots as SH
    from eidoblend.sky import make_sky
    from eidoblend.terrain import api as A
    with open(opt('--plan', os.path.join(tn, 'surfacing_judge', 'views.json')), encoding='utf-8') as f:
        plan = json.load(f)
    with open(opt('--terrains'), encoding='utf-8') as f:
        terrains = json.load(f)['views']
    samples = int(opt('--samples', '16'))
    os.makedirs(OUT, exist_ok=True)
    for item in (opt('--views') or '').split(','):
        if not item:
            continue
        recipe, view = item.split('/', 1)
        try:
            v = next(x for x in plan[recipe]['views'] if x['name'] == view)
            sc = RR.new_scene((SH.W, SH.H), samples, SH.EXPOSURE)
            t = A.Terrain.load(terrains[item]['terrain'], build=False)
            t.build(f'{recipe}_clay', palette=None, dress=False, surface=None, plants=None, mask_attributes=False,
                    log=lambda *_: None)
            # review_views.view_camera
            cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
            ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
            kind, dz = v['cam_z']
            ground = float(t.height_at(ex, ey))
            ez = ground + float(dz) if kind == 'ground' else float(dz)
            tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
            cam = bpy.data.objects.new('clay_cam', bpy.data.cameras.new('clay_cam'))
            sc.collection.objects.link(cam)
            dist = math.dist((ex, ey, ez), (tx, ty, tz))
            if kind == 'ground':
                cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.levels[0].side + 40000.0
            else:
                cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
            sc.camera = cam
            SH.aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'])
            # review_views.light
            bpy.context.view_layer.update()
            cache = os.path.join(OUT, '_sky')
            os.makedirs(cache, exist_ok=True)
            sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                           quality='film', shadows=False, sun=None, azimuth=RR.sun_azimuth_option(SH.sun_xy(cam)))
            sky.bake(frame_start=1, frame_end=1, log=lambda *_: None)
            sc.render.filepath = os.path.join(OUT, f'{recipe}_{view}_blender.png')
            bpy.ops.render.render(write_still=True)
            shutil.rmtree(cache, ignore_errors=True)
            print(f'[blender_clay] {item}: camera ({ex:.1f}, {ey:.1f}, {ez:.1f}) -> {sc.render.filepath}', flush=True)
        except Exception:                                # noqa: BLE001 - reported, the run goes on
            traceback.print_exc()
            print(f'[blender_clay] {item}: failed', flush=True)


try:
    main()
except Exception:                                        # noqa: BLE001
    traceback.print_exc()
    os._exit(1)
os._exit(0)
