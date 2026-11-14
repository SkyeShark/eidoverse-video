"""B4 LEGS (the Bestiary lead's B4-legs call, 10-27): the stag beetle's LEG SEGMENTS as CREASED SUBDIVISION CAGES, the way B3g / B3h
built the head (heads/insect_cage.py) and the mandible (heads/insect_mcage.py): every segment ONE closed quad cage whose limit
surface (forge/subdiv_sharp.py: semi-sharp Catmull-Clark, DeRose, Kass & Truong 1998; fit_controls) passes through targets on the
segment's own clay program (arthropod_parts.leg_parts: the accepted B3h clay, read, never edited), semi-sharp creases only where the
photos show an edge, at the photos' radii (BEETLE_BODY_PHOTOS 7b's ring-light rule, the legs read in scratch_b4_legs p03), the
surfaces between curved by construction.

THE SEGMENTS (per leg; the LEFT leg is built, the right is its exact mirror p_R = M p_L, the quads' winding reversed):
  coxa        fore: the procoxa's egg (COXA_FORE); mid / hind: the plates (COXA_PLATE): K 12 x 5 rings + 2 caps (plan §4.6)
  trochanter  the egg (TROCH_R): K 12 x 5 + 2 caps
  femur       the club-shaped shaft and the knee's CLUB (FEMUR_PROF, KNEE): K 16 x 22 + 2 caps
  tibia       CONSTRUCTED sections (TIBIA_SEC) on the clay's own centreline, frames and measured widths / depths (TIBIA_PROF,
              TIBIA_BOW, read off the clay's sweep): the outer MARGIN a keel creased at the photos' radius (the edge that carries
              the teeth and the spine), the mid / hind tibiae's DORSAL carina creased; the fore tibia's teeth and its inner apical
              spur, the mid / hind tibiae's spine and their two apical spurs EXTRUDED from the margin's / the apex's faces along
              the clay's own feature paths (FORE_TEETH, FORE_SPUR, MH_SPINE, MH_SPUR): one shell, no stuck-on pieces
  tarsus_n    the lobed beads (TARSO_W, TARSO_TAPER, TARSO_LOBE): K 8 x 5 (t5 K 8 x 7) + 2 caps
  claw_a / b  ONE curved hook (CLAW) built in the claw joint's frame and placed twice by a rigid turn about the vertical through
              the joint: exact copies (the clay's two arcs are congruent: the same chord, turn and section, splayed +-CLAW splay),
              so their UV shells stack (and the right leg's four mirror them through the tangent sign)
THE TARGETS: rays from each segment's spine (its own axis, the clay's) onto its UNCARVED clay field (the shells overlap at their
joints, never welded: plan §4.2), rings at equal arc length pole to pole, each cap a K/2 - 2 by 2 patch on a great arc through
its pole (insect_mcage's cap). The tibia's rings are built, not cast (the clay's squarish superellipse has no edge to crease).
THE SLEEVES (plan §4.2.3: K 12 x 3 rings, open; CROSSBREED §2.9's ARTICULATION): one at EVERY leg joint (the coxal cavity, coxa-
trochanter, trochanter-femur, the knee, the ankle, the four tarsal joints, the claws' joint), planar rings normal to the child's
axis where it leaves its parent, inside the child (SLEEVE in_child): hidden at rest, the membrane a flexed joint opens onto.
THE GRAFT RINGS (CROSSBREED §7.3 as corrected by its review R10 and the lead's decision 9): the COXA, KNEE and ANKLE sleeves'
PROXIMAL rings, 100 % on the parent, K from the ring's own radius by §2.2's chord sag (<= 2 texels at 9,257 px/m, x10), vertex 0
on slots.port_frame's tangent, right-handed on the left (the right ring is the left one mirrored, vertex for vertex); each ring's
record (§2.11, graft_records) at the author scale in metres: its frame and origin in the parent joint's bind frame (joint_frame),
the vertices and frozen normals in the creature frame, `build` the legs' cache key, the native group every segment, sleeve
(the graft sleeve itself included: R10) and claw past the cut.
THE LOW: the cage itself at its limit positions (every low vertex ON the high: A V0 = T), within the plan's leg budget (§4.6).
UNITS: life mm in the plan frame (x the creature's left, y up from the ground, z forward), the world positions of the rest chain;
to_author() multiplies by spec['author_scale'] * 1e-3 (x10: metres), or by any author_scale: the M2 graft scales a leg to its
socket by author_scale_for_root (the tibia's root, tibia_root, to 34 mm), and graft_records re-writes the rings at that scale.
b4l-2 (the restarted build:legs agent, 10-27): the tibiae's ends rounded toward the plain section and capped by a Coons patch;
the mid / hind spurs extruded where their paths leave the shaft (path_exit); the ring records' joint frames, right-side records,
native groups (the graft sleeve, the claws' sleeve) and build key; the tibia's root for M2.
"""
import hashlib
import json
import os
import time

import numpy as np

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

VERSION = 'b4l-2'
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
CACHE = os.path.join(REPO, 'work', 'bestiary', 'beetle', 'scratch_b4_legs', 'cache')
UP = np.array([0.0, 1.0, 0.0])
M_MIRROR = np.diag([-1.0, 1.0, 1.0])
PX_PER_M = 9257.0                    # BEETLE_PLAN §4.7: the one density at x10 (0.108 mm per texel; 10.8 um at life)
TEXEL_LIFE = 1.0 / PX_PER_M * 1e3 / 10.0      # mm at life per texel (the author scale x10)

# ============================================================================================ the layout and the tables
LAYOUT = dict(coxa=dict(K=12, n=5), trochanter=dict(K=12, n=5), femur=dict(K=16, n=22), tarsus=dict(K=8, n=5),
              tarsus_5=dict(K=8, n=7), claw=dict(K=8, n=6, taper_w=0.55),
              # the tibia: each margin feature's base ends (min_gap mm apart at least), the shaft between them at most `spacing`
              # mm between rings; the ends' quarter-round rings at end_phi (deg), each ring's keeled section rounded toward the
              # plain superellipse by end_round (0 keeled .. 1 round: the creases stop at the last station, so an uncreased keel
              # target there made the limit ripple round the end, b4l-2 p10); the cap's interior a Coons patch of its ring
              tibia=dict(K=16, spacing=dict(fore=0.80, mid=0.62, hind=0.66), min_gap=0.14, end_phi=(40.0, 75.0),
                         end_round=(0.55, 1.0),
                         # the NECK: the section plain (round) to u 0.08 and keeled from u 0.18 (smoothstep), the creases only
                         # where it is keeled: the tibia leaves the femur's club at u 0.087 (the knee sleeve's X: 1.09 / 0.90 /
                         # 1.04 mm along the axis), and a keel and carina crossing the club's round end cut a wavy junction (p09
                         # v2 flex, the mid knee); the clay's tibia is a plain superellipse there (M1d: the base narrow and round)
                         neck_round=(0.08, 0.18)),
              sleeve=dict(K=12, n=3))
# THE TIBIA'S SECTION (TIBIA_SEC [E], gate: the views beside the photos, p05): in the section's frame (e the feature side: the fore
# tibia's lateral edge, the mid / hind tibiae's anterior edge where the clay puts the teeth and the spine; n the clay's normal,
# vertical-ish), its extremes the clay's measured width W (along e) and depth T (along n), 16 points: k 0 the MARGIN (+e), 4 the
# dorsal extreme, 8 the inner, 12 the ventral. The margin a KEEL: its neighbours k +-1 at h1 x the half-depth, set in so the faces
# meet there at margin_angle (interior); the mid / hind dorsal a ridge (dorsal_angle); the rest on a superellipse of exponent p.
# The photos: M1d's mid / hind tibiae carry a thin highlight line just inside the anterior silhouette, M1l's a crisp top edge with a
# thin line under it (both single lines 29-47 um: r <= 0.05-0.08, p03); the fore tibia's dorsal crest prints TWO lines 0.17 mm apart
# (a ROUNDED crest, r ~0.28: no crease), its teeth on the outer margin; M1l's side views show the teeth and spines on that margin.
TIBIA_SEC = dict(fore=dict(p=2.2, h1=0.36, margin_angle=118.0, dorsal_angle=None),
                 mid=dict(p=2.5, h1=0.36, margin_angle=118.0, dorsal_angle=128.0),
                 hind=dict(p=2.5, h1=0.36, margin_angle=118.0, dorsal_angle=128.0))
# THE CREASES: (class: target limit radius mm at life, DKT sharpness s) [M-ph p03: the margins' and the carinae's single highlight
# lines 29-47 um on M1d (37 um blur) / M1l (51 um): r <= w / 0.604 = 0.048-0.078, ~w / 0.747 = 0.039-0.063 counting the lines' own
# thickness; the head's measured edges sit in the same band (the lateral margins 0.063-0.076, the supraocular ridge 0.052)]. s is
# set so the LIMIT surface's apex radius (k01's rule: a circle over +-0.06 mm of arc at the sharpest turn) meets r (p04 tunes it)
CREASE = dict(margin=dict(r=0.05, s=2.4), dorsal=dict(r=0.05, s=2.4))
CREASE_FADE = (0.35, 0.75)          # each crease chain's first / second edge from either end at this share of its sharpness
# THE SLEEVES: in_child the share of the child's own section radius the rings take (inside it: hidden at rest); step the rings'
# spacing along the child's axis, a share of the child's radius at the exit, clamped (mm)
SLEEVE = dict(in_child=0.84, step=0.36, step_min=0.05, step_max=0.15, K_min=12, sag_texels=2.0)
LEVELS = dict(fit=5, out=4)
# the claws' BASE BALL [E]: centred on the claw joint (t5's end-sphere centre), r under t5's end radius (0.22-0.23: TARSO_W) and
# about the hook's base half-section (CLAW w / d 0.32 / 0.38): hidden in t5, it sinks both claws into it (b03's 2-4 mm at x10)
CLAW_BASE = dict(r=0.19, k=0.05)
FEATURE_RINGS = dict(small=(0.85,), big=(0.45, 0.88), spur=(0.12, 0.42, 0.72, 0.95))   # (shares of the way to the tip)

LEG_NAMES = ('coxa', 'trochanter', 'femur', 'tibia', 'tarsus_1', 'tarsus_2', 'tarsus_3', 'tarsus_4', 'tarsus_5', 'claw_a', 'claw_b')
GRAFT_CUTS = dict(coxa=('body', 'coxa'), knee=('femur', 'tibia'), ankle=('tibia', 'tarsus_1'))
PLAN_BUDGET = dict(coxa_trochanter=1584, femur=4800, tibia=6000, tarsus=2784, claw=1056, sleeves_all_body=1440)


# ============================================================================================ small helpers
def _unit(v):
    v = np.asarray(v, np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-300)


def _perp(t, ref=UP):
    """ref made perpendicular to t (unit); x if ref is along t"""
    t = _unit(t)
    v = np.asarray(ref, np.float64) - t * float(t @ ref)
    if np.linalg.norm(v) < 1e-6:
        v = np.array([1.0, 0.0, 0.0]) - t * t[0]
    return _unit(v)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def cache_key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=lambda o: np.asarray(o).tolist()).encode()).hexdigest()[:16]


def desc_digest(d):
    """a descriptor's numbers (its kind, positions, radii, sections, members), for the cache key"""
    out = {'kind': d['kind'], 'name': d.get('name', '')}
    for k in ('a', 'b', 'ra', 'rb', 'c', 'half', 'r', 'axes', 'points', 'sections', 'rho', 'scale', 'normal', 'k'):
        if k in d and d[k] is not None and not callable(d[k]):
            out[k] = np.round(np.asarray(d[k], np.float64), 9).tolist()
    if d['kind'] == 'group':
        out['members'] = [desc_digest(m) for m in d['members']]
    return out


