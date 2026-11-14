"""The mesh is the field's surface, hole for hole: the hit distance of every pixel through the dual-contoured mesh
(BVH ray casts) against the engine's march of the same field from the same camera.
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_mesh_depth_parity.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
The subject is the Menger sponge at four levels (uFoldCount = 4): a field full of tunnels, whose finest holes
(25 mm) a 10 mm mesh resolves. Its distance estimator changes up to three times faster than distance, so the
march is run twice: with conservative steps (0.3 of the DE, which cannot step over a wall: the field's true
surface) and with the 'high' preset's steps (0.75). Both stop at the 'high' preset's surfEps (0.0005), set here,
not taken from the example, whose own preset ('balanced', surfEps 0.001) would stop rays a few millimetres short of
the rims and blur the reference this test measures against. PASS lines: both see the same pixels; away from depth
jumps the mesh's depth is the field's within a voxel and a half; at the hole rims (a pixel here spans 1.5 voxels)
the mesh's depth is the field's at the pixel or a neighbour, so every rim lies within a pixel of the field's.
The default march's agreement is printed. out/depth_parity.png: mesh depth, conservative march depth, and the
pixels where they part (white).
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402
import engine_march as EM  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from eidoblend import sdf  # noqa: E402

W, H = 320, 180
CACHE = os.path.join(C.OUT, 'cache_depth')
DEPTH_SHADE = r"""
vec3 shade(vec3 p, vec3 n, float mat) { return vec3(length(p - cameraPosition)); }"""

C.stage(W, H, 1, floor=False, sun=False)
o = sdf.EXAMPLES['menger_sponge'].make(name='depth_menger4', cells=200, cache_dir=CACHE, build=False, log=None)
o.set_uniform('uFoldCount', 4.0)
o.build(log=None)
print(f'[depth] mesh: {len(o.contour.quads)} quads at {o.voxel * 1000:.2f} mm', flush=True)
lo, hi = np.array([-1.02, -1.02, -1.02]), np.array([1.02, 1.02, 1.02])
diag = float(np.linalg.norm(hi - lo))
a, e = math.radians(25), math.radians(18)
off = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * diag * 1.2 * 1.6
cam = C.camera(tuple(off), (0.0, 0.0, 0.0), lens=50)

# the mesh: camera rays through the pixel centres, top row first
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(o.object, dg)
frame = cam.data.view_frame(scene=bpy.context.scene)
tr, br, bl = frame[0], frame[1], frame[2]
inv = o.object.matrix_world.inverted()
origin = inv @ cam.matrix_world.translation
t_mesh = np.full((H, W), np.inf)
for j in range(H):
    v = 1.0 - (j + 0.5) / H
    for i in range(W):
        u = (i + 0.5) / W
        d = (inv.to_3x3() @ (cam.matrix_world.to_3x3() @ (bl + (br - bl) * u + (tr - br) * v))).normalized()
        hit = bvh.ray_cast(origin, d)
        if hit[0] is not None:
            t_mesh[j, i] = hit[3]

# the march, with its shade() swapped for the hit distance (the engine march runs the example's march as written)
o.program.shade = DEPTH_SHADE
marches = {}
for tag, step, steps in (('conservative', 0.3, 1024), ('engine', 0.75, 192)):     # 1024: the kernel's own cap
    o.spec.step_scale, o.spec.max_steps, o.spec.surf_eps = step, steps, 0.0005
    img = EM.march(o, cam, W, H, samples=1)[::-1]                   # top row first, as the rays above
    marches[tag] = np.where(img[..., 3] > 0.5, img[..., 0], np.inf)

tol = 1.5 * o.voxel
ref = marches['conservative']
both = np.isfinite(t_mesh) & np.isfinite(ref)
either = np.isfinite(t_mesh) | np.isfinite(ref)
agree = np.abs(t_mesh - ref) < tol


def window(a, fill):
    """The 3 x 3 neighbourhood of every pixel, stacked: (9, H, W)."""
    p = np.pad(a, 1, constant_values=fill)
    return np.stack([p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])


# a pixel is about 1.5 voxels across here, so at a hole's rim (a depth jump) a rim a fraction of a voxel off sends
# the pixel's ray onto the face in one depth map and down the tunnel in the other; away from rims the depths must
# agree, and at a rim the mesh's depth must be the field's at a neighbouring pixel (the rim within a pixel)
win = window(np.where(np.isfinite(ref), ref, np.nan), np.nan)
with np.errstate(invalid='ignore'):
    smooth = both & (np.nanmax(win, 0) - np.nanmin(win, 0) < tol) & np.isfinite(win).all(0)
    near = np.nanmin(np.abs(win - t_mesh[None]), 0) < tol
C.check('the mesh sees what the field has: the same pixels hit', both.sum() / max(1, either.sum()) > 0.97,
        f'{both.sum()} of {either.sum()} pixels hit by both')
C.check('the mesh is the field surface away from rims: depth within 1.5 voxels', float(agree[smooth].mean()) > 0.97,
        f'{agree[smooth].mean() * 100:.1f}% of {smooth.sum()} pixels with no depth jump around them agree')
C.check('at the rims the mesh is the field within a pixel', float(near[both].mean()) > 0.97,
        f'{near[both].mean() * 100:.1f}% of {both.sum()} pixels match the field at themselves or a neighbour '
        f'({agree[both].mean() * 100:.1f}% at the pixel itself; tolerance {tol * 1000:.1f} mm)')
eng = np.isfinite(marches['engine']) & np.isfinite(marches['conservative'])
e_agree = np.abs(marches['engine'] - marches['conservative']) < tol
print(f'[depth] the engine-step march (0.75) against the conservative one: {e_agree[eng].mean() * 100:.1f}% of '
      f'{eng.sum()} pixels agree; the mesh against the engine-step march: '
      f'{(np.abs(t_mesh - marches["engine"]) < tol)[np.isfinite(t_mesh) & eng].mean() * 100:.1f}%', flush=True)

# the picture: mesh depth, march depth (near = bright), and where they part
fin = t_mesh[np.isfinite(t_mesh)]
near, far = (float(fin.min()), float(fin.max())) if len(fin) else (0.0, 1.0)


def shade_depth(t):
    g = np.where(np.isfinite(t), 1.0 - (np.clip(t, near, far) - near) / max(1e-6, far - near) * 0.8, 0.0)
    return np.repeat(g[..., None], 3, -1)


diff = np.where(both & ~agree, 1.0, np.where(both, 0.15, 0.0))
paths = []
for k, img in (('mesh', shade_depth(t_mesh)), ('march', shade_depth(marches['conservative'])),
               ('diff', np.repeat(diff[..., None], 3, -1))):
    p = os.path.join(C.OUT, f'_depth_{k}.png')
    C.save_linear_png(p, img[::-1], agx=False)          # save_linear_png takes row 0 at the bottom
    paths.append(p)
C.sheet(paths, os.path.join(C.OUT, 'depth_parity.png'), cols=3)
for p in paths:
    os.remove(p)
C.summary()
