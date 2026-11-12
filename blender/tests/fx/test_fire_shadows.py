"""What EEVEE 5.2 does for two parts of the engine's fire look (fluid_grid.js), measured:

  shadows  the engine's shadowMesh: the smoke's own soft shadow on the floor. A 1 m cube of white smoke (Principled
           Volume, density 2 per metre, albedo 1: extinction 2 per metre) hangs 1 m over a grey floor under a sun, a
           spot and a point light straight above it, each casting shadows. The floor under the cube, seen from the
           side (no camera ray crosses the cube), against the same floor with the cube hidden: the light's
           transmittance through 1 m of the smoke, against Beer-Lambert's exp(-2) = 0.135. With the scene's
           volumetric shadows off as well.
  spokes   the engine's projected spoke pattern: its point light's colour node textured the floor. A point light
           whose node tree feeds a checker into its Emission, against the same light without a node tree: the
           floor's pixels, compared.

  options  (no render) create_volume_fire refuses the engine's eight raymarch and light-node options with what EEVEE
           does in their place, in either spelling (shadow_absorption, shadowAbsorption ...)
  caster   (no render) the port of shadowMesh, create_volume_fire(shadow_floor=z): its plane over the ground, seen by
           shadow rays only, hidden until a bake; its transmittance map, marched through a frame's grids toward the
           key light, against Beer-Lambert through a slab of smoke (2 m at density 1, extinction 0.15 per metre x
           0.85, the material's detail-noise factor on average)
  fire     the example's teapot fire (test_fire_teapot.py's scene), baked 24 frames with shadow_floor: the floor lit
           by the key spot alone (the gas and the fire's lights hidden), with the caster and without, where the map
           says the smoke shadows it; the map moving with the smoke between frames 12 and 24 (and the stills with
           everything on, with and without the caster: out/fire_shadows/fire_shadow_still.png, fire_noshadow_still.png)
  heights  on the fire case's bake (no bake here): the same floor with the caster 0.5 mm to 20 cm over it, against the
           map, for EEVEE's shadow bias (shadow_lift)

Renders 480 x 270 (the teapot cases 960 x 540), 16 samples, to out/fire_shadows/*.exr (and PNG stills); prints PASS /
FAIL with the numbers.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 \
        bash run_blender.sh <worktree>/blender/tests/fx/test_fire_shadows.py [-- cases=options,shadows,spokes]
"""

import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
args = dict(a.split('=', 1) for a in argv if '=' in a)
CASES = args.get('cases', 'options,caster,shadows,spokes,fire,heights').split(',')
OUT = os.path.join(HERE, 'out', 'fire_shadows')
os.makedirs(OUT, exist_ok=True)
W, H = 480, 270
FAILS = []
DENSITY = 2.0


