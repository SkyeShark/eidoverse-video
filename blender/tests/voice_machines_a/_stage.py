"""Shared staging for the voice-machines-a probes (c64, dectalk, desktop2001, mac1984): an EEVEE scene, an oak desk
at 0.74 m against a plaster wall, a warm key light with a cool fill, a camera, stills, PASS / FAIL lines.

Imported by the test scripts beside it (run through run_blender.sh; renders through the shared GPU slot). Probe
renders stay small: 960 x 540 at most, 16 EEVEE samples or fewer.
"""
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
ASSETS = WORKTREE / 'eidoverse' / 'assets'
if str(WORKTREE / 'blender') not in sys.path:
    sys.path.insert(0, str(WORKTREE / 'blender'))

DESK_Z = 0.74                     # a desk top's height (m)
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(f'{"PASS" if ok else "FAIL"} {name}' + (f'  ({detail})' if detail else ''), flush=True)
    return ok


def summary(tag):
    n_fail = sum(1 for _, ok in RESULTS if not ok)
    print(f'[{tag}] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
    return n_fail


def args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def main_checkout():
    git = WORKTREE / '.git'
    if git.is_file():                       # a worktree: "gitdir: <main>/.git/worktrees/<name>"
        line = git.read_text().strip()
        if line.startswith('gitdir:'):
            return Path(line.split(':', 1)[1].strip()).parents[2]
    return WORKTREE


def cached(kind, name):
    """A fetched CC0 set from the shared cache (this worktree's, else the main checkout's), or None."""
    for root in (WORKTREE, main_checkout()):
        p = root / 'eidoverse' / 'assets' / 'cache' / kind / name
        if p.exists():
            return p
    return None


def fresh_scene(res=(960, 540), samples=16, fps=24, frames=(1, 48)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    r = sc.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps, r.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    e = sc.eevee
    e.taa_render_samples = samples
    e.use_raytracing = True
    e.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.new('world')
    sc.world = w
    if w.node_tree is None:
        w.use_nodes = True
    bg = w.node_tree.nodes.get('Background') or w.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.020, 0.021, 0.024, 1)
    bg.inputs['Strength'].default_value = 1.0
    return sc


def look_at(obj, target):
    d = (Vector(target) - obj.location).normalized()
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(sc, loc, target, lens=50.0, name='cam'):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    c = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(c)
    c.location = loc
    look_at(c, target)
    sc.camera = c
    return c


def area_light(sc, loc, target, power, size=0.5, color=(1, 1, 1), name='key'):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.color = color
    ld.size = size
    ld.use_custom_distance = True
    ld.cutoff_distance = 40.0
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    o.location = loc
    look_at(o, target)
    return o


def _mat(name):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    return m


def pbr_material(name, set_dir, scale=1.0, fallback=(0.3, 0.22, 0.15), tint=None):
    """A Principled material from an AmbientCG set (Color, Roughness, NormalGL) on the UVs, or a plain colour."""
    m = _mat(name)
    t = m.node_tree
    b = t.nodes.get('Principled BSDF')
    if set_dir is None:
        b.inputs['Base Color'].default_value = (*fallback, 1)
        b.inputs['Roughness'].default_value = 0.6
        return m
    sid = Path(set_dir).name.rsplit('_', 1)[0]
    tc = t.nodes.new('ShaderNodeTexCoord')
    mp = t.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    t.links.new(tc.outputs['UV'], mp.inputs['Vector'])

    def tex(suffix, non_color=False):
        n = t.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(str(Path(set_dir) / f'{sid}_{suffix}.jpg'), check_existing=True)
        if non_color:
            n.image.colorspace_settings.name = 'Non-Color'
        t.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n
    col = tex('Color').outputs['Color']
    if tint:
        mix = t.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.0
        t.links.new(col, mix.inputs[6])
        mix.inputs[7].default_value = (*tint, 1)
        col = mix.outputs[2]
    t.links.new(col, b.inputs['Base Color'])
    t.links.new(tex('Roughness', True).outputs['Color'], b.inputs['Roughness'])
    nm = t.nodes.new('ShaderNodeNormalMap')
    t.links.new(tex('NormalGL', True).outputs['Color'], nm.inputs['Color'])
    t.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return m


def box(sc, name, size, loc, mat=None, uv_scale=1.0):
    """An axis-aligned box (size x, y, z) centred at loc, with box-projected UVs in metres x uv_scale."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] * uv_scale, lp.vert.co[b] * uv_scale)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    o.location = loc
    if mat:
        me.materials.append(mat)
    return o


def desk_room(sc, width=1.8, depth=0.9, wall_y=0.55):
    """An oak desk top (its top at DESK_Z, the front edge at y = -depth / 2), a plaster wall behind, a floor."""
    wood = pbr_material('desk_oak', cached('textures', 'Wood066_1k'), scale=1.4, fallback=(0.32, 0.22, 0.13))
    plaster = pbr_material('wall_plaster', cached('textures', 'PaintedPlaster017_2k'), scale=0.8,
                           fallback=(0.55, 0.53, 0.50), tint=(0.78, 0.76, 0.72))
    box(sc, 'desk_top', (width, depth, 0.032), (0.0, 0.0, DESK_Z - 0.016), wood)
    for sx in (-1, 1):
        box(sc, f'desk_leg_{sx}', (0.05, depth - 0.1, DESK_Z - 0.032), (sx * (width / 2 - 0.06), 0.0,
                                                                        (DESK_Z - 0.032) / 2), wood)
    box(sc, 'wall', (width + 3.0, 0.06, 3.0), (0.0, wall_y + 0.03, 1.5), plaster)
    box(sc, 'floor', (width + 3.0, 4.0, 0.02), (0.0, -1.0, -0.01),
        pbr_material('floor', cached('textures', 'WoodFloor064_2k'), scale=0.7, fallback=(0.2, 0.15, 0.1)))


def key_light(sc, target, dist=1.6, power=60.0, size=0.45):
    """A warm key from the front left and above, a large cool fill from the right, a little rim from behind."""
    t = Vector(target)
    area_light(sc, t + Vector((-0.75, -1.0, 0.95)) * dist, t, power, size=size, color=(1.0, 0.88, 0.74), name='key')
    area_light(sc, t + Vector((1.1, -0.9, 0.35)) * dist, t, power * 0.22, size=size * 3.0, color=(0.78, 0.85, 1.0),
               name='fill')
    area_light(sc, t + Vector((0.4, 0.9, 1.0)) * dist, t, power * 0.25, size=size * 1.5, color=(1.0, 0.95, 0.9),
               name='rim')


def render(path, frame=None):
    sc = bpy.context.scene
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame is not None:
        sc.frame_set(frame)
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    ok = path.exists()
    print(f'[render] frame {sc.frame_current} -> {path} {"written" if ok else "MISSING"}', flush=True)
    if not ok:
        raise RuntimeError(f'render did not write {path}')
    return path


def magenta_fraction(png):
    from PIL import Image
    a = np.asarray(Image.open(png).convert('RGB')).astype(int)
    return float(((a[..., 0] > 240) & (a[..., 1] < 20) & (a[..., 2] > 240)).mean())


def project(sc, cam, co):
    """A world point -> (x, y) pixel in the render (y down), with bpy_extras.object_utils.world_to_camera_view."""
    from bpy_extras.object_utils import world_to_camera_view
    p = world_to_camera_view(sc, cam, Vector(co))
    r = sc.render
    return p.x * r.resolution_x, (1.0 - p.y) * r.resolution_y


def region_mean(png, box_px):
    """Mean sRGB (0..255) of a pixel box (x0, y0, x1, y1) of a PNG."""
    from PIL import Image
    a = np.asarray(Image.open(png).convert('RGB')).astype(float)
    x0, y0, x1, y1 = (int(round(v)) for v in box_px)
    return a[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)].reshape(-1, 3).mean(axis=0)


def fcurve(idb, path, index=0):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return None
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    if cb is None:
        return None
    return next((fc for fc in cb.fcurves if fc.data_path == path and fc.array_index == index), None)


def tidy_screens(dirs):
    """Delete regenerable screen frame folders a probe wrote."""
    import shutil
    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)


__all__ = ['OUT', 'check', 'summary', 'fresh_scene', 'camera', 'area_light', 'desk_room', 'key_light', 'render',
           'DESK_Z', 'project', 'region_mean', 'fcurve', 'magenta_fraction', 'args']
