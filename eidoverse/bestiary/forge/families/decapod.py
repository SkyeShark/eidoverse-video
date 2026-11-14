"""DECAPOD family generator: the European lobster first (work/bestiary/research/LOBSTER_PLAN.md §10, §4, §2; §12 step
X1). The recipe family stays `arthropod` with the body plan `decapod` (plan §5.1): families/arthropod.py's frame and
mirror rules are imported here, never copied or edited.

X1 (10-28): the rest chain and the plan's 167-joint skeleton (§10.1), bound RAISED in the walking stance with c06's
crouch as the REST pose (the lead's call, 10-28). The per-part clay programs (X2) and the cages (X4) come later.

UNITS AND FRAME: everything here is LIFE MILLIMETRES (species/lobster.py's SPEC) in the plan frame: the orbit (its
posterior margin) on the midline at z 0, +z forward, +y up from the GROUND, +x the creature's LEFT. skeleton(spec,
chain) multiplies ONCE by SPEC author_scale: rig.Skeleton in metres at x4 (plan §5.8).

THE BIND (rest_chain(spec)):
  - THE BODY: the carapace keeps c06's SOLVED profile (rest.c06, X0b (9): its dorsal line level within 3 mm) lifted by
    rig.lift (= rest.c10.margin - c06's margin), so its lower margin at the deepest station stands at c10's 38.3 mm and
    its dorsum at that margin + L1's own depth (body.cara_depth): 87.1 mm. The body joint sits on the midline at
    rig.body_z (the coxae's mean z), rig.body_frac of the way up from the margin to the dorsum; its bone runs to the
    rostrum's tip (z body.rostrum, at the carapace's front top height). The root stands on the ground under it.
  - THE WALKING LEGS P2-P5 (leg_points, solve_leg): each coxa pivots at its medial articulation (legs.coxae x, z; X0b
    (6)), rig.coxa_drop below the carapace's margin, and runs level along the leg's plane at azimuth theta (from
    forward toward the left; n01's pinned coxae are lateral, so theta 90 is promotion 0). The basi-ischium and the
    merus continue straight (the ischium-merus joint at 0) in that vertical plane at elevation e (the levation: the
    coxa is level); the knee bends the carpus down in the plane to the included angle alpha; the carpus-propodus joint
    deflects the propodus by delta about the axis in the plane normal to the carpus (+ swings it back); the
    propodus-dactyl joint flexes the dactyl by phi about the knee's axis carried by that deflection (P2 / P3: phi 0,
    their small chelae closed along the fixed finger). Solved per leg by SLSQP: the dactyl's tip ON the ground, its
    lateral offset inside c08's raised stance (rig.tip_x), the knee's and the tip's plan azimuths (seen from the
    medial articulation) inside c03 / c01's spreads widened by rig.az_pad (photo_directions over x1.*), every joint
    inside its range (rig.ranges.walking, plan §10.3; the carpus-propodus widened to +-45 by the photos, the levation to
    +70 by c06's crouch), and the joints NEAR MID-RANGE: minimise the squared distances of the levation, the knee, the deflection and (P4 / P5) the
    dactyl from their ranges' middles over their half-ranges, plus the pulls of the photos' median knee and tip
    azimuths (rig.leg_az, weight 1 / rig.knee_sigma^2). Then a bisection on e stands the tip on the ground to 1e-12 mm.
  - THE CHELIPEDS (solve_cheliped, claw): the same proximal chain (coxa rig.cheliped.coxa; basi-ischium, merus,
    carpus rig.cheliped.seg, measured at X2: the carpus M1's own, c11); the carpus ends at the wrist W (the carpal
    joint), inside rig.cheliped.wrist_x out, rig.cheliped.wrist_z AHEAD of the orbit (X2: the mean of c11's two traced
    wrists, the lead's 'the wrists near c11's'), at the height that puts the CRUSHER's fixed finger tip
    rig.cheliped.tip_h above the ground with the claw axis (wrist to that tip) pitched rig.cheliped.claw_pitch down and
    yawed rig.cheliped.claw_yaw (converging): forward and low (v01). The wrist is a single-axis hinge about the claw's
    dorsoventral axis (it turns the claw in, c11 / c08), so the carpus must lie in its hinge plane. Solved (SLSQP): the
    coxa's azimuth, the levation and W's x (its z held), the carpus exactly its length from the knee and in the wrist's
    plane, every joint inside its range (rig.ranges.cheliped: the promotion is the cheliped's own, forward, c11), the
    joints near mid-range. The proximal chain and W
    mirror to the right; the CLAWS are sided BY TYPE (handedness L: the crusher's propodus and dactyl on the left, the
    cutter's on the right, plan §2.3) on the shared claw axis. The fingers' plane is vertical with the dactyl the upper
    finger (c06 / c10 / c08), hinged rig.cheliped.hinge (the crusher's) / rig.cheliped.cutter_hinge (the cutter's)
    above the axis (X2: each measured at M1's articulation knob, c11) and open rig.cheliped.dactyl_open (v01). X4f (the
    lead's call 1 on the X4e check): the hinge is the CONDYLE's axis where the photos put it, under the top margin (n04's
    ball on the broad face), so its place along the axis is a SPEC row too (rig.cheliped.hinge_s / cutter_hinge_s): the
    claw rule (the closed tip Ld from the hinge at height c) stays the fallback for a claw without one.
  - THE ABDOMEN straight at Pope's length (question 1b, option (a)): abd_1 at the carapace's posterior margin (z -CL),
    abd_2..6 and the telson at M1's tergite boundaries (abdomen.segs), all on one level line rig.abd_hinge x
    abdomen.d2 below somite 2's top; the telson's tip at z -(CL + abdomen): TL = 276.6 mm. The uropods spread so the
    exopods' tips span the fan (abdomen.fan_spread); the pleopods on somites 1-5.
  - THE HEAD: the eyestalks (two articles to the cornea's centre at body.eye_z, half body.cornea_spacing out, c06's eye
    height), the antennae (three peduncle articles, then the flagellum on rig.antenna.n_flag equal straightened steps,
    straight at the bind, the yaw at its range's middle), the antennules (three articles, two flagella of
    rig.antennule.n_flag joints), the third maxillipeds (three articles under the head).

THE REST POSE (rest_pose(spec, sk, chain)): c06's crouch as JOINT ROTATIONS on the bound skeleton (posed()), with the
body joint lowered by rig.lift to c06's solved heights: each walking leg re-solved near mid-range (rest_leg) with its
tip on the ground at c06's own near tip's z (rig.rest_tip_z) and at the glass of c06's central camera, the camera its
heights come from (rig.rest_tip_x), then posed by the
changes of (theta, e, alpha, delta, phi) about its joints' axes; the abdomen curled with abd_1 straight, abd_5..telson
at rig.rest_curl_back and abd_2..4 solved so the abdomen's lowest point rests on the sand (c06's own contact would need
the back past its range: L1's abdomen is Pope's straight length), the uropods folded only if a blade would dip under
the sand, pleopods 2-5 folded forward (rig.rest_pleopod_fold; X2b: the bind already tucks them forward along the
sternites, rig.pleopod.tilt / drop_25 / at_25, so the fold is 0); the chelipeds' levation turned until the crusher's
lowest point (its palm's lateral margin, rig.cheliped.low_point: X2) rests on the ground (c06: the crusher lies on the
sand); the IK targets follow their drivers. X2b: given the clay (rest_pose's shells), the abdomen and the chelae rest
their SHELLS' lowest points instead.

skeleton(spec, chain): §10.1's 167 joints; parents before children; IK targets leaves of the root. Frames
(rig.frame_from): x along the bone to its child (or to a leaf's tip), y the side it folds toward, so a positive
rotation about z = x cross y folds the joint the anatomical way (AG 05.7):
  body, abd_1..6, telson         ventral flexion (the tail curls under)
  uropod (the protopod)          the fan folds under; uropod_endo / _exo adduct (the fan closes); uropod_exo_dist folds
                                 down at the diaeresis
  pleopod_1..5                   the power stroke (the tip swings back)
  eyestalk_0 / _1                the stalk swings medially (into the orbit) / the cornea pitches up
  antenna_0                      sweeps back (toward its yaw's -10); antenna_1, _2 flex ventrally
  flagellum_00..15               curls back (the whip sweeps back along the body, c03)
  antennule_*                    flick down
  mxp3_0 / mxp3_1, _2            swings down (opens) / curls medially
  coxa                           remotion (the leg swings back about the vertical: the arthropod convention)
  basis                          levation (the knee rises)
  merus                          the ischium-merus rotation (the knee swings back, +-10)
  carpus                         flexion (the knee closes)
  propodus (walking legs)        the distal leg swings back (the carpus-propodus bender)
  propodus (chelipeds)           the wrist adducts (the claw swings medially: the claws fold before the face)
  dactyl                         P4 / P5 flex; P2 / P3 and the chelae OPEN (0 closed: plan §10.3)
The fold vectors are the construction's own hinge axes (the coxa CAUDAL, the basis DORSAL, the carpus toward the
merus, the propodus a_cp x u_p, the dactyl a_pd x u_d), so posing the skeleton about each z reproduces the
construction: rest_pose relies on it and x01 checks it. The right side is the left reflected under arthropod.py's
written rule (AG 05.8): p_R = M p_L, F_R = M F_L diag(1, 1, -1), M = diag(-1, 1, 1). The chelae are sided by type: the
right propodus and dactyl are the CUTTER's, built on the left and reflected by the same rule, so equal bends still
mirror. sk.meta[name]: role, tier (0 body / legs / chelae, 1 dactyls, uropods, pleopods, antennae, IK, 2 face), side,
fold, tip, driver, parent, claw (crusher / cutter on the propodus and dactyl of the chelipeds).
"""
import numpy as np
from scipy.optimize import brentq, fsolve, minimize

