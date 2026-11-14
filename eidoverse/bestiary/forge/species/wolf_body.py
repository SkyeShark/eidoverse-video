"""W2d: THE WOLF'S BODY VOLUME on the head's method (the lead's W2c review: "primitives read as primitives"; two rounds of
primitive bodies read as duck-foot bun paws, a knee for a forearm, a ball for a hock and for the manubrium, ring bands
at the withers and the croup). The composed body program (families/limbed.compose_body: the trunk and neck sweep, the
limbs, the paws rebuilt from the bones) is only the START: it is sampled into grid volumes, carved by the photographs'
SIDE-view skin silhouettes (OUTER limits), rounded by hullflow's constrained curvature flow between those and the
INNER limits (the skeleton's bony points at their least skin depth, the measured muscle masses), then given STROKES
for only what reads through the skin on the wet and mange canids r01-r08, each measured there; it enters the creature's
program as GRID members (the staged sdf_grid patch, kind 9).

UNITS AND FRAME: millimetres inside this module, metres in the program. World axes (x the creature's left, y up, z
forward); every grid is world-axis-aligned, its index (i, j, k) along (x, y, z).

THE LEVELS, one LATTICE: every origin on a multiple of 2 mm, the cells 2, 1 and 0.5 mm, so a finer lattice contains its
parent's points and reproduces the parent's trilinear interpolant EXACTLY (within a cell the interpolant is
multilinear, and multilinear functions are what trilinear interpolation reproduces):
  body   2 mm (the lead: trunk <= 2 mm), the x >= 0 half (the flow mirrors at x = 0), mirrored to full width: the trunk,
         the neck to inside the head, the shoulders and arms down to below the elbows, the thighs to below the stifles
  limbs  1 mm (limbs <= 1 mm), left, mirrored to the right: fore (the forearm from just below the elbow's point, the
         carpus, the pastern), hind (the gaskin from below the stifle, the hock, the cannon)
  paws   0.5 mm (paws finer), left, mirrored: the paw and the lowest pastern
THE SEAMLESS HAND-OVER between a parent and a child (all hard unions, k 0): along the child's region (a box whose only
face that meets the skin is its TOP plane, y = top), four zones by depth below the plane: Z0 above it (parent only),
Z1 an overlap 10 mm deep where the child's values ARE the parent's interpolant, Z2 a 15 mm feather where they blend to
the child's own (smoothstep), Z3 the child alone. The child is cut off above Z1 and the parent below Z1 (inside the
region's footprint), each by a smooth max (radius CUT_K) whose dimple falls where the other member is identical, so
the union's zero set is the parent's above the overlap and the child's below it, with no seam and no bulge; every
member stays a closed solid with a positive border (the GRID member's condition).

THE FLOW per level (hullflow.flow_wp, Warp): stage A at 2 mm on the whole body (the composed program sampled near the
surface, carved by the side limits); the limbs at 1 mm START from the body's flowed field (its interpolant) and refine
briefly under the same limits; the paws at 0.5 mm start from the composed paw sampled at 0.5 mm (their lobes would not
survive a 2 mm flow) and flow briefly at their own scale. W2e: the STROKES are not baked into the grids (W2d's
displacement of the level set before the finish printed the scapular spine's oblique ridge as a ladder on the 2 mm
trunk grid, in the field): they are STROKE members of the program after the GRID members (species/wolf_strokes.py,
families/limbed.build_volume_sdf), evaluated analytically wherever the program is.

THE REVIEW POSE (the lead's W2d call 5): the body volume is built once, at the bind; the review pose bends its neck
(limbed.pose_neck's joint rotations, a smooth linear-blend warp along the neck) by resampling the body grid under the
inverse warp, which leaves every value outside the neck untouched (the limbs' overlaps stay exact).

Cached on disk by every input (hullflow.cached): the composed program's parameters, the chain, this module's tables.
"""
import time

import numpy as np

from .. import hullflow as HF

VERSION = 'w2l-2'               # W2l: the olecranon's and the carpus's bony points smaller and forward (BONES); the
                                # cache key now carries the sweeps' node positions and harmonics (a3 / a4) too
CUT_K = 3.0                     # mm, the smooth max that cuts a member at a region plane
Z1, Z2 = 10.0, 20.0             # mm, the overlap's and the feather's depth below a region's top plane
LEVEL = dict(
    # cell (mm), flow steps, dt (mm^2 per step; CFL h^2/6), redistance every, the pressure's smoothing (size_r, mm),
    # the CLOSING radius of the outer limit (mm: creases the composed masses leave are let fill), the clamp and blur of
    # the finished values (mm). THE CLAMP: a child's overlap holds its parent's values and its feather blends them into
    # its own, so their far fields must agree; but each sees only its own surfaces (the limb's grid not the trunk's), so
    # far from the skin they differ and the blend puts their difference's slope into the child (W2d b2: divisors 1.40-1.44
    # set by far-field cells in the feathers). The limbs and the paws are clamped at +-10 mm (they meet only hard unions;
    # the gradient gate's band is 5 mm), the trunk at +-10 under the chest, ramping to +-34 above it (the head's k 22 and
    # the tail's 16 meet the trunk there). The limbs flow about as long as the body (T 36 vs 48 mm^2), the paws briefly
    # at their own scale (their lobes)
    # the body's blur one cell (W2d b7: 0.7 mm, a third of a cell, left the finish's 2 mm remesh terraced where the
    # skin grazes a grid plane: a ladder of dashes down the scapular spine, dimples on the croup's bumps)
    body=dict(h=2.0, steps=120, dt=0.40, reinit=20, size_r=16.0, close=6.0, clamp=(-34.0, 34.0), blur=2.0),
    limb=dict(h=1.0, steps=300, dt=0.12, reinit=30, size_r=12.0, close=3.0, clamp=(-10.0, 10.0), blur=0.7),
    paw=dict(h=0.5, steps=60, dt=0.035, reinit=20, size_r=6.0, close=1.0, clamp=(-10.0, 10.0), blur=0.5),
)
TRUNK_CLAMP = (10.0, 34.0, 360.0, 450.0)   # the trunk's clamp: +-10 mm under y 360 mm, +-34 over 450 (smoothstep)
# the outer limit over the composed program everywhere (the side views say nothing about the width: without it the
# pressure would inflate the body sideways) and the inset of the inner limits (the masses and the bones)
TOL_PROG = 4.0
TOL_PROG_PAW = 1.5
INSET_MASS = 4.0                # W2d b3: 3 mm left the croup mass above the photos' back lines (a pinned crease)


