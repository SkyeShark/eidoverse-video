"""look/lighting.py: lights for EEVEE. Units, the sun, key / fill / rim, practicals (a glowing surface WITH its real
light), the ray-traced lighting settings that replace rt_lighting.js, light probes and their bake, the light inventory.

Units (Blender's glTF importer, io_scene_gltf2 'SPEC' mode, checked in 5.2): sun W/m2 = lux / 683; point and spot
W = candela x 4 pi / 683; spot_size = 2 x three's angle; spot_blend = three's penumbra; three's distance ->
use_custom_distance + cutoff_distance; an ambient / hemisphere light is the world's colour (Blender has no ambient light).
Relative levels port this way; absolute levels are judged again by eye (and by look.exposure) under AgX.

    from eidoblend.look import lighting as L
    sun = L.sun(scene, elevation_deg=16, azimuth_deg=-70, strength=4.5, kelvin_k=4800)
    rig = L.key_fill_rim(scene, subject=arm, camera=cam, key_w=300)              # area lights round a subject
    lamp = L.practical(scene, bpy.data.objects['LampBulb'], watts=6, kelvin_k=2700)   # the bulb glows AND lights
    rt = L.create_rt_lighting(scene, refl_max_rough=0.6)                          # rt_lighting.js's three effects
    L.add_room_probe(scene, 'room', (-2.2, -2.0, 0.0), (2.2, 2.0, 2.7), wall=0.12)   # its outer samples in the walls
    L.log_lights(scene)
"""
import math

import bpy
from mathutils import Vector

from . import camera as C

LUMENS_PER_WATT = 683.0


# ---------------------------------------------------------------------------------------------------------- units
def lux_to_sun(lux):
    """A three.js DirectionalLight in lux (physically correct lights) -> a Blender sun's strength in W/m2."""
    return lux / LUMENS_PER_WATT


def sun_to_lux(w_m2):
    return w_m2 * LUMENS_PER_WATT


def candela_to_watts(cd):
    """A three.js PointLight / SpotLight intensity in candela -> Blender point / spot power in W."""
    return cd * 4 * math.pi / LUMENS_PER_WATT


def watts_to_candela(w):
    return w * LUMENS_PER_WATT / (4 * math.pi)


def three_spot(angle_rad, penumbra):
    """three's SpotLight cone (half angle, penumbra 0..1) -> Blender (spot_size full angle, spot_blend)."""
    return 2.0 * angle_rad, float(penumbra)


def kelvin(light, k):
    """Colour a light by its colour temperature (Blender 5's blackbody temperature on the light)."""
    if hasattr(light, 'use_temperature'):
        light.use_temperature = True
        light.temperature = float(k)
        light.color = (1.0, 1.0, 1.0)
    else:
        light.color = blackbody_rgb(k)
    return light


