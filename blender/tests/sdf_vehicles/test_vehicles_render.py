"""The four SDF vehicles built by make(), each on a ground plane under a sun and the engine's city HDRI, seen from a
3/4 front view, rendered in EEVEE beside the engine's own raymarch (its shade(), sampleEnvMap bound to the same HDRI)
from the same camera.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf_vehicles/test_vehicles_render.py -- [vehicles=modern,cyber,sleek,jet] \
        [shading=parts|baked] [quality=high] [views=az,el,dist;az,el,dist...] [lens=50] [tag=] [w=960 h=540
        samples=16] [ref=1]

Writes out/veh_<kind><tag>_eevee.png, _ref.png and _sheet.png (EEVEE left, the engine's march right); further views
(views=: azimuth from the front, elevation, distance in bounding diagonals) add _v1, _v2 ... PASS lines:
the mesh is closed, its lowest point sits on the ground (the jet flies 1.2 m up, as the engine's check scenes flew
it), the bounds hold the shape (nothing clipped), every material id has its faces, the silhouette matches the
engine's march (IoU of camera coverage), the render exists.
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402
import engine_march as EM  # noqa: E402  (tests/sdf, on sys.path through _vcommon)

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402
from eidoblend.sdf.vehicles import parts as P  # noqa: E402

A = V.args()
KINDS = {'modern': 'stylized_modern_sedan', 'cyber': 'stylized_cyberpunk_sedan', 'sleek': 'stylized_sci_fi_sleek_car',
         'jet': 'stylized_fighter_jet'}
WANT = A.get('vehicles', 'modern,cyber,sleek,jet').split(',')
W, H = int(A.get('w', '960')), int(A.get('h', '540'))
SAMPLES = int(A.get('samples', '16'))
SHADING = A.get('shading', 'parts')
TAG = A.get('tag', '') + ('' if SHADING == 'parts' else '_baked')
REF = A.get('ref', '1') == '1'
VIEW_LIST = [tuple(float(x) for x in v.split(',')) for v in A['views'].split(';')] if 'views' in A else None
LENS = float(A.get('lens', '50'))
HOVER = {'jet': 1.2}
VIEWS = {'modern': (35, 12, 1.0), 'cyber': (35, 12, 1.0), 'sleek': (35, 12, 1.0), 'jet': (40, 22, 0.95)}

for kind in WANT:
    name = KINDS[kind]
    ex = sdf.EXAMPLES[name]
    V.purge()
    sc = V.stage(W, H, SAMPLES)
    t0 = time.perf_counter()
    over = {'cache_dir': V.CACHE, 'name': f'veh_{kind}', 'shading': SHADING, 'log': None}
    if 'quality' in A:
        over['quality'] = A['quality']
    if 'voxel' in A:
        over['voxel'] = float(A['voxel'])
    car = ex.make(**over)
    car.place_on_ground(0.0)
    car.object.location.z += HOVER.get(kind, 0.0)
    dt = time.perf_counter() - t0
    st = car.stats
    print(f'[render] {kind}: {st.get("quads")} quads, voxel {car.voxel * 1000:.2f} mm, carrier {st.get("carrier")}, '
          f'built in {dt:.1f} s', flush=True)
    c = car.contour
    frac, bad, tot = V.closed_fraction(c)
    V.check(f'{kind}: closed mesh', frac > 0.999, f'{bad} of {tot} edges not shared by exactly two quads')
    bpy.context.view_layer.update()
    co = np.empty(len(car.object.data.vertices) * 3, np.float32)
    car.object.data.vertices.foreach_get('co', co)
    mw = np.array(car.object.matrix_world)
    zmin = float((co.reshape(-1, 3) @ mw[2, :3] + mw[2, 3]).min())
    V.check(f'{kind}: lowest point on the ground', abs(zmin - HOVER.get(kind, 0.0)) < 1e-4,
            f'lowest z = {zmin * 1000:.3f} mm (want {HOVER.get(kind, 0.0) * 1000:.0f})')
    rep = car.bounds_report()
    V.check(f'{kind}: bounds hold the shape', not rep['clipped'],
            f'mesh {rep["mesh_min"]} .. {rep["mesh_max"]} in bounds {rep["bounds_min"]} .. {rep["bounds_max"]}; '
            f'bounds.min.y {rep["bounds_min"][1]} vs the lowest point {rep["mesh_min"][1]}')
    if SHADING == 'parts':
        fpm = V.faces_per_material(car.object)
        parts = sorted(set(P.IDS[kind].values()) - ({'rim'} if kind == 'cyber' else set()))
        missing = [p for p in parts if fpm.get(p, 0) == 0]
        V.check(f'{kind}: every part has faces', not missing,
                f'{ {k: v for k, v in fpm.items() if v} }' + (f' missing {missing}' if missing else ''))
    if REF:
        sdf.register_sdf_helper(sc)                   # binds the HDRI as the engine march's sampleEnvMap
    for vi, view in enumerate(VIEW_LIST or [VIEWS[kind]]):
        sfx = TAG + ('' if vi == 0 else f'_v{vi}')
        cam = V.three_quarter(car.object, *view, lens=LENS, name=f'cam{vi}')
        bpy.context.scene.camera = cam
        eevee = os.path.join(V.OUT, f'veh_{kind}{sfx}_eevee.png')
        t1 = time.perf_counter()
        ok = V.render(eevee)
        V.check(f'{kind}{sfx}: EEVEE render', ok, f'{eevee} in {time.perf_counter() - t1:.1f} s')
        if REF:
            ref = EM.march(car, cam, W, H, samples=4)
            refp = V.save_linear_png(os.path.join(V.OUT, f'veh_{kind}{sfx}_ref.png'), ref)
            iou, mm, mr = V.silhouette_iou(car, cam, W // 4, H // 4)
            V.check(f'{kind}{sfx}: silhouette matches the engine march', iou > 0.93,
                    f'IoU {iou:.3f} at {W // 4}x{H // 4} (mesh {mm * 100:.1f}%, march {mr * 100:.1f}% of the frame)')
            V.sheet([eevee, refp], os.path.join(V.OUT, f'veh_{kind}{sfx}_sheet.png'), cols=2)
    V.free_images()

V.summary()
