"""eidoblend.sets.same_seed.look: what the four rooms' looks share (Blender). Each room's look module writes its own
materials with it; nothing here knows a room.

    from eidoblend.sets.same_seed import look as L
    lib = L.Library('<room>/cc0.json')               # the room's CC0 IDs (eidoblend.materials.photo.Library)
    M = L.Mat('room.wall')                           # materials.photo.Mat: NT's maths, pictures, one Principled BSDF
    ao, cav, fine, arr, crn = L.baked(M, bake_dir, 'bench')      # the GPU bake's maps on a low (UV 'atlas')
    M.done(col, rough, metal)
    L.eevee(scene, samples=16)                       # the rooms' render settings (FILM_RENDER), with a room's overrides
    cam = L.camera('view', pos, aim, lens, collection); L.shoot(scene, cam, 'still.png', (960, 540))

THE BAKE'S MAPS (blender/tools/gpu_bake.py, from the room's lows.py): <atlas>_normal.png (tangent space, OpenGL),
<atlas>_masks_a.png (R ambient occlusion, G cavity, B fine curvature, 0.5 flat) and <atlas>_masks_b.png (R nearness of a
convex arris, 1 on it and 0 at its range; B nearness of an inside corner). baked() hands a material those five signals.
Every room bakes with the arris range 30 mm and the corner range 50 mm (ARRIS_MM, CORNER_MM), so a band set in
millimetres reads band(M, near, mm, ARRIS_MM).
"""

from __future__ import annotations

import os
import sys
import time

import bpy
from mathutils import Vector

from ... import common
from ...materials.photo import Library, Mat, assign, box_uv, image, mean_lum, picture, planar_uv  # noqa: F401

ARRIS_MM, CORNER_MM = 30.0, 50.0

# the rooms' render settings: EEVEE with screen-traced rays and Fast GI as global illumination, 16 samples, AgX at
# exposure 0, 1920 x 1080; a room's RENDER changes what its light needs (eevee(..., **overrides))
FILM_RENDER = {
    'resolution': (1920, 1080),
    'samples': 16,
    'view_transform': 'AgX',
    'eevee': {'use_raytracing': True, 'ray_tracing_method': 'SCREEN', 'use_shadows': True, 'shadow_ray_count': 2,
              'shadow_step_count': 12, 'shadow_resolution_scale': 1.0, 'use_fast_gi': True,
              'fast_gi_method': 'GLOBAL_ILLUMINATION', 'fast_gi_resolution': '2', 'fast_gi_step_count': 8,
              'fast_gi_distance': 0.6, 'clamp_surface_indirect': 10.0, 'use_overscan': True, 'overscan_size': 3.0},
    'ray_tracing_options': {'resolution_scale': '1', 'use_denoise': True, 'trace_max_roughness': 0.5,
                            'screen_trace_quality': 0.5},
}
T0 = time.time()


def log(tag, *a):
    print(f'[{tag} {time.time() - T0:6.1f}s]', *a, flush=True)


def baked(M, bake_dir, atlas):
    """The atlas's bake on a low (UV 'atlas'): its normal map into M's normal, and (AO, cavity, fine curvature, arris
    nearness (1 at a convex arris, 0 at ARRIS_MM), inside-corner nearness (1 at it, 0 at CORNER_MM)) as sockets."""
    uvv = M.uv('atlas')
    M.nmap(M.tex(os.path.join(bake_dir, f'{atlas}_normal.png'), uvv).outputs[0], 'atlas', 1.0)
    a = M.sep(M.tex(os.path.join(bake_dir, f'{atlas}_masks_a.png'), uvv).outputs[0])
    b = M.sep(M.tex(os.path.join(bake_dir, f'{atlas}_masks_b.png'), uvv).outputs[0])
    return a[0], a[1], a[2], b[0], b[2]


def band(M, near, mm, rng=ARRIS_MM, noise=None, k=0.3):
    """a band within `mm` of an arris, from a nearness that falls 1 -> 0 over `rng` mm; noise breaks its edge (the
    structure places it, the noise shapes its edge)"""
    t = 1.0 - mm / rng
    x = near if noise is None else M.add(near, M.mul(M.sub(noise, 0.5), k))
    return M.sm(x, t - 0.02, t + 0.02)


