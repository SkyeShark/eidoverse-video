"""W2j (the lead, 10-27): THE CANID HEAD AS ONE SUBDIVISION SURFACE, surface first, the way a creature modeller box-models
a head before sculpting it. W2c-W2i composed the head in a signed-distance field from analytic pieces (masses, cones,
fills, lofts, a skull hull plus tissue offsets): every piece printed as a lump and every switch between pieces as a ridge
(the lip lump, the ear-base knob, the cheek lump from the arch tube; the nose an extruded outline with funnel holes). Here
the head is ONE closed quad CAGE whose edge loops sit on the face's real features, Catmull-Clark with semi-sharp creases
(forge/subdiv_sharp.py: DeRose, Kass & Truong 1998) where the face has them, smooth everywhere else by construction; its
limit mesh becomes the head's signed-distance GRID (the exact distance to its triangles, the winding number's sign, on
Warp's device: the beetle's B3g route, heads/insect_cage.py), so canid.build_head, the bind's jaw and the rest of the
clay pipeline run unchanged, and the head joins the neck the way the old grid did (the head group's smooth union).

THE FRAME: canid's palate frame in millimetres: d back from the nose tip, q dorsal, x lateral (+ the creature's left).
Vertices are (d, q, x). The cage is built on the x >= 0 half and mirrored; the midline vertices are shared.

THE TOPOLOGY (a box, insect_cage's index scheme): a TOP patch T[a, b] over the dorsum (a across from the midline to the
dorsolateral line E1, b along the head at the STATIONS d_b), RINGS R[k, i] round it (k down from E1 to the ventrolateral
line E2; each half ring a FRONT segment i 0 .. nA across the face, a SIDE segment i nA .. nA + nB along the head at the
stations, a BACK segment across the back), a BOTTOM patch B[a, b] under the jaw. Every column (constant b) is a
cross-section loop and every ring a contour round the head; the rings' front segments form the FACE CAP (its rows run
across the nose, the lips and the chin, its columns down the face), the back segments the back cap buried in the neck.
The patches' corners are the only extraordinary vertices of the box (valence 3). Two features are TUBES inserted inside a
square ring of the grid (Topo.insert_tube: rings of the square ring's vertex count between it and the quads it encloses):
  NOSTRIL in the face cap (nose_i x nose_k): the square ring (the RIM, on the leather round the nostril), then the alar
          FOLD's crest, the opening's EDGE (the comma, creased), the dark CORE turned in, the vestibule DEEP and the
          CANAL turning up and back under the fold; the enclosed quads close the canal's end
  EYE     in the side segment (eye_b x eye_k): the square ring (the RIM, on the face round the eye), the ORBIT's two
          transition rings (W2k: ORB_OUT on the face, ORB_IN taking the climb's middle), the lids' outer surface
          (LID_OUT starting the climb, LID_MID on the lid's sphere), the lid MARGIN (creased) on the traced fissure, the
          margin's ROLL onto the globe, the conjunctival SAC; the enclosed quads close it inside the globe (the globe
          itself an analytic sphere, canid.build_head, seated in MWNH 358's orbit rim since W2k: canid.EYE_Q)
And one OPEN tube (W2k, Topo.insert_open_tube): the LEATHER's own loops inside the U of face-cap cells round it (row
leather_k[0], column leather_i, row leather_k[1]; the U's ends on the midline): the U itself the SUPPORT loop on the
muzzle, then the BORDER (W2l: the leather's outline on the clay's own frame, canid_nose.border_curve, spaced by its arc,
creased along its bottom) and the FRONT loop (its inset); the leather's interior grid with the nostril's tube meets the
front loop (LEATHER)
EVERY TUBE RING SHARES ITS SPOKES: each ring's vertex j sits at the same angle in the feature's chart (scaled by the
feature's half axes), at a radius between the traced curves of that ring and the next, so nested rings cannot cross and
the surface is a height field over the chart (W2j's first pass, c1-c6, mapped each ring by its own angle about its own
centre onto a block of the stations: the rings crossed, the lids crumpled). The eye's chart is the plane ACROSS THE
EYE'S AXIS (c9b; c7-c8 used the fissure's own best-fit plane, 34 deg off the axis, in which the forward-lying lower lid
bulged up into the opening and the rings folded: the Y pleat): the eye looks 24 deg up and 18 deg out, mostly FORWARD,
so the planes of constant d cut its globe in concentric circles; a block laid on the stations cannot hold an eye.
THE FEATURE LOOPS (each placed on a measured curve, its source in its table):
  LEATHER the rhinarium's border (the open tube's BORDER ring), W2l: the leather's front outline laid on the clay's own
          frame (canid_nose.border_curve: PROFILE's top at d 8.9 and bottom at 8.0, TOP's width, the photos' outline
          shape), its top and side spaced by their own arc length, its bottom evenly across; creased along its bottom,
          its top rolling onto the bridge and its sides into the muzzle without an edge. (W2f-W2k carried w12's traced
          outline through w12's solved camera, which put the leather's top 28 mm back on the bridge)
  NOSTRIL W2l: a comma in a level front chart on the clay's frame (canid_nose.nostril_chart, level_frame): the round
          head running out into the lateral slit under the alar fold, low on the front (W2i-W2k: w12's tracings in
          w12's camera, two round rimmed holes high on the front)
  EYE     the traced fissure (canid_hull.traced_fissure: EYE_FISSURES through w12's and w08's solved cameras, its corners
          drawn out to the photos' canthi, canid_hull.fissure_polygon)
  LIP     ring lip_k: the upper lip's margin across the face and along canid_hull.LIP_LINE (the profile photos' mouth
          line) to the commissure, creased (fading at the commissure); the groove and the lower lip under it, tucked in
  PHILTRUM the midline column from between the nostrils into the lip, recessed
  the STOP and the BROW: a station at the stop (d 100); the top patch's edge E1 runs over the brow
  EAR     W2y: a PORT, a tube in the side segment (ear_b x ear_k, EAR_PORT, place_ear): the square ring (the RIM, on the
          skin 7 mm outside the root), a middle ring, the ROOT on the pinna's foot (the outer face's foot from the medial
          foot round the back to the lateral foot, then the chord across the concha's mouth); the enclosed quads the
          concha's floor. The pinna stays its own shell member (canid.ear_shell); the low cuts the floor and the ear's low
          joins the root
THE OTHER VERTICES lie on the REFERENCE: W2i's skin over the skull blended into its flowed head (the canid muzzle section,
the skull's proportions and tissue depths W2i got right), smoothed (more over the cheek, the orbit and, W2k, the cranium:
REF), the muzzle's flank filled behind the canines (W2k fresh eyes: REF flank, W2i's waist there), and the nose's CAP
unioned (W2l: canid_nose.cap_field, the leather lofted on the clay's own frame and morphing into the muzzle behind it, in
place of W2k's NOSE_BLOCK and widened bridge: a flat-topped, flat-fronted block with a right-angle top-front edge),
placed by stations and Coons patches and relaxed along it.
THE FIT (fit_cage): least squares, not interpolation: the cage's control points minimise the squared distance of the
limit surface (at the cage's vertices) to the targets, weighted (features FIT w_feat; the reference w_free, down to
w_zone over the zone where W2i's construction printed a lump: the cheek's arch-tube dome; W2k dropped the brow's) plus
FIT lam times the cage's squared umbrella Laplacian (its fairness); each pass re-projects the free targets onto the
reference (they slide along it) and pushes any limit point within FIT skin_min mm of the skull (canid_skull) out to it.
Then the cage is subdivided to the limit mesh and becomes the grid (head_field).
"""
import os
import time

import numpy as np

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

VERSION = 'w2y-1'                   # W2y-1 (11-08, the wolf's ear ports): the ears' ROOT PORTS (LAYOUT ear_b / ear_k,
#                                     EAR_PORT, place_ear: a 34-vertex root on the pinna's foot, the rim 7 mm outside it, the
#                                     concha's floor inside; E_LINES' E1 brought in over the ears; FIT zone 'ear') and the
#                                     ports' floors and the back cap in the cache (the low cuts them). W2r-2:
#                                     W2r-2 (10-30, the restarted W2r head builder): the eye rig's ring weights fall off
#                                     with each ring's share of the way to the rim (EYE_RIG: no fold at any photo's gaze);
#                                     the horizontal follow eased in from the canthi (canid_hull GAZE slide_taper).
#                                     W2r-1 (10-30, the W2r head builders): the outer corner's slot fixed in the
#                                     construction (place_eye: the lid's and the orbit's rings onto the face only where the
#                                     margin lies on it, EYE on_face; each ring kept at its chart radius, EYE keep_chart;
#                                     canid_hull lid_follow's ends eased onto the canthi, GAZE end_blend); the brow's
#                                     medial end smoothed (REF brow shift az, REF canthi medial carve, FIT zone brow_med).
#                                     W2q-3:
#                                     W2q-3 (10-29 night, the second restarted W2q head builder): the brow as the face moved
#                                     forward along the lids' axis (REF brow shift) in place of the W2q-2 hood (the globe
#                                     + 6-10 mm unioned: a ball over the eye in profile), the medial groove's dorsal flank
#                                     carved (REF canthi medial carve), the cut under the eye blended in (REF under_eye
#                                     blend: the flank's ripple under the eye). W2q-2:
#                                     W2q-2 (10-29, the restarted W2q head builder): the lids' follow eased over 10 mm from the
#                                     medial canthus (canid_hull GAZE taper_medial: the inner canthus seen from every front
#                                     camera at its photo's gaze), the rim half a pad outside the posed lids (EYE env_pad:
#                                     the fold over the eye gone), the brow's lateral part (REF brow ext), the medial fill
#                                     off (REF canthi medial fill). W2q-1:
#                                     W2q-1 (10-29, the W2q head builder): the REST LIDS at a neutral gaze (EYE face follow:
#                                     canid_hull.lid_follow, the photos' lids turned back by their iris gazes), the socket
#                                     enclosing the lids' posed range (eye_chart fis_env), the eye rig (EYE_RIG) in the
#                                     cache, pose_eye. W2p-2:
#                                     W2p-2 (10-29, the successor head builder): the corners as built (REF canthi lateral on
#                                     the face, 3 / 4 / 5; medial 5 / 5 / 12, 7 upward: canthus_carve's optional 4th sigma;
#                                     EYE face roll_lateral 1, roll_medial 3; notch
#                                     0.4), the leather's front loop's top run smoothed (LEATHER smooth_top) under the border
#                                     back at the photos' bare edge (canid_nose BORDER); the rest-gaze options framed on the
#                                     unturned margin and the rings' rise (EYE face gaze / gaze_lower, EYE rise: off).
#                                     W2p-1 (10-29, the head builder): each corner's roll its own depth (EYE face roll_lateral,
#                                     roll_medial), the margin turned to rest gaze (EYE face gaze: canid_hull.fissure_chart),
#                                     on W2p's skull (canid_skull: MWNH 358's arch over the orbit). W2o-1:
#                                     W2o (10-29, the head builder): the eye's corners on the face at the profile-rule canthi
#                                     (EYE face: canid_hull.traced_fissure's face rule, the cage only), a spoke through each
#                                     tip, the lid and orbit rings on the face where the margin is, the corners' roll back
#                                     along the eye's axis; the face brought in round the canthi (REF canthi); the
#                                     nostril's head open to the high cameras (canid_nose NOSTRIL_L fold_from, NOSTRIL over,
#                                     tuck, core)
#                                     W2n n3 (10-29, the restarted head builder): the eye's corners run on along their rays (EYE
#                                     pin), the upper lid's crease and the medial notch on (EYE crease, notch)
#                                     W2n (10-29, the head builder): the photos registered like for like (canid_hull.clay_points:
#                                     the middle of the clay's lid opening, eye_landmark's fixed point, not the cornea's apex),
#                                     so the cameras, the traced fissure and the canthi are re-carried; the eye chart's tips the
#                                     traced corners (canid_hull.fissure_chart, shared with the fixed point); the globe 4 mm
#                                     forward (canid.EYE_SEAT)
#                                     W2m (10-29, the head builder): the globe seated forward (canid.EYE_SEAT) with the lids
#                                     on it (EYE lid 0.6); the leather's border wrapped back (canid_nose d_b 16.5, BORDER) with
#                                     the front loop off the front-to-top turn (LEATHER); the nostril's tube turned back and up
#                                     under a fold that roofs the comma's tail (NOSTRIL turns, tuck, over, h)
#                                     W2l h3 (10-28 night, the restarted head builder): the eye's axis turned to the lids'
#                                     own facing (canid_hull STROKES_SKULL eye axis 19 / 40) with the fissure kept star-
#                                     shaped in its chart (EYE star); the nostril's comma (canid_nose NOSTRIL_L)
#                                     W2l h1-h2 (10-28, the W2l head builder): the nose re-laid on the clay's own frame
#                                     (canid_nose: the cap in the reference, the border from PROFILE / TOP / the photos'
#                                     outline, the comma nostril in a level chart; NOSTRIL's tuck and turns), the eye's pad
#                                     8.5 / 7 with its orbit rings lower, the philtrum 1.6 mm, the ear mound sunk broad
#                                     W2k f1 (10-28, the W2k fresh eyes): the muzzle's flank filled behind the canines (REF
#                                     flank: the waist from above, the snout's bulb in the front cameras)
#                                     W2k k1 (10-28): the nose block (NOSE_BLOCK: the leather's front, the bridge widened
#                                     behind it), the leather's own loops (LEATHER: an open tube, the border spaced by its
#                                     arc), the eye seated in the orbit (canid.EYE_Q) with the orbit's two transition rings
#                                     (EYE orb), the cranium smoothed (REF cranium) and the brow's fit zone dropped
#                                     c9a (10-28, the W2j look agent): the leather's bottom row spread evenly in x (the X
#                                     pinch under the leather), the nostril's vestibule and canal run along w12's line of
#                                     sight instead of turned up (their lit floor: 0.1 % dark in the nose read); c9b: the
#                                     eye's chart seen along the eye's axis (the Y pleat in the lower lid)
#                                     c7 (10-27 night): shared-spoke tubes for the nostril and the eye, the eye in the
#                                     fissure's plane, the least-squares fair fit with zones and the skull's clearance;
#                                     c8: station 0 at d 38, the leather's top two rows above the nostrils, the lids'
#                                     outer ring on the lid's sphere; c8c: the philtrum recessed back (+d), the narrow
#                                     canal, the canthal recess 1.6 mm, the rim held at 8 mm, a mild orbit zone
REF_VERSION = 'w2r-r1'              # W2r r1: the brow shift's medial ramp 70 deg wide, the medial carve's ramps lengthened
#                                     (the S over the inner corner). W2q r3:
#                                     W2q r3: the brow shift (eye_relief_edits: each column of the face over the upper arc
#                                     moved along the lids' axis) for the hood; groove_carve (the medial groove's dorsal
#                                     flank); the cut under the eye blended in by its weight (REF under_eye blend). W2q r2:
#                                     W2q r2: r1's medial tube fill removed (it hid the inner canthus from the front
#                                     cameras); groove_fill on the finished reference, off (REF canthi medial fill).
#                                     W2q r1: the brow forward and the skin under the eye in (REF brow, under_eye:
#                                     eye_relief_edits). W2l-r1:
#                                     the reference's own version (W2l r1: canid_nose's cap for the nose block and the
#                                     widened bridge; W2k r2, the fresh eyes: the flank filled; W2k r1: the nose block for
#                                     the dome; W2j c1-c9 its first)

# ============================================================================================ the layout
LAYOUT = dict(
    nA=12, K=26,
    # the STATIONS (d mm, b = 0 .. nB): the first the face cap's boundary section (behind the leather's top: W2l puts it
    # at d 8.9, PROFILE's, where W2j-W2k's w12 camera put it 16-28 mm back on the bridge); 7 mm over the muzzle to the
    # stop (d 100), 4 mm over the eye's block (d 110-158), coarser over the cranium, the last in front of the back cap
    # (buried in the neck)
    # (c8: the first at d 38, not 30: w12's leather top lands at d 27 on the bridge, and with station 0 three mm behind it
    # the cap's rows 0-3 crowded the bridge while ONE row spanned the leather's whole top to the nostrils: long thin quads
    # whose fairness printed pleats and a ridge down the leather)
    stations=(38.0, 45.0, 52.0, 58.0, 65.0, 72.0, 79.0, 86.0, 93.0, 100.0,
              105.0, 110.0, 114.0, 118.0, 122.0, 126.0, 130.0, 134.0, 138.0, 142.0, 146.0, 150.0, 154.0, 158.0,
              163.0, 169.0, 176.0, 184.0, 193.0, 202.0, 211.0, 220.0, 229.0, 238.0, 246.0, 254.0),
    eye_b=(12, 22), eye_k=(2, 8),          # the eye's square ring: stations 12 .. 22 (d 114 .. 154), rings 2 .. 8: 32 spokes
    nose_i=(2, 8), nose_k=(5, 11),         # the nostril's square ring in the face cap: columns 2 .. 8, rows 5 .. 11: 24
    # the leather's U (its support loop; W2k): row 2 (top), column 9 (side), row 13 (bottom). (W2k k1a: column 10, two
    # cap columns between the nostril's rim and the leather's front loop: the traced border runs along the rim at the
    # nostril's height, and the two squeezed into ~1 mm printed ticks at the leather's sides)
    leather_i=9, leather_k=(2, 13),
    # W2y: THE EAR'S PORT: the square ring on stations 30 .. 35 (d 211 .. 254; its back side the last station's column,
    # carried behind the ear) and rings 1 .. 13: 34 vertices, the grid's own spacing round the ear's 156 mm foot.
    # (WOLF_PLAN 4.4's 24-vertex ring, a 4 x 8 block, pleated the limit along the rim, 0.64 mm2 of folded triangles round
    # the ears and hairlines in the renders (check d10); 5 x 12 none, the head's fold total the same as W2w's: check d9)
    ear_b=(30, 35), ear_k=(1, 13),
    lip_k=16,                              # the upper lip's margin (the groove 17, the lower lip 18)
    # W2u: the nostril's tube with the ALAR WING's own rings, its outer foot and its crest, outside the inner lip ('fold':
    # carried in over the opening): a fat lobe, where the one 'fold' ring between the rim and the edge made a thin ridge
    # (NOSTRIL wing, place_nostril)
    tubes=dict(nostril=('wing_o', 'wing', 'fold', 'edge', 'core', 'deep', 'canal'),
               # (W2k: the orbit's two transition rings outside the lids, the lead's "two or three transition rings
               # from the lid sphere out to the face")
               eye=('orb_out', 'orb_in', 'lid_out', 'lid_mid', 'margin', 'roll', 'sac'),
               # W2k: the leather's open tube inside its U (the U itself is the SUPPORT loop on the muzzle round it);
               # W2p: a MIDDLE loop between the border and the front loop (place_leather; LEATHER's note)
               leather=('border', 'mid', 'front'),
               # W2y: the ear's port: the square ring (the RIM, EAR_PORT margin outside the root), a middle ring, the ROOT
               # (the ear's foot on the skin: the pinna's outer face along its base and the chord across the concha's mouth)
               ear=('mid', 'root')))
# THE LEATHER'S LOOPS (W2k, the lead: "the nose as its own box-modelled block within the cage ... rows that follow the
# traced wrap back along its sides (spaced by the outline's arc, with the wrap getting its own rows)"): the U of face-cap
# vertices round the leather is the SUPPORT loop, `support` mm outside the BORDER on the muzzle (along the surface, away
# from the leather); the BORDER is the leather's outline on the clay's own frame (W2l: canid_nose.border_curve; W2k
# carried w12's traced outline onto the nose block), spaced by its own arc length on the top and the side (the knees at
# the U's corners), its bottom evenly across (c9a), and held at least `b_min` mm off the nostril's rim; the FRONT loop is
# the border's INSET on the
# surface (`inset`: on the top, the side and the bottom, mm), at most to `clear` mm outside the nostril's rim. The
# leather's interior grid (the nostril's tube in it) meets the front loop; the one cap strip between the nostril's rim and
# the front loop carries the turn from the front-facing rim to the wrap. (W2j put the border on the cap's own row 2,
# column 10 and row 13: the side's 12 rows spread by height skipped the wrap (one row jumped 18 mm back to front): fold
# lines down each side; spread by length the rows from the nostril's rim sheared into a slit, c7e. W2k k1a drew the front
# loop in w12's image and added a roll loop: they ran within ~1 mm of the rim at the nostril's side: ticks)
LEATHER = dict(support=2.5, inset=dict(top=16.0, side=8.0, bot=2.0), clear=4.0, b_min=3.6, mid_gap=6.0, smooth_top=20,
               smooth_corner=True)
# (W2p, the lead's call 3: smooth_top, leather_loops' relaxation of the front loop's top run (iterations; smooth_corner:
# its top-lateral corner too): with the border back at d 25.5 (canid_nose BORDER) the raw inward offsets bunched at the
# U's top-lateral corner or crossed the top midline and the fit folded the cage there (probes n1, f1: hairline cracks on
# the leather). The top inset 16 (10) keeps the front loop on the front-to-top turn (d 9.4; W2o's at 6.7), with the MIDDLE
# loop (LAYOUT tubes leather 'mid') halving the 16 mm strip to the border: with the front loop 10 mm in (d 15.5, w02
# _w2p2) the leather's interior grid ran over the turn and printed vertical pleats on its front, at 16 without the mid
# loop a V tick at the top midline (l7). Probe l8: no fold beyond the nostril tube's own (0.13 mm2 of triangles > 60 deg
# off their vertices' normals; W2o 0.11), no pleat, no V, a soft change of plane at the border from above)
# (W2m, the lead's call 2: "a convex pad with no border step". The W2l fresh eyes' "1 mm border step" was a 0.3-1 mm NOTCH
# at the FRONT loop, not at the border (check_w2m_head/out/nose_sections_lf1.png): the held loop sat on the tight turn from
# the leather's steep front into its flat top, d 1-3, and beside the raised fold on the sides. With the border moved back
# (canid_nose BORDER: the top at d 16.5, the side at 15) the insets 10 / 8 / 2 (W2l 7 / 4 / 2) put the front loop's top on
# the flat top (d 6.7) and clear 4.0 (1.6) holds its side rows 4 mm off the nostril's rim, past the turn: the notch and a
# V tick at the top midline gone (probes p1 -> p4 -> p6, out/cmp_p1_p4_nose.png, cmp_p4_p6_nose.png). At insets 14 / 11 the
# loop stayed on the turn (p1: the tick))

# the dorsolateral line E1 (the top patch's edge) and the ventrolateral line E2 (the bottom patch's): arc length (mm) along
# each station's section from the top midline / from the bottom midline [E: the dorsum's shoulder, the brow over the eye,
# the temporal line; the mandible's ventral border, the throat]
E_LINES = dict(d=(20.0, 60.0, 95.0, 112.0, 139.0, 165.0, 190.0, 211.0, 230.0, 254.0),
               s1=(19.0, 22.0, 25.0, 26.0, 26.0, 30.0, 34.0, 24.0, 22.0, 22.0),
               s2=(14.0, 16.0, 21.0, 24.0, 27.0, 30.0, 33.0, 33.5, 34.0, 30.0))
# (W2y: E1 brought in over the ears, 42 / 38 -> 22 mm from the top midline at d 211-254 (|x| ~38 -> ~20): the ear's
# medial foot runs along |x| 32 there, so the port's rim (EAR_PORT margin outside it) lies on the rings, not the top patch)
# W2y: THE EAR'S PORT (place_ear): the ROOT is the pinna's foot on the skin, the low's base loop the ear joins: the outer
# face's foot (the clay sheet's base section (canid.ear_shell on the REFERENCE's skin) less ht_low mm toward its back, at
# `cols` sheet columns evenly by column index: the head low's ear (work/bestiary/wolf/w2y/head_low.py) samples the same
# columns) from the medial foot over the top, round the back and along the bottom to the lateral foot (22 cells: the
# block's top 5, back 12, bottom 5), then the CHORD across the concha's mouth back to the medial foot (the block's front
# 12), bowed `bow` of its length out of the concha (a parabola: the corners at the feet opened from acute, where the
# limit pleated: check d3); the RIM `margin` mm outside the root along the surface (each root point's outward direction
# in the tangent plane, smoothed over `smooth` neighbours), the middle ring halfway; the enclosed floor (the concha's
# floor under the cup) a Coons patch of the root's four sides; the grid relaxed round the port in a window (`win`:
# stations, rings; `win_back` back cap columns) with the port's rings held, then only `hold` held in the fit (FIT w_feat;
# the rest slide on the reference). (check d1 held every ring and the floor: hairline pleats along the rim, 9.6 mm2 of
# folded triangles round the ears; d1-d8 relaxed the free rim with the grid, which drew it onto the root)
EAR_PORT = dict(cols=23, ht_low=0.8, margin=7.0, smooth=2, mid=0.5, win=((26, 35), (0, 18)), win_back=8, iters=200,
                hold=('root',), bow=0.22)
# the FACE CAP's rows on the midline (row k: arc length position along the reference's midline from the first station's
# top round the nose to its bottom, given by named anchors; the rest even between them)
CAP_ROWS = dict(leather_top=2, tip=8, leather_bot=13)
# the reference: W2i's skin smoothed (sigma mm), the cheek under and ahead of the eye smoothed more (the arch tube's front
# root printed a dome there: the W2i check), the leather's DOME unioned in
REF = dict(sigma=2.0, cheek=dict(sigma=5.0, d=(84.0, 98.0, 128.0, 142.0), q=(-24.0, -12.0, 26.0, 34.0), x=18.0),
           # the ORBIT smoothed too (its notch under the brow folded the eye's block: the eye's rings are built on the lid's
           # sphere, the block's boundary only needs the orbit's mass)
           orbit=dict(sigma=5.0, d=(108.0, 120.0, 156.0, 168.0), q=(4.0, 14.0, 52.0, 62.0), x=16.0),
           # W2k (the lead: "refit the reference over the temples and behind the brow to the photos' top and profile
           # outlines (lower or smooth the temporalis fill where it makes humps)"): the CRANIUM smoothed over the brow's
           # shoulders and the temporal muscles to the occiput, above the temporal line, across the midline (x -10: no
           # ramp), at sigma 9 mm: W2i's temporalis fill (canid_skin DEEP temporalis, its edges bulged, and the 12 mm
           # temporalis depth at (198, 42, 34)) printed two round humps either side of a midline 2-3 mm under PROFILE's
           # dorsal line at d 185-205; a blur this wide flattens bumps ~20 mm across and moves the dome (radius 40-60 mm)
           # under 1 mm (the w02 profile and cranial-width gates read it)
           cranium=dict(sigma=9.0, d=(108.0, 128.0, 236.0, 252.0), q=(28.0, 42.0, 120.0, 130.0), x=-10.0),
           # W2k fresh eyes: THE MUZZLE'S FLANK FILLED behind the canines (fill_flank): W2i's skin narrows 4-6 mm a side
           # from the canine lips (d 32-36, half width 33.3 at q -16) to d 56-60 (27.2) at every height and widens again
           # by d 80 (33.3), a waist the skull's near-parallel rostrum does not have (canid_skull: 24 at the canines, 20.5
           # flat over d 40-62) and the photos do not show (the wet r03 puts its skin line 8-12 mm outside the clay there,
           # w12 4-6 mm; w08, a narrower wolf, 5-7 inside): from above and from the front cameras the muzzle printed as a
           # bulb behind the nose, the pig's snout. The field lowered by amp(q) (mm, by height: the waist's 0.8, a 1-1.5 mm
           # canine eminence left) x an asymmetric gaussian in d (centre dc, sigma ahead / behind: C-infinity, under the
           # ripple gate's 20 mm quadratic) x the off-midline ramp (x0, xw: the dorsum's midline kept)
           flank=dict(dc=60.0, s=(12.0, 9.0), x0=6.0, xw=8.0,
                      amp=((-46.0, 0.0), (-38.0, 1.6), (-32.0, 3.0), (-24.0, 4.2), (-16.0, 4.9), (-10.0, 5.2), (0.0, 4.1),
                           (10.0, 4.2), (18.0, 3.5), (24.0, 1.6), (30.0, 0.0))),
           # W2o (the lead's call 1: "bring the face in by about 7 mm round the outer corner"): THE FACE ROUND EACH CANTHUS
           # (canthus_carve): the field raised by a smooth bump about each profile-rule canthus (the cage's tips, EYE
           # face) so the canthus lies `clear` mm under the reference, the bump's sigma (out along the fissure's line, in
           # toward the eye, across) mm, the skin held t_min mm off the skull
           canthi=dict(clear=2.0, t_min=2.5, k=1.0, medial=dict(sigma=(5.0, 5.0, 12.0, 7.0), clear=0.0,
                                                                fill=None,
                                                                carve=dict(c=1.7, s=(-1.0, 1.5, 3.5, 9.0),
                                                                           u=(0.8, 7.0, 7.5, 17.0), h=(-25.0, -15.0))),
                       lateral=dict(sigma=(2.2, 4.0, 5.0, 2.5), clear=0.0)),
           # (W2s, the lead's call 3, "no ridge over a pocket"): the lateral bump shorter out along the line (2.2, W2p-W2r 3)
           # and with a 4th sigma (upward, as the medial's since W2p) of 2.5 (5): W2r's pocket IS the reference's: the
           # carve's dorsal spread left a floor of -0.2..+1 at 1-3 mm dorsal of the tip's line with the brow's end rising
           # to 4 at 10 mm (W2q's brow): W2p's cage only hid it, standing proud on a 2 mm shelf (check_w2s lat_end.py). The
           # upper lid's end now steps down to the groove with no trough behind it (the dip behind the ridge 1.8 mm ->
           # 0.5 at the tip, none past it). The notch 4.8 / 4.5 / 3.3 / 1.6 -> 3.2 / 2.8 / 1.2 / 0.3 mm at 0.5 / 1 / 2 / 3 mm
           # (probes b1, e1; W2p 2.0 / 1.3 / 0.3 / 0.0), the fronts' IoU unchanged. A wider bump (6 / 5 / 7, b5) dug it
           # wider and lower
           # (W2r, the lead's call 2: the medial carve's ramps LENGTHENED, its u fade 7.5 -> 17 mm (W2q-3 9.5 -> 13: 3.5
           # mm, a step of 1.7 mm across it) and its s ramp -1 -> 1.5 (-0.3 -> 0.8): the two met on the 1.6 R circle about
           # the lids' axis at az -62 (s 0.95, u 12 mm) and printed the S over the inner corner that no gate read
           # (check_w2r/brow_ref.py: the reference round the axis 0.34 mm with the carve, 0.01 without; carve_ring.py, the
           # carve alone along the 1.6 R circle: 0.33 -> 0.16 mm). The groove past the medial tip 1.76 / 1.49 / 0.88 /
           # 0.27 mm at 0.5 / 1 / 2 / 3 mm (W2q 1.81 / 1.61 / 1.18 / 0.80; the notch's ~1.5; check_w2r probe k4,
           # notch.py). Carves starting further behind the tip (s -1.5 .. -3) dug the circle deeper at az -70 .. -94
           # (probes bc5-bc8: 0.29-0.33); an s ramp widening up the flank (k1, k2) left the groove's dorsal lip high:
           # the groove 2.9-3.1 mm deep at 0.5 mm, the inner canthus hidden from two cameras)
           # (W2q-3, the lead's call 4, "if still deep, a carve shaped for it": the medial `carve` (groove_carve) moves
           # the groove's DORSAL flank back along the lids' axis, up to c mm on a long ramp across (u 0.8 -> 9 mm dorsal of
           # the line, none by 13: the flank lowered more the higher it stands, so no second trough), past the tip (s
           # -0.3 -> 0.8 .. 3.5 -> 7.5 mm). After the shift brow the groove read 2.9 / 2.9 / 2.8 / 2.2 / 1.5 mm at
           # 0.5 / 1 / 2 / 3 / 4 mm (probe s3; the lower lip within 8 mm is the dorsal one, the brow's medial end); carved
           # 1.8 / 1.6 / 1.2 / 0.8 / 0.5 (probe s7), the brow's ripple 0.22 (the gate 0.3; the carve lies in front of the
           # brow's region), the inner canthus seen from all 10 front cameras at their gazes (the rays leave it dorsally,
           # over the lowered flank). A uniform band (1.9 mm over u 3-7.5, probe s5) dug a second trough above the floor)
           # (W2q, the lead's call 4: the medial `fill` (groove_fill: dict(target, s, band, smooth, slab), the groove's
           # floor raised to `target` under its lips on the finished reference) is OFF: the groove past the medial tip
           # and the inner canthus's sight lines trade off. After the brow (REF brow) the groove read 2.6 / 2.7 / 2.7 /
           # 2.1 / 1.4 mm at 0.5 / 1 / 2 / 3 / 4 mm down the eye's axis (check_w2q probe q3, the W2o fresh eyes'
           # notch.py; W2p 2.4 / 2.6 / 2.8 / 1.9 / 1.4) against the notch's ~1.5. The front cameras' rays to the inner
           # canthus leave it dorsally and up the eye's axis by 1.0-1.6 mm per mm past the tip, grazing the face there:
           # on the GRID head's read (check_w2q corner_vis_q.py --grid, which reproduces w02's gate on W2p's and _w2q2's
           # cages) the unfilled groove keeps the canthus seen from all 10 front cameras at +0.0..+0.4 mm (the gate
           # <= 0.5), while every fill hid it: a 3 mm tube about the canthi's line (w02 _w2q2: 2.2 / 2.0 / 1.3 / 0.6 / 0.6,
           # the first hit +2.6..+5.9 mm), the valley raised to 1.5 under the lips (q12: 2.4 / 2.3 / 2.1 / 1.8 / 1.3,
           # +1.0..+1.5), the valley's ventral side only to 1.0 (q13: 2.4 / 0.9 / 1.2 / 1.7 / 1.3, +0.7..+1.4); the
           # inner corner's own pocket (5.0 mm) is the dark seen from every front camera)
           # W2q (the lead's call 2: "find on both photographed skulls and the profiles which is off, the brow skin over
           # the frontal's postorbital process sitting too far back or the globe standing too proud, and fix that one;
           # bring the skin under the eye in where the lowered arch no longer holds it"): eye_relief_edits. THE BROW: the
           # soft tissue over the globe's upper part (the upper lid's fold, the orbital fat, the orbicularis and the
           # brow's skin over the supraorbital margin) as the globe offset by up to `t` mm, unioned (k): full over the
           # upper arc within az[0] deg of dorsal about the lids' axis (none past az[1]) and between the polar angles
           # pol (deg off the lids' axis: rising 0 -> 1 over pol[0..1], 1 to pol[2], 0 by pol[3]); THE SKIN UNDER THE EYE
           # cut back to `rel` (the face's height along the lids' axis less the cornea's apex, R units, by rho R off the
           # axis) over the lower arc (within az[0] of ventral, none past az[1]) and rho (0 -> 1 over rho[0..1], 1 to
           # rho[2], 0 by rho[3]), held t_min mm off the skull. The evidence (work/bestiary/wolf/check_w2q/NOTES.md
           # 13:15 and the brow call): the globe can sit at most ~3 mm deeper in MWNH 358's orbit (the bone 2.1 mm
           # clear at 3 mm back, 1.5 at 4, -0.07 at 6 along the lids' axis) while the face above the eye stood 6-9 mm
           # behind the cornea's apex (study T's canid and the cow hold it at the apex level at rho 1.1-1.25 R; the wet
           # r03 and the mange r06 show the eye set under its brow); the reference's orbit smoothing (sigma 5) had pulled
           # its surface INSIDE the globe over the eye's upper front (check_w2q/out/sections_q0.png), and the skin model
           # held only 3.8 mm over the postorbital landmark (canid_skin DEPTHS brow 5.5). Below, the zygomatic arch
           # (MWNH 358's, W2p) now lies 1.6 R under the eye's axis and the ray at rho 1.25-1.5 R meets no bone (-3.2 R),
           # but the skin there stood +0.12 / +0.25 R in front of the apex (the cow -0.05 / -0.15)
           brow=dict(shift=dict(amp=0.45, rho=(1.2, 2.8), az=(-85.0, -15.0, 55.0, 95.0),
                                gain=((-100.0, 0.55), (-70.0, 0.55), (-45.0, 0.60), (-20.0, 0.80), (0.0, 0.95),
                                      (30.0, 1.05), (60.0, 1.05), (105.0, 1.0)),
                                h=(-3.5, -2.5)),
                     t=0.0, ext=None, pol=(25.0, 55.0, 120.0, 165.0), az=(55.0, 95.0), k=4.0),
           # (W2r, the lead's call 2, "the shift's azimuthal gain made smooth (wider C2 ramps or a smooth lobe)": the
           # MEDIAL ramp 70 deg wide, from nothing at -85 to full by -15 (W2q-3 -85 / -45: 40 deg); the lateral end kept
           # (fading it further out deepened the trough by the outer corner, W2q's s8). But the S over the inner corner
           # (the W2q fresh eyes' brow_lumps: -0.48 / +0.38 mm at rho 1.6 R, az -70 / -62) was NOT the window's:
           # check_w2r/brow_ref.py read the REFERENCE itself round the lids' axis: with the shift off it still had 0.34
           # mm at az -62, with the shift and the medial carve off 0.01-0.02, the carve's short u fade and s ramp (REF
           # canthi medial carve, W2r below) meeting on the 1.6 R circle (check_w2r/carve_ring.py, the carve alone along
           # the circle: 0.33 mm). Started earlier (-115 / -15, probes b1, bc3z) the shift raised the groove's dorsal lip
           # by the inner corner 0.3-0.7 mm and hid the inner canthus from w07 R / w08 R / r07 L (+0.7 / +0.4 / +0.6 mm;
           # w02 _w2r1's corner gate); from -85 it stays 10 of 10 seen (probe k4, corner_vis_q --grid --posed). With the
           # carve's ramps lengthened and the FIT zone 'brow_med': the limit round the axis 0.26 / 0.15 / 0.26 mm at rho
           # 1.6 / 1.9 / 2.2 R, the largest now by the medial canthus itself (az -94; W2p 0.26 there), the brow's end
           # smooth (probe k4; W2q _w2q5 0.48 / 0.25 / 0.15 at az -70))
           # (W2q-3, the restarted head builder: THE BROW AS THE FACE MOVED FORWARD (`shift`, eye_relief_edits): each
           # column of the face over the upper arc moves along the lids' axis by amp R (0.45 R = 5.4 mm) out to 1.2 R
           # off the axis, nothing by 2.8 R (the C2 ramp), times the gain by azimuth (the face above the eye already
           # stands nearer the apex medially: -0.30..-0.34 R at rho 1 R against -0.45..-0.56 above and laterally), from
           # nothing at az -85 (the medial canthus at -100) and +95 (the lateral at +113) to full over -45 .. +55. The
           # W2q-2 HOOD (t 6 + ext 4 up-laterally: the globe + t unioned at k 4) passed the relief at rho 1.1-1.5 R
           # but on the reference it was a SHELF at -0.03 / -0.16 R out to 1.25-1.5 R and then a 6-9 mm WALL between
           # 1.75 and 2.0 R (its sphere's outline) down to the face: a ball over the eye in the w02 profile and three-
           # quarter (_w2q3; check_w2q/NOTES.md 23:01). Moved, the face keeps its own shape: up -0.03 / -0.15 / -0.32 /
           # -0.55 / -0.84 R at rho 1 / 1.25 / 1.5 / 1.75 / 2 R (scratchpad relief_map, probe s2), the brow rolling into
           # the forehead; on the cage (probe s3) the lids' axis up -0.08 / -0.15 / -0.32, up-lat -0.14 / -0.24 / -0.44,
           # up-med -0.06 / -0.08 / -0.14 (W2p -0.51 / -0.58 / -0.72, -0.63 / -0.72 / -0.87, -0.39 / -0.38 / -0.40),
           # the fronts at their gazes and both corners as the hood's. t / ext / pol / az / k are the hood's, off)
           # (W2q-2, the hood's lateral part, `ext` (off since W2q-3): t mm more over the polar angles pol (rising over pol[0..1], falling
           # over pol[2..3]) about the up-lateral azimuth az[0] (full within az[1] deg, none past az[2]): the hood
           # (the globe + t) reaches rho (R + t) / R off the lids' axis, 1.5 R at t 6, so the face up-laterally at 1.5 R
           # stood 0.66 R behind the cornea's apex (q9; the cow -0.16, study T's canid -0.10, the floor -0.46), the
           # brow's outer end over the orbit's dorsolateral rim sunk; the lead's W2p figures had it 0.73-1.05 R back)
           under_eye=dict(rel=((1.0, -0.05), (1.25, -0.10), (1.5, -0.12), (2.0, 0.0), (2.5, 0.22), (3.0, 0.45)),
                          rho=(0.95, 1.05, 1.8, 2.6), az=(50.0, 85.0), t_min=2.0, k=3.0, blend=True))
