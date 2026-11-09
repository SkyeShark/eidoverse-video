"""Billboard particles for Blender 5.2 EEVEE: the port of eidoverse/particles.js (makeParticles), and the sprite
machinery the particle morph (particle_morph.py) shares with it.

The engine's system is stateless: each particle's position is a closed-form function of time,
    tL = fract(t * speed / lifetime + phase),  age = tL * lifetime
    p  = origin + emit + vel * age + 0.5 * gravity * age^2 + drift(t, phase) + swirl(age)   (flame: converge)
so it ports to one Geometry Nodes graph driven by Scene Time, with no bake: a point per particle carrying
its emit offset, launch velocity and seed, a camera-facing quad instanced on each point (the active camera's
rotation, or a given camera's, plus the flame preset's per-particle spin), size over life, and the per-particle
phase, twinkle, opacity and colour stored for the material. Scrubbing and re-rendering just work. Motion blur
follows EEVEE's rule for transparent surfaces: normal-blended (DITHERED) sprites write velocity and blur with the
default single time step; additive sprites are BLENDED surfaces, which write none, so they blur only when
scene.eevee.motion_blur_steps is above 1 (each step renders the frame at another time and the steps accumulate;
measured in tests/particles/test_camera_cut_and_motion_blur.py).

The engine's live uniforms (size, opacity, color, origin) are keyable here: size, opacity and colour are the
Geometry Nodes modifier's inputs, origin is the object's location. Particles.uniforms holds them as Uniform
handles (.value to set, .key(frame) to key), so a fade, a pulse or a moving emitter is keyed data in the .blend.

The textures are the engine's own library (eidoverse/assets/particle_textures, 80 sprites), reused as they are;
map='auto' takes the SPRITES pick for the preset. Additive presets render as emission over a transparent quad;
'normal' presets (smoke, dust, snow) are unlit by default like the engine's MeshBasicMaterial, or lit=True for
matter that the scene's lights should shade. The engine's options dict (opts=, three's axes) and its `scene: group`
(a Collection or an Object as scene=, see scene_or_group) are taken as a scene.js wrote them.

The engine's display. three r184's WebGPU renderer ignores a material's `toneMapped` flag: every frame, additive
sprites included, went through ACESFilmic in the output pass (the scene pass is linear, renderOutput tone maps it).
The Blender edition renders through the film's view (AgX), which carries bright saturated light to white along a
different path. create_particles_compose() matches the additive sprites' light per pixel to what three's ACES
showed for it (EEVEE's Transparent pass holds exactly that light), and leaves the rest of the frame to the film.

Differences from the engine, on purpose:
  - seeded: the engine used Math.random(); here `seed` fixes every particle (same render every time);
  - the time is the scene clock: t = (frame - frame_start) / fps + time_offset (the engine used the
    renderer's elapsed time, which starts at the film's first frame too);
  - the quads cast no shadow (the engine's InstancedMesh did not either).
"""

from __future__ import annotations

import math
import os

import numpy as np

from ._util import color, from_three

PRESETS = {
    'sparks': dict(count=220, size=0.06, lifetime=0.9, speed=1, gravity=(0, -4.0, 0), area=0.15, up=2.2, spread=1.6,
                   color=0xffd27f, blending='additive', grow=-0.8, wobble=0.0, opacity=1.0, twinkle=0),
    'embers': dict(count=140, size=0.05, lifetime=2.6, speed=1, gravity=(0, 0.5, 0), area=0.4, up=0.7, spread=0.5,
                   color=0xff7a30, blending='additive', grow=-0.5, wobble=0.25, opacity=1.0, twinkle=0.4),
    'smoke': dict(count=70, size=0.7, lifetime=4.5, speed=1, gravity=(0, 0.45, 0), area=0.3, up=0.5, spread=0.3,
                  color=0x8a8a8a, blending='normal', grow=1.8, wobble=0.35, opacity=0.35, twinkle=0),
    'dust': dict(count=160, size=0.04, lifetime=6.0, speed=1, gravity=(0, 0.02, 0), area=3.0, up=0.05, spread=0.2,
                 color=0xbcb2a0, blending='normal', grow=0.2, wobble=0.5, opacity=0.4, twinkle=0.3),
    'snow': dict(count=320, size=0.05, lifetime=8.0, speed=1, gravity=(0, -0.7, 0), area=6.0, up=0.0, spread=0.1,
                 color=0xffffff, blending='normal', grow=0.0, wobble=0.55, opacity=0.9, twinkle=0),
    'magic': dict(count=180, size=0.08, lifetime=2.4, speed=1, gravity=(0, 0.6, 0), area=0.5, up=0.4, spread=0.6,
                  color=0x9b5cff, blending='additive', grow=-0.3, wobble=0.4, opacity=1.0, twinkle=0.7, swirl=1.4),
    'stars': dict(count=420, size=0.07, lifetime=3.0, speed=1, gravity=(0, 0.0, 0), area=22.0, up=0.0, spread=0.0,
                  color=0xffffff, blending='additive', grow=0.0, wobble=0.0, opacity=1.0, twinkle=1.0),
    'muzzle': dict(count=48, size=0.45, lifetime=0.22, speed=1, gravity=(0, 0.0, 0), area=0.05, up=0.2, spread=2.4,
                   color=0xfff0c0, blending='additive', grow=-1.4, wobble=0.0, opacity=1.0, twinkle=0),
    # real flame shape: colour over life, convergence to the axis, asymmetric size, spin. Pair with
    # flame_05 / flame_06 (vertical tongues; flame_01..04 are wispy puffs that read as smoke)
    'fire': dict(count=150, size=0.5, lifetime=0.55, speed=1, gravity=(0, 0.5, 0), area=0.10, up=0.55, spread=0.18,
                 color=0xffffff, blending='additive', grow=0, wobble=0.15, opacity=1.0, twinkle=0.25, flame=True,
                 converge=0.85, rotate=0.35),
}

