"""HOOF PRESETS: the rows of the hoof generator (families/hoof.py) and the sizing law, as data.

DEER_PLAN §6.2-§6.3 (work/bestiary/research/DEER_PLAN.md), the hooves study (work/bestiary/deer/hooves/STUDY.md §2.5,
§3) and HF0's measurements (work/bestiary/deer/hooves/build_NOTES.md step 1; every traced point is in
work/bestiary/deer/hooves/scripts/h03_measure.py, the numbers in data/hoof_measures.json).

Units: every shape row is a SHARE OF THE HOOF'S LENGTH HL (toe tips to the back of the heel bulbs, on the ground),
angles in degrees. The generator multiplies by HL in metres, so a hoof of any size is one shape (the study: cervid
hooves are isometric in body mass). Frame as the forge's: +Y up, +Z forward (the toes), +X the creature's left.

TAGS (the plan's legend): [M-seg] measured on a segmented photo, [M-ph] measured by eye on a photo (about +-1.5 % of
HL), [P] a primary source, [C] compiled, [S] seen in a search summary, [R] a game asset measured (never copied),
[D] derived, [E] an estimate with the step that checks it. `TAGS[preset]` holds one tag per row; rows not listed
there are [E].

Only `cervid` is MEASURED (HF0, 11-10). The other four presets hold the study's estimates and are built at HF2 after
their own photo rounds; `ready` says which may be generated.
"""
import numpy as np

# ---------------------------------------------------------------------------------------------- the sizing law


def hoof_length(mass_kg, n_support=4, a_cm=1.86, b=0.334):
    """THE MASS LAW per support foot (DEER_PLAN §6.3): seven cervids' forefoot lengths fit L = 1.86 M^0.334 cm
    (isometric; the critic's refit 1.80 M^0.340 is within 3 % from 40 to 450 kg). The law is a quadruped's, each hoof
    carrying about a quarter, so a host on n support feet loads each hoof with M / n:
    HL = 1.86 (4 M / n)^0.334 cm. Returns metres."""
    return 0.01 * a_cm * (4.0 * float(mass_kg) / float(n_support)) ** b


def natural_band(mass_kg, n_support=4, lo=1.5, hi=2.3):
    """the natural size band in metres: HL / (4 M / n)^(1/3) inside [1.5, 2.3] cm kg^-1/3 (caribou, the snow
    specialist, reads 2.16; a red deer hind 1.62-1.67). Outside it a hoof reads as stilettos or clown shoes, which
    only a mutation knob may ask for."""
    k = (4.0 * float(mass_kg) / float(n_support)) ** (1.0 / 3.0)
    return 0.01 * lo * k, 0.01 * hi * k


def size_on_ring(mass_kg, n_support, ring_radius, preset='cervid', taper_max=0.25, band_len=None):
    """A grafted hoof's size: THE LAW SIZES IT, THE RING BOUNDS IT (the lead's call on DEER_PLAN §12 item 4).
    The coronet's half-width follows from HL; the pastern band from the host's ring to the coronet may taper by at
    most `taper_max` (radius change per unit length: graft_socket's collar bound, REROOT's graft_tube), over
    band_len (default: the preset's pastern length x HL). Returns dict(HL, r_coronet, taper, ok, why): ok False
    reports `graft.size` with the numbers; a caller may then clamp HL to the nearest size that fits (a mutation knob
    may ask for any size)."""
    p = PRESETS[preset]
    HL = hoof_length(mass_kg, n_support)
    r_cor = 0.5 * p['pastern_w'] * HL                       # the haired pastern just above the coronets
    L = float(band_len) if band_len is not None else p['pastern_len'] * HL
    taper = abs(r_cor - float(ring_radius)) / max(L, 1e-9)
    lo, hi = natural_band(mass_kg, n_support)
    ok = taper <= taper_max and lo <= HL <= hi
    why = '' if ok else (f'graft.size: ring r {ring_radius * 1e3:.1f} mm to a coronet of r {r_cor * 1e3:.1f} mm over '
                         f'{L * 1e3:.0f} mm is a taper of {taper:.2f} (bound {taper_max}); HL {HL * 1e3:.0f} mm, '
                         f'natural band {lo * 1e3:.0f}-{hi * 1e3:.0f} mm')
    return dict(HL=HL, r_coronet=r_cor, taper=taper, ok=ok, why=why)


# ---------------------------------------------------------------------------------------------- the cervid rows
# THE CLAW'S PLAN OUTLINE, measured on the red deer's sole (i02, segmented): per station s (0 the toe tip, 1 the
# back of the heel bulb) the abaxial bearing edge and the axial edge, as distances from the foot's midline, the mean
# of the two claws (they differ by 5 % in width: one template, mirrored, so the pair stacks)
_S = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85,
      0.90, 0.95, 1.00]
_ABAXIAL = [0.071, 0.2015, 0.2495, 0.2845, 0.310, 0.3295, 0.3445, 0.357, 0.3665, 0.376, 0.387, 0.3875, 0.384, 0.383,
            0.368, 0.361, 0.3505, 0.3375, 0.319, 0.292, 0.190]
_AXIAL = [0.071, 0.0325, 0.025, 0.0205, 0.015, 0.0115, 0.008, 0.0045, 0.0035, 0.005, 0.0055, 0.0065, 0.006, 0.0065,
          0.0065, 0.008, 0.010, 0.012, 0.020, 0.045, 0.190]

