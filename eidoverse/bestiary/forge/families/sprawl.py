"""SPRAWL family generator: the sprawling tetrapod salamander, the axolotl first (work/bestiary/research/AXOLOTL_PLAN.md
§4, §5.2). The recipe family stays `limbed` with the body plan `sprawl`; limbed.py's sagittal solve is the wolf's and
does not apply, but its frame and mirror rules do, and are imported, not copied.

AX1 (10-28): the rest chain and the 124-joint skeleton (plan §4.1, §4.3). AX2 (10-28): the clay (clay_*; the body is
heads/caudate.py's subdivision surface, its GRID unioned with the limbs, the gill rami, the eyes and the fins here; the
section at the end of this module). The cage's body loft, ports and limbs (AX4) come later in this module.

rest_chain(spec) solves the bind pose from species/axolotl.py's SPEC (life mm, TL fractions s from the snout tip) and
returns metres at x spec['author_scale'] (plan §5.3: the axolotl is built at x4):
  - THE FRAME (DESIGN.md): +Z forward, +Y up, +X the creature's left; the root on the ground under the hips, so a
    station s sits at z = (s_hip - s) TL.
  - THE BODY: the belly line level at rest.belly under the trunk, the throat and the vent; the vertebral column at
    rig.spine_frac of the local core depth above it (core_depth: plan §2.2's trunk core, then AX0b's tail core), the
    atlanto-occipital joint at rig.head_frac of its section, the column straight between the AO and the shoulder
    joint (neck_0 lies on it). The head is LEVEL (plan §4.3, the palate horizontal): the head joint's x runs
    horizontally to the snout tip. Behind the vent the column falls straight to rest.tail_tip_h at the tail tip (the
    tail trailing low, v01).
  - THE HEAD'S FEATURES at p13's frontal fractions of the frontal box (head.height_mm standing on the belly line): the
    mouth line (the jaw hinge's height, rig.jaw_frac), the eyes (at AX0b's station eye_c_x0b, head.eyes_apart_mm
    apart, looking out, up and a little forward), the gill bases on plan §2.1's line (s gill_base) at p13's emergence
    heights, rig.gill_base_inset of p13's emergence offsets out (the true bases hidden behind the outline, §2.5).
    Each ramus runs straight along its design unit vector (gills.u_r*: a flared design pose; the bind is a design
    pose, §2.5; a gills.u_r*_x2b row, when present, in its place: AX2b's r3 raised 3 deg off the arm) for its chord x
    gills.gill_scale, four joints at equal steps.
  - THE FORELIMB: the glenoid rig.shoulder_x out and rig.glenoid_frac up its section at s shoulder_joint; the forearm
    VERTICAL with the wrist joint rest.wrist_h above the floor (AX10: limb_rest's rows, the forearm leaning forward and
    the wrist lifted; likewise the shank and the heel), so the humerus's elevation is solved exactly; its
    retraction is solved (brentq) so the two palm centres stand rest.hands_apart_target_HW x HW apart. The hand lies
    flat, pointing forward and rest.hand_out out: the carpus (rig.carpus_len, AX0b) down to the carpometacarpal joint
    at rig.palm_h, the metacarpal (rig.metacarpal) to the digit bases spread across rig.palm_w, four fingers splayed
    by rig.digit_splay, each finger limbs.finger_rel x the longest (limbs.hand_x0b - carpus - metacarpal), every
    finger joint and tip at the finger's skin radius (limbs.radii.digit) above the floor.
  - THE HINDLIMB: the hip rig.hip_x out and rig.acetabulum_frac up its section at s hip; the femur rest.femur_fwd
    forward of lateral, its elevation solved so the shank stands vertical with the ankle at rest.ankle_h; the foot flat,
    rest.foot_out out: the tarsus (limbs.tarsus) to the tarsometatarsal joint at rig.sole_h, the metatarsal
    (rig.metatarsal, AX0b), five toes (limbs.toe_rel x limbs.mt_digit - metatarsal) splayed by rig.toe_splay.
  - THE TAIL: twelve joints from the vent at equal steps to s tail_to, the tip at s 1.

skeleton(spec, chain) builds rig.Skeleton with the plan's 124 joints, parents before children; twist joints, helpers,
breathers and IK targets are leaves (AG 05.11). Frames (rig.frame_from): x along the bone to its child or leaf tip, y the
side it folds toward, z = x cross y, so a positive rotation about z folds the joint the anatomical way (AG 05.7):
  spine, neck, head and tail ventral; the jaw opens; the throat's floor drops; the tongue curls down; the eyes look up;
  each gill joint folds its ramus BACK (laid back along the head: p01's posture); the scapula retracts and the humerus
  retracts (the elbow back), the femur protracts (the knee forward): limbed.py's girdle conventions; the elbow and the
  knee FLEX (the hand or the foot toward the parent bone, so a positive bend closes the included angle); the wrist,
  the ankle and every digit flex palmar / plantar (down).
The right side is the left reflected under limbed.py's rule (AG 05.8): p_R = M p_L, F_R = M F_L diag(1, 1, -1),
M = diag(-1, 1, 1). sk.meta[name]: role, tier (0 body, 1 digits / twists / helpers / gills, 2 face), side, fold, tip,
driver, parent.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from .. import rig as RG
from .limbed import CAUDAL, CRANIAL, DORSAL, VENTRAL, mirror_frame, mirror_point

Y_AX = np.array([0.0, 1.0, 0.0])


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def _interp(table, s):
    """a (s, value) table at s: linear inside, its end values outside"""
    if s <= table[0][0]:
        return float(table[0][1])
    for (a, va), (b, vb) in zip(table, table[1:]):
        if a <= s <= b:
            return float(va + (vb - va) * (s - a) / (b - a))
    return float(table[-1][1])


def core_depth(spec, s):
    """the body core's depth (TL fraction) at station s: the trunk core table (plan §2.2) to its last station, then the
    tail core readings (AX0b, profile.tail_core_TL_x0b) to 0 at s = 1, linear (species/axolotl.core_depth's rule)"""
    p = spec['profile']
    if s <= p['core'][-1][0]:
        return _interp(p['core'], s)
    return _interp(((p['core'][-1][0], p['core'][-1][1]),) + tuple(p['tail_core_TL_x0b']) + ((1.0, 0.0),), s)


def tail_total(spec, s):
    """the tail's depth with both fins (TL fraction, plan §2.2) at station s"""
    return _interp(spec['profile']['tail_total'], s)


def section(spec):
    """the body's side-view rules in LIFE mm: z(s), the core depth D(s), the column's height col(s), the belly line"""
    a1, st, rg, rs = spec['a1'], spec['stations'], spec['rig'], spec['rest']
    TL = a1['TL']
    s_hip, s_sh, s_ao, s_vent = st['hip'], st['shoulder_joint'], st['head_joint'], st['vent']
    belly = rs['belly']
    z = lambda s: (s_hip - s) * TL                                        # noqa: E731
    D = lambda s: core_depth(spec, s) * TL                                # noqa: E731
    trunk = lambda s: belly + rg['spine_frac'] * D(s)                     # noqa: E731
    y_ao = belly + rg['head_frac'] * D(s_ao)
    y_vent = trunk(s_vent)

    def col(s):
        if s <= s_ao:
            return y_ao                                                   # the level head
        if s <= s_sh:
            return y_ao + (trunk(s_sh) - y_ao) * (s - s_ao) / (s_sh - s_ao)
        if s <= s_vent:
            return trunk(s)
        return y_vent + (rs['tail_tip_h'] - y_vent) * (s - s_vent) / (1.0 - s_vent)
    return dict(TL=TL, z=z, D=D, col=col, belly=belly, y_ao=y_ao, y_vent=y_vent)


def _limb_point(origin, length, fwd, elev):
    """origin + length along the LEFT side's direction at azimuth fwd (degrees forward of lateral, + forward) and
    elevation elev (degrees, + up); lateral is +X"""
    a, e = np.radians(fwd), np.radians(elev)
    return np.asarray(origin, float) + length * np.array([np.cos(e) * np.cos(a), np.sin(e), np.cos(e) * np.sin(a)])


def _flat_run(start, length, direction, y_end):
    """a bone of `length` from `start` heading along the horizontal `direction`, ending at height y_end"""
    dy = y_end - start[1]
    h = np.sqrt(length ** 2 - dy ** 2)
    return np.asarray(start, float) + h * np.asarray(direction, float) + np.array([0.0, dy, 0.0])


def _autopod(base, heading_deg, lens, heights, n_digits, width, splay, digit_lens, digit_r, digit_mid, pre):
    """a flat hand or foot from its wrist / ankle joint `base`: the carpus / tarsus and the metapodial along the heading
    (degrees from forward toward lateral), dropping to heights[0] and heights[1]; the digit bases spread across `width`
    (medial digit 1 first), each digit splayed and lying at digit_r above the floor. Returns the points (life mm)"""
    a = np.radians(heading_deg)
    h = np.array([np.sin(a), 0.0, np.cos(a)])                             # forward-out
    lat = np.array([np.cos(a), 0.0, -np.sin(a)])                          # the hand's lateral direction (+X side)
    P = {}
    P[f'{pre}_proxrow'] = _flat_run(base, lens[0], h, heights[0])         # the carpometacarpal / tarsometatarsal joint
    P[f'{pre}_head'] = _flat_run(P[f'{pre}_proxrow'], lens[1], h, heights[1])   # the digit bases' centre
    ts = np.linspace(-1.0, 1.0, n_digits)
    for n in range(n_digits):
        th = np.radians(splay[n])
        d = h * np.cos(th) + lat * np.sin(th)
        d0 = P[f'{pre}_head'] + ts[n] * 0.5 * width * lat
        d0[1] = digit_r
        P[f'{pre}_digit{n + 1}_0'] = d0
        P[f'{pre}_digit{n + 1}_1'] = d0 + digit_mid * digit_lens[n] * d
        P[f'{pre}_digit{n + 1}_tip'] = d0 + digit_lens[n] * d
    return P


def limb_rest(spec):
    """the bind's wrist and ankle (life mm, degrees): SPEC ax10's rows (wrist_h, ankle_h, forearm_tilt, shank_tilt) when
    present, else the plan's (rest.wrist_h, rest.ankle_h, the forearm and the shank vertical). AX10, 11-01 (the AX7c
    look's 'right-angle L': the vertical forearm / shank met the flat carpus / tarsus at ~90 deg): the rows lift the heel
    and the wrist and lean the forearm and the shank forward going down. Tried on the axolotl's bind (ankle 3 mm, shank
    15 / 8 deg): AX4's knee wedge then lay across its V crease (gate 2: 2 folds, 10 / 6 tilts), so the axolotl's SPEC
    carries none and its rig lifts the heels in the poses instead (species/axolotl_rig.STAND)"""
    rs = spec['rest']
    a10 = spec.get('ax10') or {}
    return dict(wrist_h=float(a10.get('wrist_h', rs['wrist_h'])), ankle_h=float(a10.get('ankle_h', rs['ankle_h'])),
                forearm_tilt=float(a10.get('forearm_tilt', 0.0)), shank_tilt=float(a10.get('shank_tilt', 0.0)))


def rest_chain(spec):
    """the bind (module docstring). Returns dict(pos={name: (3,) metres at x author_scale}, mm={name: life mm},
    k (metres per life mm), sec (section(spec)), and the solved values: humerus_back, humerus_elev, femur_elev,
    finger, toe, palms_apart_mm"""
    a1, st, rg, rs, hd, gl, lb = (spec['a1'], spec['stations'], spec['rig'], spec['rest'], spec['head'],
                                  spec['gills'], spec['limbs'])
    TL, HW = a1['TL'], a1['HW']
    sec = section(spec)
    z, D, col, belly = sec['z'], sec['D'], sec['col'], sec['belly']
    P = {}
    # ---- the column: pelvis, spine_0..6 (the hips -> the shoulders), neck_0, the head joint and the snout tip
    s_hip, s_sh = st['hip'], st['shoulder_joint']
    P['pelvis'] = np.array([0.0, col(s_hip), z(s_hip)])
    n_sp = rg['n_spine']
    s_spine = [s_hip - (k + 1) * (s_hip - s_sh) / n_sp for k in range(n_sp)]
    for k, s in enumerate(s_spine):
        P[f'spine_{k}'] = np.array([0.0, col(s), z(s)])
    P['neck_0'] = np.array([0.0, col(st['neck']), z(st['neck'])])
    P['head'] = np.array([0.0, sec['y_ao'], z(st['head_joint'])])
    P['snout_tip'] = np.array([0.0, sec['y_ao'], z(0.0)])
    # ---- the head's features: the frontal box from the belly line up
    hh = hd['height_mm']
    y_mouth = belly + rg['jaw_frac'] * hh
    P['jaw'] = np.array([0.0, y_mouth, z(st['jaw_hinge'])])
    P['chin_tip'] = np.array([0.0, y_mouth - rg['chin_drop'], z(rg['chin_s'])])
    P['tongue'] = np.array([0.0, y_mouth - rg['tongue_drop'], z(rg['tongue_s'][0])])
    P['tongue_tip'] = np.array([0.0, y_mouth - rg['tongue_drop'], z(rg['tongue_s'][1])])
    y_thr = belly + rg['throat_frac'] * D(st['throat'])
    P['throat'] = np.array([0.0, y_thr, z(st['throat'])])
    P['throat_tip'] = np.array([0.0, y_thr, z(st['jaw_hinge'])])
    ex = np.array(rg['eye_axis'], float)
    eye_dir = _unit(ex)                                                   # (out, up, forward) = (+X, +Y, +Z) on the left
    P['eye_L'] = np.array([0.5 * hd['eyes_apart_mm'], belly + hh * (1.0 - hd['eye_frontal'][0]), z(st['eye_c_x0b'])])
    P['eye_tip_L'] = P['eye_L'] + rg['eye_r'] * eye_dir
    for r in (1, 2, 3):
        em = gl[f'emergence_r{r}']
        base = np.array([rg['gill_base_inset'] * HW * em[1], belly + hh * (1.0 - em[0]), z(st['gill_base'])])
        u = gl.get(f'u_r{r}_x2b', gl[f'u_r{r}'])      # AX2b's design row beside the plan's solve, else the plan's
        d = _unit([u[0], u[1], -u[2]])                                    # (out, up, back) -> (+X, +Y, -Z)
        L = gl['chord'][r - 1] * gl['gill_scale']
        n_g = rg['gill_joints']
        for j in range(n_g):
            P[f'gill_{r}_{j}_L'] = base + (j / n_g) * L * d
        P[f'gill_{r}_tip_L'] = base + L * d
    s_bc = 0.5 * (s_spine[5] + s_spine[6])
    s_bb = 0.5 * (s_spine[2] + s_spine[3])
    P['breath_chest'] = np.array([0.0, belly + rg['breath_chest'] * D(s_bc), z(s_bc)])
    P['breath_belly'] = np.array([0.0, belly + rg['breath_belly'] * D(s_bb), z(s_bb)])
    # ---- the forelimb (left): the glenoid, the forearm vertical, the retraction solved for the palms' spread
    Lh, Lr = lb['humerus_x0b'], lb['forearm_x0b']
    finger = lb['hand_x0b'] - rg['carpus_len'] - rg['metacarpal']
    # the tarsus and the metatarsal + longest toe: AX2's rows at the settled hip's k06 when the SPEC has them (the
    # plan's [D-ap] rows are g06 x 0.922, the plan's hip)
    tarsus = lb.get('tarsus_x2', lb['tarsus'])
    toe = lb.get('mt_digit_x2', lb['mt_digit']) - rg['metatarsal']
    G = np.array([rg['shoulder_x'], belly + rg['glenoid_frac'] * D(s_sh), z(s_sh)])
    lr = limb_rest(spec)
    t_f = np.radians(lr['forearm_tilt'])
    y_elbow = lr['wrist_h'] + Lr * np.cos(t_f)
    h_elev = float(np.degrees(np.arcsin((y_elbow - G[1]) / Lh)))
    dr = lb['radii']['digit']

    def fore(back):
        E = _limb_point(G, Lh, -back, h_elev)
        # the forearm leaning limb_rest's forearm_tilt deg forward going down (0, VERTICAL, without AX10's rows)
        W = np.array([E[0], lr['wrist_h'], E[2] + Lr * np.sin(t_f)])
        Q = _autopod(W, rs['hand_out'], (rg['carpus_len'], rg['metacarpal']), (rg['palm_h'], dr), 4, rg['palm_w'],
                     rg['digit_splay'], [finger * f for f in lb['finger_rel']], dr, rg['digit_mid'], 'f')
        return E, W, Q

    def palm_gap(back):
        E, W, Q = fore(back)
        return 2.0 * 0.5 * (Q['f_proxrow'][0] + Q['f_head'][0]) - rs['hands_apart_target_HW'] * HW
    h_back = brentq(palm_gap, 0.0, 89.0, xtol=1e-12)
    E, W, Q = fore(h_back)
    P['scapula_top_L'] = G + np.array([-rg['scapula_x'], rg['scapula_rise'], 0.0])
    P['shoulder_L'], P['elbow_L'], P['wrist_L'] = G, E, W
    for kq, v in Q.items():
        P[kq + '_L'] = v
    # ---- the hindlimb (left): the hip, the shank vertical, the femur's elevation solved
    Lf, Lt = lb['femur_x0b'], lb['tibia_x0b']
    Hp = np.array([rg['hip_x'], belly + rg['acetabulum_frac'] * D(s_hip), z(s_hip)])
    t_s = np.radians(lr['shank_tilt'])
    f_elev = float(np.degrees(np.arcsin((lr['ankle_h'] + Lt * np.cos(t_s) - Hp[1]) / Lf)))
    K = _limb_point(Hp, Lf, rs['femur_fwd'], f_elev)
    A = np.array([K[0], lr['ankle_h'], K[2] + Lt * np.sin(t_s)])         # the shank leaning forward going down (AX10)
    Qh = _autopod(A, rs['foot_out'], (tarsus, rg['metatarsal']), (rg['sole_h'], dr), 5, rg['sole_w'],
                  rg['toe_splay'], [toe * f for f in lb['toe_rel']], dr, rg['digit_mid'], 'h')
    P['hip_L'], P['knee_L'], P['ankle_L'] = Hp, K, A
    for kq, v in Qh.items():
        P[kq + '_L'] = v
    # ---- the tail
    n_t = rg['n_tail']
    s_tail = [rg['tail_from'] + k * (rg['tail_to'] - rg['tail_from']) / (n_t - 1) for k in range(n_t)]
    for k, s in enumerate(s_tail):
        P[f'tail_{k}'] = np.array([0.0, col(s), z(s)])
    P['tail_tip'] = np.array([0.0, col(1.0), z(1.0)])
    for kq in [kq for kq in P if kq.endswith('_L')]:
        P[kq[:-2] + '_R'] = mirror_point(P[kq])
    k_m = spec['author_scale'] / 1000.0
    palms = 0.5 * (P['f_proxrow_L'] + P['f_head_L']) - 0.5 * (P['f_proxrow_R'] + P['f_head_R'])
    return dict(pos={kq: v * k_m for kq, v in P.items()}, mm=P, k=k_m, sec=sec, s_spine=s_spine, s_tail=s_tail,
                humerus_back=float(h_back), humerus_elev=h_elev, femur_elev=f_elev, finger=float(finger),
                toe=float(toe), palms_apart_mm=float(np.linalg.norm(palms)))


# --------------------------------------------------------------------------------------------- the skeleton
def skeleton(spec, chain):
    """the plan's 124 joints as rig.Skeleton (module docstring), then AX10b's eight volume helpers at the limbs' roots,
    wrists and ankles (SPEC rig helpers_x10b: 132); positions in metres at x author_scale"""
    P, rg = chain['pos'], spec['rig']
    k_m = chain['k']
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
        sw = lambda n: n[:-2] + '_R' if (n and n.endswith('_L')) else n      # noqa: E731
        for n in names:
            m = sk.meta[n]
            Wn = sk.world[sk.index(n)]
            add(sw(n), sw(m['parent']), mirror_point(Wn[:3, 3]), role=m['role'], tier=m['tier'], driver=sw(m['driver']),
                fold=None if m['fold'] is None else mirror_point(m['fold']),
                tip=None if m['tip'] is None else mirror_point(m['tip']), frame=mirror_frame(Wn[:3, :3]))

    # ---- root, pelvis, spine, neck, head and its leaves
    add('root', None, np.zeros(3), role='root', frame=np.eye(3))
    add('pelvis', 'root', P['pelvis'], P['spine_0'] - P['pelvis'], VENTRAL, 'spine')
    chain_sp = [f'spine_{k}' for k in range(rg['n_spine'])] + ['neck_0']
    prev = 'pelvis'
    for k, name in enumerate(chain_sp):
        nxt = chain_sp[k + 1] if k + 1 < len(chain_sp) else 'head'
        add(name, prev, P[name], P[nxt] - P[name], VENTRAL, 'spine')
        prev = name
    add('head', 'neck_0', P['head'], P['snout_tip'] - P['head'], VENTRAL, 'head', tip=P['snout_tip'])
    add('jaw', 'head', P['jaw'], P['chin_tip'] - P['jaw'], VENTRAL, 'jaw', tip=P['chin_tip'])
    add('tongue', 'jaw', P['tongue'], P['tongue_tip'] - P['tongue'], VENTRAL, 'tongue', 2, tip=P['tongue_tip'])
    add('eye_L', 'head', P['eye_L'], P['eye_tip_L'] - P['eye_L'], DORSAL, 'eye', 2, tip=P['eye_tip_L'])
    mirror(['eye_L'])
    add('throat', 'neck_0', P['throat'], P['throat_tip'] - P['throat'], VENTRAL, 'throat', tip=P['throat_tip'])
    gills = []
    for r in (1, 2, 3):
        n_g = rg['gill_joints']
        for j in range(n_g):
            nm = f'gill_{r}_{j}_L'
            nxt = P[f'gill_{r}_{j + 1}_L'] if j + 1 < n_g else P[f'gill_{r}_tip_L']
            add(nm, 'neck_0' if j == 0 else f'gill_{r}_{j - 1}_L', P[nm], nxt - P[nm], CAUDAL, 'gill', 1,
                tip=P[f'gill_{r}_tip_L'] if j + 1 == n_g else None)
            gills.append(nm)
    mirror(gills)
    add('breath_chest', 'spine_5', P['breath_chest'], VENTRAL, CRANIAL, 'breather', 1)
    add('breath_belly', 'spine_2', P['breath_belly'], VENTRAL, CRANIAL, 'breather', 1)
    # ---- forelimbs
    tu, tl = rg['twist_upper'], rg['twist_lower']
    add('scapula_L', f'spine_{rg["n_spine"] - 1}', P['scapula_top_L'], P['shoulder_L'] - P['scapula_top_L'], CAUDAL,
        'scapula')
    add('humerus_L', 'scapula_L', P['shoulder_L'], P['elbow_L'] - P['shoulder_L'], CAUDAL, 'hinge')
    add('humerus_twist_L', 'humerus_L', P['shoulder_L'] + tu * (P['elbow_L'] - P['shoulder_L']), role='twist', tier=1,
        driver='humerus_L', frame=frame('humerus_L'))
    add('radius_L', 'humerus_L', P['elbow_L'], P['wrist_L'] - P['elbow_L'], P['shoulder_L'] - P['elbow_L'], 'hinge')
    add('radius_twist_L', 'radius_L', P['elbow_L'] + tl * (P['wrist_L'] - P['elbow_L']), role='twist', tier=1,
        driver='radius_L', frame=frame('radius_L'))
    add('carpus_L', 'radius_L', P['wrist_L'], P['f_proxrow_L'] - P['wrist_L'], VENTRAL, 'hinge')
    add('metacarpus_L', 'carpus_L', P['f_proxrow_L'], P['f_head_L'] - P['f_proxrow_L'], VENTRAL, 'hinge',
        tip=P['f_head_L'])
    fore = ['scapula_L', 'humerus_L', 'humerus_twist_L', 'radius_L', 'radius_twist_L', 'carpus_L', 'metacarpus_L']
    for n in range(1, 5):
        d0, d1, dt = P[f'f_digit{n}_0_L'], P[f'f_digit{n}_1_L'], P[f'f_digit{n}_tip_L']
        add(f'f_digit{n}_0_L', 'metacarpus_L', d0, d1 - d0, VENTRAL, 'digit', 1)
        add(f'f_digit{n}_1_L', f'f_digit{n}_0_L', d1, dt - d1, VENTRAL, 'digit', 1, tip=dt)
        fore += [f'f_digit{n}_0_L', f'f_digit{n}_1_L']
    mirror(fore)
    # ---- hindlimbs
    add('femur_L', 'pelvis', P['hip_L'], P['knee_L'] - P['hip_L'], CRANIAL, 'hinge')
    add('femur_twist_L', 'femur_L', P['hip_L'] + tu * (P['knee_L'] - P['hip_L']), role='twist', tier=1,
        driver='femur_L', frame=frame('femur_L'))
    add('tibia_L', 'femur_L', P['knee_L'], P['ankle_L'] - P['knee_L'], P['hip_L'] - P['knee_L'], 'hinge')
    add('tibia_twist_L', 'tibia_L', P['knee_L'] + tl * (P['ankle_L'] - P['knee_L']), role='twist', tier=1,
        driver='tibia_L', frame=frame('tibia_L'))
    add('tarsus_L', 'tibia_L', P['ankle_L'], P['h_proxrow_L'] - P['ankle_L'], VENTRAL, 'hinge')
    add('metatarsus_L', 'tarsus_L', P['h_proxrow_L'], P['h_head_L'] - P['h_proxrow_L'], VENTRAL, 'hinge',
        tip=P['h_head_L'])
    hind = ['femur_L', 'femur_twist_L', 'tibia_L', 'tibia_twist_L', 'tarsus_L', 'metatarsus_L']
    for n in range(1, 6):
        d0, d1, dt = P[f'h_digit{n}_0_L'], P[f'h_digit{n}_1_L'], P[f'h_digit{n}_tip_L']
        add(f'h_digit{n}_0_L', 'metatarsus_L', d0, d1 - d0, VENTRAL, 'digit', 1)
        add(f'h_digit{n}_1_L', f'h_digit{n}_0_L', d1, dt - d1, VENTRAL, 'digit', 1, tip=dt)
        hind += [f'h_digit{n}_0_L', f'h_digit{n}_1_L']
    mirror(hind)
    # ---- tail
    n_t = rg['n_tail']
    for k in range(n_t):
        nxt = P[f'tail_{k + 1}'] if k + 1 < n_t else P['tail_tip']
        add(f'tail_{k}', 'pelvis' if k == 0 else f'tail_{k - 1}', P[f'tail_{k}'], nxt - P[f'tail_{k}'], VENTRAL,
            'tail', tip=P['tail_tip'] if k == n_t - 1 else None)
    # ---- volume helpers (AG 06.21): each in the frame of the joint whose bend drives it
    Fr, Ft = frame('radius_L'), frame('tibia_L')
    ole, kp = np.asarray(rg['olecranon']) * k_m, np.asarray(rg['knee_pt']) * k_m
    add('elbow_pt_L', 'humerus_L', P['elbow_L'] - ole[0] * Fr[:, 0] - ole[1] * Fr[:, 1], role='helper', tier=1,
        driver='radius_L', frame=Fr)
    add('knee_pt_L', 'femur_L', P['knee_L'] - kp[0] * Ft[:, 0] - kp[1] * Ft[:, 1], role='helper', tier=1,
        driver='tibia_L', frame=Ft)
    mirror(['elbow_pt_L', 'knee_pt_L'])
    # ---- IK targets (AG 05.19): under the root, on the digit bases' centre with the metapodials' frames
    add('ik_hand_L', 'root', P['f_head_L'], role='ik', tier=1, driver='metacarpus_L', frame=frame('metacarpus_L'))
    add('ik_foot_L', 'root', P['h_head_L'], role='ik', tier=1, driver='metatarsus_L', frame=frame('metatarsus_L'))
    mirror(['ik_hand_L', 'ik_foot_L'])
    # ---- AX10b (11-02): THE ROOTS' AND THE WRISTS' / ANKLES' VOLUME HELPERS (SPEC rig helpers_x10b), the elbow's and the
    # knee's construction: each ON its driver's joint in its driver's frame, a child of its driver's parent, turning half
    # its driver's local rotation (species/axolotl_rig.py drivers / HELPER), so the skin across that joint blends between
    # transforms half the bend apart: the swim's thighs laid back 93 deg kept 39-48 % of the hip root's volume, the
    # straightened wrist 61 % (ax10_check). Appended after the IK targets: the plan's 124 keep their indices
    H10B = dict(shoulder=('humerus_L', 'scapula_L'), hip=('femur_L', 'pelvis'), wrist=('carpus_L', 'radius_L'),
                ankle=('tarsus_L', 'tibia_L'))
    for nm_h in rg.get('helpers_x10b', ()):
        drv, par = H10B[nm_h]
        add(f'{nm_h}_pt_L', par, P[{'humerus_L': 'shoulder_L', 'femur_L': 'hip_L', 'carpus_L': 'wrist_L',
                                    'tarsus_L': 'ankle_L'}[drv]], role='helper', tier=1, driver=drv, frame=frame(drv))
    mirror([f'{nm_h}_pt_L' for nm_h in rg.get('helpers_x10b', ())])
    return sk


# --------------------------------------------------------------------------------------------- posing helpers
def posed(sk, local_rot, root_shift=None):
    """sk.posed_world with an optional world translation of the root (metres)"""
    W = sk.posed_world(local_rot)
    if root_shift is not None:
        T = np.eye(4)
        T[:3, 3] = root_shift
        W = [T @ w for w in W]
    return W


def aim(sk, local_rot, name, d_world, root_shift=None):
    """the local rotation that turns joint `name`'s x toward the world direction d_world under the posed parent
    (the minimal swing, no twist), added to local_rot (a copy is returned)"""
    i = sk.index(name)
    W = posed(sk, local_rot, root_shift)
    p = sk.parent[i]
    Fp = W[p][:3, :3] @ sk.local(i)[:3, :3]
    v = _unit(Fp.T @ _unit(d_world))
    x = np.array([1.0, 0.0, 0.0])
    ax = np.cross(x, v)
    s, c = np.linalg.norm(ax), float(x @ v)
    if s < 1e-15:
        R = np.eye(3)
    else:
        ax = ax / s
        Kx = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
        R = np.eye(3) + s * Kx + (1.0 - c) * (Kx @ Kx)
    out = dict(local_rot)
    out[i] = R
    return out


def swing_angles(R):
    """a local rotation's swing of the bone axis x, as (fold about z, splay about -y) in degrees: the direction R e_x =
    (cos sp cos f, cos sp sin f, -sin sp)"""
    v = R @ np.array([1.0, 0.0, 0.0])
    return float(np.degrees(np.arctan2(v[1], v[0]))), float(np.degrees(np.arcsin(np.clip(-v[2], -1.0, 1.0))))


# --------------------------------------------------------------------------------------------- the clay (AX2)
# THE CLAY (plan §5.4, AX2): ONE program at x4, metres: the body is heads/caudate.py's subdivision surface (the head,
# trunk and tail as one cage) sampled as a GRID; on it, each a group blended into the body ONCE (the octopus's
# anti-compounding lesson, sdf.py:34-37): the four limbs (a sweep from inside the body through the girdle joint, the
# elbow or knee, to the wrist or ankle; a flat palm or sole; tapering digits with round tips), the six gill rami
# (tapered sweeps along their posed chains with a fleshy root and a gentle arch), the two eyes (balls in the cage's
# lidless ports) and the two fins (SHELL membranes, species/axolotl_fins.py). Radii in life mm [E] (limbs.radii, CLAY);
# every sweep's |dr/dl| stays under the terrace limit 0.7 by construction (ax02 gates it).
# THE AX2 CHECK (10-28, close-ups the sheets show too small): (1) the palm and the sole were flat SWEEPs (aspect ~3.4),
# and a sweep's oval section measures |q| - r(theta), which near a flat oval's sides reads up to 4-8x the distance
# (|grad f| p99 2.9-4.4 on slices through the hands and feet, gate 1's body-dominated samples never saw it): sphere
# tracing printed torn shards between the digits, and AX4's projection and AX6's voxel band would read that field.
# They are now SHELL slabs (sdf.py's patch distance less a half thickness, the fins' primitive; |grad f| <= 1.02 by
# _flat_patch's bound): the same width and thickness, the top domed like the oval, round edges; ax02's gate 1 samples
# the hands and feet now. (2) The limb and ramus radii were linear between their knots (a slope kink at each): they
# are PCHIP in arc length now (C1, monotone between knots, no overshoot). The bands the close-ups showed came from
# elsewhere and stay: the mid-shank band is the limb group's 2 mm blend reaching the flank, the rami's root collars
# their 0.66 D roots under a 0.3 D blend.
# AX2b (10-28, the lead's one fix): THE RAMI TAPER AND GROW OUT OF THE HEAD. The collars were the sweep's START CAP: a
# 0.66 D ball centred on the gill base, which sits only 0.18-0.45 mm under the skin, while each stalk leaves the skin
# 34-49 deg off its normal, so most of the ball stood out as a cuff and the drop to 0.52 D behind it read as a neck.
# Now each sweep starts root_D x D INSIDE the head on the stalk's own base tangent (the buried root rides neck_0, so it
# stays in the head when the gills fold), its radius rising as a trumpet to the skin (0.74 D at the base, |dr/dl| <=
# 0.4) and its start cap small and buried (0.40 D at about 2.2 mm under the skin): no ball, no neck. On the side the
# stalk leans away from, the flared root stands up to ~1.7 mm (r1) proud of the skin and the 0.3 D blend rounds it: the
# fleshy base p13 and p20 show where the rami spread into the head's rear corner. The stalk is p17's own: the top ramus
# (seen side-on along its length, the sweep's D reference) traced across its width at 49 stations (my edge trace on its
# luminance, 10-28): 1.03-1.04 D wide from 0.26 to 0.42 L, 0.93 D at 0.50-0.58 L, 0.84 at 0.66, 0.70 at 0.74, 0.64 at
# 0.82, 0.51 at 0.90, 0.32 at 0.98: a blunt round end (the middle ramus, foreshortened, tapers harder: 0.26 D at 0.90
# L). The radii below are those half widths.
# AX2b's LOOK (10-28, close-ups beside p13, p17 and p20): the taper reads (horns, not pipes), but each root still read
# as a drum with a rim in three-quarter views: the radius fell 0.155 D over the first 0.10 L and then flattened, a knee
# that reads as a collar's edge. Now the flare EASES OUT: r = 0.515 + 0.15 exp(-t / 0.09) D from the base to 0.42 L
# (0.665 D at the base, half its excess gone every 0.062 L, so no knee), p17's half widths beyond; and the rami group's
# blend is 0.33 of r1's D (1.12 mm life; it was 0.30), a broader concave fillet under each stalk's overhang, the
# fleshy base p13 and p20 show. Not more: AX3 lays each ramus's graft ring as the tube's first ring past its port's
# fillet (the body's blend), and r3 rises off the shoulder slowly (its gap to the body grows 0.46 mm per mm), so at
# 0.40 its first clean ring fell at 0.262 of its stalk, past gill_3_1, and its graft root would have moved; at 0.33 all
# six rings sit at one share (0.2425) before gill_r_1, the plan's root. And laid back as p01, r1 already lies 1.4 mm
# into the dorsum and r3's distal stalk 0.9 mm into the upper arm, so a much larger blend webs them along their length
# (my measures, 10-28). Gates 6 and 7 read the centrelines against the body alone, so neither the profile nor the
# blend moves them.
CLAY = dict(
    k_limb=2.0, k_gill_D=0.33, k_fin=0.30, k_digit=0.35, k_palm=0.6,      # blends (life mm; the rami's in D)
    root_share=0.4,          # the forelimb's sweep starts this share of the way from the glenoid to the scapula's top
    hip_root_share=0.35,     # the hindlimb's from the hip toward the pelvis
    root_r=1.0,              # the root's radius over the limb's first segment's (buried; AX2's first look: 1.15 with a
    #                          2.5 mm blend raised a mound round each limb's root)
    elbow=1.08, knee=1.10,   # the joint's bulge over its segment's radius
    wrist=0.80, ankle=0.78,  # the wrist's and the ankle's radius over the forearm's and the shank's
    palm_t=0.85, sole_t=0.90,                 # the palm's and the sole's half thickness (mm)
    slab_sag=0.25,           # their slabs' half thickness falls this much (mm) toward the sides (_flat_patch)
    palm_root=1.5, sole_root=1.8,            # their half width at the wrist and the ankle (mm)
    digit_r=(0.58, 0.46), digit_back=0.9,    # a digit's radius at its base and tip (mm); its sweep starts this far back
    # the ramus's radius over D at t = its arc length from the base (gill_r_0) over the stalk's: t < 0 is the buried root
    # (AX2b's look; AX2's was ((0.0, 0.66), (0.10, 0.52), (0.50, 0.45), (0.90, 0.36), (1.0, 0.30)), AX2b's first build
    # ((-0.15, 0.40), (-0.07, 0.62), (0.0, 0.74), (0.035, 0.70), (0.07, 0.635), (0.10, 0.585), (0.14, 0.545), (0.25,
    # 0.52), then as now from 0.42); 0.0 to 0.29 sample the easing above, 0.42 on are p17's
    gill_r=((-0.15, 0.40), (-0.075, 0.58), (0.0, 0.665), (0.03, 0.623), (0.06, 0.592), (0.10, 0.565), (0.15, 0.544),
            (0.21, 0.530), (0.29, 0.521), (0.42, 0.515), (0.54, 0.467), (0.66, 0.42), (0.74, 0.35), (0.82, 0.322),
            (0.90, 0.262), (0.95, 0.215), (1.0, 0.175)),
    # (AX7b: the last three knots were (0.90, 0.256), (0.95, 0.195), (1.0, 0.13): the end's hemisphere of 0.13 D read as
    # a point beside p13's round blunt tips; 0.175 D keeps p17's trace (0.16 D half width at 0.98 L) within 0.02 D)
    root_D=1.0,              # the buried root's length behind the base, x D (AX2b)
    gill_arch=0.05,          # the ramus's sag over its length, its tip bowing toward its comb side (before AX7b; with
    #                          SPEC ax7b the bow is ax7b.ramus_arch, gill_rami's note)
    comb_dir=(0.0, -0.55, -0.83),                # the comb side in the bind: back and down (plan §2.5, p17)
    node_mm=0.5,             # sweep nodes (life mm)
)
# AX7b (10-30; the round-6 look: the rami "spiky cones"): (1) THE STALK IS OVAL: p17's top ramus seen side-on is 290 px
# across, its middle ramus seen face-on 415 px (one animal), p13's r1 from the front 1.31 x the side-on D: each ramus's
# sweep carries axolotl_gills.stalk_aspect in the sweep's b direction (across the comb face, round at the root), the
# filament vanes on the face's edges, built at SPEC ax7b.ramus_aspect_built (the measured 1.37), r2 / r3 turned whole so
# the stacked rami carry r1's section (the note above _port_frame; the first AX7b build was round). (2) THE BOW: p17's top
# ramus's centre lies 0.085 L (at 0.36 L) and 0.107 L (at 0.68 L) off its base-tip chord AWAY from its comb (the comb
# hangs from the concave side; the round-6 sag bowed toward it, symmetric): the bow is ax7b.ramus_arch toward -comb,
# deepest at ax7b.ramus_arch_peak (u^p (1 - u), level at the base, so the buried root's tangent is the chord's). (3) THE
# DIGITS taper to about half their base at a rounded tip (p23, p04, p05): ax7b.digit_r for CLAY digit_r, and the high's
# tip bulb is gone (axolotl_sculpt TIP)


def _catmull(P, step):
    """a centripetal-ish Catmull-Rom curve through the points P (n, 3), sampled about every `step`; returns the dense
    points and each one's parameter in [0, n - 1]"""
    P = np.asarray(P, np.float64)
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out, par = [], []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        n = max(2, int(np.ceil(np.linalg.norm(p2 - p1) / step)))
        for t in np.linspace(0.0, 1.0, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
            par.append(i + t)
    out.append(P[-1])
    par.append(len(P) - 1.0)
    return np.array(out), np.array(par)


def _transport(C, n0):
    """frame normals along the polyline C by parallel transport from n0"""
    T = np.gradient(C, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-15)
    N = np.zeros_like(C)
    n = np.asarray(n0, np.float64) - T[0] * (np.dot(n0, T[0]))
    if np.linalg.norm(n) < 1e-9:
        n = np.cross(T[0], [0.31, 0.83, 0.47])
    n /= np.linalg.norm(n)
    for i in range(len(C)):
        n = n - T[i] * (n @ T[i])
        n /= np.linalg.norm(n)
        N[i] = n
    return N, T


def _arc(P):
    """the cumulative arc length along the polyline P (n, 3)"""
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def _smooth_profile(x_knots, values, x):
    """a C1 profile through (x_knots, values) at x: PCHIP, monotone between the knots and never overshooting them (a
    linear profile kinks at every knot: the AX2 check)"""
    return PchipInterpolator(np.asarray(x_knots, np.float64), np.asarray(values, np.float64))(np.asarray(x, np.float64))


def _flat_patch(P, N, half_w, t, sag=0.25, n_across=33):
    """a SHELL slab along the centreline P (n, 3): a row across each node in the plane of the tangent T and B = T x N
    (the sweep's b axis); the half thickness t on the centreline falls off as t - s (2 f^2 - f^4) across the row (f in
    -1..1), so the top domes like the oval it replaces instead of reading as a plank (the AX2 check's first slab), and
    flat at the row's ends, so the round edge meets it without a crease (an f^2 fall-off printed a line along each
    side); s = min(sag, 0.12 x the row's patch half width) keeps |grad H| <= 1.54 s / hw <= 0.19, so |grad f| <= 1.02
    (sdf.py's shell is |p - cp| - H(cp)); the row reaches half_w - (t - s) to each side, so the slab is 2 x half_w
    wide, its edges round. H is linear over each triangle (sdf.py), so the rows are fine across (9 columns shaded as 8
    flat strips). All in one unit (metres). Returns (V (n x n_across, 3), F (m, 3), H (n x n_across,))"""
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-15)
    B = np.cross(T, N)
    B /= np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-15)
    base = np.maximum(np.asarray(half_w, np.float64) - t, 0.05 * t)
    hw = np.where(base / 0.88 * 0.12 <= sag, base / 0.88, base + sag)      # hw = base + min(sag, 0.12 hw)
    s = np.minimum(sag, 0.12 * hw)
    f = np.linspace(-1.0, 1.0, n_across)
    V = (P[:, None, :] + f[None, :, None] * hw[:, None, None] * B[:, None, :]).reshape(-1, 3)
    H = (t - s[:, None] * (2.0 * f[None, :] ** 2 - f[None, :] ** 4)).reshape(-1)
    F = []
    for i in range(len(P) - 1):
        for j in range(n_across - 1):
            a = i * n_across + j
            c = a + n_across
            F += [[a, c, c + 1], [a, c + 1, a + 1]]
    return V, np.array(F, np.int64), H