#      (W2q-3, the cut BLENDED in by its weight with its target through the knots C1 (eye_relief_edits `blend`), full
#      to 1.8 R and gone by 2.6 R (W2q-2 2.6 / 3.2), the union's k 3 (1.5): W2q-2's 60 (1 - w) cut plane made an edge
#      at the window's rims which the cage's fit rang across: the flank line q +10 wobbled +-0.3 mm at d 110-130 (w02
#      _w2q2 / _w2q3 0.28 / 0.29, _w2q4 with the brow shift 0.35 over the ripple gate's 0.3; W2p 0.20). Probes:
#      blended alone (s9) 0.40 (the cut spread wider), blended and narrower at k 3 (s10) 0.13 at d 108 over d 100-135
#      (check_w2q scratch flank_ripple.py on the limit), the lids' axis down -0.12 / -0.12 / +0.01, down-lat -0.72 /
#      -0.57 / -0.21, down-med -0.45 / -0.33 / -0.29 (s7 -0.09 / -0.12 / +0.02, -0.72 / -0.56 / -0.17, -0.45 / -0.32 /
#      -0.27))
#      (W2q probes, check_w2q/NOTES.md: brow t 5 (q1) up -0.21 / -0.39 / -0.73 R at rho 1.1 / 1.25 / 1.5 on the lids' axis
#      (W2p -0.51 / -0.58 / -0.72), t 6 (q2) -0.14 / -0.28 / -0.65, t 5.5 k 3 (q3) -0.14 / -0.31 / -0.65, t 6 with its
#      back edge faded over pol 120-165 at k 4 (q7, the defaults) -0.10 / -0.24 / -0.55, up-lateral -0.06 / -0.23 / -0.66; the cut to the
#      cow's -0.05 / -0.10 / -0.12 below (q1 ended at 2.0-2.5 R and left a 5 mm step at 2.1 R, sections_q1.png; rising
#      to the cheek over the arch by 3 R, q2 on, none): down -0.12 / -0.13 / +0.02 (W2p +0.06 / +0.12 / +0.22))
#      (W2p, the lead's calls 1 and 4, on W2p's skull (canid_skull: MWNH 358's arch over the orbit, its dorsal edge 24.9 at
#      the lateral canthus's d against s12092001's 29.2; the bone now 7.1 mm off the canthus, W2o 4.3). LATERALLY the
#      canthus ON the face (clear 0; W2o 2.0 left 4.9 of the 7.2 mm carved and the skin over the arch rose 6.5 mm within
#      1 mm below the canthus: the beak) with the bump shorter out along the line, wider across (3 / 4 / 5): down the eye's
#      axis the notch past the tip 2.0 / 1.3 / 0.3 mm at 0.5 / 1 / 2 mm (W2n's outer end, the good one, 1.6 / 1.3 / 0.65;
#      W2o 0.06 under a 6.5 mm cliff), the section below the canthus a ~45 deg slope, no cliff; in the front cameras the
#      dip past the corner 0.5-2.1 mm at 1 mm (W2o 3.4-5.4; W2n 0.9-1.3). MEDIALLY shorter out along the line toward the
#      nose and wider across below it (5 / 5 / 12; W2o 9 / 5 / 7) but 7 upward, toward the brow (the 4th sigma), with the
#      notch 0.4 mm (1.5): the groove past the tip 2.4 / 2.6 / 2.8 / 1.9 / 1.4 / 0.3 mm at 0.5 / 1 / 2 / 3 / 4 / 6 mm (W2o
#      2.6 / 3.0 / 3.8 / 2.5 / 1.8 / 1.0), the brow's ripple 0.12 (probe s1, check_w2p/ripple_p.py). Wide across in every
#      direction (5 / 5 / 12, w02 _w2p1) the groove read the notch's ~1.5 (1.6 / 1.4 / 1.6 / 1.2 / 0.8 / 0.1) but the bump
#      reached the brow 8 mm over the inner canthus: its |x| 26 line rippled 0.38 mm at d 128 (the gate 0.3); 8 across
#      (r1, r2) 2.0-2.3 and 0.30; upward 9.5 / 10.5 (s3, s4) 1.8-2.0 / 1.6-1.8 but 0.35 / 0.41; the groove is read against
#      its flanks and the brow is its upper flank. The inner canthus seen from every front camera and the level front (14
#      of 14; out along the line 4, r3, hid it from w07 R). work/bestiary/wolf/check_w2p/NOTES.md (probes p1-p7, m1-m3,
#      f1-f4, r1-r4, s1-s4), the W2o fresh eyes' notch.py / opening.py)
#      (W2o probes o2-o12, check_w2o/out/_o678_cmp.png, _o89_cmp.png, _o10_o12_medial.png: laterally clear 1.0 (the carve
#      5.9 mm, held up to 3.2 mm by the zygomatic arch's dorsal process, whose skin stands 7-8 mm in front of the canthus
#      along the eye's axis) left a round pit 3-4 mm beyond the tip; 2.0 (4.9 mm) and 2.5 none; a narrower bump (6 / 5 / 6)
#      kept it. Medially (the skull 5 mm off) the canthus goes ON the face (clear 0, 5.3 mm): at 2.0 / 0.5 mm under it the
#      front photos' lines of sight graze the face and emerge 4-7 / 1 mm in front of it (hidden from every front camera,
#      check_w2o/corner_vis.py), at 0 it is seen from all of them and the inner corner opens as a V. The lateral bump
#      SHORT (4 / 4 / 4): out along the fissure's line 10 mm it left a groove past the tip and across 6-8 mm a recess over
#      each corner, both read as fissure by w02's eye openings (_w2o1: the median 0.427 against the photos' 0.348; probes
#      f1-f3, g1: 0.386); a narrower MEDIAL bump hid the inner canthus again (g2 3 / g3 9 of 14 views))
# THE NOSE'S CAP (W2l): canid_nose.RHINARIUM (the leather lofted from PROFILE's tip to its border on the plan's width,
# its sections the photos' front outline, morphing into the muzzle behind it), unioned with the skin in reference().
# (W2k's NOSE_BLOCK, the leather's front extruded per height and closed under a plane, with the bridge widened behind
# it, made a flat top and a right-angle top-front edge: the pig's snout disc of the W2k fresh eyes; W2j's NOSE_DOME a
# blob with a waist behind it)
# THE NOSTRIL (W2l: canid_nose.nostril_chart's comma in canid_nose.level_frame's level front chart, image mm (x, q) about
# the opening's centre, the chart scaled by the opening's half axes): the RIM an ellipse round the fold's outer edge
# (fold_out's box + pad), held `inset` mm inside the leather's outline and `mid` mm off the midline; the FOLD's crest `at`
# of the way from its inner edge (fold_in: where it overhangs the opening) to its outer (fold_out), raised `h` mm along
# the leather's normal, faded over `fade` deg past the fold's ends, elsewhere `out` mm outside the opening on the leather;
# the opening's EDGE on the comma, tucked in along the line of sight (+d) `tuck0` mm all round (the planum rolls into the
# opening medially and below: no rim) and `tuck` mm more under the fold; the dark CORE's outline `core` mm in; then the
# vestibule (DEEP) and the CANAL shrunk toward the core's centre and run `depth` mm in along the line of sight turned
# `turn` deg (negative: DOWN as it runs back), so that from the level fronts and from above (w12's camera, 49 deg over
# the palate) their walls stand edge-on or face away from the key and the openings read dark; its END closes the tube
# [P the photos' comma; E the depths and the turns: a geometric read for the clay; the real vestibule runs dorsocaudally,
# its dark is the cavity]
NOSTRIL = dict(rim_pad=3.0, inset=2.8, mid=3.0, at=0.5, h=1.6, fade=25.0, out=1.4, tuck0=1.0, tuck=1.0, core=3.0,
               core_up=0.0, core_shrink=0.95, deep=dict(shrink=0.95, depth=9.0, turn=5.0),
               canal=dict(shrink=0.7, depth=14.0, turn=5.0), end=dict(depth=16.0, turn=10.0, spread=0.5),
               crease=(0.0, 1.2), tip_fade=(30.0, 0.5), over=0.0, over_lat=1.5, tuck_up=0.0,
               # (W2u restart 2: tuck_up 0 (1.2): canid_nose RHINARIUM seat now tips the opening up toward the high
               # cameras; the extra tuck only hid the opening's top under its lip from w12's camera, 1.2 mm of it)
               # W2u: THE ALAR WING as a lobe of three rings (LAYOUT tubes nostril 'wing_o', 'wing', 'fold'; place_nostril):
               # in the fold's sector its OUTER FOOT, CREST and INNER LIP at `at` of the way across the fold's band (0 its
               # inner edge on the opening's margin, 1 its outer edge), raised `h` mm along the leather's normal and
               # carried `over` mm in across the line of sight toward the opening's edge (the lip overhangs it, the edge
               # tucked `tuck` mm under it); off the sector the three on the planum at `gap` of the way from the opening to
               # the rim (no rim round the head's medial side and its foot); the wing eased out toward the slit's tip
               # over tip_fade (deg, the height's factor at the tip); the dark core at most core_wall mm inside the
               # opening's edge on every spoke (the slit a deep slot, place_nostril); the carry-in `over` beside the
               # head's lateral side rising to `over_tail` over the slit along the fold (`ramp`: its start and full
               # point, 0 at fold_from, 1 at the slit's tip)
               # the raise's part toward the level camera scaled by `fwd` (the lobe bulges sideways more than forward);
               # the core sunk core_tail mm under the slit; the wing eased in from its start over start_fade (deg, the
               # factor at the start)
               wing=dict(at=(1.0, 0.4, 0.0), gap=(0.72, 0.48, 0.24), h=(0.8, 1.9, 1.6), over=(0.0, 0.3, 0.5),
                         over_tail=(0.0, 1.2, 2.6), ramp=(0.3, 0.8), tuck=1.8, tip_fade=(45.0, 0.1), core_wall=0.9,
                         fwd=0.5, core_tail=5.5, start_fade=(45.0, 0.15)))
#                (W2u probes, check_w2u_nose: w1 h (0.7, 2.4, 2.0) over (0, 0.5, 1.6): the lobe reads at level, the lit
#                flap inside each opening stays; w2 + core_wall 0.9: the flap gone; w3 fold_w 1.8 / 4.2 / 2.2, h (0.3, 2.6,
#                2.1), over (0, 0.6, 1.8): fatter, but the lip hid the head's lateral margin (level share 12.2 -> 10.8 %)
#                and in profile the lobe stood ~2 mm ahead of the leather's front (raised along a normal that points
#                forward there); w4: the carry-in ramped head -> tail, the lobe lower (the head's margin back: the box
#                reads at f10 / 015 / 005 / f08 0.47 / 0.47 / 0.65 / 0.40, W2t's 0.49 / 0.48 / 0.66 / 0.43); w6: fwd 0.5
#                and core_tail 5.5 (W2t's three-quarter "horn" is the slit's FLOOR, a shelf facing the key 2.8 -> 3.0 mm
#                deep: sunk, it darkens); w7: start_fade and a softer outer slope (in profile w6's wing was a flap with a
#                pointed upper corner and a crisp back edge). A HOOK round the slit's end (fold_in carried on along its
#                lower edge) was a no-op: it spans less than the 24 spokes' 15 deg. Restart 2, with canid_nose RHINARIUM
#                seat: the wing sits on the set-back corner, its lip beside the head's lateral margin; a fatter wing
#                (h 1.0 / 2.6 / 2.0, over_tail 3.2: probe s6) changed no read and barely showed, so these values stay)
#                (W2u, the lead's NOSE call: "the CONSTRUCTION, a broad box of a pad (wider than tall, a flatter front)
#                and a fat alar wing over the comma's tail (the nostril tube in canid_cage)". The photos' wing (015, f10,
#                w12, f04: work/bestiary/wolf/check_w2u_nose/out/photos): a thick C-shaped lobe round each opening's
#                lateral side, ~4.5 mm wide at 015's scale, its foot hooking in over the slit tail, which runs out under
#                it as a dark crescent; W2t's one 'fold' ring (h 1.6 at 0.5 of a 1.4-3.2 mm band, carried in 1.5 over
#                the tail) printed a thin ridge on the opening's upper-lateral rim, and W2t's w1a / w1b (h 2.6, over_lat
#                3.4, band 4.0) could not be told from it: a single raised ring between the rim and the edge subdivides
#                to a peaked ridge whatever its numbers)
#                (W2s, the lead's call 6, with canid_nose NOSTRIL_L's fuller comma, its note): tuck_up 1.2 (2.5: the upper edge
#                sank under the leather above it: w12's camera sees the crest there, the tent's arch), the wing h 1.6 at
#                0.5 of the fold (1.0 at 0.55) and carried in 1.5 mm over the tail alone (over_lat), the canal nearly straight
#                back (5 / 5 / 10; 20 / 20 / 24: turned up it showed the high cameras its lit floor: deep 0.46 -> 0.82)
#                (W2r, the lead's call 4, with canid_nose NOSTRIL_L's larger, higher comma: the opening's upper edge tucked
#                back tuck_up 2.5 mm more than its lower (place_nostril: its plane tips up toward the high cameras), the
#                fold's crest no longer carried over the opening (over 0, W2m-W2q 0.5) and raised h 1.0 (1.4): from w12's
#                camera the fold hid the opening's top; the canal and its end turned up 20 / 24 deg (32 / 38): with the
#                comma 3 mm higher the end came through the leather's top as two pinholes (probe n3). w12's camera 2.9 ->
#                7.0 % of the leather, deep 0.46; tuck_up 4 (n5) 6.9 %, deep 0.24 (the gate's 0.36))
#                (W2o, the lead's call 3, "a nostril that reads dark from above AND from level / below-front": with
#                canid_nose NOSTRIL_L's fold from 60 deg (over the head's lateral side and the tail, no longer its top) the
#                crest carried in 0.5 mm (1.5), the edge tucked 1.0 more under it (1.8) and the core 3.0 mm in (2.0): the
#                comma's head opens to w12's and w08's high cameras as a dark hole, the tube still turned up under the
#                fold so the level and below-front reads keep their dark commas. check_w2o/nose_read.py (w02's geometric
#                read on probes): w12's camera the openings 1.9 -> 3.7 % of the leather, deep 0.36 -> 0.85; w08's 3.0 ->
#                4.9 %, 0.20 -> 0.85; level 5.8 -> 7.2 %, 0.78 -> 0.93; below-front 7.9 -> 11.2 %, 0.95 -> 0.90. Probes
#                n1-n8: the canal straight back (n3) or first down (n4) lit its inside from below; check_w2o/out/
#                _nose_cmp1-3.png)
#                (W2m: the fold's crest carried 1.5 mm in over the opening (`over`, place_nostril) so the fold roofs the
#                comma's tail, and raised h 1.4 mm (1.8: in profile the raised fold stood ahead of the leather's front as a
#                flap; probe p6))
#                (W2m, the lead's call 2: "the nostrils as commas whose lateral tails read as dark slits from level and
#                below-front, not round rimmed holes"; CANID_HEAD_STUDY 2.4: real nares are cavities that turn BACK AND UP
#                under an overhanging alar fold, so even untextured clay reads them dark from level and from below, and the
#                slit is dark because the fold covers it. The vestibule, the canal and the end now turn UP as they run back
#                (+20 / +32 / +38 deg: dorsocaudal, the canid's and the cow's), under the fold, where W2j-W2l turned them
#                down 50-62 deg so that w12's high camera (49 deg) would see their walls edge-on: from level and below-front
#                that showed the down-turned canal's lit back wall, a round rimmed hole. The opening's edge tucked 1.8 mm
#                under the fold (1.0) and the fold's crest kept at 0.5 of h at the slit's tip over 30 deg (0.25 over 40), so
#                the fold stands over the comma's tail. The leather above the canal is deeper now (canid_nose d_b 16.5): the
#                end, 16 mm in at 38 deg, rises ~10 mm to q ~19 at d ~13 under a top at ~22.5)
#                (W2l h3, the restarted head builder: the rim's pad 3.0 mm (2.2: with the comma's longer slit the fold
#                was crushed inside the rim on 2 spokes by its tip); the fold's crest eased to 0.25 of h at the slit's tip
#                over 40 deg (place_nostril: the wedge and spike under the slit's lateral end))
#                (W2l: in the level chart the line of sight is +d; along it, as W2j-W2k ran the canal along w12's, the
#                vestibule's floor faced w12's key and read lit (W2l n1: 0.08 % dark in w12's read); turned down 30-48 deg
#                (n2) 0.26 %; with the larger comma, tucked 1 mm all round, the core 2.5 mm in, turned 35-50 deg (n3)
#                1.2 % (2.6 % in w08's); narrower (shrink 0.65) 0.7 %; WIDER and steeper (0.95 / 0.7, 50-62 deg: n5)
#                1.8 % (2.1 % in w08's), the commas dark under the fold from the level front. The photo's own read is
#                ~8 % in w12's camera: a clay's white cavity under one key is not the leather's black)
#                (c9a, the W2j look agent: the core at the traced dark outline 3 mm in, the vestibule and the canal wider
#                (0.8 / 0.5 of it) and run 8 / 13 / 15 mm in ALONG w12's line of sight (turn 0, -5, -8 deg): turned up
#                55-70 deg, their floor faced w12's key and read lit, 0.04 % dark against the photo's 8.1 %; along the
#                line of sight the walls fall in shadow, 6.6 % (0.81 of the photo's; the gate's band 0.7-1.3). The probe
#                of n1-n6 in work/bestiary/wolf/check_w2j/ovr: a canal turned down 15-18 deg read 3.0 %, a narrow one
#                5.1 %. A geometric read for the clay; the real vestibule runs dorsocaudally, its dark is the cavity)
#                (c8c: the core 0.75 of the traced dark outline about its centre, the canal narrower: c8b's wide cone
#                (the core at the dark outline) read lit, 0.1 % dark in the nose read; turned 80 deg at 14 mm it came out
#                through the leather's top as pinholes, so it reaches 11 mm turned 55-70 deg)
#                (c7d: the core 4 mm in and 1.2 mm UP the image, under the fold, the vestibule turned 55-75 deg: c7c's
#                funnel, 3 mm in and turned 35-55 deg, faced the front cameras with lit walls; the opening's edge creased
#                crease[1] under the fold, crease[0] elsewhere: a crisp lip all round read as a ring)
# THE EYE (in the fissure's plane: canid_hull.traced_fissure with its corners drawn out to the photos' canthi, carried
# onto the lid's sphere; the chart scaled by the fissure's half axes along its canthus axis and across it): the RIM an
# ellipse `pad` (along, across) mm outside the fissure on the face; LID_OUT `f_out` and LID_MID `f_mid` of the way from the
# margin to the rim, on the lid's sphere (the globe + `lid` mm), LID_OUT half on the face; the MARGIN on the fissure, on the
# lid's sphere (past the sphere's outline, at the canthi, on the face `sink` mm in); the ROLL `roll` of the margin's radius
# on the globe (`inset` mm in; past the globe's outline `corner` mm under the margin: a shallow canthal recess, not a
# slot); the SAC `sac` of it, `sac_in` mm inside the globe; the enclosed quads deeper inside the globe [P the tracings;
# the lids' thickness STROKES_SKULL eye lid; the rest E]
EYE = dict(lid=0.6, pad=(8.5, 7.0), f_out=0.25, f_mid=0.12, lid_out=0.8, rim_cap=40.0, sink=0.5, roll=0.90, inset=0.25,
           corner=1.6, sac=0.62, sac_in=3.0, core=0.45, graze=(0.80, 0.97),
           orb=(0.30, 0.62), orb_s=(0.65, 0.92), lid_rise=0.50, star=(360, 2.5),
           pin=False, crease=(0.35, 0.25, 0.7), notch=(0.4, 28.0),
           face=dict(third=0.33, roll=4.0, roll_lateral=1.0, roll_medial=3.0, follow=True), env_pad=0.5,
           on_face=(0.5, 1.5), keep_chart=True, rim_slide=None, spoke_even=(6, 0.15))
#      (W2t, the lead's call 2, "the rim corner rebuilt so the brow and the medial fold both pass": spoke_even (n_top, frac):
#      place_eye's even_spokes, EVERY ring of the tube on spokes re-laid from the medial tip over the square's top-medial corner
#      to the top side's cell 6, the corner cell 0.15 of the way: the column's cells crowd onto the rim's steep front above the
#      tip and the rim's slanted top-front run (slope ~0.8 in (d, q), the side grid's rows ~1.1 into it) belongs to the top ROW,
#      where W2r's column put it on the medial COLUMN (the inverted side quad R[2-3, 23-24]) and W2s's rim_slide 20 moved only
#      the rim's own vertices (a held ridge 0.72 / 0.70 mm at 1.6 / 1.9 R). On the cage at the W2t seat (check_w2t probe.sh
#      sf15n6, corner_scan): 0 inverted limit triangles and 0 inverted cage quads round the rim's medial-up corner (the crease
#      points 119.3 / 41.6 / 24.4 and 122.5 / 43.0 / 26.5, r 7), seen back-faces 0.00 at rest and at every photo gaze from 5
#      cameras, the brow on the limit mesh 0.25 / 0.14 / 0.09 at 1.6 / 1.9 / 2.2 R (the 1.6 at az -100: the medial canthus's
#      own groove, which the seat brought to rho 1.54 R), the fronts at their gazes 0.79 / 0.77 / 0.75 / 0.81, w11 0.72. The
#      window is narrow: n_top 6 at frac 0.18 or n_top 5 at 0.20 keeps R[2-3, 23-24] inverted, n_top 5 at 0.15 inverts an
#      orbit-ring quad between the crowded spokes 29-30, frac 0.10 4 limit triangles and 8 quads; with even spacing (frac None)
#      the side quad stays inverted with or without a 5-10 deg rim slide)
#      (W2s, rim_slide: place_eye's note, the medial crease: seen back-faces 0.3-1.0 mm2 -> 0.00 at every camera and pose. 20 deg,
#      not 30: THE ANGLE TRADES A GROOVE FOR A RIDGE at the rim's medial-up corner. W2r's limit lay -1.79 mm under the reference
#      there (the crease), _w2s2's at 30 deg +1.47 over it at (122.3, 43.0, 26.5), its rim vertices at 0.0. Angle: inverted limit
#      triangles at the crease / the brow circles at 1.6 and 1.9 R / w02's ripple gate: 0 deg 4.94 mm2 / 0.28 0.20 / 0.27; 5 2.22 /
#      0.28 0.46; 10 0.50 / 0.33 0.46 / 0.42; 15 0.00 / 0.63 0.58 / 0.41 (FAIL, _w2s3); 20 0.00 / 0.73 0.70 / 0.27; 30 0.00 / 1.21
#      0.84 / 0.27. 20 is the least with no fold that passes the ripple. A fold as small as 10 deg's stays unseen from every test
#      camera yet a bake would print it, so the inverted triangles decide, not the seen ones. Spreading the slide over 9 or 12
#      top cells, the brow_med zone's weight 0.08 / 0.03 and RELAX eye_iters 800 do not touch the ridge: check_w2s crease.py,
#      brow_seq.py, ref_off.py, ripple_read.py)
#      (W2r, on_face (mm): the lid's and the orbit's rings go onto the face past the lid sphere only where the face stands
#      within on_face[0] mm of the margin along the eye's axis (none past on_face[0] + on_face[1]); elsewhere they climb
#      from the margin as over the globe (place_eye's W2r note: the slot under the lower lid's outer third))
#      (W2q, env_pad: the rim stands this share of the pad outside the lids posed at the largest fitted gaze (eye_chart
#      fis_env; place_eye). With the whole pad (1.0) the rim's top rose into the face cap's top rows and folded the cage
#      quad above it (172 deg off its neighbours, check_w2q probe q15), a thin dark arc over the eye in every close view;
#      at 0.5 (q16) that fold and the one over the outer corner are gone, the fronts at their gaze IoU 0.76 / 0.78 / 0.77
#      / 0.81 (q15 0.80 / 0.83 / 0.77 / 0.81). The folds at the rim's medial-up corner (d 114-124, q 39-48, |x| 24-26,
#      120-160 deg) are W2p's too)
#      (W2q, with the rest lids and the brow forward (REF brow): the lids' outer ring nearer the margin (f_out 0.25, W2p
#      0.32), lifted half way to the face (lid_rise 0.5, 0.3) and the orbit's rings nearer the face (orb_s 0.65 / 0.92,
#      0.50 / 0.82): the upper lid rolls up to the brow over the rings instead of hugging the globe to a step; the upper
#      lid's crease 0.35 mm (W2n's 0.7 printed a fold across it). Probes (check_w2q/NOTES.md): q3 these values, the
#      lateral corner's groove down the eye's axis 1.73 / 1.23 / 0.56 mm at 0.5 / 1 / 2 mm past the tip (W2p 2.04 /
#      1.34 / 0.31); the crease off with W2p's fractions (q5) 3.52 / 2.50 / 0.83 and with the rings at the face (q4)
#      3.24 / 2.44 / 1.01: the beak's start, not taken)
#      (W2q, the lead's call 1, "THE REST GAZE IS NEUTRAL ... the lids become a function of gaze"): face `follow`: the
#      margin is the REST LIDS (canid_hull.lid_follow: each photo's traced lids turned back to the rest gaze, level and
#      forward along the palate, by its own iris gaze and the fitted follow ratios, averaged with the profile w11's), the
#      chart framed on them, the rim and the orbit's rings enclosing the lids posed at the largest fitted gaze (w12's:
#      eye_chart's fis_env); the cage carries the eye rig's weights (EYE_RIG), and pose_eye turns the lids to any gaze
#      (each photo is compared at its own: w02). W2p's face `gaze` / `gaze_lower` (a fixed turn of the fronts' lids)
#      are superseded by it
# W2q: THE EYE RIG'S LID-FOLLOW WEIGHT per ring of the eye's tube (the runtime's lid joints turn the lids about the
# canthus axis by f_lid (theta(gaze) - theta_rest): canid_hull's W2q note), times the taper along the axis
# (canid_hull.lid_taper: 0 at the canthi); a vertex's upper-lid share by its spoke's side of the tip-to-tip line in the
# chart, blended over `band` of the spoke direction's offset from that line. The margin, its roll, the sac and the
# enclosed core turn with the lids; the lid's outer surface less and less out to the orbit's rim; the socket's rim not
EYE_RIG = dict(margin=1.0, roll=1.0, sac=1.0, inner=1.0, lid_mid=0.95, lid_out=0.85, orb_in=0.55, orb_out=0.25, rim=0.0,
               band=0.5)
