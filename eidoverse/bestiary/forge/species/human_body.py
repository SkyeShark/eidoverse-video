"""HUMAN H1: the BODY of the baseline cage (HUMAN_PLAN §2.4, §6.2; the lead's H1 decisions 1-4), below the shared K 48
neck ring, on MakeHuman's pinned body (human_ref.PinnedBody) with the neck blending into GNM's.

THE LAYOUT (10-28). The plan's trunk cylinder with an O-grid arm hole and an annulus to the neck fails at the shoulder:
the jugular notch sits at the acromion's height (ANSUR women 1327 against 1332 mm), so rows passing over the shoulders
collapse at the front. Instead:
  YOKE    a band from arm to arm over the shoulders: a FRONT face (the upper chest, RF rows from the trunk's junction up
          to the shoulder line), a TOP face (the shoulder tops, RT rows), a BACK face (the upper back, RB rows), CB
          columns a side from the midline to the arm's root; the NECK rises from a hole in the top face (CH columns a
          side x RT rows: 2 (2 CH + RT) = 48 round, the neck ring's K, so the neck needs no reduction)
  ARMS    tubes continuing the yoke past its end column: the arm's root loop is the yoke's section there (RF + RT + RB
          = 24 edges) plus the ARMPIT edge (8) under the arm: K 32; the ARMSCYE ring (K 32, planar) one strip distal
  TRUNK   a tube of 64 columns hanging from the yoke's open underside between the armpits (its top row: the yoke's
          front and back lower edges and the two armpit edges, 12 + 8 + 12 a side); the WAIST ring (K 64) the row on the
          omphalion's horizontal plane
  PANTS   the trunk's last row splits into the two legs by a crotch BRIDGE of 16 edges on the midline under the body
          (each leg's root loop: its half of the row, 32 edges, and the bridge: K 48); the HIP ring (K 48, planar) one
          strip distal, from the gluteal fold to the inguinal line just under the crotch
  LIMBS   arm K 32 to the ELBOW ring, 32 -> 24 on the proximal forearm (units on the medial side), the WRIST ring K 24;
          leg K 48 -> 40 -> 32 down the thigh, the KNEE ring K 32, 32 -> 24 on the shank, the ANKLE ring K 24; three loops
          round each hinge
  HANDS, FEET  MakeHuman hm08's own (CC0), from its K 20 loop at the wrist / ankle on, joined by a 24 -> 20 band: their
          fingers, toes and nails are hm08's, at its pinned positions
  PORTS   on the back's regular grid: two scapular back_limb plugs (6 x 6, K 24) over the scapulae's medial borders, the
          back shell plug (8 x 8, K 32) on the midline under them, two lumbar back_limb plugs (6 x 6, K 24) on the
          posterior flanks above the iliac crests, the sacral plug (4 x 4, K 16); each a planar ring at equal angles
ANGLES: every limb ring's vertices sit at known angles in the limb's ANATOMICAL frame (from the front, turning toward the
arm's top / the leg's lateral side), fixed by the topology (the bands' patterns), so both sexes and hm08's loops share
them. One topology for both sexes; the positions are each sex's.

    topology(log) -> BodyTopo (the left half; hm08's bands matched on the woman's pinned body)
    place(BT, sex, PB_V, head, log) -> the half's targets and records
"""
import os

import numpy as np

from . import human_ref as HR
from . import human_topo as HT

VERSION = 'h1-body-1'
BODY = dict(
    CB=12, RF=8, RT=8, RB=8, CH=8,         # the yoke (columns a side to the arm root, front / top / back rows, neck hole)
    NN=3,                                   # the neck rings between the neck base and the K 48 neck ring
    NT=26, TW=17,                           # the trunk's rows under the junction, the waist ring's row
    BR=16,                                  # the crotch bridge's edges
    # the ARM's stations on its chain (0 the shoulder joint, 1 the elbow, 2 the wrist)
    # (post: rings between the wrist / ankle ring and the 24 -> 20 band, so the band's strip into hm08's loop is short:
    # one strip 76 mm long at the ankle left the clay 3+ mm off, H1's first figure)
    # (root_blend: rings after the tilted armscye / hip ring whose planes turn from its plane to the limb's: one strip
    # ~90 mm long over the man's deltoid flattened it, aspect p99 8.1; post: two rings, so the 24 -> 20 band's poles
    # stay out of the wrist ring's collar)
    # (turn: the rings' planes turn from the upper arm's direction to the forearm's over +-turn of the chain round the
    # elbow; over +-0.10 the hinge rings turned ~57 % of the bend between two rings and closed to 4.6-7.3 mm at the inner
    # elbow, 38 mm at the olecranon: 12 of the man's cage quads folded there; the H1 review)
    arm=dict(root_blend=2, up=(0.24, 0.30, 0.36, 0.42, 0.48, 0.54, 0.60, 0.66, 0.72), elbow=0.79,
             hinge=(0.88, 0.96, 1.04), pre=(1.12,), red=1.20, fore=(1.28, 1.35, 1.42, 1.49, 1.56, 1.63, 1.70),
             wrist=1.77, post=(1.83, 1.89), hm_t=0.938, turn=0.25),
    # the LEG's (0 the hip joint, 1 the knee, 2 the ankle)
    # (thigh: the first station far enough down that the two root-blend rings have room at the back, where the tilted
    # hip ring is lowest: from 0.20 the hip ring, both blend rings and the first thigh ring sat within 6 mm at the back
    # of the woman's thigh, 11 mm a strip on the man's, and printed a crease under the buttocks; the H1 review)
    leg=dict(root_blend=2, thigh=(0.27, 0.32, 0.37, 0.41), red1=0.45, mid=(0.51, 0.57), red2=0.64, pre=(0.70,),
             knee=0.78,
             hinge=(0.88, 0.97, 1.06), shank=(1.14, 1.21, 1.28, 1.35, 1.42), red3=1.50, low=(1.57, 1.64),
             ankle=1.72, post=(1.79, 1.86), hm_t=0.919),
    armscye_out=9.0,                        # mm: the root loop this far proximal of the armscye ring
    # the HIP ring's plane: from its lowest point just under the crotch at the back of the thigh's inner side (the
    # gluteal fold) it rises toward the hip's side (hip_rise over 190 mm) and toward the front (front_rise over 80 mm:
    # the inguinal line rising laterally); planar, "from the gluteal fold to the inguinal line" (plan §6.2)
    # (front_rise 40 put the ring 30 mm under the crotch at the back of the thigh and the trunk's last rows folded
    # under the buttock into a shelf: the plane must stay under the crotch on the midline, so the rise is shared)
    hip_rise=55.0, front_rise=20.0, crotch_drop=12.0,
    pants_up=22.0,                          # mm: the trunk's last row this far over the hip ring, column by column,
    pants_floor=55.0,                       # and never lower than this over the crotch (mid-buttock at the back)
    relax=dict(iters=150, lam=0.5),
)
# the back ports on the back grid: columns c from the back midline (0) outward, rows from the yoke's back-top edge (0):
# the yoke's back face rows 0..RB, then the trunk's rows (RB + tr)
PLUGS = (
    dict(name='back_upper', kind='back_limb', c=(2, 8), row=(5, 11)),
    dict(name='back_shell', kind='back', c=(-4, 4), row=(13, 21), mid=True),
    # (on the flatter back beside the shell, not round the flank's turn: at c 8-14 the planar ring cut across the side's
    # curvature and printed ledges, H1's first figure)
    dict(name='back_lower', kind='back_limb', c=(6, 12), row=(14, 20)),
    # (rows 27-31: over the sacrum, two strips under the waist ring's row 25; at 28-32 its lower half spanned the top of
    # the gluteal cleft, the planar ring and its Coons interior filled the cleft there and printed a round pit; the H1
    # review)
    dict(name='sacral', kind='tail_base', c=(-2, 2), row=(27, 31), mid=True),
)


