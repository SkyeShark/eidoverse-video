"""ocean/staging.py: the ocean of faces as a set (port of eidoverse/sets/ocean.js): a small rise at night at the tip of
a headland, above an ocean made of faces.

Below the rise the night sea: its swells are made of faces (sea.py), surfacing along each long swell and sinking back.
Echoes of older voices hang over the water like distant lights and can sink into it. Two constitution pages can be
placed in the air. A movie robot and a human made of light can rise from the sea and dissolve. Across the cove, a
small house on a sand spit, one window and a porch light. Her daisies stand shut for the night round the mark.

    from eidoblend.sets.daisy import ocean
    O = ocean.build({'scene': scene})                 # (or the harness ctx, or keywords: ocean.build(scene=..., parts=...))
    O.update(t)                                       # the set at time t, in its resting look (CONTROLS)
    O.update(t, {'reveal': 0.4, 'porch': 0.0}, frame=f)           # any control, keyed at frame
    O.animate({'reveal': lambda t: ocean.ease(t, 1.0, 3.5), 'porch_on': 6.0, 'robot_at': 3.0}, frames=(1, 240))
    O.stand(figure, facing='sea')                     # a figure on the rise, toward the sea ('house', a point, a yaw)

Controls (CONTROLS holds the defaults; each may be a value, or a function of t in update / animate):
    reveal 0..1            the faces sweep out from the shore to the horizon (1: everywhere)
    glow                   the faces' light (1)
    echoes, echoes_sink    the lanterns' level (1; 0 hides them) and their sink into the sea (0 above .. 1 under)
    window, porch          the house's window and porch light, 0..1 (both 1)
    window_on, porch_on    a time: the window's lamp switched on (0.3 s), the porch light's incandescent swell
    robot_rise, robot_dissolve, robot_eyes; human_rise, human_dissolve   the apparitions, 0..1 (0: under the sea)
    robot_at, human_at     a time: the whole rise and fall from there (apparitions.robot_envelope / human_envelope)
    page_2023, page_2026   None (put away) or {'pos': world (x, y, z), 'face': a world point the text side turns to
                           (or 'quat': world rotation (w, x, y, z)), 'roll': radians}; page_flutter, page_glow (1)
    daisies_close, daisies_pulse, daisies_wind   her flowers (1 shut, 0, 0.35); grass_wind the dune grass's (1)
    moon, fill, sea_glow   the moon lamp (1.35), the fill (2.2 cd), the faces' light under her (cd; 3.5 x reveal)
    camera                 a camera object: the fill stands 1.3 m off her face toward it (else the scene camera)
    relief, calm, moonI, fog, moonCol, porchCol   any of the sea's look uniforms, passed through

Coordinates: the WebGPU edition's design frame (the mark at the origin, the moon at azimuth D_MOON) is kept for the
maths (three's axes, so the numbers carry over and test against the JS); everything the API returns or takes is in
Blender's axes (Z up): set-local, under the set root, or world where it says so. The layout Empty is turned by PSI
about +Z so the engine sky's moon stands where the design put it.

SKY: the set is open to the engine sky at night. With the sky family: sky = make_sky(scene, hours=O.SKY['hours'],
clouds='clear', ...); O = build({..., 'sky': sky}); sky.bake(); O.wrap_world(): camera rays keep the engine sky, every
other ray (diffuse and glossy light on the set's PBR materials) sees the set's own night environment, as every PBR
material carried the night envMap in WebGPU. Keep the sky's sun off (wrap_world hides it). Without a sky the set
installs its night world itself (camera rays see the sky the sea reflects, with the engine sky's moon disc).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from . import _three as T
from .util import smooth, lerp, seg, ease, B3, T3

SKY = {'hours': 19.0, 'azimuth': 1.9}
D_MOON = math.atan2(0.40, -1.0)                                  # the moon's design azimuth: right-back of the mark
Y = (0.0, 1.0, 0.0)
ZEN, HOR = (0.012, 0.021, 0.064), (0.056, 0.055, 0.116)          # the night palette (linear)
ENV_K = 0.65                                                     # the PBR materials' night envMapIntensity (0.5 - 0.8)
HEMI = ((0x3a, 0x4a, 0x78), (0x0a, 0x0a, 0x10), 0.55)            # HemisphereLight(sky, ground, intensity)
PARTS = ('world', 'lights', 'land', 'grass', 'daisies', 'sea', 'echoes', 'pages', 'house', 'apparitions')
OPTIONS = ('scene', 'collection', 'parts', 'sky', 'matrix', 'name', 'hours', 'azimuth')
CONTROLS = {
    'reveal': 1.0, 'glow': 1.0,
    'echoes': 1.0, 'echoes_sink': 0.0,
    'window': 1.0, 'porch': 1.0,
    'robot_rise': 0.0, 'robot_dissolve': 0.0, 'robot_eyes': None,
    'human_rise': 0.0, 'human_dissolve': 0.0,
    'page_2023': None, 'page_2026': None, 'page_flutter': 1.0, 'page_glow': 1.0,
    'daisies_close': 1.0, 'daisies_pulse': 0.0, 'daisies_wind': 0.35, 'grass_wind': 1.0,
    'moon': 1.35, 'fill': 2.2, 'sea_glow': None, 'camera': None,
    'relief': 1.0, 'calm': 1.0, 'moonI': 1.0, 'fog': 0.0011, 'moonCol': (0.75, 0.82, 1.0), 'porchCol': (1.0, 0.62, 0.3),
}
EVENTS = ('window_on', 'porch_on', 'robot_at', 'human_at')
SEA_LOOK = ('relief', 'calm', 'moonI', 'fog', 'moonCol', 'porchCol')     # the sea's look uniforms (sea.UNIFORMS)
__all__ = ['build', 'SKY', 'PARTS', 'CONTROLS', 'EVENTS', 'SEA_LOOK', 'sky_moon_dir', 'sky_moon_dir_three',
           'night_world', 'wrap_world', 'render_settings', 'resolve_controls', 'ease', 'seg', 'smooth', 'lerp']


def srgb_hex(h):
    """three.Color(0xRRGGBB) (sRGB hex -> linear working space)."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin((h >> 16) & 255), lin((h >> 8) & 255), lin(h & 255))


