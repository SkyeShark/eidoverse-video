"""A city street for the weather tests: asphalt road with a centre line, curbs, paved sidewalks, rows of buildings
with plaster / brick / concrete facades, windows (dark glass, or lit rooms behind glass), shop fronts with their
interiors, a shop awning, street lamps.

    from street_set import build_street
    S = build_street(scene)        # {'collection', 'camera', 'lamps', 'awning', ...}

Textures are the shared CC0 library (eidoverse/assets/cache/textures, through eidoblend.harness.assets.load_pbr), read
from the main checkout's cache when this worktree has none. The rooms behind the lit windows and the shop fronts are
round one's interior-window material (eidoblend.harness.interior_window) over two room pictures rendered once in
Blender (a shop and a flat; out/rooms/, reused when present). Every window is glass: a Principled reflection over
what is behind it, so a lightning flash and the street lamps show in it. The asphalt's roughness is lifted to dry
asphalt (0.72-0.86; the library map averages 0.44, a damp sheen), so the weather's wetting is what makes it shine.
Everything is in metres; the road runs along +Y.
"""
import math
import os
import random

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN_CACHE = 'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01/eidoverse/assets/cache'
# the sets this street uses live in the main checkout's shared cache (read only: no fetch writes there)
if not os.path.isdir(os.path.join(HERE, '..', '..', '..', 'eidoverse', 'assets', 'cache', 'textures', 'Asphalt025C_2k')):
    os.environ.setdefault('EIDO_ASSET_CACHE', MAIN_CACHE)
os.environ.setdefault('EIDO_NO_FETCH', '1')
ROOMS = os.path.join(HERE, 'out', 'rooms')


def _pbr(id_, res, repeat, name, tint=None, rough=None):
    """A library material; tint multiplies its colour, rough = (lo, hi) remaps its roughness map into lo..hi."""
    from eidoblend.harness.assets import load_pbr
    m = load_pbr(id_, res, maps=('diff', 'normal', 'rough'), repeat=repeat, name=name)
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    if tint is not None:
        src = p.inputs['Base Color'].links[0].from_socket
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        ins = {s.identifier: s for s in mix.inputs}
        ins['Factor_Float'].default_value = 1.0
        nt.links.new(src, ins['A_Color'])
        ins['B_Color'].default_value = (*tint, 1.0)
        out = next(s for s in mix.outputs if s.identifier == 'Result_Color')
        nt.links.new(out, p.inputs['Base Color'])
    if rough is not None and p.inputs['Roughness'].is_linked:
        src = p.inputs['Roughness'].links[0].from_socket
        mr = nt.nodes.new('ShaderNodeMapRange')
        nt.links.new(src, mr.inputs['Value'])
        mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = rough
        nt.links.new(mr.outputs['Result'], p.inputs['Roughness'])
    return m


def _flat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color, 1.0)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if emit is not None:
        p.inputs['Emission Color'].default_value = (*emit, 1.0)
        p.inputs['Emission Strength'].default_value = strength
    return m


def _box_mesh(bm, x0, x1, y0, y1, z0, z1):
    v = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([v[i] for i in f])


