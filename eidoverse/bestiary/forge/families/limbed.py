"""LIMBED family generator: quadrupeds, the wolf first (work/bestiary/research/WOLF_PLAN.md §4.1, §2.4, §6.1).

W1: the rest chain and the skeleton. W2: the skin block-out, build_skin_sdf (§4.2; module section "the skin" below).
The cage (§4.4) comes at W4.

rest_chain(spec) solves the bind pose. The limbs are wolf_numbers.py's fore() and hind() in metres: in the sagittal
plane from the ground up, the forepaw MCP and hind MTP at their pad heights, the measured standing angles, and the
metatarsus angle solved EXACTLY (brentq; the plan's 78.5 deg is a 0.5 deg scan) so the MTP sits
rest.hind_paw_behind_hip behind the hip joint. They are lifted to 3D with §2.4's half-widths (each joint at its own
|x|), the hindlimb at z 0 (the root under the hip joints) and the shoulder joint at z = body_len_wh WH -
shoulder_hip_offset (§10). Then the spine (vertebral groups between the lumbosacral and cervicothoracic joints), the
neck (rising rest.neck_pitch from C7/T1, its reach solved so the poll sits rest.occiput_ahead_wh WH ahead of the
withers), the head's landmarks (the head archetype's palate frame), the tail and the paws.

skeleton(spec, chain) builds rig.Skeleton with §6.1's 118 joints; parents come before children, and twist joints,
volume helpers, breathers and IK targets are leaves (AG 05.11). Frames (rig.frame_from): x along the bone to its child
(or to a leaf's tip); y the side the child folds toward, chosen per joint (FOLD) so that a positive rotation about
z = x cross y folds the joint the anatomical way (AG 05.7): limb flexion (shoulder: elbow back; elbow: paw forward;
carpus: paw back; hip: stifle forward; stifle: hock back; hock: paw forward; digits curl down), ventral flexion of the
spine, neck, head and tail, the jaw opening, the ears folding back, the gaze up, the lids closing. The scapula has no
flexion: positive is retraction (the shoulder joint swings back). The right side is the left reflected under one
written rule (AG 05.8): p_R = M p_L and F_R = M F_L diag(1, 1, -1), M = diag(-1, 1, 1); x keeps pointing to the child,
y keeps the fold side and the bend axis z flips, so equal bends mirror (twist and side swing flip sign).
sk.meta[name]: role, tier (0 body, 1 digits / twist / helpers, 2 face), side, fold, tip, driver, parent.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from .. import rig as RG
from .. import sdf as S_
from ..heads import archetype

M_MIRROR = np.diag([-1.0, 1.0, 1.0])
FLIP_Z = np.diag([1.0, 1.0, -1.0])
CRANIAL, CAUDAL = np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0])
DORSAL, VENTRAL = np.array([0.0, 1.0, 0.0]), np.array([0.0, -1.0, 0.0])


def mirror_point(p):
    return M_MIRROR @ np.asarray(p, np.float64)


def mirror_frame(F):
    """AG 05.8's written rule: reflect across the sagittal plane, then negate only the bend axis z"""
    return M_MIRROR @ np.asarray(F, np.float64) @ FLIP_Z


def _u2(a):
    return np.array([np.cos(a), np.sin(a)])


def _wrap(a):
    return float(np.arctan2(np.sin(a), np.cos(a)))


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


# --------------------------------------------------------------------------------------------- the sagittal solve
def fore_sagittal(spec, shoulder=None, elbow=None):
    """wolf_numbers.fore() in metres: the forelimb from the ground up, x forward, y up, the MCP at x = 0; the joint
    points and the humerus's and scapula's inclinations (degrees)"""
    jc, r = spec['jc'], spec['rest']
    sh = r['shoulder'] if shoulder is None else shoulder
    el = r['elbow'] if elbow is None else elbow
    pastern = 90.0 - r['carpus_ext']                       # the metacarpus above the horizontal
    mcp = np.array([0.0, jc['mcp_h']])
    a_mc = np.radians(180.0 - pastern)                     # MCP -> carpus: up and back
    carpus = mcp + jc['carpus_mcp'] * _u2(a_mc)
    a_r = np.radians(90.0 + r['radius_lean'])              # carpus -> elbow: up, a little back
    elbow_p = carpus + jc['radius'] * _u2(a_r)
    a_h = _wrap(a_r + np.pi + np.radians(el))              # elbow -> shoulder: the included angle round, up and forward
    assert np.cos(a_h) > 0 and np.sin(a_h) > 0, np.degrees(a_h)
    shoulder_p = elbow_p + jc['humerus'] * _u2(a_h)
    a_s = _wrap(a_h + np.pi - np.radians(sh))              # shoulder -> the scapula's dorsal border: up and back
    assert np.cos(a_s) < 0 and np.sin(a_s) > 0, np.degrees(a_s)
    top = shoulder_p + jc['scapula'] * _u2(a_s)
    return dict(mcp=mcp, carpus=carpus, elbow=elbow_p, shoulder=shoulder_p, scapula_top=top, pastern=pastern,
                humerus_below_h=float(np.degrees(a_h)), scapula_above_h=float(180.0 - np.degrees(a_s)))


def hind_sagittal(spec, pastern, stifle=None, hock=None):
    """wolf_numbers.hind() in metres: the hindlimb from the ground up, the MTP at x = 0, the metatarsus `pastern`
    degrees above the horizontal"""
    jc, r = spec['jc'], spec['rest']
    st = r['stifle'] if stifle is None else stifle
    hk = r['hock'] if hock is None else hock
    mtp = np.array([0.0, jc['mtp_h']])
    a_mt = np.radians(180.0 - pastern)                     # MTP -> hock: up and back
    hock_p = mtp + jc['hock_mtp'] * _u2(a_mt)
    a_t = _wrap(a_mt + np.pi + np.radians(hk))             # hock -> stifle: up and forward
    if np.cos(a_t) < 0:
        a_t = _wrap(a_mt + np.pi - np.radians(hk))
    stifle_p = hock_p + jc['tibia'] * _u2(a_t)
    a_f = _wrap(a_t + np.pi - np.radians(st))              # stifle -> hip: up and back
    if np.cos(a_f) > 0:
        a_f = _wrap(a_t + np.pi + np.radians(st))
    hip = stifle_p + jc['femur'] * _u2(a_f)
    return dict(mtp=mtp, hock=hock_p, stifle=stifle_p, hip=hip, metatarsus_above_h=float(pastern),
                tibia_above_h=float(np.degrees(a_t)), femur_below_h=float(180.0 - np.degrees(a_f)))


def solve_hind(spec, stifle=None, hock=None, behind=None):
    """the hindlimb with its metatarsus angle solved so the MTP sits `behind` (rest.hind_paw_behind_hip) behind the
    hip joint"""
    b = spec['rest']['hind_paw_behind_hip'] if behind is None else behind
    p = brentq(lambda a: hind_sagittal(spec, a, stifle, hock)['hip'][0] - b, 45.0, 89.9, xtol=1e-13)
    return hind_sagittal(spec, p, stifle, hock)


def withers_height(spec, fore=None):
    """the withers at the skin: the scapula's dorsal border plus rest.withers_soft"""
    f = fore_sagittal(spec) if fore is None else fore
    return float(f['scapula_top'][1] + spec['rest']['withers_soft'])


# --------------------------------------------------------------------------------------------- the rest chain
SPINE_AT = (('spine_0', 'L', 7), ('spine_1', 'L', 4), ('spine_2', 'L', 1), ('spine_3', 'T', 11),
            ('spine_4', 'T', 6), ('spine_5', 'T', 1))     # each joint at the caudal end of its named vertebra


def spine_units(lumbar_unit):
    """each spine joint's place from the lumbosacral joint (0) to C7/T1, in thoracic-body units (L7..L1, then T13..T1),
    and the total"""
    total = 7 * lumbar_unit + 13
    pos = {}
    for name, kind, n in SPINE_AT:
        pos[name] = (7 - n) * lumbar_unit if kind == 'L' else 7 * lumbar_unit + (13 - n)
    return pos, total


def _side(v, n, fore):
    """a paw value for the side digit n (2 or 5): a scalar, (II, V), or ((II, V) fore, (II, V) hind)"""
    if np.ndim(v) == 0:
        return float(v)
    v = np.asarray(v, float)
    if v.ndim == 2:
        v = v[0 if fore else 1]
    return float(v[0 if n == 2 else 1])


def _paw(spec, P, pre, c, width, dlen, pastern_deg):
    """digits II-V (and the fore dewclaw) of the left paw whose central MCP / MTP is c. W2d: the side digits' values
    may be per digit and per paw (_side: the metapodials II and V are shorter by different shares, fore and hind)"""
    pw = spec['paw']
    s3, s2 = pw['spread']
    a3, a2 = pw['splay']
    fore = pre == 'f'
    sv = lambda key, n: _side(pw[key], n, fore)
    layout = {2: (-s2, sv('setback', 2), sv('side_raise', 2), -a2, sv('side_digit', 2)),    # medial is -X on the left
              3: (-s3, 0.0, 0.0, -a3, 1.0), 4: (s3, 0.0, 0.0, a3, 1.0),
              5: (s2, sv('setback', 5), sv('side_raise', 5), a2, sv('side_digit', 5))}
    for n, (lat, back, up, splay, scale) in layout.items():
        y0 = c[1] + up
        d0 = np.array([c[0] + lat * width, y0, c[2] - back])
        hd = np.array([np.sin(np.radians(splay)), 0.0, np.cos(np.radians(splay))])
        l1, l2 = pw['p1_share'] * dlen * scale, (1.0 - pw['p1_share']) * dlen * scale
        # W2e: the side digits' PIP lower (their phalanges smaller: the paw domed from the front, w08)
        pip = pw['pip_h'] if n in (3, 4) else pw.get('pip_h_side', pw['pip_h'])
        dy1, dy2 = y0 - pip, pip - pw['tip_h']
        assert l1 > dy1 and l2 > dy2, (pre, n)
        d1 = d0 + np.sqrt(l1 ** 2 - dy1 ** 2) * hd - np.array([0.0, dy1, 0.0])
        tip = d1 + np.sqrt(l2 ** 2 - dy2 ** 2) * hd - np.array([0.0, dy2, 0.0])
        P[f'{pre}_digit{n}_0_L'], P[f'{pre}_digit{n}_1_L'], P[f'{pre}_digit{n}_tip_L'] = d0, d1, tip
    if pre == 'f':
        dc = pw['dewclaw']
        z = c[2] - (dc['h'] - c[1]) / np.tan(np.radians(pastern_deg))   # on the metacarpus's line at that height
        j = np.array([c[0] - dc['medial'], dc['h'], z])
        P['f_dewclaw_L'] = j
        P['f_dewclaw_tip_L'] = j + np.array([0.0, dc['tip_h'] - dc['h'], dc['reach']])


