"""Shared staging for the media family's probe scripts: an EEVEE scene, a camera, a room, still renders.

Imported by the test scripts beside it (run through run_blender.sh). Probe renders stay small: 960 x 540 at most,
16 EEVEE samples or fewer.
"""
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / 'out'
ASSETS = WORKTREE / 'eidoverse' / 'assets'
if str(WORKTREE / 'blender') not in sys.path:
    sys.path.insert(0, str(WORKTREE / 'blender'))


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
    e.use_fast_gi = True
    e.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.new('world')
    sc.world = w
    if w.node_tree is None:
        w.use_nodes = True
    bg = w.node_tree.nodes.get('Background') or w.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.010, 0.011, 0.013, 1)
    bg.inputs['Strength'].default_value = 1.0
    return sc


def look_at(obj, target, up=Vector((0, 0, 1))):
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


def area_light(sc, loc, target, power, size=0.5, size_y=None, color=(1, 1, 1), name='key'):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.color = color
    if size_y:
        ld.shape = 'RECTANGLE'
        ld.size, ld.size_y = size, size_y
    else:
        ld.size = size
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


def pbr_material(name, set_dir, scale=1.0, fallback=(0.3, 0.22, 0.15)):
    """A Principled material from an AmbientCG set (Color, Roughness, NormalGL), or a plain colour."""
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
        f = Path(set_dir) / f'{sid}_{suffix}.jpg'
        n = t.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(str(f), check_existing=True)
        if non_color:
            n.image.colorspace_settings.name = 'Non-Color'
        t.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n
    t.links.new(tex('Color').outputs['Color'], b.inputs['Base Color'])
    t.links.new(tex('Roughness', True).outputs['Color'], b.inputs['Roughness'])
    nm = t.nodes.new('ShaderNodeNormalMap')
    t.links.new(tex('NormalGL', True).outputs['Color'], nm.inputs['Color'])
    t.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return m


def plain_material(name, color, roughness=0.6, metallic=0.0):
    m = _mat(name)
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = roughness
    b.inputs['Metallic'].default_value = metallic
    return m


def box(sc, name, size, loc, mat=None, uv_scale=1.0):
    """An axis-aligned box (size x, y, z) with box-projected UVs in metres x uv_scale."""
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


def import_gltf(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def render_still(sc, frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sc.frame_set(frame)
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGBA' if r.film_transparent else 'RGB'
    r.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if not path.exists():
        raise RuntimeError(f'render did not write {path}')
    print(f'[probe] frame {frame} -> {path}', flush=True)
    return path
