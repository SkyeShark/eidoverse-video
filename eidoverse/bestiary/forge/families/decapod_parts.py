"""DECAPOD CLAY (X2; work/bestiary/research/LOBSTER_PLAN.md §5.2, gates §12 X2): the European lobster as one closed
shell per part, each its OWN sdf.Program (never welded: overlapping shells in one field would fuse), built at the
author scale (x4) from the SPEC (species/lobster.py, life mm), the rest chain (families/decapod.py, X1's bind) and M1's
traced outlines (research/lobster_work/x2/data/src_c11_outline_x2.json, read by work/bestiary/tests/x02_clay.py and
passed in as an Outline). FORMS ONLY (plan §5.2): no teeth, tubercles, beads, grooves or creases; the cages (X4) and
the sculpt (X6) carry those.

PARTS, each named for its rig joint (decapod.skeleton's names), its region one of species/lobster.REGIONS. Left (+x)
and midline parts are built; every right part is its left part's MIRROR (p_R = M p_L: Part.mirror, its field
f_R(p) = f_L(M p)), EXCEPT the chelae, sided by TYPE: the right propodus and dactyl are the CUTTER's, built on the left
and mirrored, as decapod.skeleton sides them.
  body           carapace (with the rostrum's blade, one shell), ventral_thorax
  head           eyestalk_0 / _1, cornea; antenna_0..2, antscale, flagellum; antennule_0..2, antennule_lat / _med;
                 mxp3_0..2 (the third maxillipeds)
  chelipeds      cheliped_coxa / _basis (the basi-ischium) / _merus / _carpus, cheliped_propodus (palm + fixed finger),
                 cheliped_dactyl
  walking legs   p2..p5 _coxa / _basis / _merus / _carpus / _propodus / _dactyl
  abdomen        abd_1..abd_6 (tergite + pleura), sternite_1..6, pleopod_1..5, telson, uropod (the protopod),
                 uropod_endo, uropod_exo, uropod_exo_dist (the exopod past the diaeresis)

HOW EACH IS MADE (life mm; emit() writes it at the author scale):
  CARAPACE   a loft through station sections along z (arthropod_parts.loft_sections), from its posterior margin
             (z -CL) to its front (the orbit's level): each section a dome over the body, the dorsal arch from the
             midline top to the widest point, the side down and a little in to the branchiostegite's free margin (a
             lip), the bottom an arch rising from the two margins over the body (the ventral thorax fills it). Its
             lines: the plan half-width M1's (c11, cara_left / cara_right); the dorsal line c06's solved landmarks at
             the bind (rest.c06 lifted by rig.lift: decapod.levels); the depth c20's line drawing (C20_DEPTH, read on
             x2/views/c20_cara.png) scaled to L1's true depth at the deepest station (body.cara_depth). A loft divides
             its whole field by its steepest change along z, so every line is held to CARA['slope'] (lipschitz): where
             c20's margin rises steeply under the eyes the clay's front stays deeper, and ends in a near-vertical front
             face, the carapace's anterior margin. The ROSTRUM a loft of lens sections on M1's traced width, its top
             through c06's front_top, unioned into the carapace's program.
  TERGITES   one loft each, a PI section: the dorsal arch over the somite and the two pleura hanging at its sides,
             their tips at M1's traced width (c11 abd_left / abd_right, M1's rows mapped onto L1's tergites: Outline.
             abd_z), the depth abdomen.d2 times ABD['depth'] [E]; the top at rig.abd_hinge x the depth over the bind's
             hinge line. X2b: each pleuron a TONGUE from the side (TONGUE, pleuron_depths): its front corner rounded
             up, its margin descending to the deepest point at the back, where T2-T5 carry a small backward tooth. Each tergite's front FLANGE (the dorsal arch alone, inset ABD['inset']) runs forward under the
             previous tergite's hind margin (abdomen.overlap's middle: 0.20 of the segment), T1's under the carapace.
             The STERNITE a rounded box between the pleura under the somite (the pleopods' footing). X2c (the
             lead's call on the X2b check): the tongues' fronts rise TONGUE['front'] (0.22) of the depth, as c04 / c10
             show them, and the sternal band shows in the NOTCHES between the tongues as those photos show it: the
             tergite's floor (ABD['floor']) no longer sits on the sternite's level (a pleuron must hang below its
             tergite's floor, so the old shared level capped the front's rise), and the sternite runs from that floor
             down to ABD['stern'] of the depth, its side face filling each notch to near the tongue line.
  LEGS, HEAD tapered TUBES (tube(): a PSWEEP of a superellipse section, two half-sizes going linearly along a straight
             segment) from joint to joint of the bind, each child's proximal end sunk SINK_FRAC of its own half-size
             back into its parent (the condyle; X4 gates 0.2-0.3 r), the half-sizes LEG_R / CHEL_R / HEAD_R [E]: the
             walking legs' merus 6 mm across (legs.merus_width), the rest by eye on c11 / c13 / n01 (gate: the look).
             Each walking leg's dactyl stops where its tip's LOWEST point meets the ground (tip_on_ground: the bind
             stands the tip joints on y 0, and a tube ending there reached its end section's rim 0.26 mm below).
             The cornea a near-sphere sunk in the eyestalk's end.
             X4e, THE KNEE (the lead's call 4 on the X4d check; KNEE's comment): the cheliped's carpus starts from a neck at K
             and a hard WHEEL about the knee's fold axis fitted inside the merus's end (knee_carpus), not a block.
  CHELAE     M1's own claws (c11): each claw's traced silhouette in its fingers' plane (Outline.claw: s along the claw
             axis from the carpal joint, m toward the dactyl) split at the dactyl's pivot (M1's articulation knob,
             which X2 measured as rig.cheliped.hinge / cutter_hinge) and the gape's bottom into the PROPODUS (palm and
             fixed finger) and the DACTYL. Each a PLAN SLAB (the plan polygon swept straight across the fingers' plane:
             an exact extrusion, divisor 1) smoothly INTERSECTED with a THICKNESS ENVELOPE (a loft along the claw's
             axis of wide lens sections: half-thickness CLAW_TH x the claw's [E] thickness, chela.crusher_thick /
             cutter_thick; its plan reach covers the slab, held to a gentle slope), so the plan is M1's exactly and the
             field stays a distance bound with a small divisor (a loft along the axis alone would divide by the
             fingers' curl and the gape's step, about 2). Mapped into the bind's claw frame (decapod.claw: the wrist W,
             the axis d, the dactyl's side n, the fingers' plane vertical); the dactyl turned about the rig's hinge H
             from M1's opening (x2.c11, 17.4 deg on the crusher) to the bind's rig.cheliped.dactyl_open. dactyl_pose
             builds it at any opening (x02's outline gate poses it at M1's).
             THE CUTTER'S FINGERTIPS (X2b): on M1 the crusher's dactyl lies across both cutter fingers, so the traced
             outline stops on its edge (cu_tip; X2 closed the fixed finger there in a 9 mm flat face). Both fingers
             are continued under it to NARROW ROUNDED TIPS, the form of c13's whole cutter (x2.c13.tip_palm: each
             finger's width L/40 behind its tip, a fraction of the palm): the fixed finger's lateral edge goes on along
             the circle fitted to its last visible run (CUTTER['lat_run'] mm), its occlusal edge along X0b's saw line,
             and a round cap joins the two (cutter_fixed_tip): its far point from the wrist is the fixed tip,
             chela.cutter_len, inside the crusher's dactyl (whose far edge, M1's open crusher gape where no cutter
             shows, lies at s 118.5-122 in the cutter's frame). X2c: the cap's radius rig.cheliped.cutter_cap is
             FITTED to c13's tip profile (x2.c13.tip_profile at x2.c13.tip_stations: the fixed finger's widths 4 / 8 /
             12 / 16 px and L/40 behind its tip, across its own axis; fit_cutter_cap) like for like: the clay's chords
             across the finger's own axis at the tip (the bisector of its two edges there), at c13's stations scaled by
             the palm as its widths are (X2b's fillet, half c13's L/40 width, read 10-19 % wide there). The cutter's
             frame is turned
             rig.cheliped.cutter_axis toward the dactyl so its axis runs to that tip, as the crusher's runs to its own
             (Outline.claws). The dactyl ends in a round cap of c13's dactyl tip width, its far point Ld from the knob
             (the rig's rule) along X2's estimate's line, its medial edge carried on smoothly from the contact
             (cutter_dactyl_tip). X4c: the cutter's propodus base round the wrist is a G1 closure (a Bezier on the
             run's end tangents, CUTTER base_handle): the crusher's 3-point layout folded back into a spur on the
             cutter's narrower palm (claw_polys); r57282_7 shows the base broad and round under the carpus.
             X4d: the crusher's base narrows across the thickness into its ARTICULAR KNOB (CLAW lump: the half-
             thickness x 0.6 at the base's back rising to x 1 by s 6), so it turns inside the carpus's end over the
             wrist's range instead of swinging its corners through the carpus's lower side (the lead's call 1).
             X4e, THE SOCKET (the lead's call 1 on the X4d check; SOCKET's comment has every size): the crusher's claw
             joint as the animal builds it. The propodus's distal end is a RIM, a concave arch in plan from the knob to
             the gape's bottom G (notch_arch), round a COLLAR, a solid of revolution about the hinge axis with a rounded
             lip (socket_parts); the dactyl's base is a FAN about the same axis (heel_plan: a radial tongue's end, the
             heel's arc inside G, a Hermite blend onto M1's occlusal edge; capped to the same revolve by the knob), so it
             slides through the rim into the palm's interior and the junction reads the same at every opening, where
             X2's straight notch line left the base swinging through a solid wall (8 mm deep at the close, wholly out at
             40). The palm's interior it swings in is socket_sd (x04 gate 9), the crescent's smooth functions rim_f,
             hard_edge_f, crescent_mask (X5 / X9's masks); the two condyles on the axis are the cage's (decapod_cage
             FEAT condyle).
             X4f (the lead's calls on the X4e check): the hinge is the CONDYLE's axis under the top margin (n04's ball,
             condyle_hinge), on BOTH claws, so each joint has two arms, the gape's and the top's (r57282_7's crescent
             and top slit), round a cup DISK on the axis (socket_notch, socket_angles, heel_plan, socket_parts); the
             condyles are X6 strokes on this cage. 3rd session: each claw's closed limit is where its fingers' CLAY
             first meets (clay_contact, x02's rule for the SPEC's hinge c); the socket's blends widened for the cage
             (SOCKET, THE BLENDS).
  FAN       the telson, the endopods and the exopods as flat slabs on M1's traced fan (c11 fan_left / telson_left,
             M1's rows mapped onto L1's abdomen, its width scaled to L1's abdomen.fan_spread), the exopod split at
             M1's diaeresis; the endopods a little under the telson's and the exopod's margins (in the fan they slide
             under them); the protopod a short tube under T6's posterolateral corner.

LISTED OVERLAPS (overlaps(parts)): every joint's parent and child (the condyle), the carapace over the ventral thorax,
each tergite over its sternite and its flange under the previous one (T1's under the carapace), the telson and the
protopods under T6, the coxae in the ventral thorax, the eyestalks, antennae and antennules in the carapace's front,
the maxillipeds in the ventral thorax, the pleopods in their sternites. x02 gates every other pair disjoint.

UNITS: life mm in; programs in metres at the author scale (chain['scale_m'] per life mm: 0.004 at x4).
"""
import numpy as np

from .. import sdf as S_
from . import arthropod_parts as AP
from . import decapod as DP

UP = np.array([0.0, 1.0, 0.0])
M_X = np.diag([-1.0, 1.0, 1.0])

# ============================================================================================ constants
# [P c20] the carapace's depth below its dorsal line (CL) at z (CL from the orbit, + forward): Calman's side drawing
# (lobster_web/c20_calman_side_drawing, 111 px per CL), read on x2/views/c20_cara.png at x6.7, +-1.5 px (+-1.4 % CL)
C20_DEPTH = ((-0.955, 0.450), (-0.838, 0.486), (-0.730, 0.491), (-0.568, 0.486), (-0.387, 0.473), (-0.297, 0.459),
             (-0.207, 0.432), (-0.117, 0.387), (-0.054, 0.333), (0.0, 0.261), (0.027, 0.189), (0.045, 0.135))
C20_DEEP = 0.491              # c20's depth at the deepest station (X0b's src_c20: 54.5 of 111 px)
CARA = dict(z_back=-100.0, z_front=0.0, step=1.5, rho=1.2, slope=0.8,
            hw_frac=0.40,      # [E] the widest point this far up from the margin (c08's front view: low on the flanks)
            margin_in=0.14,    # [E] the free margin this fraction of the half-width inside the widest point (c06's
            #                    deep_bot offset 0.20-0.27 CL against c11's widest 0.268; the walking legs' bases and
            #                    meri pass under it)
            rise=0.25, rise_max=12.0,   # [E] the bottom's arch over the body: a fraction of the depth, capped (mm)
            rise_fade=(-40.0, -4.0))    # [E] ... full behind the first z, none ahead of the second (no walking legs
#                                         under the face; x02's first run saw an empty arch from the front); spread
#                                         over 36 mm so the loft's divisor stays low
ROSTRUM = dict(z_base=-5.0, rho=0.25, t_frac=0.55, t_add=0.45, k=1.0)   # [E] half-height = t_frac x half-width + t_add
THORAX = dict(z_back=-97.0, z_front=-6.0, half=7.6, half_front=12.0, front_z=(-30.0, -14.0), below=4.5, into=1.5,
              rho=1.5)   # [E] the sternal plastron, widening forward into the mouth field (under the face)
ABD = dict(depth=(0.85, 1.0, 0.97, 0.92, 0.85, 0.70),   # [E] each somite's depth / abdomen.d2 (T2 the deepest, c06)
           rho=1.0, shoulder=0.30, flare=1.5, pleuron_t=2.4, inset=1.4, flange=0.20, step=1.0,
           smooth=1.5, slope=0.6,
           # X2c [E] by eye on c04 / c10 (the ventral band fills each notch from its top to the tongue line): the
           # tergite's FLOOR (its core's underside between the pleura) this fraction of the depth below its top, high
           # enough that the tongue's raised front still hangs below it (TONGUE plate_min); the STERNITE from that floor
           # (lapping stern_lap mm into it) down to `stern` of the depth: the pleura's own depth at their back, so no
           # notch sees through under it to the far side's notch (X2: 0.80, the floor and the sternite's top on one
           # level, its underside hidden behind the pleura); its half-width `slot` mm inside the pleura's inner faces:
           # the slot where pleopods 2-5 lie forward beside it (PLEO_FOLD), above the tongue line
           floor=0.64, stern=1.0, stern_lap=1.0, slot=5.0)
# X2c [E]: pleopods 2-5 folded forward in the slot beside their sternite (the protopods sit at the sternites' lateral
# ends; X2b laid them under its underside at x 10): their half-sizes (lateral, vertical) at the base and the tip, life
# mm, and their lowest point `lift` mm over the pleura's depth at the back (the tongue line: x02's tuck gate); the
# skeleton's rig.pleopod.x_25 / drop_25 put their joints there (x02 checks the rule)
PLEO_FOLD = dict(r=((1.4, 1.0), (0.8, 0.4)), lift=0.3)
# X2b, the pleura as TONGUES ending in the backward tooth (c04, c10 clearest; c06's T2 flatter; the lead's call), [E]
# by eye on those photos: seen from the side each pleuron's front corner is well rounded (the margin rises toward the
# front, front of the somite's depth at the front face, over its first `corner` of the somite: a quarter ellipse,
# held to `slope` mm per mm so the loft's divisor stays low), its lower margin then descends `fall` of the depth to the
# DEEPEST point at the back, the tooth: a small cone (radii tooth_r, from tooth_in inside the pleuron to tooth_out
# behind the somite's hind boundary, tooth_dip under the margin) on T2-T5, pointing back over the next pleuron's
# rounded front. The somite's depth (ABD depth x abdomen.d2) is the tooth's: c06's abd2_pleuron, somite 2's pleuron TIP
# (x02's gate 4 samples T2's lowest point at the rest). X2c (the lead's call): the front rises the full `front` of the
# depth (c04 / c10's ~0.22), the sternal band and pleopods 2-5 showing in the notch between it and the tongue in front
# (X2b capped the rise front_clear 3 mm under the sternite, which it kept hidden: the photos show the band there); the
# only guard left is the section's own: the pleuron's raised front hangs at least plate_min mm below the tergite's
# floor (ABD['floor'])
TONGUE = dict(front=0.25, corner=0.35, fall=0.07, slope=1.2, plate_min=2.0, teeth=(2, 3, 4, 5),
              tooth_r=(1.15, 0.45), tooth_in=3.0, tooth_out=3.0, tooth_dip=0.10, tooth_k=0.8)
# (X2c: front 0.22 -> 0.25, between the lead's ~0.22 (c04 / c10, the X2b builder's estimate) and c10's tongue 2, which
# reads its notch 0.27 of the depth deep over the front 0.35 of the tongue: corner 0.45 -> 0.35; the ellipse now starts at
# the loft's front face, pleuron_depths. The slope stays near X2b's 1.1: c10's front edge runs about 2 in 1, but the
# loft divides its field by its steepest change, and at 2.0 the tergites' gradient p1 fell to 0.51-0.54, x02's gate 1)
FAN = dict(half_t=1.5, rho=1.1, endo_drop=2.6, exo_drop=0.3, exo_half_t=1.1, endo_half_t=1.0, smooth=1.2,
           diaeresis=((829.0, 2662.0), (914.0, 2785.0)))   # [P c11] the beaded suture across M1's left exopod (px)
SINK_FRAC = 0.25              # [E] a condyle's sink into its parent, of the child's least half-size (X4 gate 0.2-0.3)
# [E] the walking legs' segments: (half across the leg's plane, half in it) at the proximal and distal ends, life mm;
# the merus 6 mm across (legs.merus_width; c11's distal segments 0.054-0.069 CL), the rest by eye on c11 and n01
LEG_R = dict(coxa=((4.0, 4.6), (3.6, 4.2)), basis=((3.3, 3.8), (3.0, 3.5)), merus=((2.9, 3.5), (2.7, 3.3)),
             carpus=((2.6, 3.0), (2.4, 2.8)), propodus=((2.3, 2.6), (1.7, 1.9)), dactyl=((1.45, 1.6), (0.32, 0.36)))
CHEL_R = dict(coxa=((6.0, 6.5), (5.5, 6.0)), basis=((5.3, 5.8), (5.0, 5.6)), merus=((5.5, 7.5), (6.5, 8.5)),
              carpus=((7.0, 8.0), (9.5, 10.0)))   # [E] c11 / c13 / n04 by eye: the merus deep, the carpus stout
HEAD_R = dict(eyestalk_0=((2.3, 2.3), (2.4, 2.4)), eyestalk_1=((2.4, 2.4), (2.6, 2.6)), cornea=2.9,
              antenna_0=((3.6, 3.4), (3.2, 3.0)), antenna_1=((3.0, 2.8), (2.6, 2.4)), antenna_2=((2.4, 2.2), (2.0, 1.9)),
              flagellum=((1.6, 1.6), (0.28, 0.28)), antscale=((2.1, 0.6), (0.35, 0.3)),
              antennule_0=((1.7, 1.6), (1.5, 1.4)), antennule_1=((1.4, 1.3), (1.3, 1.2)),
              antennule_2=((1.2, 1.1), (1.1, 1.0)), antennule_f=((0.8, 0.8), (0.25, 0.25)),
              mxp3_0=((2.6, 3.0), (2.3, 2.6)), mxp3_1=((2.2, 2.4), (2.0, 2.1)), mxp3_2=((1.9, 2.0), (1.2, 1.2)),
              pleopod_1=((1.2, 1.2), (0.5, 0.5)),
              protopod=((3.5, 2.6), (3.0, 2.1)))
# [E] the claws' half-thickness across the fingers' plane along each part (s / its length, a fraction of the claw's
# chela.<kind>_thick / 2): the palm's middle the thickest, the neck and the finger bases thinner, the tips 2-3 mm
CLAW_TH = dict(propodus=((-0.10, 0.62), (0.05, 0.80), (0.35, 1.0), (0.55, 0.92), (0.72, 0.62), (0.90, 0.30),
                         (1.05, 0.18)),
               dactyl=((-0.08, 0.66), (0.10, 0.70), (0.45, 0.52), (0.80, 0.30), (1.05, 0.16)))
CLAW = dict(slab_rho=0.9, env_rho=1.0, env_pad=2.2, env_slope=0.6, k=2.4, p_m=2.2, p_t=2.0, dactyl_sink=2.0,
            base_back=5.0, smooth=1.2, palm_smooth=3.0,
            edge_smooth=2.0,     # the biting edges and the dactyl's margins: M1's teeth, molars and setae out (X4, X6)
            outer_from=84.0,     # X4e: the crusher's outer margin smoothed from here on: the palm's lowest point, s 80, stays
            #                      M1's (rig.cheliped.tip_h's rule reads it: smoothed from the base, 0.06 mm off, x02)
            env_step=1.0, env_soften=2.5, env_pts=96,   # the envelope's stations, their softening along s, its lens
            # X4c: the crusher's base closure round the wrist smoothed a further base_round mm (Gaussian sigma) behind
            # s base_round_s[0], fading out by base_round_s[1] (claw_polys): its 3-point corners (the lower one turning
            # 31 deg per 0.6 mm) made the knob's rim, whose limit stood 0.85 mm off the clay where it shows at the
            # wrist's extremes (x04 gate 10, the lead's call 5)
            base_round=3.0, base_round_s=(0.0, 6.0),
            # X4d (the lead's call 1, the knob face 'built as the articular lump c11 shows'): the crusher propodus's base
            # narrows across the claw's thickness into a rounded knob that turns INSIDE the carpus's end: its half-
            # thickness x lump[0] at the base's back, rising (a smoothstep) to x 1 at claw-frame s lump[1] mm. The wrist
            # hinges about the claw's height (n) through W, at the base's top: the base, +-11.2 mm thick where the
            # carpus is +-9.5, swung its proximal corners 6 mm back into the carpus's lower side over the lead's -30..+40
            # (the swept propodus touched the carpus at s -9.7, X3's wrist ring at -10: no carpus chitin could pass it);
            # x0.6 to s 6 keeps the touched region >= 1.6 mm past X3's ring (scratch x4d probe_lump / probe_plane2:
            # 0.75 1.9 mm planar, 0.65 2.4, 0.55 3.2; the cutter's base, +-7, already turns inside)
            lump=(0.6, 6.0),
            # A0 (x6fix_x7, the lead's shape audit, point 1, 'flat slabs with edges'; scratch a0_measure.py on the X4h
            # limits): with the envelope's reach the plan's width + env_pad, its section still stood ~38 % of its
            # thickness at the plan's margin, so the slab's straight walls cut a flat band ~11 mm tall along the palm's
            # dorsal and ventral margins, its two corners the smooth intersection's shoulders (twin curvature peaks at
            # each margin; the faces r 63-131 mm where an ellipse of the same width and thickness has ~50-60). c11 / n04
            # / r57282_5-7 show swollen faces and round margins. ROUND OUTER MARGINS: the outer margins' pad round_pad
            # (the envelope closes ON the plan's margin), an elliptic section across the plan (round_p_m); the biting
            # edges and the socket keep env_pad (X4d-X4h tuned them) AND, since A0c (11-11), their own exponent p_m
            # (plan_solid: each margin's exponent follows its pad; A0 had laid round_p_m on both margins of the whole
            # part, and x04 failed gates 2 / 3 / 8 by hairs on the kept regions): the propodus's upper margin round from
            # round_base to round_knob[0] mm before its knob (M1's articulation), back to env_pad by round_knob[1] mm
            # before it; its lower margin round from round_base on; the dactyl's outer margin round from round_dactyl
            # (mm from its hinge), its occlusal margin as before (claw_pads)
            round_pad=0.0, round_p_m=2.0, round_base=(6.0, 14.0), round_knob=(8.0, 2.0), round_dactyl=(10.0, 18.0),
            round_slab=1.5, round_tip=(4.0, 12.0))