def rest_chain(spec):
    """the bind pose's points (module docstring): dict(pos={name: (3,)}, head=dict(origin, p, q, lm), WH, z_shoulder,
    z_fore, z_hind, fore2d, hind2d, neck_len, withers_z)"""
    r, hw, sp, jc = spec['rest'], spec['half_width'], spec['spine'], spec['jc']
    f = fore_sagittal(spec)
    h = solve_hind(spec)
    WH = withers_height(spec, f)
    z_sh = r['body_len_wh'] * WH - r['shoulder_hip_offset']
    zf, zh = z_sh - f['shoulder'][0], -h['hip'][0]
    lift = lambda p2, z0, half: np.array([half, p2[1], z0 + p2[0]])
    P = {}
    P['scapula_top_L'] = lift(f['scapula_top'], zf, hw['scapula_top'])
    P['shoulder_L'] = lift(f['shoulder'], zf, hw['shoulder'])
    P['elbow_L'] = lift(f['elbow'], zf, hw['elbow'])
    P['carpus_L'] = lift(f['carpus'], zf, hw['carpus'])
    P['mcp_L'] = lift(f['mcp'], zf, hw['forepaw'])
    t_cmc = (jc['carpus_mcp'] - spec['bones']['mc3']) / jc['carpus_mcp']        # the carpal row's share
    P['cmc_L'] = P['carpus_L'] + t_cmc * (P['mcp_L'] - P['carpus_L'])
    P['hip_L'] = lift(h['hip'], zh, hw['hip'])
    P['stifle_L'] = lift(h['stifle'], zh, hw['stifle'])
    P['hock_L'] = lift(h['hock'], zh, hw['hock'])
    P['mtp_L'] = lift(h['mtp'], zh, hw['hindpaw'])
    t_tmt = (jc['hock_mtp'] - spec['bones']['mt3']) / jc['hock_mtp']            # the distal tarsal rows' share
    P['tmt_L'] = P['hock_L'] + t_tmt * (P['mtp_L'] - P['hock_L'])
    _paw(spec, P, 'f', P['mcp_L'], spec['paw']['fore'][1], spec['paw']['digit_len'][0], f['pastern'])
    _paw(spec, P, 'h', P['mtp_L'], spec['paw']['hind'][1], spec['paw']['digit_len'][1], h['metatarsus_above_h'])
    # the spine: vertebral groups on the line from the lumbosacral joint to C7/T1
    P['pelvis'] = np.array([0.0, sp['pelvis'][0], sp['pelvis'][1]])
    ls = np.array([0.0, sp['ls'][0], sp['ls'][1]])
    ct = np.array([0.0, sp['ct_y'], z_sh - sp['ct_behind_shoulder']])
    su, total = spine_units(sp['lumbar_unit'])
    for name, u in su.items():
        P[name] = ls + (u / total) * (ct - ls)
    # the neck: rising neck_pitch from C7/T1 until the poll sits occiput_ahead_wh WH ahead of the withers
    head = archetype(spec.get('head_archetype', 'canid'))
    a = np.radians(r['palate_pitch'])
    p_ax, q_ax = np.array([0.0, np.sin(a), np.cos(a)]), np.array([0.0, np.cos(a), -np.sin(a)])
    nd = np.array([0.0, np.sin(np.radians(r['neck_pitch'])), np.cos(np.radians(r['neck_pitch']))])
    poll = head.poll_offset(spec)
    withers_z = P['scapula_top_L'][2]
    ao_z = withers_z + r['occiput_ahead_wh'] * WH - (poll[0] * p_ax[2] + poll[1] * q_ax[2])
    neck_len = (ao_z - ct[2]) / nd[2]
    ao = ct + neck_len * nd
    cu = np.cumsum((0.0,) + tuple(sp['cervical'])) / sum(sp['cervical'])        # C7/T1 ... AO
    P['neck_0'], P['neck_1'], P['neck_2'], P['head'] = ct, ct + cu[3] * (ao - ct), ct + cu[6] * (ao - ct), ao
    neck_bind = {k: P[k].copy() for k in ('neck_0', 'neck_1', 'neck_2', 'head')}
    if r.get('neck_pose') is not None:
        # W2d: a POSED neck (the review pose; the bind has none): the neck joints and the head turned in the sagittal
        # plane (pose_neck), the palate frame with them
        P, ao, p_ax, q_ax = pose_neck(P, p_ax, q_ax, r['neck_pose'])
    lm = head.landmarks(spec, ao, p_ax, q_ax)
    for k in [k for k in lm if k.endswith('_L')]:
        lm[k[:-2] + '_R'] = mirror_point(lm[k])
    # the tail: tail_0 just behind the sacrum, n_tail joints evenly to the tip at tail_pitch; rest tail_bend (deg per
    # joint, W2c: the posed review's rest hang curls down from the root; the bind's 0 leaves it straight)
    t0 = np.array([0.0, sp['tail_root'][0], sp['tail_root'][1]])
    n_t = spec['rig']['n_tail']
    seg = spec['tail_len'] / n_t
    bend = float(r.get('tail_bend', 0.0))
    pt = t0.copy()
    for k in range(n_t + 1):
        P['tail_tip' if k == n_t else f'tail_{k}'] = pt.copy()
        tp = np.radians(r['tail_pitch'] - bend * k)
        pt = pt + seg * np.array([0.0, np.sin(tp), -np.cos(tp)])
    for k in [k for k in P if k.endswith('_L')]:
        P[k[:-2] + '_R'] = mirror_point(P[k])
    return dict(pos=P, head=dict(origin=ao, p=p_ax, q=q_ax, lm=lm), WH=WH, z_shoulder=z_sh, z_fore=zf, z_hind=zh,
                fore2d=f, hind2d=h, neck_len=float(neck_len), withers_z=float(withers_z), neck_bind=neck_bind)


# --------------------------------------------------------------------------------------------- the posed neck (W2d)
NECK_CHAIN = ('neck_0', 'neck_1', 'neck_2', 'head')


def _rot_sag(v, deg):
    """(..., 3) vectors turned in the sagittal plane, nose-DOWN positive: a forward vector (0, 0, 1) goes to
    (0, -sin, cos)"""
    a = np.radians(deg)
    v = np.asarray(v, np.float64)
    out = v.copy()
    out[..., 1] = v[..., 1] * np.cos(a) - v[..., 2] * np.sin(a)
    out[..., 2] = v[..., 1] * np.sin(a) + v[..., 2] * np.cos(a)
    return out


def pose_neck(P, p_ax, q_ax, angles):
    """the neck posed by rotations (degrees, nose-down positive) at neck_0 (C7/T1), neck_1 (C4), neck_2 (C1) and the
    head joint (AO): forward kinematics in the sagittal plane; the bones keep their lengths. Returns the new points
    (a copy), the AO and the palate frame's axes"""
    P = {k: np.asarray(v, np.float64).copy() for k, v in P.items()}
    a = np.asarray(angles, np.float64)
    pts = [P[k].copy() for k in NECK_CHAIN]
    tot = 0.0
    new = [pts[0]]
    for i in range(1, 4):
        tot += a[i - 1]
        new.append(new[-1] + _rot_sag(pts[i] - pts[i - 1], tot))
    for k, v in zip(NECK_CHAIN, new):
        P[k] = v
    tot += a[3]
    return P, P['head'], _rot_sag(p_ax, tot), _rot_sag(q_ax, tot)


def neck_bend(points, bind, angles, blend=0.040):
    """a point set (n, 3) carried with the posed neck (linear-blend weights along the bind's neck chain: each point's
    station s on the chain polyline neck_0 -> head (extended at both ends), each joint's rotation applied beyond it
    with a smoothstep over +-blend m): the trunk sweep's neck stations follow the posed neck. bind: the bind's neck
    points (rest_chain's neck_bind)"""
    Q = np.asarray(points, np.float64)
    J = [np.asarray(bind[k], np.float64) for k in NECK_CHAIN]
    seg = [J[i + 1] - J[i] for i in range(3)]
    lens = [float(np.linalg.norm(s)) for s in seg]
    s_j = np.concatenate([[0.0], np.cumsum(lens)])
    # each point's station: its projection on the nearest segment (the first and last segments extended)
    best = np.full(len(Q), np.inf)
    st = np.zeros(len(Q))
    for i in range(3):
        u = seg[i] / lens[i]
        t = (Q - J[i]) @ u
        tc = t if i in (0, 2) else np.clip(t, 0.0, lens[i])
        if i == 0:
            tc = np.minimum(t, lens[0])
        if i == 2:
            tc = np.maximum(t, 0.0)
        d = np.linalg.norm(Q - (J[i] + tc[:, None] * u), axis=1)
        upd = d < best
        best = np.where(upd, d, best)
        st = np.where(upd, s_j[i] + tc, st)
    a = np.asarray(angles, np.float64)
    # apply the joints from the head down: each rotation about its joint's POSED position, weighted
    joints_posed = [J[0]]
    tot = 0.0
    for i in range(1, 4):
        tot += a[i - 1]
        joints_posed.append(joints_posed[-1] + _rot_sag(J[i] - J[i - 1], tot))
    # a point's transform: the chain's rigid transforms blended by smoothsteps at each joint
    W = []
    for i in range(4):
        u_ = np.clip((st - s_j[i] + blend) / (2 * blend), 0.0, 1.0)
        W.append(u_ * u_ * (3.0 - 2.0 * u_))
    W.append(np.zeros(len(Q)))
    cum = np.cumsum(np.concatenate([[0.0], a]))[1:]            # the total rotation of the bone beyond joint i
    acc = np.zeros_like(Q)
    wsum = np.zeros(len(Q))
    # bone b (b = -1: the trunk, before neck_0; b = 0..3: beyond joint b) weight W[b] - W[b + 1]
    for b in range(-1, 4):
        wb = (1.0 - W[0]) if b == -1 else (W[b] - W[b + 1])
        if b == -1:
            Tq = Q
        else:
            Tq = joints_posed[b] + _rot_sag(Q - J[b], cum[b])
        acc += wb[:, None] * Tq
        wsum += wb
    return acc / np.maximum(wsum, 1e-12)[:, None]


