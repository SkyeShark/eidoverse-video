"""OCTOPUS (Octopus vulgaris proportions): the anatomy as an SDF program and, built over it, the designed quad cage.

Orientation at rest on the ground (bind pose): the arm crown is horizontal around the oral disc, the arms lie radially
on the ground. The MANTLE LIES BACK behind the head, nearly level, its dorsal surface up and its apex a little below
the eyes (every live side view: work/bestiary/research/BLOCKOUT_V4_SPEC.md, BODY_PLAN_PHOTOS.md). Pitching a squid's
plan nose-down puts the DORSAL side forward: the eyes stand on the head's top as two turrets and look forward-out
(+Z), and the funnel (siphon) leaves from under the mantle's free margin, its free part turned forward beside the head
on the left flank under the eye (its root is ventral; at rest the free part lies along the head or turns up beside it).
Arms L1..L4 run from front to back on +X (the left), R1..R4 mirror them on -X; at rest they stand on their suckers.

Proportions (adult common octopus, measured from 13 live animals and the literature; ML = the eyes' midpoint to the
mantle's apex, 0.20 m): mantle 0.68 ML wide, 0.57-0.61 ML deep, no neck; head 0.41 ML across the turrets; arms ~4.1 ML
(the live formula 3 = 2 > 4 > 1 is SPEC['arm_pair_len']), 52 mm across at the crown; the web deepest at the sides
(0.49-0.89 ML from the mouth by sector); sessile suckers in two rows, the largest (17 mm) the 16th-17th.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator

from .. import loft, sdf

SPEC = dict(
    ML=0.20,                # mantle length (m): the eyes' midpoint to the apex (Roper & Voss 1983)
    crown_y=0.088,          # the arm crown's height above the ground at rest (the body sits on a tent of arms)
    arm_len=0.82,           # the longest pair's length; each arm's own: arm_length()
    arm_pair_len=(1.0, 1.0, 1.0, 1.0),   # arms 1..4 as shares of arm_len. The live formula is 3 = 2 > 4 > 1 (FAO;
                            # Gleadall 2016's means 0.77-0.83, 0.96-1, 0.96-1, 0.83-0.86 of the longest: arm_len 0.90
                            # with (0.80, 1.00, 1.00, 0.86)); equal at their mean while the sculpt replicates one arm
                            # by rotation and the arms' UVs stack all eight (PLAN: per-pair plans, mirrored stacking)
    arm_r0=0.026,           # arm radius at the crown: 52 mm across (live resting arms 0.4-0.5 mantle widths)
    arm_tip_r=0.0011,
    sucker_d=0.0175,        # the largest sucker's diameter (the 15th-19th; live sucker / arm 0.32-0.41, photo 14)
    crown_r0=0.050,         # the arm bases' ring radius (8 arms 52 mm across need >= 66 mm of circumference radius)
    oral_disc=(0.085, 0.026, 0.085),   # the oral disc ellipsoid's radii under the crown
    web_sector=(0.49, 0.76, 0.89, 0.78, 0.56),   # web depth by sector A..E (A between arms 1, B 1-2, C 2-3, D 3-4, E
                                                  # between arms 4): the mouth to the margin mid-sector, in ML (Guerra
                                                  # 2010 re-aligned, Gleadall means; FAO formula C > D > B > E > A)
    web_side=1.65,          # the ARM TUBE's start (the cage's square first ring, one for all eight arms): this many
                            # mid-sector depths of the deepest web out along the arms (crown v5: the margins meet the
                            # arms by sector, web_reach, all inside it; the stacked arms set keeps its start)
    web_reach=(1.80, 1.55, 1.55, 1.55, 1.80),   # where each sector's margin meets its arms' side lines, in its own
                            # mid-sector depths (A..E; research/CROWN_STUDY.md 2-3: the live deep webs' strip beside the
                            # arm is gone by ~1.55 D_mid, the shallow webs reach an arm's edge by 1.29-1.97 [M b14]; v4's
                            # one common reach put the A web's 3.16 D_mid out, a slot along the dorsal arms)
    web_wall=(3.0, 3.0, 3.0, 3.0, 3.0),   # the margin's U by sector: s = mid + (reach - mid) t^p, t = |2 lam - 1| (a
                            # flat bottom and steep walls: the live deep webs keep within 1.10 D_mid over 0.39-0.44 of
                            # the arm-to-arm angle [M b14]; v4's quarter ellipse spread the climb over the whole sector)
    web_half=(0.0075, 0.0009),   # web half-thickness at the crown, at the margin (the profile between: web_fold)
    web_fold=(0.40, 0.72, 0.0042),   # the web a FLESHY FOLD inside, a membrane outside: full crown thickness out to
                            # u0 of the mid-sector depth from the mouth, the fold gone by u1 (smoothstep), over a
                            # membrane thinning from the third value (at the crown) to the margin's along the column: v4's
                            # own 8.4 -> 1.8 mm line, 4.3 mm through at u1, 2.7 at 0.9 (b14: opaque like the arms to ~0.55
                            # D_mid, light through it beyond [M b14]; v4's line alone made the inner half a sheet; crown
                            # v5's 3.0 -> 1.8 mm membrane, 2.2 mm through at u1, made the outer half thinner than v4's,
                            # a razor-thin taut sheet from the low orbit)
    arm_round=(0.016, 0.006, 0.090, 0.125, 0.0),   # crown v6b (crown v6's): the arms among themselves by the ROUND
                            # union (sdf.ROUND), its radius r_in within d0 of the mouth (the last value: the centre's
                            # offset forward from it), easing (smoothstep) to r_out by d1: under the crown neighbouring
                            # arm roots merge in smooth saddles ~5 mm deep, no crease (c311 / c334: between the dorsal arm
                            # roots a smooth saddle, no internal contour in front views [M c311], [M c334]; the hard union
                            # creased there, L1 | R1 the front midline, and its V-notches made the crown top's radial
                            # wedges); out on the arms a 6 mm round. Not larger: the round reads the sweeps' distance up
                            # to r_in off each tube, where it is not exact, and at 26 mm it beaded the crown top in a ring
                            # round the head; at 12 mm the creases came back (crown v6)
    web_tent=(0.27, 0.27, 0.27, 0.27, 0.27),   # crown v6b: the webs' LIE near their margins by sector (A..E): each
                            # web a TENT from the crown down to its margin, its sheet rising inward from the margin at
                            # least this steeply (rise per metre of distance in from the margin: 0.27 ~ 15 deg) until
                            # its own slope up to the crown is steeper, and up the U's walls the strip beside each arm
                            # falling from its root on the arm to its free edge at the same slope (web_lift); the
                            # margin's middle stays where it was and its ends come down 3-5 mm toward the arms: B / C / D
                            # middle thirds' undersides 28.6-29.1 mm (0.21 mantle widths; c226's gap >= 0.18), arching
                            # +1.9 to +2.7 mm over the thirds' ends (c226: an arch, its ends down at the arms [M c226];
                            # c204 low front, c311 / c334 front: the inner webs and arm roots one continuous slope from
                            # the head down to the arms [CROWN_STUDY 5]). v5d laid the B / C / D webs' outer 10-40 mm
                            # and the strips beside the arms level at the arms' equator, 30 mm up, so a sand-level
                            # camera (28 mm up) saw their oral faces 5-8 deg from edge-on and the wet lobe mirrored the
                            # sunlit sand (Skye's frame 0); tented, those faces turn their backs on a camera lower than
                            # the tent's slope and it sees the aboral faces. (A v6b arch raising the margins 9 mm
                            # tilted the oral faces OUT, toward the camera, by up to 13 deg: it showed 3.4 times more of
                            # them, paler.) A and E already fall 31-36 deg from the crown
    body_bound=(0.46, 0.002),   # crown v6b: a BOUND on the body sweep's distance behind and beside the mantle's apex
                            # (body_bound: a lathe round the apex's axis out to this share of the axis, this far off the
                            # sweep, and the half-space in front of it): the sweep's first node is the apex, its radius
                            # rising from 0 as sqrt, and sdf.sd_sweep divides by the first segment's slope there (26.5):
                            # along L4 / R4's backs, 43-470 mm from the body, the field read 5-42 mm and the arms' 16 mm
                            # blend swelled them by up to 3.8 mm at s 0.24-0.60 (the polish's 1.9 mm, by its measure)
    eye_r=0.0215,           # the eye mound (a turret): 46 mm across
    eye_theta=55.0,         # the lid opening's facing: degrees from the dorsal midline (forward)
    eye_x=0.018,            # the mounds' centres either side of the midline: the two turrets ARE the head's top
    eye_h=0.46,             # the mounds' centres above the crown (ML): 1.5 mound diameters over the ventral arm bases,
                            # which the side views need (the spec's 0.35 left 1.03 and buried the funnel in the oral
                            # disc and the arm bases, t24; the eyes stand 1.1-1.3 ML over the gravel in b01 / b02)
    eyeball_r=0.0150,       # the eyeball (30 mm across: the literature's 24-30 mm for a large animal)
    eye_ap=(50.0, 50.0),    # the lid aperture's half-angles fore-aft, up-down: round, 0.50 mound diameters across
    eye_proud=0.0012,       # the eyeball's front stands this far OUT of the mound's ellipsoid (every live eye bulges;
                            # the blends take ~0.1 mm: 1.1 mm out of the skin, the lid's collar 0.4-1.0 mm over the
                            # eyeball all round, patches/v4_geom/probe_eye)
    mantle_aspect=1.20,     # lateral / dorsoventral on the mantle: wider than deep (MW 0.68 ML, depth 0.61 ML)
    mantle_tilt=15.0,       # the eye-to-apex line below level (deg): live side views -10 to -14 with a level camera,
                            # -13.5 to -24 in un-levelled frames (at -12 the mantle's top stayed level, a sausage over
                            # photo 04's falling dorsal line, t24)
    head_mass=(0.048, 0.040, 0.048, 0.014),   # the head below and in front of the eyes (the brain and buccal mass): an
                            # ellipsoid's x, y, z radii and its blend (b01, b04: the head bulges forward under the eye
                            # and runs as one mass into the arm bases; the body sweep alone left a receding neck there,
                            # t24)
    head_mass_at=(-1.10, 0.55),   # its centre below and in front of the eyes' level, in mound diameters: the turret
                            # stands clear of it all round (centred 0.95 under and 0.45 in front with a 20 mm blend it
                            # filled the eye's lower-front quadrant and the lid stood 13 mm over the eyeball there, a
                            # scoop where photo 04 shows a convex collar, the v4 cage and sculpt checks)
    taper_s0=0.90,          # the body's end taper: gentle, only enough to keep the sweep's end cap inside the oral disc
    taper_k=0.25,           # (its bottom 4 mm over the disc's); steep and the sweep's radius falls faster than its axis
                            # advances (0.93 / 0.55: a slope of ~1.6, terraces and a ledge, t18)
    funnel=dict(r_exit=0.0125, r_tip=0.0080),  # a cone, broad at the root and narrowing to its opening (live: 0.44-0.57
                            # mound diameters at the exit, the rim 0.35-0.55; photo 04's 26 mm root to a 16 mm rim; at
                            # 24 -> 19 mm the turned-up funnel read as a rigid pipe in the v4 engine render)
    funnel_lumen=0.50,      # the funnel's aperture as a share of its tip radius (0.72 read as a rigid exhaust pipe in
                            # the engine probe; a siphon's opening is small and soft)
    mantle_margin=dict(lip_r=0.0050, lip_h=0.0025, groove_r=0.0035, groove_d=0.0012),   # the free margin (live photo
                            # 04: a thick rounded rim stepping down onto the head, the gap at its foot widest
                            # ventrally where the funnel leaves, closing behind the eye): the lip's radius and height
                            # proud of the body, the pallial crease's radius and depth at its widest (a groove as deep
                            # as the lip with both sides level read as a knife cut, t24; inside the bake's reach)
    mouth_open=(0.33, 0.21),   # the mouth's opening at the rim: an ellipse of these semi-axes in lip radii, the long
                               # axis lateral (ORAL_REFERENCE §3, §7: the beak's face 0.69 x 0.41 lip radii; the round
                               # 0.46 hole was too big)
)
N_ARMS = 8


def arm_azimuths():
    """azimuths around +Y measured from +Z toward +X (the creature's left): L1..L4 then R1..R4"""
    left = np.radians([22.5, 67.5, 112.5, 157.5])
    return np.concatenate([left, -left])


def eye_level(spec):
    """the eye mounds' centre height and fore-aft position: on the head's top, eye_h ML above the crown and 0.20 ML
    BEHIND the crown centre (top views: the arms' roots converge in front of the eyes)"""
    return spec['crown_y'] + spec['eye_h'] * spec['ML'], -0.20 * spec['ML']


def collar(spec):
    """the mantle's front on the body axis (the free margin's dorsal ends lie over it, 0.6 mound diameters behind the
    eyes)"""
    ML = spec['ML']
    ye, ze = eye_level(spec)
    return np.array([0.0, ye - 0.17 * ML, ze - 0.30 * ML])


def body_axis(spec):
    """the body loft's centreline, from the mantle's apex (back, a little below the eyes) forward through the mantle,
    under the eyes and down through the head to the crown centre above the oral disc: dense, with frames whose normal
    (theta = 0) is the dorsal side. The mantle LIES BACK nearly level (every live side view: the eye-to-apex line
    10-14 deg below level with a level camera), its apex 1.00 ML from the eyes' midpoint, mantle_tilt below level; its
    axis runs 0.17 ML under the eyes at its front, so the eyes stand on the top of one head-mantle body and the arms
    leave its front underside (v4; the r4 mantle stood up behind low-set eyes as a balloon, 41 deg from vertical and
    1.28 ML long)"""
    ML = spec['ML']
    cy = spec['crown_y']
    ye, ze = eye_level(spec)
    tilt = np.radians(spec['mantle_tilt'])
    ya = ye - ML * np.sin(tilt)
    za = ze - ML * np.cos(tilt)
    col = collar(spec)
    mid = np.array([0.0, 0.5 * (ya + col[1]) + 0.002, 0.5 * (za + col[2])])
    # from the mantle's front the axis turns down into the head and the crown top on a cubic Bezier: tangent to the
    # mantle's axis at the collar and to the crown's end direction at the crown top, its handles balanced so the turn
    # spreads evenly over the whole head (through a junction node the turn sat in 3 cm and the sweep, radius 4 cm,
    # folded on the inside of the bend: curvature x radius 2.2, a crease ring round the head, t24; a quadratic still
    # bunched it at the collar, 1.13)
    crown = np.array([0.0, cy + 0.06 * ML, 0.0])
    d0 = (col - mid) / np.linalg.norm(col - mid)
    d1 = np.array([0.0, -0.63, 0.78])                   # the crown end's direction: down and forward
    hl = 0.40 * np.linalg.norm(crown - col)
    B = np.array([col, col + hl * d0, crown - hl * d1, crown])
    # dense: the mantle a Catmull-Rom through apex, middle and collar (its end tangent col - mid, the Bezier's start
    # tangent, so the join is smooth), then the head's Bezier (spline control points sampled off it kinked the axis
    # at the collar: their uneven spacing overshot the uniform Catmull-Rom, t24)
    w_ = np.linspace(0.0, 1.0, 513)[1:, None]
    head = ((1 - w_) ** 3 * B[0] + 3 * w_ * (1 - w_) ** 2 * B[1] + 3 * w_ ** 2 * (1 - w_) * B[2] + w_ ** 3 * B[3])
    D = np.vstack([loft.resample(np.array([[0.0, ya, za], mid, col]), 1024), head])
    # nodes CLUSTERED toward the apex (arclength fractions u^1.4): the egg's end changes radius steeply and a linear
    # radius between sparse nodes printed every node as a terrace ring (t09's mantle top)
    seg = np.linalg.norm(np.diff(D, axis=0), axis=1)
    sD = np.concatenate([[0], np.cumsum(seg)]) / seg.sum()
    u = np.linspace(0, 1, 320) ** 1.4
    P = np.column_stack([np.interp(u, sD, D[:, k]) for k in range(3)])
    # dorsal at the apex: perpendicular to the axis, toward up (the mantle lies back, its dorsal surface up)
    t0 = P[1] - P[0]
    t0 /= np.linalg.norm(t0)
    up = np.array([0.0, 1.0, 0.0])
    ref = up - np.dot(up, t0) * t0
    n, b, t = loft.rmf(P, ref=ref)
    return P, n, b, t


def axis_s(P):
    """arclength fractions of a polyline's nodes"""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    return np.concatenate([[0], np.cumsum(seg)]) / seg.sum()


def body_radius(s, spec):
    """the body loft's radius (its dorsoventral half-depth: body_aspect scales the lateral) along its arclength share
    s (0 apex .. 1 crown): the mantle egg 0.30 ML deep at ~0.3 of its length (an elliptical end at the apex: r ~ sqrt
    near s = 0, so the sweep's end rounds smoothly instead of ending in a nub), easing without a waist into the head
    (half-depth 0.036 m at the eyes, its width there carried by the turrets), which FLARES below the eyes into the
    crown, whose breadth is the arms' and webs' (the live head below the eye is a mass as deep as the mantle running
    into the arm bases, b01; held at 0.04 under the eyes the head read as a neck, t24). C1 (PCHIP through the
    stations): a piecewise-linear profile prints a band at every station (t03's mantle)"""
    ML = spec['ML']
    # the mantle an EGG, its blunt end forward: deepest at ~0.4-0.5 of the axis, narrowing toward the apex (photo 04's
    # dorsal line falls steadily to the apex; held near its peak from s 0.15 to 0.5 it read as a level-topped
    # sausage, t24)
    st = np.array([[0.00, 0.026], [0.08, 0.034], [0.16, 0.042], [0.24, 0.049], [0.32, 0.054], [0.40, 0.057],
                   [0.48, 0.057], [0.56, 0.052], [0.62, 0.047], [0.68, 0.042], [0.74, 0.038], [0.82, 0.040],
                   [0.88, 0.047], [0.94, 0.054], [1.00, 0.058]])
    s = np.asarray(s, np.float64)
    R = PchipInterpolator(st[:, 0], st[:, 1])(np.clip(s, 0.0, 1.0))
    # the apex: R(s) times the end factor sqrt(1 - (1 - s/se)^2), whose slope is 0 at se, so the product stays C1
    # there (the first try joined a quarter ellipse with zero slope to a rising profile: a crease ring)
    se = 0.10
    u = np.clip(s / se, 0.0, 1.0)
    e = np.sqrt(np.clip(1.0 - (1.0 - u) ** 2, 0.0, 1.0))
    return R * e * (ML / 0.20)


def body_aspect(s, spec):
    """the body sweep's per-node aspect (its b axis, the lateral, over its n axis, the dorsoventral): the mantle wider
    than deep (mantle_aspect; r4's 0.90 everywhere made it deeper than wide), easing to a round-ish head"""
    s = np.asarray(s, np.float64)
    w = np.clip((s - 0.50) / 0.30, 0.0, 1.0)            # over the mantle's front and the junction (a shorter ease
    w = w * w * (3.0 - 2.0 * w)                         # printed a shoulder ring, t24)
    return spec['mantle_aspect'] * (1.0 - w) + 0.92 * w


def arm_length(spec, az):
    """an arm's own length by its pair (azimuth 22.5 deg -> arm 1 ... 157.5 -> arm 4)"""
    pair = int(np.clip(round((abs(np.degrees(az)) - 22.5) / 45.0), 0, 3))
    return spec['arm_len'] * spec['arm_pair_len'][pair]


def arm_centreline(spec, az, count=128):
    """one arm: leaves the crown outward and down, meets the ground, runs radially out standing on its suckers (its
    rest height, arm_rest_height), the tip curling up and in"""
    L = arm_length(spec, az)
    cy = spec['crown_y']
    # the tent: from the crown ring steeply out and down to the ground ~0.13 m out; the run on the ground, its heights
    # raised onto the suckers' rest height (v4's thick arms on r4's heights put the oral skin 5.6 mm and the sucker rims
    # 11.8 mm under the ground, and t10's grid floor cut the discs off, the v4 sculpt check); the tip's curl
    rad = np.array([spec['crown_r0'], 0.085, 0.125, 0.180, 0.250, 0.320, 0.420, 0.520, 0.610, 0.700, 0.800])
    hgt0 = np.array([cy - 0.004, 0.054, 0.032, 0.021, 0.018, 0.015, 0.013, 0.011, 0.0099, 0.0088, 0.020])
    hgt = hgt0.copy()
    d = np.array([np.sin(az), 0.0, np.cos(az)])
    # stretch the radial run so the arclength is L, the run's heights following each control point's share s
    for _ in range(4):
        ctrl = np.column_stack([rad * d[0], hgt, rad * d[2]])
        P = loft.resample(ctrl, count)
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        sP = np.concatenate([[0], np.cumsum(seg)]) / seg.sum()
        s_ctrl = sP[np.argmin(np.linalg.norm(P[:, None] - ctrl[None], axis=2), axis=0)]
        hgt[2:-1] = np.maximum(hgt0[2:-1], arm_rest_height(s_ctrl[2:-1], spec))
        rad = rad[0] + (rad - rad[0]) * (L / seg.sum())
    P = loft.resample(np.column_stack([rad * d[0], hgt, rad * d[2]]), count)
    # the frame: theta = 0 is ABORAL (up, away from the ground and the suckers)
    n, b, t = loft.rmf(P, ref=np.array([0.0, 1.0, 0.0]))
    return P, n, b, t


_ARM_TAPER = PchipInterpolator([0.0, 0.15, 0.30, 0.47, 0.59, 0.70, 0.77, 0.90, 1.0],
                               [1.0, 0.91, 0.82, 0.70, 0.59, 0.46, 0.33, 0.15, 0.0])


def arm_radius(s, spec):
    """the arm's radius along its share s: thick through the proximal half, narrowing gradually to the distal third,
    then faster to the tip (Gleadall 2016; live photo 14 at s 0.30-0.77: 0.874, 0.733, 0.576, 0.41 of its width at
    s 0.30, here 0.854, 0.720, 0.561, 0.402; r4's (1 - s)^0.92 was thin through s 0.3-0.7)"""
    f = _ARM_TAPER(np.clip(np.asarray(s, np.float64), 0.0, 1.0))
    return spec['arm_tip_r'] + (spec['arm_r0'] - spec['arm_tip_r']) * f


def sucker_size(s, spec):
    """a sucker's diameter by the arm's share s (research/BLOCKOUT_V4_SPEC.md 1.7: the largest the 15th-19th, at
    s ~0.17, live sucker / arm 0.32-0.41 on photo 14; r4's 7.2 mm peak was the 51st)"""
    return spec['sucker_d'] * np.interp(s, [0.0, 0.05, 0.17, 0.33, 0.55, 0.80, 1.0],
                                        [0.30, 0.62, 1.0, 0.88, 0.60, 0.30, 0.06])


def arm_rest_height(s, spec):
    """the arm's centre height where it lies on the ground: its oral half-depth plus the suckers' rims it stands on
    (the sessile rim reaches 0.40 d past the skin; 1.2 mm more for the rows' tilt off the oral midline and the section's
    flattening, within 0.4 mm of the laid-out suckers' lowest rims, patches/v4_geom/probe_ground), the rims pressed
    0.6 mm into the ground (soft rims flatten on it; between the centreline's control points the lowest rims then lie
    -1.0 to +0.4 mm off y = 0, where 0.3 mm left a 0.7 mm gap under some)"""
    return arm_radius(s, spec) + 0.40 * sucker_size(s, spec) + 0.0012 - 0.0006


def eye_geom(spec, side):
    """an eye (side +1 left, -1 right): the mound's (turret's) centre and outward axis, the eyeball's centre and radius:
    the eyeball's front stands eye_proud OUT of the mound's surface (live eyes bulge; r4's sat 4.9 mm deep in a
    socket)"""
    ye, ze = eye_level(spec)
    th = np.radians(spec['eye_theta'])
    out = np.array([side * np.sin(th), 0.18, np.cos(th)])
    out /= np.linalg.norm(out)
    c = np.array([side * spec['eye_x'], ye, ze])
    Re = spec['eyeball_r']
    # the mound's surface along out: its ellipsoid's (1.08, 1.0, 1.08) eye_r radius in that direction, 1.076 eye_r at
    # eye_theta 55 (a flat 1.04 sank the eyeball's front 0.42 mm under the skin, the v4 cage and sculpt checks)
    a = spec['eye_r'] * np.array([1.08, 1.0, 1.08])
    t_mound = 1.0 / np.linalg.norm(out / a)
    E = c + out * (t_mound + spec['eye_proud'] - Re)
    return c, out, E, Re


def head_mass(spec):
    """the head's mass below and in front of the eyes (the brain and the buccal mass): spec head_mass gives the
    ellipsoid's radii and blend, head_mass_at its centre below and in front of the eyes' level in mound diameters.
    Returns the centre, the radii and the blend"""
    ye, ze = eye_level(spec)
    TD = 2.0 * 1.08 * spec['eye_r']
    hx, hy, hz, hk = spec['head_mass']
    dy, dz = spec.get('head_mass_at', (-0.95, 0.45))
    return np.array([0.0, ye + dy * TD, ze + dz * TD]), [hx, hy, hz], hk


def funnel_geom(spec):
    """the funnel (a near-parallel tube: root, opening, their radii): its root under the mantle's free margin on the
    head's flank (spec funnel_side: +1 the left), its free part TURNED UP AND OUT beside the head, the opening behind
    and below the eye and clear of the head. Live: the root is ventral, inside the mantle's opening, and at rest the
    free two thirds (Gleadall: of 0.37 ML) lie along the head or turn up beside it (b04 along the body, its opening
    under the eye; b05, b11, b12 turned up beside the head, b11's opening level with the eye and out beside it); 0.44-
    0.57 mound diameters across at the exit. v4's ventral head behind the eyes is the ventral arms' and the E web's
    rise to the mantle: a midline funnel lay 12-68 mm inside it and the cage cut no port (the v4 cage and sculpt
    checks). Turned up (51 deg out from forward, 12 up), the port stands clear of the crown-top ring below it: laid
    along the body as b04's (36 deg out, 1.2 diameters under the eye) its root sat on the junction with the arms'
    roots and the port folded 38-61 quads (patches/v4_geom/try_funnel)"""
    ye, ze = eye_level(spec)
    TD = 2.0 * 1.08 * spec['eye_r']
    side = spec.get('funnel_side', 1.0)
    a = np.array([side * 0.55 * TD, ye - 1.05 * TD, ze - 0.90 * TD])    # the root, under the margin's lip
    b = np.array([side * 1.30 * TD, ye - 0.85 * TD, ze - 0.30 * TD])    # the opening, out beside the head
    f = spec['funnel']
    return a, b, f['r_exit'], f['r_tip']


def mantle_margin(spec, n=41):
    """the mantle's FREE MARGIN as a curve (n points) from one side to the other round the ventral side: from just
    behind and below one eye (0.62 mound diameters behind, 0.45 below its centre: live side views), down and back under
    the mantle's front (over the funnel's root on the left flank: build_sdf projects the curve onto the shape with the
    funnel in it, so the lip rides over the root), and up to the other eye (fused dorsally: the lip fades out at the
    ends). Not yet on the surface: build_sdf projects it"""
    c, out, E, Re = eye_geom(spec, 1)
    TD = 2.0 * 1.08 * spec['eye_r']
    top = np.array([0.046, c[1] - 0.45 * TD, c[2] - 0.62 * TD])
    low = np.array([0.0, c[1] - 1.56 * TD, c[2] - 1.34 * TD])     # under the mantle's front (the funnel's root is on
                                                                   # the flank: funnel_geom)
    t = np.linspace(-1.0, 1.0, n)
    x = top[0] * np.sin(0.5 * np.pi * t)
    w = np.cos(0.5 * np.pi * t)                        # 0 at the ends, 1 ventrally
    y = top[1] + (low[1] - top[1]) * w ** 0.8
    z = top[2] + (low[2] - top[2]) * w ** 1.2
    return np.column_stack([x, y, z])


def body_taper(s, spec):
    """the body's end taper: the sweep's profile narrows over its last stretch so its end hemisphere stays inside the
    oral disc (t04: a 66 mm end cap hung 2 cm under the crown, the mouth's sag). Begun too early it pinches a neck under
    the eyes that the live animal lacks (taper_s0 0.88: a waist 10 mm deep at y 110 mm, the head band's normal-map
    stripe)"""
    s0 = spec.get('taper_s0', 0.88)
    x = np.clip((s - s0) / (1.0 - s0), 0.0, 1.0)
    return 1.0 - spec.get('taper_k', 0.55) * x * x * (3.0 - 2.0 * x)


def arm_round_centre(spec):
    """the centre of the arms' round-union radius field (arm_round): the mouth (the web depth's origin), moved
    forward (+z) by arm_round[4] when given (the field then eases off sooner behind the head, under the mantle)"""
    ar = spec['arm_round']
    return mouth_point(spec) + np.array([0.0, 0.0, ar[4] if len(ar) > 4 else 0.0])


def body_bound(spec, P, n, b, bin_w=0.002):
    """(crown v6b) a BOUND on the body sweep's distance where sdf.sd_sweep under-reads it. The sweep's first node is the
    mantle's apex, where its radius rises from 0 as sqrt (body_radius: an elliptical end), so its first segments are
    steep (slope 26.5, 10, 7, ...) and sd_sweep divides the distance by sqrt(1 + slope^2) for every point whose foot
    point falls on them or behind the apex: along L4 / R4's backs, 43-470 mm from the body, the field read 5-42 mm and
    the arms' 16 mm blend swelled them by up to 3.8 mm (s 0.24-0.60). The hull: a LATHE round the apex's own axis t0
    (sdf REVOLVE, exact), the body's greatest distance off that axis per bin_w of it (the sweep's surface sampled as
    sd_sweep lays it: the profile's harmonics, the aspect; each bin's value the greatest of it and its two neighbours,
    so the profile's chords hold every sample) plus `margin`, from `margin` behind the apex to `cut` of the axis length
    (and `margin` past it), united with the half-space in front of the plane at cut - margin (build_sdf: a ROUNDBOX's
    face, exact). The body lies inside the hull, so the hull's distance is a lower bound on the body's own: max(body,
    hull) is still a distance bound, the same zero set, unchanged wherever the sweep reads at least the hull (within
    `margin` of the body everywhere, the hull standing off it), and the true distance to the hull where the sweep
    under-read. spec['body_bound'] = (cut, margin). Returns (the profile (m, 2) of (r, y along t0), the apex, t0, the
    plane's distance along t0 from the apex)"""
    cut, margin = spec['body_bound']
    s = axis_s(P)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    r = body_radius(s, spec) * body_taper(s, spec)
    asp = body_aspect(s, spec)
    A = P[0]
    t0 = (P[1] - P[0]) / np.linalg.norm(P[1] - P[0])
    c = cut * seg.sum()
    # the sweep's surface: rings at its nodes and between, sd_sweep's profile (a2 0.035, a4 0.012, the aspect)
    ss = np.unique(np.concatenate([s, np.linspace(0.0, 1.0, 1601)]))
    th = np.linspace(-np.pi, np.pi, 361)[:-1]
    ip = lambda X: np.column_stack([np.interp(ss, s, X[:, k]) for k in range(3)])
    C, N_, B_ = ip(P), ip(n), ip(b)
    N_ /= np.linalg.norm(N_, axis=1, keepdims=True)
    B_ /= np.linalg.norm(B_, axis=1, keepdims=True)
    a_ = np.interp(ss, s, asp)[:, None]
    rr = np.interp(ss, s, r)[:, None] * (1.0 + 0.035 * np.cos(2.0 * th) + 0.012 * np.cos(4.0 * th))[None]
    rr = rr * a_ / np.sqrt(a_ ** 2 * np.cos(th)[None] ** 2 + np.sin(th)[None] ** 2)
    X = (C[:, None] + rr[..., None] * (np.cos(th)[None, :, None] * N_[:, None] +
                                       np.sin(th)[None, :, None] * B_[:, None])).reshape(-1, 3)
    ax = (X - A) @ t0
    rad = np.linalg.norm((X - A) - np.outer(ax, t0), axis=1)
    assert ax.min() > -1.0e-6, f'the body reaches {-ax.min() * 1e3:.3f} mm behind its apex plane'
    nb = int(np.ceil((c + margin) / bin_w))
    w_ = (c + margin) / nb                                   # (the bins span 0 .. c + margin exactly, at most bin_w)
    k = np.clip((ax / w_).astype(np.int64), 0, None)
    sel = k < nb
    rmax = np.zeros(nb)
    np.maximum.at(rmax, k[sel], rad[sel])
    assert (rmax > 0.0).all(), 'a lathe bin without a body sample'
    env = np.maximum(np.maximum(rmax, np.r_[rmax[1:], rmax[-1]]), np.r_[rmax[0], rmax[:-1]]) + margin
    ys = (np.arange(nb) + 0.5) * w_
    prof = np.vstack([[0.0, -margin], [env[0], -margin], np.column_stack([env, ys]), [env[-1], c + margin],
                      [0.0, c + margin]])
    return prof, A, t0, c


def _project(prog, P, iters=6, h=1.0e-4):
    """points pulled onto the program's zero set along its gradient (central differences), and the unit normals there"""
    P = np.asarray(P, np.float64).copy()
    E = np.eye(3) * h
    for it in range(iters + 1):
        f = prog.eval(P).astype(np.float64)
        g = np.stack([(prog.eval(P + E[k]).astype(np.float64) - prog.eval(P - E[k]).astype(np.float64)) / (2.0 * h)
                      for k in range(3)], -1)
        gl = np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)
        if it == iters:
            return P, g / gl
        P -= f[:, None] * g / gl ** 2


