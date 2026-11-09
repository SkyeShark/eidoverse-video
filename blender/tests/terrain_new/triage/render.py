"""Render the triage subjects (scenes.py; fields from generate.py / fetch_dem.py) in Blender EEVEE: grey clay
(ekigar.preview_material('grey'): albedo 0.5, roughness 0.92) on build_mesh's true-displacement grid, lit by make_sky's
clear-sky Earth daylight, the sun 32 degrees up from the north-west (the top of every top view is north, +y).

Three views per subject, written to renders/<name>__<view>.png:
  top     straight down over the whole tile (a near-orthographic 727 mm lens from 20 tile-widths up): the hillshade
  aerial  45 degrees down from the south-west over the whole tile (35 mm), the sun from the left
  eye     a 1.7 m camera standing on the ground (28 mm), looking north-east at the main feature, or where scenes.py
          puts it
Subjects with an overlay paint that mask on the clay (a 0..1 ramp, dark blue -> yellow), lit as clay.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/triage/render.py [--only a,b] [--group g] [--views top,aerial,eye]
        [--skip-existing] [--samples 16] [--exposure 0]
The make_sky bake takes a proxy camera with the render camera's rotation and lens, at most 2 km up, so a 200 km
aerial still gets an ordinary sky; the top view needs no bake of its own (every camera ray hits terrain).
"""
import json
import math
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, BLENDER_DIR)
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.common import script_args  # noqa: E402
from eidoblend.terrain import ekigar  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
import scenes  # noqa: E402

HOURS, AZ_BASE = 15.93, 3.001     # sky.sun_dir = north-west (-x, +y), 32 degrees up (palette.sun_moon_at)
EYE_H = 1.7
SKY_TMP = os.path.join(scenes.CACHE, '_sky')

args = script_args()


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


only = opt('--only')
only = only.split(',') if only else None
groups = opt('--group')
groups = groups.split(',') if groups else None
views = opt('--views', 'eye,aerial,top').split(',')
samples = int(opt('--samples', 16))
exposure = float(opt('--exposure', 0.0))
skip_existing = '--skip-existing' in args
os.makedirs(scenes.RENDERS, exist_ok=True)

# ------------------------------------------------------------------------------------------------ scene ---
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = samples
sc.eevee.use_shadows = True
try:
    sc.eevee.use_raytracing = True
except AttributeError:
    pass
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = exposure
sc.render.image_settings.file_format = 'PNG'
sc.render.resolution_percentage = 100
sc.frame_start = sc.frame_end = 1


def new_cam(name):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'AUTO'
    cd.sensor_width = 36.0
    ob = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(ob)
    return ob


cam = new_cam('cam')
skycam = new_cam('skycam')
sc.camera = cam
SUN = [None]
CLAY = ekigar.preview_material('grey')