def check(ok, what):
    print(f"[test_fire_shadows] {'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def stage():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    ee = sc.eevee
    ee.taa_render_samples = 16
    ee.use_raytracing = True
    ee.use_fast_gi = True
    ee.use_shadows = True
    ee.use_volumetric_shadows = True
    ee.volumetric_tile_size = '2'
    ee.volumetric_samples = 128
    ee.volumetric_shadow_samples = 32
    ee.use_volume_custom_range = True
    ee.volumetric_start, ee.volumetric_end = 0.5, 12.0
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    w = bpy.data.worlds.new('black')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w
    me = bpy.data.meshes.new('floor')
    me.from_pydata([(-10, -10, 0), (10, -10, 0), (10, 10, 0), (-10, 10, 0)], [], [(0, 1, 2, 3)])
    fl = bpy.data.objects.new('floor', me)
    sc.collection.objects.link(fl)
    fm = bpy.data.materials.new('floor')
    fm.use_nodes = True
    b = fm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    b.inputs['Roughness'].default_value = 0.9
    me.materials.append(fm)
    cd = bpy.data.cameras.new('cam')
    cd.lens = 35
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    # at the side, 6 m out and 4 m up: every ray to the floor under the cube passes under the cube's bottom (1 m)
    cam.location = (6.0, 0.0, 4.0)
    cam.rotation_euler = (math.radians(90.0 - math.degrees(math.atan2(4.0, 6.0))), 0.0, math.radians(90.0))
    sc.camera = cam
    return sc, cam


def smoke_cube():
    me = bpy.data.meshes.new('smoke')
    v = [(x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (1.0, 2.0)]
    me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    ob = bpy.data.objects.new('smoke', me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new('smoke')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    pv.inputs['Density'].default_value = DENSITY
    pv.inputs['Color'].default_value = (1, 1, 1, 1)
    nt.links.new(pv.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Volume'])
    me.materials.append(m)
    return ob


def light(kind, z=6.0):
    ld = bpy.data.lights.new(kind.lower(), kind)
    ld.use_shadow = True
    if kind == 'SUN':
        ld.energy, ld.angle = 3.0, math.radians(0.5)
    else:
        ld.energy, ld.shadow_soft_size = 3000.0, 0.02
        if kind == 'SPOT':
            ld.spot_size, ld.spot_blend = math.radians(60), 0.1
    ob = bpy.data.objects.new(kind.lower(), ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0.0, 0.0, z)
    return ob


def render(name):
    import OpenImageIO as oiio
    sc = bpy.context.scene
    p = os.path.join(OUT, name + '.exr')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    return np.asarray(oiio.ImageBuf(p).get_pixels(oiio.FLOAT), np.float64)[..., :3]


def floor_box(cam, lo=(-0.35, -0.35), hi=(0.35, 0.35)):
    """the pixel rows / columns of the floor square under the cube's middle"""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    sc = bpy.context.scene
    bpy.context.view_layer.update()                  # the camera's matrix as placed
    pts = [world_to_camera_view(sc, cam, Vector((x, y, 0.0))) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
    xs = [p.x * W for p in pts]
    ys = [(1.0 - p.y) * H for p in pts]
    return int(min(ys)) + 1, int(max(ys)), int(min(xs)) + 1, int(max(xs))


if 'options' in CASES:
    from eidoblend.fx import fire as fxfire
    sc, cam = stage()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 1))
    burner = bpy.context.active_object
    n0 = len(bpy.data.objects)
    for name in list(fxfire.ENGINE_ONLY) + ['shadowAbsorption', 'projectionRadius']:
        try:
            fxfire.create_volume_fire(burner, **{name: 1.0})
            check(False, f'{name} is refused')
        except TypeError as e:
            check('EEVEE' in str(e) or 'Principled Volume' in str(e), f'{name} is refused: {str(e)[:150]}')
    try:
        fxfire.create_volume_fire(burner, buoyancyy=1.0)
        check(False, 'a misspelt option is refused')
    except TypeError as e:
        check('unknown options' in str(e), f'a misspelt option is refused: {e}')
    check(len(bpy.data.objects) == n0, 'nothing is built when an option is refused')

if 'caster' in CASES:
    from eidoblend.fx import fire as fxfire
    from eidoblend.fx._util import read_exr
    sc, cam = stage()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 1))
    burner = bpy.context.active_object
    fire = fxfire.create_volume_fire(burner, key_light_pos=(0.0, 0.0, 40.0), shadow_floor=0.0, name='caster',
                                     cache_dir=os.path.join(OUT, 'caster_cache'))
    sm = fire.shadow_mesh
    mat = sm.active_material
    check(sm is not None and sm.hide_render and not sm.visible_camera and sm.visible_shadow
          and mat.use_transparent_shadow and mat.surface_render_method == 'DITHERED',
          'shadow_floor: a plane seen by shadow rays only, with transparent shadows, hidden until a bake')
    x0, y0, x1, y1, z = fire.shadow_extent
    lo, hi = fire._domain_box()
    lift = fire.params['shadow_lift']
    check(x0 <= lo[0] and y0 <= lo[1] and x1 >= hi[0] and y1 >= hi[1] and abs(z - lift) < 1e-9,
          f'it covers the domain\'s footprint, {lift * 100:g} cm over the ground: x {x0:.1f}..{x1:.1f}, '
          f'y {y0:.1f}..{y1:.1f}')
    GX, GY, GZ = fire.G3
    WX, WY, WZ = fire.W3
    cell = WX / GX
    arr = np.zeros((GZ, GY, GX, 4), np.float32)
    yc = (np.arange(GY) + 0.5) * cell
    arr[:, (yc >= 4.0) & (yc < 6.0), :, 0] = 1.0             # a slab of smoke 2 m thick, 4 to 6 m up
    import time
    t0 = time.time()
    fire._write_shadow(1, arr)
    t1 = time.time()
    fire._write_shadow(1, arr)
    t2 = time.time()
    check(t2 - t1 < 1.5, f'a frame\'s map takes {t2 - t1:.2f} s once the march is set up ({t1 - t0:.2f} s the first '
                         f'time), {fire.params["shadow_resolution"]}^2 texels x 64 steps')
    T = read_exr(os.path.join(fire.cache_dir, 'caster_shadow_0001.exr'))[..., 0]
    res = T.shape[0]
    mid = T[res // 2 - 4:res // 2 + 4, res // 2 - 4:res // 2 + 4].mean()
    want = math.exp(-1.0 * 2.0 * fire.params['smoke_density'] * (0.85 if fire.params['detail_noise'] else 1.0))
    check(abs(mid - want) < 0.02 * want, f'under the slab, the key light straight above: transmittance {mid:.4f} '
                                         f'(Beer-Lambert {want:.4f})')
    edge = T[1, 1]
    check(edge > 0.999, f'outside the domain the ground is clear: {edge:.4f}')

def teapot_scene():
    """test_fire_teapot.py's scene (the example's floor, teapot, key spot and camera), for the fire and heights cases:
    (scene, camera, teapot, its material, the key light, the floor's height)"""
    sys.path.insert(0, HERE)
    import _teapot
    from eidoblend.fx._util import color, from_three
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 24
    sc.eevee.taa_render_samples = 16
    sc.eevee.use_raytracing = True
    sc.eevee.use_fast_gi = True
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 1.74
    w = bpy.data.worlds.new('black')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w
    floor_z = 0.8
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, floor_z))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new('floor')
    fm.use_nodes = True
    fb = fm.node_tree.nodes['Principled BSDF']
    fb.inputs['Base Color'].default_value = (*color(0x111115), 1)
    fb.inputs['Roughness'].default_value = 0.8
    floor.data.materials.append(fm)
    teapot, min_y = _teapot.teapot_object('teapot', 0.8, 28)
    teapot.location = (0, 0, floor_z - min_y)
    tm = bpy.data.materials.new('teapot')
    tm.use_nodes = True
    tb = tm.node_tree.nodes['Principled BSDF']
    tb.inputs['Base Color'].default_value = (0, 0, 0, 1)
    tb.inputs['Metallic'].default_value = 1.0
    tb.inputs['Roughness'].default_value = 1.0
    teapot.data.materials.append(tm)
    drv = teapot.driver_add('rotation_euler', 2).driver
    drv.type = 'SCRIPTED'
    drv.expression = '(4.0 + frame / 24 * 1.2) * 0.25'
    kd = bpy.data.lights.new('key', 'SPOT')
    kd.energy = 4 * math.pi * 1000.0
    kd.spot_size, kd.spot_blend, kd.shadow_soft_size, kd.use_shadow = 2 * math.pi / 5, 1.0, 0.25, True
    key = bpy.data.objects.new('key', kd)
    sc.collection.objects.link(key)
    key.location = tuple(from_three((-4.5, 15.4, 9.0)))
    tgt = bpy.data.objects.new('key_target', None)
    sc.collection.objects.link(tgt)
    tgt.location = tuple(from_three((1, 0, 0)))
    con = key.constraints.new('TRACK_TO')
    con.target, con.track_axis, con.up_axis = tgt, 'TRACK_NEGATIVE_Z', 'UP_Y'
    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(60)
    cd.clip_start, cd.clip_end = 0.1, 100
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    cam.location = tuple(from_three((14, 5.5, 4.4)))
    look = bpy.data.objects.new('look', None)
    sc.collection.objects.link(look)
    look.location = tuple(from_three((0, 3.6, 0)))
    cc = cam.constraints.new('TRACK_TO')
    cc.target, cc.track_axis, cc.up_axis = look, 'TRACK_NEGATIVE_Z', 'UP_Y'
    sc.camera = cam
    bpy.context.view_layer.update()
    return sc, cam, teapot, tm, key, floor_z


