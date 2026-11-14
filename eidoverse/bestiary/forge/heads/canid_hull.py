"""W2c: the canid head VOLUME from the photographs (the lead's W2b review: "primitives read as primitives"; two rounds of
parametric heads read as a pig-dog and a faceted plank). The head is not built from primitives: it is the VISUAL HULL of
its traced skin silhouettes, rounded by a constrained CURVATURE FLOW on its level set, then sculpted, and it enters the
creature's program as one sampled signed-distance GRID (sdf.Program.grid, the staged patch work/bestiary/patches/
sdf_grid.md: a dedicated grid member on the OFFSET's grid machinery, coat_depth()'s trilinear sampler and the values
riding on the thickness array).

THE FRAME: canid's palate frame in millimetres, d back from the nose tip along p, q dorsal from the AO joint, x lateral
(+ the creature's left). The grid's axes are (-p, q, X), its index i along d.

1. THE HULL. Each view's skin silhouette is a closed polygon in its own image plane; a voxel survives if its projection
   falls inside every one. The views:
     PROFILE  (d, q), projection along x: the photos' consensus where the coat is thin (the nose leather, the nasal
              dorsum to the stop, the chin, the jaw's underside: w01 summer, w03 winter, w10 summer, each fur line less
              its region's coat depth) and the measured skull plus its skin depths where the coat is thick (the forehead,
              the crown, the poll: the photos' lines there ride 10-40 mm over the bone on the forehead and crown fur and
              the ear bases), the two meeting in one bend at the photos' stop (their landmarks, d 99): canid_hull.PROFILE
     TOP      (d, |x|), projection along q: the skull's dorsal outline at the SPEC scale (specimen 12092001's shape at the
              Latvian breadths) plus the lateral skin, the lips and the muscles: canid_hull.TOP
     FRONT    the head-front photos r03 (wet), r07 (a thin-coated coyote, its eyes and nose as the W2b checker corrected
              them) and w12 (winter), each in its own camera (the pitch and yaw that put the clay's planum where the
              photo's sits once its eye centres sit on the clay's visible eyes): the traced outline less its coat plus
              its tolerance is an OUTER limit (the coat there is an estimate of 2-30 mm): canid_hull.FRONTS
     SECTIONS the skull's own cross-sections (canid.HEAD's face and jaw stations, each scaled to the top view's width,
              face and jaw bridged), + 3 mm: an outer limit that rounds the hull's box corners
2. THE FLOW. phi_t = (kappa - F) |grad phi| on the hull's level set (kappa the mean curvature, the sum of the principal
   curvatures; F an inflation pressure 1 / (c r), r the hull's local thickness (minus its 16 mm min-filtered field): free
   surface relaxes toward constant mean curvature, round sections the size of the head there, instead of shrinking as
   pure mean-curvature flow does), each step CLAMPED between the constraints (the inner wins a clash): inside the outer
   bound (the views' silhouettes dilated by their outer tolerance, 2 mm in profile but 0.5 over the nasal dorsum and
   the stop, BUILD tol profile_stop; the sections), containing a ball of the minimum skin depth (+ 0.5 mm) round every
   skull landmark and excluding a ball beyond its maximum depth (- 0.5) along its measured direction, the skull's dorsal
   and ventral outlines, and pinned to the profile's outline on the midline and to the top view's outline at its rim
   height (the eroded views as an inner bound are off: box corners against the sections). Stage A at 2 mm, stage B at
   1 mm, a pure-curvature relax; redistanced every few steps (closest points through the nearest interface voxel's
   foot point).
3. THE SCULPT (canid_hull.STROKES): the domed nose leather with its median groove, the upper lip's margin and the mouth
   line, the brows, the orbits and the eye openings at the photos' lid cant, as displacements of the level set, then an
   exact redistance on the triangulated zero set (Warp's BVH), the far field clamped at +-34 mm and a 0.7 mm blur (the
   GRID member's proved divisor 1.16). The bind's jaw: the lower part cut at the occlusal plane and the lip line and
   turned rigidly about the jaw joint.

Everything is deterministic from this module's tables, canid.SKULL and the SPEC, and cached on disk by its inputs' hash
(BESTIARY_CACHE, default <repo>/work/bestiary/cache).

W2d: the generic machinery (the 2D silhouette rasters, Grid, the balls, the redistances, the flow, the samplers, the
exact distance, the divisor, the cache) moved unchanged to forge/hullflow.py, shared with the wolf's body volume
(species/wolf_body.py); its names are imported here, so canid.py and the scripts keep reading them from this module.
The head volume is bit-identical after the move (work/bestiary/wolf/scratch_w2d/head_bitcheck.py).

W2d head (the lead's call 7): the flow stage has its own cache (head_volume; the closed head bit-identical for the
same strokes, work/bestiary/wolf/scratch_w2dh/split_check.py: 40 of 40 arrays); the leather's pad a round cap (no
rim), the alae, the eye's almond a lens along the front views' canthi; the NARES left the grid: they are analytic
members subtracted over it (nares_members, canid.HEAD nares, canid.build_head), smooth at any scale.
"""
import time

import numpy as np

from ..hullflow import (CACHE, Grid, ball_bounds, cache_key, cached, curvature_term, curve_dist,  # noqa: F401
                        ellipsoid_sd, exact_distance, flow, grid_bound, inward_normals_closed, offset_polyline,
                        poly_sdf_image, redistance, resample_closed, sample2, sample3, surface_along, surface_x)
from .. import hullflow as HF

VERSION = 'w2h-h10'               # w2h-h* (W2h, the lead's calls 1-3): canid.HEAD method 'skull': the skin over the skull
                                 # (canid_skin), the traced rhinarium, the mouth line, the lid fissures (sculpt_skull);
                                 # w2g-h1 (W2g, the lead's calls 2-4): the lips, whisker pads and chin as MASSES
                                 # (face_masses, STROKES masses), the leather 1.05 x wide, the nose's fine forms analytic
                                 # (nose_members: alar folds, comma openings down-back canals, the philtrum groove), the
                                 # alar_lobes stroke and the philtrum displacement off, the eye's prism through the ball's
                                 # centre cut to the globe (STROKES eye floor 'sphere'), the brow and the lids lower;
                                 # w2f-h1 (W2f, the lead's calls 2-3): the dome curved everywhere and the top rolling onto
                                 # the bridge (leather_pad 'curved', prof_inset), the alar lobes traced on w12
                                 # (alar_lobes), the brow over the supraorbital margin; w2c-7 (the W2c check): the nares stroke (STROKES nares); w2d-h1 (W2d head): the
                                 # round leather cap, the alae, the lens eye along the measured canthi, the nares moved
                                 # to analytic members (canid HEAD nares); w2d-h2: the chin's knob softened (STROKES chin);
                                 # w2e-h1 (W2e head, the lead's call 2): the leather a broad-topped trapezoid at w08's
                                 # width with its lower front kept forward (pad_outline, pad_dome_bot), the alae and the
                                 # philtrum under the raised nares, the chin ring gone, the eye's almond 24 mm canted
FLOW_VERSION = 'w2f-flow-2'      # W2d head: the flow stage's own cache (head_volume): the hull, limits and flow, which
                                 # no stroke changes (unchanged since W2c r5); W2f (the lead's call 1): the wet r03's
                                 # re-traced stretch (an outer limit; front_pins ready for a two-sided segment), the
                                 # muzzle's taper (TOP)

# ============================================================================================ the frozen data (mm)
# Computed by work/bestiary/research/wolf_work/scripts/head_silhouettes.py --tables from the tracings (data/lm_w01,
# lm_w03, lm_w10, lm_w11; data/res_skull_s12092001.json; canid.SKULL / HEAD), the method in its docstring.
# THE PROFILE (closed, counter-clockwise from the leather's top over the nose tip): the hairless leather (the mean of
# w01, w03, w10, w11's outlines); the upper lip's front; the jaw's underside (the photos' consensus, coat removed:
# lips 1-3 mm, the intermandibular hair 3-5 winter, summer x 0.45); rising under the mandible's angle; the BACK
# boundary (indices PROFILE_BACK, buried in the neck sweep, not pinned); the occiput, the crown and the forehead on the
# skull plus its skin (crest 6, frontal 5 mm); THE STOP at the photos' (their landmarks' mean, d 99: chord 0.76 NE),
# one bend where the photos' nasal dorsum (floored at the bone + 2.5 mm, raised along a ramp from d 54 by the 3.1 mm
# that puts it 3.5 mm over the bone there) meets the forehead (the skull plus 3.5 -> 5.5 mm of skin)
PROFILE = (
    (8.9, 23.1), (6.3, 22.8), (3.8, 22.0), (1.8, 20.4), (0.2, 18.4), (-1.2, 16.3), (-2.1, 13.9), (-2.5, 11.1),
    (-2.2, 8.2), (-1.5, 5.0), (-0.7, 2.6), (0.5, 0.0), (2.4, -2.4), (5.0, -4.2), (8.0, -5.4), (9.0, -13.8),
    (12.0, -22.1), (14.0, -24.2), (16.0, -26.8), (18.0, -29.6), (20.0, -32.3), (22.0, -34.7), (24.0, -36.9),
    (26.0, -38.8), (28.0, -40.5), (30.0, -42.0), (33.0, -44.0), (36.0, -45.7), (39.0, -47.3), (42.0, -48.8),
    (45.0, -50.3), (48.0, -51.5), (51.0, -52.5), (54.0, -53.4), (57.0, -54.5), (60.0, -55.6), (63.0, -56.6),
    (66.0, -57.6), (69.0, -58.4), (72.0, -59.1), (75.0, -59.7), (78.0, -60.5), (81.0, -61.3), (84.0, -62.2),
    (87.0, -63.1), (90.0, -64.0), (93.0, -64.7), (96.0, -65.5), (99.0, -66.2), (102.0, -67.0), (105.0, -67.8),
    (108.0, -68.6), (130.0, -70.5), (150.0, -66.5), (170.0, -62.0), (190.0, -55.0), (208.0, -47.0), (226.0, -36.0),
    (243.0, -22.0), (258.0, -6.0), (268.0, 12.0), (271.0, 30.0), (268.0, 46.0), (262.0, 58.0), (256.0, 66.1),
    (253.0, 66.6), (250.0, 67.9), (247.0, 69.5), (244.0, 71.0), (241.0, 72.0), (238.0, 72.7), (235.0, 73.1),
    (232.0, 73.4), (229.0, 73.5), (226.0, 73.4), (223.0, 73.1), (220.0, 72.7), (217.0, 72.1), (214.0, 71.7),
    (211.0, 71.5), (208.0, 71.5), (205.0, 71.5), (202.0, 71.5), (199.0, 71.5), (196.0, 71.5), (193.0, 71.5),
    (190.0, 71.5), (187.0, 71.5), (184.0, 71.4), (181.0, 71.3), (178.0, 71.2), (175.0, 71.0), (172.0, 70.9),
    (169.0, 70.7), (166.0, 70.5), (163.0, 70.3), (160.0, 70.0), (157.0, 69.6), (154.0, 69.1), (151.0, 68.5),
    (148.0, 67.8), (145.0, 67.1), (142.0, 66.2), (139.0, 65.1), (136.0, 63.9), (133.0, 62.5), (130.0, 60.9),
    (127.0, 59.1), (124.0, 57.2), (121.0, 55.1), (118.0, 52.9), (115.0, 50.7), (112.0, 48.6), (109.0, 46.5),
    (106.0, 44.5), (103.0, 42.7), (100.0, 41.1), (97.0, 39.7), (94.0, 38.5), (91.0, 37.5), (88.0, 36.4),
    (85.0, 35.5), (82.0, 34.6), (79.0, 33.7), (76.0, 32.9), (73.0, 32.1), (70.0, 31.3), (67.0, 30.5), (64.0, 29.9),
    (61.0, 29.2), (58.0, 28.5), (55.0, 27.9), (52.0, 27.3), (49.0, 26.9), (46.0, 26.4), (43.0, 26.0), (40.0, 25.4),
    (37.0, 24.8), (34.0, 24.2), (31.0, 23.7), (28.0, 23.3), (25.0, 23.0), (22.0, 22.7), (19.0, 22.2), (16.0, 21.7),
    (13.0, 21.3), (12.0, 21.2))
PROFILE_BACK = (56, 63)          # the buried back boundary's indices (inclusive)
# THE TOP half outline (d, |x|): the leather's rounded front (22 mm half at d 9: w12 46, r03 48, w07 45, w08 41 mm
# wide), the lips over the canines (+6), straight to the carnassials at the skin (the maxilla's waist is bone), the
# skull's outer outline at the SPEC scale (specimen 12092001's shape x 1.0574 to ZyB 143) plus the skin (5-6 mm), the
# arches' 154.6 mm at d 171-174 (gate 149-163), smoothed 9 mm from the face back; behind the arch's root the skull's
# sections' breadth (cheek, jaw angle, ear canal), the neck at the plan's C1 112 mm
# W2f (the lead's call 1, "a round tube where the wet r03 shows a long converging wedge"): the muzzle TAPERS from the
# leather to the face instead of running parallel at 29.4 from d 39 to 72 and flaring after (W2c's "straight to the
# carnassials at the skin": the maxilla's waist filled as a tube). In r03's solved camera the far flank widens steadily
# from the leather back to the ruff (work/bestiary/wolf/scratch_w2f/r03_trace.py); the taper is held inside the muzzle
# gate's bands (the width at d 40 <= 65, at d 80 <= 76: the clay stands 4-6 mm wider than twice this outline there, its
# lips flaring under the rim height) and the canine's skin depth (<= 9 at d 30): d 15-45 +0.7-1.4 mm, d 50-75 +2-4.5
# (the waist over the premolars filled), d 80-105 as before. [E] guided by r03; W2c's values in the W2e tables
TOP = (
    (0, 0.0), (3, 16.4), (6, 20.7), (9, 22.0), (12, 22.6), (15, 23.2), (18, 23.8), (21, 24.5), (24, 25.2), (27, 26.0),
    (30, 26.9), (33, 27.7), (36, 28.5), (39, 29.3), (42, 30.0), (45, 30.6), (48, 31.2), (51, 31.6), (54, 32.0),
    (57, 32.4), (60, 32.8), (63, 33.2), (66, 33.5), (69, 33.8), (72, 34.1), (75, 34.4), (78, 34.7), (81, 35.4),
    (84, 36.9), (87, 39.0), (90, 40.8), (93, 42.0), (96, 42.7), (99, 43.6), (102, 44.5), (105, 45.0), (108, 45.7),
    (111, 46.9), (114, 48.6), (117, 50.6), (120, 52.5), (123, 54.4), (126, 56.2), (129, 58.0), (132, 59.8),
    (135, 61.6), (138, 63.3), (141, 64.9), (144, 66.5), (147, 68.1), (150, 69.5), (153, 70.9), (156, 72.1),
    (159, 73.2), (162, 74.2), (165, 74.9), (168, 75.4), (171, 75.6), (174, 75.6), (177, 75.3), (180, 74.7),
    (183, 73.9), (186, 73.0), (189, 71.9), (192, 70.8), (195, 69.7), (198, 68.7), (201, 67.5), (204, 66.3),
    (207, 65.1), (210, 63.7), (213, 62.3), (216, 60.8), (219, 59.3), (222, 57.9), (225, 56.4), (228, 55.1),
    (231, 53.7), (234, 52.5), (237, 51.3), (240, 50.2), (243, 49.2), (246, 48.2), (249, 47.4), (252, 46.7),
    (255, 46.3), (258, 46.1), (261, 46.2), (264, 46.6), (267, 47.3), (270, 48.1), (273, 49.1), (276, 50.2),
    (279, 51.3), (282, 52.3), (285, 53.3), (288, 54.1), (290, 54.5))
# the top view's rim height (q at d): the upper lip over the canine and the premolars, the zygomatic arch
Q_RIM = ((0, 12.0), (12, 4.0), (30, -14.0), (60, -18.0), (95, -20.0), (120, 0.0), (150, 15.0), (195, 15.0),
         (215, 5.0), (240, 0.0), (290, -10.0))
# THE FRONT photos (research/wolf_work/data/src/front_*.json, W2c): the image-right outline in photo px, its coat and
# tolerance per stretch (an OUTER limit: outline - coat + tol), the landmarks the camera is solved from
# W2f (the lead's call 1, "make the wet r03's front silhouette TWO-SIDED for the muzzle and face (the clay's front outline
# ON r03's skin line within 2 mm, inside and outside)"): r03's wet stretch RE-TRACED on gridded crops at 3.6-5x (10 px
# grid; work/bestiary/wolf/scratch_w2f/r03_trace.py, out/r03_edge_a.png x 2390-2520 y 1460-1620 at 5x, out/r03_edge_b.png
# x 2240-2470 y 1600-1770 at 3.6x): the visible edge of the flat wet hair against the water, from where it leaves the
# cheek ruff's lower edge round the whisker pad beside the leather and the chin to where the wet beard hides it (W2c's
# trace, read at 0.6 view px per image px, ran 15-25 px = 3-5 mm inside that edge from y 1500 to 1680); 'two_sided':
# an inner limit too (front_pins: balls touching the skin line from inside on the flowed clay's rim), the outer at 1.5.
# NOT set: in r03's solved camera the W2e clay stood 5.5-10 mm INSIDE this line all round (the flank, the whisker pad
# beside the leather, the chin), so holding it two-sided pushed the muzzle to 79 mm at d 40 and the canine's skin to
# 10.4 mm (the gates' 53-65 and 3-9) and, against the top view's and the sections' limits, printed the pins as a row of
# beads (scratch_w2f/out/head_view_pins1.png); the stretch is an outer limit 1.5 mm outside the line, the taper (TOP)
# brings the flank toward it within the gates, and w02 prints the errors (the lead's call: a decision for the lead)
front_wet_r03 = ((2497, 1488), (2493, 1500), (2490, 1510), (2488, 1520), (2484, 1530), (2477, 1540), (2474, 1550),
                 (2471, 1560), (2467, 1570), (2465, 1580), (2462, 1590), (2458, 1600), (2455, 1610), (2451, 1620),
                 (2450, 1630), (2447, 1640), (2443, 1650), (2439, 1660), (2432, 1670), (2421, 1680), (2404, 1690),
                 (2390, 1695), (2371, 1700), (2364, 1710), (2350, 1720), (2332, 1730), (2304, 1740), (2287, 1744),
                 (2268, 1742), (2261, 1739))
FRONTS = dict(
    r03=dict(landmarks=dict(eye_R=(2080, 1085), eye_L=(2450, 1080), nose_R=(2210, 1560), nose_L=(2430, 1560)),
             outline=(dict(coat_mm=23.0, tol_mm=15.0, points=((2655, 730), (2690, 780), (2705, 850), (2715, 950),
                                                                  (2725, 1050), (2730, 1110), (2718, 1180),
                                                                  (2705, 1250), (2690, 1310), (2660, 1370))),
                      dict(coat_mm=23.0, tol_mm=15.0, points=((2610, 1410), (2560, 1430))),
                      dict(coat_mm=2.0, tol_mm=1.5, points=front_wet_r03))),
    r07=dict(landmarks=dict(eye_R=(2037, 640), eye_L=(2180, 635), nose=(2140, 795)),
             outline=(dict(coat_mm=4.0, tol_mm=8.0, points=((2248, 560), (2240, 600), (2234, 650), (2228, 690),
                                                                (2218, 720))),
                      dict(coat_mm=3.0, tol_mm=6.0, points=((2208, 745), (2200, 770), (2196, 795), (2185, 820),
                                                                (2165, 840), (2140, 858))))),
    w12=dict(landmarks=dict(eye_R=(2158, 1151), eye_L=(2602, 1127), nose_R=(2282, 1725), nose_L=(2538, 1725)),
             outline=(dict(coat_mm=12.0, tol_mm=15.0, points=((2905, 600), (2930, 700), (2950, 750), (2985, 800),
                                                                  (3000, 850))),
                      dict(coat_mm=30.0, tol_mm=15.0, points=((3010, 900), (3050, 950), (3080, 1000), (3110, 1050),
                                                                  (3140, 1100), (3150, 1150), (3165, 1200),
                                                                  (3175, 1250), (3180, 1300), (3175, 1350),
                                                                  (3160, 1400), (3140, 1450), (3125, 1500),
                                                                  (3110, 1550), (3100, 1600))))))
# W2g (the lead's call 2: "the clay's front outline on r03 (and w12, w07, w08 less their coat) within 2 mm, inside and
# outside, through the solved cameras"): the MUZZLE'S image-right outline beside and under the leather on the three
# winter fronts, traced on gridded crops (work/bestiary/wolf/scratch_w2g/crop.py; out/w08_muzR.png at 5x, w12_muzR.png at
# 1.8x, w07_muzR.png at 2.4x). None of them shows the muzzle against the background (it stands against the cheek), so the
# lines are the pale whisker pad's lateral FUR edge against the darker cheek (w08: the white pad's edge from beside the
# leather's top down to the lip's corner, its bottom over the dark lip; w12: the tan streak along the pad's lateral margin,
# where the whiskers' rows end, then the pale lip round to the lip margin; w07, soft: the pad's edge past the dark whisker
# spot), each less its pad coat (w08 4 mm, w07 6, w12 8: the winter pad hair beyond the vibrissae rows) with that coat's
# uncertainty as tol; the landmarks (eyes, leather edges) from lm_<pid>.json. r03's wet stretch (FRONTS r03, 2 mm) stays
# the one SKIN silhouette; these are fur estimates
FRONT_MUZZLE = dict(
    w08=dict(outline=(dict(coat_mm=4.0, tol_mm=3.0, points=((688, 535), (683, 550), (678, 563), (673, 576), (668, 589),
                                                             (664, 600), (660, 611), (655, 621), (648, 628),
                                                             (638, 633))),)),
    w12=dict(outline=(dict(coat_mm=8.0, tol_mm=6.0, points=((2668, 1580), (2668, 1620), (2667, 1660), (2665, 1700),
                                                             (2655, 1740), (2635, 1780), (2610, 1820),
                                                             (2580, 1850))),)),
    w07=dict(outline=(dict(coat_mm=6.0, tol_mm=5.0, points=((1565, 1300), (1560, 1330), (1552, 1360), (1545, 1390),
                                                             (1538, 1420), (1525, 1450), (1505, 1470),
                                                             (1480, 1478))),)))
# W2f (the lead's call 2): THE NOSE LEATHER TRACED ON w12 (research/wolf_photos/w12_headfront_winter_gwdc_2013-12.jpg;
# work/bestiary/wolf/scratch_w2f/trace_leather.py, out/w12_leather_trace.png, out/w12_nose_bright.png): photo px, mapped
# at build time into w12's solved camera (solve_front on FRONTS w12, the eyes on the clay's visible eyes) and turned so
# the leather's own axis lands on the clay's midline. half: the leather's outline from the top middle round the
# image-right side to the bottom middle, radial luminance profiles every 3 deg from (2412, 1735) (the leather dark against
# the pale hair: the first crossing of 105 walking out), the two halves mirrored about the leather's axis (x 2414.8) and
# averaged; the top, where the leather rolls onto the equally dark hair of the bridge, read by hand (the granular leather
# against the streaky hair, y 1622 at the middle); the bottom edge over the upper lip's dark hair by hand (y 1848 at the
# middle). opening: the right naris's centre (the W2e head builder's reading on w12 at 3x, (2348, 1778) / (2483, 1777),
# mirrored and averaged), its visible size 11.3 x 8.15 mm (the W2e check, w12_nose2x.png: aspect 1.37). ala: the right
# alar lobe's crest, the pale rim of the C that curls round the opening's top and lateral side (read on the brightened
# crop out/w12_nose_bright.png at 2.8x)
NOSE_W12 = dict(
    axis=2414.8,
    half=((2415, 1622), (2427, 1623), (2439, 1623), (2451, 1625), (2463, 1627), (2475, 1631), (2488, 1635), (2497, 1641),
          (2509, 1648), (2523, 1657), (2530, 1669), (2539, 1679), (2546, 1692), (2549, 1706), (2545, 1721), (2541, 1735),
          (2540, 1748), (2537, 1761), (2532, 1773), (2529, 1786), (2523, 1798), (2515, 1808), (2506, 1817), (2498, 1828),
          (2489, 1837), (2478, 1840), (2466, 1843), (2452, 1845), (2438, 1846), (2426, 1847), (2415, 1848)),
    opening=(2482.0, 1777.0), opening_mm=(11.3, 8.15),
    ala=((2470, 1742), (2490, 1744), (2505, 1752), (2514, 1765), (2516, 1778), (2512, 1790), (2503, 1797)),
    # W2i (the lead's call 2, "THE NOSE TRACED, not described"): each NOSTRIL traced on contrast-stretched gridded crops at
    # 7x (work/bestiary/wolf/scratch_w2i/crop_enh.py; out/w12_naris_L_trace.png, w12_naris_R_trace.png, the traces drawn
    # on the photo), photo px, both sides as read (the image-left one is mirrored about the axis and averaged at build
    # time, traced_nostril): the OPENING (the visible opening: the dark comma, its head medial and round, its tail
    # running laterally under the fold, and the lit floor of the vestibule under it), the DARK core (the canal's deep
    # shadow: a reference, not built), the ALAR FOLD's inner edge (where it overhangs the opening, over its top and
    # lateral side, curling under at the tail) and its outer edge (the fold's lateral slope onto the leather)
    open_r=((2441, 1768), (2443, 1757), (2449, 1748), (2458, 1744), (2470, 1744), (2480, 1748), (2489, 1756),
            (2497, 1764), (2505, 1772), (2509, 1779), (2503, 1786), (2492, 1792), (2479, 1797), (2465, 1798),
            (2452, 1795), (2444, 1786), (2441, 1777)),
    open_l=((2316, 1768), (2320, 1756), (2330, 1749), (2345, 1747), (2357, 1750), (2367, 1759), (2376, 1770),
            (2379, 1781), (2373, 1791), (2360, 1797), (2345, 1797), (2332, 1792), (2322, 1784), (2316, 1776)),
    dark_r=((2445, 1752), (2455, 1747), (2468, 1748), (2480, 1755), (2490, 1764), (2496, 1772), (2488, 1777),
            (2474, 1779), (2460, 1781), (2450, 1778), (2445, 1768)),
    dark_l=((2333, 1768), (2345, 1757), (2357, 1755), (2368, 1763), (2376, 1773), (2376, 1785), (2366, 1793),
            (2350, 1794), (2337, 1790), (2330, 1780)),
    fold_in_r=((2462, 1741), (2476, 1742), (2488, 1748), (2498, 1756), (2506, 1765), (2511, 1775), (2508, 1784)),
    fold_in_l=((2358, 1744), (2343, 1744), (2330, 1748), (2319, 1755), (2312, 1765), (2309, 1776), (2313, 1786)),
    fold_out_r=((2470, 1735), (2490, 1734), (2510, 1740), (2524, 1750), (2530, 1763), (2528, 1777), (2518, 1788),
                (2505, 1792)),
    fold_out_l=((2352, 1735), (2330, 1735), (2312, 1742), (2300, 1752), (2294, 1766), (2296, 1780), (2304, 1790),
                (2316, 1795)))
# W2i (the lead's call 3: "the fissure, TRACED from the w12 and w08 eye crops"): each eye's PALPEBRAL FISSURE canthus to
# canthus (the canthi lm_<pid>.json's readings), the upper lid margin over the iris and the lower under it, photo px,
# traced on contrast-stretched gridded crops (work/bestiary/wolf/scratch_w2i/crop_enh.py; w12 at 5x, w08 at 12x; the
# traces drawn on the photos: out/eye_traces_sheet.png); traced_fissure carries them through each photo's solved camera
# onto the lid's sphere and averages them in the left eye's frame
EYE_FISSURES = dict(
    w12=dict(L=dict(upper=((2529, 1169), (2536, 1145), (2548, 1118), (2565, 1093), (2585, 1080), (2610, 1074), (2635, 1074),
                           (2655, 1078), (2675, 1085)),
                    lower=((2675, 1085), (2668, 1105), (2655, 1125), (2635, 1142), (2610, 1152), (2585, 1158), (2560, 1163),
                           (2540, 1167), (2529, 1169))),
             R=dict(upper=((2233, 1202), (2228, 1180), (2215, 1150), (2200, 1125), (2185, 1110), (2165, 1098), (2140, 1092),
                           (2110, 1093), (2083, 1100)),
                    lower=((2083, 1100), (2088, 1125), (2100, 1145), (2120, 1162), (2145, 1172), (2170, 1178), (2195, 1185),
                           (2215, 1195), (2233, 1202)))),
    w08=dict(L=dict(upper=((661.3, 436.7), (664, 430), (668, 424), (674, 420), (682, 418), (690, 418), (697, 420), (703, 423),
                           (705.9, 425.5)),
                    lower=((705.9, 425.5), (704, 428), (700, 433), (694, 437), (686, 440), (678, 440.5), (670, 440),
                           (664, 438.5), (661.3, 436.7))),
             R=dict(upper=((556.5, 432.2), (555, 425), (552, 419), (547, 414), (540, 412), (533, 412), (526, 413), (521, 416),
                           (519.4, 418.8)),
                    lower=((519.4, 418.8), (523, 426), (529, 430), (537, 433), (545, 434.5), (552, 434), (556.5, 432.2)))))
# the upper lip's margin, the mouth line (d, q): the occlusal line at the incisors (canid.SKULL incisor_lo q -20.5),
# dropping over the upper canine's crown (the lip covers it), along the premolars to the commissure at the photos'
# mean (w01 (95, -42.5), w03 (93, -46.2), w10 (99, -53.6)); W2b's -37 there stood 10 mm high
LIP_LINE = ((10, -21.0), (20, -26.0), (30, -30.0), (40, -33.0), (50, -35.5), (60, -37.5), (75, -40.5), (88, -43.0),
            (97, -45.5))
# the eye fissure's canthi in profile (d, q), the four head profiles' mean (w01, w03, w10, w11): the lateral canthus
# 21 mm behind and 3.4 mm under the medial one; with the head's pitch this is w08's level-camera 17 deg cant
CANTHI = dict(medial=(123.9, 32.6), lateral=(145.0, 29.2))
# W2n (the lead's calls 1 and 4: the corners like for like; "the inner corner's notch running on toward the nose"): HOW
# DEEP ALONG ITS FRONT RAYS EACH CANTHUS SITS (canthi_on_rays). Each photo's corner fixes a ray through its solved camera;
# the depth along it is a rule. 'sphere': the ray's nearest approach to the lid's sphere (W2j-W2m for both: each front
# camera's limb plane). 'profile': the ray's point nearest the head profiles' canthus (CANTHI, d and q). Measured on the
# n1 build (work/bestiary/wolf/check_w2n/corner_depth.py, canthi_tri.py): the MEDIAL canthus by the profiles lands 0.4 mm
# off the clay's own skin, in front of the ball where the photos show the inner corner from the side, so the front rays,
# the profiles and the face agree on it; by the sphere rule it sat 2.1 mm inside the head, behind the globe's equator (a
# deep slot at the inner corner, hidden from the side). The LATERAL canthus by the profiles lands 6.7 mm inside the head
# (the profiles' lateral corner and the clay's face there disagree), by the sphere rule 1.6 mm off the skin: it keeps it.
# BOTH 'sphere' for now (the n1 build's): fissure_chart draws a corner out ALONG the tip-to-tip axis only, so a medial
# canthus by the profiles moves the cage's tip 5.3 mm forward of the registration's (eye_landmark's) tip, not along the
# photos' rays: ~3.4 mm low in w12's image, not like for like; as the registration's own rule it moved the fixed point
# 7.6 mm forward and down (w12 48.3 -> 49.6 deg, 36 slow steps); and the exact carry has no fixed point (fissure_chart).
# (Probe n5: the medial corner slid along the front photos' mean line of sight to the profiles' canthus, d 124.1 q 32.8,
# the side read's medial end then visible at d 124.1, folded the lid rings at the inner corner (they stay where the
# corner was): the corner on the face needs place_eye's rings to follow it; not built)
CANTHUS_DEPTH = dict(medial='sphere', lateral='sphere')
# the corners eye_landmark's fixed point registers on: both by the sphere rule. A corner carried exactly on its own rays
# moves with the registration in every camera's image plane (the photos' canthi midpoint always lands on the clay's), so
# it cannot anchor the point: with the medial corner by the profiles the iteration drifted (w12's camera 56 -> 95 deg in
# 13 steps). Tied to the globe by the sphere rule, drawn out along the tip-to-tip axis, the corners anchor it (21 steps)
CANTHUS_DEPTH_REG = dict(medial='sphere', lateral='sphere')
BUILD = dict(
    # profile_stop (d0, d1, ramp, outer tol mm): over the nasal dorsum and the stop the profile's outer tolerance is
    # 0.5 mm, not 2 (the pressure inflates the skin to the outer limit, so the tolerance became a 2 mm offset: over the
    # stop it lifted the skin into the nasal bone's 7 mm cap at d 84, a dent that moved the stop's bend to d 86)
    tol=dict(profile=(8.0, 2.0), top=(6.0, 2.0), sections=3.0, profile_stop=(60.0, 130.0, 20.0, 0.5)),
    pressure_c=1.0, size_r=16.0, pin_r=5.0, rim_r=8.0,
    rim_range=(12.0, 200.0), pin_free_nose=10.0, outer_r=8.0, sec_sigma=6.0, sec_sigma_d=4.0,
    box=((-10.0, -100.0, -95.0), (296.0, 92.0, 95.0)), h_flow=2.0, steps=300, dt=0.4, reinit=20, h=1.0, steps_b=40,
    dt_b=0.12, reinit_b=10,
    # W2f: the two-sided fronts' pins (front_pins): radius, spacing along the skin line (mm), rims ahead of this d left to
    # the leather's sculpt, stage A's further steps with them
    front_pin_r=4.0, front_pin_step=1.5, front_pin_free_d=12.0, pin_steps=150,
    clamp=(-34.0, 34.0), blur=0.7)       # the finished grid: the far field clamped (sdf_grid.md: the producer's part),
                                         # a 0.7 mm blur (the redistanced field's kinks; |grad| of a blurred distance
                                         # stays <= 1)


def data_dict():
    """the build's inputs as canid_hull.build_flow takes them"""
    prof = np.asarray(PROFILE, float)
    back = np.zeros(len(prof), bool)
    back[PROFILE_BACK[0]:PROFILE_BACK[1] + 1] = True
    fronts = {}
    for nm, fr in FRONTS.items():
        fronts[nm] = dict(landmarks={k: list(v) for k, v in fr['landmarks'].items()},
                          outline=[dict(coat_mm=s['coat_mm'], tol_mm=s['tol_mm'], points=[list(p) for p in s['points']],
                                        **({'two_sided': True} if s.get('two_sided') else {}))
                                   for s in fr['outline']])
    return dict(profile=prof, profile_back=back, top=np.asarray(TOP, float), q_rim=Q_RIM, fronts=fronts, **BUILD)


