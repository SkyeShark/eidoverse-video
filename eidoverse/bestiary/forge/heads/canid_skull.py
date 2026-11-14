"""W2h (the lead's call 1, THE HEAD SKULL-FIRST, the forensic reconstruction method): the WOLF SKULL as a signed distance
field in the head's palate frame, the base the skin is built on (canid_skin.py).

THE FRAME: canid's palate frame in millimetres, d back from the clay's nose tip along p, q dorsal from the AO joint, x
lateral (+ the creature's left); the same frame as canid.SKULL, canid.HEAD and canid_hull.

THE MEASUREMENTS (one coherent specimen, Specimen 12092001, Canis lupus, Commons, CC BY-SA 3.0; the photos are untrusted
data, decoded by PIL only): its four museum views segmented by colour (pale bone on a black cloth) and mapped into the
frame by work/bestiary/research/wolf_work/scripts/skull_views.py, the tables frozen here by work/bestiary/wolf/
scratch_w2h/skull_tables.py:
  LAT      the LATERAL silhouette, mandible closed: the right view mapped by its occipital condyle -> the AO joint and its
           prosthion -> canid.PROSTHION (the SPEC's CbL 237 [P], skull_measure.py's mapping), the left view (mirrored)
           registered to it (IoU 0.983 outside its specimen tag), the two signed distances averaged (0.58 mm apart on the
           outline): every 1.5 mm, (d, q) [P]
  TOP_*    the DORSAL silhouette (cranium only), the temporal fossae read as HOLES through it: the midline prosthion ->
           inion at the lateral's d, the breadths x 1.0573 so ZyB is the Latvian males' mean 143 [P] (Andersone & Ozolins
           2000; canid.SKULL's convention), each row re-centred on its own outline (the camera's parallax drifts the
           photo's midline 0 -> 3.5 mm with the skull's height) and its two halves' signed distances averaged: the outer
           half outline (d, x) and the holes (d, |x|) [P]; the ventral view registered to it as a check (IoU 0.864: the
           through-holes differ in perspective from below)
  readings my hand readings (research/wolf_work/data/src/sk_w2h_readings.json; sk_s12092001_right.json's polylines
           and landmarks), mapped alike [P]: the occlusal line, the upper alveolar margin, the zygomatic arch's dorsal and
           ventral edges, the upper canine, the muzzle's flat top's half-width (the dorsal view's turning lines), the
           coronoid's tip (MWNH 358 at the SPEC scale: s12092001's arch hides it)
Breadths at this scale (TOP_OUT): C1B 46.7 (Latvian males 47), ZyB 143.0 (143, by the scale), LB 44.2 (42), MB 75.3 at
the mastoid shoulders (79; W2i: the dorsal view's otion re-read on the bone, d 217, research/wolf_work/data/src/
sk_s12092001_top.json); the lateral: CbL 237 (by the mapping; 235.4 on the bone, w02_skull), ToL 240 (the LAT table's back
at d 255.4; 265: this specimen's crest ends nearer its condyles), MdL ~175-177 (189).

W2i (the lead's call 1, "THE SKULL SMOOTH WHERE THE SKIN IS THIN"): W2h's skull was the two views' visual hull carved
by region switches (np.where along d: the fossa's span, the arch's, the region under the arch, the mandible's end, the
braincase's breadth source; the frontal plate faded in over 20 mm), and the thin skin printed every switch as a bar across
the brow and the forehead; its face flank's width followed the dorsal outline INCLUDING the cheek teeth's crowns, which
the skin printed as 13 mm stripes; its arches, base and mandible were the hull's slabs. Now every part is a LOFT: a
section given at each d by smooth profiles (tables through PCHIP, low-passed), its field the section's own approximate
distance (the side's horizontal offset normalised by its slope), so no field switches anywhere:
  CRANIUM   one loft from the incisors to the occiput whose section MORPHS along d between three families, their weights
            smoothsteps over 28-30 mm (w2h's fades were 8-20 mm, its switches 0 mm):
              FACE      the muzzle: a narrow, cambered nasal dorsum (DORSUM_HALF, half-width n) whose sides slope out and
                        down to the widest at the upper ALVEOLAR line (half-width W), the tooth row under it to the
                        occlusal line. W is the dorsal outline's run from the midline (the crowns' loops excluded) OPENED
                        over SHAPE face_open mm (the crowns' narrow bumps), less the cheek teeth's crown overhang (SHAPE
                        crown_out [E]), then low-passed (Gaussian face_sigma 10 mm: a 40 mm wave keeps 0.29 of itself, the
                        W2h stripes' 13 mm ~0); the side's profile n + (W - n)(1 - (1 - s)^side_p) (s the height share
                        from the dorsum's edge to the alveolar line), checked against MWNH 358's front
              FRONTAL   over the orbits: the frontal plate at the frontal's breadth (the supraorbital margins, the
                        postorbital processes; the fossa's medial edge from above, low-passed 5 mm) for its top `plate` mm,
                        stepping in over `step` mm to the orbit's medial wall, widening again under the orbit's floor to the
                        maxilla's tooth row and, behind it, the pterygoids
              DOME      the braincase: a dome under the sagittal crest, widest at dome_t of its height, its breadth the
                        fossa's medial edge from above, behind the fossa widening to the mastoids, then the occiput's outline
  ARCHES    the zygomatic arches as SWEPT TUBES standing free of the temporal fossa: an elliptical section (its half-height
            from the arch's measured dorsal and ventral edges in profile, its half-thickness from the dorsal view's outline
            and the fossa's lateral edge), its centre on their mean, each slice's section stretched by its centre line's
            slope along d (a tube's normal section seen in the slice); the front root runs forward and down into the
            maxilla under the orbit, the back root a chain of round cones curving medially along the dorsal outline to the
            mastoid region (SHAPE arch, arch_back)
  BASE      the basicranium (the pterygoids, the bullae, the mastoids, the paroccipital processes, the condyles) as a
            lofted superellipse between the cranial base's measured bottom (the lateral silhouette behind the mandible)
            and the dome's base, its breadth the dorsal outline behind the arches (SHAPE base)
  MANDIBLE  two lofted BODIES (a rounded section from the ventral border to the lower alveolar margin, the lower teeth a
            band to the occlusal line), the RAMUS a plate on its traced outline with rounded edges, the CONDYLE a capsule,
            the whole bone CLOSED about the condyle by SHAPE jaw_close deg (the museum photos hold the incisors edge to
            edge; a closed scissor bite overlaps them, the lower behind the upper) and its ventral border at the chin held
            on the profile photos' jaw line (canid_hull PROFILE) plus the chin's tissue (SHAPE chin_tissue [L]) where the
            specimen's stands deeper (the W2h skin there stood 10 mm under the photos' line; the lip was thinned to hide
            it; the lead's call 8: the bone fixed, not the lip)
  TEETH     the upper canine (alveolus -> tip measured), the lower canine [E]
  CARVES    the ORBIT (a socket under the supraorbital margin round the SPEC's globe, its rim MWNH 358's; the live photos'
            visible eye sits 6-10 mm behind s12092001's own orbit opening, a difference between the specimens) and the
            NASAL APERTURE, each smooth-subtracted

W2p (the lead's call 1, "check the zygomatic arch's dorsal process at d ~145 against the photographed skulls"): THE ARCH
OVER THE ORBIT IS MWNH 358's. The skull mixed two specimens at the eye's outer corner: its orbit rim is MWNH 358's (the
specimen whose orbit holds the photos' eye) and its arch was s12092001's. In each photo the orbit's ventral rim and the
zygoma's postorbital process sit on that specimen's own arch edge (s12092001: orbit_ventral (125.7, 25.2) on its edge,
the process at (139.1, 29.8); MWNH 358: (132.7, 21.3) 0.7 mm under its edge, the process (149.6, 25.4) 0.5 mm over it).
s12092001's edge runs 4.3-6.6 mm above MWNH 358's from d 125 to 165 (29.2 against 24.9 at d 145.8, the lateral canthus's
own d), so the composite's arch cut the rim's lower part off and stood level with the lateral canthus 5.5 mm lateral of
it, under ~2 mm of skin: the cliff below the canthus (the W2o fresh eyes). With s12092001's arch the photos' lateral
canthus would lie 6.7 mm behind that specimen's own orbit (its process at d 139.1); with MWNH 358's it lies inside the
orbit, 3.8 mm in front of the process and 4.3 mm over it, where a canid's lateral palpebral ligament meets the orbital
ligament. So the arch's dorsal and ventral edges over the orbit (d 122.9-175.7) are MWNH 358's readings at the SPEC
scale (ARCH_DORSAL_M358 / ARCH_VENTRAL_M358), joined to the [E] front root ahead and to s12092001's back root behind
(the two specimens agree there within 1-2 mm: 17.0 / 17.2 at d 182); the skin's masseter and temporalis hulls read the
same edges (ARCH_DORSAL_W2P / ARCH_VENTRAL_W2P, canid_skin); the back root's first round cone lowered 2 mm with them.
Checked on work/bestiary/research/wolf_work/checks/mwnh358_lateral_lateral.png and s12092001_right_lateral.png and a crop
of MWNH 358's orbit at full size (work/bestiary/wolf/check_w2p/out/skull_arch_*.png)
The parts are smooth-unioned (SHAPE k_*); the field is redistanced on its grid by the callers (skull_volume, canid_skin).
"""
import numpy as np

from ..hullflow import Grid, cache_key, cached

VERSION = 'w2p-s5'               # bump with every change of the construction's code (the key holds the tables and SHAPE)
TOP_BREADTH_SCALE = 1.0573       # the dorsal view's breadths scaled so its ZyB reads 143 [P] (skull_views.py; TOP_OUT)