from .. import rig as RG
from .arthropod import CAUDAL, DORSAL, LATERAL, VENTRAL, mirror_frame, mirror_point

MEDIAL = -LATERAL                                     # the left side's inward
UP = DORSAL
WALK = ('P2', 'P3', 'P4', 'P5')
SEGS = ('coxa', 'basis', 'merus', 'carpus', 'propodus', 'dactyl')
LANDMARKS = ('orbit', 'eye_c', 'front_top', 'cervical', 'post_top', 'deep_top', 'deep_bot', 'abd2_top', 'abd2_pleuron')


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def perp(v, x):
    """v made perpendicular to the unit vector x"""
    v = np.asarray(v, np.float64)
    return v - x * float(v @ x)


def rotm(axis, deg):
    """the right-handed rotation by deg about axis (Rodrigues)"""
    a = _unit(axis)
    t = np.radians(deg)
    K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    return np.eye(3) + np.sin(t) * K + (1.0 - np.cos(t)) * (K @ K)


def rz(deg):
    """a local rotation about a joint's own z (its bend axis)"""
    return rotm([0.0, 0.0, 1.0], deg)


def azimuth(p, o):
    """the plan azimuth (deg) of p seen from o: from forward (+z) toward the left (+x)"""
    return float(np.degrees(np.arctan2(p[0] - o[0], p[2] - o[2])))


def heading(yaw, pitch=0.0):
    """a unit vector yaw deg from forward toward the left in plan, pitched pitch deg up"""
    a, e = np.radians(yaw), np.radians(pitch)
    return np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])


def angle(a, b):
    """the angle between two vectors (deg)"""
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b)), float(np.dot(a, b)))))


def mid_half(rng):
    return 0.5 * (rng[0] + rng[1]), 0.5 * (rng[1] - rng[0])


# --------------------------------------------------------------------------------------------- the body
def levels(spec, lift):
    """the carapace's landmarks at a lift over c06's solved crouch, {name: (z, h)} life mm; the margin and the dorsum at
    the deepest station; the coxae's height; the body joint; the rostrum's tip; the cornea's height; the abdominal
    hinge line"""
    r, b, rg = spec['rest'], spec['body'], spec['rig']
    lm = {nm: (float(r['c06'][nm][0]), float(r['c06'][nm][1]) + lift) for nm in LANDMARKS}
    margin, dorsum = lm['deep_bot'][1], lm['deep_top'][1]
    return dict(lift=lift, lm=lm, margin=margin, dorsum=dorsum, y_cox=margin - rg['coxa_drop'],
                body=np.array([0.0, margin + rg['body_frac'] * (dorsum - margin), rg['body_z']]),
                rostrum=np.array([0.0, lm['front_top'][1], b['rostrum']]), y_eye=lm['eye_c'][1],
                y_abd=lm['abd2_top'][1] - rg['abd_hinge'] * spec['abdomen']['d2'])


# --------------------------------------------------------------------------------------------- the walking legs
def leg_lengths(spec, leg):
    """(coxa, basi-ischium, merus, carpus, propodus, dactyl), life mm"""
    lg = spec['legs']
    if leg in ('P4', 'P5'):
        L = lg[leg]
        return (L['coxa'], L['basis_ischium'], L['merus'], L['carpus'], L['propodus'], L['dactyl'])
    return (lg['coxa'],) + tuple(spec['rig']['p23'])


def medial_articulation(spec, leg, y):
    cx = spec['legs']['coxae'][leg]
    return np.array([cx[0], y, cx[1]])


def leg_points(M, lengths, theta, e, alpha, delta, phi):
    """one LEFT walking leg from its medial articulation M (module docstring): the joints M (thorax-coxa), B
    (coxa-basis), I (ischium-merus), K (merus-carpus), P (carpus-propodus), D (propodus-dactyl), the dactyl's tip T, the
    bone directions and the hinge axes (a_k the knee's, a_cp the deflection's, a_pd the dactyl's)"""
    Lc, Lb, Lm, Lk, Lp, Ld = lengths
    h = heading(theta)
    n_p = np.cross(h, UP)                               # the leg plane's normal (forward for a lateral leg)
    um = np.cos(np.radians(e)) * h + np.sin(np.radians(e)) * UP
    ec = e - (180.0 - alpha)
    uc = np.cos(np.radians(ec)) * h + np.sin(np.radians(ec)) * UP
    a_cp = -np.sin(np.radians(ec)) * h + np.cos(np.radians(ec)) * UP
    Rd = rotm(a_cp, delta)
    up = Rd @ uc
    a_k = -n_p
    a_pd = Rd @ a_k
    ud = rotm(a_pd, phi) @ up
    B = M + Lc * h
    I = B + Lb * um
    K = I + Lm * um
    P = K + Lk * uc
    D = P + Lp * up
    T = D + Ld * ud
    return dict(M=M, B=B, I=I, K=K, P=P, D=D, T=T, h=h, n_p=n_p, um=um, uc=uc, up=up, ud=ud, a_k=a_k, a_cp=a_cp,
                a_pd=a_pd)


def photo_directions(spec):
    """the walking legs' plan directions on c03 / c01 (x1.*: (z, x) CL, the right side mirrored), as azimuths (deg)
    seen from each leg's medial articulation: {leg: dict(knee=[(photo, side, az)], tip=[...])}"""
    CL, out = spec['body']['CL'], {}
    for photo, pts in spec['x1'].items():
        for key, (z, x) in pts.items():
            leg, side, what = key.split('_')
            cx = spec['legs']['coxae'][leg]
            az = azimuth(np.array([x * CL, 0.0, z * CL]), np.array([cx[0], 0.0, cx[1]]))
            out.setdefault(leg, dict(knee=[], tip=[]))[what].append((photo, side, az))
    return out


