"""B3g (the lead, 10-27): the stag beetle's HARD CHITIN as CREASED SUBDIVISION SURFACES, the way a hard-surface creature
modeller builds it. B3c-B3f composed the head from fields (a visual hull + a curvature flow + CSG features): every
construction left planes, shelves, slots and seams between its pieces (the tray, the shelf-like lip ending in a slot, the
boxy clypeal process, the terraced mentum). Here the head capsule is ONE closed quad CAGE whose edge loops run ALONG THE
MEASURED FEATURE LINES, creased SEMI-SHARP (forge/subdiv_sharp.py: DeRose, Kass & Truong 1998) so each edge's limit radius
meets the photos' radius, Catmull-Clark to the high's density; the surface between the loops curves by construction. The
limit mesh becomes the head's signed-distance GRID (the exact distance to its triangles, the winding number's sign, on
Warp's device), so heads/insect.capsule_descs, b03 and the rest of the pipeline run unchanged.

THE FRAME: insect_hull's plan frame in LIFE mm: x the creature's left, h above the venter's lowest point, z forward from the
clypeal tip. Vertices are (x, h, z) (the grids' axis order). The cage is built on the x >= 0 half and mirrored; the
midline vertices are shared.

THE CAGE'S TOPOLOGY (a box): the DISH is the top patch (an nA x nB grid on each half), RINGS run round it (each a closed
edge loop round the whole head: the dish's inner loop R0, the rim's crest R1, the outer faces' foot and the supraocular
ridge R2, then R3 .. R13 down the sides, the front and the back), the UNDERSIDE is the bottom patch (its boundary R14). Each
half ring has a FRONT segment (x from the midline to the front-left corner), a SIDE segment (z from the front corner to the
back corner) and a BACK segment (x from the back corner to the midline). The only extraordinary vertices are the patches'
corners (valence 3: the dish's four corners and the underside's). Features that are not rings are SQUARE RINGS inside the
grid (the orbit in a block of the side's rings, the mentum's suture in the bottom patch).

THE FEATURE LOOPS (each point's source in its table; [M] measured on a photo, [E] estimated, with its gate; B3h re-laid them on
the photos, VERSION's note):
  R1  the RIM's crest: the front margin, the anterior angle's knob, the lateral margin, the crest's lateral part (insect_hull
      FEAT rim: M1d's highlight lines, M1l's true top line) to its medial end at |x| 3.4 (M1d: the crest's highlight only at
      |x| > ~3.5), creased; then, uncreased, the DOMES' RIDGE (RIDGE_B: M1l's two peaks and the notch at M1d's columns) into
      the groove
  R0  the DISH's inner loop: the inner walls' foot, the rim less the walls' widths (FEAT rim [E], M1d's dark margin bands
      0.35-0.6 mm) on the floor (FEAT bowl3 [E]); across the domes their SHOULDER (DOME), the top patch's last rows their FACE,
      FOOT and the floor ahead (M1d's curvature-change lines): the loops follow the domes' curved fronts
  R2  the outer faces' foot: over the clypeal process its root, over the mandible bases the face's top, round the anterior
      angle its lobe's widest line (M1d's outline, SEC_WIDE), behind the eye the SUPRAOCULAR RIDGE (M1l's line, insect_hull
      FEAT lip path; M1d's band at |x| 7.55-7.75) running up into the crest at the posterior corner, behind the crest its
      back face's foot, behind the domes their back (BACK2)
  ORBIT a square ring (16 vertices) on the eye's sphere along M1l's exposed outline (SPEC eye along x across at eye_c:
      b03's eye gate's own patch), its collar (24) raised off the dome (a rounded lip), the socket (8 + 1) under the dome;
      the canthus the collar's front (M1d's canthus edge, M1l h 10.85-12.95)
  PROCESS the front rings bulged forward within |x| 2.45: ONE plate, its rows between its root and M1d's plan outline (FEAT
      clypeus_plan: the lobes fp_L / fp_R, the notch), its top M1l's under the front margin, its underside M1l's
  MENTUM a square ring in the bottom patch on M3v's trapezoid (insect_hull STROKES mentum trap), a shallow suture
  GROOVE the midline column across the back: a narrow soft valley between the domes by its targets (RIDGE_B, DOME), no crease
  BACK  R3 .. R11 behind the ridge rays at heights easing from the side's to BACK_H (R3 the posterior margin): one scheme
The other vertices (the sides, the face, the back, the underside) lie on the head's MASS (insect_hull.head_mass: the visual
hull of M1d / M1l / the sections, rounded by the constrained flow), placed by rays and relaxed along it.
"""
import hashlib
import json
import os
import time

import numpy as np

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

VERSION = 'b3h-3'                # b3h-3 (the beetle's B6, 10-29): the two spots the B5 check left, from b6_cage/g01 at L4
#                                  (out/g01_base.png -> g01_c3.png). THE ANTERIOR CORNER: R0's inward offset at the anterior
#                                  angle (WALL ant_w 0.45 on RIM_W's 0.8) passed the knob's plan radius, so R0's side points
#                                  BUNCHED into one spot and the ring edges fanned into it (a pole the dish pinched round: the
#                                  'paper-fold' corner, a self-crossing sliver at (+-6.82, 19.65, -2.13) world): ant_w 0 and the
#                                  loop's smoothing 3 -> 6 (self-crossing 70 -> 0 L4 vertices, the low's facing folds 2.10 ->
#                                  1.15 mm2). THE EYE RIM: the collar's crest stood 1.2-1.7 mm proud of the side one ring
#                                  below it (x 7.8-8.1 against 6.4-6.5) and the creased rim (orbit 2.6) hooked the limit under
#                                  it (b6_cage/out/g02_base.png's sections): ORBIT cheek 0.5 (the block's bottom row within 0.5
#                                  mm of the collar above it, tapered at the block's ends) and SHARP orbit 2.6 -> 1.2: the bake
#                                  emulation's reversed area round the orbit 0.507 -> 0.186 mm2 (under the eye 0.131 -> 0.007,
#                                  its lower rear 0.121 -> 0.020, the canthus flange 0.057 -> 0.025), no self-crossing
#                                  b3h-2 (the beetle's B5, 10-29): the MENTUM's suture out of the cage (MENTUM cage False: its
#                                  creased ring on the bottom patch folded the limit at all four of its corners, the reversed
#                                  normals at the mandible sockets); the suture is the high's micro relief. Nothing else changed.
#                                  b3h-1 (the lead's B3h, 10-27): THE CAGES RE-LAID ON THE PHOTOS. The head's top: the rim's crest
#                                  only where M1d shows an edge (R1 creased along the front margin, the anterior angles, the
#                                  lateral margins and the crest's lateral parts); across the back R1 runs on the DOMES' RIDGE
#                                  (M1l's two peaks and the notch between, at M1d's columns), uncreased; the top patch's last rows
#                                  ON the traced curvature-change lines (DOME: M1d's foot / face / shoulder per column, h02), so
#                                  the loops follow the domes' curved fronts; a soft groove between them (the midline column a
#                                  narrow valley, no crease; M1d's trough, h04); behind the ridge ONE scheme (R2 the ridge's back,
#                                  R3 .. R11 rays at heights easing from the side's to the back's: no lobe / side ramp); the
#                                  clypeal process ONE bilobed plate (its rows offsets of M1d's outline); the side running outward
#                                  under the supraocular ridge to M1d's widest outline (R4 / R5 out; R3 kept 0.06 inside the
#                                  ridge, a shallow cove: pushed out too, the ridge's radius vanished, r6 0.2-2.2), the ridge
#                                  creased crisper; the eye in a raised rounded collar (no crease); the underside's rim held in
#                                  front of the mentum's corners after the relaxation (rim_hold: b3g's turned-over quads there);
#                                  the field 0.025 mm, exact near the surface, unblurred there (HEAD_FIELD).
#                                  b3g-5 (the B3g checker, 10-27): the lobes' BACK. The reference top's bowl (the dish's floor)
#                                  is cut away behind the lobes' ridge (BOWL back_cut / back_fade): left in, its paraboloid kept
#                                  rising behind the dish (15.3-15.8 at z -9.1 .. -9.4) over the lobes' own back (13.6-14.2;
#                                  M1l's top line 15.50 / 14.43 at z -9.00 / -9.25) and set ring 6 (z -9.13 .. -9.30) 1.0-1.2
#                                  mm above it and 0.1-0.3 mm BEHIND ring 7 (the buried back at h 13.70): the surface turned
#                                  under itself, a lip along the lobes' back, a fin 1.3 mm tall at |x| 5.4-5.7 (a second spike
#                                  behind the horn in the side view) and an undercut pocket at z -9.0 (check c01 / c06). Ring 6
#                                  now lies ON the lobes' back halfway down from ring 5 to ring 7, so the back cannot fold.
#                                  b3g-4: the front margin's sharpness 3.0 -> 4.0, the supraocular ridge's 2.8 -> 4.5 (b3g-3's
#                                  limit radii 0.034-0.069 / 0.080-0.138; the field's 0.052-0.094 / 0.121-0.156 by k01's rule).
#                                  b3g-3: the lobes domes peaked at |x| 2.0.
#                                  b3g-2: the collar wraps the dome outside M1l's outline (b3g-1's exposed patch 2.275 x 2.441);
#                                  the targets on the mass smoothed (MASS_SMOOTH: the face beside the process lumpy at b3g-1)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
CACHE = os.path.join(REPO, 'work', 'bestiary', 'beetle', 'cache_hull')

# ============================================================================================ the layout and the tables
LAYOUT = dict(nA=20, nB=18, K=14,
              # the front segment's x (0 .. nA): fine over the clypeal process (|x| <= 2.45), then even to the front-left
              # corner (the front margin's turn into the anterior angle)
              front_x=(0.0, 0.30, 0.60, 0.90, 1.20, 1.50, 1.80, 2.12, 2.45), corner_front=(7.25, -1.13),
              # the side segment's z (nA .. nA + nB): the anterior angle, the ORBIT block (8 intervals, z -2.6 .. -5.6), the
              # postocular side, to the back-left corner (the lateral margin's turn into the crest)
              side_z=(-1.13, -1.42, -1.72, -2.02, -2.32, -2.60, -2.975, -3.35, -3.725, -4.10, -4.475, -4.85, -5.225, -5.60,
                      -5.90, -6.20, -6.48, -6.74, -7.00), corner_back=(7.11, -7.00),
              orbit_i=(25, 33), orbit_k=(3, 11),
              # the side rings' heights (k 3 .. 11: the orbit block; the eye's centre 11.456 at k 7)
              side_h=(13.15, 12.725, 12.30, 11.875, 11.45, 11.025, 10.60, 10.175, 9.75),
              # b3h: the back segment's x (nA + 1, the back corner to the midline): graded, columns ON the ridge's knob A
              # (2.10), notch (1.80) and dome top (1.25), and 0.14 beside the midline for the groove's soft valley
              back_x=(7.11, 6.62, 6.14, 5.67, 5.21, 4.77, 4.34, 3.93, 3.54, 3.17, 2.81, 2.46, 2.10, 1.80, 1.52, 1.25, 0.98,
                      0.70, 0.42, 0.14, 0.0),
              mentum_a=14, mentum_b=(1, 5))
# the RIM (R1): FEAT rim's points (insect_hull, B3e e03 / e05: M1d's highlight lines and outline, M1l's true top line) to the
# crest's medial end (|x| 3.40); (x, z, h, source)
RIM = ((0.00, -1.13, 14.12, 'M1d front margin highlight z -1.13; M1l top h'), (0.70, -1.24, 14.14, 'M1d / M1l'),
       (1.20, -1.30, 14.16, 'M1d -1.30 at |x| 1.2 / M1l'), (2.50, -1.24, 14.19, 'M1d / M1l'), (4.00, -1.16, 14.23, 'M1d / M1l'),
       (5.50, -1.08, 14.28, 'M1d / M1l'), (6.60, -1.02, 14.30, 'M1d / M1l'),
       (7.40, -1.18, 14.30, 'M1d outline (anterior angle)'), (7.80, -1.50, 14.70, 'M1d outline / M1l'),
       (8.00, -1.75, 15.08, 'M1d outline / M1l'), (8.08, -2.00, 15.30, 'M1l knob 15.33 at z -2.00 (e05), its top rounded'),
       (7.98, -2.40, 15.22, 'M1d / M1l'), (7.80, -2.85, 15.06, 'M1d / M1l'), (7.58, -3.25, 14.89, 'M1d / M1l'),
       (7.46, -3.60, 14.78, 'M1d lateral margin |x| 7.41 / M1l top'), (7.42, -3.90, 14.58, 'M1d / M1l'),
       (7.41, -4.10, 14.47, 'M1d / M1l notch 14.46 at -4.05'), (7.41, -4.70, 14.49, 'M1d / M1l'),
       (7.41, -5.30, 14.53, 'M1d / M1l'), (7.40, -5.90, 14.58, 'M1d / M1l'), (7.36, -6.50, 14.62, 'M1d / M1l'),
       (7.25, -6.90, 14.74, 'M1d / M1l'), (6.75, -7.25, 14.85, 'M1d crest highlight / M1l top'),
       (5.90, -7.40, 15.02, 'M1d crest (5.90, -7.47) / M1l'), (5.05, -7.50, 15.10, 'M1d / M1l 15.10 at -7.5'),
       (4.20, -7.55, 15.16, 'M1d / M1l'), (3.40, -7.62, 15.25, 'M1d crest medial end (3.80, -7.63) / M1l'))