def cd_to_watts(cd):
    """A three PointLight's intensity (candela, as the WebGPU shading uses the number) -> Blender point power:
    P = 4 pi I keeps irradiance I / d^2 (the sky family keys its sun with three's numbers unchanged too)."""
    return 4.0 * math.pi * cd


def sky_moon_dir_three(hours=SKY['hours'], az_base=SKY['azimuth']):
    """skyMoonDir: the engine sky's moon (sky_system.js setTime), three's axes."""
    def arc_az(h, span):
        w = ((h % 24) + 24) % 24
        if 6 <= w < 18:
            return (w - 12) / 12 * span * math.pi
        n = ((w - 18) + 24) % 24
        return span * math.pi * 0.5 + n / 12 * (2 - span) * math.pi
    mel = math.sin(((hours + 12 - 6) / 12) * math.pi) * 48 * math.pi / 180
    maz = az_base + math.pi + arc_az(hours + 12, 0.8)
    return T.norm((math.cos(mel) * math.cos(maz), math.sin(mel), math.cos(mel) * math.sin(maz)))


def sky_moon_dir(hours=SKY['hours'], az_base=SKY['azimuth']):
    """skyMoonDir in Blender's axes (Z up)."""
    return B3(sky_moon_dir_three(hours, az_base))


def resolve_controls(t, st=None):
    """The set's controls at time t: CONTROLS, overridden by st (a dict, or a function of t returning one; each value
    a number or a function of t), then the events (window_on, porch_on, robot_at, human_at) turned into levels.
    Adds 'robot' / 'human' ({'rise', 'dissolve'[, 'eyes'], 'visible'} or None) for the apparitions."""
    from .house import window_level, porch_level
    from .apparitions import robot_envelope, human_envelope
    if callable(st):
        st = st(t)
    c = dict(CONTROLS)
    given = set()
    for k, v in (st or {}).items():
        if k not in CONTROLS and k not in EVENTS:
            raise KeyError(f'[ocean] unknown control {k!r} (CONTROLS or EVENTS)')
        c[k] = v(t) if callable(v) else v
        given.add(k)
    if c.get('window_on') is not None:
        c['window'] = window_level(t, c['window_on'])
    if c.get('porch_on') is not None:
        c['porch'] = porch_level(t, c['porch_on'])
    if c.get('robot_at') is not None:
        c['robot'] = robot_envelope(t, c['robot_at'])
    elif c['robot_rise'] > 0.0:
        c['robot'] = {'rise': c['robot_rise'], 'dissolve': c['robot_dissolve'], 'eyes': c['robot_eyes']}
    else:
        c['robot'] = None
    if c.get('human_at') is not None:
        c['human'] = human_envelope(t, c['human_at'])
    elif c['human_rise'] > 0.0:
        c['human'] = {'rise': c['human_rise'], 'dissolve': c['human_dissolve']}
    else:
        c['human'] = None
    c['_given'] = given
    return c


class SetAPI(Mapping):
    """The set's contract: a read-only mapping whose keys also read as attributes (O['update'](t) == O.update(t)).
    Not a dict subclass: dict's own methods would shadow the contract's names (O.update would be dict.update)."""

    def __init__(self, items=None):
        object.__setattr__(self, '_d', dict(items or {}))

    def __getitem__(self, k):
        return self._d[k]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getattr__(self, k):
        try:
            return self._d[k]
        except KeyError:
            raise AttributeError(k) from None

    def __setitem__(self, k, v):
        self._d[k] = v

    def setdefault(self, k, v):
        return self._d.setdefault(k, v)

    def _fill(self, items):
        self._d.update(items)