CERVID = dict(
    digits=2, dewclaws=2, ready=True,
    type_mass=dict(stag=170.0, hind=100.0),                  # D1 and D1h (DEER_PLAN §3)
    hind_scale=0.93,                                          # the hind foot a scaled repeat of the fore
    # ---- plan view (the sole), shares of HL
    outline_s=_S, outline_abaxial=_ABAXIAL, outline_axial=_AXIAL,
    pair_w=0.775,                                             # both claws across, at s 0.55
    bulb_from=0.72,                                           # the sole ends and the soft bulb begins (0.26-0.30 long)
    # the wall's ground rim (its thickness at the border). (11-12, fix round 2: rim_axial 0.7 -> 0.40 and rim_wander:
    # i02 at 2x reads 0.022-0.026 on the abaxial side, 0.030 at the toe, 0.008 on the cleft's side, never one width;
    # an even band was half of check 2's "insole". rim_wander: the width's slow change round the claw, a share)
    rim_w=0.027, rim_w_toe=0.033, rim_axial=0.40, rim_wander=0.22,
    white_line=0.010,                                         # between the rim and the sole
    sole_depth=0.035,                                         # the trough between the rims
    spine=(0.10, 0.90),                                       # the sole's middle line runs between these stations
    # ---- side view
    wall_angle=47.5,                                          # the dorsal wall to the ground
    # (fix1: coronet_front_s 0.39 -> 0.375 with ridge_round 0.034 -> 0.06: the rounder front corner pulls the ring's
    # front point back; the ring's front stays at 0.401 behind the toe tip, as before)
    coronet_front_s=0.375, coronet_front_h=0.425,             # the coronet's front: behind the toe tip, above ground
    coronet_back_s=0.97, heel_h=0.30,                         # the coronet's back: the horn's top at the heel
    coronet_nose=(0.40, 0.10), coronet_tail=0.14,             # the ring's front: its oblique abaxial run, its axial turn
    coronet_back_x=0.0,                                      # the ring's back middle, off the heel's own middle
    ridge_at=(0.23, 0.30),                                    # the dorsal ridge's place across the claw: toe, coronet
    ridge_round=0.06,                                         # the ridge's rounding at the coronet (a blur's sigma; 0.022
                                                              # left the turn into the cleft reading as a chamfer on the high;
                                                              # 0.034 a tight crest beside the photos, check1)
    wall_lean=(80.0, 84.0),                                   # the abaxial wall to the ground: mid claw, heel
    axial_inset=0.006, axial_hollow=0.010,                    # the axial wall: upright, hollowed a little
    # ---- THE WALL IS A SHELL, NOT A CONE (11-11, fix round 1 after work/bestiary/deer/hooves/check1_NOTES.md: the
    # ruled wall alone, every column a straight line, read as flat-faced wedges beside the live wapiti e01 and the
    # red deer i01 / i04; its curvature was all across the columns and none along them). Each wall column now bows
    # OUT along the ruled surface's own normal by bulge x sin(pi w(v)) (0 at the coronet and at the ground; w puts
    # the peak at `bulge_peak` of the way down), so the wall is curved both ways: the flank steep at the ground and
    # rolling in under the hair, the toe's front a dome across, the ridge a roll. Amounts, shares of HL: the ridge's
    # own (the dorsal profile is nearly straight in the true side view e02 and in i04), the toe's fan and the flank
    # (the wapiti's near claw in e01 is a bean-shaped shell; from below on i02 the dark wall shows a hair OUTSIDE the
    # bearing rim on the abaxial side, so the flank is near upright at the ground), the toe's inner face (rounds the
    # toe, i01, i08). fix1 measures each against the photos at their own cameras (build_NOTES, FIX ROUND 1)
    # (fix1 F1, look/f04_c.png, out/f04_c_num.json: the ridge's side profile bows 0.8 mm over 59 mm, e02 reads it
    # straight within about 1 mm; the abaxial slope's sections bow 13-15 % of their chords, the checker's ruled wall
    # 4-7 %; the ridge's turn across 12 / 9 / 7 / 4 mm at s 0.1-0.4, it was 9 / 8 / 5 / 3)
    bulge_dorsal=0.008, bulge_toe=0.040, bulge_ab=0.040, bulge_ax_toe=0.020, bulge_peak=0.42,
    bulge_overhang=0.005,                                     # the most the bowed wall may stand outside its bearing edge
    # the coronet's fall from the ridge toward the abaxial side, per unit across (0: level across, the plane of
    # 11-10); the plane's back is raised to keep the heel's measured height
    # (11-11 10:3x, fix round 1: 0.0 -> 0.25. check1: "the coronet a PLANE". On the live wapiti's fore foot from the
    # front (e01, fix1/tmp/e01_front_claws_grid_x6.png) the hair's edge over each claw is an arch, about 9-10 px
    # lower at the abaxial edge than over the crest across about 30 px of a claw whose hoof is about 190 px long:
    # 0.3 per unit across, read on the hair's fringe, not on the band under it; 0.25 keeps the measured heel. The
    # ring at the widest point of the flank now stands 0.321 HL high (it was 0.361): the hairline rises over the crest)
    coronet_fall=0.25,
    # THE PAIR IS NOT AN EXACT MIRROR: the medial claw (III, the -X claw of a left foot) is the primary mirrored and
    # scaled by medial_scale about a point on the midline under the claws' middle (pair_centre_s): a similarity, so
    # it still stacks on the primary's texels. i02: the two claws differ by about 5 % in width [M-seg]
    medial_scale=0.95, pair_centre_s=0.50,
    bulb_eq_h=(0.035, 0.10), bulb_bulge=0.018, bulb_under=0.80,   # the heel bulb: its equator's height (flank, back), bulge, rounding
    periople=0.17,                                            # of the dorsal wall's length, under the coronet
    # (coronet_tuck was 0.05: the claws' least overlap under the stand-in's lip was 0.155 of the ring's radius
    # against G-R10's 0.2, check1/out/k06_gates.json; 0.06 gives the margin)
    coronet_step=0.012, coronet_lip=0.007, coronet_tuck=0.06, # the haired skin proud of the horn; its roll; the tuck
    # ---- the digits above the hoof (the neutral stump stands in for the leg until D6's cage)
    pastern_angle=68.0,                                       # the pastern's front line to the ground, standing
    pastern_axis=66.0,                                        # the digit's own axis (between its front and back)
    pastern_len=0.62,                                         # coronet's front to the fetlock's centre, along it
    pastern_w=0.70, fetlock_w=0.71, cannon_w=0.50,            # across both digits
    digit_w=0.33, digit_fwd=0.0, digit_converge=0.03,         # one digit across; the two lean together going up
    web_blend=0.085,                                          # the skin between the digits (a fillet's radius)
    pastern_d=0.60, fetlock_d=0.72, cannon_d=0.42,            # front to back, square to the limb's axis
    fetlock_h=1.00, fetlock_behind_toe=1.10,                  # the fetlock's centre
    cannon_angle=84.0, stump_top=1.62,                        # the neutral stump: the cannon's lean, where it is cut
    groove_len=0.75,                                          # the cleft runs on up the pastern's front this far
    # ---- the dewclaws (digits II and V): flat blunt pads behind the fetlock, one template
    # (11-10 20:5x: the first clay's dewclaw read as a peg from behind: 0.17 wide, tapered 42 % and rounded only from
    # 0.76. The photos' dewclaw is a blunt flat pad about three quarters as wide as long: i04 0.75, i02 / i03 from
    # below as wide as long (near the lens), the fallow's c03 a round button. Now 0.23 wide, 0.115 thick, blunt)
    # (11-11, fix round 1: dew_t was 0.115 with the side-on taper 0.42 (thickness / length 0.38, thinning to an
    # edge): from behind and on edge the pads read as NAILS (check1). The photos' pad is a thick rounded knob: on
    # edge its thickness is 0.43 of its visible length (i01, the pad seen from the front) to about 0.5 (the wapiti's
    # true side view e02), nearly as thick at its end as at its base, the end a dome both ways (c03, i04))
    # (11-12, FIX ROUND 2, after work/bestiary/deer/hooves/check2_NOTES.md verdict 5: "the dewclaws read as two
    # blue-grey CAPSULES on fur stalks". Three causes, each read on the photos at 2.5-4x, work/bestiary/deer/hooves/
    # fix2/tmp/crops/ and fix2/look/g10_dew_*.png:
    #  1 THE FORM was ONE superellipse section lofted along a straight line with an even taper and a domed end
    #    (dew_round 0.50, dew_taper (0.26, 0.12), dew_out 0.60): a pill from every side. The photos' pad changes
    #    section along its length: `dew_sections` below.
    #  2 THE HANG was 62 deg, pointing down and BACK, away from the leg. On the wapiti's true side view (e02, the
    #    nub's own axis from its top at source pixel (1672, 2735) to its tip at (1679, 2782)) it hangs 83 deg to the
    #    ground with its tip a little FORWARD of its top: it lies along the leg's back, as on i01 and c01.
    #  3 ITS PLACE was typed (dew_base_h 0.81, dew_base_s 1.36): the base ring stood a centimetre off the stand-in's
    #    skin and the mount to it was a stalk. The base is now DERIVED from the measured tip, the hang and the length
    #    (families/hoof.dewclaw_frames), and the tip hangs under the fetlock's rearmost point, as on e02: fore foot,
    #    tip 0.57-0.62 behind the heel with the fetlock's back at 0.61; hind foot 0.45 with the fetlock's back at 0.41.
    #    The stand-in's fetlock is the hind's row (1.10 behind the toe, 0.72 deep: its back 0.46 behind the heel).
    # dew_len: the visible horn, hairline to tip [M-ph e02 0.31, 0.32; i01 0.29, 0.24-0.27 by fix2's cut]; dew_w: its
    # widest across, face on (i04 0.75-0.78 of its length, c05 0.62, e02's nub 0.16-0.18 wide; it was 0.23); dew_t:
    # its thickest, on edge (i01: 79-83 of 664 pixels = 0.119-0.125; it was 0.140 from "e02 about 0.5", which is the
    # FACE seen from the side: e02 looks at the pad's face)
    dew_len=0.31, dew_w=0.21, dew_t=0.125,                    # long, across, thick
    # THE PAD'S SECTIONS ALONG ITS LENGTH (t: 0 the hairline .. 1 the tip), as shares of dew_w and dew_t:
    #   w      the width face on: a SHIELD, widest just under the hairline, its sides straight at about 20 deg to
    #          a rounded apex of 2.6 mm [M-ph i04: a rounded triangle, sides at 23-32 deg on a shorter hind pad; c05]
    #   thick  the thickness on edge: a HALF TEARDROP, thickest at 0.6, a blunt end of 3.7 mm [M-ph i01 on edge:
    #          0.10 HL at the hair, 0.125 at its thickest, the end a round cap nearer the leg's side]
    #   e_out  the outer face's roundness (2 an ellipse, under 2 a crest): a soft ridge down the middle of the pad,
    #          fading at both ends [L i04: a pale ridge line from the apex toward the base; c04: a crest]
    #   skew   the crest's place off the middle, a share of the half width, toward the pad's +a side [L i04: the
    #          two facets 40 : 60; c04: the crest toward one edge]
    #   inner  the share of the thickness on the leg's side of the widest line, and e_in its squareness: the face
    #          against the leg is FLAT with a rim (a D section): the pad's own sole inside its wall's edge [L i02 from
    #          below, end on: a dark crescent of wall round a paler flaky face]
    # Both profiles are splined in sqrt(1 - t), so the end is a round nose. One template for all eight
    dew_sections=dict(t=(0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.88, 0.96, 1.00),
                      w=(0.96, 1.00, 0.97, 0.89, 0.77, 0.60, 0.42, 0.24, 0.00),
                      thick=(0.80, 0.88, 0.95, 0.99, 1.00, 0.94, 0.76, 0.48, 0.00),
                      e_out=(2.10, 2.00, 1.88, 1.80, 1.80, 1.86, 1.95, 2.00, 2.00),
                      skew=(0.00, 0.08, 0.16, 0.21, 0.22, 0.18, 0.10, 0.03, 0.00),
                      inner=0.16, e_in=4.0, fuller=0.05, lean=-0.035),
    # WHERE IT HANGS (11-12 10:5x, read on the live wapiti's fore foot from the front, e01 at 5x, work/bestiary/deer/
    # hooves/fix2/tmp/crops/e01_fore_front_x5.png; the hoof 208 px, the cleft's line at x 4783): the dewclaw is a
    # SLIM LOBE HANGING BESIDE THE PASTERN from the fetlock's back corner: its outer edge 0.42 from the midline, the
    # gap to the pastern at 0.29, so its middle is 0.355 out; 0.125 wide with its hair (the pad seen on edge); its
    # top leaves the fetlock's outline at the fetlock's widest height (0.98), its tip is 0.19 above the coronet's
    # front (0.62); it leans out about 9 degrees going down; only its lower 0.19 shows dark horn under the hair.
    # The tip's place behind the heel and its height [M-ph e02]. (dew_apart was 0.46 [E], 0.70, then 0.77 from
    # "outer face 0.47-0.50"; the stand-in's mount to it was a stalk each time.)
    # dew_face: the way the outer face looks, for the left pad (the right pad is its mirror): outward, a little back
    # [M-ph e01 and i01 from the front: the pad on EDGE, 0.12 wide; e02 from the side: its face. I tried 45 degrees
    # back at 10:40 (i04's face-on pad, an oval print): from the front the pad then spans 0.19, half again e01's]
    # (10:55, the clay from the side: with the pad's AXIS under the fetlock's rearmost point (0.46 behind the heel on
    # the stand-in's hind row) its back edge stood 0.10 behind the leg and the root to it was a spur. On e02 the leg's
    # back outline runs straight down into the nub's BACK EDGE: the pad's width, 0.21, lies along the foot. So the
    # axis is 0.36 behind the heel, the back edge under the fetlock's back. Tip height 0.54 -> 0.58: e02's hind foot;
    # e01's fore foot from the front reads 0.62)
    dew_tip_h=0.58, dew_tip_behind_heel=0.36, dew_apart=0.71, dew_hang=83.0, dew_tip_fwd=1.0,
    dew_splay=0.12, dew_face=(0.94, 0.05, -0.34),
    dew_tuck=0.18, dew_hook=0.04, dew_periople=0.22,          # under the skin; the tip's turn; young horn's share
    # THE DIGIT'S HAIRED ROOT ON THE NEUTRAL STUMP (the stand-in's, families/hoof.stump_program; the deer's own leg
    # replaces it). The cuff: `rise` up the pad's own axis from the hairline, its sections' half sizes (across,
    # outward) after the base ring itself: slim, the pad's own width (e01: the lobe is no wider above its horn). The
    # root: a round cone from `cone_at` of the cuff's length (radius cone_r[0]) to `root`, THE FETLOCK'S BACK CORNER
    # (from the fetlock's centre: across, up, forward; radius cone_r[1]): on e01 the fetlock's widest outline from
    # the front, 0.36, is where the lobe begins: the dewclaws' roots are the fetlock's back corners. Its fillet is
    # the web's (web_blend: one radius in a ROUND group)
    # (10:47, the clay from the front: ovals 0.060-0.066 outward and a cone of 0.080 stood 0.455 from the midline at
    # the fetlock's height, a wing; on e01 the lobe's outer edge there is 0.375, the straight continuation of the
    # pad's own outer face. The cuff is no thicker than the pad now)
    # (10:57, the clay: a root that ended at the fetlock's own height left the cuff's top standing as a KNOB on each
    # back corner. On e01 the leg's outline widens in one line from the cannon (0.25 at 1.6 HL up) to the lobe's top
    # (0.375 at 0.98): the root runs on UP the cannon's back corner and the cuff's top is inside it)
    dew_mount=dict(root=(0.15, 0.30, -0.12), rise=0.16, ovals=((0.108, 0.046), (0.106, 0.048), (0.095, 0.046),
                                                               (0.070, 0.040)),
                   cone_at=0.45, cone_r=(0.062, 0.150)),
    # ---- the rig's rest numbers (the stand solve refines them on a host)
    coffin_s=0.52, coffin_h=0.30, coffin_x=0.19,              # the coffin joint (P2 | P3) inside the capsule
    # (11-10 23:0x: the first rows drew the digit from the OUTLINE's fetlock centre (1.10 behind the toe, 1.00 up)
    # to the coffin joint: a pastern lying at 50 deg, look/h70_rig_rows.png. The outline's centre is the middle of
    # the fetlock's bulge with its sesamoids; the JOINT is in the bone at its front. The chain is now built from
    # the coffin joint up the pastern's BONE axis by the two phalanges, as the base's skeleton builds it)
    bone_axis=(68.0, 70.0),                                   # the pastern's bone axis over the ground: fore, hind
    p1_len=0.571, p2_len=0.437,                               # P1 and P2, shares of the fore hoof's length
    digit_x_fetlock=0.097,                                    # each digit's joint at the fetlock, off the midline
    splay_rest=0.0, splay_max=12.0,
)
TAGS = dict(cervid=dict(
    outline_s='M-seg i02', outline_abaxial='M-seg i02 (stations 0.05-0.65), M-ph i02 (the rest)',
    outline_axial='M-ph i02', pair_w='M-seg i02; tracks t13 0.64, t10 0.73-0.80', bulb_from='M-ph i02',
    rim_w='M-ph i02', rim_w_toe='M-ph i02',
    rim_axial='M-ph i02 at 2x (fix2): 0.008 HL on the cleft\'s side against 0.022-0.026 on the abaxial side',
    rim_wander='M-ph i02 at 2x: the band is never one width (0.022-0.026 along one flank)', sole_depth='E: looked at i04 and c08 (a trough); the clay beside i04',
    wall_angle='M-ph wapiti e02 46.1 and 49.4, e01 45.4', coronet_front_s='M-ph e02 0.362, 0.366',
    coronet_front_h='M-ph e02 0.376, 0.427, e01 0.427', heel_h='M-ph e02 0.325, 0.286',
    ridge_at='M-ph i02 (the toe tip 0.23 across), i01 (the highlight line)', wall_lean='E: looked at e01 front, i04',
    axial_lean='E: P Sisson "concave and grooved"; i04', periople='E: looked at fallow c03 (0.15-0.2)',
    coronet_step='E: looked at e01, i01 (hair over the wall)', pastern_angle='M-ph e02 hind 67.6 (walk), fore 59.6 sunk; critic d06 75-78',
    pastern_len='D from fetlock_h and the angle', pastern_w='M-ph i01 0.88 x pair_w, e01 0.93', fetlock_w='M-ph e01 0.91',
    cannon_w='M-ph e01 0.64', pastern_d='M-ph e02 0.62', fetlock_d='M-ph e02 0.69-0.77', cannon_d='E: CERVIFIED metacarpal 21.4 x 17.1 mm bone + tendons',
    fetlock_h='M-ph e02 0.96, 1.05', fetlock_behind_toe='M-ph e02 1.05, 1.22', groove_len='M-ph e01 1.0 of the hoof\'s width',
    dew_len='M-ph e02 0.31, 0.32, i01 0.29 (fix2\'s colour cut of i01: 0.24, the hair over its base)',
    dew_w='M-ph i04 0.75-0.78 of its length (a hind pad), c05 0.62 (fallow), e02 0.16-0.18 HL (the face, seen from the side)',
    dew_t='M-ph i01 on edge: 0.119-0.125 HL (fix2 g10_dew_measure.py; 11-11 fix1 had 0.140 from "e02 about 0.5", which is the face)',
    dew_sections='M-ph i04 (the face: a rounded triangle), i01 (on edge: a half teardrop), L i02 (end on: a D of wall round a sole), c04 / c05 (the crest, the blunt clean tip): work/bestiary/deer/hooves/fix2/look/g10_dew_*.png',
    dew_tip_h='M-ph e02 0.58 (hind), 0.48 (fore; 0.46 by fix2); e01 fore from the front 0.62',
    dew_tip_behind_heel='M-ph e02: the nub\'s BACK EDGE continues the leg\'s back outline (the fetlock\'s back: hind 0.41-0.45, fore 0.57-0.62 behind the heel; 0.46 on the stand-in\'s row), so the axis is half the pad\'s width in front of it: 0.36',
    dew_apart='M-ph e01 fore foot from the front at 5x: the lobe between 0.29 and 0.42 from the midline (its middle 0.355); i01 0.47 its outer face (a close phone photo)',
    dew_hang='M-ph e02 fore foot: the nub\'s own axis 83 deg to the ground, its tip forward of its top (it was 62, back)',
    dew_splay='M-ph e01 fore foot from the front: the lobe leans out about 9 deg going down (0.08 before)',
    dew_face='M-ph e01, i01 (on edge from the front, 0.12 wide), e02 (its face from the side); L i04',
    dew_mount='E / L: the stand-in\'s. e01 front (the lobe begins at the fetlock\'s widest outline, 0.36), e02 (the leg\'s back outline runs down into the nub), i04 (the pad on a haired swelling)',
    hind_scale='E: track guides hind 6-7 against fore 8-9 cm is 0.78; the hooves study keeps a scaled repeat; HF2 measures',
    type_mass='C HMW 2011 via DEER_PLAN §3', coffin_s='E: h03 horse section 0.4 HL up; HF3', coffin_h='E: HF3',
    bone_axis='Ph: the base lane\'s joint centres on its photo d21 (work/bestiary/deer/base/priv/forge/species/red_deer.py HOOF.pastern)',
    p1_len='S -> E: the base lane\'s P1 = 0.235 x the metacarpal (59.1 mm on D1)', p2_len='S -> E: 0.180 x the metacarpal (45.2 mm)',
    digit_x_fetlock='P: CERVIFIED distal metacarpal 38.6 mm x 1.06: the condyles\' centres 20 mm apart',
    splay_rest='M-ph i02 (the claws touch from 0.25 back)', splay_max='E: HF5',
    bulge_dorsal='M-ph: fix1 step F1, the dorsal profile against e02 / i04 at their cameras',
    bulge_toe='M-ph: fix1 step F1, the toe\'s front against e01 (quarter) and i01 (solved camera)',
    bulge_ab='M-ph: fix1 step F1, the flank against e01 (front, quarter) and i02 (the wall a hair outside the rim from below)',
    bulge_ax_toe='L: i01, i08 (the toe rounded on its inner face)', bulge_peak='L: e01 quarter, i04',
    coronet_fall='M-ph e01 front: the hair\'s fringe over each claw falls about 0.3 per unit across toward the abaxial edge (fix1 F1b; 0.25 used, the fringe is not the band)',
    medial_scale='M-seg i02 (the claws differ by about 5 % in width); which claw is the larger: E',
    coronet_tuck='D: G-R10\'s 0.2 of the ring\'s radius with margin on the stand-in (check1 k06: 0.155 at 0.05)',
))

