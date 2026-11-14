"""THE BOW TIE (ACCESSORIES B5, 11-11; Skye's sentence 17, "and a bowtie"; work/bestiary/accessories_b5/soft_NOTES.md):
a pre-tied BUTTERFLY bow tie in BLACK SATIN, with burgundy and navy as colour variants of the same low, UVs and bake.
The old creator had no bow tie (creature_builder.js: no such option); the catalog plans one (remix/recipe.py
ACCESSORIES['bow_tie']: archetype 'tie', authored width 0.060).

THE OBJECT (what a pre-tied satin bow tie is, from the photos in soft/bow_tie/refs_photos/, CC0):
  * two LOOPS, the bow's wings: a satin tube folded back on itself, its end a soft fold; the butterfly outline (narrow
    at the knot, flaring to rounded ends) MEASURED on a real self-tied butterfly (t01_measure.json: height over span
    0.13 at the knot, 0.24 at 0.15 of the span, 0.29 at 0.20, 0.34 at 0.30, 0.40 at 0.45);
  * the KNOT: a wrap round the gathered middle, 13 x 20 mm, a barrel tucked in at its edges; two shallow PLEATS on
    each loop's front, radiating from the knot (the fabric gathered into it);
  * two TAILS behind the loops (single layers, the outline at 0.90 of the loops');
  * the NECK BAND: a doubled satin strip 13 mm wide round the neck, from behind the knot; its path per wearer is a MORPH
    TARGET (an adjustable band takes the neck's size), its rest shape a person's neck at the collar;
  * at the band's back: the SLIDE (a nickel adjuster frame over the band) and the HOOK (a nickel hook plate): METAL 1.

Frame (remix.js's item contract): metres, +Y up, +Z the tie's FRONT, +X the wearer's left; the origin the SEAT POINT:
the middle of the band's front face behind the knot (it lies on the collar's front, or the neck's).
Sizes: span 120 mm [E: a common pre-tied size; the photo's proportions]; band 13 x 1.2 mm, the neck at the collar
r 56 mm (the base woman's socket_neck_collar radius 51.8 mm + a collar) [E]; hardware 17 x 11 mm slide [E].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .. import sdf
from . import soft_common as SC

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})

SPEC = dict(
    span=0.120,
    # the loop's height over the span along |x| / span [M: t01, the butterfly; the tip's rounding beyond 0.45 E]
    prof_u=(0.045, 0.07, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.475, 0.490, 0.497),
    prof_h=(0.130, 0.145, 0.175, 0.240, 0.287, 0.316, 0.338, 0.362, 0.392, 0.402, 0.350, 0.250, 0.150),
    knot_w=0.013, knot_h=0.0205, knot_d=0.0105, knot_r=0.0045,
    loop_t0=0.0030, loop_t1=0.0066,     # the loop's thickness (front puff + back) at the knot and at its outer fold
    loop_z=0.0054,                      # the loops' and the knot's mid-plane: the knot's back on the band's front
    #                                     face (z 0), never through the band
    back_puff=0.55,                     # the loop's back is flatter than its front (it lies against the shirt)
    rho=0.0006,                         # the fabric's fold radius at the loops' top and bottom (two satin layers)
    # (11-11 08:10, after the first low: the TAILS behind the loops were wholly hidden from every view (348 quads a
    # side for nothing): taken out; a pre-tied tie shows the bow and the knot)
    pleat_v=(-0.22, 0.24), pleat_r=0.0011, pleat_depth=0.00045, pleat_len=0.30,     # of the span from the knot
    # (11-11 15:10) THE PLEATS ARE SOFT GATHERS DRAWN IN THE MATERIAL PASS ('material'): the 12:10 bake's carved
    # grooves ('groove', the keys above, kept so that bake can be rebuilt) read as channels in moulded plastic; gathers
    # 0.35 mm deep are under one pixel of the closest view, so they live in the maps (gather_at; TECHNIQUES 15)
    pleat_mode='material',
    # (b11_pleat_preview.py: 0.35 mm / 1.0 -> 2.6 mm was faint at the closest view; 0.45 / 1.2 -> 3.2: flanks 14 deg
    # at the knot, 6 at 15 mm, 2.7 at 20, gone by 25)
    gather_x0=0.0062, gather_len=0.36, gather_depth=0.00045, gather_w0=0.0012, gather_w1=0.0032, gather_fade=1.2,
    band_w=0.013, band_t=0.0012, neck_r=0.056,
    slide_w=0.017, slide_l=0.011, slide_wire=0.0012,
    hook_w=0.0085, hook_l=0.009, hook_t=0.0008,
)
N_LOOP = 14                 # points round a loop's ring (front 5, top arc 2, back 5, bottom arc 2: each fold a
#                             semicircle in 3 segments, and the tip's cap all quads)
N_KNOT = 20                 # round the knot's ring
N_BAND = 33                 # the band's stations (32 segments: 8 tiles of 4)
REGIONS = ('satin', 'knot', 'band', 'metal', 'cap')
ZONES = ('satin', 'band', 'metal', 'thread')         # masks B = 0, 1/3, 2/3, 1 (the runtime's palette zones)
SHARES = dict(loop=1.0, loop_back=0.85, loop_cap=1.4, knot=1.7, knot_back=1.0, band=1.0, slide=1.2, hook=1.2)
# (08:25: the two loop rectangles set the density by filling the sheet's width and the rest was too small to fill
# what is left: at knot 1.2, band 0.6 the sheet held 65-70 %. The leftover goes to the knot, the centre of every
# view, and the small parts)
UV_SIZE = 1024              # the sheet (a 120 mm tie: 0.092 mm a texel at the tips, finer toward the knot; the closest
#                             view's pixel is 0.43 mm)
# the recorded placing order and density (soft_common.pack's search, 11-11 08:27: 77.5 % of one 1024 sheet, least
# gutter 11.0 px, no overlap; `b05_forge.py low size=1024` with both set to None searches again, 2 minutes)
UV_ORDER = ['loop', 'loop_back', 'knot', 'band', 'knot_back', 'hook', 'slide', 'loop_cap']
UV_PPM = 10878.60961234736

VARIANTS = dict(
    black=dict(name='bow_tie', satin=(0.016, 0.016, 0.018)),            # [E: a black satin's albedo, a dyed black]
    burgundy=dict(name='bow_tie_burgundy', satin=(0.150, 0.016, 0.030)),
    navy=dict(name='bow_tie_navy', satin=(0.014, 0.024, 0.075)),
)
MATERIAL = dict(
    metal=(0.66, 0.62, 0.56), dust=(0.30, 0.28, 0.25),
    satin_rough=0.30, satin_rough_fold=0.42, band_rough=0.38, metal_rough=0.18,
    weave_pitch=0.00045,                 # the satin's floats (along the fabric's length), metres
    weave_amp=0.0000035,
    grime=0.45, sheen=0.18, seed=61, table_n=1024,
    gather_rough=0.07, gather_occ=0.30,  # the gathers' valleys: a little rougher (crushed floats), a little occluded
)


# ------------------------------------------------------------------------------------------------- the profile
def height(spec, ax):
    """the loop's full height at |x| = ax (metres): the measured profile, held flat inside the knot"""
    u = np.asarray(ax, np.float64) / spec['span']
    return spec['span'] * np.interp(u, spec['prof_u'], spec['prof_h'])