if 'fire' in CASES:
    import time
    from eidoblend.fx import fire as fxfire
    sc, cam, teapot, tm, key, floor_z = teapot_scene()
    fire = fxfire.create_volume_fire(teapot, key_light=key, shadow_floor=floor_z,
                                     cache_dir=os.path.join(OUT, 'fire_cache'), name='shadowfire')
    fire.make_lava_emissive(tm)
    t0 = time.time()
    fire.bake(1, 24)
    print(f'[test_fire_shadows] bake with the shadow map: {time.time() - t0:.1f} s', flush=True)
    fxfire.configure_eevee_for_fire(sc, fire, cam)
    sc.frame_set(24)
    # the floor lit by the key spot alone: the fire's own lights and the volume hidden (the gas's emission and
    # in-scatter along the camera rays would add the same light to both renders and pull their ratio toward 1), so
    # the floor's light is the key light through the caster, or not
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    lights_on = [fire.point_light, fire.volume_light, fire.volume_object]
    for lo in lights_on:
        lo.hide_render = True
    sm = fire.shadow_mesh
    a = render('fire_key_caster')
    sm.hide_render = True
    b = render('fire_key_nocaster')
    sm.hide_render = False
    # where the map says the smoke shadows the floor: its texels projected into the frame
    from eidoblend.fx._util import read_exr
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    Tm = read_exr(os.path.join(fire.cache_dir, 'shadowfire_shadow_0024.exr'))[..., 0]
    T12 = read_exr(os.path.join(fire.cache_dir, 'shadowfire_shadow_0012.exr'))[..., 0]
    shade = (Tm < 0.95) | (T12 < 0.95)
    sway = float(np.abs(Tm - T12)[shade].mean()) if shade.any() else 0.0
    check(sway > 0.01, f'the shadow moves with the smoke: mean |change| {sway:.3f} in transmittance between frames 12 and '
                       f'24 over the {int(shade.sum())} shadowed texels (min transmittance {Tm.min():.2f})')
    x0, y0, x1, y1, z = fire.shadow_extent
    R = Tm.shape[0]
    Ha, Wa = a.shape[:2]

    def floor_ratio(lit, bare):
        """(light passing, map transmittance) at the floor points the map shades, in view"""
        ratio, mapT = [], []
        for i in range(0, R, 2):
            for j in range(0, R, 2):
                if Tm[i, j] > 0.85:
                    continue
                p = Vector((x0 + (x1 - x0) * j / (R - 1), y0 + (y1 - y0) * i / (R - 1), floor_z))
                v = world_to_camera_view(sc, cam, p)
                if not (0.02 < v.x < 0.98 and 0.02 < v.y < 0.98 and v.z > 0):
                    continue
                px, py = int(v.x * Wa), int((1.0 - v.y) * Ha)
                la, lb = lit[py, px].mean(), bare[py, px].mean()
                if lb > 1e-4:
                    ratio.append(la / lb)
                    mapT.append(Tm[i, j])
        return np.array(ratio), np.array(mapT)

    ratio, mapT = floor_ratio(a, b)
    check(len(ratio) > 20 and abs(float(np.median(ratio)) - float(np.median(mapT))) < 0.15,
          f'the smoke shadows the floor under the key spot (the caster {fire.params["shadow_lift"] * 100:g} cm up): '
          f'{len(ratio)} shadowed floor points in view, light passing {float(np.median(ratio)):.3f} (median) where '
          f'the map says {float(np.median(mapT)):.3f}')
    for lo in lights_on:
        lo.hide_render = False
    fxfire.create_fire_compose(sc, fire)              # the example's saturation and bloom, for the stills
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    for tag, show in (('fire_shadow_still', True), ('fire_noshadow_still', False)):
        sm.hide_render = not show
        sc.render.filepath = os.path.join(OUT, tag + '.png')
        bpy.ops.render.render(write_still=True)
    sm.hide_render = False