def direction_bounds(spec, leg):
    """(the knee's, the tip's) azimuth bounds: each reading spread widened by rig.az_pad"""
    pd, pad = photo_directions(spec)[leg], spec['rig']['az_pad']
    return tuple((min(a for _, _, a in pd[w]) - pad, max(a for _, _, a in pd[w]) + pad) for w in ('knee', 'tip'))


def solve_leg(spec, leg, lv, tip_band=None, tip_z=None):
    """one LEFT walking leg (module docstring) with its coxae at lv's height: SLSQP over (theta, e, alpha, delta[, phi])
    inside every range (rig.ranges.walking: the promotion bounds theta about n01's lateral 90), the knee's azimuth
    inside the photos' spread (direction_bounds) and the tip's lateral offset inside tip_band (CL; the bind's rig.tip_x,
    the rest pose's rig.rest_tip_x). The bind holds the tip's azimuth inside the photos' spread too; the REST pose
    (tip_z given) instead stands the tip at c06's own z. Then a bisection on e so the tip stands on the ground to
    1e-12 mm. Returns dict(theta, e, alpha, delta, phi, pts=leg_points(...), cost, terms)"""
    rg, CL = spec['rig'], spec['body']['CL']
    rw = rg['ranges']['walking']
    M = medial_articulation(spec, leg, lv['y_cox'])
    lens = leg_lengths(spec, leg)
    th_k, th_t = rg['leg_az'][leg]
    (k_lo, k_hi), (t_lo, t_hi) = direction_bounds(spec, leg)
    lo, hi = rg['tip_x'] if tip_band is None else tip_band
    free_phi = leg in ('P4', 'P5')
    (m_e, h_e), (m_a, h_a), (m_d, h_d), (m_p, h_p) = (mid_half(rw[k]) for k in ('levation', 'knee', 'carpus_propodus',
                                                                                 'dactyl'))
    sig = rg['knee_sigma']

    def unpack(q):
        return (q[0], q[1], q[2], q[3], q[4] if free_phi else 0.0)

    def terms(q):
        th, e, a, d, p = unpack(q)
        T = leg_points(M, lens, th, e, a, d, p)['T']
        out = dict(levation=((e - m_e) / h_e) ** 2, knee=((a - m_a) / h_a) ** 2, carpus_propodus=((d - m_d) / h_d) ** 2,
                   knee_azimuth=((th - th_k) / sig) ** 2)
        if tip_z is None:
            out['tip_azimuth'] = ((azimuth(T, M) - th_t) / sig) ** 2
        if free_phi:
            out['dactyl'] = ((p - m_p) / h_p) ** 2
        return out

    def cost(q):
        return float(sum(terms(q).values()))

    def ground(q):
        T = leg_points(M, lens, *unpack(q))['T']
        return np.array([T[1] / 10.0] + ([] if tip_z is None else [(T[2] - tip_z) / 10.0]))

    def inside(q):
        T = leg_points(M, lens, *unpack(q))['T']
        a, x = azimuth(T, M), T[0] / CL
        return np.array(([a - t_lo, t_hi - a] if tip_z is None else []) + [x - lo, hi - x])

    p_lo, p_hi = rw['promotion']
    bounds = [(max(k_lo, 90.0 - p_hi), min(k_hi, 90.0 - p_lo)), tuple(rw['levation']), tuple(rw['knee']),
              tuple(rw['carpus_propodus'])] + ([tuple(rw['dactyl'])] if free_phi else [])
    best = None
    for e0 in (5.0, 15.0, 25.0):
        q0 = [float(np.clip(th_k, *bounds[0])), e0, m_a, 0.0] + ([m_p] if free_phi else [])
        sol = minimize(cost, q0, method='SLSQP', bounds=bounds,
                       constraints=[dict(type='eq', fun=ground), dict(type='ineq', fun=inside)],
                       options=dict(ftol=1e-12, maxiter=1000))
        if sol.success and (best is None or sol.fun < best.fun):
            best = sol
    assert best is not None, f'{leg}: no stance inside the ranges and the photos\' spreads'
    th, e, a, d, p = unpack(best.x)
    if tip_z is None:
        e = brentq(lambda z: leg_points(M, lens, th, z, a, d, p)['T'][1], e - 2.0, e + 2.0, xtol=1e-13)
    else:
        e, a = fsolve(lambda v: leg_points(M, lens, th, v[0], v[1], d, p)['T'][[1, 2]] - [0.0, tip_z], [e, a],
                      xtol=1e-13)
    q = [th, e, a, d] + ([p] if free_phi else [])
    return dict(theta=float(th), e=float(e), alpha=float(a), delta=float(d), phi=float(p), M=M, lens=lens,
                pts=leg_points(M, lens, th, e, a, d, p), cost=cost(q), terms=terms(q), bounds=bounds,
                knee_bounds=(k_lo, k_hi), tip_bounds=(t_lo, t_hi))


def rest_leg(spec, leg, lv0):
    """the REST pose's leg (c06's crouch): the coxae at c06's height (lv0), the tip on the ground at c06's own near tip's
    z (rig.rest_tip_z) and at the glass (rig.rest_tip_x: 0.513-0.573 CL out through c06's central camera, the camera
    rest.c06's heights come from), the knee inside c03 / c01's spread, the joints near mid-range (solve_leg). The leg
    folds into c06's tall arch, the knee high beside the carapace, at a levation of 58-68 deg (the X1 review widened
    rig.ranges.walking.levation to +70 for it). X0b's all-camera band (0.40-1.05 CL) had let the feet splay to about
    1.0 CL out, past the central camera's glass"""
    return solve_leg(spec, leg, lv0, tip_band=spec['rig']['rest_tip_x'], tip_z=spec['rig']['rest_tip_z'][leg])


# --------------------------------------------------------------------------------------------- the chelipeds
def cheliped_lengths(spec):
    """(coxa, basi-ischium, merus, carpus), life mm"""
    c = spec['rig']['cheliped']
    return (c['coxa'],) + tuple(c['seg'])


def claw_axis(spec):
    """the LEFT claw's axis (the wrist to the fixed finger's tip): yaw rig.cheliped.claw_yaw, pitched claw_pitch down"""
    c = spec['rig']['cheliped']
    return heading(c['claw_yaw'], -c['claw_pitch'])


def wrist_height(spec):
    """the wrist's height: the crusher's fixed finger tip rig.cheliped.tip_h above the ground"""
    c = spec['rig']['cheliped']
    return c['tip_h'] + spec['chela']['crusher_len'] * np.sin(np.radians(c['claw_pitch']))


def cheliped_points(M, lengths, theta, e):
    """the LEFT cheliped's coxa (level along theta), basi-ischium and merus (straight, elevation e): B, I, K"""
    Lc, Lb, Lm = lengths[:3]
    h = heading(theta)
    um = np.cos(np.radians(e)) * h + np.sin(np.radians(e)) * UP
    B = M + Lc * h
    return dict(M=M, h=h, um=um, B=B, I=B + Lb * um, K=B + (Lb + Lm) * um)


def wrist_axis(d):
    """the wrist's hinge axis for the LEFT claw axis d: z of the frame x = d, y = MEDIAL made perpendicular (the claw's
    dorsoventral axis: the wrist swings the claw in and out, c11 / c08)"""
    return _unit(np.cross(d, perp(MEDIAL, d)))


def wrist_angle(c, d):
    """the wrist's bind angle (deg): the rotation about the wrist's hinge axis that takes the carpus direction c to the
    claw axis d (+ adduction: the claw swings medially), the LEFT side; exact when c lies in the hinge plane"""
    z = wrist_axis(d)
    return float(np.degrees(np.arctan2(float(np.cross(c, d) @ z), float(c @ d))))


