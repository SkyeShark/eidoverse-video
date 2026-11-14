"""The mesh and API package's acceptance in Blender (design section 11, package 5).

    bash run_blender.sh blender/tests/terrain/mesh_api/test_api_blender.py [--parts synthetic,place,api,cracks]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

Parts
  synthetic  the ring mesh of nested levels at odd offsets (strides 1, 2, 4, cores) as a Blender object: its
             polygons are the RingMesh triangles one for one, every vertex where it was written, and straight-down
             ray casts (mathutils BVH on the object) at 2,000 points across rings and seams land within 1e-4 m of
             height_at
  place      real_place Lauterbrunnen with a hero window at the reference's eye spot (seven levels): the Blender
             mesh's open edges are its outer border only and it has no T-junctions; 2,000 ray casts across rings
             and seams against height_at (float32 vertices at kilometre heights: within 1e-4 m plus four float32
             steps of the coordinates there); the triangle budget
  api        unpacking, terrain_height_at after the fact (from the object alone), save / load, the errors naming
             the nearest valid name (recipe, knob, keyword, quality, mask, flatten key), a focus outside the tile,
             recipes() and describe()
  cracks     emissive renders: the terrain black, a magenta plane below the whole outermost window, the world green;
             straight-down views over every seam's corners and middles and 45-degree views along its steepest
             stretch; no magenta pixel may show (a crack), and no green one (a view the terrain does not fill
             proves nothing)
Results: out/mesh_api/test_api_blender.json, the crack renders in out/mesh_api/cracks/.
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..')))
sys.path.insert(0, HERE)
from eidoblend.terrain import make_terrain, recipes, describe, terrain_height_at, Terrain  # noqa: E402
from eidoblend.terrain.build import mesh as M  # noqa: E402
import test_mesh as TM  # noqa: E402
from _common import EYE, lauterbrunnen  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'mesh_api'))
rng = np.random.default_rng(11)
RESULTS = {}


def log(*a):
    print('[mesh_api]', *a, flush=True)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_arrays(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_total', lt)
    vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', vi)
    return co.reshape(-1, 3), lt, vi


def bvh(verts, tris, offset):
    """A BVH of the triangles in a frame shifted by `offset` (float64 subtraction, then float32): small local
    coordinates near the offset keep the ray arithmetic's rounding below the tolerance there."""
    v = (verts.astype(np.float64) - np.asarray(offset, np.float64)).astype(np.float32)
    return BVHTree.FromPolygons([tuple(map(float, p)) for p in v], [tuple(map(int, t)) for t in tris])


def raycast(tree, x, y, z_top, offset):
    """Straight-down rays: ((N, 3) world hit points, (N,) face index), NaN / -1 where a ray missed."""
    out = np.full((len(x), 3), np.nan)
    face = np.full(len(x), -1, np.int64)
    ox, oy, oz = offset
    for k in range(len(x)):
        hit = tree.ray_cast(Vector((x[k] - ox, y[k] - oy, z_top[k] - oz)), Vector((0.0, 0.0, -1.0)))
        if hit[0] is not None:
            out[k] = (hit[0].x + ox, hit[0].y + oy, hit[0].z + oz)
            face[k] = hit[2]
    return out, face


def on_triangle(co, tris, face, x, y):
    """z of the vertical through (x, y) on Blender triangle `face`, in float64 from the mesh's own vertices: the
    rendered triangle the ray found, without the float32 rounding of the ray arithmetic."""
    p = co[tris[face]].astype(np.float64)
    a, b, c = p[:, 0], p[:, 1], p[:, 2]
    d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
    l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
    return l1 * a[:, 2] + l2 * b[:, 2] + (1.0 - l1 - l2) * c[:, 2]


def ulp32(v):
    return np.spacing(np.abs(np.asarray(v, np.float32))).astype(np.float64)


