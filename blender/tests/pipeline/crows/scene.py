"""Test T5: a model's own clips. Two crows on old planks: the imported one pecks, its clone (its own rig, the mesh
shared) caws, offset in time, so they never move in unison. Feet at the origin, real scale, nose along glTF +z
(Blender -y), so a crow at rotation 0 faces the camera.

    python eido_blender.py render blender/tests/pipeline/crows/scene.json --at 0.5 --at 1.6 --at 2.6
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import assets


def setup(ctx):
    scene = ctx.scene
    planks = assets.load_pbr('Planks039', res='1k', maps=('diff', 'normal', 'rough'), repeat=(0.6, 0.6))
    me = bpy.data.meshes.new('deck')
    me.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (8, 0), (8, 8), (0, 8)]):
        loop.uv = (u, v)
    me.materials.append(planks)
    deck = bpy.data.objects.new('deck', me)
    scene.collection.objects.link(deck)

    a = assets.import_model(ctx.assets['crow'], name='crow_peck')
    a.rotation_euler.z = math.radians(35)
    played = assets.play_model_animations(a, clip='Peck')
    b = assets.clone_model(a, name='crow_caw', location=(0.75, 0.55, 0.0))
    b.rotation_euler.z = math.radians(-30)
    assets.play_model_animations(b, clip='Caw', offset=0.4)
    ctx.log('clips:', played, '+ Caw on the clone;', 'all clips:', sorted(assets.model_clips(a)))

    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA'))
    key.data.shape, key.data.size, key.data.energy = 'DISK', 2.0, 300.0
    key.data.color = (1.0, 0.9, 0.8)
    key.location = (-1.8, -1.2, 2.2)
    key.rotation_euler = (Vector((0.3, 0.2, 0.2)) - key.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(key)
    w = bpy.data.worlds.new('dusk')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
    scene.world = w

    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 40
    cam.location = (0.9, -2.6, 0.75)
    cam.rotation_euler = (Vector((0.35, 0.25, 0.25)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
