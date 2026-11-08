"""Test T10: load_kit. The kit's parts come out of their catalogue row standing on z = 0 wherever they are placed;
the row itself never renders. The scene records what it measured (scene.kit_bases, scene.kit_row) for run_tests.py.
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import assets


def setup(ctx):
    scene = ctx.scene
    concrete = assets.load_pbr('Concrete031', res='1k', maps=('diff', 'normal', 'rough'), repeat=(0.5, 0.5))
    me = bpy.data.meshes.new('ground')
    me.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (6, 0), (6, 6), (0, 6)]):
        loop.uv = (u, v)
    me.materials.append(concrete)
    scene.collection.objects.link(bpy.data.objects.new('ground', me))

    kit = assets.load_kit(ctx.assets['kit'])
    placed = [kit.get('crate_small', (0.0, 0.0, 0.0)),
              kit.get('crate_small', (-0.55, 0.35, 0.0), rotation_z=math.radians(30)),
              kit.get('post_tall', (0.6, 0.25, 0.0)),
              kit.get('pipe_elbow_01', (0.05, -0.55, 0.0), rotation_z=math.radians(-20))]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    lows = {}
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent and inst.parent.original in placed:
            mw = inst.matrix_world
            z = min((mw @ Vector(c)).z for c in inst.object.bound_box)
            key = inst.parent.original.name
            lows[key] = min(lows.get(key, 1e9), z)
    worst = max((abs(z) for z in lows.values()), default=1e9)
    ctx.record('kit_bases', 'PASS' if len(lows) == 4 and worst < 1e-3 else 'WARN',
               f'{len(lows)} kit instances, lowest points {[round(z, 4) for z in lows.values()]} (want 0)')
    row = [o.name for o in scene.objects if o.name in kit.list()]
    ctx.record('kit_row', 'PASS' if not row else 'WARN', f'catalogue parts in the scene: {row or "none"}; '
               f'parts: {kit.list()}')

    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA'))
    key.data.size, key.data.energy = 2.0, 260.0
    key.location = (-1.6, -1.6, 2.4)
    key.rotation_euler = (Vector((0, 0, 0.2)) - key.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(key)
    w = bpy.data.worlds.new('grey')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.08, 0.08, 0.09, 1)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 35
    cam.location = (1.2, -2.6, 1.3)
    cam.rotation_euler = (Vector((0.0, 0.0, 0.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
