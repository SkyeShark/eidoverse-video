"""Test T14: a simulation longer than Blender's default cache (1-250). Three wooden crates drop onto a concrete floor
and settle; late in the film (frames 255-290, after the default cache would have ended) a steel slab sweeps
through the pile and knocks them along. The build must stretch the rigid-body cache to the film's last frame
(300) and bake it, so the crates move when the slab reaches them. (The verifier's bake probe showed the slab
passing straight through crates frozen at frame 250.) Two shots: a medium on the pile (to frame 250), then a
wide one for the push.

    python eido_blender.py render blender/tests/pipeline/bake/scene.json --at 10 --at 11.5 --at 12
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import assets


def body(ob, kind, **kw):
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        bpy.ops.rigidbody.object_add(type=kind)
    for k, v in kw.items():
        setattr(ob.rigid_body, k, v)


def setup(ctx):
    scene = ctx.scene
    conc = assets.load_pbr('Concrete034', res='2k', maps=('diff', 'normal', 'rough'), repeat=(0.5, 0.5))
    wood = assets.load_pbr('Planks039', res='2k', maps=('diff', 'normal', 'rough'), repeat=(1.0, 1.0))
    me = bpy.data.meshes.new('floor')                              # 60 m: its edge stays out of shot
    me.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (60, 0), (60, 60), (0, 60)]):
        loop.uv = (u, v)
    me.materials.append(conc)
    floor = bpy.data.objects.new('floor', me)
    scene.collection.objects.link(floor)
    bpy.ops.rigidbody.world_add()
    body(floor, 'PASSIVE', collision_shape='MESH', friction=0.8)
    for i, (x, z, yaw) in enumerate(((0.0, 0.6, 0.1), (0.15, 1.4, 0.5), (-0.1, 2.2, 0.9))):
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(x, 0.0, z), rotation=(0.0, 0.0, yaw))
        c = bpy.context.object
        c.name = f'crate_{i}'
        c.data.materials.append(wood)
        body(c, 'ACTIVE', mass=8.0, friction=0.7, collision_shape='BOX')
    # the slab: a kinematic (animated) passive body keyed along X late in the film
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-3.0, 0.0, 0.5))
    slab = bpy.context.object
    slab.name = 'slab'
    slab.scale = (0.4, 1.6, 1.0)
    steel = bpy.data.materials.new('steel')
    steel.use_nodes = True
    b = steel.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.32, 0.33, 0.35, 1)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.35
    slab.data.materials.append(steel)
    body(slab, 'PASSIVE', kinematic=True, collision_shape='BOX')
    for f, x in ((ctx.frame_start, -3.0), (255, -3.0), (290, 3.0)):
        slab.location.x = x
        ctx.key(slab, 'location', frame=f)
    ctx.flag(slab, 'no_motion_check')                             # a pusher blade travels broadside on purpose

    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy, sun.data.angle = 3.5, math.radians(1.5)
    sun.rotation_euler = (math.radians(48), 0.0, math.radians(-30))
    scene.collection.objects.link(sun)
    w = bpy.data.worlds.new('overcast')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.32, 0.36, 0.42, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
    scene.world = w
    shots = []
    for name, lens, at, aim in (('cam_pile', 40, (0.6, -3.1, 1.25), (0.05, 0.0, 0.45)),
                                ('cam_push', 32, (0.9, -3.6, 1.4), (0.9, 0.0, 0.4))):
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        cam.data.lens = lens
        cam.location = at
        cam.rotation_euler = (Vector(aim) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.collection.objects.link(cam)
        shots.append(cam)
    ctx.cut(ctx.frame_start, shots[0])
    ctx.cut(251, shots[1])