class Spine:
    """a segment's axis: points (m, 3) with tangents and frames (N the given normals made perpendicular, else UP made perpendicular;
    B = T x N); at(u) at the arc fraction u"""

    def __init__(self, P, N=None):
        P = np.asarray(P, np.float64)
        if len(P) == 2:
            P = P[0][None, :] + np.linspace(0.0, 1.0, 9)[:, None] * (P[1] - P[0])[None, :]
            N = None if N is None else np.repeat(np.asarray(N, np.float64).reshape(-1, 3)[:1], 9, axis=0)
        self.P = P
        T = np.gradient(P, axis=0)
        self.T = _unit(T)
        if N is None:
            Nn = np.array([_perp(t) for t in self.T])
        else:
            Nn = np.asarray(N, np.float64).reshape(-1, 3)
            if len(Nn) == 1:
                Nn = np.repeat(Nn, len(P), axis=0)
            Nn = _unit(Nn - self.T * np.sum(Nn * self.T, axis=1, keepdims=True))
        self.N = Nn
        self.B = _unit(np.cross(self.T, self.N))
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])
        self.L = float(self.s[-1])

    def at(self, u):
        x = np.clip(u, 0.0, 1.0) * self.L
        i = int(np.clip(np.searchsorted(self.s, x) - 1, 0, len(self.s) - 2))
        w = (x - self.s[i]) / max(self.s[i + 1] - self.s[i], 1e-300)
        P = (1 - w) * self.P[i] + w * self.P[i + 1]
        T = _unit((1 - w) * self.T[i] + w * self.T[i + 1])
        N = _unit((1 - w) * self.N[i] + w * self.N[i + 1])
        N = _unit(N - T * float(N @ T))
        return P, T, N, _unit(np.cross(T, N))


# ============================================================================================ the clay's programs
def clay_programs(spec, chain):
    """the clay's leg descriptors per pair (arthropod_parts.leg_parts as it stands: the mid / hind coxa plates read the venter's
    field), the body's fields the coxal sleeves read (the venter's, the pronotum's without the head's collar carve: it lies far from
    the procoxae), and evaluators per segment (life mm). Returns dict(pair: dict(seg: (descs, parent)), fields, digest)"""
    from . import arthropod_parts as AP
    from . import arthropod as AR
    from .. import sdf as S_
    s = chain['scale_m']
    clear = chain['clearance']
    ely_V, ely_F, ely = AP.elytron_patch(spec, clear)
    ven = AP.venter_descs(spec, clear, ely)
    f_ven = AP.field_mm(ven, s)
    pron = AP.pronotum_descs(spec, clear)
    f_pron = AP.field_mm(pron, s)
    legs, dig, carved, body_socket = {}, {}, {}, {}
    ev = lambda p: (lambda P: p.eval(np.asarray(P, np.float64).reshape(-1, 3) * s).astype(np.float64) / s)    # noqa: E731
    for c, pair, cox, i in AR.LEGS:
        out = AP.leg_parts(spec, chain, c, pair, dict(venter=f_ven))
        legs[pair] = {k.rsplit('_', 1)[0] if k.endswith(f'_{c}') else k: v for k, v in out.items()}
        dig[pair] = {k: [desc_digest(d) for d in v[0]] for k, v in legs[pair].items()}
        # the clay's CLEARANCE carves (build_parts: every trochanter carved by its body part less its coxa's socket, every femur
        # by its body part, each coxa by its femur, all grown by CLEAR): the accepted clay's grooves, which the cages keep (left
        # out, the mid / hind trochanters and femora crossed the venter by 0.16-0.33 mm, p07). The joints' SINK carves are not
        # cast: the cages overlap at their joints, never welded
        L_ = legs[pair]
        tgt = pron if pair == 'fore' else ven
        cox_ = [AP.shrink_desc(d, AP.SINK - AP.CLEAR) for d in L_['coxa'][0]]
        body_ = AP.group([dict(d) for d in tgt] + [dict(d, op=S_.SUBTRACT, k=0.0) for d in cox_], name='body less the coxa')
        carved[pair] = dict(
            trochanter=ev(AP.program_of(L_['trochanter'][0], s, [(body_, AP.CLEAR, S_.SUBTRACT)])),
            femur=ev(AP.program_of(L_['femur'][0], s, [(d, AP.CLEAR, S_.SUBTRACT) for d in tgt if AP.carvable(d, AP.CLEAR)])),
            coxa=ev(AP.program_of(L_['coxa'][0], s, [(d, AP.CLEAR, S_.SUBTRACT) for d in L_['femur'][0]
                                                     if AP.carvable(d, AP.CLEAR)])))
        # the body as b03 reads a coxa's depth in it: carved by both coxae shrunk by SINK (its socket)
        body_socket[pair] = ev(AP.program_of(tgt, s, [(d, -AP.SINK, S_.SUBTRACT) for ds in
                                                      (L_['coxa'][0], [AP.mirror_desc(d) for d in L_['coxa'][0]])
                                                      for d in ds if AP.carvable(d, -AP.SINK)]))
    return dict(legs=legs, body=dict(venter=f_ven, pronotum=f_pron), carved=carved, body_socket=body_socket, digest=dig,
                sink=AP.SINK, clear=AP.CLEAR)


def field_of(descs, s):
    from . import arthropod_parts as AP
    return AP.field_mm(descs, s)


# ============================================================================================ rays onto a field
def first_exit(field, O, D, t_max, step=0.004, iters=30):
    """the first inside -> outside crossing of field (life mm) along O + t D, t in 0..t_max, refined by bisection; ok where the
    origin is inside and a crossing exists"""
    O = np.atleast_2d(np.asarray(O, np.float64))
    D = np.atleast_2d(np.asarray(D, np.float64))
    n = len(O)
    ts = np.arange(0.0, t_max + 0.5 * step, step)
    f = field((O[:, None, :] + ts[None, :, None] * D[:, None, :]).reshape(-1, 3)).reshape(n, len(ts))
    out = f >= 0.0
    idx = np.argmax(out, axis=1)
    ok = out[np.arange(n), idx] & (idx > 0) & (f[:, 0] < 0.0)
    lo = ts[np.maximum(idx - 1, 0)].astype(np.float64)
    hi = ts[idx].astype(np.float64)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        inside = field(O + mid[:, None] * D) < 0.0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    return 0.5 * (lo + hi), ok


# ============================================================================================ the cage's assembly
class Cage:
    """one segment's cage: targets V (life mm, world), quads Q, creases {(a, b): s}, its rings (n, K) vertex ids, the cap ids, its
    spine and frame, its features"""

    def __init__(self, name, kind, K):
        self.name, self.kind, self.K = name, kind, K
        self.V = np.zeros((0, 3))
        self.Q = []
        self.sharp = {}
        self.rings = None
        self.features = []
        self.meta = {}

    def add(self, P):
        P = np.atleast_2d(np.asarray(P, np.float64))
        i0 = len(self.V)
        self.V = np.vstack([self.V, P])
        return list(range(i0, i0 + len(P)))

    def tube(self, ring_pts):
        """rings (n, K, 3): their vertices and the bands' quads"""
        n, K = ring_pts.shape[:2]
        ids = np.array(self.add(ring_pts.reshape(-1, 3)), int).reshape(n, K)
        self.rings = ids
        for j in range(n - 1):
            for k in range(K):
                self.Q.append((ids[j, k], ids[j, (k + 1) % K], ids[j + 1, (k + 1) % K], ids[j + 1, k]))
        return ids

    def cap(self, ring_ids, interior, flip):
        """insect_mcage's cap: an m x 2 patch (m = (K - 4) / 2) whose boundary is the ring's loop, its middle row the ring's
        point 2m + 3, the m - 1 interior points, the ring's point m + 1"""
        L = list(ring_ids)
        K = len(L)
        m = (K - 4) // 2
        ids = self.add(interior) if len(interior) else []
        assert len(ids) == m - 1, f'{self.name}: a K {K} cap takes {m - 1} interior points'
        Bv = [L[c] for c in range(m + 1)]
        Tv = [L[2 * m + 2 - c] for c in range(m + 1)]
        Mv = [L[2 * m + 3]] + ids + [L[m + 1]]
        qs = [(Bv[c], Bv[c + 1], Mv[c + 1], Mv[c]) for c in range(m)] + [(Mv[c], Mv[c + 1], Tv[c + 1], Tv[c])
                                                                       for c in range(m)]
        for q in qs:
            self.Q.append(q[::-1] if flip else q)
        return ids

    def crease(self, chain, s):
        ss = np.broadcast_to(np.asarray(s, np.float64), (len(chain) - 1,))
        for (a, b), v in zip(zip(chain[:-1], chain[1:]), ss):
            if v > 0:
                self.sharp[(min(a, b), max(a, b))] = float(v)

    def mesh(self):
        return QuadMesh(self.V, np.array(self.Q, int).reshape(-1, 4))

    def orient(self):
        """outward: the signed volume positive (every quad reversed otherwise)"""
        m = self.mesh()
        V, Q = m.V, m.Q
        vol = np.sum(np.einsum('ij,ij->i', V[Q[:, 0]], np.cross(V[Q[:, 1]] - V[Q[:, 0]], V[Q[:, 2]] - V[Q[:, 0]])) +
                     np.einsum('ij,ij->i', V[Q[:, 0]], np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 0]]))) / 6.0
        if vol < 0:
            self.Q = [tuple(q[::-1]) for q in self.Q]
        self.meta['volume'] = abs(float(vol))
        return self


def cap_arc_dirs(r_left, axial, phi_e, m):
    """the m - 1 interior directions of a cap's middle row: on the great circle from the ring's left end (its radial r_left at the
    ring's tilt phi_e) through the pole (axial) to the right end"""
    out = []
    for c in range(1, m):
        a = phi_e + (np.pi - 2.0 * phi_e) * c / m
        out.append(np.cos(a) * r_left + np.sin(a) * axial)
    return np.array(out).reshape(-1, 3)


