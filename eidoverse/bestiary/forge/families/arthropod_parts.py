"""ARTHROPOD CLAY (B3; BEETLE_PLAN.md §4.2, §4.4-§4.5, §7 B3): one closed shell per sclerite, each its OWN sdf.Program
(never welded: overlapping shells in one field would fuse, plan §4.2.4), built at the author scale (x10, metres) from
the SPEC (life mm) and the rest chain (families/arthropod.py). The head's parts are heads/insect.py's
(head_parts); this module holds the body (pronotum, scutellum, elytra, venter), the legs, the joints between shells,
the right side and the assembly.

PARTS (92 at B1: plan §0.6 "92 with each funicle as one piece"): head, eye, mandible, scape, funicle, lamella_0..3,
palp_max, palp_lab (insect.py); pronotum, scutellum, elytron, venter; per leg coxa, trochanter, femur, tibia,
tarsus_1..5, claw_a, claw_b. Left (+x) and midline parts are built; every right part is its left part's MIRROR
(p_R = M p_L, limbed's rule): Part.mirror, its field f_R(p) = f_L(M p) (Part.eval), its mesh the left one's reflected.

DESCRIPTORS. Each part is a list of primitive descriptors in LIFE mm in the plan frame with the ground at y 0 (y = h +
the venter's clearance, arthropod.clearance): 'roundcone', 'roundbox', 'psweep', 'revolve' (the profile a function of
the grow), 'shell'. emit() writes one into a Program at the author scale, optionally GROWN (an exact offset: radii,
half extents and corner radius, rho, half-thickness, the revolve's own profile function) and with another op.

JOINTS. Each segment's proximal end is a condyle sunk SINK (life mm) into its parent (plan §4.2.2: about 0.24; B3's
gate 2-4 mm at x10) by one of two constructions:
  carve  the parent's program SUBTRACTS the child's primitives shrunk by SINK (hard), so no point of the child lies
         deeper than SINK inside the parent, and the child, set well inside, reaches it: sockets for the coxae, the
         head in the pronotum's emargination, the eyes and the mandibles in the head capsule
  seat   (thin children, whose radii are below SINK, and the leg and antenna chains) the child's proximal pole is put
         SINK inside the parent along the child's own axis, at the parent's surface crossing found on the parent's
         program (seat_along): on a capped tube that pole is the child's deepest point
Unlisted neighbours that would touch are carved apart with CLEAR (the femora and trochanters along the body: their
grooves). condyles(parts) lists the joints; b03 gates every listed pair's depth and every other pair's clearance.

THE CULLING. sdf.Program culls a blended member by its GROUP's k (PLAN.md, the wolf's and the beetle's checkers);
until the fix lands in sdf.Program every member blended by its own k has its box padded by that k (pad_member_boxes,
limbed.pad_cull_boxes's rule). The parts here use no multi-member groups, so each member's group k is its own; the
pad is kept as the lead asked.

UNITS: life mm in, metres out (spec['author_scale'] * 1e-3 per life mm: 0.01). [E] marks each estimate with the gate
that verifies it; the measured inputs are the SPEC's tagged leaves.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator

from .. import sdf as S_
from . import arthropod as AR
from ..heads import insect as HEAD

SINK = 0.28           # [E] each condyle's sink into its parent, life mm (plan §4.2: ~0.24; gate 0.2-0.4)
HEAD_SINK = 0.31      # [E] the scape's and the palps' sink into the head and the head's into the pronotum's socket (B3h:
#                       b03 reads a depth in the parent's field, the GRID's values over its proved divisor; the B3h head's
#                       exact unblurred 0.025 mm field divides by 1.408 (b3g's blurred 0.05 by 1.197), so the true 0.28 read
#                       1.89-1.99 at x10, under the gate's 2.0; 0.31 reads ~2.1-2.2)
CLEAR = 0.06          # [E] the least gap where an unlisted neighbour is carved apart, life mm
COLLAR_K = 0.15       # [E] the head's socket in the pronotum's collar carved smooth by this blend, life mm
M_MIRROR = np.diag([-1.0, 1.0, 1.0])
UP = np.array([0.0, 1.0, 0.0])


# --------------------------------------------------------------------------------------------- descriptors
def roundcone(a, b, ra, rb, op=S_.UNION, k=0.0, name=''):
    return dict(kind='roundcone', a=np.asarray(a, np.float64), b=np.asarray(b, np.float64), ra=float(ra),
                rb=float(rb), op=op, k=float(k), name=name)


def roundbox(c, half, r, axes=None, op=S_.UNION, k=0.0, name=''):
    R = np.eye(3) if axes is None else np.asarray(axes, np.float64)
    return dict(kind='roundbox', c=np.asarray(c, np.float64), half=np.asarray(half, np.float64), r=float(r), axes=R,
                op=op, k=float(k), name=name)


def psweep(points, sections, rho, key=0.0, scale=1.0, twist=0.0, normal=None, op=S_.UNION, k=0.0, name=''):
    return dict(kind='psweep', points=np.asarray(points, np.float64), sections=np.asarray(sections, np.float64),
                rho=float(rho), key=key, scale=scale, twist=twist, normal=normal, op=op, k=float(k), name=name)


def revolve(profile_fn, center, axis, op=S_.UNION, k=0.0, name=''):
    """profile_fn(grow) -> the closed (r, y) profile of the solid offset by grow (life mm)"""
    return dict(kind='revolve', profile_fn=profile_fn, center=np.asarray(center, np.float64),
                axis=np.asarray(axis, np.float64), op=op, k=float(k), name=name)


def shell(V, F, ht, op=S_.UNION, k=0.0, name=''):
    """ht: one half-thickness or one per vertex (life mm)"""
    ht = float(ht) if np.ndim(ht) == 0 else np.asarray(ht, np.float64)
    return dict(kind='shell', V=np.asarray(V, np.float64), F=np.asarray(F, np.int32), ht=ht, op=op,
                k=float(k), name=name)


def grid(origin, cell, values, op=S_.UNION, k=0.0, name=''):
    """B3c: a sampled signed distance (life mm, negative inside) on an axis-aligned box from origin (life mm, world)
    at cell mm (the head's volume, heads/insect_hull.py): the staged GRID member (work/bestiary/patches/sdf_grid.md:
    sdf.Program.grid, which the forge's sdf.py has not landed; b03 loads the staged module). Grown by subtracting the
    grow from its values (its inside far field is clamped deeper than any grow it takes)"""
    return dict(kind='grid', origin=np.asarray(origin, np.float64), cell=float(cell),
                values=np.asarray(values, np.float32), op=op, k=float(k), name=name)


def group(members, op=S_.UNION, k=0.0, name=''):
    """a part built by booleans among its own members (B3b: the mandible, a plan prism intersected with a side prism
    less two cutters): sdf.Program's group, the members combined by their own ops first, the whole folded into the
    program by op and k. Grown as a solid: its solid members by the grow, its SUBTRACT members (cutters) by minus it
    ((A n B - C) shrunk by r = (A - r) n (B - r) - (C + r)), so a parent's socket carve takes the whole part"""
    return dict(kind='group', members=list(members), op=op, k=float(k), name=name)


def mirror_desc(d):
    """the descriptor reflected across the sagittal plane (x -> -x)"""
    e = dict(d)
    k = d['kind']
    if k == 'roundcone':
        e['a'], e['b'] = M_MIRROR @ d['a'], M_MIRROR @ d['b']
    elif k == 'roundbox':
        e['c'], e['axes'] = M_MIRROR @ d['c'], M_MIRROR @ d['axes']
    elif k == 'psweep':
        e['points'] = d['points'] @ M_MIRROR
        if d['normal'] is not None:
            nv = np.asarray(d['normal'], np.float64)
            e['normal'] = nv @ M_MIRROR if nv.ndim == 2 else M_MIRROR @ nv
        e['sections'] = d['sections'] * np.array([1.0, -1.0])     # the binormal t x n flips under a reflection
        e['twist'] = -np.asarray(d['twist'], np.float64) if np.ndim(d['twist']) else -float(d['twist'])
    elif k == 'revolve':
        e['center'], e['axis'] = M_MIRROR @ d['center'], M_MIRROR @ d['axis']
    elif k == 'shell':
        e['V'], e['F'] = d['V'] @ M_MIRROR, d['F'][:, ::-1].copy()
    elif k == 'group':
        e['members'] = [mirror_desc(m) for m in d['members']]
    elif k == 'grid':
        nx = d['values'].shape[0]
        e['values'] = d['values'][::-1].copy()
        e['origin'] = np.array([-(d['origin'][0] + (nx - 1) * d['cell']), d['origin'][1], d['origin'][2]])
    return e


def emit(prog, d, s, grow=0.0, op=None, k=None):
    """write descriptor d into prog at s metres per life mm, offset by grow (life mm; < 0 shrinks), with op and k
    (life mm) overriding its own. Returns the primitive's index"""
    o = d['op'] if op is None else op
    kk = (d['k'] if k is None else k) * s
    kind = d['kind']
    nm = d.get('name', '')
    if kind == 'roundcone':
        ra, rb = d['ra'] + grow, d['rb'] + grow
        assert min(ra, rb) > 0.0, f'{nm}: a round cone shrunk past its radius'
        return prog.roundcone(d['a'] * s, d['b'] * s, ra * s, rb * s, op=o, k=kk, name=nm)
    if kind == 'roundbox':
        h = d['half'] + grow
        r = max(d['r'] + grow, 0.0)
        assert h.min() > 0.0, f'{nm}: a round box shrunk past its half extents'
        return prog.roundbox(d['c'] * s, h * s, min(r, h.min()) * s, axes=d['axes'], op=o, k=kk, name=nm)
    if kind == 'psweep':
        rho = d['rho'] + grow
        sec = d['sections']
        scale = d['scale']
        if rho < 0.0 and np.ndim(sec) == 3 and len(sec) > 1 and not np.ndim(scale):
            # a loft through station sections (loft_sections) past its corner radius: each station's core offset
            # inward by the deficit along its own normals (the scale rule below, by the GLOBAL half extent, shrank the
            # head's small back stations by 0.21 of SINK's 0.28: its socket in the pronotum's collar held 2.0 at x10);
            # B3e: its convex corners first rounded to the deficit (round_convex: the pronotum's carina)
            sec = np.stack([offset_closed(round_convex(c_, -rho + 0.02), rho) for c_ in sec])
            rho = 0.0
        if rho < 0.0:
            # past its corner radius: the scaled core shrinks by the deficit (each axis by the deficit over the core's
            # half extent there: exact for a box-like core, a close inward offset for the rounded cores used here)
            ext = np.abs(sec.reshape(-1, 2)).max(0)
            sc = np.broadcast_to(np.asarray(scale, np.float64), (len(d['points']), 2)) if np.ndim(scale) else \
                np.full((len(d['points']), 2), float(scale))
            scale = np.maximum(sc + rho / ext[None, :], 0.02 * sc)
            rho = 0.0
        # B3c: an explicit band (life mm) past the reach where the descriptor gives one (the mandible arm's knee: the
        # default band, the reach again, doubled the bend's share of the divisor, 1.7 against 1.4)
        bd = None if d.get('band') is None else float(d['band']) * s
        return prog.psweep(d['points'] * s, sec * s, rho=rho * s, key=d['key'], scale=scale, twist=d['twist'],
                           normal=d['normal'], band=bd, op=o, k=kk, name=nm)
    if kind == 'revolve':
        return prog.revolve(np.asarray(d['profile_fn'](grow)) * s, d['center'] * s, d['axis'], op=o, k=kk, name=nm)
    if kind == 'shell':
        ht = np.asarray(d['ht'], np.float64) + grow
        assert np.min(ht) > 0.0, f'{nm}: a shell shrunk past its half-thickness'
        return prog.shell(d['V'] * s, d['F'], ht * s, op=o, k=kk, name=nm)
    if kind == 'group':
        prog.begin_group(op=o, k=kk)
        idx = None
        for m in d['members']:
            g = -grow if m['op'] == S_.SUBTRACT else grow           # a cutter grows as the solid shrinks
            i = emit(prog, m, s, grow=g)
            idx = i if idx is None else idx
        prog.end_group()
        return idx
    if kind == 'grid':
        assert hasattr(prog, 'grid'), (f'{nm}: a GRID member needs the staged sdf module (work/bestiary/patches/'
                                       f'scratch_grid/sdf.py: b03_clay.py --sdf auto loads it)')
        return prog.grid(d['origin'] * s, np.eye(3), d['cell'] * s, (d['values'] - grow) * s, op=o, k=kk, name=nm)
    raise ValueError(kind)


def shrink_desc(d, delta):
    """a round cone or round box descriptor offset inward by delta (life mm) in its own terms (B3d: a socket's cutter
    pre-shrunk, so emitted with a carve's grow it is the socket)"""
    if d['kind'] == 'roundcone':
        return dict(d, ra=d['ra'] - delta, rb=d['rb'] - delta)
    if d['kind'] == 'roundbox':
        return dict(d, half=np.asarray(d['half'], np.float64) - delta, r=max(d['r'] - delta, 0.0))
    raise ValueError(f'shrink_desc: {d["kind"]}')


def carvable(d, grow):
    """whether descriptor d can be offset by grow (< 0: shrunk) and still be a solid: the thin ones (a tooth's tip, a
    lamella's stalk) stay out of a parent's socket carve and are SEATED instead"""
    if d['kind'] == 'group':
        return d['op'] == S_.UNION and all(m['op'] == S_.SUBTRACT or carvable(dict(m, op=S_.UNION), grow)
                                           for m in d['members'])
    if d['op'] != S_.UNION:
        return False
    if d['kind'] == 'roundcone':
        return min(d['ra'], d['rb']) + grow > 0.02
    if d['kind'] == 'roundbox':
        return d['half'].min() + grow > 0.02
    if d['kind'] == 'shell':
        return float(np.min(d['ht'])) + grow > 0.02
    if d['kind'] == 'psweep' and d['rho'] + grow < 0.0:
        sc = np.asarray(d['scale'], np.float64)
        return float(sc.min()) > -(d['rho'] + grow) + 0.02
    if d['kind'] == 'grid':
        return float(d['values'].min()) < grow - 0.05                # its clamped inside reaches past the shrink
    return True


def pad_member_boxes(prog):
    """pad each blended member's culling box by its own blend k (in place): limbed.pad_cull_boxes's rule, until
    sdf.Program pads by the member's own k (the program culls by its group's)"""
    for i in range(len(prog.kind)):
        k = float(prog.k[i])
        if k > 0.0 and prog.par[i][24] > -1.0e8:
            prog.par[i][24:27] -= k
            prog.par[i][27:30] += k
    prog._dev = None


def program_of(descs, s, extra=()):
    """a Program of descriptors, then extra (descriptor, grow, op[, k]) carves (k life mm, hard when left out); boxes
    padded"""
    p = S_.Program()
    for d in descs:
        emit(p, d, s)
    for e in extra:
        emit(p, e[0], s, grow=e[1], op=e[2], k=e[3] if len(e) > 3 else 0.0)
    pad_member_boxes(p)
    return p


def field_mm(descs, s):
    """a quick evaluator in life mm for seating: f(points (n, 3) life mm) -> life mm"""
    p = program_of(descs, s)
    return lambda P: p.eval(np.asarray(P, np.float64).reshape(-1, 3) * s).astype(np.float64) / s


def seat_along(f, p0, t, start=-3.0, end=6.0, n=901):
    """the distance along t from p0 where the parent field f (life mm) last crosses from inside to outside, scanning
    start..end (life mm), refined by bisection; None if the axis never leaves the parent"""
    t = np.asarray(t, np.float64) / np.linalg.norm(t)
    ss = np.linspace(start, end, n)
    v = f(np.asarray(p0)[None, :] + ss[:, None] * t[None, :])
    hit = [i for i in range(n - 1) if v[i] < 0.0 <= v[i + 1]]
    if not hit:
        return None
    a, b = ss[hit[-1]], ss[hit[-1] + 1]
    for _ in range(40):
        m = 0.5 * (a + b)
        if f((np.asarray(p0) + m * t)[None, :])[0] < 0.0:
            a = m
        else:
            b = m
    return 0.5 * (a + b)


# --------------------------------------------------------------------------------------------- small helpers
def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def pchip(xs, ys):
    """a PCHIP through (x, y) stations, any order"""
    xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    o = np.argsort(xs)
    return PchipInterpolator(xs[o], ys[o], extrapolate=True)


def perp_normal(T, ref=UP):
    """ref made perpendicular to each tangent (unit)"""
    T = np.asarray(T, np.float64)
    N = ref[None, :] - (T @ ref)[:, None] * T
    return N / np.linalg.norm(N, axis=1, keepdims=True)


def superellipse(n=64, p=4.0):
    """a closed unit superellipse |x|^p + |y|^p = 1, counter-clockwise from +x"""
    a = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    c, s_ = np.cos(a), np.sin(a)
    return np.column_stack([np.sign(c) * np.abs(c) ** (2.0 / p), np.sign(s_) * np.abs(s_) ** (2.0 / p)])


def mirror_x(half):
    """a closed polygon from its x >= 0 half given top to bottom (the first point on +y's axis, the last on -y's)"""
    half = np.asarray(half, np.float64)
    other = half[-2:0:-1] * np.array([-1.0, 1.0])
    poly = np.vstack([half, other])
    return poly[::-1]                       # counter-clockwise


LOFT_SHIFTS = (-2.0, -1.0, 0.0, 1.0, 2.0)
LOFT_SLOPE = 0.5       # the steepest a lofted part's half-width or half-height may change along z: the PSWEEP divides
#                        its WHOLE field by its steepest segment's bound, which adds the scale's change and the shift's
#                        (the gradient gate's p1 >= 0.6; b03's first clay: divisors 2.4-4.2 at the [E] ends)
LINE_SMOOTH = 0.6      # [E] the measured top lines (outline.dorsal_line) Gaussian-smoothed over this much z (life mm)
#                        before lofting: the contour's +-0.03 mm pixel noise prints as bands across a glossy dome


def smooth_rows(z, v, sigma):
    """values at stations z (any order) Gaussian-smoothed over sigma life mm of z (resampled at 0.05 mm, then read
    back at the stations)"""
    from scipy.ndimage import gaussian_filter1d
    z, v = np.asarray(z, np.float64), np.asarray(v, np.float64)
    o = np.argsort(z)
    zz = np.arange(z[o][0], z[o][-1] + 1e-9, 0.05)
    vv = gaussian_filter1d(np.interp(zz, z[o], v[o]), sigma / 0.05, mode='nearest')
    return np.interp(z, zz, vv)


def smooth_core(half, n=72):
    """a closed core polygon from its control half (x >= 0, top to bottom) through a periodic smoothing spline: the
    PSWEEP's section is the polygon offset by rho, so a coarse polygon prints its facets"""
    from scipy.interpolate import splev, splprep
    P = mirror_x(half)
    tck, _ = splprep([np.append(P[:, 0], P[0, 0]), np.append(P[:, 1], P[0, 1])], s=0.0, per=1, k=3)
    x, y = splev(np.linspace(0.0, 1.0, n, endpoint=False), tck)
    Q = np.column_stack([x, y])
    a = np.sum(Q[:, 0] * np.roll(Q[:, 1], -1) - np.roll(Q[:, 0], -1) * Q[:, 1])
    return Q if a > 0 else Q[::-1]


def lipschitz_below(z, v, smax):
    """the largest function <= v whose slope along z stays within smax: min_j (v_j + smax |z - z_j|)"""
    z, v = np.asarray(z, np.float64), np.asarray(v, np.float64)
    return np.min(v[None, :] + smax * np.abs(z[:, None] - z[None, :]), axis=1)


# --------------------------------------------------------------------------------------------- measured outlines
# The rules of the SPEC's B3b rows (stag_beetle.SPEC outline.mand_plan, outline.mand_fork; b00_spec.py recomputes each
# from the photo strand's tracings, passed in as research/beetle_scripts/b3_outlines' Frames and module)
def dense_loop(P, step):
    """a closed polygon's boundary sampled every `step` (or closer)"""
    P = np.asarray(P, np.float64)
    seg = np.vstack([P, P[:1]])
    out = []
    for a, b in zip(seg[:-1], seg[1:]):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out.append(a + np.outer(np.arange(n) / n, b - a))
    return np.vstack(out)


def polygon_sdf(P, X, step):
    """the signed distance of points X (n, 2) to the closed polygon P (negative inside), to about step / 2"""
    from matplotlib.path import Path
    from scipy.spatial import cKDTree
    d, _ = cKDTree(dense_loop(P, 0.5 * step)).query(X)
    return np.where(Path(P).contains_points(X), -d, d)


def resample_loop(P, n):
    """a closed polygon resampled to n points evenly by arc length, from its first point"""
    Q = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])])