def thick(spec, ax):
    """the loop's thickness at |x|: gathered at the knot, open at the outer fold, closing over the tip"""
    u = np.asarray(ax, np.float64) / spec['span']
    t = spec['loop_t0'] + (spec['loop_t1'] - spec['loop_t0']) * SC.smoothstep(0.05, 0.40, u)
    return t * np.interp(u, [0.0, 0.46, 0.49, 0.497], [1.0, 1.0, 0.55, 0.35])


def loop_stations(spec):
    """|x| of the loop's rings: one inside the knot, dense where the loop flares, the tip's three closing rings"""
    s = spec['span']
    return np.array([0.0055, 0.0080, 0.0110, 0.0150, 0.0200, 0.0260, 0.0320, 0.0380, 0.0440, 0.0500, 0.0540,
                     0.0570, 0.0588, 0.0596]) * (s / 0.120)


LENS_V = np.array([-0.88, -0.5, 0.0, 0.5, 0.88])


def lens(v):
    """the loop's PUFF across its height: 1 in the middle, falling toward the folds (a satin tube with air in it)"""
    return np.power(np.clip(1.0 - np.asarray(v, np.float64) ** 2, 0.0, 1.0), 0.6)


def lens_core(n=24, back=SPEC['back_puff']):
    """the high's psweep core for a loop: x (the thickness, +x the front) = 0.5 lens(v) at the front, -0.5 back lens(v)
    behind; y = 0.5 v; scaled per node by (T_puff, H) - 2 rho (lens14's points lie on it, offset by rho)"""
    v = np.linspace(-1.0, 1.0, n)
    front = np.column_stack([0.5 * lens(v), 0.5 * v])
    backs = np.column_stack([-0.5 * back * lens(v[::-1]), 0.5 * v[::-1]])
    return np.vstack([front, backs[1:-1]])


def lens14(T, H, rho, back):
    """a loop's ring: (14, 2) points (z, y) on the lens core offset by rho, STARTING UNDER THE BOTTOM FOLD (the UV
    seam's place: hidden underneath): 0 the bottom fold's front point, 1..5 the front face (bottom to top), 6 and 7 the
    top fold (front, back), 8..12 the back face (top to bottom), 13 the bottom fold's back point. T the front puff's
    full thickness scale and H the height: the core scaled by (T - 2 rho, H - 2 rho)"""
    a, yb = 0.5 * max(T - 2.0 * rho, 1e-5), 0.5 * max(H - 2.0 * rho, 1e-5)
    v = LENS_V
    front = np.column_stack([rho + a * lens(v), yb * v])
    th = np.radians([55.0, 125.0])
    top = np.column_stack([rho * np.cos(th), yb + rho * np.sin(th)])
    back_ = np.column_stack([-(rho + back * a * lens(v[::-1])), yb * v[::-1]])
    bot = np.column_stack([rho * np.cos(th + np.pi), -yb + rho * np.sin(th + np.pi)])     # 235 deg (back), 305 (front)
    return np.vstack([bot[1:2], front, top, back_, bot[0:1]])


def rrect20(a, b, r):
    """the knot's ring: (20, 2) points (z, y) round a rounded rectangle (half sizes a in z, b in y, corner r), from the
    front's bottom, going up the front"""
    r = min(r, 0.95 * a, 0.95 * b)
    ya, za = b - r, a - r
    th = np.radians([30.0, 60.0])
    pts = [[a, -ya], [a, -0.5 * ya], [a, 0.0], [a, 0.5 * ya], [a, ya]]                  # front 5
    pts += [[za + r * np.cos(t), ya + r * np.sin(t)] for t in th]                       # top-front corner 2
    pts += [[za, b], [0.0, b], [-za, b]]                                                # top 3
    pts += [[-za - r * np.sin(t), ya + r * np.cos(t)] for t in th]                      # top-back corner 2
    pts += [[-a, ya], [-a, 0.0], [-a, -ya]]                                             # back 3
    pts += [[-za - r * np.cos(t), -ya - r * np.sin(t)] for t in th]                     # bottom-back corner 2
    pts += [[0.0, -b]]                                                                  # bottom 1
    pts += [[za + r * np.sin(t), -ya - r * np.cos(t)] for t in th]                      # bottom-front corner 2
    return np.array(pts)


def knot_stations(spec):
    hw = 0.5 * spec['knot_w']
    x = np.array([-1.0, -0.72, -0.30, 0.30, 0.72, 1.0]) * hw
    # the barrel: full in the middle, tucked onto the loops at its edges
    f = np.array([0.62, 0.92, 1.0, 1.0, 0.92, 0.62])
    return x, f


# ------------------------------------------------------------------------------------------------- the band
def band_path(spec=SPEC, hull=None, tilt=0.0):
    """the band's centre line as N_BAND stations (P), their width directions (W) and outward normals (O): from behind
    the knot's left edge, round the neck, to behind its right edge. hull: the neck's outline in the band's plane as a
    convex polygon (m, 2) of (x, z) in the tie's frame (None: the rest shape, a circle of neck_r touching the origin's
    plane from behind); tilt: the plane turned about +X (radians; + its back lower)"""
    hw = 0.5 * spec['knot_w']
    zf = -0.5 * spec['band_t']                                  # the centre line just behind the band's front face
    if hull is None:
        R = spec['neck_r']
        c = np.array([0.0, zf - R])
        th0 = np.arcsin(min(0.95, hw / R))
        th = np.linspace(th0, 2.0 * np.pi - th0, N_BAND)        # from the front-left round the back to the front-right
        P2 = np.column_stack([c[0] + R * np.sin(th), c[1] + R * np.cos(th)])
    else:
        H = np.asarray(hull, np.float64)
        cen = H.mean(0)
        ang = np.arctan2(H[:, 0] - cen[0], H[:, 1] - cen[1])
        o = np.argsort(ang)
        H = H[o]
        ang = ang[o]
        # the hull's outline sampled by angle from its centre, starting at the front-left of the knot
        a0 = np.arctan2(hw - cen[0], zf - cen[1])
        th = a0 + np.linspace(0.0, 2.0 * np.pi - 2.0 * a0, N_BAND)
        th = (th + np.pi) % (2.0 * np.pi) - np.pi
        Hc = np.vstack([H, H[:1]])
        out = []
        for t_ in th:
            d = np.array([np.sin(t_), np.cos(t_)])
            best = None
            for k in range(len(H)):
                p, q = Hc[k], Hc[k + 1]
                M_ = np.column_stack([d, p - q])
                if abs(np.linalg.det(M_)) < 1e-14:
                    continue
                s_, u_ = np.linalg.solve(M_, p - cen)
                if s_ > 0.0 and -1e-9 <= u_ <= 1.0 + 1e-9:
                    best = s_ if best is None else max(best, s_)
            out.append(cen + d * (best if best is not None else 0.0))
        P2 = np.array(out)
        P2[0] = [hw, zf]
        P2[-1] = [-hw, zf]
    ct, st = np.cos(tilt), np.sin(tilt)
    P = np.column_stack([P2[:, 0], -(P2[:, 1] - zf) * st, zf + (P2[:, 1] - zf) * ct])
    T = np.gradient(P, axis=0)
    Wd = np.tile(np.array([0.0, ct, st]), (len(P), 1))         # the band's width: the plane's normal
    O = SC.unit(np.cross(T, Wd))
    cen3 = P.mean(0)
    if float(((P - cen3) * O).sum()) < 0.0:
        O = -O
    return P, Wd, O