def solve_cheliped(spec, lv):
    """the LEFT cheliped at the bind (module docstring): SLSQP over (theta, e, the wrist's x and z) inside every range
    (rig.ranges.cheliped) and the wrist's band (rig.cheliped.wrist_x), with the carpus exactly its length from the knee
    AND lying in the wrist's hinge plane (the wrist is a single-axis hinge about the claw's dorsoventral axis, so the
    claw's pitch must come from the levation and the elbow, not the wrist), and (X2) the wrist's z held at
    rig.cheliped.wrist_z when the SPEC has it; then Newton so the equalities hold to 1e-12: on (x, z) with z free, on
    (e, x) with z held. Returns dict(theta, e, W, alpha, omega, pts, d, cost, terms)"""
    rg = spec['rig']
    rc = rg['ranges']['cheliped']
    M = medial_articulation(spec, 'P1', lv['y_cox'])
    lens = cheliped_lengths(spec)
    d = claw_axis(spec)
    zw_ax = wrist_axis(d)
    yw = wrist_height(spec)
    z_held = rg['cheliped'].get('wrist_z')
    (m_p, h_p), (m_e, h_e), (m_a, h_a), (m_w, h_w) = (mid_half(rc[k]) for k in ('promotion', 'levation', 'knee',
                                                                                 'wrist'))

    def geo(q):
        G = cheliped_points(M, lens, q[0], q[1])
        W = np.array([q[2], yw, q[3]])
        c = _unit(W - G['K'])
        return G, W, c, angle(G['I'] - G['K'], W - G['K']), wrist_angle(c, d)

    def terms(q):
        G, W, c, a, w = geo(q)
        return dict(promotion=((90.0 - q[0] - m_p) / h_p) ** 2, levation=((q[1] - m_e) / h_e) ** 2,
                    knee=((a - m_a) / h_a) ** 2, wrist=((w - m_w) / h_w) ** 2)

    def cost(q):
        return float(sum(terms(q).values()))

    def eqs(q):
        G, W, c, _, _ = geo(q)
        out = [(np.linalg.norm(W - G['K']) - lens[3]) / 10.0, float(c @ zw_ax)]
        if z_held is not None:
            out.append((q[3] - z_held) / 10.0)
        return np.array(out)

    def inside(q):
        _, _, _, a, w = geo(q)
        return np.array([a - rc['knee'][0], rc['knee'][1] - a, w - rc['wrist'][0], rc['wrist'][1] - w])

    bounds = [(90.0 - rc['promotion'][1], 90.0 - rc['promotion'][0]), tuple(rc['levation']),
              tuple(rg['cheliped']['wrist_x']), (-100.0, 250.0)]
    best = None
    for th0, e0, x0, z0 in ((60.0, 10.0, 50.0, 50.0), (50.0, 0.0, 40.0, 70.0), (70.0, 20.0, 60.0, 40.0),
                            (40.0, 5.0, 45.0, 80.0), (75.0, 5.0, 60.0, 30.0), (65.0, 0.0, 55.0, 35.0)):
        z0 = z0 if z_held is None else z_held
        sol = minimize(cost, [th0, e0, x0, z0], method='SLSQP', bounds=bounds,
                       constraints=[dict(type='eq', fun=eqs), dict(type='ineq', fun=inside)],
                       options=dict(ftol=1e-12, maxiter=1000))
        if sol.success and (best is None or sol.fun < best.fun):
            best = sol
    assert best is not None, 'cheliped: no carriage inside the ranges'
    th, e = best.x[:2]
    if z_held is None:
        xz = fsolve(lambda v: eqs([th, e, v[0], v[1]]), best.x[2:], xtol=1e-13)
        q = [th, e, xz[0], xz[1]]
    else:       # the wrist held (X2): its x may sit on its band's edge, so the coxa's azimuth and the levation polish
        te = fsolve(lambda v: eqs([v[0], v[1], best.x[2], z_held])[:2], best.x[:2], xtol=1e-13)
        q = [te[0], te[1], best.x[2], z_held]
        assert bounds[0][0] - 1e-6 <= q[0] <= bounds[0][1] + 1e-6 and \
            bounds[1][0] - 1e-6 <= q[1] <= bounds[1][1] + 1e-6, \
            f'cheliped: the polish left its bounds (azimuth {q[0]:.6f}, levation {q[1]:.6f})'
    G, W, c, a, w = geo(q)
    return dict(theta=float(q[0]), e=float(q[1]), W=W, alpha=float(a), omega=float(w), M=M, lens=lens, pts=G, d=d,
                cost=cost(q), terms=terms(q), plane=float(c @ zw_ax))


def claw(spec, W, d, kind):
    """one claw on the LEFT at the wrist W along the axis d, of type kind ('crusher' or 'cutter'): the fixed finger's
    tip, the dactyl's hinge H, its direction (open by rig.cheliped.dactyl_open) and tip, and the fingers' plane's
    vector n (the dactyl's side). X4f: H's place along the axis is rig.cheliped.hinge_s (cutter_hinge_s) x L where the
    SPEC has it (the condyle's, the photos'), else the claw rule's.
    A0 (11-10, the lead's shape audit, point 4): THE FINGERS' PLANE is rig.cheliped.claw_plane deg up from FLAT: at 0
    n is the wrist's own fold vector perp(MEDIAL, d), so the dactyl is the MEDIAL finger, the broad faces are dorsal
    and ventral, and the wrist's hinge axis (wrist_axis) is the claw's THICKNESS: the claw swings in its own plane (c10,
    c06, v01, c01, c03, c11 measured: lobster.py's row). Without the row: X1-X4h's vertical plane (n up)"""
    ch, c = spec['chela'], spec['rig']['cheliped']
    L = ch[f'{kind}_len']
    palm = ch[f'{kind}_palm']
    Ld = ch['crusher_dactyl'] if kind == 'crusher' else c['cutter_dactyl'] * L
    tau = c.get('claw_plane')
    if tau is None:
        n = _unit(perp(UP, d))
    else:                                   # (wrist_axis(d) = d x perp(MEDIAL, d) points down on the left: - it is up)
        n = _unit(np.cos(np.radians(tau)) * _unit(perp(MEDIAL, d)) - np.sin(np.radians(tau)) * wrist_axis(d))
    hg = c['cutter_hinge'] if kind == 'cutter' and 'cutter_hinge' in c else c['hinge']   # X2: each claw's own (c11)
    b, cc = hg[0] * palm, hg[1] * palm
    hs = c.get('cutter_hinge_s' if kind == 'cutter' else 'hinge_s')
    a = hs * L if hs is not None else L - np.sqrt(Ld ** 2 - (b - cc) ** 2)
    H = W + a * d + b * n
    u_closed = _unit(W + L * d + cc * n - H)
    a_h = _unit(np.cross(u_closed, n))
    u = rotm(a_h, c['dactyl_open']) @ u_closed
    return dict(kind=kind, L=L, Ld=Ld, palm=palm, tip=W + L * d, H=H, u_closed=u_closed, u=u, dactyl_tip=H + Ld * u,
                n=n, a_h=a_h)