# ============================================================================================ lattice and regions
def snap(v, step=2.0, up=False):
    """v (mm) to the lattice multiple of step below (or above) it"""
    v = np.asarray(v, float)
    return (np.ceil(v / step) if up else np.floor(v / step)) * step


class WGrid(HF.Grid):
    """a world-axis grid in mm: index (i, j, k) at (x0 + i h, y0 + j h, z0 + k h); (d, q, x) of hullflow.Grid are
    (x, y, z) here"""

    def points_m(self, sl=None):
        X, Y, Z = self.mesh()
        P = np.stack([X, Y, Z], -1)
        return P * 1.0e-3


def region_layout(chain):
    """the child regions (mm, the left side): their parent, cell, box and top plane. ONE top plane for both limbs (so
    the body's cut is a single plane: a box's corners put cells of slope sqrt 3 into the divisor, W2d b1): the lower of
    10 mm under the elbow joint (the elbow's point, the olecranon, stays in the 2 mm body, as the chest floor above it)
    and 40 mm under the stifle joint (the patella and the stifle in the body); the paws' at 85 mm (the dewclaw at 55 mm,
    inside the paw)"""
    P = {k: np.asarray(v, float) * 1000.0 for k, v in chain['pos'].items()}
    yl = float(snap(min(P['elbow_L'][1] - 10.0, P['stifle_L'][1] - 40.0), 1.0))
    yf = yh = yl
    return dict(
        fore=dict(parent='body', level='limb', top=yf, side=1),
        hind=dict(parent='body', level='limb', top=yh, side=1),
        fpaw=dict(parent='fore', level='paw', top=85.0, side=1),
        hpaw=dict(parent='hind', level='paw', top=85.0, side=1),
    )


def solid_extent(prog, lo, hi, h=4.0):
    """the composed program's solid within the box [lo, hi] mm: the extent of the cells whose field is under h"""
    G = WGrid(lo, hi, h)
    f = prog.eval(G.points_m().reshape(-1, 3)).reshape(G.n) * 1000.0
    m = f < h
    if not m.any():
        return None
    idx = np.argwhere(m)
    return G.lo + idx.min(0) * h, G.lo + idx.max(0) * h


def boxes(prog, chain, regions, subs):
    """each level's grid box (mm, lattice-snapped): the body's x >= 0 half from 30 mm under the lowest region top, the
    regions round their own limb's solid (subs: the left limb-and-paw sub-programs; a coarse pass) plus margins"""
    P = {k: np.asarray(v, float) * 1000.0 for k, v in chain['pos'].items()}
    out = {}
    m = 6.0
    for nm, r in regions.items():
        sub = subs[nm]
        if r['level'] == 'limb':
            zc = P['carpus_L'][2] if nm == 'fore' else P['hock_L'][2]
            lo, hi = np.array([-20.0, 40.0, zc - 200.0]), np.array([150.0, r['top'] + 12.0, zc + 200.0])
        else:
            c = P['mcp_L'] if nm == 'fpaw' else P['mtp_L']
            lo, hi = np.array([c[0] - 70.0, -6.0, c[2] - 90.0]), np.array([c[0] + 70.0, r['top'] + 10.0, c[2] + 130.0])
        lo[0] = max(lo[0], -4.0)
        ext = solid_extent(sub, lo, hi, 2.0)
        assert ext is not None, nm
        a, b = ext
        h = LEVEL[r['level']]['h']
        blo = snap(np.maximum(a - m, lo), 2.0)
        bhi = snap(np.minimum(b + m, hi), 2.0, up=True)
        blo[1] = min(blo[1], -2.0) if r['level'] == 'paw' else blo[1]
        bhi[1] = snap(r['top'] + CUT_K + 4.0, 2.0, up=True)
        out[nm] = (blo, bhi, h)
    y_floor = min(r['top'] for r in regions.values() if r['level'] == 'limb') - Z1 - Z2 - 12.0
    ext = solid_extent(prog, np.array([0.0, y_floor, -260.0]), np.array([200.0, 900.0, 960.0]), 4.0)
    a, b = ext
    out['body'] = (np.array([0.0, float(snap(y_floor, 2.0)), float(snap(a[2] - 8.0, 2.0))]),
                   np.array([float(snap(b[0] + 8.0, 2.0, up=True)), float(snap(b[1] + 8.0, 2.0, up=True)),
                             float(snap(b[2] + 8.0, 2.0, up=True))]), 2.0)
    return out


