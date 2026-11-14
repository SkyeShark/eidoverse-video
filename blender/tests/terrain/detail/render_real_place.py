"""Eye-level renders of real_place Lauterbrunnen's hero levels, with and without the detail stages (the package's
done-when: hero-level eye views show rills, ribs and talus, not clay):

    bash run_blender.sh blender/tests/terrain/detail/render_real_place.py [--variants upsampled,detail,full] [--tag r1]
        [--views eye,wall,slope,ground]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The terrain is the mesh-and-API package's (focus: the reference's eye spot and the robot's spot 14 m along the view),
made by make_terrain with
    upsampled   the DEM stage only (the hero levels are the DEM upsampled: clay at eye level)
    detail      the DEM, then this package's rock breakup and hydraulic pass on the hero levels
    full        the registered recipe: fluvial refinement, talus (package 3), rock breakup, hydraulic (package 12)
Views, all from 1.7 m (the reference rig's eye height), make_sky daylight with the reference rig's settings:
    eye     the reference's own eye camera (renders/lauterbrunnen_views.json): south up the valley
    wall    from the eye spot west to the foot of the west wall, 400-500 m away (1 and 2 m cells)
    slope   from the eye spot east across the floor to the forested slope below Wengen (1 and 2 m cells)
    ground  the ground 4-40 m ahead of the eye, looking down 12 degrees (the 0.5 m level)
each in grey clay (the reference rig's albedo 0.18) and in the alpine palette with its rocks.
Writes out/detail/renders/<tag>_<variant>_<view>_<clay|alpine>.png and <tag>_renders.json.
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
REF = os.path.normpath(os.path.join(HERE, '..', 'reference'))
sys.path.insert(0, BLENDER)
sys.path.insert(0, REF)
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.terrain import make_terrain  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
import lauterbrunnen_truth as LT  # noqa: E402
from run_real_place import recipe_for  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'detail', 'renders'))


def log(*a):
    print('[detail.render]', *a, flush=True)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    get = (lambda k, d: a[a.index(k) + 1] if k in a else d)
    recipe = get('--recipe', 'real_place')
    dv = 'upsampled,detail,full' if recipe == 'real_place' else 'nodetail,full'
    dw = 'eye,wall,slope,ground' if recipe == 'real_place' else 'down,up,ground'
    return dict(variants=get('--variants', dv).split(','), tag=get('--tag', 'r1'), recipe=recipe,
                views=get('--views', dw).split(','), focus=get('--focus', '850,-2350'))


def hillside_views(t, fx, fy):
    """fluvial_range: from 1.7 m on the hillside at the focus, looking down the slope, up it, and at the ground."""
    d = 6.0
    gx = (float(t.height_at(fx + d, fy)) - float(t.height_at(fx - d, fy))) / (2 * d)
    gy = (float(t.height_at(fx, fy + d)) - float(t.height_at(fx, fy - d))) / (2 * d)
    L = max(math.hypot(gx, gy), 1e-9)
    ux, uy = -gx / L, -gy / L                                       # downhill
    ez = float(t.height_at(fx, fy)) + RR.EYE_HEIGHT
    out = {}
    for name, sgn, dist, lens in (('down', 1.0, 300.0, 35.0), ('up', -1.0, 200.0, 35.0)):
        tx, ty = fx + sgn * dist * ux, fy + sgn * dist * uy
        out[name] = ((fx, fy, ez), (tx, ty, float(t.height_at(tx, ty)) + 1.0), lens)
    tx, ty = fx + 14.0 * ux, fy + 14.0 * uy
    out['ground'] = ((fx, fy, ez), (tx, ty, float(t.height_at(tx, ty))), 28.0)
    return out


def views(t, eye):
    """name -> (camera xyz, target xyz, lens): the reference's eye camera, and three looks from the same spot."""
    ex, ey = eye['camera'][:2]
    ez = float(t.height_at(ex, ey)) + RR.EYE_HEIGHT
    out = {'eye': ((ex, ey, ez), tuple(eye['target']), eye['lens_mm'])}
    for name, (tx, ty), lens, dz in (('wall', (40.0, 1540.0), 35.0, 60.0), ('slope', (980.0, 1560.0), 35.0, 40.0)):
        out[name] = ((ex, ey, ez), (tx, ty, float(t.height_at(tx, ty)) + dz), lens)
    # the ground ahead: along the reference view, 12 degrees down
    tx, ty = eye['target'][:2]
    L = math.hypot(tx - ex, ty - ey)
    ux, uy = (tx - ex) / L, (ty - ey) / L
    gx, gy = ex + 18.0 * ux, ey + 18.0 * uy
    out['ground'] = ((ex, ey, ez), (gx, gy, ez - 18.0 * math.tan(math.radians(12.0))), 28.0)
    return out


