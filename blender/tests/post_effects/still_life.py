"""tests/post_effects/still_life.py: the scene the post-effects tests photograph, and the plumbing that renders it once
and composites each effect over the saved frame. Test dressing, not ports.

The still life: a checker floor 40 m wide, a glossy red sphere, a blue torus, a yellow cone, a white Suzanne, a green
cube, a hot emissive lamp (the flares' highlight: about 40x white), a row of grey pillars receding to 30 m (depth for
the fogs), a sun with shadows, and a sky whose colour is a LINKED gradient (so retro_wireframe's background must
replace a linked world). The camera is look.camera.make_camera's (sensor fit AUTO, 36 mm, a 45 degree vertical fov):
the fit the underwater pass's ray rebuild must read right. The source is rendered once (EEVEE) to EXR: Combined,
Depth, Normal (look/post/chain.save_frames_passes); a second source renders it on a transparent film (the sky alpha
0) for chromatic_aberration_alpha. Every effect then runs over the saved frames in a scene with nothing to draw, its
camera the source camera (blueprint, cross_hatch, full_toon and underwater read it).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(HERE, 'out')
SRC = os.path.join(OUT, 'src')
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
RES = (960, 540)
FPS = 24


def args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def _mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    if emit is not None:
        b.inputs['Emission Color'].default_value = (*emit, 1.0)
        b.inputs['Emission Strength'].default_value = strength
    return m


def _checker(name, a, b, scale):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ck = nt.nodes.new('ShaderNodeTexChecker')
    ck.inputs['Color1'].default_value = (*a, 1.0)
    ck.inputs['Color2'].default_value = (*b, 1.0)
    ck.inputs['Scale'].default_value = scale
    nt.links.new(ck.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.6
    return m


def _add(ob, scene, mat, loc, rot=(0.0, 0.0, 0.0), smooth=True):
    scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    ob.data.materials.append(mat)
    if smooth and hasattr(ob.data, 'polygons'):
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def _mesh(name, op, **kw):
    """A primitive through bmesh (no operator context needed)."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    getattr(bmesh.ops, op)(bm, **kw)
    bm.to_mesh(me)
    bm.free()
    return bpy.data.objects.new(name, me)


def _torus(name, major=0.55, minor=0.18, seg=48, ring=20):
    me = bpy.data.meshes.new(name)
    vs, fs = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(ring):
            b = 2 * math.pi * j / ring
            r = major + minor * math.cos(b)
            vs.append((r * math.cos(a), r * math.sin(a), minor * math.sin(b)))
    for i in range(seg):
        for j in range(ring):
            i2, j2 = (i + 1) % seg, (j + 1) % ring
            fs.append((i * ring + j, i2 * ring + j, i2 * ring + j2, i * ring + j2))
    me.from_pydata(vs, [], fs)
    return bpy.data.objects.new(name, me)


def _suzanne(name):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_monkey(bm)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    mod = ob.modifiers.new('subd', 'SUBSURF')
    mod.levels = mod.render_levels = 2
    return ob


