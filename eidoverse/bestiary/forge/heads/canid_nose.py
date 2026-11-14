"""W2l (the HEAD builder, 10-28): THE CANID NOSE RE-LAID ON THE CLAY'S OWN FRAME, for heads/canid_cage.py.

W2f-W2k carried the leather and the nostrils from ONE photo (w12, a winter head-front) through its solved camera (49 deg
over the palate). That camera puts the leather's top 16-24 mm back on the bridge where the four head profiles (PROFILE)
put it at d 8.9, and w12's traced leather is 40.7 mm tall in its image where the profiles' leather projects to ~22: each
photo is a different wolf, and the solved camera's pitch absorbs the difference in the eyes-to-nose geometry. Carried
onto a near-vertical front, w12's openings came out 11.4 x 11.4 mm, high in a flat-fronted block with a flat top and a
right-angle top-front edge: from the front, a pig's snout disc (the W2k fresh eyes).

So the vertical layout comes from the clay's own measure (the lead's W2l call: "the skull and the profiles are the
consistent measure of this animal; use the photos for shape, rescaled per feature where their scale disagrees"):
  the MIDLINE PROFILE  canid_hull PROFILE's leather (the mean of four head profiles: the top at (8.9, 23.1), the tip at
                       (-2.5, 11.1), the bottom at (8.0, -5.4)), the bridge behind it [P]
  the PLAN             TOP's rounded front, 22 mm half wide (the fronts: 41-48 mm wide at IO 80) [P]
  the FRONT OUTLINE'S  SHAPE from near-level fronts, normalised by the leather's own width and height (research/wolf_web/
                       nose_w2l_wolves: 004 'Loup gris', 005 'Loup portrait', 002, 015; W/H 1.16-1.58 between wolves):
                       a superellipse, its widest at mid-height, the top half rounder (exponent ~2.2) than the bottom
                       (~2.6) [P, the photos, my tracing on gridded crops]
THE CAP (cap_field): the leather and the muzzle's front as a LOFT of sections across d: from the tip to the dorsal
border (d_b) each section is the front outline's superellipse at the plan's half width a(d) between the profile's dorsal
and ventral lines (so the front is broad and nearly flat across, rounded in profile, and the top a convex dome sloping
back: no planes, no edge); behind the border the sections MORPH into the skin's own section at d_s (so the muzzle behind
the leather keeps its width at every height and narrows into the bridge without a waist), the top line following
PROFILE's bridge with a soft dip behind the border (the leather's edge stands a little proud of the haired skin: the
profiles' 23.1 at d 8.9 against 21.2 at d 12, as a saddle under 1 mm), then sinking inside the skin. The loft is an
inside test on a fine local grid, signed by Euclidean distance transforms, lightly blurred and sampled onto the
reference's grid; canid_cage unions it with the skin.
THE BORDER (border_curve): the same front outline carried back onto the reference at PROFILE's depths (BORDER), in
canid_cage.trace_leather's old form for the leather's open tube.
THE NOSTRIL (nostril_curves, nostril_chart, level_frame): a COMMA in a level front chart on the clay's frame (NOSTRIL_L):
the round head medially, the slit curving out and down under the alar fold, low on the front, wider than tall; canid_cage
.place_nostril lays its tube's rings along the chart's line of sight (+d).
W2l's choice for w12's camera (the lead: "decide how (or whether) w12's camera is used for the leather's vertical
layout"): NOT used for the nose. The fronts' solved cameras sit 36-49 deg over the palate and their pitch absorbs each
wolf's own eyes-to-nose geometry: in them the photos' leathers stand 1.15-1.9 x the profiles' leather's projected height,
the excess growing with the camera's pitch (005 16 deg: 31.8 against 27.6 mm; 004 34: 38 against 24.8; w12 49: 40.7
against 21.7), so a leather traced in one of them and carried onto the clay lands too tall and too far back on the bridge.
The photos give shapes and fractions, measured in their own nose's box; the profiles and the plan give the box.
W2t (the lead's NOSE call: "not accepted from a level camera (a game camera sits near level)"): the comma LOW on the pad
under the dome, its head full and round, its tail out and down under the wing (NOSTRIL_L's W2t note), and the PHILTRUM
carved into the cap (RHINARIUM philtrum, cap_field), judged on six traced fronts in the leather's own box at each photo's
solved camera (work/bestiary/wolf/check_w2t_nose: nose_eval.py, sheet.py). w12's camera no longer fits: its traced
openings sit, through its eyes-registered camera, on the clay's UPPER front face, where the dome round the tip does not
hide them; openings low on the pad, as the near-level fronts, both head profiles and f21 (44 deg) show them, sit under
that dome from 48 deg (check_w2t_nose/out/diag_w12_*.png).
W2u (the lead's NOSE call: "the CONSTRUCTION, a broad box of a pad ... and a fat alar wing over the comma's tail"): the
pad's dorsal leather broader (RHINARIUM plan taper 0.1) and BORDER's lower side forward / upper side back, so the
leather reads as the photos' broad-topped box from the high cameras with the near-level fronts unchanged; the comma's
fold band wider for canid_cage NOSTRIL wing's three rings (the wing's construction lives there). w12's REGISTERED
read did not follow on any pad shape (work/bestiary/wolf/check_w2u_nose/w12reg.py): its trace is anchored by the eyes
and canid.py's planum point (the solve holds: w12's eyes sit 1.32 IO over its nose, which on this clay needs 46.5 deg;
22 deg would need the eyes ~233 mm behind the planum), the two leathers coincide in its camera, and there its openings
sit 0.54-0.78 down the leather where an opening on the cap's flat front sits 0.69-0.88. What moves it is WHERE THE
OPENING SITS IN DEPTH: THE NOSTRIL'S SEAT (RHINARIUM seat, seat_carve): each nostril set back on the pad's front-lateral
corner, deepest over the head's top, so the opening faces forward, out and a little up, as the dogs in three-quarter
and w11 (w12's own wolf, in profile) show it. Its (x, q) at the level front is unchanged (the level read held,
0.30-0.65 down, 11.9 %); in w12's camera its rims project where the photo's do (IoU 0.27 -> 0.75, share 5.8 -> 9.3 %).
"""
import numpy as np