# ============================================================================================ the frozen tables (mm)
# skull_tables.py LAT: s12092001 right + left (registered), the mean signed distance's outline, every 1.5 mm, (d, q)
LAT = (
    (255.2, 51.1), (254.9, 52.5), (254.4, 53.9), (253.6, 55.2), (253.1, 56.6), (252.3, 57.8), (251.4, 59.0), (250.3, 60.0),
    (249.2, 61.0), (248.0, 62.0), (246.9, 62.8), (245.6, 63.5), (244.4, 64.3), (243.1, 64.8), (241.7, 65.4), (240.4, 65.9),
    (239.0, 66.1), (237.6, 66.5), (236.2, 66.6), (234.8, 66.8), (233.4, 66.9), (232.0, 67.0), (230.5, 67.1), (229.1, 67.3),
    (227.8, 67.2), (226.7, 67.2), (225.6, 67.2), (224.2, 67.1), (222.8, 67.2), (221.4, 67.0), (220.0, 66.5), (218.7, 65.8),
    (217.3, 65.2), (215.9, 65.0), (214.5, 65.0), (213.0, 65.0), (211.6, 64.8), (210.1, 64.6), (208.6, 64.4), (207.2, 64.2),
    (205.7, 64.0), (204.3, 63.8), (202.9, 63.5), (201.5, 63.5), (200.0, 63.6), (198.5, 63.6), (197.1, 63.9), (195.6, 63.9),
    (194.2, 64.1), (192.7, 64.1), (191.2, 64.1), (189.8, 63.9), (188.3, 63.9), (186.8, 63.9), (185.3, 63.9), (183.9, 64.0),
    (182.4, 64.0), (180.9, 64.0), (179.4, 64.1), (178.2, 64.0), (176.9, 64.1), (175.6, 64.0), (174.2, 64.0), (172.8, 63.9),
    (171.3, 63.9), (169.9, 63.8), (168.4, 63.9), (166.9, 64.0), (165.4, 64.0), (163.9, 64.1), (162.6, 64.3), (161.2, 64.3),
    (159.8, 64.4), (158.3, 64.4), (156.8, 64.2), (155.4, 64.1), (153.9, 63.8), (152.5, 63.6), (151.0, 63.3), (149.6, 63.0),
    (148.1, 62.6), (146.7, 62.1), (145.3, 61.6), (143.9, 61.0), (142.5, 60.5), (141.1, 60.0), (139.8, 59.4), (138.4, 58.7),
    (137.1, 58.1), (135.8, 57.4), (134.5, 56.7), (133.2, 55.9), (131.9, 55.1), (130.6, 54.4), (129.3, 53.6), (128.0, 52.9),
    (126.8, 52.0), (125.6, 51.1), (124.4, 50.3), (123.2, 49.4), (122.0, 48.5), (120.8, 47.6), (119.6, 46.8), (118.3, 46.0),
    (117.2, 45.0), (116.0, 44.1), (114.7, 43.3), (113.5, 42.5), (112.2, 41.7), (111.0, 40.9), (109.8, 40.1), (108.5, 39.3),
    (107.3, 38.5), (106.0, 37.8), (104.6, 37.2), (103.3, 36.5), (102.1, 35.8), (100.8, 35.2), (99.5, 34.6), (98.1, 33.9),
    (96.8, 33.3), (95.5, 32.7), (94.2, 32.2), (92.9, 31.5), (91.6, 30.9), (90.3, 30.4), (89.0, 29.8), (87.6, 29.3),
    (86.3, 29.0), (84.9, 28.5), (83.5, 28.1), (82.1, 27.8), (80.7, 27.5), (79.2, 27.1), (77.8, 26.8), (76.3, 26.6),
    (74.9, 26.4), (73.4, 26.3), (71.9, 26.0), (70.5, 25.8), (69.0, 25.5), (67.5, 25.4), (66.1, 25.1), (64.6, 24.8),
    (63.1, 24.5), (61.7, 24.2), (60.2, 23.9), (58.8, 23.4), (57.4, 23.1), (55.9, 22.8), (54.5, 22.4), (53.1, 22.0),
    (51.7, 21.6), (50.3, 21.1), (48.9, 20.5), (47.5, 20.0), (46.2, 19.5), (44.8, 18.9), (43.5, 18.2), (42.2, 17.6),
    (40.9, 16.8), (39.7, 16.0), (38.8, 14.8), (37.8, 13.8), (37.1, 12.4), (36.2, 11.2), (35.3, 10.1), (34.5, 8.8),
    (33.6, 7.6), (32.8, 6.3), (32.0, 5.1), (31.1, 3.9), (30.2, 2.7), (29.3, 1.5), (28.3, 0.5), (27.2, -0.5),
    (26.0, -1.4), (24.8, -2.2), (23.5, -3.1), (22.5, -4.1), (21.6, -5.3), (20.6, -6.4), (19.7, -7.6), (18.8, -8.7),
    (18.2, -10.1), (17.7, -11.3), (17.2, -12.7), (16.3, -13.9), (15.4, -15.1), (14.9, -16.4), (14.6, -17.9), (14.6, -19.4),
    (14.6, -20.9), (14.9, -22.3), (15.3, -23.8), (16.4, -24.7), (17.9, -24.6), (19.2, -24.9), (18.7, -26.1), (18.2, -27.5),
    (18.5, -28.9), (18.9, -30.3), (19.5, -31.7), (20.2, -33.0), (21.2, -34.1), (22.3, -35.1), (23.1, -36.4), (23.9, -37.6),
    (24.5, -38.9), (25.4, -40.2), (26.4, -41.3), (27.5, -42.3), (28.6, -43.3), (29.6, -44.4), (30.7, -45.4), (31.9, -46.3),
    (33.0, -47.3), (34.1, -48.3), (35.3, -49.0), (36.7, -49.8), (38.1, -50.3), (39.5, -50.7), (40.9, -51.1), (42.3, -51.5),
    (43.6, -52.0), (45.0, -52.5), (46.3, -52.9), (47.7, -53.3), (49.1, -53.6), (50.6, -53.9), (52.0, -54.1), (53.5, -54.2),
    (55.0, -54.4), (56.4, -54.4), (57.8, -54.2), (59.2, -54.4), (60.7, -54.4), (62.2, -54.5), (63.7, -54.6), (65.2, -54.8),
    (66.6, -55.0), (68.1, -55.2), (69.6, -55.4), (71.0, -55.6), (72.5, -55.8), (73.9, -56.0), (75.4, -56.0), (76.8, -56.2),
    (78.3, -56.5), (79.8, -56.6), (81.2, -56.9), (82.7, -57.1), (84.2, -57.4), (85.6, -57.6), (87.1, -57.9), (88.5, -58.1),
    (90.0, -58.4), (91.4, -58.6), (92.9, -58.9), (94.4, -59.1), (95.8, -59.2), (97.3, -59.3), (98.6, -59.4), (100.0, -59.6),
    (101.4, -59.7), (102.8, -59.9), (104.2, -60.1), (105.7, -60.1), (107.2, -60.1), (108.7, -60.2), (110.1, -60.4), (111.6, -60.4),
    (113.1, -60.5), (114.6, -60.5), (116.1, -60.6), (117.6, -60.6), (119.1, -60.6), (120.6, -60.7), (122.1, -60.7), (123.5, -60.7),
    (125.0, -60.7), (126.4, -60.8), (127.9, -60.7), (129.3, -60.7), (130.8, -60.6), (132.3, -60.6), (133.8, -60.5), (135.3, -60.4),
    (136.8, -60.2), (138.2, -60.0), (139.7, -59.8), (141.2, -59.6), (142.6, -59.4), (144.1, -59.1), (145.5, -58.7), (147.0, -58.4),
    (148.4, -58.1), (149.9, -57.6), (151.3, -57.2), (152.7, -56.8), (154.1, -56.3), (155.6, -55.8), (157.0, -55.3), (158.4, -54.9),
    (159.7, -54.2), (161.0, -53.5), (162.3, -52.8), (163.6, -52.1), (164.9, -51.3), (166.0, -50.3), (167.1, -49.4), (168.3, -48.4),
    (169.4, -47.5), (170.6, -46.6), (171.6, -45.6), (172.6, -44.7), (173.9, -44.1), (175.2, -43.7), (176.5, -43.1), (177.7, -42.4),
    (179.0, -42.1), (180.3, -41.6), (181.6, -41.1), (182.9, -41.1), (184.3, -40.9), (185.6, -40.4), (187.0, -40.1), (188.4, -39.9),
    (189.7, -39.7), (190.9, -39.6), (192.2, -39.6), (193.6, -39.5), (195.1, -39.4), (196.5, -39.1), (197.8, -38.6), (199.1, -38.1),
    (200.2, -37.2), (201.3, -36.1), (202.1, -35.0), (202.8, -33.8), (203.2, -32.4), (203.4, -31.0), (203.2, -29.6), (202.9, -28.2),
    (203.6, -27.0), (203.9, -25.6), (203.9, -24.1), (203.0, -23.4), (202.0, -24.4), (200.8, -24.1), (199.3, -24.1), (197.9, -23.8),
    (196.7, -23.2), (195.5, -22.9), (194.2, -22.4), (192.8, -22.1), (192.4, -20.8), (192.4, -19.3), (192.6, -17.9), (192.7, -16.7),
    (193.4, -15.5), (194.7, -14.9), (194.7, -16.0), (195.8, -16.6), (196.9, -16.1), (198.3, -15.9), (199.4, -15.0), (200.3, -13.9),
    (201.3, -12.9), (202.4, -12.0), (203.5, -11.1), (204.7, -10.2), (205.9, -9.6), (207.1, -10.3), (207.1, -11.6), (207.4, -13.0),
    (207.4, -14.5), (207.9, -15.8), (208.4, -17.1), (209.4, -18.0), (210.6, -18.6), (212.0, -18.9), (213.4, -19.1), (214.8, -18.9),
    (216.3, -18.9), (217.7, -18.6), (219.0, -18.1), (220.3, -17.6), (221.6, -17.1), (222.8, -16.3), (223.8, -15.3), (225.1, -14.6),
    (226.4, -14.2), (227.7, -13.6), (228.8, -12.8), (230.1, -12.4), (231.4, -11.9), (232.8, -11.6), (234.1, -12.2), (235.1, -13.0),
    (236.3, -13.0), (236.9, -11.8), (236.4, -10.5), (235.8, -9.2), (235.1, -8.0), (235.1, -6.7), (234.9, -5.3), (233.9, -4.2),
    (233.6, -2.8), (233.1, -1.5), (233.1, -0.0), (234.4, 0.4), (235.8, 0.6), (237.1, 0.6), (237.9, -0.5), (238.6, -1.7),
    (239.5, -2.8), (240.4, -4.0), (241.4, -5.1), (242.1, -6.3), (242.5, -7.6), (242.9, -8.6), (243.7, -9.6), (245.1, -9.9),
    (246.4, -9.9), (247.6, -9.6), (248.8, -8.9), (249.9, -8.0), (250.4, -6.7), (250.4, -5.2), (250.4, -3.7), (250.1, -2.3),
    (249.6, -1.0), (249.1, 0.3), (248.4, 1.5), (247.5, 2.6), (246.5, 3.6), (245.6, 4.6), (245.9, 6.0), (246.8, 6.9),
    (247.4, 8.2), (247.5, 9.7), (247.4, 11.0), (246.3, 12.1), (245.4, 13.2), (244.9, 14.5), (244.2, 15.8), (243.8, 17.2),
    (243.4, 18.6), (243.1, 20.0), (242.9, 21.5), (242.8, 23.0), (242.8, 24.5), (242.5, 25.9), (242.5, 27.4), (242.5, 28.9),
    (242.5, 30.4), (242.4, 31.9), (242.5, 33.4), (242.6, 34.9), (243.7, 35.7), (244.7, 36.8), (245.4, 38.1), (246.2, 39.3),
    (247.0, 40.5), (247.8, 41.8), (248.7, 42.9), (249.4, 44.1), (250.3, 45.3), (251.4, 46.2), (252.7, 46.9), (254.1, 47.3),
    (255.1, 48.3), (255.4, 49.7))
