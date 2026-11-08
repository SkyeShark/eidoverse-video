"""eidoverse/examples/basic_vrm.js in Blender: the minimal VRM scene, the starting template for scenes that don't use
the terrain harness. A VRM plays its idle clip on a dark reflective floor under a sky/ground hemisphere and one sun,
in a thin depth fog, while the camera orbits it.

    python eido_blender.py render blender/tests/claudesona/basic_vrm/scene.json --at 0 --at 3 --at 6
    python eido_blender.py render blender/tests/claudesona/basic_vrm/scene_claudesona.json --at 2

The WebGPU example, part by part:
    background 0x0a0a14                the world seen by the camera (Light Path: camera rays), the hemisphere elsewhere
    HemisphereLight(0xffffff, 0x202040, 0.8)   a world gradient, sky white to ground blue-black, radiance 0.8 / pi
                                       (three's light intensities are irradiance; a uniform world of radiance L gives
                                       pi L), as the turntable's studio does
    DirectionalLight(0xffffff, 2.5) at (3, 6, 4)   a sun of strength 2.5 from that direction (three's +y up -> +Z)
    PlaneGeometry(10, 10), color 0x1a1a2e, roughness 0.35, metalness 0.8   the same floor, Principled; EEVEE's
                                       ray-traced reflections give it the "picks up reflections" of the comment
    loader + VRMLoaderPlugin           eidoblend.characters.load_vrm (the VRM add-on's import: MToon kept)
    playVRMADefault(vrm, 'idle')       play_vrma_default(me, 'idle'): the clip as a looping NLA strip
    vrm.update(dt) in the engine loop  the spring bones baked to keys over the film (characters.springs.bake_springs)
    camera.position = (cos 0.4t, 1.4, sin 0.4t) * r, lookAt (0, 1.1, 0), fov 50   keyed per frame in render_frame
    CustomEffectsDeno 'depth_fog', density 0.06   look.post.custom_effects 'depth_fog' (a lit volume box)
    ACESFilmic tone mapping            AgX, the edition's view transform
"""
import math

import bpy
from mathutils import Vector

from eidoblend.characters import load_vrm, play_vrma_default
from eidoblend.characters.springs import bake_springs
from eidoblend.look.post import custom_effects as FX


def lin(hexv):
    out = []
    for ch in ((hexv >> 16) & 255, (hexv >> 8) & 255, hexv & 255):
        s = ch / 255.0
        out.append(s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def world(scene):
    wd = bpy.data.worlds.new('basic_vrm')
    scene.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')                 # three's hemisphere: 0.5 + 0.5 * up
    mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = -1.0, 1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(mr.outputs['Result'], mix.inputs['Factor'])
    mix.inputs['A'].default_value = lin(0x202040) + (1.0,)
    mix.inputs['B'].default_value = lin(0xffffff) + (1.0,)
    hemi = nt.nodes.new('ShaderNodeBackground')
    hemi.inputs['Strength'].default_value = 0.8 / math.pi
    nt.links.new(mix.outputs['Result'], hemi.inputs['Color'])
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = lin(0x0a0a14) + (1.0,)
    lp = nt.nodes.new('ShaderNodeLightPath')
    ms = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], ms.inputs['Fac'])
    nt.links.new(hemi.outputs['Background'], ms.inputs[1])
    nt.links.new(bg.outputs['Background'], ms.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(ms.outputs['Shader'], out.inputs['Surface'])


def setup(ctx):
    scene = ctx.scene
    world(scene)
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy = 2.5
    sun.angle = math.radians(1.0)
    ob = bpy.data.objects.new('sun', sun)
    scene.collection.objects.link(ob)
    p = Vector((3.0, -4.0, 6.0))                             # three (3, 6, 4)
    ob.location = p
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (-p).to_track_quat('-Z', 'Y')

    me = bpy.data.meshes.new('floor')
    me.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new('floor')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(0x1a1a2e) + (1.0,)
    b.inputs['Roughness'].default_value = 0.35
    b.inputs['Metallic'].default_value = 0.8
    me.materials.append(m)
    floor = bpy.data.objects.new('floor', me)
    scene.collection.objects.link(floor)

    vrm = load_vrm(ctx.assets['character_vrm'])
    play_vrma_default(vrm, 'idle', loop=True, until=ctx.duration)
    bake_springs(vrm, ctx.frame_start, ctx.frame_end)          # the engine's vrm.update(dt): springs, every frame

    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(50.0)
    cd.clip_start, cd.clip_end = 0.1, 100.0
    cam = bpy.data.objects.new('cam', cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    place_camera(cam, 0.0)

    FX.apply_to(scene, 'depth_fog', {'depth_fog': {'density': 0.06}})


def place_camera(cam, t):
    r, a = 2.5, t * 0.4
    cam.location = Vector((math.cos(a) * r, -math.sin(a) * r, 1.4))     # three (cos a r, 1.4, sin a r)
    aim = Vector((0.0, 0.0, 1.1))
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler('XYZ', cam.rotation_euler)


def render_frame(ctx, t, i):
    cam = ctx.scene.camera
    place_camera(cam, t)
    ctx.key(cam, 'location')
    ctx.key(cam, 'rotation_euler')