# THE CAP (cap_field) [P PROFILE, TOP, the photos' outlines; E the morph and the dip]
RHINARIUM = dict(
    W=22.0,                       # the leather's half width (TOP: 22 at its widest)
    plan=dict(d_full=9.0, m=2.6, taper=0.1, taper_from=12.0),
    #                               a(d) = W (1 - ((d_full - d) / (d_full - d_tip))^m)^(1/m): TOP's front shifted onto
    #                               PROFILE's tip (16.5 / 20.4 / 21.7 mm at 2.5 / 5.5 / 8.5 mm behind it; TOP 16.4 / 20.7 /
    #                               22.0 at 3 / 6 / 9 behind its own front); W2q: narrowing behind d 12 by 0.3 of W at the
    #                               border (plan_halfwidth: the cap carried back over the bridge narrows into it, 30.8 mm
    #                               wide at d_b, instead of a 44 mm block: W2p's 'box nose' at d_b 25)
    #                               W2u (the lead's NOSE call: "a broad box of a pad"): taper 0.1 (0.3), 39.6 mm wide at
    #                               d_b. The seven traced photos' leathers in their own boxes (check_w2u_nose/outline_fit.py)
    #                               are broad-topped from 20 deg up (half width at 0.1 / 0.25 down: w12 0.65 / 0.92, f21
    #                               0.85 / 0.97, f08 0.75 / 0.92) where W2t's clay read 0.45-0.49 / 0.71-0.73 at every such
    #                               camera (an egg: the dorsal leather narrowing into the bridge); at 0.1 taper with BORDER's
    #                               W2u depths the clay reads 0.52-0.56 / 0.79-0.81, the leather's own IoU at the photos'
    #                               cameras 0.85-0.94 (0.83-0.91), the near-level fronts unchanged (their tops are round
    #                               arches: f10 0.52 / 0.78), no block from three-quarter or in profile (probe p1w3)
    n_up=2.2, n_lo=2.6,           # the front outline's upper / lower superellipse exponents (005: 2.3 / 2.5; 004 2.0 / 2.7)
    # W2m (the lead's call 2: "the leather's dorsal top further back, toward w11's evidence (about d 15-19)"): d 16.5, where
    # w11's leather meets the fur on the dorsal outline ~19 mm behind its tip (the W2l fresh eyes' gridded crop
    # prof_w11_nose_grid.png, 95 px at ~5 px / mm; w12 is very likely w11's animal), the tip at d -2.5. PROFILE's 8.9 is the
    # mean of w10 (5-6 mm behind its tip) and w11; its 1.9 mm dip behind 8.9 is the fur line, now leather: the top runs
    # convex from the tip over (8.9, 23.1) into the bridge (profile_lines skips the bridge points ahead of d_b + 1). In
    # w08's camera (36.6 deg over the palate) the 7.6 mm move adds ~3.5 mm to the leather's projected height (27 -> ~31
    # against the photo's 35: w08 is a third wolf, its leather longer again)
    # W2q (the lead's call 3: "take the cap's own form back toward the cast edge so it reaches w12's photo edge without
    # pleats"): d 24 (16.5), the plan narrowing behind d 12 (plan taper) and the morph into the arch moved back with it
    # (d_ref 32, d_s 36); with canid_nose BORDER's top at 28 the leather's border stands at d 27.9 on the midline (W2p
    # 25.3; w12's traced edge cast onto the clay d 28.5), the leather's front smooth in w12's camera, from above and in
    # three-quarter (check_w2q probe n1: nose_q2_n1.png; at d_b 16.5 the last ~3 mm pleated with the loops alone)
    d_b=24.0,                     # the dorsal border on the midline (W2l: 8.9, PROFILE's leather top; W2m-W2p 16.5)
    bot=((8.0, -5.4), (9.5, -6.5), (13.0, -9.5), (18.0, -13.0), (26.0, -16.0)),   # the ventral line behind the leather
    #                               (into the upper lip, inside the skin)
    # behind the border: the sections morph into the ARCH (the skin's own section at d_ref, the nasal dorsum over the
    # pads, lifted to the top line) by d_s, the top (above q split[1]) within `fast` mm of the border, the pads (below
    # split[0]) over the whole run: the leather's top corners stand clear of a narrower bridge, its lower half runs into
    # the pads; then sunk inside the skin over `sink` mm
    # (W2l d1-d2: the top's morph within 7-12 mm and the profile's dip within 3 mm left the leather a button with a rim
    # behind its top corners in the three-quarter view; the photos' leather runs into the muzzle's side)
    # W2m: d_ref 28 / d_s 32 (W2l 24 / 28: with the border at 16.5 the morph keeps a run of ~15 mm into the arch)
    morph=dict(d_ref=32.0, d_s=36.0, fast=10.0, split=(17.0, 21.0), inset=0.8, sink=8.0,
               # the top line behind the border: PROFILE's bridge lifted by (d, mm). W2m (the lead's call 2: "a convex pad
               # with no border step"): no lift; behind d 16.5 PROFILE's bridge rises steadily (22.0 at d 17, 23.3 at 28),
               # so the top runs on without a saddle. (W2l: the profile's 1.9 mm dip behind the leather's edge at 8.9 eased
               # to a 0.3-0.7 mm saddle over d 9-22 by a 1.2-1.6 mm lift)
               lift=((16.5, 0.0), (40.0, 0.0))),
    fine=0.25, box=((-6.0, -20.0, -34.0), (44.0, 32.0, 34.0)), blur=0.5, k=2.5,
    # W2t (the lead's NOSE call: "the pad wider than tall with a broad top and the philtrum"): THE PHILTRUM carved into
    # the cap, a groove on the midline `depth` mm deep, Gaussian across (`w` mm sigma), from between the nostrils (none
    # above q[0], full below q[1]) down the leather's front and underside, faded out behind d[0]..d[1] (cap_field). The
    # near-level photos (f08, f21, 015: check_w2t_nose) show it as a clear groove from between the openings through the
    # leather's bottom into the lip; canid_cage LIP philtrum recesses the midline column only 0.8 mm on the leather (half
    # its 1.6), which the W2s level renders show as a faint crease
    philtrum=dict(depth=0.9, w=1.1, q=(10.5, 6.5), d=(9.0, 15.0)),
    # W2u (the lead's NOSE call: "the CONSTRUCTION ... commas that read from the level AND w12's camera"): THE NOSTRIL'S
    # SEAT (seat_field, seat_carve; canid_cage.reference carves it into the skin-and-cap union): each nostril sits on
    # the pad's FRONT-LATERAL CORNER, set back `depth` mm at most behind the cap's front there, the central column
    # (|x| < x[0]) and the side silhouette (|x| > x[3]) untouched; in height its share per (q, factor) knots (pchip),
    # deepest over the opening's top and lateral half, fading above it at <= 0.8 mm per mm (w12's ray, 46.5 deg over
    # the palate, climbs 0.95 mm forward per mm: the roof over the opening never blocks it); acting on the front alone
    # (full for d < d[0], none behind d[1]). The tube's rings, laid along the level line of sight onto the reference
    # (canid_cage.place_nostril), follow it: the opening's (x, q) at the level front unchanged, its lateral half and
    # top set back, so it faces forward and out as the photos' do [P: the dogs in three-quarter, research/wolf_web/
    # nose_w2l_dogs 003 / 007 / 009 / 015, each opening a dark hole on the rounded corner with the wing lateral to it;
    # w11, w12's own wolf, in profile: the opening's head seen from the side ~6 mm behind the tip, 2-4 mm behind the
    # local front (work/bestiary/wolf/check_w2u_nose NOTES, its 4x gridded crop), where the clay showed none (0.1 % of
    # the leather); E the numbers between them]
    # The values (check_w2u_nose probes s1-s7, nose_eval on the frozen W2t head): 6 mm over the head's top and lateral
    # half (x 7.5-17, q 14.5-16), ~2.3 at its bottom (q 5.4), rising smoothly from the midline (0.5 mm at x 2: no ridge
    # between the openings; s1's start at x 4 left a steep column and a "T" from below) and fading out at the side
    # silhouette. Against W2u's tube wing alone (w7): w12's registered IoU 0.27 -> 0.75, share 5.8 -> 9.3 %, in its own
    # box 0.10 -> 0.52; the level read held (0.30-0.65 down, 11.9 %); the near-level fronts in the leather's box f10
    # 0.48 -> 0.50, 015 0.47 -> 0.42, 005 0.65 -> 0.56, f08 0.41 -> 0.50, f21 0.14 -> 0.32; in profile the head shows
    # (0.1 -> 1.5 % of the leather); from below (-65 deg) the openings hide (4.7 -> 0.1 %) and the pad's front reads
    # rounder in plan. Not taken: the seat ending before the wing (s3: the wing's lip then stood in front of the head's
    # lateral margin, w12 0.61), deeper over the top (s5: 0.74, the visible area grew without aligning)
    seat=dict(depth=6.0, x=(0.0, 7.5, 17.0, 21.5), xk=1.0,
              q=((2.0, 0.0), (5.4, 0.43), (10.0, 0.75), (14.5, 1.0), (16.0, 1.0), (23.5, 0.0)), d=(6.0, 10.0)))

