"""AX4 (work/bestiary/research/AXOLOTL_PLAN.md §5.5, §5.8, §6; the gates of §5.5): THE SPRAWL FAMILY'S DESIGNED CAGE,
built part by part on the accepted clay and AX3's records (work/bestiary/axolotl/seams.json). The FORELIMB first and
complete: it runs ahead through AX5-AX9 for AX-X1 (the octopus arm ending in an axolotl forearm and hand). The body
loft, the head, the gill-base regions, the hindlimbs, the rami and the fin membranes follow on the same conventions.

CONVENTIONS (forge/mesh.py, loft.Tube, seams.json): life mm in the plan frame of the bind (x lateral, + the creature's
left; y up; z forward); the step script scales by chain['k'] to the forge's x4 metres. Every ring is right-handed about
its distal direction with vertex 0 on its frame's X, so a quad (ring_i[k], ring_i[k+1], ring_i+1[k+1], ring_i+1[k])
winds counter-clockwise seen from outside. The RIGHT limb is the exact mirror of the left (x -> -x, the quads reversed),
so its record rings come out as AX3's R records (themselves L's exact mirrors) and |x_L + x_R| = 0.

THE FORELIMB, from the body outward (research/game_study/CREATURE_LOOPS_STUDY.md: a limb is its own loop system whose
first ring is an oval on the flank; a hand is a flattened palm tube splitting into digit tubes, the poles in the clefts):
  1 the FOOTPRINT ring (K 16): per column, where the arm's sweep surface enters the body (the true junction curve,
    ports.cone_footprint's idea on the sweep), cast onto the clay's fillet. It is the limb's open root: the body's port
    block and the halfway ring meet it in the body build (the shared gill-base region: AX3 found r3's port 0.19 mm
    from this footprint, so the port block is laid with the gills');
  2 FILLET rings to the AXILLA ring (AX3's record, bit for bit), each column's arc interpolated;
  3 the ARM: K 16 rings about one square-quad step apart, their planes on a turning-weighted slerp of the frames
    between records (the elbow's 90 deg turn spread, so no two ring planes meet inside the tube; the columns' twist
    shared out with it), through the FOREARM ring (record) and the wrist onto the palm, three loops at least in each
    hinge zone AX3 recorded (elbow, wrist, the carpal, metacarpal and knuckle rows);
  4 the PALM: K 16 rings onto the HAND ring (record, sag-spaced: its columns crowd the palm's rounded edges), its
    collar ring at +h, three rings in the knuckle row's zone, then a two-row TILE STRIP 16 -> 32: each of the 8 long
    flat chords becomes 3 edges (a 2-row tile: the narrow ring stays clean, its 5-pole sits in the middle row and its
    3-pole on the end ring, on a web corner where one is under the tile), each of the 8 short edge-cap chords 1;
  5 the END ring (32) = the four digits' base rings (K 8: 3 dorsal edges, 1 side, 3 palmar, 1 side) and the three web
    quads between them (the interdigital margin: one quad over the middle band of the palm's front face between two
    fingers; the strip's second row wraps the front edge's rounding above and below it);
  6 the DIGITS: K 8 rings along each finger past the palm's front edge (three loops within one radius of the IP joint,
    the knuckle's are the palm's), a 2 x 2 quad-grid tip cap (loft.cap).
THE HINDLIMB is the same construction (limb('hind', ...)): groin, knee, shank, ankle, the sole and five toes; its
strip pairs the sole ring's edge-cap chords into 2 -> 4 units (16 -> 40), KINDS.
THE LEAD'S TWO CALLS (10-29), both before the forelimb freezes at AX5:
  - the LENGTH SEAM on one column: AX3's seam vertices (seams.json seam_k, nearest the caudomedial hidden line) are
    joined by one column per limb: the span from one record to the next joins column k to vertex k + m (m = the seam
    vertices' difference), the extra twist spent with the records' own. The thigh's seam (groin 1 -> shank 10) costs
    its columns a -91.4 deg twist (+66.1 as the records' frames left them): the caudomedial line itself turns -87 deg
    round the sprawled thigh and knee;
  - the WEDGE (plan 5.5) on the compression side of each elbow and knee: the bend's inner side is a sharp V crease in
    the clay, so one ring is pinned on it (each crease column cast on the crease line, fixed in the fit) and a closed
    loop round its inner half (two partial rings, one on each wall of the V) gives the fold its extra loops; its poles
    (four 5- and four 3-) sit on the bend's sides. The bend zone's rings step wider (bend_step) so the wedge doubles
    the inner side's loops instead of halving a band the fan had already narrowed.
"""
import math

import numpy as np

from .. import loft as LF
from ..mesh import QuadMesh

TAU = 2.0 * math.pi
REGIONS = ('root', 'arm', 'palm', 'digit', 'web', 'cap', 'ramus')
DIGIT_ANGLES = np.radians(22.5 + 45.0 * np.arange(8))   # T0 T1 T2 T3 (dorsal, lateral to medial), B3 B2 B1 B0
# the two limbs: AX3's ring names (the proximal, mid and distal cuts), the clay's member names, the digits lateral to
# medial, and the autopod strip's units over the hand / foot ring's 16 chords (k = 0 .. 15, from vertex 0 on the
# lateral equator): 'S' straight (1 end edge), 'T' a 2-row TILE (3: its 5-pole in the middle row, its 3-pole on the end
# ring), 'U' a 2-row 2 -> 4 unit over this chord and the next ('x'; 4 end edges: one 5-pole, one 3-pole). The flat
# chords take tiles, the short edge-cap chords stay single (the hand: 8 x 1 + 8 x 3 = 32 = 4 digits x 8) or pair up
# (the foot: 4 x 4 + 8 x 3 = 40 = 5 digits x 8); the lateral side edge 15-0 meets the lateral digit's side edge
KINDS = dict(
    fore=dict(rings=('axilla', 'forearm', 'hand'), tube='fore', pod='palm', digit='finger', joint='f_digit',
              digits=(4, 3, 2, 1), units='SSTTTTSSSSTTTTSS', bend='elbow', bend2='wrist', sigma=(5.0, 3.0),
              knuckle_at=(0.07, 0.5, 0.93), bend_step=1.15),
    # (bend_step: the elbow / knee zone's ring step with the wedge. The fan left the inner side's edges 0.45-0.63 mm
    # against chords of 1.0-1.3, so the wedge halving them made quads of aspect 5.5-7; swept 1.15 / 1.3 / 1.45 (knee
    # 1.5 / 1.7 / 1.9): the elbow's 1.15 keeps the arm's min angle p1 41 deg, the knee's 1.7 its wedge's quads >= 25.7
    # deg)
    # the foot: the knee turns 102 deg (the elbow 91) and its columns twist 66 deg, so its spread is wider; the outer
    # toes splay 36 deg and their bases' corners reach back beside the sole's equators, so the knuckle zone's rings
    # (the last is the strip's narrow ring) sit earlier in it: at 0.93 the strip's equator columns were 0.05 mm long
    hind=dict(rings=('groin', 'shank', 'foot'), tube='hind', pod='sole', digit='toe', joint='h_digit',
              digits=(5, 4, 3, 2, 1), units='UxTTTTUxUxTTTTUx', bend='knee', bend2='ankle', sigma=(9.0, 4.0),
              knuckle_at=(0.0, 0.3, 0.6), pod_step=0.8, knuckle_eq=(0.5, 0.8, 1.0), arm_step=1.15, bend_step=1.7),
    # (pod_step: the sole is long (the foot ring 11 mm along it) and wide, its sag-spaced flat chords 2.6-2.8 mm: rings
    # 0.6 apart made them aspect 4.7; 0.8 between the hinge zones, still 0.6 inside them. knuckle_eq: past the foot
    # ring's collar its knuckle rings blend the record's sag-spaced columns toward equal arc, so the wide sole's flats
    # are not two 2.7 mm chords a quadrant under rings 0.54 apart. arm_step: the thigh's square step, 2 pi 3.0 / 16:
    # at the arm's 0.9 the knee's inner side kept four quads at aspect 4.1-4.8)
)
CAGE = dict(
    fillet_step=1.5,       # mm over the columns' geometric mean span (2.88-7.50 here: two rings; 1.0 and 1.25 left
    #                        the short posterior columns' quads at aspect 5.4 and 4.3, p99)
    arm_step=0.9,          # mm between the axilla and the forearm rings (square quads at r 2.15-2.45: 0.84-0.96)
    wrist_n=16,            # intervals between the forearm and the hand rings (0.60 mm: 3 loops in each wrist zone)
    slerp_sigma=1.5,       # mm: the Gaussian that spreads a span's turning over its ring planes (the default; the
    #                        limbs' own are KINDS' sigma: the elbow's / knee's bend radius is about the tube's, so
    #                        planes turning at the limb's own rate meet at the inner crease, 0.08 mm apart there;
    #                        swept 3 / 4 / 5 / 6 (wrist 2 / 2.5 / 3 / 3.5): from 5 / 3 no arm quad's aspect is over 4)
    strip_relax=12,        # rounds of umbrella smoothing on the tile strip's middle ring (on the clay)
    twist_in_zone=0.35,    # the columns' twist rate inside a hinge zone, against 1 outside (all outside sheared the
    twist_sigma=0.8,       # wrist's flanks where the rate jumped); smoothed over this many mm
    digit_step=0.45,       # mm between digit rings (square quads at K 8, r 0.55-0.64)
    digit_clear=1.18,      # a base ring's vertices within this x the finger radius of its axis: on the finger alone
    relax_iters=6,
    wedge_cols=8,          # the wedge's width in columns: the inner half, so its poles sit on the bend's sides
    twist_on_pod=0.0,      # the columns' twist rate on the palm / sole (against 1 on the tube outside the zones): with
    #                        the seam's offsets the wrist / ankle spans twist -70.5 / -76.5 deg, and spent on the flat
    #                        sole too it took its quads to aspect p99 4.86 (0: 3.29, no twist on the slab)
)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