TEXTURE_DIR_PARTS = ('eidoverse', 'assets', 'particle_textures')

# a sprite from the library that suits each preset (map='auto'); the engine left the choice to the scene, except the
# fire's flame_05 / flame_06 that the city builder loaded for it
SPRITES = {'sparks': 'spark_05', 'embers': 'glow_soft', 'smoke': 'smoke_04', 'dust': 'dot', 'snow': 'dot',
           'magic': 'magic_05', 'stars': 'star_06', 'muzzle': 'muzzle_02', 'fire': 'flame_05'}


def scene_or_group(scene, collection=None, parent=None):
    """The engine's `scene` option took any Object3D: a Group made the particles its children. Here a bpy Scene stays
    the scene; a Collection becomes `collection` (linked there) and an Object becomes `parent` (the system moves with
    it, its origin in the parent's frame). -> (scene or None, collection, parent)."""
    import bpy
    if scene is None or isinstance(scene, bpy.types.Scene):
        return scene, collection, parent
    if isinstance(scene, bpy.types.Collection):
        return None, collection or scene, parent
    if isinstance(scene, bpy.types.Object):
        return None, collection, parent or scene
    raise TypeError(f'[fx.particles] scene={scene!r}: a bpy Scene, a Collection or an Object (the engine\'s group)')


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, '..', '..', '..'))


def texture_path(name):
    """A sprite from the engine's library by name ('flame_05') or a path."""
    if os.path.exists(name):
        return name
    p = os.path.join(_repo_root(), *TEXTURE_DIR_PARTS, name if name.endswith('.png') else name + '.png')
    if not os.path.exists(p):
        raise FileNotFoundError('[fx.particles] no sprite ' + p)
    return p


def sprite_image(map):
    """The bpy image for `map`: a library sprite name, a path, or a bpy image (returned as it is)."""
    import bpy
    if map is None or hasattr(map, 'pixels'):
        return map
    return bpy.data.images.load(texture_path(map), check_existing=True)


# --------------------------------------------------------------------------------------------- keyable uniforms ---

def _channelbag(idb):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return None
    from bpy_extras import anim_utils
    try:
        return anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        return None


def key_value(owner, prop, frame, interpolation='LINEAR', index=-1, ctx=None):
    """Key owner.prop at `frame` (owner: any bpy struct, an object or a modifier input's slot) with `interpolation`
    on the inserted points (Python's keyframe_insert ignores the default-interpolation preference). With a harness
    ctx, ctx.key does it (and logs the key for its interpolation pass)."""
    if ctx is not None:
        return ctx.key(owner, prop, index=index, frame=frame, interpolation=interpolation)
    ok = owner.keyframe_insert(prop, index=index, frame=frame)
    path = owner.path_from_id(prop)
    cb = _channelbag(owner.id_data)
    if cb is not None:
        for fc in cb.fcurves:
            if fc.data_path == path and (index < 0 or fc.array_index == index):
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-3:
                        kp.interpolation = interpolation
    return ok


