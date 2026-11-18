"""A recipe's look, rendered from the judge's matched cameras: the textured frame and, with --layers, the layer map of
the same frame (each layer one flat colour, unlit), so a palette edit is read beside the photograph of the place and
beside the render before it (board.py puts them side by side).

    bash run_blender.sh blender/tests/terrain/surface_look/render_look.py --recipe canyon \\
        [--views a,b] [--tag new] [--data] [--layers] [--snap <dir>] [--palettes <file.py>] [--samples 16]
        [--no-rocks] [--plan <views.json>]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The cameras are the judge's (surfacing_judge/views.json: the review's matched cameras, the ones that faced walls moved,
an establishing aerial and a low oblique added); the terrain is make_terrain's at the judge's settings (the reference's
extent, seed 1, film quality, a hero focus at the camera of an eye-level view); the light is make_sky daylight with the
sun 70 degrees left of the view; 960 x 540, 16 samples, AgX at exposure -0.5: a frame here lines up with the review's
renders and photographs.

    --data             the per-texel material (SURFACING_DESIGN.md 2.4): the terrain's surface data baked with its
                       palette (terrain/surface.bake_surface: the maps, the far colour C and the provenance colour P),
                       the plant layer's expected cover added first when the palette has a canopy layer or a weight
                       reads the plant rasters (plants.expected_cover, so the forest reads canopy_expected, the scrub
                       shrubs_far, and C sees them), the far material on
                       the rings beyond 1.5 D0 of every camera rendered from that terrain. Without it, the material
                       reads the mesh's mask attributes (the path a terrain without baked data takes)
    --snap <dir>       the first run of a view saves its terrain there (Terrain.save), later runs load it: the same
                       geometry under every palette, and no terrain cache involved. A saved terrain whose focus is not
                       the view's camera (a camera the judge moved) is not used: <recipe>_<view>_j.npz is made for it.
                       Views without a focus take the judge's saved terrain (out/surfacing_judge/terrains/<recipe>.npz)
                       when it is there. The palette is always resolved from the code as it is now
    --palettes <file>  another palettes.py to build the material from (the file as it was before an edit, for the
                       'before' frame of a board): loaded in place of eidoblend.terrain.build.palettes
    --layers           also render <view>_<tag>_layers.png: the material's debug 'layers' output under the Standard
                       view transform, a black world and black water, rocks hidden (surfacing/review_views.py's
                       layer pass, which the judge's layer decoding reads)
    --params k=v,...   recipe knobs (real_place: dem=lauterbrunnen)
    --plants           with --data: the plant layer's plants as well (plants.plan_plants around the first view's
                       camera, their cover rasters in the surface data, so the material's crowns and scrub leave the
                       ground under the instanced plants to them; plant_instances.instance_plants), for the forests
                       read with plants and without (SURFACING_DESIGN.md 5.4, package 3, item 5)

Views that share a terrain are rendered in one scene: the terrain, its bake and its material are made once, then
every view, then (with --layers) the layer material once and every view's layer map.

Writes out/surface_look/<recipe>/<view>_<tag>.png (and _layers.png) and <recipe>_<tag>_record.json.
"""
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
OUT = os.path.join(TN, 'out', 'surface_look')
VIEWS = os.path.join(TN, 'surfacing_judge', 'views.json')
JUDGE_TERRAINS = os.path.join(TN, 'out', 'surfacing_judge', 'terrains')
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
                data='--data' in a, plants='--plants' in a, snap=opt('--snap') or os.environ.get('EIDO_LOOK_SNAP'),
                palettes=opt('--palettes'), params=params or None, plan=opt('--plan', VIEWS))


ARGS = args()
if ARGS['palettes']:
    # another palettes.py in place of the package's: registered under the package's name before anything imports it,
    # so the recipes (strata.palette_for), the material, the surface bake and the rock scatter all read this one
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


def log(*a, **k):
    print(*a, **k, flush=True)


def quiet(*_a, **_k):
    pass


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


def _saved_focus(npz):
    """The focus a saved terrain was made with (its .json beside the .npz), or None."""
    js = os.path.splitext(npz)[0] + '.json'
    try:
        info = json.load(open(js, encoding='utf-8'))
    except (OSError, ValueError):
        return None
    f = info.get('focus') if isinstance(info, dict) else None
    if f is None and isinstance(info, dict) and isinstance(info.get('info'), dict):
        f = info['info'].get('focus')
    return f