# ============================================================================================ sampling the program
def sample_nb(prog, G, coarse=4, log=print):
    """the program on the grid G (mm), exact within a band round the surface: a grid `coarse` cells apart evaluated
    everywhere, each cell whose corners come within its diagonal (x 1.6) of the surface re-evaluated at every fine
    point, the rest trilinear (far from the surface the values only carry the sign: the flow redistances them)"""
    from scipy import ndimage as nd
    t = time.time()
    n = np.array(G.n)
    nc = (n - 1) // coarse + 1
    hc = G.h * coarse
    xs = [G.lo[a] + np.arange(nc[a]) * hc for a in range(3)]
    Pc = np.stack(np.meshgrid(*xs, indexing='ij'), -1).reshape(-1, 3) * 1.0e-3
    A = (prog.eval(Pc).reshape(nc) * 1000.0).astype(np.float32)
    nn = (nc - 1) * coarse + 1
    Up = nd.zoom(A, [nn[a] / nc[a] for a in range(3)], order=1, grid_mode=False, mode='nearest')
    near = np.abs(A) <= hc * np.sqrt(3.0) * 1.6
    cell = near[:-1, :-1, :-1] | near[1:, :-1, :-1] | near[:-1, 1:, :-1] | near[:-1, :-1, 1:] | \
        near[1:, 1:, :-1] | near[1:, :-1, 1:] | near[:-1, 1:, 1:] | near[1:, 1:, 1:]
    ci = np.argwhere(cell)
    o = np.stack(np.meshgrid(*[np.arange(coarse + 1)] * 3, indexing='ij'), -1).reshape(-1, 3)
    key = np.unique((((ci[:, None, :] * coarse + o[None]).reshape(-1, 3)) * np.array([nn[1] * nn[2], nn[2], 1])).sum(1))
    ii = np.stack([key // (nn[1] * nn[2]), (key // nn[2]) % nn[1], key % nn[2]], -1)
    pts = (G.lo + ii * G.h) * 1.0e-3
    vals = np.concatenate([prog.eval(pts[s:s + 2_000_000]) for s in range(0, len(pts), 2_000_000)]) * 1000.0
    Up[ii[:, 0], ii[:, 1], ii[:, 2]] = vals
    out = np.full(G.n, float(Up.max()), np.float32)
    sl = tuple(slice(0, min(G.n[a], nn[a])) for a in range(3))
    out[sl] = Up[sl]
    if any(G.n[a] > nn[a] for a in range(3)):          # the last partial coarse cell: evaluated outright
        rest = np.ones(G.n, bool)
        rest[sl] = False
        ri = np.argwhere(rest)
        out[rest] = prog.eval((G.lo + ri * G.h) * 1.0e-3) * 1000.0
    log(f'[body]   sampled the composed program on {G.n} at {G.h:.1f} mm: {len(pts) + len(Pc):,} evaluations in '
        f'{time.time() - t:.0f}s')
    return out


def sub_program(prog, idx):
    """the primitives idx of a program as a program of their own (one group, hard union; node and shell arrays
    shared): the masses as inner limits"""
    from .. import sdf as S_
    sp = S_.Program()
    sp.node_p, sp.node_n, sp.node_r, sp.node_h = prog.node_p, prog.node_n, prog.node_r, prog.node_h
    sp.shell_meshes, sp.shell_thick, sp.shell_tri = prog.shell_meshes, prog.shell_thick, prog.shell_tri
    for i in idx:
        sp.kind.append(prog.kind[i])
        sp.op.append(0)
        sp.k.append(0.0)
        p = prog.par[i].copy()
        p[20], p[21], p[22] = 0.0, 0.0, 0.0
        sp.par.append(p)
        sp.names.append(prog.names[i])
    return sp


# ============================================================================================ the side limits
def side_lines(chain, sil):
    """the photos' side-view skin lines in the clay's sagittal frame (z, y mm), each with the side its OUTSIDE lies on,
    its tolerance and the x range it holds over: sil['lines'] from build_silhouettes (the photos mapped on the ground,
    the withers height and the withers, wolf_body.SIDE)"""
    return sil['lines']


END_TAPER = 40.0                # mm: a line's tolerance grows by up to this over its last END_TAPER mm (W2d b4)


def line_field(G, line):
    """one side line's outer-limit field on G (mm): the signed distance from each voxel's (z, y) to the polyline,
    positive on its outside, where the voxel's nearest point is an interior point of the line and within `reach` of
    it and inside the line's x range; -inf elsewhere (no limit). The tolerance TAPERS OPEN over the line's last
    END_TAPER mm at either end (tol + END_TAPER at the end itself, smoothstep): a limit that stopped dead at a line's
    end (a window's edge, a photo's tail root) was a cliff in the outer limit, and the clay took it as one (W2d b4:
    the chest's crease at the r05 line's window top, y 520 mm; the croup's slot behind w03's and w05's ends)"""
    Pz = np.asarray(line['zy'], float)
    out = np.full(G.n, -np.inf, np.float32)
    # WGrid's axes: d = x, q = y, x = z (hullflow.Grid's names)
    xm = (G.d >= line['x'][0]) & (G.d <= line['x'][1])
    if not xm.any() or len(Pz) < 2:
        return out
    zz, yy = np.meshgrid(G.x, G.q, indexing='ij')      # (nz, ny): z first
    Q = np.stack([zz.ravel(), yy.ravel()], -1)
    a, b = Pz[:-1], Pz[1:]
    ab = b - a
    L2 = np.maximum((ab * ab).sum(1), 1e-12)
    cum = np.concatenate([[0.0], np.cumsum(np.sqrt(L2))])
    best = np.full(len(Q), np.inf)
    sgn = np.zeros(len(Q))
    pos = np.zeros(len(Q))
    interior = np.zeros(len(Q), bool)
    for s in range(len(a)):
        t = ((Q - a[s]) @ ab[s]) / L2[s]
        tc = np.clip(t, 0.0, 1.0)
        C = a[s] + tc[:, None] * ab[s]
        d = np.linalg.norm(Q - C, axis=1)
        upd = d < best
        best = np.where(upd, d, best)
        nrm = np.array([-ab[s, 1], ab[s, 0]]) / np.sqrt(L2[s])
        side = np.sign((Q - C) @ nrm)
        sgn = np.where(upd, side, sgn)
        pos = np.where(upd, cum[s] + tc * np.sqrt(L2[s]), pos)
        is_int = ~(((s == 0) & (t <= 0.0)) | ((s == len(a) - 1) & (t >= 1.0)))
        interior = np.where(upd, is_int, interior)
    sd = best * sgn * line['out_sign']
    # the taper opens END_TAPER mm at each end over that end's RAMP (mm along the line: line['ramp'] = (start, end),
    # default END_TAPER at both, which is the W2d builder's taper exactly). W2d check: the belly lines' front end ramps
    # over 160 mm: over 40 mm the released limit fell 1.5 mm per mm, and the clay's underline followed it from the
    # carved belly down to the composed chest floor, a 25 mm step in 20 mm behind the elbow (a lump in the side view, a
    # shelf along the chest's floor from below); over 160 the release is under 0.4 mm per mm (20 deg)
    r0, r1 = (END_TAPER if r_ is None else float(r_) for r_ in line.get('ramp') or (None, None))
    e0 = np.clip(pos / r0, 0.0, 1.0)
    e1 = np.clip((cum[-1] - pos) / r1, 0.0, 1.0)
    taper = END_TAPER * np.maximum(1.0 - e0 * e0 * (3.0 - 2.0 * e0), 1.0 - e1 * e1 * (3.0 - 2.0 * e1))
    ok = interior & (np.abs(sd) <= line['reach'])
    f2 = np.where(ok, sd - line['tol'] - taper, -np.inf).reshape(len(G.x), len(G.q)).T    # (ny, nz)
    out[xm] = f2[None, :, :]
    if line.get('slack'):
        # W2f (the lead's call 6: "the crease above the forelegs smoothed"): the limit LEANS AWAY past |x| x0 by `slope`
        # mm per mm (line['slack'] = (x0, slope)): a side line is the silhouette, made at the midline for the chest's
        # front, and held at every x it cut the lateral chest where that met the line's extrusion (the W2e check's bind
        # mesh: a crease 7.6 mm off w01's throat-chest line at x ~71, scratch_w2f/crease_probe.py)
        x0, sl_ = line['slack']
        xs = np.abs(G.d[xm])
        out[xm] = out[xm] - (sl_ * np.maximum(xs - x0, 0.0))[:, None, None].astype(np.float32)
    return out


def closing(phi, h, r, sym=False):
    """phi's zero set closed by radius r (mm): dilated by r, redistanced, eroded by r (creases tighter than r filled)"""
    if r <= 0:
        return phi
    return (HF.redistance_sym(phi - r, h, sym) + r).astype(np.float32)


def hull_limits(G, prog_phi, sil, lines, log=print, paw=False, close=0.0, sym=False):
    """the carved hull and the OUTER limit on G: the composed program cut by every side line at the line itself (the
    hull), the lower bound the side lines with their tolerances and the program CLOSED by `close` mm (the creases
    between the composed masses let fill: W2d b2 kept the chest's crease at the pectorals' top and the croup's at the
    thigh) plus TOL_PROG everywhere"""
    tol_p = TOL_PROG_PAW if paw else TOL_PROG
    lower = np.minimum(prog_phi, closing(prog_phi, G.h, close, sym)) - tol_p
    hull = prog_phi.copy()
    used = []
    for ln in lines:
        f = line_field(G, ln)
        m = np.isfinite(f)
        if not m.any():
            continue
        carve = np.where(m, f + ln['tol'], -np.inf)
        cut = int(((carve > 0) & (prog_phi < 0)).sum())
        hull = np.maximum(hull, carve)
        lower = np.maximum(lower, f)
        used.append((ln['name'], cut))
    log(f'[body]   side limits on {G.n}: ' + ', '.join(f'{n} (carves {c:,} voxels)' for n, c in used if c)
        + f'; {sum(1 for _, c in used if not c)} more lines carve nothing here')
    return hull.astype(np.float32), lower.astype(np.float32)


# ============================================================================================ the inner limits
def inner_upper(G, chain, prog, info, phi_band, lower, inset=INSET_MASS, band=16.0, log=print):
    """the INNER limits as an upper bound on phi: the measured masses (the composed program's named muscle and mass
    members, inset by `inset`: the clay contains each shrunk by it), evaluated where the surface can go (|phi_band| <
    band), and the bony points at their least skin depth (BONES: balls the clay must contain). Where a mass CLASHES
    with the photos' outer limit `lower` (the skin line deeper than the mass's inset) the MASS GIVES WAY (its bound
    raised to lower + 1 mm): the skin line is the measurement, the mass my composition's estimate, and a mass that won
    held its own inset shape up inside the carved skin as a rim (W2d b4: the oval on the withers, the croup's rim).
    The bony points hold (they win the flow's clamp; their clashes are logged)"""
    names = set(info.get('masses', []))
    idx = [i for i, n in enumerate(prog.names) if n in names]
    up = np.full(G.n, np.inf, np.float32)
    if idx:
        sp = sub_program(prog, idx)
        m = np.abs(phi_band) < band
        ii = np.nonzero(m)
        P = np.column_stack([G.d[ii[0]], G.q[ii[1]], G.x[ii[2]]]) * 1.0e-3
        f = np.concatenate([sp.eval(P[s:s + 4_000_000]) for s in range(0, len(P), 4_000_000)]) * 1000.0
        up[ii] = (f + inset).astype(np.float32)
    clash = np.isfinite(up) & (lower + 1.0 > up)
    deep = float((lower + 1.0 - up)[clash].max()) if clash.any() else 0.0
    up = np.where(clash, lower + 1.0, up).astype(np.float32)
    balls = [(c, r) for c, r in bone_balls(chain)]
    ub, _ = HF.ball_bounds(G, balls, [])
    bone_clash = int((lower > ub).sum())
    up = np.minimum(up, ub)
    log(f'[body]   inner limits on {G.n}: {len(idx)} masses inset {inset:.0f} mm, {len(balls)} bony points; the masses '
        f'gave way to the skin lines at {int(clash.sum()):,} voxels (up to {deep:.1f} mm); bony points against the lines '
        f'at {bone_clash:,} voxels (the bones hold)')
    return up


def group_sub(prog, names):
    """the primitives whose names are in `names`, each kept with its group id, op, k and box (sdf's group folding as
    in the whole program): one limb and its paw alone"""
    from .. import sdf as S_
    keep = set(names)
    sp = S_.Program()
    sp.node_p, sp.node_n, sp.node_r, sp.node_h = prog.node_p, prog.node_n, prog.node_r, prog.node_h
    sp.shell_meshes, sp.shell_thick, sp.shell_tri = prog.shell_meshes, prog.shell_thick, prog.shell_tri
    for i, nm in enumerate(prog.names):
        if nm in keep:
            sp.kind.append(prog.kind[i])
            sp.op.append(prog.op[i])
            sp.k.append(prog.k[i])
            sp.par.append(prog.par[i].copy())
            sp.names.append(nm)
    return sp


BONES = (
    # (chain anchor a, b, t, (lateral, up, forward) mm offset, radius mm) at the bony points' least skin depth: the bone
    # under the point plus 2-3 mm of skin [E] (dog anatomy; the photos' points (WOLF_BODY_PHOTOS §3.1) set where)
    # the olecranon: 0.512 WH, the elbow's point. W2e: 30 mm behind the joint (W2d 36): its skin ~39 mm behind it (a
    # large dog's olecranon tuber 30-35 mm caudal of the humeral condyles, plus the skin), so the forearm's column
    # stands as the side photos' does (its midline lean, WOLF_BODY_PHOTOS §3.3)
    # W2l (the lead's "the elbow's knob"): r 9 -> 5.5 mm, 6 mm forward and 4 up (its back 29.5 mm behind the joint, was
    # 39): the 9 mm ball stood proud of the forearm cut in under it, a pendant knob from the side and a teardrop from
    # behind; the elbow's point is now the ulnar flexor's broad round top (SPEC skin.fore.tendons), the ball inside it
    ('elbow', None, 0.0, (2.0, -2.0, -24.0), 5.5),
    # W2l (the W2i checker: "the carpal pad is a distinct knob at the back of the carpus"): 3 mm forward, r 6.5 (was 7)
    ('carpus', None, 0.0, (0.0, -4.0, -11.0), 6.5),        # the accessory carpal bone behind the carpus
    # the calcaneal tuber (0.30 WH, the hock's point) at the composed tuber's end (limbed's 'tuber' tendon: its 7.2 mm
    # end at (0, 36.9, -26.9) mm from the hock joint), inside it. W2d check: at (0, 30, -34) r 8 its back stood 8 mm
    # behind the composed tuber's and the clay had to contain it: a marble on the hock from the side, the back and the
    # medial side (check_w2d/out/hock_try_base.png; the composed hock alone is the point the lead asked for)
    ('hock', None, 0.0, (0.0, 36.0, -27.0), 6.5),
    ('stifle', None, 0.0, (2.0, -4.0, 24.0), 9.0),         # the patella and the tibial crest
    ('shoulder', None, 0.0, (4.0, 4.0, 14.0), 13.0),       # the point of the shoulder (the humerus' greater tubercle)
    ('hip', None, 0.0, (10.0, 6.0, 0.0), 14.0),            # the greater trochanter
)


def bone_balls(chain):
    P = chain['pos']
    out = []
    for a, b, t, off, r in BONES:
        for side in (1,):
            pa = np.asarray(P[f'{a}_L'], float)
            p = pa if b is None else pa + t * (np.asarray(P[f'{b}_L'], float) - pa)
            out.append((p * 1000.0 + np.array([side * off[0], off[1], off[2]]), r))
    return out


# ============================================================================================ the pressure, the flow
def pressure_field(phi_h, G, lv):
    """THE BODY'S PRESSURE: the start's own mean curvature averaged over the skin (a Gaussian of sigma lv['size_r'] mm
    over a band of 3 cells round the zero set, normalized by the band's weight), so the flow phi_t = (kappa - F)
    |grad phi| removes only the curvature's departures from its local mean (the primitives' seams and creases, ring
    bands, bulbs, the carve's edges) and keeps the composed masses' size. W2d b2 took the head's inflation pressure
    (one over the depth sensed within 16 mm): under the trunk's own curvature (radii 100-150 mm) it inflated the whole
    body to its outer limit (the program + 4 mm). kappa clipped to one over the cell (the carve's creases)"""
    from scipy import ndimage as nd
    kg, _ = HF.curvature_term(phi_h, G.h)
    kg = np.clip(kg, -1.0 / G.h, 1.0 / G.h)
    w = (np.abs(phi_h) < 3.0 * G.h).astype(np.float32)
    s = lv['size_r'] / G.h
    num = nd.gaussian_filter(kg * w, s, mode='nearest')
    den = nd.gaussian_filter(w, s, mode='nearest')
    return np.where(den > 1e-4, num / np.maximum(den, 1e-4), 0.0).astype(np.float32)


def voids(phi):
    """the outside's pieces that touch no face of the box (voids inside the solid): their count and volume (voxels)"""
    from scipy import ndimage as nd
    lab, n = nd.label(phi > 0)
    if n == 0:
        return 0, 0
    edge = set(np.unique(np.concatenate([lab[[0, -1]].ravel(), lab[:, [0, -1]].ravel(), lab[:, :, [0, -1]].ravel()])))
    inner = [i for i in range(1, n + 1) if i not in edge]
    vol = int(sum(int((lab == i).sum()) for i in inner)) if inner else 0
    return len(inner), vol


def run_flow(phi0, lower, upper, G, lv, sym, log, steps=None):
    lower = np.minimum(lower, upper)
    pr = pressure_field(phi0, G, lv)
    phi = HF.redistance_sym(np.minimum(np.maximum(phi0, lower), upper), G.h, sym)
    phi, hist = HF.flow_wp(phi, lower, upper, pr, G.h, lv['steps'] if steps is None else steps, lv['dt'],
                           lv['reinit'], log, sym=sym, band=4.0 * G.h)
    nv, vv = voids(phi)
    log(f'[body]   after the flow on {G.n}: {nv} voids inside the solid ({vv} voxels)')
    return phi, hist


# ============================================================================================ assembly
def interp_parent(Vp, Gp, Gc):
    """the parent's finished values' trilinear interpolant at the child's lattice points (exact: the child's lattice
    refines the parent's)"""
    from scipy import ndimage as nd
    X, Y, Z = Gc.mesh()
    f = np.stack([(X - Gp.lo[0]) / Gp.h, (Y - Gp.lo[1]) / Gp.h, (Z - Gp.lo[2]) / Gp.h])
    return nd.map_coordinates(Vp, f.reshape(3, -1), order=1, mode='nearest').reshape(Gc.n).astype(np.float32)


def smax(a, b, k):
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return a * h + b * (1.0 - h) + k * h * (1.0 - h)


def child_values(Vc_own, Vp_interp, G, top):
    """the child's member: the parent's interpolant over the overlap Z1, blended to its own over the feather Z2,
    its own below; cut off above the overlap (a smooth max at the top plane, its dimple inside the overlap)"""
    Y = G.q[None, :, None]
    u = top - Y                                        # depth below the top plane
    w = np.clip((u - Z1) / Z2, 0.0, 1.0)
    w = w * w * (3.0 - 2.0 * w)
    V = (1.0 - w) * Vp_interp + w * Vc_own
    return smax(V, -u + 0.0 * V, CUT_K).astype(np.float32)


def parent_cut(Vp, Gp, top):
    """the parent cut off below the overlap: a smooth max with the half-space under top - Z1 (one plane: the parent's
    grid holds nothing else that low but its children's limbs, W2d's regions)"""
    Y = Gp.q[None, :, None]
    return smax(Vp, (top - Z1) - Y + 0.0 * Vp, CUT_K).astype(np.float32)


def mirror_values(V, G):
    """the right side's member from the left's: x reversed, the origin mirrored (x0' = -(x0 + (n - 1) h))"""
    lo = G.lo.copy()
    lo[0] = -(G.lo[0] + (G.n[0] - 1) * G.h)
    return V[::-1].copy(), lo


def full_body(Vh, G):
    """the body's full-width values from its x >= 0 half (index 0 on the midline)"""
    lo = G.lo.copy()
    lo[0] = -(G.n[0] - 1) * G.h
    return np.concatenate([Vh[:0:-1], Vh], axis=0), lo


# ============================================================================================ silhouette errors
def side_errors(levels, lines, res=0.5):
    """each photo line's signed distance to the clay's side silhouette (mm, e > 0 where the photo's skin line lies
    outside the clay): the silhouette the union over the levels of each grid's min over x (its zero set by a signed
    EDT at res mm), per line (n, median |e|, p90 |e|, mean e, max |e|)"""
    from scipy import ndimage as nd
    zlo = min(G.x[0] for G, _ in levels)
    zhi = max(G.x[-1] for G, _ in levels)
    ylo = min(G.q[0] for G, _ in levels)
    yhi = max(G.q[-1] for G, _ in levels)
    nz, ny = int((zhi - zlo) / res) + 2, int((yhi - ylo) / res) + 2
    mask = np.zeros((nz, ny), bool)
    for G, phi in levels:
        mn = phi.min(axis=0).T                     # (nz, ny) after transposing (ny, nz)
        Zf = (zlo + np.arange(nz) * res - G.x[0]) / G.h
        Yf = (ylo + np.arange(ny) * res - G.q[0]) / G.h
        ZZ, YY = np.meshgrid(Zf, Yf, indexing='ij')
        inb = (ZZ >= 0) & (ZZ <= G.n[2] - 1) & (YY >= 0) & (YY <= G.n[1] - 1)
        v = nd.map_coordinates(mn, [ZZ.ravel(), YY.ravel()], order=1, mode='nearest').reshape(nz, ny)
        mask |= inb & (v < 0)
    sd = (nd.distance_transform_edt(~mask) - nd.distance_transform_edt(mask) + np.where(mask, 0.5, -0.5)) * res
    out = {}
    for ln in lines:
        P = np.asarray(ln['zy_full'], float)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        t = np.arange(0.0, s[-1], 2.0)
        Q = np.column_stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])])
        fz, fy = (Q[:, 0] - zlo) / res, (Q[:, 1] - ylo) / res
        ok = (fz >= 0) & (fz < nz - 1) & (fy >= 0) & (fy < ny - 1)
        if ok.sum() < 3:
            continue
        e = nd.map_coordinates(sd, [fz[ok], fy[ok]], order=1) * ln['out_sign_err']
        a = np.abs(e)
        out[ln['name']] = np.array([ok.sum(), np.median(a), np.percentile(a, 90), e.mean(), a.max()])
    return out