def solve_neck_pose(spec, neck_angle, neck_len, head_pitch, split=(0.0, 0.0, 0.0), bend_max=15.0):
    """the review pose's neck (W2d, the lead's call 5: "the head and neck at w01's measured neck pitch, so the side
    overlays compare like with like"): the neck turned about C7/T1 so the withers' skin to the poll (the head
    archetype's poll offset) stands at neck_angle degrees over the horizontal, and the head about the AO so its
    occiput-to-nose line stands at head_pitch (WOLF_BODY_PHOTOS §3.2's measures on w01): two unknowns, two measures,
    exact. The neck's LENGTH stays the bind's (a pose keeps the bones): w01's 0.389 WH from the withers to the occiput
    against the bind's 0.470 is not reachable without folding the neck (solved free, C7/T1 39 deg down and C4, C1 64
    deg up each; with every bend held to 15 deg the reach did not shorten), so it is reported, not posed (neck_len is
    the target the report measures). split / bend_max: a bend t shared by C4 and C1 (zero by default). Returns
    (angles, the poll's distance from w01's occiput point (mm), the head pitch reached, the neck angle reached, the
    neck length reached (WH))"""
    from scipy.optimize import least_squares
    ch = rest_chain({**spec, 'rest': {k: v for k, v in spec['rest'].items() if k != 'neck_pose'}})
    WH = ch['WH']
    w = np.array([0.0, WH, ch['withers_z']])
    target = w + neck_len * WH * np.array([0.0, np.sin(np.radians(neck_angle)), np.cos(np.radians(neck_angle))])
    head = archetype(spec.get('head_archetype', 'canid'))
    poll = head.poll_offset(spec)
    sp = np.asarray(split, float)

    def pose(x):
        b, t, hd = x
        ang = np.array([b + sp[0] * t, sp[1] * t, sp[2] * t, hd])
        P2, ao, pa, qa = pose_neck(ch['pos'], ch['head']['p'], ch['head']['q'], ang)
        pl = ao + poll[0] * pa + poll[1] * qa
        nose = head.landmarks(spec, ao, pa, qa)['nose_tip']
        d = pl - w
        return (ang, pl, float(np.degrees(np.arctan2(nose[1] - pl[1], nose[2] - pl[2]))),
                float(np.degrees(np.arctan2(d[1], d[2]))), float(np.hypot(d[1], d[2]) / WH))

    def f(x):
        _, pl, pitch, angle, length = pose(x)
        return np.array([10.0 * (angle - neck_angle), 5.0 * (pitch - head_pitch)])
    if float(np.max(np.abs(sp[1:]))) > 0.0:
        tmax = bend_max / float(np.max(np.abs(sp[1:])))
        g = lambda x: np.concatenate([f(x), [1000.0 * (pose(x)[4] - neck_len) * WH]])
        sol = least_squares(g, x0=np.array([0.0, 0.0, 5.0]),
                            bounds=([-bend_max, -tmax, -40.0], [bend_max, tmax, 40.0]))
        x = sol.x
    else:
        sol = least_squares(lambda x2: f(np.array([x2[0], 0.0, x2[1]])), x0=np.array([0.0, 5.0]))
        x = np.array([sol.x[0], 0.0, sol.x[1]])
    ang, pl, pitch, angle, length = pose(x)
    return ang, float(1000.0 * np.linalg.norm((pl - target)[1:])), pitch, angle, length


# --------------------------------------------------------------------------------------------- the skeleton
def skeleton(spec, chain):
    """§6.1's joints as rig.Skeleton (module docstring); sk.meta holds each joint's role, tier, side, fold, tip,
    driver and parent"""
    P, lm = chain['pos'], chain['head']['lm']
    p_ax = chain['head']['p']
    sk = RG.Skeleton()
    sk.meta = {}

    def add(name, parent, pos, x=None, fold=None, role='', tier=0, tip=None, driver=None, frame=None):
        if frame is None:
            frame = RG.frame_from(x, fold)
        sk.add(name, parent, np.asarray(pos, np.float64), frame)
        side = 'L' if name.endswith('_L') else ('R' if name.endswith('_R') else '')
        sk.meta[name] = dict(role=role, tier=tier, side=side, parent=parent, driver=driver,
                             fold=None if fold is None else np.asarray(fold, np.float64),
                             tip=None if tip is None else np.asarray(tip, np.float64))

    def frame(name):
        return sk.world[sk.index(name)][:3, :3]

    def mirror(names):
        sw = lambda n: n[:-2] + '_R' if (n and n.endswith('_L')) else n
        for n in names:
            m = sk.meta[n]
            W = sk.world[sk.index(n)]
            add(sw(n), sw(m['parent']), mirror_point(W[:3, 3]), role=m['role'], tier=m['tier'], driver=sw(m['driver']),
                fold=None if m['fold'] is None else mirror_point(m['fold']),
                tip=None if m['tip'] is None else mirror_point(m['tip']), frame=mirror_frame(W[:3, :3]))

    # ---- root, pelvis, spine, breathers, neck, head
    add('root', None, np.zeros(3), role='root', frame=np.eye(3))
    add('pelvis', 'root', P['pelvis'], P['spine_0'] - P['pelvis'], VENTRAL, 'spine')
    chain_sp = ['spine_0', 'spine_1', 'spine_2', 'spine_3', 'spine_4', 'spine_5', 'neck_0', 'neck_1', 'neck_2']
    prev = 'pelvis'
    for k, name in enumerate(chain_sp):
        nxt = chain_sp[k + 1] if k + 1 < len(chain_sp) else 'head'
        add(name, prev, P[name], P[nxt] - P[name], VENTRAL, 'spine')
        prev = name
    by = spec['spine']['breath_y']
    add('breath_belly', 'spine_1', [0.0, by[1], 0.5 * (P['spine_1'][2] + P['spine_2'][2])], VENTRAL, CRANIAL,
        'breather', 1)
    add('breath_chest', 'spine_4', [0.0, by[0], P['spine_4'][2]], VENTRAL, CRANIAL, 'breather', 1)
    add('head', 'neck_2', P['head'], lm['nose_tip'] - P['head'], VENTRAL, 'head', tip=lm['nose_tip'])
    add('jaw', 'head', lm['tmj'], lm['chin'] - lm['tmj'], VENTRAL, 'jaw', tip=lm['chin'])
    tg = ['tongue_0', 'tongue_1', 'tongue_2', 'tongue_tip']
    for k in range(3):
        add(tg[k], 'jaw' if k == 0 else tg[k - 1], lm[tg[k]], lm[tg[k + 1]] - lm[tg[k]], VENTRAL, 'tongue', 2,
            tip=lm['tongue_tip'] if k == 2 else None)
    r_eye = spec['eye']['ball_r']
    add('eye_L', 'head', lm['eye_L'], lm['eye_dir_L'], DORSAL, 'eye', 2, tip=lm['eye_L'] + r_eye * lm['eye_dir_L'])
    add('lid_up_L', 'head', lm['eye_L'], lm['lid_up_tip_L'] - lm['eye_L'], VENTRAL, 'lid', 2, tip=lm['lid_up_tip_L'])
    add('lid_lo_L', 'head', lm['eye_L'], lm['lid_lo_tip_L'] - lm['eye_L'], DORSAL, 'lid', 2, tip=lm['lid_lo_tip_L'])
    add('ear_0_L', 'head', lm['ear_0_L'], lm['ear_1_L'] - lm['ear_0_L'], CAUDAL, 'ear', 2)
    add('ear_1_L', 'ear_0_L', lm['ear_1_L'], lm['ear_tip_L'] - lm['ear_1_L'], CAUDAL, 'ear', 2, tip=lm['ear_tip_L'])
    xs = _unit(lm['nose_tip'] - lm['snout'])
    add('snout', 'head', lm['snout'], xs, DORSAL, 'face', 2, tip=lm['snout'] + 0.02 * xs)
    add('nose', 'head', lm['nose'], lm['nose_tip'] - lm['nose'], DORSAL, 'face', 2, tip=lm['nose_tip'])
    add('brow_L', 'head', lm['brow_L'], p_ax, DORSAL, 'face', 2, tip=lm['brow_L'] + 0.015 * p_ax)
    add('lip_up_L', 'head', lm['lip_up_L'], p_ax, DORSAL, 'face', 2, tip=lm['lip_up_L'] + 0.02 * p_ax)
    add('lip_lo_L', 'jaw', lm['lip_lo_L'], lm['jaw_dir'], VENTRAL, 'face', 2, tip=lm['lip_lo_L'] + 0.02 * lm['jaw_dir'])
    mirror(['eye_L', 'lid_up_L', 'lid_lo_L', 'ear_0_L', 'ear_1_L', 'brow_L', 'lip_up_L', 'lip_lo_L'])
    # ---- forelimbs
    tu, tl = spec['rig']['twist_upper'], spec['rig']['twist_lower']
    fore = ['scapula_L', 'humerus_L', 'humerus_twist_L', 'radius_L', 'radius_twist_L', 'carpus_L', 'metacarpus_L']
    add('scapula_L', 'spine_4', P['scapula_top_L'], P['shoulder_L'] - P['scapula_top_L'], CAUDAL, 'scapula')
    add('humerus_L', 'scapula_L', P['shoulder_L'], P['elbow_L'] - P['shoulder_L'], CAUDAL, 'hinge')
    add('humerus_twist_L', 'humerus_L', P['shoulder_L'] + tu * (P['elbow_L'] - P['shoulder_L']), role='twist',
        tier=1, driver='humerus_L', frame=frame('humerus_L'))
    add('radius_L', 'humerus_L', P['elbow_L'], P['carpus_L'] - P['elbow_L'], CRANIAL, 'hinge')
    add('radius_twist_L', 'radius_L', P['elbow_L'] + tl * (P['carpus_L'] - P['elbow_L']), role='twist', tier=1,
        driver='radius_L', frame=frame('radius_L'))
    add('carpus_L', 'radius_L', P['carpus_L'], P['cmc_L'] - P['carpus_L'], CAUDAL, 'hinge')
    add('metacarpus_L', 'carpus_L', P['cmc_L'], P['mcp_L'] - P['cmc_L'], CAUDAL, 'hinge', tip=P['mcp_L'])
    for n in (2, 3, 4, 5):
        d0, d1, dt = P[f'f_digit{n}_0_L'], P[f'f_digit{n}_1_L'], P[f'f_digit{n}_tip_L']
        add(f'f_digit{n}_0_L', 'metacarpus_L', d0, d1 - d0, VENTRAL, 'digit', 1)
        add(f'f_digit{n}_1_L', f'f_digit{n}_0_L', d1, dt - d1, VENTRAL, 'digit', 1, tip=dt)
        fore += [f'f_digit{n}_0_L', f'f_digit{n}_1_L']
    add('f_dewclaw_L', 'metacarpus_L', P['f_dewclaw_L'], P['f_dewclaw_tip_L'] - P['f_dewclaw_L'], CAUDAL, 'digit', 1,
        tip=P['f_dewclaw_tip_L'])
    mirror(fore + ['f_dewclaw_L'])
    # ---- hindlimbs
    hind = ['femur_L', 'femur_twist_L', 'tibia_L', 'tibia_twist_L', 'tarsus_L', 'metatarsus_L']
    add('femur_L', 'pelvis', P['hip_L'], P['stifle_L'] - P['hip_L'], CRANIAL, 'hinge')
    add('femur_twist_L', 'femur_L', P['hip_L'] + tu * (P['stifle_L'] - P['hip_L']), role='twist', tier=1,
        driver='femur_L', frame=frame('femur_L'))
    add('tibia_L', 'femur_L', P['stifle_L'], P['hock_L'] - P['stifle_L'], CAUDAL, 'hinge')
    add('tibia_twist_L', 'tibia_L', P['stifle_L'] + tl * (P['hock_L'] - P['stifle_L']), role='twist', tier=1,
        driver='tibia_L', frame=frame('tibia_L'))
    add('tarsus_L', 'tibia_L', P['hock_L'], P['tmt_L'] - P['hock_L'], CRANIAL, 'hinge')
    add('metatarsus_L', 'tarsus_L', P['tmt_L'], P['mtp_L'] - P['tmt_L'], CRANIAL, 'hinge', tip=P['mtp_L'])
    for n in (2, 3, 4, 5):
        d0, d1, dt = P[f'h_digit{n}_0_L'], P[f'h_digit{n}_1_L'], P[f'h_digit{n}_tip_L']
        add(f'h_digit{n}_0_L', 'metatarsus_L', d0, d1 - d0, VENTRAL, 'digit', 1)
        add(f'h_digit{n}_1_L', f'h_digit{n}_0_L', d1, dt - d1, VENTRAL, 'digit', 1, tip=dt)
        hind += [f'h_digit{n}_0_L', f'h_digit{n}_1_L']
    mirror(hind)
    # ---- tail
    n_t = spec['rig']['n_tail']
    for k in range(n_t):
        nxt = P[f'tail_{k + 1}'] if k + 1 < n_t else P['tail_tip']
        add(f'tail_{k}', 'pelvis' if k == 0 else f'tail_{k - 1}', P[f'tail_{k}'], nxt - P[f'tail_{k}'], VENTRAL,
            'tail', tip=P['tail_tip'] if k == n_t - 1 else None)
    # ---- volume helpers (AG 06.21): each in the frame of the joint whose bend drives it
    hp = spec['helpers']
    Fr, Fh, Ff, Ft = frame('radius_L'), frame('humerus_L'), frame('femur_L'), frame('tarsus_L')
    ole = hp['olecranon']
    add('elbow_pt_L', 'humerus_L', P['elbow_L'] - ole[0] * Fr[:, 0] - ole[1] * Fr[:, 1], role='helper', tier=1,
        driver='radius_L', frame=Fr)
    add('triceps_L', 'humerus_L', 0.5 * (P['shoulder_L'] + P['elbow_L']) + hp['triceps'] * Fh[:, 1], role='helper',
        tier=1, driver='humerus_L', frame=Fh)
    add('patella_L', 'femur_L', P['stifle_L'] + hp['patella'] * Ff[:, 1], role='helper', tier=1, driver='tibia_L',
        frame=frame('tibia_L'))
    add('hock_pt_L', 'tibia_L', P['hock_L'] + spec['paw']['calcaneus'] * _unit(P['hock_L'] - P['mtp_L'])
        - hp['tuber_plantar'] * Ft[:, 1], role='helper', tier=1, driver='tarsus_L', frame=Ft)
    g = hp['gluteal']
    add('gluteal_L', 'pelvis', P['hip_L'] + np.array([g[1], g[0], g[2]]), role='helper', tier=1, driver='femur_L',
        frame=Ff)
    mirror(['elbow_pt_L', 'triceps_L', 'patella_L', 'hock_pt_L', 'gluteal_L'])
    # ---- IK targets (AG 05.19): under the root, on the paws' MCP / MTP with the metapodials' frames
    add('ik_forepaw_L', 'root', P['mcp_L'], role='ik', tier=1, driver='metacarpus_L', frame=frame('metacarpus_L'))
    add('ik_hindpaw_L', 'root', P['mtp_L'], role='ik', tier=1, driver='metatarsus_L', frame=frame('metatarsus_L'))
    mirror(['ik_forepaw_L', 'ik_hindpaw_L'])
    return sk