def band_verts(P, W, O, spec=SPEC):
    hw, ht = 0.5 * spec['band_w'], 0.5 * spec['band_t']
    return np.stack([P + hw * W + ht * O, P - hw * W + ht * O, P - hw * W - ht * O, P + hw * W - ht * O], 1)


# ---------------------------------------------------------------------------------------------------- the low
def _ring_quads(nr, ns, closed=True):
    idx = np.arange(nr * ns).reshape(ns, nr)
    Q = []
    for i in range(ns - 1):
        for k in range(nr if closed else nr - 1):
            Q.append([idx[i, k], idx[i, (k + 1) % nr], idx[i + 1, (k + 1) % nr], idx[i + 1, k]])
    return np.array(Q), idx


def _perim_uv(ring):
    """a ring's cumulative arc length (metres) from its first point, closed (n + 1 values)"""
    d = np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])


def bow_z(spec, x):
    """the loop's mid-plane offset along x: its front bows forward 1 mm at the middle, the tip sweeps back 1.2 mm"""
    u = np.asarray(x, np.float64) / spec['span']
    return 0.0010 * np.sin(np.pi * np.clip(u / 0.5, 0.0, 1.0)) - 0.0012 * SC.smoothstep(0.30, 0.50, u)


def wing(spec, side, kind='loop'):
    """a loop on one side (+1 the wearer's left): its lens rings along x (lens14), the tip's cap. UVs per quad
    corner: u round the ring (cut at the front face's bottom), v along x (metres)"""
    sx = float(side)
    xs = loop_stations(spec)
    zc = spec['loop_z']
    rings = []
    for x in xs:
        r2 = lens14(thick(spec, x), height(spec, x), spec['rho'], spec['back_puff'])
        rings.append(np.column_stack([np.full(N_LOOP, sx * x), r2[:, 1], zc + bow_z(spec, x) + r2[:, 0]]))
    # THE UV SEAM IS A VERTEX SPLIT (11-11 08:12: the first pack shared each ring's first vertex between its first and
    # last quads, so the closing column ran backwards across the whole island: "95 % fill" by area, 48.9 % on the
    # sheet): each ring carries its first point again at its end, the same position, u = the full perimeter
    per = [_perim_uv(np.column_stack([r[:, 1], r[:, 2]])) for r in rings]
    V = np.vstack([np.vstack([r, r[:1]]) for r in rings])
    nr = N_LOOP + 1
    Q, idx = _ring_quads(nr, len(xs), closed=False)
    # THE LOOP'S ISLANDS UNWRAPPED AS RECTANGLES (08:18): every ring's arc length stretched to the widest ring's (the
    # tip's) perimeter. As trapezoids (the perimeter grows 32 -> 100 mm toward the tip) they packed at 70 %. The
    # material pass draws the satin from OBJECT-space coordinates (attr), so the stretch only moves texels: up to
    # ~3 x the density toward the knot, where the pleats are; the tip keeps the sheet's density
    pmax = max(float(p[-1]) for p in per)
    uv = np.vstack([np.column_stack([p * (pmax / p[-1]), np.full(nr, x)]) for p, x in zip(per, xs)])
    # the tip: a cap of quads joining each front point (1..5) to its back partner (12..8) across the closed end, the
    # two folds' arcs closing it top (5, 6, 7, 8) and bottom (12, 13, 0, 1); its own island (its points laid flat)
    last = idx[-1]
    cq = [[last[k], last[k + 1], last[12 - k], last[13 - k]] for k in range(1, 5)]
    cq += [[last[5], last[6], last[7], last[8]], [last[12], last[13], last[0], last[1]]]
    nm = f'{kind}' if side > 0 else f'{kind}_R'
    # per quad corner UVs (assemble takes (m, 4, 2)): the tube's from its vertices, the cap's from (y, z) at the tip
    uvq = [[uv[v] for v in q] for q in Q] + [[[float(V[v][1]), float(V[v][2])] for v in q] for q in cq]
    Qall = np.vstack([Q, np.array(cq)])
    # TWO ISLANDS round the tube (08:14: one ring-wide island, a trapezoid 32 -> 100 mm wide, packed at 52 %): the
    # FRONT (columns 0..6: the bottom fold's front half, the front face, the whole top fold) and the BACK (7..13)
    col = np.tile(np.arange(nr - 1), len(xs) - 1)
    sfx = '' if side > 0 else '_R'
    island = [f'{kind}{sfx}' if c <= 6 else f'{kind}_back{sfx}' for c in col] + [f'{kind}_cap{sfx}'] * len(cq)
    Qo = SC.orient(Qall, V, centre=np.array([sx * 0.5 * xs.mean(), 0.0, zc]))
    uvq = np.array(uvq)
    for f in range(len(Qall)):
        if not np.array_equal(Qo[f], Qall[f]):
            uvq[f] = uvq[f][::-1]
    attr = np.zeros((len(V), 4))
    attr[:, 0] = np.repeat(xs, nr)                               # along the wing (the satin's grain)
    attr[:, 1] = np.concatenate(per)                             # round it
    attr[:, 2] = sx
    return dict(name=nm, region=0, V=V, Q=Qo, uv=uvq, island=island, primary=side > 0, attr=attr)


def knot(spec):
    xs, f = knot_stations(spec)
    a0, b0 = 0.5 * spec['knot_d'], 0.5 * spec['knot_h']
    zc = spec['loop_z']
    rings = []
    # (the ring starts at its BOTTOM'S MIDDLE (rrect20's point 17): the UV seam hidden under the knot)
    order = np.r_[17:20, 0:17]
    for x, s in zip(xs, f):
        r2 = rrect20(a0 * s, b0 * (0.80 + 0.20 * s), spec['knot_r'] * s)[order]
        rings.append(np.column_stack([np.full(N_KNOT, x), r2[:, 1], zc + r2[:, 0]]))
    per = [_perim_uv(np.column_stack([r[:, 1], r[:, 2]])) for r in rings]
    V = np.vstack([np.vstack([r, r[:1]]) for r in rings])          # the seam split (wing()'s note)
    nr = N_KNOT + 1
    Q, idx = _ring_quads(nr, len(xs), closed=False)
    uv = np.vstack([np.column_stack([p, np.full(nr, x)]) for p, x in zip(per, xs)])
    Qo = SC.orient(Q, V, centre=np.array([0.0, 0.0, zc]))
    # TWO ISLANDS (08:22: one ring-wide strip stood as a tall column and left a 215 px gutter beside it): the FRONT
    # (columns 0..10: from the bottom's middle up the front to the top's middle) and the BACK (11..19, on the band)
    col = np.tile(np.arange(nr - 1), len(xs) - 1)
    island = ['knot' if c <= 10 else 'knot_back' for c in col]
    attr = np.zeros((len(V), 4))
    attr[:, 0] = np.repeat(xs, nr)
    attr[:, 1] = np.concatenate(per)
    return dict(name='knot', region=1, V=V, Q=Qo, uv=uv, island=island, primary=True, attr=attr)


