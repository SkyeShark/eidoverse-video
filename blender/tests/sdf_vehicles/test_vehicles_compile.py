"""The four vehicle EXAMPLES as specs: their GLSL compiles and evaluates in Blender's GPU module (dist, grad, the
baked surface(), the engine's raymarch with its shade() from tests/sdf/engine_march.py), the bounds contract holds
(the shape stays inside its
bounds, and bounds.min.y is its lowest point), the material ids on the surface are the ones the part tables map,
create_sdf_object(EXAMPLES[...]) builds (the engine's createSdfObject(EXAMPLES.x) path) and help() lists them.
No render.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf_vehicles/test_vehicles_compile.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402
import engine_march as EM  # noqa: E402  (tests/sdf, on sys.path through _vcommon)

from eidoblend import sdf  # noqa: E402
from eidoblend.sdf.gpu_eval import SdfProgram  # noqa: E402
from eidoblend.sdf.vehicles import parts as P  # noqa: E402
from eidoblend.sdf.vehicles.vehicle import KIND_OF  # noqa: E402

rng = np.random.default_rng(11)
V.check('the vehicle examples loaded', not sdf.EXAMPLE_IMPORT_ERRORS.get('examples_vehicles'),
        sdf.EXAMPLE_IMPORT_ERRORS.get('examples_vehicles', 'ok')[-600:])

for name, kind in KIND_OF.items():
    ex = sdf.EXAMPLES[name]
    t0 = time.perf_counter()
    prog = SdfProgram(map=ex['map'], surface=ex.get('surface'), shade=ex.get('shade'), extra=ex.get('extra', ''),
                      uniforms=ex.get('uniforms'), textures=ex.get('textures'), label=name)
    lo = np.asarray(ex['bounds']['min'], np.float32)
    hi = np.asarray(ex['bounds']['max'], np.float32)
    pts = (lo + rng.random((60000, 3), dtype=np.float32) * (hi - lo)).astype(np.float32)
    d, m = prog.dist(pts)
    inside = float(np.mean(d < 0))
    V.check(f'{name}: dist kernel', np.isfinite(d).mean() > 0.999 and 0.01 < inside < 0.9,
            f'{inside * 100:.1f}% of the bounds inside')
    g = prog.grad(pts[:4000], 0.001)[2]
    V.check(f'{name}: grad kernel', np.isfinite(g).all(), f'|grad| median {np.median(np.linalg.norm(g, axis=1)):.3f}')
    near = pts[np.abs(d) < 0.01][:20000]
    ch = prog.surface_eval(near, project=3, grad_h=0.0005, normal_h=0.0005)
    ids = sorted(set(np.rint(ch['mat']).astype(int).tolist()))
    want = sorted(P.IDS[kind])
    V.check(f'{name}: the surface carries the material ids the part table maps', set(ids) <= set(want),
            f'ids on the surface {ids}; table {want}')
    alb = ch['albedo']
    ok = (np.isfinite(alb).all() and alb.min() >= -1e-4 and alb.max() <= 1.0001 and np.isfinite(ch['emission']).all()
          and ch['roughness'].min() >= 0.0)
    V.check(f'{name}: baked surface() kernel', ok, f'{len(near)} points, albedo mean {alb.mean(axis=0).round(3).tolist()}, '
            f'emission max {ch["emission"].max():.2f}')
    # the raymarch kernel (the engine's shade()), a few pixels from the front
    march = EM.MarchProgram(prog)
    march.values.update({'sdfCameraUniform': (2.5, 1.5, 6.0), 'sdfCamFwd': tuple((-np.array([2.5, 1.0, 6.0]) /
                         np.linalg.norm([2.5, 1.0, 6.0])).tolist()), 'sdfImageSize': (64.0, 36.0),
                         'sdfClipMin': tuple(float(x) for x in lo), 'sdfClipMax': tuple(float(x) for x in hi),
                         'uMaxSteps': 192.0, 'uSurfEps': 0.0005, 'uStepScale': 0.75, 'uMaxDist': 150.0})
    img = march.eval('raymarch', np.zeros((64 * 36, 3), np.float32), width=64)[0]
    V.check(f'{name}: raymarch kernel (shade())', np.isfinite(img).all() and img[:, 3].mean() > 0.05,
            f'coverage {img[:, 3].mean() * 100:.1f}%')
    # the bounds contract: the field is positive on the bounds box (nothing crosses it), and there is solid within
    # 2 mm above bounds.min.y (it is the lowest point, so the placement rule seats the shape on the ground)
    n = 160
    faces = []
    for ax in range(3):
        for side in (lo[ax], hi[ax]):
            uv = rng.random((n * n, 2), dtype=np.float32)
            q = np.empty((n * n, 3), np.float32)
            others = [a for a in range(3) if a != ax]
            q[:, ax] = side
            q[:, others[0]] = lo[others[0]] + uv[:, 0] * (hi[others[0]] - lo[others[0]])
            q[:, others[1]] = lo[others[1]] + uv[:, 1] * (hi[others[1]] - lo[others[1]])
            faces.append(q)
    fd = prog.dist(np.concatenate(faces))[0]
    V.check(f'{name}: the shape stays inside its bounds', float(fd.min()) > -1e-4, f'min field on the box {fd.min():.4f}')
    xs = np.linspace(lo[0], hi[0], 400, dtype=np.float32)
    zs = np.linspace(lo[2], hi[2], 800, dtype=np.float32)
    X, Z = np.meshgrid(xs, zs)
    low = np.stack([X.ravel(), np.full(X.size, lo[1] + 0.002, np.float32), Z.ravel()], -1)
    dl = prog.dist(low)[0]
    # a sharp lowest edge (the jet's bomb fins, a box corner turned 45 degrees) is a few millimetres wide 2 mm up:
    # refine round the coarse grid's 12 lowest field values on a 0.5 mm grid
    fine = []
    for i in np.argsort(dl)[:12]:
        c = low[i]
        u = np.linspace(-0.02, 0.02, 81, dtype=np.float32)
        U, W2 = np.meshgrid(u, u)
        fine.append(np.stack([c[0] + U.ravel(), np.full(U.size, c[1], np.float32), c[2] + W2.ravel()], -1))
    dl = np.minimum(dl.min(), prog.dist(np.concatenate(fine).astype(np.float32))[0].min())
    V.check(f'{name}: bounds.min.y is the lowest point (solid within 2 mm above it)', float(dl.min()) < 0.0,
            f'min field 2 mm above bounds.min.y {dl.min():.4f}')
    prog.free()
    print(f'[compile] {name} {time.perf_counter() - t0:.2f} s', flush=True)

# the jet's canted fins splay outward as the public engine's TSL map turns them (x c - y s, x s + y c): a point
# 5 cm under a fin's top edge, on its mid-plane, is at |x| 0.409 (outboard of the fin root at 0.3); the backup's
# opposite turn put it at 0.191 (inboard)
jet = sdf.EXAMPLES['stylized_fighter_jet']
prog = SdfProgram(map=jet['map'], extra=jet['extra'], uniforms=jet.get('uniforms'), label='jet_fins')
out_pts = np.array([[0.409, 0.939, -1.96], [-0.409, 0.939, -1.96]], np.float32)
in_pts = np.array([[0.191, 0.939, -1.96], [-0.191, 0.939, -1.96]], np.float32)
d_out, d_in = prog.dist(out_pts)[0], prog.dist(in_pts)[0]
V.check('stylized_fighter_jet: the canted fins splay outward (the public engine\'s turn)',
        bool((d_out < 0).all() and (d_in > 0.05).all()),
        f'field at the outward fin tops {d_out.round(4).tolist()}, at the inward mirror {d_in.round(4).tolist()}')
prog.free()

# the engine's createSdfObject(EXAMPLES.x): the generic path, coarse here for speed
for name in KIND_OF:
    t0 = time.perf_counter()
    obj = sdf.create_sdf_object(sdf.EXAMPLES[name], voxel=0.02, cache_dir=os.path.join(V.OUT, 'cache_compile'),
                                name=f'generic_{name}', log=None)
    V.check(f'{name}: create_sdf_object(EXAMPLES[...]) builds (the baked surface)', len(obj.object.data.polygons) > 1000
            and obj.material is not None, f"{len(obj.object.data.polygons)} quads, carrier {obj.stats.get('carrier')} in "
                                          f'{time.perf_counter() - t0:.1f} s')

msg = sdf.help()
V.check('help() lists the four vehicles', all(n in msg for n in KIND_OF))
V.summary()