def mean_outline(A, B, n_out=520, step=0.0008, smooth=2.0):
    """the mean of two closed outlines in one frame (B3b's one mirrored mandible: M1's left and mirrored right in
    their chord frames): B fitted rigidly onto A (a turn about B's centroid and a shift, minimising the mean of
    min(d, 0.06)^2 of B's points to A's boundary, three starts: the checker's mand_mirror.py rule), then the zero set
    of the mean of the two signed distance fields on a grid of `step` (the mean field Gaussian-smoothed over `smooth`
    cells: a slit where one side's small tooth meets the other's gap, 26 um wide, closes), counter-clockwise,
    resampled to n_out points evenly by arc length from the point nearest the origin. Returns (mean (n_out, 2),
    dict(turn deg, shift, R_fit))"""
    from scipy.ndimage import gaussian_filter
    from scipy.optimize import minimize
    from scipy.spatial import cKDTree
    from skimage.measure import find_contours
    A, B = np.asarray(A, np.float64), np.asarray(B, np.float64)
    tree = cKDTree(dense_loop(A, 0.002))
    cB = B.mean(0)

    def moved(x):
        a = np.radians(x[0])
        R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        return cB + (B - cB) @ R.T + x[1:]

    def cost(x):
        d, _ = tree.query(moved(x))
        return float(np.mean(np.minimum(d, 0.06) ** 2))
    best = min((minimize(cost, x0, method='Nelder-Mead', options=dict(xatol=1e-7, fatol=1e-14, maxiter=4000))
                for x0 in ([0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [-2.0, 0.0, 0.0])), key=lambda r: r.fun)
    Bf = moved(best.x)
    lo = np.minimum(A.min(0), Bf.min(0)) - 0.03
    hi = np.maximum(A.max(0), Bf.max(0)) + 0.03
    xs = np.arange(lo[0], hi[0] + step, step)
    ys = np.arange(lo[1], hi[1] + step, step)
    X = np.stack(np.meshgrid(xs, ys, indexing='ij'), -1).reshape(-1, 2)
    M = (0.5 * (polygon_sdf(A, X, step) + polygon_sdf(Bf, X, step))).reshape(len(xs), len(ys))
    C = max(find_contours(gaussian_filter(M, smooth, mode='nearest'), 0.0), key=len)
    P = np.column_stack([lo[0] + C[:, 0] * step, lo[1] + C[:, 1] * step])
    if np.allclose(P[0], P[-1]):
        P = P[:-1]
    if np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]) < 0.0:
        P = P[::-1]
    P = np.roll(P, -int(np.argmin(np.linalg.norm(P, axis=1))), axis=0)
    return resample_loop(P, n_out), dict(turn=float(best.x[0]), shift=best.x[1:].copy(), R_fit=Bf)


def m1_mandible_loops(F, B3O):
    """M1d's two closed mandible outlines (the photo strand's md_*_outer stretch from the outer base to the tip, its
    md_*_inner stretch from the tip to the inner base, then the base edge back to the outer base, where the head's
    front margin covers the mandible), each in its own chord frame (b3_outlines.chord_frame: u along the outer base ->
    tip chord, v + away from the midline, both / that side's chord): the right side so mirrored. F: b3_outlines.Frames;
    B3O: the module (its stretch and chord_frame)"""
    pts, fc = F.ra['points'], F.sa['from_contour']
    out = dict(chord={})
    for s, side in (('L', 1), ('R', -1)):
        P = []
        for key in (f'md_{s}_outer', f'md_{s}_inner'):
            sp = fc[key]
            via = np.array(pts[sp['via']] if isinstance(sp['via'], str) else sp['via'], np.float64)
            P.append(F.dors(B3O.stretch(F.Ca, np.array(pts[sp['from']], np.float64),
                                        np.array(pts[sp['to']], np.float64), via)))
        o, i = P
        if np.linalg.norm(o[0] - F.dpt(f'mand_base_out_{s}')) > np.linalg.norm(o[-1] - F.dpt(f'mand_base_out_{s}')):
            o = o[::-1]
        if np.linalg.norm(i[0] - F.dpt(f'mand_tip_{s}')) > np.linalg.norm(i[-1] - F.dpt(f'mand_tip_{s}')):
            i = i[::-1]
        uv, L = B3O.chord_frame(F.dpt(f'mand_base_out_{s}'), F.dpt(f'mand_tip_{s}'), np.vstack([o, i]), side)
        out[s], out['chord'][s] = uv, L
    return out


def m1_fork_edge(F, B3O, step=0.1):
    """M1l's fork edge, the lower front edge of the mandible's end from its tip (mand_tip) back to the tine's lowest
    point (md_tine_b): the contour stretch between them the short way (via their midpoint), in the plan frame (z, h),
    resampled every `step` mm of arc from the tip"""
    a = np.array(F.rc['points']['mand_tip'], np.float64)
    b = np.array(F.rc['points']['md_tine_b'], np.float64)
    P = F.lat(B3O.stretch(F.Cc, a, b, 0.5 * (a + b)))
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], max(3, int(np.ceil(s[-1] / step)) + 1))
    return np.column_stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])])


def loft(z, half, top, bot, core, rho, clear, x=0.0, op=S_.UNION, k=0.0, name='', tilt=False, tilt_fit=None):
    """a body part lofted along z on a STRAIGHT centreline (PSWEEP's bound holds the centreline's curvature x the
    section's reach under 1: a wide section must ride a straight line), its section the unit core scaled per node to
    the half-width and half-height, and moved up or down to the measured top and bottom by blending copies of the
    core shifted by LOFT_SHIFTS core heights (a blend of translated copies is the translated core). The half-width
    and half-height are held to LOFT_SLOPE (lipschitz_below: they only shrink where a station is steeper), the mid
    line kept. z ascending; half, top, bot (h above the venter) per z; life mm"""
    z, half, top, bot = (np.asarray(v, np.float64) for v in (z, half, top, bot))
    mid = 0.5 * (top + bot)
    sv = lipschitz_below(z, 0.5 * (top - bot), LOFT_SLOPE) - rho
    half = lipschitz_below(z, half, LOFT_SLOPE)
    assert sv.min() > 0.05 and (half - rho).min() > 0.05, f'{name}: a section thinner than its corner radius'
    # tilt: the straight centreline on the mid line's linear trend (the shifts, in section heights, stay small where
    # the section is thin: the bound multiplies a scale change by the shifted core's reach); it leans the end faces
    # (normal to the centreline), so only a part whose ends are buried takes it (the venter)
    # (tilt_fit: the z range the trend is fitted on, B3e: the venter's run past its tip kept out of it)
    fz = np.ones(len(z), bool) if tilt_fit is None else (z >= tilt_fit[0]) & (z <= tilt_fit[1])
    b1, b0 = np.polyfit(z[fz], mid[fz], 1) if tilt else (0.0, float(np.mean(mid)))
    c0 = b0 + b1 * z
    key = np.clip((mid - c0) / sv - LOFT_SHIFTS[0], 0.0, len(LOFT_SHIFTS) - 1.0)
    keys = np.stack([core + np.array([0.0, s]) for s in LOFT_SHIFTS])
    P = np.column_stack([np.full_like(z, x), c0 + clear, z])
    return psweep(P, keys, rho, key=key, scale=np.column_stack([half - rho, sv]), normal=[1.0, 0.0, 0.0], op=op, k=k,
                  name=name)