# the other presets: the study's rows (STUDY §2.5), every one [E] / [P] / [S] as tagged there; built at HF2
PRESETS = dict(
    cervid=CERVID,
    caprine=dict(digits=2, dewclaws=2, ready=False, pair_w=0.65, wall_angle=52.0, heel_toe=0.40, periople=0.15),
    bovine=dict(digits=2, dewclaws=2, ready=False, pair_w=0.90, wall_angle=50.0, heel_toe=0.48, periople=0.15),
    suid=dict(digits=2, dewclaws=2, ready=False, pair_w=0.80, wall_angle=50.0, heel_toe=0.50, periople=0.20),
    equine=dict(digits=1, dewclaws=0, ready=False, pair_w=0.95, wall_angle=47.0, heel_toe=0.33, periople=0.20),
)
SUB_PRESETS = dict(caribou=dict(base='cervid', note='crescent claws, concave soles, long hooked dewclaws, a white '
                                                     'coronet band; L / M^(1/3) ~2.2'),
                   moose=dict(base='cervid', note='long splaying claws, larger dewclaws'),
                   bison=dict(base='bovine', note='round wide prints'))

# ---------------------------------------------------------------------------------------------- the horn rows
# THE HOOF'S MATERIAL, AS A RECIPE ROW OF THE ONE HORN MATERIAL STAGE (families/horn_skin.material: the HORN builder's
# file, DEER_CRITIC §2; the options this row uses beyond the antler's are staged in work/bestiary/deer/STAGED.md and
# built in work/bestiary/deer/hooves/priv/forge/families/horn_skin.py). Colours linear; roughness as three's.
#   * THE WALL AND THE DEWCLAWS go through the stage's own rules, as any keratin sheath will (a ram's horn is the
#     same tissue): pale / mid / dark by the stain (flats 0.44 mid + 0.56 dark = the slate; hollows dark; worn ring
#     crests toward pale), `ivory` where the fields' `tip` says worn (the toe's thin brown horn), `young` the
#     periople, the world's dust, the mottle. Base values are growth.RECIPES['keratin'] (ior 1.55, sss 0.20).
#   * THE OTHER TISSUES AND THE MARKS are `layers`, each a field of families/hoof_surface.hoof_fields and a colour.
# HOW THE ROWS WERE SET (11-10 22:2x, the second paint; the first, look/h60_board_a.png, read as grey stone: a pale
# wall under a heavy dust line, scratches like straw, a pale chalk sole with dark holes, bulbs as pale as the leg):
#   [M-ph] by the snow as a white reference (scripts/h51_photo_albedo.py -> data/photo_albedo.json; good to about a
#   third on matte zones, useless on the glossy wall, whose sheen is the sky): under the hairline (0.116, 0.098,
#   0.088); the sole's dark patches L 0.02-0.09, its scurf L 0.16-0.35, its median (0.166, 0.146, 0.134) on a dry
#   winter foot; the rim from below (0.161, 0.117, 0.082); a bulb L 0.03; the wall in shade L 0.008-0.05.
#   [L] looked at beside i01 (walls), i04 (a live hind foot: sole dark and smooth, the edge pale), e01 (sun, dust).
# Looks this must not contradict: the wolf's claws (work/bestiary/wolf/w4/geo/g50_skin.py) and the octopus's beak
# (species/octopus_beak.paint_beak). Lengths are shares of HL: horn_recipe() turns them into metres.
HORN_ROWS = dict(cervid=dict(
    base='keratin',
    pale=(0.070, 0.064, 0.060),                                     # worn ring crests [L i01]
    # (11-12, FIX ROUND 2, check 2's failure 2: mid was (0.032, 0.034, 0.039) and dark (0.010, 0.010, 0.012), blue /
    # red 1.2: read on i01, a foot lying in BLUE SNOW SHADE, so the snow's sky went into the horn's own colour (and
    # the sole's and the shed plates' below). The horn's hue is read where the light is known: e01, overcast: the
    # dark horn's median sRGB (57, 53, 51) in the quarter view's box (check2/out/c09_light.json), (59, 58, 59) on the
    # hind claw's wall (fix2/out/g40_light.json): linear r : g : b about 1 : 0.92 : 0.88, a black with a little brown
    # in it. The luminances are kept (they were matched to the photos' at the same brightness))
    mid=(0.0363, 0.0334, 0.0319),                                   # [M-ph e01 hue; L i01]
    dark=(0.0109, 0.0100, 0.0096),                                  # black horn in its hollows [M-ph e01 hue]
    ivory=(0.060, 0.044, 0.032),                                    # the worn toe: thin brown horn [L i01]
    bare=(0.300, 0.270, 0.220),                                     # (no cut face on a hoof; the stage asks the key)
    dust=(0.210, 0.185, 0.150),                                     # [L e01]
    # (top -0.40 painted every growth ring as a pale band: look/h60_board_b.png read as stacked layers; the rings
    # are in the normal map, their colour only a hint)
    # (cavity 1.0 and ao_local 1.2 stained every CONTACT SHADOW into the colour and the roughness: the bake's rays
    # hit the skin's lip, the other claw and the leg, so a dark rough line ran under the coronet, round each
    # dewclaw's hairline and down the cleft: the streak audit's clusters, look/h46_flags_h.png. A contact's shade
    # is the AO map's alone. The horn's OWN hollows (ring troughs, scores, the sole's cracks) are read from the
    # bake's curvature instead, which knows no neighbour: the stage's conc / conc_mid)
    stain=dict(flat=0.80, cavity=0.0, ao_local=0.0, conc=0.50, conc_mid=0.30, gutter=0.0, top=-0.15, along=0.0),
    polish=dict(start=0.5, band=(0.5, 1.5), top=0.10, cavity=-0.15, rub=0.0, noise=0.08),
    # (11-11 05:0x, the material pass after THE ENGINE'S PICTURES AT THE PHOTOS' CAMERAS, look/h80_engine_board_c.png.
    # The wall: flat -0.18 (0.42) -> -0.12 (0.48), and `matte` patches to 0.66 outside the worn toe: at one even
    # gloss the wall mirrored the sky as a blue-grey sheet. Scores: pale HAIRLINES by colour (they were 0.22 of a
    # grey barely paler than the wall, with the relief doing the work: creased foil). The sole: it was (0.058,
    # 0.055, 0.054) at 0.84 with scurf at 0.80: a brown-grey chalky plate inside a tan rim, a shoe's insole. On the
    # live foot i04 the sole is the wall's own dark slate, satin, with the cream rim round it; the plan's deer is
    # a live summer stag. The bulb: a little paler and more matte than the sole (i04: grained, grey))
    rough=dict(flat=-0.12, cavity=0.14, top=-0.05, polished=0.46, dust=0.22, bare=0.70),   # the wall 0.48: satin [L i01]
    wear=dict(dust=0.30, rub_dir=(0.0, 0.25, 1.0)),
    mottle=dict(cell=0.055, amp=0.20),                              # cell: a share of HL
    young=dict(albedo=(0.092, 0.081, 0.072), rough=0.80),           # the periople's film [M-ph i01 0.116 with hair tips in the box]
    layers=[
        dict(field='matte', rough=0.66, amount=0.75, outside='tip'),                           # roughness only
        dict(field='scuff', albedo=(0.105, 0.097, 0.090), rough=0.76, amount=0.70, tint=0.7, wear=0.6),
        dict(field='scratch', albedo=(0.200, 0.190, 0.180), rough=0.78, amount=0.50, wear=1.0),   # [L i01 3.5x]
        # (gain: the lacy mottle of hoof_fields' `grain`; without it the bulb and the rim were flat fills)
        # (cavity was 0.35: with the bulb's grain in the high it drew every groove between two granules as a dark
        # line: a net of polygons in the colour, look/h46_flags_n.png. The grain is the normal map's; 0.12 a hint)
        dict(field='bulb', albedo=(0.050, 0.046, 0.043), rough=0.82, cavity=0.12, tint=0.3, young=1.0, gain=('grain', 0.30)),
        # (11-12, FIX ROUND 2, check 2's failure 4: "from below, the sole reads as a shoe's insole: one tan rim of
        # even width all the way round, and one even net of pale cracks". The rim was (0.150, 0.110, 0.078), a tan
        # measured from below on the dead winter foot i02 through its frost, painted as one band 2.8 mm wide. On the
        # live-horned foot i04 at 2.2x (work/bestiary/deer/hooves/fix2/tmp/crops/i04_sole_x2.png) the wall's section
        # from below is the sole's own dark slate; what is pale is a THIN CREAM LINE where the wall meets the sole,
        # 0.5-0.8 mm wide, strongest round the toe, where it hooks, and broken along the flanks. On i02 at 2x the
        # band is grey-brown horn, 0.022-0.026 HL wide on the abaxial side, 0.030 at the toe, 0.008 on the cleft's
        # side. So: the rim is DARK worn horn a little browner than the sole (the wall's own section), the cream is
        # the white line's, by its own field (strong at the toe, in runs elsewhere: hoof_surface.hoof_fields), and
        # the border's width is uneven in the FORM (rim_axial 0.7 -> 0.40, rim_wander))
        dict(field='rim', albedo=(0.058, 0.050, 0.044), rough=0.60, tint=0.6, gain=('grain', 0.32)),   # [L i04; M-ph i02]
        dict(field='sole', albedo=(0.0384, 0.0353, 0.0338), rough=0.62, cavity=0.3, tint=0.5, gain=('grain', 0.22)),   # [L i04; M-ph i02 dark patches 0.02-0.09; e01's hue]
        # (after the sole: the sole's layer reaches a little over the line, and painted first the line was half
        # painted out)
        # [L i04: the cream line reads sRGB about (190, 180, 160) in low sun, three to four times the slate beside
        # it; the worn edge's own row below is (0.200, 0.165, 0.125)]
        dict(field='white_line', albedo=(0.210, 0.180, 0.138), rough=0.74, cavity=0.3, tint=0.1, amount=0.85,
             gain=('grain', 0.30)),
        dict(field='bulb_lace', rough=0.66, amount=0.80),            # roughness only: no zone at one roughness
        dict(field='sole_lace', rough=0.48, amount=0.75),
        dict(field='scurf', albedo=(0.260, 0.245, 0.230), rough=0.93, amount=0.55, tint=0.0),  # [M-ph i02]
        dict(field='shed', albedo=(0.0237, 0.0218, 0.0208), rough=0.50, amount=0.85),
        # (dirt was (0.045, 0.036, 0.028), paler than the sole it lies in: with the cracks all open it drew the
        # "even net of pale cracks". Packed dirt in a crack of dark horn is darker than the horn)
        dict(field='dirt', albedo=(0.022, 0.019, 0.016), rough=0.92, amount=0.60, tint=0.0),
        dict(field='edge', albedo=(0.200, 0.165, 0.125), rough=0.72, amount=0.70, tint=0.3, wear=1.0),   # [L i04]
        dict(field='chip', albedo=(0.250, 0.215, 0.170), rough=0.80, amount=0.80, tint=0.2, wear=1.0),
    ],
    # grown_root()'s options for the periople AS THE REMIX SEAM'S DRESSING (graft_socket.grown_root on a host's
    # ring; HF6), as SHARES OF HL (the constant GROWN_ROOT is the beetle tibia's): not read by the material stage
    grown_root=dict(film=(0.012, 0.034), film_cell=0.025, young=0.045, mature=0.11, wander=0.02, wander_cell=0.06,
                    young_col=(0.105, 0.092, 0.082), young_rough=0.30, striae_l=(0.013, 0.021),
                    striae_h=(0.00003, 0.000025)),
))