def blackbody_rgb(k):
    """An approximate linear-sRGB colour of a blackbody at k Kelvin (for emitters; lights use their own temperature)."""
    t = k / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    srgb = [min(255.0, max(0.0, v)) / 255.0 for v in (r, g, b)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    m = max(lin)
    return tuple(c / m for c in lin)


# ---------------------------------------------------------------------------------------------------------- lights
def _light(scene, name, kind, collection=None):
    data = bpy.data.lights.new(name, kind)
    ob = bpy.data.objects.new(name, data)
    (collection or scene.collection).objects.link(ob)
    return ob


def sun_direction(elevation_deg, azimuth_deg):
    """The unit vector toward the sun: azimuth from +Y (0) toward +X (90), elevation above the horizon."""
    e, a = math.radians(elevation_deg), math.radians(azimuth_deg)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def sun(scene, elevation_deg=30.0, azimuth_deg=0.0, strength=4.0, kelvin_k=5500, angle_deg=0.53, name='sun',
        collection=None, shadow_jitter=True):
    """The sun: a SUN light from (elevation, azimuth), strength in W/m2 (lux / 683), its real angular size (0.53 deg:
    soft-edged shadows that sharpen toward the contact), colour by temperature."""
    ob = _light(scene, name, 'SUN', collection)
    d = ob.data
    d.energy = float(strength)
    d.angle = math.radians(angle_deg)
    kelvin(d, kelvin_k)
    d.use_shadow = True
    if hasattr(d, 'use_shadow_jitter'):
        d.use_shadow_jitter = bool(shadow_jitter)
    toward = sun_direction(elevation_deg, azimuth_deg)
    ob.matrix_world = C.look_matrix(toward * 100.0, Vector((0.0, 0.0, 0.0)))
    ob['sun_elevation'], ob['sun_azimuth'] = float(elevation_deg), float(azimuth_deg)
    return ob


def area(scene, name, position, aim, watts, size=1.0, size_y=None, kelvin_k=5000, spread_deg=180.0, shape=None,
         collection=None, shadow=True):
    """An area light at `position` facing `aim` (a target spec), `watts` of power, size in metres (its softness)."""
    ob = _light(scene, name, 'AREA', collection)
    d = ob.data
    d.energy = float(watts)
    if size_y is not None:
        d.shape = shape or 'RECTANGLE'
        d.size, d.size_y = float(size), float(size_y)
    else:
        d.shape = shape or 'DISK'
        d.size = float(size)
    d.spread = math.radians(spread_deg)
    d.use_shadow = shadow
    kelvin(d, kelvin_k)
    ob.matrix_world = C.look_matrix(Vector(position), Vector(C.target_fn(aim)()))
    return ob


def point(scene, name, position, watts, radius=0.05, kelvin_k=2700, collection=None, shadow=True):
    ob = _light(scene, name, 'POINT', collection)
    ob.location = position
    ob.data.energy = float(watts)
    ob.data.shadow_soft_size = float(radius)
    ob.data.use_shadow = shadow
    kelvin(ob.data, kelvin_k)
    return ob


def spot(scene, name, position, aim, watts, cone_deg=40.0, blend=0.15, radius=0.05, kelvin_k=3200, collection=None,
         shadow=True):
    """A spot light aimed at a target: cone_deg is the FULL cone angle (three's angle x 2)."""
    ob = _light(scene, name, 'SPOT', collection)
    d = ob.data
    d.energy = float(watts)
    d.spot_size = math.radians(cone_deg)
    d.spot_blend = float(blend)
    d.shadow_soft_size = float(radius)
    d.use_shadow = shadow
    kelvin(d, kelvin_k)
    ob.matrix_world = C.look_matrix(Vector(position), Vector(C.target_fn(aim)()))
    return ob


def key_fill_rim(scene, subject, camera, key_w=250.0, fill_ratio=0.25, rim_w=200.0, distance=3.0, key_deg=40.0,
                 key_height=1.2, size=1.0, kelvin_k=(5000, 6000, 4500), y_bias=0.25, rim_cone_deg=30.0, collection=None):
    """A three-point rig round a subject, placed from the camera: the key (a softbox: an area light with a 120 deg
    spread) `key_deg` to the camera's side and above, the fill (wider, softer) on the other side at fill_ratio of the
    key, the rim behind and high: a SPOT with a narrow cone, so it edges the silhouette instead of flooding the floor
    behind (an area light there did exactly that, test_key_fill_rim.py 11-07). Lights a person or a prop the studio
    way; outdoors the sun is the key and the sky the fill, so use it there only as a bounce or a kicker."""
    tgt = C.focus_point(subject, y_bias) if not callable(subject) else Vector(subject())
    cpos = camera.matrix_world.translation
    to_cam = (cpos - tgt)
    to_cam.z = 0
    to_cam.normalize()
    side = Vector((0.0, 0.0, 1.0)).cross(to_cam)

    def place(deg, h, back=False):
        a = math.radians(deg)
        d = (to_cam * math.cos(a) + side * math.sin(a)) * (-1 if back else 1)
        return tgt + d * distance + Vector((0.0, 0.0, h))
    col = collection or scene.collection
    k = area(scene, 'key', place(key_deg, key_height), tgt, key_w, size, kelvin_k=kelvin_k[0], spread_deg=120.0,
             collection=col)
    f = area(scene, 'fill', place(-key_deg - 15, key_height * 0.5), tgt, key_w * fill_ratio, size * 1.5,
             kelvin_k=kelvin_k[1], spread_deg=150.0, collection=col)
    r = spot(scene, 'rim', place(-25, key_height * 1.8, back=True), tgt, rim_w, cone_deg=rim_cone_deg, blend=0.35,
             radius=0.15, kelvin_k=kelvin_k[2], collection=col)
    return {'key': k, 'fill': f, 'rim': r}


def practical(scene, emitter, watts, kelvin_k=2700, strength=None, kind='POINT', size=None, aim=None, name=None,
              collection=None):
    """A practical light: the fixture's emitting surface glows AND a real light of the same size and colour sits on it
    (episode three's film_face_light pattern). An emission alone lights nothing reliably in EEVEE (only through probes
    and the screen-space GI); a light alone is light from nowhere. emitter: the object whose material is the lit
    part (a bulb, a lampshade, a screen). Its emission colour and strength are set (strength default: chosen so
    the surface reads a little brighter than what it lights). kind POINT (a bulb), AREA (a panel / screen), SPOT."""
    ob = bpy.data.objects[emitter] if isinstance(emitter, str) else emitter
    col = blackbody_rgb(kelvin_k)
    for slot in ob.material_slots:
        m = slot.material
        if m is None or not m.node_tree:
            continue
        p = next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
        if p is None:
            continue
        p.inputs['Emission Color'].default_value = (*col, 1.0)
        p.inputs['Emission Strength'].default_value = float(strength if strength is not None else 12.0)
    lo, hi = C.world_bounds(ob)
    centre = (lo + hi) * 0.5
    ext = hi - lo
    nm = name or f'{ob.name}_light'
    if kind == 'AREA':
        lt = area(scene, nm, centre, aim if aim is not None else centre - Vector((0, 0, 1)), watts,
                  size=size or max(ext.x, ext.y), kelvin_k=kelvin_k, collection=collection)
    elif kind == 'SPOT':
        lt = spot(scene, nm, centre, aim if aim is not None else centre - Vector((0, 0, 1)), watts,
                  radius=(size or max(ext) / 2), kelvin_k=kelvin_k, collection=collection)
    else:
        lt = point(scene, nm, centre, watts, radius=(size or max(ext) / 2), kelvin_k=kelvin_k, collection=collection)
    ob.visible_shadow = False        # the glowing part never shadows its own light
    lt['practical_of'] = ob.name
    return lt


# ---------------------------------------------------------------------------------------------------------- RT
class RTLighting:
    """The handle create_rt_lighting returns. EEVEE traces every frame from scratch in a final render: update() and
    reset_history() have nothing to do (kept so a ported scene's calls stay valid)."""

    def __init__(self, scene, settings):
        self.scene = scene
        self.settings = settings
        self.uniforms = {}

    def update(self):
        return self

    def reset_history(self):
        return self


def create_rt_lighting(scene, shadows=True, gi=True, reflections=True, refl_max_rough=0.6, light_radius=None,
                       denoise=True, gi_distance=None, method='SCREEN'):
    """rt_lighting.js's three effects, as EEVEE settings:
      shadows      every light's virtual shadow map, traced soft (shadow rays x steps); a light's radius is its
                   shadow_soft_size (area: size; sun: angle). light_radius sets every point / spot that is still at
                   Blender's default 0.25 m. castShadow=false -> obj.visible_shadow = False.
      gi           fast GI (GLOBAL_ILLUMINATION, screen space, dynamic) on top of baked volume probes (static: bake
                   them, bake_light_probes). keepFill has no counterpart: a broad fill must be real lights or
                   emissive panels plus a baked probe. INDOORS, with a baked room probe, gi=False: fast GI's scan
                   (in either mode, GI or AO only) lit the corner room's floor contacts and wall bases with the world
                   through the walls (a blue crescent under a white sphere, bright strips, grain), and with it off
                   EEVEE agreed with Cycles (measured 11-07; probe.render_reference is the check).
      reflections  ray tracing up to refl_max_rough (rougher lobes come from sphere probes / the world).
      denoise      the ray tracing denoiser (spatial + temporal + bilateral). OIDN is the compositor Denoise node,
                   for low-sample previews only.
    Returns an RTLighting handle (update / reset_history are no-ops)."""
    ee = scene.eevee
    done = {}
    ee.use_shadows = bool(shadows)
    done['shadows'] = ee.use_shadows
    if light_radius is not None:
        for o in scene.objects:
            if o.type == 'LIGHT' and o.data.type in ('POINT', 'SPOT') and abs(o.data.shadow_soft_size - 0.25) < 1e-6:
                o.data.shadow_soft_size = float(light_radius)
    ee.use_fast_gi = bool(gi)
    if gi:
        ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
        if gi_distance is not None:
            ee.fast_gi_distance = float(gi_distance)
    done['gi'] = ee.use_fast_gi
    ee.use_raytracing = bool(reflections)
    if reflections:
        ee.ray_tracing_method = method
        o = ee.ray_tracing_options
        o.trace_max_roughness = float(refl_max_rough)
        o.use_denoise = bool(denoise)
        o.denoise_spatial = o.denoise_temporal = o.denoise_bilateral = bool(denoise)
    done['reflections'] = {'on': ee.use_raytracing, 'max_roughness': refl_max_rough, 'method': method}
    return RTLighting(scene, done)


# ---------------------------------------------------------------------------------------------------------- probes
def add_volume_probe(scene, name, centre, size, resolution=(16, 16, 8), samples=1024, clamp_indirect=10.0,
                     collection=None):
    """A volume light probe (baked indirect light for a room or a set): centre, size (x, y, z) metres; resolution the
    grid of samples inside it (cell-centred: the outermost sit half a cell inside the box). Surfaces beyond the
    outermost samples fade to the WORLD's light, as if nothing stood between them and the sky: a room's probe must
    reach into its walls (add_room_probe), not stop at them."""
    d = bpy.data.lightprobes.new(name, 'VOLUME')
    ob = bpy.data.objects.new(name, d)
    (collection or scene.collection).objects.link(ob)
    ob.location = centre
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    for attr, v in (('resolution_x', resolution[0]), ('resolution_y', resolution[1]), ('resolution_z', resolution[2]),
                    ('bake_samples', samples), ('clamp_indirect', clamp_indirect)):
        if hasattr(d, attr):
            setattr(d, attr, v)
    return ob


def add_room_probe(scene, name, inner_min, inner_max, wall=0.12, spacing=0.35, samples=1024, clamp_indirect=10.0,
                   collection=None):
    """A volume probe for a room: inner_min / inner_max are the room's inside corners (floor to ceiling), wall the
    thickness of its walls, floor and ceiling. The outermost rows of samples sit in the middle of the walls, about
    `spacing` apart, so every interior surface lies BETWEEN rows of samples. The samples inside the walls see
    backfaces: EEVEE marks them invalid and fills them from the room side (validity, dilation). A window's hole has
    no wall: its samples see the sky, as the room does there.

    Why: EEVEE fades a volume probe to the world's light beyond its outermost samples. Measured 11-07 on the corner
    room, a probe sized to the room's interior lit the walls, the floor and the spheres' lower halves with the uniform
    world as if there were no walls: pale blue walls, and a white sphere with a dark cap where its top reached the
    probe's samples. Cycles, path traced, shows that room warm and the sphere evenly lit. Returns the probe."""
    lo = Vector(inner_min) - Vector((wall / 2,) * 3)
    hi = Vector(inner_max) + Vector((wall / 2,) * 3)
    res = [max(2, int(round((hi[i] - lo[i]) / spacing)) + 1) for i in range(3)]
    cell = [(hi[i] - lo[i]) / (res[i] - 1) for i in range(3)]
    size = [hi[i] - lo[i] + cell[i] for i in range(3)]
    return add_volume_probe(scene, name, (lo + hi) * 0.5, size, resolution=res, samples=samples,
                            clamp_indirect=clamp_indirect, collection=collection)


def add_sphere_probe(scene, name, centre, radius=2.0, falloff=0.2, collection=None):
    """A sphere probe (reflections for the surroundings of `centre`): captures the scene round it."""
    d = bpy.data.lightprobes.new(name, 'SPHERE')
    ob = bpy.data.objects.new(name, d)
    (collection or scene.collection).objects.link(ob)
    ob.location = centre
    if hasattr(d, 'influence_distance'):
        d.influence_distance = float(radius)
    if hasattr(d, 'falloff'):
        d.falloff = float(falloff)
    return ob


def bake_light_probes(scene, probes=None, exclude=()):
    """Bake volume probes (a GPU job: run through heavy.sh). One probe at a time, `exclude` objects / collections hidden
    from the bake (episode three left out the room's haze, 'air'). Returns seconds per probe. Sphere probes need no
    bake: EEVEE refreshes them itself."""
    import time
    vols = probes or [o for o in scene.objects if o.type == 'LIGHT_PROBE' and o.data.type == 'VOLUME']
    hidden = []
    for o in C._collect(list(exclude)):
        if not o.hide_probe_volume:
            o.hide_probe_volume = True
            hidden.append(o)
    out = {}
    try:
        for p in vols:
            for o in scene.objects:
                o.select_set(False)
            p.select_set(True)
            bpy.context.view_layer.objects.active = p
            t = time.perf_counter()
            with bpy.context.temp_override(scene=scene, active_object=p, object=p, selected_objects=[p]):
                bpy.ops.object.lightprobe_cache_bake(subset='ACTIVE')
            out[p.name] = round(time.perf_counter() - t, 1)
            print(f'[lighting] baked {p.name} in {out[p.name]} s', flush=True)
    finally:
        for o in hidden:
            o.hide_probe_volume = False
    return out


# ---------------------------------------------------------------------------------------------------------- review
def log_lights(scene, out=print):
    """The light inventory, once at setup: name, type, power, radius / size, colour temperature, shadow."""
    rows = []
    for o in scene.objects:
        if o.type != 'LIGHT' or o.hide_render:
            continue
        d = o.data
        if d.type == 'SUN':
            size, unit = f'angle {math.degrees(d.angle):.2f} deg', 'W/m2'
        elif d.type == 'AREA':
            size, unit = f'size {d.size:.2f}' + (f' x {d.size_y:.2f}' if d.shape in ('RECTANGLE', 'ELLIPSE') else '') + ' m', 'W'
        else:
            size, unit = f'radius {d.shadow_soft_size:.3f} m', 'W'
        extra = f', cone {math.degrees(d.spot_size):.0f} deg blend {d.spot_blend:.2f}' if d.type == 'SPOT' else ''
        temp = f'{d.temperature:.0f} K' if getattr(d, 'use_temperature', False) else 'rgb ' + ','.join(f'{c:.2f}' for c in d.color)
        rows.append(f'{o.name}: {d.type} {d.energy:g} {unit}, {size}{extra}, {temp}, shadow {d.use_shadow}')
    w = scene.world
    rows.append(f'world: {w.name if w else None}' + (f', sun threshold {w.sun_threshold}' if w else ''))
    for r in rows:
        out('[lights] ' + r)
    return rows


def debug_passes(scene, out_dir, passes=('diffuse_light', 'specular_light', 'shadow', 'ao', 'vector', 'normal', 'z'),
                 name='passes'):
    """rt_lighting's debug views, as render passes written through compositor File Output nodes (a render's own
    multilayer EXR holds only Combined in 5.2), one node and one EXR per pass: <out_dir>/<name>_<pass>_*.exr (raw
    data: no view transform). 'vector' needs motion blur off: the pass is empty with it on."""
    vl = bpy.context.view_layer
    flags = {'diffuse_light': ('use_pass_diffuse_direct', 'use_pass_diffuse_indirect'),
             'specular_light': ('use_pass_glossy_direct', 'use_pass_glossy_indirect'),
             'shadow': ('use_pass_shadow',), 'ao': ('use_pass_ambient_occlusion',), 'vector': ('use_pass_vector',),
             'normal': ('use_pass_normal',), 'z': ('use_pass_z',), 'emission': ('use_pass_emit',),
             'environment': ('use_pass_environment',), 'mist': ('use_pass_mist',)}
    for p in passes:
        for f in flags[p]:
            setattr(vl, f, True)
    if 'vector' in passes:
        scene.render.use_motion_blur = False
    from .post import chain
    t = chain.tree(scene)
    # a Render Layers node made AFTER the passes are switched on (an older node keeps its stale, unavailable sockets:
    # linked, they write nothing)
    old = t.nodes.get('look:passes_rl')
    if old is not None:
        t.nodes.remove(old)
    rl = t.nodes.new('CompositorNodeRLayers')
    rl.name = 'look:passes_rl'
    rl.scene = scene
    rl.location = (-400, -400)
    for n in [n for n in t.nodes if n.name.startswith('look:pass:')]:
        t.nodes.remove(n)
    # the Render Layers node's pass sockets, by their 5.2 names (EEVEE: 'Diffuse Direct' / 'Glossy Direct' carry the
    # light; there are no indirect sockets)
    sockets = {'diffuse_light': ('Diffuse Direct', 'Diffuse Indirect'), 'specular_light': ('Glossy Direct', 'Glossy Indirect'),
               'shadow': ('Shadow',), 'ao': ('Ambient Occlusion',), 'vector': ('Vector',), 'normal': ('Normal',),
               'z': ('Depth',), 'emission': ('Emission', 'Emit'), 'environment': ('Environment', 'Env'), 'mist': ('Mist',)}
    names = [s for p in passes for s in sockets[p]]
    written, absent, nodes = [], [], []
    for i, nm in enumerate(names):
        s = rl.outputs.get(nm)
        if s is None or not s.enabled:
            absent.append(nm)
            continue
        # ONE File Output node per pass: in 5.2.0 a node with several items writes only its first one into the
        # multilayer EXR (measured 11-07: Shadow + Diffuse Direct + Normal items -> a file with Shadow.V alone)
        fo = t.nodes.new('CompositorNodeOutputFile')
        fo.name = f'look:pass:{nm}'
        fo.location = (200, -400 - 120 * i)
        fo.directory = out_dir
        fo.file_name = f"{name}_{nm.lower().replace(' ', '_')}_"
        fo.save_as_render = False               # data, not a picture: no view transform
        fo.format.media_type = 'MULTI_LAYER_IMAGE'
        fo.format.file_format = 'OPEN_EXR_MULTILAYER'
        fo.format.color_depth = '32'
        fo.file_output_items.new('FLOAT' if s.type == 'VALUE' else ('VECTOR' if s.type == 'VECTOR' else 'RGBA'), nm)
        t.links.new(s, fo.inputs[nm])
        written.append(nm)
        nodes.append(fo)
    print(f'[lighting] debug_passes: {written} -> {out_dir}/{name}_<pass>_*.exr'
          + (f' (not offered by this engine: {absent})' if absent else ''), flush=True)
    return nodes