# ============================================================================================ the build
def body_volume(spec, chain, prog, info, sil, log=print):
    """THE BODY VOLUME at the bind (module docstring): the members' finished values, cached. prog / info: the composed
    body program (families/limbed.compose_body); sil: the side lines (wolf_body_refs.side_silhouettes). W2e: the strokes
    are no longer baked into the grids (STROKE members over them, families/limbed.build_volume_sdf; species/
    wolf_strokes.py), so they are not in its key either. Returns dict(members=[dict(name, region, lo mm, h mm, values
    mm)], errors={stage: {line: row}}, notes)"""
    key = HF.cache_key(dict(v=VERSION, level=LEVEL, z=(Z1, Z2, CUT_K), tc=TRUNK_CLAMP,
                            tol=(TOL_PROG, TOL_PROG_PAW, INSET_MASS),
                            bones=BONES, par=np.concatenate(prog.par).tolist(), nodes=np.asarray(prog.node_r).tolist(),
                            # W2l: the nodes' positions and their harmonics (a3, phi3, a4): node_r holds only r0, a2,
                            # phi2 and the aspect, so a sweep's keel or its centre line could change under a stale body
                            node_p=np.asarray(prog.node_p).tolist(), node_h=np.asarray(prog.node_h).tolist(),
                            pos={k: np.asarray(v).tolist() for k, v in chain['pos'].items()},
                            lines=[(ln['name'], np.asarray(ln['zy']).tolist(), ln['tol'], ln['x'], ln['reach'],
                                    ln.get('ramp')) + ((ln['slack'],) if ln.get('slack') else ())
                                   for ln in sil['lines']],
                            masses=sorted(info.get('masses', []))))

    def build():
        return _build(spec, chain, prog, info, sil, log)
    return HF.cached('wolf_body', key, build, log)