def build(transparent=False):
    """The still life in a fresh file. Returns the scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    sc.frame_start, sc.frame_end = 1, 48
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    floor = _mesh('floor', 'create_grid', x_segments=1, y_segments=1, size=20.0)
    _add(floor, sc, _checker('floor', (0.55, 0.42, 0.30), (0.12, 0.10, 0.09), 24.0), (0.0, 0.0, 0.0), smooth=False)
    _add(_mesh('sphere', 'create_uvsphere', u_segments=48, v_segments=24, radius=0.6), sc,
         _mat('red', (0.8, 0.05, 0.04), rough=0.15, coat=0.6), (-1.6, 0.4, 0.6))
    _add(_torus('torus'), sc, _mat('blue', (0.05, 0.15, 0.75), rough=0.45), (-0.35, 2.0, 0.72),
         rot=(math.radians(75), 0, math.radians(20)))
    _add(_mesh('cone', 'create_cone', cap_ends=True, segments=32, radius1=0.45, radius2=0.0, depth=1.1), sc,
         _mat('yellow', (0.85, 0.65, 0.05), rough=0.4), (1.45, -0.45, 0.55))
    suz = _add(_suzanne('suzanne'), sc, _mat('white', (0.7, 0.7, 0.68), rough=0.35), (0.4, 0.15, 0.5),
               rot=(math.radians(-10), 0, math.radians(20)))
    suz.scale = (0.7, 0.7, 0.7)
    _add(_mesh('cube', 'create_cube', size=0.8), sc, _mat('green', (0.08, 0.55, 0.12), rough=0.5),
         (2.4, 1.6, 0.4), rot=(0, 0, math.radians(30)), smooth=False)
    lamp = _add(_mesh('lamp', 'create_uvsphere', u_segments=24, v_segments=12, radius=0.1), sc,
                _mat('lamp', (1.0, 0.9, 0.7), emit=(1.0, 0.85, 0.6), strength=60.0), (-0.85, 2.6, 1.9))
    lamp['test_lamp'] = True
    grey = _mat('pillar', (0.5, 0.5, 0.52), rough=0.7)
    for k, y in enumerate((5.0, 9.0, 14.0, 20.0, 28.0)):
        _add(_mesh(f'pillar{k}', 'create_cube', size=1.0), sc, grey, (-3.2 + 1.4 * k, y, 1.5), smooth=False).scale = (
            0.5, 0.5, 3.0)
    # the sun 40 degrees up from the front left (a three-quarter light: lit fronts, a shadow side, shadows falling back
    # and right), soft
    ld = bpy.data.lights.new('sun', 'SUN')
    ld.energy, ld.angle, ld.color = 3.5, math.radians(2.0), (1.0, 0.95, 0.88)
    sun = bpy.data.objects.new('sun', ld)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(-65))
    # a sky gradient LINKED into the world's colour (zenith blue to a pale horizon)
    w = bpy.data.worlds.new('still_life_sky')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.0, 0.6
    ramp.color_ramp.elements[0].color = (0.62, 0.70, 0.82, 1.0)
    ramp.color_ramp.elements[1].color = (0.10, 0.25, 0.65, 1.0)
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    # the camera: look.camera's (AUTO fit), 45 degrees vertical
    from eidoblend.look import camera as C
    cam = C.make_camera('still_cam', fov=45.0, fov_axis='vertical', clip=(0.1, 200.0), scene=sc)
    pos, aim = Vector((0.4, -6.4, 1.55)), Vector((0.1, 1.2, 0.75))
    cam.location = pos
    cam.rotation_quaternion = (aim - pos).to_track_quat('-Z', 'Y')
    sc.camera = cam
    from eidoblend.look import render_settings as RS
    RS.apply_auto_enhance(sc, 'probe', resolution=RES, samples=16, exposure=0.0, motion_blur=False)
    sc.render.film_transparent = bool(transparent)
    sc.render.use_compositing = True
    return sc


def camera_meta(sc):
    cam = sc.camera
    d = cam.data
    return {'matrix': [list(r) for r in cam.matrix_world], 'lens': d.lens, 'sensor_width': d.sensor_width,
            'sensor_height': d.sensor_height, 'sensor_fit': d.sensor_fit, 'clip_start': d.clip_start,
            'clip_end': d.clip_end, 'res': list(RES), 'fps': FPS,
            'view': [sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure]}


def render_sources(name, transparent=False):
    """Render the still life's frame 1 to EXR (Combined, Depth, Normal) + a plain PNG; meta.json beside them."""
    from eidoblend.look.post import chain
    sc = build(transparent)
    d = os.path.join(SRC, name)
    os.makedirs(d, exist_ok=True)
    pats = chain.save_frames_passes(sc, d, ('Depth', 'Normal'), name='src')
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.frame_set(1)
    sc.render.filepath = os.path.join(d, 'src_plain_0001.png')
    bpy.ops.render.render(write_still=True)
    paths = {p: os.path.join(d, pat.replace('####', '0001')) for p, pat in pats.items()}
    for p, path in paths.items():
        if not os.path.exists(path):
            raise RuntimeError(f'render_sources: {p} was not written ({path})')
    meta = camera_meta(sc)
    meta['paths'] = paths
    meta['plain'] = sc.render.filepath
    meta['lamp'] = list(next(o for o in sc.objects if o.get('test_lamp')).matrix_world.translation)
    with open(os.path.join(d, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, 'still_life.blend'))
    return meta


