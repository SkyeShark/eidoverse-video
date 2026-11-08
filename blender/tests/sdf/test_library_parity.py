"""The SDF primitive library three ways: the engine's GLSL (SDF_PRIMITIVES, run on the GPU through SdfProgram), the
Python mirror SDF_NP (numpy), and the mesher on a few exact shapes. No render.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_library_parity.py

Prints PASS/FAIL per primitive (max error over 20k random points; the hash-based noises report the share of points
that agree to 1e-4, since float32 FMA contraction differs between any two compilers and the hash amplifies it) and
per mesher check (radius error, outward winding, closed 2-manifold, Euler characteristic, sharp box corners).
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402
from eidoblend.sdf import SDF_NP as S
from eidoblend.sdf.gpu_eval import SdfProgram
from eidoblend.sdf.mesher import dual_contour

rng = np.random.default_rng(3)
P = rng.uniform(-1.5, 1.5, (20000, 3)).astype(np.float32)

A = S.vec3(0.1, -0.4, 0.2)
B = S.vec3(-0.3, 0.5, -0.1)

# (name, GLSL expression of the distance at p, numpy function of p, tolerance or ('share', min share))
CASES = [
    ('sdSphere', 'sdSphere(p, 0.6)', lambda p: S.sd_sphere(p, 0.6), 1e-5),
    ('sdSphere(p,c,r)', 'sdSphere(p, vec3(0.1, 0.2, 0.3), 0.5)', lambda p: S.sd_sphere(p - S.vec3(0.1, 0.2, 0.3), 0.5), 1e-5),
    ('sdBox', 'sdBox(p, vec3(0.5, 0.3, 0.4))', lambda p: S.sd_box(p, S.vec3(0.5, 0.3, 0.4)), 1e-5),
    ('sdRoundBox', 'sdRoundBox(p, vec3(0.4, 0.2, 0.3), 0.1)', lambda p: S.sd_round_box(p, S.vec3(0.4, 0.2, 0.3), 0.1), 1e-5),
    ('sdCapsule', 'sdCapsule(p, vec3(0.1, -0.4, 0.2), vec3(-0.3, 0.5, -0.1), 0.25)', lambda p: S.sd_capsule(p, A, B, 0.25), 1e-5),
    ('sdCap2', 'sdCap2(p, vec3(0.1, -0.4, 0.2), vec3(-0.3, 0.5, -0.1), 0.3, 0.1)', lambda p: S.sd_cap2(p, A, B, 0.3, 0.1), 1e-5),
    ('sdEllipsoid', 'sdEllipsoid(p, vec3(0.8, 0.5, 0.6))', lambda p: S.sd_ellipsoid(p, S.vec3(0.8, 0.5, 0.6)), 1e-5),
    ('sdEllipsoid(p,c,r)', 'sdEllipsoid(p, vec3(0.2, 0.0, -0.1), vec3(0.5, 0.3, 0.4))',
     lambda p: S.sd_ellipsoid(p - S.vec3(0.2, 0.0, -0.1), S.vec3(0.5, 0.3, 0.4)), 1e-5),
    ('sdTorus', 'sdTorus(p, vec2(0.6, 0.2))', lambda p: S.sd_torus(p, (0.6, 0.2)), 1e-5),
    ('sdCone', 'sdCone(p, vec2(sin(0.5), cos(0.5)), 0.8)', lambda p: S.sd_cone(p, (math.sin(0.5), math.cos(0.5)), 0.8), 1e-5),
    ('sdRoundCone', 'sdRoundCone(p, vec3(0.1, -0.4, 0.2), vec3(-0.3, 0.5, -0.1), 0.3, 0.1)', lambda p: S.sd_round_cone(p, A, B, 0.3, 0.1), 1e-5),
    ('sdTriPrism', 'sdTriPrism(p, 0.5, 0.3)', lambda p: S.sd_tri_prism(p, 0.5, 0.3), 1e-5),
    ('smin', 'smin(sdSphere(p, 0.5), sdBox(p - vec3(0.5, 0.0, 0.0), vec3(0.3)), 0.2)',
     lambda p: S.smin(S.sd_sphere(p, 0.5), S.sd_box(p - S.vec3(0.5, 0, 0), S.vec3(0.3, 0.3, 0.3)), 0.2), 1e-5),
    ('smax', 'smax(sdSphere(p, 0.5), sdBox(p - vec3(0.5, 0.0, 0.0), vec3(0.3)), 0.2)',
     lambda p: S.smax(S.sd_sphere(p, 0.5), S.sd_box(p - S.vec3(0.5, 0, 0), S.vec3(0.3, 0.3, 0.3)), 0.2), 1e-5),
    ('opSub', 'opSub(sdSphere(p, 0.3), sdBox(p, vec3(0.5)))',
     lambda p: S.op_sub(S.sd_sphere(p, 0.3), S.sd_box(p, S.vec3(0.5, 0.5, 0.5))), 1e-5),
    ('opSmoothSub', 'opSmoothSub(sdSphere(p, 0.3), sdBox(p, vec3(0.5)), 0.1)',
     lambda p: S.op_smooth_sub(S.sd_sphere(p, 0.3), S.sd_box(p, S.vec3(0.5, 0.5, 0.5)), 0.1), 1e-5),
    ('opInt', 'opInt(sdSphere(p, 0.6), sdBox(p, vec3(0.45)))',
     lambda p: S.op_int(S.sd_sphere(p, 0.6), S.sd_box(p, S.vec3(0.45, 0.45, 0.45))), 1e-5),
    ('opRotateX', 'sdBox(opRotateX(p, 0.7) - vec3(0.1, 0.2, 0.0), vec3(0.5, 0.2, 0.3))',
     lambda p: S.sd_box(S.op_rotate_x(p, 0.7) - S.vec3(0.1, 0.2, 0), S.vec3(0.5, 0.2, 0.3)), 1e-5),
    ('opRotateY', 'sdBox(opRotateY(p, 0.7) - vec3(0.1, 0.2, 0.0), vec3(0.5, 0.2, 0.3))',
     lambda p: S.sd_box(S.op_rotate_y(p, 0.7) - S.vec3(0.1, 0.2, 0), S.vec3(0.5, 0.2, 0.3)), 1e-5),
    ('opRotateZ', 'sdBox(opRotateZ(p, 0.7) - vec3(0.1, 0.2, 0.0), vec3(0.5, 0.2, 0.3))',
     lambda p: S.sd_box(S.op_rotate_z(p, 0.7) - S.vec3(0.1, 0.2, 0), S.vec3(0.5, 0.2, 0.3)), 1e-5),
    ('opMirrorX', 'sdSphere(opMirrorX(p) - vec3(0.4, 0.0, 0.0), 0.3)',
     lambda p: S.sd_sphere(S.op_mirror_x(p) - S.vec3(0.4, 0, 0), 0.3), 1e-5),
    ('opMirrorZ', 'sdSphere(opMirrorZ(p) - vec3(0.0, 0.0, 0.4), 0.3)',
     lambda p: S.sd_sphere(S.op_mirror_z(p) - S.vec3(0, 0, 0.4), 0.3), 1e-5),
    # the hash is `precise` in the GLSL, so the GPU computes the float32 arithmetic as written and numpy repeats it
    ('hash', '_hash(floor(p * 7.0))', lambda p: S.hash(np.floor(p * np.float32(7.0))), 1e-6),
    ('vnoise', 'vnoise(p * 3.1)', lambda p: S.vnoise(p * np.float32(3.1)), 1e-5),
    ('fbm', 'fbm(p * 2.0)', lambda p: S.fbm(p * np.float32(2.0)), ('corr', 0.999)),
    ('fbm6', 'fbm6(p * 2.0)', lambda p: S.fbm6(p * np.float32(2.0)), ('corr', 0.999)),
]

# opU / opSmoothU pick a material: check distance and id
PAIR_CASES = [
    ('opU', 'opU(vec2(sdSphere(p, 0.5), 1.0), vec2(sdBox(p - vec3(0.4, 0.0, 0.0), vec3(0.3)), 2.0))',
     lambda p: S.op_u((S.sd_sphere(p, 0.5), np.float32(1.0)), (S.sd_box(p - S.vec3(0.4, 0, 0), S.vec3(0.3, 0.3, 0.3)), np.float32(2.0)))),
    ('opSmoothU', 'opSmoothU(vec2(sdSphere(p, 0.5), 1.0), vec2(sdBox(p - vec3(0.4, 0.0, 0.0), vec3(0.3)), 2.0), 0.15)',
     lambda p: S.op_smooth_u((S.sd_sphere(p, 0.5), np.float32(1.0)), (S.sd_box(p - S.vec3(0.4, 0, 0), S.vec3(0.3, 0.3, 0.3)), np.float32(2.0)), 0.15)),
]

t0 = time.perf_counter()
for name, expr, fn, tol in CASES:
    prog = SdfProgram(map='vec2 map(vec3 p) { return vec2(%s, 1.0); }' % expr, label=name)
    d_gpu, _m = prog.dist(P)
    d_np = np.asarray(fn(P), np.float32)
    err = np.abs(d_gpu - d_np)
    if isinstance(tol, tuple):
        # same noise, not the same bits: the GPU compiler fuses and reorders float32 arithmetic, and the hash's
        # product (up to ~2.5e5) turns that last-ulp difference into a different value at some lattice points
        share = float(np.mean(err < 1e-4))
        corr = float(np.corrcoef(d_gpu, d_np)[0, 1])
        stat = abs(float(d_gpu.mean() - d_np.mean())) < 0.01 and abs(float(d_gpu.std() - d_np.std())) < 0.01
        C.check(f'glsl~numpy {name}', corr > tol[1] and stat,
                f'correlation {corr:.4f}, {share * 100:.1f}% of points within 1e-4, mean {d_gpu.mean():.4f}/{d_np.mean():.4f}, '
                f'std {d_gpu.std():.4f}/{d_np.std():.4f}')
    else:
        C.check(f'glsl~numpy {name}', float(err.max()) < tol, f'max err {err.max():.2e}')

for name, expr, fn in PAIR_CASES:
    prog = SdfProgram(map='vec2 map(vec3 p) { return %s; }' % expr, label=name)
    d_gpu, m_gpu = prog.dist(P)
    d_np, m_np = fn(P)
    err = np.abs(d_gpu - d_np)
    mism = float(np.mean(np.abs(m_gpu - m_np) > 0.5))
    C.check(f'glsl~numpy {name}', float(err.max()) < 1e-5 and mism < 1e-3, f'max err {err.max():.2e}, material mismatch {mism * 100:.3f}%')

print(f'[parity] {len(CASES) + len(PAIR_CASES)} programs in {time.perf_counter() - t0:.2f} s', flush=True)

# the noise is continuous across lattice cell faces (each lattice point hashes to one value from every cell)
n = 200000
base = rng.uniform(-8, 8, (n, 3)).astype(np.float32)
ax = rng.integers(0, 3, n)
face = np.floor(base[np.arange(n), ax]) + 1.0
lo_side, hi_side = base.copy(), base.copy()
lo_side[np.arange(n), ax] = face - np.float32(2e-4)
hi_side[np.arange(n), ax] = face + np.float32(2e-4)
vn = SdfProgram(map='vec2 map(vec3 p) { return vec2(vnoise(p), 1.0); }', label='vnoise_faces')
jump = np.abs(vn.dist(lo_side)[0] - vn.dist(hi_side)[0])
C.check('vnoise continuous across cell faces', float(jump.max()) < 0.01,
        f'max jump {jump.max():.4f} over {n} face crossings ({np.mean(jump > 0.01) * 100:.3f}% above 0.01)')


# ---- the mesher on exact shapes -------------------------------------------------------------------------------
def mesh_checks(tag, prog, lo, hi, voxel, exact_fn=None, corners=None):
    c = dual_contour(lambda p: prog.dist(p)[0], lambda p, h: prog.grad(p, h)[2], lo, hi, voxel, brick=4,
                     lipschitz=1.2, log=print)
    v, q = c.verts.astype(np.float64), c.quads
    if exact_fn is not None:
        e = np.abs(exact_fn(v))
        C.check(f'{tag}: on the surface', float(e.max()) < 0.15 * voxel, f'max |d| at vertices {e.max() / voxel:.3f} voxel')
    # outward: quad normal (Newell) agrees with the field gradient at its centre
    fv = v[q]
    nrm = np.zeros((len(q), 3))
    for i in range(4):
        a, b = fv[:, i], fv[:, (i + 1) % 4]
        nrm[:, 0] += (a[:, 1] - b[:, 1]) * (a[:, 2] + b[:, 2])
        nrm[:, 1] += (a[:, 2] - b[:, 2]) * (a[:, 0] + b[:, 0])
        nrm[:, 2] += (a[:, 0] - b[:, 0]) * (a[:, 1] + b[:, 1])
    g = prog.grad(fv.mean(axis=1).astype(np.float32), 0.5 * voxel)[2]
    outward = float(np.mean(np.sum(nrm * g, axis=1) > 0))
    C.check(f'{tag}: winding outward', outward > 0.999, f'{outward * 100:.3f}% of quads face along the gradient')
    # closed 2-manifold: every undirected edge used exactly twice, once in each direction
    e = np.stack([q, np.roll(q, -1, axis=1)], -1).reshape(-1, 2)
    und = np.sort(e, axis=1)
    _u, cnt = np.unique(und, axis=0, return_counts=True)
    C.check(f'{tag}: closed manifold', bool((cnt == 2).all()), f'{int((cnt != 2).sum())} edges not shared by exactly 2 quads')
    V, E, F = len(v), len(_u), len(q)
    if corners is not None:
        d = np.min(np.linalg.norm(v[:, None, :] - np.asarray(corners)[None], axis=2), axis=0)
        C.check(f'{tag}: sharp corners kept', float(d.max()) < 0.1 * voxel, f'nearest vertex to each corner {d.max() / voxel:.3f} voxel')
    return V - E + F, c


sphere = SdfProgram(map='vec2 map(vec3 p) { return vec2(sdSphere(p, 0.6), 1.0); }')
chi, c = mesh_checks('sphere r=0.6 @ 1/128', sphere, (-0.7,) * 3, (0.7,) * 3, 1.4 / 128,
                     exact_fn=lambda v: np.linalg.norm(v, axis=1) - 0.6)
C.check('sphere: Euler characteristic 2', chi == 2, f'V-E+F = {chi}')

box = SdfProgram(map='vec2 map(vec3 p) { return vec2(sdBox(p - vec3(0.013, -0.021, 0.007), vec3(0.5, 0.3, 0.4)), 1.0); }')
cs = [(0.013 + sx * 0.5, -0.021 + sy * 0.3, 0.007 + sz * 0.4) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
chi, c = mesh_checks('box @ 1/64', box, (-0.6, -0.4, -0.5), (0.6, 0.4, 0.5), 1.2 / 64, corners=cs)
C.check('box: Euler characteristic 2', chi == 2, f'V-E+F = {chi}')

torus = SdfProgram(map='vec2 map(vec3 p) { return vec2(sdTorus(p, vec2(0.6, 0.2)), 1.0); }')
chi, c = mesh_checks('torus @ 1/96', torus, (-0.9, -0.3, -0.9), (0.9, 0.3, 0.9), 1.8 / 96,
                     exact_fn=lambda v: np.hypot(np.hypot(v[:, 0], v[:, 2]) - 0.6, v[:, 1]) - 0.2)
C.check('torus: Euler characteristic 0', chi == 0, f'V-E+F = {chi}')

C.summary()