# ============================================================================================ cameras
def front_camera(alpha_deg, psi_deg):
    """a front photo's camera in the palate-aligned frame (x lateral +left, y = q, z = p): c toward the camera
    (alpha above the palate axis, psi toward the creature's left), image right r (the creature's left when facing the
    camera) and up u; projection of a (p, q, x) point: (X . r, X . u) with X = (x, q, p)"""
    a, s = np.radians(alpha_deg), np.radians(psi_deg)
    c = np.array([np.cos(a) * np.sin(s), np.sin(a), np.cos(a) * np.cos(s)])
    u = np.array([0.0, 1.0, 0.0]) - np.sin(a) * c
    u /= np.linalg.norm(u)
    r = np.cross(u, c)
    r /= np.linalg.norm(r)
    return c, r, u


def project_front(cam, d, q, x, npd):
    """palate-frame points (d, q, x mm; npd the nose tip's p in mm) -> the camera's image plane (mm)"""
    c, r, u = cam
    X = np.stack([np.asarray(x, float), np.asarray(q, float), npd - np.asarray(d, float)], -1)
    return X @ r, X @ u


def sim2(u0, u1, w0, w1):
    u0, u1, w0, w1 = (complex(*a) for a in (u0, u1, w0, w1))
    a = (w1 - w0) / (u1 - u0)
    b = w0 - a * u0
    return (lambda Q: (lambda c: np.stack([c.real, c.imag], -1))(a * (np.asarray(Q, float)[..., 0]
                                                                     + 1j * np.asarray(Q, float)[..., 1]) + b)), abs(a)


def solve_front(fr, clay):
    """the photo's camera: alpha and psi whose projection puts the clay's planum centre where the photo's sits once
    the photo's eye centres sit on the clay's visible eyes (photo y down: flipped). Returns cam, alpha, psi, the photo
    px -> image mm map and its residual (mm)"""
    from scipy.optimize import minimize
    L = fr['landmarks']
    nose_px = np.asarray(L['nose'], float) if 'nose' in L else 0.5 * (np.asarray(L['nose_R'], float) +
                                                                       np.asarray(L['nose_L'], float))
    flip = lambda Q: np.asarray(Q, float) * np.array([1.0, -1.0])
    npd = clay['np_mm']

    def fit(ap):
        cam = front_camera(*ap)
        e = [np.array(project_front(cam, *clay[k], npd)) for k in ('vis_R', 'vis_L')]
        T, sc = sim2(flip(L['eye_R']), flip(L['eye_L']), e[0], e[1])
        n_img = np.array(project_front(cam, *clay['planum'], npd))
        return cam, T, float(np.linalg.norm(T(flip(nose_px)) - n_img))
    best = minimize(lambda ap: fit(ap)[2], x0=np.array([40.0, 0.0]), method='Nelder-Mead',
                    options=dict(xatol=0.01, fatol=1e-4, maxiter=600,
                                 initial_simplex=np.array([[40.0, 0.0], [48.0, 0.0], [40.0, 8.0]])))
    cam, T, res = fit(best.x)
    return dict(cam=cam, alpha=float(best.x[0]), psi=float(best.x[1]), to_img=lambda Q: T(flip(Q)), resid=res)


def front_polygon(fr, solved, interior, far=400.0):
    """the photo's traced (image-right, top to bottom) outline in the camera's image plane (mm): the visible outline,
    its coat and tolerance per point, the skin estimate (outline - coat) and the OUTER-limit polygon (outline - coat +
    tol), closed generously round the untraced side: from the outline's lowest point straight down, then across under
    the head, up beyond the head, and back in to the outline's top point from above and inside (a closing path straight
    up from the ear's base would carve the temple)"""
    pts, coat, tol, two = [], [], [], []
    for seg in fr['outline']:
        for p in seg['points']:
            pts.append(p)
            coat.append(seg['coat_mm'])
            tol.append(seg['tol_mm'])
            two.append(bool(seg.get('two_sided', False)))
    img = solved['to_img'](np.asarray(pts, float))
    coat, tol = np.asarray(coat), np.asarray(tol)
    skin = offset_polyline(img, coat, interior)
    outer = offset_polyline(img, coat - tol, interior)
    top, bot = outer[0], outer[-1]
    close = np.array([[bot[0], bot[1] - far], [bot[0] - far, bot[1] - far], [top[0] - far, top[1] + far],
                      [top[0] - 0.25 * far, top[1] + far]])
    return dict(visible=img, skin=skin, outer=outer, polygon=np.vstack([outer, close]), tol=tol, coat=coat,
                two_sided=np.asarray(two, bool), interior=np.asarray(interior, float))


# ============================================================================================ the grid (hullflow.Grid)
def view_fields(G, sil):
    """each view's 2D signed distance at every voxel (mm): profile (d, q), top (d, |x|), each front in its camera"""
    D, Q, X = G.mesh()
    out = {}
    img, lo, res = sil['profile_img']
    out['profile'] = sample2(img, lo, res, D, Q)
    img, lo, res = sil['top_img']
    out['top'] = sample2(img, lo, res, D, np.abs(X))
    for nm, fr in sil['fronts'].items():
        u, v = project_front(fr['cam'], D, Q, X, sil['np_mm'])
        img, lo, res = fr['img']
        out['front_' + nm] = sample2(img, lo, res, u, v)
        # the head is symmetric (S = M S): a voxel y belongs only if both y and its mirror M y = (d, q, -x) project
        # inside the traced (left-side) limit in the same camera
        um, vm = project_front(fr['cam'], D, Q, -X, sil['np_mm'])
        out['front_' + nm] = np.maximum(out['front_' + nm], sample2(img, lo, res, um, vm))
    return out


# ============================================================================================ the build
def _clay_base(spec):
    """clay_points without the visible eyes: the nose tip's p, the planum's centre, and the cornea's APEX (ball_r along
    the SPEC's optical axis from the globe's centre: W2-W2m's 'visible eye'), palate frame mm"""
    from . import canid
    NP = canid.nose_p(spec)
    L = canid.landmarks_pqx(spec)
    e = np.asarray(L['eye_L'], float) + spec['eye']['ball_r'] * np.asarray(L['eye_dir_L'], float)
    apex = (1000 * (NP - e[0]), 1000 * e[1], 1000 * e[2])
    pl = np.asarray(L['nose'], float)
    return dict(np_mm=1000 * NP, apex_L=apex, apex_R=(apex[0], apex[1], -apex[2]),
                planum=(1000 * (NP - pl[0]), 1000 * pl[1], 0.0))


def clay_points(spec):
    """the clay's points the photos are matched on, palate frame mm: the nose tip's p, the VISIBLE EYES (vis_L, vis_R),
    the planum's centre; the cornea's apex as apex_L / apex_R.
    W2n (the lead's call 1, "register the photos like for like"): the visible eye is the MIDDLE OF THE CLAY'S LID
    OPENING, the midpoint of its two canthi (eye_landmark: the eye chart's fissure tips, which are carried from the
    photos through the cameras solved on this same point, iterated to a fixed point). It is the photos' own landmark:
    every front photo's eye mark is the midpoint of its canthi (w12 0.0 px, w07 / w08 within 4.5 px; the W2m fresh
    eyes, work/bestiary/wolf/check_w2m_fresh/resolve_gaze.py). W2-W2m matched it to the cornea's apex (ball_r along the
    SPEC's optical axis, 12 up / 20 out), which lands 6.0-9.2 mm off the ball's projected centre in every photo camera:
    the solved cameras came out 5-10 deg too steep, and 135 of the 296 traced fissure points missed the lid's sphere and
    were pinned onto the ball's outline (traced_fissure), building the lower lid on the outline as w12 sees it"""
    out = dict(_clay_base(spec))
    v = tuple(float(a) for a in eye_landmark(spec)['front'])
    out.update(vis_L=v, vis_R=(v[0], v[1], -v[2]))
    return out


def silhouettes(spec, data, log=print):
    """the views' polygons as 2D signed-distance rasters, the front cameras solved"""
    clay = clay_points(spec)
    prof = np.asarray(data['profile'], float)
    top = np.asarray(data['top'], float)
    top_poly = np.vstack([top, (top * [1.0, -1.0])[::-1]])
    sil = dict(np_mm=clay['np_mm'], clay=clay, profile=prof, profile_back=np.asarray(data['profile_back'], bool),
               top=top, top_poly=top_poly, fronts={})
    sil['profile_img'] = poly_sdf_image(prof, (-20.0, -130.0), (320.0, 120.0), 0.25)
    sil['top_img'] = poly_sdf_image(top_poly, (-20.0, -110.0), (320.0, 110.0), 0.25)
    for nm, fr in data['fronts'].items():
        so = solve_front(fr, clay)
        interior = np.array(project_front(so['cam'], 130.0, 10.0, 0.0, clay['np_mm']))
        fp = front_polygon(fr, so, interior)
        lo = fp['polygon'].min(0) - 5.0
        hi = fp['polygon'].max(0) + 5.0
        lo = np.maximum(lo, [-300.0, -500.0])
        hi = np.minimum(hi, [300.0, 300.0])
        sil['fronts'][nm] = dict(cam=so['cam'], alpha=so['alpha'], psi=so['psi'], resid=so['resid'],
                                 img=poly_sdf_image(fp['polygon'], lo, hi, 0.5), **fp)
        log(f'[hull] front {nm}: camera {so["alpha"]:.1f} deg above the palate axis, yaw {so["psi"]:+.1f} deg toward the '
            f'left; planum residual {so["resid"]:.1f} mm; {len(fp["visible"])} outline points')
    return sil


def constraint_balls(spec, sil, data, h):
    """the inner balls (the shape contains each) and outer balls (the shape excludes each), palate frame mm"""
    from . import canid
    SK = canid.SKULL
    inner, outer, notes = [], [], []
    dep = SK['depths']
    rows = (('nasal', SK['nasal'][0], (0, 1, 0)), ('nasal', SK['nasal'][1], (0, 1, 0)), ('stop', SK['stop'], (0, 1, 0)),
            ('frontal', SK['frontal'], (0, 1, 0)), ('crest', SK['crest'], (0, 1, 0)),
            ('zygion', SK['zygion'], (0, 0, 1)), ('canine', SK['canine'], (0, 0, 1)),
            ('mandible', SK['mandible'], (0, -1, 0)), ('chin', SK['infradentale'], (-1, 0, 0)))
    used = set()
    m_ = data.get('depth_margin', 0.5)       # inside the band by this much (the finish's blur moves the skin ~0.2 mm)
    for nm, lm, n in rows:
        lo_, hi_ = dep[nm]
        for sx in ((1, -1) if lm[2] > 0 else (1,)):
            c = np.array([lm[0], lm[1], sx * lm[2]], float)
            nv = np.array(n, float) * np.array([1, 1, sx])
            inner.append((c, lo_ + m_))
            R = data.get('outer_r', 8.0)
            outer.append((c + (hi_ - m_ + R) * nv, R))
        used.add(id(lm))
    for k in ('prosthion', 'rhinion', 'entorbitale', 'postorbital', 'postorbital_constriction', 'meatus', 'otion', 'tmj',
              'inion', 'incisor_lo', 'orbit'):
        lm = SK[k]
        for sx in ((1, -1) if lm[2] > 0 else (1,)):
            inner.append((np.array([lm[0], lm[1], sx * lm[2]], float), 2.0 if k != 'orbit' else 0.5))
    # the skull's dorsal midline and the mandible's ventral border: the minimum skin over the whole outline
    sk_d = np.array([r[0] for r in SK['dorsal']], float)
    sk_q = np.array([r[1] for r in SK['dorsal']], float)
    for d in np.arange(sk_d[0], sk_d[-1] + 0.1, 3.0):
        inner.append((np.array([d, np.interp(d, sk_d, sk_q), 0.0]), 2.5))
    sv_d = np.array([r[0] for r in SK['ventral']], float)
    sv_q = np.array([r[1] for r in SK['ventral']], float)
    for d in np.arange(sv_d[0], sv_d[-1] + 0.1, 3.0):
        inner.append((np.array([d, np.interp(d, sv_d, sv_q), 0.0]), 4.0))
    # the profile's outline pinned on the midline (not its buried back boundary): a ball of pin_r touching the outline
    # from inside (a small ball creases the surface round it: 3 mm printed ridges)
    r = data.get('pin_r', 5.0)
    P = sil['profile']
    keep = ~sil['profile_back']
    Pr = resample_closed(P, 2.0)
    # carry the back mask by nearest original point
    near = np.argmin(np.linalg.norm(Pr[:, None, :] - P[None, :, :], axis=2), axis=1)
    N = inward_normals_closed(Pr)
    n_pin = 0
    d_free = data.get('pin_free_nose', 10.0)      # the nose's front left to the leather's sculpt (pins there drew a beak)
    for p, nrm, ok in zip(Pr, N, keep[near]):
        if ok and p[0] >= d_free:
            c = p + r * nrm
            inner.append((np.array([c[0], c[1], 0.0]), r))
            n_pin += 1
    # the top view's outline pinned at its rim height over the lips, the face and the arches (behind the arches the
    # skull's sections set the breadth; rim pins there stood off the narrower braincase as islands)
    top = sil['top']
    qr = np.asarray(data['q_rim'], float)
    rr = data.get('rim_r', 8.0)
    d0r, d1r = data.get('rim_range', (12.0, 200.0))
    n_rim = 0
    for d in np.arange(d0r, d1r + 0.1, 3.0):
        w = float(np.interp(d, top[:, 0], top[:, 1]))
        q = float(np.interp(d, qr[:, 0], qr[:, 1]))
        if w > rr + 1.0:
            for sx in (1, -1):
                inner.append((np.array([d, q, sx * (w - rr)]), rr))
            n_rim += 1
    notes.append(f'{len(rows)} skull depth rows (inner ball = the minimum depth, outer ball beyond the maximum along '
                 f'the measured axis), 11 more landmarks inside by 2 mm, the skull\'s dorsal and the mandible\'s ventral '
                 f'outlines under 2.5 / 4 mm of skin, {n_pin} midline pins on the profile, {n_rim} x 2 rim pins on the top')
    return inner, outer, notes


def front_pins(G, sil, phi_ref, data, log=print):
    """W2f (the lead's call 1): the TWO-SIDED stretches of the front outlines (FRONTS segments with 'two_sided': the wet
    r03's muzzle, whisker pad and chin) as INNER limits too. Along the stretch's skin line (the outline less its coat in
    the photo's solved camera), every BUILD front_pin_step mm, a ball of front_pin_r whose projection touches the line
    from inside (its centre front_pin_r inside the line in the image plane), centred on the camera ray at the depth
    where phi_ref (the flowed head) comes nearest the ray: the rim the silhouette is made at there, moved out (or in) to
    the line; mirrored (the head is symmetric). With the outer limit front_tol mm outside the line (the segment's
    tol_mm) the silhouette is held on the line from both sides. Rims ahead of front_pin_free_d (the leather's, sculpted
    after the flow: canid_hull.STROKES leather) are left to the sculpt. Returns the inner balls ((d, q, x) mm, r)."""
    r_p = data.get('front_pin_r', 4.0)
    step = data.get('front_pin_step', 1.5)
    d_free = data.get('front_pin_free_d', 12.0)
    npd = sil['np_mm']
    hi = G.lo + (np.array(G.n) - 1) * G.h
    ts = np.arange(-320.0, 320.0, 0.5)
    pins = []
    for nm, fr in sil['fronts'].items():
        two = fr.get('two_sided')
        if two is None or not np.any(two):
            continue
        c, r, u = fr['cam']
        idx = np.nonzero(two)[0]
        n_used = n_free = 0
        for run in np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1):
            if len(run) < 2:
                continue
            Sk = np.asarray(fr['skin'][run], float)
            s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Sk, axis=0), axis=1))])
            tt = np.linspace(0.0, s[-1], max(2, int(s[-1] / step) + 1))
            Sk = np.column_stack([np.interp(tt, s, Sk[:, k]) for k in range(2)])
            T = np.gradient(Sk, axis=0)
            T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
            N = np.stack([-T[:, 1], T[:, 0]], -1)
            sgn = np.sign(np.sum((fr['interior'] - Sk) * N, axis=1))
            sgn[sgn == 0] = 1.0
            N *= sgn[:, None]
            for s_, n_ in zip(Sk, N):
                a, b = s_ + r_p * n_
                X = a * r[None] + b * u[None] + ts[:, None] * c[None]           # (x, q, p)
                P = np.column_stack([npd - X[:, 2], X[:, 1], X[:, 0]])          # (d, q, x)
                f = sample3(phi_ref, G, P)
                f[~np.all((P >= G.lo) & (P <= hi), axis=1)] = np.inf
                k = int(np.argmin(f))
                if P[k, 0] < d_free:
                    n_free += 1
                    continue
                pins.append((P[k].copy(), r_p))
                pins.append((P[k] * np.array([1.0, 1.0, -1.0]), r_p))
                n_used += 1
        log(f'[hull] front {nm}: the two-sided stretch pinned at {n_used} rims (balls of {r_p:.1f} mm every {step:.1f} mm, '
            f'mirrored; {n_free} rims ahead of d {d_free:.0f} left to the leather\'s sculpt)')
    return pins


def section_field(G, data):
    """the skull's CROSS-SECTIONS as a per-slice 2D signed distance (mm): canid.HEAD's face and (closed) jaw stations
    (the skull's dorsal profile, its breadths and the orbit's rim plus the skin, half-sections of nine points),
    interpolated along d as canid._stations does, each slice's closed polygon (the face's union the jaw's) smoothed
    along its outline over data['sec_sigma'] mm (no facets: W2b's 7 mm corner radius printed its corners as stripes),
    then its 2D distance at every voxel of the slice. Ahead of the face's first station the field is -inf (no
    limit: the nose)"""
    from matplotlib.path import Path
    from scipy import ndimage as nd
    from scipy.ndimage import gaussian_filter1d
    from . import canid
    hd = canid.HEAD
    out = np.full(G.n, -1.0e3, np.float32)
    parts = []
    for rows in (hd['face'], hd['jaw']):
        d0, d1 = rows[0][0], rows[-1][0]
        m = (G.d >= d0) & (G.d <= d1)
        halves = canid._stations(rows, G.d[m], hd['face_sigma']) if m.sum() > 1 else None
        parts.append((np.where(m)[0], halves))
    res = 0.5
    qlo, xlo = G.lo[1], -max(abs(G.x[0]), abs(G.x[-1]))
    nq = int((G.q[-1] - qlo) / res) + 2
    nx = int((-2 * xlo) / res) + 2
    Qr, Xr = np.meshgrid(qlo + np.arange(nq) * res, xlo + np.arange(nx) * res, indexing='ij')
    pts = np.column_stack([Xr.ravel(), Qr.ravel()])
    sig = data.get('sec_sigma', 6.0)
    top = np.asarray(data['top'], float)
    prof = np.asarray(data['profile'], float)
    d_face = hd['face'][0][0]
    # the nose ahead of the face's first station: the leather's traced front outline (canid.HEAD nose: w12's outline,
    # |x| and z about its centre) fitted to the box the profile and the top views give at each slice
    lea = np.asarray(hd['nose']['outline'], float)
    lea = np.vstack([lea, (lea[-2:0:-1] * np.array([-1.0, 1.0]))])
    lea_n = (lea - [0.0, lea[:, 1].min()]) / [lea[:, 0].max(), np.ptp(lea[:, 1])]      # |x| in [0, 1], z in [0, 1]

    def profile_span(d):
        """the profile polygon's q range on the vertical line through d"""
        qs = []
        for a, b in zip(prof, np.roll(prof, -1, axis=0)):
            if (a[0] - d) * (b[0] - d) <= 0 and a[0] != b[0]:
                qs.append(a[1] + (b[1] - a[1]) * (d - a[0]) / (b[0] - a[0]))
        return (min(qs), max(qs)) if len(qs) >= 2 else None
    for i in range(G.n[0]):
        polys = []
        w_top = float(np.interp(G.d[i], top[:, 0], top[:, 1], left=0.0, right=top[-1, 1]))
        if G.d[i] < d_face:
            span = profile_span(G.d[i])
            if span is None or w_top < 1.0:
                continue
            P = np.column_stack([lea_n[:, 0] * w_top, span[0] + lea_n[:, 1] * (span[1] - span[0])])
            polys.append(resample_closed(P, 1.0))
        fj = []
        for idx, halves in parts:
            if halves is None or i not in idx:
                continue
            h = halves[int(np.where(idx == i)[0][0])]                 # nine (|x|, q) points, top to bottom
            poly = np.vstack([h, (h[-2:0:-1] * np.array([-1.0, 1.0]))])
            P = resample_closed(poly, 1.0)
            P = np.column_stack([gaussian_filter1d(P[:, k], sig, mode='wrap') for k in range(2)])
            polys.append(P)
            fj.append(P)
        if len(fj) == 2:
            # THE BRIDGE: the closed mouth and the cheek are one flank, the face's lower half and the jaw's upper half
            # joined by their convex hull (the union of two sections left a waist at the lip line, printed as a groove
            # the length of the head; the mouth line is a sculpt stroke, the masseter fills the cheek)
            from scipy.spatial import ConvexHull
            Fp, Jp = fj
            q_fw = Fp[int(np.argmax(np.abs(Fp[:, 0]))), 1]
            q_jw = Jp[int(np.argmax(np.abs(Jp[:, 0]))), 1]
            B = np.vstack([Fp[Fp[:, 1] <= q_fw], Jp[Jp[:, 1] >= q_jw]])
            if len(B) >= 3:
                hull = ConvexHull(B)
                polys.append(B[hull.vertices])
        if not polys:
            continue
        # the sections' breadth set by the top view (their shape is the skull's): one lateral scale per slice so the
        # union's widest |x| is the top outline's half-width (clipped to 0.85-1.25)
        if G.d[i] >= d_face:
            ws = max(float(np.abs(P[:, 0]).max()) for P in polys)
            s = float(np.clip(w_top / max(ws, 1e-6), 0.85, 1.25))
            polys = [P * np.array([s, 1.0]) for P in polys]
        inside = np.zeros(len(pts), bool)
        for P in polys:
            inside |= Path(P).contains_points(pts)
        inside = inside.reshape(nq, nx)
        sd = (nd.distance_transform_edt(~inside) - nd.distance_transform_edt(inside)
              + np.where(inside, 0.5, -0.5)) * res
        fq = (G.q - qlo) / res
        fx = (G.x - xlo) / res
        FQ, FX = np.meshgrid(fq, fx, indexing='ij')
        out[i] = nd.map_coordinates(sd, [FQ.ravel(), FX.ravel()], order=1, mode='nearest').reshape(G.n[1], G.n[2])
    # smoothed along d (each slice was built alone: its own polygon and lateral scale printed as vertical bands down
    # the muzzle and the cheek wherever the surface pressed against the limit)
    have = out[:, 0, 0] > -999.0
    sm = gaussian_filter1d(np.where(have[:, None, None], out, 0.0), data.get('sec_sigma_d', 4.0) / G.h, axis=0,
                           mode='nearest')
    wsum = gaussian_filter1d(have.astype(np.float32), data.get('sec_sigma_d', 4.0) / G.h, mode='nearest')
    out = np.where(have[:, None, None], sm / np.maximum(wsum, 1e-6)[:, None, None], out)
    return out.astype(np.float32)


def hull_fields(G, sil, data, inner, outer, log=print):
    """phi_H (the hull), the lower / upper bounds, the pressure, per voxel"""
    vf = view_fields(G, sil)
    if data.get('sections', True):
        vf['sections'] = section_field(G, data)
    ti_p, to_p = data['tol']['profile']
    ti_t, to_t = data['tol']['top']
    to_s = data['tol'].get('sections', 3.0)
    ps = data['tol'].get('profile_stop')
    if ps:                      # the outer tolerance tightened over d0-d1, smoothstep ramps of `ramp` mm either side
        d0, d1, ramp, tt = ps
        w = np.clip(np.minimum((G.d - (d0 - ramp)) / ramp, ((d1 + ramp) - G.d) / ramp), 0.0, 1.0)
        to_p = (to_p - (to_p - tt) * w * w * (3.0 - 2.0 * w))[:, None, None]
    fronts = [(k, v) for k, v in vf.items() if k.startswith('front_')]
    outer_parts = [('profile', vf['profile'] - to_p), ('top', vf['top'] - to_t)] + fronts
    if 'sections' in vf:
        outer_parts.append(('sections', vf['sections'] - to_s))
    phi_h = np.maximum(vf['profile'], vf['top'])
    for _, f in fronts:
        phi_h = np.maximum(phi_h, f)
    if 'sections' in vf:
        phi_h = np.maximum(phi_h, vf['sections'])
    phi_o = outer_parts[0][1]
    for _, f in outer_parts[1:]:
        phi_o = np.maximum(phi_o, f)
    # the eroded views as an inner bound: OFF by default (its sections are rectangles inset by the tolerance, so it
    # forces box corners against the skull's sections; the silhouettes are held by the rim pins instead)
    phi_i = np.maximum(vf['profile'] + ti_p, vf['top'] + ti_t) if data.get('inner_views', False) \
        else np.full(G.n, np.inf, np.float32)
    up_b, lo_b = ball_bounds(G, inner, outer)
    upper = np.minimum(phi_i, up_b)
    lower = np.maximum(phi_o, lo_b)
    clash = lower > upper
    if clash.any():
        # which outer limit meets which inner one
        rows = []
        for nm, f in outer_parts + [('outer balls', lo_b)]:
            for nm2, g in (('eroded views', phi_i), ('inner balls', up_b)):
                c = int(((f > g) & clash).sum())
                if c:
                    rows.append(f'{nm} vs {nm2} {c}')
        log(f'[hull]   {int(clash.sum())} voxels where an outer limit meets an inner one (the inner wins): '
            + ', '.join(rows))
    lower = np.minimum(lower, upper)
    # the pressure at the hull's own scale: F = 1 / (c r), r the deepest the hull reaches within data['size_r'] mm (a
    # min filter of its distance), so the jaw inflates at the jaw's size and the cranium at the cranium's (scaled by
    # the head's top width the jaw shrank to a round blob)
    from scipy import ndimage as nd
    k = max(3, int(2 * data.get('size_r', 16.0) / G.h) | 1)
    r_loc = -nd.minimum_filter(phi_h, size=k, mode='nearest')
    pressure = 1.0 / (data['pressure_c'] * np.clip(r_loc, 8.0, 90.0))
    return dict(views=vf, phi_h=phi_h.astype(np.float32), lower=lower.astype(np.float32),
                upper=upper.astype(np.float32), pressure=pressure.astype(np.float32), clash=int(clash.sum()))


def silhouette_errors(G, phi, sil, res=0.5):
    """each view's silhouette of phi's solid against the traced skin outline: per view (n, median |e|, p90 |e|, mean,
    max |e|) mm, e > 0 where the traced outline lies OUTSIDE the clay. The silhouette: the minimum of phi along each
    ray (profile along x, top along q, fronts along the camera), upsampled to `res`, its zero set by a signed EDT"""
    from scipy import ndimage as nd
    out = {}

    def sd_from_min(mn, lo2, h2, pts):
        # the fine raster at exact coordinates lo2 + i res, the coarse min-phi sampled there (bilinear)
        nu, nv = int((mn.shape[0] - 1) * h2 / res) + 1, int((mn.shape[1] - 1) * h2 / res) + 1
        U, V = np.meshgrid(np.arange(nu) * res / h2, np.arange(nv) * res / h2, indexing='ij')
        z = nd.map_coordinates(mn, [U.ravel(), V.ravel()], order=1, mode='nearest').reshape(nu, nv)
        m = z < 0
        sd = (nd.distance_transform_edt(~m) - nd.distance_transform_edt(m) + np.where(m, 0.5, -0.5)) * res
        fu = (pts[:, 0] - lo2[0]) / res
        fv = (pts[:, 1] - lo2[1]) / res
        return nd.map_coordinates(sd, [fu, fv], order=1, mode='nearest')

    def stats(e, pts=None):
        a = np.abs(e)
        r = dict(n=int(len(e)), med=float(np.median(a)), p90=float(np.percentile(a, 90)), mean=float(np.mean(e)),
                 max=float(a.max()))
        if pts is not None:
            r['pts'], r['e'] = np.asarray(pts, float), np.asarray(e, float)
        return r
    # profile: the polygon's outline less its buried back boundary
    P = resample_closed(sil['profile'], 1.0)
    near = np.argmin(np.linalg.norm(P[:, None, :] - sil['profile'][None, :, :], axis=2), axis=1)
    P = P[~sil['profile_back'][near]]
    mn = phi.min(axis=2)
    out['profile'] = stats(sd_from_min(mn, G.lo[[0, 1]], G.h, P), P)
    # top: the half outline (x > 0.5) ahead of the neck
    T = sil['top']
    T = T[(T[:, 1] > 0.5) & (T[:, 0] < 260)]
    mn = phi.min(axis=1)
    out['top'] = stats(sd_from_min(mn, G.lo[[0, 2]], G.h, T), T)
    # fronts: splat min phi into the camera raster
    D, Q, X = G.mesh()
    for nm, fr in sil['fronts'].items():
        u, v = project_front(fr['cam'], D, Q, X, sil['np_mm'])
        lo2 = np.array([u.min(), v.min()]) - 2 * G.h
        iu = ((u - lo2[0]) / G.h).astype(int).ravel()
        iv = ((v - lo2[1]) / G.h).astype(int).ravel()
        R = np.full((iu.max() + 2, iv.max() + 2), 1e3, np.float32)
        np.minimum.at(R, (iu, iv), phi.ravel())
        R = np.where(R >= 1e3, nd.grey_erosion(R, size=(3, 3)), R)      # fill only the pixels no voxel landed in
        skin = fr['skin']
        out['front_' + nm] = stats(sd_from_min(R, lo2, G.h, skin), skin)
        out['front_' + nm]['coat_note'] = f'outline less {fr["coat"].min():.0f}-{fr["coat"].max():.0f} mm of coat'
    return out


def build_flow(spec, data, log=print):
    """stage A (data['h_flow'] mm) and stage B (data['h'] mm): the hull, its constraints, the flow; returns the
    refined phi with its grid and the diagnostics"""
    sil = silhouettes(spec, data, log)
    lo, hi = data['box']
    GA = Grid(lo, hi, data['h_flow'])
    inner, outer, notes = constraint_balls(spec, sil, data, GA.h)
    for n_ in notes:
        log('[hull] constraints: ' + n_)
    t = time.time()
    FA = hull_fields(GA, sil, data, inner, outer, log)
    log(f'[hull] stage A grid {GA.n} at {GA.h} mm: fields in {time.time() - t:.1f}s; hull volume '
        f'{(FA["phi_h"] < 0).sum() * GA.h ** 3 / 1e6:.3f} l')
    phi0 = redistance(FA['phi_h'], GA.h)
    err_hull = silhouette_errors(GA, phi0, sil)
    t = time.time()
    phiA, histA = flow(phi0, FA['lower'], FA['upper'], FA['pressure'], GA.h, data['steps'], data['dt'],
                       data.get('reinit', 20), log)
    log(f'[hull] stage A flow: {data["steps"]} steps in {time.time() - t:.0f}s')
    # W2f (the lead's call 1): the two-sided fronts' pins on the flowed rim, then stage A again from there with them (the
    # inner limits clamp the surface out to the balls; the further steps round the surface round them and the pressure
    # fills between); stage B and the relax keep them
    pins = front_pins(GA, sil, phiA, data, log)
    if pins:
        inner = inner + pins
        t = time.time()
        FA = hull_fields(GA, sil, data, inner, outer, log)
        phiA, histA2 = flow(phiA, FA['lower'], FA['upper'], FA['pressure'], GA.h, data.get('pin_steps', 150),
                            data['dt'], data.get('reinit', 20), log)
        histA = histA + histA2
        log(f'[hull] stage A with the pins: {data.get("pin_steps", 150)} steps in {time.time() - t:.0f}s')
    err_a = silhouette_errors(GA, phiA, sil)
    # stage B: 1 mm
    from scipy import ndimage as nd
    GB = Grid(lo, hi, data['h'])
    fz = [GB.n[a] / GA.n[a] for a in range(3)]
    phiB = nd.zoom(phiA, fz, order=1, mode='nearest', grid_mode=False)[:GB.n[0], :GB.n[1], :GB.n[2]]
    pad = [(0, GB.n[a] - phiB.shape[a]) for a in range(3)]
    phiB = np.pad(phiB, pad, mode='edge')
    t = time.time()
    FB = hull_fields(GB, sil, data, inner, outer, log)
    phiB = redistance(phiB.astype(np.float32), GB.h)
    phiB, histB = flow(phiB, FB['lower'], FB['upper'], FB['pressure'], GB.h, data['steps_b'], data['dt_b'],
                       data.get('reinit_b', 15), log)
    log(f'[hull] stage B grid {GB.n} at {GB.h} mm: {data["steps_b"]} steps in {time.time() - t:.0f}s')
    # the RELAX: pure mean-curvature flow, short (t ~ 3.6 mm^2: bands under ~6 mm decay, the shape moves ~kappa t,
    # 0.05 mm), held only by the skull's balls and the pins: the slices' faint bands where the surface pressed on the
    # sections' limit
    if data.get('relax_steps', 30):
        lo_free = np.full(GB.n, -np.inf, np.float32)
        up_balls, _ = ball_bounds(GB, inner, [])
        phiB, _ = flow(phiB, lo_free, up_balls, np.zeros(GB.n, np.float32), GB.h, data.get('relax_steps', 30),
                       data.get('dt_b', 0.12), data.get('reinit_b', 10), None)
    err_b = silhouette_errors(GB, phiB, sil)
    return dict(phi=phiB, grid=GB, sil=sil, fields=FB, errors=dict(hull=err_hull, flow_2mm=err_a, flow=err_b),
                hist=(histA, histB), inner=inner, outer=outer, phi_h=FB['phi_h'])