RIM_W = (0.50, 0.50, 0.50, 0.55, 0.60, 0.60, 0.50, 0.50, 0.65, 0.80, 0.85, 0.80, 0.60, 0.35, 0.35, 0.35, 0.35, 0.35,
         0.35, 0.35, 0.35, 0.35, 0.40, 0.40, 0.40, 0.40, 0.45)   # the inner walls' widths at RIM's points (FEAT rim, [E])
# the outer faces' foot: the drop and run from the crest [E] (the front margin's face 66-68 deg, the crest's back 48-52 deg,
# FEAT rim); the clypeal process's top under the front margin (M1l, FEAT process top)
FACE = dict(front_drop=0.62, front_run=0.30, proc_top=((-1.13, 13.86), (-0.55, 13.88), (0.20, 13.84), (0.70, 13.72)),
            crest_drop=0.45, crest_run=0.34)
# R2 on the side: the anterior angle's lobe foot (M1d's outline less 0.03; SEC_WIDE's 13.35 at z -2.0) into the SUPRAOCULAR
# RIDGE (M1l: FEAT lip path; M1d: |x| 7.55-7.75 behind the eye) [E: its x over the eye and at its ends]: (z, x, h, source)
RIDGE = ((-1.13, 8.30, 13.35, 'M1d outline 8.35 at -0.75; SEC_WIDE 13.30'), (-1.42, 8.68, 13.35, 'M1d outline 8.74 at -1.5'),
         (-1.72, 8.72, 13.35, 'M1d outline'), (-2.02, 8.72, 13.35, 'M1d outline 8.755 at -2.0; SEC_WIDE 13.35'),
         (-2.32, 8.62, 13.40, 'M1d outline'), (-2.60, 8.50, 13.50, 'M1d outline 8.59 at -2.5'),
         (-2.975, 8.26, 13.80, 'M1d canthus edge (8.29, -3.25)'), (-3.35, 7.98, 14.15, 'M1l ridge front (-3.30, 14.20)'),
         (-3.725, 7.80, 14.05, 'M1l ridge (f02_m1l_ridge: 13.99 at -4.0)'), (-4.10, 7.72, 13.93, 'M1l ridge'),
         (-4.475, 7.67, 13.76, 'M1l ridge (-4.60, 13.70)'), (-4.85, 7.65, 13.58, 'M1l ridge (-5.00, 13.52)'),
         (-5.225, 7.65, 13.54, 'M1l ridge; M1d band 7.55-7.75'), (-5.60, 7.65, 13.58, 'M1l e03 strip (-5.64, 13.65)'),
         (-5.90, 7.65, 13.61, 'M1l ridge'), (-6.20, 7.65, 13.63, 'M1l ridge'), (-6.48, 7.64, 13.66, 'M1l ridge'),
         (-6.74, 7.58, 13.74, 'M1l ridge (-6.75, 13.74)'), (-7.00, 7.42, 13.94, 'M1l ridge (-7.04, 13.97) rising'))
# the ORBIT: the rim ON the eye's sphere along M1l's outline; the collar's crest (b3h) RAISED `lip` off the dome along the
# sphere's normal, `collar_out` outside the rim, never under the side surface + `collar` (M1l h01_eye: a dark rounded collar
# 0.10-0.17 mm wide round the whole eye, its lower rear too; b3g's crest at the side + 0.04 met the dome in a V-notch there, the
# B3g check c09), its front the canthus (M1d's edge x 8.29-8.60 at z -2.5 .. -3.25, M1l h 10.85-12.95); the socket `socket` /
# `floor` under the dome [E]
ORBIT = dict(collar=0.04, collar_out=0.20, lip=0.07, socket=0.30, floor=0.55, canthus_x=8.36, canthus_h=(10.85, 12.95),
             rim_clip=0.995, wrap=0.15,    # wrap: the block's boundary over the dome outside the outline (B3f's collar 0.18)
             cheek=0.5)                    # (b3h-3) the block's bottom row within this of the collar above it (orbit())
# the clypeal process (M1d's plan outline: FEAT clypeus_plan, res_s01a fp_L / fp_R; the notch rounded, b3h: M1d h01_proc at 200
# px/mm, the ears' tips (1.40, 0.70) / (-1.68, 0.71), the notch's bottom z 0.10-0.18; M1l: its top under the front margin, its
# underside FEAT clypeus_floor (0.70, 13.25) -> (0.15, 12.85)) [E: the edge's rows]. b3h: ONE bilobed plate, its rows the
# outline's inward offsets (`rows`: (offset along the outline's inward normal mm, height) for k 3 .. 7: the top, the rim's top,
# the rim, its underside, the underside), blended into the face beside it over `blend` mm past the outline's end
PROCESS = dict(plan=((0.00, 0.10), (0.18, 0.15), (0.45, 0.38), (1.05, 0.66), (1.55, 0.70), (1.95, 0.05), (2.45, -0.45)),
               top=13.80, top_front=13.68, edge_lo=13.30, under=12.98, under_back=0.48, face=12.55,
               rows=((0.45, 13.80), (0.88, 13.66), (1.0, 13.48), (0.86, 13.28), (0.40, 12.98)), blend=(2.0, 0.9),
               under_depth=0.60)
#                                  (blend (x0, run): the plate's rows eased into the face's from x0 over run: from the outline's
#                                  end (2.45 over 0.6) the plate's lateral underside met the face in a slit, h08 _h6 proc_front)
#                                  (rows: (the plan fraction from the plate's root, R2 (k 3-5), or from the face under the
#                                  plate (k 6, 7), to the outline; the height): M1l's top 13.84-13.72 and underside 13.25-12.85,
#                                  FACE proc_top / FEAT clypeus_floor; b3g's rows by the outline's z at fixed x, their front rows
#                                  pinned to the mass's face and blended into its rays over x 1.95-2.45: lumps at 150 px/mm)
# ---- b3h THE BACK OF THE HEAD, traced (BEETLE_BODY_PHOTOS 7e). DOME: the curvature-change lines of M1d's 0.35 mm-blurred
# luminance per column (beetle/scratch_b03h/h02_domes.py, h02_trace_m1d.png: M1d is ring-lit, so a glossy face is darkest where it
# tilts most), left and right averaged (the right dome reads 0.3-0.4 mm forward of the left: the specimen and its light), the
# groove's tongue (|x| < 0.4) from the left column's foot (-7.83 at x 0, -7.43 at 0.2): FOOT the floor turning up (half way
# from the floor's brightness to the face's), FACE the darkest (the steepest), SHOULDER half way from the face's to the top's;
# the rows of the top patch's last loops (b nB-2, nB-1) and R0 lie ON them; `pre` the floor row ahead of the foot (b nB-3);
# the face's and the shoulder's heights these shares of the rise from the floor to the ridge [E]
DOME = dict(x=(0.00, 0.14, 0.42, 0.80, 1.20, 1.60, 2.00, 2.40, 2.80, 3.20, 3.60),
            foot=(-6.58, -6.57, -6.54, -6.53, -6.58, -6.60, -6.75, -6.88, -6.88, -6.85, -6.72),
            face=(-7.02, -7.00, -6.96, -6.86, -6.90, -6.98, -7.15, -7.30, -7.32, -7.18, -7.04),
            shoulder=(-7.84, -7.82, -7.78, -7.70, -7.67, -7.70, -7.72, -7.70, -7.62, -7.48, -7.33),
            pre=0.45, face_up=0.30, shoulder_up=0.75,
            smooth=0.35,                       # the rows' rise to the ridge from its heights smoothed over this (mm, along x):
            #                                    the notch between knob A and top B is the ridge's own (M1l's silhouette), not
            #                                    the front's (b3h-1 v2: carried down the front it striped it, h06 back_g5_h3)
            groove=(0.10, 0.12, 0.0, 0.5, 0.8),  # the GROOVE in the rows: its depth at the ridge (RIDGE_B), its half-width
            #                                    (gaussian, mm), the shares of that depth at the foot, the face and the shoulder
            crest_rows=(0.28, 0.56, 1.00),     # in the crest's region the rows ahead of its inner foot (R0): face, foot, pre
            x_blend=(3.6, 4.6))                # the dome's rows -> the crest region's (smooth01 over this x)
#                                  (b3h-1 v1: the domes' rows to x 2.0 only, easing into the crest's narrow wall by 3.2, left a
#                                  valley between each dome and the crest's medial end (h03 _h1); M1d's foot runs on at -6.85 to x
#                                  3.4 (h02): the domes' fronts reach the crest's medial end. The groove at the foot: c08's front
#                                  runs straight across the midline (-6.18 at x 0, -6.13 at 1.4, h02); M1d's left foot at x 0-0.2
#                                  (-7.83 / -7.43) is the groove's own dark line (FWHM 0.13-0.42): the groove starts at the foot
#                                  and lags the domes' face and shoulder by 0.25-0.35 behind)
# R1 BACK: the crest's lateral part (FEAT rim: M1d's crest highlight, M1l's true top) to its medial end, then the DOMES' RIDGE
# (uncreased): M1l's top silhouette behind the eye (h04: the knob A 15.73 at z -8.15 .. -8.20, the notch 15.615 at -8.35, the
# dome top B 16.01 at -8.65, the front slope 15.43-15.52 at -7.8 .. -7.9) at M1d's columns (h02's top line: the highlight's
# peak per column, x 1.2-1.4 brightest; it curves forward laterally to -8.05 at x 2.0, -7.82 at 2.2), down to the groove; (x, z,
# h, source)
RIDGE_B = ((7.11, -7.00, 14.77, 'the back corner (corner_back; M1l 14.76 at z -7.0)'),
           (6.75, -7.25, 14.85, 'M1d crest highlight / M1l top'), (5.90, -7.40, 15.02, 'M1d crest (5.90, -7.47) / M1l'),
           (5.05, -7.50, 15.10, 'M1d / M1l 15.10 at -7.5'), (4.20, -7.55, 15.16, 'M1d / M1l'),
           (3.40, -7.62, 15.25, 'M1d crest medial end (3.80, -7.63); M1l 15.24-15.26 at z -7.65 .. -7.70'),
           (2.75, -7.86, 15.48, 'the ridge into the crest: M1d top line; M1l 15.48 at z -7.85'),
           (2.10, -8.15, 15.73, 'knob A: M1l peak 15.73 at z -8.15 .. -8.20 (h04); M1d top line x 2.0-2.2'),
           (1.80, -8.35, 15.62, 'the notch: M1l 15.615 at z -8.35 (h04); M1d top line x 1.8 (-8.27)'),
           (1.52, -8.50, 15.89, 'M1l 15.82-15.90 at z -8.45 .. -8.50'),
           (1.25, -8.65, 16.01, 'dome top B: M1l peak 16.01 at z -8.65 (h04); M1d highlight brightest at x 1.2-1.4'),
           (0.98, -8.67, 15.98, '[E] the dome toward the groove (M1d top brightness 0.61-0.68 at x 0.6-0.8, 0.75-0.81 at the '
                                'top: a gentle slope)'),
           (0.70, -8.68, 15.95, '[E]'), (0.42, -8.69, 15.89, '[E] (M1d 0.55-0.63 at x 0.2-0.4)'),
           (0.14, -8.70, 15.85, 'the groove\'s flank (DOME groove) [E]'),
           (0.00, -8.70, 15.78, 'the groove bottom: M1d trough FWHM 0.13-0.42 mm (median 0.22), no bright line at its bottom '
                                '(ring light): radius <= ~0.1, so a narrow shallow valley (h04) [E depth 0.10]'))
