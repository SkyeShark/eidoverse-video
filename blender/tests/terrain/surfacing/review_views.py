"""The judge's views, rendered with the current palettes (one recipe per Blender process, through a GPU slot), so
each textured view lies beside its photograph (the surfacing judge's boards, blender/tests/terrain/surfacing_judge/):

    EIDO_TERRAIN_CACHE_GB=20 bash run_blender.sh blender/tests/terrain/surfacing/review_views.py --recipe canyon \\
        [--views a,b] [--tag v2] [--layers] [--debug layers] [--samples 16] [--no-rocks] [--aniso 16] [--time] \\
        [--plan <views.json>] [--palettes <palettes.py>]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The cameras are the judge's (surfacing_judge/views.json: the review's matched spot, aim point and lens of each
photograph, the cameras that faced walls on today's terrain moved, an establishing aerial and a low oblique added;
--plan takes another file of that shape, such as the review's own out/review/views_plan.json), built and lit as
out/review/scripts/review_render.py does: make_terrain at the judge's settings (the
reference's extent, seed 1, film quality, hero levels on the camera when it stands in the main tile), the recipe's
palette ('auto'; --debug layers: each layer one flat colour, unlit), its rocks, make_sky daylight with the sun 70
degrees left of the view, 960 x 540, 16 samples, exposure -0.5. Writes out/surfacing/review/<recipe>/<view>[_<tag>].png
and <recipe>[_<tag>]_record.json (camera, build and render seconds, the material's node count). Set
EIDO_TERRAIN_CACHE_GB above the terrain cache's size (16 GB on 11-12) so a cache miss does not prune the review's
cached terrains.

    --snap <dir>   material iterations: the first run of a view saves its built terrain there (Terrain.save,
                   <dir>/<recipe>_<view>.npz, about 0.5 GB), later runs load it (Terrain.load) and only rebuild the
                   object with the current palette and render: a minute a view instead of a rebuild whenever another
                   package's solver edit changes the terrain cache's code hash. The geometry is that snapshot's.
    --once         render each view once (no second, timing frame)
    --layers       after the textured frame, the same frame as a layer map: <view>[_<tag>]_layers.png, the palette's
                   debug='layers' material (each layer one flat colour mixed by its weight, unlit) with lakes and the
                   sea black, rocks and plants hidden, no world, the Standard view transform, a transparent film,
                   8-bit RGBA. The judge decodes it into the material's own weights per pixel
                   (surfacing_judge/layers.decode_layer_map): the one-material share and within-layer variation of the
                   frame, and the board's layer-map column
    --palettes <f> the palettes module read from this file instead of the checkout's (a state before a round:
                   `git show <commit>:blender/eidoblend/terrain/build/palettes.py > <file>`, outside the repo); the
                   record names the file
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
REVIEW = os.path.join(TN, 'out', 'review')
OUT = os.path.join(TN, 'out', 'surfacing', 'review')
JUDGE_VIEWS = os.path.join(TN, 'surfacing_judge', 'views.json')
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, os.path.normpath(os.path.join(TN, '..', '..')))


def _install_palettes():
    """--palettes <file>: that file becomes eidoblend.terrain.build.palettes before anything imports the checkout's
    (build/ is a namespace package, so importing it runs no module)."""
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if '--palettes' not in a:
        return None
    import importlib.util
    import eidoblend.terrain.build as build
    path = os.path.abspath(a[a.index('--palettes') + 1])
    spec = importlib.util.spec_from_file_location('eidoblend.terrain.build.palettes', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    build.palettes = mod
    print(f'[review_views] palettes from {path}', flush=True)
    return path


PALETTES_FILE = _install_palettes()

import bpy  # noqa: E402

import render_references as RR  # noqa: E402
from judge import refs  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402

REF = {'fluvial_range': 'san_gabriel_mountains', 'alpine_valley': 'lauterbrunnen', 'stratovolcano': 'mount_fuji',
       'caldera': 'crater_lake', 'cinder_cones': 'sp_crater', 'impact_crater': 'meteor_crater',
       'canyon': 'grand_canyon_toroweap', 'incised_meanders': 'goosenecks', 'mesas_buttes': 'monument_valley',
       'badlands': 'badlands_sd', 'dunes': 'namib_star_dunes', 'tower_karst': 'guilin_karst',
       'sea_cliffs': 'seven_sisters', 'rolling_hills': 'palouse_hills', 'real_place': 'lauterbrunnen', 'meadow': None}
PARAMS = {'real_place': {'dem': 'lauterbrunnen'}}
TEX_EXPOSURE = -0.5
W, H = 960, 540


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(recipe=opt('--recipe'), views=(opt('--views') or ''), tag=opt('--tag', ''), debug=opt('--debug'),
                samples=int(opt('--samples', '16')), rocks='--no-rocks' not in a, aniso=int(opt('--aniso', '16')),
                time='--time' in a, snap=opt('--snap'), once='--once' in a, layers='--layers' in a,
                plan=opt('--plan', JUDGE_VIEWS if os.path.exists(JUDGE_VIEWS)
                         else os.path.join(REVIEW, 'views_plan.json')))


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


def render(sc, cam, path, sky_root, once=False):
    bpy.context.view_layer.update()
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    cache = os.path.join(sky_root, os.path.splitext(os.path.basename(path))[0])
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    t_first = time.time() - t0
    if once:
        shutil.rmtree(cache, ignore_errors=True)
        return t_first, None
    t0 = time.time()
    bpy.ops.render.render(write_still=False)           # the second frame: the material compiled
    shutil.rmtree(cache, ignore_errors=True)
    return t_first, time.time() - t0


def layer_pass(sc, t, path):
    """The layer map of the frame just rendered (--layers in the module doc). Returns the render seconds."""
    from eidoblend.terrain.build import palettes as Pal
    from eidoblend.terrain.build import surfacing as S
    info = t.info
    strata = (Pal.PLACES.get(info['place']) or {}).get('strata') if info.get('place') else None
    S.apply_surface(t.obj, palette=info.get('palette') or 'auto', recipe=t.recipe, strata=strata,
                    options={'debug': 'layers'}, log=None)
    black = bpy.data.materials.new('judge_water_black')
    black.use_nodes = True
    nt = black.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    water = [o for o in list(t.water.get('lakes') or []) + [t.water.get('sea')] if o is not None]
    for o in water:
        o.data.materials.clear()
        o.data.materials.append(black)
    keep = {t.obj.name} | {o.name for o in water}
    for o in sc.objects:
        if o.type != 'CAMERA' and o.name not in keep:
            o.hide_render = True                           # rocks, plants, clouds, the sun
    world = bpy.data.worlds.new('judge_black')
    world.color = (0.0, 0.0, 0.0)
    sc.world = world
    vs = sc.view_settings
    vs.view_transform = 'Standard'
    vs.look = 'None'
    vs.exposure = 0.0
    vs.gamma = 1.0
    sc.render.film_transparent = True
    sc.render.use_compositing = False
    sc.render.use_sequencer = False
    im = sc.render.image_settings
    im.file_format = 'PNG'
    im.color_mode = 'RGBA'
    im.color_depth = '8'                               # the decode is exact to 0.03 at 8 bits (test_measures)
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t0


def build_terrain(a, recipe, size, params, palette, focus, view_name):
    """make_terrain at the judge's settings, or with --snap the saved terrain of this view (made and saved on its
    first run), rebuilt with the current palette."""
    dress = a['rocks'] and not a['debug']
    snap = os.path.join(a['snap'], f'{recipe}_{view_name}.npz') if a['snap'] else None
    if snap and os.path.exists(snap):
        t = A.Terrain.load(snap, build=True, name=f'{recipe}_review', palette=palette, dress=dress)
        t.info['cache_hit'] = 'snapshot'
        return t
    t = A.make_terrain(recipe, size=size, seed=1, params=params, quality='film', palette=palette, dress=dress,
                       focus=focus, name=f'{recipe}_review')
    if snap:
        os.makedirs(a['snap'], exist_ok=True)
        t.save(snap)
    return t


def main():
    a = args()
    recipe = a['recipe']
    plan = json.load(open(a['plan'], encoding='utf-8'))[recipe]
    sel = [s for s in a['views'].split(',') if s]
    views = [v for v in plan['views'] if not sel or v['name'] in sel]
    out = os.path.join(OUT, recipe)
    os.makedirs(out, exist_ok=True)
    sky_root = os.path.join(OUT, '_sky', recipe)
    ref = plan['reference'] if 'reference' in plan else REF[recipe]       # the judge's views.json names both
    size = refs.load(ref).extent if ref else None
    params = plan['params'] if 'params' in plan else PARAMS.get(recipe)
    c0 = recipe_centre(recipe, params)
    tag = f"_{a['tag']}" if a['tag'] else ''
    rec_path = os.path.join(out, f'{recipe}{tag}_record.json')
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}
    palette = 'auto'
    if a['debug']:
        palette = P.get('auto', recipe=A._registry.resolve(recipe))
        palette['options']['debug'] = a['debug']
    for v in views:
        t0 = time.time()
        name = v['name'] + (f"_debug_{a['debug']}" if a['debug'] else '') + tag
        try:
            sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE)          # a fresh file each view
            # EEVEE's anisotropic filtering is a preference, 2x after read_factory_settings: ground seen at a grazing
            # angle past the 'Auto' handover (9 m) smears along the view at 2x; --aniso sets it (default 16)
            bpy.context.preferences.system.anisotropic_filter = f"FILTER_{a['aniso']}"
            focus = [(c0[0] + v['cam'][0], c0[1] + v['cam'][1])] if v['focus'] else None
            t = build_terrain(a, recipe, size, params, palette, focus, v['name'])
            tb = time.time() - t0
            cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
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
            path = os.path.join(out, name + '.png')
            t_first, t_second = render(sc, cam, path, sky_root, once=a['once'])
            grp = next((n.node_tree for n in t.obj.data.materials[0].node_tree.nodes
                        if n.bl_idname == 'ShaderNodeGroup'), None)
            timing = {}
            if a['time']:
                # the material's own cost: the same frame in grey clay back to back (other jobs share the GPU, so
                # the difference survives better than either number), and the textured frame at 2x anisotropy
                from eidoblend.terrain.build import surfacing as S
                mat = t.obj.data.materials[0]
                for label, aniso, clay in (('textured_aniso2', 2, False), ('clay', a['aniso'], True),
                                           ('textured', a['aniso'], False)):
                    bpy.context.preferences.system.anisotropic_filter = f'FILTER_{aniso}'
                    t.obj.data.materials[0] = S.clay_material() if clay else mat
                    bpy.ops.render.render(write_still=False)              # compile
                    best = 1e9
                    for _ in range(2):
                        t1 = time.time()
                        bpy.ops.render.render(write_still=False)
                        best = min(best, time.time() - t1)
                    timing[label + '_s'] = round(best, 2)
                timing['material_s'] = round(timing['textured_s'] - timing['clay_s'], 2)
                print(f"[review_views] {recipe}/{name}: timing {timing}", flush=True)
            rec[name] = dict(camera=[round(ex, 1), round(ey, 1), round(ez, 1)], ground=round(ground, 1),
                             aim=[round(tx, 1), round(ty, 1), round(tz, 1)], lens=v['lens'],
                             heading_deg=round(heading, 1), pitch_deg=round(pitch, 2), focus=focus,
                             levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'),
                             rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None,
                             palette=t.obj.data.materials[0].get('eido_palette'),
                             nodes=(len(grp.nodes) if grp else None), anisotropic_filter=a['aniso'], timing=timing,
                             build_s=round(tb, 1),
                             first_render_s=round(t_first, 1),
                             second_render_s=None if t_second is None else round(t_second, 2),
                             total_s=round(time.time() - t0, 1), caption=v['caption'], photo=v.get('photo'),
                             frame=v.get('frame'), plan=os.path.basename(a['plan']), palettes_file=PALETTES_FILE)
            if a['layers'] and not a['debug']:
                lp = os.path.join(out, name + '_layers.png')
                rec[name]['layers'] = os.path.basename(lp)
                rec[name]['layers_render_s'] = round(layer_pass(sc, t, lp), 1)
            hit = t.info.get('cache_hit')
            print(f"[review_views] {recipe}/{name}: heading {heading:.0f} pitch {pitch:.1f} lens {v['lens']:.0f}; "
                  f"build {tb:.0f} s (cache {hit if isinstance(hit, str) else ('hit' if hit else 'miss')}), first "
                  f"render {t_first:.1f} s" + ('' if t_second is None else f", second {t_second:.2f} s"), flush=True)
            del t
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            rec[name] = dict(error=f'{type(e).__name__}: {e}')
        gc.collect()
        with open(rec_path, 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[review_views] done', flush=True)
    os._exit(0)


main()
