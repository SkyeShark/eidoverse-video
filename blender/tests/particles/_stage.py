"""The particles tests' stage (tests only): a clean scene, EEVEE at probe settings under AgX, a dark or daylit world, a
camera aimed at a point, a still renderer that checks its file exists, PASS/FAIL bookkeeping and argument parsing."""

import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN = 'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01'
sys.path.insert(0, os.path.join(REPO, 'blender'))
OUT = os.path.join(HERE, 'out')
# out=<folder under out/> (e.g. out=verify) writes a run's stills and files there instead, beside earlier runs
_sub = next((x.split('=', 1)[1] for x in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
             if x.startswith('out=')), None)
if _sub:
    OUT = os.path.join(OUT, _sub)
os.makedirs(OUT, exist_ok=True)
# the shared model library: this worktree has none of its own, the main checkout's is read (never written) here
if not os.environ.get('EIDO_ASSET_CACHE') and not os.path.isdir(os.path.join(REPO, 'eidoverse', 'assets', 'cache')):
    os.environ['EIDO_ASSET_CACHE'] = os.path.join(MAIN, 'eidoverse', 'assets', 'cache')
    os.environ.setdefault('EIDO_NO_FETCH', '1')

RESULTS = []


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default=None):
    a = argv()
    for i, x in enumerate(a):
        if x == name and i + 1 < len(a):
            return a[i + 1]
        if x.startswith(name + '='):
            return x.split('=', 1)[1]
    return default


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    return ok


def summary(tag):
    bad = [n for n, ok in RESULTS if not ok]
    print(f'[{tag}] {len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed' + (f'; FAILED: {bad}' if bad else ''),
          flush=True)
    return not bad


def clean_scene(fps=24, start=1, end=48):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for ng in list(bpy.data.node_groups):
        if ng.users == 0:
            bpy.data.node_groups.remove(ng)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = start, end
    if sc.compositing_node_group is not None:
        sc.compositing_node_group = None
    sc.render.use_compositing = False
    return sc


def probe_render(sc, res=(960, 540), samples=16, look='None'):
    r, ee = sc.render, sc.eevee
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    r.filter_size = 1.5
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN'
    ee.use_shadows = True
    ee.use_fast_gi = True
    r.film_transparent = False
    vs = sc.view_settings
    vs.view_transform = 'AgX'
    vs.look = look if look != 'None' else 'None'
    vs.exposure = 0.0
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    return sc


def world(sc, color=(0.004, 0.005, 0.009), strength=1.0, sky=None):
    """A plain world colour (dark by default: glowing particle work is staged on dark), or sky=(zenith, horizon)
    for a daylit gradient."""
    w = bpy.data.worlds.new('probe_world')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBackground')
    if sky is None:
        bg.inputs['Color'].default_value = (*color, 1.0)
    else:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Generated'], sep.inputs[0])
        mp = nt.nodes.new('ShaderNodeMapRange')
        mp.inputs['From Min'].default_value, mp.inputs['From Max'].default_value = 0.5, 1.0
        nt.links.new(sep.outputs['Z'], mp.inputs['Value'])
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        ins = {s.identifier: s for s in mix.inputs}
        nt.links.new(mp.outputs[0], ins['Factor_Float'])
        ins['A_Color'].default_value = (*sky[1], 1.0)
        ins['B_Color'].default_value = (*sky[0], 1.0)
        outs = {s.identifier: s for s in mix.outputs}
        nt.links.new(outs['Result_Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    return w


def camera(name, loc, target, lens=35.0, sc=None):
    sc = sc or bpy.context.scene
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.05, 200.0
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    aim(cam, loc, target)
    sc.camera = cam
    return cam


def aim(cam, loc, target):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def sun(name, direction, color=(1.0, 0.97, 0.92), strength=3.0, sc=None):
    sc = sc or bpy.context.scene
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = color
    ld.angle = math.radians(2.0)
    ob = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (-Vector(direction)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def floor(size=30.0, color=(0.05, 0.05, 0.055), roughness=0.6, z=0.0, sc=None):
    sc = sc or bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    ob = bpy.context.object
    ob.name = 'floor'
    m = bpy.data.materials.new('floor')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = roughness
    ob.data.materials.append(m)
    return ob


def render_still(path, frame=None, sc=None):
    """Render one still to `path` (PNG) and check it exists (Blender exits 0 even when a render fails)."""
    sc = sc or bpy.context.scene
    if frame is not None:
        sc.frame_set(int(frame))
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    ok = os.path.isfile(path)
    print(f'[render] {os.path.basename(path)} {"ok" if ok else "MISSING"} {time.time() - t:.1f}s', flush=True)
    return ok
