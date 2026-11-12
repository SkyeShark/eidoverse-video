"""The stage of test T19 (scene.py, scene_crt.py): an ember-orange glowing ball crosses a dark plaster room left to
right in 1.5 s, past a lit concrete block, the camera still. The post effect each scene puts on it reads earlier
frames back: what a --at still shows of the ball's trail depends on the frames rendered before it."""
import math

import bpy
from mathutils import Vector

X0, X1, Z = -1.6, 1.6, 1.1


def stage(ctx):
    from eidoblend.harness import assets
    scene = ctx.scene
    plaster = assets.load_pbr('PaintedPlaster017', res='2k', maps=('diff', 'normal', 'rough'), repeat=(1.5, 1.0))
    conc = assets.load_pbr('Concrete034', res='2k', maps=('diff', 'normal', 'rough'), repeat=(1.0, 1.0))

    def quad(name, verts, mat, uv_size):
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name='UVMap')
        for loop, (u, v) in zip(uv.data, [(0, 0), (uv_size[0], 0), uv_size, (0, uv_size[1])]):
            loop.uv = (u, v)
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        scene.collection.objects.link(ob)
        return ob
    quad('floor', [(-4, -3, 0), (4, -3, 0), (4, 3, 0), (-4, 3, 0)], conc, (4, 3))
    quad('wall', [(-4, 1.2, 0), (4, 1.2, 0), (4, 1.2, 3), (-4, 1.2, 3)], plaster, (4, 1.5))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.55, 0.45, 0.35))
    block = bpy.context.object
    block.name = 'block'
    block.scale = (0.7, 0.5, 0.7)
    block.data.materials.append(conc)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, segments=32, ring_count=16, location=(X0, 0.0, Z))
    ember = bpy.context.object
    ember.name = 'ember'
    ember['no_support_check'] = True                      # it flies
    m = bpy.data.materials.new('ember')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (1.0, 0.35, 0.08, 1.0)
    b.inputs['Emission Color'].default_value = (1.0, 0.38, 0.1, 1.0)
    b.inputs['Emission Strength'].default_value = 40.0
    ember.data.materials.append(m)
    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA'))
    key.data.shape, key.data.size, key.data.energy = 'DISK', 1.5, 90.0
    key.location = (-1.5, -1.8, 2.4)
    key.rotation_euler = (Vector((0.3, 0.4, 0.4)) - key.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(key)
    w = bpy.data.worlds.new('dark')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.008, 0.008, 0.01, 1.0)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 32
    cam.location = (0.0, -4.6, 1.5)
    cam.rotation_euler = (Vector((0.0, 0.4, 0.85)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam


def render_frame(ctx, t, i):
    ember = bpy.data.objects['ember']
    k = min(1.0, t / max(1e-6, ctx.duration - 1.0 / ctx.fps))
    ember.location = (X0 + (X1 - X0) * k, 0.0, Z + 0.25 * math.sin(math.pi * k))
    ctx.key(ember, 'location')