# THE LEATHER'S BORDER (border_curve): the front outline (the cap's section at the border: RHINARIUM's superellipse, W,
# from PROFILE's bottom to its top) seen from the front, carried back onto the reference at the depth d_b(phi) behind the
# tip by its polar angle phi about the outline's centre (deg: 90 the top midline, 0 lateral, -90 the bottom midline):
# PROFILE puts the top at 8.9 and the bottom at 8.0; at the sides the leather ends where the plan reaches its full width
# (TOP: d 9) [P PROFILE, TOP; E between]. Its knees (the U's corners) at the outline's parameter `knees` (deg); the top
# and the side spaced by their 3D arc length, the bottom evenly in x (canid_cage.trace_leather's rules)
# W2m (the lead's call 2): the border WRAPS BACK along the sides. In both head profiles (the W2l fresh eyes' gridded crops
# prof_w10_nose_grid.png, prof_w11_nose_grid.png) the leather's border slopes back as it descends: close behind the tip on
# the dorsal outline, ~19 mm behind it at the nostril's height (w10: the alar wing's back edge ~140 px behind the tip at
# ~7.5 px / mm; w11 further), then forward and down to the philtrum. W2l's border ran 8-9.6 mm behind the tip at every
# angle: a thin cap on the muzzle's front (the "button", the fresh eyes' side view: a disc). Now the top at d_b (16.5),
# the upper side 16.0, the side at mid-height 15.0 (behind the alar wing), the lower side 11.0, the bottom on PROFILE's
# 8.0 [P w10, w11, PROFILE; E between]
BORDER = dict(depth=((-90.0, 8.0), (-45.0, 9.0), (-20.0, 12.5), (0.0, 18.0), (25.0, 24.5), (45.0, 27.0), (90.0, 28.0)),
              knees=(52.0, -48.0))
# (W2u, the lead's NOSE call, "a broad box of a pad": the lower side forward (-45: 9, W2q 11; -20: 12.5, the pchip gave
# ~14.6), so the leather's lower sides wrap less onto the muzzle where it is widest (the clay's leather widest 0.61-0.66
# down at every camera, the seven photos' 0.35-0.53: a bell), and the upper side held back longer (25: 24.5, the pchip
# gave ~23.5), the dorsal leather's back edge broad from above, with RHINARIUM plan taper 0.1. The top, the side and the
# bottom where W2q put them)
# (W2q, the lead's call 3: the top at 28 (25.5), the upper side 27 (24), the side 18 (17), with the cap's own form carried
# back to d 24 (RHINARIUM d_b, the plan narrowing behind d 12): the border's top lands at d 27.9 on the midline, 0.6 mm
# short of w12's cast edge; no pleat on the leather's front (probe n1). W2p's values follow)
# (W2l: depth ((-90, 8.0), (-45, 8.6), (0, 9.6), (45, 9.2), (90, 8.9)); W2m-W2o ((-90, 8.0), (-45, 11.0), (0, 15.0),
# (45, 16.0), (90, 16.5)))
# W2p (the lead's call 3, "the leather's dorsal extent up to the photos' bare edge"): the top back to d 25.5 on the
# midline, the upper side 24, the side 17. The evidence: w12's traced leather (its top the bare leather's real edge, the
# W2o fresh eyes) cast onto the clay along w12's solved rays lands at d 28.5 on the midline, 28.9-29.3 at 45-60 deg, 26.9
# at 30 (work/bestiary/wolf/check_w2p/leather_cast.py); w11, w12's own wolf in profile, carries its dark leather along
# the top silhouette ~26 mm in d behind its tip (W2m's '95 px, d 16.5' was a misread). W2l's objection to the high
# cameras (their leathers 'too tall', growing with the camera's pitch) is what a long dorsal surface does. In w12's camera
# the border's top now stands 2.7 mm under the photo's edge (W2o 9.9). At 28.5 (probes n1-n4, l1, l5: the full cast) the
# leather's front pleated between the nostrils (its interior grid stretched from a front loop 18 mm back on the top) and,
# before canid_cage LEATHER smooth_top, its front loop folded at its top-lateral corner (the loops' layout for the 25.5:
# canid_cage LEATHER, LAYOUT tubes leather 'mid'); the cap's own form still ends at
# d_b 16.5, so the extra 9 mm of leather is the loops on the morph into the bridge, and the edge in clay a soft change
# of plane ~0.5 mm proud (the profiles' "under 1 mm" saddle, RHINARIUM's note)

# THE NOSTRIL in a LEVEL FRONT chart (level_frame: image mm = (x, q), the line of sight +d), a COMMA (nostril_curves) laid
# on the clay's own frame. The near-level fronts (004, 005, 002, 015; research/wolf_web/nose_w2l_wolves, my tracing on
# gridded crops): the visible opening with its slit 0.19-0.23 of the leather's width (median ~0.21: ~9 mm of 44), 0.75-0.85
# as tall as wide, the centres 0.44-0.46 of the leather's width apart (+-10-11 mm: the heads' medial edges at +-0.32 W,
# the slits' tips at 0.72 W), the tops 0.50-0.57 and the bottoms 0.72-0.75 down the leather in cameras 16-34 deg over the
# palate: carried through the clay's own profile, the opening's top at q ~12.7 (just over the tip's 11.1), its bottom ~5.5,
# wider than tall and low on the front. Its shape as the photos and the dog close-ups show it (w12's traced opening,
# rescaled, was an oval with a short lateral point: W2l n1 read as two rimmed ovals again): a round HEAD (medial; centre,
# radii) running out into the lateral SLIT, a band along `tail` (x, q, half width) tapering as it curves out and down
# under the alar fold; the dark CORE the head shrunk by `core`; the alar FOLD over the head's top and lateral side and
# along the slit's upper edge (its inner edge on the opening's margin from `fold_from` deg about the head's centre, its
# outer edge `fold_w` mm outside: at its start, at the head's lateral side, at the slit's tip) [P 004, 005, 015, 016 and
# the dog close-ups 004 / 007 / 009 in research/wolf_web/nose_w2l_dogs; E the numbers between them]
NOSTRIL_L = dict(head=(8.9, 10.0), head_r=(4.3, 4.6),
                 tail=((12.5, 8.4, 2.6), (14.1, 6.8, 1.6), (14.9, 5.3, 1.0), (15.1, 4.2, 0.65)),
                 core=0.78, core_in=0.7, fold_from=50.0, fold_w=(1.8, 4.2, 2.2))