class BodyTopo:
    pass


def side_centres(n_o, nu, at):
    """nu units side by side, centred on the outer position `at` (their poles together on one side of a limb)"""
    first = at - 2 * (nu - 1)
    return [int((first + 4 * k) % n_o) for k in range(nu)]


def circ_mean_deg(a):
    r = np.radians(a)
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())))


def limb_frame(axis, side_ref):
    """the anatomical frame of a ring perpendicular to `axis`: e1 the front (+z) projected, e2 toward side_ref (the
    arm's top +y, the leg's lateral +x) turning from e1; returns e1, e2 (angles measured from e1 toward e2)"""
    ax = axis / np.linalg.norm(axis)
    e1 = np.array([0.0, 0.0, 1.0]) - ax[2] * ax
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    if e2 @ side_ref < 0:
        e2 = -e2
    return e1, e2


# ============================================================================================ hm08's hands and feet
def hm_loop_near(B, T, a, b, t_want, partset):
    """hm08's closed K 20 loop round the limb nearest the chain parameter t_want of the joint segment a -> b"""
    V = B.Vb
    ax = (b - a) / np.linalg.norm(b - a)
    Lseg = np.linalg.norm(b - a)
    best = None
    seen = set()
    for v in range(len(V)):
        if B.part[v] not in partset:
            continue
        t = (V[v] - a) @ ax / Lseg
        if abs(t - t_want) > 0.06:
            continue
        for w in T.nbr[v]:
            d = V[w] - V[v]
            if abs(d @ ax) > 0.5 * np.linalg.norm(d):
                continue
            L = T.loop_from(v, w, maxn=60)
            if L is None or len(L) != 20:
                continue
            k = frozenset(L)
            if k in seen:
                continue
            seen.add(k)
            tm = float(np.mean((V[L] - a) @ ax) / Lseg)
            if best is None or abs(tm - t_want) < abs(best[0] - t_want):
                best = (tm, L)
    assert best is not None, 'no K 20 loop of hm08 near the station'
    return best[1]


