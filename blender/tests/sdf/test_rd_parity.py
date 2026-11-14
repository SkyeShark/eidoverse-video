"""rhombic_dodecahedron.js against its Blender port: deno runs the engine's file as written (rd_dump.mjs) and the
port must give the same cell (vertices, faces, outward normals) and the same FCC lattice points for fillVolumeRD,
fillSphereRD and voxelizeMeshRD (a box, ray parity). No render.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_rd_parity.py
"""

import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402
from eidoblend.common import EIDOVERSE_DIR  # noqa: E402
from eidoblend.sdf import rhombic_dodecahedron as RD  # noqa: E402

sys.path.insert(0, os.path.dirname(C.HERE))
import _where  # noqa: E402

# three from the checkout that holds node_modules/ (blender/tests/_where.py main_checkout())
THREE = os.path.join(str(_where.main_checkout()), 'node_modules', 'three', 'build', 'three.module.js')
deno = os.environ.get('DENO', 'deno')
res = subprocess.run([deno, 'run', '--no-config', '--no-lock', '-A', os.path.join(C.HERE, 'rd_dump.mjs'),
                      EIDOVERSE_DIR, THREE], capture_output=True, text=True, timeout=120)
line = [ln for ln in res.stdout.strip().splitlines() if ln.startswith('{')]
if not line:
    C.check('deno ran the engine file', False, res.stderr[-2000:])
    C.summary()
js = json.loads(line[-1])

# ---- the cell: the same 14 vertices, the same 12 faces, normals outward like the engine's normal attribute ----
v, f = RD.rd_geometry(0.5)
pos = np.asarray(js['cell']['positions']).reshape(-1, 3)
nrm = np.asarray(js['cell']['normals']).reshape(-1, 3)
js_verts = {tuple(np.round(p, 6)) for p in pos}
py_verts = {tuple(np.round(p, 6)) for p in v}
C.check('cell vertices', js_verts == py_verts, f'{len(js_verts)} engine / {len(py_verts)} port')
js_faces = [{tuple(np.round(p, 6)) for p in pos[i * 6:(i + 1) * 6]} for i in range(12)]
py_faces = [{tuple(np.round(v[k], 6)) for k in face} for face in f]
C.check('cell faces', all(jf in py_faces for jf in js_faces), '12 rhombi')
ok = True
for i, face in enumerate(f):
    a, b, c = v[face[0]], v[face[1]], v[face[2]]
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n)
    fs = {tuple(np.round(v[k], 6)) for k in face}
    j = js_faces.index(fs)
    ok &= bool(np.allclose(n, nrm[j * 6], atol=1e-6))
C.check('cell winding gives the engine normals', ok, 'Blender face normal == engine normal attribute, all 12')
inr = float(np.linalg.norm(v[f].mean(axis=1), axis=1).mean())
C.check('cell inradius as the engine built it', abs(inr - 0.5 * 2 ** -0.5) < 1e-9,
        f'face centres at {inr:.4f} for radius 0.5 (the engine comment said 0.5)')

# ---- lattices, in the engine's own axes (the walk is axis-agnostic) ----
for key, pts in (('volume', RD.fcc_lattice({'x': [-1.5, 1.5], 'y': [0, 2], 'z': [-1, 1.3]}, 0.5)),):
    ref = np.asarray(js[key])
    C.check(f'fillVolumeRD lattice', ref.shape == pts.shape and np.allclose(ref, pts, atol=1e-9),
            f'{len(ref)} engine points, {len(pts)} port points (same order)')
sph = RD.fcc_lattice({'x': [0.2 - 1.4, 0.2 + 1.4], 'y': [1.0 - 1.4, 1.0 + 1.4], 'z': [-0.3 - 1.4, -0.3 + 1.4]}, 0.4)
sph = sph[((sph - np.array([0.2, 1.0, -0.3])) ** 2).sum(axis=1) <= 1.4 * 1.4]
ref = np.asarray(js['sphere'])
C.check('fillSphereRD lattice', ref.shape == sph.shape and np.allclose(ref, sph, atol=1e-9),
        f'{len(ref)} engine points, {len(sph)} port points')

# ---- voxelizeMeshRD on the same box, in Blender (ray parity along up), compared as point sets ----
import bpy  # noqa: E402
C.clear_scene()
bpy.ops.mesh.primitive_cube_add(size=1.0)
cube = bpy.context.active_object
cube.scale = (2.0, 1.5, 1.0)                          # three BoxGeometry(2, 1, 1.5): x, y=-z, z=y
cube.location = (0.13, 0.04, 0.07)                    # three position (0.13, 0.07, -0.04) -> (x, -z, y)
bpy.context.view_layer.update()
BOX_C, BOX_H = np.array([0.13, 0.04, 0.07]), np.array([1.0, 0.75, 0.5])
ref = np.asarray(js['voxelized'])
ref_b = np.stack([ref[:, 0], -ref[:, 2], ref[:, 1]], -1)
a = {tuple(np.round(p, 6) + 0.0) for p in ref_b}
eng = RD.voxelize_mesh_rd(mesh=cube, cell_size=0.3, front_faces_only=True, name='rd_engine_like')
b = {tuple(np.round(p, 6) + 0.0) for p in eng.points}
C.check('voxelizeMeshRD, single-sided raycast like three', a == b,
        f'{len(a)} engine / {len(b)} port unique points (the ellipsoid fallback; engine list {len(ref)} long with '
        f'its float walk\'s duplicates)')
C.check('fills drop the engine walk\'s duplicate points', len(eng.points) == len(b) and
        eng.duplicates_dropped == len(ref) - len(a), f'{len(eng.points)} instances, {eng.duplicates_dropped} duplicates '
        f'dropped ({len(ref) - len(a)} in the engine list)')
dup = RD.fill_volume_rd(bounds={'x': [-0.9, 1.1], 'y': [-0.7, 0.8], 'z': [-0.45, 0.55]}, cell_size=0.3, name='rd_dups')
walk = RD.fcc_lattice_blender({'x': [-0.9, 1.1], 'y': [-0.7, 0.8], 'z': [-0.45, 0.55]}, 0.3)
C.check('a walk that rounds two strides to one point yields one cell', dup.duplicates_dropped > 0 and
        len(dup.points) == len({tuple(np.round(p, 6)) for p in walk}),
        f'{len(walk)} walked, {dup.duplicates_dropped} duplicates dropped, {len(dup.points)} cells')
vox = RD.voxelize_mesh_rd(mesh=cube, cell_size=0.3)
lo, hi = BOX_C - BOX_H, BOX_C + BOX_H
lat = RD.fcc_lattice_blender({'x': [lo[0], hi[0]], 'y': [lo[1], hi[1]], 'z': [lo[2], hi[2]]}, 0.3)
truth = {tuple(np.round(p, 6) + 0.0) for p in lat if np.all(np.abs(p - BOX_C) < BOX_H)}
got = {tuple(np.round(p, 6) + 0.0) for p in vox.points}
C.check('voxelizeMeshRD, every crossing counted (the documented intent)', got == truth,
        f'{len(got)} cells = the walk\'s lattice points inside the box ({len(truth)})')
C.summary()