def part_synthetic():
    rec = {}
    ok = True
    for label, wins, res, cores in (
            ('stride2_cores_odd_offsets', TM.nested(96, 0.25, 5, [(3, -5), (-1, 2), (5, 5), (-7, 1)]), 48, True),
            ('stride1', TM.nested(64, 0.5, 4, [(1, -1), (-2, 3)]), 64, False),
            ('stride4_cores_odd_offsets', TM.nested(128, 0.25, 3, [(5, -3), (-1, 7)]), 32, True)):
        fresh()
        hs = TM.level_arrays(wins, TM.surface)
        rm = M.build_rings(wins, hs, attributes={'sx': TM.level_arrays(wins, lambda X, Y: X)}, cores=cores,
                           mesh_res=res)
        obj = M.make_object(rm, label)
        co, lt, vi = mesh_arrays(obj)
        same_tris = bool(np.all(lt == 3)) and len(lt) == rm.triangle_count and bool(
            np.array_equal(vi.reshape(-1, 3), rm.tris))
        same_verts = bool(np.array_equal(co, rm.verts))
        x, y = TM.seam_points(rm, 2000)
        tris_b = vi.reshape(-1, 3)[:rm.terrain_triangles]
        tree = bvh(co, tris_b, (0.0, 0.0, 0.0))
        hit, face = raycast(tree, x, y, rm.height_at(x, y) + 5.0, (0.0, 0.0, 0.0))
        miss = int((face < 0).sum())
        ok_ = face >= 0
        err = float(np.abs(hit[ok_, 2] - rm.height_at(hit[ok_, 0], hit[ok_, 1])).max())
        good = same_tris and same_verts and miss == 0 and err <= 1e-4
        ok &= good
        rec[label] = dict(triangles=rm.triangle_count, polygons_are_the_triangles=same_tris,
                          vertices_as_written=same_verts, rays=len(x), misses=miss, max_err_m=err, pass_=good)
        log(f'synthetic {label}: {"PASS" if good else "FAIL"} {rm.triangle_count} tris, polygons = triangles '
            f'{same_tris}, vertices as written {same_verts}, {len(x)} rays, {miss} misses, max |ray - height_at| '
            f'{err:.2e} m')
    RESULTS['synthetic'] = rec
    return ok


def seam_and_ring_points(t, n):
    """n points over the terrain: a quarter uniform over the main tile, a quarter over the hero levels, the rest
    within a vertex spacing of a ring border (every ring, cores included) or of its corners."""
    rm = t.ring
    main = t.main
    k = n // 4
    xs = [rng.uniform(main.x0, main.x1, k)]
    ys = [rng.uniform(main.y0, main.y1, k)]
    fin = t.levels[-1]
    hero = t.levels[_first_hero(t)] if _first_hero(t) is not None else main
    xs.append(rng.uniform(hero.x0, hero.x1, k))
    ys.append(rng.uniform(hero.y0, hero.y1, k))
    rings = rm.rings[1:]
    m = n - 2 * k
    for q in range(m):
        r = rings[q % len(rings)]
        sp = r.spec.sp * rm.unit
        x0, x1, y0, y1 = r.xm[0], r.xm[-1], r.ym[0], r.ym[-1]
        if q % 3 == 2:                                  # a corner
            px, py = (x0, x1)[rng.integers(2)], (y0, y1)[rng.integers(2)]
        else:
            s = rng.integers(4)
            tt = rng.uniform(0, 1)
            px = [x0, x1, x0 + tt * (x1 - x0), x0 + tt * (x1 - x0)][s]
            py = [y0 + tt * (y1 - y0), y0 + tt * (y1 - y0), y0, y1][s]
        xs.append([px + rng.uniform(-2 * sp, 2 * sp)])
        ys.append([py + rng.uniform(-2 * sp, 2 * sp)])
    del fin
    return np.concatenate(xs), np.concatenate(ys)


def _first_hero(t):
    for lv in t.levels:
        if lv.role == 'hero':
            return lv.index
    return None


def open_edge_check(co, tris, n_border_expected, bounds):
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e.sort(axis=1)
    key = e[:, 0].astype(np.int64) * len(co) + e[:, 1]
    uk, cnt = np.unique(key, return_counts=True)
    one = uk[cnt == 1]
    a, b = one // len(co), one % len(co)
    xmin, ymin, xmax, ymax = bounds
    on = lambda v: (np.isclose(co[v, 0], xmin) | np.isclose(co[v, 0], xmax) | np.isclose(co[v, 1], ymin) |
                    np.isclose(co[v, 1], ymax))
    return int(len(one)), bool(np.all(on(a) & on(b))), int(np.sum(cnt > 2))