def _fleshy_digit(a7c, ray0, d0, d1, dt, up, step, k_m, dr_joint):
    """AX7c, 10-30: A DIGIT AS THE PHOTOS MEASURE IT (the AX7b check: rods 0.12-0.14 of their length wide at the base,
    where p04's toes and p23's fingers are fleshy cones 0.30-0.37, webbed at the base; p04's tips dark). One sweep (x4 m)
    from ray0, inside the palm / sole near its proximal row, through the digit's base joint d0, its IP d1, to its tip dt:
      - the DIGIT (d0 -> tip): a cone whose base half-width is digit_base_k x the digit's own length (at least
        digit_base_min), narrowing as (1 - u)^digit_taper_p to digit_tip_k of the base at a round tip; slightly flat
        (digit_aspect = half-width / half-height): a long digit is a broad one, so neighbours overlap near the palm's
        edge and the clay webs them there (their union and its blend), each standing free past the web;
      - the RAY (ray0 -> d0): the metapodial under the skin, ray_r0 of the base widening into it, so the dorsum of the
        palm / sole carries a ridge into each digit instead of the slab's flat top (the chrome sheet: AX7c item 3);
      - LYING ON THE FLOOR: each node raised along the hand's dorsal `up` by its half-height less the joints' height
        above the floor (dr_joint, AX1's), so a broad base does not sink through the floor and its sole stays down.
    Returns (P, N, r0 (the half-height), aspect, the base half-width life mm, the digit's length life mm, i_d0: the first
    node at d0: P[i_d0:] is the digit proper, P[:i_d0] its ray, which belongs to the palm's section: AX3's collar gate
    asks a palm or sole ring to clear the digit, not the ray inside its own pad)"""
    Pd, pard = _catmull(np.array([ray0, d0, d1, dt]), step)
    Ld = _arc(Pd)
    a0 = float(np.interp(1.0, pard, Ld))                       # the arc at d0
    L = (Ld[-1] - a0) / k_m                                    # life mm, d0 to the tip
    rb = max(a7c['digit_base_min'], a7c['digit_base_k'] * L)
    rt = max(a7c['digit_tip_min'], a7c['digit_tip_k'] * rb)
    u = np.clip((Ld - a0) / max(Ld[-1] - a0, 1e-12), 0.0, 1.0)
    w_dig = rt + (rb - rt) * (1.0 - u) ** a7c['digit_taper_p']
    t = np.clip(Ld / max(a0, 1e-12), 0.0, 1.0)
    w_ray = rb * (a7c['ray_r0'] + (1.0 - a7c['ray_r0']) * t * t * (3.0 - 2.0 * t))
    w = np.where(Ld < a0, w_ray, w_dig)                        # the half-width, life mm
    h = w / a7c['digit_aspect']                                # the half-height
    up = np.asarray(up, np.float64) / np.linalg.norm(up)
    Pd = Pd + up[None, :] * (np.maximum(h - dr_joint, 0.0) * k_m)[:, None]
    Nd, _ = _transport(Pd, up)
    i_d0 = int(np.searchsorted(Ld, a0))
    return Pd, Nd, h * k_m, np.full(len(Pd), a7c['digit_aspect']), float(rb), float(L), i_d0