# skull_tables.py TOP_OUT: the dorsal outline's x >= 0 half, rows re-centred, halves averaged, x 1.0573, (d, x)
TOP_OUT = (
    (13.9, 0.1), (14.2, 1.6), (14.1, 3.1), (14.4, 4.6), (14.8, 6.0), (15.0, 7.5), (15.0, 9.0), (15.3, 10.5),
    (16.1, 11.7), (17.3, 12.6), (18.4, 13.5), (18.6, 15.0), (18.9, 16.4), (20.1, 17.4), (21.5, 17.7), (23.0, 17.6),
    (24.5, 17.3), (26.0, 17.0), (27.5, 17.0), (28.9, 17.5), (30.3, 17.8), (31.7, 18.4), (33.1, 18.9), (33.6, 20.2),
    (33.9, 21.7), (34.8, 22.8), (36.3, 23.2), (37.8, 23.2), (39.3, 23.1), (40.7, 23.3), (42.2, 23.4), (43.7, 23.3),
    (45.2, 23.0), (46.6, 22.7), (48.1, 22.5), (49.6, 22.2), (51.1, 22.0), (52.6, 21.9), (54.1, 21.8), (55.5, 21.5),
    (57.0, 21.3), (58.5, 21.0), (60.0, 20.6), (61.4, 20.3), (62.9, 19.9), (64.3, 19.6), (65.8, 19.4), (67.3, 19.5),
    (68.8, 19.7), (70.3, 19.9), (71.8, 20.2), (73.1, 20.8), (72.4, 21.9), (71.0, 22.3), (69.5, 22.6), (68.0, 22.6),
    (68.6, 23.4), (70.1, 23.8), (71.6, 24.0), (73.1, 23.9), (74.5, 24.2), (75.9, 24.7), (77.1, 25.6), (77.9, 26.9),
    (78.9, 28.1), (80.0, 29.1), (81.1, 30.0), (82.5, 30.7), (83.7, 31.5), (85.0, 32.3), (86.4, 32.9), (87.5, 33.9),
    (88.4, 35.1), (89.4, 36.3), (90.7, 37.0), (91.6, 36.2), (93.0, 35.6), (94.5, 35.3), (96.0, 35.1), (97.5, 35.4),
    (99.0, 35.5), (100.5, 35.7), (101.9, 36.0), (102.0, 37.0), (100.6, 36.8), (99.1, 37.0), (97.7, 37.4), (97.5, 38.6),
    (98.9, 39.2), (100.3, 39.6), (101.8, 39.8), (103.2, 40.1), (104.7, 40.1), (106.3, 40.0), (107.7, 40.2), (109.2, 40.1),
    (110.7, 40.6), (111.9, 41.5), (113.0, 42.4), (114.3, 43.2), (115.6, 44.0), (116.7, 45.0), (117.8, 46.0), (119.0, 47.0),
    (120.2, 47.8), (121.4, 48.7), (122.7, 49.5), (123.9, 50.3), (125.2, 51.1), (126.5, 51.9), (127.8, 52.6), (129.1, 53.4),
    (130.4, 54.1), (131.7, 54.8), (133.1, 55.5), (134.4, 56.2), (135.7, 56.9), (137.0, 57.7), (138.2, 58.6), (139.5, 59.3),
    (140.8, 60.1), (142.1, 60.9), (143.4, 61.6), (144.6, 62.4), (146.0, 63.0), (147.4, 63.7), (148.7, 64.5), (149.9, 65.3),
    (151.4, 65.3), (152.8, 65.5), (153.9, 66.6), (155.1, 67.4), (156.5, 68.0), (157.9, 68.5), (159.3, 69.0), (160.8, 69.5),
    (162.2, 70.0), (163.6, 70.4), (165.1, 70.8), (166.6, 71.0), (168.0, 71.3), (169.5, 71.3), (171.0, 71.5), (172.5, 71.5),
    (174.0, 71.4), (175.5, 71.4), (177.0, 71.2), (178.5, 71.0), (179.9, 70.7), (181.4, 70.2), (182.8, 69.8), (184.2, 69.3),
    (185.5, 68.6), (186.9, 67.9), (188.1, 67.0), (189.3, 66.1), (190.4, 65.1), (191.5, 64.1), (192.5, 62.9), (193.5, 61.8),
    (194.3, 60.6), (195.3, 59.4), (196.1, 58.1), (196.9, 56.8), (197.6, 55.5), (198.2, 54.2), (198.8, 52.8), (199.4, 51.5),
    (200.0, 50.0), (200.4, 48.6), (200.9, 47.2), (201.5, 45.8), (202.2, 44.5), (203.0, 43.2), (204.2, 42.2), (205.5, 41.5),
    (206.9, 41.0), (208.3, 40.6), (209.8, 40.4), (211.3, 40.4), (212.9, 40.4), (214.3, 40.1), (215.7, 39.4), (216.8, 38.4),
    (217.4, 37.1), (217.8, 35.7), (218.5, 34.4), (219.5, 33.2), (220.4, 32.0), (221.4, 30.9), (222.3, 29.7), (223.4, 28.6),
    (224.4, 27.5), (225.4, 26.4), (226.5, 25.4), (227.7, 24.5), (228.9, 23.7), (230.2, 22.8), (231.5, 22.0), (232.9, 21.9),
    (234.4, 21.5), (235.6, 20.7), (237.0, 20.0), (238.4, 19.4), (239.7, 18.7), (240.9, 17.9), (242.2, 17.1), (243.5, 16.3),
    (244.8, 15.5), (246.1, 14.8), (247.3, 13.9), (248.4, 12.9), (249.4, 11.8), (250.2, 10.5), (251.1, 9.3), (252.0, 8.1),
    (252.9, 6.9), (254.1, 5.9), (254.4, 4.5), (255.0, 3.1), (255.2, 1.6), (255.1, 0.1))
# skull_tables.py TOP_HOLE 1 (the temporal fossa with the orbit's open back) and 0 (the orbit's front-medial gap), (d, |x|)
TOP_HOLES = ((
    (184.3, 29.5), (183.7, 28.3), (182.5, 27.5), (181.2, 26.8), (179.8, 26.2), (178.4, 25.6), (177.1, 24.9), (175.8, 24.2),
    (174.5, 23.6), (173.1, 22.9), (171.7, 22.5), (170.2, 22.1), (168.7, 22.2), (167.2, 22.4), (165.9, 22.9), (164.4, 23.4),
    (163.1, 24.0), (161.7, 24.6), (160.3, 25.1), (158.9, 25.7), (157.5, 26.3), (156.2, 27.0), (154.9, 27.8), (153.6, 28.6),
    (152.3, 29.3), (151.2, 30.4), (150.3, 31.6), (149.5, 32.8), (148.5, 33.9), (147.4, 35.0), (146.0, 35.6), (144.6, 35.8),
    (143.0, 35.7), (141.6, 35.2), (140.3, 34.6), (139.1, 33.7), (137.9, 32.7), (136.8, 31.7), (135.8, 30.6), (134.7, 29.6),
    (133.6, 28.5), (132.4, 27.6), (131.0, 27.1), (129.5, 27.2), (128.1, 27.7), (128.2, 28.7), (129.2, 29.9), (130.2, 31.0),
    (130.5, 32.4), (129.5, 33.6), (128.5, 34.7), (127.7, 35.9), (127.2, 37.4), (127.4, 38.8), (127.8, 40.2), (128.6, 41.5),
    (129.5, 42.7), (130.5, 43.8), (131.5, 44.9), (132.4, 46.1), (133.3, 47.3), (134.4, 48.3), (135.7, 48.9), (137.1, 49.5),
    (138.6, 49.7), (140.1, 50.1), (141.4, 50.5), (142.5, 49.8), (143.7, 50.4), (144.0, 51.9), (144.6, 53.2), (145.2, 54.5),
    (146.1, 55.8), (147.0, 56.9), (148.1, 58.0), (149.2, 59.0), (150.3, 60.0), (151.6, 60.8), (152.9, 60.8), (154.4, 61.2),
    (155.3, 62.3), (156.6, 63.1), (158.0, 63.6), (159.4, 64.0), (160.8, 64.4), (162.3, 64.5), (163.7, 64.6), (165.2, 64.8),
    (166.6, 64.5), (168.1, 64.4), (169.6, 64.2), (171.0, 63.8), (172.3, 63.4), (173.8, 63.1), (175.3, 63.1), (176.7, 62.7),
    (177.9, 61.9), (178.8, 60.7), (179.5, 59.3), (180.2, 58.0), (180.5, 56.6), (180.7, 55.1), (180.8, 53.6), (180.8, 52.1),
    (180.7, 50.6), (180.5, 49.1), (180.3, 47.6), (180.2, 46.1), (180.2, 44.6), (180.1, 43.1), (180.1, 41.6), (180.4, 40.1),
    (180.4, 38.6), (180.3, 37.1), (180.1, 35.6), (180.0, 34.1), (180.0, 32.7), (180.5, 31.2), (181.7, 30.4), (183.2, 30.5)), (
    (125.5, 28.5), (124.4, 27.6), (123.0, 27.0), (121.6, 26.8), (120.1, 26.9), (118.6, 27.3), (117.2, 27.7), (116.0, 28.5),
    (115.8, 29.9), (116.3, 31.3), (116.9, 32.7), (118.0, 33.7), (119.4, 34.2), (120.9, 34.3), (122.0, 33.3), (123.0, 32.3),
    (123.9, 31.0), (124.8, 29.8)))