def loft_sections(zs, cores, rho, y0, name='', op=S_.UNION, k=0.0, n_nodes=None, dense=0.1, soften=0.35):
    """a PSWEEP through station SECTIONS (B3b: the pronotum and the head capsule): cores (K, M, 2), each station's
    closed CORE polygon (x, h world-y) at the K ascending stations zs (the section is the core offset by rho), point i
    of each matching point i of the next; a straight centreline along z at x 0 and world height y0, the cores relative
    to it as the keys, blended linearly between stations, then resampled every `dense` mm and each point's path along
    z softened by a gaussian of `soften` mm (blended linearly between the stations alone, the surface was piecewise
    linear along z and its creases at the stations showed as bands in the renders, B3b check; a monotone cubic
    instead steepened the loft's divisor 1.28 -> 1.37, the softening cannot steepen it); each node's key its index by
    its z; the end faces rho past the end stations (flat, rounded by rho). The PSWEEP divides its field by the
    steepest key change"""
    from scipy.ndimage import gaussian_filter1d
    zs = np.asarray(zs, np.float64)
    keys = np.asarray(cores, np.float64) - np.array([0.0, y0])
    if dense:
        zk = np.linspace(zs[0], zs[-1], int(np.ceil((zs[-1] - zs[0]) / dense)) + 1)
        ki = np.interp(zk, zs, np.arange(len(zs), dtype=np.float64))
        a = np.minimum(ki.astype(int), len(zs) - 2)
        keys = keys[a] + (keys[a + 1] - keys[a]) * (ki - a)[:, None, None]
        if soften:
            keys = gaussian_filter1d(keys, soften / (zk[1] - zk[0]), axis=0, mode='nearest')
        zs = zk
    K = len(zs)
    n = n_nodes or max(24, int(np.ceil((zs[-1] - zs[0]) / 0.08)) + 1)
    z = np.linspace(zs[0], zs[-1], n)
    key = np.clip(np.interp(z, zs, np.arange(K, dtype=np.float64)), 0.0, K - 1.0)
    P = np.column_stack([np.zeros(n), np.full(n, y0), z])
    return psweep(P, keys, rho, key=key, scale=1.0, normal=[1.0, 0.0, 0.0], op=op, k=k, name=name)


def round_convex(poly, r_min, iters=200):
    """B3e: a closed polygon's convex corners sharper than r_min rounded IN (each such point pulled toward its
    neighbours' mean, repeated until every convex turn's circle through a point and its two neighbours is r_min or
    rounder): the same points in the same order (a loft's keys keep their correspondence), so an inward offset_closed
    by up to r_min cannot cross itself there (the pronotum's carina, rho 0.08, shrunk by SINK as the venter's cutter:
    B3e's first full run, 'keys ... cross themselves')"""
    P = np.array(poly, np.float64)
    ccw = np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]) > 0
    for _ in range(iters):
        a, b = np.roll(P, 1, axis=0), np.roll(P, -1, axis=0)
        u, v = P - a, b - P
        cr = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
        convex = cr > 0 if ccw else cr < 0
        R = (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) * np.linalg.norm(b - a, axis=1)
             / np.maximum(2.0 * np.abs(cr), 1e-30))
        sharp = convex & (R < r_min)
        if not sharp.any():
            break
        P[sharp] = 0.5 * P[sharp] + 0.25 * (a[sharp] + b[sharp])
    return P


def offset_closed(poly, d):
    """a closed polygon's points moved d along their outward normals (d < 0: inward; the mean of the two edges'
    normals, normalised): an offset for a smooth polygon whose convex turns are rounder than |d|"""
    P = np.asarray(poly, np.float64)
    ccw = np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]) > 0
    e = np.roll(P, -1, axis=0) - P
    n_e = np.column_stack([e[:, 1], -e[:, 0]]) * (1.0 if ccw else -1.0)    # outward edge normals
    n_e /= np.linalg.norm(n_e, axis=1, keepdims=True)
    n_v = n_e + np.roll(n_e, 1, axis=0)
    n_v /= np.linalg.norm(n_v, axis=1, keepdims=True)
    return P + d * n_v


def section_half(top, mid, bot, half, p_top=2.4, q_top=2.0, p_bot=1.7, q_bot=2.0, m=120):
    """the right half (x >= 0) of a closed section from the top centre (0, top) to the bottom centre (0, bot): a
    superellipse arc out to its widest point (half, mid), then another in to the bottom: m + 1 points"""
    ma = m // 2
    t = np.linspace(0.0, 0.5 * np.pi, ma + 1)
    up = np.column_stack([half * np.sin(t) ** (2.0 / p_top), mid + (top - mid) * np.cos(t) ** (2.0 / q_top)])
    s = np.linspace(0.0, 0.5 * np.pi, m - ma + 1)[1:]
    dn = np.column_stack([half * np.cos(s) ** (2.0 / p_bot), mid - (mid - bot) * np.sin(s) ** (2.0 / q_bot)])
    return np.vstack([up, dn])


def pron_section_half(top, keel, bot, half, lip, recess, lift, p_top=2.2, q_top=1.7, p_bot=1.8, q_bot=1.8, m=(70, 10,
                                                                                                          12, 60),
                      cove=0.0, flank=70.0):
    """B3e, the pronotum's section (right half, top centre to bottom centre; a CORE, the section is it grown by rho):
    the DISC a convex superellipse arc from the top (0, top) down to its foot (half - lip[0], keel + lip[1]); the CARINA
    the margin's edge (half, keel), a ridge: the disc's foot runs on down and out to it (a quadratic, vertical at the
    foot, arriving at `flank` deg below the horizontal: a narrowly reflexed margin), the lip's underside leaves it
    straight in and down to (half - recess, keel - lift); under it the HYPOMERON SET IN: a concave cove (radius `cove`)
    turning the underside straight down, then a convex arc down and in to the bottom (0, bot); no corner but the
    carina's (B3d: a horizontal lip, its edge a 180 deg turn grown by rho 0.3: a soft bead). m: the points per stretch
    (disc, flank, underside, hypomeron)"""
    lx, ly = lip
    xf, yf = half - lx, keel + ly
    t = np.linspace(0.0, 0.5 * np.pi, m[0] + 1)
    disc = np.column_stack([xf * np.sin(t) ** (2.0 / p_top), yf + (top - yf) * np.cos(t) ** (2.0 / q_top)])
    a = max(ly - lx * np.tan(np.radians(flank)), 0.0)          # the control point under the foot
    s = np.linspace(0.0, 1.0, m[1] + 1)[1:, None]
    P0, Q, P2 = np.array([xf, yf]), np.array([xf, yf - a]), np.array([half, keel])
    upper = (1.0 - s) ** 2 * P0 + 2.0 * s * (1.0 - s) * Q + s * s * P2
    xh, yh = half - recess, keel - lift
    s = np.linspace(0.0, 1.0, m[2] + 1)[1:, None]
    under = P2 + s * (np.array([xh, yh]) - P2)
    parts = [disc, upper, under]
    d0 = unit(np.array([xh, yh]) - P2)
    if cove > 0.0:
        # the cove: tangent to the underside, turning (about a centre outside the body) until it runs straight down
        n0 = np.array([-d0[1], d0[0]])                           # left of the travel: outside the body
        C = np.array([xh, yh]) + cove * n0
        a0, a1 = np.arctan2(-n0[1], -n0[0]), np.pi
        th = np.linspace(a0, a1, 13)[1:]
        parts.append(C + cove * np.column_stack([np.cos(th), np.sin(th)]))
        xh, yh = parts[-1][-1]
    u = np.linspace(0.0, 0.5 * np.pi, m[3] + 1)[1:]
    parts.append(np.column_stack([xh * np.cos(u) ** (2.0 / p_bot), yh - (yh - bot) * np.sin(u) ** (2.0 / q_bot)]))
    return np.vstack(parts)


def closed_from_half(half):
    """the closed counter-clockwise polygon of a right half given top to bottom (its ends on x = 0)"""
    H = np.asarray(half, np.float64)
    full = np.vstack([H, (H[-2:0:-1] * np.array([-1.0, 1.0]))])
    a = np.sum(full[:, 0] * np.roll(full[:, 1], -1) - np.roll(full[:, 0], -1) * full[:, 1])
    return full if a > 0 else full[::-1]


def tube_frame(t):
    """two unit vectors perpendicular to t (the second the more vertical)"""
    t = unit(t)
    v = UP - t * (t @ UP)
    if np.linalg.norm(v) < 1e-6:
        v = np.array([0.0, 0.0, 1.0]) - t * t[2]
    v = unit(v)
    return np.cross(v, t), v


# ============================================================================================ the elytron
ELY_SE = 2.6                    # [E] the cross-section's superellipse exponent, the suture's top to the lateral
#                                  margin (steep sides, a rounded top: P3's front view; gate b03's lateral outline)
ELY_EPI = 0.9                    # [E] the epipleuron's width (the fold under the margin that clasps the venter)
ELY_GAP = 0.03                   # [E] half the gap at the suture: "the gap at the suture is geometry" (plan §4.5)
ELY_APEX_TAIL = ((0.973, 0.258), (0.9944, 0.091))
#                                  [M-ph M1d] B3f: the elytra's plan half-width (fraction of EW / 2) near the apex, read
#                                  on beetle/scratch_b03f/f01_m1d_apex.png (64.527 px/mm): the pair's outline one broad
#                                  arc meeting the suture almost square, half-width 0.85 / 2.40 / 3.95 mm at 0.14 / 0.67 /
#                                  1.40 mm from the apex (the last agrees with the trace's 0.95 station). The trace's 0.98
#                                  station (0.111, SPEC profiles.elytra) measured the dark run through the line's point
#                                  at the suture, where the elytra part over a pale 0.6 mm gap: one elytron's tip only.
#                                  With it the pair narrowed to a point and the patch's last rows, clipped at the sutural
#                                  edge, ended each elytron in a round knob (b03 B3e; f12 _a0)
SCUT = dict(half=1.35, ht=0.35, top=(11.42, 11.30), rho=0.18)        # [E] the scutellum's base half-width, half
#                                  thickness, top (front, apex) and corners; its length M1d's visible 2.39 (body.scut)


def elytra_profiles(spec):
    """the elytron's measured lines (life mm, z in the plan frame): its outer half-width w(z) (SPEC profiles.elytra x
    EW / 2, the humeri 0.902 at the base, 0 at the apex), its top (SPEC outline.dorsal_line behind the base, the base
    top landmarks.ely_base_top), its lateral margin (M1l's margin points: landmarks.ely_marg_top and the res_s01c
    margin row, plan §2.3) and the scutellum's half-width at z. THE BASE stands where the side view puts it
    (landmarks.ely_base_top, z -18.68: M1l's elytra are 24.90 long in the horizontal, M1d's 25.24 on its card, the
    pinned body pitched 12.7 deg between the two views' planes): the plan profile's fractions run from that base to
    the shared apex"""
    b, lm, o = spec['body'], spec['landmarks'], spec['outline']
    z0, EW = lm['ely_base_top'][0], b['EW']
    EL = z0 - lm['ely_apex'][0]
    # (B3f: the apex's last stretch from ELY_APEX_TAIL, not the trace's 0.98 station: the lead, the apex one continuous
    # rounded end at the suture, not two knobs)
    prof = [(0.0, b['EW_hum'] / EW)] + [p for p in spec['profiles']['elytra'] if p[0] <= 0.96] + list(ELY_APEX_TAIL) + \
        [(1.0, 0.0)]
    fw = pchip([p[0] for p in prof], [p[1] for p in prof])
    w = lambda z: 0.5 * EW * np.clip(fw(np.clip((z0 - np.asarray(z)) / EL, 0.0, 1.0)), 0.0, None)
    dl = [(z, h) for z, h in o['dorsal_line'] if z <= -19.0]
    top_pts = [tuple(lm['ely_base_top'])] + dl
    zt_, ht_ = np.array(top_pts).T
    ft = pchip(zt_, smooth_rows(zt_, ht_, LINE_SMOOTH))
    mg = [(z0, o['ely_margin'][0][1] + 0.03)] + list(o['ely_margin'])            # [E] the margin at the base's edge
    fm = pchip([p[0] for p in mg], [p[1] for p in mg])
    zs_ = z0 - b['scut']                                          # the scutellum's apex: M1d's visible length behind
    scut = lambda z: np.where((np.asarray(z) <= z0 + 0.4) & (np.asarray(z) >= zs_),
                              SCUT['half'] * np.clip((np.asarray(z) - zs_) / (z0 - zs_), 0.0, 1.0) ** 0.8, 0.0)
    return dict(w=w, top=ft, marg=fm, scut=scut, z_base=z0, z_apex=-b['BL'], z_scut_apex=zs_)


def elytron_patch(spec, clear, ns=150, nd=44, ne=6):
    """the left elytron's MID-SURFACE patch (V life mm world, F): rows along z (cosine-spaced: dense at the base and
    the apex), each the section from the sutural edge over the dome (a superellipse quadrant, ELY_SE) to the lateral
    margin, then the epipleuron folding inward. The shell around it (half-thickness ht) puts its outer surface on the
    measured outline, top and margin"""
    ht = 0.5 * spec['body']['ely_plate']
    pr = elytra_profiles(spec)
    z0 = pr['z_base'] - ht
    z1 = pr['z_apex'] + ht
    s = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, ns)))
    zs = z0 + (z1 - z0) * s
    xs_edge = np.maximum(ht + ELY_GAP, pr['scut'](zs) + 0.06 + ht)
    wm = np.maximum(pr['w'](zs) - ht, xs_edge + 0.02)
    tm = pr['top'](zs) - ht
    mm = np.minimum(pr['marg'](zs) + ht, tm - 0.04)
    f_ap = np.clip((zs - (pr['z_apex'] + 4.0)) / -4.0, 0.0, 1.0)          # 0 .. 1 over the last 4 mm
    epi = ELY_EPI * (1.0 - 0.8 * f_ap)
    epi = np.minimum(epi, 0.6 * (wm - xs_edge))
    ph = 0.5 * np.pi * np.linspace(0.0, 1.0, nd) ** 0.9
    e2 = 2.0 / ELY_SE
    rows = []
    for i in range(ns):
        x = xs_edge[i] + (wm[i] - xs_edge[i]) * np.sin(ph) ** e2
        y = mm[i] + (tm[i] - mm[i]) * np.cos(ph) ** e2
        xe = wm[i] - epi[i] * np.linspace(0.0, 1.0, ne + 1)[1:]
        ye = mm[i] + 0.15 * np.linspace(0.0, 1.0, ne + 1)[1:] * (epi[i] / ELY_EPI)
        row = np.column_stack([np.concatenate([x, xe]), np.concatenate([y, ye]) + clear, np.full(nd + ne, zs[i])])
        rows.append(row)
    V = np.vstack(rows)
    nt = nd + ne
    F = []
    for i in range(ns - 1):
        for j in range(nt - 1):
            a, b_, c, d = i * nt + j, i * nt + j + 1, (i + 1) * nt + j + 1, (i + 1) * nt + j
            F += [[a, b_, c], [a, c, d]]
    return V, np.array(F, np.int32), dict(ht=ht, zs=zs, wm=wm, tm=tm, mm=mm, epi=epi, xs=xs_edge, profiles=pr)