# R2 BACK: behind the ridge. Over the domes (|x| <= 1.6) M1l's back line: 0.75 under the top 0.40 behind it (16.01 at -8.65 ->
# 15.26 at -9.05, h04); behind the knob and the crest the back face's foot (FACE crest_drop / crest_run), eased between
BACK2 = dict(dome_drop=0.75, dome_run=0.40, x_blend=(1.6, 2.1))
# R4 .. R11 BACK: ONE scheme with the side, rays from the spine at heights easing from the side's (side_h, at the back corner)
# to the back's (h, R4 .. R11) over x_blend; R3 between R2 and R4, `bulge` x their chord outward (the back's profile convex: M1l
# 14.41 / 14.16 at z -9.25 / -9.40 behind the domes, h04). b3g's lobe rows at fixed z blended into the side's rays (its `wb`
# ramp, x 4.2 .. 6.0) crumpled the posterior corners (the B3g check); b3h-1 v1's R3 a ray at 14.15 left the mass (low behind
# the crest: its top under the crest's back face) AHEAD of R2 at x 3-5 (h07)
BACK_H = dict(h=(13.35, 12.85, 12.35, 11.85, 11.35, 10.85, 10.30, 9.75), x_blend=(4.4, 6.9), bulge=0.05)
BOWL = dict(h0=13.42, zc=-4.30, kx=0.016, kx_front=0.010, kz=0.064, tz=-0.060, min_drop=0.25)   # FEAT bowl3 [E]
# the SIDE under the supraocular ridge (b3h; the lead's call: the side runs OUTWARD under the ridge to M1d's widest outline,
# insect_hull DORSAL 8.12 / 7.94 / 7.80 / 7.62 at z -5.0 / -5.94 / -6.5 / -7.2; BEETLE_BODY_PHOTOS 7d): behind z z0 (eased over
# `ease`) R3 at least `r3_out` outside the ridge, R4 / R5 at least DORSAL less `r4_in` / `r5_in`
SIDE = dict(z0=-5.45, ease=0.45, r3_in=0.06, r4_in=0.14, r5_in=0.05, z_end=(-6.55, -7.00))
#                                  (R3 stays r3_in INSIDE the ridge, a shallow cove: M1l prints the ridge as a thin highlight
#                                  line, which needs the surface under it to turn in; b3h-1 v2 set R3 outside it and the ridge's
#                                  turn fell to 2-44 deg at z -6.0 / -6.5 (r6 2.17 / 0.21, h05 _h9): the profile from the lateral
#                                  margin's crest through the ridge to the widest outline is straight. R4 / R5 run out to M1d's
#                                  widest outline below it)
#                                  (z0 -5.45: behind the orbit block, i > 33; from z -4.70 the push reached the block's top-rear
#                                  corner and stood a wedge over the collar, h08 _h5 eye_side)
#                                  (z_end: the push eased out toward the back corner, where M1d's outline closes on the ridge
#                                  (0.16-0.20 outside it at z -6.5 .. -7.2) and the rings turn onto the back: held to the corner,
#                                  the side's last index jumped 0.3-0.5 mm against the corner's, a concave sweep below the
#                                  ridge's end, h08 _h4 corner_low)
MENTUM = dict(trap=((3.90, -1.30), (4.10, -2.20), (2.50, -3.70)), suture=0.06, bulge=0.04,      # M3v; depths [E]
              cage=False)
#                                  (b3h-2, the beetle's B5) cage False: the suture is NOT built in the cage. Built (b3h-1), its
#                                  creased square ring forced M3v's trapezoid onto the bottom patch's grid: its rear edge (x 0 ..
#                                  2.50 over 15 columns) against the grid's natural 0 .. 4.2 sheared the rows behind it ~70 deg at
#                                  the creased rear corners, its front corner (3.90, -1.30) sat ON the underside rim's own turn
#                                  (rows 0 and 1 swapped order there), and rim_hold's 0.02 mm strip in front of its front edge left
#                                  R13 behind the rim at the same height (R12 -> R13 -> R14 -> row 1 zigzagged): the limit crossed
#                                  itself at all four corners (b5_cage c01: 16,611 L6 vertices at each front corner, 404 at each
#                                  rear one), the engineering check's black crescents at the mandible sockets. The suture is a
#                                  0.1 mm groove: it lives in the high's micro relief (stag_beetle_sculpt's head groove mask, on
#                                  this same trapezoid), the bottom patch stays the regular grid on the mass, rim_hold is not
#                                  needed. True rebuilds b3h-1's ring (and its folds)
# SHARPNESS per loop (DKT): calibrated so each limit edge's radius meets the photos' bound (BEETLE_BODY_PHOTOS 7b: the front
# margin <= 0.060, the lateral margins <= 0.078-0.094, the crest <= 0.16-0.18, the supraocular ridge <= 0.065). b3h: no groove
# crease (a soft valley by its targets); the crest's crease ends at its medial end (crest_end, eased over crest_taper); the
# supraocular ridge `ridge` behind z -5.8 (b3g-5's limit 0.064-0.079 there at 4.5, h05); the process's rim a light crease
SHARP = dict(front=4.0, angle=0.5, lateral=2.6, crest=2.0, crest_end=3.40, crest_taper=1.0, ridge=4.5, ridge_aft=5.5,
             ridge_back=1.6, orbit=1.2, collar=0.0, proc_edge=0.0, mentum=1.4)
#                                  (orbit 2.6 -> 1.2, b3h-3: the creased rim hooked the limit under the collar, the eye-rim
#                                  creases; the rim still reads as the eye's edge, the eye's own sphere meets it there)
#                                  (collar 0: the raised collar rounds by its loops' spacing; creased 0.6 its crest read as a thin
#                                  sharp ring, h08 _h5 eye_side; M1l a rounded dark band 0.10-0.17 mm wide)
#                                  (proc_edge 0: a crease along the rim's top edge (b3h-1 v1, 0.8) followed the outline's every
#                                  wave; the rim rounds by its rows' spacing)
WALL = dict(rise=0.25, ant_w=0.0, ant_rise=0.25, smooth=6)    # R0 this share of the inner wall's height over the floor (the
#                                      foot curves into the bowl); at the anterior angle the wall `ant_w` wider and its foot
#                                      `ant_rise` higher (the hump); R0's plan line smoothed `smooth` times
#                                      (b3h-3: ant_w 0.45 -> 0, smooth 3 -> 6: the wider wall's offset passed the knob's plan
#                                      radius and bunched R0's points into a pole, the pinched anterior corner)
UNDER = dict(**{'in': 1.6}, in_front=0.85, smooth=4, mentum_gap=0.02, mentum_reach=0.15, mentum_taper=(1.0, 0.4, 0.1),
             mentum_band=(0.0, 0.33))   # R14: R11's plan ring offset inward by this (mm; along the front
#                                      in_front), smoothed (the underside's rim); b3h: rim_hold's gap in front of the mentum's
#                                      front edge, its reach past the corner, its taper over the neighbours, and the shares of
#                                      the move R12 / R13 take (h15 on the limit: R12 / R13 moved with the rim by 1/3 and 2/3
#                                      tightened the rim's turn, the under terrace 10.2-10.5 um rms; the rim alone and R13 a
#                                      third 9.0, B3g-5's limit 9.2). The suture's creased front corners fold the limit in a
#                                      sub-cell patch at every gap (inverted micro-triangles; b3g's too): at 0.02 two 1-cell
#                                      voids at x +-3.77, z -1.22 (h13), at 0.10 four candidates a corner (h19): HEAD_FIELD fill
SPINE = dict(x_in=5.4, z_front=-2.6, z_back=-5.6)   # the rings' rays leave this plan rectangle radially (inside the head)
LEVELS = dict(fit=5, out=5)
RELAX = dict(iters=16, lam=0.5)
CLAMP = (-1.9, 2.5)
# b3h THE HEAD'S FIELD (the lead's call 3: the shipped field at the limit surface's radii, at most 0.035 mm, blur no more than one
# cell): the exact distance on `h` within `near` of the surface (blurred `s_near`), the coarse pass (`coarse` x h, trilinear)
# blurred `s_far` from `far` out, eased between; the box the limit mesh's + `pad` (b3g: the mass's box at 0.05, blurred 0.03
# everywhere: the front margin and the supraocular ridge 0.02-0.05 mm rounder on the field than on the limit, h05)
HEAD_FIELD = dict(h=0.025, near=0.16, far=0.28, s_near=0.0, s_far=0.07, coarse=4, pad=0.6, fill=True)
#                                  (fill: every 6-connected region of f > 0 that does not reach the grid's border, an enclosed
#                                  void inside the solid, which only a folded patch of the limit can make (its winding number
#                                  < 0.5 inside the solid: the mentum suture's front corners), set inside, -h / 2)
#                                  (h 0.025: on b3h-1's limit the supraocular ridge reads r6 0.078 / 0.071 / 0.063 at z -6.5 on
#                                  exact fields at 0.035 / 0.030 / 0.025 (limit 0.057; bound 0.065), the front margin 0.059 /
#                                  0.057 / 0.057 at x 6.0 (limit 0.053; bound 0.060), h05; blurred at one cell, 0.035, the front
#                                  margin read 0.060-0.084: the blur, not the spacing, rounded b3g's edges)
MASS_SMOOTH = dict(general=0.30, face=0.80)   # the mass smoothed for the cage's targets (Mass sigma): everywhere, and on the
#                                               face beside the clypeal process (b03 _b3gq1: lumps there, the mass's condyle
#                                               balls, insect_hull inner_balls, which the mandible bases only partly cover)


# ============================================================================================ small helpers
def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def cache_key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=lambda o: np.asarray(o).tolist()).encode()).hexdigest()[:16]


def pchip(xs, ys):
    from scipy.interpolate import PchipInterpolator
    xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    o = np.argsort(xs)
    return PchipInterpolator(xs[o], ys[o], extrapolate=True)


# ============================================================================================ the reference surfaces
class Mass:
    """the head's MASS (insect_hull.head_mass: hull + flow, the x >= 0 half): its distance (trilinear, mirrored), gradient,
    projection and rays"""

    def __init__(self, spec, log=print, sigma=0.0):
        """sigma (mm): the distance gaussian-smoothed first (MASS_SMOOTH: the flow's level-set terraces, 3-16 um at
        0.15-0.25 mm on the underside, B3f check k02; the face's condyle bulges)"""
        from . import insect_hull as IH
        from scipy.ndimage import gaussian_filter
        M = IH.head_mass(spec, log)
        self.h = float(M['h'])
        phi = np.asarray(M['phi'], np.float64)
        if sigma > 0:
            # (the x >= 0 half: mirrored before the filter so the midline stays symmetric)
            full = np.concatenate([phi[:0:-1], phi], axis=0)
            phi = gaussian_filter(full, sigma / self.h, mode='nearest')[phi.shape[0] - 1:]
        self.phi = phi
        self.lo = np.asarray(M['lo'], np.float64)

    def __call__(self, P):
        from scipy import ndimage as nd
        P = np.atleast_2d(np.asarray(P, np.float64))
        q = [(np.abs(P[:, 0]) - self.lo[0]) / self.h, (P[:, 1] - self.lo[1]) / self.h, (P[:, 2] - self.lo[2]) / self.h]
        return nd.map_coordinates(self.phi, q, order=1, mode='nearest')

    def grad(self, P, e=0.02):
        P = np.atleast_2d(np.asarray(P, np.float64))
        g = np.zeros_like(P)
        for k in range(3):
            d = np.zeros(3)
            d[k] = e
            g[:, k] = (self(P + d) - self(P - d)) / (2 * e)
        return g

    def project(self, P, it=6):
        P = np.atleast_2d(np.asarray(P, np.float64)).copy()
        for _ in range(it):
            f = self(P)
            g = self.grad(P)
            P -= (f / np.maximum((g * g).sum(1), 1e-6))[:, None] * g
        return P

    def ray(self, A, D, reach=9.0, step=0.02, enter=False):
        """the first EXIT (enter: the first ENTRY) of the mass along A + t D, refined by bisection; NaN where none"""
        A = np.atleast_2d(np.asarray(A, np.float64))
        D = np.atleast_2d(np.asarray(D, np.float64))
        D = D / np.linalg.norm(D, axis=1, keepdims=True)
        ts = np.arange(0.0, reach + 1e-9, step)
        Q = A[:, None, :] + ts[None, :, None] * D[:, None, :]
        f = self(Q.reshape(-1, 3)).reshape(len(A), len(ts))
        out = np.full((len(A), 3), np.nan)
        for j in range(len(A)):
            cond = (f[j, :-1] >= 0) & (f[j, 1:] < 0) if enter else (f[j, :-1] < 0) & (f[j, 1:] >= 0)
            hit = np.nonzero(cond)[0]
            if not len(hit):
                continue
            a_, b_ = ts[hit[0]], ts[hit[0] + 1]
            fa = f[j, hit[0]]
            for _ in range(28):
                m_ = 0.5 * (a_ + b_)
                if (self(A[j] + m_ * D[j])[0] < 0) == (fa < 0):
                    a_ = m_
                else:
                    b_ = m_
            out[j] = A[j] + 0.5 * (a_ + b_) * D[j]
        return out

    def top(self, x, z, h0=17.5):
        """the mass's top height at plan points (the first entry going down)"""
        x, z = np.atleast_1d(x), np.atleast_1d(z)
        A = np.column_stack([x, np.full(len(x), h0), z])
        return self.ray(A, np.tile([0.0, -1.0, 0.0], (len(x), 1)), reach=12.0, enter=True)[:, 1]