# my readings (sk_w2h_readings.json, sk_s12092001_right.json) in the frame, (d, q)
OCCLUSAL = ((22.8, -26.0), (43.0, -29.5), (53.0, -27.9), (63.2, -27.3), (73.3, -26.0), (88.6, -25.2), (104.2, -25.6),
            (119.4, -23.8), (134.3, -21.0))
ALVEOLAR = ((15.0, -12.0), (32.4, -12.4), (38.5, -16.1), (50.8, -15.9), (66.1, -15.1), (81.8, -15.9), (94.2, -16.4),
            (123.3, -17.5))
ARCH_DORSAL = ((116.4, 19.7), (125.7, 25.2), (133.4, 28.3), (140.5, 29.3), (150.8, 29.2), (158.6, 29.1), (166.2, 29.5),
               (171.8, 27.4), (177.7, 23.3), (182.5, 17.0), (185.6, 8.3))
ARCH_VENTRAL = ((116.1, -0.5), (124.3, 5.2), (134.0, 8.5), (143.8, 11.4), (153.7, 13.5), (161.3, 14.1), (169.2, 13.5),
                (176.1, 9.6), (182.4, 3.6), (186.5, -1.9))
# W2p: MWNH 358's arch edges (research/wolf_work/data/res_skull_s12092001.json lateral_mwnh358, its lateral view mapped by
# the occipital condyle -> the AO joint and the prosthion -> canid.PROSTHION at the SPEC's CbL 237, as LAT), (d, q) [P]
ARCH_DORSAL_M358 = ((122.9, 18.3), (133.9, 22.5), (143.9, 24.9), (151.4, 24.9), (164.4, 23.1), (183.7, 16.6),
                    (197.8, 7.6), (206.2, -0.5))
ARCH_VENTRAL_M358 = ((131.7, 7.6), (157.1, 9.3), (175.7, 8.1), (191.4, 1.1), (203.4, -6.4))
# W2p (the module docstring's W2p): THE ARCH'S EDGES AS USED (the skin's hulls read these; SHAPE arch extends them into
# the maxilla): MWNH 358's over the orbit (d 122.9-175.7: between its readings by linear interpolation at 171.8 / 177.7
# and 124.3 / 143.8 / 169.2 / 176.1), s12092001's behind it (its back root from d 182.4) and its ventral 116.1 ahead; the
# dorsal edge at d 116.4 an [E] join rising into MWNH 358's 18.3 at 122.9 (s12092001's 19.7 there would dip 1.4 mm)
ARCH_DORSAL_W2P = ((116.4, 17.5), (122.9, 18.3), (133.9, 22.5), (143.9, 24.9), (151.4, 24.9), (164.4, 23.1), (171.8, 20.6),
                   (177.7, 18.6), (182.5, 17.0), (185.6, 8.3))
ARCH_VENTRAL_W2P = ((116.1, -0.5), (124.3, 3.7), (131.7, 7.6), (143.8, 8.4), (157.1, 9.3), (169.2, 8.6), (176.1, 7.9),
                    (182.4, 3.6), (186.5, -1.9))
# W2i (the lead's call 8): the OTION re-read on s12092001_top at the real mastoid shoulders, (2275, 778) / (2255, 1455)
# px, the outline's posterior corners over the mastoids (work/bestiary/wolf/scratch_w2i/out/otion_top_R.png,
# otion_top_L.png at 3x; W2h's (2390, 760) / (2390, 1455) lay in the black background ~17 mm off the bone): d 217.2,
# |x| 37.7 (the two sides 34.8 / 40.5 about a midline drifted 2.9 mm by the camera's parallax), MB 75.3 (Latvian 79)
LANDMARKS = dict(prosthion=(15.0, -12.0), rhinion=(31.8, 8.7), infradentale=(24.6, -34.8), canine_alveolus=(32.4, -12.4),
                 orbit_anterior=(109.1, 23.0), orbit_dorsal=(122.6, 42.2), orbit_ventral=(125.7, 25.2),
                 postorbital_frontal=(138.1, 50.2), postorbital_zygoma=(139.1, 29.8), meatus=(211.0, -1.5),
                 occipital_condyle=(243.9, 0.0), mandibular_condyle=(193.4, -8.6), angular_process=(201.0, -25.8),
                 inion=(253.7, 56.0), coronoid=(180.9, 29.7), otion=(217.2, -4.0))
CANINE_UP = ((32.4, -12.4), (39.8, -34.4))
DORSUM_HALF = ((47.1, 8.1), (62.9, 7.2), (84.0, 7.0), (105.0, 6.7))