# ============================================================================================ the sculpt (STROKES)
STROKES = dict(
    # W2d head (the lead's call 7, "a flat-fronted puck"): the pad's front a ROUND cap (dome_shape: continuous
    # curvature, meeting the sides tangentially, no rim; W2c's rho^1.6 plateau met them at ~45 deg), its centre 2 mm
    # ahead (-2.0, the profiles' tip -2.5), the rim 13 mm behind, rounded 7 mm, filleted 7 mm into the muzzle
    # (scratch_w2dh/nose_look.py variants cur -> b3, looked at)
    # W2e head (the lead's call 2, "a round disc with the nares at its bottom rim: a pig snout; rebuild from w12 / w08: a
    # rounded trapezoid broad at the top ... w08's width"): the PAD's own front outline (pad_outline (|x|, z) about
    # pad_centre_q 10.5: the top edge broad (34 mm across its corners), the widest 36.6 mm at the alae just under the
    # middle, narrowing to 14 mm at the philtrum, q -7.9 .. 22.5), and its dome falling back only pad_dome_bot under
    # q 3 (13 over q 11): the leather continues under the nares, as w08 / w12 show 12-15 mm of it under their nares'
    # centres and the profiles' traced leathers (w03, w11) run their fronts down to q -3..-6 at d ~2. Measured in the
    # solved cameras (work/bestiary/wolf/scratch_w2e/nose_lab.py, the head builder's probe: the skin within 3 mm of the
    # pad, facing): w08 76.9 px wide [w08 77; W2d 88.9], height / width 0.93 [0.81]; over w12's traced leather IoU 0.86
    # [W2d 0.84]. canid.HEAD nose's outline still shapes the hull's nose sections and keys the flow
    # W2f (the lead's call 2): the dome CURVED everywhere (dome_shape 'curved': rho over the inradius pad_rho_r, the front
    # falling back as rho^dome_exp; W2e's round cap stood flat inside 13 mm of its rim, the plate), and held inside the
    # profile photos' outline, sinking prof_inset mm under the bridge's line over its top (no rim)
    # W2g (the lead's call 3: "the leather at the photos' ratio (about 0.58 of the eye spacing)"): the pad's outline 1.05 x
    # as wide (pad_scale_x; 38.4 mm across the pad, its widest at the alae, the analytic ALAR FOLDS standing on its lower
    # lateral corners out to |x| ~24); the leather's width over the eye spacing in w12's camera is measured by w02's
    # 'the nose's read' against the photos' 0.508-0.595 (median 0.572)
    leather=dict(dome=1.2, ramp=5.0, d_full=8.0, d_end=20.0,           # the domed nose leather (mm): its rise, the
                 pad_front=-2.0, pad_dome=13.0, pad_back=22.0, pad_k=7.0,  # ramp, its extent along d; the PAD (w12's
                 pad_round=7.0, pad_centre_q=10.5, dome_shape='curved',  # rim's rounding; its centre q (W2d 9: the
                 pad_dome_bot=5.0, pad_dome_q=(3.0, 11.0),               # profiles' leather loops centre near q 9)
                 pad_rho_r=15.0, dome_exp=1.5, prof_inset=((14.0, 0.0), (19.0, 1.2), (24.0, 1.8)), pad_scale_x=1.05,
                 pad_outline=((0, 12.0), (8, 11.9), (12, 11.4), (14.8, 10.2), (16.6, 7.6), (17.8, 3.4), (18.3, -1.5),
                              (18.1, -5.5), (17.2, -9.0), (15.2, -12.5), (11.8, -15.6), (7.0, -17.6), (0, -18.4))),
    # W2g (the lead's call 2: "THE LIPS AND WHISKER PADS BUILT AS MASSES, not flow inflation"): face_masses on the flowed
    # skin, smooth-unioned (k mm) before the leather sits on them, over d < d_max where the flowed head is within reach
    # mm. lip (d, q, r, e): the upper lip from beside the philtrum to the commissure, each station's round cone r mm,
    # standing e mm over the flowed skin at (d, q); pad: the mystacial pad beside and under the leather; chin. Fitted in
    # r03's solved camera to its wet stretch (canid_hull FRONTS r03, less its 2 mm: work/bestiary/wolf/scratch_w2g/
    # rim_probe.py): the flowed head stood +5.0..+9.1 mm inside it (the flank at d 40-50 +7.5..+9.1, the muzzle's side
    # d 23-40 +5.1..+6.1, beside the leather +5.7..+8.2, under it +7.6..+8.9, the chin +6.9..+8.2); with the masses the
    # flank and the pads within -1.2..+1.7 (the top point by the ruff +4.1) and the chin +3.7..+4.7 (the profile photos'
    # jaw line holds the chin's front: a chin mass far enough out for r03 hung as a plate under the lips, m2). Tried
    # again in W2g's run w2g2: 12 x 11 x 14 at (25, -37) brought r03's whole stretch to p90 |e| 1.9 but stood as a BALL
    # under the lower lip in every profile photo (tests/out/wolf/w02_head_profile_sheetw2g2.png; w02_head_viewsw2g2.png),
    # and a wider flatter chin (9 x 9 x 18 at (27, -35)) read r03 p90 4.5: r03's chin rows follow the wet hair hanging
    # under its chin (out/face_chin2.png), so the chin stays here (r03 p90 3.9, the chin +3.7..+4.7). The lips at the
    # commissure (d 74, 92) stand 2.5 / 3.5 mm INSIDE the flowed skin (their union's bulge alone): no photo shows the
    # muzzle's width there, so it keeps the estimate's 64-76 at d 80 (75.8; at +2.5 / +0.5 it read 80)
    masses=dict(k=7.0, k_chain=2.0, k_pad=6.0, d_max=112.0, reach=22.0, lip_step=3.0,
                lip=((11, -13, 7, 4), (18, -15, 10, 5), (30, -15, 12, 3.5), (44, -12, 14, 6), (58, -16, 13, 5),
                     (74, -24, 10, -2.5), (92, -36, 6, -3.5)),
                pad=((18, -6, (12, 12, 10), 6),),
                chin=((24, -34, 0), (10, 8, 12))),
    # the median groove from under the nares down the leather and the upper lip to the lip margin (W2e: 1.3 -> 1.5 deep).
    # W2g (the lead's call 3: "the philtrum a real GROOVE splitting the upper lip"): this displacement off (depth 0); the
    # groove is an analytic chain over the grid (canid HEAD nares philtrum, nose_members), widening down the lip
    philtrum=dict(depth=0.0, sigma=1.1, q_top=8.0, q_bot=-21.5, d_end=14.0),
    mouth=dict(depth=2.2, sigma=1.4, step_up=0.7, step_dn=-0.9, step_w=3.0, tail=6.0),   # the mouth line and the lips
    # W2d head: the brow 2.2 -> 1.6 mm and the orbit's skin 3.0 -> 3.8 mm over the cornea (W2c's eyes read as round
    # sockets under heavy brows from the front)
    # W2f (the lead's call 3: "almond openings under a BROW (the skull's supraorbital process plus the skin depth ...),
    # not small pits on a flat face"): the brow a ridge 2.8 mm proud over the supraorbital margin (W2d 1.6: no shelf), its
    # crest along the margin from over the medial canthus round the postorbital process (canid.SKULL postorbital (141, 50,
    # 33) plus the skin) to the lateral canthus' end, the orbit's hollow tighter under it (sigma_q 9 -> 6.5) so the shelf
    # overhangs the upper lid instead of the whole eye sitting in a dish
    # W2g (call 4): the brow 2.8 -> 1.5 mm and the orbit's hollow broader (sigma_d 12 -> 16, sigma_q 6.5 -> 9, x_min 18 ->
    # 14) and closer to the cornea (lids 3.8 -> 2.0): the lids round the almond's ends and the brow over it stood as walls
    # the front cameras (38-51 deg over the palate) could not see past, so the opening read as a slit under a ledge
    # (scratch_w2g eye_open_e14 -> e17: the visible opening 0.187 -> 0.209 IO median)
    brow=dict(height=1.5, sigma=5.0, points=((116.0, 43.0, 22.0), (129.0, 47.5, 34.0), (141.0, 48.0, 44.0),
                                             (150.0, 43.0, 52.0))),
    orbit=dict(lids=2.0, sigma_d=16.0, sigma_q=9.0, x_min=14.0),      # the orbit's hollow: the skin brought to the
                                                                         # cornea plus the lids' thickness (mm), its
                                                                         # extent; not within x_min of the midline
    # W2d head (the lead's call 7, "the eyes' almond from the front"): the fissure runs canthus_dx mm LATERAL from the
    # medial to the lateral canthus (W2c: 12, so the 28 mm almond ran mostly along d and a front camera saw it 12 mm
    # long, round): the front views measure the canthi 20.5 / 24.7 mm apart across (w08, level), 19 / 23 (w07), 27 / 26
    # (w12, from above; research/wolf_work/data/lm_w0*.json canthus points at IO 80); and the opening a LENS, two arcs
    # meeting in pointed canthi, its lid ring along it (an ellipse rounds the canthi). W2e head (the lead's call 2: "the
    # eye's almond 22-25 mm canthus to canthus at 15-19 deg (now 27 mm at 9-14)"): half-length 14 -> 12 mm and the
    # lateral canthus lifted cant_q 3.2 mm: in w08's level camera 23.6 / 23.1 mm, the lateral canthus +17.3 / +17.7 deg
    # over the interocular line [w08 21.8 / 25.4 mm, 16.8 / 17.2 deg (lm_w08); W2d 27.2 / 26.5 mm, +11.4 / +11.7]
    # W2g (the lead's call 4: "the lids WRAP the 24 mm globe with the corners near its equator (no flat-floored cut 3 mm
    # past the cornea) ... Gate the VISIBLE opening"): the lens prism now THROUGH THE BALL'S CENTRE along prism_axis
    # (elevation over the palate axis, splay out, deg: between the optical axis (12, 20) and the front cameras (38-51, 0)),
    # cutting only what lies outside the globe and in front of its centre plane (floor 'sphere'), so the globe shows over
    # the whole almond out to its outline (W2f's floor 3 mm past the cornea: within 7.9 mm of its centre, 11-13 mm), half
    # length 15 mm (the canthi just past the globe's outline: shallow dark corners, the medial one the caruncle's place),
    # rolled -22 deg in its plane (the level front w08's cant), k 1.5 -> 0.8 and the globe's union 1.0 -> 0.5 mm (the
    # narrow corners closed under the wider blends), the lid ring 1.3 -> 0.6 mm; the cut held inside the globe's outline
    # along the prism (rim_in) and through at most `far` 5 mm of skin past the cornea's level (a straight tunnel through
    # the thick skin at the medial canthus stood as a box-walled pocket in profile: eye_open / views_eyes_e15, e16). The
    # wrapped-shell variant (the lids lowered onto a shell R + t, the fissure cut on the sphere's directions) was tried
    # and left craters and pockets on the 1 mm grid (work/bestiary/wolf/scratch_w2g/out/eye_open_e1-e8.png); this one:
    # eye_open_e17.png, views_eyes_e17.png
    eye=dict(half=(15.0, 5.3, 9.0), sink=2.0, k=0.8, lid=0.6, lid_at=1.12, lid_w=0.14, globe_k=0.5, canthus_dx=21.0,
             lens=True, cant_q=3.2, floor='sphere', prism_axis=(28.0, 10.0), roll=-22.0, far=5.0, rim_in=0.3),
                                                                         # (half-axes along the canthi, across, into
                                                                         # the head), the globe (SPEC eye.ball_r round
                                                                         # canid's eye centre) seated inside it
    # W2d head: THE ALAE, a rounded lobe over each naris's lateral side (w12, w06), the slit and the opening are the
    # program's analytic members (canid HEAD nares): centre (q, |x|) on the leather's skin, sunk / half-widths d, q, x.
    # W2e head: with the raised nares (q 10, |x| 16; W2d 6.5, 18) and lower (1.6 mm; W2d 2.4) inside w08's width
    alae=dict(q=10.0, x=16.0, sink=1.5, sd=4.5, sq=4.5, sx=4.0, height=1.6),
    # W2e head (the lead's call 2: "the chin ring goes"): W2d's chin ring (STROKES chin, a 2.2 mm ring round the knob's
    # axis) read as a round pad under the mouth from the front (the W2d check); removed, the chin back to the hull's and
    # the skin-depth ball's own (w02's chin depth 6.5 mm against its 6-16 band at W2d's body run)
    # W2c CHECK's NARES (an ellipsoid and a slit capsule carved into the 1 mm grid, its rims ragged at the grid) moved
    # at W2d to analytic members over the grid (canid HEAD nares, canid_hull.nares_members): a STROKES['nares'] entry
    # (x, q, half, tilt_up, tilt_in, k, slit_a, slit_b, slit_r) still carves them into the grid as W2c did
)


def _smin(a, b, k):
    h_ = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h_) + a * h_ - k * h_ * (1 - h_)


def face_masses(P, phi0, G, ms):
    """W2g (the lead's call 2: "THE LIPS AND WHISKER PADS BUILT AS MASSES, not flow inflation: the upper lip along its
    line from the philtrum to the commissure, hanging over the lower jaw as the flews; the mystacial (whisker) pads as
    full rounded masses beside and under the leather; the chin"): the field (mm) at P (n, 3) (d, q, x) of the union of
    the face's soft masses, mirrored (evaluated at |x|), each placed on the FLOWED skin phi0 (the hull's head before the
    sculpt) so its thickness over that skin is the table's e (mm):
      lip   the upper lip, a chain of round cones through stations (d, q, r, e): each centre at the station's (d, q),
            r inside the flowed skin's |x| there plus e, so its outer surface stands e mm beyond the skin at that
            height (the lip's own fullness over the maxilla and the teeth); consecutive cones unioned with k_chain
      pad   the mystacial pads, ellipsoids (d, q, half (d, q, x), e): the centre's |x| the flowed skin's at (d, q) less
            the lateral half-axis plus e
      chin  the chin under the lower lip, an ellipsoid ((d, q, x), half (d, q, x)) on the midline
    Returns the field (1000 mm where no mass is given)"""
    Pm = np.column_stack([P[:, 0], P[:, 1], np.abs(P[:, 2])])
    f = np.full(len(P), 1.0e3)
    if 'lip' in ms:
        from scipy.interpolate import PchipInterpolator
        st = np.asarray(ms['lip'], float)
        # the control stations resampled every lip_step mm along d (PCHIP: q, r and e change smoothly, so the chain of
        # short round cones is one tapered tube; a few long cones printed each junction as a lump)
        dd = np.arange(st[0, 0], st[-1, 0] + 1e-9, ms.get('lip_step', 3.0))
        st = np.column_stack([dd] + [PchipInterpolator(st[:, 0], st[:, k])(dd) for k in (1, 2, 3)])
        xs = surface_x(phi0, G, st[:, 0], st[:, 1])
        assert np.all(np.isfinite(xs)), ('a lip station lies outside the flowed head', st[~np.isfinite(xs)])
        C = np.column_stack([st[:, 0], st[:, 1], xs - st[:, 2] + st[:, 3]])
        g = np.full(len(P), 1.0e3)
        for a, b, ra, rb in zip(C[:-1], C[1:], st[:-1, 2], st[1:, 2]):
            g = _smin(g, sd_roundcone_np(Pm, a, b, ra, rb), ms.get('k_chain', 4.0))
        f = np.minimum(f, g)
    for d_, q_, half_, e_ in ms.get('pad', ()):
        xs = float(surface_x(phi0, G, np.array([float(d_)]), np.array([float(q_)]))[0])
        assert np.isfinite(xs), ('a pad centre lies outside the flowed head', d_, q_)
        c = np.array([d_, q_, xs - half_[2] + e_])
        f = _smin(f, ellipsoid_sd(Pm, c, np.eye(3), np.asarray(half_, float)), ms.get('k_pad', 4.0))
    if 'chin' in ms:
        c_, half_ = ms['chin']
        f = _smin(f, ellipsoid_sd(Pm, np.asarray(c_, float), np.eye(3), np.asarray(half_, float)), ms.get('k_pad', 4.0))
    return f


def leather_pad(P, lv=None):
    """THE NOSE LEATHER PAD's field (mm) at points P (n, 3) (d, q, x) mm: canid.HEAD nose's front outline ((|x|, z)
    about STROKES leather pad_centre_q) puffed into a dome (its front on the centre at d pad_front, its rim pad_dome
    behind), the rim rounded pad_round, its back at pad_back; the sculpt smooth-unions it into the muzzle, and the
    probes read 'the leather as the clay shows it' as the skin near it. Returns (field, the outline polygon (x, q),
    the outline's 2D distance image (img, lo, res))"""
    from . import canid
    lv = STROKES['leather'] if lv is None else lv
    # W2e head: the pad's own front outline when given (STROKES leather pad_outline); canid.HEAD nose's outline also
    # shapes the hull's nose sections (section_field) and keys the flow's cache, so it stays
    half = np.asarray(lv.get('pad_outline', canid.HEAD['nose']['outline']), float) * [lv.get('pad_scale_x', 1.0), 1.0]
    poly = np.vstack([np.column_stack([half[:, 0], lv['pad_centre_q'] + half[:, 1]]),
                      np.column_stack([-half[-2:0:-1, 0], lv['pad_centre_q'] + half[-2:0:-1, 1]])])
    img, lo2, r2 = poly_sdf_image(poly, (-40.0, -30.0), (40.0, 50.0), 0.25)
    s2n = sample2(img, lo2, r2, P[:, 2], P[:, 1])
    rho2 = np.clip(1.0 + s2n / 13.0, 0.0, 1.0)              # 0 on the outline's deepest, 1 on the outline
    dome = lv['pad_dome']
    if 'pad_dome_bot' in lv:
        # W2e head: the dome's fall-back smaller low on the leather (pad_dome_bot under q pad_dome_q[0], pad_dome over
        # pad_dome_q[1]): the leather's lower front stays forward under the nares, as the profiles' traced leathers
        # (w03, w11: their fronts down to q -3..-6 at d ~2) and as the fronts see it (w08, w12: 12-15 mm of leather
        # under the nares' centres); W2d's round cap fell 13 mm back all round, so a camera from above saw ~3-5 mm
        q0, q1 = lv['pad_dome_q']
        t_ = np.clip((P[:, 1] - q0) / (q1 - q0), 0.0, 1.0)
        dome = lv['pad_dome_bot'] + (lv['pad_dome'] - lv['pad_dome_bot']) * t_ * t_ * (3.0 - 2.0 * t_)
    if lv.get('dome_shape') == 'curved':
        # W2f (the lead's call 2: "a flat round plate"): rho over the outline's INRADIUS (pad_rho_r), so the front falls
        # back from its deepest point outward everywhere (W2d / W2e's round cap measured rho over 13 mm from the rim and
        # stood flat over the middle: the plate), as rho^dome_exp
        rho2 = np.clip(1.0 + s2n / lv['pad_rho_r'], 0.0, 1.0)
        d_front = lv['pad_front'] + dome * rho2 ** lv.get('dome_exp', 1.5)
    elif lv.get('dome_shape') == 'round':
        # W2d head: a round cap (1 - sqrt(1 - rho^2)): continuous curvature from the centre and a vertical tangent at
        # the outline, so the front meets the pad's sides without a rim (W2c's rho^1.6 plateau met them at ~45 deg:
        # the lead's "flat-fronted puck")
        d_front = lv['pad_front'] + dome * (1.0 - np.sqrt(np.maximum(0.0, 1.0 - rho2 ** 2)))
    else:
        d_front = lv['pad_front'] + dome * rho2 ** lv.get('dome_exp', 1.6)
    smax = lambda a, b, k: -_smin(-a, -b, k)
    # the rim rounded (a hard max printed the pad as a flat-faced plug with a crisp edge)
    pad = smax(smax(s2n, d_front - P[:, 0], lv['pad_round']), P[:, 0] - lv['pad_back'], 2.0)
    if 'prof_inset' in lv:
        # W2f (the lead's call 2: "the leather's top rolling onto the bridge (no rim)"): the pad held inside the profile
        # photos' outline (PROFILE), by prof_inset mm interpolated over q ((q, inset) rows): on the midline the front is
        # the profile's, and over the top the pad sinks under the bridge's line so the leather rolls onto it (W2e's pad
        # top stood as a ledge on the dorsum, its back corner at d 20-22)
        qi = np.asarray(lv['prof_inset'], float)
        pim = poly_sdf_image(np.asarray(PROFILE, float), (-20.0, -40.0), (60.0, 60.0), 0.25)
        pad = smax(pad, sample2(*pim, P[:, 0], P[:, 1]) + np.interp(P[:, 1], qi[:, 0], qi[:, 1]), 1.0)
    return pad, poly, (img, lo2, r2)


def nose_frame(spec, rv=None):
    """W2f (the lead's call 2): the traced leather (NOSE_W12) in w12's SOLVED camera (solve_front on FRONTS w12: the eyes
    on the clay's visible eyes, the planum on the photo's nose): the camera (c, r, u: (x, q, p) toward the camera, image
    right, image up; image mm = (X . r, X . u) with X = (x, q, npd - d)), the leather's outline turned so the photo's
    leather axis lands vertical on the clay's midline and mirrored (image mm), its half width per image height, the
    midline FRONT as the depth toward the camera per image height (the profile photos' leather, PROFILE's nose: the
    front each image height sees; the photo's leather top lands on the bridge 16-24 mm behind the tip, v_lt the profile
    leather's own top), the alar crest and the opening's centre (image mm). Used to carry the traced lobes and openings
    onto the clay (on_skin_w12) and by the nose gate's overlay"""
    rv = {} if rv is None else rv
    nw = NOSE_W12
    clay = clay_points(spec)
    so = solve_front(dict(landmarks=FRONTS['w12']['landmarks']), clay)
    c, r, u = (np.asarray(a, float) for a in so['cam'])
    npd = clay['np_mm']
    half_px = np.asarray(nw['half'], float)
    A = so['to_img'](np.array([[nw['axis'], half_px[:, 1].min()], [nw['axis'], half_px[:, 1].max()]]))
    a = (A[0] - A[1]) / np.linalg.norm(A[0] - A[1])              # the photo's leather axis, upward, image mm
    ph = np.arctan2(a[0], a[1])
    Rm = np.array([[np.cos(ph), -np.sin(ph)], [np.sin(ph), np.cos(ph)]])
    mid = 0.5 * (A[0] + A[1])
    u_ax = float((npd - rv.get('d_axis', 4.0)) * r[2])            # the clay's midline (x 0) at the leather's depth
    to_leather = lambda Q: (so['to_img'](np.asarray(Q, float)) - mid) @ Rm.T + mid + np.array([u_ax - mid[0], 0.0])
    half = to_leather(half_px)
    half[:, 0] = np.maximum(half[:, 0], u_ax)
    half[0, 0] = half[-1, 0] = u_ax
    full = np.vstack([half, (half * [-1.0, 1.0] + [2.0 * u_ax, 0.0])[-2:0:-1]])
    vg = np.arange(half[:, 1].min() - 0.5, half[:, 1].max() + 0.5, 0.25)
    hw = np.zeros_like(vg)
    for a_, b_ in zip(half[:-1], half[1:]):
        lo_, hi_ = min(a_[1], b_[1]), max(a_[1], b_[1])
        m = (vg >= lo_) & (vg <= hi_) & (hi_ > lo_)
        if m.any():
            uu = a_[0] + (b_[0] - a_[0]) * (vg[m] - a_[1]) / (b_[1] - a_[1])
            hw[m] = np.maximum(hw[m], uu - u_ax)
    # the midline front: PROFILE's leather from the dorsum behind its top round the tip to its bottom, densely, in the
    # camera's (v, t); per image height the front-most t (the front the camera sees)
    pr = np.asarray(PROFILE, float)
    pts = np.vstack([pr[-3:], pr[:15]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    ss = np.linspace(0.0, s[-1], 800)
    pd_ = np.column_stack([np.interp(ss, s, pts[:, 0]), np.interp(ss, s, pts[:, 1])])
    X = np.column_stack([np.zeros(len(pd_)), pd_[:, 1], npd - pd_[:, 0]])
    vv, tt = X @ u, X @ c
    tmid = np.full_like(vg, np.nan)
    for j, v_ in enumerate(vg):
        m = np.abs(vv - v_) < 0.4
        if m.any():
            tmid[j] = tt[m].max()
    ok = np.isfinite(tmid)
    tmid = np.interp(vg, vg[ok], tmid[ok])
    img = poly_sdf_image(full, full.min(0) - 20.0, full.max(0) + 20.0, 0.2)
    ala = to_leather(np.asarray(nw['ala'], float))
    opening = to_leather(np.asarray([nw['opening']], float))[0]
    # the profile's leather top (its dorsal edge on the midline, PROFILE[0]) in the camera: above it (higher in the
    # image) the traced leather lies on the bridge, where it rolls on without a rim (nose_relief)
    v_lt = float(np.array([0.0, pr[0, 1], npd - pr[0, 0]]) @ u)
    return dict(cam=(c, r, u), npd=npd, u_ax=u_ax, half=half, full=full, vg=vg, hw=hw, tmid=tmid, img=img, ala=ala,
                opening=opening, to_leather=to_leather, alpha=so['alpha'], psi=so['psi'], v_lt=v_lt)


# W2f: w08's nose leather traced on research/wolf_photos/w08_front_winter_prague_2015-02.jpg (brightened gridded crop at
# 6x, work/bestiary/wolf/scratch_w2f/out/w08_nose_bright.png: the leather's top under its sky highlight y 555, its widest
# x 558-635 at y 590, its bottom y 619), the image-right half from the top middle, mirrored about x 595.5; its nares'
# centres (575.7, 590.7) / (609.3, 590.7) (the W2e head builder's reading)
NOSE_W08 = dict(axis=595.5, half=((595.5, 555), (610, 556), (622, 560), (630, 568), (634, 578), (635, 590), (633, 600),
                                  (628, 608), (620, 614), (608, 618), (595.5, 619)),
                nares=((575.7, 590.7), (609.3, 590.7)))
NOSE_W12_NARES = ((2348.0, 1778.0), (2483.0, 1777.0))      # w12's openings' centres (the W2e head builder's reading)


def leather_material(spec):
    """W2h: the nose leather as a MATERIAL for the measures (nose_measures; work/bestiary/tests/w02_face.nose_read): the
    surface inside an outline in (x, q) mm and ahead of a back d (mm). canid.HEAD method 'skull': the traced
    rhinarium's outline (rhinarium_outline, the outline the sculpt lofts from), behind it STROKES leather pad_back (the
    leather's top rolling back over the bridge); else the W2c-W2g pad's (leather_pad). Returns (the outline's 2D
    distance image, its lo, its res, the outline (k, 2), the back)"""
    from . import canid
    if canid.HEAD.get('method') == 'cage':
        # W2j: the cage's own leather border (W2l: canid_nose.border_curve on the clay's frame; W2j-W2k w12's traced
        # outline through its solved camera), seen along d, both sides; the leather runs back to the border's top
        from . import canid_cage as CC
        Z, _ = CC.cage_cached(spec)
        lb = Z['loop_leather_border']
        outline = np.vstack([lb[:, [2, 1]], (lb[::-1] * np.array([1.0, 1.0, -1.0]))[1:-1][:, [2, 1]]])
        img, lo2, res = poly_sdf_image(outline, (-45.0, -40.0), (45.0, 60.0), 0.25)
        return img, lo2, res, outline, float(lb[:, 0].max() + 0.5)
    if canid.HEAD.get('method') == 'skull':
        outline, _ = rhinarium_outline(spec, STROKES_SKULL['rhinarium'])
        img, lo2, res = poly_sdf_image(outline, (-45.0, -40.0), (45.0, 60.0), 0.25)
        return img, lo2, res, outline, float(STROKES['leather']['pad_back'])
    lv = STROKES['leather']
    _, poly, (img, lo2, res) = leather_pad(np.zeros((1, 3)), lv)
    return img, lo2, res, poly, float(lv['pad_back'])


def nose_measures(phi, G, spec, members, tol=3.0):
    """W2f (the lead's call 2: "gate by overlay on w12 and w08: the leather's IoU, each nostril's aspect (w12 1.37) and
    position"): on a closed head's grid (palate frame mm) with its nares members (nares_members), in w12's and w08's
    solved cameras: the LEATHER as a material, the skin inside the pad's front outline ((|x|, q), with q held at the
    outline's top 1 mm under it so the leather runs on back over the bridge to the pad's back, as both photos show its top
    rolling there) or formed by the alar lobes, facing the camera, rasterised in the photo's px against the traced
    leather (NOSE_W12 / NOSE_W08, mirrored): its IoU, width and height (mm at IO 80); each NOSTRIL's visible rim (the
    opening member's surface where it meets the skin) projected: width, height, aspect, its centre down the leather and
    the two apart over its width; beside the photo's own. Returns {pid: dict}"""
    import json as _json
    import os as _os
    from matplotlib.path import Path
    from PIL import Image, ImageDraw
    from skimage.measure import marching_cubes
    from . import canid
    lo = np.asarray(G.lo, float)
    sub = np.asarray(phi[:int((40.0 - lo[0]) / G.h)], np.float32)
    V, F, _, _ = marching_cubes(sub, 0.0, spacing=(G.h,) * 3)
    V = V + lo
    gr = np.gradient(sub, G.h)
    iv = np.clip(np.round((V - lo) / G.h).astype(int), 0, np.array(sub.shape) - 1)
    N = np.stack([g[iv[:, 0], iv[:, 1], iv[:, 2]] for g in gr], -1)
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    # W2h: the leather's material by leather_material (the skull method's traced rhinarium; its alae are the program's
    # analytic members, not the grid's lobes)
    img, lo2, r2, poly, back_ = leather_material(spec)
    q_top = float(poly[:, 1].max()) - 1.0
    lea = (sample2(img, lo2, r2, V[:, 2], np.minimum(V[:, 1], q_top)) <= 0.0) & (V[:, 0] < back_)
    if 'alar_lobes' in STROKES and canid.HEAD.get('method') not in ('skull', 'cage'):
        lob, _ = alar_lobes(V, phi, G, spec, STROKES['alar_lobes'])
        lea |= lob <= tol
    clay = clay_points(spec)
    out = {}
    lm08 = None
    for pid, nw, nar_ph in (('w12', NOSE_W12, NOSE_W12_NARES), ('w08', NOSE_W08, NOSE_W08['nares'])):
        if pid == 'w08':
            if lm08 is None:
                here = _os.path.dirname(_os.path.abspath(__file__))
                p = _os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work', 'data',
                                  'lm_w08.json')
                pt = _json.load(open(p))['points']
                lm08 = {k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}
            L = lm08
        else:
            L = FRONTS['w12']['landmarks']
        so = solve_front(dict(landmarks=L), clay)
        c, r, u = (np.asarray(a, float) for a in so['cam'])
        # image mm -> photo px: invert the eye similarity
        flip = np.array([1.0, -1.0])
        e = [np.array(project_front(so['cam'], *clay[k], clay['np_mm'])) for k in ('vis_R', 'vis_L')]
        Tf, _ = sim2(np.asarray(L['eye_R'], float) * flip, np.asarray(L['eye_L'], float) * flip, e[0], e[1])
        A0, A1 = Tf(np.array([[0.0, 0.0]]))[0], Tf(np.array([[1000.0, 0.0]]))[0]
        Tinv, _ = sim2(A0, A1, np.array([0.0, 0.0]), np.array([1000.0, 0.0]))
        to_px = lambda W: Tinv(W) * flip
        proj = lambda P: np.stack(project_front(so['cam'], P[:, 0], P[:, 1], P[:, 2], clay['np_mm']), -1)
        h = np.asarray(nw['half'], float)
        trace = np.vstack([h, (h * [-1.0, 1.0] + [2.0 * nw['axis'], 0.0])[-2:0:-1]])
        x0, y0 = trace.min(0) - 60.0
        x1, y1 = trace.max(0) + 60.0
        s4 = 4.0
        Wd, Hd = int((x1 - x0) * s4), int((y1 - y0) * s4)
        Vpx = to_px(proj(V))
        facing = np.stack([N[:, 2], N[:, 1], -N[:, 0]], -1) @ c > 0.05
        m = Image.new('L', (Wd, Hd), 0)
        dm = ImageDraw.Draw(m)
        for f_ in F[(lea & facing)[F].all(1)]:
            dm.polygon([((Vpx[i, 0] - x0) * s4, (Vpx[i, 1] - y0) * s4) for i in f_], fill=255)
        mc = np.asarray(m) > 0
        yy, xx = np.mgrid[0:Hd, 0:Wd]
        mt = Path((trace - [x0, y0]) * s4).contains_points(np.column_stack([xx.ravel(), yy.ravel()])).reshape(Hd, Wd)
        iou = float((mc & mt).sum() / max((mc | mt).sum(), 1))
        ys_, xs_ = np.nonzero(mc)
        top, bot = ys_.min() / s4 + y0, ys_.max() / s4 + y0
        wl, wr = xs_.min() / s4 + x0, xs_.max() / s4 + x0
        px_mm = float(np.linalg.norm(np.subtract(L['eye_L'], L['eye_R']))) / 80.0
        th = np.linspace(0, 2 * np.pi, 90)
        pp = np.linspace(0.05, np.pi - 0.05, 45)
        TH, PH = np.meshgrid(th, pp)
        rows = []
        for mm_ in members[0]:
            if mm_[0] == 'psweep':
                if mm_[7] is None:                       # W2i: a canal (no rim of its own) or a fissure's prism
                    continue
                rim = np.asarray(mm_[7], float)           # W2i: the traced loop on the skin (nostrils_traced)
            elif mm_[0] == 'ellipsoid':
                E = np.stack([np.sin(PH) * np.cos(TH), np.sin(PH) * np.sin(TH), np.cos(PH)], -1).reshape(-1, 3) * mm_[3]
                Pe = mm_[1] + E @ mm_[2]
                rim = Pe[np.abs(sample3(phi, G, Pe)) < 0.35]
            else:
                continue
            q_ = to_px(proj(rim))
            w_, h_ = np.ptp(q_[:, 0]) / px_mm, np.ptp(q_[:, 1]) / px_mm
            rows.append(dict(w=float(w_), h=float(h_), aspect=float(w_ / max(h_, 1e-6)),
                             down=float((q_[:, 1].mean() - top) / (bot - top)), x=float(q_[:, 0].mean()), rim=q_))
        ph_t, ph_b = trace[:, 1].min(), trace[:, 1].max()
        # each nostril's place against the photo's own opening (mm at IO 80; matched by side)
        nph = sorted([np.asarray(p_, float) for p_ in nar_ph], key=lambda p_: p_[0])
        rws = sorted(rows, key=lambda r_: r_['x'])
        for r_, p_ in zip(rws, nph):
            r_['off'] = float(np.hypot(r_['x'] - p_[0], r_['rim'][:, 1].mean() - p_[1]) / px_mm)
        out[pid] = dict(iou=iou, width=float((wr - wl) / px_mm), height=float((bot - top) / px_mm),
                        photo_width=float(np.ptp(trace[:, 0]) / px_mm), photo_height=float(np.ptp(trace[:, 1]) / px_mm),
                        nostrils=rows, apart=float(abs(rows[0]['x'] - rows[1]['x']) / (wr - wl)),
                        photo_down=float(np.mean([(p[1] - ph_t) / (ph_b - ph_t) for p in nar_ph])),
                        photo_apart=float(abs(nar_ph[1][0] - nar_ph[0][0]) / np.ptp(trace[:, 0])),
                        mask=(mc, x0, y0, s4), trace=trace, camera=(so['alpha'], so['psi']))
    return out


def front_outline_errors(phi, G, spec, pid, res=0.25, muzzle=False):
    """W2f (the lead's call 1): a front photo's traced outline (FRONTS[pid]) against the clay's silhouette in the
    photo's SOLVED camera (solve_front: the eyes on the clay's visible eyes, the planum on its nose): the closed head's
    zero set (marching cubes of phi, palate frame mm) projected and rasterised at `res` mm, its signed distance at every
    1 mm of each segment's skin line (the outline less its coat). Returns [(segment index, coat, tol, two-sided flag,
    skin points (n, 2) image mm, e (n,) mm: + where the photo's skin line lies OUTSIDE the clay)]"""
    from PIL import Image, ImageDraw
    from scipy import ndimage as nd
    from skimage.measure import marching_cubes
    clay = clay_points(spec)
    if pid in FRONTS and not muzzle:
        fr = FRONTS[pid]
        lms = fr['landmarks']
    else:
        # W2g (muzzle): the winter fronts' muzzle outlines (FRONT_MUZZLE), their landmarks from lm_<pid>.json (w12's are
        # FRONTS w12's, the same reading)
        import json as _json
        import os as _os
        here = _os.path.dirname(_os.path.abspath(__file__))
        pt = _json.load(open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work',
                                           'data', f'lm_{pid}.json')))['points']
        lms = {k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}
        fr = FRONT_MUZZLE[pid]
    so = solve_front(dict(landmarks=lms), clay)
    V, F, _, _ = marching_cubes(np.asarray(phi, np.float32), 0.0, spacing=(G.h,) * 3)
    V = V + np.asarray(G.lo, float)
    W = np.stack(project_front(so['cam'], V[:, 0], V[:, 1], V[:, 2], clay['np_mm']), -1)
    lo, hi = W.min(0) - 30.0, W.max(0) + 30.0
    nu, nv = (np.ceil((hi - lo) / res).astype(int) + 1)
    im = Image.new('L', (int(nu), int(nv)), 0)
    dr = ImageDraw.Draw(im)
    U = (W - lo) / res
    for f_ in F:
        dr.polygon([(U[i, 0], U[i, 1]) for i in f_], fill=255)
    m = (np.asarray(im) > 0).T
    sd = (nd.distance_transform_edt(~m) - nd.distance_transform_edt(m) + np.where(m, 0.5, -0.5)) * res
    interior = np.array(project_front(so['cam'], 130.0, 10.0, 0.0, clay['np_mm']))
    out = []
    for i, seg in enumerate(fr['outline']):
        img = so['to_img'](np.asarray(seg['points'], float))
        skin = offset_polyline(img, np.full(len(img), seg['coat_mm']), interior)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(skin, axis=0), axis=1))])
        t = np.arange(0.0, s[-1] + 1e-9, 1.0)
        sk = np.column_stack([np.interp(t, s, skin[:, 0]), np.interp(t, s, skin[:, 1])])
        e = nd.map_coordinates(sd, [(sk[:, 0] - lo[0]) / res, (sk[:, 1] - lo[1]) / res], order=1, mode='nearest')
        out.append((i, seg['coat_mm'], seg['tol_mm'], bool(seg.get('two_sided')), sk, e))
    return out, so


