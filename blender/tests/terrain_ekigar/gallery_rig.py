"""The camera and light Ekigar's visual suite renders every operator with (examples.GALLERY_VIEW: azimuth 42,
elevation 36, distance 1.38 tiles, fov 40; a warm sun at three (-0.7, 0.6, -0.45) over a sky/ground hemisphere at
Ekigar's 14:1 sun-to-sky ratio) as a Blender EEVEE scene, shared by the gallery and variant renders.

Exposure: Ekigar tone-maps with ACES at three's default exposure; the same light through AgX at exposure 0 put lit
flat ground near white and flattened the forms (the first gallery). exposure -0.6 with AgX Medium High Contrast keeps
the light, its ratio and direction, and brings lit ground to mid grey, so slopes away from the sun read dark.
"""
import math

import bpy
from mathutils import Vector

from eidoblend.terrain import ekigar

V = ekigar.GALLERY_VIEW


def srgb(hexs):
    c = [int(hexs[k:k + 2], 16) / 255.0 for k in (1, 3, 5)]
    return tuple((v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c)


def setup_scene(W=100.0, samples=16, exposure=-0.6, look='AgX - Medium High Contrast', image=None):
    """A fresh scene with the suite's world, sun and camera for a W-metre tile centred on the origin."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = look
    except TypeError:
        pass
    sc.view_settings.exposure = exposure
    sc.render.resolution_x, sc.render.resolution_y = image or V['image']
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    world = bpy.data.worlds.new('gallery_world')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    hemi = nt.nodes.new('ShaderNodeMix')
    hemi.data_type = 'RGBA'
    hemi.inputs[6].default_value = (*srgb(V['hemisphere']['ground']), 1.0)
    hemi.inputs[7].default_value = (*srgb(V['hemisphere']['sky']), 1.0)
    nt.links.new(mr.outputs['Result'], hemi.inputs[0])
    bg_light = nt.nodes.new('ShaderNodeBackground')
    # three lights a surface with hemisphere irradiance = colour * intensity; a Blender world of strength S gives
    # pi * S * colour, so S = intensity / pi keeps Ekigar's sun-to-sky ratio
    bg_light.inputs['Strength'].default_value = V['hemisphere']['intensity'] / math.pi
    nt.links.new(hemi.outputs[2], bg_light.inputs['Color'])
    bg_cam = nt.nodes.new('ShaderNodeBackground')
    bg_cam.inputs['Color'].default_value = (*srgb(V['background']), 1.0)
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(bg_light.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    sun_d = bpy.data.lights.new('sun', 'SUN')
    sun_d.energy = V['sun']['intensity']
    sun_d.color = srgb(V['sun']['colour'])
    sun_d.angle = math.radians(1.0)
    sun = bpy.data.objects.new('sun', sun_d)
    sc.collection.objects.link(sun)
    px, py, pz = V['sun']['position_three']
    d = Vector((px, -pz, py))                        # three (x, y, z) -> Blender (x, -z, y)
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam_d = bpy.data.cameras.new('cam')
    cam_d.sensor_fit = 'VERTICAL'
    cam_d.angle_y = math.radians(V['camera']['fov_deg'])
    cam_d.clip_start = 0.1
    cam_d.clip_end = 20 * W
    cam = bpy.data.objects.new('cam', cam_d)
    sc.collection.objects.link(cam)
    a = math.radians(V['camera']['azimuth_deg'])
    e = math.radians(V['camera']['elevation_deg'])
    dist = V['camera']['distance'] * W
    cam.location = (dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e))
    cam.rotation_euler = (-cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    return sc