def _skin(sk, W):
    """the skinning matrices (posed world x rest world inverse) by joint name"""
    return {nm: W[i] @ np.linalg.inv(sk.world[i]) for i, nm in enumerate(sk.names)}


def _pt(M, p):
    return (M @ np.append(np.asarray(p, np.float64), 1.0))[:3]


def body_owners(spec, chain):
    """the axial bones by station (each owns the body from its joint to the next joint toward its tip): (names, the
    station boundaries) for rig.hat_weights"""
    st, rg = spec['stations'], spec['rig']
    s_sp = chain['s_spine']
    owners = ['head', 'neck_0'] + [f'spine_{k}' for k in range(rg['n_spine'] - 1, -1, -1)] + ['pelvis'] + \
        [f'tail_{k}' for k in range(rg['n_tail'])]
    # the head owns [0, AO], neck_0 [AO, neck], spine_6 [neck, its own station (the shoulder)] ... spine_0 [.., its
    # station], the pelvis from spine_0 to tail_0 (the girdle and the cloaca ride it), each tail joint to the next
    edges = [0.0, st['head_joint'], st['neck']] + [s_sp[k] for k in range(rg['n_spine'] - 1, -1, -1)] + \
        list(chain['s_tail']) + [1.0]
    assert len(edges) == len(owners) + 1
    return owners, np.array(edges)


