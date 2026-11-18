"""The judge's views, rendered through make_terrain's own path (one recipe per Blender process, through a GPU slot), so
each textured view lies beside its photograph (the surfacing judge's boards, blender/tests/terrain/surfacing_judge/):

    EIDO_TERRAIN_CACHE_GB=40 bash run_blender.sh blender/tests/terrain/surfacing/review_views.py --recipe canyon \\
        [--views a,b] [--tag v2] [--plants] [--layers] [--snap <dir>] [--surface none] [--debug layers]
        [--samples 16] [--no-rocks] [--aniso 16] [--time] [--once] [--plan <views.json>] [--palettes <palettes.py>]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The cameras are the judge's (surfacing_judge/views.json: the review's matched spot, aim point and lens of each
photograph, the cameras that faced walls on today's terrain moved, an establishing aerial and a low oblique added;
--plan takes another file of that shape, such as the review's own out/review/views_plan.json). Each terrain is made
as a scene author makes a shot: the terrain at the judge's settings (the reference's extent, seed 1, film quality,
hero levels on the camera when it stands in the main tile: api.generate, or a saved one), the cameras placed on it,
then Terrain.build with the recipe's palette as the code has it now, its rocks, the surface bake (surface='auto'),
the cameras passed (cameras=: the far material on the rings beyond 1.5 D0 of them, plants' crowns kept off them)
and the mask attributes left off the mesh (the per-texel material reads none); make_sky daylight with the sun 70
degrees left of the view, 960 x 540, 16 samples, exposure -0.5. The views without a focus share one terrain (the
judge's saved one, or one generated without a focus): it is built once for all of them, their plants planned along
the ground they look at, and each focused view has its own. Writes out/surfacing/review/<recipe>/<view>[_<tag>].png
and <recipe>[_<tag>]_record.json (camera, the terrain's source, build, surface, plants and render seconds, the
material's samplers and far hand-off). Set EIDO_TERRAIN_CACHE_GB above the terrain cache's size so a cache miss
does not prune the cached terrains.

    --plants       the plant layer as make_terrain plants it (plants=): an eye view's plants around its camera, an
                   aerial's around the ground it looks at (the views sharing a terrain: along those points); a view
                   with vista_m (views.json) keeps the first metres of its sight line clear of crowns (discs every 5
                   m, 2 m across). The sun binds the SeedThree plants (Terrain.bind_sun) once the sky is made
    --snap <dir>   saved terrains (Terrain.save, <dir>/<recipe>_<view>[_j].npz, about 0.5 GB each) are loaded instead of
                   generated when one's focus is the view's camera, and the views without a focus take the judge's
                   saved terrain (out/surfacing_judge/terrains/<recipe>.npz); a terrain generated here is saved there.
                   The geometry is that snapshot's; the palette is always the code's as it is now
    --surface none the material without the surface bake (the mask attributes on the mesh, the forest's fallback): the
                   path a terrain made before the bake took, for a 'before' state (with --palettes)
    --once         render each view once (no second, timing frame)
    --layers       after a terrain's textured frames, the same frames as layer maps: <view>[_<tag>]_layers.png, the
                   palette's debug='layers' material on the same data (each layer one flat colour mixed by its weight,
                   unlit) with lakes and the sea black, rocks and plants hidden, no world, the Standard view transform,
                   a transparent film, 8-bit RGBA. The judge decodes it into the material's own weights per pixel
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
from surfacing_judge import shots as SH  # noqa: E402

REF = {'fluvial_range': 'san_gabriel_mountains', 'alpine_valley': 'lauterbrunnen', 'stratovolcano': 'mount_fuji',
       'caldera': 'crater_lake', 'cinder_cones': 'sp_crater', 'impact_crater': 'meteor_crater',
       'canyon': 'grand_canyon_toroweap', 'incised_meanders': 'goosenecks', 'mesas_buttes': 'monument_valley',
       'badlands': 'badlands_sd', 'dunes': 'namib_star_dunes', 'tower_karst': 'guilin_karst',
       'sea_cliffs': 'seven_sisters', 'rolling_hills': 'palouse_hills', 'real_place': 'lauterbrunnen', 'meadow': None}
TEX_EXPOSURE = SH.EXPOSURE
W, H = SH.W, SH.H


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(recipe=opt('--recipe'), views=(opt('--views') or ''), tag=opt('--tag', ''), debug=opt('--debug'),
                samples=int(opt('--samples', '16')), rocks='--no-rocks' not in a, aniso=int(opt('--aniso', '16')),
                time='--time' in a, snap=opt('--snap'), once='--once' in a, layers='--layers' in a,
                plants='--plants' in a, surface=(None if opt('--surface') == 'none' else 'auto'),
                plan=opt('--plan', JUDGE_VIEWS if os.path.exists(JUDGE_VIEWS)
                         else os.path.join(REVIEW, 'views_plan.json')))


quiet = SH.quiet


def light(sc, cam, cache, sun=None):
    """make_sky daylight with the sun RR.SUN_LEFT_DEG left of the view (a later view of the scene reuses the lamp)."""
    bpy.context.view_layer.update()
    os.makedirs(cache, exist_ok=True)
    try:
        sun = sun if (sun is not None and sun.name in sc.objects) else None
    except ReferenceError:
        sun = None
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, sun=sun, azimuth=RR.sun_azimuth_option(SH.sun_xy(cam)))
    sky.bake(frame_start=1, frame_end=1, log=quiet)
    return sky


def render(sc, path, once=False):
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    t_first = time.time() - t0
    if once:
        return t_first, None
    t0 = time.time()
    bpy.ops.render.render(write_still=False)           # the second frame: the material compiled
    return t_first, time.time() - t0


def layer_material(t, palette):
    """The palette's debug='layers' material on the terrain's own data (each layer one flat colour by its weight),
    built while the data is held, for the layer pass after the frames."""
    from eidoblend.terrain.build import surfacing as S
    info = t.info
    strata = (P.PLACES.get(info['place']) or {}).get('strata') if info.get('place') else None
    consts = S.terrain_constants(t.obj)
    return S.surface_material(palette, recipe=t.recipe, strata=strata, options={'debug': 'layers'},
                              name=t.obj.name + '_layers', log=None, constants=consts, data=t.surface)


def image_users(mats):
    """[(Image Texture node, image name)] of materials, their node groups included."""
    out, seen = [], set()

    def walk(nt):
        if nt is None or nt.name in seen:
            return
        seen.add(nt.name)
        for nd in nt.nodes:
            if nd.bl_idname == 'ShaderNodeTexImage' and nd.image is not None:
                out.append((nd, nd.image.name))
            elif nd.bl_idname == 'ShaderNodeGroup':
                walk(nd.node_tree)
    for m in mats:
        if m is not None and m.use_nodes:
            walk(m.node_tree)
    return out


def relink(users):
    """Point every recorded image node at the image of its recorded name again: a second material of the same
    palette replaces the strata column's images by name (surfacing.strata_image), which empties the first
    material's nodes; the new images hold the same column."""
    n = 0
    for nd, name in users:
        if nd.image is None or nd.image.name != name:
            img = bpy.data.images.get(name)
            if img is not None:
                nd.image = img
                n += 1
    return n