# ============================================================================================ the pronotum
PRON = dict(rho=0.08, front=-9.04,                                  # [M-ph] the anterior angles' z (M1d pron_ant);
            # the hind margin: M1l's pronotum back top (landmarks.pron_back_top, the waist's z as the side view puts it,
            # where the gated heights stand; M1d's lies 0.42 ahead: build_parts' docstring); the bottom [E]: the
            # prosternum and the hypomera, its back brought down to the venter's front (B3b: the step under the
            # pronotum's back, 1.7 mm in B3, now 0.1)
            bot={-9.04: 5.1, -10.0: 4.6, -11.0: 4.0, -12.5: 3.3, -14.0: 2.9, -15.5: 2.8, -17.0: 2.7, -18.45: 2.55},
            n_stations=40, slope=0.6, keel_slope=0.65,               # the stations; the half-width's and the
            #                                                           height's steepest change (the divisor's share)
            # B3d (the lead: the disc CONVEX above a PROJECTING keel, the hypomeron RECESSED under it, M1l; B3c's two
            # flat planes met at a V crease): pron_section_half's disc arc (p_top / q_top: a dome falling to its foot,
            # no vertical wall), the keel a lip `lip` past the disc's foot, the hypomeron's top `recess` further in under
            # it, the lip's faces `lift` over / under the keel line (a core wedge, grown by rho: its edge rounded by
            # rho), the hypomeron a convex arc (p_bot / q_bot) [E: gate the renders beside M1l, c03 and P3]
            lip=(0.15, 0.55), recess=0.50, lift=0.30, flank=70.0, p_top=2.2, p_bot=1.8,
            q_top=1.5, q_bot=1.8, cove=0.40,
            # B3e (the lead: the keel a CRISP CARINA, a sharp ridge profile of small radius, the hypomeron SET IN under
            # it; B3d's horizontal lip grown by rho 0.3 read as a soft bead): the margin a RIDGE in the core
            # (pron_section_half): the disc's foot lip[0] in from the edge and lip[1] over it, its flank arriving at
            # `flank` deg, the underside leaving straight in and down (recess, lift: the ridge's angle ~100 deg), the
            # cove (concave) under it; rho 0.08, the carina's measured radius (M1l's highlight, one unresolved line
            # 62 um wide: r <= 0.08-0.10, beetle/scratch_b03e/e03). (A separate wedge swept along a rho 0.3 bead read
            # as a blade on the bead, or as a rounded nose, e10 _b5 / _b12)
            corner_k=0.35, hind_arc=0.30, back_half=6.4)    # B3e: the hind angle cuts' blend (B3d's), their faces'
            #                   bow (in from the cut line at the face's ends: pronotum_descs), and the loft's half-width
            #                   at the base [E] (B3d: the last measured less 0.3, 6.92: the section stood 1.1 mm past the
            #                   hind margin cut, its face 4.4 mm tall; 6.4 holds the loft's PRON slope back to M1d's
            #                   0.90 station, 7.15 at z -17.2, and halves the overhang)
            # B3c: the KEEL a sharp edge (M1l): the dorsal arc comes down to the margin
#                                      vertically (a rounded barrel, B3b's 2.2) and the hypomeron below it leaves the
#                                      margin at an angle (its exponent 1), so the margin is an edge with the hypomeron
#                                      under it (a first try, both near 1, made the dorsal side a flat facet), rounded
#                                      by rho 0.3 (B3b 0.4; under SINK, the venter's carve by the pronotum shrunk by SINK
#                                      crossed the keys at the keel); 40 stations (22 banded)


def pronotum_descs(spec, clear):
    """the prothorax shell (B3b): a PSWEEP through station SECTIONS along z (loft_sections), each a 240-point
    section (the 72-point core's 5-deg facets banded the barrel sides, B3's check) whose WIDEST point is the lateral
    margin (the keel) at M1l's own height there (SPEC outline.pron_keel: the margin dips to 7.3 at z -13.1 and rises to
    10.7 / 10.0 at the front and back; B3's [E] keel stood 2 mm higher mid-side), the dorsal surface a superellipse
    arc from the measured top (outline.dorsal_line) out to it at the measured half-width (outline.pron_half, the
    anterior angles at PW_front / 2), the hypomeron sloping in below it to the bottom [E]; the hind angles cut
    obliquely through M1d's 0.90 and 0.97 profile stations (SPEC profiles.pronotum); the front emargination is the
    head's carve (build_parts)"""
    b, o, lm = spec['body'], spec['outline'], spec['landmarks']
    rho = PRON['rho']
    back = lm['pron_back_top'][0] - 0.02
    # the half-width: the measured run to z -17.0; behind it the hind angles are the cuts below
    hw = [(PRON['front'], 0.5 * b['PW_front'])] + [(z, w) for z, w, _ in o['pron_half'] if z >= -17.0]
    hw.append((back, min(hw[-1][1] - 0.3, PRON['back_half'])))     # (B3e: PRON back_half, nearer the cut)
    fw = pchip([p[0] for p in hw], [p[1] for p in hw])
    dl = [(z, h) for z, h in o['dorsal_line'] if -18.0 <= z <= -10.0]
    dl = [(PRON['front'], dl[0][1] + 0.12)] + dl + [(back, lm['pron_back_top'][1] + 0.06)]
    zl_, hl_ = np.array(dl).T
    ftp = pchip(zl_, smooth_rows(zl_, hl_, LINE_SMOOTH))
    fb = pchip(list(PRON['bot'].keys()), list(PRON['bot'].values()))
    kz, kh = np.array(o['pron_keel']).T                              # M1l's margin, extended linearly past its ends
    o_ = np.argsort(kz)
    kz, kh = kz[o_], kh[o_]
    ext = lambda zq: np.interp(zq, kz, kh) + np.where(zq < kz[0], (zq - kz[0]) * (kh[1] - kh[0]) / (kz[1] - kz[0]), 0.0) \
        + np.where(zq > kz[-1], (zq - kz[-1]) * (kh[-1] - kh[-2]) / (kz[-1] - kz[-2]), 0.0)   # noqa: E731
    z = np.linspace(back + rho, PRON['front'] - rho, PRON['n_stations'])
    w = lipschitz_below(z, fw(z), PRON['slope'])
    tp, bt = ftp(z), fb(z)
    hh = lipschitz_below(z, 0.5 * (tp - bt), PRON['slope'])
    mid = 0.5 * (tp + bt)
    tp, bt = mid + hh, mid - hh
    # the margin's height held to PRON keel_slope (the divisor's share; it lowers M1l's ends by up to 0.3 mm)
    keel = np.clip(lipschitz_below(z, ext(z), PRON['keel_slope']), bt + rho + 0.6, tp - rho - 0.6)
    assert (w - rho).min() > 0.3, 'pronotum: a section narrower than its corner radius'
    cores = [closed_from_half(pron_section_half(t - rho + clear, k_ + clear, b_ + rho + clear, w_ - rho, PRON['lip'],
                                                PRON['recess'], PRON['lift'], p_top=PRON['p_top'], q_top=PRON['q_top'],
                                                p_bot=PRON['p_bot'], q_bot=PRON['q_bot'], cove=PRON['cove'],
                                                flank=PRON['flank']))
             for t, k_, b_, w_ in zip(tp, keel, bt, w)]
    c = mid + clear
    out = [loft_sections(z, cores, rho, float(c.mean()), name='pronotum')]
    # the hind angles: a vertical cut through the 0.90 and 0.97 stations of M1d's profile (z on pron_front + frac x the
    # profile's length), smoothed into the shell
    zf, zl = o['pron_profile_z']
    pp = dict(spec['profiles']['pronotum'])
    p90 = np.array([0.5 * pp[0.90] * b['PW'], zf - 0.90 * zl])
    p97 = np.array([0.5 * pp[0.97] * b['PW'], zf - 0.97 * zl])
    dline = unit(p97 - p90)
    n = np.array([dline[1], -dline[0]])
    n = n if n[0] > 0 else -n
    n3 = np.array([n[0], 0.0, n[1]])
    d3 = np.array([dline[0], 0.0, dline[1]])                      # along the cut, from the 0.90 toward the 0.97 point
    seg = float(np.linalg.norm(p97 - p90))
    # B3e (the lead: the hind corner's 2.3 mm flat face rounded; B3d's box cuts' vertical planes left a 2.34 mm face at
    # z -17.8): each cut a PRISM along B3d's cut line (the plan's hind angle as B3d: M1d's 0.90 / 0.97 stations) whose
    # section's inner side is a CONVEX arc on the cut line at the face's middle, PRON hind_arc in from it at the face's
    # ends (where the section at the 0.97 station's z crosses the cut line, above and below): the face a round (radius
    # (V^2 + b^2) / 2 b, V its half-height), its ends blended into the disc and the hypomeron, the plan's hind angle
    # B3d's. (A larger blend on the planes eroded the hind angle 0.5-0.7 mm in plan; horizontal capsules scooped the
    # face concave between two edges; an arc 0.45 in at ends 0.35 past the face's raised it to 5 mm; one bowed out past
    # the cut line widened the plan's hind angle 0.3-0.5 mm, e10 _b5-_b17)
    bow_ = PRON['hind_arc']
    k97 = int(np.argmin(np.abs(z - p97[1])))
    core97 = pron_section_half(tp[k97] - rho, keel[k97], bt[k97] + rho, w[k97] - rho, PRON['lip'], PRON['recess'],
                               PRON['lift'], p_top=PRON['p_top'], q_top=PRON['q_top'], p_bot=PRON['p_bot'],
                               q_bot=PRON['q_bot'], cove=PRON['cove'], flank=PRON['flank'])
    xo_ = core97[:, 0] + rho                                       # (the grown outline, near enough in x)
    cross_ = np.where(np.diff(np.sign(xo_ - p97[0])) != 0)[0]
    if len(cross_) >= 2:
        h_top_, h_bot_ = float(core97[cross_[0], 1]), float(core97[cross_[-1], 1])
    else:
        h_top_, h_bot_ = float(keel[k97]) + 0.6, float(keel[k97]) - 1.6
    h_mid = 0.5 * (h_top_ + h_bot_)
    Va_ = 0.5 * (h_top_ - h_bot_)
    Ra_ = (Va_ ** 2 + bow_ ** 2) / (2.0 * bow_)
    th_ = np.linspace(np.arcsin(Va_ / Ra_), -np.arcsin(Va_ / Ra_), 41)
    arc_ = np.column_stack([Ra_ * np.cos(th_) - Ra_, Ra_ * np.sin(th_)])   # (u out, v up): (0, 0) its middle, (-b, +-V)
    poly_ = np.vstack([arc_, [[0.0, -Va_ - 2.5], [6.0, -Va_ - 2.5], [6.0, Va_ + 2.5], [0.0, Va_ + 2.5]]])

    def hind_prism(Pa, Pb, nrm, name):
        t_ = unit(Pb - Pa)
        sg_v = float(np.cross(t_, nrm) @ UP)                       # the section's second axis is t x n: up or down
        sec_ = np.column_stack([poly_[:, 0], poly_[:, 1] * sg_v])
        if np.sum(sec_[:, 0] * np.roll(sec_[:, 1], -1) - np.roll(sec_[:, 0], -1) * sec_[:, 1]) < 0:
            sec_ = sec_[::-1]
        return psweep(np.array([Pa, Pb]), sec_, 0.0, normal=nrm, op=S_.SUBTRACT, k=PRON['corner_k'], name=name)

    for sgn in (1.0, -1.0):
        M = np.diag([sgn, 1.0, 1.0])
        nn, dd = M @ n3, M @ d3
        P0 = M @ np.array([p90[0], h_mid + clear, p90[1]])
        # the oblique cut from well ahead of the 0.90 station to the 0.97 one (M1d's hind angle), ...
        out.append(hind_prism(P0 - 6.0 * dd, P0 + seg * dd, nn, f'hind angle cut {"L" if sgn > 0 else "R"}'))
        # ... then the corner straight back at the 0.97 station's half-width to the side view's waist
        z_hi, z_lo = p97[1], back - 3.0
        out.append(hind_prism(np.array([sgn * p97[0], h_mid + clear, z_hi]), np.array([sgn * p97[0], h_mid + clear, z_lo]),
                              np.array([sgn, 0.0, 0.0]), f'hind margin cut {"L" if sgn > 0 else "R"}'))
    return out


# ============================================================================================ the venter
VENTER = dict(rho=0.45, front_in=0.65, tip=-42.3,                    # front_in: its front this far inside the
              #   pronotum's hind face (the carve holds the depth at SINK)
              # the venter's lowest line (h): M1l's ventral silhouette z -19.9 .. -26.2 (res_s01c prof_lat, the legs
              # mask it beyond) [M], the rest [E] rising to the abdominal tip under the elytral apex
              bot={-18.05: 2.3, -19.0: 1.45, -20.0: 0.70, -21.0: 0.40, -22.0: 0.25, -24.0: 0.07, -27.0: 0.05,
                   -30.0: 0.40, -34.0: 1.0, -37.5: 1.7, -39.5: 2.4, -41.5: 3.4, -42.3: 3.80},
              #   (B3b: the tip's 3.95 swung the last sections up against the top's floor, bt + 2 rho + 1: the loft's
              #   divisor 1.656, the venter's gradient p1 0.604; at 3.80 it is 1.424)
              top_front=11.0,           # [E] the mesothorax's dorsum under the scutellum (the scutellum sinks into it)
              wing_space=2.2)           # [E] the hindwings' space under the elytral top