def build_sdf(spec=SPEC):
    prog = sdf.Program()
    P, n, b, t = body_axis(spec)
    s = axis_s(P)
    # mantle and head: oval (the mantle wider than deep, the head round-ish), a slight squareness at the head, the end
    # tapered
    prog.sweep(P, n, body_radius(s, spec) * body_taper(s, spec), a2=0.035, phi2=0.0, a4=0.012,
               aspect=body_aspect(s, spec), name='body')
    # (crown v6b) the body's distance BOUNDED behind and beside the mantle's apex (body_bound): the sweep, intersected
    # hard with a hull that holds it whole, is the same shape with its far field read true where sd_sweep under-read it
    bb = body_bound(spec, P, n, b) if spec.get('body_bound') else None
    if bb is not None:
        prof, A_, t0_, c_ = bb
        prog.begin_group(op=sdf.INTERSECT, k=0.0)
        prog.revolve(prof, A_, t0_, name='body bound')
        H_ = 5.0
        e1_ = np.cross(t0_, [1.0, 0.0, 0.0]) if abs(t0_[0]) < 0.9 else np.cross(t0_, [0.0, 1.0, 0.0])
        e1_ /= np.linalg.norm(e1_)
        prog.roundbox(A_ + t0_ * (c_ - spec['body_bound'][1] + H_), [H_, H_, H_],
                      axes=np.column_stack([e1_, np.cross(t0_, e1_), t0_]), name='body bound front')
        prog.end_group()
    ML = spec['ML']
    cy = spec['crown_y']
    # the eye mounds: two turrets on the head's top, meeting over a shallow saddle, facing forward-out
    for side in (1, -1):
        c, out, E, Re = eye_geom(spec, side)
        prog.ellipsoid(c, [spec['eye_r'] * 1.08, spec['eye_r'] * 1.0, spec['eye_r'] * 1.08], k=0.014,
                       name=f'eye mound {"L" if side > 0 else "R"}')
        # (the supraocular papillae, the socket and the lids are the sculpt plan's: octopus_sculpt)
    # the head's mass under and in front of the eyes, one with the turrets and the crown
    ye, ze = eye_level(spec)
    TD = 2.0 * 1.08 * spec['eye_r']
    hc, hr, hk = head_mass(spec)
    prog.ellipsoid(hc, hr, k=hk, name='head mass')
    # the oral disc under the crown: broad, the arms' bases merge into it
    prog.ellipsoid([0.0, cy - 0.010, 0.0], list(spec['oral_disc']), k=0.024, name='oral disc')
    # the funnel: from under the mantle's free margin, forward and out beside the head on the left flank; a light
    # blend so the tube stays a tube where it leaves the head
    fa, fb, fra, frb = funnel_geom(spec)
    prog.roundcone(fa, fb, fra, frb, k=0.008, name='funnel')
    # the mantle's FREE MARGIN (a high detail: low_spec drops it): the curve projected onto the body, a rounded lip
    # proud of it (the mantle's edge, fading out at the dorsal ends where the margin is fused) and the pallial groove
    # in front of it toward the head (the closed opening: live photo 04's gap, widest ventrally where the funnel
    # leaves, closing behind the eye), both softly blended (a hard groove read as a knife slit, t24)
    mm = spec.get('mantle_margin')
    if mm:
        Cm, Nm = _project(prog, mantle_margin(spec))
        Tm = np.gradient(Cm, axis=0)
        Tm /= np.linalg.norm(Tm, axis=1, keepdims=True)
        Sm = np.cross(Nm, Tm)
        Sm /= np.linalg.norm(Sm, axis=1, keepdims=True)
        Sm[np.einsum('ij,ij->i', Sm, np.array([0.0, ye, ze]) - Cm) < 0.0] *= -1.0      # toward the head
        u = np.linspace(0.0, 1.0, len(Cm))
        w = np.clip(np.minimum(u, 1.0 - u) / 0.22, 0.0, 1.0)
        w = w * w * (3.0 - 2.0 * w)                      # the lip: full over most of the margin, fading at its ends
        g = np.sin(np.pi * u) ** 1.5                     # the gap: widest ventrally
        nm, _, _ = loft.rmf(Cm, ref=Nm[0])
        lip = Cm - Nm * (mm['lip_r'] - mm['lip_h'] * w + 0.001 * (1.0 - w))[:, None]
        prog.sweep(lip, nm, np.full(len(Cm), mm['lip_r']), k=0.004, name='mantle lip')
        # the crease at the lip's foot on the head's side: its tube's centre OUTSIDE the skin by its radius less the
        # depth, so it dips groove_d into it at its widest and stands clear 0.5 mm at the ends (bake_misses: centred
        # inside, as the lip's, the carve ran 2 rg - groove_d = 5.8 mm deep under a mouth narrower than its belly,
        # a keyhole channel 4.5 mm deep after its blend whose walls face away from every low ray: the head set's
        # 52 mm strip of misses on the right flank, x -39 mm)
        rg = mm['groove_r'] * (0.55 + 0.45 * g)
        groove = Cm + Sm * (0.9 * mm['lip_r']) + Nm * (rg - mm['groove_d'] * g + 0.0005 * (1.0 - g))[:, None]
        prog.sweep(groove, nm, rg, op=sdf.SUBTRACT, k=0.003, name='pallial groove')
    # arms and webs: each set a GROUP blended into the body once (no compounding). The arms among themselves by the
    # ROUND union (crown v6b, sdf.ROUND) with a radius FIELD (arm_round: r_in within d0 of the mouth, easing to r_out
    # by d1): over the crown neighbouring arm roots merge in smooth saddles where their tubes meet (the hard union
    # creased there, L1 | R1 the front midline, and its V-notches made the crown top's radial wedges); exact wherever
    # one arm alone lies within the radius, symmetric in its members, never filling farther than the radius however
    # many arms meet (the oral centre untouched: the compounding that sank it, sdf.py); the webs stay as they were
    azs = arm_azimuths()
    arms = [arm_centreline(spec, az) for az in azs]
    ar = spec.get('arm_round')
    prog.begin_group(k=0.016, round_field=(arm_round_centre(spec), (1.0, 1.0, 1.0), ar[2], ar[3], ar[1]) if ar else
                     None)
    for i, (Pa, na, ba, ta) in enumerate(arms):
        sa = np.linspace(0, 1, len(Pa))
        # the section: rounder aboral, flatter oral (where the sucker rows sit)
        prog.sweep(Pa, na, arm_radius(sa, spec), a2=0.06, phi2=0.0, a3=0.05, phi3=0.0, aspect=0.92,
                   op=sdf.ROUND if ar else sdf.UNION, k=ar[0] if ar else 0.0, name=f'arm {i}')
    prog.end_group()
    # around the crown in the cage's column order (theta = -azimuth increasing): web j joins arm order[j]'s +b side
    # to arm order[j+1]'s -b side, its margin by its sector (web_plan)
    plan = web_plan(spec, arms)
    order = plan['order']
    prog.begin_group(k=0.006)
    for j in range(N_ARMS):
        ia, ib = order[j], order[(j + 1) % N_ARMS]
        Va, Fa, Ha = web_patch(arms[ia], arms[ib], spec, lambda lam, j=j: margin_s(lam, plan, j),
                               cap=max(plan['sw'][ia], plan['sw'][ib]) + 0.002, depth=plan['d_mid'][j],
                               lift=lambda lam, s, j=j: web_lift(spec, plan, j, lam, s))
        prog.shell(Va, Fa, Ha, k=0.0, maxd=0.03, name=f'web {ia}-{ib}')
    prog.end_group()
    # the MANTLE'S SEAT (crown v5): the mantle rests on the crown top behind the head in a tight fold (live behind views
    # c49, c226: no valley, the arm roots and webs meet the mantle's sides [M c49]); the blends left a cleft 10-25 mm
    # deep between the mantle's underside and the crown's back face, whose mouth the cage bridged (bake_misses C, the
    # dark jagged crease of t11_mantle). Balls filling the cleft, measured on the low program (seat_balls), one hard
    # union blended into the rest
    prog.seat = None
    if spec.get('mantle_seat', True):
        prog.seat = seat_balls(spec)
        if prog.seat is not None:
            prog.begin_group(k=0.003)
            for c_, r_ in zip(*prog.seat):
                prog.ellipsoid(c_, [r_, r_, r_], name='mantle seat')
            prog.end_group()
    # the MOUTH at the oral pole (Skye 10-20: "the central mouth hole"): a fleshy lip ring (the buccal membrane's
    # peristome) round an opening into the buccal mass, where the beak sits (its own part, octopus_beak). The pole is
    # measured on the block-out so far: the arms' blend lowers the oral disc's underside a little
    md = mouth_dims(spec)
    ys = np.linspace(cy - 0.09, cy, 901)
    d = prog.eval(np.column_stack([np.zeros_like(ys), ys, np.zeros_like(ys)]))
    i = int(np.argmax(d < 0.0))
    y0 = ys[i - 1] + (ys[i] - ys[i - 1]) * d[i - 1] / (d[i - 1] - d[i])
    up = np.array([0.0, 1.0, 0.0])
    mc = np.array([0.0, y0, 0.0])
    prog.torus(mc + up * md['lift'], up, md['R'], md['r'], k=0.0025, name='lip')
    if spec.get('mouth_open'):
        # an elliptical cavity whose section at the rim is the opening (its centre 0.6 depths in, its height a depth:
        # sqrt(1 - 0.6^2) = 0.8 of its semi-axes at the oral plane), widening a little inside round the beak
        dep = md['depth']
        prog.ellipsoid(mc + up * (0.6 * dep), [md['ax'] / 0.8, dep, md['az'] / 0.8], op=sdf.SUBTRACT, k=0.0012,
                       name='mouth')
    else:
        prog.roundcone(mc - up * 0.006, mc + up * md['depth'], md['r_open'], 0.85 * md['r_open'], op=sdf.SUBTRACT,
                       k=0.0015, name='mouth')
    prog.mouth = dict(c=mc, up=up, **md)
    return prog, arms


def seat_balls(spec, rc=0.045, h=0.0025, cover=0.99, r_min=0.006, proud=0.002):
    """the mantle's seat: the cleft between the mantle's underside and the crown's back face, measured on the LOW
    program without it (the free margin's lip and crease are the high's alone and stay out of the measure, so the low
    and the high get the same seat). In a voxel window behind the head (h ML voxels; x within 0.2 ML of the midline,
    y from the crown up to 0.1 ML under the collar, z from 0.15 ML behind the collar to 0.25 ML in front), the 3D
    CLOSING of the shape by a ball rc ML across minus the shape is the cleft (the funnel's own slot, round its axis,
    left out). Balls cover it greedily, each the largest centred on a cleft voxel still open that fits inside the
    closing (and `proud` ML more: a crease narrower than a few mm took hundreds of balls tangent to it), until
    `cover` of the cleft's voxels are covered or the room left is under r_min ML; their union fills the cleft whole (a
    tube through the cleft's mouth left its tip a void behind it). Returns (centres (n, 3), radii (n,)) mirrored to
    be exact about x = 0, or None when there is no cleft. Measured ONCE per spec and process (_SEAT: the low, the high
    and every later build_sdf of one spec share it; t10's cage + UV step took 158-165 s with a closing per call, 39 s
    before the seat)"""
    key = repr(sorted((k, v) for k, v in low_spec(spec).items() if k != 'mantle_seat')) + repr((rc, h, cover, r_min,
                                                                                                proud))
    if key not in _SEAT:
        _SEAT[key] = _seat_balls(spec, rc, h, cover, r_min, proud)
    got = _SEAT[key]
    return None if got is None else (got[0].copy(), got[1].copy())