def _box(coll, name, x0, x1, y0, y1, z0, z1, mat, uv_m=3.0):
    """An axis-aligned box with box-projected UVs in metres / uv_m (so textures tile at real scale)."""
    bm = bmesh.new()
    _box_mesh(bm, x0, x1, y0, y1, z0, z1)
    bm.normal_update()
    uv = bm.loops.layers.uv.new('UVMap')
    for face in bm.faces:
        n = face.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for loop in face.loops:
            c = loop.vert.co
            a, b = [(c.y, c.z), (c.x, c.z), (c.x, c.y)][ax]
            loop[uv].uv = (a / uv_m, b / uv_m)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _quad(coll, name, corners, mat):
    """A quad with 0..1 UVs: U along its first edge (across the window), V up."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(corners, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = c
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _cyl(coll, name, x, y, z0, z1, r, mat, seg=12):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=z1 - z0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, (z0 + z1) / 2))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


# ------------------------------------------------------------------------------------------------- the rooms ---

def _furnish(kind):
    """build(scene) for render_room_image: a shop (shelves of goods, a counter) or a flat (sofa, rug, lamp,
    pictures). The room spans x -1.6..1.6, depth y 0..3, height 2.6."""
    def mat(name, rgb, rough=0.6, emit=None, strength=0.0):
        return _flat('room_' + name, rgb, rough=rough, emit=emit, strength=strength)

    def add(sc, name, boxes, m):
        bm = bmesh.new()
        for b in boxes:
            _box_mesh(bm, *b)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)

    def build(sc):
        rnd = random.Random(3 if kind == 'shop' else 11)
        if kind == 'shop':
            wood = mat('shelf_wood', (0.32, 0.2, 0.11), 0.55)
            add(sc, 'shelves', [(-1.5, 1.5, 2.55, 2.95, z, z + 0.035) for z in (0.25, 0.75, 1.25, 1.75, 2.2)]
                + [(-1.5, -1.45, 2.55, 2.95, 0.0, 2.3), (1.45, 1.5, 2.55, 2.95, 0.0, 2.3)], wood)
            goods = [mat('goods_%d' % i, c, 0.45) for i, c in enumerate(
                ((0.55, 0.12, 0.08), (0.12, 0.25, 0.5), (0.75, 0.6, 0.18), (0.85, 0.82, 0.75), (0.2, 0.42, 0.22)))]
            for zi, z in enumerate((0.285, 0.785, 1.285, 1.785, 2.235)):
                x = -1.42
                while x < 1.3:
                    w = rnd.uniform(0.08, 0.26)
                    h = rnd.uniform(0.12, 0.36)
                    add(sc, 'goods', [(x, x + w, 2.6, 2.6 + rnd.uniform(0.15, 0.32), z, z + h)], rnd.choice(goods))
                    x += w + rnd.uniform(0.01, 0.06)
            add(sc, 'counter', [(-1.45, -0.35, 1.0, 1.55, 0.0, 0.95)], mat('counter', (0.6, 0.58, 0.52), 0.35))
            add(sc, 'till', [(-1.1, -0.75, 1.15, 1.4, 0.95, 1.18)], mat('till', (0.05, 0.05, 0.06), 0.3))
            add(sc, 'pendant', [(-0.12, 0.12, 1.5, 1.74, 2.2, 2.32)],
                mat('pendant', (0.0, 0.0, 0.0), emit=(1.0, 0.8, 0.55), strength=25.0))
        else:
            add(sc, 'sofa', [(-1.1, 1.1, 2.3, 2.95, 0.0, 0.45), (-1.1, 1.1, 2.75, 2.95, 0.45, 0.95),
                             (-1.1, -0.9, 2.3, 2.95, 0.45, 0.65), (0.9, 1.1, 2.3, 2.95, 0.45, 0.65)],
                mat('sofa', (0.2, 0.28, 0.33), 0.8))
            add(sc, 'rug', [(-1.0, 1.0, 0.9, 2.2, 0.0, 0.01)], mat('rug', (0.45, 0.16, 0.12), 0.95))
            add(sc, 'pictures', [(-0.8, -0.2, 2.97, 3.0, 1.3, 1.75), (0.15, 0.65, 2.97, 3.0, 1.25, 1.85)],
                mat('pictures', (0.7, 0.62, 0.45), 0.4))
            add(sc, 'lamp_stand', [(1.3, 1.36, 2.4, 2.46, 0.0, 1.45)], mat('lamp_stand', (0.05, 0.05, 0.05), 0.4))
            add(sc, 'lamp_shade', [(1.18, 1.48, 2.28, 2.58, 1.45, 1.75)],
                mat('lamp_shade', (0.0, 0.0, 0.0), emit=(1.0, 0.7, 0.4), strength=12.0))
            add(sc, 'table', [(-0.45, 0.45, 1.3, 1.8, 0.0, 0.4)], mat('table', (0.3, 0.19, 0.1), 0.5))
    return build


def room_pictures(size=256):
    """The two room pictures (rendered once into out/rooms/, then reused): {'shop': path, 'flat': path}."""
    from eidoblend.harness.interior_window import render_room_image
    os.makedirs(ROOMS, exist_ok=True)
    out = {}
    for kind, lamp, wall in (('shop', (1.0, 0.86, 0.68), (0.72, 0.68, 0.6)), ('flat', (1.0, 0.74, 0.5),
                                                                             (0.55, 0.47, 0.38))):
        p = os.path.join(ROOMS, 'room_%s.png' % kind)
        if not os.path.exists(p):
            render_room_image(p, size=size, build=_furnish(kind), samples=16, lamp=lamp, wall=wall)
            for sc in [s for s in bpy.data.scenes if s.name.startswith('interior_room')]:
                bpy.data.scenes.remove(sc)          # the room's own scene: only its picture stays
        out[kind] = p
    return out


def glass_over(mat, rough=0.03):
    """Add a glass reflection (a black Principled: Fresnel specular only) over whatever the material shows."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
    src = out.inputs['Surface'].links[0].from_socket
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    p.inputs['Roughness'].default_value = rough
    p.inputs['IOR'].default_value = 1.52
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(src, add.inputs[0])
    nt.links.new(p.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    mat['eido_noWet'] = 1                    # vertical glass: the weather leaves it as it is
    return mat


def build_street(scene, length=170.0, seed=7, lamps_on=True, rooms=True):
    """rooms=False: every window is dark glass (no room pictures rendered: for runs that render nothing)."""
    from eidoblend.harness.interior_window import create_interior_window_material
    rnd = random.Random(seed)
    coll = bpy.data.collections.new('street')
    scene.collection.children.link(coll)
    road = _pbr('Asphalt025C', '2k', (1.0, 1.0), 'street_asphalt', rough=(0.72, 0.86))
    walk = _pbr('PavingStones128', '1k', (1.0, 1.0), 'street_paving', tint=(0.85, 0.83, 0.8), rough=(0.62, 0.8))
    curb = _pbr('Concrete034', '2k', (1.0, 1.0), 'street_curb', rough=(0.7, 0.85))
    facades = [_pbr('PaintedPlaster017', '2k', (1, 1), 'facade_plaster', tint=(0.92, 0.86, 0.78)),
               _pbr('Bricks097', '2k', (1, 1), 'facade_brick'),
               _pbr('PaintedBricks004', '2k', (1, 1), 'facade_painted_brick'),
               _pbr('Concrete034', '2k', (1, 1), 'facade_concrete', tint=(0.8, 0.8, 0.82))]
    paint = _flat('road_paint', (0.78, 0.76, 0.7), rough=0.6)
    glass = _flat('window_dark', (0.012, 0.014, 0.017), rough=0.04)
    glass['eido_noWet'] = 1
    frame_m = _flat('window_frame', (0.06, 0.06, 0.065), rough=0.4, metal=0.6)
    if rooms:
        pics = room_pictures()
        lit = [glass_over(create_interior_window_material(room=pics['flat'], depth=depth, brightness=bright,
                                                          name='window_lit_%d' % i))
               for i, (bright, depth) in enumerate(((0.55, 0.55), (0.8, 0.45), (0.4, 0.6)))]
        shop = glass_over(create_interior_window_material(room=pics['shop'], depth=0.28, brightness=0.9,
                                                          name='shop_window'))
    else:
        lit, shop = [glass], glass
    awning_m = _pbr('Fabric039', '1k', (1, 1), 'awning_fabric', tint=(0.75, 0.16, 0.12))
    pole = _flat('lamp_pole', (0.05, 0.055, 0.06), rough=0.35, metal=0.8)
    lamp_head = _flat('lamp_glow', (0.0, 0.0, 0.0), emit=(1.0, 0.72, 0.42), strength=40.0)
    # ground
    _box(coll, 'road', -4.0, 4.0, -30.0, length, -0.3, 0.0, road, uv_m=4.0)
    for i in range(int((length + 30) / 6)):
        y = -30 + i * 6
        _box(coll, 'line_%02d' % i, -0.08, 0.08, y, y + 3.0, 0.0, 0.004, paint, uv_m=1.0)
    for s in (-1, 1):
        _box(coll, 'curb_%+d' % s, min(s * 4.0, s * 4.25), max(s * 4.0, s * 4.25), -30.0, length, -0.3, 0.15, curb,
             uv_m=1.0)
        _box(coll, 'sidewalk_%+d' % s, min(s * 4.25, s * 7.5), max(s * 4.25, s * 7.5), -30.0, length, -0.3, 0.15, walk,
             uv_m=2.0)
    # buildings with windows on the street face
    for s in (-1, 1):
        y = -30.0
        k = 0
        while y < length:
            w = rnd.uniform(9.0, 15.0)
            h = rnd.choice((9.6, 12.8, 16.0, 19.2, 22.4))
            fm = facades[(k + (0 if s < 0 else 2)) % len(facades)]
            xa, xb = s * 7.5, s * 21.0
            _box(coll, 'building_%+d_%02d' % (s, k), min(xa, xb), max(xa, xb), y, y + w, 0.0, h, fm, uv_m=3.0)
            xf = s * 7.5 - s * 0.03                          # the facade plane, windows 3 cm proud of it
            floors = int((h - 3.6) / 3.2)
            cols = max(1, int((w - 1.0) / 2.6))
            for fl in range(floors):
                z = 4.0 + fl * 3.2
                for c in range(cols):
                    yc = y + (w - (cols - 1) * 2.6) / 2 + c * 2.6
                    m = rnd.choice(lit) if rnd.random() < 0.32 else glass
                    # each window faces the street (its normal toward x = 0), U left to right as seen from it
                    _quad(coll, 'win_%+d_%02d_%d_%d' % (s, k, fl, c),
                          [(xf, yc - 0.6, z), (xf, yc + 0.6, z), (xf, yc + 0.6, z + 1.6), (xf, yc - 0.6, z + 1.6)]
                          if s < 0 else
                          [(xf, yc + 0.6, z), (xf, yc - 0.6, z), (xf, yc - 0.6, z + 1.6), (xf, yc + 0.6, z + 1.6)], m)
                    _box(coll, 'sill_%+d_%02d_%d_%d' % (s, k, fl, c), min(xf, xf - s * 0.12), max(xf, xf - s * 0.12),
                         yc - 0.7, yc + 0.7, z - 0.08, z, frame_m, uv_m=1.0)
            if rnd.random() < 0.6:                       # a shop front at street level, framed
                yc = y + w / 2
                hw = w * 0.3
                _quad(coll, 'shop_%+d_%02d' % (s, k),
                      [(xf, yc - hw, 0.6), (xf, yc + hw, 0.6), (xf, yc + hw, 2.8), (xf, yc - hw, 2.8)]
                      if s < 0 else
                      [(xf, yc + hw, 0.6), (xf, yc - hw, 0.6), (xf, yc - hw, 2.8), (xf, yc + hw, 2.8)], shop)
                xo = xf - s * 0.08
                for (ya, yb, za, zb) in ((yc - hw - 0.08, yc - hw, 0.5, 2.9), (yc + hw, yc + hw + 0.08, 0.5, 2.9),
                                         (yc - hw, yc + hw, 2.8, 2.9), (yc - hw, yc + hw, 0.5, 0.6),
                                         (yc - 0.03, yc + 0.03, 0.6, 2.8)):
                    _box(coll, 'shopframe_%+d_%02d' % (s, k), min(xf, xo), max(xf, xo), ya, yb, za, zb, frame_m,
                         uv_m=1.0)
            y += w + 0.02
            k += 1
    # the awning over a shop on the left: 2.4 m deep, sloping from 3.1 m at the wall to 2.75 m at its edge
    aw = bpy.data.meshes.new('awning')
    bm = bmesh.new()
    y0, y1 = 14.0, 22.0
    vs = [bm.verts.new(c) for c in ((-7.47, y0, 3.10), (-5.07, y0, 2.75), (-5.07, y1, 2.75), (-7.47, y1, 3.10))]
    bm.faces.new(vs)
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.03)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co.y / 1.0, lp.vert.co.x / 1.0)
    bm.to_mesh(aw)
    bm.free()
    aw.materials.append(awning_m)
    awning = bpy.data.objects.new('awning', aw)
    coll.objects.link(awning)
    # street lamps on the right sidewalk
    lamps = []
    for i, y in enumerate(range(6, int(length), 20)):
        _cyl(coll, 'lamp_pole_%02d' % i, 5.6, y, 0.15, 6.2, 0.07, pole)
        _box(coll, 'lamp_arm_%02d' % i, 4.2, 5.6, y - 0.05, y + 0.05, 6.1, 6.2, pole, uv_m=1.0)
        _box(coll, 'lamp_head_%02d' % i, 3.9, 4.5, y - 0.18, y + 0.18, 5.95, 6.1, lamp_head, uv_m=1.0)
        if lamps_on:
            ld = bpy.data.lights.new('street_lamp_%02d' % i, 'SPOT')
            ld.energy = 900.0
            ld.color = (1.0, 0.72, 0.45)
            ld.spot_size = math.radians(120)
            ld.spot_blend = 0.6
            ld.shadow_soft_size = 0.15
            lo = bpy.data.objects.new('street_lamp_%02d' % i, ld)
            lo.location = (4.2, y, 5.9)
            lo.rotation_euler = (0, 0, 0)
            scene.collection.objects.link(lo)
            lamps.append(lo)
    cam_d = bpy.data.cameras.new('street_cam')
    cam_d.lens = 30
    cam_d.clip_end = 6000
    cam = bpy.data.objects.new('street_cam', cam_d)
    scene.collection.objects.link(cam)
    cam.location = (2.2, -8.0, 1.62)
    cam.rotation_euler = (math.radians(91.5), 0, math.radians(4.0))
    scene.camera = cam
    return dict(collection=coll, camera=cam, lamps=lamps, awning=awning)