def part_place():
    fresh()
    t0 = time.perf_counter()
    recipe, off = lauterbrunnen()
    t = make_terrain(recipe, params={'dem': 'lauterbrunnen'}, focus=EYE, palette=None, dress=False, seed=1,
                     name='lauterbrunnen')
    gen_s = time.perf_counter() - t0
    rm = t.ring
    co, lt, vi = mesh_arrays(t.obj)
    tris = vi.reshape(-1, 3)[:rm.terrain_triangles]
    n_open, border_only, over_shared = open_edge_check(co[:rm.skirt['first_vertex']], tris,
                                                       None, rm.bounds())
    r0 = rm.rings[0]
    perim = 2 * (len(r0.xs) - 1) + 2 * (len(r0.ys) - 1)
    tj = rm.t_junctions()
    same = bool(np.array_equal(co, rm.verts)) and bool(np.array_equal(vi.reshape(-1, 3), rm.tris))
    # ray casts in a frame centred on the eye (float64 offset)
    x, y = seam_and_ring_points(t, 2000)
    frame = (EYE[0], EYE[1], float(t.height_at(*EYE)))          # the BVH's local frame, centred on the eye
    tree = bvh(co, tris, frame)
    hit, face = raycast(tree, x, y, t.height_at(x, y) + 5.0, frame)
    miss = int((face < 0).sum())
    good_ = face >= 0
    # the design's test, exact: z on the Blender triangle each ray hit, in float64 at the hit's (x, y) (which the
    # BVH found inside that triangle), against height_at there
    hx, hy, hz = hit[good_, 0], hit[good_, 1], hit[good_, 2]
    z_tri = on_triangle(co, tris, face[good_], hx, hy)
    exact = np.abs(z_tri - t.height_at(hx, hy))
    rays_on_far_triangle = int(np.sum(exact > 1e-4))
    err = np.abs(hz - t.height_at(hx, hy))
    # what float32 allows away from the eye: the BVH holds the vertices shifted to the eye's frame and rounded to
    # float32 there (half a step of the local coordinate), which a slope multiplies
    nz = np.abs(t.normal_at(hx, hy, smooth=False)[:, 2])
    grad = np.sqrt(np.maximum(1.0 / np.maximum(nz, 1e-6) ** 2 - 1.0, 0.0))
    local = np.maximum.reduce([np.abs(hx - frame[0]), np.abs(hy - frame[1]), np.abs(hz - frame[2])])
    tol = 1e-4 + 2.0 * ulp32(local) * (1.0 + grad)
    near = np.hypot(hx - EYE[0], hy - EYE[1]) < 1000.0
    within = bool(np.all(err <= tol))
    rec = dict(generate_s=round(gen_s, 1), seconds=t.info['seconds'], levels=[str(lv) for lv in t.levels],
               rings=[s.as_list() for s in rm.specs], triangles=rm.triangle_count,
               terrain_triangles=rm.terrain_triangles, vertices=int(len(rm.verts)),
               polygons_are_the_triangles=same, open_edges=n_open, open_edges_expected=perim,
               open_edges_on_border=border_only, edges_shared_by_3plus=over_shared, t_junctions=tj,
               rays=int(len(x)), misses=miss, max_err_on_hit_triangle_m=float(exact.max()),
               rays_over_0p1mm_on_hit_triangle=rays_on_far_triangle,
               float32_ray_max_err_m=float(err.max()), float32_ray_max_err_within_1km_of_eye_m=float(err[near].max()),
               rays_within_1km=int(near.sum()), float32_ray_err_over_tolerance=float((err / tol).max()),
               within_tolerance=within, budget_ok=rm.triangle_count <= 3.5e6,
               skipped_stages=t.info['skipped_stages'], stages_switched_off=off)
    good = (same and n_open == perim and border_only and over_shared == 0 and tj == 0 and miss == 0 and within
            and float(exact.max()) <= 1e-4 and rec['budget_ok'])
    rec['pass_'] = bool(good)
    RESULTS['place'] = rec
    log(f'place: {"PASS" if good else "FAIL"} {rm.triangle_count:,} triangles ({rm.terrain_triangles:,} terrain), '
        f'open edges {n_open}/{perim} on border {border_only}, 3+-shared edges {over_shared}, t-junctions {tj}, '
        f'{len(x)} rays ({miss} misses): max |z on the hit triangle - height_at| {exact.max():.2e} m; the float32 '
        f'ray hits themselves {err.max():.2e} m ({err[near].max():.2e} m within 1 km of the eye), worst / float32 '
        f'tolerance {(err / tol).max():.2f}; made in {gen_s:.1f} s')
    return good, t


def expect_error(fn, *words):
    try:
        fn()
    except Exception as e:
        msg = f'{type(e).__name__}: {e}'
        return all(w in msg for w in words), msg
    return False, 'no error raised'


