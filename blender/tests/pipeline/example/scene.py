"""The Blender edition's smallest whole scene: a wooden stool with an alarm clock on it, in the corner of a plaster
room on a wood floor, lit by a soft warm key and a cool fill; the camera pushes in over three seconds.

    python eido_blender.py render blender/tests/pipeline/example/scene.json --at 0 --at 1.5 --at 3
    python eido_blender.py render blender/tests/pipeline/example/scene.json

Everything real comes from the shared library (Poly Haven / AmbientCG, CC0): the floor, the walls, the stool and the
clock, at real-world scale. The stool and the clock are seated with the placement family's place_on (each on the
highest surface under its footprint), so the runner runs that family's audits too: a piece left floating by a
later hand edit is named in the digest. Coordinates: Z up, metres; the camera looks along +Y into the corner.
"""
import math

import bpy
from mathutils import Vector

from eidoblend.harness import assets
from eidoblend.placement import place_on


def plane(name, size, location, rotation, material):
    me = bpy.data.meshes.new(name)
    w, h = size
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, (u, v) in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = (u * w, v * h)                     # one UV unit per metre: repeat = tiles per metre
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    ob.location, ob.rotation_euler = location, rotation
    bpy.context.scene.collection.objects.link(ob)
    return ob


def area_light(name, location, target, size, power, colour):
    li = bpy.data.lights.new(name, 'AREA')
    li.shape, li.size, li.energy, li.color = 'DISK', size, power, colour
    ob = bpy.data.objects.new(name, li)
    ob.location = location
    ob.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup(ctx):
    scene = ctx.scene
    # the room: a 6 m floor and two 3 m plaster walls meeting in a corner behind the stool
    wood = assets.load_pbr('WoodFloor064', res='2k', maps=('diff', 'normal', 'rough'), repeat=(0.5, 0.5))
    plaster = assets.load_pbr('PaintedPlaster017', res='2k', maps=('diff', 'normal', 'rough'), repeat=(0.5, 0.5))
    floor = plane('floor', (6, 6), (0, 1.0, 0), (0, 0, 0), wood)
    plane('wall_back', (6, 3), (0, 1.6, 1.5), (math.radians(90), 0, 0), plaster)
    plane('wall_left', (6, 3), (-1.4, 1.0, 1.5), (math.radians(90), 0, math.radians(90)), plaster)

    stool = assets.import_model(assets.fetch_model_file('wooden_stool_01', res='1k'), name='stool')
    stool.rotation_euler.z = math.radians(18)
    place_on(stool, floor, xy=(0.0, 0.55))
    clock = assets.import_model(assets.fetch_model_file('alarm_clock_01', res='2k'), name='clock')
    clock.rotation_euler.z = math.radians(-24)
    place_on(clock, stool, xy=(0.03, 0.52))
    top = assets.bounds(stool)[1].z

    # light: a warm key from camera left, small enough (a 0.5 m softbox) that the stool casts a shadow you can read
    # and its feet meet the floor; a cool fill from the right, weak, so the shadow side stays a shadow
    area_light('key', (-1.1, -0.4, 1.7), (0.0, 0.55, 0.5), 0.5, 260.0, (1.0, 0.86, 0.72))
    area_light('fill', (1.3, -0.9, 1.1), (0.0, 0.55, 0.5), 1.0, 30.0, (0.78, 0.86, 1.0))
    world = bpy.data.worlds.new('room')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.045, 0.043, 0.04, 1.0)   # the room's own dim bounce, not a sky
    bg.inputs['Strength'].default_value = 1.0
    scene.world = world

    cam_data = bpy.data.cameras.new('cam')
    cam_data.lens = 50
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 4.0
    cam = bpy.data.objects.new('cam', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # a push-in: from the whole stool standing on the floor to the clock on it
    global START, END, AIM_START, AIM_END
    START, END = Vector((0.75, -1.75, 1.05)), Vector((0.42, -0.85, 0.85))
    AIM_START, AIM_END = Vector((0.02, 0.55, 0.30)), Vector((0.03, 0.52, top + 0.05))
    cam_data.dof.focus_object = clock
    place_camera(cam, 0.0)


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def place_camera(cam, t):
    k = smoothstep(t / DURATION)
    cam.location = START.lerp(END, k)
    aim = AIM_START.lerp(AIM_END, k)
    # compatible with the previous frame's angles, so a keyed rotation never wraps through 360 degrees
    cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler('XYZ', cam.rotation_euler)


def render_frame(ctx, t, i):
    cam = ctx.scene.camera
    place_camera(cam, t)
    ctx.key(cam, 'location')
    ctx.key(cam, 'rotation_euler')
