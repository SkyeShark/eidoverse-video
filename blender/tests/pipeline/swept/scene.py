"""Test T18: parts that turn in place, against their neighbours (the runner's motion.swept_clearance). Three desk-fan
rotors and a scanning radar bar on a concrete floor, 2 s at 24 fps:

    rotor_A  a two-blade rotor in front of its motor can, 2.5 cm clear      nothing to say
    rotor_B  the same rotor sunk inside a drum housing                       sits inside its mount at every angle
    rotor_C  a rotor whose blade tips cut into the wooden cabinet beside it  sweeps through the cabinet at some angles
    radar    a radar bar scanning +-40 degrees beside a pole it would hit    nothing to say: it never turns that far,
             at 90 degrees                                                   and only the angles it turns through count

The rotors turn twice about their own Y axis (keyed LINEAR), the radar sweeps a sine about Z. build() makes the whole
scene for setup(ctx) and for blender/tests/harness/test_swept_clearance.py (no runner, the audit called directly).

    python eido_blender.py render blender/tests/pipeline/swept/scene.json --at 0.5
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

FAN_Z = 1.2                 # the rotors' axle height
BLADE = (0.05, 0.45)        # a blade from the hub to its tip (m from the axle)


def principled(name, colour, metallic=0.0, roughness=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*colour, 1.0)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = roughness
    return m


def _cylinder(bm, radius, depth, centre, axis='Z', segments=48):
    """A capped cylinder along an axis, into bm."""
    geom = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius,
                                 radius2=radius, depth=depth, calc_uvs=True)
    rot = {'Z': Matrix(), 'Y': Matrix.Rotation(math.pi / 2, 4, 'X'), 'X': Matrix.Rotation(math.pi / 2, 4, 'Y')}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(centre) @ rot, verts=geom['verts'])


def _box(bm, size, centre, rot=Matrix()):
    geom = bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(centre) @ rot @ Matrix.Diagonal((*size, 1.0)),
                        verts=geom['verts'])


def mesh_object(name, parts, material, location=(0, 0, 0)):
    """One object from a list of (maker, args) bmesh parts, its origin at `location`."""
    bm = bmesh.new()
    bm.loops.layers.uv.new('UVMap')
    for fn, args in parts:
        fn(bm, *args)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = False
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    bpy.context.scene.collection.objects.link(ob)
    return ob


def rotor(name, pivot, material):
    """A hub and two pitched blades about the object's origin (the axle, along Y)."""
    pitch = Matrix.Rotation(math.radians(18), 4, 'X')
    mid, length = (BLADE[0] + BLADE[1]) / 2, BLADE[1] - BLADE[0]
    parts = [(_cylinder, (0.045, 0.05, Vector((0, 0, 0)), 'Y', 32))]
    for side in (1, -1):
        parts.append((_box, ((length, 0.012, 0.085), Vector((side * mid, 0, 0)), pitch)))
    return mesh_object(name, parts, material, pivot)


def stand(bm_parts, x, y):
    """A desk fan's post and base under the axle (into a parts list)."""
    bm_parts.append((_cylinder, (0.025, FAN_Z - 0.1, Vector((x, y, (FAN_Z - 0.1) / 2)), 'Z', 24)))
    bm_parts.append((_cylinder, (0.2, 0.03, Vector((x, y, 0.015)), 'Z', 48)))
    return bm_parts