def cast_tube(name, kind, field, spine, K, n_rings, t_max, theta0=0.0, phi_max=np.radians(88.0), n_dense=(14, None, 14),
              taper_w=0.0):
    """a closed tube cage on a field: n_rings rings at equal arc length pole to pole (the proximal cap's tilt, the spine, the distal
    cap's tilt), K rays each from the spine (k 0 along the spine's N, toward B with k), two caps (great arcs through the poles).
    taper_w > 0: the arc weighted by (r_max / r)^taper_w (r the ring's mean radius from the spine): rings closer where a hook
    narrows, so its quads keep their shape"""
    th = theta0 + 2.0 * np.pi * np.arange(K) / K
    n_c0, n_s, n_c1 = n_dense
    n_s = n_s or max(12, int(spine.L / 0.04))

    def params(tau):
        if tau < 1.0:
            P, T, N, B = spine.at(0.0)
            return P, N, B, -T, phi_max * (1.0 - tau)
        if tau <= 2.0:
            P, T, N, B = spine.at(tau - 1.0)
            return P, N, B, T, 0.0
        P, T, N, B = spine.at(1.0)
        return P, N, B, T, phi_max * (tau - 2.0)

    def dirs(N, B, A, phi):
        r = np.cos(th)[:, None] * N[None, :] + np.sin(th)[:, None] * B[None, :]
        return np.cos(phi) * r + np.sin(phi) * A[None, :], r

    def cast(tau_list):
        O, D = [], []
        for t in tau_list:
            P, N, B, A, phi = params(t)
            d, _ = dirs(N, B, A, phi)
            O.append(np.repeat(P[None, :], K, axis=0))
            D.append(d)
        O, D = np.vstack(O), np.vstack(D)
        t, ok = first_exit(field, O, D, t_max)
        assert ok.all(), f'{name}: {int((~ok).sum())} rays found no surface (an origin outside, or t_max {t_max} short)'
        return (O + t[:, None] * D).reshape(len(tau_list), K, 3)

    taus = np.concatenate([np.linspace(0.0, 1.0, n_c0, endpoint=False), 1.0 + np.linspace(0.0, 1.0, n_s),
                           2.0 + np.linspace(0.0, 1.0, n_c1 + 1)[1:]])
    Pd = cast(taus)
    P0, T0, N0, B0 = spine.at(0.0)
    P1, T1, N1, B1 = spine.at(1.0)
    tp, ok = first_exit(field, np.vstack([P0, P1]), np.vstack([-T0, T1]), t_max)
    assert ok.all(), f'{name}: a pole ray found no surface'
    pole0, pole1 = P0 - tp[0] * T0, P1 + tp[1] * T1
    arc = np.concatenate([[float(np.mean(np.linalg.norm(Pd[0] - pole0, axis=1)))],
                          np.mean(np.linalg.norm(np.diff(Pd, axis=0), axis=2), axis=1)])
    arc_end = float(np.mean(np.linalg.norm(Pd[-1] - pole1, axis=1)))
    if taper_w > 0:
        Od = np.array([params(t)[0] for t in taus])
        rr_ = np.mean(np.linalg.norm(Pd - Od[:, None, :], axis=2), axis=1)
        wgt = (rr_.max() / np.maximum(rr_, 0.08 * rr_.max())) ** taper_w
        wm = np.concatenate([[wgt[0]], 0.5 * (wgt[1:] + wgt[:-1])])
        arc = arc * wm
        arc_end *= wgt[-1]
    S = np.cumsum(arc)
    S_tot = float(S[-1] + arc_end)
    targets = S_tot * np.arange(1, n_rings + 1) / (n_rings + 1)
    tau_r = np.interp(targets, S, taus)
    R = cast(list(tau_r))
    cg = Cage(name, kind, K)
    ids = cg.tube(R)
    m = (K - 4) // 2
    # the caps: interior points cast from the end origins on the great arcs through the poles
    for end, (j, tau) in enumerate(((0, tau_r[0]), (n_rings - 1, tau_r[-1]))):
        P, N, B, A, phi = params(tau)
        _, rr = dirs(N, B, A, phi)
        Oc = spine.at(0.0)[0] if end == 0 else spine.at(1.0)[0]
        Ax = -spine.at(0.0)[1] if end == 0 else spine.at(1.0)[1]
        # (a cap on a side ring: its tilt 0, the arc from the radial through the axis)
        D = cap_arc_dirs(rr[2 * m + 3], Ax, phi if tau < 1.0 or tau > 2.0 else 0.0, m)
        if len(D):
            t, ok = first_exit(field, np.repeat(Oc[None, :], len(D), axis=0), D, t_max)
            assert ok.all(), f'{name}: a cap ray found no surface'
            pts = Oc[None, :] + t[:, None] * D
        else:
            pts = np.zeros((0, 3))
        cg.cap(ids[j], pts, flip=(end == 0))
    cg.meta.update(spine=spine, poles=(pole0, pole1), tau=tau_r, arc=S_tot, theta0=theta0)
    return cg.orient()


# ============================================================================================ the tibia
def tibia_section(W, T, sec):
    """the 16 section points (e, n) at width W (along e) and depth T (along n): TIBIA_SEC's keel margin (k 0), the dorsal ridge
    (k 4, mid / hind), the rest on the superellipse"""
    a, b = 0.5 * W, 0.5 * T
    p = sec['p']

    def se(ang):
        c, s_ = np.cos(ang), np.sin(ang)
        return np.array([a * np.sign(c) * abs(c) ** (2.0 / p), b * np.sign(s_) * abs(s_) ** (2.0 / p)])
    P = np.array([se(2.0 * np.pi * k / 16.0) for k in range(16)])
    # the margin keel: k 0 the extreme (a, 0); k +-1 at height h1 b, set in so the two faces meet at margin_angle
    h1 = sec['h1'] * b
    d1 = h1 / np.tan(np.radians(0.5 * sec['margin_angle']))
    P[0] = (a, 0.0)
    P[1] = (a - d1, h1)
    P[15] = (a - d1, -h1)
    # k 2 between k 1 and the dorsal side: on the superellipse but no farther out than the keel's faces allow (convex)
    if sec['dorsal_angle'] is not None:
        x3 = 0.30 * a
        drop = x3 / np.tan(np.radians(0.5 * sec['dorsal_angle']))
        P[4] = (0.0, b)
        P[3] = (x3, b - drop)
        P[5] = (-x3, b - drop)
    for k, (k0, k1) in ((2, (1, 3)), (14, (15, 13))):
        mid = 0.5 * (P[k0] + P[k1])
        out = P[k]
        # keep the point outside the chord k0-k1 (convex) and inside the superellipse
        nrm = np.array([P[k1][1] - P[k0][1], -(P[k1][0] - P[k0][0])])
        nrm /= np.linalg.norm(nrm)
        if (out - mid) @ nrm * np.sign((mid - np.zeros(2)) @ nrm) < 0.02 * b:
            P[k] = mid + 0.02 * b * nrm * np.sign((mid - np.zeros(2)) @ nrm)
    return P


def tibia_round(W, T, sec):
    """the plain superellipse (TIBIA_SEC's exponent) at the 16 section angles, no keel and no ridge: the shape the ends' rings
    round toward (LAYOUT tibia end_round)"""
    a, b = 0.5 * W, 0.5 * T
    p = sec['p']
    ang = 2.0 * np.pi * np.arange(16) / 16.0
    c, s_ = np.cos(ang), np.sin(ang)
    return np.column_stack([a * np.sign(c) * np.abs(c) ** (2.0 / p), b * np.sign(s_) * np.abs(s_) ** (2.0 / p)])


def coons_cap(ring, m):
    """insect_mcage's cap's m - 1 middle-row points as a discrete Coons patch of its boundary (rows Bv = ring[0..m], Tv =
    ring[2m+2 .. m+2], the short sides ring[2m+3] and ring[m+1]): each interior point the mean of its column's two boundary
    points plus the sides' linear blend less the corners' bilinear term, so the patch's quads follow the ring's own shape (b4l-1
    put them on the straight chord between the short sides, shrunk toward the centroid: on a keeled ring the quads came out
    uneven and the fitted limit crumpled over the end, p10)"""
    Bv = [ring[c] for c in range(m + 1)]
    Tv = [ring[2 * m + 2 - c] for c in range(m + 1)]
    M0, Mm = ring[2 * m + 3], ring[m + 1]
    out = []
    for c in range(1, m):
        u = c / m
        out.append(0.5 * (Bv[c] + Tv[c]) + (1.0 - u) * M0 + u * Mm
                   - 0.5 * ((1.0 - u) * (Bv[0] + Tv[0]) + u * (Bv[m] + Tv[m])))
    return np.array(out).reshape(-1, 3)


