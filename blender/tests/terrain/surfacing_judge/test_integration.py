"""make_terrain with its surface and its plants, end to end (SURFACING_DESIGN.md 5.4, package 5, item 3), in Blender
as a GPU job (the bake's kernels, a shader compile, one small render):

    bash run_blender.sh blender/tests/terrain/surfacing_judge/test_integration.py [--only meadow,canopy_and_far]
    (on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

1. make_terrain('meadow', plants='auto', cameras=[an eye camera]) with the defaults surface='auto' and
   mask_attributes=True: the surface bake is t.surface and holds the plan's cover; the material is the per-texel one
   reading that bake; the plants are planned around the focus and instanced; no plant's crown stands within 1.5 m
   of the camera; the eido_<mask> attributes are on the mesh; a frame renders with no failed shader.
2. save and load: Terrain.save writes the spots beside the .npz, Terrain.load(build=True) reads them back (the same
   counts), its bake is a cache hit and it builds the same material.
3. a palette with a canopy layer and plants=None (Lauterbrunnen, real_place, the judge's saved terrain): the bake
   still holds canopy_expected (the ecotope's expected cover), and the forest layer reads it.
4. cameras=: the far material (slot 1) only on the rings lying beyond 1.5 D0 of every camera; with no cameras, none.
5. mask_attributes=False: of the eido_ attributes only eido_level stays.
6. terrain_surface(obj) on the .blend saved and reopened: every atlas found where it was; after save_images and a
   move, the atlases relinked from the folder given.
Prints [PASS] / [FAIL] per check and a summary line; writes out/surfacing_judge/integration/ (git-ignored).
"""
import json
import math
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
for _p in (BLENDER_DIR, TN):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.terrain import api as A  # noqa: E402
from eidoblend.terrain import make_terrain, terrain_surface  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

OUT = os.path.join(TN, 'out', 'surfacing_judge', 'integration')
JUDGE_TERRAINS = os.path.join(TN, 'out', 'surfacing_judge', 'terrains')
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f': {detail}' if detail else ''), flush=True)
    return ok


def quiet(*_a, **_k):
    pass


def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 4
    sc.render.resolution_x, sc.render.resolution_y = 480, 270
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    return sc


def eido_attributes(obj):
    return sorted(a.name for a in obj.data.attributes if a.name.startswith('eido_'))


def material_slots(obj):
    me = obj.data
    idx = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', idx)
    return idx


def ring_distance(r, pts):
    """Horizontal metres from each camera point to a ring (its window less its hole), as surfacing.far_rings
    measures it."""
    x0, y0, x1, y1 = r['window']
    dx = np.maximum(np.maximum(x0 - pts[:, 0], pts[:, 0] - x1), 0.0)
    dy = np.maximum(np.maximum(y0 - pts[:, 1], pts[:, 1] - y1), 0.0)
    d = np.hypot(dx, dy)
    if r.get('hole'):
        hx0, hy0, hx1, hy1 = r['hole']
        inside = (pts[:, 0] > hx0) & (pts[:, 0] < hx1) & (pts[:, 1] > hy0) & (pts[:, 1] < hy1)
        dh = np.minimum(np.minimum(pts[:, 0] - hx0, hx1 - pts[:, 0]), np.minimum(pts[:, 1] - hy0, hy1 - pts[:, 1]))
        d = np.where(inside, dh, d)
    return d


# ---------------------------------------------------------------------------------------------- 1, 2, 6 ---

