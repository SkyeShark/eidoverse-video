"""The engine's overlay layer and auto-enhance hooks through the real runner (run_tests.py U4).

A crate on a concrete floor under a warm key; module-level hooks, as the WebGPU globals were: the colour hook
desaturates the world, the screen hook inverts the whole frame; an overlay layer carries an html_mesh lower third
(orange on near-black). In the engine's order the overlay comes after the colour hook and before the screen hook, so
the still shows a grey (desaturated) world inverted, and the card NOT desaturated but inverted: its near-black panel
turns near-white and its orange text turns blue. The view is Standard so those colours can be measured (the digest
warns that the view is not AgX: a deliberate choice for this test).

    python eido_blender.py render blender/tests/pipeline2/overlay/scene.json --at 1
"""
import json
import math

import bpy
from mathutils import Vector

from eidoblend.harness import assets, post
from eidoblend.harness.html_mesh import El, html_mesh
from eidoblend.placement import place_on

_bloom_params = {'strength': 0.0}          # the engine's knob: strength 0 is no bloom


def _auto_enhance_color_hook(scene, tree):
    n = tree.nodes.new('CompositorNodeHueSat')
    n.inputs['Saturation'].default_value = 0.0
    return n


def _auto_enhance_screen_hook(scene, tree):
    return tree.nodes.new('CompositorNodeInvert')


def setup(ctx):
    global _overlay
    scene = ctx.scene
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    me = bpy.data.meshes.new('floor')
    me.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (4, 0), (4, 4), (0, 4)]):
        loop.uv = (u, v)
    me.materials.append(assets.load_pbr('Concrete034', res='2k', maps=('diff', 'normal', 'rough'), repeat=(1, 1)))
    floor = bpy.data.objects.new('floor', me)
    scene.collection.objects.link(floor)
    crate = assets.import_model(assets.fetch_model_file('wooden_military_crate', res='1k'), name='crate')
    crate.rotation_euler.z = math.radians(25)
    place_on(crate, floor, xy=(0.0, 0.3))
    key = bpy.data.objects.new('key', bpy.data.lights.new('key', 'AREA'))
    key.data.shape, key.data.size, key.data.energy, key.data.color = 'DISK', 0.8, 400.0, (1.0, 0.75, 0.45)
    key.location = (-1.6, -1.2, 2.2)
    key.rotation_euler = (Vector((0, 0.3, 0.3)) - key.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(key)
    w = bpy.data.worlds.new('dusk')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.05, 0.12, 1)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 35
    cam.location = (1.4, -2.6, 1.2)
    cam.rotation_euler = (Vector((0, 0.3, 0.35)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
    _overlay = post.make_overlay_layer(scene)
    card = El('div', style='display: inline-block; padding: 18px 30px; background: #0d1014; color: #ff9a1a; '
                           'font: 700 56px Rajdhani-Bold; border-left: 10px solid #ff9a1a',
              children=[El('div', text='OVERLAY LAYER'), El('div', style='font: 400 26px SpaceMono-Regular; '
                                                                         'color: #ff9a1a', text='after the colour hook')])
    scr = html_mesh(card, name='lower_third', scene=_overlay.scene)
    obj = scr.obj
    obj.rotation_euler = (-math.pi / 2, 0, 0)                    # its face (-Y) toward the overlay camera (+Z)
    _overlay.add(obj)
    w_m, h_m = obj.dimensions.x, obj.dimensions.z
    obj.location = (-_overlay.half_w + 0.06 + w_m / 2, -_overlay.half_h + 0.07 + h_m / 2, -1.0)
    box = [0.06 / (2 * _overlay.half_w), 1.0 - (0.07 + h_m) / (2 * _overlay.half_h),      # left, top, right, bottom
           (0.06 + w_m) / (2 * _overlay.half_w), 1.0 - 0.07 / (2 * _overlay.half_h)]    # (frame fractions, y down)
    ctx.record('overlay_card', 'PASS', json.dumps({'box': box}))