#                (W2u restart 2, with RHINARIUM seat: the whole comma 0.9 mm MEDIAL (head x 9.8 -> 8.9, every tail point
#                with it): the centres 0.481 -> 0.442 of the leather's width apart, inside the near-level fronts' 0.44-0.46
#                (above), and in w12's registered camera the photo's openings sat ~1 mm more medial than the ring (w12
#                IoU 0.68 -> 0.71 with the seat's first form). The width read unchanged (0.248). A head 0.3 mm more medial
#                and 0.2 mm wider with the tail 0.5 mm in (probe s7) lost the lateral side in w12's camera (0.75 -> 0.68):
#                the photo's head is wider than the visible opening on both sides, and w02's width limit (0.25) caps it)
#                (W2u, the lead's NOSE call: "the CONSTRUCTION ... a fat alar wing over the comma's tail": the fold's band
#                1.8 / 4.2 / 2.2 mm (1.4 / 3.2 / 1.6), the photos' wing ~4.5 mm wide beside the head (015 at its leather's
#                scale: work/bestiary/wolf/check_w2u_nose/out/photos/015.png), for canid_cage NOSTRIL wing's three rings;
#                the tail's end blunter at the same lateral reach (its last point 0.4 / 0.3 mm in, its half width 0.35 ->
#                0.65 mm: x 16.65 as before; w02's frame read 0.248 of the leather's width on the W2u pad, 0.244 on W2t's:
#                the leather 0.7 mm narrower, the gate's 0.25 close), so the slit rounds off under the wing instead of
#                ending in a point)
#                (W2t, the lead's NOSE call: "comma openings low on the pad (0.50-0.75 down), the round head small and facing
#                forward and out, the tail sweeping out and down under the alar wing; gated on traced level-front photos with
#                w12's read held >= 0.75". Measured first (check_w2t_nose/out/traces, cams.json; the openings' top..bottom down
#                the leather, the share of it, at each photo's solved camera): f10 3 deg 0.28-0.72, 19.5 %; 015 12 deg
#                0.46-0.80, 14.8 %; 005 20 deg 0.49-0.75, 11.2 %; f08 24 deg 0.43-0.77, 13.1 %; f21 44 deg 0.58-0.82, 5.1 %;
#                w12 48 deg 0.56-0.84, 10.4 %. The share falls ~4x from 3 to 44 deg: the openings face ~30-35 deg DOWN
#                (they sit on the front face below the tip, as both head profiles show: w10 0.46-0.80, w11 0.52-0.81 down
#                in profile), and w12's 10.4 % at 48 deg is the outlier. W2s's comma (head (10.15, 14.0) r (4.4, 5.0): q 9-19,
#                over the tip's 11.1) read 0.16-0.45 at the level front, 0.28-0.56 at 015's camera; it matched only the high
#                cameras. Now the head fuller and 4 mm LOWER (q 5.4-14.6), the tail from its lower-lateral side out and down
#                to (16.3, 4.0), the wing from 50 deg (over the head's upper-lateral side and the tail, no longer its top:
#                the photos' wing is the lobe lateral to the opening). Level 0.30-0.65 (share 12.2 %); against the traces in
#                the leather's own box at their cameras (nose_lib.photo_iou), W2s -> W2t: f10 0.21 -> 0.49, 015 0.11 -> 0.48,
#                005 0.24 -> 0.66, f08 0.40 -> 0.43, f21 0.28 -> 0.18; below35 two dark commas, from below (-65) the openings
#                now show (5.2 %, W2s none); w02's frame read 0.244 of the leather's width, apart 0.474. w12's IoU 0.83 ->
#                0.29: from 48 deg the dome round the tip hides openings this low (out/diag_w12_n7.png; the tucks are not
#                the occluder: NOSTRIL tuck_up 0 read 0.31). Holding w12 >= 0.75 needs the head's top at q >= ~18.5
#                (sweep n1-n4: q 15.2 -> 0.33, 16.8 -> 0.47, 19 -> 0.83), which is W2s's level read; a high head with a long
#                low tail (n4a) held 0.75 and read worse at every near-level photo (a tall comma, aspect 0.78))
#                (W2s, w02 _w2s2 / _w2s3: the ring ran past the cast's x 17.0, 0.256 / 0.251 of the leather's width against the
#                gate's 0.25 at the tail tip 16.9 / 16.5, half a mm of width per mm of tip: the tail's last two points 0.4 / 0.7 mm in)
#                (W2s restart: at tip 16.2 _w2s4 read 0.2505 still: the edge ring's lateral extreme had left the tip for the
#                tail's shoulder (x 17.08 at q 12.2, the second point's 2.1 mm half width, cage 2ca5b064). Moving the third
#                point in (15.8 -> 15.6) turned the tail down more steeply there and swung that shoulder OUT (0.2516, cage
#                1cdcf4e5: taken back). The ring's medial extreme is the head's medial side (x 5.52), so the head 0.15 mm
#                lateral: 11.40 of 46.11 mm, 0.247, the centres 0.476 apart [0.41-0.49], 0.87 as tall as wide (cage af33e0eb))
#                (W2s, the lead's call 6: "round-headed commas low on the leather with the alar wing curling over them, facing
#                the high cameras as w12's do (the photos' share in w12's camera)". w12's traced opening cast through its
#                camera onto the reference spans the same x as W2r's comma (5.6-17.0) but q 9.9-19.5 against 7.1-16.2, and
#                in that camera W2r's edge ring lost its top right on a diagonal: the TENT; the comma's tail drooped where
#                the photo has a full shoulder and a short tail going sideways (check_w2s nostril_cast.py). The head taller
#                and 1.6 mm higher, the tail short and level, the wing from over the head's top (fold_from 95, W2r 60)
#                and wider at the tail; with canid_cage NOSTRIL's tuck_up 1.2, h 1.6, over_lat 1.5, the canal nearly straight
#                back (turn 5 / 5 / 10): the visible opening in w12's camera 48 -> 72 mm2 against the traced 81, IoU with
#                the traced opening 0.53 -> 0.84, 10.5 % of the leather (the photo 10.4), deep 0.82; w08's camera 11.8 %,
#                the level front 13.7 %, 10.9 x 9.0 mm: 0.24 of the leather's width, 0.83 as tall as wide (the near-level
#                fronts 0.19-0.23, 0.75-0.85) (check_w2s nose_probe.py: n0, n3, n5, n7; the tall round hole of the full cast,
#                q 19.5, would read as a pig's from the level front: this keeps the top 2.5 mm under it)
#                (W2r, the lead's call 4: "the nares opened toward the photos' share (comma-shaped, with the alar fold),
#                read at the photos' cameras": in w12's camera (48 deg over the palate) the W2q openings were 3.1 % of the
#                leather against the photo's 10.4 %, two slits at the leather's foot (the photo's dark blobs 9.7 x 7.9 and
#                13.9 x 11.2 mm, 0.69 down the leather; the clay's 0.81). The head larger (4.0 x 3.8, W2q 3.7 x 3.0) and
#                3 mm higher, the slit with it: the opening 11.3 x 9.1 mm in the level chart, 0.23 of the leather's width
#                (the photos 0.19-0.23), 0.85 as tall as wide (0.75-0.85); with canid_cage NOSTRIL's tuck_up 2.5, over 0,
#                h 1.0: w12's camera 7.0 % deep 0.46 (w12's own traced dark core over its opening 0.47 / 0.57), w08's 8.1 %,
#                the level front 9.9 %, below-front 15.4 % (check_w2r/nose_read.py: probes n1-n5; bc3z, W2q's: 2.9 / 4.1 /
#                7.4 / 21.2 %). The rest of the gap in w12's camera is the leather's own: from 48 deg the clay shows its
#                long dorsal surface and a foreshortened front, the photo a front tipped toward it)
#                (W2o, the lead's call 3: "a nostril that reads dark from above AND from level / below-front": the fold
#                from 60 deg about the head's centre (its upper-lateral side), not 118 (over the head's top): the alar fold
#                roofs the comma's tail and the head's lateral side, and the head opens to the photos' high cameras, where
#                W2m's fold over its top hid it (w12's openings 2.2 % of the leather, deep 0.38). With canid_cage NOSTRIL's
#                over 0.5, tuck 1.0, core 3.0: w12's camera 3.7 % deep 0.85, w08's 4.9 % / 0.85, the level front 7.2 % /
#                0.93, below-front 11.2 % / 0.90 (check_w2o/nose_read.py on probe n8; o13, W2n's: 1.9 / 3.0 / 5.8 / 7.9 %))
#                (W2l n2: head radii 3.0 x 2.9 and a slit to x 15.7: the opening 9.0 x 7.2 mm read as small pale commas
#                from the level front, 0.26 % dark in w12's read; n3 10.1 x 7.9 mm, the photos' 0.21-0.23 of the leather.
#                W2l h3, the restarted head builder: from the front h2's read as a KEYHOLE, a round dark hole with its own
#                rim beside a lit slot: the slit's band was 1.1 -> 0.15 mm half wide, a hairline beside the head, and the
#                tube's core ring stayed round the head (core, the head's ellipse shrunk), so the slit was a shallow ledge.
#                Now the head a little wider than tall (3.7 x 3.0), the slit's band 1.7 -> 0.3 mm (in the photos 004 / 005
#                the slit at its root is about half the head's height), curving a little lower, and the dark CORE the comma
#                itself eroded core_in mm (nostril_curves), so the vestibule and canal run under the slit: the opening 10.7
#                x 8.2 mm, the dark blobs in w12's read 7.5 mm long (h2 5.3), dark 2.0 % of the leather (h2 1.8; w08 2.6 /
#                2.1); the fold's width at the slit's tip 0.5 mm (0.9))