# ============================================================================================ the anatomy between [E]
SMOOTH_IMG = 0.75                # the silhouettes' signed distances blurred (mm): the segmented edge's pixel wiggles
SMOOTH_PROF = 2.0                # the raw profiles along d smoothed (mm): the rasters' steps
SHAPE = dict(
    # ---- THE CRANIUM's profiles (Gaussian sigma, mm, on a 0.25 mm raster along d)
    top_sigma=3.0,               # the dorsal profile (the lateral's top: the nasal dorsum, the stop, the forehead, the crest)
    face_sigma=10.0,             # the face's widths: no wave shorter than ~40 mm survives (a 40 mm wave keeps 0.29)
    face_front=(20.0, 42.0),     # ahead of d 20 the face's width barely smoothed (1.5 mm: the incisor arc's blunt front),
                                 # fully face_sigma behind d 42 (a smoothstep between)
    face_open=10.0,              # the dorsal outline OPENED over this window first: the crowns' narrow loops and bumps
    # the cheek teeth's crowns overhanging the upper alveolar margin laterally in the dorsal view [E] (d, mm): the canine's
    # crown over its eminence, P1-P3 set in line, P4 and the molars' buccal cusps
    crown_out=((28.0, 0.0), (34.0, 1.0), (48.0, 1.0), (56.0, 0.5), (72.0, 0.5), (84.0, 2.0), (126.0, 2.0), (136.0, 0.0)),
    # the region behind the last molar (d, mm): the face's width falling to the pterygoids' (the palatine's back, the
    # pterygoid plates, the TOP outline's 35-37 at the carnassial is the crowns)
    under_w=((118.0, 33.5), (126.0, 31.5), (134.0, 23.0), (142.0, 15.5), (170.0, 15.0), (195.0, 16.0)),
    alveolar_sigma=5.0, occlusal_sigma=5.0,
    # the FACE family: the dorsum's half-width n (d, mm: DORSUM_HALF measured d 47-105, the nasal tips ahead [E], widening
    # over the orbits to the frontal's breadth), its camber (mm the edge stands under the midline), the dorsolateral and
    # the bottom roundings (k mm), the side's profile exponent (n + (W - n)(1 - (1 - s)^p): 1 a straight slope, 2 a
    # quarter-round: W2h's quarter ellipse stood the muzzle as a full box under a narrow top), the tooth row tooth_in mm
    # inside W over tooth_w mm under the alveolar line
    dorsum=((22.0, 5.0), (30.0, 5.5), (47.1, 8.1), (62.9, 7.2), (84.0, 7.0), (105.0, 6.7), (114.0, 13.0), (122.6, 26.5),
            (130.0, 28.0)),
    dorsum_sigma=4.0, arch_top=1.8, k_top=4.0, k_bot=2.0, side_p=1.7, tooth_in=1.5, tooth_w=2.5, front_d=13.6, k_front=3.0,
    # the FRONTAL family (over the orbits): the frontal's breadth wt (the fossa's medial edge from above d 128-160, its
    # postorbital processes at d 144; low-passed frontal_sigma: their sharp peak printed horns over the eyes at W2g), the
    # plate's thickness and step down to the orbit's medial wall mw (EntB 47 [P] / 2 at the orbits, LB 42 [P] / 2 behind
    # the processes), the orbit floor's height q_fl under which the section widens over step2 mm to the maxilla's tooth row
    # and the pterygoids (the face's W), the plate's camber
    frontal_w=((100.0, 7.0), (110.0, 11.0), (116.0, 19.0), (122.6, 26.5), (128.0, 27.5)),
    frontal_sigma=5.0, plate=6.0, step=16.0, frontal_arch=6.0, k_frontal=5.0,
    medial_wall=((104.0, 16.0), (114.0, 21.0), (124.0, 23.5), (140.0, 22.5), (165.0, 21.0), (190.0, 22.0)),
    orbit_floor=((100.0, 4.0), (114.0, 10.0), (126.0, 14.0), (140.0, 12.0), (160.0, 8.0), (190.0, 4.0)), step2=10.0,
    frontal_bot=((120.0, -22.0), (140.0, -19.0), (160.0, -16.0), (200.0, -14.0)),
    # the DOME family (the braincase): widest at dome_t of the height from its base (base_q), the base base_share as wide,
    # its breadth the fossa's medial edge (from above) to d 184, then widening to the mastoids (brain_w), then the occiput's
    # outline (TOP) behind d 216; the crest's half-width; low-passed brain_sigma
    crest_half=2.5, dome_t=0.40, base_share=0.82, base_q=((150.0, -6.0), (200.0, -10.0), (240.0, -14.0)),
    brain_w=((188.0, 30.5), (195.0, 33.0), (206.0, 38.0), (214.0, 39.5)), brain_sigma=4.0, k_dome=3.0,
    # the occiput's BACK: the lateral silhouette's back edge at each height (its rightmost d, the nuchal plane and the
    # condyles), a cap on the dome and the base, rounded k_back mm; the crest's floor fading out behind crest_end
    k_back=3.0, crest_end=(244.0, 252.0),
    # the families' weights along d: the face 1 -> 0 over face_w, the dome 0 -> 1 over dome_w, the frontal the rest
    face_w=(104.0, 134.0), dome_w=(140.0, 168.0),
    # ---- THE ARCHES: the tube's lateral and medial edges from above (d, |x|: the dorsal outline and the fossa's lateral
    # edge d 128-180 [P], the front root under the orbit and into the maxilla [E] from the outline), its dorsal and ventral
    # edges in profile (W2p: ARCH_DORSAL_W2P / ARCH_VENTRAL_W2P [P], MWNH 358's over the orbit; W2h-W2o s12092001's
    # ARCH_DORSAL / ARCH_VENTRAL, 4.3-6.6 mm higher there; extended forward and down into the maxilla [E]); the section's
    # roundness (an ellipse); the back root a chain of round cones ((d, q, |x|), radius) along the outline's curve medially
    # to the mastoid region [E] (W2p: its first cone 16 -> 14, under the lowered tube's top at d 176, 19.2)
    arch=dict(lat=((96.0, 31.0), (104.0, 37.5), (110.0, 40.0), (116.0, 44.0), (122.0, 48.8), (128.0, 52.5),
                   (134.0, 55.8), (140.0, 59.5), (146.0, 62.8), (152.0, 65.4), (158.0, 68.5), (164.0, 70.5),
                   (170.0, 71.3), (176.0, 71.2), (180.0, 70.5)),
              med=((96.0, 26.0), (104.0, 29.0), (110.0, 31.0), (116.0, 34.0), (122.0, 39.0), (128.0, 44.0),
                   (134.0, 48.0), (140.0, 50.2), (146.0, 55.8), (152.0, 60.6), (158.0, 63.8), (164.0, 64.7),
                   (170.0, 64.2), (176.0, 63.0), (180.0, 61.5)),
              dors=((96.0, 5.0), (104.0, 9.0), (110.0, 12.5), (116.4, 15.6), (122.9, 18.3), (133.9, 22.5),
                    (143.9, 24.9), (151.4, 24.9), (164.4, 23.1), (171.8, 20.6), (177.7, 18.6), (182.0, 17.2)),
              vent=((96.0, -8.0), (104.0, -6.0), (110.0, -3.0), (116.1, -0.5), (124.3, 3.7), (131.7, 7.6),
                    (143.8, 8.4), (157.1, 9.3), (169.2, 8.6), (176.1, 7.9), (182.0, 4.5)),
              d=(98.0, 182.0), taper=7.0, sigma=3.0, k=3.0),
    arch_back=(((176.0, 14.0, 67.0), 5.5), ((183.0, 10.0, 66.0), 5.8), ((189.0, 4.0, 60.5), 6.0),
               ((194.0, 0.5, 52.5), 6.0), ((199.0, -2.0, 44.0), 6.0), ((204.0, -3.0, 36.5), 5.5)),
    # ---- THE BASE (the basicranium): its bottom (the lateral silhouette's bottom behind the mandible [P], the pterygoids
    # ahead of it [E]; the notches between the bulla, the paroccipital process and the condyle bridged), its top inside
    # the dome, its half-width (the pterygoids [E]; the dorsal outline behind the arches [P]: the mastoids at d 206-216,
    # the occiput narrowing to the inion), the superellipse's exponent, its ends' taper
    base=dict(bot=((136.0, -20.0), (160.0, -17.0), (190.0, -15.0), (204.0, -15.0), (212.0, -19.0), (218.0, -18.5),
                   (226.0, -14.5), (234.0, -12.5), (241.0, -9.0), (247.0, -9.5), (252.0, -6.0)),
              top=((136.0, 6.0), (180.0, 10.0), (220.0, 14.0), (252.0, 20.0)),
              half=((136.0, 14.0), (170.0, 15.0), (190.0, 22.0), (200.0, 33.0), (206.0, 39.5), (214.0, 39.5),
                    (218.0, 35.0), (224.0, 28.0), (232.0, 22.0), (240.0, 18.5), (246.0, 15.0), (252.0, 9.0)),
              m=2.6, d=(136.0, 254.0), taper=8.0, sigma=3.0, k=4.0),
    # ---- THE ORBIT's rim and the socket's apex (the optic canal [E]); the socket's margin round the SPEC's globe (mm).
    # The rim is MWNH 358's (res_skull_s12092001.json lateral_mwnh358 at the SPEC scale: the lacrimal front, the
    # supraorbital margin, the arch's dorsal edge, the two postorbital processes; |x| from the dorsal outline and the
    # arch): the photos' palpebral fissure (CANTHI d 124 -> 145 in profile) lies inside it, 6-10 mm behind s12092001's
    # opening (d 109 -> 139: an individual difference), so the SPEC's globe sits in this socket
    rim=((114.5, 26.7, 26.5), (128.8, 49.6, 30.0), (144.6, 49.4, 35.5), (149.6, 25.4, 58.0), (132.7, 21.3, 48.0)),
    apex=(172.0, 20.0, 14.0), rim_in=1.2, periorbita=1.5, k_orbit=1.5,
    # the nasal aperture's cavity: (d, |x| half, q lo, q hi) rows from the aperture into the nasal cavity, its end faded.
    # W2i: MWNH 358's front shows the aperture ~0.46 of the face's breadth at the canines (~21.5 mm at C1B 47), from the
    # premaxillae over the incisors' roots (q ~ -6) to the nasals' tips (the dorsal profile's front, d 33-38), narrowing
    # downward; behind the tips the cavity stays >= 3 mm under the dorsal line (the nasal bones are its roof: a carve to
    # q 15-17 at d 40-48 took them and the skin dipped behind the nose)
    nasal=((22.0, 9.5, -6.5, 4.0), (27.0, 11.0, -6.0, 6.0), (33.0, 11.5, -5.0, 8.0), (40.0, 10.0, -4.0, 12.0),
           (48.0, 8.5, -3.0, 14.5), (58.0, 6.0, -1.5, 16.0)),
    nasal_end=(52.0, 62.0), k_nasal=1.5,
    # ---- THE MANDIBLE: CLOSED by jaw_close deg about the condyle (s12092001's photos hold the incisors edge to edge,
    # sk_w2h_readings.json "the mouth a few mm open"; a closed scissor bite overlaps them ~2.5 mm, the lower behind the
    # upper [E]: 2.5 mm over the 178 mm from the condyle to the incisors); the bodies' lateral face |x| (d, x_out) and
    # thickness (d, t) [E] (2-4 mm inside the upper tooth row: the closed bite; the condyles at canid.SKULL tmj's |x| 36
    # [P]); the lower alveolar margin under the occlusal line by the lower crowns' height (d, mm) [E]; the lower teeth's
    # band half-thickness; the ventral border at the CHIN on the profile photos' jaw line (canid_hull PROFILE, the photos'
    # consensus less their coat) plus the chin's tissue (d, mm) [L]: the skin and subcutis under the symphysis and the
    # mandible's ventral border (canid_skin DEPTHS chin, lip_lower, jaw_ventral), wherever the closed specimen's border
    # stands deeper (it does over d 20-66: by up to 5 mm at d 40), faded out behind chin_d
    jaw_close=0.8,
    mand_out=((14.0, 9.0), (25.0, 14.5), (40.0, 17.5), (60.0, 17.0), (80.0, 21.0), (100.0, 27.0), (120.0, 30.5),
              (150.0, 34.0), (175.0, 38.0), (195.0, 41.0), (205.0, 43.0)),
    mand_t=((14.0, 30.0), (30.0, 22.0), (45.0, 13.0), (90.0, 13.5), (140.0, 12.0), (160.0, 8.0), (205.0, 7.0)),
    crown_lo=((14.0, 9.0), (26.0, 9.0), (34.0, 6.0), (60.0, 7.0), (90.0, 10.0), (110.0, 12.0), (130.0, 9.0),
              (150.0, 5.0)),
    # the upper crowns' buccal cusps overlap the lower teeth (mm under / over the occlusal line): the closed scissor bite,
    # no groove along the tooth rows
    overlap_up=1.0, overlap_lo=1.5,
    teeth_half=3.6, mand_m=3.0, mand_d=(14.5, 186.0), mand_taper=5.0, mand_sigma=2.0,
    chin_tissue=((12.0, 3.5), (30.0, 4.0), (50.0, 4.5), (95.0, 6.0)), chin_d=(66.0, 86.0), k_chin=2.0,
    # the ramus's outline in profile (d, q) [E] through the measured coronoid tip, condyle and angular process; its plate's
    # half-thickness and rounding
    ramus=((146.0, -30.0), (156.0, -10.0), (166.0, 8.0), (174.0, 22.0), (180.9, 29.7), (186.0, 28.0), (189.0, 18.0),
           (190.5, 5.0), (191.5, -3.0), (197.0, -4.0), (199.5, -9.0), (197.5, -14.0), (198.5, -21.0), (203.0, -25.0),
           (203.5, -32.0), (196.0, -39.0), (160.0, -52.0)),
    ramus_half=3.2, k_ramus=3.0,
    condyle=dict(c=(193.4, -8.6), x=(26.0, 46.0), r=5.5),
    k_mand=1.0,
    # ---- THE TEETH: the upper canine (alveolus -> tip measured, |x| [E]), radii; the lower canine [E]
    canine_up=dict(x=(19.0, 21.0), r=(5.4, 1.4)), canine_lo=((24.5, -33.0, 13.0), (22.0, -13.5, 15.5), 4.8, 1.3),
    # the parts' smooth unions (mm)
    k=1.5,
)