# --------------------------------------------------------------------------------------------- the abdomen and head
def abdomen_points(spec, lv):
    """the straight abdomen: the joints' z (abd_1..6, the telson), the telson's tip, the pleopods and the LEFT uropods"""
    ab, rg, CL = spec['abdomen'], spec['rig'], spec['body']['CL']
    y = lv['y_abd']
    z = [-CL]
    for s in ab['segs'][:6]:
        z.append(z[-1] - s)
    P = {f'abd_{k + 1}': np.array([0.0, y, z[k]]) for k in range(6)}
    P['telson'] = np.array([0.0, y, z[6]])
    P['telson_tip'] = np.array([0.0, y, z[6] - ab['segs'][6]])
    pl = rg['pleopod']
    for k in range(5):
        base = np.array([pl['x'], y - pl['drop'] * ab['d2'], z[k] - 0.5 * ab['segs'][k]])
        if k > 0 and 'drop_25' in pl:       # X2b: pleopods 2-5 tucked forward along the sternites from at_25
            d25 = pl['drop_25'][k - 1] if isinstance(pl['drop_25'], (tuple, list)) else pl['drop_25']
            base = np.array([pl.get('x_25', pl['x']), y - d25 * ab['d2'], z[k] - pl['at_25'] * ab['segs'][k]])
        if k == 0:
            dv = np.array([0.0, -np.sin(np.radians(pl['tilt1'])), np.cos(np.radians(pl['tilt1']))])
            length = pl['len1']
        else:                               # X2c: splayed splay_25 deg outward (+x on the left) into the slot
            sp = np.radians(pl.get('splay_25', 0.0))
            fwd = -np.sin(np.radians(pl['tilt']))
            dv = np.array([np.sin(sp) * fwd, -np.cos(np.radians(pl['tilt'])), np.cos(sp) * fwd])
            length = pl['len']
        P[f'pleopod_{k + 1}_L'] = base
        P[f'pleopod_{k + 1}_tip_L'] = base + length * dv
    u, zt = rg['uropod'], z[6]
    P['uropod_L'] = np.array([u['base'][0], y, zt + u['base'][1]])
    P['uropod_endo_L'] = np.array([u['endo'][0], y, zt + u['endo'][1]])
    P['uropod_endo_tip_L'] = np.array([u['endo_tip_x'], y, zt - ab['segs'][6] * ab['uropod_reach']])
    P['uropod_exo_L'] = np.array([u['exo'][0], y, zt + u['exo'][1]])
    P['uropod_exo_dist_L'] = np.array([u['exo_dist'][0], y, zt + u['exo_dist'][1]])
    P['uropod_exo_tip_L'] = np.array([0.5 * ab['fan_spread'], y, zt + u['exo_tip_dz']])
    P['uropod_end_L'] = 0.5 * (P['uropod_endo_L'] + P['uropod_exo_L'])       # the protopod's bone end
    return P


def head_points(spec, lv):
    """the LEFT eyestalk, antenna (peduncle + flagellum), antennule (peduncle + two flagella) and third maxilliped"""
    b, rg, an = spec['body'], spec['rig'], spec['antenna']
    ye = lv['y_eye']
    P = {}
    C = np.array([0.5 * b['cornea_spacing'], ye, b['eye_z']])
    es = rg['eyestalk']
    P['eyestalk_0_L'] = np.array([es['base'][0], ye + es['base'][1], es['base'][2]])
    P['eyestalk_1_L'] = P['eyestalk_0_L'] + es['mid'] * (C - P['eyestalk_0_L'])
    P['cornea_L'] = C
    a = rg['antenna']
    ua = heading(a['yaw'], a['pitch'])
    p = np.array([a['base'][0], ye + a['base'][1], a['base'][2]])
    for k in range(3):
        P[f'antenna_{k}_L'] = p.copy()
        p = p + a['ped'][k] * ua
    nf = a['n_flag']
    step = an['flagellum'] / nf
    for k in range(nf):
        P[f'flagellum_{k:02d}_L'] = p + k * step * ua
    P['antenna_tip_L'] = p + an['flagellum'] * ua
    n = rg['antennule']
    un = heading(n['yaw'], n['pitch'])
    p = np.array([n['base'][0], ye + n['base'][1], n['base'][2]])
    for k in range(3):
        P[f'antennule_{k}_L'] = p.copy()
        p = p + n['ped'][k] * un
    Lf = an['antennule'] - sum(n['ped'])
    for fl, sgn in (('lat', 1.0), ('med', -1.0)):
        uf = heading(n['yaw'] + sgn * n['split'], n['pitch'])
        for k in range(n['n_flag']):
            P[f'antennule_{fl}_{k}_L'] = p + k * (Lf / n['n_flag']) * uf
        P[f'antennule_{fl}_tip_L'] = p + Lf * uf
    m = rg['mxp3']
    um = heading(m['yaw'], m['pitch'])
    p = np.array([m['base'][0], lv['margin'] + m['base'][1], m['base'][2]])
    for k in range(3):
        P[f'mxp3_{k}_L'] = p.copy()
        p = p + m['seg'][k] * um
    P['mxp3_tip_L'] = p
    return P


# --------------------------------------------------------------------------------------------- the rest chain
def rest_chain(spec):
    """the bind's points in life mm (module docstring): dict(pos={name: (3,)}, legs={leg: solve_leg's dict},
    cheliped=solve_cheliped's dict, claws={'crusher', 'cutter': claw()'s dicts, both built on the LEFT}, lv=levels(),
    scale_m (metres per life mm at the author scale))"""
    lv = levels(spec, spec['rig']['lift'])
    P = {'root': np.array([0.0, 0.0, lv['body'][2]]), 'body': lv['body'], 'rostrum_tip': lv['rostrum']}
    P.update(abdomen_points(spec, lv))
    P.update(head_points(spec, lv))
    legs = {}
    for leg in WALK:
        s = solve_leg(spec, leg, lv)
        legs[leg] = s
        g, lo = s['pts'], leg.lower()
        for seg, key in zip(SEGS, ('M', 'B', 'I', 'K', 'P', 'D')):
            P[f'{lo}_{seg}_L'] = g[key]
        P[f'{lo}_tip_L'] = g['T']
    ch = solve_cheliped(spec, lv)
    g = ch['pts']
    for seg, key in zip(SEGS[:3], ('M', 'B', 'I')):
        P[f'cheliped_{seg}_L'] = g[key]
    P['cheliped_carpus_L'] = g['K']
    P['cheliped_propodus_L'] = ch['W']
    claws = {kind: claw(spec, ch['W'], ch['d'], kind) for kind in ('crusher', 'cutter')}
    cr = claws['crusher']
    P['cheliped_dactyl_L'], P['cheliped_tip_L'], P['cheliped_dactyl_tip_L'] = cr['H'], cr['tip'], cr['dactyl_tip']
    for k in [k for k in P if k.endswith('_L')]:
        P[k[:-2] + '_R'] = mirror_point(P[k])
    cu = claws['cutter']                               # the right claw is the cutter's own (sided by type)
    P['cheliped_dactyl_R'], P['cheliped_tip_R'], P['cheliped_dactyl_tip_R'] = (mirror_point(cu['H']),
                                                                               mirror_point(cu['tip']),
                                                                               mirror_point(cu['dactyl_tip']))
    return dict(pos=P, legs=legs, cheliped=ch, claws=claws, lv=lv, scale_m=spec['author_scale'] * 1e-3)