def eye_canthi_w08(curves, spec):
    """W2f (the lead's call 3: "the lid cant 15-19 deg, 22-25 mm canthus to canthus"): each lens fissure's canthi
    (canid_hull.sculpt's eye curves: the centre +- STROKES eye half[0] along u) in w08's solved camera (the near-level
    front): canthus to canthus (mm) and the lateral canthus over the interocular line (deg, + higher). curves: the closed
    head's ('eye_L_centre', 'eye_L_u', ... or the sculpt's dicts)"""
    import json as _json
    import os as _os
    here = _os.path.dirname(_os.path.abspath(__file__))
    pt = _json.load(open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work', 'data',
                                       'lm_w08.json')))['points']
    clay = clay_points(spec)
    so = solve_front(dict(landmarks={k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}), clay)
    proj = lambda P: np.stack(project_front(so['cam'], P[:, 0], P[:, 1], P[:, 2], clay['np_mm']), -1)
    E = proj(np.array([clay['vis_L'], clay['vis_R']], float))
    eye_line = E[0] - E[1]
    from . import canid
    # W2h: the skull method's fissure (sculpt_skull: the lens's half-length a along its rolled canthus axis)
    hl = STROKES_SKULL['eye']['a'] if canid.HEAD.get('method') == 'skull' else STROKES['eye']['half'][0]
    res = {}
    for side in ('L', 'R'):
        ce = curves.get(f'eye_{side}')
        cen = np.asarray(ce['centre'] if isinstance(ce, dict) else curves[f'eye_{side}_centre'], float)
        u = np.asarray(ce['u'] if isinstance(ce, dict) else curves[f'eye_{side}_u'], float)
        P3 = np.array([cen + hl * u, cen - hl * u])
        A = proj(P3)
        lat = int(np.argmax(np.abs(P3[:, 2])))
        v = A[lat] - A[1 - lat]
        od = eye_line if side == 'L' else -eye_line
        ang = float(np.degrees(np.arctan2(od[0] * v[1] - od[1] * v[0], od @ v)))
        res[side] = (float(np.linalg.norm(v)), ang if side == 'L' else -ang)
    return res


def on_skin_w12(phi, G, fr, img_pts):
    """W2f: image points of w12's solved camera (nose_frame's image mm) onto the skin of phi: each camera ray marched in
    from the camera side to its first crossing; returns the skin points (d, q, x) mm and phi's outward normals there"""
    c, r, u = fr['cam']
    npd = fr['npd']
    ts = np.arange(320.0, 0.0, -0.1)          # the depth toward the camera from the AO joint: the nose stands near 160
    out, nrm = [], []
    for a, b in np.asarray(img_pts, float):
        X = a * r[None] + b * u[None] + ts[:, None] * c[None]
        P = np.column_stack([npd - X[:, 2], X[:, 1], X[:, 0]])
        f = sample3(phi, G, P)
        j = int(np.argmax(f < 0))
        if f[j] >= 0 or j == 0:
            out.append(P[0] * np.nan)
            nrm.append(np.full(3, np.nan))
            continue
        w = f[j - 1] / (f[j - 1] - f[j])
        S = P[j - 1] + w * (P[j] - P[j - 1])
        e = 0.5
        g = np.array([sample3(phi, G, (S + e * k)[None])[0] - sample3(phi, G, (S - e * k)[None])[0]
                      for k in np.eye(3)])
        out.append(S)
        nrm.append(g / max(np.linalg.norm(g), 1e-9))
    return np.asarray(out), np.asarray(nrm)


def alar_lobes(P, phi, G, spec, al, fr=None):
    """W2f (the lead's call 2: "each nostril's comma and the thick rolled ALAR LOBE over its lateral part"): the alar
    lobes as rolls along the crest traced on w12 (NOSE_W12 ala, the pale rim of the C round each opening's top and
    lateral side), carried onto the leather's skin by w12's solved camera rays (on_skin_w12), each crest point's roll
    centre al['r'] - al['h'] under the skin along its normal (its top al['h'] proud), round cones between them tapering
    from al['r'] at the top to al['r_end'] at the lower lateral end; mirrored (evaluated at |x|). Field (mm) at P (n, 3);
    and the crest's skin points"""
    fr = nose_frame(spec) if fr is None else fr
    S, N = on_skin_w12(phi, G, fr, fr['ala'])
    ok = np.all(np.isfinite(S), axis=1)
    S, N = S[ok], N[ok]
    rr = np.linspace(al['r'], al.get('r_end', al['r']), len(S))
    C = S - (rr - al['h'])[:, None] * N
    if al.get('toward', 0.0):
        # the roll leaning over the opening: each centre moved al['toward'] mm toward the opening's skin centre, in the
        # skin's tangent plane (the lobe's medial edge overhangs the opening's lateral part: the comma)
        O = on_skin_w12(phi, G, fr, fr['opening'][None])[0][0]
        dv = O[None] - C
        dv -= np.sum(dv * N, axis=1, keepdims=True) * N
        C = C + al['toward'] * dv / np.maximum(np.linalg.norm(dv, axis=1, keepdims=True), 1e-9)
    Pm = np.column_stack([P[:, 0], P[:, 1], np.abs(P[:, 2])])
    f = np.full(len(P), np.inf)
    for a_, b_, ra, rb in zip(C[:-1], C[1:], rr[:-1], rr[1:]):
        f = np.minimum(f, sd_roundcone_np(Pm, a_, b_, ra, rb))
    return f, S


def sculpt(phi, G, spec, log=print):
    """the STROKES as displacements of the level set (phi - D: D > 0 raises the skin), the eye openings as smooth
    subtractions; within a band of 14 mm round the skin. Returns phi and the strokes' curves (palate frame mm)"""
    from . import canid
    st = STROKES

    def smooth01(t):
        t = np.clip(t, 0.0, 1.0)
        return t * t * (3 - 2 * t)

    def smin(a, b, k):
        h_ = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
        return b * (1 - h_) + a * h_ - k * h_ * (1 - h_)
    # ---- W2g (the lead's call 2): THE LIPS, THE WHISKER PADS AND THE CHIN as masses on the flowed skin (face_masses),
    # smooth-unioned before the leather sits on them
    if 'masses' in st:
        ms = st['masses']
        phi0 = phi
        phi = phi.copy()
        reg = np.zeros(G.n, bool)
        reg[:int((ms.get('d_max', 112.0) - G.lo[0]) / G.h)] = True
        reg &= phi0 < ms.get('reach', 22.0)
        im_ = np.nonzero(reg)
        Pm_ = np.column_stack([G.d[im_[0]], G.q[im_[1]], G.x[im_[2]]])
        phi[im_] = smin(phi[im_], face_masses(Pm_, phi0, G, ms), ms['k'])
    # ---- the nose leather PAD (leather_pad), smooth-unioned into the muzzle: the hull alone left a 29 mm cone (nothing
    # holds a broad nose once the profile's pins leave the leather to the sculpt)
    lv = st['leather']
    near_nose = np.zeros(G.n, bool)
    near_nose[:int((lv['pad_back'] + 6 - G.lo[0]) / G.h)] = True
    ii = np.nonzero(near_nose)
    Pn = np.column_stack([G.d[ii[0]], G.q[ii[1]], G.x[ii[2]]])
    pad, poly, (img, lo2, r2) = leather_pad(Pn, lv)
    phi = phi.copy()
    phi[ii] = smin(phi[ii], pad, lv['pad_k'])
    curves = {'leather_outline': poly}
    if 'alar_lobes' in st:
        # W2f (the lead's call 2): the alar lobes, rolls along the crest traced on w12, over each opening's lateral part
        al = st['alar_lobes']
        lob, crest = alar_lobes(Pn, phi, G, spec, al)
        phi[ii] = smin(phi[ii], lob, al['k'])
        curves['ala_crest'] = crest
    band = np.abs(phi) < 14.0
    if st['eye'].get('floor') in ('centre', 'sphere'):
        # W2g: the band reaches the whole eyeball (the skin over the upper globe stood more than 14 mm over it, so the
        # fissure's cut never reached the globe there: the W2f opening's upper half stayed shut, 11-13 mm long)
        Le_ = canid.landmarks_pqx(spec)
        e_ = np.asarray(Le_['eye_L'], float)
        ce_ = np.array([1000 * (canid.nose_p(spec) - e_[0]), 1000 * e_[1], 1000 * e_[2]])
        D_, Q_, X_ = G.mesh()
        rr_ = 1000.0 * spec['eye']['ball_r'] + st['eye'].get('band_reach', 16.0)
        for sx_ in (1.0, -1.0):
            band |= ((D_ - ce_[0]) ** 2 + (Q_ - ce_[1]) ** 2 + (X_ - sx_ * ce_[2]) ** 2) < rr_ * rr_
        del D_, Q_, X_
    idx = np.nonzero(band)
    P = np.column_stack([G.d[idx[0]], G.q[idx[1]], G.x[idx[2]]])
    D = np.zeros(len(P), np.float32)
    s2 = sample2(img, lo2, r2, P[:, 2], P[:, 1])
    fade = 1.0 - smooth01((P[:, 0] - lv['d_full']) / (lv['d_end'] - lv['d_full']))
    D += (lv['dome'] * smooth01(-s2 / lv['ramp']) ** 0.7 * fade).astype(np.float32)
    # ---- the philtrum: one median groove down the leather's lower half and the upper lip to the lip margin
    ph = st['philtrum']
    wq = smooth01((P[:, 1] - ph['q_bot']) / 2.0) * (1.0 - smooth01((P[:, 1] - ph['q_top']) / 2.5))
    wd = 1.0 - smooth01((P[:, 0] - ph['d_end'] + 3.0) / 3.0)
    D -= (ph['depth'] * np.exp(-P[:, 2] ** 2 / (2 * ph['sigma'] ** 2)) * wq * wd).astype(np.float32)
    # ---- W2d head: THE ALAE, each a rounded lobe on the leather over the naris's lateral side (w12, w06: the wing the
    # alar slit separates from the opening; the openings and the slits are the program's analytic members, canid HEAD
    # nares), a smooth bump centred on the leather's front skin at (q, |x|), its half-widths along d, q, x
    if 'alae' in st and 'alar_lobes' not in st:
        al = st['alae']
        for sx in (1.0, -1.0):
            c0 = surface_along(phi, G, np.array([[20.0, al['q'], sx * al['x']]]), np.array([[-1.0, 0.0, 0.0]]),
                               reach=34.0)[0]
            r2_ = ((P[:, 0] - c0[0] - al['sink']) ** 2 / al['sd'] ** 2 + (P[:, 1] - c0[1]) ** 2 / al['sq'] ** 2
                   + (P[:, 2] - c0[2]) ** 2 / al['sx'] ** 2)
            D += (al['height'] * np.exp(-0.5 * r2_)).astype(np.float32)
            curves[f'ala_{"L" if sx > 0 else "R"}'] = c0[None]
    # ---- W2d head: THE CHIN softened: the chin's skin-depth ball (constraint_balls: the skin >= 6.5 mm ahead of the
    # infradentale) printed as a round knob under the mouth line from the front; the wet front r03 shows the lower lip
    # and the chin as one rounded taper under the leather. A ring round the knob's axis (along d at (q, x 0), elliptic
    # in (q, x), radius r0, width w) lifts its flanks so it blends into the chin; its front (the depth gate) is not cut
    if 'chin' in st:
        ch_ = st['chin']
        rr_ = np.sqrt(((P[:, 1] - ch_['q']) / ch_['aq']) ** 2 + (P[:, 2] / ch_['ax']) ** 2)
        wd_ = 1.0 - smooth01((P[:, 0] - ch_['d_end']) / 6.0)
        D += (ch_['height'] * np.exp(-((rr_ - ch_['r0']) / ch_['w']) ** 2) * wd_).astype(np.float32)
    # ---- the mouth line: the upper lip's margin on the skin (LIP_LINE's d, q; the skin's |x| there), round the front
    # midline under the nose; a groove with the upper lip rolled over it and the lower lip tucked under
    ll = np.asarray(LIP_LINE, float)
    mo = st['mouth']
    dd = np.arange(ll[0, 0], ll[-1, 0] + mo['tail'] + 0.1, 1.0)
    qq = np.interp(dd, ll[:, 0], ll[:, 1], right=ll[-1, 1] + 0.15 * (dd[-1] - ll[-1, 0]))
    xs = surface_x(phi, G, dd, qq)
    ok = np.isfinite(xs)
    dd, qq, xs = dd[ok], qq[ok], xs[ok] - 0.5
    front = np.array([[ll[0, 0] - 1.5, ll[0, 1] - 0.3, 0.0]])
    left = np.column_stack([dd, qq, xs])
    lip = np.vstack([left[::-1] * [1, 1, -1], front, left])
    curves['mouth_line'] = lip
    r, s = curve_dist(P, lip)
    ends = smooth01(np.minimum(s, 1 - s) * len(lip) / mo['tail'])        # fades over the tails behind the commissures
    q_line = np.interp(P[:, 0], dd, qq, left=ll[0, 1], right=qq[-1])
    t = P[:, 1] - q_line
    near = np.exp(-r ** 2 / (2 * (2.5 * mo['step_w']) ** 2))
    D += (ends * (-mo['depth'] * np.exp(-r ** 2 / (2 * mo['sigma'] ** 2))
                  + near * (mo['step_up'] * np.exp(-((t - mo['step_w']) / mo['step_w']) ** 2)
                            + mo['step_dn'] * np.exp(-((t + mo['step_w']) / mo['step_w']) ** 2)))).astype(np.float32)
    # ---- the eyes: the orbit's soft hollow, the brow over it, the almond opening (the photos' canthi: the lateral
    # canthus behind and below the medial one; with the head's pitch the level front's 17 deg cant), its lid rims
    L = canid.landmarks_pqx(spec)
    NP = canid.nose_p(spec)
    ey = st['eye']
    orb = st['orbit']
    e0 = np.asarray(L['eye_L'], float)
    o0 = np.asarray(L['eye_dir_L'], float)
    vis0 = np.array([1000 * (NP - e0[0]), 1000 * e0[1], 1000 * e0[2]]) + 1000 * spec['eye']['ball_r'] * \
        np.array([-o0[0], o0[1], o0[2]])
    # THE ORBIT'S HOLLOW: the skin at the visible eye's height stood x_s - cornea mm proud of the cornea (the skull
    # sections run straight from the brow to the arch past the orbit): an elliptical hollow brings it to the cornea
    # plus the lids, so the eye sits nearly flush in them
    x_s = float(surface_x(phi, G, np.array([vis0[0]]), np.array([vis0[1]]))[0])
    depth_orb = max(0.0, x_s - (vis0[2] + orb['lids']))
    for sx in (1.0, -1.0):
        gd = np.exp(-((P[:, 0] - vis0[0]) ** 2 / (2 * orb['sigma_d'] ** 2)
                      + (P[:, 1] - vis0[1]) ** 2 / (2 * orb['sigma_q'] ** 2)))
        D -= (depth_orb * gd * smooth01((sx * P[:, 2] - orb['x_min']) / 6.0)).astype(np.float32)
    phi_h = phi.copy()
    phi_h[idx] = phi[idx] - D                       # the hollow in place: the eye's skin point is found on it
    for sx in (1.0, -1.0):
        vis = vis0 * np.array([1.0, 1.0, sx])
        o = np.array([-o0[0], o0[1], sx * o0[2]])
        S_eye = surface_along(phi_h, G, vis[None] - 6.0 * o[None], o[None])[0]
        # the opening: a cavity along the optical axis from the skin down to the cornea (the visible eye point), its
        # section an almond whose long axis follows the canthi (made normal to the axis); its centre half-way, its
        # depth half-axis reaching 1 mm past the cornea (an almond in the skin's tangent plane stopped short of the
        # globe: a dark hole)
        t_c = float((S_eye - vis) @ o)
        cm, cl = np.asarray(CANTHI['medial'], float), np.asarray(CANTHI['lateral'], float)
        # W2e head: cant_q lifts the lateral canthus (mm) over the profiles' mean (the level front w08's 17 deg cant)
        u = np.array([cl[0] - cm[0], cl[1] - cm[1] + ey.get('cant_q', 0.0), sx * ey.get('canthus_dx', 12.0)])
        u = u - (u @ o) * o
        u /= np.linalg.norm(u)
        v = np.cross(o, u)
        Dl = P - S_eye
        ru = Dl @ u
        rv = Dl @ v
        ro = Dl @ o
        if ey.get('lens'):
            # W2d head: the almond as a LENS (two arcs meeting in pointed canthi: the lid margins of w12 / w08), half
            # length half[0] along the canthi, half height half[1]: arcs of radius R centred +-c across
            a_, b_ = ey['half'][0], ey['half'][1]
            R_ = (a_ * a_ + b_ * b_) / (2.0 * b_)
            c_ = R_ - b_
            rho = np.maximum(np.hypot(ru, rv - c_), np.hypot(ru, rv + c_)) / R_
        else:
            rho = np.sqrt((ru / ey['half'][0]) ** 2 + (rv / ey['half'][1]) ** 2)
        D += (ey['lid'] * np.exp(-((rho - ey['lid_at']) / ey['lid_w']) ** 2) * (np.abs(ro) < 6.0)).astype(np.float32)
        curves[f'eye_{"L" if sx > 0 else "R"}'] = dict(centre=S_eye, u=u, v=v, o=o, cornea=vis,
                                                         depth=np.array([t_c]))
        # the brow: the supraorbital margin's skin over this eye
        bp = np.array([[p_[0], p_[1], sx * p_[2]] for p_ in st['brow']['points']])
        bo = np.array([0.0, 0.55, sx * 0.83])
        bs = surface_along(phi, G, bp - 8.0 * bo, np.tile(bo / np.linalg.norm(bo), (len(bp), 1)))
        rb, sb = curve_dist(P, bs)
        endb = smooth01(np.minimum(sb, 1 - sb) * 4.0)
        D += (st['brow']['height'] * np.exp(-rb ** 2 / (2 * st['brow']['sigma'] ** 2)) * endb).astype(np.float32)
        curves[f'brow_{"L" if sx > 0 else "R"}'] = bs
    out = phi.copy()
    out[idx] = phi[idx] - D
    # the eye openings: smooth subtraction of the almonds (after the displacements: their walls stay clean). W2g (the lead's
    # call 4: "the lids WRAP the 24 mm globe with the corners near its equator (no flat-floored cut 3 mm past the cornea),
    # the opening an almond with the lateral canthus higher"): STROKES eye floor 'sphere' (below)
    for nm in ('eye_L', 'eye_R'):
        c = curves[nm]
        t_c = float(c['depth'][0])
        cen = c['centre'] - 0.5 * (t_c + 1.0) * c['o']
        half_e = (ey['half'][0], ey['half'][1], max(ey['half'][2], 0.5 * (t_c + 1.0) + 2.0))
        if ey.get('lens'):
            # the lens prism along the optical axis from the skin to 1 mm past the cornea (W2d head)
            a_, b_ = ey['half'][0], ey['half'][1]
            R_ = (a_ * a_ + b_ * b_) / (2.0 * b_)
            c_ = R_ - b_
            Dl = P - c['centre']
            uu_, vv_, oo_ = (np.asarray(c[k], float) for k in ('u', 'v', 'o'))
            if ey.get('lift'):
                # W2g (the lead's call 4): the prism's axis turned UP about the canthus axis by lift deg (the lid opening
                # faces the front cameras, 38-51 deg over the palate, which see the whole almond)
                lt_ = np.radians(ey['lift'])
                vd_ = vv_ * (1.0 if vv_[1] >= 0 else -1.0)
                oo_ = np.cos(lt_) * oo_ + np.sin(lt_) * vd_
                vv_ = np.cross(oo_, uu_)
            ru, rv, ro = Dl @ uu_, Dl @ vv_, Dl @ oo_
            lens = np.maximum(np.hypot(ru, rv - c_), np.hypot(ru, rv + c_)) - R_
            hd = 0.5 * (t_c + 1.0) + 2.0
            E = np.maximum(lens, np.abs(ro + 0.5 * (t_c + 1.0)) - hd)
            if ey.get('floor') in ('centre', 'sphere'):
                # W2g (the lead's call 4: "no flat-floored cut 3 mm past the cornea"): the prism from 2 mm outside the
                # skin down to the EYEBALL'S CENTRE plane (the globe fills everything behind its surface, so the opening
                # shows the globe over the whole almond, out to the corners at its equator; W2f's floor 3 mm past the
                # cornea showed it only within 7.9 mm of its centre); 'sphere': only what lies outside the globe (0.4 mm
                # into it) and in front of its centre plane, so past the globe's outline the corners stay shallow slots
                Rg_ = 1000.0 * spec['eye']['ball_r']
                lo_o, hi_o = -(t_c + Rg_), 2.0
                E = np.maximum(lens, np.abs(ro - 0.5 * (lo_o + hi_o)) - 0.5 * (hi_o - lo_o))
                if ey.get('floor') == 'sphere':
                    sxe = 1.0 if nm == 'eye_L' else -1.0
                    e_ = np.asarray(L['eye_L'], float)
                    cb_ = np.array([1000 * (NP - e_[0]), 1000 * e_[1], sxe * 1000 * e_[2]])
                    Wb_ = P - cb_
                    if ey.get('prism_axis'):
                        # the prism THROUGH THE BALL'S CENTRE along (elevation over the palate axis, splay out) deg: the
                        # almond centred on the globe as the front cameras see it (from S_eye along the lifted optical
                        # axis it stood medial of the globe there: half the almond a pocket past its outline)
                        el_, sp_ = (np.radians(a__) for a__ in ey['prism_axis'])
                        oo_ = np.array([-np.cos(el_) * np.cos(sp_), np.sin(el_), sxe * np.cos(el_) * np.sin(sp_)])
                        uu_ = uu_ - (uu_ @ oo_) * oo_
                        uu_ /= np.linalg.norm(uu_)
                        vv_ = np.cross(oo_, uu_)
                        vv_ *= 1.0 if vv_[1] >= 0 else -1.0
                        # the almond rolled in its plane (deg, + lifting the lateral end): the level front w08's 17 deg
                        rl_ = np.radians(ey.get('roll', 0.0)) * (1.0 if (uu_[2] * sxe) >= 0 else -1.0)
                        uu_, vv_ = np.cos(rl_) * uu_ + np.sin(rl_) * vv_, -np.sin(rl_) * uu_ + np.cos(rl_) * vv_
                        ru, rv = Wb_ @ uu_, Wb_ @ vv_
                        lens = np.maximum(np.hypot(ru, rv - c_), np.hypot(ru, rv + c_)) - R_
                    # ... and within the globe's outline along the prism's axis (past it the cut opened a box-walled
                    # pocket beside the globe at the medial canthus, seen in profile: scratch_w2g/out/views_eyes_e15)
                    rad_ = np.hypot(Wb_ @ uu_, Wb_ @ vv_) if ey.get('prism_axis') else np.zeros(len(P))
                    E = np.maximum.reduce([lens, Rg_ - 0.4 - np.linalg.norm(Wb_, axis=1), -(Wb_ @ oo_),
                                           (Wb_ @ oo_) - (Rg_ + t_c + ey.get('far', 12.0)),
                                           rad_ - (Rg_ - ey.get('rim_in', 0.3))])
        else:
            E = ellipsoid_sd(P, cen, np.stack([c['u'], c['v'], c['o']]), half_e)
        cur = out[idx]
        k = ey['k']
        h_ = np.clip(0.5 - 0.5 * (-E - cur) / k, 0.0, 1.0)
        out[idx] = (-E) * (1 - h_) + cur * h_ + k * h_ * (1 - h_)          # smax(cur, -E, k)
    # ---- the nares (W2c check, STROKES nares): each opening an ellipsoid sunk 1 mm behind the leather's front face at
    # (|x|, q), its inward axis into the head tipped up and medial, the alar slit a capsule out and back from its
    # lateral top; both smooth-subtracted
    na = st.get('nares')
    for sx in ((1.0, -1.0) if na else ()):
        P0 = np.array([[20.0, na['q'], sx * na['x']]])
        S_n = surface_along(out, G, P0, np.array([[-1.0, 0.0, 0.0]]), reach=34.0)[0]       # the front face, from inside
        o = np.array([1.0, na['tilt_up'], -sx * na['tilt_in']])
        o /= np.linalg.norm(o)
        u = np.array([0.0, 0.0, sx]) - o[2] * sx * o
        u /= np.linalg.norm(u)
        v = np.cross(o, u)
        v *= np.sign(v[1]) if v[1] != 0 else 1.0
        E = ellipsoid_sd(P, S_n + 1.0 * o, np.stack([u, v, o]), na['half'])
        cur = out[idx]
        h_ = np.clip(0.5 - 0.5 * (-E - cur) / na['k'], 0.0, 1.0)
        out[idx] = (-E) * (1 - h_) + cur * h_ + na['k'] * h_ * (1 - h_)
        a_ = np.array([S_n[0] + na['slit_a'][0], na['q'] + na['slit_a'][1], sx * na['slit_a'][2]])
        b_ = np.array([S_n[0] + na['slit_b'][0], na['q'] + na['slit_b'][1], sx * na['slit_b'][2]])
        ba = b_ - a_
        t_ = np.clip(((P - a_) @ ba) / float(ba @ ba), 0.0, 1.0)
        Cs = np.linalg.norm(P - a_ - t_[:, None] * ba, axis=1) - na['slit_r']
        cur = out[idx]
        k2 = 0.6
        h_ = np.clip(0.5 - 0.5 * (-Cs - cur) / k2, 0.0, 1.0)
        out[idx] = (-Cs) * (1 - h_) + cur * h_ + k2 * h_ * (1 - h_)
        curves[f'naris_{"L" if sx > 0 else "R"}'] = np.vstack([S_n, a_, b_])
    # the globes seated in the openings (canid's eye centres, SPEC eye.ball_r): the eyeball part replaces them later;
    # the clay shows the lids round a convex eye instead of a hole
    for sx in (1.0, -1.0):
        e = np.asarray(L['eye_L'], float)
        c = np.array([1000 * (NP - e[0]), 1000 * e[1], sx * 1000 * e[2]])
        sph = np.linalg.norm(P - c, axis=1) - 1000 * spec['eye']['ball_r']
        out[idx] = smin(out[idx], sph, ey['globe_k'])
    log(f'[hull] sculpt: {len(P):,} band voxels; the leather pad and its dome, the philtrum, the mouth line '
        f'({len(lip)} points, the commissure at d {dd[-1] - mo["tail"]:.0f}), the orbits, the brows, the eye openings '
        f'(the orbit\'s hollow {depth_orb:.1f} mm deep; skin to cornea along the optical axis then '
        f'{float(curves["eye_L"]["depth"][0]):.1f} mm), the globes')
    return out, curves


# ============================================================================================ the W2h sculpt
# W2h (the lead's calls 1-3): the head's base is the SKIN OVER THE SKULL (canid_skin.py; canid.HEAD method 'skull'), the
# furred silhouettes outer limits only; on it the features, each measured:
#   rhinarium  the nose leather as a RELIEF TRACED FROM w12 (NOSE_W12 through w12's solved camera, nose_frame): every
#              point inside the traced outline as that camera sees it (scaled about the leather's axis by `scale`, the
#              photos' ratio: w12 0.604 of the eye spacing, the fronts' 0.509-0.604, median 0.572; x 0.97 -> 0.586) and
#              behind its FRONT, the profile photos' leather (PROFILE's nose: nose_frame tmid) falling back only `flat` mm
#              toward the outline's edge (rho^flat_exp: a flattened front face, not a dome), cut at d `back`, its edge
#              rounded `round` mm, smooth-unioned into the skin with k `k` mm only (a defined BORDER where the leather meets
#              the haired skin; the W2c-W2g pad blended 7 mm and read as a button)
#   mouth      the mouth line (LIP_LINE): a groove with the upper lip rolled over the lower (the thin margin along the jaw;
#              no lip masses)
#   eye        the lids are the skin over the globe (canid_skin DEPTHS lid); the FISSURE a lens (half-length a, half-height
#              b) along the canthi (CANTHI and canthus_dx, made normal to the prism axis, rolled `roll` deg so the lateral
#              canthus rises) cut through at most `cut` mm of skin (the lids' thickness and a little: past the globe's
#              outline the canthi are shallow folds, never a tunnel, so no pocket) in front of the globe's centre plane,
#              then the globe re-added (SPEC eye.ball_r round canid's eye centre)
STROKES_SKULL = dict(
    # the NOSE a loft (the skull's skin has no nose ahead of the nasal tips, d ~30: the cartilages): the traced outline
    # to loft[0], morphing (its 2D field into the skin's own section) to loft[1]; an extrusion stood out as a box. The
    # BORDER a groove `border` (depth, sigma mm) along the outline on the leather's front and sides
    # the front a PILLOW: flat over the middle, rolling back `flat` mm to the outline's edge as rho^flat_exp (the traced
    # outline is the leather's widest section seen from the front, not its front face; at 3 mm it stood as a flat box)
    # W2h h6: x 1.04 (h5 0.97: the leather read 0.512 of the eye spacing wide in w12's camera, the photos 0.57-0.60; the
    # pillow's fall-back and the loft narrow it from its outline's 0.586), the fall-back 7.5 (9), the outline held to
    # d 6 before the loft (3)
    # W2h h7: on the nasal cartilages' front (canid_skin DEEP nose) x 1.0, the fall-back 6, the loft 3 -> 30
    rhinarium=dict(scale=1.0, flat=6.0, flat_exp=2.2, round=3.0, k=3.0, loft=(3.0, 30.0), border=(0.5, 0.7),
                   loft_bot=(-6.0, 8.0, 10.0)),
    mouth=dict(depth=2.0, sigma=1.3, step_up=0.6, step_dn=-0.8, step_w=3.0, tail=6.0),
    # W2h h6: the LIDS seated on the globe (lid: thickness, reach mm) and the cut through them to it (cut, back mm: the
    # lens prism `back` mm behind the globe's centre plane); a 16.5 (h5 14.5: the fissure read 0.295 of the eye spacing,
    # the photos' 0.348)
    # h7: a 17.5, the lids 1.8 thick, the prism 5 mm behind the centre plane, cut 2.8 (h6 16.5 / 2.2 / 3 / 3.0: the
    # fissure 0.310 of the eye spacing, the ball over 0.77 of it)
    # h8: the prism 8 mm behind the centre plane (h7 5: the front cameras look 27 deg off the eye's axis, so the globe's
    # far silhouette lay behind the prism's back and the lid hid it)
    # h10: b 6.6 (5.6: the lens's ends left the globe's edge under the lids, the eyeball over 0.77 of the fissure)
    # W2i (the lead's call 3): the lids a lid[0] mm shell on the globe (ext: its ellipsoid's extra width across the
    # axis, 0: a sphere) seated seat[0] mm past the traced fissure (faded over seat[1]), out past the lid's sphere along
    # the axis flaring `flare` mm per mm and fading (full to out[0] mm, gone by out[0] + out[1]) within `reach` mm of the
    # globe: a crater up into the cheek where the face stands before the eye (h8's channel ended at its slice box: a
    # ledge); the analytic fissure (eye_members): the traced polygon's corners rounded fis_rho, the prism from `back` mm
    # along the axis (h3-h7 began it at R - 3: the eyeball showed over 17.5 mm of its 24), the cutter's band from band[0]
    # mm inside the globe to band[1] mm outside the lid held within the globe's outline plus `clip`, the cut's smooth
    # subtraction cut_kg (the margins' roll), the canthal grooves (half width, depth) groove[0] -> groove[1] groove_end of
    # the way to the photos' canthi, the globe re-added with globe_k (mm). a, b, roll, canthus_dx, cant_q: W2h's lens,
    # now only the printed lid curve (eye_canthi_w08); axis: the eye's axis (elevation, splay deg), the prism's direction
    # (W2m: lid[0] 0.6 mm, the lids on the globe (canid_cage EYE lid); W2i-W2l 1.8)
    eye=dict(a=18.0, b=6.6, axis=(19.0, 40.0), roll=-14.0, canthus_dx=21.0, cant_q=3.2, globe_k=0.3,
             lid=(0.6, 5.0), ext=0.0, seat=(2.5, 3.0), fis_rho=0.3, band=(0.4, 0.8), cut_kg=0.6, back=-3.0,
             clip=-0.3, groove=((1.1, 1.1), (0.6, 0.6)), groove_end=0.85, flare=0.6, out=(1.5, 9.0), reach=20.0),
    # (W2l, the lead: "check the eye's axis and seat against measured canid orbits and the photos": the axis 19 deg up /
    # 40 out (W2h-W2k 24 / 18). The traced fissure's OWN best-fit plane (canid_cage.eye_chart's fis3 on the lid's
    # sphere) faces 9 deg down / 29 out in the old chart, 4-6 up / 34-35 out once the chart turns toward it; MWNH 358's
    # orbit rim plane faces 26 up / 51 out; the canthi run 21 mm back for 21 out (45 deg in plan). At 18 out the axis
    # stood 35 deg off the lids' own plane and the medial face rose across it: the rim's medial spokes, cast along the
    # forward axis, landed high on the bridge's side and the quads between folded (the vertical crease from the inner
    # corner, the W2k fresh eyes' quads 503 / 561 / 620). At 19 / 40 the plane is 16 deg off it and the medial side
    # slopes into the corner (work/bestiary/wolf/check_w2l_head probes a1-a3, b1, c1-c2, s1, d1, g1; fissure_plane.py).
    # 14 up (s1) cleared the crease wholly but hid the fissure from the photos' high cameras (w12 0.27 / 0.28 of the
    # eye spacing against its photo's 0.38 / 0.41; 19 up: 0.33); 24 up (d1) left a thin line at the medial corner. The
    # lower lid's medial end runs nearly radially in the turned chart: canid_cage EYE star keeps the fissure star-shaped)
    # behind the ears the flowed head (the visual hull's: the ear canal, the parotid, the neck's attachments, which the
    # skull's bone does not carry; to d 190 the two agree within 3-6 mm, behind d 205 the skin follows the occiput to the
    # inion, 20 mm narrower at d 240): the skin over the skull interpolated into it from blend[0] to blend[1] (d mm)
    blend=(192.0, 228.0),
)