# ============================================================================================ the topology
def topology(log=print):
    """the body's topology, the left half (x >= 0; the midline vertices listed); hm08's hand and foot from the woman's
    pinned body (the same quads on both sexes)"""
    P = BODY
    CB, RF, RT, RB, CH = P['CB'], P['RF'], P['RT'], P['RB'], P['CH']
    R = RF + RT + RB
    n = [0]
    tag = {}

    def new(t):
        n[0] += 1
        tag[n[0] - 1] = t
        return n[0] - 1
    Q = []
    # ---- the YOKE: bar[c][r], c 0..CB (0 the midline), r 0..R; the neck hole's interior removed
    bar = -np.ones((CB + 1, R + 1), np.int64)
    for c in range(CB + 1):
        for r in range(R + 1):
            if c < CH and RF < r < RF + RT:
                continue
            bar[c, r] = new('yoke')
    for c in range(CB):
        for r in range(R):
            if c < CH and RF <= r < RF + RT:
                continue
            Q.append((bar[c, r], bar[c + 1, r], bar[c + 1, r + 1], bar[c, r + 1]))
    neck_base = [int(bar[c, RF]) for c in range(CH + 1)] + [int(bar[CH, r]) for r in range(RF + 1, RF + RT)] + \
                [int(bar[c, RF + RT]) for c in range(CH, -1, -1)]
    for v in neck_base:
        tag[v] = 'neck_base'
    # ---- the NECK: NN half rings, then the neck ring (shared with the head: its ids replaced at assembly)
    neck = [neck_base]
    for m in range(P['NN'] + 1):
        ring = [new('neck' if m < P['NN'] else 'neck_ring') for _ in range(len(neck_base))]
        a_, b_ = neck[-1], ring
        for k in range(len(a_) - 1):
            Q.append((a_[k], a_[k + 1], b_[k + 1], b_[k]))
        neck.append(ring)
    # ---- the ARM's root loop: the yoke's end column and the armpit edge (7 new vertices, back -> front)
    ab = [new('armpit') for _ in range(7)]
    root = [int(bar[CB, r]) for r in range(R + 1)] + ab
    # ---- the TRUNK: trunk[tr][tj], tj 0..32 (0 the front midline, 32 the back midline); row 0 the junction
    NT = P['NT']
    trunk = -np.ones((NT + 1, 33), np.int64)
    trunk[0, :CB + 1] = bar[:, 0]
    trunk[0, CB + 1:CB + 8] = ab[::-1]
    trunk[0, CB + 8:] = bar[::-1, R]
    for tr in range(1, NT + 1):
        for tj in range(33):
            trunk[tr, tj] = new('waist' if tr == P['TW'] else 'pants' if tr == NT else 'trunk')
    for tr in range(NT):
        for tj in range(32):
            Q.append((trunk[tr, tj], trunk[tr, tj + 1], trunk[tr + 1, tj + 1], trunk[tr + 1, tj]))
    # ---- the crotch BRIDGE (15 midline vertices, front -> back) and the leg's root loop (48)
    bridge = [new('bridge') for _ in range(P['BR'] - 1)]
    leg_root = [int(trunk[NT, tj]) for tj in range(33)] + bridge[::-1]
    # ---- the LIMB TUBES, each ring with its vertices' anatomical angles (degrees)
    tubes = {}

    def tube(name, first, ang0, stations):
        rings, angs, labels, bands = [list(first)], [np.asarray(ang0, np.float64)], ['root'], []
        for kind, K, lab in stations:
            prev = rings[-1]
            if kind == 'ring':
                ring = [new(lab) for _ in range(len(prev))]
                for k in range(len(prev)):
                    k1 = (k + 1) % len(prev)
                    Q.append((prev[k], prev[k1], ring[k1], ring[k]))
                rings.append(ring)
                angs.append(angs[-1].copy())
                labels.append(lab)
            else:
                nu = (len(prev) - K) // 2
                cs = side_centres(len(prev), nu, lab['medial'])
                Bd = HT.band(prev, K, cs, lambda: new('band'))
                Q.extend(Bd['quads'])
                # the inner ring under the outer vertices it hangs from (no shear across the band's strip); the rings
                # after it ease to equal angles by the next graft ring (or the next band's outer ring): equal angles at
                # once sheared the strip by the units' whole deficit on the far side (3 mm off on the thighs' fronts)
                h = angs[-1][Bd['hang']].copy()
                h = np.degrees(np.unwrap(np.radians(h)))
                rings.append(Bd['inner'])
                angs.append(h)
                labels.append(lab['name'])
                bands.append(dict(name=lab['name'], outer=len(rings) - 2, centres=cs, mids=Bd['mids'], hang=Bd['hang']))
        # the angles in one ordered pass: a plain ring copies the ring before it; a band's inner ring hangs under the
        # (already settled) outer ring's vertices, then eases to equal angles by the next graft ring, the next band's
        # outer ring or the tube's end
        GRAFT = ('armscye', 'elbow', 'wrist', 'hip', 'knee', 'ankle')
        binner = {b['outer'] + 1: b for b in bands}
        bouter = set(b['outer'] for b in bands)
        out = [angs[0]] + [None] * (len(rings) - 1)
        j = 1
        while j < len(rings):
            if j in binner:
                h = np.degrees(np.unwrap(np.radians(out[j - 1][binner[j]['hang']])))
                it = len(rings) - 1
                for k in range(j + 1, len(rings)):
                    if labels[k] in GRAFT or k in bouter or k in binner:
                        it = k if k not in binner else k - 1
                        break
                K = len(rings[j])
                step = 360.0 / K
                off = circ_mean_deg(h - step * np.arange(K))
                eq = off + step * np.arange(K)
                eq = h + ((eq - h + 180.0) % 360.0 - 180.0)
                span = max(it - j, 1)
                for k in range(j, it + 1):
                    f = (k - j) / span
                    out[k] = (1 - f) * h + f * eq
                j = it + 1
            else:
                out[j] = out[j - 1].copy()
                j += 1
        tubes[name] = dict(rings=rings, angs=out, labels=labels, bands=bands)
    A = P['arm']
    arm_st = [('ring', 32, 'armscye')] + [('ring', 32, 'arm_root')] * A['root_blend'] + \
             [('ring', 32, 'arm')] * len(A['up']) + [('ring', 32, 'elbow')] + \
             [('ring', 32, 'arm_hinge')] * len(A['hinge']) + [('ring', 32, 'arm')] * len(A['pre']) + \
             [('band', 24, dict(name='arm_red', medial=28))] + [('ring', 24, 'arm')] * len(A['fore']) + \
             [('ring', 24, 'wrist')] + [('ring', 24, 'arm')] * len(A['post'])
    # the root's angles: phi 4 at the front, 12 the arm's top, 20 the back, 28 the armpit
    tube('arm', root, (np.arange(32) - 4) * 11.25, arm_st)
    Lg = P['leg']
    # (hip_pre: a free ring between the root loop and the hip ring, two strips over the buttock's lower curve)
    leg_st = [('ring', 48, 'hip_pre'), ('ring', 48, 'hip')] + [('ring', 48, 'leg_root')] * Lg['root_blend'] + \
             [('ring', 48, 'leg')] * len(Lg['thigh']) + \
             [('band', 40, dict(name='leg_red1', medial=44))] + [('ring', 40, 'leg')] * len(Lg['mid']) + \
             [('band', 32, dict(name='leg_red2', medial=36))] + [('ring', 32, 'leg')] * len(Lg['pre']) + \
             [('ring', 32, 'knee')] + [('ring', 32, 'leg_hinge')] * len(Lg['hinge']) + \
             [('ring', 32, 'leg')] * len(Lg['shank']) + [('band', 24, dict(name='leg_red3', medial=28))] + \
             [('ring', 24, 'leg')] * len(Lg['low']) + [('ring', 24, 'ankle')] + [('ring', 24, 'leg')] * len(Lg['post'])
    # psi 8 at the front, 20 lateral, 32 the back-medial (the bridge's end), 44 medial
    tube('leg', leg_root, (np.arange(48) - 8) * 7.5, leg_st)
    # ---- hm08's HAND and FOOT, joined by 24 -> 20 bands matched by angle on the woman's pinned body
    z = np.load(os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', 'body_pinned_F.npz'))
    B = HR.MHBody('F', z['V'])
    T = HT.Topo(B.Q, len(B.Vb))
    J = B.joints
    Lmh = HR.mh_landmarks(B, log=lambda *x: None)
    hm = {}
    for name, a, b, partset, tipname, t_want, side_ref in (
            ('hand', J['l-elbow'], J['l-hand'], ('arm_L', 'hand_L'), 'fingertip', A['hm_t'], np.array([0, 1.0, 0])),
            ('foot', J['l-knee'], J['l-ankle'], ('leg_L', 'foot_L'), 'toe', Lg['hm_t'], np.array([1.0, 0, 0]))):
        loop = hm_loop_near(B, T, a, b, t_want, partset)
        keep = T.side_of(loop, T.vq[Lmh[tipname]][0])
        Qd = B.Q[keep]
        vd = np.unique(Qd)
        h2c = {int(v): new('hm_' + name) for v in vd.tolist()}
        Q.extend([tuple(h2c[v] for v in q) for q in Qd.tolist()])
        # the loop's anatomical angles about the limb's axis
        X = B.Vb[loop]
        c1 = X.mean(0)
        e1, e2 = limb_frame(b - a, side_ref)
        a_loop = np.degrees(np.arctan2((X - c1) @ e2, (X - c1) @ e1))
        tb = tubes['arm' if name == 'hand' else 'leg']
        last = tb['rings'][-1]
        a_last = tb['angs'][-1]
        # 2 units on the medial side: the outer position nearest the medial angle (arm 270 deg = the armpit side,
        # leg 270 deg = medial)
        med = int(np.argmin(np.abs(((a_last - 270.0) + 180.0) % 360.0 - 180.0)))
        cs = side_centres(len(last), 2, med)
        hang = HT.band_pattern(len(last), cs)
        best = None
        for d in (1, -1):
            L2 = list(loop[::d])
            A2 = a_loop[::d]
            for sh in range(len(L2)):
                Ar = np.roll(A2, -sh)
                cost = float(np.sum(1.0 - np.cos(np.radians(Ar - a_last[hang]))))
                if best is None or cost < best[0]:
                    best = (cost, L2[sh:] + L2[:sh], d)
        inner = [h2c[int(v)] for v in best[1]]
        Bd = HT.band(last, 20, cs, lambda: new('band'), inner_ids=inner)
        Q.extend(Bd['quads'])
        hm[name] = dict(h2c=h2c, loop=inner, quads=int(len(Qd)), hm_quads=int(len(Qd)), match_cost=best[0],
                        mids=Bd['mids'], centres=cs)
        log(f'[body] hm08 {name}: {len(Qd)} quads from its K 20 loop at t {t_want:.3f}; the 24 -> 20 band turned to it '
            f'(angle mismatch {np.degrees(np.arccos(max(-1.0, 1.0 - best[0] / 20.0))):.1f} deg rms-ish)')
    mid = set(int(v) for v in bar[0] if v >= 0)
    for ring in neck:
        mid.add(int(ring[0]))
        mid.add(int(ring[-1]))
    for tr in range(NT + 1):
        mid.add(int(trunk[tr, 0]))
        mid.add(int(trunk[tr, -1]))
    mid |= set(int(v) for v in bridge)
    # ---- the PLUGS on the back grid (topology: their blocks)
    def back(c, row):
        """the back grid's vertex at column c (>= 0 from the back midline) and row (0 the yoke's back-top edge)"""
        if row <= RB:
            return int(bar[c, RF + RT + row]) if c <= CB else -1
        tj = 32 - c
        return int(trunk[row - RB, tj]) if 0 <= tj <= 32 else -1
    plugs = {}
    for p in PLUGS:
        (c0, c1), (r0, r1) = p['c'], p['row']
        cs_ = range(max(c0, 0), c1 + 1)
        G = np.array([[back(c, row) for c in cs_] for row in range(r0, r1 + 1)], np.int64)
        assert (G >= 0).all(), f'the {p["name"]} block leaves the back grid'
        plugs[p['name']] = dict(kind=p['kind'], grid=G, mid=bool(p.get('mid')), c=(c0, c1), row=(r0, r1))
    BT = BodyTopo()
    BT.Q, BT.n, BT.tag = np.array(Q, np.int64), n[0], tag
    BT.bar, BT.ab, BT.root, BT.trunk, BT.bridge, BT.leg_root = bar, ab, root, trunk, bridge, leg_root
    BT.neck, BT.neck_base, BT.tubes, BT.hm, BT.plugs = neck, neck_base, tubes, hm, plugs
    BT.mid = np.array(sorted(mid), np.int64)
    BT.back = back
    nq = collections_counter(tag)
    log(f'[body] half body: {n[0]} vertices, {len(Q)} quads; {nq}')
    return BT


def collections_counter(tag):
    import collections
    c = collections.Counter(tag.values())
    return dict(sorted(c.items(), key=lambda kv: -kv[1])[:12])


# ============================================================================================ the placement
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def chain_point(A, t):
    s = int(np.clip(np.floor(t), 0, len(A) - 2))
    f = t - s
    return A[s] * (1 - f) + A[s + 1] * f


def chain_dir(A, t, blend=0.10):
    """the chain's direction at t, blended across each interior joint over +-blend (the hinge loops turn with it)"""
    dirs = [(A[s + 1] - A[s]) / np.linalg.norm(A[s + 1] - A[s]) for s in range(len(A) - 1)]
    s = int(np.clip(np.floor(t), 0, len(A) - 2))
    d = dirs[s]
    for j in range(1, len(A) - 1):
        if abs(t - j) < blend:
            w = smoothstep((t - (j - blend)) / (2 * blend))
            d = (1 - w) * dirs[j - 1] + w * dirs[j]
    return d / np.linalg.norm(d)


def ring_rays(tm, o, n, angs, side_ref, maxt=600.0):
    """K points on a PLANAR ring: rays in the plane (o, n) from o at the anatomical angles `angs` (deg, from the front
    toward side_ref); the first hits on the reference"""
    e1, e2 = limb_frame(n, side_ref)
    a = np.radians(np.asarray(angs, np.float64))
    D = np.cos(a)[:, None] * e1[None, :] + np.sin(a)[:, None] * e2[None, :]
    t, f, b = tm.ray(np.repeat(np.asarray(o, np.float64)[None, :], len(a), 0), D, maxt)
    assert (t > 0).all(), f'{int((t <= 0).sum())} ring rays missed the body'
    return o[None, :] + t[:, None] * D


def half_section(tm, y, zc, n_dense=361):
    """the trunk's horizontal half section at height y (the front midline to the back midline), dense: rays from
    (0, y, zc) at angles 0..180 deg from +z toward +x; returns the points and their cumulative arc length"""
    th = np.linspace(0.0, np.pi, n_dense)
    D = np.column_stack([np.sin(th), np.zeros_like(th), np.cos(th)])
    O = np.repeat(np.array([[0.0, y, zc]]), len(th), 0)
    t, f, b = tm.ray(O, D, 800.0)
    ok = t > 0
    assert ok.all(), f'a trunk ray missed at y {y:.0f}'
    X = O + t[:, None] * D
    X[[0, -1], 0] = 0.0
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))])
    return X, s, th