# --------------------------------------------------------------------------------------------- the skin (W2)
# THE HAIRLESS CLAY (plan §4.2, §10 step 2), with today's sdf.Program only: no OFFSET, the clay is the skin, at true
# mass (CG 16.9). Each structure is a GROUP that unions (nearly) hard inside and blends into the body ONCE (the
# octopus's anti-compounding lesson):
#   trunk           the trunk-and-neck SWEEP from C1 to the point of buttock (PCHIP stations, a3 keel, a4 < 0 on the
#                   loin, both ends rounded as the octopus's apex), the withers' interscapular mass, the manubrium
#   fore_L/R        a SWEEP along the forelimb's joint chain from inside the trunk to the MCP, muscle masses as
#   hind_L/R        ellipsoids in the bones' frames, tendons as round cones, the bony points (olecranon, accessory
#                   carpal, calcaneal tuber, patella) as small ellipsoids
#   fpaw_L/R        digits as round-cone chains to the claw beds, the pads as flattened ellipsoids, the fore dewclaw
#   hpaw_L/R
#   tail            a SWEEP from inside the croup to the tip
#   head            heads/<archetype>.build_head: the head group, the ears as SHELL groups, the mouth slit (SUBTRACT)
#                   LAST in the whole program (guide §9)
# The numbers are SPEC['skin'] (species/wolf.py), fitted BY EYE to the traced live animals at matched scale
# (work/bestiary/tests/w02_clay.py); the rest chain places every group, so the skin rides the skeleton the rig binds to.
# Each primitive is tagged for the coat (prog.coat_tags, the layout forge/coat.py's tag() writes) and each group's
# primitive range and region (species REGIONS) go in info['groups'].
X_AX = np.array([1.0, 0.0, 0.0])
Y_AX = np.array([0.0, 1.0, 0.0])
Z_AX = np.array([0.0, 0.0, 1.0])


def _pchip_curve(C, n=4096, sigma=0.0):
    """a smooth curve through (near) the control points C (k, 3): each coordinate PCHIP-interpolated against the
    cumulative chord (shape-preserving: no overshoot between unevenly spaced points, the octopus axis's lesson), then,
    with sigma > 0 (m of arclength), Gaussian-smoothed: PCHIP is only C1 and its curvature SPIKES at a control point
    where the slope changes (W2: curvature x radius 2.5 at the trunk's T1 station, a fold across the withers; a sweep
    folds on the concave side wherever curvature x radius passes 1, the octopus t24 crease ring). The ends are
    extended along their tangents before smoothing, so they keep their place and direction. Returns the dense points
    (n, 3), their arclength (n,) and each control point's arclength (k,) (its nearest dense point)"""
    C = np.asarray(C, np.float64)
    t = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    tt = np.linspace(0.0, t[-1], n)
    D = np.column_stack([PchipInterpolator(t, C[:, k])(tt) for k in range(3)])
    if sigma > 0:
        ds = tt[1] - tt[0]
        m = int(np.ceil(3.0 * sigma / ds))
        t0 = (D[1] - D[0]) / np.linalg.norm(D[1] - D[0])
        t1 = (D[-1] - D[-2]) / np.linalg.norm(D[-1] - D[-2])
        j = np.arange(1, m + 1)[:, None] * ds
        E = np.vstack([D[0] - j[::-1] * t0, D, D[-1] + j * t1])
        from scipy.ndimage import gaussian_filter1d
        D = gaussian_filter1d(E, sigma / ds, axis=0, mode='nearest')[m:m + n]
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    sc = np.array([s[int(np.argmin(np.linalg.norm(D - c, axis=1)))] for c in C])
    sc[0], sc[-1] = 0.0, s[-1]
    return D, s, np.maximum.accumulate(sc)


def _node_s(L, n, ends=(0.05, 0.05), gain=2.5, bumps=()):
    """n node arclengths on [0, L], denser toward both ends (a Gaussian density rise of `gain` over ends[0] / ends[1]:
    the rounded ends change radius fast) and at bumps ((s, width, gain), ...): where the radius changes fast a linear
    radius between sparse nodes prints every node as a terrace ring (the octopus mantle, t09)"""
    ss = np.linspace(0.0, L, 8192)
    dens = np.ones_like(ss)
    if ends[0] > 0:
        dens += gain * np.exp(-(ss / ends[0]) ** 2)
    if ends[1] > 0:
        dens += gain * np.exp(-((L - ss) / ends[1]) ** 2)
    for sb, wb, gb in bumps:
        dens += gb * np.exp(-((ss - sb) / wb) ** 2)
    c = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(ss))])
    return np.interp(np.linspace(0.0, c[-1], n), c, ss)


def end_taper(s, L, r_start, r_end, e_start=0.6, e_end=0.6):
    """THE ROUNDED ENDS: the radius eases (smoothstep, slope 0 at both ends of the ease) from its full value down to
    e_start / e_end of it over the first r_start and the last r_end of the arclength, and the kernel's own hemisphere
    cap of that end radius closes the sweep. W2 replaced the plan's octopus factor sqrt(1 - (1 - u)^2) (radius 0 at the
    end node): its last segment's slope runs to ~20, sd_sweep divides the cap's distance by sqrt(1 + slope^2), and past
    the end the field read up to 20x short (the mandible 16.8 mm where its box stood 37.9 mm away). sdf.Program culls
    a member whose box lies beyond the result before its group plus the group's k, so an underestimated member was
    dropped where it still mattered: 0.7-1.2 mm steps, the seams across the head and at the tail root (w02_clay.py
    i02); the near-zero gradient there failed the bound gate too. A cap of radius e R with zero slope into it is an
    exact sphere distance"""
    s = np.asarray(s, np.float64)
    f = np.ones_like(s)
    for Lr, u, e in ((r_start, s / max(r_start, 1e-12), e_start), (r_end, (L - s) / max(r_end, 1e-12), e_end)):
        if Lr > 0:
            u = np.clip(u, 0.0, 1.0)
            f = f * (e + (1.0 - e) * u * u * (3.0 - 2.0 * u))
    return f


def _tangents(P):
    T = np.gradient(np.asarray(P, np.float64), axis=0)
    return T / np.linalg.norm(T, axis=1, keepdims=True)


def _perp(ref, T):
    """ref made perpendicular to each tangent (unit): a sweep's theta = 0 direction"""
    N = np.asarray(ref, np.float64)[None, :] - (T @ np.asarray(ref, np.float64))[:, None] * T
    return N / np.linalg.norm(N, axis=1, keepdims=True)


def _tag(prog, index, part, chain=None):
    """forge/coat.py tag()'s record (prog.coat_tags[index] = (part, chain)) without importing the coat layer"""
    if getattr(prog, 'coat_tags', None) is None:
        prog.coat_tags = {}
    prog.coat_tags[int(index)] = (str(part), chain)
    return index


def _side_pt(P, name, side):
    """a chain point by its base name on one side (+1 left, -1 right); midline names as they are"""
    if f'{name}_L' in P:
        return np.asarray(P[f'{name}_L' if side > 0 else f'{name}_R'], np.float64)
    return np.asarray(P[name], np.float64)