def rhinarium_outline(spec, rv, fr=None):
    """W2h: w12's traced leather outline carried onto the clay: each traced point (image mm in w12's solved camera,
    nose_frame full) to (|x|, q) where its camera ray meets the profile photos' leather front at its image height
    (nose_frame tmid: the depth toward the camera; q = v cos(alpha) + t sin(alpha)), |x| scaled about the leather's axis by
    rv scale. Returns the closed outline (k, 2) (x, q) mm and nose_frame's result"""
    fr = nose_frame(spec) if fr is None else fr
    c, r, u = fr['cam']
    full = np.asarray(fr['full'], float)
    tm = np.interp(full[:, 1], fr['vg'], fr['tmid'])
    # (x, q, p) = U r + V u + T c for the ray at (U, V) at depth T
    X = full[:, :1] * r[None] + full[:, 1:2] * u[None] + tm[:, None] * c[None]
    xs = (full[:, 0] - fr['u_ax']) * rv['scale']
    return np.column_stack([xs, X[:, 1]]), fr


def rhinarium(P, rv, outline, skin):
    """W2h: the nose's field (mm) at P (n, 3) (d, q, x) mm (STROKES_SKULL rhinarium; the comment above it): the traced
    outline's 2D field (rhinarium_outline) to rv loft[0], morphing into `skin` (the skin's own field at P, mm) by
    loft[1]; behind the profile photos' leather front (PROFILE's nose, d as a function of q) falling back `flat` mm
    toward the outline's edge (rho^flat_exp of its inradius). Returns the field and the outline's 2D field. W2h h6: the
    morph runs into the 3D skin itself (h5 morphed into the skin's section at loft[1] extruded forward: a seam stood
    across the muzzle's side at loft[1])"""
    img, lo2, res = poly_sdf_image(outline, (-45.0, -40.0), (45.0, 60.0), 0.25)
    s2 = sample2(img, lo2, res, P[:, 2], P[:, 1])
    nose = np.asarray(PROFILE, float)[:15]          # the leather's profile from its top over the tip to its bottom
    order = np.argsort(nose[:, 1])
    d_front = np.interp(P[:, 1], nose[order, 1], nose[order, 0])
    rin = -float(img.min())                         # the outline's inradius (mm)
    rho = np.clip(1.0 + s2 / max(rin, 1.0), 0.0, 1.0)
    front = (d_front + rv['flat'] * rho ** rv['flat_exp']) - P[:, 0]
    a, b = rv['loft']
    # W2i (the lead's call 2: "the leather's underside flows into the upper lip through the philtrum (no box corners)"):
    # the morph into the skin ends at loft_bot[2] mm at the leather's bottom (q <= loft_bot[0]), at loft[1] from loft_bot[1]
    # up: the underside slopes back into the lip within a few mm instead of standing as a shelf the outline's width
    if 'loft_bot' in rv:
        q0, q1, b_bot = rv['loft_bot']
        wq = np.clip((P[:, 1] - q0) / (q1 - q0), 0.0, 1.0)
        b = b_bot + (b - b_bot) * wq * wq * (3.0 - 2.0 * wq)
    t = np.clip((P[:, 0] - a) / (b - a), 0.0, 1.0)
    t = t * t * (3.0 - 2.0 * t)
    sec = (1.0 - t) * s2 + t * skin
    smax = lambda a_, b_, k: -_smin(-a_, -b_, k)
    return smax(sec, front, rv['round']), s2


def eye_frame(spec, side):
    """W2h: the fissure's frame for one eye (STROKES_SKULL eye): the globe's centre (mm), the prism axis oo (outward),
    the canthus axis uu (rolled), the across axis vv (up), the lens's R and c"""
    from . import canid
    ey = STROKES_SKULL['eye']
    L = canid.landmarks_pqx(spec)
    NP = canid.nose_p(spec)
    e = np.asarray(L['eye_L'], float)
    sx = 1.0 if side == 'L' else -1.0
    ce = np.array([1000 * (NP - e[0]), 1000 * e[1], sx * 1000 * e[2]])
    el, sp = (np.radians(a) for a in ey['axis'])
    oo = np.array([-np.cos(el) * np.cos(sp), np.sin(el), sx * np.cos(el) * np.sin(sp)])
    cm, cl = np.asarray(CANTHI['medial'], float), np.asarray(CANTHI['lateral'], float)
    uu = np.array([cl[0] - cm[0], cl[1] - cm[1] + ey['cant_q'], sx * ey['canthus_dx']])
    uu = uu - (uu @ oo) * oo
    uu /= np.linalg.norm(uu)
    vv = np.cross(oo, uu)
    vv *= 1.0 if vv[1] >= 0 else -1.0
    rl = np.radians(ey['roll']) * (1.0 if uu[2] * sx >= 0 else -1.0)
    uu, vv = np.cos(rl) * uu + np.sin(rl) * vv, -np.sin(rl) * uu + np.cos(rl) * vv
    a_, b_ = ey['a'], ey['b']
    R_ = (a_ * a_ + b_ * b_) / (2.0 * b_)
    return dict(centre=ce, oo=oo, uu=uu, vv=vv, R=R_, c=R_ - b_, a=a_, b=b_, r_globe=1000.0 * spec['eye']['ball_r'])


def fissure_sd(P, ef):
    """the fissure lens prism's signed distance (in its plane) at P: negative inside the almond"""
    W = P - ef['centre']
    ru, rv = W @ ef['uu'], W @ ef['vv']
    return np.maximum(np.hypot(ru, rv - ef['c']), np.hypot(ru, rv + ef['c'])) - ef['R']


def lid_half(r_globe, grow):
    """W2i: the lid surface's ellipsoid half-axes (lateral e1, dorsal ed, along the axis oo) mm, grown by `grow`: the
    globe's radius plus the lids' thickness along the axis, `ext` mm wider across it (STROKES_SKULL eye)"""
    ey = STROKES_SKULL['eye']
    a = r_globe + ey['lid'][0] + grow
    return np.array([a + ey['ext'], a + ey['ext'], a])


def lid_frame(spec, side):
    """W2i: one eye's frame for the lids and the fissure: the globe's centre (mm), its axis oo (STROKES_SKULL eye axis),
    e1 the lateral direction made normal to oo, e2 = oo x e1, ed the dorsal one of +-e2, the globe's radius"""
    ef = eye_frame(spec, side)
    oo = ef['oo']
    sx = 1.0 if side == 'L' else -1.0
    e1 = np.array([0.0, 0.0, sx]) - sx * oo[2] * oo
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(oo, e1)
    ed = e2 if e2[1] >= 0 else -e2
    return dict(centre=ef['centre'], oo=oo, e1=e1, e2=e2, ed=ed, R=ef['r_globe'])


def traced_fissure(spec, n=36, clay=None, pin=True, face=None, loops3=False):
    """W2i (the lead's call 3): EYE_FISSURES carried through each photo's SOLVED camera (solve_front: the eyes on the
    clay's visible eyes, the planum on the photo's nose) onto the lid's sphere (the globe's radius plus STROKES_SKULL eye
    lid[0]; each ray's camera-side crossing, its nearest approach where it misses), seen along the eye's axis in its
    (lateral, dorsal) plane; each loop resampled canthus to canthus (the upper margin to the lateral canthus, the lower
    back), the four averaged (both eyes of w12 and w08; the right eyes mirrored by their own lateral axis). Returns the
    average (2 n, 2) mm (e1 lateral, ed dorsal; from the medial canthus over the top), and the per-photo loops.
    clay: the registration (clay_points' dict; W2n: eye_landmark passes its fixed point's iterates).
    pin (W2n): a ray that misses the sphere is pinned onto it (its nearest approach scaled back to the sphere: W2i-W2m,
    and eye_landmark's corners, which this ties to the globe); pin=False keeps the nearest approach itself, past the
    ball's outline, so each loop's corner end runs on along its rays to its canthus (canthi_on_rays' point) instead of
    along the ball's outline: the cage's pointed corners (canid_cage EYE pin).
    face (W2o, the lead's call 1: "carry the fissure's inner third and both canthi onto the face at the profile-rule
    points, in the cage only"): None, or the corner rule (canid_cage EYE face: dict(third=...)). Each loop's two canthi
    (its ends, index 0 and n) go to the PROFILE RULE on their own rays (canthi_on_rays 'profile': the ray's point whose
    (d, q) is nearest the head profiles' CANTHI), and every point between is carried along its OWN ray at a depth
    interpolated from the sphere rule's (the lid sphere's camera-side crossing, the nearest approach where the ray
    misses: each front camera's LIMB PLANE, where W2n's corners sat) toward its canthus's, by a smooth weight of the arc
    length from that canthus (1 at the canthus, 0 at face['third'] of the lid's length), never into the globe (where the
    ray meets the globe it stays at or in front of its crossing). So each loop still lands on its photo's tracing in that
    camera while its corner ends run onto the face: the medial canthus 8.3-10.4 mm TOWARD each front camera from its
    limb plane (in front of the ball, the inner third of both lids with it), the lateral one 7.5-11.2 mm AWAY from it
    (round the globe's side; on the ball the lateral end keeps the sphere's crossing). The registration does not use it
    (eye_landmark keeps the pinned sphere corners). With face, the averaged heights along the eye's axis (oo, the lid
    frame's) per point are returned as a third item.
    loops3 (W2q, with face): each photo eye's loop in 3D as well (palate mm, the right eyes mirrored onto the left), a
    fourth item {'<pid>_<side>': (2 n, 3)}: lid_follow turns each by its own photo's gaze before they are averaged"""
    import json as _json
    import os as _os
    clay = clay_points(spec) if clay is None else clay
    npd = clay['np_mm']
    lid = STROKES_SKULL['eye']['lid'][0]
    here = _os.path.dirname(_os.path.abspath(__file__))
    loops, out, hs, l3 = {}, [], [], {}
    sm01 = lambda x: np.clip(x, 0.0, 1.0) ** 2 * (3.0 - 2.0 * np.clip(x, 0.0, 1.0))  # noqa: E731
    for pid, sides in EYE_FISSURES.items():
        if pid in FRONTS:
            L = FRONTS[pid]['landmarks']
        else:
            pt = _json.load(open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work',
                                               'data', f'lm_{pid}.json')))['points']
            L = {k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}
        so = solve_front(dict(landmarks=L), clay)
        c, r, u = (np.asarray(a, float) for a in so['cam'])
        dir_ = np.array([-c[2], c[1], c[0]])                 # toward the camera, palate (d, q, x)
        for side, tr in sides.items():
            lf = lid_frame(spec, side)
            R_ = lf['R'] + lid
            halves, hh, halves3 = [], [], []
            for key in ('upper', 'lower'):
                pts = np.asarray(tr[key], float)
                s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
                t = np.linspace(0.0, s[-1], n + 1)
                pts = np.column_stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])])
                W = so['to_img'](pts)
                P3 = []
                if face is not None:
                    # W2o: each point's ray (o: its point on the image plane, relative to the globe's centre), the sphere
                    # rule's depth tt_s along dir_, the globe's own camera-side crossing tt_g (-inf where the ray misses
                    # the globe), the canthi's profile-rule depths at this half's two ends
                    O = np.array([np.array([npd - X_[2], X_[1], X_[0]]) - lf['centre']
                                  for X_ in (U * r + V * u for U, V in W)])
                    b = O @ dir_
                    oo2 = np.einsum('ij,ij->i', O, O)
                    disc = b * b - (oo2 - R_ * R_)
                    tt_s = np.where(disc >= 0.0, -b + np.sqrt(np.maximum(disc, 0.0)), -b)
                    disc_g = b * b - (oo2 - lf['R'] ** 2)
                    tt_g = np.where(disc_g >= 0.0, -b + np.sqrt(np.maximum(disc_g, 0.0)), -np.inf)
                    ends = (('medial', 0), ('lateral', n)) if key == 'upper' else (('lateral', 0), ('medial', n))
                    tt = tt_s.copy()
                    for nm_, j_ in ends:
                        tgt = np.asarray(CANTHI[nm_], float) - lf['centre'][:2]
                        tt_c = float((tgt - O[j_, :2]) @ dir_[:2] / (dir_[:2] @ dir_[:2]))
                        fr_ = np.abs(np.arange(n + 1) - j_) / float(n)          # the arc length from this canthus
                        w_ = sm01(1.0 - fr_ / face['third'])
                        tt = tt + w_ * (tt_c - tt_s)
                    tt = np.maximum(tt, tt_g)
                    P3 = O + tt[:, None] * dir_[None]
                    hh.append(P3 @ lf['oo'])
                else:
                    for U, V in W:
                        X = U * r + V * u
                        o = np.array([npd - X[2], X[1], X[0]]) - lf['centre']
                        b = float(dir_ @ o)
                        cc = float(o @ o) - R_ * R_
                        disc = b * b - cc
                        tt = -b + np.sqrt(disc) if disc >= 0.0 else -b
                        pq = o + tt * dir_
                        P3.append(pq * (R_ / max(np.linalg.norm(pq), 1e-9)) if (disc < 0.0 and pin) else pq)
                    P3 = np.array(P3)
                halves.append(np.column_stack([P3 @ lf['e1'], P3 @ lf['ed']]))
                halves3.append(np.asarray(P3, float))
            loop = np.vstack([halves[0][:-1], halves[1][:-1]])
            loops[f'{pid}_{side}'] = loop
            out.append(loop)
            if face is not None:
                hs.append(np.concatenate([hh[0][:-1], hh[1][:-1]]))
            # (W2q: the loop in 3D, relative to its own globe's centre, mirrored onto the left eye)
            L3_ = np.vstack([halves3[0][:-1], halves3[1][:-1]]) * np.array([1.0, 1.0, 1.0 if side == 'L' else -1.0])
            l3[f'{pid}_{side}'] = L3_ + lid_frame(spec, 'L')['centre']
    if face is not None:
        if loops3:
            return np.mean(out, axis=0), loops, np.mean(hs, axis=0), l3
        return np.mean(out, axis=0), loops, np.mean(hs, axis=0)
    return np.mean(out, axis=0), loops


def traced_canthi(spec, phi, G):
    """W2i (the lead's call 3): the photos' CANTHI (lm_<pid>.json canthus_med_*, canthus_lat_*: the ends each photo's
    fissure is read between) carried through each photo's solved camera onto the skin of phi (on_skin_w12's march),
    the right eyes mirrored, averaged over the photos of EYE_FISSURES. The tracing's own corners reach them in the
    photos, but past the globe's outline the rays miss the lid's sphere (w12's fissures 30-33 mm against a 27.6 mm
    sphere), so traced_fissure's polygon stops short of them. Returns {'medial', 'lateral': (3,)} palate mm, the left eye"""
    import json as _json
    import os as _os
    clay = clay_points(spec)
    npd = clay['np_mm']
    here = _os.path.dirname(_os.path.abspath(__file__))
    acc = {'medial': [], 'lateral': []}
    for pid in EYE_FISSURES:
        pt = _json.load(open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work',
                                           'data', f'lm_{pid}.json'), encoding='utf-8'))['points']
        L = FRONTS[pid]['landmarks'] if pid in FRONTS else {k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}
        so = solve_front(dict(landmarks=L), clay)
        fr_ = dict(cam=so['cam'], npd=npd)
        for side in ('L', 'R'):
            for key, nm in (('medial', f'canthus_med_{side}'), ('lateral', f'canthus_lat_{side}')):
                S, _ = on_skin_w12(phi, G, fr_, so['to_img'](np.asarray(pt[nm], float)[None]))
                if np.isfinite(S[0]).all():
                    acc[key].append(S[0] * np.array([1.0, 1.0, 1.0 if side == 'L' else -1.0]))
    return {k: np.mean(v, axis=0) for k, v in acc.items()}


def fissure_polygon(poly0, can, lf, side, tips=None, exact=False):
    """W2i: traced_fissure's polygon (e1, ed mm) with its CORNERS drawn out along its tip-to-tip axis till its tips
    stand over the photos' canthi (traced_canthi, seen along the eye's axis), its middle (the traced margins over the
    iris) kept; poly0 itself when can is None. The lid seat and the analytic cut share it. tips: the corners' indices
    (W2n: traced_fissure's own canthi, 0 and n; default the least and most lateral points: the averaged medial end is
    blunt, so that pick flipped between the upper lid's 5th point and the lower lid's 69th with a 0.5 mm camera change).
    exact (W2n): each tip moved onto its canthus in the chart (both coordinates, either way), the same smooth weights
    carrying the corner's neighbours with it"""
    if can is None:
        return poly0
    sx_ = 1.0 if side == 'L' else -1.0
    c2d = {k: np.array([(v * np.array([1.0, 1.0, sx_]) - lf['centre']) @ lf['e1'],
                        (v * np.array([1.0, 1.0, sx_]) - lf['centre']) @ lf['ed']]) for k, v in can.items()}
    im_, il_ = (int(np.argmin(poly0[:, 0])), int(np.argmax(poly0[:, 0]))) if tips is None else tips
    ua = poly0[il_] - poly0[im_]
    ua /= np.linalg.norm(ua)
    s_ = poly0 @ ua
    sm_, sl_ = s_[im_], s_[il_]
    sc_ = 0.5 * (sm_ + sl_)
    dm_, dl_ = min(c2d['medial'] @ ua - sm_, 0.0), max(c2d['lateral'] @ ua - sl_, 0.0)
    sm01 = lambda t: np.clip(t, 0.0, 1.0) ** 2 * (3.0 - 2.0 * np.clip(t, 0.0, 1.0))
    if exact:
        wm, wl = sm01((sc_ - s_) / (sc_ - sm_)), sm01((s_ - sc_) / (sl_ - sc_))
        return poly0 + wm[:, None] * (c2d['medial'] - poly0[im_])[None] + wl[:, None] * (c2d['lateral'] - poly0[il_])[None]
    move = dm_ * sm01((sc_ - s_) / (sc_ - sm_)) + dl_ * sm01((s_ - sc_) / (sl_ - sc_))
    return poly0 + move[:, None] * ua[None]


# ============================================================================================ W2n: the eye's landmark
# THE PHOTOS' EYE LANDMARK, LIKE FOR LIKE (the lead's W2n call 1). Every photo marks its eye at the middle of the lid
# opening, the midpoint of its two canthi (the fronts w12 0.0 px, w07 / w08 within 4.5 px; the profiles w01 / w03 / w10 /
# w11 within 0.001-0.009 NE: the W2m fresh eyes). The clay's matching point is the middle of ITS opening in that view:
# from the front cameras both canthi show, so it is the midpoint of the eye chart's fissure tips (fissure_chart: the
# cage's margin, the traced fissure with its corners drawn out to the photos' canthi on their rays); from the side (the
# profiles) the medial canthus can hide behind the ball, and the opening's front end there is where the ball shows
# (eye_opening_side). The tips are carried from the photos through the cameras and the cameras are solved on their
# midpoint, so the two are iterated to a fixed point (eye_landmark)
_EYE_LM = {}


def canthi_on_rays(spec, clay=None, Rl=None, depth=None):
    """the photos' CANTHI (lm_<pid>.json canthus_med_*, canthus_lat_*, the photos of EYE_FISSURES) on their solved
    cameras' rays, each at the depth its rule gives (depth: {'medial', 'lateral': 'sphere' | 'profile'}, default
    CANTHUS_DEPTH): 'sphere' the point NEAREST THE LID'S SPHERE (its camera-side crossing, or the ray's nearest approach
    where it passes outside), 'profile' the point whose (d, q) is nearest the head profiles' canthus (CANTHI); each lands
    on its photo's corner in that camera; the right eyes mirrored onto the left, averaged. clay: the registration
    (clay_points' dict); Rl: the lid sphere's radius (mm; default the globe's + STROKES_SKULL eye lid[0]). Returns
    {'medial', 'lateral': (3,)} palate mm, the left eye. (W2n: canid_cage.canthi_near_globe's body, moved here so
    eye_landmark can carry it under a given registration; canid_cage calls it)"""
    depth = CANTHUS_DEPTH if depth is None else depth
    import json as _json
    import os as _os
    clay = clay_points(spec) if clay is None else clay
    npd = clay['np_mm']
    here = _os.path.dirname(_os.path.abspath(__file__))
    acc = {'medial': [], 'lateral': []}
    for pid in EYE_FISSURES:
        with open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work', 'data',
                                f'lm_{pid}.json'), encoding='utf-8') as fh:
            pt = _json.load(fh)['points']
        L = FRONTS[pid]['landmarks'] if pid in FRONTS else {k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}
        so = solve_front(dict(landmarks=L), clay)
        cc, r, u = (np.asarray(a, np.float64) for a in so['cam'])
        dv = np.array([cc[2], -cc[1], -cc[0]])               # away from the camera, palate (d, q, x)
        dv /= np.linalg.norm(dv)
        for side in ('L', 'R'):
            lf = lid_frame(spec, side)
            c = lf['centre']
            R_ = lf['R'] + STROKES_SKULL['eye']['lid'][0] if Rl is None else Rl
            for key, nm in (('medial', f'canthus_med_{side}'), ('lateral', f'canthus_lat_{side}')):
                W = so['to_img'](np.asarray(pt[nm], np.float64)[None])[0]
                X0 = W[0] * r + W[1] * u + 400.0 * cc
                o = np.array([npd - X0[2], X0[1], X0[0]])
                if depth.get(key, 'sphere') == 'profile':
                    tgt = np.asarray(CANTHI[key], np.float64)
                    if side == 'R':
                        o = o * np.array([1.0, 1.0, -1.0])
                        dv_ = dv * np.array([1.0, 1.0, -1.0])
                    else:
                        dv_ = dv
                    P = o + float((tgt - o[:2]) @ dv_[:2] / (dv_[:2] @ dv_[:2])) * dv_
                    acc[key].append(P)
                    continue
                ts = float((c - o) @ dv)
                Pn = o + ts * dv
                dist = float(np.linalg.norm(Pn - c))
                P = o + (ts - np.sqrt(R_ * R_ - dist * dist)) * dv if dist < R_ else Pn
                acc[key].append(P * np.array([1.0, 1.0, 1.0 if side == 'L' else -1.0]))
    return {k: np.mean(v, axis=0) for k, v in acc.items()}


def fissure_chart(spec, clay=None, Rl=None, depth=None, pin=True, face=None):
    """W2n: THE EYE CHART'S FISSURE (canid_cage.eye_chart's margin before its star-shaping): traced_fissure's polygon with
    its corners drawn out to the photos' canthi on their rays (canthi_on_rays, fissure_polygon), lifted along the eye's
    axis onto the lid's sphere (radius Rl), past 0.97 of its outline pushed out radially to Rl + 0.5 mm (the commissures
    hug the globe). clay: the registration (default clay_points'); Rl: default the globe's + STROKES_SKULL eye lid[0];
    pin: traced_fissure's (eye_landmark's fixed point is solved on pin=True's tips; the cage may build pin=False's
    pointed corners, whose tips' midpoint lands within a fraction of a mm of it: check_w2n/regtest.py prints it).
    Returns dict(poly0, poly (k, 2) e1 / ed mm, P3 (k, 3) palate mm, tips {'medial', 'lateral'}: (3,), tip_idx, can,
    lf, Rl), the left eye. The tips are the traced corners (traced_fissure's loop runs from the medial canthus, index 0,
    over the upper lid to the lateral canthus, index n, and back), drawn out to the photos' canthi (depth: their rules,
    default CANTHUS_DEPTH; eye_landmark passes CANTHUS_DEPTH_REG).
    face (W2o, the CAGE's corners: canid_cage EYE face): traced_fissure's face rule, each loop carried along its own rays
    with its canthi at the profile rule and its corner ends running to them on the face; the tips are then the profile-
    rule canthi themselves (the average of the loops' ends is canthi_on_rays 'profile''s average: the same points), no
    drawing out. Inside the lid sphere's outline the margin is lifted onto the sphere or stays in front of it where the
    loops put it (the inner third, off the ball toward the medial canthus); past the outline it keeps the loops' own
    height along the axis (the corners on the face), never closer than Rl + 0.5 mm to the globe's centre"""
    lf = lid_frame(spec, 'L')
    c, oo, e1, ed = lf['centre'], lf['oo'], lf['e1'], lf['ed']
    Rl = lf['R'] + STROKES_SKULL['eye']['lid'][0] if Rl is None else Rl
    if face is not None:
        follow = isinstance(face, dict) and bool(face.get('follow'))
        if follow:
            # W2q (the lead's call 1): THE REST LIDS, each photo's turned back to the rest gaze by its own iris gaze and
            # the fitted follow ratios, then averaged with the profiles' (lid_follow; the module's W2q note); the loop
            # keeps traced_fissure's layout (index 0 the medial canthus, n the lateral)
            LF_ = lid_follow(spec, clay, {k: v for k, v in face.items() if k != 'follow'})
            poly0, h0 = LF_['poly0'], LF_['h0']
        else:
            poly0, _, h0 = traced_fissure(spec, clay=clay, pin=False, face=face)
        can = canthi_on_rays(spec, clay, Rl, dict(medial='profile', lateral='profile'))
        im_, il_ = 0, len(poly0) // 2

        def lift(pl_, hh_):
            r2_ = (pl_ ** 2).sum(1)
            hs__ = np.where(r2_ < Rl * Rl, np.sqrt(np.maximum(Rl * Rl - r2_, 0.0)), -np.inf)
            h__ = np.maximum(hs__, hh_)
            P_ = c + pl_[:, :1] * e1 + pl_[:, 1:2] * ed + h__[:, None] * oo
            D__ = P_ - c
            nD_ = np.linalg.norm(D__, axis=1, keepdims=True)
            out_ = r2_ > (0.97 * Rl) ** 2
            P_[out_] = (c + D__ / nD_ * np.maximum(nD_, Rl + 0.5))[out_]
            return P_, h__
        P3, h = lift(poly0, h0)
        P3_env = None
        if follow:
            # (the rest lids posed at the largest fitted gaze, lifted alike: canid_cage.eye_chart's rim and orbit rings
            # enclose it, the socket staying with the face while the lids turn inside it)
            De_ = LF_['env'] - c
            P3_env, _ = lift(np.column_stack([De_ @ e1, De_ @ ed]), De_ @ oo)
        gz = float(face.get('gaze', 0.0)) if isinstance(face, dict) else 0.0
        gzl = float(face.get('gaze_lower', gz)) if isinstance(face, dict) else 0.0
        P3_0 = P3.copy()
        if gz != 0.0 or gzl != 0.0:
            # W2p (the lead's call 2, "resolve the lids' height between the fronts and the profiles"): THE LIDS AT REST
            # GAZE. The front photos' wolves look up into their cameras (w12 48 deg over the palate, w08 37: 29 / 18 over
            # the eye's axis) and a canid's lids follow the cornea, so carried onto the globe the photos' opening faces
            # 27 deg up for w12 and 8 deg for w08 (work/bestiary/wolf/check_w2p/NOTES.md, scratchpad gaze.py), and from the
            # side the margin stood 6 mm high on its corner line where the head profiles' (level gaze; w11 is w12's wolf)
            # straddle theirs. The registration cannot move it (the side read held within 0.1 mm for the globe 4 mm down,
            # the cameras 12 deg flatter, the axis 10 deg lower: seat_p.py, cam_sens.py, axis_sens.py). So the margin on
            # the globe is turned DOWN by `gaze` deg about the horizontal axis across the eye's axis through the globe's
            # centre (the eye's own vertical rotation), the corners held: the weight runs 0 at each tip to 1 over
            # `gaze_ramp` of the tip-to-tip line, and 0 wherever the margin runs on the face (past the lid sphere + 0.3 mm,
            # over 1.5 mm: place_eye's w_on)
            k_ = np.cross(oo, np.array([0.0, 1.0, 0.0]))
            k_ /= np.linalg.norm(k_)
            if (oo * np.cos(0.01) + np.cross(k_, oo) * np.sin(0.01))[1] > oo[1]:
                k_ = -k_
            s_ = (P3 - P3[im_]) @ (P3[il_] - P3[im_]) / float((P3[il_] - P3[im_]) @ (P3[il_] - P3[im_]))
            ramp = float(face.get('gaze_ramp', 0.25))
            sm_ = lambda t_: (lambda u: u * u * (3.0 - 2.0 * u))(np.clip(t_, 0.0, 1.0))  # noqa: E731
            rho_ = np.linalg.norm(P3 - c, axis=1)
            w_ = sm_(s_ / ramp) * sm_((1.0 - s_) / ramp) * (1.0 - sm_((rho_ - (Rl + 0.3)) / 1.5))
            # (W2p successor: each lid its own turn, `gaze` the upper lid's (the loop from the medial tip over the top to
            # the lateral tip, indices im_ .. il_), `gaze_lower` the lower's (default the same))
            up_ = np.arange(len(P3)) <= il_
            a_ = np.radians(np.where(up_, gz, gzl)) * w_
            D_ = P3 - c
            P3 = c + (D_ * np.cos(a_)[:, None] + np.cross(k_[None], D_) * np.sin(a_)[:, None]
                      + k_[None] * (D_ @ k_)[:, None] * (1.0 - np.cos(a_))[:, None])
        # (P3_0: the margin before the rest-gaze turn; canid_cage.eye_chart builds the chart's frame, and with it the rim
        # and the orbit's rings, from it: the lids turn with the eye, the socket stays with the face)
        # (W2q, follow: P3 is the rest margin and frames the chart itself (its centre inside the rest opening: the
        # fissure star-shaped round it); P3_env, the margin at the largest fitted gaze, is what the socket encloses)
        return dict(poly0=poly0, poly=poly0.copy(), P3=P3, P3_0=P3_0, P3_env=P3_env,
                    tips=dict(medial=P3[im_], lateral=P3[il_]), tip_idx=(im_, il_), can=can, lf=lf, Rl=Rl, h=h,
                    follow=LF_ if follow else None)
    poly0, _ = traced_fissure(spec, clay=clay, pin=pin)
    can = canthi_on_rays(spec, clay, Rl, depth)
    im_, il_ = 0, len(poly0) // 2
    # (the corners drawn out ALONG the tip-to-tip axis only, as the n1 build and its flow stage were made: the 'exact'
    # carry, each tip moved onto its canthus in both chart coordinates, follows the photos' rays, which move with the
    # registration, so eye_landmark had no fixed point (steps 0.27 -> 0.15 mm after 45 iterations, w12's camera 48.3 ->
    # 51.1 -> 49.8 deg: a slow drift down the face); with it the medial corner by the profiles ran off (w12 95 deg))
    poly = fissure_polygon(poly0, can, lf, 'L', tips=(im_, il_), exact=False)
    r2 = (poly ** 2).sum(1)
    h = np.sqrt(np.maximum(Rl * Rl - r2, 0.0))
    # W2n: a canthus past the lid sphere's outline placed by the PROFILES' depth (CANTHUS_DEPTH 'profile': the medial one,
    # on the face in front of the ball) lands at its own depth along the axis: on that tip's half of the polygon, past
    # 0.97 of the outline, the height runs from the sphere's there to the canthus's linearly in the chart radius. A
    # canthus by the 'sphere' rule keeps W2j-W2m's corner: no height past the outline (the plane through the globe's
    # centre), pushed out radially below. (Lifting the sphere-rule corners too, whose rays miss the sphere at each
    # camera's limb plane, moved the registration's tips with the cameras: eye_landmark's iteration ran off to w12 at
    # 76.5 deg / yaw +47 and its lateral tip 23 mm from the globe's centre; check_w2n/out/regtest_r4.json)
    depth_ = CANTHUS_DEPTH if depth is None else depth
    r_ = np.sqrt(r2)
    r0 = 0.97 * Rl
    h0 = float(np.sqrt(Rl * Rl - r0 * r0))
    s_ = poly @ (poly[il_] - poly[im_])
    s_mid = 0.5 * (s_[im_] + s_[il_])
    for key, half in (('medial', s_ < s_mid), ('lateral', s_ >= s_mid)):
        if depth_.get(key, 'sphere') != 'profile':
            continue
        cn = np.asarray(can[key], np.float64) - c
        rc = float(np.hypot(cn @ e1, cn @ ed))
        if rc > r0 + 1e-6:
            sel = half & (r_ > r0)
            h[sel] = h0 + (float(cn @ oo) - h0) * np.clip((r_[sel] - r0) / (rc - r0), 0.0, 1.0)
    P3 = c + poly[:, :1] * e1 + poly[:, 1:2] * ed + h[:, None] * oo
    D_ = P3 - c
    nD = np.linalg.norm(D_, axis=1, keepdims=True)
    out = r2 > (0.97 * Rl) ** 2
    P3[out] = (c + D_ / nD * np.maximum(nD, Rl + 0.5))[out]
    return dict(poly0=poly0, poly=poly, P3=P3, tips=dict(medial=P3[im_], lateral=P3[il_]), tip_idx=(im_, il_), can=can,
                lf=lf, Rl=Rl)


def _eye_landmark_key(spec):
    """every input of eye_landmark (the in-process cache's key: probes override the tables in place)"""
    import hashlib as _hl
    import os as _os
    from . import canid
    dd = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..', '..', 'work', 'bestiary',
                       'research', 'wolf_work', 'data')
    lm = {}
    for p in EYE_FISSURES:
        with open(_os.path.join(dd, f'lm_{p}.json'), 'rb') as fh:
            lm[p] = _hl.sha1(fh.read()).hexdigest()
    return cache_key(dict(eye=spec['eye'], head_len=spec['head_len'], seat=canid.EYE_SEAT, eq=canid.EYE_Q,
                          elev=canid.EYE_ELEV, poll=canid.POLL, nq=canid.NOSE_Q, nj=canid.NOSE_J,
                          lid=STROKES_SKULL['eye'], canthi=CANTHI, depth=CANTHUS_DEPTH_REG, fis=EYE_FISSURES, lm=lm,
                          fronts={k: v['landmarks'] for k, v in FRONTS.items()}))


