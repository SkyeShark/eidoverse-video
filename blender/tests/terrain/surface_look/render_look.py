"""A recipe's look, rendered from the review's matched cameras: the textured frame and, with --layers, the layer map
of the same frame (each layer one flat colour, unlit), so a palette edit is read beside the photograph of the place
and beside the render before it (board.py puts them side by side).

    bash run_blender.sh blender/tests/terrain/surface_look/render_look.py --recipe canyon \\
        [--views a,b] [--tag new] [--layers] [--snap <dir>] [--palettes <file.py>] [--samples 16] [--no-rocks]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The cameras, the terrain and the light are the review's (surfacing/review_views.py: out/review/views_plan.json,
make_terrain at the judge's settings, make_sky daylight with the sun 70 degrees left of the view, 960 x 540,
16 samples, AgX at exposure -0.5), so a frame here lines up with the review's renders and photographs.

    --snap <dir>       the first run of a view saves its terrain there (Terrain.save), later runs load it: the same
                       geometry under every palette, and no terrain cache involved. The palette is always resolved
                       from the code as it is now (a saved terrain's recipe carries the palette it was made with)
    --palettes <file>  another palettes.py to build the material from (the file as it was before an edit, for the
                       'before' frame of a board): loaded in place of eidoblend.terrain.build.palettes
    --layers           also render <view>_<tag>_layers.png: the material's debug 'layers' output under the Standard
                       view transform, the sky transparent, rocks hidden
    --params k=v,...   recipe knobs (real_place: dem=lauterbrunnen)

Writes out/surface_look/<recipe>/<view>_<tag>.png (and _layers.png) and <recipe>_<tag>_record.json.
"""
import copy
import gc
import importlib.util
import json
import math
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
REVIEW = os.path.join(TN, 'out', 'review')
OUT = os.path.join(TN, 'out', 'surface_look')
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
for _p in (TN, os.path.join(TN, 'reference'), BLENDER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    params = {}
    for kv in (opt('--params') or '').split(','):
        if '=' in kv:
            k, v = kv.split('=', 1)
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    return dict(recipe=opt('--recipe'), views=(opt('--views') or ''), tag=opt('--tag', 'new'),
                samples=int(opt('--samples', '16')), rocks='--no-rocks' not in a, layers='--layers' in a,
                snap=opt('--snap') or os.environ.get('EIDO_LOOK_SNAP'), palettes=opt('--palettes'),
                params=params or None, plan=opt('--plan', os.path.join(REVIEW, 'views_plan.json')))


ARGS = args()
if ARGS['palettes']:
    # another palettes.py in place of the package's: registered under the package's name before anything imports it,
    # so the recipes (strata.palette_for), the material and the rock scatter all read this one
    _name = 'eidoblend.terrain.build.palettes'
    _spec = importlib.util.spec_from_file_location(_name, ARGS['palettes'])
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _mod
    _spec.loader.exec_module(_mod)

import bpy  # noqa: E402

import render_references as RR  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

REF = {'fluvial_range': 'san_gabriel_mountains', 'alpine_valley': 'lauterbrunnen', 'stratovolcano': 'mount_fuji',
       'caldera': 'crater_lake', 'cinder_cones': 'sp_crater', 'impact_crater': 'meteor_crater',
       'canyon': 'grand_canyon_toroweap', 'incised_meanders': 'goosenecks', 'mesas_buttes': 'monument_valley',
       'badlands': 'badlands_sd', 'dunes': 'namib_star_dunes', 'tower_karst': 'guilin_karst',
       'sea_cliffs': 'seven_sisters', 'rolling_hills': 'palouse_hills', 'real_place': 'lauterbrunnen', 'meadow': None}
PARAMS = {'real_place': {'dem': 'lauterbrunnen'}}
TEX_EXPOSURE = -0.5
W, H = 960, 540


def recipe_centre(recipe, params):
    R = A._registry.resolve(recipe)
    values, _ = R.resolve(params or None)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    c = dfl.get('centre', (0.0, 0.0))
    return float(c[0]), float(c[1])


def aim_camera(cam, eye, target, frame, lens):
    """Point cam from eye so that target lands at frame (0..1 from the left, from the top): the review's rule."""
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


def palette_now(recipe):
    """The recipe's 'auto' palette from the code as it is now ('auto' for a real place: its palette is a name), and
    the strata a real place adds."""
    if recipe == 'real_place':
        return 'auto'
    return P.get('auto', recipe=A._registry.get(recipe))


def build_terrain(a, recipe, size, params, focus, view_name):
    dress = a['rocks']
    palette = palette_now(recipe)
    snap = os.path.join(a['snap'], f'{recipe}_{view_name}.npz') if a['snap'] else None
    if snap and os.path.exists(snap):
        t = A.Terrain.load(snap, build=True, name=f'{recipe}_look', palette=palette, dress=dress)
        t.info['cache_hit'] = 'snapshot'
        return t
    t = A.make_terrain(recipe, size=size, seed=1, params=params, quality='film', palette=palette, dress=dress,
                       focus=focus, name=f'{recipe}_look')
    if snap:
        os.makedirs(a['snap'], exist_ok=True)
        t.save(snap)
    return t


def layer_pass(sc, t, path):
    """The same frame with the material's debug 'layers' output: flat colours, the Standard view transform, a
    transparent sky, the rocks hidden."""
    pal = t.info.get('palette')
    strata = None
    if t.info.get('place'):
        strata = (P.PLACES.get(t.info['place']) or {}).get('strata')
    S.apply_surface(t.obj, palette=pal, recipe=t.recipe, strata=strata, options=dict(debug='layers'),
                    log=lambda *_a, **_k: None)
    hidden = []
    for ob in sc.objects:
        if ob is not t.obj and ob.type == 'MESH' and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    vt, ex, ft = sc.view_settings.view_transform, sc.view_settings.exposure, sc.render.film_transparent
    look = sc.view_settings.look
    try:
        sc.view_settings.look = 'None'
    except TypeError:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = 0.0
    sc.render.film_transparent = True
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    sc.view_settings.view_transform, sc.view_settings.exposure, sc.render.film_transparent = vt, ex, ft
    try:
        sc.view_settings.look = look
    except TypeError:
        pass
    for ob in hidden:
        ob.hide_render = False


def main():
    a = ARGS
    recipe = a['recipe']
    plan = json.load(open(a['plan'], encoding='utf-8'))[recipe]
    sel = [s for s in a['views'].split(',') if s]
    views = [v for v in plan['views'] if not sel or v['name'] in sel]
    out = os.path.join(OUT, recipe)
    os.makedirs(out, exist_ok=True)
    sky_root = os.path.join(OUT, '_sky', f"{recipe}_{a['tag']}")
    size = refs.load(REF[recipe]).extent if REF[recipe] else None
    params = a['params'] or PARAMS.get(recipe)
    c0 = recipe_centre(recipe, params)
    rec_path = os.path.join(out, f"{recipe}_{a['tag']}_record.json")
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}
    for v in views:
        t0 = time.time()
        name = f"{v['name']}_{a['tag']}"
        try:
            sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE)          # a fresh file each view
            bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
            focus = [(c0[0] + v['cam'][0], c0[1] + v['cam'][1])] if v['focus'] else None
            t = build_terrain(a, recipe, size, params, focus, v['name'])
            tb = time.time() - t0
            cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
            ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
            kind, dz = v['cam_z']
            ground = float(t.height_at(ex, ey))
            ez = ground + float(dz) if kind == 'ground' else float(dz)
            tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
            cam = bpy.data.objects.new('look_cam', bpy.data.cameras.new('look_cam'))
            sc.collection.objects.link(cam)
            sc.camera = cam
            dist = math.dist((ex, ey, ez), (tx, ty, tz))
            if kind == 'ground':
                cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.main.side + 40000.0
            else:
                cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
            heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'])
            bpy.context.view_layer.update()
            d = cam.matrix_world.col[2][:3]
            hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
            cache = os.path.join(sky_root, name)
            os.makedirs(cache, exist_ok=True)
            sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus',
                           cache_dir=cache, quality='film', shadows=False,
                           azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
            sky.bake(frame_start=1, frame_end=1, log=lambda *_a, **_k: None)
            path = os.path.join(out, name + '.png')
            sc.render.filepath = path
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            t_first = time.time() - t1
            grp = next((n.node_tree for n in t.obj.data.materials[0].node_tree.nodes
                        if n.bl_idname == 'ShaderNodeGroup'), None)
            nodes = len(grp.nodes) if grp else None
            t_layers = None
            if a['layers']:
                t1 = time.time()
                layer_pass(sc, t, os.path.join(out, name + '_layers.png'))
                t_layers = time.time() - t1
            shutil.rmtree(cache, ignore_errors=True)
            pal = t.info.get('palette')
            rec[name] = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], ground=round(ground, 1),
                             aim=[round(tx, 1), round(ty, 1), round(tz, 1)], lens=v['lens'],
                             heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), focus=focus,
                             levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'),
                             rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None,
                             palette=(pal.get('name') if isinstance(pal, dict) else pal),
                             layers=([L['name'] for L in pal['layers']] if isinstance(pal, dict) else None),
                             palettes_file=a['palettes'] and os.path.basename(a['palettes']), nodes=nodes,
                             build_s=round(tb, 1), first_render_s=round(t_first, 1),
                             layers_s=None if t_layers is None else round(t_layers, 1),
                             total_s=round(time.time() - t0, 1), caption=v['caption'], photo=v.get('photo'))
            hit = t.info.get('cache_hit')
            print(f"[render_look] {recipe}/{name}: heading {heading:.0f} pitch {pitch:.1f} lens {v['lens']:.0f}; "
                  f"build {tb:.0f} s (cache {hit if isinstance(hit, str) else ('hit' if hit else 'miss')}), "
                  f"{nodes} nodes, first render {t_first:.1f} s"
                  + ('' if t_layers is None else f', layers {t_layers:.1f} s'), flush=True)
            del t
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            rec[name] = dict(error=f'{type(e).__name__}: {e}')
        gc.collect()
        with open(rec_path, 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[render_look] done', flush=True)
    os._exit(0)


main()
