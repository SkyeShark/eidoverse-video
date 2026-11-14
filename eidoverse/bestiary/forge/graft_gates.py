"""CROSSBREED's SEAM GATES G-R1..G-R9 (work/bestiary/research/CROSSBREED_DESIGN.md §2.12), each a function of
arrays only, so every one is proved on a PLANTED defect first (SKIN_AND_DETAIL.md: a gate that never failed proves
nothing): the caller perturbs one input the way the defect would and asserts the gate fails.

  G-R1  ring identity             positions, normals and (joint name, weight) pairs bit-identical across every
                                  duplicated ring vertex (base copies and part copies)
  G-R2  geometry at the seam      the part's faces next to the ring against the native's at the same place: normal
                                  angle < 1 deg, position delta < 1e-6 m (DESIGN.md's seam bar)
  G-R3  baked normal continuity   the world normal decoded from each side's own map in each side's own TBN (bake.py:
                                  T, B = cross(N, T) w, N interpolated and normalised, n = T x + B y + N z) at matched
                                  points along the ring: p99 <= 1 deg
  G-R4  colour at w = 0           albedo dE00 <= 1.0 p99 (both decoded by the exact sRGB curve, as three does) and
                                  roughness (ORM G) delta <= 0.02 p99 at the same points
  G-R5  density and stretch       the part's texel density on the ring's triangles within 5 % of the base's there;
                                  the band's anisotropy p95 <= 1.2
  G-R6  band shape                |dr/dz| <= 0.35, bend <= 15 deg, 0 folds and 0 tilts (gates.quad_quality on the
                                  shape), corner angle p1 >= 25 deg, no pole within 0.5 L_band of the ring
  G-R7  bake                      the bake's own gate (islands, clusters) and DESIGN's per-part bars (misses whole
                                  <= 0.5 %, |low - high| p95 <= 3 mm), and the WRONG-SURFACE gate on the band (C5a-3:
                                  the hit against the field's nearest surface from the low point, and the baked normal
                                  against the field's at that point)
  G-R8  motion                    over the rest motion's frames: ring delta 0 (base and part copies skinned), no band
                                  triangle turned over, no band self-intersection, band volume loss <= 8 %
  G-R9  base untouched            the base's images byte-identical, every kept vertex's position, normal, tangent, UV
                                  and (joint name, weight) pairs identical, faces = the original minus exactly the
                                  native group; and (the M0 / M1a check's additions) the base's materials, textures and
                                  samplers as written, each base primitive on its material, every kept node's rest TRS /
                                  extras / references, every kept joint's inverse bind bit for bit
  G-R3b / G-R4b  the collar       G-R3 and G-R4 inside the band's triangles, not only on the ring line (the check's
                                  addition: a seam line 2-5 texels past the ring passed both): decoded normals, albedo
                                  dE00, roughness and AO (the review's R30) at matched points of the part's band and the
                                  native's on the same quads, where w = 0
"""
import numpy as np


def _bits(a):
    return np.ascontiguousarray(np.asarray(a, np.float32)).view(np.uint32)


# ------------------------------------------------------------------------------------------------ G-R1
def g_r1(base_copies, part_copies):
    """base_copies / part_copies: per ring vertex k a list of (V float32 (3,), N float32 (3,), {joint name: weight
    float32}) for every copy. Bit-identical across ALL copies of k, on both sides"""
    bad = []
    for k, (bc, pc) in enumerate(zip(base_copies, part_copies)):
        ref = bc[0]
        for side, cps in (('base', bc), ('part', pc)):
            for c in cps:
                if not np.array_equal(_bits(c[0]), _bits(ref[0])):
                    bad.append((k, side, 'position'))
                if not np.array_equal(_bits(c[1]), _bits(ref[1])):
                    bad.append((k, side, 'normal'))
                wa = {n: int(_bits([w])[0]) for n, w in c[2].items() if w > 0}
                wb = {n: int(_bits([w])[0]) for n, w in ref[2].items() if w > 0}
                if wa != wb:
                    bad.append((k, side, 'weights'))
    n = sum(len(b) + len(p) for b, p in zip(base_copies, part_copies))
    return dict(ok=not bad, copies=n, mismatches=bad[:8], n_bad=len(bad))


# ------------------------------------------------------------------------------------------------ G-R2
def tri_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)


def g_r2(V_part, F_part, V_nat, F_nat, max_deg=1.0, max_dp=1e-6):
    """the part's triangles next to the ring (F_part into V_part) against the NATIVE triangles on the same quads
    (F_nat into V_nat, corner for corner): the normal angle and every corner's position delta"""
    a = tri_normals(np.asarray(V_part, np.float64), F_part)
    b = tri_normals(np.asarray(V_nat, np.float64), F_nat)
    ang = np.degrees(np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)))
    dp = np.linalg.norm(np.asarray(V_part, np.float64)[F_part] - np.asarray(V_nat, np.float64)[F_nat], axis=2)
    return dict(ok=bool(ang.max() < max_deg and dp.max() < max_dp), max_deg=float(ang.max()), max_dp=float(dp.max()),
                tris=len(F_part), per_tri=dict(deg=np.round(ang, 9).tolist(), dp=dp.max(1).tolist()))


# ------------------------------------------------------------------------------------------------ sampling
def bilinear(img, uv):
    """img (H, W, C) uint8 in image order, uv (n, 2) in the forge's v-up convention: texel centres at (i + 0.5) / size
    (three's / WebGPU's sampling of a texture at its UV); returns float (n, C)"""
    h, w = img.shape[:2]
    x = uv[:, 0] * w - 0.5
    y = (1.0 - uv[:, 1]) * h - 0.5
    x0 = np.clip(np.floor(x).astype(int), 0, w - 1)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 1)
    x1, y1 = np.clip(x0 + 1, 0, w - 1), np.clip(y0 + 1, 0, h - 1)
    fx = np.clip(x - np.floor(x), 0, 1)[:, None]
    fy = np.clip(y - np.floor(y), 0, 1)[:, None]
    im = np.asarray(img, np.float64).reshape(h, w, -1)
    return (im[y0, x0] * (1 - fx) + im[y0, x1] * fx) * (1 - fy) + (im[y1, x0] * (1 - fx) + im[y1, x1] * fx) * fy


def edge_samples(n_per_edge=32):
    return (np.arange(n_per_edge) + 0.5) / n_per_edge


def interp_on_edge(A, ia, ib, f):
    """per-vertex attribute A interpolated on the edges (ia[e], ib[e]) at fractions f: (n_e * n_f, ...)"""
    A = np.asarray(A, np.float64)
    return (A[ia][:, None] * (1 - f)[None, :, None] + A[ib][:, None] * f[None, :, None]).reshape(-1, A.shape[1])


def decode_normal(nmap_px, N, T4):
    """bake.py's frame at a point: T, B = cross(N, T) w (per vertex, then interpolated: the caller passes the
    interpolated N, T and the per-point B), normalised; n = T x + B y + N z of the map's 2 rgb - 1"""
    t = nmap_px[:, :3] / 255.0 * 2.0 - 1.0
    N_ = N / np.linalg.norm(N, axis=1, keepdims=True)
    T_ = T4[:, :3] / np.linalg.norm(T4[:, :3], axis=1, keepdims=True)
    B_ = T4[:, 3:6] / np.linalg.norm(T4[:, 3:6], axis=1, keepdims=True)
    n = T_ * t[:, 0:1] + B_ * t[:, 1:2] + N_ * t[:, 2:3]
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def side_frame(N, TAN, ia, ib, f):
    """N, T and B = cross(N, T) w per vertex interpolated along the edges (bake.py interpolates T and B, then
    normalises)"""
    B = np.cross(np.asarray(N, np.float64), np.asarray(TAN, np.float64)[:, :3]) * np.asarray(TAN, np.float64)[:, 3:4]
    Ni = interp_on_edge(N, ia, ib, f)
    TB = interp_on_edge(np.column_stack([np.asarray(TAN, np.float64)[:, :3], B]), ia, ib, f)
    return Ni, TB


