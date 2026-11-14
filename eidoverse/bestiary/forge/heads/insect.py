"""INSECT head archetype (BEETLE_PLAN.md §2.3-§2.5, §4.5, §6.1, §6.5): the head's landmarks, placed once for the
skeleton (B1) and for the head block-out (B3 reads the same table: AG 05.4, joint positions from the geometry
builder's own pivot data). The stag beetle is the first (species/stag_beetle.py).

UNITS: LIFE MILLIMETRES (the SPEC's); the family multiplies by the author scale. THE PLAN FRAME: the clypeal tip at
z 0, +z forward, h above the venter's lowest point, +x the creature's left. THE HEAD FRAME: origin the head-prothorax
joint at the neck (z -HL, h SPEC rig.neck_h: plan §6.1); p forward, q dorsal, x left. At the bind the head keeps M1's
attitude (plan §2.7: until a relaxed live side view on flat ground is measured, c04 / l02), so p = +z and q = +y: a
landmark's (p, q) is its plan-frame (z, h) less the neck's. landmarks_pqx(spec) returns the left side and the midline
(names ending _L are mirrored by the family); directions end in _dir or _axis.

MEASURED (SPEC): the frons top, the vertex crest, the head top at and under the eye, the eye centre (M1l, plan §2.3),
the eye spacing and axis (101.3 / 102.5 deg: the head margin's outward normal, their mean for the mirrored rig, plan
§2.4), the mandible bases (M1d's outer bases: the hinge x and z; M1l's dorsal and ventral bases: its h), the pinned
tip's height (M1l), the chords and directions (closed M1, rest P1: plan §2.5), the antenna's lengths (plan §2.4).
ESTIMATED here [E]: the constants below, set on B1's head (REF_HEAD) and scaled by a morph's head (HW, head height,
HL) so B12's heads inherit them; each names the gate that replaces it.

THE MANDIBLE (plan §2.5): dicondylic, so it turns about ONE fixed axis, near dorso-ventral, tilted SPEC
mandible.hinge_tilt top-forward [E-an]. Its pinned closure (M1, the mean of both sides: plan angle `closed`, the tip
at M1l's height) turned about that axis until its plan angle is P1's live `rest` gives the bind: 8.2 deg open in plan
(plan §2.5 "8 on average"). The rig's frame keeps x along the chord (the house convention), so the joint's z is the
axis's part perpendicular to the chord; the true axis rides along as mandible_axis_L for the runtime and B9.
"""
import numpy as np
from scipy.optimize import brentq

REF_HEAD = dict(HW=17.627, head_h_eye=6.722, HL=9.671)   # B1's head, on which the [E] constants were set (SPEC)
CLYPEUS_DROP = 0.68          # [E] the clypeal process's tip (z 0) this far under the mandible's dorsal base (h 14.18):
                             # it projects ~2 mm ahead of the frons top (h 15.29) and slopes down between the bases
                             # (plan §2.4); B3 fits it to M1l's head outline
ANT_SOCKET = (0.9, 1.6, 1.1)  # [E] the antennal socket under the canthus: 0.9 inside the head margin (HW / 2), 1.6
                              # ahead of the eye centre (the eye's front edge is ~1.0 ahead) and 1.1 below it (M1l: "the
                              # scape runs from its socket in front of the eye"); P1 shows the antennae leaving the
                              # head's front corners; gate B3 (the canthus) and B9 (the scape clears the mandible base)
PALP_MAX = ((1.3, -0.6, -0.24), (3.7, 5.2, -1.24))  # [E] the maxillary palp's base and tip: (x, z, h from the
                              # mandible's ventral base, h 9.84); the tip's x and z [D from M-ph]: M1d's maxillary palp
                              # spans x 1.7-3.7 and 0.06-5.25 ahead of the clypeal tip (res_s01a notes: "the jointed rod
                              # between the mandibles"); gate B3's mouthparts
PALP_MID = 0.45              # [E] palp_max_1 this far along the maxillary palp (its middle segments)
PALP_LAB = ((0.7, -1.0, -0.84), (1.5, 1.2, -1.44))  # [E] the labial palp: short, medial, under the maxillae
MOUTH = (-0.4, 0.76)         # [E] socket_mouth on the midline between the mandible bases at the labrum: (z, h from the
                             # ventral base)
HORN = (5.8, -1.6, 0.22)     # [E] socket_horn_L on the head's dorsal front beside the mandible base: (x, z, h from the
                             # dorsal base); socket_horn_mid on the dorsal midline HORN_MID_BACK behind the head top at
                             # the eye, on the line to the vertex crest (plan §6.5)
HORN_MID_BACK = 1.3


def _ref(spec):
    """the morph's head against B1's: (lateral, height, fore-aft) factors for the [E] constants"""
    b = spec['body']
    return (b['HW'] / REF_HEAD['HW'], spec['lateral']['head_h_eye'] / REF_HEAD['head_h_eye'], b['HL'] / REF_HEAD['HL'])


def neck(spec):
    """the head-prothorax joint in the plan frame: (x, h, z)"""
    return np.array([0.0, spec['rig']['neck_h'], -spec['body']['HL']])


def rot(axis, deg):
    """the rotation matrix about a unit axis (right hand, degrees)"""
    k = np.asarray(axis, np.float64) / np.linalg.norm(axis)
    K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    a = np.radians(deg)
    return np.eye(3) + np.sin(a) * K + (1.0 - np.cos(a)) * (K @ K)


def inward(v):
    """a left mandible's plan direction, degrees inward of forward"""
    return float(np.degrees(np.arctan2(-v[0], v[2])))


def mandible(spec):
    """the left mandible in the plan frame (x, h, z): its hinge, the pinned (closed) tip, the bind's tip, the hinge
    axis and the turn about it from closed to the bind (degrees, + opens)"""
    md, lm = spec['mandible'], spec['landmarks']
    hinge = np.array([0.5 * md['base_span'], 0.5 * (lm['mand_base_dors'][1] + lm['mand_base_vent'][1]),
                      -md['base_behind']])
    a = np.radians(md['closed'])
    closed = hinge + np.array([-md['chord'] * np.sin(a), 0.0, md['chord'] * np.cos(a)])
    closed[1] = lm['mand_tip'][1]
    t = np.radians(md['hinge_tilt'])
    axis = np.array([0.0, np.cos(t), np.sin(t)])
    v = closed - hinge
    turn = brentq(lambda d: inward(rot(axis, d) @ v) - md['rest'], 0.0, 45.0, xtol=1e-12)
    return dict(hinge=hinge, closed=closed, rest=hinge + rot(axis, turn) @ v, axis=axis, turn=turn)


def _plan_dir(deg, elev):
    a, e = np.radians(deg), np.radians(elev)
    return np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])


def landmarks_xhz(spec):
    """every landmark in the plan frame: name -> (x, h, z) for points, unit (x, y, z) for directions; the left side
    (names ending _L) and the midline"""
    b, lm, md, an, ey, r = spec['body'], spec['landmarks'], spec['mandible'], spec['antenna'], spec['eye'], spec['rest']
    sx, sh, sz = _ref(spec)
    P = lambda k: np.array([0.0, lm[k][1], lm[k][0]])
    L = dict(neck=neck(spec), frons_top=P('frons_top'), crown=P('head_crest'), head_top_eye=P('head_top_eye'),
             head_under_eye=P('head_under_eye'))
    dors, vent = lm['mand_base_dors'][1], lm['mand_base_vent'][1]
    L['clypeal_tip'] = np.array([0.0, dors - CLYPEUS_DROP * sh, 0.0])
    # the eye: the centre on M1l at the spacing's half; the axis the head margin's outward normal (horizontal)
    L['eye_L'] = np.array([0.5 * ey['spacing'], lm['eye_c'][1], lm['eye_c'][0]])
    L['eye_dir_L'] = _plan_dir(ey['splay'], 0.0)
    L['eyes_bridge'] = np.array([0.0, lm['head_top_eye'][1], lm['eye_c'][0]])
    # the mandible
    m = mandible(spec)
    L['mandible_L'], L['mandible_closed_L'], L['mandible_tip_L'] = m['hinge'], m['closed'], m['rest']
    L['mandible_axis_L'] = m['axis']
    L['mandible_turn'] = m['turn']
    # the antenna at the bind (SPEC rest.antenna_dir / _elev [E]): scape, elbow, pedicel / funicle, club, lamellae
    s0 = np.array([0.5 * b['HW'] - ANT_SOCKET[0] * sx, lm['eye_c'][1] - ANT_SOCKET[2] * sh,
                   lm['eye_c'][0] + ANT_SOCKET[1] * sz])
    d0, d1, d2 = (_plan_dir(r['antenna_dir'][i], r['antenna_elev'][i]) for i in range(3))
    e1 = s0 + an['scape'] * d0
    e2 = e1 + spec['rig']['pedicel_frac'] * an['funicle'] * d1
    e3 = e1 + an['funicle'] * d1
    tip = e3 + an['club'] * d2
    L['antenna_0_L'], L['antenna_1_L'], L['antenna_2_L'], L['antenna_3_L'], L['antenna_tip_L'] = s0, e1, e2, e3, tip
    # the lamellae: plates standing out of the club's FORWARD side (P1's comb), closed at the bind (rest.lamella_fan)
    fwd = np.cross(d2, np.array([0.0, 1.0, 0.0]))
    fwd = -fwd if fwd[2] < 0 else fwd
    fwd = fwd / np.linalg.norm(fwd)
    fan = np.radians(r['lamella_fan'])
    reach = 0.5 * sum(an['lamella_reach'])
    for i, f in enumerate(spec['rig']['lamella_at']):
        base = e3 + f * an['club'] * d2
        dr = np.cos(fan * (i - 1.5) / 1.5) * fwd + np.sin(fan * (i - 1.5) / 1.5) * d2
        L[f'lamella_{i}_L'], L[f'lamella_tip_{i}_L'] = base, base + reach * dr
    # the palps
    pm0 = np.array([PALP_MAX[0][0] * sx, vent + PALP_MAX[0][2] * sh, PALP_MAX[0][1] * sz])
    pmt = np.array([PALP_MAX[1][0] * sx, vent + PALP_MAX[1][2] * sh, PALP_MAX[1][1] * sz])
    L['palp_max_0_L'], L['palp_max_1_L'], L['palp_max_tip_L'] = pm0, pm0 + PALP_MID * (pmt - pm0), pmt
    L['palp_lab_0_L'] = np.array([PALP_LAB[0][0] * sx, vent + PALP_LAB[0][2] * sh, PALP_LAB[0][1] * sz])
    L['palp_lab_tip_L'] = np.array([PALP_LAB[1][0] * sx, vent + PALP_LAB[1][2] * sh, PALP_LAB[1][1] * sz])
    # the head sockets' points (plan §6.5; their frames are B10's)
    L['mouth'] = np.array([0.0, vent + MOUTH[1] * sh, MOUTH[0] * sz])
    L['horn_L'] = np.array([HORN[0] * sx, dors + HORN[2] * sh, HORN[1] * sz])
    te, cr = lm['head_top_eye'], lm['head_crest']
    zm = te[0] - HORN_MID_BACK * sz
    L['horn_mid'] = np.array([0.0, te[1] + (zm - te[0]) / (cr[0] - te[0]) * (cr[1] - te[1]), zm])
    return L


def landmarks_pqx(spec):
    """the landmarks in the HEAD FRAME (module docstring): (p, q, x) relative to the neck for points, (p, q, x) for
    directions; scalars pass through"""
    n = neck(spec)
    out = {}
    for k, v in landmarks_xhz(spec).items():
        if np.isscalar(v):
            out[k] = float(v)
        elif k.endswith('_dir_L') or k.endswith('_axis_L'):
            out[k] = np.array([v[2], v[1], v[0]])
        else:
            out[k] = np.array([v[2] - n[2], v[1] - n[1], v[0] - n[0]])
    return out