def _pchip(xs, ys):
    from scipy.interpolate import PchipInterpolator
    xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    o = np.argsort(xs)
    return PchipInterpolator(xs[o], ys[o], extrapolate=True)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def profile_lines():
    """the midline's DORSAL line q_top(d) (the tip to the dorsal border, then PROFILE's bridge) and VENTRAL line q_bot(d)
    (the tip to the leather's bottom, then into the upper lip), PROFILE's leather: callables of d, and the tip (d, q)"""
    from . import canid_hull as CH
    pr = np.asarray(CH.PROFILE, np.float64)
    tip = pr[7]
    dors = pr[7::-1]                                   # the tip (-2.5, 11.1) up to the top (8.9, 23.1)
    bridge = pr[-30:][::-1]                            # (12, 21.2) .. back along the nasal dorsum
    bridge = bridge[(bridge[:, 0] > RHINARIUM['d_b'] + 1.0) & (bridge[:, 0] < 60.0)]
    top = np.vstack([dors, bridge])
    vent = np.vstack([pr[7:15], np.asarray(RHINARIUM['bot'], np.float64)[1:]])
    return _pchip(top[:, 0], top[:, 1]), _pchip(vent[:, 0], vent[:, 1]), tip


def plan_halfwidth(d, tip_d):
    """the leather's half width in plan, a(d) (RHINARIUM plan); W2q: behind `taper_from` it narrows smoothly by
    `taper` of W at the dorsal border (d_b), so a cap carried back over the bridge narrows into it instead of running on
    as a 44 mm block (W2p's 'box nose')"""
    pl = RHINARIUM['plan']
    L = pl['d_full'] - tip_d
    d = np.asarray(d, np.float64)
    u = np.clip((pl['d_full'] - d) / L, 0.0, 1.0)
    a = RHINARIUM['W'] * (1.0 - u ** pl['m']) ** (1.0 / pl['m'])
    tp = float(pl.get('taper', 0.0))
    if tp > 0.0:
        t0 = float(pl.get('taper_from', pl['d_full']))
        a = a * (1.0 - tp * smooth01((d - t0) / max(RHINARIUM['d_b'] - t0, 1e-6)))
    return a


def leather_xmax(q, qt, qb, a):
    """the half width at heights q of the leather's section with top qt, bottom qb and half width a (broadcast): the
    front outline's superellipse, its widest at mid-height; -1 outside the section's height"""
    rh = RHINARIUM
    qc = 0.5 * (qt + qb)
    bu = np.maximum(qt - qc, 1e-6)
    bl = np.maximum(qc - qb, 1e-6)
    s_up = (q - qc) / bu
    s_lo = (qc - q) / bl
    up = q >= qc
    s = np.where(up, s_up, s_lo)
    n = np.where(up, rh['n_up'], rh['n_lo'])
    inside = s <= 1.0
    x = a * np.power(np.clip(1.0 - np.power(np.clip(s, 0.0, 1.0), n), 0.0, 1.0), 1.0 / n)
    return np.where(inside, x, -1.0)