def part_api(t):
    rec = {}
    ok = True
    obj, height_at, masks = t
    rec['unpacking'] = bool(obj is t.obj and callable(height_at) and 'slope' in masks)
    x = rng.uniform(t.main.x0, t.main.x1, 1000)
    y = rng.uniform(t.main.y0, t.main.y1, 1000)
    h2 = terrain_height_at(obj)
    rec['terrain_height_at_max_diff_m'] = float(np.abs(h2(x, y) - height_at(x, y)).max())
    rec['scalar_height_is_float'] = isinstance(height_at(100.0, -200.0), float)
    s = t.mask('slope').at(x, y)
    rec['mask_at_shape_ok'] = bool(s.shape == x.shape and np.all(np.isfinite(s)))
    rec['masks'] = masks.names()
    path = os.path.join(OUT, 'saved', 'lauterbrunnen')
    t.save(path)
    rec['saved_mb'] = round(os.path.getsize(path + '.npz') / 1e6, 1)
    t2 = Terrain.load(path, build=False)
    rec['save_load_max_diff_m'] = float(np.abs(t2.height_at(x, y) - height_at(x, y)).max())
    for ext in ('.npz', '.json'):                         # a film terrain's file is hundreds of MB: not kept
        os.remove(path + ext)
    vp = t.viewpoint((-382.0, -3558.0), 5000.0, prefer='low')
    rec['viewpoint'] = dict(eye=vp.eye, heading_deg=vp.heading_deg, pitch_deg=vp.pitch_deg,
                            clearance_m=vp.clearance_m)
    checks = {
        'unknown_recipe': expect_error(lambda: make_terrain('real_plcae'), 'real_place'),
        'unknown_knob': expect_error(lambda: make_terrain('real_place', params={'dme': 'lauterbrunnen'}), 'dem'),
        'unknown_keyword': expect_error(lambda: make_terrain('real_place', focsu=(0, 0)), 'focus'),
        'unknown_quality': expect_error(lambda: make_terrain('real_place', quality='flim'), 'film'),
        'unknown_mask': expect_error(lambda: t.mask('slpoe'), 'slope'),
        'unknown_dem': expect_error(lambda: make_terrain('real_place', params={'dem': 'lauterbrunen'}),
                                    'lauterbrunnen'),
        'unknown_flatten_key': expect_error(lambda: make_terrain('real_place', flatten=[{'at': (0, 0), 'raduis': 9}]),
                                            'radius'),
        'focus_outside': expect_error(lambda: make_terrain('real_place', focus=(9000.0, 0.0)), 'outside'),
        'no_recipe': expect_error(lambda: make_terrain(), 'real_place'),
    }
    for k, (good, msg) in checks.items():
        rec[k] = dict(ok=good, message=msg[:300])
        ok &= good
        log(f'api {k}: {"PASS" if good else "FAIL"} -> {msg[:160]}')
    rec['recipes'] = recipes()
    rec['describe'] = describe('real_place', log=None)
    good = (rec['unpacking'] and rec['terrain_height_at_max_diff_m'] == 0.0 and rec['scalar_height_is_float']
            and rec['mask_at_shape_ok'] and rec['save_load_max_diff_m'] == 0.0)
    ok &= good
    rec['pass_'] = bool(ok)
    RESULTS['api'] = rec
    log(f'api: {"PASS" if ok else "FAIL"} unpacking {rec["unpacking"]}, terrain_height_at diff '
        f'{rec["terrain_height_at_max_diff_m"]}, save/load diff {rec["save_load_max_diff_m"]}, masks '
        f'{len(rec["masks"])}, viewpoint {rec["viewpoint"]}')
    return ok


def emission(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*rgb, 1.0)
    e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs['Emission'], o.inputs['Surface'])
    return m