# --------------------------------------------------------------------------------------------- the skeleton
def skeleton(spec, chain, scale=None):
    """§10.1's 167 joints as rig.Skeleton in metres at the author scale (module docstring); sk.meta holds each joint's
    role, tier, side, fold, tip (metres), driver, parent and claw"""
    s = chain['scale_m'] if scale is None else scale
    P, legs, ch, claws = chain['pos'], chain['legs'], chain['cheliped'], chain['claws']
    sk = RG.Skeleton()
    sk.meta = {}

    def add(name, parent, pos, x=None, fold=None, role='', tier=0, tip=None, driver=None, frame=None, kind=None):
        if frame is None:
            frame = RG.frame_from(x, fold)
        sk.add(name, parent, np.asarray(pos, np.float64) * s, frame)
        side = 'L' if name.endswith('_L') else ('R' if name.endswith('_R') else '')
        sk.meta[name] = dict(role=role, tier=tier, side=side, parent=parent, driver=driver, claw=kind,
                             fold=None if fold is None else np.asarray(fold, np.float64),
                             tip=None if tip is None else np.asarray(tip, np.float64) * s)

    def frame(name):
        return sk.world[sk.index(name)][:3, :3]

    sw = lambda n: n[:-2] + '_R' if (n and n.endswith('_L')) else n          # noqa: E731

    def mirror(names):
        for n in names:
            m = sk.meta[n]
            W = sk.world[sk.index(n)]
            add(sw(n), sw(m['parent']), mirror_point(W[:3, 3]) / s, role=m['role'], tier=m['tier'],
                driver=sw(m['driver']), fold=None if m['fold'] is None else mirror_point(m['fold']),
                tip=None if m['tip'] is None else mirror_point(m['tip']) / s, frame=mirror_frame(W[:3, :3]),
                kind=m['claw'])

    def mirrored_add(name_R, parent_R, pos_L, x, fold, role, tier, tip_L, kind):
        """a right joint that is the reflection of a LEFT construction which is not in the skeleton (the cutter)"""
        F = RG.frame_from(x, fold)
        add(name_R, parent_R, mirror_point(pos_L), role=role, tier=tier, fold=mirror_point(fold),
            tip=mirror_point(tip_L), frame=mirror_frame(F), kind=kind)

    def toward(p, j, x):
        return perp(np.asarray(p, np.float64) - np.asarray(j, np.float64), _unit(x))

    def chain_add(names, parent, pts, tip, fold, role, tier):
        """a straight run of joints at pts (the last bone ends at tip), each folding toward fold (made perpendicular)"""
        for k, n in enumerate(names):
            nxt = pts[k + 1] if k + 1 < len(names) else tip
            x = nxt - pts[k]
            add(n, parent if k == 0 else names[k - 1], pts[k], x, perp(fold, _unit(x)), role, tier,
                tip=tip if k + 1 == len(names) else None)

    # ---- root, body, abdomen, telson
    add('root', None, P['root'], role='root', frame=np.eye(3))
    add('body', 'root', P['body'], P['rostrum_tip'] - P['body'], VENTRAL, 'body', tip=P['rostrum_tip'])
    abd = [f'abd_{k}' for k in range(1, 7)] + ['telson']
    for k, n in enumerate(abd):
        nxt = P[abd[k + 1]] if k + 1 < len(abd) else P['telson_tip']
        add(n, 'body' if k == 0 else abd[k - 1], P[n], nxt - P[n], VENTRAL, 'telson' if n == 'telson' else 'abdomen',
            tip=P['telson_tip'] if n == 'telson' else None)
    # ---- uropods (on abd_6: they articulate on T6's posterolateral corners) and pleopods
    add('uropod_L', 'abd_6', P['uropod_L'], P['uropod_end_L'] - P['uropod_L'], VENTRAL, 'uropod', 1)
    x = P['uropod_endo_tip_L'] - P['uropod_endo_L']
    add('uropod_endo_L', 'uropod_L', P['uropod_endo_L'], x, perp(MEDIAL, _unit(x)), 'uropod', 1,
        tip=P['uropod_endo_tip_L'])
    x = P['uropod_exo_dist_L'] - P['uropod_exo_L']
    add('uropod_exo_L', 'uropod_L', P['uropod_exo_L'], x, perp(MEDIAL, _unit(x)), 'uropod', 1)
    x = P['uropod_exo_tip_L'] - P['uropod_exo_dist_L']
    add('uropod_exo_dist_L', 'uropod_exo_L', P['uropod_exo_dist_L'], x, perp(VENTRAL, _unit(x)), 'uropod', 1,
        tip=P['uropod_exo_tip_L'])
    mirror(['uropod_L', 'uropod_endo_L', 'uropod_exo_L', 'uropod_exo_dist_L'])
    ple = []
    for k in range(1, 6):
        x = P[f'pleopod_{k}_tip_L'] - P[f'pleopod_{k}_L']
        add(f'pleopod_{k}_L', f'abd_{k}', P[f'pleopod_{k}_L'], x, perp(CAUDAL, _unit(x)), 'pleopod', 1,
            tip=P[f'pleopod_{k}_tip_L'])
        ple.append(f'pleopod_{k}_L')
    mirror(ple)
    # ---- the head: eyestalks, antennae, antennules, third maxillipeds
    x = P['eyestalk_1_L'] - P['eyestalk_0_L']
    add('eyestalk_0_L', 'body', P['eyestalk_0_L'], x, perp(MEDIAL, _unit(x)), 'eyestalk', 2)
    x = P['cornea_L'] - P['eyestalk_1_L']
    add('eyestalk_1_L', 'eyestalk_0_L', P['eyestalk_1_L'], x, perp(DORSAL, _unit(x)), 'eyestalk', 2, tip=P['cornea_L'])
    mirror(['eyestalk_0_L', 'eyestalk_1_L'])
    nf = spec['rig']['antenna']['n_flag']
    ant = ['antenna_0_L', 'antenna_1_L', 'antenna_2_L']
    flg = [f'flagellum_{k:02d}_L' for k in range(nf)]
    x = P['antenna_1_L'] - P['antenna_0_L']
    add('antenna_0_L', 'body', P['antenna_0_L'], x, perp(CAUDAL, _unit(x)), 'antenna', 1)
    for k in (1, 2):
        nxt = P[f'antenna_{k + 1}_L'] if k < 2 else P['flagellum_00_L']
        x = nxt - P[f'antenna_{k}_L']
        add(f'antenna_{k}_L', f'antenna_{k - 1}_L', P[f'antenna_{k}_L'], x, perp(VENTRAL, _unit(x)), 'antenna', 1)
    chain_add(flg, 'antenna_2_L', [P[n] for n in flg], P['antenna_tip_L'], CAUDAL, 'flagellum', 1)
    mirror(ant + flg)
    nn = spec['rig']['antennule']['n_flag']
    anl = ['antennule_0_L', 'antennule_1_L', 'antennule_2_L']
    for k, n in enumerate(anl):
        nxt = P[anl[k + 1]] if k < 2 else P['antennule_lat_0_L']
        x = nxt - P[n]
        add(n, 'body' if k == 0 else anl[k - 1], P[n], x, perp(VENTRAL, _unit(x)), 'antennule', 2)
    for fl in ('lat', 'med'):
        names = [f'antennule_{fl}_{k}_L' for k in range(nn)]
        chain_add(names, 'antennule_2_L', [P[n] for n in names], P[f'antennule_{fl}_tip_L'], VENTRAL, 'antennule', 2)
        anl += names
    mirror(anl)
    mx = ['mxp3_0_L', 'mxp3_1_L', 'mxp3_2_L']
    for k, n in enumerate(mx):
        nxt = P[mx[k + 1]] if k < 2 else P['mxp3_tip_L']
        x = nxt - P[n]
        add(n, 'body' if k == 0 else mx[k - 1], P[n], x, perp(VENTRAL if k == 0 else MEDIAL, _unit(x)), 'mxp', 2,
            tip=P['mxp3_tip_L'] if k == 2 else None)
    mirror(mx)
    # ---- the chelipeds: the proximal chain mirrored, the claws sided by type
    g = ch['pts']
    cl = ['cheliped_coxa_L', 'cheliped_basis_L', 'cheliped_merus_L', 'cheliped_carpus_L']
    add(cl[0], 'body', g['M'], g['B'] - g['M'], perp(CAUDAL, g['h']), 'coxa')
    add(cl[1], cl[0], g['B'], g['um'], perp(DORSAL, g['um']), 'basis')
    add(cl[2], cl[1], g['I'], g['um'], perp(CAUDAL, g['um']), 'merus')
    xc = ch['W'] - g['K']
    add(cl[3], cl[2], g['K'], xc, toward(g['I'], g['K'], xc), 'carpus')
    mirror(cl)
    cr, cu, d = claws['crusher'], claws['cutter'], ch['d']
    fold_w = perp(MEDIAL, d)
    add('cheliped_propodus_L', 'cheliped_carpus_L', ch['W'], d, fold_w, 'propodus', tip=cr['tip'], kind='crusher')
    add('cheliped_dactyl_L', 'cheliped_propodus_L', cr['H'], cr['u'], perp(cr['n'], cr['u']), 'dactyl',
        tip=cr['dactyl_tip'], kind='crusher')
    mirrored_add('cheliped_propodus_R', 'cheliped_carpus_R', ch['W'], d, fold_w, 'propodus', 0, cu['tip'], 'cutter')
    mirrored_add('cheliped_dactyl_R', 'cheliped_propodus_R', cu['H'], cu['u'], perp(cu['n'], cu['u']), 'dactyl', 0,
                 cu['dactyl_tip'], 'cutter')
    # ---- the walking legs
    for leg in WALK:
        sl, lo = legs[leg], leg.lower()
        g = sl['pts']
        names = [f'{lo}_{seg}_L' for seg in SEGS]
        add(names[0], 'body', g['M'], g['h'], perp(CAUDAL, g['h']), 'coxa')
        add(names[1], names[0], g['B'], g['um'], perp(DORSAL, g['um']), 'basis')
        add(names[2], names[1], g['I'], g['um'], perp(CAUDAL, g['um']), 'merus')
        add(names[3], names[2], g['K'], g['uc'], toward(g['I'], g['K'], g['uc']), 'carpus')
        add(names[4], names[3], g['P'], g['up'], np.cross(g['a_cp'], g['up']), 'propodus')
        flex = np.cross(g['a_pd'], g['ud'])
        add(names[5], names[4], g['D'], g['ud'], flex if leg in ('P4', 'P5') else -flex, 'dactyl', 1, tip=g['T'])
        mirror(names)
    # ---- IK targets (AG 05.19): leaves of the root on the carpus's distal joint with the carpus's frame (the merus
    # and carpus solve a two-bone IK to it; the propodus and dactyl are laid to the ground from it, plan §10.4)
    iks = [(f'ik_foot_{leg.lower()}_L', P[f'{leg.lower()}_propodus_L'], f'{leg.lower()}_carpus_L') for leg in WALK]
    iks.append(('ik_claw_L', P['cheliped_propodus_L'], 'cheliped_carpus_L'))
    for n, p, drv in iks:
        add(n, 'root', p, role='ik', tier=1, driver=drv, frame=frame(drv))
    mirror([n for n, _, _ in iks])
    return sk