def eye_landmark(spec, tol=1e-3, iters=60):
    """W2n (the lead's call 1): THE CLAY'S EYE LANDMARK FOR THE FRONT PHOTOS, like for like: the middle of its lid
    opening, the midpoint of the eye chart's two fissure tips (fissure_chart, its corners by CANTHUS_DEPTH_REG and pinned:
    tied to the globe, the anchor; the cage builds the unpinned corners, canid_cage EYE pin, whose tips' midpoint lands
    0.42-0.52 mm from this point in the five front cameras' images), with the
    front cameras solved on that same point. Iterated from the cornea's apex to a FIXED POINT: each step solves the cameras on the current point,
    carries the traced fissure and the photos' canthi through them and takes the tips' new midpoint, until it moves
    under `tol` mm. Returns dict(front (3,) palate mm (d, q, x) of the left eye, tips, steps (mm per iteration), cams
    {pid: (alpha, psi)} of the photos the fissure is carried from), cached in the process by its inputs"""
    key = _eye_landmark_key(spec)
    if key in _EYE_LM:
        return _EYE_LM[key]
    base = _clay_base(spec)
    e = np.asarray(base['apex_L'], np.float64)
    steps = []
    F, clay = None, None
    # (plain iteration: 21 steps, the last ones shrinking ~0.78 a step. An Aitken jump tried on the way lands 0.004 mm off
    # the plain iterate, which the flow stage's key (flow_key: clay_points to 1e-4 mm) reads as a new registration)
    for _ in range(iters):
        clay = dict(base, vis_L=tuple(e), vis_R=(e[0], e[1], -e[2]))
        F = fissure_chart(spec, clay, depth=CANTHUS_DEPTH_REG)
        m = 0.5 * (F['tips']['medial'] + F['tips']['lateral'])
        steps.append(float(np.linalg.norm(m - e)))
        e = m
        if steps[-1] < tol:
            break
    if steps[-1] >= tol:
        raise RuntimeError(f'eye_landmark: no fixed point in {iters} iterations (the last steps {steps[-3:]} mm)')
    import json as _json
    import os as _os
    cams = {}
    here = _os.path.dirname(_os.path.abspath(__file__))
    for pid in EYE_FISSURES:
        if pid in FRONTS:
            L = FRONTS[pid]['landmarks']
        else:
            with open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work', 'data',
                                    f'lm_{pid}.json'), encoding='utf-8') as fh:
                pt = _json.load(fh)['points']
            L = {k: pt[k] for k in ('eye_R', 'eye_L', 'nose_R', 'nose_L')}
        so = solve_front(dict(landmarks=L), dict(base, vis_L=tuple(e), vis_R=(e[0], e[1], -e[2])))
        cams[pid] = (so['alpha'], so['psi'])
    res = dict(front=e, tips={k: np.asarray(v, np.float64) for k, v in F['tips'].items()}, steps=steps, cams=cams,
               apex=np.asarray(base['apex_L'], np.float64))
    _EYE_LM[key] = res
    return res


def eye_opening_side(spec, clay=None, n=(91, 181)):
    """W2n (the lead's call 1, "the profile / NE / IO reads use the middle of the clay's visible lid opening in that
    view"): THE CLAY'S EYE OPENING SEEN FROM THE SIDE, projected along x as the head profiles w01 / w03 / w10 / w11 see it
    (their eye mark is the middle of the opening seen there, the midpoint of their canthi). Its visible part: the margin
    (fissure_chart's) where the ball does not hide it from the side, and the globe where it shows through the opening and
    faces the side. Its front and back ends (least and most d) and their middle. From the side the medial canthus can hide
    behind the ball (W2m: d 133.2 behind the ball's front at d 131.2), and the opening's front end is then the ball's own
    outline. Returns dict(front, back, middle: (3,) palate mm (d, q, x), the left eye; medial_hidden). The margin is
    the cage's (canid_cage EYE pin: its corners pinned to the ball's outline or run on along their rays; W2o EYE face:
    its corners on the face at the profile-rule canthi)"""
    from . import canid_cage as _CC
    F = fissure_chart(spec, clay, pin=_CC.EYE.get('pin', True), face=_CC.EYE.get('face'))
    lf = F['lf']
    c, oo, e1, ed, R = lf['centre'], lf['oo'], lf['e1'], lf['ed'], float(lf['R'])
    xs = np.array([0.0, 0.0, 1.0])
    P = F['P3']
    t_ = (c - P) @ xs
    near = np.linalg.norm(P + t_[:, None] * xs[None] - c, axis=1)
    vis_m = ~((t_ > 0.0) & (near < R))
    th, ph = np.meshgrid(np.linspace(0.0, np.pi, n[0]), np.linspace(-np.pi, np.pi, n[1]), indexing='ij')
    U = np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], -1).reshape(-1, 3)
    poly = F['poly']
    img, lo, res = poly_sdf_image(poly, poly.min(0) - 3.0, poly.max(0) + 3.0, 0.1)
    inside = (U @ oo > 0.0) & (sample2(img, lo, res, R * (U @ e1), R * (U @ ed)) <= 0.0) & (U @ xs > 0.0)
    pts = np.vstack([P[vis_m], c + R * U[inside]])
    fr_, bk_ = pts[int(np.argmin(pts[:, 0]))], pts[int(np.argmax(pts[:, 0]))]
    return dict(front=fr_, back=bk_, middle=0.5 * (fr_ + bk_), medial_hidden=bool(not vis_m[F['tip_idx'][0]]),
                tips=F['tips'])


# ============================================================================================ W2q: the lids follow the gaze
# THE REST GAZE AND THE LIDS AS A FUNCTION OF GAZE (the lead's W2q call 1: "the clay's rest eye looks level and forward
# along the head's own axis, as a game asset's eye is modelled (the rig adds look-at and lid-follow later). The lids
# become a function of gaze: when the cornea turns, the lids follow it by a follow ratio (upper and lower their own) that
# you fit from the photos themselves ... Each photo is compared with the clay posed at ITS OWN gaze, read from its iris
# ... The rest lids are solved jointly from fronts and profiles under that model. Keep the follow ratios as data the
# runtime's eye rig can read").
# THE MODEL. The lids turn about the CANTHUS AXIS: the line through the globe's centre parallel to the two canthi (the
# cage's tips, canthi_on_rays 'profile'); a turn about it carries the margin across the fissure over the ball, while the
# corners, 5.7 mm off the axis at its two ends, barely move. Every point is read in that axis' cylinder: s along it
# (medial -, lateral +), rho off it, phi about it (0 along the lids' axis oo made normal to it, 90 dorsal). A gaze g (the
# cornea's direction from the globe's centre) has its own turn about the axis, theta(g) = atan2(g . n_v, g . n_o) (its
# component ALONG the axis carries the cornea along the fissure, which the lids do not follow: w11's iris at its lateral
# corner), and each lid follows it: phi(s; g) = phi_rest(s) + f_lid (theta(g) - theta_rest) w(s), w(s) 1 over the ball
# and easing to 0 at the canthi over GAZE taper mm of s. The rest gaze is level and forward along the palate (GAZE rest:
# theta_rest -24.4 deg on W2p's canthi).
# THE GAZES are READ FROM EACH PHOTO'S IRIS (EYE_IRIS) against the clay's globe in the photo's own frame (photo_gaze: the
# fronts through their solved cameras, the profiles with their canthi registered onto the tips' (d, q) and seen along
# x): the visible iris is the limbus circle, its centre sqrt(R^2 - limbus^2) along g from the globe's centre (GAZE
# limbus, the cornea's radius). Measured on W2p's clay (work/bestiary/wolf/check_w2q/NOTES.md 13:05): theta w12 L / R
# +18 / +22, w08 -15 / -4, w11 -33.5, w01 -58; each photo's lids are centred on its IRIS gaze (the opening's middle phi
# at s 0: w12 +13, w08 -9, w11 -38, w01 -43), not on its camera (against the clay's globe the fronts read 20-33 deg off
# their cameras, 'into the camera' would put w12 at +35 and w08 at +22-24 with no fit to the lids). The FOLLOW RATIOS:
# fitted (lid_follow) on the same wolf at two gazes first (GAZE pair, w12 / w11: upper 1.02, lower 0.91), then on every
# photo with an iris and traced lids (GAZE fit: w12, w08, w11: upper 0.97, lower 0.82), w01 (looking 58 deg down, the
# lids saturating) a check only. The rest lids: each photo's lids turned back to the rest gaze by its own turn, then
# averaged (GAZE rest_from), fronts and profiles together
# THE IRISES (photo px: the centre and radius of a circle fitted to each iris's visible side arcs, the lids clipping its
# top and bottom; check_w2q scratch iris2.py, the fits drawn on the photos in its iris2_sheet.png). w07's two are read
# by eye on a blurred crop (+-5 px, ~10 deg of gaze: its fissure gate's pose only); w03 (black-and-white, dark) and w10
# (the eyes nearly shut in sun: a squint, not a gaze pose) have none. w01 is a right profile: its right eye. The wet r03
# and the mange r07 (no lm files; FRONTS' landmarks) read by eye on dark / small crops (+-1.2 mm, ~7 deg): w02's margin
# gate poses their eyes by them
# W2r (the lead's call 3, "at w11's gaze the upper lid arches with its peak mid-length as the photo's does (IoU 0.57
# toward the fronts' ~0.77), without losing the fronts"): THE HORIZONTAL FOLLOW. The W2q rig turned the lids about the
# canthus axis by the gaze's turn about it and ignored the cornea's move ALONG the axis (along the fissure). But the
# photos' lids, turned back by their turns, disagree in exactly that: the fronts (their corneas 1.7-7.9 mm from the
# rest gaze's toward the lateral canthus, looking into cameras in front) peak at s -9..-11 (+22..+29 deg), w11 (+18.1 mm:
# its iris at its lateral corner) rises to the lateral end (-13 deg at s -8 to +21 at s +12), w01 (+10.3) peaks at s +5;
# their lids' centroids along s follow the cornea's place, ~0.3 mm per mm (check_w2r/along_gaze.py), as the upper lid
# rides over the cornea's bulge (in cats and primates the lid's highest point stays over the pupil). So each lid's
# shape SLIDES along the axis by GAZE slide x the cornea's move D = R (g - g_rest) . a (gaze_slide), the canthi held by
# the taper: lid_follow fits on the photos' lids slid back (lid_slide), canid_cage.pose_cage slides the rest lids
# (slide_points). Fitted: the upper lid's spread about the rest falls 8.6 -> 8.3 / 6.8 deg rms at 0.3 / 0.6 (the
# vertical follow refitted 0.72 / 0.69), the lower lid's rises (5.4 -> 7.4 at 0.3): the lower slides 0. At 0.3 w11's side
# at its gaze IoU 0.57 -> 0.68, the fronts 0.79 / 0.76 / 0.80 / 0.82 -> 0.77 / 0.76 / 0.81 / 0.81 (check_w2r probe
# c1, slide_probe.py); 0.45: w11 0.69, the fronts down to 0.73. w11's read (out +101 deg: the cornea 18 mm along the
# axis) is the fit's lever and the least certain gaze; 0.3 keeps the fronts
# W2s (the lead's calls 1-2: "THE REST GAZE from the canid's measured visual axis ... re-fit the follow ratios on it";
# "THE ALMOND: fit the rest lids with the side photos (w11, w04, w01) weighted beside the fronts, so the upper lid's peak
# sits mid-length from the side while the fronts hold"). THE REST GAZE: 20 deg lateral of the midline, level (GAZE rest;
# Miller & Murphy 1995), not along the palate (43.6 deg medial of the lids' axis: the painted iris filled 21 % of the
# globe seen in profile). THE WEDGE'S CAUSE (work/bestiary/wolf/check_w2s/gaze_probe.py, its phi(s) tables): in the
# canthus cylinder the fronts' lids turned back peak at s -10 (+25..+38 deg) and fall laterally, w11's turned back RISES
# to the lateral end (-20 at s -12 to +18 at s +6): opposite shapes, which the W2q-W2r average (four front eyes to one
# profile) settled in the fronts' favour; and from the side the stretch s -12..-4 of the upper lid rides the globe's
# forward face, seen edge-on, so whatever it does reads at t 0.12-0.17 (the "8 mm climb within 13 %"). The same wolf
# w12 -> w11 moves its upper lid's hump ~17-19 mm along s for the cornea's 12.4 mm: the lid's highest point rides with
# the cornea, far more than W2r's 0.3 mm per mm, and W2r's slide (s - k D w(s), w the taper) FOLDS the lid along s once
# k D w' > 1 (k 1.0: the upper lid below its corner line at t 0.2-0.3 from the side). THE HORIZONTAL FOLLOW AS A WARP
# (GAZE slide_mode 'warp', gaze_warp): a monotone PCHIP map of s through the canthi (held) and the rest cornea's place
# moved k D, k 1.0, so the hump rides with the cornea without folding; lid_follow undoes it before the fit (lid_unwarp)
# and loop_at / canid_cage.slide_points apply it. The follow ratios fitted on all five photo sets (the profiles w01 and
# w04 joining w12 / w08 / w11; w04 read on its 10x crop, EYE_IRIS): upper 0.76, lower 0.59; the rest lids averaged with
# the profiles weighted (GAZE rest_w: w11 3, w01 2, w04 0.5; each front eye 1). Scanned analytically (check_w2s
# gaze_scan.py, scan1-3: the posed margin through the photos' cameras) and probed on the cage (probe_s.py s3: the
# fronts at their gazes IoU 0.77 / 0.73 / 0.78 / 0.82, w11 from the side at its gaze: its upper lid's crest at t 0.52
# where the photo's is at 0.50; W2r: 0.19). AT REST, FROM THE EXACT SIDE, THE CREST STILL READS t 0.16-0.18 (9.7 mm): IN 3D
# the rest lid IS an almond (its farthest point from the chord at t 0.44, s -2.6), but the chord foreshortens 32.4 ->
# 21.6 mm from the side and the crest stands proud along the view, so the projection shears it (check_w2s rest_shear.py:
# crest t 0.52 / 0.40 / 0.28 / 0.18 at az 0 / 45 / 75 / 90; a perfectly symmetric bell of that height lands at 0.26). NOT
# TESTED AGAINST A PHOTO: the side wolves in hand, w11 and the held-out v611 and v031 (check_w2s/ref_ahead), all look toward their
# cameras, solving to +88..+100 deg out from a 20 deg rest: more turn than a canid's eye has, in three unrelated wolves, so
# the globe's station along the head (the one coordinate the fronts barely see) may be a few mm forward of the truth:
# check_w2s seat_scan.py, relief_read.py; the lead's call, EYE_SEAT unchanged here
EYE_IRIS = dict(
    w12=dict(L=(2612.6, 1103.6, 46.8), R=(2137.3, 1123.0, 36.2)),
    w08=dict(L=(683.2, 430.8, 10.7), R=(537.6, 421.2, 10.9)),
    w07=dict(L=(1536.2, 1022.7, 12.5), R=(1282.3, 1033.4, 10.2)),
    w11=dict(L=(1502.6, 1049.0, 28.4)),
    w01=dict(R=(3269.9, 746.6, 11.7)),
    # W2s: the right profile w04 (its near eye the right; its canthi 40 px apart): read by eye on a 10x crop
    # (work/bestiary/wolf/check_w2s/out/zoom_w04_eye.png): the amber crescent's left and right arcs at x 1935 / 1948
    # (y 570-574), its lower arc at y ~578, the pupil and the upper iris in the upper lid's shadow; +-3 px, ~10 deg
    w04=dict(R=(1941.0, 567.0, 10.0)),
    r03=dict(L=(2442.7, 1076.8, 18.0), R=(2087.7, 1083.2, 18.0)),
    r07=dict(L=(2178.5, 634.5, 7.0), R=(2037.6, 641.6, 7.0)))
GAZE = dict(rest=(-0.9396926207859084, 0.0, 0.3420201433256687),
            #                                 W2s (the lead's call 1): THE CANID'S VISUAL AXIS, 20 deg lateral of the
            #                                 midline, level, palate (d, q, x) of the left eye (Miller & Murphy 1995, JAVMA
            #                                 207: "the eyes typically are placed so as to deviate approximately 20 deg
            #                                 lateral to the midline"; wolf.py eye.splay). W2q-W2r: (-1, 0, 0), along the
            #                                 palate, 43.6 deg medial of the lids' axis (the painted iris 21 % of the globe
            #                                 seen in profile)
            limbus=7.5,                     # the cornea's radius (mm): the iris circle's centre depth on the 12 mm globe
            taper=10.0,                     # w(s) eases from 0 at each canthus to 1 over this much s (mm; W2q-W2r 5. W2s
            #                                 10, the lateral end: the lid's outer third follows the gaze less, so at a
            #                                 down-gaze it stays up: w11 from the side IoU 0.66 -> 0.75, w01 0.67 -> 0.81,
            #                                 the flat crest w01's photo shows, the fronts unchanged; check_w2s e1, e2)
            taper_medial=10.0,              # the same from the medial canthus (mm; the medial palpebral ligament; W2q-W2r
            #                                 10. W2s tried 5, the fronts' IoU ~0.02 higher, and w02 _w2s2 read the inner
            #                                 canthus hidden at 7 of 10 posed cameras, +0.6..+0.9 mm against the gate's 0.5:
            #                                 back to 10)
            n=36,                           # points per lid in the rest loop (traced_fissure's)
            n_s=49,                         # the s samples canthus to canthus the lids are averaged on
            smooth=1.2,                     # the rest lids' smoothing along s (mm, gaussian)
            end_blend=(3.0, 3.0),           # W2r: the rest lids eased onto the canthi over this much s (mm; medial,
            #                                 lateral): lid_follow (W2q pinned the last sample)
            slide=(1.0, 0.0),               # W2r: THE HORIZONTAL FOLLOW (upper, lower): each lid's shape slides along
            #                                 the canthus axis by this many mm per mm of the cornea's move along it
            #                                 (lid_follow, canid_cage.pose_cage; the module's W2r note). W2s: 1.0 in the
            #                                 warp (W2r 0.3 in the taper: the module's W2s note)
            slide_taper=(13.0, 9.0),        # W2r: the slide eased in from each canthus over this much s (mm; medial,
            #                                 lateral): the corners' steep rises stay put (slide_taper; 'taper' mode only)
            slide_mode='warp',              # W2s: 'taper' (W2r: s - k D w(s)) or 'warp' (gaze_warp: a monotone map of
            #                                 the lid's s, the canthi fixed, the rest cornea's place moved by k D)
            warp_margin=3.0,                # W2s: the warp's anchor kept this far (mm) inside each canthus
            profiles=('w11', 'w01', 'w04'),  # W2s: the head profiles read from the side (profile_lids; W2q-W2r w11, w01)
            rest_w=dict(w11=3.0, w01=2.0, w04=0.5),
            #                                 W2s (the lead's call 2: "fit the rest lids with the side photos (w11, w04,
            #                                 w01) weighted beside the fronts"): each photo's weight in the rest lids'
            #                                 average (default 1: each of w12's and w08's eyes 1); w04 0.5 (its 40 px eye:
            #                                 the research trace runs through the iris, check_w2s/out/trace_w04.png)
            pair=('w12', 'w11'),            # the same wolf at two gazes: the first fit
            fit=('w12', 'w08', 'w11', 'w01', 'w04'),
            #                                 the photos the follow ratios are fitted on (W2s: with the profiles, upper
            #                                 0.76 / lower 0.59; W2q-W2r w12, w08, w11: 0.70 / 0.75 on the palate's rest)
            rest_from=('w12', 'w08', 'w11', 'w01', 'w04'),  # the photos the rest lids are averaged from
            check=(),                       # read and printed, not fitted (W2q-W2r w01: its lids saturating in its
            #                                 58-65 deg down-gaze; W2s: fitted with the warp)
            mid=6.0)                        # the fit reads |s| <= mid (mm), where w(s) = 1 on the ball
_GAZE = {}


def lid_axis(spec, clay=None):
    """W2q: THE CANTHUS AXIS of the left eye (the module's W2q note): dict(c the globe's centre, R, Rl the lid sphere's
    radius, a the axis (unit, medial to lateral canthus), no (phi 0: the lids' axis made normal to a), nv (phi 90,
    dorsal), oo, canthi {'medial', 'lateral': (3,)}, cyl_canthi {key: (s, rho, phi)}), palate mm"""
    lf = lid_frame(spec, 'L')
    c, oo, R = np.asarray(lf['centre'], float), np.asarray(lf['oo'], float), float(lf['R'])
    Rl = R + STROKES_SKULL['eye']['lid'][0]
    can = canthi_on_rays(spec, clay, Rl, dict(medial='profile', lateral='profile'))
    cm, cl = np.asarray(can['medial'], float), np.asarray(can['lateral'], float)
    a = (cl - cm) / np.linalg.norm(cl - cm)
    no = oo - (oo @ a) * a
    no /= np.linalg.norm(no)
    nv = np.cross(a, no)
    nv = nv if nv[1] >= 0.0 else -nv
    ax = dict(c=c, R=R, Rl=Rl, a=a, no=no, nv=nv, oo=oo, canthi=dict(medial=cm, lateral=cl))
    ax['cyl_canthi'] = {k: tuple(float(x[0]) for x in cyl(ax, v)) for k, v in ax['canthi'].items()}
    return ax


def cyl(ax, P):
    """W2q: points (n, 3) palate mm -> (s, rho, phi deg) in the canthus axis' cylinder"""
    D = np.atleast_2d(np.asarray(P, float)) - ax['c']
    x_, y_ = D @ ax['no'], D @ ax['nv']
    return D @ ax['a'], np.hypot(x_, y_), np.degrees(np.arctan2(y_, x_))


def uncyl(ax, s, rho, phi):
    """W2q: (s, rho, phi deg) -> points (n, 3) palate mm"""
    s, rho, ph = (np.atleast_1d(np.asarray(v, float)) for v in (s, rho, np.radians(phi)))
    return (ax['c'][None] + s[:, None] * ax['a'][None] + (rho * np.cos(ph))[:, None] * ax['no'][None]
            + (rho * np.sin(ph))[:, None] * ax['nv'][None])


def gaze_turn(ax, g):
    """W2q: the gaze g's turn about the canthus axis (deg): the component the lids follow"""
    g = np.asarray(g, float)
    return float(np.degrees(np.arctan2(g @ ax['nv'], g @ ax['no'])))


def lid_taper(ax, s):
    """W2q: the lid-follow weight along the axis, 0 at each canthus easing to 1 over GAZE taper mm of s (taper_medial
    from the medial canthus)"""
    sm_, sl_ = ax['cyl_canthi']['medial'][0], ax['cyl_canthi']['lateral'][0]
    t_ = np.minimum((np.asarray(s, float) - sm_) / GAZE.get('taper_medial', GAZE['taper']),
                    (sl_ - np.asarray(s, float)) / GAZE['taper'])
    t_ = np.clip(t_, 0.0, 1.0)
    return t_ * t_ * (3.0 - 2.0 * t_)


def _photo_lm(pid):
    import json as _json
    import os as _os
    here = _os.path.dirname(_os.path.abspath(__file__))
    with open(_os.path.join(here, '..', '..', '..', '..', 'work', 'bestiary', 'research', 'wolf_work', 'data',
                            f'lm_{pid}.json'), encoding='utf-8') as fh:
        return _json.load(fh)


def _profile_to_dq(spec, pid, ax):
    """W2q: a head profile's photo px -> the clay's (d, q) mm: its canthi onto the cage's tips' (d, q) (a similarity,
    the photo flipped so d runs back from the nose and q up)"""
    Lj = _photo_lm(pid)
    pt = Lj['points']
    right = pt['nose_tip'][0] > pt['eye_centre'][0]
    sg = np.array([1.0, -1.0]) if right else np.array([-1.0, -1.0])

    def to_dq(Q):
        F_ = np.atleast_2d(np.asarray(Q, float)) * sg
        return np.column_stack([-F_[:, 0], F_[:, 1]])
    T, scl = sim2(to_dq(pt['canthus_med'])[0], to_dq(pt['canthus_lat'])[0], ax['canthi']['medial'][:2],
                  ax['canthi']['lateral'][:2])
    return (lambda Q: T(to_dq(Q))), scl, Lj


def photo_gaze(spec, pid, side, clay=None, ax=None):
    """W2q: a photo eye's GAZE READ FROM ITS IRIS (EYE_IRIS) against the clay's globe (the module's W2q note): the fronts
    through their solved cameras (solve_front), the profiles with their canthi on the cage's tips (_profile_to_dq), seen
    along x. Returns dict(g the gaze (3,) of the left eye (the right eyes mirrored), palate (d, q, x); elev, out (deg
    over the palate, lateral); theta (gaze_turn); cam (deg off the camera's direction; fronts) or None)"""
    clay = clay_points(spec) if clay is None else clay
    ax = lid_axis(spec, clay) if ax is None else ax
    R = ax['R']
    Re = float(np.sqrt(max(R * R - GAZE['limbus'] ** 2, 1.0)))
    ir = EYE_IRIS[pid][side]
    sx = 1.0 if side == 'L' else -1.0
    try:
        Lj = _photo_lm(pid)
    except OSError:
        Lj = dict(kind='front', points={})          # (r03, r07: FRONTS' landmarks only)
    if Lj.get('kind') in ('side', 'head_profile'):
        to_dq, _, _ = _profile_to_dq(spec, pid, ax)
        dl = (to_dq(np.asarray(ir[:2], float))[0] - ax['c'][:2]) / Re
        g = np.array([dl[0], dl[1], np.sqrt(max(1.0 - float(dl @ dl), 0.0))])
        off = None
    else:
        L = FRONTS[pid]['landmarks'] if pid in FRONTS else {k: Lj['points'][k] for k in ('eye_R', 'eye_L', 'nose_R',
                                                                                          'nose_L')}
        so = solve_front(dict(landmarks=L), clay)
        c3, r3, u3 = (np.asarray(v_, float) for v_ in so['cam'])
        cg = ax['c'] * np.array([1.0, 1.0, sx])
        gi = np.array(project_front(so['cam'], cg[0], cg[1], cg[2], clay['np_mm']))
        dl = (so['to_img'](np.asarray(ir[:2], float)[None])[0] - gi) / Re
        gX = dl[0] * r3 + dl[1] * u3 + np.sqrt(max(1.0 - float(dl @ dl), 0.0)) * c3
        g = np.array([-gX[2], gX[1], gX[0]]) * np.array([1.0, 1.0, sx])
        tc = np.array([-c3[2], c3[1], c3[0]]) * np.array([1.0, 1.0, sx])
        off = float(np.degrees(np.arccos(np.clip(g @ tc, -1.0, 1.0))))
    g /= np.linalg.norm(g)
    return dict(g=g, elev=float(np.degrees(np.arcsin(g[1]))), out=float(np.degrees(np.arctan2(g[2], -g[0]))),
                theta=gaze_turn(ax, g), cam=off, delta=gaze_slide(ax, g))


def gaze_slide(ax, g):
    """W2r: the cornea's move ALONG the canthus axis from the rest gaze's (mm: R (g - g_rest) . a; + toward the lateral
    canthus): what the horizontal follow (GAZE slide) slides the lids' shapes by"""
    g0 = np.asarray(GAZE['rest'], float)
    g0 = g0 / np.linalg.norm(g0)
    g = np.asarray(g, float)
    return float(ax['R'] * ((g / np.linalg.norm(g) - g0) @ ax['a']))


def slide_taper(ax, s):
    """W2r: the horizontal follow's weight along the axis (GAZE slide_taper): 0 at each canthus easing to 1 over its own
    distances, longer than the vertical follow's taper: the rest upper lid rises ~10-16 deg per mm out of the medial
    canthus (s -14 .. -10), so a slide there turned the corner's ramp itself (w02 _w2r2: the upper lid's medial third
    folded over its margin at w12 R's gaze, the inner canthus hidden from w07 R)"""
    t_m, t_l = GAZE.get('slide_taper', (GAZE.get('taper_medial', GAZE['taper']), GAZE['taper']))
    sm_, sl_ = ax['cyl_canthi']['medial'][0], ax['cyl_canthi']['lateral'][0]
    t_ = np.clip(np.minimum((np.asarray(s, float) - sm_) / t_m, (sl_ - np.asarray(s, float)) / t_l), 0.0, 1.0)
    return t_ * t_ * (3.0 - 2.0 * t_)


def warp_anchor(ax):
    """W2s: the horizontal follow's anchor (warp mode): the rest cornea's place along the canthus axis (mm, R g_rest . a),
    kept GAZE warp_margin inside each canthus; with the canthi's s: (s_medial, s_anchor, s_lateral, margin)"""
    g0 = np.asarray(GAZE['rest'], float)
    g0 = g0 / np.linalg.norm(g0)
    sm_, sl_ = ax['cyl_canthi']['medial'][0], ax['cyl_canthi']['lateral'][0]
    mg = float(GAZE.get('warp_margin', 3.0))
    return sm_, float(np.clip(ax['R'] * (g0 @ ax['a']), sm_ + mg, sl_ - mg)), sl_, mg


def gaze_warp(ax, s, D, k):
    """W2s (the lead's call 2, the almond): THE HORIZONTAL FOLLOW AS A WARP of the lid's place along the canthus axis: the
    posed place of a rest point at s (mm) when the cornea has moved D mm along the axis from the rest gaze's: a monotone
    PCHIP map through the canthi (held) and the rest cornea's place (warp_anchor) moved k D (clipped warp_margin inside
    the canthi); identity outside the canthi. The W2r slide (s - k D w(s), w the slide taper) folds the lid along s once
    k D w' > 1, so w11's D 15-18 mm could not take the slide the photos ask for (check_w2s gaze_probe: k 1.0 printed the
    upper lid below its corner line at t 0.2-0.3 from the side); the warp keeps every order"""
    return warp_s(s, D, k, warp_anchor(ax))


def warp_s(s, D, k, anchor):
    """W2s: gaze_warp on given anchor data (warp_anchor's (s_medial, s_anchor, s_lateral, margin); canid_cage's cache
    keeps them as eye_rig_warp)"""
    from scipy.interpolate import PchipInterpolator
    s = np.asarray(s, float)
    sm_, sa_, sl_, mg = (float(v) for v in anchor)
    sb_ = float(np.clip(sa_ + k * D, sm_ + mg, sl_ - mg))
    if abs(sb_ - sa_) < 1e-9:
        return s.copy()
    f_ = PchipInterpolator([sm_, sa_, sl_], [sm_, sb_, sl_])
    inside = (s > sm_) & (s < sl_)
    out = s.copy()
    out[inside] = f_(s[inside])
    return out


def lid_unwarp(ax, S_, ph, D, k):
    """W2s: a lid's phi on the axis' samples S_ read at the photo's gaze, the warp undone (gaze_warp: the rest sample at s
    appears at gaze_warp(s) in the photo), resampled on S_ (nan off the lid's reach)"""
    ok = np.isfinite(ph)
    if k == 0.0 or D == 0.0 or ok.sum() < 2:
        return np.asarray(ph, float).copy()
    return np.interp(gaze_warp(ax, S_, D, k), S_[ok], np.asarray(ph, float)[ok], left=np.nan, right=np.nan)


def slide_weight(ax, s):
    """W2s: the horizontal follow's weight along the axis for the cage's rig: slide_taper in GAZE slide_mode 'taper'
    (W2r), 1 in 'warp' (the warp holds the canthi itself; a taper on top would undo it near the corners)"""
    if GAZE.get('slide_mode', 'taper') == 'warp':
        return np.ones_like(np.asarray(s, float))
    return slide_taper(ax, s)


def lid_slide(S_, ph, D, k, w):
    """W2r: a lid's phi on the axis' samples S_ with its shape slid BACK by k D w(s) mm (the sample at s came from the
    rest's s - k D w(s)): the horizontal follow undone, resampled on S_ (nan off the lid's reach)"""
    ok = np.isfinite(ph)
    if k == 0.0 or D == 0.0 or ok.sum() < 2:
        return np.asarray(ph, float).copy()
    s_rest = S_ - k * D * w
    o = np.argsort(s_rest[ok])
    return np.interp(S_, s_rest[ok][o], np.asarray(ph, float)[ok][o], left=np.nan, right=np.nan)


def profile_lids(spec, pid, ax):
    """W2q: a head profile's traced lids (lm_<pid>.json eye_fissure, split at its lateral canthus) in the canthus axis'
    cylinder: at each s over the ball (|s| <= Rl - 1.6) the phi where the lid sphere's circle at s, seen along x, crosses
    the traced lid on its camera-side half (x >= the globe's centre - 2 mm), the crossing nearest phi 0. Returns
    {'upper', 'lower': (s (k,), phi (k,))}"""
    to_dq, _, Lj = _profile_to_dq(spec, pid, ax)
    poly = np.asarray(Lj['outlines']['eye_fissure'], float)
    k_lat = int(np.argmin(np.linalg.norm(poly - np.asarray(Lj['points']['canthus_lat'], float), axis=1)))
    curves = dict(upper=to_dq(poly[:k_lat + 1]), lower=to_dq(np.vstack([poly[k_lat:], poly[:1]])))
    Rl = ax['Rl']
    phs = np.linspace(-120.0, 120.0, 481)
    cs, sn = np.cos(np.radians(phs)), np.sin(np.radians(phs))
    out = {}
    for key, Cv in curves.items():
        ss, pp = [], []
        for s0 in np.arange(-(Rl - 1.6), Rl - 1.6 + 1e-9, 0.5):
            rho = np.sqrt(max(Rl * Rl - s0 * s0, 0.0))
            Pc = ax['c'][None] + s0 * ax['a'][None] + rho * (cs[:, None] * ax['no'][None] + sn[:, None] * ax['nv'][None])
            front = (Pc[:, 2] - ax['c'][2]) > -2.0
            A2, B2 = Pc[:-1, :2], Pc[1:, :2]
            hs = []
            for q0, q1 in zip(Cv[:-1], Cv[1:]):
                r_ = B2 - A2
                s_ = q1 - q0
                den = r_[:, 0] * s_[1] - r_[:, 1] * s_[0]
                ok = np.abs(den) > 1e-12
                with np.errstate(divide='ignore', invalid='ignore'):
                    t_ = ((q0 - A2)[:, 0] * s_[1] - (q0 - A2)[:, 1] * s_[0]) / den
                    u_ = ((q0 - A2)[:, 0] * r_[:, 1] - (q0 - A2)[:, 1] * r_[:, 0]) / den
                hit = ok & (t_ >= 0) & (t_ <= 1) & (u_ >= 0) & (u_ <= 1) & front[:-1] & front[1:]
                hs += list(phs[:-1][hit] + t_[hit] * (phs[1] - phs[0]))
            if hs:
                ss.append(s0)
                pp.append(hs[int(np.argmin(np.abs(hs)))])
        out[key] = (np.array(ss), np.array(pp))
    return out


def _gaze_key(spec, face):
    prof_ = tuple(GAZE.get('profiles', ('w11', 'w01')))
    return cache_key(dict(lm=_eye_landmark_key(spec), face=face, gaze=GAZE, iris=EYE_IRIS, canthi=CANTHI,
                          prof={p: _photo_lm(p)['outlines'].get('eye_fissure') for p in prof_},
                          prof_c={p: [_photo_lm(p)['points'][k] for k in ('canthus_med', 'canthus_lat')]
                                  for p in prof_}))