def band(spec, path=None):
    """the band: 4 faces round, N_BAND stations, 8 tiles of 4 segments stacked on the first (face_mask's strap, the
    same construction); the inner face stacked on the outer"""
    P, W, O = path if path is not None else band_path(spec)
    C4 = band_verts(P, W, O, spec)
    Vs = C4.reshape(-1, 3)
    ids = np.arange(len(Vs)).reshape(N_BAND, 4)
    Ls = np.linalg.norm(np.diff(P, axis=0), axis=1)
    tile_len = 4.0 * float(Ls.mean())
    w_, t_ = spec['band_w'], spec['band_t']
    span = {0: (t_ + w_, t_), 1: (t_, 0.0), 2: (t_, t_ + w_), 3: (t_ + w_ + t_, t_ + w_)}
    Qs, uvs, isl, prim = [], [], [], []
    for j in range(N_BAND - 1):
        tile, k4 = divmod(j, 4)
        u0, u1 = k4 * tile_len / 4.0, (k4 + 1) * tile_len / 4.0
        for fc in range(4):
            a, b = fc, (fc + 1) % 4
            Qs.append([ids[j, a], ids[j, b], ids[j + 1, b], ids[j + 1, a]])
            va, vb = span[fc]
            uvs.append([[u0, va], [u0, vb], [u1, vb], [u1, va]])
            base = 'band' if fc in (0, 1, 3) else 'band_in'
            isl.append(base if (tile == 0 and fc != 2) else f'{base}_{tile}')
            prim.append(tile == 0 and fc != 2)
    Qs, uvs = np.array(Qs), np.array(uvs)
    Qo = SC.orient(Qs, Vs)
    nq = np.cross(Vs[Qo[0, 2]] - Vs[Qo[0, 0]], Vs[Qo[0, 3]] - Vs[Qo[0, 1]])
    if float(nq @ O[0]) < 0.0:
        Qo = Qo[:, ::-1].copy()
    for f_ in range(len(Qs)):
        if not np.array_equal(Qo[f_], Qs[f_]) and np.array_equal(Qo[f_], Qs[f_][::-1]):
            uvs[f_] = uvs[f_][::-1]
    a_s = np.zeros((len(Vs), 4))
    a_s[:, 0] = np.repeat((np.arange(N_BAND) % 4) * tile_len / 4.0, 4)
    a_s[:, 1] = np.tile([w_, 0.0, 0.0, w_], N_BAND)
    return dict(name='band', region=2, V=Vs, Q=Qo, uv=uvs, island=isl, primary=np.array(prim), attr=a_s), (P, W, O)


def _box_frame(c, ex, ey, ez, w, l, wire, name, island, region):
    """a rectangular wire frame (the slide): 4 bars of square section round a w (along ex) x l (along ey) opening, its
    plane normal ez: 8 corner points per bar end -> 4 bars x 4 faces, the corners mitred"""
    hw, hl, h = 0.5 * w, 0.5 * l, 0.5 * wire
    outer = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]
    inner = [(-hw + wire, -hl + wire), (hw - wire, -hl + wire), (hw - wire, hl - wire), (-hw + wire, hl - wire)]
    V = []
    for (ox, oy), (ix, iy) in zip(outer, inner):
        for (px, py) in ((ox, oy), (ix, iy)):
            for dz in (h, -h):
                V.append(c + px * ex + py * ey + dz * ez)
    V = np.array(V)                                              # per corner k: 4 points (o+, o-, i+, i-)
    Q = []
    for k in range(4):
        a, b = 4 * k, 4 * ((k + 1) % 4)
        Q += [[a + 0, b + 0, b + 2, a + 2],                      # top face (z +)
              [a + 3, b + 3, b + 1, a + 1],                      # bottom face
              [a + 1, b + 1, b + 0, a + 0],                      # outer side
              [a + 2, b + 2, b + 3, a + 3]]                      # inner side
    Q = np.array(Q)
    Qo = SC.orient(Q, V, centre=c)
    # the frame's outer side must face out: orient by the centre would point the inner side's normals away from
    # the centre too (outward from the frame's middle): correct for a frame seen as a ring
    uv = np.column_stack([(V - c) @ ex, (V - c) @ ey]) + np.array([0.0, 0.0])
    return dict(name=name, region=region, V=V, Q=Qo, uv=uv, island=island, primary=True,
                attr=np.column_stack([uv, np.zeros((len(V), 2))]))


def _plate(c, ex, ey, ez, w, l, t, name, island, region):
    """a flat plate (the hook): a box w x l x t, 6 faces"""
    hw, hl, ht = 0.5 * w, 0.5 * l, 0.5 * t
    corners = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]
    V = np.array([c + x * ex + y * ey + z * ez for z in (ht, -ht) for (x, y) in corners])
    Q = np.array([[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]])
    Qo = SC.orient(Q, V, centre=c)
    uv = np.column_stack([(V - c) @ ex + 0.6 * ((V - c) @ ez), (V - c) @ ey])
    return dict(name=name, region=region, V=V, Q=Qo, uv=uv, island=island, primary=True,
                attr=np.column_stack([uv, np.zeros((len(V), 2))]))


def hardware(spec, path):
    """the slide over the band at its back, the hook plate beside it (the band's frame there)"""
    P, W, O = path
    j = N_BAND // 2
    T = SC.unit(P[j + 1] - P[j - 1])
    c = P[j] + O[j] * (0.5 * spec['band_t'] + 0.5 * spec['slide_wire'] + 0.0001)
    slide = _box_frame(c, W[j], T, O[j], spec['slide_w'], spec['slide_l'], spec['slide_wire'], 'slide', 'slide', 3)
    k = j + 3
    T2 = SC.unit(P[k + 1] - P[k - 1])
    c2 = P[k] + O[k] * (0.5 * spec['band_t'] + 0.5 * spec['hook_t'] + 0.0001)
    hook = _plate(c2, W[k], T2, O[k], spec['hook_w'], spec['hook_l'], spec['hook_t'], 'hook', 'hook', 3)
    return [slide, hook]


