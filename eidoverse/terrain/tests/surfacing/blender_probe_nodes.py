"""Blender's shader nodes the material port transcribes, rendered by EEVEE as the oracle (PORT_PLAN.md 8.2 row P17):
what EEVEE's Image Texture node reads with Cubic interpolation, the White Noise Texture's colour (hex tiling's
offsets and turns) and the Voronoi texture's F1 distance and colour (the canopy's crowns), each as an unlit emission
seen top-down, one sample, no film filter, into a 32-bit EXR.

    bash run_blender.sh eidoverse/terrain/tests/surfacing/blender_probe_nodes.py -- <out dir>
    (a GPU job: behind the machine's GPU queue on a shared machine)

Writes <out dir>/probe_nodes.json (the cases and their inputs) and <out dir>/<case>.npy (each render, (H, W, 4)
float32, row 0 the bottom: Blender's pixel order) beside the probe's input image.
"""
import json
import os
import sys

import bpy
import numpy as np

_ARGS = [a for a in sys.argv[sys.argv.index('--') + 1:] if a != '--'] if '--' in sys.argv else []
OUT = os.path.abspath(_ARGS[0]) if _ARGS else os.path.join(os.getcwd(), 'probe_nodes')
os.makedirs(OUT, exist_ok=True)


def scene(n):
    sc = bpy.context.scene
    for o in list(bpy.data.objects):                  # the startup file's cube, light and camera too
        bpy.data.objects.remove(o, do_unlink=True)
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE'
    sc.render.resolution_x = sc.render.resolution_y = n
    sc.render.resolution_percentage = 100
    sc.world = bpy.data.worlds.new('black')
    sc.world.color = (0.0, 0.0, 0.0)
    sc.render.film_transparent = True
    vs = sc.view_settings
    vs.view_transform = 'Standard'
    vs.look = 'None'
    vs.exposure = 0.0
    vs.gamma = 1.0
    sc.eevee.taa_render_samples = 1
    try:
        sc.render.filter_size = 0.0
    except (AttributeError, TypeError):
        pass
    sc.render.use_compositing = False
    im = sc.render.image_settings
    im.file_format = 'OPEN_EXR'
    im.color_depth = '32'
    im.color_mode = 'RGBA'
    return sc


def plane(side, mat):
    """A plane `side` metres across, its corner at the origin (object coordinates 0..side)."""
    me = bpy.data.meshes.new('probe_plane')
    me.from_pydata([(0, 0, 0), (side, 0, 0), (side, side, 0), (0, side, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new('probe_plane', me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def camera(side):
    cam = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = side
    cam.data.clip_start, cam.data.clip_end = 0.1, 100.0
    cam.location = (side / 2, side / 2, 10.0)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.scene.camera = cam
    return cam


def emission_material(name, build):
    """build(nt, coords) -> a colour socket."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    col = build(nt, tc.outputs['Object'])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(col, em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def render(name):
    path = os.path.join(OUT, name + '.exr')
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    a = px.reshape(h, w, 4)
    np.save(os.path.join(OUT, name + '.npy'), a)
    os.remove(path)
    return a


cases = {}

# 1. Cubic: a 16 x 16 float image (32-bit on the GPU), EXTEND, read over a 16 m plane at 4 pixels a texel
N_IMG, PX = 16, 4
rng = np.random.default_rng(5)
vals = rng.random((N_IMG, N_IMG, 4)).astype(np.float32)
vals[..., 3] = 1.0
np.save(os.path.join(OUT, 'cubic_image.npy'), vals)
img = bpy.data.images.new('probe_cubic', N_IMG, N_IMG, alpha=True, float_buffer=True)
img.colorspace_settings.name = 'Non-Color'
img.use_half_precision = False
img.pixels.foreach_set(vals.ravel())
img.update()
for interp in ('Cubic', 'Linear', 'Closest'):
    def build(nt, co, interp=interp):
        m = nt.nodes.new('ShaderNodeVectorMath')
        m.operation = 'SCALE'
        nt.links.new(co, m.inputs[0])
        m.inputs[3].default_value = 1.0 / N_IMG
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = img
        tx.interpolation = interp
        tx.extension = 'EXTEND'
        nt.links.new(m.outputs[0], tx.inputs['Vector'])
        return tx.outputs['Color']
    sc = scene(N_IMG * PX)
    plane(float(N_IMG), emission_material('probe_' + interp, build))
    camera(float(N_IMG))
    render(f'image_{interp.lower()}')
    cases[f'image_{interp.lower()}'] = dict(image='cubic_image.npy', side_m=N_IMG, px=N_IMG * PX)

# 2. White Noise (3D) Color at integer lattice points (x, y, 7.1): a pixel a unit over 64 units
NW = 64


def build_white(nt, co):
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(co, sep.inputs[0])
    fx = nt.nodes.new('ShaderNodeMath')
    fx.operation = 'FLOOR'
    nt.links.new(sep.outputs[0], fx.inputs[0])
    fy = nt.nodes.new('ShaderNodeMath')
    fy.operation = 'FLOOR'
    nt.links.new(sep.outputs[1], fy.inputs[0])
    cb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(fx.outputs[0], cb.inputs[0])
    nt.links.new(fy.outputs[0], cb.inputs[1])
    cb.inputs[2].default_value = 7.1
    wn = nt.nodes.new('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '3D'
    nt.links.new(cb.outputs[0], wn.inputs['Vector'])
    return wn.outputs['Color']


sc = scene(NW)
plane(float(NW), emission_material('probe_white', build_white))
camera(float(NW))
render('white_noise')
cases['white_noise'] = dict(side_m=NW, px=NW, z=7.1)

# 3. Voronoi F1 (3D, Euclidean, randomness 0.85, scale 1 / 4.5) at (x, y, 3.3) + an offset: distance and colour
NV = 128


def build_voronoi(nt, co, out):
    ad = nt.nodes.new('ShaderNodeVectorMath')
    ad.operation = 'ADD'
    nt.links.new(co, ad.inputs[0])
    ad.inputs[1].default_value = (13.7, -29.1, 3.3)
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    vo.voronoi_dimensions = '3D'
    vo.feature = 'F1'
    nt.links.new(ad.outputs[0], vo.inputs['Vector'])
    vo.inputs['Scale'].default_value = 1.0 / 4.5
    vo.inputs['Randomness'].default_value = 0.85
    if out == 'Distance':
        cb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(vo.outputs['Distance'], cb.inputs[0])
        nt.links.new(vo.outputs['Distance'], cb.inputs[1])
        nt.links.new(vo.outputs['Distance'], cb.inputs[2])
        return cb.outputs[0]
    return vo.outputs['Color']


for out in ('Distance', 'Color'):
    sc = scene(NV)
    plane(64.0, emission_material('probe_voronoi_' + out, lambda nt, co, out=out: build_voronoi(nt, co, out)))
    camera(64.0)
    render(f'voronoi_{out.lower()}')
    cases[f'voronoi_{out.lower()}'] = dict(side_m=64.0, px=NV, offset=[13.7, -29.1, 3.3], scale=1.0 / 4.5, randomness=0.85)

with open(os.path.join(OUT, 'probe_nodes.json'), 'w') as f:
    json.dump(dict(blender=bpy.app.version_string, cases=cases), f, indent=1)
print(f'[probe_nodes] wrote {len(cases)} cases to {OUT}')
