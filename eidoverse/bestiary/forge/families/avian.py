"""The AVIAN family (HAWK_PLAN.md §4.1, §7): the rest chain, the 149-joint skeleton, the wing-fold coupling and the
flight-feather layout (each feather's insertion and tip, fitted to the measured planform).

LIFE MILLIMETRES in the chain; the skeleton in metres (scale_m 1e-3). THE PLAN FRAME: +z forward, +y up, +x the bird's
LEFT; the origin at the hips' midpoint on the ground plane's normal (y = 0 is the ground: the chain is shifted so the
lowest toe pad touches it).

HOW THE BIND POSE IS BUILT (the lead's call: the wings extended, the folded perch a pose):
  1. the trunk, wings and tail in the FLIGHT attitude (body axis along +z), the wing in the body's dorsal plane;
  2. that frame pitched nose-up by rest.perch_axis (60 deg, plan §2.7) about the hips' axis;
  3. the legs, the neck's S-curve and the head in the world (the head held level, the toes flat on the ground).
THE WING AT THE BIND is the Beaty preps' planform (hawk/d1_work/wing/outlines.json, mean_both), the arm nearly straight
(humerus WING_ANG['humerus'] deg aft of the span axis, forearm forward, hand along it): the planform the D1.4 gate
compares against. The glide's swept hand (c049) is a pose (`sweep`).
THE GLENOID sits at x = GLENOID[0]; the prep's root cut is taken at the glenoid (outline x = 0).

FEATHERS (plan §5.2): P1-P10 insert along the carpometacarpus and digit II (P1 at the wrist, P10 at the digit tip),
S1-S13 along the ulna (S1 at the wrist), T1-T3 on the humerus' distal third, A1-A4 on the alular digit at the wrist;
R1-R6 (central to outer) round the pygostyle. Each primary and secondary TIP lies on the mean outline: P8 (the longest,
SPEC wing.longest_primary) at the tip, P9 and P10 along the leading edge, P7-P1 then S1-S13 along the trailing edge at
stated arc steps (PRIM_ARC, measured on B015440 by eye), the secondaries evenly in span between P1's tip and the root.

THE FOLD (plan §7.3): one scalar fold in [0, 1] (0 = the bind, 1 = perched) drives the shoulder's swing (the humerus
back along the body), the elbow's flexion e = fold * ELBOW_MAX and the wrist's w = K_WRIST * e (the radius sliding on
the ulna couples them); `spread` fans the primaries (1 = as bound, 0 = stacked on the hand axis) and the secondaries
close with the elbow. pose(sk, fold, spread, sweep) returns the local rotations for rig.Skeleton.posed_world.
"""
import numpy as np

from .. import rig as RG