def meadow():
    sc = fresh_scene()
    cam = bpy.data.objects.new('test_cam', bpy.data.cameras.new('test_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    focus = (0.0, -20.0)
    t0 = time.time()
    # the camera's ground point is known before the terrain: an eye camera 1.7 m over z 0 is "near the ground"
    t = make_terrain('meadow', seed=7, focus=focus, plants='auto', cameras=[(focus[0], focus[1], 1.7)],
                     name='meadow_test', log=quiet)
    build_s = time.time() - t0
    sd = t.surface
    check('1 make_terrain: t.surface is the bake', sd is not None and hasattr(sd, 'maps'),
          f"{sd!r}, {build_s:.0f} s ({t.info['seconds']})")
    mat = t.obj.data.materials[0]
    check('1 the material reads the bake', mat.get('eido_surface_key') == str(sd.key) and mat.get('eido_samplers'),
          f"key {str(mat.get('eido_surface_key'))[:10]}, {mat.get('eido_samplers')} samplers, "
          f"far hand-off {mat.get('eido_far_m')} m")
    sp = t.plants
    counts = {n: sp.count(n) for n in sp.names()} if sp is not None else {}
    check('1 plants planned', sp is not None and sum(counts.values()) > 0, f'{counts}')
    check('1 plants instanced', any(t.plant_objects.values()),
          f"{ {k: len(v) for k, v in t.plant_objects.items()} }")
    cov = t.info.get('surface', {}).get('cover_maps') or []
    check("1 the bake holds the plan's cover", t.info['surface'].get('cover') in ('planned', 'cached')
          and 'canopy_expected' in sd.names() and 'shrubs' in sd.names(), f'{cov}')
    near = []
    for n in sp.names():
        e = sp.entry(n)
        a = sp.array(n)
        if not len(a):
            continue
        crown = float(e.get('crown_m', e.get('core_m', 0.0))) * a[:, 4]
        d = np.hypot(a[:, 0] - focus[0], a[:, 1] - focus[1]) - crown
        near.append(float(d.min()))
    check('1 the camera stands clear of every crown', not near or min(near) >= A.STAND_M - 1e-3,
          f'nearest crown edge {min(near) if near else None:.2f} m (stand_m {A.STAND_M})')
    att = eido_attributes(t.obj)
    check('1 the eido_<mask> attributes on the mesh by default', 'eido_slope' in att and 'eido_level' in att,
          f'{len(att)} eido_ attributes')
    # a frame: the camera at eye height, a sun and a plain sky
    gz = float(t.height_at(*focus))
    A.place_camera(A.Viewpoint((focus[0], focus[1], gz + 1.7), (focus[0], focus[1] + 60.0, gz), gz, 0.0, 0.0, 60.0,
                               1.0, 35.0), cam)
    sun = bpy.data.objects.new('test_sun', bpy.data.lights.new('test_sun', 'SUN'))
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(30))
    sc.collection.objects.link(sun)
    w = bpy.data.worlds.new('test_world')
    w.color = (0.4, 0.5, 0.7)
    sc.world = w
    t.bind_sun(sun)
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, 'meadow_eye.png')
    sc.render.filepath = png
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(png)
    px = np.asarray(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[..., :3]
    magenta = float(np.mean((px[..., 0] > 0.9) & (px[..., 1] < 0.1) & (px[..., 2] > 0.9)))
    check('1 a frame renders (no failed shader)', magenta < 0.01 and float(px.std()) > 0.01,
          f'{time.time() - t1:.1f} s, magenta share {magenta:.3f}, spread {float(px.std()):.3f}; {png}')
    # 2. save and load
    snap = os.path.join(OUT, 'meadow_test.npz')
    t.save(snap)
    check('2 Terrain.save writes the spots', os.path.exists(os.path.join(OUT, 'meadow_test.plants.json')))
    surf_key = str(sd.key)
    # 6. the .blend, with copies of the atlases beside it
    blend = os.path.join(OUT, 'meadow_test.blend')
    shipped = os.path.join(OUT, 'meadow_test_surface')
    shutil.rmtree(shipped, ignore_errors=True)
    files = sd.save_images(shipped)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    del t, sd, sp
    sc = fresh_scene()
    t2 = A.Terrain.load(snap, build=True, name='meadow_loaded', dress=True, log=quiet)
    c2 = {n: t2.plants.count(n) for n in t2.plants.names()} if t2.plants is not None else {}
    check('2 Terrain.load reads the spots back', c2 == counts, f'{c2}')
    check("2 the loaded terrain's bake is a cache hit, the same material",
          t2.surface is not None and str(t2.surface.key) == surf_key and t2.info['surface'].get('cache_hit')
          and t2.obj.data.materials[0].get('eido_surface_key') == surf_key,
          f"key {surf_key[:10]}, hit {t2.info['surface'].get('cache_hit')}, plants instanced "
          f"{sum(len(v) for v in t2.plant_objects.values())} objects")
    del t2
    # 6. reopen the .blend
    bpy.ops.wm.open_mainfile(filepath=blend)
    obj = bpy.data.objects['meadow_test']
    rec = terrain_surface(obj)
    ok = rec['images'] and all(os.path.exists(p) for p in rec['images'].values())
    check('6 terrain_surface: every atlas found after reopening', ok, f"{sorted(rec['images'])}")
    moved = os.path.join(OUT, 'meadow_test_moved')
    shutil.rmtree(moved, ignore_errors=True)
    shutil.copytree(shipped, moved)
    for img in A._material_images(obj).values():
        img.filepath = os.path.join(OUT, 'nowhere', os.path.basename(img.filepath))
    rec = terrain_surface(obj, folder=moved)
    ok = rec['images'] and all(os.path.dirname(p) == moved for p in rec['images'].values())
    check('6 terrain_surface relinks moved atlases from the folder given', ok,
          f"{len(rec['images'])} images from {os.path.basename(moved)} ({len(files)} files shipped)")
    shutil.rmtree(moved, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- 3, 4, 5 ---

def canopy_and_far():
    snap = os.path.join(JUDGE_TERRAINS, 'real_place.npz')
    if not os.path.exists(snap):
        check('3 Lauterbrunnen (the judge\'s saved terrain)', False,
              f'{snap} is missing: make it with surfacing_judge/make_terrains.py')
        return
    sc = fresh_scene()
    t = A.Terrain.load(snap, build=False)
    main = t.main
    cx, cy = main.x0 + main.side / 2.0, main.y0 + main.side / 2.0
    cams = [(cx, cy, float(t.height_at(cx, cy)) + 300.0)]
    t.build('lb_test', palette='keep', dress=False, plants=None, cameras=cams, mask_attributes=False, log=quiet)
    sd = t.surface
    has = sd is not None and 'canopy_expected' in sd.names()
    ce = sd.maps(t.main.index).get('canopy_expected') if has else None
    check('3 plants=None: the bake holds canopy_expected (a palette with a canopy layer)',
          has and ce is not None and float(ce.max()) > 0.2 and t.info['surface'].get('cover') == 'expected',
          f"cover {t.info['surface'].get('cover')}, canopy_expected on the main level mean "
          f"{float(ce.mean()) if ce is not None else None:.3f}, max {float(ce.max()) if ce is not None else None:.2f}")
    from eidoblend.terrain.build import palettes as P
    pal = S.resolve(t.info['palette'], t.recipe)
    forest = [L['name'] for L in pal['layers'] if 'canopy_expected' in P.names_in(L['weight'])]
    check('3 the forest layer reads canopy_expected', bool(forest), f'{forest}')
    # 4. the far material by camera
    mat = t.obj.data.materials[0]
    far_m = float(mat['eido_far_m'])
    pts = np.asarray([c[:2] for c in cams], np.float64)
    idx = material_slots(t.obj)
    bad, far, near = [], [], []
    for r in S._ring_table(t.obj):
        d = float(ring_distance(r, pts).min())
        sl = idx[int(r['start']):int(r['start']) + int(r['count'])]
        is_far = bool(len(sl)) and bool((sl == 1).all())
        is_near = bool(len(sl)) and bool((sl == 0).all())
        if d > 1.5 * far_m:
            (far if is_far else bad).append(int(r['ring']))
        else:
            (near if is_near else bad).append(int(r['ring']))
    check('4 cameras=: the far material only on rings beyond 1.5 D0', not bad and len(t.obj.data.materials) == (2 if far
                                                                                                             else 1),
          f'D0 {far_m:.0f} m; far rings {far}, near rings {near}, wrong {bad}')
    att = eido_attributes(t.obj)
    check('5 mask_attributes=False: only eido_level', att == ['eido_level'], f'{att}')
    del t, sd
    sc = fresh_scene()
    t = A.Terrain.load(snap, build=False)
    t.build('lb_nocam', palette='keep', dress=False, plants=None, cameras=None, log=quiet)
    idx = material_slots(t.obj)
    check('4 no cameras: no ring takes the far material', int(idx.max(initial=0)) == 0
          and len(t.obj.data.materials) == 1, f'{len(t.obj.data.materials)} material slot(s)')
    att = eido_attributes(t.obj)
    check('5 mask_attributes default: the masks stay', len(att) > 10, f'{len(att)} eido_ attributes')


def main():
    t0 = time.time()
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
    for fn in (meadow, canopy_and_far):
        if only and fn.__name__ not in only:
            continue
        try:
            fn()
        except Exception as e:                                   # noqa: BLE001 - recorded, the next part runs
            traceback.print_exc()
            check(f'{fn.__name__} ran', False, f'{type(e).__name__}: {e}')
    n_ok = sum(ok for _n, ok in RESULTS)
    print(f'[test_integration] {n_ok} / {len(RESULTS)} checks pass in {time.time() - t0:.0f} s', flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'test_integration.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(results=[dict(check=n, passed=ok) for n, ok in RESULTS], seconds=round(time.time() - t0, 1)),
                  f, indent=1)
    os._exit(0 if n_ok == len(RESULTS) else 1)


main()