def section_halfwidths(ds, qs, skin_half, skin_top):
    """THE CAP's half width XM[i, j] at (ds[i], qs[j]) (-1 where the section does not reach): the leather's superellipse
    sections ahead of the border, the morph into the arch behind it (skin_half, skin_top: the skin's section at d_ref,
    a callable q -> |x| and its top), then the sink"""
    rh = RHINARIUM
    mo = rh['morph']
    q_top, q_bot, tip = profile_lines()
    d_b, d_s = rh['d_b'], mo['d_s']
    D = np.asarray(ds, np.float64)[:, None]
    Q = np.asarray(qs, np.float64)[None, :]
    XM = np.full((len(ds), len(qs)), -1.0)
    # the leather: from the tip to the border
    dl = np.clip(D, tip[0], d_b)
    qt = np.where(D >= tip[0], q_top(dl), np.nan)
    # W2m: the section's bottom follows PROFILE's leather bottom to its end (d 8.0) and stays there behind it, as the morph's
    # start section does (qb_b below): W2l took the lower of it and the lip line, a 0.6 mm step at the border with d_b 8.9
    # and a 7 mm one with d_b 16.5 (the lip line at -12.6 there); the section's part below the leather lies inside the pads
    qb = np.where(D >= tip[0], q_bot(np.minimum(dl, rh['bot'][0][0])), np.nan)
    a = plan_halfwidth(dl, tip[0])
    lea = (D >= tip[0]) & (D <= d_b)
    XL = leather_xmax(Q, qt, qb, a)
    XM = np.where(lea, XL, XM)
    # behind the border: the morph (the leather's section at d_b -> the arch, less the inset), both remapped in height
    # so their tops lie on the top line (PROFILE's bridge + the lift), the top fast and the pads slow; then the sink
    qt_b = float(q_top(d_b))
    qb_b = float(q_bot(rh['bot'][0][0]))
    lf = np.asarray(mo['lift'], np.float64)
    beh = (D > d_b) & (D <= d_s + mo['sink'])
    top_a = skin_top - mo['inset']
    sink = smooth01((D - d_s) / mo['sink'])
    top_tgt = q_top(np.clip(D, d_b, d_s)) + np.interp(D, lf[:, 0], lf[:, 1]) - 4.0 * sink
    q_low = -14.0
    QeL = q_low + (Q - q_low) * (qt_b - q_low) / np.maximum(top_tgt - q_low, 1e-6)
    QeA = q_low + (Q - q_low) * (top_a - q_low) / np.maximum(top_tgt - q_low, 1e-6)
    XLb = leather_xmax(QeL, qt_b, qb_b, float(plan_halfwidth(d_b, tip[0])))
    XA = np.where(QeA <= top_a, np.maximum(skin_half(QeA) - mo['inset'], -1.0), -1.0)
    beta = smooth01((Q - mo['split'][0]) / (mo['split'][1] - mo['split'][0]))
    w = (1.0 - beta) * smooth01((D - d_b) / (d_s - d_b)) + beta * smooth01((D - d_b) / mo['fast'])
    XB = (1.0 - w) * np.maximum(XLb, 0.0) + w * np.maximum(XA, 0.0)
    XB = XB * (1.0 - 0.25 * sink) - 3.0 * sink
    ok = (XLb >= 0.0) | (XA >= 0.0)
    XM = np.where(beh & ok & (XB > 0.0), XB, XM)
    return XM


def cap_field(phi_skin, G, log=print):
    """THE CAP's signed distance (mm, negative inside) on the grid G (palate (d, q, x)): the loft (section_halfwidths)
    as an inside test on a fine local grid (RHINARIUM fine, box), signed by Euclidean distance transforms, blurred
    `blur` mm, sampled trilinearly onto G (+60 outside the box); phi_skin: the skin whose section at d_ref is the arch
    (G's)"""
    from scipy import ndimage as nd
    from .canid_cage import bridge_width
    rh = RHINARIUM
    d_s, d_ref = rh['morph']['d_s'], rh['morph']['d_ref']
    skin_half = bridge_width(phi_skin, G, d_ref)
    # the skin's top at d_ref (its midline's highest inside sample)
    f = (d_ref - G.lo[0]) / G.h
    i0 = int(np.floor(f))
    w_ = f - i0
    j0 = int(np.argmin(np.abs(G.lo[2] + np.arange(G.n[2]) * G.h)))
    col = (1.0 - w_) * phi_skin[i0, :, j0] + w_ * phi_skin[i0 + 1, :, j0]
    qs_g = G.lo[1] + np.arange(G.n[1]) * G.h
    ins = np.nonzero(col < 0.0)[0]
    jt = ins.max()
    skin_top = float(qs_g[jt] + G.h * col[jt] / (col[jt] - col[jt + 1]))
    hf = rh['fine']
    lo = np.asarray(rh['box'][0], np.float64)
    hi = np.asarray(rh['box'][1], np.float64)
    n = tuple(int(np.round((hi[a] - lo[a]) / hf)) + 1 for a in range(3))
    ds = lo[0] + np.arange(n[0]) * hf
    qs = lo[1] + np.arange(n[1]) * hf
    xs = lo[2] + np.arange(n[2]) * hf
    XM = section_halfwidths(ds, qs, skin_half, skin_top)
    inside = np.abs(xs)[None, None, :] <= XM[:, :, None]
    sd = (nd.distance_transform_edt(~inside) - nd.distance_transform_edt(inside)) * hf
    ph = rh.get('philtrum')
    if ph:
        # W2t: the philtrum's groove (RHINARIUM philtrum): the distance raised on the midline, so the surface sinks
        # `depth` mm there, before the blur rounds its edges
        wq = smooth01((ph['q'][0] - qs) / (ph['q'][0] - ph['q'][1]))
        wd = smooth01((ph['d'][1] - ds) / (ph['d'][1] - ph['d'][0]))
        gx = np.exp(-0.5 * (xs / ph['w']) ** 2)
        sd += ph['depth'] * wd[:, None, None] * wq[None, :, None] * gx[None, None, :]
    sd = nd.gaussian_filter(sd, rh['blur'] / hf, mode='nearest')
    # onto G
    D, Q, X = G.mesh()
    out = np.full(G.n, 60.0, np.float32)
    m = (D >= lo[0]) & (D <= hi[0]) & (Q >= lo[1]) & (Q <= hi[1]) & (X >= lo[2]) & (X <= hi[2])
    c = np.stack([(D[m] - lo[0]) / hf, (Q[m] - lo[1]) / hf, (X[m] - lo[2]) / hf])
    out[m] = nd.map_coordinates(sd, c, order=1, mode='nearest')
    log(f'[nose] the cap: the leather lofted from the tip ({profile_lines()[2][0]:.1f}, {profile_lines()[2][1]:.1f}) to '
        f'the border at d {rh["d_b"]} ({int(inside.sum()):,} of {inside.size:,} fine voxels inside), morphed into the '
        f'arch (the skin\'s section at d {d_ref:.0f}, its top q {skin_top:.1f}, on the bridge\'s line) by d {d_s:.0f} (its '
        f'top by d {rh["d_b"] + rh["morph"]["fast"]:.0f}), sunk by d {d_s + rh["morph"]["sink"]:.0f}')
    return out