def _anchor(P, side, a, b, t, off=(0.0, 0.0, 0.0)):
    """the point t of the way from chain point a to b (b None: a itself), plus a world offset (lateral, up, forward);
    lateral is away from the midline on either side"""
    pa = _side_pt(P, a, side)
    p = pa if b is None else pa + t * (_side_pt(P, b, side) - pa)
    return p + np.array([side * off[0], off[1], off[2]])


def bone_frame(P, side, a, b):
    """a bone's frame (columns: along a -> b, cranial (+Z made perpendicular), lateral (away from the midline))"""
    pa, pb = _side_pt(P, a, side), _side_pt(P, b, side)
    ea = (pb - pa) / np.linalg.norm(pb - pa)
    ec = Z_AX - (Z_AX @ ea) * ea
    ec /= np.linalg.norm(ec)
    el = np.cross(ea, ec)
    if el @ X_AX * side < 0:
        el = -el
    return pa, pb, np.column_stack([ea, ec, el])


def _on_bone(P, side, a, b, t, dc, dl, du=0.0):
    """a point t along bone a -> b, offset dc cranially, dl laterally and du along the bone (the bone's frame)"""
    pa, pb, R = bone_frame(P, side, a, b)
    return pa + t * (pb - pa) + du * R[:, 0] + dc * R[:, 1] + dl * R[:, 2], R


def trunk_axis(spec, chain, neck=None):
    """the trunk-and-neck sweep's nodes from SPEC['skin']['trunk']: rows (name, z, y, r0, aspect, a3, a4), the section
    centre in the sagittal plane, its half-depth r0 along the dorsal normal (theta = 0, perpendicular to the axis),
    width / depth, the keel a3 (phi3 = pi: peaks ventrally and dorsolaterally) and the loin's a4 (< 0 flattens the top:
    r(45 deg) / r(0) = (1 - a4) / (1 + a4)). The axis is a PCHIP curve through the centres, Gaussian-smoothed (SPEC
    trunk_smooth); the profile is PCHIP through the stations against arclength (C1: the octopus mantle's terrace
    lesson); both ends ease into their hemisphere caps (end_taper, SPEC trunk_round: C1 first, the point of buttock
    last). The dorsal skin over a station is at r0 (1 - a3 + a4), the ventral at r0 (1 + a3 + a4), the half-width
    r0 (1 + a4) aspect.

    THE DISTANCE BOUND (W2's gradient gate): the kernel's |q| - r(theta) overstates |grad f| by sqrt(1 + (r'/r)^2) for
    a non-circular section, so width / depth stays >= 0.78 with small harmonics (|grad| <= 1.05); on a bend's concave
    side the radius change is amplified by 1 / (1 - curvature x radius), which the withers mass covers (SPEC withers)"""
    sk = spec['skin']
    rows = sk['trunk']
    names = [r[0] for r in rows]
    C = np.array([[0.0, r[2], r[1]] for r in rows])
    if neck is not None:
        # W2d: the review pose's posed neck: the stations carried with it (neck_bend; the trunk behind C7/T1 stays)
        C = neck_bend(C, neck[0], neck[1])
    D, s, sc = _pchip_curve(C, sigma=sk['trunk_smooth'])
    sc = sc + np.arange(len(sc)) * 1e-9
    L = float(s[-1])
    r_start, r_end, e_start, e_end = sk['trunk_round']
    bumps = [(float(sc[names.index(nm)]), w, g) for nm, w, g in sk['trunk_dense']]
    sn = _node_s(L, int(sk['trunk_nodes']), ends=(r_start, r_end), gain=2.5, bumps=bumps)
    P = np.column_stack([np.interp(sn, s, D[:, k]) for k in range(3)])
    T = _tangents(P)
    N = _perp(Y_AX, T)
    prof = np.array([[r[3], r[4], r[5], r[6]] for r in rows])
    r0, asp, a3, a4 = (PchipInterpolator(sc, prof[:, k])(sn) for k in range(4))
    fac = end_taper(sn, L, r_start, r_end, e_start, e_end)
    core = (sn >= r_start) & (sn <= L - r_end)
    # the end caps round (W2 r05): past an end node the kernel's |q| - r(theta) takes theta from a near-axial q, so a
    # non-round end section (aspect, a3, a4) pinches the cap's apex into a star; the sections ease to circles over
    # SPEC trunk_round_sections (start, end) of arclength, the dorsal half-depth r0 (1 - a3 + a4) kept
    w = np.ones_like(sn)
    for length, u in zip(sk.get('trunk_round_sections', (0.0, 0.0)), (sn, L - sn)):
        if length > 0:
            u = np.clip(u / length, 0.0, 1.0)
            w = w * u * u * (3.0 - 2.0 * u)
    r0 = r0 * (1.0 - a3 + a4) / (1.0 - a3 * w + a4 * w)
    asp, a3, a4 = 1.0 + (asp - 1.0) * w, a3 * w, a4 * w
    return dict(P=P, N=N, T=T, s=sn, L=L, r0=r0 * fac, r0_raw=r0, aspect=asp, a3=a3, a4=a4, core=core,
                station_s=dict(zip(names, sc.tolist())), names=names)


def _path_sweep(P, side, rows, n_per_m=330.0, sigma=0.0):
    """a limb or tail sweep's nodes from path rows (a, b, t, (lateral, up, forward), r0, aspect): control points on the
    chain, a smoothed PCHIP curve through them (sigma: the corners at the joints rounded so curvature x radius stays
    under 1 on the concave side), the profile PCHIP against arclength; theta = 0 cranial (+Z made perpendicular)"""
    C = np.array([_anchor(P, side, r[0], r[1], r[2], r[3]) for r in rows])
    D, s, sc = _pchip_curve(C, sigma=sigma)
    sc = sc + np.arange(len(sc)) * 1e-9
    L = float(s[-1])
    n = max(16, int(np.ceil(L * n_per_m)))
    sn = np.linspace(0.0, L, n)
    Pn = np.column_stack([np.interp(sn, s, D[:, k]) for k in range(3)])
    T = _tangents(Pn)
    prof = np.array([[r[4], r[5]] for r in rows])
    r0, asp = (PchipInterpolator(sc, prof[:, k])(sn) for k in range(2))
    return dict(P=Pn, T=T, N=_perp(Z_AX, T), s=sn, L=L, r0=r0, aspect=asp, core=np.ones(n, bool), ctrl=C)


def _add_sweep(prog, ax, name, k=0.0, a3=0.0, phi3=0.0, a4=0.0):
    i = prog.sweep(ax['P'], ax['N'], ax['r0'], a3=ax.get('a3', a3), phi3=phi3, a4=ax.get('a4', a4),
                   aspect=ax['aspect'], k=k, name=name)
    return i


def _muscles(prog, P, side, rows, part, chain_pts, suffix):
    """ellipsoids in their bones' frames: rows (name, a, b, t, cranial, lateral, along, (r_along, r_cranial,
    r_lateral), k)"""
    out = []
    for name, a, b, t, dc, dl, du, radii, k in rows:
        c, R = _on_bone(P, side, a, b, t, dc, dl, du)
        i = prog.ellipsoid(c, radii, axes=R, k=k, name=f'{name}{suffix}')
        out.append(_tag(prog, i, part, chain_pts))
    return out


def _spindles(prog, P, side, rows, part, chain_pts, suffix):
    """muscle bellies as tapered round cones along a bone (exact distances; an ellipsoid 3-4x longer than wide left
    iq's estimate's gradient over 1.05 on the forearm, w02 i06): rows (name, a, b, t0, t1, cranial, lateral, r0, r1,
    k), the cone from t0 to t1 of the bone a -> b, offset in the bone's frame"""
    out = []
    for name, a, b, t0, t1, dc, dl, r0, r1, k in rows:
        p0, _ = _on_bone(P, side, a, b, t0, dc, dl)
        p1, _ = _on_bone(P, side, a, b, t1, dc, dl)
        i = prog.roundcone(p0, p1, r0, r1, k=k, name=f'{name}{suffix}')
        out.append(_tag(prog, i, part, chain_pts))
    return out


def _tendons(prog, P, side, rows, part, chain_pts, suffix):
    """round cones between two bone-frame points: rows (name, (a, b, t, cranial, lateral), (a, b, t, cranial,
    lateral), r1, r2, k)"""
    out = []
    for name, e1, e2, r1, r2, k in rows:
        p1, _ = _on_bone(P, side, *e1)
        p2, _ = _on_bone(P, side, *e2)
        i = prog.roundcone(p1, p2, r1, r2, k=k, name=f'{name}{suffix}')
        out.append(_tag(prog, i, part, chain_pts))
    return out


def _limb_group(prog, spec, chain, key, side, part, info):
    """one limb: its sweep along the chain plus muscles and tendons, one group blended into the body by its k"""
    P = chain['pos']
    L = spec['skin'][key]
    sfx = '_L' if side > 0 else '_R'
    lo = len(prog.kind)
    prog.begin_group(S_.UNION, L['k'])
    ax = _path_sweep(P, side, L['path'], sigma=L['smooth'])
    i = _add_sweep(prog, ax, f'{key}_sweep{sfx}')
    _tag(prog, i, part)
    ms = _muscles(prog, P, side, L['muscles'], part, ax['P'], sfx)
    ms += _spindles(prog, P, side, L.get('spindles', ()), part, ax['P'], sfx)
    ms += _tendons(prog, P, side, L['tendons'], part, ax['P'], sfx)
    # W2d: the measured masses are the body volume's inner limits (wolf_body.inner_upper), the bony knobs excepted
    # (they are the volume's bones and strokes)
    info.setdefault('masses', []).extend(prog.names[j] for j in ms
                                         if not prog.names[j].startswith(tuple(L.get('not_masses', ()))))
    prog.end_group()
    info['groups'].append(dict(name=f'{key}{sfx}', region=part, lo=lo, hi=len(prog.kind), sweep=i))
    info['sweeps'][f'{key}{sfx}'] = ax
    return ax


def _capsule(prog, c, axis, half_len, r, k, name):
    """a round cone of one radius (exact distance) centred on c along axis; W2 builds the pads and the knuckle mass
    from these: iq's ellipsoid estimate inside a 7-12 mm flattened ellipsoid left the field's gradient outside
    [0.6, 1.05] within 5 mm of the surface (w02 i03: ~1000 samples on the paws each way)"""
    a = np.asarray(axis, np.float64)
    a = a / np.linalg.norm(a)
    return prog.roundcone(c - half_len * a, c + half_len * a, r, r, k=k, name=name)