def pose_body(spec, chain, sk, W, P_mm):
    """the body's points (life mm, the bind) moved by the posed axial skeleton: linear blend of the owning bones by
    station (rig.hat_weights on the owners' spans)"""
    owners, edges = body_owners(spec, chain)
    k_m = chain['k']
    st = spec['stations']
    TL = spec['a1']['TL']
    s = st['hip'] - (np.asarray(P_mm)[:, 2] / TL)
    k0, k1, t = RG.hat_weights(s, edges)
    Ms = _skin(sk, W)
    M = np.stack([Ms[nm] for nm in owners])
    Pm = np.asarray(P_mm, np.float64) * k_m
    Ph = np.concatenate([Pm, np.ones((len(Pm), 1))], 1)
    A = np.einsum('nij,nj->ni', M[np.minimum(k0, len(owners) - 1)], Ph)[:, :3]
    B = np.einsum('nij,nj->ni', M[np.minimum(k1, len(owners) - 1)], Ph)[:, :3]
    return ((1 - t)[:, None] * A + t[:, None] * B) / k_m


def limb_sweeps(spec, chain, sk, W, node_mm=None):
    """the four limbs' sweeps in metres: a list of dict(name, P (n, 3), N (n, 3), r0 (n,), aspect (n,), k, group).
    node_mm: the sweeps' node spacing (life mm; CLAY's by default). A sweep's centreline is the polyline through its
    nodes, so a bent tube carries a facet at every node (AX6's look: bands 2 mm x4 apart round the knee and the elbow
    in a wet light); the voxel high samples the same curves denser"""
    lb, rg = spec['limbs'], spec['rig']
    rad = lb.get('radii_x2', lb['radii'])            # AX2's limb widths read on the photos, else the plan's [E]
    k_m = chain['k']
    C = CLAY
    Ms = _skin(sk, W)
    meta = sk.meta
    pos = lambda nm: W[sk.index(nm)][:3, 3]                                     # noqa: E731
    tip = lambda nm: _pt(Ms[nm], meta[nm]['tip'])                              # noqa: E731
    out = []
    step = (C['node_mm'] if node_mm is None else node_mm) * k_m
    digit_r = spec['ax7b']['digit_r'] if 'ax7b' in spec else C['digit_r']        # AX7b: the taper (CLAY's note)
    a7c = spec.get('ax7c') if 'digit_base_k' in spec.get('ax7c', {}) else None    # AX7c: the fleshy digits
    if a7c is not None and spec.get('ax8'):
        # AX8: the fine tips (SPEC ax8's digit rows over AX7c's of the same name: p04 / p23's points, where AX7c's round
        # ends at half the base read as human fingertips)
        a7c = dict(a7c, **{k: v for k, v in spec['ax8'].items() if k.startswith('digit_')})
    dr_joint = lb['radii']['digit']                  # the digits' joints above the floor (AX1's rest_chain)
    pad_t = (a7c['pad_t'] if a7c else (C['palm_t'], C['sole_t']))                 # AX7c: the palm's / sole's half
    pad_sag = a7c['pad_sag'] if a7c else C['slab_sag']                             # thickness and dome
    # AX10: the palm's / sole's blend into the forearm / shank (limb_rest's note: the wrist and ankle a filleted bend)
    k_pad = float((spec.get('ax10') or {}).get('k_pad', C['k_palm']))
    for side in ('L', 'R'):
        # ---- forelimb: root -> glenoid -> elbow -> wrist, round; the palm flat; four fingers
        g, e, wr = pos(f'humerus_{side}'), pos(f'radius_{side}'), pos(f'carpus_{side}')
        root = g + C['root_share'] * (pos(f'scapula_{side}') - g)
        r_ua, r_fa = rad['upper_arm'], rad['forearm']
        knots = np.array([root, g, 0.5 * (g + e), e, 0.5 * (e + wr), wr])
        rk = np.array([C['root_r'] * r_ua, r_ua * 1.04, r_ua, C['elbow'] * max(r_ua, r_fa) * 0.97, r_fa,
                       C['wrist'] * r_fa]) * k_m
        Pc, par = _catmull(knots, step)
        Lc = _arc(Pc)
        r0 = _smooth_profile(np.interp(np.arange(len(knots)), par, Lc), rk, Lc)
        Nn, _ = _transport(Pc, [0.0, 1.0, 0.0])
        out.append(dict(name=f'fore_{side}', P=Pc, N=Nn, r0=r0, aspect=np.ones(len(Pc)), k=0.0, group=f'limb_fore_{side}'))
        # the palm: wrist -> the carpometacarpal joint -> the digit bases' centre, flat, its dorsal normal the carpus's -y;
        # a SHELL slab (CLAY's note): P, N, r0 and aspect stay as its description (the gates' samplers read them)
        cm, hd = pos(f'metacarpus_{side}'), tip(f'metacarpus_{side}')
        Pp, parp = _catmull(np.array([wr, cm, hd + 0.25 * (hd - cm)]), step)
        up = -W[sk.index(f'carpus_{side}')][:3, 1]
        Np, _ = _transport(Pp, up)
        Lp = _arc(Pp)
        half_w = _smooth_profile(np.interp([0.0, 1.0, 2.0], parp, Lp),
                                 [C['palm_root'], 0.5 * rg['palm_w'] + 0.35, 0.5 * rg['palm_w'] + 0.4], Lp)
        r0p = np.full(len(Pp), pad_t[0]) * k_m
        out.append(dict(name=f'palm_{side}', P=Pp, N=Np, r0=r0p, aspect=half_w / pad_t[0], k=k_pad * k_m,
                        group=f'limb_fore_{side}',
                        shell=_flat_patch(Pp, Np, half_w * k_m, pad_t[0] * k_m, pad_sag * k_m)))
        for n in range(1, 5):
            d0, d1, dt = pos(f'f_digit{n}_0_{side}'), pos(f'f_digit{n}_1_{side}'), tip(f'f_digit{n}_1_{side}')
            if a7c:
                # AX7c: the fleshy webbed digit and its ray from the palm's proximal row (_fleshy_digit)
                ray0 = cm + a7c['ray_lat'] * (d0 - hd) - (d0 - hd) @ up * up
                Pd, Nd, r0d, asp, rb, Ldig, i_d0 = _fleshy_digit(a7c, ray0, d0, d1, dt, up, step, k_m, dr_joint)
                out.append(dict(name=f'finger{n}_{side}', P=Pd, N=Nd, r0=r0d, aspect=asp, k=a7c['k_digit'] * k_m,
                                group=f'limb_fore_{side}', base_halfwidth=rb, digit_len=Ldig, i_d0=i_d0))
                continue
            back = d0 - C['digit_back'] * k_m * (d1 - d0) / np.linalg.norm(d1 - d0)
            Pd, pard = _catmull(np.array([back, d0, d1, dt]), step)
            Ld = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))])
            # AX7b: the radius eases from the base toward the tip (u^1.4: p23's digits hold their base a little, then
            # taper to about half at a rounded tip); before, linear from C digit_r's (0.58, 0.46)
            r0d = (digit_r[0] + (digit_r[1] - digit_r[0]) * (Ld / Ld[-1]) ** 1.4) * k_m * rad['digit'] / 0.5
            Nd, _ = _transport(Pd, up)
            out.append(dict(name=f'finger{n}_{side}', P=Pd, N=Nd, r0=r0d, aspect=np.ones(len(Pd)), k=C['k_digit'] * k_m,
                            group=f'limb_fore_{side}'))
        # ---- hindlimb: root -> hip -> knee -> ankle; the sole; five toes
        hp, kn, an = pos(f'femur_{side}'), pos(f'tibia_{side}'), pos(f'tarsus_{side}')
        root = hp + C['hip_root_share'] * (pos('pelvis') - hp)
        r_th, r_sh = rad['thigh'], rad['shank']
        knots = np.array([root, hp, 0.5 * (hp + kn), kn, 0.5 * (kn + an), an])
        rk = np.array([C['root_r'] * r_th, r_th * 1.04, r_th, C['knee'] * max(r_th, r_sh) * 0.95, r_sh,
                       C['ankle'] * r_sh]) * k_m
        Pc, par = _catmull(knots, step)
        Lc = _arc(Pc)
        r0 = _smooth_profile(np.interp(np.arange(len(knots)), par, Lc), rk, Lc)
        Nn, _ = _transport(Pc, [0.0, 1.0, 0.0])
        out.append(dict(name=f'hind_{side}', P=Pc, N=Nn, r0=r0, aspect=np.ones(len(Pc)), k=0.0, group=f'limb_hind_{side}'))
        # the sole: a SHELL slab, as the palm
        tm, fh = pos(f'metatarsus_{side}'), tip(f'metatarsus_{side}')
        Pp, parp = _catmull(np.array([an, tm, fh + 0.2 * (fh - tm)]), step)
        up = -W[sk.index(f'tarsus_{side}')][:3, 1]
        Np, _ = _transport(Pp, up)
        Lp = _arc(Pp)
        half_w = _smooth_profile(np.interp([0.0, 1.0, 2.0], parp, Lp),
                                 [C['sole_root'], 0.5 * rg['sole_w'] + 0.3, 0.5 * rg['sole_w'] + 0.4], Lp)
        r0p = np.full(len(Pp), pad_t[1]) * k_m
        out.append(dict(name=f'sole_{side}', P=Pp, N=Np, r0=r0p, aspect=half_w / pad_t[1], k=k_pad * k_m,
                        group=f'limb_hind_{side}',
                        shell=_flat_patch(Pp, Np, half_w * k_m, pad_t[1] * k_m, pad_sag * k_m)))
        for n in range(1, 6):
            d0, d1, dt = pos(f'h_digit{n}_0_{side}'), pos(f'h_digit{n}_1_{side}'), tip(f'h_digit{n}_1_{side}')
            if a7c:
                # AX7c: the fleshy webbed toe and its ray from the sole's proximal row (_fleshy_digit)
                ray0 = tm + a7c['ray_lat'] * (d0 - fh) - (d0 - fh) @ up * up
                Pd, Nd, r0d, asp, rb, Ldig, i_d0 = _fleshy_digit(a7c, ray0, d0, d1, dt, up, step, k_m, dr_joint)
                out.append(dict(name=f'toe{n}_{side}', P=Pd, N=Nd, r0=r0d, aspect=asp, k=a7c['k_digit'] * k_m,
                                group=f'limb_hind_{side}', base_halfwidth=rb, digit_len=Ldig, i_d0=i_d0))
                continue
            back = d0 - C['digit_back'] * k_m * (d1 - d0) / np.linalg.norm(d1 - d0)
            Pd, pard = _catmull(np.array([back, d0, d1, dt]), step)
            Ld = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))])
            # AX7b: the radius eases from the base toward the tip (u^1.4: p23's digits hold their base a little, then
            # taper to about half at a rounded tip); before, linear from C digit_r's (0.58, 0.46)
            r0d = (digit_r[0] + (digit_r[1] - digit_r[0]) * (Ld / Ld[-1]) ** 1.4) * k_m * rad['digit'] / 0.5
            Nd, _ = _transport(Pd, up)
            out.append(dict(name=f'toe{n}_{side}', P=Pd, N=Nd, r0=r0d, aspect=np.ones(len(Pd)), k=C['k_digit'] * k_m,
                            group=f'limb_hind_{side}'))
    return out


