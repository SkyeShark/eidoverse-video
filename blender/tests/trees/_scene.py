"""Shared probe-scene helpers for the trees tests (self-contained on purpose: the
trees family imports no other family's subpackage).

The probe world is a neutral test stage: a physical Sky Texture + a sun lamp and a
ground plane wearing SeedThree's own grass/desert ground PBR set. Films light trees
with the sky family's make_sky; these probes only need honest, repeatable light.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'out')
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return [x for x in a if x != '--']


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def render_settings(scene, w=960, h=540, samples=16):
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    ee = scene.eevee
    ee.taa_render_samples = samples
    for attr, val in (('use_raytracing', True), ('use_shadows', True), ('shadow_ray_count', 2),
                      ('shadow_step_count', 8), ('use_volumetric_shadows', False)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    if hasattr(ee, 'ray_tracing_options'):
        ee.ray_tracing_options.resolution_scale = '2'
    if hasattr(ee, 'fast_gi_method'):
        try:
            ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
        except TypeError:
            pass
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    if vs.view_transform != 'AgX':
        raise RuntimeError('AgX view transform not available')
    try:
        vs.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False


def sky_and_sun(scene, sun_elev_deg=38.0, sun_az_deg=135.0, strength=1.0, sun_strength=4.0):
    """Sun azimuth: degrees from +Y toward +X, the direction the light COMES FROM."""
    world = bpy.data.worlds.new('probe sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new('ShaderNodeTexSky')
    for t in ('MULTIPLE_SCATTERING', 'NISHITA', 'HOSEK_WILKIE'):
        try:
            sky.sky_type = t
            break
        except TypeError:
            continue
    el, az = math.radians(sun_elev_deg), math.radians(sun_az_deg)
    for attr, val in (('sun_elevation', el), ('sun_rotation', az), ('altitude', 200.0), ('air_density', 1.0),
                      ('dust_density', 1.0), ('ozone_density', 1.0), ('sun_disc', False)):
        if hasattr(sky, attr):
            setattr(sky, attr, val)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    sun_data = bpy.data.lights.new('probe sun', 'SUN')
    sun_data.energy = sun_strength
    sun_data.angle = math.radians(0.6)
    sun_data.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new('probe sun', sun_data)
    scene.collection.objects.link(sun)
    # light travels opposite to where it comes from
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return sun, sky


def ground(scene, assets_dir, kind='grass', size=400.0, tile=3.0):
    me = bpy.data.meshes.new('probe ground')
    s = size / 2
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    k = size / tile
    for i, (u, v) in enumerate(((0, 0), (k, 0), (k, k), (0, k))):
        uv.data[i].uv = (u, v)
    ob = bpy.data.objects.new('probe ground', me)
    scene.collection.objects.link(ob)
    mat = bpy.data.materials.new('probe ground ' + kind)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    base = os.path.join(assets_dir, 'ground', kind)
    for suffix, sock, nc in (('_albedo.png', 'Base Color', False), ('_roughness.png', 'Roughness', True),
                             ('_normal.png', 'Normal', True)):
        p = base + suffix
        if not os.path.isfile(p):
            continue
        img = bpy.data.images.load(p, check_existing=True)
        img.colorspace_settings.name = 'Non-Color' if nc else 'sRGB'
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        if sock == 'Normal':
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(tex.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        elif sock == 'Roughness':
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(tex.outputs['Color'], sep.inputs[0])
            nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
        else:
            nt.links.new(tex.outputs['Color'], bsdf.inputs[sock])
    me.materials.append(mat)
    return ob


def camera(scene, loc, target, lens=35.0, name='probe cam'):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.1
    cd.clip_end = 2000
    cam = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def render(scene, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if not os.path.isfile(path):
        raise RuntimeError('render did not write ' + path)
    print('[trees] wrote', path)