def claw_points(base, tip, a0, a1, n=28):
    """W2e: a HOOKED claw's axis (the lead's call 3: "dark HOOKED claws curving down to touch the ground ahead of the
    toes (w01, w08), not straight 11 mm pegs"): a quadratic Bezier in the vertical plane through its base (inside the
    ungual crest) and its tip, leaving the base a0 degrees below the horizontal along the toe's heading and arriving at
    the tip a1 degrees below it (a0 < a1: the claw's back convex, its point turned down onto the ground), resampled to
    n + 1 points evenly along its length (W2d's: a 6 mm lift on a 20 mm chord falling 60 deg, a straight peg)"""
    base, tip = np.asarray(base, np.float64), np.asarray(tip, np.float64)
    hd = tip - base
    hd[1] = 0.0
    hd /= np.linalg.norm(hd)
    dn = np.array([0.0, -1.0, 0.0])
    d0 = np.cos(np.radians(a0)) * hd + np.sin(np.radians(a0)) * dn
    d1 = np.cos(np.radians(a1)) * hd + np.sin(np.radians(a1)) * dn
    st = np.linalg.lstsq(np.column_stack([d0, d1]), tip - base, rcond=None)[0]
    assert st[0] > 0.0 and st[1] > 0.0, ('the claw\'s start and arrival directions do not meet ahead of it', a0, a1)
    ctrl = base + st[0] * d0
    t = np.linspace(0.0, 1.0, 400)[:, None]
    C = (1 - t) ** 2 * base + 2 * (1 - t) * t * ctrl + t ** 2 * tip
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    su = np.linspace(0.0, s[-1], n + 1)
    return np.column_stack([np.interp(su, s, C[:, k]) for k in range(3)])


def claw_args(base, tip, depth, width, tip_scale, a0, a1, rho, k, name, taper=1.2):
    """the claw's PSWEEP arguments (keratin, a part of its own: crisp, never flowed): a laterally compressed oval
    section, `depth` (dorsal-ventral) by `width` (m) at the base, scaled down to tip_scale at the tip (a blunt point,
    the corner radius rho kept) as 1 - (1 - tip_scale) u^taper along the length u (W2g: taper 1.6, the claw broad down
    its visible length, not a pin), along claw_points; the section's x on the frame normal carried from up (the claw's
    plane is the toe's vertical plane, so the frame stays in it). W2d's claws were round cones 11 mm across (pegs)"""
    P = claw_points(base, tip, a0, a1)
    ang = np.linspace(0.0, 2.0 * np.pi, 20, endpoint=False)
    core = np.column_stack([(0.5 * depth - rho) * np.cos(ang), (0.5 * width - rho) * np.sin(ang)])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    u = s / s[-1]
    scale = 1.0 - (1.0 - tip_scale) * u ** taper
    return dict(points=P, sections=core, rho=rho, scale=scale, normal=np.array([0.0, 1.0, 0.0]), k=k,
                name=f'{name}_0')


def claw_fold(prog, args, fold, name):
    """W2g (the lead's call 6: "the claws as claws ... curving down from the toe tips with the nail bed's fold"): THE
    NAIL BED'S FOLD, the skin's lip round the claw's root: the claw's own section `proud` (m) larger all round over the
    first `length` of its axis (from its base, inside the toe's end, out past the toe's skin), smooth-unioned with k.
    Skin, not keratin: a paw member (the body volume flows it with the paw) while the claw itself stays a primitive"""
    proud, length, k = fold
    P = args['points']
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    m = s <= length + 1e-12
    i = prog.psweep(P[m], args['sections'], rho=args['rho'] + proud, scale=args['scale'][m], normal=args['normal'],
                    k=k, name=name)
    _tag(prog, i, 'paw')
    return i


def add_claw(prog, args, info=None):
    """a claw from claw_args into the program (the composed paw's group, or the body volume's first group)"""
    i = prog.psweep(args['points'], args['sections'], rho=args['rho'], scale=args['scale'], normal=args['normal'],
                    k=args['k'], name=args['name'])
    _tag(prog, i, 'claw')
    if info is not None:
        info.setdefault('claws', []).append(i)
        info.setdefault('claw_args', {})[args['name']] = args
    return i


def _claw(prog, base, tip, depth, width, tip_scale, a0, a1, rho, k, name, info):
    return add_claw(prog, claw_args(base, tip, depth, width, tip_scale, a0, a1, rho, k, name), info)


def _paw_group(prog, spec, chain, pre, side, info):
    """one paw (W2d, rebuilt FROM THE BONES; the lead: "digits III / IV long and forward, II / V shorter and set back
    (w08 front); the toes ARCHED with the knuckles high (w01 side); tight lobes; the digital pads and the metacarpal /
    metatarsal pad; hooked claws leaving the ungual crest; the forepaw's dewclaw high on the medial side"):
      the digits on the skeleton's joints (rest_chain._paw: the MCP / MTP head, the PIP, the claw tip; II and V on
      their shorter metapodials, raised and set back, SPEC paw), each soft toe three round cones: the proximal phalanx
      from the head to the PIP (level: the knuckle high), the middle phalanx to a DIP on the arch (W dip: its share of
      the way to the claw tip and its rise over that chord), the distal phalanx to the UNGUAL CREST (W crest), the
      radii W digit_r (head, PIP, DIP, crest), II and V scaled by side_scale; the toes packed tight (SPEC paw.spread)
      so neighbours touch with shallow grooves (the lobes);
      the digital pad under each DIP (a capsule on the ground), the metacarpal / metatarsal pad under and behind the
      heads (a rounded box), the KNUCKLE MASS over the heads (a rounded box: the palm's dorsum);
      the CLAWS hooked from inside the crest to the claw tip (claw_points), listed in info['claws'] with their PSWEEP
      arguments in info['claw_args']: parts of their own, never flowed (the body volume leaves them out and adds them
      back as primitives);
      on the forelimb the carpal pad and the dewclaw (digit I) high on the medial side with its claw.
    W2e (the lead's call 3: "one COMPACT rounded mass as w08 shows (toes held tight, shallow grooves with skin between,
    not sausages grooved to the ground); dark HOOKED claws curving down to touch the ground ahead of the toes (w01, w08);
    the metacarpal pad tucked under; the pastern meeting the paw's dorsum in one curve (~130 deg, w01)"):
      the WEB between neighbouring toes (W web: a round cone along the mid-line of each pair from their PIPs to t_end of
      the way to their DIPs, its axis `drop` under theirs and its radius theirs less `groove` plus `drop`: its top a
      groove's depth under the toes' tops, its bottom near the pads), so the four toes are one mass with shallow
      grooves on top and skin between, their fronts free as lobes;
      the RAMP (W ramp): the dorsum from the pastern's front down to the knuckles in one slope, a rounded box tilted
      `slope` deg whose top runs from the pastern's front at `up` over the head to the knuckles over III / IV's PIPs;
      the HEEL (W heel): a round cone behind the pastern's foot into the metacarpal pad, so the caudal outline runs from
      the pastern into the pad in one curve (W2d's pad stood as a ball behind a notch);
      the claws (W claw_section, claw_dir, claw_tip_scale, claw_rho, claw_base) laterally compressed and hooked.
    Each member's name goes in info['masses'] (the volume's inner limits) except the claws"""
    P = chain['pos']
    W = spec['skin']['paw']
    sfx = '_L' if side > 0 else '_R'
    fore = pre == 'f'
    head = 'mcp' if fore else 'mtp'
    lo = len(prog.kind)
    masses = info.setdefault('masses', [])
    prog.begin_group(S_.UNION, W['k'])
    r_head, r_pip, r_dip, r_cr = W['digit_r'] if fore else W['digit_r_hind']
    c = _side_pt(P, head, side)
    f_dip, h_dip = W['dip']
    f_cr, h_cr = W['crest']
    cdep, cwid = W['claw_section'][0 if fore else 1]
    ca0, ca1 = W['claw_dir']
    cback, cup = W['claw_base']
    pads, toes = {}, {}
    for n in (2, 3, 4, 5):
        d0 = _side_pt(P, f'{pre}_digit{n}_0', side)
        d1 = _side_pt(P, f'{pre}_digit{n}_1', side)
        tip = _side_pt(P, f'{pre}_digit{n}_tip', side)
        sc = 1.0 if n in (3, 4) else W['side_scale']
        dip = d1 + f_dip * (tip - d1) + np.array([0.0, h_dip * sc, 0.0])
        crest = d1 + f_cr * (tip - d1) + np.array([0.0, h_cr * sc, 0.0])
        toes[n] = dict(d0=d0, d1=d1, dip=dip, crest=crest, sc=sc)
        for a_, b_, ra, rb, nm in ((d0, d1, r_head, r_pip, 'p1'), (d1, dip, r_pip, r_dip, 'p2'),
                                   (dip, crest, r_dip, r_cr, 'p3')):
            i = prog.roundcone(a_, b_, ra * sc, rb * sc, k=W['k_digit'], name=f'{pre}digit{n}{nm}{sfx}')
            _tag(prog, i, 'paw')
            masses.append(prog.names[i])
        # the digital pad under the DIP, its sole on the ground (a capsule along the toe)
        pl, ph, pa = W['pad_digital'] if fore else W['pad_digital_hind']
        u = tip - d1
        hd = np.array([u[0], 0.0, u[2]]) / np.linalg.norm([u[0], u[2]])
        pc = dip + W['pad_along'] * (crest - dip)
        pc = np.array([pc[0], ph * sc, pc[2]])
        i = _capsule(prog, pc, hd, max(pa - ph, 0.0) * sc, ph * sc, W['k_pad'], f'{pre}pad{n}{sfx}')
        _tag(prog, i, 'pad')
        masses.append(prog.names[i])
        pads[n] = pc
        # the claw: from inside the crest (back along the toe's heading, raised) hooked down onto the ground at the tip.
        # W2g: claw_base's first value negative puts the base AHEAD of the crest, just under the toe's front (the claw
        # leaves the toe's tip with its full section); its root wrapped by the nail bed's fold (claw_fold)
        cbase = crest - cback * sc * hd + np.array([0.0, cup * sc, 0.0])
        a_cl = claw_args(cbase, tip, cdep * sc, cwid * sc, W['claw_tip_scale'], ca0, ca1, W['claw_rho'], W['k_claw'],
                         f'{pre}claw{n}{sfx}', taper=W.get('claw_taper', 1.2))
        add_claw(prog, a_cl, info)
        if W.get('claw_fold'):
            i = claw_fold(prog, a_cl, W['claw_fold'], f'{pre}nailfold{n}{sfx}')
            masses.append(prog.names[i])
    # the web between neighbouring toes: one mass, shallow grooves on top
    wdrop, wgroove, wend, wk = W['web']
    for a, b in ((2, 3), (3, 4), (4, 5)):
        ta, tb = toes[a], toes[b]
        sa = 0.5 * (ta['sc'] + tb['sc'])
        p0 = 0.5 * (ta['d1'] + tb['d1']) - np.array([0.0, wdrop, 0.0])
        q1 = 0.5 * (ta['dip'] + tb['dip']) - np.array([0.0, wdrop, 0.0])
        p1 = p0 + wend * (q1 - p0)
        r0_ = r_pip * sa - wgroove + wdrop
        r1_ = (r_pip + wend * (r_dip - r_pip)) * sa - wgroove + wdrop
        i = prog.roundcone(p0, p1, r0_, r1_, k=wk, name=f'{pre}web{a}{b}{sfx}')
        _tag(prog, i, 'paw')
        masses.append(prog.names[i])
    # the metacarpal / metatarsal pad and the knuckle mass over the heads
    ml, mh, ma, mfwd, mr = W['pad_meta'] if fore else W['pad_meta_hind']
    mc = np.array([c[0], mh, c[2] + mfwd])
    # W2g (the lead's call 6: "the heel the carpal / metacarpal pad's mass ... no rounded block with a crease along its
    # top"): the pad's own blend k_meta (the digital pads keep k_pad): the box is wider than the pastern's foot, and at
    # k_pad its top stood as a ledge along the paw's side behind the toes, the crease
    i = prog.roundbox(mc, (ml, mh, ma), r=mr, k=W.get('k_meta', W['k_pad']), name=f'{pre}pad_meta{sfx}')
    _tag(prog, i, 'pad')
    masses.append(prog.names[i])
    kl, kv, ka, kup, kfwd = W['knuckle'] if fore else W['knuckle_hind']
    # a rounded box, its top flat across the four heads (an ellipsoid's top fell away at II and V, whose raised heads'
    # proximal phalanges then stood out as rods, W2d b2)
    i = prog.roundbox(np.array([c[0], kup, c[2] + kfwd]), (kl, kv, ka), r=min(kv, 0.010), k=W['k_palm'],
                      name=f'{pre}palm{sfx}')
    _tag(prog, i, 'paw')
    masses.append(prog.names[i])
    # the ramp: the dorsum's slope from the pastern's front onto the knuckles over III / IV (a tilted rounded box: its
    # top face through the junction J on the pastern's front and the knuckles' top K)
    rup, rslope, rr, rhw, rk = W['ramp'] if fore else W['ramp_hind']
    hd3 = toes[3]['d1'] - toes[3]['d0']
    hd3 = np.array([hd3[0], 0.0, hd3[2]]) / np.linalg.norm([hd3[0], hd3[2]])
    kt = 0.5 * (toes[3]['d1'] + toes[4]['d1']) + np.array([0.0, r_pip, 0.0])       # the knuckles' top
    a_r = np.radians(rslope)
    along = np.cos(a_r) * hd3 - np.sin(a_r) * Y_AX                                # down the ramp, forward
    perp = np.sin(a_r) * hd3 + np.cos(a_r) * Y_AX                                 # its top face's outward normal
    jt = kt - along * ((c[1] + rup - kt[1]) / np.sin(a_r))                        # the junction at the pastern's front
    # the box from J to a radius past K: its back end's rounding sinks into the pastern at J, its flat top runs from a
    # radius past J to K and its front end rounds over onto the toes
    half_along = 0.5 * float(np.linalg.norm(kt - jt)) + 0.5 * rr
    rc = 0.5 * (jt + kt) + along * (0.5 * rr) - perp * rr
    lat = np.cross(perp, along)
    i = prog.roundbox(rc, (rhw, rr, half_along), r=min(rr, rhw), axes=np.column_stack([lat, perp, along]),
                      k=rk, name=f'{pre}ramp{sfx}')
    _tag(prog, i, 'paw')
    masses.append(prog.names[i])
    info.setdefault('ramps', {})[f'{pre}{sfx}'] = (jt, kt)
    # the heel: behind the pastern's foot down into the metacarpal pad (both ends from the head: up, back). W2f (the lead's
    # call 5: "the heel ball behind the pastern blended into the pad (w01's caudal line one curve)"): a TAPERED cone (7
    # values: its radius at the top end and at the pad's end) reaching up the pastern's back, so the caudal outline runs
    # from the pastern down into the pad's back in one slope (W2e's short 7.5 mm cone left the pad's rounded back corner
    # standing behind a dent: the ball)
    hv = W['heel'] if fore else W['heel_hind']
    hy0, hz0, hy1, hz1 = hv[:4]
    hr0, hr1, hk = (hv[4], hv[4], hv[5]) if len(hv) == 6 else hv[4:7]
    # W2g (the lead's call 6: "the heel the carpal / metacarpal pad's mass ... no rounded block with a crease along its
    # top"): an 8th value puts the tapered cone TWICE, `hx` either side of the paw's midline: the heel then spans the
    # metacarpal pad's width at the ground and narrows up the pastern's back and sides (one cone on the midline left
    # the pad's lateral thirds standing out of the pastern's foot as a ledge: the block's top, the crease)
    hx = hv[7] if len(hv) > 7 else 0.0
    for j, sx in enumerate((1.0, -1.0) if hx > 0.0 else (0.0,)):
        i = prog.roundcone(c + np.array([sx * hx, hy0, -hz0]), c + np.array([sx * hx, hy1, -hz1]), hr0, hr1, k=hk,
                           name=f'{pre}heel{sfx}' + ('', 'm')[j])
        _tag(prog, i, 'paw')
        masses.append(prog.names[i])
    if fore:
        # the carpal pad on the back of the carpus (it does not register), and the dewclaw (digit I) with its claw
        cl, ch, ca, cbk, cdown = W['pad_carpal']
        cp = _side_pt(P, 'carpus', side) + np.array([0.0, -cdown, -cbk])
        i = prog.roundcone(cp, cp, ch, ch, k=W['k_pad'], name=f'fpad_carpal{sfx}')
        _tag(prog, i, 'pad')
        masses.append(prog.names[i])
        dj, dt = _side_pt(P, 'f_dewclaw', side), _side_pt(P, 'f_dewclaw_tip', side)
        u = (dt - dj) / np.linalg.norm(dt - dj)
        r1, r2 = W['dewclaw_r']
        dcrest = dt - W['dew_claw'] * u
        i = prog.roundcone(dj, dcrest, r1, r2, k=W['k_digit'], name=f'fdewclaw{sfx}')
        _tag(prog, i, 'paw')
        masses.append(prog.names[i])
        dd, dw = W['dewclaw_section']
        db = dcrest - 0.6 * r2 * u
        chord = float(np.degrees(np.arctan2(db[1] - dt[1], np.hypot(dt[0] - db[0], dt[2] - db[2]))))
        a_dc = claw_args(db, dt, dd, dw, W['claw_tip_scale'], max(chord - 18.0, 5.0), min(chord + 14.0, 86.0),
                         W['claw_rho'], W['k_claw'], f'fdewclawk{sfx}', taper=W.get('claw_taper', 1.2))
        add_claw(prog, a_dc, info)
        if W.get('claw_fold'):
            i = claw_fold(prog, a_dc, W['claw_fold'], f'fdewnailfold{sfx}')
            masses.append(prog.names[i])
    prog.end_group()
    info['groups'].append(dict(name=f'{pre}paw{sfx}', region='paw', lo=lo, hi=len(prog.kind)))
    info.setdefault('pads', {})[f'{pre}{sfx}'] = pads