# ============================================================================================ 2D rasters
def _multi_poly_sdf(outer, holes, lo, hi, res):
    """the signed distance (mm) of the region inside every polygon of `outer` (union) minus `holes` (union) on the
    raster [lo, hi] at res: (image, lo, res)"""
    from matplotlib.path import Path
    from scipy import ndimage as nd
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    nu, nv = (np.ceil((hi - lo) / res).astype(int) + 1)
    U, V = np.meshgrid(lo[0] + np.arange(nu) * res, lo[1] + np.arange(nv) * res, indexing='ij')
    pts = np.column_stack([U.ravel(), V.ravel()])
    inside = np.zeros(len(pts), bool)
    for P in outer:
        inside |= Path(np.asarray(P, float)).contains_points(pts)
    for P in holes:
        inside &= ~Path(np.asarray(P, float)).contains_points(pts)
    inside = inside.reshape(nu, nv)
    sd = (nd.distance_transform_edt(~inside) - nd.distance_transform_edt(inside) + np.where(inside, 0.5, -0.5)) * res
    return sd.astype(np.float32), lo, res


def _sample(img, u, v):
    from scipy import ndimage as nd
    a, lo, res = img
    fu = (np.asarray(u, float) - lo[0]) / res
    fv = (np.asarray(v, float) - lo[1]) / res
    cu = np.clip(fu, 0, a.shape[0] - 1)
    cv = np.clip(fv, 0, a.shape[1] - 1)
    s = nd.map_coordinates(a, [cu.ravel(), cv.ravel()], order=1, mode='nearest').reshape(np.shape(u))
    return s + np.hypot(fu - cu, fv - cv) * res


def _interp(rows, d):
    """a table (d, v) at d: PCHIP through the rows (no kinks to print as ridges), held flat past its ends"""
    from scipy.interpolate import PchipInterpolator
    r = np.asarray(rows, float)
    if len(r) < 3:
        return np.interp(d, r[:, 0], r[:, 1])
    return PchipInterpolator(r[:, 0], r[:, 1], extrapolate=False)(np.clip(d, r[0, 0], r[-1, 0]))


def _smax(a, b, k):
    if k <= 0:
        return np.maximum(a, b)
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return a * h + b * (1.0 - h) + k * h * (1.0 - h)


def _smin(a, b, k):
    return -_smax(-a, -b, k)


def _smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _dsmooth01(t):
    """the smoothstep's derivative (0 outside [0, 1])"""
    tc = np.clip(t, 0.0, 1.0)
    return 6.0 * tc * (1.0 - tc)


def _ellipse(u, v, a, b):
    """iq's bound-corrected ellipse estimate (the ellipsoid's in 2D): u, v offsets, a, b the half-axes"""
    a = np.maximum(a, 1e-3)
    b = np.maximum(b, 1e-3)
    k0 = np.sqrt((u / a) ** 2 + (v / b) ** 2)
    k1 = np.sqrt((u / (a * a)) ** 2 + (v / (b * b)) ** 2)
    return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -np.minimum(a, b))


def _superellipse(u, v, a, b, m):
    """a superellipse |u/a|^m + |v/b|^m = 1 (u, v offsets, a, b half-axes): its level (rho - 1) over |grad rho|, the
    first-order distance"""
    a = np.maximum(a, 1e-3)
    b = np.maximum(b, 1e-3)
    au, av = np.abs(u) / a, np.abs(v) / b
    s = au ** m + av ** m
    rho = np.maximum(s ** (1.0 / m), 1e-6)
    g1 = rho ** (1.0 - m) * au ** (m - 1.0) / a
    g2 = rho ** (1.0 - m) * av ** (m - 1.0) / b
    gn = np.sqrt(g1 * g1 + g2 * g2)
    return np.where(gn > 1e-9, (rho - 1.0) / np.maximum(gn, 1e-9), -np.minimum(a, b))


def _seg_dist(P, a, b):
    """the distance from points P (n, 3) to the segment a-b"""
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