def layer_scene(sc, obj, water, mat):
    """The layer pass's scene (--layers in the module doc): the layer material on every ring, water black, every
    other object hidden, a black world, the Standard view transform, 8-bit RGBA."""
    import numpy as np
    me = obj.data
    me.materials.clear()
    me.materials.append(mat)
    me.polygons.foreach_set('material_index', np.zeros(len(me.polygons), np.int32))
    me.update()
    black = bpy.data.materials.new('judge_water_black')
    black.use_nodes = True
    nt = black.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    for o in water:
        o.data.materials.clear()
        o.data.materials.append(black)
    keep = {obj.name} | {o.name for o in water}
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


def view_camera(sc, t, v):
    """The view's camera on terrain t: (camera object, eye, aim, ground z)."""
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    kind, dz = v['cam_z']
    ground = float(t.height_at(ex, ey))
    ez = ground + float(dz) if kind == 'ground' else float(dz)
    tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
    nm = 'review_cam_' + v['name']
    cam = bpy.data.objects.get(nm) or bpy.data.objects.new(nm, bpy.data.cameras.new(nm))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    dist = math.dist((ex, ey, ez), (tx, ty, tz))
    if kind == 'ground':
        cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.levels[0].side + 40000.0
    else:
        cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
    return cam, (ex, ey, ez), (tx, ty, tz), ground


