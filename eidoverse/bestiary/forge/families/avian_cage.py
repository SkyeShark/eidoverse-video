"""The AVIAN family's designed CAGE (HAWK_PLAN.md §4.6, §8.1): the skin's low, all quads, built on the D1.3 clay
(avian_body.skin_program) with the donor organs' graft rings as loops of it (CROSSBREED §7.1: K = 0 mod 4, vertex 0
on the ring frame's X, planar, no pole within +-h, a frame per ring recorded).

CONVENTIONS: life mm in the world (the chain's frame: +z forward, +y up, +x the bird's left). Every ring is cast in its
own plane: N_RAYS rays from a point inside the clay at even angles about the frame's Z (the distal direction), each to
the clay's zero set (sdf.Program.project), then resampled to K points by arc length from the ray at angle 0 (the
frame's X): so a ring is planar by construction, its vertex 0 on X, its points spaced evenly round the section (a flat
wing section's trailing edge gets its share). Rings run right-handed about Z (X, then Y = Z x X).

THE DESIGN (one design, D1.3; the plan's numbers [E] where it gave them):
  spine   one K 32 tube from the tail root's end through the trunk, the neck and the head to the face, cast on the
          LIMBLESS body (no wing or leg ray can run out along a limb). K 32 for the trunk (the plan's K 48 was sized on
          the plumaged 0.13 m width; the skin is about 0.09 m wide: 32 columns give the plan's 9 mm), the neck and the
          head (the plan's K 32 / K 48). Station steps: trunk 7.5 mm, neck 4, head 3.5 [E: square quads].
  tail    the rump's end ring reduces 32 -> 16 (loft.reduce_ring: 4 -> 2 units), three K 16 rings over the tail root,
          the TAIL ring (§8.1: K 16, h 5) on the second, a 4 x 4 cap at the pygostyle
  wing    a 4 (round) x 8 (along) block cut on each shoulder (ports.cut: a 24 loop) bridged to a K 24 tube cast along the
          wing's bones on the wing's own clay (its SHELL + arm cones), the WING ring (§8.1: K 24, h 8) the tube's first;
          the digit tip closed by an 8 x 4 cap (the section is flat)
  leg     a 6 x 6 block on each flank where the thigh leaves the trunk (a 24 loop) bridged to a K 24 thigh tube, a
          24 -> 16 strip (reduce_mixed: 4 -> 2 and 2 -> 2 units alternating: all quads), K 16 over the drumstick, the
          ANKLE ring at the intertarsal joint (§8.1: K 16, h 4) and the FOOT ring above the trochleae (K 16, h 3) on
          the tarsus, then a 4 x 4 cap (the toes are the next round: plan §4.6's K 12 toe lofts from a foot pad)
  face    heads/raptor_cage.face: the spine's last ring (the feather line, the plan's 32 face ring) bridged to a
          figure loop that splits into the UPPER bill's ring (K 24) and the LOWER's (K 16) with a two-row gape strip
          of 6 quads between them (the mouth's commissures at its ends): both rings stay open (the keratin shells sink
          into them: SOCKET seams, §8.1)
"""
import numpy as np

from .. import loft as LF
from .. import ports as PT
from .. import sdf
from ..mesh import QuadMesh
from . import avian as AV
from . import avian_body as AB

MM = 1e-3
N_RAYS = 256
SPINE_K, WING_K, LEG_K, ANKLE_K, TAIL_K = 32, 24, 24, 16, 16
SPINE_TURN = 24.0                     # mm: the Gaussian over the spine's tangents (10: the ring planes crossed inside
#                                       the tube where the trunk's axis turns 60 deg into the neck: folded quads)
MAX_MOVE = 4.0                        # mm: the most project() moves a vertex along its normal
RELAX_ITERS, RELAX_LAM = 8, 0.5       # project()'s tangential relaxation on the skin (D1.3b)
PAIR_TOL = 0.06                       # mm: project()'s mirror pairing. The limbs are the left's mirror to the bit and
#                                       the spine's rings are cast symmetric; the head's ports (eye and nostril rings)
#                                       are cast per side, their frames read off the surface: up to 0.040 mm apart
#                                       (D1.3c, 108 vertices). Under the cage's least spacing (the nostril's pit, 0.2)
LEG_TURN = 22.0                      # mm: the Gaussian over the leg path's tangents
WING_CAP_DOME = 2.0                   # mm: the digit tip's 8 x 4 cap lifted along the tube (loft.cap's dome; D1.3c fix 1)
WING_START = 36.0                   # mm past the glenoid: the wing tube's first ring (the WING record)
STEP = dict(trunk=7.5, neck=4.0, head=3.5, face=2.5, wing=6.0, leg=5.0, tail=6.0, toe=4.0)
FACE_STOP = 4.5                      # mm behind the keratin's margin: the spine's last ring (on the cere). D1.3c fix 1:
#                                       3 -> 4.5: with the lower bill's keratin re-read from x 1378 (its margin 0.9 mm
#                                       farther back, 3.5 mm tall) the last ring's chin ran over the lower's margin: 4
#                                       quads folded 159-172 deg at the mouth's corners (scratch f09_facesweep.py:
#                                       4.5 = no fold over 60 deg in the head, least corner 9.1 deg, none flipped)
FACE_LEN = 9.0                        # mm: the last stretch of the head (the cere, the nostril's rows) at STEP['face']
RINGS = dict(wing=dict(K=24, h=8.0), foot=dict(K=16, h=3.0), ankle=dict(K=16, h=4.0), tail=dict(K=16, h=5.0),
             beak_upper=dict(K=24, h=2.0), beak_lower=dict(K=16, h=2.0), eye=dict(K=24, h=2.0))
# D1.3b's head ports and feet (plan §4.6: the lid rings 24, the nostril's 8-ring, toes, pads):
EYE_BLOCK = 3                         # the eye's port: the (2r x 2r) quad block round the vertex nearest the opening's
#                                       centre (6 x 6: a 24 loop, about 21 x 24 mm on the head's rings)
EYE_RHO = (0.4, 4.0)                 # mm: the lid margin ring's radius inside the opening (r_open - this), the eye
#                                       SOCKET ring's radius (on the eye's cap: planar by construction)
HUB_AT = (11.0, -2.5, 2.0, 6.0)        # mm along the tarsus from the foot joint (+ = down): the K 16 tube's end, the
#                                       hub's three K 24 rings (the toe ports' rows: the middle one at the toes' axis)
NOSTRIL_BACK = -1.0                   # mm: the nostril's port block centred this far behind the pit (head_ports; - =
#                                       ahead: the rim's front stood past the block's front edge and its quad folded)
NOSTRIL_RIM = 0.6                    # mm the nostril's 8-ring stands inside the pit's oval (SPEC head.nostril; 0.15:
#                                       on restart 2's cere the ring's front-lower point met the 2 x 2 block's edge
#                                       within 0.17 mm, a 4 deg corner; 0.45 -> 6.7 deg, 0.6 -> 11.1, scratch sweep)
NOSTRIL_DISH_RING = 0.65              # D1.3c: the nostril's RIM ring, this share of the dish's oval (on its wall, about
#                                       0.4 mm down; the whole oval, 5.2 x 3.0 turned 18 deg, does not fit the 2 x 2
#                                       block's 4.2 x 5.1 mm with room for its quads)
NOSTRIL_PIT = dict(at=(-0.5, 0.2), semi=(1.0, 0.4))
#                                       mm, in the dish's frame (along its long axis, toward its upper side): the PIT
#                                       ring's centre and half axes, inside the rim ring's footprint and the slot's
#                                       3.6 x 1.5 mouth; cast along the cere's normal into the slot
TOE_K, HUB_K = 8, 24                # the toes' rings (the axolotl's digit K 8: 3 dorsal, 1 side, 3 plantar, 1 side;
#                                       the plan's 12 would need a 48 hub from the K 16 tarsus); the foot's hub
HUB_PAD = (9.0, 7.5, 11.0)            # [E] mm: the hub's clay for its casts: the ball of the foot round the joint
#                                       (half widths x, y, z: the trochleae 15.1 mm across plus the pads)