def _ramp(x, x0, x1):
    """0 before x0, 1 after x1, a smoothstep between"""
    t = float(np.clip((x - x0) / (x1 - x0), 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def claw_pads(part, s_knob=None):
    """A0 (CLAW round): a claw part's envelope pads (pad_lo(s), pad_hi(s)), s along the part's own axis (life mm): the
    propodus's (s from the wrist; s_knob its knob, claw_polys artic) round on both outer margins, its upper margin back
    to env_pad at the socket and along the fixed finger's biting edge; the dactyl's (s from its hinge) round on its
    outer (upper) margin past its base, its occlusal margin env_pad"""
    P, R = CLAW['env_pad'], CLAW['round_pad']
    if part == 'propodus':
        b0, b1 = CLAW['round_base']
        k0, k1 = CLAW['round_knob']

        def lo_(s):
            return P + (R - P) * _ramp(s, b0, b1)

        def hi_(s):
            return P + (R - P) * _ramp(s, b0, b1) * (1.0 - _ramp(s, s_knob - k0, s_knob - k1))
        return lo_, hi_
    d0, d1 = CLAW['round_dactyl']
    return (lambda s: P), (lambda s: P + (R - P) * _ramp(s, d0, d1))


def grow_round(poly, pads, delta):
    """A0 (CLAW round_slab): the plan polygon (s, m) with each vertex on a ROUND side moved out along the polygon's own
    outward normal by delta x that side's roundness (1 - pad / env_pad there): where the envelope closes ON M1's margin
    the slab's wall stood on it too, and the smooth intersection (CLAW k) pulled the margin in by k / 4 (0.6 mm: x02's
    outline gate read the cutter's fit at scale 0.974); delta clear of it the pull is (k / 4)(1 - delta / k)^2 (0.085 mm
    at 1.5) and the envelope alone draws M1's margin. The biting edges and the socket (pad env_pad) stay unmoved; each
    vertex moves ACROSS the plan only (its normal's m share: no part grows along its axis), and not within round_tip
    mm of the part's tip (x02's fingertip gate: there the envelope cannot narrow as fast as the plan, so the slab
    draws the tip; moved, the cutter's fixed tip grew 1.07 mm and its profile left c13's)"""
    P = ccw(np.asarray(poly, np.float64))
    E = np.roll(P, -1, axis=0) - P
    en = np.column_stack([E[:, 1], -E[:, 0]])                        # each edge's outward normal (counter-clockwise)
    en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-12)
    vn = en + np.roll(en, 1, axis=0)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    Pd = CLAW['env_pad']
    s_tip = float(P[:, 0].max())
    t0, t1 = CLAW['round_tip']
    w = np.zeros(len(P))
    for j, (s, m) in enumerate(P):
        iv = interval_at(P, float(np.clip(s, P[:, 0].min() + 1e-6, P[:, 0].max() - 1e-6)))
        if iv is None:
            continue
        pad = pads[1](float(s)) if abs(m - iv[1]) < abs(m - iv[0]) else pads[0](float(s))
        w[j] = float(np.clip(1.0 - pad / Pd, 0.0, 1.0)) * _ramp(s_tip - float(s), t0, t1)
    return P + np.column_stack([np.zeros(len(P)), vn[:, 1]]) * (delta * w)[:, None]
# X4e (the lead's call 1 on the X4d check, THE SOCKET; module docstring, CHELAE): the claw joint as the animal builds it
# about the rig's hinge H: the dactyl's base is a FAN about the hinge axis sliding through the propodus's RIM, the rim a
# solid of revolution (the COLLAR), so the junction reads the same at every opening. X4f (the lead's calls 1-2 on the X4e
# check): H is the CONDYLE's axis under the top margin (decapod_parts condyle_hinge, n04's ball), on BOTH claws, so the
# joint has TWO ARMS: on each broad face the rim runs from the knob A down to the condyle and on to the gape's bottom G
# (n04; r57282_7's top slit and gape-side crescent meet at the boss). The propodus keeps a DISK of the condyle's radius
# round the axis (the cup: its plan's notch goes round H on the distal side), the condyles' domes whole on its faces
# (decapod_cage FEAT condyle); the GAPE ARM's rim is the ray from the cup to G, the TOP ARM's the ray from the cup to A.
# Opening drives the gape side OUT (its crescent opens) and the top side IN; closing the reverse: each arm has its own
# tongue, collar, rim ring and hard edge (socket_notch, socket_angles, heel_plan, socket_parts, socket_sd). [D] by
# construction, [E] the sizes:
#   clear   the HEEL's clearance inside G: the dactyl's occlusal edge near its base is the arc of radius |G - H| - clear
#           about H, so G is a fixed point the heel slides past at every opening; clear_o the same for the TOP ARM: the
#           dactyl's top margin near its base is the arc |A - H| - clear_o about H (the claw's margins are thin: inside the
#           knob the propodus must stand round the arc's edge), so A is a fixed point it slides past
#   back    the gape TONGUE: the base carried this far (deg) behind the gape ray at the open limit (SPEC
#           chela.dactyl_open), its end a radial line: inside the propodus at every pose; back_o the TOP TONGUE (the
#           second tongue, the lead's call 1), the top margin's arc carried this far behind the top ray at the CLOSED limit
#   front   the heel's arc runs this far (deg) past the angle that reaches G at the closed limit (`close`, deg), then
#           a Hermite blend of `blend` mm back onto M1's edge; front_o / blend_o: the top arc this far past the angle
#           that reaches A at the open limit, then onto M1's top edge
#   wall    each arm's COLLAR: the propodus round the arm's ray thickened to the joint's thickness T(r) plus this (mm), a
#           solid of revolution about the hinge axis over the sector behind the ray (phi_min / phi_min_o deg), smooth-
#           unioned (col_k); T(r) the dactyl's own half-thickness at radius r, the most over that arm's SLIDING BAND
#           (every part of it that ever passes the ray, its tongue included; + t_margin), so the collar is a rim round
#           the base (r57282_7 / c08: the rim wraps the dactyl's base), the visible rim `wall` wide. Where the propodus
#           is thinner than that at the collar's back edge, T(r) is held `bury` under it less the wall and the dactyl's
#           band CAPPED to it by a revolve (cap_k) over that arm's band only, out to the last such radius + 1, released
#           over cap_ramp mm (X4e: a cap over the whole base cut a groove across the finger, look/clay_socket1.png); X4f,
#           2nd session: cap_k 1.5 (was 0.6): the cap's edge at its band's ends is a step in the dactyl's broad face by
#           the axis, and at 0.6 the dactyl cages' limits tilted / folded across it (x04 gate 2: the crusher's quads 20
#           and 28 at the gape band's -26.9 deg end, the cutter's at -56; scratch x4f probe_g23 i: 0 / 0 at 1.5)
#   socket  the propodus's interior the base swings in (x04 gate 9 reads its chitin without it): per arm r <= its heel's
#           radius + sock_r, |t| <= its T(r) + sock_t, from its ray to its tongue's end at the far limit plus sock_deg
#           (X4f: 4, was 2: the cutter's tongue end, rounded, reaches 2-4 deg past its radial line at r 3-5 mm);
#           and the CUP: within the bearing's reach + cup_pad of the axis at any angle (the bearing: both shells turn
#           there; the pad holds the unions' fillets), |t| <= the disk's face + sock_t (X4f, 3rd session: the reach
#           r_cup + cup_k / 4 or the hub measured in the V's middle, hub_off deg in from the rays out to the shorter ray +
#           hub_pad; the thickness no longer less the wall: THE BLENDS)
#   cup     the propodus's DISK round the axis (the real joint is flush at the condyle, the ball on top: n04): radius
#           x2.n04.condyle_r of |G - A| (n04's ball) plus cup_gap mm, a solid of revolution whose faces stand cup_rise
#           over the dactyl's thickest face just outside it (so the turning dactyl never shows through it), its edge
#           rounded cup_rho, unioned cup_k; its arc on the distal side sampled every cup_n mm. The condyles' domes sit on
#           its faces where the axis leaves them, condyle_h of their width high (decapod_cage FEAT condyle). X4f, 2nd
#           session: the ball's foot must stand on the disk's FLAT face, cup_gap - cup_rho (0.5 mm) of it round the
#           foot: at gap 0.5 / rho 1.0 the flat ended at the ball's radius less 0.5 (the crusher 3.60 mm against its
#           4.08 foot, the cutter 1.59 against 2.09: its whole foot on the rounding) and the dome's foot quads, draped
#           over the rim, folded the limit (x04 gate 2: 53 / 50 faces, 17 / 16 against the clay's own normal; scratch
#           x4f probe_g23, check_fold_ref) (moot once the condyles became X6 STROKES, decapod_cage FEAT condyle_band: the
#           3rd session rounds the edge 3 mm, THE BLENDS below); and the cup leaves slit_min mm of the TOP RAY to the
#           knob A (r57282_7's top slit runs from the boss to the knob): the crusher's 5.07 mm, the cutter's 1.66 (its
#           ball's 3.09 reached
#           within 0.5 mm of its knob, and its cage, ~3.5 mm faces, chorded across it: x04 gate 2's low tilts at the axis)
#   wedge   the dactyl's gape HARD EDGE: a copy of the gape ray turned to this many deg past it at the open limit. Behind it
#           the fan is the joint's membrane (rigid on the dactyl, no skin: decapod_cage labels it): under the rim until
#           `wedge` deg short of the open limit, then the photos' dark crescent, a wedge zero at the cup and widest at the
#           gape (r57282_7, r6_hingeTop: ~2-2.5 mm there); each rim's own ring (`wall`, `clear` at the gape) is the
#           crescent at the lesser openings (M1's dark slot at 17 deg) and, on the top arm, r57282_7's TOP SLIT;
#           wedge_o the top hard edge past the top ray at the closed limit (X4f 0: the top band's membrane never showed;
#           X4g 8, THE TOP SLIT below)
#   rim_k   the collar's ridge rounded by this smooth intersection (r6_hingeTop / c05's rim is a rounded lip, and the cage's
#           columns on a 0.3 mm ridge stood 0.67 mm inside it, x04 _x4e2)
#   wall_g  the gape rim's width at G (the crescent is widest there, r57282_7), from `wall` over the outer 0.4 of the
#           radius, the collar's profile softened (Gaussian, col_soft mm)
#   bulge   the rim's clay stands up to this past each ray in the plane (col_k's smooth union of the collar and the palm,
#           both bounded by it): socket_sd's bound allows it
#   X4f, 3rd session, THE BLENDS (x04 gates 2 and 10 on the claws' cages; scratch x4f probe_g23 n-r, look_g10,
#           section_clay, check_sdf): the cage's 4-5 mm cells bridge every blend narrower than about a cell, the limit
#           standing OUTSIDE the clay in the concave ones (true distances 0.3-0.7 mm where |field| read 0.3-0.5: the
#           field's gradient is 0.64-0.95 there). The disk's edge rounded cup_rho 3.0 (at most cup_rho_share 0.8 of the
#           cup's radius: the cutter's 1.33), unioned cup_k 6.0 (0.5 / 0.8: its rim tilted and folded the limit, 4 low
#           tilts a claw on the cup's arc; cup_k 4: gate 10 0.63 / 0.55); the collars unioned col_k 5.0 (3.0) so their
#           valleys with the palm and the disk are wider than a cell, bulge 1.6 (1.0: col_k / 4 is 1.25 now, and the
#           clay measured 1.32 mm past the gape ray at r 13.8, 1.5 at r 8 where the disk's union joins: scratch dbg_hub); the dactyl's
#           caps cap_k 2.5 (1.5: the cutter's base corner stood 0.36 mm off, 0.25 at 2.5). What still stands off past
#           gate 10's 0.3 (probe q): the crusher palm's face at the axis 0.54 (the disk's face 2.4 mm under the palm's
#           there, so its smooth union lifts the palm h^2 k / 4 ~ 0.5 mm: a bump narrower than a cell), its collars'
#           valleys 0.37-0.39, its dactyl's gape tongue end 0.38, the cutter's gape collar 0.39: the cage's construction
#           (columns laid on the notch's rays and round the cup, as X4e laid them up its arch), not the clay's. The blends
#           carry the hub past r_cup, so the BEARING (sock bear, gate 9's) reaches r_cup + cup_k / 4 (socket_parts), and
#           decapod_cage notch_opening's band grows with `bulge`
#   X4g (the lead's calls on the X4f check), THE TOP SLIT AND THE CUTTER'S OPEN END: r57282_7 shows on both claws a SMALL
#           boss at the junction, the gape crescent from it toward G and a long dark TOP SLIT from it across the dactyl's
#           base to the knob A (x4g look r7_cr_4x / r7_cu_2x: the boss's radius ~0.08-0.18 of the top ray; the slit pale
#           by the boss, dark and lens-shaped out to a rounded lip at A). The X4f cup (n04's ball + cup_gap, the crusher's
#           5.07 of its 6.97 mm top ray) left the slit only the top ray's last 1.9 mm, and THE BLENDS stood its notch face
#           1.9-2.8 mm off the ray: a mid-thickness speck. And the cutter's open-end overlap (its propodus 0.51 mm inside
#           its dactyl at 47.5, r 5.1 past the knob) was the hub's FILL plus the top collar's union swell (col_k 5, ~1 mm
#           into the V past the knob): x4g look_clay, the clay meshed in memory, the cutter clear at 55 by 1.5 mm once the
#           cup is small and cup_k 1.5. So: the cup is the BOSS, boss_share of |A - H| + boss_gap (the crusher's 0.15:
#           1.35 mm; the cutter's 0.48: 2.01 mm, the least that hides its dactyl's top-band CAP near the axis, whose step
#           tilted the dactyl's cage in the V's apex at 0.83: scratch x4g probe_g23 Aa / B48), cup_k 1.5, the TOP collar's
#           union col_k_o 1.5 (3.0 swelled into the cutter dactyl's top margin at 55: 176 points 0.50 mm, probe K30); the
#           TOP SOCKET reaches the knob, R_o + sock_r_o (the dactyl's top margin past the top arc slides under the knob's
#           lip at the widest openings: the cutter's 0.32 mm at 55, r 3.55 = A's radius, probe A); wedge_o 8: the top fan
#           behind its hard edge shows dark as the dactyl closes past 8 deg (the slit widens as the claw closes, closes
#           as it opens: its membrane stretched and folded), the gape arm's wedge mirrored
SOCKET = dict(clear=1.8, back=5.0, front=3.0, blend=5.0, close=0.0, wall=1.2, col_k=5.0, t_margin=0.1, phi_min=50.0,
              bury=0.2, cap_k=2.5, cap_ramp=3.0, r_step=0.5, reach=2.0, sock_r=0.4, sock_t=0.6, sock_deg=4.0, n_phi=32,
              wedge=8.0, bulge=1.6, rim_k=2.5, wall_g=2.2, col_soft=0.8,
              clear_o=0.8, back_o=5.0, front_o=3.0, blend_o=3.0, wedge_o=8.0, phi_min_o=50.0,
              cup_gap=1.0, cup_n=0.4, cup_rise=0.2, cup_rho=3.0, cup_rho_share=0.8, cup_k=1.5, cup_pad=0.6, condyle_h=0.41,
              slit_min=1.9, hub_off=30.0, hub_pad=1.5,
              boss_share=dict(crusher=0.15, cutter=0.48), boss_gap=0.3, col_k_o=1.5, sock_r_o=1.2)
# X4e (the lead's call 4 on the X4d check, THE KNEE; r57282_6's folded knee, n04): the carpus's proximal end is a big
# round HARD ball rolling under the merus's rim, a thin crescent between them, the hinge axis through two condyles at the
# axis's ends. X2's carpus was a block centred on K (half-width 8, its corners 8.7 mm from K, the merus 6.6 and ending flat
# 1.65 mm past K), so at the fold its corner stood 5 mm past the merus's end, a rounded end that X4d's buried-condyle
# membrane showed pink. THE WHEEL: a solid of revolution about the knee's fold axis through K, its radius at each z the
# merus's own section at K (the least of its four half-widths at +-z) less `wall`, so its tail stays inside the merus's
# flanks at every pose and past the merus's end shows the same round silhouette at every pose; the carpus's tube starts
# at K from a NECK of half-sizes neck (along its `across`, in the fold plane), widening to the old tube's section by
# s_neck mm along it (the old tube past that, the wrist unchanged; n04: the carpus a cone from a narrow articulation),
# smooth-unioned (k) with the wheel
KNEE = dict(wall=0.6, neck=(7.0, 5.9), s_neck=20.0, k=2.0, step=0.1, stations=15)
# A0, ORGANIC (x6fix_x7, 11-10; Skye on the lobster: "looks overly geometry, not organic enough shapes in his arms and
# joints and such"; the lead's shape audit, point 3, 'plain pipes with rings'): THE CHELIPED'S ARM AS LOFTS OF MEASURED,
# CHANGING SECTIONS (limb_loft) in place of the round tubes (CHEL_R keeps the old ends: the knee's wheel and neck, the
# wrist's tube). Each row: (s mm from the segment's proximal joint, (xp, xm, yp, ym) the section's four half-sizes
# along +N / -N (its `across` normal) and +B / -B (B = t x N), (p of the quadrants +N+B, -N+B, -N-B, +N-B), and
# optionally the section centre's offset (along N, along B) from the straight axis). WHICH SIDE IS WHICH at the bind
# (scratch x6fix_x7/org2/probe_frames.py): coxa: +N anterior, +B ventral; basis, merus: +N anterior = the knee's FLEXOR
# side (the carpus folds onto it), -N posterior = EXTENSOR (toward P2), +B ventral, -B dorsal; carpus: +N the limb's
# dorsal side (the knee's fold axis, 38 deg medial of world up), +B the FLEXOR side (toward the merus), -B EXTENSOR
# (lateral). WHAT THE PHOTOS SHOW (c11 from above at 6.52 px a mm, n04 / c04 / c06 / c10 / r57282_5-7 from the sides):
#   merus    a CLUB: slim by the ischium, widening over its distal half to the knee (c11 ~24 mm across; ours was a 12-13
#            mm pipe); a flattened section, the back arched, the belly flatter. Ours widens on the EXTENSOR side only
#            (the flexor side is the old tube's: the knee's window and X4h's fold, x04 gates 9 / 11) and only past its
#            middle: P2's knee stands 10.6 mm from its axis at share 0.49 (probe_bind.py), so there the extensor
#            half-size stays under 6.7 (x02's disjoint gate); arched 1.2 mm dorsally
#   carpus   STOUT (c11 ~37 mm across, 40 long): from the knee's narrow articulation (the wheel and neck, X4e) it swells
#            at once on its lateral (extensor) and dorsal sides to a BODY ~27 x 25 mm that ends in a thick rounded
#            distal LIP round the wrist (c06 / c10: the rim that cups the propodus's knob, the membrane crescent under
#            it), its dorsal-medial corner produced into a rounded LOBE over the knob (c11's tan lobe, c04, r57282_6).
#            The flexor side keeps the old tube's section to s 20 (the first A0 body, swollen both ways, put the merus
#            2.62 mm in the carpus at the knee's 30 deg fold: x04 _a0). The body is its OWN loft (carpus_body), ending
#            flat at the lip: a lip inside the tube's loft would divide the whole field by its slope (PSWEEP), and the
#            wrist's ring (x03: the first collar clear of the propodus bases, s ~33.6 on the flat claw plane) and the
#            membrane past it stay on the old tube
#   coxa, basis   short stout barrels, never round: the coxa's belly swollen, its back flat under the carapace (the
#            basis 0.45 mm from the carapace at life: no growth dorsally); the basi-ischium's anterior margin keeled
#            and swelling toward the merus (n04, r57282_6)
# Flanks are held under ~0.95 mm per mm along the axis (a PSWEEP divides its field by sqrt(1 + slope^2): x02's
# gradient gate, p1 >= 0.6). rho: each loft's corner radius, its flat ends rounded by it (the rims, millimetres)
ARM = dict(
    # A0 v3b (the 22:02 restart; both still read as round barrels in v3j): the same two forms said harder, their END
    # rows as before (the joints): the coxa's belly fuller (8.0 at s 4) under a flatter back (5.7, p 3.0: the
    # carapace is 0.45 mm over it); the basi-ischium's anterior margin a KEEL (the anterior quarters' p 1.7) that
    # swells to 7.1 by the merus (n04, r57282_6). By eye from those two photos: neither shows a scale for them
    coxa=dict(rho=1.8, rows=((0.0, (6.4, 6.0, 6.9, 6.4), (2.2, 2.2, 2.6, 2.6)),
                             (4.0, (7.0, 6.2, 8.0, 5.7), (2.1, 2.1, 3.0, 3.0)),
                             (9.0, (6.7, 5.9, 7.3, 5.6), (2.1, 2.1, 3.0, 3.0)),
                             (12.5, (6.2, 5.7, 6.4, 5.8), (2.3, 2.3, 2.6, 2.6)),
                             (13.959, (6.2, 5.7, 6.3, 5.9), (2.3, 2.3, 2.5, 2.5)))),
    basis=dict(rho=1.6, rows=((0.0, (5.5, 5.3, 5.9, 5.8), (2.2, 2.4, 2.4, 2.2)),
                              (4.0, (6.0, 5.3, 6.2, 5.5), (1.9, 2.4, 2.4, 1.9)),
                              (8.0, (6.9, 5.5, 6.0, 5.3), (1.7, 2.5, 2.5, 1.7)),
                              (11.5, (7.1, 5.5, 5.6, 5.3), (1.7, 2.5, 2.5, 1.7)),
                              (13.021, (6.2, 5.3, 5.4, 5.3), (2.0, 2.5, 2.5, 2.0)))),
    # A0 v2 (19:25 restart; v1's merus read as a pipe with a cut end): THE MERUS A CLUB, DEEP AT THE KNEE: its distal
    # third deeper dorsally and ventrally (n04 / r57282_6: the merus's end as deep as the carpus it carries) and wider
    # on the extensor side, the back keeled (the dorsal quadrants' p 1.75-1.8), the belly round; its flexor half-size
    # (xp) the old tube's all along (the knee's window, X4h's fold).
    # A0 v3 (20:36 restart; v2a's knee read as a ball in a pipe's flat cut end: the club's 18.8 x 22 mm end face stood
    # bare round a 6 mm wheel): THE END A KNUCKLE: past s 38.5 the extensor, dorsal and ventral half-sizes fall to
    # 8.2-9.6 at the knee (slopes 0.4-0.65), so the end face left round the wheel is 2-3 mm, all of it inside the end's
    # rounding (c04's merus rounds over into the joint line; r57282_6's pale knob between merus and carpus).
    # A0 v3b (the 22:02 restart; v3a's knee still read as a ball between two forms): THE HINGE'S TWO EARS (`tongues`),
    # carried 4 mm PAST the knee (K at s 44.2) over the wheel's two poles, the only place past a hinge the partner
    # never sweeps (it turns about the axis through them; the carpus's neck is 7.0 high at K). Each is a TONGUE, a
    # small loft of its own (rows as the segment's, with a centre offset (N, B) and a TURN): flat and tapering, its
    # outer face the segment's own line carried on: the dorsal one the back's line into a hood (c04's hood line;
    # n04 / r57282_6's spine stands on it), the ventral one the knob under the joint (r57282_6). So the wheel shows
    # only in the two windows the carpus swings through, as the membrane's lens (n04), not as a ball.
    # THEY LIE ON THE FOLD AXIS, NOT ON THE MERUS'S OWN B: the knee's axis stands 13 deg from it (its dorsal end at
    # theta 283, its ventral end at 103, from +N toward +B). Written on +-B they were tilted 13 deg to the fold
    # plane and the carpus's neck came ~1 mm into their flexor edges at the knee's extended limit (-58.6 deg). So
    # each row is TURNED 13 deg (its section's own y along the fold axis) and its centre lies r mm out along that
    # axis (r 9.2-10.8 dorsal, 7.9-10.5 ventral: undersides 8.8 / 8.6 mm from the fold plane at K, over the wheel's
    # poles, which stand at 8.3-8.5; scratch x6fix_x7/org4/arm_lab.py's ears row: the swept carpus stays 0.3 mm and
    # more off them).
    # Each lies inside the body to s ~41 and comes out where the knuckle falls away under it, on a CRISP line (k
    # 0.3): blended broadly (k 1.2-2.5, and with v3a's two round-cone lobes under their roots) the blends alone put
    # 1.2-1.8 % of the merus's surface under gradient 0.6 (x02 gate 1). (Tried and dropped as ears: round cones,
    # whose ends read as pegs with ball tips; round boxes, which read as a bracket's tabs.)
    # A0 v3t (11-11, the 00:52 restart): THE EARS ARE GONE, THE BACK A KEEL. Looked at beside c04 / n04 at full size,
    # v3r's two ears (crisp, k 0.3) read as TABS standing free past a tube's rim: c04 shows no free part there (the
    # merus's rim runs obliquely into the joint line) and n04's pale condyle boss lies IN the joint, between the two
    # shells; what stands over the knee dorsally is the merus's SPINE, which the cage builds (decapod_cage's
    # merus_spine feature). And decapod_cage builds this shell as ONE tube (its first descriptor): a tab standing 2-4
    # mm off that tube past its end is nothing its rings can follow. So the knee is the knuckle, its rolled rim and
    # the membrane's lens (lab v3s). `tongues` stays in arm_descs for a part that needs one.
    # The two DORSAL quadrants' exponent 1.75-2.0 -> 1.4 from s 8 on: at 1.75 the 'keeled back' was an ellipse's and
    # the merus read as a round tapering pipe; at 1.4 its back is a ridge with flat flanks (n04 / c04: the ridge
    # that carries the spines). The half-sizes are unchanged, so the form only LOSES clay on its dorsal shoulders:
    # nothing new can reach P2, the carapace or the folded carpus (lab: gradient p1 0.723, the knee enters 0 points,
    # P2 0.67-0.69 mm clear, as v3r).
    merus=dict(rho=1.65, bow=1.2,
               rows=((0.0, (5.5, 5.5, 7.5, 7.5), (2.4, 2.5, 2.2, 2.2)),
                     (8.0, (5.7, 5.8, 7.8, 8.2), (2.4, 2.5, 1.4, 1.4)),
                     (16.0, (5.9, 6.3, 8.2, 9.0), (2.4, 2.6, 1.4, 1.4)),
                     (22.0, (6.0, 6.8, 8.7, 9.8), (2.4, 2.6, 1.4, 1.4)),
                     (28.0, (6.1, 8.6, 9.4, 10.8), (2.4, 2.6, 1.4, 1.4)),
                     (34.0, (6.3, 10.8, 10.0, 11.8), (2.4, 2.6, 1.4, 1.4)),
                     (38.5, (6.5, 11.8, 10.3, 12.2), (2.4, 2.6, 1.4, 1.4)),
                     (41.5, (6.6, 10.4, 9.6, 11.4), (2.4, 2.5, 1.4, 1.4)),
                     (44.204, (6.6, 8.2, 8.2, 9.6), (2.4, 2.4, 1.4, 1.4)))),
    # A0 v3 (20:36 restart), THE CARPUS: ONE LOFT FROM THE KNEE TO THE WRIST, NO COLLAR, ITS RIM OF BOSSES. v1 / v2 kept
    # X4e's necked tube (r 9.4-10 to W) and unioned a body onto it: the tube showed 8 mm long between the body and the
    # crusher's base as a cylinder collar, and on the flat claw plane its end stood out of both claws (scratch
    # x6fix_x7/org4/arm_lab.py --sect: each claw's base is a KNOB +-7.3 mm thick, the crusher's medial edge 2.2 mm past
    # W, where the tube was +-10: its end showed above, below and medial of the knob).
    # Rows (s, half-sizes, p, offset, TURN): the section's axes turn from the knee's frame (N the fold axis's dorsal
    # end, +B the flexor side) to the WRIST's by s 24 (wrist_turn -37.2 deg: +x world dorsal U = the wrist's hinge
    # axis, +y MEDIAL), so past the turn the four half-sizes read (dorsal, ventral, medial, lateral).
    # WHERE THE CHITIN MAY STAND (arm_lab.py's wrist rows: decapod_cage.joint_margin's own rule on this clay, each
    # claw's propodus swept over the rig's wrist range, -39.1..+43.4 deg from the bind): the crusher's base wall, at
    # its abducted limit a plane through the hinge line ~39 deg back, cuts the LATERAL side at s ~27-29 (r < 16.8 /
    # 15 / 13.8 / 12.5 / 10.8 at s 25 / 26 / 27 / 28 / 29); the cutter's medial edge, adducted, the MEDIAL side at
    # ~36.5; above and below the knobs (|height| > 7.6) nothing sweeps: the dorsal and ventral sides are free to the
    # hinge line (s 40). c04 / c06 / c10 show exactly that: a dorsal NOSE and a ventral lobe over the two condyles,
    # the membrane a crescent between them on the lateral face; c11 from above: the tan lobe on the claw's base.
    # THE FORM, A0 v3b (the 22:02 restart; v3a, the same plan made of five round-cone bosses on a cone, read as a lumpy
    # potato touching the claw at a point): A FIST WITH THE MEMBRANE'S CRESCENTS PRESSED INTO IT. `rows` is the FIST,
    # the taut shell a viewer sees: from the knee's neck (X4e's, at s 0) the EXTENSOR shoulder rises at once; full
    # girth from s 15 to the wrist (widest laterally at s 20-24, c11's lateral corner); its end over the hinge blunt
    # (the dorsal and ventral half-sizes held to W, the medial one falling to 3 mm: the claws' bases stand lateral of
    # the hinge). `lips` says where the fist's SURFACE stays chitin; the rest, a wedge on its lateral-distal face, is
    # cut down to the membrane. WHERE THE CLAWS SWEEP THAT SURFACE (scratch x6fix_x7/org4/probe_sweep.py: the first s
    # each claw's base reaches per (m medial, h dorsal), from the cached swept fields): the crusher's base, swinging
    # back, reaches the lateral flank from s 25.0 / 28.2 / 30.2 / 32.0 at m -16 / -12 / -8 / -5 at mid-height and
    # later toward the top and bottom (m -12: s 30-32 at h +-8, 34-36 at +-10; nothing above h +12, or above +10
    # nearer the hinge than m -8); the cutter's heel sweeps only the fist's inside (s 30-32 at m -8..0, |h| < 7.6)
    # and 3 mm of its medial end (s 37 on). The chitin is the fist inside any of three half-spaces: BEHIND THE WALL
    # (the plane s = wall[0] + wall[1] m, standing on the hinge axis' direction: the sweep's edge less 0.6 mm),
    # ABOVE the radial plane `up` deg from dorsal toward lateral (the dorsal NOSE) and BELOW the one `low` deg from
    # ventral (the ventral LOBE): c04, c06, c10's two lobes over the hinge with the crescent between. The planes
    # meet the fist's surface squarely, so each lip is a blunt rolled rim (k_rim), not a feather edge (a capsule cut
    # met the shoulder at 64 deg: a blade, and its blend halved the field's gradient); the crescent's corners are
    # rounded by k_out. On the fist's curved flank the wall's rim runs forward toward the top and bottom by itself.
    # `rec` (per side: (s, mm) rows) is how far the membrane lies under the fist: the loft the cage reads first
    # (knee_carpus) is the fist less rec: its lateral side a taut sheet 1-3.6 mm under the lips, its top and bottom
    # 0.8 mm (it fills the fist under the lips: no slot a cage column would cross twice), its end at W inside both
    # knobs. The cage finds the chitin's margin by the sweep, as before
    carpus=dict(rho=1.5, wrist_turn=-37.2, shell_k=0.3,
                # the back's line (c04 from the side): a hump over the body (s 15-20), a shallow SADDLE (s 28-34), then
                # the NOSE: one lobe standing 2 mm over the saddle, on over the claw's base (`bosses`: limb_bosses in
                # the wrist's frame, theta 0 dorsal, 90 medial; above the lips' `up` plane, where nothing sweeps)
                rows=((0.0, (7.0, 7.0, 5.9, 5.9), (2.4, 2.4, 2.4, 2.4), (0.0, 0.0), 0.0),
                      (3.0, (7.5, 7.3, 6.0, 8.4), (2.3, 2.4, 2.4, 2.3), (0.0, 0.0), 0.0),
                      (6.0, (8.8, 8.2, 6.3, 11.0), (2.3, 2.4, 2.4, 2.3), (0.0, 0.0), -2.0),
                      (10.0, (11.0, 9.6, 7.0, 13.8), (2.2, 2.3, 2.5, 2.3), (0.0, 0.0), -9.0),
                      (15.0, (12.9, 11.0, 8.4, 16.8), (2.2, 2.3, 2.5, 2.4), (0.0, 0.0), -22.0),
                      (20.0, (13.2, 11.6, 10.0, 19.0), (2.2, 2.2, 2.4, 2.4), (0.0, 0.0), -33.0),
                      (24.0, (12.7, 11.4, 11.0, 19.0), (2.2, 2.0, 2.4, 2.4), (0.0, 0.0), -37.2),
                      (28.0, (12.2, 11.0, 10.7, 17.2), (2.2, 1.8, 2.4, 2.4), (0.0, 0.0), -37.2),
                      (31.0, (12.2, 11.0, 10.0, 15.6), (2.2, 1.8, 2.4, 2.4), (0.0, 0.0), -37.2),
                      (34.0, (12.2, 11.2, 9.0, 13.9), (2.2, 1.9, 2.3, 2.3), (0.0, 0.0), -37.2),
                      (36.5, (12.0, 11.3, 7.6, 12.3), (2.2, 2.0, 2.3, 2.3), (0.0, 0.0), -37.2),
                      (38.5, (11.6, 11.0, 6.0, 10.8), (2.2, 2.1, 2.2, 2.2), (0.0, 0.0), -37.2),
                      (40.103, (11.0, 10.6, 4.6, 9.2), (2.2, 2.2, 2.2, 2.2), (0.0, 0.0), -37.2)),
                rec=dict(dv=((28.0, 0.0), (32.0, 0.8), (40.103, 0.8)),
                         med=((34.0, 0.0), (38.0, 0.8), (40.103, 1.0)),
                         lat=((18.0, 0.0), (22.0, 1.2), (26.0, 2.2), (31.0, 2.8), (36.0, 3.4), (40.103, 3.6))),
                lips=dict(wall=(34.6, 0.636), up=42.0, low=27.0, k_out=4.0, k_rim=1.2),
                bosses=(dict(a=(30.5, -8.0, 8.6, 5.3), b=(37.2, -8.0, 9.3, 4.9), k=2.5, name='nose'),)))
# X2b, the cutter's hidden fingertips (module docstring, CHELAE): the fixed finger's lateral edge fitted by a circle
# over its last visible run (this far back along s from where it meets the crusher's dactyl: 7 points on M1, fit
# residual 0.2 mm); X0b's saw points (c11 px) for its occlusal edge; arc / cap sampling (life mm). X2c: the cap's
# radius rig.cheliped.cutter_cap, fitted to c13's profile (fit_cutter_cap) over cap_bounds (mm)
CUTTER = dict(lat_run=23.0, saw_a=(1102.0, 631.0), saw_b=(1310.0, 800.0), contact=(1082.0, 725.5),
              gape=(1340.0, 855.0), arc_step=0.4, cap_bounds=(0.5, 3.0),
              # X4c: the propodus's base closure (claw_polys): a G1 Bezier's handles, x its chord / 6 (1.5 passes
              # through the crusher's 3-point layout's first point: the upper margin and W's place kept)
              base_handle=1.5)


# ============================================================================================ small helpers
def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def perp(v, x):
    v = np.asarray(v, np.float64)
    return v - x * float(v @ x)


def lipschitz_above(z, v, smax):
    """the least function >= v whose slope along z stays within smax: max_j (v_j - smax |z - z_j|)"""
    z, v = np.asarray(z, np.float64), np.asarray(v, np.float64)
    return np.max(v[None, :] - smax * np.abs(z[:, None] - z[None, :]), axis=1)


def smooth_loop(P, sigma, step=0.25):
    """a closed polygon resampled every `step` and Gaussian-smoothed over sigma (life mm) of its arc"""
    from scipy.ndimage import gaussian_filter1d
    P = np.asarray(P, np.float64)
    L = float(np.sum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)))
    Q = AP.resample_loop(P, max(16, int(np.ceil(L / step))))
    if sigma > 0:
        Q = gaussian_filter1d(Q, sigma / step, axis=0, mode='wrap')
    return Q