if 'heights' in CASES:
    # the caster's height over the ground against EEVEE's shadow bias, on the fire case's bake (no bake here): the floor
    # under the key spot (the gas and the fire's lights hidden) with the plane at 0.5 mm to 20 cm, against the map
    from eidoblend.fx import fire as fxfire
    from eidoblend.fx._util import read_exr
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    sc, cam, teapot, tm, key, floor_z = teapot_scene()
    cache = os.path.join(OUT, 'fire_cache')
    fire = fxfire.create_volume_fire(teapot, key_light=key, shadow_floor=floor_z, cache_dir=cache, name='shadowfire')
    fire._attach_shadow_sequence(1, 24)
    sc.frame_set(24)
    for ob in (fire.point_light, fire.volume_light, fire.volume_object):
        ob.hide_render = True
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    sm = fire.shadow_mesh
    Tm = read_exr(os.path.join(cache, 'shadowfire_shadow_0024.exr'))[..., 0]
    x0, y0, x1, y1, z_built = fire.shadow_extent
    R = Tm.shape[0]
    pts = []                                    # the floor pixels the map shades, in view: (row, column, map value)
    for i in range(0, R, 2):
        for j in range(0, R, 2):
            if Tm[i, j] > 0.85:
                continue
            v = world_to_camera_view(sc, cam, Vector((x0 + (x1 - x0) * j / (R - 1), y0 + (y1 - y0) * i / (R - 1),
                                                      floor_z)))
            if 0.02 < v.x < 0.98 and 0.02 < v.y < 0.98 and v.z > 0:
                pts.append((int((1.0 - v.y) * sc.render.resolution_y), int(v.x * sc.render.resolution_x), Tm[i, j]))
    sm.hide_render = True
    bare = render('heights_none')
    sm.hide_render = False
    mapT = float(np.median([t for _r, _c, t in pts])) if pts else float('nan')
    passing = {}
    for h in (0.0005, 0.005, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2):
        sm.location.z = floor_z + h - z_built
        img = render(f'heights_{h * 1000:g}mm')
        r = [img[py, px].mean() / bare[py, px].mean() for py, px, _t in pts if bare[py, px].mean() > 1e-4]
        passing[h] = float(np.median(r)) if r else float('nan')
    sm.location.z = 0.0
    print('[test_fire_shadows] the caster at a height over the floor, light passing (median over '
          f'{len(pts)} shaded floor points; the map says {mapT:.3f}): '
          + ', '.join(f'{h * 1000:g} mm {p:.3f}' for h, p in passing.items()), flush=True)
    good = [h for h, p in passing.items() if abs(p - mapT) < 0.1]
    check(bool(good), f'some height lets the caster shadow the floor as the map says: '
                      f'{", ".join(f"{h * 1000:g} mm" for h in good) or "none"}')