def meta(name):
    with open(os.path.join(SRC, name, 'meta.json')) as f:
        return json.load(f)


def post_scene(m, name='post', frames=(1, 400)):
    """A scene with nothing to draw but a camera (the source's: matrix, lens, sensor, fit, clip), its compositor
    reading the saved frame: every effect runs over it as over a render. hold(sc, f) keeps frame 1 under any frame."""
    from eidoblend.look.post import chain
    sc = bpy.data.scenes.new(name)
    if bpy.context.window:
        bpy.context.window.scene = sc
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 1
    sc.render.fps, sc.render.fps_base = m['fps'], 1.0
    sc.frame_start, sc.frame_end = frames
    sc.render.resolution_x, sc.render.resolution_y = m['res']
    sc.render.resolution_percentage = 100
    sc.render.use_motion_blur = False
    cd = bpy.data.cameras.new(name + '_cam')
    cd.lens, cd.sensor_width, cd.sensor_height, cd.sensor_fit = m['lens'], m['sensor_width'], m['sensor_height'], \
        m['sensor_fit']
    cd.clip_start, cd.clip_end = m['clip_start'], m['clip_end']
    cam = bpy.data.objects.new(name + '_cam', cd)
    sc.collection.objects.link(cam)
    cam.matrix_world = Matrix(m['matrix'])
    sc.camera = cam
    sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure = m['view']
    chain.tree(sc)
    chain.use_saved_frames(sc, m['paths']['Combined'], frame_start=1,
                           passes={k: v for k, v in m['paths'].items() if k != 'Combined'})
    return sc


def hold(sc, frame):
    """Every source node reads the saved frame 1 at `frame` (Image frame_offset), so Scene Time moves on a still."""
    t = sc.compositing_node_group
    for n in t.nodes:
        if n.bl_idname == 'CompositorNodeImage' and n.name.startswith('look:render'):
            n.frame_offset = 1 - int(frame)


def render_png(sc, path, frame):
    hold(sc, frame)
    sc.frame_set(frame)
    s = sc.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.color_mode = 'IMAGE', 'PNG', '8', 'RGB'
    sc.render.filepath = path
    with bpy.context.temp_override(scene=sc):
        bpy.ops.render.render(write_still=True, scene=sc.name)
    if not os.path.exists(path):
        raise RuntimeError(f'render_png: {path} was not written')
    return path


def render_exr(sc, frame, tmp=None):
    """The post's output in scene-linear light (before the view transform), top-down (H, W, 4)."""
    import numpy as np
    hold(sc, frame)
    sc.frame_set(frame)
    with bpy.context.temp_override(scene=sc):
        bpy.ops.render.render(write_still=False, scene=sc.name)
    p = tmp or os.path.join(OUT, '_tmp.exr')
    s = sc.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.exr_codec, s.color_mode = 'IMAGE', 'OPEN_EXR', '32', 'ZIP', 'RGBA'
    bpy.data.images['Render Result'].save_render(p, scene=sc)
    return load_exr(p)


def load_exr(path):
    import numpy as np
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1].copy()
    bpy.data.images.remove(im)
    return a


def source_arrays(m):
    """(Combined RGBA, Depth (H, W), Normal (H, W, 3)) of the saved frame, top-down."""
    c = load_exr(m['paths']['Combined'])
    dep = load_exr(m['paths']['Depth'])[..., 0]
    nrm = load_exr(m['paths']['Normal'])[..., :3]
    return c, dep, nrm


class Checks:
    def __init__(self, tag):
        self.tag, self.fail, self.report = tag, [], {}

    def __call__(self, ok, what):
        print(f"[{self.tag}] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
        if not ok:
            self.fail.append(what)
        return ok

    def save(self, name):
        self.report['fail'] = self.fail
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f'report_{name}.json'), 'w') as f:
            json.dump(self.report, f, indent=1, default=str)
        print(f"[{self.tag}] {'FAIL ' + str(len(self.fail)) if self.fail else 'PASS'}", flush=True)