def smooth_run(C, sl, sigma):
    """the open run C[sl] of a polyline Gaussian-smoothed over sigma (life mm) of its arc, its two ends held (a claw's
    medial palm edge: its white tubercles' bumps, a feature the clay leaves to the cage and the sculpt)"""
    from scipy.ndimage import gaussian_filter1d
    C = np.asarray(C, np.float64).copy()
    R = C[sl]
    if len(R) < 4:
        return C
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(R, axis=0), axis=1))])
    st = 0.25
    ss = np.arange(0.0, s[-1] + 1e-9, st)
    Q = np.column_stack([np.interp(ss, s, R[:, 0]), np.interp(ss, s, R[:, 1])])
    Qs = gaussian_filter1d(Q, sigma / st, axis=0, mode='nearest')
    w = np.clip(np.minimum(ss, ss[-1] - ss) / (2.0 * sigma), 0.0, 1.0)[:, None]   # the ends held
    Qs = w * Qs + (1.0 - w) * Q
    R2 = np.column_stack([np.interp(s, ss, Qs[:, 0]), np.interp(s, ss, Qs[:, 1])])
    C[sl] = R2
    return C


def ccw(P):
    P = np.asarray(P, np.float64)
    a = np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return P if a > 0 else P[::-1].copy()


def core_of(poly, rho):
    """a polygon's PSWEEP core: its convex corners rounded to rho first, then offset inward by rho"""
    return AP.offset_closed(AP.round_convex(ccw(poly), rho + 0.05), -rho)


def interval_at(P, s):
    """the plan interval (lo, hi) of the closed polygon P (columns s, m) at abscissa s: its crossings' min and max"""
    Q = np.vstack([P, P[:1]])
    a, b = Q[:-1], Q[1:]
    lo, hi = np.minimum(a[:, 0], b[:, 0]), np.maximum(a[:, 0], b[:, 0])
    sel = (s >= lo) & (s <= hi) & (hi > lo)
    if not sel.any():
        return None
    t = (s - a[sel, 0]) / (b[sel, 0] - a[sel, 0])
    m = a[sel, 1] + t * (b[sel, 1] - a[sel, 1])
    return float(m.min()), float(m.max())


# ============================================================================================ M1's outlines
class Outline:
    """M1's c11 tracings (a src_c11_outline_x2.json dict) in L1's frames: plan(px) -> (x, z) life mm (x the creature's
    left, z forward from the orbit; CL = the orbit to the posterior margin), claw(px, kind) -> (s, m) life mm (s along
    the claw's axis from its carpal joint, m toward its dactyl), abd_z(px) -> L1's z for M1's abdominal rows (each
    tergite and the telson stretched onto L1's abdomen.segs: M1's mount telescopes, L1 is Pope's straight length)"""

    def __init__(self, src, spec):
        self.src, self.spec = src, spec
        self.P = {k: np.asarray(v, np.float64) for k, v in src['points'].items()}
        self.poly = {k: np.asarray(v, np.float64) for k, v in src['polylines'].items()}
        self.flags = {k: np.array([c == '1' for c in v]) for k, v in src.get('flags', {}).items()}
        o, p = self.P['orbit_mid'], self.P['cara_post']
        self.o = o
        self.a = (p - o) / np.linalg.norm(p - o)                  # backward along the body
        self.b = np.array([self.a[1], -self.a[0]])                 # image right (the creature's right)
        self.k = spec['body']['CL'] / float(np.linalg.norm(p - o))  # life mm per px
        CL = spec['body']['CL']
        segs = spec['abdomen']['segs']
        rows = ('cara_post', 't1_post', 't2_post', 't3_post', 't4_post', 't5_post', 'telson_base', 'telson_tip')
        # the sweep's abdominal boundaries (src_c11.json, the same image): along-axis px; their L1 z
        sw = dict(cara_post=self.P['cara_post'], telson_base=self.P['telson_base'], telson_tip=self.P['telson_tip'])
        sw.update(t1_post=np.array([1143.0, 2110.0]), t2_post=np.array([1143.0, 2247.0]),
                  t3_post=np.array([1143.0, 2370.0]), t4_post=np.array([1143.0, 2496.0]),
                  t5_post=np.array([1143.0, 2620.0]))
        self.u_rows = np.array([float((sw[r] - o) @ self.a) for r in rows])
        self.z_rows = -CL - np.concatenate([[0.0], np.cumsum(segs)])
        self.claws, self.claws_traced = {}, {}
        for kind, j, tip, dref in (('crusher', 'cr_joint', 'cr_tip', 'cr_tip_inner'),
                                   ('cutter', 'cu_joint', 'cu_tip', 'cu_dactyl_tip')):
            W = self.P[j]
            d = (self.P[tip] - W) / np.linalg.norm(self.P[tip] - W)
            m = np.array([-d[1], d[0]])
            if (self.P[dref] - W) @ m < 0:
                m = -m
            self.claws_traced[kind] = (W, d, m)
            if kind == 'cutter':        # X2b: the axis to the fixed tip continued under the crusher's dactyl
                th = np.radians(spec['rig']['cheliped'].get('cutter_axis', 0.0))
                d, m = np.cos(th) * d + np.sin(th) * m, -np.sin(th) * d + np.cos(th) * m
            self.claws[kind] = (W, d, m)

    def plan(self, X):
        Q = np.asarray(X, np.float64).reshape(-1, 2) - self.o
        return np.column_stack([-(Q @ self.b) * self.k, -(Q @ self.a) * self.k])

    def along(self, X):
        """M1's along-axis px from the orbit (+ backward)"""
        return (np.asarray(X, np.float64).reshape(-1, 2) - self.o) @ self.a

    def abd_z(self, X):
        """L1's z for M1 points on the abdomen and the fan: piecewise linear in M1's rows (extrapolated past the ends
        by the end segments' stretch)"""
        u = self.along(X)
        U, Z = self.u_rows, self.z_rows
        out = np.interp(u, U, Z)
        lo, hi = u < U[0], u > U[-1]
        out[lo] = Z[0] + (u[lo] - U[0]) * (Z[1] - Z[0]) / (U[1] - U[0])
        out[hi] = Z[-1] + (u[hi] - U[-1]) * (Z[-1] - Z[-2]) / (U[-1] - U[-2])
        return out

    def abd_plan(self, X, fx=1.0):
        """(x, z) life mm of M1's abdominal or fan points on L1's abdomen, x scaled by fx"""
        x = self.plan(X)[:, 0] * fx
        return np.column_stack([x, self.abd_z(X)])

    def claw(self, X, kind):
        W, d, m = self.claws[kind]
        Q = np.asarray(X, np.float64).reshape(-1, 2) - W
        return np.column_stack([Q @ d, Q @ m]) * self.k

    def nearest(self, key, pt):
        P = self.poly[key]
        return int(np.argmin(np.linalg.norm(P - np.asarray(pt, np.float64), axis=1)))


# ============================================================================================ primitives
def tube(a, b, ra, rb, across, p=2.4, sink=0.0, n=6, rho_frac=0.3, op=S_.UNION, k=0.0, name=''):
    """a straight segment's shell: a PSWEEP from a (moved `sink` back along the axis, into its parent) to b, its section
    a superellipse (exponent p) of half-sizes (along `across`, made perpendicular to the axis; and across both) going
    linearly from ra at a to rb at b; flat ends rounded by rho (rho_frac of the least half-size)"""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    t = unit(b - a)
    a0 = a - sink * t
    L = float(np.linalg.norm(b - a0))
    u = np.linspace(0.0, 1.0, max(2, n))
    pts = a0[None, :] + u[:, None] * (b - a0)[None, :]
    f = np.clip((u * L - sink) / max(L - sink, 1e-9), 0.0, 1.0)
    ra, rb = np.asarray(ra, np.float64), np.asarray(rb, np.float64)
    hs = ra[None, :] + f[:, None] * (rb - ra)[None, :]
    rho = rho_frac * float(hs.min())
    N = perp(across, t)
    if np.linalg.norm(N) < 1e-6:
        N = perp(UP if abs(t[1]) < 0.9 else np.array([1.0, 0.0, 0.0]), t)
    return AP.psweep(pts, AP.superellipse(48, p), rho, key=0.0, scale=hs - rho, normal=unit(N), op=op, k=k, name=name)


def limb_section(xp, xm, yp, ym, p, off=(0.0, 0.0), m=64):
    """A0, ORGANIC (ARM): one limb section, a closed polygon (m, 2), counter-clockwise from +x: in each quadrant a
    superellipse arc of that quadrant's own exponent between its two half-sizes (x along the section frame's normal N:
    xp toward +N, xm toward -N; y along t x N: yp, ym), so the four sides differ (a flat belly, an arched back, a
    swollen flank); p = (p of +x+y, -x+y, -x-y, +x-y); off moves its centre"""
    a = np.linspace(0.0, 2.0 * np.pi, m, endpoint=False)
    c, s_ = np.cos(a), np.sin(a)
    q = np.where(c >= 0.0, np.where(s_ >= 0.0, 0, 3), np.where(s_ >= 0.0, 1, 2))
    pe = np.asarray(p, np.float64)[q]
    return np.column_stack([np.sign(c) * np.abs(c) ** (2.0 / pe) * np.where(c >= 0.0, xp, xm) + off[0],
                            np.sign(s_) * np.abs(s_) ** (2.0 / pe) * np.where(s_ >= 0.0, yp, ym) + off[1]])


def limb_loft(a, across, t, rows, rho, sink=0.0, bow=0.0, sub=4, m=64, op=S_.UNION, k=0.0, name=''):
    """A0, ORGANIC (ARM): a limb segment's shell as a LOFT of sections that change along it: a PSWEEP on the STRAIGHT
    axis from a along t (X4's cages cast from that axis; a bowed form moves its sections, not its centreline), from
    a - sink t (the rows' first section carried back: the condyle in its parent, tube()'s) to the rows' last station,
    each node its own key section (limb_section: four half-sizes, four exponents), the rows interpolated by PCHIP at
    `sub` nodes per interval (monotone: no overshoot between stations). The stored polygons are each section's CORE
    (its half-sizes less rho), divided by the FIRST node's nominal half-sizes, which ride as the PSWEEP's scale, the
    same at every node (so scale[0] + rho is the start's mean half-size, as tube()'s: decapod_cage reads it).
    A0 v3b: the size rides in the KEYS, not in a per-node scale: the kernel divides the whole field by a BOUND on the
    section's speed that adds the keys' change and the scale's change (sdf.Program.psweep_bound); with both changing
    it divided the v3a carpus by 2.365 (gradient 0.423, x02's gate 1 wants p1 >= 0.6) where its points truly move
    1.09 mm per mm (1.48: 0.674); with one scale the bound is the points' own speed (scratch x6fix_x7/org4/
    loft_speed.py prints both). No decapod program grows or shrinks a loft (emit's scale rule is not used). bow: the sections' centres
    moved this far toward -B (dorsal on the cheliped) in the loft's middle (sin^2 over its length), 0 at its ends.
    The ends are flat, rounded by rho. A row's optional 5th value is its section's TURN (deg about the axis, from N
    toward B; A0 v2): the section's own axes turned, so a segment whose two joints' axes are not parallel (the carpus:
    the knee's fold axis at one end, the wrist's at the other) carries each end's form in that end's frame"""
    from scipy.interpolate import PchipInterpolator
    a, t = np.asarray(a, np.float64), unit(t)
    N = perp(across, t)
    if np.linalg.norm(N) < 1e-6:
        N = perp(UP if abs(t[1]) < 0.9 else np.array([1.0, 0.0, 0.0]), t)
    N = unit(N)
    ss = np.array([r_[0] for r_ in rows], np.float64)
    H = np.array([r_[1] for r_ in rows], np.float64)
    Pq = np.array([r_[2] for r_ in rows], np.float64)
    Of = np.array([r_[3] if len(r_) > 3 else (0.0, 0.0) for r_ in rows], np.float64)
    Tu = np.array([r_[4] if len(r_) > 4 else 0.0 for r_ in rows], np.float64)
    sn = np.unique(np.concatenate([np.linspace(ss[i], ss[i + 1], sub + 1) for i in range(len(ss) - 1)]))
    Hn, Pn, On, Tn = (PchipInterpolator(ss, v_, axis=0)(sn) for v_ in (H, Pq, Of, Tu))
    if bow:
        On[:, 1] -= bow * np.sin(np.pi * (sn - ss[0]) / (ss[-1] - ss[0])) ** 2
    if sink > 0.0:                              # the condyle: the first section carried back into the parent
        sn, Hn, Pn, On, Tn = (np.concatenate([[sn[0] - sink], sn]), np.vstack([Hn[:1], Hn]), np.vstack([Pn[:1], Pn]),
                              np.vstack([On[:1], On]), np.concatenate([Tn[:1], Tn]))
    assert float(Hn.min()) - rho > 0.25, f'{name}: a half-size under rho {rho} (+ 0.25)'
    nom = np.column_stack([0.5 * (Hn[:, 0] + Hn[:, 1]), 0.5 * (Hn[:, 2] + Hn[:, 3])]) - rho

    def turned(i):
        """node i's core polygon, turned by its row's angle (the offset is given in the unturned frame)"""
        q = limb_section(*(Hn[i] - rho), Pn[i], (0.0, 0.0), m)
        c_, s_ = np.cos(np.radians(Tn[i])), np.sin(np.radians(Tn[i]))
        return q @ np.array([[c_, s_], [-s_, c_]]) + On[i][None, :]
    keys = np.stack([turned(i) / nom[0][None, :] for i in range(len(sn))])
    pts = a[None, :] + sn[:, None] * t[None, :]
    return AP.psweep(pts, keys, rho, key=np.arange(len(sn), dtype=np.float64), scale=np.tile(nom[0], (len(sn), 1)),
                     normal=N, op=op, k=k, name=name)