# ------------------------------------------------------------------------------------------------ G-R3 / G-R4
def g_r3(base_side, part_side, n_per_edge=32, p99_deg=1.0):
    """each side: dict(ia, ib (the ring's edges, vertex ids in its own arrays, in the same order and direction on both
    sides), UV, N, TAN, nmap (H, W, 3) uint8). The decoded world normals at the same points along the ring"""
    f = edge_samples(n_per_edge)
    out = []
    for s in (base_side, part_side):
        uv = interp_on_edge(s['UV'], s['ia'], s['ib'], f)
        Ni, TB = side_frame(s['N'], s['TAN'], s['ia'], s['ib'], f)
        out.append(decode_normal(bilinear(s['nmap'], uv), Ni, TB))
    ang = np.degrees(np.arccos(np.clip((out[0] * out[1]).sum(1), -1.0, 1.0)))
    return dict(ok=bool(np.percentile(ang, 99) <= p99_deg), p99_deg=float(np.percentile(ang, 99)),
                max_deg=float(ang.max()), median_deg=float(np.median(ang)), points=len(ang),
                per_point=dict(deg=np.round(ang, 5).tolist(), edges=len(base_side['ia']), per_edge=n_per_edge))


def srgb_to_linear(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_lab(rgb):
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = rgb @ M.T / np.array([0.95047, 1.0, 1.08883])
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0
    fx = np.where(xyz > e, np.cbrt(xyz), (k * xyz + 16.0) / 116.0)
    return np.column_stack([116.0 * fx[:, 1] - 16.0, 500.0 * (fx[:, 0] - fx[:, 1]), 200.0 * (fx[:, 1] - fx[:, 2])])


def de2000(lab1, lab2):
    """CIEDE2000 (Sharma, Wu, Dalal 2005)"""
    L1, a1, b1 = lab1.T
    L2, a2, b2 = lab2.T
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = 0.5 * (C1 + C2)
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0.0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lbp = 0.5 * (L1 + L2)
    Cbp = 0.5 * (C1p + C2p)
    hs = h1p + h2p
    hbp = np.where(C1p * C2p == 0, hs, np.where(np.abs(h1p - h2p) <= 180, hs / 2,
                                                  np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dth = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def g_r4(base_side, part_side, n_per_edge=32, de_p99=1.0, rough_p99=0.02):
    """each side: dict(ia, ib, UV, albedo (H, W, 3) uint8 sRGB, orm (H, W, 3) uint8). dE00 and the roughness delta at
    the same points along the ring"""
    f = edge_samples(n_per_edge)
    lab, rough, srgb = [], [], []
    for s in (base_side, part_side):
        uv = interp_on_edge(s['UV'], s['ia'], s['ib'], f)
        px = bilinear(s['albedo'], uv)[:, :3] * 1.0
        srgb.append(px)
        lab.append(linear_to_lab(srgb_to_linear(px)))
        rough.append(bilinear(s['orm'], uv)[:, 1] / 255.0)
    de = de2000(lab[0], lab[1])
    dr = np.abs(rough[0] - rough[1])
    return dict(ok=bool(np.percentile(de, 99) <= de_p99 and np.percentile(dr, 99) <= rough_p99),
                de_p99=float(np.percentile(de, 99)), de_max=float(de.max()), de_median=float(np.median(de)),
                rough_p99=float(np.percentile(dr, 99)), rough_max=float(dr.max()), points=len(de),
                per_point=dict(de=np.round(de, 5).tolist(), rough_delta=np.round(dr, 6).tolist(),
                               srgb_base=np.round(srgb[0], 3).tolist(), srgb_part=np.round(srgb[1], 3).tolist(),
                               rough_base=np.round(rough[0], 6).tolist(), rough_part=np.round(rough[1], 6).tolist()))


# ------------------------------------------------------------------------------------------------ G-R3b / G-R4b
def bary_grid(n):
    """barycentric points on a triangle, n steps per edge, corners and edges included: ((n + 1)(n + 2) / 2, 3)"""
    return np.array([(i / n, j / n, (n - i - j) / n) for i in range(n + 1) for j in range(n + 1 - i)])


def side_at(s, F, lam):
    """one side's attributes at barycentric points lam on its triangles F (t, 3): uv, N, and bake.py's T | B (B =
    cross(N, T) w per vertex, then interpolated), each (t * p, c)"""
    UV, N, TAN = (np.asarray(s[k], np.float64) for k in ('UV', 'N', 'TAN'))
    B = np.cross(N, TAN[:, :3]) * TAN[:, 3:4]
    ip = lambda A: np.einsum('pk,tkc->tpc', lam, A[F]).reshape(-1, A.shape[1])
    return ip(UV), ip(N), np.column_stack([ip(TAN[:, :3]), ip(B)])


def g_r34_band(base_side, part_side, F_base, F_part, ring_origin, ring_axis, row_m, n=24, p99_deg=1.0, de_p99=1.0,
               rough_p99=0.02, ao_p99=0.02, row_q=90.0, row_min=20):
    """THE COLLAR (G-R3b / G-R4b, the M0 / M1a check's addition): G-R3's decoded world normal and G-R4's albedo dE00
    and roughness, plus the ORM's AO (the review's R30), at matched points INSIDE the band: the part's band triangles
    F_part (into part_side's arrays, which also carry V) against the native's on the same quads F_base (corner for
    corner: G-R2's pairing), on a barycentric grid of n steps per edge. G-R3 and G-R4 sample the ring line alone, so a
    seam line a few texels past the ring passed both (the check's plants). Two bars per channel: p99 over every point,
    and in every ROW parallel to the ring (the points binned by their distance along ring_axis from ring_origin, row_m
    wide: one texel) the row_q percentile, so a line along the ring cannot hide under a percentile of the whole band.
    Valid where w = 0: the identity and null grafts' whole band (a donor's band only over its zero-slope start)"""
    lam = bary_grid(n)
    dec, lab, rough, ao = [], [], [], []
    for s, F in ((base_side, F_base), (part_side, F_part)):
        uv, Ni, TB = side_at(s, np.asarray(F), lam)
        dec.append(decode_normal(bilinear(s['nmap'], uv), Ni, TB))
        lab.append(linear_to_lab(srgb_to_linear(bilinear(s['albedo'], uv)[:, :3])))
        o = bilinear(s['orm'], uv)
        rough.append(o[:, 1] / 255.0)
        ao.append(o[:, 0] / 255.0)
    Pp = np.einsum('pk,tkc->tpc', lam, np.asarray(part_side['V'], np.float64)[np.asarray(F_part)]).reshape(-1, 3)
    z = (Pp - np.asarray(ring_origin, np.float64)) @ (np.asarray(ring_axis, np.float64) / np.linalg.norm(ring_axis))
    row = np.floor(z / row_m).astype(np.int64)
    ch = dict(normal_deg=(np.degrees(np.arccos(np.clip((dec[0] * dec[1]).sum(1), -1.0, 1.0))), p99_deg),
              de=(de2000(lab[0], lab[1]), de_p99), rough=(np.abs(rough[0] - rough[1]), rough_p99),
              ao=(np.abs(ao[0] - ao[1]), ao_p99))
    out, ok = dict(points=int(len(z)), rows=int(len(np.unique(row))), row_mm=row_m * 1e3), True
    for k, (x, bar) in ch.items():
        p99 = float(np.percentile(x, 99))
        rq = {int(r): float(np.percentile(x[row == r], row_q)) for r in np.unique(row) if (row == r).sum() >= row_min}
        worst = max(rq, key=rq.get)
        out[k] = dict(p99=p99, max=float(x.max()), worst_row=worst, worst_row_q=rq[worst],
                      rows_over=sorted(r for r, v in rq.items() if v > bar))
        ok &= p99 <= bar and rq[worst] <= bar
    out['ok'] = bool(ok)
    return out


# ------------------------------------------------------------------------------------------------ G-R5
def tri_density(V, F, UV, size):
    P, T = np.asarray(V, np.float64)[F], np.asarray(UV, np.float64)[F] * size
    a3 = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    d1, d2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    a2 = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    return np.sqrt(a2 / np.maximum(a3, 1e-20)), a3


def g_r5(V, F_ring, F_band, UV, size, px_base, tol=0.05, aniso_p95=1.2):
    from . import uv as U
    d, a = tri_density(V, F_ring, UV, size)
    d_ring = float(np.sqrt((d ** 2 * a).sum() / a.sum()))
    s1, s2, ok = U.stretch(np.asarray(V, np.float64), F_band, np.asarray(UV, np.float64))
    an = (s1 / s2)[ok]
    rel = d_ring / px_base - 1.0
    return dict(ok=bool(abs(rel) <= tol and np.percentile(an, 95) <= aniso_p95), px_ring=d_ring, px_base=px_base,
                rel=float(rel), aniso_p95=float(np.percentile(an, 95)), aniso_max=float(an.max()),
                density_p5_p95=[float(np.percentile(d, 5)), float(np.percentile(d, 95))])


# ------------------------------------------------------------------------------------------------ G-R6
def loop_frame(ring, toward):
    """a loop's own frame from its vertices: origin the centroid, Z the best-fit plane's normal turned toward `toward`,
    X vertex 0's direction in that plane"""
    c = ring.mean(0)
    _, _, vt = np.linalg.svd(ring - c)
    z = vt[2] if np.dot(vt[2], toward - c) >= 0 else -vt[2]
    x = ring[0] - c
    x -= z * np.dot(x, z)
    x /= np.linalg.norm(x)
    return c, np.column_stack([x, np.cross(z, x), z])


def g_r6(rings_xyz, Q_band, V_band, prog, L_band, pole_dist=None, slope_max=0.35, bend_max=15.0,
         min_angle_p1=25.0, ref_normals=None):
    """rings_xyz: the ring and the band's loops (m, K, 3) in order (each loop's frame its own: loop_frame); Q_band,
    V_band: the band's quads; prog: the shape (gates.quad_quality's fold and tilt); pole_dist: the distance from the
    ring of the nearest interior vertex whose valence is not 4 inside the band (None: none). The bend: the angle between
    the first and the last loop's normals. THE TAPER |dr/dz| (CROSSBREED M2c restart): per COLUMN (vertex k through the
    loops), its radius about the band's centreline (the loops' centroids; the local axis the polyline's tangent) against
    its own station along it, the steepest step between loops: the surface's own slope, the design's |dr/dz|. The first
    measure, each loop's fitted section's r0 between loops (kept as slope_fit), assumes planar loops: on M2c's waving lip
    line the fit traded r0 against its aspect (0.70 and 1.30, the fit's bounds) and its r0 jumped 19.7 -> 14.4 mm
    between two loops whose mean radii about the axis are 16.06 and 16.04 mm (a slope of 1.25 on a band that tapers by
    0.03)"""
    from . import gates
    from .mesh import QuadMesh
    from .graft import fit_section
    K = rings_xyz.shape[1]
    th = 2.0 * np.pi * np.arange(K) / K
    frames = [loop_frame(r, rings_xyz[min(i + 1, len(rings_xyz) - 1)] .mean(0) if i + 1 < len(rings_xyz)
                         else 2 * r.mean(0) - rings_xyz[i - 1].mean(0)) for i, r in enumerate(rings_xyz)]
    r0, z = [], []
    O0, R0 = frames[0]
    for (Oi, Ri), ring in zip(frames, rings_xyz):
        loc = (ring - Oi) @ Ri
        sec, _ = fit_section(np.hypot(loc[:, 0], loc[:, 1]), np.arctan2(loc[:, 1], loc[:, 0]) % (2 * np.pi))
        r0.append(sec['r0'])
        z.append(float(np.dot(Oi - O0, R0[:, 2])))
    r0, z = np.array(r0), np.array(z)
    slope_fit = float(np.abs(np.diff(r0) / np.maximum(np.diff(z), 1e-12)).max())
    slope, r_mean, z_mean = band_taper(rings_xyz)
    bend = float(np.degrees(np.arccos(np.clip(np.dot(frames[-1][1][:, 2], R0[:, 2]), -1.0, 1.0))))
    m = QuadMesh(V_band, Q_band, {})
    qq, _ = gates.quad_quality(m, prog)
    if 'dot' not in qq:
        # (HX0) a base with no SDF program (the human: its cage is fitted to scans, not to a field) judges folds and
        # tilts against its own shipped vertex normals: each quad's normal (quad_quality's, the diagonals' cross)
        # against the mean of its corners' normals
        assert ref_normals is not None, 'g_r6 without a shape program needs ref_normals (per V_band vertex)'
        Vq, Qq = np.asarray(V_band, np.float64), np.asarray(Q_band)
        nq = np.cross(Vq[Qq[:, 2]] - Vq[Qq[:, 0]], Vq[Qq[:, 3]] - Vq[Qq[:, 1]])
        nq /= np.maximum(np.linalg.norm(nq, axis=1, keepdims=True), 1e-20)
        gq = np.asarray(ref_normals, np.float64)[Qq].mean(1)
        gq /= np.maximum(np.linalg.norm(gq, axis=1, keepdims=True), 1e-20)
        qq['dot'] = (nq * gq).sum(1)
    folds, tilts = int((qq['dot'] < 0).sum()), int((qq['dot'] < 0.5).sum())
    ang_p1 = float(np.percentile(qq['min_angle'], 1))
    pole_ok = pole_dist is None or pole_dist >= 0.5 * L_band
    return dict(ok=bool(slope <= slope_max and bend <= bend_max and folds == 0 and tilts == 0 and ang_p1 >= min_angle_p1
                        and pole_ok), slope=slope, slope_fit=slope_fit, bend_deg=bend, folds=folds, tilts=tilts,
                min_angle_p1=ang_p1, pole_dist=pole_dist, r0_mm=(r0 * 1e3).round(3).tolist(),
                z_mm=(z * 1e3).round(2).tolist(), r_mean_mm=(r_mean * 1e3).round(3).tolist(),
                z_mean_mm=(z_mean * 1e3).round(2).tolist())


def band_taper(rings_xyz):
    """(CROSSBREED M2c restart) a band's TAPER per column (g_r6's docstring): the centreline through the loops'
    centroids, each loop's local axis its tangent (central differences), every vertex's radius from it and its station
    (the centreline's arc length plus its axial offset); returns (the steepest |dr/dz| between loops, each loop's mean
    radius, each loop's mean station) in metres"""
    C = rings_xyz.mean(1)
    seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    T = np.gradient(C, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-20)
    d = rings_xyz - C[:, None, :]
    ax_off = np.einsum('mkj,mj->mk', d, T)
    r_col = np.linalg.norm(d - ax_off[..., None] * T[:, None, :], axis=-1)
    z_col = arc[:, None] + ax_off
    slope_cols = np.abs(np.diff(r_col, axis=0)) / np.maximum(np.abs(np.diff(z_col, axis=0)), 1e-12)
    return float(slope_cols.max()), r_col.mean(1), z_col.mean(1)


# ------------------------------------------------------------------------------------------------ G-R7
def raster_low(V, F, UV, N, TAN, size):
    """per texel (image order) the low's triangle under its CENTRE (-1: none), its point, and bake.py's frame there
    (N, T, B = cross(N, T) w interpolated; not normalised): a numpy rasteriser over the triangles' texel boxes"""
    V, UV, N, TAN = (np.asarray(x, np.float64) for x in (V, UV, N, TAN))
    B = np.cross(N, TAN[:, :3]) * TAN[:, 3:4]
    tid = -np.ones((size, size), np.int64)
    out = {k: np.zeros((size, size, 3)) for k in ('P', 'N', 'T', 'B')}
    T2 = UV * size                                        # kernel rows: y = v * size (image row = size - 1 - y)
    for t, f in enumerate(np.asarray(F)):
        a, b, c = T2[f]
        x0, y0 = np.floor(np.minimum(np.minimum(a, b), c)).astype(int)
        x1, y1 = np.ceil(np.maximum(np.maximum(a, b), c)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-14:
            continue
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        l2 = 1.0 - l0 - l1
        m = (l0 >= -1e-9) & (l1 >= -1e-9) & (l2 >= -1e-9)
        if not m.any():
            continue
        yy = (size - 1 - np.floor(gy[m]).astype(int))
        xx = np.floor(gx[m]).astype(int)
        tid[yy, xx] = t
        w = np.stack([l0[m], l1[m], l2[m]], 1)
        for k, A in (('P', V), ('N', N), ('T', TAN[:, :3]), ('B', B)):
            out[k][yy, xx] = w @ A[f]
    return tid, out


def g_r7(bake_gate, drivers, band, t_hit, t_true, n_baked, n_field, miss_whole_max=0.005, p95_max=0.003,
         tol_d=0.10e-3, tol_a=30.0):
    """the bake's own gate row (bake.gate: islands and clusters) and DESIGN's per-part bars (texels missed whole
    <= 0.5 %, |low - high| p95 <= 3 mm), and the WRONG-SURFACE gate on the band (C5a-3's bars: WRONG where the hit
    stands more than tol_d beyond the NEAREST surface crossing on its line through the texel's low point, or no
    crossing is there, or its baked normal is more than tol_a off the field's at the hit). band: the band's covered
    texels' arrays: t_hit (the hit's distance from the low point), t_true (the nearest crossing's, inf if none), the
    baked world normals and the field's at the hits"""
    cov = drivers['normal'][..., 3] > 0
    missv = np.asarray(drivers['miss']) > 0
    whole = float((missv & ~cov).sum() / max((cov | missv).sum(), 1))
    p95 = float(np.percentile(np.abs(np.asarray(drivers['height'], np.float64)[cov]), 95))
    g_ok = bool(bake_gate.get('ok', False))
    far = (t_hit - t_true > tol_d) | ~np.isfinite(t_true)
    ang = np.degrees(np.arccos(np.clip((n_baked * n_field).sum(1), -1.0, 1.0)))
    tilted = ang > tol_a
    return dict(ok=bool(g_ok and whole <= miss_whole_max and p95 <= p95_max and not far.any() and not tilted.any()),
                gate_ok=g_ok, islands_failed=bake_gate.get('islands_failed'),
                clusters_failed=bake_gate.get('clusters_failed'), miss_whole=whole, height_p95_mm=p95 * 1e3,
                band_texels=int(band), wrong_far=int(far.sum()), wrong_tilted=int(tilted.sum()),
                normal_vs_field_p99_deg=float(np.percentile(ang, 99)) if len(ang) else 0.0)


# ------------------------------------------------------------------------------------------------ G-R8
def tube_volume(rings):
    """the signed volume of the tube between the first and last of rings (m, K, 3), closed by a fan at each end"""
    c0, c1 = rings[0].mean(0), rings[-1].mean(0)
    vol = 0.0
    K = rings.shape[1]
    tet = lambda a, b, c: np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0
    for i in range(len(rings) - 1):
        A, Bv = rings[i], rings[i + 1]
        A1, B1 = np.roll(A, -1, 0), np.roll(Bv, -1, 0)
        vol += tet(A, A1, B1) + tet(A, B1, Bv)
    vol += tet(np.repeat(c0[None], K, 0), np.roll(rings[0], -1, 0), rings[0])
    vol += tet(np.repeat(c1[None], K, 0), rings[-1], np.roll(rings[-1], -1, 0))
    return abs(float(vol))


def tri_tri_intersect(P, F, tol=1e-9):
    """non-adjacent triangle pairs of one small mesh that intersect (segment-triangle tests both ways)"""
    def seg_tri(p, q, a, b, c):
        e1, e2 = b - a, c - a
        d = q - p
        h = np.cross(d, e2)
        det = np.dot(e1, h)
        if abs(det) < tol:
            return False
        s = p - a
        u = np.dot(s, h) / det
        if u < 0 or u > 1:
            return False
        qv = np.cross(s, e1)
        v = np.dot(d, qv) / det
        if v < 0 or u + v > 1:
            return False
        t = np.dot(e2, qv) / det
        return 1e-9 < t < 1 - 1e-9
    hits = 0
    for i in range(len(F)):
        for k in range(i + 1, len(F)):
            if set(F[i]) & set(F[k]):
                continue
            A, Bt = P[F[i]], P[F[k]]
            if any(seg_tri(A[e], A[(e + 1) % 3], *Bt) for e in range(3)) or \
                    any(seg_tri(Bt[e], Bt[(e + 1) % 3], *A) for e in range(3)):
                hits += 1
    return hits


def g_r8(frames, vol_loss_max=0.08):
    """frames: per frame dict(ring_base (n, 3) skinned, ring_part (n, 3) skinned (the copies in the same order), band_V
    (m, 3) skinned, band_F, band_N_rest_turned (per band triangle the rest normal turned by the skin), band_rings
    (r, K, 3) skinned, rest_volume). Ring delta must be 0 exactly"""
    worst_ring, flips, inter, worst_loss = 0.0, 0, 0, 0.0
    for fr in frames:
        worst_ring = max(worst_ring, float(np.abs(fr['ring_base'] - fr['ring_part']).max()))
        n = tri_normals(fr['band_V'], fr['band_F'])
        flips += int(((n * fr['band_N_rest_turned']).sum(1) <= 0).sum())
        if fr.get('check_intersection'):
            inter += tri_tri_intersect(fr['band_V'], fr['band_F'])
        if fr.get('band_rings') is not None:          # (HX0) a surface port's plug has no tube: no volume term
            worst_loss = max(worst_loss, 1.0 - tube_volume(fr['band_rings']) / fr['rest_volume'])
    return dict(ok=bool(worst_ring == 0.0 and flips == 0 and inter == 0 and worst_loss <= vol_loss_max),
                frames=len(frames), ring_delta_max=worst_ring, folds=flips, self_intersections=inter,
                volume_loss_max=worst_loss)


# ------------------------------------------------------------------------------------------------ G-R9
def g_r9(base_glb, out_glb, report, native_tris):
    """the assembled glb against its base: (1) every base image's bytes, (2) every kept vertex's POSITION, NORMAL,
    TANGENT, TEXCOORD_0 and WEIGHTS_0 bytes and (joint name, weight) pairs, (3) each base primitive's triangles = the
    original's minus exactly the native group (the same order), through ASSEMBLE's vertex remaps.
    base_glb / out_glb: paths, or (json, bin) already read (a planted defect edits a copy in memory);
    native_tris: {material name: triangle positions dropped}"""
    import hashlib
    from .assemble import accessor_array, read_glb
    jb, bb = read_glb(base_glb) if isinstance(base_glb, str) else base_glb
    ja, ba = read_glb(out_glb) if isinstance(out_glb, str) else out_glb
    sh = lambda j, b, i: hashlib.sha1(b[j['bufferViews'][j['images'][i]['bufferView']].get('byteOffset', 0):
                                        j['bufferViews'][j['images'][i]['bufferView']].get('byteOffset', 0)
                                        + j['bufferViews'][j['images'][i]['bufferView']]['byteLength']]).hexdigest()
    img_same = [sh(jb, bb, i) == sh(ja, ba, i) for i in range(len(jb['images']))]
    jn_b = [jb['nodes'][n]['name'] for n in jb['skins'][0]['joints']]
    jn_a = [ja['nodes'][n]['name'] for n in ja['skins'][0]['joints']]
    mats_b = [m['name'] for m in jb['materials']]
    mats_a = [m['name'] for m in ja['materials']]
    pb, pa = jb['meshes'][0]['primitives'], ja['meshes'][0]['primitives']
    vert_bad, face_bad, sets = 0, 0, {}
    for pos_acc, s in report['sets'].items():
        vmap = s['vmap']
        kept = np.nonzero(vmap >= 0)[0]
        kb = next(k for k, p in enumerate(pb) if p['attributes']['POSITION'] == pos_acc)
        ka = next(k for k, p in enumerate(pa) if mats_a[p['material']] == mats_b[pb[kb]['material']])
        for an in ('POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'WEIGHTS_0', 'COLOR_0'):
            if an not in pb[kb]['attributes']:
                continue
            A = accessor_array(jb, bb, pb[kb]['attributes'][an])[kept]
            Bv = accessor_array(ja, ba, pa[ka]['attributes'][an])[vmap[kept]]
            vert_bad += int((A.view(np.uint32) != Bv.view(np.uint32)).any(1).sum()) if A.dtype == np.float32 \
                else int((A != Bv).any(1).sum())
        Jb = accessor_array(jb, bb, pb[kb]['attributes']['JOINTS_0'])[kept].astype(int)
        Ja = accessor_array(ja, ba, pa[ka]['attributes']['JOINTS_0'])[vmap[kept]].astype(int)
        Wb = accessor_array(jb, bb, pb[kb]['attributes']['WEIGHTS_0'])[kept]
        nb = np.array(jn_b, object)[Jb]
        na = np.array(jn_a, object)[Ja]
        vert_bad += int(((nb != na) & (Wb > 0)).any(1).sum())
        for k in [k for k, p in enumerate(pb) if p['attributes']['POSITION'] == pos_acc]:
            mn = mats_b[pb[k]['material']]
            ka2 = next(i for i, p in enumerate(pa) if mats_a[p['material']] == mn)
            Fb = accessor_array(jb, bb, pb[k]['indices']).reshape(-1, 3).astype(np.int64)
            Fa = accessor_array(ja, ba, pa[ka2]['indices']).reshape(-1, 3).astype(np.int64)
            keep = np.ones(len(Fb), bool)
            if mn in native_tris:
                keep[list(native_tris[mn])] = False
            want = vmap[Fb[keep]]
            face_bad += int(not (len(want) == len(Fa) and np.array_equal(want, Fa)))
            sets.setdefault(mn, dict(before=len(Fb), after=len(Fa), dropped=int((~keep).sum())))
    # (4)-(6), added by the M0 / M1a check (each proved on a plant it made: a base material re-pointed to the part's
    # normal map, a sampler set to clamp, a material factor changed, a kept joint's rest translation and its inverse
    # bind moved 1 mm, a kept socket renamed; every image byte stayed as it was, so (1)-(3) passed all six):
    # (4) the base's materials, textures and samplers as written, and each base primitive still on its material
    mat_bad = [mats_b[i] for i in range(len(mats_b)) if i >= len(ja['materials']) or ja['materials'][i] != jb['materials'][i]]
    tex_b, tex_a = jb.get('textures', []), ja.get('textures', [])
    tex_bad = [i for i, t in enumerate(tex_b) if i >= len(tex_a) or tex_a[i] != t]
    smp_b, smp_a = jb.get('samplers', []), ja.get('samplers', [])
    smp_bad = [i for i, s in enumerate(smp_b) if i >= len(smp_a) or smp_a[i] != s]
    prim_restyled = [mats_b[p['material']] for k, p in enumerate(pb)
                     if not any(mats_a[q['material']] == mats_b[p['material']] for q in pa)
                     or set(p['attributes']) != set(next(q for q in pa if mats_a[q['material']] == mats_b[p['material']])
                                                    ['attributes'])]
    # (5) every KEPT node by name (ASSEMBLE's node map): its rest TRS, extras, camera and mesh / skin references, and
    # its kept children still its children (a part's joints may be added under its root)
    node_map = report.get('node_map', {})
    names_b = [n.get('name', '') for n in jb['nodes']]
    names_a = [n.get('name', '') for n in ja['nodes']]
    keys = ('name', 'translation', 'rotation', 'scale', 'matrix', 'extras', 'camera')
    node_bad = []
    for i, nb_ in enumerate(jb['nodes']):
        nm = names_b[i]
        if nm not in node_map:
            continue
        na_ = ja['nodes'][node_map[nm]] if node_map[nm] < len(ja['nodes']) else {}
        if any(nb_.get(k) != na_.get(k) for k in keys) or ('mesh' in nb_) != ('mesh' in na_) \
                or ('skin' in nb_) != ('skin' in na_):
            node_bad.append(nm)
            continue
        kids_b = {names_b[c] for c in nb_.get('children', []) if names_b[c] in node_map}
        kids_a = {names_a[c] for c in na_.get('children', [])}
        if not kids_b <= kids_a:
            node_bad.append(nm)
    # (6) every kept joint's inverse bind, bit for bit
    ib_b = accessor_array(jb, bb, jb['skins'][0]['inverseBindMatrices'])
    ib_a = accessor_array(ja, ba, ja['skins'][0]['inverseBindMatrices'])
    pos_a = {n: k for k, n in enumerate(jn_a)}
    ibm_bad = [n for k, n in enumerate(jn_b) if n in node_map and (n not in pos_a or not np.array_equal(
        ib_b[k].view(np.uint32), ib_a[pos_a[n]].view(np.uint32)))]
    ok = (all(img_same) and vert_bad == 0 and face_bad == 0 and not mat_bad and not tex_bad and not smp_bad
          and not prim_restyled and not node_bad and not ibm_bad)
    return dict(ok=bool(ok), images_same=f'{sum(img_same)} / {len(img_same)}', vertex_mismatches=vert_bad,
                primitive_mismatches=face_bad, primitives=sets, materials_changed=mat_bad, textures_changed=tex_bad,
                samplers_changed=smp_bad, primitives_restyled=prim_restyled, kept_nodes_changed=node_bad[:12],
                kept_nodes_checked=len(node_map), kept_ibm_changed=ibm_bad[:12])


# ================================================================================================ (HX0) many meshes, packs
# (HX0, work/bestiary/human/hx0; staged as hx0/patches/graft_gates_multi.md) THE HUMAN: 13 meshes; a skin whose colour
# is the runtime's own model over PACKS (no albedo or ORM map: albedo = a LUT over the PIGMENT pack, roughness and AO
# in the SURFACE and AUX packs); a VRM map. The same bars as the gates above.

def _sample_packs(side, uv):
    return {k: bilinear(img, uv) for k, img in side['packs'].items()}


def g_r4_packs(base_side, part_side, colour_fn, rough_fn, ao_fn=None, n_per_edge=32, de_p99=1.0, rough_p99=0.02,
               ao_p99=0.02):
    """G-R4 for a skin over packs: each side dict(ia, ib, UV (v up), packs={name: (H, W, C) uint8}); colour_fn(samples)
    -> LINEAR rgb (n, 3), rough_fn(samples) -> (n,), ao_fn(samples) -> (n,) (the review's R30), where samples = {name:
    (n, C) float codes} at matched points along the ring. Bars as g_r4 (dE00 p99 <= 1.0, roughness delta p99 <= 0.02),
    the AO's delta p99 <= 0.02; each pack's largest code delta reported beside"""
    f = edge_samples(n_per_edge)
    S = []
    for s in (base_side, part_side):
        S.append(_sample_packs(s, interp_on_edge(s['UV'], s['ia'], s['ib'], f)))
    lab = [linear_to_lab(np.clip(colour_fn(x), 0.0, None)) for x in S]
    de = de2000(lab[0], lab[1])
    dr = np.abs(rough_fn(S[0]) - rough_fn(S[1]))
    da = np.abs(ao_fn(S[0]) - ao_fn(S[1])) if ao_fn else np.zeros(len(de))
    p = lambda x: float(np.percentile(x, 99))
    return dict(ok=bool(p(de) <= de_p99 and p(dr) <= rough_p99 and p(da) <= ao_p99), de_p99=p(de),
                de_max=float(de.max()), de_median=float(np.median(de)), rough_p99=p(dr), rough_max=float(dr.max()),
                ao_p99=p(da), ao_max=float(da.max()), points=len(de),
                pack_code_delta_max={k: float(np.abs(S[0][k] - S[1][k]).max()) for k in S[0]},
                per_point=dict(de=np.round(de, 5).tolist(), rough_delta=np.round(dr, 6).tolist()))


def g_r34_band_packs(base_side, part_side, F_base, F_part, ring_origin, ring_axis, row_m, colour_fn, rough_fn, ao_fn,
                     normal_maps=('N',), n=24, p99_deg=1.0, de_p99=1.0, rough_p99=0.02, ao_p99=0.02, row_q=90.0,
                     row_min=20):
    """G-R3b / G-R4b (g_r34_band's two bars: p99 over every point, and the row_q percentile in every one-texel row along
    the ring) for a skin over packs: the decoded world normal of each map in normal_maps (each side's own TBN), the
    colour by colour_fn, the roughness and the AO, at matched barycentric points of the part's band triangles F_part and
    the native's on the same quads F_base (corner for corner). Each side dict(UV, N, TAN, packs={...}); part_side also V"""
    lam = bary_grid(n)
    smp, dec = [], {k: [] for k in normal_maps}
    for s, F in ((base_side, F_base), (part_side, F_part)):
        uv, Ni, TB = side_at(s, np.asarray(F), lam)
        S = _sample_packs(s, uv)
        smp.append(S)
        for k in normal_maps:
            dec[k].append(decode_normal(np.asarray(S[k][:, :3], np.float64), Ni, TB))
    Pp = np.einsum('pk,tkc->tpc', lam, np.asarray(part_side['V'], np.float64)[np.asarray(F_part)]).reshape(-1, 3)
    z = (Pp - np.asarray(ring_origin, np.float64)) @ (np.asarray(ring_axis, np.float64) / np.linalg.norm(ring_axis))
    row = np.floor(z / row_m).astype(np.int64)
    ch = {f'normal_{k}_deg': (np.degrees(np.arccos(np.clip((dec[k][0] * dec[k][1]).sum(1), -1.0, 1.0))), p99_deg)
          for k in normal_maps}
    lab = [linear_to_lab(np.clip(colour_fn(x), 0.0, None)) for x in smp]
    ch['de'] = (de2000(lab[0], lab[1]), de_p99)
    ch['rough'] = (np.abs(rough_fn(smp[0]) - rough_fn(smp[1])), rough_p99)
    ch['ao'] = (np.abs(ao_fn(smp[0]) - ao_fn(smp[1])), ao_p99)
    out, ok = dict(points=int(len(z)), rows=int(len(np.unique(row))), row_mm=row_m * 1e3), True
    for k, (x, bar) in ch.items():
        p99 = float(np.percentile(x, 99))
        rq = {int(r): float(np.percentile(x[row == r], row_q)) for r in np.unique(row) if (row == r).sum() >= row_min}
        worst = max(rq, key=rq.get)
        out[k] = dict(p99=p99, max=float(x.max()), worst_row=worst, worst_row_q=rq[worst],
                      rows_over=sorted(r for r, v in rq.items() if v > bar))
        ok &= p99 <= bar and rq[worst] <= bar
    out['pack_code_delta_max'] = {k: float(np.abs(smp[0][k] - smp[1][k]).max()) for k in smp[0]}
    out['ok'] = bool(ok)
    return out


def g_r9_multi(base_glb, out_glb, report, native_tris, dropped_names=None):
    """G-R9 on a base of MANY meshes (assemble_multi's report: mesh_map, node_map, tri_maps and vmaps per (mesh, prim)):
    (1) every base image byte-identical; (2) every kept vertex of every kept primitive, EVERY attribute's bits
    (POSITION, NORMAL, TANGENT, TEXCOORD_n, WEIGHTS_n, COLOR_n and custom ones: the human's _MOUTH / _SHELL / _RING) and
    its (joint name, weight) pairs; (3) each primitive's triangles = the original's minus exactly the native group, in
    order; (4) the base's materials, textures and samplers as written, each primitive on its material; (5) every kept
    node by name: rest TRS, extras, camera, the NAME of its mesh, its skin, its kept children; (6) every kept joint's
    inverse bind bit for bit; (7) the nodes that left are exactly dropped_names (None: not checked); (8) the scene's
    roots kept. native_tris: {(mesh name, prim): triangle positions dropped}"""
    import hashlib
    from .assemble import accessor_array, read_glb
    jb, bb = read_glb(base_glb) if isinstance(base_glb, str) else base_glb
    ja, ba = read_glb(out_glb) if isinstance(out_glb, str) else out_glb

    def img_sha(j, b, i):
        v = j['bufferViews'][j['images'][i]['bufferView']]
        o = v.get('byteOffset', 0)
        return hashlib.sha1(b[o:o + v['byteLength']]).hexdigest()
    img_same = [i < len(ja['images']) and img_sha(jb, bb, i) == img_sha(ja, ba, i) for i in range(len(jb['images']))]
    jn_b = np.array([jb['nodes'][n]['name'] for n in jb['skins'][0]['joints']], object)
    jn_a = np.array([ja['nodes'][n]['name'] for n in ja['skins'][0]['joints']], object)
    mesh_map = report['mesh_map']
    vert_bad, face_bad, attr_bad, prims = 0, 0, {}, {}
    for m in jb['meshes']:
        name = m['name']
        if name not in mesh_map:
            continue
        ma = ja['meshes'][mesh_map[name]]
        if ma.get('name') != name:
            attr_bad.setdefault(name, []).append('mesh name')
        kept_pi = [pi for pi in range(len(m['primitives'])) if (report['tri_maps'][(name, pi)] >= 0).any()]
        for pi, pb in enumerate(m['primitives']):
            if pi not in kept_pi:
                continue
            pa = ma['primitives'][kept_pi.index(pi)]
            vmap = report['vmaps'][(name, pi)]
            kept = np.nonzero(vmap >= 0)[0]
            if set(pb['attributes']) != set(pa['attributes']):
                attr_bad.setdefault(name, []).append('attribute set')
            for an, ai in pb['attributes'].items():
                if an not in pa['attributes'] or an.startswith('JOINTS_'):
                    continue
                A2 = accessor_array(jb, bb, ai)[kept].reshape(len(kept), -1)
                B2 = accessor_array(ja, ba, pa['attributes'][an])[vmap[kept]].reshape(len(kept), -1)
                if A2.dtype != B2.dtype or A2.shape != B2.shape:
                    attr_bad.setdefault(name, []).append(f'{an} type')
                    vert_bad += len(A2)
                    continue
                bad = (A2.view(np.uint32) != B2.view(np.uint32)).any(1) if A2.dtype == np.float32 else (A2 != B2).any(1)
                if bad.any():
                    attr_bad.setdefault(name, []).append(an)
                vert_bad += int(bad.sum())
            for an in [a for a in pb['attributes'] if a.startswith('JOINTS_')]:
                wn = 'WEIGHTS_' + an.split('_', 1)[1]
                Jb = accessor_array(jb, bb, pb['attributes'][an])[kept].astype(np.int64)
                Ja = accessor_array(ja, ba, pa['attributes'][an])[vmap[kept]].astype(np.int64)
                Wb = accessor_array(jb, bb, pb['attributes'][wn])[kept]
                bad = ((jn_b[Jb] != jn_a[Ja]) & (Wb > 0)).any(1)
                if bad.any():
                    attr_bad.setdefault(name, []).append(an + ' names')
                vert_bad += int(bad.sum())
            Fb = accessor_array(jb, bb, pb['indices']).reshape(-1, 3).astype(np.int64)
            Fa = accessor_array(ja, ba, pa['indices']).reshape(-1, 3).astype(np.int64)
            keep = np.ones(len(Fb), bool)
            drop = native_tris.get((name, pi), set())
            if drop:
                keep[sorted(drop)] = False
            want = vmap[Fb[keep]]
            f_ok = bool(len(want) == len(Fa) and np.array_equal(want, Fa))
            face_bad += int(not f_ok)
            prims[f'{name}[{pi}]'] = dict(before=len(Fb), after=len(Fa), dropped=int((~keep).sum()), ok=f_ok)
            if pb.get('material') != pa.get('material'):
                attr_bad.setdefault(name, []).append('material index')
    mat_bad = [jb['materials'][i].get('name', i) for i in range(len(jb['materials']))
               if i >= len(ja['materials']) or ja['materials'][i] != jb['materials'][i]]
    tex_b, tex_a = jb.get('textures', []), ja.get('textures', [])
    tex_bad = [i for i, t in enumerate(tex_b) if i >= len(tex_a) or tex_a[i] != t]
    smp_b, smp_a = jb.get('samplers', []), ja.get('samplers', [])
    smp_bad = [i for i, s in enumerate(smp_b) if i >= len(smp_a) or smp_a[i] != s]
    node_map = report.get('node_map', {})
    names_b = [n.get('name', '') for n in jb['nodes']]
    names_a = [n.get('name', '') for n in ja['nodes']]
    mname = lambda j, n: j['meshes'][n['mesh']].get('name') if 'mesh' in n else None
    keys = ('name', 'translation', 'rotation', 'scale', 'matrix', 'extras', 'camera')
    node_bad = []
    for i, nb_ in enumerate(jb['nodes']):
        nm = names_b[i]
        if nm not in node_map:
            continue
        na_ = ja['nodes'][node_map[nm]] if node_map[nm] < len(ja['nodes']) else {}
        if any(nb_.get(k) != na_.get(k) for k in keys) or mname(jb, nb_) != mname(ja, na_) \
                or ('skin' in nb_) != ('skin' in na_):
            node_bad.append(nm)
            continue
        kids_b = {names_b[c] for c in nb_.get('children', []) if names_b[c] in node_map}
        if not kids_b <= {names_a[c] for c in na_.get('children', [])}:
            node_bad.append(nm)
    ib_b = accessor_array(jb, bb, jb['skins'][0]['inverseBindMatrices'])
    ib_a = accessor_array(ja, ba, ja['skins'][0]['inverseBindMatrices'])
    pos_a = {n: k for k, n in enumerate(jn_a)}
    ibm_bad = [n for k, n in enumerate(jn_b) if n in node_map and (n not in pos_a or not np.array_equal(
        ib_b[k].view(np.uint32), ib_a[pos_a[n]].view(np.uint32)))]
    gone = [n for n in names_b if n not in node_map]
    drop_extra = sorted(set(gone) - set(dropped_names)) if dropped_names is not None else []
    drop_missing = sorted(set(dropped_names) - set(gone)) if dropped_names is not None else []
    roots_b = {names_b[i] for s in jb['scenes'] for i in s['nodes'] if names_b[i] in node_map}
    roots_a = {names_a[i] for s in ja['scenes'] for i in s['nodes']}
    ok = (all(img_same) and vert_bad == 0 and face_bad == 0 and not attr_bad and not mat_bad and not tex_bad
          and not smp_bad and not node_bad and not ibm_bad and not drop_extra and not drop_missing
          and roots_b <= roots_a)
    return dict(ok=bool(ok), images_same=f'{sum(img_same)} / {len(img_same)}', vertex_mismatches=vert_bad,
                primitive_mismatches=face_bad, attribute_problems=attr_bad, primitives=prims,
                materials_changed=mat_bad, textures_changed=tex_bad, samplers_changed=smp_bad,
                kept_nodes_changed=node_bad[:12], kept_nodes_checked=len(node_map), kept_ibm_changed=ibm_bad[:12],
                nodes_left=len(gone), nodes_left_unexpected=drop_extra[:12], nodes_kept_unexpected=drop_missing[:12],
                scene_roots_ok=bool(roots_b <= roots_a))


VRM1_REQUIRED = ('hips', 'spine', 'head', 'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightUpperArm', 'rightLowerArm',
                 'rightHand', 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot')


def g_vrm_map(base_glb, out_glb, report, part_bones=None):
    """THE VRM MAP after a graft (HX0, the brief's item 2), by NODE NAME before and after: a humanBone whose joint was
    kept points at the same-named node; one whose joint left is gone, unless a part names it again (part_bones = {bone:
    joint name}) and then it points at that part's ADDED node; VRM 1.0's required bones all present (three-vrm refuses a
    VRM without them); the meta, lookAt and every expression unchanged but for morph binds on nodes that left; the
    firstPerson annotations by name; VRMC_springBone / VRMC_node_constraint node references by name"""
    import json as _json
    from .assemble import read_glb
    jb, _ = read_glb(base_glb) if isinstance(base_glb, str) else base_glb
    ja, _ = read_glb(out_glb) if isinstance(out_glb, str) else out_glb
    vb, va = jb['extensions']['VRMC_vrm'], ja['extensions']['VRMC_vrm']
    nb = [n.get('name', '') for n in jb['nodes']]
    na = [n.get('name', '') for n in ja['nodes']]
    kept = set(report['node_map'])
    added = set(report.get('added_nodes', {}).values())
    part_bones = part_bones or {}
    hb = {k: nb[v['node']] for k, v in vb['humanoid']['humanBones'].items()}
    ha = {k: na[v['node']] for k, v in va['humanoid']['humanBones'].items()}
    bad = []
    for bone, jn in hb.items():
        if jn in kept and bone not in part_bones:
            if ha.get(bone) != jn:
                bad.append(f'{bone}: {jn} -> {ha.get(bone)}')
        elif bone in part_bones:
            node = va['humanoid']['humanBones'].get(bone, {}).get('node')
            if ha.get(bone) != part_bones[bone] or node not in added:
                bad.append(f'{bone}: the part\'s {part_bones[bone]} expected, {ha.get(bone)} (added node: {node in added})')
        elif bone in ha:
            bad.append(f'{bone}: its joint {jn} left, the bone stayed on {ha[bone]}')
    extra = sorted(set(ha) - set(hb))
    missing_required = [b for b in VRM1_REQUIRED if b not in ha]
    pruned = sorted(b for b in hb if b not in ha)

    def exprs(v, names):
        out = {}
        for grp in ('preset', 'custom'):
            for k, e in (v.get('expressions', {}).get(grp) or {}).items():
                e2 = _json.loads(_json.dumps(e))
                if 'morphTargetBinds' in e2:
                    e2['morphTargetBinds'] = [dict(x, node=names[x['node']]) for x in e2['morphTargetBinds']]
                out[f'{grp}.{k}'] = e2
        return out
    eb, ea = exprs(vb, nb), exprs(va, na)
    for e in eb.values():
        if 'morphTargetBinds' in e:
            e['morphTargetBinds'] = [x for x in e['morphTargetBinds'] if x['node'] in kept]
    ex_bad = sorted(k for k in set(eb) | set(ea) if eb.get(k) != ea.get(k))
    fpa = lambda v, names: sorted((names[a['node']], a.get('type')) for a in
                                  (v.get('firstPerson') or {}).get('meshAnnotations', []))
    fp_ok = [x for x in fpa(vb, nb) if x[0] in kept] == fpa(va, na)
    other = {k: (vb.get(k) == va.get(k)) for k in ('meta', 'lookAt', 'specVersion')}
    sb_ok = True
    if 'VRMC_springBone' in (jb.get('extensions') or {}):
        sb_ok = False                       # (none on the human; a base with springs needs this term written first)
    nc = [n.get('name', '') for n in ja['nodes'] if 'VRMC_node_constraint' in (n.get('extensions') or {})]
    ok = not bad and not extra and not missing_required and not ex_bad and fp_ok and all(other.values()) and sb_ok
    return dict(ok=bool(ok), bones_before=len(hb), bones_after=len(ha), pruned=pruned, re_added=sorted(part_bones),
                mismatches=bad[:12], unexpected_bones=extra, missing_required=missing_required,
                expressions_changed=ex_bad[:12], first_person_ok=bool(fp_ok), unchanged=other,
                node_constraints=nc, spring_bone_ok=sb_ok)


# ---- G-R8's ROOT TERM (H4c, work/bestiary/human/h4c/patches/g_r8_root.md; landed at L1 from the builders' gate script
# h4d/build/g06_rootmotion.py and its twist rule h4d/build/g04_twist.py, the numbers unchanged). G-R8 compares the part
# against the base (ring delta 0), so on an identity graft it passes even when the base's PORT ring itself slides on its
# root joint (HX0's check k13: the back-limb rings 16-31 mm against spine_05, 57 mm in the walk). A SOCKET seats its
# flange rigidly on its joint (CROSSBREED §2.6): every ring record with port true must ride its ROOT alone. Limb cuts and
# region rings are measured and listed, not gated (a limb part's own skin continues across them).
G_R8_ROOT_MM = 0.05         # float32 at 1.5 m is ~1e-4 mm; a rigid seat needs the ring fixed on its joint


def _r8_rot(axis, deg):
    a = np.asarray(axis, np.float64)
    a = a / np.linalg.norm(a)
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * (K @ K)


def _r8_mat_quat(R):
    w = np.sqrt(max(0.0, 1.0 + R[0, 0] + R[1, 1] + R[2, 2])) / 2.0
    x = np.sqrt(max(0.0, 1.0 + R[0, 0] - R[1, 1] - R[2, 2])) / 2.0
    y = np.sqrt(max(0.0, 1.0 - R[0, 0] + R[1, 1] - R[2, 2])) / 2.0
    z = np.sqrt(max(0.0, 1.0 - R[0, 0] - R[1, 1] + R[2, 2])) / 2.0
    x = np.copysign(x, R[2, 1] - R[1, 2])
    y = np.copysign(y, R[0, 2] - R[2, 0])
    z = np.copysign(z, R[1, 0] - R[0, 1])
    return np.array([x, y, z, w])


def r8_twist_angle(R, a):
    """the swing-twist decomposition's twist angle of rotation R about unit axis a (radians, wrapped to (-pi, pi])"""
    q = _r8_mat_quat(R)
    t = 2.0 * np.arctan2(float(q[:3] @ a), float(q[3]))
    return (t + np.pi) % (2.0 * np.pi) - np.pi


def r8_drive(local, drivers, gain_scale=1.0):
    """the runtime's twist rule (human/h4b/rig/patches/twist_contract.md) over a pose's local rotations: each twist
    joint at gain x its source's twist about axis_local; returns the pose with the twists"""
    out = dict(local)
    for tw, d in drivers.items():
        a = np.asarray(d['axis_local'], np.float64)
        tau = r8_twist_angle(local.get(d['source'], np.eye(3)), a)
        out[tw] = _r8_rot(a, np.degrees(gain_scale * d['gain'] * tau))
    return out


def r8_skin_mats(names, parents, PT, local):
    """skinning matrices (pose x rest^-1) and joint worlds from local rotations on a rest whose rotations are all the
    identity (PT the joints' rest positions)"""
    W, S = {}, np.zeros((len(names), 4, 4))
    for i, nm in enumerate(names):
        p = parents[nm]
        L = np.eye(4)
        L[:3, :3] = local.get(nm, np.eye(3))
        L[:3, 3] = PT[nm] - (PT[p] if p else 0.0)
        W[nm] = (W[p] @ L) if p else L
        rest = np.eye(4)
        rest[:3, 3] = PT[nm]
        S[i] = W[nm] @ np.linalg.inv(rest)
    return S, W


def r8_ring_arrays(r, names):
    """a ring record's frozen float32 vertices (mm) and its frozen per-vertex (joint, weight) lists as index / weight
    arrays over `names`: what a graft reads"""
    V = np.asarray(r['verts_f32'], np.uint32).view(np.float32).reshape(-1, 3).astype(np.float64) * 1000.0
    pv = r['weights']['per_vertex']
    k = max(len(x) for x in pv)
    J = np.zeros((len(pv), k), np.int64)
    W = np.zeros((len(pv), k))
    for i, x in enumerate(pv):
        for q, (j, w) in enumerate(x):
            J[i, q], W[i, q] = names.index(j), w
    return V, J, W


def _r8_skin(V, J, W, S):
    Vh = np.c_[V, np.ones(len(V))]
    return np.einsum('nk,nkij,nj->ni', W, S[J], Vh)[:, :3]


def _r8_in_root(P, Wroot):
    return (np.linalg.inv(Wroot) @ np.c_[P, np.ones(len(P))].T).T[:, :3]


def r8_human_motion(names, parents, PT, twists, arm_open, walk=()):
    """the human's motion set (g_r8_root.md's table), each pose against its reference, twists driven: the T-pose down
    (less the gait record's arm opening), swing +-25, raise 90, shrug 15 / 30, hip +-30, hip roll +-30, spine turn 20,
    spine bend 15; and `walk`: the controller's frames as (skinning matrices, joint worlds by name order), against the T
    rest. Returns dict(poses=[(label, (S_ref, W_ref), (S_pose, W_pose))], walk=[...], rest=(S, W))"""
    R = _r8_rot
    dn = 70.0 - arm_open
    down = {'upperarm_L': R([0, 0, 1], -dn), 'upperarm_R': R([0, 0, 1], dn)}
    ax = {sd: twists[f'thigh_twist_01_{sd}']['axis_local'] for sd in 'LR'}
    P = [('T-pose down', {}, down)]
    P += [(f'swing {s:+d}', down, {k: R([1, 0, 0], -s) @ v for k, v in down.items()}) for s in (25, -25)]
    P += [('raise 90', {}, {'upperarm_L': R([0, 0, 1], 90), 'upperarm_R': R([0, 0, 1], -90)})]
    P += [(f'shrug {s}', down, dict(down, clavicle_L=R([0, 0, 1], s), clavicle_R=R([0, 0, 1], -s))) for s in (15, 30)]
    P += [(f'hip {s:+d}', down, dict(down, thigh_L=R([1, 0, 0], -s), thigh_R=R([1, 0, 0], -s))) for s in (30, -30)]
    P += [(f'hip roll {s:+d}', down, dict(down, thigh_L=R(ax['L'], s), thigh_R=R(ax['R'], -s))) for s in (30, -30)]
    P += [('spine turn 20', down, dict(down, spine_03=R([0, 1, 0], 10), spine_04=R([0, 1, 0], 10)))]
    P += [('spine bend 15', down, dict(down, spine_03=R([1, 0, 0], 7.5), spine_04=R([1, 0, 0], 7.5)))]
    poses = [(lab, r8_skin_mats(names, parents, PT, r8_drive(ref, twists)),
              r8_skin_mats(names, parents, PT, r8_drive(p, twists))) for lab, ref, p in P]
    rest = (np.stack([np.eye(4) for _ in names]), {n: np.eye(4) for n in names})
    for n in names:
        rest[1][n][:3, 3] = PT[n]
    return dict(poses=poses, walk=list(walk), rest=rest)


def g_r8_root(ring, names, motion, bar_mm=G_R8_ROOT_MM):
    """G-R8's ROOT TERM on one ring record: the largest displacement (mm) of a ring vertex in its ROOT joint's frame,
    each pose against its reference and the walk's frames against the rest (motion = r8_human_motion's dict); gated
    (bar_mm) only for records with port true. -> dict(ok, gated, max_mm, worst, per_motion, off_root_weight_max)"""
    V, J, W = r8_ring_arrays(ring, names)
    root = ring['root']
    k = names.index(root)
    row = {}
    for lab, (Sr, Wr), (Sp, Wp) in motion['poses']:
        a = _r8_in_root(_r8_skin(V, J, W, Sp), Wp[root])
        b = _r8_in_root(_r8_skin(V, J, W, Sr), Wr[root])
        row[lab] = float(np.linalg.norm(a - b, axis=1).max())
    if motion.get('walk'):
        S0, W0 = motion['rest']
        b0 = _r8_in_root(_r8_skin(V, J, W, S0), W0[root])
        wmax = 0.0
        for S, M in motion['walk']:
            a = _r8_in_root(_r8_skin(V, J, W, S), M[k])
            wmax = max(wmax, float(np.linalg.norm(a - b0, axis=1).max()))
        row['walk'] = wmax
    off_root = float((W * (J != k)).sum(1).max())
    port = bool(ring.get('port'))
    mx = max(row.values())
    return dict(ok=(not port) or mx <= bar_mm, gated=port, max_mm=mx, worst=max(row, key=row.get),
                per_motion={k_: round(v, 4) for k_, v in row.items()}, off_root_weight_max=round(off_root, 6))