def _u(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def frame(z, ref):
    """the ring frame: Z the distal direction, X the reference projected off it, Y = Z x X (columns X, Y, Z)"""
    Z = _u(z)
    X = _u(np.asarray(ref, float) - Z * (np.asarray(ref, float) @ Z))
    return np.column_stack([X, np.cross(Z, X), Z])


def _cast(prog, O, D, maxd):
    """rays from O (mm) along D to prog's zero set (sdf.Program.project); a ray the sphere trace leaves short (status
    != 0: inside the head, the PSWEEPs' bound is a few mm where the surface is 17 mm away, and 96 steps stop short:
    D1.3b's ring 49 had two rays fall back near its centre and crumpled) is found again by sampling the ray every
    0.2 mm and bisecting the first sign change. Returns (n, 3) metres and the status (0 = found)"""
    P, st = prog.project(np.tile(np.asarray(O, float) * MM, (len(D), 1)), D, maxd=maxd)
    bad = np.nonzero(st != 0)[0]
    if len(bad):
        t = np.arange(0.0, maxd, 0.2 * MM)
        for i in bad:
            Q = np.asarray(O, float)[None] * MM + t[:, None] * D[i][None]
            f = prog.eval(Q)
            j = np.nonzero((f[1:] > 0) != (f[0] > 0))[0]
            if not len(j):
                continue
            lo, hi = t[j[0]], t[j[0] + 1]
            for _ in range(30):
                mid = 0.5 * (lo + hi)
                fm = prog.eval((np.asarray(O, float) * MM + mid * D[i])[None])[0]
                if (fm > 0) == (f[0] > 0):
                    lo = mid
                else:
                    hi = mid
            P[i] = np.asarray(O, float) * MM + 0.5 * (lo + hi) * D[i]
            st[i] = 0
    return P, st


def cast_ring(prog, O, Fr, K, rmax=0.12, sym=False, recentre=True):
    """a planar ring of K points (module docstring); sym: mirror-symmetric about x = 0 (the spine's rings, whose
    plane contains the world x axis); recentre: cast again from the first cast's centroid, so vertex 0 lies on X as
    seen from the ring's own centre (the frame's origin a record carries; D1.3: cast from the path point, vertex 0
    sat 1.5-2.3 deg off X from the centre). Returns (K, 3) mm and the casts' ok fraction"""
    a = np.linspace(0.0, 2 * np.pi, N_RAYS, endpoint=False)
    D = np.cos(a)[:, None] * Fr[:, 0][None] + np.sin(a)[:, None] * Fr[:, 1][None]
    P, st = _cast(prog, O, D, rmax)
    P = P / MM
    ring = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ring, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], K, endpoint=False)
    R = np.stack([np.interp(t, s, ring[:, k]) for k in range(3)], 1)
    if sym:
        M = R[(K // 2 - np.arange(K)) % K] * np.array([-1.0, 1.0, 1.0])
        R = 0.5 * (R + M)
    if recentre and (st == 0).all():
        # from the K points' own centroid (the record's centre), twice: it converges in one or two
        for _ in range(2):
            c = R.mean(0)
            c = c - Fr[:, 2] * ((c - np.asarray(O, float)) @ Fr[:, 2])      # stay in the plane
            if prog.eval(c[None] * MM)[0] >= 0:
                break
            R, okr = cast_ring(prog, c, Fr, K, rmax, sym, recentre=False)
            O = c
    return R, float((st == 0).mean())


def cast_ring_mouth(prog, O, Fr, K, pin, w, k_mouth=(30, 18)):
    """a spine ring (K 32, mirror-symmetric) whose columns k_mouth (left, right) lie on the mouth line: the dense cast
    from O, the left mouth at the ray toward `pin` (its angle in the ring's plane), the right its mirror; the arc over
    the top shared evenly by the columns between them, the arc under the jaw likewise; w in [0, 1] blends these
    stations with the even ones (cast_ring's), so the head's columns ease into the neck's behind the rictus.
    (D1.3b: the mouth line is one edge loop of the head from the bill to under the eye, so the jaw can open along it
    and the bake's gape lies on a column)"""
    a = np.linspace(0.0, 2 * np.pi, N_RAYS, endpoint=False)
    D = np.cos(a)[:, None] * Fr[:, 0][None] + np.sin(a)[:, None] * Fr[:, 1][None]
    P, st = _cast(prog, O, D, 0.12)
    P = P / MM
    ring = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ring, axis=0), axis=1))])
    L = s[-1]
    q = np.asarray(pin, float) - np.asarray(O, float)
    am = np.arctan2(q @ Fr[:, 1], q @ Fr[:, 0]) % (2 * np.pi)
    a_c = np.concatenate([a, [2 * np.pi]])
    sm = float(np.interp(am, a_c, s))                                     # the left mouth's arc station
    # its mirror's station, read at the mirrored RAY (theta -> pi - theta). D1.3c fix 2: this was (L / 2 - sm), which
    # is the mirror only when the arc over the top (angle 0 -> pi) is half the ring. On the face's last rings the
    # origin sits high in the section (3 mm under the cere, 12 mm over the jaw): the top arc is far shorter, the
    # "right mouth" landed under the jaw, and the mirror average below then dragged BOTH mouth columns down off the
    # crease: 2.39 mm under it on the last ring but one, 3.59 mm on the last (the pin's ray at 310.3 deg, column 30 at
    # 293.5; scratch d13c_fix2/mc.py), so the bridge's corner quads straddled the lips (fold 52-60 deg, and it moved
    # with every change of the cere's or the nostril's arc length: fix 1's 56-68 deg)
    smr = float(np.interp((np.pi - am) % (2 * np.pi), a_c, s))
    kl, kr = k_mouth
    top = (smr - sm) % L                                                  # the arc over the top, left -> right
    n_top = (kr - kl) % K
    t_pin = np.empty(K)
    for j in range(n_top + 1):
        t_pin[(kl + j) % K] = sm + j * top / n_top
    n_bot = K - n_top
    for j in range(1, n_bot):
        t_pin[(kr + j) % K] = smr + j * (L - top) / n_bot
    t_even = np.arange(K) * L / K
    t_pin = t_even + ((t_pin - t_even + 0.5 * L) % L - 0.5 * L)          # each nearest its even station
    t = (1.0 - w) * t_even + w * t_pin
    R = np.stack([np.interp(t % L, s, ring[:, k]) for k in range(3)], 1)
    M = R[(K // 2 - np.arange(K)) % K] * np.array([-1.0, 1.0, 1.0])
    return 0.5 * (R + M), float((st == 0).mean())


def _mouth_pin(G, O, Z, fade=7.0):
    """the mouth line G (rictus -> the tomium's foot) where it crosses the plane (O, Z), and the pinning weight: 1 in
    front of the rictus, fading over `fade` mm behind it; ahead of the line's front end, its end point"""
    d = (G - O) @ Z
    for i in range(len(G) - 1):
        if d[i] <= 0.0 <= d[i + 1] or d[i] >= 0.0 >= d[i + 1]:
            f = d[i] / (d[i] - d[i + 1]) if d[i] != d[i + 1] else 0.0
            return G[i] + f * (G[i + 1] - G[i]), 1.0
    if (d > 0).all():                                                     # the ring is behind the rictus
        return G[0] - Z * d[0], float(np.clip(1.0 - d[0] / fade, 0.0, 1.0))
    return G[-1] - Z * d[-1], 1.0


class Cage:
    """a growing quad mesh (life mm) with its ring records"""

    def __init__(self):
        self.V, self.Q, self.records, self.notes = [], [], {}, []
        self.keep = set()           # vertices project()'s relaxation never slides (the mouth's columns, the lid, the
        #                             nostril's rim, the beak's rings: features placed on purpose; D1.3b)
        self.cuts = {}              # the UV islands' cut loops (vertex id loops; species/red_tailed_hawk_uv.py)
        self.terms = {}             # closed ends a seam runs to (the wing tips, the toe tips, the tail's cap)

    def add(self, P):
        i0 = len(self.V)
        self.V += [np.asarray(p, float) for p in np.asarray(P, float).reshape(-1, 3)]
        return np.arange(i0, i0 + len(np.asarray(P).reshape(-1, 3)))

    def band(self, A, B):
        """quads between two rings of equal K, index for index (A then B along Z)"""
        K = len(A)
        for k in range(K):
            k1 = (k + 1) % K
            self.Q.append([A[k], A[k1], B[k1], B[k]])

    def mesh(self):
        return QuadMesh(np.array(self.V), np.array(self.Q, np.int64))

    def set_mesh(self, m):
        self.V = [v for v in m.V]
        self.Q = [list(q) for q in m.Q]

    def record(self, name, ids, Fr, pinned, native, **kw):
        P = np.array([self.V[i] for i in ids])
        c = P.mean(0)
        r = float(np.linalg.norm(P - c, axis=1).mean())
        n = np.linalg.svd(P - c)[2][2]
        plan = RINGS[name.rsplit('_', 1)[0] if name.endswith(('_L', '_R')) else name]
        self.records[name] = dict(ids=np.asarray(ids), frame=Fr, centre=c, r_mean=r, K=len(ids), K_plan=plan['K'],
                                  h=plan['h'], planarity=float(np.abs((P - c) @ n).max() / r), pinned=pinned,
                                  native=native, **kw)


def reduce_mixed(cage, ring, inner_pos, units):
    """a K -> K' strip after `ring` (the far ring of the tube it ends, its faces using its edges backward, as
    loft.reduce_ring): units, a string over the ring's edges in order: 'R' a 4 -> 2 unit (one middle vertex, four
    quads: loft.reduce_ring's), 'S' a 2 -> 2 unit (two quads straight across). inner_pos: the inner ring's positions,
    one per inner vertex in order. Returns the inner ring's ids. (24 -> 16: 'RS' x 4; loft.py is shared, so the mixed
    strip lives here)"""
    R = list(ring)
    K = len(R)
    assert sum(4 if u == 'R' else 2 for u in units) == K
    K2 = sum(2 for _ in units)
    inner = cage.add(inner_pos)
    assert len(inner) == K2
    o, i = 0, 0
    for u in units:
        if u == 'R':
            oo = [R[(o + j) % K] for j in range(5)]
            i0, i1, i2 = inner[i % K2], inner[(i + 1) % K2], inner[(i + 2) % K2]
            m = cage.add([0.5 * np.asarray(cage.V[oo[2]]) + 0.5 * np.asarray(cage.V[i1])])[0]
            cage.Q += [[oo[0], oo[1], m, i0], [oo[1], oo[2], oo[3], m], [oo[3], oo[4], i2, m], [i0, m, i2, i1]]
            o += 4
        else:
            oo = [R[(o + j) % K] for j in range(3)]
            i0, i1, i2 = inner[i % K2], inner[(i + 1) % K2], inner[(i + 2) % K2]
            cage.Q += [[oo[0], oo[1], i1, i0], [oo[1], oo[2], i2, i1]]
            o += 2
        i += 2
    return inner


def orient(Q):
    """make the winding consistent across shared edges (propagation from face 0); returns Q and the number flipped"""
    Q = [list(q) for q in Q]
    from collections import defaultdict, deque
    ed = defaultdict(list)
    for f, q in enumerate(Q):
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            ed[(min(a, b), max(a, b))].append(f)
    seen = [False] * len(Q)
    flips = 0
    for s in range(len(Q)):
        if seen[s]:
            continue
        seen[s] = True
        dq = deque([s])
        while dq:
            f = dq.popleft()
            q = Q[f]
            dirs = {(q[k], q[(k + 1) % 4]) for k in range(4)}
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                for g in ed[(min(a, b), max(a, b))]:
                    if g == f or seen[g]:
                        continue
                    qg = Q[g]
                    gd = {(qg[j], qg[(j + 1) % 4]) for j in range(4)}
                    if (a, b) in gd:                        # same direction: g must flip
                        Q[g] = qg[::-1]
                        flips += 1
                    seen[g] = True
                    dq.append(g)
    return Q, flips


# --------------------------------------------------------------------------------------------- the path
def _resample(P, step):
    P = np.asarray(P, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    n = max(int(round(s[-1] / step)), 1) + 1
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(3)], 1)


def _tangents(P, sigma_mm):
    from scipy.ndimage import gaussian_filter1d
    T = np.gradient(P, axis=0)
    ds = np.linalg.norm(np.diff(P, axis=0), axis=1).mean()
    return _u(gaussian_filter1d(T, max(sigma_mm / ds, 0.5), axis=0, mode='nearest'))


def spine_path(spec, chain, info):
    """the spine's stations (rump -> face) as (points, segment label) at STEP spacing per segment"""
    tr = info['tail_root']['C']
    tk = info['trunk']['C']
    tz = info['trunk']['table'][:, 0]
    nk = info['neck']['C']
    hd = info['head']['centre']
    fwd = info['head']['fwd']
    c0, T0 = info['head']['collar']
    # the tail root runs z -96 .. -44 (flight); the trunk from -44 (its rows beyond the tail's end) to 78
    zt = info['tail_root']['table'][:, 0]
    seg_tail = tr[(zt <= -44.0) & (zt >= -62.0)]                 # behind -62 is the K 16 tail root's (build)
    seg_trunk = tk[(tz > -44.0) & (tz <= 78.0)]
    seg_neck = nk[1:]
    # the head: its centreline from where it passes the neck's end, to the collar's back (the face ring there)
    proj_end = (seg_neck[-1] - hd[0]) @ fwd
    # D1.3b: the head's rings run onto the CERE, FACE_STOP behind the keratin's margin (D1.3 stopped 13 mm short and
    # bridged the bare lores and cere with two interpolated rings: 10 flipped quads, no rows for the nostril)
    p_end = c0 - T0 * FACE_STOP
    stop = (p_end - hd[0]) @ fwd
    hp = (hd - hd[0]) @ fwd
    seg_head = hd[(hp > proj_end + 2.0) & (hp < stop - 1.0)]
    seg_head = np.vstack([seg_head, seg_head[-1] + np.linspace(0.0, 1.0, 5)[1:, None] * (p_end - seg_head[-1])[None]])
    hp2 = (seg_head - hd[0]) @ fwd
    seg_face = seg_head[hp2 > stop - FACE_LEN]
    seg_head = seg_head[hp2 <= stop - FACE_LEN]
    out, lab = [], []
    for nm, seg in (('tail', seg_tail), ('trunk', seg_trunk), ('neck', seg_neck), ('head', seg_head),
                    ('face', seg_face)):
        out.append(seg)
        lab += [nm] * len(seg)
    P = np.vstack(out)
    from scipy.ndimage import gaussian_filter1d
    ds = np.linalg.norm(np.diff(P, axis=0), axis=1)
    keep = np.concatenate([[True], ds > 1e-6])
    P, lab = P[keep], list(np.array(lab)[keep])
    Ps = gaussian_filter1d(P, 3.0, axis=0, mode='nearest')
    Ps[0], Ps[-1] = P[0], P[-1]
    # stations: walk the path, the step by the segment
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Ps, axis=0), axis=1))])
    st, labs = [0.0], [lab[0]]
    while st[-1] < s[-1] - 1.0:
        i = min(int(np.searchsorted(s, st[-1], side='right')) - 1, len(lab) - 1)
        st.append(min(st[-1] + STEP[lab[i]], s[-1]))
        labs.append(lab[min(int(np.searchsorted(s, st[-1], side='right')) - 1, len(lab) - 1)])
    pts = np.stack([np.interp(st, s, Ps[:, k]) for k in range(3)], 1)
    return pts, labs