def compose_body(spec, chain, neck=None):
    """THE COMPOSED BODY (W2-W2c's construction, W2d's START of the body volume): the trunk and neck sweep with its
    masses, the limbs, the paws, as primitives: (prog, info). info: groups, sweeps, the trunk axis, masses (the names
    of the members that are the volume's inner limits), claws (the claw primitives' indices), pads. neck: None (the
    trunk's stations as the SPEC places them, the bind) or (bind neck points, angles): the stations ahead of the
    withers carried with a posed neck (neck_bend: the review pose)"""
    P = chain['pos']
    sk = spec['skin']
    prog = S_.Program()
    prog.coat_tags = {}
    info = dict(groups=[], sweeps={}, spec_skin=sk, masses=[], claws=[])
    # ---- trunk and neck: one sweep, C1 to the point of buttock, plus the withers' mass and the manubrium
    ax = trunk_axis(spec, chain, neck)
    lo = len(prog.kind)
    prog.begin_group(S_.UNION, 0.0)
    i = prog.sweep(ax['P'], ax['N'], ax['r0'], a3=ax['a3'], phi3=np.pi, a4=ax['a4'], aspect=ax['aspect'], name='trunk')
    _tag(prog, i, 'body')
    for name in ('withers', 'manubrium', 'croup'):
        if name not in sk:
            continue
        c, radii, k = sk[name]
        j = prog.ellipsoid(np.array([0.0, c[0], c[1]]), radii, k=k, name=name)
        _tag(prog, j, 'body', i)
        # W2e: SPEC skin.trunk_not_masses (the withers' and the croup's masses) shape the composed start only: as the
        # body volume's inner limits their inset outlines printed through the flowed skin (the withers' oval from the
        # top; the croup's horseshoe round the tail's root where the mass yielded to the photos' back lines)
        if name != 'manubrium' and name not in sk.get('trunk_not_masses', ()):
            info['masses'].append(name)
    # W2d: the pectoral masses either side of the keel's front (SPEC skin.pectorals: (y, z), lateral, radii, k)
    for name, (y_, z_), lat, radii, k in sk.get('pectorals', ()):
        for side in (1, -1):
            j = prog.ellipsoid(np.array([side * lat, y_, z_]), radii, k=k, name=f'{name}{"_L" if side > 0 else "_R"}')
            _tag(prog, j, 'body', i)
            info['masses'].append(prog.names[j])
    # the neck's muscles (SPEC skin neck_muscles): round cones between chain anchors, each side
    for name, ea, eb, r0, r1, k in sk.get('neck_muscles', ()):
        for side in (1, -1):
            pa, pb = _anchor(P, side, *ea), _anchor(P, side, *eb)
            j = prog.roundcone(pa, pb, r0, r1, k=k, name=f'{name}{"_L" if side > 0 else "_R"}')
            _tag(prog, j, 'body', i)
            info['masses'].append(prog.names[j])
    prog.end_group()
    info['groups'].append(dict(name='trunk', region='torso', lo=lo, hi=len(prog.kind), sweep=i))
    info['sweeps']['trunk'] = ax
    info['trunk'] = ax
    # ---- limbs, paws
    for side in (1, -1):
        _limb_group(prog, spec, chain, 'fore', side, 'forelimb', info)
        _limb_group(prog, spec, chain, 'hind', side, 'hindlimb', info)
    for side in (1, -1):
        _paw_group(prog, spec, chain, 'f', side, info)
        _paw_group(prog, spec, chain, 'h', side, info)
    return prog, info