def gill_rami(spec, chain, sk, W, node_mm=None, _turns=None):
    """the six rami along their posed chains: {(r, side): dict(P (n, 3) m, N, r0 (n,) m, D m, comb (n, 3) unit, joint
    (n,) sk index, L m, i0)}; the comb side is the bind's back-and-down direction across each stalk, carried by the joint
    each node rides (plan §2.5: the anterior face bare). AX2b (CLAY's note): each sweep starts CLAY root_D x D inside
    the head on the stalk's base tangent, its two buried control points riding neck_0 (so the root stays in the head in
    every posture and the stalk turns about its base); P[i0:] is the stalk from its base (gill_r_0) to its tip, the part
    the filaments line and the radius profile's t = 0 .. 1 measures. node_mm: as limb_sweeps'. _turns: the oval stalks'
    rigid turns (_oval_turns; read here on the bind at CLAY's nodes whenever the SPEC builds ovals, {} for none)"""
    gl, rg = spec['gills'], spec['rig']
    k_m = chain['k']
    Ms = _skin(sk, W)
    meta = sk.meta
    out = {}
    d_pv = np.asarray(CLAY['comb_dir'], np.float64)
    j_neck = sk.index('neck_0')
    a7 = spec.get('ax7b')
    if _turns is None:
        # AX7b: the oval stalks' turns (the note above _port_frame), read once on the BIND at CLAY's own node spacing, so
        # every posture and every consumer (AX2's poses, AX3-AX5's bind, AX6's denser high) turns each ramus alike
        oval = bool(a7) and a7['ramus_aspect_built'] != 1.0
        _turns = _oval_turns(spec, gill_rami(spec, chain, sk, sk.world, None, _turns={})) if oval else {}
    for side in ('L', 'R'):
        for r in (1, 2, 3):
            names = [f'gill_{r}_{j}_{side}' for j in range(rg['gill_joints'])]
            rest = [sk.world[sk.index(nm)][:3, 3] for nm in names] + [meta[names[-1]]['tip']]
            rest = np.array(rest)
            L = float(np.linalg.norm(rest[-1] - rest[0]))
            D = L / gl['ramus_D']
            # the bind's chain bowed (AX7b: away from the comb side, deepest near the tip: the note above CLAY's end;
            # before, a symmetric sag toward it), then posed joint by joint
            ax = (rest[-1] - rest[0]) / L
            c0 = d_pv - ax * (d_pv @ ax)
            c0 /= np.linalg.norm(c0)
            u = np.linspace(0.0, 1.0, len(rest))
            if a7:
                pk = a7['ramus_arch_peak']
                p_ = pk / (1.0 - pk)                          # u^p (1 - u) is deepest at u = p / (p + 1)
                prof = u ** p_ * (1.0 - u) / (pk ** p_ * (1.0 - pk))
                bowed = rest - a7['ramus_arch'] * L * prof[:, None] * c0
                slope0 = np.zeros(3)                          # level at the base (p_ > 1)
            else:
                bowed = rest + CLAY['gill_arch'] * L * 4.0 * (u * (1 - u))[:, None] * c0
                slope0 = 4.0 * CLAY['gill_arch'] * L * c0
            # the buried root: two control points behind the base on the bowed chain's tangent there, so the curve runs
            # on into the head with no kink
            t0 = (rest[-1] - rest[0]) + slope0
            t0 /= np.linalg.norm(t0)
            depth = CLAY['root_D'] * D
            ctrl = np.vstack([bowed[0] - depth * t0, bowed[0] - 0.5 * depth * t0, bowed])
            turn = _turns.get((r, side))
            if turn is not None:
                # AX7b: the whole bind ramus (its bow, buried root and comb side) turned rigidly about its graft ring's
                # axis, so r2 / r3 stay exact similar copies of r1 with each oval where its ring needs it
                O_t, Z_t, ang = turn['O'], turn['Z'], turn['turn']
                ctrl = O_t + _rotate_about(ctrl - O_t, np.broadcast_to(Z_t, ctrl.shape), ang)
                c0 = _rotate_about(c0[None], Z_t[None], ang)[0]
            joint_of = [j_neck, j_neck] + [sk.index(nm) for nm in names] + [sk.index(names[-1])]
            posed = np.array([_pt(Ms[sk.names[joint_of[k]]], ctrl[k]) for k in range(len(ctrl))])
            # the middle buried point rides half the base joint's turn (the mean of its two placements): a fold at the
            # base (ax02's p01 pose aims gill_r_0) spreads over the root instead of kinking there, where the inner side
            # creased (AX2b's look). The bind is unchanged (every skin matrix the identity)
            posed[1] = 0.5 * (posed[1] + _pt(Ms[names[0]], ctrl[1]))
            Pc, par = _catmull(posed, (CLAY['node_mm'] if node_mm is None else node_mm) * k_m)
            seg = np.minimum(np.floor(par).astype(int), len(ctrl) - 2)
            jt = np.array([joint_of[k] for k in seg])
            comb = np.array([Ms[sk.names[j]][:3, :3] @ c0 for j in jt])
            i0 = int(np.argmax(par >= 2.0 - 1e-9))          # the base: control point 2, sampled exactly by _catmull
            Ln = _arc(Pc)
            t = (Ln - Ln[i0]) / (Ln[-1] - Ln[i0])
            r0 = _smooth_profile(*np.asarray(CLAY['gill_r']).T, t) * D
            Nn, _ = _transport(Pc, comb[0])
            # AX7b: the oval stalk (the sweep's b axis broad), the filaments' roots read the same function
            from ..species import axolotl_gills as GL
            asp = GL.stalk_aspect(spec, t)
            out[(r, side)] = dict(P=Pc, N=Nn, r0=r0, D=D, comb=comb, joint=jt, L=L, i0=i0, aspect=asp,
                                  roll_deg=turn['roll_deg'] if turn else 0.0)
    return out