def part_cracks(t):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 16
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'PNG'
    # the world green: a view the terrain does not fill shows it, so a view that missed the seam cannot pass
    world = bpy.data.worlds.new('green')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 1, 0, 1)
    sc.world = world
    obj = t.obj
    obj.data.materials.clear()
    obj.data.materials.append(emission('ink', (0.0, 0.0, 0.0), 0.0))
    for o in list(sc.objects):
        if o is not obj:
            bpy.data.objects.remove(o, do_unlink=True)
    zmin = float(t.ring.verts[:, 2].min())
    outer = t.levels[0]                                  # the backdrop under the whole outermost window
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(outer.centre[0], outer.centre[1], zmin - 100.0))
    back = bpy.context.active_object
    back.scale = (outer.side * 1.25, outer.side * 1.25, 1.0)
    back.data.materials.append(emission('magenta', (1.0, 0.0, 1.0), 1.0))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    d = os.path.join(OUT, 'cracks')
    os.makedirs(d, exist_ok=True)
    rm = t.ring
    views = []
    for k, r in enumerate(rm.rings[1:], 1):
        sp = r.spec.sp * rm.unit                      # this ring's vertex spacing (the finer side of the seam)
        x0, x1, y0, y1 = r.xm[0], r.xm[-1], r.ym[0], r.ym[-1]
        for tag, px, py in (('sw', x0, y0), ('se', x1, y0), ('ne', x1, y1), ('nw', x0, y1),
                            ('s', (x0 + x1) / 2, y0), ('n', (x0 + x1) / 2, y1)):
            views.append((f'seam{k}_{tag}_top', 'top', px, py, 30 * sp))
        # 45 degrees along the steepest stretch of the seam
        tt = np.linspace(0, 1, 400)
        cand = [(x0 + tt * (x1 - x0), np.full_like(tt, y0)), (x0 + tt * (x1 - x0), np.full_like(tt, y1)),
                (np.full_like(tt, x0), y0 + tt * (y1 - y0)), (np.full_like(tt, x1), y0 + tt * (y1 - y0))]
        best = None
        for (cx, cy) in cand:
            nz = t.normal_at(cx, cy, smooth=False)[:, 2]
            i = int(np.argmin(nz))
            if best is None or nz[i] < best[0]:
                best = (nz[i], cx[i], cy[i])
        views.append((f'seam{k}_steepest_oblique', 'oblique', best[1], best[2], 30 * sp))
    rec = {}
    total = 0
    unframed = 0
    for label, kind, px, py, span in views:
        gz = float(t.height_at(px, py))
        if kind == 'top':
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = span
            cam.location = (px, py, float(t.ring.verts[:, 2].max()) + 50.0)
            cam.rotation_euler = (0.0, 0.0, 0.0)
            cam.data.clip_start, cam.data.clip_end = 1.0, 1.0e5
        else:
            cam.data.type = 'PERSP'
            cam.data.lens = 35.0
            n = t.normal_at(px, py, smooth=False)
            hd = math.atan2(-n[1], -n[0])                  # look into the slope, from its downhill side
            dist = span
            cam.location = (px - math.cos(hd) * dist * 0.7, py - math.sin(hd) * dist * 0.7, gz + dist * 0.7)
            dvec = Vector((px, py, gz)) - Vector(cam.location)
            cam.rotation_euler = dvec.to_track_quat('-Z', 'Y').to_euler()
            cam.data.clip_start, cam.data.clip_end = 0.05, 1.0e5
        sc.render.filepath = os.path.join(d, label + '.png')
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath, check_existing=False)
        px_ = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(px_)
        px_ = px_.reshape(-1, 4)
        mag = int(np.sum((px_[:, 0] - px_[:, 1] > 0.1) & (px_[:, 2] - px_[:, 1] > 0.1)))
        sky = int(np.sum((px_[:, 1] - px_[:, 0] > 0.1) & (px_[:, 1] - px_[:, 2] > 0.1)))
        bpy.data.images.remove(img)
        rec[label] = dict(backdrop_pixels=mag, world_pixels=sky)
        total += mag
        unframed += sky
        log(f'cracks {label}: {mag} backdrop pixels, {sky} world pixels')
    good = total == 0 and unframed == 0
    RESULTS['cracks'] = dict(views=rec, total_backdrop_pixels=total, total_world_pixels=unframed, pass_=good,
                             folder=d)
    return good


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parts = 'synthetic,place,api,cracks'
    if '--parts' in argv:
        parts = argv[argv.index('--parts') + 1]
    parts = parts.split(',')
    os.makedirs(OUT, exist_ok=True)
    ok = True
    t = None
    if 'synthetic' in parts:
        ok &= part_synthetic()
    if any(p in parts for p in ('place', 'api', 'cracks')):
        good, t = part_place()
        ok &= good
    if 'api' in parts:
        ok &= part_api(t)
    if 'cracks' in parts:
        ok &= part_cracks(t)
    RESULTS['pass'] = bool(ok)
    path = os.path.join(OUT, 'test_api_blender.json')
    old = {}
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    old.update(RESULTS)
    with open(path, 'w') as f:
        json.dump(old, f, indent=1, default=str)
    log('ALL PASS' if ok else 'FAILURES', '->', path)


main()