class Skull:
    """the skull's rasters and smooth 1D profiles, built once (__init__), then field() at any points"""

    def __init__(self):
        from scipy import ndimage as nd
        from scipy.interpolate import PchipInterpolator
        sh = SHAPE
        r = 0.25
        # the silhouettes' signed distances, blurred SMOOTH_IMG mm: the segmented outlines carry ~0.5 mm wiggles
        sm = SMOOTH_IMG / r
        a, lo, res = _multi_poly_sdf([LAT], [], (-20.0, -80.0), (280.0, 90.0), r)
        self.lat = (nd.gaussian_filter(a, sm, mode='nearest'), lo, res)
        top = np.asarray(TOP_OUT, float)
        full = np.vstack([top, (top * [1.0, -1.0])[-2:0:-1]])
        holes = []
        for h in TOP_HOLES:
            h = np.asarray(h, float)
            holes += [h, h * [1.0, -1.0]]
        a, lo, res = _multi_poly_sdf([full], holes, (-20.0, -100.0), (280.0, 100.0), r)
        self.top = (nd.gaussian_filter(a, sm, mode='nearest'), lo, res)
        # ---- the raw profiles along d (every 0.25 mm): the lateral's top and bottom, the dorsal outline's half-width,
        # the run from the midline (the outline's loops round the crowns and the fossa excluded)
        self.dd = dd = np.arange(0.0, 270.0, 0.25)
        qq = np.arange(-80.0, 90.0, 0.25)
        xx = np.arange(0.0, 100.0, 0.25)
        D, Q = np.meshgrid(dd, qq, indexing='ij')
        L = _sample(self.lat, D, Q) < 0
        q_top = np.array([qq[np.nonzero(c)[0].max()] if c.any() else np.nan for c in L])
        q_bot = np.array([qq[np.nonzero(c)[0].min()] if c.any() else np.nan for c in L])
        # the occiput's back: the lateral's rightmost d at each height (behind d 200), low-passed 2 mm along q
        back = np.array([dd[np.nonzero(c & (dd > 200.0))[0].max()] if (c & (dd > 200.0)).any() else np.nan for c in L.T])
        okb = np.isfinite(back)
        self.qq = qq
        self.d_back = nd.gaussian_filter1d(np.interp(qq, qq[okb], back[okb]), 2.0 / r, mode='nearest')
        D, X = np.meshgrid(dd, xx, indexing='ij')
        T = _sample(self.top, D, X) < 0
        w_out = np.array([xx[np.nonzero(c)[0].max()] if c.any() else np.nan for c in T])
        w_mid, h_lat = [], []
        for c in T:
            if not c.any() or not c[0]:
                w_mid.append(np.nan)
                h_lat.append(np.nan)
                continue
            j = int(np.argmax(~c)) if (~c).any() else len(c)
            w_mid.append(xx[j - 1])
            rest = c[j:]
            h_lat.append(xx[j + int(np.argmax(rest))] if rest.any() else np.nan)
        self.raw = dict(q_top=q_top, q_bot=q_bot, w_out=w_out, w_mid=np.array(w_mid), h_lat=np.array(h_lat))

        def filled(v):
            v = np.asarray(v, float)
            ok = np.isfinite(v)
            return np.interp(np.arange(len(v)), np.nonzero(ok)[0], v[ok])

        def lp(v, sigma):
            return nd.gaussian_filter1d(filled(v), sigma / r, mode='nearest')

        def table(rows, sigma=0.0):
            rw = np.asarray(rows, float)
            v = PchipInterpolator(rw[:, 0], rw[:, 1], extrapolate=False)(np.clip(dd, rw[0, 0], rw[-1, 0]))
            return lp(v, sigma) if sigma > 0 else v
        P = {}
        # the dorsal profile
        P['qt'] = lp(q_top, sh['top_sigma'])
        # the alveolar and occlusal lines (the occlusal rising behind the last molar to the jaw's hinge)
        P['qa'] = table(ALVEOLAR, sh['alveolar_sigma'])
        oc = np.vstack([[[10.0, -24.5], [20.7, -25.9]], np.asarray(OCCLUSAL, float), [[193.4, -8.6], [260.0, -8.6]]])
        P['qo'] = lp(np.interp(dd, oc[:, 0], oc[:, 1]), sh['occlusal_sigma'])
        # THE FACE's width at the alveolar line: the run from the midline (the outline without its crown loops) to d 112,
        # opened (the crowns' narrow bumps), less the crowns' overhang, the region behind the last molar from under_w;
        # low-passed face_sigma behind face_front (the blunt incisor arc ahead barely smoothed)
        wm = filled(np.where(dd <= 112.0, np.array(w_mid), np.nan))
        wm = np.where(dd < 13.9, 0.0, wm)
        n_open = max(1, int(round(sh['face_open'] / r)))
        wo = nd.grey_opening(wm, size=n_open, mode='nearest')
        wo = wo - table(sh['crown_out'])
        under = table(sh['under_w'])
        t_u = _smooth01((dd - 112.0) / 14.0)
        wf = (1.0 - t_u) * wo + t_u * under
        w_lo = nd.gaussian_filter1d(wf, 1.5 / r, mode='nearest')
        w_hi = nd.gaussian_filter1d(wf, sh['face_sigma'] / r, mode='nearest')
        t_f = _smooth01((dd - sh['face_front'][0]) / (sh['face_front'][1] - sh['face_front'][0]))
        P['W'] = np.maximum((1.0 - t_f) * w_lo + t_f * w_hi, 0.0)
        P['n'] = np.minimum(table(sh['dorsum'], sh['dorsum_sigma']), 0.85 * np.maximum(P['W'], 0.5))
        # THE FRONTAL's breadth: the face's dorsum widening over the orbits into the fossa's medial edge (d 128-160, the
        # postorbital processes), behind it the braincase (low-passed frontal_sigma)
        fw = np.asarray(sh['frontal_w'], float)
        sel = (dd >= 129.0) & (dd <= 184.0)
        rows_f = np.vstack([fw, np.column_stack([dd[sel][::8], np.array(w_mid)[sel][::8]])])
        P['wt'] = table(rows_f, sh['frontal_sigma'])
        P['mw'] = table(sh['medial_wall'], 4.0)
        P['qfl'] = table(sh['orbit_floor'], 4.0)
        P['qbf'] = table(sh['frontal_bot'], 4.0)
        # THE BRAINCASE's breadth: the fossa's medial edge to d 184, the mastoids, then the occiput's outline (TOP)
        sel2 = (dd >= 216.0) & (dd <= 255.0)
        rows_b = np.vstack([np.column_stack([dd[sel][::8], np.array(w_mid)[sel][::8]]), np.asarray(sh['brain_w'], float),
                            np.column_stack([dd[sel2][::8], w_out[sel2][::8]]), [[256.0, 0.5]]])
        rows_b = rows_b[np.argsort(rows_b[:, 0])]
        P['bw'] = table(rows_b, sh['brain_sigma'])
        P['qb'] = table(sh['base_q'], 4.0)
        # the ARCH's tube
        ar = sh['arch']
        P['a_lat'] = table(ar['lat'], ar['sigma'])
        P['a_med'] = table(ar['med'], ar['sigma'])
        P['a_dors'] = table(ar['dors'], ar['sigma'])
        P['a_vent'] = table(ar['vent'], ar['sigma'])
        # the BASE
        bs = sh['base']
        P['b_bot'] = table(bs['bot'], bs['sigma'])
        P['b_top'] = table(bs['top'], bs['sigma'])
        P['b_half'] = table(bs['half'], bs['sigma'])
        # the MANDIBLE (its own frame: the photographed pose; field() rotates the query points)
        P['m_out'] = table(sh['mand_out'], sh['mand_sigma'])
        P['m_t'] = table(sh['mand_t'], sh['mand_sigma'])
        P['m_top'] = P['qo'] - table(sh['crown_lo'], sh['mand_sigma'])
        # the ventral border: the lateral's bottom (its front the chin's sloped face), raised at the chin to the profile
        # photos' jaw line plus the chin's tissue (that target taken into the photographed pose by the closing rotation's
        # rise at each d)
        from . import canid_hull as CH_
        prof = np.asarray(CH_.PROFILE, float)[16:52]
        q_ph = np.interp(dd, prof[:, 0], prof[:, 1])
        rise = (193.4 - dd) * np.tan(np.radians(sh['jaw_close']))
        target = q_ph + table(sh['chin_tissue']) - rise
        w_chin = 1.0 - _smooth01((dd - sh['chin_d'][0]) / (sh['chin_d'][1] - sh['chin_d'][0]))
        vb = lp(q_bot, 1.0)
        vb_fix = _smax(vb, target, sh['k_chin'])
        P['m_vent'] = lp((1.0 - w_chin) * vb + w_chin * vb_fix, sh['mand_sigma'])
        P['m_raise'] = P['m_vent'] - lp(vb, sh['mand_sigma'])
        # the profiles' slopes along d (the arch's section stretch)
        for k_ in ('a_lat', 'a_med', 'a_dors', 'a_vent'):
            P['d_' + k_] = np.gradient(P[k_], r)
        self.P = P
        self.ramus_img = _multi_poly_sdf([sh['ramus']], [], (130.0, -70.0), (215.0, 40.0), 0.25)

    def pr(self, name, d):
        return np.interp(d, self.dd, self.P[name])

    # ---------------------------------------------------------------------------------------- the cranium's families
    def face(self, d, q, x):
        """the muzzle's section (module docstring, FACE)"""
        sh = SHAPE
        qt, qa, qo, n, W = (self.pr(k, d) for k in ('qt', 'qa', 'qo', 'n', 'W'))
        qe = qt - sh['arch_top']
        hgt = np.maximum(qe - qa, 6.0)
        s = (qe - q) / hgt
        sc = np.clip(s, 0.0, 1.0)
        p = sh['side_p']
        g = 1.0 - (1.0 - sc) ** p
        dg = p * (1.0 - sc) ** (p - 1.0) * ((s > 0.0) & (s < 1.0))
        tt = (qa - q) / sh['tooth_w']
        hw = n + (W - n) * g - sh['tooth_in'] * _smooth01(tt)
        dhw = -(W - n) * dg / hgt + sh['tooth_in'] * _dsmooth01(tt) / sh['tooth_w']
        side = (x - hw) / np.sqrt(1.0 + dhw * dhw)
        top = q - (qt - sh['arch_top'] * np.minimum((x / np.maximum(n, 1.0)) ** 2, 2.25))
        f = _smax(side, top, sh['k_top'])
        # the upper crowns reach overlap_up mm under the occlusal line (the buccal cusps over the lower teeth)
        f = _smax(f, (qo - sh['overlap_up']) - q, sh['k_bot'])
        return _smax(f, sh['front_d'] - d, sh['k_front'])

    def frontal(self, d, q, x):
        """the interorbital and postorbital section (module docstring, FRONTAL)"""
        sh = SHAPE
        qt, wt, mw, qfl, u, qbf = (self.pr(k, d) for k in ('qt', 'wt', 'mw', 'qfl', 'W', 'qbf'))
        t1 = (q - (qt - sh['plate'] - sh['step'])) / sh['step']
        t2 = (qfl - q) / sh['step2']
        hw = mw + (wt - mw) * _smooth01(t1) + (u - mw) * _smooth01(t2)
        dhw = (wt - mw) * _dsmooth01(t1) / sh['step'] - (u - mw) * _dsmooth01(t2) / sh['step2']
        side = (x - hw) / np.sqrt(1.0 + dhw * dhw)
        tq = qt - sh['frontal_arch'] * np.minimum((x / np.maximum(wt, 1.0)) ** 2, 2.25)
        f = _smax(side, q - tq, sh['k_frontal'])
        return _smax(f, qbf - q, sh['k_bot'])

    def dome(self, d, q, x):
        """the braincase's section (module docstring, DOME)"""
        sh = SHAPE
        qt, qb, bw = (self.pr(k, d) for k in ('qt', 'qb', 'bw'))
        H = np.maximum(qt - qb, 10.0)
        t = (q - qb) / H
        dt_ = sh['dome_t']
        uu = np.clip((t - dt_) / (1.0 - dt_), 0.0, 0.999)
        upper = np.sqrt(1.0 - uu * uu)
        d_up = -uu / np.sqrt(1.0 - uu * uu) / (1.0 - dt_)
        lower = sh['base_share'] + (1.0 - sh['base_share']) * _smooth01(t / dt_)
        d_lo = (1.0 - sh['base_share']) * _dsmooth01(t / dt_) / dt_
        prof = np.minimum(upper, lower)
        dprof = np.where(upper < lower, d_up, d_lo)
        hw = bw * prof
        dhw = np.clip(bw * dprof / H, -25.0, 25.0)
        # the crest: never narrower than crest_half (a smooth floor), fading out over the occiput
        ce = sh['crest_end']
        hw_s = _smax(hw, sh['crest_half'] * (1.0 - _smooth01((d - ce[0]) / (ce[1] - ce[0]))), 1.0)
        side = (x - hw_s) / np.sqrt(1.0 + dhw * dhw)
        f = _smax(side, q - qt, sh['k_dome'])
        f = _smax(f, qb - q, sh['k_bot'])
        return _smax(f, d - np.interp(q, self.qq, self.d_back), sh['k_back'])

    def cranium(self, P):
        """the cranium's loft: the three families' fields morphed along d (weights smoothsteps over 28-30 mm)"""
        sh = SHAPE
        d, q, x = P[:, 0], P[:, 1], np.abs(P[:, 2])
        wf = 1.0 - _smooth01((d - sh['face_w'][0]) / (sh['face_w'][1] - sh['face_w'][0]))
        wd = _smooth01((d - sh['dome_w'][0]) / (sh['dome_w'][1] - sh['dome_w'][0]))
        wr = np.clip(1.0 - wf - wd, 0.0, 1.0)
        f = np.zeros(len(d))
        for w, fn in ((wf, self.face), (wr, self.frontal), (wd, self.dome)):
            m = w > 1e-6
            if m.any():
                f[m] += w[m] * fn(d[m], q[m], x[m])
        return f

    def arch(self, P):
        """the zygomatic arches: the swept elliptical tube (module docstring, ARCHES) and its back root's chain"""
        from .canid_hull import sd_roundcone_np
        sh = SHAPE
        ar = sh['arch']
        d, q, x = P[:, 0], P[:, 1], np.abs(P[:, 2])
        lat, med, dors, vent = (self.pr(k, d) for k in ('a_lat', 'a_med', 'a_dors', 'a_vent'))
        xc, qc = 0.5 * (lat + med), 0.5 * (dors + vent)
        sx = 0.5 * (self.pr('d_a_lat', d) + self.pr('d_a_med', d))
        sq = 0.5 * (self.pr('d_a_dors', d) + self.pr('d_a_vent', d))
        taper = _smooth01((d - ar['d'][0]) / ar['taper']) * _smooth01((ar['d'][1] - d) / ar['taper'])
        a = 0.5 * (lat - med) * np.sqrt(1.0 + sx * sx) * taper
        b = 0.5 * (dors - vent) * np.sqrt(1.0 + sq * sq) * taper
        f = _ellipse(x - xc, q - qc, a, b)
        f = np.maximum(f, np.maximum(ar['d'][0] - d, d - ar['d'][1]))
        Pm = np.column_stack([d, q, x])
        rows = sh['arch_back']
        for (c0, r0), (c1, r1) in zip(rows[:-1], rows[1:]):
            f = np.minimum(f, sd_roundcone_np(Pm, np.asarray(c0, float), np.asarray(c1, float), r0, r1))
        return f

    def base(self, P):
        """the basicranium's superellipse loft (module docstring, BASE)"""
        bs = SHAPE['base']
        d, q, x = P[:, 0], P[:, 1], np.abs(P[:, 2])
        bot, top, half = (self.pr(k, d) for k in ('b_bot', 'b_top', 'b_half'))
        taper = _smooth01((d - bs['d'][0]) / bs['taper']) * _smooth01((bs['d'][1] - d) / bs['taper'])
        hh = 0.5 * (top - bot)
        f = _superellipse(x, q - 0.5 * (top + bot), half * taper, hh * np.maximum(taper, 0.3), bs['m'])
        f = np.maximum(f, np.maximum(bs['d'][0] - d, d - bs['d'][1]))
        return _smax(f, d - np.interp(q, self.qq, self.d_back), SHAPE['k_back'])

    def occlusal(self, d):
        """the occlusal line (d, q), low-passed: the bite measured from the incisors to the last molar, rising behind to
        the jaw's hinge (the mandibular condyle)"""
        return self.pr('qo', d)

    def dorsum(self, d):
        """the face's dorsum half-width (SHAPE dorsum)"""
        return self.pr('n', d)

    def orbit_carve(self, P, eye_c, eye_r):
        """THE ORBIT's socket (positive inside the cut): under the supraorbital margin, inside the measured rim, from
        the rim's plane outward and as a cone in to the apex, and round the SPEC's globe (periorbita)"""
        sh = SHAPE
        R = np.asarray(sh['rim'], float)
        out = []
        for sx in (1.0, -1.0):
            Rs = R * [1.0, 1.0, sx]
            c = Rs.mean(0)
            u, s, vt = np.linalg.svd(Rs - c)
            nrm = vt[2]
            if nrm @ np.array([-1.0, 0.0, sx]) < 0:
                nrm = -nrm
            e1 = vt[0]
            e2 = np.cross(nrm, e1)
            a1 = np.abs((Rs - c) @ e1).max() - sh['rim_in']
            a2 = np.abs((Rs - c) @ e2).max() - sh['rim_in']
            W = P - c
            h = W @ nrm
            ap = np.asarray(sh['apex'], float) * [1.0, 1.0, sx]
            depth = float(-(ap - c) @ nrm)
            sc = np.clip(1.0 + np.minimum(h, 0.0) / max(depth, 1.0), 0.02, 1.0)
            ell = 1.0 - np.sqrt(((W @ e1) / (a1 * sc)) ** 2 + ((W @ e2) / (a2 * sc)) ** 2)
            ell = ell * np.minimum(a1, a2) * sc
            cone = np.minimum(ell, h + depth)
            ec = np.asarray(eye_c, float) * [1.0, 1.0, sx]
            globe = (eye_r + sh['periorbita']) - np.linalg.norm(P - ec, axis=1)
            out.append(np.maximum(cone, globe))
        # W2i: never medial of the orbit's medial wall (the frontal, the palatine, the sphenoid: bone), so the cone toward
        # the apex does not hollow the braincase's side behind the eye (the W2i s2 probe's d 152 section necked to 7 mm)
        mw = self.pr('mw', P[:, 0])
        return _smin(np.maximum(out[0], out[1]), np.abs(P[:, 2]) - (mw - 1.0), 2.0)

    def nasal_carve(self, P):
        """the nasal aperture's cavity behind the incisive bones and the nasal tips (positive inside the cut), its end
        shrunk smoothly over SHAPE nasal_end"""
        sh = SHAPE
        r = np.asarray(sh['nasal'], float)
        d, q, x = P[:, 0], P[:, 1], np.abs(P[:, 2])
        sc = 1.0 - 0.9 * _smooth01((d - sh['nasal_end'][0]) / (sh['nasal_end'][1] - sh['nasal_end'][0]))
        hx = np.interp(d, r[:, 0], r[:, 1]) * sc
        lo = np.interp(d, r[:, 0], r[:, 2])
        hi = np.interp(d, r[:, 0], r[:, 3])
        hq = 0.5 * (hi - lo) * sc
        cq = 0.5 * (hi + lo)
        return -_ellipse(x, q - cq, hx, hq) - 6.0 * _smooth01((d - sh['nasal_end'][1]) / 4.0)

    def _closed(self, P):
        """query points carried into the photographed mandible's pose (the inverse of the closing rotation)"""
        cd, cq = SHAPE['condyle']['c']
        th = np.radians(SHAPE['jaw_close'])
        c, s = np.cos(th), np.sin(th)
        dd, dq = P[:, 0] - cd, P[:, 1] - cq
        return np.column_stack([cd + c * dd - s * dq, cq + s * dd + c * dq, P[:, 2]])

    def mandible(self, P):
        """the mandible, closed (module docstring, MANDIBLE)"""
        sh = SHAPE
        Pc = self._closed(P)
        d, q, x = Pc[:, 0], Pc[:, 1], np.abs(Pc[:, 2])
        xo, t, vent, top, qo = (self.pr(k, d) for k in ('m_out', 'm_t', 'm_vent', 'm_top', 'qo'))
        xc = xo - 0.5 * t
        taper = _smooth01((d - sh['mand_d'][0]) / sh['mand_taper']) * _smooth01((sh['mand_d'][1] - d) / 12.0)
        body = _superellipse(x - xc, q - 0.5 * (top + vent), 0.5 * t * np.maximum(taper, 0.2),
                             0.5 * np.maximum(top - vent, 2.0) * np.maximum(taper, 0.2), sh['mand_m'])
        body = np.maximum(body, np.maximum(sh['mand_d'][0] - 2.0 - d, d - sh['mand_d'][1]))
        qtop_ = qo + sh['overlap_lo']
        teeth = _superellipse(x - xc, q - 0.5 * (top + qtop_), sh['teeth_half'] * np.maximum(taper, 0.2),
                              0.5 * np.maximum(qtop_ - top, 1.0) + 0.5, 4.0)
        teeth = np.maximum(teeth, np.maximum(sh['mand_d'][0] - 1.0 - d, d - 150.0))
        rp = _sample(self.ramus_img, d, q)
        plate = np.abs(x - (xo - sh['ramus_half'])) - sh['ramus_half']
        ramus = _smax(rp, plate, sh['k_ramus'])
        cd = sh['condyle']
        Pm = np.column_stack([d, q, x])
        cyl = _seg_dist(Pm, np.array([cd['c'][0], cd['c'][1], cd['x'][0]]),
                        np.array([cd['c'][0], cd['c'][1], cd['x'][1]])) - cd['r']
        f = _smin(body, teeth, 1.0)
        f = _smin(f, ramus, sh['k_ramus'])
        return _smin(f, cyl, 1.5)

    def teeth(self, P):
        from .canid_hull import sd_roundcone_np
        sh = SHAPE
        Pm = np.column_stack([P[:, 0], P[:, 1], np.abs(P[:, 2])])
        (a0, a1), (b0, b1) = CANINE_UP
        cu = sh['canine_up']
        up = sd_roundcone_np(Pm, np.array([a0, a1, cu['x'][0]]), np.array([b0, b1, cu['x'][1]]), cu['r'][0], cu['r'][1])
        a, b, ra, rb = sh['canine_lo']
        Pc = self._closed(P)
        Pcm = np.column_stack([Pc[:, 0], Pc[:, 1], np.abs(Pc[:, 2])])
        lo = sd_roundcone_np(Pcm, np.asarray(a, float), np.asarray(b, float), ra, rb)
        return np.minimum(up, lo)

    def field(self, P, eye_c, eye_r):
        """the skull at points P (n, 3) (d, q, x) mm: approximate signed distance (mm)"""
        sh = SHAPE
        P = np.asarray(P, float)
        # the cranium and the base carved by the orbits and the nasal aperture, THEN the arches (the arch's dorsal edge
        # is the orbit's ventrolateral rim: the socket's cone cut it at W2i s1), the mandible and the teeth
        f = _smin(self.cranium(P), self.base(P), sh['base']['k'])
        f = _smax(f, self.orbit_carve(P, eye_c, eye_r), sh['k_orbit'])
        f = _smax(f, self.nasal_carve(P), sh['k_nasal'])
        f = _smin(f, self.arch(P), sh['arch']['k'])
        f = _smin(f, self.mandible(P), sh['k_mand'])
        return np.minimum(f, self.teeth(P))

    def parts(self, P, eye_c, eye_r):
        """each part's field at P (the review's colouring): dict name -> field"""
        P = np.asarray(P, float)
        return dict(cranium=self.cranium(P), arch=self.arch(P), base=self.base(P), mandible=self.mandible(P),
                    teeth=self.teeth(P))