# W2s: THE HORIZONTAL FOLLOW'S OWN RING WEIGHTS (canid_hull GAZE slide_mode 'warp': the lid's shape carried along the
# fissure with the cornea); a ring not named takes its EYE_RIG weight. Empty: the vertical follow's weights
EYE_RIG_SLIDE = dict()
#      (W2r, the lead's call 1, "a gate counts ring crossings at rest and at every photo's gaze": the weights fall off
#      with each ring's share of the way from the margin to the rim along its spoke (lid_mid 0.12, lid_out 0.25, orb_in
#      ~0.48, orb_out ~0.72 in the chart), so the band between the lifted margin and the fixed rim compresses in order.
#      W2q's 1.0 / 0.75 / 0.35 / 0.1 put the whole drop between lid_mid and orb_in: at w12 R's up-gaze (the upper lid
#      turned 31.7 deg) lid_mid rode with the margin while lid_out lagged 7.9 deg, past it by 0.5 mm on the cage and
#      -0.15 mm on the limit at spoke 3 (check_w2r/fold_diag.py; the rings gate's FOLD). With these: no fold at rest, at
#      any fitted gaze or at w07's +30 / w01's -65; the lids' largest lean over the margin 55 deg (w12 R, spoke 2; the
#      gate's wall 65) (ring_gate.py W2R_RIG scans on probe c2: 0.88 / 0.75 / 0.525 / 0.285, the linear shares, also
#      fold-free but lid_mid leaned 70 deg there: the pretarsal skin lagging the margin stands in front of it)
#      (W2p, the lead's calls 1 and 4: each corner's roll its own depth (place_eye): the LATERAL 1 mm back along the eye's
#      axis (W2o's 4 mm pocket under the face read as the slit between the beak's two lit lips; at 0.5 the reads past the
#      tip are the same), the MEDIAL 3 mm (the inner corner's dark pocket kept, seen from every front camera: the tip's own
#      depth down the axis 4.5-5.0 mm, the pocket, W2o 6.5); the medial NOTCH 0.4 mm on its 4 spokes (with REF canthi's
#      medial bump, the groove past the tip ~1.5 mm). Two options stay OFF (W2p, for the lead's call on the eye's gaze, NOTES
#      W2p): face `gaze` / `gaze_lower` (deg: canid_hull.fissure_chart turns each lid down to a rest gaze about the
#      globe's horizontal axis, the corners held; eye_chart frames the chart on the unturned margin) and `rise` (mm: the
#      orbit's rings and the rim each that much farther from the globe's centre than the ring inside, where the margin
#      rides the globe). Probes q22 / q28: the side read 0.91 -> 0.72 / 0.65 of the opening over its corner line (the
#      profiles 0.32-0.52) while w12's IoU fell 0.70 -> 0.39 / 0.31 and the turned upper lid grew a flap; gl20 (the lower
#      lid alone, 20 deg): the side 0.80, the level front 0.80 (0.87), w08's share over its corner line 0.62 / 0.63 (its
#      photo 0.59 / 0.65; at 0 0.70), w12's IoU 0.65 / 0.61 (0.70 / 0.65))
#      (W2o, the lead's call 1: "carry the fissure's inner third and both canthi onto the face at the profile-rule points,
#      in the CAGE only ... make place_eye's lid and orbit rings follow the corners". `face`: canid_hull.traced_fissure's
#      face rule (each photo's canthi at the profile rule on their own rays, `third` of each lid's length from a canthus
#      carried along its rays from the sphere rule's depth toward the canthus's, never into the globe), so the cage's tips
#      ARE the profile-rule canthi (canid_hull.canthi_on_rays 'profile'): medial (124.5, 33.4, 27.5), lateral (145.8,
#      29.7, 51.6), where W2n's sat on the cameras' limb planes 7.1 / 6.9 mm off. place_eye puts a spoke through each tip
#      (spokes_on_tips); where the margin runs on the face its lid and orbit rings lie on the face (the reference, brought
#      in round the canthi: REF canthi), and its roll goes `roll` mm back along the eye's axis (the corner a steep pocket,
#      dark from the front cameras: radially, 1.6 mm, it left a lit tongue at the inner corner; 3 / 4 / 5 mm probed,
#      probes o3-o6). The registration keeps its pinned sphere corners (canid_hull.eye_landmark, CANTHUS_DEPTH_REG): no
#      fixed-point problem)
#      (W2n, the lead's calls 1 and 4: `pin` False: the traced fissure's corner ends run on along their rays past the ball's
#      outline to the photos' canthi (canid_hull.traced_fissure pin), not pinned onto the outline, then drawn out along the
#      tip-to-tip axis: the corners pointed. Pinned (n1), every photo's medial end ran down the outline and the tips drawn
#      2 mm further out carried it: a square medial end 13-14 mm off the axis, a window into the canthal recess from w12
#      and three-quarter (check_w2n/out/cmp_n2_n3_eyes.png, eye_overlay_n3.png). The registration keeps the pinned corners
#      (canid_hull.eye_landmark: pinned, they tie the fixed point to the globe; the unpinned tips follow the cameras); the
#      unpinned tips' midpoint lands 0.66 mm from it, 0.4 mm in w12's image. `crease` (depth mm, the spoke's sine where it
#      starts and where it is full) and `notch` (depth mm, half angle deg): place_eye's upper-lid crease and medial notch
#      (CANID_HEAD_STUDY 6). Both read faintly at the clay's scale: the crease as a soft line over the upper lid from w12
#      and three-quarter; the notch (the rings beyond the medial tip sunk along the axis) only as a slight dip: 1.0 / 18
#      deg reached 2-3 spokes, 1.5 / 28 deg reaches 4 (probes n2-n4)
#      (W2n fresh eyes, measured on this cage (de09fd419a55a076): only the LATERAL corner is pointed. Unpinned, a missed
#      ray keeps its nearest approach to the lid sphere, which lies on that camera's limb plane (the plane through the
#      globe's centre facing it), and seen along the lids' axis that is the globe's medial outline: the margin's inner end
#      still runs 11.8 mm down the globe's medial side (d 128.8-130.1, q 28.3-41.5) to a tip at (129.1, 28.3, 29.1), 7.1 mm
#      from where the front rays and the profiles agree the inner canthus is (canid_hull.canthi_on_rays 'profile': (124.5,
#      33.4, 27.5), ~1 mm under this skin); from every front camera that tip lies 12-17 mm behind the first skin toward it:
#      work/bestiary/wolf/check_w2n_fresh/corners.py, out/corners_n6.png)
#      (W2m, the lead's call 1: "lids flush on the globe"; CANID_HEAD_STUDY 1.4: the lid margin rides ON the globe, at
#      1.06 R in the cow and 1.007 R in study T's canid, never on a sphere 1.8 mm out (1.15 R): the step the W2l fresh eyes
#      saw from the high cameras as a lit band inside the socket ring. lid 0.6 mm = 1.05 R (W2h-W2l 1.8), with canid_hull
#      STROKES_SKULL eye lid[0], which carries the traced fissure onto the same sphere)
#      (W2l, the restarted head builder: `star` (n angles, the largest rise of the chart radius per radian in its half-axis
#      units) keeps the traced fissure star-shaped round the chart's centre (eye_chart, star_outline): with the eye's axis
#      turned out to the lids' own facing (canid_hull STROKES_SKULL eye axis 19 / 40) the lower lid ran nearly radially
#      into the medial corner and turned back ~3 deg, and the spokes' farthest crossings jumped 0.71 -> 0.95 of the lid's
#      sphere between two spokes: a notch at the lower lid's medial end)
#      (W2l, the lead: "the lids sit on a sloping face rather than in a crater": the climb of 12-25 mm medially and below
#      spread over a pad 8.5 / 7 mm (W2k 7 / 6), the orbit's inner ring nearer the lids and lower (orb 0.30 at 0.50 of the
#      climb; W2k 0.38 at 0.62), the outer at 0.62 / 0.82 (0.70 / 0.88): the socket's lip softer, the fissure gate's median
#      0.351 and the eyeball 0.78 (W2k 0.378 / 0.73). Tried and dropped: the medial spokes cast LEVEL instead of along the
#      descending axis (a cliff and a cut down the medial side, the eyeball 0.65-0.69) and the pad grown 5-9 mm medially /
#      4-7 mm below (a wider basin, the eyeball 0.64-0.66). The MWNH 358 orbit rim's plane faces 26 deg up and 51 deg out;
#      the lids' axis (canid_hull STROKES_SKULL eye axis, 24 up / 18 out) and the globe's seat (the cornea at the rim's
#      centre) were left: the traced fissure is carried in that frame)
#      (W2k, the lead: "the eye in a socket ... two or three transition rings from the lid sphere out to the face, so no
#      single row climbs the difference": the RIM on the face (rim_cap 40: no hold; W2j's 6 held it under the face
#      medially and ventrally, where the face stands 6-12 mm over the lid's sphere at the fissure's medial corner and 20+
#      mm out from the globe's centre beyond it (the orbit's medial rim and the muzzle's side stand forward of the forward-
#      looking eye), and the next row out climbed the whole difference), its ellipse pad (along, across) 7 / 6 mm outside
#      the fissure; the lids' outer ring nearer the margin (f_out 0.32, f_mid 0.12) and starting the climb (lid_rise 0.30
#      of the way from the lid's sphere to the face there); between it and the rim the ORBIT's two rings at orb of the way
#      out on the chart, each on the face there (cast along -nf, as the rim) held at orb_s of the way from the lids' outer
#      ring's distance from the globe's centre to the face's: a full lid fold rising from the globe and rolling into the
#      face over the orbit's rim (the cornea sits at MWNH 358's rim plane, its ventral and medial rim 8-10 mm proud of the
#      globe, the skin 5-7 over it). Tried and dropped: the rim held within 10 / 14 mm of the lid's sphere (a crater with
#      a lip: the hold pulls the rim inside the face), rings set radially from the globe's centre (the face is no sphere
#      round it: the outer ring stood over it), a carve of the reference into a bowl round the eye (a cliff-edged cavity),
#      pad 9 / 8 (the socket read as an oval ring round the eye from the front))
#      (c8c: the canthal recess 1.6 mm (0.8: too shallow for the opening the fissure gate reads on the surface: the
#      medians 0.310 against the photos' 0.348); rim_cap 8 with a fairness zone let the cheek sag: back to 6)
# THE LIP: the groove and the lower lip under the margin (each: arc length below the margin along the section, inset
# along the inward normal, mm), faded out behind the commissure over `fade` mm
LIP = dict(rows=((1.6, 2.4), (3.6, 1.3)), fade=10.0, philtrum=dict(rows=(9, 16), depth=1.6, side=0.5))
#      (W2l: the philtrum 1.6 mm deep (1.0): with the leather on the clay's frame its groove runs from between the nostrils
#      (row 9, the openings' lower half) down the leather's underside into the lip; at 1.0 it barely read from the front)
# the semi-sharp creases (DKT sharpness)
SHARP = dict(lip=2.0, leather=0.4, leather_top=0.0, rim=1.2, lid=1.5, crease=1.0)
#      (W2n: crease, the upper lid's crease along the lids' outer ring where EYE crease sinks it; nothing at depth 0)
LEVELS = dict(fit=3, out=3)          # (a crease of sharpness s is sharp for its first s levels: past ceil(max s) every
#                                      vertex's limit mask is the smooth one, so the fit needs no more levels)
RELAX = dict(iters=60, lam=0.5, eye_iters=200)
# THE FIT (fit_cage): weights of the targets (features, the reference, the reference inside the ZONES), the fairness lam
# (the cage's umbrella Laplacian squared, eased to lam_crease at crease vertices), the passes, the skull's clearance
# (skin_min mm, weight w_skull); a zone's weight eases in over `ramp` (d, q) mm boxes and past |x| > x (6 mm ramp)
FIT = dict(w_feat=40.0, w_free=1.0, w_zone=0.05, lam=0.2, lam_crease=0.02, passes=5, skin_min=2.0, w_skull=20.0,
           zones=(
               # the cheek ahead of and under the eye: W2i's arch tube's front root printed a 30 mm dome (the W2i check)
               dict(name='cheek', d=(80.0, 94.0, 128.0, 142.0), q=(-26.0, -14.0, 24.0, 32.0), x=16.0),
               # W2r (the lead's call 2): the brow over the inner corner at weight 0.3, where the limit rang +-0.25 mm
               # round the lids' axis over the reference's +-0.15 (the eye rim's medial-up corner: W2p's fold there);
               # the 1.6 / 1.9 R circles 0.27 / 0.18 -> 0.24 / 0.15 mm (check_w2r probes bc3, bc3z)
               dict(name='brow_med', d=(106.0, 113.0, 127.0, 134.0), q=(30.0, 37.0, 50.0, 57.0), x=14.0, w=0.3),
               # W2y: round the ears' ports, where the grid bends round the rim: the fairness leads, the root held (at
               # weight 1 the limit kept 0.30 mm2 of folded triangles round the ears, check d11; 0.1: none, d9; the skin
               # moved at most 0.9 mm off W2w's outside the ports, at the zone's lower front edge)
               dict(name='ear', d=(195.0, 205.0, 272.0, 285.0), q=(5.0, 15.0, 72.0, 80.0), x=14.0, w=0.1),),
           # (W2k: no 'brow' zone (weight 0.05 over d 100-170, q 26-82): the fit drifted off the reference inside it and
           # came back over its 12 mm edge at d 158-170: the crosswise step behind the brow; the reference's brow shoulders
           # it stood for are smoothed now (REF cranium))
           # (no zone round the eye: c8a (weight 0.05) and c8c (0.3) both let the face under it sag into a draped fold)
           globe_min=0.4, w_globe=20.0)     # (the free surface held globe_min mm outside the lid's sphere)
# THE HEAD'S FIELD (head_field): the exact signed distance to the limit mesh unioned with the globes, on the W2i head
# GRID's box at h mm (its 1 mm lattice every second sample, the gates' closed head): exact within `near` of the surface,
# eased by `far` into a coarse pass (coarse x h, trilinear, blurred s_far mm: the medial axes' creases far out), the air
# inside each nostril's canal capped at pocket cap mm within pocket r of its centreline (a cavity's medial axis would set
# the GRID's divisor for the whole head), clamped; the bind's opened jaw redistanced and blurred blur_open mm
HEAD_FIELD = dict(h=0.5, box=((-10.0, -100.0, -95.0), (296.0, 92.0, 95.0)), coarse=4, near=1.5, far=3.0, s_far=1.0,
                  clamp=(-34.0, 34.0), pocket=dict(r=4.0, cap=0.8, grow=1.0), blur_open=0.35, globe_pad=40.0,
                  finish_closed=True)
#                                  (globe_pad: each globe's union box reaches its radius + this, past the clamp: c7f's box
#                                  of r + 6 mm ended where the globe was still the nearest surface, a 9 mm step in one cell
#                                  in front of each eye and the GRID's divisor 3.6)
#                                  (pocket grow: the cap rises this many mm per mm in front of the opening's plane, so it
#                                  meets the true distance there continuously: a flat cap ran 5 mm out into the air in
#                                  front of the nose, a 6 mm step at its edge, the divisor 21)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smoother01(t):
    """the C2 ramp 0 -> 1 over t 0 .. 1 (Perlin's smootherstep): a displacement shaped by it prints no crease line along
    its iso-lines (smooth01's curvature jumps at its ends)"""
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def pchip(xs, ys):
    from scipy.interpolate import PchipInterpolator
    xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    o = np.argsort(xs)
    return PchipInterpolator(xs[o], ys[o], extrapolate=True)


def resample(P, n, closed=False):
    """a polyline (k, m) resampled to n points evenly by arc length (closed: n points round the loop, the first kept)"""
    P = np.asarray(P, np.float64)
    if closed:
        P = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n + (1 if closed else 0))[:n] if closed else np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(t, s, P[:, a]) for a in range(P.shape[1])])


def arclen(P):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.asarray(P, float), axis=0), axis=1))])


def polar_radius(poly, ang, closed=True):
    """the radius at which the ray from the origin at each angle (rad) meets the polyline (k, 2) (the farthest crossing;
    NaN where none: an open polyline outside its angular span)"""
    P = np.asarray(poly, np.float64)
    A, B = (P, np.roll(P, -1, axis=0)) if closed else (P[:-1], P[1:])
    D = np.stack([np.cos(ang), np.sin(ang)], -1)
    E = B - A
    den = -D[:, None, 0] * E[None, :, 1] + E[None, :, 0] * D[:, None, 1]
    with np.errstate(divide='ignore', invalid='ignore'):
        r = (-A[None, :, 0] * E[None, :, 1] + E[None, :, 0] * A[None, :, 1]) / den
        t = (D[:, None, 0] * A[None, :, 1] - A[None, :, 0] * D[:, None, 1]) / den
    ok = (np.abs(den) > 1e-12) & (t >= -1e-9) & (t <= 1.0 + 1e-9) & (r > 0.0)
    r = np.where(ok, r, -np.inf).max(axis=1)
    return np.where(np.isfinite(r), r, np.nan)


def ray_sphere(o, dv, c, R):
    """the first crossing of the rays o + t dv (unit dv) with the sphere (c, R) from outside, NaN where they miss; and each
    ray's closest approach to the centre (rho)"""
    o = np.atleast_2d(o)
    w = o - c
    b = w @ dv
    cc = np.einsum('ij,ij->i', w, w) - R * R
    disc = b * b - cc
    rho = np.sqrt(np.maximum(np.einsum('ij,ij->i', w, w) - b * b, 0.0))
    t = -b - np.sqrt(np.maximum(disc, 0.0))
    P = o + t[:, None] * dv[None]
    P[disc < 0.0] = np.nan
    return P, rho


# ============================================================================================ the reference
class Ref:
    """a reference surface as a sampled field on a grid (palate (d, q, x) mm): its value, gradient, projection and the
    first crossings along rays"""

    def __init__(self, phi, lo, h):
        self.phi = np.asarray(phi, np.float32)
        self.lo = np.asarray(lo, np.float64)
        self.h = float(h)

    def __call__(self, P):
        from scipy import ndimage as nd
        P = np.atleast_2d(np.asarray(P, np.float64))
        c = (P - self.lo) / self.h
        return nd.map_coordinates(self.phi, c.T, order=1, mode='nearest')

    def grad(self, P, e=0.35):
        P = np.atleast_2d(np.asarray(P, np.float64))
        g = np.zeros_like(P)
        for k in range(3):
            d = np.zeros(3)
            d[k] = e
            g[:, k] = (self(P + d) - self(P - d)) / (2 * e)
        return g

    def normal(self, P):
        g = self.grad(P)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)

    def project(self, P, it=10, max_step=2.0):
        """closest-point steps onto the zero set, each at most max_step mm (a vanishing gradient, where the clamped far
        field is flat, took unbounded steps), kept inside the grid's box"""
        P = np.atleast_2d(np.asarray(P, np.float64)).copy()
        hi = self.lo + (np.array(self.phi.shape) - 1) * self.h
        for _ in range(it):
            f = self(P)
            g = self.grad(P)
            st = (f / np.maximum((g * g).sum(1), 0.25))[:, None] * g
            ln = np.linalg.norm(st, axis=1, keepdims=True)
            P -= st * np.minimum(1.0, max_step / np.maximum(ln, 1e-12))
            P = np.clip(P, self.lo + self.h, hi - self.h)
        return P

    def cross(self, A, D, reach=60.0, step=0.25, outward=True, chunk=4000):
        """the first crossing along A + t D, t in [0, reach]: inside -> outside (outward) or outside -> inside; NaN where
        none"""
        A = np.atleast_2d(np.asarray(A, np.float64))
        D = np.atleast_2d(np.asarray(D, np.float64))
        D = D / np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
        ts = np.arange(0.0, reach + 1e-9, step)
        out = np.full((len(A), 3), np.nan)
        for s0 in range(0, len(A), chunk):
            a, dv = A[s0:s0 + chunk], D[s0:s0 + chunk]
            Q = a[:, None, :] + ts[None, :, None] * dv[:, None, :]
            f = self(Q.reshape(-1, 3)).reshape(len(a), len(ts))
            c = (f[:, :-1] < 0) & (f[:, 1:] >= 0) if outward else (f[:, :-1] >= 0) & (f[:, 1:] < 0)
            has = c.any(1)
            j = np.argmax(c, axis=1)
            r = np.arange(len(a))
            f0, f1 = f[r, j], f[r, j + 1]
            t = ts[j] + step * f0 / np.where(np.abs(f0 - f1) > 1e-12, f0 - f1, 1e-12)
            P = a + t[:, None] * dv
            for _ in range(2):                      # Newton along the ray
                fp = self(P)
                gp = np.sum(self.grad(P) * dv, axis=1)
                P = P - (fp / np.where(np.abs(gp) > 1e-3, gp, 1e-3))[:, None] * dv
            P[~has] = np.nan
            out[s0:s0 + chunk] = P
        return out

    def section(self, d):
        """the section at d: the x >= 0 half of its outline from the top midline to the bottom midline, (k, 2) (q, x)
        by 0.25 mm of arc length"""
        from skimage.measure import find_contours
        f = (d - self.lo[0]) / self.h
        i0 = int(np.clip(np.floor(f), 0, self.phi.shape[0] - 2))
        w = f - i0
        sl = (1.0 - w) * self.phi[i0] + w * self.phi[i0 + 1]
        cs = find_contours(sl, 0.0)
        C = max(cs, key=len)
        Q = self.lo[1] + C[:, 0] * self.h
        X = self.lo[2] + C[:, 1] * self.h
        P = np.column_stack([Q, X])
        if np.allclose(P[0], P[-1]):
            P = P[:-1]
        # the top midline crossing (x 0, the highest) and the bottom one; the arc between them on the x >= 0 side
        sgn = np.sign(P[:, 1])
        cr = np.nonzero(sgn != np.roll(sgn, -1))[0]
        pts = []
        for j in cr:
            a, b = P[j], P[(j + 1) % len(P)]
            t = a[1] / (a[1] - b[1]) if a[1] != b[1] else 0.0
            pts.append((j, a[0] + t * (b[0] - a[0])))
        jt = max(pts, key=lambda p: p[1])
        jb = min(pts, key=lambda p: p[1])
        n = len(P)

        def walk(j0, j1, step):
            idx = [j0]
            j = j0
            while j != j1:
                j = (j + step) % n
                idx.append(j)
            return idx
        # the two arcs between the crossings; keep the one on x >= 0
        arc1 = walk((jt[0] + 1) % n, jb[0], 1)
        arc2 = walk(jt[0], (jb[0] + 1) % n, -1)
        arc = arc1 if np.mean(P[arc1, 1]) > 0 else arc2
        H = np.vstack([[jt[1], 0.0], P[arc], [jb[1], 0.0]])
        H[:, 1] = np.maximum(H[:, 1], 0.0)
        s = arclen(H)
        t = np.arange(0.0, s[-1], 0.25)
        return np.column_stack([np.interp(t, s, H[:, 0]), np.interp(t, s, H[:, 1])])


def fill_flank(phi, G):
    """THE MUZZLE'S FLANK FILLED behind the canines (REF flank), phi on the grid G in place: the field lowered by amp(q) x
    an asymmetric gaussian in d about dc x the off-midline ramp (x0, xw), so the muzzle's sides move out by up to amp mm
    where W2i's skin pinched them. Returns the fill's peak (mm)"""
    fl = REF['flank']
    ds = G.lo[0] + np.arange(G.n[0]) * G.h
    qs = G.lo[1] + np.arange(G.n[1]) * G.h
    xs = G.lo[2] + np.arange(G.n[2]) * G.h
    sd = np.where(ds < fl['dc'], fl['s'][0], fl['s'][1])
    a_d = np.exp(-0.5 * ((ds - fl['dc']) / sd) ** 2)
    at = np.asarray(fl['amp'], np.float64)
    a_q = np.interp(qs, at[:, 0], at[:, 1], left=0.0, right=0.0)
    gx = smooth01((np.abs(xs) - fl['x0']) / fl['xw'])
    for i in np.nonzero(a_d > 1e-3)[0]:
        phi[i] -= (a_d[i] * a_q[:, None] * gx[None, :]).astype(phi.dtype)
    return float(at[:, 1].max())


