"""The octopus's BEAK: its own part, seated in the mouth's opening like the eyes in their sockets (craft guide 16.4:
a layered assembly, not painted skin). Skye 10-20: "the octopus's underside is missing a beak area ... the central
mouth hole".

Built to the oral reference (work/bestiary/research/ORAL_REFERENCE.md §7-§10):
  * both beaks are U-shaped troughs folded back at the front into a biting edge and a hood; the UPPER (dorsal, +Z
    here) fits WITHIN the LOWER (ventral, -Z), the cephalopod's inverted parrot: "the ventral jaw, which bites outside
    the dorsal, is the larger and wider" (Isgrove);
  * octopod rostra are wide and BLUNT: the upper's tip wide and flat, the lower's "especially well rounded",
    anvil-like (Uyeno & Kier; Lu & Ickeringill);
  * seen from the oral side the lower's broad, rounded rostrum is the front surface and frames the upper's narrower
    hooked tip, which ends inside the lower's rostral hollow;
  * the rostra and hoods are tanned near-black with a cool cast (fresh L* 3-15); the walls and wings mid-dark brown,
    amber only at the trailing margins; growth lines parallel to the edges; glossy and wet.
(The first beak was a parrot: the upper in front with a needle tip, the lower 14 % narrower: all three wrong.)

Only the rostra show between the lips: the rest sits in the buccal mass, built just far enough to read past them.
Sizes in units of the lip's outer radius L = R + r (prog.mouth).

    beak_meshes(mouth) -> [dict(name, V, F, N, UV)]: triangles, one UV island per mandible in a shared atlas
    paint_beak(size)   -> albedo (sRGB uint8), normal (GL uint8), orm (uint8): painted in the atlas's (around, along)
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc

N_T, N_A = 24, 20           # stations along a mandible, vertices round it (~960 triangles each)
KEEL = 0.75                 # the cutting edge's angular position round the section (fraction of a turn)

# per mandible, in units of L: the centreline's control points as (up, toward its own side), the section's half-width
# and half-depth at the base, and their floors at the rostrum (a blunt end, not a point)
MANDIBLES = {
    # (t16b: from below the two read as equal lobes; the lower's rostrum broader, the upper set deeper, so the lower's
    # face fills the opening and the upper's tip shows only inside its hollow)
    'lower': dict(side=-1, ctrl=[(1.30, 0.50), (0.80, 0.55), (0.22, 0.30), (0.05, -0.05)],
                  w0=0.50, w_tip=0.25, h0=0.30, h_tip=0.09),
    'upper': dict(side=+1, ctrl=[(1.85, 0.45), (1.10, 0.48), (0.55, 0.20), (0.42, -0.08)],
                  w0=0.38, w_tip=0.09, h0=0.30, h_tip=0.07),
}


def _bezier(P, t):
    t = t[:, None]
    return ((1 - t) ** 3) * P[0] + 3 * ((1 - t) ** 2) * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3]


def mandible(mouth, name, v0, v1):
    """one mandible as a closed loft (MANDIBLES[name]); its UVs fill v0..v1"""
    spec = MANDIBLES[name]
    c, up = mouth['c'], mouth['up']
    L = mouth['R'] + mouth['r']
    zz = np.array([0.0, 0.0, float(spec['side'])])
    xx = np.array([1.0, 0.0, 0.0])
    P = [c + up * (a * L) + zz * (b * L) for a, b in spec['ctrl']]
    t = np.linspace(0.0, 1.0, N_T)
    C = _bezier(P, t)
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    D = np.cross(xx[None], T)                           # the section's depth axis (toward this mandible's own side)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    if np.dot(D[0], zz) < 0:
        D = -D
    X = np.cross(T, D)
    # the section: broad at the base, narrowing to a BLUNT rostrum (its width and depth keep a floor); the inner side
    # (toward the other mandible, -D) drawn to a keel, the biting edge; a low ridge down the outer side, the hood's crest
    w = L * ((spec['w0'] - spec['w_tip']) * (1.0 - t) ** 0.9 + spec['w_tip'])
    h = L * ((spec['h0'] - spec['h_tip']) * (1.0 - t ** 1.5) ** 0.8 + spec['h_tip'])
    # N_A + 1 per ring: the last a copy of the first at u = 1 (the UV seam), so no strip wraps the atlas
    na = N_A + 1
    a = np.linspace(0.0, 2.0 * np.pi, na)
    ca, sa = np.cos(a), np.sin(a)
    keel = np.clip(-sa, 0.0, 1.0) ** 4                  # 1 at the inner side
    crest = np.clip(sa, 0.0, 1.0) ** 6
    prof = sa * (1.0 + 0.6 * keel + 0.2 * crest)
    V = (C[:, None] + w[:, None, None] * ca[None, :, None] * X[:, None]
         + (h[:, None, None] * prof[None, :, None]) * D[:, None])
    # rings -> quads (u round, v along), the base and the rostrum closed by fans to their end points (the rostrum's
    # end point barely proud of its last ring: a rounded blunt end)
    V = V.reshape(-1, 3)
    UV = np.column_stack([np.tile(a / (2 * np.pi), N_T), np.repeat(v0 + (v1 - v0) * t, na)])
    F = []
    for i in range(N_T - 1):
        for k in range(N_A):
            p, q, r_, s_ = i * na + k, i * na + k + 1, (i + 1) * na + k + 1, (i + 1) * na + k
            F += [[p, q, r_], [p, r_, s_]]
    nb = len(V)
    V = np.vstack([V, C[0] - T[0] * 0.0003, C[-1] + T[-1] * (0.6 * spec['h_tip'] * L)])
    # the fan points just past their rings in v (a UV triangle needs area; the paint clamps there to base / rostrum)
    UV = np.vstack([UV, [0.5, v0 - 0.01], [0.5, v1 + 0.01]])
    for k in range(N_A):
        F.append([nb, k + 1, k])
        F.append([nb + 1, (N_T - 1) * na + k, (N_T - 1) * na + k + 1])
    F = np.array(F, np.int64)
    # the winding: outward (each tube face's normal points away from the centreline)
    n_tube = 2 * N_A * (N_T - 1)
    fc = V[F[:n_tube]].mean(1)
    fn = np.cross(V[F[:n_tube, 1]] - V[F[:n_tube, 0]], V[F[:n_tube, 2]] - V[F[:n_tube, 0]])
    ring = np.arange(n_tube) // (2 * N_A)
    if np.mean(np.einsum('ij,ij->i', fn, fc - C[ring])) < 0:
        F = F[:, [0, 2, 1]]
    # smooth normals, welded across the seam copies (same position)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    key = np.unique(np.round(V * 1e7).astype(np.int64), axis=0, return_inverse=True)[1].reshape(-1)
    Nw = np.zeros((key.max() + 1, 3))
    for kk in range(3):
        np.add.at(Nw, key[F[:, kk]], fn)
    N = Nw[key] / np.maximum(np.linalg.norm(Nw[key], axis=1, keepdims=True), 1e-20)
    return dict(name=f'beak_{name}', V=V, F=F, N=N, UV=UV)


def beak_meshes(mouth):
    return [mandible(mouth, 'upper', 0.02, 0.48), mandible(mouth, 'lower', 0.52, 0.98)]


@wp.kernel
def k_beak(size: int, seed: int, alb: wp.array(dtype=wp.vec3), hgt: wp.array(dtype=wp.float32),
           rough: wp.array(dtype=wp.float32)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    u = (float(px) + 0.5) / float(size)
    v = (float(py) + 0.5) / float(size)
    # which mandible, and t along it (0 base, 1 rostrum)
    t = wp.clamp((v - 0.02) / 0.46, 0.0, 1.0)
    if v > 0.5:
        t = wp.clamp((v - 0.52) / 0.46, 0.0, 1.0)
    # angular distance from the biting edge (the keel at KEEL of a turn)
    du = wp.abs(u - 0.75)
    du = wp.min(du, 1.0 - du)
    edge = 1.0 - proc.smoothstep(0.0, 0.22, du)
    # tanning (ORAL_REFERENCE §10): the rostrum, hood and biting edge near-black with a cool cast (fresh L* 3-15); the
    # walls and wings mid-dark brown, streaky; amber only at the trailing margins (the base, t < ~0.06)
    front = t + 0.30 * edge + 0.06 * proc.fbm3(wp.vec3(u * 9.0, t * 6.0, float(seed)), 3, 2.0, 0.5, seed)
    dark = proc.smoothstep(0.03, 0.28, front)
    brown = M.srgb(wp.vec3(0.45, 0.35, 0.25))
    brown2 = M.srgb(wp.vec3(0.36, 0.27, 0.18))
    amber = M.srgb(wp.vec3(0.62, 0.40, 0.20))
    black = M.srgb(wp.vec3(0.105, 0.11, 0.12))
    m = 0.5 + 0.5 * proc.fbm3(wp.vec3(u * 14.0, t * 22.0, 7.0), 3, 2.0, 0.5, seed + 3)
    col = M.mix3(brown, brown2, m)
    col = M.mix3(amber, col, proc.smoothstep(0.0, 0.06, t))
    # growth lines: daily increments parallel to the edges (~0.09 mm in the reference; ~0.2 mm here, uneven in spacing
    # and strength, so they read at this texel size without a fingerprint)
    ph = front * 70.0 + 3.0 * proc.fbm3(wp.vec3(u * 6.0, t * 3.0, 3.0), 2, 2.0, 0.5, seed + 5)
    gl = (0.5 + 0.5 * wp.cos(6.283185307 * ph)) * proc.smoothstep(-0.3, 0.4, proc.fbm3(
        wp.vec3(u * 11.0, t * 7.0, 5.0), 2, 2.0, 0.5, seed + 9))
    col = col * (0.97 + 0.03 * gl)
    col = M.mix3(col, black, dark)
    alb[tid] = col
    hgt[tid] = 0.000005 * (gl - 0.5) * (1.0 - 0.6 * dark)
    rough[tid] = 0.16 + 0.05 * (1.0 - gl) * (1.0 - dark) - 0.04 * dark


def paint_beak(size=512, seed=17):
    from .octopus_eye import height_to_normal
    n = size * size
    alb = wp.zeros(n, dtype=wp.vec3)
    hgt = wp.zeros(n, dtype=wp.float32)
    rgh = wp.zeros(n, dtype=wp.float32)
    wp.launch(k_beak, dim=n, inputs=[size, seed, alb, hgt, rgh])
    A = alb.numpy().reshape(size, size, 3)[::-1]
    H = hgt.numpy().reshape(size, size)[::-1]
    Rg = rgh.numpy().reshape(size, size)[::-1]
    albedo = (M.srgb_oetf(A) * 255 + 0.5).astype(np.uint8)
    normal = height_to_normal(H, 0.00005)
    orm = np.dstack([np.full((size, size), 255, np.uint8), (np.clip(Rg, 0, 1) * 255 + 0.5).astype(np.uint8),
                     np.zeros((size, size), np.uint8)])
    return albedo, normal, orm
