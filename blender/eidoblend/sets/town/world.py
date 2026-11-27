"""eidoblend.sets.town.world: the town's light and air. Blender:

    from eidoblend.sets.town import world as TW
    sky = TW.light(scene, camera, sky='sky', cache_dir='//sky_cache')  # the sky family's Earth sky, its sun the town's
    sky.bake(frame, frame)                                             #   (re-bake after moving the camera)
    TW.light(scene, camera, sky='hdri')        # the named option: a CC0 photo sky (kloofendal_43d_clear_puresky)
    TW.air(collection, parent)                 # 'town_air': the dust held in the air, a volume round the town
    TW.eevee(scene, samples=16)                # the EEVEE settings the town is lit for, and the volumes' range

THE SUN stands 50 degrees up, from the south-east of the town's own axes (it travels along SUN_DIR), so every parapet,
tank and car draws itself with a shadow; a desert's hard sun, its disc widened a little by the dust (1.2 degrees).

THE SKY, by default, is the sky family's (eidoblend.sky.make_sky: world 'earth', clear): the hour and the azimuth are
solved so its sun stands exactly where SUN_DIR puts it, its sun and sky retinted toward a dusty country's (warmer sun,
a paler, warmer sky low down: SKY_FAMILY), and the view exposure raised to the town's balance between sun and sky. It is
a baked sky: bake it for the frames and the camera you render (Sky.bake), again after the camera moves.

sky='hdri' is the photo option: Poly Haven's kloofendal_43d_clear_puresky (CC0, fetched by ID into the shared library
on first use): a clear sky with no ground, its own sun at 43 degrees clamped out of it (the lamp is the sun, with its
shadow), the picture turned about the vertical so its bright side is the lamp's side, eased toward the dust's colour
near the horizon, lighting at one strength and seen at another (SKY: a pale bright desert sky behind the town, a fill
of a fifth to a quarter of the light on a roof). sky=None leaves the scene's world alone and only makes the sun.

THE AIR is dust held in the air, a homogeneous volume 5.2 km across and 900 m high (EEVEE renders a volume in an object,
not one in the World), so the town greys into the distance and fades into its plain; eevee() gives the volumes the
range that needs (out to 3.5 km).
"""
import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector

SUN_DIR = Vector((-0.45, 0.5, -0.80)).normalized()                  # the way its light travels
SUN = dict(energy=4.6, color=(1.0, 0.925, 0.80), angle_deg=1.2)
# the sky family's Earth sky for the town: clear, its sun and sky retinted (Sky.set_colors), the view exposure (stops)
# that brings its sun (2.8 W/m2 at 50 degrees) to the town's balance, and its diffuse fill (make_sky ambient)
SKY_FAMILY = dict(clouds='clear', sun_tint=(1.0, 0.94, 0.82), sky_tint=(1.25, 1.0, 0.7), exposure=0.75, ambient=0.35)
# the photo sky: lights at 'strength', seen at 'seen'; its sun clamped to 'clamp'; eased toward 'horizon' low down
SKY = dict(strength=0.52, seen=1.3, clamp=1.6, horizon=(0.80, 0.74, 0.64), horizon_mix=0.35, desaturate=0.12)
HDRI = dict(id='kloofendal_43d_clear_puresky', res='4k')
AIR = dict(density=0.00042, color=(0.86, 0.78, 0.66), anisotropy=0.45, size=(5200.0, 5200.0, 900.0), z0=-40.0)


def sun(sc):
    """the town's sun lamp 'town_sun' (outside the town's collection), made or reset"""
    o = bpy.data.objects.get('town_sun')
    if o is None:
        o = bpy.data.objects.new('town_sun', bpy.data.lights.new('town_sun', 'SUN'))
        sc.collection.objects.link(o)
    o.data.energy, o.data.color = SUN['energy'], SUN['color']
    o.data.angle = math.radians(SUN['angle_deg'])
    o.rotation_mode = 'XYZ'
    o.rotation_euler = SUN_DIR.to_track_quat('-Z', 'Y').to_euler()
    for k, v in (('use_shadow', True), ('shadow_soft_size', 0.0)):
        try:
            setattr(o.data, k, v)
        except (AttributeError, TypeError):
            pass
    return o