GLENOID = (24.0, 22.0, 72.0)          # [E] half the sternum width + the coracoid's offset; 72 mm before the hips
HIP = (16.0, 0.0, 0.0)                # [E] half the pelvis width (34.1) less the acetabular rim
PELVIS_SPAN = (27.0, -40.0)           # [E] the synsacrum's front and back z (67 mm, the acetabulum 40 % from the front)
WING_ANG = dict(humerus=-10.0, forearm=8.0, hand=-10.0, digit2=-14.0)   # deg from the span axis, + = forward [E]
# D1b: the hand follows the mean LE aft past the wrist (the LE drops from y 7.4 at the wrist to 27.6 at x 315): fitted
# so the cmc end sits 5.0 mm and the digit tip 3.9 mm aft of the LE (hand 0 / digit -3 left them 7 / 11 mm PROUD of
# the skin edge, and the P6-P10 bases with them: D1.4's outline residual at x 300-330)
WRIST_AFT_OF_LE = 6.0                 # [E] the wrist joint sits 6 mm aft of the propatagium's edge
PREP_ROOT_MEDIAL = 27.0               # [M-d0 from E] the prep's root cut lies 27 mm medial of the glenoid (it keeps
#                                       scapular / body skin): so B015440's wrist-to-tip (326 mm, wrist by eye) closes
#                                       on the straight arm; the arm alone (humerus + ulna 203 mm) cannot reach it
PRIM_ARC = dict(P10=44.0, P9=20.0, P8=0.0, P7=18.0, P6=40.0, P5=70.0, P4=100.0, P3=128.0, P2=155.0, P1=180.0)
# D1.3: P10 58 -> 44 [D-d13 between M-d0 and the mean]: B015440's tips (d1_notes, mm on the photo) put P10 37 mm of tip
# chord from P8 (21 + 16); at 58 P10 ended at x 491 and P9's notched outer margin stood 9 mm aft of the mean LE past it
# (hand LE p95 7.2). Swept 58..40 with P9 16..22 (scratchpad hawk_p10arc.py): 44 / 20 is the least hand LE (4.3 / 4.0)
# with all four slots open; 40-42 or P9 18 / 22 close the P8/P9 slot
P_INS_FWD = {10: 4.0}                 # [E, D1.3] mm the calamus sits forward of the bone's axis: P10 seats on digit II's
#                                       LEADING side (the bone's half depth + skin), not on its axis. On the axis (3.9 mm
#                                       inside the LE) P10's outer margin ran 4 mm aft of the mean LE from x 330 to 410,
#                                       the hand's LE past the covert band (feather-made edges p95 6.7 mm, D1b check)
LEG_ANG = dict(femur=-30.0, tibiotarsus=-130.0, tarsometatarsus=-80.0)   # deg in the sagittal plane from +z [E]
TOE = dict(hallux=(0.65, 180.0, 28.0), d2=(0.80, -25.0, 25.0), d3=(1.00, 8.0, 20.0), d4=(0.80, 40.0, 17.0))
# toe: (length / middle toe, plan yaw from +z toward +x (the outside), claw length mm) [E: c003, plan §2.5]
PAD = 6.0                             # [E] the toe's underside below the phalanx joints
# the fold [D-d1 from E]: the humerus' folded frame (deg out from the body axis, down, the normal's tilt up from
# lateral) and the elbow / wrist ranges, fitted on a grid to c022's folded primary-tip share 0.893 (against the tail on
# the body axis) with the folded tips and wrist inside the plumage's half width and the tips on the dorsal side
HUM_FOLD = (5.0, 10.0, 20.0)
ELBOW_MAX, K_WRIST = 150.0, 1.083
FOLD_STAGE = 0.6                      # [D-d1b] the staged fold: stage A (fold in the wing's plane) ends here, stage B
#                                       (the roll onto the flank) runs to 1; each smoothstepped (pose(), _stages())
FOLD_LIFT = 15.0                      # [E, D1b] deg the wing is raised over the back during stage A
FOLD_OUT_A = 12.0                     # [E, D1b] deg wider than HUM_FOLD's out angle at stage A's end (at HUM_FOLD's 5
#                                       the left and right P8 tips crossed the midline by 24 mm over the tail)
# D1b: K 1.15 took D1.1's hand (8 deg off the forearm at rest) to 180.5 deg folded; the D1b hand rests 18 deg off it,
# so K = (180.5 - 18) / 150 keeps the same folded hand (1.15 over-folded it 10 deg: tips 56-92 mm dorsal)
NECK_CHORD = 62.0                     # [E] neck base to the occipital condyle in the perch's S
TAIL_LIFT = 20.0                      # [E] deg the tail is raised on the body axis at the bind (the toes stand on
#                                       ground, not a perch: c022's tail hangs below its perch, 0.443 of nape-perch)
# caudal_0, caudal_1, pygostyle (flight frame) [E]: the synsacrum ends about 40 mm behind the acetabulum, then six free
# caudals (about 7 mm each, grouped in two joints) and the pygostyle (D1.1: a 62 mm tail root put the folded
# primaries past the tail tip for every fold)
TAIL_JOINTS = ((0.0, 5.0, -42.0), (0.0, 7.0, -64.0), (0.0, 9.0, -86.0))
JUVENILE_TAIL = 1.08                  # plan §2.8 [E]: a juvenile's tail about 8 % longer (c022 is a juvenile)
EYE_BACK = (0.0, 0.348, -3.176)       # [M-pl from E] mm (world): the GLOBE's centre (the eye joint, P['eye_L']) from
#                                       c018's eye_c (P['eye_c_L']: the plan's §2.4 eye centre, 46.4 mm from the bill
#                                       tip, the face frame's anchor). eye_c is the VISIBLE eye's centre in a lateral
#                                       photo; on the 65 deg axis the iris (SPEC eye 22.5, iris 11.7: its plane 9.61 mm
#                                       out from the centre) stands 4.06 mm forward of the globe's centre, so with the
#                                       globe ON eye_c the clay's pupil landed 3.1 mm forward of c018's at the build's
#                                       own camera (the D1.3c check). Moved back so the iris centre lands on c018's
#                                       pupil (882, 496) at heads/raptor.face_frame's camera (D1.3c fix 1, scratchpad
#                                       f01_globe.py; raptor.face_frame prints the registration). The face, its scale
#                                       and the beak's rings stay on eye_c: unchanged