def canthus_carve(phi, G, spec, log=print):
    """W2o (the lead's call 1: "bring the face in by about 7 mm round the outer corner (the profile-rule outer canthus is
    7.2 mm inside today's skin; the inner ~1 mm)"): THE FACE BROUGHT IN ROUND EACH CANTHUS (REF canthi), phi on the grid
    G in place, both eyes: the field raised by a smooth bump about each profile-rule canthus (canid_hull.canthi_on_rays
    'profile': the cage's tips under EYE face), as deep as puts the canthus `clear` mm under the reference (the lids'
    corner meets the skin there, where W2n's reference stood 6.9 mm out of the lateral canthus and 5.3 out of the medial),
    a gaussian long along the fissure's line away from the other canthus (sigma[0]: the lateral canthal groove back toward
    the ear, the medial notch toward the nose: CANID_HEAD_STUDY 6), shorter toward the eye (sigma[1]) and across
    (sigma[2]); and HELD so the skin stays t_min mm off the skull (canid_cage.skull_ref; the thickness at a grid point
    read as the skull's distance minus the field, the carve smoothly capped by it, k mm): laterally the zygomatic arch's
    dorsal process stands 7.5 mm from the canthus at its height with ~2 mm of skin over it, and it keeps that.
    Returns {canthus: (the depth asked at it, the reference there before, after)} mm"""
    from . import canid_hull as CH
    cv = REF['canthi']
    pro = {k: np.asarray(v, np.float64) for k, v in CH.canthi_on_rays(spec, depth=dict(medial='profile',
                                                                                         lateral='profile')).items()}
    sk = skull_ref(spec, lambda s: None)
    ref0 = Ref(phi, G.lo, G.h)
    out = {}
    for key, other in (('medial', 'lateral'), ('lateral', 'medial')):
        # (W2p, the successor head builder: an optional 4th sigma, ACROSS UPWARD: the bump's spread on the dorsal side of
        # the fissure's line (toward the brow) apart from the rest across (below it and in depth). Medially a bump wide
        # across (12 mm: a shallow groove toward the nose, the lead's call 4) also reached the brow 8 mm over the inner
        # canthus and printed a 0.38 mm ripple on its |x| 26 line at d 128 (w02 _w2p1); narrower upward it stays clear)
        sg4 = tuple(cv[key]['sigma'])
        so_, si_, sx_ = sg4[:3]
        sxu_ = float(sg4[3]) if len(sg4) > 3 else sx_
        for sx in (1.0, -1.0):
            m = np.array([1.0, 1.0, sx])
            p = pro[key] * m
            a = (pro[key] - pro[other]) * m
            a /= np.linalg.norm(a)
            f0 = float(ref0(p[None])[0])
            dep = max(0.0, -f0 - cv[key].get('clear', cv['clear']))
            if dep <= 0.0:
                continue
            reach = 3.0 * max(so_, si_, sx_)
            i0 = np.maximum(np.floor((p - reach - G.lo) / G.h).astype(int), 0)
            i1 = np.minimum(np.ceil((p + reach - G.lo) / G.h).astype(int) + 1, np.array(G.n))
            ax_ = [G.lo[j] + np.arange(i0[j], i1[j]) * G.h for j in range(3)]
            D, Q, X = np.meshgrid(*ax_, indexing='ij')
            W = np.stack([D - p[0], Q - p[1], X - p[2]], -1)
            sa = W @ a
            Wp = W - sa[..., None] * a
            sp = np.linalg.norm(Wp, axis=-1)
            if sxu_ != sx_:
                up_ = np.array([0.0, 1.0, 0.0]) - a[1] * a
                up_ /= np.linalg.norm(up_)
                su = Wp @ up_
                so2 = np.maximum(sp * sp - su * su, 0.0)
                sxs = np.where(su > 0.0, sxu_, sx_)
                K = np.exp(-0.5 * (sa / np.where(sa > 0.0, so_, si_)) ** 2 - 0.5 * su * su / (sxs * sxs)
                           - 0.5 * so2 / (sx_ * sx_))
            else:
                sg = np.where(sa > 0.0, so_, si_)
                K = np.exp(-0.5 * (sa / sg) ** 2 - 0.5 * (sp / sx_) ** 2)
            sub = phi[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
            T = sk(np.stack([D, Q, X], -1).reshape(-1, 3)).reshape(D.shape) - sub
            cap = np.maximum(T - cv['t_min'], 0.0)
            want = dep * K
            car = _smin(want, cap, cv['k'])
            car = np.maximum(car, 0.0)
            sub += car.astype(sub.dtype)
            if sx > 0:
                out[key] = (dep, f0, float(Ref(phi, G.lo, G.h)(p[None])[0]), float((want - car).max()))
    log('[cage] W2o the face brought in round the canthi (REF canthi): '
        + '; '.join(f'{k} {v[0]:.1f} mm asked (the reference there {v[1]:+.1f} -> {v[2]:+.1f} mm; the skull\'s hold took up '
                    f'to {v[3]:.1f})' for k, v in out.items()))
    return out


def eye_relief_edits(phi, G, spec, log=print):
    """W2q (the lead's call 2): THE BROW BROUGHT FORWARD AND THE SKIN UNDER THE EYE BROUGHT IN (REF brow, under_eye), phi
    on the grid G in place, both eyes: the brow's union with the globe offset over its upper arc, the cut of the face
    under the eye back to the target relief along the lids' axis, held off the skull. Returns {item: (the largest move
    mm, voxels touched)}"""
    from scipy import ndimage as nd
    from . import canid_hull as CH
    br, ue = REF.get('brow'), REF.get('under_eye')
    if not br and not ue:
        return {}
    sk = skull_ref(spec, lambda s: None)
    out = {}
    src = phi.copy() if (br and br.get('shift')) else None     # the shift samples the field as it stood
    for sx in (1.0, -1.0):
        lf = CH.lid_frame(spec, 'L' if sx > 0 else 'R')
        c, R = np.asarray(lf['centre'], np.float64), float(lf['R'])
        oo = np.asarray(lf['oo'], np.float64)
        up = np.array([0.0, 1.0, 0.0])
        dor = up - (up @ oo) * oo
        dor /= np.linalg.norm(dor)
        lat = np.cross(dor, oo)
        lat = lat if lat[2] * sx > 0 else -lat
        reach = 3.2 * R
        i0 = np.maximum(np.floor((c - reach - G.lo) / G.h).astype(int), 0)
        i1 = np.minimum(np.ceil((c + reach - G.lo) / G.h).astype(int) + 1, np.array(G.n))
        ax_ = [G.lo[j] + np.arange(i0[j], i1[j]) * G.h for j in range(3)]
        D, Q, X = np.meshgrid(*ax_, indexing='ij')
        W = np.stack([D - c[0], Q - c[1], X - c[2]], -1)
        h = W @ oo
        rr = np.linalg.norm(W, axis=-1)
        rho = np.sqrt(np.maximum(rr * rr - h * h, 0.0))
        az = np.degrees(np.arctan2(W @ lat, W @ dor))                  # 0 dorsal, +- 180 ventral
        pol = np.degrees(np.arccos(np.clip(h / np.maximum(rr, 1e-9), -1.0, 1.0)))
        sub = phi[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
        before = sub.copy()
        if br and br.get('shift'):
            # W2q-3 (the restarted head builder): THE BROW AS THE FACE ITSELF MOVED FORWARD along the lids' axis, each
            # column by amp R (full to rho[0] R off the axis, out to nothing by rho[1] R on the C2 ramp), over the upper
            # arc (az deg: from nothing at az[0] medially to full at az[1] .. az[2], nothing again by az[3] laterally;
            # 0 dorsal), times `gain` by az (pchip through its (az, gain) knots: the face above the eye stands nearer
            # the apex medially than laterally; or `lat`, a gain at az +45 eased to 1 at 0 and +90), in front of h[0] R
            # along the axis (full by h[1]: the head's far side untouched). The face keeps its own shape, moved: the
            # hood (the globe + t, unioned) printed a ball over the eye in profile, a shelf at the apex level out to
            # 1.5-1.8 R and then a 6-9 mm wall down to the face (check_w2q/NOTES.md 23:2x, relief_map)
            sh_ = br['shift']
            r1, r2 = sh_['rho']
            a0, a1, a2, a3 = sh_['az']
            if sh_.get('gain'):
                gk = np.asarray(sh_['gain'], np.float64)
                g_l = pchip(gk[:, 0], gk[:, 1])(np.clip(az, gk[0, 0], gk[-1, 0]))
            else:
                g_l = 1.0 + (sh_.get('lat', 1.0) - 1.0) * np.clip(1.0 - np.abs(az - 45.0) / 45.0, 0.0, 1.0)
            A = (R * sh_['amp'] * (1.0 - smoother01((rho / R - r1) / (r2 - r1)))
                 * smoother01((az - a0) / (a1 - a0)) * smoother01((a3 - az) / (a3 - a2)) * g_l
                 * smoother01((h / R - sh_['h'][0]) / (sh_['h'][1] - sh_['h'][0])))
            m_ = A > 1e-3
            P_ = np.stack([D[m_], Q[m_], X[m_]], -1) - A[m_][:, None] * oo[None]
            sub[m_] = nd.map_coordinates(src, ((P_ - G.lo) / G.h).T, order=1, mode='nearest').astype(sub.dtype)
        if br and (br.get('t', 0.0) > 0.0 or br.get('ext')):
            p0, p1, p2, p3 = br['pol']
            w_pol = smooth01((pol - p0) / (p1 - p0)) * smooth01((p3 - pol) / (p3 - p2))
            w_az = smooth01((br['az'][1] - np.abs(az)) / (br['az'][1] - br['az'][0]))
            t_ = br['t'] * w_pol * w_az
            ex = br.get('ext')
            if ex:
                # the brow's lateral part (REF brow ext): more over the outer half of the upper arc, further out
                e0, e1, e2, e3 = ex['pol']
                ac, af, az0 = ex['az']
                t_ = t_ + ex['t'] * (smooth01((pol - e0) / (e1 - e0)) * smooth01((e3 - pol) / (e3 - e2))
                                     * smooth01((az0 - np.abs(az - ac)) / (az0 - af)))
            hood = np.where(t_ > 0.05, rr - (R + t_), 60.0)
            sub[...] = _smin(sub.astype(np.float64), hood, br['k']).astype(sub.dtype)
        mid = sub.copy()
        if ue:
            rt = np.asarray(ue['rel'], np.float64)
            if ue.get('blend'):
                # W2q-3: the target relief through its knots C1 (pchip), the cut BLENDED in by its weight (the field
                # between uncut and cut by w_): W2q-2's cut plane was pushed 60 (1 - w_) mm in, so the cut went from
                # none to full where 60 (1 - w_) passed the face's few mm over the target (w_ 0.93-0.98): an edge at the
                # az window's rim, and the linear target's knots creased it; the flank line q +10 read it as a 0.35 mm
                # wiggle at d 117-123 (w02 _w2q4's ripple gate; W2p 0.20, the cut's first runs 0.28-0.29)
                h_t = R * (1.0 + pchip(rt[:, 0], rt[:, 1])(np.clip(rho / R, rt[0, 0], rt[-1, 0])))
            else:
                h_t = R * (1.0 + np.interp(rho / R, rt[:, 0], rt[:, 1]))
            r0, r1, r2, r3 = ue['rho']
            w_r = smooth01((rho / R - r0) / (r1 - r0)) * smooth01((r3 - rho / R) / (r3 - r2))
            w_a = smooth01((ue['az'][1] - (180.0 - np.abs(az))) / (ue['az'][1] - ue['az'][0]))
            w_ = w_r * w_a
            T = sk(np.stack([D, Q, X], -1).reshape(-1, 3)).reshape(D.shape)
            if ue.get('blend'):
                cut = np.minimum(h - h_t, T - ue['t_min'])
                full = -_smin(-sub.astype(np.float64), -cut, ue['k'])
                sub[...] = (sub + w_ * (full - sub)).astype(sub.dtype)
            else:
                cut = (h - h_t) - 60.0 * (1.0 - w_)
                cut = np.minimum(cut, T - ue['t_min'])
                sub[...] = (-_smin(-sub.astype(np.float64), -cut, ue['k'])).astype(sub.dtype)
        if sx > 0:
            gain = before - mid
            cutd = sub - mid
            out['brow'] = (float(gain.max()), int((gain > 0.05).sum()))
            out['under_eye'] = (float(cutd.max()), int((cutd > 0.05).sum()))
    log('[cage] W2q the eye\'s relief edits (REF brow, under_eye): ' + '; '.join(
        f'{k} up to {v[0]:.1f} mm on {v[1]:,} voxels' for k, v in out.items()))
    return out


def groove_fill(phi, G, spec, log=print):
    """W2q (the lead's call 4: "re-measure the medial groove after the brow; if still deep, a carve shaped for it"): THE
    MEDIAL GROOVE'S FLOOR RAISED TO ITS TARGET DEPTH (REF canthi medial fill), phi on the grid G in place, both eyes, on
    the finished reference (after canthus_carve and eye_relief_edits). The groove is read as the W2o fresh eyes' notch.py
    reads it: looking down the lids' axis oo, at s mm past the medial tip along the tip-to-tip line made normal to oo (ua)
    the height along oo across the line (u along va = oo x ua, dorsal +); the floor is the least height within 2.5 mm of
    the line, the lips the lower of the highest heights within 8 mm beyond it on each side. Where the floor lies more than
    `target` mm under the lips, the valley's points below lips - target are raised to it within the across band (u mm:
    rising 0 -> 1 over band[0..1], 1 to band[2], 0 by band[3]; the floor lies VENTRAL of the line, u -1.7 .. -0.3 at
    s 0.5-3 on the W2q reference), smoothed `smooth` mm, faded in over s[0..1] (the tip's own pocket kept) and out over
    s[2..3]; the raise moves the surface along oo (the field lowered in a slab of +-slab mm about the surface). The face
    DORSAL of the line is left as it is: the front cameras' rays to the inner canthus leave it dorsally and up (per mm
    past the tip u +0.6..+1.4 and up the axis +1.0..+1.6 mm), grazing the face there (check_w2q corner_vis_q.py).
    Returns {s: (the depth before, the largest raise)} for the left eye"""
    from scipy import ndimage as nd
    from . import canid_hull as CH
    fl = REF['canthi']['medial'].get('fill')
    if not fl:
        return {}
    pro = {k: np.asarray(v, np.float64) for k, v in CH.canthi_on_rays(spec, depth=dict(medial='profile',
                                                                                         lateral='profile')).items()}
    lfL = CH.lid_frame(spec, 'L')
    s0, s1, s2, s3 = fl['s']
    b0, b1, b2, b3 = fl['band']
    hs = 0.25
    S_ = np.arange(-0.5, s3 + 1.0 + 1e-9, hs)
    U_ = np.arange(-12.0, 12.0 + 1e-9, hs)
    H_ = np.arange(16.0, -8.0 - 1e-9, -0.1)
    out = {}
    for sx in (1.0, -1.0):
        m = np.array([1.0, 1.0, sx])
        p = pro['medial'] * m
        oo = np.asarray(lfL['oo'], np.float64) * m
        a = (pro['medial'] - pro['lateral']) * m
        ua = a - (a @ oo) * oo
        ua /= np.linalg.norm(ua)
        va = np.cross(oo, ua)
        va *= 1.0 if va[1] >= 0 else -1.0
        reach = np.abs(np.stack([ua, va, oo])).T @ np.array([s3 + 1.5, 12.5, 17.0])
        i0 = np.maximum(np.floor((p - reach - G.lo) / G.h).astype(int), 0)
        i1 = np.minimum(np.ceil((p + reach - G.lo) / G.h).astype(int) + 1, np.array(G.n))
        sub = phi[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]

        def field(P):
            c = (P.reshape(-1, 3) - G.lo) / G.h - i0
            return nd.map_coordinates(sub, c.T, order=1, mode='nearest').reshape(P.shape[:-1])
        # the height map: the first crossing coming in along -oo
        Ss, Uu, Hh = np.meshgrid(S_, U_, H_, indexing='ij')
        f = field(p + Ss[..., None] * ua + Uu[..., None] * va + Hh[..., None] * oo)
        inside = f < 0.0
        k = np.argmax(inside, axis=2)
        ok = inside.any(axis=2) & (k > 0)
        kk = np.maximum(k, 1)
        f_in = np.take_along_axis(f, kk[..., None], 2)[..., 0]
        f_out = np.take_along_axis(f, (kk - 1)[..., None], 2)[..., 0]
        t_ = f_out / np.maximum(f_out - f_in, 1e-9)
        Hm = np.where(ok, H_[kk - 1] - 0.1 * t_, np.nan)
        dlt = np.zeros_like(Hm)
        for i, s in enumerate(S_):
            w_s = float(smooth01((s - s0) / (s1 - s0)) * smooth01((s3 - s) / (s3 - s2)))
            row = Hm[i]
            cc = np.isfinite(row) & (np.abs(U_) <= 2.5)
            if w_s <= 0.0 or not cc.any():
                continue
            j = int(np.argmin(np.where(cc, row, np.inf)))
            u_k = U_[j]
            up_ = np.isfinite(row) & (U_ > u_k + 0.05) & (U_ <= u_k + 8.0)
            lo_ = np.isfinite(row) & (U_ < u_k - 0.05) & (U_ >= u_k - 8.0)
            if not (up_.any() and lo_.any()):
                continue
            lips = min(row[up_].max(), row[lo_].max())
            band = smooth01((U_ - b0) / (b1 - b0)) * smooth01((b3 - U_) / (b3 - b2))
            want = np.where(np.isfinite(row), np.maximum(lips - fl['target'] - row, 0.0), 0.0) * band * w_s
            dlt[i] = want
            if sx > 0 and abs(s - round(s)) < 1e-6 and 0.0 <= s <= s3:
                out[float(s)] = (float(lips - row[j]), float(want.max()))
        dlt = nd.gaussian_filter(dlt, fl['smooth'] / hs)
        Hf = np.where(np.isfinite(Hm), Hm, 0.0)
        # carried onto the grid: each voxel's (s, u, h) in the frame, the raise there in a slab about the surface
        ax_ = [G.lo[j] + np.arange(i0[j], i1[j]) * G.h for j in range(3)]
        D, Q, X = np.meshgrid(*ax_, indexing='ij')
        W = np.stack([D - p[0], Q - p[1], X - p[2]], -1)
        sv, uv, hv = W @ ua, W @ va, W @ oo
        cs = np.stack([(sv - S_[0]) / hs, (uv - U_[0]) / hs], 0).reshape(2, -1)
        dv = nd.map_coordinates(dlt, cs, order=1, mode='constant', cval=0.0).reshape(sv.shape)
        hsf = nd.map_coordinates(Hf, cs, order=1, mode='nearest').reshape(sv.shape)
        w_h = smooth01((fl['slab'] + 1.5 - np.abs(hv - hsf)) / 1.5)
        sub -= (dv * w_h).astype(sub.dtype)
    log('[cage] W2q the medial groove\'s floor raised to ' + f'{fl["target"]:.1f} mm under its lips (REF canthi medial '
        'fill): ' + ', '.join(f's {s:.0f}: {v[0]:.2f} deep, raised up to {v[1]:.2f}' for s, v in sorted(out.items())))
    return out


def groove_carve(phi, G, spec, log=print):
    """W2q-3 (the lead's call 4: "re-measure the medial groove after the brow; if still deep, a carve shaped for it"):
    THE MEDIAL GROOVE'S DORSAL FLANK CARVED (REF canthi medial carve), phi on the grid G in place, both eyes, on the
    finished reference. notch.py reads the groove past the medial tip against the lower of its two lips within 8 mm, and
    after the brow that is the DORSAL lip (the brow's medial end); the front cameras' rays to the inner canthus leave it
    dorsally (check_w2q corner_vis_q.py), so carving that flank keeps the canthus in view, where raising the floor hid
    it (groove_fill). In the medial tip's frame (s along the tip-to-tip line made normal to the lids' axis oo, past the
    tip toward the nose; u = oo x s, dorsal; h along oo) each column moves back along oo by c mm x ramp(s) x ramp(u)
    (each `s` / `u` a C2 ramp up over [0..1], full to [2], none by [3]), in front of h[0] mm (full by h[1]).
    Returns the left eye's largest move (mm) and the voxels moved"""
    from scipy import ndimage as nd
    from . import canid_hull as CH
    cv = REF['canthi']['medial'].get('carve')
    if not cv:
        return {}
    pro = {k: np.asarray(v, np.float64) for k, v in CH.canthi_on_rays(spec, depth=dict(medial='profile',
                                                                                         lateral='profile')).items()}
    lfL = CH.lid_frame(spec, 'L')
    src = phi.copy()
    s0, s1, s2, s3 = cv['s']
    u0, u1, u2, u3 = cv['u']
    out = {}
    for sx in (1.0, -1.0):
        m = np.array([1.0, 1.0, sx])
        p = pro['medial'] * m
        oo = np.asarray(lfL['oo'], np.float64) * m
        a = (pro['medial'] - pro['lateral']) * m
        ua = a - (a @ oo) * oo
        ua /= np.linalg.norm(ua)
        va = np.cross(oo, ua)
        va *= 1.0 if va[1] >= 0 else -1.0
        reach = np.abs(np.stack([ua, va, oo])).T @ np.array([max(abs(s0), s3) + 1.0, u3 + 1.0, 30.0])
        i0 = np.maximum(np.floor((p - reach - G.lo) / G.h).astype(int), 0)
        i1 = np.minimum(np.ceil((p + reach - G.lo) / G.h).astype(int) + 1, np.array(G.n))
        ax_ = [G.lo[j] + np.arange(i0[j], i1[j]) * G.h for j in range(3)]
        D, Q, X = np.meshgrid(*ax_, indexing='ij')
        W = np.stack([D - p[0], Q - p[1], X - p[2]], -1)
        sv, uv, hv = W @ ua, W @ va, W @ oo
        c_ = (cv['c'] * smoother01((sv - s0) / (s1 - s0)) * smoother01((s3 - sv) / (s3 - s2))
              * smoother01((uv - u0) / (u1 - u0)) * smoother01((u3 - uv) / (u3 - u2))
              * smoother01((hv - cv['h'][0]) / (cv['h'][1] - cv['h'][0])))
        m_ = c_ > 1e-3
        sub = phi[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
        P_ = np.stack([D[m_], Q[m_], X[m_]], -1) + c_[m_][:, None] * oo[None]
        sub[m_] = nd.map_coordinates(src, ((P_ - G.lo) / G.h).T, order=1, mode='nearest').astype(sub.dtype)
        if sx > 0:
            out = dict(c=float(c_.max()), voxels=int(m_.sum()))
    log(f'[cage] W2q-3 the medial groove\'s dorsal flank carved (REF canthi medial carve): up to {out.get("c", 0):.2f} mm '
        f'on {out.get("voxels", 0):,} voxels')
    return out


def bridge_width(phi, G, d):
    """the reference's half width per height at station d (phi on the grid G): a callable q -> |x| of the section's
    outward crossing from the midline (0 where the midline is outside), from its 0.25 mm samples (canid_nose's arch)"""
    f = (d - G.lo[0]) / G.h
    i0 = int(np.clip(np.floor(f), 0, G.n[0] - 2))
    w = f - i0
    sl = (1.0 - w) * phi[i0] + w * phi[i0 + 1]
    qs = G.lo[1] + np.arange(G.n[1]) * G.h
    xs = G.lo[2] + np.arange(G.n[2]) * G.h
    j0 = int(np.argmin(np.abs(xs)))
    half = np.zeros(len(qs))
    for a in range(len(qs)):
        row = sl[a, j0:]
        if row[0] >= 0.0:
            continue
        out = np.nonzero(row >= 0.0)[0]
        if not len(out):
            continue
        b = out[0]
        half[a] = xs[j0 + b - 1] + G.h * row[b - 1] / (row[b - 1] - row[b])
    return lambda q_: np.interp(q_, qs, half)


def _smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def reference(spec, log=print):
    """THE REFERENCE (REF): W2i's skin over the skull blended into its flowed head (canid_hull.head_volume's phi before
    sculpt_skull), gaussian-smoothed (sigma; more over the cheek, the orbit and the cranium), the muzzle's flank filled
    behind the canines (REF flank), the nose's cap unioned (W2l: canid_nose.cap_field, RHINARIUM k); cached"""
    from scipy import ndimage as nd
    from . import canid_hull as CH, canid_nose as CN, canid_skin as CK
    from ..hullflow import Grid, cache_key, cached
    # (W2k: the flow stage by canid_hull.flow_stage under its shared key, which holds the clay's visible eyes: W2j built it
    # on a miss as canid_hull.head_volume(spec)['closed'], the sculpted W2i head, under the flow's own file name)
    key_flow = CH.flow_key(spec)
    # (W2o: the canthus carve reads the profile-rule canthi and the skull: their values join the key)
    from . import canid_skull as SK
    can_ = CH.canthi_on_rays(spec, depth=dict(medial='profile', lateral='profile'))
    key = cache_key(dict(v=REF_VERSION, flow=key_flow, skin=CH._skin_key(spec), blend=CH.STROKES_SKULL['blend'], ref=REF,
                         rh=CN.RHINARIUM, prof=CH.PROFILE, top=CH.TOP,
                         canthi={k: np.round(np.asarray(v, float), 2).tolist() for k, v in can_.items()},
                         skull=SK.skull_key(spec)))

    def build():
        t0 = time.time()
        Fz = CH.flow_stage(spec, log)
        G = Grid(Fz['lo'], Fz['lo'] + (np.array(Fz['phi'].shape) - 1) * float(Fz['h']), float(Fz['h']))
        Sk = CK.skin_volume(spec, tuple(G.lo), tuple(G.lo + (np.array(G.n) - 1) * G.h), G.h, log)
        pre = CH.blend_behind(Sk['phi'], Fz['phi'], G).astype(np.float64)
        phi = nd.gaussian_filter(pre, REF['sigma'] / G.h)
        D, Q, X = G.mesh()
        for nm_ in ('cheek', 'orbit', 'cranium'):
            ch = REF[nm_]
            w = (smooth01((D - ch['d'][0]) / (ch['d'][1] - ch['d'][0])) * smooth01((ch['d'][3] - D) / (ch['d'][3] - ch['d'][2]))
                 * smooth01((Q - ch['q'][0]) / (ch['q'][1] - ch['q'][0])) * smooth01((ch['q'][3] - Q) / (ch['q'][3] - ch['q'][2]))
                 * smooth01((np.abs(X) - ch['x']) / 6.0))
            phi_c = nd.gaussian_filter(pre, ch['sigma'] / G.h)
            phi = (1.0 - w) * phi + w * phi_c
        # W2k fresh eyes: the muzzle's flank filled behind the canines (REF flank: the waist from above)
        fill = fill_flank(phi, G)
        # W2o: the face brought in round the canthi (REF canthi: the lids' corners meet the skin)
        canthus_carve(phi, G, spec, log)
        # W2q: the brow forward over the globe's upper part, the skin under the eye in (REF brow, under_eye)
        eye_relief_edits(phi, G, spec, log)
        # W2q: the medial groove's floor raised to its target depth (REF canthi medial fill)
        groove_fill(phi, G, spec, log)
        # W2q-3: the medial groove's dorsal flank carved (REF canthi medial carve)
        groove_carve(phi, G, spec, log)
        # W2l: THE NOSE'S CAP (canid_nose): the leather lofted on the clay's own frame, morphing into this skin's arch
        cap = CN.cap_field(phi, G, log)
        phi = _smin(phi, cap.astype(np.float64), CN.RHINARIUM['k'])
        # W2u: THE NOSTRIL'S SEAT (canid_nose.seat_carve, RHINARIUM seat) carved into the union: each nostril set back on
        # the pad's front-lateral corner (the skin follows the same PROFILE / TOP as the cap, so the cap alone can't)
        if CN.RHINARIUM.get('seat'):
            phi = CN.seat_carve(phi, G, log)
        log(f'[cage] the reference: W2i\'s pre-feature skin smoothed {REF["sigma"]} mm (the cheek {REF["cheek"]["sigma"]}, the '
            f'orbit {REF["orbit"]["sigma"]}, the cranium {REF["cranium"]["sigma"]}), the muzzle\'s flank filled behind '
            f'the canines (at most {fill:.1f} mm at d {REF["flank"]["dc"]:.0f}), the nose\'s cap unioned (k '
            f'{CN.RHINARIUM["k"]}); in {time.time() - t0:.0f}s')
        return dict(phi=phi.astype(np.float32), lo=G.lo, h=np.float64(G.h))
    Z = cached('canid_cage_ref', key, build, log)
    return Ref(Z['phi'], Z['lo'], float(Z['h']))


def skull_ref(spec, log=print):
    """the skull's signed distance (canid_skull.skull_volume at 0.5 mm, cached) as a Ref (mm, negative inside the bone)"""
    from . import canid_skull as SK
    Z = SK.skull_volume(spec, 0.5, log)
    return Ref(Z['phi'], Z['lo'], float(Z['h']))


# ============================================================================================ the topology
class Topo:
    """the half cage's index structure (insect_cage's scheme) with the nostril's and the eye's tubes inserted; the full
    mesh mirrored and welded on the midline"""

    def __init__(self):
        L = LAYOUT
        self.nA, self.K = L['nA'], L['K']
        self.nB = len(L['stations']) - 1
        nA, nB, K = self.nA, self.nB, self.K
        self.M = M = 2 * nA + nB + 1
        self.T = np.arange((nA + 1) * (nB + 1)).reshape(nA + 1, nB + 1)
        cnt = self.T.size
        self.R = np.full((K + 1, M), -1, int)
        for i in range(M):
            self.R[0, i] = self.boundary(self.T, i)
        for k in range(1, K):
            self.R[k] = cnt + np.arange(M)
            cnt += M
        self.B = cnt + np.arange((nA + 1) * (nB + 1)).reshape(nA + 1, nB + 1)
        cnt += self.B.size
        for i in range(M):
            self.R[K, i] = self.boundary(self.B, i)
        Q = []
        for a in range(nA):
            for b in range(nB):
                Q.append((self.T[a, b], self.T[a + 1, b], self.T[a + 1, b + 1], self.T[a, b + 1]))
        self.q_ring0 = len(Q)
        for k in range(K):
            for i in range(M - 1):
                Q.append((self.R[k, i], self.R[k + 1, i], self.R[k + 1, i + 1], self.R[k, i + 1]))
        for a in range(nA):
            for b in range(nB):
                Q.append((self.B[a, b], self.B[a, b + 1], self.B[a + 1, b + 1], self.B[a + 1, b]))
        self.Qh = np.array(Q, int)
        self.n_half = cnt
        self.loops = {}
        self.sharp_h = {}
        # THE TUBES: each inserted between its square ring (the RIM) and the quads it encloses
        self.rim, self.rim_cells, self.tubes, self.inner = {}, {}, {}, {}
        (i0, i1), (k0, k1) = L['nose_i'], L['nose_k']
        self._tube('nostril', i0, i1, k0, k1)
        (b0, b1), (k0, k1) = L['eye_b'], L['eye_k']
        self._tube('eye', nA + b0, nA + b1, k0, k1)
        # W2y: THE EAR's port (place_ear)
        (b0, b1), (k0, k1) = L['ear_b'], L['ear_k']
        self._tube('ear', nA + b0, nA + b1, k0, k1)
        # (the BACK CAP's quads, the rings' back segments behind the last station: the low cuts them, the neck's seam)
        self.back_cap_q = np.array([self.q_ring0 + k * (M - 1) + i for k in range(K) for i in range(nA + nB, M - 1)], int)
        # W2k: THE LEATHER's own loops, an OPEN tube inside the U of face-cap cells round it (LAYOUT leather_*), its ends on
        # the midline (module docstring, LEATHER)
        self.mid_extra = []
        self._open_tube('leather', L['leather_i'], *L['leather_k'], len(L['tubes']['leather']))

    def _tube(self, name, i0, i1, k0, k1):
        M = self.M
        cells = self.square_ring(i0, i1, k0, k1)
        self.rim_cells[name] = cells
        self.rim[name] = [int(self.R[k, i]) for (i, k) in cells]
        inner_q = [self.q_ring0 + k * (M - 1) + i for k in range(k0, k1) for i in range(i0, i1)]
        self.inner[name] = [int(self.R[k, i]) for k in range(k0 + 1, k1) for i in range(i0 + 1, i1)]
        self.inner_cells = getattr(self, 'inner_cells', {})
        self.inner_cells[name] = [(i, k) for k in range(k0 + 1, k1) for i in range(i0 + 1, i1)]
        self.tubes[name] = self.insert_tube(self.rim[name], inner_q, len(LAYOUT['tubes'][name]))

    def _open_tube(self, name, il, kt, kb, n):
        """W2k: n rings inside the U of face-cap vertices round the leather (row kt from the midline out to column il, down
        column il, back along row kb to the midline) and the leather's interior quads (columns 0 .. il - 1, rows kt ..
        kb - 1, the nostril's tube among them); every ring's ends are midline vertices (the mirror shares them)"""
        rim = [int(self.R[kt, i]) for i in range(il + 1)] + [int(self.R[k, il]) for k in range(kt + 1, kb)] + \
              [int(self.R[kb, i]) for i in range(il, -1, -1)]
        inner_q = [self.q_ring0 + k * (self.M - 1) + i for k in range(kt, kb) for i in range(il)]
        rings = self.insert_open_tube(rim, inner_q, n)
        self.rim[name] = rim
        self.tubes[name] = rings
        self.mid_extra += [r[0] for r in rings] + [r[-1] for r in rings]
        self.leather_u = dict(il=il, kt=kt, kb=kb, m=len(rim), j_tl=il, j_bl=il + (kb - kt))

    def insert_open_tube(self, rim, inner_quads, n):
        """insert_tube for an OPEN polyline `rim` (its ends not joined): n new rings, each as long as the rim, between it
        and the quads `inner_quads` inside it (their rim vertices moved to the innermost ring), quad strips between;
        returns the rings' vertex ids [ring 1 .. n]"""
        m = len(rim)
        rings = []
        for t in range(n):
            rings.append(list(range(self.n_half, self.n_half + m)))
            self.n_half += m
        pos = {v: j for j, v in enumerate(rim)}
        Qh = self.Qh.copy()
        dirs = {}
        for qi in inner_quads:
            q = Qh[qi]
            for c in range(4):
                a, b = int(q[c]), int(q[(c + 1) % 4])
                if a in pos and b in pos:
                    ja, jb = pos[a], pos[b]
                    if jb - ja == 1:
                        dirs[ja] = True              # the inner quad runs rim[ja] -> rim[ja + 1]
                    elif ja - jb == 1:
                        dirs[jb] = False
        assert len(dirs) == m - 1, f'the open rim\'s edges in the inner quads: {len(dirs)} of {m - 1}'
        last = rings[-1]
        for qi in set(inner_quads):
            Qh[qi] = [last[pos[int(v)]] if int(v) in pos else int(v) for v in Qh[qi]]
        new = []
        chain = [list(rim)] + rings
        for A, Bv in zip(chain[:-1], chain[1:]):
            for j in range(m - 1):
                if dirs[j]:
                    new.append((A[j], A[j + 1], Bv[j + 1], Bv[j]))
                else:
                    new.append((A[j + 1], A[j], Bv[j], Bv[j + 1]))
        self.Qh = np.vstack([Qh, np.array(new, int)])
        return rings

    def boundary(self, G, i):
        nA, nB = self.nA, self.nB
        if i <= nA:
            return G[i, 0]
        if i <= nA + nB:
            return G[nA, i - nA]
        return G[2 * nA + nB - i, nB]

    @staticmethod
    def square_ring(i0, i1, k0, k1):
        """the (i, k) cells round a square ring, in order (insect_cage's): along k0 (i rising), down i1, back along k1,
        up i0"""
        return [(i, k0) for i in range(i0, i1)] + [(i1, k) for k in range(k0, k1)] + \
               [(i, k1) for i in range(i1, i0, -1)] + [(i0, k) for k in range(k1, k0, -1)]

    def insert_tube(self, rim, inner_quads, n):
        """n new rings between the closed loop `rim` and the quads `inner_quads` inside it (their rim vertices moved to
        the innermost ring), quad strips between; returns the rings' vertex ids [ring 1 .. n]"""
        m = len(rim)
        rings = []
        for t in range(n):
            rings.append(list(range(self.n_half, self.n_half + m)))
            self.n_half += m
        pos = {v: j for j, v in enumerate(rim)}
        Qh = self.Qh.copy()
        inner_set = set(inner_quads)
        dirs = {}
        for qi in inner_quads:
            q = Qh[qi]
            for c in range(4):
                a, b = int(q[c]), int(q[(c + 1) % 4])
                if a in pos and b in pos:
                    ja, jb = pos[a], pos[b]
                    if (jb - ja) % m == 1:
                        dirs[ja] = True              # the inner quad runs rim[ja] -> rim[ja + 1]
                    elif (ja - jb) % m == 1:
                        dirs[jb] = False
        assert len(dirs) == m, f'the rim\'s edges in the inner quads: {len(dirs)} of {m}'
        last = rings[-1]
        for qi in inner_set:
            Qh[qi] = [last[pos[int(v)]] if int(v) in pos else int(v) for v in Qh[qi]]
        new = []
        chain = [list(rim)] + rings
        for A, Bv in zip(chain[:-1], chain[1:]):
            for j in range(m):
                j1 = (j + 1) % m
                if dirs[j]:
                    new.append((A[j], A[j1], Bv[j1], Bv[j]))
                else:
                    new.append((A[j1], A[j], Bv[j], Bv[j1]))
        self.Qh = np.vstack([Qh, np.array(new, int)])
        return rings

    def midline(self):
        ids = set(self.T[0, :].tolist()) | set(self.B[0, :].tolist()) | set(self.R[:, 0].tolist()) | \
            set(self.R[:, -1].tolist()) | set(getattr(self, 'mid_extra', []))
        return np.array(sorted(ids), int)

    def crease(self, ids, s, closed=False):
        ids = list(ids)
        pairs = list(zip(ids[:-1], ids[1:])) + ([(ids[-1], ids[0])] if closed else [])
        ss = np.broadcast_to(np.asarray(s, np.float64), (len(pairs),))
        for (a, b), v in zip(pairs, ss):
            if v > 0:
                self.sharp_h[(min(a, b), max(a, b))] = float(v)

    def adjacency(self):
        """the half cage's vertex adjacency (sparse, symmetric, 0/1)"""
        import scipy.sparse as sp
        E = np.concatenate([self.Qh[:, [0, 1]], self.Qh[:, [1, 2]], self.Qh[:, [2, 3]], self.Qh[:, [3, 0]]])
        E = np.unique(np.sort(E, axis=1), axis=0)
        n = self.n_half
        return sp.csr_matrix((np.ones(2 * len(E)), (np.concatenate([E[:, 0], E[:, 1]]), np.concatenate([E[:, 1], E[:, 0]]))),
                             shape=(n, n))

    def full(self, P_half):
        """the full mesh (the half and its mirror x -> -x, welded on the midline): QuadMesh, the half -> mirror map, the
        full sharpness dict"""
        mid = self.midline()
        is_mid = np.zeros(self.n_half, bool)
        is_mid[mid] = True
        off = np.cumsum(~is_mid) - 1 + self.n_half
        mir = np.where(is_mid, np.arange(self.n_half), off)
        n = self.n_half + int((~is_mid).sum())
        V = np.zeros((n, 3))
        V[:self.n_half] = P_half
        V[mid, 2] = 0.0
        Pm = np.asarray(P_half, np.float64).copy()
        Pm[:, 2] *= -1.0
        V[mir[~is_mid]] = Pm[~is_mid]
        Q = np.vstack([self.Qh, mir[self.Qh][:, ::-1]])
        sharp = {}
        for (a, b), s in self.sharp_h.items():
            sharp[(min(a, b), max(a, b))] = s
            sharp[(min(mir[a], mir[b]), max(mir[a], mir[b]))] = s
        return QuadMesh(V, Q), mir, sharp


def ring_angles(cells, i0, i1, k0, k1):
    """each square-ring cell's spoke angle (rad) in a chart whose +u runs with i and +v against k (k counts down): the
    four sides a quarter turn each, the corners at 135, 45, -45 and -135 deg (the first side, along k0, from 135 to 45)"""
    ni, nk = i1 - i0, k1 - k0
    out = []
    for (i, k) in cells:
        if k == k0 and i < i1:
            a = 135.0 - 90.0 * (i - i0) / ni
        elif i == i1 and k < k1:
            a = 45.0 - 90.0 * (k - k0) / nk
        elif k == k1 and i > i0:
            a = -45.0 - 90.0 * (i1 - i) / ni
        else:
            a = -135.0 - 90.0 * (k1 - k) / nk
        out.append(np.radians(a))
    return np.array(out)


# ============================================================================================ the placement
class Cage:
    """the cage's TARGETS (the limit surface is fitted to them), their sources, the fixed (feature) flags"""

    def __init__(self, topo):
        self.t = topo
        self.P = np.full((topo.n_half, 3), np.nan)
        self.fixed = np.zeros(topo.n_half, bool)
        self.src = {}

    def put(self, v, p, tag, fix=True):
        self.P[v] = p
        self.fixed[v] = fix
        self.src[int(v)] = tag


def station_contours(ref, stations):
    return [ref.section(d) for d in stations]


def at_arc(C, s):
    """the section C's point (q, x) at arc length s (clamped)"""
    t = np.arange(len(C)) * 0.25
    return np.array([np.interp(s, t, C[:, 0]), np.interp(s, t, C[:, 1])])


def arc_of_q(C, q, s_from):
    """the arc length of the first point at or below height q along the section after s_from (going down the side)"""
    t = np.arange(len(C)) * 0.25
    j0 = int(np.searchsorted(t, s_from))
    below = np.nonzero(C[j0:, 0] <= q)[0]
    if not len(below):
        return t[-1]
    j = j0 + below[0]
    if j == 0:
        return 0.0
    a, b = C[j - 1, 0], C[j, 0]
    w = (a - q) / (a - b) if a != b else 0.0
    return t[j - 1] + w * 0.25


def place_stations(C, ref, cons, log=print):
    """the TOP patch, the SIDE segments and the BOTTOM patch at every station: each station's section by arc length from
    the top midline: the top patch's columns to E1, the rings between E1 and E2 by anchors (the lip's margin on LIP_LINE
    to the commissure, behind it easing to 0.62 of the side), the bottom patch's columns from E2 to the bottom midline.
    The eye's rim is laid later in its own chart (place_eye) and the side relaxed round it"""
    from . import canid_hull as CH
    t = C.t
    L = LAYOUT
    nA, nB, K = t.nA, t.nB, t.K
    st = np.asarray(L['stations'])
    s1f = pchip(E_LINES['d'], E_LINES['s1'])
    s2f = pchip(E_LINES['d'], E_LINES['s2'])
    ll = np.asarray(CH.LIP_LINE, np.float64)
    d_comm = float(ll[-1, 0])
    lk = L['lip_k']
    frac_lip_comm = None
    rows = {}
    for b, d in enumerate(st):
        Cs = cons[b]
        stot = (len(Cs) - 1) * 0.25
        s1, s2 = float(s1f(d)), stot - float(s2f(d))
        anchors = {0: s1, K: s2}
        if d <= d_comm + 1e-9:
            anchors[lk] = arc_of_q(Cs, float(np.interp(d, ll[:, 0], ll[:, 1])), s1 + 2.0)
        else:
            if frac_lip_comm is None:
                frac_lip_comm = rows[b - 1]['frac_lip']
            fr_ = frac_lip_comm + (0.62 - frac_lip_comm) * smooth01((d - d_comm) / 60.0)
            anchors[lk] = s1 + fr_ * (s2 - s1)
        ks = sorted(anchors)
        sk = np.interp(np.arange(K + 1), ks, [anchors[k] for k in ks])
        rows[b] = dict(frac_lip=(anchors[lk] - s1) / max(s2 - s1, 1e-9))
        for k in range(K + 1):
            q_, x_ = at_arc(Cs, sk[k])
            v = t.R[k, nA + b]
            tag = 'E1 (the top patch\'s edge): E_LINES s1' if k == 0 else 'E2 (the bottom patch\'s edge): E_LINES s2' \
                if k == K else 'the lip\'s margin on LIP_LINE (the profile photos\' mouth line)' if (k == lk and d <= d_comm) \
                else f'ring {k} on the station\'s section (the reference), by arc length between anchors'
            C.put(v, (d, q_, x_), tag, fix=(k == lk and d <= d_comm))
        for a in range(1, nA):
            q_, x_ = at_arc(Cs, s1 * a / nA)
            C.put(t.T[a, b], (d, q_, x_), 'the top patch on the station\'s section (the reference)', fix=False)
            q_, x_ = at_arc(Cs, stot - (stot - s2) * a / nA)
            C.put(t.B[a, b], (d, q_, x_), 'the bottom patch on the station\'s section (the reference)', fix=False)
        q_, x_ = at_arc(Cs, 0.0)
        C.put(t.T[0, b], (d, q_, 0.0), 'the top midline (the reference\'s section)', fix=False)
        q_, x_ = at_arc(Cs, stot)
        C.put(t.B[0, b], (d, q_, 0.0), 'the bottom midline (the reference\'s section)', fix=False)
    log(f'[cage] the {nB + 1} stations placed (d {st[0]:.0f} .. {st[-1]:.0f})')


def midline_curve(ref, d_front_limit, top_q, bot_q, d0):
    """the reference's MIDLINE in front of the station d0 (x 0): from (d0, top) forward round the nose to (d0, bottom),
    (k, 2) (d, q) by 0.25 mm: rays in the midline plane from a centre inside the muzzle"""
    c = np.array([d0 + 6.0, 0.5 * (top_q + bot_q), 0.0])
    ang = np.radians(np.linspace(-89.0, 269.0, 1433))
    D = np.column_stack([-np.cos(ang), np.sin(ang), np.zeros_like(ang)])      # 0 deg forward (-d), 90 up
    P = ref.cross(np.tile(c, (len(D), 1)), D, reach=60.0, step=0.2, outward=True)
    ok = np.isfinite(P).all(1)
    P = P[ok]
    # keep the run in front of d0 from the top crossing to the bottom one
    a0 = int(np.argmin(np.abs(P[:, 0] - d0) + 1e3 * (P[:, 1] < c[1])))
    a1 = int(np.argmin(np.abs(P[:, 0] - d0) + 1e3 * (P[:, 1] > c[1])))
    seg = P[min(a0, a1):max(a0, a1) + 1]
    if seg[0, 1] < seg[-1, 1]:
        seg = seg[::-1]
    H = seg[:, :2]
    s = arclen(H)
    tt = np.arange(0.0, s[-1], 0.25)
    return np.column_stack([np.interp(tt, s, H[:, 0]), np.interp(tt, s, H[:, 1])])


def place_face_cap(C, ref, mid, anchors_s, log=print):
    """THE FACE CAP (the rings' front segments, i 0 .. nA, k 0 .. K): the midline column on the reference's midline by
    arc length (anchors_s: row -> arc length), the boundary the first station's section (placed), the interior a Coons
    patch of its four sides carried onto the reference by rays from a centre inside the muzzle"""
    t = C.t
    nA, K = t.nA, t.K
    tm = np.arange(len(mid)) * 0.25
    ks = sorted(anchors_s)
    sk = np.interp(np.arange(K + 1), ks, [anchors_s[k] for k in ks])
    for k in range(1, K):
        d_, q_ = np.interp(sk[k], tm, mid[:, 0]), np.interp(sk[k], tm, mid[:, 1])
        C.put(t.R[k, 0], (d_, q_, 0.0), 'the face cap\'s midline on the reference\'s midline (arc length by anchors)',
              fix=True)
    Pm = np.array([C.P[t.R[k, 0]] for k in range(K + 1)])
    Pc = np.array([C.P[t.R[k, nA]] for k in range(K + 1)])
    Pt = np.array([C.P[t.R[0, i]] for i in range(nA + 1)])
    Pb = np.array([C.P[t.R[K, i]] for i in range(nA + 1)])
    cen = np.array([LAYOUT['stations'][0] + 8.0, -6.0, 0.0])
    for k in range(1, K):
        for i in range(1, nA):
            u, v = i / nA, k / K
            p = (1 - u) * Pm[k] + u * Pc[k] + (1 - v) * Pt[i] + v * Pb[i] - \
                ((1 - u) * (1 - v) * Pm[0] + u * (1 - v) * Pc[0] + (1 - u) * v * Pm[K] + u * v * Pc[K])
            dv = p - cen
            q = ref.cross(cen[None], dv[None], reach=80.0, step=0.2)[0]
            if not np.isfinite(q).all():
                q = ref.project(p[None])[0]
            C.put(t.R[k, i], q, 'the face cap (a Coons patch of its sides onto the reference)', fix=False)
    log('[cage] the face cap placed')


def place_back_cap(C, ref, log=print):
    """THE BACK CAP (the rings' back segments; buried in the neck): a Coons patch of its sides onto the reference by rays
    from a centre inside the head"""
    t = C.t
    nA, nB, K, M = t.nA, t.nB, t.K, t.M
    iB = list(range(nA + nB, M))                    # i nA + nB (the last station's side) .. 2 nA + nB (the back midline)
    d_last = LAYOUT['stations'][-1]
    cen = np.array([d_last - 30.0, 20.0, 0.0])
    # the back midline: rays in the midline plane from the centre, from the last station's top round to its bottom
    top, bot = C.P[t.T[0, nB]], C.P[t.B[0, nB]]
    a_t = np.arctan2(top[1] - cen[1], top[0] - cen[0])
    a_b = np.arctan2(bot[1] - cen[1], bot[0] - cen[0])
    if a_b > a_t:
        a_b -= 2 * np.pi
    angs = np.linspace(a_t, a_b, 400)
    D = np.column_stack([np.cos(angs), np.sin(angs), np.zeros_like(angs)])
    Pm = ref.cross(np.tile(cen, (len(D), 1)), D, reach=90.0, step=0.25)
    ok = np.isfinite(Pm).all(1)
    Pm = Pm[ok]
    Pm = np.vstack([top, Pm, bot])
    Pk = resample(Pm, K + 1)
    for k in range(1, K):
        C.put(t.R[k, M - 1], (Pk[k, 0], Pk[k, 1], 0.0), 'the back midline (the reference; buried in the neck)', fix=False)
    Pmid = np.array([C.P[t.R[k, M - 1]] for k in range(K + 1)])
    Pside = np.array([C.P[t.R[k, nA + nB]] for k in range(K + 1)])
    Pt = np.array([C.P[t.R[0, i]] for i in iB])
    Pb = np.array([C.P[t.R[K, i]] for i in iB])
    for k in range(1, K):
        for jj in range(1, nA):
            i = iB[jj]
            u, v = jj / nA, k / K                   # u 0 at the side, 1 at the midline
            p = (1 - u) * Pside[k] + u * Pmid[k] + (1 - v) * Pt[jj] + v * Pb[jj] - \
                ((1 - u) * (1 - v) * Pside[0] + u * (1 - v) * Pmid[0] + (1 - u) * v * Pside[K] + u * v * Pmid[K])
            q = ref.cross(cen[None], (p - cen)[None], reach=90.0, step=0.25)[0]
            if not np.isfinite(q).all():
                q = ref.project(p[None])[0]
            C.put(t.R[k, i], q, 'the back cap (a Coons patch onto the reference; buried in the neck)', fix=False)
    log('[cage] the back cap placed')


def relax(C, ref, iters=None, lam=None, only=None):
    """Laplacian smoothing of the free vertices (those in `only`, default all), each step re-projected onto the reference
    (over the placed neighbours only); the midline's x held at 0"""
    iters = RELAX['iters'] if iters is None else iters
    lam = RELAX['lam'] if lam is None else lam
    Adj = C.t.adjacency()
    mid = np.zeros(C.t.n_half, bool)
    mid[C.t.midline()] = True
    sel0 = ~C.fixed & (np.ones(C.t.n_half, bool) if only is None else only)
    for _ in range(iters):
        ok = np.isfinite(C.P).all(1)
        cnt = Adj @ ok.astype(np.float64)
        avg = (Adj @ np.where(ok[:, None], C.P, 0.0)) / np.maximum(cnt, 1.0)[:, None]
        sel = sel0 & ok & (cnt > 0)
        P = C.P[sel] + lam * (avg[sel] - C.P[sel])
        P[mid[sel], 2] = 0.0
        P = ref.project(P, it=4)
        P[mid[sel], 2] = 0.0
        C.P[sel] = P


# ============================================================================================ the cameras
def view_dir(fr):
    """a solved camera's line of sight INTO the scene, (d, q, x)"""
    c = np.asarray(fr['cam'][0], np.float64)
    v = np.array([c[2], -c[1], -c[0]])
    return v / np.linalg.norm(v)


def back_project(ref, fr, W, reach=320.0, graze=None):
    """image points W (n, 2) of a solved front camera (fr: canid_hull.nose_frame-like: cam (c, r, u) in (x, q, p), npd)
    onto the reference: each camera ray's first crossing from the camera side. graze (mm): a ray that first passes within
    graze of the surface without entering it there (an OCCLUDING CONTOUR: a traced outline's silhouette part) takes its
    closest approach, projected onto the surface, instead of the crossing it reaches further on"""
    c, r, u = (np.asarray(a, np.float64) for a in fr['cam'])
    npd = fr['npd']
    W = np.atleast_2d(np.asarray(W, np.float64))
    X0 = W[:, :1] * r[None] + W[:, 1:2] * u[None] + reach * c[None]       # (x, q, p) far on the camera side
    A = np.column_stack([npd - X0[:, 2], X0[:, 1], X0[:, 0]])
    dirv = np.array([c[2], -c[1], -c[0]])                                   # into the scene, (d, q, x)
    hit = ref.cross(A, np.tile(dirv, (len(A), 1)), reach=reach + 60.0, step=0.2, outward=False)
    if graze is None:
        return hit
    ts = np.arange(0.0, reach + 60.0, 0.2)
    for j in range(len(A)):
        Q = A[j][None] + ts[:, None] * dirv[None]
        f = ref(Q)
        near = np.nonzero(f < graze)[0]
        if not len(near):
            continue
        j0 = near[0]
        win = slice(j0, min(len(ts), j0 + 30))                              # 6 mm past the first approach
        if np.any(f[win] < 0.0):
            continue                                                        # it enters there: the crossing stands
        jm = j0 + int(np.argmin(f[win]))
        hit[j] = ref.project(Q[jm][None])[0]
    return hit


def to_image(fr, P):
    """palate points (n, 3) -> the solved camera's image mm"""
    c, r, u = (np.asarray(a, np.float64) for a in fr['cam'])
    X = np.column_stack([P[:, 2], P[:, 1], fr['npd'] - P[:, 0]])
    return np.column_stack([X @ r, X @ u])


# ============================================================================================ the features
def surf_march(ref, P, dirv, dist, step=0.5):
    """points P (n, 3) moved `dist` mm along the reference's surface, starting in the tangent directions dirv (n, 3),
    each step re-projected and its direction kept tangent"""
    P = np.atleast_2d(np.asarray(P, np.float64)).copy()
    dv = np.atleast_2d(np.asarray(dirv, np.float64)).copy()
    dist = np.broadcast_to(np.asarray(dist, np.float64), (len(P),))
    ns = max(1, int(np.ceil(float(dist.max()) / step)))
    for _ in range(ns):
        n_ = ref.normal(P)
        dv = dv - np.sum(dv * n_, axis=1, keepdims=True) * n_
        dv /= np.maximum(np.linalg.norm(dv, axis=1, keepdims=True), 1e-9)
        P = ref.project(P + (dist / ns)[:, None] * dv, it=4)
    return P


def mid_at(mid, s):
    """the reference's midline curve (k, 2) (d, q) by 0.25 mm at arc length s: (d, q, 0)"""
    tm = np.arange(len(mid)) * 0.25
    return np.array([np.interp(s, tm, mid[:, 0]), np.interp(s, tm, mid[:, 1]), 0.0])


def mid_s(mid, P):
    """the arc length of the midline curve's point nearest P's (d, q)"""
    j = int(np.argmin(np.hypot(mid[:, 0] - P[0], mid[:, 1] - P[1])))
    return 0.25 * j


def border_frame(ref, B):
    """each point of the leather's border B (m, 3, the U's order: from the top midline round the side to the bottom
    midline) with its OUTWARD tangent direction on the surface (away from the leather: the surface normal crossed with
    the border's direction, which points back on the top and the side, down at the bottom), (m, 3)"""
    T = np.gradient(B, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    N = ref.normal(B)
    out = np.cross(N, T)
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def leather_loops(ref, B, rim3, lu, rim_col=None):
    """THE LEATHER'S BORDER held off the nostril's rim and its FRONT loop (LEATHER b_min, inset, clear): the border's
    points within b_min mm of the rim (rim3, the rim's targets on the creature's left, densified along the loop) moved out
    along the surface, away from the leather, till they clear it; the front loop each border point moved IN along the
    surface by the inset of its part (the top, the side, the bottom: blended over the U's corners), at most to `clear` mm
    outside the rim; then, at the rows the nostril's square ring spans (rim_col: cap row -> the rim's lateral vertex on
    it), FRONT-FACING: the rim's lateral vertex moved out along the surface, away from the rim's centre, by `clear`, the
    rows between eased (the one cap strip from the rim to the front loop stays even; the strip from the front loop to the
    border takes the turn back along the wrap: W2k k1e's inset there printed a slit by the rim). Returns (border (m, 3),
    front (m, 3), the outward directions (m, 3))"""
    lv = LEATHER
    m, j_tl, j_bl = lu['m'], lu['j_tl'], lu['j_bl']
    B = np.asarray(B, np.float64).copy()
    rim_d = resample(rim3, 10 * len(rim3), closed=True)
    jj = np.arange(m)
    inner = (jj > 0) & (jj < m - 1)
    for _ in range(10):
        dd = np.linalg.norm(B[:, None, :] - rim_d[None], axis=2).min(1)
        need = inner & (dd < lv['b_min'] - 0.05)
        if not need.any():
            break
        out = border_frame(ref, B)
        B[need] = surf_march(ref, B[need], out[need], np.minimum(lv['b_min'] - dd[need] + 0.1, 1.0))
    out = border_frame(ref, B)
    ins = lv['inset']
    w_t = smooth01((j_tl + 1.5 - jj) / 3.0)
    w_b = smooth01((jj - (j_bl - 1.5)) / 3.0)
    w_in = w_t * ins['top'] + w_b * ins['bot'] + (1.0 - w_t - w_b).clip(0.0, 1.0) * ins['side']
    dd = np.linalg.norm(B[:, None, :] - rim_d[None], axis=2).min(1)
    w_in = np.minimum(w_in, np.maximum(dd - lv['clear'], 1.0))
    F = B.copy()
    F[inner] = surf_march(ref, B[inner], -out[inner], w_in[inner])
    n_sm = int(lv.get('smooth_top', 0))
    if n_sm > 0 and j_tl > 1:
        # W2p (the successor head builder; the lead's call 3, "the leather's dorsal extent up to the photos' bare edge"):
        # THE FRONT LOOP'S TOP RUN SMOOTHED along the loop. With the border's top back on the bridge (canid_nose BORDER:
        # d 28.5 on the midline, w12's traced bare edge cast onto the clay) its inward offsets crowd where the border
        # turns: at the U's top-lateral corner three front-loop points fell within ~1 mm (probe n1: cage edges 0.4 / 3.2
        # mm beside 12 mm strips, two quads folded 157-173 deg) and, with a shallower upper side, the point beside the top
        # midline crossed it (f1: x -1.3): the fit folded both, the renders' hairline cracks on the leather. So the run from
        # the midline end to the corner (both kept) is relaxed n_sm times along the loop (lam 0.5), each time put back on
        # the reference and kept off the midline: evenly spread across the leather's top. (Its midline end is the border's
        # own midline point inset the same way, on the midline: place_leather puts the loop's end there, on the midline
        # curve, after this; F[0] is still the border's here)
        F0 = surf_march(ref, B[:1], -out[:1], w_in[:1])
        F0[0, 2] = 0.0
        F[0] = ref.project(F0)[0]
        j2 = j_tl + 1 if lv.get('smooth_corner', False) else j_tl
        for _ in range(n_sm):
            Fm = F.copy()
            Fm[1:j2] = F[1:j2] + 0.5 * (0.5 * (F[0:j2 - 1] + F[2:j2 + 1]) - F[1:j2])
            Fm[1:j2] = ref.project(Fm[1:j2])
            Fm[1:j2, 2] = np.maximum(Fm[1:j2, 2], 0.25 * Fm[2:j2 + 1, 2])
            F = Fm
    if rim_col:
        rc = rim3.mean(0)
        kt = lu['kt']
        ks = sorted(rim_col)
        jr = np.array([j_tl + (k - kt) for k in ks])
        Pr = np.array([rim_col[k] for k in ks])
        Ff = surf_march(ref, Pr, Pr - rc, lv['clear'])
        F[jr] = Ff
        # the side's rows between the corners and the rim's rows eased along the surface (projected chords)
        for a, b in ((j_tl, jr[0]), (jr[-1], j_bl)):
            for j in range(a + 1, b):
                t_ = (j - a) / (b - a)
                F[j] = ref.project(((1.0 - t_) * F[a] + t_ * F[b])[None])[0]
        # still inside the border: where the border lies within b_min of the front loop, it is moved out
        for _ in range(8):
            gap = np.linalg.norm(B - F, axis=1)
            need = inner & (gap < lv['b_min'] - lv['clear'])
            if not need.any():
                break
            out = border_frame(ref, B)
            B[need] = surf_march(ref, B[need], out[need], np.minimum(lv['b_min'] - lv['clear'] - gap[need] + 0.1, 1.0))
        out = border_frame(ref, B)
    return B, F, out


def leather_mid(ref, fr, tr, mid):
    """the leather's loops' MIDLINE ENDS as arc lengths along the reference's midline curve (from the first station's top
    round the nose): the border's (canid_nose.border_curve), the front loop's its inset inside them (LEATHER inset top / bot: toward
    the tip), the support's `support` mm outside. The face cap's midline rows are anchored on them"""
    lv = LEATHER
    B = tr['border']
    sB0, sB1 = mid_s(mid, B[0]), mid_s(mid, B[-1])
    return dict(sS0=sB0 - lv['support'], sB0=sB0, sF0=sB0 + lv['inset']['top'], sF1=sB1 - lv['inset']['bot'], sB1=sB1,
                sS1=sB1 + lv['support'])


def place_leather(C, ref, fr, mid, lm, log=print, tr=None, nost=None):
    """THE LEATHER'S LOOPS (LEATHER; the open tube 'leather' inside the U of face-cap vertices round it): the BORDER on
    the leather's outline on the clay's frame (tr: canid_nose.border_curve) held off the nostril's rim, the FRONT loop
    its inset (leather_loops), the U itself the SUPPORT loop outside the border; their midline ends on the reference's
    midline curve (lm: leather_mid). The border and the front loop are held (features); the support loop slides on the
    reference in the fit"""
    t = C.t
    lv = LEATHER
    lu = t.leather_u
    m, j_tl, j_bl = lu['m'], lu['j_tl'], lu['j_bl']
    rim3 = nost['P']['rim']
    (ni0, ni1), (nk0, nk1) = LAYOUT['nose_i'], LAYOUT['nose_k']
    rim_col = {k: C.P[t.R[k, ni1]].copy() for k in range(nk0, nk1 + 1)}
    B, F, out = leather_loops(ref, tr['border'], rim3, lu, rim_col)
    # the midline ends on the midline curve (leather_mid); the support loop `support` mm outside the border along the
    # surface
    sB0, sF0, sF1, sB1 = lm['sB0'], lm['sF0'], lm['sF1'], lm['sB1']
    B[0], B[-1] = mid_at(mid, sB0), mid_at(mid, sB1)
    F[0], F[-1] = mid_at(mid, sF0), mid_at(mid, sF1)
    S = surf_march(ref, B, out, lv['support'])
    S[0] = mid_at(mid, sB0 - lv['support'])
    S[-1] = mid_at(mid, sB1 + lv['support'])
    names = LAYOUT['tubes']['leather']
    rings = dict(zip(names, t.tubes['leather']))
    src = dict(border='the leather\'s BORDER: its outline on the clay\'s own frame (canid_nose.border_curve: PROFILE, TOP, '
                      'the photos\' outline), spaced by its arc length (the bottom evenly across), off the nostril\'s rim',
               front='the leather\'s FRONT loop: the border\'s inset on the surface, clear of the nostril\'s rim (LEATHER)',
               mid='the leather\'s MIDDLE loop: half way from its border to its front loop on the surface (W2p)')
    put_ = [('border', B), ('front', F)]
    if 'mid' in rings:
        # W2p (the lead's call 3, "the leather's dorsal extent up to the photos' bare edge"): with the border's top back on
        # the bridge (canid_nose BORDER, d 28.5: w12's traced bare edge cast onto the clay, w11's own leather) one strip
        # from the border to the front loop ran 20 mm over the leather's top, and the fit printed pleats and a tick down
        # it (probes n1-n2): a middle loop halves it, on the surface between the two
        M_ = ref.project(0.5 * (B + F), it=12)
        M_[0, 2] = M_[-1, 2] = 0.0             # (its ends on the midline: the mirror shares them)
        put_.append(('mid', M_))
    for nm, P_ in put_:
        for j, v in enumerate(rings[nm]):
            C.put(v, P_[j], src[nm])
    for j, v in enumerate(t.rim['leather']):
        C.put(v, S[j], 'the leather\'s SUPPORT loop on the muzzle round its border (LEATHER support)', fix=False)
    t.loops['leather border'] = list(rings['border'])
    t.loops['leather front'] = list(rings['front'])
    t.leather_mid = lm
    sl = arclen(B[j_tl:j_bl + 1])
    log(f'[cage] the leather\'s loops: the border on the clay\'s frame, the top at d {B[0, 0]:.1f} on the midline (q '
        f'{B[0, 1]:.1f}), the top-lateral corner ({B[j_tl, 0]:.1f}, {B[j_tl, 1]:.1f}, {B[j_tl, 2]:.1f}), its side '
        f'{sl[-1]:.1f} mm long in {j_bl - j_tl} steps of {np.diff(sl).min():.1f}-{np.diff(sl).max():.1f}, the bottom-'
        f'lateral corner ({B[j_bl, 0]:.1f}, {B[j_bl, 1]:.1f}, {B[j_bl, 2]:.1f}), the bottom at the midline (d {B[-1, 0]:.1f}, '
        f'q {B[-1, 1]:.1f}); the front loop\'s top at d {F[0, 0]:.1f} (q {F[0, 1]:.1f}), its corners ({F[j_tl, 0]:.1f}, '
        f'{F[j_tl, 1]:.1f}, {F[j_tl, 2]:.1f}), ({F[j_bl, 0]:.1f}, {F[j_bl, 1]:.1f}, {F[j_bl, 2]:.1f}); the strips front -> '
        f'border {np.linalg.norm(B - F, axis=1).min():.1f}-{np.linalg.norm(B - F, axis=1).max():.1f} mm')
    return tr


def nostril_chart(spec, fr):
    """THE NOSTRIL's chart (W2l: canid_nose.nostril_chart, the comma in the level front chart; W2i-W2k: w12's tracings in
    w12's solved camera): the opening's centre, its half axes, and the opening, the dark core, the fold's inner and outer
    edges in the chart (image mm about the centre, divided by the half axes)"""
    from . import canid_nose as CN
    return CN.nostril_chart(spec, fr)


def place_nostril(C, ref, fr, spec, log=print):
    """THE NOSTRIL (NOSTRIL; the tube 'nostril'): every ring on the rim's spokes (ring_angles) in the chart (fr: W2l
    canid_nose.level_frame, the level front), its radius from the comma's curves, lifted along the line of sight onto
    the leather (back_project) and moved along the leather's normal (the fold) or in along the line of sight and turned
    (the edge, the core, the vestibule, the canal); the enclosed vertices at the canal's end"""
    t = C.t
    L = LAYOUT
    ns = NOSTRIL
    (i0, i1), (k0, k1) = L['nose_i'], L['nose_k']
    ch = nostril_chart(spec, fr)
    ab = ch['ab']
    ang = ring_angles(t.rim_cells['nostril'], i0, i1, k0, k1)
    m = len(ang)
    r_open = polar_radius(ch['open'], ang)
    r_dark = polar_radius(ch['dark'] - (ch['dark'].mean(0) * 0.0), ang)
    r_fi = polar_radius(ch['fold_in'], ang, closed=False)
    r_fo = polar_radius(ch['fold_out'], ang, closed=False)
    assert np.isfinite(r_open).all() and np.isfinite(r_dark).all(), 'the opening and the core must be star-shaped round ' \
                                                                     'the opening\'s centre'
    # the fold's sector: where both its traced edges are crossed, faded `fade` deg past their ends (the angles of the
    # traced edges' ends about the centre)
    infold = np.isfinite(r_fi) & np.isfinite(r_fo)
    a_end = np.concatenate([np.arctan2(ch['fold_in'][[0, -1], 1], ch['fold_in'][[0, -1], 0]),
                            np.arctan2(ch['fold_out'][[0, -1], 1], ch['fold_out'][[0, -1], 0])])
    da = np.full(m, np.inf)
    for j in np.nonzero(~infold)[0]:
        da[j] = np.degrees(np.min(np.abs(np.angle(np.exp(1j * (ang[j] - a_end))))))
    w_f = np.where(infold, 1.0, smooth01(1.0 - da / ns['fade']))
    # W2l h3 (the restarted head builder): the fold's crest eased down toward the slit's tip (NOSTRIL tip_fade: its height
    # x tip_fade[1] at the tip, full tip_fade[0] deg back along the fold): at full height to its end the crest stood h mm
    # proud at the slit's tip and the spokes past it dropped off it, a wedge and a spike under the slit's lateral end
    h_tip = np.ones(m)
    if ns.get('tip_fade'):
        a_tip = np.arctan2(ch['fold_in'][-1, 1], ch['fold_in'][-1, 0])
        d_tip = np.degrees(np.abs(np.angle(np.exp(1j * (ang - a_tip)))))
        h_tip = ns['tip_fade'][1] + (1.0 - ns['tip_fade'][1]) * smooth01(d_tip / ns['tip_fade'][0])
    r_core = np.minimum(r_dark, 0.85 * r_open)
    if ns.get('wing') and ns['wing'].get('core_wall'):
        # W2u: the dark core at most `core_wall` mm inside the opening's edge on every spoke, so it runs into the slit tail
        # too (the comma eroded by core_in loses the tail's thin end, and on the tail's spokes the tube sloped from the
        # tail's edge back to a core round the head: the lit triangular flap inside each opening from the level front)
        s_mm = np.hypot(ab[0] * np.cos(ang), ab[1] * np.sin(ang))
        r_core = np.maximum(r_core, np.minimum(r_open - ns['wing']['core_wall'] / s_mm, 0.92 * r_open))
    out_s = ns['out'] / np.hypot(ab[0] * np.cos(ang), ab[1] * np.sin(ang)) * np.hypot(np.cos(ang), np.sin(ang))
    r_crest_f = np.where(infold, r_fi + ns['at'] * (r_fo - r_fi), r_open + out_s)
    r_fold = np.maximum(w_f * r_crest_f + (1.0 - w_f) * (r_open + out_s), 1.08 * r_open)
    # THE RIM: an ellipse round the fold's outer edge (+ pad), held inside the leather's border and off the midline
    fo_mm = ch['unsc'](ch['fold_out'])
    op_mm = ch['unsc'](ch['open'])
    lo_mm = np.minimum(fo_mm.min(0), op_mm.min(0)) - ns['rim_pad']
    hi_mm = np.maximum(fo_mm.max(0), op_mm.max(0)) + ns['rim_pad']
    full = np.asarray(fr['full'], np.float64)
    u_mid = fr['u_ax'] + ns['mid']
    lo_mm[0] = max(lo_mm[0], u_mid)
    hi_mm[0] = min(hi_mm[0], full[:, 0].max() - ns['inset'])
    hi_mm[1] = min(hi_mm[1], full[:, 1].max() - ns['inset'])
    lo_mm[1] = max(lo_mm[1], full[:, 1].min() + ns['inset'])
    rc = 0.5 * (lo_mm + hi_mm)
    rh = 0.5 * (hi_mm - lo_mm)
    # the rim's points by the spokes from the opening's centre (ch c) onto the ellipse (rc, rh)
    dmm = np.column_stack([np.cos(ang) * ab[0], np.sin(ang) * ab[1]])
    dmm /= np.linalg.norm(dmm, axis=1, keepdims=True)
    o_ = ch['c'] - rc
    aa = (dmm[:, 0] / rh[0]) ** 2 + (dmm[:, 1] / rh[1]) ** 2
    bb = 2.0 * ((o_[0] * dmm[:, 0]) / rh[0] ** 2 + (o_[1] * dmm[:, 1]) / rh[1] ** 2)
    cc = (o_[0] / rh[0]) ** 2 + (o_[1] / rh[1]) ** 2 - 1.0
    tr_ = (-bb + np.sqrt(np.maximum(bb * bb - 4.0 * aa * cc, 0.0))) / (2.0 * aa)
    # each spoke held `inset` mm inside the leather's traced border at its own image height (nose_frame's half width hw
    # per image height vg) and `mid` mm off the midline: the fold's outer edge nearly reaches the leather's side in w12,
    # and an ellipse held only to the border's widest point crushed the column between them (c7a: pleats and a slit)
    ts = np.linspace(0.0, 1.0, 241)
    n_cl = 0
    for j in range(m):
        seg = ch['c'][None] + (ts * tr_[j])[:, None] * dmm[j][None]
        hw_ = np.interp(seg[:, 1], fr['vg'], fr['hw'], left=0.0, right=0.0)
        out_ = (seg[:, 0] - fr['u_ax'] > hw_ - ns['inset']) | (seg[:, 0] - fr['u_ax'] < ns['mid'])
        if out_.any():
            tr_[j] = ts[max(int(np.argmax(out_)) - 1, 1)] * tr_[j]
            n_cl += 1
    rim_mm = ch['c'] + tr_[:, None] * dmm
    r_rim = np.linalg.norm((rim_mm - ch['c']) / ab, axis=1)
    # the fold held inside the rim (c7c pushed the rim back out past the leather's border instead: the slot at its side)
    bad = r_fold > r_rim / 1.12
    r_fold = np.minimum(r_fold, r_rim / 1.12)
    r_fold = np.maximum(r_fold, 1.04 * r_open)
    r_rim = np.maximum(r_rim, 1.05 * r_fold)
    if bad.any():
        log(f'[cage] the nostril\'s fold held inside the rim on {int(bad.sum())} spokes')
    # W2u: THE ALAR WING's three rings (NOSTRIL wing; LAYOUT tubes nostril 'wing_o', 'wing', 'fold'): in the fold's sector
    # across its band (fold_in -> fold_out), off it on the planum across the gap from the opening to the rim, blended by
    # the sector's weight; ordered edge < lip < crest < outer foot < rim, each 4 % apart in the chart (a fold-free tube)
    wg = ns.get('wing') if 'wing' in L['tubes']['nostril'] else None
    if wg:
        band = np.where(infold, r_fo - r_fi, 0.0)
        r_fi0 = np.where(infold, r_fi, r_open)

        def blend(a_, f_):
            return w_f * (r_fi0 + a_ * band) + (1.0 - w_f) * (r_open + f_ * (r_rim - r_open))
        r_wo, r_wc, r_wi = (blend(a_, f_) for a_, f_ in zip(wg['at'], wg['gap']))
        r_wi = np.maximum(r_wi, 1.04 * r_open)
        r_wc = np.maximum(r_wc, 1.04 * r_wi)
        r_wo = np.maximum(r_wo, 1.04 * r_wc)
        n_wb = int((r_rim < 1.05 * r_wo).sum())
        r_rim = np.maximum(r_rim, 1.05 * r_wo)
        r_fold = r_wi
        if n_wb:
            log(f'[cage] the nostril\'s rim held outside the wing\'s outer foot on {n_wb} spokes')
        # the wing eased out toward the slit's tip (its height and its carry-in), so the slit's lateral end rounds off
        # into the pad
        h_tip_w = np.ones(m)
        if wg.get('tip_fade'):
            a_tip = np.arctan2(ch['fold_in'][-1, 1], ch['fold_in'][-1, 0])
            d_tip = np.degrees(np.abs(np.angle(np.exp(1j * (ang - a_tip)))))
            h_tip_w = wg['tip_fade'][1] + (1.0 - wg['tip_fade'][1]) * smooth01(d_tip / wg['tip_fade'][0])
        if wg.get('start_fade'):
            # and eased in from its start over the head's upper-lateral side (w6: at full height from fold_from on, the
            # wing's upper end stood as a pointed corner in profile)
            a_st = np.arctan2(ch['fold_in'][0, 1], ch['fold_in'][0, 0])
            d_st = np.degrees(np.abs(np.angle(np.exp(1j * (ang - a_st)))))
            h_tip_w = h_tip_w * (wg['start_fade'][1] + (1.0 - wg['start_fade'][1]) * smooth01(d_st / wg['start_fade'][0]))
    spoke = np.column_stack([np.cos(ang), np.sin(ang)])
    uv = lambda r_: ch['unsc'](r_[:, None] * spoke)          # noqa: E731
    dirv = view_dir(fr)
    up = np.array([0.0, 1.0, 0.0]) - (dirv[1]) * dirv
    up /= np.linalg.norm(up)
    turn = lambda deg: np.cos(np.radians(deg)) * dirv + np.sin(np.radians(deg)) * up      # noqa: E731

    def surf(W):
        S = back_project(ref, fr, W)
        bad_ = ~np.isfinite(S).all(1)
        if bad_.any():
            raise RuntimeError(f'the nostril: {int(bad_.sum())} rays missed the leather')
        return S
    S_rim = surf(uv(r_rim))
    S_fold = surf(uv(r_fold))
    S_edge = surf(uv(r_open))
    cd = ch['dark'].mean(0)                                    # the core's centre (chart)
    S_core = surf(ch['unsc'](cd + ns['core_shrink'] * (r_core[:, None] * spoke - cd)))
    n_fold = ref.normal(S_fold)
    P = {}
    P['rim'] = S_rim
    P['fold'] = S_fold + (w_f * ns['h'] * h_tip)[:, None] * n_fold
    # W2m: the fold's crest carried IN over the opening (NOSTRIL over, mm, across the line of sight toward the opening's
    # edge on its spoke): a roof over the opening's upper margin and the comma's tail, under which the edge is tucked
    # (CANID_HEAD_STUDY 2.1: the cow's dorsal-lateral rim overhangs its nares, so they read as dark slots under a ledge
    # from level and from below; a crest raised beside the opening reads as a rim round a hole)
    if wg:
        # W2u: THE WING's outer foot, crest and inner lip, each raised along the leather's normal at its own point and
        # carried in across the line of sight toward the opening's edge on its spoke (NOSTRIL wing h, over), all three
        # by the sector's weight and eased out toward the slit's tip: a lobe whose lip overhangs the opening's lateral
        # margin and the comma's tail
        # the carry-in RAMPS along the fold (over beside the head's lateral side -> over_tail over the slit, by the
        # spoke's place along fold_in, 0 at fold_from, 1 at the slit's tip, eased over `ramp`): the photos' wing roofs
        # the tail and leaves the head open (w3: carried in 1.8 mm all along, it hid the head's lateral margin, the
        # level share 12.2 -> 10.8 %, and the slit's floor still showed lit from three-quarter and from above)
        fi_ = np.asarray(ch['fold_in'], np.float64)
        t_fi = np.linspace(0.0, 1.0, len(fi_))
        P_x = np.where(np.isfinite(r_fi), r_fi, r_open)[:, None] * spoke
        t_sp = t_fi[np.argmin(np.linalg.norm(P_x[:, None, :] - fi_[None], axis=2), axis=1)]
        ramp = wg.get('ramp', (0.3, 0.8))
        w_tail = smooth01((t_sp - ramp[0]) / max(ramp[1] - ramp[0], 1e-6))
        ov_tail = wg.get('over_tail', wg['over'])
        for nm, r_, h_, o_, ot_ in zip(('wing_o', 'wing', 'fold'), (r_wo, r_wc, r_wi), wg['h'], wg['over'], ov_tail):
            S_ = S_fold if nm == 'fold' else surf(uv(r_))
            tw = S_edge - S_
            tw -= (tw @ dirv)[:, None] * dirv[None]
            tw /= np.maximum(np.linalg.norm(tw, axis=1, keepdims=True), 1e-9)
            o_s = o_ + (ot_ - o_) * w_tail
            # raised along the leather's normal with its part toward the level camera scaled by `fwd`: the lobe bulges
            # out to the side more than forward (w4: along the full normal the lobe over the tail stood ahead of the
            # front's lower part in profile, a flap the profiles w10 / f04 do not show)
            n_ = ref.normal(S_)
            n_ = n_ - (1.0 - float(wg.get('fwd', 1.0))) * (n_ @ -dirv)[:, None] * (-dirv)[None]
            n_ /= np.maximum(np.linalg.norm(n_, axis=1, keepdims=True), 1e-9)
            P[nm] = S_ + (w_f * h_ * h_tip_w)[:, None] * n_ + (w_f * o_s * h_tip_w)[:, None] * tw
    elif ns.get('over') or ns.get('over_lat'):
        # W2s (the lead's call 6, "the alar wing curling over them"): over_lat, the crest carried in on the LATERAL spokes
        # alone (their cosine): w12's wing overhangs the comma's tail, the round head stays open to the high cameras
        # (W2r took `over` off everywhere because over the head's top it hid the opening from w12's camera)
        tw = S_edge - S_fold
        tw -= (tw @ dirv)[:, None] * dirv[None]
        tw /= np.maximum(np.linalg.norm(tw, axis=1, keepdims=True), 1e-9)
        ov_ = float(ns.get('over', 0.0)) + float(ns.get('over_lat', 0.0)) * smooth01((np.cos(ang) - 0.1) / 0.6)
        P['fold'] = P['fold'] + (ov_ * w_f * h_tip)[:, None] * tw
    # W2r (the lead's call 4, "the nares opened toward the photos' share ... read at the photos' cameras"): the opening's
    # UPPER edge tucked back along the line of sight by tuck_up mm more than its lower (eased in over the opening's height,
    # its spoke's sine), the core with it: the opening's plane tips up toward the high cameras, as the photos' nares do
    # (w12, 48 deg over the palate, sees its openings as round dark ovals, 10.4 % of the leather; W2q's 3.1 %, a slit
    # under the leather's foot)
    w_up = smooth01((np.sin(ang) + 0.2) / 1.0) * float(ns.get('tuck_up', 0.0))
    tuck_f = float(wg['tuck']) if wg else ns['tuck']          # W2u: the edge tucked deeper under the wing's lip
    P['edge'] = S_edge + (ns['tuck0'] + w_f * tuck_f + w_up)[:, None] * dirv[None]
    up_img = np.asarray(fr['cam'][2], np.float64)
    up_img = np.array([-up_img[2], up_img[1], up_img[0]])           # the image's up, (d, q, x)
    core_d = ns['core'] + w_up
    if wg and wg.get('core_tail'):
        # W2u: the core sunk deeper under the slit (NOSTRIL wing core_tail mm along the line of sight where the carry-in
        # has ramped to the tail): with the edge tucked 2.8 mm there and the core 3 mm in, the slit's floor was a nearly
        # flat shelf facing the key, the lit "horn" from three-quarter and from above (w1-w5)
        core_d = core_d + (float(wg['core_tail']) - ns['core']) * (w_f * w_tail)
    P['core'] = S_core + core_d[:, None] * dirv[None] + ns['core_up'] * up_img[None]
    for nm in ('deep', 'canal'):
        g = ns[nm]
        S_ = surf(ch['unsc'](cd + g['shrink'] * (r_core[:, None] * spoke - cd)))
        P[nm] = S_ + g['depth'] * turn(g['turn'])[None]
    S_c = surf(ch['unsc'](cd[None]))[0]
    e_ = ns['end']
    end = S_c + e_['depth'] * turn(e_['turn'])
    names = L['tubes']['nostril']
    for j, v in enumerate(t.rim['nostril']):
        C.put(v, P['rim'][j], 'the nostril\'s RIM on the leather (an ellipse round w12\'s traced fold, its spokes the ring\'s)')
    src = dict(wing_o='the alar WING\'s outer foot (NOSTRIL wing: at the fold\'s outer edge, a little raised; off the '
                      'sector on the planum)',
               wing='the alar WING\'s crest (NOSTRIL wing: across the fold\'s band, raised along the leather\'s normal)',
               fold=('the alar WING\'s inner lip (NOSTRIL wing: on the opening\'s margin, raised and carried in over '
                     'the opening)') if wg else
                    'the alar FOLD\'s crest (between NOSE_W12 fold_in and fold_out, raised along the leather\'s normal; '
                    'elsewhere just outside the opening)',
               edge='the opening\'s EDGE on the comma (canid_nose.nostril_chart; tucked in, more under the fold)',
               core='the dark CORE\'s outline in along the line of sight',
               deep='the vestibule (DEEP), turned (NOSTRIL deep turn)', canal='the CANAL, turned (NOSTRIL canal turn)')
    for nm, ring in zip(names, t.tubes['nostril']):
        for j, v in enumerate(ring):
            C.put(v, P[nm][j], src[nm])
    # the enclosed vertices: the canal's end, spread a little in its plane by their grid position
    e1 = np.cross(turn(e_['turn']), np.array([0.0, 0.0, 1.0]))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(turn(e_['turn']), e1)
    ic, kc = 0.5 * (i0 + i1), 0.5 * (k0 + k1)
    for (i, k), v in zip(t.inner_cells['nostril'], t.inner['nostril']):
        C.put(v, end + e_['spread'] * ((i - ic) / (0.5 * (i1 - i0)) * e2 + (kc - k) / (0.5 * (k1 - k0)) * e1),
              'the canal\'s END (the tube closed)')
    t.loops['nostril rim'] = list(t.tubes['nostril'][names.index('edge')])
    t.loops['nostril fold'] = list(t.tubes['nostril'][names.index('fold')])
    t.nostril_wf = w_f
    log(f'[cage] the nostril: the opening {2 * ab[0]:.1f} x {2 * ab[1]:.1f} mm in the level chart, the fold over '
        f'{int(infold.sum())} of {m} spokes, the rim {2 * rh[0]:.1f} x {2 * rh[1]:.1f} mm ({n_cl} spokes held inside the '
        f'leather\'s border), the canal\'s end {np.linalg.norm(end - S_c):.1f} mm in')
    rr = dict(open=r_open, core=r_core, fold=r_fold, rim=r_rim)
    if wg:
        rr.update(wing_o=r_wo, wing=r_wc)
    return dict(P=P, end=end, ang=ang, w_fold=w_f, r=rr)


def canthi_near_globe(spec):
    """the photos' CANTHI (lm_<pid>.json canthus_med_*, canthus_lat_*, the photos of EYE_FISSURES) on their solved
    cameras' rays at the point NEAREST THE LID'S SPHERE (its camera-side crossing, or the ray's nearest approach where
    it passes outside): each lands on its photo's corner in that camera and at the eye's depth, so the lids' commissures
    hug the globe; the right eyes mirrored onto the left, averaged. canid_hull.traced_canthi carries them onto the skin
    instead, where the clay's face happens to stand: the medial one at d 118, 30 mm from the globe's centre, on the
    muzzle's side in front of the eye (c7c's spike). Returns {'medial', 'lateral': (3,)} palate mm, the left eye.
    (W2n: the body is canid_hull.canthi_on_rays, under clay_points' registration: the eye landmark's fixed point carries
    the same canthi)"""
    from . import canid_hull as CH
    return CH.canthi_on_rays(spec, CH.clay_points(spec), CH.lid_frame(spec, 'L')['R'] + EYE['lid'])


def eye_chart(spec, ref, log=print):
    """THE EYE'S CHART: the traced fissure (canid_hull.traced_fissure, its corners drawn out to the photos' canthi on the
    reference: traced_canthi, fissure_polygon) carried onto the lid's sphere (past its outline onto the reference along
    the eye's axis); the chart the plane across the eye's axis (its normal nf = the axis, outward; c9b: the fissure's own
    best-fit plane folded the lower lid), u along the canthus axis (medial to lateral), v = nf x u (dorsal); the fissure
    in the chart scaled by its half axes. Returns the frame and the fissure"""
    from . import canid_hull as CH
    lf = CH.lid_frame(spec, 'L')
    c, oo, e1, ed, Rg = lf['centre'], lf['oo'], lf['e1'], lf['ed'], lf['R']
    Rl = Rg + EYE['lid']
    # (W2n: canid_hull.fissure_chart, shared with the eye landmark's fixed point (canid_hull.eye_landmark: the photos are
    # registered on the midpoint of these tips): traced_fissure's polygon, its corners drawn out to the photos' canthi on
    # their rays (canthi_near_globe), lifted onto the lid's sphere; past its outline (toward the canthi drawn out) pushed
    # out from the globe's centre to the lid's sphere + 0.5 mm: the commissures hug the globe)
    # (W2o: EYE face, the corners on the face at the profile-rule canthi, carried along the photos' own rays)
    F = CH.fissure_chart(spec, None, Rl, pin=EYE.get('pin', True), face=EYE.get('face'))
    poly, P3, can, r2 = F['poly'], F['P3'].copy(), F['can'], (F['poly'] ** 2).sum(1)
    log(f'[cage] the canthi on the photos\' rays ({"the profile rule, on the face" if EYE.get("face") else "nearest the lid sphere"}): '
        f'medial {np.round(can["medial"], 1)} ({float(np.linalg.norm(can["medial"] - c)):.1f} mm from the globe\'s centre), '
        f'lateral {np.round(can["lateral"], 1)} ({float(np.linalg.norm(can["lateral"] - c)):.1f}); the tips medial '
        f'{np.round(F["tips"]["medial"], 1)}, lateral {np.round(F["tips"]["lateral"], 1)}; the fissure out to '
        f'{float(np.sqrt(r2.max())):.1f} mm off the eye\'s axis (the lid\'s sphere {Rl:.1f})')
    # THE CHART: the plane across the eye's axis (its normal nf = oo outward; c9b, below), seen ORTHOGONALLY: it only parametrises the rings
    # (shared spokes, nested radii); the MARGIN is the traced fissure itself (P3: on the lid's sphere, at the canthi on the
    # face), the RIM is cast onto the face along -nf, and the lids, the roll and the sac are laid from those two radially
    # about the globe's centre (place_eye). (c7b lifted every ring radially from the centre through an angular chart: the
    # rays toward the canthi run beside the globe through the head and left it 30-67 mm out; c7a cast every ring along
    # -nf, 42 deg off the eye's axis, and grazed the lid's sphere on 23 of 32 spokes)
    # W2p (the successor head builder): with the lids turned to rest gaze (EYE face gaze: canid_hull.fissure_chart) the
    # chart's FRAME (its centre, axes and half axes, so the rim's ellipse and the orbit's rings cast from it) is the
    # unturned margin's (F['P3_0']): the lids turn with the eye, the socket and the brow stay with the face. (Framed on the
    # turned margin, probe g25's shorter chart pulled the rim's top down onto the reference's own eye opening, 0.2 mm off
    # the globe, and the orbit's rings inside it: the globe showed through the upper lid)
    P3f = np.asarray(F.get('P3_0', P3), np.float64)
    cf = P3f.mean(0)
    _, _, Vt = np.linalg.svd(P3f - cf)
    nfit = Vt[2] * (1.0 if Vt[2] @ oo > 0 else -1.0)
    # (c9b, the W2j look agent: the chart's normal is the EYE'S AXIS oo, not the fissure's best-fit plane normal nfit, 34
    # deg off it. The traced lower lid lies forward on the lid's sphere, up to 6.4 mm in front of that plane, so in its
    # chart the lower margin bulged UP to v -3 mm in the middle while the canthi hung at v -8.5 / -9.5: the shared spokes
    # crossed the lower margin 3.5-8 mm out at -54 .. -126 deg but its canthal parts 13.7-16 mm out at -45 and -135 deg,
    # and every ring folded over the lower opening there (work/bestiary/wolf/check_w2j/eye_spokes.py): the Y-shaped pleat.
    # Seen along the eye's axis the same fissure is a convex almond (fissure_polygon's own frame: the lower lid at -5.5 ..
    # -10.5 mm), and the margin, the rim cast along -nf, the lids, the roll and the sac all follow from the chart unchanged.
    # Blending the normal 0.7 of the way (10 deg off the axis) left a small notch in the lower lid)
    nf = oo
    im_, il_ = F['tip_idx']        # (W2n: the traced corners; the least / most lateral pick flipped at the blunt medial end)
    ua = P3f[il_] - P3f[im_]
    ua -= (ua @ nf) * nf
    ua /= np.linalg.norm(ua)
    va = np.cross(nf, ua)
    uvf = np.column_stack([(P3f - cf) @ ua, (P3f - cf) @ va])
    # the chart's centre at the fissure's box centre (the canthi drawn out can pull the mean off it)
    cb = 0.5 * (uvf.max(0) + uvf.min(0))
    cf = cf + cb[0] * ua + cb[1] * va
    ab = 0.5 * (uvf.max(0) - uvf.min(0))
    uv = np.column_stack([(P3 - cf) @ ua, (P3 - cf) @ va])
    fis, n_fill = uv / ab, 0
    tips = {k: np.asarray(v, np.float64) for k, v in F['tips'].items()}
    a_tip = [float(np.arctan2(((tips[k] - cf) @ va) / ab[1], ((tips[k] - cf) @ ua) / ab[0])) for k in ('medial', 'lateral')]
    if EYE.get('star'):
        # W2l (the restarted head builder): the fissure STAR-SHAPED round the chart's centre (EYE star, star_outline)
        # (W2o: the tips' own angles among the outline's samples, so its corners stay sharp; the filled points keep the
        # traced outline's height, so the corners on the face keep theirs)
        fis, P3, n_fill = star_outline(fis, P3, cf, ua, va, ab, nf, c, Rl, *EYE['star'],
                                       extra=a_tip if EYE.get('face') else (), keep_h=bool(EYE.get('face')))
    log(f'[cage] the eye\'s chart: the fissure {2 * ab[0]:.1f} x {2 * ab[1]:.1f} mm seen along the eye\'s axis (the '
        f'fissure\'s own plane {np.degrees(np.arccos(np.clip(nfit @ oo, -1, 1))):.0f} deg off it); u along +d {ua[0]:+.2f}, '
        f'v up {va[1]:+.2f}, (u x v) . x {np.cross(ua, va)[2]:+.2f}; star-shaped round its centre ({n_fill} of '
        f'{len(fis)} angles filled out)')
    assert ua[0] > 0.0 and va[1] > 0.0, 'the eye\'s chart must run with the stations (u back) and against the rings (v up)'
    # W2q (EYE face follow): the lids posed at the largest fitted gaze in this chart (scaled like fis): place_eye's rim and
    # orbit rings enclose them, so the socket holds the lids' whole posed range while the chart frames the rest lids
    fis_env = None
    if F.get('P3_env') is not None:
        Pe_ = np.asarray(F['P3_env'], np.float64)
        fis_env = np.column_stack([(Pe_ - cf) @ ua, (Pe_ - cf) @ va]) / ab
        log(f'[cage] W2q the rest lids frame the chart; the lids at the largest fitted gaze reach '
            f'{float(fis_env[:, 1].max()):.2f} of its half height above its centre (the rest lids '
            f'{float(fis[:, 1].max()):.2f})')
    return dict(c=c, oo=oo, Rg=Rg, Rl=Rl, cf=cf, nf=nf, ua=ua, va=va, ab=ab, fis=fis, fis3=P3, poly=poly, tips=tips,
                a_tip=dict(medial=a_tip[0], lateral=a_tip[1]), fis_env=fis_env, follow=F.get('follow'))


def eye_tips(spec):
    """W2o: the cage's lid-margin TIPS as eye_chart builds them (canid_hull.fissure_chart under EYE pin and EYE face),
    the left eye, palate (d, q, x) mm: w02's gates and place_eye's notch read them"""
    from . import canid_hull as CH
    Rl = CH.lid_frame(spec, 'L')['R'] + EYE['lid']
    F = CH.fissure_chart(spec, None, Rl, pin=EYE.get('pin', True), face=EYE.get('face'))
    return {k: np.asarray(v, np.float64) for k, v in F['tips'].items()}


def spokes_on_tips(ang, E):
    """W2o: the eye's spoke angles (ring_angles) warped, piecewise linearly with their order kept, so that the spoke
    nearest each fissure tip's direction in the chart (eye_chart's a_tip) passes through it: the margin ring
    (polar_points at the spokes) then holds the tips themselves. (A pointed corner between two spokes 9-15 deg apart is
    cut short by their crossings: the cage's tip would fall short of the canthus by mm.) The ring's square layout puts
    spokes at 0 and 180 deg, so the warp is a few degrees"""
    two = 2.0 * np.pi
    a_l, a_m = E['a_tip']['lateral'], E['a_tip']['medial']
    i_l = int(np.argmin(np.abs((ang - a_l + np.pi) % two - np.pi)))
    i_m = int(np.argmin(np.abs((ang - a_m + np.pi) % two - np.pi)))
    base = float(ang[i_l])
    s = (ang - base) % two
    sm = float(s[i_m])
    tl = float((a_l - base + np.pi) % two - np.pi)
    tm = float((a_m - base) % two)
    new = np.where(s <= sm, tl + (tm - tl) * s / sm, tm + (two + tl - tm) * (s - sm) / (two - sm))
    return base + new


def even_spokes(ang, a_med, n_top, frac=None):
    """W2t (the lead's call 2, THE RIM CORNER REBUILT): the spokes from the one through the medial tip (spokes_on_tips) round
    the square's top-medial corner (cell 0, the square's 135 deg) to the top side's cell n_top spaced EVENLY in angle, the
    two ends held: every ring of the eye's tube (the rim, the orbit's rings, the lids, the margin, the roll, the sac) moves
    with its spoke. The square layout gives the medial side 15 deg a cell and the top side 9 (90 deg a side over 6 / 10
    cells), and the tip's warp opens the step past the tip to ~22 deg: so the rim's stretch above the medial canthus, which
    runs at slope 0.4-0.7 in (d, q) where the side grid's rows run at ~1, lay on the medial COLUMN (cells 26-31: W2r's
    inverted side quads R[2-3, 23-24]). W2s cured that by sliding the RIM's own vertices along the rim (EYE rim_slide) while
    the orbit's rings and the lids kept their spokes: the tube's outer quads sheared, and the limit, fitted through the held
    slid rim, stood 0.7 mm proud round the corner (the brow on the limit mesh 0.72 / 0.70 at 1.6 / 1.9 R). Here the corner
    cell moves (to ~150 deg) with all its rings, so the stretch goes to the top ROW and the tube stays radial.
    frac (W2t, the corner's share): the corner cell at this fraction of the way (in angle) from the tip's spoke to the top
    side's cell n_top, the cells either side of it even (None: every step even, the corner at 3 / 8 of the way with
    n_top 5). Evenly spaced, the medial column's top cell (31) still lay on the rim's SLANTED top-front run (slope ~0.8 in
    (d, q) where the side grid's rows climb at ~1.1 into the corner), so the side quad R[2-3, 23-24] stayed inverted in the
    targets (check_w2t corner_scan / cage_quads); with a small share the column's cells crowd onto the rim's steep front
    above the tip and the whole slanted run belongs to the top row"""
    two = 2.0 * np.pi
    m = len(ang)
    i_m = int(np.argmin(np.abs((ang - a_med + np.pi) % two - np.pi)))
    a_ = ang[0] - ((ang[0] - ang) % two)             # unwrapped, decreasing from cell 0
    seq = [(j, a_[j], 0.0) for j in range(i_m, m)] + [(j, a_[j] - two, two) for j in range(0, n_top + 1)]
    n = len(seq) - 1
    k_c = m - i_m                                    # the corner cell's place in seq
    a0, a1 = seq[0][1], seq[-1][1]
    out = ang.copy()
    for k, (j, _, wrap) in enumerate(seq):
        if frac is None:
            f_ = k / n
        elif k <= k_c:
            f_ = float(frac) * k / k_c
        else:
            f_ = float(frac) + (1.0 - float(frac)) * (k - k_c) / (n - k_c)
        out[j] = a0 + (a1 - a0) * f_ + wrap
    return out


def star_outline(fis, P3, cf, ua, va, ab, nf, c, Rl, n=360, k=2.5, extra=(), keep_h=False):
    """W2l (the restarted head builder): the eye chart's fissure made STAR-SHAPED round the chart's centre. With the eye's
    axis turned out to the lids' own facing (canid_hull STROKES_SKULL eye axis 19 / 40) the chart's centre (the fissure's
    box centre) stands over the canthal line, so the lower lid runs nearly radially into the medial corner and turns back
    ~3 deg (polar angles -128.5 .. -131 deg at 0.73-0.96 of the lid's sphere): the spokes' farthest crossings
    (polar_radius, polar_points) jumped 0.71 -> 0.95 between two spokes, a notch at the lower lid's medial end. Here the
    outline is resampled at n angles as its farthest crossing, the radius's steps rounded OUTWARD (never inward) so it
    rises at most k (the chart's half-axis units) per radian; the 3D outline is the traced one at its crossings and, where
    the cap filled it out, the chart's point lifted onto the lid's sphere (c, Rl) along nf (past its outline pushed out
    radially to Rl + 0.5 mm, as eye_chart does). Returns (fis (n, 2), fis3 (n, 3), the number of angles filled out).
    W2o (EYE face): `extra` angles (the tips') join the samples, so a pointed corner is sampled at its tip; with keep_h a
    filled point off the lid's sphere keeps the traced outline's height at its angle (its crossing moved out in the
    chart's plane, at least Rl + 0.5 mm from the centre), so the corners on the face keep theirs"""
    th = np.linspace(-np.pi, np.pi, int(n), endpoint=False)
    if len(extra):
        th = np.sort(np.concatenate([th, (np.asarray(extra, np.float64) + np.pi) % (2.0 * np.pi) - np.pi]))
    r0 = polar_radius(fis, th)
    d_ = np.abs(th[:, None] - th[None, :])
    d_ = np.minimum(d_, 2.0 * np.pi - d_)
    r = (r0[None, :] - k * d_).max(axis=1)
    Q3 = polar_points(fis, P3, th)
    fill = r > r0 + 1e-6
    if fill.any():
        S_ = r[fill, None] * np.column_stack([np.cos(th[fill]), np.sin(th[fill])]) * ab
        X = cf + S_[:, :1] * ua + S_[:, 1:2] * va
        w = X - c
        b = w @ nf
        disc = b * b - (np.einsum('ij,ij->i', w, w) - Rl * Rl)
        Pf = X + (-b + np.sqrt(np.maximum(disc, 0.0)))[:, None] * nf
        out = disc <= 0.0
        if out.any():
            D_ = X[out] - c
            nD = np.linalg.norm(D_, axis=1, keepdims=True)
            Pf[out] = c + D_ / nD * np.maximum(nD, Rl + 0.5)
        if keep_h:
            off = np.linalg.norm(Q3[fill] - c, axis=1) > Rl + 0.3
            if off.any():
                S2 = (r[fill] - r0[fill])[:, None] * np.column_stack([np.cos(th[fill]), np.sin(th[fill])]) * ab
                Pk = Q3[fill] + S2[:, :1] * ua + S2[:, 1:2] * va
                D_ = Pk - c
                nD = np.linalg.norm(D_, axis=1, keepdims=True)
                Pk = c + D_ / nD * np.maximum(nD, Rl + 0.5)
                Pf[off] = Pk[off]
        Q3[fill] = Pf
    return r[:, None] * np.column_stack([np.cos(th), np.sin(th)]), Q3, int(fill.sum())


def polar_points(poly2, poly3, ang):
    """each spoke's crossing with the closed chart polygon poly2 (k, 2) carried to the matching 3D polyline poly3 (k, 3)
    (the crossing edge's parameter), so a ring sampled at the spokes lies on the traced curve itself"""
    P = np.asarray(poly2, np.float64)
    A, B = P, np.roll(P, -1, axis=0)
    D = np.stack([np.cos(ang), np.sin(ang)], -1)
    E_ = B - A
    den = -D[:, None, 0] * E_[None, :, 1] + E_[None, :, 0] * D[:, None, 1]
    with np.errstate(divide='ignore', invalid='ignore'):
        r = (-A[None, :, 0] * E_[None, :, 1] + E_[None, :, 0] * A[None, :, 1]) / den
        t = (D[:, None, 0] * A[None, :, 1] - A[None, :, 0] * D[:, None, 1]) / den
    ok = (np.abs(den) > 1e-12) & (t >= -1e-9) & (t <= 1.0 + 1e-9) & (r > 0.0)
    rr = np.where(ok, r, -np.inf)
    e = np.argmax(rr, axis=1)
    tt = np.clip(t[np.arange(len(ang)), e], 0.0, 1.0)
    Q3 = np.asarray(poly3, np.float64)
    return Q3[e] + tt[:, None] * (np.roll(Q3, -1, axis=0)[e] - Q3[e])


def place_eye(C, ref, spec, log=print):
    """THE EYE (EYE; the tube 'eye'): every ring on the rim's spokes (ring_angles) in the fissure's chart (eye_chart), its
    radius between the traced fissure and the rim's ellipse, lifted along the chart's normal onto the face (the rim), the
    lid's sphere (the lids, the margin; on the face past its outline) or the globe (the roll, the sac); the enclosed
    vertices inside the globe"""
    t = C.t
    L = LAYOUT
    ey = EYE
    (b0, b1), (k0, k1) = L['eye_b'], L['eye_k']
    i0, i1 = t.nA + b0, t.nA + b1
    E = eye_chart(spec, ref, log)
    c, Rg, Rl, cf, nf, ua, va, ab = (E[k] for k in ('c', 'Rg', 'Rl', 'cf', 'nf', 'ua', 'va', 'ab'))
    ang = ring_angles(t.rim_cells['eye'], i0, i1, k0, k1)
    if ey.get('face'):
        # W2o: a spoke through each tip (the corners on the face, the margin ring holding them)
        a0 = ang.copy()
        ang = spokes_on_tips(ang, E)
        log(f'[cage] W2o the spokes on the tips: medial {np.degrees(E["a_tip"]["medial"]):.1f} deg, lateral '
            f'{np.degrees(E["a_tip"]["lateral"]):.1f} deg in the chart; the spokes moved by at most '
            f'{np.degrees(np.max(np.abs((ang - a0 + np.pi) % (2 * np.pi) - np.pi))):.1f} deg')
        se_raw = ey.get('spoke_even') or 0
        se_, se_frac = (int(se_raw[0]), float(se_raw[1])) if isinstance(se_raw, (tuple, list)) else (int(se_raw), None)
        if se_ > 0:
            a1 = ang.copy()
            ang = even_spokes(ang, E['a_tip']['medial'], se_, se_frac)
            log(f'[cage] W2t the spokes even from the medial tip over the rim\'s top-medial corner to the top side\'s cell '
                f'{se_} (every ring): the corner cell at {np.degrees(ang[0]) % 360.0:.1f} deg in the chart (the square\'s '
                f'135), spokes moved by at most {np.degrees(np.max(np.abs((ang - a1 + np.pi) % (2 * np.pi) - np.pi))):.1f} '
                f'deg')
    m = len(ang)
    r_m = polar_radius(E['fis'], ang)
    assert np.isfinite(r_m).all(), 'the fissure must be star-shaped round its centre'
    A_, B_ = (ab[0] + ey['pad'][0]) / ab[0], (ab[1] + ey['pad'][1]) / ab[1]

    def rim_radius(a_):
        """the rim's chart radius at the angles a_ (the pad's ellipse, the W2q env, 1.25 of the margin's)"""
        rr_ = 1.0 / np.sqrt((np.cos(a_) / A_) ** 2 + (np.sin(a_) / B_) ** 2)
        rm_ = polar_radius(E['fis'], a_)
        if E.get('fis_env') is not None:
            # W2q: the rim as far outside the lids at their largest fitted gaze as the pad puts it outside the rest lids
            # (the socket stays where the up-gazing lids need it: framed on the rest lids alone, the rim's top came down
            # onto the reference over the globe, W2p's probe g25)
            re_ = polar_radius(E['fis_env'], a_)
            ok_ = np.isfinite(re_)
            rr_ = np.where(ok_ & (re_ > rm_), np.maximum(rr_, re_ + ey.get('env_pad', 1.0) * (rr_ - rm_)), rr_)
        return np.maximum(rr_, 1.25 * rm_)
    r_rim = rim_radius(ang)
    spoke = np.column_stack([np.cos(ang), np.sin(ang)])

    def X(r_):
        """the chart's points at radii r_ on the spokes, 3D on the chart's plane"""
        S_ = r_[:, None] * spoke * ab
        return cf + S_[:, :1] * ua + S_[:, 1:2] * va

    def radial(P_, rmin):
        """P_ pushed out from the globe's centre to at least rmin"""
        D_ = P_ - c
        n_ = np.linalg.norm(D_, axis=1, keepdims=True)
        return c + D_ / n_ * np.maximum(n_, rmin)
    P = {}
    # the MARGIN: the traced fissure at the spokes (on the lid's sphere; at the canthi on the face)
    P['margin'] = polar_points(E['fis'], E['fis3'], ang)
    rho_m = np.linalg.norm(P['margin'] - c, axis=1)
    # the RIM: on the face along -nf (the face round the eye faces the fissure's plane: no grazing there)
    Xr = X(r_rim)
    H = ref.cross(Xr + 45.0 * nf, np.tile(-nf, (m, 1)), reach=90.0, step=0.2, outward=False)
    miss = ~np.isfinite(H).all(1)
    if miss.any():
        H[miss] = ref.project(Xr[miss])
    # held at most rim_cap mm out from the lid's sphere (the eye set in, not pitted: the reference's cheek and muzzle side
    # stand 8-20 mm proud of the lids medially and ventrally, W2i's 'arch skin in front of the globe')
    rr_ = np.linalg.norm(H - c, axis=1, keepdims=True)
    P['rim'] = c + (H - c) * np.minimum(1.0, (Rl + ey['rim_cap']) / rr_)
    # the LIDS between the margin and the rim along each spoke: on the lid's sphere where the chord dips under it, the
    # outer ring carried onto the face (the reference's closest point) and kept off the lid's sphere
    P['lid_mid'] = radial(P['margin'] + ey['f_mid'] * (P['rim'] - P['margin']), Rl + 0.1)
    # (c8: the outer ring on the lid's sphere + lid_out mm, the lids hugging the globe; c7f set it half way to the face,
    # 21-35 mm out medially and ventrally, a cliff at the bowl's lip: the free rim and the fit's fairness make that rise)
    P['lid_out'] = radial(P['margin'] + ey['f_out'] * (P['rim'] - P['margin']), Rl + ey['lid_out'])
    # W2k: THE ORBIT'S RINGS between the lids' outer ring and the rim (EYE orb, orb_s): on each spoke at the chart radius
    # orb of the way from the lids' outer ring's to the rim's, the face there (the reference cast along -nf, as the rim)
    # held at orb_s of the way from the lids' outer ring's distance from the globe's centre to the face's: the outer ring
    # follows the face (its orb_s ~1), the inner one takes the climb's middle. (k2c-d set both radially from the globe's
    # centre between the outer ring and the rim: the face is no sphere round the globe, and the outer ring stood over it
    # in a lip round the eye)
    ra_ = np.linalg.norm(P['lid_out'] - c, axis=1)
    r_lo = np.linalg.norm(((P['lid_out'] - cf) - ((P['lid_out'] - cf) @ nf)[:, None] * nf) @ np.column_stack([ua, va]) /
                          ab, axis=1)

    def face_at(r_):
        Xo = X(r_)
        Ho = ref.cross(Xo + 45.0 * nf, np.tile(-nf, (m, 1)), reach=90.0, step=0.2, outward=False)
        mo = ~np.isfinite(Ho).all(1)
        if mo.any():
            Ho[mo] = ref.project(Xo[mo])
        return Ho
    keep_ = bool(ey.get('keep_chart'))

    def on_spoke(Q_, r_):
        """W2r: Q_ moved back onto its spoke at the chart radius r_, its height along the eye's axis kept"""
        return X(r_) + ((Q_ - cf) @ nf)[:, None] * nf[None]
    for nm, f_, s_ in (('orb_in', ey['orb'][0], ey['orb_s'][0]), ('orb_out', ey['orb'][1], ey['orb_s'][1])):
        Ho = face_at(r_lo + f_ * (r_rim - r_lo))
        rf_ = np.linalg.norm(Ho - c, axis=1)
        rr_t = np.minimum(ra_ + s_ * (rf_ - ra_), Rl + ey['rim_cap'])
        P[nm] = c + (Ho - c) * (rr_t / rf_)[:, None]
        if keep_:
            P[nm] = on_spoke(P[nm], r_lo + f_ * (r_rim - r_lo))
    # the lids' outer ring itself starts the climb (lid_rise of the way from the lid's sphere to the face there): a
    # profile convex from the margin out, no groove at the climb's foot (the fissure gate's closing reads such a groove
    # as the opening: W2k k2e-f)
    Hl = face_at(r_lo)
    rfl = np.linalg.norm(Hl - c, axis=1)
    rl_t = np.maximum(ra_ + ey['lid_rise'] * (rfl - ra_), ra_)
    P['lid_out'] = c + (P['lid_out'] - c) * (rl_t / ra_)[:, None]
    if keep_:
        # W2r (EYE keep_chart): the radial holds and lifts above (the orbit's rings held at orb_s of the climb toward the
        # globe's centre, the lids' outer ring lifted lid_rise of it away from the centre) also moved each point across
        # the chart, the lifted ring outward and the held ones inward: on the _w2q5 cage the lids' outer ring stood
        # 0.3-1.9 mm farther out along spokes 16-23 (the lower lid) than the orbit's inner ring outside it, so the
        # tube folded back between them (check_w2r/ring_gate.py W2R_ORDER; W2p's fin3 none, W2o's beak at 15-17). Each
        # keeps its chart radius (the rings nested out along every spoke) and takes the height the radial rule gives it
        P['lid_out'] = on_spoke(P['lid_out'], r_lo)
    fc_ = ey.get('face') or {}
    w_on = smooth01((rho_m - (Rl + 0.3)) / 1.5)
    if fc_ and w_on.max() > 0.0 and ey.get('on_face'):
        # W2r (the lead's call 1: "the lid's and the orbit's outer rings stay on the skin side of the margin"): the rings
        # go onto the face only where the margin itself lies ON the face (W2o's corners on the face: the margin past the
        # lid sphere was the photos' loops carried onto the face). The W2q rest lids are the photos' loops turned back to
        # the rest gaze about the canthus axis, which carries their stretch past the lid sphere under the face: on the
        # _w2q5 cage the lower lid's outer third (spoke 16) lay 3.5 mm under the reference (5.8 mm behind it along the
        # eye's axis) while its rings went onto the face: a wall 84 deg over the margin (check_w2r/ring_gate.py), the
        # slot under the lower lid that forks the outer corner. Where the face stands more than on_face[0] mm in front of
        # the margin along the eye's axis (none past on_face[0] + on_face[1]) the rings climb from the margin as they do
        # over the globe (lid_mid by the margin, lid_out lid_rise of the way up, the orbit's rings orb_s of the way)
        Hm_ = ref.cross(P['margin'] + 45.0 * nf, np.tile(-nf, (m, 1)), reach=90.0, step=0.2, outward=False)
        dm_ = np.where(np.isfinite(Hm_).all(1), (Hm_ - P['margin']) @ nf, 0.0)
        of_ = ey['on_face']
        w_mf = 1.0 - smooth01((dm_ - of_[0]) / of_[1])
        past_ = w_on > 0.05
        off_ = past_ & (w_mf < 0.95)
        w_on = w_on * w_mf
        log(f'[cage] W2r the rings onto the face only where the margin lies on it: {int(off_.sum())} of '
            f'{int(past_.sum())} spokes past the lid sphere have the face '
            + (f'{float(dm_[off_].min()):.1f}-{float(dm_[off_].max()):.1f}' if off_.any() else '-')
            + ' mm in front of the margin along the eye\'s axis; their rings climb from it')
    if fc_ and w_on.max() > 0.0:
        # W2o (the lead's call 1: "make place_eye's lid and orbit rings follow the corners"): where the margin runs on the
        # face (past the globe, the corners carried to the canthi; w_on: its distance from the globe's centre past the lid
        # sphere) the lids are skin converging on the canthus, so their rings and the orbit's lie ON the face (the
        # reference along the eye's axis through each ring point), not held under it as the socket's fold round the
        # globe is: held, they made a channel past the lateral tip and a pit above it (probes o2-o4)
        for nm_ in ('lid_mid', 'lid_out', 'orb_in', 'orb_out'):
            Hf = ref.cross(P[nm_] + 45.0 * nf, np.tile(-nf, (m, 1)), reach=90.0, step=0.2, outward=False)
            ok_ = np.isfinite(Hf).all(1)
            Hf[~ok_] = P[nm_][~ok_]
            Hf = radial(Hf, Rl + 0.1)
            P[nm_] = P[nm_] + w_on[:, None] * (Hf - P[nm_])
    # the ROLL: radially under the margin, onto the globe where the margin sits on the lid's sphere, `corner` mm under the
    # margin where it sits on the face (the canthi: a shallow recess, not a slot)
    w_face = smooth01((rho_m - (Rl + 0.3)) / 1.5)
    rho_r = np.minimum((1.0 - w_face) * (Rg - ey['inset']) + w_face * (rho_m - ey['corner']), rho_m - 0.3)
    P['roll'] = c + rho_r[:, None] * (P['margin'] - c) / rho_m[:, None]
    fc_ = ey.get('face') or {}
    if fc_.get('roll', 0.0) > 0.0:
        # W2o: where the margin runs on the face (the corners carried to the canthi) its roll goes `roll` mm straight back
        # along the eye's axis, the inside of each corner a steep pocket (the conjunctival fornix runs back along the
        # orbit) that the front cameras see edge-on and in shadow, as the photos' dark corners; radially toward the
        # globe's centre (`corner` mm) it left a long floor sloping from the canthus to the sac, lit (probe o2: the
        # tongue at the inner corner)
        # W2p (the lead's call 1, "the lateral corner becomes a soft slope (no cliff, no beak)"): each corner its own
        # depth (`roll_lateral`, `roll_medial`, default `roll`), blended across the chart by the spoke's side (its cosine:
        # the lateral tip at +0.82, the medial at -0.82): at the lateral corner the 4 mm pocket under the face read as
        # a slit between two lit lips in every front camera (the W2o fresh eyes' beak; W2n's outer end, no pocket, was
        # the good one)
        rl_ = np.full(m, float(fc_['roll']))
        if 'roll_lateral' in fc_ or 'roll_medial' in fc_:
            w_lat = smooth01((np.cos(ang) + 0.3) / 0.6)
            rl_ = (float(fc_.get('roll_medial', fc_['roll'])) * (1.0 - w_lat)
                   + float(fc_.get('roll_lateral', fc_['roll'])) * w_lat)
        P['roll'] = (1.0 - w_face)[:, None] * P['roll'] + w_face[:, None] * (P['margin'] - rl_[:, None] * nf[None])
    # the SAC: inside the globe along the chart's rays at `sac` of the margin's radius (held where they meet the globe
    # well inside its outline)
    r_s = ey['sac'] * r_m
    for _ in range(16):
        Hs, rho_s = ray_sphere(X(r_s) + 45.0 * nf, -nf, c, Rg)
        r_s = np.where(~np.isfinite(Hs).all(1) | (rho_s > 0.8 * Rg), 0.9 * r_s, r_s)
    Hs, _ = ray_sphere(X(r_s) + 45.0 * nf, -nf, c, Rg)
    Hs = np.where(np.isfinite(Hs), Hs, c + nf * Rg)
    P['sac'] = c + (Hs - c) * ((Rg - ey['sac_in']) / Rg)
    # W2n (the lead's call 4; CANID_HEAD_STUDY 6: "the upper lid carries a crease line parallel above its margin ... the
    # medial canthus continues as a short notch toward the nose"). THE UPPER LID'S CREASE (EYE crease: depth mm, the
    # spoke's sine where it starts and where it is full): the lids' outer ring (2-3 mm above the margin) sunk toward the
    # globe's centre over the upper arc, kept outside the lid's sphere, and creased semi-sharp there (SHARP crease,
    # creases()): the fold where the lid's roll meets the skin rising to the brow. THE MEDIAL NOTCH (EYE notch: depth mm,
    # half angle deg): the rings beyond the medial tip (the lids' outer ring and the orbit's two, x 1 / 0.75 / 0.4) sunk
    # along -nf on the spokes within the half angle of the tip's direction in the chart: a short groove continuing the
    # medial corner toward the nose (the tear duct's line). Both off at depth 0
    cr = ey.get('crease', (0.0, 0.25, 0.7))
    w_cr = smooth01((np.sin(ang) - cr[1]) / max(cr[2] - cr[1], 1e-6)) if cr[0] > 0.0 else np.zeros(m)
    if cr[0] > 0.0:
        D_ = P['lid_out'] - c
        n_ = np.linalg.norm(D_, axis=1)
        P['lid_out'] = c + D_ * (np.maximum(n_ - cr[0] * w_cr, Rl + 0.1) / n_)[:, None]
    t.eye_crease_w = w_cr
    nt = ey.get('notch', (0.0, 18.0))
    if nt[0] > 0.0:
        tm3 = np.asarray(E['tips']['medial'], np.float64)          # (W2o: the chart's own tips, EYE face)
        a_t = np.arctan2(((tm3 - cf) @ va) / ab[1], ((tm3 - cf) @ ua) / ab[0])
        dang = np.abs((ang - a_t + np.pi) % (2.0 * np.pi) - np.pi)
        w_nt = smooth01(1.0 - dang / np.radians(nt[1]))
        for nm_, k_ in (('lid_out', 1.0), ('orb_in', 0.75), ('orb_out', 0.4)):
            P[nm_] = P[nm_] - (nt[0] * k_ * w_nt)[:, None] * nf[None]
        log(f'[cage] W2n the medial notch: {nt[0]:.1f} mm on {int((w_nt > 0.01).sum())} spokes about the tip\'s direction '
            f'({np.degrees(a_t):.0f} deg in the chart)')
    if cr[0] > 0.0:
        log(f'[cage] W2n the upper lid\'s crease: the lids\' outer ring sunk up to {cr[0]:.1f} mm on '
            f'{int((w_cr > 0.01).sum())} spokes, creased {SHARP.get("crease", 0.0):.1f}')
    rise = float(ey.get('rise', 0.0))
    if rise > 0.0:
        # W2p (the successor head builder): THE RINGS RISE OUTWARD OVER THE GLOBE. Where the margin rides the globe (1 -
        # w_on), each ring outward from the lids' outer one (the orbit's two, the rim) stands at least `rise` mm farther
        # from the globe's centre than the ring inside it: the lid's skin rolls out over the ball, never back into it.
        # (The orbit's rings and the rim are cast onto the reference, whose own eye opening lies within ~0.2 mm of the
        # globe over its top: with the lids turned to rest gaze (EYE face gaze) the upper ones followed it inside the
        # globe, probe g25, and the ball showed through the upper lid)
        w_g = 1.0 - w_on
        prev = np.linalg.norm(P['lid_out'] - c, axis=1)
        n_push = 0
        for nm_ in ('orb_in', 'orb_out', 'rim'):
            D_ = P[nm_] - c
            n_ = np.linalg.norm(D_, axis=1)
            need = np.maximum(prev + rise - n_, 0.0) * w_g
            n_push += int((need > 0.01).sum())
            P[nm_] = c + D_ * ((n_ + need) / n_)[:, None]
            prev = n_ + need
        log(f'[cage] W2p the rings rise outward over the globe ({rise:.1f} mm a ring): {n_push} ring points lifted')
    rs_ = ey.get('rim_slide')
    if rs_:
        # W2s (the lead's call 4, the medial crease): THE RIM'S TOP-MEDIAL CORNER MOVED FORWARD ALONG THE RIM (EYE rim_slide:
        # deg in the chart, the ring cells re-spaced evenly to the top side's rs_[1]-th cell and the medial side's
        # rs_[2]-th). Above the medial canthus the rim's forward edge runs at slope 0.4-0.7 in (d, q) where the side grid's
        # rows run at ~1.0: that stretch lay on the block's column 24 (i0), so the side quads R[2-4, 23-24] were inverted
        # in the TARGETS, before any fit (crease_q.py, cage_src.py), and the limit folded along them 10 mm from the
        # medial canthus: 0.3-1.0 mm2 of skin seen from inside in every pose, in W2r too (the failure W2k met at this
        # corner; pulling the corner in along its spoke made it worse: 2.9 mm2, probe c1). Sliding the rim's own points
        # along the rim gives that stretch to the block's top row, which runs with the side grid's rows. The lids, the
        # orbit's rings and the spokes stay: only the rim's vertices move, along the same curve
        a_ = ang[0] - ((ang[0] - ang) % (2.0 * np.pi))
        ac_ = a_[0] + np.radians(rs_[0])
        a_r = a_.copy()
        a_r[0] = ac_
        for j in range(1, int(rs_[1])):
            a_r[j] = ac_ + (a_[int(rs_[1])] - ac_) * j / rs_[1]
        for j in range(1, int(rs_[2])):
            a_r[m - j] = (ac_ - 2.0 * np.pi) + (a_[m - int(rs_[2])] - (ac_ - 2.0 * np.pi)) * j / rs_[2]
        r_r = rim_radius(a_r)
        Xs_ = cf + (r_r * np.cos(a_r) * ab[0])[:, None] * ua + (r_r * np.sin(a_r) * ab[1])[:, None] * va
        Hs_ = ref.cross(Xs_ + 45.0 * nf, np.tile(-nf, (m, 1)), reach=90.0, step=0.2, outward=False)
        ms_ = ~np.isfinite(Hs_).all(1)
        if ms_.any():
            Hs_[ms_] = ref.project(Xs_[ms_])
        rr_s = np.linalg.norm(Hs_ - c, axis=1, keepdims=True)
        P['rim'] = c + (Hs_ - c) * np.minimum(1.0, (Rl + ey['rim_cap']) / rr_s)
        log(f'[cage] W2s the rim\'s top-medial corner moved {rs_[0]:.0f} deg forward along the rim, {int(rs_[1])} + '
            f'{int(rs_[2])} cells re-spaced')
    names = L['tubes']['eye']
    # the RIM held (c8a left it free in a low-weight orbit zone: the face under the eye sagged into a draped pit)
    for j, v in enumerate(t.rim['eye']):
        C.put(v, P['rim'][j], 'the eye\'s RIM (an ellipse round the traced fissure in its plane, EYE pad) on the face, held '
                              'within EYE rim_cap of the lid\'s sphere')
    src = dict(orb_out='the ORBIT\'s outer transition ring (EYE orb: the face rolling into the socket)',
               orb_in='the ORBIT\'s inner transition ring (EYE orb: the socket rolling onto the lids)',
               lid_out='the lids\' outer surface (the lid\'s sphere, half on the face)',
               lid_mid='the lids\' surface by the margin (the lid\'s sphere)',
               margin='the LID MARGIN on the traced fissure (EYE_FISSURES through w12\'s and w08\'s solved cameras, its '
                      'corners drawn out to the photos\' canthi) on the lid\'s sphere',
               roll='the margin\'s ROLL onto the globe (a shallow recess at the canthi)',
               sac='the conjunctival SAC inside the globe')
    for nm, ring in zip(names, t.tubes['eye']):
        for j, v in enumerate(ring):
            C.put(v, P[nm][j], src[nm])
    # the enclosed vertices: inside the globe, by their grid position in a small ellipse of the chart, deep
    ic, kc = 0.5 * (i0 + i1), 0.5 * (k0 + k1)
    for (i, k), v in zip(t.inner_cells['eye'], t.inner['eye']):
        su = (i - ic) / (0.5 * (i1 - i0)) * ey['core'] * ab[0]
        sv = (kc - k) / (0.5 * (k1 - k0)) * ey['core'] * ab[1]
        Xp = cf + su * ua + sv * va
        Hi, _ = ray_sphere((Xp + 45.0 * nf)[None], -nf, c, Rg)
        Hi = Hi[0] if np.isfinite(Hi).all() else c + nf * Rg
        C.put(v, c + 0.55 * (Hi - c), 'inside the globe (the sac closed)')
    if E.get('follow') is not None:
        # W2q: THE EYE RIG (EYE_RIG): each eye vertex's lid-follow weight (its ring's, times canid_hull.lid_taper along
        # the canthus axis) and its upper-lid share (its spoke's side of the tip-to-tip line in the chart; the enclosed
        # core by its own chart position), for pose_eye and the runtime's lid-follow
        from . import canid_hull as CH
        ax = E['follow']['ax']
        tc_ = {k: np.array([((E['tips'][k] - cf) @ ua) / ab[0], ((E['tips'][k] - cf) @ va) / ab[1]])
               for k in ('medial', 'lateral')}
        tl_ = tc_['lateral'] - tc_['medial']
        n_tl = np.array([-tl_[1], tl_[0]]) / np.linalg.norm(tl_)
        n_tl = n_tl if n_tl[1] > 0 else -n_tl
        band = float(EYE_RIG['band'])
        u_sp = smooth01((spoke @ n_tl) / band + 0.5)
        ids_, w_, u_, ws_ = [], [], [], []
        for nm, ring in [('rim', t.rim['eye'])] + list(zip(names, t.tubes['eye'])):
            Pr = P[nm]
            s_, _, _ = CH.cyl(ax, Pr)
            ids_ += list(ring)
            w_ += list(EYE_RIG[nm] * CH.lid_taper(ax, s_))
            u_ += list(u_sp)
            # (W2r: the horizontal follow's weight, the ring's weight x canid_hull.slide_taper; W2s: in the warp mode
            # the ring's own slide weight (EYE_RIG_SLIDE, default its EYE_RIG weight) alone, canid_hull.slide_weight)
            ws_ += list(EYE_RIG_SLIDE.get(nm, EYE_RIG[nm]) * CH.slide_weight(ax, s_))
            if nm == 'margin':
                # (the margin loop's own weights, in the loop's order: w02 poses the 'lid margin' loop with them; W2r:
                # the third column the slide's)
                t.eye_margin_rig = np.column_stack([EYE_RIG[nm] * CH.lid_taper(ax, s_), u_sp,
                                                    EYE_RIG_SLIDE.get(nm, EYE_RIG[nm]) * CH.slide_weight(ax, s_)])
        Pin = np.array([C.P[v] for v in t.inner['eye']])
        uv_in = np.column_stack([((Pin - cf) @ ua) / ab[0], ((Pin - cf) @ va) / ab[1]])
        s_in, _, _ = CH.cyl(ax, Pin)
        ids_ += list(t.inner['eye'])
        w_ += list(EYE_RIG['inner'] * CH.lid_taper(ax, s_in))
        ws_ += list(EYE_RIG_SLIDE.get('inner', EYE_RIG['inner']) * CH.slide_weight(ax, s_in))
        u_ += list(smooth01(((uv_in - tc_['medial']) @ n_tl) / band + 0.5))
        t.eye_rig = dict(ids=np.asarray(ids_, int), w=np.asarray(w_, float), up=np.asarray(u_, float),
                         ws=np.asarray(ws_, float))
        # the quads from the margin inward (the opening's: the margin's roll, the sac, the core)
        sel_ = set(t.tubes['eye'][names.index('margin')]) | set(t.tubes['eye'][names.index('roll')]) | \
            set(t.tubes['eye'][names.index('sac')]) | set(t.inner['eye'])
        t.eye_inner_quads = np.array([j for j, q in enumerate(t.Qh) if all(int(v) in sel_ for v in q)], int)
        log(f'[cage] W2q the eye rig: {len(ids_)} vertices weighted (follow upper {E["follow"]["f_upper"]:.2f}, lower '
            f'{E["follow"]["f_lower"]:.2f} about the canthus axis; rest theta {E["follow"]["theta_rest"]:+.1f} deg); '
            f'{len(t.eye_inner_quads)} quads inside the margin')
    t.loops['lid margin'] = list(t.tubes['eye'][names.index('margin')])
    t.loops['lid outer'] = list(t.tubes['eye'][names.index('lid_out')])
    t.loops['orbit outer'] = list(t.tubes['eye'][names.index('orb_out')])
    t.loops['eye rim'] = list(t.rim['eye'])
    on_lid = np.abs(rho_m - Rl) < 0.05
    log(f'[cage] the eye: the fissure {2 * ab[0]:.1f} x {2 * ab[1]:.1f} mm, the rim {2 * (ab[0] + ey["pad"][0]):.1f} x '
        f'{2 * (ab[1] + ey["pad"][1]):.1f} on the chart, the margin (the traced fissure) on the lid\'s sphere at '
        f'{int(on_lid.sum())} of {m} spokes, the rest {float(rho_m.min()):.1f}-{float(rho_m.max()):.1f} mm from the globe\'s '
        f'centre (the lid\'s sphere {Rl:.1f}); the roll {float((rho_m - rho_r).min()):.1f}-{float((rho_m - rho_r).max()):.1f} '
        f'mm under the margin')
    return dict(P=P, chart=E, ang=ang)


def ear_base(spec, ref, log=print):
    """W2y: the left ear's foot on the REFERENCE's skin (EAR_PORT): canid.ear_shell built over the reference (its skin
    search on the reference's field, the cage's own surface: the closed head is built FROM the cage), the sheet's base
    section (its row n_sink: where each column enters the skin) moved ht_low mm toward the pinna's back. Returns dict(
    outer: the outer face's foot at the port's columns (cols, 3), cols (sheet column ids), n_open (the opening, palate
    (d, q, x)), sheet (nr, ns, 3) and ht (nr, ns) mm, n_sink), palate (d, q, x) mm"""
    from . import canid, canid_hull as CH
    ep = EAR_PORT
    npn = 1000.0 * canid.nose_p(spec)
    qline = np.arange(95.0, -60.0, -0.25)
    dors = np.asarray(CH.PROFILE, np.float64)[CH.PROFILE_BACK[1]:][::-1]

    def surface_q(d, x):
        f = ref(np.column_stack([np.full(len(qline), d), qline, np.full(len(qline), x)]))
        j = int(np.argmax(f < 0))
        if f[j] >= 0 or j == 0:
            return float(np.interp(d, dors[:, 0], dors[:, 1]))
        return float(qline[j - 1] + 0.25 * f[j - 1] / (f[j - 1] - f[j]))
    surface_q.phi = lambda P: ref(np.asarray(P, np.float64))
    V_, F_, ht_, _ = canid.ear_shell(spec, 1, surface_q)
    F_ = np.asarray(F_)
    ns = int(F_[0][2] - 1) if F_[0][0] == 0 else int(F_[0][0] - 1)
    G = np.asarray(V_, np.float64).reshape(-1, ns, 3) * 1000.0
    G = np.stack([npn - G[..., 0], G[..., 1], G[..., 2]], -1)
    H = np.asarray(ht_, np.float64).reshape(-1, ns) * 1000.0
    ez = canid.ear_face_frame(spec, 1)[3]
    n_open = np.array([-ez[0], ez[1], ez[2]])
    n = np.cross(np.gradient(G, axis=0), np.gradient(G, axis=1))
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-12)
    if float(np.mean(n.reshape(-1, 3) @ n_open)) < 0.0:
        n = -n
    eh = canid.HEAD['ear']
    n_sink = max(2, int(np.ceil(eh['sink'] / eh['facet'])))
    cols = np.unique(np.round(np.linspace(0, ns - 1, ep['cols'])).astype(int))
    assert len(cols) == ep['cols'], (len(cols), ns)
    outer = G[n_sink, cols] - np.minimum(H[n_sink, cols], ep['ht_low'])[:, None] * n[n_sink, cols]
    log(f'[cage] W2y the ear\'s foot on the reference: sheet {G.shape[0]} x {ns}, base row {n_sink}; the outer foot d '
        f'{outer[:, 0].min():.1f}-{outer[:, 0].max():.1f}, |x| {outer[:, 2].min():.1f}-{outer[:, 2].max():.1f}, q '
        f'{outer[:, 1].min():.1f}-{outer[:, 1].max():.1f} mm; the sheet\'s base row off the reference |f| max '
        f'{np.abs(ref(G[n_sink])).max():.2f} mm')
    return dict(outer=outer, cols=cols, n_open=n_open, sheet=G, ht=H, n_sink=n_sink)


def place_ear(C, ref, spec, log=print):
    """W2y: THE EAR'S PORT (LAYOUT ear_b / ear_k, EAR_PORT): the ROOT on the ear's foot (ear_base: the outer face's foot
    round the C from the medial foot to the lateral, then the chord across the concha's mouth, bowed out of it), the RIM
    (the block's square ring) `margin` mm outside it on the skin, the middle ring between, the enclosed floor (the concha's
    floor under the cup, buried under the pinna's clay at its band) a Coons patch of the root's sides; EAR_PORT hold held
    in the fit. The grid round it relaxed in a window (build_cage). Returns dict(root, rim, mid (m, 3) mm, eb: ear_base)"""
    t = C.t
    L = LAYOUT
    ep = EAR_PORT
    eb = ear_base(spec, ref, log)
    (b0, b1), (k0, k1) = L['ear_b'], L['ear_k']
    i0, i1 = t.nA + b0, t.nA + b1
    ni, nk = i1 - i0, k1 - k0
    m = len(t.rim['ear'])
    no = len(eb['outer'])
    assert m == 2 * (ni + nk) and no == 2 * ni + nk + 1, (m, ni, nk, no)
    # the root: the outer face's foot (j 0 .. 2 ni + nk: top, back, bottom sides), then the chord's inner points back to
    # the medial foot (the front side)
    nc = m - (no - 1)
    ch = eb['outer'][-1][None] + (np.arange(1, nc) / nc)[:, None] * (eb['outer'][0] - eb['outer'][-1])[None]
    # (the chord bowed out of the concha, away from the outer face's middle, by `bow` of its length (a parabola): the
    # port's corners at the feet opened from acute (check d3: the limit pleated along the medial foot's corner))
    s_ = np.arange(1, nc) / nc
    away = 0.5 * (eb['outer'][0] + eb['outer'][-1]) - eb['outer'][len(eb['outer']) // 2]
    away /= np.linalg.norm(away)
    clen = float(np.linalg.norm(eb['outer'][0] - eb['outer'][-1]))
    ch = ch + (4.0 * s_ * (1.0 - s_) * ep['bow'] * clen)[:, None] * away[None]
    root = ref.project(np.vstack([eb['outer'], ch]), it=12)
    # outward in the tangent plane, smoothed along the loop
    tg = np.roll(root, -1, 0) - np.roll(root, 1, 0)
    nr = ref.normal(root)
    out = np.cross(tg, nr)
    cen = root.mean(0)
    if float(np.sum(np.einsum('ij,ij->i', out, root - cen))) < 0.0:
        out = -out
    out /= np.linalg.norm(out, axis=1, keepdims=True)
    s = int(ep['smooth'])
    for _ in range(s):
        out = (np.roll(out, 1, 0) + 2.0 * out + np.roll(out, -1, 0)) / 4.0
        out -= np.einsum('ij,ij->i', out, nr)[:, None] * nr
        out /= np.linalg.norm(out, axis=1, keepdims=True)
    rim = ref.project(root + ep['margin'] * out, it=12)
    mid = ref.project(root + ep['mid'] * ep['margin'] * out, it=12)
    for j, v in enumerate(t.rim['ear']):
        C.put(v, rim[j], 'the ear port\'s RIM (EAR_PORT margin outside the root, on the skin)', fix='rim' in ep['hold'])
    names = L['tubes']['ear']
    P = dict(mid=mid, root=root)
    src = dict(mid='the ear port\'s middle ring (halfway from the root to the rim)',
               root='the ear\'s ROOT: the pinna\'s outer face along its foot on the skin (canid.ear_shell over the '
                    'reference) and the chord across the concha\'s mouth')
    for nm, ring in zip(names, t.tubes['ear']):
        for j, v in enumerate(ring):
            C.put(v, P[nm][j], src[nm], fix=nm in ep['hold'])
    # the floor: a Coons patch of the root's four sides (top j 0 .. ni, back ni .. ni + nk, bottom .. 2 ni + nk, front)
    top = lambda i: root[i - i0]                                  # noqa: E731
    right = lambda k: root[ni + (k - k0)]                         # noqa: E731
    bot = lambda i: root[ni + nk + (i1 - i)]                      # noqa: E731
    left = lambda k: root[(2 * ni + nk + (k1 - k)) % m]           # noqa: E731
    P00, P10, P11, P01 = top(i0), top(i1), bot(i1), bot(i0)
    for (i, k), v in zip(t.inner_cells['ear'], t.inner['ear']):
        u, w = (i - i0) / ni, (k - k0) / nk
        p = (1 - u) * left(k) + u * right(k) + (1 - w) * top(i) + w * bot(i) - \
            ((1 - u) * (1 - w) * P00 + u * (1 - w) * P10 + (1 - u) * w * P01 + u * w * P11)
        C.put(v, ref.project(p[None], it=12)[0], 'the ear port\'s floor (a Coons patch of the root; the concha\'s floor)',
              fix='floor' in ep['hold'])
    t.loops['ear root'] = list(t.tubes['ear'][names.index('root')])
    t.loops['ear rim'] = list(t.rim['ear'])
    sel_ = set(t.tubes['ear'][names.index('root')]) | set(t.inner['ear'])
    t.ear_inner_quads = np.array([j for j, q in enumerate(t.Qh) if all(int(v) in sel_ for v in q)], int)
    per = float(np.sum(np.linalg.norm(np.roll(root, -1, 0) - root, axis=1)))
    log(f'[cage] W2y the ear\'s port: the root {m} vertices round the ear\'s foot ({per:.0f} mm; the outer face {no - 1} '
        f'cells, the chord {nc}), the rim {ep["margin"]:.0f} mm outside it (d {rim[:, 0].min():.0f}-{rim[:, 0].max():.0f}, '
        f'q {rim[:, 1].min():.0f}-{rim[:, 1].max():.0f}, |x| {rim[:, 2].min():.0f}-{rim[:, 2].max():.0f}), '
        f'{len(t.ear_inner_quads)} floor quads inside the root')
    return dict(root=root, rim=rim, mid=mid, eb=eb)


def place_lip(C, ref, log=print):
    """THE LIP's margin across the face cap (ring lip_k's front segment: from the midline's row to the first station's
    side, on the reference) and the groove and the lower lip under it along the front and the side (LIP rows), tucked in
    along the inward normal, faded out behind the commissure"""
    from . import canid_hull as CH
    t = C.t
    L = LAYOUT
    nA, nB = t.nA, t.nB
    lk = L['lip_k']
    st = np.asarray(L['stations'])
    ll = np.asarray(CH.LIP_LINE, np.float64)
    d_comm = float(ll[-1, 0])
    # the front segment: the midline row's point (the face cap's midline) to the side's first station, on the reference
    P0, P1 = C.P[t.R[lk, 0]].copy(), C.P[t.R[lk, nA]].copy()
    for i in range(1, nA):
        u = i / nA
        d_ = P0[0] + (P1[0] - P0[0]) * u ** 1.6
        q_ = P0[1] + (P1[1] - P0[1]) * u
        A = np.array([[d_, q_, 0.0]])
        hit = ref.cross(A, np.array([[0.0, 0.0, 1.0]]), reach=60.0, step=0.2)[0]
        if not np.isfinite(hit).all():
            hit = ref.project(np.array([[d_, q_, P1[2] * u]]))[0]
        C.put(t.R[lk, i], hit, 'the upper lip\'s margin across the face (from the midline\'s lip point to LIP_LINE at the '
                               'first station, on the reference)')
    C.fixed[t.R[lk, 0]] = True
    t.loops['lip margin'] = [t.R[lk, i] for i in range(0, nA + 1)] + \
        [t.R[lk, nA + b] for b in range(1, nB + 1) if st[b] <= d_comm + 1e-9]
    # the groove and the lower lip under the margin (front and side), each its arc below the margin along the column (the
    # face cap's) or the station's section, inset along the inward normal
    rows_ = LIP['rows']
    for i in range(0, nA + nB + 1):
        if i > nA and st[i - nA] > d_comm + LIP['fade']:
            break
        col = np.array([C.P[t.R[k, i]] for k in range(lk, min(lk + 6, t.K) + 1)])
        s = arclen(col)
        fade = 1.0 if i <= nA else (1.0 - smooth01((st[i - nA] - d_comm) / LIP['fade']))
        for r_, (below, inset) in enumerate(rows_, start=1):
            p_ = np.array([np.interp(below, s, col[:, a]) for a in range(3)])
            p_ = ref.project(p_[None])[0]
            n_ = ref.normal(p_[None])[0]
            p_ = p_ - inset * fade * n_
            if i == 0:
                p_[2] = 0.0
            C.put(t.R[lk + r_, i], p_, 'the lip\'s groove under the margin (LIP rows)' if r_ == 1 else
                  'the lower lip\'s top under the upper lip\'s overhang (LIP rows)')
    log(f'[cage] the lip: the margin across the face and on LIP_LINE to the commissure (d {d_comm:.0f}), the groove and '
        f'the lower lip tucked in under it')


def place_philtrum(C, ref, log=print):
    """THE PHILTRUM: the midline column from row ph rows[0] (between the nostrils) down to the lip's margin recessed
    `depth` mm BACK into the face (+d), half that on the leather (above its bottom row), its neighbour column `side` of
    it. (c8b recessed along the reference's inward normal, which on the nose's underside points UP into the nose: the
    leather's bottom pinched into a notch that every column fanned into)"""
    t = C.t
    ph = LIP['philtrum']
    k0, k1 = ph['rows']
    kb = LAYOUT['leather_k'][1]

    def recess(v, f, w):
        p2 = C.P[v] + np.array([ph['depth'] * f * w, 0.0, 0.0])
        if f == 1.0:
            p2[2] = 0.0
        C.P[v] = p2
        C.fixed[v] = True
        C.src[int(v)] = 'the PHILTRUM: the midline recessed back into the face (LIP philtrum)'
    for k in range(k0, k1):
        w = smooth01((k - k0 + 1) / 2.5) * (0.5 if k < kb else 1.0)
        for i, f in ((0, 1.0), (1, ph['side'])):
            recess(t.R[k, i], f, w)
    # W2k: the leather's loops' bottom ends (between the cap's rows kb - 1 and kb on the midline: on the leather, half)
    if 'leather' in t.tubes:
        for ring in t.tubes['leather']:
            recess(ring[-1], 1.0, 0.5)
            recess(ring[-2], ph['side'], 0.5)
    log('[cage] the philtrum recessed')


def creases(C):
    """the semi-sharp creases (SHARP): the lip's margin (faded at the commissure), the leather's border (its top rolls
    onto the bridge without an edge), the nostril's edge, the lid margin"""
    from . import canid_hull as CH
    t = C.t
    L = LAYOUT
    sp = SHARP
    d_comm = float(np.asarray(CH.LIP_LINE)[-1, 0])
    lm = t.loops['lip margin']
    s_l = []
    for a, b in zip(lm[:-1], lm[1:]):
        d_ = 0.5 * (C.P[a, 0] + C.P[b, 0])
        s_l.append(sp['lip'] * (1.0 - smooth01((d_ - (d_comm - 12.0)) / 12.0)))
    t.crease(lm, s_l)
    lb = t.loops['leather border']
    # the leather's border creased along its BOTTOM only (the leather's underside meets the philtrum and the lip at an
    # edge in the profiles); its top rolls onto the bridge and its sides round into the muzzle without one (c7e's side
    # crease printed as a cut). W2k: the border is the leather's own loop, its bottom from the U's bottom-lateral corner
    bot_ids = set(int(v) for v in lb[t.leather_u['j_bl']:])
    s_b = [sp['leather'] if (int(a) in bot_ids and int(b) in bot_ids) else 0.0 for a, b in zip(lb[:-1], lb[1:])]
    t.crease(lb, s_b)
    # the opening's edge: crisp under the fold (its lip overhangs the opening), soft elsewhere (the leather rolls in)
    wf = np.asarray(t.nostril_wf, np.float64)
    c0, c1 = NOSTRIL['crease']
    t.crease(t.loops['nostril rim'], c0 + (c1 - c0) * 0.5 * (wf + np.roll(wf, -1)), closed=True)
    t.crease(t.loops['lid margin'], sp['lid'], closed=True)
    # W2n: the upper lid's crease (place_eye, EYE crease) along the lids' outer ring where it is sunk
    wc = np.asarray(getattr(t, 'eye_crease_w', np.zeros(0)), np.float64)
    if wc.size and wc.max() > 0.0 and sp.get('crease', 0.0) > 0.0:
        t.crease(t.loops['lid outer'], sp['crease'] * 0.5 * (wc + np.roll(wc, -1)), closed=True)


# ============================================================================================ build, fit, limit
def build_cage(spec, ref=None, log=print):
    """the cage's targets and creases: (Topo, Cage, extras)"""
    from . import canid_hull as CH, canid_nose as CN
    t0 = time.time()
    ref = reference(spec, log) if ref is None else ref
    topo = Topo()
    C = Cage(topo)
    L = LAYOUT
    st = L['stations']
    cons = station_contours(ref, st)
    place_stations(C, ref, cons, log)
    # the face cap's midline: the reference's midline in front of the first station
    top_q, bot_q = C.P[topo.T[0, 0], 1], C.P[topo.B[0, 0], 1]
    mid = midline_curve(ref, None, top_q, bot_q, st[0])
    tm = np.arange(len(mid)) * 0.25
    ll = np.asarray(CH.LIP_LINE, np.float64)
    pr = np.asarray(CH.PROFILE, np.float64)

    def s_near(dq):
        j = np.argmin(np.hypot(mid[:, 0] - dq[0], mid[:, 1] - dq[1]))
        return float(tm[j])
    # W2l: the nose on the clay's own frame: the level front chart (the nostril's comma) and the leather's border
    fr = CN.level_frame(spec)
    ltr = CN.border_curve(ref, L['leather_i'], *L['leather_k'])
    lm = leather_mid(ref, fr, ltr, mid)
    kt_, kb_ = L['leather_k']
    tip = CAP_ROWS['tip']
    an = {0: 0.0, topo.K: float(tm[-1])}
    an[tip] = s_near(pr[7])
    an[L['lip_k']] = s_near(ll[0])
    an[L['lip_k'] + 1] = an[L['lip_k']] + LIP['rows'][0][0]
    an[L['lip_k'] + 2] = an[L['lip_k']] + LIP['rows'][1][0]
    # W2k: the rows round the leather on its loops' midline ends (leather_mid): the U's top and bottom rows on the support
    # loop's, the leather's interior rows from one step inside its front loop's to the tip and on to its bottom
    an[kt_] = lm['sS0']
    an[kb_] = lm['sS1']
    an[kt_ + 1] = lm['sF0'] + (an[tip] - lm['sF0']) / (tip - kt_)
    an[kb_ - 1] = lm['sF1'] - (lm['sF1'] - an[tip]) / (kb_ - tip)
    place_face_cap(C, ref, mid, an, log)
    place_back_cap(C, ref, log)
    nA_, nB_, K_ = topo.nA, topo.nB, topo.K
    caps = np.zeros(topo.n_half, bool)
    for k in range(1, K_):
        caps[topo.R[k, :nA_]] = True
        caps[topo.R[k, nA_ + nB_ + 1:]] = True
    relax(C, ref, only=caps)
    # (W2k: the nostril first: the leather's front loop keeps clear of its rim)
    nost = place_nostril(C, ref, fr, spec, log)
    leather = place_leather(C, ref, fr, mid, lm, log, tr=ltr, nost=nost)
    place_lip(C, ref, log)
    relax(C, ref, only=caps)
    eye = place_eye(C, ref, spec, log)
    # the side relaxed round the eye's rim (its stations and rings within a window of the block), the caps round the
    # nostril and the leather
    (b0, b1), (k0, k1) = L['eye_b'], L['eye_k']
    win = np.zeros(topo.n_half, bool)
    for k in range(max(1, k0 - 4), min(K_, k1 + 5)):
        win[topo.R[k, nA_ + max(0, b0 - 4):nA_ + min(nB_, b1 + 4) + 1]] = True
    # (W2k: the dorsolateral line E1 itself over the eye's stations too (a = nA): the rim's top-medial corner lands above
    # it at station 12, and ring 1 between them folded (the crease up from the eye's inner corner); and a longer relax)
    for a in range(nA_ - 4, nA_ + 1):
        win[topo.T[a, max(1, b0 - 4):min(nB_ - 1, b1 + 4) + 1]] = True
    relax(C, ref, only=caps | win, iters=RELAX['eye_iters'])
    # W2y: THE EAR'S PORT, then the grid round it relaxed (EAR_PORT win: its stations and rings, the top patch's rows by E1
    # over them, the back cap's first columns behind the last station)
    ear = place_ear(C, ref, spec, log)
    ep = EAR_PORT
    (wb0, wb1), (wk0, wk1) = ep['win']
    win_e = np.zeros(topo.n_half, bool)
    for k in range(max(1, wk0), min(K_, wk1) + 1):
        win_e[topo.R[k, nA_ + wb0:min(topo.M - 1, nA_ + nB_ + 1 + ep['win_back'])]] = True
    for a in range(nA_ - 4, nA_ + 1):
        win_e[topo.T[a, wb0:nB_ + 1]] = True
    # (the port's rings stay put while the grid relaxes round them, then slide on the reference in the fit unless held:
    # check d1-d8 relaxed the free rim with the grid, which drew it onto the root over the top and the back)
    port = np.array(list(topo.rim['ear']) + [v for r in topo.tubes['ear'] for v in r] + list(topo.inner['ear']), int)
    fx0 = C.fixed[port].copy()
    C.fixed[port] = True
    relax(C, ref, only=win_e, iters=ep['iters'])
    C.fixed[port] = fx0
    place_philtrum(C, ref, log)
    creases(C)
    assert np.isfinite(C.P).all(), f'{int((~np.isfinite(C.P).all(1)).sum())} vertices without a target'
    hi_ = ref.lo + (np.array(ref.phi.shape) - 1) * ref.h
    bad = np.nonzero(~((C.P >= ref.lo - 1.0) & (C.P <= hi_ + 1.0)).all(1))[0]
    assert not len(bad), f'targets outside the reference\'s box: {[(int(v), C.src.get(int(v))) for v in bad[:6]]}'
    off = np.abs(ref(C.P[~C.fixed]))
    log(f'[cage] the free targets on the reference: |f| median {np.median(off):.3f}, max {off.max():.3f} mm')
    log(f'[cage] targets placed in {time.time() - t0:.0f}s: {topo.n_half} half-cage vertices, {len(topo.Qh)} quads, '
        f'{int(C.fixed.sum())} held on features')
    C.ref, C.spec = ref, spec
    return topo, C, dict(leather=leather, nostril=nost, eye=eye, ear=ear, mid=mid, ref=ref)


def zone_weight(P):
    """the reference's weight at P (n, 3) (FIT): w_free, down to w_zone inside each zone (its (d, q) box with smooth
    ramps, past |x| > x)"""
    fz = FIT
    w = np.ones(len(P))
    D, Q, Xa = P[:, 0], P[:, 1], np.abs(P[:, 2])
    for z in fz['zones']:
        b = (smooth01((D - z['d'][0]) / (z['d'][1] - z['d'][0])) * smooth01((z['d'][3] - D) / (z['d'][3] - z['d'][2])) *
             smooth01((Q - z['q'][0]) / (z['q'][1] - z['q'][0])) * smooth01((z['q'][3] - Q) / (z['q'][3] - z['q'][2])) *
             smooth01((Xa - z['x']) / 6.0))
        w = np.minimum(w, 1.0 - (1.0 - z.get('w', fz['w_zone']) / fz['w_free']) * b)
    return fz['w_free'] * w


def fit_cage(topo, C, levels=None, log=print):
    """THE FIT (FIT; the module's docstring): the full cage's control points V minimising
    sum_v w_v |A V - T|_v^2 + lam sum_v f_v |L V|_v^2 (A the limit points of the cage's vertices, subdiv_sharp's
    limit_operator with the creases; L the cage's umbrella Laplacian; w: features w_feat, the reference zone_weight; f 1,
    lam_crease / lam at crease vertices), in passes: each re-targets the free vertices at the reference's closest point
    to their limit point and any limit point within skin_min mm of the skull at its clearance (weight w_skull). Returns
    (the cage QuadMesh with the controls, the targets QuadMesh, mirror map, sharpness dict, report)"""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    fz = FIT
    levels = LEVELS['fit'] if levels is None else levels
    t0 = time.time()
    from . import canid_hull as CH
    ref, spec = C.ref, C.spec
    sk = skull_ref(spec, log)
    globes = [CH.lid_frame(spec, s_)['centre'] for s_ in ('L', 'R')]
    Rl_g = CH.lid_frame(spec, 'L')['R'] + EYE['lid']
    tgt, mir, sharp = topo.full(C.P)
    chk = tgt.check()
    assert chk['nonmanifold_edges'] == 0 and chk['boundary_edges'] == 0 and chk['flipped_or_dup_directed'] == 0, chk
    n = len(tgt.V)
    A, _ = SS.limit_operator(tgt, sharp, levels)
    E, _ = tgt.edges()
    Adj = sp.csr_matrix((np.ones(2 * len(E)), (np.concatenate([E[:, 0], E[:, 1]]), np.concatenate([E[:, 1], E[:, 0]]))),
                        shape=(n, n))
    deg = np.asarray(Adj.sum(1)).ravel()
    Lap = (sp.eye(n) - sp.diags(1.0 / deg) @ Adj).tocsr()
    fixed = np.zeros(n, bool)
    fixed[:topo.n_half] = C.fixed
    fixed[mir[:topo.n_half]] |= C.fixed
    on_crease = np.zeros(n, bool)
    for (a, b) in sharp:
        on_crease[a] = on_crease[b] = True
    f_w = np.where(on_crease, fz['lam_crease'] / fz['lam'], 1.0)
    w_ref = zone_weight(tgt.V)
    T = tgt.V.copy()
    w = np.where(fixed, fz['w_feat'], w_ref)
    mid = np.zeros(n, bool)
    mid[topo.midline()] = True
    LtL = (Lap.T @ sp.diags(f_w) @ Lap).tocsr()
    rep = {}
    V = tgt.V.copy()
    held = np.zeros(n, bool)
    for ps in range(fz['passes']):
        Wm = sp.diags(w)
        Sys = (A.T @ Wm @ A + fz['lam'] * LtL).tocsc()
        lu = spla.splu(Sys)
        rhs = A.T @ (w[:, None] * T)
        V = np.column_stack([lu.solve(rhs[:, k]) for k in range(3)])
        V[mid, 2] = 0.0
        P = A @ V
        dev = np.linalg.norm(P - T, axis=1)
        # re-target: the free vertices at the reference's closest point to their limit point; the skull's clearance
        fr_ = ~fixed
        Tn = T.copy()
        Tn[fr_] = ref.project(P[fr_], it=6)
        s = sk(P)
        g = sk.normal(P)
        # (the free surface only: the eye's sac and the nostril's canal are features that lie in or by the bone; pushing
        # their targets fought their own weights and the passes oscillated, c8d: 23 points 3 mm into the skull)
        close = fr_ & (s < fz['skin_min'])
        push = P + (fz['skin_min'] + 0.3 - s)[:, None] * g
        Tn[close] = push[close]
        # the clearance REMEMBERED: a point once held off the bone keeps its push and the skull's weight (in the cheek's
        # low-weight zone the fairness pulled a released point back 3 mm into the bone on every other pass, c8d), its
        # targets also held off the bone where the smoothed reference dips within skin_min of it
        sT = sk(Tn)
        closeT = fr_ & ~close & (sT < fz['skin_min'])
        Tn[closeT] = (Tn + (fz['skin_min'] + 0.3 - sT)[:, None] * sk.normal(Tn))[closeT]
        keep = held & ~close & ~closeT
        Tn[keep] = T[keep]
        held = held | close | closeT
        close = held
        # the globes: the free surface held globe_min mm outside each lid's sphere (the eye's own rings are features)
        gclose = np.zeros(n, bool)
        for gc in globes:
            Dg = P - gc
            ng = np.maximum(np.linalg.norm(Dg, axis=1), 1e-9)
            gc_ = fr_ & (ng < Rl_g + fz['globe_min'])
            Tn[gc_] = (gc + Dg / ng[:, None] * (Rl_g + fz['globe_min'] + 0.2))[gc_]
            gclose |= gc_
        w = np.where(fixed, fz['w_feat'], np.where(close, fz['w_skull'], np.where(gclose, fz['w_globe'], w_ref)))
        T = Tn
        T[mid, 2] = 0.0
        rep[f'pass{ps}'] = dict(feat_max=float(dev[fixed].max()), feat_p95=float(np.percentile(dev[fixed], 95)),
                                free_med=float(np.median(dev[fr_])), free_p95=float(np.percentile(dev[fr_], 95)),
                                skull_close=int(close.sum()), skull_min=float(s[fr_].min()), globe_close=int(gclose.sum()))
        log(f'[cage] fit pass {ps}: the features within {rep[f"pass{ps}"]["feat_max"]:.2f} mm of their targets (p95 '
            f'{rep[f"pass{ps}"]["feat_p95"]:.2f}), the free limit points {rep[f"pass{ps}"]["free_med"]:.2f} (median), '
            f'{rep[f"pass{ps}"]["free_p95"]:.2f} (p95) off theirs; {int(close.sum())} free limit points within '
            f'{fz["skin_min"]} mm of the skull (least {float(s[fr_].min()):.2f}), {int(gclose.sum())} within '
            f'{fz["globe_min"]} mm of a lid\'s sphere')
    # symmetric by construction; the mirror pairs averaged against round-off
    Vm = V.copy()
    Vm[mir[:topo.n_half]] = V[:topo.n_half] * np.array([1.0, 1.0, -1.0])
    V = 0.5 * (V + Vm)
    V[mid, 2] = 0.0
    rep['time'] = time.time() - t0
    rep['res'] = float(np.linalg.norm(A @ V - T, axis=1)[fixed].max())
    return QuadMesh(V, tgt.Q), tgt, mir, sharp, rep


def limit_surface(topo, C, levels=None, log=print):
    """the fitted cage (fit_cage) subdivided to its limit mesh; (cage QuadMesh with controls, sharp, limit QuadMesh,
    residual at the features, targets, mirror map)"""
    levels = LEVELS if levels is None else levels
    t0 = time.time()
    cage, tgt, mir, sharp, rep = fit_cage(topo, C, levels['fit'], log)
    lim, s_e, par, _ = SS.subdivide(cage, sharp, levels['out'])
    log(f'[cage] {len(cage.V)} cage vertices, {len(cage.Q)} quads, {len(sharp)} crease edges; fitted in {rep["time"]:.1f}s '
        f'(the features within {rep["res"]:.2f} mm) and subdivided {levels["out"]} levels to {len(lim.Q):,} quads in '
        f'{time.time() - t0:.1f}s')
    C.fit_report = rep
    return cage, sharp, lim, rep['res'], tgt, mir


# ============================================================================================ the cached cage and its field
def _file_sha(path):
    import hashlib
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def cage_key(spec):
    """every input of the cage: this module's tables and canid_nose's (W2l), the traced data it carries (canid_hull
    EYE_FISSURES, LIP_LINE, PROFILE, TOP, lm_w08.json / lm_w12.json, which traced_fissure and traced_canthi read), the
    skin's inputs (the reference), the skull's (the clearance) and the SPEC's eye and head"""
    from . import canid, canid_hull as CH, canid_nose as CN, canid_skull as SK
    from ..hullflow import cache_key
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'work', 'bestiary', 'research',
                        'wolf_work', 'data')
    return cache_key(dict(v=VERSION, rv=REF_VERSION, layout=LAYOUT, e=E_LINES, cap=CAP_ROWS, ref=REF,
                          rh=CN.RHINARIUM, border=CN.BORDER, nostril_l=CN.NOSTRIL_L,
                          leather=LEATHER, nostril=NOSTRIL, eye=EYE, lip=LIP, sharp=SHARP, levels=LEVELS, relax=RELAX,
                          fit=FIT, top=CH.TOP, fronts=CH.FRONTS['w12']['landmarks'],
                          spec_eye=spec['eye'], head_len=spec['head_len'], fis=CH.EYE_FISSURES, lip_line=CH.LIP_LINE,
                          profile=CH.PROFILE, lid=CH.STROKES_SKULL['eye'], skin=CH._skin_key(spec), skull=canid.SKULL,
                          skull_tables=SK.skull_key(spec), blend=CH.STROKES_SKULL['blend'],
                          lm=[_file_sha(os.path.join(data, f'lm_{p}.json')) for p in ('w08', 'w12')],
                          # W2q: the rest lids' inputs (the irises, the gaze model, the profiles' traced lids) and the rig
                          gaze=CH.GAZE, iris=CH.EYE_IRIS, rig=EYE_RIG, rig_slide=EYE_RIG_SLIDE,
                          lm_q=[_file_sha(os.path.join(data, f'lm_{p}.json'))
                                for p in CH.GAZE.get('profiles', ('w11', 'w01'))],
                          # W2n: the registration the canthi and the fissure are carried under (canid_hull.clay_points:
                          # the eye landmark's fixed point), so a change of it rebuilds the cage (W2o, the lead's call 4:
                          # read to 0.01 mm, as canid_hull.flow_key)
                          clay={k: np.round(np.asarray(v, float), 2).tolist() for k, v in CH.clay_points(spec).items()},
                          canthi=CH.CANTHI, canthus_depth=CH.CANTHUS_DEPTH,
                          # W2y: the ear's port reads the pinna's sheet (canid.ear_shell: HEAD ear, the SPEC's ear, the
                          # ear's frame and tip)
                          ear_port=EAR_PORT, ear=canid.HEAD['ear'], spec_ear=spec['ear'],
                          ear_frame=[np.round(np.asarray(v, float), 9).tolist() for v in canid.ear_face_frame(spec, 1)],
                          ear_tip=canid.EAR_TIP_R))


def cage_cached(spec, log=print):
    """THE CAGE (build_cage, limit_surface) cached by its inputs: the control cage, its creases, the targets, the limit mesh
    (vertices, triangles), the feature loops' positions, the nostrils' canals (pockets) and the fit's report"""
    from ..hullflow import cached
    from . import canid_hull as CH
    key = cage_key(spec)

    def build():
        ref = reference(spec, log)
        topo, C, ex = build_cage(spec, ref, log)
        cage, sharp, lim, res, tgt, mir = limit_surface(topo, C, log=log)
        V, F = lim.V, lim.tris()
        # outward: the winding number's sign needs it (the signed volume positive)
        vol = float(np.sum(np.einsum('ij,ij->i', V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])))) / 6.0
        if vol < 0:
            F = F[:, ::-1].copy()
        out = dict(V=V, F=F.astype(np.int32), cage_V=cage.V, cage_Q=cage.Q, tgt_V=tgt.V, fit_res=np.float64(res),
                   sharp_pairs=np.array(list(sharp.keys()), np.int64).reshape(-1, 2),
                   sharp_vals=np.array(list(sharp.values()), np.float64), mir=mir, n_half=np.int64(topo.n_half),
                   fixed=C.fixed.copy())
        for nm_, ids in topo.loops.items():
            out['loop_' + nm_.replace(' ', '_')] = tgt.V[np.asarray(ids, int)]
        # the nostril's canal (the opening's edge, the core, the vestibule, the canal; its end): rings and end, the left
        names = LAYOUT['tubes']['nostril']
        rings = [tgt.V[np.asarray(topo.tubes['nostril'][names.index(nm)], int)] for nm in ('edge', 'core', 'deep', 'canal')]
        out['nostril_rings'] = np.stack(rings)
        out['nostril_end'] = ex['nostril']['end']
        out['vol'] = np.float64(vol)
        # W2y: the ears' ports (the floors inside each root: the left's quads, then the right's; the low cuts them and the
        # ear's low joins the root) and the back cap's quads (the low's cut: the neck's seam), full-cage quad ids; the
        # sheet columns the root's outer face was taken at
        out['ear_inner_quads'] = np.concatenate([topo.ear_inner_quads, topo.ear_inner_quads + len(topo.Qh)])
        out['back_cap_quads'] = np.concatenate([topo.back_cap_q, topo.back_cap_q + len(topo.Qh)])
        out['ear_cols'] = np.asarray(ex['ear']['eb']['cols'], np.int64)
        if hasattr(topo, 'eye_rig'):
            # W2q: THE EYE RIG for pose_eye and the runtime (EYE_RIG; canid_hull's W2q note): the left eye's cage vertex ids
            # and their mirrors (the right eye), each one's lid-follow weight and upper-lid share; the canthus axis (the
            # globe's centre, the axis, n_o, n_v: palate mm, the left eye); the follow ratios (upper, lower), the rest
            # gaze's turn, the largest fitted gaze's, the taper (mm); the rest gaze (palate); the quads inside the margin
            # (the left eye's, then the right's)
            rig = topo.eye_rig
            fo = ex['eye']['chart']['follow']
            ax_ = fo['ax']
            out['eye_rig_ids'] = rig['ids']
            out['eye_rig_mir'] = mir[rig['ids']]
            out['eye_rig_w'] = rig['w']
            out['eye_rig_up'] = rig['up']
            out['eye_rig_axis'] = np.stack([ax_['c'], ax_['a'], ax_['no'], ax_['nv']])
            out['eye_rig_follow'] = np.array([fo['f_upper'], fo['f_lower'], fo['theta_rest'], fo['theta_max'],
                                              CH.GAZE['taper']])
            out['eye_rig_rest'] = np.asarray(CH.GAZE['rest'], np.float64)
            out['eye_inner_quads'] = np.concatenate([topo.eye_inner_quads, topo.eye_inner_quads + len(topo.Qh)])
            out['eye_margin_rig'] = topo.eye_margin_rig
            # W2r: THE HORIZONTAL FOLLOW's data (canid_hull GAZE slide): the slide ratios (upper, lower) and the rest lids'
            # phi along the canthus axis (s, upper, lower: mm, deg), which pose_cage slides
            out['eye_rig_slide'] = np.asarray(fo.get('slide', (0.0, 0.0)), np.float64)
            out['eye_rig_ws'] = rig['ws']
            out['eye_rig_rest_phi'] = np.stack([np.asarray(fo['s'], np.float64), np.asarray(fo['rest']['upper'][1]),
                                                np.asarray(fo['rest']['lower'][1])])
            if fo.get('slide_mode') == 'warp':
                # W2s: THE HORIZONTAL FOLLOW AS A WARP (canid_hull.gaze_warp): its anchor (s of the medial canthus, of the
                # rest cornea, of the lateral canthus, the margin; mm), which pose_cage's slide_points reads
                out['eye_rig_warp'] = np.asarray(fo['warp'], np.float64)
        for k_, v_ in C.fit_report.items():
            if isinstance(v_, dict):
                for kk, vv in v_.items():
                    out[f'fit_{k_}_{kk}'] = np.float64(vv)
        log(f'[cage] the limit mesh: {len(V):,} vertices, {len(F):,} triangles, volume {abs(vol) / 1000:.0f} cm3')
        return out
    return cached('canid_cage_mesh', key, build, log), key


def head_field(V, F, globes, pockets, G, log=print):
    """THE HEAD'S FIELD (HEAD_FIELD) on the grid G (palate mm): the exact signed distance to the limit mesh (V, F: outward,
    closed; the winding number's sign) unioned with the globes [(centre, R)], exact near the surface and eased into a
    blurred coarse pass beyond, the nostrils' canals capped (pockets: [(centreline (n, 3), radii (n,))]), clamped"""
    import warp as wp
    from scipy import ndimage as nd
    from .insect_cage import _kernels
    hf = HEAD_FIELD
    c = hf['coarse']
    kk = _kernels()
    dev = wp.get_preferred_device()
    t0 = time.time()
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev), support_winding_number=True)
    n = tuple(int(a) for a in G.n)
    nc = tuple((n[a] - 1) // c + 1 for a in range(3))
    assert all((nc[a] - 1) * c + 1 == n[a] for a in range(3)), (n, nc)
    o_ = wp.zeros(int(np.prod(nc)), dtype=wp.float32, device=dev)
    wp.launch(kk['sdf'], dim=int(np.prod(nc)), inputs=[m.id, wp.vec3(*np.asarray(G.lo, np.float32)), float(c * G.h),
                                                     int(nc[1]), int(nc[2]), 60.0, o_], device=dev)
    lo_c, hi_c = hf['clamp']
    dc = np.clip(o_.numpy().reshape(nc), lo_c - 4.0, hi_c + 4.0).astype(np.float32)
    d = nd.zoom(dc, [n[a] / nc[a] for a in range(3)], order=1, grid_mode=False, mode='nearest').astype(np.float32)
    del dc
    assert d.shape == n
    if hf['s_far'] > 0:
        d = nd.gaussian_filter(d, hf['s_far'] / G.h, mode='nearest')
    reach = hf['far'] + c * G.h * np.sqrt(3.0)
    near = np.abs(d) < reach
    idx = np.argwhere(near)
    P = (np.asarray(G.lo, np.float64)[None, :] + idx * G.h).astype(np.float32)
    del idx
    o2 = wp.zeros(len(P), dtype=wp.float32, device=dev)
    wp.launch(kk['sdf_pts'], dim=len(P), inputs=[m.id, wp.array(P, dtype=wp.vec3, device=dev), 60.0, o2], device=dev)
    dn = o2.numpy()
    w = smooth01((hf['far'] - np.abs(dn)) / (hf['far'] - hf['near'])).astype(np.float32)
    d[near] = w * dn + (1.0 - w) * d[near]
    nn = int(near.sum())
    del near, dn, w, o2
    # the globes (exact spheres; the analytic members put them back at any scale)
    D_, Q_, X_ = np.meshgrid(*[G.lo[a] + np.arange(n[a]) * G.h for a in range(3)], indexing='ij', sparse=True)
    gp = hf['globe_pad']
    for cg, rg in globes:
        sl = tuple(slice(max(0, int((cg[a] - rg - gp - G.lo[a]) / G.h)), min(n[a], int((cg[a] + rg + gp - G.lo[a]) / G.h) + 1))
                   for a in range(3))
        ds = np.sqrt((D_[sl[0]] - cg[0]) ** 2 + (Q_[:, sl[1]] - cg[1]) ** 2 + (X_[:, :, sl[2]] - cg[2]) ** 2) - rg
        d[sl] = np.minimum(d[sl], ds.astype(np.float32))
    # the nostrils' canals: the air within pocket r of the centreline capped (a lower bound of the distance stays one)
    pk = hf['pocket']
    ncap = 0
    for C_, R_ in pockets:
        lo_b = C_.min(0) - pk['r'] - 2.0
        hi_b = C_.max(0) + pk['r'] + 2.0
        sl = tuple(slice(max(0, int((lo_b[a] - G.lo[a]) / G.h)), min(n[a], int((hi_b[a] - G.lo[a]) / G.h) + 1))
                   for a in range(3))
        Pb = np.stack(np.meshgrid(*[G.lo[a] + np.arange(sl[a].start, sl[a].stop) * G.h for a in range(3)],
                                  indexing='ij'), -1).reshape(-1, 3)
        dist = np.full(len(Pb), np.inf)
        for a_, b_, ra, rb in zip(C_[:-1], C_[1:], R_[:-1], R_[1:]):
            ab = b_ - a_
            t_ = np.clip(((Pb - a_) @ ab) / max(float(ab @ ab), 1e-9), 0.0, 1.0)
            rr = ra + (rb - ra) * t_
            dist = np.minimum(dist, np.linalg.norm(Pb - (a_ + t_[:, None] * ab), axis=1) - rr)
        n_out = C_[0] - C_[1]
        n_out = n_out / max(np.linalg.norm(n_out), 1e-9)
        # (the cap also grows 1 mm per mm outside the capsule: continuous where the comma's air leaves the round capsule)
        cap_v = pk['cap'] + pk['grow'] * np.maximum((Pb - C_[0]) @ n_out, 0.0) + np.maximum(dist, 0.0)
        sub = d[sl].reshape(-1)
        cap = sub > cap_v
        ncap += int(cap.sum())
        sub[cap] = cap_v[cap]
        d[sl] = sub.reshape(d[sl].shape)
    d = np.clip(d, lo_c, hi_c).astype(np.float32)
    log(f'[cage] the head field on {n} ({int(np.prod(n)):,} points at {G.h} mm): exact at {nn:,} within {reach:.2f} mm of '
        f'the surface, the {nc} coarse pass blurred {hf["s_far"]} mm beyond, {len(globes)} globes, the canals\' air capped '
        f'at {ncap:,} points; on {dev} in {time.time() - t0:.0f}s')
    return d


def eye_curves(spec):
    """the eyes' frames as canid_hull's closed head carries them (curve_eye_<side>_centre, u, v, o, cornea, depth)"""
    from . import canid_hull as CH
    out = {}
    for side in ('L', 'R'):
        ef = CH.eye_frame(spec, side)
        out.update({f'curve_eye_{side}_centre': ef['centre'], f'curve_eye_{side}_u': ef['uu'],
                    f'curve_eye_{side}_v': ef['vv'], f'curve_eye_{side}_o': ef['oo'],
                    f'curve_eye_{side}_cornea': ef['centre'] + ef['r_globe'] * ef['oo'],
                    f'curve_eye_{side}_depth': np.array([EYE['lid']])})
    return out


def pockets_of(Z):
    """the nostrils' canals from the cached cage: per side the centreline (the rings' centres, the end) and radii (each
    ring's mean radius about its centre, the end 1 mm)"""
    rings = Z['nostril_rings']
    cen = rings.mean(axis=1)
    rad = np.array([np.linalg.norm(r_ - c_, axis=1).mean() for r_, c_ in zip(rings, cen)])
    C_ = np.vstack([cen, Z['nostril_end'][None]])
    R_ = np.concatenate([rad, [1.0]])
    out = []
    for sx in (1.0, -1.0):
        out.append((C_ * np.array([1.0, 1.0, sx]), R_))
    return out


def nares_members(Z):
    """the nostrils as canid_hull's measures read them: per side a 'psweep'-shaped record (its nodes the canal's
    centreline, its rim the cage's traced opening, its surface samples the opening and the vestibule's rings: psweep_np
    and nose_measures read only these)"""
    rings = Z['nostril_rings']
    out = []
    for sx in (1.0, -1.0):
        m = np.array([1.0, 1.0, sx])
        R3 = rings * m
        nodes = R3.mean(axis=1)
        out.append(('psweep', nodes, None, 0.0, np.zeros(len(nodes)), np.ones(len(nodes)), np.array([0.0, 0.0, 1.0]),
                    R3[0], R3.reshape(-1, 3)))
    return out


def head_volume(spec, jaw_deg=0.0, log=print):
    """THE HEAD GRID from the subdivision surface (canid_hull.head_volume's return: values mm on the fine grid, lo, h,
    divisor, closed (phi on the 1 mm lattice, the curves), grid), the bind's jaw opened by jaw_deg (canid_hull.open_jaw on
    the fine grid, redistanced, blurred HEAD_FIELD blur_open), every stage cached by its inputs"""
    from . import canid_hull as CH
    from ..hullflow import Grid, cache_key, cached, grid_bound, finish
    hf = HEAD_FIELD
    Z, key = cage_cached(spec, log)
    lo, hi = (np.asarray(b, np.float64) for b in hf['box'])
    G = Grid(lo, hi, hf['h'])
    G1 = Grid(lo, hi, 1.0)
    key_f = cache_key(dict(cage=key, field=hf))
    globes = [(CH.lid_frame(spec, s)['centre'], CH.lid_frame(spec, s)['R']) for s in ('L', 'R')]

    def build_field():
        phi = head_field(Z['V'], Z['F'], globes, pockets_of(Z), G, log)
        # finished like the opened jaw (redistanced, clamped, blurred): a raw distance's medial axes inside the clamp
        # bound the GRID's divisor at sqrt 3 (c8b's closed head 1.755: the head's field read at 0.57 in the review)
        phi = finish(phi, G, hf['clamp'], hf['blur_open'])
        return dict(values=phi, divisor=np.float64(max(1.0, grid_bound(phi, G.h))))

    def build_closed():
        Fd_ = cached('canid_cage_field', key_f, build_field, log)
        phi1 = np.ascontiguousarray(Fd_['values'][::2, ::2, ::2])
        assert phi1.shape == tuple(G1.n), (phi1.shape, G1.n)
        return dict(phi=phi1, divisor=Fd_['divisor'])
    Cd = cached('canid_cage_closed', key_f, build_closed, log)
    closed = dict(phi=Cd['phi'], lo=G1.lo, h=np.float64(1.0), **closed_curves(spec, Z), cage_key=np.array(key))
    Fd = cached('canid_cage_field', key_f, build_field, log)
    values, divisor = Fd['values'], float(Fd['divisor'])
    if abs(jaw_deg) > 1e-6:
        key_o = cache_key(dict(field=key_f, deg=jaw_deg, open_version=2, blur=hf['blur_open']))

        def build_open():
            ph = CH.open_jaw(values, G, spec, jaw_deg, log)
            fo = finish(ph, G, hf['clamp'], hf['blur_open'])
            return dict(values=fo, divisor=np.float64(max(1.0, grid_bound(fo, G.h))))
        Od = cached('canid_cage_open', key_o, build_open, log)
        values, divisor = Od['values'], float(Od['divisor'])
    return dict(values=values, lo=G.lo, h=G.h, divisor=divisor, closed=closed, grid=G, cage=Z, nares=nares_members(Z))


def closed_curves(spec, Z):
    """the closed head's curves as canid_hull's carries them: the mouth line across the face (both sides), the leather's
    outline seen along d, the eyes' frames, and every cage loop (curve_cage_*)"""
    curves = {}
    lm = Z['loop_lip_margin']
    curves['curve_mouth_line'] = np.vstack([(lm * [1.0, 1.0, -1.0])[::-1], lm[1:]])
    lb = Z['loop_leather_border']
    curves['curve_leather_outline'] = np.vstack([lb[:, [2, 1]], (lb[::-1] * [1.0, 1.0, -1.0])[1:-1][:, [2, 1]]])
    for k_ in list(Z.keys()):
        if k_.startswith('loop_'):
            curves['curve_cage_' + k_[5:]] = Z[k_]
    curves.update(eye_curves(spec))
    return curves


def closed_head(spec, log=print):
    """the closed head alone (the 1 mm lattice and the curves; the cached small file), for the ears' bases and the
    measures that read no fine field"""
    from ..hullflow import Grid, cache_key, cached
    hf = HEAD_FIELD
    Z, key = cage_cached(spec, log)
    lo, hi = (np.asarray(b, np.float64) for b in hf['box'])
    G1 = Grid(lo, hi, 1.0)
    key_f = cache_key(dict(cage=key, field=hf))
    Cd = cached('canid_cage_closed', key_f, lambda: head_volume(spec, 0.0, log)['closed'], log)
    return dict(closed=dict(phi=Cd['phi'], lo=G1.lo, h=np.float64(1.0), **closed_curves(spec, Z)))


_RASTER = []


def _raster():
    """W2q: an orthographic z-buffer over a pixel grid (numba), compiled once"""
    if not _RASTER:
        import numba as nb

        @nb.njit(cache=False)
        def raster(sx, sy, sz, Fs, W, H, zbuf, tid):
            for t in range(Fs.shape[0]):
                i0, i1, i2 = Fs[t, 0], Fs[t, 1], Fs[t, 2]
                x0, y0, z0 = sx[i0], sy[i0], sz[i0]
                x1, y1, z1 = sx[i1], sy[i1], sz[i1]
                x2, y2, z2 = sx[i2], sy[i2], sz[i2]
                area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
                if abs(area) < 1e-14:
                    continue
                minx = max(int(np.floor(min(x0, min(x1, x2)))), 0)
                maxx = min(int(np.ceil(max(x0, max(x1, x2)))), W - 1)
                miny = max(int(np.floor(min(y0, min(y1, y2)))), 0)
                maxy = min(int(np.ceil(max(y0, max(y1, y2)))), H - 1)
                for py in range(miny, maxy + 1):
                    cy = py + 0.5
                    for px in range(minx, maxx + 1):
                        cx = px + 0.5
                        w0 = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) / area
                        w1 = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) / area
                        w2 = 1.0 - w0 - w1
                        if w0 < -1e-7 or w1 < -1e-7 or w2 < -1e-7:
                            continue
                        zz = w0 * z0 + w1 * z1 + w2 * z2
                        if zz > zbuf[py, px]:
                            zbuf[py, px] = zz
                            tid[py, px] = t
        _RASTER.append(raster)
    return _RASTER[0]