def tibia_cage(name, pair, descs, sink):
    """the tibia (module docstring): its shaft rings on the clay sweep's centreline / frames / widths, its features extruded"""
    sh = None
    feats = []
    for d in descs:
        if d['kind'] == 'group' and d['members'][0]['kind'] == 'psweep' and 'shaft' in d['members'][0]['name']:
            sh = d['members'][0]
        elif d['kind'] == 'psweep':
            feats.append(d)
    assert sh is not None, f'{name}: no shaft sweep in the clay tibia'
    Pt = np.asarray(sh['points'], np.float64)
    rho = float(sh['rho'])
    sc = np.asarray(sh['scale'], np.float64)
    thick, wide = 2.0 * (sc[:, 0] + rho), 2.0 * (sc[:, 1] + rho)
    sp = Spine(Pt, sh['normal'])
    L = sp.L
    u_pts = sp.s / L
    sec = TIBIA_SEC[pair]
    lay = LAYOUT['tibia']
    # the feature side e_f: the clay's own (the fore teeth on the lateral side, the mid / hind spine on the anterior side)
    P0, T0, N0, B0 = sp.at(0.5)
    if pair == 'fore':
        e_sign = 1.0 if B0[0] > 0 else -1.0
    else:
        e_sign = 1.0 if B0[2] >= 0 else -1.0
    # ---- the FEATURES from the clay's descriptors: teeth / spine (flat teeth on the margin), the spurs (at the apex)
    F = []
    for d in feats:
        nm = d['name']
        pts = np.asarray(d['points'], np.float64)
        scf = np.asarray(d['scale'], np.float64)
        r_ = float(d['rho'])
        # the station along the tibia: the base point's nearest point on the spine
        base = pts[0]
        j = int(np.argmin(np.linalg.norm(sp.P - base, axis=1)))
        lo, hi = max(j - 1, 0), min(j + 1, len(sp.P) - 1)
        uu = np.linspace(sp.s[lo], sp.s[hi], 81) / L
        best = min(uu, key=lambda u: np.linalg.norm(sp.at(u)[0] - base))
        if 'spur' in nm and pair != 'fore':
            F.append(dict(name=nm, kind='spur', u=float(best), path=pts, r=scf[:, 0] + r_, rho=r_))
        else:
            # a flat tooth: its base half-length (along the tibia) and half-thicknesses at base / tip, its tip
            side = 'inner' if 'spur' in nm else 'margin'
            F.append(dict(name=nm, kind='tooth', side=side, u=float(best), half_len=float(scf[0, 1] + r_),
                          th0=float(scf[0, 0] + r_), th1=float(scf[-1, 0] + r_), tip=pts[-1], p0=pts[0],
                          big=bool(np.linalg.norm(pts[-1] - pts[0]) > 0.45)))
    # ---- the stations: every margin feature's base ends (its own gap), the shaft between them filled to LAYOUT's spacing
    spans = []
    g = lay['min_gap'] / L
    for f in F:
        if f['kind'] == 'tooth' and f['side'] == 'margin':
            du = f['half_len'] / L
            u0, u1 = f['u'] - du, f['u'] + du
            # (a base end within min_gap of the apex snaps onto it: a ring 0.06 mm short of the apex made a sliver band whose
            # limit folded, p05 v2)
            u1 = 1.0 if u1 > 1.0 - g else u1
            u0 = min(u0, u1 - 0.12 / L)
            spans.append([u0, u1, f])
    spans.sort(key=lambda r: r[0])
    # neighbours apart by at least min_gap (shrunk toward their centres where they would touch)
    for a_, b_ in zip(spans[:-1], spans[1:]):
        if b_[0] - a_[1] < g:
            mid = 0.5 * (a_[1] + b_[0])
            a_[1], b_[0] = mid - 0.5 * g, mid + 0.5 * g
    req = sorted({0.0, 1.0} | {s_[0] for s_ in spans} | {s_[1] for s_ in spans})
    st = []
    for a_, b_ in zip(req[:-1], req[1:]):
        st.append(a_)
        own = any(abs(a_ - s_[0]) < 1e-12 and abs(b_ - s_[1]) < 1e-12 for s_ in spans)
        if not own:
            n_ = int(np.ceil((b_ - a_) * L / lay['spacing'][pair] - 1e-9))
            st += list(a_ + (b_ - a_) * np.arange(1, n_) / max(n_, 1))
    st = np.array(st + [1.0])
    W_ = np.interp(st, u_pts, wide)
    T_ = np.interp(st, u_pts, thick)
    rings = []
    frames = []
    nr0, nr1 = lay['neck_round']

    def t_neck(u_):
        """the share of the plain section at u (LAYOUT tibia neck_round: 1 on the neck, 0 where keeled)"""
        return 1.0 - float(smooth01((u_ - nr0) / (nr1 - nr0)))
    for j, u in enumerate(st):
        P, T, N, B = sp.at(u)
        e = e_sign * B
        tn = t_neck(u)
        q = (1.0 - tn) * tibia_section(W_[j], T_[j], sec) + tn * tibia_round(W_[j], T_[j], sec)
        rings.append(P[None, :] + q[:, :1] * e[None, :] + q[:, 1:] * N[None, :])
        frames.append((P, T, N, e))
    # ---- the ends: the clay sweep's flat ends lie rho past the end nodes, rounded by rho (a quarter circle): rings on it at
    # end_phi, the cap on the end plane inside the last of them
    ext = {0: [], 1: []}
    for end in (0, 1):
        P, T, N, e = frames[0 if end == 0 else -1]
        sgn = -1.0 if end == 0 else 1.0
        We, Te = W_[0 if end == 0 else -1], T_[0 if end == 0 else -1]
        for phi, rnd in zip(np.radians(lay['end_phi']), lay['end_round']):
            rnd = max(rnd, t_neck(0.0 if end == 0 else 1.0))       # (the proximal end: the neck's plain section)
            off, ins = rho * np.sin(phi), rho * (1.0 - np.cos(phi))
            q = ((1.0 - rnd) * tibia_section(We - 2.0 * ins, Te - 2.0 * ins, sec)
                 + rnd * tibia_round(We - 2.0 * ins, Te - 2.0 * ins, sec))
            ext[end].append(P[None, :] + sgn * off * T[None, :] + q[:, :1] * e[None, :] + q[:, 1:] * N[None, :])
    R = np.stack(ext[0][::-1] + rings + ext[1])
    n0 = len(ext[0])
    cg = Cage(name, 'tibia', 16)
    ids = cg.tube(R)
    m = 6
    cap_q = {}
    for end in (0, 1):
        j = 0 if end == 0 else len(R) - 1
        P, T, N, e = frames[0 if end == 0 else -1]
        sgn = -1.0 if end == 0 else 1.0
        ring = R[j]
        # (the Coons patch of the end ring, on the end plane: the clay sweep's flat end face, rho past the end node)
        pts = [p_ + ((P + sgn * rho * T - p_) @ T) * T for p_ in coons_cap(ring, m)]
        n_before = len(cg.Q)
        inner = cg.cap(ids[j], np.array(pts), flip=(end == 0))
        cap_q[end] = dict(quads=list(range(n_before, len(cg.Q))), interior=inner, ring=ids[j])
    # ---- the creases: the margin (k 0) along every station; the dorsal ridge (k 4) on the mid / hind tibiae
    jr = np.array([n0 + i for i, u in enumerate(st) if t_neck(u) < 0.5])   # (the keeled stations: none on the neck)
    # (each crease FADES over its first and last edges, CREASE fade: a crease that stopped at full sharpness on the end's first
    # station pinched a notch into the rounded end beside it, p11 q1; insect_cage eases its crest's crease out the same way)
    def faded(n_e, s_):
        w_ = np.ones(n_e)
        for i_, f_ in enumerate(CREASE_FADE):
            if i_ < n_e:
                w_[i_] = min(w_[i_], f_)
                w_[n_e - 1 - i_] = min(w_[n_e - 1 - i_], f_)
        return s_ * w_
    cg.crease([ids[j, 0] for j in jr], faded(len(jr) - 1, CREASE['margin']['s']))
    if sec['dorsal_angle'] is not None:
        cg.crease([ids[j, 4] for j in jr], faded(len(jr) - 1, CREASE['dorsal']['s']))
    st_all = np.concatenate([[-1.0] * n0, st, [2.0] * n0])
    cg.meta.update(spine=sp, stations=st, e_sign=e_sign, frames=frames, W=W_, T=T_, rho=rho, n_end=n0)
    # ---- the extrusions
    def take(faces):
        """the cage's own quads with these vertex sets (their winding as stored), removed"""
        got = []
        for f_ in faces:
            hit = [q for q in cg.Q if set(q) == set(f_)]
            assert len(hit) == 1, f'{name}: a feature face is not in the cage (shared with another feature?)'
            got.append(hit[0])
        cg.Q = [q for q in cg.Q if q not in got]
        return got

    dist_ring = ids[len(R) - 1]
    base_Q = list(cg.Q)                                       # the shaft and its caps before any feature (the spurs' exits)
    for f in F:
        if f['kind'] == 'tooth' and f['side'] == 'margin':
            sp_ = next(s_ for s_ in spans if s_[2] is f)
            ja = int(np.argmin(np.abs(st_all - sp_[0])))
            jb = int(np.argmin(np.abs(st_all - sp_[1])))
            assert jb > ja, f'{name}: {f["name"]}: no gap under its base'
            k0 = 0
            km, kp = (k0 - 1) % 16, (k0 + 1) % 16
            faces = []
            for j in range(ja, jb):
                faces += [(ids[j, km], ids[j, k0], ids[j + 1, k0], ids[j + 1, km]),
                          (ids[j, k0], ids[j, kp], ids[j + 1, kp], ids[j + 1, k0])]
            got = take(faces)
            for j in range(ja, jb):                                  # (the margin's crease under the tooth: no edge now)
                cg.sharp.pop((min(ids[j, k0], ids[j + 1, k0]), max(ids[j, k0], ids[j + 1, k0])), None)
            nj = jb - ja
            loop = patch_loop(got, start=ids[ja, km])
            fr = FEATURE_RINGS['big' if f['big'] else 'small']
            extrude(cg, loop, nj, flat_rings(cg, loop, nj, f, fr), f)
        elif f['kind'] == 'tooth' and f['side'] == 'inner':
            # the fore tibia's inner apical spur: the apex cap's two quads round the ring's point 7 (beside the inner extreme),
            # facing on along the tibia as the spur does
            r = cap_q[1]['ring']
            i5 = cap_q[1]['interior'][-1]
            got = take([(r[5], r[6], r[7], i5), (i5, r[7], r[8], r[9])])
            loop = patch_loop(got, mid_edge=(i5, r[7]))
            extrude(cg, loop, 1, flat_rings(cg, loop, 1, f, FEATURE_RINGS['big']), f)
        elif f['kind'] == 'spur':
            # a mid / hind APICAL SPUR (b4l-2): extruded from the cage face where the clay's own spur path LEAVES the shaft (the
            # path starts inside the apex: leg_parts' A_, MH_SPUR back), the first crossing of the path with the shaft's quads
            # still free; its rings on the path from that crossing, parallel-transported (no twist). b4l-1 took a fixed apex-cap
            # quad, and the path, leaving through the rim beside it, bent the spur's root over the cap: a kinked wire with a
            # dimple at its root (p10 e1)
            free = [q for q in base_Q if q in cg.Q]
            hit = path_exit(cg.V, free, f['path'])
            assert hit is not None, f'{name}: {f["name"]}: its path never leaves the shaft'
            got = take([free[hit[0]]])
            loop = patch_loop(got)
            extrude(cg, loop, 1, spur_rings(cg, loop, f, hit[2]), f, one_face=True)
            f['exit'] = dict(point=hit[1], s=hit[2], quad=tuple(int(v) for v in got[0]))
    cg.meta['cap_quads'] = cap_q
    return cg.orient()


