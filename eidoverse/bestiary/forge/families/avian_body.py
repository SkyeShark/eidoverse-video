"""The AVIAN body's skin (HAWK_PLAN.md §4.1, §4.2, §4.5): the SDF program of the skin under the plumage, built on the
bind skeleton (families/avian.py rest_chain, life mm, world). The members in metres (the forge's sdf.Program).

THE SKIN, not the plumage (plan §4.2): contour feathers lie flat (the Gorvid's mean card distance 0.00 cm [R]), so the
coat's cards sit on this surface plus a per-tract loft; the plumage envelope (plumage_program) adds a coat depth c(p)
(sdf OFFSET, the wolf's kind 6) for the silhouette gates and the cage's head and thigh regions.

MEMBERS (life mm [E] unless sourced; one group each, round-blended where they meet):
  trunk     a SWEEP along the body axis in the FLIGHT frame (pitched to the world by chain['R']): from the vent behind
            the synsacrum to the crop before the furcula, elliptical sections whose width and depth follow TRUNK
            (the keel's depth: S1's sternum 64.1 mm keel to rim; the breast's width over the pectorals; the glenoids
            and the hips inside it)
  tail root a SWEEP over the free caudals and the pygostyle (plan §4.5: about 40 x 25 mm with its coverts' bases)
  neck      a SWEEP through the neck joints (the perch's S), from inside the trunk's crop to the head's occiput
  wings     the wing SKIN (pro- and postpatagium, the hand's skin) as ONE continuous SHELL per side (sdf
            Program.shell(continuous=True): its half-thickness varies across the sheet, so the default rule's step
            where the closest point jumps would crack it; W2w's lesson on the wolf's ear): a triangulated patch in the
            wing's plane whose leading edge lies the half-thickness inside the Beaty mean LE (the SHELL rounds it by
            that radius: the LE sits ON the mean) and whose trailing edge is the flight feathers' insertion line plus
            INS_SKIN (their bases sink under it, plan §4.2); half-thickness WING_HT. The arm's bulk (the humerus's
            and forearm's muscles, the hand's) is a round cone per bone inside the sheet.
  legs      the thigh ("trousers'" skin: the femur and the tibiotarsus's muscles) and the tarsus as round cones on S1's
            bones; the toes as round cones per phalanx, their pads below (avian.PAD)
  talons    separate keratin shells (talon_programs): a curved cone per toe from SPEC feet.claw_arc's sweep, sunk
            into its nail bed
"""
import numpy as np

from .. import sdf
from . import avian as AV