def seat_field(D, Q, X):
    """W2u: THE NOSTRIL'S SEAT (RHINARIUM seat) at palate points (d, q, x mm, broadcast): how far (mm) the reference's
    front is set back there. Across: 0 on the central column (|x| <= x[0]), rising to `xk` of the depth by x[1] and to
    the full depth past it, held to x[2], falling to 0 at the side silhouette (x[3]); in height: the q knots' factor
    (pchip, clipped to 0..1); on the front alone: full for d <= d[0], none behind d[1]"""
    st = RHINARIUM['seat']
    x0, x1, x2, x3 = st['x']
    ax = np.abs(np.asarray(X, np.float64))
    rise = smooth01((ax - x0) / (x1 - x0))
    sx = np.where(ax <= x1, st['xk'] * rise, st['xk'] + (1.0 - st['xk']) * smooth01((ax - x1) / max(x2 - x1, 1e-6)))
    sx = sx * smooth01((x3 - ax) / max(x3 - x2, 1e-6))
    qk = np.asarray(st['q'], np.float64)
    sq = np.clip(_pchip(qk[:, 0], qk[:, 1])(np.clip(np.asarray(Q, np.float64), qk[0, 0], qk[-1, 0])), 0.0, 1.0)
    sd_ = smooth01((st['d'][1] - np.asarray(D, np.float64)) / (st['d'][1] - st['d'][0]))
    return st['depth'] * sx * sq * sd_


def seat_carve(phi, G, log=print):
    """W2u: the nostril's seat carved into the reference (canid_cage.reference: the skin unioned with the cap; the skin
    alone follows the same PROFILE and TOP, so a seat in the cap alone would be filled by it): phi raised by
    seat_field, which sets the front back by about that much where it faces forward (|grad| ~1 there). Returns phi"""
    st = RHINARIUM.get('seat')
    if not st:
        return phi
    # on the sub-block where it acts alone (the grid's axes broadcast, no full mesh)
    qk = np.asarray(st['q'], np.float64)
    i = np.nonzero(G.d <= st['d'][1])[0]
    j = np.nonzero((G.q >= qk[0, 0]) & (G.q <= qk[-1, 0]))[0]
    k = np.nonzero(np.abs(G.x) <= st['x'][3])[0]
    if not (len(i) and len(j) and len(k)):
        return phi
    sl = (slice(i[0], i[-1] + 1), slice(j[0], j[-1] + 1), slice(k[0], k[-1] + 1))
    R = seat_field(G.d[sl[0]][:, None, None], G.q[sl[1]][None, :, None], G.x[sl[2]][None, None, :])
    out = np.array(phi, copy=True)
    out[sl] += R.astype(out.dtype)
    log(f'[nose] the nostril\'s seat: the front set back up to {float(R.max()):.1f} mm round each nostril (|x| '
        f'{st["x"][0]:.0f}-{st["x"][3]:.1f}, q {qk[0, 0]:.1f}-{qk[-1, 0]:.1f}, on the front ahead of d {st["d"][1]:.0f})')
    return out


def front_outline(theta_deg):
    """the leather's FRONT OUTLINE at superellipse parameters theta (deg; 90 the top midline, 0 lateral, -90 the bottom
    midline): (n, 2) (x, q) mm, x >= 0: RHINARIUM's section at the border (W; PROFILE's bottom and top)"""
    rh = RHINARIUM
    q_top, q_bot, _ = profile_lines()
    qt, qb = float(q_top(rh['d_b'])), float(q_bot(rh['bot'][0][0]))
    qc, b = 0.5 * (qt + qb), 0.5 * (qt - qb)
    t = np.radians(np.asarray(theta_deg, np.float64))
    n = np.where(t >= 0.0, rh['n_up'], rh['n_lo'])
    c, s = np.cos(t), np.sin(t)
    x = rh['W'] * np.abs(c) ** (2.0 / n)
    q = qc + b * np.sign(s) * np.abs(s) ** (2.0 / n)
    return np.column_stack([x, q])


def border_curve(ref, il, kt, kb):
    """THE LEATHER'S BORDER on the reference (BORDER), in canid_cage.trace_leather's form for the U of face-cap cells
    (il its column, kt / kb its rows): dict(border (m, 3) (d, q, x): the top from the midline (il + 1 points), the side
    (kb - kt + 1, sharing the corners) and the bottom back to the midline (il + 1), top, side, bot (from the midline),
    half (the outline (x, q) seen from the front), knees (their indices in half))"""
    from .canid_cage import resample
    bd = BORDER
    th = np.linspace(90.0, -90.0, 721)
    O = front_outline(th)
    q_top, q_bot, _ = profile_lines()
    qc = 0.5 * (float(q_top(RHINARIUM['d_b'])) + float(q_bot(RHINARIUM['bot'][0][0])))
    phi = np.degrees(np.arctan2(O[:, 1] - qc, O[:, 0]))
    dt = np.asarray(bd['depth'], np.float64)
    dd = _pchip(dt[:, 0], dt[:, 1])(phi)
    P0 = np.column_stack([dd, O[:, 1], O[:, 0]])
    P = ref.project(P0, it=12)
    P[0, 2] = P[-1, 2] = 0.0
    j_tl = int(np.argmin(np.abs(th - bd['knees'][0])))
    j_bl = int(np.argmin(np.abs(th - bd['knees'][1])))
    top, side, bot = P[:j_tl + 1], P[j_tl:j_bl + 1], P[j_bl:][::-1]
    rt = resample(top, il + 1)
    rs = resample(side, kb - kt + 1)
    # the bottom evenly in x from the midline to the bottom-lateral corner (c9a's rule: the bottom edge is near level)
    xs_b = np.linspace(0.0, float(bot[-1, 2]), il + 1)
    o = np.argsort(bot[:, 2])
    rb = np.column_stack([np.interp(xs_b, bot[o, 2], bot[o, 0]), np.interp(xs_b, bot[o, 2], bot[o, 1]), xs_b])
    rb = ref.project(rb, it=8)
    rb[0, 2] = 0.0
    rb[-1] = rs[-1]
    rt[0, 2] = 0.0
    border = np.vstack([rt, rs[1:], rb[::-1][1:]])
    return dict(border=border, top=rt, side=rs, bot=rb, half=O, knees=(j_tl, j_bl))