if 'shadows' in CASES:
    sc, cam = stage()
    cube = smoke_cube()
    y0, y1, x0, x1 = floor_box(cam)
    print(f'[test_fire_shadows] the floor under the cube: rows {y0}..{y1}, columns {x0}..{x1}', flush=True)
    expect = math.exp(-DENSITY * 1.0)
    # the control: the same cube as an opaque surface, which must shadow the floor
    solid = smoke_cube()
    solid.name = 'solid'
    sm = bpy.data.materials.new('solid')
    sm.use_nodes = True
    solid.data.materials.clear()
    solid.data.materials.append(sm)
    for kind in ('SUN', 'SPOT', 'POINT'):
        lo = light(kind)
        res = {}
        solid.hide_render = True
        for vs in (True, False):
            sc.eevee.use_volumetric_shadows = vs
            cube.hide_render = False
            a = render(f'{kind.lower()}_smoke_vs{int(vs)}')
            cube.hide_render = True
            b = render(f'{kind.lower()}_clear_vs{int(vs)}')
            t = float(a[y0:y1, x0:x1].mean() / max(b[y0:y1, x0:x1].mean(), 1e-9))
            res[vs] = t
        solid.hide_render = False
        c = render(f'{kind.lower()}_solid')
        solid.hide_render = True
        t_solid = float(c[y0:y1, x0:x1].mean() / max(b[y0:y1, x0:x1].mean(), 1e-9))
        check(t_solid < 0.2, f'{kind.lower()}: the control, the cube made opaque, shadows the floor: {t_solid:.3f} '
                             'of the light passes')
        check(res[True] > 0.98 and res[False] > 0.98,
              f'{kind.lower()}: 1 m of smoke casts no shadow on the floor (EEVEE 5.2): transmittance {res[True]:.3f} '
              f'with volumetric shadows on, {res[False]:.3f} off (Beer-Lambert through it: {expect:.3f})')
        bpy.data.objects.remove(lo, do_unlink=True)
    sc.eevee.use_volumetric_shadows = True
    cube.hide_render = False
    light('SUN')
    sc.render.image_settings.file_format = 'PNG'
    from mathutils import Vector
    cam.location = (4.5, -4.5, 3.0)                  # the cube and the floor under it, where a shadow would fall
    cam.rotation_euler = (Vector((0.0, 0.0, 0.9)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, 'smoke_shadow_still.png')
    bpy.ops.render.render(write_still=True)

if 'spokes' in CASES:
    sc, cam = stage()
    cam.location = (0.0, -7.0, 4.0)
    cam.rotation_euler = (math.radians(60.0), 0.0, 0.0)
    lo = light('POINT', z=1.5)
    plain = render('point_plain')
    ld = lo.data
    ld.use_nodes = True
    nt = ld.node_tree
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    ck = nt.nodes.new('ShaderNodeTexChecker')
    ck.inputs['Scale'].default_value = 6.0
    ck.inputs['Color1'].default_value = (1, 0.2, 0.0, 1)
    ck.inputs['Color2'].default_value = (0.0, 0.0, 0.0, 1)
    nt.links.new(ck.outputs['Color'], em.inputs['Color'])
    noded = render('point_node_tree')
    d = float(np.abs(noded - plain).max())
    check(d < 1e-4, f'EEVEE ignores the light node tree: max |difference| {d:.2e} over the floor (a checker into the '
                    'light\'s Emission colour)')

print(f'[test_fire_shadows] {"FAIL" if FAILS else "PASS"}: {len(FAILS)} failed check(s)')