def bowl(x, z):
    """the dish's floor (FEAT bowl3, [E])"""
    b = BOWL
    z = np.asarray(z, np.float64)
    kx = b['kx_front'] + (b['kx'] - b['kx_front']) * smooth01((-z - 1.8) / 1.5)
    return b['h0'] + kx * np.asarray(x, np.float64) ** 2 + b['kz'] * (z - b['zc']) ** 2 + b['tz'] * (z - b['zc'])


def top_ref(x, z):
    """the reference top of the dish's interior (the relaxation's kind-1 vertices): its floor (b3h: the domes and the groove are
    the fixed rows' own targets, DOME / RIDGE_B, not a field)"""
    return bowl(x, z)


def ridge_at(x):
    """R1's back segment at |x|: (z, h) along RIDGE_B (the crest, then the domes' ridge to the groove), PCHIP in x"""
    R = np.array([r[:3] for r in RIDGE_B], np.float64)
    x = np.abs(np.asarray(x, np.float64))
    return pchip(R[:, 0], R[:, 1])(x), pchip(R[:, 0], R[:, 2])(x)


_PROC = {}


def _proc_curve():
    if not _PROC:
        pr = np.array(PROCESS['plan'], np.float64)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pr, axis=0), axis=1))])
        from scipy.interpolate import PchipInterpolator
        _PROC['x'] = PchipInterpolator(s / s[-1], pr[:, 0])
        _PROC['z'] = PchipInterpolator(s / s[-1], pr[:, 1])
    return _PROC


def proc_outline(t):
    """the clypeal process's plan outline (PROCESS plan, PCHIP by arc length) at the arc-length fraction t (0 the notch, 1 its
    lateral end): (x, z)"""
    P = _proc_curve()
    return np.array([float(P['x'](t)), float(P['z'](t))])


def proc_normal(t, e=1e-3):
    """the outline's inward normal in plan at t (toward the head: away from the outline's outside)"""
    a, b = proc_outline(max(t - e, 0.0)), proc_outline(min(t + e, 1.0))
    tg = (b - a) / max(np.linalg.norm(b - a), 1e-12)
    n = np.array([tg[1], -tg[0]])                     # (the outline runs +x from the notch: its outside is +z)
    return n if n[1] < 0 or (abs(n[1]) < 1e-9 and n[0] < 0) else -n


_DOME_H = {}


def dome_height(x):
    """the domes' ridge height at |x| SMOOTHED along x (DOME smooth), the groove taken out (the dome continuous across the
    midline at its value at |x| 0.42): the height the front's rows rise toward"""
    if not _DOME_H:
        xx = np.linspace(-6.0, 6.0, 2401)
        _, hh = ridge_at(xx)
        hh = np.where(np.abs(xx) < 0.42, float(ridge_at(0.42)[1]), hh)
        from scipy.ndimage import gaussian_filter1d
        _DOME_H['x'], _DOME_H['h'] = xx, gaussian_filter1d(hh, DOME['smooth'] / (xx[1] - xx[0]), mode='nearest')
    return float(np.interp(abs(x), _DOME_H['x'], _DOME_H['h']))


def dome_rows(x, z1, h1, z0c):
    """the top patch's last rows at |x| (b3h): z and h of the PRE-foot, FOOT and FACE rows and of R0 (the SHOULDER), given R1's
    (z1, h1) there and z0c, the crest region's R0 (its inner wall's foot). Over the domes the traced lines (DOME), the face and
    the shoulder at DOME face_up / shoulder_up of the rise from the floor to the ridge; in the crest's region (x past DOME
    x_blend) the floor rows ahead of R0 (crest_rows) and R0 at WALL rise; eased between"""
    d = DOME
    x = float(abs(x))
    xs = np.array(d['x'])
    zf = float(pchip(xs, d['foot'])(min(x, xs[-1])))
    za = float(pchip(xs, d['face'])(min(x, xs[-1])))
    zs = float(pchip(xs, d['shoulder'])(min(x, xs[-1])))
    zp = zf + d['pre']
    fl = lambda z: float(bowl(x, z))                                                    # noqa: E731
    # the rise toward the ridge from its SMOOTHED heights (DOME smooth; the groove taken out first, then put back per row)
    gd, gw, g_foot, g_face, g_sh = d['groove']
    gx = float(np.exp(-(x / gw) ** 2))
    hs = dome_height(x)
    dome = dict(pre=(zp, fl(zp)), foot=(zf, fl(zf) - g_foot * gd * gx),
                face=(za, fl(za) + d['face_up'] * (hs - fl(za)) - g_face * gd * gx),
                shoulder=(zs, fl(zs) + d['shoulder_up'] * (hs - fl(zs)) - g_sh * gd * gx))
    ra, rf, rp = d['crest_rows']
    F0 = min(fl(z0c), h1 - BOWL['min_drop'])
    crest = dict(pre=(z0c + rp, fl(z0c + rp)), foot=(z0c + rf, fl(z0c + rf)), face=(z0c + ra, fl(z0c + ra)),
                 shoulder=(z0c, F0 + WALL['rise'] * (h1 - F0)))
    w = float(smooth01((x - d['x_blend'][0]) / (d['x_blend'][1] - d['x_blend'][0])))
    return {k: ((1 - w) * dome[k][0] + w * crest[k][0], (1 - w) * dome[k][1] + w * crest[k][1]) for k in dome}, w


# ============================================================================================ the cage
class Cage:
    """the half cage's index structure; targets per vertex; loops and creases; the full (mirrored, welded) mesh"""

    def __init__(self):
        L = LAYOUT
        self.nA, self.nB, self.K = L['nA'], L['nB'], L['K']
        nA, nB, K = self.nA, self.nB, self.K
        self.M = 2 * nA + nB + 1
        cnt = 0
        self.T = np.arange((nA + 1) * (nB + 1)).reshape(nA + 1, nB + 1)
        cnt = self.T.size
        self.R = np.full((K + 1, self.M), -1, int)
        for i in range(self.M):
            self.R[0, i] = self.boundary(self.T, i)
        for k in range(1, K):
            self.R[k] = cnt + np.arange(self.M)
            cnt += self.M
        self.B = cnt + np.arange((nA + 1) * (nB + 1)).reshape(nA + 1, nB + 1)
        cnt += self.B.size
        for i in range(self.M):
            self.R[K, i] = self.boundary(self.B, i)
        self.n_half = cnt
        Q = []
        for a in range(nA):
            for b in range(nB):
                Q.append((self.T[a, b], self.T[a + 1, b], self.T[a + 1, b + 1], self.T[a, b + 1]))
        for k in range(K):
            for i in range(self.M - 1):
                # (wound so each shared edge runs opposite ways in its two quads: the top patch's (a + 1) x (b + 1) order
                # faces up, these face out, the bottom patch faces down)
                Q.append((self.R[k, i], self.R[k + 1, i], self.R[k + 1, i + 1], self.R[k, i + 1]))
        for a in range(nA):
            for b in range(nB):
                Q.append((self.B[a, b], self.B[a, b + 1], self.B[a + 1, b + 1], self.B[a + 1, b]))
        self.Qh = np.array(Q, int)
        self.P = np.full((self.n_half, 3), np.nan)          # the targets (x, h, z)
        self.fixed = np.zeros(self.n_half, bool)           # set by the features (not relaxed)
        self.kind = np.zeros(self.n_half, int)             # 0 on the mass, 1 on the top (dish / lobes: h from top_ref)
        self.src = {}                                      # vertex -> its source tag
        self.sharp_h = {}                                  # (a, b) half-cage pairs -> sharpness
        self.loops = {}                                    # name -> half-cage vertex ids

    def boundary(self, G, i):
        nA, nB = self.nA, self.nB
        if i <= nA:
            return G[i, 0]
        if i <= nA + nB:
            return G[nA, i - nA]
        return G[2 * nA + nB - i, nB]

    def midline(self):
        ids = set(self.T[0, :].tolist()) | set(self.B[0, :].tolist()) | set(self.R[:, 0].tolist()) | \
            set(self.R[:, -1].tolist())
        return np.array(sorted(ids), int)

    def put(self, v, p, tag, fix=True, kind=0):
        self.P[v] = p
        self.fixed[v] = fix
        self.kind[v] = kind
        self.src[int(v)] = tag

    def crease(self, ids, s, closed=False):
        """a crease along the vertex chain ids (sharpness s: a number or one per edge)"""
        ids = list(ids)
        pairs = list(zip(ids[:-1], ids[1:])) + ([(ids[-1], ids[0])] if closed else [])
        ss = np.broadcast_to(np.asarray(s, np.float64), (len(pairs),))
        for (a, b), v in zip(pairs, ss):
            if v > 0:
                self.sharp_h[(min(a, b), max(a, b))] = float(v)

    def neighbours(self):
        nb = [set() for _ in range(self.n_half)]
        for q in self.Qh:
            for k in range(4):
                a, b = q[k], q[(k + 1) % 4]
                nb[a].add(b)
                nb[b].add(a)
        return [np.array(sorted(s), int) for s in nb]

    def full(self, P_half):
        """the full mesh (the half and its mirror x -> -x, welded on the midline): QuadMesh, the half -> mirror id map, the
        full sharpness dict"""
        mid = self.midline()
        is_mid = np.zeros(self.n_half, bool)
        is_mid[mid] = True
        mir = np.arange(self.n_half)
        off = np.cumsum(~is_mid) - 1 + self.n_half
        mir = np.where(is_mid, mir, off)
        n = self.n_half + int((~is_mid).sum())
        V = np.zeros((n, 3))
        V[:self.n_half] = P_half
        V[mid, 0] = 0.0
        Pm = P_half.copy()
        Pm[:, 0] *= -1.0
        V[mir[~is_mid]] = Pm[~is_mid]
        Q = np.vstack([self.Qh, mir[self.Qh][:, ::-1]])
        sharp = {}
        for (a, b), s in self.sharp_h.items():
            sharp[(min(a, b), max(a, b))] = s
            sharp[(min(mir[a], mir[b]), max(mir[a], mir[b]))] = s
        return QuadMesh(V, Q), mir, sharp


def rim_curve(C):
    """R1 along the half ring: (M, 3) (x, h, z); b3h: the back segment the crest then the domes' ridge (RIDGE_B)"""
    L = LAYOUT
    nA, nB, M = C.nA, C.nB, C.M
    R = np.array([r[:3] for r in RIM], np.float64)
    out = np.zeros((M, 3))
    # the front: x at LAYOUT front_x, then even to the corner; z, h along the front margin's rows (x 0 .. 7.40)
    fx = np.array(L['front_x'], np.float64)
    cx, cz = L['corner_front']
    fx = np.concatenate([fx, np.linspace(fx[-1], cx, nA - len(fx) + 2)[1:]])
    out[:nA + 1] = np.column_stack([fx, np.interp(fx, R[:8, 0], R[:8, 2]), np.interp(fx, R[:8, 0], R[:8, 1])])
    out[nA, 2] = cz
    # the side: z at LAYOUT side_z; x, h on the rim's side rows from the front corner to the back corner
    sz = np.array(L['side_z'], np.float64)
    bxc, bzc = L['corner_back']
    zz = np.concatenate([[cz], R[7:22, 1], [bzc]])
    xx = np.concatenate([[cx], R[7:22, 0], [bxc]])
    hh = np.concatenate([[out[nA, 1]], R[7:22, 2], [14.77]])
    out[nA:nA + nB + 1] = np.column_stack([pchip(zz, xx)(sz), pchip(zz, hh)(sz), sz])
    # the back (b3h): x at LAYOUT back_x (the back corner to the midline), z and h along RIDGE_B (the crest to its medial end,
    # then the domes' ridge: knob A, the notch, the top B, down into the groove)
    bx = np.array(L['back_x'], np.float64)
    assert len(bx) == nA + 1 and abs(bx[0] - bxc) < 1e-9 and bx[-1] == 0.0
    bz, bh = ridge_at(bx)
    out[nA + nB:] = np.column_stack([bx, bh, bz])
    return out