def neck_align(sex, gV, gF, off=30.0):
    """the z shift that centres GNM's lower neck on MakeHuman's: the arc-length centroids of their sections on the
    plane parallel to the neck base plane (through the suprasternale and the cervicale, level left to right), `off` mm
    over it, where both are closed loops on both sexes (the base plane itself cuts GNM's shoulders open). gV, gF: GNM's
    skin in the body frame with its height already set. Returns (dz, the MakeHuman and GNM centroids).
    (The first rule put the neck ring's centre over the mean of MakeHuman's neck vertices at its height, under
    MakeHuman's chin: GNM's lower neck sat 15-18 mm behind MakeHuman's, its nape 25-37 mm behind, and the three-ring
    blend bent the nape back, forward and back again: the collar at the neck's base, and craniovertebral angles of 63.5
    and 59.3 deg against ~50-56 standing; the H1 review)"""
    import json
    z = np.load(os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', f'body_pinned_{sex}.npz'))
    B = HR.MHBody(sex, z['V'])
    lmk = json.load(open(os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', 'body_pinned.json'),
                         encoding='utf-8'))[sex]['landmarks']
    S_, C_ = B.Vb[lmk['suprasternale']], B.Vb[lmk['cervicale']]
    nb = np.cross(np.array([1.0, 0.0, 0.0]), C_ - S_)
    nb /= np.linalg.norm(nb)
    if nb[1] < 0:
        nb = -nb
    o = 0.5 * (S_ + C_) + off * nb
    V, F = HR.mh_smooth(sex)
    cents = []
    for VV, FF in ((V, F), (gV, gF)):
        S, _ = HR.plane_section(VV, FF, o, nb)
        S = S[np.linalg.norm(S.mean(1) - o, axis=1) < 140.0]
        lp = max(HR.section_loops(S), key=len)
        Pl = np.vstack([lp, lp[:1]])
        seg = np.linalg.norm(np.diff(Pl, axis=0), axis=1)
        cents.append(((0.5 * (Pl[1:] + Pl[:-1])) * seg[:, None]).sum(0) / seg.sum())
    return float(cents[0][2] - cents[1][2]), cents[0], cents[1]


def place(BT, sex, head, log=print):
    """the body half's TARGETS for one sex. head: dict(ring=(48, 3) the K 48 neck ring in the body frame (index 0 the
    front midline), gnm_tm=TriMesh of GNM's skin in the body frame). Returns dict(P (BT.n, 3), records, reference)"""
    import json
    P = BODY
    CB, RF, RT, RB, CH = P['CB'], P['RF'], P['RT'], P['RB'], P['CH']
    R = RF + RT + RB
    z = np.load(os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', f'body_pinned_{sex}.npz'))
    B = HR.MHBody(sex, z['V'])
    V0, F = B.Vb.copy(), B.F
    lmk = json.load(open(os.path.join(HR.ROOT, 'work', 'bestiary', 'human', 'h1', 'ref', 'body_pinned.json'),
                         encoding='utf-8'))[sex]['landmarks']
    lm = lambda k: V0[lmk[k]]          # noqa: E731
    J = B.joints
    Xp = np.full((BT.n, 3), np.nan)
    recs = {}
    # ---- the neck: its base plane (through the suprasternale and the cervicale, level left to right), the top ring
    ring_top = np.asarray(head['ring'], np.float64)
    half_top = [0] + (list(range(1, 25)) if ring_top[1, 0] > 0 else list(range(47, 23, -1)))
    S_, C_ = lm('suprasternale'), lm('cervicale')
    nb = np.cross(np.array([1.0, 0.0, 0.0]), C_ - S_)
    nb /= np.linalg.norm(nb)
    if nb[1] < 0:
        nb = -nb
    ob = 0.5 * (S_ + C_)
    c_top = ring_top.mean(0)
    ax = c_top - ob
    Lax = np.linalg.norm(ax)
    ax /= Lax
    # ---- the reference: hm08's SMOOTH surface (its subdivision limit through the pinned vertices)
    V, F = HR.mh_smooth(sex)
    tm = HR.TriMesh(V, F)
    vn = tm.normals()
    s_out = 1.0 if float(np.mean(np.einsum('ij,ij->i', V - V.mean(0), vn))) > 0 else -1.0
    # ---- the NECK BASE loop (the yoke's hole): the base plane's section, its 48 points by arc length (front 16,
    # sides 8, back 16; the half: front midline -> left -> back midline)
    Sx, _ = HR.plane_section(V, F, ob, nb)
    Sx = Sx[np.linalg.norm(Sx.mean(1) - ob, axis=1) < 110.0]
    lp = max(HR.section_loops(Sx), key=len)
    e1, e2, _ = HR.plane_basis(nb, np.array([0.0, 0.0, 1.0]))
    ang = np.arctan2((lp - ob) @ e2, (lp - ob) @ e1)
    if np.mean(((lp - ob) @ np.array([1.0, 0, 0]))[np.abs(ang - 0.5 * np.pi) < 0.6]) < 0:
        e2 = -e2
        ang = np.arctan2((lp - ob) @ e2, (lp - ob) @ e1)
    o_ = np.argsort(ang)
    half = lp[o_][(ang[o_] >= -1e-3) & (ang[o_] <= np.pi + 1e-3)]
    half = np.vstack([half[:1] * np.array([0, 1, 1]), half, half[-1:] * np.array([0, 1, 1])])
    cs_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(half, axis=0), axis=1))])
    sfr = np.concatenate([np.linspace(0, 1 / 3, CH + 1), np.linspace(1 / 3, 2 / 3, RT + 1)[1:-1],
                          np.linspace(2 / 3, 1.0, CH + 1)])
    base_pts = np.column_stack([np.interp(sfr * cs_[-1], cs_, half[:, k]) for k in range(3)])
    base_pts[[0, -1], 0] = 0.0
    Xp[BT.neck_base] = base_pts
    # the neck rings: between the base loop (MakeHuman's) and the top ring (GNM's), by rays from the neck's axis, each
    # target's distance from the axis a MONOTONE CUBIC from the base point's to the ring point's (Hermite, its end slopes
    # MakeHuman's just over the base and GNM's just under the ring along the same rays, Fritsch-Carlson limited): the
    # plan's blend from GNM's surface at the ring to MakeHuman's at the neck's base, smooth at both ends. (Sampling both
    # references at the rings themselves and blending them took GNM's lower neck where it already flares into ITS OWN
    # shoulders, 40-50 mm wider at the sides 15-30 mm over the base plane: the neck bulged at the sides over the base and
    # pinched in to MakeHuman's base, a collar seen from every side; the H1 review)
    top_half = ring_top[half_top]
    Xp[BT.neck[-1]] = top_half

    def neck_ray(fr):
        pts = (1 - fr) * base_pts + fr * top_half
        cc = (1 - fr) * ob + fr * c_top
        d = pts - cc
        d = d - np.outer(d @ ax, ax)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        return cc[None, :] + np.outer((pts - cc) @ ax, ax), d
    o0_, d0_ = neck_ray(0.0)
    o1_, d1_ = neck_ray(1.0)
    rad0 = np.einsum('ij,ij->i', base_pts - o0_, d0_)
    rad1 = np.einsum('ij,ij->i', top_half - o1_, d1_)
    hs = 0.2
    t_mh, _, _ = tm.ray(*neck_ray(hs), 300.0)
    t_g, _, _ = head['gnm_tm'].ray(*neck_ray(1.0 - hs), 300.0)
    sec = rad1 - rad0
    m0 = np.where(t_mh > 0, (t_mh - rad0) / hs, sec)
    m1 = np.where(t_g > 0, (rad1 - t_g) / hs, sec)
    for mm in (m0, m1):
        mm[np.sign(mm) != np.sign(sec)] = 0.0
        mm[:] = np.sign(mm) * np.minimum(np.abs(mm), 3.0 * np.abs(sec))
    for m in range(1, P['NN'] + 1):
        fr = m / (P['NN'] + 1)
        o2, d = neck_ray(fr)
        rad = (2 * fr ** 3 - 3 * fr ** 2 + 1) * rad0 + (fr ** 3 - 2 * fr ** 2 + fr) * m0 + \
              (-2 * fr ** 3 + 3 * fr ** 2) * rad1 + (fr ** 3 - fr ** 2) * m1
        Xp[BT.neck[m]] = o2 + rad[:, None] * d
        Xp[BT.neck[m][0], 0] = Xp[BT.neck[m][-1], 0] = 0.0
    # ---- the ARM
    A = P['arm']
    armA = np.array([J['l-shoulder'], J['l-elbow'], J['l-hand']])
    up = np.array([0.0, 1.0, 0.0])
    tb = BT.tubes['arm']
    # the ARMSCYE ring: the plane through the axilla (just distal of its apex) and the acromion, containing the front
    # direction; rays from the shoulder joint's foot on it
    Ap = lm('axilla') + 4.0 * (armA[1] - armA[0]) / np.linalg.norm(armA[1] - armA[0])
    Cp = lm('acromion')
    n1 = np.cross(Cp - Ap, np.array([0.0, 0.0, 1.0]))
    n1 /= np.linalg.norm(n1)
    if n1 @ (armA[1] - armA[0]) < 0:
        n1 = -n1
    o1 = armA[0] - ((armA[0] - Ap) @ n1) * n1
    r1 = ring_rays(tm, o1, n1, tb['angs'][1], up)
    Xp[tb['rings'][1]] = r1
    recs['armscye'] = dict(kind='leg_fore', cut='shoulder', K=32, loop=tb['rings'][1], centre=o1.tolist(),
                           normal=n1.tolist())
    # the ROOT loop: one strip proximal, on the skin
    r0 = tm.closest(r1 - P['armscye_out'] * n1[None, :])[0]
    Xp[tb['rings'][0]] = r0
    # the blend rings: their planes turn from the armscye's to the first station's, their centres move along
    NBa = A['root_blend']
    a_f, d_f = chain_point(armA, A['up'][0]), chain_dir(armA, A['up'][0])
    for j in range(1, NBa + 1):
        f = j / (NBa + 1)
        nn_ = (1 - f) * n1 + f * d_f
        Xp[tb['rings'][1 + j]] = ring_rays(tm, (1 - f) * o1 + f * a_f, nn_ / np.linalg.norm(nn_), tb['angs'][1 + j],
                                           up)
    st = list(A['up']) + [A['elbow']] + list(A['hinge']) + list(A['pre']) + [A['red']] + list(A['fore']) + \
        [A['wrist']] + list(A['post'])
    for k, t in enumerate(st):
        ri = k + 2 + NBa
        o = chain_point(armA, t)
        n_ = chain_dir(armA, t, A.get('turn', 0.10))
        Xp[tb['rings'][ri]] = ring_rays(tm, o, n_, tb['angs'][ri], up)
        lab = tb['labels'][ri]
        if lab in ('elbow', 'wrist'):
            recs[lab] = dict(kind='leg_fore', cut=lab, K=len(tb['rings'][ri]), loop=tb['rings'][ri], centre=o.tolist(),
                             normal=n_.tolist(), t=t)
    for name, partset in (('hand', None), ('foot', None)):
        for hv, cv in BT.hm[name]['h2c'].items():
            Xp[cv] = V0[hv]
    # ---- the LEG
    Lg = P['leg']
    legA = np.array([J['l-upper-leg'], J['l-knee'], J['l-ankle']])
    tl = BT.tubes['leg']
    yc = lm('crotch')[1]
    # the HIP ring: a plane through a point under the crotch on the midline, rising toward the hip's side and toward
    # the front: y = y0 + a x + b (z - zc)
    zc_t = float(np.interp(yc - P['crotch_drop'], [legA[1][1], legA[0][1]], [legA[1][2], legA[0][2]]))
    P1 = np.array([0.0, yc - P['crotch_drop'], zc_t])
    nh = np.array([P['hip_rise'] / 190.0, -1.0, P['front_rise'] / 80.0])
    nh /= np.linalg.norm(nh)
    # the thigh axis' crossing with the plane
    dl = legA[1] - legA[0]
    tq = ((P1 - legA[0]) @ nh) / (dl @ nh)
    oh = legA[0] + tq * dl
    lat = np.array([1.0, 0.0, 0.0])
    Xp[tl['rings'][2]] = ring_rays(tm, oh, nh, tl['angs'][2], lat)
    recs['hip'] = dict(kind='leg_hind', cut='hip', K=48, loop=tl['rings'][2], centre=oh.tolist(), normal=nh.tolist())
    NBl = Lg['root_blend']
    a_f, d_f = chain_point(legA, Lg['thigh'][0]), chain_dir(legA, Lg['thigh'][0])
    for j in range(1, NBl + 1):
        f = j / (NBl + 1)
        nn_ = (1 - f) * nh + f * d_f
        Xp[tl['rings'][2 + j]] = ring_rays(tm, (1 - f) * oh + f * a_f, nn_ / np.linalg.norm(nn_), tl['angs'][2 + j],
                                           lat)
    st = list(Lg['thigh']) + [Lg['red1']] + list(Lg['mid']) + [Lg['red2']] + list(Lg['pre']) + [Lg['knee']] + \
        list(Lg['hinge']) + list(Lg['shank']) + [Lg['red3']] + list(Lg['low']) + [Lg['ankle']] + list(Lg['post'])
    for k, t in enumerate(st):
        ri = k + 3 + NBl
        o = chain_point(legA, t)
        n_ = chain_dir(legA, t)
        Xp[tl['rings'][ri]] = ring_rays(tm, o, n_, tl['angs'][ri], lat)
        lab = tl['labels'][ri]
        if lab in ('knee', 'ankle'):
            recs[lab] = dict(kind='leg_hind', cut=lab, K=len(tl['rings'][ri]), loop=tl['rings'][ri], centre=o.tolist(),
                             normal=n_.tolist(), t=t)
    # ---- the TRUNK: the junction row (the yoke's lower edges between the midline and the armpit corners, the armpit
    # edge from the root loop), then horizontal rows; the waist on the omphalion's plane at equal angles
    bar, trunk = BT.bar, BT.trunk
    # the trunk section's centre z per height: the trunk vertices' mean z in 10 mm bands, smoothed
    trv = np.isin(B.part, ('trunk', 'neck'))
    yy = np.arange(500.0, 1700.0, 10.0)
    czv = np.array([V0[trv & (np.abs(V0[:, 1] - h) < 15.0), 2].mean() if (trv & (np.abs(V0[:, 1] - h) < 15.0)).any()
                    else np.nan for h in yy])
    ok_ = ~np.isnan(czv)
    czv = np.convolve(np.pad(np.interp(yy, yy[ok_], czv[ok_]), 5, mode='edge'), np.ones(11) / 11, mode='valid')
    cz = lambda y: float(np.interp(y, yy, czv))      # noqa: E731
    front_c, back_c = r0[0], r0[24]
    for corner, idx in ((front_c, [int(bar[c, 0]) for c in range(CB + 1)]),
                        (back_c, [int(bar[c, R]) for c in range(CB + 1)])):
        y = corner[1]
        X, s, th = half_section(tm, y, cz(y))
        thc = np.arctan2(corner[0], corner[2] - cz(y))
        sc = float(np.interp(thc, th, s))
        if corner is back_c:
            sb = s[-1] - sc
            pts = np.column_stack([np.interp(s[-1] - np.linspace(0, sb, CB + 1), s, X[:, k]) for k in range(3)])
        else:
            pts = np.column_stack([np.interp(np.linspace(0, sc, CB + 1), s, X[:, k]) for k in range(3)])
        pts[0, 0] = 0.0
        pts[-1] = corner
        Xp[idx] = pts
    # the trunk rows' heights: row 1 under the junction, the waist at the omphalion, the last over the crotch
    y_j = min(front_c[1], back_c[1], float(np.min(r0[24:, 1])))
    y_w = lm('omphalion')[1]
    NT, TW = P['NT'], P['TW']
    # the last row follows the hip ring column by column (the leg's root columns psi = tj), pants_up over it; the
    # rows between the waist and it blend the waist's level row into it
    Hh = Xp[tl['rings'][2]][:33]
    czh = cz(float(Hh[:, 1].mean()))
    y_pc = np.maximum(Hh[:, 1] + P['pants_up'], yc + P['pants_floor'])
    y_pc[0], y_pc[-1] = y_pc[1], y_pc[-2]
    th_pc = np.arctan2(Hh[:, 0], Hh[:, 2] - czh)
    th_pc[0], th_pc[-1] = 0.0, np.pi
    th_pc = np.maximum.accumulate(np.clip(th_pc, 0.0, np.pi))
    # behind the hip's side the columns spread evenly to the back midline: the hip ring's back vertices sit behind the
    # THIGH (~130 deg about the trunk's axis at psi 180), so following them column by column left the last column a
    # ~50 deg jump to the midline, one quad ~100 mm wide over the lower buttock (the H1 review)
    j_lat = int(np.argmin(np.abs(th_pc - 0.5 * np.pi)))
    th_pc[j_lat:] = np.linspace(th_pc[j_lat], np.pi, 33 - j_lat)
    y_p = float(y_pc.max())
    ys = np.linspace(y_j, y_w, TW + 1)[1:]
    # the junction row's arc fractions (per column) along its own half: its columns ease into the waist's angles
    j_pts = Xp[trunk[0]]
    j_s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(j_pts, axis=0), axis=1))])
    j_s /= j_s[-1]
    for tr in range(1, TW + 1):
        y = ys[tr - 1]
        X, s, th = half_section(tm, y, cz(y))
        th_eq = np.linspace(0.0, np.pi, 33)
        s_eq = np.interp(th_eq, th, s) / s[-1]
        wgt = tr / TW
        frac = s_eq if tr == TW else (1 - wgt) * j_s + wgt * s_eq
        pts = np.column_stack([np.interp(frac * s[-1], s, X[:, k]) for k in range(3)])
        pts[[0, -1], 0] = 0.0
        Xp[trunk[tr]] = pts
    th_w = np.linspace(0.0, np.pi, 33)
    for tr in range(TW + 1, NT + 1):
        f = (tr - TW) / (NT - TW)
        y_c = (1 - f) * y_w + f * y_pc
        th_c = (1 - f) * th_w + f * th_pc
        O = np.column_stack([np.zeros(33), y_c, np.array([cz(v) for v in y_c])])
        D = np.column_stack([np.sin(th_c), np.zeros(33), np.cos(th_c)])
        t_, _, _ = tm.ray(O, D, 800.0)
        assert (t_ > 0).all(), f'a lower trunk ray missed (row {tr})'
        pts = O + t_[:, None] * D
        pts[[0, -1], 0] = 0.0
        Xp[trunk[tr]] = pts
    recs['waist'] = dict(kind='body_region', cut='waist', K=64, centre=[0.0, y_w, cz(y_w)], normal=[0.0, 1.0, 0.0],
                         row=TW)
    # the BRIDGE: the crotch's midline curve under the last row, front -> back, 16 edges: the FIRST hit of each ray in
    # the midline plane from a point over the crotch (inside the pelvis), fanned from the front vertex to the back one.
    # (The midline plane's whole section sorted by angle took in the inner thighs where they touch across the midline:
    # the bridge zigzagged 40 mm up and down under the crotch and folded ~100 cage quads there; the H1 review)
    pf, pb = Xp[trunk[NT, 0]], Xp[trunk[NT, -1]]
    cen = np.array([0.0, y_p, 0.5 * (pf[2] + pb[2])])
    a_f = np.arctan2(-(pf[1] - cen[1]), pf[2] - cen[2])               # 0 at the front, pi/2 under, pi at the back
    a_b = np.arctan2(-(pb[1] - cen[1]), pb[2] - cen[2])
    aa = np.linspace(a_f, a_b, 722)[1:-1]
    Dm = np.column_stack([np.zeros_like(aa), -np.sin(aa), np.cos(aa)])
    Om = np.repeat(cen[None, :], len(aa), 0)
    tmid, _, _ = tm.ray(Om, Dm, 800.0)
    okm = tmid > 0
    curve = np.vstack([pf[None, :], (Om + tmid[:, None] * Dm)[okm], pb[None, :]])
    curve[:, 0] = 0.0
    cs2 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))])
    bpts = np.column_stack([np.interp(np.linspace(0, cs2[-1], P['BR'] + 1)[1:-1], cs2, curve[:, k]) for k in range(3)])
    Xp[BT.bridge] = bpts
    # the free ring between the legs' root loop and the hip ring: midway, on the skin (then relaxed)
    Xp[tl['rings'][1]] = tm.closest(0.5 * (Xp[tl['rings'][0]] + Xp[tl['rings'][2]]))[0]
    # ---- the YOKE: its midline column (the profiles), its end column (the root loop), the hole (the neck base); the
    # rest interpolated, then relaxed
    Xp[[int(bar[CB, r]) for r in range(R + 1)]] = r0[:R + 1]
    Xp[BT.ab] = r0[R + 1:]
    yf_, zf_ = HR._profile(V, F, front=True)
    yb_, zb_ = HR._profile(V, F, front=False)

    def prof(y0, y1, n_, front):
        yy = np.linspace(y0, y1, 400)
        zz = np.interp(yy, yf_, zf_) if front else np.interp(yy, yb_, zb_)
        Cc = np.column_stack([np.zeros_like(yy), yy, zz])
        cs3 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Cc, axis=0), axis=1))])
        return np.column_stack([np.interp(np.linspace(0, cs3[-1], n_), cs3, Cc[:, k]) for k in range(3)])
    Xp[[int(bar[0, r]) for r in range(RF + 1)]] = prof(Xp[bar[0, 0], 1], Xp[bar[0, RF], 1], RF + 1, True)
    Xp[[int(bar[0, r]) for r in range(RF + RT, R + 1)]] = prof(Xp[bar[0, RF + RT], 1], Xp[bar[0, R], 1], RB + 1, False)
    for r in range(R + 1):
        for c in range(1, CB):
            v = int(bar[c, r])
            if v < 0 or not np.isnan(Xp[v, 0]):
                continue
            if RF <= r <= RF + RT and c > CH:
                a_, b_ = int(bar[CH, r]), int(bar[CB, r])
                f2 = (c - CH) / (CB - CH)
            else:
                a_, b_ = int(bar[0, r]), int(bar[CB, r])
                f2 = c / CB
            Xp[v] = (1 - f2) * Xp[a_] + f2 * Xp[b_]
    # the reduction units' middle vertices: between their outer apex and inner apex, on the skin
    mids = []
    for tname in ('arm', 'leg'):
        tt_ = BT.tubes[tname]
        for bd in tt_['bands']:
            outer = tt_['rings'][bd['outer']]
            inner = tt_['rings'][bd['outer'] + 1]
            for (m, c, ai) in bd['mids']:
                mids.append((m, outer[c], inner[ai]))
    for name in ('hand', 'foot'):
        tname = 'arm' if name == 'hand' else 'leg'
        outer = BT.tubes[tname]['rings'][-1]
        inner = BT.hm[name]['loop']
        for (m, c, ai) in BT.hm[name]['mids']:
            mids.append((m, outer[c], inner[ai]))
    for (m, a_, b_) in mids:
        Xp[m] = 0.5 * (Xp[a_] + Xp[b_])
    mv = [m for (m, _, _) in mids]
    Xp[mv] = tm.closest(Xp[mv])[0]
    miss = np.nonzero(np.isnan(Xp[:, 0]))[0]
    assert not len(miss), f'{len(miss)} body vertices without a target: {[BT.tag[int(v)] for v in miss[:8]]}'
    return dict(P=Xp, recs=recs, tm=tm, V=V, F=F, s_out=s_out, B=B, lm=lmk, neck_base=(ob, nb), y=dict(
        junction=y_j, waist=y_w, pants=y_p, crotch=yc), half_top=half_top)