class Field:
    """a clay program (the forge's sdf.Program, x4 metres) seen in life mm"""

    def __init__(self, prg, km):
        self.prg, self.km = prg, float(km)

    def eval(self, P):
        return self.prg.eval(np.asarray(P, np.float64).reshape(-1, 3) * self.km).astype(np.float64) / self.km

    def normals(self, P):
        return self.prg.normals(np.asarray(P, np.float64).reshape(-1, 3) * self.km)

    def cast(self, O, D, rmax):
        """from points O inside the clay along unit directions D to its zero set (the forge's projector);
        returns (points, ok)"""
        D = np.asarray(D, np.float64).reshape(-1, 3)
        O = np.broadcast_to(np.asarray(O, np.float64).reshape(-1, 3), D.shape)
        P, st = self.prg.project(O * self.km, D, maxd=float(rmax) * self.km)
        return P / self.km, st == 0

    def nearest(self, P, iters=8):
        """Newton steps onto the zero set along the gradient"""
        P = np.asarray(P, np.float64).reshape(-1, 3).copy()
        for _ in range(iters):
            P = P - self.eval(P)[:, None] * self.normals(P)
        return P


class Track:
    """a centreline (life mm): the point and the tangent at an arc (np.gradient tangents, linear between nodes: AX3's
    Track, so a record's origin and Z are reproduced at its arc)"""

    def __init__(self, P):
        self.P = np.asarray(P, np.float64)
        self.L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(self.P, axis=0), axis=1))])
        self.T = unit(np.gradient(self.P, axis=0))

    def at(self, a):
        a = float(np.clip(a, 0.0, self.L[-1]))
        i = int(np.clip(np.searchsorted(self.L, a, side='right') - 1, 0, len(self.P) - 2))
        f = (a - self.L[i]) / max(self.L[i + 1] - self.L[i], 1e-12)
        return self.P[i] + f * (self.P[i + 1] - self.P[i]), unit(self.T[i] * (1 - f) + self.T[i + 1] * f)


def rotation(axis, ang):
    x, y, z = unit(axis)
    K = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + math.sin(ang) * K + (1.0 - math.cos(ang)) * (K @ K)


def axis_angle(R):
    ang = math.acos(float(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)))
    if ang < 1e-12:
        return np.array([0.0, 0.0, 1.0]), 0.0
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2.0 * math.sin(ang))
    return unit(ax), ang


def frame_of(rec):
    """a record's frame as columns (X, Y, Z)"""
    c = rec['frame']['creature']
    return np.column_stack([c['X'], c['Y'], c['Z']]).astype(np.float64)


def turning_weight(track, a0, a1, sigma, step=0.02):
    """w(a) on [a0, a1]: the share of the span's turning (the tangent's cumulative angle) done by a, smoothed by a
    Gaussian of sigma mm and renormalised to 0 .. 1 (monotone): the ring planes turn with the arm, spread"""
    from scipy.ndimage import gaussian_filter1d
    a = np.linspace(a0, a1, max(int(math.ceil((a1 - a0) / step)), 2) + 1)
    T = np.array([track.at(x)[1] for x in a])
    d = np.arccos(np.clip((T[1:] * T[:-1]).sum(1), -1.0, 1.0))
    phi = np.concatenate([[0.0], np.cumsum(d)])
    w = phi / phi[-1] if phi[-1] > 1e-6 else (a - a0) / (a1 - a0)
    w = gaussian_filter1d(w, sigma / (a[1] - a[0]), mode='nearest')
    w = (w - w[0]) / max(w[-1] - w[0], 1e-12)
    return lambda x: float(np.interp(x, a, w))


class Builder:
    """vertices (life mm) with a region per vertex, quads, named rings"""

    def __init__(self):
        self.V, self.R, self.Q, self.rings, self.fixed = [], [], [], {}, []

    def add(self, P, region, fixed=False):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        n0 = sum(len(v) for v in self.V)
        self.V.append(P)
        self.R.append(np.full(len(P), REGIONS.index(region)))
        self.fixed.append(np.full(len(P), bool(fixed)))
        return np.arange(n0, n0 + len(P))

    def quad(self, a, b, c, d):
        self.Q.append((int(a), int(b), int(c), int(d)))

    def strip(self, ra, rb):
        K = len(ra)
        for k in range(K):
            self.quad(ra[k], ra[(k + 1) % K], rb[(k + 1) % K], rb[k])

    def mesh(self):
        V = np.concatenate(self.V)
        reg = np.concatenate(self.R)
        part = np.zeros((len(V), len(REGIONS)))
        part[np.arange(len(V)), reg] = 1.0
        return QuadMesh(V, np.array(self.Q, np.int64), {'part': part}), np.concatenate(self.fixed)