def build_cage(spec, mass, log=print, mass_face=None):
    """the head cage's TARGETS (the limit surface passes through them) and creases (the module docstring)"""
    from . import insect as HD
    C = Cage()
    L = LAYOUT
    nA, nB, K, M = C.nA, C.nB, C.K, C.M
    iF, iS, iB = range(0, nA + 1), range(nA, nA + nB + 1), range(nA + nB, M)
    t0 = time.time()
    # ---- R1, the rim's crest; across the back (b3h) the crest's lateral part, then the domes' ridge (RIDGE_B)
    R1 = rim_curve(C)
    rb_x = np.array([r[0] for r in RIDGE_B])
    for i in range(M):
        if i <= nA:
            tag = 'R1 front margin: M1d plan line, M1l height'
        elif i <= nA + nB:
            tag = 'R1 anterior angle / lateral margin: M1d plan line, M1l height'
        else:
            tag = ('R1 crest: ' if R1[i, 0] >= SHARP['crest_end'] else 'R1 the domes\' ridge: ') + \
                RIDGE_B[int(np.argmin(np.abs(rb_x - R1[i, 0])))][3]
        C.put(C.R[1, i], R1[i], tag)
    C.loops['R1 rim crest / the domes ridge'] = C.R[1].tolist()
    # ---- R0, the dish's inner loop: inward of R1 by the inner wall's width, on the floor (never above R1 - min_drop)
    pl = R1[:, [0, 2]]
    tg = np.gradient(pl, axis=0)
    tg /= np.linalg.norm(tg, axis=1, keepdims=True)
    nin = np.column_stack([-tg[:, 1], tg[:, 0]])
    if nin[nA + nB // 2, 0] > 0:                                   # inward on the side is -x
        nin = -nin
    Rr = np.array([r[:2] for r in RIM])
    from scipy.spatial import cKDTree
    _, j_ = cKDTree(Rr).query(pl)
    W = np.array(RIM_W)[j_]
    back = np.arange(M) > nA + nB                                  # (b3h: the back segment's R0 and rows from dome_rows below)
    W = np.where(back, 0.45, W)
    # the ANTERIOR ANGLE a broad hump (M1l: the knob's profile rises over z -1.2 .. -3.5; M1d: a thick rounded lobe whose top
    # slopes into the dish): its inner wall wider and its foot higher there (c2's 0.85 mm wall at the floor stood a fin)
    ant = np.exp(-((R1[:, 2] + 2.05) / 0.75) ** 2) * (np.arange(M) > nA - 2) * (np.arange(M) < nA + nB)
    W = W + WALL['ant_w'] * ant
    P0 = pl + W[:, None] * nin
    # (the inward offset smoothed along the loop: past the lobe's plan radius at the knob it swallowtailed, c2's slit; within
    # each segment, the dish's corners held: smoothed across them the patch's corner quad flattened into a dimple, c3)
    hold = np.zeros(M, bool)
    hold[[0, nA, nA + nB, M - 1]] = True
    for _ in range(WALL['smooth']):
        sm_ = 0.5 * P0[1:-1] + 0.25 * (P0[:-2] + P0[2:])
        P0[1:-1] = np.where(hold[1:-1, None], P0[1:-1], sm_)
    P0[[0, -1], 0] = 0.0
    F_ = np.minimum(bowl(P0[:, 0], P0[:, 1]), R1[:, 1] - BOWL['min_drop'])
    h0 = F_ + (WALL['rise'] + WALL['ant_rise'] * ant) * (R1[:, 1] - F_)
    # (b3h) the BACK: R0 and the top patch's last three rows from dome_rows at R1's columns: over the domes the traced
    # SHOULDER (R0), FACE, FOOT and the floor ahead (PRE), in the crest's region its inner wall's foot (the offset above) and the
    # floor rows ahead of it
    T = C.T
    rows_back = {}
    for i in range(nA + nB + 1, M):
        a = 2 * nA + nB - i
        rr, wcr = dome_rows(R1[i, 0], R1[i, 2], R1[i, 1], float(P0[i, 1]))
        x_ = 0.0 if a == 0 else float(R1[i, 0])
        P0[i] = (x_, rr['shoulder'][0])
        h0[i] = rr['shoulder'][1]
        rows_back[a] = (x_, rr, wcr)
    for i in range(M):
        if i > nA + nB:
            tag = ('R0 the domes\' SHOULDER (DOME: M1d h02, the half way from the face\'s brightness to the top\'s)'
                   if rows_back[2 * nA + nB - i][2] < 0.5 else 'R0 the crest\'s inner wall foot [E] (FEAT rim)')
        else:
            tag = 'R0 dish inner loop: R1 less the wall [E], the floor [E]'
        C.put(C.R[0, i], (P0[i, 0], h0[i], P0[i, 1]), tag)
    C.loops['R0 dish inner loop / the domes shoulder'] = C.R[0].tolist()
    # ---- the dish (the top patch's interior). b3h: rows nB-1 (FACE), nB-2 (FOOT), nB-3 (PRE) fixed ON the traced lines (the
    # loops follow the domes' curved fronts), the floor's rows 1 .. nB-4 a Coons patch in plan between row 0 and row nB-3, h the
    # floor, relaxed
    nR = 3
    for a in range(0, nA):
        x_, rr, wcr = rows_back[a]
        for k_, key in enumerate(('face', 'foot', 'pre')):
            z_, h_ = rr[key]
            src = {'face': 'the domes\' FACE (DOME: M1d h02, the darkest per column)',
                   'foot': 'the domes\' FOOT (DOME: M1d h02, the floor turning up)',
                   'pre': 'the floor ahead of the domes\' foot (DOME pre) [E]'}[key] if wcr < 0.5 else \
                'the floor ahead of the crest\'s inner wall [E] (DOME crest_rows)'
            C.put(T[a, nB - 1 - k_], (x_, h_, z_), src, fix=True, kind=0)
    bF = nB - nR                                                     # the floor sub-patch's back row
    for b in range(1, bF):
        z_ = C.P[T[0, 0], 2] + b / bF * (C.P[T[0, bF], 2] - C.P[T[0, 0], 2])
        C.put(T[0, b], (0.0, float(top_ref(0.0, z_)), z_), 'the dish floor [E] (FEAT bowl3)', fix=False, kind=1)
    c00, c10, c01, c11 = C.P[T[0, 0]], C.P[T[nA, 0]], C.P[T[0, bF]], C.P[T[nA, bF]]
    for a in range(1, nA):
        for b in range(1, bF):
            u, v = a / nA, b / bF
            p = (1 - v) * C.P[T[a, 0]] + v * C.P[T[a, bF]] + (1 - u) * C.P[T[0, b]] + u * C.P[T[nA, b]] - (
                (1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11)
            C.put(T[a, b], (p[0], float(top_ref(p[0], p[2])), p[2]), 'the dish floor [E] (FEAT bowl3)', fix=False, kind=1)
    # ---- R2, the outer faces' foot
    R2 = np.zeros((M, 3))
    src2 = [''] * M
    pr = np.array(PROCESS['plan'])
    pt = np.array(FACE['proc_top'])
    for i in iF:
        x_ = R1[i, 0]
        if x_ <= 2.45 + 1e-9:
            z_ = R1[i, 2] + 0.30
            R2[i] = (x_, float(np.interp(z_, pt[:, 0], pt[:, 1])) - 0.01, z_)
            src2[i] = 'R2 the clypeal process root: M1l (FEAT process top), 0.30 ahead of the crest [E]'
        else:
            R2[i] = (x_, R1[i, 1] - FACE['front_drop'], R1[i, 2] + FACE['front_run'])
            src2[i] = 'R2 the front margin outer face foot [E] (its 66-68 deg face, FEAT rim)'
    rg = np.array([r[:3] for r in RIDGE])
    for i in iS:
        z_ = R1[i, 2]
        R2[i] = (float(np.interp(z_, rg[::-1, 0], rg[::-1, 1])), float(np.interp(z_, rg[::-1, 0], rg[::-1, 2])), z_)
        src2[i] = 'R2 ' + RIDGE[int(np.argmin(np.abs(rg[:, 0] - z_)))][3]
    for i in iB:
        x_, h_, z_ = R1[i]
        # b3h: behind the domes' top M1l's back line (BACK2 dome_drop / dome_run), behind the knob and the crest the back
        # face's foot (FACE crest_drop / crest_run), eased between
        wb = float(smooth01((x_ - BACK2['x_blend'][0]) / (BACK2['x_blend'][1] - BACK2['x_blend'][0])))
        # (from the SMOOTHED dome height, the groove put back: the notch is the ridge's own; carried into R2 it corrugated the
        # domes' back, h03 _h8)
        gd_, gw_ = DOME['groove'][0], DOME['groove'][1]
        p_d = np.array([x_, dome_height(x_) - gd_ * np.exp(-(x_ / gw_) ** 2) - BACK2['dome_drop'], z_ - BACK2['dome_run']])
        p_c = np.array([x_ + 0.06, h_ - FACE['crest_drop'], z_ - FACE['crest_run']])
        R2[i] = wb * p_c + (1 - wb) * p_d
        src2[i] = 'R2 the crest\'s back face foot [E]' if wb > 0.5 else \
            'R2 the domes\' back: M1l\'s back line (16.01 at -8.65 -> 15.26 at -9.05, h04)'
    R2[M - 1, 0] = 0.0
    # (the back corner: the supraocular ridge rising into the crest's lateral end)
    R2[nA + nB] = 0.5 * (R2[nA + nB] + R2[nA + nB + 1]) + np.array([0.08, 0.0, 0.10])
    for i in range(M):
        C.put(C.R[2, i], R2[i], src2[i])
    C.loops['R2 outer face foot / supraocular ridge'] = C.R[2].tolist()
    log(f'[cage] R0-R2 and the dish placed in {time.time() - t0:.1f}s')
    # ---- the RINGS k 3 .. 13, one scheme round the whole half ring (c2: the front's own heights met the side's 1.1-2.3 mm
    # apart at the corners and twisted the quads there, a fold inside the head): per index the OUTWARD plan direction D (R2's
    # plan normal, smoothed) and an ANCHOR 2.5 mm inside R2; ring k a horizontal ray from the anchor along D at the SIDE's
    # height for it (LAYOUT side_h: the orbit block k 3 .. 11), the gena's two rings (k 12, 13) rays turned down 30 / 55 deg;
    # over the clypeal process the process's own rows (k 3 .. 7), over the lobes the lobes' rows (k 3 .. 6) and the buried
    # back's heights (k 7 .. 13), each blended into the common scheme beside it
    # (the rays leave a rounded-rectangle SPINE inside the head, SPINE x <= x_in, z_back <= z <= z_front: each ray from the
    # spine's nearest point to R2's plan point, so no two rays cross (c3: anchors 2.5 mm inside R2 crossed inside the head at
    # the front-left corner, where R2 turns sharply, and reversed the rings there: a fold))
    p2 = R2[:, [0, 2]]
    Anc = np.column_stack([np.minimum(p2[:, 0], SPINE['x_in']), np.clip(p2[:, 1], SPINE['z_back'], SPINE['z_front'])])
    D = p2 - Anc
    D[np.linalg.norm(D, axis=1) < 1e-9] = (0.0, 1.0)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    sh = list(L['side_h'])

    def on_face(i):
        """the face beside the clypeal process (the front segment past |x| 2.0, short of the corner)"""
        return i < nA - 1 and R1[i, 0] > 2.0

    def ray_h(i, h_, down=0.0):
        """ring point at index i: from the anchor at height h_ along D turned down by `down` degrees"""
        a_ = np.radians(down)
        d3 = np.array([D[i, 0] * np.cos(a_), -np.sin(a_), D[i, 1] * np.cos(a_)])
        mm = mass_face if (mass_face is not None and on_face(i)) else mass
        q = mm.ray(np.array([[Anc[i, 0], h_, Anc[i, 1]]]), d3[None])[0]
        if not np.isfinite(q[0]):
            q = mass.project(np.array([[p2[i, 0], h_, p2[i, 1]]]))[0]
        return q

    from . import insect_hull as IH
    dors = np.array([d_ for d_ in IH.DORSAL if d_[1] <= -4.4], np.float64)          # M1d's outline behind the eye (x, z)
    dors_x = lambda z: float(np.interp(z, dors[::-1, 1], dors[::-1, 0]))           # noqa: E731
    bh_ = np.array(BACK_H['h'])
    zo_ = pchip(pr[:, 0], pr[:, 1])
    for i in range(M):
        x_ = R1[i, 0]
        common = {}
        # (beside the clypeal process the face's rings k 3 .. 7 start at the process's own heights and descend to the side's
        # outward: c6's rings dropped 0.65 mm right at its side, an awning)
        w_ph = (1.0 - smooth01((x_ - 2.45) / 2.2)) if i <= nA else 0.0
        ph_ = (PROCESS['top'], PROCESS['top_front'], PROCESS['edge_lo'], PROCESS['under'], PROCESS['face'])
        # (b3h) the back segment's heights ease from the side's (at the back corner) to the back's (BACK_H): ONE scheme
        w_bk = float(smooth01((x_ - BACK_H['x_blend'][0]) / (BACK_H['x_blend'][1] - BACK_H['x_blend'][0]))) \
            if i > nA + nB else 1.0
        for k in range(3, 12):
            hh_ = sh[k - 3] if k > 3 else min(sh[0], R2[i, 1] - 0.40)
            if i > nA + nB and k >= 4:
                hh_ = w_bk * hh_ + (1.0 - w_bk) * bh_[k - 4]
            if k <= 7:
                hh_ = min(w_ph * ph_[k - 3] + (1.0 - w_ph) * hh_, R2[i, 1] - 0.22 - 0.30 * (k - 3))
            common[k] = ray_h(i, hh_)
        common[12] = common[11]                                    # (k 12, 13 set between R11 and R14 below)
        common[13] = common[11]
        tag = {k: 'the side / face (the mass, rays out at the side heights)' if k < 12 else
               'the gena / underside front (the mass, rays out and down)' for k in common}
        pos = dict(common)
        fixk = {k: False for k in common}
        if i > nA + nB:
            tag.update({k: 'the back (the mass, rays at heights easing from the side\'s to BACK_H)' for k in range(4, 12)})
            # R3 between R2 and R4, bulged outward by BACK_H bulge x their chord (in the column's (z, h) plane): the back's
            # profile convex, never crossing R2 or R4 (b3h-1 v1's ray left the mass ahead of R2 behind the crest, h07)
            ch_ = common[4] - R2[i]
            nz_ = np.array([0.0, -ch_[2], ch_[1]])
            nz_ /= max(np.linalg.norm(nz_), 1e-9)
            pos[3] = 0.5 * (R2[i] + common[4]) + BACK_H['bulge'] * np.linalg.norm(ch_) * nz_
            if i == M - 1:
                pos[3][0] = 0.0
            fixk[3] = True
            tag[3] = 'the back between R2 and R4, bulged (BACK_H bulge; M1l 14.41 / 14.16 at z -9.25 / -9.40)'
        if i <= nA and x_ <= PROCESS['blend'][0] + PROCESS['blend'][1]:
            # THE CLYPEAL PROCESS (b3h): ONE bilobed plate. Its rows lie between its root (R2: the front margin's outer face
            # foot) and M1d's outline in plan (PROCESS plan; rows (fraction, height)): the top, the rim's top, the rim, the
            # rim's underside, the underside (from the face under the plate toward the outline); every row level across the
            # plate (M1l), so the plate is one clean form; blended into the face beside it past the outline's end
            xo = min(x_, 2.45)
            w_in = 1.0 - smooth01((x_ - PROCESS['blend'][0]) / PROCESS['blend'][1])
            # the outline's point for this column BY ARC LENGTH (the front segment's x over 0 .. 2.45 mapped onto the outline's
            # length: b3h-1 v1 took the point at the column's own x, and the ears' lateral sides, which run back 1.15 mm over
            # 0.9 mm of x, got two columns: the rim waved between them, h08 _h5 proc_front)
            Op = proc_outline(xo / 2.45)
            root = np.array([R2[i, 0], R2[i, 2]])
            # the underside's root a fixed depth behind the outline (M1l: the underside 0.55-0.6 mm deep behind the rim, FEAT
            # clypeus_floor), not the mass's face (its condyle balls waved the underside's rows)
            # (the depth eased from under_depth to its half over the ears (t 0.35 .. 0.52, their tips at t 0.54): offset 0.6
            # inward from both sides of an ear 0.6-0.8 mm wide, the underside's roots crossed at the tips and drew the face's
            # columns into a slit, h08 _h7)
            t_ = xo / 2.45
            uroot = Op + PROCESS['under_depth'] * (1.0 - 0.5 * smooth01((t_ - 0.35) / 0.17)) * proc_normal(t_)
            for k, (t_, h_) in enumerate(PROCESS['rows'], start=3):
                base = root if k <= 5 else uroot
                p2_ = base + t_ * (Op - base)
                p = np.array([p2_[0], h_, p2_[1]])
                pos[k] = w_in * p + (1 - w_in) * common[k]
                fixk[k] = w_in > 0.3
                tag[k] = 'the clypeal process plate: M1d plan outline (PROCESS plan, h01_proc), M1l top / underside'
        for k in range(3, K):
            q = pos[k]
            if nA < i < nA + nB and R1[i, 2] <= -3.0 and k <= 5:
                # THE SIDE UNDER THE SUPRAOCULAR RIDGE. R3 stays r3_in inside the ridge (a shallow cove under its crisp edge:
                # M1l's thin highlight line); behind the eye (b3h, the lead's call 2) the side below runs OUTWARD to M1d's widest
                # outline: R4 / R5 at least DORSAL less r4_in / r5_in (b3g: R4 / R5 on the mass, 0.44 inside the ridge at z
                # -5.6: the side receded under it, a soft rolled shelf)
                e_ = float(smooth01((SIDE['z0'] - R1[i, 2]) / SIDE['ease'])) * \
                    (1.0 - float(smooth01((SIDE['z_end'][0] - R1[i, 2]) / (SIDE['z_end'][0] - SIDE['z_end'][1]))))
                if k == 3:
                    q = np.array([min(q[0], R2[i, 0] - SIDE['r3_in']), q[1], q[2]])
                    fixk[k] = True
                    tag[k] = 'just under the supraocular ridge: a shallow cove, SIDE r3_in inside it (M1l\'s thin highlight) [E]'
                elif e_ > 0:
                    xd = dors_x(R1[i, 2]) - (SIDE['r4_in'] if k == 4 else SIDE['r5_in'])
                    q = np.array([q[0] + e_ * max(xd - q[0], 0.0), q[1], q[2]])
                    fixk[k] = e_ > 0.5
                    tag[k] = f'the side under the ridge out to M1d\'s widest outline (insect_hull DORSAL less SIDE r{k}_in)'
            C.put(C.R[k, i], q, tag[k], fix=fixk[k], kind=2 if (on_face(i) and not fixk[k] and mass_face is not None) else 0)
    # (b3h) the back's R3 smoothed along the ring: its R4 rays read the mass's lumpy back (h03 _h8, the domes' back corrugated)
    ib_ = np.arange(nA + nB + 1, M)
    for _ in range(3):
        Pq_ = C.P[C.R[3, ib_]].copy()
        Pq_[1:-1] = 0.5 * Pq_[1:-1] + 0.25 * (Pq_[:-2] + Pq_[2:])
        Pq_[-1, 0] = 0.0
        C.P[C.R[3, ib_]] = Pq_
    log(f'[cage] the rings placed in {time.time() - t0:.1f}s')
    # ---- the UNDERSIDE: R14 the inward plan offset of R11 (UNDER in, smoothed along the ring; c3: rings turned down from the
    # front and the side crossed at the front-left corner, a fold), on the mass's underside (rays down from inside); R12 and
    # R13 between R11 and R14 (thirds, projected onto the mass), so the lower rings nest by construction; the bottom patch by a
    # Coons patch in plan, every point on the underside
    B = C.B
    p11 = np.array([C.P[C.R[11, i]][[0, 2]] for i in range(M)])
    # (along the front the rim stays in front of the mentum's front edge, M3v's z -1.3: c5's 1.6 put it at -1.4, behind the
    # suture's corners, a fold)
    w_fr = 1.0 - smooth01((np.arange(M) - (nA - 3)) / 4.0)
    p14 = p11 - (UNDER['in'] + (UNDER['in_front'] - UNDER['in']) * w_fr)[:, None] * D
    for _ in range(UNDER['smooth']):
        p14[1:-1] = 0.5 * p14[1:-1] + 0.25 * (p14[:-2] + p14[2:])
    p14[[0, -1], 0] = 0.0
    for i in range(M):
        qq = mass.ray(np.array([[p14[i, 0], 10.8, p14[i, 1]]]), np.array([[0.0, -1.0, 0.0]]))[0]
        if not np.isfinite(qq[0]):
            qq = mass.project(np.array([[p14[i, 0], 8.0, p14[i, 1]]]))[0]
        C.put(C.R[K, i], qq, 'the underside edge (mass: R11 offset in, rays down)', fix=False)
        a_, b_ = C.P[C.R[11, i]], qq
        for k, f_ in ((12, 1.0 / 3.0), (13, 2.0 / 3.0)):
            p = a_ + f_ * (b_ - a_)
            n_ = mass.grad(p[None])[0]
            q = mass.project(p[None])[0] if np.linalg.norm(n_) > 0 else p
            C.put(C.R[k, i], q, 'the gena / underside rim (the mass, between R11 and R14)', fix=False)
    for b in range(1, nB):
        p = C.P[B[0, 0]] + b / nB * (C.P[B[0, nB]] - C.P[B[0, 0]])
        q = mass.ray(np.array([[0.0, 10.8, p[2]]]), np.array([[0.0, -1.0, 0.0]]))[0]
        C.put(B[0, b], q if np.isfinite(q[0]) else p, 'the underside midline (mass)', fix=False)
    c00, c10, c01, c11 = C.P[B[0, 0]], C.P[B[nA, 0]], C.P[B[0, nB]], C.P[B[nA, nB]]
    for a in range(1, nA):
        for b in range(1, nB):
            u, v = a / nA, b / nB
            p = (1 - v) * C.P[B[a, 0]] + v * C.P[B[a, nB]] + (1 - u) * C.P[B[0, b]] + u * C.P[B[nA, b]] - (
                (1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11)
            q = mass.ray(np.array([[p[0], 10.8, p[2]]]), np.array([[0.0, -1.0, 0.0]]))[0]
            C.put(B[a, b], q if np.isfinite(q[0]) else p, 'the underside (mass, rays down)', fix=False)
    log(f'[cage] the underside placed in {time.time() - t0:.1f}s')
    # ---- the relaxation: the non-feature vertices evened along the mass (or the top, in plan), the features held
    relax(C, mass, mass_face=mass_face)
    # ---- the ORBIT: square rings in the side block (after the relaxation: the block's boundary on the relaxed side)
    orbit(C, spec, mass)
    # ---- the MENTUM's suture: a square ring in the bottom patch on M3v's trapezoid; then the rest relaxed round both.
    # (b3h-2) only when MENTUM cage: the suture is the high's micro relief (MENTUM's note); the rest relaxed round the orbit
    if MENTUM.get('cage', True):
        mentum(C, mass)
    relax(C, mass, iters=RELAX['iters'] // 2, mass_face=mass_face)
    dzs = rim_hold(C, mass) if MENTUM.get('cage', True) else np.zeros(1)
    log(f'[cage] relaxed, the orbit {"and the mentum " if MENTUM.get("cage", True) else ""}set in {time.time() - t0:.1f}s; '
        f'the underside rim held up to {dzs.max():.2f} mm in front of the mentum')
    creases(C, R1)
    return C


def relax(C, mass, iters=None, lam=None, mass_face=None):
    """Laplacian smoothing of the free vertices, each step reprojected: on the mass (kind 0) or, in plan, on the top (kind 1);
    the midline's x held at 0"""
    iters = RELAX['iters'] if iters is None else iters
    lam = RELAX['lam'] if lam is None else lam
    nb = C.neighbours()
    free = np.nonzero(~C.fixed)[0]
    mid = np.zeros(C.n_half, bool)
    mid[C.midline()] = True
    for _ in range(iters):
        avg = np.array([C.P[nb[v]].mean(0) for v in free])
        P = C.P[free] + lam * (avg - C.P[free])
        P[mid[free], 0] = 0.0
        on_top = C.kind[free] == 1
        on_fc = (C.kind[free] == 2) if mass_face is not None else np.zeros(len(free), bool)
        if on_top.any():
            P[on_top, 1] = top_ref(P[on_top, 0], P[on_top, 2])
        for sel, mm in ((~on_top & ~on_fc, mass), (on_fc, mass_face)):
            if sel.any():
                Q = mm.project(P[sel])
                Q[mid[free][sel], 0] = 0.0
                P[sel] = Q
        C.P[free] = P


def orbit(C, spec, mass):
    """the ORBIT block (LAYOUT orbit_i x orbit_k): square ring j = 0 the block's boundary (kept on the side), j = 1 the collar's
    crest (its front the canthus), j = 2 the rim ON the eye's sphere along M1l's exposed outline, j = 3 the socket, j = 4 its
    floor; the rim and the collar creased"""
    from . import insect as HD
    ey, lm = spec['eye'], spec['landmarks']
    Re = ey['radius']
    a = np.array([np.sin(np.radians(ey['splay'])), 0.0, np.cos(np.radians(ey['splay']))])   # (x, ., z)
    apex = np.array([HD.EYE_APEX[0], lm['eye_c'][1], HD.EYE_APEX[1]])                      # (x, h, z)
    Cx = apex - Re * np.array([a[0], 0.0, a[2]])
    zc, hc = lm['eye_c']
    ha, hb = 0.5 * ey['along'], 0.5 * ey['across']
    (i0, i1), (k0, k1) = LAYOUT['orbit_i'], LAYOUT['orbit_k']
    ic, kc = 0.5 * (i0 + i1), 0.5 * (k0 + k1)
    ob = ORBIT

    def dome_x(z_, h_):
        """the eye sphere's lateral surface x at (z, h) (-inf off its disc)"""
        r2 = Re ** 2 - (z_ - Cx[2]) ** 2 - (h_ - Cx[1]) ** 2
        return Cx[0] + np.sqrt(r2) if r2 > 0 else -np.inf

    def ang(i, k, j):
        # the side segment: i grows backward (-z), k downward (-h); the square ring's vertex mapped to the ellipse's angle
        u = (ic - i) / max(0.5 * (i1 - i0) - j, 1)                  # + forward
        v = (kc - k) / max(0.5 * (k1 - k0) - j, 1)                  # + up
        return np.arctan2(v, u)

    def rim_pt(t):
        """the rim's point at the ellipse angle t: ON the eye's sphere along M1l's outline (clipped inside its disc)"""
        dz, dh = zc + ha * np.cos(t) - Cx[2], hc + hb * np.sin(t) - Cx[1]
        kk = min(1.0, ob['rim_clip'] * Re / max(np.hypot(dz, dh), 1e-9))
        dz, dh = dz * kk, dh * kk
        return np.array([Cx[0] + np.sqrt(max(Re ** 2 - dz ** 2 - dh ** 2, 0.0)), Cx[1] + dh, Cx[2] + dz])

    rims, collars = [], []
    for j in range(1, 5):
        ring = square_ring(i0 + j, i1 - j, k0 + j, k1 - j)
        if j == 4:
            ring = [(int(round(ic)), int(round(kc)))]
        ids = []
        for (i, k) in ring:
            v = C.R[k, i]
            if j == 4:
                p = Cx + (Re - ob['floor']) * np.array([a[0], 0.0, a[2]])
                C.put(v, p, 'the orbit socket floor [E] (under the dome)')
                continue
            t = ang(i, k, j)
            if j == 2:
                C.put(v, rim_pt(t), "the orbit RIM on the eye's sphere (M1l's exposed outline, SPEC eye)")
            elif j == 1:
                z_ = zc + (ha + ob['collar_out']) * np.cos(t)
                h_ = hc + (hb + ob['collar_out']) * np.sin(t)
                q = mass.ray(np.array([[2.0, h_, z_]]), np.array([[1.0, 0.0, 0.0]]))[0]
                xs = q[0] if np.isfinite(q[0]) else 7.9
                # (the collar WRAPS the dome outside M1l's outline: over the eye's sphere wherever the dome stands proud of the
                # side, b03 _b3gq1: on the side alone the dome lay bare in front of and under the outline, the exposed patch
                # 2.275 x 2.441 against M1l's 1.948 x 2.365). b3h: a RAISED rounded lip all round, level with the rim it
                # surrounds (the dome at the rim's point of the same angle) + lip, never under the dome at its own point + lip
                # or the side + collar (b3g's side + 0.04 / dome + 0.15 sank under the dome's edge at the lower rear: the
                # V-notch, the B3g check c09; M1l h01_eye: a dark rounded collar round the whole eye)
                x_ = max(xs + ob['collar'], rim_pt(t)[0] + ob['lip'], dome_x(z_, h_) + ob['lip'])
                # the CANTHUS: the collar's front stands out toward M1d's canthus edge over the eye's front, within M1l's
                # canthus heights (10.85-12.95)
                wc = smooth01((np.cos(t) - 0.30) / 0.45) * smooth01((h_ - ob['canthus_h'][0]) / 0.45) * \
                    smooth01((ob['canthus_h'][1] - h_) / 0.45)
                x_ = x_ + wc * max(ob['canthus_x'] - x_, 0.0)
                C.put(v, (x_, h_, z_), 'the orbit collar crest [E]; its front the canthus (M1d edge 8.29-8.60)')
            else:
                dz = zc + ha * 0.62 * np.cos(t) - Cx[2]
                dh = hc + hb * 0.62 * np.sin(t) - Cx[1]
                d3 = np.array([np.sqrt(max(Re ** 2 - dz * dz - dh * dh, 0.05)), dh, dz])
                d3 /= np.linalg.norm(d3)
                C.put(v, Cx + (Re - ob['socket']) * d3, 'the orbit socket wall [E] (under the dome)')
            ids.append(v)
        if j == 2:
            rims = ids
        if j == 1:
            collars = ids
    # the block's boundary held where the relaxation left it, but over the dome wherever the dome reaches it (wrapped)
    for (i, k) in square_ring(i0, i1, k0, k1):
        v = C.R[k, i]
        p = C.P[v]
        C.P[v, 0] = max(p[0], dome_x(p[2], p[1]) + ob['wrap'] + 0.03)
        C.fixed[v] = True
    # (10-29, B6) the CHEEK under the eye: the block's bottom row (k1) within ORBIT cheek (mm, in x) of the collar's crest
    # above it (row k1 - 1), so the side turns in under the collar over two rows of the low, not one. The collar stood
    # 1.2-1.7 mm proud of the side below it (x 7.8-8.1 against 6.4-6.5 one ring down, 0.3-0.5 mm lower): the limit hooked
    # under it, the low's quad across the hook reversed (the B5 check's reversed texels under the eye, its 'thin crack';
    # at the canthus, z -3.35, a knife flange). 0: as before
    # (the push eased toward the block's front and back columns, ORBIT cheek_taper per column from the end: pushed in full
    # at the corner its neighbours outside the block stayed on the side and the corner folded)
    if ob.get('cheek', 0.0) > 0.0:
        tp = ob.get('cheek_taper', (0.0, 0.5))
        for i in range(i0, i1 + 1):
            ic_ = min(max(i, i0 + 1), i1 - 1)
            e_ = min(i - i0, i1 - i)
            w_ = tp[e_] if e_ < len(tp) else 1.0
            v = C.R[k1, i]
            C.P[v, 0] = C.P[v, 0] + w_ * max(C.P[C.R[k1 - 1, ic_], 0] - ob['cheek'] - C.P[v, 0], 0.0)
    C.loops['ORBIT rim'] = rims
    C.loops['ORBIT collar'] = collars


def square_ring(i0, i1, k0, k1):
    """the (i, k) cells round a square ring, in order"""
    out = [(i, k0) for i in range(i0, i1)] + [(i1, k) for k in range(k0, k1)] + \
          [(i, k1) for i in range(i1, i0, -1)] + [(i0, k) for k in range(k1, k0, -1)]
    return out


def mentum(C, mass):
    """the mentum's SUTURE: the bottom patch's block a <= mentum_a, b in mentum_b: its boundary on M3v's trapezoid (smoothed),
    a shallow groove (`suture` up into the head), the plate inside bulging `bulge`"""
    a1 = LAYOUT['mentum_a']
    b0, b1 = LAYOUT['mentum_b']
    tr = np.array(MENTUM['trap'])
    # the half outline: the front edge (x 0 -> 3.9 at z -1.3), the side (3.9, -1.3) -> (4.1, -2.2) -> (2.5, -3.7), the rear
    # edge (2.5 -> 0 at -3.7)
    B = C.B
    ring = [(a, b0) for a in range(0, a1)] + [(a1, b) for b in range(b0, b1)] + [(a, b1) for a in range(a1, -1, -1)]
    nf, ns, nr = a1, b1 - b0, a1 + 1
    front = np.column_stack([np.linspace(0.0, tr[0, 0], nf + 1)[:-1], np.full(nf, tr[0, 1])])
    sd = np.array([tr[0], tr[1], tr[2]])
    s_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(sd, axis=0), axis=1))])
    ts = np.linspace(0.0, s_[-1], ns + 1)[:-1]
    side = np.column_stack([np.interp(ts, s_, sd[:, 0]), np.interp(ts, s_, sd[:, 1])])
    rear = np.column_stack([np.linspace(tr[2, 0], 0.0, nr), np.full(nr, tr[2, 1])])
    pts = np.vstack([front, side, rear])
    ids = []
    for (a, b), (x_, z_) in zip(ring, pts):
        v = B[a, b]
        q = mass.ray(np.array([[x_, 10.8, z_]]), np.array([[0.0, -1.0, 0.0]]))[0]
        q = q if np.isfinite(q[0]) else np.array([x_, 8.2, z_])
        C.put(v, (x_, q[1] + MENTUM['suture'], z_), "the mentum's suture: M3v's trapezoid (STROKES mentum trap)")
        ids.append(v)
    # the plate inside: the block's interior re-gridded inside the trapezoid, bulging
    for a in range(0, a1):
        for b in range(b0 + 1, b1):
            fa, fb = a / a1, (b - b0) / (b1 - b0)
            xl = np.interp(fb, [0.0, 0.36, 1.0], [tr[0, 0], tr[1, 0], tr[2, 0]])
            x_ = fa * xl
            z_ = tr[0, 1] + fb * (tr[2, 1] - tr[0, 1])
            q = mass.ray(np.array([[x_, 10.8, z_]]), np.array([[0.0, -1.0, 0.0]]))[0]
            q = q if np.isfinite(q[0]) else np.array([x_, 8.2, z_])
            C.put(B[a, b], (x_, q[1] - MENTUM['bulge'], z_), 'the mentum plate (M3v), bulging [E]')
    C.loops['MENTUM suture'] = ids


