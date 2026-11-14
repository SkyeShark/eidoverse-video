"""Shared test scaffolding for the flora probes (headless Blender 5.2): a clean EEVEE scene, TEST lights (a sun and a
plain sky colour: the flora family cannot import the sky family's subpackage, so these stand in for lookdev only),
a ground plane with the CC0 Poly Haven leafy_grass texture from the shared texture cache (fetch_texture.py
leafy_grass 2k --cache), a camera, and a still render.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
PHYS_SKY_K = 0.12 / 11.37       # lights(physical=True): background strength per unit of sun strength (see lights)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return a


def arg(name, default=None):
    a = args()
    return a[a.index(name) + 1] if name in a else default


def new_scene(res=(960, 540), samples=16):
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = 24
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_raytracing = True
    sc.eevee.use_shadows = True
    sc.eevee.shadow_ray_count = 2
    sc.eevee.shadow_step_count = 8
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False
    try:
        bpy.context.preferences.system.anisotropic_filter = 'FILTER_8'
    except Exception:
        pass
    return sc


def lights(sun_elev_deg=38.0, sun_az_deg=-60.0, strength=4.0, sky=(0.42, 0.58, 0.85), sky_strength=1.0, angle_deg=1.0,
           gradient=False, physical=False, color=(1.0, 1.0, 1.0)):
    """TEST lights: a sun (azimuth measured from +X toward +Y, the direction the light COMES FROM) and a plain sky:
    flat, or with gradient=True a horizon-to-zenith ramp over a dark ground hemisphere (no light from below), or with
    physical=True Blender's own multiple-scattering clear sky for the same sun (its disc off: the sun lamp is the
    direct light) at sky_strength x PHYS_SKY_K x strength, so its horizontal irradiance is ~12 % of the sun's normal
    irradiance, a clear day's diffuse share at a 30 deg sun (measured with a Cycles equirect of the node: 11.37 at
    strength 1 for a 30 deg sun, 10.5 at 24, 11.9 at 34; its sun_rotation r puts the sun at azimuth 90 deg - r)."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new('test_world')
    sc.world = w
    nt = w.node_tree
    bg = nt.nodes.get('Background') or nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*sky, 1.0)
    bg.inputs['Strength'].default_value = sky_strength
    if physical:
        st = nt.nodes.new('ShaderNodeTexSky')
        st.sky_type = 'MULTIPLE_SCATTERING'
        st.sun_disc = False
        st.sun_elevation = math.radians(sun_elev_deg)
        st.sun_rotation = math.radians(90.0 - sun_az_deg)
        k = sky_strength * PHYS_SKY_K * strength
        bg.inputs['Strength'].default_value = k
        # below the horizon: sunlit brown earth (albedo 0.15 under the sun and the sky), not the model's dark sea
        earth = 0.15 * strength * (math.sin(math.radians(sun_elev_deg)) + 0.12) / math.pi / max(k, 1e-6)
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sz = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Generated'], sz.inputs[0])
        gd = nt.nodes.new('ShaderNodeMapRange')
        nt.links.new(sz.outputs['Z'], gd.inputs['Value'])
        gd.inputs['From Min'].default_value, gd.inputs['From Max'].default_value = -0.03, 0.0
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        nt.links.new(gd.outputs[0], mx.inputs[0])
        mx.inputs[6].default_value = (earth, earth * 0.85, earth * 0.6, 1)
        nt.links.new(st.outputs['Color'], mx.inputs[7])
        nt.links.new(mx.outputs[2], bg.inputs['Color'])
    elif gradient:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sz = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Generated'], sz.inputs[0])
        up = nt.nodes.new('ShaderNodeMapRange')
        nt.links.new(sz.outputs['Z'], up.inputs['Value'])
        up.inputs['From Min'].default_value, up.inputs['From Max'].default_value = 0.0, 0.7
        sk = nt.nodes.new('ShaderNodeMix')
        sk.data_type = 'RGBA'
        nt.links.new(up.outputs[0], sk.inputs[0])
        sk.inputs[6].default_value = (0.78, 0.84, 0.92, 1)       # horizon haze
        sk.inputs[7].default_value = (0.22, 0.38, 0.72, 1)       # zenith
        gd = nt.nodes.new('ShaderNodeMapRange')
        nt.links.new(sz.outputs['Z'], gd.inputs['Value'])
        gd.inputs['From Min'].default_value, gd.inputs['From Max'].default_value = -0.04, 0.02
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        nt.links.new(gd.outputs[0], mx.inputs[0])
        mx.inputs[6].default_value = (0.06, 0.055, 0.04, 1)      # the ground below the horizon
        nt.links.new(sk.outputs[2], mx.inputs[7])
        nt.links.new(mx.outputs[2], bg.inputs['Color'])
    ld = bpy.data.lights.new('test_sun', 'SUN')
    ld.energy = strength
    ld.color = color
    ld.angle = math.radians(angle_deg)
    sun = bpy.data.objects.new('test_sun', ld)
    sc.collection.objects.link(sun)
    el, az = math.radians(sun_elev_deg), math.radians(sun_az_deg)
    to_sun = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    sun.rotation_euler = (-to_sun).to_track_quat('-Z', 'Y').to_euler()
    return sun, to_sun


def ground(size=60.0, tex='leafy_grass', tile=2.0):
    """A ground plane under the flora: the CC0 leafy_grass texture (diffuse, roughness, normal) at 2k, tiled every
    `tile` m. The set comes from the shared texture cache (eidoblend.terrain.find_set: this checkout's,
    $EIDO_TEXTURE_CACHE, $EIDO_ASSET_CACHE, the main checkout's when this one is a git worktree); without it the
    ground is plain soil colour."""
    from eidoblend.terrain import find_set
    bpy.ops.mesh.primitive_plane_add(size=size)
    g = bpy.context.active_object
    g.name = 'test_ground'
    m = bpy.data.materials.new('test_ground')
    nt = m.node_tree
    pr = nt.nodes.get('Principled BSDF')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / tile, 1 / tile, 1)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    try:
        s = find_set(tex, prefer='2k')
    except FileNotFoundError:
        s = {}

    def im(path, color):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(str(path), check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
        nt.links.new(mp.outputs[0], n.inputs['Vector'])
        return n
    if all(k in s for k in ('color', 'roughness', 'normal')):
        nt.links.new(im(s['color'], True).outputs['Color'], pr.inputs['Base Color'])
        nt.links.new(im(s['roughness'], False).outputs['Color'], pr.inputs['Roughness'])
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(im(s['normal'], False).outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs[0], pr.inputs['Normal'])
    else:
        pr.inputs['Base Color'].default_value = (0.08, 0.06, 0.035, 1)
    g.data.materials.append(m)
    return g


def camera(loc, target, lens=35.0, name='test_cam'):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.02
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(path, frame=None):
    sc = bpy.context.scene
    if frame is not None:
        sc.frame_set(frame)
    if '--no-render' in args():                 # build check only (no render: not a GPU job)
        bpy.context.evaluated_depsgraph_get()
        print(f'[flora-test] (no render) {path}', flush=True)
        return
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if not os.path.exists(path):
        raise SystemExit(f'[flora-test] render did not write {path}')
    print(f'[flora-test] wrote {path}', flush=True)