def cast_ring(field, O, F, thetas, rmax):
    """a planar ring: rays from O in the plane of the frame F's X and Y at the angles (right-handed about Z)"""
    D = np.cos(thetas)[:, None] * F[:, 0][None] + np.sin(thetas)[:, None] * F[:, 1][None]
    return field.cast(O, D, rmax)


def unwrap_deg(a):
    a = np.radians(np.asarray(a, np.float64))
    return np.unwrap(np.concatenate([a, a[:1] + TAU]))[:-1]


def limb(kind, rec, members, joints, field, body, log=print):
    """the LEFT fore- or hindlimb's cage (life mm; kind 'fore' or 'hind', KINDS). rec: AX3's records {proximal, mid,
    distal ring}_L (axilla / forearm / hand, groin / shank / foot); members: the clay's limb members for that limb in
    life mm {tube, pod, digit1 ..} ('fore', 'palm', 'finger1'..; 'hind', 'sole', 'toe1'..; dicts with P, N, r0);
    joints: {name: position} for the digits' {joint}{n}_{0,1}_L; field: the clay (Field); body: the body alone (a
    Field: the junction and the corner's bisector). The comments name the forelimb's parts; the hindlimb's are the
    same in order (groin, knee, shank, ankle, sole, toes). Returns a dict: mesh (QuadMesh, attrs 'part'), fixed (bool
    per vertex: the records' and the footprint's vertices, never moved by the fit), rings (name -> vertex ids),
    stations (the limb's ring arcs on the tube + pod track), digits (each digit's stations), notes"""
    C = CAGE
    KD = KINDS[kind]
    nm_ax, nm_fa, nm_hd = (f'{r}_L' for r in KD['rings'])
    body_sd, body_normal = body.eval, body.normals
    B = Builder()
    notes = []
    fore, palm = members[KD['tube']], members[KD['pod']]
    tf, tp = Track(fore['P']), Track(palm['P'])
    Lf = tf.L[-1]
    arm = Track(np.vstack([fore['P'], palm['P'][1:]]))          # the carpus is the fore's end and the palm's start
    ax, fa, hd = rec[nm_ax], rec[nm_fa], rec[nm_hd]
    a_ax, a_fa, a_hd = ax['arc_mm'], fa['arc_mm'], Lf + hd['arc_mm']
    F_ax, F_fa, F_hd = frame_of(ax), frame_of(fa), frame_of(hd)
    th_ax, th_fa, th_hd = unwrap_deg(ax['angles_deg']), unwrap_deg(fa['angles_deg']), unwrap_deg(hd['angles_deg'])
    r_arm = lambda a: float(np.interp(a, tf.L, fore['r0']))                 # noqa: E731

    # ---- 1 the footprint: per column, the last arc (from the axilla back) where the sweep's surface is in the body
    dirs = np.cos(th_ax)[:, None] * F_ax[:, 0] + np.sin(th_ax)[:, None] * F_ax[:, 1]
    a_grid = np.arange(a_ax, 0.0, -0.02)
    S = np.array([[tf.at(a)[0] + r_arm(a) * dirs[k] for a in a_grid] for k in range(16)])
    sd = body_sd(S.reshape(-1, 3)).reshape(16, len(a_grid))
    assert (sd <= 0.0).any(axis=1).all(), 'a column of the arm never enters the body'
    a_j = np.array([a_grid[int(np.argmax(sd[k] <= 0.0))] for k in range(16)])
    # each root point from OUTSIDE: the sweep's surface point S at the column's arc (on the body at the junction, in the
    # air or the fillet beyond it), the ray coming in along the bisector u of the column's direction and the body's
    # normal there (u points out of the concave corner): it meets the fillet without running into the body's bulk (a
    # ray along a posterior column from the axis does: the junction is oblique) and without the nearest-point collapse
    # of neighbouring columns in the armpit's crease
    sweep_pt = lambda aa: np.array([tf.at(aa[k])[0] + r_arm(aa[k]) * dirs[k] for k in range(16)])   # noqa: E731

    def root_ring(aa, s=0.0):
        """s: 0 at the footprint (the corner's bisector) .. 1 at the axilla (the column's own radial ray). The ray
        starts outside the clay: 2.0 mm out at the footprint (the fillet bulges up to ~1.5 mm past the junction),
        0.5 mm at the axilla, halved where that start is still inside (behind the arm the body's flank is near)"""
        Sp = sweep_pt(aa)
        u = unit((1.0 - s) * unit(dirs + body_normal(Sp)) + s * dirs)
        off = np.full(16, 2.0 - 1.5 * s)
        for _ in range(6):
            inside = field.eval(Sp + off[:, None] * u) <= 0.0
            if not inside.any():
                break
            off[inside] *= 0.5
        P, ok = field.cast(Sp + off[:, None] * u, u, off.max() + 2.0)
        return P, ok

    foot, ok = root_ring(a_j)
    notes.append(f'the footprint: the sweep enters the body at arcs {a_j.min():.2f}-{a_j.max():.2f} mm (the axilla ring '
                 f'at {a_ax:.2f}), each junction cast onto the fillet from outside along the corner\'s bisector: '
                 f'{int(ok.sum())} / 16 landed; the fillet bulges {float(np.linalg.norm(foot - sweep_pt(a_j), axis=1).max()):.2f}'
                 f' mm at most past the junction')
    ring_ids = [B.add(foot, 'root', fixed=True)]
    B.rings[f'footprint_{kind}_L'] = ring_ids[0]
    # the fillet's rings: each column's points evenly along the straight segment from its footprint vertex to its
    # axilla vertex, moved to the nearest clay (on the concave fillet the segment runs through the air in the corner,
    # so the points keep their order; a cast per ring with a direction blended from the bisector to the radial slid
    # the posterior footprint 0.017 mm from the next ring's vertex). The junction is oblique (each column's span
    # differs), so the count balances the longest span's quads against the shortest's: the geometric mean span
    sp = a_ax - a_j
    n_f = max(2, int(round(math.sqrt(float(sp.max() * sp.min())) / C['fillet_step'])) - 1)
    V_ax = np.array(ax['verts_mm'])
    for i in range(1, n_f + 1):
        s = i / (n_f + 1.0)
        ring_ids.append(B.add(field.nearest((1.0 - s) * foot + s * V_ax), 'root'))
    notes.append(f'the fillet: {n_f} rings between the footprint and the axilla ring (the columns\' spans '
                 f'{sp.min():.2f}-{sp.max():.2f} mm along the arm)')
    ring_ids.append(B.add(np.array(ax['verts_mm']), 'arm', fixed=True))
    B.rings[nm_ax] = ring_ids[-1]
    stations = [a_ax]
    # the length seam (the lead's call, 10-29): AX3's seam vertices (seams.json seam_k, nearest the caudomedial hidden
    # line) are joined by ONE column per span: span A -> B joins A's column k to B's vertex k + m, m = seam_B - seam_A
    # taken in [-8, 8). Each ring keeps its own vertex order (the records bit for bit); ring_off holds its offset from
    # the canonical order (the footprint's, the fillet's and the proximal record's), and the strips join canonical
    # columns
    seam = [int(rec[nm]['seam_k']) for nm in (nm_ax, nm_fa, nm_hd)]
    m_seam = [((seam[1] - seam[0] + 8) % 16) - 8, ((seam[2] - seam[1] + 8) % 16) - 8]
    ring_off = [0] * len(ring_ids)
    notes.append(f'the length seam: AX3\'s seam vertices {seam} ({nm_ax}, {nm_fa}, {nm_hd}), joined by one column: the '
                 f'spans offset {m_seam[0]:+d} and {m_seam[1]:+d} columns')

    # ---- 3 the arm and the wrist: between two records the ring planes BEND with the arm (the minimal rotation from
    # one record's Z to the next, by the turning weight) and the columns TWIST linearly in arc outside the hinge zones
    # (the records' X differ by a twist: each is its port frame's lateral axis made normal to its own Z; spent inside
    # the elbow it shears the quads on the bend's inner side)
    def span(aA, FA, thA, aB, FB, thB, n, region_of, ang_from, zones=(), sigma=C['slerp_sigma'], step_out=None,
             step_in=0.6, col_off=0, off=0, pin=None):
        """n rings evenly in arc, or (step_out) about step_out mm apart outside the zones and step_in inside them.
        col_off: the column offset (the lead's seam call: A's column k ends on B's vertex k + col_off, so the column
        through A's seam vertex ends on B's seam vertex and the length seam is ONE column); off: A's offset from the
        canonical column order (the axilla's), carried by every ring of the span. pin(geom) -> (arc, per-column arcs):
        one ring forced at that arc, each column with a finite arc cast at it and fixed (the crease ring). Returns the
        span's ring geometry geom(a) -> (origin, frame, angles) and the pinned ring's index in ring_ids"""
        from scipy.ndimage import gaussian_filter1d
        w = turning_weight(arm, aA, aB, sigma)
        ZA, ZB = FA[:, 2], FB[:, 2]
        axb = np.cross(ZA, ZB)
        ang_b = math.atan2(float(np.linalg.norm(axb)), float(ZA @ ZB))
        R_bend = (lambda t: rotation(axb, ang_b * t)) if np.linalg.norm(axb) > 1e-9 else (lambda t: np.eye(3))
        X1 = R_bend(1.0) @ FA[:, 0]
        psi0 = math.atan2(float(np.cross(X1, FB[:, 0]) @ ZB), float(X1 @ FB[:, 0]))
        # the seam offset: the frame twists col_off columns more, so it ends at B's frame turned by dpsi about Z_B,
        # where B's vertex k + col_off sits at its angle less dpsi (near A's own angle k on an equal-arc ring)
        K = len(thA)
        dpsi = TAU * col_off / K
        psi = psi0 + dpsi
        thB = np.array([thB[(k + col_off) % K] + TAU * ((k + col_off) // K) for k in range(K)]) - dpsi
        xs = np.linspace(aA, aB, 401)
        m = np.array([C['twist_in_zone'] if any(z0 <= x <= z1 for z0, z1 in zones) else 1.0 for x in xs])
        m = np.where(xs > Lf, C['twist_on_pod'], m)                       # the palm / sole (CAGE twist_on_pod)
        m = gaussian_filter1d(m, C['twist_sigma'] / (xs[1] - xs[0]), mode='nearest')    # no kink where a zone starts
        cm = np.concatenate([[0.0], np.cumsum(0.5 * (m[1:] + m[:-1]) * np.diff(xs))])
        u_tw = (lambda a: float(np.interp(a, xs, cm / cm[-1]))) if cm[-1] > 1e-9 else (lambda a: (a - aA) / (aB - aA))
        notes.append(f'span {aA:.2f} -> {aB:.2f} mm: the planes bend {math.degrees(ang_b):.1f} deg, the columns twist '
                     f'{math.degrees(psi):+.1f} deg (the records\' frames {math.degrees(psi0):+.1f}, the seam offset '
                     f'{col_off:+d} columns) outside the zones '
                     f'{[(round(float(z0), 2), round(float(z1), 2)) for z0, z1 in zones]}')

        def geom(a):
            """the ring at arc a: its origin, frame and column angles (A's column order)"""
            Rb = R_bend(w(a))
            Zi = Rb @ ZA
            Xi = rotation(Zi, psi * u_tw(a)) @ (Rb @ FA[:, 0])
            Fi = np.column_stack([Xi, np.cross(Zi, Xi), Zi])
            f = float(np.clip((a - ang_from) / (aB - ang_from), 0.0, 1.0)) if aB > ang_from else 0.0
            f = f * f * (3.0 - 2.0 * f)
            return arm.at(a)[0], Fi, thA + f * (thB - thA)

        a_pin, col_arcs = pin(geom) if pin is not None else (None, None)

        def arcs_on(a0, a1):
            """the ring arcs from a0 to a1 (both included): step_out outside the zones and step_in inside, else n"""
            if step_out is None:
                k_ = max(1, int(round(n * (a1 - a0) / (aB - aA))))
                return a0 + (a1 - a0) * np.arange(k_ + 1) / k_
            xs_ = np.linspace(a0, a1, 801)
            dens = np.array([1.0 / step_in if any(z0 <= x <= z1 for z0, z1 in zones) else 1.0 / step_out for x in xs_])
            cum = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(xs_))])
            k_ = max(1, int(round(cum[-1])))
            return np.interp(np.arange(k_ + 1) * cum[-1] / k_, cum, xs_)

        arcs = arcs_on(aA, aB) if a_pin is None else np.concatenate([arcs_on(aA, a_pin), arcs_on(a_pin, aB)[1:]])
        i_pin = None
        for i in range(1, len(arcs) - 1):
            a = float(arcs[i])
            O, Fi, th = geom(a)
            P, ok = cast_ring(field, O, Fi, th, 6.0)
            pinned = a_pin is not None and abs(a - a_pin) < 1e-12
            if pinned:
                for k in np.nonzero(np.isfinite(col_arcs))[0]:          # each crease column on the crease line
                    Ok, Fk, thk = geom(float(col_arcs[k]))
                    Pk, okk = cast_ring(field, Ok, Fk, np.array([thk[k]]), 6.0)
                    P[k], ok[k] = Pk[0], okk[0]
            if not ok.all():
                notes.append(f'arm ring at arc {a:.2f}: {int((~ok).sum())} rays missed')
            ring_ids.append(B.add(P, region_of(a)))
            if pinned:
                # the crease vertices are DESIGNED on the V's edge: fixed, as the records (the fit's relaxation slid
                # them onto one wall, and the knee's quads beside them read the other wall's normal at two corners)
                i_pin = len(ring_ids) - 1
                B.fixed[-1][np.isfinite(col_arcs)] = True
            ring_off.append(off)
            stations.append(a)
        return geom, i_pin

    region_arm = lambda a: 'arm' if a <= Lf else 'palm'                     # noqa: E731
    z_fore = [tuple(z['arc']) for z in fa['hinge_zones']]                   # the elbow and the wrist (fore arcs)
    z_palm = [(Lf + z['arc'][0], Lf + z['arc'][1]) for z in hd['hinge_zones']]   # the carpal, metacarpal, knuckle rows
    n_arm = max(2, int(round((a_fa - a_ax) / KD.get('arm_step', C['arm_step']))))
    i_span1 = len(ring_ids)
    bend_step = KD.get('bend_step')       # the bend zone's ring step: the wedge doubles the inner side's loops there
    z_b = tuple(fa['hinge_zones'][0]['arc'])                                # the elbow / knee zone
    d_in = unit(arm.at(z_b[1])[1] - arm.at(z_b[0])[1])                     # toward the bend's inner side
    crease = {}

    def pin_crease(geom):
        """the bend's inner side is a sharp V crease in the clay (its normal flips 80-130 deg between neighbouring
        rings, no ring in between): one ring is pinned on it, each crease column at its own arc, so the wedge's bands
        either side lie each on one wall (a band across the crease tilted 70-90 deg off the clay)"""
        a_s, col_arcs, k_in = crease_columns(geom, field, d_in, arm.at(z_b[0])[1], arm.at(z_b[1])[1], z_b)
        lim_ = 0.35 * (bend_step or KD.get('arm_step', C['arm_step']))      # within the bands either side
        col_arcs = np.where(np.abs(col_arcs - a_s) <= lim_, col_arcs, np.nan)
        crease.update(arc=a_s, cols=col_arcs, k_in=k_in)
        return a_s, col_arcs

    geom1, i_h = span(a_ax, F_ax, th_ax, a_fa, F_fa, th_fa, n_arm, region_arm, a_ax,
                      zones=[z for z in z_fore if z[1] > a_ax and z[0] < a_fa], sigma=KD['sigma'][0],
                      step_out=KD.get('arm_step', C['arm_step']) if bend_step else None, step_in=bend_step or 0.6,
                      col_off=m_seam[0], off=0, pin=pin_crease if C['wedge_cols'] else None)
    ring_ids.append(B.add(np.array(fa['verts_mm']), 'arm', fixed=True))
    ring_off.append(m_seam[0])
    B.rings[nm_fa] = ring_ids[-1]
    stations.append(a_fa)
    span(a_fa, F_fa, th_fa, a_hd, F_hd, th_hd, C['wrist_n'], region_arm, Lf - 1.0,
         zones=[z for z in z_fore + z_palm if z[1] > a_fa and z[0] < a_hd], sigma=KD['sigma'][1],
         step_out=KD.get('pod_step'), col_off=m_seam[1], off=m_seam[0])
    ring_ids.append(B.add(np.array(hd['verts_mm']), 'palm', fixed=True))
    ring_off.append(m_seam[0] + m_seam[1])
    B.rings[nm_hd] = ring_ids[-1]
    i_hand = len(ring_ids) - 1
    stations.append(a_hd)

    # ---- 4 the palm beyond the hand ring: the collar, the knuckle zone's rings (the hand ring's columns), the frame
    # carried along the palm track by minimal rotations
    Fc, Zc = F_hd.copy(), F_hd[:, 2].copy()
    zk = hd['hinge_zones'][-1]['arc']                                         # the knuckle row's zone (palm arcs)
    eq = (0.0,) + tuple(KD.get('knuckle_eq', (0.0, 0.0, 0.0)))                 # the collar keeps the record's angles
    for i_p, a_p in enumerate([hd['arc_mm'] + hd['h_mm']] + [zk[0] + f * (zk[1] - zk[0]) for f in KD['knuckle_at']]):
        O, T = tp.at(a_p)
        axv = np.cross(Zc, T)
        if np.linalg.norm(axv) > 1e-12:
            Fc = rotation(axv, math.asin(min(1.0, float(np.linalg.norm(axv))))) @ Fc
        Zc = Fc[:, 2]
        th = th_hd
        if eq[i_p] > 0.0:                                     # beyond the collar the columns may even out across
            th_eq = []                                        # the flats: equal arc per quadrant, blended in
            for q in range(4):
                dense = th_hd[4 * q] + np.linspace(0.0, TAU / 4, 49)
                Pd, _ = cast_ring(field, O, Fc, dense, 6.0)
                acc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))])
                th_eq.append(np.interp(acc[-1] * np.arange(4) / 4, acc, dense))
            th = (1.0 - eq[i_p]) * th_hd + eq[i_p] * np.concatenate(th_eq)
        P, ok = cast_ring(field, O, Fc, th, 6.0)
        if not ok.all():
            notes.append(f'palm ring at palm arc {a_p:.2f}: {int((~ok).sum())} rays missed')
        ring_ids.append(B.add(P, 'palm'))
        ring_off.append(m_seam[0] + m_seam[1])
        stations.append(Lf + a_p)
    canon = [np.roll(r, -o) for r, o in zip(ring_ids, ring_off)]       # each ring in the canonical column order
    for i in range(len(ring_ids) - 1):
        B.strip(canon[i], canon[i + 1])
    narrow = ring_ids[-1]
    B.rings[f'{KD["rings"][2]}_collar_L'] = ring_ids[i_hand + 1]

    # ---- 5 the digits' base rings (lateral to medial: digit 4, 3, 2, 1) and the end ring
    order = KD['digits']
    nd = len(order)
    digs = []
    for n in order:
        m = members[f'{KD["digit"]}{n}']
        tr = Track(m['P'])
        Nn = np.asarray(m['N'], np.float64)
        r0 = np.asarray(m['r0'], np.float64)

        def frame_at(a, tr=tr, Nn=Nn):
            O, Z = tr.at(a)
            i = int(np.clip(np.searchsorted(tr.L, a) - 1, 0, len(Nn) - 1))
            Y = unit(Nn[i] - Z * (Nn[i] @ Z))
            return O, np.column_stack([np.cross(Y, Z), Y, Z])

        a_d0 = float(tr.L[int(np.argmin(np.linalg.norm(tr.P - joints[f'{KD["joint"]}{n}_0_L'], axis=1)))])
        a_b, base = None, None
        for a in np.arange(a_d0, tr.L[-1] - 1.0, 0.05):
            O, F = frame_at(a)
            P, ok = cast_ring(field, O, F, DIGIT_ANGLES, 2.0)
            r = float(np.interp(a, tr.L, r0))
            if ok.all() and (np.linalg.norm(P - O, axis=1) <= C['digit_clear'] * r).all():
                a_b, base = float(a), P
                break
        assert a_b is not None, f'no base station on finger {n}'
        digs.append(dict(n=n, tr=tr, frame_at=frame_at, r0=r0, a_b=a_b, base=base, a_d0=a_d0))
        ip_name = f'{KD["joint"]}{n}_1_L'
        a_ip0 = float(tr.L[int(np.argmin(np.linalg.norm(tr.P - joints[ip_name], axis=1)))])
        notes.append(f'digit {n}: its base ring at arc {a_b:.2f} on its {KD["digit"]} (the MCP at {a_d0:.2f}, the IP at '
                     f'{a_ip0:.2f}, {tr.L[-1]:.2f} long)')
    # the end ring's 8 nd vertices: the tops lateral to medial (digit i's T_m at 4 i + m), then the bottoms medial to
    # lateral (digit i's B_m at 4 nd + 4 (nd - 1 - i) + 3 - m)
    NE = 8 * nd
    top = lambda i, m: 4 * i + m                                              # noqa: E731
    bot = lambda i, m: 4 * nd + 4 * (nd - 1 - i) + (3 - m)                   # noqa: E731
    end_pos = np.zeros((NE, 3))
    for i, d in enumerate(digs):
        for m in range(4):
            end_pos[top(i, m)] = d['base'][m]                    # T0 T1 T2 T3
            end_pos[bot(i, m)] = d['base'][7 - m]                # base[4..7] = B3 B2 B1 B0
    end = B.add(end_pos, 'digit')
    B.rings[f'end_{kind}_L'] = end
    for i, d in enumerate(digs):
        d['ring0'] = end[[top(i, 0), top(i, 1), top(i, 2), top(i, 3), bot(i, 3), bot(i, 2), bot(i, 1), bot(i, 0)]]

    # ---- the strip: the middle ring (one vertex under each narrow-ring vertex) and the quads, unit by unit
    units = KD['units']
    start, anchor, j = {}, np.zeros(16, int), 0
    for k in range(16):
        if units[k] == 'x':
            continue
        start[k] = j
        anchor[k] = j
        if units[k] == 'U':
            anchor[k + 1] = j + 2                                 # the unit's middle vertex sits over its fan
        j += {'S': 1, 'T': 3, 'U': 4}[units[k]]
    assert j == NE, f'the strip makes {j} end edges for an end ring of {NE}'
    mid_pos = field.nearest(0.5 * (B_pos(B, narrow) + end_pos[anchor % NE]))
    mid = B.add(mid_pos, 'palm')
    B.rings[f'strip_mid_{kind}_L'] = mid
    webs = set()
    for i in range(nd - 1):
        webs |= {top(i, 3), top(i + 1, 0), bot(i + 1, 0), bot(i, 3)}           # the web quads' corners
    E_ = lambda q: end[q % NE]                                                # noqa: E731
    tiles = []
    for k in range(16):
        k1 = (k + 1) % 16
        B.quad(narrow[k], narrow[k1], mid[k1], mid[k])
        if units[k] == 'x':
            continue
        j0 = start[k]
        if units[k] == 'S':
            B.quad(mid[k], mid[k1], E_(j0 + 1), E_(j0))
        elif units[k] == 'T':
            # every tile the same way (A: the diagonal from the middle vertex under b to d; e has no up edge). An A
            # tile beside a B tile shares a middle vertex holding BOTH diagonals: a valence-6 pole beside a cleft (the
            # first build chose B where d was a web corner and made one per side); all-A leaves only 3 / 5 pairs
            B.quad(mid[k], mid[k1], E_(j0 + 1), E_(j0))
            B.quad(mid[k1], E_(j0 + 3), E_(j0 + 2), E_(j0 + 1))
            tiles.append((k, 'T', int((j0 + 2) % NE)))
        else:                                                    # 'U': chords k, k + 1 over 4 end edges, one fan
            k2 = (k + 2) % 16
            B.quad(mid[k], mid[k1], E_(j0 + 1), E_(j0))
            B.quad(mid[k1], mid[k2], E_(j0 + 4), E_(j0 + 3))
            B.quad(mid[k1], E_(j0 + 3), E_(j0 + 2), E_(j0 + 1))
            tiles.append((k, 'U', int((j0 + 2) % NE)))
    notes.append(f'the strip 16 -> {NE}: ' + ', '.join(
        f'chord {k}-{(k + 1) % 16} {o} (no up edge at end {j}{" = a web corner" if j in webs else ""})' for k, o, j in tiles))
    # the web quads: (D[i].T3, D[i+1].T0, D[i+1].B0, D[i].B3)
    for i in range(nd - 1):
        B.quad(end[top(i, 3)], end[top(i + 1, 0)], end[bot(i + 1, 0)], end[bot(i, 3)])
    # the middle ring smoothed on the clay (each vertex toward its neighbours' mean, re-projected): its first places
    # (midpoints) left the tiles by the splayed outer digits at 20-25 deg
    Vall = np.concatenate(B.V)
    nb = {int(i): set() for i in mid}
    for q in B.Q:
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            if a in nb:
                nb[a].add(b)
            if b in nb:
                nb[b].add(a)
    for _ in range(C['strip_relax']):
        U = np.array([Vall[sorted(nb[int(i)])].mean(0) for i in mid])
        Vall[mid] = field.nearest(Vall[mid] + 0.5 * (U - Vall[mid]))
    B.V, B.R, B.fixed = [Vall], [np.concatenate(B.R)], [np.concatenate(B.fixed)]

    # ---- 6 the digits: K 8 rings along each finger; three loops within one radius of the IP; a 2 x 2 tip cap
    caps = []
    for d in digs:
        n, tr = d['n'], d['tr']
        a_ip = float(tr.L[int(np.argmin(np.linalg.norm(tr.P - joints[f'{KD["joint"]}{n}_1_L'], axis=1)))])
        r_ip = float(np.interp(a_ip, tr.L, d['r0']))
        a_end = float(tr.L[-1])
        knots = [d['a_b']]
        for seg_a, seg_b in ((d['a_b'], a_ip - r_ip), (a_ip - r_ip, a_ip + r_ip), (a_ip + r_ip, a_end)):
            if seg_b <= knots[-1] + 0.1:
                continue
            nseg = max(1, int(math.ceil((seg_b - knots[-1]) / C['digit_step'] - 1e-9)))
            if seg_a == a_ip - r_ip:
                nseg = max(nseg, 2)                      # the IP's three loops: a_ip - r, a_ip, a_ip + r
            knots += list(np.linspace(knots[-1], seg_b, nseg + 1)[1:])
        prev = d['ring0']
        d['stations'] = list(knots)
        for a in knots[1:]:
            O, F = d['frame_at'](a)
            P, ok = cast_ring(field, O, F, DIGIT_ANGLES, 2.0)
            if not ok.all():
                notes.append(f'digit {n} ring at {a:.2f}: {int((~ok).sum())} rays missed')
            ids = B.add(P, 'digit')
            B.strip(prev, ids)
            prev = ids
        # the fingertip: one ring on the sweep's round end (0.55 of its radius past the last node, so 0.84 of the radius
        # across) before the 2 x 2 cap: a cap straight off the last ring domed to a cone
        O, Z = tr.at(a_end)
        r_end = float(d['r0'][-1])
        _, F = d['frame_at'](a_end)
        P, ok = cast_ring(field, O + 0.55 * r_end * Z, F, DIGIT_ANGLES, 2.0)
        if not ok.all():
            notes.append(f'digit {n} tip ring: {int((~ok).sum())} rays missed')
        ids = B.add(P, 'digit')
        B.strip(prev, ids)
        caps.append((ids, Z, r_end))
        d['a_ip'], d['r_ip'] = a_ip, r_ip
    mesh, fixed = B.mesh()
    # ---- the WEDGE on the bend's compression side (plan 5.5, the lead's call 10-29): a closed loop round the inner arc
    # of the crease ring (pinned on the elbow's / knee's crease), the inset of the two bands either side of it over
    # the inner half (C['wedge_cols'] columns centred on the crease), so the inner side has two more loops where it
    # folds and the wedge's four 5-poles and four 3-poles sit on the bend's sides (its neutral plane), not in the crease
    wg = None
    if C['wedge_cols']:
        j_h = i_h - i_span1 + 1                                   # the crease ring's place in stations
        a_h = np.where(np.isfinite(crease['cols']), crease['cols'], stations[j_h])     # its arc per column
        a_nb = (stations[j_h - 1], stations[j_h + 1])

        def place(uv, a0):
            """the wedge's vertices CAST as the rings are, on the span's ring family: halfway in arc between the crease
            ring's column and its neighbour ring (u = -0.5, +0.5), or on the crease ring (u = 0), at the column angle
            and arc interpolated to the fractional column a0 + v (a bilinear point in the crease lies in the air of
            the concave fold, and the nearest surface from there can be the fold's other side)"""
            out_ = []
            for u, v in uv:
                c0 = min(int(math.floor(v)), C['wedge_cols'] - 1)
                k0, k1 = (a0 + c0) % 16, (a0 + c0 + 1) % 16
                ah = a_h[k0] + (v - c0) * (a_h[k1] - a_h[k0])
                a = ah if u == 0 else 0.5 * (ah + a_nb[0 if u < 0 else 1])
                O, F, th = geom1(float(a))
                thw = np.concatenate([th, th[:1] + TAU])           # the 16 angles and the first a turn on
                P, _ = cast_ring(field, O, F, np.array([thw[k0] + (v - c0) * (thw[k0 + 1] - thw[k0])]), 6.0)
                out_.append(P[0])
            return np.array(out_)

        mesh, fixed, wg = wedge(mesh, fixed, (canon[i_h - 1], canon[i_h], canon[i_h + 1]), d_in, place,
                                C['wedge_cols'])
        wg.update(arc=stations[j_h], crease=crease, ring=ring_ids[i_h])
        notes.append(f'the wedge: round the inner arc of the crease ring at arc {wg["arc"]:.2f} (the {KD["bend"]} joint '
                     f'at {0.5 * (z_b[0] + z_b[1]):.2f}; {int(np.isfinite(crease["cols"]).sum())} crease columns on the '
                     f'crease line, arcs {np.nanmin(crease["cols"]):.2f}-{np.nanmax(crease["cols"]):.2f}), columns '
                     f'{wg["cols"][0]}..{wg["cols"][-1]} (canonical) centred on the crease; the inner edges beside the '
                     f'crease ring {wg["inner_mm"][0]:.3f}-{wg["inner_mm"][1]:.3f} mm against its chord '
                     f'{wg["chord_mm"]:.3f}')
    # the length seam's vertices: the canonical column through the proximal record's seam vertex, from the footprint
    # to the distal record (through the wedge's partial rings where the column crosses them)
    nbr = {}
    for q in mesh.Q:
        for a_, b_ in zip(q, np.roll(q, -1)):
            nbr.setdefault(int(a_), set()).add(int(b_))
            nbr.setdefault(int(b_), set()).add(int(a_))
    seam_ids = [int(canon[0][seam[0]])]
    for i in range(1, i_hand + 1):
        v = int(canon[i][seam[0]])
        if v not in nbr[seam_ids[-1]]:              # the wedge's partial ring crosses the column between the two rings
            mid_v = nbr[seam_ids[-1]] & nbr[v]
            assert len(mid_v) == 1, 'the seam column is broken'
            seam_ids.append(mid_v.pop())
        seam_ids.append(v)
    for ring, Z, r_end in caps:
        n_before = len(mesh.V)
        mesh, G = LF.cap(mesh, ring, Z, dome=0.45 * r_end)
        mesh.attrs['part'][n_before:] = np.eye(len(REGIONS))[REGIONS.index('cap')]
    fixed = np.concatenate([fixed, np.zeros(len(mesh.V) - len(fixed), bool)])    # the caps' centres: the fit projects
    return dict(mesh=mesh, fixed=fixed, rings=B.rings, stations=stations, digits=digs, Lf=Lf, notes=notes,
                tiles=tiles, end=end, mid=mid, narrow=narrow, wedge=wg, seam=seam, seam_offsets=m_seam,
                seam_ids=np.array(seam_ids), seam_rings=i_hand + 1)