VENTER_CORE_HALF = ((0.0, 1.0), (0.30, 0.99), (0.58, 0.93), (0.80, 0.82), (0.93, 0.64), (0.99, 0.42), (1.0, 0.15),
                    (0.99, -0.12), (0.94, -0.38), (0.84, -0.63), (0.66, -0.83), (0.40, -0.96), (0.0, -1.0))   # [E]
VENTER_END = dict(side_z=-39.0, side_out=0.05, k=1.10, past=1.2)   # [E] B3d: the end's arc in plan runs
#                                  (B3e past: the loft runs this far beyond the tip, so the arc's cut alone ends it,
#                                  venter_descs)
#                                  from the apex (z
#                                  VENTER tip, the midline) to the loft's side at side_z (side_out outside it: no cut
#                                  ahead of it), the end cut smoothly by k (its top and bottom edges rounded); B3c's half
#                                  section at the tip 4.30 wide x 1.04 high


VENTER_EPI_EXTRA = 0.20          # [E] the venter a little wider than the epipleuron's inner edge + SINK: its rounded
#                                  section meets the epipleuron below its widest line (b03: 0.13, then 0.18 mm deep;
#                                  B3b: 0.25 read 3.83 at x10 once the loft's divisor fell to 1.42, near the gate's 4)


def venter_descs(spec, clear, ely):
    """the ventral thorax and abdomen: a PSWEEP along z, its section widest where the elytron's epipleuron lies (the
    epipleura clasp it: its half-width the epipleuron's inner edge + SINK, a listed overlap), its bottom M1l's ventral
    line (the venter's lowest point landmarks.venter [M]), its top under the elytra by the wings' space [E]"""
    lm = spec['landmarks']
    pr, ht = ely['profiles'], ely['ht']
    rho = VENTER['rho']
    front = lm['pron_back_top'][0] - 0.02 + VENTER['front_in']    # the face, inside the pronotum's hind face
    bot = dict(VENTER['bot'])
    bot[lm['venter'][0]] = lm['venter'][1]
    fb = pchip(list(bot.keys()), list(bot.values()))
    zt = np.array([front, -19.0, -21.0, -24.0, -26.4, -30.0, -34.0, -37.0, -40.0, -42.0, VENTER['tip']])
    tt = np.where(zt > -21.5, VENTER['top_front'], pr['top'](zt) - VENTER['wing_space'] * np.clip(
        (zt + 43.6) / 4.0, 0.55, 1.0))
    ftp = pchip(zt, tt)
    # B3e (the lead: the venter's end a rounded CAP from the side too; B3d's end showed a 1.31 mm vertical face in
    # profile): B3d's loft ended AT the tip, where the end arc's cylinder (below) is tangent to it, so on the midline the
    # loft's own flat end face (its rho corners) stood as the end; the loft now runs VENTER_END past beyond the tip (its
    # tip section held: no section change, no divisor change) and the end arc alone ends it, its smooth intersection
    # (k) rounding the end's top and bottom edges round the whole arc, the midline too. B3d's nodes and its centreline's
    # trend are kept (the run past the tip is added before them and kept out of the fit: the mid and hind coxa plates
    # read the venter's lower surface, and a 0.03 mm shift there lost both trochanters' seats, e10 _b9). (A capsule
    # unioned on the end face instead: sdf.Program skips a UNION member at points already inside the result, so the end
    # arc's wide blend read the loft's shallow field inside its end face and slit it, _b8; thinning the loft's end
    # raised its divisor 1.42 -> 1.63, _b4-_b6)
    z = np.linspace(VENTER['tip'] + rho, front - rho, 110)        # the loft's end faces stand rho past its end nodes
    hz0 = float(z[1] - z[0])
    z = np.concatenate([z[0] - hz0 * np.arange(int(np.ceil(VENTER_END['past'] / hz0)), 0, -1), z])
    zq = np.maximum(z, z[z >= VENTER['tip'] + rho - 1e-6][0])     # (past B3d's first node: its section, its width
    #                                                                too: the epipleura narrow on past it, and
    #                                                                LOFT_SLOPE carried that narrowing 12 mm up the
    #                                                                venter; its keys and scale held, e11)
    zz = np.clip(zq, ely['zs'].min(), ely['zs'].max())
    epi_in = np.interp(zz, ely['zs'][::-1], (ely['wm'] - ely['epi'])[::-1]) - ht
    w = np.maximum(epi_in + SINK + VENTER_EPI_EXTRA, 0.7)
    zb = pr['z_base']
    w = np.where(z > zb, np.interp(z, [zb, front], [w[z <= zb][-1], 5.6]), w)
    tp, bt = ftp(zq), fb(zq)
    tp = np.maximum(tp, bt + 2.0 * rho + 1.0)                     # the tip keeps a section thicker than its corners
    w = np.maximum(w, rho + 0.3)
    # (past the tip the held section rides the centreline's trend: its keys held too; held level, they ran on to 3.1
    # and the loft's divisor rose 1.42 -> 1.52, e11)
    fit_ = z >= VENTER['tip'] + rho - 1e-6
    b1_ = float(np.polyfit(z[fit_], 0.5 * (tp + bt)[fit_], 1)[0])
    tp, bt = tp + b1_ * (z - zq), bt + b1_ * (z - zq)
    body = loft(z, w, tp, bt, smooth_core(VENTER_CORE_HALF, 160), rho, clear, name='venter', tilt=True,
                tilt_fit=(VENTER['tip'] + rho - 1e-6, front))
    # B3d (the lead: the venter's end ROUNDED from below as well as from the side; B3c: a flat transverse U 8.6 mm wide
    # under the apex, B3b's end cap a nub on its midline): the loft cannot narrow there (the epipleura clasp it to the
    # end, and LOFT_SLOPE would carry a narrower end up the whole abdomen), so the end is CUT to an arc in plan: kept is
    # the inside of a vertical cylinder through the end's apex (z tip, the midline) and the loft's side at VENTER_END's
    # z, or anything ahead of that z, intersected smoothly (k: the end's top and bottom edges rounded in profile)
    lw = lipschitz_below(z, w, LOFT_SLOPE)
    zs_ = VENTER_END['side_z']
    ws_ = float(np.interp(zs_, z, lw)) + VENTER_END['side_out']
    sag = zs_ - VENTER['tip']
    Rc = (sag * sag + ws_ * ws_) / (2.0 * sag)
    zc = VENTER['tip'] + Rc
    y_lo, y_hi = clear - 1.0, clear + 14.0
    # (the members' boxes join the part's meshing box: each held to the venter's own extent, a 30 mm box ahead made the
    # full-resolution meshing grid 45 GB)
    hz_ = 0.5 * (front + 0.5 - zs_)
    tq_ = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
    disc = Rc * np.column_stack([np.cos(tq_), np.sin(tq_)])         # (a prism along y: no caps past y_lo / y_hi)
    keep = group([psweep(np.array([[0.0, y_lo, zc], [0.0, y_hi, zc]]), disc, 0.0, normal=[1.0, 0.0, 0.0],
                         name='venter end arc'),
                  roundbox(np.array([0.0, 0.5 * (y_lo + y_hi), zs_ + hz_]), (float(w.max()) + 1.0, 0.5 * (y_hi - y_lo),
                                                                             hz_), 0.0, name='venter ahead of the end')],
                 op=S_.INTERSECT, k=VENTER_END['k'], name='venter end')
    return [body, keep]


def scutellum_descs(spec, clear, ely):
    """the scutellum (with the visible mesothorax): a rounded plate between the elytral bases, its apex M1d's
    visible length behind the base (body.scut), its underside SINK into the venter's dorsum"""
    pr = ely['profiles']
    zb, za = pr['z_base'], pr['z_scut_apex']
    rho = SCUT['rho']
    z = np.linspace(za + rho, zb - 0.0, 30)
    half = np.maximum(pr['scut'](z), rho + 0.08)
    t_top = np.interp(z, [za, zb], [SCUT['top'][1], SCUT['top'][0]])
    return [loft(z, half, t_top, t_top - 2.0 * SCUT['ht'], superellipse(40, 4.0), rho, clear, name='scutellum')]


# ============================================================================================ the legs
# THE COXAE (B3b). h is above the venter's lowest point (world y = h + the clearance; B3's world y moved with the stand)
COXA_FORE = dict(a=(1.40, 2.62, -15.30), ra=1.05, b=(2.35, 2.55, -13.00), rb=0.85)  # [E] the procoxa an oblique egg
#                                  (B3b: B3's round box read as a soap bar): from its rear-medial bulge, whose lowest
#                                  point is M1l's procoxa (landmarks.procoxa_low, h 1.70 at z -15.82 [M]), forward and
#                                  out to the femur's exit (coxae.pro) inside its front end; P3 shows it globular
COXA_PLATE = dict(                 # [M-ph M3v] the meso- and metacoxae as PLATES (B3b: buried 1.3-1.4 mm in B3), their
    #                                outlines on M3v (beetle/scratch_b03b/g_m3v_coxae.png, 42.85 px/mm, x B1 / M3 EW
    #                                0.922): centre (x, z), half extents (across, along), plan turn (deg, + the outer end
    #                                back), corner radius; the ventral face PROUD of the venter by `proud` [E], the top
    #                                over the femur's exit, the rest inside the venter's socket
    mid=dict(c=(2.60, -20.95), half=(1.40, 1.25), turn=12.0, r=1.10, proud=0.40),   # B3c: ROUNDED, a cup bulging
    #                                from the venter (M3v's mesocoxae: oval domes; B3b's round boxes of corner radius
    #                                0.55 read as flat tiles), its corner radius near its half extents
    hind=dict(c=(2.50, -31.27), half=(2.10, 1.20), turn=6.0, r=1.00, proud=0.30),   # B3c: TRANSVERSE, from 0.4 off
    #                                the midline out to 4.6 (M3v's metacoxa runs to x ~5.6 dorsal of the femur, which
    #                                crosses it ventrally in its groove: arthropod_parts' femur carve into its coxa)
    over_exit=0.55)
TROCH_R = (0.42, 0.64)                       # [E] the trochanter's radii, coxa end / femur end (B3f, the lead: OVOID, set on
#                                            the coxa: an egg narrowing into its coxa, M3v's shiny ovals at the femora's
#                                            bases; B3e's 0.50 / 0.55 read as a capsule)
# B3f: THE KNEE (the lead: the femur's distal end with articular condyles, the tibia's head seated between them; B3e's
# femur sweep ended in a flat cap at the knee and the tibia's pipe plugged into it). M3v / M1d: the femur's apex a rounded
# club end, the tibia narrowing to its base (M1d 0.93 at 10 % of the mid and hind tibiae against 1.21-1.29 at 25 %,
# beetle/scratch_b03f/f09_tibia.py) and leaving the club's end. Built round the knee joint K: the tibia's HEAD a ball of
# r_h at K; the femur's sweep stops inside a rounded KNOB (a round box of the femur's distal section, rounded by most of
# its half-thickness) whose tip stands r_h - SINK short of K, so the head sinks SINK into it; two CONDYLES (round plates
# on the hinge axis, cross(femur, tibia)) flank the head, overlapping it by `over`; the tibia's sweep starts in the head
# at its NECK (TIBIA_PROF u 0)
KNEE = dict(fore=dict(r_h=0.58), mid=dict(r_h=0.50), hind=dict(r_h=0.50), over=0.10, knob_back=0.30, knob_ext=0.30,
            knob_k=0.15, notch_r=0.06, notch_k=0.04, head_k=0.08, neck_in=0.12,
            club=True, club_back=0.55, club_ext=0.55, club_swell=1.15, club_round=0.98, club_neck_in=-0.12, club_k=0.28)
#                                            (B3h, the lead's call 5: the club's swelling flows into the shaft. The shaft's
#                                            measured widest stations (fore 1.66-1.75 at 72-87 %, FEMUR_PROF) narrow to its end
#                                            section (1.36 at 94 %), and a club only club_swell 1.08 wider than that end, met by
#                                            a 0.15 blend, left a waist: a faint ring round the femur behind the knee (the B3g
#                                            check c04 / c11 tiles 17-18). club_swell 1.15 and the club's own blend club_k 0.28
#                                            fill it; M3v's knobs wider than the shaft's end, no wider than its widest)
#                                            (the B3g checker, 10-27: club_ext 0.32 -> 0.55: the tibia's start rim stood
#                                            outside the club's rounded end on the outside of the bend, a NUB at every knee,
#                                            0.176 / 0.142 / 0.051 mm proud at 0.47 / 0.39 / 0.26 mm past the knee along the
#                                            femur, fore / mid / hind (beetle/scratch_b3gcheck/c04); covering it needs the end
#                                            at 0.44-0.55 past the knee less its rounding. Moving the tibia's start along its
#                                            own axis cannot: the rim's reach along the femur is the tibia's half width)
#                                            [E] the knob from knob_back behind the notch's floor to knob_ext past the knee;
#                                            the notch's corner radius and blend; the neck's sweep from neck_in past K
#                                            B3g (the lead, 10-27: the knee a rounded FEMORAL CLUB over the tibia's narrow base,
#                                            M1d / M3v / BEETLE_BODY_PHOTOS 7c, no sphere, no slot, no clevis; B3f's ball in a
#                                            notched knob read as a mechanical clevis, beetle/scratch_b3fcheck/k08 tiles 12-13):
#                                            club True: the femur ends in a CLUB, a round box from club_back behind the knee to
#                                            club_ext past it, club_swell x the shaft's end section across (M3v: the mid and
#                                            hind femora's ends round knobs wider than the shaft's end), rounded by club_round x
#                                            its half-thickness (round across, its end a cap), blended by knob_k; the tibia has
#                                            NO ball: its sweep starts club_neck_in along the tibia from the knee, inside the
#                                            club, at its narrow neck (TIBIA_PROF u 0, M1d's 0.93 at 10 %), and leaves the club;
#                                            the femur carved by the tibia shrunk by SINK (build_parts' chain carve): the joint
#                                            SINK deep [E: back, ext, swell]
# B3e (the lead: each segment's MEASURED swelling and taper, the femur swelling mid-length, the tibia widening and
# flattening distally; B3d's 3- and 2-station linear sections read as uniform pipes): the PROFILES along each segment,
# (u from the proximal end, width, depth) mm, PCHIP between the stations. Widths: M3v's (beetle/scratch_b03e/e09_legs.py,
# 13 cuts across each left segment, the dark run through the axis at 42.85 px / mm x B1 / M3 EW 0.9222: the tibiae clean
# against the white ground; the femora against the dark body, their valid cuts only: fore 1.33 (0.13) / 1.52 (0.45) / 1.66-
# 1.75 (0.72-0.86) / 1.36 (0.94), mid 1.37 (0.28) / 1.67 (0.50) / 2.10 (0.65) / 1.98-1.83 (0.79-0.86), hind 1.29 (0.35) /
# 1.85-2.01 (0.50-0.94): club-shaped, widest at 0.6-0.85, narrowing at the knee; B3d's checker read the fore femur 1.8-1.9
# on g_m3v_femora.png); depths: M1l's (l01_leg_depths.py: the fore femur 1.63 / 1.68 / 1.98 near / mid / distal, the fore
# tibia 1.20 / 1.10 / 1.04, the mid tibia 1.63 / 1.53 / 1.45; the hind tibia 0.98 / 1.21 / 0.94, B3c) and [E] the mid and
# hind femora's (hidden on M1l) at B3d's 1.25-1.40 on the widths' shape. The tibiae's teeth and spurs are their own.
FEMUR_PROF = dict(fore=((0.00, 1.45, 1.55), (0.25, 1.58, 1.62), (0.50, 1.76, 1.70), (0.72, 1.88, 1.82), (0.86, 1.86, 1.84),
                        (1.00, 1.62, 1.66)),
                  mid=((0.00, 1.30, 1.15), (0.25, 1.55, 1.28), (0.50, 1.88, 1.40), (0.68, 2.05, 1.45), (0.85, 1.95, 1.40),
                       (1.00, 1.60, 1.22)),
                  hind=((0.00, 1.35, 1.15), (0.25, 1.62, 1.30), (0.50, 1.90, 1.42), (0.70, 2.02, 1.45), (0.86, 1.98, 1.42),
                        (1.00, 1.78, 1.28)))