def build_low(spec=SPEC, path=None, log=print):
    parts = [wing(spec, +1), wing(spec, -1), knot(spec)]
    b, pth = band(spec, path)
    parts.append(b)
    parts += hardware(spec, pth)
    nq = sum(len(p['Q']) for p in parts)
    log(f'[bow_tie] low: {len(parts)} parts, {nq} quads ({2 * nq} triangles): '
        + ', '.join(f'{p["name"]} {len(p["Q"])}' for p in parts))
    return parts, dict(path=pth)


# ------------------------------------------------------------------------------------------------ block-out
def _knot_sdf(prog, spec, core):
    """the knot's barrel sweep in its own box (build_sdf's group; knot_solid's alone)"""
    xs, f = knot_stations(spec)
    xk = np.linspace(xs[0], xs[-1], 24)
    fk = np.interp(xk, xs, f)
    rk = spec['knot_r'] * 0.62                                  # (the core + 2 rho = the low ring's faces exactly)
    sc = np.column_stack([np.maximum(spec['knot_d'] * fk - 2.0 * rk, 2e-4),
                          np.maximum(spec['knot_h'] * (0.80 + 0.20 * fk) - 2.0 * rk, 2e-4)])
    prog.begin_group(op=sdf.UNION, k=0.0008)
    prog.psweep(np.column_stack([xk, np.zeros_like(xk), np.full_like(xk, spec['loop_z'])]), core,
                rho=rk, scale=sc, normal=[0.0, 0.0, 1.0], name='knot')
    prog.roundbox([0.0, 0.0, spec['loop_z']], [0.5 * spec['knot_w'] + 0.0025, 0.5 * spec['knot_h'] + 0.0015,
                                               0.5 * spec['knot_d'] + 0.0015], r=0.0005, op=sdf.INTERSECT,
                  name='the knot\'s box')
    prog.end_group()


KNOT_HIDE = 0.0002          # a missed texel whose low point lies this deep inside the knot's solid is HIDDEN (a voxel)