def limb_bosses(K, t, X_, Y_, bosses, name):
    """A0 v3 (ARM): a limb segment's BOSSES: round cones, each given by its two ends (s mm along the axis from K, theta
    deg about the axis from X_ toward Y_, the centre's distance from the axis, the radius), smooth-unioned by its own k
    (life mm): a rim's lobes, a hump, a shoulder. Each stands mostly buried in the segment's loft, on a broad blended
    foot (k), and is an exact distance field (a loft's own flanks are held under ~0.95 mm per mm: a rim that falls
    faster than that is a boss's rounded end, not the loft's)"""
    out = []
    for b_ in bosses:
        ends = []
        for s_, th_, rc_, r_ in (b_['a'], b_['b']):
            c_, sn_ = np.cos(np.radians(th_)), np.sin(np.radians(th_))
            ends.append((K + s_ * t + rc_ * (c_ * X_ + sn_ * Y_), r_))
        out.append(AP.roundcone(ends[0][0], ends[1][0], ends[0][1], ends[1][1], op=S_.UNION, k=b_['k'],
                                name=f'{name} {b_["name"]}'))
    return out


def carpus_core_rows(body):
    """A0 v3b (ARM carpus): the MEMBRANE's rows: the fist's rows, each half-size less its side's `rec` at its station
    (PCHIP through body['rec'][side], 0 before its first station; dv: the dorsal and ventral half-sizes, med, lat):
    the loft under the fist's scoops, down to the small end at W. (The sides are the WRIST's: rec starts where the
    rows' TURN is nearly done.)"""
    from scipy.interpolate import PchipInterpolator

    def at(side, s_):
        r_ = np.asarray(body['rec'][side], np.float64)
        return float(PchipInterpolator(r_[:, 0], r_[:, 1])(s_)) if s_ > r_[0, 0] else 0.0
    out = []
    for r_ in body['rows']:
        s_, (xp, xm, yp, ym) = r_[0], r_[1]
        out.append((s_, (xp - at('dv', s_), xm - at('dv', s_), yp - at('med', s_), ym - at('lat', s_))) + tuple(r_[2:]))
    return tuple(out)


def knee_carpus(I, K, W, merus, ra, rb, across, sc, name, p=2.4, rho_frac=0.3, kn=None, body=None):
    """X4e (KNEE): the carpus's descriptors, [its shell from the neck at K (A0 v3: ONE loft, knee to wrist, ARM carpus;
    body False: X4e's necked tube), the wheel about the knee's fold axis, A0 v3: its bosses], and the wheel's record:
    I, K, W the merus's and carpus's joints, merus the merus's descriptor, ra / rb the old tube's end half-sizes (X2's
    CHEL_R), sc metres per life mm"""
    from scipy.ndimage import gaussian_filter1d
    kn = KNEE if kn is None else kn
    I, K, W = (np.asarray(v, np.float64) for v in (I, K, W))
    am, t = unit(K - I), unit(W - K)
    z = unit(np.cross(am, t))
    y = unit(np.cross(z, am))
    fm = AP.field_mm([merus], sc)
    zs = np.arange(0.0, 14.0, kn['step'])

    def half(sz, sy):
        """the merus's half-width from K + z along sy y, at the z's sz zs, to where its field reads -wall: x6fix_x7
        (11-11), the wall in the merus's OWN distance, not the half-width less `wall` along y. Along y the two agree on
        the flanks; at the wheel's POLES the merus's surface turns across the axis and the old rule left the pole 0.1
        mm short of the axis's exit (z_table 8.20 against 8.30) and the profile's +0.3 and the union's swell put the
        carpus's clay 0.25 mm OUT of the merus there at every knee pose (x04 _a0g gate 9's no-bulge hair, the limit
        0.105 mm out; scratch x6fix_x7 claw/probe_knee_bulge.py, probe_wheel_pole.py)"""
        P0 = K[None, :] + sz * zs[:, None] * z[None, :]
        lo, hi = np.zeros(len(zs)), np.full(len(zs), 30.0)
        ins = fm(P0) < -kn['wall']
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            q = fm(P0 + sy * mid[:, None] * y[None, :]) < -kn['wall']
            lo, hi = np.where(q, mid, lo), np.where(q, hi, mid)
        return np.where(ins, lo, 0.0)
    rho_z = np.min([half(a_, b_) for a_ in (1.0, -1.0) for b_ in (1.0, -1.0)], axis=0)
    n_ = int(np.argmax(rho_z <= 0.0)) if (rho_z <= 0.0).any() else len(zs)
    zp, rp = zs[:n_], gaussian_filter1d(rho_z[:n_], 2.0, mode='nearest')
    rp = np.minimum.accumulate(rp)

    def wheel_profile(grow):
        """the closed (r, y) profile, y along the fold axis, counter-clockwise from the axis at -z over the equator"""
        up = np.column_stack([np.maximum(np.append(rp, 0.0) + grow, 0.0), np.append(zp, zp[-1] + 0.3) + grow])
        return np.vstack([up[::-1] * [1.0, -1.0], up[1:]])
    wheel = AP.revolve(wheel_profile, K, z, op=S_.UNION, k=kn['k'], name=f'{name} wheel')
    # the tube: the neck at K, the old tube's linear section from s_neck on (its rounding rho kept: the wrist unchanged)
    L = float(np.linalg.norm(W - K))
    ra, rb, nk = (np.asarray(v, np.float64) for v in (ra, rb, kn['neck']))
    ss = np.concatenate([np.linspace(0.0, kn['s_neck'], kn['stations'] - 2), [0.5 * (kn['s_neck'] + L), L]])
    f_old = (ss / L)[:, None]
    hs_old = ra[None, :] + f_old * (rb - ra)[None, :]
    w = np.clip(ss / kn['s_neck'], 0.0, 1.0)[:, None]
    w = w * w * (3.0 - 2.0 * w)
    hs = (1.0 - w) * nk[None, :] + w * hs_old
    N = unit(perp(across, t))
    body = ARM.get('carpus') if body is None else body
    if body:        # A0 v3, ORGANIC (ARM carpus): ONE loft from the neck at K to the wrist W (the cage reads this first
        Bn = np.cross(t, N)                     # descriptor as it read the tube: decapod_cage.tube_nodes), then the
        assert float(Bn @ (I - K)) > 0.0, f'{name}: ARM carpus is written with +B the flexor side (toward the merus)'
        assert abs(body['rows'][-1][0] - L) < 0.02, f'{name}: ARM carpus\'s last station is not its length {L:.3f}'
        # the wrist's own frame: X_ world up made perpendicular to the axis (dorsal: the wrist's hinge axis), Y_
        # medial; the rows' TURN column reaches the same frame (wrist_turn deg from N toward B)
        X_ = unit(perp(UP, t))
        Y_ = np.cross(t, X_)
        turn = float(np.degrees(np.arctan2(X_ @ Bn, X_ @ N)))
        assert abs(turn - body['wrist_turn']) < 0.5, \
            f'{name}: the wrist\'s frame is {turn:.1f} deg from the knee\'s (ARM carpus wrist_turn {body["wrist_turn"]})'
        # A0 v3b: FIRST the membrane's loft (the fist less `rec`: what the cage's tube_nodes and condyle read),
        # then the wheel, then the CHITIN as one group: the union of the lips' three half-spaces (each a big box
        # with one face on its plane), intersected with the fist (the lips are the fist's own taut surface, their
        # rims where a plane leaves it; the crescent's floor is the first loft)
        lp, big = body['lips'], 70.0

        def half_space(nrm, d0, nm_, k_=0.0):
            """the big box whose +nrm face is the plane nrm . (p - K) = d0 (life mm): the solid nrm . (p - K) <= d0"""
            nrm = unit(nrm)
            e2 = unit(perp(t if abs(nrm @ t) < 0.9 else X_, nrm))
            return AP.roundbox(K + (d0 - big) * nrm, (big, 2.0 * big, 2.0 * big), 0.0,
                               axes=np.column_stack([nrm, e2, np.cross(nrm, e2)]), op=S_.UNION, k=k_, name=nm_)
        n_w = unit(t - lp['wall'][1] * Y_)       # the wall s = wall[0] + wall[1] m: behind it n_w . p <= wall[0] |n|
        a_u, a_l = np.radians(lp['up']), np.radians(lp['low'])
        chit = [half_space(n_w, lp['wall'][0] / float(np.hypot(1.0, lp['wall'][1])), f'{name} behind the wall'),
                half_space(-(np.sin(a_u) * X_ + np.cos(a_u) * Y_), 0.0, f'{name} nose side', lp['k_out']),
                half_space(-(-np.sin(a_l) * X_ + np.cos(a_l) * Y_), 0.0, f'{name} ventral lobe side', lp['k_out']),
                limb_loft(K, N, t, body['rows'], body['rho'], op=S_.INTERSECT, k=lp['k_rim'], name=f'{name} fist')]
        out = [limb_loft(K, N, t, carpus_core_rows(body), body['rho'], name=name), wheel,
               AP.group(chit, op=S_.UNION, k=body.get('shell_k', 0.0), name=f'{name} shell')]
        out += limb_bosses(K, t, X_, Y_, body.get('bosses', ()), name)
    else:
        rho = rho_frac * float(min(ra.min(), nk.min()))
        pts = K[None, :] + ss[:, None] * t[None, :]
        out = [AP.psweep(pts, AP.superellipse(48, p), rho, key=0.0, scale=hs - rho, normal=N, name=name), wheel]
    return out, dict(K=K, z=z, y=y, z_table=zp, r_table=rp, wall=kn['wall'], neck=kn['neck'])


def tip_on_ground(a, b, ra, rb, across, p=2.4, rho_frac=0.3, ground=0.0):
    """the end point for tube(a, ., ra, rb, across) that puts its rounded end's LOWEST point on y = ground: b moved
    back along the axis (its direction kept) by the end's reach below b over the axis's fall. The reach is the end
    section's (rb less tube's rounding rho, a superellipse across the axis) support straight down, plus rho"""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    t = unit(b - a)
    if t[1] > -0.2:                                     # not pointing down (no tip on the ground): unchanged
        return b
    N = perp(across, t)
    if np.linalg.norm(N) < 1e-6:
        N = perp(UP if abs(t[1]) < 0.9 else np.array([1.0, 0.0, 0.0]), t)
    N = unit(N)
    Bn = np.cross(t, N)                                 # the section's second axis (tube's: across both)
    rho = rho_frac * float(min(np.min(ra), np.min(rb)))
    sec = AP.superellipse(48, p) * (np.asarray(rb, np.float64) - rho)
    reach = float((sec @ np.array([-N[1], -Bn[1]])).max()) + rho
    return b - t * ((reach - (b[1] - ground)) / -t[1])


def slab(origin, d, n, poly_sm, half_t, rho, op=S_.UNION, k=0.0, name=''):
    """a PLAN SLAB: the closed plan polygon poly_sm (columns s along d, m along n, life mm from origin) swept straight
    across its plane (along t = d x n) from -half_t to +half_t: an exact extrusion, its edges rounded by rho"""
    d, n = unit(d), unit(n)
    t = np.cross(d, n)
    sec = np.column_stack([poly_sm[:, 1], -poly_sm[:, 0]])     # the section's x along n (m), y along t x n = -d (-s)
    pts = np.array([origin - half_t * t, origin + half_t * t])
    return AP.psweep(pts, core_of(sec, rho), rho, key=0.0, scale=1.0, normal=n, op=op, k=k, name=name)


def envelope(origin, d, n, s, lo, hi, th, rho, p_m=2.2, p_t=2.0, slope=0.6, pad=2.0, m_pts=48, op=S_.INTERSECT, k=0.0,
             name=''):
    """a THICKNESS ENVELOPE: a loft along d (straight, from origin) of lens sections across the plane (x along n, y
    along t = d x n): at each station s its plan reach covers [lo - pad, hi + pad] (each side held to `slope` along s:
    lipschitz_above), its half-thickness th; a superellipse (p_m across the plan, p_t through the thickness). pad: a
    number, or (pad_lo, pad_hi) per station (A0, x6fix_x7: a claw's outer margins closed round on the plan, CLAW round).
    p_m: a number, or (p_lo, p_hi) per station (A0c, 11-11: EACH MARGIN'S OWN EXPONENT, plan_solid): the section's
    lower half (toward -n) a superellipse of p_lo, its upper half of p_hi, about the same centre and half-width, so
    they meet at the thickness's poles with a level tangent"""
    s, lo, hi, th = (np.asarray(v, np.float64) for v in (s, lo, hi, th))
    pad_lo, pad_hi = (pad, pad) if np.ndim(pad) == 0 else (np.asarray(pad[0], np.float64), np.asarray(pad[1], np.float64))
    hi_e = lipschitz_above(s, hi + pad_hi, slope)
    lo_e = -lipschitz_above(s, -(lo - pad_lo), slope)
    mc, we = 0.5 * (hi_e + lo_e), 0.5 * (hi_e - lo_e)
    ang = np.linspace(0.0, 2.0 * np.pi, m_pts, endpoint=False)
    c, sn = np.cos(ang), np.sin(ang)
    if np.ndim(p_m) == 0:
        unit_se = np.column_stack([np.sign(c) * np.abs(c) ** (2.0 / p_m), np.sign(sn) * np.abs(sn) ** (2.0 / p_t)])
        keys = np.stack([unit_se * [we[i] - rho, th[i] - rho] + [mc[i], 0.0] for i in range(len(s))])
    else:
        p_lo, p_hi = (np.asarray(v, np.float64) for v in p_m)
        y1 = np.sign(sn) * np.abs(sn) ** (2.0 / p_t)
        keys = np.stack([np.column_stack([np.where(c >= 0.0, np.abs(c) ** (2.0 / p_hi[i]), -np.abs(c) ** (2.0 / p_lo[i]))
                                          * (we[i] - rho) + mc[i], y1 * (th[i] - rho)]) for i in range(len(s))])
    pts = np.asarray(origin, np.float64)[None, :] + s[:, None] * unit(d)[None, :]
    return AP.psweep(pts, keys, rho, key=np.arange(len(s), dtype=np.float64), scale=1.0, normal=unit(n), op=op, k=k,
                     name=name)


def plan_solid(origin, d, n, poly, th_fn, length, half_t_max, name, s_pad=(4.0, 3.0), pads=None, p_m=None):
    """a part whose plan is the polygon poly (s, m) and whose thickness follows th_fn(s / length) (half, life mm): the
    plan slab smoothly intersected with the thickness envelope (module docstring, CHELAE); the thickness softened along
    s over CLAW['env_soften'] (a profile with corners printed bands across the palm, x02's first run). pads: None (the
    envelope's reach the plan's + CLAW env_pad on both sides) or (pad_lo(s), pad_hi(s)) callables (A0: claw_pads);
    p_m: the envelope's exponent across the plan (None: CLAW p_m). A0c (11-11): WITH pads, p_m is the ROUND margins'
    exponent only: per station each margin's exponent follows its own roundness (1 - pad / env_pad), from CLAW p_m
    where its pad is env_pad (a kept margin: the biting edges, the socket, the bases) to p_m where it is round_pad.
    A0 had given the whole part p_m on both margins, so the regions X4d-X4h's cages were tuned on changed with the
    outer margins: at the dactyl's base, where BOTH pads are env_pad, the exponent alone (2.2 -> 2.0) moved
    decapod_cage.occlusal_rims' sharpest turn, the band's middle columns stood 7.2-8.3 mm apart over rings 0-2
    (X4h: 3.9-4.2) and x04 failed gates 2 and 3 there (3 quads tilted 61 deg, the membrane's aspect 4.90)"""
    from scipy.ndimage import gaussian_filter1d
    s0, s1 = float(poly[:, 0].min()) - s_pad[0], float(poly[:, 0].max()) + s_pad[1]
    ss = np.linspace(s0, s1, max(24, int(np.ceil((s1 - s0) / CLAW['env_step'])) + 1))
    lo, hi = [], []
    for s in ss:
        iv = interval_at(poly, float(np.clip(s, poly[:, 0].min() + 1e-6, poly[:, 0].max() - 1e-6)))
        lo.append(iv[0])
        hi.append(iv[1])
    th = np.array([th_fn(s / length) for s in ss])
    th = gaussian_filter1d(th, CLAW['env_soften'] / (ss[1] - ss[0]), mode='nearest')
    poly_sl = poly if pads is None else grow_round(poly, pads, CLAW['round_slab'])      # A0: the slab clear of the round
    sl = slab(origin, d, n, poly_sl, half_t_max, CLAW['slab_rho'], name=f'{name} plan')  # margins (grow_round)
    pd = CLAW['env_pad'] if pads is None else (np.array([pads[0](s) for s in ss]), np.array([pads[1](s) for s in ss]))
    pm = CLAW['p_m'] if p_m is None else p_m
    if pads is not None and p_m is not None:            # A0c: each margin's own exponent (the docstring)
        pm = tuple(CLAW['p_m'] + (p_m - CLAW['p_m']) * np.clip(1.0 - q / CLAW['env_pad'], 0.0, 1.0) for q in pd)
    en = envelope(origin, d, n, ss, np.array(lo), np.array(hi), th, CLAW['env_rho'],
                  p_m=pm, p_t=CLAW['p_t'],
                  slope=CLAW['env_slope'], pad=pd, m_pts=CLAW['env_pts'], op=S_.INTERSECT, k=CLAW['k'],
                  name=f'{name} envelope')
    return AP.group([sl, en], name=name)


# ============================================================================================ the carapace
def carapace_lines(spec, chain, O):
    """the carapace's measured lines (module docstring): dict(top, depth, half (callables of z, life mm), z range,
    the margin's and the bottom's heights, the cervical station)"""
    b, lv, CL = spec['body'], chain['lv'], spec['body']['CL']
    lm = lv['lm']
    keys = ('post_top', 'deep_top', 'cervical', 'orbit', 'front_top')
    zt = np.array([lm[k_][0] for k_ in keys])
    ht = np.array([lm[k_][1] for k_ in keys])
    top = AP.pchip(zt, ht)
    zc = np.array([p_[0] for p_ in C20_DEPTH]) * CL
    dc = np.array([p_[1] for p_ in C20_DEPTH]) * CL * (b['cara_depth'] / (C20_DEEP * CL))
    zz = np.arange(CARA['z_back'] - 2.0, CARA['z_front'] + 6.0, 0.25)
    dd = lipschitz_above(zz, np.interp(zz, zc, dc), CARA['slope'])
    depth = lambda z: np.interp(z, zz, dd)                                     # noqa: E731
    Lp, Rp = O.plan(O.poly['cara_left']), O.plan(O.poly['cara_right'])
    zl, xl = Lp[:, 1], Lp[:, 0]
    zr, xr = Rp[:, 1], -Rp[:, 0]
    zw = np.arange(CARA['z_back'] - 2.0, CARA['z_front'] + 3.0, 0.5)
    w = 0.5 * (np.interp(zw, zl[::-1], xl[::-1]) + np.interp(zw, zr[::-1], xr[::-1]))
    w = AP.smooth_rows(zw, w, 2.0)
    w = AP.lipschitz_below(zw, w, CARA['slope'])
    half = lambda z: np.interp(z, zw, w)                                       # noqa: E731
    return dict(top=top, depth=depth, half=half, z=(CARA['z_back'], CARA['z_front']), cervical=-b['cervical'],
                deepest=b['deepest_z'])


def bottom_rise(z, depth):
    """the carapace's bottom arch over the body at z (life mm): CARA['rise'] of the depth, capped, faded out toward
    the front (CARA['rise_fade'], a smoothstep)"""
    z0, z1 = CARA['rise_fade']
    f = float(np.clip((z1 - z) / (z1 - z0), 0.0, 1.0))
    return min(CARA['rise_max'], CARA['rise'] * depth) * f * f * (3.0 - 2.0 * f)


def cara_section(T, B, W, rho, rise, n=(26, 12, 16)):
    """the carapace's CORE section (counter-clockwise, x across, y up) at the top T, margin B, half-width W, its bottom
    arched `rise` over the margins (module docstring): the dorsal arch to the widest point, the side down to the free
    margin's lip, the bottom arch"""
    Hw = B + CARA['hw_frac'] * (T - B)
    Wm = W * (1.0 - CARA['margin_in'])
    T_, B_, W_, Wm_ = T - rho, B + rho, W - rho, Wm - rho
    t = np.linspace(0.0, 0.5 * np.pi, n[0] + 1)
    arc = np.column_stack([W_ * np.sin(t) ** (2.0 / 2.3), Hw + (T_ - Hw) * np.cos(t)])
    s = np.linspace(0.0, 1.0, n[1] + 1)[1:]
    side = np.column_stack([Wm_ + (W_ - Wm_) * (1.0 - s ** 2), Hw - (Hw - B_) * s])
    v = np.linspace(0.0, 1.0, n[2] + 1)[1:]
    bot = np.column_stack([Wm_ * (1.0 - v), B_ + rise * (1.0 - (1.0 - v) ** 2)])
    return AP.closed_from_half(np.vstack([arc, side, bot]))


def carapace_descs(spec, chain, O):
    """the carapace (a loft) and the rostrum's blade (a loft), one shell: [carapace, rostrum (union, k)]"""
    L = carapace_lines(spec, chain, O)
    rho = CARA['rho']
    z0, z1 = CARA['z_back'] + rho, CARA['z_front']
    zs = np.linspace(z0, z1, int(np.ceil((z1 - z0) / CARA['step'])) + 1)
    y0 = 60.0
    cores = np.stack([cara_section(float(L['top'](z)), float(L['top'](z) - L['depth'](z)), float(L['half'](z)), rho,
                                   bottom_rise(z, float(L['depth'](z)))) for z in zs])
    cara = AP.loft_sections(zs, cores, rho, y0, name='carapace', dense=0.5, soften=1.0,
                            n_nodes=int((z1 - z0) / 0.4) + 1)
    # the rostrum: M1's traced width (c11 rostrum_left / _right) from the orbit to its tip, lens sections, its top
    # through c06's front_top (the dorsal outline at z +17.4), its base buried in the carapace's front
    lv, b = chain['lv'], spec['body']
    Lr, Rr = O.plan(O.poly['rostrum_left']), O.plan(O.poly['rostrum_right'])
    zr = np.concatenate([Lr[:, 1], Rr[:, 1]])
    wr = np.concatenate([Lr[:, 0], -Rr[:, 0]])
    o_ = np.argsort(zr)
    zr, wr = zr[o_], wr[o_]
    tip = b['rostrum']
    rr = ROSTRUM['rho']
    zq = np.linspace(ROSTRUM['z_base'], tip - rr, 28)
    wq = np.maximum(np.interp(zq, zr, wr, left=wr[0]), rr + 0.12)
    wq = np.where(zq < zr[0], wr[0] + (zr[0] - zq) * 0.15, wq)                  # widening into the carapace's front
    tq = ROSTRUM['t_frac'] * wq + ROSTRUM['t_add']
    zf, hf = lv['lm']['front_top']
    h0 = lv['lm']['orbit'][1]                       # its keel continues the carapace's midline at the orbit
    top = np.interp(zq, [0.0, zf], [h0, hf])        # (np.interp holds the ends: level behind z 0 and past front_top)
    yc = top - tq
    lens = AP.superellipse(32, 1.8)
    rcores = np.stack([lens * [wq[i] - rr, tq[i] - rr] + [0.0, yc[i]] for i in range(len(zq))])
    rost = AP.loft_sections(zq, rcores, rr, float(np.mean(yc)), name='rostrum', op=S_.UNION, k=ROSTRUM['k'],
                            dense=0.25, soften=0.5, n_nodes=110)
    return [cara, rost], L