def crease_columns(geom, field, d_in, T0, T1, zone, scan=0.1, jump_deg=60.0, K=16):
    """a bend's inner CREASE on a span's ring family (geom(a) -> origin, frame, angles): per column of the inner half
    (the column nearest d_in at the zone's middle +- K / 4), the arc where the cast vertex's clay normal flips from the
    proximal wall's (along T1, the distal segment's direction) to the distal wall's (against T0): the largest jump
    of its angle on a scan of the zone +- 1 mm, if over jump_deg (a sharp V: the elbow's inner columns jump 62-81 deg
    between scan samples 0.1 mm apart, the knee's 125-133; the soft folds beside them 10-55, their largest jump often
    far from the crease), then bisection. Returns (the median arc, per-column arcs (NaN: no crease), the inner column)"""
    def ang_at(a, k):
        O, F, th = geom(a)
        P, _ = cast_ring(field, O, F, np.array([th[k]]), 6.0)
        n = field.normals(P)[0]
        return math.atan2(float(n @ T0), float(n @ -T1))

    aj = 0.5 * (zone[0] + zone[1])
    O, F, th = geom(aj)
    P, _ = cast_ring(field, O, F, th, 6.0)
    k_in = int(np.argmax(unit(P - O) @ d_in))
    xs = np.arange(zone[0] - 1.0, zone[1] + 1.0 + 1e-9, scan)
    arcs = np.full(K, np.nan)
    for dk in range(-K // 4, K // 4 + 1):
        k = (k_in + dk) % K
        g = np.unwrap([ang_at(a, k) for a in xs])
        d = np.abs(np.diff(g))
        j = int(np.argmax(d))
        if math.degrees(d[j]) < jump_deg:
            continue
        lo, hi, g_lo, g_hi = xs[j], xs[j + 1], g[j], g[j + 1]
        for _ in range(24):
            mid = 0.5 * (lo + hi)
            gm = g_lo + ((ang_at(mid, k) - g_lo + math.pi) % TAU - math.pi)
            if abs(gm - g_lo) <= abs(gm - g_hi):
                lo = mid
            else:
                hi = mid
        arcs[k] = lo
    assert np.isfinite(arcs).any(), 'no crease found in the bend zone'
    return float(np.nanmedian(arcs)), arcs, k_in


def wedge(mesh, fixed, rings3, d_in, place, ncols):
    """a WEDGE loop: the closed loop round the hinge ring's arc of `ncols` quads centred on the direction d_in (the
    bend's inner side), as the inset of the 2 x ncols quads between the hinge ring's neighbours (rings3 = proximal,
    hinge, distal, each in one column order). Quad strips cannot end inside a quad mesh, so a partial loop closes on
    itself: its long sides are two partial rings (one in each band beside the hinge ring), its ends cross the hinge
    ring between its columns. The region's corners become 5-poles and the inset's corners 3-poles, all on the bend's
    sides. The inset sits halfway in each band, the ends half a column in: place([(u, v), ..], a) gives the points at
    the grid places (u -0.5 / 0 / +0.5 across the bands, v columns from column a). Returns (mesh, fixed, info)"""
    from .. import ports as PT
    prev, hinge, nxt = (np.asarray(r) for r in rings3)
    K = len(hinge)
    V = mesh.V
    c = V[hinge].mean(0)
    k_in = int(np.argmax(unit(V[hinge] - c) @ d_in))
    a = (k_in - ncols // 2) % K
    cols = [(a + j) % K for j in range(ncols + 1)]
    key = {frozenset(int(v) for v in q): f for f, q in enumerate(mesh.Q)}
    faces = []
    for j in range(ncols):
        c0, c1 = cols[j], cols[j + 1]
        for r0, r1 in ((prev, hinge), (hinge, nxt)):
            faces.append(key[frozenset((int(r0[c0]), int(r0[c1]), int(r1[c1]), int(r1[c0])))])
    inner_e = [float(np.linalg.norm(V[hinge[k]] - V[r[k]])) for k in cols for r in (prev, nxt)]
    chord = float(np.linalg.norm(V[np.roll(hinge, -1)] - V[hinge], axis=1).mean())
    cut, loop = PT.cut(mesh, faces)
    # each loop vertex's grid place (u: -1 proximal, 0 hinge, +1 distal; v: 0 .. ncols across), its inset's place
    where = {}
    for j, k in enumerate(cols):
        where[int(prev[k])] = (-1.0, float(j))
        where[int(nxt[k])] = (1.0, float(j))
    where[int(hinge[cols[0]])] = (0.0, 0.0)
    where[int(hinge[cols[-1]])] = (0.0, float(ncols))
    Y = place([(0.5 * where[int(v)][0], float(np.clip(where[int(v)][1], 0.5, ncols - 0.5))) for v in loop], a)
    out, ids = PT.extend(cut, loop, [Y])
    sub = {int(x): int(y) for x, y in zip(loop, ids[1])}
    inner = np.array([[sub.get(int(v), int(v)) for v in mesh.Q[f]] for f in faces], np.int64)
    out = QuadMesh(out.V, np.vstack([out.Q, inner]), out.attrs)
    fixed = np.concatenate([np.asarray(fixed, bool), np.zeros(len(out.V) - len(fixed), bool)])
    corners = [int(prev[cols[0]]), int(prev[cols[-1]]), int(nxt[cols[0]]), int(nxt[cols[-1]])]
    return out, fixed, dict(cols=cols, faces=len(faces), loop=[int(v) for v in ids[1]], poles5=corners,
                            poles3=[sub[v] for v in corners], inner_mm=(min(inner_e), max(inner_e)), chord_mm=chord,
                            k_in=k_in)


def ramus(rec, P, r0, i0, field, step_D=0.5):
    """a LEFT gill ramus's cage beyond its graft ring (life mm): AX3's ring (rec, K 12, bit for bit), then K 12 rings
    about step_D x D apart along the stalk (plan §5.5: 'rings about 0.5 D apart'; the record's angles, its frame carried
    by minimal rotations), a ring on the sweep's round end and a 3 x 3 quad-grid tip cap. The root (the socket in the
    shared gill-base region and its two fillet rings) is the body build's. P (n, 3), r0 (n,): the ramus's sweep in life
    mm (from its buried root), i0 the stalk's base node (AX3's stalk share counts from it). Returns dict(mesh, fixed,
    ring (the record's ids), stations, notes)"""
    B = Builder()
    tr = Track(P)
    F = frame_of(rec)
    th = unwrap_deg(rec['angles_deg'])
    a0 = float(tr.L[i0] + rec['stalk_share'] * (tr.L[-1] - tr.L[i0]))         # AX3's ring arc (ax03 gill_ring)
    D = float(rec['D_mm'])
    o_err = float(np.linalg.norm(tr.at(a0)[0] - np.array(rec['frame']['creature']['origin_mm'])))
    assert o_err < 1e-6, f'the ring\'s origin is {o_err:.2e} mm off the stalk at its share'
    a_end = float(tr.L[-1])
    # the step follows the taper: step_D x D at the graft ring, shrinking with the radius (the ramus ends at 0.13 D:
    # a constant 0.5 D left its tip's quads at aspect 7.5 against K 12 chords of 0.23 mm), floored at a quarter
    xs = np.linspace(a0, a_end, 401)
    r_ring = float(np.interp(a0, tr.L, r0))
    step = step_D * D * np.maximum(np.interp(xs, tr.L, r0) / r_ring, 0.25)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (1.0 / step[1:] + 1.0 / step[:-1]) * np.diff(xs))])
    n = max(2, int(round(cum[-1])))
    arcs = np.interp(np.arange(n + 1) * cum[-1] / n, cum, xs)
    ring = B.add(np.array(rec['verts_mm']), 'ramus', fixed=True)
    prev, Z, notes, stations = ring, F[:, 2].copy(), [], [a0]
    for i in range(1, n + 1):
        a = float(arcs[i])
        O, T = tr.at(a)
        axv = np.cross(Z, T)
        if np.linalg.norm(axv) > 1e-12:
            F = rotation(axv, math.asin(min(1.0, float(np.linalg.norm(axv))))) @ F
        Z = F[:, 2]
        Pr, ok = cast_ring(field, O, F, th, 3.0 * D)
        if not ok.all():
            notes.append(f'ramus ring at {a:.2f}: {int((~ok).sum())} rays missed')
        ids = B.add(Pr, 'ramus')
        B.strip(prev, ids)
        prev = ids
        stations.append(a)
    r_end = float(r0[-1])
    O, T = tr.at(a_end)
    Pr, ok = cast_ring(field, O + 0.55 * r_end * T, F, th, 3.0 * D)       # on the round end, as the fingertips'
    if not ok.all():
        notes.append(f'ramus tip ring: {int((~ok).sum())} rays missed')
    ids = B.add(Pr, 'ramus')
    B.strip(prev, ids)
    mesh, fixed = B.mesh()
    n_before = len(mesh.V)
    mesh, _ = LF.cap(mesh, ids, T, dome=0.45 * r_end)
    mesh.attrs['part'][n_before:] = np.eye(len(REGIONS))[REGIONS.index('cap')]
    fixed = np.concatenate([fixed, np.zeros(len(mesh.V) - len(fixed), bool)])
    notes.append(f'{n} rings {np.diff(arcs).max():.2f}-{np.diff(arcs).min():.2f} mm apart (D {D:.2f}; the step follows '
                 f'the taper) from the graft ring at arc {a0:.2f} to the sweep\'s end at {a_end:.2f}, a tip ring and a '
                 f'3 x 3 cap')
    return dict(mesh=mesh, fixed=fixed, ring=ring, stations=stations, notes=notes)


