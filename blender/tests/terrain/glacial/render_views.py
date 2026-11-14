"""Render photo-matched views (photo_views.py writes the job) in grey clay under make_sky daylight, with the
reference rig's scene: its clay, exposure and AgX look, the main tile and its wider context as meshes, the Earth's
curvature (with refraction) dropped away from the camera, the sun 70 degrees left of the view at 15:30.

    bash run_blender.sh blender/tests/terrain/glacial/render_views.py --job <job.json> [--samples 16]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Each view: {name, source: {reference: name} or {npz: path (gen.py's: h row 0 = south, cell, context_h,
context_cell)}, camera: {x, y, z (metres, the source's own heights), heading_deg (compass), pitch_deg, lens_mm (a
36 mm frame's width)}}. Writes <out_dir>/<name>.png at 960 x 540 and <out_dir>/<job>_record.json.
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, TN)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain.core import grid  # noqa: E402
from judge import refs  # noqa: E402


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[a.index('--job') + 1], int(a[a.index('--samples') + 1]) if '--samples' in a else 16


def load_source(src):
    """(h north-up float64, pixel, context (hc north-up, pc) or None), heights in metres as stored."""
    if 'reference' in src:
        r = refs.load(src['reference'])
        ctx = refs.load_context(src['reference'])
        c = (grid.to_north_up(ctx[0]), ctx[1]) if ctx is not None else None
        return grid.to_north_up(r.h), r.pixel, c
    d = np.load(src['npz'])
    c = None
    if 'context_h' in d.files:
        c = (grid.to_north_up(np.asarray(d['context_h'], np.float64)), float(d['context_cell']))
    return grid.to_north_up(np.asarray(d['h'], np.float64)), float(d['cell']), c


def build(h, pixel, context, cam_xy):
    """The rig's eye-view scene: the tile and its context in clay, both dropped by the Earth's curvature away from
    the camera; the context under the tile follows the tile 8 m down with its covered quads cut. Returns z0 (the
    height subtracted from every mesh)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = RR.new_scene((960, 540), SAMPLES, RR.EXPOSURE)
    clay = RR.material('clay', RR.CLAY, 0.9)
    rows, cols = h.shape
    ext = (cols * pixel, rows * pixel)
    z0 = float(h.min())
    xs, ys = RR.axes(rows, cols, pixel)
    X, Y = np.meshgrid(xs, ys)
    z = h - z0 - ((X - cam_xy[0]) ** 2 + (Y - cam_xy[1]) ** 2) / (2 * RR.R_EFF)
    RR.grid_mesh('terrain', z, xs, ys, skirt_m=15.0, mat=clay)
    if context is not None:
        hc, pc = context
        rc, cc = hc.shape
        xcs, ycs = RR.axes(rc, cc, pc)
        XC, YC = np.meshgrid(xcs, ycs)
        zc = hc - z0
        inside = (np.abs(XC) < ext[0] / 2) & (np.abs(YC) < ext[1] / 2)
        meta_t = dict(rows=rows, cols=cols, pixel_size_m=pixel)
        zc[inside] = RR.R.sample(h - z0, meta_t, XC[inside], YC[inside]) - 8.0
        zc = zc - ((XC - cam_xy[0]) ** 2 + (YC - cam_xy[1]) ** 2) / (2 * RR.R_EFF)
        shrink = (np.abs(XC) < ext[0] / 2 - pc) & (np.abs(YC) < ext[1] / 2 - pc)
        keep = ~(shrink[:-1, :-1] & shrink[1:, :-1] & shrink[1:, 1:] & shrink[:-1, 1:])
        RR.grid_mesh('context', zc, xcs, ycs, face_keep=keep, mat=clay)
    return sc, z0


def render(view, out_dir, sky_root):
    t0 = time.time()
    h, pixel, ctx = load_source(view['source'])
    c = view['camera']
    sc, z0 = build(h, pixel, ctx, (c['x'], c['y']))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    hd, pt = math.radians(c['heading_deg']), math.radians(c['pitch_deg'])
    d = Vector((math.sin(hd) * math.cos(pt), math.cos(hd) * math.cos(pt), math.sin(pt)))
    eye = Vector((c['x'], c['y'], c['z'] - z0))
    cam.data.lens = float(c['lens_mm'])
    cam.data.sensor_width = 36.0
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.clip_start, cam.data.clip_end = 1.0, 120000.0
    RR.place_camera(cam, eye, eye + 1000.0 * d)
    # the sun 70 degrees left of the view's compass heading, as the rig's views have it
    sun_xy = (math.sin(hd - math.radians(RR.SUN_LEFT_DEG)), math.cos(hd - math.radians(RR.SUN_LEFT_DEG)))
    cache = os.path.join(sky_root, view['name'])
    os.makedirs(cache, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = os.path.join(out_dir, view['name'] + '.png')
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    print(f"[glacial.views] {view['name']}.png {time.time() - t0:.1f} s", flush=True)
    return dict(camera=c, z0=z0, seconds=round(time.time() - t0, 1))


SAMPLES = 16


def main():
    global SAMPLES
    job_path, SAMPLES = args()
    job = json.load(open(job_path, encoding='utf-8'))
    out_dir = job['out_dir']
    os.makedirs(out_dir, exist_ok=True)
    sky_root = tempfile.mkdtemp(prefix='glacial_sky_')
    rec = {}
    for v in job['views']:
        try:
            rec[v['name']] = render(v, out_dir, sky_root)
        except Exception as e:                                         # noqa: BLE001 - the job goes on
            import traceback
            traceback.print_exc()
            rec[v['name']] = dict(error=f'{type(e).__name__}: {e}')
    shutil.rmtree(sky_root, ignore_errors=True)
    with open(os.path.splitext(job_path)[0] + '_record.json', 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    print('[glacial.views] done', flush=True)
    os._exit(0)


main()