def thorax_desc(spec, chain, L):
    """the ventral thorax (the sternal plastron and the coxal frames): a loft under the carapace between the coxae,
    its top in the carapace's bottom arch (an overlap), its bottom THORAX['below'] under the coxae's articulations"""
    lv = chain['lv']
    T = THORAX
    zs = np.linspace(T['z_back'] + T['rho'], T['z_front'], 40)
    y_bot = lv['y_cox'] - T['below']
    cores = []
    for z in zs:
        tp = float(L['top'](z) - L['depth'](z))
        top = tp + bottom_rise(z, float(L['depth'](z))) + T['into']
        bot = y_bot + max(0.0, (z + 22.0) * 0.6)            # the mouth field rising toward the carapace's front
        bot = min(bot, top - 6.0)
        f = float(np.clip((z - T['front_z'][0]) / (T['front_z'][1] - T['front_z'][0]), 0.0, 1.0))
        hw = T['half'] + (T['half_front'] - T['half']) * f * f * (3.0 - 2.0 * f) - T['rho']
        half = AP.section_half(top - T['rho'], 0.5 * (top + bot), bot + T['rho'], hw, p_top=3.0, q_top=3.0,
                               p_bot=3.0, q_bot=3.0, m=40)
        cores.append(AP.closed_from_half(half))
    return AP.loft_sections(zs, np.stack(cores), T['rho'], float(y_bot + 10.0), name='ventral_thorax', dense=0.5,
                            soften=1.0, n_nodes=200)


# ============================================================================================ the abdomen
def tergite_section(T, D, W, rho, inset=0.0, lobe=0.0, n=(22, 12, 6, 8, 4, 10)):
    """a tergite's CORE section (counter-clockwise): the dorsal arch to the shoulder, the pleuron's outer face down to
    its tip at W (`lobe` mm deeper than D: the pleuron's bowed lower margin), the inner face up to the tergite's floor
    (ABD['floor'] of the depth; X2c: no longer the sternite's level), across under the somite (module docstring,
    TERGITES)"""
    A = ABD
    T, D, W = T - inset, D - 2.0 * inset, W - inset
    T_ = T - rho
    Hs = T - A['shoulder'] * D
    Ws = W - A['flare'] - rho
    Wt = W - rho
    Yt = T - D - lobe + rho
    Wi = W - A['pleuron_t'] + rho
    Sb = T - A['floor'] * D + rho
    t = np.linspace(0.0, 0.5 * np.pi, n[0] + 1)
    arc = np.column_stack([Ws * np.sin(t) ** (2.0 / 2.4), Hs + (T_ - Hs) * np.cos(t)])
    # the pleuron's outer face: flaring from the shoulder to its full width by the floor's level, then hanging
    # straight to its tip (the core's pleuron then keeps pleuron_t - 2 rho everywhere, whatever the lobe)
    n_f = n[1] // 2 + 1
    s = np.linspace(0.0, 1.0, n_f + 1)[1:]
    flare = np.column_stack([Ws + (Wt - Ws) * s ** 0.7, Hs - (Hs - Sb) * s])
    s = np.linspace(0.0, 1.0, n[1] - n_f + 1)[1:]
    outer = np.vstack([flare, np.column_stack([np.full(len(s), Wt), Sb - (Sb - (Yt + 0.8)) * s])])
    a = np.linspace(0.0, np.pi, n[2] + 1)[1:-1]
    rt = 0.5 * (Wt - Wi)
    tipc = np.array([0.5 * (Wt + Wi), Yt + 0.8])
    tip = np.column_stack([tipc[0] + rt * np.cos(a), tipc[1] - 0.8 * np.sin(a)])
    s = np.linspace(0.0, 1.0, n[3] + 1)
    inner = np.column_stack([np.full(len(s), Wi), (Yt + 0.8) + (Sb - 0.6 - (Yt + 0.8)) * s])
    c = np.array([[Wi - 0.4, Sb - 0.1], [Wi - 1.0, Sb]])
    v = np.linspace(0.0, 1.0, n[5] + 1)[1:]
    bot = np.column_stack([(Wi - 1.0) * (1.0 - v), np.full(len(v), Sb)])
    return AP.closed_from_half(np.vstack([arc, outer, tip, inner, c, bot]))


def flange_section(T, W, D, rho, thick=3.2, n=24):
    """a flange's CORE: the dorsal arch alone, a crescent thick `thick` from the top to the shoulder"""
    Hs = T - ABD['shoulder'] * D
    Ws = W - ABD['flare']
    t = np.linspace(0.0, 0.5 * np.pi, n + 1)
    outer = np.column_stack([(Ws - rho) * np.sin(t) ** (2.0 / 2.4), Hs + (T - rho - Hs) * np.cos(t)])
    inner = np.column_stack([(Ws - thick + rho) * np.sin(t[::-1]) ** (2.0 / 2.4),
                             (Hs + 0.5) + (T - thick + rho - Hs - 0.5) * np.cos(t[::-1])])
    return AP.closed_from_half(np.vstack([outer, inner[1:]]))


def abdomen_widths(spec, O):
    """M1's pleura half-width (the mean of its two traced sides) as a callable of L1's z, smoothed"""
    zs, ws = [], []
    for key, sg in (('abd_left', 1.0), ('abd_right', -1.0)):
        P = O.abd_plan(O.poly[key])
        zs.append(P[:, 1])
        ws.append(sg * P[:, 0])
    zq = np.arange(-260.0, -90.0, 0.25)
    w = []
    for z, x in zip(zs, ws):
        o_ = np.argsort(z)
        w.append(np.interp(zq, z[o_], x[o_]))
    wq = AP.smooth_rows(zq, 0.5 * (w[0] + w[1]), ABD['smooth'])
    return lambda z: np.interp(z, zq, wq)                                      # noqa: E731


def abdomen_levels(spec, chain):
    """per somite k (1..6): its front z, back z, depth D, top T at the bind"""
    ab, lv, CL = spec['abdomen'], chain['lv'], spec['body']['CL']
    z = -CL - np.concatenate([[0.0], np.cumsum(ab['segs'])])
    out = []
    for k in range(6):
        D = ABD['depth'][k] * ab['d2']
        out.append(dict(k=k + 1, z_front=float(z[k]), z_back=float(z[k + 1]), D=D,
                        T=lv['y_abd'] + spec['rig']['abd_hinge'] * D, seg=float(ab['segs'][k])))
    return out, float(z[6]), float(z[7])


def pleuron_depths(S, zs):
    """somite S's pleuron margin, its depth below the somite's top at the stations zs (life mm; TONGUE, X2b): the
    front corner a quarter ellipse up to the front face, the margin then descending to the somite's full depth S['D']
    at the back (the tooth's level), the whole held to TONGUE['slope'] along z. X2c: the front rises the full
    TONGUE['front'] of the depth, guarded only by the section (plate_min under the tergite's floor)"""
    D, seg, T = S['D'], S['seg'], TONGUE
    # from the tergite loft's front face (X2c: the loft's first section stands ABD rho behind the somite's front, its
    # end rounded over that rho; an ellipse starting at the somite's front had already fallen most of the way there,
    # so the face showed 0.16 of the depth of the designed rise)
    Ll = seg - 2.0 * ABD['rho']                                                # the loft's own length
    x = np.clip(S['z_front'] - ABD['rho'] - np.asarray(zs, np.float64), 0.0, Ll)
    d_front = max(D * (1.0 - T['front']), ABD['floor'] * D + T['plate_min'])
    d_mid, xc = D * (1.0 - T['fall']), T['corner'] * seg
    out = np.where(x < xc, d_front + (d_mid - d_front) * np.sqrt(np.clip(1.0 - (1.0 - x / xc) ** 2, 0.0, 1.0)),
                   d_mid + (D - d_mid) * np.clip((x - xc) / (Ll - xc), 0.0, 1.0) ** 2)
    return AP.lipschitz_below(x, out, T['slope'])


def tergite_descs(spec, chain, O, k, Lc):
    """somite k's tergite: [the loft, its teeth (T2-T5), its flange] (module docstring); Lc the carapace's lines (T1's
    flange)"""
    lev, _, _ = abdomen_levels(spec, chain)
    S = lev[k - 1]
    wfn = abdomen_widths(spec, O)
    rho = ABD['rho']
    z0, z1 = S['z_back'] + rho, S['z_front'] - rho
    zs = np.linspace(z0, z1, max(8, int(np.ceil((z1 - z0) / ABD['step'])) + 1))
    W = wfn(zs)
    if k == 6:                  # T6 narrows behind M1's last traced row (the fan's margin covers it) to the telson's base
        W = np.minimum(W, np.interp(zs, [z0, z0 + 0.45 * (z1 - z0)], [0.72 * float(W[-1]), float(W[-1])]))
    W = AP.lipschitz_below(zs, W, ABD['slope'])
    lobe = pleuron_depths(S, zs) - S['D']          # X2b: the tongue (the section's lobe: mm deeper than D, here <= 0)
    cores = np.stack([tergite_section(S['T'], S['D'], float(W[i]), rho, lobe=float(lobe[i])) for i in range(len(zs))])
    body = AP.loft_sections(zs, cores, rho, S['T'] - S['D'] / 2.0, name=f'abd_{k}', dense=0.4, soften=0.8,
                            n_nodes=max(60, int((z1 - z0) / 0.3)))
    teeth = []
    if k in TONGUE['teeth']:    # the backward tooth at each pleuron's posterior-ventral corner, mid its thickness
        ra, rb = TONGUE['tooth_r']
        xt = float(W[0]) - 0.5 * ABD['pleuron_t']
        ym = S['T'] - S['D']                         # the margin's underside at the back
        for sg in (1.0, -1.0):
            teeth.append(AP.roundcone([sg * xt, ym + ra + 0.25, S['z_back'] + TONGUE['tooth_in']],
                                      [sg * xt, ym - TONGUE['tooth_dip'] + rb, S['z_back'] - TONGUE['tooth_out']],
                                      ra, rb, op=S_.UNION, k=TONGUE['tooth_k'], name=f'abd_{k} tooth'))
    # the flange: forward under the previous tergite's hind margin (T1: under the carapace's)
    if k == 1:
        Tp = float(Lc['top'](S['z_front'] + 2.0))
        Wp = float(Lc['half'](S['z_front'] + 2.0)) * (1.0 - CARA['margin_in'])
        Dp = float(Lc['depth'](S['z_front'] + 2.0))
    else:
        P_ = lev[k - 2]
        Tp, Dp = P_['T'], P_['D']
        Wp = float(wfn(S['z_front'] + 2.0))
    Tf = min(S['T'], Tp) - ABD['inset']
    Wf = min(float(W[-1]), Wp) - ABD['inset']
    Df = min(S['D'], Dp)
    ov = ABD['flange'] * S['seg']
    zf = np.linspace(S['z_front'] - 1.0, S['z_front'] + ov, 8)
    fl_core = flange_section(Tf, Wf, Df, 0.8)
    fl = AP.loft_sections(zf, np.stack([fl_core] * len(zf)), 0.8, Tf - 4.0, name=f'abd_{k} flange', dense=0.0,
                          soften=0.0, n_nodes=24)
    return [body] + teeth + [fl], S, W


def floor_level(S):
    """somite S's tergite floor (its core's underside between the pleura), y life mm at the bind (X2c: ABD['floor'])"""
    return S['T'] - ABD['floor'] * S['D']


def sternite_desc(S, W):
    """somite k's sternite: a rounded box between the pleura, its top lapping ABD['stern_lap'] into the tergite's
    floor, its underside ABD['stern'] of the depth below the somite's top (X2c: from the floor down to the pleura's
    depth at their back, so its side face shows in the notches between the tongues as c04 / c10 show the sternal band,
    and no notch sees through to the far side's; X2's was a 2.5 mm plate on the floor's level, its underside hidden),
    ABD['slot'] mm inside the pleura's inner faces (pleopods 2-5 lie forward in that slot, PLEO_FOLD), the somite's
    whole length (X2c: abutting its neighbours as the tergites do; X2 left 1.2 mm between them, the membrane strip the
    clay does not carry, which the notches now look into)"""
    Sb = S['T'] - ABD['stern'] * S['D']
    top = floor_level(S) + ABD['stern_lap']
    zc = 0.5 * (S['z_front'] + S['z_back'])
    hw = float(np.min(W)) - ABD['pleuron_t'] - ABD['slot']
    hl = 0.5 * (S['z_front'] - S['z_back'])
    ht = 0.5 * (top - Sb)
    return AP.roundbox([0.0, Sb + ht, zc], [hw, ht, hl], min(1.0, ht - 0.05), name=f'sternite_{S["k"]}')


def fan_polys(O, spec):
    """M1's telson, left endopod and left exopod (split at the diaeresis) plans on L1's abdomen, (x, z) life mm"""
    fx = spec['abdomen']['fan_spread'] / (O.k * float(np.linalg.norm(O.P['fan_R'] - O.P['fan_L'])))
    tl, tr = O.poly['telson_left'], O.poly['telson_right']
    tel_px = np.vstack([tl, tr[-2::-1]])
    fan = O.poly['fan_left']
    i_ex = O.nearest('fan_left', (990.0, 2845.5))
    i_en = O.nearest('fan_left', (1077.0, 2844.5))
    exo_px = np.vstack([fan[:i_ex + 1], [[992.0, 2780.0], [998.0, 2700.0]]])
    endo_px = np.vstack([fan[i_ex:i_en + 1], [[1078.0, 2800.0], [1068.0, 2760.0], [1060.0, 2728.0], [1045.0, 2700.0],
                                              [1020.0, 2682.0], [1000.0, 2700.0], [992.0, 2780.0]]])
    f = lambda X: O.abd_plan(X, fx)                                             # noqa: E731
    return dict(telson=f(tel_px), endo=f(endo_px), exo=f(exo_px), diaeresis=f(np.array(FAN['diaeresis'])), fx=fx)


def fan_descs(spec, chain, O):
    """the telson, the left endopod, exopod and exopod past the diaeresis, and the left protopod (module docstring)"""
    lev, z_tel, z_tip = abdomen_levels(spec, chain)
    T6 = lev[5]
    y_fan = T6['T'] - 1.0 - FAN['half_t']
    F = fan_polys(O, spec)
    up = UP
    ez = np.array([0.0, 0.0, 1.0])
    ex = np.array([1.0, 0.0, 0.0])

    def flat(poly_xz, y, half_t, rho, name, op=S_.UNION, k=0.0):
        # the plan (x, z) as (s, m) with s along +z and m along +x, about its centroid (the slab's culling box is its
        # reach round that point): slab across y
        c = poly_xz.mean(0)
        P = np.column_stack([poly_xz[:, 1] - c[1], poly_xz[:, 0] - c[0]])
        return slab(np.array([c[0], y, c[1]]), ez, ex, smooth_loop(P, FAN['smooth']), half_t, rho, op=op, k=k,
                    name=name)
    out = {}
    out['telson'] = [flat(F['telson'], y_fan, FAN['half_t'], FAN['rho'], 'telson')]
    out['uropod_endo_L'] = [flat(F['endo'], y_fan - FAN['endo_drop'], FAN['endo_half_t'], 0.8, 'endopod')]
    ex_poly = F['exo']
    a, b = F['diaeresis']
    nrm = unit(np.array([-(b - a)[1], (b - a)[0]]))                   # in (x, z): toward the distal side?
    cen = 0.5 * (a + b)
    if (ex_poly.mean(0) - cen) @ nrm > 0:                              # the exopod's bulk (proximal) on +nrm: flip
        nrm = -nrm
    yex = y_fan - FAN['exo_drop']
    big = 200.0
    R3 = np.column_stack([[nrm[0], 0.0, nrm[1]], [0.0, 1.0, 0.0], [-nrm[1], 0.0, nrm[0]]])   # columns: nrm, up, along
    c3 = np.array([cen[0], yex, cen[1]])
    distal_box = AP.roundbox(c3 + big * np.array([nrm[0], 0.0, nrm[1]]), [big, 20.0, big], 0.0, axes=R3,
                             op=S_.INTERSECT, name='diaeresis (distal side)')
    proximal_box = AP.roundbox(c3 - big * np.array([nrm[0], 0.0, nrm[1]]), [big, 20.0, big], 0.0, axes=R3,
                               op=S_.INTERSECT, name='diaeresis (proximal side)')
    slab_ex = flat(ex_poly, yex, FAN['exo_half_t'], 0.85, 'exopod plan')
    out['uropod_exo_L'] = [AP.group([slab_ex, dict(proximal_box)], name='exopod')]
    out['uropod_exo_dist_L'] = [AP.group([dict(slab_ex), dict(distal_box)], name='exopod past the diaeresis')]
    P = chain['pos']
    pa = np.array([P['uropod_L'][0], T6['T'] - 0.45 * T6['D'], z_tel + 3.0])
    pb = np.array([P['uropod_end_L'][0] + 2.0, y_fan - 1.0, z_tel - 4.0])
    out['uropod_L'] = [tube(pa, pb, *HEAD_R['protopod'], across=UP, name='protopod')]
    return out, dict(y_fan=y_fan, polys=F, z_tel=z_tel, z_tip=z_tip)


# ============================================================================================ the chelae
def fit_circle(P):
    """the least-squares circle through the points P (n, 2), Kasa's algebraic fit: (centre, radius, max residual)"""
    P = np.asarray(P, np.float64)
    A = np.column_stack([2.0 * P[:, 0], 2.0 * P[:, 1], np.ones(len(P))])
    x = np.linalg.lstsq(A, (P ** 2).sum(1), rcond=None)[0]
    c = x[:2]
    R = float(np.sqrt(x[2] + c @ c))
    return c, R, float(np.max(np.abs(np.linalg.norm(P - c, axis=1) - R)))


def arc_pts(c, R, a0, a1, step=None):
    """the circle (c, R) from angle a0 to angle a1 (radians; the sign of a1 - a0 is the way round), every `step` mm"""
    step = CUTTER['arc_step'] if step is None else step
    n = max(2, int(np.ceil(abs(a1 - a0) * R / step)) + 1)
    a = np.linspace(a0, a1, n)
    return np.asarray(c, np.float64)[None, :] + R * np.column_stack([np.cos(a), np.sin(a)])


def angle_of(v):
    return float(np.arctan2(v[1], v[0]))


def cutter_fixed_tip(O, C=None, r=None):
    """the cutter's FIXED FINGER past the crusher's dactyl (module docstring, CHELAE; X2b), in the cutter's claw frame
    (Outline.claw, the wrist at the origin): dict(lat_idx (the outline indices of the fitted lateral run, from where
    the crusher's dactyl covers it back CUTTER['lat_run'] mm), c0, R, resid (the circle and its fit), sa, sb, e (the
    saw line, tipward), nu (its normal into the finger), r (the cap: rig.cheliped.cutter_cap, X2c; X2b's fillet was
    c13's fixed tip width / 2, x2.c13.tip_palm x the palm; `r` given overrides both), cf (its centre), t_arc, t_line
    (its tangent points), tip (its far point from the wrist), L (that distance: chela.cutter_len's rule), axis (the
    tip's angle off the frame's axis, deg: 0 once the frame is turned by rig.cheliped.cutter_axis) and u_tip (the
    finger's own axis at the tip: the bisector of the arc's and the saw line's tipward tangents at the cap))"""
    spec = O.spec
    key = 'cutter_outline'
    C = O.claw(O.poly[key], 'cutter') if C is None else C
    i_t = O.nearest(key, O.P['cu_tip'])
    lat = [i_t + 1]
    while lat[-1] + 1 < len(C) and C[lat[-1] + 1, 0] >= C[i_t + 1, 0] - CUTTER['lat_run']:
        lat.append(lat[-1] + 1)
    c0, R, resid = fit_circle(C[lat])
    sa = O.claw(np.array([CUTTER['saw_a']]), 'cutter')[0]
    sb = O.claw(np.array([CUTTER['saw_b']]), 'cutter')[0]
    e = unit(sa - sb)
    nu = np.array([e[1], -e[0]])
    if nu[1] > 0.0:                                     # into the fixed finger: its lateral side (- m)
        nu = -nu
    if r is None:
        rc = spec['rig']['cheliped']
        r = rc['cutter_cap'] if 'cutter_cap' in rc else 0.5 * spec['x2']['c13']['tip_palm'][0] * spec['chela']['cutter_palm']
    q = sa + r * nu - c0
    b_, c_ = 2.0 * float(q @ e), float(q @ q) - (R - r) ** 2
    t = 0.5 * (-b_ + np.sqrt(b_ * b_ - 4.0 * c_))       # the tipward root: inside the circle, r from the saw line
    cf = sa + r * nu + t * e
    tip = cf + r * unit(cf)
    t_arc = c0 + R * unit(cf - c0)
    rad = unit(t_arc - c0)
    tan_arc = np.array([-rad[1], rad[0]])
    if tan_arc @ e < 0.0:
        tan_arc = -tan_arc
    return dict(lat_idx=lat, c0=c0, R=R, resid=resid, sa=sa, sb=sb, e=e, nu=nu, r=float(r), cf=cf, t_arc=t_arc,
                t_line=sa + t * e, tip=tip, L=float(np.linalg.norm(tip)), axis=float(np.degrees(angle_of(tip))),
                u_tip=unit(tan_arc + e))


def tip_profile(O, r=None, stations=None):
    """the cutter's fixed finger at its tip as c13's profile reads it (X2c): the plan's chords ACROSS THE FINGER'S OWN
    AXIS (cutter_fixed_tip's u_tip) at `stations` mm behind its far point along that axis (default c13's: its
    x2.c13.tip_stations, palm fractions, x the cutter's palm: c13's tip region scaled by the palm, as its widths are),
    from the exact construction (the lateral arc, the cap, the saw line); returns (the chords / the palm, the stations
    mm, the cutter_fixed_tip dict)"""
    spec = O.spec
    palm = spec['chela']['cutter_palm']
    ft = cutter_fixed_tip(O, r=r)
    if stations is None:
        stations = np.asarray(spec['x2']['c13']['tip_stations'], np.float64) * palm
    c0, R, cf, e, u = ft['c0'], ft['R'], ft['cf'], ft['e'], ft['u_tip']
    a0, a1 = angle_of(ft['t_arc'] - cf), angle_of(ft['t_line'] - cf)
    while a1 < a0:
        a1 += 2.0 * np.pi
    reach = float(np.max(stations)) + 2.0
    P = np.vstack([arc_pts(c0, R, angle_of(ft['t_arc'] - c0) - reach / R, angle_of(ft['t_arc'] - c0), step=0.02),
                   arc_pts(cf, ft['r'], a0, a1, step=0.01)[1:],
                   np.linspace(ft['t_line'], ft['t_line'] - reach * e, int(reach / 0.02) + 2)[1:]])
    s_tip = float(np.max(P @ u))
    nn = np.array([-u[1], u[0]])
    out = []
    for back in np.asarray(stations, np.float64):
        s0 = s_tip - back
        sa_, sb_ = P[:-1] @ u - s0, P[1:] @ u - s0
        k = np.nonzero(sa_ * sb_ < 0.0)[0]
        q = P[k] + (P[k + 1] - P[k]) * (sa_[k] / (sa_[k] - sb_[k]))[:, None]
        out.append(float(np.ptp(q @ nn)) if len(k) >= 2 else float('nan'))
    return np.array(out) / palm, np.asarray(stations, np.float64), ft