# --------------------------------------------------------------------------------------------- posing and the rest pose
def posed(sk, local_rot=None, local_shift=None):
    """world matrices for local rotations {joint index: 3x3} applied in each joint's bind local frame (as
    rig.Skeleton.posed_world) and local translations {joint index: (3,) metres} added to a joint's local offset in its
    parent's frame (the body's descent, the IK targets)"""
    out = [None] * len(sk.names)
    for i in range(len(sk.names)):
        L = sk.local(i).copy()
        if local_rot and i in local_rot:
            L[:3, :3] = L[:3, :3] @ local_rot[i]
        if local_shift and i in local_shift:
            L[:3, 3] = L[:3, 3] + np.asarray(local_shift[i], np.float64)
        p = sk.parent[i]
        out[i] = L if p < 0 else out[p] @ L
    return out


def tip_world(sk, W, name):
    """a leaf joint's tip under the world matrices W"""
    i = sk.index(name)
    local = np.linalg.inv(sk.world[i]) @ np.append(sk.meta[name]['tip'], 1.0)
    return (W[i] @ local)[:3]


FAN_TIPS = ('telson', 'uropod_endo_L', 'uropod_exo_dist_L', 'uropod_endo_R', 'uropod_exo_dist_R')
UROPOD_TIPS = FAN_TIPS[1:]
CURL_FRONT, CURL_BACK = ('abd_2', 'abd_3', 'abd_4'), ('abd_5', 'abd_6', 'telson')