def _build(spec, chain, prog, info, sil, log):
    t0 = time.time()
    regions = region_layout(chain)
    gn = info['group_names']
    subs = dict(fore=group_sub(prog, gn['fore_L'] + gn['fpaw_L']), fpaw=group_sub(prog, gn['fore_L'] + gn['fpaw_L']),
                hind=group_sub(prog, gn['hind_L'] + gn['hpaw_L']), hpaw=group_sub(prog, gn['hind_L'] + gn['hpaw_L']))
    bx = boxes(prog, chain, regions, subs)
    lines = sil['lines']
    errs = {}
    # ---- stage A: the body at 2 mm, the x >= 0 half
    lo, hi, h = bx['body']
    GA = WGrid(lo, hi, h)
    lv = LEVEL['body']
    log(f'[body] stage A: the body at {h:.0f} mm, the x >= 0 half {GA.n} ({np.prod(GA.n) / 1e6:.1f} M voxels), box '
        f'{lo.tolist()} -> {hi.tolist()} mm')
    phiP = sample_nb(prog, GA, 4, log)
    hull, lower = hull_limits(GA, phiP, sil, [ln for ln in lines if ln['level'] in ('body', 'all')], log,
                              close=lv['close'], sym=True)
    upper = inner_upper(GA, chain, prog, info, phiP, lower, log=log)
    phiA, histA = run_flow(hull, lower, upper, GA, lv, True, log)
    mv = np.where((np.abs(hull) < 4.0) | (np.abs(phiA) < 4.0), np.abs(phiA - hull), 0.0)
    for _ in range(3):
        i_ = np.unravel_index(int(np.argmax(mv)), mv.shape)
        log(f'[body]   stage A moved the skin most at ({GA.d[i_[0]]:.0f}, {GA.q[i_[1]]:.0f}, {GA.x[i_[2]]:.0f}) mm: '
            f'{mv[i_]:.1f} mm (the hull {hull[i_]:+.1f}, flowed {phiA[i_]:+.1f}, outer limit {lower[i_]:+.1f}, inner '
            f'{upper[i_]:+.1f})')
        sl = tuple(slice(max(0, i_[a] - 10), i_[a] + 11) for a in range(3))
        mv[sl] = 0.0
    errs['hull_A'] = (GA, hull)
    errs['flow_A'] = (GA, phiA)
    VA = HF.finish(phiA, GA, lv['clamp'], lv['blur'], sym=True)
    c0, c1, y0, y1 = TRUNK_CLAMP
    u_ = np.clip((GA.q - y0) / (y1 - y0), 0.0, 1.0)
    cy = (c0 + (c1 - c0) * u_ * u_ * (3.0 - 2.0 * u_))[None, :, None]
    VA = np.clip(VA, -cy, cy).astype(np.float32)
    log(f'[body]   stage A done in {time.time() - t0:.0f}s')
    levels = {'body': (GA, VA)}
    # ---- the limbs at 1 mm (left): their own limb's composed program sampled at 1 mm, carved, flowed as long as the body
    # (the body's interpolant is only theirs over the overlap: W2d b1 started them from it, and below the body's box its
    # clamped sampling extruded the box's bottom section down the leg)
    for nm in ('fore', 'hind'):
        lo, hi, h = bx[nm]
        G = WGrid(lo, hi, h)
        lvl = LEVEL['limb']
        t = time.time()
        phiP = sample_nb(subs[nm], G, 4, log)
        hull, lower = hull_limits(G, phiP, sil, [ln for ln in lines if ln['level'] in ('limb', 'all')
                                                 and ln['limb'] in (nm, None)], log, close=lvl['close'])
        upper = inner_upper(G, chain, subs[nm], info, phiP, lower, log=log)
        phi, _ = run_flow(hull, lower, upper, G, lvl, False, log)
        errs[f'flow_{nm}'] = (G, phi)
        errs[f'hull_{nm}'] = (G, hull)
        V = HF.finish(phi, G, lvl['clamp'], lvl['blur'])
        levels[nm] = (G, V)
        log(f'[body]   {nm} at {h:.0f} mm {G.n} ({np.prod(G.n) / 1e6:.1f} M voxels) in {time.time() - t:.0f}s')
    # ---- the paws at 0.5 mm (left): the composed paw sampled at its own scale, a short flow at its own scale
    for nm in ('fpaw', 'hpaw'):
        lo, hi, h = bx[nm]
        G = WGrid(lo, hi, h)
        lvl = LEVEL['paw']
        t = time.time()
        phiP = sample_nb(subs[nm], G, 4, log)
        hull, lower = hull_limits(G, phiP, sil, [ln for ln in lines if ln['level'] == 'paw'
                                                 and ln['limb'] in (nm, None)], log, paw=True, close=lvl['close'])
        upper = inner_upper(G, chain, subs[nm], info, phiP, lower, inset=1.0, log=log)
        phi, _ = run_flow(hull, lower, upper, G, lvl, False, log)
        errs[f'hull_{nm}'] = (G, hull)
        errs[f'flow_{nm}'] = (G, phi)
        V = HF.finish(phi, G, lvl['clamp'], lvl['blur'])
        levels[nm] = (G, V)
        log(f'[body]   {nm} at {h:.1f} mm {G.n} ({np.prod(G.n) / 1e6:.1f} M voxels) in {time.time() - t:.0f}s')
    # ---- the hand-over: children take their parent's interpolant over the overlap; parents are cut below it. The
    # paws first (their parents, the limbs, keep their own values until the paws have copied them), then the limbs
    final = {k: v[1].copy() for k, v in levels.items()}
    Vp_full, lo_full = full_body(final['body'], GA)
    Gp_full = WGrid(lo_full, lo_full + (np.array(Vp_full.shape) - 1) * GA.h, GA.h)
    for nm in ('fpaw', 'hpaw', 'fore', 'hind'):
        r = regions[nm]
        G, _ = levels[nm]
        if r['parent'] == 'body':
            vp = interp_parent(Vp_full, Gp_full, G)           # the body uncut (cut once, below)
        else:
            vp = interp_parent(final[r['parent']], levels[r['parent']][0], G)
        final[nm] = child_values(final[nm], vp, G, r['top'])
        if r['parent'] != 'body':
            final[r['parent']] = parent_cut(final[r['parent']], levels[r['parent']][0], r['top'])
    final['body'] = parent_cut(final['body'], GA, regions['fore']['top'])
    # the body's full width; the right side's members mirrored
    members = []
    Vb, lob = full_body(final['body'], GA)
    members.append(dict(name='trunk', region='torso', lo=lob, h=GA.h, values=Vb))
    for nm, grp, reg in (('fore', 'fore', 'forelimb'), ('hind', 'hind', 'hindlimb'), ('fpaw', 'fpaw', 'paw'),
                         ('hpaw', 'hpaw', 'paw')):
        G, _ = levels[nm]
        members.append(dict(name=f'{grp}_L', region=reg, lo=G.lo.copy(), h=G.h, values=final[nm]))
        Vr, lor = mirror_values(final[nm], G)
        members.append(dict(name=f'{grp}_R', region=reg, lo=lor, h=G.h, values=Vr))
    # the side silhouette's errors per photo line: the hull (the composed program carved) and after the flow
    err_rows = {}
    for stage in ('hull', 'flow'):
        lv_ = [errs[f'{stage}_A']] + [errs[f'{stage}_{nm}'] for nm in ('fore', 'hind', 'fpaw', 'hpaw')]
        err_rows[stage] = side_errors(lv_, sil['err_lines'])
    res = dict(n_members=np.array(len(members)))
    for i, m in enumerate(members):
        res[f'm{i}_name'] = np.array(m['name'])
        res[f'm{i}_region'] = np.array(m['region'])
        res[f'm{i}_lo'] = np.asarray(m['lo'], float)
        res[f'm{i}_h'] = np.array(m['h'])
        res[f'm{i}_values'] = m['values'].astype(np.float32)
    for stage, rows in err_rows.items():
        for k, v in rows.items():
            res[f'err_{stage}_{k}'] = v
    for nm, (G, V) in levels.items():
        Vf = final[nm] if nm != 'body' else full_body(final['body'], GA)[0]
        lo_f = G.lo if nm != 'body' else full_body(final['body'], GA)[1]
        b_, at_ = bound_argmax(Vf, G.h)
        res[f'div_{nm}'] = np.array(b_)
        res[f'divat_{nm}'] = np.asarray(lo_f + np.asarray(at_) * G.h, float)
        log(f'[body]   {nm}: divisor {b_:.4f}, its worst cell at {np.round(lo_f + np.asarray(at_) * G.h).tolist()} mm '
            f'(the values there {Vf[at_[0]:at_[0] + 2, at_[1]:at_[1] + 2, at_[2]:at_[2] + 2].round(2).ravel().tolist()})')
    log(f'[body] the body volume in {time.time() - t0:.0f}s: {len(members)} members, '
        f'{sum(m["values"].size for m in members) / 1e6:.1f} M values')
    return res


def bound_argmax(V, h):
    """hullflow.grid_bound and the index of the cell that sets it"""
    s = []
    for a in range(3):
        e = np.abs(np.diff(V, axis=a)) / h
        others = [b for b in range(3) if b != a]
        m = None
        for o0 in (slice(0, -1), slice(1, None)):
            for o1 in (slice(0, -1), slice(1, None)):
                sl = [slice(None)] * 3
                sl[others[0]], sl[others[1]] = o0, o1
                m = e[tuple(sl)] if m is None else np.maximum(m, e[tuple(sl)])
        s.append(m.astype(np.float64))
    B = np.sqrt(s[0] ** 2 + s[1] ** 2 + s[2] ** 2)
    i = np.unravel_index(int(np.argmax(B)), B.shape)
    return float(B[i]), i


def members_of(res):
    return [dict(name=str(res[f'm{i}_name']), region=str(res[f'm{i}_region']), lo=res[f'm{i}_lo'],
                 h=float(res[f'm{i}_h']), values=res[f'm{i}_values']) for i in range(int(res['n_members']))]