def overlay_material():
    """The clay with a 0..1 mask painted on it through a dark-blue -> teal -> yellow ramp, lit like the clay."""
    mat = bpy.data.materials.new('triage_overlay')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.92
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_type = 'GEOMETRY'
    at.attribute_name = 'triage_ov'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    stops = [(0.0, (0.02, 0.02, 0.12)), (0.25, (0.03, 0.10, 0.45)), (0.5, (0.02, 0.40, 0.42)),
             (0.75, (0.35, 0.65, 0.08)), (1.0, (0.95, 0.85, 0.05))]
    cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1)
    cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = cr.elements.new(p)
        e.color = (*c, 1)
    nt.links.new(at.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


OVERLAY = overlay_material()


# ----------------------------------------------------------------------------------------------- fields ---
def load(name):
    d = np.load(scenes.cache_path(name), allow_pickle=False)
    meta = json.loads(str(d['meta']))
    h = d['height'].astype(np.float64)
    aux = d['aux'].astype(np.float64)
    z0 = np.zeros_like(h)
    hf = ekigar.Heightfield(np.stack([h, z0, z0, aux]), {}, meta['tile'], meta['W'], meta['vs'], (0.0, 0.0),
                            meta['z_base'], meta['warnings'], meta)
    ov = d['ov'].astype(np.float64) if 'ov' in d.files else None
    return hf, ov, meta


def blur(a, k):
    """Separable box blur, radius k texels, edges clamped."""
    if k < 1:
        return a
    for ax in (0, 1):
        p = np.pad(a, [(k, k) if i == ax else (0, 0) for i in range(2)], mode='edge')
        c = np.cumsum(p, axis=ax)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=ax)), c], axis=ax)
        n = a.shape[ax]
        a = (np.take(c, np.arange(2 * k + 1, 2 * k + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)) / (2 * k + 1)
    return a


def uv_to_xy(hf, u, v):
    W = hf.world_size
    return (u - 0.5) * W, (v - 0.5) * W


# ---------------------------------------------------------------------------------------------- cameras ---
def look(ob, at):
    ob.rotation_euler = (Vector(at) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def cam_top(hf):
    z = hf.heights_m
    W = hf.world_size
    D = 20.0 * W
    cam.location = (0.0, 0.0, float(z.max()) + D)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    cam.data.lens = 18.0 / (0.494 / 20.0)            # half-width 0.494 W at 20 W: inside the outermost vertices
    cam.data.clip_start = D - W
    cam.data.clip_end = D + float(z.max() - z.min()) + W
    sc.render.resolution_x = sc.render.resolution_y = 540


def cam_aerial(hf):
    z = hf.heights_m
    W = hf.world_size
    tgt = Vector((0.0, 0.0, float(np.median(z))))
    D = 1.45 * W
    d = Vector((-math.sqrt(0.5) * math.cos(math.radians(45)), -math.sqrt(0.5) * math.cos(math.radians(45)),
                math.sin(math.radians(45))))
    cam.location = tgt + d * D
    look(cam, tgt)
    cam.data.lens = 35.0
    cam.data.clip_start = max(0.05, 0.02 * W)
    cam.data.clip_end = 5.0 * W
    sc.render.resolution_x, sc.render.resolution_y = 960, 540


def eye_spot(hf, s):
    """(camera x, y, target x, y, z): scenes.py's spot, else stand south-west of the main feature, far enough that it
    rises about 14 degrees, inside the tile."""
    W = hf.world_size
    z = hf.heights_m
    ny, nx = z.shape
    e = s.get('eye')
    if e:
        if 'at_low' in e:                     # the lowest ground in a (u0, v0, u1, v1) box: a valley or crater floor
            u0, v0, u1, v1 = e['at_low']
            zb = blur(z, max(1, nx // 128))
            i0, i1, j0, j1 = int(u0 * nx), int(u1 * nx), int(v0 * ny), int(v1 * ny)
            sub = zb[j0:j1, i0:i1]
            jj, ii = np.unravel_index(int(np.argmin(sub)), sub.shape)
            px, py = (ii + i0 + 0.5) / nx * W - W / 2, (jj + j0 + 0.5) / ny * W - W / 2
        else:
            px, py = uv_to_xy(hf, *e['at'])
        if 'look_dir' in e:                   # a compass heading (0 = north, +y; 90 = east, +x), level
            a = math.radians(e['look_dir'])
            tx, ty = px + math.sin(a) * W, py + math.cos(a) * W
            tz = float(hf.height_at(px, py)) + EYE_H
        else:
            tx, ty = uv_to_xy(hf, *e['look'])
            tz = float(hf.height_at(tx, ty))
        return px, py, tx, ty, tz
    zs = blur(z, max(1, nx // 48))
    m = int(nx * 0.15)
    inner = zs[m:ny - m, m:nx - m]
    j, i = np.unravel_index(int(np.argmax(inner)), inner.shape)
    j, i = j + m, i + m
    tx, ty = (i + 0.5) / nx * W - W / 2, (j + 0.5) / ny * W - W / 2
    tz = float(z[j, i])
    relief = max(tz - float(np.percentile(z, 20)), 1e-3)
    d = float(np.clip(relief / math.tan(math.radians(14)), 0.12 * W, 0.42 * W))
    px = float(np.clip(tx - math.sqrt(0.5) * d, -0.46 * W, 0.46 * W))
    py = float(np.clip(ty - math.sqrt(0.5) * d, -0.46 * W, 0.46 * W))
    return px, py, tx, ty, tz


def cam_eye(hf, s):
    W = hf.world_size
    px, py, tx, ty, tz = eye_spot(hf, s)
    cz = float(hf.height_at(px, py)) + EYE_H
    cam.location = (px, py, cz)
    dist = max(math.hypot(tx - px, ty - py), 1e-3)
    a_top = math.atan2(tz - cz, dist)
    pitch = (s.get('eye') or {}).get('pitch')
    pitch = math.radians(pitch) if pitch is not None else min(max(a_top - math.radians(6), math.radians(-5)),
                                                              math.radians(15))
    yaw = math.atan2(ty - py, tx - px)
    cam.rotation_euler = (math.pi / 2 + pitch, 0.0, yaw - math.pi / 2)
    cam.data.lens = 28.0
    cam.data.clip_start = 0.1 if W < 50000 else 2.0
    cam.data.clip_end = 3.0 * W
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    return {'at_m': [round(px, 1), round(py, 1), round(cz, 1)], 'look_m': [round(tx, 1), round(ty, 1), round(tz, 1)],
            'pitch_deg': round(math.degrees(pitch), 1)}


def bake_sky(tag):
    """make_sky (clear Earth daylight) baked through a proxy of the render camera: same rotation and lens, at most
    2 km up."""
    skycam.matrix_world = cam.matrix_world.copy()
    loc = cam.matrix_world.translation
    skycam.location = (loc.x, loc.y, min(loc.z, 2000.0))
    skycam.data.lens = cam.data.lens
    skycam.data.clip_start = cam.data.clip_start
    skycam.data.clip_end = cam.data.clip_end
    d = os.path.join(SKY_TMP, tag)
    sky = make_sky(sc, camera=skycam, world='earth', hours=HOURS, clouds='clear', cache_dir=d, quality='film',
                   shadows=False, sun=SUN[0], azimuth=AZ_BASE)
    sky.bake(log=lambda *a: None)
    if SUN[0] is None:
        SUN[0] = sky.sun
        sd = sky.sun_dir
        print('[triage] sun dir', [round(c, 3) for c in sd], 'elevation %.1f' % math.degrees(math.asin(sd[2])),
              flush=True)
    sc.camera = cam
    return d


def purge():
    for im in list(bpy.data.images):
        if im.users == 0:
            bpy.data.images.remove(im)


# ---------------------------------------------------------------------------------------------- the run ---
subs = [s for s in scenes.SUBJECTS if (not only or s['name'] in only) and (not groups or s['group'] in groups)]
first = opt('--first')
if first:                                  # render these first (a quick look at the rig before the long run)
    first = first.split(',')
    subs = [s for s in subs if s['name'] in first] + [s for s in subs if s['name'] not in first]
index_path = os.path.join(scenes.RENDERS, 'index.json')
index = json.load(open(index_path)) if os.path.exists(index_path) else {}
t_all = time.time()
for s in subs:
    name = s['name']
    if not os.path.exists(scenes.cache_path(name)):
        print(f'[triage] {name}: no field in the cache, skipped', flush=True)
        continue
    todo = [v for v in views if not (skip_existing and os.path.exists(os.path.join(scenes.RENDERS,
                                                                                  f'{name}__{v}.png')))]
    if not todo:
        continue
    t0 = time.time()
    hf, ov, meta = load(name)
    tile3 = s.get('tile3') and hf.tile.x > 0 and hf.tile.y > 0
    obj = ekigar.build_mesh(hf, name=name, attributes=False, wrap=bool(tile3))
    if ov is not None:
        if tile3:                                          # the wrap mesh's seam row and column read texel 0
            ov = np.pad(ov, ((0, 1), (0, 1)), mode='wrap')
        att = obj.data.attributes.new('triage_ov', 'FLOAT', 'POINT')
        att.data.foreach_set('value', np.clip(ov, 0.0, 1.0).astype(np.float32).ravel())
        obj.data.materials.append(OVERLAY)
    else:
        obj.data.materials.append(CLAY)
    t_mesh = time.time() - t0
    rec = index.get(name, {})
    rec.update({'group': s['group'], 'promise': s['promise'], 'W': meta['W'], 'relief_m': meta['relief_m'],
                'texel_m': meta['texel_m'], 'warnings': meta.get('warnings', []), 'ov_range': meta.get('ov_range')})
    order = [v for v in ('eye', 'aerial', 'top') if v in todo]
    if order == ['top']:
        order = ['aerial_bake_only', 'top']                # the top view still needs a keyed world
    copies = []
    for v in order:
        for c in copies:                                   # the 3 x 3 layout is for the eye-level view only
            bpy.data.objects.remove(c, do_unlink=True)
        copies = []
        if v == 'eye':
            rec['eye'] = cam_eye(hf, s)
            if tile3:
                W = hf.world_size
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx or dy:
                            c = bpy.data.objects.new(f'{name}_copy', obj.data)     # linked: same mesh
                            c.location = (dx * W, dy * W, 0.0)
                            sc.collection.objects.link(c)
                            copies.append(c)
                rec['eye']['tiled_3x3'] = True
        elif v in ('aerial', 'aerial_bake_only'):
            cam_aerial(hf)
        else:
            cam_top(hf)
        d = None
        if v != 'top':
            d = bake_sky(f'{name}_{v}')
        if v != 'aerial_bake_only':
            sc.render.filepath = os.path.join(scenes.RENDERS, f'{name}__{v}.png')
            bpy.ops.render.render(write_still=True)
        if d:
            shutil.rmtree(d, ignore_errors=True)
        purge()
    for c in copies:
        bpy.data.objects.remove(c, do_unlink=True)
    me = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    rec['render_s'] = round(time.time() - t0, 1)
    index[name] = rec
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=1)
    print(f'[triage] {name:34s} mesh {t_mesh:.1f}s total {time.time() - t0:.1f}s', flush=True)
print(f'[triage] {len(subs)} subjects in {time.time() - t_all:.0f}s', flush=True)
