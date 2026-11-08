"""The sea's maths without a render: the PCG cell draws against three's hash, the Geometry Nodes displacement against
the numpy reference of sea.js's vertex stage (swells + the faces' relief), the mesh against sea.js's.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_sea_math.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.sets.daisy.ocean import sea as S  # noqa: E402
from eidoblend.sets.daisy.ocean.land import make_coast  # noqa: E402

ck = C.Checks('sea_math')
js = C.js_dump()

# ---- three's hash, exactly
got = S.pcg_hash(np.array([h[0] for h in js['hash']], np.float32))
want = np.array([h[1] for h in js['hash']])
ck.check('pcg hash = three TSL hash (JS reference)', np.array_equal(got, want), f'max diff {np.abs(got - want).max():.3g}')
A, B = S.cell_tables()
row, col = 3, 57
seed = (col + 4096) * 131.0 + (row + 64) * 7919.0
ri, ci = row - S.ROW_MIN, col + S.COL0
ck.check('cell table A holds hash(seed + 0/17/41/73)',
         np.allclose(A[ri, ci], [S.pcg_hash(seed + d) for d in (0, 17, 41, 73)], atol=0, rtol=1e-7))
ck.check('cell table B: present + the row offset', B[ri, ci, 0] == float(S.pcg_hash(seed + 97) >= 0.16)
         and abs(B[ri, 5, 1] - S.pcg_hash((row + 64) * 37.0) * 9) < 1e-6)
info = js['faceCellInfo']
ck.check('face cell info = sea.js', all(abs(info[k] - v) < 1e-12 for k, v in
                                        {'W': 1.7, 'hV': 3.0, 'r0': 3.0, 'DL': 1.7 / 3.0}.items()))

# ---- build the sea in a clean scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
coast = make_coast()
t0 = time.time()
sea = S.build_sea(shore_fn=coast.sdist_3, radius=1500)
print(f'[sea_math] build_sea {time.time() - t0:.1f}s; material nodes {sea.mesh.active_material["eido_nodes"]}, '
      f'displace nodes {len(sea.mesh.modifiers[0].node_group.nodes)}', flush=True)
me = sea.mesh.data
X, Z, tris, Sh = S.sea_mesh_arrays(coast.sdist_3, 1500)
ck.check('mesh: 250 x 768 rings, buried quads dropped as sea.js', len(me.vertices) == 251 * 768 and len(me.polygons) == len(tris),
         f'{len(me.vertices)} verts, {len(me.polygons)} tris')

# ---- the displacement at a moment, against the reference
tt, rev = 41.3, 0.85
sea.set('t', tt)
sea.set('reveal', rev)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = sea.mesh.evaluated_get(dg)
em = ev.to_mesh()
n = len(em.vertices)
P = np.empty(n * 3, np.float32)
em.vertices.foreach_get('co', P)
P = P.reshape(-1, 3)
rest = np.empty(n * 3, np.float32)
em.attributes['rest'].data.foreach_get('vector', rest)
rest = rest.reshape(-1, 3)
ev.to_mesh_clear()
ck.check('rest attribute = the undisplaced mesh', np.abs(rest[:, 0] - X).max() < 1e-3 and np.abs(rest[:, 1] + Z).max() < 1e-3)
pick = np.random.default_rng(1).choice(n, 20000, replace=False)
ref = S.sea_point_np(X[pick], Z[pick], tt, shore=Sh[pick], reveal=rev)
got = np.stack([P[pick, 0], P[pick, 2], -P[pick, 1]], 1)                  # Blender -> three (x, y, z)
err = np.abs(got - np.stack(ref, 1)).max(axis=1)
ck.check('GN displacement = sea.js vertex stage (numpy reference)', np.percentile(err, 99.5) < 2e-3,
         f'p50 {np.median(err) * 1000:.3f} mm, p99.5 {np.percentile(err, 99.5) * 1000:.3f} mm, max {err.max() * 1000:.1f} mm')
fh = S.relief_np(X[pick], Z[pick], tt, rev, 1.0, S._ss(0.5, 6.0, Sh[pick]))
ck.check('faces surface: relief present at this moment', (fh > 0.05).sum() > 50, f'{(fh > 0.05).sum()} of {len(pick)} points > 5 cm')
near = np.hypot(X, Z) < 40
ck.check('swell amplitude near her ~0.3 m (two-bar swell)', 0.25 < np.abs(P[near, 2]).max() < 0.9,
         f'max |dz| {np.abs(P[near, 2]).max():.3f} m')


def heights(**props):
    for k, v in props.items():
        sea.set(k, v)
    bpy.context.view_layer.update()
    e = sea.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    z = np.empty(len(e.vertices) * 3, np.float32)
    e.vertices.foreach_get('co', z)
    sea.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    return z.reshape(-1, 3)[:, 2]


z_relief0 = heights(relief=0.0)
z_calm0 = heights(relief=1.0, calm=0.0)
z_both0 = heights(relief=0.0, calm=0.0)
ck.check('U.calm = 0 stills the swells (only the faces rise)', np.abs(z_both0).max() < 1e-6 and z_calm0.max() > 0.05,
         f'calm 0: max {z_calm0.max():.3f} m of relief, both 0: {np.abs(z_both0).max():.1e}')
ck.check('U.relief = 0 flattens the faces into the swell', np.abs(z_relief0 - (P[:, 2])).max() > 0.05)
ok = ck.summary()
with open(os.path.join(C.OUT, 'test_sea_math.json'), 'w') as f:
    import json
    json.dump(ck.rows, f, indent=1)