def terrain_source(a, recipe, view, focus):
    """(path of the saved terrain to load or to save, exists) for a view: the judge's saved terrain for a view
    without a focus, else the view's snapshot in --snap whose focus is the view's camera (None without --snap)."""
    if not focus:
        p = os.path.join(JUDGE_TERRAINS, recipe + '.npz')
        if os.path.exists(p):
            return p, True
    if not a['snap']:
        return None, False
    for suffix in ('', '_j'):
        p = os.path.join(a['snap'], f"{recipe}_{view['name']}{suffix}.npz")
        if not os.path.exists(p):
            if suffix == '_j':
                return p, False
            continue
        if not focus:
            return p, True
        sf = _saved_focus(p)
        if sf and math.dist(tuple(sf[0][:2]), tuple(focus[0])) < 1.0:
            return p, True
    return os.path.join(a['snap'], f"{recipe}_{view['name']}_j.npz"), False


def build_terrain(a, recipe, size, params, focus, src):
    dress = a['rocks']
    palette = palette_now(recipe)
    path, exists = src
    if path and exists:
        t = A.Terrain.load(path, build=True, name=f'{recipe}_look', palette=palette, dress=dress)
        t.info['cache_hit'] = 'snapshot'
        return t
    t = A.make_terrain(recipe, size=size, seed=1, params=params, quality='film', palette=palette, dress=dress,
                       focus=focus, name=f'{recipe}_look')
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        t.save(path)
    return t


def palette_args(t):
    """(palette, strata) as make_terrain passes them to apply_surface for this terrain (a real place: its own
    palette name and strata)."""
    strata = None
    if t.info.get('place'):
        strata = (P.PLACES.get(t.info['place']) or {}).get('strata')
    return t.info.get('palette'), strata


def bake_data(t, rec):
    """The terrain's surface data with its palette: the plant layer's expected cover first when the palette has a
    canopy layer (from the terrain's masks: the ecotopes' densities read no baked map), handed to the bake, so the
    forest layers read canopy_expected and the far colour C is baked with it; then the maps and the palette bake (C
    and P). One bake with the palette's constants: a bake without them (snowline, sun, wind) has another key, and the
    surface cache keeps one bake per terrain."""
    from eidoblend.terrain import surface as SU
    from eidoblend.terrain.surface import bake as SB
    pal, _strata = palette_args(t)
    t0 = time.time()
    rpal = SB.resolve_palette(t, pal if pal is not None else 'auto')
    extra = None
    plant_maps = {'canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far'}
    if any(L.get('canopy') or (P.names_in(L['weight']) & plant_maps) for L in rpal['layers']):
        from eidoblend.terrain.build import plants as PL
        extra = PL.expected_cover(t)
        rec['cover_s'] = round(time.time() - t0, 1)
    sd = SU.bake_surface(t, palette=rpal, extra=extra, log=quiet)
    rec['bake_s'] = round(time.time() - t0, 1)
    rec['surface_key'] = str(sd.key)[:12]
    pb = sd.info.get('palette_bake')
    rec['palette_bake'] = pb if isinstance(pb, (str, dict)) else str(pb)
    return sd


def apply_material(t, sd, cams, options=None):
    pal, strata = palette_args(t)
    return S.apply_surface(t.obj, palette=pal, recipe=t.recipe, strata=strata, options=options, data=sd,
                           cameras=cams if sd is not None else None, log=quiet)


def view_camera(sc, t, v, c0):
    """(camera object, eye, target, heading, pitch) at the judge's view on terrain t."""
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    kind, dz = v['cam_z']
    ground = float(t.height_at(ex, ey))
    ez = ground + float(dz) if kind == 'ground' else float(dz)
    tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
    nm = 'look_cam_' + v['name']
    cam = bpy.data.objects.get(nm) or bpy.data.objects.new(nm, bpy.data.cameras.new(nm))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    dist = math.dist((ex, ey, ez), (tx, ty, tz))
    if kind == 'ground':
        cam.data.clip_start, cam.data.clip_end = 0.1, 4.0 * t.main.side + 40000.0
    else:
        cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 30.0 * dist
    heading, pitch = aim_camera(cam, (ex, ey, ez), (tx, ty, tz), v['frame'], v['lens'])
    bpy.context.view_layer.update()
    return cam, (ex, ey, ez), (tx, ty, tz), heading, pitch, ground