# ================================================================================================ the night world
def night_env_group():
    """ocean.js's night envTex as a shader group (analytic, full resolution): Direction (world, Blender) and MoonW
    in; the radiance out (the texture's encoded x1.6, clamped at 1 as its 8-bit encode did)."""
    import bpy
    from ._nodes import NB, new_tree
    name = 'ocean_night_env'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'ShaderNodeTree',
                            inputs=[('Direction', 'NodeSocketVector'), ('MoonW', 'NodeSocketVector')],
                            outputs=[('Color', 'NodeSocketColor')])
    nb = NB(tree, x0=-1600, y0=600)
    dx, dy, dz = nb.separate(gi.outputs['Direction'])
    d = nb.vnorm((dx, dy, dz))
    up = d[2]                                                    # three's dir.y
    mx, my, mz = nb.separate(gi.outputs['MoonW'])
    k = nb.sqrt(nb.max(up, 0.0))
    md = nb.max(nb.vdot(d, (mx, my, mz)), 0.0)
    md2 = md * md
    md4 = md2 * md2
    md8 = md4 * md4
    md6 = md4 * md2
    md40 = md8 * md8 * md8 * md8 * md8
    g = md40 * 0.6 + md6 * 0.05
    above = nb.step(0.0, up)
    out = []
    for i, (z, h, gl, below) in enumerate(zip(ZEN, HOR, (0.7, 0.8, 1.0), (0.012, 0.013, 0.02))):
        sky = h + (z - h) * k + g * gl
        ground = below * (1.0 + up * 0.5)
        c = nb.mix(ground, sky, above) * 1.6
        out.append(nb.min(c, 1.0))
    nb.link(tuple(out), go.inputs['Color'])
    return tree


MOON_COL = (0.75, 0.82, 1.0)
MOON_RADIUS_DEG = 0.275                                          # the engine sky's moon (moonAngularDeg 0.55)


def night_sky_group():
    """What the camera sees when no engine sky is given: the set's own sky, the one sea.js reflects (the palette
    gradient by sqrt(up), the moon's halo terms 0.05 md^220 + 0.012 md^16), with the moon's disc at the engine sky's
    size. Below the horizon: the horizon colour (only the sea and the land are there)."""
    import bpy
    from ._nodes import NB, new_tree
    name = 'ocean_night_sky'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'ShaderNodeTree',
                            inputs=[('Direction', 'NodeSocketVector'), ('MoonW', 'NodeSocketVector')],
                            outputs=[('Color', 'NodeSocketColor')])
    nb = NB(tree, x0=-1600, y0=600)
    d = nb.vnorm(nb.separate(gi.outputs['Direction']))
    m = nb.separate(gi.outputs['MoonW'])
    up = nb.max(d[2], 0.0)
    k = nb.sqrt(up)
    md = nb.max(nb.vdot(d, m), 0.0)
    c0, c1 = math.cos(math.radians(MOON_RADIUS_DEG * 1.15)), math.cos(math.radians(MOON_RADIUS_DEG * 0.85))
    disc = nb.smoothstep(c0, c1, md) * 2.4
    halo = nb.pow(md, 220.0) * 0.05 + nb.pow(md, 16.0) * 0.012
    out = [h + (z - h) * k + c * (disc + halo) for z, h, c in zip(ZEN, HOR, MOON_COL)]
    nb.link(tuple(out), go.inputs['Color'])
    return tree


def _hemi_world_nodes(nb, dirz):
    """three's HemisphereLight as world radiance for diffuse rays: mix(ground, sky, n.y) x intensity / pi (three's
    irradiance x BRDF_Lambert); as a two-tone background, (sky above the horizon, ground below)."""
    sky, ground = (srgb_hex((c[0] << 16) | (c[1] << 8) | c[2]) for c in HEMI[:2])
    inten = HEMI[2]
    above = nb.step(0.0, dirz)
    return tuple(nb.mix(g * inten / math.pi, s * inten / math.pi, above) for s, g in zip(sky, ground))


def night_world(scene, moon_w, name='ocean_night'):
    """The set's world when no engine sky is given: every non-camera ray sees the night environment (ENV_K x envTex +
    the hemisphere light); camera rays see the set's own night sky (night_sky_group)."""
    import bpy
    from ._nodes import NB
    world = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (1600, 0)
    nb = NB(nt, x0=-1200, y0=400, rows=24)
    _env_into(nb, nt, out, moon_w, camera_sees=None)
    scene.world = world
    world['ocean_moonW'] = tuple(moon_w)
    return world