_SEAT = {}


def _seat_balls(spec, rc, h, cover, r_min, proud):
    """seat_balls' measure itself (uncached)"""
    from scipy import ndimage
    ML = spec['ML']
    prog, _ = build_sdf(dict(low_spec(spec), mantle_seat=False))
    col = collar(spec)
    cy = spec['crown_y']
    g = h * ML
    fa, fb, fra, frb = funnel_geom(spec)
    C, Rr = [], []
    for x_half, (y0, y1), (z0, z1) in ((0.2 * ML, (cy - 0.005, col[1] - 0.1 * ML),
                                        (col[2] - 0.15 * ML, col[2] + 0.25 * ML)),):
        pad = int(np.ceil(rc / h)) + 2
        xs = np.arange(0.0, x_half + g / 2, g)
        xs = np.concatenate([-xs[:0:-1], xs])
        X, Y, Z = np.meshgrid(xs, np.arange(y0, y1, g), np.arange(z0, z1, g), indexing='ij')
        solid = prog.eval(np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])).reshape(X.shape) < 0.0
        sp = np.pad(solid, pad)                                        # (outside the window: air)
        dil = ndimage.distance_transform_edt(~sp) * g <= rc * ML
        closing = ndimage.distance_transform_edt(np.pad(dil[pad:-pad, pad:-pad, pad:-pad], pad)) * g > rc * ML
        closing |= sp
        cleft = closing & ~sp
        # not the funnel's slot beside the head (its root under the margin on the left flank)
        P = np.stack([np.pad(A, pad, mode='edge') for A in (X, Y, Z)], -1)
        ab = fb - fa
        t_ = np.clip(((P - fa) @ ab) / (ab @ ab), 0.0, 1.0)
        cleft &= np.linalg.norm(P - (fa + t_[..., None] * ab), axis=-1) > fra + rc * ML
        n_cleft = int((cleft & (P[..., 0] >= -0.5 * g)).sum())
        if n_cleft < 8:
            continue
        dt_out = ndimage.distance_transform_edt(closing) * g            # room inside the closing
        open_ = cleft & (P[..., 0] >= -0.5 * g)                        # the left half (x >= 0); mirrored below
        while open_.sum() > (1.0 - cover) * n_cleft:
            i = np.unravel_index(np.argmax(np.where(open_, dt_out, -1.0)), open_.shape)
            if dt_out[i] < r_min * ML:
                break
            r = dt_out[i] - 0.5 * g + proud * ML
            c = P[i]
            C.append(c)
            Rr.append(r)
            lo = [max(int(i[k] - r / g) - 1, 0) for k in range(3)]
            hi = [min(int(i[k] + r / g) + 2, open_.shape[k]) for k in range(3)]
            sl = tuple(slice(lo[k], hi[k]) for k in range(3))
            open_[sl] &= np.linalg.norm(P[sl] - c, axis=-1) > r
    if not C:
        return None
    C, Rr = np.array(C), np.array(Rr)
    # exact about x = 0 (the voxels are, the float evaluation may not be): each ball and its mirror
    keep = C[:, 0] >= -0.5 * g
    C, Rr = C[keep], Rr[keep]
    side = C[:, 0] > 0.5 * g
    C = np.vstack([C, C[side] * np.array([-1.0, 1.0, 1.0])])
    Rr = np.concatenate([Rr, Rr[side]])
    return C, Rr


def mouth_dims(spec):
    """the mouth's lip ring (R its crest radius, r its tube, lift: its centre above the oral surface), the opening's
    radius and depth: scaled with the mantle (O. vulgaris: a lip ring ~4 % of the mantle length in radius). With
    spec['mouth_open'] = (sx, sz) the opening at the rim is an ELLIPSE of semi-axes sx and sz lip radii (L = R + r),
    the long axis lateral (ORAL_REFERENCE §3, §7: the visible beak face 0.69 x 0.41 lip radii, the mouth closed at rest);
    ax and az are the rim's semi-axes (both r_open for the round opening)"""
    ML = spec['ML']
    d = dict(R=0.040 * ML, r=0.016 * ML, r_open=0.026 * ML, depth=0.050 * ML, lift=0.004 * ML)
    mo = spec.get('mouth_open')
    L = d['R'] + d['r']
    d['ax'], d['az'] = (mo[0] * L, mo[1] * L) if mo else (d['r_open'], d['r_open'])
    return d


def arm_side(arm, s, spec, sign):
    """a point on an arm's side line at s: the centre plus sign * b * r (sign +1: the +b side)"""
    Pa, na, ba, ta = arm
    sa = np.linspace(0, 1, len(Pa))
    ip = lambda X: np.array([np.interp(s, sa, X[:, k]) for k in range(3)])
    return ip(Pa) + sign * ip(ba) * arm_radius(np.array([s]), spec)[0]


CAGE = dict(K=128, SECT=16, HALF=4, R=16, body_step=0.0050, arm_step=0.0085,    # R: the bottom's rows to the arms'
                                                                # tube (crown v5: the webs' columns end on their margins,
                                                                # rows level with the arms'; at 12 the A web's oral face
                                                                # kept 3 rows, 40 mm quads)
            wall_from=0.5,                                      # a wall column meets the margin this share of a column
                                                                # toward its neighbour, its run up the wall from there
            fold_air=0.002,                                     # a top junction line that runs this far through air
                                                                # is a concave fold: cast onto its nearest surface,
            fold_turn=60.0,                                     # its crease (a row pinned there, on a web's or side
                                                                # column) a turn of this many degrees into the shape
            support_rows=2,                                     # crown v5d: the top layer's SUPPORT rows (every column
                                                                # takes them), pinned on the back band's fold profiles
            support_gap=0.0006,                                 # where a chord of a column's rows, the ring to its
            support_min=0.0015,                                 # band's edge and the next, stands this far off it,
                                                                # never nearer a row than this;
            support_fine=8,                                     # the junction's line cut this many times a step for
            support_sweeps=2,                                   # the profile; rounds of taking each support out and
                                                                # putting it back (support_plan)
            slide_bot=True, slide_top=True,                     # (rest-pose round) the rows slid off their chords
            slide_top_cut=0.0020, slide_top_skip=(0,),          # (chord_slide), per layer; the top only on columns
            slide_t=0.4, slide_reach=0.008, slide_gain=5.0e-5,  # where a chord stands this far off the shape, outside
            slide_sweeps=3, slide_tau=0.0015, slide_seg=0.5,    # the sectors listed (0, the A web's: the head gate's
            slide_rho0=0.060,                                   # front midline); a row's candidates at most this share
                                                                # of the way to its neighbour, cast at most this far
                                                                # along its normal; a move kept when its chords' |f|
                                                                # past slide_tau comes slide_gain nearer; rounds; no
                                                                # step under slide_seg of the row's step before; the
                                                                # bottom's rows within slide_rho0 of the mouth's axis
                                                                # stay
            body_s0=0.10, apex_s=(0.068, 0.040, 0.018),         # the body loft starts here; the reduction rings
            lean_s0=0.10,                                       # the body rings lean toward the crown-top ring past here
            junction_off=0.001, junction_run=0.015,             # the crown-top ring: the shape this far off the head,
                                                                # for this long along the axis
            eye_gap=0.006,                                      # the eye's block: the lid's fold ring + this
            funnel_gap=2, funnel_half=0.5,                      # the funnel's block: its footprint's cells + this many
                                                                # (its corners left out); the halfway ring's share
                                                                # from the block's loop to the footprint
            mouth_r=(0.026, 0.018, 0.012),                      # row 0 round the mouth, then the reduction rings
            open_r=0.075,                                       # the arms' side lines part this far out from the
                                                                # mouth's axis: the crown's arm layout starts beyond,
            layout_in=0.002,                                    # where its proxies stand no deeper in the shape
            junction_relax=12,                                  # rounds of relaxation over the crown's junction rows
            junction_into=1,                                    # and this many layout rows past each junction
            row_hold=(1.0, 0.0),                                # the crown's rows held level with their neighbours'
                                                                # (top, bottom): shear over the columns' spacing
                                                                # against uneven steps (top 0.75 and 1.0: no folds, 45
                                                                # and 44 quads under 10 deg; 1.5: a fold in the A web;
                                                                # bottom 0.6: LSCM laid the A and E webs' undersides
                                                                # over themselves, 19 texels, t08 --low)
            polar_w=2.0,                                        # the bottom's rows this much denser round the mouth
            side_delta=(30.0, 28.0),                            # degrees: the layers' side lines either side of the
                                                                # web (top, bottom: at 30 the bottom's side and first web
                                                                # columns met across the shallow webs' acute creases and
                                                                # folded under the preserving fit, t04 v4; at 40, crown
                                                                # v5-v5d, the bottom's side line stood ~19 deg down the
                                                                # arm's flank from the web's underside and its quads to
                                                                # the wall column chorded the crotch between them, 2.0-2.4
                                                                # mm off the shape: 60 of v5d's 86 bridging triangles;
                                                                # rest-pose round), at most:
            side_fillet=0.002,                                  # crown v5: by the web's own half-thickness where it
                                                                # meets the arm, plus this for the webs' blend
            top_lead=3,                                         # the top layer's extra rows off the head ring
            bot_extra=8,                                        # Stage 4: the bottom layer's rows over R (its own,
                                                                # inside the shared runs: the margins, the walls' and
                                                                # the arms' bare runs, the tubes' first rings stay
                                                                # where row_plan put them on R rows): at R alone the
                                                                # oral web turns 21-50 deg per row where it hangs into
                                                                # the walls (rows 3-7, steps 17-27 mm), and at Skye's
                                                                # sand-level frame its contour runs along row 6 into
                                                                # the wall columns as straight V notches
            bot_wall_lam=0.3)                                   # Stage 4: the bottom's wall columns start this share
                                                                # of their lam out from the arm's side line (into the
                                                                # crotch, near the junction's fillet) and sweep out to
                                                                # the same lam_end at the margin: one quad (17.6 / 35.8
                                                                # mm wide at rows 6 / 7) took the web's 60-70 deg turn
                                                                # into the arm's flank, its crease the notch's other
                                                                # arm; now two (12.5 / 23.5 mm and the next)


def web_sector(ia, ib):
    """the web sector (0..4 = A..E) between two neighbouring arms (indices: L1..L4 = 0..3, R1..R4 = 4..7): A between
    the arms 1, B arms 1-2, C 2-3, D 3-4, E between the arms 4"""
    if {ia, ib} == {0, 4}:
        return 0
    if {ia, ib} == {3, 7}:
        return 4
    return 1 + min(ia % 4, ib % 4)


def mouth_point(spec):
    """the web depth's origin: the mouth (Roper & Voss measure the web from it)"""
    return np.array([0.0, spec['crown_y'] - 0.036, 0.0])


def _depth_s(spec, armA, armB, target):
    """the arm share s at which the point midway between armA's +b and armB's -b side lines lies `target` metres
    from the mouth"""
    ss = np.linspace(0.0, 0.6, 601)
    r = arm_radius(ss, spec)

    def side(arm, sign):
        Pa, na, ba, ta = arm
        sa = np.linspace(0, 1, len(Pa))
        ip = lambda X: np.column_stack([np.interp(ss, sa, X[:, k]) for k in range(3)])
        return ip(Pa) + sign * ip(ba) * r[:, None]
    q = 0.5 * (side(armA, 1.0) + side(armB, -1.0))
    return float(np.interp(target, np.linalg.norm(q - mouth_point(spec), axis=1), ss))


def web_plan(spec, arms):
    """the web margins round the crown in the cage's column order (web j joins arm order[j]'s +b side to arm
    order[j+1]'s -b side): per web its sector, its mid-sector reach s_mid along the arms (where the point midway
    between the side lines lies web_sector[sector] ML from the mouth, D_mid) and its REACH s_reach, where the margin
    meets the arms' side lines (web_reach[sector] x D_mid), its wall exponent and D_mid itself; per ARM the start sw of
    its tube: the larger of its two webs' web_side x their depth, so the cage's arm tube starts square across the arm
    (crown v5: the margins meet the arms at their own reach inside it, the arm's flank bare out to sw; v4 ran every
    margin out to the common sw, 3.16 D_mid for the A web)"""
    order = np.argsort(np.mod(-np.degrees(arm_azimuths()), 360.0))
    ML = spec['ML']
    sector, s_mid, s_side, s_reach, d_mid = [], [], [], [], []
    for j in range(N_ARMS):
        ia, ib = order[j], order[(j + 1) % N_ARMS]
        sec = web_sector(ia, ib)
        d = spec['web_sector'][sec] * ML
        sector.append(sec)
        d_mid.append(d)
        s_mid.append(_depth_s(spec, arms[ia], arms[ib], d))
        s_side.append(_depth_s(spec, arms[ia], arms[ib], spec['web_side'] * d))
        reach = spec.get('web_reach')
        s_reach.append(_depth_s(spec, arms[ia], arms[ib], (reach[sec] if reach else spec['web_side']) * d))
    sw = np.zeros(N_ARMS)
    for j in range(N_ARMS):
        for a in (order[j], order[(j + 1) % N_ARMS]):
            sw[a] = max(sw[a], s_side[j])
    if len(set(spec['arm_pair_len'])) == 1:
        sw[:] = sw.max()            # identical arms (one sculpt plan rotated, one stacked UV set): one tube start
    s_reach = np.minimum(np.array(s_reach), [min(sw[order[j]], sw[order[(j + 1) % N_ARMS]]) for j in range(N_ARMS)])
    wall = np.array([spec.get('web_wall', (0.0,) * 5)[sec] for sec in sector])
    plan = dict(order=order, sector=np.array(sector), s_mid=np.array(s_mid), s_side=np.array(s_side), sw=sw,
                s_reach=s_reach, wall=wall, d_mid=np.array(d_mid))
    # (crown v6b, for web_lift) the side lines at each arm's nodes (its +b side, its -b side: arm_side's) and every web's
    # margin, densely (web_patch's sheet at s = margin_s(lam), lam cosine-spaced: dense up the U's walls)
    sa = np.linspace(0.0, 1.0, len(arms[0][0]))
    ra = arm_radius(sa, spec)[:, None]
    plan['arm_s'] = sa
    plan['side_p'] = np.array([[Pa + ba * ra, Pa - ba * ra] for Pa, na, ba, ta in arms])
    lm = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, 401))
    plan['margin_p'] = np.array([web_sheet(plan, j, lm, margin_s(lm, plan, j)) for j in range(N_ARMS)])
    return plan


def web_sheet(plan, j, lam, s):
    """(crown v6b) web j's flat sheet (web_patch's before any lift) at (lam, s): (1 - lam) SA(s) + lam SB(s) between
    arm order[j]'s +b side line and arm order[j + 1]'s -b side line (web_plan's side_p, interpolated at the arms'
    nodes as arm_side does); lam and s broadcast, the points (..., 3)"""
    lam, s = np.broadcast_arrays(np.asarray(lam, np.float64), np.asarray(s, np.float64))
    sa, SP = plan['arm_s'], plan['side_p']
    ia, ib = plan['order'][j], plan['order'][(j + 1) % N_ARMS]
    A = np.stack([np.interp(s, sa, SP[ia, 0][:, k]) for k in range(3)], -1)
    B = np.stack([np.interp(s, sa, SP[ib, 1][:, k]) for k in range(3)], -1)
    return (1.0 - lam)[..., None] * A + lam[..., None] * B


def margin_s(lam, plan, j):
    """web j's margin reach along its arms at the share lam between their side lines: s_mid midway, rising on a U to
    the web's reach s_reach on both arms' side lines. With a wall exponent p (spec web_wall, crown v5): s = mid +
    (reach - mid) t^p, t = |2 lam - 1|: a flat bottom and steep walls that meet the arm at an angle, the strip beside
    the arm narrowing to nothing at the reach (live b14: within 1.10 D_mid over 0.39-0.44 of the arm-to-arm angle,
    the strip gone by ~1.55 D_mid [M b14]). p = 0 keeps v4's quarter ellipse (s = mid + (side - mid)(1 - sqrt(1 -
    t^2)), meeting each arm's sw tangentially: Skye 10-20, the webs "asymptote toward the arms", not "a hard triangle
    cut"; its climb spread over the whole sector)"""
    lam = np.clip(np.asarray(lam, np.float64), 0.0, 1.0)
    t = np.abs(2.0 * lam - 1.0)
    mid = plan['s_mid'][j]
    p = float(plan['wall'][j]) if 'wall' in plan else 0.0
    if p > 0.0:
        return mid + (plan['s_reach'][j] - mid) * t ** p
    order = plan['order']
    side = np.where(lam < 0.5, plan['sw'][order[j]], plan['sw'][order[(j + 1) % N_ARMS]])
    return mid + (side - mid) * (1.0 - np.sqrt(np.clip(1.0 - t * t, 0.0, 1.0)))


def low_spec(spec):
    """the spec the LOW is fitted to: the mantle's free margin (a lip 2.5 mm proud, a groove 1.2 mm deep) is the high's
    alone and bakes into the maps (guide 00.13: under ~8 px a feature is surface, not outline)"""
    return dict(spec, mantle_margin=None)