def knot_solid(spec=SPEC):
    """the knot's solid alone: points (n, 3) -> its signed distance (metres). The loops' first rings lie 2.5 mm
    INSIDE the knot (the named exception of the low): their texels are buried under the wrap, no camera sees them,
    and the bake finds no high within the cage there (11-11 10:30: the boxed bake's gate failed on exactly those
    strips, b05b_miss_where.py). forge_bake passes them to bake.bake as `exclude`: hidden, out of the miss bar"""
    prog = sdf.Program()
    _knot_sdf(prog, spec, np.array([[0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [-0.5, -0.5]]))
    return prog.eval


def build_sdf(spec=SPEC, path=None):
    """the HIGH: the loops as swept LENS sections (sdf psweep: the measured outline, the puff, the folds rounded by
    rho), the knot a barrel sweep smooth-unioned onto them, the pleats carved, the band a shell, the hardware boxes"""
    prog = sdf.Program()
    rho = spec['rho']
    core = np.array([[0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [-0.5, -0.5]])          # x: thickness (z), y: height
    lcore = lens_core()
    # EACH SWEEP IS CUT BY ITS OWN BOX (11-11 09:05): a psweep's distance is exact only within its band of the
    # centreline; far away it read under 2 mm at 30 % of a 2 mm grid over the tie's bounds (max 11.7 mm anywhere), and
    # the voxel high's narrow band took nearly the whole box: CUDA out of memory in allocate_by_voxels. INTERSECT with a
    # box 1.5 mm round the sweep's own extent: the box's exact distance outside it, the sweep's at the surface
    for sx in (1.0, -1.0):
        xs = np.linspace(0.0045, loop_stations(spec)[-1], 56)
        H, T = height(spec, xs), thick(spec, xs)
        P = np.column_stack([sx * xs, np.zeros_like(xs), spec['loop_z'] + bow_z(spec, xs)])
        sc = np.column_stack([np.maximum(T - 2.0 * rho, 2e-4), np.maximum(H - 2.0 * rho, 2e-4)])
        prog.begin_group(op=sdf.UNION, k=0.0006)
        prog.psweep(P, lcore, rho=rho, scale=sc, normal=[0.0, 0.0, 1.0], name=f'loop {"L" if sx > 0 else "R"}')
        x0, x1 = 0.0045 - rho - 0.0015, float(xs[-1]) + rho + 0.0015
        y1 = 0.5 * float(H.max()) + 0.0015
        z0, z1 = spec['loop_z'] - 0.0045 - 0.0015, spec['loop_z'] + 0.0050 + 0.0015
        prog.roundbox([sx * 0.5 * (x0 + x1), 0.0, 0.5 * (z0 + z1)], [0.5 * (x1 - x0), y1, 0.5 * (z1 - z0)], r=0.0005,
                      op=sdf.INTERSECT, name='the loop\'s box')
        prog.end_group()
    # the knot: a barrel swept along x, smooth-unioned (the wrap pressed onto the loops)
    _knot_sdf(prog, spec, core)
    # the pleats: in 'groove' mode (the 12:10 bake) two shallow grooves carved on each loop's front, from the knot
    # outward, tapering (roundcone chains); in 'material' mode none here: the material pass draws them (gather_at)
    for sx in ((1.0, -1.0) if spec.get('pleat_mode', 'groove') == 'groove' else ()):
        for vv in spec['pleat_v']:
            # (11 points, 10 segments: at 5 the straight chords dipped 0.13 mm under the loop's curving front at each
            # joint, every 3.6 mm). The depth eases out as (1 - t)^pleat_fade (1.0: the 12:10 bake's linear fade)
            nseg = int(spec.get('pleat_seg', 10))
            fade = float(spec.get('pleat_fade', 1.0))
            xs_ = np.linspace(0.0068, 0.0068 + spec['pleat_len'] * spec['span'] * 0.5, nseg + 1)
            # (the front face at the pleat's height: the lens's z there, on the bowed mid-plane)
            front = lambda x_: (spec['loop_z'] + bow_z(spec, x_) + rho
                                + 0.5 * (thick(spec, x_) - 2.0 * rho) * lens(2.0 * vv * height(spec, x_)
                                                                            / max(height(spec, x_) - 2.0 * rho, 1e-5)))
            # ONE CONTINUOUS TAPER, THE CHAIN SUBTRACTED ONCE (11-11 10:50: each segment had run r -> 0.9 r and the
            # next began at r again, each smooth-subtracted on its own: the baked pleat read as a stack of rings in
            # the normal map, b05_maps_contact_black.png). Now the radius eases r -> 0.55 r along the pleat, the
            # segments hard-unioned in a group that folds into the loop by one smooth SUBTRACT
            prog.begin_group(op=sdf.SUBTRACT, k=0.0006)
            for i in range(len(xs_) - 1):
                pa, pb = xs_[i], xs_[i + 1]
                ya, yb = vv * height(spec, pa), vv * height(spec, pb)
                ra = spec['pleat_r'] * (1.0 - 0.45 * i / nseg)
                rb = spec['pleat_r'] * (1.0 - 0.45 * (i + 1) / nseg)
                za = front(pa) + ra - spec['pleat_depth'] * (1.0 - i / nseg) ** fade
                zb_ = front(pb) + rb - spec['pleat_depth'] * (1.0 - (i + 1) / nseg) ** fade
                prog.roundcone([sx * pa, ya, za], [sx * pb, yb, zb_], ra, rb, op=sdf.UNION, k=0.0, name='pleat')
            prog.end_group()
    # the band: a shell of its mid-surface strip (face_mask's strap, the same construction)
    P, W, O = path if path is not None else band_path(spec)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    g = np.linspace(0.0, s[-1], int(np.ceil(s[-1] / 0.001)) + 1)
    fi = lambda A: np.column_stack([np.interp(g, s, A[:, k]) for k in range(3)])
    Pd, Wd = fi(P), SC.unit(fi(W))
    hw = 0.5 * spec['band_w'] - 0.5 * spec['band_t']
    V = np.stack([Pd - hw * Wd, Pd, Pd + hw * Wd], 1).reshape(-1, 3)
    i = np.arange(len(Pd) - 1)[:, None] * 3 + np.arange(2)[None, :]
    q = np.stack([i, i + 3, i + 4, i + 1], -1).reshape(-1, 4)
    F = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    prog.shell(V, F, 0.5 * spec['band_t'], k=0.0, maxd=0.01, name='band')
    # the hardware: the slide frame (a box less its opening) and the hook plate
    j = N_BAND // 2
    T = SC.unit(P[j + 1] - P[j - 1])
    Rf = np.column_stack([W[j], T, O[j]])
    c = P[j] + O[j] * (0.5 * spec['band_t'] + 0.5 * spec['slide_wire'] + 0.0001)
    prog.roundbox(c, [0.5 * spec['slide_w'], 0.5 * spec['slide_l'], 0.5 * spec['slide_wire']], r=0.0003, axes=Rf,
                  name='slide')
    prog.roundbox(c, [0.5 * spec['slide_w'] - spec['slide_wire'], 0.5 * spec['slide_l'] - spec['slide_wire'], 0.003],
                  r=0.0002, axes=Rf, op=sdf.SUBTRACT, k=0.0002, name='slide opening')
    k = j + 3
    T2 = SC.unit(P[k + 1] - P[k - 1])
    c2 = P[k] + O[k] * (0.5 * spec['band_t'] + 0.5 * spec['hook_t'] + 0.0001)
    prog.roundbox(c2, [0.5 * spec['hook_w'], 0.5 * spec['hook_l'], 0.5 * spec['hook_t']], r=0.0003,
                  axes=np.column_stack([W[k], T2, O[k]]), name='hook')
    return prog


def bounds(spec=SPEC, pad=0.004):
    P, W, O = band_path(spec)
    lo = np.minimum(P.min(0) - 0.012, [-0.5 * spec['span'], -0.5 * spec['span'] * 0.45, -0.01])
    hi = np.maximum(P.max(0) + 0.012, [0.5 * spec['span'], 0.5 * spec['span'] * 0.45, 0.02])
    return lo - pad, hi + pad


# ------------------------------------------------------------------------------------------- the material pass
@wp.struct
class Surf:
    h: float
    col: wp.vec3
    rough: float
    metal: float
    fuzz: float
    mat: float
    zone: float
    wear: wp.vec4


@wp.func
def surf_at(p: wp.vec3, reg: int, at: wp.vec4, ao: float, aol: float, conv: float, texel: float,
            C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32), seed: int, full: int):
    """the surface at a point of region reg (at: the vertex attributes: x along the grain, round, side). full = 0: the
    height only"""
    o = Surf()
    h = float(0.0)
    col = C[0]
    rough = S[0]
    metal = float(0.0)
    fuzz = float(0.0)
    mat = float(0.0)
    zone = float(0.0)
    w_dust = float(0.0)
    w_hand = float(0.0)
    grime = wp.clamp(1.6 * (1.0 - ao) + 4.0 * wp.max(-aol, 0.0), 0.0, 1.0)
    if reg == 0 or reg == 1 or reg == 2:
        # SATIN: the floats along the grain (at[0] along the wing, at[1] round it), faded below 2 texels a pitch
        pitch = S[4]
        fl = wp.cos(6.2831853 * at[1] / pitch) * proc.smoothstep(2.0, 3.5, pitch / texel)
        h = S[5] * fl + 0.0000025 * proc.noise3(p / 0.003, seed + 3)
        if full == 1:
            # folds a little rougher (the pleats' valleys and the knot's wrap by the bake's AO); dust in them
            fold = wp.clamp(1.0 - ao, 0.0, 1.0)
            rough = S[0] + (S[1] - S[0]) * wp.clamp(2.0 * fold, 0.0, 1.0)
            w_dust = S[6] * grime * (0.5 + 0.5 * proc.noise3(p / 0.004, seed + 5))
            # handled: the knot and the loops' ends a touch smoother (fingers)
            w_hand = proc.smoothstep(0.035, 0.058, wp.abs(at[0])) * 0.5
            if reg == 1:
                w_hand = w_hand + 0.6
            rough = rough - 0.06 * w_hand
            col = C[0] * (1.0 + 0.04 * proc.noise3(p / 0.02, seed + 7))
            col = M.mix3(col, C[2], 0.35 * w_dust)
            fuzz = S[7]
            mat = 1.0
            if reg == 2:
                rough = S[2]
                zone = 1.0 / 3.0
    else:
        # nickel: the slide and the hook, METAL 1, a little grime in the corners
        h = 0.0000012 * proc.noise3(p / 0.0008, seed + 11)
        if full == 1:
            w_dust = 0.5 * S[6] * grime
            col = C[1] * (1.0 - 0.3 * w_dust)
            rough = S[3] + 0.25 * w_dust
            metal = 1.0
            zone = 2.0 / 3.0
    o.h = h
    o.col = col
    o.rough = rough
    o.metal = metal
    o.fuzz = fuzz
    o.mat = mat
    o.zone = zone
    o.wear = wp.vec4(0.0, 0.0, w_dust, w_hand)
    return o


@wp.func
def gather_at(p: wp.vec3, G: wp.array(dtype=wp.float32), Hs: wp.array(dtype=wp.float32)):
    """THE PLEATS AS SOFT GATHERS (11-11 15:10; soft_NOTES.md TECHNIQUES 15): the valley's weight 0..1 at an object
    point of a loop. Two lines run out from the knot at the fixed fractions G[6], G[7] of the loop's height (so they
    open with the butterfly's outline); across each line a bell exp(-u^2), u = the distance across over a half-width
    growing from G[3] at the knot to G[4] at the end; along it full depth under the knot and out to G[0], then fading
    as (1 - t)^G[5] over G[1]. No crease, no end cap: a gathered satin's valley. The surface height is -G[2] x this
    (on the loop's front: front_w). Hs: the loop's full height at n points over |x| in [0, G[8]]"""
    ax = wp.abs(p[0])
    t = wp.clamp((ax - G[0]) / G[1], 0.0, 1.0)
    amp = wp.pow(1.0 - t, G[5])
    w = G[3] + (G[4] - G[3]) * t
    n = Hs.shape[0]
    f = wp.clamp(ax / G[8], 0.0, 1.0) * float(n - 1)
    i0 = wp.min(int(f), n - 2)
    a = f - float(i0)
    H = Hs[i0] * (1.0 - a) + Hs[i0 + 1] * a
    u0 = (p[1] - G[6] * H) / w
    u1 = (p[1] - G[7] * H) / w
    return amp * wp.max(wp.exp(-u0 * u0), wp.exp(-u1 * u1))


@wp.func
def front_w(n: wp.vec3):
    """the loop's front face (its normal toward +Z): the gathers are drawn there, faded toward the folds"""
    return proc.smoothstep(0.15, 0.55, n[2])


def gather_tables(spec=SPEC, recipe=MATERIAL):
    """gather_at's two tables: G (11 numbers) and the loop's full height Hs at 96 points over |x| in [0, span / 2]"""
    ax = np.linspace(0.0, 0.5 * spec['span'], 96)
    G = np.array([spec['gather_x0'], spec['gather_len'] * spec['span'] * 0.5, spec['gather_depth'], spec['gather_w0'],
                  spec['gather_w1'], spec['gather_fade'], spec['pleat_v'][0], spec['pleat_v'][1], 0.5 * spec['span'],
                  recipe['gather_rough'], recipe['gather_occ']], np.float32)
    return G, np.asarray(height(spec, ax), np.float32)


@wp.kernel
def k_gather(P: wp.array(dtype=wp.vec3), G: wp.array(dtype=wp.float32), Hs: wp.array(dtype=wp.float32),
             out: wp.array(dtype=wp.float32)):
    tid = wp.tid()
    out[tid] = gather_at(P[tid], G, Hs)


def gather_eval(P, spec=SPEC, recipe=MATERIAL):
    """the gathers' valley weight at object points (n, 3) (front_w not applied): for previews and checks"""
    G, Hs = gather_tables(spec, recipe)
    out = wp.zeros(len(P), dtype=wp.float32)
    wp.launch(k_gather, dim=len(P), inputs=[wp.array(np.asarray(P, np.float32).reshape(-1, 3), dtype=wp.vec3),
                                            wp.array(G, dtype=wp.float32), wp.array(Hs, dtype=wp.float32), out])
    return out.numpy().astype(np.float64)


@wp.kernel
def k_tie(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
          ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
          d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
          d_aol: wp.array(dtype=wp.float32), d_conv: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3),
          S: wp.array(dtype=wp.float32), texel: float, seed: int, G: wp.array(dtype=wp.float32),
          Hs: wp.array(dtype=wp.float32), gather: int, o_alb: wp.array(dtype=wp.vec3),
          o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4),
          o_wear: wp.array(dtype=wp.vec4), o_hit: wp.array(dtype=wp.int32)):
    """face_mask.k_mask's loop (supersampled texels, the bake's normal + the tier's height as a surface gradient);
    gather = 1: the loops' soft gathers added to that height (gather_at), their valleys rougher and occluded"""
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    base = d_base[tid]
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_m = float(0.0)
    acc_k = wp.vec4(0.0)
    acc_w = wp.vec4(0.0)
    acc_o = float(0.0)
    hits = int(0)
    hb = float(0.0)
    have_hb = int(0)
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            if have_hb == 0:
                if base[3] > 0.5:
                    hb = wp.dot(wp.vec3(base[0], base[1], base[2]) - lo.p, lo.n)
                have_hb = 1
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            reg = lreg[lo.face]
            pb0 = lo.p + lo.n * hb
            sf = surf_at(pb0, reg, lo.attr, d_ao[tid], d_aol[tid], d_conv[tid], texel, C, S, seed, 1)
            gv0 = float(0.0)
            if gather == 1 and reg == 0:
                gv0 = gather_at(pb0, G, Hs) * front_w(lo.n)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = surf_at(pbx, reg, lx.attr, 1.0, 0.0, 0.0, texel, C, S, seed, 0).h
                hy = surf_at(pby, reg, ly.attr, 1.0, 0.0, 0.0, texel, C, S, seed, 0).h
                h0 = surf_at(pb0, reg, lo.attr, 1.0, 0.0, 0.0, texel, C, S, seed, 0).h
                if gather == 1 and reg == 0:
                    h0 = h0 - G[2] * gv0
                    hx = hx - G[2] * gather_at(pbx, G, Hs) * front_w(lx.n)
                    hy = hy - G[2] * gather_at(pby, G, Hs) * front_w(ly.n)
                g = M.surface_grad(pb0, pbx, pby, h0, hx, hy)
            nw = M.to_world(lo, tn_b)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + sf.col
            acc_r = acc_r + wp.clamp(sf.rough + G[9] * gv0, 0.04, 1.0)
            acc_o = acc_o + gv0
            acc_m = acc_m + sf.metal
            acc_k = acc_k + wp.vec4(sf.fuzz, sf.mat, sf.zone, 0.0)
            acc_w = acc_w + sf.wear
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(d_ao[tid] * (1.0 - G[10] * acc_o / fh), wp.clamp(rr, 0.0, 1.0),
                         wp.clamp(acc_m / fh, 0.0, 1.0))
    o_mask[tid] = acc_k / fh
    o_wear[tid] = acc_w / fh
    o_hit[tid] = 1