def landmarks(spec, origin, p_ax, q_ax):
    """the landmarks in world space for a head joint at `origin` with the head frame's axes p_ax, q_ax (unit, in the
    sagittal plane): name -> np.array(3) (points and unit directions, left side and midline; mirror for _R), plus the
    scalars"""
    X = np.array([1.0, 0.0, 0.0])
    out = {}
    for k, v in landmarks_pqx(spec).items():
        if np.isscalar(v):
            out[k] = float(v)
        elif k.endswith('_dir_L') or k.endswith('_axis_L'):
            out[k] = v[0] * p_ax + v[1] * q_ax + v[2] * X
        else:
            out[k] = np.asarray(origin, np.float64) + v[0] * p_ax + v[1] * q_ax + v[2] * X
    return out


# ============================================================================================ B3: the head's clay
# The head's shells (BEETLE_PLAN §4.2, §4.5): the capsule, two compound eyes, two mandibles, per antenna a scape, a
# funicle and four lamellae, two palps a side. Descriptors in LIFE mm in the world frame (y = h + the venter's
# clearance) for families/arthropod_parts.py, which emits, carves, seats and mirrors them. Built at the bind (the
# head at M1's attitude, plan §2.7); pose 'closed' sets the mandibles at M1's pinned closure (the overlays on M1).
#
# THE CAPSULE (B3c, the lead 10-21): a VOLUME built from the photographs (heads/insect_hull.py: the visual hull of M1d,
# M1l and the rounded sections, the constrained curvature flow, the strokes: the dish, the crest along M1d's arcs, the
# swollen side, the canthus, the supraocular ridge, the orbit round the eye, the clypeal process and the mentum as
# rounded plates) entering the head's program as one GRID member (patches/sdf_grid.md, the staged module). B3b's
# station loft, crest pieces, lip, canthus box, bevels and plates read as a flat-walled box with a ball eye.
EYE_APEX = (8.55, -4.15)       # [M-ph] the dome's outermost point (x, z): SPEC outline.head_half at z -3.5 .. -4.0
EYE_FILLET = 0.18              # [E] the cap's rim rounded, inside the capsule, unseen: it must END below the capsule's
#                                side (the fillet meets the dome at R (yb + rf) / (R - rf) along the axis, under R - proud
#                                for rf <= 0.205): B3's 0.32 reached 0.04 past it, so the exposed outline lay on the
#                                fillet, 2.25 tall at most (M1l 2.365; B3b probe p07). Under SINK the cap shrunk by SINK
#                                has a sharp rim, which is still its exact inward offset (a convex cap's erosion)
EYE_DEEP = 0.45                # [E] B3e: the cap's base plane this much deeper again (the B3e head's ORBIT is carved round
#                                the eye down past B3d's capsule side, so the cap's rim and base stood in the opening: the
#                                exposed vertices fitted a 0.978 mm sphere, residual 745 um, b03 _b3e); the dome is the
#                                SPEC sphere wherever the orbit opens it, the head's socket carve follows it down
SCAPE_R = (0.30, 0.42)         # [E] the scape's radii, base / elbow (club-shaped, plan §2.4)
BEAD_R = (0.30, 0.34)          # [E] a funicle bead's radii; 5 beads (SPEC antenna.n_funicle)
LAMELLA = dict(width=0.90, thick=0.22, stalk=0.24, r=0.10)   # [E] plan_numbers.py's lamella (1.27 x 0.90 x 0.22, the
#                                  reach SPEC antenna.lamella_reach's mean), now a rounded LEAF (B3b), and its stalk
PALP_SEG = ((0.16, 0.22, 0.24, 0.38), (0.30, 0.30, 0.40))   # [C] the maxillary palp's 4 segments, the labial's 3
#                                  (Lucanidae), as shares of each palp's length [E]
PALP_R = ((0.22, 0.20, 0.18, 0.15), (0.18, 0.15, 0.12))     # [E] their radii, base to tip
PALP_BOW = (0.45, 0.30)        # [E] each palp's curve: the mid control point dropped ventrally this far (mm)


HEAD_BUILD = 'subd'            # B3g (the lead, 10-27): the head capsule a CREASED SUBDIVISION SURFACE (heads/insect_cage.py:
#                                one quad cage, its edge loops on the measured feature lines, semi-sharp creases, the limit
#                                mesh's exact distance on the GRID); 'hull': B3c-B3f's visual hull + flow + CSG features
#                                (heads/insect_hull.py, kept for the before / after)


_HV = {}


def head_volume(spec, log=print):
    """the head's GRID volume by HEAD_BUILD (both builders return insect_hull.head_volume's dict). B3h: held once per process
    (the bind and the closed builds share one array: at the B3h head's 0.025 mm each load was 0.5 GB more for b03)"""
    if HEAD_BUILD == 'subd':
        from . import insect_cage as IC
        key = ('subd', IC.head_key(spec))
        if key not in _HV:
            _HV.clear()
            _HV[key] = IC.head_volume(spec, log)
        return _HV[key]
    from . import insect_hull as IH
    return IH.head_volume(spec, log)


def capsule_descs(spec, clear, coarse=False):
    """the head capsule (B3c; the block comment above; B3g: HEAD_BUILD): ONE GRID member, the head volume's sampled
    distance (the plan frame's h shifted up by the venter's clearance), descriptors in life mm. coarse (B3h): every second
    sample (twice the cell), for the uses that never show the head's edges: the pronotum's socket carve (inside its collar)
    and the scape's and palps' seats (arthropod_parts.build_parts)"""
    from ..families import arthropod_parts as AP
    hv = head_volume(spec, log=lambda s: print(s, flush=True))
    lo = np.asarray(hv['lo'], np.float64)
    if coarse:
        return [AP.grid((lo[0], lo[1] + clear, lo[2]), 2.0 * hv['h'], np.ascontiguousarray(hv['values'][::2, ::2, ::2]),
                        name='head capsule (volume, coarse)')]
    return [AP.grid((lo[0], lo[1] + clear, lo[2]), hv['h'], hv['values'], name='head capsule (volume)')]


def eye_descs(spec, clear):
    """the left compound eye: a spherical cap (REVOLVE) on the head margin's outward normal (SPEC eye.splay, the mean
    of both sides), its apex at the measured outline, its base plane SINK inside the capsule's side"""
    from ..families import arthropod_parts as AP
    ey, lm = spec['eye'], spec['landmarks']
    EYE_R = ey['radius']                           # B3b: the SPEC's dome radius (its rule in stag_beetle TAGS)
    a = np.array([np.sin(np.radians(ey['splay'])), 0.0, np.cos(np.radians(ey['splay']))])
    apex = np.array([EYE_APEX[0], lm['eye_c'][1] + clear, EYE_APEX[1]])
    C = apex - EYE_R * a
    proud = ey['sliver'] / a[0]                    # the dome's height over the capsule's side, along its axis
    y_base = EYE_R - proud - AP.SINK - EYE_DEEP

    def profile(grow, R=EYE_R, yb=y_base, rf=EYE_FILLET):
        """the cap's meridian, offset by grow: the base plane, a fillet of radius rf + grow into the dome (a rounded
        rim, so the cap shrunk by SINK is its exact inward offset: a sharp rim would sit sqrt(2) SINK from it), the
        dome to the apex on the axis (the axis closes it)"""
        Rg, yg, fg = R + grow, yb - grow, max(rf + grow, 0.0)
        cy = yg + fg
        cx = np.sqrt(max((Rg - fg) ** 2 - cy ** 2, 1e-12))
        a_s = np.arctan2(cx, cy)                    # the fillet meets the dome along the line from the centre
        out = [[0.0, yg], [cx, yg]]
        if fg > 1e-9:
            t = np.linspace(-0.5 * np.pi, 0.5 * np.pi - a_s, 10)[1:]
            out += [[cx + fg * np.cos(q), cy + fg * np.sin(q)] for q in t]
        ph = np.linspace(a_s, 0.0, 36)[1:]
        out += [[Rg * np.sin(q), Rg * np.cos(q)] for q in ph]
        return np.array(out)
    return [AP.revolve(profile, C, a, name='compound eye')], dict(center=C, axis=a, radius=EYE_R, apex=apex,
                                                                   y_base=y_base)


