"""The overlay layer and the auto-enhance hooks as a film uses them (run_tests.py U6): a lower third over a graded shot.

A vintage kettle and an old camera on a crate against a plaster wall, a slow keyed push-in. The engine's hooks, named
at module level as its globals were:
    _bloom_params                  a soft bloom on the chrome's highlights (the chain's Glare)
    _auto_enhance_color_hook       a warm documentary grade (a little less saturation, warm gain), UNDER the overlay
    _auto_enhance_screen_hook      a vignette, OVER the overlay (a HUD is part of the picture the lens darkens)
and an html_mesh lower third on the overlay layer (make_overlay_layer), placed with the media overlay's place() and
sliding in from the left over the first 0.75 s (keyed). The overlay lands as drawn (post.py's authored route: the
over in display space), and the vignette after it darkens the HUD with the film.

    python eido_blender.py render blender/tests/pipeline2/lower_third/scene.json --at 2
"""
import math
import os

import bpy
from mathutils import Vector

from eidoblend.harness import assets, post
from eidoblend.harness.html_mesh import El, html_mesh
from eidoblend.placement import place_on

_bloom_params = {'strength': 0.12, 'radius': 0.55, 'threshold': 1.4}


def _group(name):
    """A compositor node group with one Image in and one Image out: a hook returns one node, and a group carries a
    graph of any size."""
    g = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    g.interface.new_socket('Image', in_out='INPUT', socket_type='NodeSocketColor')
    g.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    return g, g.nodes.new('NodeGroupInput'), g.nodes.new('NodeGroupOutput')


def _multiply(g, a, b_colour=None, b=None, factor=1.0):
    m = g.nodes.new('ShaderNodeMix')
    m.data_type, m.blend_type = 'RGBA', 'MULTIPLY'
    m.inputs[0].default_value = factor
    g.links.new(a, m.inputs[6])
    if b is not None:
        g.links.new(b, m.inputs[7])
    else:
        m.inputs[7].default_value = b_colour
    return m.outputs[2]


def _auto_enhance_color_hook(scene, tree):
    g, gi, go = _group('warm_grade')
    hs = g.nodes.new('CompositorNodeHueSat')
    hs.inputs['Saturation'].default_value = 0.9
    g.links.new(gi.outputs[0], hs.inputs['Image'])
    g.links.new(_multiply(g, hs.outputs['Image'], (1.07, 1.0, 0.88, 1.0)), go.inputs[0])
    n = tree.nodes.new('CompositorNodeGroup')
    n.node_tree = g
    return n


def _auto_enhance_screen_hook(scene, tree):
    g, gi, go = _group('vignette')
    em = g.nodes.new('CompositorNodeEllipseMask')
    em.inputs['Size'].default_value = (1.05, 1.05)
    bl = g.nodes.new('CompositorNodeBlur')
    bl.inputs['Size'].default_value = (220, 220)
    g.links.new(em.outputs['Mask'], bl.inputs['Image'])
    lift = g.nodes.new('ShaderNodeMix')                            # 0.55 at the corners, 1 inside the ellipse
    lift.data_type = 'RGBA'
    g.links.new(bl.outputs['Image'], lift.inputs[0])
    lift.inputs[6].default_value = (0.55, 0.55, 0.55, 1.0)
    lift.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)
    g.links.new(_multiply(g, gi.outputs[0], b=lift.outputs[2]), go.inputs[0])
    n = tree.nodes.new('CompositorNodeGroup')
    n.node_tree = g
    return n


if os.environ.get('EIDO_TEST_NO_VIGNETTE') == '1':     # run_tests.py U6's reference still: the same film, no screen hook
    del _auto_enhance_screen_hook


def _plane(name, size, loc, rot, mat, uv=0.5):
    me = bpy.data.meshes.new(name)
    sx, sy = size
    me.from_pydata([(-sx / 2, -sy / 2, 0), (sx / 2, -sy / 2, 0), (sx / 2, sy / 2, 0), (-sx / 2, sy / 2, 0)], [],
                   [(0, 1, 2, 3)])
    lay = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(lay.data, [(0, 0), (sx * uv, 0), (sx * uv, sy * uv), (0, sy * uv)]):
        loop.uv = (u, v)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location, ob.rotation_euler = loc, rot
    return ob


def _area(scene, name, loc, aim, watts, size, colour):
    ob = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
    ob.data.shape, ob.data.size, ob.data.energy, ob.data.color = 'DISK', size, watts, colour
    ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(ob)
    return ob