def sky_hours(direction=None, el_max=62.0, az_span=0.9):
    """(hours, azimuth base) that put the sky family's sun where `direction` (the way the light travels, Blender axes)
    says: its elevation is sin((h - 6) / 12 * pi) * el_max (the afternoon's root), its azimuth base + the day's sweep"""
    from ...sky import palette as P
    to_sun = -(direction or SUN_DIR).normalized()
    x3, y3, z3 = P.blender_to_three(tuple(to_sun))
    el = math.degrees(math.asin(max(-1.0, min(1.0, y3))))
    if el >= el_max:
        raise ValueError(f'the sun at {el:.1f} degrees is above the sky family\'s highest ({el_max:g})')
    day_k = 1.0 - math.asin(el / el_max) / math.pi
    hours = 6.0 + 12.0 * day_k
    az = math.atan2(z3, x3)
    return hours, az - P.arc_az(hours, az_span)


def light(sc, camera=None, sky='sky', cache_dir=None, quality='draft', hdri=None, log=print):
    """the town's sun and sky in the scene. sky 'sky' (the default): the sky family's Earth sky, returned to bake;
    'hdri': the photo world (hdri: a file of your own, else HDRI's, fetched; nothing to bake: returns None); None: the
    sun only, the world left as it is"""
    o = sun(sc)
    if sky in (None, False):
        return None
    if sky == 'hdri':
        world_hdri(sc, hdri, log)
        return None
    if sky not in ('sky', 'earth'):
        raise ValueError(f"[town] sky {sky!r}: 'sky' (the sky family), 'hdri' or None")
    from ...sky import make_sky
    if camera is None:
        camera = sc.camera
    if camera is None:
        raise ValueError('[town] the sky family needs the camera it is baked for (pass camera=, or set scene.camera)')
    hours, az = sky_hours()
    if cache_dir is None:
        cache_dir = os.path.join(bpy.app.tempdir or os.path.dirname(bpy.data.filepath or '.'), 'town_sky')
    s = make_sky(sc, camera=camera, world='earth', hours=hours, clouds=SKY_FAMILY['clouds'], sun=o, cache_dir=cache_dir,
                 quality=quality, ambient=SKY_FAMILY['ambient'], azimuth=az, audio=False, weather_fx=False)
    s.set_colors({'sun': SKY_FAMILY['sun_tint'], 'sky': SKY_FAMILY['sky_tint']})
    sc.view_settings.exposure = SKY_FAMILY['exposure']
    log(f'[town] sky family: hour {hours:.3f}, azimuth base {az:.4f} rad (the sun travels {tuple(round(v, 3) for v in SUN_DIR)})')
    return s


def hdri_path(fetch=True):
    """the photo sky's .hdr in the shared library (cache/hdris/<id>_<res>/hdri.hdr), fetched once with fetch_hdri.py
    (EIDO_NO_FETCH=1 forbids the download)"""
    from ... import common
    d = common.cache_dir('hdris', f"{HDRI['id']}_{HDRI['res']}")
    p = os.path.join(d, 'hdri.hdr')
    if os.path.isfile(p) or not fetch:
        return p
    cmd = [os.environ.get('PYTHON') or ('python' if os.name == 'nt' else 'python3'), os.path.join(common.REPO, 'fetch_hdri.py'),
           HDRI['id'], HDRI['res']]
    if os.environ.get('EIDO_NO_FETCH') == '1':
        raise FileNotFoundError(f'{p} is not in the library; fetch it in that folder with: {" ".join(cmd[1:])}')
    os.makedirs(d, exist_ok=True)
    subprocess.run(cmd, cwd=d, capture_output=True, text=True, creationflags=0x08000000 if sys.platform == 'win32' else 0)
    if not os.path.isfile(p):
        raise FileNotFoundError(f'{p}: fetch_hdri.py {HDRI["id"]} {HDRI["res"]} did not write it')
    return p