def mandible_geometry(spec, clear, pose='bind'):
    """the left mandible (B3c, the lead 10-21: a CONVEX BODY; B3b's prisms and shell cutters left a thin slanted plate
    with flat striped walls where M1l shows a thick bar, convex everywhere): world, life mm, at the pose.
      ARM         a PSWEEP along the arm whose section is ONE convex rolled lens (MAND sec: a thick round outer rim
                  high, a thin rounded inner edge low, M1l and P3's end-on bars), standing normal to the arm, each node's
                  centre, width and height SOLVED (_arm_solve) so the lens's outer and inner extreme points lie on M1d's
                  outer edge and the arm's inner edge (SPEC outline.mand_outer; the inner envelope mand_inner, on the
                  broad base M1d's own contour, in the one mirrored mandible's chord frame) and its top and bottom points
                  on M1l's dorsal edge and lower silhouette (the ventral edge, its plunge to the fork's lowest point,
                  the fork's lower edge to the apex), each point where the turned and pitched section puts it
      TEETH       each tooth of M1d's inner contour (its protrusion past the envelope, MAND tooth_min and up) a short
                  PSWEEP from inside the arm's inner edge out past the tooth's tip, its lens thin and rounded, lying at
                  the inner edge's height; the fork's inner TINE a longer one from the arm down to the fork's lowest point
                  on M1l (outline.mand_fork's bottom), its lens rounded (a prong)
      PRISMS      M1d's closed plan outline (outline.mand_plan, teeth and base, the base carried MAND base_back behind
                  under the head's margin) and M1l's closed side outline (outline.mand_dorsal, mand_fork, mand_ventral)
                  extruded; the convex body INTERSECTED SMOOTHLY with both (MAND k_prism): they cut the teeth's and the
                  tine's outlines, the tip and the base; the arm's own silhouettes match M1d's width and M1l's depth
                  (b03 gates both within 0.1 mm), so they barely touch its flanks
    The arm's u runs along the chord (0 the outer base, 1 the tip). At the bind the whole turns about the true hinge
    axis by the turn that opens it to P1's rest (mandible())"""
    from ..families import arthropod_parts as AP
    md, o, lm = spec['mandible'], spec['outline'], spec['landmarks']
    m = mandible(spec)
    hinge = np.array([m['hinge'][0], m['hinge'][1] + clear, m['hinge'][2]])
    L = md['chord']
    a = np.radians(md['closed'])
    t2 = np.array([-np.sin(a), np.cos(a)])                       # (x, z): the plan chord's direction
    n2 = np.array([np.cos(a), np.sin(a)])                        # away from the midline
    B = np.array([hinge[0], hinge[2]])
    plan = lambda uv: B[None, :] + np.outer(uv[:, 0], L * t2) + np.outer(uv[:, 1], L * n2)   # noqa: E731
    # ---- the plan prism's polygon: the base edge (the first straight run, to the inner base's corner) replaced by
    # the hidden base behind it
    UV = np.array(o['mand_plan'], np.float64)
    ic = int(np.argmin(UV[:60, 1]))                              # the inner base's corner
    bk = np.array([np.cos(a), np.sin(a)]) * MAND['base_back'] / L  # back by base_back in plan z, in chord units
    UVp = np.vstack([UV[:1], UV[:1] - bk, UV[ic:ic + 1] - bk, UV[ic:]])
    poly_xz = plan(UVp)
    # ---- the side prism's polygon (z, h): dorsal edge to the tip, fork edge, ventral edge, closed behind the base
    zd, hd = np.array(o['mand_dorsal']).T
    fork = np.array(o['mand_fork'])
    zv, hv = np.array(o['mand_ventral']).T
    keep = zd < fork[0, 0] - 0.05
    dors = np.column_stack([zd[keep], hd[keep]])
    vent = np.vstack([np.column_stack([zv, hv])[::-1], [lm['mand_base_vent'][0], lm['mand_base_vent'][1]],
                      [lm['mand_base_vent'][0] - 1.4, lm['mand_base_vent'][1] + 0.05]])
    zb = MAND['side_back']
    # (B3f: the side prism's top behind the dorsal base follows the base's dive, MAND base_dive, below)
    bd0 = MAND['base_dive']
    zdv = np.linspace(zb, min(bd0['z0'], float(zd[keep][0]) - 0.02), 9)
    udv = np.maximum(bd0['z0'] - zdv, 0.0)
    gdv = np.where(udv < bd0['u0'], udv * udv / (2.0 * bd0['u0']), udv - 0.5 * bd0['u0'])
    dive = np.column_stack([zdv, hd[0] - 0.05 - bd0['slope'] * gdv])
    side = np.vstack([dive, dors, fork, vent, [[zb, vent[-1, 1] + 0.1]]])
    # ---- the arm's edges over u (M1d) and its top / lower silhouette (M1l)
    uo, vo = np.array(o['mand_outer']).T
    ui, vi = np.array(o['mand_inner']).T
    fo, fi = AP.pchip(uo, vo), AP.pchip(ui, vi)
    edge = lambda u, f: B[None, :] + np.outer(u, L * t2) + np.outer(f(u) * L, n2)          # noqa: E731
    fd = AP.pchip(zd, hd)
    Dz = lambda z: fd(np.clip(z, zd.min(), fork[0, 0]))           # noqa: E731
    zv_a = np.concatenate([[lm['mand_base_vent'][0] - 1.4, lm['mand_base_vent'][0]], zv])
    hv_a = np.concatenate([[lm['mand_base_vent'][1] + 0.05, lm['mand_base_vent'][1]], hv])
    Vz = lambda z: np.interp(z, zv_a, hv_a)                        # noqa: E731
    u = np.linspace(MAND['u_arm'][0], MAND['u_arm'][1], MAND['n_arm'])
    O, I = edge(u, fo), edge(u, fi)                               # (n, 2): x, z
    # where M1d's inner contour runs inside the envelope over a broad stretch (the broad base, u 0.12-0.38: no teeth,
    # the arm itself is that wide) the arm follows the contour, smoothed; the teeth further on are protrusions
    UVc = UV[:int(np.argmax(UV[:, 0]))]
    UVc = UVc[(UVc[:, 0] > 0.10) & (UVc[:, 0] < MAND['u_contour'][1] + 0.05)]
    o_ = np.argsort(UVc[:, 0])
    from scipy.ndimage import gaussian_filter1d as _g1
    uc_ = np.linspace(0.10, MAND['u_contour'][1] + 0.04, 200)
    vc_ = _g1(np.interp(uc_, UVc[o_, 0], UVc[o_, 1]), 3.0, mode='nearest')
    vin = fi(u)
    wc_ = np.clip((MAND['u_contour'][1] - u) / (MAND['u_contour'][1] - MAND['u_contour'][0]), 0.0, 1.0)
    vin = np.where(u <= MAND['u_contour'][1], np.minimum(vin, vin + wc_ * (np.interp(u, uc_, vc_) - vin)), vin)
    # behind u_base the contour turns into M1d's base edge: the arm keeps its width there, parallel to the outer edge
    # (a convex BASE LOBE, mandible_descs, fills the broad base to its inner corner; the plan prism trims it); the
    # inner edge smoothed along u (a kink at the switch bent the centreline past the PSWEEP's band check)
    ub_ = MAND['u_base']
    vb_ = float(np.interp(ub_, u, vin))
    vin = np.where(u < ub_, vb_ + (fo(u) - fo(ub_)), vin)
    vin = _g1(vin, MAND['inner_smooth'] / (u[1] - u[0]), mode='nearest')
    # never outside M1d's own contour where the arm follows it (the plan prism, 0.04 mm out, cut flat walls into the
    # inner flank where the smoothed edge stood past it: b03 _b3cq's flat runs at u 0.20 and 0.40)
    raw_ = np.interp(u, UVc[o_, 0], UVc[o_, 1])
    inb_ = (u > 0.10) & (u < MAND['u_contour'][1] + 0.05)
    vin = np.where(inb_, np.maximum(vin, raw_ - MAND['contour_in'] / L), vin)
    # B3d: past inner_hold's u never less inward than M1d's envelope (the smoothing filled its dip at u 0.50), eased in
    uh_, th_ = MAND['inner_hold']
    wh_ = np.clip((u - uh_) / 0.04, 0.0, 1.0)
    vin = np.where(u > uh_, vin + wh_ * (np.minimum(vin, fi(u) + th_) - vin), vin)
    # B3e: the inner edge eased outward by inner_fix (u, mm) where the arm stood wider than M1d's (the width gate's u 0.20
    # +0.102) and its inner flank close enough to the plan prism's grown wall for the smooth intersection to flatten it
    # (the sections gate's flat runs at u 0.20 / 0.40, 0.30-0.32 mm)
    fx_ = np.array(MAND['inner_fix'], np.float64)
    vin = vin + np.interp(u, fx_[:, 0], fx_[:, 1], left=0.0, right=0.0) / L
    I = B[None, :] + np.outer(u, L * t2) + np.outer(vin * L, n2)
    Pic = plan(UV[ic:ic + 1])[0]
    # ---- the side lines the arm answers to: M1l's dorsal edge to the apex, and its lower silhouette: the ventral edge,
    # its plunge to the fork's lowest point, then the fork's lower edge to the apex (the arm's own underside, which
    # descends at up to 60 deg there: B3b's carried depth past the fork's start left the side 0.3-0.7 mm short)
    fk = fork[np.argsort(fork[:, 0])]
    fk = fk[fk[:, 0] > zv_a[-1]]
    zL, hL = np.concatenate([zv_a, fk[:, 0]]), np.concatenate([hv_a, fk[:, 1]])
    Lz = lambda z: np.interp(z, zL, hL)                            # noqa: E731
    # the arm's own underside: between MAND bridge's z the lower line is the TINE's (its plunge to the fork's lowest
    # point, then back up: the tine hangs below the arm there, its own sweep), bridged by a cubic matching both ends'
    # heights and slopes [E]; elsewhere M1l's line (the solve's first try followed the plunge and bent the centreline
    # at 2.5 / mm, past the sweep's band check)
    zb0_, zb1_ = MAND['bridge']
    s0_, s1_ = (Lz(zb0_) - Lz(zb0_ - 0.25)) / 0.25, (Lz(zb1_ + 0.25) - Lz(zb1_)) / 0.25

    def Lz_arm(z):
        z = np.asarray(z, np.float64)
        t = np.clip((z - zb0_) / (zb1_ - zb0_), 0.0, 1.0)
        dz_ = zb1_ - zb0_
        hb = ((2 * t ** 3 - 3 * t ** 2 + 1) * Lz(zb0_) + (t ** 3 - 2 * t ** 2 + t) * dz_ * s0_
              + (-2 * t ** 3 + 3 * t ** 2) * Lz(zb1_) + (t ** 3 - t ** 2) * dz_ * s1_)
        return np.where((z > zb0_) & (z < zb1_), hb, Lz(z))

    fd2 = AP.pchip(np.append(zd[keep], fork[0, 0]), np.append(hd[keep], fork[0, 1]))
    Dz2 = lambda z: fd2(np.clip(z, zd.min(), fork[0, 0]))          # noqa: E731
    # (B3f: the hidden base's DIVE under the front margin is the side prism's alone, MAND base_dive, above: carried into
    # this line, the base's hard smoothing, u_hold, spread it forward and lowered the visible base's top 0.1-0.33 at z 1-5,
    # beetle/scratch_b03f/f08 _m1)
    # ---- the arm's sections SOLVED so each lens touches the four silhouettes at its own extreme points (B3c: the arm
    # turns and pitches; a section normal to it has its top ahead of and its bottom behind its centre by half its
    # height x sin(pitch), over 1 mm on the distal descent, and its edges ride along the arm likewise: placed by the
    # plan alone, the convex body stood up to 0.8 mm past M1l and the side prism cut flat walls into it, probe m01 _np)
    core = lens_section()
    w0 = np.linalg.norm(O - I, axis=1)
    sp_ = MAND['sec']
    zt0 = O[:, 1] + sp_['outer'][0] * (I[:, 1] - O[:, 1])
    zb0 = O[:, 1] + (1.0 - sp_['inner'][0]) * (I[:, 1] - O[:, 1])
    top0, bot0 = Dz2(zt0), Lz_arm(zb0)
    mid2 = 0.5 * (O + I)
    C0 = np.column_stack([mid2[:, 0], 0.5 * (top0 + bot0), mid2[:, 1]])
    uu = np.linspace(max(u[0] - 0.05, -0.2), 1.0, 2400)
    vin_uu = np.interp(uu, u, vin)
    Oq = B[None, :] + np.outer(uu, L * t2) + np.outer(fo(uu) * L, n2)
    Iq = B[None, :] + np.outer(uu, L * t2) + np.outer(vin_uu * L, n2)
    taper = np.clip((u - MAND['u_tip_w']) / max(u[-1] - MAND['u_tip_w'], 1e-6), 0.0, 1.0)
    # the base (inside the head's socket and its deep ventral corner, which the arm's broad sections cannot follow
    # within the band check) smoothed hard, blending to the solve by u_hold[1]
    hold = np.clip((MAND['u_hold'][1] - u) / (MAND['u_hold'][1] - MAND['u_hold'][0]), 0.0, 1.0)
    sol = _arm_solve(C0, w0, top0 - bot0, Oq, Iq, Dz2, Lz_arm, core, MAND['smooth'], O - I, taper, MAND['w_tip'],
                     hold=hold, smooth_hold=MAND['smooth_hold'])
    # the centreline's bends limited for the sweep pieces' band check (the distal knee, where M1l's dorsal edge turns
    # 30 deg within 0.7 mm: the solved curvature x the section's reach reached 1.4)
    rch = 0.5 * np.hypot(sol['W'], sol['H'])
    reach = np.zeros(len(u))
    for u0_, u1_ in MAND['pieces']:
        sel_ = (u >= u0_ - 1e-9) & (u <= u1_ + 1e-9)
        reach[sel_] = np.maximum(reach[sel_], rch[sel_].max())
    Cl = _limit_bend(sol['C'], reach, MAND['bend_limit'])
    sol['bend_shift'] = np.linalg.norm(Cl - sol['C'], axis=1)
    sol['T'], sol['N'], sol['B'] = _arm_frame(Cl, (O - I)[0])
    sol['C'] = Cl
    # where the relaxed centreline lifts a section's top past M1l's dorsal edge (or drops its bottom past the lower
    # line) the section is thinned by the excess instead (the side prism cut a flat top there, u 0.7-0.8, probe m01 _e)
    # (each section's top and bottom POINTS only: thinning to its whole edge, b03 _b3cq, thinned the arm past the distal
    # knee by 0.17-0.22 mm, where the sweep's limited bend cannot follow M1l's dorsal edge, and raised the divisor to 2.2)
    xt_, xb_, _, _ = _lens_extremes(core)
    Wr = sol['W'] - 2 * MAND['rho']
    Hh_ = sol['H'].copy()
    for _ in range(5):                                             # (damped: a thinner section's top stands further
        zt_ = Cl[:, 2] + xt_ * Wr * sol['N'][:, 2] + 0.5 * Hh_ * sol['B'][:, 2]    # back, where the edge is higher)
        zb_ = Cl[:, 2] + xb_ * Wr * sol['N'][:, 2] - 0.5 * Hh_ * sol['B'][:, 2]
        e_t = Cl[:, 1] + 0.5 * Hh_ * sol['B'][:, 1] - Dz2(zt_)
        e_b = Lz_arm(zb_) - (Cl[:, 1] - 0.5 * Hh_ * sol['B'][:, 1])
        Hh_ = Hh_ - 0.6 * 2.0 * np.maximum(np.maximum(e_t, e_b) - MAND['excess_tol'], 0.0) / sol['B'][:, 1]
    from scipy.ndimage import maximum_filter1d
    sol['thinned'] = _gauss_lin(maximum_filter1d(sol['H'] - Hh_, 17), 6.0)    # (gently: a fast change in the
    #                                                                            section's size raises the divisor)
    sol['H'] = sol['H'] - sol['thinned']
    C3 = Cl + np.array([0.0, clear, 0.0])
    nrm, w, dep = sol['N'], sol['W'], sol['H']
    top, bot = sol['top'], sol['bot']                              # (plan h, as M1l's lines)
    Vz = Lz_arm
    scale = np.column_stack([np.maximum(w - 2 * MAND['rho'], 0.1), np.maximum(dep - 2 * MAND['rho'], 0.1)])
    # ---- the teeth: M1d's inner contour's protrusions past the envelope (each a short sweep), the tine a longer one
    # (protrusions past the arm's own inner edge: where it follows M1d's contour, the broad base, nothing protrudes; B3c's
    # first builds measured them past the envelope and made the base's slope two teeth at u 0.25 and 0.29)
    UVi = UV[:int(np.argmax(UV[:, 0])) + 1]
    UVi = UVi[UVi[:, 0] > MAND['tooth_u0']]
    env = np.interp(UVi[:, 0], u, vin)
    pr = (env - UVi[:, 1]) * L
    from scipy.signal import find_peaks
    pk, _ = find_peaks(np.append(pr, -1.0), height=MAND['tooth_min'], distance=3)
    teeth = []
    for p in pk:
        if UVi[p, 0] > MAND['tooth_u1']:
            continue
        # the tooth's base: from its tip along the contour each way while the protrusion falls (to a notch, or a
        # quarter of the tip's): M1d's large tooth has a long proximal side and a short distal one
        j0, j1 = p, p
        lo_ = min(0.35 * pr[p], 0.15)                             # (the large tooth's long proximal side to 0.15 mm)
        while j0 > 0 and lo_ < pr[j0 - 1] <= pr[j0] + 0.02:
            j0 -= 1
        while j1 < len(pr) - 1 and lo_ < pr[j1 + 1] <= pr[j1] + 0.02:
            j1 += 1
        u0_, u1_ = sorted((float(UVi[j0, 0]), float(UVi[j1, 0])))
        base = float(np.clip((u1_ - u0_) * L, 0.35, MAND['tooth_base']))
        ub = float(np.clip(0.5 * (u0_ + u1_), UVi[p, 0] - 0.5 * base / L, UVi[p, 0] + 0.5 * base / L))
        # B3e: the tooth's OUTLINE in plan, level by level (the lead: curved tapering cones whose tips follow M1d's outline
        # by construction): at protrusion levels from the base (the higher of its two flanks' feet) to the peak, the
        # proximal and distal flanks' points where the contour crosses the level, their midpoint (the cone's axis in plan,
        # curved as the outline leans) and half their distance (its half-width)
        lv = []
        base_lv = max(pr[j0], pr[j1])
        for s in np.linspace(0.0, 1.0, MAND['tooth_levels']):
            Ls = base_lv + s * (pr[p] - base_lv)
            pts_ = []
            for rng_ in (range(p, j0 - 1, -1), range(p, j1 + 1)):
                rng_ = list(rng_)
                q_ = None
                for a_i, b_i in zip(rng_[:-1], rng_[1:]):
                    if (pr[a_i] - Ls) * (pr[b_i] - Ls) <= 0 and pr[a_i] != pr[b_i]:
                        w_ = (pr[a_i] - Ls) / (pr[a_i] - pr[b_i])
                        q_ = UVi[a_i] + w_ * (UVi[b_i] - UVi[a_i])
                        break
                pts_.append(UVi[rng_[-1]] if q_ is None else q_)
            Pp, Pd = plan(np.array(pts_))
            lv.append((s, 0.5 * (Pp + Pd), 0.5 * float(np.linalg.norm(Pp - Pd))))
        teeth.append(dict(u=float(UVi[p, 0]), v=float(UVi[p, 1]), protr=float(pr[p]), base=base, u_base=ub, levels=lv,
                          tip=plan(UVi[p:p + 1])[0],
                          tine=bool(abs(UVi[p, 0] - md['fork_frac_LR'][0] * 0.5 - md['fork_frac_LR'][1] * 0.5) < 0.04)))
    R = rot(m['axis'], m['turn']) if pose == 'bind' else np.eye(3)
    tf = lambda p: hinge + (np.asarray(p, np.float64) - hinge) @ R.T   # noqa: E731
    return dict(poly_xz=poly_xz, side=side + np.array([0.0, clear]), hinge=hinge, R=R, tf=tf, axis=m['axis'],
                turn=m['turn'], outer=O, inner=I, u=u, centre=C3, normal=nrm, scale=scale, width=w, depth=dep,
                top=top, bot=bot, teeth=teeth, fork=fork, Dz=Dz2, Vz=Vz, plan=plan, fi=fi, fo=fo, L=L, B=B, t2=t2,
                n2=n2, inner_corner=Pic, vin=vin, sol=sol)