def material_tables(variant, recipe=MATERIAL):
    C = np.array([VARIANTS[variant]['satin'], recipe['metal'], recipe['dust']], np.float32)
    S = np.array([recipe['satin_rough'], recipe['satin_rough_fold'], recipe['band_rough'], recipe['metal_rough'],
                  recipe['weave_pitch'], recipe['weave_amp'], recipe['grime'], recipe['sheen']], np.float32)
    return C, S


def run_material(L, drivers, size, texel, variant, ss=2, recipe=MATERIAL, log=print, spec=SPEC):
    import time

    from .. import calib
    t0 = time.time()
    G, Hs = gather_tables(spec, recipe)
    gather = 1 if spec.get('pleat_mode', 'groove') == 'material' else 0
    pr = np.asarray(L['primary'], bool)
    F = L['F'][pr]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat') if k in drivers}
    Dv = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel)})
    C, S = material_tables(variant, recipe)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask, o_wear = wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_tie, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                    wp.array(np.asarray(L['region'], np.int32)[pr], dtype=wp.int32), Dv['normal'],
                                    Dv['ao'], Dv['base'], Dv['ao_local'], Dv['conv'], wp.array(C, dtype=wp.vec3),
                                    wp.array(S, dtype=wp.float32), float(texel), int(recipe['seed']),
                                    wp.array(G, dtype=wp.float32), wp.array(Hs, dtype=wp.float32), gather, o_alb,
                                    o_nrm, o_orm, o_mask, o_wear, o_hit])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    cov = np.asarray(o_hit.numpy()).reshape(size, size)[::-1] > 0
    maps = SC.finish_maps(img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4), img(o_wear, 4), cov, ZONES)
    log(f'[bow_tie] material ({variant}) {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in maps['palette_base'].items()))
    return maps


# ------------------------------------------------------------------------------------------------- fit data
def fit_data(variant, spec=SPEC, conform=None):
    """the tie's fit (remix.js's item contract): archetype 'tie', the authored width (recipe.ARCHETYPES['tie']:
    scale = the seat's width / this; THE WIDTH IS THE NECK'S, the band's rest diameter at the collar), the knot's back
    (the seat point), the band's rest path, the wearers' poses and band targets (conform)"""
    P, W, O = band_path(spec)
    rnd = lambda a: np.round(np.asarray(a, np.float64), 5).tolist()
    # (width: the catalog authors a tie at width 0.060 (recipe.ACCESSORIES['bow_tie']): here HALF THE SPAN, 60 mm, so
    # a remix seat's width (the axolotl's seat_tie 0.03) gives the scale as the recipe's contract says)
    return dict(archetype='tie', prop=VARIANTS[variant]['name'], variant=variant, width=round(0.5 * spec['span'], 5),
                span=spec['span'], seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0],
                                             left=[1.0, 0.0, 0.0]),
                knot=dict(width=spec['knot_w'], height=spec['knot_h'], depth=spec['knot_d']),
                band=dict(width=spec['band_w'], thickness=spec['band_t'], rest_neck_radius=spec['neck_r'],
                          stations=rnd(P), note='an ADJUSTABLE band: its path per wearer is a morph target named in '
                                                'conform[species].band'),
                variants={k: v['name'] for k, v in VARIANTS.items()}, conform=conform or {})