def rim_hold(C, mass):
    """(b3h) the underside's rim (R14 = the bottom patch's row 0) in front of the mentum suture's front edge. The relaxed rim
    sagged to z -1.36 .. -1.51 at x 3.4-4.0, behind the edge's z -1.30, and the quads between (row 0 / row 1, a 11-13)
    turned over in plan: slivers at the suture's front corners (b3g's too), which the 0.025 mm exact field reads as enclosed
    voids (h13: 32 of 1-2 cells). After the last relaxation, each rim point within `mentum_reach` of the corner (in x) moved
    forward to `mentum_gap` in front of the edge, the move tapered over three neighbours each side (no kink), x unchanged,
    re-rayed onto the mass; R12 / R13 moved with it by a third / two thirds (projected). (A hold before or between the
    relaxations kept the offset ring's spacing, bunched the rim and dragged its free points back: creases in the terrace
    map, a kink at the midline.)"""
    B, nA = C.B, C.nA
    tr = np.array(MENTUM['trap'])
    zf = tr[0, 1] + UNDER['mentum_gap']
    need = np.array([max(0.0, zf - C.P[B[a, 0]][2]) if C.P[B[a, 0]][0] <= tr[0, 0] + UNDER['mentum_reach'] else 0.0
                     for a in range(nA + 1)])
    taper = UNDER['mentum_taper']
    nt = len(taper) - 1
    dzs = np.array([max(need[j] * taper[abs(a - j)] for j in range(max(0, a - nt), min(nA, a + nt) + 1))
                    for a in range(nA + 1)])
    for a in np.nonzero(dzs > 1e-6)[0]:
        p0 = C.P[B[a, 0]].copy()
        q = mass.ray(np.array([[p0[0], 10.8, p0[2] + dzs[a]]]), np.array([[0.0, -1.0, 0.0]]))[0]
        q = q if np.isfinite(q[0]) else p0 + np.array([0.0, 0.0, dzs[a]])
        C.put(B[a, 0], q, f"the underside's rim, {dzs[a]:.2f} forward: in front of the mentum's front edge", fix=True)
        for k, f_ in zip((12, 13), UNDER['mentum_band']):
            v = C.R[k, a]
            C.put(v, mass.project((C.P[v] + f_ * (q - p0))[None])[0], 'the gena / underside rim (eased with the rim)',
                  fix=False)
    return dzs


