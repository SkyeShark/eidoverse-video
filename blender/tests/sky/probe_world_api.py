"""Probe the EEVEE world facts the sky port relies on (tiny renders, seconds):

  P1  Light Path 'Is Camera Ray' in a world: camera rays see one colour, lighting sees another
  P2  which Texture Coordinate output is the world-space view direction in a world shader
  P4  an Environment Texture image SEQUENCE: does world lighting follow the frame?
  P5  can world LIGHTING tell diffuse from glossy (Is Diffuse Ray / Is Glossy Ray)? A rough white sphere
      and a chrome sphere under a world that is green for diffuse rays and red for glossy rays.
      (A fact, not a pass/fail: it decides where the weather's hemiDim can act.)
  P6  which file a sequence shows OUTSIDE its range and at sub-frames, with world_nodes' own image
      user (sequence starting at frame 5): frame 4, 4.75 (a motion-blur sample), 5, 5.75, 6, 7

Run: bash run_blender.sh blender/tests/sky/probe_world_api.py   (prints PASS/FAIL lines)
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out', 'probe_world_api')
os.makedirs(OUT, exist_ok=True)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 64, 36
    sc.render.resolution_percentage = 100
    sc.eevee.taa_render_samples = 4
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    cam_data = bpy.data.cameras.new('cam')
    cam = bpy.data.objects.new('cam', cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0, -6, 0)
    cam.rotation_euler = (1.5707963, 0, 0)          # looks along +Y
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.sun_threshold = 0.0
    return sc, cam, w


def add_sphere(sc, x=0.0):
    me = bpy.data.meshes.new('s')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    bm.to_mesh(me)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('s', me)
    ob.location = (x, 0, 0)
    sc.collection.objects.link(ob)
    mat = bpy.data.materials.new('white')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
    bsdf.inputs['Roughness'].default_value = 1.0
    me.materials.append(mat)
    return ob


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    import OpenImageIO as oiio
    buf = oiio.ImageBuf(path)
    return np.asarray(buf.get_pixels(oiio.FLOAT))[::-1]   # row 0 = bottom


def world_nodes(w):
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return nt, bg


results = []

# ---- P1: Is Camera Ray ----
sc, cam, w = reset_scene()
add_sphere(sc)
nt, bg = world_nodes(w)
lp = nt.nodes.new('ShaderNodeLightPath')
mix = nt.nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
mix.inputs['A'].default_value = (1, 0, 0, 1)     # lighting: red
mix.inputs['B'].default_value = (0, 0, 1, 1)     # camera: blue
nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Factor'])
nt.links.new(mix.outputs['Result'], bg.inputs['Color'])
img = render(os.path.join(OUT, 'p1.exr'))
corner = img[2, 2, :3]
centre = img[18, 32, :3]
print('P1 corner (background)', corner.round(3), 'centre (sphere)', centre.round(3))
ok = corner[2] > 0.5 and corner[0] < 0.1 and centre[0] > 0.1 and centre[0] > 3 * centre[2]
results.append(('P1 Is Camera Ray in world: camera sees B, lighting sees A', ok))

# ---- P2: direction coordinate ----
for output in ('Generated', 'Object', 'Normal', 'Reflection', 'Camera', 'Window'):
    sc, cam, w = reset_scene()
    nt, bg = world_nodes(w)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs[output], bg.inputs['Color'])
    img = render(os.path.join(OUT, 'p2_%s.exr' % output))
    c = img[18, 32, :3]
    r = img[18, 60, :3]
    t = img[33, 32, :3]
    print('P2 %-10s centre %s right %s top %s' % (output, c.round(3), r.round(3), t.round(3)))
    if output == 'Generated':
        # camera looks +Y: centre should be ~(0, 1, 0), right edge +X, top +Z
        ok = abs(c[1] - 1) < 0.05 and abs(c[0]) < 0.05 and r[0] > 0.2 and t[2] > 0.1
        results.append(('P2 Generated = world view direction', ok))

# ---- P4: image sequence drives world lighting per frame ----
import OpenImageIO as oiio
seq_dir = os.path.join(OUT, 'seq')
os.makedirs(seq_dir, exist_ok=True)
for f, col in ((1, (1.0, 0.0, 0.0)), (2, (0.0, 1.0, 0.0))):
    arr = np.zeros((16, 32, 3), np.float32)
    arr[:] = col
    spec = oiio.ImageSpec(32, 16, 3, 'half')
    o = oiio.ImageOutput.create(os.path.join(seq_dir, 'env_%04d.exr' % f))
    o.open(os.path.join(seq_dir, 'env_%04d.exr' % f), spec)
    o.write_image(arr)
    o.close()
sc, cam, w = reset_scene()
add_sphere(sc)
nt, bg = world_nodes(w)
env = nt.nodes.new('ShaderNodeTexEnvironment')
im = bpy.data.images.load(os.path.join(seq_dir, 'env_0001.exr'))
im.source = 'SEQUENCE'
env.image = im
env.image_user.frame_duration = 2
env.image_user.frame_start = 1
env.image_user.use_auto_refresh = True
nt.links.new(env.outputs['Color'], bg.inputs['Color'])
lp = nt.nodes.new('ShaderNodeLightPath')
mix = nt.nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Factor'])
nt.links.new(env.outputs['Color'], mix.inputs['A'])
mix.inputs['B'].default_value = (0, 0, 0, 1)
nt.links.new(mix.outputs['Result'], bg.inputs['Color'])
sc.frame_start, sc.frame_end = 1, 2
cols = []
for f in (1, 2):
    sc.frame_set(f)
    img = render(os.path.join(OUT, 'p4_f%d.exr' % f))
    cols.append(img[18, 32, :3])
    print('P4 frame', f, 'sphere', img[18, 32, :3].round(3))
ok = cols[0][0] > 3 * cols[0][1] and cols[1][1] > 3 * cols[1][0]
results.append(('P4 world lighting follows an image sequence per frame', ok))

# ---- P5: diffuse vs glossy world lighting ----
sc, cam, w = reset_scene()
sc.render.resolution_x, sc.render.resolution_y = 128, 72
cam.location = (0, -7, 0)
rough = add_sphere(sc, -1.3)
chrome = add_sphere(sc, 1.3)
cm = bpy.data.materials.new('chrome')
cm.use_nodes = True
cb = cm.node_tree.nodes['Principled BSDF']
cb.inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1)
cb.inputs['Metallic'].default_value = 1.0
cb.inputs['Roughness'].default_value = 0.02
chrome.data.materials[0] = cm
nt, bg = world_nodes(w)
lp = nt.nodes.new('ShaderNodeLightPath')
m_diff = nt.nodes.new('ShaderNodeMix')
m_diff.data_type = 'RGBA'
m_diff.inputs['A'].default_value = (1, 1, 1, 1)          # neither flag: white
m_diff.inputs['B'].default_value = (0, 1, 0, 1)          # Is Diffuse Ray: green
nt.links.new(lp.outputs['Is Diffuse Ray'], m_diff.inputs['Factor'])
m_glos = nt.nodes.new('ShaderNodeMix')
m_glos.data_type = 'RGBA'
m_glos.inputs['B'].default_value = (1, 0, 0, 1)          # Is Glossy Ray: red
nt.links.new(m_diff.outputs['Result'], m_glos.inputs['A'])
nt.links.new(lp.outputs['Is Glossy Ray'], m_glos.inputs['Factor'])
m_cam = nt.nodes.new('ShaderNodeMix')
m_cam.data_type = 'RGBA'
m_cam.inputs['B'].default_value = (0, 0, 1, 1)           # Is Camera Ray: blue
nt.links.new(m_glos.outputs['Result'], m_cam.inputs['A'])
nt.links.new(lp.outputs['Is Camera Ray'], m_cam.inputs['Factor'])
nt.links.new(m_cam.outputs['Result'], bg.inputs['Color'])
img = render(os.path.join(OUT, 'p5.exr'))
d_px, g_px = img[36, 64 - 33, :3], img[36, 64 + 33, :3]       # sphere centres (lens 50, 7 m away)
name = lambda c: ('red(glossy)' if c[0] > 2 * c[1] and c[0] > 2 * c[2] else 'green(diffuse)'
                  if c[1] > 2 * c[0] and c[1] > 2 * c[2] else 'white(neither)' if min(c) > 0.3 * max(c) else 'mixed')
print('P5 rough sphere', d_px.round(3), name(d_px), '| chrome sphere', g_px.round(3), name(g_px))
separable = name(d_px) != name(g_px)
print('FACT P5 world lighting %s diffuse from glossy rays' % ('SEPARATES' if separable else 'does NOT separate'))

# ---- P6: a sequence outside its range, and at sub-frames (world_nodes' image user) ----
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky.world_nodes import _seq_image, _set_user  # noqa: E402
seq6 = os.path.join(OUT, 'seq6')
os.makedirs(seq6, exist_ok=True)
for f, col in ((5, (1.0, 0.0, 0.0)), (6, (0.0, 1.0, 0.0))):
    arr = np.zeros((16, 32, 3), np.float32)
    arr[:] = col
    p = os.path.join(seq6, 'env_%04d.exr' % f)
    o = oiio.ImageOutput.create(p)
    o.open(p, oiio.ImageSpec(32, 16, 3, 'half'))
    o.write_image(arr)
    o.close()
sc, cam, w = reset_scene()
nt, bg = world_nodes(w)
env = nt.nodes.new('ShaderNodeTexEnvironment')
env.image = _seq_image(os.path.join(seq6, 'env_0005.exr'), 5, 2, 'p6_seq')
_set_user(env, 5, 2)
nt.links.new(env.outputs['Color'], bg.inputs['Color'])
sc.frame_start, sc.frame_end = 5, 6
seen = {}
for f, sub in ((4, 0.0), (4, 0.75), (5, 0.0), (5, 0.75), (6, 0.0), (7, 0.0)):
    sc.frame_set(f, subframe=sub)
    c = render(os.path.join(OUT, 'p6_%d_%02d.exr' % (f, int(sub * 100))))[18, 32, :3]
    seen[f + sub] = ('red=5' if c[0] > 0.5 and c[1] < 0.2 and c[2] < 0.2 else 'green=6' if c[1] > 0.5 and c[0] < 0.2
                     else 'MISSING(%s)' % c.round(2))
    print('P6 frame %.2f shows %s' % (f + sub, seen[f + sub]))
results.append(('P6 a sub-frame shows the integer frame (5.75 -> 5)', seen[5.75] == 'red=5'))

for name, ok in results:
    print(('PASS ' if ok else 'FAIL ') + name)
sys.stdout.flush()