def fit_cutter_cap(O):
    """rig.cheliped.cutter_cap's rule (X2c): the cap radius whose tip_profile best matches c13's (x2.c13.tip_profile,
    and x2.c13.tip_palm[0] at the last station, L/40), least squares over CUTTER['cap_bounds']; returns (r, rms palm,
    the profile at r)"""
    from scipy.optimize import minimize_scalar
    c13 = O.spec['x2']['c13']
    want = np.concatenate([np.asarray(c13['tip_profile'], np.float64), [c13['tip_palm'][0]]])

    def rms(r):
        return float(np.sqrt(np.mean((tip_profile(O, r)[0] - want) ** 2)))
    res = minimize_scalar(rms, bounds=CUTTER['cap_bounds'], method='bounded', options=dict(xatol=1e-7))
    return float(res.x), float(res.fun), tip_profile(O, float(res.x))[0]


def cutter_dactyl_tip(lower, dtip, artic, G, rd, n_herm=14):
    """the cutter's dactyl past the crusher's dactyl (X2b): its medial edge `lower` (the knob to the contact) carried
    on by a Hermite curve (its own direction at the contact, the cap's at the joint) to the top of a round cap of
    radius rd whose far point is dtip (Ld from the knob, on the line from the knob); the cap round the tip; the
    occlusal edge from the cap's tangent point straight back to G (the gape's bottom, lifted) bowed as X2's. Returns
    the plan run: medial -> cap -> occlusal (clockwise in (s, m))"""
    ud = unit(dtip - artic)
    nd = np.array([-ud[1], ud[0]])
    if nd[1] < 0.0:                                     # toward the dactyl's medial edge (+ m)
        nd = -nd
    cd = dtip - rd * ud
    P0, P3 = lower[-1], cd + rd * nd
    t0 = unit(lower[-1] - lower[-4])
    k = float(np.linalg.norm(P3 - P0))
    tau = np.linspace(0.0, 1.0, n_herm)[1:, None]
    herm = ((2 * tau ** 3 - 3 * tau ** 2 + 1) * P0 + (tau ** 3 - 2 * tau ** 2 + tau) * k * t0
            + (-2 * tau ** 3 + 3 * tau ** 2) * P3 + (tau ** 3 - tau ** 2) * k * ud)
    g = G - cd
    beta = np.arccos(min(1.0, rd / float(np.linalg.norm(g))))
    cand = []
    for sg in (1.0, -1.0):
        a_ = angle_of(g) + sg * beta
        cand.append(cd + rd * np.array([np.cos(a_), np.sin(a_)]))
    T = min(cand, key=lambda p: float((p - cd) @ nd))   # the lower tangent point (the occlusal side)
    a0, a1 = angle_of(nd), angle_of(T - cd)
    while a1 > a0:
        a1 -= 2.0 * np.pi
    cap = arc_pts(cd, rd, a0, a1)
    nb = 12
    occ = np.linspace(T, G, nb) + np.sin(np.linspace(0.0, np.pi, nb))[:, None] * np.array([0.0, 0.6])
    return np.vstack([lower, herm, cap[1:], occ[1:]])


def claw_polys(O, kind, Ld=None, H_sm=None):
    """M1's claw (kind) in its claw frame, (s, m) life mm: dict(outline, propodus, dactyl, artic, gape, dactyl_tip)
    (module docstring, CHELAE). The crusher's run goes lateral -> fixed tip -> gape -> dactyl tip -> knob -> medial;
    the cutter's medial -> knob -> dactyl -> contact -> fixed tip -> lateral, its gape and dactyl tip hidden (behind
    the crusher's dactyl): its occlusal edges from X0b's saw (saw_a / saw_b, on the fixed finger) and the gape's
    bottom read by eye (x2/outline/z_cutter_dactyl_base.png); its tip put Ld from the knob along the estimate's line
    (the rig's measured dactyl, rig.cheliped.cutter_dactyl: the estimate stops where the tip goes out of sight). X2b:
    both cutter fingers continued under the crusher's dactyl to c13's narrow rounded tips (cutter_fixed_tip,
    cutter_dactyl_tip), where X2 closed the fixed finger along the crusher's dactyl's edge in a flat face. X4f: H_sm
    the hinge (claw frame): the propodus's notch from the gape's bottom to the knob goes round it (socket_notch, the
    cup x2.n04.condyle_r of |G - A| + SOCKET cup_gap), on both claws; without it the straight chord"""
    key = f'{kind}_outline'
    P = O.poly[key]
    C = O.claw(P, kind)
    C_raw = C.copy()

    def notch_of(gape_, artic_):
        """X4f: the notch from the gape's bottom to the knob (socket_notch round H_sm; else the straight chord)"""
        if H_sm is None:
            return dict(notch=np.linspace(gape_, artic_, 7))
        r_ball = O.spec['x2']['n04']['condyle_r'] * float(np.linalg.norm(artic_ - gape_))
        r_cup = min(r_ball + SOCKET['cup_gap'], float(np.linalg.norm(artic_ - H_sm)) - SOCKET['slit_min'])
        bs_ = SOCKET.get('boss_share')
        bs_ = bs_.get(kind) if isinstance(bs_, dict) else bs_
        if bs_ is not None:                             # X4g: the cup is r57282_7's BOSS (SOCKET's TOP SLIT paragraph)
            r_cup = bs_ * float(np.linalg.norm(artic_ - H_sm)) + SOCKET['boss_gap']
        return dict(socket_notch(gape_, H_sm, artic_, r_cup), r_cup=r_cup, r_ball=r_ball)
    i_k0 = O.nearest(key, O.P['cr_artic' if kind == 'crusher' else 'cu_artic'])
    C = smooth_run(C, slice(i_k0, None) if kind == 'crusher' else slice(0, i_k0 + 1), CLAW['palm_smooth'])
    es = CLAW['edge_smooth']
    if kind == 'crusher':
        i_g = O.nearest(key, O.P['cr_gape_bottom'])
        i_k = O.nearest(key, O.P['cr_artic'])
        i_ft = O.nearest(key, O.P['cr_tip'])
        C = smooth_run(C, slice(i_ft, i_g + 1), es)            # the fixed finger's biting edge: its molar and teeth out
        i_o = int(np.argmax(C[:i_ft + 1, 0] > CLAW['outer_from']))
        C = smooth_run(C, slice(i_o, i_ft + 1), es)            # X4e: its outer margin's trace bumps out too (one stood
        #                                                        between two rings, x04 gate 10's 0.31 mm since X4c)
        gape, artic = C[i_g], C[i_k]
        dtip = O.claw(O.P['cr_tip_inner'], kind)[0]
        nt = notch_of(gape, artic)                      # X4f: round the hinge (X4e: a concave arch from the knob)
        prop = np.vstack([C[:i_g + 1], nt['notch'][1:-1], C[i_k:]])
        dac = C[i_g:i_k + 1].copy()
        i_dt = int(np.argmin(np.linalg.norm(dac - dtip, axis=1)))
        dac = smooth_run(smooth_run(dac, slice(0, i_dt + 1), es), slice(i_dt, None), es)   # its molar, tubercles out
    else:
        i_k = O.nearest(key, O.P['cu_artic'])
        i_c = O.nearest(key, CUTTER['contact'])               # where the dactyl's lower edge meets the crusher's dactyl
        artic = C[i_k]
        gape = O.claw(np.array([CUTTER['gape']]), kind)[0]
        dtip = O.claw(O.P['cu_dactyl_tip'], kind)[0]
        if Ld is not None:
            dtip = artic + Ld * unit(dtip - artic)
        # X2b: the fixed finger on past the crusher's dactyl: its lateral edge's circle, the fillet of c13's tip width
        # round the tip, back along the saw line (cutter_fixed_tip)
        ft = cutter_fixed_tip(O, C)
        i_l = ft['lat_idx'][0]
        lateral = C[i_l:][::-1]                                # lateral base -> where the crusher's dactyl covers it
        arc = arc_pts(ft['c0'], ft['R'], angle_of(C[i_l] - ft['c0']), angle_of(ft['t_arc'] - ft['c0']))
        a0, a1 = angle_of(ft['t_arc'] - ft['cf']), angle_of(ft['t_line'] - ft['cf'])
        while a1 < a0:
            a1 += 2.0 * np.pi
        cap = arc_pts(ft['cf'], ft['r'], a0, a1)
        sa, sb = ft['sa'], ft['sb']
        n_back = max(2, int(np.ceil(np.linalg.norm(ft['t_line'] - sa) / 1.5)) + 1)
        occl = np.vstack([np.linspace(ft['t_line'], sa, n_back)[1:], np.linspace(sa, sb, 8)[1:],
                          np.linspace(sb, gape, 5)[1:]])
        nt = notch_of(gape, artic)                      # X4f: round the hinge (X2 - X4e: the straight chord)
        prop = np.vstack([lateral, arc[1:], cap[1:], occl, nt['notch'][1:-1], C[:i_k + 1][::-1]])
        lower = smooth_run(C[i_k:i_c + 1], slice(0, None), es)   # its setae tufts out
        rd = 0.5 * O.spec['x2']['c13']['tip_palm'][1] * O.spec['chela']['cutter_palm']
        dac = cutter_dactyl_tip(lower, dtip, artic, gape + np.array([0.0, 0.4]), rd)
    # the propodus's base closed round the wrist (W at s, m = 0), from the medial end of the joint to its lateral end
    # (both runs end there): the carpus's end sinks into it
    bb = CLAW['base_back']
    if kind == 'cutter':
        # X4c (the lead's calls 1 and 3: the joints, the cutter): the crusher's 3-point layout below, laid on its 62 mm
        # palm, doubles back on the cutter's: the cutter's run already starts 7 mm behind W (s -6.97), so the third
        # point (s -3) stepped forward and the loop folded into a 78 deg spur at the base's lower corner (where the X4 /
        # X4b cutter cages tilted and folded: the 'wedge'); r57282_7's right wrist shows the cutter's base broad and
        # ROUND under the carpus's margin. A G1 closure instead: a cubic Bezier from the run's end round to its start,
        # its handles along the run's end and start tangents, CUTTER base_handle x the chord / 6 long (the spur
        # rounded, the base's back at s -7.6 against -6.2; the upper margin and W's place in the base as before)
        e_, s_ = prop[-1], prop[0]
        t_e, t_s = unit(e_ - prop[-4]), unit(prop[3] - s_)
        h_ = CUTTER['base_handle'] * float(np.linalg.norm(s_ - e_)) / 6.0
        tb = np.linspace(0.0, 1.0, 15)[1:-1][:, None]
        base = ((1 - tb) ** 3) * e_ + 3 * ((1 - tb) ** 2) * tb * (e_ + h_ * t_e) + 3 * (1 - tb) * tb * tb * (
            s_ - h_ * t_s) + (tb ** 3) * s_
    else:
        base = np.array([[-bb * 0.4, 3.0], [-bb, -0.35 * (prop[:, 1].max() - prop[:, 1].min()) * 0.5],
                         [-bb * 0.6, prop[0, 1] * 0.8]])
    prop = smooth_loop(np.vstack([prop, base]), CLAW['smooth'])
    if kind == 'crusher':                               # X4c: its closure's corners rounded (CLAW base_round)
        from scipy.ndimage import gaussian_filter1d
        wide = gaussian_filter1d(prop, CLAW['base_round'] / 0.25, axis=0, mode='wrap')   # (smooth_loop's 0.25 steps)
        s0_, s1_ = CLAW['base_round_s']
        w_ = np.clip((s1_ - prop[:, 0]) / (s1_ - s0_), 0.0, 1.0)[:, None]
        prop = (1.0 - w_) * prop + w_ * wide
    per = float(np.sum(np.linalg.norm(np.diff(np.vstack([prop, prop[:1]]), axis=0), axis=1)))
    out = dict(outline=C_raw, propodus=AP.resample_loop(prop, int(np.ceil(per / 0.6))), dactyl_c11=dac, artic=artic,
               gape=gape, dactyl_tip=dtip)
    if kind == 'cutter':                                # X4c: X0b's saw line (s, m) for the saw's strokes (no geometry)
        out['saw'] = np.array([sa, sb])
    out['notch'] = nt                                   # X4f: the notch's pieces (socket_notch) and the cup's radius
    return out


def socket_notch(G, H, A, r_cup, step=None):
    """X4f (SOCKET, the two-armed joint): the propodus's notch in the claw frame (s, m), the gape's bottom G -> the knob A
    through the hinge H: the GAPE RAY and the TOP RAY meeting at H (n04's V; the propodus's plan, whose smoothing fills
    the V's apex inside the cup), and the pieces the rims' labels read: rim_g the gape ray from the cup's radius to G,
    rim_o the top ray from it to A, cup the CUP's arc of radius r_cup round H on the distal side (the propodus's DISK,
    socket_parts, a solid of revolution about the axis, the condyles whole on its faces). Returns dict(notch, rim_g,
    rim_o, cup)"""
    st = SOCKET['cup_n'] if step is None else step
    G, H, A = (np.asarray(v, np.float64) for v in (G, H, A))
    ug, uo = unit(G - H), unit(A - H)
    rg, ro = float(np.linalg.norm(G - H)), float(np.linalg.norm(A - H))
    a0, a1 = np.arctan2(ug[1], ug[0]), np.arctan2(uo[1], uo[0])
    while a1 < a0:                                      # (counter-clockwise from the gape ray to the top ray: the distal
        a1 += 2.0 * np.pi                               # side, through the claw axis)
    ray_g = H + np.linspace(r_cup, rg, max(3, int(np.ceil((rg - r_cup) / st)) + 1))[:, None] * ug
    ray_o = H + np.linspace(r_cup, ro, max(3, int(np.ceil((ro - r_cup) / st)) + 1))[:, None] * uo
    th = np.linspace(a0, a1, max(5, int(np.ceil((a1 - a0) * r_cup / st)) + 1))
    cup = H + r_cup * np.column_stack([np.cos(th), np.sin(th)])
    v_g = H + np.linspace(0.0, rg, max(3, int(np.ceil(rg / st)) + 1))[:, None] * ug
    v_o = H + np.linspace(0.0, ro, max(3, int(np.ceil(ro / st)) + 1))[:, None] * uo
    return dict(notch=np.vstack([v_g[::-1], v_o[1:]]), rim_g=ray_g, rim_o=ray_o, cup=cup)


def palm_side(G, A):
    """X4f: the unit normal of the knob A -> the gape's bottom G chord pointing into the palm (the left of G -> A in the
    claw frame (s, m): the palm is proximal of the notch on both claws, as notch_arch bows)"""
    G, A = np.asarray(G, np.float64), np.asarray(A, np.float64)
    u = (A - G) / float(np.linalg.norm(A - G))
    return np.array([-u[1], u[0]])


def condyle_hinge(A, G, spec):
    """X4f (the lead's call 1 on the X4e check, 'move the hinge where the photos put it'): the claw's hinge as the
    CONDYLE's axis on M1's plan (claw frame s, m, life mm): n04's ball in its cup (x2.n04.condyle: f along the knob A ->
    the gape's bottom G, e into the palm, both / |G - A|; src_n04_x2.json cr_knob / cr_gape / cr_condyle), where the rim on
    the broad face bends from the knob down to the gape (r57282_7's top slit and gape-side crescent meet there). Returns
    (H, |G - A|)"""
    f, e = spec['x2']['n04']['condyle']
    A, G = np.asarray(A, np.float64), np.asarray(G, np.float64)
    c = float(np.linalg.norm(G - A))
    return A + f * (G - A) + e * c * palm_side(G, A), c


def plan_contact(D, P, H, G, A, step=0.25):
    """X4f: the plan contact of a claw closing from M1's pose: the turn (deg, toward the fixed finger) of the dactyl's plan D
    (M1's run, claw frame) about the hinge H at which a FINGER point (more than 8 mm from the gape's bottom G and the knob A,
    past G along the claw) first enters the propodus's plan P (even-odd), bisected to 1e-7 deg; NaN if none by 40 deg.
    x02's rule for rig.cheliped.hinge c (the rig's closed limit is this contact: x04 gate 12 measures it on the limits)"""
    D, P = np.asarray(D, np.float64), np.asarray(P, np.float64)
    H, G, A = (np.asarray(v, np.float64) for v in (H, G, A))
    F = D[(np.linalg.norm(D - G, axis=1) > 8.0) & (np.linalg.norm(D - A, axis=1) > 8.0) & (D[:, 0] > G[0])]

    def inside(X):
        x, y = X[:, 0][:, None], X[:, 1][:, None]
        x0, y0 = P[:, 0][None, :], P[:, 1][None, :]
        x1, y1 = np.roll(P[:, 0], -1)[None, :], np.roll(P[:, 1], -1)[None, :]
        cr = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / np.where(y1 != y0, y1 - y0, 1e-30) + x0)
        return (cr.sum(axis=1) % 2) == 1

    def hit(a):
        th = np.radians(-a)
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        return bool(inside((F - H) @ R.T + H).any())
    if hit(0.0):
        return 0.0
    lo, hi = 0.0, None
    for a in np.arange(step, 40.0 + 1e-9, step):
        if hit(a):
            hi = float(a)
            break
        lo = float(a)
    if hi is None:
        return float('nan')
    while hi - lo > 1e-7:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if not hit(mid) else (lo, mid)
    return hi


def clay_contact(prop, dac, inf, sc, step=0.35, lo=-10.0):
    """X4f, 3rd session (x02's rule for BOTH claws' hinge c: the rig's 0 is the CLAY's contact): the opening (rig deg, +
    opens) at which the dactyl's FINGER (its clay's surface points past the socket's heel radius + 0.2 mm: x04 gate 12's
    selection), turned rigidly about the hinge axis from the bind, first reaches the propodus's clay (collars and disk
    included), coming from open, bisected to 1e-6 deg. The plan contact (plan_contact) is the plan outlines' meeting: the
    clay's rounded biting edges meet later (the crusher 0.43 deg past it, x04 _x4f3 gate 12's -0.42 on the limits) and M1's
    cutter outlines already cross at its pose (its plan contact 0). The surface points come from a lattice anchored on the
    hinge in the DACTYL's own frame (claw_parts' local frame, step mm), projected onto its clay: they ride the dactyl, so
    the answer does not move with the SPEC's c. prop / dac / inf: claw_parts' returns; sc metres per life mm. Returns
    dict(contact, d0 (the fingers' least distance at the rig's 0, mm), at (the touching point: claw s, m, t), n_finger)"""
    sock = inf['socket']
    C3, d, n, tv = (np.asarray(sock[k], np.float64) for k in ('C3', 'd', 'n', 't'))
    fP = AP.field_mm(prop if isinstance(prop, list) else [prop], sc)
    fD = AP.field_mm([dac], sc)
    want, H = float(inf['want']), np.asarray(inf['H_sm'], np.float64)
    ang = np.radians(float(inf['c11_dir']) + want - float(inf['open_c11']))     # (the dactyl's axis at the bind)
    e1, e2 = np.array([np.cos(ang), np.sin(ang)]), np.array([-np.sin(ang), np.cos(ang)])
    E1, E2 = e1[0] * d + e1[1] * n, e2[0] * d + e2[1] * n
    loc = np.asarray(inf['dactyl_plan'], np.float64) - H[None, :]
    k1 = np.arange(np.floor((loc @ e1).min() / step) - 3, np.ceil((loc @ e1).max() / step) + 4)
    k2 = np.arange(np.floor((loc @ e2).min() / step) - 3, np.ceil((loc @ e2).max() / step) + 4)
    t_half = 0.5 * float(inf['thick']) + 3.0
    k3 = np.arange(-np.ceil(t_half / step), np.ceil(t_half / step) + 1)
    pts = []
    for a_ in k1:                                       # (slab by slab along the dactyl's axis)
        G_ = np.stack(np.meshgrid([a_], k2, k3, indexing='ij'), -1).reshape(-1, 3) * step
        P_ = C3[None, :] + G_[:, 0:1] * E1[None, :] + G_[:, 1:2] * E2[None, :] + G_[:, 2:3] * tv[None, :]
        pts.append(P_[np.abs(fD(P_)) < 0.6 * step])
    P = np.vstack(pts)
    for _ in range(3):                                  # (onto the clay along its gradient)
        f_ = fD(P)
        g_ = np.stack([(fD(P + e_) - fD(P - e_)) / 2e-3 for e_ in np.eye(3) * 1e-3], 1)
        P = P - f_[:, None] * g_ / np.maximum(np.linalg.norm(g_, axis=1, keepdims=True), 1e-12)
    q_ = P - C3[None, :]
    F = P[np.hypot(q_ @ d, q_ @ n) > sock['R'] + 0.2]
    K_ = np.array([[0.0, -tv[2], tv[1]], [tv[2], 0.0, -tv[0]], [-tv[1], tv[0], 0.0]])

    def posed(a_rig):
        th = np.radians(a_rig - want)
        R_ = np.eye(3) + np.sin(th) * K_ + (1.0 - np.cos(th)) * (K_ @ K_)     # (+ opens: d toward n about t)
        return (F - C3) @ R_.T + C3

    def dmin(a_rig):
        return float(fP(posed(a_rig)).min())
    out = dict(contact=float('nan'), d0=dmin(0.0), at=(float('nan'),) * 3, n_finger=int(len(F)))
    hi = want
    if dmin(lo) > 0.0 or dmin(hi) <= 0.0:
        return out
    while hi - lo > 1e-6:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if dmin(mid) <= 0.0 else (lo, mid)
    Pc = posed(hi)
    k_ = int(np.argmin(fP(Pc)))
    at = Pc[k_] - np.asarray(inf['W'], np.float64)
    out.update(contact=float(hi), at=(float(at @ d), float(at @ n), float(at @ tv)))
    return out


def dactyl_run(cp):
    """X4f: M1's dactyl run (cp['dactyl_c11']) oriented from the gape's bottom G along the occlusal edge, round the tip,
    back along the top edge to the knob A (the crusher's own order; the cutter's runs the other way, cutter_dactyl_tip)"""
    D = np.asarray(cp['dactyl_c11'], np.float64)
    G, A = np.asarray(cp['gape'], np.float64), np.asarray(cp['artic'], np.float64)
    return D[::-1].copy() if np.linalg.norm(D[0] - A) < np.linalg.norm(D[0] - G) else D