def horn_recipe(name='cervid', HL=None):
    """the preset's recipe row for families/horn_skin.material, its lengths in metres for a hoof of length HL (the
    type stag's when None). The stage's own keys only (grown_root is the seam dressing's)"""
    r = dict(HORN_ROWS[name])
    HL = hoof_length(PRESETS[name]['type_mass']['stag']) if HL is None else float(HL)
    r['mottle'] = dict(r['mottle'], cell=r['mottle']['cell'] * HL)
    r.pop('grown_root', None)
    return r


# ---------------------------------------------------------------------------------------------- the relief rows
# THE HIGH'S RELIEF (families/hoof_surface.py), shares of HL, read off the red deer photos i01 (dorsal wall), i04
# (wall, bearing edge and sole from the side) and i02 (sole and bulbs): [L] looked at beside the photo, sizes by eye
# against the hoof's own length; HF4 sets them beside closer photos.
RELIEF = dict(cervid=dict(
    # growth rings: parallel to the coronet, a few faint bands and one or two stress rings [L i04, i01]
    # (the first high, look/h20_board_a.png, read as a procedure in four places: the sole a net of clean polygon
    # cracks, the bulbs ruled like layer lines, the edge's 16 chips a perforation, the grain as ruled lines. The
    # rows below are the second: warped frayed plates, faint broken striations, 7 unequal chips, grain broken up)
    # (11-11, fix round 1: ring was dict(height=0.0020, base=0.55, spacing=(0.020, 0.055), stress=2, wobble=0.004,
    # follow=0.30), every ring whole round the claw, 0.4-1.2 mm wide: at the named 1 m view in daylight they read as
    # evenly ruled horizontal stripes, a brushed or printed surface (check1 verdict 4; the photos at that scale show
    # none). Now fewer (4-11 mm apart), wide and low (width 0.3 of the largest spacing: 3.4 mm; a regular ring
    # 0.02-0.06 mm high, the one stress ring 0.10 mm), each a run of about `keep` of the way round, about `run` HL
    # long (hoof_surface._ring_field))
    ring=dict(height=0.0010, base=0.55, spacing=(0.040, 0.110), stress=1, wobble=0.004, follow=0.30, width=0.30,
              keep=0.40, run=0.25),
    streak=dict(height=0.00016, cell=0.012, fine=0.00006, fine_cell=0.004),    # along the tubules [L i01 sheen]
    # (length was (0.03, 0.16): the toe close-up, look/h60_c_toe_close.png, read as pick-up sticks; i01's scores are
    # mostly 3-8 mm with a few long ones)
    # (11-11 05:0x, THE ENGINE AT PHOTO 1'S CAMERA, look/h80_c_matched_dorsal.png: 230 scores 0.12-0.27 mm wide and
    # 0.03-0.08 mm deep on a satin wall read as CREASED FOIL: each a groove with a lit wall. On i01 at 3.5x a score
    # is a pale HAIRLINE: its colour is scuffed white keratin, its relief next to nothing, there are hundreds, most
    # of them 1-4 mm, in every direction. So: three times as many, short (the length drawn skewed: u ** 2), one to
    # two texels wide, 6-20 micrometres deep; the colour does the work (HORN_ROWS, the `scratch` layer))
    scratch=dict(n=700, across=0.35, length=(0.008, 0.075), width=(0.0010, 0.0017), depth=(0.00006, 0.00020)),
    film=dict(height=0.0004, edge=0.018, wander=0.02, wander_cell=0.06),       # the periople's soft film [L c03]
    # (11-11 05:0x: on the live foot i04 at 2.5x the bulb is PEBBLED like grained leather (granules about 0.5 mm),
    # with the striations faint; i02's combed fibres are a dead winter foot's. `pebble` is that grain: 0.72 mm
    # cells (5 texels: 0.5 mm would alias on the 1024 sheet), 0.06 mm high)
    wrinkle=dict(depth=0.00018, period=0.0105, wobble=0.012, lump=0.0006),     # the bulb's striations [L i02]
    pebble=dict(cell=0.0070, height=0.0006),                                   # the bulb's grain [L i04 2.5x]
    # (11-11 05:0x, THE ENGINE FROM BELOW, look/h80_c_matched_sole.png: the sole read as cracked mud under RULED
    # HATCHING: `fibre` was a noise seven times longer along the claw than across (0.5 mm lines). A live sole (i04)
    # is smooth dark horn with soft undulation and few marks; a dead winter one (i02) is crumbs and flakes, never
    # parallel lines. Now: the fibre term is an even CRUMB (cells 0.9 x 1.2 mm), plates and cracks at half their
    # height, a third of the plates shed before (0.22 -> 0.08), and the sole horn ends over the bulb in a ragged
    # LIP (border: how far the line wanders at 5 mm and at 1.2 mm; lip: its swell, 0.4 mm))
    # (11-12, FIX ROUND 2, check 2's failure 4, "one even net of pale cracks": every plate stood at its own height
    # and every border carried a curled edge, so the whole sole was one net of lit steps. On i04 the live sole is
    # smooth horn in soft bands with a few lifted flakes toward the bulb. `open` (how much of the sole's cracks stand
    # open: a slow noise's window) (0.15, 0.75) -> (0.45, 0.95): about a quarter of the borders; and the plates'
    # steps and the curled edges are now gated by the same window (hoof_surface.claw_relief): where the horn is
    # whole it is smooth)
    flake=dict(cell=0.060, warp=0.016, plate=0.0005, shed=0.08, shed_depth=0.0012, crack=0.0005, curl=0.0003,
               fibre=0.0004, lump=0.0010, open=(0.45, 0.95)),                  # the sole's plates [L i02, i04]
    bulb_border=dict(bow=0.10, wander=0.05, wander_fine=0.02, width=0.012, lip=0.0040, lip_reach=0.06),   # [L i04, i02]
    white_line=dict(depth=0.0007),
    edge=dict(bevel=0.0018, bevel_toe=0.0046, reach=0.006, chips=7, chip_depth=(0.002, 0.008),
              chip_w=(0.006, 0.030), chip_reach=0.012),                        # the worn, chipped bearing edge [L i04]
    dew=dict(ring_h=0.0005, ring_spacing=(0.012, 0.030), scuff=0.0006, film=0.0004, lump=0.0008),
))