def eye_of(t, v):
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    kind, dz = v['cam_z']
    ez = float(t.height_at(ex, ey)) + float(dz) if kind == 'ground' else float(dz)
    return (ex, ey, ez)


_SUN = {}


def light(sc, cam, cache):
    """make_sky daylight with the sun RR.SUN_LEFT_DEG left of the view (a later view in the scene reuses the lamp)."""
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    os.makedirs(cache, exist_ok=True)
    sun = _SUN.get(sc.name)
    try:
        sun = sun if (sun is not None and sun.name in sc.objects) else None
    except ReferenceError:
        sun = None
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, sun=sun, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))))
    sky.bake(frame_start=1, frame_end=1, log=quiet)
    _SUN[sc.name] = sky.sun
    return sky


def black_layers_scene(sc, t):
    """The layer pass's scene state (review_views.py's): water black, every other object hidden, a black world,
    the Standard view transform. Returns a function that restores it."""
    black = bpy.data.materials.get('look_water_black')
    if black is None:
        black = bpy.data.materials.new('look_water_black')
        black.use_nodes = True
        nt = black.node_tree
        nt.nodes.clear()
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    water = [o for o in list((getattr(t, 'water', None) or {}).get('lakes') or [])
             + [(getattr(t, 'water', None) or {}).get('sea')] if o is not None]
    kept_mats = {o.name: list(o.data.materials) for o in water}
    for o in water:
        o.data.materials.clear()
        o.data.materials.append(black)
    keep = {t.obj.name} | {o.name for o in water}
    hidden = []
    for o in sc.objects:
        if o.type != 'CAMERA' and o.name not in keep and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    world = sc.world
    bw = bpy.data.worlds.get('look_black') or bpy.data.worlds.new('look_black')
    bw.color = (0.0, 0.0, 0.0)
    sc.world = bw
    vs = sc.view_settings
    old = (vs.view_transform, vs.look, vs.exposure, sc.render.film_transparent)
    vs.view_transform = 'Standard'
    try:
        vs.look = 'None'
    except TypeError:
        pass
    vs.exposure = 0.0
    sc.render.film_transparent = False

    def restore():
        for o in water:
            o.data.materials.clear()
            for m in kept_mats[o.name]:
                o.data.materials.append(m)
        for o in hidden:
            o.hide_render = False
        sc.world = world
        vs.view_transform = old[0]
        try:
            vs.look = old[1]
        except TypeError:
            pass
        vs.exposure, sc.render.film_transparent = old[2], old[3]
    return restore


