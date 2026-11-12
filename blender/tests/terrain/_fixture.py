"""Test fixtures for the terrain family's probes: an empty scene, a TEST daylight (a sun lamp plus a
Sky Texture world: a fixture only, never shipped as a sky; the sky family ports ours), cameras,
render settings at probe size, and the probes' ground (make_terrain's meadow recipe, small, with a
level clearing). Imported by the probe scripts next to it. The ground needs the terrain's GPU
kernels: run the probes through a GPU slot.
"""
import math
import os
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / 'out'
if str(WORKTREE / 'blender') not in sys.path:
    sys.path.insert(0, str(WORKTREE / 'blender'))


def args():
    """Arguments after Blender's `--`."""
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else []


def ground(size=24.0, seed=3, clearing_m=8.0, relief_m=0.8, valley_spacing_m=16.0, name='ground'):
    """The probes' ground: make_terrain('meadow') `size` metres across (draft quality: no hero levels),
    its swales `valley_spacing_m` apart and `relief_m` high, with a level clearing of radius
    `clearing_m` at the origin (blended over 0.6 x the radius), in the meadow palette. Returns
    (obj, height_at); height_at is exact on the mesh's triangles."""
    from eidoblend.terrain import make_terrain
    t = make_terrain('meadow', size=size, seed=seed, quality='draft', palette='meadow', dress=False,
                     params={'relief_m': relief_m, 'valley_spacing_m': valley_spacing_m},
                     flatten=[{'at': (0.0, 0.0), 'radius': clearing_m, 'falloff': 0.6 * clearing_m}],
                     name=name)
    return t.obj, t.height_at


def clean_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.images):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)
    return bpy.context.scene


def render_settings(width=960, height=540, samples=16):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = width
    sc.render.resolution_y = height
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.use_shadows = True
    ee.use_fast_gi = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    # (preferences.system.anisotropic_filter does not reach EEVEE renders: FILTER_0 and FILTER_16
    # rendered pixel-identical on 11-07; the terrain's film material samples Cubic instead)
    return sc


def test_daylight(sun_elevation=32.0, sun_azimuth=135.0, sun_strength=4.0, sky_strength=0.03):
    """TEST FIXTURE ONLY: a sun lamp and a matching Sky Texture world.

    sun_azimuth: compass degrees the light comes FROM (0 = from +Y, 90 = from +X).
    Balance (measured 11-07 on a white lambert plane, sun at 30 deg): the MULTIPLE_SCATTERING sky at
    strength 1 lights a horizontal plane ~8x more than a strength-4 sun does, so the sky runs at ~0.03
    for a clear day's ~4:1 sun-to-sky ratio.
    """
    sc = bpy.context.scene
    w = bpy.data.worlds.new('test_daylight_world')
    sc.world = w
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_disc = False
    sky.sun_elevation = math.radians(sun_elevation)
    sky.sun_rotation = math.radians(sun_azimuth)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = sky_strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    # below the horizon: hazy distant land instead of the sky model's dark blue, so a probe's
    # finite terrain does not end in a "sea" (radiance-matched to sunlit soil, then x 1/strength)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    below = nt.nodes.new('ShaderNodeMapRange')
    below.interpolation_type = 'SMOOTHSTEP'
    below.inputs['From Min'].default_value = 0.004
    below.inputs['From Max'].default_value = -0.02
    nt.links.new(sep.outputs['Z'], below.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(below.outputs['Result'], mix.inputs[0])
    nt.links.new(sky.outputs['Color'], mix.inputs[6])
    mix.inputs[7].default_value = tuple(c / max(sky_strength, 1e-6) for c in (0.105, 0.098, 0.085)) + (1.0,)
    nt.links.new(mix.outputs[2], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    L = bpy.data.lights.new('test_sun', 'SUN')
    L.energy = sun_strength
    L.angle = math.radians(0.53)
    L.color = (1.0, 0.96, 0.9)
    o = bpy.data.objects.new('test_sun', L)
    sc.collection.objects.link(o)
    el, az = math.radians(sun_elevation), math.radians(sun_azimuth)
    toward_sun = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    o.rotation_euler = (-toward_sun).to_track_quat('-Z', 'Y').to_euler()
    return o


def camera(name, location, look_at, lens=35.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 2000
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(location)
    d = Vector(look_at) - Vector(location)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def render(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(path)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    ok = path.exists()
    print('[probe] %s %s (%.1f s)' % ('wrote' if ok else 'FAILED', path, time.time() - t))
    if not ok:
        raise RuntimeError('render did not write ' + str(path))
    return path