def fixed_mask(BT):
    """the body half's vertices the relaxation holds: the neck base and the neck ring, every limb ring (the arm's root
    loop included) and band middle, hm08's hands and feet, the waist row, the bridge; free: the yoke, the junction row's
    edges, the trunk's other rows, the last row (the legs' root loops less the bridge) and the free ring under it
    (hip_pre: placed midway at the closest point of the root loop's and the hip ring's midpoint, ~100 mm inside the
    buttock at the back, and never relaxed, it sat wherever that point fell; the H1 review), the neck's middle rings"""
    fx = np.zeros(BT.n, bool)
    for ring in BT.neck:
        fx[ring] = True
    for tname in ('arm', 'leg'):
        rings = BT.tubes[tname]['rings']
        for i, r in enumerate(rings):
            if tname == 'leg' and i in (0, 1):
                continue
            fx[r] = True
        for bd in BT.tubes[tname]['bands']:
            for (m, _, _) in bd['mids']:
                fx[m] = True
    for name in ('hand', 'foot'):
        fx[list(BT.hm[name]['h2c'].values())] = True
        for (m, _, _) in BT.hm[name]['mids']:
            fx[m] = True
    fx[BT.trunk[BODY['TW']]] = True
    # the crotch: the bridge held where it was built (relaxed on the whole reference, its closest points jumped between
    # the thighs and folded 12,405 limit triangles under the crotch: H1's gates); the free ring under it now relaxes on
    # the reference's own half (relax_body)
    fx[BT.bridge] = True
    return fx