# --------------------------------------------------------------------------------------------- the build
def limb_prog(spec, chain, kind, side):
    """the clay of one limb alone (the casts of its rings never run into the trunk)"""
    p = sdf.Program()
    if kind == 'wing':
        V, F, H, _ = AB.wing_patch(spec, chain)
        if side == 'R':
            V, F = V * np.array([-1.0, 1.0, 1.0]), F[:, ::-1]
        p.begin_group(op=sdf.UNION, k=9.0 * MM)
        p.shell(V * MM, F, H * MM, continuous=True, name=f'wing_skin_{side}')
        AB._arm_cones(p, chain, side, k=3.0)
        p.end_group()
    else:
        p.begin_group(op=sdf.UNION, k=6.0 * MM)
        AB._leg_members(p, chain, side, k=4.0)
        p.end_group()
    return p


def cut_block(cg, v, r):
    """cut the (2r x 2r) quad block round vertex v (every face whose corners all lie within r face-steps of v: the
    Chebyshev ball on the quad grid) and return the hole's loop (8 r vertex ids, boundary order). Asserts the block is
    a clean grid (its (2r)^2 faces, valence 4 inside)"""
    from collections import defaultdict
    cg.Q, _ = orient(cg.Q)                  # boundary_loop walks the winding: strips added either way are made to agree
    vf = defaultdict(list)
    for f, q in enumerate(cg.Q):
        for a in q:
            vf[int(a)].append(f)
    dist = {int(v): 0}
    front = [int(v)]
    for d in range(1, r + 1):
        nxt = []
        for a in front:
            for f in vf[a]:
                for b in cg.Q[f]:
                    if int(b) not in dist:
                        dist[int(b)] = d
                        nxt.append(int(b))
        front = nxt
    F = [f for f, q in enumerate(cg.Q) if all(dist.get(int(a), r + 1) <= r for a in q)]
    assert len(F) == (2 * r) ** 2, f'block round {v}: {len(F)} faces, want {(2 * r) ** 2}'
    inner = [a for a, d in dist.items() if d < r]
    assert all(len(vf[a]) == 4 for a in inner), f'block round {v}: a pole inside'
    m = cg.mesh()
    keep = np.ones(len(m.Q), bool)
    keep[F] = False
    m = QuadMesh(m.V, m.Q[keep])
    ring_v = {a for a, d in dist.items() if d == r}
    cand = [l for l in LF.boundary_loop(m) if set(int(x) for x in l) == ring_v]
    assert len(cand) == 1, f'block round {v}: {len(cand)} loops'
    cg.set_mesh(m)
    return np.array(cand[0])


def nearest_vertex(cg, p, among=None):
    V = np.array(cg.V)
    ids = np.arange(len(V)) if among is None else np.asarray(among)
    return int(ids[np.argmin(np.linalg.norm(V[ids] - np.asarray(p, float), axis=1))])


def reduce_mixed_existing(cage, ring, inner, units):
    """reduce_mixed's strip between two EXISTING rings (the outer, K, and the inner, K'); only the 'R' units' middle
    vertices are new. The foot's hub widens the K 16 tarsus to K 24 this way (the inner ring is the tube's last)"""
    R = list(ring)
    K = len(R)
    K2 = len(inner)
    assert sum(4 if u == 'R' else 2 for u in units) == K and 2 * len(units) == K2
    o, i = 0, 0
    for u in units:
        if u == 'R':
            oo = [R[(o + j) % K] for j in range(5)]
            i0, i1, i2 = inner[i % K2], inner[(i + 1) % K2], inner[(i + 2) % K2]
            m = cage.add([0.5 * np.asarray(cage.V[oo[2]]) + 0.5 * np.asarray(cage.V[i1])])[0]
            cage.Q += [[oo[0], oo[1], m, i0], [oo[1], oo[2], oo[3], m], [oo[3], oo[4], i2, m], [i0, m, i2, i1]]
            o += 4
        else:
            oo = [R[(o + j) % K] for j in range(3)]
            i0, i1, i2 = inner[i % K2], inner[(i + 1) % K2], inner[(i + 2) % K2]
            cage.Q += [[oo[0], oo[1], i1, i0], [oo[1], oo[2], i2, i1]]
            o += 2
        i += 2


def _toe_prog(chain, t, side):
    """one toe's clay alone (avian_body._leg_members' toe members), for its rings' casts"""
    P = chain['pos']
    sg = 1.0 if side == 'L' else -1.0
    foot = np.asarray(P[f'foot_{side}'], float)
    g = chain['toes'][t]
    pts = [np.asarray(p, float) * np.array([sg, 1.0, 1.0]) for p in g['pts']]
    ra, rb = AB.THIGH['toe']
    lift = np.array([0.0, -(AV.PAD - ra) * 0.5 + 0.5, 0.0])
    n = len(pts)
    p = sdf.Program()
    p.begin_group(op=sdf.UNION, k=2.0 * MM)
    p.roundcone(foot * MM, (pts[0] + lift) * MM, AB.THIGH['tarsus'][1] * MM, ra * MM, op=sdf.UNION, k=2.0 * MM)
    for i in range(n - 1):
        r0 = ra + (rb - ra) * i / max(n - 1, 1)
        r1 = ra + (rb - ra) * (i + 1) / max(n - 1, 1)
        p.roundcone((pts[i] + lift) * MM, (pts[i + 1] + lift) * MM, r0 * MM, r1 * MM, op=sdf.UNION, k=1.0 * MM)
    p.end_group()
    return p, [q + lift for q in pts]