def B_pos(B, ids):
    V = np.concatenate(B.V)
    return V[np.asarray(ids)]


def fit_cage(mesh, prg, fixed, km, iters=CAGE['relax_iters'], relax=0.5, nudge_mm=1.0e-3, maxd_mm=2.0):
    """retopo.fit on a cage whose proxies were CAST onto the clay (mesh in x4 metres). Each free vertex is first
    nudged nudge_mm out along the field's normal. Why: a point exactly on the zero set evaluates to 0.0 in float32, and
    sdf.k_project then marches INWARD (sgn stays -1 unless f0 < 0) but tests its crossing as if it started INSIDE
    ((fn > 0) != (f0 > 0) with f0 > 0 false), so it crosses only at the FAR side of the part: a palm vertex on the top
    of the 1.7 mm slab landed on its bottom (AX4's first fit moved 89 of 1,044 vertices up to 1.73 mm and crumpled
    every finger). retopo.fit's first projection keeps that result unguarded; its relaxation rounds reject it (the
    short-move test). Nudged off the zero set, f0 > 0 and the first sample past it crosses at once. Returns (status
    counts, the accepted share per round, the first projection's largest move in mm)"""
    from .. import retopo as RT
    V0 = mesh.V.copy()
    free = ~np.asarray(fixed, bool)
    n = prg.normals(mesh.V[free])
    mesh.V[free] = mesh.V[free] + nudge_mm * km * n
    st, acc = RT.fit(mesh, prg, iters=0, relax=relax, fixed=fixed, maxd=maxd_mm * km)
    first = float(np.linalg.norm(mesh.V - V0, axis=1).max()) / km
    if iters:
        mesh.V[free] = mesh.V[free] + nudge_mm * km * prg.normals(mesh.V[free])
        st, acc = RT.fit(mesh, prg, iters=iters, relax=relax, fixed=fixed, maxd=maxd_mm * km)
    return st, acc, first