TIBIA_PROF = dict(fore=((0.00, 1.00, 1.00), (0.08, 1.18, 1.14), (0.20, 1.30, 1.18), (0.45, 1.31, 1.12), (0.60, 1.42, 1.10),
                        (0.75, 1.60, 1.07), (0.90, 1.74, 1.05), (1.00, 1.78, 1.04)),
                  mid=((0.00, 0.84, 1.00), (0.08, 0.96, 1.36), (0.20, 1.12, 1.62), (0.30, 1.14, 1.58), (0.55, 1.10, 1.53),
                       (0.80, 1.06, 1.48), (0.88, 1.10, 1.47), (0.94, 1.24, 1.46), (1.00, 1.42, 1.45)),
                  hind=((0.00, 0.84, 0.90), (0.08, 0.98, 0.98), (0.20, 1.14, 1.08), (0.28, 1.16, 1.12), (0.50, 1.14, 1.21),
                        (0.78, 1.10, 1.06), (0.88, 1.12, 1.00), (0.94, 1.24, 0.96), (1.00, 1.40, 0.94)))
# (B3f: the NECK at u 0 under the knee's head (M1d: 0.93 at 10 % of the mid and hind tibiae, rising to 1.21-1.29 by 25 %,
# f09); B3e's u-0 rows now stand at u 0.20; the DISTAL WIDENING to the apex M1d's (mid 0.99 / 1.08 / 1.35 at 85 / 90 / 95 %,
# hind 1.08 / 1.16 / 1.39; M3v mid 1.10 / 1.44 at 85 / 90 %), B3e's 1.32 / 1.24 at the apex were the 90 % widths)
TIBIA_BOW = dict(mid=('arc', 0.16), hind=('base', 0.10))
#                                            [M-ph M1d, f09] the mid and hind tibiae's CURVATURE in plan, toward the
#                                            anterior-lateral side (the horizontal normal to the tibia with +z): the mid
#                                            tibia bowed 0.10-0.25 mm (both sides, 1.5-2.5 % of its 8.5-9.8 mm chord;
#                                            M3v 0.19), 'arc' sin(pi u); the hind tibia straight past 25 % (within 0.05) and
#                                            its base bent 0.10-0.16 toward that side, 'base': the shaft held off the knee-
#                                            ankle chord on the other side by up to the amount, the base curving to the head
MH_SPINE = dict(mid=(0.72, 0.24, 0.26), hind=(0.68, 0.22, 0.26))
#                                            [M-ph M1d] the outer SPINE on the mid and hind tibiae's anterior-lateral edge
#                                            (M1d mid: the width's bump to 1.13 at 70-75 %, the spine on f01_m1d_midleg;
#                                            hind ~70 %): (fraction, protrusion, base length) mm, a flat tooth
MH_SPUR = dict(mid=dict(len=1.00), hind=dict(len=1.10), r=(0.085, 0.02), off=0.36, sep=0.14, splay=0.30, rise=0.12,
               bend=0.06, back=0.15, n=12)
#                                            [M-ph M1d, M3v] the two APICAL SPURS at the mid and hind tibiae's posterior-
#                                            medial apex, pointing on past the tarsus's base and diverging from it (M1d's
#                                            1.0-1.4 mm on the mid tibia, 1.0-1.2 on the hind; thin on M3v): base / tip radius,
#                                            their bases `off` from the axis and `sep` apart (vertical), splay and rise
#                                            off the tarsus's direction, bent `bend` x their length toward it, sunk `back`
LEG_RHO = (0.35, 0.24)                       # [E] femur / tibia corners
FORE_TEETH = ((0.31, 0.24, 0.24), (0.385, 0.26, 0.26), (0.45, 0.28, 0.28), (0.52, 0.28, 0.28), (0.64, 0.60, 0.50),
              (0.70, 0.28, 0.28), (0.75, 0.28, 0.28), (0.88, 0.75, 0.60), (0.98, 0.95, 0.70))
#                                            [M-ph M1d] the fore tibia's OUTER teeth (B3b, read on g_m1d_tibL.png at
#                                            64.527 px/mm): (fraction from the knee, protrusion, base length) mm; flat
#                                            triangles leaning TOOTH_LEAN toward the ankle
FORE_SPUR = (1.0, 0.60, 0.26)                # [M-ph M1d] the inner apical spur (fraction, length, base)
TOOTH = dict(thick=(0.34, 0.20), lean=22.0, rho=0.05, sink=0.22, flat=0.60)   # [E] a tooth's thickness big / small,
#                                            lean, rho, the base's depth into the tibia, the thickness kept at its tip
TARSO_W = dict(fore=(0.45, 0.44, 0.46), mid=(0.50, 0.46, 0.46), hind=(0.56, 0.46, 0.46))
#                                            [M-ph M1d] the tarsomeres' plan WIDTHS (B3b, leg_widths.py: t1-t4, t5 at its
#                                            base; B3's 0.80-0.88); round sections: rest.ankle_h is the widest's half
#                                            (0.28). t5's END [E] 0.46, the claws' socket (the onychium): a socket's
#                                            depth is bounded by its parent's radius, and the gate's 0.2 mm needs 0.2+
#                                            (M1d reads 0.36-0.42 at 0.75 of t5)
TARSO_TAPER = 0.62                           # [E] a tarsomere's base radius against its end (each widens distally: B3c,
#                                            LOBED as P3 and M1l show them, each a bead swelling to its end; B3b 0.85)
TARSO_LOBE = dict(r=0.62, drop=0.42, back=0.30, k=0.08)   # [E from M-ph M1l, P3] t1-t4's ventral lobe: a ball of
#                                            r x the end radius, drop x it below the end, back x the segment from it
TARSO_SEAT = -0.05                           # [E] a tarsomere's pole this much short of SINK into the one before: at the
#                                            parent's end-ball centre, where it is widest (the parent's radius, 0.22-0.28,
#                                            bounds the depth b03 reads: 0.198 at SINK, 0.196 at SINK + 0.04 behind it)
CLAW = dict(w=(0.32, 0.05), d=(0.38, 0.06), turn=98.0, splay=11.0, rho=0.03, knob=0.215)
#                                            the claws: CURVED HOOKS (B3b; M1d, P3, c03): width [M-ph M1d 0.26-0.33] and
#                                            depth [E] base / tip; the arc's turn [E] (it leaves t5 rising and lands on
#                                            the ground pointing down), the plan splay each side [E]; the pretarsus's
#                                            radius [E] (claw b's hidden knob in t5's end cap, radius 0.23)


def femur_core():
    """a flattened oval with a slight ventral keel (unit; x vertical, y horizontal) [E: plan §4.4 'flattened ovals
    with keels']"""
    th = np.linspace(0.0, 2.0 * np.pi, 40, endpoint=False)
    x, y = np.cos(th), np.sin(th)
    x = x - 0.12 * np.exp(-((th - np.pi) / 0.35) ** 2)            # the keel: x -1 side pulled down
    return np.column_stack([x, y])