def foot_hub(cg, spec, chain, side, last, log=print):
    """the FOOT (plan §4.6's toes and pads, D1.3b): the K 16 tarsus's last ring `last` widens to a K 24 hub (a 16 -> 24
    strip, 'RS' x 4) over three rings round the ball of the foot (HUB_AT; cast on the tarsus + HUB_PAD alone, so the
    toes' bases never pull the rings into flat plates as in D1.3), the sole a 6 x 6 cap; four 2 x 2 ports on the
    hub's middle ring (an 8 loop each), each bridged by one ring to its toe: K 8 rings every STEP['toe'] mm along the
    toe's phalanges to the claw's bed, a 2 x 2 cap (the talon's shell sinks into it). The front toes' ports stand at
    least three columns apart (45 deg: two 2 x 2 blocks must not share a vertex), so d2 and d4 leave the hub at
    +-45 deg off d3 and turn to their own yaws (-25, +40) within the bridge"""
    P = chain['pos']
    sg = 1.0 if side == 'L' else -1.0
    ank = np.asarray(P[f'tarsometatarsus_{side}'], float)
    foot = np.asarray(P[f'foot_{side}'], float)
    u = _u(foot - ank)
    side_ax = np.array([sg, 0.0, 0.0])
    hub = sdf.Program()
    hub.begin_group(op=sdf.UNION, k=4.0 * MM)
    hub.roundcone(ank * MM, foot * MM, AB.THIGH['tarsus'][0] * MM, AB.THIGH['tarsus'][1] * MM, op=sdf.UNION, k=0.0)
    hub.ellipsoid((foot + np.array([0.0, HUB_PAD[1] - foot[1], 0.0])) * MM, np.array(HUB_PAD) * MM, op=sdf.UNION,
                  k=4.0 * MM)
    hub.end_group()
    Fr = frame(u, side_ax)
    hr = []
    for j, a in enumerate(HUB_AT[1:]):
        R, ok = cast_ring(hub, foot + u * a, Fr, HUB_K)
        if j == 0:
            # the 16 -> 24 strip: the new K 24 ring rolled so its anchors meet the tube's last ring
            anc = _inner_anchor('RS' * 4)
            last_p = np.array([cg.V[v] for v in last])
            best = min(range(HUB_K), key=lambda s_: float(np.linalg.norm(np.roll(R, -s_, axis=0)[anc] - last_p,
                                                                          axis=1).sum()))
            ids = cg.add(np.roll(R, -best, axis=0))
            reduce_mixed_existing(cg, ids, list(last), 'RS' * 4)
        else:
            ids = cg.add(np.roll(R, -best, axis=0))
            cg.band(hr[-1], ids)
        hr.append(ids)
    m = cg.mesh()
    m, _ = LF.cap(m, hr[-1], u, shape=(6, 6))
    cg.set_mesh(m)
    # the toes' ports on the middle ring
    mid = np.array([cg.V[v] for v in hr[1]])
    c_mid = mid.mean(0)
    ang = lambda q: np.arctan2((q - c_mid) @ Fr[:, 1], (q - c_mid) @ Fr[:, 0])
    a_v = np.array([ang(q) for q in mid])
    toes = chain['toes']
    dirs = {t: _u(np.asarray(g['dir'], float) * np.array([sg, 1.0, 1.0])) for t, g in toes.items()}
    col = {t: int(np.argmin(np.abs(np.angle(np.exp(1j * (a_v - ang(c_mid + dirs[t]))))))) for t in toes}
    # d2 and d4 at least 3 columns from d3, on their own sides
    for t in ('d2', 'd4'):
        dk = (col[t] - col['d3'] + HUB_K // 2) % HUB_K - HUB_K // 2
        if abs(dk) < 3:
            da = float(np.angle(np.exp(1j * (ang(c_mid + dirs[t]) - ang(c_mid + dirs['d3'])))))
            col[t] = (col['d3'] + (3 if da >= 0 else -3)) % HUB_K
    loops = {t: cut_block(cg, int(hr[1][col[t]]), 1) for t in ('d3', 'd2', 'd4', 'hallux')}
    for t, lp in loops.items():
        cg.cuts[f'toe_{t}_{side}'] = np.asarray(lp)
        tp, pts = _toe_prog(chain, t, side)
        d = dirs[t]
        tip = pts[-1] + d * (AB.THIGH['toe'][1] - 0.5)
        start = foot + np.array([0.0, pts[0][1] - foot[1], 0.0]) + d * (HUB_PAD[2] if t in ('d3', 'hallux') else
                                                                        HUB_PAD[0]) * 1.05
        path = _resample(np.vstack([start, pts[1:], tip]), STEP['toe'])
        Tt = _tangents(path, 4.0)
        tr = []
        for p, t_ in zip(path, Tt):
            R, ok = cast_ring(tp, p, frame(t_, [0.0, 1.0, 0.0]), TOE_K, rmax=0.03)
            ids = cg.add(R)
            if tr:
                cg.band(tr[-1], ids)
            tr.append(ids)
        m = cg.mesh()
        m, _ = LF.bridge(m, lp, tr[0], rings=1)
        m, _ = LF.cap(m, tr[-1], Tt[-1], shape=(2, 2))
        cg.set_mesh(m)
        # the tip cap's own UV island (the talon's bed: unrolled with the toe, the 2 x 2 dome stretched to p95 1.5)
        cg.cuts[f'tipcap_{t}_{side}'] = np.asarray(tr[-1])
    log(f'[cage] foot {side}: hub K {HUB_K} (rings at {HUB_AT[1:]} mm), sole 6 x 6, toe ports at columns '
        + ', '.join(f'{t} {c}' for t, c in col.items()))


def _poly_radius(Q, a):
    """the radius along each angle a (about the origin) of a closed polygon Q (n, 2) the origin lies inside (star-
    shaped about it): where the ray meets the polygon's edge"""
    out = np.empty(len(a))
    E0, E1 = Q, np.roll(Q, -1, axis=0)
    for i, t in enumerate(a):
        u = np.array([np.cos(t), np.sin(t)])
        dE = E1 - E0
        den = dE[:, 0] * u[1] - dE[:, 1] * u[0]
        with np.errstate(divide='ignore', invalid='ignore'):
            s = (E0[:, 1] * u[0] - E0[:, 0] * u[1]) / den              # the edge's parameter where the ray crosses it
            r = (E0[:, 0] + s * dE[:, 0]) * u[0] + (E0[:, 1] + s * dE[:, 1]) * u[1]
        ok = (s >= 0.0) & (s <= 1.0) & (r > 0.0) & np.isfinite(r)
        out[i] = float(r[ok].min())
    return out


def _poly_inset(Q, t):
    """a closed polygon (n, 2) moved t mm inward, each vertex along its inward bisector"""
    Q = np.asarray(Q, float)
    nrm = lambda e_: np.stack([e_[:, 1], -e_[:, 0]], 1) / np.maximum(np.linalg.norm(e_, axis=1, keepdims=True), 1e-12)
    area = 0.5 * np.sum(Q[:, 0] * np.roll(Q[:, 1], -1) - np.roll(Q[:, 0], -1) * Q[:, 1])
    b = nrm(Q - np.roll(Q, 1, axis=0)) + nrm(np.roll(Q, -1, axis=0) - Q)
    b = (1.0 if area > 0 else -1.0) * b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return Q - t * b


def _axis_ring(prog, c, d, X, rho, K, out=30.0, ellipse=None, poly=None):
    """K points round the axis (c, d) at radius rho (or the ellipse (a, b) along X, Y, or the closed polygon `poly`
    (n, 2) in the frame's (X, Y), star-shaped about the axis: each vertex at its angle on it), cast onto prog's surface
    from `out` mm outside along -d: planar wherever that surface is a solid of revolution about the axis. Vertex 0 on
    X, right-handed about d. Returns the points and the frame (columns X, Y, Z = d)"""
    Fr = frame(d, X)
    a = np.linspace(0.0, 2 * np.pi, K, endpoint=False)
    if poly is not None:
        ra = rb = _poly_radius(np.asarray(poly, float), a)
    else:
        ra, rb = (rho, rho) if ellipse is None else ellipse
    ra, rb = np.broadcast_to(ra, (K,))[:, None], np.broadcast_to(rb, (K,))[:, None]
    P0 = c[None] + d[None] * out + ra * np.cos(a)[:, None] * Fr[:, 0][None] + rb * np.sin(a)[:, None] * Fr[:, 1][None]
    # (k_project marches against its direction from outside: d, not -d)
    Pp, st = prog.project(P0 * MM, np.tile(d, (K, 1)), maxd=0.06)
    assert (st == 0).all(), f'axis ring: {int((st != 0).sum())} casts missed'
    return Pp / MM, Fr


def _loop_round_opening(cg, skin, loop, c, l_ax, s_up, a_in, semi):
    """the 8 vertices of a 2 x 2 block's loop DRAWN ROUND AN OBLIQUE OPENING (the nostril's scoop; D1.3c fix 2): each
    moved onto the oval `semi` (mm, along l_ax / s_up about c: the opening's own oval grown by a gap), at the slot (a
    multiple of 45 deg, the loop's order kept) nearest its own direction, and carried onto the skin ALONG THE
    PASSAGE'S AXIS a_in from outside. The scoop is a prism along that axis, so a point whose shadow along the axis
    lies outside the oval lies outside the opening however the cere curves; carried along the cere's NORMAL the
    same oval falls into the opening on a curved cere (the prism leans 60 deg: the opening's upper back corner lies
    0.9 mm outside its nominal oval in the normal's chart, scratch d13c_fix2/no.py). The loop's vertices are kept
    (project() never slides them). Why: the block's own grid is 5.6 x 3.6 mm against an opening 5.8 x 3.3: with the
    mouth columns on the crease (cast_ring_mouth's corrected mirror) its top row and its front row lay INSIDE the
    opening (two vertices 1.8-2.2 mm down the scoop, a rim quad of 2.2 deg, a 66 deg fold behind it)"""
    V = np.array([cg.V[int(i)] for i in loop], float)
    # each vertex's own direction in the mouth's frame, read along the cere's NORMAL (l_ax x s_up): a vertex the ring's
    # cast left down the scoop casts its shadow along the passage's axis right across the oval (the first try read
    # the directions that way and turned the whole loop by one slot: a 6.7 deg corner behind the nostril)
    phi = np.arctan2(((V - c[None]) @ s_up) / semi[1], ((V - c[None]) @ l_ax) / semi[0])
    best = None
    for dr in (1.0, -1.0):
        for o in range(8):
            a = dr * (np.arange(8) + o) * (np.pi / 4.0)
            d = np.angle(np.exp(1j * (phi - a)))
            if best is None or float(d @ d) < best[0]:
                best = (float(d @ d), a)
    a = best[1]
    T = c[None] + (semi[0] * np.cos(a))[:, None] * l_ax[None] + (semi[1] * np.sin(a))[:, None] * s_up[None]
    # (k_project marches against its direction from outside: -a_in, from 3 mm out along it)
    Pp, st = skin.project((T - 3.0 * a_in[None]) * MM, np.tile(-a_in, (8, 1)), maxd=0.03)
    assert (st == 0).all(), f'nostril loop: {int((st != 0).sum())} casts missed'
    for i, p in zip(loop, Pp / MM):
        cg.V[int(i)] = np.asarray(p, float)
    cg.keep |= set(int(i) for i in loop)


def _lift_onto_outer_skin(cg, skin, among, skip, c, n, l_ax, s_up):
    """the ring vertices beside an opening whose PASSAGE RUNS ON UNDER THE SKIN, put back on the skin (D1.3c fix 2,
    11-11). A spine ring is cast from its centre OUTWARD and stops at the first surface it meets (_cast); behind and
    above the nostril the scoop's passage lies under the cere's upper lip, so a ray that crosses it stops on the
    passage's own wall, under the roof: two vertices of the face rings beside the nostril's loop stood 0.9-1.0 mm
    under the cere (f = 0 there too, so 'on clay' passed and the relax kept them), and the ring quad between them and
    the loop folded 68 deg (d1_05 on the 03:12 and 04:25 builds; scratch d13c_fix2/nq.py's chart). Each vertex of
    `among` within the passage's reach of c (mm, in the opening's frame: l along l_ax, s along s_up, n along the
    skin's normal there) and not in `skip` is cast again FROM OUTSIDE along n; where the first surface met from there
    lies over the vertex, the vertex was under a roof and moves up onto it (a move along n, upward only). Returns the
    moves (id, mm)"""
    ids = []
    for i in among:
        i = int(i)
        w = np.asarray(cg.V[i], float) - c
        if i not in skip and -10.0 < float(w @ l_ax) < 4.0 and -3.5 < float(w @ s_up) < 7.0 and -6.0 < float(w @ n) < 1.0:
            ids.append(i)
    if not ids:
        return []
    V = np.array([cg.V[i] for i in ids], float)
    # (k_project marches against its direction from outside: n, from 5 mm out along it)
    Pp, st = skin.project((V + 5.0 * n[None]) * MM, np.tile(n, (len(ids), 1)), maxd=0.012)
    moved = []
    for i, v, p, s_ in zip(ids, V, Pp / MM, st):
        up = float((p - v) @ n)
        if s_ == 0 and 0.05 < up < 5.0:
            cg.V[i] = np.asarray(p, float)
            moved.append((i, up))
    return moved


def head_ports(cg, skin, info, rings, spec, log=print):
    """the EYES and the NOSTRILS (plan §4.6: the 24-vertex lid rings, the nostril's 8-ring; D1.3b). Each eye: the 6 x 6
    block of the head's rings round the vertex nearest the opening's centre (a 24 loop), one ring of the orbit's skin
    (loft.bridge), the LID MARGIN ring (24) just inside the carved opening's rim, the eye's SOCKET ring (24, on the eye's
    cap, open: the EYE set's globe sits in it; recorded 'eye_L' / 'eye_R'). Each nostril: the 2 x 2 block round the
    vertex nearest the pit (an 8 loop), its rim (8, on the pit's oval), one ring down the pit, a 2 x 2 cap at its
    floor"""
    hd = info['head']
    e0, d0 = np.asarray(hd['eye'], float), _u(hd['eye_dir'])
    fwd = np.asarray(hd['fwd'], float)
    head_v = np.concatenate([np.asarray(r) for r in rings])            # the spine's rings (the head's are nearest)
    out = []
    for side, sg in (('L', 1.0), ('R', -1.0)):
        e = e0 * np.array([sg, 1.0, 1.0])
        d = d0 * np.array([sg, 1.0, 1.0])
        c_s, _ = _axis_ring(skin, e, d, fwd, 0.01, 4)
        v = nearest_vertex(cg, c_s.mean(0), head_v)
        loop = cut_block(cg, v, EYE_BLOCK)
        cg.cuts[f'eye_{side}'] = np.asarray(loop)                # the eye's island (HEAD: the bare orbit and lids)
        if 'caps' in hd:
            # (D1.3c fix 1: the lids' opening is c018's almond outline, raptor._eye_opening: the margin ring on it,
            # EYE_RHO[0] inside, each vertex at its angle about the axis; D1.3c's opening was a circle of r_open)
            Fr_ = frame(d, fwd)
            W_ = np.asarray(hd['caps'][side]['poly'], float) - e
            Q_ = np.column_stack([W_ @ Fr_[:, 0], W_ @ Fr_[:, 1]])
            Pm, _ = _axis_ring(skin, e, d, fwd, None, RINGS['eye']['K'], poly=_poly_inset(Q_, EYE_RHO[0]))
        else:
            Pm, _ = _axis_ring(skin, e, d, fwd, hd['r_open'] - EYE_RHO[0], RINGS['eye']['K'])
        Pi, Fi = _axis_ring(skin, e, d, fwd, EYE_RHO[1], RINGS['eye']['K'])
        mi = cg.add(Pm)
        m = cg.mesh()
        m, _ = LF.bridge(m, loop, mi, rings=1)
        cg.set_mesh(m)
        ii = cg.add(Pi)
        cg.band(mi, ii)
        cg.keep |= set(int(x) for x in mi)
        cg.record(f'eye_{side}', ii, Fi, pinned=['head'], native=dict(joints=[f'eye_{side}'], kept_weighted_beyond=0),
                  seam='SOCKET', lid=[int(x) for x in mi])
        # the nostril
        c0, T0, D0 = (np.asarray(hd['cere'][k], float) for k in ('c0', 'T0', 'D0'))
        n_c = np.asarray(hd['nostril'][0 if side == 'L' else 1], float)
        xa = np.array([sg, 0.0, 0.0])
        X_n = T0
        if 'nostril_frame' in hd:
            # (D1.3c: the oval is carved along the cere's normal, its long axis turned NOSTRIL['tilt']: the rim and the
            # pit cast along that normal, X on the long axis)
            _, xa, X_n, _ = (np.asarray(q, float) for q in hd['nostril_frame'][0 if side == 'L' else 1])
        if 'nostril_dish' in hd:
            # (D1.3c: the nostril is a 5.2 x 3.0 DISH with a deep SLOT under its upper lip, raptor.NOSTRIL. The RIM
            # ring on the dish's wall: NOSTRIL_DISH_RING of the dish's oval round its centre; the PIT ring in the
            # slot's mouth: NOSTRIL_PIT in the dish's frame; both cast along the CERE's normal from outside, so the
            # port is a height field over the cere (what a camera sees of the nostril) and the slot's undercut under
            # the lip stays the bake's; the block centred on the dish. With both rings sized for the old 3.7 x 2.1 pit
            # they lay inside the slot, and the eight quads from the block down the dish to the rim pleated in the
            # face's UV island: 51 texels under two triangles; cast along the slot's leaning axis the pit ring went
            # under the lip: 4 quads against the clay's normal)
            Pn, n_s, l_ax, s_up = (np.asarray(q, float) for q in hd['nostril_dish'][0 if side == 'L' else 1])
            (d_l, d_s), _ = hd['nostril_size']
            v = nearest_vertex(cg, Pn, head_v)
            loop = cut_block(cg, v, 1)
            # (D1.3c fix 2: the nostril is ONE SCOOP, raptor.NOSTRIL: the head says where the cage's rings go:
            # 'nostril_loop', the gap by which the block's own loop stands outside the opening, drawn round it
            # along the passage's axis (_loop_round_opening); 'nostril_ring' and 'nostril_pit', each an ellipse about
            # a point of the mouth's frame, on the scoop's floor; the older heads' rule stays for a head without them)
            if hd.get('nostril_loop') is not None:
                a_in = -np.asarray(hd['nostril_frame'][0 if side == 'L' else 1][1], float)
                _loop_round_opening(cg, skin, loop, Pn, l_ax, s_up, a_in,
                                    (0.5 * d_l + hd['nostril_loop'], 0.5 * d_s + hd['nostril_loop']))
                up_ = _lift_onto_outer_skin(cg, skin, head_v, set(int(i) for i in loop), Pn, n_s, l_ax, s_up)
                log(f'[cage] nostril_{side}: {len(up_)} ring vertices beside the loop stood under the passage\'s roof, '
                    f'moved up onto the cere' + (f' (by {min(u for _, u in up_):.2f} .. {max(u for _, u in up_):.2f} mm)'
                                                 if up_ else ''))
            rg_, pt_ = hd.get('nostril_ring'), hd.get('nostril_pit', NOSTRIL_PIT)
            if rg_ is not None:
                Pr, Fn = _axis_ring(skin, Pn + rg_['at'][0] * l_ax + rg_['at'][1] * s_up - n_s * 3.0, n_s, l_ax, None,
                                    8, out=6.0, ellipse=tuple(rg_['semi']))
            else:
                Pr, Fn = _axis_ring(skin, Pn - n_s * 3.0, n_s, l_ax, None, 8, out=6.0,
                                    ellipse=(NOSTRIL_DISH_RING * 0.5 * d_l, NOSTRIL_DISH_RING * 0.5 * d_s))
            c_p = Pn + pt_['at'][0] * l_ax + pt_['at'][1] * s_up
            Pd, _ = _axis_ring(skin, c_p - n_s * 3.0, n_s, l_ax, None, 8, out=6.0, ellipse=tuple(pt_['semi']))
            xa = n_s                                              # (the floor's cap faces out along the cere's normal)
        else:
            # (the block's centre a little ahead of the pit (NOSTRIL_BACK): D1.3b)
            v = nearest_vertex(cg, n_c - T0 * NOSTRIL_BACK, head_v)
            loop = cut_block(cg, v, 1)
            a_, b_ = 0.5 * np.asarray(spec['head']['nostril'], float) - NOSTRIL_RIM
            Pr, Fn = _axis_ring(skin, n_c - xa * 3.0, xa, X_n, None, 8, out=6.0, ellipse=(a_, b_))
            Pd, _ = _axis_ring(skin, n_c - xa * 3.0, xa, X_n, None, 8, out=6.0, ellipse=(0.45 * a_, 0.45 * b_))
        ri = cg.add(Pr)
        m = cg.mesh()
        m, _ = LF.bridge(m, loop, ri, rings=0)
        cg.set_mesh(m)
        cg.cuts[f'nostril_{side}'] = np.asarray(ri)             # the nostril's own UV island: the dish's floor, the
        #                                                         slot (flattened with the face, the cup's walls folded
        #                                                         over: 1 UV triangle turned, D1.3b r2)
        di = cg.add(Pd)
        cg.band(ri, di)
        cg.keep |= set(int(x) for x in ri) | set(int(x) for x in di)
        m = cg.mesh()
        m, _ = LF.cap(m, di, xa, shape=(2, 2))
        cg.set_mesh(m)
        out.append(side)
    log(f'[cage] head ports: eyes (6 x 6 block -> orbit ring -> lid margin 24 -> eye SOCKET 24, open), nostrils (2 x 2 '
        f'-> rim 8 -> pit 8 -> 2 x 2 floor), both sides')


MIRROR = np.array([-1.0, 1.0, 1.0])


def _swap_side(s):
    return s[:-2] + '_R' if s.endswith('_L') else s


def mirror_limbs(cg, new_ids, loops):
    """the RIGHT limbs as the left's EXACT MIRROR (D1.3c): every vertex the left wing and leg added (new_ids) mirrored
    across x = 0, every quad on them (and on the left port loops) copied with the vertices mapped and the winding
    reversed; a left port loop's vertex maps to its right twin on the spine (the spine's rings are cast mirror-
    symmetric, sym=True, so the twins are exact). The left records ('wing_L', 'ankle_L', 'foot_L') get their right twins:
    vertex k of the right ring is the mirror of the left's vertex -k (so each runs right-handed about its own distal
    axis, vertex 0 on its frame's X, as cast_ring's per-side rings did), the frame mirrored (X, Y -> -mirrored Y, Z);
    the limbs' cut loops ('knee_L', 'toe_*_L', 'tipcap_*_L') and kept vertices likewise. Returns (vertices, quads)
    added"""
    from scipy.spatial import cKDTree
    Vn = set(int(i) for i in new_ids)
    V = np.array(cg.V)
    lp_L = set(int(v) for nm in ('wing_L', 'leg_L') for v in loops[nm])
    lp_R = np.array(sorted(set(int(v) for nm in ('wing_R', 'leg_R') for v in loops[nm])))
    d, j = cKDTree(V[lp_R]).query(V[sorted(lp_L)] * MIRROR)
    assert d.max() < 1e-6, f'the port loops are not mirror twins ({d.max():.2e} mm)'
    m = {v: int(lp_R[jj]) for v, jj in zip(sorted(lp_L), j)}
    ids = sorted(Vn)
    base = cg.add(V[ids] * MIRROR)
    m.update({v: int(b) for v, b in zip(ids, base)})
    allowed = Vn | lp_L
    Q_L = [q for q in cg.Q if all(int(a) in allowed for a in q) and any(int(a) in Vn for a in q)]
    for q in Q_L:
        cg.Q.append([m[int(a)] for a in q][::-1])
    for nm in [k for k in list(cg.records) if k.endswith('_L') and all(int(i) in Vn for i in cg.records[k]['ids'])]:
        r = cg.records[nm]
        K = len(r['ids'])
        idsR = [m[int(r['ids'][(-k) % K])] for k in range(K)]
        Fr = np.asarray(r['frame'], float)
        X, Y, Z = Fr[:, 0] * MIRROR, -(Fr[:, 1] * MIRROR), Fr[:, 2] * MIRROR
        extra = {k: v for k, v in r.items() if k not in ('ids', 'frame', 'centre', 'r_mean', 'K', 'K_plan', 'h',
                                                         'planarity', 'pinned', 'native')}
        nat = {k: ([_swap_side(s) for s in v] if isinstance(v, list) else v) for k, v in r['native'].items()}
        cg.record(_swap_side(nm), idsR, np.column_stack([X, Y, Z]), pinned=[_swap_side(s) for s in r['pinned']],
                  native=nat, **extra)
    for nm in [k for k in list(cg.cuts) if k.endswith('_L') and all(int(i) in Vn for i in cg.cuts[k])]:
        cg.cuts[_swap_side(nm)] = np.array([m[int(i)] for i in cg.cuts[nm]])
    cg.keep |= {m[v] for v in cg.keep if v in Vn}
    return len(ids), len(Q_L)


def symmetric_pairs(V, tol=1e-3):
    """each vertex's mirror twin across x = 0 where one lies within tol mm (a midline vertex is its own; the per-side
    head ports' casts agree to float noise), -1 else"""
    from scipy.spatial import cKDTree
    d, j = cKDTree(V).query(np.asarray(V) * MIRROR)
    return np.where(d <= tol, j, -1)


def _poly_path(pts, step):
    P = _resample(np.asarray(pts, float), 0.5)
    from scipy.ndimage import gaussian_filter1d
    Ps = gaussian_filter1d(P, 6.0, axis=0, mode='nearest')
    Ps[0], Ps[-1] = P[0], P[-1]
    return _resample(Ps, step)


def build(spec, chain, log=print):
    """the cage (Cage) and the programs it was cast on: dict(cage, body, skin, info, shells)"""
    from ..heads import raptor_cage as RC
    skin, info = AB.skin_program(spec, chain)
    body, _ = AB.skin_program(spec, chain, wings=False, legs=False)
    shells, _ = AB.shells(spec, chain)
    cg = Cage()
    P = chain['pos']
    # ---- the spine
    pts, labs = spine_path(spec, chain, info)
    T = _tangents(pts, SPINE_TURN)
    rings, frames = [], []
    worst = 1.0
    G_mouth = np.asarray(info['head']['gape'][0], float)          # the left crease, rictus -> the bill
    # the face's last rings TILT to the bills' margin plane (the plane fitted through both keratin margins: the lower
    # leaves the chin's skin 2-3 mm behind the upper leaves the cere), so the last ring lies FACE_STOP behind both;
    # square to the head's axis the last ring's lower half ran ahead of the lower margin and its bridge folded back
    # (D1.3b's first build: 24 flipped quads round the gape strip)
    Mg = np.vstack([np.asarray(shells['beak_upper']['margin'], float), np.asarray(shells['beak_lower']['margin'], float)])
    Nm = np.linalg.svd(Mg - Mg.mean(0))[2][2]
    Nm = Nm if Nm[2] > 0 else -Nm
    i_face = [i for i, lb in enumerate(labs) if lb == 'face']
    for i in i_face:
        w_ = (i - i_face[0] + 1) / len(i_face)
        T[i] = _u((1.0 - w_) * T[i] + w_ * Nm)
    for p, t, lb in zip(pts, T, labs):
        Fr = frame(t, [1.0, 0.0, 0.0])
        pin, w = _mouth_pin(G_mouth, p, Fr[:, 2]) if lb in ('head', 'face') else (None, 0.0)
        if w > 0.0:
            R, ok = cast_ring_mouth(body, p, Fr, SPINE_K, pin, w, RC.MOUTH_K)
        else:
            R, ok = cast_ring(body, p, Fr, SPINE_K, sym=True)
        worst = min(worst, ok)
        rings.append(cg.add(R))
        if w >= 0.999:
            cg.keep |= {int(rings[-1][k]) for k in RC.MOUTH_K}
        frames.append(Fr)
    for a, b in zip(rings[:-1], rings[1:]):
        cg.band(a, b)
    log(f'[cage] spine: {len(rings)} rings of K {SPINE_K} (tail {labs.count("tail")}, trunk {labs.count("trunk")}, '
        f'neck {labs.count("neck")}, head {labs.count("head")}, face {labs.count("face")}); casts ok >= {worst:.3f}')
    # ---- ports on the spine: the wing (4 round x 8 along) and the leg (6 x 6), each side
    def ring_angle(i, q):
        Fr = frames[i]
        d = np.asarray(q, float) - pts[i]
        return np.arctan2(d @ Fr[:, 1], d @ Fr[:, 0]) % (2 * np.pi)

    def nearest_ring(q):
        return int(np.argmin([abs((np.asarray(q) - pts[i]) @ T[i]) + 0.2 * np.linalg.norm(np.asarray(q) - pts[i])
                              for i in range(len(pts))]))

    def block(i_c, k_c, rows, cols):
        i0, k0 = i_c - rows // 2, k_c - cols // 2
        F = []
        for i in range(i0, i0 + rows):
            for k in range(k0, k0 + cols):
                F.append(i * SPINE_K + (k % SPINE_K))
        return F, i0, k0

    ports = {}
    # the wing's port where the humerus's axis leaves the body clay (the glenoid itself lies near the dorsal midline
    # seen from the spine's centre: D1.3's first blocks met over the back)
    sh, el = np.asarray(P['shoulder_L'], float), np.asarray(P['elbow_L'], float)
    ts_ = np.linspace(0.0, 1.0, 400)
    fa = body.eval((sh[None] + ts_[:, None] * (el - sh)[None]) * MM)
    w_exit = sh + float(ts_[np.argmax(fa > 0)]) * (el - sh)
    ig = nearest_ring(w_exit)
    kg = int(round(ring_angle(ig, w_exit) / (2 * np.pi / SPINE_K)))
    # the thigh's exit: where its axis leaves the body clay
    hip = np.asarray(P['femur_L'], float) + np.array([6.0, 4.0, 4.0])
    knee = np.asarray(P['tibiotarsus_L'], float)
    ts = np.linspace(0.0, 1.0, 200)
    ax = hip[None] + ts[:, None] * (knee - hip)[None]
    fb = body.eval(ax * MM)
    t_exit = float(ts[np.argmax(fb > 0)])
    exit_L = hip + t_exit * (knee - hip)
    il = nearest_ring(exit_L)
    kl = int(round(ring_angle(il, exit_L) / (2 * np.pi / SPINE_K)))
    for side, sg in (('L', 1), ('R', -1)):
        kw = kg if side == 'L' else (SPINE_K // 2 - kg) % SPINE_K
        kk = kl if side == 'L' else (SPINE_K // 2 - kl) % SPINE_K
        # (a block of an EVEN width centred on a vertex column: the mirror of [k0, k0 + w) is [16 - k0 - w, 16 - k0))
        ports[f'wing_{side}'] = block(ig, kw, 8, 4)
        # the leg: 8 along x 4 round (the drumstick is long fore and aft; a 6 x 6 block centred where the thigh
        # leaves, 22 deg off the ventral midline, met its mirror across it), at least one face column off the
        # midline (column 24 = straight down) so the two holes never share a vertex
        kc = max(kl, SPINE_K * 3 // 4 + 3) if side == 'L' else min(kk, SPINE_K * 3 // 4 - 3)
        ports[f'leg_{side}'] = block(il, kc, 8, 4)
    allf = [f for v in ports.values() for f in v[0]]
    assert len(allf) == len(set(allf)), 'the port blocks overlap: ' + '; '.join(
        f'{k} rows {v[1]}.. cols {v[2]}..' for k, v in ports.items()) + f' (wing ring {ig} col {kg}, leg {il} {kl})'
    log(f'[cage] ports: wing at spine ring {ig} column {kg}; leg at ring {il} column {kl} (the thigh leaves the body '
        f'at {t_exit:.2f} of hip -> knee)')
    m = cg.mesh()
    loops = {}
    # the four blocks cut at once (the spine's quads are the first in cg.Q, so the block ids index them directly);
    # each hole's loop is the boundary loop inside its block's vertices, ordered as the remaining faces run
    keep = np.ones(len(m.Q), bool)
    keep[allf] = False
    m = QuadMesh(m.V, m.Q[keep])
    bl = LF.boundary_loop(m)
    for nm, (F, i0, k0) in ports.items():
        verts = set()
        for f in F:
            verts |= set(int(v) for v in cg.Q[f])
        cand = [l for l in bl if set(l) <= verts and len(l) >= 16]
        assert len(cand) == 1, f'{nm}: {len(cand)} loops'
        loops[nm] = np.array(cand[0])
    cg.set_mesh(m)
    for nm, lp in loops.items():
        cg.cuts[f'port_{nm}'] = np.asarray(lp)
    cg.cuts['head'] = np.asarray(rings[labs.index('head')])     # the head island's border: the first head ring
    # the FACE: the first face ring, the feather line before the cere and the lores (plan §4.7: HEAD holds the bare
    # parts; the feathered head is skin under the coat, BODY's: D1.3b restart 2's UVs)
    cg.cuts['face'] = np.asarray(rings[labs.index('face')])
    log(f'[cage] port loops: ' + ', '.join(f'{k} {len(v)}' for k, v in loops.items()))

    # ---- the wings and the legs: the LEFT side built, the right its EXACT MIRROR (D1.3c, the lead's call: left and right
    # share UV space, Skye's UV reuse; built per side, the bridges, caps and reduction strips' rolls differed by side, up
    # to 3.2 mm at the feet, and no limb island could stack). Anatomy gives no asymmetry here: the skeleton is mirrored
    # (D1.0's |x_L + x_R| < 1e-6), the clay's right limbs are its left mirrored
    v_limbs0 = len(cg.V)
    for side, sg in (('L', 1.0),):
        wp_ = limb_prog(spec, chain, 'wing', side)
        bones = [P[f'{k}_{side}'] for k in ('shoulder', 'elbow', 'wrist', 'cmc_end', 'digit_tip')]
        path = _poly_path(bones, STEP['wing'])
        Tw = _tangents(path, 8.0)
        dirs = [np.linalg.norm(p - bones[0]) for p in path]
        # from WING_START past the glenoid: out of the wing's 9 mm blend into the trunk (at 22 mm the projection onto
        # the full skin bent the record ring: planarity 0.056) and h (8 mm) clear of the port's corner poles
        start = int(np.argmax(np.array(dirs) >= WING_START))
        path, Tw = path[start:-1], Tw[start:-1]
        fwd_w = chain['R'] @ np.array([0.0, 0.0, 1.0])            # the wing's leading direction (X: the LE side)
        wr = []
        for j, (p, t) in enumerate(zip(path, Tw)):
            Fr = frame(t, fwd_w)                                  # right-handed about its own distal Z
            R, ok = cast_ring(wp_, p, Fr, WING_K)
            ids = cg.add(R)
            if wr:
                cg.band(wr[-1], ids)
            wr.append(ids)
            if j == 0:
                cg.record(f'wing_{side}', ids, Fr, pinned=['thorax', f'scapula_{side}'],
                          native=dict(joints=[f'humerus_{side}', f'forearm_{side}', f'hand_{side}', f'digit2_{side}'],
                                      kept_weighted_beyond=0))
        # bridge the port loop to the first ring (2 rings between), then cap the digit tip (8 x 4)
        m = cg.mesh()
        m, _ = LF.bridge(m, loops[f'wing_{side}'], wr[0], rings=2)
        # (domed WING_CAP_DOME along the tube: flat in the last ring's plane, its quads at the digit tip projected
        # onto the tip's round folded 106-126 deg on both diagonals, the D1.3c check's k04; scratch f10_wingtip.py: dome
        # 2 mm, the worst fold 35 deg, the least corner 32.5)
        m, _ = LF.cap(m, wr[-1], Tw[-1], shape=(8, 4), dome=WING_CAP_DOME)
        cg.set_mesh(m)
    log(f'[cage] wings: K 24 tubes along the bones from {WING_START:.0f} mm past the glenoid, bridged to the ports, '
        f'capped 8 x 4')

    # ---- the legs (the left: the right is its mirror, below)
    for side, sg in (('L', 1.0),):
        lp = limb_prog(spec, chain, 'leg', side)
        knee = np.asarray(P[f'tibiotarsus_{side}'], float)
        ank = np.asarray(P[f'tarsometatarsus_{side}'], float)
        foot = np.asarray(P[f'foot_{side}'], float)
        ex = exit_L * np.array([sg, 1.0, 1.0])
        start = ex + _u(knee - ex) * 10.0
        # to 3 mm above the foot joint: the FOOT record 12 mm above it (above the trochleae), two rings past it before
        # the cap (its corner poles were ON the record when it was the last ring: D1.3)
        # (D1.3 second pass: ending 3 mm above the foot joint, the last rings flared round the toes' bases into flat
        # plates; the leg's bends (knee ~100 deg on a 14 mm tube) need the wider LEG_TURN or the ring planes cross)
        path = _poly_path([start, knee, ank, foot - _u(foot - ank) * HUB_AT[0]], STEP['leg'])
        i_foot = int(np.argmin(np.linalg.norm(path - (foot - _u(foot - ank) * 19.0), axis=1)))
        Tl = _tangents(path, LEG_TURN)
        side_ax = np.array([sg, 0.0, 0.0])
        lr, K = [], LEG_K
        i_ank = int(np.argmin(np.linalg.norm(path - ank, axis=1)))
        i_red = max(i_ank - 6, 2)                                 # the 24 -> 16 strip on the drumstick
        for j, (p, t) in enumerate(zip(path, Tl)):
            Fr = frame(t, side_ax)
            if j == i_red + 1:
                R, ok = cast_ring(lp, p, Fr, ANKLE_K)
                # the inner ring keeps its own order (vertex 0 on X: the K 16 rings after it band index for index);
                # the OUTER ring is rolled so the strip's units meet it (D1.3: shifting the inner ring instead
                # twisted the next band into spikes and put the ankle's vertex 0 1.8 deg off X)
                outer = np.array(lr[-1])
                anc = _inner_anchor('RS' * 4)
                best = min(range(len(outer)), key=lambda s_: float(np.linalg.norm(
                    np.array([cg.V[v] for v in np.roll(outer, -s_)[anc]]) - R, axis=1).sum()))
                ids = reduce_mixed(cg, np.roll(outer, -best), R, 'RS' * 4)
                K = ANKLE_K
            else:
                R, ok = cast_ring(lp, p, Fr, K)
                ids = cg.add(R)
                if lr:
                    cg.band(lr[-1], ids)
            lr.append(ids)
            if j == i_ank:
                cg.record(f'ankle_{side}', ids, Fr, pinned=[f'tibiotarsus_{side}'],
                          native=dict(joints=[f'tarsometatarsus_{side}'], kept_weighted_beyond=0))
        cg.record(f'foot_{side}', lr[i_foot], frame(Tl[i_foot], side_ax), pinned=[f'tarsometatarsus_{side}'],
                  native=dict(joints=[n for n in ('hallux', 'd2', 'd3', 'd4')], kept_weighted_beyond=0))
        # the KNEE ring cuts the thigh's UV island in two (unrolled whole, the ~100 deg bend curled the strip over
        # itself: 10-11k texels of self-overlap, D1.3b restart 2)
        cg.cuts[f'knee_{side}'] = np.asarray(lr[int(np.argmin(np.linalg.norm(path - knee, axis=1)))])
        m = cg.mesh()
        m, _ = LF.bridge(m, loops[f'leg_{side}'], lr[0], rings=2)
        cg.set_mesh(m)
        foot_hub(cg, spec, chain, side, lr[-1], log=log)
    log('[cage] legs: K 24 thighs from the flank ports, 24 -> 16 on the drumstick, K 16 to the foot ring, the hub '
        f'16 -> {HUB_K} and four K {TOE_K} toes from its ports, each capped 2 x 2')
    n_mir = mirror_limbs(cg, range(v_limbs0, len(cg.V)), loops)
    log(f'[cage] right wing and leg: the left\'s exact mirror ({n_mir[0]} vertices, {n_mir[1]} quads; records, cut '
        f'loops mirrored; each right record ring runs right-handed about its own distal axis)')

    # ---- the tail: the spine's first ring reduces 32 -> 16, three K 16 rings, the record, a 4 x 4 cap
    first = rings[0]
    tp = info['tail_root']['C']
    t_dir = _u(tp[0] - tp[3])                                     # backward along the tail root
    # stations back from the spine's first ring (z -62) along the tail root, while inside it with 4 mm to spare
    # (D1.3: stations past its end collapsed the ring)
    stations = [pts[0] + t_dir * d for d in np.arange(5.0, 60.0, STEP['tail'] * 0.8)]
    stations = [s_ for s_ in stations if body.eval((s_ + t_dir * 4.0)[None] * MM)[0] < 0]
    assert len(stations) >= 4, f'the tail root holds {len(stations)} K 16 rings'
    m = cg.mesh()
    # the strip: the first ring's edges are used FORWARD by the spine's quads, so it is given reversed
    Fr0 = frame(-T[0], [1.0, 0.0, 0.0])
    R16, _ = cast_ring(body, stations[0], Fr0, TAIL_K)
    # the inner ring in its own order (vertex 0 on X), the reversed spine ring ROLLED to meet it (as the leg's strip)
    rev = np.array(first[::-1])
    s_best = min(range(len(rev)), key=lambda s_: float(np.linalg.norm(
        np.array([cg.V[v] for v in np.roll(rev, -s_)[0::2]]) - R16, axis=1).sum()))
    m, inner = LF.reduce_ring(m, np.roll(rev, -s_best), R16)
    cg.set_mesh(m)
    tr_ = [inner]
    for j, sp in enumerate(stations[1:]):
        R, _ = cast_ring(body, sp, Fr0, TAIL_K)
        ids = cg.add(R)
        cg.band(tr_[-1], ids)
        tr_.append(ids)
    # the third K 16 ring (the second sat 4.8 mm from the strip's poles: h 5)
    cg.record('tail', tr_[2], Fr0, pinned=['pelvis'], native=dict(joints=['caudal_0', 'caudal_1', 'pygostyle'],
                                                                     kept_weighted_beyond=0))
    m = cg.mesh()
    m, _ = LF.cap(m, tr_[-1], -T[0])
    cg.set_mesh(m)
    log('[cage] tail: 32 -> 16 at the rump, K 16 tail root, capped 4 x 4')

    # ---- the face
    RC.face(cg, rings[-1], frames[-1], shells, log=log)
    head_ports(cg, skin, info, rings, spec, log=log)
    Q, flips = orient(cg.Q)
    cg.Q = Q
    # the outward sign: most faces' normals along the clay's gradient
    m = cg.mesh()
    fc = m.V[m.Q].mean(1)
    fn = m.face_normals()
    g = skin.normals(fc * MM)
    if (np.einsum('ij,ij->i', fn, g) < 0).mean() > 0.5:
        cg.Q = [q[::-1] for q in cg.Q]
    log(f'[cage] oriented ({flips} faces flipped to agree)')
    # the closed ends the UV seams run to: the wing tips, the toe tips, the tail's cap
    Va = np.array(cg.V)
    refd = np.unique(np.array(cg.Q, np.int64))
    near_ = lambda p: int(refd[np.argmin(np.linalg.norm(Va[refd] - np.asarray(p, float), axis=1))])
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        cg.terms[f'wing_{sd}'] = near_(P[f'digit_tip_{sd}'])
        for t, g_ in chain['toes'].items():
            cg.terms[f'toe_{t}_{sd}'] = near_(np.asarray(g_['tip'], float) * np.array([sg, 1.0, 1.0]))
    # (among the vertices within 25 mm of the tail root's axis: over the whole cage the farthest along the tail's
    # down-back direction was the left hallux's tip, and the trunk's tail cap flattened round its uncut end, D1.3b r2)
    on_ax = refd[np.linalg.norm(np.cross(Va[refd] - pts[0], t_dir), axis=1) < 25.0]
    cg.terms['tail'] = int(on_ax[np.argmax((Va[on_ax] - pts[0]) @ t_dir)])
    # compact: the cut blocks' inner vertices are left unreferenced (D1.3b's ports); every id list is remapped
    used = np.unique(np.array(cg.Q, np.int64))
    remap = -np.ones(len(cg.V), np.int64)
    remap[used] = np.arange(len(used))
    cg.V = [cg.V[i] for i in used]
    cg.Q = [[int(remap[a]) for a in q] for q in cg.Q]
    for r in cg.records.values():
        r['ids'] = remap[np.asarray(r['ids'])]
        for k in ('commissures', 'lid'):
            if k in r:
                r[k] = [int(remap[i]) for i in r[k]]
    cg.keep = set(int(remap[i]) for i in cg.keep if remap[i] >= 0)
    cg.cuts = {k: remap[np.asarray(v)] for k, v in cg.cuts.items()}
    cg.terms = {k: int(remap[v]) for k, v in cg.terms.items()}
    assert all((v >= 0).all() for v in cg.cuts.values())
    rings = [remap[np.asarray(r)] for r in rings]
    log(f'[cage] compacted: {len(remap) - len(used)} unreferenced vertices dropped')
    return dict(cage=cg, body=body, skin=skin, info=info, shells=shells, spine=dict(pts=pts, labs=labs, rings=rings))


def _inner_anchor(units):
    """for a reduce_mixed strip: the outer vertex each inner vertex sits beside (its unit's start and middle)"""
    out, o = [], 0
    for u in units:
        out += [o, o + (2 if u == 'R' else 1)]
        o += 4 if u == 'R' else 2
    return out


def _align(R, want):
    """R's cyclic shift (and direction) nearest `want`, index for index"""
    best = None
    for d in (1, -1):
        Rd = R[::d]
        for s in range(len(R)):
            Rs = np.roll(Rd, -s, axis=0)
            c = float(np.linalg.norm(Rs - want, axis=1).sum())
            if best is None or c < best[0]:
                best = (c, Rs)
    return best[1]


def project(cage, skin, skip=()):
    """move every vertex not in skip onto the skin's zero set along its vertex normal (then Newton); returns the
    residual |f| (mm) per vertex"""
    m = cage.mesh()
    V = m.V.copy()
    twins = symmetric_pairs(V, PAIR_TOL)            # (D1.3c: the mirror pairs as built, kept exact through the moves)
    pr0 = np.nonzero(twins >= 0)[0]
    assert (twins[twins[pr0]] == pr0).all(), 'project: a mirror pairing is not mutual'
    fn = m.face_normals()
    vn = np.zeros_like(V)
    for k in range(4):
        np.add.at(vn, m.Q[:, k], fn)
    vn = _u(vn + 1e-12)
    idx = np.array([i for i in range(len(V)) if i not in set(skip)])
    Pp, st = skin.project(V[idx] * MM, vn[idx], maxd=0.01)
    Pp = Pp / MM
    # a move over MAX_MOVE is the wrong surface (D1.3: a foot cap's centre landed on the breast, 200 mm away): kept
    # where it was, then the Newton walk below with each step clamped to 1 mm finds the near surface
    far = np.linalg.norm(Pp - V[idx], axis=1) > MAX_MOVE
    V[idx[~far]] = Pp[~far]
    # Newton along the field's gradient where the ray found no crossing (D1.3: 45 vertices at the face's strip and the
    # neck's base stayed up to 3.7 mm off)
    for _ in range(40):
        f = skin.eval(V[idx] * MM) / MM
        bad = np.abs(f) > 1e-4
        if not bad.any():
            break
        g = skin.normals(V[idx][bad] * MM)
        V[idx[bad]] -= g * np.clip(f[bad], -1.0, 1.0)[:, None]
    # RELAX (D1.3b): RELAX_ITERS rounds of a tangential Laplacian (each free vertex RELAX_LAM of the way to its edge
    # neighbours' mean, the move's normal part removed) and the Newton walk back onto the skin. The bridges and funnels
    # (the shoulders, the face, the foot's hub and toes) are interpolated rings that the projection alone left folded
    # (D1.3: 30 flipped quads; D1.3b's first build 108). Fixed: the sockets (skip), every record ring (their planarity
    # and frames are gated as cast) and cage.keep (the mouth's columns, the lid margins, the nostrils' rims)
    fixed = set(int(i) for i in skip) | set(cage.keep)
    for r in cage.records.values():
        fixed |= set(int(i) for i in r['ids'])
    free = np.array([i for i in range(len(V)) if i not in fixed])
    nb = [[] for _ in range(len(V))]
    for q in m.Q:
        for k in range(4):
            a, b = int(q[k]), int(q[(k + 1) % 4])
            nb[a].append(b)
            nb[b].append(a)
    nbs = [np.array(sorted(set(n)), np.int64) for n in nb]
    free = np.array([i for i in free if len(nbs[i])], np.int64)
    for _ in range(RELAX_ITERS):
        mean = np.array([V[nbs[i]].mean(0) for i in free])
        n_ = skin.normals(V[free] * MM)
        dv = mean - V[free]
        dv -= n_ * np.einsum('ij,ij->i', dv, n_)[:, None]
        V[free] += RELAX_LAM * dv
        for _ in range(20):
            f = skin.eval(V[free] * MM) / MM
            bad = np.abs(f) > 1e-4
            if not bad.any():
                break
            g = skin.normals(V[free][bad] * MM)
            V[free[bad]] -= g * np.clip(f[bad], -1.0, 1.0)[:, None]
    # the MIRROR kept exact (D1.3c): each paired vertex the mean of its own move and its twin's mirrored (the clay is
    # its own mirror image: avian_body.skin_program folds the legs first; so the two moves differ by the float order
    # of the program's members, and by the per-side casts of the head's ports, PAIR_TOL), a midline vertex on x = 0;
    # the right side's UVs are the left's, so its positions must be the left's mirrored. Then one more Newton walk for
    # the pairs the mean moved, the SAME step taken on both sides (the left's, mirrored)
    pr = twins >= 0
    V[pr] = 0.5 * (V[pr] + V[twins[pr]] * MIRROR)
    lead = np.array([i for i in idx if twins[i] >= 0 and i not in fixed and
                     (V[i, 0] > 0.0 or (twins[i] == i))], np.int64)
    for _ in range(20):
        f = skin.eval(V[lead] * MM) / MM
        bad = np.abs(f) > 1e-4
        if not bad.any():
            break
        g = skin.normals(V[lead][bad] * MM)
        V[lead[bad]] -= g * np.clip(f[bad], -1.0, 1.0)[:, None]
    V[lead, 0] = np.where(twins[lead] == lead, 0.0, V[lead, 0])
    V[twins[lead]] = V[lead] * MIRROR
    cage.V = [v for v in V]
    mirror_diagonals(cage)
    return np.abs(skin.eval(V * MM)) / MM


def _split_bend(V, q):
    """the angle (deg) between the two triangles of the quad q split along q[0] - q[2]"""
    a, b, c, d = (V[int(i)] for i in q)
    n1, n2 = np.cross(b - a, c - a), np.cross(c - a, d - a)
    return float(np.degrees(np.arccos(np.clip((n1 @ n2) / max(np.linalg.norm(n1) * np.linalg.norm(n2), 1e-30), -1.0, 1.0))))


def mirror_diagonals(cage):
    """the STORED SPLIT of every quad (its diagonal q[0] - q[2]: what an export by stored order triangulates along)
    made (1) the split that bends least and (2) the mirror image of its twin's (D1.3c fix 2, check 2's k21: the
    mirror reverses a quad's winding, which turned the stored diagonal on 3282 of 3300 pairs; 89 pairs bent over 30
    deg on one side only, 47 / 113 deg by the eye, 60 / 106 at the mouth corner: a low triangulated by stored order
    would not share the mirrored bake). The left quad leads: rolled so its better split is stored; its twin stored as
    [m(q0), m(q3), m(q2), m(q1)] (the mirror of that diagonal, the winding reversed back). A quad across the midline
    (its own twin) only gets its better split: no split of it is its own mirror image. Returns (pairs, quads rolled)"""
    V = np.array(cage.V)
    tw = symmetric_pairs(V, 1e-9)
    key = {frozenset(int(i) for i in q): k for k, q in enumerate(cage.Q)}
    n_pair = n_roll = 0
    for k, q in enumerate(cage.Q):
        q = [int(i) for i in q]
        mq = [int(tw[i]) for i in q]
        j = key.get(frozenset(mq)) if min(mq) >= 0 else None
        if j is not None and j != k and V[q].mean(0)[0] < 0.0:
            continue                                               # a right quad: its left twin leads
        if _split_bend(V, q) > _split_bend(V, q[1:] + q[:1]) + 1e-9:
            q = q[1:] + q[:1]
            n_roll += 1
        cage.Q[k] = q
        if j is not None and j != k:
            cage.Q[j] = [int(tw[q[0]]), int(tw[q[3]]), int(tw[q[2]]), int(tw[q[1]])]
            n_pair += 1
    return n_pair, n_roll