def creases(C, R1):
    """the semi-sharp creases (SHARP): R1's runs (b3h: the crest's crease ends at its medial end; the domes' ridge is smooth),
    the supraocular ridge on R2, the orbit's rim and collar, the mentum's suture, the clypeal process's rim (b3h: no groove
    crease)"""
    nA, nB, M = C.nA, C.nB, C.M
    sp = SHARP
    s1 = np.zeros(M - 1)
    for i in range(M - 1):
        xm = 0.5 * (R1[i, 0] + R1[i + 1, 0])
        zm = 0.5 * (R1[i, 2] + R1[i + 1, 2])
        if i < nA:
            s1[i] = sp['front']
        elif i < nA + nB:
            s1[i] = sp['angle'] if zm > -3.25 else sp['lateral']
        else:
            # the crest, easing to 0 at its medial end (crest_end) over crest_taper mm: the domes' ridge is smooth
            s1[i] = sp['crest'] * smooth01((xm - sp['crest_end']) / sp['crest_taper'])
    C.crease(C.R[1], s1)
    # the supraocular ridge: R2 from z -3.25 back (b3h: ridge_aft behind z -5.8), on through the back corner into the crest's
    # back face, fading
    s2 = np.zeros(M - 1)
    for i in range(nA, M - 1):
        zm = 0.5 * (C.P[C.R[2, i], 2] + C.P[C.R[2, i + 1], 2])
        xm = 0.5 * (C.P[C.R[2, i], 0] + C.P[C.R[2, i + 1], 0])
        if i < nA + nB:
            s_ = sp['ridge'] + (sp['ridge_aft'] - sp['ridge']) * smooth01((-5.6 - zm) / 0.4)
            s2[i] = s_ * smooth01((-3.10 - zm) / 0.35)
        else:
            # (b3h: the ridge's crease ends at the back corner, the crest's back face beside it uncreased: b3g's 1.6 faded over x
            # 6.5 .. 5.6 swept a creased line round the posterior corner; M1d: the surface falls away there)
            s2[i] = sp['ridge_back'] * smooth01((xm - 6.45) / 0.5)
    C.crease(C.R[2], s2)
    C.crease(C.loops['ORBIT rim'], sp['orbit'], closed=True)
    C.crease(C.loops['ORBIT collar'], sp['collar'], closed=True)
    if 'MENTUM suture' in C.loops:                      # (b3h-2: only when the cage builds it, MENTUM cage)
        C.crease(C.loops['MENTUM suture'], sp['mentum'])
    if sp['proc_edge'] > 0:
        # the clypeal process's rim (its top edge, R4) across the plate, easing out past the outline's end
        xs4 = [C.P[C.R[4, i], 0] for i in range(0, nA)]
        sp4 = [sp['proc_edge'] * (1.0 - smooth01((0.5 * (xs4[i] + xs4[i + 1]) - 2.30) / 0.5)) for i in range(nA - 1)]
        C.crease([C.R[4, i] for i in range(0, nA)], sp4)