def opening_view(V, F, inner_tri, cam, npd, cg, R, half=22.0, res=0.04):
    """W2q: ONE EYE'S OPENING in an orthographic camera (cam = (c toward it, r image right, u up) in canid_hull's
    (x, q, p) frame; npd the nose tip's p): the limit mesh V, F (palate mm) z-buffered, the globe (centre cg, radius R)
    analytic, on a (2 half / res)^2 grid centred on the globe's image; the OPENING every pixel whose first surface is
    the globe or a triangle inside the lid margin (inner_tri: per triangle, the cage quads from the margin inward), as
    the W2o fresh eyes' opening.py reads it. Returns dict(GX, GY (image mm), opening, ball, n, cg (image), half, res)"""
    c, r, u = (np.asarray(a, np.float64) for a in cam)

    def to_cam(P):
        P = np.atleast_2d(P)
        X = np.column_stack([P[:, 2], P[:, 1], npd - P[:, 0]])
        return X @ r, X @ u, X @ c
    Ucg, Vcg, Zcg = (float(a[0]) for a in to_cam(np.asarray(cg, np.float64)))
    n = int(round(2 * half / res))
    U, Vv, Zz = to_cam(np.asarray(V, np.float64))
    sx = (U - (Ucg - half)) / res
    sy = ((Vcg + half) - Vv) / res
    F = np.asarray(F, np.int64)
    keep = ((sx[F] > -2).any(1) & (sx[F] < n + 2).any(1) & (sy[F] > -2).any(1) & (sy[F] < n + 2).any(1))
    ids = np.nonzero(keep)[0]
    zbuf = np.full((n, n), -1e9)
    tid = np.full((n, n), -1, np.int64)
    _raster()(sx, sy, Zz, np.ascontiguousarray(F[keep]), n, n, zbuf, tid)
    gx = (Ucg - half) + (np.arange(n) + 0.5) * res
    gy = (Vcg + half) - (np.arange(n) + 0.5) * res
    GX, GY = np.meshgrid(gx, gy)
    rho2 = (GX - Ucg) ** 2 + (GY - Vcg) ** 2
    zs = np.where(rho2 < R * R, Zcg + np.sqrt(np.maximum(R * R - rho2, 0.0)), -1e9)
    ball = (rho2 < R * R) & (zs > zbuf + 0.02)
    hit = tid >= 0
    tri = np.full((n, n), -1, np.int64)
    tri[hit] = ids[tid[hit]]
    pocket = hit & ~ball & np.asarray(inner_tri, bool)[np.maximum(tri, 0)]
    return dict(GX=GX, GY=GY, opening=ball | pocket, ball=ball, n=n, cg=(Ucg, Vcg), half=half, res=res,
                to_cam=to_cam)