def nostril_curves():
    """THE COMMA in the level chart (NOSTRIL_L; mm (x, q), the creature's left): the OPENING's outline (the head's
    ellipse unioned with the slit's tapering band, rastered at 0.05 mm and contoured; counter-clockwise from its lateral
    tip), the dark CORE (the head shrunk), the FOLD's inner edge (the opening's margin from fold_from over the head's top
    and lateral side along the slit's upper edge to its tip) and outer edge (offset outward by fold_w). Returns dict"""
    from scipy.interpolate import interp1d
    from skimage.measure import find_contours
    nl = NOSTRIL_L
    hc = np.asarray(nl['head'], np.float64)
    hr = np.asarray(nl['head_r'], np.float64)
    tl = np.asarray(nl['tail'], np.float64)
    res = 0.05
    lo = np.array([hc[0] - hr[0] - 1.0, tl[:, 1].min() - 2.0])
    hi = np.array([tl[:, 0].max() + 1.0, hc[1] + hr[1] + 1.0])
    xs = np.arange(lo[0], hi[0], res)
    qs = np.arange(lo[1], hi[1], res)
    X, Q = np.meshgrid(xs, qs, indexing='ij')
    inside = ((X - hc[0]) / hr[0]) ** 2 + ((Q - hc[1]) / hr[1]) ** 2 <= 1.0
    # the slit: a band of varying half width along the tail's centreline (from the head's centre)
    cl = np.vstack([np.r_[hc, hr[1] * 0.9], tl])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(cl[:, :2], axis=0), axis=1))])
    ss = np.linspace(0.0, s[-1], 400)
    fx, fq, fw = (interp1d(s, cl[:, k], kind='quadratic' if len(cl) > 2 else 'linear')(ss) for k in range(3))
    for x_, q_, w_ in zip(fx, fq, fw):
        inside |= (X - x_) ** 2 + (Q - q_) ** 2 <= max(w_, 0.05) ** 2
    C = max(find_contours(inside.astype(np.float32), 0.5), key=len)
    op = np.column_stack([lo[0] + C[:, 0] * res, lo[1] + C[:, 1] * res])
    # counter-clockwise, starting at the slit's tip (the outline point farthest along the tail)
    area = 0.5 * np.sum(op[:, 0] * np.roll(op[:, 1], -1) - np.roll(op[:, 0], -1) * op[:, 1])
    if area < 0:
        op = op[::-1]
    j_tip = int(np.argmin(np.linalg.norm(op - tl[-1, :2], axis=1)))
    op = np.roll(op, -j_tip, axis=0)
    from .canid_cage import resample
    op = resample(op, 144, closed=True)
    # the dark core: W2l h3 (the restarted head builder) the COMMA itself, the opening's inside eroded `core_in` mm, so
    # canid_cage.place_nostril's core, vestibule and canal run into the slit too (with the head's ellipse shrunk by `core`
    # the core ring stayed round the head and the slit was a shallow lit ledge between the comma's edge and a round core:
    # a keyhole from the front, a round hole beside a slot); without core_in, the head shrunk about its centre
    if nl.get('core_in'):
        from scipy import ndimage as nd
        dist = nd.distance_transform_edt(inside) * res
        Cd = max(find_contours((dist >= nl['core_in']).astype(np.float32), 0.5), key=len)
        dark = resample(np.column_stack([lo[0] + Cd[:, 0] * res, lo[1] + Cd[:, 1] * res]), 72, closed=True)
    else:
        t = np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False)
        dark = hc + nl['core'] * hr * np.column_stack([np.cos(t), np.sin(t)])
    # the fold's inner edge: from the outline point at fold_from (about the head's centre) clockwise (decreasing index:
    # the outline runs counter-clockwise from the tip) over the top and the lateral side to the slit's tip (index 0)
    ang = np.degrees(np.arctan2(op[:, 1] - hc[1], op[:, 0] - hc[0]))
    near_head = np.linalg.norm((op - hc) / hr, axis=1) < 1.15
    cand = np.nonzero(near_head & (np.abs(ang - nl['fold_from']) < 20.0))[0]
    j0 = int(cand[np.argmin(np.abs(ang[cand] - nl['fold_from']))])
    fi = op[j0::-1].copy()                                # from the start over the top and down to the slit's tip
    # its OUTER edge drawn on its own (an offset of the opening's margin kinks at the head-slit junction, a concave
    # corner): in polar form about the head's centre, the inner edge's radius per angle smoothed over ~25 deg, plus w
    # (fold_w: fold_from -> the lateral side (0 deg) -> the slit's tip)
    from scipy.ndimage import gaussian_filter1d
    w0, w1, w2 = nl['fold_w']
    a_i = np.unwrap(np.arctan2(fi[:, 1] - hc[1], fi[:, 0] - hc[0]))
    r_i = np.linalg.norm(fi - hc, axis=1)
    o_ = np.argsort(a_i)
    th_ = np.linspace(a_i.min(), a_i.max(), 160)
    r_s = gaussian_filter1d(np.interp(th_, a_i[o_], r_i[o_]), 160 * np.radians(25.0) / np.ptp(th_) / 2.0,
                            mode='nearest')
    wv = np.interp(np.degrees(th_), [np.degrees(a_i.min()), 0.0, np.degrees(a_i.max())], [w2, w1, w0])
    fo = hc + (r_s + wv)[:, None] * np.column_stack([np.cos(th_), np.sin(th_)])
    fo = fo[::-1]                                        # from the start (fold_from) to the slit's tip, as fold_in
    return dict(opening=op, dark=dark, fold_in=resample(fi, 24), fold_out=resample(fo, 24), head=hc)


def nostril_chart(spec, fr):
    """canid_cage.nostril_chart for the level frame: the comma (nostril_curves) in the chart (image mm = (x, q)): the
    opening's centre (its points' mean), its half axes, and the opening, the core, the fold's edges about the centre over
    the half axes"""
    nc = nostril_curves()
    op = nc['opening']
    c = op.mean(0)
    ab = 0.5 * (op.max(0) - op.min(0))
    sc = lambda P: (np.asarray(P, np.float64) - c) / ab          # noqa: E731
    return dict(c=c, ab=ab, open=sc(op), dark=sc(nc['dark']), fold_in=sc(nc['fold_in']), fold_out=sc(nc['fold_out']),
                sc=sc, unsc=lambda S: np.asarray(S, np.float64) * ab + c)


def level_frame(spec):
    """THE LEVEL FRONT CHART for canid_cage.place_nostril (nose_frame's fields): the camera on the palate axis (image mm =
    (x, q), the line of sight +d), the leather's outline (front_outline) as `half` / `full` with its half width per image
    height (vg, hw), the midline at u_ax 0 (the nostril's chart is nostril_chart's comma, drawn in these mm)"""
    from . import canid_hull as CH
    clay = CH.clay_points(spec)
    cam = CH.front_camera(0.0, 0.0)
    half = front_outline(np.linspace(90.0, -90.0, 181))
    half[0, 0] = half[-1, 0] = 0.0
    full = np.vstack([half, (half * [-1.0, 1.0])[-2:0:-1]])
    vg = np.arange(half[:, 1].min() - 0.5, half[:, 1].max() + 0.5, 0.25)
    # (the outline's q runs monotonically from its top to its bottom: one half width per height)
    hw = np.interp(vg, half[::-1, 1], half[::-1, 0], left=0.0, right=0.0)
    return dict(cam=cam, npd=clay['np_mm'], u_ax=0.0, half=half, full=full, vg=vg, hw=hw, alpha=0.0, psi=0.0)