def socket_angles(cp, H_sm, open_c11, open_lim, sk=None):
    """X4e / X4f (SOCKET): the joint's angles about the hinge H_sm (claw frame s, m; deg about H from the axis toward n),
    PER ARM (X4f: socket_notch's two rays). THE GAPE ARM: phi_n the gape's bottom G's angle, its rim as a table (arch_r,
    arch_phi: its angle at radius r, from 0) and its largest recess `lead`, R the heel's radius; in the dactyl's frame at
    M1's opening (open_c11) the tongue's end phi_back and the heel's front phi_front; in the propodus's frame the socket's
    far end phi_sock (the tongue's end at the closed limit) and the collar's back edge phi_col. THE TOP ARM (_o, the
    mirror: opening drives it in): phi_o the knob A's angle, its table (arch_r_o, arch_phi_o) and recess lead_o, R_o the
    top arc's radius; the top tongue's end phi_back_o (it covers the closed limit) and the top arc's front phi_front_o
    (past A at the open limit, while M1's top edge stays within 2 clear_o of the arc: on a small circle it leaves it
    first); the top socket's far end phi_sock_o (the top tongue's end at the open limit), its collar's phi_col_o. r_cup
    the cup's radius (open_lim: the open limit)"""
    sk = SOCKET if sk is None else sk
    G, A, H = (np.asarray(v, np.float64) for v in (cp['gape'], cp['artic'], H_sm))
    nt = cp['notch']

    def ang(P):
        P = np.asarray(P, np.float64)
        return np.degrees(np.arctan2(P[..., 1] - H[1], P[..., 0] - H[0]))
    phi_n, phi_o = float(ang(G)), float(ang(A))
    rg, ro = np.asarray(nt['rim_g'], np.float64), np.asarray(nt['rim_o'], np.float64)
    ar, ap = np.concatenate([[0.0], np.linalg.norm(rg - H, axis=1)]), np.concatenate([ang(rg[:1]), ang(rg)])
    ar_o, ap_o = np.concatenate([[0.0], np.linalg.norm(ro - H, axis=1)]), np.concatenate([ang(ro[:1]), ang(ro)])
    lead, lead_o = float(phi_n - ap.min()), float(ap_o.max() - phi_o)
    R_o = float(np.linalg.norm(A - H)) - sk['clear_o']
    phi_back = phi_n - (open_lim - open_c11) - sk['back'] - lead
    phi_back_o = phi_o + (open_c11 - sk['close']) + sk['back_o'] + lead_o
    # the top arc's front: past A by the open limit's travel and front_o, short of where M1's top edge (from A toward the
    # tip) first leaves r <= R_o + 2 clear_o (the cutter's 3.6 mm circle turns 56 deg over that travel)
    D = dactyl_run(cp)[::-1]                            # (from the knob toward the tip along the top edge)
    rD = np.linalg.norm(D - H, axis=1)
    i_l = int(np.argmax(rD > R_o + 2.0 * sk['clear_o'])) if (rD > R_o + 2.0 * sk['clear_o']).any() else len(D) - 1
    phi_front_o = max(phi_o - (open_lim - open_c11) - sk['front_o'], float(ang(D[i_l])))
    return dict(H=H, G=G, A=A, phi_n=phi_n, R=float(np.linalg.norm(G - H)) - sk['clear'], phi_back=phi_back,
                phi_front=phi_n + (open_c11 - sk['close']) + sk['front'],
                phi_sock=phi_back - (open_c11 - sk['close']) - sk['sock_deg'], phi_col=phi_n - sk['phi_min'],
                open_c11=float(open_c11), open_lim=float(open_lim), arch_r=ar, arch_phi=ap, lead=lead,
                phi_o=phi_o, R_o=R_o, phi_back_o=phi_back_o, phi_front_o=phi_front_o,
                phi_sock_o=phi_back_o + (open_lim - open_c11) + sk['sock_deg'], phi_col_o=phi_o + sk['phi_min_o'],
                arch_r_o=ar_o, arch_phi_o=ap_o, lead_o=lead_o, r_cup=float(nt['r_cup']), r_ball=float(nt['r_ball']),
                close=float(sk['close']))


def hermite(P0, T0, P1, T1, step=0.4):
    """the cubic Hermite's interior points from P0 (tangent T0) to P1 (tangent T1), the tangents scaled by |P1 - P0|"""
    k = float(np.linalg.norm(P1 - P0))
    tt = np.linspace(0.0, 1.0, max(6, int(np.ceil(k / step)) + 1))[1:-1, None]
    return ((2 * tt ** 3 - 3 * tt ** 2 + 1) * P0 + (tt ** 3 - 2 * tt ** 2 + tt) * k * T0
            + (-2 * tt ** 3 + 3 * tt ** 2) * P1 + (tt ** 3 - tt ** 2) * k * T1)


def heel_plan(cp, sa, sk=None):
    """X4e / X4f (SOCKET): the dactyl's plan at M1's opening (claw frame), M1's run (cp['dactyl_c11']: the gape's bottom
    G, the occlusal edge, the tip, the top edge, the knob A) with its base made the joint's FAN about the hinge
    (socket_angles sa). The GAPE ARM: the HEEL (the arc of radius sa R about H) from the gape tongue's end phi_back on to
    phi_front, a cubic Hermite onto M1's occlusal edge SOCKET blend mm past where it crosses phi_front. Then M1's run
    round the tip back along its top edge. X4f, THE TOP ARM: blend_o mm short of where the top edge crosses phi_front_o,
    a Hermite onto the TOP ARC (radius sa R_o about H) on to the top tongue's end phi_back_o; the base's back the chord
    from there to the heel's start (inside the propodus at every pose). Returns the closed polygon (not yet smoothed)"""
    sk = SOCKET if sk is None else sk
    D = dactyl_run(cp)
    H, R, R_o = sa['H'], sa['R'], sa['R_o']
    if np.linalg.norm(D[0] - sa['G']) > 0.5 or np.linalg.norm(D[-1] - np.asarray(cp['artic'])) > 0.5:
        raise ValueError('heel_plan: the claw\'s run (the gape ... the knob) expected')     # (smooth_run's held ends)
    ang = np.degrees(np.arctan2(D[:, 1] - H[1], D[:, 0] - H[0]))
    i0 = int(np.argmax(ang > sa['phi_front']))          # (along the occlusal edge from G its angle rises)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    j = int(np.searchsorted(arc, arc[i0] + sk['blend']))
    ph = np.radians(np.linspace(sa['phi_back'], sa['phi_front'],
                                max(8, int(np.ceil(np.radians(sa['phi_front'] - sa['phi_back']) * R / 0.4)) + 1)))
    heel = H[None, :] + R * np.column_stack([np.cos(ph), np.sin(ph)])
    herm = hermite(heel[-1], np.array([-np.sin(ph[-1]), np.cos(ph[-1])]), D[j], unit(D[j + 1] - D[j - 1]))
    # the top arm (from the knob back along the top edge its angle falls)
    io = len(D) - 1 - int(np.argmax(ang[::-1] < sa['phi_front_o']))
    ko = int(np.searchsorted(arc, arc[io] - sk['blend_o'])) - 1
    if ko <= j + 2:
        raise ValueError(f'heel_plan: the top arm reaches the heel (top edge index {ko}, heel blend {j})')
    pho = np.radians(np.linspace(sa['phi_front_o'], sa['phi_back_o'],
                                 max(6, int(np.ceil(np.radians(sa['phi_back_o'] - sa['phi_front_o']) * R_o / 0.3)) + 1)))
    top = H[None, :] + R_o * np.column_stack([np.cos(pho), np.sin(pho)])
    herm_o = hermite(D[ko], unit(D[ko + 1] - D[ko - 1]), top[0], np.array([-np.sin(pho[0]), np.cos(pho[0])]))
    B0, B1 = top[-1], heel[0]
    back = np.linspace(B0, B1, max(4, int(np.ceil(np.linalg.norm(B1 - B0) / 0.5)) + 1))[1:-1]
    return np.vstack([heel, herm, D[j:ko + 1], herm_o, top, back])


def socket_parts(prop, dac, ci, sa, sc, sk=None):
    """X4e / X4f (SOCKET): the joint's thickness profiles, the propodus's collars (solids of revolution about the hinge
    axis, through H along the claw's thickness t) and the socket's record. prop / dac: the propodus's and the dactyl's
    descriptors (the dactyl at ci['want'] deg); sc metres per life mm. PER ARM (X4f: the gape arm and the top arm), T(r):
    the dactyl's own half-thickness at radius r, the most over that arm's sliding band (sampled in its own frame so every
    pose reads the same; a running max, smoothed) + t_margin, held SOCKET bury under the propodus's own at the arm's
    collar's back edge less the wall. Returns (the dactyl's CAPS: per arm whose hold bites, a revolve |t| <= T(r) out to
    the last bite + 1 mm, released over cap_ramp, over that arm's band only, groups to INTERSECT; the COLLARS: per arm the
    sector behind its ray from just inside the cup, |t| <= T(r) + wall, groups to UNION into the propodus; the socket
    dict: both arms, the cup's bearing thickness bear_T over (bear_r, bear_phi), the condyles on the broad faces)"""
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    sk = SOCKET if sk is None else sk
    W, d, n = ci['W'], unit(ci['d']), unit(ci['n'])
    t = unit(np.cross(d, n))
    H = sa['H']
    C3 = W + H[0] * d + H[1] * n                        # the hinge axis's point in the fingers' plane
    turn = ci['want'] - sa['open_c11']

    def half(f, r_, ph_deg):
        """the half-thickness of field f (life mm) at polar (r, phi) about H in the fingers' plane (vectorised)"""
        r_, ph_ = np.broadcast_arrays(np.asarray(r_, np.float64), np.radians(np.asarray(ph_deg, np.float64)))
        P0 = C3[None, :] + (r_ * np.cos(ph_)).reshape(-1, 1) * d[None, :] + (r_ * np.sin(ph_)).reshape(-1, 1) * n[None, :]
        lo, hi = np.zeros(len(P0)), np.full(len(P0), 40.0)
        inside0 = f(P0) < 0.0
        for _ in range(36):
            mid = 0.5 * (lo + hi)
            ins = f(P0 + mid[:, None] * t[None, :]) < 0.0
            lo, hi = np.where(ins, mid, lo), np.where(ins, hi, mid)
        return np.where(inside0, lo, 0.0).reshape(r_.shape)
    fD, fP = AP.field_mm([dac], sc), AP.field_mm(prop if isinstance(prop, list) else [prop], sc)
    r_cup = sa['r_cup']
    Ybig = 60.0
    Rbig = 250.0                                        # (X4f, 2nd session: the caps' far reach past the whole dactyl: at
    #                                                     60 mm the cutter's tip, ~64.5 mm from its hinge, lay past the
    #                                                     cap group's revolve and pie, and cap_k 1.5 cut it off: x04 _x4f3)

    def pie(a0, a1, Rp):
        """the plan polygon of the pie slice a0 -> a1 (deg, counter-clockwise) about H, radius Rp"""
        while a1 < a0:
            a1 += 360.0
        ph_ = np.radians(np.linspace(a0, a1, max(8, int(np.ceil((a1 - a0) / 3.0)) + 1)))
        return np.vstack([H[None, :], H[None, :] + Rp * np.column_stack([np.cos(ph_), np.sin(ph_)])])
    arms, caps, collars = {}, [], []
    # per ARM (X4f): its sliding band (deg in the dactyl's M1 frame), the heel's radius, the collar's sector (propodus
    # frame, counter-clockwise), the rim's width growing to wall_g toward the far end (the gape arm only)
    for arm, band, R_h, sect, grow_g in (('gape', (sa['phi_back'], sa['phi_front']), sa['R'], (sa['phi_col'], sa['phi_n']),
                                          True),
                                         ('top', (sa['phi_front_o'], sa['phi_back_o']), sa['R_o'],
                                          (sa['phi_o'], sa['phi_col_o']), False)):
        rs_ = np.arange(0.0, R_h + sk['reach'] + 1e-9, sk['r_step'])
        phs = np.linspace(band[0], band[1], sk['n_phi']) + turn
        RR, PP = np.meshgrid(rs_, phs, indexing='ij')
        T_nat = half(fD, RR, PP).max(axis=1)
        T_nat = np.maximum(gaussian_filter1d(maximum_filter1d(T_nat, 3, mode='nearest'), 1.0 / sk['r_step'],
                                             mode='nearest'), T_nat)
        phi_c = sect[0] if arm == 'gape' else sect[1]   # (the collar's back edge)
        T_room = half(fP, rs_, np.full_like(rs_, phi_c))
        hold = T_room - sk['wall'] - sk['bury']
        T = np.maximum(np.minimum(T_nat + sk['t_margin'], hold), 1.0)
        bite = (T_nat + sk['t_margin'] > hold) & (rs_ <= R_h) & (rs_ >= r_cup)
        if bite.any():                                  # the dactyl's band capped to T(r) (its band only), released past
            r_rel = float(rs_[bite].max()) + 1.0
            rr_, ct_ = rs_[rs_ <= r_rel], T[rs_ <= r_rel]

            def cap_profile(grow, rr_=rr_, ct_=ct_, r_rel=r_rel):
                ramp = np.array([[r_rel + sk['cap_ramp'], -Ybig], [r_rel + Rbig, -Ybig], [r_rel + Rbig, Ybig],
                                 [r_rel + sk['cap_ramp'], Ybig]])
                return np.vstack([np.column_stack([rr_, -(ct_ + grow)]), ramp,
                                  np.column_stack([rr_[::-1], (ct_ + grow)[::-1]])])
            lo_, hi_ = band[0] + turn - 4.0, band[1] + turn + 4.0      # (the band at the build's opening, 4 deg wider)
            caps.append(AP.group([AP.revolve(cap_profile, C3, t, name=f'dactyl socket cap ({arm} arm)'),
                                  slab(W, d, n, pie(hi_, lo_ + 360.0, Rbig), 40.0, 0.3, name=f'off the {arm} band')],
                                 op=S_.INTERSECT, k=sk['cap_k'], name=f'dactyl socket cap ({arm} arm)'))
        r0 = max(r_cup - 1.0, 0.5)                      # (the collar from just inside the cup's disk)
        sel = rs_ >= r0
        x_w = np.clip((rs_ - 0.6 * R_h) / (0.4 * R_h), 0.0, 1.0) if grow_g else np.zeros_like(rs_)
        T_col = gaussian_filter1d(T + sk['wall'] + (sk['wall_g'] - sk['wall']) * x_w * x_w * (3.0 - 2.0 * x_w),
                                  sk['col_soft'] / sk['r_step'], mode='nearest')
        rc_, Tc = rs_[sel], T_col[sel]

        def col_profile(grow, rc_=rc_, Tc=Tc):
            return np.vstack([np.column_stack([rc_, -(Tc + grow)]), np.column_stack([rc_[::-1], (Tc + grow)[::-1]])])
        ck_ = sk['col_k'] if arm == 'gape' or sk.get('col_k_o') is None else sk['col_k_o']   # (X4g: the top arm's own)
        collars.append(AP.group([slab(W, d, n, pie(sect[0], sect[1], float(rs_[-1]) + 1.0), 40.0, 0.3,
                                      name=f'propodus collar sector ({arm} arm)'),
                                 AP.revolve(col_profile, C3, t, op=S_.INTERSECT, k=sk['rim_k'],
                                            name=f'propodus collar ({arm} arm)')],
                                op=S_.UNION, k=ck_, name=f'propodus collar ({arm} arm)'))
        arms[arm] = dict(r=rs_, T=T, T_nat=T_nat, T_room=T_room, cap_to=float(rs_[bite].max()) + 1.0 if bite.any() else 0.0)
    # the CUP: the propodus's DISK round the axis (SOCKET cup), its faces cup_rise over the dactyl's thickest face just
    # outside it at any angle (the dactyl turning under it never shows through), its edge rounded; the condyles where the
    # axis leaves its faces
    cup_all = np.linspace(-180.0, 180.0, 145)
    T_face = float(np.max(half(fD, np.full_like(cup_all, r_cup + 0.3), cup_all))) + sk['cup_rise']
    rho_c = min(sk['cup_rho'], sk['cup_rho_share'] * r_cup)   # (X4f: the rounding within the disk, the cutter's 1.66 mm)

    def disk_profile(grow, T_=T_face, R_=r_cup, rho_=rho_c):
        """the disk's (r, y) profile grown by `grow`: a rectangle from the axis, its two outer corners rounded"""
        rc_ = max(rho_ + grow, 0.05)
        a_lo = np.radians(np.linspace(-90.0, 0.0, 9))   # (the lower corner, from the bottom face to the side)
        a_hi = np.radians(np.linspace(0.0, 90.0, 9))    # (the upper corner, from the side to the top face)
        lo_ = np.column_stack([R_ - rho_ + rc_ * np.cos(a_lo), -(T_ - rho_) + rc_ * np.sin(a_lo)])
        hi_ = np.column_stack([R_ - rho_ + rc_ * np.cos(a_hi), (T_ - rho_) + rc_ * np.sin(a_hi)])
        return np.vstack([[[0.0, -(T_ + grow)]], lo_, hi_, [[0.0, T_ + grow]]])
    collars.append(AP.revolve(disk_profile, C3, t, op=S_.UNION, k=sk['cup_k'], name='propodus disk (the cup)'))
    cup_phi = np.linspace(sa['phi_n'], sa['phi_o'], 48)        # (the dactyl just outside the cup at the bind: rim_f's
    cup_T = half(fD, np.full_like(cup_phi, r_cup + 0.3), cup_phi)  # trace on the cup's arc)
    # X4f, 3rd session, THE BEARING MEASURED: the hub both shells turn in is the propodus's clay round the axis on the
    # distal side between the rays (the disk, its smooth unions with the palm and the collars, the plan's filled V apex),
    # and THE BLENDS carry it past r_cup (x04 official 11-01 03:57, gate 9: the dactyl 0.42-0.59 mm into it at r 6.0-6.8 on
    # the crusher, where the declared cup ended at r_cup + cup_pad 5.67): `bear` is the disk's reach with its smooth
    # union's largest swell, r_cup + cup_k / 4, or the HUB's measured reach where that is further: the farthest point of
    # the propodus's clay from the axis in the V's MIDDLE (hub_off deg in from both rays), out to the shorter ray's length
    # + hub_pad, |t| under the bearing's thickness (the three unions folded in turn fill the cutter's small V out to r ~5:
    # x04 gate 9 read the propodus 2.1 mm into its dactyl at the bind there, scratch x4f probe_g23 t; a reach taken over
    # the whole V ran along the rims' own bulge and, on the cutter, past the short top ray onto the knob: dbg_hub)
    bear_t = T_face + sk['sock_t']                      # (the hub's whole thickness: X4e's T_face - wall was the disk's
    #                                                     face over the dactyl; the cutter's fill stands to the palm's)
    r_hub = r_cup + 0.25 * sk['cup_k']
    a_lo, a_hi = sa['phi_n'], sa['phi_o']
    while a_hi < a_lo:
        a_hi += 360.0
    if a_hi - a_lo > 2.0 * sk['hub_off'] + 5.0:
        fA = AP.field_mm(([prop] if not isinstance(prop, list) else list(prop)) + collars, sc)
        r_max = min(float(np.linalg.norm(sa['A'] - H)), float(np.linalg.norm(sa['G'] - H))) + sk['hub_pad']
        PH, TH, RH = np.meshgrid(np.radians(np.linspace(a_lo + sk['hub_off'], a_hi - sk['hub_off'], 25)),
                                 np.linspace(-bear_t, bear_t, 9), np.arange(r_cup, r_max + 1e-9, 0.1), indexing='ij')
        P_h = (C3[None, :] + (RH * np.cos(PH)).reshape(-1, 1) * d[None, :] + (RH * np.sin(PH)).reshape(-1, 1) * n[None, :]
               + TH.reshape(-1, 1) * t[None, :])
        ins_h = fA(P_h).reshape(PH.shape) < 0.0
        if ins_h.any():
            r_hub = max(r_hub, float(RH[ins_h].max()))
    g_, o_ = arms['gape'], arms['top']
    sock = dict(C3=C3, d=d, n=n, t=t, angles=dict(sa), wall=sk['wall'], bulge=sk['bulge'], r_cup=r_cup, bear=r_hub,
                T_face=T_face, bear_pad=sk['cup_pad'], bear_t=bear_t,
                condyles=(C3 + T_face * t, C3 - T_face * t), condyle_d=2.0 * sa['r_ball'],
                condyle_h=sk['condyle_h'] * 2.0 * sa['r_ball'], cup_phi=cup_phi, cup_T=cup_T,
                # the gape arm (X4e's keys)
                phi_n=sa['phi_n'], phi_sock=sa['phi_sock'], R=sa['R'] + sk['sock_r'], R_heel=sa['R'], r=g_['r'],
                T=g_['T'] + sk['sock_t'], T_joint=g_['T'], T_nat=g_['T_nat'], T_room=g_['T_room'],
                arch_r=sa['arch_r'], arch_phi=sa['arch_phi'], wedge=sk['wedge'], cap_to=g_['cap_to'],
                # the top arm
                phi_o=sa['phi_o'], phi_sock_o=sa['phi_sock_o'], R_o=sa['R_o'] + sk.get('sock_r_o', sk['sock_r']),
                R_heel_o=sa['R_o'],
                r_o=o_['r'], T_o=o_['T'] + sk['sock_t'], T_joint_o=o_['T'], T_nat_o=o_['T_nat'], T_room_o=o_['T_room'],
                arch_r_o=sa['arch_r_o'], arch_phi_o=sa['arch_phi_o'], wedge_o=sk['wedge_o'], cap_to_o=o_['cap_to'])
    return caps, collars, sock


def _polar(P, sock):
    """points P (any (..., 3)) about the socket's hinge axis: (shape, t across the claw, r, the angle deg from d toward n)"""
    P = np.asarray(P, np.float64)
    Q = P.reshape(-1, 3) - sock['C3'][None, :]
    s_, m_ = Q @ sock['d'], Q @ sock['n']
    return P.shape[:-1], Q @ sock['t'], np.hypot(s_, m_), np.degrees(np.arctan2(m_, s_))


def _sector_sd(r, y, ph, R, rr, TT, lo, hi):
    """a socket region's distance bound: r <= R, |t| <= TT(r), lo <= phi <= hi (deg)"""
    d_t = np.abs(y) - np.interp(r, rr, TT, right=0.0)
    inside = (ph >= lo) & (ph <= hi)
    dph = np.where(inside, -np.minimum(ph - lo, hi - ph), np.minimum(np.abs(ph - lo), np.abs(ph - hi)))
    return np.maximum(np.maximum(r - R, d_t), r * np.sin(np.radians(np.minimum(dph, 90.0))))


def socket_sd(P, sock):
    """X4e / X4f: the SOCKET's signed distance bound (life mm, negative inside) at points P (any (..., 3), the propodus's
    frame): the propodus's interior the dactyl's base swings in (socket_parts): per ARM r <= its R about the hinge axis,
    |t| <= its T(r), between its ray (+- bulge) and its socket's far end (the gape arm phi_sock .. its ray, the top arm its
    ray .. phi_sock_o); the CUP, within the bearing's reach (X4f, 3rd session: bear, the hub's reach, socket_parts; it was
    the disk's radius) + bear_pad of the axis at any angle, |t| <= the disk's face + sock_t (bear_t; X4e - X4f's 2nd
    session less the wall); x04's gate 9 reads the propodus's chitin as max(its field, -socket_sd)"""
    sh, y, r, ph = _polar(P, sock)
    bul = np.degrees(sock['bulge'] / np.maximum(r, 1.0))
    g = _sector_sd(r, y, ph, sock['R'], sock['r'], sock['T'], sock['phi_sock'],
                   np.interp(r, sock['arch_r'], sock['arch_phi']) + bul)
    o = _sector_sd(r, y, ph, sock['R_o'], sock['r_o'], sock['T_o'],
                   np.interp(r, sock['arch_r_o'], sock['arch_phi_o']) - bul, sock['phi_sock_o'])
    c = np.maximum(r - sock['bear'] - sock['bear_pad'], np.abs(y) - sock['bear_t'])
    return np.minimum(np.minimum(g, o), c).reshape(sh)


def notch_piece(r, ph, sock):
    """X4f: which notch piece a point (r, phi deg about the hinge axis) lies nearest in the fingers' plane (0 the gape
    ray, 1 the top ray, 2 the cup's arc on the distal side) and its distance (mm) from it (inf: none near)"""
    sa = sock['angles']
    a_n, a_o = sa['phi_n'], sa['phi_o']
    pg, po = r * np.cos(np.radians(ph - a_n)), r * np.cos(np.radians(ph - a_o))    # (along each ray from the axis)
    d_g = np.where((pg >= sock['r_cup'] - 0.5) & (pg <= sock['R_heel'] + 3.0), np.abs(r * np.sin(np.radians(ph - a_n))),
                   np.inf)
    d_o = np.where((po >= sock['r_cup'] - 0.5) & (po <= sock['R_heel_o'] + 2.0), np.abs(r * np.sin(np.radians(ph - a_o))),
                   np.inf)
    d_c = np.where((ph >= a_n) & (ph <= a_o), np.abs(r - sock['r_cup']), np.inf)
    D = np.stack([d_g, d_o, d_c])
    return np.argmin(D, axis=0), D.min(axis=0)