def _u(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def mirror_point(p):
    p = np.array(p, np.float64)
    p[0] = -p[0]
    return p


def rot_x(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rot_axis(axis, deg):
    a = _u(axis)
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def load_outline(path):
    """the mean planform: x (mm from the root), le, te (mm aft of the LE's most forward point)"""
    import json
    o = json.load(open(path, encoding='utf-8'))['mean_both']
    x = np.linspace(0.0, o['L_mm'], len(o['le']))
    return dict(x=x, le=np.array(o['le']), te=np.array(o['te']), L=float(o['L_mm']))


def outline_polygon(ol):
    """the closed planform polygon (x, y): the LE root -> tip, then the TE tip -> root"""
    return np.concatenate([np.stack([ol['x'], ol['le']], 1), np.stack([ol['x'][::-1], ol['te'][::-1]], 1)])


def _walk(poly, start, arc, direction):
    """the point at arc length `arc` from vertex `start` along the polygon (direction +1 / -1)"""
    n = len(poly)
    i, left = start, arc
    while True:
        j = (i + direction) % n
        seg = np.linalg.norm(poly[j] - poly[i])
        if seg >= left or seg == 0 and left == 0:
            return poly[i] + (poly[j] - poly[i]) * (left / max(seg, 1e-12))
        left -= seg
        i = j


def wing_plane(spec, ol):
    """the wing's 2D skeleton (u span outward, v forward; the glenoid at the origin) and the outline frame's offset:
    returns dict(pts={name: (u, v)}, y_g (the glenoid's outline y), to_uv (outline (x, y) -> (u, v)))"""
    b = spec['bones']
    d = lambda a: np.array([np.cos(np.radians(a)), np.sin(np.radians(a))])
    P = {'shoulder': np.zeros(2)}
    P['elbow'] = P['shoulder'] + b['humerus'] * d(WING_ANG['humerus'])
    P['wrist'] = P['elbow'] + b['ulna'] * d(WING_ANG['forearm'])
    P['cmc_end'] = P['wrist'] + b['carpometacarpus'] * d(WING_ANG['hand'])
    P['digit_tip'] = P['cmc_end'] + b['digit2'] * d(WING_ANG['digit2'])
    x0 = PREP_ROOT_MEDIAL                                     # the glenoid sits at outline x = x0
    le_w = np.interp(P['wrist'][0] + x0, ol['x'], ol['le'])
    y_g = le_w + WRIST_AFT_OF_LE + P['wrist'][1]                # y = y_g - v at the wrist
    return dict(pts=P, y_g=y_g, x0=x0, to_uv=lambda xy: np.array([xy[0] - x0, y_g - xy[1]]),
                to_xy=lambda uv: np.array([uv[0] + x0, y_g - uv[1]]))


def feather_layout(spec, ol, wp):
    """per flight feather: insertion and tip (u, v) in the wing plane, its group and index (module docstring)"""
    P, to_uv = wp['pts'], wp['to_uv']
    poly = outline_polygon(ol)
    n_le = len(ol['x'])
    tip_i = n_le - 1                                          # the LE's last vertex = the tip
    F = {}
    w = spec['wing']
    # primaries: insertions evenly from the wrist (P1) over the cmc to the digit tip (P10)
    hand = [P['wrist'], P['cmc_end'], P['digit_tip']]
    seg = [np.linalg.norm(hand[1] - hand[0]), np.linalg.norm(hand[2] - hand[1])]
    tot = sum(seg)
    for k in range(1, w['n_primary'] + 1):
        s = (k - 1) / (w['n_primary'] - 1) * tot * 0.96 + 0.02 * tot
        ins = hand[0] + (hand[1] - hand[0]) * (s / seg[0]) if s <= seg[0] else \
            hand[1] + (hand[2] - hand[1]) * ((s - seg[0]) / seg[1])
        ins = ins + np.array([0.0, P_INS_FWD.get(k, 0.0)])     # v = forward
        arc = PRIM_ARC[f'P{k}']
        if k > w['longest_primary']:
            tip = _walk(poly, tip_i, arc, -1)                    # back along the LE
        else:
            tip = _walk(poly, tip_i, arc, +1)                    # forward along the TE
        F[f'P{k}'] = dict(group='primary', index=k, ins=ins, tip=to_uv(tip))
    # secondaries: insertions along the ulna (S1 at the wrist), tips on the TE evenly in span
    x0 = wp['x0']
    p1x = F['P1']['tip'][0] + x0                              # outline x
    for k in range(1, w['n_secondary'] + 1):
        t = (k - 0.5) / w['n_secondary']
        ins = P['wrist'] + (P['elbow'] - P['wrist']) * (0.04 + 0.94 * t)
        x_tip = p1x - (p1x - (0.30 * P['elbow'][0] + x0)) * (k / (w['n_secondary'] + 0.6))
        F[f'S{k}'] = dict(group='secondary', index=k, ins=ins,
                          tip=to_uv((x_tip, np.interp(x_tip, ol['x'], ol['te']))))
    # tertials on the humerus' distal third, tips at the root's trailing edge
    for k in range(1, w['n_tertial'] + 1):
        ins = P['elbow'] + (P['shoulder'] - P['elbow']) * (0.12 + 0.12 * k)
        x_tip = 75.0 - 15.0 * k                               # T1 (beside S13) at outline x 60, T3 at 30 [E: D1.4]
        F[f'T{k}'] = dict(group='tertial', index=k, ins=ins, tip=to_uv((x_tip, np.interp(x_tip, ol['x'], ol['te']))))
    # alula: on the alular digit at the wrist's distal end; each tip ON the outline, 3 + k mm aft of the leading edge
    # (D1.4: straight tips stood out past the LE, which curves aft beyond the wrist)
    for k in range(1, w['n_alula'] + 1):
        ins = P['wrist'] + np.array([4.0 + 2.0 * k, 2.0 - 0.8 * k])
        x_t = ins[0] + x0 + 22.0 + 9.0 * k
        F[f'A{k}'] = dict(group='alula', index=k, ins=ins,
                          tip=to_uv((x_t, np.interp(x_t, ol['x'], ol['le']) + 3.0 + k)))
    for f in F.values():
        f['length'] = float(np.linalg.norm(f['tip'] - f['ins']))
    _seat_cards(spec, ol, wp, F)
    return F


def _stages(fold):
    """the staged fold's two smoothstepped parameters (a: the in-plane fold, b: the roll onto the flank)"""
    sm = lambda v: float(np.clip(v, 0.0, 1.0)) ** 2 * (3.0 - 2.0 * float(np.clip(v, 0.0, 1.0)))
    return sm(fold / FOLD_STAGE), sm((fold - FOLD_STAGE) / (1.0 - FOLD_STAGE))


def _outline_sd(ol, pts):
    """signed distance (mm) of outline-frame points to the planform's edge: + outside, - inside"""
    poly = outline_polygon(ol)
    a, b = poly, np.roll(poly, -1, 0)
    ab = b - a
    t = np.clip(np.einsum('psk,sk->ps', pts[:, None, :] - a[None], ab) / np.maximum((ab * ab).sum(1), 1e-12), 0.0, 1.0)
    q = a[None] + t[..., None] * ab[None]
    dist = np.sqrt(((pts[:, None, :] - q) ** 2).sum(-1)).min(1)
    x, y = pts[:, 0], pts[:, 1]
    inside = (x >= 0) & (x <= ol['L']) & (y >= np.interp(x, ol['x'], ol['le'])) & (y <= np.interp(x, ol['x'], ol['te']))
    return np.where(inside, -dist, dist)


def _seat_cards(spec, ol, wp, F):
    """D1b: seat each primary and secondary CARD in the outline, not only its rachis tip. With the tip on the edge a
    card's vane stands past it where the feather meets the edge obliquely (P5 / P6's inner vanes 4-6 mm past the
    TE, P10's blunt outer margin 1-2 mm past the LE, which pinned its bow). Each feather is shortened along its own
    axis (scale 0.92 .. 1.0, step 0.0025) to the length that minimises max(the card's overshoot, the rachis tip's
    gap inside the edge). The leading-edge primaries (P9, P10) also get their bow (fit_le_bow; P9 under P10's
    inner margin), fitted before and after the seat. Sets f['bow'] (None = the class default) and f['seat']."""
    from . import avian_feathers as AF
    to_xy, to_uv = wp['to_xy'], wp['to_uv']
    w = spec['wing']
    lp, first = w['longest_primary'], w['emarginated_first']
    em = lambda f: f['group'] == 'primary' and f['index'] >= first

    def card_xy(f, tip_xy, bow):
        poly, prof = AF.outline(f['group'], float(np.linalg.norm(tip_xy - to_xy(f['ins']))), f['index'], em(f),
                                n=96, bow=bow)
        return AF.place(poly, to_xy(f['ins']), tip_xy, -1.0), prof

    def fit_bow(n):
        f = F[n]
        nb = f'P{f["index"] + 1}'
        x_from, cover = None, None
        if nb in F:
            g = F[nb]
            x_from = to_xy(g['tip'])[0]
            _, pr = card_xy(g, to_xy(g['tip']), g['bow'])
            q = AF.place(np.stack([pr['s'], pr['w_in']], 1), to_xy(g['ins']), to_xy(g['tip']), -1.0)
            q = q[np.argsort(q[:, 0])]
            cover = (q[:, 0], q[:, 1])
        f['bow'], f['bow_worst'] = AF.fit_le_bow(f['group'], f['length'], f['index'], em(f), to_xy(f['ins']),
                                                 to_xy(f['tip']), ol['x'], ol['le'], x_from=x_from, cover=cover)

    def seat(n):
        f = F[n]
        ins, tip0 = to_xy(f['ins']), to_xy(f['tip0'])
        best = None
        for sc in np.arange(1.0, 0.9199, -0.0025):
            tip = ins + sc * (tip0 - ins)
            P_, _ = card_xy(f, tip, f['bow'])
            over = max(float(_outline_sd(ol, P_).max()), 0.0)
            gap = max(-float(_outline_sd(ol, tip[None])[0]), 0.0)
            cost = max(over, gap)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, sc, tip, over, gap)
        f['tip'] = to_uv(best[2])
        f['length'] = float(np.linalg.norm(f['tip'] - f['ins']))
        f['seat'] = dict(scale=float(best[1]), over=best[3], gap=best[4])

    order = [n for n in F if F[n]['group'] in ('primary', 'secondary')]
    le = sorted([n for n in order if F[n]['group'] == 'primary' and F[n]['index'] > lp], key=lambda n: -F[n]['index'])
    for n in F:
        F[n]['bow'] = None
        F[n]['tip0'] = F[n]['tip'].copy()
    for n in le:
        fit_bow(n)
    for n in order:
        seat(n)
    for n in le:
        fit_bow(n)


def rest_chain(spec, outline_path):
    """the bind pose (life mm, world): dict(pos, wing (the 2D plane data), feathers, rect, pitch, ground_shift)"""
    ol = load_outline(outline_path)
    wp = wing_plane(spec, ol)
    feathers = feather_layout(spec, ol, wp)
    R = rot_x(-spec['rest']['perch_axis'])                    # flight frame -> world: the nose up
    fw = lambda p: R @ np.asarray(p, np.float64)
    P = {}
    P['pelvis'] = fw((0.0, 0.0, 0.0))
    P['pelvis_tail'] = fw((0.0, 4.0, PELVIS_SPAN[1]))
    P['thorax'] = fw((0.0, 8.0, PELVIS_SPAN[0]))
    P['thorax_end'] = fw((0.0, 28.0, 82.0))
    P['scapula_L'] = fw((10.0, 28.0, 68.0))
    G = np.array(GLENOID)
    wing3 = lambda uv: G + np.array([uv[0], 0.0, uv[1]])      # the wing plane = the body's dorsal plane (flight frame)
    for k, uv in wp['pts'].items():
        P[f'{k}_L'] = fw(wing3(uv))
    P['alula_L'] = fw(wing3(wp['pts']['wrist'] + np.array([3.0, 2.0])))
    P['alula_tip_L'] = fw(wing3(wp['pts']['wrist'] + np.array([14.0, 4.0])))
    fpos = {}
    for n, f in feathers.items():
        fpos[n] = dict(ins=fw(wing3(f['ins'])), tip=fw(wing3(f['tip'])))
    # tail: caudals, pygostyle, rectrices (closed: a 1.5 deg step per pair; the central pair longest)
    for k, p in zip(('caudal_0', 'caudal_1', 'pygostyle'), TAIL_JOINTS):
        P[k] = fw(p)
    py = np.array(TAIL_JOINTS[2])
    rect = {}
    L_t = spec['tail']['length']
    lift = rot_x(TAIL_LIFT)                                   # the tail raised off the ground (-z turns toward +y)
    for i in range(1, spec['tail']['n_rectrix'] // 2 + 1):
        ins = py + np.array([1.5 + 3.0 * (i - 1), 1.0 - 0.6 * i, -4.0])
        yaw = np.radians(1.5 * i)
        L = L_t * (1.0 - 0.012 * (i - 1) ** 1.5)
        tip = ins + L * (lift @ np.array([np.sin(yaw), -0.04, -np.cos(yaw)]))
        rect[f'R{i}'] = dict(ins=fw(ins), tip=fw(tip), length=float(L))
    P['tail_tip_inline'] = fw(py + np.array([0.0, 0.0, -4.0 - L_t]))   # the closed tail on the body axis
    P['tail_tip_inline_juv'] = fw(py + np.array([0.0, 0.0, -4.0 - JUVENILE_TAIL * L_t]))   # c022's (a juvenile)
    # neck and head in the world: the base on the thorax's front, an S to the condyle, the head level
    base = fw((0.0, 30.0, 84.0))
    ax = R @ np.array([0.0, 0.0, 1.0])
    condyle = base + NECK_CHORD * _u([0.0, 0.93, 0.37])
    c1 = base + 0.45 * NECK_CHORD * ax
    c2 = condyle + 0.40 * NECK_CHORD * np.array([0.0, -0.75, -0.66])
    nj = spec['body']['neck_joints']
    for i in range(nj + 1):
        t = i / nj
        q = (1 - t) ** 3 * base + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t ** 2 * c2 + t ** 3 * condyle
        P[f'neck_{i}' if i < nj else 'head'] = q
    H = P['head']
    hd = spec['head']
    sk = spec['bones']['skull']
    # plan §2.4: the eye centre 46.4 mm from the bill tip, the DISTANCE (D1.3: D1.1 took 46.4 along z alone, with the
    # eye 17 mm above the tip that put it 49.4 mm away: 3 mm off c018's scale, which heads/raptor.py builds the face on)
    eye_z = sk - 8.0 - float(np.sqrt(46.4 ** 2 - 17.0 ** 2))
    P['occiput'] = H + np.array([0.0, 4.0, -8.0])
    P['bill_tip'] = H + np.array([0.0, -14.0, sk - 8.0])
    P['jaw'] = H + np.array([0.0, -10.0, 8.0])
    P['jaw_tip'] = P['bill_tip'] + np.array([0.0, 4.0, -hd['hook_overhang']])
    P['upper_bill'] = H + np.array([0.0, 8.0, sk - 8.0 - hd['culmen'] - hd['cere'] - 3.0])
    P['eye_c_L'] = H + np.array([13.0, 3.0, eye_z])               # c018's eye_c: the face frame's anchor (EYE_BACK)
    P['eye_L'] = P['eye_c_L'] + np.array(EYE_BACK)                  # the globe's centre: the eye joint
    P['eye_dir_L'] = np.array([np.sin(np.radians(65.0)), 0.0, np.cos(np.radians(65.0))])
    # legs (sagittal angles in the world, then the toes flat)
    b = spec['bones']
    sag = lambda deg: np.array([0.0, np.sin(np.radians(deg)), np.cos(np.radians(deg))])
    P['femur_L'] = np.array(HIP)
    P['tibiotarsus_L'] = P['femur_L'] + b['femur'] * sag(LEG_ANG['femur'])
    P['tarsometatarsus_L'] = P['tibiotarsus_L'] + b['tibiotarsus'] * sag(LEG_ANG['tibiotarsus'])
    P['foot_L'] = P['tarsometatarsus_L'] + b['tarsometatarsus'] * sag(LEG_ANG['tarsometatarsus'])
    toes = {}
    mt = spec['feet']['middle_toe']
    nph = dict(zip(('hallux', 'd2', 'd3', 'd4'), spec['feet']['phalanges']))
    for t, (frac, yaw, claw) in TOE.items():
        d = np.array([np.sin(np.radians(yaw)), 0.0, np.cos(np.radians(yaw))])
        base_t = P['foot_L'] + np.array([0.0, -2.0, 0.0]) + 4.0 * d
        n = nph[t]
        Lt = frac * mt
        # n joints per toe (one per phalanx), equal shares of the toe; the last (the ungual) carries the talon [E]
        pts = [base_t + Lt * (i / (n - 1)) * d for i in range(n)]
        tip = pts[-1] + claw * 0.55 * d + np.array([0.0, -0.45 * claw * 0.5, 0.0])
        toes[t] = dict(pts=pts, tip=tip, dir=d)
    # shift so the toe pads touch the ground (y = 0)
    low = min(min(p[1] for p in g['pts']) for g in toes.values()) - PAD
    shift = np.array([0.0, -low, 0.0])
    for k in P:
        if not k.startswith('eye_dir'):
            P[k] = P[k] + shift
    for g in toes.values():
        g['pts'] = [p + shift for p in g['pts']]
        g['tip'] = g['tip'] + shift
    for g in list(fpos.values()) + list(rect.values()):
        g['ins'] = g['ins'] + shift
        g['tip'] = g['tip'] + shift
    for k in [k for k in P if k.endswith('_L')]:
        P[k[:-2] + '_R'] = mirror_point(P[k]) if not k.startswith('eye_dir') else mirror_point(P[k])
    return dict(pos=P, wing=wp, outline=ol, feathers=feathers, fpos=fpos, rect=rect, toes=toes, R=R, shift=shift,
                ground_low=low, scale_m=1e-3)


# --------------------------------------------------------------------------------------------- the skeleton
def skeleton(spec, chain):
    """the 149 joints (plan §7.1) as rig.Skeleton in metres; sk.meta[name] = role, side, tip (m), group, layer"""
    s = chain['scale_m']
    P, fpos, rect, toes, R = chain['pos'], chain['fpos'], chain['rect'], chain['toes'], chain['R']
    up_body = R @ np.array([0.0, 1.0, 0.0])                   # the body's dorsal direction in the world
    sk = RG.Skeleton()
    sk.meta = {}

    def add(name, parent, pos, x, up, role, tip=None, **kw):
        x = np.asarray(x, np.float64)
        up = np.asarray(up, np.float64)
        if abs(_u(x) @ _u(up)) > 0.999:
            up = up_body if abs(_u(x) @ up_body) < 0.99 else np.array([1.0, 0.0, 0.0])
        sk.add(name, parent, np.asarray(pos) * s, RG.frame_from(x, up))
        side = 'L' if name.endswith('_L') else ('R' if name.endswith('_R') else '')
        sk.meta[name] = dict(role=role, side=side, parent=parent,
                             tip=None if tip is None else np.asarray(tip) * s, **kw)

    def mirror(names):
        sw = lambda n: n[:-2] + '_R' if (n and n.endswith('_L')) else n
        M = np.diag([-1.0, 1.0, 1.0])
        for n in names:
            m = sk.meta[n]
            W = sk.world[sk.index(n)]
            F = M @ W[:3, :3] @ np.diag([1.0, 1.0, -1.0])     # x and y mirrored, z = x cross y stays right-handed
            sk.add(sw(n), sw(m['parent']), mirror_point(W[:3, 3]), F)
            mm = dict(m)
            mm['side'], mm['parent'] = 'R', sw(m['parent'])
            if m['tip'] is not None:
                mm['tip'] = mirror_point(m['tip'])
            sk.meta[sw(n)] = mm

    lat = np.array([1.0, 0.0, 0.0])
    add('root', None, np.array([0.0, 0.0, P['pelvis'][2]]), [0, 0, 1], [0, 1, 0], 'root')
    add('pelvis', 'root', P['pelvis'], P['pelvis_tail'] - P['pelvis'], up_body, 'pelvis', tip=P['pelvis_tail'])
    add('thorax', 'pelvis', P['thorax'], P['thorax_end'] - P['thorax'], up_body, 'thorax', tip=P['thorax_end'])
    nj = spec['body']['neck_joints']
    for i in range(nj):
        nxt = P[f'neck_{i + 1}'] if i + 1 < nj else P['head']
        add(f'neck_{i}', 'thorax' if i == 0 else f'neck_{i - 1}', P[f'neck_{i}'], nxt - P[f'neck_{i}'], [0, 0, 1],
            'neck')
    add('head', f'neck_{nj - 1}', P['head'], P['bill_tip'] - P['head'], [0, 1, 0], 'head', tip=P['bill_tip'])
    add('jaw', 'head', P['jaw'], P['jaw_tip'] - P['jaw'], [0, 1, 0], 'jaw', tip=P['jaw_tip'])
    add('upper_bill', 'head', P['upper_bill'], P['bill_tip'] - P['upper_bill'], [0, 1, 0], 'upper_bill',
        tip=P['bill_tip'])
    ed = P['eye_dir_L']
    add('eye_L', 'head', P['eye_L'], ed, [0, 1, 0], 'eye', tip=P['eye_L'] + 11.0 * ed)
    for lid, off in (('lid_upper', (0, 4, 0)), ('lid_lower', (0, -4, 0)), ('nictitans', (0, 0, 3))):
        add(f'{lid}_L', 'eye_L', P['eye_L'] + np.array(off), ed, [0, 1, 0], 'lid', tip=P['eye_L'] + 11.5 * ed)
    mirror(['eye_L', 'lid_upper_L', 'lid_lower_L', 'nictitans_L'])
    # tail
    add('caudal_0', 'pelvis', P['caudal_0'], P['caudal_1'] - P['caudal_0'], up_body, 'tail')
    add('caudal_1', 'caudal_0', P['caudal_1'], P['pygostyle'] - P['caudal_1'], up_body, 'tail')
    add('pygostyle', 'caudal_1', P['pygostyle'], P['pygostyle'] - P['caudal_1'], up_body, 'tail')
    rl = []
    for n, r in rect.items():
        add(f'rectrix_{n[1:]}_L', 'pygostyle', r['ins'], r['tip'] - r['ins'], up_body, 'rectrix', tip=r['tip'],
            group='rectrix', index=int(n[1:]), length=r['length'])
        rl.append(f'rectrix_{n[1:]}_L')
    mirror(rl)
    # wing: bones then feathers (each feather rigid on its own joint; layer = the dorsal-to-ventral order, plan §5.2)
    wl = []
    add('scapula_L', 'thorax', P['scapula_L'], P['shoulder_L'] - P['scapula_L'], up_body, 'scapula')
    add('humerus_L', 'scapula_L', P['shoulder_L'], P['elbow_L'] - P['shoulder_L'], up_body, 'humerus',
        tip=P['elbow_L'])
    add('forearm_L', 'humerus_L', P['elbow_L'], P['wrist_L'] - P['elbow_L'], up_body, 'forearm', tip=P['wrist_L'])
    add('forearm_twist_L', 'forearm_L', 0.5 * (P['elbow_L'] + P['wrist_L']), P['wrist_L'] - P['elbow_L'], up_body,
        'forearm_twist')
    add('hand_L', 'forearm_L', P['wrist_L'], P['cmc_end_L'] - P['wrist_L'], up_body, 'hand', tip=P['cmc_end_L'])
    add('alula_L', 'hand_L', P['alula_L'], P['alula_tip_L'] - P['alula_L'], up_body, 'alula', tip=P['alula_tip_L'])
    add('digit2_L', 'hand_L', P['cmc_end_L'], P['digit_tip_L'] - P['cmc_end_L'], up_body, 'digit2',
        tip=P['digit_tip_L'])
    wl += ['scapula_L', 'humerus_L', 'forearm_L', 'forearm_twist_L', 'hand_L', 'alula_L', 'digit2_L']
    feathers = chain['feathers']
    par = dict(primary=lambda f: 'digit2_L' if np.linalg.norm(f['ins'] - chain['wing']['pts']['cmc_end']) < 1e-9 or
               f['ins'][0] > chain['wing']['pts']['cmc_end'][0] else 'hand_L',
               secondary=lambda f: 'forearm_L', tertial=lambda f: 'humerus_L', alula=lambda f: 'alula_L')
    layer = dict(tertial=0, alula=1, secondary=2, primary=3)
    for n, f in feathers.items():
        g = f['group']
        a, t = fpos[n]['ins'], fpos[n]['tip']
        # within a group: each secondary over its outer neighbour; each primary under its inner neighbour (§5.2)
        add(f'{n}_L', par[g](f), a, t - a, up_body, 'feather', tip=t, group=g, index=f['index'],
            length=f['length'], layer=layer[g] * 100 + (f['index'] if g in ('primary', 'alula') else -f['index']))
        wl.append(f'{n}_L')
    mirror(wl)
    # legs and toes
    ll = []
    add('femur_L', 'pelvis', P['femur_L'], P['tibiotarsus_L'] - P['femur_L'], lat, 'femur', tip=P['tibiotarsus_L'])
    add('tibiotarsus_L', 'femur_L', P['tibiotarsus_L'], P['tarsometatarsus_L'] - P['tibiotarsus_L'], lat,
        'tibiotarsus', tip=P['tarsometatarsus_L'])
    add('tarsometatarsus_L', 'tibiotarsus_L', P['tarsometatarsus_L'], P['foot_L'] - P['tarsometatarsus_L'], lat,
        'tarsometatarsus', tip=P['foot_L'])
    ll += ['femur_L', 'tibiotarsus_L', 'tarsometatarsus_L']
    for t, g in toes.items():
        pts = g['pts'] + [g['tip']]
        for i in range(len(g['pts'])):
            nm = f'{t}_{i + 1}_L'
            last = i == len(g['pts']) - 1
            side_ax = np.cross([0, 1, 0], g['dir'])
            add(nm, 'tarsometatarsus_L' if i == 0 else f'{t}_{i}_L', pts[i], pts[i + 1] - pts[i], side_ax,
                'talon' if last else 'toe', tip=g['tip'] if last else None)
            ll.append(nm)
    mirror(ll)
    # IK targets
    add('ik_foot_L', 'root', P['foot_L'], [0, 0, 1], [0, 1, 0], 'ik')
    add('ik_wingtip_L', 'root', fpos['P8']['tip'], [0, 0, 1], [0, 1, 0], 'ik')
    mirror(['ik_foot_L', 'ik_wingtip_L'])
    return sk


# --------------------------------------------------------------------------------------------- the fold
def pose(sk, chain, fold=0.0, spread=1.0, sweep=0.0, side='L'):
    """local rotations {joint index: 3x3} for one wing (and its mirror when side='both'): the coupled fold
    (module docstring). Rotations act about the body's dorsal axis expressed in each joint's rest frame, so the
    fold stays in the wing's plane; sweep (deg) bends the hand back (c049's glide)."""
    up = chain['R'] @ np.array([0.0, 1.0, 0.0])
    sides = ('L', 'R') if side == 'both' else (side,)
    out = {}
    for sd in sides:
        sg = 1.0 if sd == 'L' else -1.0

        def about(name, deg):
            i = sk.index(name)
            Wr = sk.world[i][:3, :3]
            out[i] = rot_axis(Wr.T @ up, sg * deg)

        # THE HUMERUS goes to an explicit folded frame (the rotation from its rest frame, scaled by fold): its axis aft
        # along the body, HUM_FOLD's degrees out and down; the wing's normal (the frame's y) turned to face outward,
        # tilted up. The elbow and wrist then flex about that carried normal, so the folded wing lies in the flank's
        # sagittal plane, its dorsal face out (c022), never across the belly
        body_ax = chain['R'] @ np.array([0.0, 0.0, 1.0])
        lat = np.array([sg, 0.0, 0.0])
        out_d, down_d, tilt_d = (np.radians(a) for a in HUM_FOLD)
        xt = _u(-body_ax * np.cos(out_d) * np.cos(down_d) + lat * np.sin(out_d) - up * np.sin(down_d))
        yt = lat * np.cos(tilt_d) + up * np.sin(tilt_d)
        yt = _u(yt - xt * (yt @ xt))
        T = np.column_stack([xt, yt, np.cross(xt, yt)])
        ih = sk.index(f'humerus_{sd}')
        Wh = sk.world[ih][:3, :3]
        # THE STAGED PATH (D1b; D1.1's single slerp W_h -> T swung the hand forward-ventral through the legs at fold
        # 0.5-0.75). Stage A (fold 0 .. FOLD_STAGE): the humerus swings aft about the body's dorsal normal only, to M
        # (its axis aft, out_d out, in the wing's own plane) while the elbow, wrist and feathers close: the wing folds
        # flat over the back and nothing leaves the dorsal plane. Stage B (FOLD_STAGE .. 1): the closed wing rolls M
        # -> T down onto the flank. fold 1 = D1.1's pose exactly (M @ M^T T = T)
        a, b = _stages(fold)
        oa = out_d + np.radians(FOLD_OUT_A)                   # splayed: the two wings' tips stay apart over the tail
        xm = _u(-body_ax * np.cos(oa) + lat * np.sin(oa))
        x0 = _u(Wh[:, 0] - up * (Wh[:, 0] @ up))
        phi = np.degrees(np.arctan2(np.cross(x0, xm) @ up, x0 @ xm))
        # ... and raised FOLD_LIFT over the back (birds lift the folding wing; on the 60 deg perch axis an aft-pointing
        # flat wing points its primaries down at the ground: D1b measured 23 mm below it at fold 0.45 without the lift)
        def lift(s, xd):                                      # about xd x up: turns xd toward up by FOLD_LIFT * s
            return rot_axis(_u(np.cross(xd, up)), FOLD_LIFT * s)
        xa = rot_axis(up, a * phi) @ Wh[:, 0]
        M = lift(1.0, xm) @ rot_axis(up, phi) @ Wh
        Wa = lift(a, xa) @ rot_axis(up, a * phi) @ Wh
        Rl = M.T @ T
        ang = np.degrees(np.arccos(np.clip((np.trace(Rl) - 1.0) / 2.0, -1.0, 1.0)))
        Wb = Wa
        if ang > 1e-9 and b > 0.0:
            axl = np.array([Rl[2, 1] - Rl[1, 2], Rl[0, 2] - Rl[2, 0], Rl[1, 0] - Rl[0, 1]])
            Wb = M @ rot_axis(axl, b * ang)
        out[ih] = Wh.T @ Wb
        e = a * ELBOW_MAX
        fa = a                                                # the feathers close with stage A (below)
        about(f'forearm_{sd}', -e)                            # the elbow flexes: the forearm turns forward
        about(f'hand_{sd}', +K_WRIST * e + sweep)             # the wrist flexes back (coupled)
        # primaries close toward the hand axis; secondaries toward the forearm axis
        for n, m in sk.meta.items():
            if m.get('role') != 'feather' or m['side'] != sd:
                continue
            i = sk.index(n)
            Wr = sk.world[i][:3, :3]
            pi = sk.parent[i]
            axis_par = sk.world[pi][:3, 0]
            ang = np.degrees(np.arctan2(np.cross(axis_par, Wr[:, 0]) @ up, axis_par @ Wr[:, 0]))
            close = 1.0 - spread * (1.0 - fa) if m['group'] == 'primary' else fa
            # secondaries close ANTI-parallel to the forearm (it points forward when folded, they point aft);
            # primaries, alula and tertials close PARALLEL to their parent (the hand and humerus point aft)
            target = 0.0
            if m['group'] == 'secondary':
                # secondaries point aft-out from the forearm (whose axis points out): fold toward the inward axis
                d = (ang - np.sign(ang) * 175.0) if abs(ang) > 1e-9 else 0.0
                out[i] = rot_axis(Wr.T @ up, -close * d * 0.92)
            else:
                out[i] = rot_axis(Wr.T @ up, -close * (ang - target) * 0.97)
    return out
