"""The finishing example in Blender (eidoverse/examples/finishing/scene.js): the classic Claude sona sings the example
song's two lines on a small dark stage, under a warm key and a cool rim, while the camera pushes in from the whole
figure to the face. Its mouth is read from the vocal stem in Blender's own Python
(characters.lipsync.visemes_from_vocal: lipsync.py's get_viseme_timeline_from_vocal, values 0..1) and keyed at build
time on the VRM's expressions. From the repository root:

    python eidoverse/examples/finishing/song.py                     # the song, its vocal stem and words (system Python)
    python eido_blender.py render blender/tests/finishing/scene.json --at 4 --at 9.5
    python eido_blender.py render blender/tests/finishing/scene.json
    python eidoverse/examples/finishing/finish.py --film blender/tests/finishing/out/finishing_video_only.mp4

finish.py merges the song, measures it (song_clock.py), prints the film (film_print.py) and lays it out line by line
(contact_sheet.py --lines) into work/finishing/. Coordinates: Z up, metres; the sona faces -Y, the camera looks
along +Y.
"""
import json
import math

import bpy
from mathutils import Vector

from eidoblend.characters import lipsync as L
from eidoblend.characters import load_vrm, play_vrma_default
from eidoblend.characters.springs import bake_springs


def lin(hexv):
    out = []
    for ch in ((hexv >> 16) & 255, (hexv >> 8) & 255, hexv & 255):
        s = ch / 255.0
        out.append(s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def material(name, hexv, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(hexv) + (1.0,)
    b.inputs['Roughness'].default_value = roughness
    return m


def spot(name, location, target, power, colour, angle, blend):
    li = bpy.data.lights.new(name, 'SPOT')
    li.energy, li.color, li.spot_size, li.spot_blend = power, colour, angle, blend
    li.shadow_soft_size = 0.25
    ob = bpy.data.objects.new(name, li)
    ob.location = location
    ob.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup(ctx):
    scene = ctx.scene
    world = bpy.data.worlds.new('stage')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = lin(0x0d0a08) + (1.0,)   # a dark house; the stage's own bounce is the fill
    bg.inputs['Strength'].default_value = 1.0
    scene.world = world

    # the stage: a slab of boards, its top at z 0 (the ground), and a deep red curtain with folds behind
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=3.2, depth=0.02, location=(0.0, 0.0, -0.01))
    boards = bpy.context.active_object
    boards.name = 'boards'
    boards['no_support_check'] = True                           # the stage floor itself: nothing stands under it
    boards.data.materials.append(material('boards', 0x5a3a22, 0.55))
    me = bpy.data.meshes.new('curtain')
    cols, rows = 91, 2
    verts = [(-4.5 + 9.0 * i / (cols - 1), 2.2 + 0.12 * math.sin((-4.5 + 9.0 * i / (cols - 1)) * 7.0), 5.0 * j)
             for j in range(rows) for i in range(cols)]
    faces = [(i, i + 1, cols + i + 1, cols + i) for i in range(cols - 1)]
    me.from_pydata(verts, [], faces)
    me.materials.append(material('curtain', 0x5c0a10, 0.85))
    curtain = bpy.data.objects.new('curtain', me)
    scene.collection.objects.link(curtain)
    for p in curtain.data.polygons:
        p.use_smooth = True

    # light: a warm key from the front left, a cool rim from behind right
    spot('key', (-1.6, -2.6, 3.2), (0.0, 0.0, 1.2), 650.0, (1.0, 0.85, 0.69), 0.84, 0.6)
    spot('rim', (1.8, 1.6, 2.6), (0.0, 0.0, 1.3), 380.0, (0.56, 0.72, 1.0), 1.0, 0.7)

    vrm = load_vrm(ctx.assets['character_vrm'])
    play_vrma_default(vrm, 'stand_breathe', loop=True, until=ctx.duration)
    bake_springs(vrm, ctx.frame_start, ctx.frame_end)          # the engine's vrm.update(dt): springs, every frame
    with open(ctx.assets['timeline'], encoding='utf-8') as f:
        words = json.load(f)['words']
    vis = L.visemes_from_vocal(ctx.assets['vocal'], words, fps=ctx.fps)
    L.key_lipsync(vrm, vis, start_t=0.0, input_max=1.0)       # raw 0..1 on the expressions

    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(32.0)
    cd.clip_start, cd.clip_end = 0.1, 60.0
    cam = bpy.data.objects.new('cam', cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    place_camera(cam, 0.0, ctx.duration)


def place_camera(cam, t, duration):
    x = min(1.0, max(0.0, t / duration))
    k = x * x * (3 - 2 * x)                                     # from the whole figure to the face
    cam.location = Vector((0.35 - 0.3 * k, -(4.4 - 3.1 * k), 1.25 + 0.2 * k))
    aim = Vector((0.0, 0.0, 1.0 + 0.42 * k))
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler('XYZ', cam.rotation_euler)


def render_frame(ctx, t, i):
    cam = ctx.scene.camera
    place_camera(cam, t, ctx.duration)
    ctx.key(cam, 'location')
    ctx.key(cam, 'rotation_euler')