def make_low(size=2048, spec=SPEC, path=None, log=print):
    parts, info = build_low(spec, path, log)
    low = SC.assemble(parts)
    share = lambda nm: SHARES.get(nm, SHARES.get(nm.split('_')[0], 1.0))
    # (on a 1024 sheet the packer's raster at 2 texels a cell: the same absolute resolution as its 4 on a 2048 sheet;
    # at 4 the slivers between the loop's trapezoids went unused: 69.1 %)
    fill, place, ppm, order = SC.pack(low, {nm: share(nm) for nm in low['names']}, size=size,
                                      order=UV_ORDER, ppm=UV_PPM, g=2 if size <= 1024 else 4, tries=24, log=log)
    L = SC.low_arrays(low, place, ppm, size)
    log(f'[bow_tie] uv: {len(place)} primary islands of {len(low["names"])}; {ppm:.0f} px/m at {size} '
        f'({1000 / ppm:.3f} mm/texel), fill {fill * 100:.1f} %; order {order}')
    return L, low, info, dict(fill=fill, order=order, ppm=ppm)


def band_shape(L, low, hull, spec=SPEC, tilt=0.0):
    """the export's vertices and normals with the BAND round another wearer's neck (hull: (x, z) in the tie's frame;
    tilt: the band's plane turned about +X): the same construction, so the same vertices in the same order"""
    path = band_path(spec, hull=hull, tilt=tilt)
    b, _ = band(spec, path)
    hw = hardware(spec, path)
    V = L['V'].copy()
    N = L['N'].copy()
    for part in [b] + hw:
        pi = low['parts'].index(part['name'])
        qs = np.nonzero(low['part'] == pi)[0]
        src = np.asarray(part['Q'], np.int64)
        dst = low['Q'][qs]
        for f in range(len(dst)):
            for k in range(4):
                V[dst[f, k]] = part['V'][src[f, k]]
    from .. import bake
    N2, _ = bake.low_frames(V, L['F'], L['UV'], L['N'])
    return V, N2, path


def forge_bake(out_dir, size=2048, voxel_size=0.0002, band_mm=0.0015, ss=2, seed=7, spec=SPEC, log=print):
    import os
    import time

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    L, low, info, uvr = make_low(size, spec, log=log)
    np.savez_compressed(os.path.join(out_dir, 'low_bow_tie.npz'),
                        **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                        size=L['size'], quad_part=low['part'], Q=low['Q'], parts=np.array(low['parts']))
    prog = build_sdf(spec)
    f = np.abs(prog.eval(L['V']))
    log(f'[bow_tie] low on the block-out: |sdf| p50 {np.median(f) * 1e6:.0f} um, p99 '
        f'{np.percentile(f, 99) * 1e6:.0f} um, max {f.max() * 1e6:.0f} um')
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band_mm, log=log)
    pr = L['primary']
    ks = knot_solid(spec)
    res = bake.bake(G, L['V'], L['F'][pr], L['UV'], L['N'], L['TAN'], L['region'][pr], size=size, ss=ss, cage=0.003,
                    ao_r=0.012, cav_r=0.0015, n_thk=2, thk_max=0.008, seed=seed, log=log,
                    region_names=dict(enumerate(REGIONS)), exclude=lambda P_: ks(P_) < -KNOT_HIDE)
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position' and isinstance(v, np.ndarray)}
    np.savez_compressed(os.path.join(out_dir, 'drivers_bow_tie.npz'), **keep)
    log(f'[bow_tie] the bake is saved (drivers_bow_tie.npz) after {time.time() - t0:.0f}s')
    return L


MASKS_CHANNELS = ('R fuzz / sheen amount (the satin), G material (1 satin, 0 metal), B palette zone (0 satin, 1/3 band, '
                  '2/3 metal, 1 thread); RGB, no alpha')
DELIVER_SIZE = 512          # (11-11, OPTIMIZATION in soft_NOTES.md) the 1024 master sheet is 0.092 mm a texel at the
#                             tips, 4.7 texels under a pixel of the closest view (0.43 mm); 512 is 0.18 mm, 2.3 texels
#                             a pixel, a quarter of the GPU memory


def export(out_dir, variant, L, maps, spec=SPEC, conform=None, shapes=None, deliver=None):
    """one colour alone in its own glb (a look trial); the shipped tie is export_skins'"""
    import os
    name = VARIANTS[variant]['name']
    return SC.export_glb(os.path.join(out_dir, f'{name}.glb'), name, L, maps, fit_data(variant, spec, conform), ZONES,
                         MASKS_CHANNELS, 'tie', shapes=shapes, deliver=deliver)


def export_skins(out_dir, L, maps_by_variant, spec=SPEC, conform=None, shapes=None, deliver=DELIVER_SIZE):
    """THE SHIPPED TIE: ONE glb `bow_tie.glb`, its colours SKINS of one mesh (black the default, burgundy, navy;
    accessories_b5/STAGED.md F5, the cowboy hat's way): one normal map, and since the colours differ only in the satin's
    dye (material_tables: C[0]), the burgundy and navy skins share the default's ORM and masks (one index each)"""
    import os
    order = ['black'] + [v for v in maps_by_variant if v != 'black']
    fit = fit_data('black', spec, conform)
    fit['skins'] = order
    return SC.export_glb(os.path.join(out_dir, 'bow_tie.glb'), 'bow_tie', L, None, fit, ZONES, MASKS_CHANNELS, 'tie',
                         shapes=shapes, skins={v: maps_by_variant[v] for v in order}, deliver=deliver)