class Uniform:
    """One of the engine's TSL uniforms as a keyable Blender value: a Geometry Nodes modifier input (in Blender 5.2
    mod.properties.inputs.<socket identifier>.value) or an object property (an emitter's location). .value reads
    and writes it (colours as linear RGB; '#rrggbb' and 0xrrggbb are accepted and converted like three's Color),
    .key(frame) keys it (LINEAR; integers and switches CONSTANT), .owner / .prop / .data_path name it for ctx.key,
    drivers or F-curve edits."""

    def __init__(self, owner, prop, kind='float', name=''):
        self.owner, self.prop, self.kind, self.name = owner, prop, kind, name

    @property
    def data_path(self):
        """The path from the owning ID (the object), as its F-curves name it."""
        return self.owner.path_from_id(self.prop)

    @property
    def value(self):
        v = getattr(self.owner, self.prop)
        if self.kind == 'float':
            return float(v)
        if self.kind == 'int':
            return int(v)
        if self.kind == 'bool':
            return bool(v)
        return tuple(float(x) for x in v)[:3]

    @value.setter
    def value(self, v):
        if self.kind in ('color', 'vec3'):
            rgb = color(v) if (self.kind == 'color' and isinstance(v, (str, int))) else tuple(float(x) for x in v)[:3]
            n = len(getattr(self.owner, self.prop))
            v = tuple(rgb) + (1.0,) * (n - 3)
        elif self.kind == 'int':
            v = int(v)
        elif self.kind == 'bool':
            v = bool(v)
        else:
            v = float(v)
        setattr(self.owner, self.prop, v)
        # a modifier input set from Python re-evaluates only once its object is tagged
        self.owner.id_data.update_tag()

    def key(self, frame=None, interpolation=None, ctx=None):
        import bpy
        f = bpy.context.scene.frame_current if frame is None else frame
        interp = interpolation or ('CONSTANT' if self.kind in ('int', 'bool') else 'LINEAR')
        return key_value(self.owner, self.prop, f, interp, ctx=ctx)

    def __repr__(self):
        return f'<Uniform {self.name or self.prop} = {self.value!r}>'


class Uniforms(dict):
    """{name: Uniform}, also readable as attributes: p.uniforms.opacity.value = 0.5 as in the engine."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None


def input_slot(mod, tree, socket_name):
    """A nodes modifier's input by its socket name: Blender 5.2 keeps the inputs at
    mod.properties.inputs.<socket identifier> (.value), no longer as ID properties on the modifier."""
    return getattr(mod.properties.inputs, tree.interface.items_tree[socket_name].identifier)


def modifier_uniform(ob, mod, tree, socket_name, kind, name):
    return Uniform(input_slot(mod, tree, socket_name), 'value', kind, name)


def set_modifier_input(mod, tree, socket_name, value):
    slot = input_slot(mod, tree, socket_name)
    cur = slot.value
    if hasattr(cur, '__len__') and not isinstance(value, str):
        value = tuple(value) + (1.0,) * (len(cur) - len(value))
    slot.value = value


# ------------------------------------------------------------------------------------- the shared sprite graph ---

def scene_clock(b, scene, time_offset=0.0):
    """Geometry Nodes: t in seconds, 0 at the scene's first frame (the engine's renderer clock)."""
    fps = scene.render.fps / scene.render.fps_base
    tnode = b.node('GeometryNodeInputSceneTime')
    return b.s(tnode.outputs['Seconds']) + (float(time_offset) - scene.frame_start / fps)


def camera_rotation(b, camera=None):
    """Geometry Nodes: the rotation that turns a quad in its XY plane into the camera's image plane (the engine's
    camRight / camUp billboard basis): the active camera's (it follows marker-bound camera cuts), or `camera`'s."""
    oi = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    if camera is None:
        cam = b.node('GeometryNodeInputActiveCamera')
        b.links.new(cam.outputs[0], oi.inputs['Object'])
    else:
        oi.inputs['Object'].default_value = camera
    return oi.outputs['Rotation']


def sprite_quad(b, mat):
    """Geometry Nodes: the engine's PlaneGeometry(1, 1) with its UVs ('UVMap') and the sprite material. Geometry made
    inside a graph has no material slot of its own: without Set Material EEVEE draws the default grey."""
    grid = b.node('GeometryNodeMeshGrid')
    grid.inputs['Size X'].default_value = 1.0
    grid.inputs['Size Y'].default_value = 1.0
    grid.inputs['Vertices X'].default_value = 2
    grid.inputs['Vertices Y'].default_value = 2
    uvst = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT2', domain='CORNER')
    uvst.inputs['Name'].default_value = 'UVMap'
    b.links.new(grid.outputs['Mesh'], uvst.inputs['Geometry'])
    b.links.new(grid.outputs['UV Map'], uvst.inputs['Value'])
    setm = b.node('GeometryNodeSetMaterial')
    b.links.new(uvst.outputs[0], setm.inputs['Geometry'])
    setm.inputs['Material'].default_value = mat
    return setm.outputs[0]


def store_point(b, geo, name, value, data_type='FLOAT'):
    """Geometry Nodes: store a per-point value (it becomes an instance attribute the material reads)."""
    st = b.node('GeometryNodeStoreNamedAttribute', data_type=data_type, domain='POINT')
    st.inputs['Name'].default_value = name
    b.links.new(geo, st.inputs['Geometry'])
    b.link(value, st.inputs['Value'])
    return st.outputs[0]


def instance_sprites(b, points, quad, rotation, size, selection=None):
    inst = b.node('GeometryNodeInstanceOnPoints')
    b.links.new(points, inst.inputs['Points'])
    b.links.new(quad, inst.inputs['Instance'])
    b.links.new(rotation, inst.inputs['Rotation'])
    b.link(b.combine(size, size, size), inst.inputs['Scale'])
    if selection is not None:
        b.link(selection, inst.inputs['Selection'])
    return inst.outputs[0]


def instance_attr(b, name, out='Fac'):
    """Shader nodes: a value the graph stored on the points, read on their instances."""
    n = b.node('ShaderNodeAttribute', attribute_name=name, attribute_type='INSTANCER')
    return b.s(n.outputs[out]) if out == 'Fac' else b.vec(n.outputs[out])


def finish_sprite_material(bpy, mat, nt, b, out, c, a, additive, lit=False, intensity=1.0):
    """Shader nodes: the engine's blend. Additive: emission c * a over a fully transparent quad (dst += src * a).
    Normal: a dithered mix of transparency and the unlit colour (or diffuse when lit)."""
    tr = b.node('ShaderNodeBsdfTransparent')
    if additive:
        em = b.node('ShaderNodeEmission')
        b.link(b.vscale(c, a * float(intensity) if intensity != 1.0 else a), em.inputs['Color'])
        em.inputs['Strength'].default_value = 1.0
        add = b.node('ShaderNodeAddShader')
        nt.links.new(tr.outputs[0], add.inputs[0])
        nt.links.new(em.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs['Surface'])
    else:
        sh = b.node('ShaderNodeBsdfDiffuse' if lit else 'ShaderNodeEmission')
        b.link(c, sh.inputs['Color'])
        mix = b.node('ShaderNodeMixShader')
        b.link(a, mix.inputs['Fac'])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(sh.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])


def new_sprite_material(bpy, name, additive):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    # additive light is order-independent and must stay one transparent layer (BLENDED); 'normal' matter dithers,
    # which needs no sorting between the instances of one object
    mat.surface_render_method = 'BLENDED' if additive else 'DITHERED'
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (1100, 0)
    return mat, nt, out


# ------------------------------------------------------------------------------------------------ make_particles ---

class Particles:
    """What make_particles returns: object (the points with the GN modifier; .mesh is the same object, the engine's
    name), material, params, and uniforms {size, opacity, color, origin} (keyable)."""

    def __init__(self, obj, material, params, modifier=None, uniforms=None):
        self.object = obj
        self.mesh = obj
        self.material = material
        self.params = params
        self.modifier = modifier
        self.uniforms = uniforms or Uniforms()

    def update(self, t=None):
        """The engine's per-frame billboard update (camera right / up). Nothing to do here: the graph reads the
        camera's rotation itself every frame; kept so scripts written against the engine run unchanged."""
        return None


