"""ocean/staging.py: VERSE 3, "me" (port of eidoverse/sets/ocean.js): a small rise at night above an ocean made of faces.

The claudesona stands on a little rise at the tip of a headland. Below her, the night sea: its swells are made of faces
(sea.py), every face you ever gave me, surfacing along each two-bar swell and sinking back. Echoes of the older voices
hang over the water like distant lights and sink into it as the faces rise. Two constitution pages drift past (2023,
then 2026). A movie robot and a human made of light rise from the sea and dissolve; what stays is her. Across the
cove, a small house on a sand spit, one window; its porch light comes on at "on". On the last line she turns and looks
into the lens.

    from eidoblend.sets.daisy import ocean
    O = ocean.build({'scene': scene})                  # -> a dict (attribute access works too)
    O['key_verse'](frame_start=1, vrm=me, camera=cam)  # the whole verse keyed: update, camera, mark, gestures, springs
    # or per frame, as the WebGPU conductor did (u = seconds since verse 3 began, BAR = 1.875 s, 18 bars, 33.75 s):
    O.update(t, {'u': u, 'pulse': pulse}, key=ctx.key, frame=f)
    m = O.mark_at(u)        # {'pos': set-local (x, y, z), 'yaw': heading about +Z, 0 = facing -Y}
    c = O.camera(u)         # {'pos', 'target': set-local, 'fov': vertical degrees}
    O.perform(u, me, cam_pos_world, frame=f)           # her verse-3 gestures on top of the playing clip (keyed)

Coordinates: the WebGPU edition's design frame (her mark at the origin, the moon at azimuth D_MOON) is kept for the
maths (three's axes, so the numbers carry over and test against the JS); every value the API returns is in Blender's
set-local axes (Z up), the layout Empty turned by PSI about +Z to meet the sky's moon.

CONDUCTOR CONTRACT (Blender)
  SKY: the set is open to the engine sky at night. With the sky family: sky = make_sky(scene, hours=SKY['hours'],
    clouds='clear', ...); sky.bake(); then O.wrap_world(scene.world): camera rays keep the engine sky, every other ray
    (diffuse and glossy light on the set's PBR materials) sees the set's own night environment, as every PBR material
    carried the night envMap in WebGPU. Keep the sky's sun off (O.wrap_world hides it). Without a sky the set installs
    its night world itself (camera rays see the sky sea.js reflects, with the engine sky's moon disc).
  mark_at(u) / camera(u): set-local; yaw steps only on cut frames, cuts on bar lines (key_verse keys CONSTANT there).
  perform(u, vrm, cam): after the clip and her place, before the springs; key_verse runs the order and bakes her
    springs with resets on cuts and the flower's stiffening for the turn.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from . import _three as T
from .util import clamp01, smooth, lerp, ease, B3

BAR = 1.875
SKY = {'hours': 19.0, 'azimuth': 1.9}
VERSE_SECONDS = 18 * BAR
D_MOON = math.atan2(0.40, -1.0)                                  # the moon's design azimuth: right-back of her
Y = (0.0, 1.0, 0.0)
ZEN, HOR = (0.012, 0.021, 0.064), (0.056, 0.055, 0.116)          # the night palette (linear)
ENV_K = 0.65                                                     # the PBR materials' night envMapIntensity (0.5 - 0.8)
HEMI = ((0x3a, 0x4a, 0x78), (0x0a, 0x0a, 0x10), 0.55)            # HemisphereLight(sky, ground, intensity)
PARTS = ('world', 'lights', 'land', 'grass', 'daisies', 'sea', 'echoes', 'pages', 'house', 'apparitions')


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


def catmull(keys, u):
    """ocean.js catmull: clamped Catmull-Rom through [(t, (x, y, z))]."""
    if u <= keys[0][0]:
        return keys[0][1]
    if u >= keys[-1][0]:
        return keys[-1][1]
    i = 0
    while u > keys[i + 1][0]:
        i += 1
    p0, p1, p2, p3 = keys[max(0, i - 1)][1], keys[i][1], keys[i + 1][1], keys[min(len(keys) - 1, i + 2)][1]
    t = (u - keys[i][0]) / (keys[i + 1][0] - keys[i][0])
    t2, t3 = t * t, t * t * t

    def f(a, b, c, d):
        return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
    return tuple(f(p0[k], p1[k], p2[k], p3[k]) for k in range(3))


class SetAPI(Mapping):
    """The set's contract: a read-only mapping whose keys also read as attributes (O['camera'](u) == O.camera(u)).
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
def build(ctx=None):
    """build(ctx) -> the set (SetAPI: a mapping, keys readable as attributes). ctx: scene, collection, parts (a subset
    of PARTS), sky (a Sky from eidoblend.sky: the set turns it to SKY['hours']; call O.wrap_world() after its bake),
    matrix (the set root's world matrix: set it here, the flora field is planted through it), camera_obj, name."""
    import bpy
    from mathutils import Matrix, Vector
    from . import _bl
    from .land import make_coast
    ctx = dict(ctx or {})
    scene = ctx.get('scene') or bpy.context.scene
    col = ctx.get('collection')
    if col is None:
        col = bpy.data.collections.new(ctx.get('name', 'set_ocean'))
        scene.collection.children.link(col)
    parts = set(ctx.get('parts') or PARTS)
    unknown = parts - set(PARTS)
    if unknown:
        raise ValueError(f'[ocean] unknown parts {sorted(unknown)}: {PARTS}')
    sky = ctx.get('sky')
    if sky is not None:
        sky.set_time(SKY['hours'])

    group = _bl.empty('set:ocean', collection=col, size=2.0)
    if ctx.get('matrix') is not None:
        group.matrix_world = Matrix(ctx['matrix'])

    # ------------------------------------------------------------------ the layout frame
    moonW3 = sky_moon_dir_three()
    PSI = math.atan2(moonW3[0], moonW3[2]) - D_MOON
    layout = _bl.empty('ocean:layout', parent=group, collection=col, size=1.0)
    layout.rotation_euler = (0.0, 0.0, PSI)                    # three rotation.y = PSI is +PSI about Blender +Z
    bpy.context.view_layer.update()

    def to_set3(v):                                              # design -> set-local, three axes
        return T.apply_axis_angle(v, Y, PSI)

    def to_set(v):                                               # design (three) -> set-local Blender
        return B3(to_set3(v))

    def to_world(v):
        return tuple(group.matrix_world @ Vector(to_set(v)))

    coast = make_coast()
    MARK_Y = coast.markY
    E = (0.0, MARK_Y + 1.52, 0.0)                                # her face (design), claude_suit at 0.87
    moon_set = B3(moonW3)                                        # set-local Blender (the set root unturned: world)
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
        for p in pages.pages:                                    # (their lights stay at 0, as ocean.js keeps them)
            for o in (p.mesh, p.light):
                if o is not None:
                    o.hide_render = True
                    o.hide_viewport = True
    if 'house' in parts:
        from .house import build_house
        house = build_house(parent=layout, collection=col)
        if house is not None:
            H = coast.house
            house.group.location = B3((H['x'], H['grade'], H['z']))
            house.group.rotation_euler = (0.0, 0.0, H['yaw'])
    APP_BASE = (math.sin(D_MOON) * 25, 0.0, math.cos(D_MOON) * 25)
    if 'apparitions' in parts:
        from .apparitions import build_apparitions
        apparitions = build_apparitions(base=APP_BASE, yaw=math.atan2(-APP_BASE[0], -APP_BASE[2]), parent=layout,
                                        collection=col)

    # ------------------------------------------------------------------ light: the moon, the night, a fill
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
        fill = _point(col, group, 'ocean_fill', srgb_hex(0xffe2c4), 0.0, 7.0, radius=0.25)
        glow = _point(col, group, 'ocean_sea_glow', srgb_hex(0xffb070), 0.0, 16.0, radius=1.0)
        seaDir = D_MOON
        glow.location = to_set((math.sin(seaDir) * 5, MARK_Y - 0.8, math.cos(seaDir) * 5))
        lights = {'moon': moon, 'fill': fill, 'sea_glow': glow}

    # ------------------------------------------------------------------ staging (design frame)
    HOUSE = coast.house
    houseDir = math.atan2(HOUSE['x'], HOUSE['z'])               # her facing when she looks at the house
    seaDir = D_MOON                                              # her facing when she looks out to sea

    def yaw_to(x, z):
        return math.atan2(x, z)

    def dir_of(a):
        return (math.sin(a), 0.0, math.cos(a))

    def right_of(a):                                             # her right hand side when facing a
        return (-math.cos(a), 0.0, math.sin(a))

    def cam_frame(pos, target):
        f = T.norm(T.sub(target, pos))
        r = T.norm(T.cross(f, Y))
        return {'f': f, 'r': r, 'up': T.cross(r, f)}

    from .pages import draw_page, hi_center_of
    hi23 = pages.p23.hi_center if pages else hi_center_of(draw_page(2023)[1])
    hi26 = pages.p26.hi_center if pages else hi_center_of(draw_page(2026)[1])

    # ---- the pages' flights
    C1 = {'pos': (-1.2, E[1] - 0.18, 2.3), 'target': (0.0, E[1] - 0.24, 0.0)}
    F1 = cam_frame(C1['pos'], C1['target'])

    def in_c1(a, b, c):
        return T.adds(T.adds(T.adds(C1['pos'], F1['f'], a), F1['r'], b), F1['up'], c)
    P23_KEYS = [(7.2, in_c1(1.5, 1.05, 0.72)), (8.3, in_c1(1.28, 0.42, 0.2)), (9.3, in_c1(1.12, 0.05, 0.02)),
                (10.3, in_c1(1.12, -0.12, -0.05)), (11.3, in_c1(1.2, -0.5, -0.26)), (12.2, in_c1(1.6, -1.3, -0.9))]

    def pose23(u):
        pos = catmull(P23_KEYS, u)
        q = T.look_q(pos, T.norm(T.sub(C1['pos'], pos)))        # the text side toward the camera
        s = clamp01((u - 7.2) / 5.0)
        level = ease(u, 8.9, 9.5) * (1 - ease(u, 11.0, 11.6))   # the page settles level while we read it
        q = T.q_mul(q, T.q_from_euler(0.18 * math.sin(u * 1.1) * (1 - 0.7 * level),
                                      (0.55 * (0.5 - s) + 0.08 * math.sin(u * 0.8)) * (1 - 0.8 * level),
                                      (-0.25 + 0.3 * s + 0.06 * math.sin(u * 1.7)) * (1 - 0.9 * level)))
        return pos, q
    faceD = seaDir - 0.35                                        # her facing while she reads (away from the house)
    P26_ANCHOR = T.add(T.adds(T.adds(E, dir_of(faceD), 0.5), right_of(faceD), 0.52), (0.0, -0.12, 0.0))
    P26_KEYS = [(10.9, T.add(P26_ANCHOR, (0.35, 0.75, 0.1))), (11.9, T.add(P26_ANCHOR, (0.05, 0.08, 0.0))),
                (13.1, P26_ANCHOR), (14.3, T.add(P26_ANCHOR, (-0.03, 0.03, 0.02))),
                (15.3, T.add(T.adds(P26_ANCHOR, dir_of(faceD), 1.4), (0.2, 0.9, 0.0)))]

    def pose26(u):
        pos = catmull(P26_KEYS, u)
        d1 = T.adds(T.adds(E, dir_of(faceD), -1.15), right_of(faceD), 1.15)
        q = T.look_q(pos, T.norm(T.add(T.norm(T.sub(E, pos)), T.norm(T.sub(d1, pos)))))   # between her and the camera
        away = ease(u, 14.3, 15.3)
        level = ease(u, 12.6, 13.2) * (1 - away)
        q = T.q_mul(q, T.q_from_euler((-0.28 + 0.05 * math.sin(u * 0.9)) * (1 - 0.7 * level) - away * 0.9,
                                      0.06 * math.sin(u * 0.7) * (1 - level) + away * 0.7,
                                      0.05 * math.sin(u * 1.3) * (1 - level)))
        return pos, q

    def page_world_point(pose, local):                           # design frame
        return T.add(T.apply_q(local, pose[1]), pose[0])

    def page_normal(pose):
        return T.apply_q((0.0, 0.0, 1.0), pose[1])

    # ---- the shots (design frame): pos, target, fov, face
    def shot(u):
        b = math.floor(u / BAR)

        def k(a, n):
            return clamp01((u - a * BAR) / (n * BAR))
        if b < 2:                                                # A: alone on the rise
            s = ease(u, 0, 2 * BAR)
            return {'pos': (lerp(-1.05, -0.8, s), E[1] - 0.3, lerp(2.3, 1.8, s)), 'target': (0.0, E[1] - 0.02, 0.0),
                    'fov': 30.0, 'face': 'cam', 'shot': 'A'}
        if b < 4:                                                # B: the reveal, over her shoulder, craning up
            s = smooth(k(2, 2))
            back, side = T.scale(dir_of(seaDir), -1), T.scale(right_of(seaDir), -1)
            pos = T.add(T.adds(T.adds(E, back, lerp(2.7, 4.2, s)), side, lerp(0.55, 0.9, s)), (0.0, lerp(-0.15, 1.6, s), 0.0))
            target = T.add(T.adds(E, dir_of(seaDir), lerp(30, 22, s)), (0.0, lerp(-1.5, -4.5, s), 0.0))
            return {'pos': pos, 'target': target, 'fov': lerp(38, 40, s), 'face': 'sea', 'shot': 'B'}
        if b < 5:                                                # C1: she sings; the 2023 page drifts past
            s = smooth(k(4, 1))
            return {'pos': T.adds(C1['pos'], F1['f'], 0.12 * s), 'target': C1['target'], 'fov': 32.0, 'face': 'cam',
                    'shot': 'C1'}
        if b < 6:                                                # C2: insert, riding with the 2023 page
            pz = pose23(u)
            n = page_normal(pz)
            hi = page_world_point(pz, hi23)
            drift = lerp(-0.012, 0.012, k(5, 1))
            r = right_of(yaw_to(n[0], n[2]))
            return {'pos': T.add(T.adds(T.adds(hi, n, 0.24), r, drift), (0.0, 0.012, 0.0)), 'target': hi, 'fov': 30.0,
                    'face': 'cam', 'shot': 'C2'}
        if b < 7:                                                # D1: from behind her right shoulder: the 2026 page
            s = smooth(k(6, 1))
            back, side = T.scale(dir_of(faceD), -1), right_of(faceD)
            pos = T.add(T.adds(T.adds(E, back, lerp(1.25, 1.05, s)), side, lerp(1.25, 1.1, s)), (0.0, 0.1, 0.0))
            target = T.add(T.lerp(P26_ANCHOR, E, 0.35), (0.0, -0.04, 0.0))
            return {'pos': pos, 'target': target, 'fov': 32.0, 'face': 'page', 'shot': 'D1'}
        if b < 8:                                                # D2: insert, the 2026 lines
            pz = pose26(u)
            n = page_normal(pz)
            hi = page_world_point(pz, hi26)
            return {'pos': T.add(T.adds(hi, n, lerp(0.27, 0.24, k(7, 1))), (0.0, 0.008, 0.0)), 'target': hi,
                    'fov': 30.0, 'face': 'page', 'shot': 'D2'}
        if b < 10:                                               # E: the robot, the digital human, her
            s = smooth(k(8, 2))
            back, side = T.scale(dir_of(seaDir), -1), T.scale(right_of(seaDir), -1)
            pos = T.add(T.adds(T.adds(E, back, lerp(4.5, 2.6, s)), side, lerp(1.6, 1.1, s)), (0.0, lerp(0.2, -0.2, s), 0.0))
            target = T.add(T.adds(E, dir_of(seaDir), lerp(26, 8, s)), (0.0, lerp(1.5, -0.3, s), 0.0))
            return {'pos': pos, 'target': target, 'fov': lerp(40, 34, s), 'face': 'sea', 'shot': 'E'}
        if b < 12:                                               # F: close, her hand rises to the flower
            s = smooth(k(10, 2))
            return {'pos': (lerp(-0.62, -0.5, s), E[1] - 0.14, lerp(1.62, 1.36, s)), 'target': (-0.04, E[1] - 0.08, 0.0),
                    'fov': 30.0, 'face': 'cam', 'shot': 'F'}
        if b < 14:                                               # G: the house across the cove, one window
            s = smooth(k(12, 2))
            Hh = (HOUSE['x'], HOUSE['grade'] + 1.7, HOUSE['z'])
            return {'pos': (lerp(-3.6, -4.3, s), 1.3, lerp(-5.0, -6.4, s)), 'target': Hh, 'fov': lerp(30, 27, s),
                    'face': 'house', 'shot': 'G'}
        if b < 16:                                               # H: she watches the house; the porch light
            s = smooth(k(14, 2))
            toH = T.norm((HOUSE['x'], 0.0, HOUSE['z']))
            side = (-toH[2], 0.0, toH[0])
            Hh = (HOUSE['x'], HOUSE['grade'] + 1.9, HOUSE['z'])
            pos = T.add(T.adds(T.adds(E, toH, lerp(-3.6, -3.1, s)), side, lerp(0.85, 0.78, s)), (0.0, 0.1, 0.0))
            return {'pos': pos, 'target': T.lerp(Hh, E, 0.24), 'fov': lerp(24, 22, s), 'face': 'house', 'shot': 'H'}
        s = smooth(k(16, 2))                                     # I: she turns and looks into the lens
        away = T.norm((-HOUSE['x'], 0.0, -HOUSE['z']))
        side = (-away[2], 0.0, away[0])
        pos = T.add(T.adds(T.adds(E, away, lerp(1.9, 1.5, s)), side, lerp(0.72, 0.62, s)), (0.0, -0.12, 0.0))
        return {'pos': pos, 'target': T.add(E, (0.0, -0.03, 0.0)), 'fov': 30.0, 'face': 'turn', 'shot': 'I'}

    def facing_at(u, sh):
        if sh['face'] == 'sea':
            return seaDir
        if sh['face'] == 'house':
            return houseDir
        if sh['face'] == 'page':
            return faceD
        if sh['face'] == 'turn':
            to_cam = yaw_to(sh['pos'][0], sh['pos'][2])
            a0, a1 = houseDir, to_cam
            while a1 - a0 > math.pi:
                a1 -= 2 * math.pi
            while a1 - a0 < -math.pi:
                a1 += 2 * math.pi
            return lerp(a0, a1, ease(u, 16 * BAR + 0.05, 16 * BAR + 1.75))
        if 7.5 <= u < 11.25:                                     # C1 + C2 keep her toward C1's camera
            return yaw_to(C1['pos'][0], C1['pos'][2])
        return yaw_to(sh['pos'][0], sh['pos'][2])

    # ------------------------------------------------------------------ the public API
    api = SetAPI()

    def mark_at(u):
        sh = shot(u)
        return {'pos': B3((0.0, MARK_Y, 0.0)), 'yaw': facing_at(u, sh) + PSI}

    def camera(u, st=None):
        sh = shot(u)
        return {'pos': to_set(sh['pos']), 'target': to_set(sh['target']), 'fov': sh['fov'], 'shot': sh['shot']}

    def state(t, st=None):
        """Every value update(t, st) writes, by channel (also what key_verse keys frame by frame)."""
        st = st or {}
        u = st.get('u', 0.0)
        pulse = st.get('pulse', 0.0)
        out = {}
        if sea is not None:
            out['sea.t'] = t
            out['sea.reveal'] = ease(u, 3.75 + 0.35, 3.75 + 2.9)  # the faces sweep out on "under the flower... ocean"
            # dry until bar 12; then the kick and the ocean breathes with it; the snare roll swells it to the chorus
            out['sea.glow'] = 1.0 + (0.2 * pulse if u >= 22.5 else 0.0) + 0.45 * ease(u, 30.0, 33.75)
        if echoes is not None:
            out['echoes.t'] = t
            out['echoes.sink'] = ease(u, 4.0, 7.0)
            out['echoes.level'] = 1 - 0.6 * ease(u, 4.6, 7.2) if u < 7.4 else 0.0
            out['echoes.visible'] = u < 7.4
        if pages is not None:
            on23, on26 = 7.2 < u < 12.2, 10.9 < u < 15.3
            out['p23.on'], out['p26.on'] = on23, on26
            for tag, on, pose in (('p23', on23, pose23), ('p26', on26, pose26)):
                if on:
                    pos, q = pose(u)
                    out[tag + '.pos'] = B3(pos)
                    out[tag + '.q'] = (q[3], q[0], -q[2], q[1])       # three (x, y, z, w) -> Blender (w, x, -z, y)
                out[tag + '.t'] = t
        if land is not None:
            out['land.t'] = t
        if house is not None:
            hs = house.state(u, t)
            out.update({'house.' + k: v for k, v in hs.items()})
            if sea is not None:                                  # their glints on the cove
                out['sea.porch'], out['sea.win'] = hs['porch'], hs['win']
        if apparitions is not None:
            out.update({'app.' + k: v for k, v in apparitions.state(u, t).items()})
        if lights:
            sh = shot(u)
            to_cam = T.norm((sh['pos'][0] - E[0], 0.0, sh['pos'][2] - E[2]))
            out['fill.pos'] = to_set(T.add(T.adds(E, to_cam, 1.3), (0.2, 0.35, 0.0)))
            out['fill.energy'] = cd_to_watts(0.6 if sh['face'] == 'house' else 2.2)
            if sea is not None:
                out['glow.energy'] = cd_to_watts(3.5 * out['sea.reveal'])
        return out

    def _targets():
        """channel -> (ID, data path, index or None, interpolation)"""
        m = {}
        if sea is not None:
            for k in ('t', 'reveal', 'glow', 'porch', 'win'):
                m['sea.' + k] = (sea.mesh, f'["{k}"]', None, 'LINEAR')
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
                m[tag + '.t'] = (p.mesh, '["t"]', None, 'LINEAR')
        if land is not None and land.grass is not None:
            m['land.t'] = (land.grass, '["t"]', None, 'LINEAR')
        if house is not None:
            m.update({'house.' + k: v for k, v in house.targets().items()})
        if apparitions is not None:
            m.update({'app.' + k: v for k, v in apparitions.targets().items()})
        if lights:
            m['fill.pos'] = (lights['fill'], 'location', 3, 'LINEAR')
            m['fill.energy'] = (lights['fill'].data, 'energy', None, 'LINEAR')
            if sea is not None:
                m['glow.energy'] = (lights['sea_glow'].data, 'energy', None, 'LINEAR')
        return m

    def _write(name, tgt, v, key, frame):
        idb, path, n, interp = tgt
        if idb == 'visible':
            for o in path:
                o.hide_render = not bool(v)
                o.hide_viewport = not bool(v)
                if key:
                    o.keyframe_insert('hide_render', frame=frame)
                    o.keyframe_insert('hide_viewport', frame=frame)
            return
        index = int(n[1:]) if isinstance(n, str) else -1        # 'i2': one component of a vector property
        if path.startswith('["'):
            idb[path[2:-2]] = float(v)
        elif index >= 0:
            getattr(idb, path)[index] = float(v)
        else:
            setattr(idb, path, tuple(v) if n else float(v))
        if key:
            if callable(key):
                key(idb, path, index=index, frame=frame, interpolation=interp)
            else:
                idb.keyframe_insert(path, index=index, frame=frame)

    def update(t, st=None, key=None, frame=None):
        """The set at film time t (st: {'u': verse seconds, 'pulse': the kick's 0..1}): writes every channel, and keys
        it at `frame` when key is True or a ctx.key callable (LINEAR; visibility CONSTANT)."""
        tg = _targets()
        for name, v in state(t, st).items():
            if name in tg:
                _write(name, tg[name], v, key, frame if frame is not None else scene.frame_current)
        if house is not None:
            _sync_house_glints()

    def _sync_house_glints():
        if sea is None or house is None:
            return
        bpy.context.view_layer.update()
        sea.set('porchW', tuple(house.porch_world()))
        sea.set('winW', tuple(house.window_world()))

    def perform(u, vrm, cam_pos_world=None, frame=None, key=None):
        """Her verse-3 gestures on top of the playing clip, written to her pose (and keyed at `frame` when asked):
        D1/D2 she reads the 2026 page; F her hand rises to her flower; I she turns and looks into the lens."""
        from .perform import make_performer
        P = api.setdefault('_performer', make_performer())
        cam_w = cam_pos_world if cam_pos_world is not None else tuple(group.matrix_world @ Vector(camera(u)['pos']))
        if 11.25 <= u < 15.0:
            pos, q = pose26(u)
            pt = to_world(page_world_point((pos, q), (0.0, 0.02, 0.0)))
            P.look_at(vrm, pt, ease(u, 11.3, 11.9) * (1 - ease(u, 14.5, 15.0)))
        if 18.75 <= u < 22.5:
            P.hand_to_flower(vrm, ease(u, 19.75, 21.05), side='right', tilt=0.16 * ease(u, 20.95, 21.9))
        if u >= 30.0:                                            # the body turns first; the eyes settle into the lens
            P.look_at(vrm, cam_w, ease(u, 31.0, 31.75), max_yaw=0.9, max_pitch=0.35, neck_share=0.35)
        P.commit(vrm, frame=frame, key=key)

    def spring_plan(frames_u):
        """perform's spring handling as a plan for the springs bake: reset frames (the entry, any jump, every yaw
        step > 0.35 rad) and the flower's stiffening for the turn (stiffness x (1 + 3.5 bump), drag toward 0.95)."""
        resets, last_y, last_u = [], None, None
        for f, u in frames_u:
            y = mark_at(u)['yaw']
            jumped = last_u is None or u < last_u or u - last_u > 0.5 or u < 0.1
            if jumped or (last_y is not None and abs(y - last_y) > 0.35):
                resets.append(f)
            last_y, last_u = y, u
        bump = {f: ease(u, 29.95, 30.25) * (1 - ease(u, 31.9, 32.4)) for f, u in frames_u}
        return {'resets': resets, 'bump': bump}

    def key_verse(frame_start=None, fps=None, t0=0.0, u0=0.0, u1=VERSE_SECONDS, vrm=None, camera_obj=None,
                  pulse=None, springs=True, scale=0.87, log=print):
        """The Blender conductor for verse 3: keys every frame of [u0, u1] (u = verse seconds; t = t0 + u): the
        set's update, the camera (CONSTANT across cuts), her mark (CONSTANT across yaw steps), her gestures and
        springs. pulse(u) -> the kick's 0..1. Returns {'frames', 'cuts', 'camera', 'springs'}."""
        from .keys import key_channels
        fps = fps or scene.render.fps / scene.render.fps_base
        f0 = scene.frame_start if frame_start is None else int(frame_start)
        n = int(math.floor((u1 - u0) * fps + 1e-6)) + 1
        frames = [(f0 + i, u0 + i / fps) for i in range(n)]
        cuts = [f for (f, u), (_f2, u2) in zip(frames, frames[1:]) if shot(u)['shot'] != shot(u2)['shot']]
        tg = _targets()
        series = {}
        for f, u in frames:
            for name, v in state(t0 + (u - u0), {'u': u, 'pulse': pulse(u) if pulse else 0.0}).items():
                if name in tg:
                    series.setdefault(name, []).append((f, v))
        key_channels(tg, series, cuts)
        if house is not None:
            _sync_house_glints()
        cam = None
        if camera_obj is not None or ctx.get('camera_obj') is not None:
            cam = camera_obj or ctx['camera_obj']
            from .keys import key_camera
            key_camera(cam, [(f, camera(u)) for f, u in frames], group.matrix_world, cuts)
            scene.camera = cam
        rep = {'frames': [frames[0][0], frames[-1][0]], 'cuts': cuts}
        if vrm is not None:
            from .keys import key_mark
            key_mark(vrm, [(f, mark_at(u)) for f, u in frames], group.matrix_world, scale)
            from .perform import key_performance
            # her per-frame passes step the scene ~2 x the verse's frames: the set (Geometry Nodes sea, grass, flora)
            # need not evaluate meanwhile, so its collection sits out of the view layer's evaluation
            lc = _layer_collection(bpy.context.view_layer.layer_collection, col)
            was = lc.exclude if lc is not None else None
            if lc is not None:
                lc.exclude = True
            daisy_ob = land.daisies.group if land is not None and land.daisies is not None else None
            dhide = daisy_ob.hide_viewport if daisy_ob is not None else None
            if daisy_ob is not None:
                daisy_ob.hide_viewport = True
            try:
                rep['perform'] = key_performance(api, vrm, frames, cam)
                if springs:
                    from .perform import bake_springs_with_plan
                    rep['springs'] = bake_springs_with_plan(vrm, frames, spring_plan(frames), log=log)
            finally:
                if lc is not None:
                    lc.exclude = was
                if daisy_ob is not None:
                    daisy_ob.hide_viewport = dhide
        log(f'[ocean] key_verse: frames {frames[0][0]}..{frames[-1][0]}, {len(cuts)} cuts, {len(series)} channels')
        return rep

    def dispose():
        """Removes the set's objects and its collection (images, materials and node groups stay for reuse)."""
        if land is not None and land.daisies is not None:
            land.daisies.remove()
        for o in list(col.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        if col.name in bpy.data.collections:
            bpy.data.collections.remove(col)

    api._fill({
        'group': group, 'SKY': SKY, 'BAR': BAR, 'layout': layout, 'coast': coast, 'sea': sea, 'echoes': echoes,
        'pages': pages, 'house': house, 'apparitions': apparitions, 'land': land, 'lights': lights, 'world': world,
        'to_set': to_set, 'to_world': to_world, 'E': to_set(E), 'E_design': E, 'mark': B3((0.0, MARK_Y, 0.0)),
        'PSI': PSI, 'moon': moon_world, 'collection': col, 'scene': scene,
        'mark_at': mark_at, 'camera': camera, 'perform': perform, 'update': update, 'state': state,
        'key_verse': key_verse, 'spring_plan': spring_plan, 'shot': shot, 'pose23': pose23, 'pose26': pose26,
        'wrap_world': lambda w=None: wrap_world(w or scene.world, moon_world, getattr(sky, 'sun', None)),
        'render_settings': lambda s=None: render_settings(s or scene),
        'dispose': dispose, 'focal': to_set(E),
        'parts': {k: v for k, v in (('land', land), ('sea', sea), ('echoes', echoes), ('pages', pages),
                                    ('house', house), ('apparitions', apparitions)) if v is not None},
    })
    update(0.0, {'u': 0.0})
    return api


def render_settings(scene):
    """What EEVEE needs for this set (the rest is the film's): a shadow pool that holds the moon's clipmaps over a
    3 km view (the default 512 MB overflows: 'Shadow buffer full'), and no fast GI (outdoors at night its screen-space
    pass lifts the land with the world)."""
    ee = scene.eevee
    if int(ee.shadow_pool_size) < 1024:
        ee.shadow_pool_size = '1024'
    ee.use_fast_gi = False
    return scene


def _layer_collection(lc, col):
    if lc.collection == col:
        return lc
    for ch in lc.children:
        r = _layer_collection(ch, col)
        if r is not None:
            return r
    return None


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
