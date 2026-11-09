"""Test T17: Geometry Nodes modifier inputs through the runner (Blender 5.2 keeps them as RNA, not ID properties).

A grey concrete-coloured pillar on a floor, grown by a Geometry Nodes modifier 'grow' whose group has two inputs:
Height (the pillar's z scale) and Twist (its turn about z, radians). render_frame keys Height every frame through
ctx.key on Blender 5.2's path, modifiers["grow"].properties.inputs.<Socket_N>.value, so the pillar rises from 0.5 m
to 2.5 m over the 2 s film. With "_unkeyed": true in the config it also sets Twist WITHOUT a key, which the build's
un-keyed check must name (it reads the modifier's inputs: keying.node_inputs).

What it checks (run_tests.py T17): the build finishes (keying.snapshot read the modifier without raising), nothing
is flagged un-keyed in the keyed variant, the saved .blend shows the keyed heights, and the un-keyed variant names
the Twist input.
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import keying


def _group():
    ng = bpy.data.node_groups.new('grow', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    h = ng.interface.new_socket('Height', in_out='INPUT', socket_type='NodeSocketFloat')
    h.default_value = 1.0
    ng.interface.new_socket('Twist', in_out='INPUT', socket_type='NodeSocketFloat')
    gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    tf = ng.nodes.new('GeometryNodeTransform')
    sc, rot = ng.nodes.new('ShaderNodeCombineXYZ'), ng.nodes.new('ShaderNodeCombineXYZ')
    sc.inputs['X'].default_value = sc.inputs['Y'].default_value = 1.0
    ng.links.new(gi.outputs['Height'], sc.inputs['Z'])
    ng.links.new(gi.outputs['Twist'], rot.inputs['Z'])
    ng.links.new(gi.outputs['Geometry'], tf.inputs['Geometry'])
    ng.links.new(sc.outputs['Vector'], tf.inputs['Scale'])
    ng.links.new(rot.outputs['Vector'], tf.inputs['Rotation'])
    ng.links.new(tf.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def _ident(ng, name):
    return next(it.identifier for it in ng.interface.items_tree
                if getattr(it, 'in_out', None) == 'INPUT' and it.name == name)


def _mat(name, rgb, rough):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    return m


def _input(ident):
    return getattr(PILLAR.modifiers['grow'].properties.inputs, ident)


def setup(ctx):
    global PILLAR, H_ID, T_ID, H_PATH
    scene = ctx.scene
    floor_me = bpy.data.meshes.new('floor')
    floor_me.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
    floor_me.materials.append(_mat('floor', (0.32, 0.30, 0.27), 0.8))
    floor = bpy.data.objects.new('floor', floor_me)
    scene.collection.objects.link(floor)

    me = bpy.data.meshes.new('pillar')         # a 0.5 m square column, 1 m tall at rest, its foot 1 cm in the floor
    v = [(x, y, z) for z in (-0.01, 1.0) for x, y in ((-.25, -.25), (.25, -.25), (.25, .25), (-.25, .25))]
    me.from_pydata(v, [], [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    me.materials.append(_mat('pillar', (0.62, 0.60, 0.56), 0.55))
    PILLAR = bpy.data.objects.new('pillar', me)
    scene.collection.objects.link(PILLAR)
    ng = _group()
    mod = PILLAR.modifiers.new('grow', 'NODES')
    mod.node_group = ng
    H_ID, T_ID = _ident(ng, 'Height'), _ident(ng, 'Twist')
    H_PATH = f'modifiers["grow"].properties.inputs.{H_ID}.value'
    labels = [f'{name} ({ident}) = {v}' for ident, name, _path, v in keying.node_inputs(mod)]
    ctx.log(f'grow inputs as the snapshot reads them: {labels}; Height keyed at {H_PATH}')

    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy, sun.data.angle = 3.0, math.radians(2.0)
    sun.rotation_euler = (math.radians(48), 0, math.radians(30))
    scene.collection.objects.link(sun)
    w = bpy.data.worlds.new('sky')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.20, 0.24, 0.30, 1)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 40
    cam.location = (1.5, -2.3, 1.5)
    cam.rotation_euler = (Vector((0, 0, 1.25)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    ctx.cut(0, cam)


def render_frame(ctx, t, i):
    _input(H_ID).value = 0.5 + t                 # 0.5 m -> 2.5 m over the film
    ctx.key(PILLAR, H_PATH)
    if ctx.cfg.get('_unkeyed'):
        _input(T_ID).value = 0.6 * t             # turned, never keyed: the defect the build must name