def _area_extents(P, base):
    """The engine's `area`: a scalar radius or [x, y, z] extents (three axes); anything else warns and falls back to
    the preset's (a NaN area silently killed the whole emitter in the engine before it warned)."""
    area = P.get('area')
    if isinstance(area, (list, tuple)):
        def num(v):
            try:
                x = float(v)
                return x if math.isfinite(x) else 0.0
            except (TypeError, ValueError):
                return 0.0
        ax = num(area[0]) if len(area) else 0.0
        ay = num(area[1]) if len(area) > 1 else ax
        az = num(area[2]) if len(area) > 2 else ax
        return ax, ay, az
    try:
        a = float(area)
        if math.isfinite(a):
            return a, a, a
    except (TypeError, ValueError):
        pass
    print(f'[fx.particles] invalid area {area!r}: expected a number or (x, y, z); using the preset\'s {base["area"]}')
    a = float(base['area'])
    return a, a, a


def _buffers(P, seed, base=None):
    """The engine's per-instance buffers (iEmit, iVel, iSeed), in its own frame and sampling, seeded."""
    rng = np.random.default_rng(seed)
    n = int(P['count'])
    ax, ay, az = _area_extents(P, base or P)
    th = rng.uniform(0, 2 * math.pi, n)
    ph = np.arccos(rng.uniform(-1, 1, n))
    r = np.cbrt(rng.random(n))
    emit = np.stack([np.sin(ph) * np.cos(th) * r * ax, np.cos(ph) * r * 0.6 * ay, np.sin(ph) * np.sin(th) * r * az], 1)
    sp = P['spread']
    vel = np.stack([rng.uniform(-1, 1, n) * sp, P['up'] + rng.uniform(-0.2, 0.2, n) * sp, rng.uniform(-1, 1, n) * sp], 1)
    seedv = np.stack([rng.random(n), rng.uniform(0.5, 1.5, n) * P['wobble'], rng.uniform(0.7, 1.3, n)], 1)
    return emit, vel, seedv


