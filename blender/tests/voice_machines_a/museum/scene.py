"""A museum of voices, four seconds: the 2001 desktop, the Macintosh, the C64 and the DECtalk on one oak desk against a
plaster wall. Each machine powers on (its CRT opening from a line), shows its words and speaks in turn while the
camera drifts along the desk. Everything the machines do is keyed by their update(t, state) through ctx.

    EIDO_ASSET_CACHE=<checkout>/eidoverse/assets/cache EIDO_NO_FETCH=1 \\
        python eido_blender.py build blender/tests/voice_machines_a/museum/scene.json
    python eido_blender.py render blender/tests/voice_machines_a/museum/scene.json --at 0.4 --at 1.3 --at 2.4 --at 3.6

Coordinates: Z up, metres; the desk runs along X, the machines face -Y, the camera looks along +Y.
"""
import math

import bpy
from mathutils import Vector

from eidoblend import props
from eidoblend.harness import assets
from eidoblend.props import voice_machines as VM

DESK_Z, DESK_W, DESK_D = 0.74, 3.3, 0.9
# machine: x on the desk, the time it powers on, its voice window (s)
CAST = {'desktop2001': (-1.02, 0.0, (0.5, 1.4)), 'mac1984': (0.02, 0.7, (1.3, 2.2)),
        'c64': (0.62, 1.5, (2.3, 3.1)), 'dectalk': (1.25, 0.0, (3.0, 3.9))}
M = {}


def box(name, size, location, material, uv_per_m=1.0):
    """An axis-aligned box with box-projected UVs (uv_per_m tiles per metre)."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] * uv_per_m, lp.vert.co[b] * uv_per_m)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    bpy.context.scene.collection.objects.link(ob)
    return ob


def area_light(name, location, target, size, power, colour):
    li = bpy.data.lights.new(name, 'AREA')
    li.shape, li.size, li.energy, li.color = 'DISK', size, power, colour
    li.use_custom_distance, li.cutoff_distance = True, 40.0
    ob = bpy.data.objects.new(name, li)
    ob.location = location
    ob.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup(ctx):
    wood = assets.load_pbr('Wood066', res='1k', maps=('diff', 'normal', 'rough'))
    floor = assets.load_pbr('WoodFloor064', res='2k', maps=('diff', 'normal', 'rough'))
    plaster = assets.load_pbr('PaintedPlaster017', res='2k', maps=('diff', 'normal', 'rough'))
    box('floor', (8.0, 6.0, 0.02), (0.0, 0.5, -0.01), floor, 0.7)
    box('wall', (8.0, 0.08, 3.2), (0.0, DESK_D / 2 + 0.2, 1.6), plaster, 0.8)
    top = box('desk_top', (DESK_W, DESK_D, 0.032), (0.0, 0.0, DESK_Z - 0.016), wood, 1.4)
    ctx.flag(top, 'no_support_check')                 # it stands on its two leg panels, which the check does not model
    for sx in (-1, 1):
        box(f'desk_leg_{sx}', (0.05, DESK_D - 0.1, DESK_Z - 0.032), (sx * (DESK_W / 2 - 0.06), 0.0,
                                                                   (DESK_Z - 0.032) / 2), wood, 1.4)
    for name, (x, _on, _voice) in CAST.items():
        m = props.build(name, ctx=ctx)
        cx, cy = VM.MACHINES[name]['center']
        # 2.5 mm into the top: the keyboards' flat bottoms would otherwise share its plane (EEVEE z-fights coplanar
        # faces; the placement audit flags any within 2 mm), and proud of it they would hover
        m.group.location = (x - cx, -cy + 0.05, DESK_Z - 0.0025)
        M[name] = m
    area_light('key', (-1.6, -2.2, 2.6), (0.0, 0.0, DESK_Z + 0.2), 2.0, 260.0, (1.0, 0.88, 0.74))
    area_light('fill', (2.4, -2.0, 1.4), (0.0, 0.0, DESK_Z + 0.2), 3.0, 70.0, (0.78, 0.85, 1.0))
    area_light('rim', (0.5, 1.2, 2.4), (0.0, 0.0, DESK_Z + 0.2), 1.5, 50.0, (1.0, 0.95, 0.9))
    w = bpy.data.worlds.new('dim')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.021, 0.024, 1.0)
    ctx.scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 32
    cam.data.clip_start = 0.02
    ctx.scene.collection.objects.link(cam)
    ctx.cut(0, cam)
    M['cam'] = cam


def voice(t, window):
    """Syllables: five pulses a second inside the window, a soft attack and release."""
    a, b = window
    if not a <= t <= b:
        return 0.0
    env = min(1.0, (t - a) / 0.12, (b - t) / 0.2)
    return max(0.0, env * (0.55 + 0.45 * math.sin((t - a) * math.pi * 10)))


def ramp(t, t0, dur=0.6):
    return min(1.0, max(0.0, (t - t0) / dur))


def render_frame(ctx, t, i):
    st = {n: {'power': ramp(t, on), 'voice': voice(t, win)} for n, (_x, on, win) in CAST.items()}
    st['desktop2001']['text'] = 'reading screens' if t < 1.0 else 'I read every screen aloud'
    st['mac1984']['text'] = 'hello' if t < 1.6 else 'I was a mouth'
    st['c64']['lines'] = ['READY.'] + (['SAY "DAISY"'] if t >= 2.0 else []) + (['DAISY', 'READY.'] if t >= 2.9 else [])
    for n, m in M.items():
        if n != 'cam':
            m.update(t, st[n])
    # the camera drifts along the desk, from the desktop to the DECtalk
    u = t / 4.0
    s = u * u * (3 - 2 * u)
    cam = M['cam']
    x = -0.85 + 1.9 * s
    cam.location = (x, -2.05, DESK_Z + 0.55)
    cam.rotation_euler = (Vector((x * 0.85, 0.0, DESK_Z + 0.18)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    ctx.key_transform(cam)