def render(sc, cam, path, sky_root, sun=None):
    d = cam.matrix_world.col[2][:3]
    hd = math.atan2(-d[1], -d[0]) + math.radians(RR.SUN_LEFT_DEG)
    cache = os.path.join(sky_root, os.path.basename(path))
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option((math.cos(hd), math.sin(hd))), sun=sun)
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    shutil.rmtree(cache, ignore_errors=True)
    return sky, round(time.time() - t0, 1)


def main():
    A = args()
    os.makedirs(OUT, exist_ok=True)
    if A['recipe'] == 'real_place':
        pts, eye = LT.focus()
        params = {'dem': 'lauterbrunnen'}
    else:
        fx, fy = (float(v) for v in A['focus'].split(','))
        pts, eye, params = [(fx, fy)], None, {}
    rec = {}
    sky_root = tempfile.mkdtemp(prefix='detail_sky_')
    for variant in A['variants']:
        sc = RR.new_scene((960, 540), 16, RR.EXPOSURE)
        t0 = time.time()
        t = make_terrain(recipe_for(A['recipe'], variant, {}, {}), params=params, focus=pts, seed=1,
                         name=f'{A["recipe"]}_{variant}', dress=True)
        rec[variant] = dict(seconds=round(time.time() - t0, 1), triangles=t.ring.triangle_count,
                            rocks=(t.rocks or {}).get('count'), skipped=t.info.get('skipped_stages'),
                            timing=t.info['seconds'])
        log(variant, rec[variant])
        alpine = list(t.obj.data.materials)
        clay = S.clay_material(f'clay_{variant}')
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_start, cam.data.clip_end = 0.05, 60000.0
        sun = None
        vs = views(t, eye) if A['recipe'] == 'real_place' else hillside_views(t, *pts[0])
        for vname, (c, tg, lens) in vs.items():
            if vname not in A['views']:
                continue
            RR.place_camera(cam, c, tg)
            cam.data.lens = lens
            for look in ('clay', 'alpine'):
                t.obj.data.materials.clear()
                for m in ([clay] if look == 'clay' else alpine):
                    t.obj.data.materials.append(m)
                if t.rocks:
                    t.rocks['collection'].hide_render = (look == 'clay')
                p = os.path.join(OUT, f"{A['tag']}_{variant}_{vname}_{look}.png")
                sky, sec = render(sc, cam, p, sky_root, sun)
                sun = sun or getattr(sky, 'sun', None)
                rec[variant][f'{vname}_{look}'] = dict(path=p, camera=list(c), target=list(tg), lens=lens, seconds=sec)
                log(p, sec, 's')
        for ob in list(bpy.data.objects):                       # the next variant starts from an empty file
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.orphans_purge(do_recursive=True)
    shutil.rmtree(sky_root, ignore_errors=True)
    with open(os.path.join(OUT, f"{A['tag']}_renders.json"), 'w') as f:
        json.dump(rec, f, indent=1, default=str)


main()