def rest_pose(spec, sk, chain, shells=None):
    """c06's crouch as a pose of the bound skeleton (module docstring). Returns dict(rot, shift, W (posed world),
    legs={leg: rest_leg's dict}, abd=(the front curl of abd_2..4, the back curl of abd_5..telson, the uropods' ventral
    fold), claw_lift (the cheliped levation's change), lv).

    shells (X2b): the clay, as [(joint name, (n, 3) points in METRES at the bind)] (a shell's convex hull suffices: a
    rigid body's lowest point is a hull vertex). When given, the rest rests the SHELLS' lowest points on the sand: the
    abdomen's (its tergites, sternites, pleopods, telson and uropods) instead of its joints and fan tips, and the
    chelae's (both propodi and dactyli, posed) instead of the bind's palm low point carried rigidly (X2's rest sank the
    telson 1.87 mm and the crusher's palm 0.74 mm: the X2 check). Without them (x01: no clay) the skeleton's points."""
    s = chain['scale_m']
    rg, idx = spec['rig'], {n: i for i, n in enumerate(sk.names)}
    TAIL_SET = set(CURL_FRONT + CURL_BACK + ('abd_1',)) | {n for n in sk.names if n.startswith(('uropod', 'pleopod'))}
    sh_tail = [(idx[j], P) for j, P in (shells or []) if j in TAIL_SET]
    sh_claw = [(idx[j], P) for j, P in (shells or []) if j.startswith(('cheliped_propodus', 'cheliped_dactyl'))]

    def low_pt(Wm, group):                  # the lowest posed point of the shells in group: (its joint, the point, mm)
        best = (None, None, np.inf)
        for j, P in group:
            Tm = Wm[j] @ np.linalg.inv(sk.world[j])
            y = P @ Tm[1, :3] + Tm[1, 3]
            k = int(np.argmin(y))
            if y[k] < best[2]:
                best = (sk.names[j], (Tm[:3, :3] @ P[k] + Tm[:3, 3]) / s, float(y[k]))
        return best[0], best[1]
    lv0 = levels(spec, 0.0)
    rot, shift = {}, {idx['body']: np.array([0.0, -rg['lift'] * s, 0.0])}
    legs = {}
    for leg in WALK:
        b = chain['legs'][leg]
        r = rest_leg(spec, leg, lv0)
        legs[leg] = r
        lo = leg.lower()
        for side in ('L', 'R'):
            rot[idx[f'{lo}_coxa_{side}']] = rz(r['theta'] - b['theta'])
            rot[idx[f'{lo}_basis_{side}']] = rz(r['e'] - b['e'])
            rot[idx[f'{lo}_carpus_{side}']] = rz(b['alpha'] - r['alpha'])
            rot[idx[f'{lo}_propodus_{side}']] = rz(r['delta'] - b['delta'])
            rot[idx[f'{lo}_dactyl_{side}']] = rz(r['phi'] - b['phi'])
    for k in range(2, 6):                                        # pleopods 2-5 folded along the sternites
        for side in ('L', 'R'):
            rot[idx[f'pleopod_{k}_{side}']] = rz(rg['rest_pleopod_fold'])

    def with_abd(cf, cb, u=0.0):     # abd_1 stays straight (c06: T1 level with the carapace)
        out = dict(rot)
        for names, v in ((CURL_FRONT, cf), (CURL_BACK, cb)):
            for n in names:
                out[idx[n]] = rz(v)
        for side in ('L', 'R'):
            out[idx[f'uropod_{side}']] = rz(u)
        return out

    cb = rg['rest_curl_back']                                    # the fan turned down (c06), the back at its limit
    tail = [f'abd_{k}' for k in range(2, 7)] + ['telson']

    def lowest(cf, u=0.0):              # the abdomen's lowest point: its shells' (X2b), else a fan tip or a joint
        Wa = posed(sk, with_abd(cf, cb, u), shift)
        if sh_tail:
            n, p = low_pt(Wa, sh_tail)
            return f'{n} shell', p
        pts = {f'{n} tip': tip_world(sk, Wa, n) / s for n in FAN_TIPS}
        pts.update({f'{n} joint': Wa[idx[n]][:3, 3] / s for n in tail})
        n = min(pts, key=lambda k: pts[k][1])
        return n, pts[n]
    cf = brentq(lambda a: lowest(a)[1][1], rg['ranges']['abdomen'][0], rg['ranges']['abdomen'][1], xtol=1e-12)

    def uro_low(u):
        Wu = posed(sk, with_abd(cf, cb, u), shift)
        if sh_tail:
            return low_pt(Wu, [(j, P) for j, P in sh_tail if sk.names[j].startswith('uropod')])[1][1]
        return min(tip_world(sk, Wu, n)[1] / s for n in UROPOD_TIPS)
    u = 0.0 if uro_low(0.0) >= -1e-9 else brentq(uro_low, 0.0, rg['ranges']['uropod'][1], xtol=1e-12)
    rot = with_abd(cf, cb, u)
    contact = lowest(cf, u)

    # the crusher rests on the sand by its LOWEST point (X2: the palm's lateral margin, rig.cheliped.low_point, carried
    # by the propodus's joint; X1 rested the fixed tip, which on the claw's real shape put the palm under the sand;
    # X2b with the clay: the chelae's shells' lowest point at the rest itself)
    i_cp = idx['cheliped_propodus_L']
    low_local = np.linalg.inv(sk.world[i_cp]) @ np.append(claw_low_point(spec, chain) * s, 1.0)

    def claw_r(dl):
        r2 = dict(rot)
        for side in ('L', 'R'):
            r2[idx[f'cheliped_basis_{side}']] = rz(dl)
        return r2

    def claw_y(dl):
        Wc = posed(sk, claw_r(dl), shift)
        if sh_claw:
            return low_pt(Wc, sh_claw)[1][1]
        return float((Wc[i_cp] @ low_local)[1]) / s
    dl = brentq(claw_y, -10.0, 60.0, xtol=1e-12)
    for side in ('L', 'R'):
        rot[idx[f'cheliped_basis_{side}']] = rz(dl)
    W = posed(sk, rot, shift)
    claw_low = low_pt(W, sh_claw)[1] if sh_claw else (W[i_cp] @ low_local)[:3] / s
    for n in [n for n in sk.names if sk.meta[n]['role'] == 'ik']:      # the IK targets follow their drivers
        i, drv = idx[n], sk.meta[n]['driver']
        j = idx[drv]
        child = [c for c in sk.names if sk.meta[c]['parent'] == drv and sk.meta[c]['role'] != 'ik'][0]
        shift[i] = W[idx[child]][:3, 3] - sk.world[i][:3, 3]
        rot[i] = sk.world[i][:3, :3].T @ W[j][:3, :3]
    W = posed(sk, rot, shift)
    return dict(rot=rot, shift=shift, W=W, legs=legs, abd=(float(cf), float(cb), float(u)), contact=contact,
                claw_lift=float(dl), claw_low=claw_low, lv=lv0)


def claw_low_point(spec, chain):
    """the crusher propodus's lowest point at the bind, life mm (rig.cheliped.low_point in its claw frame: s along the
    axis from the wrist, m toward the dactyl, and (A0: the flat plane, where the lowest point lies on the ventral FACE)
    a third value along the thickness d x n; without that row, the fixed tip)"""
    ch, cr = chain['cheliped'], chain['claws']['crusher']
    lp = spec['rig']['cheliped'].get('low_point')
    if lp is None:
        return np.asarray(cr['tip'], np.float64)
    p = ch['W'] + lp[0] * ch['d'] + lp[1] * cr['n']
    return p + lp[2] * np.cross(ch['d'], cr['n']) if len(lp) > 2 else p


# --------------------------------------------------------------------------------------------- the bind's angles
def bind_angles(spec, chain):
    """every articulated joint class's bind angle against its plan §10.3 range (the lead's 'joints near mid-range'):
    a list of dict(joint, value, range, how); the LEFT side (the right mirrors it)"""
    rg = spec['rig']
    rw, rc, R = rg['ranges']['walking'], rg['ranges']['cheliped'], rg['ranges']
    out = []
    for leg in WALK:
        sl = chain['legs'][leg]
        lo = leg.lower()
        out += [dict(joint=f'{lo}_coxa', value=90.0 - sl['theta'], range=rw['promotion'],
                     how='promotion (+ forward) from n01\'s lateral coxa'),
                dict(joint=f'{lo}_basis', value=sl['e'], range=rw['levation'], how='levation from the level coxa'),
                dict(joint=f'{lo}_merus', value=0.0, range=rw['ischium_merus'], how='straight (the bind\'s zero)'),
                dict(joint=f'{lo}_carpus', value=sl['alpha'], range=rw['knee'], how='the knee\'s included angle'),
                dict(joint=f'{lo}_propodus', value=sl['delta'], range=rw['carpus_propodus'],
                     how='the deflection (+ back) from the carpus\'s line'),
                dict(joint=f'{lo}_dactyl', value=sl['phi'], range=rw['dactyl'],
                     how='flexion from straight' if leg in ('P4', 'P5') else 'the small chela closed (opening 0)')]
    ch = chain['cheliped']
    out += [dict(joint='cheliped_coxa', value=90.0 - ch['theta'], range=rc['promotion'],
                 how='promotion (+ forward) from n01\'s lateral coxa'),
            dict(joint='cheliped_basis', value=ch['e'], range=rc['levation'], how='levation from the level coxa'),
            dict(joint='cheliped_merus', value=0.0, range=rw['ischium_merus'], how='straight (the bind\'s zero)'),
            dict(joint='cheliped_carpus', value=ch['alpha'], range=rc['knee'], how='the knee\'s included angle'),
            dict(joint='cheliped_propodus', value=ch['omega'], range=rc['wrist'],
                 how='the wrist (+ adduction) from the carpus\'s line'),
            dict(joint='cheliped_dactyl (crusher)', value=rg['cheliped']['dactyl_open'], range=rc['crusher'],
                 how='open'),
            dict(joint='cheliped_dactyl (cutter)', value=rg['cheliped']['dactyl_open'], range=rc['cutter'],
                 how='open'),
            dict(joint='abd_1..6, telson', value=0.0, range=R['abdomen'], how='straight (question 1b, option (a))'),
            dict(joint='uropods', value=R['uropod'][1], range=R['uropod'],
                 how='spread to the fan\'s 1.00 CL: the range\'s spread end by its definition'),
            dict(joint='eyestalk_0 (yaw)', value=0.0, range=R['eyestalk_yaw'], how='the bind\'s zero'),
            dict(joint='eyestalk_1 (pitch)', value=0.0, range=R['eyestalk_pitch'], how='the bind\'s zero'),
            dict(joint='antenna_0 (yaw)', value=90.0 - rg['antenna']['yaw'], range=R['antenna_yaw'],
                 how='yaw forward of lateral'),
            dict(joint='antenna_0 (pitch)', value=rg['antenna']['pitch'], range=R['antenna_pitch'], how='pitch'),
            dict(joint='flagellum_00..15', value=0.0, range=R['flagellum'], how='straight')]
    return out