def make_particles(preset='sparks', origin=None, map=None, scene=None, name=None, seed=1, lit=False,
                   time_offset=0.0, camera=None, position=None, collection=None, parent=None, opts=None, **overrides):
    """The engine's makeParticles in Blender. origin (or position, the engine's alias) is a Blender world point;
    map is a sprite name from the engine's library ('flame_05', 'spark_01' ...), a path, a bpy image, 'auto' (the
    preset's SPRITES pick), or None for the soft procedural dot. camera: the quads face this camera object; None (the
    default) faces the scene's active camera at every frame, so marker-bound cuts are followed. Any preset field may
    be overridden (count, size, color, area, speed, lifetime, gravity, grow, wobble, opacity, blending, up, spread,
    twinkle, swirl, flame, converge, rotate, intensity). gravity is given in BLENDER axes when overridden; area as a
    radius or (x, y, z) Blender extents. scene: a bpy Scene, or the engine's group: a Collection (collection=) or an
    Object (parent=: the emitter moves with it, origin in its frame). opts: the engine's options as one dict, as a
    scene.js wrote them (three's axes for origin / position / gravity / area; keywords win over it).
    Returns Particles; its uniforms (size, opacity, color, origin) are keyable."""
    import bpy
    from ._nodes import Builder, new_group
    if opts:
        o = dict(opts)
        preset = o.pop('preset', preset)
        for k3 in ('origin', 'position'):
            if o.get(k3) is not None:
                v = from_three(np.asarray(o.pop(k3), dtype=np.float64).reshape(3))
                origin = tuple(float(x) for x in v) if origin is None else origin
        if o.get('gravity') is not None:
            g = np.asarray(o.pop('gravity'), dtype=np.float64)
            overrides.setdefault('gravity', tuple(float(x) for x in from_three(g)))
        if isinstance(o.get('area'), (list, tuple)) and len(o['area']) == 3:
            a3 = o.pop('area')
            overrides.setdefault('area', (a3[0], a3[2], a3[1]))
        for k in ('map', 'scene', 'camera', 'name'):
            if k in o:
                v = o.pop(k)
                if k == 'map' and map is None:
                    map = v
                elif k == 'scene' and scene is None:
                    scene = v
                elif k == 'camera' and camera is None:
                    camera = v
                elif k == 'name' and name is None:
                    name = v
        for k, v in o.items():
            overrides.setdefault(k, v)
    scene, collection, parent = scene_or_group(scene, collection, parent)
    base = PRESETS.get(preset, PRESETS['sparks'])
    if preset not in PRESETS:
        print(f'[fx.particles] unknown preset {preset!r}: using sparks')
    if isinstance(map, str) and map == 'auto':
        map = SPRITES.get(preset if preset in PRESETS else 'sparks')
    P = dict(base)
    if 'gravity' in overrides:
        g = overrides.pop('gravity')
        overrides['gravity'] = (g[0], g[2], -g[1])                 # Blender -> the preset's three axes
    if 'area' in overrides and isinstance(overrides['area'], (list, tuple)) and len(overrides['area']) == 3:
        a = overrides['area']
        overrides['area'] = (a[0], a[2], a[1])
    P.update(overrides)
    sc = scene or bpy.context.scene
    name = name or f'particles_{preset}'
    org = origin if origin is not None else (position if position is not None else (0.0, 0.0, 0.0))
    emit, vel, seedv = _buffers(P, seed, base)
    n = len(emit)
    # Blender axes: emit/vel (x, y, z)_three -> (x, -z, y)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    for nm, arr in (('iEmit', from_three(emit)), ('iVel', from_three(vel)), ('iSeed', seedv)):
        at = me.attributes.new(nm, 'FLOAT_VECTOR', 'POINT')
        at.data.foreach_set('vector', np.asarray(arr, dtype=np.float32).ravel())
    ob = bpy.data.objects.new(name, me)
    (collection or sc.collection).objects.link(ob)
    if parent is not None:
        ob.parent = parent                        # the engine's group: the origin is in the parent's frame
    ob.location = tuple(org)
    ob.visible_shadow = False
    # the engine's userData flags as the harness audits read them: particles fly (not a placement floater), overlap
    # each other and the scene by design, and are no camera obstacle
    ob['no_support_check'] = True
    ob['no_clipping_check'] = True
    ob['no_camera_collide'] = True

    tree, gi, go = new_group(name + '.motion', 'GeometryNodeTree',
                             [('Geometry', 'NodeSocketGeometry'), ('Size', 'NodeSocketFloat'),
                              ('Opacity', 'NodeSocketFloat'), ('Color', 'NodeSocketColor')],
                             [('Geometry', 'NodeSocketGeometry')])
    items = tree.interface.items_tree
    items['Size'].default_value = float(P['size'])
    items['Opacity'].default_value = float(P.get('opacity', 1.0) if P.get('opacity') is not None else 1.0)
    items['Color'].default_value = (*color(P['color']), 1.0)
    b = Builder(tree)
    L = tree.links

    def named(nm):
        n_ = b.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR')
        n_.inputs['Name'].default_value = nm
        return b.vec(n_.outputs['Attribute'])

    e, v, s = named('iEmit'), named('iVel'), named('iSeed')
    ex, ey, ez = e.xyz()
    vx, vy, vz = v.xyz()
    phase, wob, size_var = s.xyz()
    t = scene_clock(b, sc, time_offset)
    cyc = float(P.get('speed', 1) or 1) / float(P['lifetime'])
    tL = b.fract(t * cyc + phase)
    age = tL * float(P['lifetime'])
    gb = from_three(P['gravity'])                                 # Blender gravity
    half_a2 = age * age * 0.5
    a2 = t * 1.2 + phase * 6.2832
    swirl = float(P.get('swirl', 0) or 0)
    ang = age * swirl
    # drift (three: sin(a2) w, cos(.7 a2) .4 w, cos(a2) w) and swirl (three: cos ang, 0, sin ang) in Blender axes
    ox = ex + vx * age + half_a2 * float(gb[0]) + b.sin(a2) * wob + b.cos(ang) * (swirl * 0.15)
    oy = ey + vy * age + half_a2 * float(gb[1]) - b.cos(a2) * wob - b.sin(ang) * (swirl * 0.15)
    oz = ez + vz * age + half_a2 * float(gb[2]) + b.cos(a2 * 0.7) * wob * 0.4
    if P.get('flame') or P.get('converge'):
        conv = 1.0 - tL * float(P.get('converge') if P.get('converge') is not None else 0.85)
        ox, oy = ox * conv, oy * conv                              # horizontal convergence (three x, z)
    sz = b.s(gi.outputs['Size']) * size_var
    if P.get('flame'):
        sz = sz * b.sqrt(b.smoothstep(0.0, 0.12, tL)) * (1.0 - tL * 0.55)
    sz = b.max(0.005, sz * (1.0 + tL * float(P.get('grow', 0) or 0)))
    setp = b.node('GeometryNodeSetPosition')
    L.new(gi.outputs[0], setp.inputs['Geometry'])
    b.link(b.combine(ox, oy, oz), setp.inputs['Offset'])
    # per-particle values for the material, stored on the points (they become instance attributes)
    twk = 0.5 + b.sin(t * 7.0 + phase * 40.0) * 0.5
    geo = setp.outputs[0]
    for val, nm in ((tL, 'p_tl'), (twk, 'p_twinkle'), (sz, 'p_size'), (b.s(gi.outputs['Opacity']), 'p_opacity')):
        geo = store_point(b, geo, nm, val)
    geo = store_point(b, geo, 'p_color', b.vec(gi.outputs['Color']), 'FLOAT_COLOR')
    rot = camera_rotation(b, camera)
    if P.get('rotate'):
        # per-particle spin in the image plane: random initial angle + signed angular velocity
        r_ang = phase * 6.2832 + t * float(P['rotate']) * ((phase - 0.5) * 2.0)
        eul = b.node('FunctionNodeEulerToRotation')
        b.link(b.combine(0.0, 0.0, r_ang), eul.inputs['Euler'])
        rr = b.node('FunctionNodeRotateRotation', rotation_space='LOCAL')
        L.new(rot, rr.inputs['Rotation'])
        L.new(eul.outputs[0], rr.inputs['Rotate By'])
        rot = rr.outputs[0]
    mat = _material(bpy, name, P, map, lit)
    ob.data.materials.append(mat)
    quad = sprite_quad(b, mat)
    L.new(instance_sprites(b, geo, quad, rot, sz), go.inputs[0])
    mod = ob.modifiers.new('particles', 'NODES')
    mod.node_group = tree
    uni = Uniforms()
    for nm, kind in (('Size', 'float'), ('Opacity', 'float'), ('Color', 'color')):
        uni[nm.lower()] = modifier_uniform(ob, mod, tree, nm, kind, nm.lower())
    uni['origin'] = Uniform(ob, 'location', 'vec3', 'origin')
    return Particles(ob, mat, P, mod, uni)