def group_plants(vs, eyes, aims):
    """make_terrain's plants= for the views of one terrain: around each eye view's camera and each aerial's aim
    (several views: along those points), with every view's vista kept clear of crowns."""
    foci, excl = [], []
    for v, e, m in zip(vs, eyes, aims):
        s = SH.plant_spec(v, e, m)
        foci.append(s['focus'])
        excl += s.get('exclude') or []
    spec = dict(focus=foci[0] if len(foci) == 1 else foci)
    if excl:
        spec['exclude'] = excl
    return spec


def render_group(a, recipe, size, params, c0, vs, out, sky_root, tag, rec):
    """One terrain and its views: the textured frames, then (with --layers) the layer maps."""
    t0 = time.time()
    palette = SH.palette_now(recipe)
    if a['debug']:
        palette = P.get('auto', recipe=A._registry.resolve(recipe))
        palette['options']['debug'] = a['debug']
    sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE)          # a fresh file per terrain
    # EEVEE's anisotropic filtering is a preference, 2x after read_factory_settings; the build raises it to 16x for
    # the surface bake's atlases, and --aniso sets it for every image the frames draw
    bpy.context.preferences.system.anisotropic_filter = f"FILTER_{a['aniso']}"
    v0 = vs[0]
    focus = [(c0[0] + v0['cam'][0], c0[1] + v0['cam'][1])] if v0['focus'] else None
    t, source = SH.terrain_for(recipe, v0['name'], size, params, focus, a['snap'])
    tg = time.time() - t0
    shots = [(v,) + view_camera(sc, t, v) for v in vs]
    eyes = [s[2] for s in shots]
    aims = [s[3] for s in shots]
    spec = group_plants(vs, eyes, aims) if a['plants'] and not a['debug'] else None
    tb = time.time()
    t.build(f'{recipe}_review', palette=palette, dress=a['rocks'] and not a['debug'], surface=a['surface'],
            plants=spec, cameras=eyes, mask_attributes=a['surface'] is None, log=quiet)
    tb = time.time() - tb
    if a['aniso'] != 16:
        bpy.context.preferences.system.anisotropic_filter = f"FILTER_{a['aniso']}"
    mat = t.obj.data.materials[0]
    grp = next((n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup'), None)
    secs = t.info.get('seconds', {})
    surf = t.info.get('surface') or {}
    common = dict(levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'), terrain=source,
                  rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None,
                  palette=mat.get('eido_palette'), nodes=(len(grp.nodes) if grp else None),
                  samplers=mat.get('eido_samplers'), far_m=mat.get('eido_far_m'),
                  far_material=len(t.obj.data.materials) > 1, anisotropic_filter=a['aniso'],
                  surface=dict(key=str(surf.get('key', ''))[:12], cache_hit=surf.get('cache_hit'),
                               cover=surf.get('cover'), palette_bake=surf.get('palette_bake')) if surf else None,
                  plants=(t.info.get('plants') or {}).get('counts'), plant_focus=(spec or {}).get('focus'),
                  views_built_together=[v['name'] for v in vs],
                  seconds={k: secs.get(k) for k in ('surface', 'plants_plan', 'plants_cover', 'material',
                                                    'plants_instance')},
                  terrain_s=round(tg, 1), build_s=round(tb, 1), plan=os.path.basename(a['plan']),
                  palettes_file=PALETTES_FILE)
    # what the frames need is in Blender now: the layer material is built while the data is held, then the numpy
    # side (the levels' fields and masks, the surface maps, the plan's working arrays: several GB on a film terrain)
    # is let go before the first frame, which compiles every shader under the job's RAM cap
    users = image_users(list(t.obj.data.materials))
    lmat = layer_material(t, palette) if a['layers'] and not a['debug'] else None
    common['relinked_images'] = relink(users)
    obj, plant_objects = t.obj, dict(t.plant_objects)
    water = [o for o in list(t.water.get('lakes') or []) + [t.water.get('sea')] if o is not None]
    t.surface = t.plants = None
    del t
    gc.collect()
    done = []
    sun = None
    for v, cam, eye, aim, ground in shots:
        name = v['name'] + (f"_debug_{a['debug']}" if a['debug'] else '') + tag
        try:
            t1 = time.time()
            sc.camera = cam
            heading, pitch = SH.aim_camera(cam, eye, aim, v['frame'], v['lens'])
            cache = os.path.join(sky_root, v['name'])
            sky = light(sc, cam, cache, sun)
            sun = sky.sun
            bound = None
            if any(plant_objects.values()):
                from eidoblend.terrain.build import plant_instances as PI
                bound = PI.bind_sun(sun)
            path = os.path.join(out, name + '.png')
            t_first, t_second = render(sc, path, once=a['once'])
            shutil.rmtree(cache, ignore_errors=True)
            timing = {}
            if a['time']:
                # the material's own cost: the same frame in grey clay back to back (other jobs share the GPU, so
                # the difference survives better than either number)
                from eidoblend.terrain.build import surfacing as S
                for label, clay in (('clay', True), ('textured', False)):
                    obj.data.materials[0] = S.clay_material() if clay else mat
                    bpy.ops.render.render(write_still=False)              # compile
                    best = 1e9
                    for _ in range(2):
                        t2 = time.time()
                        bpy.ops.render.render(write_still=False)
                        best = min(best, time.time() - t2)
                    timing[label + '_s'] = round(best, 2)
                timing['material_s'] = round(timing['textured_s'] - timing['clay_s'], 2)
            rec[name] = dict(common, camera=[round(c, 1) for c in eye], ground=round(ground, 1),
                             aim=[round(c, 1) for c in aim], lens=v['lens'], heading_deg=round(heading, 1),
                             pitch_deg=round(pitch, 2), focus=focus, vista_m=v.get('vista_m'),
                             sun=getattr(bound, 'name', None), timing=timing, first_render_s=round(t_first, 1),
                             second_render_s=None if t_second is None else round(t_second, 2),
                             view_s=round(time.time() - t1, 1), caption=v['caption'], photo=v.get('photo'),
                             frame=v.get('frame'))
            done.append((v, name, cam))
            print(f"[review_views] {recipe}/{name}: heading {heading:.0f} pitch {pitch:.1f} lens {v['lens']:.0f}; "
                  f"terrain {source} {tg:.0f} s, build {tb:.0f} s ({common['seconds']}), plants "
                  f"{common['plants']}, first render {t_first:.1f} s"
                  + ('' if t_second is None else f", second {t_second:.2f} s"), flush=True)
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            rec[name] = dict(common, error=f'{type(e).__name__}: {e}')
    if lmat is not None and done:
        try:
            t1 = time.time()
            layer_scene(sc, obj, water, lmat)
            for v, name, cam in done:
                sc.camera = cam
                lp = os.path.join(out, name + '_layers.png')
                sc.render.filepath = lp
                t2 = time.time()
                bpy.ops.render.render(write_still=True)
                rec[name]['layers'] = os.path.basename(lp)
                rec[name]['layers_render_s'] = round(time.time() - t2, 1)
            print(f"[review_views] {recipe}: {len(done)} layer maps in {time.time() - t1:.0f} s", flush=True)
        except Exception as e:                                   # noqa: BLE001
            traceback.print_exc()
            for _v, name, _c in done:
                rec[name]['layers_error'] = f'{type(e).__name__}: {e}'
    gc.collect()


def main():
    a = args()
    recipe = a['recipe']
    plan = json.load(open(a['plan'], encoding='utf-8'))[recipe]
    sel = [s for s in a['views'].split(',') if s]
    views = [v for v in plan['views'] if not sel or v['name'] in sel]
    out = os.path.join(OUT, recipe)
    os.makedirs(out, exist_ok=True)
    sky_root = os.path.join(OUT, '_sky', f"{recipe}_{a['tag'] or 'untagged'}")
    ref = plan['reference'] if 'reference' in plan else REF[recipe]       # the judge's views.json names both
    size = refs.load(ref).extent if ref else None
    params = plan['params'] if 'params' in plan else SH.PARAMS.get(recipe)
    c0 = SH.recipe_centre(recipe, params)
    tag = f"_{a['tag']}" if a['tag'] else ''
    rec_path = os.path.join(out, f'{recipe}{tag}_record.json')
    rec = json.load(open(rec_path, encoding='utf-8')) if os.path.exists(rec_path) else {}
    groups = {}
    for v in views:                                    # the views without a focus share one terrain
        groups.setdefault(('shared',) if not v['focus'] else ('own', v['name']), []).append(v)
    for vs in groups.values():
        try:
            render_group(a, recipe, size, params, c0, vs, out, sky_root, tag, rec)
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            for v in vs:
                rec.setdefault(v['name'] + tag, dict(error=f'{type(e).__name__}: {e}'))
        with open(rec_path, 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    print('[review_views] done', flush=True)
    os._exit(0)


main()
