"""The characters family's probe stage (tests only): a clean scene, EEVEE at probe settings, the claude_robot example's own
studio light (eidoverse/examples/claude_robot.js: a key softbox front left, a fill front right, a rim behind, made as an
equirect, no HDRI file; its key and rim lights), uneven ground from a height function with a scanned soil texture from
the shared texture cache, and cameras placed per still. Plain helpers; each test builds its own scene from them."""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def clean_scene(fps=24):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    return sc


def probe_render(sc, res=(960, 540), samples=16):
    r, ee = sc.render, sc.eevee
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    r.filter_size = 1.5
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN'
    o = ee.ray_tracing_options
    o.resolution_scale = '1'
    o.trace_max_roughness = 0.5
    o.use_denoise = True
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    ee.fast_gi_distance = 0.6
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 12
    ee.use_overscan = True
    ee.overscan_size = 3.0
    vs = sc.view_settings
    vs.view_transform = 'AgX'
    vs.look = 'AgX - Base Contrast'
    vs.exposure = 0.0
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.use_motion_blur = False


def studio_world(sc, strength=0.8, background=None):
    """examples/claude_robot.js studioEnvironment(): the same boxes and formula, sampled in Blender's equirect;
    background: a hex colour the camera sees instead (three's scene.background beside its environment)"""
    W, H = 512, 256
    boxes = [((-0.55, 0.55, 0.63), 9.0, 0.3), ((0.75, 0.25, 0.6), 1.6, 0.45), ((0.45, 0.5, -0.75), 5.0, 0.22)]
    boxes = [(np.array(d) / np.linalg.norm(d), k, w) for d, k, w in boxes]
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    phi = (0.5 - u) * 2 * math.pi                      # Blender: u = -atan2(y, x) / 2pi + 0.5
    el = (v - 0.5) * math.pi
    PH, EL = np.meshgrid(phi, el)
    bx, by, bz = np.cos(EL) * np.cos(PH), np.cos(EL) * np.sin(PH), np.sin(EL)
    tx, ty, tz = bx, bz, -by                           # Blender -> three
    val = 0.05 + 0.08 * np.maximum(0, ty)
    for d, k, w in boxes:
        val = val + k * np.exp((tx * d[0] + ty * d[1] + tz * d[2] - 1) / (w * w))
    img = bpy.data.images.new('studio_env', W, H, float_buffer=True)
    px = np.ones((H, W, 4), dtype=np.float32)
    px[..., 0] = px[..., 1] = px[..., 2] = val
    img.pixels.foreach_set(px.ravel())
    img.pack()
    wd = bpy.data.worlds.new('studio')
    sc.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new('ShaderNodeTexEnvironment')
    tex.image = img
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(tex.outputs['Color'], bg.inputs['Color'])
    if background is None:
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    else:
        c = ((background >> 16) & 255, (background >> 8) & 255, background & 255)
        flat = nt.nodes.new('ShaderNodeBackground')
        flat.inputs['Color'].default_value = tuple((ch / 255.0) ** 2.2 for ch in c) + (1.0,)
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs['Background'], mix.inputs[1])
        nt.links.new(flat.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return wd


def floor_disc(radius=6.0, colour=0x2a2a2e, roughness=0.7, name='floor'):
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius, fill_type='NGON', location=(0, 0, 0))
    ob = bpy.context.object
    ob.name = name
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    c = ((colour >> 16) & 255, (colour >> 8) & 255, colour & 255)
    b.inputs['Base Color'].default_value = tuple((ch / 255.0) ** 2.2 for ch in c) + (1.0,)
    b.inputs['Roughness'].default_value = roughness
    ob.data.materials.append(mat)
    return ob


def sun(name, pos_three, colour_hex, strength, angle_deg=2.0, target=(0.0, 0.0, 0.0)):
    """a three.js DirectionalLight at pos (three axes) shining at target, as a Blender sun"""
    x, y, z = pos_three
    p = Vector((x, -z, y))
    c = ((colour_hex >> 16) & 255, (colour_hex >> 8) & 255, colour_hex & 255)
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = tuple((ch / 255.0) ** 2.2 for ch in c)
    ld.angle = angle_deg * math.pi / 180
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    d = (Vector(target) - p).normalized()
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(d)
    return ob


TEX = None


def texture_set(name):
    """a CC0 set from the shared texture cache, the first root that has it (eidoblend.terrain.texture_roots: this
    checkout's, EIDO_TEXTURE_CACHE, EIDO_ASSET_CACHE, the main checkout's when this one is a git worktree):
    {role: path}"""
    from eidoblend.terrain import texture_roots
    for r in texture_roots():
        d = os.path.join(r, name)
        if os.path.isdir(d):
            fs = os.listdir(d)
            pick = lambda suf: next((os.path.join(d, f) for f in fs if f.endswith(suf)), None)  # noqa: E731
            return {'color': pick('_Color.jpg'), 'normal': pick('_NormalGL.jpg'), 'rough': pick('_Roughness.jpg'),
                    'ao': pick('_AmbientOcclusion.jpg')}
    return None


def ground_mesh(fn, x0, x1, y0, y1, step=0.02, tex='Ground106_2k', tile=1.6, name='ground'):
    nx, ny = int(round((x1 - x0) / step)) + 1, int(round((y1 - y0) / step)) + 1
    xs, ys = np.linspace(x0, x1, nx), np.linspace(y0, y1, ny)
    X, Y = np.meshgrid(xs, ys)
    Z = fn(X, Y)
    verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    quads = np.stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()], axis=1)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    me.loops.add(len(quads) * 4)
    me.loops.foreach_set('vertex_index', quads.astype(np.int32).ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', (np.arange(len(quads)) * 4).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(quads), 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    me.polygons.foreach_set('use_smooth', np.ones(len(quads), dtype=bool))
    uv = me.uv_layers.new(name='UVMap')
    lv = verts[quads.ravel()]
    uv.data.foreach_set('uv', (lv[:, :2] / tile).astype(np.float32).ravel())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(name + '_soil')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ts = texture_set(tex)
    if ts:
        def img(role, colour):
            if not ts.get(role):
                return None
            n = nt.nodes.new('ShaderNodeTexImage')
            n.image = bpy.data.images.load(ts[role], check_existing=True)
            n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
            return n
        c, r, nrm, ao = img('color', True), img('rough', False), img('normal', False), img('ao', False)
        if c and ao:
            mul = nt.nodes.new('ShaderNodeMix')
            mul.data_type = 'RGBA'
            mul.blend_type = 'MULTIPLY'
            mul.inputs['Factor'].default_value = 0.6
            nt.links.new(c.outputs['Color'], mul.inputs['A'])
            nt.links.new(ao.outputs['Color'], mul.inputs['B'])
            nt.links.new(mul.outputs['Result'], bsdf.inputs['Base Color'])
        elif c:
            nt.links.new(c.outputs['Color'], bsdf.inputs['Base Color'])
        if r:
            nt.links.new(r.outputs['Color'], bsdf.inputs['Roughness'])
        if nrm:
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value = 1.0
            nt.links.new(nrm.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.12, 0.09, 0.07, 1)
        bsdf.inputs['Roughness'].default_value = 0.9
    me.materials.append(mat)
    return ob


def camera(name='cam', lens=50.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.05, 200.0
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def aim(cam, pos, target, roll=0.0):
    cam.location = Vector(pos)
    d = Vector(target) - Vector(pos)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')


def still(sc, cam, frame, path):
    sc.camera = cam
    sc.frame_set(frame)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return os.path.exists(path)


def bone_world(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].head