# ------------------------------------------------------------------------------------------- models, lights ---

def import_gltf(path, coll):
    """a glTF imported into collection coll (only there); -> its new objects, marked as loaded assets"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        o['eido_loaded_asset'] = True
    return new


def world_bbox(objs):
    """(lo, hi) of the meshes' world bounds"""
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    bpy.context.view_layer.update()
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo, hi = Vector(map(min, lo, w)), Vector(map(max, hi, w))
    return lo, hi


# ------------------------------------------------------------------------------------------ render settings ---

def eevee(sc, samples=None, resolution=None, shadow_pool='1024', exposure=0.0, base=True, rt=None, **overrides):
    """The rooms' render settings on the scene: EEVEE, AgX, no motion blur, an opaque film. base=True: FILM_RENDER's ray
    tracing and Fast GI first (base=False: Blender's own defaults); samples / resolution replace the preset's; overrides
    are scene.eevee attributes (e.g. fast_gi_method='AMBIENT_OCCLUSION_ONLY'), rt ray-tracing options; exposure the view's.
    shadow_pool: the shadow pool's size in MB (a room's many lights; None keeps Blender's)."""
    R = FILM_RENDER
    sc.render.engine = 'BLENDER_EEVEE'
    for k, v in (list(R['eevee'].items()) if base else []) + list(overrides.items()):
        try:
            setattr(sc.eevee, k, v)
        except (AttributeError, TypeError, ValueError) as e:
            log('eevee', 'setting skipped:', k, e)
    for k, v in (list(R['ray_tracing_options'].items()) if base else []) + list((rt or {}).items()):
        try:
            setattr(sc.eevee.ray_tracing_options, k, v)
        except (AttributeError, TypeError, ValueError) as e:
            log('eevee', 'ray tracing option skipped:', k, e)
    sc.eevee.taa_render_samples = int(samples or R['samples'])
    if shadow_pool:
        try:
            sc.eevee.shadow_pool_size = str(shadow_pool)
        except (AttributeError, TypeError) as e:
            log('eevee', 'shadow pool size skipped:', e)
    sc.view_settings.view_transform = R['view_transform']
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = float(exposure)
    sc.render.resolution_x, sc.render.resolution_y = resolution or R['resolution']
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.use_motion_blur = False


def camera(name, pos, aim, lens, coll):
    """a camera at pos looking at aim (metres), a lens of `lens` mm on a 36 mm sensor"""
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = lens, 36.0, 0.05, 800.0
    o = bpy.data.objects.new(name, cd)
    coll.objects.link(o)
    o.location = Vector(pos)
    o.rotation_euler = (Vector(aim) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    return o


def shoot(sc, cam, path, res=None):
    """a still through cam into path (PNG)"""
    sc.camera = cam
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log('render', f'{os.path.basename(path)} {sc.render.resolution_x} x {sc.render.resolution_y} in {time.time() - t:.1f} s')
    return path


def bake_volume_probe(probe, log_tag='probe'):
    """bake one volume light probe over what the scene holds now (its bake is saved with the file and travels with it)"""
    t = time.time()
    bpy.ops.object.select_all(action='DESELECT')
    probe.select_set(True)
    bpy.context.view_layer.objects.active = probe
    r = bpy.ops.object.lightprobe_cache_bake(subset='ALL')
    log(log_tag, f'volume probe {probe.name} baked: {r} in {time.time() - t:.1f} s')
    return r


def save(path):
    """the file, compressed, with no .blend1 beside it; its pictures by path (the library and the room's folder)"""
    bpy.context.preferences.filepaths.save_version = 0
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
    return path


def args(argv=None):
    """{'--key': value} and flags from the arguments after Blender's '--'"""
    a = common.script_args(argv if argv is not None else sys.argv)
    out = {}
    i = 0
    while i < len(a):
        if a[i].startswith('--') and i + 1 < len(a) and not a[i + 1].startswith('--'):
            out[a[i]] = a[i + 1]
            i += 2
        else:
            out[a[i]] = True
            i += 1
    return out