# AX7b: THE OVAL STALKS' TURN. The six stalks stack on r1's UVs (AX5) through ring-index maps (SPEC ax7b.ring_shift:
# r1's ring vertex c is r_k's vertex c + shift), and every ring keeps the crossbreed contract (vertex 0 on its own port
# frame's tangent X, AX3). A round section maps onto itself under any roll; an oval one only where each oval sits in its
# own ring frame as r1's sits in r1's, read through the shift: r2 (shift 0) at r1's angle; r3 (shift 1) at r1's angle
# less r1's ring table at vertex -1 (AX3 gives r3's ring r1's table re-based the same way). The bind's rami are similar
# copies of r1 (each built on its own chord and comb side), so each r2 / r3 turns RIGIDLY about its graft ring's axis
# (the stalk's tangent through the ring's centre at SPEC ax7b.graft_share) by the angle that puts its oval there: its
# bow, buried root, sweep frame and comb side together, so it stays r1's exact similar copy (AX3 gate 5) under the map
# that takes r1's ring frame to its own. (The first AX7b build turned only the frame and the comb, leaving the bow
# behind: r2 / r3 2.5 texels off r1's similarity at AX3.) The ring's frame is the turn's axis, so one turn is exact. The
# right side is the left's mirror (the same angles in its left-handed convention).
def _port_frame(Z, side):
    """slots.port_frame's X (the lateral axis made perpendicular to Z; -z where |Z.x| > 0.9), Y = Z x X (ax03's
    tangent_frame)"""
    Z = Z / np.linalg.norm(Z)
    ref = np.array([0.0, 0.0, -1.0]) if abs(Z[0]) > 0.9 else np.array([-1.0 if side == 'R' else 1.0, 0.0, 0.0])
    X = ref - (ref @ Z) * Z
    X /= np.linalg.norm(X)
    return X, np.cross(Z, X), Z