def preset(name='cervid'):
    p = PRESETS[name]
    if not p.get('ready'):
        raise ValueError(f'hoof preset {name!r} is not measured yet (HF2): only cervid is built')
    return p


def outline(name='cervid', n=None, fair=True):
    """the claw's plan outline as arrays (s, abaxial, axial), shares of HL from the foot's midline. fair=True (what
    the generator builds on): the measured knots FAIRED, each edge a smoothing spline held inside the tracing's own
    error (about 0.006 HL rms: my hand points lie p50 0.015 HL from the segmentation), the end knots kept; raw
    per-station readings wobble, and a wobbling outline reads as a scalloped bearing edge (HIGH_TO_LOW, the
    hard-surface rebuild's item 9). fair=False: the knots as measured. `outline_fair_dev` reports the difference"""
    p = preset(name)
    s, a, x = (np.asarray(p[k], np.float64) for k in ('outline_s', 'outline_abaxial', 'outline_axial'))
    if fair:
        from scipy.interpolate import UnivariateSpline
        m = (s >= 0.10 - 1e-9) & (s <= 0.90 + 1e-9)          # the flanks; the toe's and the heel's turns stay as read
        w = np.ones(int(m.sum()))
        w[[0, -1]] = 30.0                                     # held where the flanks meet the turns
        tol = p.get('outline_fair', 0.006)
        a, x = a.copy(), x.copy()
        a[m] = UnivariateSpline(s[m], a[m], w=w, k=4, s=int(m.sum()) * tol ** 2)(s[m])
        x[m] = UnivariateSpline(s[m], x[m], w=w, k=4, s=int(m.sum()) * (0.5 * tol) ** 2)(s[m])
    if n is None:
        return s, a, x
    sq = np.linspace(0.0, 1.0, n)
    return sq, np.interp(sq, s, a), np.interp(sq, s, x)


def outline_fair_dev(name='cervid'):
    """how far the faired outline lies from the measured knots: (max, rms) per edge, shares of HL"""
    s, a0, x0 = outline(name, fair=False)
    _, a1, x1 = outline(name, fair=True)
    return dict(abaxial=(float(np.abs(a1 - a0).max()), float(np.sqrt(np.mean((a1 - a0) ** 2)))),
                axial=(float(np.abs(x1 - x0).max()), float(np.sqrt(np.mean((x1 - x0) ** 2)))))
