"""Textured renders of the real DEMs: package 6's acceptance views. Each place's palette (palettes.PLACES) on its
reference DEM (the _place fixture: levels, package 4's masks, package 5's ring mesh), with the reference rig's exact
cameras (reference/renders/<name>_views.json), make_sky daylight, look and exposure, so every textured view lies
beside its grey-clay reference. The eye view adds the palette's rocks around the camera.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/surfacing/render_places.py [--only toroweap,lauterbrunnen,...]
        [--views aerial,eye] [--no-rocks] [--clay] [--samples 16] [--tag v1] [--sky-cache <dir>]

Writes out/surfacing/<place>_<palette>_<view>[_<tag>].png and <place>[_<tag>]_record.json (render seconds per frame:
the first render, which compiles the material, and a second one of the same frame; triangles; rocks).
Short names: toroweap, lauterbrunnen, sand_dunes, fuji, badlands, badlands_detail, guilin, seven_sisters, palouse.
"""
import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _place as PL  # noqa: E402
import render_references as RR  # noqa: E402  (reference/, on the path through _place)
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain.build import dressing as D  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

SHORT = {'toroweap': 'grand_canyon_toroweap', 'lauterbrunnen': 'lauterbrunnen', 'sand_dunes': 'great_sand_dunes',
         'fuji': 'mount_fuji', 'badlands': 'badlands_sd', 'badlands_detail': 'badlands_sd_detail',
         'guilin': 'guilin_karst', 'seven_sisters': 'seven_sisters', 'palouse': 'palouse_hills',
         'namib': 'namib_star_dunes', 'crater_lake': 'crater_lake', 'monument_valley': 'monument_valley'}
ROCK_RADIUS = {'mount_fuji': 120.0}


def water_material():
    m = bpy.data.materials.new('water')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.02, 0.05, 0.07, 1.0)      # the reference rig's water
    b.inputs['Roughness'].default_value = 0.15
    return m


def add_water(st, curvature):
    """Flat sheets over the main tile's lakes (and a sea plane), as the reference rig draws them."""
    p = st['meta']['pixel_size_m']
    wmat = None
    for name, kind, level, sel in PL.lakes(st):
        wmat = wmat or water_material()
        if kind == 'sea':
            span = max(l['n'] * l['cell'] for l in st['levels'])
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, level + 0.1))
            ob = bpy.context.active_object
            ob.name = 'sea'
            ob.scale = (span, span, 1.0)
            ob.data.materials.append(wmat)
            continue
        if not sel.any():
            continue
        m = sel[::-1]                                     # back to north-up for the rig's grid_mesh
        rows, cols = m.shape
        r_idx, c_idx = np.nonzero(m)
        r0, r1 = max(r_idx.min() - 1, 0), min(r_idx.max() + 2, rows)
        c0, c1 = max(c_idx.min() - 1, 0), min(c_idx.max() + 2, cols)
        sub = m[r0:r1, c0:c1]
        keep = sub[:-1, :-1] | sub[1:, :-1] | sub[1:, 1:] | sub[:-1, 1:]
        xs, ys = RR.axes(rows, cols, p)
        X, Y = np.meshgrid(xs[c0:c1], ys[r0:r1])
        wz = np.full(sub.shape, level + 0.1)
        if curvature:
            wz = wz - PL.curvature_drop(X, Y, st['eye'])
        RR.grid_mesh('lake_' + name.replace(' ', '_'), wz, xs[c0:c1], ys[r0:r1], face_keep=keep, mat=wmat)


def gpu_utilisation():
    """The GPU's utilisation in percent just now (nvidia-smi), or None: other jobs share it, so render times come
    with it."""
    try:
        import subprocess
        out = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except Exception:
        return None


def views_record(name):
    with open(os.path.join(str(PL.REF), 'renders', f'{name}_views.json')) as f:
        return json.load(f)


def camera(view, rec, height_at, spans):
    sc = bpy.context.scene
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    pos, tgt = Vector(rec['camera']), Vector(rec['target'])
    cam.data.lens = rec['lens_mm']
    if view == 'aerial':
        dist = (pos - tgt).length
        cam.data.clip_start, cam.data.clip_end = dist * 0.02, dist * 6
    else:
        pos.z = float(height_at(pos.x, pos.y)) + RR.EYE_HEIGHT       # stand on this mesh (hero levels are smoother)
        cam.data.clip_start = 0.05
        cam.data.clip_end = 2.5 * spans
    RR.place_camera(cam, pos, tgt)
    return cam, pos, tgt