def build(scene, frame_start, frame_end, key, materials=None, radar_turns=False):
    """The scene's objects, the rotors' two turns keyed at both ends and the radar's sweep on every frame, through
    key(ob, data_path, frame) (ctx.key in a runner build). radar_turns: the radar turns a whole revolution instead
    of scanning (the control: then its bar does sweep through the pole). Returns {name: object}."""
    M = materials or {}
    steel = M.get('steel') or principled('steel', (0.55, 0.56, 0.58), 1.0, 0.35)
    paint = M.get('paint') or principled('rotor_paint', (0.9, 0.33, 0.06), 0.0, 0.45)
    wood = M.get('wood') or principled('cabinet_wood', (0.42, 0.26, 0.13), 0.0, 0.6)
    floor_m = M.get('floor') or principled('floor', (0.35, 0.35, 0.34), 0.0, 0.8)
    white = principled('radar_white', (0.82, 0.83, 0.85), 0.0, 0.4)
    wall_m = M.get('wall') or principled('wall', (0.6, 0.58, 0.55), 0.0, 0.9)
    ob = {'floor': mesh_object('floor', [(_box, ((12.0, 8.0, 0.1), Vector((0, 0.0, -0.05))))], floor_m),
          'wall': mesh_object('wall', [(_box, ((12.0, 0.2, 4.0), Vector((0, 2.6, 2.0))))], wall_m)}
    # A: a motor can behind the rotor, its face 2.5 cm behind the hub's back
    xa, xb, xc, xr = -2.4, -0.9, 0.6, 2.3
    ob['mount_A'] = mesh_object('mount_A', stand([(_cylinder, (0.11, 0.26, Vector((xa, 0.18, FAN_Z)), 'Y'))], xa,
                                                 0.18), steel)
    ob['rotor_A'] = rotor('rotor_A', (xa, -0.02, FAN_Z), paint)
    # B: the rotor sunk inside a drum housing 1 m across (the blades never show)
    ob['mount_B'] = mesh_object('mount_B', stand([(_cylinder, (0.5, 0.3, Vector((xb, 0.1, FAN_Z)), 'Y'))], xb, 0.1),
                                steel)
    ob['rotor_B'] = rotor('rotor_B', (xb, 0.02, FAN_Z), paint)
    # C: clear of its can, but a cabinet stands 36 cm from the axle: the blade tips (45 cm) cut into it
    ob['mount_C'] = mesh_object('mount_C', stand([(_cylinder, (0.11, 0.26, Vector((xc, 0.18, FAN_Z)), 'Y'))], xc,
                                                 0.18), steel)
    ob['rotor_C'] = rotor('rotor_C', (xc, -0.02, FAN_Z), paint)
    ob['cabinet_C'] = mesh_object('cabinet_C', [(_box, ((0.5, 0.45, 1.5), Vector((xc + 0.61, -0.08, 0.75))))], wood)
    # the radar: a 1.4 m bar on a mast, scanning +-40 degrees; a pole 45 cm off its axis, where the bar would point
    # at 90 degrees
    ob['mast'] = mesh_object('mast', [(_cylinder, (0.04, 1.45, Vector((xr, 0.0, 0.725)), 'Z', 24)),
                                      (_cylinder, (0.2, 0.03, Vector((xr, 0.0, 0.015)), 'Z', 48))], steel)
    ob['radar'] = mesh_object('radar', [(_box, ((1.4, 0.08, 0.18), Vector((0, 0, 0))))], white, (xr, 0.0, 1.55))
    ob['pole_D'] = mesh_object('pole_D', [(_cylinder, (0.07, 1.9, Vector((xr, 0.45, 0.95)), 'Z', 24))], steel)
    n = frame_end - frame_start
    for name in ('rotor_A', 'rotor_B', 'rotor_C'):
        r = ob[name]
        r['no_support_check'] = True        # held on its axle in front of its mount: it rests on no surface beneath
        for f, a in ((frame_start, 0.5 * math.pi), (frame_end, 0.5 * math.pi - 4.0 * math.pi)):   # blades upright
            r.rotation_euler = (0.0, a, 0.0)                                                          # at the start,
            key(r, 'rotation_euler', f)                                                               # two turns
    for f in range(frame_start, frame_end + 1):
        k = (f - frame_start) / n
        a = 2.0 * math.pi * k if radar_turns else math.radians(40.0) * math.sin(2.0 * math.pi * k)
        ob['radar'].rotation_euler = (0.0, 0.0, a)
        key(ob['radar'], 'rotation_euler', f)
    return ob


def setup(ctx):
    scene = ctx.scene
    from eidoblend.harness import assets
    mats = {'floor': assets.load_pbr('Concrete034', res='2k', maps=('diff', 'normal', 'rough'), repeat=(4, 3)),
            'wall': assets.load_pbr('PaintedPlaster017', res='2k', maps=('diff', 'normal', 'rough'), repeat=(4, 1.5)),
            'wood': assets.load_pbr('Wood027', res='1k', maps=('diff', 'normal', 'rough'))}
    build(scene, ctx.frame_start, ctx.frame_end, lambda o, p, f: ctx.key(o, p, frame=f), mats)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy, sun.data.angle = 3.0, math.radians(4)
    sun.rotation_euler = (math.radians(52), 0.0, math.radians(-28))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'AREA'))
    fill.data.shape, fill.data.size, fill.data.energy = 'DISK', 3.0, 400.0
    fill.location = (2.5, -4.0, 3.0)
    fill.rotation_euler = (Vector((0.0, 0.0, 1.0)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(fill)
    w = bpy.data.worlds.new('shop')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.055, 0.065, 1.0)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 26
    cam.location = (0.15, -4.7, 1.75)
    cam.rotation_euler = (Vector((0.15, 0.3, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