def _graft_frame(R, share):
    """the stalk at its share (ax03's Track over the sweep's nodes): the centre, the tangent, the sweep's N across it,
    the radius and the aspect there"""
    P = R['P']
    Ln = _arc(P)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    a = Ln[R['i0']] + share * (Ln[-1] - Ln[R['i0']])
    i = int(np.clip(np.searchsorted(Ln, a, side='right') - 1, 0, len(P) - 2))
    f = (a - Ln[i]) / max(Ln[i + 1] - Ln[i], 1e-15)
    O = P[i] + f * (P[i + 1] - P[i])
    Z = T[i] * (1 - f) + T[i + 1] * f
    Z /= np.linalg.norm(Z)
    n = R['N'][i] * (1 - f) + R['N'][i + 1] * f
    n = n - Z * (n @ Z)
    n /= np.linalg.norm(n)
    return (O, Z, n, float(R['r0'][i] * (1 - f) + R['r0'][i + 1] * f),
            float(R['aspect'][i] * (1 - f) + R['aspect'][i + 1] * f))


def oval_ring_table(r, asp, phi, K=12, n_dense=48):
    """ax03 place_ring's 'arc' rule on the analytic oval (radius r along its axis at ring angle phi, r x asp across):
    the four axis vertices on the axis lines, each quadrant's others at equal arc length over n_dense + 1 samples"""
    from ..species import axolotl_gills as GL
    q = K // 4
    phis = []
    for quad in range(4):
        dense = quad * np.pi / 2 + np.linspace(0.0, np.pi / 2, n_dense + 1)
        rho = GL.oval_radius(r, asp, dense - phi)
        Pq = np.column_stack([rho * np.cos(dense), rho * np.sin(dense)])
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pq, axis=0), axis=1))])
        phis.append(np.interp(arc[-1] * np.arange(q) / q, arc, dense))
    return np.concatenate(phis)