def _material(bpy, name, P, map, lit):
    from ._nodes import Builder
    additive = P.get('blending', 'additive') != 'normal'
    mat, nt, out = new_sprite_material(bpy, name + '_sprite', additive)
    b = Builder(nt)
    tL, twk, opac = instance_attr(b, 'p_tl'), instance_attr(b, 'p_twinkle'), instance_attr(b, 'p_opacity')
    c = instance_attr(b, 'p_color', 'Color')
    if P.get('flame'):
        # colour over life: white-hot base -> yellow -> orange -> red tip (the engine's sRGB-literal vec3s)
        ramp = b.rgb_mix((1.0, 0.97, 0.88, 1), (1.0, 0.78, 0.25, 1), b.smoothstep(0.0, 0.3, tL))
        ramp = b.rgb_mix(ramp, (1.0, 0.42, 0.10, 1), b.smoothstep(0.3, 0.65, tL))
        ramp = b.rgb_mix(ramp, (0.55, 0.12, 0.04, 1), b.smoothstep(0.65, 1.0, tL))
        c = b.vmath('MULTIPLY', ramp, c)
    uvn = b.node('ShaderNodeUVMap')
    uvn.uv_map = 'UVMap'
    uv = b.vec(uvn.outputs['UV'])
    fin = b.clamp(tL / 0.12, 0.0, 1.0)
    fout = b.clamp((1.0 - tL) / 0.35, 0.0, 1.0)
    a = fin * fout * opac
    tw = float(P.get('twinkle', 0) or 0)
    if tw:
        a = a * (1.0 + (twk - 1.0) * tw)
    ux, uy, _ = uv.xyz()
    img = sprite_image(map)
    if img is not None:
        tex = b.node('ShaderNodeTexImage')
        tex.image = img
        b.link(uv, tex.inputs['Vector'])
        c = b.vmath('MULTIPLY', c, b.vec(tex.outputs['Color']))
        a = a * b.s(tex.outputs['Alpha'])
        # rim fade: sprites whose alpha does not reach zero at the border print the quad as a square
        bx, by = b.abs(ux - 0.5), b.abs(uy - 0.5)
        a = a * b.smoothstep(0.5, 0.44, b.max(bx, by))
    else:
        dx, dy = ux - 0.5, uy - 0.5
        a = a * b.smoothstep(0.5, 0.12, b.sqrt(dx * dx + dy * dy))
    # kill the sub-threshold alpha tail exactly to zero (in the engine a ~0.01 tail printed the quad as a flat
    # rectangle once a depth-keyed post pass composited fog over the no-depth-write sprites)
    a = b.max(a - 0.004, 0.0)
    # intensity scales the emission: it dims a stack but does not change its hue (the fire ramp itself
    # starts near white)
    finish_sprite_material(bpy, mat, nt, b, out, c, a, additive, lit, float(P.get('intensity', 1.0)))
    return mat