def render_group(a, recipe, size, params, c0, views, src, out, sky_root, rec):
    """One terrain, its views: the textured frames, then (with --layers) the layer maps."""
    t0 = time.time()
    v0 = views[0]
    focus = [(c0[0] + v0['cam'][0], c0[1] + v0['cam'][1])] if v0['focus'] else None
    sc = RR.new_scene((W, H), a['samples'], TEX_EXPOSURE)          # a fresh file per terrain
    bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'   # before any image is drawn
    t = build_terrain(a, recipe, size, params, focus, src)
    tb = time.time() - t0
    common = dict(levels=[str(lv) for lv in t.levels], cache_hit=t.info.get('cache_hit'),
                  terrain=os.path.basename(src[0]) if src[0] else None, build_s=round(tb, 1),
                  rocks=(t.rocks or {}).get('count') if isinstance(t.rocks, dict) else None,
                  palettes_file=a['palettes'] and os.path.basename(a['palettes']), data=bool(a['data']))
    sd = None
    planted = None
    if a['data']:
        sd = bake_data(t, common)
        if a['plants']:
            from eidoblend.terrain.build import plants as PL
            t1 = time.time()
            ex, ey, _ez = eye_of(t, views[0])
            spots = PL.plan_plants(t, focus=(ex, ey), data=sd, log=quiet)
            sd.add_maps(spots.cover_extra())
            common['plan_s'] = round(time.time() - t1, 1)
            common['plants'] = {k: int(spots.count(k)) for k in spots.names()}
            planted = spots
        t1 = time.time()
        mat = apply_material(t, sd, [eye_of(t, v) for v in views])
        common['material_s'] = round(time.time() - t1, 1)
        common['samplers'] = mat.get('eido_samplers')
        common['far_m'] = mat.get('eido_far_m')
        common['far_rings'] = len(t.obj.data.materials) > 1
        if planted is not None:
            from eidoblend.terrain.build import plant_instances as PI
            t1 = time.time()
            PI.instance_plants(planted, t, log=quiet)
            common['instance_s'] = round(time.time() - t1, 1)
    pal = t.info.get('palette')
    common['palette'] = pal.get('name') if isinstance(pal, dict) else pal
    grp = next((n.node_tree for n in t.obj.data.materials[0].node_tree.nodes if n.bl_idname == 'ShaderNodeGroup'),
               None)
    common['nodes'] = len(grp.nodes) if grp else None
    shots = []
    for v in views:
        name = f"{v['name']}_{a['tag']}"
        try:
            t1 = time.time()
            cam, eye, tgt, heading, pitch, ground = view_camera(sc, t, v, c0)
            cache = os.path.join(sky_root, name)
            sky = light(sc, cam, cache)
            if planted is not None:
                from eidoblend.terrain.build import plant_instances as PI
                PI.bind_sun(sky.sun)                         # the leaves' backlight and the billboards' sun
            path = os.path.join(out, name + '.png')
            sc.render.filepath = path
            t2 = time.time()
            bpy.ops.render.render(write_still=True)
            t_first = time.time() - t2
            shutil.rmtree(cache, ignore_errors=True)
            rec[name] = dict(common, camera=[round(c, 1) for c in eye], ground=round(ground, 1),
                             aim=[round(c, 1) for c in tgt], lens=v['lens'], heading_deg=round(heading, 1),
                             pitch_deg=round(pitch, 2), focus=focus, render_s=round(t_first, 1),
                             view_s=round(time.time() - t1, 1), caption=v.get('caption'), photo=v.get('photo'))
            shots.append((v, name, cam))
            log(f"[render_look] {recipe}/{name}: heading {heading:.0f} pitch {pitch:.1f} lens {v['lens']:.0f}; "
                f"terrain {common['terrain']} ({common['cache_hit']}) {tb:.0f} s"
                + (f", bake {common.get('bake_s')} s, material {common.get('material_s')} s, "
                   f"{common.get('samplers')} samplers" if a['data'] else '')
                + f"; render {t_first:.1f} s")
        except Exception as e:                                   # noqa: BLE001 - recorded, the run goes on
            traceback.print_exc()
            rec[name] = dict(common, error=f'{type(e).__name__}: {e}')
    if a['layers'] and shots:
        try:
            t1 = time.time()
            if a['data']:
                apply_material(t, sd, [], options=dict(debug='layers'))
            else:
                S.apply_surface(t.obj, palette=palette_args(t)[0], recipe=t.recipe, strata=palette_args(t)[1],
                                options=dict(debug='layers'), log=quiet)
            restore = black_layers_scene(sc, t)
            for v, name, cam in shots:
                sc.camera = cam
                sc.render.filepath = os.path.join(out, name + '_layers.png')
                t2 = time.time()
                bpy.ops.render.render(write_still=True)
                rec[name]['layers_s'] = round(time.time() - t2, 1)
            restore()
            log(f"[render_look] {recipe}: {len(shots)} layer maps in {time.time() - t1:.0f} s")
        except Exception as e:                                   # noqa: BLE001
            traceback.print_exc()
            for _v, name, _c in shots:
                rec[name]['layers_error'] = f'{type(e).__name__}: {e}'
    del t
    gc.collect()


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
    groups = {}
    for v in views:
        focus = [(c0[0] + v['cam'][0], c0[1] + v['cam'][1])] if v['focus'] else None
        src = terrain_source(a, recipe, v, focus)
        key = src[0] if (src[0] and not v['focus']) else (src[0] or v['name'])
        if v['focus']:
            key = (key, v['name'])                               # a focused view has its own terrain
        groups.setdefault(key, (src, []))[1].append(v)
    for _key, (src, vs) in groups.items():
        try:
            render_group(a, recipe, size, params, c0, vs, src, out, sky_root, rec)
        except Exception as e:                                   # noqa: BLE001
            traceback.print_exc()
            for v in vs:
                rec.setdefault(f"{v['name']}_{a['tag']}", dict(error=f'{type(e).__name__}: {e}'))
        with open(rec_path, 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, indent=1, default=str)
    shutil.rmtree(sky_root, ignore_errors=True)
    log('[render_look] done')
    os._exit(0)


main()