def coons_grid(GX):
    """a grid's interior positions by a Coons patch over its boundary (GX: rows x cols x 3; interior overwritten)"""
    rows, cols = GX.shape[:2]
    out = GX.copy()
    for i in range(1, rows - 1):
        for j in range(1, cols - 1):
            u, v = i / (rows - 1), j / (cols - 1)
            out[i, j] = ((1 - v) * GX[i, 0] + v * GX[i, -1] + (1 - u) * GX[0, j] + u * GX[-1, j]
                         - ((1 - u) * (1 - v) * GX[0, 0] + u * (1 - v) * GX[-1, 0] + (1 - u) * v * GX[0, -1] +
                            u * v * GX[-1, -1]))
    return out


def place_plugs(BT, Xp, tm, s_out, radius_k=0.9, log=print, planar_tol=None):
    """the back ports: each block's boundary re-placed on a PLANAR ring at equal angles (human_head.plane_ring: a circle
    projected onto the skin, flattened on its plane), vertex 0 on the frame's tangent (up the back for the midline
    ports, the block's first axis otherwise), the interior by a Coons patch on the skin. Returns the records"""
    from . import human_head as HH
    recs = {}
    closest = lambda X: tm.closest(X)            # noqa: E731
    M = np.array([-1.0, 1.0, 1.0])
    for name, pl in BT.plugs.items():
        G = pl['grid']
        rows, cols = G.shape
        if pl['mid']:
            left = [G[0, j] for j in range(cols)] + [G[i, cols - 1] for i in range(1, rows)] + \
                   [G[rows - 1, j] for j in range(cols - 2, -1, -1)]
            K = 2 * (len(left) - 1)
            ctr = Xp[G.ravel()].mean(0) * np.array([0.0, 1.0, 1.0])
            p0, f0, b0 = tm.closest(ctr[None, :])
            c = p0[0]
            n0 = s_out * tm.normal_at(f0, b0)[0]
            t0 = Xp[G[0, 0]] - Xp[G[-1, 0]]
            r0 = radius_k * float(np.mean(np.linalg.norm(Xp[left] - c, axis=1)))
            ring, orig, fr = HH.plane_ring(None, c, n0, t0, K, r0, closest=closest, planar_tol=planar_tol,
                                           ray=tm.ray)
            if fr['t1'][0] < 0:                  # turn toward the left (+x) first
                ring = np.vstack([ring[:1], ring[1:][::-1]])
            Xp[left] = ring[:len(left)]
            Xp[left[0], 0] = Xp[left[-1], 0] = 0.0
            # the interior: the full block (its right half mirrored) by Coons, the left half kept
            GX = np.zeros((rows, 2 * cols - 1, 3))
            for j in range(cols):
                GX[:, cols - 1 + j] = Xp[G[:, j]]
                GX[:, cols - 1 - j] = Xp[G[:, j]] * M
            GX = coons_grid(GX)
            inner = G[1:-1, :-1].ravel()
            Xin = GX[1:-1, cols - 1:-1].reshape(-1, 3)
            Xin = tm.closest(Xin)[0]
            Xp[inner] = Xin
            Xp[G[1:-1, 0], 0] = 0.0
            loop_full = left
        else:
            loop, inner = HT.grid_loop(G)
            K = len(loop)
            ctr = Xp[G.ravel()].mean(0)
            p0, f0, b0 = tm.closest(ctr[None, :])
            c = p0[0]
            n0 = s_out * tm.normal_at(f0, b0)[0]
            t0 = Xp[G[-1, cols // 2]] - Xp[G[0, cols // 2]]
            r0 = radius_k * float(np.mean(np.linalg.norm(Xp[loop] - c, axis=1)))
            ring, orig, fr = HH.plane_ring(None, c, n0, t0, K, r0, closest=closest, planar_tol=planar_tol,
                                           ray=tm.ray)
            cur = Xp[loop]

            def sarea(Z):
                Z2 = np.column_stack([(Z - c) @ fr['t0'], (Z - c) @ fr['t1']])
                return 0.5 * np.sum(Z2[:, 0] * np.roll(Z2[:, 1], -1) - np.roll(Z2[:, 0], -1) * Z2[:, 1])
            if np.sign(sarea(ring)) != np.sign(sarea(cur)):
                ring = ring[::-1]
            best = None
            for sh in range(K):
                cand = np.roll(ring, -sh, axis=0)
                cost = float(np.linalg.norm(cand - cur, axis=1).sum())
                if best is None or cost < best[0]:
                    best = (cost, cand)
            Xp[loop] = best[1]
            GX = coons_grid(Xp[G])
            Xp[G[1:-1, 1:-1].ravel()] = tm.closest(GX[1:-1, 1:-1].reshape(-1, 3))[0]
            loop_full = loop
        recs[name] = dict(kind=pl['kind'], K=K, loop=[int(v) for v in loop_full], mid=pl['mid'], centre=c.tolist(),
                          normal=fr['normal'].tolist(), t0=fr['t0'].tolist(), radius=fr['radius'],
                          off_skin=fr['off_skin'], planarity=fr['planarity'], grid=G)
    return recs


def relax_body(BT, Xp, tm, fixed, mir, mid, iters=150, lam=0.5, log=print, Qfull=None):
    """the free vertices relaxed on the reference: uniform Laplacian steps (on the full mirrored cage), each pulled back
    to the closest point of the reference's OWN HALF (x >= 0: the half's vertices never land on the other thigh where
    the thighs touch under the crotch, which is why the free ring under the crotch was held at first); the midline kept
    at x 0"""
    cx = tm.V[tm.F].mean(1)[:, 0]
    tm = HR.TriMesh(tm.V, tm.F[cx > -0.5])
    n = len(Xp)
    E = np.unique(np.sort(np.concatenate([Qfull[:, [0, 1]], Qfull[:, [1, 2]], Qfull[:, [2, 3]], Qfull[:, [3, 0]]]),
                          axis=1), axis=0)
    import scipy.sparse as sp
    nf = int(Qfull.max()) + 1
    Adj = sp.csr_matrix((np.ones(2 * len(E)), (np.concatenate([E[:, 0], E[:, 1]]), np.concatenate([E[:, 1], E[:, 0]]))),
                        shape=(nf, nf))
    Avg = sp.diags(1.0 / np.maximum(np.asarray(Adj.sum(1)).ravel(), 1)) @ Adj
    M = np.array([-1.0, 1.0, 1.0])
    Xf = np.zeros((nf, 3))
    Xf[:n] = Xp
    Xf[mir[:n]] = Xp * M
    free = np.nonzero(~fixed)[0]
    for it in range(iters):
        Xn = Xf[:n].copy()
        Xn[free] = Xf[free] + lam * ((Avg @ Xf)[free] - Xf[free])
        Xn[free] = tm.closest(Xn[free])[0]
        Xn[mid, 0] = 0.0
        Xf[:n] = Xn
        Xf[mir[:n]] = Xn * M
    return Xf[:n]