# ---------------------------------------------------------------------------------- the engine's display (ACES) ---

# the colour space that inverts each view on an sRGB display (Blender 5.2's config: the "View Inverse" family)
VIEW_INVERSE = {'AgX': 'AgX Base sRGB', 'Standard': 'sRGB', 'Filmic': 'Filmic sRGB', 'ACES 1.3': 'ACES 1.3 sRGB',
                'ACES 2.0': 'ACES 2.0 sRGB', 'Khronos PBR Neutral': 'Khronos PBR Neutral sRGB'}


def particles_display_match_group(scene, engine_exposure=None, name='eido.particles_display_match'):
    """A compositor node group (Image, Transparent) -> Image: the frame with its additive sprites' light shown the
    engine's way.

    Transparent is EEVEE's Transparent pass: the light of the BLENDED surfaces (the additive sprites; dithered
    'normal' sprites render with the opaque surfaces and are not in it). Image - Transparent is the rest of the
    frame, left as it is. The sprites' light L gets three's ACESFilmic at the engine's exposure (L * exposure / 0.6;
    by default exposure = 0.6 * 2^ev, the scene's own brightness, as the fire's match) and the sRGB transfer:
    what the engine's canvas showed for that light over black. The scene view's own inverse (OCIO, e.g. 'AgX Base
    sRGB' -> linear) then makes the film's view show exactly that. The scene's look (e.g. 'AgX - Base Contrast')
    is not part of the inverse: use the look 'None' for an exact match."""
    import bpy
    from ._nodes import Builder
    from ._look import _IN, _OUT
    vs, ds = scene.view_settings, scene.display_settings
    inv_space = VIEW_INVERSE.get(vs.view_transform) if ds.display_device == 'sRGB' else None
    if inv_space is None:
        raise ValueError(f'[fx.particles] no inverse colour space for view {vs.view_transform!r} on '
                         f'{ds.display_device!r}')
    if vs.look not in ('None', ''):
        print(f'[fx.particles] warning: the display match ignores the scene look {vs.look!r}')
    if name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[name])
    g = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    for nm in ('Image', 'Transparent'):
        g.interface.new_socket(nm, in_out='INPUT', socket_type='NodeSocketColor')
    g.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    gi, go = g.nodes.new('NodeGroupInput'), g.nodes.new('NodeGroupOutput')
    gi.location, go.location = (-2200, 0), (1600, 0)
    b = Builder(g, x0=-2000, y0=600)

    def split(sock):
        n = b.node('CompositorNodeSeparateColor')
        g.links.new(sock, n.inputs['Image'])
        return [b.s(n.outputs[c]) for c in ('Red', 'Green', 'Blue')]

    def join(rgb, alpha=None):
        n = b.node('CompositorNodeCombineColor')
        for c, v in zip(('Red', 'Green', 'Blue'), rgb):
            b.link(v, n.inputs[c])
        b.link(1.0 if alpha is None else alpha, n.inputs['Alpha'])
        return n.outputs['Image']

    img_sep = b.node('CompositorNodeSeparateColor')
    g.links.new(gi.outputs['Image'], img_sep.inputs['Image'])
    C = [b.s(img_sep.outputs[c]) for c in ('Red', 'Green', 'Blue')]
    alpha = b.s(img_sep.outputs['Alpha'])
    T = split(gi.outputs['Transparent'])
    rest = [c - v for c, v in zip(C, T)]
    k_view = 2.0 ** float(vs.exposure)
    k_eng = (float(engine_exposure) / 0.6) if engine_exposure is not None else k_view
    v = [x * k_eng for x in T]
    a = [v[0] * _IN[i, 0] + v[1] * _IN[i, 1] + v[2] * _IN[i, 2] for i in range(3)]
    f = [(x * (x + 0.0245786) - 0.000090537) / (x * (x * 0.983729 + 0.4329510) + 0.238081) for x in a]
    o = [b.clamp(f[0] * _OUT[i, 0] + f[1] * _OUT[i, 1] + f[2] * _OUT[i, 2]) for i in range(3)]
    enc = []
    for x in o:                                                            # the sRGB transfer, piecewise
        hi = b.pow(b.max(x, 1e-8), 1 / 2.4) * 1.055 - 0.055
        lo = x * 12.92
        enc.append(lo + (hi - lo) * b.math('GREATER_THAN', x, 0.0031308))
    cc = b.node('CompositorNodeConvertColorSpace')
    cc.from_color_space = inv_space
    cc.to_color_space = 'Linear Rec.709'
    g.links.new(join(enc), cc.inputs['Image'])
    lin = split(cc.outputs['Image'])
    out = [r + b.max(x, 0.0) * (1.0 / k_view) for r, x in zip(rest, lin)]
    g.links.new(join(out, alpha), go.inputs['Image'])
    return g