# ============================================================================================ fit, limit, distance
def limit_surface(C, levels=None, log=print):
    """the full cage (targets mirrored), the control points fitted so the limit surface passes through the targets, the
    subdivided limit mesh. Returns (cage QuadMesh with controls, sharp dict, limit QuadMesh, fit residual)"""
    levels = LEVELS if levels is None else levels
    t0 = time.time()
    tgt, mir, sharp = C.full(C.P)
    V0, res = SS.fit_controls(tgt, sharp, tgt.V, levels['fit'])
    cage = QuadMesh(V0, tgt.Q)
    lim, s_e, par, _ = SS.subdivide(cage, sharp, levels['out'])
    log(f'[cage] {len(cage.V)} cage vertices, {len(cage.Q)} quads, {len(sharp)} crease edges; controls fitted (residual '
        f'{res:.1e} mm) and subdivided {levels["out"]} levels to {len(lim.Q):,} quads in {time.time() - t0:.1f}s')
    return cage, sharp, lim, res, tgt


def mesh_sdf(V, F, lo, h, n, log=print, band=None):
    """the signed distance (mm) of the closed triangle mesh (V (x, h, z) mm, F) on the grid lo + h (i, j, k): the exact
    distance to the nearest triangle (Warp's BVH), the sign by the winding number. band (mm, optional): exact only where a
    4x coarser pass (trilinear) puts the surface within band (+ the coarse cells' reach); elsewhere +-band with the coarse
    sign (for a thin part in a large box, whose field is clamped at band anyway)"""
    import warp as wp
    kk = _kernels()
    dev = wp.get_preferred_device()
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev), support_winding_number=True)
    t0 = time.time()

    def full(lo_, h_, n_):
        N_ = int(np.prod(n_))
        o_ = wp.zeros(N_, dtype=wp.float32, device=dev)
        wp.launch(kk['sdf'], dim=N_, inputs=[m.id, wp.vec3(*np.asarray(lo_, np.float32)), float(h_), int(n_[1]), int(n_[2]),
                                             50.0, o_], device=dev)
        return o_.numpy().reshape(n_)
    if band is None:
        d = full(lo, h, n)
        log(f'[cage] distance on {tuple(n)} ({int(np.prod(n)):,} points) on {dev} in {time.time() - t0:.1f}s')
        return d
    from scipy import ndimage as nd
    nc = tuple(int(np.ceil((n[a] - 1) / 4)) + 1 for a in range(3))
    dc = full(lo, 4.0 * h, nc)
    I = np.stack(np.meshgrid(*[np.arange(n[a]) / 4.0 for a in range(3)], indexing='ij'), 0)
    du = nd.map_coordinates(dc, I.reshape(3, -1), order=1, mode='nearest').reshape(n)
    near = np.abs(du) < band + 4.0 * h * np.sqrt(3.0)
    idx = np.argwhere(near)
    P = (np.asarray(lo, np.float64)[None, :] + idx * h).astype(np.float32)
    o_ = wp.zeros(len(P), dtype=wp.float32, device=dev)
    wp.launch(kk['sdf_pts'], dim=len(P), inputs=[m.id, wp.array(P, dtype=wp.vec3, device=dev), 50.0, o_], device=dev)
    d = np.where(du < 0, -band, band).astype(np.float32)
    d[near] = o_.numpy()
    log(f'[cage] distance on {tuple(n)} ({int(np.prod(n)):,} points; {len(P):,} exact in the {band} mm band, a coarse '
        f'{nc} pass) on {dev} in {time.time() - t0:.1f}s')
    return d


def head_field(V, F, lo, h, n, log=print):
    """b3h THE HEAD'S FIELD (HEAD_FIELD; the lead's call 3): the exact signed distance to the limit mesh on the lattice lo + h (i,
    j, k) within `near` of the surface (the shipped edges are the limit surface's: blurred everywhere, b3g's 0.03 mm rounded the
    front margin and the supraocular ridge 0.02-0.05 mm past the limit's, h05), eased from `near` to `far` into the coarse pass
    (the exact distance on `coarse` x h, trilinear) blurred `s_far` (the deep field's medial-axis creases, which the GRID's
    divisor bound would otherwise read); clamped to CLAMP. n - 1 a multiple of `coarse` on each axis"""
    import warp as wp
    from scipy import ndimage as nd
    hf = HEAD_FIELD
    c = hf['coarse']
    kk = _kernels()
    dev = wp.get_preferred_device()
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev), support_winding_number=True)
    t0 = time.time()
    nc = tuple((n[a] - 1) // c + 1 for a in range(3))
    assert all((nc[a] - 1) * c + 1 == n[a] for a in range(3))
    o_ = wp.zeros(int(np.prod(nc)), dtype=wp.float32, device=dev)
    wp.launch(kk['sdf'], dim=int(np.prod(nc)), inputs=[m.id, wp.vec3(*np.asarray(lo, np.float32)), float(c * h), int(nc[1]),
                                                     int(nc[2]), 50.0, o_], device=dev)
    dc = np.clip(o_.numpy().reshape(nc), CLAMP[0], CLAMP[1]).astype(np.float32)
    d = nd.zoom(dc, [n[a] / nc[a] for a in range(3)], order=1, grid_mode=False, mode='nearest').astype(np.float32)
    assert d.shape == tuple(n)
    reach = hf['far'] + c * h * np.sqrt(3.0)
    near = np.abs(d) < reach
    if hf['s_far'] > 0:
        d = nd.gaussian_filter(d, hf['s_far'] / h, mode='nearest')
    idx = np.argwhere(near)
    P = (np.asarray(lo, np.float64)[None, :] + idx * h).astype(np.float32)
    del idx
    o2 = wp.zeros(len(P), dtype=wp.float32, device=dev)
    wp.launch(kk['sdf_pts'], dim=len(P), inputs=[m.id, wp.array(P, dtype=wp.vec3, device=dev), 50.0, o2], device=dev)
    dn = np.clip(o2.numpy(), CLAMP[0], CLAMP[1])
    del P
    w = smooth01((hf['far'] - np.abs(dn)) / (hf['far'] - hf['near'])).astype(np.float32)
    d[near] = w * dn + (1.0 - w) * d[near]
    if hf['s_near'] > 0:
        d = nd.gaussian_filter(d, hf['s_near'] / h, mode='nearest')
    nfill = 0
    if hf.get('fill'):
        lab, nl = nd.label(d > 0)
        edge = np.unique(np.concatenate([lab[[0, -1]].ravel(), lab[:, [0, -1]].ravel(), lab[:, :, [0, -1]].ravel()]))
        enc = np.setdiff1d(np.arange(1, nl + 1), edge)
        if len(enc):
            m_ = np.isin(lab, enc)
            nfill = int(m_.sum())
            d[m_] = -0.5 * h
        del lab
    log(f'[cage] the head field on {tuple(n)} ({int(np.prod(n)):,} points at {h} mm): exact at {int(near.sum()):,} within '
        f'{reach:.3f} mm of the surface (eased {hf["near"]} -> {hf["far"]}), the {nc} coarse pass blurred {hf["s_far"]} '
        f'beyond; enclosed voids filled: {nfill} cells; on {dev} in {time.time() - t0:.1f}s')
    return d.astype(np.float32)


_K = {}


def _kernels():
    if _K:
        return _K
    import warp as wp

    @wp.kernel
    def k_sdf(mesh: wp.uint64, lo: wp.vec3, h: float, ny: int, nz: int, maxd: float, out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        i = tid // (ny * nz)
        r = tid - i * ny * nz
        j = r // nz
        k = r - j * nz
        p = lo + wp.vec3(float(i) * h, float(j) * h, float(k) * h)
        q = wp.mesh_query_point_sign_winding_number(mesh, p, maxd, 2.0, 0.5)
        if q.result:
            c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[tid] = wp.length(p - c) * q.sign
        else:
            out[tid] = maxd

    @wp.kernel
    def k_sdf_pts(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        p = pts[tid]
        q = wp.mesh_query_point_sign_winding_number(mesh, p, maxd, 2.0, 0.5)
        if q.result:
            c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[tid] = wp.length(p - c) * q.sign
        else:
            out[tid] = maxd
    _K['sdf'] = k_sdf
    _K['sdf_pts'] = k_sdf_pts
    return _K


def head_key(spec):
    from . import insect_hull as IH
    tabs = dict(v=VERSION, layout=LAYOUT, rim=RIM, rim_w=RIM_W, face=FACE, ridge=RIDGE, orbit=ORBIT,
                process=PROCESS, dome=DOME, ridge_b=RIDGE_B, back2=BACK2, back_h=BACK_H, side=SIDE, bowl=BOWL,
                mentum=MENTUM, sharp=SHARP, levels=LEVELS, relax=RELAX, grid=(HEAD_FIELD, CLAMP), wall=WALL, under=UNDER,
                spine=SPINE, mass_smooth=MASS_SMOOTH,
                eye=spec['eye'],
                lm=spec['landmarks'], mass=dict(dorsal=IH.DORSAL, lateral=IH.LATERAL, sec_wide=IH.SEC_WIDE, sec=IH.SEC,
                                                build={k: IH.BUILD[k] for k in IH.MASS_KEYS}))
    return cache_key(tabs)


def head_volume(spec, log=print):
    """THE HEAD GRID from the creased subdivision surface (insect_hull.head_volume's return: values (nx, ny, nz) mm on
    insect_hull's FEAT grid box, lo, h, divisor, errors, curves), cached by every input"""
    from . import insect_hull as IH
    from scipy import ndimage as nd
    key = head_key(spec)
    path = os.path.join(CACHE, f'beetle_subd_head_{key}.npz')
    if not os.path.exists(path):
        t0 = time.time()
        mass = Mass(spec, log, MASS_SMOOTH['general'])
        C = build_cage(spec, mass, log, mass_face=Mass(spec, log, MASS_SMOOTH['face']))
        cage, sharp, lim, res, tgt = limit_surface(C, log=log)
        V = lim.V
        F = lim.tris()
        # the grid (b3h, HEAD_FIELD): the limit mesh's box + pad at h, symmetric about the midline, its sizes a whole number of
        # coarse cells; the field exact near the surface, the coarse pass blurred far from it (head_field)
        hf = HEAD_FIELD
        h_ = hf['h']
        c_ = hf['coarse']
        xm_ = np.ceil((np.abs(V[:, 0]).max() + hf['pad']) / h_) * h_
        lo = np.array([-xm_, np.floor((V[:, 1].min() - hf['pad']) / h_) * h_, np.floor((V[:, 2].min() - hf['pad']) / h_) * h_])
        hi = np.array([xm_, V[:, 1].max() + hf['pad'], V[:, 2].max() + hf['pad']])
        n = tuple(int(c_ * np.ceil((hi[a] - lo[a]) / (c_ * h_) - 1e-9)) + 1 for a in range(3))
        d = head_field(V, F, lo, h_, n, log)
        out = dict(values=d, lo=lo, h=np.float64(h_), cage_V=cage.V, cage_Q=cage.Q, targets=tgt.V,
                   sharp_pairs=np.array([k for k, _ in sharp.items()], np.int64).reshape(-1, 2),
                   sharp_vals=np.array([v for _, v in sharp.items()], np.float64), fit_res=np.float64(res))
        for nm_, ids in C.loops.items():
            out['loop_' + nm_.replace(' ', '_').replace('/', '-')] = tgt.V[np.asarray(ids, int)]
        os.makedirs(CACHE, exist_ok=True)
        np.savez_compressed(path, **out)
        log(f'[cage] built the subdivision head in {time.time() - t0:.0f}s -> {os.path.relpath(path, REPO)}')
    Z = np.load(path, allow_pickle=False)
    V = Z['values']
    M = IH.head_mass(spec, log)
    errs = {k[4:]: M[k] for k in M if k.startswith('err_')}
    curves = {k[5:]: Z[k] for k in Z.files if k.startswith('loop_')}
    return dict(values=V, lo=Z['lo'], h=float(Z['h']), divisor=IH.grid_divisor(V, float(Z['h'])), errors=errs,
                curves=curves, key=key, path=path)
