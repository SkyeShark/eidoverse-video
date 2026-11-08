"""Film-scale probes of the Ekigar port in Blender EEVEE, grey clay under a low raking sun (scenes in hero_scenes.py):

  tile_strip_*   Ekigar's proof_tile_strip (scripts/proof_tile_strip.mjs): one tile laid out three times side by
                 side, built with build_mesh(wrap=True); a seam between copies would show as a crease, a step or a
                 slit. *_seam_wrap / *_seam_nowrap look straight down a seam from close by: with the seam row
                 (wrap=True) and without it (the one-texel slit the copies had before)
  hero_*         landforms at 1024 texels over real kilometres, seen from a low aerial camera, to judge them as
                 ground a film would stand on
  hero_alpine_valley_composite_eye_level / _contact   the film terrain from a person's eye on the valley floor, with
                 1.8 m figures and 4 m boulders placed by hf.height_at, and a close look at one figure's feet
  preview_*      every preview_material mode (grey, Ekigar's shaded preview, its unlit diagnostics and 'mask:<name>'
                 views of a named output and a masks.js mask) on one terrain

Generate first, on the CPU (no GPU slot needed):  python blender/tests/terrain_ekigar/hero_scenes.py
then render:
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \\
        bash run_blender.sh <worktree>/blender/tests/terrain_ekigar/render_heroes.py [--only name,name]
A scene whose cache is missing is generated here. Writes out/heroes/<name>.png and out/heroes/index.json.
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.common import script_args  # noqa: E402
from eidoblend.terrain import ekigar  # noqa: E402
from eidoblend.terrain.ekigar.mesh import PREVIEW_MODES  # noqa: E402
import hero_scenes  # noqa: E402

args = script_args()
only = args[args.index('--only') + 1].split(',') if '--only' in args else None
OUT = os.path.join(HERE, 'out', 'heroes')
os.makedirs(OUT, exist_ok=True)
MASK_VIEWS = ['mask:depth', 'mask:concave']          # snow's named output, and a masks.js mask


def setup(res=(960, 540), samples=16):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = res
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.42, 0.52, 0.66, 1.0)
    bg.inputs['Strength'].default_value = 0.35
    sun_d = bpy.data.lights.new('sun', 'SUN')
    sun_d.energy = 4.0
    sun_d.angle = math.radians(0.6)
    sun_d.color = (1.0, 0.93, 0.84)
    sun = bpy.data.objects.new('sun', sun_d)
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.5
    cam.data.clip_end = 100000
    return sc, sun, cam


def aim(obj, at):
    obj.rotation_euler = (Vector(at) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def sun_from(sun, azimuth_deg, elevation_deg):
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()


def heightfield(name, how, res, world, vs):
    path = hero_scenes.cache_path(OUT, name)
    if os.path.exists(path):
        return ekigar.Heightfield.load(path)
    g, t = hero_scenes.build(ekigar, how)
    hf = ekigar.generate(g, target=t, resolution=res, world_size=world, vertical_scale=vs, z_base='min')
    hf.save(path)
    return hf


def flat_mat(name, rgb, rough=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    return m


index = {}


def render(sc, shot, **info):
    sc.render.filepath = os.path.join(OUT, f'{shot}.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    ok = os.path.exists(sc.render.filepath)
    index[shot] = dict(info, render_s=round(time.time() - t0, 2), written=ok)
    print(f'[heroes] {shot} render {time.time() - t0:.1f}s {"" if ok else "NOT WRITTEN"}', flush=True)


def tile_seams(name, hf, saz, sel):
    """Straight down a seam between two copies, from close by, with and without the seam row."""
    W = hf.world_size
    h = 0.5 * W / hf.resolution[0]
    seam_x = W / 2 + h                                    # copy 1 (at 0) meets copy 2 (at W) here when wrapped
    ys = np.linspace(-0.3 * W, 0.3 * W, 61)
    zs = hf.height_at(np.full_like(ys, seam_x), ys, wrap=True)
    y0 = float(ys[int(np.argmax(np.abs(np.gradient(zs))))])   # where the ground is steepest along the seam
    z0 = float(hf.height_at(seam_x, y0, wrap=True))
    for wrap in (True, False):
        shot = f'{name}_seam_{"wrap" if wrap else "nowrap"}'
        if only and shot not in only and name not in only:
            continue
        sc, sun, cam = setup()
        mat = ekigar.preview_material('grey')
        for k in (1, 2):
            o = ekigar.build_mesh(hf, name=f'{shot}_{k}', attributes=False, wrap=wrap,
                                  location=((k - 1) * W, 0, 0))
            o.data.materials.append(mat)
        cam.location = (seam_x - 18, y0 - 26, z0 + 55)
        cam.data.lens = 50
        aim(cam, (seam_x, y0, z0))
        sun_from(sun, saz, max(sel, 35))
        render(sc, shot, seam_x=seam_x, seam_y=y0, texel_m=2 * h, wrap=wrap)


def valley_eye_level(hf, saz):
    """The film terrain from eye height on its valley floor: figures and boulders placed by height_at."""
    W = hf.world_size
    z = hf.heights_m
    ny, nx = z.shape
    xs, ys = hf.grid_xy()
    slope = hf.mask('slope')
    inner = np.zeros_like(z, dtype=bool)
    inner[ny // 4:3 * ny // 4, nx // 4:3 * nx // 4] = True
    cand = inner & (slope < np.quantile(slope[inner], 0.25))
    j, i = np.unravel_index(int(np.argmin(np.where(cand, z, np.inf))), z.shape)
    fx, fy = float(xs[j, i]), float(ys[j, i])
    # the valley runs where the ground rises least: try 24 bearings, 400 m out
    bearings = np.linspace(0, 2 * math.pi, 24, endpoint=False)
    rise = [float(np.mean([hf.height_at(fx + r * math.cos(b), fy + r * math.sin(b)) for r in (150, 300, 450)]))
            for b in bearings]
    b = float(bearings[int(np.argmin(rise))])
    d = np.array([math.cos(b), math.sin(b)])
    n = np.array([-d[1], d[0]])
    cam_xy = np.array([fx, fy]) - 12 * d
    cam_z = float(hf.height_at(*cam_xy)) + 1.7
    sc, sun, cam = setup()
    terr = ekigar.build_mesh(hf, name='valley', attributes=False)
    terr.data.materials.append(ekigar.preview_material('grey'))
    fig = flat_mat('figure', (0.75, 0.16, 0.10), 0.5)
    rock = flat_mat('boulder', (0.22, 0.21, 0.20), 0.9)
    placed = []
    for k, (along, side) in enumerate([(14, 2.5), (22, -3), (35, 5), (55, -6), (90, 4), (150, -10)]):
        p = np.array([fx, fy]) + along * d + side * n
        zg = float(hf.height_at(*p))
        bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=1.8, vertices=24, location=(p[0], p[1], zg + 0.9))
        bpy.context.active_object.data.materials.append(fig)
        placed.append((float(p[0]), float(p[1]), zg))
        q = p + 4.0 * n * (1 if k % 2 else -1) + 2.0 * d
        bpy.ops.mesh.primitive_ico_sphere_add(radius=2.0, subdivisions=3,
                                              location=(q[0], q[1], float(hf.height_at(*q)) + 1.2))
        bpy.context.active_object.data.materials.append(rock)
    look = np.array([fx, fy]) + 120 * d
    cam.location = (float(cam_xy[0]), float(cam_xy[1]), cam_z)
    cam.data.lens = 24
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20000
    aim(cam, (float(look[0]), float(look[1]), cam_z + 6))
    sun_from(sun, saz, 24)
    info = {'floor': [fx, fy, float(hf.height_at(fx, fy))], 'bearing_deg': math.degrees(b), 'figures': placed}
    render(sc, 'hero_alpine_valley_composite_eye_level', **info)
    x, y, zg = placed[1]
    cam.location = (x - 4.5 * d[0] + 3 * n[0], y - 4.5 * d[1] + 3 * n[1], zg + 1.4)
    cam.data.lens = 35
    aim(cam, (x, y, zg + 0.5))
    render(sc, 'hero_alpine_valley_composite_contact', figure=[x, y, zg])


for name, how, res, world, vs, cam_loc, look, saz, sel, copies in hero_scenes.SCENES:
    shots = ([f'preview_{m}' for m in PREVIEW_MODES + MASK_VIEWS] if name == 'preview_modes' else [name])
    extra = []
    if name.startswith('tile_strip_'):
        extra = [f'{name}_seam_wrap', f'{name}_seam_nowrap']
    if name == 'hero_alpine_valley_composite':
        extra = [f'{name}_eye_level', f'{name}_contact']
    if only and not any(m in only for m in shots + extra + [name]):
        continue
    hf = heightfield(name, how, res, world, vs)
    relief = float(hf.heights_m.max() - hf.heights_m.min())
    for shot in shots:
        if only and shot not in only and name not in only:
            continue
        small = shot.startswith('preview_')
        sc, sun, cam = setup(res=(480, 270) if small else (960, 540))
        mode = shot[len('preview_'):].replace('mask_', 'mask:') if small else 'grey'
        mat = ekigar.preview_material(mode)
        for k in range(copies):
            ox = (k - (copies - 1) / 2) * hf.world_size
            o = ekigar.build_mesh(hf, name=f'{shot}_{k}', attributes=small, location=(ox, 0, 0), wrap=copies > 1)
            o.data.materials.append(mat)
        cam.location = cam_loc
        cam.data.lens = 28 if copies > 1 else 35
        aim(cam, look)
        sun_from(sun, saz, sel)
        render(sc, shot.replace(':', '_'), world_size=hf.world_size, resolution=hf.resolution, relief_m=relief,
               warnings=hf.warnings)
    if name.startswith('tile_strip_'):
        tile_seams(name, hf, saz, sel)
    if name == 'hero_alpine_valley_composite' and (not only or any(e in only for e in extra + [name])):
        valley_eye_level(hf, saz)
with open(os.path.join(OUT, 'index.json'), 'w') as f:
    json.dump(index, f, indent=1, default=str)
print(f'[heroes] {len(index)} shots', flush=True)