def _hdri_sun(img, log=print):
    """where the picture's own sun is: (azimuth from +x toward +y, elevation), radians; and its sky's share of the light"""
    import numpy as np
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    lum = px[..., 0] * 0.2126 + px[..., 1] * 0.7152 + px[..., 2] * 0.0722
    j, i = np.unravel_index(np.argmax(lum), lum.shape)             # (row from the bottom, column)
    u, v = (i + 0.5) / w, (j + 0.5) / h
    az, el = math.pi - 2.0 * math.pi * u, (v - 0.5) * math.pi
    upper = lum[h // 2:, :]
    el_r = ((np.arange(h // 2, h) + 0.5) / h - 0.5) * math.pi        # each row's elevation
    wgt = (np.sin(el_r) * np.cos(el_r))[:, None] * (math.pi / h) * (2.0 * math.pi / w)
    e_sky = float((np.minimum(upper, SKY['clamp']) * wgt).sum()) * SKY['strength']
    e_sun = SUN['energy'] * float(-SUN_DIR.z)
    log(f'[town] photo sky: its sun at azimuth {math.degrees(az):.1f}, elevation {math.degrees(el):.1f}; on a level roof the sky '
        f'gives {e_sky:.2f} W/m2 against the sun\'s {e_sun:.2f} ({e_sky / (e_sky + e_sun):.0%} of the light)')
    return az, el


def world_hdri(sc, path=None, log=print):
    """the photo world 'town_world' (sky='hdri'), from `path` (an equirectangular .hdr / .exr) or the named CC0 sky:
    see the module's docstring"""
    w = bpy.data.worlds.get('town_world') or bpy.data.worlds.new('town_world')
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputWorld')
    img = bpy.data.images.load(os.path.abspath(path) if path else hdri_path(), check_existing=True)   # (a .hdr loads as scene-linear)
    az_s, el_s = _hdri_sun(img, log)
    to_sun = -SUN_DIR
    az_t = math.atan2(to_sun.y, to_sun.x)
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    mp.vector_type = 'VECTOR'
    mp.inputs['Rotation'].default_value = (0.0, 0.0, az_s - az_t)   # the lookup turned: the picture's sun comes to the lamp's azimuth
    L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    env = N.new('ShaderNodeTexEnvironment')
    env.image = img
    L.new(mp.outputs[0], env.inputs['Vector'])
    # its sun's disc and the glare round it clamped to the sky's own level (the lamp is the sun)
    lum = N.new('ShaderNodeRGBToBW')
    L.new(env.outputs['Color'], lum.inputs[0])
    sc_ = N.new('ShaderNodeMath')
    sc_.operation = 'DIVIDE'
    sc_.inputs[0].default_value = SKY['clamp']
    L.new(lum.outputs[0], sc_.inputs[1])
    mn = N.new('ShaderNodeMath')
    mn.operation, mn.use_clamp = 'MINIMUM', False
    mn.inputs[1].default_value = 1.0
    L.new(sc_.outputs[0], mn.inputs[0])
    mul = N.new('ShaderNodeVectorMath')
    mul.operation = 'SCALE'
    L.new(env.outputs['Color'], mul.inputs[0])
    L.new(mn.outputs[0], mul.inputs['Scale'])
    # a dusty country's sky: a little less blue, and paler and warmer toward the horizon
    hs = N.new('ShaderNodeHueSaturation')
    hs.inputs['Saturation'].default_value = 1.0 - SKY['desaturate']
    L.new(mul.outputs[0], hs.inputs['Color'])
    nrm = N.new('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    L.new(tc.outputs['Generated'], nrm.inputs[0])
    sz = N.new('ShaderNodeSeparateXYZ')
    L.new(nrm.outputs[0], sz.inputs[0])
    mr = N.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs[1].default_value, mr.inputs[2].default_value = 0.0, 0.32
    mr.inputs[3].default_value, mr.inputs[4].default_value = SKY['horizon_mix'], 0.0
    L.new(sz.outputs[2], mr.inputs[0])
    lv = N.new('ShaderNodeRGBToBW')
    L.new(hs.outputs[0], lv.inputs[0])
    hz = N.new('ShaderNodeVectorMath')
    hz.operation = 'SCALE'
    hz.inputs[0].default_value = SKY['horizon']
    L.new(lv.outputs[0], hz.inputs['Scale'])
    hz2 = N.new('ShaderNodeVectorMath')                             # (the horizon's level kept: only its colour changes)
    hz2.operation = 'SCALE'
    hz2.inputs['Scale'].default_value = 1.0 / (0.2126 * SKY['horizon'][0] + 0.7152 * SKY['horizon'][1] + 0.0722 * SKY['horizon'][2])
    L.new(hz.outputs[0], hz2.inputs[0])
    mx = N.new('ShaderNodeMix')
    mx.data_type = 'RGBA'
    L.new(mr.outputs[0], mx.inputs[0])
    L.new(hs.outputs[0], mx.inputs[6])
    L.new(hz2.outputs[0], mx.inputs[7])
    bg = N.new('ShaderNodeBackground')
    lp = N.new('ShaderNodeLightPath')                               # the strength it lights with; the strength the lens sees
    st = N.new('ShaderNodeMath')
    st.operation = 'MULTIPLY_ADD'
    L.new(lp.outputs['Is Camera Ray'], st.inputs[0])
    st.inputs[1].default_value, st.inputs[2].default_value = SKY['seen'] - SKY['strength'], SKY['strength']
    L.new(st.outputs[0], bg.inputs['Strength'])
    L.new(mx.outputs[2], bg.inputs['Color'])
    L.new(bg.outputs[0], out.inputs['Surface'])
    for k, v in (('sun_threshold', 1000.0), ('use_sun_shadow', False)):     # (no second sun pulled out of the picture)
        try:
            setattr(w, k, v)
        except (AttributeError, TypeError):
            pass
    sc.world = w
    sc.view_settings.exposure = 0.0
    return w


def air(col, parent=None):
    """the dust in the air: a box of it round the town, 5.2 km across and 900 m high"""
    me = bpy.data.meshes.get('town_air')
    if me is None:
        sx, sy, sz = AIR['size']
        z0 = AIR['z0']
        v = [(-sx / 2, -sy / 2, z0), (sx / 2, -sy / 2, z0), (sx / 2, sy / 2, z0), (-sx / 2, sy / 2, z0),
             (-sx / 2, -sy / 2, z0 + sz), (sx / 2, -sy / 2, z0 + sz), (sx / 2, sy / 2, z0 + sz), (-sx / 2, sy / 2, z0 + sz)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        me = bpy.data.meshes.new('town_air')
        me.from_pydata(v, [], f)
        m = bpy.data.materials.new('town.air')
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.type != 'OUTPUT_MATERIAL':
                nt.nodes.remove(n)
        pv = nt.nodes.new('ShaderNodeVolumePrincipled')
        pv.inputs['Density'].default_value = AIR['density']
        pv.inputs['Color'].default_value = (*AIR['color'], 1.0)
        pv.inputs['Anisotropy'].default_value = AIR['anisotropy']
        nt.links.new(pv.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Volume'])
        me.materials.append(m)
    o = bpy.data.objects.new('town_air', me)
    col.objects.link(o)
    if parent is not None:
        o.parent = parent
    o.display_type = 'BOUNDS'
    return o


def eevee(sc, samples=16, log=print):
    """the EEVEE settings the town is lit for (ray-traced screen-space reflections, fast GI, soft shadows) and the
    volumes' range for its air; AgX"""
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
    ee = sc.eevee
    for k, v in (('taa_render_samples', samples), ('use_raytracing', True), ('ray_tracing_method', 'SCREEN'), ('use_shadows', True),
                 ('shadow_ray_count', 2), ('shadow_step_count', 12), ('use_fast_gi', True), ('fast_gi_method', 'GLOBAL_ILLUMINATION'),
                 ('fast_gi_resolution', '2'), ('fast_gi_step_count', 8), ('fast_gi_distance', 0.6), ('clamp_surface_indirect', 10.0),
                 ('volumetric_start', 0.5), ('volumetric_end', 3500.0), ('volumetric_tile_size', '8'), ('volumetric_samples', 64),
                 ('volumetric_sample_distribution', 0.85), ('use_volumetric_shadows', False)):
        try:
            setattr(ee, k, v)
        except (AttributeError, TypeError) as e:
            log(f'[town] EEVEE setting not taken: {k} ({e})')
    try:
        ee.ray_tracing_options.resolution_scale = '1'
        ee.ray_tracing_options.use_denoise = True
        ee.ray_tracing_options.trace_max_roughness = 0.5
        ee.ray_tracing_options.screen_trace_quality = 0.5
    except (AttributeError, TypeError):
        pass
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