def eye_globe(spec):
    """the SPEC's eyeball in the frame (mm): the left centre (d, q, x) and the radius"""
    from . import canid
    L = canid.landmarks_pqx(spec)
    e = np.asarray(L['eye_L'], float)
    npm = 1000.0 * canid.nose_p(spec)
    return np.array([npm - 1000.0 * e[0], 1000.0 * e[1], 1000.0 * e[2]]), 1000.0 * spec['eye']['ball_r']


GRID = dict(lo=(6.0, -70.0, -82.0), hi=(262.0, 74.0, 82.0))


def skull_key(spec, extra=None):
    """the skull's inputs for the cache keys (the tables, the anatomy, the profile photos' jaw line it reads, the eye)"""
    from . import canid_hull as CH_
    eye_c, eye_r = eye_globe(spec)
    k = dict(v=VERSION, lat=LAT, top=TOP_OUT, holes=TOP_HOLES, occ=OCCLUSAL, alv=ALVEOLAR, ad=ARCH_DORSAL,
             av=ARCH_VENTRAL, lm=LANDMARKS, can=CANINE_UP, dors=DORSUM_HALF, shape=SHAPE, sm=(SMOOTH_IMG, SMOOTH_PROF),
             prof=CH_.PROFILE[16:52], eye=(eye_c.tolist(), eye_r), ad2=ARCH_DORSAL_W2P, av2=ARCH_VENTRAL_W2P)
    if extra:
        k.update(extra)
    return k


def skull_volume(spec, h=0.5, log=print):
    """the skull on a grid at h mm (the frame, mm), redistanced (each voxel's distance to the zero set by the EDT foot
    point): dict(phi, lo, h); cached by the tables, the anatomy and the eye"""
    from ..hullflow import redistance
    eye_c, eye_r = eye_globe(spec)
    key = cache_key(skull_key(spec, dict(h=h, grid=GRID)))

    def build():
        import time
        t0 = time.time()
        S = Skull()
        G = Grid(GRID['lo'], GRID['hi'], h)
        phi = np.empty(G.n, np.float32)
        Qm, Xm = np.meshgrid(G.q, G.x, indexing='ij')
        for i in range(G.n[0]):
            P = np.column_stack([np.full(Qm.size, G.d[i]), Qm.ravel(), Xm.ravel()])
            phi[i] = S.field(P, eye_c, eye_r).reshape(Qm.shape)
        log(f'[skull] field on {G.n} at {h} mm in {time.time() - t0:.0f}s')
        phi = redistance(phi, h)
        log(f'[skull] redistanced ({time.time() - t0:.0f}s)')
        return dict(phi=phi, lo=G.lo, h=np.float64(h))
    return cached('wolf_skull', key, build, log)