def render_one(name, view, args, cache_root):
    rec_ref = views_record(name)[view]
    t0 = time.time()
    exposure = RR.EXPOSURE if args.clay else args.exposure
    sc = RR.new_scene(tuple(rec_ref['resolution']), args.samples, exposure)
    st = PL.stack(name, view)
    rm = PL.ring_mesh(st, mesh_res=args.mesh_res)
    obj = PL.make_mesh(st, rm, 'terrain')
    height_at, normal_at, mask_at = PL.samplers(st, rm)
    pal = st['palette']
    if args.clay:
        obj.data.materials.append(S.clay_material())
        tag_pal = 'clay'
    else:
        if args.debug:
            pal['options']['debug'] = args.debug
        S.apply_surface(obj, pal)
        tag_pal = pal['name'] + (f'_debug_{args.debug}' if args.debug else '')
    add_water(st, curvature=(view == 'eye'))
    rocks = None
    if view == 'eye' and not args.no_rocks and not args.clay and pal.get('dressing'):
        rocks = D.scatter_rocks(spec=pal['dressing'], mask_at=mask_at, height_at=height_at, normal_at=normal_at,
                                focus=st['eye'], radius_m=ROCK_RADIUS.get(name, 150.0), seed=7)
    spans = max(l['n'] * l['cell'] for l in st['levels'])
    cam, pos, tgt = camera(view, rec_ref, height_at, spans)
    sd = rec_ref['sun_dir']
    sun_xy = (sd[0] / math.hypot(sd[0], sd[1]), sd[1] / math.hypot(sd[0], sd[1]))
    cache_dir = os.path.join(cache_root, f'{name}_{view}')
    os.makedirs(cache_dir, exist_ok=True)
    t_build = time.time() - t0
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache_dir,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    tag = f'_{args.tag}' if args.tag else ''
    out = PL.OUT / f'{name}_{tag_pal}_{view}{tag}.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out)
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    t_first = time.time() - t1
    gpu_busy = gpu_utilisation()
    t_second = 1e9
    for _ in range(2):                                   # the GPU is shared with other jobs: the best of two frames
        t2 = time.time()
        bpy.ops.render.render(write_still=False)
        t_second = min(t_second, time.time() - t2)
    t_clay = None
    if args.time_clay and not args.clay:
        # the same frame in clay, back to back: the difference is the material's own shading cost, which survives
        # the other jobs sharing the GPU better than either number alone
        obj.data.materials.clear()
        obj.data.materials.append(S.clay_material())
        bpy.ops.render.render(write_still=False)           # compile
        t_clay = 1e9
        for _ in range(2):
            t2 = time.time()
            bpy.ops.render.render(write_still=False)
            t_clay = min(t_clay, time.time() - t2)
    print(f'[places] {out.name}: build {t_build:.1f} s, first render {t_first:.1f} s (compiles the material), '
          f'second {t_second:.2f} s; {rm.triangle_count} triangles' + (f'; {rocks["count"]} rocks' if rocks else ''),
          flush=True)
    if t_clay is not None:
        print(f'[places] {out.name}: the same frame in clay {t_clay:.2f} s (material cost {t_second - t_clay:.2f} s); '
              f'GPU busy {gpu_busy}% before timing', flush=True)
    return dict(view=view, palette=tag_pal, png=str(out), build_s=round(t_build, 2), first_render_s=round(t_first, 2),
                second_render_s=round(t_second, 2), clay_render_s=(round(t_clay, 2) if t_clay else None),
                gpu_busy_percent=gpu_busy, triangles=int(rm.triangle_count),
                rocks=(rocks['count'] if rocks else 0), camera=[round(v, 2) for v in pos],
                levels=[(l['role'], l['cell']) for l in st['levels']], samples=args.samples, exposure=exposure)


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='toroweap,lauterbrunnen,sand_dunes,fuji,badlands')
    ap.add_argument('--views', default='aerial,eye')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--no-rocks', action='store_true')
    ap.add_argument('--clay', action='store_true', help='grey clay instead of the palette (the fixture against the rig)')
    # the rig's +0.5 makes 0.18 clay readable; on real albedos it pushes sunlit ground into AgX's shoulder (pale,
    # washed-out colour; measured 11-08 on Toroweap, Lauterbrunnen and the dunes at +0.5, -0.5 and -1.0): textured
    # views are exposed one stop lower, like a photograph of the place
    ap.add_argument('--exposure', type=float, default=-0.5,
                    help="the textured views' exposure (default -0.5; the clay keeps the rig's +0.5)")
    ap.add_argument('--debug', default=None, help="'weights' or 'albedo': the material's debug output, unlit")
    ap.add_argument('--time-clay', action='store_true', help='also time the same frame in clay (the material cost)')
    ap.add_argument('--mesh-res', type=int, default=1000,
                    help="vertices per side a level is drawn at (1000: stride 1, like the 8 m clay; package 5's "
                         "default 512: stride 2 on 1000-cell levels, about 3 M triangles)")
    ap.add_argument('--tag', default='')
    ap.add_argument('--sky-cache', default=None)
    a = ap.parse_args(argv)
    cache_root = a.sky_cache or tempfile.mkdtemp(prefix='surfacing_sky_')
    for short in [s for s in a.only.split(',') if s]:
        name = SHORT.get(short, short)
        recs = {}
        for v in a.views.split(','):
            recs[v] = render_one(name, v, a, cache_root)
        tag = f'_{a.tag}' if a.tag else ''
        rp = PL.OUT / f'{name}{"_clay" if a.clay else ""}{tag}_record.json'
        old = json.loads(rp.read_text()) if rp.exists() else {}
        old.update(recs)
        rp.write_text(json.dumps(old, indent=1))
    if not a.sky_cache:
        shutil.rmtree(cache_root, ignore_errors=True)
    print('[places] done', flush=True)


if __name__ == '__main__':
    main()