def _rotate_about(V, T, ang):
    """each row of V turned by ang (rad, right-handed) about the unit row of T (Rodrigues)"""
    return V * np.cos(ang) + np.cross(T, V) * np.sin(ang) + T * (T * V).sum(1)[:, None] * (1 - np.cos(ang))


def _oval_turns(spec, bind, K=12):
    """the turns of r2 / r3 (the note above _port_frame) from the unturned BIND rami: {(r, side): dict(O, Z (the turn's
    axis through the graft ring's centre, m), turn (rad, right-handed about Z), roll_deg (in the ring's own angle
    convention), ring_phi_deg (where the oval's N then sits in its ring frame))}"""
    a7 = spec['ax7b']
    share, shifts = a7['graft_share'], a7['ring_shift']
    turns = {}
    for side, hand in (('L', 1.0), ('R', -1.0)):
        _, Z1, n1, r1, asp1 = _graft_frame(bind[(1, side)], share)
        X1, Y1, _ = _port_frame(Z1, side)
        phi1 = float(np.arctan2(hand * (n1 @ Y1), n1 @ X1))
        th1 = oval_ring_table(r1, asp1, phi1, K)
        for r in (2, 3):
            O, Z, n, _, _ = _graft_frame(bind[(r, side)], share)
            X, Y, _ = _port_frame(Z, side)
            phi = float(np.arctan2(hand * (n @ Y), n @ X))
            s = int(shifts[r - 1])
            alpha = phi1 - th1[(-s) % K]
            delta = float((alpha - phi + np.pi) % (2 * np.pi) - np.pi)
            turns[(r, side)] = dict(O=O, Z=Z, turn=hand * delta, roll_deg=float(np.degrees(delta)),
                                    ring_phi_deg=float(np.degrees(alpha)))
    return turns


def eye_balls(eye, sk, W, k_m):
    """the two eyeballs' posed centres (m) and radius (m): caudate's ball (the left eye's, life mm) mirrored, riding the
    head joint"""
    Mh = W[sk.index('head')] @ np.linalg.inv(sk.world[sk.index('head')])
    out = []
    for sgn in (1.0, -1.0):
        c = np.asarray(eye['centre'], np.float64) * np.array([sgn, 1.0, 1.0]) * k_m
        out.append(_pt(Mh, c))
    return out, eye['r_ball'] * k_m


def clay_program(spec, SDF, grid, limbs=None, rami=None, eyes=None, fins=None):
    """the clay's SDF program (metres at x4; SDF the sdf module holding GRID: the forge's once landed, the staged patch
    until then). grid: (values m, origin m, cell m); limbs: limb_sweeps(...); rami: gill_rami(...); eyes: (centres,
    radius); fins: {name: (V m, F, half thickness m)}. Each part's group is blended into the body once"""
    prg = SDF.Program()
    vals, org, cell = grid
    prg.grid(org, np.eye(3), cell, vals, name='body')
    k_m = spec['author_scale'] / 1000.0
    if limbs:
        for g in sorted(set(m['group'] for m in limbs)):
            prg.begin_group(SDF.UNION, CLAY['k_limb'] * k_m)
            for m in [m for m in limbs if m['group'] == g]:
                if 'shell' in m:            # the palm and the sole (CLAY's note)
                    V, F, H = m['shell']
                    prg.shell(V, F, H, op=SDF.UNION, k=m['k'], maxd=0.02, name=m['name'])
                else:
                    prg.sweep(m['P'], m['N'], m['r0'], aspect=m['aspect'], op=SDF.UNION, k=m['k'], name=m['name'])
            prg.end_group()
    if rami:
        Dm = max(v['D'] for v in rami.values())
        prg.begin_group(SDF.UNION, CLAY['k_gill_D'] * Dm)
        for (r, side), R in sorted(rami.items()):
            prg.sweep(R['P'], R['N'], R['r0'], aspect=R.get('aspect', 1.0), op=SDF.UNION, k=0.0,
                      name=f'ramus_{r}_{side}')
        prg.end_group()
    if eyes:
        cs, rb = eyes
        prg.begin_group(SDF.UNION, 0.0)
        for i, c in enumerate(cs):
            prg.ellipsoid(c, (rb, rb, rb), op=SDF.UNION, k=0.0, name=f'eye_{"LR"[i]}')
        prg.end_group()
    if fins:
        prg.begin_group(SDF.UNION, CLAY['k_fin'] * k_m)
        for nm, (V, F, H) in fins.items():
            prg.shell(V, F, H, op=SDF.UNION, k=0.0, maxd=0.02, name=f'fin_{nm}')
        prg.end_group()
    return prg