def unit2(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def _lens_extremes(core):
    """the unit lens's top / bottom points' x and its outer / inner points' y"""
    return (float(core[np.argmax(core[:, 1]), 0]), float(core[np.argmin(core[:, 1]), 0]),
            float(core[np.argmax(core[:, 0]), 1]), float(core[np.argmin(core[:, 0]), 1]))


def _line_hits(P0, D, Q, side):
    """for each plan line P0[j] + t D[j] the t where it crosses the polyline Q nearest P0 on the given side (+1: t > 0,
    -1: t < 0); nan where it does not"""
    Tn = np.column_stack([-D[:, 1], D[:, 0]])
    out = np.full(len(P0), np.nan)
    for j in range(len(P0)):
        d = (Q - P0[j]) @ Tn[j]
        s = np.nonzero(np.sign(d[:-1]) != np.sign(d[1:]))[0]
        if not len(s):
            continue
        a = d[s] / (d[s] - d[s + 1])
        X = Q[s] + a[:, None] * (Q[s + 1] - Q[s])
        t = (X - P0[j]) @ D[j]
        t = t[t * side > 0]
        if len(t):
            out[j] = t[np.argmin(np.abs(t))]
    return out


def _gauss_lin(A, sig):
    """Gaussian smoothing along axis 0 with the ends extended linearly (their mean step over 5 nodes): a straight run
    stays straight and the ends stay where they are (padding by the end value pulled the arm's base 2.3 mm out of the
    head's socket under the base's hard smoothing)"""
    from scipy.ndimage import gaussian_filter1d
    A = np.asarray(A, np.float64)
    n, p, m = len(A), int(np.ceil(4.0 * sig)) + 1, min(5, len(A) - 1)
    d0, d1 = (A[m] - A[0]) / m, (A[-1] - A[-1 - m]) / m
    k = np.arange(1, p + 1, dtype=np.float64)
    if A.ndim == 1:
        pre, post = A[0] - k[::-1] * d0, A[-1] + k * d1
    else:
        pre, post = A[0][None] - k[::-1, None] * d0[None], A[-1][None] + k[:, None] * d1[None]
    return gaussian_filter1d(np.concatenate([pre, A, post]), sig, axis=0, mode='nearest')[p:p + n]


def _limit_bend(C, reach, limit, iters=600):
    """the centreline relaxed (Laplacian steps on the nodes around each offender) until its curvature x the reach of
    the sweep piece carrying it stays under `limit` (the PSWEEP band check: H = gam - reach x curv >= 0.2)"""
    C = np.asarray(C, np.float64).copy()
    for _ in range(iters):
        s = np.linalg.norm(np.diff(C, axis=0), axis=1)
        T = np.diff(C, axis=0) / s[:, None]
        kap = np.zeros(len(C))
        kap[1:-1] = np.linalg.norm(T[1:] - T[:-1], axis=1) / (0.5 * (s[1:] + s[:-1]))
        bad = kap * reach > limit
        if not bad.any():
            break
        m = np.convolve(bad.astype(float), np.ones(5), 'same') > 0
        m[0] = m[-1] = False
        lap = np.zeros_like(C)
        lap[1:-1] = 0.5 * (C[:-2] + C[2:]) - C[1:-1]
        C[m] += 0.5 * lap[m]
    return C


def _arm_frame(C, ref):
    """the arm's section frame: T along it, N horizontal and normal to its plan direction (toward the outer edge at
    the first node by ref, then turning continuously: a sign flipped where the edges meet at the tip set a divisor of
    3e5), B = T x N (up-ish)"""
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    tp = T[:, [0, 2]] / np.linalg.norm(T[:, [0, 2]], axis=1, keepdims=True)
    N = np.column_stack([tp[:, 1], np.zeros(len(C)), -tp[:, 0]])
    if N[0, [0, 2]] @ ref < 0:
        N[0] *= -1.0
    for j in range(1, len(C)):
        if N[j] @ N[j - 1] < 0:
            N[j] *= -1.0
    return T, N, np.cross(T, N)


def _arm_solve(C0, W0, H0, Oq, Iq, Dz, Lz, core, smooth, ref, taper, w_tip, hold=None, smooth_hold=2.0, n_iter=7):
    """the arm's centreline (life mm, plan x / z, height h), full widths W and heights H (normal to the arm) such that
    each node's lens (the unit `core` scaled to W - 2 rho by H - 2 rho, then rounded by rho) has its outer and inner
    extreme points on the plan polylines Oq and Iq and its top and bottom points on Dz(z) and Lz(z), each point where
    it actually stands (the frame from _arm_frame), smoothed along the arm by `smooth` mm between rounds (by
    `smooth_hold` mm where `hold` is 1, blended by it); past the taper's start the width blends to w_tip"""
    from scipy.optimize import brentq
    rho = MAND['rho']
    xt, xb, yo, yi = _lens_extremes(core)
    C, W, H = C0.astype(np.float64).copy(), W0.astype(np.float64).copy(), H0.astype(np.float64).copy()
    ds = max(float(np.median(np.linalg.norm(np.diff(C0, axis=0), axis=1))), 1e-6)
    sig, sig_h = smooth / ds, smooth_hold / ds
    hold = np.zeros(len(C)) if hold is None else np.asarray(hold, np.float64)
    ref = np.asarray(ref, np.float64)[0]

    def smooth_all(C, W, H, f=1.0):
        Cs, Ws, Hs = _gauss_lin(C, f * sig), _gauss_lin(W, f * sig), _gauss_lin(H, f * sig)
        if hold.any():
            Ch, Wh, Hh = _gauss_lin(C, sig_h), _gauss_lin(W, sig_h), _gauss_lin(H, sig_h)
            Cs = hold[:, None] * Ch + (1 - hold[:, None]) * Cs
            Ws, Hs = hold * Wh + (1 - hold) * Ws, hold * Hh + (1 - hold) * Hs
        return Cs, Ws, Hs

    for it in range(n_iter):
        C, W, H = smooth_all(C, W, H)
        T, N, Bv = _arm_frame(C, ref)
        Np, Bp, Cp = N[:, [0, 2]], Bv[:, [0, 2]], C[:, [0, 2]]
        t_o = _line_hits(Cp + (yo * (H - 2 * rho))[:, None] * Bp, Np, Oq, +1)
        t_i = _line_hits(Cp + (yi * (H - 2 * rho))[:, None] * Bp, Np, Iq, -1)
        ok = np.isfinite(t_o) & np.isfinite(t_i) & (t_o - t_i > 0.2)
        c = 0.5 * (t_o + t_i)
        C[ok, 0] += c[ok] * Np[ok, 0]
        C[ok, 2] += c[ok] * Np[ok, 1]
        W[ok] = (t_o - t_i)[ok]
        W = W + (w_tip - W) * taper
        for j in range(len(C)):
            zt0 = C[j, 2] + xt * (W[j] - 2 * rho) * N[j, 2]
            zb0 = C[j, 2] + xb * (W[j] - 2 * rho) * N[j, 2]
            f = lambda h: float(Dz(zt0 + 0.5 * h * Bv[j, 2]) - Lz(zb0 - 0.5 * h * Bv[j, 2]) - h * Bv[j, 1])   # noqa: E731
            if f(0.15) > 0 > f(12.0):
                H[j] = brentq(f, 0.15, 12.0, xtol=1e-5)
            C[j, 1] = 0.5 * float(Dz(zt0 + 0.5 * H[j] * Bv[j, 2]) + Lz(zb0 - 0.5 * H[j] * Bv[j, 2]))
    C, W, H = smooth_all(C, W, H, 0.5)
    T, N, Bv = _arm_frame(C, ref)
    top = C[:, 1] + 0.5 * H * Bv[:, 1]
    bot = C[:, 1] - 0.5 * H * Bv[:, 1]
    return dict(C=C, W=W, H=H, N=N, T=T, B=Bv, top=top, bot=bot)


MAND = dict(base_back=1.20,          # [E] the hidden base carried this far behind M1d's base edge (under the margin)
            side_back=-1.60,         # [E] the side prism closed this far back (behind the dorsal base, M1l z -1.10)
            base_dive=dict(z0=-0.95, u0=0.20, slope=1.2),   # [E] B3f: the hidden base's top dives from z0 back (onset
            #                          over u0 mm, then slope): 14.11 at M1l's dorsal base (z -1.10, landmark 14.18), 13.88 at
            #                          z -1.3 and 13.64 at -1.5, under the head's bowl (its inner wall 14.09 at -1.3, the floor
            #                          ~14.0 at the dish's front corners): no cover over the bases (insect_hull FEAT mand_skin)
            u_arm=(-0.06, 0.985), n_arm=150,   # the arm's sweep from inside the head's socket to just short of the tip
            u_contour=(0.33, 0.40),  # the arm's inner edge on M1d's smoothed contour to u 0.33, blending to the
            #                          envelope by 0.40 (the broad base)
            smooth=0.60,             # its centreline and sizes smoothed over this much arc (mm) between the solve's
            #                          rounds (_arm_solve)
            u_hold=(0.08, 0.18), smooth_hold=1.6,   # [E] the base smoothed by smooth_hold mm to u_hold[0], blending
            #                          to the solve by u_hold[1]
            bridge=(9.5, 12.6),      # [E] the arm's underside bridged between these z (the tine's stretch of M1l's
            #                          lower line, B3b's reading: from z ~9.5 it plunges to the tine at 44-73 deg, steeper
            #                          than the arm, whose own section overshot it by 0.1-0.6 mm, probe m01 _np2, b03 _b3cq)
            bend_limit=0.48,         # the centreline's curvature x its piece's reach at most (the band check's 0.8,
            #                          less a margin for its own segment rule and the knee's divisor: 0.62 left 1.69)
            excess_tol=0.03,         # a section's top / bottom past M1l's lines by more than this is thinned (mm)
            band=0.6,                # the arm pieces' PSWEEP band past their reach (mm; the default, the reach again,
            #                          1.0-3.0 mm here, set the knee's divisor 1.7: the meshing's coarse test and the
            #                          gradient gate's samples stand within 0.15 mm of the surface)
            socket_u=0.30,           # the pieces starting before this u carve the head's socket
            vent_base=dict(r=0.55, r_fwd=0.32, back=0.70, len=2.80, low=0.12, x=0.0, k=0.30),   # [E] B3e: the ventral
            #                          (B3f, the lead: the keel blended into the base: NOT achieved, B3e's kept. Tried, f08
            #                          _m1.._m7: blend 0.60 -> |grad| p1 0.585; r 0.80 / 1.60 round cones -> their level
            #                          bottoms cut flat by the side prism where M1l's line climbs 0.6-1.1 mm per mm ahead
            #                          of the corner, a striped plate from below; swept along the line (PSWEEP, tapered,
            #                          shallow or deep sections, blends 0.12-0.30) -> a soft swelling from below but the
            #                          sweep's divisor and the blends held its surface at |grad| 0.49-0.55, p1 0.54-0.60)
            #                          (r_fwd over SINK + 0.02: at 0.28 the keel could not shrink by SINK, so the socket
            #                          group was not carvable and the head took no socket: head~mandible 10.54 at x10, b03
            #                          _b3e)
            #                          base a long low keel: its radius behind and forward, its reach behind the corner and
            #                          forward along the arm, its lowest point over the corner, its offset, its blend
            u_base=0.12,             # behind this the arm keeps its width (the base lobe fills the base)
            inner_smooth=0.025,      # the inner edge smoothed along u by this (chord fractions; at 0.015 the base's
            #                          sections ran away in the solve, a divisor of 10)
            contour_in=0.02,         # and held within this of M1d's contour (mm past it at most) where it follows it
            pieces=((-0.06, 0.20), (0.15, 0.30), (0.25, 0.44), (0.38, 0.62), (0.56, 0.70), (0.65, 0.75), (0.71, 0.80),
                    (0.76, 0.88), (0.83, 0.985)),
            #                          overlapping
            #                          pieces (u): the PSWEEP's
            #                          band check weighs its largest section against its sharpest bend, so the wide base
            #                          and the bent, narrow distal arm ride separate sweeps, identical where they overlap
            u_tip_w=0.93, w_tip=0.50,   # [E] the width narrowing to the tip past u_tip_w (M1d's inner envelope crosses
            #                          the outer edge there: the hook's inner side, an apical tooth below)
            rho=0.05,                # [E] the sections' corner radius
            # the section: a convex ROLLED LENS (lens_section; x outward, y up, before the unit box): the outer rim a
            # circle (x, y, r), the inner edge a small one, the flanks arcs of radius R_top / R_bot touching both (M1l's
            # convex flank; P3's thick rounded bars end-on) [E]
            sec=dict(outer=(0.22, 0.12, 0.30), inner=(-0.40, -0.30, 0.10), R_top=0.64, R_bot=0.58, n=112),
            #                          (R near the least that touches both circles: the flanks' longest run flat
            #                          within 0.004 mm 0.28 mm at the base's 4.0 x 3.7, 0.25 at the arm's 2.9 x 2.4)
            tooth_u0=0.20, tooth_u1=1.0, tooth_min=0.15,   # teeth: M1d's protrusions past the arm's inner edge from
            #                          u tooth_u0 (the apical hook's inner point among them), tooth_min mm and up (B3d
            #                          0.15: M1d's basal denticles too; at 0.25 the clay's inner envelope stood 0.11-0.15
            #                          mm short of M1d's at u 0.50, where they keep M1d's edge inward)
            tooth_base=2.6,          # [E] a tooth's base along the arm at most (B3d: 2.6, BROAD-BASED; B3c 2.0)
            # B3e (the lead: the teeth CURVED TAPERING CONES, horn-like, rounded tips, grown from the inner edge and blended
            # at the base, their tips on M1d's outline BY CONSTRUCTION, no prism shaving them; B3d's straight bars ended in
            # flat vertical faces): the outline sampled at tooth_levels protrusion levels (mandible_geometry), the tip's
            # radius tooth_r (the rounded end reaching M1d's peak; the crest's measured radius class, scratch_b03e/e03), the
            # base sunk tooth_sink into the arm, the half-thickness the half-width (a round cone) up to tooth_bmax at the
            # base, easing to 0.65 of it at the tip's level [E: bmax, sink; M1l shows the teeth no thicker than the arm's
            # lower half]
            tooth_levels=14, tooth_stations=40, tooth_r=0.07, tooth_sink=0.40, tooth_bmax=0.55, tooth_cone_min=0.45,
            tooth_bend=0.30,          # a swept cone's axis bend x (its reach + band) at most (the divisor's share)
            tooth_taper=0.45, tooth_band=0.20,   # a swept cone's half-width falling at most this per mm from its base;
            #                          its PSWEEP band past the reach (life mm: b03's gradient gate samples within 0.15 mm
            #                          of the surface; the default band, the reach again, doubled the bend's share)
            denticle_r=(0.30, 0.10),  # [E] a denticle's base radius at most (the apical hook's inner point, u > 0.95, the
            #                          smaller: the tip is 0.7 mm deep; a 0.55 cone there stood a ball, e08 _m1; 0.16 stood
            #                          0.11 proud of the depth, _m3)
            tooth_lift=0.15,         # [E] a tooth's underside this far over M1l's lower line (B3e 0.10 -> 0.15: the large
            #                          tooth's broad base, tilted with the line at its middle, hung 0.09 under it at z 9.5)
            prism_grow=0.04,         # the prisms' walls grown outward (life mm; B3d: 0.08 left the tip and the fork end
            #                          untrimmed, b03 _b3dq5)
            prism_grow_base=0.12, prism_base_u=0.38,   # B3d: the plan prism grown more over the broad base (mandible_descs)
            #                          (B3e 0.09 -> 0.12: the teeth no longer pass through it, and its smooth intersection
            #                          flattened the broad base's inner flank, the sections gate's u 0.30 / 0.40)
            tine_tip=0.22, tine_bmax=0.62, tine_sink=0.55,   # [E] B3e: the fork's TINE a robust ROUNDED prong (P3), the
            #                          same cone as a tooth along its outline's midline, falling from the arm to the fork's
            #                          lowest point (M1l): its tip's radius, its half-thickness at most, its base's sink
            hook=dict(z_back=10.58, h_low=4.31, r=0.31, r_back=0.18, h_back=4.60, dx=-0.45, len=0.34, k=0.16,
                      blend=1.6),   # [M-ph M1l, B3f] (k 0.12 -> 0.16: _m2's seam ring round the hook, from below; 0.22
            #                          lowered the field's |grad| p1 round the fork, _m3)
            #                          the fork's HOOK (contour_s01c: its rear at z 10.58, its bottom 4.31-4.33 over z
            #                          10.98-11.5, its end's outline a quarter ellipse ~0.45 x 0.42): a round end of radius r
            #                          (its rear and bottom there), dx from the arm's centreline toward its inner side (under
            #                          the arm, inside M1d's silhouette), its axis len forward, blended k; the fork blade starts
            #                          inside it, its path easing onto the centreline over `blend` mm (the band check)
            arm_dense=3,             # B3f: the arm's sweep resampled this many times as densely (no ribbing)
            fork=dict(z=(11.40, 14.95), q=(0.0, 0.22, 1.0), w=(0.50, 0.95, 0.45), t=(0.28, 0.44, 0.20), lift=0.03,
                      r=0.14, k=0.15, stations=120, edge_sigma=0.10),   # (B3f: stations 30 -> 120, the edge smoothed;
            #                          k 0.20 -> 0.15: the fork's wide-angle junctions held the field's |grad| p1 near 0.6)
            #                          [E] the FORK blade along M1l's fork edge (outline.mand_fork) from the tine to
            #                          the tip under the arm's centreline: its width (along x) and half-thickness proximal /
            #                          peak / distal, its underside lift over the edge, its rounding (B3e: a rounded prong,
            #                          rho 0.14, near round; B3d's 0.16-0.40 half-thick at rho 0.02 read as a flat paddle),
            #                          its blend
            inner_fix=((0.10, 0.0), (0.16, 0.035), (0.30, 0.035), (0.36, 0.0)),   # (u, mm) [B3e]
            side_grow=0.062,         # B3e: the SIDE prism's walls grown this far (the plan prism's prism_grow): at 0.04 its
            #                          smooth intersection pressed the arm's underside flat at u 0.30 (0.35 mm, e08 _m12); at
            #                          0.07 it left the arm's low inner edge 0.09 under M1l's lower line at z 9.5 (_m14)
            inner_hold=(0.42, 0.002),   # B3d: past this u the smoothed inner edge never stands less inward than M1d's
            #                          envelope + this (chord fractions): the smoothing filled its dip at u 0.50 (the width
            #                          gate's -0.154)
            k_teeth=0.10, k_tine=0.18, k_prism=0.10)   # [E] the blends (the teeth and the tine into the arm, the prisms:
            #                          B3f: k_tine 0.24 -> 0.18, the fork's low |grad| samples (f08: z 11.5-12.5));
            #                          B3e: the teeth 0.10, the cones' own bases broad: 0.15 widened the flank's flat run at
            #                          the large tooth's root to 0.33, e08 _m4;
            #                          B3d 0.18 / 0.24 / 0.10: the teeth GROW out of the edge (0.24 widened the envelope
            #                          at u 0.65 by 0.11, b03 _b3dq4), the prisms TRIM smoothly; at prism_grow 0.04 a 0.10
            #                          blend shaves the arm's own edge by 0.005 mm)


def _flank_arc(c1, r1, c2, r2, R, side, n=400):
    """the arc of radius R touching the circles (c1, r1) and (c2, r2) from outside them (both inside it), bulging to
    `side` of the line c1 -> c2 (+1 left): its points between the two touching points"""
    d = float(np.linalg.norm(c2 - c1))
    e = (c2 - c1) / d
    nv = np.array([-e[1], e[0]])
    a, b = R - r1, R - r2
    x = (a * a - b * b + d * d) / (2 * d)
    X = c1 + x * e - side * np.sqrt(max(a * a - x * x, 0.0)) * nv
    T1 = X + R * (c1 - X) / np.linalg.norm(c1 - X)
    T2 = X + R * (c2 - X) / np.linalg.norm(c2 - X)
    a1, a2 = np.arctan2(*(T1 - X)[::-1]), np.arctan2(*(T2 - X)[::-1])
    am = np.arctan2(*(0.5 * (T1 + T2) - X)[::-1])
    da = np.angle(np.exp(1j * (a2 - a1)))
    if np.sign(np.angle(np.exp(1j * (am - a1)))) != np.sign(da):
        da = da - np.sign(da) * 2 * np.pi
    t = a1 + np.linspace(0.0, 1.0, n) * da
    return X + R * np.column_stack([np.cos(t), np.sin(t)])


def lens_section(par=None):
    """the arm's unit section (MAND sec): a ROLLED LENS, thick and round at the outer rim (a circle high on the outer
    side), thin but rounded at the inner edge (a small circle low on the inner side), its upper and lower flanks arcs of
    radius R touching both (tangent: no crease, curved everywhere; B3c's first lenses, a hull of end ellipses and arcs
    that bent inward, then a shrinking family, had flanks flat within 0.004 mm over 0.5-0.9 mm, probe m05), normalised
    to the unit box, resampled by arc length and turning, counter-clockwise (x outward, y up, in -0.5 .. 0.5)"""
    from scipy.spatial import ConvexHull
    p = MAND['sec'] if par is None else par
    co, ro = np.array(p['outer'][:2], np.float64), float(p['outer'][2])
    ci, ri = np.array(p['inner'][:2], np.float64), float(p['inner'][2])
    t = np.linspace(0.0, 2.0 * np.pi, 600, endpoint=False)
    circ = lambda c, r: c + r * np.column_stack([np.cos(t), np.sin(t)])     # noqa: E731
    Q = np.vstack([circ(co, ro), circ(ci, ri), _flank_arc(co, ro, ci, ri, p['R_top'], +1.0),
                   _flank_arc(co, ro, ci, ri, p['R_bot'], -1.0)])
    H = Q[ConvexHull(Q).vertices]                                 # (counter-clockwise)
    lo, hi = H.min(0), H.max(0)
    H = (H - 0.5 * (lo + hi)) / (hi - lo)                        # the unit box
    # resampled evenly in arc length plus turning (the narrow end keeps its roundness in few vertices)
    d = np.roll(H, -1, 0) - H
    seg = np.linalg.norm(d, axis=1)
    ang = np.arctan2(d[:, 1], d[:, 0])
    turn = np.abs(np.angle(np.exp(1j * (ang - np.roll(ang, 1)))))
    w = np.concatenate([[0.0], np.cumsum(seg + 0.08 * turn)])
    q = np.linspace(0.0, w[-1], p['n'], endpoint=False)
    Hc = np.vstack([H, H[:1]])
    R = np.column_stack([np.interp(q, w, Hc[:, 0]), np.interp(q, w, Hc[:, 1])])
    if np.sum(R[:, 0] * np.roll(R[:, 1], -1) - np.roll(R[:, 0], -1) * R[:, 1]) < 0:
        R = R[::-1]
    return R


MAND_BUILD = 'subd'            # B3g (the lead's call 2): the mandible ONE creased subdivision cage (heads/insect_mcage.py: the
#                                arm a tube of measured lens rings, the teeth and the hooked tine extrusions of its inner
#                                edge, the keel and the blade its own underside), its GRID; 'sweep': B3c-B3f's sweeps, cones
#                                and prisms (below)


def mandible_descs(spec, clear, pose='bind'):
    """the left mandible (MAND_BUILD): 'subd' ONE GRID member, the cage's limit surface (heads/insect_mcage.py), g['arm']
    the arm alone's grid (b03's section gate); 'sweep' ONE group (arthropod_parts.group, mandible_geometry's docstring):
    the convex arm, its teeth and its tine unioned smoothly, then intersected smoothly with M1d's plan prism and M1l's side
    prism. Returns the descriptors, the geometry (g['socket']: what the head's socket carve takes shrunk by SINK)"""
    from ..families import arthropod_parts as AP
    if MAND_BUILD == 'subd':
        from . import insect_mcage as MC
        G = MC.mandible_grids(spec, clear, pose, log=lambda s: print(s, flush=True))
        h_ = MC.MCAGE['grid_h']
        whole = AP.grid(G['whole_lo'], h_, G['whole_values'], name='mandible (subd cage)')
        g = mandible_geometry(spec, clear, pose)
        g['socket'] = [dict(whole)]
        if 'arm_values' in G:                                      # (the closed pose: b03's section gate)
            g['arm'] = [AP.grid(G['arm_lo'], h_, G['arm_values'], name='mandible arm (subd cage, the arm alone)')]
        g['section'] = lens_section()
        return [AP.group([whole], name='mandible')], g
    g = mandible_geometry(spec, clear, pose)
    R, hinge, tf = g['R'], g['hinge'], g['tf']
    P, side = g['poly_xz'], g['side']
    # the prisms grown outward by prism_grow (their walls stand clear of the arm's own edges, which match M1d and M1l:
    # a smooth intersection on the very edge ate the thin inner edge, B3c probe m02), so they cut what stands out
    # B3d: grown more over the broad base (prism_grow_base to u prism_base_u, easing back by 0.10): where the arm's inner
    # edge hugs M1d's contour within 0.02 mm, the smooth intersection pressed it onto the prism's vertical wall (flat runs
    # of 0.30-0.45 mm at u 0.10-0.30, b03 _b3dq4-6); the distal arm, its teeth and tip keep prism_grow (0.08 there left
    # the tip 0.17 mm wide, _b3dq5)
    P = AP.resample_loop(P, 900)
    up_ = ((P - g['B'][None, :]) @ g['t2']) / g['L']
    gw_ = MAND['prism_grow'] + (MAND['prism_grow_base'] - MAND['prism_grow']) * (
        1.0 - np.clip((up_ - MAND['prism_base_u']) / 0.10, 0.0, 1.0))
    ccw_ = np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]) > 0
    e_ = np.roll(P, -1, axis=0) - P
    ne_ = np.column_stack([e_[:, 1], -e_[:, 0]]) * (1.0 if ccw_ else -1.0)
    ne_ /= np.linalg.norm(ne_, axis=1, keepdims=True)
    nv_ = ne_ + np.roll(ne_, 1, axis=0)
    nv_ /= np.linalg.norm(nv_, axis=1, keepdims=True)
    P = P + gw_[:, None] * nv_
    side = AP.offset_closed(AP.resample_loop(side, 700), MAND['side_grow'])
    y_lo, y_hi = side[:, 1].min() - 1.5, side[:, 1].max() + 1.5
    sec = np.column_stack([P[:, 0] - hinge[0], -(P[:, 1] - hinge[2])])        # (x, -z): N +x, B = +y x +x = -z
    pts = np.array([[hinge[0], y_lo, hinge[2]], [hinge[0], y_hi, hinge[2]]])
    plan_prism = AP.psweep(tf(pts), sec, 0.0, normal=R @ np.array([1.0, 0.0, 0.0]), op=AP.S_.INTERSECT,
                           k=MAND['k_prism'], name='mandible plan prism')
    x_lo, x_hi = P[:, 0].min() - 1.5, P[:, 0].max() + 1.5
    yc, zc = float(side[:, 1].mean()), float(side[:, 0].mean())
    sec2 = np.column_stack([side[:, 1] - yc, side[:, 0] - zc])                 # (y, z): N +y, B = +x x +y = +z
    pts2 = np.array([[x_lo, yc, zc], [x_hi, yc, zc]])
    side_prism = AP.psweep(tf(pts2), sec2, 0.0, normal=R @ np.array([0.0, 1.0, 0.0]), op=AP.S_.INTERSECT,
                           k=MAND['k_prism'], name='mandible side prism')
    core = lens_section()
    arms = []
    # B3f (the lead: no ribbing along the arm, a smooth sweep): the PSWEEP is linear between its stations, so the solved arm
    # (n_arm stations, 0.12 mm apart) printed its station spacing as 5-10 um ribs (the B3e check's r02 high-pass, strongest
    # on the distal arm): its centre, scale and normal resampled MAND arm_dense times as densely along u by cubic splines
    from scipy.interpolate import CubicSpline
    nd_ = MAND['arm_dense']
    u_f = np.linspace(g['u'][0], g['u'][-1], (len(g['u']) - 1) * nd_ + 1)
    C_f = CubicSpline(g['u'], g['centre'], axis=0)(u_f)
    S_f = np.maximum(CubicSpline(g['u'], g['scale'], axis=0)(u_f), 0.1)
    N_f = CubicSpline(g['u'], g['normal'], axis=0)(u_f)
    N_f /= np.linalg.norm(N_f, axis=1, keepdims=True)
    for u0, u1 in MAND['pieces']:
        sel = (u_f >= u0 - 1e-9) & (u_f <= u1 + 1e-9)
        arms.append(dict(AP.psweep(tf(C_f[sel]), core, MAND['rho'], scale=S_f[sel],
                                   normal=N_f[sel] @ R.T, name=f'mandible arm u{u0:.2f}-{u1:.2f}'),
                         band=MAND['band']))
    # (B3c's first builds added a base lobe for the broad base; the arm's inner edge now follows M1d's contour there,
    # and the lobe stood 0.4-0.8 mm below M1l's ventral edge, probe m01 _np.) The VENTRAL BASE: a round lobe whose
    # lowest point is M1l's ventral base corner (landmarks.mand_base_vent) under the arm's centreline there (the base's
    # hard smoothing, which the band check needs, left the arm 0.42 mm above it)
    vb = MAND['vent_base']
    zb_, hb_ = spec['landmarks']['mand_base_vent']
    Cz_ = g['centre'][:, 2]
    # B3e (the lead: the ventral keel's bump under the base gone; B3d's keel, r 0.75 over 2.25 mm, read as an oval bump
    # from below): a LONG LOW keel (an exact round cone: a flattened sweep's fast-shrinking sections set a divisor of 3.65,
    # e08 _m2) along the arm's underside, from inside the head forward, its lowest point `low` over M1l's ventral base
    # corner (landmarks.mand_base_vent: b03's landmark within 0.3), its radii small against the base's width, blended wide
    # (k) so it reads as the base's underside and not a lump
    xb_ = float(np.interp(zb_, Cz_, g['centre'][:, 0])) + vb['x']
    ub_ = np.array([np.interp(zb_, Cz_, np.gradient(g['centre'][:, 0])), 0.0, np.interp(zb_, Cz_, np.gradient(Cz_))])
    ub_ = ub_ / np.linalg.norm(ub_)
    ca_ = np.array([xb_, hb_ + vb['low'] + vb['r'], zb_]) - vb['back'] * ub_
    cf_ = np.array([xb_, hb_ + vb['low'] + vb['r'], zb_]) + vb['len'] * ub_ + np.array([0.0, vb['r'] - vb['r_fwd'], 0.0])
    vlobe = AP.roundcone(tf((ca_ + np.array([0.0, clear, 0.0]))[None])[0], tf((cf_ + np.array([0.0, clear, 0.0]))[None])[0],
                         vb['r'], vb['r_fwd'], k=vb['k'], name='mandible ventral base')
    arms.append(vlobe)
    members = list(arms)
    up = np.array([0.0, 1.0, 0.0])
    # B3e (the lead): the teeth, the tine and the fork blade are added AFTER the prisms (sdf.Program folds a group's members
    # in order: the prisms trim the arm only), so no prism shaves a tip into a flat face; each TOOTH a curved tapering CONE
    # along its outline's midline (mandible_geometry's levels), its half-width the outline's, its half-thickness the same
    # (round) up to tooth_bmax (an ellipse flattened at the broad base), its rounded tip (rho tooth_r) touching M1d's peak,
    # its base sunk tooth_sink into the arm and blended (k_teeth); its underside on M1l's lower line + tooth_lift
    after = []
    for tt in g['teeth']:
        lv = tt['levels']
        s_ = np.array([q_[0] for q_ in lv])
        M2 = np.array([q_[1] for q_ in lv])
        a_ = np.array([q_[2] for q_ in lv])
        rt_ = MAND['tine_tip'] if tt['tine'] else MAND['tooth_r']
        bmax = MAND['tine_bmax'] if tt['tine'] else MAND['tooth_bmax']
        if not tt['tine'] and float(np.linalg.norm(M2[-1] - M2[0])) < MAND['tooth_cone_min']:
            # a DENTICLE (its outline above the higher flank's foot under tooth_cone_min: a neighbour raises one foot):
            # one ROUND CONE (exact, spherical ends) from inside the arm's inner edge at its base to M1d's peak, its tip's
            # rounded end touching the peak
            ub_ = tt['u_base']
            Ie = g['B'] + ub_ * g['L'] * g['t2'] + float(np.interp(ub_, g['u'], g['vin'])) * g['L'] * g['n2']
            Tp = np.asarray(tt['tip'], np.float64)
            d2 = (Tp - Ie) / max(np.linalg.norm(Tp - Ie), 1e-9)
            ra = float(min(0.5 * tt['base'], bmax, MAND['denticle_r'][0] if tt['u'] < 0.95 else MAND['denticle_r'][1]))
            A2 = Ie - MAND['tooth_sink'] * d2
            B2 = Tp - rt_ * d2
            hA = float(g['Vz'](A2[1])) + ra + MAND['tooth_lift']
            hB = float(g['Vz'](B2[1])) + rt_ + MAND['tooth_lift']
            # (lifted by its largest deficit along its length: a straight cone between its ends sagged 0.2 under M1l's
            # lower line where it rises between them, e08 _m6, the depth gate's z 8.0 / 8.5)
            qq = np.linspace(0.0, 1.0, 21)
            zz_ = A2[1] + qq * (B2[1] - A2[1])
            need = g['Vz'](zz_) + (ra + qq * (rt_ - ra)) + MAND['tooth_lift'] - (hA + qq * (hB - hA))
            hA, hB = hA + max(0.0, float(need.max())), hB + max(0.0, float(need.max()))
            A3 = np.array([A2[0], hA + clear, A2[1]])
            B3 = np.array([B2[0], hB + clear, B2[1]])
            tt['axis3'] = np.vstack([tf(A3[None])[0], tf(B3[None])[0]])          # (world: y = h + the clearance)
            after.append(AP.roundcone(tf(A3[None])[0], tf(B3[None])[0], ra, rt_, k=MAND['k_teeth'],
                                      name=f'mandible denticle u{tt["u"]:.3f}'))
            continue
        # the axis ends where the outline's half-width falls to the tip's radius (the rounded end reaches the peak)
        keep = a_ > rt_
        if keep.sum() < 2:
            keep[:2] = True
        last = int(np.nonzero(keep)[0].max())
        if last + 1 < len(a_):                                       # the station where the half-width is the tip's
            w_ = (a_[last] - rt_) / max(a_[last] - a_[last + 1], 1e-9)
            Mt = M2[last] + w_ * (M2[last + 1] - M2[last])
            M2 = np.vstack([M2[:last + 1], Mt[None]])
            a_ = np.append(a_[:last + 1], rt_)
            s_ = np.append(s_[:last + 1], s_[last] + w_ * (s_[last + 1] - s_[last]))
        else:
            M2, a_, s_ = M2[:last + 1], a_[:last + 1], s_[:last + 1]
        # the base carried back into the arm along the tooth's own axis (toward the centreline it would bend the axis
        # sharply on a short tooth: the PSWEEP's band check)
        nin = M2[0] - M2[-1]
        nin /= max(np.linalg.norm(nin), 1e-9)
        sink = MAND['tine_sink'] if tt['tine'] else MAND['tooth_sink']
        M2 = np.vstack([M2[0] + sink * nin, M2[0] + 0.5 * sink * nin, M2])
        a_ = np.concatenate([[a_[0], a_[0]], a_])
        s_ = np.concatenate([[-0.2, -0.1], s_])
        # the axis one smooth curve (a quadratic in arc length, least squares: a horn's single bend; the raw midline turns
        # sharply where the flanks converge, past the PSWEEP's band check), resampled evenly; the sizes along it
        sa = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(M2, axis=0), axis=1))])
        ta = sa / max(sa[-1], 1e-9)
        wfit = np.ones(len(ta))
        wfit[[0, -1]] = 20.0                                         # (the ends held: the sunk base, the tip's station)
        cx_ = np.polyfit(ta, M2[:, 0], 2, w=wfit)
        cz_ = np.polyfit(ta, M2[:, 1], 2, w=wfit)
        tn = np.linspace(0.0, 1.0, MAND['tooth_stations'])
        Mq = np.column_stack([np.polyval(cx_, tn), np.polyval(cz_, tn)])
        # the bend held to tooth_bend / reach (the PSWEEP divides its field by sqrt(1 + (B / (gam - reach curv))^2): the
        # outline's lean at a broad base bent the large tooth's axis to a divisor of 2.38, e08 _m2): the quadratic eased
        # toward the straight chord by lam
        Ml = Mq[0][None, :] + tn[:, None] * (Mq[-1] - Mq[0])[None, :]
        d1x, d1z = np.polyval(np.polyder(cx_), tn), np.polyval(np.polyder(cz_), tn)
        d2x, d2z = np.polyval(np.polyder(cx_, 2), tn), np.polyval(np.polyder(cz_, 2), tn)
        kap = np.abs(d1x * d2z - d1z * d2x) / np.maximum(np.hypot(d1x, d1z) ** 3, 1e-12)
        reach_ = float(a_.max()) + rt_ + MAND['tooth_band']
        lam = float(min(1.0, MAND['tooth_bend'] / max(kap.max() * reach_, 1e-9)))
        M2 = Ml + lam * (Mq - Ml)
        # (B3f, the lead: no banding on the tine cone: its half-width read off the outline's levels by PCHIP, not piecewise
        # linear (B3e's 12 stations, linear between the levels, printed rings); MAND tooth_stations 40)
        from scipy.interpolate import PchipInterpolator
        tu_, iu_ = np.unique(ta, return_index=True)
        a_ = PchipInterpolator(tu_, a_[iu_])(tn)
        s_ = PchipInterpolator(tu_, s_[iu_])(tn)
        # the taper rate-limited from the base (tooth_taper per mm at most: the outline's flanks converge fast at a broad
        # base, a section speed of 0.6-0.8 that set the large tooth's divisor to 2.6, e08 _m3): the cone fuller than the
        # outline only at the base's fillets, which the blend fills anyway
        lt = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(M2, axis=0), axis=1))])
        for i in range(1, len(a_)):
            a_[i] = max(a_[i], a_[i - 1] - MAND['tooth_taper'] * (lt[i] - lt[i - 1]))
        b_ = np.minimum(a_, bmax * (1.0 - 0.35 * np.clip(s_, 0.0, 1.0)))
        b_ = np.maximum(b_, np.minimum(a_, rt_))
        if tt['tine']:
            # the tine from the arm's lower level down to the fork's lowest point (outline.mand_fork's bottom), M1l
            fz = g['fork']
            h0 = float(g['Vz'](M2[0, 1])) + b_[0] + 0.25
            h1 = float(fz[np.argmin(fz[:, 1]), 1]) + rt_
            hq = h0 + (h1 - h0) * np.clip(s_, 0.0, 1.0) ** 1.3
        else:
            hq = g['Vz'](M2[:, 1]) + b_ + MAND['tooth_lift']
        hq_q = np.polyval(np.polyfit(tn, hq, 2, w=np.r_[20.0, np.ones(len(tn) - 2), 20.0]), tn)   # (one smooth bend, its
        hq_l = hq_q[0] + tn * (hq_q[-1] - hq_q[0])                  # ends held: the tip on M1l's lower line), eased as
        hq = hq_l + lam * (hq_q - hq_l)                             # the plan's bend
        if not tt['tine']:
            # never under M1l's lower line + its half-thickness + the lift (a fit between the ends sat 0.2 under the line
            # where it rises in the middle, e08 _m4: the depth gate's z 8.0 / 8.5): the whole axis lifted by the largest
            # deficit (a per-station max kinked the axis past the band check)
            hq = hq + max(0.0, float(np.max(g['Vz'](M2[:, 1]) + b_ + MAND['tooth_lift'] - hq)))
        Pt = np.column_stack([M2[:, 0], hq + clear, M2[:, 1]])
        Tt = np.gradient(Pt, axis=0)
        Tt /= np.linalg.norm(Tt, axis=1, keepdims=True)
        across = np.cross(Tt, up)
        across /= np.linalg.norm(across, axis=1, keepdims=True)    # horizontal, across the tooth (along the arm)
        # (tilted with M1l's lower line along the arm: a broad base's horizontal section hung under the line where it
        # climbs, 0.7 mm per mm at the large tooth's base, e08 _m7, the depth gate's z 8.0 / 8.5)
        sl_ = (g['Vz'](M2[:, 1] + 0.1) - g['Vz'](M2[:, 1] - 0.1)) / 0.2
        across = np.column_stack([across[:, 0], sl_ * across[:, 2], across[:, 2]])
        across /= np.linalg.norm(across, axis=1, keepdims=True)
        sc = np.column_stack([np.maximum(a_ - rt_, 0.003), np.maximum(b_ - rt_, 0.003)])
        tt['axis3'] = tf(Pt)                                          # (world: y = h + the clearance)
        after.append(dict(AP.psweep(tf(Pt), AP.superellipse(32, 2.0), rt_, scale=sc, normal=across @ R.T,
                                    k=MAND['k_tine'] if tt['tine'] else MAND['k_teeth'],
                                    name=f'mandible {"tine" if tt["tine"] else "tooth"} u{tt["u"]:.3f}'),
                          band=MAND['tooth_band']))
    # the FORK blade along M1l's fork edge, from the tine to the tip, under the arm's centreline: a ROUNDED prong (B3e:
    # its section near round, rho fork r; P3's robust prongs), its underside on the edge by construction (after the prisms)
    fb = MAND['fork']
    fz_ = g['fork'][np.argsort(g['fork'][:, 0])]
    # B3f (the lead: the fork ends in ONE hooked tine as M1l shows, no second knob): M1l's own contour (contour_s01c, the
    # stretch from the ventral edge's end to the tine's bottom: beetle/scratch_b03f/f03_m1l_fork.py) hooks BACK under the
    # notch, its rear at z 10.58, its bottom 4.31-4.33 from z 10.98 to 11.5 (the SPEC's fork edge starts at 11.34, so B3e's
    # blade began there with its own rounded end beside the tine cone's: the two knobs). The blade now starts at the HOOK:
    # a round end (MAND hook: radius r, its rear and bottom on M1l's), under the arm's inner part (M1d's silhouette hides
    # it: the arm and its small teeth span x 2.2-4.6 at z 10.5-11.3), the blade carried forward from it along the fork edge
    hk = MAND['hook']
    # (the hook's end a round cone: its rear sphere r_back (its rear on M1l's z 10.58, its bottom rising to it as M1l's
    # end does: 4.42 at z 10.76, 4.57 at 10.61), its front sphere r (its bottom M1l's 4.31-4.33 flat run))
    z_h, h_h = hk['z_back'] + hk['r_back'], hk['h_low'] + hk['r']
    Cc_ = g['centre']
    x_h = float(np.interp(z_h, Cc_[:, 2], Cc_[:, 0])) + hk['dx']
    # (B3f, the lead: no banding along the fork: B3e's blade had 30 stations over 4.5 mm, its sizes linear between the
    # table's nodes and its underside on the raw contour's pixel steps: rings every 0.15 mm on the prong, f08 _m2. Now the
    # path and sizes on a 0.01 mm grid (the sizes by PCHIP, the edge from M1l's contour), the path smoothed over
    # edge_sigma mm along z (C1: a kink between the dense stations is a curvature spike, the PSWEEP's band check), then
    # sampled at fb stations)
    from scipy.interpolate import PchipInterpolator
    from scipy.ndimage import gaussian_filter1d
    zz_ = np.arange(z_h + 0.08 - 0.4, fb['z'][1] + 0.4, 0.01)
    q_ = np.clip((zz_ - fb['z'][0]) / (fb['z'][1] - fb['z'][0]), 0.0, 1.0)
    t_h = np.clip((zz_ - z_h) / hk['blend'], 0.0, 1.0)
    sg_ = fb['edge_sigma'] / 0.01
    path_x = gaussian_filter1d(np.interp(zz_, Cc_[:, 2], Cc_[:, 0]) + hk['dx'] * (1.0 - t_h * t_h * (3.0 - 2.0 * t_h)),
                               sg_, mode='nearest')
    tq_ = gaussian_filter1d(PchipInterpolator(fb['q'], fb['t'])(q_), sg_, mode='nearest')
    wq_ = gaussian_filter1d(PchipInterpolator(fb['q'], fb['w'])(q_), sg_, mode='nearest')
    # (behind the fork edge the blade's underside follows the hook cone's bottom line, M1l's: 4.42 at its rear sphere,
    # 4.31 at its front; level at h_low it hung 0.09 under M1l at z 10.75, f08 _m3)
    edge_ = np.where(zz_ < fz_[0, 0], np.interp(zz_, [z_h, z_h + hk['len']], [hk['h_back'] - hk['r_back'], hk['h_low']]),
                     np.interp(zz_, fz_[:, 0], fz_[:, 1]))
    path_h = gaussian_filter1d(edge_, sg_, mode='nearest') + tq_ + fb['lift']
    zq = np.linspace(z_h + 0.08, fb['z'][1], fb['stations'])
    tq, wq = np.interp(zq, zz_, tq_), np.interp(zq, zz_, wq_)
    Pf = np.column_stack([np.interp(zq, zz_, path_x), np.interp(zq, zz_, path_h) + clear, zq])
    hook_a = np.array([x_h, hk['h_back'] + clear, z_h])
    x_b_ = float(np.interp(z_h + hk['len'], zq, Pf[:, 0]))
    hook_b = np.array([x_b_, h_h + clear, z_h + hk['len']])
    after.append(AP.roundcone(tf(hook_a[None])[0], tf(hook_b[None])[0], hk['r_back'], hk['r'], k=hk['k'],
                              name='mandible fork hook'))
    Tf = np.gradient(Pf, axis=0)
    Tf /= np.linalg.norm(Tf, axis=1, keepdims=True)
    Nf = np.cross(np.array([0.0, 1.0, 0.0]), Tf)
    Nf /= np.linalg.norm(Nf, axis=1, keepdims=True)                 # horizontal, across the blade (its width)
    after.append(AP.psweep(tf(Pf), AP.superellipse(32, 2.0), fb['r'],
                           scale=np.column_stack([np.maximum(0.5 * wq - fb['r'], 0.005), np.maximum(tq - fb['r'], 0.005)]),
                           normal=Nf @ R.T, k=fb['k'], name='mandible fork blade'))
    group = AP.group(members + [plan_prism, side_prism] + after, name='mandible')
    # the head's socket: the base pieces within their prisms (the ones that reach into the head; the tip piece's sections
    # cannot shrink by SINK, and one such member left the whole socket uncarved: the head stood 0.8 mm into the base)
    base_arms = [dict(a_) for (u0_, _), a_ in zip(MAND['pieces'], arms) if u0_ < MAND['socket_u']] + [dict(vlobe)]
    g['socket'] = [AP.group(base_arms + [dict(plan_prism), dict(side_prism)], name='mandible socket')]
    g['section'] = core
    return [group], g