def rim_f(P, sock):
    """X4e / X4f (SOCKET): the rim's SMOOTH coordinate at points P (any (..., 3), the propodus's frame): mm outside the
    dactyl's trace on the notch's surface, by the nearest notch piece: on a RAY the larger of |t| - its arm's T(r) and r -
    its heel's radius; on the CUP's arc |t| - the dactyl's half-thickness just outside the cup at the bind (cup_T over
    cup_phi). 0 <= rim_f <= the ring's width is the rim's ring on the propodus: the gape arm's crescent, the top arm's
    slit, the cup's (decapod_cage notch_opening; X5 / X9's mask reads this, not the quads' labels)"""
    sh, y, r, ph = _polar(P, sock)
    k, _ = notch_piece(r, ph, sock)
    f_g = np.maximum(np.abs(y) - np.interp(r, sock['r'], sock['T_joint'], right=0.0), r - sock['R_heel'])
    f_o = np.maximum(np.abs(y) - np.interp(r, sock['r_o'], sock['T_joint_o'], right=0.0), r - sock['R_heel_o'])
    f_c = np.abs(y) - np.interp(ph, sock['cup_phi'], sock['cup_T'])
    return np.choose(k, [f_g, f_o, f_c]).reshape(sh)


def crescent_mask(P, sock, part, want, tol=1.6, ring=3.0):
    """X4e / X4f: the crescent as a SMOOTH mask at points P (any (..., 3)) on a shell's surface at the bind: the rims'
    ring on the propodus (within tol mm of a notch piece's surface, rim_f under `ring` mm) or the fan behind either hard
    edge on the dactyl (at `want` deg open). What X5 / X9's mask reads; the cage's per-quad regions only approximate it
    (its quads are wider than the ring)"""
    sh, y, r, ph = _polar(P, sock)
    if part == 'dactyl':
        return ((hard_edge_f(P, sock, want).reshape(-1) < 0.0) & (r > sock['r_cup'])
                & (r < np.maximum(sock['R'], sock['R_o']) + 0.5)).reshape(sh)
    _, dist = notch_piece(r, ph, sock)
    f = rim_f(P, sock).reshape(-1)
    return ((dist < tol) & (f > -0.6) & (f < ring)).reshape(sh)


def hard_edge_f(P, sock, want):
    """X4e / X4f (SOCKET wedge, wedge_o): the dactyl's HARD EDGES at points P of the dactyl at `want` deg open (any (...,
    3)): deg of its fan inside both edges (> 0: chitin; < 0: the membrane behind one). The gape edge: a copy of the gape
    ray turned to `wedge` deg past it at the open limit (under the rim below open_lim - wedge, then the crescent); the top
    edge (X4f): the top ray turned to wedge_o deg past it, outward, at the closed limit (under the top rim at every
    opening past close + wedge_o)"""
    sh, y, r, ph = _polar(P, sock)
    sa = sock['angles']
    e_g = np.interp(r, sock['arch_r'], sock['arch_phi']) - (sa['open_lim'] - want) + sock['wedge']
    e_o = np.interp(r, sock['arch_r_o'], sock['arch_phi_o']) + (want - sa['close']) - sock['wedge_o']
    return np.minimum(ph - e_g, e_o - ph).reshape(sh)


def dactyl_poly(cp, H_sm, angle, socket=None):
    """the dactyl's plan (s, m): M1's (cp['dactyl_c11']), its base extended CLAW['dactyl_sink'] back past the line from
    the gape's bottom to the knob (into the propodus), turned by `angle` deg about the hinge H_sm (+ opens: toward m).
    X4e: socket (socket_angles' dict): the crusher's base as the joint's fan instead (heel_plan)"""
    D = np.asarray(cp['dactyl_c11'], np.float64)
    if socket is not None:
        D = smooth_loop(heel_plan(cp, socket), 0.8)
        per = float(np.sum(np.linalg.norm(np.diff(np.vstack([D, D[:1]]), axis=0), axis=1)))
        D = AP.resample_loop(D, int(np.ceil(per / 0.5)))
        th = np.radians(angle)
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        return (D - H_sm) @ R.T + H_sm
    g, a = cp['gape'], cp['artic']
    ax = unit(cp['dactyl_tip'] - 0.5 * (g + a))
    back = -ax * CLAW['dactyl_sink']
    ext = [a + back + 0.2 * (g - a), g + back - 0.2 * (g - a)]       # the run ends at the knob: then knob side first
    if np.linalg.norm(D[-1] - g) < np.linalg.norm(D[-1] - a):        # (the cutter's run ends at the gape)
        ext = ext[::-1]
    D = smooth_loop(np.vstack([D, ext]), 0.8)
    per = float(np.sum(np.linalg.norm(np.diff(np.vstack([D, D[:1]]), axis=0), axis=1)))
    D = AP.resample_loop(D, int(np.ceil(per / 0.5)))
    th = np.radians(angle)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    return (D - H_sm) @ R.T + H_sm


def claw_parts(spec, chain, O, kind, dactyl_angle=None):
    """the claw (kind) on the LEFT at the bind: (propodus descriptor, dactyl descriptor, info); the dactyl turned to
    `dactyl_angle` deg open (None: the bind's rig.cheliped.dactyl_open)"""
    ch = chain['cheliped']
    cl = chain['claws'][kind]
    W, d, n = ch['W'], ch['d'], cl['n']
    H_sm = np.array([float((cl['H'] - W) @ d), float((cl['H'] - W) @ n)])     # the rig's hinge (decapod.claw)
    cp = claw_polys(O, kind, cl['Ld'], H_sm=H_sm)       # X4f: the notch round it
    L = cl['L']
    thick = spec['chela'][f'{kind}_thick']
    tp = np.array(CLAW_TH['propodus'])
    fp = AP.pchip(tp[:, 0], tp[:, 1])
    th_p = lambda u: 0.5 * thick * float(fp(np.clip(u, tp[0, 0], tp[-1, 0])))               # noqa: E731
    if kind == 'crusher':                   # X4d: the base's articular knob (CLAW lump), turning inside the carpus
        lm, s_lm = CLAW['lump']
        s_bk = float(np.asarray(cp['propodus'])[:, 0].min())
        th_0 = th_p

        def th_p(u, th_0=th_0, lm=lm, s_lm=s_lm, s_bk=s_bk, L=L):
            w = float(np.clip((u * L - s_bk) / (s_lm - s_bk), 0.0, 1.0))
            return th_0(u) * (lm + (1.0 - lm) * w * w * (3.0 - 2.0 * w))
    prop = plan_solid(W, d, n, cp['propodus'], th_p, L, 0.5 * thick + 4.0, name='propodus',
                      pads=claw_pads('propodus', float(np.asarray(cp['artic'])[0])), p_m=CLAW['round_p_m'])   # A0
    # the dactyl: M1's opening (x2.c11) to the requested one about the rig's hinge H_sm
    # X4f: M1's dactyl direction ABOUT THE HINGE, its tip (claw_polys' dactyl_tip, the claw frame: the cutter's turned
    # rig.cheliped.cutter_axis) from H_sm. X2-X4e read it from the knob, which was the hinge; under the margin the two
    # lines differ by 7.4 deg on the crusher
    tipd = np.asarray(cp['dactyl_tip'], np.float64)
    c11_dir = float(np.degrees(np.arctan2(tipd[1] - H_sm[1], tipd[0] - H_sm[0])))
    palm = cl['palm']
    cc = (spec['rig']['cheliped']['cutter_hinge'] if kind == 'cutter' else spec['rig']['cheliped']['hinge'])[1] * palm
    closed_dir = np.degrees(np.arctan2(cc - H_sm[1], L - H_sm[0]))
    open_c11 = c11_dir - closed_dir
    want = spec['rig']['cheliped']['dactyl_open'] if dactyl_angle is None else dactyl_angle
    # X4e (SOCKET): the base as the joint's fan about the hinge; X4f: two-armed, on both claws (the lead's call 2)
    sa = socket_angles(cp, H_sm, open_c11, spec['chela']['dactyl_open'][0 if kind == 'crusher' else 1])
    dp = dactyl_poly(cp, H_sm, want - open_c11, socket=sa)
    td = np.array(CLAW_TH['dactyl'])
    Ld = cl['Ld']
    base_s = float(dp[:, 0].min())
    # the dactyl's envelope runs along its own axis in the claw plane: a local frame (s', m') from its base
    ang = np.radians(c11_dir + (want - open_c11))
    dd = np.cos(ang) * d + np.sin(ang) * n
    nd_ = -np.sin(ang) * d + np.cos(ang) * n
    o_d = W + H_sm[0] * d + H_sm[1] * n
    loc = np.column_stack([(dp - H_sm) @ np.array([np.cos(ang), np.sin(ang)]),
                           (dp - H_sm) @ np.array([-np.sin(ang), np.cos(ang)])])
    fd = AP.pchip(td[:, 0], td[:, 1])
    th_d = lambda u: 0.5 * thick * float(fd(np.clip(u, td[0, 0], td[-1, 0])))               # noqa: E731
    dac = plan_solid(o_d, dd, nd_, loc, th_d, Ld, 0.5 * thick + 3.0, name='dactyl', s_pad=(3.0, 2.5),
                     pads=claw_pads('dactyl'), p_m=CLAW['round_p_m'])                                        # A0
    # X4e / X4f: the propodus's collars round the dactyl's sliding base, one per arm (its bands capped where a hold bites)
    caps, collars, sock = socket_parts(prop, dac, dict(W=W, d=d, n=n, want=want), sa, chain['scale_m'])
    dac['members'].extend(caps)
    prop = [prop] + collars
    info = dict(kind=kind, W=W, d=d, n=n, t=np.cross(d, n), L=L, Ld=Ld, H_sm=H_sm, open_c11=open_c11, want=want,
                c11_dir=c11_dir, polys=cp, dactyl_plan=dp, base_s=base_s, socket=sock, thick=thick)
    return prop, dac, info


# ============================================================================================ the parts
class Part(AP.Part):
    """one shell: AP.Part, plus `src` (the program's owner: a right part's left one, the cutter's own build)"""

    def __init__(self, name, region, joint, prog, descs, parent=None, mirror=False, side='', src=None):
        super().__init__(name, region, joint, prog, descs, parent=parent, mirror=mirror, side=side)
        self.src = src or name


def arm_descs(M_, B_, I_, K_, W_, across, s):
    """A0, ORGANIC: the left cheliped's PROXIMAL CHAIN (coxa, basis, merus, carpus) as descriptors, ({shell name: [its
    descriptors]} in chain order, the knee wheel's record), from its joints' points (the rest chain's M, B, I, K and the
    wrist W, life mm), `across` (the chain plane's normal: build_parts' np.cross(h, UP)) and s (metres per life mm).
    build_parts' own code, split out so the arm's clay can be built ALONE, in seconds, while it is sculpted beside the
    photos (scratch x6fix_x7/org4/arm_lab.py; build_parts takes minutes)"""
    chain_pts = [M_, B_, I_, K_, W_]
    out, wheel = {}, None
    for i, seg in enumerate(('coxa', 'basis', 'merus', 'carpus')):
        ra, rb = CHEL_R[seg]
        sink = SINK_FRAC * min(ra)
        nm = f'cheliped_{seg}_L'
        if seg == 'carpus':                     # X4e (KNEE): its proximal end the wheel about the knee's fold axis
            ds, wheel = knee_carpus(I_, K_, W_, out['cheliped_merus_L'][0], ra, rb, across, s, nm)
        else:                                   # A0, ORGANIC (ARM): a loft of changing sections, joint to joint
            am_ = ARM[seg]
            a_, b_ = np.asarray(chain_pts[i], np.float64), np.asarray(chain_pts[i + 1], np.float64)
            assert abs(am_['rows'][-1][0] - float(np.linalg.norm(b_ - a_))) < 0.02, \
                f'ARM {seg}: its last station is not the segment\'s length {float(np.linalg.norm(b_ - a_)):.3f}'
            if seg == 'merus':                  # (its rows are written with +N the flexor side: the carpus's)
                assert float(perp(across, unit(b_ - a_)) @ (np.asarray(W_) - np.asarray(K_))) > 0.0, \
                    'ARM merus: +N is not the flexor side'
            ds = limb_loft(a_, across, b_ - a_, am_['rows'], am_['rho'], sink=sink, bow=am_.get('bow', 0.0), name=nm)
            if am_.get('bosses'):               # A0 v3: its bosses, in the rows' own frame (theta from +N toward +B)
                t_ = unit(b_ - a_)
                N_ = unit(perp(across, t_))
                ds = [ds] + limb_bosses(a_, t_, N_, np.cross(t_, N_), am_['bosses'], nm)
            for tg in am_.get('tongues', ()):   # A0 v3b: its tongues (a joint's ears), each a small loft of its own
                ds = (ds if isinstance(ds, list) else [ds]) + [limb_loft(
                    a_, across, b_ - a_, tg['rows'], tg['rho'], op=S_.UNION, k=tg['k'], name=f'{nm} {tg["name"]}')]
        out[nm] = ds if isinstance(ds, list) else [ds]
    return out, wheel


def build_parts(spec, chain, O, dactyl_angle=None):
    """every shell (module docstring) as {name: Part} and an info dict (the carapace's lines, the abdomen's levels, the
    fan's level, the claws' frames). dactyl_angle: the chelae's dactyls open this much (deg; None: the bind's)"""
    s = chain['scale_m']
    P = chain['pos']
    descs, meta, info = {}, {}, {}

    def add(name, region, joint, ds, parent=None):
        descs[name] = ds if isinstance(ds, list) else [ds]
        meta[name] = (region, joint, parent)

    # ---- the body
    cd, Lc = carapace_descs(spec, chain, O)
    add('carapace', 'carapace', 'body', cd)
    add('ventral_thorax', 'ventral_thorax', 'body', thorax_desc(spec, chain, Lc), 'carapace')
    info['carapace'] = Lc
    # ---- the abdomen
    lev, z_tel, z_tip = abdomen_levels(spec, chain)
    info['abdomen'] = dict(levels=lev, z_tel=z_tel, z_tip=z_tip)
    for k in range(1, 7):
        ds, S, W = tergite_descs(spec, chain, O, k, Lc)
        add(f'abd_{k}', 'tergite', f'abd_{k}', ds, 'carapace' if k == 1 else f'abd_{k - 1}')
        add(f'sternite_{k}', 'sternite', f'abd_{k}', sternite_desc(S, W), f'abd_{k}')
        if k <= 5:
            base, tip_ = P[f'pleopod_{k}_L'], P[f'pleopod_{k}_tip_L']
            if k == 1:              # the gonopod from the sternite's underside, forward along the sternum
                Sb = S['T'] - ABD['stern'] * S['D']
                top = np.array([base[0], Sb + 0.2, base[2]])
                pl_desc = tube(top, tip_, *HEAD_R['pleopod_1'], across=np.array([0.0, 0.0, 1.0]), name='pleopod_1')
            else:                   # X2c: folded forward from the sternite's lateral end into the slot beside it
                pl_desc = tube(base, tip_, *PLEO_FOLD['r'], across=np.array([1.0, 0.0, 0.0]), name=f'pleopod_{k}')
            add(f'pleopod_{k}_L', 'pleopod', f'pleopod_{k}_L', pl_desc, f'sternite_{k}')
    fd, finfo = fan_descs(spec, chain, O)
    info['fan'] = finfo
    add('telson', 'telson', 'telson', fd['telson'], 'abd_6')
    add('uropod_L', 'uropod', 'uropod_L', fd['uropod_L'], 'abd_6')
    add('uropod_endo_L', 'uropod', 'uropod_endo_L', fd['uropod_endo_L'], 'uropod_L')
    add('uropod_exo_L', 'uropod', 'uropod_exo_L', fd['uropod_exo_L'], 'uropod_L')
    add('uropod_exo_dist_L', 'uropod', 'uropod_exo_dist_L', fd['uropod_exo_dist_L'], 'uropod_exo_L')
    # ---- the walking legs
    for leg in DP.WALK:
        g = chain['legs'][leg]['pts']
        lo = leg.lower()
        pts = [g[k_] for k_ in ('M', 'B', 'I', 'K', 'P', 'D', 'T')]
        across = g['n_p']
        prev = None
        for i, seg in enumerate(DP.SEGS):
            ra, rb = LEG_R[seg]
            sink = SINK_FRAC * min(ra)                  # the coxa into the ventral thorax, each segment into its parent
            nm = f'{lo}_{seg}_L'
            end = tip_on_ground(pts[i], pts[i + 1], ra, rb, across) if seg == 'dactyl' else pts[i + 1]
            add(nm, 'walking_leg', nm, tube(pts[i], end, ra, rb, across=across, sink=sink, name=nm),
                'ventral_thorax' if i == 0 else prev)
            prev = nm
    # ---- the chelipeds: the proximal chain (arm_descs), then the claws sided by type
    ch = chain['cheliped']
    g = ch['pts']
    arm, info['knee_wheel'] = arm_descs(g['M'], g['B'], g['I'], g['K'], ch['W'], np.cross(g['h'], UP), s)
    prev = None
    for nm, ds in arm.items():
        add(nm, 'cheliped', nm, ds, 'ventral_thorax' if prev is None else prev)
        prev = nm
    claws = {}
    for kind in ('crusher', 'cutter'):
        pr, da, ci = claw_parts(spec, chain, O, kind, dactyl_angle)
        claws[kind] = ci
        tag = 'L' if kind == 'crusher' else 'cutter'
        add(f'cheliped_propodus_{tag}', 'propodus', 'cheliped_propodus_L', pr, 'cheliped_carpus_L')
        add(f'cheliped_dactyl_{tag}', 'dactyl', 'cheliped_dactyl_L', da, f'cheliped_propodus_{tag}')
    info['claws'] = claws
    # ---- the head: eyestalks and corneas, antennae, antennules, third maxillipeds
    es0, es1, C = P['eyestalk_0_L'], P['eyestalk_1_L'], P['cornea_L']
    add('eyestalk_0_L', 'eyestalk', 'eyestalk_0_L', tube(es0, es1, *HEAD_R['eyestalk_0'], across=UP, name='eyestalk_0'),
        'carapace')
    add('eyestalk_1_L', 'eyestalk', 'eyestalk_1_L',
        tube(es1, C, *HEAD_R['eyestalk_1'], across=UP, sink=SINK_FRAC * 2.4, name='eyestalk_1'), 'eyestalk_0_L')
    te = unit(C - es1)
    rc = HEAD_R['cornea']
    add('cornea_L', 'cornea', 'eyestalk_1_L', AP.roundcone(C + te * (rc * 0.15), C + te * (rc * 0.35), rc, rc * 0.92,
                                                          name='cornea'), 'eyestalk_1_L')
    a = spec['rig']['antenna']
    ua = DP.heading(a['yaw'], a['pitch'])
    acr = np.cross(ua, UP)
    ant = [P['antenna_0_L'], P['antenna_1_L'], P['antenna_2_L'], P['flagellum_00_L']]
    prev = 'carapace'
    for i in range(3):              # the first article from 2 mm inside the carapace's front face (its socket)
        nm = f'antenna_{i}_L'
        add(nm, 'antenna', nm, tube(ant[i], ant[i + 1], *HEAD_R[f'antenna_{i}'], across=acr,
                                    sink=2.0 if i == 0 else SINK_FRAC * HEAD_R[f'antenna_{i}'][0][1], name=nm), prev)
        prev = nm
    add('flagellum_L', 'flagellum', 'flagellum_00_L',
        tube(ant[3], P['antenna_tip_L'], *HEAD_R['flagellum'], across=acr, sink=SINK_FRAC * 1.6, n=12, p=2.0,
             name='flagellum'), 'antenna_2_L')
    b = spec['body']
    sc_base = ant[1] - 4.0 * ua + np.array([0.0, 1.2, 0.0])
    sc_tip = np.array([0.5 * b['antscale_tips'], ant[1][1] + 1.5, max(11.5, sc_base[2] + 9.0)])
    add('antscale_L', 'antenna', 'antenna_1_L', tube(sc_base, sc_tip, *HEAD_R['antscale'], across=UP, p=2.0,
                                                     name='antscale'), 'antenna_1_L')
    anl = [P['antennule_0_L'], P['antennule_1_L'], P['antennule_2_L'], P['antennule_lat_0_L']]
    n_ = spec['rig']['antennule']
    un = DP.heading(n_['yaw'], n_['pitch'])
    prev = 'carapace'
    for i in range(3):
        nm = f'antennule_{i}_L'
        add(nm, 'antennule', nm, tube(anl[i], anl[i + 1], *HEAD_R[f'antennule_{i}'], across=np.cross(un, UP),
                                      sink=3.0 if i == 0 else SINK_FRAC * HEAD_R[f'antennule_{i}'][0][1], name=nm),
            prev)
        prev = nm
    for fl in ('lat', 'med'):
        a0, a1 = P[f'antennule_{fl}_0_L'], P[f'antennule_{fl}_tip_L']
        add(f'antennule_{fl}_L', 'antennule', f'antennule_{fl}_0_L',
            tube(a0, a1, *HEAD_R['antennule_f'], across=UP, sink=SINK_FRAC * 0.8, n=6, p=2.0, name=f'antennule_{fl}'),
            'antennule_2_L')
    mx = [P['mxp3_0_L'], P['mxp3_1_L'], P['mxp3_2_L'], P['mxp3_tip_L']]
    prev = 'ventral_thorax'
    for i in range(3):
        nm = f'mxp3_{i}_L'
        add(nm, 'maxilliped', nm, tube(mx[i], mx[i + 1], *HEAD_R[f'mxp3_{i}'], across=UP,
                                       sink=SINK_FRAC * min(HEAD_R[f'mxp3_{i}'][0]), name=nm), prev)
        prev = nm
    # ---- the programs: left and midline built; right parts mirror their left (the cutter its own build)
    parts = {}
    for nm, ds in descs.items():
        region, joint, parent = meta[nm]
        if nm.endswith('_cutter'):
            continue
        prog = AP.program_of(ds, s)
        side = 'L' if nm.endswith('_L') else ''
        parts[nm] = Part(nm, region, joint, prog, ds, parent=parent, side=side)
    for nm in list(parts):
        if nm.endswith('_L'):
            pr = parts[nm]
            rn = nm[:-2] + '_R'
            par = pr.parent[:-2] + '_R' if (pr.parent and pr.parent.endswith('_L')) else pr.parent
            if nm in ('cheliped_propodus_L', 'cheliped_dactyl_L'):
                cn = nm[:-2] + '_cutter'
                prog = AP.program_of(descs[cn], s)
                parts[rn] = Part(rn, pr.region, pr.joint[:-2] + '_R', prog, descs[cn], parent=par, mirror=True,
                                 side='R', src=cn)
            else:
                parts[rn] = Part(rn, pr.region, pr.joint[:-2] + '_R', pr.prog, pr.descs, parent=par, mirror=True,
                                 side='R', src=nm)
    return parts, info


def overlaps(parts):
    """the listed overlapping pairs (module docstring): {frozenset((a, b))}. Besides every joint's parent and child and
    each tergite with its sternite: the WALKING LEGS' coxae, bases and meri under the carapace's free margin (the
    branchiostegite overhangs them in the animal; the clay's carapace is solid where the animal's is a shell over the
    gills, X4's cage hides that inner face), the two antennule flagella from one peduncle, the eyestalks' and the
    antennules' second articles in the carapace's front, the antennal scale on its peduncle's neighbours, the fan's
    blades lapping under the telson and T6"""
    out = set()
    for nm, p in parts.items():
        if p.parent and p.parent in parts:
            out.add(frozenset((nm, p.parent)))
    for k in range(1, 7):
        out.add(frozenset((f'abd_{k}', f'sternite_{k}')))
    for s_ in ('L', 'R'):
        out |= {frozenset(('telson', f'uropod_endo_{s_}')), frozenset((f'uropod_{s_}', 'telson')),
                frozenset((f'eyestalk_1_{s_}', 'carapace')), frozenset((f'antennule_1_{s_}', 'carapace')),
                frozenset((f'antennule_lat_{s_}', f'antennule_med_{s_}')),
                frozenset((f'antscale_{s_}', f'antenna_0_{s_}')), frozenset((f'antscale_{s_}', f'antenna_2_{s_}')),
                frozenset((f'uropod_exo_{s_}', 'telson')), frozenset((f'uropod_exo_dist_{s_}', f'uropod_endo_{s_}')),
                frozenset((f'uropod_endo_{s_}', 'abd_6'))}
        for leg in DP.WALK:
            for seg in ('coxa', 'basis', 'merus'):
                out.add(frozenset((f'{leg.lower()}_{seg}_{s_}', 'carapace')))
    return {pr for pr in out if all(x in parts for x in pr)}