def lid_follow(spec, clay=None, face=None, log=None):
    """W2q: THE LID-FOLLOW MODEL FITTED FROM THE PHOTOS and THE REST LIDS solved jointly under it (the module's W2q note).
    Each front photo eye's loop (traced_fissure's face rule, loops3: its rays on the lid sphere, its corners on the face
    at the profile-rule canthi) and each head profile's traced lids (profile_lids) read in the canthus axis' cylinder,
    each photo eye's gaze from its iris (photo_gaze). The follow ratio of each lid: the slope of phi(s) on theta over the
    photos, one intercept per s, over |s| <= GAZE mid (where w(s) = 1): first on the same wolf at two gazes (GAZE pair),
    then on GAZE fit (used). The rest lids: each photo's phi(s) turned back by f (theta - theta_rest) w(s), averaged
    over GAZE rest_from at each s (the profiles where they reach), rho from the fronts' loops (which run onto the face to
    the canthi), smoothed along s (GAZE smooth), the canthi kept. Returns dict(f_upper, f_lower, pair (upper, lower),
    theta {photo eye: deg}, theta_rest, gaze {photo eye: photo_gaze}, s (k,), rest {'upper', 'lower': (rho, phi)},
    loop (2 n, 3) the rest margin from the medial canthus over the upper lid (index n the lateral canthus), env (2 n, 3)
    the same posed at the largest fitted gaze, poly0 (2 n, 2) / h0 (2 n,) in the lid frame's chart, ax, spread
    {lid: deg rms of the turned-back photos about the rest at |s| <= mid}), cached in the process"""
    key = _gaze_key(spec, face)
    if key in _GAZE:
        return _GAZE[key]
    say_ = log or (lambda s_: None)
    clay = clay_points(spec) if clay is None else clay
    ax = lid_axis(spec, clay)
    n = GAZE['n']
    _, _, _, L3 = traced_fissure(spec, n=n, clay=clay, pin=False, face=face, loops3=True)
    (sm_, rm_, pm_), (sl_, rl_, pl_) = ax['cyl_canthi']['medial'], ax['cyl_canthi']['lateral']
    S_ = np.linspace(sm_, sl_, GAZE['n_s'])
    th0 = gaze_turn(ax, np.asarray(GAZE['rest'], float) / np.linalg.norm(GAZE['rest']))
    data = {'upper': {}, 'lower': {}}      # photo eye -> (rho (k,), phi (k,)) on S_ (nan off its reach)
    theta, gz = {}, {}
    for k_, P in L3.items():
        pid, sd = k_.split('_')
        if pid not in EYE_IRIS or sd not in EYE_IRIS[pid]:
            continue
        up_ = np.vstack([P[:n], P[n:n + 1]])
        lo_ = np.vstack([P[n:], P[:1]])
        for lid, Q in (('upper', up_), ('lower', lo_)):
            s_, r_, p_ = cyl(ax, Q)
            o_ = np.argsort(s_)
            s_, r_, p_ = s_[o_], r_[o_], np.unwrap(np.radians(p_[o_]))
            data[lid][k_] = (np.interp(S_, s_, r_), np.degrees(np.interp(S_, s_, p_)))
        gz[k_] = photo_gaze(spec, pid, sd, clay, ax)
        theta[k_] = gz[k_]['theta']
    for pid in GAZE.get('profiles', ('w11', 'w01')):
        sd = 'L' if 'L' in EYE_IRIS[pid] else 'R'
        k_ = f'{pid}_{sd}'
        pl = profile_lids(spec, pid, ax)
        for lid in ('upper', 'lower'):
            s_, p_ = pl[lid]
            ok_ = (S_ >= s_.min()) & (S_ <= s_.max()) if len(s_) > 1 else np.zeros(len(S_), bool)
            ph_ = np.where(ok_, np.interp(S_, s_, p_) if len(s_) > 1 else np.nan, np.nan)
            rh_ = np.sqrt(np.maximum(ax['Rl'] ** 2 - S_ * S_, 0.0))
            data[lid][k_] = (np.where(ok_, rh_, np.nan), ph_)
        gz[k_] = photo_gaze(spec, pid, sd, clay, ax)
        theta[k_] = gz[k_]['theta']
    w_ = lid_taper(ax, S_)
    mid = np.abs(S_) <= GAZE['mid']
    # W2r: THE HORIZONTAL FOLLOW undone before the fit (the module's W2r note): each photo eye's lid shape slid back by
    # GAZE slide x its cornea's move along the axis (gaze_slide) x the taper, so the vertical follow and the rest lids
    # are fitted on lids whose corneas stand where the rest gaze's does
    k_sl = dict(zip(('upper', 'lower'), (float(v) for v in GAZE.get('slide', (0.0, 0.0)))))
    D_ = {k: float(gz[k].get('delta', 0.0)) for k in gz}
    ws_ = slide_taper(ax, S_)
    warp_ = GAZE.get('slide_mode', 'taper') == 'warp'
    if warp_:
        # W2s: the horizontal follow undone by its WARP (gaze_warp; the module's W2s note)
        ph_ = {lid: {k: lid_unwarp(ax, S_, data[lid][k][1], D_[k], k_sl[lid]) for k in data[lid]} for lid in data}
    else:
        ph_ = {lid: {k: lid_slide(S_, data[lid][k][1], D_[k], k_sl[lid], ws_) for k in data[lid]} for lid in data}

    def slope(keys, lid):
        X_, Y_ = [], []
        for j in np.nonzero(mid)[0]:
            ys = np.array([ph_[lid][k][j] for k in keys])
            ts = np.array([theta[k] for k in keys])
            ok = np.isfinite(ys)
            if ok.sum() >= 2 and np.ptp(ts[ok]) > 1.0:
                X_.append(ts[ok] - ts[ok].mean())
                Y_.append(ys[ok] - ys[ok].mean())
        X_, Y_ = np.concatenate(X_), np.concatenate(Y_)
        return float(X_ @ Y_ / (X_ @ X_))

    def keys_of(pids):
        return [k for k in data['upper'] if k.split('_')[0] in pids]

    # the pair: the same wolf's two eyes at one gaze against its profile (the mean of w12's eyes as one sample per s)
    pair = {}
    for lid in ('upper', 'lower'):
        a_, b_ = GAZE['pair']
        ka, kb = keys_of((a_,)), keys_of((b_,))
        ya = np.nanmean([ph_[lid][k] for k in ka], axis=0)
        yb = np.nanmean([ph_[lid][k] for k in kb], axis=0)
        ta, tb = np.mean([theta[k] for k in ka]), np.mean([theta[k] for k in kb])
        pair[lid] = float(np.nanmean(((ya - yb) / (ta - tb))[mid]))
    f_ = {lid: slope(keys_of(GAZE['fit']), lid) for lid in ('upper', 'lower')}
    rest, spread = {}, {}
    rk_ = keys_of(GAZE['rest_from'])
    front_k = [k for k in rk_ if not _photo_lm(k.split('_')[0]).get('kind') in ('side', 'head_profile')]
    # W2s (the lead's call 2): each photo's weight in the average (GAZE rest_w, by photo id; default 1)
    wr_ = np.array([float(GAZE.get('rest_w', {}).get(k.split('_')[0], 1.0)) for k in rk_])
    for lid in ('upper', 'lower'):
        turned = np.array([ph_[lid][k] - f_[lid] * (theta[k] - th0) * w_ for k in rk_])
        okt = np.isfinite(turned)
        wt_ = np.where(okt, wr_[:, None], 0.0)
        with np.errstate(invalid='ignore', divide='ignore'):
            ph0 = np.where(wt_.sum(0) > 0, np.nansum(np.where(okt, turned, 0.0) * wt_, axis=0) / wt_.sum(0), np.nan)
        spread[lid] = float(np.sqrt(np.nanmean(((turned - ph0[None]) ** 2)[:, mid])))
        rh0 = np.nanmean(np.array([data[lid][k][0] for k in front_k]), axis=0)
        # smoothed along s (gaussian, the ends held at the canthi)
        sig = GAZE['smooth'] / max(float(S_[1] - S_[0]), 1e-9)
        from scipy.ndimage import gaussian_filter1d
        ph0 = gaussian_filter1d(ph0, sig, mode='nearest')
        rh0 = gaussian_filter1d(rh0, sig, mode='nearest')
        eb_ = GAZE.get('end_blend')
        if eb_:
            # W2r (the lead's call 1, "the rest lower lid's lateral end runs into the canthus smoothly (its angle
            # blended toward the canthus's over its last millimetres, rho continuous, never pinned at a last sample)"):
            # each lid's angle and distance about the axis eased onto the canthus's (the two canthi share them: the
            # axis runs parallel to their line) over the last end_blend mm of s, by 1 - (1 - t)^3 (t 0 at the canthus
            # to 1 at end_blend: C2 where it joins the lid, a finite corner angle at the canthus). W2q held the
            # smoothed lids to their last sample and then pinned that sample to the canthus: the lower lid at -58.8 deg
            # / rho 6.83 mm 0.68 mm from the lateral canthus (-57.6 / 5.66), the upper at -49.7 / 4.81
            dm_ = (S_ - sm_) / float(eb_[0])
            dl_ = (sl_ - S_) / float(eb_[1])
            t_ = np.clip(np.minimum(dm_, dl_), 0.0, 1.0)
            b_ = 1.0 - (1.0 - t_) ** 3
            pc_ = np.where(dm_ < dl_, pm_, pl_)
            rc_ = np.where(dm_ < dl_, rm_, rl_)
            ph0 = pc_ + b_ * (ph0 - pc_)
            rh0 = rc_ + b_ * (rh0 - rc_)
        ph0[0], ph0[-1], rh0[0], rh0[-1] = pm_, pl_, rm_, rl_
        rest[lid] = (rh0, ph0)
    # the upper lid stays above the lower inside the corners (at least 2 deg)
    gap = rest['upper'][1] - rest['lower'][1]
    inner = np.arange(len(S_))[1:-1]
    bad = inner[gap[inner] < 2.0]
    if len(bad):
        mid_ph = 0.5 * (rest['upper'][1][bad] + rest['lower'][1][bad])
        rest['upper'][1][bad], rest['lower'][1][bad] = mid_ph + 1.0, mid_ph - 1.0

    def loop_at(dth, D=0.0):
        """the rest lids posed by a gaze turn dth (deg) from the rest and (W2r) slid by the cornea's move D (mm) along
        the axis, resampled n per lid by arc length, as one loop"""
        pts = []
        for lid, rev in (('upper', False), ('lower', True)):
            rh, ph = rest[lid]
            if warp_ and k_sl[lid] and D:
                ph = np.interp(S_, gaze_warp(ax, S_, D, k_sl[lid]), ph)       # (W2s: the rest at s shows at warp(s))
            else:
                ph = np.interp(S_ - k_sl[lid] * D * ws_, S_, ph) if (k_sl[lid] and D) else ph
            P_ = uncyl(ax, S_, rh, ph + f_[lid] * dth * w_)
            P_ = P_[::-1] if rev else P_
            sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P_, axis=0), axis=1))])
            t_ = np.linspace(0.0, sl[-1], n + 1)
            pts.append(np.column_stack([np.interp(t_, sl, P_[:, k]) for k in range(3)])[:-1])
        return np.vstack(pts)
    loop = loop_at(0.0)
    k_max = max(keys_of(GAZE['fit']), key=lambda k: theta[k])
    th_max = theta[k_max]
    env = loop_at(th_max - th0, D_[k_max])
    lf = lid_frame(spec, 'L')
    Dl_ = loop - lf['centre']
    res = dict(f_upper=f_['upper'], f_lower=f_['lower'], pair=(pair['upper'], pair['lower']), theta=theta,
               theta_rest=th0, theta_max=th_max, gaze=gz, s=S_, w=w_, rest=rest, loop=loop, env=env,
               poly0=np.column_stack([Dl_ @ lf['e1'], Dl_ @ lf['ed']]), h0=Dl_ @ lf['oo'], ax=ax, spread=spread,
               data=data, slide=(k_sl['upper'], k_sl['lower']), delta=D_, w_slide=ws_,
               slide_mode='warp' if warp_ else 'taper', warp=warp_anchor(ax), rest_w=dict(zip(rk_, wr_.tolist())))
    say_(f'[gaze] the lids follow the gaze about the canthus axis: upper {f_["upper"]:.2f}, lower {f_["lower"]:.2f} '
         f'(fitted on {", ".join(GAZE["fit"])}; the pair {GAZE["pair"][0]} / {GAZE["pair"][1]} {pair["upper"]:.2f} / '
         f'{pair["lower"]:.2f}); theta (deg): ' + ', '.join(f'{k} {v:+.1f}' for k, v in theta.items())
         + f'; rest {th0:+.1f}; the turned-back photos about the rest lids {spread["upper"]:.1f} / {spread["lower"]:.1f} '
         f'deg rms')
    _GAZE[key] = res
    return res


def pose_points(ax, P, dth_upper, dth_lower, w_upper, w_side=None):
    """W2q: THE LID-FOLLOW POSE of points P (n, 3) of the left eye: each turned about the canthus axis by
    w (dth_upper u + dth_lower (1 - u)) deg (u = w_upper (n,) the point's upper-lid share 0..1, w = w_side (n,) its rig
    weight, default 1): canid_cage.pose_eye's turn (the runtime's lid-follow: dth_lid = f_lid (theta(g) - theta_rest))"""
    P = np.atleast_2d(np.asarray(P, float))
    u = np.broadcast_to(np.asarray(w_upper, float), (len(P),))
    w = np.ones(len(P)) if w_side is None else np.broadcast_to(np.asarray(w_side, float), (len(P),))
    al = np.radians(w * (dth_upper * u + dth_lower * (1.0 - u)))
    D = P - ax['c']
    # Rodrigues about the axis signed so a turn by + al carries n_o toward n_v (+ phi)
    a = ax['a'] if float(np.cross(ax['a'], ax['no']) @ ax['nv']) > 0.0 else -ax['a']
    ca, sa = np.cos(al)[:, None], np.sin(al)[:, None]
    return ax['c'] + D * ca + np.cross(a[None], D) * sa + a[None] * (D @ a)[:, None] * (1.0 - ca)


def eye_members(spec, phi=None, G=None):
    """W2i (the lead's call 3): per eye the FISSURE CUT THROUGH THE LID SHELL ONLY, analytic over the head's grid (exact
    at any scale): a SUBTRACT group of the traced fissure's PRISM along the eye's axis from its equator (a PSWEEP of
    traced_fissure's polygon, its corners drawn out to the photos' canthi by fissure_polygon, rounded STROKES_SKULL eye
    fis_rho), INTERSECTED with the lid's sphere grown band[1], the globe shrunk band[0] SUBTRACTED and held inside the
    globe's outline plus clip (a capsule along the axis), so the cutter is the shell over the globe and no cut opens a
    cavity; past the globe the CANTHAL GROOVES on phi's skin toward the canthi (traced_canthi, groove, groove_end);
    the group's smooth subtraction (cut_kg) rounds the lid margins; then the GLOBES re-added as exact spheres (globe_k).
    phi, G: the closed head's grid (the canthi and the grooves; without it the polygon as traced and no grooves).
    Returns [(kind, (members, k_union, k_group), name)] for canid.build_head; a member ('psweep', ...) as
    nostrils_traced's (op last), ('sphere', centre, radius, op), ('ellip', centre, axes, half, op) or a round cone
    with its op, palate (d, q, x) mm"""
    ey = STROKES_SKULL['eye']
    poly0, _ = traced_fissure(spec)
    can = traced_canthi(spec, phi, G) if phi is not None else None
    groups, globes = [], []
    for side in ('L', 'R'):
        lf = lid_frame(spec, side)
        ce, oo, R_ = lf['centre'], lf['oo'], lf['R']
        # the corners drawn out to the photos' canthi (fissure_polygon): within the radial clip the cut so reaches the
        # eyeball's ends, and past it the canthal grooves below carry the corners on to the canthi themselves
        poly = fissure_polygon(poly0, can, lf, side)
        sgn = 1.0 if lf['e2'] @ lf['ed'] > 0 else -1.0
        sec = np.column_stack([poly[:, 0], sgn * poly[:, 1]])
        if np.sum(sec[:, 0] * np.roll(sec[:, 1], -1) - np.roll(sec[:, 0], -1) * sec[:, 1]) < 0:
            sec = sec[::-1]
        # the prism from `back` mm along the axis (about the globe's equator: the traced fissure reaches ~80 deg off the
        # axis, the photos' canthi at the eyeball's outline; W2i h3-h7 began it at R - 3 mm, so it cut the shell only
        # within ~8 mm of the axis and the eyeball showed over ~17.5 mm of its 24 whatever the corners did)
        P = np.array([ce + ey['back'] * oo, ce + (R_ + ey['lid'][0] + 4.0) * oo])
        ax3 = np.stack([lf['e1'], lf['ed'], oo])
        # the band: the lid surface's ellipsoid grown band[1] (intersected) less the globe shrunk band[0] (subtracted:
        # the cut reaches the globe, re-added after, everywhere the globe lies behind the lid), the whole held inside the
        # globe's outline plus `clip` (a capsule along the axis, intersected), so past the globe no cut can open a pocket
        # (W2i h3's inner ellipsoid stood in front of the globe off the axis: the eyeball over 0.55 of the fissure; h12's
        # radial clip let the drawn-out corners' prism walls stand at the medial corner and the upper lid drop)
        mem = [('psweep', P, sec[None], ey['fis_rho'], np.zeros(2), np.ones(2), lf['e1'], None, None, 'union'),
               ('ellip', ce, ax3, lid_half(R_, ey['band'][1]), 'intersect'),
               ('sphere', ce, R_ - ey['band'][0], 'subtract'),
               ('roundcone', ce - 25.0 * oo, ce + 30.0 * oo, R_ + ey['clip'], R_ + ey['clip'], 0.0, 'intersect')]
        # the CANTHI: grooves ON THE SKIN from where each corner of the polygon leaves the clipped disc (the lid's surface
        # there) toward the photos' canthus (traced_canthi), groove_end of the way, each point snapped onto phi's skin and
        # the groove's sphere set by its half width w and depth g there (radius (w^2 + g^2) / 2 g, its centre r - g under
        # the skin), w and g tapering from groove[0] to groove[1] (mm): the corners' conjunctiva and the commissure, which
        # the photos read their fissures to (W2h-W2i h9's notches ran on the lid's sphere, not the skin)
        if can is not None:
            (w0_, g0_), (w1_, g1_) = ey['groove']
            hl = lid_half(R_, 0.0)
            rc_ = R_ + ey['clip']
            for key_, pick in (('medial', np.argmin), ('lateral', np.argmax)):
                j = int(pick(poly[:, 0]))
                cen2 = poly.mean(0)
                dir2 = poly[j] - cen2
                dir2 /= np.linalg.norm(dir2)
                bq = float(cen2 @ dir2)
                s0 = -bq + np.sqrt(max(bq * bq - float(cen2 @ cen2) + rc_ * rc_, 0.0))
                s0 = min(s0, float(np.linalg.norm(poly[j] - cen2)))
                a2, b2 = cen2 + (s0 - 0.8) * dir2
                z_ = hl[2] * np.sqrt(max(1.0 - (a2 / hl[0]) ** 2 - (b2 / hl[1]) ** 2, 0.0))
                p_a = ce + a2 * lf['e1'] + b2 * lf['ed'] + z_ * oo
                p_b = can[key_] * np.array([1.0, 1.0, 1.0 if side == 'L' else -1.0])
                p_b = p_a + ey['groove_end'] * (p_b - p_a)
                nn_ = max(3, int(np.ceil(np.linalg.norm(p_b - p_a) / 0.8)))
                ch_ = []
                for t_ in np.linspace(0.0, 1.0, nn_ + 1):
                    p_ = p_a + t_ * (p_b - p_a)
                    for _ in range(4):
                        f_ = sample3(phi, G, p_[None])[0]
                        gr = np.array([sample3(phi, G, (p_ + 0.5 * k_)[None])[0] - sample3(phi, G, (p_ - 0.5 * k_)[None])[0]
                                       for k_ in np.eye(3)])
                        nrm_ = gr / max(np.linalg.norm(gr), 1e-9)
                        p_ = p_ - f_ * nrm_
                    w_, g_ = w0_ + t_ * (w1_ - w0_), g0_ + t_ * (g1_ - g0_)
                    r_ = (w_ * w_ + g_ * g_) / (2.0 * g_)
                    ch_.append((p_ - (r_ - g_) * nrm_, r_))
                for (ca_, ra_), (cb_, rb_) in zip(ch_[:-1], ch_[1:]):
                    mem.append(('roundcone', ca_, cb_, ra_, rb_, 0.0, 'union'))
        groups.append(('sub', (mem, 0.0, ey['cut_kg']), f'fissure_{side}'))
        globes.append(('sphere', ce, R_, 'union'))
    return groups + [('union', (globes, 0.0, ey['globe_k']), 'globes')]


def sculpt_skull(phi, G, spec, log=print):
    """W2h: the features on the skin over the skull (STROKES_SKULL): the traced rhinarium, the mouth line, the lid
    fissures and the globes. Returns phi and the curves (palate frame mm)"""
    st = STROKES_SKULL

    def smooth01(t):
        t = np.clip(t, 0.0, 1.0)
        return t * t * (3 - 2 * t)
    out = np.array(phi, np.float32, copy=True)
    curves = {}
    # ---- the rhinarium, unioned with a small k (its border)
    rv = st['rhinarium']
    outline, fr = rhinarium_outline(spec, rv)
    ib = int(round((rv['loft'][1] - G.lo[0]) / G.h))
    near = np.zeros(G.n, bool)
    near[:ib + 1] = True
    ii = np.nonzero(near)
    Pn = np.column_stack([G.d[ii[0]], G.q[ii[1]], G.x[ii[2]]])
    nose_f, s2 = rhinarium(Pn, rv, outline, out[ii])
    # W2h h6: the union's k fades to 0 over the loft's last 12 mm: at loft[1] the nose's field is the skin's own, and a
    # smooth union of a field with itself stands k / 4 proud (h5's step across the muzzle at loft[1])
    kf = rv['k'] * (1.0 - smooth01((Pn[:, 0] - (rv['loft'][1] - 12.0)) / 12.0))
    out[ii] = _smin(out[ii], nose_f, np.maximum(kf, 1e-6))
    # the leather's BORDER: a fine groove along the outline on the nose's front and sides (ahead of the loft's end)
    bd, bs = rv['border']
    gw = np.exp(-0.5 * (s2 / bs) ** 2) * (Pn[:, 0] < rv['loft'][0] + 6.0)
    out[ii] = out[ii] + (bd * gw * (np.abs(out[ii]) < 3.0)).astype(np.float32)
    curves['leather_outline'] = outline
    # ---- the mouth line (sculpt's mouth stroke on this skin)
    band = np.abs(out) < 14.0
    idx = np.nonzero(band)
    P = np.column_stack([G.d[idx[0]], G.q[idx[1]], G.x[idx[2]]])
    ll = np.asarray(LIP_LINE, float)
    mo = st['mouth']
    dd = np.arange(ll[0, 0], ll[-1, 0] + mo['tail'] + 0.1, 1.0)
    qq = np.interp(dd, ll[:, 0], ll[:, 1], right=ll[-1, 1] + 0.15 * (dd[-1] - ll[-1, 0]))
    xs = surface_x(out, G, dd, qq)
    ok = np.isfinite(xs)
    dd, qq, xs = dd[ok], qq[ok], xs[ok] - 0.5
    front = np.array([[ll[0, 0] - 1.5, ll[0, 1] - 0.3, 0.0]])
    left = np.column_stack([dd, qq, xs])
    lip = np.vstack([left[::-1] * [1, 1, -1], front, left])
    curves['mouth_line'] = lip
    r, s = curve_dist(P, lip)
    ends = smooth01(np.minimum(s, 1 - s) * len(lip) / mo['tail'])
    q_line = np.interp(P[:, 0], dd, qq, left=ll[0, 1], right=qq[-1])
    t = P[:, 1] - q_line
    nearm = np.exp(-r ** 2 / (2 * (2.5 * mo['step_w']) ** 2))
    D = ends * (-mo['depth'] * np.exp(-r ** 2 / (2 * mo['sigma'] ** 2))
                + nearm * (mo['step_up'] * np.exp(-((t - mo['step_w']) / mo['step_w']) ** 2)
                           + mo['step_dn'] * np.exp(-((t + mo['step_w']) / mo['step_w']) ** 2)))
    out[idx] = out[idx] - D.astype(np.float32)
    # ---- W2i (the lead's call 3, "THE LIDS ON THE GLOBE: the lid is a shell on the globe (globe radius + lid thickness)
    # blending into the face skin; the fissure ... cut through THE SHELL ONLY"): within the globe's silhouette along its
    # axis (seat[0] mm beyond it, faded over seat[1]) and in front of the plane 8 mm behind its centre (the front cameras
    # look ~27 deg off the eye's axis), the skin drawn onto the globe offset by the lids' thickness (lid[0]: the skin,
    # the orbicularis, the tarsus); the fissure is cut through that shell and the globe re-added by the analytic members
    # (eye_members: the traced fissure's prism intersected with the shell's band), exact at any scale. W2h cut a lens
    # prism through the grid's skin 8 mm behind the globe's centre: its flat side wall and hooked fold showed medially
    ey = st['eye']
    phi0 = out.copy()
    thick = ey['lid'][0]
    # the seat over traced_fissure's own polygon (W2i h12 seated over the corners drawn out to the canthi too: the upper
    # lid dropped over the globe and the lateral corner flicked up; the corners are the cut's and the grooves' alone)
    fpoly, _ = traced_fissure(spec)
    fimg = poly_sdf_image(fpoly, fpoly.min(0) - 30.0, fpoly.max(0) + 30.0, 0.2)
    for side in ('L', 'R'):
        ef = eye_frame(spec, side)
        lf = lid_frame(spec, side)
        reach = ef['r_globe'] + ey['ext'] + ey['reach']
        sl = tuple(slice(max(0, int((ef['centre'][a] - reach - G.lo[a]) / G.h)),
                         min(G.n[a], int((ef['centre'][a] + reach - G.lo[a]) / G.h) + 1)) for a in range(3))
        Dg, Qg, Xg = np.meshgrid(G.d[sl[0]], G.q[sl[1]], G.x[sl[2]], indexing='ij')
        Pe = np.stack([Dg, Qg, Xg], -1).reshape(-1, 3)
        W_ = Pe - ef['centre']
        ax_ = W_ @ ef['oo']
        # the LID SURFACE: an oblate ellipsoid round the globe, its axial semi-axis the globe's radius plus the lids'
        # thickness, its others `ext` mm wider, so near the axis it is the globe offset by the lid and past the globe's
        # outline it runs on under the canthi (a sphere's band there cut a pocket into the face's skin: W2i h2)
        E_lid = ellipsoid_sd(Pe, ef['centre'], np.stack([lf['e1'], lf['ed'], lf['oo']]), lid_half(ef['r_globe'], 0.0))
        # seated within seat[0] mm of the traced fissure (in the plane across the eye's axis), faded over seat[1], in
        # front of the plane 4 mm behind the globe's centre, out to the clip past the globe's outline
        s2 = sample2(*fimg, W_ @ lf['e1'], W_ @ lf['ed'])
        rad = np.linalg.norm(W_ - ax_[:, None] * ef['oo'][None], axis=1)
        # out past the lid's sphere along the axis the seat FLARES (its footprint and its radius grow `flare` mm per mm
        # out) and FADES (full to out[0] mm past the lid, gone by out[0] + out[1]): where the face stands in front of the
        # lid (the zygomatic arch's skin before the eye's lower lateral quarter: the SPEC's globe sits ~7 mm caudal and
        # ~3 mm ventral of the skull's orbit landmarks) the seat carves a crater sloping up into the cheek, not a channel
        # along the axis ending at this slice box's face (W2i h8: the box's face stood as a flat ledge under the eye)
        ax_lid = np.sqrt(np.maximum((ef['r_globe'] + thick) ** 2 - rad ** 2, 0.0))
        past = np.maximum(ax_ - ax_lid, 0.0)
        fl_, (o0_, o1_) = ey['flare'], ey['out']
        w_ = smooth01((ey['seat'][0] + fl_ * past - s2) / ey['seat'][1]) * smooth01((ax_ + 4.0) / 4.0) * \
            smooth01((ef['r_globe'] + ey['clip'] + 1.0 + fl_ * past - rad) / 2.5) * smooth01((o0_ + o1_ - past) / o1_)
        cur = phi0[sl].ravel()
        cur = (1.0 - w_) * cur + w_ * E_lid
        out[sl] = cur.reshape(Dg.shape).astype(np.float32)
        curves[f'eye_{side}'] = dict(centre=ef['centre'], u=ef['uu'], v=ef['vv'], o=ef['oo'],
                                     cornea=ef['centre'] + ef['r_globe'] * ef['oo'], depth=np.array([thick]))
    log(f'[hull] W2i sculpt on the skin over the skull: the rhinarium traced on w12 (x {rv["scale"]:.2f}, front falling '
        f'back {rv["flat"]:.1f} mm, its underside into the lip by d {rv.get("loft_bot", (0, 0, rv["loft"][1]))[2]:.0f}), the '
        f'mouth line ({len(lip)} points), the lids a {thick:.1f} mm shell on the globes (the fissures analytic)')
    return out, curves


def blend_behind(skin, flow, G):
    """W2h: the skin over the skull ahead of STROKES_SKULL blend[0], the flowed head (the visual hull's) behind blend[1],
    their fields interpolated (smoothstep) between"""
    d0, d1 = STROKES_SKULL['blend']
    t = np.clip((G.d - d0) / (d1 - d0), 0.0, 1.0)
    w = (t * t * (3 - 2 * t))[:, None, None].astype(np.float32)
    return ((1.0 - w) * skin + w * flow).astype(np.float32)


# ============================================================================================ the nose (analytic, W2g)
def _skin_frame(phi, G, S):
    """the outward unit normal of phi at S (d, q, x) mm (central differences, 0.5 mm)"""
    e = 0.5
    g = np.array([sample3(phi, G, (S + e * k)[None])[0] - sample3(phi, G, (S - e * k)[None])[0] for k in np.eye(3)])
    return g / max(np.linalg.norm(g), 1e-9)