def patch_loop(faces, start=None, mid_edge=None):
    """the directed boundary loop of a patch of quads, following their own winding (the extrusion's bands then run with the
    patch's neighbours); rotated to begin at `start`, or so that the shared edge mid_edge's ends sit at the template's two middle
    points (positions 1 and nb / 2 + 1)"""
    E = [(int(q[k]), int(q[(k + 1) % 4])) for q in faces for k in range(4)]
    S = set(E)
    bnd = [(a, b) for (a, b) in E if (b, a) not in S]
    nxt = dict(bnd)
    assert len(nxt) == len(bnd), 'patch_loop: a pinched patch'
    loop = [bnd[0][0]]
    while True:
        b = nxt[loop[-1]]
        if b == loop[0]:
            break
        loop.append(b)
    assert len(loop) == len(bnd), 'patch_loop: the boundary is not one loop'
    nb = len(loop)
    if start is not None:
        i = loop.index(int(start))
        loop = loop[i:] + loop[:i]
    elif mid_edge is not None:
        a, b = (int(v) for v in mid_edge)
        for i in range(nb):
            rot = loop[i:] + loop[:i]
            if {rot[1], rot[nb // 2 + 1]} == {a, b}:
                loop = rot
                break
        else:
            raise AssertionError('patch_loop: the shared edge is not across the loop')
    return loop


def flat_rings(cg, loop, nj, f, fr):
    """a FLAT TOOTH's rings (the clay's flat_tooth: its base half-length along the patch's middle line, its half-thickness across,
    tapering to its tip): straight from the patch's middle to the tip, one frame"""
    nb = len(loop)
    m1, m2 = cg.V[loop[1]], cg.V[loop[nb // 2 + 1]]
    base_m = 0.5 * (m1 + m2)
    a_hint = m2 - m1
    b_hint = cg.V[loop[0]] - cg.V[loop[2]]                   # toward the template's +y (its top: positions 0 and nb - 1)
    dt = _unit(f['tip'] - base_m)
    a_ = _unit(a_hint - dt * float(a_hint @ dt))
    b_ = _unit(b_hint - dt * float(b_hint @ dt) - a_ * float(b_hint @ a_))
    out = []
    for q_ in fr:
        c_ = base_m + q_ * (f['tip'] - base_m)
        out.append((c_, a_, b_, max(f['half_len'] * (1.0 - q_) ** 0.85, 0.018),
                    max(f['th0'] + (f['th1'] - f['th0']) * q_, 0.012)))
    return out


def path_exit(V, quads, path):
    """the first crossing of a polyline that starts inside a closed cage with a set of its quads (each as two triangles):
    (the index into `quads`, the point, the arc length along the path there), or None"""
    P = np.asarray(path, np.float64)
    Qa = np.asarray(quads, int).reshape(-1, 4)
    A, B, C, D = (V[Qa[:, k]] for k in range(4))
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    for i in range(len(P) - 1):
        o, d = P[i], P[i + 1] - P[i]
        best = None
        for T0, T1, T2 in ((A, B, C), (A, C, D)):
            e1, e2 = T1 - T0, T2 - T0
            h = np.cross(d, e2)
            a = np.einsum('ij,ij->i', e1, h)
            ok = np.abs(a) > 1e-15
            fa = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
            s_ = o - T0
            u = fa * np.einsum('ij,ij->i', s_, h)
            q = np.cross(s_, e1)
            v = fa * (q @ d)
            t = fa * np.einsum('ij,ij->i', e2, q)
            hit = ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t >= 0.0) & (t <= 1.0)
            if hit.any():
                j = int(np.argmin(np.where(hit, t, np.inf)))
                if best is None or t[j] < best[1]:
                    best = (j, float(t[j]))
        if best is not None:
            j, t = best
            return j, o + t * d, float(sl[i] + t * (sl[i + 1] - sl[i]))
    return None


def spur_rings(cg, loop, f, s0):
    """an APICAL SPUR's rings on its own path (the clay's sweep: radius rq + rho) from s0, where the path leaves the shaft through
    the base quad (path_exit), to near its tip, the frames parallel-transported from the base quad's own axes (no twist)"""
    path = f['path']
    P4 = cg.V[loop]
    a_hint = 0.5 * (P4[2] + P4[3]) - 0.5 * (P4[0] + P4[1])
    b_hint = 0.5 * (P4[0] + P4[3]) - 0.5 * (P4[1] + P4[2])
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    at = lambda s_: np.array([np.interp(s_, sl, path[:, a]) for a in range(3)])     # noqa: E731
    out = []
    a_prev, b_prev = None, None
    # the base quad's own frame (a, b in its plane, n its outward normal: the loop runs with the removed quad's winding)
    a_f = _unit(a_hint)
    b_f = _unit(b_hint - a_f * float(b_hint @ a_f))
    n_f = _unit(np.cross(P4[1] - P4[0], P4[3] - P4[0]) + np.cross(P4[3] - P4[2], P4[1] - P4[2]))
    for q_ in FEATURE_RINGS['spur']:
        s_ = s0 + q_ * (sl[-1] - s0)
        ta = _unit(at(min(s_ + 0.02, sl[-1])) - at(max(s_ - 0.02, 0.0)))
        if a_prev is None:
            # the first ring's frame: the base quad's turned by the least rotation taking its normal onto the path's tangent
            # (b4l-1 projected the quad's axes off the tangent: where the path leaves the face obliquely the projected axes
            # spun and the root twisted, p11 q1)
            n_use = n_f if float(n_f @ ta) >= 0.0 else -n_f
            ax_ = np.cross(n_use, ta)
            sa, ca = float(np.linalg.norm(ax_)), float(n_use @ ta)
            if sa > 1e-9:
                k_ = ax_ / sa
                Kx = np.array([[0.0, -k_[2], k_[1]], [k_[2], 0.0, -k_[0]], [-k_[1], k_[0], 0.0]])
                Rm = np.eye(3) + sa * Kx + (1.0 - ca) * Kx @ Kx
            else:
                Rm = np.eye(3)
            a_ = _unit(Rm @ a_f - ta * float((Rm @ a_f) @ ta))
            b_ = _unit(np.cross(ta, a_))
            b_ = b_ if b_ @ (Rm @ b_f) >= 0 else -b_
        else:
            a_ = _unit(a_prev - ta * float(a_prev @ ta))
            b_ = _unit(np.cross(ta, a_))
            b_ = b_ if b_ @ b_prev >= 0 else -b_
        a_prev, b_prev = a_, b_
        r_ = float(np.interp(s_, sl, f['r']))
        out.append((at(s_), a_, b_, r_, r_))
    return out


def template(nj, one_face=False):
    """insect_mcage's template: the section's (along, across) points in its boundary's order (proximal side top, middle, bottom;
    the bottom edge; the distal side bottom, middle, top; the top edge back), the corners in; a one-face patch: its four corners"""
    if one_face:
        return np.array([(-1.0, 1.0), (-1.0, -1.0), (1.0, -1.0), (1.0, 1.0)]) * 0.80
    cor = 0.80
    P = [(-cor, cor), (-1.0, 0.0), (-cor, -cor)] + [(-1.0 + 2.0 * m / nj, -1.0) for m in range(1, nj)]
    P += [(cor, -cor), (1.0, 0.0), (cor, cor)] + [(-1.0 + 2.0 * m / nj, 1.0) for m in range(nj - 1, 0, -1)]
    return np.array(P, np.float64)


def extrude(cg, bl, nj, rings_f, f, one_face=False):
    """a feature: its rings (centre, along axis a, across axis b, half-sizes A / B) from the boundary loop bl (patch_loop's: the
    patch's own winding), a cap across the last ring (one quad for a one-face spur)"""
    TP = template(nj, one_face)
    nb = len(bl)
    assert len(TP) == nb
    prev = list(bl)
    tip = rings_f[-1][0] + (rings_f[-1][0] - (rings_f[-2][0] if len(rings_f) > 1 else cg.V[bl].mean(0)))
    for c_, a_, b_, A, Bt in rings_f:
        pts = c_[None, :] + TP[:, :1] * A * a_[None, :] + TP[:, 1:] * Bt * b_[None, :]
        ids = cg.add(pts)
        for m in range(nb):
            cg.Q.append((prev[m], prev[(m + 1) % nb], ids[(m + 1) % nb], ids[m]))
        prev = ids
    if one_face:
        # the tip: the last ring closed by one quad, traversed against the last band (each band runs the new ring backwards)
        cg.Q.append((prev[0], prev[1], prev[2], prev[3]))
    else:
        # insect_mcage's cap across the last ring: its top and bottom rows the template's top and bottom edges, its middle row
        # the proximal middle, nj - 1 interior points, the distal middle
        r = prev
        top = [r[0]] + [r[(2 * nj + 4) - m] for m in range(1, nj)] + [r[nj + 4]]
        bot = [r[2]] + [r[2 + m] for m in range(1, nj)] + [r[nj + 2]]
        mids = [r[1]]
        if nj > 1:
            Pl = cg.V[r]
            ax_ = _unit(tip - Pl.mean(0))
            rad = float(np.mean(np.linalg.norm(Pl - Pl.mean(0), axis=1)))
            mp = [0.5 * (cg.V[top[m]] + cg.V[bot[m]]) + 0.30 * rad * ax_ for m in range(1, nj)]
            mids += cg.add(np.array(mp))
        mids.append(r[nj + 3])
        for m in range(nj):
            cg.Q.append((top[m], mids[m], mids[m + 1], top[m + 1]))
            cg.Q.append((mids[m], bot[m], bot[m + 1], mids[m + 1]))
    cg.features.append(dict(name=f['name'], kind=f['kind'], rings=len(rings_f), gaps=nj))


# ============================================================================================ one leg
def leg_cages(spec, chain, clay, pair):
    """the left leg's segment cages (Cage per LEG_NAMES entry, claw_b a rigid copy of claw_a) from the clay's descriptors"""
    from . import arthropod_parts as AP
    s = chain['scale_m']
    L_ = clay['legs'][pair]
    out = {}
    # ---- coxa (its clay field with the clay's femur groove: clay_programs carved)
    dc = L_['coxa'][0][0]
    f_c = clay['carved'][pair]['coxa']
    if dc['kind'] == 'roundcone':
        sp = Spine([dc['a'], dc['b']])
        tm = dc['ra'] + dc['rb'] + np.linalg.norm(dc['b'] - dc['a'])
    else:
        ax = np.asarray(dc['axes'], np.float64)
        hh = np.asarray(dc['half'], np.float64)
        i_l = 0 if hh[0] >= hh[2] else 2
        e_l = ax[:, i_l]
        r_round = min(float(dc['r']), float(hh[1]))
        ext = max(hh[i_l] - r_round, 0.15)
        sp = Spine([dc['c'] - ext * e_l, dc['c'] + ext * e_l], N=ax[:, 1])
        tm = 2.0 * float(hh.max()) + 1.0
    out['coxa'] = cast_tube(f'coxa {pair}', 'coxa', f_c, sp, LAYOUT['coxa']['K'], LAYOUT['coxa']['n'], tm)
    # ---- trochanter
    dt = L_['trochanter'][0][0]
    sp = Spine([dt['a'], dt['b']])
    out['trochanter'] = cast_tube(f'trochanter {pair}', 'trochanter', clay['carved'][pair]['trochanter'], sp,
                                  LAYOUT['trochanter']['K'], LAYOUT['trochanter']['n'],
                                  dt['ra'] + dt['rb'] + np.linalg.norm(dt['b'] - dt['a']))
    # ---- femur: the shaft's spine on into the club, to the club's end-sphere centre
    g = L_['femur'][0][0]
    shaft = next(m for m in g['members'] if m['kind'] == 'psweep')
    club = next(m for m in g['members'] if m['kind'] == 'roundbox')
    uf = np.asarray(club['axes'], np.float64)[:, 0]
    half = np.asarray(club['half'], np.float64)
    rk = float(club['r'])
    p_end = np.asarray(club['c'], np.float64) + max(half[0] - rk, 0.0) * uf
    pts = np.asarray(shaft['points'], np.float64)
    spine_pts = np.vstack([pts, p_end[None, :]]) if np.linalg.norm(p_end - pts[-1]) > 1e-6 else pts
    Nf = np.asarray(shaft['normal'], np.float64)
    Nf = np.vstack([Nf, Nf[-1:]]) if len(spine_pts) > len(Nf) else Nf
    sp = Spine(spine_pts, Nf)
    out['femur'] = cast_tube(f'femur {pair}', 'femur', clay['carved'][pair]['femur'], sp, LAYOUT['femur']['K'],
                             LAYOUT['femur']['n'], 3.0)
    # ---- tibia
    out['tibia'] = tibia_cage(f'tibia {pair}', pair, L_['tibia'][0], clay['sink'])
    # ---- tarsomeres
    for n in range(1, 6):
        d = L_[f'tarsus_{n}'][0][0]
        cone = d['members'][0] if d['kind'] == 'group' else d
        sp = Spine([cone['a'], cone['b']])
        lay = LAYOUT['tarsus_5' if n == 5 else 'tarsus']
        out[f'tarsus_{n}'] = cast_tube(f'tarsus {n} {pair}', 'tarsus', field_of(L_[f'tarsus_{n}'][0], s), sp, lay['K'],
                                       lay['n'], 1.2)
    # ---- the claws: claw a cast on its sweep united with the claws' BASE BALL (CLAW_BASE: centred on the claw joint, so the two
    # claws stay congruent under the turn; the clay sank them by a pretarsus knob on claw b alone, which a copy cannot carry);
    # claw b its rigid copy (a turn about the vertical through the claw joint)
    da = L_['claw_a'][0][0]
    J5 = chain['pos'][f'claw_{pair[0]}_L']
    f_hook = field_of(L_['claw_a'][0], s)
    rb_, kb_ = CLAW_BASE['r'], CLAW_BASE['k']

    def f_claw(P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        a_ = f_hook(P)
        b_ = np.linalg.norm(P - J5[None, :], axis=1) - rb_
        h = np.clip(0.5 + 0.5 * (b_ - a_) / kb_, 0.0, 1.0)
        return b_ * (1 - h) + a_ * h - kb_ * h * (1 - h)            # the polynomial smooth min (sdf.py's family)
    pts_c = np.vstack([J5[None, :], np.asarray(da['points'], np.float64)])
    Nc = np.asarray(da['normal'], np.float64)
    sp = Spine(pts_c, np.vstack([Nc[:1], Nc]))
    ca = cast_tube(f'claw a {pair}', 'claw', f_claw, sp, LAYOUT['claw']['K'], LAYOUT['claw']['n'], 0.6,
                   taper_w=LAYOUT['claw']['taper_w'])
    db = L_['claw_b'][0][0]
    hook_b = db['members'][0] if db['kind'] == 'group' else db
    ua = _unit(np.asarray(da['points'])[-1] - J5)
    ub = _unit(np.asarray(hook_b['points'])[-1] - J5)
    ang = np.arctan2(ua[0], ua[2]) - np.arctan2(ub[0], ub[2])
    Ry = np.array([[np.cos(-ang), 0.0, np.sin(-ang)], [0.0, 1.0, 0.0], [-np.sin(-ang), 0.0, np.cos(-ang)]])
    # the claw's local frame (origin the claw joint, x its chord in plan, y up): claw a's cage there, placed twice
    yaw_a = np.arctan2(ua[0], ua[2])
    Ra = np.array([[np.cos(yaw_a), 0.0, np.sin(yaw_a)], [0.0, 1.0, 0.0], [-np.sin(yaw_a), 0.0, np.cos(yaw_a)]])
    local = (ca.V - J5[None, :]) @ Ra            # R_a^T (p - J5), row form
    ca.V = J5[None, :] + local @ Ra.T
    cb = Cage(f'claw b {pair}', 'claw', ca.K)
    Rb = Ry @ Ra
    cb.V = J5[None, :] + local @ Rb.T
    cb.Q = list(ca.Q)
    cb.sharp = dict(ca.sharp)
    cb.rings = ca.rings
    cb.meta = dict(ca.meta, copy_of='claw_a', R=Rb)
    ca.meta.update(local=local, R=Ra, joint_pt=J5)
    cb.meta.update(local=local, joint_pt=J5)
    out['claw_a'], out['claw_b'] = ca, cb
    for k, cg in out.items():
        cg.meta['parent'] = {'coxa': 'body', 'trochanter': 'coxa', 'femur': 'trochanter', 'tibia': 'femur',
                             'tarsus_1': 'tibia', 'claw_a': 'tarsus_5', 'claw_b': 'tarsus_5'}.get(
            k, f'tarsus_{int(k[-1]) - 1}' if k.startswith('tarsus') else None)
        cg.meta['joint'] = {'claw_a': f'claw_{pair[0]}', 'claw_b': f'claw_{pair[0]}'}.get(k, f'{k}_{pair[0]}')
    return out


# ============================================================================================ fit, limit, low
def limit(cg, levels=None, fit_levels=None):
    """the controls fitted (the limit through the targets) and the limit mesh; vertices no quad uses (a feature's replaced
    patch) left out of the fit and the subdivision (insect_mcage m7f). Returns (limit QuadMesh, controls V0 (cage numbering),
    the fit's residual, the compact cage QuadMesh (targets), its sharp dict)"""
    levels = LEVELS['out'] if levels is None else levels
    fit_levels = LEVELS['fit'] if fit_levels is None else fit_levels
    Q = np.asarray(cg.Q, int)
    used = np.zeros(len(cg.V), bool)
    used[Q.ravel()] = True
    new = -np.ones(len(cg.V), int)
    new[used] = np.arange(int(used.sum()))
    mc_ = QuadMesh(cg.V[used], new[Q])
    sh_ = {(int(new[a]), int(new[b])): s for (a, b), s in cg.sharp.items() if used[a] and used[b]}
    V0c, res = SS.fit_controls(mc_, sh_, mc_.V, fit_levels)
    lim, _, _, _ = SS.subdivide(QuadMesh(V0c, mc_.Q), sh_, levels)
    V0 = cg.V.copy()
    V0[used] = V0c
    return lim, V0, res, mc_, sh_


def mirror_mesh(V, Q):
    """the right side: p_R = M p_L, every quad reversed (outward kept); the same vertex numbering (stacked UVs)"""
    return np.asarray(V, np.float64) * np.array([-1.0, 1.0, 1.0]), np.asarray(Q, int)[:, ::-1].copy()


def to_author(V, spec=None, author_scale=None):
    """life mm -> metres at the author scale (spec['author_scale'] unless given: x10 for B1; the M2 graft passes its own)"""
    a = float(author_scale if author_scale is not None else spec['author_scale'])
    return np.asarray(V, np.float64) * a * 1e-3


# ============================================================================================ Warp mesh queries
_WK = {}


def _wk():
    if _WK:
        return _WK
    import warp as wp

    @wp.kernel
    def k_sdf(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        p = pts[tid]
        q = wp.mesh_query_point_sign_winding_number(mesh, p, maxd, 2.0, 0.5)
        if q.result:
            c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[tid] = wp.length(p - c) * q.sign
        else:
            out[tid] = maxd

    @wp.kernel
    def k_udf(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        p = pts[tid]
        q = wp.mesh_query_point_no_sign(mesh, p, maxd)
        if q.result:
            c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[tid] = wp.length(p - c)
        else:
            out[tid] = maxd

    @wp.kernel
    def k_ray(mesh: wp.uint64, o: wp.array(dtype=wp.vec3), d: wp.array(dtype=wp.vec3), tmax: float,
              out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        q = wp.mesh_query_ray(mesh, o[tid], d[tid], tmax)
        if q.result:
            out[tid] = q.t
        else:
            out[tid] = -1.0

    @wp.kernel
    def k_ray_face(mesh: wp.uint64, o: wp.array(dtype=wp.vec3), d: wp.array(dtype=wp.vec3), tmax: float,
                   out: wp.array(dtype=wp.float32), face: wp.array(dtype=wp.int32)):
        tid = wp.tid()
        q = wp.mesh_query_ray(mesh, o[tid], d[tid], tmax)
        if q.result:
            out[tid] = q.t
            face[tid] = q.face
        else:
            out[tid] = -1.0
            face[tid] = -1
    _WK.update(sdf=k_sdf, udf=k_udf, ray=k_ray, ray_face=k_ray_face, wp=wp)
    return _WK


class MeshQ:
    """a triangle mesh (life mm) for signed / unsigned distances and rays (Warp, the preferred device)"""

    def __init__(self, V, F):
        k = _wk()
        wp = k['wp']
        self.dev = wp.get_preferred_device()
        self.V = np.asarray(V, np.float32)
        self.F = np.asarray(F, np.int32)
        self.m = wp.Mesh(points=wp.array(self.V, dtype=wp.vec3, device=self.dev),
                         indices=wp.array(self.F.ravel(), dtype=wp.int32, device=self.dev), support_winding_number=True)

    def _run(self, kern, P, maxd):
        k = _wk()
        wp = k['wp']
        P = np.asarray(P, np.float32).reshape(-1, 3)
        o = wp.zeros(len(P), dtype=wp.float32, device=self.dev)
        wp.launch(k[kern], dim=len(P), inputs=[self.m.id, wp.array(P, dtype=wp.vec3, device=self.dev), float(maxd), o],
                  device=self.dev)
        return o.numpy().astype(np.float64)

    def sdf(self, P, maxd=10.0):
        return self._run('sdf', P, maxd)

    def udf(self, P, maxd=10.0):
        return self._run('udf', P, maxd)

    def ray(self, O, D, tmax=10.0):
        k = _wk()
        wp = k['wp']
        O = np.asarray(O, np.float32).reshape(-1, 3)
        D = np.asarray(D, np.float32).reshape(-1, 3)
        o = wp.zeros(len(O), dtype=wp.float32, device=self.dev)
        wp.launch(k['ray'], dim=len(O), inputs=[self.m.id, wp.array(O, dtype=wp.vec3, device=self.dev),
                                                 wp.array(D, dtype=wp.vec3, device=self.dev), float(tmax), o], device=self.dev)
        return o.numpy().astype(np.float64)

    def ray_face(self, O, D, tmax=10.0):
        """the first hit's distance and triangle (-1 / -1 where none)"""
        k = _wk()
        wp = k['wp']
        O = np.asarray(O, np.float32).reshape(-1, 3)
        D = np.asarray(D, np.float32).reshape(-1, 3)
        o = wp.zeros(len(O), dtype=wp.float32, device=self.dev)
        f = wp.zeros(len(O), dtype=wp.int32, device=self.dev)
        wp.launch(k['ray_face'], dim=len(O), inputs=[self.m.id, wp.array(O, dtype=wp.vec3, device=self.dev),
                                                      wp.array(D, dtype=wp.vec3, device=self.dev), float(tmax), o, f],
                  device=self.dev)
        return o.numpy().astype(np.float64), f.numpy().astype(np.int64)


# ============================================================================================ the sleeves and the graft rings
def port_frame(normal, side='L'):
    """slots.port_frame's rule (the creature's lateral axis made perpendicular to the normal: +X on the left, -X on the right; -Z
    world where the normal lies within 25.8 deg of the lateral axis): (Z, X, Y = Z x X), right-handed on the left"""
    n = _unit(normal)
    ref = np.array([0.0, 0.0, -1.0]) if abs(n[0]) > 0.9 else (np.array([-1.0, 0.0, 0.0]) if side == 'R'
                                                             else np.array([1.0, 0.0, 0.0]))
    t = _unit(ref - n * float(ref @ n))
    return n, t, np.cross(n, t)


def ring_K(radii, K_min=None, texels=None):
    """the least K (a multiple of 4, >= K_min) whose chord sag r (1 - cos pi / K) at the ring's largest radius is within `texels`
    texels at 9,257 px/m, x10 (CROSSBREED §2.2)"""
    K_min = SLEEVE['K_min'] if K_min is None else K_min
    texels = SLEEVE['sag_texels'] if texels is None else texels
    r = float(np.max(radii))
    K = K_min
    while r * (1.0 - np.cos(np.pi / K)) > texels * TEXEL_LIFE:
        K += 4
    return K, r * (1.0 - np.cos(np.pi / K)) / TEXEL_LIFE


def sleeve(name, origin, axis, parent_sdf, child_q, child_extra=None, K=None, graft=False):
    """one SLEEVE (module docstring): X where the child's axis (from origin, inside the parent) leaves the parent (parent_sdf:
    points -> signed mm), three planar rings normal to the axis at X - d, X, X + d, each the child's own section from the axis
    (rays on child_q, the child's limit mesh; child_extra: more child meshes whose section the ring must also stay inside: the
    claws' two hooks) x in_child. K: the graft rings' K from their radius (ring_K); 12 elsewhere. Returns a dict"""
    axis = _unit(axis)
    # X: the inside -> outside crossing of the parent along the axis nearest the origin (scanned from behind it: a seated child's
    # spine starts at its end sphere's centre, which can lie just past the parent's surface, the trochanter's 0.14 mm)
    ts = np.arange(-1.5, 3.0, 0.002)
    f = parent_sdf(origin[None, :] + ts[:, None] * axis[None, :])
    io = np.nonzero((f[:-1] < 0) & (f[1:] >= 0))[0]
    assert len(io), f'{name}: the child\'s axis never leaves the parent'
    i = int(io[np.argmin(np.abs(ts[io]))])
    X = origin + (ts[i] - f[i] * (ts[i + 1] - ts[i]) / (f[i + 1] - f[i])) * axis
    Z, Xt, Y = port_frame(axis, 'L')

    def section(c, Kk):
        th = 2.0 * np.pi * np.arange(Kk) / Kk
        D = np.cos(th)[:, None] * Xt[None, :] + np.sin(th)[:, None] * Y[None, :]
        O = np.repeat(c[None, :], Kk, axis=0)
        r = child_q.ray(O, D, 5.0)
        for q in child_extra or ():
            rx = q.ray(O, D, 5.0)
            r = np.minimum(r, np.where(rx > 0, rx, 9.0))
        return r, D
    r_x, _ = section(X, 48)
    assert (r_x > 0).all(), f'{name}: the sleeve\'s centre is not inside the child at X'
    d = float(np.clip(SLEEVE['step'] * np.median(r_x), SLEEVE['step_min'], SLEEVE['step_max']))
    # the proximal step no farther than half the child's own extent behind X (a short seated egg: the hind trochanter's pole lies
    # 0.2-0.3 mm behind it)
    t_back = float(child_q.ray(X[None, :], -axis[None, :], 5.0)[0])
    d_in = min(d, 0.5 * t_back) if t_back > 0 else d
    if K is None:
        K = SLEEVE['K_min']
        if graft:
            K, _ = ring_K(SLEEVE['in_child'] * r_x)
    rings, radii = [], []
    for j, off in enumerate((-d_in, 0.0, d)):
        c = X + off * axis
        r, D = section(c, K)
        assert (r > 0).all(), f'{name}: ring {j} leaves the child'
        r = SLEEVE['in_child'] * r
        rings.append(c[None, :] + r[:, None] * D)
        radii.append(r)
    R = np.stack(rings)
    V = R.reshape(-1, 3)
    Q = []
    for j in range(2):
        for k in range(K):
            Q.append((j * K + k, j * K + (k + 1) % K, (j + 1) * K + (k + 1) % K, (j + 1) * K + k))
    Q = np.array(Q, int)
    # outward (away from the axis)
    c_ = V[Q].mean(1)
    nq = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    radial = c_ - (X + ((c_ - X) @ axis)[:, None] * axis[None, :])
    if np.sum(np.einsum('ij,ij->i', nq, radial)) < 0:
        Q = Q[:, ::-1].copy()
    sag = max(float(np.max(r) * (1.0 - np.cos(np.pi / K))) for r in radii) / TEXEL_LIFE
    return dict(name=name, V=V, Q=Q, K=K, X=X, axis=axis, frame=dict(Z=Z, X=Xt, Y=Y), step=d, step_in=d_in, radii=radii,
                sag_texels=sag, graft=graft)


def section_fit(ring_local):
    """sdf.SWEEP's section vocabulary {r0, a2, phi2, a3, phi3, a4, aspect} least-squares fitted to a ring's points (local
    (x, y) in the port frame: theta from X toward Y); aspect from the extents, the harmonics linear; the residual per point"""
    x, y = ring_local[:, 0], ring_local[:, 1]
    th = np.arctan2(y, x)
    r = np.hypot(x, y)
    asp = float(np.ptp(y) / max(np.ptp(x), 1e-12))
    sq = asp / np.sqrt(asp * asp * np.cos(th) ** 2 + np.sin(th) ** 2)
    base = r / sq
    A = np.column_stack([np.ones_like(th), np.cos(2 * th), np.sin(2 * th), np.cos(3 * th), np.sin(3 * th), np.cos(4 * th)])
    co, *_ = np.linalg.lstsq(A, base, rcond=None)
    r0 = float(co[0])
    a2, phi2 = float(np.hypot(co[1], co[2]) / r0), float(0.5 * np.arctan2(co[2], co[1]))
    a3, phi3 = float(np.hypot(co[3], co[4]) / r0), float(np.arctan2(co[4], co[3]) / 3.0)
    a4 = float(co[5] / r0)
    fitr = (A @ co) * sq
    return dict(r0=r0, a2=a2, phi2=phi2, a3=a3, phi3=phi3, a4=a4, aspect=asp), r - fitr


def joint_frame(rec, sk):
    """CROSSBREED §2.11: the record's `frame` and `origin` in the bind frame of the joint the ring is 100 % on (sk:
    arthropod.skeleton at the record's author scale, metres), beside the creature frame's (`frame_creature`,
    `origin_creature`, as the vertices and normals are: the export's mesh space)"""
    j = rec['weights']['joints'][0]
    W = sk.world[sk.index(j)]
    R_, o = W[:3, :3], W[:3, 3]
    fc, oc = rec['frame_creature'], np.asarray(rec['origin_creature'], np.float64)
    rec['frame'] = dict(normal=(R_.T @ np.asarray(fc['normal'])).tolist(), tangent=(R_.T @ np.asarray(fc['tangent'])).tolist(),
                        joint=j, space='the joint\'s bind frame')
    rec['origin'] = (R_.T @ (oc - o)).tolist()
    return rec


def ring_record(slv, cut, pair, side, parent_joint, native, spec, chain_pts, author_scale=None, sk=None):
    """CROSSBREED §2.11's ring record for a graft sleeve's PROXIMAL ring (R10: 100 % on the parent), at the author scale in metres;
    the right side's record is the left's mirrored (vertex k of R = M vertex k of L). sk (arthropod.skeleton at that author
    scale): the frame and origin in the joint's bind frame as well (joint_frame)"""
    K = slv['K']
    a = float(author_scale if author_scale is not None else spec['author_scale'])
    sc = a * 1e-3
    V = slv['V'][:K].copy()
    Z, Xt, Y = (np.asarray(slv['frame'][k], np.float64) for k in ('Z', 'X', 'Y'))
    c = V.mean(0)
    # the frozen normals: the sleeve's own vertex normals at the ring (welded: the band's next ring present)
    qm = QuadMesh(slv['V'], slv['Q'])
    vn = qm.vertex_normals()[:K]
    loc = np.column_stack([(V - c) @ Xt, (V - c) @ Y])
    secf, resid = section_fit(loc)
    planar = float(np.max(np.abs((V - c) @ Z)))
    rbar = float(np.mean(np.linalg.norm(V - c, axis=1)))
    # seam_k: the axis vertex (k in 0, K/4, K/2, 3K/4) on the hidden line, caudomedial on a limb (WOLF_PLAN.md:824)
    hid = _unit(np.array([-1.0, 0.0, -1.0]))
    seam_k = max((0, K // 4, K // 2, 3 * K // 4), key=lambda k: float(_unit(V[k] - c) @ hid))
    # the anatomical share along the leg's chain (coxa joint .. claw tip)
    seg = np.linalg.norm(np.diff(chain_pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    best = (1e9, 0.0)
    for i in range(len(seg)):
        p0, p1 = chain_pts[i], chain_pts[i + 1]
        t = float(np.clip((c - p0) @ (p1 - p0) / max(seg[i] ** 2, 1e-12), 0.0, 1.0))
        dd = float(np.linalg.norm(p0 + t * (p1 - p0) - c))
        if dd < best[0]:
            best = (dd, (cum[i] + t * seg[i]) / cum[-1])
    rec = dict(K=K, cut=cut, pair=pair, side=side,
               frame_creature=dict(normal=Z.tolist(), tangent=Xt.tolist()), origin_creature=(c * sc).tolist(),
               frame=None, origin=None,
               section={k: (v * sc if k == 'r0' else v) for k, v in secf.items()}, section_residual=(resid * sc).tolist(),
               slope=dict(dr_dz=float((np.mean(slv['radii'][1]) - np.mean(slv['radii'][0])) / slv['step_in'])),
               verts=(V * sc).tolist(), normals=vn.tolist(),
               weights=dict(joints=[parent_joint], w=[[1.0] for _ in range(K)]),
               coat=None, h=float(slv['step_in'] * sc), seam_k=int(seam_k), px_per_m=PX_PER_M, set='BODY',
               **{'class': 'membrane'}, shell_class='chitin', st_s=float(best[1]),
               native=native, planarity=planar / max(rbar, 1e-12), sag_texels=float(slv['sag_texels']),
               units='metres at the author scale', author_scale=a, build=None)
    return joint_frame(rec, sk) if sk is not None else rec


def mirror_record(rec, sk=None):
    """the right side's record: every point and direction x -> -x in the creature frame, vertex k kept (left-handed about Z on
    the right: CROSSBREED §2.2); the port frame's tangent -X there, as slots.port_frame gives it; sk: the frame and origin in
    the right joint's own bind frame (joint_frame), else left None"""
    M = np.array([-1.0, 1.0, 1.0])
    r = json.loads(json.dumps(rec))
    r['side'] = 'R'
    fc = rec['frame_creature']
    r['frame_creature'] = dict(normal=(np.array(fc['normal']) * M).tolist(), tangent=(np.array(fc['tangent']) * M).tolist())
    r['origin_creature'] = (np.array(rec['origin_creature']) * M).tolist()
    r['verts'] = (np.array(rec['verts']) * M).tolist()
    r['normals'] = (np.array(rec['normals']) * M).tolist()
    r['weights'] = dict(joints=[j[:-2] + '_R' if j.endswith('_L') else j for j in rec['weights']['joints']],
                        w=rec['weights']['w'])
    r['native'] = json.loads(json.dumps(rec['native']).replace('_L"', '_R"'))
    r['frame'], r['origin'] = None, None
    return joint_frame(r, sk) if sk is not None else r


def graft_records(segs, sl, pair, chain, spec, key, sk, author_scale=None):
    """one leg's graft rings (CROSSBREED §7.3's coxa, knee and ankle cuts as corrected by R10 and the lead's decision 9): each
    the PROXIMAL ring of the sleeve at that joint, 100 % on the parent (no pin), its record at the author scale; the sleeve
    itself is native (R10: dropped with the graft, the part re-makes it from the ring), so the native group holds it with
    every segment, sleeve and claw past the cut. Returns ({cut: left record}, {cut: right record})"""
    c = pair[0]
    P_ = chain['pos']
    chain_pts = np.array([P_[f'coxa_{c}_L'], P_[f'trochanter_{c}_L'], P_[f'femur_{c}_L'], P_[f'tibia_{c}_L']] +
                         [P_[f'tarsus_{n}_{c}_L'] for n in range(1, 6)] + [P_[f'claw_{c}_L'], P_[f'claw_tip_{c}_L']])
    segs_after = {'coxa': LEG_NAMES, 'knee': LEG_NAMES[3:], 'ankle': LEG_NAMES[4:]}
    L, R = {}, {}
    for cut, (par, chd) in GRAFT_CUTS.items():
        s_ = next(x for x in sl if x['child'] == chd)
        names = segs_after[cut]
        kids = set(names) | {'claw'}                              # (the claws' sleeve: its child is the pair, 'claw')
        joints = sorted({segs[n]['joint'] + '_L' for n in names})
        native = dict(group=[f'{n}_{c}_L' for n in names] + [f'sleeve {x["parent"]}-{x["child"]} {c}_L' for x in sl
                                                             if x['child'] in kids],
                      sleeve=f'sleeve {s_["parent"]}-{s_["child"]} {c}_L', joints=joints, instances={},
                      fx=[f'socket_claw_{c}_L', f'socket_foot_{c}_L'])
        rec = ring_record(s_, cut, pair, 'L', s_['parent_joint'], native, spec, chain_pts, author_scale=author_scale, sk=sk)
        rec['build'] = key
        L[cut] = rec
        R[cut] = mirror_record(rec, sk)
    return L, R


def tibia_root(sl):
    """the tibia's section where it leaves the femur (the knee sleeve's middle ring, at X, divided by in_child): its largest
    and mean diameter (life mm), the size the M2 graft scales to its socket (CROSSBREED §8 M2)"""
    s_ = next(x for x in sl if x['child'] == 'tibia')
    r = np.asarray(s_['radii'][1], np.float64) / SLEEVE['in_child']
    K = len(r)
    d = r[:K // 2] + r[K // 2:]
    return dict(d_max=float(d.max()), d_mean=float(d.mean()), K=K)


def author_scale_for_root(legs, pair, width_m=0.034, which='d_max'):
    """the author scale at which the tibia's root (tibia_root: its section where it leaves the femur) is width_m metres across
    (CROSSBREED §8 M2: the tibia's root about 34 mm wide on the octopus's 18 mm cut-8 ring); pass it as author_scale to
    to_author / graft_records (with arthropod.skeleton(spec, chain, scale=author_scale * 1e-3))"""
    return width_m / (legs['tibia_root'][pair][which] * 1e-3)


# ============================================================================================ every leg
SLEEVE_JOINTS = (('body', 'coxa'), ('coxa', 'trochanter'), ('trochanter', 'femur'), ('femur', 'tibia'), ('tibia', 'tarsus_1'),
                 ('tarsus_1', 'tarsus_2'), ('tarsus_2', 'tarsus_3'), ('tarsus_3', 'tarsus_4'), ('tarsus_4', 'tarsus_5'),
                 ('tarsus_5', 'claw'))


def legs_key(spec, clay):
    """every input: this module's own source (any edit rebuilds), its tables, the clay's leg descriptors digested, the SPEC's legs"""
    with open(os.path.abspath(__file__), 'rb') as fh:
        src = hashlib.sha1(fh.read()).hexdigest()
    return cache_key(dict(v=VERSION, src=src, layout=LAYOUT, sec=TIBIA_SEC, crease=CREASE, sleeve=SLEEVE, levels=LEVELS,
                          feat=FEATURE_RINGS, claw=CLAW_BASE, clay=clay['digest'], legs=spec['legs'], rest=spec['rest'],
                          rig=spec['rig'], sink=clay['sink']))


def build_legs(spec=None, chain=None, levels=None, log=print, cache=True):
    """EVERY LEG (module docstring), cached by every input (the clay's leg descriptors digested): per pair the left segments' cages
    (targets, quads, creases), their fitted controls and limit meshes at `levels`; the sleeves; the graft rings' records (x10),
    left and right. The right side's meshes are made on load by mirror_legs (exact copies). Returns dict(pairs={pair: {seg:
    dict(V, Q, sharp, ctrl, lim_V, lim_F, kind, joint, parent, features, meta)}}, sleeves={pair: [...]}, rings={pair: {cut:
    record}}, rings_R (the right side's records), tibia_root={pair: tibia_root}, key, path)"""
    from ..species import stag_beetle as SB
    from . import arthropod as AR
    spec = SB.SPEC if spec is None else spec
    chain = AR.rest_chain(spec) if chain is None else chain
    levels = LEVELS['out'] if levels is None else levels
    clay = clay_programs(spec, chain)
    key = legs_key(spec, clay) + f'_L{levels}'
    path = os.path.join(CACHE, f'b4_legs_{key}.npz')
    if cache and os.path.exists(path):
        return load_legs(path, key)
    t0 = time.time()
    sk = AR.skeleton(spec, chain)
    out = dict(pairs={}, sleeves={}, rings={}, rings_R={}, tibia_root={}, key=key, path=path)
    for c, pair, cox, i in AR.LEGS:
        cages = leg_cages(spec, chain, clay, pair)
        segs = {}
        for nm, cg in cages.items():
            if cg.meta.get('copy_of'):
                continue
            lim, V0, res, mc, sh = limit(cg, levels=levels)
            used = np.unique(np.asarray(cg.Q).ravel())
            segs[nm] = dict(V=mc.V, Q=mc.Q, sharp=sh, ctrl=V0[used], lim_V=lim.V, lim_F=lim.tris(), kind=cg.kind,
                            joint=cg.meta['joint'], parent=cg.meta['parent'], features=cg.features, res=res,
                            spine=(cg.meta['spine'].P, cg.meta['spine'].N))
            log(f'[legs] {pair} {nm}: {len(mc.Q)} quads, {len(sh)} creases, fit {res:.1e}, limit {len(lim.Q)} quads '
                f'({time.time() - t0:.0f}s)')
        # claw b: claw a's mesh under the rigid turn (exact copies: the same local cage, two placements)
        ca, cb = cages['claw_a'], cages['claw_b']
        Ra, Rb, J5 = ca.meta['R'], cb.meta['R'], ca.meta['joint_pt']
        A_ = segs['claw_a']
        to_b = lambda P: J5[None, :] + ((np.asarray(P) - J5[None, :]) @ Ra) @ Rb.T        # noqa: E731
        segs['claw_b'] = dict(A_, V=to_b(A_['V']), ctrl=to_b(A_['ctrl']), lim_V=to_b(A_['lim_V']),
                              spine=(to_b(A_['spine'][0]), A_['spine'][1] @ Ra @ Rb.T), copy_of='claw_a',
                              copy_R=(Rb @ Ra.T), copy_origin=J5)
        out['pairs'][pair] = segs
        # ---- the sleeves (on the limit meshes: child rays, parent signed distances; the body's clay fields for the coxae)
        Q_ = {nm: MeshQ(s_['lim_V'], s_['lim_F']) for nm, s_ in segs.items()}
        P_ = chain['pos']
        sl = []
        for par, chd in SLEEVE_JOINTS:
            graft = chd in ('coxa', 'tibia', 'tarsus_1')
            if chd == 'coxa':
                body = clay['body']['pronotum' if pair == 'fore' else 'venter']
                cV = segs['coxa']['lim_V']
                expo = cV[body(cV) > 0.0]
                cen = segs['coxa']['spine'][0].mean(0)
                axis = _unit(expo.mean(0) - cen)
                s_ = sleeve(f'{pair} coxal cavity', cen, axis, body, Q_['coxa'], graft=True)
            elif chd == 'claw':
                o = P_[f'claw_{c}_L']
                ta = _unit(segs['claw_a']['spine'][0][1] - segs['claw_a']['spine'][0][0])
                tb = _unit(segs['claw_b']['spine'][0][1] - segs['claw_b']['spine'][0][0])
                s_ = sleeve(f'{pair} claws', o, _unit(ta + tb), Q_['tarsus_5'].sdf, Q_['claw_a'], child_extra=[Q_['claw_b']])
            else:
                sp_P = segs[chd]['spine'][0]
                s_ = sleeve(f'{pair} {par}-{chd}', sp_P[0], _unit(sp_P[1] - sp_P[0]), Q_[par].sdf, Q_[chd], graft=graft)
            s_.update(parent=par, child=chd, parent_joint=(('pronotum' if pair == 'fore' else 'body') if par == 'body'
                                                            else segs[par]['joint'] + '_L'),
                      child_joint=(f'claw_{c}_L' if chd == 'claw' else segs[chd]['joint'] + '_L'))
            sl.append(s_)
        out['sleeves'][pair] = sl
        # ---- the graft rings' records (the coxa, knee and ankle sleeves' proximal rings), both sides; the tibia's root (M2)
        out['rings'][pair], out['rings_R'][pair] = graft_records(segs, sl, pair, chain, spec, key, sk)
        out['tibia_root'][pair] = tibia_root(sl)
        rings = out['rings'][pair]
        log(f'[legs] {pair}: sleeves {len(sl)} (graft K: ' + ', '.join(f'{k} {v["K"]}' for k, v in rings.items()) +
            f'), {time.time() - t0:.0f}s')
    if cache:
        save_legs(out, path)
    return out


def save_legs(out, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Z = {}
    meta = dict(key=out['key'], pairs={}, sleeves={}, rings=out['rings'], rings_R=out['rings_R'], tibia_root=out['tibia_root'])
    for pair, segs in out['pairs'].items():
        meta['pairs'][pair] = {}
        for nm, s_ in segs.items():
            p = f'{pair}__{nm}__'
            for k in ('V', 'Q', 'ctrl', 'lim_V', 'lim_F'):
                Z[p + k] = s_[k]
            Z[p + 'sp'] = np.array(list(s_['sharp'].keys()), np.int64).reshape(-1, 2)
            Z[p + 'sv'] = np.array(list(s_['sharp'].values()), np.float64)
            Z[p + 'spineP'], Z[p + 'spineN'] = s_['spine']
            meta['pairs'][pair][nm] = dict(kind=s_['kind'], joint=s_['joint'], parent=s_['parent'], features=s_['features'],
                                           res=float(s_['res']), copy_of=s_.get('copy_of'))
            if s_.get('copy_of'):
                Z[p + 'copyR'], Z[p + 'copyO'] = s_['copy_R'], s_['copy_origin']
        meta['sleeves'][pair] = []
        for i, s_ in enumerate(out['sleeves'][pair]):
            p = f'{pair}__sleeve{i}__'
            Z[p + 'V'], Z[p + 'Q'], Z[p + 'X'], Z[p + 'axis'] = s_['V'], s_['Q'], s_['X'], s_['axis']
            Z[p + 'radii'] = np.array(s_['radii'])
            meta['sleeves'][pair].append({k: (v if not isinstance(v, np.ndarray) else v.tolist()) for k, v in s_.items()
                                          if k in ('name', 'K', 'step', 'step_in', 'sag_texels', 'graft', 'parent', 'child',
                                                   'parent_joint', 'child_joint')} |
                                         dict(frame={k: v.tolist() for k, v in s_['frame'].items()}))
    Z['meta'] = np.array(json.dumps(meta))
    np.savez_compressed(path, **Z)


def load_legs(path, key=None):
    Z = np.load(path, allow_pickle=False)
    meta = json.loads(str(Z['meta']))
    out = dict(pairs={}, sleeves={}, rings=meta['rings'], rings_R=meta.get('rings_R', {}), tibia_root=meta.get('tibia_root', {}),
               key=meta['key'], path=path)
    for pair, segs in meta['pairs'].items():
        out['pairs'][pair] = {}
        for nm, m in segs.items():
            p = f'{pair}__{nm}__'
            s_ = dict(m, V=Z[p + 'V'], Q=Z[p + 'Q'], ctrl=Z[p + 'ctrl'], lim_V=Z[p + 'lim_V'], lim_F=Z[p + 'lim_F'],
                      sharp={(int(a), int(b)): float(v) for (a, b), v in zip(Z[p + 'sp'], Z[p + 'sv'])},
                      spine=(Z[p + 'spineP'], Z[p + 'spineN']))
            if m.get('copy_of'):
                s_['copy_R'], s_['copy_origin'] = Z[p + 'copyR'], Z[p + 'copyO']
            out['pairs'][pair][nm] = s_
        out['sleeves'][pair] = []
        for i, m in enumerate(meta['sleeves'][pair]):
            p = f'{pair}__sleeve{i}__'
            out['sleeves'][pair].append(dict(m, V=Z[p + 'V'], Q=Z[p + 'Q'], X=Z[p + 'X'], axis=Z[p + 'axis'],
                                             radii=list(Z[p + 'radii']),
                                             frame={k: np.array(v) for k, v in m['frame'].items()}))
    return out


def mirror_legs(legs):
    """the RIGHT legs: every left segment, sleeve and ring record mirrored (p_R = M p_L, the quads reversed, the vertex numbering
    kept: the right side's UVs stack on the left's through the tangent sign); returns {pair: {seg: dict(V, Q, lim_V, lim_F,
    sharp)}} and the sleeves and records likewise"""
    R = dict(pairs={}, sleeves={}, rings={})
    for pair, segs in legs['pairs'].items():
        R['pairs'][pair] = {}
        for nm, s_ in segs.items():
            V, Q = mirror_mesh(s_['V'], s_['Q'])
            lV, lF = mirror_mesh(s_['lim_V'], s_['lim_F'])
            R['pairs'][pair][nm] = dict(s_, V=V, Q=Q, lim_V=lV, lim_F=lF, ctrl=s_['ctrl'] * np.array([-1.0, 1.0, 1.0]),
                                        joint=s_['joint'], side='R')
        R['sleeves'][pair] = []
        for s_ in legs['sleeves'][pair]:
            V, Q = mirror_mesh(s_['V'], s_['Q'])
            R['sleeves'][pair].append(dict(s_, V=V, Q=Q, X=s_['X'] * np.array([-1.0, 1.0, 1.0]),
                                           axis=s_['axis'] * np.array([-1.0, 1.0, 1.0])))
        R['rings'][pair] = (legs['rings_R'][pair] if legs.get('rings_R', {}).get(pair)
                            else {cut: mirror_record(r) for cut, r in legs['rings'][pair].items()})
    return R