MM = 1e-3
# trunk stations in the FLIGHT frame: z (mm along the body axis, 0 = the hips), centre y, half width, half depth [E]
# (the skin under the plumage: the plan's plumaged 130 x 150 mm less about 20 mm a side of contour feathers and down;
# a 1.04 kg bird's trunk of about 0.8 L; the scapulars' skin 10 mm over the glenoid (y 22), the keel 60 mm under the
# sternum's rim)
TRUNK = np.array([
    # z      y     hw    hh
    [-52.0, 6.0, 12.0, 10.0],
    [-40.0, 5.0, 24.0, 20.0],
    [-22.0, 2.0, 34.0, 32.0],
    [-2.0, -4.0, 40.0, 42.0],
    [22.0, -12.0, 44.0, 52.0],
    [46.0, -14.0, 46.0, 55.0],
    [68.0, -6.0, 43.0, 45.0],
    [84.0, 8.0, 33.0, 30.0],
    [95.0, 18.0, 20.0, 18.0],
])
TAIL_ROOT = np.array([       # flight frame: z, y, half width, half depth [E] (plan §4.5: 40 x 25 mm)
    [-44.0, 6.0, 18.0, 11.0],
    [-64.0, 8.0, 19.0, 10.0],
    [-86.0, 9.0, 17.0, 8.0],
    [-96.0, 9.0, 13.0, 6.0],
])
NECK_R = (22.0, 15.5)       # [E] D1.3's neck tube radii (kept for the cage's spine path: neck() below is the clay)
# THE NECK AS ITS FEATHERED VOLUME (D1.3b): the skin tube round the vertebrae's S (D1.3) read as a long stalk under the
# head (the D1.3 check, beside c022 / c029 / c019: a perched red-tail shows no neck; the head sits on the shoulders, the
# nape and the throat run straight into the mantle and the breast). The neck's contour feathers are long and fill the
# S's hollows, so here the clay is that filled volume, as plan §4.2 already builds the head and the thighs on their
# plumage: one tapered elliptical tube on a STRAIGHT line from inside the crop to under the occiput (the S inside it).
# Stations (fraction along the line, half width, half depth (sagittal), the centre's offset forward, mm) [E: c019's
# head-on neck as wide as the head's cheeks; c022 / c029 side: the throat line from the chin to the breast]
NECK_FILL = np.array([
    [0.00, 30.0, 30.0, 0.0],
    [0.35, 26.0, 26.0, 2.0],
    [0.70, 20.0, 21.0, 2.0],
    [1.00, 16.5, 17.0, 0.0],
])
NECK_BLEND = 14.0           # mm: the neck's smooth union into the trunk (the mantle's and the breast's feather line)
LEG_BLEND = 6.0             # mm: the thighs' smooth union into the flanks (8 dipped |grad| under 0.6 there): the
#                             trunk's fold into the pair of legs (skin_program: the legs are folded first)
INS_SKIN = 4.0              # mm the skin runs past the feathers' insertion line (avian D1.4's band used the same)
WING_HT = dict(le_root=4.0, le_wrist=3.0, le_digit=2.2, web=1.0, te=2.4, te_hand=2.0)   # half-thicknesses [E]
#                             (plan §4.5: the LE radius 3-5 mm; the membrane 2 mm; the insertion band holds the
#                             follicles of the secondaries / primaries)
SHOULDER_FAIR = np.array([  # the wing root (_arm_cones): mm along the humerus from the glenoid, half chord, half
    # thickness, the centre's offset along the chord (forward: the propatagium's base) [E: plan §8.1's 60 x 30 ring;
    # c148 / c151: the wing's root runs the shoulder's depth fore and aft]
    [0.0, 30.0, 14.0, 0.0],
    [18.0, 24.0, 11.0, 2.0],
    [36.0, 15.0, 8.0, 1.5],
    [55.0, 8.0, 6.0, 0.0],
])
ARM_R = dict(humerus=(9.0, 6.5), forearm=(6.5, 4.2), hand=(4.2, 3.0), digit=(3.0, 2.2))   # [E] the bone + muscle
THIGH = dict(hip=19.0, knee=14.0, ankle=6.5, tarsus=(6.5, 6.0), toe=(4.6, 3.4))   # [E] radii (S1's tarsometatarsus
#                             15.1 mm across its trochleae; the shaft about 9 mm; scutes and skin over it)


PER_NODE_EPS = 2.0          # mm: the PSWEEPs' PER-NODE DIVISOR's near band (D1.3c, staged for sdf.py in
#                             work/bestiary/hawk/d13c/STAGED.md): every hawk PSWEEP opts in where the installed sdf has it.
#                             2 mm holds the sculpts' depths (plan 4.8: under 1.2 mm) and the gradient gate's samples
#                             (-0.5 .. +1.5 mm); at 3 the curved members' near need (H = gam - (reach + eps) curv: the
#                             hook's pieces, the lower bill, the talons) stood 10-20 % higher for nothing


def pn_kw():
    """psweep's per-node divisor argument where the installed sdf.py has it (the staged hawk/d13c/sdf_pernode.py until
    the landing), else none: the live module builds exactly what it built before"""
    import inspect
    return {'per_node': PER_NODE_EPS * MM} if 'per_node' in inspect.signature(sdf.Program.psweep).parameters else {}


PIECE_SINK = 0.4            # mm: ellipse_psweep's pieces sink this far under their neighbours at their overlaps' ends