def seen_backfaces(V, F, cam, npd, cg, R, half=24.0, res=0.04, rho_max=2.4, cos_tol=0.05):
    """W2s (the lead's call 4, "the medial crease gone, gated by a seen-back-face count"; the W2r fresh eyes' test,
    check_w2r_fresh/foldvis.py): on a closed, consistently oriented surface that does not pass through itself every
    triangle a camera SEES faces it (save grazing ones at a silhouette); a seen triangle whose outward normal points
    away from the camera (normal . toward-camera < -cos_tol) is skin seen from inside: a fold. The limit mesh V, F
    (palate mm, outward triangles) z-buffered orthographically round one globe (cg, R: analytic, in the depth test too)
    in cam = (c toward it, r, u) in canid_hull's (x, q, p) frame. Returns dict(area (mm2 within rho_max R of the globe's
    centre in the image), back (the mask), reach, GX, GY, cg (image), where (palate (d, q, x) mm of the seen
    back-faces in reach, (k, 3)))"""
    c, r, u = (np.asarray(a, np.float64) for a in cam)

    def to_cam(P):
        P = np.atleast_2d(P)
        X = np.column_stack([P[:, 2], P[:, 1], npd - P[:, 0]])
        return X @ r, X @ u, X @ c
    V = np.asarray(V, np.float64)
    F = np.asarray(F, np.int64)
    Ucg, Vcg, Zcg = (float(a[0]) for a in to_cam(np.asarray(cg, np.float64)))
    n = int(round(2 * half / res))
    U, Vv, Zz = to_cam(V)
    sx = (U - (Ucg - half)) / res
    sy = ((Vcg + half) - Vv) / res
    keep = ((sx[F] > -2).any(1) & (sx[F] < n + 2).any(1) & (sy[F] > -2).any(1) & (sy[F] < n + 2).any(1))
    ids = np.nonzero(keep)[0]
    zbuf = np.full((n, n), -1e9)
    tid = np.full((n, n), -1, np.int64)
    _raster()(sx, sy, Zz, np.ascontiguousarray(F[keep]), n, n, zbuf, tid)
    g = (np.arange(n) + 0.5) * res
    GX, GY = np.meshgrid((Ucg - half) + g, (Vcg + half) - g)
    rho2 = (GX - Ucg) ** 2 + (GY - Vcg) ** 2
    zs = np.where(rho2 < R * R, Zcg + np.sqrt(np.maximum(R * R - rho2, 0.0)), -1e9)
    ball = (rho2 < R * R) & (zs > zbuf + 0.02)
    hit = (tid >= 0) & ~ball
    tri = np.full((n, n), -1, np.int64)
    tri[tid >= 0] = ids[tid[tid >= 0]]
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    fnX = np.column_stack([fn[:, 2], fn[:, 1], -fn[:, 0]])          # (d, q, x) -> (x, q, p)
    facing = np.zeros((n, n))
    facing[hit] = fnX[tri[hit]] @ c
    back = hit & (facing < -cos_tol)
    reach = rho2 <= (rho_max * R) ** 2
    b_ = back & reach
    X_ = GX[b_][:, None] * r[None] + GY[b_][:, None] * u[None] + zbuf[b_][:, None] * c[None]
    where = np.column_stack([npd - X_[:, 2], X_[:, 1], X_[:, 0]]) if b_.any() else np.zeros((0, 3))
    return dict(area=float(b_.sum()) * res * res, back=back, reach=reach, GX=GX, GY=GY, cg=(Ucg, Vcg), where=where)