def antenna_descs(spec, lm):
    """the left antenna at the bind (landmarks_xhz's joints, world): the scape a round cone from the socket to the
    elbow; the funicle 5 beads; 4 lamellae, each a stalk on the club axis and a plate standing forward (P1's comb).
    Returns {part: descs} and the seating axes"""
    from ..families import arthropod_parts as AP
    s0, e1, e3, tip = lm['antenna_0_L'], lm['antenna_1_L'], lm['antenna_3_L'], lm['antenna_tip_L']
    out = {}
    out['scape'] = [AP.roundcone(s0, e1, SCAPE_R[0], SCAPE_R[1], name='scape')]
    d1 = AP.unit(e3 - e1)
    nb = spec['antenna']['n_funicle']
    Lf = float(np.linalg.norm(e3 - e1))
    beads = []
    for i in range(nb):
        c = e1 + (i + 0.5) / nb * Lf * d1
        h = 0.5 * Lf / nb * 0.62
        beads.append(AP.roundcone(c - h * d1, c + h * d1, BEAD_R[0], BEAD_R[1], k=0.05 if i else 0.0,
                                  name=f'funicle bead {i}'))
    out['funicle'] = beads
    d2 = AP.unit(tip - e3)
    fwd = np.cross(d2, AP.UP)
    fwd = -fwd if fwd[2] < 0 else fwd
    fwd = AP.unit(fwd)
    side = AP.unit(np.cross(d2, fwd))
    reach = 0.5 * sum(spec['antenna']['lamella_reach'])
    club = spec['antenna']['club']
    q = np.linspace(0.0, 1.0, 14)
    wq = LAMELLA['width'] * (0.32 + 0.68 * np.sin(np.pi * q))              # B3b: a rounded LEAF (B3's were cards)
    tq = np.interp(q, [0.0, 1.0], [LAMELLA['thick'], 0.6 * LAMELLA['thick']])
    lr = 0.4 * 0.5 * LAMELLA['thick']
    for k, f in enumerate(spec['rig']['lamella_at']):
        a_k = e3 + f * club * d2
        st = AP.roundcone(a_k - 0.42 * d2, a_k + 0.30 * d2, LAMELLA['stalk'], LAMELLA['stalk'], name=f'lamella {k} stalk')
        Pq = (a_k - 0.05 * fwd)[None, :] + np.outer(0.05 + q * reach, fwd)
        leaf = AP.psweep(Pq, AP.superellipse(24, 2.0), lr, scale=np.column_stack(
            [np.maximum(0.5 * tq - lr, 0.01), np.maximum(0.5 * wq - lr, 0.01)]), normal=np.tile(d2, (len(q), 1)),
            k=0.08, name=f'lamella {k} leaf')
        out[f'lamella_{k}'] = [st, leaf]
    return out, dict(scape=(s0, AP.unit(e1 - s0)), funicle=(e1, d1), club=(e3, d2))