def _u(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _smoothstep(x):
    x = np.clip(np.asarray(x, float), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _fw(chain, p):
    """flight frame -> world mm (the pitch and the ground shift of rest_chain)"""
    return (chain['R'] @ np.asarray(p, float).T).T + chain['shift']


def _dense(stations, step=2.0, z_hi=None):
    """resample a station table (z first) to about `step` mm with a smooth (Catmull-Rom) interpolation per column.
    z_hi: stop there (the WHOLE table's curves, sampled up to z_hi: cutting the table's rows first and resampling
    the rest gave another curve near the cut: the trunk's straight pieces ran up to 1.3 mm inside the tube over their
    last 14 mm, a step across the breast where the tilted front piece takes over; D1.3c restart 3)"""
    S = np.asarray(stations, float)
    S = S[np.argsort(S[:, 0])]
    z = S[:, 0]
    zz = np.arange(z.max() if z_hi is None else float(z_hi), z.min() - 1e-9, -step)[::-1]
    from scipy.interpolate import PchipInterpolator
    return np.column_stack([zz] + [PchipInterpolator(z, S[:, k])(zz) for k in range(1, S.shape[1])])


def ellipse_psweep(prog, C, normal, hw, hh, op=sdf.UNION, k=0.0, name='', n=128, pieces=1, off=0.0, straight=False,
                   axis=None, y_w=None, lap=3):
    """an ELLIPTICAL tube (life mm in, metres stored): a PSWEEP whose key at each node is the ellipse polygon
    (half width hw along `normal`, half height hh along t x normal). D1.3: SWEEP's aspect is not a distance bound
    (|grad f| p99 1.19-1.21 on the trunk, head and talons against the 1.05 bar); PSWEEP's 2D distance is exact and its
    divisor keeps it a bound. n 128 polygon points (48 showed as facet stripes in the head's shading: the normals kink
    at each corner, though the sag is 0.04 mm; this clay is the bakes' high). pieces > 1 splits it into overlapping PSWEEPs (each divisor from its own reach and turn)
    added to the current group (the caller's begin_group) or as separate members.
    y_w (D1.3c, per node, mm; None = the plain ellipse, as before): the section's WIDEST level, above its centre: two
    half ellipses joined there with vertical tangents (the upper of height hh - y_w, the lower hh + y_w), so the
    section keeps its height 2 hh and its half width hw at y_w (the raptor's head: widest at the brows).
    lap (D1.3c fix 2; 3 = as before): the nodes each piece runs past its own share, sinking under its neighbour
    (the head's envelope has six stations per old node now and keeps the same overlap in mm: lap 18)"""
    C = np.asarray(C, float)
    N = len(C)
    hw = np.broadcast_to(np.asarray(hw, float), (N,))
    hh = np.broadcast_to(np.asarray(hh, float), (N,))
    nrm = np.broadcast_to(np.asarray(normal, float), (N, 3)).copy()
    off = np.broadcast_to(np.asarray(off, float), (N,))          # the ellipse's centre off the line along t x normal
    a = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    yw = np.zeros(N) if y_w is None else np.broadcast_to(np.asarray(y_w, float), (N,))
    sa = np.sin(a)

    def keys_of(sink):
        """the ellipse keys, each half axis less sink (per node, mm)"""
        if y_w is None:
            return np.stack([np.stack([(hw[j] - sink[j]) * np.cos(a), off[j] + (hh[j] - sink[j]) * sa], 1)
                             for j in range(N)]) * MM
        return np.stack([np.stack([(hw[j] - sink[j]) * np.cos(a), off[j] + yw[j] + np.where(
            sa >= 0, hh[j] - sink[j] - yw[j], hh[j] - sink[j] + yw[j]) * sa], 1) for j in range(N)]) * MM
    out = []
    edges = np.linspace(0, N - 1, pieces + 1).round().astype(int)
    for p in range(pieces):
        i0, i1 = max(edges[p] - lap, 0), min(edges[p + 1] + lap, N - 1) + 1
        # each piece's overlap past its own share (3 nodes each way) SINKS under its neighbour's surface, PIECE_SINK at
        # its last node (a smoothstep from 0 at the share's end node, where both are whole): so every surface point
        # is one piece's and no piece's flat end meets the surface. D1.3c fix 1: with the ends' rims ON the surface,
        # the neighbour's smaller field (its larger divisor) took the rim's distance near it: the field's gradient
        # tilted 2 deg in a band round the head at each piece's end, a ring in every sphere-traced view head-on (the
        # D1.3c check's "circular seam round the lower face")
        jj = np.arange(N, dtype=float)
        ds = np.maximum(edges[p] - jj, 0.0) + np.maximum(jj - edges[p + 1], 0.0)
        sink = np.where(pieces > 1, PIECE_SINK * _smoothstep(ds / float(lap)), 0.0)
        Cp, kp = C[i0:i1], keys_of(sink)[i0:i1].copy()
        if straight and i1 - i0 > 2:
            # the piece's own straight line, PARALLEL to the whole tube's end-to-end axis, through the piece's mean
            # centre; each ellipse offset on it in its plane (D1.3: the trunk's centres climb 24 mm from the breast to
            # the crop, and that motion of the keys set the divisor; the offset within one piece is small). Every
            # piece's planes are normal to the one axis, so the pieces' surfaces coincide where they overlap (lines
            # through each piece's own ends tilted its sections: rings on the trunk)
            t = (C[-1] - C[0]) if axis is None else np.asarray(axis, float)
            t = t / np.linalg.norm(t)
            s_ = (Cp - Cp.mean(0)) @ t
            Lp = Cp.mean(0)[None] + s_[:, None] * t[None]
            b = np.cross(t, nrm[i0])
            dlt = Cp - Lp
            kp[:, :, 0] += (dlt @ nrm[i0])[:, None] * MM
            kp[:, :, 1] += (dlt @ b)[:, None] * MM
            Cp = Lp
        out.append(prog.psweep(Cp * MM, kp, rho=0.0, key=np.arange(i1 - i0, dtype=float),
                               normal=nrm[i0:i1], op=op, k=k, name=f'{name}' if pieces == 1 else f'{name}_{p}',
                               check=False, **pn_kw()))
    return out


def _tilted_cut_piece(prog, chain, table, z0, z1, tilt, name, step=2.0, n=128, op=sdf.UNION, k=0.0, covers_from=None):
    """a PSWEEP over the table's tube (its ellipses normal to the body axis) between z0 and z1 at the axis, on a
    straight line TILTED `tilt` deg up from the body axis, its keys the tube's CUTS by the planes normal to that line
    (D1.3c: where the breast rises 60 deg into the crop, planes normal to the body axis cut it at a grazing angle: its
    points moved 2 mm per mm, the trunk's front pieces' divisors 2.3 over every segment, |grad| 0.44 over the
    breast's top and flanks). The same surface, so the straight pieces it overlaps meet it exactly. covers_from: the
    z (at the axis's normal plane) where the straight pieces END: asserted, that this piece's first plane lies 2 mm or
    more behind that whole section. Its planes are tilted, so under the axis they stand FORWARD of z0 by the
    section's depth x tan(tilt): with z0 12 mm behind the cut the breast had a wedge of nothing between the two, 6
    mm wide at the skin and 16 deep (D1.3c restart 3 found it in the clay's views). Life mm in"""
    Dd = _dense(table, 0.5)
    zt, yc, hw, hh = Dd[:, 0], Dd[:, 1], Dd[:, 2], Dd[:, 3]
    th = np.radians(tilt)
    u = np.array([0.0, np.sin(th), np.cos(th)])                  # the line's direction (flight frame)
    ex = np.array([1.0, 0.0, 0.0])
    ey = np.cross(u, ex)                                          # the PSWEEP frame's y: t x n
    zm = 0.5 * (z0 + z1)
    Q0 = np.array([0.0, float(np.interp(zm, zt, yc)), zm])
    L = (z1 - z0) / np.cos(th)
    tj = np.arange(-0.5 * L, 0.5 * L + 1e-9, step)
    a = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    nodes, keys = [], []
    for t in tj:
        c = Q0 + t * u
        lo, hi = np.full(n, zt[0]), np.full(n, zt[-1])
        g = lambda z_: ((np.interp(z_, zt, yc) + np.interp(z_, zt, hh) * np.sin(a) - c[1]) * u[1] + (z_ - c[2]) * u[2])
        if (g(lo) > 0).any() or (g(hi) < 0).any():
            continue                                              # the plane leaves the tube's ends: no node here
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            pos = g(mid) > 0
            hi = np.where(pos, mid, hi)
            lo = np.where(pos, lo, mid)
        z_ = 0.5 * (lo + hi)
        P = np.stack([np.interp(z_, zt, hw) * np.cos(a), np.interp(z_, zt, yc) + np.interp(z_, zt, hh) * np.sin(a), z_],
                     1)
        nodes.append(c)
        keys.append(np.stack([(P - c) @ ex, (P - c) @ ey], 1))
    nodes = np.array(nodes)
    if covers_from is not None:
        zc = float(covers_from)
        Pc = np.stack([np.interp(zc, zt, hw) * np.cos(a), np.interp(zc, zt, yc) + np.interp(zc, zt, hh) * np.sin(a),
                       np.full(n, zc)], 1)
        lead = float(((Pc - nodes[0]) @ u).min())
        assert lead >= 2.0, (f'{name}: its first plane stands {-lead:+.1f} mm IN FRONT of the section at z {zc:g} '
                             f'somewhere: a void between it and the straight pieces (start it farther back: z0)')
    Cw = _fw(chain, nodes)
    nw = chain['R'] @ ex
    return prog.psweep(Cw * MM, np.array(keys) * MM, rho=0.0, key=np.arange(len(nodes), dtype=float),
                       normal=np.tile(nw, (len(nodes), 1)), op=op, k=k, name=name, check=False, **pn_kw())


TRUNK_FRONT = dict(z_cut=62.0, z0=34.0, z1=92.0, tilt=32.0, pieces=7)
#                                         [D1.3c] the trunk's straight pieces end at z_cut (flight mm); the front from
#                                         z0 to z1 (at the axis) is _tilted_cut_piece's, tilted `tilt` deg. z0 34: its
#                                         first plane 4.8 mm behind the cut's section at the breast, the section's
#                                         lowest point (50: 11.4 mm in FRONT of it there, the wedge of nothing)


def _sweep_from_table(prog, chain, table, name, op=sdf.UNION, k=0.0, step=2.0, pieces=1, z_hi=None):
    D = _dense(table, step, z_hi)
    C = _fw(chain, np.column_stack([np.zeros(len(D)), D[:, 1], D[:, 0]]))
    # straight lines per piece, the ellipses offset on them (a line through the centres turns too sharply for the band
    # at the trunk's 55 mm reach: D1.3)
    ellipse_psweep(prog, C, [1.0, 0.0, 0.0], D[:, 2], D[:, 3], op=op, k=k, name=name, pieces=pieces, straight=True,
                   axis=chain['R'] @ np.array([0.0, 0.0, 1.0]))      # the table's sections are normal to the body axis
    return None, C, D


# --------------------------------------------------------------------------------------------- the wing skin
def wing_patch(spec, chain, nx=72, ny=14):
    """the wing skin's SHELL patch for the LEFT wing: V (n, 3) world mm, F (m, 3), ht (n,) mm, plus the 2D outline
    frame data. The patch spans from x 8 mm (inside the trunk: the root blends into the body) to the digit tip; at each
    span station its leading edge is the mean LE + ht_LE (the SHELL's round puts the skin's edge ON the mean LE) and its
    trailing edge the feathers' insertion line + INS_SKIN"""
    ol, wp, fe = chain['outline'], chain['wing'], chain['feathers']
    to_xy = wp['to_xy']
    pts = {k: to_xy(v) for k, v in wp['pts'].items()}
    x_tip = pts['digit_tip'][0] + 2.0
    ins = sorted([to_xy(f['ins']) for f in fe.values() if f['group'] != 'alula'], key=lambda p: p[0])
    ins = np.array(ins)
    # the insertion line as a function of x (the inner tertials' insertions run toward the root; past the last one
    # inward the line is carried flat to the root at the trunk's side)
    xi, yi = ins[:, 0], ins[:, 1]
    xs = np.linspace(8.0, x_tip, nx)
    wrist_x = pts['wrist'][0]

    def ht_le(x):
        return np.interp(x, [8.0, wrist_x, x_tip], [WING_HT['le_root'], WING_HT['le_wrist'], WING_HT['le_digit']])

    le = np.interp(xs, ol['x'], ol['le']) + ht_le(xs)
    te = np.interp(xs, xi, yi, left=yi[0]) + INS_SKIN - np.interp(xs, [8.0, x_tip], [WING_HT['te'],
                                                                                         WING_HT['te_hand']])
    # the patch must stay a sheet: at the hand the chord (the LE to the insertions) narrows to the digit's width
    te = np.maximum(te, le + 2.0)
    vs = np.linspace(0.0, 1.0, ny)
    X = np.repeat(xs[:, None], ny, 1)
    Y = le[:, None] + (te - le)[:, None] * vs[None, :]
    # half-thickness: the LE round eases into the web, the web into the insertion band (smooth in v)
    sm = lambda a, b, v: np.clip((v - a) / (b - a), 0.0, 1.0) ** 2 * (3 - 2 * np.clip((v - a) / (b - a), 0.0, 1.0))
    hle = ht_le(X)
    hte = np.interp(X, [8.0, x_tip], [WING_HT['te'], WING_HT['te_hand']])
    H = hle + (WING_HT['web'] - hle) * sm(0.0, 0.35, Y * 0 + vs[None, :]) + (hte - WING_HT['web']) * \
        sm(0.70, 1.0, Y * 0 + vs[None, :])
    # into the world: outline (x, y) -> wing plane (u, v) -> the flight frame (glenoid + (u, 0, v)) -> world
    G = np.array(AV.GLENOID)
    UV = np.stack([X.ravel() - wp['x0'], wp['y_g'] - Y.ravel()], 1)
    Pf = G[None] + np.column_stack([UV[:, 0], np.zeros(len(UV)), UV[:, 1]])
    V = _fw(chain, Pf)
    F = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            a, b, c, d = i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1
            F += [[a, b, c], [a, c, d]]
    return V, np.array(F), H.ravel(), dict(xs=xs, le=le, te=te, ht_le=ht_le(xs))


def _arm_cones(prog, chain, side, k):
    P = chain['pos']
    s = side
    segs = [('humerus', 'shoulder', 'elbow'), ('forearm', 'elbow', 'wrist'), ('hand', 'wrist', 'cmc_end'),
            ('digit', 'cmc_end', 'digit_tip')]
    for nm, a, b in segs:
        ra, rb = ARM_R[nm]
        prog.roundcone(np.asarray(P[f'{a}_{s}']) * MM, np.asarray(P[f'{b}_{s}']) * MM, ra * MM, rb * MM,
                       op=sdf.UNION, k=k * MM, name=f'arm_{nm}_{s}')
    # the WING ROOT (D1.3b): the humeral tract's skin and the propatagium's / the axilla's bases, a flat elliptical
    # tube along the humerus from inside the trunk, chord-wide at the body (plan §8.1: the shoulder ring about 60 x 30
    # mm, the propatagium's base included), easing to the arm's cone by SHOULDER_FAIR's last station. D1.3 had the
    # arm's 9 mm cone straight out of the trunk: the cage's K 24 loop ran about 190 mm round on the trunk and 50 on the
    # arm, and the funnel between folded (20 flipped quads, the D1.3 report)
    sh, el = np.asarray(P[f'shoulder_{s}'], float), np.asarray(P[f'elbow_{s}'], float)
    t_h = _u(el - sh)
    chord = chain['R'] @ np.array([0.0, 0.0, 1.0])               # the body axis: the wing's chord direction at its root
    chord = _u(chord - t_h * (chord @ t_h))
    st = SHOULDER_FAIR
    ss = np.linspace(st[0, 0], st[-1, 0], 24)
    C = sh[None] + ss[:, None] * t_h[None] + np.interp(ss, st[:, 0], st[:, 3])[:, None] * chord[None]
    ellipse_psweep(prog, C, chord, np.interp(ss, st[:, 0], st[:, 1]), np.interp(ss, st[:, 0], st[:, 2]),
                   op=sdf.UNION, k=k * MM, name=f'wing_root_{s}', n=96, straight=True, axis=t_h)


# --------------------------------------------------------------------------------------------- legs, toes, talons
def _leg_members(prog, chain, side, k):
    P = chain['pos']
    s = side
    hip = np.asarray(P[f'femur_{s}'], float)
    knee = np.asarray(P[f'tibiotarsus_{s}'], float)
    ank = np.asarray(P[f'tarsometatarsus_{s}'], float)
    foot = np.asarray(P[f'foot_{s}'], float)
    sg = 1.0 if s == 'L' else -1.0
    # the thigh's skin: from inside the flank over the femur to the knee, then the drumstick to the intertarsal joint
    prog.roundcone((hip + np.array([sg * 6.0, 4.0, 4.0])) * MM, knee * MM, THIGH['hip'] * MM, THIGH['knee'] * MM,
                   op=sdf.UNION, k=k * MM, name=f'thigh_{s}')
    prog.roundcone(knee * MM, ank * MM, THIGH['knee'] * MM, THIGH['ankle'] * MM, op=sdf.UNION, k=k * MM,
                   name=f'drumstick_{s}')
    prog.roundcone(ank * MM, foot * MM, THIGH['tarsus'][0] * MM, THIGH['tarsus'][1] * MM, op=sdf.UNION, k=1.5 * MM,
                   name=f'tarsus_{s}')
    toes = chain['toes']
    for t, g in toes.items():
        pts = [np.asarray(p, float) * np.array([sg, 1.0, 1.0]) for p in g['pts']]
        ra, rb = THIGH['toe']
        # the toe's skin rides on its phalanges: the pad's underside PAD below the joints, the top 1.5 mm over them
        lift = np.array([0.0, -(AV.PAD - ra) * 0.5 + 0.5, 0.0])
        n = len(pts)
        prog.roundcone(foot * MM, (pts[0] + lift) * MM, THIGH['tarsus'][1] * MM, ra * MM, op=sdf.UNION, k=2.0 * MM,
                       name=f'toe_{t}_base_{s}')
        for i in range(n - 1):
            r0 = ra + (rb - ra) * i / max(n - 1, 1)
            r1 = ra + (rb - ra) * (i + 1) / max(n - 1, 1)
            prog.roundcone((pts[i] + lift) * MM, (pts[i + 1] + lift) * MM, r0 * MM, r1 * MM, op=sdf.UNION,
                           k=1.0 * MM, name=f'toe_{t}_{i + 1}_{s}')


def talon_programs(spec, chain, side='L'):
    """one closed keratin shell per toe (a SWEEP along an arc of SPEC feet.claw_arc deg in the toe's vertical plane,
    laterally compressed: aspect 1.35, tapering to a 0.25 mm point), its base sunk 1.5 mm into the toe's tip.
    Returns {toe: dict(prog, C, r0)}"""
    sg = 1.0 if side == 'L' else -1.0
    out = {}
    arc = np.radians(spec['feet']['claw_arc'])
    for t, (frac, yaw, claw) in AV.TOE.items():
        g = chain['toes'][t]
        last = np.asarray(g['pts'][-1], float) * np.array([sg, 1.0, 1.0])
        d = _u(np.asarray(g['dir'], float) * np.array([sg, 1.0, 1.0]))
        up = np.array([0.0, 1.0, 0.0])
        base = last + d * (THIGH['toe'][1] - 1.5) + np.array([0.0, 0.8, 0.0])
        R = claw / arc                                  # the claw's length along its curve = claw (mm)
        n = 40
        th = np.linspace(0.0, arc, n)
        # a circle in the (d, up) plane, starting along d and curling down
        C = base[None] + R * (np.sin(th)[:, None] * d[None] + (np.cos(th) - 1.0)[:, None] * up[None])
        r = np.interp(np.linspace(0, 1, n), [0.0, 0.15, 1.0], [2.9, 2.6, 0.25]) * (claw / 28.0) ** 0.5
        side_ax = _u(np.cross(up, d))
        p = sdf.Program()
        ellipse_psweep(p, C, side_ax, r, 1.35 * r, name=f'talon_{t}_{side}', n=64)
        out[t] = dict(prog=p, C=C, r0=float(r[0]))
    return out


# --------------------------------------------------------------------------------------------- the program
def skin_program(spec, chain, wings=True, head=True, legs=True):
    """the skin's sdf.Program (metres) and its info (world mm): the trunk + tail root + neck (+ the head's members
    from heads/raptor) in one round-blended group, then each wing's SHELL + arm cones, then each leg"""
    from ..heads import raptor as RP
    prog = sdf.Program()
    info = {}
    P = chain['pos']
    # THE LEGS FIRST (D1.3c): the left leg, the right HARD-unioned with it, then the trunk blended into the pair. A
    # fold of two mirror-symmetric fields is symmetric, so the clay is its own mirror image exactly. Folded last, one
    # after the other (D1.3 .. D1.3b), the right leg met the body WITH the left already in it: between the thighs under
    # the belly (the knees stand 4 mm apart) the three-way blend moved the right thigh's inner face 0.2 mm nearer the
    # midline than the left's, and the mirrored cage could not lie on both. And the two legs do not blend with EACH
    # OTHER (they did, by the group's 6 mm): across the 3.4 mm gap between the thighs the two fields, their gradients
    # 158 deg apart, blended to |grad| 0.59 on the thighs' own inner faces (13 % of the skin's low-gradient samples),
    # and the inner toes, which cross at their tips in the bind, were webbed. Each leg meets the trunk as before
    for sd in (('L', 'R') if legs else ()):
        prog.begin_group(op=sdf.UNION, k=0.0)
        _leg_members(prog, chain, sd, k=4.0)
        prog.end_group()
    prog.begin_group(op=sdf.UNION, k=(LEG_BLEND * MM if legs else 0.0))
    # in pieces (one hard-unioned group): one PSWEEP's divisor was 2.30, set by the rump's and the crop's steep ends,
    # which put |grad f| at 0.44 over the whole trunk (D1.3); D1.3c: the straight pieces end at TRUNK_FRONT['z_cut'],
    # the breast's rise into the crop is one TILTED piece (_tilted_cut_piece)
    TF = TRUNK_FRONT
    z_c = TF['z_cut']
    _sweep_from_table(prog, chain, TRUNK, 'trunk', op=sdf.UNION, k=0.0, pieces=TF['pieces'], z_hi=z_c)
    _tilted_cut_piece(prog, chain, TRUNK, TF['z0'], TF['z1'], TF['tilt'], 'trunk_front', covers_from=z_c)
    prog.end_group()
    Dt = _dense(TRUNK, 2.0)                                       # (the whole table: the cage's spine reads it)
    Ct = _fw(chain, np.column_stack([np.zeros(len(Dt)), Dt[:, 1], Dt[:, 0]]))
    _, Cr, Dr = _sweep_from_table(prog, chain, TAIL_ROOT, 'tail_root', op=sdf.UNION, k=10.0 * MM)
    info['trunk'] = dict(C=Ct, table=Dt)
    info['tail_root'] = dict(C=Cr, table=Dr)
    # the neck: from inside the crop through the joints to under the occiput
    nj = spec['body']['neck_joints']
    pts = [_fw(chain, [0.0, 10.0, 80.0])] + [np.asarray(P[f'neck_{i}'], float) for i in range(nj)] + \
        [np.asarray(P['head'], float) + np.array([0.0, -2.0, 4.0])]
    pts = np.array(pts)
    from scipy.interpolate import CubicSpline
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    cs = CubicSpline(s, pts, bc_type='natural')
    ss = np.linspace(0.0, s[-1], int(s[-1] / 2.0) + 2)
    Cn = cs(ss)
    rn = np.interp(ss / s[-1], [0.0, 0.3, 1.0], [NECK_R[0], 0.5 * (NECK_R[0] + NECK_R[1]), NECK_R[1]])
    # the clay: the feathered volume (NECK_FILL) on the straight line from the S's first point to its last
    a, b = pts[0], pts[-1]
    tn = np.linspace(0.0, 1.0, 40)
    t_ax = _u(b - a)
    fwd_n = _u(np.cross(np.array([1.0, 0.0, 0.0]), t_ax))         # in the sagittal plane, normal to the line
    if fwd_n[2] < 0:
        fwd_n = -fwd_n
    Cf = a[None] + tn[:, None] * (b - a)[None] + np.interp(tn, NECK_FILL[:, 0], NECK_FILL[:, 3])[:, None] * fwd_n[None]
    # (three pieces hard-unioned in a group that blends into the trunk: each piece's divisor from its own taper)
    prog.begin_group(op=sdf.UNION, k=NECK_BLEND * MM)
    ellipse_psweep(prog, Cf, [1.0, 0.0, 0.0], np.interp(tn, NECK_FILL[:, 0], NECK_FILL[:, 1]),
                   np.interp(tn, NECK_FILL[:, 0], NECK_FILL[:, 2]), op=sdf.UNION, k=0.0, name='neck',
                   straight=True, axis=t_ax, pieces=3)
    prog.end_group()
    info['neck'] = dict(C=Cn, r=rn, fill=Cf)
    if head:
        info['head'] = RP.head_members(prog, spec, chain)
    if wings:
        Vw, Fw, Hw, wd = wing_patch(spec, chain)
        info['wing'] = dict(V=Vw, F=Fw, ht=Hw, **wd)
        for sd in ('L', 'R'):
            V = Vw if sd == 'L' else Vw * np.array([-1.0, 1.0, 1.0])
            F = Fw if sd == 'L' else Fw[:, ::-1]
            prog.begin_group(op=sdf.UNION, k=9.0 * MM)
            prog.shell(V * MM, F, Hw * MM, op=sdf.UNION, k=0.0, maxd=0.05, name=f'wing_skin_{sd}', continuous=True)
            _arm_cones(prog, chain, sd, k=3.0)
            prog.end_group()
    return prog, info


def shells(spec, chain):
    """the keratin shells (each its own closed Program): the two rhamphothecae and eight talons"""
    from ..heads import raptor as RP
    out = {}
    bk = RP.beak(spec, chain)
    out['beak_upper'] = bk['upper']
    out['beak_lower'] = bk['lower']
    for sd in ('L', 'R'):
        for t, v in talon_programs(spec, chain, sd).items():
            out[f'talon_{t}_{sd}'] = v
    return out, bk['frame']