def setup(ctx):
    global _overlay
    scene = ctx.scene

    def pbr(t):
        return assets.load_pbr(t, res='2k', maps=('diff', 'normal', 'rough'), repeat=(1, 1))
    floor = _plane('floor', (8, 8), (0, 0, 0), (0, 0, 0), pbr('WoodFloor064'), 0.6)
    _plane('wall', (8, 3.2), (0, 1.1, 1.6), (math.pi / 2, 0, 0), pbr('PaintedPlaster015'))
    crate = assets.import_model(assets.fetch_model_file('wooden_military_crate', res='1k'), name='crate')
    crate.rotation_euler.z = math.radians(-8)
    place_on(crate, floor, xy=(0.0, 0.35))
    kettle = assets.import_model(assets.fetch_model_file('vintage_electric_kettle', res='2k'), name='kettle')
    kettle.rotation_euler.z = math.radians(-35)
    place_on(kettle, crate, xy=(-0.12, 0.33))
    cam_prop = assets.import_model(assets.fetch_model_file('Camera_01', res='1k'), name='old_camera')
    cam_prop.rotation_euler.z = math.radians(25)
    place_on(cam_prop, crate, xy=(0.28, 0.36), z_offset=0.0025)   # its strap lies flat: 2.5 mm off the lid, no flicker
    _area(scene, 'window_key', (-1.5, -0.7, 1.4), (0, 0.35, 0.55), 220, 1.2, (1.0, 0.86, 0.68))
    _area(scene, 'fill', (1.6, -1.4, 0.9), (0, 0.35, 0.5), 35, 2.0, (0.75, 0.85, 1.0))
    _area(scene, 'rim', (0.9, 1.0, 1.5), (0, 0.35, 0.55), 60, 0.4, (1.0, 0.95, 0.9))
    w = bpy.data.worlds.new('room')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.055, 0.06, 1)
    scene.world = w
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    aim = Vector((0.05, 0.35, 0.5))
    for f, p in ((ctx.frame_at(0.0), Vector((0.75, -1.85, 0.85))), (ctx.frame_at(3.0), Vector((0.55, -1.45, 0.78)))):
        cam.location = p
        cam.rotation_euler = (aim - p).to_track_quat('-Z', 'Y').to_euler()
        ctx.key_transform(cam, frame=f, interpolation='BEZIER')
    _overlay = post.make_overlay_layer(scene)
    card = El('div', style='display: inline-block; padding: 16px 30px 18px 26px; background: rgba(12, 13, 16, 0.80); '
                           'border-left: 8px solid #e8b04a; color: #f4efe6; font: 700 50px Rajdhani-Bold; '
                           'text-transform: uppercase; letter-spacing: 1px',
              children=[El('div', text='Vintage electric kettle'),
                        El('div', style='font: 400 22px SpaceMono-Regular; color: #d9cdb8; text-transform: none',
                           text='from the workshop shelf')])
    obj = html_mesh(card, name='lower_third', scene=_overlay.scene).obj
    obj.rotation_euler = (-math.pi / 2, 0, 0)                    # its face (-Y) toward the overlay camera (+Z)
    # html_mesh is 1 mm a pixel; at the overlay's depth (1 m) a 50 mm lens frames 2 x half_w = 0.72 m: size the card
    # as a fraction of the frame, 42 % of its width. Its size from the mesh's own bounds: the overlay scene is not
    # the one view_layer.update() evaluates, so obj.dimensions would read a stale matrix
    xs, zs = [c[0] for c in obj.bound_box], [c[2] for c in obj.bound_box]
    w_m, h_m = max(xs) - min(xs), max(zs) - min(zs)
    s = 0.42 * 2 * _overlay.half_w / w_m
    obj.scale = (s, s, s)
    fw, fh = w_m * s / (2 * _overlay.half_w), h_m * s / (2 * _overlay.half_h)   # the card as frame fractions
    x_in, y = -0.5 + 0.05 + fw / 2, -0.5 + 0.09 + fh / 2
    for t, x in ((0.0, -0.5 - fw / 2 - 0.02), (0.75, x_in)):     # slides in from beyond the left edge
        _overlay.place(obj, x=x, y=y)
        ctx.key(obj, 'location', frame=ctx.frame_at(t), interpolation='BEZIER')
    ctx.record('lower_third', 'PASS', f'card {fw:.2f} x {fh:.2f} of the frame, in place from 0.75 s')