def _tail_group(prog, spec, chain, info, in_group=False):
    """the tail sweep, its own group blended into the body by the tail's k; in_group (W2d's body volume): a MEMBER of
    the group already open, carrying that k itself (the same smooth union, smin of the body's members and the tail,
    but never culled: as a later group it was skipped inside the trunk, and the field under the croup's skin was the
    trunk's alone, a rim round the tail's root, W2d b5)"""
    T = spec['skin']['tail']
    lo = len(prog.kind)
    if not in_group:
        prog.begin_group(S_.UNION, T['k'])
    tax = _path_sweep(chain['pos'], 1, T['path'], n_per_m=300.0, sigma=T.get('smooth', 0.0))
    fil = T.get('fillet') if in_group else None
    if fil is None:
        i = _add_sweep(prog, tax, 'tail', k=T['k'] if in_group else 0.0)
        _tag(prog, i, 'tail')
    else:
        # W2f CHECK: THE FILLET AT THE ROOT ONLY (SPEC skin.tail.fillet = (s0, s1) m along the tail). In the body volume's
        # group the tail's smooth union meets every GRID member's field, and those are CLAMPED far from their skin
        # (wolf_body LEVEL: the limbs and paws +-10 mm, the trunk +-10 under y 360 mm) and extended past their boxes, so
        # wherever the hanging tail lies within the k of a box the smin swells it by a constant: below the hind limbs'
        # box tops (y 318 mm at the review's rest hang) the tail stood +7.0 mm laterally and +2.5 caudally over its own
        # radius (k 32, a field of 10 / D = 9.0 mm), a flat-sided slab starting at a step (check_w2f/probe_tail.py,
        # out/tail_w2f.png). So the tail is TWO sweeps on the same nodes: the root to s1 carries the k (the croup's
        # fillet, the root's own measured swell gone by s 0.11 m), then the rest from s0 in a hard union, its own radius
        # (their overlap s0..s1 coincides, the root's end cap inside the rest)
        s_ = np.asarray(tax['s'], float)
        j1 = int(np.searchsorted(s_, fil[1]))
        j0 = int(np.searchsorted(s_, fil[0]))
        cut = lambda a, b: {k_: (v_[a:b] if isinstance(v_, np.ndarray) and len(v_) == len(s_) else v_)
                            for k_, v_ in tax.items()}
        i = _add_sweep(prog, cut(0, j1 + 1), 'tail', k=T['k'])
        _tag(prog, i, 'tail')
        i2 = _add_sweep(prog, cut(j0, len(s_)), 'tail_rest', k=0.0)
        _tag(prog, i2, 'tail')
    if not in_group:
        prog.end_group()
    info['groups'].append(dict(name='tail', region='tail', lo=lo, hi=len(prog.kind), sweep=i))
    info['sweeps']['tail'] = tax


def build_skin_sdf(spec, chain):
    """THE HAIRLESS CLAY (section comment above): (prog, info). info: groups [dict(name, region, lo, hi)] in program
    order, sweeps {name: axis dict (P, N, r0, aspect, s, core)} for the slope gate, the trunk axis, the head's own
    info (heads/<archetype>.build_head) and the coat tags (also prog.coat_tags). W2d: with SPEC skin.volume the body
    is the species' grid volume (build_volume_sdf)"""
    if spec['skin'].get('volume'):
        return build_volume_sdf(spec, chain)
    prog, info = compose_body(spec, chain)
    _tail_group(prog, spec, chain, info)
    # ---- the head archetype last: its mouth slit must be the program's last primitive (guide §9)
    head = archetype(spec.get('head_archetype', 'canid'))
    info['head'] = head.build_head(prog, spec, chain['head'], info)
    pad_cull_boxes(prog)
    info['coat_tags'] = prog.coat_tags
    return prog, info


def without(prog, idx_drop):
    """the program without the primitives idx_drop (each other primitive kept with its group id and box)"""
    drop = set(int(i) for i in idx_drop)
    sp = S_.Program()
    sp.node_p, sp.node_n, sp.node_r, sp.node_h = prog.node_p, prog.node_n, prog.node_r, prog.node_h
    sp.shell_meshes, sp.shell_thick, sp.shell_tri = prog.shell_meshes, prog.shell_thick, prog.shell_tri
    for i in range(len(prog.kind)):
        if i not in drop:
            sp.kind.append(prog.kind[i])
            sp.op.append(prog.op[i])
            sp.k.append(prog.k[i])
            sp.par.append(prog.par[i].copy())
            sp.names.append(prog.names[i])
    sp.coat_tags = {}
    return sp


def build_volume_sdf(spec, chain):
    """W2d: THE BODY AS GRID VOLUMES (species/wolf_body.py): the composed body (compose_body, at this chain's pose: the
    review pose's neck carried with it) sampled, carved by the photos' side skin lines, flowed between its outer and
    inner limits, stroked, finished; its members (the 2 mm trunk, the 1 mm limbs, the 0.5 mm paws, the right side
    mirrored) GRID members of the program's first group, hard-unioned (their overlaps are identical by construction),
    each paw's claws back as primitives after it; then the tail sweep and the head as before. info adds 'composed' (the
    composed program and its info: the pads, the sweeps), 'body' (the volume's cached result: the silhouette errors,
    the divisors) and 'grids'"""
    from ..species import wolf_body as WB
    from ..species import wolf_body_refs as WR
    from ..species import wolf_strokes as WS
    sk = spec['skin']
    pose = spec['rest'].get('neck_pose')
    neck = None if pose is None else (chain['neck_bind'], pose)
    cprog, cinfo = compose_body(spec, chain, neck)
    claws = set(cinfo['claws'])
    cinfo['group_names'] = {g['name']: [cprog.names[i] for i in range(g['lo'], g['hi']) if i not in claws]
                            for g in cinfo['groups']}
    body_prog = without(cprog, cinfo['claws'])
    sil = WR.side_silhouettes(spec, chain, body_prog)
    st = WS.strokes(spec, chain, body_prog)
    res = WB.body_volume(spec, chain, body_prog, cinfo, sil)
    prog = S_.Program()
    prog.coat_tags = {}
    info = dict(groups=[], sweeps=dict(cinfo['sweeps']), spec_skin=sk, trunk=cinfo['trunk'], composed=(cprog, cinfo),
                body=res, grids={}, strokes=st)
    eye = np.eye(3)
    members = WB.members_of(res)
    # ONE DIVISOR for the body's members: each member's field is its values over its divisor, so two members whose
    # overlaps hold identical values but different divisors meet with a slope kink at their common zero set, which
    # marching cubes interpolates differently there (W2d b3: a dashed line round each limb at the hand-over, the trunk
    # 1.54 against the forelimb 1.10). Every member's values are scaled by 1 / D (D the largest member bound): each
    # stored grid then bounds itself by 1 (its own divisor 1) and reads V / D exactly
    D = max(1.0, max(float(res[f'div_{nm}']) for nm in ('body', 'fore', 'hind', 'fpaw', 'hpaw')))
    info['body_divisor'] = D
    # ALL the body's members in ONE group, the program's FIRST: sdf.Program skips a union member whose box lies farther
    # than the result before its group (+ the group's k), and inside the solid that result is negative while a box
    # distance never is, so a member in a LATER group is skipped wherever an earlier group is already inside. Each member
    # its own group (W2d b1-b4) left the trunk's value wherever the trunk was inside: across the trunk's cut (y 298-304
    # mm, its smooth max raising its interior) the field just under the skin was the trunk's raised value instead of the
    # forelimb's (probe: -0.199 for -0.414 mm, 0.6 mm in), the zero set right but marching cubes misplaced its vertices
    # there: the dashed line round every limb at its parent's cut. The first group is never culled: its field is the
    # members' true minimum. info['groups'] keeps each member's own index range (a paw's with its claws)
    prog.begin_group(S_.UNION, 0.0)
    for m in members:
        lo = len(prog.kind)
        i = prog.grid(np.asarray(m['lo'], float) * 1.0e-3, eye, m['h'] * 1.0e-3, m['values'] * (1.0e-3 / D),
                      name=m['name'])
        _tag(prog, i, {'torso': 'body', 'forelimb': 'forelimb', 'hindlimb': 'hindlimb', 'paw': 'paw'}[m['region']])
        if m['region'] == 'paw':
            sfx = m['name'][-2:]
            pre = m['name'][0]
            for j in cinfo['claws']:
                nm = cprog.names[j]              # e.g. fclaw3_L_0, fdewclawk_L_0: the claw, its side, its piece
                if (nm.startswith(f'{pre}claw') or (pre == 'f' and nm.startswith('fdewclawk'))) and \
                        nm.rsplit('_', 1)[0].endswith(sfx):
                    add_claw(prog, cinfo['claw_args'][nm])        # W2e: a PSWEEP, rebuilt from its arguments
        info['groups'].append(dict(name=m['name'], region=m['region'], lo=lo, hi=len(prog.kind)))
        info['grids'][m['name']] = dict(index=i, divisor=float(prog.par[i][17]) * D, shape=tuple(m['values'].shape),
                                        cell=m['h'])
    # W2e: THE STROKES as STROKE members (the staged patch's kind 10, op DISPLACE) after the body's members and claws,
    # before the tail: evaluated analytically over the grids (W2d baked them in, and the scapular spine's oblique ridge
    # terraced on the 2 mm trunk grid). The grids read V / D, so each weight is divided by D too (the displacement then
    # moves the skin by its height); and a stroke's slope across its direction (0.61 height / sigma, its own part D
    # smaller) must stay within what the divisor leaves for a distance bound, sqrt(1 - 1 / D^2), in quadrature
    lim = float(np.sqrt(max(1.0 - 1.0 / (D * D), 0.0)))
    for nm, h_, s_ in st['effective']:
        assert 0.61 * h_ / s_ / D <= lim + 1e-9, (f'stroke {nm}: slope {0.61 * h_ / s_ / D:.3f} past the bound {lim:.3f} '
                                                  f'(divisor {D:.3f})')
    bnd = tuple(b * 1.0e-3 for b in WS.BAND)
    st_lo = len(prog.kind)
    for nm, c_, n_, s_, w_ in st['members']:
        prog.stroke(np.asarray(c_, float) * 1.0e-3, n_, s_ * 1.0e-3, w_ * 1.0e-3 / D, band=bnd, name=f'stroke_{nm}')
    info['stroke_range'] = (st_lo, len(prog.kind))
    _tail_group(prog, spec, chain, info, in_group=True)
    prog.end_group()
    head = archetype(spec.get('head_archetype', 'canid'))
    info['head'] = head.build_head(prog, spec, chain['head'], info)
    pad_cull_boxes(prog)
    info['coat_tags'] = prog.coat_tags
    return prog, info


def pad_cull_boxes(prog):
    """pad each blended member's culling box by its own blend k (in place; the program's own data, sdf.py unchanged).
    sdf.Program skips a UNION member whose box lies farther than the result before its group plus the GROUP's k; but a
    member blended into its group by its own k still lowers the group's field up to k beyond its own distance, so such
    a member was culled where it mattered: the head's zygoma (k 22 mm) and cheek flipped in and out at their boxes'
    faces and printed a 0.2-0.3 mm vertical seam down the side of the neck (W2 final close-up, p22_cull.py). A member
    then counts only where field < d_before + k_group + k_member, which the padded box guarantees for an exact field"""
    for i in range(len(prog.kind)):
        k = float(prog.k[i])
        if k > 0.0 and prog.par[i][24] > -1.0e8:
            prog.par[i][24:27] -= k
            prog.par[i][27:30] += k
    prog._dev = None
