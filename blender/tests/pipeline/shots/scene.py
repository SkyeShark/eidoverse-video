"""Test T16: two shots joined by a cut, after the verifier's cut probe. Shot A (0-1 s): a wooden crate slides
3 m/s across a concrete floor under a low sun, a small warm lamp low (20 W). Shot B (1-2 s): a closer camera on a
vintage kettle, the lamp up to 600 W. frame_start 0, the film preset's motion blur on.

What it checks (run_tests.py T16): the keys render_frame makes are LINEAR (the crate) or CONSTANT where asked (the
lamp's step at the cut), and the saved film shows them (20 W in shot A, 600 W in shot B); nothing is changed
without a key; each shot's framing record measures the subject ITS camera sees (the kettle in shot B, where the
crate is out of frame).
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import assets


def look(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def setup(ctx):
    scene = ctx.scene
    conc = assets.load_pbr('Concrete034', res='2k', maps=('diff', 'normal', 'rough'), repeat=(0.5, 0.5))
    me = bpy.data.meshes.new('floor')                              # 60 m: its edge stays out of both shots
    me.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (60, 0), (60, 60), (0, 60)]):
        loop.uv = (u, v)
    me.materials.append(conc)
    floor = bpy.data.objects.new('floor', me)
    scene.collection.objects.link(floor)

    global CRATE, X0, LAMP
    CRATE = assets.import_model(assets.fetch_model_file('wooden_military_crate', res='1k'), name='crate')
    assets.rest_on(CRATE, 0.0, xy=(-1.5, 0.0))
    X0 = CRATE.location.x
    kettle = assets.import_model(assets.fetch_model_file('vintage_electric_kettle', res='2k'), name='kettle')
    assets.rest_on(kettle, 0.0, xy=(0.0, 2.0))
    kettle.rotation_euler.z = math.radians(-35)

    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy, sun.data.angle = 3.0, math.radians(1.0)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    scene.collection.objects.link(sun)
    LAMP = bpy.data.objects.new('lamp', bpy.data.lights.new('lamp', 'POINT'))
    LAMP.data.shadow_soft_size = 0.1
    LAMP.data.color = (1.0, 0.55, 0.25)
    LAMP.data.energy = 20.0
    LAMP.location = (0.6, 0.8, 1.2)
    scene.collection.objects.link(LAMP)
    w = bpy.data.worlds.new('dim')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
    scene.world = w

    cam_a = bpy.data.objects.new('cam_A', bpy.data.cameras.new('cam_A'))
    cam_a.data.lens = 35                                          # the crate crosses this frame, left to right
    cam_a.location = (0.0, -3.4, 1.0)
    look(cam_a, (0.0, 0.0, 0.3))
    cam_b = bpy.data.objects.new('cam_B', bpy.data.cameras.new('cam_B'))
    cam_b.data.lens = 50
    cam_b.location = (2.2, -0.2, 0.9)
    look(cam_b, (0.0, 2.0, 0.15))
    for c in (cam_a, cam_b):
        scene.collection.objects.link(c)
    ctx.cut(0, cam_a)
    ctx.cut(1.0, cam_b)


def render_frame(ctx, t, i):
    CRATE.location.x = X0 + 3.0 * min(t, 1.0)
    ctx.key(CRATE, 'location')
    LAMP.data.energy = 20.0 if t < 1.0 else 600.0
    ctx.key(LAMP.data, 'energy', interpolation='CONSTANT')       # a step at the cut, not a ramp across it