def tibia_core():
    th = np.linspace(0.0, 2.0 * np.pi, 40, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    return np.column_stack([np.sign(c) * np.abs(c) ** 0.85, np.sign(s) * np.abs(s) ** 0.85])


def leg_axis(P0, P1, n=24):
    P0, P1 = np.asarray(P0, np.float64), np.asarray(P1, np.float64)
    u = np.linspace(0.0, 1.0, n)
    return P0[None, :] + u[:, None] * (P1 - P0)[None, :]


def leg_parts(spec, chain, c, pair, parent_fields):
    """one left leg's shells (descriptor lists, world life mm), each seated on its parent along its own axis
    (seat_along on the parent's program); parent_fields: the coxa's parent's field is not needed (the coxa is carved
    into the body). Returns {part: (descs, parent)}"""
    P = chain['pos']
    s = chain['scale_m']
    clear = chain['clearance']
    C, F, K = P[f'trochanter_{c}_L'], P[f'femur_{c}_L'], P[f'tibia_{c}_L']
    J = [P[f'tarsus_{n}_{c}_L'] for n in range(1, 6)] + [P[f'claw_{c}_L']]
    tip = P[f'claw_tip_{c}_L']
    out = {}
    if pair == 'fore':
        cf = COXA_FORE
        ca, cb = np.array(cf['a']) + np.array([0.0, clear, 0.0]), np.array(cf['b']) + np.array([0.0, clear, 0.0])
        out['coxa_f'] = ([roundcone(ca, cb, cf['ra'], cf['rb'], name='coxa f')], 'pronotum')
    else:
        out[f'coxa_{c}'] = ([coxa_plate(COXA_PLATE[pair], C, parent_fields['venter'], name=f'coxa {c}')], 'venter')
    f_par = field_mm(out[f'coxa_{c}'][0], s)
    # trochanter: from inside the coxa toward the femur joint, seated
    ut = unit(F - C)
    s_ = seat_along(f_par, C, ut, start=-2.0, end=3.0)
    a = C + (s_ - SINK + TROCH_R[0]) * ut
    b = F + 0.25 * ut
    if float(np.linalg.norm(b - a)) < 0.5 * (TROCH_R[1] - TROCH_R[0]) + 0.3:
        b = a + (0.5 * (TROCH_R[1] - TROCH_R[0]) + 0.3) * ut      # (an egg: its ends far enough apart for the cone)
    out[f'trochanter_{c}'] = ([roundcone(a, b, TROCH_R[0], TROCH_R[1], name=f'trochanter {c}')], f'coxa_{c}')
    # femur: PSWEEP from the trochanter into the knee's KNOB (B3f: KNEE, above), the CONDYLES flanking the tibia's head
    f_par = field_mm(out[f'trochanter_{c}'][0], s)
    uf = unit(K - F)
    ub = unit(J[0] - K)
    kn = KNEE
    r_h = kn[pair]['r_h']
    s_ = seat_along(f_par, F, uf, start=-1.5, end=2.5)
    rho = LEG_RHO[0]
    start = F + (s_ - SINK + rho) * uf
    fp_ = np.array(FEMUR_PROF[pair], np.float64)                  # B3e: the measured swelling (PCHIP on its stations)
    W_e, T_e = float(fp_[-1, 1]), float(fp_[-1, 2])
    if kn['club']:
        # B3g: the CLUB (KNEE's comment): from club_back behind the knee to club_ext past it, swollen past the shaft's end
        W_e, T_e = W_e * kn['club_swell'], T_e * kn['club_swell']
        rk = kn['club_round'] * 0.5 * min(W_e, T_e)
        # (the club's half-length at least its rounding, so its end is a round cap: a round box rounds no further than its
        # least half extent, and at club_back 0.55 the end stood a flat drum face, g16 _q1)
        k_back = K - max(kn['club_back'], 2.0 * rk - kn['club_ext']) * uf
        k_front = K + kn['club_ext'] * uf
    else:
        rk = 0.9 * 0.5 * min(W_e, T_e)                             # the knob's rounding
        k_floor = K - (r_h - SINK) * uf                            # the notch's floor: the head (r_h at K) sinks SINK in
        k_back = k_floor - (kn['knob_back'] + rk) * uf             # the knob from here (inside the shaft's end) ...
        k_front = K + kn['knob_ext'] * uf                          # ... past the knee: its two lobes flank the head
    k_c = 0.5 * (k_back + k_front)                                 # its centre: the femur's sweep ends there
    Pf = leg_axis(start, k_c, 26)
    tq = np.linspace(0.0, 1.0, len(Pf))
    # (the profile over the femur's own length, start .. K, sampled on the shortened sweep)
    uq = tq * float(np.linalg.norm(k_c - start)) / max(float(np.linalg.norm(K - start)), 1e-9)
    wide, thick = PchipInterpolator(fp_[:, 0], fp_[:, 1])(uq), PchipInterpolator(fp_[:, 0], fp_[:, 2])(uq)
    Nf = perp_normal(np.tile(uf, (len(Pf), 1)))
    fv, fw = Nf[-1], unit(np.cross(uf, Nf[-1]))                    # the femur's section axes: thick (vertical), wide
    # (roundbox: `half` the full half extents, the rounding inside them)
    knob = roundbox(k_c, (0.5 * float(np.linalg.norm(k_front - k_back)), 0.5 * W_e, 0.5 * T_e), rk,
                    axes=np.column_stack([uf, fw, fv]), k=kn['club_k'] if kn['club'] else kn['knob_k'],
                    name=f'femur {c} {"club" if kn["club"] else "knob"}')
    nh = np.cross(uf, ub)
    nh = unit(nh) if np.linalg.norm(nh) > 1e-3 else fw            # the knee's hinge axis
    e3 = unit(np.cross(uf, nh))
    shaft = psweep(Pf, femur_core(), rho, scale=np.column_stack([0.5 * thick - rho, 0.5 * wide - rho]), normal=Nf,
                   name=f'femur {c} shaft')
    if kn['club']:
        # B3g: the club alone ends the femur (no notch: KNEE's comment)
        out[f'femur_{c}'] = ([group([shaft, knob], name=f'femur {c}')], f'trochanter_{c}')
    else:
        # the CONDYLES: the knob's end split by a NOTCH across the joint (the plane of femur and tibia), `over` narrower
        # each side than the head, its floor at k_floor: the two halves of the knob's rounded end are the condyles,
        # continuous with the femur (round cones on its sides read as pills, round plates as stuck-on tiles: f11 _l2, _l3)
        sl_len = float(np.linalg.norm(k_front - k_floor)) + rk + 0.2
        slot = roundbox(k_floor + 0.5 * sl_len * uf, (0.5 * sl_len, r_h - kn['over'], 0.5 * T_e + 0.5 * W_e + 0.3),
                        kn['notch_r'], axes=np.column_stack([uf, nh, e3]), op=S_.SUBTRACT, k=kn['notch_k'],
                        name=f'femur {c} notch')
        out[f'femur_{c}'] = ([group([shaft, knob, slot], name=f'femur {c}')], f'trochanter_{c}')
    # tibia: its HEAD a ball at the knee, its sweep from the neck in the head to the ankle (B3f: the mid and hind tibiae
    # bowed, TIBIA_BOW; their outer spine and apical spurs; the fore tibia's teeth on its outer edge)
    rho = LEG_RHO[1]
    start = K + (kn['club_neck_in'] if kn['club'] else kn['neck_in']) * ub
    Pt = leg_axis(start, J[0], 24)
    tq = np.linspace(0.0, 1.0, len(Pt))
    d_bow = np.cross(UP, ub)
    d_bow = unit(d_bow if d_bow[2] >= 0.0 else -d_bow) if np.linalg.norm(d_bow) > 1e-3 else unit(np.cross(ub, nh))
    if pair in TIBIA_BOW:
        kind_, amt_ = TIBIA_BOW[pair]
        if kind_ == 'arc':
            bow_ = amt_ * np.sin(np.pi * tq)
        else:                                                      # the shaft off the chord, the base curving to the head
            bow_ = -amt_ * np.sin(0.5 * np.pi * np.clip(tq / 0.25, 0.0, 1.0)) * (1.0 - np.clip((tq - 0.25) / 0.75, 0.0, 1.0))
        Pt = Pt + bow_[:, None] * d_bow[None, :]
    tp_ = np.array(TIBIA_PROF[pair], np.float64)                  # B3e: widening and flattening distally (measured)
    wide, thick = PchipInterpolator(tp_[:, 0], tp_[:, 1])(tq), PchipInterpolator(tp_[:, 0], tp_[:, 2])(tq)
    Tt_ = np.gradient(Pt, axis=0)
    Tt_ /= np.linalg.norm(Tt_, axis=1, keepdims=True)
    Nt = perp_normal(Tt_) if pair in TIBIA_BOW else perp_normal(np.tile(ub, (len(Pt), 1)))
    tshaft = psweep(Pt, tibia_core(), rho, scale=np.column_stack([0.5 * thick - rho, 0.5 * wide - rho]), normal=Nt,
                    k=kn['head_k'], name=f'tibia {c} shaft')
    if kn['club']:
        # B3g: no ball: the tibia's narrow neck starts inside the femur's club (KNEE's comment)
        tib = [group([dict(tshaft, k=0.0)], name=f'tibia {c}')]
    else:
        head = roundcone(K - 0.001 * ub, K + 0.001 * ub, r_h, r_h, name=f'tibia {c} head')
        tib = [group([head, tshaft], name=f'tibia {c}')]
    if pair in MH_SPINE:
        # the outer SPINE (a flat tooth on the anterior-lateral edge) and the two APICAL SPURS (curved, tapering sweeps
        # from inside the apex's posterior-medial corner, past the tarsus's base, diverging from it)
        frac, ln, wb = MH_SPINE[pair]
        i_ = int(round(frac * (len(Pt) - 1)))
        tib.append(flat_tooth(Pt[i_], d_bow, Tt_[i_], np.cross(Tt_[i_], d_bow), 0.5 * float(wide[i_]), ln, wb,
                              TOOTH['thick'][1], f'{pair} tibia spine', lean=35.0))
        sp = MH_SPUR
        uj0 = unit(J[1] - J[0])
        e_p = -d_bow - uj0 * float(-d_bow @ uj0)
        e_p = unit(e_p)
        e_v = unit(np.cross(uj0, e_p))
        L_s = sp[pair]['len']
        for i, sg in enumerate((1.0, -1.0)):
            A_ = J[0] - sp['back'] * Tt_[-1] + sp['off'] * e_p + sg * 0.5 * sp['sep'] * e_v
            d_ = unit(uj0 + sp['splay'] * e_p + sg * sp['rise'] * e_v)
            qn = np.linspace(0.0, 1.0, sp['n'])
            Ps = A_[None, :] + (qn * (L_s + sp['back']))[:, None] * d_[None, :] - (
                sp['bend'] * L_s * 4.0 * qn * (1.0 - qn))[:, None] * e_p[None, :]
            rq_ = sp['r'][0] + (sp['r'][1] - sp['r'][0]) * qn
            Ts_ = np.gradient(Ps, axis=0)
            Ts_ /= np.linalg.norm(Ts_, axis=1, keepdims=True)
            rs_ = 0.6 * sp['r'][1]
            tib.append(psweep(Ps, superellipse(24, 2.0), rs_, scale=np.column_stack([np.maximum(rq_ - rs_, 0.004)] * 2),
                              normal=perp_normal(Ts_, e_v), k=0.04, name=f'{pair} tibia spur {"ab"[i]}'))
    if pair == 'fore':
        side = np.cross(ub, Nt[0])                                 # the tibia's horizontal across direction
        side = side if side[0] > 0 else -side                      # its outer (lateral) edge
        L_t = float(np.linalg.norm(J[0] - start))
        for frac, ln, wb in FORE_TEETH:                            # flat triangles on the outer edge (B3b, M1d)
            q = min(frac, 1.0 - 0.5 * wb / L_t)
            hw_ = 0.5 * float(np.interp(q, tq, wide))
            tib.append(flat_tooth(start + q * (J[0] - start), side, ub, Nt[0], hw_, ln, wb,
                                  TOOTH['thick'][0 if ln >= 0.5 else 1], f'fore tibia tooth {frac:.3f}'))
        frac, ln, wb = FORE_SPUR                                   # the inner apical spur, pointing on along the leg
        q = 1.0 - 0.5 * wb / L_t
        hw_ = 0.5 * float(np.interp(q, tq, wide))
        tib.append(flat_tooth(start + q * (J[0] - start), -side, ub, Nt[0], hw_, ln, wb, TOOTH['thick'][1],
                              'fore tibia spur', lean=70.0))
    out[f'tibia_{c}'] = (tib, f'femur_{c}')
    # the tarsomeres: round cones joint to joint, each seated on the one before (t1 on the tibia), at M1d's widths
    prev, prev_name = out[f'tibia_{c}'][0], f'tibia_{c}'
    tw = TARSO_W[pair]
    for n in range(5):
        r1 = 0.5 * (tw[0] if n < 4 else tw[2])
        r0 = TARSO_TAPER * 0.5 * tw[0] if n < 4 else 0.5 * tw[1]
        f_par = field_mm(prev, s)
        uj = unit(J[n + 1] - J[n])
        s_ = seat_along(f_par, J[n], uj, start=-1.2, end=1.2)
        a = J[n] + (s_ - SINK - (TARSO_SEAT if n else 0.0) + r0) * uj   # (t1 into the tibia at SINK)
        d = [roundcone(a, J[n + 1], r0, r1, name=f'tarsus {n + 1} {c}')]
        if n < 4:
            # the ventral lobe under the segment's end (P3, M1l: each tarsomere's end swollen below, its pad)
            lb = TARSO_LOBE
            dn = UP - uj * (uj @ UP)
            dn = -dn / max(np.linalg.norm(dn), 1e-9)
            seg_l = float(np.linalg.norm(J[n + 1] - a))
            lc = J[n + 1] - lb['back'] * seg_l * uj + lb['drop'] * r1 * dn
            d = [group([d[0], roundcone(lc - 0.02 * uj, lc + 0.02 * uj, lb['r'] * r1, lb['r'] * r1, k=lb['k'],
                                        name=f'tarsus {n + 1} lobe {c}')], name=f'tarsus {n + 1} {c}')]
        out[f'tarsus_{n + 1}_{c}'] = (d, prev_name)
        prev, prev_name = d, f'tarsus_{n + 1}_{c}'
    # two claws: CURVED HOOKS (B3b), circular arcs in the vertical plane of each splayed direction from the tarsus tip
    # to the claw tip on the ground beyond it (the chord the SPEC claw), bulging up: each leaves t5 rising and lands
    # pointing down (M1d, P3, c03)
    T = J[5]
    u5 = unit(J[5] - J[4])
    u_c = unit(np.array([tip[0] - T[0], 0.0, tip[2] - T[2]]))
    reach = float(np.linalg.norm((tip - T)[[0, 2]]))
    for side_, nm in ((1.0, 'a'), (-1.0, 'b')):
        a_ = np.radians(side_ * CLAW['splay'])
        uc = np.array([u_c[0] * np.cos(a_) + u_c[2] * np.sin(a_), 0.0, -u_c[0] * np.sin(a_) + u_c[2] * np.cos(a_)])
        E = np.array([T[0] + reach * uc[0], CLAW['d'][1] * 0.5 + CLAW['rho'], T[2] + reach * uc[2]])
        # the base face (rho behind the sweep's first point) at the centre of t5's end cap (its radius 0.5 TARSO_W[2]
        # deep in every direction: the seat), and so at the pretarsus's centre
        t0 = unit(claw_arc(T, E, CLAW['turn'], 24)[1] - T)
        Pc = claw_arc(T + CLAW['rho'] * t0, E, CLAW['turn'], 24)
        q = np.linspace(0.0, 1.0, len(Pc))
        wv = np.interp(q, [0.0, 1.0], CLAW['w'])
        dv = np.interp(q ** 0.8, [0.0, 1.0], CLAW['d'])
        Tc = np.gradient(Pc, axis=0)
        Tc /= np.linalg.norm(Tc, axis=1, keepdims=True)
        Nc = perp_normal(Tc, np.cross(uc, UP))                     # x across (horizontal), y in the arc's plane
        cd = [psweep(Pc, superellipse(24, 2.0), CLAW['rho'],
                     scale=np.column_stack([np.maximum(0.5 * wv - CLAW['rho'], 0.01),
                                            np.maximum(0.5 * dv - CLAW['rho'], 0.01)]),
                     normal=Nc, name=f'claw {nm} {c}')]
        if nm == 'b':
            # the claws' common base (the pretarsus) inside t5's end cap, carried by claw b: claw a's base face sits at
            # its centre (the listed overlap, 2-4 mm deep at x10, needs a body over 0.2 mm thick: the hooks, at M1d's
            # 0.26-0.33, are not), hidden (its radius under the cap's). One group with the hook: as a member of its own,
            # sdf.Program's cull skipped it inside the hook (an interior step in the field, |grad| 2.5 in b03's samples)
            cd = [group(cd + [roundcone(T - 0.10 * u5, T, CLAW['knob'], CLAW['knob'], name=f'pretarsus {c}')],
                        name=f'claw b and pretarsus {c}')]
        out[f'claw_{nm}_{c}'] = (cd, f'tarsus_5_{c}')
    return out


def claw_arc(A, E, turn, n):
    """a circular arc from A to E turning `turn` degrees, in the vertical plane through them, bulging up"""
    A, E = np.asarray(A, np.float64), np.asarray(E, np.float64)
    c = float(np.linalg.norm(E - A))
    ch = (E - A) / c
    up = UP - ch * (ch @ UP)
    up /= np.linalg.norm(up)
    th = np.radians(turn)
    R = c / (2.0 * np.sin(0.5 * th))
    O = 0.5 * (A + E) - R * np.cos(0.5 * th) * up
    ph = np.linspace(-0.5 * th, 0.5 * th, n)
    return O[None, :] + R * (np.cos(ph)[:, None] * up[None, :] + np.sin(ph)[:, None] * ch[None, :])


def flat_tooth(edge_pt, out_dir, axis, normal, hw, length, base, thick, name, lean=None):
    """a FLAT TRIANGULAR tooth (B3b; M1d's fore tibia): a PSWEEP from inside the tibia's edge out along out_dir leaned
    toward the ankle (axis) by TOOTH lean, its section a lens `base` long along the tibia and `thick` across it
    (normal), tapering to a point: the tibia's half-width hw at the tooth puts its base on the edge"""
    lean = TOOTH['lean'] if lean is None else lean
    o = unit(out_dir - axis * (out_dir @ axis))
    d = unit(np.cos(np.radians(lean)) * o + np.sin(np.radians(lean)) * axis)
    p0 = edge_pt + (hw - TOOTH['sink']) * o
    p1 = edge_pt + hw * o + length * d
    n = 8
    q = np.linspace(0.0, 1.0, n)
    Pt_ = p0[None, :] + q[:, None] * (p1 - p0)[None, :]
    rho = TOOTH['rho']
    sb = np.interp(q, [0.0, 1.0], [0.5 * base - rho, 0.012])          # along the tibia (the section's y): to a point
    # B3e (the lead: the fore tibia's teeth FLAT TRIANGLES along its outer edge, M1d, not cones; B3d tapered the
    # thickness to a point with the base, a cone): the thickness held to TOOTH flat x itself at the tip, a plate
    st = np.interp(q, [0.0, 1.0], [0.5 * thick - rho, max(TOOTH['flat'] * 0.5 * thick - rho, 0.012)])
    Nn = np.tile(unit(normal - d * (normal @ d)), (n, 1))
    return psweep(Pt_, superellipse(24, 2.0), rho, scale=np.column_stack([st, sb]), normal=Nn, k=0.10, name=name)


def coxa_plate(cp, C, f_venter, name=''):
    """a mid or hind coxa as a PLATE (B3b, M3v): a round box over the plan outline cp, its ventral face parallel to the
    venter's surface there (a plane fitted to the surface under the footprint) and cp['proud'] below it, its top
    cp['over_exit'] over the femur's exit C (the trochanter seats on it); the venter carves its socket"""
    cx, cz = cp['c']
    hx, hz = cp['half']
    th = np.radians(cp['turn'])
    ex2, ez2 = np.array([np.cos(th), -np.sin(th)]), np.array([np.sin(th), np.cos(th)])
    us, vs = np.meshgrid(np.linspace(-hx, hx, 7), np.linspace(-hz, hz, 5))
    XZ = np.array([cx, cz])[None, :] + us.reshape(-1, 1) * ex2[None, :] + vs.reshape(-1, 1) * ez2[None, :]
    ys = []
    for x_, z_ in XZ:                                              # the venter's lower surface: the first inside point
        # (searched about the femur's exit: B3c's venter stands 8.67 mm up, above B3b's fixed -1 .. 8 mm search, which
        # then found no surface and stood each plate on the ground as a pillar)
        yy = np.linspace(float(C[1]) - 4.0, float(C[1]) + 6.0, 401)
        v = f_venter(np.column_stack([np.full_like(yy, x_), yy, np.full_like(yy, z_)]))
        i = int(np.argmax(v < 0.0))
        lo_, hi_ = yy[i - 1], yy[i]
        for _ in range(30):
            m = 0.5 * (lo_ + hi_)
            if f_venter(np.array([[x_, m, z_]]))[0] < 0.0:
                hi_ = m
            else:
                lo_ = m
        ys.append(0.5 * (lo_ + hi_))
    ys = np.array(ys)
    A_ = np.column_stack([np.ones(len(XZ)), XZ])
    co, *_ = np.linalg.lstsq(A_, ys, rcond=None)
    plane = A_ @ co
    nrm = unit(np.array([-co[1], 1.0, -co[2]]))
    off = float((ys - plane).min()) - cp['proud']                  # the face under the surface everywhere, then proud
    face = np.array([cx, co[0] + co[1] * cx + co[2] * cz + off, cz])
    hh = 0.5 * (float((np.asarray(C) - face) @ nrm) + COXA_PLATE['over_exit'])
    hh = max(hh, cp['r'] + 0.05)                                   # (B3c: taller into the venter's socket, so the
    ex = np.array([ex2[0], 0.0, ex2[1]])                           # corner radius rounds the face and the outline)
    ex = unit(ex - nrm * (ex @ nrm))
    ez = np.cross(ex, nrm)
    return roundbox(face + hh * nrm, (hx, hh, hz), min(cp['r'], hh), axes=np.column_stack([ex, nrm, ez]), name=name)


# ============================================================================================ the assembly
class Part:
    """one shell: its Program (at the author scale, metres), region and rig joint; a right part mirrors its left"""

    def __init__(self, name, region, joint, prog, descs, parent=None, mirror=False, side=''):
        self.name, self.region, self.joint, self.prog, self.descs = name, region, joint, prog, descs
        self.parent, self.mirror, self.side = parent, mirror, side

    def eval(self, pts):
        """the field at world points (metres): the mirror reads its left part at M p"""
        P = np.asarray(pts, np.float64).reshape(-1, 3)
        return self.prog.eval(P @ M_MIRROR if self.mirror else P)

    def normals(self, pts, h=2.0e-5):
        P = np.asarray(pts, np.float64).reshape(-1, 3)
        if not self.mirror:
            return self.prog.normals(P, h)
        return self.prog.normals(P @ M_MIRROR, h) @ M_MIRROR


def side_name(n, s):
    """a left part's name on side s ('L' / 'R'); midline parts unchanged"""
    return f'{n}_{s}'


def build_parts(spec, chain, pose='bind'):
    """every shell (module docstring) as {name: Part}, and an info dict (the head's and the elytron's construction
    data, the joints list). Left parts end in _L, right in _R, midline parts bare"""
    s = chain['scale_m']
    clear = chain['clearance']
    lmw = chain['head']['lm']
    raw = {}                                            # name -> (descs, parent, region, joint)
    # ---- head
    cap = HEAD.capsule_descs(spec, clear)
    raw['head'] = (cap, 'pronotum', 'head', 'head')
    eye, eye_info = HEAD.eye_descs(spec, clear)
    raw['eye'] = (eye, 'head', 'eye', 'head')
    mand, mand_info = HEAD.mandible_descs(spec, clear, pose)
    raw['mandible'] = (mand, 'head', 'mandible', 'mandible')
    ant, ant_axes = HEAD.antenna_descs(spec, lmw)
    palps = HEAD.palp_descs(lmw)
    # (B3h: the seats and the pronotum's socket read the head's COARSE grid, every second sample: neither shows the head's
    # edges, and the B3h head's 0.025 mm grid held three more times over put b03 past its memory cap)
    cap_c = HEAD.capsule_descs(spec, clear, coarse=True) if HEAD.HEAD_BUILD == 'subd' else cap
    f_head = field_mm(cap_c, s)
    # seat the scape and the palps on the capsule along their axes (their radii are below SINK: no carve)
    for nm, descs in list(ant.items()) + list(palps.items()):
        if nm.startswith('lamella') or nm == 'funicle':
            continue
        d0 = descs[0]
        u = unit(d0['b'] - d0['a'])
        s_ = seat_along(f_head, d0['a'], u, start=-3.0, end=4.0)
        if s_ is not None:
            shift = (s_ - HEAD_SINK + d0['ra']) * u
            descs[0] = dict(d0, a=d0['a'] + shift)
    raw['scape'] = (ant['scape'], 'head', 'antenna', 'antenna_0')
    f_sc = field_mm(ant['scape'], s)
    e1, d1 = ant_axes['funicle']
    s_ = seat_along(f_sc, e1, d1, start=-1.0, end=1.5)
    b0 = ant['funicle'][0]
    sh = (s_ - SINK + b0['ra']) - float((b0['a'] - e1) @ d1)
    ant['funicle'][0] = dict(b0, a=b0['a'] + sh * d1)
    raw['funicle'] = (ant['funicle'], 'scape', 'antenna', 'antenna_2')
    prev, prev_nm = ant['funicle'], 'funicle'
    e3, d2 = ant_axes['club']
    for k in range(4):
        dd = ant[f'lamella_{k}']
        f_par = field_mm(prev, s)
        st = dd[0]
        # the stalk's back pole SINK inside its parent, where the club axis leaves the parent
        s_ = seat_along(f_par, st['a'], d2, start=-1.0, end=1.5)
        if s_ is not None:
            a_new = st['a'] + (s_ - SINK + st['ra']) * d2
            if float((st['b'] - a_new) @ d2) < 0.05:
                a_new = st['b'] - 0.05 * d2
            dd[0] = dict(st, a=a_new)
        raw[f'lamella_{k}'] = (dd, prev_nm, 'antenna', 'lamella_' + str(k))
        prev, prev_nm = dd, f'lamella_{k}'
    raw['palp_max'] = (palps['palp_max'], 'head', 'mouthparts', 'palp_max_0')
    raw['palp_lab'] = (palps['palp_lab'], 'head', 'mouthparts', 'palp_lab_0')
    # ---- body
    ely_V, ely_F, ely = elytron_patch(spec, clear)
    raw['elytron'] = ([shell(ely_V, ely_F, ely['ht'], name='elytron')], 'venter', 'elytron', 'elytron')
    raw['pronotum*'] = (pronotum_descs(spec, clear), 'venter', 'pronotum', 'pronotum')
    raw['venter*'] = (venter_descs(spec, clear, ely), None, 'venter', 'body')
    raw['scutellum*'] = (scutellum_descs(spec, clear, ely), 'venter', 'scutellum', 'body')
    # ---- legs (the mid and hind coxae are plates on the venter's surface: they read its field)
    f_ven = field_mm(raw['venter*'][0], s)
    for c, pair, cox, i in AR.LEGS:
        for nm, (descs, par) in leg_parts(spec, chain, c, pair, dict(venter=f_ven)).items():
            region = nm.split('_')[0]
            jn = {'coxa': f'coxa_{c}', 'trochanter': f'trochanter_{c}', 'femur': f'femur_{c}', 'tibia': f'tibia_{c}',
                  'tarsus': nm[:-2], 'claw': f'claw_{c}'}[region]
            raw[nm] = (descs, par, region if region != 'claw' else 'claw', jn)
    # ---- the carves: sockets (shrunk by SINK) and clearances (grown by CLEAR) into the midline parents
    mid_names = ('head', 'pronotum*', 'venter*', 'scutellum*')
    both = lambda nm: [raw[nm][0], [mirror_desc(d) for d in raw[nm][0]]]
    carve = {k: [] for k in raw}
    for ds in both('eye'):
        carve['head'] += [(d, -SINK, S_.SUBTRACT) for d in ds if carvable(d, -SINK)]
    # the mandibles' sockets: the convex arm within its prisms (B3c: a tooth's or the tine's tip cannot shrink by SINK)
    for ds in (mand_info['socket'], [mirror_desc(d) for d in mand_info['socket']]):
        carve['head'] += [(d, -SINK, S_.SUBTRACT) for d in ds if carvable(d, -SINK)]
    # the head's socket in the pronotum's collar, rounded: hard, it left a rim thinner than the grid where the collar's
    # outside and the socket meet at a shallow angle (ragged in the close-ups)
    carve['pronotum*'] += [(d, -HEAD_SINK, S_.SUBTRACT, COLLAR_K) for d in cap_c if carvable(d, -HEAD_SINK)]
    for c, pair, cox, i in AR.LEGS:
        tgt = 'pronotum*' if c == 'f' else 'venter*'
        for ds in both(f'coxa_{c}'):
            carve[tgt] += [(d, -SINK, S_.SUBTRACT) for d in ds if carvable(d, -SINK)]
        # B3c: the femora now run UNDER the venter from their lowered coxae (§2.7). The trochanters carve their
        # clearance into the body; a mid or hind femur that touches the sternites (the hind femur rises 6.6 deg across
        # them, 0.47 mm into the venter uncarved) is carved BY the venter instead, so the venter keeps no pit with the
        # legs off (the lead: no holes in the venter, legs on or off); the fore femur carves the pronotum as in B3b
        # B3d (the lead: no trochanter pits, legs on or off): every trochanter and femur is carved BY its body part
        # grown by CLEAR (B3c did it for the mid and hind femora): the body keeps no clearance pit with the legs off
        # (B3c's trochanter cuts left round pits 1.1 mm across outside the metacoxae and holes in the mesocoxal cups).
        # The trochanter's cutter is the body LESS its coxa's socket (the coxa shrunk by SINK, as the body's own carve
        # takes it): the trochanter keeps its seat in the coxa and loses only what lies in the body beside it (carved by
        # the whole body, its seat went too: coxa~trochanter apart, b03 _b3dq2)
        cox_ = [shrink_desc(d, SINK - CLEAR) for d in raw[f'coxa_{c}'][0]]
        body_ = group([dict(d) for d in raw[tgt][0]] + [dict(d, op=S_.SUBTRACT, k=0.0) for d in cox_],
                      name=f'{tgt.rstrip("*")} less the coxa {c} socket')
        carve[f'trochanter_{c}'] += [(body_, CLEAR, S_.SUBTRACT)]
        carve[f'femur_{c}'] += [(d, CLEAR, S_.SUBTRACT) for d in raw[tgt][0] if carvable(d, CLEAR)]
        # the femur rests against its own coxa (B3b's plates reach past the femur's exit): its groove
        carve[f'coxa_{c}'] += [(d, CLEAR, S_.SUBTRACT) for d in raw[f'femur_{c}'][0] if carvable(d, CLEAR)]
    # the chains and the body's own joints: each parent carved by its child shrunk by SINK where the child can be (the
    # seat put the child's pole SINK inside along its axis; the carve keeps every other point of it no deeper)
    legs_ = ('coxa', 'trochanter', 'femur', 'tibia', 'tarsus')
    for nm, (descs, par, region, joint) in raw.items():
        if par is not None and par.split('_')[0] in legs_:
            carve[par] += [(d, -SINK, S_.SUBTRACT) for d in descs if carvable(d, -SINK)]
    for ch in ('pronotum*', 'scutellum*'):
        carve['venter*'] += [(d, -SINK, S_.SUBTRACT) for d in raw[ch][0] if carvable(d, -SINK)]
    parts = {}
    for nm, (descs, par, region, joint) in raw.items():
        mid = nm in mid_names
        base = nm.rstrip('*')
        prog = program_of(descs, s, carve.get(nm, []))
        if mid:
            parts[base] = Part(base, region, joint, prog, descs, parent=(par.rstrip('*') if par else None))
        else:
            pn = None if par is None else (par.rstrip('*') if par.rstrip('*') in ('head', 'pronotum', 'venter',
                                                                                  'scutellum') else par + '_L')
            parts[base + '_L'] = Part(base + '_L', region, joint + '_L', prog, descs, parent=pn, side='L')
            pr_ = None if pn is None else (pn if not pn.endswith('_L') else pn[:-2] + '_R')
            parts[base + '_R'] = Part(base + '_R', region, joint + '_R', prog, descs, parent=pr_, mirror=True,
                                      side='R')
    info = dict(eye=eye_info, mandible=mand_info, elytron=ely, raw=raw, pose=pose)
    return parts, info


def condyles(parts):
    """the listed overlaps: each part with its parent (the joint it is sunk into), as (child, parent) names, and each
    leg's two claws with each other (both sunk into the fifth tarsomere: the pretarsus joins their bases)"""
    out = [(n, p.parent) for n, p in parts.items() if p.parent is not None]
    out += [(n, n.replace('claw_a', 'claw_b')) for n in parts if n.startswith('claw_a')]
    return out