def _chain(C, R, step, k=0.0):
    """a smooth TUBE through control points C (n, 3) with radii R (n,): the curve PCHIP-interpolated by arclength and
    resampled every `step` mm, consecutive round cones sharing their end spheres (a hard union of such a chain is one
    tube, C1 at the joints; W2f's few cones with a smooth union printed beads). Members ('roundcone', a, b, r1, r2, k)"""
    from scipy.interpolate import PchipInterpolator
    C, R = np.asarray(C, float), np.asarray(R, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    n = max(2, int(np.ceil(s[-1] / step)) + 1)
    t = np.linspace(0.0, s[-1], n)
    P = np.column_stack([PchipInterpolator(s, C[:, a])(t) for a in range(3)])
    r = PchipInterpolator(s, R)(t)
    return [('roundcone', P[i], P[i + 1], float(r[i]), float(r[i + 1]), k) for i in range(n - 1)]


def nose_members(phi, G, hn, lv=None):
    """W2g (the lead's call 3: "the nostrils dark COMMAS: deep canals turning laterally under THICK rolled alar folds
    ..., spaced at the photo's 0.50 of the leather's width; the philtrum a real GROOVE splitting the upper lip; the
    leather ... with a defined BORDER where it meets the haired skin"), the nose's fine forms as ANALYTIC members over
    the head's grid (exact at any scale; the 1 mm grid printed W2f's lobes as beads and its openings as lit dishes):
      the ALAE (a UNION group before the openings are cut): per side a thick roll round the opening's dorsal and lateral
          rim, a chain of round cones through hn['ala'] rows (angle deg from lateral toward dorsal round the opening's
          centre in the skin's tangent plane, in-plane radius mm, the axis' height over the skin mm (negative: under it),
          the roll's radius mm), each axis point found on the skin under its in-plane place; the roll's inner side
          overhangs the opening (w12: the pale rim of the C over each opening's top and lateral side, NOSE_W12 ala)
      the OPENINGS (SUBTRACT): per side the CANAL, a chain of round cones from outside the skin in through the opening and
          turning laterally and dorsally under the ala (hn['canal'] rows (along the outward normal, lateral, dorsal, r)
          mm from the opening's skin centre), and the ALAR SLIT, the comma's tail out and down under the ala's lower end
          (hn['slit'] rows alike); the PHILTRUM, a groove on the midline from between the openings down the leather and
          through the upper lip to its margin (hn['philtrum']: q the skin points' heights from top to bottom, r the
          cone's radius, groove its depth under the skin), splitting the lip; the BORDER, a narrow groove round the
          leather's outline on the skin (lv pad_outline about pad_centre_q, |x| x pad_scale_x; hn['border'] (radius,
          depth))
    The opening's centre S: the leather's front skin at hn (q, x) (the place w12's traced naris centre lands through its
    solved camera, W2f nares_place). Returns (union members, k_union, k_group), (subtract members, k_union, k_group);
    a member ('roundcone', a, b, r1, r2) in (d, q, x) mm"""
    lv = STROKES['leather'] if lv is None else lv
    ala_m, sub_m = [], []
    step = hn.get('step', 1.5)
    for sx in (1.0, -1.0):
        S = surface_along(phi, G, np.array([[20.0, hn['q'], sx * hn['x']]]), np.array([[-1.0, 0.0, 0.0]]),
                          reach=34.0)[0]
        n = _skin_frame(phi, G, S)
        lat = np.array([0.0, 0.0, sx]) - (np.array([0.0, 0.0, sx]) @ n) * n
        lat /= np.linalg.norm(lat)
        dor = np.cross(n, lat)
        dor *= np.sign(dor[1]) if dor[1] != 0 else 1.0
        C, R = [], []
        for ang, rho, hgt, rr in hn['ala']:
            a = np.radians(ang)
            Pp = S + rho * (np.cos(a) * lat + np.sin(a) * dor)
            Q = surface_along(phi, G, (Pp - 5.0 * n)[None], n[None], reach=14.0)[0]
            C.append(Q + hgt * _skin_frame(phi, G, Q))
            R.append(rr)
        ala_m += _chain(C, R, step, hn.get('ala_k', 0.0))
        dv_ = None
        if 'canal_dir' in hn:
            # W2h: the CANAL straight along a direction in the palate frame (d, q, x; x mirrored per side), w12's line of
            # sight into the head: through the opening the camera sees the canal's far end, deep and shadowed (the
            # canal in the skin's frame ran across that line on the traced rhinarium and showed its lit walls)
            dv_ = np.asarray(hn['canal_dir'], float) * np.array([1.0, 1.0, sx])
            dv_ /= np.linalg.norm(dv_)
            ss_ = np.linspace(-2.0, hn['canal_len'], 7)
            sub_m += _chain(S[None] + ss_[:, None] * dv_[None],
                            np.interp(ss_, [ss_[0], ss_[-1]], list(hn['canal_r'])), step, 0.0)
        if 'mouth' in hn:
            # the opening's MOUTH, an ellipsoid wider than tall (w12's openings 11.3 x 8.15 mm), its lateral end turned
            # down by tilt, its long axis INTO the head along the canal's first leg (the canal's first two rows): (along
            # n, lateral, dorsal of its centre, half lateral, half dorsal, half along the canal, tilt deg)
            o_, l_, u_, hl_, hd_, hn_, tl_ = hn['mouth']
            if dv_ is not None:
                ax = dv_.copy()
            else:
                c0, c1 = np.asarray(hn['canal'][0][:3], float), np.asarray(hn['canal'][1][:3], float)
                ax = (c1 - c0) @ np.stack([n, lat, dor])
                ax /= np.linalg.norm(ax)
            e1 = lat - (lat @ ax) * ax
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(ax, e1)
            e2 *= np.sign(e2 @ dor) if e2 @ dor != 0 else 1.0
            th = np.radians(tl_)
            e1, e2 = np.cos(th) * e1 - np.sin(th) * e2, np.sin(th) * e1 + np.cos(th) * e2
            sub_m.append(('ellipsoid', S + o_ * n + l_ * lat + u_ * dor, np.stack([e1, e2, -ax]),
                          np.array([hl_, hd_, hn_], float)))
        for key in (('slit',) if dv_ is not None else ('canal', 'slit')):
            rows = np.asarray(hn[key], float)
            C = S[None] + rows[:, :1] * n[None] + rows[:, 1:2] * lat[None] + rows[:, 2:3] * dor[None]
            sub_m += _chain(C, rows[:, 3], step, 0.0 if key == 'canal' else hn['slit_k'])
    # the philtrum on the midline: each row's skin point found from in front along +d at (q, x 0), the axis depth under it
    ph = hn['philtrum']
    P_, R_ = [], []
    t = np.arange(0.0, 45.0, 0.1)
    nq = len(ph['q'])
    rr_ = np.broadcast_to(np.asarray(ph['r'], float), (nq,))          # per row (the groove widening down the lip)
    gg_ = np.broadcast_to(np.asarray(ph['groove'], float), (nq,))
    for q_, r_, g_ in zip(ph['q'], rr_, gg_):
        # the first inside sample marching +d from in front (surface_along finds exits, not entries)
        f = sample3(phi, G, np.column_stack([-12.0 + t, np.full_like(t, q_), np.zeros_like(t)]))
        j = int(np.argmax(f < 0))
        if f[j] < 0 and j > 0:
            Sm = np.array([-12.0 + t[j - 1] + 0.1 * f[j - 1] / (f[j - 1] - f[j]), q_, 0.0])
            P_.append(Sm + (r_ - g_) * _skin_frame(phi, G, Sm))
            R_.append(r_)
    if len(P_) >= 2:
        sub_m += _chain(P_, R_, ph.get('step', 1.0), 0.0)
    # the leather's border: round the pad's outline on the skin (from in front along +d at each outline point's (q, x))
    if 'border' in hn:
        # the lateral and ventral margin only (the outline below q_max: the leather's top rolls onto the bridge with no
        # edge), an open curve from the left side round the bottom to the right
        rb_, db_, qmax_ = hn['border']
        half = np.asarray(lv['pad_outline'], float)
        sc = lv.get('pad_scale_x', 1.0)
        ring = np.vstack([np.column_stack([half[:, 0] * sc, lv['pad_centre_q'] + half[:, 1]]),
                          np.column_stack([-half[-2:0:-1, 0] * sc, lv['pad_centre_q'] + half[-2:0:-1, 1]])])
        ring = resample_closed(ring, 1.0)
        ring = np.roll(ring, -int(np.argmax(ring[:, 1])), axis=0)          # start at the top middle
        keep = ring[:, 1] <= qmax_
        B = []
        for x_, q_ in ring[keep]:
            f = sample3(phi, G, np.column_stack([-12.0 + t, np.full_like(t, q_), np.full_like(t, x_)]))
            j = int(np.argmax(f < 0))
            if f[j] < 0 and j > 0:
                Sb = np.array([-12.0 + t[j - 1] + 0.1 * f[j - 1] / (f[j - 1] - f[j]), q_, x_])
                B.append(Sb + (rb_ - db_) * _skin_frame(phi, G, Sb))
        if len(B) >= 2:
            sub_m += _chain(B, np.full(len(B), float(rb_)), hn.get('border_step', 2.0), 0.0)
    return (ala_m, hn.get('ala_k', 0.0), hn.get('ala_kg', 0.8)), (sub_m, hn['slit_k'], hn['k'])


# ============================================================================================ the traced nostrils (W2i)
def traced_nostril():
    """W2i: w12's traced nostril (NOSE_W12 open_*, fold_in_*, fold_out_*) as the image-RIGHT one (the creature's left,
    +x), photo px: the image-left tracing mirrored about the leather's axis and averaged with it (the opening resampled
    by angle about its centroid, the fold's edges by arclength). Returns dict(opening (72, 2), fold_in (24, 2),
    fold_out (24, 2))"""
    nw = NOSE_W12
    ax2 = 2.0 * nw['axis']

    def ring(P, n=72):
        P = np.asarray(P, float)
        c = P.mean(0)
        a = np.unwrap(np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]))
        a = np.concatenate([a, a[:1] + 2 * np.pi])
        rr = np.concatenate([np.linalg.norm(P - c, axis=1), [np.linalg.norm(P[0] - c)]])
        if a[-1] < a[0]:
            a, rr = a[::-1], rr[::-1]
        t = np.linspace(a[0], a[0] + 2 * np.pi, n, endpoint=False)
        r_ = np.interp(t, a, rr)
        return c, t, r_

    def curve(P, n=24):
        P = np.asarray(P, float)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        t = np.linspace(0.0, s[-1], n)
        return np.column_stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])])
    mir = lambda P: np.column_stack([ax2 - np.asarray(P, float)[:, 0], np.asarray(P, float)[:, 1]])
    c1, t1, r1 = ring(nw['open_r'])
    c2, t2, r2 = ring(mir(nw['open_l'])[::-1])
    c = 0.5 * (c1 + c2)
    t = np.linspace(-np.pi, np.pi, 72, endpoint=False)
    rr = 0.5 * (np.interp(t, t1 - 2 * np.pi * np.floor((t1 + np.pi) / (2 * np.pi)), r1, period=2 * np.pi)
                + np.interp(t, t2 - 2 * np.pi * np.floor((t2 + np.pi) / (2 * np.pi)), r2, period=2 * np.pi))
    opening = c + rr[:, None] * np.column_stack([np.cos(t), np.sin(t)])
    fi = 0.5 * (curve(nw['fold_in_r']) + curve(mir(nw['fold_in_l'])))
    fo = 0.5 * (curve(nw['fold_out_r']) + curve(mir(nw['fold_out_l'])))
    # the DARK core (the canal's mouth under the fold) averaged alike
    d1, td1, rd1 = ring(nw['dark_r'])
    d2, td2, rd2 = ring(mir(nw['dark_l'])[::-1])
    dc = 0.5 * (d1 + d2)
    rr_d = 0.5 * (np.interp(t, td1 - 2 * np.pi * np.floor((td1 + np.pi) / (2 * np.pi)), rd1, period=2 * np.pi)
                  + np.interp(t, td2 - 2 * np.pi * np.floor((td2 + np.pi) / (2 * np.pi)), rd2, period=2 * np.pi))
    dark = dc + rr_d[:, None] * np.column_stack([np.cos(t), np.sin(t)])
    return dict(opening=opening, fold_in=fi, fold_out=fo, centre=c, dark=dark, dark_centre=dc)


def nostrils_traced(phi, G, hn, spec):
    """W2i (the lead's call 2): THE NOSTRILS FROM w12's TRACINGS (traced_nostril), carried onto the closed head's
    leather through w12's solved camera (nose_frame, on_skin_w12) and mirrored for the creature's right:
      OPENING  (SUBTRACT) a PSWEEP of the traced outline: its section the traced loop on the skin seen in the skin's
               tangent frame at its centre; from hn opening 'out' mm outside the skin straight in along the inward
               normal (key 0, the traced outline, at the skin), widening by 'under' mm toward the fold's side over the
               vestibule's first mm (key 1: the vestibule under the overhanging fold) to 'vest' mm in, then the CANAL
               turning UP and BACK (toward 'turn' deg up from the palate's back direction) on an arc of 'arc_r' mm and
               running on 'canal' mm, its section shrinking to 'end_scale'; corners rounded 'rho' mm. From every front
               camera the canal's end turns out of sight behind the fold and the opening's top: its visible inside is the
               vestibule's walls under the fold, deep and occluded
      FOLD     (UNION, before the openings) the ALAR FOLD: a roll along the traced fold's crest (midway between its
               inner and outer edges), its radius half their distance on the skin (clamped 'fold_r'), its axis 'fold_h'
               mm along the normal from the skin: rolled over the opening's top and lateral side
      SLIT     (SUBTRACT) the comma's tail run on as a groove from the opening's lateral end BACK along the leather's
               side and up ('slit': length, rise per mm, radii, sink), as the profile photos show it (w10, w11: the dark
               slit sweeping back near the leather's lateral border)
      PHILTRUM (SUBTRACT) hn philtrum's chain, as nose_members
    Returns (union members, k_union, k_group), (subtract members, k_union, k_group); a 'psweep' member is ('psweep', P
    (N, 3) centreline, sections (2, M, 2) mm, rho, keys (N,), scale (N,), start normal (3,), rim (M, 3) the traced loop
    on the skin, surface samples (n, 3) for the measures), all palate (d, q, x) mm"""
    tr = traced_nostril()
    fr = nose_frame(spec)
    u_ax = fr['u_ax']
    op = hn['opening']
    fold_m, sub_m = [], []
    for sx in (1.0, -1.0):
        def to_img(P):
            W = fr['to_leather'](np.asarray(P, float))
            if sx < 0:
                W = np.column_stack([2.0 * u_ax - W[:, 0], W[:, 1]])
            return W
        # every member's entry runs along w12's LINE OF SIGHT, so its outline in w12's camera is the traced one exactly
        # (the leather's front faces ~55 deg off that line: the outline back-projected along the skin's normal stood 16
        # mm tall)
        cr_, rr_, ur_ = (np.asarray(a, float) for a in fr['cam'])
        dirc = np.array([-cr_[2], cr_[1], cr_[0]])         # toward the camera, palate (d, q, x)
        rdq = np.array([-rr_[2], rr_[1], rr_[0]])          # image right
        udq = np.array([-ur_[2], ur_[1], ur_[0]])          # image up
        tin = -dirc
        e1 = rdq - (rdq @ tin) * tin
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(tin, e1)
        th = np.radians(op['turn'])
        tend = np.cos(th) * np.array([1.0, 0.0, 0.0]) + np.sin(th) * np.array([0.0, 1.0, 0.0])
        fold_dir = np.array([sx * np.sign(e1 @ rdq), np.sign(e2 @ udq)])
        fold_dir /= np.linalg.norm(fold_dir)

        def sweep(Wpoly, Wc, depth, depth_scale, under, turn=True, Wpoly1=None):
            """a PSWEEP of an image-plane polygon (image mm) about its centre Wc: from op out mm outside the skin in along
            the line of sight to `depth` mm past it (the scale falling to depth_scale, key 1 widened `under` mm toward
            the fold's side over op under_d, or Wpoly1 about the same centre), then (turn) the arc toward the
            up-and-back direction and the canal on"""
            if Wpoly1 is not None:
                under = 1.0
            Sc, _ = on_skin_w12(phi, G, fr, Wc)
            Sc = Sc[0]
            nodes, keys, scale = [], [], []
            for s_ in np.arange(-op['out'], depth + 1e-9, 0.5):
                nodes.append(Sc + s_ * tin)
                keys.append(float(np.clip((s_ - op['under_d'][0]) / (op['under_d'][1] - op['under_d'][0]), 0.0, 1.0))
                            if under > 0 else 0.0)
                scale.append(1.0 if s_ <= 0.0 else 1.0 - (1.0 - depth_scale) * min(s_ / depth, 1.0))
            if turn:
                p0 = nodes[-1]
                ang = np.arccos(np.clip(tin @ tend, -1.0, 1.0))
                axis_n = tend - (tend @ tin) * tin
                axis_n /= np.linalg.norm(axis_n)
                nn = max(3, int(np.ceil(op['arc_r'] * ang / 0.6)))
                for j in range(1, nn + 1):
                    a_ = ang * j / nn
                    nodes.append(p0 + op['arc_r'] * (np.sin(a_) * tin + (1.0 - np.cos(a_)) * axis_n))
                    keys.append(keys[-1])
                    scale.append(depth_scale + (op['end_scale'] - depth_scale) * 0.5 * (j / nn))
                p1 = nodes[-1]
                nc = max(2, int(np.ceil(op['canal'] / 0.6)))
                for j in range(1, nc + 1):
                    nodes.append(p1 + op['canal'] * j / nc * tend)
                    keys.append(keys[-1])
                    scale.append(depth_scale + (op['end_scale'] - depth_scale) * (0.5 + 0.5 * j / nc))
            nodes = np.array(nodes)
            Wr = np.column_stack([Wpoly[:, 0] - Wc[0, 0], Wpoly[:, 1] - Wc[0, 1]])
            sec0 = np.column_stack([Wr[:, 0] * (e1 @ rdq), Wr[:, 1] * (e2 @ udq)])
            rel = sec0 - sec0.mean(0)
            rad = np.linalg.norm(rel, axis=1, keepdims=True)
            w = np.clip((rel / np.maximum(rad, 1e-9)) @ fold_dir, 0.0, 1.0) ** 1.5
            sec1 = sec0 + under * w[:, None] * rel / np.maximum(rad, 1e-9)
            if Wpoly1 is not None:
                Wr1 = np.column_stack([Wpoly1[:, 0] - Wc[0, 0], Wpoly1[:, 1] - Wc[0, 1]])
                sec1 = np.column_stack([Wr1[:, 0] * (e1 @ rdq), Wr1[:, 1] * (e2 @ udq)])
            rim_, _ = on_skin_w12(phi, G, fr, Wpoly)
            if (np.sum(sec0[:, 0] * np.roll(sec0[:, 1], -1) - np.roll(sec0[:, 0], -1) * sec0[:, 1])) < 0:
                sec0, sec1, rim_ = sec0[::-1], sec1[::-1], rim_[::-1]
            secs = np.stack([sec0, sec1])
            # surface samples for the measures (the openings' proximity): each node's section outline in its frame (the
            # frame transported along the centreline as the PSWEEP's)
            samp = []
            T = np.gradient(nodes, axis=0)
            T /= np.linalg.norm(T, axis=1, keepdims=True)
            nf = e1.copy()
            for j in range(len(nodes)):
                if j:
                    axr = np.cross(T[j - 1], T[j])
                    sa = np.linalg.norm(axr)
                    if sa > 1e-12:
                        axr /= sa
                        ca = float(T[j - 1] @ T[j])
                        nf = nf * ca + np.cross(axr, nf) * sa + axr * float(axr @ nf) * (1.0 - ca)
                    nf = nf - (nf @ T[j]) * T[j]
                    nf /= np.linalg.norm(nf)
                bf = np.cross(T[j], nf)
                sec = (secs[0] + (secs[1] - secs[0]) * keys[j]) * scale[j]
                samp.append(nodes[j] + sec[:, :1] * nf + sec[:, 1:2] * bf)
            return ('psweep', nodes, secs, op['rho'], np.array(keys), np.array(scale), e1,
                    rim_[np.isfinite(rim_).all(1)], np.vstack(samp))
        # the OPENING: at the skin the traced opening (the dark comma and the lit floor round it, key 0), within under_d mm
        # morphing into the traced DARK core about the same centre (key 1: the canal's mouth), narrowing to the throat
        # over `vest` mm (from w12's camera the walls close in: deep and occluded), then turning up and back out of every
        # front camera's sight (W2i h3's shallow recess round a separate canal read as a ring in a ring)
        Wo = to_img(tr['opening'])
        rim = on_skin_w12(phi, G, fr, Wo)[0]
        rim = rim[np.isfinite(rim).all(1)]
        sub_m.append(sweep(Wo, to_img(tr['centre'][None]), op['vest'], op['vest_scale'], 0.0,
                           Wpoly1=to_img(tr['dark'])))
        # the ALAR FOLD along the traced crest
        crest = 0.5 * (tr['fold_in'] + tr['fold_out'])
        Ci, _ = on_skin_w12(phi, G, fr, to_img(tr['fold_in']))
        Co, _ = on_skin_w12(phi, G, fr, to_img(tr['fold_out']))
        Cc, Cn = on_skin_w12(phi, G, fr, to_img(crest))
        okc = np.isfinite(Cc).all(1) & np.isfinite(Ci).all(1) & np.isfinite(Co).all(1)
        rad_f = np.clip(0.5 * np.linalg.norm(Ci - Co, axis=1), *hn['fold_r'])
        C = Cc[okc] + hn['fold_h'] * Cn[okc]
        # the roll tapered to its ends (h2's full-radius ends stood as knobs at the fold's two tips)
        tt_ = np.linspace(0.0, 1.0, int(okc.sum()))
        fold_m += _chain(C, rad_f[okc] * (0.45 + 0.55 * np.sin(np.pi * tt_) ** 0.6), hn.get('step', 1.0), 0.0)
        # the SLIT from the opening's lateral end (the loop's point nearest the fold's inner edge's lower end), back along
        # the skin and up
        tail = rim[int(np.argmin(np.linalg.norm(rim - Ci[okc][-1], axis=1)))]
        ln, rise, r0, r1, sink = hn['slit']
        Pp, Q_ = tail.copy(), []
        for j in range(int(ln) + 1):
            nq = _skin_frame(phi, G, Pp)
            Q_.append(Pp - sink * nq)
            step_ = np.array([1.0, rise, 0.0])
            step_ = step_ - (step_ @ nq) * nq
            Pp = surface_along(phi, G, (Pp + step_ / np.linalg.norm(step_) - 4.0 * nq)[None], nq[None], reach=10.0)[0]
        sub_m += _chain(np.array(Q_), np.linspace(r0, r1, len(Q_)), 1.0, hn['slit_k'])
    # the philtrum on the midline (nose_members' rule)
    ph = hn['philtrum']
    P_, R_ = [], []
    t = np.arange(0.0, 45.0, 0.1)
    nq_ = len(ph['q'])
    rr_ = np.broadcast_to(np.asarray(ph['r'], float), (nq_,))
    gg_ = np.broadcast_to(np.asarray(ph['groove'], float), (nq_,))
    for q_, r_, g_ in zip(ph['q'], rr_, gg_):
        f = sample3(phi, G, np.column_stack([-12.0 + t, np.full_like(t, q_), np.zeros_like(t)]))
        j = int(np.argmax(f < 0))
        if f[j] < 0 and j > 0:
            Sm = np.array([-12.0 + t[j - 1] + 0.1 * f[j - 1] / (f[j - 1] - f[j]), q_, 0.0])
            P_.append(Sm + (r_ - g_) * _skin_frame(phi, G, Sm))
            R_.append(r_)
    if len(P_) >= 2:
        sub_m += _chain(P_, R_, ph.get('step', 1.0), 0.0)
    return (fold_m, 0.0, hn['fold_kg']), (sub_m, hn['slit_k'], hn['k'])


def psweep_np(P, m):
    """a 'psweep' member's field at palate points P (n, 3) mm, approximately: the distance to its surface samples, signed
    by the nearest node's section (inside: negative); for the measures only (the program evaluates the PSWEEP exactly)"""
    from matplotlib.path import Path
    from scipy.spatial import cKDTree
    nodes, secs, keys, scale, samp = m[1], m[2], m[4], m[5], m[8]
    dist, _ = cKDTree(samp).query(P)
    jn = cKDTree(nodes).query(P)[1]
    inside = np.zeros(len(P), bool)
    T = np.gradient(nodes, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    for j in np.unique(jn):
        sel = np.nonzero(jn == j)[0]
        loop = samp.reshape(len(nodes), -1, 3)[j]
        cen = nodes[j]
        e1 = loop[0] - cen - ((loop[0] - cen) @ T[j]) * T[j]
        e1 /= np.linalg.norm(e1) + 1e-12
        e2 = np.cross(T[j], e1)
        poly = np.column_stack([(loop - cen) @ e1, (loop - cen) @ e2])
        Pp = np.column_stack([(P[sel] - cen) @ e1, (P[sel] - cen) @ e2])
        inside[sel] = Path(poly).contains_points(Pp)
    return np.where(inside, -dist, dist)


# ============================================================================================ the nares (analytic)
def nares_members(phi, G, hn):
    """W2d head (the lead's call 7): THE NARES as analytic members, a SUBTRACT group over the head's grid
    (canid.build_head), smooth at any scale (W2c's were carved into the 1 mm grid: ragged rims). Per side: the
    OPENING, an ellipsoid sunk `sink` mm behind the leather's front skin at (q, |x|), its inward axis into the head
    tipped up and medial (the canal runs up and back), half-axes across / up / in; the ALAR SLIT, a chain of round
    cones from the opening's lateral edge out, down and back round the ala (the comma's tail: w12, w06), each point
    (|x|, q) on the skin, its axis `slit_sink` mm inside it, radii tapering. phi, G: the closed head's grid (palate
    frame mm); hn: canid.HEAD['nares']. Returns ([members], k_union, k_group), a member ('ellipsoid', centre (3,),
    axes (3, 3) rows = local axes, half (3,)) or ('roundcone', a, b, r1, r2), all (d, q, x) mm"""
    out = []
    for sx in (1.0, -1.0):
        S_n = surface_along(phi, G, np.array([[20.0, hn['q'], sx * hn['x']]]), np.array([[-1.0, 0.0, 0.0]]),
                            reach=34.0)[0]
        o = np.array([1.0, hn['tilt_up'], -sx * hn['tilt_in']])
        o /= np.linalg.norm(o)
        u = np.array([0.0, 0.0, sx]) - o[2] * sx * o
        u /= np.linalg.norm(u)
        v = np.cross(o, u)
        v *= np.sign(v[1]) if v[1] != 0 else 1.0
        th = np.radians(hn.get('tilt_uv', 0.0))         # the comma: the opening's lateral end turned down
        u, v = np.cos(th) * u - np.sin(th) * v, np.sin(th) * u + np.cos(th) * v
        out.append(('ellipsoid', S_n + hn['sink'] * o, np.stack([u, v, o]), np.asarray(hn['half'], float)))
        pts = []
        for (ax_, q_, r_) in hn['slit']:
            s_ = surface_along(phi, G, np.array([[25.0, q_, sx * ax_]]), np.array([[-1.0, 0.0, 0.0]]),
                               reach=40.0)[0]
            pts.append((s_ + np.array([hn['slit_sink'], 0.0, 0.0]), r_))
        for (a_, ra), (b_, rb) in zip(pts[:-1], pts[1:]):
            out.append(('roundcone', a_, b_, ra, rb))
    return out, hn['slit_k'], hn['k']


def sd_roundcone_np(P, a, b, r1, r2):
    """sdf.sd_roundcone (iq's exact round cone) in numpy, P (n, 3)"""
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / max(l2, 1.0e-20)
    pa = P - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - ba[None] * y[:, None]
    x2 = np.sum(xv * xv, axis=1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))


def nares_apply(f, P, members):
    """the program's evaluation of the nares group on a field f at points P (d, q, x mm): the members unioned (smin,
    k_union; the first member of each side hard, as the group's first primitive), the group subtracted (smax with
    k_group); members as nares_members returns them"""
    mem, k_u, k_g = members

    def smin(a, b, k):
        if k <= 0:
            return np.minimum(a, b)
        h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
        return b * (1.0 - h) + a * h - k * h * (1.0 - h)
    g = None
    for m in mem:
        if m[0] == 'ellipsoid':
            dm = ellipsoid_sd(P, m[1], m[2], m[3])
        else:
            dm = sd_roundcone_np(P, m[1], m[2], m[3], m[4])
        # W2g: a round cone may carry its own union k (its 6th entry: the smooth tubes' chains hard-unioned)
        g = dm if g is None else smin(g, dm, m[5] if m[0] == 'roundcone' and len(m) > 5 else k_u)
    return -smin(-f, g, k_g)


# ============================================================================================ the bind's jaw
def open_jaw(phi, G, spec, deg, log=print):
    """the jaw opened by deg about the jaw joint (canid TMJ): TWO PARTS of the closed head cut by the SPLIT surface,
    the part above it kept, the part below turned rigidly by deg, their smooth union (k 8 mm: near the joint, where
    the parts barely part, they fuse). The split: inside the mouth the occlusal plane (q -21 at the incisors, the lower
    incisor crowns' line, canid.SKULL incisor_lo; -25 along the premolars, rising behind the commissure to the joint),
    dropping in front of the commissure over the last 12 mm to the skin's lip line (LIP_LINE), so the lips part along
    the mouth line and the lower jaw keeps its lips and floor. The cuts are half-spaces (exact faces: a voxel-wise
    branch pick printed the cut faces as a staircase)"""
    from . import canid
    L = canid.landmarks_pqx(spec)
    NP = canid.nose_p(spec)
    tmj = np.array([1000 * (NP - L['tmj'][0]), 1000 * L['tmj'][1]])
    ll = np.asarray(LIP_LINE, float)
    d_c = ll[-1, 0]
    dd = np.arange(ll[0, 0], d_c + 1.0, 1.0)
    xl = surface_x(phi, G, dd, np.interp(dd, ll[:, 0], ll[:, 1]))
    xl = np.interp(dd, dd[np.isfinite(xl)], xl[np.isfinite(xl)])

    def q_split(d, x):
        qo = np.interp(d, [0.0, 10.0, 60.0, d_c, tmj[0]], [-21.0, -21.0, -25.0, -26.0, tmj[1]])
        ql = np.interp(d, ll[:, 0], ll[:, 1])
        t = np.clip((np.abs(x) - (np.interp(d, dd, xl) - 12.0)) / 12.0, 0.0, 1.0)
        fade = 1.0 - np.clip((d - d_c) / 30.0, 0.0, 1.0)          # the drop eases out over 30 mm behind the
        fade = fade * fade * (3 - 2 * fade)                         # commissure (a hard stop cut a vertical face)
        t = t * t * (3 - 2 * t) * fade
        return qo + (ql - qo) * t

    a = np.radians(-deg)          # the jaw opens downward: a rotation toward -q in the (p, q) plane

    def rot(d, q, ang):
        dp, dq = -(d - tmj[0]), q - tmj[1]          # p = NP - d: a (p, q) vector from the joint
        c, s = np.cos(ang), np.sin(ang)
        rp, rq = c * dp - s * dq, s * dp + c * dq
        return tmj[0] - rp, tmj[1] + rq

    D, Q, X = G.mesh()
    up = np.maximum(phi, q_split(D, X) - Q)                         # above the split: kept
    yd, yq = rot(D, Q, -a)                                          # the lower part's preimage
    low = np.maximum(sample3(phi, G, np.stack([yd, yq, X], -1)), yq - q_split(yd, X))
    k = 8.0
    h_ = np.clip(0.5 + 0.5 * (low - up) / k, 0.0, 1.0)
    out = low * (1 - h_) + up * h_ - k * h_ * (1 - h_)
    log(f'[hull] jaw opened {deg:.1f} deg about the joint (d {tmj[0]:.0f}, q {tmj[1]:.0f}): the two parts cut at the '
        f'occlusal plane and the lip line, k {k:.0f} mm')
    return out.astype(np.float32)


def _skin_key(spec):
    """W2h: the skull's and the skin's inputs (canid_skull, canid_skin) for the closed head's cache key"""
    from . import canid_skin as CK, canid_skull as SK
    eye_c, eye_r = SK.eye_globe(spec)
    return dict(kv=CK.VERSION, sv=SK.VERSION, lat=SK.LAT, top=SK.TOP_OUT, holes=SK.TOP_HOLES, occ=SK.OCCLUSAL,
                alv=SK.ALVEOLAR, ad=SK.ARCH_DORSAL, av=SK.ARCH_VENTRAL, lm=SK.LANDMARKS, can=SK.CANINE_UP,
                dors=SK.DORSUM_HALF, shape=SK.SHAPE, sm=(SK.SMOOTH_IMG, SK.SMOOTH_PROF), deep=CK.DEEP, depths=CK.DEPTHS,
                base=(CK.BASE, CK.BASE_W, CK.SMOOTH, CK.SMOOTH_SIGMAS, CK.SMOOTH_DEPTH), eye=(eye_c.tolist(), eye_r),
                ad2=SK.ARCH_DORSAL_W2P, av2=SK.ARCH_VENTRAL_W2P)


def flow_key(spec):
    """the FLOW stage's cache key (head_volume's and canid_cage.reference's: they share its file): its inputs, and since
    W2k the clay's points the front photos' cameras are solved on (clay_points: the visible eyes and the planum), which
    silhouettes() reads: canid.EYE_Q moved the visible eye 4 mm (W2k) and the flow's front silhouettes with it, where the
    SPEC's eye dict alone had not changed.
    W2o (the lead's call 4): the clay's points read to 0.01 mm (W2k-W2n 1e-4 mm: eye_landmark's fixed point moves by
    thousandths of a mm with its iteration path, and each such move forced a ~25 min rebuild for nothing)"""
    from . import canid
    data = data_dict()
    clay = clay_points(spec)
    return cache_key(dict(v=FLOW_VERSION, data={k: v for k, v in data.items()}, head_len=spec['head_len'],
                          eye=spec['eye'], skull=canid.SKULL, face=canid.HEAD['face'], jaw=canid.HEAD['jaw'],
                          nose=canid.HEAD['nose'], clay={k: np.round(np.asarray(v, float), 2).tolist()
                                                         for k, v in clay.items()}))


def flow_stage(spec, log=print):
    """the FLOW stage (build_flow: the hull, its limits, the flow; everything before the sculpt) cached by flow_key: dict
    (phi, lo, h, err_*, cam_*)"""
    def build_flow_stage():
        data = data_dict()
        R = build_flow(spec, data, log)
        G = R['grid']
        out = dict(phi=R['phi'], lo=G.lo, h=np.float64(G.h))
        for stage, E in R['errors'].items():
            for v, e in E.items():
                out[f'err_{stage}_{v}'] = np.array([e['n'], e['med'], e['p90'], e['mean'], e['max']])
        for nm, fr in R['sil']['fronts'].items():
            out[f'cam_{nm}'] = np.array([fr['alpha'], fr['psi'], fr['resid']])
        return out
    return cached('canid_head_flow', flow_key(spec), build_flow_stage, log)


def finish(phi, G):
    """the grid as the GRID member takes it: the exact distance to phi's zero set, the far field clamped (the
    producer's part, sdf_grid.md), blurred 0.7 mm (a blurred distance keeps |grad| <= 1): hullflow.finish at BUILD's
    clamp and blur"""
    return HF.finish(phi, G, BUILD['clamp'], BUILD['blur'])


def head_volume(spec, jaw_deg=0.0, log=print):
    """THE HEAD GRID in the palate frame: the hull, the flow, the sculpt (jaw closed), then the jaw opened by jaw_deg
    for the bind; finished (clamp, blur). Cached by every input. Returns dict(values mm (nd, nq, nx), lo mm, h mm,
    divisor, errors per view before / after the flow, curves, notes).

    W2d head: the FLOW stage (the hull, its limits, the flow: everything before the sculpt) has its own cache,
    keyed by the flow's inputs only (FLOW_VERSION, not the strokes), so a change of the strokes re-sculpts the cached
    flow instead of re-running it (~7 min on the CPU); the closed head's key and content are as before (for the same
    strokes the closed grid is bit-identical: the same phi, grid and sculpt)"""
    from . import canid
    import hashlib as _hl
    import os as _os
    data = data_dict()
    skull_method = canid.HEAD.get('method') in ('skull', 'cage')
    # W2j (the lead's call, the W2i check's item 10): the closed head's key holds EVERY input of traced_fissure and
    # traced_canthi: EYE_FISSURES and the photos' landmark files they read (lm_w08.json; lm_w12.json for the canthi), so
    # an edit of either rebuilds the head instead of reusing a stale one
    _dd = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..', '..', 'work', 'bestiary',
                        'research', 'wolf_work', 'data')
    lm_sha = {p: _hl.sha1(open(_os.path.join(_dd, f'lm_{p}.json'), 'rb').read()).hexdigest() for p in ('w08', 'w12')}
    key_closed = cache_key(dict(v=VERSION, data={k: v for k, v in data.items()}, strokes=STROKES, lip=LIP_LINE,
                                canthi=CANTHI, head_len=spec['head_len'], eye=spec['eye'], skull=canid.SKULL,
                                face=canid.HEAD['face'], jaw=canid.HEAD['jaw'], nose=canid.HEAD['nose'],
                                **(dict(method='skull', skin=_skin_key(spec), strokes_skull=STROKES_SKULL,
                                        nose_w12=NOSE_W12, fronts_w12=FRONTS['w12']['landmarks'],
                                        eye_fissures=EYE_FISSURES, lm=lm_sha)
                                   if skull_method else {})))
    # (W2k: the flow stage's key and build shared with canid_cage.reference: flow_key, flow_stage)

    def build_closed():
        Fz = flow_stage(spec, log)
        G = Grid(Fz['lo'], Fz['lo'] + (np.array(Fz['phi'].shape) - 1) * float(Fz['h']), float(Fz['h']))
        if skull_method:
            # W2h (the lead's call 1): THE SKIN OVER THE SKULL (canid_skin.py) ahead of the poll, the flowed head behind it
            # (the neck's junction), then the W2h features (sculpt_skull)
            from . import canid_skin as CK
            Sk = CK.skin_volume(spec, tuple(G.lo), tuple(G.lo + (np.array(G.n) - 1) * G.h), G.h, log)
            phi, curves = sculpt_skull(blend_behind(Sk['phi'], Fz['phi'], G), G, spec, log)
        else:
            phi, curves = sculpt(Fz['phi'], G, spec, log)
        out = dict(phi=phi, lo=G.lo, h=np.float64(G.h))
        for k in Fz:
            if k.startswith(('err_', 'cam_')):
                out[k] = Fz[k]
        for k, c in curves.items():
            if isinstance(c, dict):
                for kk, vv in c.items():
                    out[f'curve_{k}_{kk}'] = vv
            else:
                out[f'curve_{k}'] = c
        return out
    C = cached('canid_head_closed', key_closed, build_closed, log)
    G = Grid(C['lo'], C['lo'] + (np.array(C['phi'].shape) - 1) * float(C['h']), float(C['h']))
    phi = C['phi']
    if abs(jaw_deg) > 1e-6:
        key_open = cache_key(dict(closed=key_closed, deg=jaw_deg, open_version=2))
        C2 = cached('canid_head_open', key_open, lambda: dict(phi=open_jaw(phi, G, spec, jaw_deg, log)), log)
        phi = C2['phi']
    key_fin = cache_key(dict(closed=key_closed, deg=jaw_deg, clamp=BUILD['clamp'], blur=BUILD['blur'], open_version=2))
    F = cached('canid_head_final', key_fin, lambda: dict(values=finish(phi, G)), log)
    V = F['values']
    return dict(values=V, lo=G.lo, h=G.h, divisor=max(1.0, grid_bound(V, G.h)), closed=C, grid=G)