def palp_descs(lm):
    """the left maxillary palp (two segments) and labial palp (one), round cones on landmarks_xhz's joints"""
    a, b, c = lm['palp_max_0_L'], lm['palp_max_1_L'], lm['palp_max_tip_L']
    mx = palp_chain(a, b, c, PALP_SEG[0], PALP_R[0], PALP_BOW[0], 'maxillary palp')
    d, e = lm['palp_lab_0_L'], lm['palp_lab_tip_L']
    lb = palp_chain(d, 0.5 * (d + e), e, PALP_SEG[1], PALP_R[1], PALP_BOW[1], 'labial palp')
    return dict(palp_max=mx, palp_lab=lb)


def palp_chain(a, b, c, segs, radii, bow, name):
    """a SEGMENTED, CURVED palp (B3b; B3's were straight rods): round cones along the quadratic curve from a to c
    through b, its control point then dropped `bow` ventrally, split at the segment shares; each segment widens
    distally (0.78 -> 1 of its radius), joined to the next by a small blend"""
    from ..families import arthropod_parts as AP
    a, b, c = (np.asarray(v, np.float64) for v in (a, b, c))
    q = 2.0 * b - 0.5 * (a + c) + np.array([0.0, -bow, 0.0])
    t = np.linspace(0.0, 1.0, 201)
    C = (1 - t)[:, None] ** 2 * a + 2 * (t * (1 - t))[:, None] * q + t[:, None] ** 2 * c
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    cut = np.concatenate([[0.0], np.cumsum(segs)]) / np.sum(segs) * s[-1]
    pt = lambda x: np.array([np.interp(x, s, C[:, k]) for k in range(3)])   # noqa: E731
    out = []
    for i, r in enumerate(radii):
        p0, p1 = pt(cut[i] + (0.04 if i else 0.0)), pt(cut[i + 1])
        out.append(AP.roundcone(p0, p1, 0.78 * r, r, k=0.03 if i else 0.0, name=f'{name} {i + 1}'))
    return out