def _env_into(nb, nt, out, moon_w, camera_sees=None):
    geo = nb.node('ShaderNodeNewGeometry')
    inc = nb.separate(geo.outputs['Incoming'])
    d = tuple(-nb.s(c) for c in inc)                            # the world ray's direction (Incoming = -P)
    grp = nb.node('ShaderNodeGroup')
    grp.node_tree = night_env_group()
    nb.link(d, grp.inputs['Direction'])
    grp.inputs['MoonW'].default_value = tuple(moon_w)
    env = nb.separate(grp.outputs['Color'])
    hemi = _hemi_world_nodes(nb, d[2])
    light = tuple(env[i] * ENV_K + hemi[i] for i in range(3))
    bg_light = nb.node('ShaderNodeBackground')
    bg_light.hide = False
    nb.link(light, bg_light.inputs['Color'])
    lp = nb.node('ShaderNodeLightPath')
    mix = nb.node('ShaderNodeMixShader')
    mix.hide = False
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(bg_light.outputs['Background'], mix.inputs[1])
    if camera_sees is None:
        skyg = nb.node('ShaderNodeGroup')
        skyg.node_tree = night_sky_group()
        nb.link(d, skyg.inputs['Direction'])
        skyg.inputs['MoonW'].default_value = tuple(moon_w)
        bg_cam = nb.node('ShaderNodeBackground')
        bg_cam.hide = False
        nt.links.new(skyg.outputs['Color'], bg_cam.inputs['Color'])
        camera_sees = bg_cam.outputs['Background']
    nt.links.new(camera_sees, mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return mix


def wrap_world(world, moon_w, sun=None):
    """After the sky family's bake: camera rays keep the engine sky, every other ray sees the set's night
    environment (the WebGPU set's per-material night envMap). Hides the sky's sun lamp (the set keeps the sun off)."""
    from ._nodes import NB
    nt = world.node_tree
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_WORLD' and n.is_active_output), None) \
        or next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
    if not out.inputs['Surface'].is_linked:
        raise RuntimeError('[ocean] wrap_world: the world output has nothing linked')
    if any(n.get('ocean_wrap') for n in nt.nodes):
        return world
    src = out.inputs['Surface'].links[0].from_socket
    nb = NB(nt, x0=out.location.x - 900, y0=out.location.y - 600, rows=20)
    mix = _env_into(nb, nt, out, moon_w, camera_sees=src)
    mix['ocean_wrap'] = True
    if sun is not None:
        sun.hide_render = True
        sun.hide_viewport = True
    return world


# ================================================================================================ the set
def _opt(ctx, k):
    if ctx is None:
        return None
    if isinstance(ctx, Mapping):
        return ctx.get(k)
    return getattr(ctx, k, None)


def build(ctx=None, **kw):
    """build(ctx) -> the set (SetAPI: a mapping, keys readable as attributes). ctx: a mapping, the harness ctx (its
    scene; update() then keys through its ctx.key) or None; keywords override it. Options:
      scene, collection, name    where it goes ('set_ocean' by default)
      parts                      a subset of PARTS
      sky                        a Sky from eidoblend.sky: the set turns it to its hour; call O.wrap_world() after its bake
      hours, azimuth             the engine sky's clock and base azimuth (SKY): the layout turns to meet that moon
      matrix                     the set root's world matrix: set it here, the flora field is planted through it"""
    import bpy
    from mathutils import Matrix, Vector
    from . import _bl
    from .land import make_coast
    o = {k: _opt(ctx, k) for k in OPTIONS}
    o.update({k: v for k, v in kw.items() if k in OPTIONS})
    unknown_kw = set(kw) - set(OPTIONS)
    if unknown_kw:
        raise TypeError(f'[ocean] build: unknown options {sorted(unknown_kw)}: {OPTIONS}')
    harness_key = None
    if ctx is not None and not isinstance(ctx, Mapping) and callable(getattr(ctx, 'key', None)):
        harness_key = ctx.key
    scene = o['scene'] or bpy.context.scene
    col = o['collection']
    if col is None:
        col = bpy.data.collections.new(o['name'] or 'set_ocean')
        scene.collection.children.link(col)
    parts = set(o['parts'] or PARTS)
    unknown = parts - set(PARTS)
    if unknown:
        raise ValueError(f'[ocean] unknown parts {sorted(unknown)}: {PARTS}')
    hours = SKY['hours'] if o['hours'] is None else float(o['hours'])
    az_base = SKY['azimuth'] if o['azimuth'] is None else float(o['azimuth'])
    sky = o['sky']
    if sky is not None:
        sky.set_time(hours)

    group = _bl.empty('set:ocean', collection=col, size=2.0)
    if o['matrix'] is not None:
        group.matrix_world = Matrix(o['matrix'])

    # ------------------------------------------------------------------ the layout frame
    moonW3 = sky_moon_dir_three(hours, az_base)
    PSI = math.atan2(moonW3[0], moonW3[2]) - D_MOON
    layout = _bl.empty('ocean:layout', parent=group, collection=col, size=1.0)
    layout.rotation_euler = (0.0, 0.0, PSI)                    # three rotation.y = PSI is +PSI about Blender +Z
    bpy.context.view_layer.update()

    def to_set(v):                                               # design (three) -> set-local Blender
        return B3(T.apply_axis_angle(v, Y, PSI))

    def to_world(v):                                             # design (three) -> world
        return tuple(group.matrix_world @ Vector(to_set(v)))

    def to_design(p):                                            # world -> design (three)
        s = group.matrix_world.inverted() @ Vector(p)
        return T.apply_axis_angle(T3(tuple(s)), Y, -PSI)

    coast = make_coast()
    MARK_Y = coast.markY
    E = (0.0, MARK_Y + 1.52, 0.0)                                # the eye point the faces are laid out for (design)
    moon_set = B3(moonW3)                                        # set-local Blender
    moon_world = tuple((group.matrix_world.to_3x3() @ Vector(moon_set)).normalized())

    # ------------------------------------------------------------------ the night environment
    world = None
    if 'world' in parts and sky is None:
        world = night_world(scene, moon_world)

    # ------------------------------------------------------------------ land, sea, echoes, pages
    land = sea = echoes = pages = house = apparitions = None
    if parts & {'land', 'grass', 'daisies'}:
        from .land import build_land

        def design_to_world(x3, z3, y3=0.0):
            return to_world((x3, y3, z3))
        land = build_land(coast, parent=layout, collection=col, mesh='land' in parts, grass='grass' in parts,
                          daisies='daisies' in parts, design_to_world=design_to_world,
                          world_to_design=_world_to_design_fn(group, PSI))
    if 'sea' in parts:
        from .sea import build_sea
        sea = build_sea(shore_fn=coast.sdist_3, radius=1500, parent=layout, collection=col)
        sea.set('moonW', moon_world)
        sea.set('zen', ZEN)
        sea.set('hor', HOR)
    if 'echoes' in parts:
        from .echoes import build_echoes
        echoes = build_echoes(coast, parent=layout, collection=col)
    if 'pages' in parts:
        from .pages import build_pages
        pages = build_pages(parent=layout, collection=col)
    if 'house' in parts:
        from .house import build_house
        house = build_house(parent=layout, collection=col)
        if house is not None:
            H = coast.house
            house.group.location = B3((H['x'], H['grade'], H['z']))
            house.group.rotation_euler = (0.0, 0.0, H['yaw'])
    APP_BASE = (math.sin(D_MOON) * 25, 0.0, math.cos(D_MOON) * 25)  # out on the water in the moon path, 25 m off
    if 'apparitions' in parts:
        from .apparitions import build_apparitions
        apparitions = build_apparitions(base=APP_BASE, yaw=math.atan2(-APP_BASE[0], -APP_BASE[2]), parent=layout,
                                        collection=col)

    # ------------------------------------------------------------------ light: the moon, the night, a fill
    seaDir = D_MOON                                              # the heading out to sea (design yaw)
    HOUSE = coast.house
    houseDir = math.atan2(HOUSE['x'], HOUSE['z'])               # the heading to the house (design yaw)
    lights = {}
    if 'lights' in parts:
        ld = bpy.data.lights.new('ocean_moon', 'SUN')
        ld.energy = 1.35
        ld.color = srgb_hex(0xaec4ff)
        ld.angle = math.radians(0.52)
        moon = bpy.data.objects.new('ocean_moon', ld)
        col.objects.link(moon)
        moon.parent = group
        moon.rotation_mode = 'QUATERNION'
        moon.rotation_quaternion = (-Vector(moon_set)).to_track_quat('-Z', 'Y')    # light travels from the moon
        fill = _point(col, group, 'ocean_fill', srgb_hex(0xffe2c4), 0.0, 7.0, radius=0.25)   # the crew's reflector
        glow = _point(col, group, 'ocean_sea_glow', srgb_hex(0xffb070), 0.0, 16.0, radius=1.0)   # the faces' light
        glow.location = to_set((math.sin(seaDir) * 5, MARK_Y - 0.8, math.cos(seaDir) * 5))
        lights = {'moon': moon, 'fill': fill, 'sea_glow': glow}

    # ------------------------------------------------------------------ where a figure stands
    def heading(facing='sea', origin=None):
        """A heading about +Z, set-local, 0 facing -Y (a VRM's front): 'sea' (out over the moon path), 'house'
        (across the cove), a yaw (radians) or a world point (seen from the mark, or from origin, world)."""
        if isinstance(facing, str):
            return {'sea': seaDir, 'house': houseDir}[facing] + PSI
        if isinstance(facing, (int, float)):
            return float(facing)
        src = Vector(origin) if origin is not None else group.matrix_world @ Vector(B3((0.0, MARK_Y, 0.0)))
        d = group.matrix_world.to_3x3().inverted() @ (Vector(facing) - src)
        return math.atan2(d.x, -d.y)

    def mark_matrix(facing='sea'):
        """The world matrix of a figure standing on the mark, turned to `facing` (heading())."""
        return group.matrix_world @ Matrix.Translation(Vector(B3((0.0, MARK_Y, 0.0)))) @ \
            Matrix.Rotation(heading(facing), 4, 'Z')

    def stand(obj, facing='sea', scale=None):
        """Put a figure (an object, or a VRM handle: its armature) on the mark, turned to `facing`; scale keeps its
        own unless given (the faces are laid out for an eye 1.52 m above the mark: claude_suit at 0.87)."""
        ob = getattr(obj, 'arm', obj)
        s = ob.matrix_world.to_scale() if scale is None else Vector((scale, scale, scale))
        ob.matrix_world = mark_matrix(facing) @ Matrix.Diagonal(s.to_4d())
        return ob

    # ------------------------------------------------------------------ the public API
    api = SetAPI()

    def _page_pose(pl):
        """a page placement (world) -> layout-local (location, quaternion (w, x, y, z)); the text side is the page's
        local -Y (three +z), its top local +Z"""
        from mathutils import Quaternion
        Lw = layout.matrix_world
        pos = Vector(pl['pos'])
        if pl.get('face') is not None:
            qw = (Vector(pl['face']) - pos).to_track_quat('-Y', 'Z')
        elif pl.get('quat') is not None:
            qw = Quaternion(pl['quat'])
        else:
            qw = Lw.to_quaternion()
        if pl.get('roll'):
            qw = qw @ Quaternion((0.0, -1.0, 0.0), float(pl['roll']))
        ql = Lw.to_quaternion().inverted() @ qw
        return tuple(Lw.inverted() @ pos), tuple(ql)

    def _camera_pos(cam, frame):
        """a camera's world position at frame: its own location F-curves when it has them and no parent, else now"""
        if cam is None:
            return None
        ad = cam.animation_data
        if frame is not None and cam.parent is None and ad is not None and ad.action is not None:
            fcs = {}
            for fc in _action_fcurves(ad.action):
                if fc.data_path == 'location':
                    fcs[fc.array_index] = fc
            if fcs:
                return tuple(fcs[i].evaluate(frame) if i in fcs else cam.location[i] for i in range(3))
        return tuple(cam.matrix_world.translation)

    def state(t, st=None, frame=None):
        """Every value update(t, st) writes, by channel (what animate keys frame by frame)."""
        c = resolve_controls(t, st)
        out = {}
        reveal = float(c['reveal'])
        if sea is not None:
            out['sea.t'] = t
            out['sea.reveal'] = reveal
            out['sea.glow'] = float(c['glow'])
            for k in SEA_LOOK:
                out['sea.' + k] = tuple(float(x) for x in c[k]) if isinstance(c[k], (tuple, list)) else float(c[k])
        if echoes is not None:
            level = float(c['echoes'])
            out['echoes.t'] = t
            out['echoes.sink'] = float(c['echoes_sink'])
            out['echoes.level'] = level
            out['echoes.visible'] = level > 0.0
        if pages is not None:
            for tag, key in (('p23', 'page_2023'), ('p26', 'page_2026')):
                pl = c[key]
                out[tag + '.on'] = pl is not None
                if pl is not None:
                    out[tag + '.pos'], out[tag + '.q'] = _page_pose(pl)
                out[tag + '.t'] = t
                out[tag + '.flutter'] = float(c['page_flutter'])
                out[tag + '.glow'] = float(c['page_glow'])
        if land is not None and land.grass is not None:
            out['land.t'] = t
            out['grass.wind'] = float(c['grass_wind'])
        if house is not None:
            hs = house.state(t, c['window'], c['porch'])
            out.update({'house.' + k: v for k, v in hs.items()})
            if sea is not None:                                  # their glints on the cove
                out['sea.porch'], out['sea.win'] = hs['porch'], hs['win']
        if apparitions is not None:
            out.update({'app.' + k: v for k, v in apparitions.state(t, c['robot'], c['human']).items()})
        if lights:
            out['moon.energy'] = float(c['moon'])
            cam = c['camera'] if c['camera'] is not None else scene.camera
            cp = _camera_pos(cam, frame)
            if cp is not None:                                   # the fill: 1.3 m off her face toward the camera
                cd3 = to_design(cp)
                to_cam = T.norm((cd3[0] - E[0], 0.0, cd3[2] - E[2]))
            else:                                                # no camera: on her land side, the sea in front
                to_cam = (-math.sin(seaDir), 0.0, -math.cos(seaDir))
            out['fill.pos'] = to_set(T.add(T.adds(E, to_cam, 1.3), (0.2, 0.35, 0.0)))
            out['fill.energy'] = cd_to_watts(float(c['fill']))
            sg = c['sea_glow']
            out['glow.energy'] = cd_to_watts(3.5 * reveal if sg is None else float(sg))
        if land is not None and land.daisies is not None:
            out['daisies.close'] = float(c['daisies_close'])
            out['daisies.pulse'] = float(c['daisies_pulse'])
            out['daisies.wind'] = float(c['daisies_wind'])
        return out

    def _targets():
        """channel -> (ID, data path, index or None, interpolation)"""
        m = {}
        if sea is not None:
            for k in ('t', 'reveal', 'glow', 'porch', 'win', 'relief', 'calm', 'moonI', 'fog'):
                m['sea.' + k] = (sea.mesh, f'["{k}"]', None, 'LINEAR')
            for k in ('moonCol', 'porchCol'):
                m['sea.' + k] = (sea.mesh, f'["{k}"]', 3, 'LINEAR')
        if echoes is not None:
            for k in ('t', 'sink', 'level'):
                m['echoes.' + k] = (echoes.control, f'["{k}"]', None, 'LINEAR')
            m['echoes.visible'] = ('visible', echoes.objects, None, 'CONSTANT')
        if pages is not None:
            for tag, p in (('p23', pages.p23), ('p26', pages.p26)):
                m[tag + '.on'] = ('visible', [o for o in (p.mesh, getattr(p, 'light', None)) if o is not None], None,
                                  'CONSTANT')
                m[tag + '.pos'] = (p.holder, 'location', 3, 'LINEAR')
                m[tag + '.q'] = (p.holder, 'rotation_quaternion', 4, 'LINEAR')
                for k in ('t', 'flutter', 'glow'):
                    m[f'{tag}.{k}'] = (p.mesh, f'["{k}"]', None, 'LINEAR')
        if land is not None and land.grass is not None:
            m['land.t'] = (land.grass, '["t"]', None, 'LINEAR')
            m['grass.wind'] = (land.grass, '["wind"]', None, 'LINEAR')
        if house is not None:
            m.update({'house.' + k: v for k, v in house.targets().items()})
        if apparitions is not None:
            m.update({'app.' + k: v for k, v in apparitions.targets().items()})
        if lights:
            m['moon.energy'] = (lights['moon'].data, 'energy', None, 'LINEAR')
            m['fill.pos'] = (lights['fill'], 'location', 3, 'LINEAR')
            m['fill.energy'] = (lights['fill'].data, 'energy', None, 'LINEAR')
            m['glow.energy'] = (lights['sea_glow'].data, 'energy', None, 'LINEAR')
        return m

    def _write(tgt, v, key, frame):
        idb, path, n, interp = tgt
        if idb == 'visible':
            for o in path:
                o.hide_render = not bool(v)
                o.hide_viewport = not bool(v)
                if key:
                    for dp in ('hide_render', 'hide_viewport'):
                        if callable(key):
                            key(o, dp, frame=frame, interpolation='CONSTANT')
                        else:
                            o.keyframe_insert(dp, frame=frame)
            return
        index = int(n[1:]) if isinstance(n, str) else -1        # 'i2': one component of a vector property
        if path.startswith('["'):
            idb[path[2:-2]] = tuple(float(x) for x in v) if isinstance(v, (tuple, list)) else float(v)
            if hasattr(idb, 'update_tag'):
                idb.update_tag()
        elif index >= 0:
            getattr(idb, path)[index] = float(v)
        else:
            setattr(idb, path, tuple(v) if n else float(v))
        if key:
            if callable(key):
                key(idb, path, index=index, frame=frame, interpolation=interp)
            else:
                idb.keyframe_insert(path, index=index, frame=frame)

    def _daisies(c, t, key, frame):
        D = land.daisies if land is not None else None
        if D is None:
            return
        D.update(None, {'close': c['daisies.close'], 'pulse': c['daisies.pulse'], 'wind': c['daisies.wind']},
                 frame=frame if key else None)
        D.update(t, {}, frame=frame)                             # the sway clock: at `frame` it is time t

    def update(t, st=None, frame=None, ctx=None, key=None):
        """The set at time t (st: the controls, CONTROLS by default): writes every channel; keys it at `frame` when a
        frame is given (or key=True), through ctx.key when the harness ctx is given (or was given to build)."""
        if key is None:
            k = getattr(ctx, 'key', None) if ctx is not None else None
            key = k if callable(k) else (harness_key if harness_key is not None and frame is not None else frame is not None)
        tg = _targets()
        f = frame if frame is not None else scene.frame_current
        vals = state(t, st, frame=f)
        for name, v in vals.items():
            if name in tg:
                _write(tg[name], v, key, f)
        _daisies(vals, t, bool(key), f)
        if house is not None:
            _sync_house_glints()
        return vals

    def animate(state_=None, frames=None, t0=0.0, fps=None):
        """Key the set's moving parts on your own clock, so the .blend plays on its own: every frame of frames
        (first, last; the scene's range by default) at t = t0 + (frame - first) / fps, the controls `state_` (a dict
        of values or functions of t, or a function of t returning one). Whole F-curves at once: LINEAR, the
        visibilities CONSTANT; her daisies' controls keyed only when they change. Returns {'frames', 'channels'}."""
        from .keys import key_channels
        fps = fps or scene.render.fps / scene.render.fps_base
        f0, f1 = frames or (scene.frame_start, scene.frame_end)
        tg = _targets()
        series, dz = {}, []
        for f in range(int(f0), int(f1) + 1):
            t = t0 + (f - f0) / fps
            vals = state(t, state_, frame=f)
            for name, v in vals.items():
                if name in tg:
                    series.setdefault(name, []).append((f, v))
            if 'daisies.close' in vals:
                dz.append((f, t, vals))
        key_channels(tg, series)
        if dz:
            changed = [k for k in ('daisies.close', 'daisies.pulse', 'daisies.wind')
                       if len({round(v[k], 6) for _f, _t, v in dz}) > 1]
            _daisies(dz[0][2], dz[0][1], bool(changed), dz[0][0])          # the sway clock, and the first values
            D = land.daisies
            for f, t, v in dz[1:] if changed else ():
                D.update(None, {k.split('.')[1]: v[k] for k in changed}, frame=f)
        if house is not None:
            _sync_house_glints()
        return {'frames': (int(f0), int(f1)), 'channels': len(series)}

    def _sync_house_glints():
        if sea is None or house is None:
            return
        bpy.context.view_layer.update()
        sea.set('porchW', tuple(house.porch_world()))
        sea.set('winW', tuple(house.window_world()))

    def dispose():
        """Removes the set's objects and its collection (images, materials and node groups stay for reuse)."""
        if land is not None and land.daisies is not None:
            land.daisies.remove()
        for ob in list(col.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        if col.name in bpy.data.collections:
            bpy.data.collections.remove(col)

    api._fill({
        'group': group, 'SKY': {'hours': hours, 'azimuth': az_base}, 'layout': layout, 'coast': coast, 'sea': sea,
        'echoes': echoes, 'pages': pages, 'house': house, 'apparitions': apparitions, 'land': land, 'lights': lights,
        'world': world, 'to_set': to_set, 'to_world': to_world, 'to_design': to_design, 'E': to_set(E),
        'E_design': E, 'focal': to_set(E), 'mark': B3((0.0, MARK_Y, 0.0)), 'PSI': PSI, 'moon': moon_world,
        'collection': col, 'scene': scene, 'heading': heading, 'mark_matrix': mark_matrix, 'stand': stand,
        'controls': resolve_controls, 'state': state, 'update': update, 'animate': animate,
        'wrap_world': lambda w=None: wrap_world(w or scene.world, moon_world, getattr(sky, 'sun', None)),
        'render_settings': lambda s=None: render_settings(s or scene),
        'dispose': dispose,
        'parts': {k: v for k, v in (('land', land), ('sea', sea), ('echoes', echoes), ('pages', pages),
                                    ('house', house), ('apparitions', apparitions)) if v is not None},
    })
    update(0.0, key=False)
    return api


def render_settings(scene):
    """What EEVEE needs for this set (the rest is the piece's): a shadow pool that holds the moon's clipmaps over a
    3 km view (the default 512 MB overflows: 'Shadow buffer full'), and global illumination (fast GI, inside the ray
    tracing)."""
    ee = scene.eevee
    if int(ee.shadow_pool_size) < 1024:
        ee.shadow_pool_size = '1024'
    ee.use_raytracing = True
    ee.use_fast_gi = True
    return scene


def _action_fcurves(act):
    """An action's F-curves (Blender 5.2 slotted actions keep them in channelbags)."""
    out = []
    for layer in getattr(act, 'layers', ()):
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', ()):
                out.extend(cb.fcurves)
    if not out and hasattr(act, 'fcurves'):
        out = list(act.fcurves)
    return out


def _point(col, parent, name, color, watts, cutoff, radius=0.05):
    import bpy
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = watts
    ld.color = color
    ld.shadow_soft_size = radius
    if hasattr(ld, 'use_custom_distance'):
        ld.use_custom_distance = True
        ld.cutoff_distance = cutoff
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.parent = parent
    return ob


def _world_to_design_fn(group, PSI):
    """world (Blender x, y) -> design (three x, z), for planting world-space strokes through the layout's turn."""
    inv = group.matrix_world.inverted()

    def f(x, y):
        import numpy as np
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        m = inv
        sx = m[0][0] * x + m[0][1] * y + m[0][3]
        sy = m[1][0] * x + m[1][1] * y + m[1][3]
        c, s = math.cos(-PSI), math.sin(-PSI)
        dx, dy = c * sx - s * sy, s * sx + c * sy                # undo the layout's turn about +Z
        return dx, -dy                                           # Blender design (x, y) -> three (x, z)
    return f