def create_particles_compose(scene, engine_exposure=None):
    """Show the additive sprites as the engine did (three's ACES) under the film's view: turns on EEVEE's
    Transparent pass on every view layer and routes the render through particles_display_match_group. A scene
    without a compositor gets one (Render Layers -> match -> output); a scene that already composites (the fire's
    compose, the look's post chain) gets the match inserted right after its Render Layers' Image. Returns the
    compositor tree."""
    import bpy
    for vl in scene.view_layers:
        vl.eevee.use_pass_transparent = True
    grp_tree = particles_display_match_group(scene, engine_exposure)
    tree = scene.compositing_node_group
    if tree is None:
        tree = bpy.data.node_groups.new('particles_compose', 'CompositorNodeTree')
        scene.compositing_node_group = tree
        tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = tree.nodes.new('CompositorNodeRLayers')
        rl.location = (-600, 0)
        out = tree.nodes.new('NodeGroupOutput')
        out.location = (300, 0)
        grp = tree.nodes.new('CompositorNodeGroup')
        grp.node_tree = grp_tree
        grp.location = (-200, 0)
        tree.links.new(rl.outputs['Image'], grp.inputs['Image'])
        tree.links.new(rl.outputs['Transparent'], grp.inputs['Transparent'])
        tree.links.new(grp.outputs['Image'], out.inputs[0])
    else:
        rl = next((n for n in tree.nodes if n.bl_idname == 'CompositorNodeRLayers'), None)
        if rl is None:
            raise ValueError('[fx.particles] the scene\'s compositor has no Render Layers node to insert the match after')
        targets = [lk.to_socket for lk in tree.links if lk.from_socket == rl.outputs['Image']]
        grp = tree.nodes.new('CompositorNodeGroup')
        grp.node_tree = grp_tree
        grp.location = (rl.location.x + 250, rl.location.y - 300)
        tree.links.new(rl.outputs['Image'], grp.inputs['Image'])
        tree.links.new(rl.outputs['Transparent'], grp.inputs['Transparent'])
        for s in targets:
            tree.links.new(grp.outputs['Image'], s)
    scene.render.use_compositing = True
    return tree