def above_share(P, p0, p1):
    """W2q: the share of a point set's height across the line p0 -> p1 (up +) that lies above the line"""
    a = (p1 - p0) / np.linalg.norm(p1 - p0)
    b = np.array([-a[1], a[0]])
    b = b if b[1] >= 0 else -b
    h = (np.asarray(P, np.float64) - p0) @ b
    return float(h.max() / max(float(np.ptp(h)), 1e-6))


def inner_triangles(Z, F):
    """W2q: per triangle of a three-level limit mesh of the cache's cage (the level-3 quads' first triangles, then their
    second; 64 per cage quad), whether its cage quad lies inside the lid margin (Z eye_inner_quads)"""
    nl = len(F) // 2
    assert len(F) == 2 * 64 * len(Z['cage_Q']), 'the limit mesh is not three levels of the cage'
    return np.isin((np.arange(len(F)) % nl) // 64, np.asarray(Z['eye_inner_quads']))


def rig_axis(Z):
    """W2q: the cached cage's canthus axis (the left eye) as canid_hull's ax dict"""
    A_ = np.asarray(Z['eye_rig_axis'], np.float64)
    return dict(c=A_[0], a=A_[1], no=A_[2], nv=A_[3])


def pose_cage(Z, theta):
    """W2q: THE CAGE POSED AT A GAZE (the runtime's lid-follow, EYE_RIG): theta {'L': ..., 'R': ...}, each eye's gaze turn
    about its canthus axis (canid_hull.gaze_turn of its gaze; the right eye's on its mirrored axis) in deg, or (W2r) a
    dict with it as 'theta' and the cornea's move along the axis as 'delta' (mm, canid_hull.gaze_slide; canid_hull
    .photo_gaze's result is one), None for the rest; each eye vertex turned about the axis by w (f_upper u + f_lower
    (1 - u)) (theta - theta_rest) (canid_hull.pose_points), then (W2r, THE HORIZONTAL FOLLOW, the cache's eye_rig_slide)
    by its lids' rest phi read k_lid delta mm back along the axis less their own at its s, x w (u for the upper lid,
    1 - u for the lower): each lid's shape slides along the fissure with the cornea, the canthi held by the taper.
    Returns the posed control points (n, 3)"""
    from . import canid_hull as CH
    V = np.array(Z['cage_V'], np.float64, copy=True)
    if theta is None:
        return V
    ax = rig_axis(Z)
    fu, fl, th0 = (float(x) for x in np.asarray(Z['eye_rig_follow'])[:3])
    ks = np.asarray(Z['eye_rig_slide'], np.float64) if 'eye_rig_slide' in Z else np.zeros(2)
    for side, ids, sx in (('L', Z['eye_rig_ids'], 1.0), ('R', Z['eye_rig_mir'], -1.0)):
        th = theta.get(side) if isinstance(theta, dict) else theta
        if th is None:
            continue
        dl = float(th.get('delta', 0.0)) if isinstance(th, dict) else 0.0
        th = float(th['theta']) if isinstance(th, dict) else float(th)
        m = np.array([1.0, 1.0, sx])
        dth = th - th0
        P = CH.pose_points(ax, V[ids] * m, fu * dth, fl * dth, Z['eye_rig_up'], Z['eye_rig_w'])
        if dl != 0.0 and np.any(ks != 0.0) and 'eye_rig_rest_phi' in Z:
            P = slide_points(Z, P, V[ids] * m, dl, Z['eye_rig_ws'] if 'eye_rig_ws' in Z else Z['eye_rig_w'],
                             Z['eye_rig_up'])
        V[ids] = P * m
    return V


def slide_points(Z, P, P_rest, delta, w, u):
    """W2r: THE HORIZONTAL FOLLOW's turn of points P (the left eye's, already turned by the vertical follow) whose rest
    positions are P_rest: each turned about the canthus axis by w (u (phi_u(s - k_u delta) - phi_u(s)) + (1 - u)
    (phi_l(s - k_l delta) - phi_l(s))) deg, phi_u / phi_l the rest lids' phi along the axis (the cache's eye_rig_rest_phi),
    k the slide ratios (eye_rig_slide), s each rest point's place along the axis, w its rig weight, u its upper-lid share"""
    from . import canid_hull as CH
    ax = rig_axis(Z)
    ks = np.asarray(Z['eye_rig_slide'], np.float64)
    s_r, ph_u, ph_l = (np.asarray(a_, np.float64) for a_ in Z['eye_rig_rest_phi'])
    s_v, _, _ = CH.cyl(ax, np.asarray(P_rest, np.float64))
    u_ = np.asarray(u, np.float64)
    if 'eye_rig_warp' in Z:
        # W2s (canid_hull.gaze_warp): the point at s takes its lid's rest phi from where the warp sends to s (the warp
        # inverted on a dense grid: it is monotone), the canthi held by the warp itself
        anc = np.asarray(Z['eye_rig_warp'], np.float64)
        g_ = np.linspace(float(anc[0]) - 1.0, float(anc[2]) + 1.0, 801)
        src = [np.interp(s_v, CH.warp_s(g_, delta, float(k_), anc), g_) for k_ in ks]
    else:
        src = [s_v - ks[0] * delta, s_v - ks[1] * delta]
    al = np.asarray(w, np.float64) * (u_ * (np.interp(src[0], s_r, ph_u) - np.interp(s_v, s_r, ph_u))
                                      + (1.0 - u_) * (np.interp(src[1], s_r, ph_l) - np.interp(s_v, s_r, ph_l)))
    return CH.pose_points(ax, P, 1.0, 1.0, np.ones(len(P)), al)


def pose_eye(Z, theta, levels=None):
    """W2q: THE LIMIT MESH POSED AT A GAZE: pose_cage's control points subdivided as the cache's limit (LEVELS out, the
    cage's creases), the triangles oriented as the cache's. Returns (V (n, 3), F (m, 3)) palate mm"""
    V = pose_cage(Z, theta)
    sharp = {(int(a), int(b)): float(s) for (a, b), s in zip(np.asarray(Z['sharp_pairs']), np.asarray(Z['sharp_vals']))}
    lim, _, _, _ = SS.subdivide(QuadMesh(V, np.asarray(Z['cage_Q'])), sharp, LEVELS['out'] if levels is None else levels)
    Vl, Fl = lim.V, lim.tris()
    vol = float(np.sum(np.einsum('ij,ij->i', Vl[Fl[:, 0]], np.cross(Vl[Fl[:, 1]], Vl[Fl[:, 2]])))) / 6.0
    if vol < 0:
        Fl = Fl[:, ::-1].copy()
    return Vl, Fl.astype(np.int32)