def build_cage(spec, prog, arms, cage=CAGE, log=print):
    """the designed quad cage, fitted to the SDF.

    BODY loft: rings of K along the body axis from the apex (closed by a quad-grid cap) to the crown top ring, where
    the head meets the crown (each column's rings evenly spaced along it on the shape).
    CROWN, two layers of rows 0..R (columns as the body's: 8 sectors of SECT = arm 2*HALF + web SECT - 2*HALF):
      TOP (aboral): row 0 = the body's last ring; rows run out along each arm's aboral half and over the webs;
      BOTTOM (oral): row 0 = a ring round the mouth (reduction rings, the lip and the opening inside it); rows run out
      under the arms and the webs.
    The WEB MARGIN crosses rows (crown v5): each web's middle columns end on its margin at the row level with the arms'
    rows there, the columns next to the arms climb its walls (a run of rim vertices up the margin), and the arms' side
    columns end their web part where the margin meets the arm (the web's reach) and run on as one column of both
    layers along the arm's bare flank; the rim and these runs are ONE set of vertices shared by both layers (two quads
    per edge; info top / bot hold -1 past a column's end). Row RB (RT on top; RB = R + bot_extra) is each arm tube's
    first ring at sw
    (2 * 2 * HALF = 16 vertices: the interior columns per layer, the side columns shared). Arm tubes run out to
    quad-grid tip caps.
    Returns the fitted QuadMesh and an info dict (ring ids, pinned mask)."""
    from ..mesh import QuadMesh
    K, SECT, HALF, R = cage['K'], cage['SECT'], cage['HALF'], cage['R']
    assert K == N_ARMS * SECT

    def settle(X):
        """points projected onto the shape, set 10 um out along its normal before the fit sees them: one left EXACTLY
        on the zero set (f == 0 in float32, as a bisected projection often leaves it) is thrown through the part when
        the fit projects it again (sdf's k_project takes f0 == 0 for outside, marches inward and finds no sign change
        until the far side: 187 of 1998 points cast onto webs and arms jumped, up to 45 mm, patches/v4_cage/exp_zero)"""
        X = np.atleast_2d(np.asarray(X, np.float64))
        return X + prog.normals(X) * 1.0e-5
    V = []                                   # proxies
    part = []                                # region ids: 0 body, 1 crown top, 2 crown bottom, 3+j arm j
    st = []                                  # (s, cos, sin, side)
    def add(p, reg, s=0.0, th=0.0, side=0.0):
        V.append(np.asarray(p, np.float64))
        part.append(reg)
        st.append((s, np.cos(th), np.sin(th), side))
        return len(V) - 1
    Q = []
    # ---------------------------------------------------------------- BODY
    from .. import sdf as _sdf
    P, n, b, t = body_axis(spec)
    L = np.linalg.norm(np.diff(P, axis=0), axis=1)
    Lt = L.sum()
    sP = np.concatenate([[0], np.cumsum(L)]) / Lt
    s0 = cage['body_s0']
    NB = int(round(Lt * (1 - s0) / cage['body_step'])) + 1
    th = np.arange(K) * (2 * np.pi / K)
    body = np.zeros((NB, K), np.int64)

    def body_ring(s, thetas, radial=False):
        """points on the body sweep at stations s (one, or one per theta), its radius tapered and its section oval as
        build_sdf's sweep (without the taper the crown-top ring stood 14.5 mm off it, v4); past s = 1 over the sweep's
        end hemisphere (its distance there is to the end node). radial: also each point's direction out from the axis"""
        thetas = np.asarray(thetas, np.float64)
        s = np.broadcast_to(np.asarray(s, np.float64), thetas.shape)
        sc = np.minimum(s, 1.0)
        ip = lambda X: np.column_stack([np.interp(sc, sP, X[:, k]) for k in range(3)])
        h = np.maximum(s - 1.0, 0.0) * Lt
        r = body_radius(sc, spec) * body_taper(sc, spec)
        r = np.sqrt(np.maximum(r * r - h * h, 0.0))
        d = np.cos(thetas)[:, None] * ip(n) + (body_aspect(sc, spec) * np.sin(thetas))[:, None] * ip(b)
        p = ip(P) + np.outer(h, t[-1]) + r[:, None] * d
        return (p, d / np.linalg.norm(d, axis=1, keepdims=True)) if radial else p
    # the CROWN-TOP RING, where the loft ends: per column, the first station from which the shape (each station
    # projected radially onto it) stands more than junction_off off the HEAD alone (the sweep, the eye mounds, the head
    # mass and the funnel, blended as build_sdf blends them) for junction_run along the axis: the crown's arms, webs
    # and oral disc have taken over there (the free margin's lip, 2.5 mm proud and ~9 mm wide on the full spec, is no
    # junction). v4's
    # axis turns down through the head, so its ring at s = 1 stands 51 deg off level: the back half lay inside the
    # ventral arms' bases and the oral disc, and the crown's top layer began on the oral side there (t04 v4: 254 body
    # folds, 43 crown top). The ring runs from s 1.06 at the front (over the sweep's end cap to the dorsal arms' tops)
    # to 0.50 at the back, where the ventral arms and the E web rise to the mantle's underside
    head = _sdf.Program()
    head.sweep(P, n, body_radius(sP, spec) * body_taper(sP, spec), a2=0.035, phi2=0.0, a4=0.012,
               aspect=body_aspect(sP, spec))
    for side in (1, -1):
        head.ellipsoid(eye_geom(spec, side)[0], [spec['eye_r'] * 1.08, spec['eye_r'], spec['eye_r'] * 1.08], k=0.014)
    ye, ze = eye_level(spec)
    TD = 2.0 * 1.08 * spec['eye_r']
    hc, hr, hk = head_mass(spec)
    head.ellipsoid(hc, hr, k=hk)
    # the funnel is the head's too (the body grid carries its port): without it the walk stopped on the funnel's
    # flank and the crown-top ring rode up onto it, into the port's block (61 folds, v4 funnel on the flank)
    fa_, fb_, fra_, frb_ = funnel_geom(spec)
    head.roundcone(fa_, fb_, fra_, frb_, k=0.008)
    # and the mantle's seat (crown v5): the mantle's underside runs on over it into the fold, so the ring at the back
    # stands where the crown's back face takes over, with the free margin's lip (the high's, 2.5 mm proud) on the body
    # grid behind it (at v4's ring, on the lip, the junction quads bridged the fold under it: bake_misses C)
    if getattr(prog, 'seat', None) is not None:
        head.begin_group(k=0.003)
        for c_, r_ in zip(*prog.seat):
            head.ellipsoid(c_, [r_, r_, r_])
        head.end_group()
    ss = np.arange(cage['lean_s0'], 1.2, 0.001 / Lt)                  # 1 mm stations
    Sg, Tg = np.meshgrid(ss, th, indexing='ij')
    pts, dirs = body_ring(Sg.ravel(), Tg.ravel(), radial=True)
    q, stq = prog.project(pts, dirs, maxd=0.05)
    off = ((head.eval(q) > cage['junction_off']) | (stq != 0)).reshape(len(ss), K)
    run = int(round(cage['junction_run'] / 0.001))
    cs = np.vstack([np.zeros((1, K), np.int64), np.cumsum(off, axis=0)])
    held = (cs[run:] - cs[:-run]) == run                               # off for the whole run from here
    s_raw = ss[np.where(held.any(0), held.argmax(0), len(held) - 1)]
    # mirrored (the body is), then smoothed: cosines up to the 3rd harmonic, lowered so the ring stays on the head side
    # of the junction everywhere (a ring past it lands on the crown's fillet, and the top layer's lead rows fold back)
    s_raw = 0.5 * (s_raw + s_raw[(K - np.arange(K)) % K])
    A = np.column_stack([np.cos(m * th) for m in range(4)])
    fit = A @ np.linalg.lstsq(A, s_raw, rcond=None)[0]
    s_end = fit - max(0.0, float((fit - s_raw).max()))
    # the rings LEAN from lean_s0 on (perpendicular to the axis behind it, as the apex's reduction rings are), and from
    # there each column's rings lie EVENLY SPACED ON THE SHAPE along it to the crown-top ring (stations even in s put
    # the dorsal rings 12 mm apart over the turrets' saddle and the ventral ones 1.9 mm apart, v4)
    v = np.linspace(s0, 1.0, NB)
    il = int(np.searchsorted(v, cage['lean_s0'] - 1e-9))              # the first leaning ring
    u = np.linspace(0.0, 1.0, 400)[:, None]
    Sg = v[il] + u * (s_end[None, :] - v[il])                          # (400, K) stations on to the crown-top ring
    pts, dirs = body_ring(Sg.ravel(), np.tile(th, len(u)), radial=True)
    q, stq = prog.project(pts, dirs, maxd=0.05)
    q = np.where((stq == 0)[:, None], q, pts).reshape(len(u), K, 3)
    arc = np.vstack([np.zeros((1, K)), np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=2), axis=0)])
    S_body = np.repeat(v[:, None], K, axis=1)
    even = np.linspace(0.0, 1.0, NB - il)
    for k in range(K):
        S_body[il:, k] = np.interp(even * arc[-1, k], arc[:, k], Sg[:, k])
    assert np.all(np.diff(S_body, axis=0) > 0.0), 'the body rings cross'
    # the rings' vertices projected RADIALLY onto the shape, each out along its own column: over the eye turrets and the
    # head mass a column stays a column (the eye blocks are chosen on this grid as it lies on the shape)
    pts, dirs = body_ring(S_body.ravel(), np.tile(th, NB), radial=True)
    q, stq = prog.project(pts, dirs, maxd=0.05)
    pos = np.where((stq == 0)[:, None], settle(q), pts).reshape(NB, K, 3)
    for i in range(NB):
        for k in range(K):
            body[i, k] = add(pos[i, k], 0, min(S_body[i, k], 1.0), th[k])
    for i in range(NB - 1):
        for k in range(K):
            k1 = (k + 1) % K
            Q.append([body[i, k], body[i, k1], body[i + 1, k1], body[i + 1, k]])
    # ---------------------------------------------------------------- CROWN
    azs = arm_azimuths()
    # arm j around the crown (theta = -azimuth): column centre SECT / 2 + SECT j
    theta_arm = np.mod(-np.degrees(azs), 360.0)
    order = np.argsort(theta_arm)            # j -> index into arms
    cy = spec['crown_y']
    plan = web_plan(spec, arms)
    sw = plan['sw']                          # per arm: its tube's start (its side lines' reach at the tube's first ring)
    depth_web = plan['d_mid']                # per web: its mid-sector depth (the fold's scale, web_fold_half)
    mouth_p = mouth_point(spec)
    up = np.array([0.0, 1.0, 0.0])

    def arm_frame(a, s):
        Pa, na, ba, ta = arms[a]
        sa = np.linspace(0, 1, len(Pa))
        ip = lambda X: np.array([np.interp(s, sa, X[:, k]) for k in range(3)])
        return ip(Pa), ip(na), ip(ba), ip(ta), arm_radius(np.array([s]), spec)[0]

    def col_info(k):
        """sector j, and either ('arm', offset -HALF..HALF) or ('web', lambda in (0,1))"""
        j = int(((k - (SECT // 2 - HALF)) // SECT)) % N_ARMS        # sector start = arm's left side column
        c = SECT // 2 + SECT * j                                      # arm centre column
        o = (k - c + K // 2) % K - K // 2
        if -HALF <= o <= HALF:
            return j, 'arm', o
        lam = (o - HALF) / (SECT - 2 * HALF)
        return j, 'web', lam

    def layout(layer, k, s_first, frac):
        """crown vertex (layer 'top'|'bot', column k) on its arm or web, the share frac of the way from s_first out to
        the margin: its position, (sector, s, alpha) and the ray it projects along, as the fit projects it (on an arm
        NaN: the field's gradient, its nearest surface; on a web its normal; on the margin out in the web's plane)"""
        j, kind, val = col_info(k)
        a = order[j]
        if kind == 'arm':
            s = s_first + (sw[a] - s_first) * frac
            c, na, ba, ta, ra = arm_frame(a, s)
            # inside the web zone the web ATTACHES along the arm's side line: the top layer's half-ring spans
            # +-(90 - delta) (above the attachment), the bottom's 90 + delta .. 270 - delta (below it); delta tapers
            # to 0 where the web's margin meets the arm (t04: both side lines started at the same proxy and collapsed
            # together, folding the corner quads). Crown v5: at the reach of the web on that side (offset > 0: web j,
            # the arm's +b side; < 0: web j - 1), the two side lines one line beyond it, the arm's bare flank out to sw
            jw = j if val > 0 else (j - 1) % N_ARMS
            s_end = plan['s_reach'][jw] if val != 0 else sw[a]
            delta = cage['side_delta'][layer == 'bot']
            fr_ = float(np.clip((s - s_first) / max(s_end - s_first, 1e-9), 0.0, 1.0))
            if cage.get('side_fillet') is not None and val != 0:
                # where the web's faces meet the arm: its own half-thickness there (web_fold_half) and the webs' blend
                # off the side line, or side_delta on a quadratic taper where that is more: a linear 30 / 40 deg taper
                # ran the side lines 6 mm down the arm's flank in the membrane zone, and the wall's strip quads from
                # there to the rim bridged the crotch, up to 4.6 mm off the shape; by the web alone they met the rim
                # near the walls' foot and one folded (the E web)
                d_ = depth_web[jw]
                u_ = np.linalg.norm(c + ba * ra * np.sign(val) - mouth_p) / d_
                h_ = float(web_fold_half(spec, u_, min(s / max(s_end, 1e-9), 1.0))) + cage['side_fillet']
                d_web = min(delta, float(np.degrees(np.arcsin(min(h_ / ra, 1.0)))))
                delta = max(d_web * (1.0 - fr_), delta * (1.0 - fr_) ** 2)
            else:
                delta = delta * (1.0 - fr_)
            half = 90.0 - delta
            alpha = np.radians(val * half / HALF) if layer == 'top' else np.radians(180.0 - val * half / HALF)
            return c + 1.05 * ra * (np.cos(alpha) * na + np.sin(alpha) * ba), (j, s, alpha), np.full(3, np.nan)
        an = order[(j + 1) % N_ARMS]
        # a wall column (next to an arm) bends toward its neighbour on the way out and meets the margin at lam_end,
        # where its run up the wall begins (the U's corner: a run from its own lam left the chord from the bottom's
        # last rim vertex 30 mm long, 0.4 mm outside the membrane at the E web)
        lam_end = wall_lam(val)
        lam = val + (lam_end - val) * min(frac, 1.0) ** 2
        if layer == 'bot' and cage.get('bot_wall_lam', 1.0) != 1.0 and abs(lam_end - val) > 1.0e-12:
            # (Stage 4) the bottom's wall column starts bot_wall_lam of its lam from its arm's side line, into the
            # crotch, and sweeps out to the same lam_end at the margin (its run up the wall, shared, as before)
            l0 = val * cage['bot_wall_lam'] if val < 0.5 else 1.0 - (1.0 - val) * cage['bot_wall_lam']
            lam = l0 + (lam_end - l0) * min(frac, 1.0) ** 2
        sm = margin_s(lam_end, plan, j)
        s = s_first + (sm - s_first) * frac
        c1, n1, b1, t1, r1 = arm_frame(a, s)
        c2, n2, b2, t2, r2 = arm_frame(an, s)
        p = (1 - lam) * (c1 + b1 * r1) + lam * (c2 - b2 * r2) + up * float(web_lift(spec, plan, j, lam, s))
        meta = (j, s, np.pi / 2 if layer == 'top' else -np.pi / 2)
        if frac < 1.0:
            # lifted off the web's plane (vanishing at the arms' side lines, where the arm's flank would win the
            # projection: t04), then ray-projected along the web's normal
            lift = (0.008 if layer == 'top' else -0.008) * (1.0 - frac * 0.7) * 4.0 * lam * (1.0 - lam)
            return p + up * lift, meta, (up if layer == 'top' else -up)
        # on the margin: the web patch's own boundary point, between the same side lines web_patch spans (the rim
        # vertex is kept there, on the membrane's mid-surface; the ray out in the web's plane is the rim's direction)
        return p, meta, margin_dir(k)

    def margin_dir(k):
        """the in-plane outward direction at a margin vertex: the two arms' tangents blended"""
        j, kind, val = col_info(k)
        a, an = order[j], order[(j + 1) % N_ARMS]
        lam = val if kind == 'web' else 0.0
        s = margin_s(lam, plan, j)
        _, _, _, t1, _ = arm_frame(a, s)
        _, _, _, t2, _ = arm_frame(an, s)
        d = (1 - lam) * t1 + lam * t2
        return d / np.linalg.norm(d)

    # crown v5: the MARGIN CROSSES ROWS. Each web's columns end where they meet its margin, the rows held level with
    # the arms' (v4 ended every column on one margin row: an arm's side column at sw 0.335, the A web's first column at
    # its margin 0.16, the quads between them 70-112 mm out of step and folded along their diagonals, bake_misses A1 /
    # A2). The web columns next to the arms (lam LAM1, 1 - LAM1) climb the margin's WALLS: past the bottom's row they
    # run up along the margin to the arm (a run of rim vertices); the arm's side columns end their web part at the
    # web's reach (the meeting point) and run on as ONE column of both layers along the arm's bare flank to sw
    LAM1 = 1.0 / (SECT - 2 * HALF)

    def wall_lam(val):
        """where a web column meets the margin: its own lam, but a wall column's wall_from of the way toward its
        neighbour's lam"""
        if abs(val - LAM1) < 1e-9 or abs(val - (1.0 - LAM1)) < 1e-9:
            return val + np.sign(0.5 - val) * cage.get('wall_from', 0.0) * LAM1
        return val

    def margin_point(j, lam):
        """web j's own boundary point at lam (the membrane's mid-surface, between web_patch's side lines, lifted as
        web_patch lifts it: web_lift)"""
        a, an = order[j], order[(j + 1) % N_ARMS]
        sm = float(margin_s(lam, plan, j))
        c1, n1, b1, t1, r1 = arm_frame(a, sm)
        c2, n2, b2, t2, r2 = arm_frame(an, sm)
        return (1 - lam) * (c1 + b1 * r1) + lam * (c2 - b2 * r2) + up * float(web_lift(spec, plan, j, lam, sm))

    def wall(j, near_a):
        """web j's margin WALL from where its column next to the arm meets the margin (wall_lam) out to that arm's side
        line at the web's reach (lam 0, or 1): dense points on the patch's edge, their arclengths and their lam"""
        l0 = wall_lam(LAM1)
        lw = l0 * (1.0 - np.linspace(0.0, 1.0, 241)) if near_a else 1.0 - l0 * (1.0 - np.linspace(0.0, 1.0, 241))
        Wp = np.array([margin_point(j, l) for l in lw])
        return Wp, np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Wp, axis=0), axis=1))]), lw

    def rim_triple(j, lam, got=None, end=False):
        """the RIM STRIP at web j's margin point lam (crown v5b): S on the membrane's mid-surface edge p (crown v5's rim
        vertex: the high's rim is a half-cylinder of the margin's half-thickness h round it), T and B on the top and
        bottom faces h in from the edge (the shape's zero along the membrane's normal n from p - h o, o its outward
        in-plane direction perpendicular to the margin): a 45 deg wedge inscribed in the rounded rim. One shared rim
        row made a knife edge whose welded normals averaged the two faces: 98 deg off the top faces' (p50, canonical
        and crown v5 alike), so the top layer's last row searched and re-found its base point through the membrane's
        far face (crown v5's 41,037 crown-top texels with the base point lost, the dark torn rim of probe 3); T's normal
        now leans on the top faces, B's on the bottom's, and the strip between them faces out over the apex. Inset, its
        chords stay on the membrane: the U's margin is convex in lam, so a chord between two rim points runs out into
        the notch (up to 1.03 mm past the apex with S on it; on the mid-surface +0.18 mm, crown v5's). Returns the
        three vertex ids (T, S, B; fixed: designed on the shape, judged by t04). got: the point's frame (rim_frame) and
        its two projections, made beforehand with every rim point's in one launch (crown v5c; None: made here). end: a
        wall's last point, beside its meeting point (crown v5c): T and B straight over and under the edge (no inset)"""
        sm, p, x0, h_, D = rim_frame(j, lam, end) if got is None else got[0]
        q_, s_ = prog.project(np.tile(x0, (2, 1)), D, maxd=0.01) if got is None else got[1]
        q_ = np.where((s_ == 0)[:, None], q_, x0 + h_ * D)
        ids = []
        for qq_, reg_ in zip((q_[0], p, q_[1]), (1, 1, 2)):
            ids.append(add(qq_, reg_, sm, np.pi / 2, 0.5))
            pinned.append(ids[-1])
            rim_fixed.append(ids[-1])
        return ids

    def rim_frame(j, lam, end=False):
        """rim_triple's margin point at web j's lam: its share sm along the arms, the point p, the projections' start p
        - h o (a wall's last point, end: p itself), the half-thickness h and the membrane's normals (n, -n)"""
        a, an = order[j], order[(j + 1) % N_ARMS]

        def cpt(l, s):
            c1, n1, b1, t1, r1 = arm_frame(a, s)
            c2, n2, b2, t2, r2 = arm_frame(an, s)
            return (1 - l) * (c1 + b1 * r1) + l * (c2 - b2 * r2) + up * float(web_lift(spec, plan, j, l, s))
        el, es = 1.0e-3, 1.0e-3
        lo, hi = max(lam - el, 0.0), min(lam + el, 1.0)
        sm = float(margin_s(lam, plan, j))
        p = cpt(lam, sm)
        d_l = (cpt(hi, sm) - cpt(lo, sm)) / (hi - lo)                  # the patch's tangents: across the web (lam)
        d_s = (cpt(lam, sm + es) - cpt(lam, sm - es)) / (2.0 * es)     # and out along the arms (s)
        n = np.cross(d_l, d_s)
        n /= np.linalg.norm(n)
        if n[1] < 0.0:
            n = -n
        t_m = margin_point(j, hi) - margin_point(j, lo)                 # along the margin
        o = np.cross(n, t_m)
        o /= np.linalg.norm(o)
        # outward: the parameter plane's outward normal (-ds/dlam, 1) of the margin s(lam), mapped by the patch
        dm = (float(margin_s(hi, plan, j)) - float(margin_s(lo, plan, j))) / (hi - lo)
        if np.dot(o, d_s - dm * d_l) < 0.0:
            o = -o
        h_ = float(web_fold_half(spec, np.linalg.norm(p - mouth_p) / depth_web[j], 1.0))
        # (crown v5c) beside a meeting point the margin runs within a millimetre or two of the arm's side line (the U's
        # wall meets it at a few degrees) and the inset points at the arm: by the full h a wall's last T and B stood on
        # the side column's line, so the grid quads reaching the meeting point split into triangles edge-on to the web
        # (inside out, 4-6 mm2 at the A web). There T and B stand straight over and under the edge
        return sm, p, p - (0.0 if end else h_) * o, h_, np.array([n, -n])

    def arm_point(a, s, alpha):
        """a point 1.05 local radii out from arm a's centreline at s, angle alpha (0 aboral, +90 the +b side)"""
        c, na, ba, ta, ra = arm_frame(a, s)
        return c + 1.05 * ra * (np.cos(alpha) * na + np.sin(alpha) * ba)

    def col_role(k):
        """(kind, web j, side): 'side' (an arm's side column: its web j, the arm's side +1 / -1), 'wall' (a web column
        next to an arm: its web, near arm a +1 or arm an -1), 'web' (a web's middle columns), 'arm' (an arm's interior)"""
        j, kind, val = col_info(k)
        if kind == 'arm':
            if abs(val) == HALF:
                return ('side', j if val > 0 else (j - 1) % N_ARMS, 1 if val > 0 else -1)
            return ('arm', j, 0)
        if abs(val - LAM1) < 1e-9:
            return ('wall', j, 1)
        if abs(val - (1.0 - LAM1)) < 1e-9:
            return ('wall', j, -1)
        return ('web', j, 0)

    LEAD = cage['top_lead']
    SUP = int(cage.get('support_rows', 0))   # (crown v5d) and SUP support rows (pinned on the back band's folds,
    RT = R + LEAD + SUP                      # support_plan): the top layer's rows, LEAD + SUP more than the bottom's
    RB = R + int(cage.get('bot_extra', 0))   # (Stage 4) the bottom layer's rows: bot_extra more inside its shared runs
    NR = {'top': RT, 'bot': RB}
    top = np.full((RT + 1, K), -1, np.int64)              # -1: past the column's end (the margin crosses rows)
    bot = np.full((RB + 1, K), -1, np.int64)
    top[0] = body[-1]
    # bottom row 0: a ring round the mouth (the reduction rings inside it come after)
    mouth_c = np.array([0.0, cy - 0.034, 0.0])

    def mouth_ring(radius, thetas):
        az = -np.asarray(thetas)
        return mouth_c + radius * np.column_stack([np.sin(az), np.zeros_like(az), np.cos(az)])
    mr = mouth_ring(cage['mouth_r'][0], th)
    for k in range(K):
        bot[0, k] = add(mr[k], 2, 0.0, th[k])
    rim_fixed = []                           # the rim vertices (the webs' and the walls' runs), on the patch's edge (fixed)
    pinned = []
    first_dirs = {}                          # vertex -> its first projection's direction (the rim's: in-plane out)
    # each column's rows along its own path out to the margin, EVEN along it and, in the top layer, held level with the
    # neighbouring columns' rows (row_stations). The arm layout holds only where the eight
    # arms' side lines have parted, open_r out from the mouth's axis (inside it a side point of one arm lies past its
    # neighbour's and the columns cross: t04's folds round the mouth), and the top layer's only where its arm or web
    # has come out from under the head ring. So the TOP path runs from the head ring's vertex over the junction (on
    # the shape) to the layout's start, then out; the BOTTOM path from the mouth ring out along the oral surface
    # (polar, by azimuth, on the shape: rays down from inside the oral disc) to open_r, then on to the layout and out.
    # Rows by count from fixed starts (top_s0, bot_s0, five polar rows) were crushed where v4's shallow webs end just
    # past them: the A web's margin 7 mm beyond top_s0 with 11 rows in it (t04 v4: quads 125:1 at its midline, rows
    # 0-2 mm apart, while the arms' rows ran 17-30 mm and the lead band 85 mm in 4)
    H = np.array([V[i] for i in top[0]])
    rho_p = np.linspace(cage['mouth_r'][0], cage['open_r'], 9)[1:]
    pol0 = np.array([[rh * np.sin(-th_), cy - 0.010, rh * np.cos(-th_)] for th_ in th for rh in rho_p])
    polar, _ = prog.project(pol0, np.tile(-up, (len(pol0), 1)), maxd=0.06)       # (the oral disc's centre height)
    polar = settle(polar).reshape(K, len(rho_p), 3)
    fs = np.linspace(0.0, 1.0, 65)
    starts = {'top': np.zeros(K), 'bot': np.zeros(K)}       # each column's layout start (s), per layer

    def cast(X, D):
        """points projected onto the shape as the fit's first pass projects them (along D, or the field's gradient
        where D is NaN), settled. The junction's lines and each layout's start use it; the rows themselves stay
        proxies for the fit: projected here too, the preserving fit kept 8-10 folds in the top layer against 2 (t04 v4;
        it keeps the proxies' differential layout)"""
        X, D = np.atleast_2d(X), np.atleast_2d(D)
        D = np.where(np.isnan(D[:, :1]), prog.normals(X), D)
        q_, s_ = prog.project(X, D, maxd=0.06)
        return np.where((s_ != 2)[:, None], settle(q_), X)

    def batched(gens):
        """drive generators in LOCKSTEP (crown v5c): each yields ('eval', X), ('normals', X) (crown v5d) or ('cast', X,
        D) and is sent the answer (prog.eval's values, prog.normals', cast's points); every round answers all the
        requests pending of one kind in ONE launch (the kernels work per point, so each point gets exactly what it got
        alone: the cage is byte for byte the same). Returns the generators' return values. Each column's path cast
        alone took 3,312 launches of ~9 points on the GPU, 103 s of t10's 163 s cage step (crown v5b)"""
        res, todo = [None] * len(gens), {}

        def step(i, ans):
            try:
                todo[i] = gens[i].send(ans)
            except StopIteration as e:
                res[i] = e.value
                todo.pop(i, None)
        for i in range(len(gens)):
            step(i, None)
        while todo:
            now, ans = dict(todo), {}
            for kind in ('eval', 'normals', 'cast'):
                ids = [i for i in now if now[i][0] == kind]
                if not ids:
                    continue
                X = [np.atleast_2d(now[i][1]) for i in ids]
                cut = np.cumsum([0] + [len(x) for x in X])
                got = prog.eval(np.concatenate(X)) if kind == 'eval' else prog.normals(np.concatenate(X)) \
                    if kind == 'normals' else \
                    cast(np.concatenate(X), np.concatenate([np.atleast_2d(now[i][2]) for i in ids]))
                ans.update({i: got[cut[n_]:cut[n_ + 1]] for n_, i in enumerate(ids)})
            for i in now:
                step(i, ans[i])
        return res

    def column_path(layer, k):
        """the column's path from its row 0 over the junction to the layout's start and out along the layout to the
        margin (an arm column: to sw), and a wall column's on up the margin's wall to its arm: a dict of path, cum (its
        arclength, the bottom's polar part counted polar_w times), nl (path[nl] is the layout's start, frac 0), nlay
        (path[nlay] its end, frac 1), s_first (the layout's start s), L_line (cum at nlay), and for a wall column the
        wall (Wp, Wc: points, arclengths), for a side column L_meet (cum where the layout reaches the web's reach).
        A generator (crown v5c): it yields its eval and cast requests and `batched` answers every column's at once"""
        j, kind, val = col_info(k)
        s_m = sw[order[j]] if kind == 'arm' else float(margin_s(wall_lam(val), plan, j))
        ss_ = np.linspace(0.0, s_m, 121)
        C0 = np.array([layout(layer, k, s_, 0.0)[0] for s_ in ss_])
        # the layout starts where it describes the shape: past open_r, its proxies CLEAR of the shape (a web's lifted
        # point off the membrane, an arm's 1.05 r point outside the tube) for a run of stations. Nearer the head they
        # lie inside the webs' and arms' blended roots: the D web's first proxies 8-11 mm under its top, cast up onto
        # it, landed on the junction's last row and folded it (t04 v4)
        clear = (np.linalg.norm(C0[:, [0, 2]], axis=1) >= cage['open_r']) & ((yield ('eval', C0)) > -cage['layout_in'])
        held = clear[:-3] & clear[1:-2] & clear[2:-1] & clear[3:]
        s_first = ss_[int(np.argmax(held))] if held.any() else 0.6 * s_m
        if layer == 'top':
            # and out past its head ring vertex: at the back the ring lies on the mantle's underside, 100 mm out, past
            # the ventral arms' roots, and a path running in to them before out along them folded back (t04 v4)
            past = np.nonzero(np.linalg.norm(C0[:, [0, 2]], axis=1) >= np.linalg.norm(H[k, [0, 2]]) + 0.005)[0]
            s_first = max(s_first, ss_[int(np.argmin(np.linalg.norm(C0 - H[k], axis=1)))],
                          ss_[past[0]] if len(past) else ss_[-2])
        s_first = min(s_first, 0.9 * s_m)
        starts[layer][k] = s_first
        p0, _, d0 = layout(layer, k, s_first, 0.0)
        start = (yield ('cast', p0, d0))[0]
        # the JUNCTION on the shape, from the head ring (top) or the polar rows' end (bottom) to the layout's start:
        # straight, bulged out a little (top), cast up and out onto the top surface or down onto the oral one (left to
        # the fit's gradient, a point of it inside an arm's root dropped 15 mm onto its underside and folded, t04 v4)
        a0 = H[k] if layer == 'top' else polar[k][-1]
        u_j = np.linspace(0.0, 1.0, 12)[1:-1, None]
        J = (1.0 - u_j) * a0 + u_j * start
        hz = J * np.array([1.0, 0.0, 1.0])
        hz /= np.maximum(np.linalg.norm(hz, axis=1, keepdims=True), 1e-9)
        i_crease = crease_pt = fine = None
        if layer == 'top' and (yield ('eval', J)).max() > cage.get('fold_air', 1.0e9):
            # a CONCAVE junction (crown v5): the straight line runs through air, under the fold where the mantle rests
            # on the crown's back face; each point goes onto its nearest surface, so the line turns the fold's corner
            # (bulged out and cast up and out, as over the arms' roots in front, it ran under the corner 6-8 mm off the
            # shape: the junction quads bridging it, bake_misses C); then RELAXED on the surface, each point the
            # nearest surface point of its neighbours' midpoint, even by arclength, so the line hugs the fold's crease
            # as a geodesic does (cast alone, every point of it landed on the nearer back face and the line still
            # jumped the corner at the midline)
            nan3 = np.full((len(J), 3), np.nan)
            Jl = np.vstack([a0[None], (yield ('cast', J, nan3)), start[None]])
            for _ in range(cage.get('fold_relax', 24)):
                Jl[1:-1] = yield ('cast', 0.5 * (Jl[:-2] + Jl[2:]), nan3)
                cl_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Jl, axis=0), axis=1))])
                Jl[1:-1] = np.column_stack([np.interp(np.linspace(0.0, cl_[-1], len(Jl))[1:-1], cl_, Jl[:, d])
                                            for d in range(3)])
            J = yield ('cast', Jl[1:-1], nan3)
            # the fold's CREASE: where the line turns most sharply INTO the shape (its neighbours' midpoint in air; a
            # row is pinned there: row_plan). The farthest point from the chord took the back face's bulge below it
            Jl = np.vstack([a0[None], J, start[None]])
            e0, e1 = Jl[1:-1] - Jl[:-2], Jl[2:] - Jl[1:-1]
            turn = np.arccos(np.clip((e0 * e1).sum(1) / np.maximum(np.linalg.norm(e0, axis=1) *
                                                                   np.linalg.norm(e1, axis=1), 1e-18), -1.0, 1.0))
            turn = np.where((yield ('eval', 0.5 * (Jl[:-2] + Jl[2:]))) > 0.0, turn, 0.0)
            # (on the webs' and the arms' side columns only: the fold over the E web; pinned on the back arms' own
            # columns too, the top island's inner edge touched itself in UV, 1-3 texels)
            if turn.max() > np.radians(cage.get('fold_turn', 45.0)) and col_role(k)[0] != 'arm':
                i_crease = 1 + int(np.argmax(turn))
                crease_pt = Jl[i_crease].copy()
            if cage.get('support_rows', 0):
                # the fold's PROFILE (crown v5d; the back band's columns take it as their lead, relead): the line cut
                # support_fine times a step and relaxed again on the surface IN ITS PLANE (the coarse line's
                # least-squares plane: each point cast onto the shape along the field's gradient's part in it), so the
                # rows set along it lie on the fold's section (its steps of 4-7 mm chorded it: at the E web the line
                # ran from the seat's edge to the back face's foot 3-5 mm under the corner, the rows between,
                # interpolated on it, in the air). The corner and the crease stay the coarse line's
                ctr = Jl.mean(0)
                pn = np.linalg.svd(Jl - ctr)[2][2]
                inpl = lambda X: X - ((X - ctr) @ pn)[:, None] * pn[None]
                nf_ = int(cage.get('support_fine', 8))
                u_f = (np.arange(nf_) / nf_)[:, None]
                Jf = np.vstack([Jl[i] + u_f * (Jl[i + 1] - Jl[i]) for i in range(len(Jl) - 1)] + [Jl[-1:]])
                n_rel = cage.get('fold_relax', 24)
                for r_ in range(n_rel + 2):
                    X = inpl(0.5 * (Jf[:-2] + Jf[2:]) if 0 < r_ <= n_rel else Jf[1:-1])
                    G = yield ('normals', X)
                    Jf[1:-1] = yield ('cast', X, G - (G @ pn)[:, None] * pn[None])
                    if 0 < r_ <= n_rel:
                        cl_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Jf, axis=0), axis=1))])
                        Jf[1:-1] = np.column_stack([np.interp(np.linspace(0.0, cl_[-1], len(Jf))[1:-1], cl_,
                                                              Jf[:, d]) for d in range(3)])
                fine = Jf[1:-1].copy()
        else:
            if layer == 'top':
                J, d_ = J + hz * 0.006 * np.sin(np.pi * u_j), hz + up
            else:
                d_ = np.tile(-up, (len(J), 1))
            J = yield ('cast', J, d_ / np.linalg.norm(d_, axis=1, keepdims=True))
        lead = ([H[k]] if layer == 'top' else [mr[k]] + list(polar[k])) + list(J) + [start]
        # the layout's own part measured along its curve (smooth, near the shape), set on its projected start.
        # Measured on the projected curve instead, the rows piled into its jumps where a point near the root landed on
        # another sheet (t04 v4: 226 folds)
        Lp = np.array([layout(layer, k, s_first, f_)[0] for f_ in fs])
        path = np.vstack(lead + list(Lp[1:] - Lp[0] + start))
        nlay = len(path) - 1
        role, jr, sd = col_role(k)
        out = dict(nl=len(lead) - 1, nlay=nlay, s_first=s_first)
        if role == 'wall':
            # on up the margin's wall to the arm (the run of rim vertices: build_cage's row plan)
            Wp, Wc, Wl = wall(jr, sd > 0)
            path = np.vstack([path, Wp[1:] - Wp[0] + path[-1]])
            out.update(Wp=Wp, Wc=Wc, Wl=Wl)
        seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
        if layer == 'bot':
            # the polar part counted polar_w times: round the mouth the columns stand 1.3-3.7 mm apart, and evenly
            # spaced its rows made a band of 1.3 x 21 mm slivers out of the mouth ring that LSCM laid over itself
            # (t08 v4: 54 texels in six of the bottom's sectors)
            seg[:len(polar[k])] *= cage['polar_w']
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        out.update(path=path, cum=cum, L_line=float(cum[nlay]))
        if i_crease is not None:
            out['crease'] = float(cum[i_crease])
        if fine is not None:
            out.update(fine=fine, crease_pt=crease_pt)      # (crown v5d: the fold's profile, relead)
        if role == 'side':
            # where the layout (s_first .. sw, even in s over fs) reaches the web's reach on this side
            f_m = np.clip((plan['s_reach'][jr] - s_first) / max(sw[order[j]] - s_first, 1e-9), 0.0, 1.0)
            out['L_meet'] = float(np.interp(out['nl'] + f_m * (len(fs) - 1), np.arange(len(cum)), cum))
        return out

    def column_rows(layer, k, col, a):
        """the column's rows at the stations a along its path (col: column_path's), each (position, (s, alpha), on the
        layout); a station past the layout's end lies on a wall column's wall"""
        path, cum, nl, nlay, s_first = col['path'], col['cum'], col['nl'], col['nlay'], col['s_first']
        rows_ = []
        for a_ in a:
            if a_ > cum[nlay] + 1e-12 and 'Wp' in col:
                w_ = a_ - cum[nlay]
                p_ = np.array([np.interp(w_, col['Wc'], col['Wp'][:, d_]) for d_ in range(3)])
                rows_.append((p_, (0.0, th[k]), True))
                continue
            i_ = min(int(np.searchsorted(cum[:nlay + 1], a_, side='right')) - 1, nlay - 1)
            u_ = (a_ - cum[i_]) / max(cum[i_ + 1] - cum[i_], 1e-12)
            if i_ >= nl:
                p_, (jj, s_, al), _ = layout(layer, k, s_first, fs[i_ - nl] + u_ * (fs[1] - fs[0]))
                rows_.append((p_, (s_, al), True))
            else:
                rows_.append(((1.0 - u_) * path[i_] + u_ * path[i_ + 1], (0.0, th[k]), False))
        return rows_

    def row_stations(cols, plan_rows, hold):
        """every column's rows as stations along its path: plan_rows[k] = (n, f, fixed): the column's last row n, its
        first FIXED row f and the fixed stations of rows f..n (shared with the other layer: a rim vertex, a wall's run, a
        side column's meeting point and its run along the arm, an arm tube's first ring). Rows 1..f - 1 are solved:
        EVEN along each column up to row f, but held level with the neighbouring columns' rows where both have them and
        the columns run close. Least squares over the whole layer: each step's departure from its column's even step,
        relative to it, and each row's shear against the next column's (the difference of their stations, both measured
        from row 0) over the columns' spacing there, row_hold times. Rows by each column's own arclength alone put
        neighbours out of step wherever their paths differ in length: an arm's side column runs 330 mm out along the
        arm, the A web's first column 180 mm, its middle one 110 mm, so the A web's columns, 2.3 mm apart at its root,
        met their rows 21 mm out of step (t04 v4 check: its 2 folds and 142 crown-top quads under 10 deg, r4's cage
        none; held, 0 folds and 44, most where a web's rim runs onto its arm). Returns per column the stations of its
        rows 1..n"""
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import spsolve
        n_ = np.array([p_[0] for p_ in plan_rows])
        f_ = np.array([p_[1] for p_ in plan_rows])
        Sf = np.array([p_[2][0] for p_ in plan_rows])                  # each column's first fixed station (row f)
        inner = [p_[3] if len(p_) > 3 else {} for p_ in plan_rows]     # rows pinned before f (a fold's crease)
        h = Sf / f_
        even = [np.arange(1, f_[k]) * h[k] for k in range(K)]          # rows 1 .. f - 1: even up to row f
        for k in range(K):
            for r, st_ in inner[k].items():
                even[k][r - 1] = st_
        full = lambda k, x: np.concatenate([x, plan_rows[k][2]])       # rows 1 .. n
        if not hold:
            return [full(k, even[k]) for k in range(K)]
        at = lambda c_, a: np.column_stack([np.interp(a, c_['cum'], c_['path'][:, d_]) for d_ in range(3)])

        def to_path(X, Pn):
            """each point's distance to a polyline"""
            A0, AB = Pn[:-1], Pn[1:] - Pn[:-1]
            t_ = np.clip(((X[:, None] - A0[None]) * AB[None]).sum(2) / np.maximum((AB * AB).sum(1), 1e-18)[None], 0, 1)
            return np.linalg.norm(X[:, None] - (A0[None] + t_[..., None] * AB[None]), axis=2).min(1)
        # the unknowns: rows 2 .. f - 1 of every column (row 1 keeps its even station: below)
        idx, nu = {}, 0
        for k in range(K):
            for r in range(2, f_[k]):
                if r not in inner[k]:
                    idx[(k, r)] = nu
                    nu += 1

        def station0(k, r):
            """row r's starting station (even, pinned, or fixed)"""
            return even[k][r - 1] if r < f_[k] else plan_rows[k][2][r - f_[k]]
        rows_i, cols_i, vals, rhs = [], [], [], []
        ne = 0

        def term(coefs, b):
            """one equation: sum c x (+ the known stations moved to the right) = b"""
            nonlocal ne
            bb = b
            for (k, r), c in coefs:
                if r == 0:
                    continue
                if (k, r) in idx:
                    rows_i.append(ne)
                    cols_i.append(idx[(k, r)])
                    vals.append(c)
                else:
                    bb -= c * station0(k, r)
            rhs.append(bb)
            ne += 1
        # each step over its column's even one, up to row f
        for k in range(K):
            for r in range(f_[k]):
                term([((k, r + 1), 1.0 / h[k]), ((k, r), -1.0 / h[k])], 1.0)
        # row 1 off row 0 keeps its even station and the hold eases in over rows 2 and 3 (held, row 1 over the arms 2
        # rose from 15-20 mm under the head ring to 11-12 and the ring's band there tilted 82 deg, t04 v4 check); the
        # columns' spacing: each row point's distance to the next column's path and back, averaged (one way only, a
        # pair and its mirror image were weighed differently and the solve came out lopsided, t04 v4 check)
        for k in range(K):
            k1 = (k + 1) % K
            rr = np.arange(2, min(n_[k], n_[k1]))
            rr = rr[[(k, r) in idx or (k1, r) in idx for r in rr]] if len(rr) else rr
            if not len(rr):
                continue
            Xa = at(cols[k], np.array([station0(k, r) for r in rr]))
            Xb = at(cols[k1], np.array([station0(k1, r) for r in rr]))
            gap = 0.5 * (to_path(Xa, cols[k1]['path']) + to_path(Xb, cols[k]['path']))
            for r, g in zip(rr, gap):
                w = hold * min((r - 1.0) / 2.0, 1.0) / max(g, 1.0e-3)
                term([((k, r), w), ((k1, r), -w)], 0.0)
        out = []
        if nu:
            A = coo_matrix((vals, (rows_i, cols_i)), shape=(ne, nu)).tocsr()
            sol = spsolve((A.T @ A).tocsc(), A.T @ np.array(rhs))
        for k in range(K):
            x = np.array([station0(k, r) if (k, r) not in idx else sol[idx[(k, r)]] for r in range(1, f_[k])])
            if len(x):
                # no step under a quarter of its column's even one: where the hold asks more, the column eases back
                steps = np.diff(np.concatenate([[0.0], x, [Sf[k]]]))
                t_back = min(1.0, float(np.where(steps < 0.25 * h[k], 0.75 * h[k] / np.maximum(h[k] - steps, 1e-12),
                                                 1.0).min()))
                x = even[k] + t_back * (x - even[k])
            out.append(full(k, x))
        return out

    def row_plan(extra=SUP):
        """per layer and column (n, f, fixed stations): the rows where each web's columns meet its margin, chosen from
        the paths' lengths so each layer's rows lie level with its arms': per web the side columns' bare run m (the
        rows from the meeting point at the web's reach out to sw) and the walls' run (the rows a wall column climbs the
        margin from the bottom's row to its arm), both the same in the two layers (their vertices are shared); the
        bottom's row then sits run rows under the meeting point (the top layer LEAD rows over the bottom's). extra: of
        the SUP support rows, how many the top layer takes (crown v5d: the runs m and run judged without them, so the
        margin, its rim strip and the bare runs stay as they were; 0: the plan the supports are chosen on). The
        bottom's bot_extra rows (Stage 4) are judged the same way: m and run on R rows, the bottom then taking RB"""
        NR0 = {'top': R + LEAD, 'bot': R}
        NRx = {'top': R + LEAD + extra, 'bot': RB}
        P = {'top': [None] * K, 'bot': [None] * K}
        m_w, run_w = np.zeros(N_ARMS, int), np.zeros(N_ARMS, int)
        for j in range(N_ARMS):
            ka, kb = (SECT // 2 + HALF + SECT * j) % K, (SECT // 2 - HALF + SECT * (j + 1)) % K
            k1, k7 = (ka + 1) % K, (kb - 1) % K
            kmid = [(ka + i) % K for i in range(2, SECT - 2 * HALF - 1)]
            m_nat, run_nat = [], []
            for layer in ('top', 'bot'):
                n = NR0[layer]
                for ks, kw in ((ka, k1), (kb, k7)):
                    cs, cw = cols[layer][ks], cols[layer][kw]
                    e_s = n * cs['L_meet'] / cs['cum'][-1]
                    m_nat.append(n - e_s)
                    step = 0.5 * (cs['L_meet'] + cw['cum'][-1]) / max(e_s, 1.0)
                    L_bot = np.mean([cols[layer][kk]['cum'][-1] for kk in kmid])
                    run_nat.append(cw['Wc'][-1] / step + (cw['L_line'] - L_bot) / step)
            m = int(np.clip(np.round(np.mean(m_nat)), 0, R - 3))
            run = int(np.clip(np.round(np.mean(run_nat)), 0, R - m - 2))
            m_w[j], run_w[j] = m, run
            for layer in ('top', 'bot'):
                n = NRx[layer]
                e_s = n - m
                e_b = e_s - run
                for ks in (ka, kb):
                    c_ = cols[layer][ks]
                    L_arm = c_['cum'][-1]
                    st_ = [c_['L_meet'] + (L_arm - c_['L_meet']) * i / max(m, 1) for i in range(m + 1)] if m else [L_arm]
                    P[layer][ks] = (n, e_s, np.array(st_))
                for kw in (k1, k7):
                    c_ = cols[layer][kw]
                    W = c_['Wc'][-1]
                    P[layer][kw] = (e_s, e_b, c_['L_line'] + W * np.arange(run + 1) / (run + 1))
                for kk in kmid:
                    P[layer][kk] = (e_b, e_b, np.array([cols[layer][kk]['cum'][-1]]))
        for layer in ('top', 'bot'):
            for k in range(K):
                if P[layer][k] is None:              # an arm's interior column: its last row the tube's first ring
                    P[layer][k] = (NRx[layer], NRx[layer], np.array([cols[layer][k]['cum'][-1]]))
        # a concave junction's crease takes the row nearest it (the fold under the mantle: rows by the even spacing
        # alone fell 8.6 and 33 mm along a line whose crease lay 21 mm along, and the quad between them bridged it)
        for k in range(K):
            c_ = cols['top'][k].get('crease')
            if c_ is None:
                continue
            n, f, tail = P['top'][k][:3]
            h_ = tail[0] / f
            r = int(np.clip(round(c_ / h_), 1, f - 1))
            # (not within three quarters of a step of the ring: pinned 7 mm off it on a 13 mm step, row 1 made a
            # sliver whose UVs flipped; that close the first quad's chord over the crease is short anyway)
            if 0.75 * h_ < c_ < tail[0] - 0.3 * h_:
                P['top'][k] = (n, f, tail, {r: c_})
        return P, m_w, run_w

    def support_plan(P1):
        """(crown v5d) the SUPPORT rows. On the back's band (the sectors holding a fold's crease run: the band
        octopus_uv cuts off) each concave junction's rows, from the head ring to the band's edge (its crease, else row
        1) and the next, are checked against the fold's PROFILE (the column's lead: its section on the surface, in its
        plane): the chord standing farthest off the profile, when more than support_gap, takes a row pinned at the
        profile's farthest point from it (never within support_min of a row), and the rows are solved again
        (row_stations), SUP times, so each support is chosen on the rows as the earlier ones left them (chosen at once,
        on the rows without them, the rows after them were pushed down the back face by the solve and the next quad
        chorded the corner). Then each support in turn is taken out and put back where the rows, solved without it,
        leave the farthest chord, the change kept on a column only where its own farthest chord, the rows solved again,
        comes out nearer: the hold keeps a row level with its neighbours' rows of the same index, which a support
        shifts, so a column's free rows move with its neighbours' supports, and kept every time, a support on the arms'
        columns went from the corner to the seat and back, sweep after sweep, and ended off the corner. A column keeps
        its other rows (the SUP rows every column takes go to its supports; one with fewer keeps the rest free).
        Mirrored: chosen on the columns k <= K / 2, the same stations on K - k. Returns the top layer's plan (a band
        column's pins: its crease, if any, its supports and its rows on the back face, below; every other column's: its
        rows as the plan without supports sets them, below), the support rows and the crease rows per column. One row
        on the seat's edge and the crease on the back face's foot left the quad between them
        chording the fold's rounding 3-5 mm under the restored lip (crown v5c, the head gate's misses at x +-11-16
        mm), the crease on the corner and the next row 14 mm down the face chorded the wall under it (the midline pair
        at x +-2.7 mm), and row 1 on the arms' columns, past the corner, chorded it from the ring"""
        P0 = row_plan(0)[0]['top']
        hold = cage['row_hold'][0]
        st0 = row_stations(cols['top'], P0, hold)
        cand = [k for k in band if k <= K // 2 and cols['top'][k].get('fine') is not None]
        gap_min, d_min = cage.get('support_gap', 6.0e-4), cage.get('support_min', 1.5e-3)
        mir = lambda k: (K - k) % K
        both = sorted(set(cand) | {mir(k) for k in cand})
        # every other column keeps its rows as the plan without supports sets them, pinned there, its SUP more rows
        # free, one in each of its first SUP steps from the head ring (one rule round the ring, so a row index means
        # the same row on neighbouring columns: the hold keeps rows of the same index level). Spread over the whole
        # column by the solve, the extra rows moved every row off the band too: at the front midline the junction's
        # last quad came to chord the head's root 2.6 mm deep against 2.0 (73 and 42 texels missed there, 7 before)
        assert all(k in both for k in range(K) if len(P0[k]) > 3), 'a crease off the back band'
        P = [P0[k] if k in both else P0[k][:3] for k in range(K)]
        for k in range(K):
            if k not in both:
                n0, f0, tail = P0[k][:3]
                P[k] = (n0 + SUP, f0 + SUP, tail, {r_ + min(r_, SUP): float(st0[k][r_ - 1]) for r_ in range(1, f0)})
        sup = {k: [] for k in both}
        cr_st = {k: P0[k][3][next(iter(P0[k][3]))] for k in both if len(P0[k]) > 3}
        reach = {k: (next(iter(P0[k][3])) if len(P0[k]) > 3 else 1) + 1 for k in both}   # the band's edge + 1

        def rebuild(k, st):
            """column k's plan with its supports sup[k] (and its crease), its free rows ranked as the solve st left
            them (the free rows' count never changes: each support is one more row)"""
            pins = P[k][3] if len(P[k]) > 3 else {}
            free = [s_ for r_, s_ in enumerate(st[k][:P[k][1] - 1], 1) if r_ not in pins]
            pst = ([cr_st[k]] if k in cr_st else []) + sup[k]
            allr = sorted(free + pst)
            n0, f0, tail = P0[k][:3]
            P[k] = (n0 + len(sup[k]), f0 + len(sup[k]), tail) + (({1 + allr.index(s_): s_ for s_ in pst},) if pst
                                                                  else ())

        def chords(k, st):
            """column k's chords from the ring to the band's edge and the next, as the solve st sets its rows: per
            chord the profile's farthest distance off it, and its farthest point at least support_min from both ends
            (distance, station)"""
            c_ = cols['top'][k]
            path, cum, nl = c_['path'], c_['cum'], c_['nl']
            rows = [0.0] + list(st[k][:P[k][1] - 1])
            ends = [s_ for s_ in rows[:reach[k] + len(sup[k]) + 1] if s_ <= cum[nl] + 1.0e-12]
            at = lambda s_: np.array([np.interp(s_, cum, path[:, d_]) for d_ in range(3)])
            out = []
            for a, b in zip(ends[:-1], ends[1:]):
                sel = (cum > a) & (cum < b) & (np.arange(len(cum)) <= nl)
                if not sel.any():
                    continue
                A0, AB = at(a), at(b) - at(a)
                t_ = np.clip(((path[sel] - A0) @ AB) / max(float(AB @ AB), 1.0e-18), 0.0, 1.0)
                d = np.linalg.norm(path[sel] - (A0 + t_[:, None] * AB), axis=1)
                w = (cum[sel] > a + d_min) & (cum[sel] < b - d_min)
                i_ = int(np.argmax(np.where(w, d, -1.0)))
                out.append((float(d.max()), float(d[i_]) if w.any() else 0.0, float(cum[sel][i_])))
            return out

        def pick(k, st):
            """the station of the profile's point farthest off column k's chords (at least support_min from the
            chord's ends), when more than support_gap"""
            got = max(((g_w, s_) for _, g_w, s_ in chords(k, st)), default=(0.0, None))
            return got[1] if got[0] > gap_min else None
        worst = lambda k, st: max((g for g, _, _ in chords(k, st)), default=0.0)
        for _ in range(SUP):
            st = row_stations(cols['top'], P, hold)
            for k in cand:
                s_ = pick(k, st)
                if s_ is not None:
                    for kk in {k, mir(k)}:
                        sup[kk].append(s_)
                        rebuild(kk, st)
        st = row_stations(cols['top'], P, hold)
        cur = {k: worst(k, st) for k in cand}
        for _ in range(cage.get('support_sweeps', 2)):
            for j in range(SUP):
                keep = (list(P), {k: list(v) for k, v in sup.items()})
                out_ = {}
                for k in cand:
                    if len(sup[k]) > j:
                        out_[k] = sorted(sup[k])[j]
                        for kk in {k, mir(k)}:
                            sup[kk] = [s_ for s_ in sup[kk] if s_ != out_[k]]
                            rebuild(kk, st)
                st_ = row_stations(cols['top'], P, hold)
                for k in out_:
                    s_ = pick(k, st_)
                    if s_ is not None:
                        for kk in {k, mir(k)}:
                            sup[kk].append(s_)
                            rebuild(kk, st_)
                st_ = row_stations(cols['top'], P, hold)
                for k in out_:
                    if worst(k, st_) >= cur[k] - 1.0e-5:          # (not nearer: back as it was)
                        for kk in {k, mir(k)}:
                            P[kk], sup[kk] = keep[0][kk], list(keep[1][kk])
                st = row_stations(cols['top'], P, hold)
                cur = {k: worst(k, st) for k in cand}
        # then the free rows on the lead past the last pin (the back face under the fold) are set where the profile
        # needs them, and pinned there: each in turn (twice over) goes to the profile's point between its neighbours
        # that brings the farther of its two chords nearest, when 0.05 mm nearer (the neighbours on the lead).
        # Evenly spaced they chorded the E web's back face at the midline, its bulge 15-28 mm under the corner, 2.5 mm
        # deep (the head gate's one failing cluster, 21 texels; crown v5c's 11 + 13 there)
        st = row_stations(cols['top'], P, hold)
        for k in cand:
            if len(P[k]) < 4:
                continue
            c_ = cols['top'][k]
            path, cum, nl = c_['path'], c_['cum'], c_['nl']
            at = lambda s_: np.array([np.interp(s_, cum, path[:, d_]) for d_ in range(3)])
            on = np.arange(len(cum)) <= nl

            def gap(a, b):
                sel = (cum > a) & (cum < b) & on
                if not sel.any():
                    return 0.0
                A0, AB = at(a), at(b) - at(a)
                t_ = np.clip(((path[sel] - A0) @ AB) / max(float(AB @ AB), 1.0e-18), 0.0, 1.0)
                return float(np.linalg.norm(path[sel] - (A0 + t_[:, None] * AB), axis=1).max())
            pins, f_k = P[k][3], P[k][1]
            rows = [0.0] + [float(s_) for s_ in st[k][:f_k - 1]] + [float(P[k][2][0])]
            last = max(pins.values())
            mv = [r_ for r_ in range(1, f_k) if r_ not in pins and last < rows[r_] and rows[r_ + 1] <= cum[nl]]
            for _ in range(2):
                for r_ in mv:
                    a, b = rows[r_ - 1], rows[r_ + 1]
                    now = max(gap(a, rows[r_]), gap(rows[r_], b))
                    ss_ = cum[(cum > a + d_min) & (cum < b - d_min) & on]
                    if len(ss_):
                        g_ = [max(gap(a, s_), gap(s_, b)) for s_ in ss_]
                        if min(g_) < now - 5.0e-5:
                            rows[r_] = float(ss_[int(np.argmin(g_))])
            for kk in {k, mir(k)}:
                P[kk] = P[kk][:3] + ({**P[kk][3], **{r_: rows[r_] for r_ in mv}},)
        sup_rows, cr_rows = {}, {}
        for k in range(K):
            if k in both:
                n0, f0, tail = P0[k][:3]
                pins = P[k][3] if len(P[k]) > 3 else {}
                P[k] = (n0 + SUP, f0 + SUP, tail) + ((pins,) if pins else ())
                at_ = {s_: r_ for r_, s_ in pins.items()}
                if k in cr_st:
                    cr_rows[k] = at_[cr_st[k]]
                if sup[k]:
                    sup_rows[k] = sorted(at_[s_] for s_ in sup[k])
        return P, sup_rows, cr_rows

    def relead(c_):
        """(crown v5d) a top column's path with the fold's profile (column_path's 'fine': its points between the head
        ring and the layout's start) for its lead in place of the coarse junction line: the stations past the lead
        shift by its change of length; the crease takes the profile's point nearest the coarse line's"""
        nl, Jf = c_['nl'], c_['fine']
        path = np.vstack([c_['path'][:1], Jf, c_['path'][nl:]])
        d_n = len(Jf) + 1 - nl
        cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        d_l = float(cum[nl + d_n] - c_['cum'][nl])
        out = dict(c_, path=path, cum=cum, nl=nl + d_n, nlay=c_['nlay'] + d_n, L_line=c_['L_line'] + d_l)
        if 'L_meet' in c_:
            out['L_meet'] = c_['L_meet'] + d_l
        if c_.get('crease_pt') is not None:
            out['crease'] = float(cum[int(np.argmin(np.linalg.norm(path[:nl + d_n + 1] - c_['crease_pt'], axis=1)))])
        return out
    paths_ = batched([column_path(layer, k) for layer in ('top', 'bot') for k in range(K)])
    cols = {'top': paths_[:K], 'bot': paths_[K:]}
    # (crown v5d) the back's BAND: the sectors holding a fold's crease run (the band octopus_uv cuts off) and the seam
    # column closing the last; its concave junctions take the fold's profile for their lead, the support rows go there
    secs = {k // SECT for k in range(K) if 'crease' in cols['top'][k]}
    band = [k for k in range(K) if k // SECT in secs or (k % SECT == 0 and (k // SECT - 1) % N_ARMS in secs)]
    for k in band:
        if cols['top'][k].get('fine') is not None:
            cols['top'][k] = relead(cols['top'][k])
    plan_rows, web_m, web_run = row_plan()
    crease_of = {'top': {k: next(iter(plan_rows['top'][k][3])) for k in range(K) if len(plan_rows['top'][k]) > 3},
                 'bot': {}}                  # the creases' rows per column (the pins also hold the supports, crown v5d)
    sup_of = {}                              # column -> its support rows (crown v5d)
    if SUP:
        plan_rows['top'], sup_of, crease_of['top'] = support_plan(plan_rows['top'])
    stations = {'top': row_stations(cols['top'], plan_rows['top'], cage['row_hold'][0]),
                'bot': row_stations(cols['bot'], plan_rows['bot'], cage['row_hold'][1])}
    lead_n = {'top': np.zeros(K, np.int64), 'bot': np.zeros(K, np.int64)}    # each column's rows over its junction
    first_shared = {'top': np.zeros(K, np.int64), 'bot': np.zeros(K, np.int64)}
    shared = {}                              # (column, i): the i-th vertex of the column's run shared by both layers
    rim3 = {}                                # (column, i): a rim point's strip vertices (T, S, B): rim_triple

    def rim_lam(k, i, n_k, f_k):
        """the lam of a web column's rim point, or of a wall column's i-th point up the margin's wall"""
        if col_role(k)[0] == 'wall':
            c_ = cols['top'][k]
            return float(np.interp(c_['Wc'][-1] * i / (n_k - f_k + 1), c_['Wc'], c_['Wl']))
        return col_info(k)[2]
    rim_end = lambda k, i: col_role(k)[0] == 'wall' and i == plan_rows['top'][k][0] - plan_rows['top'][k][1]
    # every rim point's frame first, and their projections in ONE launch (crown v5c; rim_triple projected each alone:
    # 140 launches of two points)
    rim_pre = {(k, i): (rim_lam(k, i, *plan_rows['top'][k][:2]),) for k in range(K) if col_role(k)[0] in ('wall', 'web')
               for i in range(plan_rows['top'][k][0] - plan_rows['top'][k][1] + 1)}
    rim_pre = {key: v + (rim_frame(col_role(key[0])[1], v[0], rim_end(*key)),) for key, v in rim_pre.items()}
    if rim_pre:
        q_, s_ = prog.project(np.concatenate([np.tile(v[1][2], (2, 1)) for v in rim_pre.values()]),
                              np.concatenate([v[1][4] for v in rim_pre.values()]), maxd=0.01)
        rim_pre = {key: v + ((q_[2 * n_:2 * n_ + 2], s_[2 * n_:2 * n_ + 2]),)
                   for n_, (key, v) in enumerate(rim_pre.items())}
    for k in range(K):
        j, kind, val = col_info(k)
        role, jr, sd = col_role(k)
        for layer, G, reg in (('top', top, 1), ('bot', bot, 2)):
            n_k, f_k, fixed_st = plan_rows[layer][k][:3]
            first_shared[layer][k] = f_k
            rows_ = column_rows(layer, k, cols[layer][k], stations[layer][k][:f_k - 1])
            for r_, (p_, (s_, al), on_layout) in enumerate(rows_, start=1):
                lead_n[layer][k] += not on_layout
                G[r_, k] = add(p_, reg, s_, al)
                if on_layout and kind == 'web':
                    # the web's own faces: ray along the web's normal (up for the top layer, down for the bottom)
                    first_dirs[G[r_, k]] = up if layer == 'top' else -up
                if not cage.get('relax_crown', True):
                    pinned.append(G[r_, k])
            if role == 'arm':                # the arm tube's first ring: per layer inside the side lines
                p_, (jj, s_, al), _ = layout(layer, k, 0.0, 1.0)
                G[n_k, k] = add(p_, reg, s_, al)
                continue
            for i in range(n_k - f_k + 1):   # the run shared by both layers
                if role == 'side':
                    # the meeting point (the web's margin on the arm's side line at its reach), then the arm's bare
                    # flank out to sw, its last vertex the tube's first ring's side vertex (pinned, as v4's). Where a
                    # bare run follows it (crown v5c) each layer's grid takes its own vertex there instead, a quarter
                    # of the run's first step on and over (top) or under (bottom) the side line by the margin's
                    # half-thickness: the strip's apex runs on into the meeting point, which closes it with two quads
                    # (M_top T S M, M S B M_bottom) and one more on the arm's flank (M_top M M_bottom and the run's
                    # first vertex). One quad M T S B closing the strip, split along T-B as t10 splits it, left a
                    # cross-section triangle T S B facing along the margin (inside out, 1.0-1.1 mm2 at the A and E webs)
                    m_ = n_k - f_k
                    key_ = (k, i, layer) if i == 0 and m_ > 0 else (k, i)
                    for key_ in ([(k, i), key_] if len(key_) == 3 else [key_]):
                        if key_ in shared:
                            continue
                        s_ = sw[order[j]] if m_ == 0 else \
                            plan['s_reach'][jr] + (sw[order[j]] - plan['s_reach'][jr]) * i / m_
                        al = np.pi / 2 * (1 if val > 0 else -1)
                        if len(key_) == 3:
                            s_ += 0.25 * (sw[order[j]] - plan['s_reach'][jr]) / m_
                            c_, na_, ba_, ta_, ra_ = arm_frame(order[j], s_)
                            u_ = np.linalg.norm(c_ + ba_ * ra_ * np.sign(val) - mouth_p) / depth_web[jr]
                            d_ = float(np.arcsin(min(float(web_fold_half(spec, u_, 1.0)) / (1.05 * ra_), 1.0)))
                            al = al - np.sign(al) * d_ if layer == 'top' else al + np.sign(al) * d_
                        shared[key_] = add(arm_point(order[j], s_, al), 2 if len(key_) == 3 and layer == 'bot' else 1,
                                           s_, al, 0.5)
                        if i == 0 or i == m_:
                            pinned.append(shared[key_])
                    G[f_k + i, k] = shared[key_]
                    continue
                # a web column's rim point, or a wall column's run up the margin: the membrane's edge on the web
                # patch's own boundary (its mid-surface), and there the RIM STRIP's three vertices (rim_triple): this
                # layer's own edge vertex (T on top, B below) in its grid, the apex S between them shared (the strip's
                # quads after the grids). On the mid-surface, as crown v5 kept its one shared rim row, the chords of the
                # U stay inside the membrane (bake_misses: on the apex they ran 0.2-0.9 mm outside it)
                if (k, i) not in rim3:
                    lam_ = rim_lam(k, i, n_k, f_k)
                    pre = rim_pre.get((k, i))
                    rim3[(k, i)] = rim_triple(jr, lam_, pre[1:] if pre is not None and pre[0] == lam_ else None,
                                              end=rim_end(k, i))
                G[f_k + i, k] = rim3[(k, i)][0 if layer == 'top' else 2]
    # the junction rows RELAXED on the shape (umbrella moves in the tangent plane, re-projected; the fit's safeguards):
    # each column's line over the junction is cast on its own, and they crossed where an arm's side column starts up
    # its flank and the web column beside it on the web (t04 v4: 12 folds in the designed top layer, 2 in the bottom,
    # which the preserving fit keeps). With them the first layout row past each junction (junction_into): a column
    # that leaves its junction a row before its neighbour put its layout row beside the neighbour's junction row, a
    # dart that folded at the D web's root (t04 v4 check). The layout beyond stays as designed. Each round ends
    # MIRRORED (column k against K - k, x against -x): a move accepted on one side and refused on the other, float noise
    # apart, grew over the rounds into the crown's only asymmetry, 4.7 mm in the top layer and 5.5 in the bottom (t04 v4
    # check)
    mk = (K - np.arange(K)) % K
    flip = np.array([-1.0, 1.0, 1.0])
    for layer, G in (('top', top), ('bot', bot)):
        free = np.zeros(G.shape, bool)
        for k in range(K):
            # (never a shared row: a rim, a wall's run, a side column's meeting point and bare run, a tube's first ring;
            # every free row's four neighbours exist, the margin crossing rows only past them)
            free[1:min(1 + lead_n[layer][k] + cage['junction_into'], first_shared[layer][k]), k] = True
            if layer == 'top':
                free[sup_of.get(k, []), k] = False       # (the supports stay on the fold's profile: crown v5d)
        ids = G[free]
        # a fold's crease rows stay ON THE CREASE: relaxed with the rest, then snapped back onto the crease line (the
        # polyline through its group's crease points, in column order), so they may slide along it. Smoothed freely
        # they slid down the back face beside the midline and the quads above bridged the fold again; held fixed, the
        # rows round them stayed uneven and the top island's inner edge curled over itself in UV (3 texels). One line
        # per run of neighbouring crease columns (crown v5b: the bottom's groove runs round the crown, closed when
        # whole; one line through every crease column would chord across the crown between two runs)
        runs = []
        for k in range(K):
            if k in crease_of[layer]:
                if runs and runs[-1][-1] == k - 1:
                    runs[-1].append(k)
                else:
                    runs.append([k])
        if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == K - 1:
            runs[0] = runs.pop() + runs[0]
        cr_lines, grp = [], {}
        for run in runs:
            if len(run) > 1:
                vs_ = [int(G[crease_of[layer][k], k]) for k in run]
                grp.update({v: len(cr_lines) for v in vs_})
                cr_lines.append(np.array([V[v] for v in vs_ + vs_[:1] * (len(run) == K)]))
        cr_of = np.array([grp.get(int(v), -1) for v in ids])
        loc = {int(v): i for i, v in enumerate(ids)}
        mirror_of = np.array([loc.get(int(v), -1) for v in G[:, mk][free]])      # each free vertex's mirror among them
        pair = mirror_of >= 0
        for _ in range(cage['junction_relax']):
            Pg = np.array([V[i] for i in G.ravel()]).reshape(G.shape + (3,))
            nb = np.stack([np.roll(Pg, 1, axis=1), np.roll(Pg, -1, axis=1),
                           np.vstack([Pg[1:], Pg[-1:]]), np.vstack([Pg[:1], Pg[:-1]])])
            P0 = Pg[free]
            h = np.linalg.norm(nb[:, free] - P0[None], axis=2).mean(0)
            Nn = prog.normals(P0)
            step = 0.5 * (nb[:, free].mean(0) - P0)
            step -= (step * Nn).sum(1, keepdims=True) * Nn
            step *= np.minimum(1.0, 0.25 * h / np.maximum(np.linalg.norm(step, axis=1), 1e-12))[:, None]
            q_, s_ = prog.project(P0 + step, prog.normals(P0 + step), maxd=0.06)
            ok = (s_ == 0) & (np.linalg.norm(q_ - (P0 + step), axis=1) < 0.3 * h) & \
                 ((prog.normals(q_) * Nn).sum(1) > 0.8)
            q_ = np.where(ok[:, None], settle(q_), P0)
            q_[pair] = 0.5 * (q_[pair] + q_[mirror_of[pair]] * flip)
            for g_, cr_line in enumerate(cr_lines):
                is_cr = cr_of == g_
                if not is_cr.any():
                    continue
                X_ = q_[is_cr]
                A0, AB = cr_line[:-1], cr_line[1:] - cr_line[:-1]
                t_ = np.clip(((X_[:, None] - A0[None]) * AB[None]).sum(2) / np.maximum((AB * AB).sum(1), 1e-18)[None],
                             0.0, 1.0)
                C_ = A0[None] + t_[..., None] * AB[None]
                q_[is_cr] = C_[np.arange(len(X_)), np.linalg.norm(X_[:, None] - C_, axis=2).argmin(1)]
            for i, p_ in zip(ids, q_):
                V[i] = p_

    # (rest-pose round) the ROWS SLID OFF THE CHORDS. A column's rows lie even along its path (the top's held level
    # with their neighbours'), whatever the surface does between them, and a quad chords every turn it straddles: on
    # the oral side the rows, 15-34 mm apart round the oral disc's edge, bridge the groove where the webs' undersides
    # meet it (the crown bottom's 86 triangles more than 2 mm off the low program, 3.2 mm at the A and E roots, crown
    # v5d), and on top two rows straddle the head mass's bulge over the B webs' roots, the quad between them cutting
    # 3.9 mm into it (the B notch, 12 + 12 triangles). So a picked column's rows, cast as the fit's first pass casts
    # them, are judged by their CHORDS: the most |f| of the program along the straight line between two neighbouring
    # rows (what a quad between them stands off the shape). Row by row (the odd rows, then the even, so a row's two
    # neighbours stay put while it moves) each slides to the place between its neighbours where its two chords stand
    # least past slide_tau off the shape (their excesses summed, the farther chord a tie-break: excess() below; the
    # farther chord alone traded one bridge for another by the mouth): candidates a share t of the way toward the next
    # row (t > 0) or the previous, |t| <= slide_t, each cast along the row's own normal at most slide_reach and taken
    # only where it lands on a face turned as the row's (never through a web to its far face) and leaves no step under
    # slide_seg of the row's step before; a move kept when the excess falls by slide_gain; slide_sweeps rounds; the
    # moved rows then mirrored (column k against K - k). The bottom's rows (past slide_rho0 of the axis) slide on
    # every column between the mouth ring and the first shared row; the top's only on columns off the back's band and
    # outside the sectors slide_top_skip names (the A web's) where a chord stands more than slide_top_cut off the
    # shape, and their two neighbours a side. The moved rows lie on the shape, and the fit keeps them (it relaxes
    # toward the design)
    W8 = (np.arange(1, 9) / 9.0)[:, None, None]

    def chord_f(A, B):
        """per pair of points (A[i], B[i]): the program's |f| at its most along the chord between them, signed"""
        X_ = (1.0 - W8) * A[None] + W8 * B[None]
        f_ = prog.eval(X_.reshape(-1, 3)).reshape(8, len(A)).astype(np.float64)
        i_ = np.abs(f_).argmax(0)
        return f_[i_, np.arange(len(A))]

    def chord_slide(layer, G, picks):
        """picks: {k: (r_lo, r_hi)}: rows r_lo + 1 .. r_hi - 1 of column k slide between rows r_lo and r_hi (kept).
        Returns {k: (the most |f| over its chords before, after (mm), the chord's first row before)}"""
        ks = sorted(picks)
        ids_of = {k: [int(G[r, k]) for r in range(picks[k][0], picks[k][1] + 1)] for k in ks}
        P = {k: np.array([V[i] for i in ids_of[k]]) for k in ks}
        inner = [(k, m_) for k in ks for m_ in range(1, len(ids_of[k]) - 1)]
        if not inner:
            return {}
        X_ = np.array([P[k][m_] for k, m_ in inner])
        D_ = np.array([first_dirs.get(ids_of[k][m_], np.full(3, np.nan)) for k, m_ in inner])
        for (k, m_), p_ in zip(inner, cast(X_, D_)):          # (as the fit's first pass casts them)
            P[k][m_] = p_
        P0_ = {k: P[k].copy() for k in ks}

        def worst(Pd):
            out_ = {}
            A_ = np.concatenate([Pd[k][:-1] for k in ks])
            B_ = np.concatenate([Pd[k][1:] for k in ks])
            f_ = np.abs(chord_f(A_, B_))
            c_ = 0
            for k in ks:
                n_ = len(Pd[k]) - 1
                i_ = int(np.argmax(f_[c_:c_ + n_]))
                out_[k] = (float(f_[c_ + i_]) * 1e3, picks[k][0] + i_)
                c_ += n_
            return out_
        before = worst(P)
        tmax = float(cage.get('slide_t', 0.4))
        T_ = np.array([t_ for t_ in np.linspace(-tmax, tmax, 9) if abs(t_) > 1e-9])
        reach, gain = float(cage.get('slide_reach', 0.008)), float(cage.get('slide_gain', 5.0e-5))
        tau, seg_min = float(cage.get('slide_tau', 0.0015)), float(cage.get('slide_seg', 0.5))
        rho0 = float(cage.get('slide_rho0', 0.0)) if layer == 'bot' else 0.0
        # (not the rows round the mouth: the polar rows' spacing is the UVs', polar_w)
        inner = [(k, m_) for k, m_ in inner if np.linalg.norm(P[k][m_][[0, 2]]) >= rho0]

        def excess(fa, fb):
            """a row's two chords: their |f| past tau summed (so both are brought under it), the farther one a tie-break"""
            fa, fb = np.abs(fa), np.abs(fb)
            return np.maximum(fa - tau, 0.0) + np.maximum(fb - tau, 0.0) + 0.05 * np.maximum(fa, fb)
        moved = set()
        for _ in range(int(cage.get('slide_sweeps', 3))):
            for par in (1, 0):
                rows_ = [(k, m_) for k, m_ in inner if m_ % 2 == par]
                if not rows_:
                    continue
                A_ = np.array([P[k][m_ - 1] for k, m_ in rows_])
                C_ = np.array([P[k][m_] for k, m_ in rows_])
                B_ = np.array([P[k][m_ + 1] for k, m_ in rows_])
                la = np.array([np.linalg.norm(P0_[k][m_] - P0_[k][m_ - 1]) for k, m_ in rows_])
                lb = np.array([np.linalg.norm(P0_[k][m_ + 1] - P0_[k][m_]) for k, m_ in rows_])
                now = excess(chord_f(A_, C_), chord_f(C_, B_))
                Nc = prog.normals(C_)
                Nc /= np.maximum(np.linalg.norm(Nc, axis=1, keepdims=True), 1e-12)
                tt = T_[None, :, None]
                X_ = np.where(tt > 0, C_[:, None] + tt * (B_ - C_)[:, None], C_[:, None] - tt * (A_ - C_)[:, None])
                n_c = len(T_)
                Xf = X_.reshape(-1, 3)
                Nf = np.repeat(Nc, n_c, axis=0)
                q_, s_ = prog.project(Xf, Nf, maxd=reach)
                Nq = prog.normals(q_)
                ok_ = (s_ == 0) & ((Nq * Nf).sum(1) > 0.5 * np.linalg.norm(Nq, axis=1))
                Af, Bf = np.repeat(A_, n_c, axis=0), np.repeat(B_, n_c, axis=0)
                # no step under seg_min of the row's own step there before the slide
                ok_ &= (np.linalg.norm(q_ - Af, axis=1) >= seg_min * np.repeat(la, n_c)) & \
                       (np.linalg.norm(Bf - q_, axis=1) >= seg_min * np.repeat(lb, n_c))
                cost = excess(chord_f(Af, q_), chord_f(q_, Bf))
                cost = np.where(ok_, cost, np.inf).reshape(len(rows_), n_c)
                best = cost.argmin(1)
                q_ = q_.reshape(len(rows_), n_c, 3)
                for i_, (k, m_) in enumerate(rows_):
                    if cost[i_, best[i_]] < now[i_] - gain:
                        P[k][m_] = settle(q_[i_, best[i_]])[0]
                        moved.add((k, m_))
        # mirrored (column k against K - k, x against -x), the moved rows on both sides
        flip_ = np.array([-1.0, 1.0, 1.0])
        sym = {(k, m_) for k, m_ in moved} | {((K - k) % K, m_) for k, m_ in moved if (K - k) % K in P}
        for k, m_ in sym:
            km = (K - k) % K
            if km in P and len(P[km]) == len(P[k]):
                p_ = 0.5 * (P[k][m_] + P[km][m_] * flip_)
                V[ids_of[k][m_]] = cast(p_[None], np.full((1, 3), np.nan))[0]
            elif (k, m_) in moved:
                V[ids_of[k][m_]] = P[k][m_]
        Pn = {k: np.array([V[i] if (k, m_) in sym else P0_[k][m_] for m_, i in enumerate(ids_of[k])]) for k in ks}
        after = worst(Pn)
        return {k: (before[k][0], after[k][0], before[k][1]) for k in ks}

    slide_log = {}
    if cage.get('slide_bot'):
        slide_log['bot'] = chord_slide('bot', bot, {k: (0, int(first_shared['bot'][k])) for k in range(K)
                                                    if first_shared['bot'][k] >= 2})
    if cage.get('slide_top'):
        # the top: the columns off the band whose chords (the ring to the first shared row, as the fit casts them)
        # stand more than slide_top_cut off the shape, and two neighbours a side
        # (and off the sectors slide_top_skip names: the A web's, the front midline, where the junction's last quads
        # decide the head gate: slid there, a 22-texel cluster failed it at (-0.5, 65, 86) mm, as crown v5d's d7 failed
        # it when its rows moved there)
        def sector_of(k):
            j, kind, val = col_info(k)
            return int(plan['sector'][j]) if kind == 'web' else -1
        skip = set(cage.get('slide_top_skip', ()))
        off_band = [k for k in range(K) if k not in band and first_shared['top'][k] >= 2 and
                    sector_of(k) not in skip and sector_of((k - 1) % K) not in skip and
                    sector_of((k + 1) % K) not in skip]
        ids_t = {k: [int(top[r, k]) for r in range(int(first_shared['top'][k]) + 1)] for k in off_band}
        A_, B_, own = [], [], []
        for k in off_band:
            Pk = np.array([V[i] for i in ids_t[k]])
            D_ = np.array([first_dirs.get(i, np.full(3, np.nan)) for i in ids_t[k][1:-1]])
            Pk[1:-1] = cast(Pk[1:-1], D_)
            A_.append(Pk[:-1])
            B_.append(Pk[1:])
            own += [k] * (len(Pk) - 1)
        fa_ = np.abs(chord_f(np.concatenate(A_), np.concatenate(B_)))
        own = np.array(own)
        hot = sorted({int(k) for k in own[fa_ > float(cage['slide_top_cut'])]})
        picks_ = {}
        for k in hot:
            for dk in (-2, -1, 0, 1, 2):
                kk = (k + dk) % K
                if kk in ids_t:
                    picks_[kk] = (0, int(first_shared['top'][kk]))
        if picks_:
            slide_log['top'] = chord_slide('top', top, picks_)
    for lay, v in slide_log.items():
        if v:
            log(f'[cage] rows slid ({lay}): {len(v)} columns; the most |f| over a column\'s chords, the worst column '
                f'{max(x[0] for x in v.values()):.2f} -> {max(x[1] for x in v.values()):.2f} mm, over 2 mm on '
                f'{sum(x[0] > 2.0 for x in v.values())} -> {sum(x[1] > 2.0 for x in v.values())} columns')
    # the web margins: per web the rim points in order from the meeting point on arm order[j] down its wall column's
    # run, along the middle columns, up the other wall to the other meeting point. Between consecutive rim points the
    # RIM STRIP's quads (crown v5b): T T' S' S on top, B S S' B' below (each layer's winding), and at each meeting point
    # the quads closing the strip onto it: where its layers have their own vertices there (crown v5c) M_top T S M and M
    # S B M_bottom (the apex runs on into the meeting point M) and M_top M M_bottom X on the arm's flank (X the bare
    # run's first vertex; the bottom island's), else one, M T S B (the bottom island's). The SEAMS between the layers'
    # islands run along the apex S (the creases) on into M and round the flank quad to X (one quad: round it to its
    # meeting point; one more edge across the strip at each web's middle column, where the top layer's islands part),
    # and the arms' bare runs out to sw are the layers' own seams too (side_seams: the top and bottom layers meet along
    # them, one island each side)
    creases, side_seams, strip = [], [], []
    for j in range(N_ARMS):
        ka, kb = (SECT // 2 + HALF + SECT * j) % K, (SECT // 2 - HALF + SECT * (j + 1)) % K
        k1, k7 = (ka + 1) % K, (kb - 1) % K
        keys = [(k1, i) for i in range(plan_rows['top'][k1][0] - first_shared['top'][k1], -1, -1)]
        keys += [((ka + i) % K, 0) for i in range(2, SECT - 2 * HALF - 1)]
        keys += [(k7, i) for i in range(plan_rows['top'][k7][0] - first_shared['top'][k7] + 1)]
        T_, S_, B_ = ([rim3[q_][c_] for q_ in keys] for c_ in range(3))
        for a_ in range(len(keys) - 1):
            strip.append([T_[a_], T_[a_ + 1], S_[a_ + 1], S_[a_]])
            strip.append([B_[a_], S_[a_], S_[a_ + 1], B_[a_ + 1]])
        creases += list(zip(S_[:-1], S_[1:]))
        for ks, (Tq, Sq, Bq), sgn in ((ka, (T_[0], S_[0], B_[0]), 1), (kb, (T_[-1], S_[-1], B_[-1]), -1)):
            Mt, Mb_ = top[first_shared['top'][ks], ks], bot[first_shared['bot'][ks], ks]
            if Mt == Mb_:
                q4 = [Mt, Tq, Sq, Bq]
                strip.append(q4 if sgn > 0 else [Mt, Bq, Sq, Tq])
                creases += [(Mt, Tq), (Tq, Sq)]
            else:
                M_, X_ = shared[(ks, 0)], top[first_shared['top'][ks] + 1, ks]
                strip += [[Mt, Tq, Sq, M_], [M_, Sq, Bq, Mb_], [Mt, M_, Mb_, X_]] if sgn > 0 else \
                    [[Mb_, Bq, Sq, M_], [M_, Sq, Tq, Mt], [M_, Mt, X_, Mb_]]
                creases += [(Sq, M_), (M_, Mt), (Mt, X_)]
            side_seams += [(top[r, ks], top[r + 1, ks]) for r in range(first_shared['top'][ks] + (Mt != Mb_), RT)]
        kw = (SECT * (j + 1)) % K
        creases.append(tuple(rim3[(kw, 0)][:2]))
    for r in range(RT):
        for k in range(K):
            k1 = (k + 1) % K
            if top[r + 1, k] >= 0 and top[r + 1, k1] >= 0:
                Q.append([top[r, k], top[r, k1], top[r + 1, k1], top[r + 1, k]])
    for r in range(RB):
        for k in range(K):
            k1 = (k + 1) % K
            if bot[r + 1, k] >= 0 and bot[r + 1, k1] >= 0:
                Q.append([bot[r, k], bot[r + 1, k], bot[r + 1, k1], bot[r, k1]])
    Q += strip
    # ---------------------------------------------------------------- ARMS
    arm_rings = []
    for j in range(N_ARMS):
        a = order[j]
        c = SECT // 2 + SECT * j
        cols = [(c + o) % K for o in range(-HALF, HALF + 1)]
        ring0 = [top[RT, kk] for kk in cols] + [bot[RB, (c + o) % K] for o in range(HALF - 1, -HALF, -1)]
        nk = len(ring0)
        alphas = np.radians(-90.0 + np.arange(nk) * (360.0 / nk))
        Larm = arm_length(spec, azs[a]) * (1.0 - sw[a])
        M = int(round(Larm / cage['arm_step']))
        s_arm = sw[a] + (1.0 - sw[a]) * (np.arange(1, M + 1) / M) ** 1.0 * 0.996
        rings = [np.array(ring0)]
        for s in s_arm:
            cc, na, ba, ta, ra = arm_frame(a, s)
            rings.append(np.array([add(cc + 1.05 * ra * (np.cos(al) * na + np.sin(al) * ba), 3 + j, s, al)
                                   for al in alphas]))
        for i in range(len(rings) - 1):
            for m in range(nk):
                m1 = (m + 1) % nk
                Q.append([rings[i][m], rings[i][m1], rings[i + 1][m1], rings[i + 1][m]])
        arm_rings.append(rings)
    n_regions = 3 + N_ARMS
    onehot = np.zeros((len(V), n_regions))
    onehot[np.arange(len(V)), part] = 1.0
    mesh = QuadMesh(np.array(V), np.array(Q), {'part': onehot, 'st': np.array(st)})
    # ---------------------------------------------------------------- APEX AND MOUTH: reduction strips, then caps
    from .. import loft as _loft
    # the apex: the body's first ring is its tube's NEAR ring, reversed it is a far ring for the strips
    ring = body[0][::-1]
    th_ring = th[::-1]
    for s_red in cage['apex_s']:
        th_ring = th_ring[::2]
        mesh, ring = _loft.reduce_ring(mesh, ring, body_ring(s_red, th_ring))
    mesh, _ = _loft.cap(mesh, ring, -t[0], dome=0.002)
    # the mouth: bottom row 0 is already used backward by its layer (a far ring)
    ring = bot[0]
    th_ring = th.copy()
    mouth_red = []                           # the reduction rings (vertex i at row 0's vertex 2i, 4i: the UVs' cuts)
    for rad in cage['mouth_r'][1:]:
        th_ring = th_ring[::2]
        mesh, ring = _loft.reduce_ring(mesh, ring, mouth_ring(rad, th_ring))
        mouth_red.append(ring)
    # then the LIP and the opening (prog.mouth; the block-out carries both, so the fit settles these rings onto them):
    # the lip's foot, outer flank, crest, inner flank, the rim rolling in, three rings down the opening's wall, and a
    # cap at its end behind the beak (t10: the oral pole was a grid cap, no mouth)
    from .. import ports
    M_ = prog.mouth
    R_, r_, ro, dep, lift = M_['R'], M_['r'], M_['r_open'], M_['depth'], M_['lift']
    prof = [(1.30 * R_, -0.125 * r_), (1.175 * R_, -0.5 * r_), (R_, lift - r_), (0.80 * R_, -0.56 * r_),
            (1.04 * ro, -0.19 * r_), (0.96 * ro, 0.25 * dep), (0.90 * ro, 0.60 * dep), (0.85 * ro, 1.0 * dep)]
    az_m = -th_ring
    unit = np.column_stack([np.sin(az_m), np.zeros_like(az_m), np.cos(az_m)])
    lip_rings = [M_['c'] + up * dy + unit * rho for rho, dy in prof]
    if spec.get('mouth_open'):
        # the rim and the cavity's rings follow the elliptical opening (semi-axes ax lateral, az fore and aft), the
        # wall rings widening inside as the cavity does
        ell = np.column_stack([np.sin(az_m) * M_['ax'], np.zeros_like(az_m), np.cos(az_m) * M_['az']])
        for k_, (sc, dy) in zip(range(4, 8), ((1.04, -0.19 * r_), (1.10, 0.25 * dep), (1.16, 0.60 * dep),
                                              (1.0, 1.0 * dep))):
            lip_rings[k_] = M_['c'] + up * dy + ell * sc
    m_try, mouth_rings = ports.extend(mesh, ring, lip_rings)
    # the winding: the foot band faces down, out of the oral surface (mesh.face_normals' diagonal cross)
    qf = m_try.Q[len(mesh.Q)]
    if np.dot(np.cross(m_try.V[qf[2]] - m_try.V[qf[0]], m_try.V[qf[3]] - m_try.V[qf[1]]), up) > 0.0:
        m_try, mouth_rings = ports.extend(mesh, ring[::-1], [r[::-1] for r in lip_rings])
    mesh = m_try
    mesh, _ = _loft.cap(mesh, mouth_rings[-1], -up, dome=-0.8 * ro)
    for j in range(N_ARMS):
        a = order[j]
        cc, na, ba, ta, ra = arm_frame(a, 0.999)
        mesh, _ = _loft.cap(mesh, arm_rings[j][-1], ta, dome=0.0008)
    # ---------------------------------------------------------------- PORTS: the eyes and the funnel
    from .. import ports
    fixed_ids = list(rim_fixed)
    # the body grid as it lies on the shape: its quads were added first, ring gap by ring gap (face ids shift as ports
    # are cut, so every block is taken as corner tuples before the first cut; corners do not shift)
    QB = mesh.Q[:(NB - 1) * K]
    CB = mesh.V[QB].mean(1)

    def locate(pt):
        """the body grid's (ring gap, column) under a point: its nearest quad on the shape"""
        f = int(np.argmin(np.linalg.norm(CB - pt, axis=1)))
        return f // K, f % K

    def block(rows, cols):
        """the corner tuples of the body quads in ring gaps rows[0]..rows[1] and columns cols[0]..cols[1]"""
        return [tuple(QB[i * K + (k % K)]) for i in range(rows[0], rows[1] + 1) for k in range(cols[0], cols[1] + 1)]

    def faces_of(quads):
        lut = {tuple(q): f for f, q in enumerate(mesh.Q.tolist())}
        return [lut[tuple(int(x) for x in q)] for q in quads]

    def col_span(ks):
        """the columns' span (first, last) round the ring, unwrapped about their circular mean"""
        kc = int(np.round(np.angle(np.exp(1j * np.asarray(ks) * 2 * np.pi / K).mean()) / (2 * np.pi / K))) % K
        dk = ((np.asarray(ks) - kc + K // 2) % K) - K // 2
        return kc + dk.min(), kc + dk.max()
    # the EYES: each lid opens round its eyeball's axis (eye_ap: the aperture's half-angles fore and aft, up and down;
    # round in the live eyes), its fold on the aperture's RIM, where the sculpt's carve (a cone from the eyeball's
    # centre) meets the shape: on rays from the eyeball's centre at the aperture's angle (r4's fold, 1.13 Re at +11 deg
    # projected along the gradient, stood for a socket 4.9 mm deep; v4's eye is near flush with its turret, the rim
    # 1.4 mm over the eyeball above it, and 6 deg past the rim the rays below and in front ran 30 mm through the
    # blended crease between the turret and the head mass without leaving the shape)
    a_h, a_v = np.radians(spec['eye_ap'][0]), np.radians(spec['eye_ap'][1])
    beta = lambda a_: 1.0 / np.sqrt((np.cos(a_) / a_v) ** 2 + (np.sin(a_) / a_h) ** 2)

    def eye_frame(out):
        """the lid's frame about the eye's axis, as ports.loop_frame makes it (e1: up, off the axis)"""
        e1 = up - np.dot(up, out) * out
        e1 /= np.linalg.norm(e1)
        return e1, np.cross(out, e1)

    def on_eye(E, out, rad, bet, a_):
        e1, e2 = eye_frame(out)
        d_ = np.cos(bet)[:, None] * out + np.sin(bet)[:, None] * (np.cos(a_)[:, None] * e1 + np.sin(a_)[:, None] * e2)
        return E + rad * d_

    def fold_ring(E, Re, out, a_):
        d_ = (on_eye(E, out, 1.0, beta(a_), a_) - E)
        p_, st_ = prog.project(E + d_ * Re, d_, maxd=0.03)
        if (st_ != 0).any():
            log(f'[cage] ⚠ eye fold: {int((st_ != 0).sum())} of {len(a_)} rays from the eyeball missed the shape')
        return settle(p_)
    # the block round each eye: the grid's quads within the fold ring's reach of the eye's axis (+ eye_gap) angle by
    # angle round it, on the aperture's side of the turret, as one rectangle of ring gaps and columns; the right eye's
    # mirrors the left's. Centred on the APERTURE, not the mound: the aperture faces 55 deg out from forward, and a
    # block round the mound's own cell held the fold ring at its edge (v4: the loop-to-fold band folded over the
    # turret's top)
    c_e, out, E, Re = eye_geom(spec, 1)
    e1, e2 = eye_frame(out)
    a48 = np.linspace(0.0, 2 * np.pi, 49)
    F48 = fold_ring(E, Re, out, a48[:-1])
    polar = lambda X: (np.linalg.norm((X - E) - np.outer((X - E) @ out, out), axis=1),
                       np.arctan2((X - E) @ e2, (X - E) @ e1) % (2 * np.pi))
    rf, _ = polar(F48)
    rq, aq = polar(CB)
    near = (rq < np.interp(aq, a48, np.append(rf, rf[0])) + cage['eye_gap']) & ((CB - c_e) @ out > 0.0)
    ii, kk = np.nonzero(near.reshape(NB - 1, K))
    rows_e, cols_l = (int(ii.min()), int(ii.max())), col_span(kk)
    cols_r = (K - 1 - cols_l[1], K - 1 - cols_l[0])
    assert K // 2 < cols_l[0] and cols_l[1] <= K - 2, f'the eye blocks meet across the dorsal midline: {cols_l}'
    eyes = [(block(rows_e, cols_l),) + eye_geom(spec, 1)[1:], (block(rows_e, cols_r),) + eye_geom(spec, -1)[1:]]
    eye_rings = []
    fa, fb, fra, frb = funnel_geom(spec)
    # the funnel's block CONTAINS the cone's true footprint (+ one cell): the footprint first, at 64 angles, located on
    # the body grid (t05: a fixed 6 x 10 block cut inside an oblique footprint, its first band ran backward at the top)
    base = _sdf.Program()
    base.sweep(P, n, body_radius(sP, spec) * body_taper(sP, spec), a2=0.035, phi2=0.0, a4=0.012,
               aspect=body_aspect(sP, spec))
    fax = (fb - fa) / np.linalg.norm(fb - fa)
    e1f = up - np.dot(up, fax) * fax
    e1f /= np.linalg.norm(e1f)
    frame_f = (e1f, np.cross(fax, e1f), fax)
    foot64, t64 = ports.cone_footprint(base, np.linspace(0, 2 * np.pi, 64, endpoint=False), frame_f, fa, fb, fra, frb,
                                       lift=0.0, return_t=True)
    # a footprint point is a CROSSING only where the base's field is zero there: with none on a surface line
    # cone_footprint falls back to the line's least |f| (v4: the cone lies wholly inside the body sweep, none of its 64
    # lines leaves it, and the fallback's extrapolated points made a block over half the grid: t04's KeyError)
    f64 = np.abs(base.eval(foot64))
    funnel_port = bool(np.all((f64 < 2.0e-4) & (t64 >= -0.4) & (t64 <= 0.8)))
    if not funnel_port:
        log(f'[cage] ⚠ NO FUNNEL PORT: the funnel cone does not leave the body sweep all round '
            f'({int((f64 >= 2.0e-4).sum())} of 64 surface lines never cross it): funnel_geom lies inside the body')
    funnel_block = []
    if funnel_port:
        foot64 = foot64 + base.normals(foot64) * 0.0015
        cells = np.array([locate(p) for p in foot64])
        k_lo, k_hi = col_span(cells[:, 1])
        g = cage.get('funnel_gap', 2)
        rows_f = (max(cells[:, 0].min() - g, 0), min(cells[:, 0].max() + g, NB - 2))
        cols_f = (k_lo - g, k_hi + g)
        # the rectangle with its four corner cells left out: a rounder loop round the cone (the flank funnel's
        # upper-back corner sat in the head-mantle crease and its band to the halfway ring folded)
        funnel_block = [tuple(QB[i * K + (k % K)]) for i in range(rows_f[0], rows_f[1] + 1)
                        for k in range(cols_f[0], cols_f[1] + 1) if not (i in rows_f and k in cols_f)]
        # clear of the eyes' blocks, not even sharing a corner with them (one shared corner merges the two holes; v4's
        # footprint ran over half the grid and into an eye's block: t04's KeyError in faces_of)
        taken = {v for quads, *_ in eyes for q_ in quads for v in q_}
        if taken & {v for q_ in funnel_block for v in q_}:
            log('[cage] ⚠ NO FUNNEL PORT: its block meets an eye\'s')
            funnel_port, funnel_block = False, []
    for quads, out, E, Re in eyes:
        # the eye: the body loop -> a ring halfway to the fold (on the shape) -> the lid's fold on the rim (on the
        # shape: pinned) -> the lid's edge on the eyeball at the aperture -> a tuck inside the eyeball -> a socket cap
        # behind it (all three fixed: designed on the eyeball, not on the shape)
        mesh, loop = ports.cut(mesh, faces_of(quads))
        ang, (e1, e2, ax) = ports.loop_frame(mesh.V, loop, E, out, up)
        # the lid's rings EVENLY spaced round the aperture, the fold too (the body loop is a rectangle of quads: its
        # vertices bunch along some sides and spread along others, and the lid's edge read as a squarish octagon,
        # t14). The bands out of the body loop take up the change, two of them through a ring halfway (one band from
        # the block's rectangle, its steps round the eye 0.6-19.8 deg, to the even fold 7-33 mm away fanned into
        # skewed quads over the turret, v4; the funnel's halfway ring, t05)
        un = np.unwrap(ang)
        dirn = 1.0 if un[-1] > un[0] else -1.0
        base_even = dirn * 2.0 * np.pi * np.arange(len(un)) / len(un)
        even = base_even + np.angle(np.exp(1j * (un - base_even)).mean())
        fold = fold_ring(E, Re, out, even)
        halfway = 0.5 * (mesh.V[loop] + fold)
        d_h = (halfway - E) / np.linalg.norm(halfway - E, axis=1, keepdims=True)
        rings = [cast(halfway, d_h), fold, on_eye(E, out, Re * 1.025, beta(even), even),
                 on_eye(E, out, Re * 0.86, beta(even) - np.radians(3.0), even),
                 on_eye(E, out, Re * 0.62, beta(even) * 0.85, even)]
        mesh, rids = ports.extend(mesh, loop, rings)
        pinned += [int(x) for x in rids[2]]
        half = len(loop) // 2
        mesh, G = _loft.cap(mesh, rids[-1], -out, shape=(half // 2, half - half // 2))
        fixed_ids += list(rids[3]) + list(rids[4]) + list(rids[5]) + [int(x) for x in G.ravel()]
        eye_rings.append(rids)
    # the funnel: the body loop -> rings along the cone (projected) -> the rim at the tip -> the lip rolling in -> the
    # lumen (fixed) -> a cap inside
    funnel_rings = []
    if funnel_port:
        mesh, loop = ports.cut(mesh, faces_of(funnel_block))
        ang, (e1, e2, ax) = ports.loop_frame(mesh.V, loop, fa, fax, up)
        # the cone's rings EVENLY spaced round it, as the eyes' are: the block's loop seen along an oblique funnel's
        # axis folds over itself, and its own angles ran backward over the funnel's upper-back side (one column folded
        # through the halfway ring, the footprint and the first cone ring: the flank funnel at 51 deg). The bands out
        # of the loop take up the change
        un = np.unwrap(ang)
        dirn = 1.0 if un[-1] > un[0] else -1.0
        base_even = dirn * 2.0 * np.pi * np.arange(len(un)) / len(un)
        ang = base_even + np.angle(np.exp(1j * (un - base_even)).mean())

        def on_cone(tt, scale=1.0, inward=0.0):
            """points on the cone at parameter tt (a scalar, or one per loop vertex)"""
            tt = np.broadcast_to(np.asarray(tt, np.float64), (len(ang),))[:, None]
            cpt = fa + (fb - fa) * tt - fax * inward
            rr = (fra + (frb - fra) * tt) * scale
            return cpt + rr * (np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2)
        # the first ring: the cone's TRUE footprint on the body (the body sweep alone as the base surface)
        foot, t_foot = ports.cone_footprint(base, ang, (e1, e2, ax), fa, fb, fra, frb, lift=0.0025, return_t=True)
        # a ring half way from the block's rectangle to the footprint (two milder bands, not one skewed frame), eased
        # along itself so the rectangle's corners spread their turn over the ring (a bare midpoint at the block's
        # upper-back corner, in the head-mantle crease, folded the band from the loop: the flank funnel; cast onto the
        # shape out from the axis as the eyes' is, the ring caught the funnel's own flank: 9-11 folds)
        hw_ = cage.get('funnel_half', 0.5)
        halfway = (1.0 - hw_) * mesh.V[loop] + hw_ * foot
        for _ in range(3):
            halfway = 0.5 * halfway + 0.25 * (np.roll(halfway, 1, axis=0) + np.roll(halfway, -1, axis=0))
        # the cone's rings start from EACH VERTEX'S OWN footprint (the funnel leans along the body: its underside
        # leaves the body at t ~ 0.55; a ring at a fixed t = 0.40 lay behind the footprint there: t05's 56 folds)
        tf = np.clip(t_foot, 0.0, 0.9)
        on_t = lambda share: on_cone(tf + (0.93 - tf) * share)
        # the lip rolling in to the lumen (its radius a share of the tip's: funnel_lumen, matched by the sculpt's carve)
        fl = spec.get('funnel_lumen', 0.72)
        rings = [halfway, foot, on_t(0.33), on_t(0.66), on_cone(0.93), on_cone(1.0, 0.98, -0.0030),
                 on_cone(1.0, fl + 0.02, -0.0018), on_cone(1.0, fl - 0.08, 0.006)]
        mesh, rids = ports.extend(mesh, loop, rings)
        funnel_rings = rids
        L2 = len(loop) // 2
        mesh, G = _loft.cap(mesh, rids[-1], -fax, shape=(L2 // 2, L2 - L2 // 2))
        fixed_ids += list(rids[6]) + list(rids[7]) + list(rids[8]) + [int(x) for x in G.ravel()]
    # the support rows pinned through the fit as well (crown v5d: they stay on the fold's profile, where the junction's
    # relax left them too)
    pinned += [int(top[r, k]) for k, rs in sup_of.items() for r in rs]
    pin = np.zeros(len(mesh.V), bool)
    pin[pinned] = True
    fixed = np.zeros(len(mesh.V), bool)
    fixed[fixed_ids] = True
    # the quad gate's exemption (attrs 'fixed': designed off the shape, faces turned from it by design: the eyes'
    # tucks, the lumen) leaves out the web columns' rim vertices. They sit 0.9 mm inside the rim's apex, fixed for the
    # fit only; their quads face as the membrane does, so t04 keeps judging them (as exempt corners they took the 128
    # rim quads out of its fold and tilt counts)
    exempt = fixed.copy()
    exempt[rim_fixed] = False
    mesh.attrs['fixed'] = exempt[:, None].astype(np.float64)
    dirs = np.full((len(mesh.V), 3), np.nan)
    for v, d in first_dirs.items():
        dirs[v] = d
    # drop the cut blocks' interior vertices, remapping every per-vertex table
    used = np.unique(mesh.Q)
    remap = np.full(len(mesh.V), -1, np.int64)
    remap[used] = np.arange(len(used))
    mesh = mesh.compact()
    rm = lambda a: np.where(np.asarray(a) >= 0, remap[np.asarray(a)], -1)       # (-1: past a column's end, kept)
    return mesh, dict(body=rm(body), top=rm(top), bot=rm(bot), arm_rings=[[rm(r) for r in rings] for rings in arm_rings],
                      pinned=pin[used], order=order, first_dirs=dirs[used], fixed=fixed[used],
                      creases=rm(np.array(creases, np.int64)), side_seams=rm(np.array(side_seams, np.int64)),
                      strip=rm(np.array(strip, np.int64)),
                      # (the back's band, octopus_uv, is cut off at this row: a fold's crease, or on a column with
                      # support rows and no crease its last support, past the fold's corner, crown v5d; the band at
                      # row 1 there left the corner's quads in the back sectors' islands, and ARAP laid them over
                      # themselves)
                      crease_row=np.array([crease_of['top'].get(k, max(sup_of.get(k, [-1]))) for k in range(K)]),
                      support_rows=np.array([(sup_of.get(k, []) + [-1] * SUP)[:SUP] for k in range(K)],
                                            np.int64).reshape(K, SUP),
                      funnel_rings=[rm(r) for r in funnel_rings],
                      mouth_rings=[rm(r) for r in mouth_rings], mouth_red=[rm(r) for r in mouth_red],
                      eye_rings=[[rm(r) for r in er] for er in eye_rings], RT=RT, R=R, RB=RB, K=K,
                      crown_top_s=s_end, layout_s=starts, lead_rows=lead_n,
                      row_ends={layer: np.array([plan_rows[layer][k][0] for k in range(K)]) for layer in NR},
                      first_shared=first_shared, web_m=web_m, web_run=web_run)


def web_fold_half(spec, u, us):
    """the web's half-thickness at u (the distance from the mouth over the web's mid-sector depth) and us (the share of
    the way out from the crown to the margin along the patch's column): web_half[0] (the crown's) out to web_fold's
    u0, easing (smoothstep) to the membrane by u1, the membrane thinning from web_fold's third value to the margin's
    web_half[1] (crown v5; without web_fold the v4 line from the crown's to the margin's)"""
    h0, hm = spec['web_half']
    fold = spec.get('web_fold')
    if not fold:
        return h0 * (1 - us) + hm * us
    u0, u1, h_mem = fold
    x = np.clip((u - u0) / (u1 - u0), 0.0, 1.0)
    return hm + (h_mem - hm) * np.clip(1.0 - us, 0.0, 1.0) + max(h0 - h_mem, 0.0) * (1.0 - x * x * (3.0 - 2.0 * x))


def web_lift(spec, plan, j, lam, s):
    """(crown v6b) web j's LIE near its margin, a TENT: the height (m, straight up) its mid-surface rises over the flat
    sheet between the arms' side lines (web_sheet) at (lam, s). The sheet is held up to a CONE rising inward from the
    whole margin at web_tent[sector]: with d the point's distance from the margin (web_plan's margin_p, the sheet's
    own edge; negative past it), z = slope d - (y - y_m) is the cone's height over the sheet (y_m the nearest margin
    point's height); the lift is z where the cone stands higher (out toward the margin, where the sheet lies level)
    and nothing where the sheet already climbs more steeply toward the crown, the two joined by the polynomial smooth
    max over k (k0 = 0.02 ML from ell = 0.25 ML in, rising from 0 at the margin so the margin itself stays where it
    was), times sin^2(pi lam) across the web (rooted on both arms' side lines and level where it leaves them, as the
    sheet was). By the distance from the margin, not the depth along the arms: up the U's walls the margin runs beside
    the arm, and a column's own depth there reached the crown (a ramp 160 mm long beside the arms, lifting the crown
    top 5 mm by the arm roots, where t04's crown-top quads folded). The WALLS: up the U's walls the web is a strip
    between the arm's side line, its root, and the margin, its free edge; held at its root the cone cannot rise from
    that edge, so the strip FALLS toward its free edge at the same slope (-slope x its distance from the nearer side
    line, eased in over 0.02 ML from the root, weighted by the column's lam, 1 under 0.15 of the span and 0 by 0.45,
    and faded out from 0.10 to 0.25 ML in from the margin), so the margin's middle stays where it was and its ends come
    down toward the arms, c226's arch [M c226]: a sand-level camera between two arms looks along those strips, and
    level they were most of Skye's wedges (graze2: 8,600 of the 12,295 web-oral pixels her camera saw lie within 0.1
    of the span of an arm). Past the margin the cone and the fall run on (the cage's rim frames difference the sheet
    across its edge). Zero where the spec has no web_tent (crown v5d's sheet)"""
    lam, s = np.broadcast_arrays(np.clip(np.asarray(lam, np.float64), 0.0, 1.0), np.asarray(s, np.float64))
    tent = spec.get('web_tent')
    if not tent or tent[plan['sector'][j]] <= 0.0:
        return np.zeros(lam.shape)
    shape, lam, s = lam.shape, lam.ravel(), s.ravel()
    M = web_sheet(plan, j, lam, s)
    Q = plan['margin_p'][j]
    A, AB = Q[:-1], Q[1:] - Q[:-1]
    ab2 = np.maximum((AB * AB).sum(-1), 1.0e-20)
    d, ym = np.empty(len(M)), np.empty(len(M))
    for c in range(0, len(M), 2048):
        X = M[c:c + 2048, None] - A[None]
        t = np.clip((X * AB[None]).sum(-1) / ab2[None], 0.0, 1.0)
        D2 = ((X - t[..., None] * AB[None]) ** 2).sum(-1)
        i = np.argmin(D2, axis=1)
        r = np.arange(len(i))
        d[c:c + 2048] = np.sqrt(D2[r, i])
        ym[c:c + 2048] = A[i, 1] + t[r, i] * AB[i, 1]
    g = tent[plan['sector'][j]]
    d = d * np.sign(margin_s(lam, plan, j) - s)
    z = g * d - (M[:, 1] - ym)
    k0, ell = 0.02 * spec['ML'], 0.25 * spec['ML']
    k = k0 * (1.0 - (1.0 - np.clip(d / ell, 0.0, 1.0)) ** 2)
    h = np.maximum(k - np.abs(z), 0.0) / np.maximum(k, 1.0e-12)
    rise = np.where(d > 0.0, np.maximum(z, 0.0) + 0.25 * k * h * h, np.minimum(z, 0.0))
    # the walls' fall: rho, the distance from the nearer side line (eased in over r0: rho - r0 tanh(rho / r0), level
    # where the web leaves the arm, as the sheet left it), weighted by the column's own lam (1 under 0.15 of the span,
    # 0 by 0.45) and faded with the distance in from the margin (1 within 0.10 ML, 0 by 0.25 ML: the strips up the U's
    # walls and the margin's corners, never deep inside beside the arms); past the margin it runs on
    near = np.minimum(lam, 1.0 - lam)
    rho = near * np.linalg.norm(web_sheet(plan, j, 1.0, s) - web_sheet(plan, j, 0.0, s), axis=-1)
    r0 = 0.02 * spec['ML']
    x = np.clip((0.45 - near) / 0.30, 0.0, 1.0)
    f = np.clip((d - 0.10 * spec['ML']) / (0.15 * spec['ML']), 0.0, 1.0)
    fall = -g * (rho - r0 * np.tanh(rho / r0)) * x * x * (3.0 - 2.0 * x) * (1.0 - f * f * (3.0 - 2.0 * f))
    # the cone's rise eased to nothing at both side lines as sin^2 (level where the web leaves an arm: as sin, the web
    # rose off the side lines at up to 19 deg deep inside, and its junction with the arms' flanks creased, the crown
    # v6 checker's crease gate along every web's side lines from 0.11 m out)
    return (np.sin(np.pi * lam) ** 2 * rise + fall).reshape(shape)


def web_patch(armA, armB, spec, margin, cap, nl=81, ns=96, ext=0.15, depth=None, lift=None):
    """the web between two adjacent arms, spanning their FACING SIDE LINES (arm A's +b side, arm B's -b side: the
    cage's web columns use the same lambda, so its margin starts on the arms' surfaces; t04's centreline patch put
    the rim's ends inside the arms): (1-l) SA(s) + l SB(s) for s up to the margin's reach margin(l) (at most cap),
    l from -ext to 1 + ext (the ends tuck into the arms); the half-thickness falls from the crown to the margin
    (depth: the web's mid-sector depth D_mid in metres, the fold's scale, web_fold_half; None: by us alone). FINE
    (~1 mm facets): the shell is an offset of this polyhedral patch by only 1-4 mm, and an offset thinner than the
    facets keeps them (t05's high reproduced the 6-9 mm facets as streaks). lift(lam, s) (crown v6b, web_lift): the
    sheet's rise near its margin, added straight up (the half-thickness is the flat sheet's)"""
    # lambda dense toward the arms (cosine spacing: the margin changes fastest there), plus the extensions tucked into
    # the arms
    inner = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, nl))
    lam = np.concatenate([np.linspace(-ext, 0, 7)[:-1], inner, np.linspace(1, 1 + ext, 7)[1:]])
    nl = len(lam)
    us = np.linspace(0, 1, ns)
    # the side lines sampled once per arm at fine s, then interpolated (vectorised)
    s_fine = np.linspace(0, cap, 600)
    SA = np.array([arm_side(armA, s, spec, +1) for s in s_fine])
    SB = np.array([arm_side(armB, s, spec, -1) for s in s_fine])
    ipA = lambda s: np.column_stack([np.interp(s, s_fine, SA[:, k]) for k in range(3)])
    ipB = lambda s: np.column_stack([np.interp(s, s_fine, SB[:, k]) for k in range(3)])
    V, H = [], []
    mouth = mouth_point(spec)
    for li, l in enumerate(lam):
        sm = min(float(margin(np.clip(l, 0.0, 1.0))), cap)
        ss = us * sm
        V.append((1 - l) * ipA(ss) + l * ipB(ss))
        u = np.linalg.norm(V[-1] - mouth, axis=1) / depth if depth else us
        H.append(web_fold_half(spec, u, us) if depth else
                 spec['web_half'][0] * (1 - us) + spec['web_half'][1] * us)
        if lift is not None:
            V[-1] = V[-1] + np.outer(lift(np.full(len(ss), l), ss), [0.0, 1.0, 0.0])
    V = np.concatenate(V)
    H = np.concatenate(H)
    F = []
    for li in range(nl - 1):
        for si in range(ns - 1):
            a = li * ns + si
            F += [[a, a + ns, a + 1], [a + 1, a + ns, a + ns + 1]]
    return V, np.array(F), np.array(H)
