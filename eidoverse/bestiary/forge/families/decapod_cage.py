"""X4 (work/bestiary/research/LOBSTER_PLAN.md §5.3 / §5.4, §12's X4 row): THE LOBSTER'S CAGES, one closed creased
subdivision cage per shell plus the sleeves, on the accepted clay (X2 / X2b / X2c: families/decapod_parts.py) and X3's
records (work/bestiary/lobster/seams.json). THIS ROUND: THE CRUSHER CHELIPED FIRST (coxa to dactyl, its sleeves), so
X7's pilot can follow; the other parts take the same conventions.

THE METHOD (the beetle's B3g / B4: forge/subdiv_sharp.py, families/arthropod_cage.py, heads/insect_mcage.py; read and
called, never edited):
  - each SHELL is ONE closed quad cage: K-column rings along its own spine (a segment's straight axis, a claw part's
    plan centreline), both ends capped by a GRID CAP (grid_cap: n x n, n = K / 4, its corners the four valence-3 poles;
    x4-1: arthropod_cage's m x 2 cap stretched to aspect 6 at K 20);
  - its TARGETS lie on the shell's own clay program: in-plane rays from the spine, past each end rays tilted toward
    the spine's end tangent (cones from the end node: the rounded end); rings spaced by the LOCAL column spacing and the
    profile's turning (ring_taus), equal steps between the fixed stations (X3's records), walking out toward each pole
    until the arc left is under the ring's radius; an end zone tilted in sight is relaxed on the clay (relax_ends);
  - a child's proximal end stays the clay's (its condyle sunk past the joint by X2's SINK_FRAC; condyle() lengthens a
    child short of x04's gate, hidden);
  - the CONTROLS are fitted so the limit surface passes through every target at the cage's vertices
    (subdiv_sharp.fit_controls), and THE LOW is the cage at those limit positions, its vertices = the targets;
  - creases only where the photos show an edge (§5.3's classes); the lobster is mostly smooth;
  - COLUMNS: vertex 0 on the port frame's tangent of the spine's start (remix/slots.port_frame, X3's convention),
    right-handed about the spine (distal), the frame carried along a curved spine by parallel transport; a ring that
    carries an X3 record takes the record's own frame, angles and vertices exactly (bit-exact: its targets ARE the
    record's verts_mm);
  - the RIGHT side is the left's exact mirror (p_R = M p_L, the quads reversed), except the chelae, sided by type.
THE SLEEVES (§5.4): at every joint three planar rings normal to the child's axis at X - d_in, X, X + d (X where the
child's axis leaves the parent, d = 0.36 r clamped 0.4-3.0 mm at life, d_in no deeper than half the child behind X),
each the child's section x in_child 0.84: hidden at rest, open (two bands). A graft site's PROXIMAL ring is X3's record
(the sleeve's other two rings re-cast by X3's own rule, x03_seams.build_ring).
THE WRIST (X4d, the lead's call 1 on the X4c check, 10-30; it replaces X4's inset collar past X3's ring): the CARPUS is
one closed shell on its own clay, X3's wrist ring a loop of it (no crease in the ring's collar), its chitin carried to
its true distal margin, where its claw's swept propodus first reaches it (joint_margin: per column of its profile, a
smooth function on the shell, margin_f); past the margin its faces are the wrist MEMBRANE (region 'membrane', skinned
carpus -> propodus along the profile, its end inside the propodus base). The right carpus is the left's exact mirror
with the CUTTER's margin (its own claw's). A graft at the wrist drops the membrane with the claw (seams.json native).
X4b (the lead's calls on the X4 check, 10-29):
  - THE MOTION RANGES (MOTION, joint_motions): each child posed rigidly about its joint's fold axis (the skeleton's z)
    over its range: the claw open 0-40 deg and the wrist -30..+40 from the bind (the lead's), the proximal joints over
    the rig's own ranges (rig.ranges.cheliped; the ischium-merus the walking legs' +-10: the cheliped has none). A face
    is HIDDEN OVER THE RANGE when it lies inside another shell (centre and corners, MOTION margin deep) at every pose
    (range_hidden): X5's no-texel rule and x04's hidden-tilt exemption take only those;
  - THE CONDYLES TRIMMED (cut_depth, CutField): each child's buried end cut at the DEEPEST depth behind X0 whose cut
    face stays hidden over the whole range (MOTION margin inside the fixed shells at every pose); deeper, the end would
    swing out through its parent's wall (the X4 check: the propodus's knob 3.9-4.9 mm out of the carpus). A joint whose
    range brings even the shallowest cap out (the knee's 120 deg; the claw, whose base and proximal underside along
    the gape all come out at 40 deg) keeps the clay's end, and its faces keep their texels. On this clay NO depth of any
    of the six joints passes (x04 5b: each child's section crosses its parent's wall at some pose), so no end is cut.
    An end hidden over the range hands its face to the grid cap at the first ring that is (ring_taus hide: no rings
    walking across a face no one sees: the budget's trim; the coxa's, basis's and merus's distal ends, inside their
    children);
  - THE SAG-SPACED RINGS (the lead's call 4): X3's coxa ring and ischium weld are sag-spaced (K 16 / K 20); the coxa,
    its sleeve and the basi-ischium take the records' own angles (and the weld's K), so their columns line up;
  - THE DACTYL'S BASE (the lead's call 1): its flat base face (decapod_parts.dactyl_poly's 2 mm sink past the line from
    the gape's bottom to the knob, about 70 deg to the dactyl's axis) was crossed diagonally by rings normal to the
    smoothed centreline, four quads tilted 71-81 deg off the clay with corners out of the propodus; now the spine STARTS
    on the base face's normal (dactyl_spine: a Hermite curve from the face's normal into the plan centreline; Spine T0
    holds the planes on it over CAGE base_blend): the end rings lie parallel to the face and walk evenly over its rim.
    The base shows at 40 deg open, so it is built as a visible end;
  - §5.3's FEATURES on the crusher (the lead's call 2; x4-3; FEAT's comment, crusher_features): the occlusal rims
    creased on columns laid on them (occlusal_warp) and built crisp (their targets toward each ring's virtual corner),
    the two molars and the dactyl's lump as domes on the biting surfaces, the tubercle rows on the claw's margins, the
    carpus and the merus as knobs and spines, each extruded from the cage's own faces (one shell);
  - THE CUTTER'S CLAW (kind 'cutter', built on the left and mirrored): its propodus's wedge base handed to the grid cap
    early and the cap's grid rolled onto the wedge's ridge (CAGE cap_c_cutter, cap_roll_cutter).
X4c (the lead's calls on X4b, 10-29):
  - THE JOINTS (call 1): every membrane SKINNED to both shells (skin_cages, skin_w: the wrist membrane rides the carpus
    at X3's ring and the propodus from its last ring, each sleeve its parent at its proximal ring and its child from
    its distal one), so the wrist shows membrane at every pose and its cap stays inside the propodus; the shells stay
    single-influence. CLEARANCE by a swept field (each shell cleared of its partner's chitin swept over the range) was
    built and measured (x04 _x4c4): it broke gates 2 / 3 / 10 on every shell and the joints still passed chitin through
    chitin, so it is out (the sockets came as clay: X4e, below; x04 gate 9 measures what they must clear);
  - FEATURES SPLIT BY SCALE (call 2): the cage keeps the occlusal rims, the molars, the lump and the two spines; the
    tubercles, knobs and denticles are STROKES for X6 (STROKES, stroke_record, cutter_strokes); the domes and spines
    walked up their own profiles (profile_curve, walk_profile);
  - THE CUTTER (call 3): its base round (decapod_parts claw_polys: the 'wedge' was the base closure's spur), its fixed
    tip handed over early (a round end never meets the hand-over rule at cap_c 1); its build carries the proximal
    chain's own features (crusher_features claw False), so its proximal cages equal the crusher's;
  - THE CRUSHER'S HAND-OVER (call 4), measured and not taken: cap_c 1.5 on the knob and the dactyl's base saves 736
    quads (the claw inside 5.3's 6.1k) but its grid caps stand 0.96 / 0.67 mm off the clay where both show (the
    wrist's extremes, the claw open), against call 5's 0.3, and tilt on the dactyl's base; the knob's 0.85 mm (X4b) was
    the base closure's corner, rounded in the clay (decapod_parts CLAW base_round): 0.32 at cap_c 1.
X4e (the lead's calls on the X4d check, 10-30; the sockets the docstring's X4c left for later, in the clay: decapod_parts
SOCKET and KNEE):
  - THE CRUSHER'S CLAW: no joint_margin on its dactyl: the base is a fan sliding through the propodus's rim, chitin at every
    pose. On the cages: the propodus's occlusal columns run on up the rim's arch (s_band), so the rim is two columns, not a
    corner its limit cuts; notch_opening labels the rim's surface (OPENING, hidden at every pose; CRESCENT, the rim's
    ring); dactyl_edge labels the fan behind the hard edge (rigid, under the rim below open_lim - wedge); the dactyl's
    creases start past the heel, and x04's gate 9 reads the propodus's chitin without the socket. The closed limit is
    measured (MOTION claw; x04 gate 12). The hinge's two CONDYLES are domes extruded from the propodus's faces
    (FEAT condyle)
  - THE KNEE: the carpus's proximal end is the hard WHEEL (decapod_parts KNEE): region 'lump', chitin, in sight by design
    (no buried-condyle membrane; X4d's rode the merus and showed as a rounded pink end at the fold). Its sleeve lies
    wholly inside the carpus and rides it at every pose (skin_cages). The merus's and carpus's spines stay on the
    chitin side of their margins (spine_feet, joint_margin keep_out)
X4f (the lead's calls on the X4e check, 10-31; decapod_parts SOCKET two-armed, condyle_hinge):
  - THE HINGE under the top margin where the photos put it (n04's ball): BOTH claws socketed, each joint two-armed (the
    gape arm and the top arm round a cup disk on the axis); notch_opening labels both rays and the cup; claw_frames' base
    face is the chord between the two tongues' ends; cheliped_cages' dactyl pre-pass a longer reach, then the dactyl's own
    axis from the hinge, else a clear error (the X4e check's longer tongue left sleeve_depths a None)
  - THE CONDYLES: n04's ball on the hinge axis, a cage dome standing on the axis (extrude_patch normal) only where a
    centred loop holds it whole with a band (FEAT condyle_band / condyle_ecc), else a STROKE for X6 at n04's size
    (crusher_features: on this cage both claws'); a feature's foot faces are judged by the clay's normal (feature_outward)
  - THE WRIST over the rig's whole range, the CUTTER'S DACTYL about its own hinge (joint_motions: X4c-X4e turned it about
    the crusher's, 14.8 mm away). 3rd session: the rig's wrist shrunk (the cutter's base cap left the carpus near the old
    top: lobster.py's note); both claws' closed limits at their CLAY contact (decapod_parts clay_contact, the SPEC's hinge
    c: x02); notch_opening's band from the socket's bulge
  - 4th session: notch_opening's crescent also takes the rim quads the dactyl's clay COVERS at some pose but not at every
    pose (posed_inside_any; rim_f's T(r) under-reads the real trace where the dactyl's body passes its band's cap), and
    its cup piece reaches the hub's face (to the socket's `bear`, cover-only there); ring_taus cap_rmin stops a round
    end's rings at a radius (the cutter's base: CAGE cap_rmin_cutter)
X4h (the lead's calls on the X4g check, 11-08):
  - THE TRUE OFFSET (surface_distance, offset_true): x04's gate 10 reads the distance to a point found on the clay's
    surface (Newton onto it, slid to the nearest), not |field|, which reads short by |grad f| ~0.5-0.8 in the clay's
    smooth blends (the X4g check's 0.370 / 0.308 / 0.434 were 0.50 / 0.42 / 0.56; read true, the crusher's and the
    cutter's DACTYLS failed too: 0.59 / 0.32 at their bases)
  - THE CLAWS' REFIT (limit_refit, REFIT): the cells that bridge those blends refitted to the clay over their whole
    surface, the features and the creased rims held, the low kept on the clay; the low's tilts relaxed (relax_tilts)
  - THE CUTTER'S DACTYL (CAGE dactyl_cutter): 4 more columns inside its occlusal band (x04 gate 3's two 4.17 quads), its
    round tip's rings stopped at 1 mm (cap_rmin_cutter: at K 28 they walked to the pole and the limit folded)
UNITS: life mm in the plan frame of the bind (x the creature's left, y up, z forward); the step script writes x4 metres.
"""
import math

import numpy as np

from .. import subdiv_sharp as SS
from ..mesh import QuadMesh
from . import arthropod_cage as AC
from . import decapod_parts as DPP

VERSION = 'x4-6'                  # X4f
M_X = np.array([-1.0, 1.0, 1.0])
SLV = dict(in_child=0.84, step=0.36, step_min=0.4, step_max=3.0)     # X3's sleeve (x03_seams.SLV), life mm
# the cages' layout [D]: each part's K (columns) and its ring spacing as a share of its column spacing (2 pi r / K,
# rings about square to the columns), clamped (mm at life); phi_max the end rings' last tilt (deg) before the cap.
# K: the crusher chain's rings are X3's (coxa sleeve 16, basi-ischium weld 16, carpus sleeve 20, wrist 24), so the
# shells carrying or meeting them take those K (columns line up across a joint); the merus 20 (its sleeve into the
# carpus, K 20); the chelae from their size against §5.3's budget (the crusher's two parts about 6k triangles): the
# propodus 32 (a 140 mm round palm: 4.4 mm columns), the dactyl 24
CAGE = dict(K=dict(cheliped_coxa=16, cheliped_basis=16, cheliped_merus=20, cheliped_carpus=24, propodus=32, dactyl=24),
            spacing=1.0, h_min=0.3, h_max=3.5, phi_max=80.0, n_dense=(24, None, 24), dense_step=0.25,
            cap_c=1.0,        # a capped end's last ring: where the arc left to its pole is under this x its radius
            #                   (on a flat end the arc left IS the radius, so the rings walk on toward the pole and cover
            #                   the rim, the cap small at the centre: the ends' fidelity and the condyles' poles; 1.2 /
            #                   1.5 handed the rim to the grid cap: tilts there, the limit 0.55 mm off the clay at the
            #                   segments' ends against 0.19)
            turn_max=30.0,    # deg of the profile's turning between rings at most (ring_taus; 20 crowded a K 16 segment's
            #                   1.8 mm rims to rings 0.6 mm apart against 2.4 mm columns: aspect p99 4.4; 30: three
            #                   rings over a 90 deg rim)
            # X4b, THE CUTTER'S CLAW: each part's ends' hand-over (ring_taus cap_c, proximal / distal): its propodus's
            # base is a WEDGE (the base closure round the wrist on a 34 mm palm), and at cap_c 1.0 its proximal end
            # zone's 12 rings crowded within 1.8 mm onto the wedge's edge (aspect 47, min angle 3, 703 limit folds:
            # the X4 smoke test's 'rings piling at s -5.6..-4.3'); at 1.5 the grid cap takes the wedge from its first
            # end-zone ring (aspect p99 2.50, min angle p1 54.5, 1 limit fold; probe10); the dactyl's flat base alike.
            # X4c (3rd session): the base is ROUND now (decapod_parts claw_polys: the 'wedge' was the base closure's
            # spur), so it walks its rings again (1.0: the in-sight offset 0.17 mm, at 1.5 the grid cap stood 0.32 off;
            # probes cb1 / x04 _x4c5), and the propodus's FIXED TIP hands over early instead: on a ROUND end (c13's
            # 1.7 mm tip cap) the rule 'arc left <= cap_c x the ring's radius' never fires at 1.0 (x <= sin x), so the
            # rings walked to the pole and left an 8 x 8 cap of 0.05-0.11 mm edges whose limit folded (84 faces); X4b's
            # tip passed only by the luck of the spine's 0.5 mm grid (probe u3b / u4: at 1.5 0 folds, cap edges
            # 0.22-1.38 mm). X4f, 3rd session: the base stays at 1.0: at 1.25 / 1.5 its grid cap reached the base's rim and
            # stood 1.2-1.6 mm out of the carpus over most of the wrist's range (x04 gate 11, scratch x4f probe_wrist_cap,
            # probe_g23 t2); at 1.0 on the round base the rings walk to the pole unless the end is hidden over the range
            # (ring_taus hide): the rig's wrist range is what keeps it so (lobster.py rig.ranges.cheliped.wrist)
            cap_c_cutter=dict(propodus=(1.0, 1.5), dactyl=(1.5, 1.0)),
            # X4f, 4th session: ... but with the rig's wrist (-30, 55) its rings still walked to the pole (no ring there is
            # hidden at every wrist pose by ring_taus' test), the grid cap's centre quads 0.1 mm and 2 of them folding
            # the limit (x04 gate 2 counts folds hidden or not; scratch x4f probe_g23 t3, quads 2808 / 2815), and 1.1 handed
            # over 9 rings sooner, its low standing 0.6-1.5 mm out of the carpus over the range (probe x1): the rings stop
            # at this radius instead (ring_taus cap_rmin), the 8 x 8 cap's edges about r / 4. 1.0 drops the last ring before
            # the pole (0.8 never fires: the same folds, probe y5); at 1.3 / 2.0 the cap reached the base's surface that
            # meets the carpus at the wrist's top and showed from +40 / +30 rel (probes y4 / y1); at 1.0, 2 cap quads 0.04
            # mm inside at 55 abs against gate 11's 0.05 (probe y3): the rig's wrist top 52.5 (lobster.py)
            cap_rmin_cutter=dict(propodus=(1.0, None), dactyl=(None, 1.0)),
            # A0 (x6fix_x7, 11-11): THE CARPUS'S TWO POLES the same way. On the wrist ring's own K 32 and sag-spaced
            # angles (A0c) its rings walked to both poles (ring 0 at r 0.82 mm, the last at 0.43; X4h's K 24 round tube
            # did too, with even columns, and passed): the sag-spaced columns stand 0.03-0.17 mm apart there, the
            # membrane's last two bands read aspect 4-11 (x04 _a0e / _a0f gate 3: p99 4.97) and 5 quads of the distal
            # 8 x 8 grid cap folded the limit on 42 faces (gate 2 counts folds hidden or not). The rings stop at this
            # radius (proximal, distal; mm): the membrane 2.69, no fold (scratch x6fix_x7/claw/probe_arm_cage.py with
            # var_carpus_ends.py: runs/arm_ends_r2_r2.log)
            cap_rmin_carpus=(2.0, 2.0),
            # ... AND ITS COLUMNS FAN OUT EVENLY TOWARD THE KNEE. The wrist ring's sag-spaced angles are a rule about
            # ONE section (the fist at the wrist: columns 3.4 deg apart at its lateral corner, 11.25 on average); carried
            # to the knee's round wheel they left a column pair 0.12 mm apart on ring 0 (r 2.1), and that sliver quad
            # folded the limit on 2 faces beside the grid cap, in sight (the same trial: 'limit 2 / 3'). The columns
            # run on EQUAL angles up to u = carpus_fan[0] of the spine (the wheel and the neck), on the ring's own
            # from carpus_fan[1] (the fist's full girth, s 18 of 40), a smoothstep between (capped_tube th_fn)
            carpus_fan=(0.10, 0.45),
            # X4h: ... and the cutter DACTYL'S round TIP the same: at K 28 (dactyl_cutter) its rings walked to the pole
            # (the last at tau 2.99, the 7 x 7 grid cap's edges 0.05-0.08 mm) and the limit folded on 97 faces (scratch
            # x4h probe r1); at K 24 its rings had stopped short by luck
            # ... and X4b's roll of the base cap onto the wedge's RIDGE (its corners K/8 round the ring; probe12: low
            # tilts 7 -> 2), kept: on the round base it changes no gate (probe u2: roll 0 and 4 identical)
            cap_roll_cutter=dict(propodus=(4, 0)),
            turn_max_propodus=24.0,   # X4b: the propodus's own (its knob's lower rim turns ~76 deg over 1.8 mm; at 30
            #                   two quads there tilted 61-62 deg, hidden at rest and out at the wrist's extremes; 24 on
            #                   every shell pushed the coxa's aspect p99 to 4.45 and the dactyl's to 4.01, on the
            #                   propodus alone it keeps 2.73)
            # X4e: the crusher propodus's RINGS' PHASE: ring_taus's anchor, the spine's middle 1.5 by default. The socket's
            # clay curves fast on the cheek below the rim's end by G (s 78, m -5, t -10.5), under quads 5.5 mm long: the fit's
            # ripple there stood 0.315 mm off the clay at 1.5 (gate 10's 0.3); the same 68 rings moved along the spine read
            # 0.317 / 0.336 / 0.269 / 0.293 at 1.4875 / 1.4938 / 1.5062 / 1.5125 (scratch probe_turn; a lower turn_max
            # adds no ring there)
            anchor_crusher=1.5062,
            # X4g (the lead's call 3 on the X4f check: the rows round the cup): a socketed propodus keeps a ring through the
            # notch's APEX (the cup's distal point on the V's bisector, decapod_parts SOCKET's small boss): the sharp turn
            # there from the gape ray round the boss to the top ray, which the cutter's rings crossed diagonally (4 quads
            # tilted 61-63 deg in sight, scratch x4g probe_g23 A); a station within station_gap mm of arc of another is left
            # out (the crusher's anchor ring already runs 0.14 mm from its apex: two rings there made a 0.1 mm band whose
            # limit folded on 1028 faces, probe Aa)
            station_gap=1.0,
            # ... and one through the far end of a ray steeper than ray_steep deg to the claw axis (it runs along the rings,
            # so no column follows its lip: the cutter's gape ray at -73 deg, G's lip tilted 63-66 deg on 2 quads, probe B48;
            # through G: 0 / 0, probe B48g; the crusher's top ray at 87 deg ends at A, by its apex ring: left out)
            ray_steep=60.0,
            # X4g (call 3, the columns on the notch's rays): a socketed propodus's band warp lands its rim columns on the
            # gape ray's edges, and the next column out stood ~11 deg further on the broad face: one cell bridged the
            # collar wall's fillet beside the rim, the limit 0.3-0.4 mm off it in a strip along the ray (scratch x4g look
            # cage_crusher_M1: 46 vertices, 0.397). So over the ray's span those columns stand foot_pull deg outside each
            # rim (probe_g23 crusher, pull 3 / 5 / 7: 183 v 0.401 / 31 v 0.378 / 29 v 0.370, the strip gone, what is left
            # by the boss; out at the far concave turn, 41-73 deg: 439 v 0.704)
            foot_pull=7.0,
            # X4h (the lead's call 3 on the X4g check, gate 3): THE CUTTER'S DACTYL takes 4 more columns, ALL INSIDE ITS
            # OCCLUSAL BAND (its rims at +-cols columns about the band's centre, occlusal_warp; 4 quads across before): the
            # band runs 3.0-3.3 mm wide between its creased rims, and over the base's 0.86 mm ring step (the fan, X4g's
            # open limit 55) its two outer quads read aspect 4.14 / 4.17. The long side is across the band, so the split is
            # columns; the 20 columns outside the band are unchanged (K 24 -> 28, the grid caps 7 x 7)
            # ... and its rims' virtual corner (crusher_features) reads the band's line through its 2nd and 3rd columns from
            # each rim (band_nb; the claws' default (1, 2) on 4-column bands): at (1, 2) on the 8-column band the rims read
            # 0.385-0.447 mm (x04 gate 8 failed), at (2, 4) 0.204-0.293 with 267 limit faces tilted beside them; (1, 3)
            # 0.352-0.392, (2, 4) at share 0.6 0.298-0.386, (2, 3) 0.228-0.304, each 0 tilts and gate 10 0.175 (scratch x4h)
            # x6fix_x7 (11-11): 'anchor', its rings' phase (claw_cage anchor, as anchor_crusher; absent = the spine's
            # middle): the socket's cap step, a hard crease near the hinge axis on both broad faces (X4g B48, X4h r3's
            # tilt_probe), ran through ring 0's hidden cells on X4h's dactyl; A0's round outer margin changed the arc the
            # walk divides, its first rings came ~0.25 mm further out and an extra ring stood by the pole, and the crease
            # crossed ring 2's cells IN SIGHT (x04 _a0f gate 2 'low 0 / 2': quads 60 / 79 at 62-63 deg). The crease is
            # the socket CUP's arc on the dactyl (r 1.5-2.2 mm about the hinge axis, phi -8..+40, both faces): a circle
            # no ring or column follows. The scan (scratch x6fix_x7 run_anchor_scan.sh, claw/probe_claw.py GPU=1 ONLY=
            # dactyl; the shift of every ring along the 65.89 mm spine): 0 -> 2 in sight + 2 hidden; -0.15 -> 2 in sight
            # (63 deg); -0.3 -> 2 (X4h's own quads 3 / 24, now in sight); +0.3 -> 4; -0.6 -> NONE, hidden or not, and
            # the dactyl's other rows pass (gate 8 0.227-0.302, gate 10 max 0.187, gate 3 cap 34.7 / 1.74, chitin
            # 62.8 / 1.86, membrane 73.7 / 1.76). X4h's tilt_slide tried too: the refit after it re-tilts quads 60 / 79
            dactyl_cutter=dict(K=28, cols=4, band_nb=(2, 3), anchor=1.49089),
            tilt_deg=55.0, relax_rounds=40, relax_lam=0.5,   # relax_ends: an end zone with a quad tilted more than
            #                   this off a corner's clay normal (x04's gate 60 deg, a margin of 5) is relaxed on the clay
            # a claw part's spine: the plan interval's middle, Gaussian-smoothed (mm along s); its ends this share of
            # the end's half-width in from the plan's extreme (the end nodes inside the shell)
            spine_sigma=4.0, spine_end=0.55, spine_step=0.5,
            # the ring planes' normal: the spine's tangent smoothed over this arc (mm; Spine plane_sigma): the crusher's
            # centreline turns ~40 deg over 15 mm at the gape under a palm ~30 mm half-high, so planes normal to it
            # crossed there; smoothed over 15 mm they turn ~1 deg / mm, 30 mm x 0.0175 = 0.5 < 1: no crossing
            plane_sigma=15.0,
            # X4b: a trimmed condyle's cut face is rounded into its side by cut_k (mm, a smooth intersection), and its
            # spine starts cut_in (x cut_k) distal of the cut
            cut_k=1.0, cut_in=1.6,
            # X4b, THE DACTYL'S SPINE (dactyl_spine): from its base face's centre, base_in x the face's half-length inside
            # it, along the face's normal, a Hermite curve joining the plan centreline at join x the dactyl's length, then
            # the centreline; the planes held on the normal over the first base_blend mm (Spine T0: the smoothing would
            # pull them off it). x4-2's first try (the planes blended from the normal onto the plan centreline over 8 mm)
            # crossed them: that centreline dips 35 deg toward the gape along the slanted base while the normal rises 34
            base_in=0.30, join=0.50, base_blend=6.0)
# X4b, the lead's call 3: THE MOTION RANGES (module docstring): the claw open 0-40 deg (absolute; the bind at
# rig.cheliped.dactyl_open); the wrist X4b-X4e -30..+40 deg from the bind (the lead's: X7's clip), X4f (the lead's call 4)
# the rig's whole range rig.ranges.cheliped.wrist (absolute: joint_motions); the other cheliped joints over the rig's
# ranges; samples every `step` deg; a face or a cut is hidden when it lies `margin` mm inside the fixed shells at every
# pose; a trimmed condyle keeps at least `keep` mm behind its sleeve's proximal ring (the sleeve stays inside its child)
# X4e (the lead's call 3 on the X4d check): the claw's closed limit is where the crusher's occlusal edges meet, MEASURED on
# the level-3 limits by x04 gate 12, which holds it there: on the socket's clay the molars first touch at 0.16 deg open
# (it moved 0.05-0.34 with the cage's rounds), so the rig's own 0 (plan 10.3) is the contact, the fingers -0.09 mm there
MOTION = dict(claw=(0.0, 40.0), step=2.5, margin=0.5, cut_step=0.25, keep=0.5)
LEVELS = dict(out=3)              # the limit mesh's levels for the gates and the views (the fit's: crease-sharpness led)
CAP_RELAX = 12                    # a grid cap's rounds of umbrella smoothing (each pushed back onto the clay)


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def plane_frame(axis, side='L'):
    """X3's ring frame (x03_seams.plane_frame): Z the axis, X slots.port_frame's tangent made perpendicular, Y = Z x X"""
    from ...remix import slots as SL
    pf = SL.port_frame(np.asarray(axis, np.float64).tolist(), 'L' if side == 'R' else side)
    Z, X = unit(pf['normal']), unit(pf['tangent'])
    X = unit(X - Z * (X @ Z))
    return Z, X, np.cross(Z, X)


def rotate_onto(a, b):
    """the least rotation (3 x 3) taking unit a onto unit b"""
    a, b = unit(a), unit(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3) if c > 0 else -np.eye(3)
    K_ = np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])
    return np.eye(3) + K_ + K_ @ K_ * (1.0 / (1.0 + c))


# ============================================================================================ the clay as a field
# A0b (x6fix_x7, 11-10): THE CLAY'S FIELD ON SEVERAL THREADS. x04 runs on the CPU, and a part's eval is one Warp CPU
# kernel launched through ctypes (the GIL released while it runs); every point's value is its own, so a big batch cut
# into chunks and evaluated side by side returns the SAME bytes in the same order (scratch x6fix_x7/p4/
# probe_threads.py: 200,000 points on the crusher propodus, 8 threads 6.5 times faster, max |diff| 0). On one thread
# x04's crusher chain alone took 6,043 s (X4h's r3: 105 min). A batch under 2 x chunk points runs as before; the
# first chunk runs alone on the calling thread (a program's first eval builds its device arrays). threads 1 = off
EVAL = dict(threads=8, chunk=4096)
_EVAL_POOL = []


def _eval_pool():
    if not _EVAL_POOL:
        from concurrent.futures import ThreadPoolExecutor
        _EVAL_POOL.append(ThreadPoolExecutor(int(EVAL['threads'])))
    return _EVAL_POOL[0]


class Field:
    """the union of named clay parts (decapod_parts.Part, x4 metres) seen in life mm: eval, normals, ray casts"""

    def __init__(self, parts, names, sc):
        self.parts, self.names, self.sc = parts, list(names), float(sc)

    def _eval1(self, P):
        return np.min(np.stack([self.parts[n].eval(P * self.sc) for n in self.names]), axis=0) / self.sc

    def eval(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        n, ch = len(P), int(EVAL['chunk'])
        if int(EVAL['threads']) < 2 or n < 2 * ch:
            return self._eval1(P)
        cuts = np.array_split(np.arange(n), max(2, min(4 * int(EVAL['threads']), n // ch)))
        first = self._eval1(P[cuts[0]])
        rest = list(_eval_pool().map(lambda ix: self._eval1(P[ix]), cuts[1:]))
        return np.concatenate([first] + rest)

    def normals(self, P, e=1.0e-3):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        g = np.stack([(self.eval(P + d) - self.eval(P - d)) for d in np.eye(3) * e], 1)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)

    def cast(self, O, D, tmax=60.0, step=0.1):
        """each ray's FIRST EXIT (inside -> outside), life mm along it; nan where it starts outside or never leaves
        (x03_seams.cast's rule, a finer march)"""
        O, D = np.atleast_2d(O).astype(np.float64), np.atleast_2d(D).astype(np.float64)
        O = np.broadcast_to(O, D.shape)
        n = len(D)
        ts = np.arange(0.0, tmax + step, step)
        f = self.eval((O[:, None, :] + ts[None, :, None] * D[:, None, :]).reshape(-1, 3)).reshape(n, -1)
        out = np.full(n, np.nan)
        ok = f[:, 0] < 0.0
        hit = (f[:, :-1] < 0.0) & (f[:, 1:] >= 0.0)
        has = ok & hit.any(axis=1)
        j = np.argmax(hit, axis=1)
        lo, hi = ts[j].copy(), ts[np.minimum(j + 1, len(ts) - 1)].copy()
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            inside = self.eval(O + mid[:, None] * D) < 0.0
            lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
        out[has] = 0.5 * (lo + hi)[has]
        return out


class CapsuleUnion:
    """a field united with a capsule (the segment p0-p1, radius r, life mm): a CONDYLE lengthened where the clay's
    child barely reaches into its parent (condyle(); none of the crusher's joints needs it at the bind); the capsule
    lies inside the parent, hidden, and casts as Field"""

    def __init__(self, base, p0, p1, r):
        self.base, self.p0, self.p1, self.r = base, np.asarray(p0, np.float64), np.asarray(p1, np.float64), float(r)

    def eval(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        ab = self.p1 - self.p0
        t = np.clip(((P - self.p0) @ ab) / max(float(ab @ ab), 1e-18), 0.0, 1.0)
        cap = np.linalg.norm(P - (self.p0[None, :] + t[:, None] * ab[None, :]), axis=1) - self.r
        return np.minimum(self.base.eval(P), cap)

    normals = Field.normals
    cast = Field.cast


class CutField:
    """X4b: a field cut by the plane through p_cut normal to `axis` (unit, pointing into the part): everything proximal
    of the plane removed by a smooth intersection (the cut's rim rounded over k mm): a TRIMMED CONDYLE (cut_depth),
    whose cut face stays hidden over the motion range; casts as Field"""

    def __init__(self, base, p_cut, axis, k):
        self.base, self.p, self.a, self.k = base, np.asarray(p_cut, np.float64), unit(axis), float(k)

    def eval(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        a_, b_ = self.base.eval(P), (self.p[None, :] - P) @ self.a
        h_ = np.maximum(self.k - np.abs(a_ - b_), 0.0) / self.k
        return np.maximum(a_, b_) + h_ * h_ * self.k * 0.25

    normals = Field.normals
    cast = Field.cast


def field_grad(field, P, e=1.0e-3):
    """X4h: the field's gradient (central differences, life mm), (n, 3)"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    return np.stack([(field.eval(P + d) - field.eval(P - d)) / (2.0 * e) for d in np.eye(3) * e], 1)


def surface_distance(field, P, newton=12, slide=10, tol=1.0e-5):
    """X4h (the lead's call 1 on the X4g check: x04's gate 10 read |field|, and the clay's smooth unions have |grad f|
    0.73-0.80 in their blends, so it printed 0.370 / 0.308 / 0.434 where the true distances were 0.50 / 0.42 / 0.56 mm):
    the TRUE distance from each point P to the field's zero set (the clay's surface), as the distance to a point FOUND
    ON that surface: Newton steps X -= f g / |g|^2 onto f = 0, then the foot slid along the surface toward P (X moved by
    the tangential part of P - X and put back on the surface; a step kept only where it brings X nearer P) until P - X
    lies along the normal (the nearest point's condition). Every foot lies on the surface (|f(X)| returned as the
    residual), so the distance is never less than the nearest one; the slide makes it the nearest locally. Returns
    (distance mm, the feet X (n, 3), |f(X)|, |grad f| at P)"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    g0 = np.linalg.norm(field_grad(field, P), axis=1)

    def onto(X, k):
        for _ in range(k):
            f = field.eval(X)
            g = field_grad(field, X)
            X = X - (f / np.maximum((g * g).sum(1), 1e-12))[:, None] * g
        return X
    X = onto(P.copy(), newton)
    d = np.linalg.norm(P - X, axis=1)
    for _ in range(slide):
        g = field_grad(field, X)
        n = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)
        r = P - X
        t_ = r - (r * n).sum(1)[:, None] * n
        if float(np.abs(t_).max()) < tol:
            break
        todo = np.ones(len(P), bool)
        for h_ in (1.0, 0.5, 0.25, 0.125):               # (a step that lands no nearer is halved: X4h's dactyl plant
            idx = np.nonzero(todo)[0]                    # read one point 0.489 for 0.35, its full step overshooting)
            if not len(idx):
                break
            Xn = onto(X[idx] + h_ * t_[idx], 4)
            dn = np.linalg.norm(P[idx] - Xn, axis=1)
            ok = (dn < d[idx]) & (np.abs(field.eval(Xn)) < 1.0e-4)
            X[idx[ok]], d[idx[ok]] = Xn[ok], dn[ok]
            todo[idx[ok]] = False
    return d, X, np.abs(field.eval(X)), g0


OFFSET = dict(screen=0.1)         # X4h: offset_true measures by surface_distance every point whose first-order distance
#                                   |f| / |grad f| exceeds this (mm); the rest read that estimate (within second order)


def offset_true(field, P, screen=None):
    """X4h: the distance from each point P to the clay's surface (field's zero set), mm: surface_distance where the
    first-order estimate |f| / |grad f| exceeds OFFSET screen, that estimate elsewhere. Returns (distance, |f|, |grad f|,
    the measured mask)"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    screen = OFFSET['screen'] if screen is None else float(screen)
    f = np.abs(field.eval(P))
    g = np.linalg.norm(field_grad(field, P), axis=1)
    d = f / np.maximum(g, 1e-6)
    m = d > screen
    if m.any():
        d[m] = surface_distance(field, P[m])[0]
    return d, f, g, m


CONDYLE = dict(depth=0.22, step=0.25, max_ext=8.0, r_share=0.8,  # a child's end reaches this x r deep into its parent
               #                                                    at least (r its mean half-size at the joint; x04's
               #                                                    gate 0.20, the plan's 0.2-0.3 r: a margin for the
               #                                                    limit's ~0.05 mm off the clay)
               # A0 (x6fix_x7, 11-11): THE LENGTHENING MUST BUY DEPTH: the walk goes on only while a step deepens the pole
               # by at least `gain` x the step. On the A0 clay the carpus's pole stands 1.220 mm in the merus (0.19 r, the
               # bar 1.42) and at the 91 deg bind its axis runs ALONG the merus's end face: 19 steps bought 0.083 mm
               # (0.0175 mm a mm), and the 4.75 mm capsule (r 4.72) they left stood 2.15 mm OUT of the merus at the bind
               # and 5.19 mm at the knee's fold end (scratch x6fix_x7/claw/probe_knee_condyle.py; x04 _a0f: gate 9's
               # 7895 wheel points 1.13 mm outside, gate 2's ring 0 'in sight'). A walk INTO the parent gains ~1 a step
               # (x04 _a0 on 11-10: 1.00 mm for its 0.2). The carpus's end is the knee's WHEEL, in sight by design, and
               # x04's gate 5 reads it 16 mm behind X0: it needs no capsule
               gain=0.25)


def condyle(name, field, parent, a0, axis, rho, half):
    """a child's CONDYLE in its parent, the plan's 'sunk 0.2-0.3 r in its parent' measured as the beetle's b03 measures
    it: the deepest point of the child's end inside the parent (its clay pole, rho behind its proximal node a0 along
    the axis). The clay sinks each child SINK_FRAC 0.25 of its least half-size behind its joint, so every crusher joint
    meets CONDYLE depth (the carpus at the knee closest: its pole 1.89 mm in the merus, 0.25 r). A child short of it
    is LENGTHENED back along its axis, hidden (a capsule, CapsuleUnion), only while that deepens it: at a bent joint
    the child's axis crosses its parent and past the deepest point heads for the far wall (x4-1's first search ran on
    to its 8 mm cap and out of the merus). Returns (field, spine start, dict)"""
    rbar = float(np.mean(half))
    depth_at = lambda e: -float(parent.eval((a0 - (rho + e) * axis)[None, :])[0])   # noqa: E731
    d_clay = depth_at(0.0)
    ext, d0 = 0.0, d_clay
    while d0 < CONDYLE['depth'] * rbar and ext < CONDYLE['max_ext']:
        d1 = depth_at(ext + CONDYLE['step'])
        if d1 - d0 < CONDYLE['gain'] * CONDYLE['step']:   # (A0: no depth bought, CONDYLE gain; was d1 <= d0)
            break
        ext += CONDYLE['step']
        d0 = d1
    info_ = dict(rbar=rbar, depth_clay=d_clay, ext=ext, depth=d0)
    if ext <= 0.0:
        return field, a0, info_
    return CapsuleUnion(field, a0, a0 - ext * axis, CONDYLE['r_share'] * float(np.min(half))), a0 - ext * axis, info_


# ============================================================================================ spines
class Spine:
    """a shell's spine: points P (n, 3) with tangents T and a frame X (parallel-transported from X0, perpendicular to
    T), Y = T x X (so a ring's vertex k at angle th_k from X toward Y is right-handed about T); at(u) at the arc
    fraction u. plane_sigma (mm): every ring's plane normal to the spine's tangent SMOOTHED over this much of its arc
    (the chelae, x4-1: rings normal to the curved centreline crossed on the inside of its bend at the gape, where the
    palm is wider than the bend's radius; heavily smoothed, the planes turn slower than the section is wide, and at
    the fingertip they face along the finger, so the end rings tilt about their own plane's normal); the end caps'
    axes the smoothed tangent's ends. X4b: T0 (unit) the planes' normal at the start instead (the dactyl's base face),
    turned onto the smoothed tangent by a smoothstep over the first t0_blend mm of arc (the proximal cap's axis T0)"""

    def __init__(self, P, X0, plane_sigma=None, T0=None, t0_blend=None):
        P = np.asarray(P, np.float64)
        if len(P) == 2:
            P = P[0][None, :] + np.linspace(0.0, 1.0, 9)[:, None] * (P[1] - P[0])[None, :]
        self.P = P
        G = np.gradient(P, axis=0)
        if plane_sigma:
            from scipy.ndimage import gaussian_filter1d
            step = float(np.mean(np.linalg.norm(np.diff(P, axis=0), axis=1)))
            G = gaussian_filter1d(unit(G), plane_sigma / max(step, 1e-9), axis=0, mode='nearest')
        G = unit(G)
        if T0 is not None:
            s_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
            w = np.clip(s_ / max(float(t0_blend or 1.0), 1e-9), 0.0, 1.0)
            w = (w * w * (3.0 - 2.0 * w))[:, None]
            G = unit((1.0 - w) * unit(T0)[None, :] + w * G)
        self.T = G
        self.T_end = (self.T[0].copy(), self.T[-1].copy())
        X = np.zeros_like(P)
        x = unit(np.asarray(X0, np.float64) - self.T[0] * float(np.asarray(X0) @ self.T[0]))
        X[0] = x
        for i in range(1, len(P)):                      # parallel transport: the least rotation T[i-1] -> T[i]
            x = rotate_onto(self.T[i - 1], self.T[i]) @ x
            x = unit(x - self.T[i] * float(x @ self.T[i]))
            X[i] = x
        self.X = X
        self.s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        self.L = float(self.s[-1])

    def at(self, u):
        x = float(np.clip(u, 0.0, 1.0)) * self.L
        i = int(np.clip(np.searchsorted(self.s, x) - 1, 0, len(self.s) - 2))
        w = (x - self.s[i]) / max(self.s[i + 1] - self.s[i], 1e-300)
        P = (1 - w) * self.P[i] + w * self.P[i + 1]
        T = unit((1 - w) * self.T[i] + w * self.T[i + 1])
        X = unit((1 - w) * self.X[i] + w * self.X[i + 1])
        X = unit(X - T * float(X @ T))
        return P, T, X, np.cross(T, X)

    def u_of(self, P):
        """the arc fraction of the spine point nearest P (on the polyline)"""
        best = (1e18, 0.0)
        for i in range(len(self.P) - 1):
            a, b = self.P[i], self.P[i + 1]
            t = float(np.clip((P - a) @ (b - a) / max(float((b - a) @ (b - a)), 1e-18), 0.0, 1.0))
            d = float(np.linalg.norm(a + t * (b - a) - P))
            if d < best[0]:
                best = (d, (self.s[i] + t * (self.s[i + 1] - self.s[i])) / self.L)
        return best[1]


# ============================================================================================ casting a capped tube
def profile_dirs(spine, tau, th, phi_max):
    """the rays of the profile at tau (0..1 the proximal end's tilt from phi_max to 0, 1..2 the spine, 2..3 the distal
    end's tilt to phi_max): (origin, (K, 3) directions, the in-plane radial directions, tilt rad)"""
    if tau < 1.0:
        P, T, X, Y = spine.at(0.0)
        A, phi = -spine.T_end[0], phi_max * (1.0 - tau)
    elif tau <= 2.0:
        P, T, X, Y = spine.at(tau - 1.0)
        A, phi = T, 0.0
    else:
        P, T, X, Y = spine.at(1.0)
        A, phi = spine.T_end[1], phi_max * (tau - 2.0)
    r = np.cos(th)[:, None] * X[None, :] + np.sin(th)[:, None] * Y[None, :]
    return P, unit(np.cos(phi) * r + np.sin(phi) * A[None, :]), r, phi, A


def cast_profile(field, spine, taus, th, phi_max, tmax=80.0, scale=1.0):
    """the rings' targets at the profile stations taus: (n, K, 3); raises where a ray finds no surface"""
    out = []
    for tau in taus:
        P, D, _, _, _ = profile_dirs(spine, tau, th, phi_max)
        t = field.cast(P, D, tmax)
        if not np.isfinite(t).all():
            raise RuntimeError(f'a ray of the profile at tau {tau:.3f} found no surface ({int((~np.isfinite(t)).sum())} '
                               f'of {len(t)}): the spine leaves the shell')
        out.append(P[None, :] + (scale * t)[:, None] * D)
    return np.stack(out)


def ring_taus(field, spine, th, phi_max, fixed=(), h_fn=None, n_dense=(12, None, 12), dense_step=0.25, caps=(True, True),
              tmax=80.0, cap_c=None, hide=(None, None), turn_max=None, cap_rmin=None):
    """the profile stations of the rings, spaced by the LOCAL column spacing (CAGE spacing x each dense ring's own,
    clamped h_min .. h_max: the normalised arc N = the integral of dS / h, S the mean distance between neighbouring
    rings' points): equal steps of N between the fixed stations (taus that must be rings: X3's records) and the open
    ends; toward a pole (a capped end) the rings walk out one step of N at a time from the last fixed station (none:
    the spine's middle) and stop once the arc left to the pole is under CAGE cap_c x the ring's own radius (the grid
    cap is square at any radius; x4-1: one spacing for the whole profile left the rings sweeping a broad flat end at
    aspect 5-8 against their shrinking columns, and rings AT a pole are loops no cap takes). caps (proximal, distal):
    False ends the profile at the spine's end (an open end, itself a ring). h_fn is not used (kept for the call's
    shape). cap_c (proximal, distal): each end's hand-over (default CAGE cap_c). X4b, hide (proximal, distal): a
    callable(ring points (K, 3)) -> True when they are HIDDEN OVER THE MOTION RANGE; walking toward that pole the rings
    stop at the first ring past the spine's end that is (the grid cap covers the rest: no rings across a face no one
    sees, the budget's trim). turn_max: the profile's turning between rings at most (default CAGE turn_max). X4f, 4th
    session, cap_rmin (proximal, distal; mm or None): walking toward that pole the rings also stop at the first ring past
    the spine's end whose radius is under it (on a ROUND end cap_c 1.0 never fires, x <= sin x, and the rings walk to the
    pole: the X4c tip's failure, the cutter's base in X4f's probes). Returns the taus, sorted, and the dense profile (taus,
    S)"""
    cap_c = (CAGE['cap_c'], CAGE['cap_c']) if cap_c is None else cap_c
    cap_rmin = (None, None) if cap_rmin is None else cap_rmin
    turn_max = CAGE['turn_max'] if turn_max is None else float(turn_max)
    n0, n_s, n1 = n_dense
    n_s = n_s or max(16, int(spine.L / dense_step))
    t0 = np.linspace(0.0, 1.0, n0, endpoint=False) if caps[0] else np.zeros(0)
    t1 = 2.0 + np.linspace(0.0, 1.0, n1 + 1)[1:] if caps[1] else np.zeros(0)
    taus = np.concatenate([t0, 1.0 + np.linspace(0.0, 1.0, n_s), t1])
    R = cast_profile(field, spine, taus, th, phi_max, tmax)
    arc = np.concatenate([[0.0], np.mean(np.linalg.norm(np.diff(R, axis=0), axis=2), axis=1)])
    S = np.cumsum(arc)
    col = np.mean(np.linalg.norm(np.roll(R, -1, axis=1) - R, axis=2), axis=1)
    rad = []
    for tau, Rr in zip(taus, R):                         # each ring's radius about its own axis line
        P, _, _, _, A = profile_dirs(spine, tau, th, phi_max)
        q = Rr - P[None, :]
        rad.append(float(np.mean(np.linalg.norm(q - (q @ A)[:, None] * A[None, :], axis=1))))
    rad = np.array(rad)
    h = np.clip(CAGE['spacing'] * col, CAGE['h_min'], CAGE['h_max'])
    # the profile's TURNING: per column the angle between successive steps, its MEAN over the columns per mm; no more
    # than CAGE turn_max of it between rings (x4-1: quads straddling a blunt end's tight rim read tilted 60 deg off
    # the clay's normals at their corners; a rim turns every column together, while the sharpest single column also
    # reads a palm edge's smoothed tubercle wiggles and crowded the palm's rings to aspect 6.6)
    st_ = R[1:] - R[:-1]
    st_ /= np.maximum(np.linalg.norm(st_, axis=2, keepdims=True), 1e-12)
    turn = np.degrees(np.arccos(np.clip(np.sum(st_[1:] * st_[:-1], axis=2), -1.0, 1.0))).mean(axis=1)
    rate = np.concatenate([[0.0], turn / np.maximum(0.5 * (arc[1:-1] + arc[2:]), 1e-6), [0.0]])
    h = np.minimum(h, np.where(rate > 1e-9, turn_max / np.maximum(rate, 1e-9), np.inf))
    h = np.maximum(h, CAGE['h_min'])
    N = np.concatenate([[0.0], np.cumsum(np.diff(S) * 0.5 * (1.0 / h[1:] + 1.0 / h[:-1]))])
    t_of = lambda n_: float(np.interp(n_, N, taus))                       # noqa: E731
    lo_t, hi_t = float(taus[0]), float(taus[-1])
    anchors = sorted(set(float(f) for f in fixed))
    if not caps[0]:
        anchors = [lo_t] + anchors
    if not caps[1]:
        anchors = anchors + [hi_t]
    if not anchors:
        anchors = [1.5]
    anchors = sorted(set(anchors))
    out = list(anchors)
    for a, b in zip(anchors[:-1], anchors[1:]):           # interior: equal steps of N
        Na, Nb = float(np.interp(a, taus, N)), float(np.interp(b, taus, N))
        n = max(1, int(round(Nb - Na)))
        out += [t_of(Na + (Nb - Na) * i / n) for i in range(1, n)]
    S_end = {0: float(S[0]) - float(rad[0]), 1: float(S[-1]) + float(rad[-1])}       # the true poles, about one radius on
    for end, closed in enumerate(caps):
        if not closed:
            continue
        a = anchors[0] if end == 0 else anchors[-1]
        Na = float(np.interp(a, taus, N))
        sgn = -1.0 if end == 0 else 1.0
        k = 1
        while True:
            Nk = Na + sgn * k
            if (end == 0 and Nk <= N[0]) or (end == 1 and Nk >= N[-1]):
                break
            tk = t_of(Nk)
            left = abs(S_end[end] - float(np.interp(tk, taus, S)))
            out.append(tk)
            in_end = tk < 1.0 if end == 0 else tk > 2.0    # the hand-over only past the spine's end (x4-1: tested on a
            #                                                short segment's barrel it gave half the coxa to the cap)
            if in_end and left <= cap_c[end] * float(np.interp(tk, taus, rad)):
                break
            if in_end and cap_rmin[end] is not None and float(np.interp(tk, taus, rad)) < cap_rmin[end]:
                break
            if in_end and hide[end] is not None and hide[end](cast_profile(field, spine, [tk], th, phi_max, tmax)[0]):
                break
            k += 1
    return np.array(sorted(set(np.round(out, 12)))), (taus, S)


def grid_cap(cg, ring_ids, field, node, axis, phi_ring, flip, tmax=80.0, relax=CAP_RELAX):
    """a GRID CAP (x4-1: arthropod_cage's m x 2 cap stretched its side quads to aspect 6 at K 20): an n x n quad patch,
    n = K / 4, its boundary the ring (its four corners on the ring's axis vertices 0, K/4, K/2, 3K/4: the four
    valence-3 poles, as the m x 2 cap's four). Its interior nodes: the discrete Coons patch of the ring's own points,
    each pushed onto the clay along the cap's axis (`axis`, outward), then `relax` rounds of umbrella smoothing over
    the grid, each followed by the same push (x4-1: rays fanned from the end node collapsed quads on the chelae's
    broad blunt base and flat dactyl cut, min angle 0); a node the push misses takes its ray from the end node, the
    ring's tilt at the rim to the pole at the centre. Returns the interior ids"""
    L = list(ring_ids)
    K = len(L)
    n = K // 4
    V = cg.V
    B = {}
    for i in range(n + 1):
        B[(i, 0)] = L[i]
        B[(n, i)] = L[n + i]
        B[(n - i, n)] = L[(2 * n + i) % K]
        B[(0, n - i)] = L[(3 * n + i) % K]
    axis = unit(axis)
    node = np.asarray(node, np.float64)
    c0 = np.mean(V[L], axis=0)
    X = unit(V[L[0]] - c0 - axis * float((V[L[0]] - c0) @ axis))
    Y = np.cross(axis, X)
    Rr = float(np.mean(np.linalg.norm(V[L] - c0, axis=1)))

    def push(P):
        """each point moved along the axis onto the clay: the first exit from its line's point 1 mm behind the end
        node's level (inside the shell under the end ring's footprint)"""
        O = P - (((P - node) @ axis) + 1.0)[:, None] * axis[None, :]
        t = field.cast(O, np.repeat(axis[None, :], len(P), axis=0), tmax, step=0.05)
        ok = np.isfinite(t)
        out = P.copy()
        out[ok] = O[ok] + t[ok, None] * axis[None, :]
        return out, ok

    def fallback(P):
        """the end node's ray toward each point's angle, tilted by its normalised radius"""
        out = []
        for p in P:
            q = p - c0
            rho = float(np.clip(np.linalg.norm(q - axis * float(q @ axis)) / max(Rr, 1e-9), 0.0, 1.0))
            psi = math.atan2(float(q @ Y), float(q @ X))
            ph = phi_ring + (0.5 * math.pi - phi_ring) * (1.0 - rho)
            out.append(math.cos(ph) * (math.cos(psi) * X + math.sin(psi) * Y) + math.sin(ph) * axis)
        D = np.array(out).reshape(-1, 3)
        t = field.cast(np.repeat(node[None, :], len(D), axis=0), D, tmax)
        if not np.isfinite(t).all():
            raise RuntimeError(f'{cg.name}: a cap ray found no surface')
        return node[None, :] + t[:, None] * D
    keys = [(i, j) for i in range(1, n) for j in range(1, n)]
    ids = {}
    if keys:
        P3 = {k_: V[v] for k_, v in B.items()}
        pts = []
        for i, j in keys:
            u, w = i / n, j / n
            pts.append((1 - w) * P3[(i, 0)] + w * P3[(i, n)] + (1 - u) * P3[(0, j)] + u * P3[(n, j)]
                       - ((1 - u) * (1 - w) * P3[(0, 0)] + u * (1 - w) * P3[(n, 0)] + u * w * P3[(n, n)]
                          + (1 - u) * w * P3[(0, n)]))
        Pi = np.array(pts)
        Pi, ok = push(Pi)
        if not ok.all():
            Pi[~ok] = fallback(Pi[~ok])
        idx = {k_: a for a, k_ in enumerate(keys)}
        for _ in range(relax):
            G_ = dict(P3)
            G_.update({k_: Pi[a] for k_, a in idx.items()})
            Pn = np.array([0.25 * (G_[(i - 1, j)] + G_[(i + 1, j)] + G_[(i, j - 1)] + G_[(i, j + 1)]) for i, j in keys])
            Pp, ok = push(Pn)
            Pi = np.where(ok[:, None], Pp, Pi)
        new = cg.add(Pi)
        ids = dict(zip(keys, new))
    G = dict(B)
    G.update(ids)
    for i in range(n):
        for j in range(n):
            q = (G[(i, j)], G[(i + 1, j)], G[(i + 1, j + 1)], G[(i, j + 1)])
            cg.Q.append(q[::-1] if flip else q)
    return list(ids.values())


def band_tilts(R, field):
    """per ring band (n - 1, K): each quad's least cosine between its normal (by its diagonals) and the clay's normals
    at its four corners, x04's gate 2 on the low; the band's outward sense from its median; and the quads' centres"""
    Nc = field.normals(R.reshape(-1, 3)).reshape(R.shape)
    A_, B_ = R[:-1], R[1:]
    nq = np.cross(np.roll(B_, -1, axis=1) - A_, B_ - np.roll(A_, -1, axis=1))
    nq /= np.maximum(np.linalg.norm(nq, axis=2, keepdims=True), 1e-20)
    corners = (Nc[:-1], np.roll(Nc[:-1], -1, axis=1), np.roll(Nc[1:], -1, axis=1), Nc[1:])
    dq = np.min(np.stack([np.sum(nq * c_, axis=2) for c_ in corners]), axis=0)
    dq *= np.sign(np.median(dq, axis=1, keepdims=True) + 1e-12)
    cen = 0.25 * (A_ + B_ + np.roll(A_, -1, axis=1) + np.roll(B_, -1, axis=1))
    return dq, cen


def project(field, P, iters=3):
    """points moved onto the field's zero set along its normals (Newton steps on a near-distance field)"""
    P = np.asarray(P, np.float64).copy()
    for _ in range(iters):
        P -= field.eval(P)[:, None] * field.normals(P)
    return P


def relax_ends(R, taus, field, records=None, hidden=None, hidden_fn=None):
    """THE END ZONES' RELAXATION (x4-1): where a ring band past the spine's end (tau < 1 or > 2: the rings' cones from
    the end node) has a quad tilted more than CAGE tilt_deg off a corner's clay normal, in sight (not inside `hidden`,
    the neighbouring shells' clay; X4b: hidden_fn(points (m, 5, 3)) -> hidden OVER THE MOTION RANGE, the centre and
    corners, instead), that end's rings between its cap's ring and the spine's end are relaxed on the
    clay (umbrella steps of CAGE relax_lam over the ring and column neighbours, each projected back onto the clay),
    CAGE relax_rounds at most, until no such tilt is left. The crusher propodus's proximal knob turns ~76 deg over
    1.8 mm on its lower rim, which the cones cross diagonally: a ring pinched to 1.9 mm beside 3.4 mm edges made
    trapezoids whose normals followed one side of the rim (cos 0.35 at the other side's corner); a ring inserted there
    instead made 0.9 mm bands (aspect 6) and, at the dactyl's sunk base, folds. Record rings never move"""
    rec_t = [float(k_) for k_ in (records or {})]
    R0 = np.asarray(R, np.float64)
    R = R0.copy()
    n = len(taus)
    t_ = np.asarray(taus)
    tm = 0.5 * (t_[:-1] + t_[1:])

    def seen_tilts(R_, deg):
        """the end-zone quads tilted more than deg in sight: (count, the ends {0, 1} they lie in)"""
        dq, cen = band_tilts(R_, field)
        badq = (dq < math.cos(math.radians(deg))) & ((tm < 1.0) | (tm > 2.0))[:, None]
        if hidden_fn is not None and badq.any():
            A_, B_ = R_[:-1], R_[1:]
            cor = np.stack([A_, np.roll(A_, -1, axis=1), np.roll(B_, -1, axis=1), B_], axis=2)     # (n-1, K, 4, 3)
            hq = np.zeros_like(badq)
            hq[badq] = hidden_fn(np.concatenate([cen[..., None, :], cor], axis=2)[badq])
            badq &= ~hq
        elif hidden is not None and badq.any():
            hq = np.zeros_like(badq)
            hq[badq] = hidden.eval(cen[badq]) < -0.05
            badq &= ~hq
        rows = np.nonzero(badq.any(axis=1))[0]
        return int(badq.sum()), {0 for j in rows if tm[j] < 1.0} | {1 for j in rows if tm[j] > 2.0}
    n_gate, ends = seen_tilts(R, 60.0)                  # relaxed only where x04's gate would fail
    if not n_gate:
        return R
    mv = np.array([j for j in range(1, n - 1) if ((0 in ends and t_[j] < 1.0) or (1 in ends and t_[j] > 2.0))
                   and not any(abs(t_[j] - r_) < 1e-9 for r_ in rec_t)], int)
    if not len(mv):
        return R
    for it in range(CAGE['relax_rounds']):
        avg = 0.25 * (R[mv - 1] + R[mv + 1] + np.roll(R[mv], 1, axis=1) + np.roll(R[mv], -1, axis=1))
        P = R[mv] + CAGE['relax_lam'] * (avg - R[mv])
        R[mv] = project(field, P.reshape(-1, 3)).reshape(P.shape)
        if (it + 1) % 5 == 0 and not seen_tilts(R, CAGE['tilt_deg'])[0]:
            break
    return R if seen_tilts(R, 60.0)[0] < n_gate else R0  # kept only if it helped


def capped_tube(name, kind, field, spine, K, taus, th=None, records=None, caps=(True, True), phi_max_deg=80.0,
                regions=None, tmax=80.0, scale_fn=None, cap_regions=('cap', 'cap'), hidden=None, hidden_fn=None,
                th_fn=None, cap_roll=(0, 0)):
    """one shell's cage (arthropod_cage.Cage) from its profile stations: rings cast at taus (records: {tau: (K, 3)
    verts} placed exactly), the end zones relaxed where they tilt in sight (relax_ends; hidden: the neighbours' clay),
    caps at the closed ends (grid_cap); regions: a function tau -> region name for the band behind a ring; scale_fn:
    tau -> the ring's inset (1.0 on the shell: the membrane's < 1); X4b, th_fn: tau -> the ring's own K angles (the
    chelae's occlusal rims: occlusal_warp), th otherwise. Returns the Cage with meta (rings' taus, ids, region per quad,
    record ring ids)"""
    th = 2.0 * np.pi * np.arange(K) / K if th is None else np.asarray(th, np.float64)
    phi_max = math.radians(phi_max_deg)
    records = records or {}

    def ring_at(tau):
        rec = next((v for k_, v in records.items() if abs(k_ - tau) < 1e-9), None)
        if rec is not None:
            return np.asarray(rec, np.float64)
        sc_ = 1.0 if scale_fn is None else float(scale_fn(tau))
        return cast_profile(field, spine, [tau], th if th_fn is None else th_fn(tau), phi_max, tmax, scale=sc_)[0]
    taus = [float(t_) for t_ in taus]
    R = np.stack([ring_at(t_) for t_ in taus])
    if scale_fn is None:
        R = relax_ends(R, taus, field, records, hidden, hidden_fn)
    cg = AC.Cage(name, kind, K)
    ids = cg.tube(R)
    q_region = []
    for j in range(len(taus) - 1):
        q_region += [regions(0.5 * (taus[j] + taus[j + 1])) if regions else kind] * K
    for end, closed in enumerate(caps):
        if not closed:
            continue
        j = 0 if end == 0 else len(taus) - 1
        tau = taus[j]
        P, D, rr, phi, A = profile_dirs(spine, tau, th if th_fn is None else th_fn(tau), phi_max)
        Oc = spine.at(0.0 if end == 0 else 1.0)[0]
        Ax = -spine.T_end[0] if end == 0 else spine.T_end[1]
        n_before = len(cg.Q)
        ring_c = list(ids[j])
        if cap_roll[end]:                               # X4b: the grid's corners rolled round the ring (a ridge)
            ring_c = ring_c[cap_roll[end]:] + ring_c[:cap_roll[end]]
        grid_cap(cg, ring_c, field, Oc, Ax, phi if (tau < 1.0 or tau > 2.0) else 0.0, flip=(end == 0), tmax=tmax)
        q_region += [cap_regions[end]] * (len(cg.Q) - n_before)
    cg.orient()
    cg.meta.update(taus=np.asarray(taus), ring_ids=ids, region=np.array(q_region), spine=spine, th=th, th_fn=th_fn,
                   record_ids={k_: ids[int(np.argmin(np.abs(np.asarray(taus) - k_)))] for k_ in records})
    return cg


# ============================================================================================ the fit and the limit
def fit(cg):
    """the controls whose limit passes through the targets (cg.V) at the cage's vertices: subdiv_sharp.fit_controls at
    the levels the creases need (ceil(max s) + 1; none: 1). Returns (V0 controls, the residual's max, levels)"""
    mesh = QuadMesh(cg.V, np.asarray(cg.Q, int))
    smax = max(cg.sharp.values()) if cg.sharp else 0.0
    lv = int(math.ceil(smax)) + 1
    V0, res = SS.fit_controls(mesh, cg.sharp, cg.V, lv)
    return V0, res, lv


REFIT = dict(level=3, over=0.2, grow=2, iters=14, w_low=1.0, w_hold=3.0)
# X4h (the lead's call 2 on the X4g check: the three gate-10 rows under 0.3 mm BY CONSTRUCTION): limit_refit. The fit
# INTERPOLATES the clay at the cage's vertices only, and where a cell (2-4 mm) bridges one of the clay's smooth-union
# blends (the socket's collar round the top ray, the dactyl's base rim) the limit between the vertices stood up to
# 0.50-0.59 mm off it (true distance). So the cells whose limit stands more than `over` mm off are REFITTED to the clay
# over their whole surface: the controls of their vertices (grown `grow` rings) solved by least squares so the limit's
# level-`level` points land on their nearest points of the clay (surface_distance's feet, re-found each of `iters`
# rounds), the cage's own vertices there kept ON the clay (weight w_low: the low slides along it, so gate 2 still reads
# it against the clay's normal where it lies) and the creased rims' vertices at their targets (weight w_hold: the
# virtual corners, crisp by construction); THE LOW is the cage at its new limit positions (so x04's fit reproduces
# these controls exactly). The features and every vertex whose limit stencil reaches them stay fixed (their stand-off
# is by design). First try (iters 4, held the rims' whole ring, a weight toward the old targets): the cutter's knob lip
# could not move (its cells sit in the rims' ring) and the dactyls' lows slid into 2 tilts each


def low_tilts(cg, field, skip=None):
    """X4h: per quad of the cage's low, the least cosine between its normal and the clay's normals at its corners
    (x04's gate 2 on the low), the features' quads (skip) 1.0"""
    Q = np.asarray(cg.Q, int)
    V = cg.V
    nq = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    nq /= np.maximum(np.linalg.norm(nq, axis=1, keepdims=True), 1e-20)
    nc = field.normals(V)
    d = np.stack([(nq * nc[Q[:, k]]).sum(1) for k in range(4)], 1).min(1)
    if skip is not None:
        d[skip] = 1.0
    return d


def relax_tilts(cg, field, log=print, label=''):
    """X4h: THE LOW'S TILTS ANYWHERE ON A CLAW PART (relax_ends' rule beyond the end zones): a quad tilted more than 60
    deg off a corner's clay normal, hidden or not (the cutter dactyl's base quads by the hinge read hidden by x04's
    range_hidden on one build and not on the next, and the posed lows show them, X4g check's lowhid list), has its free
    vertices and their one ring relaxed on the clay (umbrella steps of CAGE relax_lam over the cage's edge neighbours, each
    projected back), CAGE relax_rounds at most; the features' and the creased rims' vertices never move. Kept only if it
    leaves fewer such quads. Returns (before, after)"""
    Q = np.asarray(cg.Q, int)
    n = len(cg.V)
    fq, near_f, _, _ = feature_masks(cg)
    held = np.zeros(n, bool)
    held[np.unique(Q[fq | near_f].ravel())] = True
    if cg.sharp:
        held[np.array([v for e_ in cg.sharp for v in e_], int)] = True
    for r_ids in (cg.meta.get('record_ids') or {}).values():
        held[np.asarray(r_ids, int)] = True
    lim = math.cos(math.radians(60.0))
    d0 = low_tilts(cg, field, fq)
    bad = d0 < lim
    if not bad.any():
        return 0, 0
    nb = [set() for _ in range(n)]
    for q in Q:
        for k in range(4):
            a, b = int(q[k]), int(q[(k + 1) % 4])
            nb[a].add(b)
            nb[b].add(a)
    mv = set(int(v) for v in np.unique(Q[bad].ravel()))
    for v in list(mv):
        mv |= nb[v]
    mv = np.array(sorted(v for v in mv if not held[v]), int)
    V0 = cg.V.copy()
    if len(mv):
        for it in range(CAGE['relax_rounds']):
            avg = np.array([cg.V[list(nb[v])].mean(0) for v in mv])
            cg.V[mv] = project(field, cg.V[mv] + CAGE['relax_lam'] * (avg - cg.V[mv]))
            if (it + 1) % 5 == 0 and not (low_tilts(cg, field, fq) < math.cos(math.radians(CAGE['tilt_deg']))).any():
                break
    n1 = int((low_tilts(cg, field, fq) < lim).sum())
    if n1 >= int(bad.sum()):
        cg.V = V0
        n1 = int(bad.sum())
    if n1 and CAGE.get('tilt_slide'):
        # X4h: a quad that a HARD CREASE of the clay crosses diagonally (the cutter dactyl's socket cap step, tilt_probe:
        # the normals jump 0.94 -> 0.39 over 0.2 mm) has one corner past the crease, which no umbrella moves: that corner
        # slides on the clay toward the quad's opposite corner, a step at a time, to the first place where no quad round
        # it is tilted past 60 deg (and none newly is)
        for _ in range(12):
            d_ = low_tilts(cg, field, fq)
            badq = np.nonzero(d_ < lim)[0]
            if not len(badq):
                break
            Vn_ = cg.V
            nc_ = field.normals(Vn_)
            moved_any = False
            for q in badq:
                qq = Q[q]
                nq_ = np.cross(Vn_[qq[2]] - Vn_[qq[0]], Vn_[qq[3]] - Vn_[qq[1]])
                nq_ /= max(np.linalg.norm(nq_), 1e-20)
                k = int(np.argmin(nc_[qq] @ nq_))
                v = int(qq[k])
                if held[v]:
                    continue
                tgt = Vn_[int(qq[(k + 2) % 4])]
                ring_q = np.nonzero((Q == v).any(axis=1))[0]
                P0 = Vn_[v].copy()
                before = int((d_[ring_q] < lim).sum())
                for s_ in np.linspace(0.05, 0.6, 12):
                    cg.V[v] = project(field, (P0 + s_ * (tgt - P0))[None, :])[0]
                    dd_ = low_tilts(cg, field, fq)[ring_q]
                    if int((dd_ < lim).sum()) < before and dd_.min() > d_[ring_q].min() - 1e-9:
                        moved_any = True
                        break
                else:
                    cg.V[v] = P0
            if not moved_any:
                break
        n1 = int((low_tilts(cg, field, fq) < lim).sum())
    log(f'[decapod_cage] {label or cg.name}: relax_tilts (X4h): {int(bad.sum())} low quads tilted > 60 deg -> {n1} '
        f'({len(mv)} vertices relaxed on the clay)')
    return int(bad.sum()), n1


def limit_refit(cg, field, log=print, label=''):
    """X4h (REFIT's comment): the cage's controls refitted to the clay where its limit stands more than REFIT over mm
    off, the features and creases fixed; cg.V becomes the cage's limit positions. Returns a summary dict"""
    import scipy.sparse as sp_
    import scipy.sparse.linalg as spla_
    Q = np.asarray(cg.Q, int)
    n = len(cg.V)
    mesh = QuadMesh(cg.V, Q)
    C, _, lv = fit(cg)
    A, _ = SS.limit_operator(mesh, cg.sharp, lv)
    cur, s_e, par, ops = SS.subdivide(mesh, cg.sharp, REFIT['level'], keep=True, to_limit=False)
    Mx = SS.limit_matrix(cur, s_e)
    for S in ops[::-1]:
        Mx = (Mx @ S).tocsr()
    Mx = Mx.tocsr()
    Ql = np.asarray(cur.Q, int)
    # held: the features (their quads and the quads round their feet: every vertex within one ring of theirs, so their
    # limit, which stands off the clay by design, is untouched) and the creased rims' own vertices (their neighbours may
    # move: the rims' limit positions are then held by rows of weight w_hold at their targets, the virtual corners)
    fq, near_f, _, _ = feature_masks(cg)
    feat_q = fq | near_f
    sv = np.zeros(n, bool)
    if cg.sharp:
        sv[np.array([v for e_ in cg.sharp for v in e_], int)] = True
    rim_q = sv[Q].any(axis=1)
    adj = [set() for _ in range(n)]
    for q in Q:
        for a in q:
            adj[int(a)].update(int(b) for b in q)
    feat_v = np.zeros(n, bool)
    feat_v[np.unique(Q[feat_q].ravel())] = True
    for r_ids in (cg.meta.get('record_ids') or {}).values():    # A0 (the carpus is refitted too): an X3 RECORD ring is
        feat_v[np.asarray(r_ids, int)] = True                   # held as a feature is, its one ring of neighbours with
    #                                                             it, so its limit positions stay bit-exact (x04 gate 4)
    buf = feat_v.copy()
    for v in np.nonzero(feat_v)[0]:
        buf[list(adj[v])] = True
    buf |= sv
    hold_v = feat_v | sv                                # (whose limit positions stay at their targets)
    T0 = cg.V.copy()
    pt_q = par                                          # each limit quad's cage quad
    out = dict(rounds=[], fixed_v=int(buf.sum()))
    free_all = np.zeros(n, bool)
    best = None
    skip_q = feat_q | rim_q                             # (their limit points are not fitted to the clay)
    for it in range(REFIT['iters'] + 1):
        P = Mx @ C
        lv_ok = np.unique(Ql[~skip_q[pt_q]].ravel())    # the limit points of the fitted quads
        d, _, _, _ = offset_true(field, P[lv_ok])
        bad = lv_ok[d > REFIT['over']]
        out['rounds'].append((int(len(bad)), float(d.max()) if len(d) else 0.0))
        if best is None or out['rounds'][-1][1] < best[0]:      # (the rounds are not monotone near the end: the
            best = (out['rounds'][-1][1], C.copy(), it)          # crusher dactyl 0.286 at round 11, 0.302 at 14)
        if not len(bad) or it == REFIT['iters']:
            break
        trig = np.unique(pt_q[np.isin(Ql, bad).any(axis=1)])
        fr_ = np.zeros(n, bool)
        fr_[np.unique(Q[trig].ravel())] = True
        for _ in range(REFIT['grow']):
            fr_[np.unique(np.concatenate([list(adj[v]) for v in np.nonzero(fr_)[0]]))] = True
        fr_ &= ~buf
        free_all |= fr_
        F_ = np.nonzero(free_all)[0]
        if not len(F_):
            break
        # rows: the fitted limit points whose patch holds a freed control (the cage quads of the freed vertices' ring)
        near_v = free_all.copy()
        for v in F_:
            near_v[list(adj[v])] = True
        rq = near_v[Q].any(axis=1)
        rows = np.unique(Ql[(rq & ~skip_q)[pt_q]].ravel())
        _, Y, _, _ = surface_distance(field, P[rows])
        # the cage's own vertices in reach: the free-able ones kept ON the clay (their nearest points: the low stays on
        # the clay, sliding along it), the held ones (rims) at their targets
        cv = np.nonzero(near_v)[0]
        cv_h = cv[hold_v[cv]]
        cv_f = cv[~hold_v[cv]]
        Pv = A[cv_f] @ C
        _, Yv, _, _ = surface_distance(field, Pv) if len(cv_f) else (None, np.zeros((0, 3)), None, None)
        X_ = np.nonzero(~free_all)[0]
        blocks = [(Mx[rows], Y, 1.0), (A[cv_f], Yv, REFIT['w_low']), (A[cv_h], T0[cv_h], REFIT['w_hold'])]
        G = None
        rhs = 0.0
        for Mb, Yb, w in blocks:
            if Mb.shape[0] == 0:
                continue
            Mf, Mk = Mb[:, F_], Mb[:, X_]
            Gb = (w * w) * (Mf.T @ Mf)
            rb = (w * w) * (Mf.T @ (Yb - Mk @ C[X_]))
            G = Gb if G is None else G + Gb
            rhs = rhs + rb
        G = G + 1.0e-9 * sp_.identity(len(F_))
        lu = spla_.splu(G.tocsc())
        C = C.copy()
        C[F_] = np.column_stack([lu.solve(np.asarray(rhs[:, k]).ravel()) for k in range(3)])
    C = best[1]                                         # the round with the least worst offset
    out['kept_round'] = int(best[2])
    Vn = A @ C
    for r_ids in (cg.meta.get('record_ids') or {}).values():    # x6fix_x7 (x04 _a0g gate 4: the wrist ring 2.8e-14 mm
        r_ids = np.asarray(r_ids, int)                          # off its record): A @ C recomputes every held limit to
        Vn[r_ids] = T0[r_ids]                                   # float noise; a RECORD's vertices are copied back bit
    #                                                             for bit (their controls are held: the same surface)
    moved_fixed = float(np.abs(Vn[hold_v] - T0[hold_v]).max()) if hold_v.any() else 0.0
    cg.V = Vn
    cg.meta['refit'] = dict(out, free_v=int(free_all.sum()), moved_max=float(np.linalg.norm(Vn - T0, axis=1).max()),
                            moved_fixed=moved_fixed)
    log(f'[decapod_cage] {label or cg.name}: limit_refit (X4h): ' + ' -> '.join(f'{b} pts > {REFIT["over"]} (max {m:.3f})'
                                                                             for b, m in out['rounds'])
        + f'; {int(free_all.sum())} vertices freed of {n} ({int(buf.sum())} held by the features / creases), the low moved '
          f'<= {cg.meta["refit"]["moved_max"]:.3f} mm, the held {moved_fixed:.1e}; kept round {out["kept_round"]}')
    return cg.meta['refit']


def limit_mesh(cg, V0, levels=None):
    """the limit surface at `levels` (subdiv_sharp.subdivide pushed to the limit) and each quad's ancestor quad"""
    lim, _, parent, _ = SS.subdivide(QuadMesh(V0, np.asarray(cg.Q, int)), cg.sharp, LEVELS['out'] if levels is None
                                     else levels)
    return lim, parent


# ============================================================================================ segments and sleeves
def tube_nodes(part):
    """a clay tube part's PSWEEP: its end nodes (proximal, distal), across normal, rho (life mm)"""
    d0 = part.descs[0]
    p = np.asarray(d0['points'], np.float64)
    return p[0], p[-1], unit(np.asarray(d0['normal'], np.float64)), float(d0['rho'])


def col_spacing(field, spine, th, u, scale=1.0):
    """the mean column spacing (mm) of a ring at the spine's arc fraction u"""
    P, D, _, _, _ = profile_dirs(spine, 1.0 + u, th, 0.0)
    t = field.cast(P, D, 80.0)
    Q = P[None, :] + (scale * t)[:, None] * D
    return float(np.mean(np.linalg.norm(np.roll(Q, -1, axis=0) - Q, axis=1)))


def h_function(field, spine, th, n_probe=9):
    """the ring spacing along the profile: CAGE spacing x the local column spacing, clamped (h_min, h_max)"""
    us = np.linspace(0.0, 1.0, n_probe)
    cs = np.array([col_spacing(field, spine, th, u) for u in us])
    hs = np.clip(CAGE['spacing'] * cs, CAGE['h_min'], CAGE['h_max'])

    def h(tau):
        u = float(np.clip(tau - 1.0, 0.0, 1.0))
        return float(np.interp(u, us, hs))
    return h


def segment_cage(name, kind, field, a0, b, X0, K, records=None, th=None, caps=(True, True), regions=None,
                 extra_taus=(), scale_fn=None, fixed_extra=(), cap_regions=('cap', 'cap'), hidden=None, cap_c=None,
                 hide=(None, None), hidden_fn=None, cap_rmin=None, th_fn=None):
    """a straight shell (a clay tube) from its proximal end node a0 to its distal end node b, its columns from X0 (at
    the angles th: X4b, a sag-spaced record's own); records: {(the record's centre), (K, 3) verts}: each placed as a ring
    at its own station on the axis; cap_c, hide, cap_rmin (A0): each end's hand-over to its grid cap (ring_taus);
    hidden_fn: relax_ends' sight test (X4b: hidden over the motion range); th_fn (A0): tau -> the ring's own K angles
    (capped_tube), th otherwise"""
    sp = Spine(np.array([a0, b]), X0)
    th = 2.0 * np.pi * np.arange(K) / K if th is None else th
    rec_taus = {}
    for c_, V_ in (records or {}).items():
        u = float(np.clip((np.asarray(c_) - a0) @ sp.T[0] / sp.L, 0.0, 1.0))
        rec_taus[1.0 + u] = V_
    h = h_function(field, sp, th)
    taus, _ = ring_taus(field, sp, th, math.radians(CAGE['phi_max']), fixed=list(rec_taus) + list(fixed_extra),
                        h_fn=h, n_dense=CAGE['n_dense'], dense_step=CAGE['dense_step'], caps=caps, cap_c=cap_c,
                        hide=hide, cap_rmin=cap_rmin)
    taus = np.array(sorted(set(np.round(list(taus) + list(extra_taus), 12))))
    return capped_tube(name, kind, field, sp, K, taus, th=th, records=rec_taus, caps=caps,
                       phi_max_deg=CAGE['phi_max'], regions=regions, scale_fn=scale_fn, cap_regions=cap_regions,
                       hidden=hidden, hidden_fn=hidden_fn, th_fn=th_fn)


def sleeve_cage(name, child, parent, origin, axis, K, X, record=None, kind='sleeve', th=None):
    """one SLEEVE (module docstring; X3's rule, x03_seams.build_ring's 'sleeve' branch): X0 where the child's axis
    (from its proximal node `origin`) leaves the parent, rings at X0 - d_in, X0, X0 + d, the child's section x
    in_child; K columns from X (the record's frame when it carries X3's ring: its ring 0 placed exactly; X4b: th the
    record's own angles when it is sag-spaced). Returns (Cage (open: two bands), dict(X0, d, d_in, centres))"""
    axis = unit(axis)
    ts = np.arange(-2.0, 25.0, 0.01)
    fpar = parent.eval(origin[None, :] + ts[:, None] * axis[None, :])
    io = np.nonzero((fpar[:-1] < 0.0) & (fpar[1:] >= 0.0))[0]
    if not len(io):
        raise RuntimeError(f'{name}: the child\'s axis never leaves the parent')
    i = int(io[0])
    X0 = origin + (ts[i] - fpar[i] * (ts[i + 1] - ts[i]) / (fpar[i + 1] - fpar[i])) * axis
    X = unit(X - axis * float(X @ axis))
    Y = np.cross(axis, X)
    th48 = 2.0 * np.pi * np.arange(48) / 48
    D48 = np.cos(th48)[:, None] * X[None, :] + np.sin(th48)[:, None] * Y[None, :]
    r0 = child.cast(np.repeat(X0[None, :], 48, axis=0), D48, 30.0)
    if not np.isfinite(r0).all():
        raise RuntimeError(f'{name}: the sleeve\'s centre is not inside the child at X')
    d = float(np.clip(SLV['step'] * np.median(r0), SLV['step_min'], SLV['step_max']))
    t_back = float(child.cast(X0[None, :], -axis[None, :], 30.0)[0])
    d_in = min(d, 0.5 * t_back) if np.isfinite(t_back) else d
    centres = [X0 - d_in * axis, X0, X0 + d * axis]
    if record is None and d_in < 0.5 * d:
        # a sleeve with no X3 ring to keep: its three rings d apart from the proximal one (the dactyl's base lies ~1 mm
        # behind X0, so X3's d_in made a band 0.5 mm deep against 2.4 mm columns: aspect 4.7), still inside the child
        centres = [X0 - d_in * axis, X0 + (d - d_in) * axis, X0 + (2.0 * d - d_in) * axis]
    given_th = th is not None
    th = 2.0 * np.pi * np.arange(K) / K if th is None else np.asarray(th, np.float64)
    if record is None and not given_th:
        # no X3 ring to keep: the columns at equal arc per quadrant of the middle ring's section (the loft's column
        # rule; equal angles crowded the dactyl's flattened base, radii 1.8-9 mm, to 0.45 mm columns: aspect 4.7)
        nd = 96
        dth = 2.0 * np.pi * np.arange(4 * nd) / (4 * nd)
        Dd = np.cos(dth)[:, None] * X[None, :] + np.sin(dth)[:, None] * Y[None, :]
        rd = child.cast(np.repeat(centres[1][None, :], len(dth), axis=0), Dd, 30.0)
        if np.isfinite(rd).all():
            Pd = centres[1][None, :] + rd[:, None] * Dd
            q, out_th = K // 4, []
            for quad in range(4):
                idx = np.arange(quad * nd, quad * nd + nd + 1) % (4 * nd)
                seg = np.linalg.norm(np.diff(Pd[idx], axis=0), axis=1)
                acc = np.concatenate([[0.0], np.cumsum(seg)])
                ang = quad * 0.5 * np.pi + np.linspace(0.0, 0.5 * np.pi, nd + 1)
                out_th.append(np.interp(acc[-1] * np.arange(q) / q, acc, ang))
            th = np.concatenate(out_th)
    D = np.cos(th)[:, None] * X[None, :] + np.sin(th)[:, None] * Y[None, :]
    rings = []
    for j, c_ in enumerate(centres):
        if j == 0 and record is not None:
            rings.append(np.asarray(record, np.float64))
            continue
        r = child.cast(np.repeat(c_[None, :], K, axis=0), D, 30.0)
        if not np.isfinite(r).all():
            raise RuntimeError(f'{name}: sleeve ring {j} leaves the child')
        rings.append(c_[None, :] + (SLV['in_child'] * r)[:, None] * D)
    cg = AC.Cage(name, kind, K)
    ids = cg.tube(np.stack(rings))
    cg.orient()
    # an open tube's signed volume is not its orientation: outward means away from the axis
    Qa = np.asarray(cg.Q, int)
    c_q = cg.V[Qa].mean(1)
    nq = np.cross(cg.V[Qa[:, 2]] - cg.V[Qa[:, 0]], cg.V[Qa[:, 3]] - cg.V[Qa[:, 1]])
    radial = c_q - (X0[None, :] + ((c_q - X0) @ axis)[:, None] * axis[None, :])
    if float(np.sum(np.einsum('ij,ij->i', nq, radial))) < 0.0:
        cg.Q = [tuple(q[::-1]) for q in cg.Q]
    cg.meta.update(ring_ids=ids, region=np.array([kind] * len(cg.Q)), record_ids={0: ids[0]} if record is not None
                   else {}, X0=X0, d=d, d_in=d_in, centres=centres, axis=axis, frame=(X, Y), t_back=t_back,
                   r_bar=float(np.mean(r0)))
    return cg


# ============================================================================================ the chelae
def plan_spine(poly, origin, d_ax, n_ax, s_lo=None, s_hi=None, T0=None, s_min=None):
    """a claw part's spine (Spine) in its fingers' plane: the plan interval's middle along s (decapod_parts.interval_at),
    Gaussian-smoothed over CAGE spine_sigma, from s_lo to s_hi (default: CAGE spine_end x the end's half-width in from
    the plan's extremes); the frame's X the in-plane normal toward +m (Y = T x X: the claw's thickness direction);
    T0: the planes' normal at the start (X4b, the dactyl's base face: Spine T0 over CAGE base_blend); s_min: the
    proximal extreme instead of the plan's (X4b: a trimmed base's cut), the default start measured from it"""
    from scipy.ndimage import gaussian_filter1d
    P = np.asarray(poly, np.float64)
    s0, s1 = float(P[:, 0].min()), float(P[:, 0].max())
    ss = np.arange(s0 + 0.05, s1 - 0.05, CAGE['spine_step'])
    iv = [DPP.interval_at(P, float(s)) for s in ss]
    ok = np.array([v is not None for v in iv])
    ss = ss[ok]
    lo = np.array([v[0] for v in iv if v is not None])
    hi = np.array([v[1] for v in iv if v is not None])
    mc = gaussian_filter1d(0.5 * (lo + hi), CAGE['spine_sigma'] / CAGE['spine_step'], mode='nearest')
    hw = 0.5 * (hi - lo)
    if s_lo is None:
        i0 = 0 if s_min is None else int(np.clip(np.searchsorted(ss, s_min), 0, len(ss) - 1))
        s_lo = float(ss[i0] + CAGE['spine_end'] * hw[min(i0 + int(3.0 / CAGE['spine_step']), len(hw) - 1)])
    if s_hi is None:
        s_hi = float(ss[-1] - CAGE['spine_end'] * hw[max(len(hw) - 1 - int(1.5 / CAGE['spine_step']), 0)])
    sel = (ss >= s_lo) & (ss <= s_hi)
    s_, m_ = ss[sel], mc[sel]
    d_ax, n_ax = unit(d_ax), unit(n_ax)
    P3 = origin[None, :] + s_[:, None] * d_ax[None, :] + m_[:, None] * n_ax[None, :]
    return (Spine(P3, n_ax, plane_sigma=CAGE['plane_sigma'], T0=T0, t0_blend=CAGE['base_blend']),
            dict(s=s_, m=m_, lo=lo[sel], hi=hi[sel]))


def claw_frames(info):
    """a claw's frames at the bind (decapod_parts.claw_parts' info): the propodus's (W, d, n) and the dactyl's own (its
    hinge o_d, its axis dd, its in-plane normal nd) with its plan in that frame"""
    W, d, n, H = info['W'], unit(info['d']), unit(info['n']), np.asarray(info['H_sm'], np.float64)
    ang = math.radians(info['c11_dir'] + (info['want'] - info['open_c11']))
    dd = math.cos(ang) * d + math.sin(ang) * n
    nd = -math.sin(ang) * d + math.cos(ang) * n
    o_d = W + H[0] * d + H[1] * n
    dp = np.asarray(info['dactyl_plan'], np.float64)
    loc = np.column_stack([(dp - H) @ np.array([math.cos(ang), math.sin(ang)]),
                           (dp - H) @ np.array([-math.sin(ang), math.cos(ang)])])
    # X4b, the dactyl's BASE FACE (decapod_parts.dactyl_poly: the plan's straight base CLAW dactyl_sink behind the line
    # from the gape's bottom to the knob, swept across the thickness: a plane): its line in the dactyl's own frame is
    # M1's (gape - knob) turned by -c11_dir (the opening's turn and the frame's cancel); its normal into the dactyl
    g_, a_ = np.asarray(info['polys']['gape'], np.float64), np.asarray(info['polys']['artic'], np.float64)
    gk = g_ - a_
    c_, s_ = math.cos(math.radians(info['c11_dir'])), math.sin(math.radians(info['c11_dir']))
    Rm = np.array([[c_, s_], [-s_, c_]])                # M1's claw frame -> the dactyl's own (about the hinge)
    bl = Rm @ gk
    nb = np.array([-bl[1], bl[0]]) / max(float(np.linalg.norm(bl)), 1e-12)
    nb = nb if nb[0] > 0.0 else -nb
    # the base's two ends as dactyl_poly lays them (its CLAW dactyl_sink behind the gape-knob line, 0.2 in from each end)
    ax_ = unit(np.asarray(info['polys']['dactyl_tip'], np.float64) - 0.5 * (g_ + a_))
    back = -ax_ * DPP.CLAW['dactyl_sink']
    ends = [Rm @ (p_ - H) for p_ in (a_ + back + 0.2 * gk, g_ + back - 0.2 * gk)]
    if info.get('socket') is not None:                  # X4e (decapod_parts SOCKET): the base is the TONGUES' back: X4f,
        sa_ = info['socket']['angles']                  # the chord from the top tongue's end (phi_back_o, R_o) to the
        H2 = np.asarray(sa_['H'], np.float64)           # heel's start at phi_back (heel_plan; X4e: the radial line
        ph_, pho = math.radians(sa_['phi_back']), math.radians(sa_['phi_back_o'])     # from the knob, the hinge)
        pb_ = H2 + sa_['R'] * np.array([math.cos(ph_), math.sin(ph_)])
        pt_ = H2 + sa_['R_o'] * np.array([math.cos(pho), math.sin(pho)])
        gk = pb_ - pt_
        bl = Rm @ gk
        nb = np.array([-bl[1], bl[0]]) / max(float(np.linalg.norm(bl)), 1e-12)
        nb = nb if nb[0] > 0.0 else -nb
        ends = [Rm @ (p_ - H) for p_ in (pt_ + 0.2 * gk, pb_ - 0.2 * gk)]
    return dict(W=W, d=d, n=n, o_d=o_d, dd=dd, nd=nd, dactyl_local=loc, propodus=np.asarray(info['polys']['propodus']),
                base_normal=unit(nb[0] * dd + nb[1] * nd), base_line_local=bl, base_normal_local=nb,
                base_ends_local=ends)


def dactyl_spine(fr):
    """X4b, the lead's call 1: THE DACTYL'S SPINE (CAGE base_in / join / base_blend): from its base face's centre, inside
    it along the face's normal, a Hermite curve onto the plan centreline (plan_spine's) at CAGE join x the dactyl's
    length, then that centreline to its end; the planes held on the base face's normal at the start (Spine T0), so the
    end rings lie parallel to the slanted base face and the proximal cap's axis is its normal"""
    loc = np.asarray(fr['dactyl_local'], np.float64)
    bk, bg = (np.asarray(e, np.float64) for e in fr['base_ends_local'])
    nb = np.asarray(fr['base_normal_local'], np.float64)
    S0 = 0.5 * (bk + bg) + CAGE['base_in'] * 0.5 * float(np.linalg.norm(bg - bk)) * nb
    _, inf0 = plan_spine(loc, fr['o_d'], fr['dd'], fr['nd'])
    cl = np.column_stack([inf0['s'], inf0['m']])
    j = int(np.clip(np.argmin(np.abs(cl[:, 0] - CAGE['join'] * float(loc[:, 0].max()))), 1, len(cl) - 2))
    P1, T1 = cl[j], unit(cl[j + 1] - cl[j - 1])
    k = float(np.linalg.norm(P1 - S0))
    tt = np.linspace(0.0, 1.0, max(8, int(np.ceil(1.3 * k / CAGE['spine_step']))))[:, None]
    herm = ((2 * tt ** 3 - 3 * tt ** 2 + 1) * S0 + (tt ** 3 - 2 * tt ** 2 + tt) * k * nb
            + (-2 * tt ** 3 + 3 * tt ** 2) * P1 + (tt ** 3 - tt ** 2) * k * T1)
    pts = np.vstack([herm, cl[j + 1:]])
    P3 = fr['o_d'][None, :] + pts[:, :1] * fr['dd'][None, :] + pts[:, 1:] * fr['nd'][None, :]
    return Spine(P3, fr['nd'], plane_sigma=CAGE['plane_sigma'], T0=fr['base_normal'], t0_blend=CAGE['base_blend'])


def tau_through(sp, X, n=801):
    """X4g: the profile station (1 + u) whose ring plane (normal to the spine's smoothed tangent) passes through the
    point X, or None"""
    us = np.linspace(0.0, 1.0, n)
    f = np.array([float((X - sp.at(u)[0]) @ sp.at(u)[1]) for u in us])
    k = np.nonzero(((f[:-1] > 0) & (f[1:] <= 0)) | ((f[:-1] < 0) & (f[1:] >= 0)))[0]
    if not len(k):
        return None
    k = int(k[0])
    return 1.0 + float(us[k] + (us[k + 1] - us[k]) * f[k] / (f[k] - f[k + 1]))


def claw_cage(name, field, poly, origin, d_ax, n_ax, K, regions=None, hidden=None, cap_c=None, s_min=None, spine=None,
              hide=(None, None), hidden_fn=None, turn_max=None, occlusal=None, cap_roll=(0, 0), anchor=None, cap_rmin=None,
              fixed_at=(), split_first=False):
    """a claw part (the propodus, palm and fixed finger; the dactyl) as one closed cage along its plan centreline
    (plan_spine): rings normal to the spine (the frame's X toward +m: the dactyl's side, Y the claw's thickness),
    both ends capped. X4b: s_min a trimmed base's cut (the spine starts by the plan's rule from it), spine a spine of
    its own instead (the dactyl's: dactyl_spine), cap_c / hide each end's hand-over, turn_max the part's own (ring_taus);
    occlusal (FEAT band: centre deg, s_from the claw-frame s where the band starts or None, ramp mm): the columns
    +-FEAT crease cols about the occlusal direction laid on the band's rims (occlusal_rims, occlusal_warp). X4e: anchor
    a station the rings keep (tau: their phase along the spine, CAGE anchor_crusher). X4g: fixed_at, points (3,) whose
    ring planes are stations too (tau_through; one within CAGE station_gap mm of arc of another is left out)"""
    if spine is None:
        sp, info_ = plan_spine(poly, origin, d_ax, n_ax, s_min=s_min)
    else:
        sp, info_ = spine, dict(own=True)
    th = 2.0 * np.pi * np.arange(K) / K
    h = h_function(field, sp, th, n_probe=15)
    fixed = [] if anchor is None else [float(anchor)]
    for X_ in fixed_at:
        t_ = tau_through(sp, np.asarray(X_, np.float64))
        if t_ is not None and all(abs(t_ - f_) * sp.L > CAGE['station_gap'] for f_ in fixed):
            fixed.append(t_)
    taus, _ = ring_taus(field, sp, th, math.radians(CAGE['phi_max']), fixed=tuple(fixed), h_fn=h,
                        n_dense=CAGE['n_dense'], dense_step=CAGE['dense_step'], cap_c=cap_c, hide=hide, turn_max=turn_max,
                        cap_rmin=cap_rmin)
    if split_first:                                     # X4h: one ring more, half way along the first band
        taus = np.sort(np.r_[taus, 0.5 * (taus[0] + taus[1])])
    th_fn, warp = None, None
    if occlusal is not None:
        s_at = lambda u: float((sp.at(u)[0] - origin) @ unit(d_ax))           # noqa: E731
        us = np.linspace(0.0, 1.0, 41)
        s_from, ramp = occlusal.get('s_from'), float(occlusal.get('ramp', 0.0))
        tf = float(occlusal.get('tip_fade', 0.0))      # X4d: the warp faded out over the spine's last tf mm (the cutter's
        #                                               fixed tip: its grid cap on warped columns read aspect 4.50)

        def fade(u, tf=tf):
            if tf <= 0.0:
                return 1.0
            x = float(np.clip((1.0 - u) * sp.L / tf, 0.0, 1.0))
            return x * x * (3.0 - 2.0 * x)
        if s_from is not None:
            us = us[np.array([s_at(u) >= s_from - ramp - 2.0 for u in us])]

            def w_fn(u, s_from=s_from, ramp=ramp):
                x = float(np.clip((s_at(u) - (s_from - ramp)) / max(ramp, 1e-9), 0.0, 1.0))
                return x * x * (3.0 - 2.0 * x) * fade(u)
        else:
            def w_fn(u):
                return fade(u)
        rims, us_k = occlusal_rims(field, sp, occlusal['centre'], us, n_rays=360)
        fs_ = occlusal.get('foot_span')                 # X4g: the collar's wall columns over the socket's span (CAGE foot_pull)
        span = None if fs_ is None else np.array([1.0 if fs_[0] <= s_at(u) <= fs_[1] else 0.0 for u in us_k])
        cols_ = int(occlusal.get('cols', FEAT['crease']['cols']))    # (X4h: a part's own, CAGE dactyl_cutter)
        th_fn = occlusal_warp(K, occlusal['centre'], cols_, us_k, rims, w_fn,
                              pull=occlusal.get('foot_pull'), span=span)
        warp = dict(us=us_k, rims_deg=np.degrees(rims), centre=occlusal['centre'], cols=cols_,
                    **{k_: occlusal[k_] for k_ in ('band_nb', 'corner_share') if k_ in occlusal})
    cg = capped_tube(name, 'chitin', field, sp, K, taus, th=th, phi_max_deg=CAGE['phi_max'], regions=regions,
                     hidden=hidden, hidden_fn=hidden_fn, th_fn=th_fn, cap_roll=cap_roll)
    cg.meta['plan_spine'] = info_
    cg.meta['occlusal'] = warp
    return cg


# ============================================================================================ X4b: the motion ranges
def rot_axis(axis, deg):
    """the rotation (3 x 3) by deg about the unit axis (right-handed)"""
    a = unit(axis)
    t = math.radians(deg)
    K_ = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    return np.eye(3) + math.sin(t) * K_ + (1.0 - math.cos(t)) * K_ @ K_


def joint_motions(spec, chain, kind='crusher'):
    """X4b (module docstring; MOTION): the LEFT cheliped's joints and their motion ranges, {child joint: dict(o the
    joint, z its fold axis (+ folds the anatomical way, decapod.skeleton), rel (lo, hi) deg from the bind, angles (the
    samples, the bind's 0 among them), how)}"""
    from . import decapod as DP
    sk = DP.skeleton(spec, chain, scale=1.0)
    ba = {d_['joint']: d_['value'] for d_ in DP.bind_angles(spec, chain)}
    rc, rw = spec['rig']['ranges']['cheliped'], spec['rig']['ranges']['walking']
    op = spec['rig']['cheliped']['dactyl_open']
    claw = MOTION['claw'] if kind == 'crusher' else tuple(rc['cutter'])
    rel = dict(
        cheliped_coxa_L=([-(p - ba['cheliped_coxa']) for p in rc['promotion']],
                         f'the rig\'s promotion {tuple(rc["promotion"])} (+ remotion about z)'),
        cheliped_basis_L=([v - ba['cheliped_basis'] for v in rc['levation']], f'the rig\'s levation {tuple(rc["levation"])}'),
        cheliped_merus_L=(list(rw['ischium_merus']), f'the walking legs\' ischium-merus {tuple(rw["ischium_merus"])} (the '
                                                     f'cheliped has no range of its own)'),
        cheliped_carpus_L=([ba['cheliped_carpus'] - v for v in rc['knee']], f'the rig\'s knee {tuple(rc["knee"])} included '
                                                                            f'(+ flexion closes it)'),
        cheliped_propodus_L=([v - ba['cheliped_propodus'] for v in rc['wrist']],    # X4f (the lead's call 4): the rig's
                             f'the rig\'s wrist {tuple(rc["wrist"])} absolute (the bind at '          # whole range
                             f'{ba["cheliped_propodus"]:.1f}; X4b-X4e gated -30..+40 from it)'),
        cheliped_dactyl_L=([v - op for v in claw], f'the claw open {claw} (the bind at {op:.0f})'))
    out = {}
    for j, (rr, how) in rel.items():
        W = sk.world[sk.index(j)]
        o_, z_ = W[:3, 3].copy(), unit(W[:3, 2])
        if j == 'cheliped_dactyl_L' and kind != 'crusher':
            # X4f, 2nd session: the cutter's claw, built on the LEFT, turns about ITS OWN hinge (the skeleton's frame rule,
            # decapod.skeleton's add); the skeleton's left dactyl is the crusher's, 14.79 mm along the claw axis from the
            # cutter's, and X4c-X4f posed the cutter's dactyl about that point in every gate, joint margin and hidden test
            cl_ = chain['claws'][kind]
            o_ = np.asarray(cl_['H'], np.float64).copy()
            z_ = unit(DP.RG.frame_from(cl_['u'], DP.perp(cl_['n'], cl_['u']))[:, 2])
        lo, hi = float(min(rr)), float(max(rr))
        ang = np.unique(np.round(np.concatenate([np.arange(lo, hi + 1e-9, MOTION['step']), [lo, hi, 0.0]]), 9))
        out[j] = dict(o=o_, z=z_, rel=(lo, hi), angles=ang, how=how)
    return out


def posed_inside(field, P, mo, child_moves, margin):
    """for points P (any shape (..., 3)) of one shell: True where they lie more than `margin` inside `field` (another
    shell) at EVERY pose of the motion mo; child_moves: P belongs to the moving side (posed by R about o), else the field
    does (P taken into its frame by R^-1)"""
    P = np.asarray(P, np.float64)
    sh = P.shape[:-1]
    Pf = P.reshape(-1, 3) - mo['o'][None, :]
    ok = np.ones(len(Pf), bool)
    for a in mo['angles']:
        R = rot_axis(mo['z'], a)
        Q = (Pf @ R.T if child_moves else Pf @ R) + mo['o'][None, :]
        ok &= field.eval(Q) < -margin
    return ok.reshape(sh)


def posed_inside_any(field, P, mo, child_moves, margin):
    """X4f: as posed_inside, True where points P lie more than `margin` inside `field` at ANY pose of the motion mo"""
    P = np.asarray(P, np.float64)
    sh = P.shape[:-1]
    Pf = P.reshape(-1, 3) - mo['o'][None, :]
    ok = np.zeros(len(Pf), bool)
    for a in mo['angles']:
        R = rot_axis(mo['z'], a)
        Q = (Pf @ R.T if child_moves else Pf @ R) + mo['o'][None, :]
        ok |= field.eval(Q) < -margin
    return ok.reshape(sh)


def section_ring(field, c, axis, n=36, tmax=60.0):
    """the field's section in the plane through c normal to axis: n rays' exits (n, 3), or None if c is outside"""
    axis = unit(axis)
    X = unit(np.cross(axis, [0.0, 1.0, 0.0]) if abs(axis[1]) < 0.9 else np.cross(axis, [1.0, 0.0, 0.0]))
    Y = np.cross(axis, X)
    th = 2.0 * np.pi * np.arange(n) / n
    D = np.cos(th)[:, None] * X[None, :] + np.sin(th)[:, None] * Y[None, :]
    r = field.cast(np.repeat(np.asarray(c, np.float64)[None, :], n, axis=0), D, tmax, step=0.05)
    if not np.isfinite(r).all():
        return None
    return np.asarray(c, np.float64)[None, :] + r[:, None] * D


def cut_depth(child, fixed, mo, X0, axis, t_back, t_min, centre_fn=None):
    """X4b, the lead's call 3 (module docstring): the depth t behind X0 (along -axis) where the child's buried end is
    cut: the DEEPEST end of the first run of depths (scanning from t_min deeper) whose cut face (the child's section
    there: its rim and two inner rings) lies MOTION margin inside `fixed` (the shells the joint does not move) at every
    pose. Deeper than that run the end would swing out through its parent's wall. Returns (t or None, dict): None when
    no depth is hidden (the end keeps the clay's, its faces visible in the range) or the run reaches the end's own pole
    (nothing to cut: the end is hidden over the range as it is); centre_fn(t): the section's centre (default on the
    axis)"""
    step, mg = MOTION['cut_step'], MOTION['margin']
    if not np.isfinite(t_back) or t_min > t_back - step:
        return None, dict(t_min=float(t_min), t_back=float(t_back), scanned=[], run=None,
                          why=f'the end reaches only {t_back:.2f} mm behind X0 (its least {t_min:.2f}): nothing to cut')
    ts = np.arange(t_min, t_back - 0.5 * step, step)
    run, first, rows = [], None, []
    for t in ts:
        c = X0 - t * axis if centre_fn is None else centre_fn(t)
        rim = section_ring(child, c, axis)
        if rim is None:
            break
        pts = np.vstack([rim, c[None, :] + 0.7 * (rim - c[None, :]), c[None, :] + 0.35 * (rim - c[None, :]), c[None, :]])
        hid = bool(posed_inside(fixed, pts, mo, True, mg).all())
        rows.append((float(t), hid))
        if hid:
            run.append(float(t))
            first = float(t) if first is None else first
        elif run:
            break
    info_ = dict(t_min=float(t_min), t_back=float(t_back), scanned=rows, run=(run[0], run[-1]) if run else None)
    if not run:
        return None, dict(info_, why='no depth whose face stays hidden over the range: the end keeps the clay\'s')
    if run[-1] >= t_back - 1.5 * step:
        return None, dict(info_, why='hidden to its own pole: nothing to cut', hidden_end=True)
    if run[-1] - run[0] < CAGE['cut_k'] + step:
        return None, dict(info_, why=f'the hidden run {run[0]:.2f}-{run[-1]:.2f} mm is shorter than the cut\'s rounding')
    return run[-1], dict(info_, why='cut', hidden_end=True)


def range_hidden_pts(pts, relations, margin=0.05):
    """X4b: per face given by its points (n, m, 3) (its centre and corners), True when it is HIDDEN OVER THE MOTION
    RANGE: every point inside another shell at every pose of the joint between them, for at least one relation (field,
    motion, this shell moves) (a face hidden by its parent over one joint's range or by its child over the other's is
    hidden at every combination of the two)"""
    out = np.zeros(len(pts), bool)
    for field, mo, moves in relations:
        out |= posed_inside(field, pts, mo, moves, margin).all(axis=1)
    return out


def range_hidden(V, Q, relations, margin=0.05):
    """range_hidden_pts per quad of one shell's low (V, Q): its centre and four corners. x04's gate 2 exempts only these
    faces from the tilt rule; X5 gives only these no texels"""
    Q = np.asarray(Q, int)
    return range_hidden_pts(np.concatenate([V[Q].mean(1)[:, None, :], V[Q]], axis=1), relations, margin)


# ============================================================================================ X4b: the features (§5.3)
# The lead's call 2 (X4b): §5.3's features in the crusher's cage before X5 (they change its topology), BY CONSTRUCTION
# (the beetle tibia's method, arthropod_cage.extrude: faces of the cage itself extruded, one shell, no stuck-on pieces):
#   - THE OCCLUSAL-EDGE CREASES: each finger's biting surface is the plan slab's flat side face (decapod_parts
#     plan_solid), a band facing the other finger (+m on the fixed finger, -m on the dactyl) with two rims where it
#     meets the broad faces (probe7 on the clay: the fixed finger's rims at +-27 deg about its spine at the gape to +-17
#     near the tip, the dactyl's +-29..+-41); the band's columns are laid ON the rims (occlusal_warp: each ring's
#     angles warped so columns +-crease cols land on the rims measured in its own plane), the rims creased semi-sharp
#     (§5.3's 'cutting edge' class 0.2-0.4 mm at life; s set so the limit's apex radius lands inside: x04 gate 8)
#   - THE MOLARS (one per finger) and THE LUMP by the dactyl's articulation: domes EXTRUDED from the band's faces
#     between the rims (the whole biting surface, as n04's molars span it), the creases dropped along their bases
#   - THE TUBERCLE ROWS: rounded cones extruded from single faces (2 x 2 for the large ones) along the palm's medial
#     margin and the dactyl's outer margin (c11 = L1's own claw), over the carpus (2 large dorsal, 2 small lateral, the
#     distal-medial spine) and the merus (the distal spine, a row of small ventral denticles: n04)
# Their sizes [E] read on the photos (n04's ruler 12 px / mm; c11 ~11 px / mm at the claw), their places on c11's
# traced outline (probe6) and n04's shares. Every feature's rings are targets the limit interpolates (fit_controls).
# X4c, THE LEAD'S CALL 2, FEATURES SPLIT BY SCALE (the AAA rule: the low carries the silhouette, the bake the rest): the
# CAGE keeps what reads in silhouette: the occlusal rims (creased), the two molars, the lump by the articulation, the
# carpus's and the merus's spines; the palm tubercles, the dactyl's tubercle, the carpus's dorsal and lateral knobs and
# the merus's ventral denticles (1.1-2.4 mm high on 1.4-3.6 mm feet: 25-65 texels at THE density, a few cage faces each)
# are STROKES for X6's high (STROKES: each with its source; crusher_features resolves each onto the clay and records it
# in the cage's meta['strokes'], x04 writes them). The domes and the spines are walked up their own profiles
# (profile_curve / walk_profile: X4b's fixed ring shares left the fixed molar's upper band at 0.28 mm against 1.76 mm
# radial edges, aspect 6.35, and the carpus spine's tip cap at 27.5 deg / 4.20: the X4b check).
FEAT = dict(
    # THE RIMS' CONSTRUCTION (crisp by construction, the beetle tibia's built sections): a creased limit that passes
    # through targets ON the clay's soft rim (slab_rho 0.9 mm, the envelope's k 2.4 blend) keeps its rounding: x4-3
    # measured 0.8 mm at s 4 (the corner's turn only 28 deg over +-0.36 mm, the rest spread over the neighbours; and
    # 5 fit levels took 400 s). So each rim target is moved corner_share of the way to the VIRTUAL CORNER of its ring
    # (the band's line through its two band-side neighbours met with the broad face's line through its two outer
    # neighbours, in the ring's plane), and s stays 3 (4 fit levels)
    crease=dict(cols=2, s=3.0, fade=(0.35, 0.75), r=(0.2, 0.4), half_arc=0.36, near=0.6, levels=4, corner_share=0.9),
    # the occlusal bands: the occlusal direction (deg about the claw part's spine from its X, +m), where the band (and
    # its warp) starts along the claw (s, claw frame mm; None: the spine's start), the warp's ramp (mm), the crease's
    # span in tau (the spine's 1..2: the distal end zone keeps no crease)
    # (the dactyl's rims at s 3.0 read 0.18-0.35 mm against the propodus's 0.21-0.40: s 2.85 there, x 2^0.15; X4d: its
    # base now the claw's membrane, the run starts past it and read 0.214-0.405 at 2.85, 0.212-0.400 at 2.9: 2.95)
    # X4e: notch: a socketed claw's propodus band starts this far (mm) past the hinge's s, on the rim's arch
    band=dict(propodus=dict(centre=0.0, s_from='gape', ramp=4.0, tau=(None, 1.97), notch=3.0),
              dactyl=dict(centre=180.0, s_from=None, ramp=0.0, tau=(1.06, 1.97), s=2.95)),
    # domes on the bands: (claw-frame s of the centre, width along the finger, height above the band; mm at life).
    # The fixed molar: c11's traced crest s ~92.5 (0.33 of the free finger from the gape's bottom), n04 0.37: s 93;
    # SPEC chela.molar_fixed 9.95 wide, ~0.35 of it high (c11 ~0.3, n04 ~0.4-0.5). The dactyl's molar: c11's bump s
    # 96-99 (0.45 of its occlusal chord from the tip; n04 0.40): s 98.5, SPEC molar_dactyl 5.97, 0.4 of it high (n04
    # 0.38). The lump: n04's second rounded lump 0.27 of the dactyl's occlusal chord from its base, on the gape side
    # (X4c: a dome's foot is the patch inset all round, FEAT profile dome; X4b's foot shares (0.70, 0.65) are gone)
    # X4d (the lead's call 6): the fixed molar as n04 / c08's BROAD LOW HUMP, not X4b's 3.5 mm tent with a crest. On the
    # band, only 4 columns across between its creased rims, an extruded dome rises to a crest (lowered to 2.2 mm it
    # still read peaked from the front, x04 _x4d4/5); extruded over the rims (one column past each, their creases broken
    # round it) the limit folded on 703 faces and the broken runs never reached their radius (x04 _x4d6). n04's molars
    # are the whole biting side SWELLING out past the occlusal edge: so the fixed molar is a SWELL (swell_patch: the
    # band, both rims and `swell` flank columns a side lifted along the patch's normal, the rims and `plateau` columns
    # past them riding up whole, no new faces), 2.6 mm high (n04's fixed-finger hump ~0.25-0.3 of its width), its patch
    # 13.5 mm along so its profile's half height spans ~9.6 mm (SPEC molar_fixed 9.95 wide; over 9.95 mm it read ~7);
    # plateau 1: the flank column beside each rim, its edges already near aspect 4, takes no stretch (scratch
    # probe_swell: aspect p99 4.69 -> 3.91, the rims' radii 0.313-0.390 mm, 0 folds); its small blunt teeth and the
    # bead row are strokes (STROKES crusher_teeth)
    domes=(dict(name='molar_fixed', shell='propodus', s=93.0, width=13.5, height=2.6, swell=3, plateau=1),
           dict(name='molar_dactyl', shell='dactyl', s=98.5, width=5.969, height=2.4),
           dict(name='lump_dactyl', shell='dactyl', s=87.0, width=5.0, height=1.8)),
    # X4e (the lead's call 1 on the X4d check): the two CONDYLES on the hinge axis, hard domes extruded from the propodus's
    # own faces where the axis leaves its clay: n04's ball in its cup (X4e: 6.4 mm across, 2.6 high; at 1.5 mm they read as
    # swellings, _x4e5). X4f: their size is the socket's (decapod_parts socket_parts condyle_d / condyle_h: n04's ball,
    # x2.n04.condyle_r of each claw's |G - A|, SOCKET condyle_h of it high), on the cup's disk where the moved axis leaves it
    # X4c: the carpus's and the merus's SPINES, the segment features the cage keeps (the knobs and denticles are
    # STROKES now): u along the segment's chitin from its proximal node, the direction about its axis ('dorsal' world
    # +y, 'lateral' +x on the left, 'medial' -x, 'ventral' -y, mixed by the angle given, deg from the first toward the
    # second), height, lean distally (deg), the foot's diameter d, the tip's radius (mm at life; c11's carpus spine and
    # n04's merus spine end in blunt points: [E] 0.3-0.45 by eye; at 0.30 the walk's last rings crowded under a 0.3 mm
    # cap and folded the limit at both tips, 48 / 16 faces: 0.45, probe f7); each spine's patch from its d
    # (knob_patch). The X4b check: c11's carpus spine leans distally, X4b's stood almost square: lean 15 -> 35
    segment_spines=dict(
        cheliped_carpus_L=(dict(name='carpus_spine', u=0.86, dir=('medial', 'dorsal', 35.0), height=4.2,
                                lean=35.0, kind='spine', d=3.0, tip=0.45),),
        cheliped_merus_L=(dict(name='merus_spine', u=0.90, dir=('dorsal', 'lateral', 0.0), height=3.6,
                               lean=30.0, kind='spine', d=3.0, tip=0.45),)),
    # the profiles. A SPINE: its FOOT a circle of its diameter d on the clay ('round': at most foot_max of the patch's
    # half-size), then rings WALKED up a cone with a rounded tip (profile_curve 'spine'); A DOME (X4c): its foot the
    # patch inset by inset_share x the patch's mean column edge ('inset': a strip of band along the rims, which stay
    # creased: their radius follows that distance), then rings walked up the 'bump' q = (1 - rho^2)^1.5 (level at the
    # foot, round on top: n04's molars), each outline rounding from the foot's toward the oval down to w_top of the
    # foot's from rho `round` in, shrinking evenly (extrude_patch's comment); every ring the squarest band the curve
    # allows (walk_profile) until rho falls under `end`; the cap's interior on the same curve. (x4-3 / X4b's fixed
    # shares: the fixed molar's second ring 0.28 vs 1.76 mm edges; the spine's 3 x 3 cap rose 1.1 mm over 0.3. X4c's
    # probes f1-f7: a spherical cap on an inset oval, a ball on an apron, aspect 4.4-50; a cosine bump, a volcano)
    profile=dict(dome=dict(foot='inset', shape='bump', inset_share=0.5, end=0.25, round=0.5, w_top=0.75),
                 spine=dict(foot='round', shape='spine', end=0.30),
                 condyle=dict(foot='round', shape='bump', end=0.30)),
    # (the foot's gaps to the patch's loop: x4-3 at along 0.85 left 0.8 mm against 3 mm edges at a dome's ends, aspect
    # 5.4; a knob's foot at 0.8 of a small patch, 7.3: so knobs take as many faces a side as keep d / 2 <= knob_fill of
    # the patch's half-size, and a dome's patch covers its width / along)
    foot=dict(across=0.75, along=0.75), foot_max=0.6, knob_fill=0.6,
    # X4f (2nd session): a condyle's dome needs a patch whose loop, projected onto the plane normal to the hinge axis,
    # holds n04's whole ball with condyle_band mm round it (the foot band's least width) and is no more eccentric about
    # the axis's exit than condyle_ecc (its farthest vertex over that clearance); else the ball is a STROKE for X6
    # (crusher_features)
    condyle_band=1.0, condyle_ecc=2.2)
FEATURE_REGIONS = ('molar', 'tubercle', 'spine', 'condyle')
# X4c, the lead's call 2: THE STROKES for X6's high (plan §5.5's S tier: CONE / ball strokes held out of the smooth),
# out of the cage: each one's place, size and SOURCE, as X4b built them (the X4b notes, probe6). kind: 'tubercle' a
# white-tipped rounded cone, 'knob' a low rounded one, 'denticle' a small blunt tooth; d the foot's diameter, height,
# lean distally (deg), all mm at life [E] from the photos (n04's ruler 12 px / mm, c11 ~11 px / mm at the claw)
STROKES = dict(
    # the claw margins: c11's traced bumps (L1's own claw; claw-frame s, m at the bind, on the margin's mid-thickness)
    claw=dict(propodus=((58.8, 20.7), (47.2, 18.8), (29.2, 14.4), (20.3, 8.3), (14.6, 6.0)), dactyl=((79.0, 17.0),),
              kind='tubercle', d=3.6, height=2.0, lean=20.0,
              source='c11 (M1 = L1\'s claws): the palm\'s medial margin outline idx 139 / 145 / 155 / 160 / 165 and the '
                     'dactyl\'s outer margin idx 125 (X4b probe6, x4b/look/c11_crusher_outline.png); c04 4-5 white-'
                     'tipped tubercles on the propodus\'s upper margin; sizes [E] c11 3-3.6 mm feet, ~2 mm high'),
    # A0 (x6fix_x7, the lead's shape audit): THE CUTTER'S tubercle row (X4d's cutter call had 'no domes and no tubercles';
    # c11's cutter shows four white-tipped domes along its palm's medial margin and one on its dactyl's outer margin by
    # the base, c04's live cutter 5-6 on its upper margin): c11 px (1348, 989), (1396, 1021), (1453, 1057), (1494, 1078)
    # and (1262, 855) (scratch x6fix_x7/look/grid_c11_cutter_margin.png, read by eye) in the cutter's claw frame by
    # Outline.claw; the dactyl's turned about its hinge from M1's 0.1 deg opening to the bind's 10 (s, m at the bind)
    claw_cutter=dict(propodus=((38.2, 12.6), (29.6, 10.8), (19.5, 8.5), (12.8, 6.3)), dactyl=((62.3, 9.6),),
                     kind='tubercle', d=3.4, height=1.9, lean=20.0,
                     source='c11 (M1): the cutter palm\'s medial margin, four white-tipped domes, and one on its '
                            'dactyl\'s outer margin by the base (x6fix_x7/look/grid_c11_cutter_margin.png); c04\'s live '
                            'cutter 5-6 on its upper margin; sizes [E] by eye beside the crusher\'s'),
    # the carpus and the merus (as FEAT segment_spines: u along the chitin, the direction about the axis)
    segment=dict(
        cheliped_carpus_L=(dict(name='carpus_dorsal_1', u=0.42, dir=('dorsal', 'lateral', 12.0), kind='tubercle',
                                d=3.4, height=2.4, lean=10.0),
                           dict(name='carpus_dorsal_2', u=0.62, dir=('dorsal', 'medial', 14.0), kind='tubercle',
                                d=3.4, height=2.4, lean=10.0),
                           dict(name='carpus_lateral_1', u=0.68, dir=('lateral', 'dorsal', 25.0), kind='knob',
                                d=1.6, height=1.4, lean=15.0),
                           dict(name='carpus_lateral_2', u=0.84, dir=('lateral', 'dorsal', 25.0), kind='knob',
                                d=1.6, height=1.4, lean=15.0),
                           # A0 (x6fix_x7, the lead's shape audit, point 3: the carpus's spines and knobs; c11 at
                           # 6.52 px a mm: THREE white domes on its dorsal face, the third toward its lateral side;
                           # r57282_7 / _8: a second, smaller spine on its inner margin before the big one)
                           dict(name='carpus_dorsal_3', u=0.52, dir=('dorsal', 'lateral', 45.0), kind='tubercle',
                                d=3.0, height=2.0, lean=10.0),
                           dict(name='carpus_medial_spine_2', u=0.58, dir=('medial', 'dorsal', 15.0), kind='spine',
                                d=2.6, height=2.8, lean=25.0)),
        cheliped_merus_L=tuple(dict(name=f'merus_ventral_{i + 1}', u=u_, dir=('ventral', 'medial', 20.0),
                                    kind='denticle', d=1.4, height=1.1, lean=20.0)
                               for i, u_ in enumerate((0.32, 0.46, 0.60, 0.74)))),
    segment_source=dict(
        cheliped_carpus_L='c11 (x4b/look/c11_carpus_merus.png): two large white tubercles on the carpus\'s dorsal face '
                          'mid-segment, two small on its lateral margin distally; c04 4-6 on its upper / outer faces',
        cheliped_merus_L='n04 (x4b/look/n04_merus.png): a row of small denticles along the merus\'s ventral edge'),
    # X4c, the lead's call 3 (plan §5.5's S tier): THE CUTTER'S SAW, conical denticles along its fixed finger's occlusal
    # edge: SPEC chela.saw_run (41.1 mm, M1's own: from its first nub at tip_share of the claw's length toward the base)
    # and saw_denticles (about 22 resolved on M1, ~1.9 mm pitch), on X0b's saw line (decapod_parts CUTTER saw_a / saw_b);
    # size [E] (§5.5: 0.5-1 mm high), leaning tipward
    cutter_saw=dict(count=22, tip_share=0.96, kind='denticle', d=1.4, height=0.6, lean=15.0,
                    source='c11 (M1 = L1\'s claws): the cutter\'s saw, X0b (5) and the 10-28 review (SPEC chela.saw_run, '
                           'saw_denticles); n04 25-30 by eye on the giant; sizes [E] plan 5.5'),
    # X4d, the lead's call 6 (plan 5.5's S tier): THE CRUSHER'S SMALL BLUNT TEETH on the dactyl and THE FIXED FINGER'S
    # BEAD ROW: rounded blunt beads ON the occlusal edge, one row per finger along its band's middle from the gape to
    # tip_clear mm short of the tip, the molars and the lump (FEAT domes, +- half their width + gap) left free; sizes
    # [E] read on n04 (the giant M3, CL ~139: its beads ~2.9 mm across at ~3 mm pitch at its 2x crop, 24 px / mm) scaled
    # to L1 (x 0.72)
    crusher_teeth=dict(dactyl=dict(kind='tooth', d=2.0, height=0.9, pitch=2.2),
                       propodus=dict(kind='bead', d=1.8, height=0.8, pitch=2.1),
                       tip_clear=3.0, gap=0.6, lean=10.0,
                       source='n04 (M3, the dried giant): a row of rounded blunt beads along each finger\'s occlusal edge, '
                              'the molars and the second lump interrupting it (x4c/look/n04_dac_margin_2x.png, '
                              'n04_gape_1x.png); the X4c builder: "the bead row ON the rim" (rim_measure)'))


def cutter_strokes(out, fr, info, spec, log=print):
    """X4c, the lead's call 3: the cutter's saw (STROKES cutter_saw) as strokes for X6 on its propodus: count denticles
    over SPEC chela.saw_run along X0b's saw line (claw-frame s, m at mid-thickness), from the first at tip_share x the
    claw's length toward the base, each placed on the clay (stroke_record) leaning tipward. Returns the rows"""
    st = STROKES['cutter_saw']
    nm = next(n for n in out if n.startswith('cheliped_propodus'))
    cg = out[nm]
    W, d, n = fr['W'], unit(fr['d']), unit(fr['n'])
    sa, sb = (np.asarray(p, np.float64) for p in info['claws']['cutter']['polys']['saw'])
    tdir = unit(sa - sb)                                # tipward along the saw line
    s_tip = st['tip_share'] * float(spec['chela']['cutter_len'])
    p_tip = sb + tdir * ((s_tip - sb[0]) / max(float(tdir[0]), 1e-6))
    run = float(spec['chela']['saw_run'])
    lean = unit(tdir[0] * d + tdir[1] * n)
    for i in range(st['count']):
        p2 = p_tip - tdir * (run * i / (st['count'] - 1))
        rec = stroke_record(cg.meta['field'], W + p2[0] * d + p2[1] * n, lean, f'saw_{i + 1}', st['kind'], st['d'],
                            st['height'], st['lean'], st['source'] + f' (s {p2[0]:.1f}, m {p2[1]:.1f})')
        cg.meta.setdefault('strokes', []).append(rec)
    moved = [r_['moved'] for r_ in cg.meta['strokes']]
    row = (f'{nm}: the saw, {st["count"]} STROKES for X6 ({st["kind"]}, d {st["d"]}, {st["height"]} mm high) over '
           f'{run:.1f} mm from s {s_tip:.1f}, {np.mean(moved):.2f} mm (max {max(moved):.2f}) from the saw line onto the clay')
    log('[decapod_cage] feature: ' + row)
    return [row]


def occlusal_rims(field, spine, centre_deg, us, n_rays=720, half=80.0):
    """the occlusal band's two RIMS at each spine fraction u: in the ring plane there, the sharpest turns of the section
    (n_rays in-plane rays) either side of the occlusal direction centre_deg (about the spine from its X); returns (m, 2)
    rad (the minus and plus rims, relative to the occlusal direction) and the stations kept"""
    th = np.radians(np.arange(n_rays) * 360.0 / n_rays)
    rel_all = (np.degrees(th) - centre_deg + 180.0) % 360.0 - 180.0
    out, kept = [], []
    w = max(2, n_rays // 180)
    for u in us:
        P, T, X, Y = spine.at(u)
        D = np.cos(th)[:, None] * X[None, :] + np.sin(th)[:, None] * Y[None, :]
        t = field.cast(np.repeat(P[None, :], n_rays, 0), D, 60.0, step=0.1)
        if not np.isfinite(t).all():
            continue
        Q = P[None, :] + t[:, None] * D
        d1 = np.roll(Q, -1, 0) - Q
        seg = np.linalg.norm(d1, axis=1)
        tg = d1 / np.maximum(seg[:, None], 1e-12)
        turn = np.degrees(np.arccos(np.clip((np.roll(tg, -w, 0) * np.roll(tg, w, 0)).sum(1), -1.0, 1.0)))
        arc = sum(np.roll(seg, s_) for s_ in range(-w, w))
        rate = turn / np.maximum(arc, 1e-9)
        pair = []
        for sgn in (-1.0, 1.0):
            m = (sgn * rel_all > 3.0) & (sgn * rel_all < half)
            j = np.nonzero(m)[0][np.argmax(rate[m])]
            pair.append(math.radians(rel_all[j]))
        out.append(pair)
        kept.append(float(u))
    return np.array(out), np.array(kept)


def occlusal_warp(K, centre_deg, cols, us, rims, w_fn, pull=None, span=None):
    """X4b: a ring's K angles WARPED so columns +-cols about the occlusal direction (centre_deg) land on the band's
    rims (occlusal_rims at the stations us, interpolated in u, smoothed), monotone (piecewise linear between -pi, the two
    rims and pi: the columns keep their order), blended in by w_fn(u) (0: equal angles). X4g: pull (deg) and span (a
    weight per station of us, 0..1): the next columns out, +-(cols + 1), `pull` deg outside each rim where span says
    (CAGE foot_pull: the collar's wall). Returns th_fn(tau)"""
    from scipy.ndimage import gaussian_filter1d
    th0 = 2.0 * np.pi * np.arange(K) / K
    c = math.radians(centre_deg)
    thc = cols * 2.0 * np.pi / K
    rm = gaussian_filter1d(rims[:, 0], 1.5, mode='nearest')
    rp = gaussian_filter1d(rims[:, 1], 1.5, mode='nearest')
    th3 = (cols + 1) * 2.0 * np.pi / K
    feet = None
    if pull is not None and span is not None and np.max(span) > 0.0:
        ws = gaussian_filter1d(np.asarray(span, np.float64), 1.5, mode='nearest')
        dm = -np.pi + (np.pi - th3) * (rm + np.pi) / (np.pi - thc)         # (where the plain warp puts those columns)
        dp = rp + (th3 - thc) * (np.pi - rp) / (np.pi - thc)
        pr = math.radians(pull)
        feet = (dm + ws * (rm - pr - dm), dp + ws * (rp + pr - dp))

    def th_fn(tau):
        u = float(np.clip(tau - 1.0, 0.0, 1.0))
        w = float(w_fn(u))
        if w <= 0.0:
            return th0.copy()
        a_m, a_p = float(np.interp(u, us, rm)), float(np.interp(u, us, rp))
        phi = (th0 - c + np.pi) % (2.0 * np.pi) - np.pi
        if feet is None:
            tgt = np.interp(phi, [-np.pi, -thc, thc, np.pi], [-np.pi, a_m, a_p, np.pi])
        else:
            f_m, f_p = float(np.interp(u, us, feet[0])), float(np.interp(u, us, feet[1]))
            tgt = np.interp(phi, [-np.pi, -th3, -thc, thc, th3, np.pi], [-np.pi, f_m, a_m, a_p, f_p, np.pi])
        return c + phi + w * (tgt - phi)
    return th_fn


def _quad_index(cg):
    """{frozenset(vertex ids): quad index} of a cage's quads"""
    return {frozenset(int(v) for v in q): i for i, q in enumerate(cg.Q)}


def tube_patch(cg, j0, nj, k0, na):
    """the tube's patch over rings j0..j0+nj and columns k0..k0+na (mod K): its vertex grid G[(a, b)] (a the column
    offset, b the ring offset) and its quads' indices (as stored); raises if a quad is gone (another feature's)"""
    ids = cg.meta['ring_ids']
    K = cg.K
    if j0 < 0 or j0 + nj > len(ids) - 1:
        raise ValueError(f'{cg.name}: a feature patch past the tube\'s rings ({j0}..{j0 + nj} of {len(ids)})')
    G = {(a, b): int(ids[j0 + b, (k0 + a) % K]) for a in range(na + 1) for b in range(nj + 1)}
    qi = _quad_index(cg)
    got = []
    for b in range(nj):
        for a in range(na):
            key = frozenset((G[(a, b)], G[(a + 1, b)], G[(a + 1, b + 1)], G[(a, b + 1)]))
            if key not in qi:
                raise ValueError(f'{cg.name}: a feature patch quad is not in the cage (taken by another feature?)')
            got.append(qi[key])
    return G, got


def profile_curve(shape, a, h, tip=None, n=400):
    """X4c: a feature's profile from its foot (r a, y 0) to its apex (0, h), mm: 'dome' a spherical cap of height h on
    radius a (n04's molars); 'spine' a cone ending in a sphere of radius `tip` tangent to it (c11's / n04's blunt
    points); 'bump' (X4c) q = (1 - rho^2)^1.5: level with its foot there, a narrow concave fillet out to its inflection
    at rho 0.71, convex and round over the rest (n04's molars: broad rounded humps rising out of the occlusal edge on a
    short fillet; a spherical cap on an inset oval read as a ball on an apron, a cosine bump, concave over its outer
    half, as a pointed volcano). Returns (rho = r / a, q = y / h, the arc length in mm from the foot), dense"""
    if shape == 'bump':
        rho_ = np.linspace(1.0, 0.0, n)
        r, y = a * rho_, h * (1.0 - rho_ * rho_) ** 1.5
    elif shape == 'dome':
        R = (a * a + h * h) / (2.0 * h)
        yc = h - R
        p0 = math.atan2(a, -yc) if yc < 0.0 else math.asin(min(a / R, 1.0))
        ph = np.linspace(p0, 0.0, n)
        r, y = R * np.sin(ph), yc + R * np.cos(ph)
    else:
        rt = float(min(tip or 0.25 * a, 0.45 * a, 0.45 * h))
        yc = h - rt
        # the cone r = a (1 - y / H) tangent to the tip's circle (centre (0, yc), radius rt): solve H by bisection
        def miss(H):
            return a * (1.0 - yc / H) - rt * math.sqrt(1.0 + (a / H) ** 2)
        lo_, hi_ = yc + 1e-6, 50.0 * h
        for _ in range(80):
            mid = 0.5 * (lo_ + hi_)
            lo_, hi_ = (mid, hi_) if miss(mid) < 0.0 else (lo_, mid)
        H = 0.5 * (lo_ + hi_)
        nrm = np.array([1.0, a / H]) / math.sqrt(1.0 + (a / H) ** 2)    # the line's outward normal (r, y)
        tp = np.array([0.0, yc]) + rt * nrm                              # the tangent point
        m_ = max(4, int(n * float(np.hypot(a - tp[0], tp[1])) / (float(np.hypot(a - tp[0], tp[1])) + rt * 1.6)))
        t_ = np.linspace(0.0, 1.0, m_, endpoint=False)
        r1, y1 = a + t_ * (tp[0] - a), t_ * tp[1]
        a0 = math.atan2(nrm[1], nrm[0])
        ang = np.linspace(a0, 0.5 * math.pi, n - m_)
        r2, y2 = rt * np.cos(ang), yc + rt * np.sin(ang)
        r, y = np.concatenate([r1, r2]), np.concatenate([y1, y2])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(r), np.diff(y)))])
    return r / a, y / h, s


def walk_profile(curve, D, height, end, k_max=2.5, D_of=None):
    """X4c: the raised rings up a profile (profile_curve's (rho, q, s)) over the loop's offsets D (nb, 3) at rho 1: from
    the foot, each next ring at the curve's sample whose band (ring i -> ring j: every column's four edges, the
    tangential ones rho x the loop's edges, the radial one from the radius and height steps) has the LEAST WORST
    max / min edge, until rho falls under `end` (a first try bounded one radial / least-tangential ratio: the short
    sides of an oval foot took long tangential edges over short radial ones, aspect 4.0-4.5). When the best step is
    the last one the curve leaves (the arc left to `end` shorter than a square band) and its band is worse than k_max,
    the walk stops there and the cap takes the rest (X4c: a last ring 0.003 rho in from the one before made a 0.01 mm
    band, aspect 50, on the dactyl's molar; on the spines' tips 0.04 mm bands folded the limit). D_of(rho) -> (nb, 3):
    the ring's own offsets when its outline changes shape as it rises (a dome's), else rho x D. Returns [(rho, q)]"""
    rho, q, _ = curve
    D = np.asarray(D, np.float64)
    if D_of is None:
        Ds = rho[:, None, None] * D[None, :, :]
    else:
        Ds = np.stack([np.asarray(D_of(float(r_)), np.float64) for r_ in rho])
    es = np.linalg.norm(np.roll(Ds, -1, axis=1) - Ds, axis=2)

    def worst(i, j):
        rad = np.sqrt(np.sum((Ds[j] - Ds[i]) ** 2, axis=1) + ((q[j] - q[i]) * height) ** 2)
        rad1 = np.roll(rad, -1)
        E = np.stack([es[i], es[j], rad, rad1], 1)
        return float((E.max(1) / np.maximum(E.min(1), 1e-12)).max())
    out, i = [], 0
    while True:
        cand = [j for j in range(i + 1, len(rho)) if rho[j] >= end]
        if not cand:
            break
        w = np.array([worst(i, j) for j in cand])
        jb = int(np.argmin(w))
        if jb == len(cand) - 1 and out and w[jb] > k_max:
            break
        out.append((float(rho[cand[jb]]), float(q[cand[jb]])))
        i = cand[jb]
    return out


def patch_frame(cg, G, got, na, nj, normal=None):
    """a tube patch's frame (extrude_patch's): (c the mean of its vertices, n0 its outward normal, e1 across its columns
    and e2 along its rings in the tangent plane at c, its half-sizes along them). X4f: normal the OUTWARD direction n0
    takes instead of the patch's own, as given (the caller knows the side): the hinge's condyles stand ON THE HINGE AXIS,
    solids of revolution about it, where the patch round the axis's exit straddles the cup disk's rim and its mean normal
    leaned the dome ~20 deg toward the notch (its apex 1.1 mm off the axis, scratch x4f probe_g23); on the cutter's a
    patch half on the notch face turned the mean normal's sign and the dome rose into the claw (probe e)"""
    V = cg.V
    Qa = np.asarray(cg.Q, int)
    c = V[np.array(sorted(set(G.values())))].mean(0)
    n0 = unit(np.cross(V[Qa[got, 2]] - V[Qa[got, 0]], V[Qa[got, 3]] - V[Qa[got, 1]]).sum(0))
    if normal is not None:
        n0 = unit(normal)
    e1 = sum(V[G[(na, b)]] - V[G[(0, b)]] for b in range(nj + 1))
    e1 = unit(e1 - n0 * float(e1 @ n0))
    e2 = np.cross(n0, e1)
    if float(e2 @ sum(V[G[(a, nj)]] - V[G[(a, 0)]] for a in range(na + 1))) < 0.0:
        e2 = -e2
    half_a = 0.5 * float(np.mean([(V[G[(na, b)]] - V[G[(0, b)]]) @ e1 for b in range(nj + 1)]))
    half_b = 0.5 * float(np.mean([(V[G[(a, nj)]] - V[G[(a, 0)]]) @ e2 for a in range(na + 1)]))
    return c, n0, e1, e2, half_a, half_b


def extrude_patch(cg, G, got, na, nj, profile, height, region, name, lean_dir=None, lean_deg=0.0, d=None, field=None,
                  foot=None, tip=None, center=None, normal=None):
    """a FEATURE extruded from the patch (tube_patch's G / got): the patch's quads removed; a FOOT ring on the clay
    inside the patch's loop (field: projected), then rings [(radius share, height share)] lifted along the feature's
    axis (the patch's outward normal turned lean_deg toward lean_dir), the last closed by an na x nj grid rising to the
    full height. The rings are laid in the patch's own 2D frame: every patch vertex's grid place (u, v) in [-1, 1]^2
    mapped onto the unit disc (the square-to-disc map), scaled by the feature's half-sizes: a knob (profile foot
    'round') a circle of diameter d (x4-3 shrank the patch's square loop: square knobs, the carpus's spine a blade); a
    dome (foot 'band') an oval, FEAT foot share of the patch's half-sizes (its rims' creases stay on the loop). Region
    per new quad `region`; cg.meta['region'] kept aligned; cg.meta['features'] records it (x04's gates). X4f: center a
    point the feature is centred on instead of the patch's vertices' mean (the hinge's condyles on the axis's exit; the
    caller sees that its foot fits inside the loop round it, so a round foot keeps its d: no FEAT foot_max cap), normal
    the frame's outward normal (patch_frame: the condyles' the hinge axis, their foot circles in the plane normal to it)"""
    V = cg.V
    loop = ([G[(a, 0)] for a in range(na + 1)] + [G[(na, b)] for b in range(1, nj + 1)]
            + [G[(a, nj)] for a in range(na - 1, -1, -1)] + [G[(0, b)] for b in range(nj - 1, 0, -1)])
    loop_ab = ([(a, 0) for a in range(na + 1)] + [(na, b) for b in range(1, nj + 1)]
               + [(a, nj) for a in range(na - 1, -1, -1)] + [(0, b) for b in range(nj - 1, 0, -1)])
    inner = [(a, b) for b in range(1, nj) for a in range(1, na)]
    c0, n0, e1, e2, half_a, half_b = patch_frame(cg, G, got, na, nj, normal=normal)   # (n0 outward: the cage is oriented)
    if center is not None:
        c0 = np.asarray(center, np.float64)
    ax = n0
    if lean_dir is not None and lean_deg:
        ld = unit(np.asarray(lean_dir, np.float64) - n0 * float(np.asarray(lean_dir) @ n0))
        ax = unit(math.cos(math.radians(lean_deg)) * n0 + math.sin(math.radians(lean_deg)) * ld)
    # the stored winding along the loop's first edge decides the new quads' (forward: the patch quad holds G00 -> G10)
    q0 = tuple(int(v) for v in cg.Q[got[0]])
    i0 = q0.index(loop[0])
    forward = q0[(i0 + 1) % 4] == loop[1]

    # the patch's own frame (patch_frame): e1 across (its columns, a), e2 along (its rings, b), in the tangent plane
    inset_foot = profile.get('foot') == 'inset'
    if profile.get('foot') == 'round':
        A_ = B_ = 0.5 * float(d or 2.0 * min(half_a, half_b))
        if center is None:                              # (X4f: a centred feature's caller fits its foot to the loop)
            A_, B_ = min(A_, FEAT['foot_max'] * half_a), min(B_, FEAT['foot_max'] * half_b)
    elif inset_foot:                                    # X4c: the foot inset all round: its half-sizes. The inset is
        #                                                 inset_share x the patch's mean column (across) edge: the rim's
        #                                                 crease radius follows its band-side neighbour's distance (the
        #                                                 propodus's 3.2 mm columns at 1.2 mm read 0.185-0.21 mm, the
        #                                                 dactyl's 2.4 mm at 1.2 mm 0.20-0.39: X4c probe f5)
        col_e = float(np.mean([np.linalg.norm(V[G[(a + 1, b)]] - V[G[(a, b)]]) for a in range(na) for b in (0, nj)]))
        inset_mm = profile['inset_share'] * col_e
        A_, B_ = half_a - inset_mm, half_b - inset_mm
    else:                                               # (foot: a dome's own (across, along) shares, else FEAT foot's)
        fa, fb = foot if foot is not None else (FEAT['foot']['across'], FEAT['foot']['along'])
        A_, B_ = fa * half_a, fb * half_b

    def disc(ab):
        """the grid places (a, b) -> concentric squares onto concentric circles (Shirley's map), x the half-sizes (a
        knob's circle, a dome's oval), as 3D offsets; and each place's radius (0..1). (x4-3: the patch's square shrunk
        made square knobs and the carpus's spine a blade; a dome on the patch's own grid scaled read as a box)"""
        ab = np.asarray(ab, np.float64).reshape(-1, 2)
        u, v = 2.0 * ab[:, 0] / na - 1.0, 2.0 * ab[:, 1] / nj - 1.0
        rho = np.maximum(np.abs(u), np.abs(v))
        th_ = np.arctan2(v, u)
        x, y = rho * np.cos(th_), rho * np.sin(th_)
        return (x * A_)[:, None] * e1[None, :] + (y * B_)[:, None] * e2[None, :], rho
    D_loop, _ = disc(loop_ab)
    rings_pts, prev = [], list(loop)
    new_q = []
    nb = len(loop)
    shares, cap_share = list(profile.get('rings', ())), float(profile.get('cap', 0.0))
    lam = 1.0
    # the FOOT ring on the clay (the knob's / the dome's outline inside the patch); a MID ring on the clay between the
    # loop and the foot where the loop is over twice the foot (x4-3: a 1.4 mm knob on 2.1 mm faces made trapezoids of
    # aspect 4.7-5.1 in one band)
    D_patch = V[loop] - c0
    D_patch = D_patch - (D_patch @ n0)[:, None] * n0[None, :]          # (in the tangent plane at c0)

    def on_clay(D_):
        P_ = c0 + D_
        return project(field, P_, iters=4) if field is not None else P_

    def worst_aspect(rings_):
        """the worst max / min edge of the bands between successive rings (3D points, the foot rings on the clay)"""
        w_ = 0.0
        for R0, R1 in zip(rings_[:-1], rings_[1:]):
            e_ = [np.linalg.norm(np.roll(R0, -1, 0) - R0, axis=1), np.linalg.norm(np.roll(R1, -1, 0) - R1, axis=1),
                  np.linalg.norm(R1 - R0, axis=1), np.linalg.norm(np.roll(R1, -1, 0) - np.roll(R0, -1, 0), axis=1)]
            E_ = np.stack(e_, 1)
            w_ = max(w_, float((E_.max(1) / np.maximum(E_.min(1), 1e-9)).max()))
        return w_
    def outline_w(rho_):
        """X4c, a dome: the share of the foot's own outline in the ring's (the rest the oval's): 1 at rho 1, w_top from
        profile 'round' in (smoothstep)"""
        x_ = np.clip((np.asarray(rho_, np.float64) - profile['round']) / (1.0 - profile['round']), 0.0, 1.0)
        return profile['w_top'] + (1.0 - profile['w_top']) * x_ * x_ * (3.0 - 2.0 * x_)
    # (the MID ring only where it lowers the foot bands' worst aspect, judged on the clay in 3D: it helps a small knob
    # on mid-sized faces, and hurt the palm's, whose foot sits close to the patch's short sides; x4-3 judged it in the
    # tangent plane and picked it where the real bands came out worse)
    D_of = None
    if inset_foot:
        # X4c, a DOME's construction (FEAT profile dome): its FOOT the patch's loop offset inward by `inset` mm in the
        # tangent plane (a parallel offset: an even strip of band along the rims, which stay creased, and short edges
        # at the patch's corners; X4b's oval foot at 0.65-0.75 of the half-sizes left 2-3 mm diagonals there: the foot
        # bands' aspect 5, and the rim's crease soft at those valence-5 corners, 0.43-0.49 mm); then its rings, each
        # outline rounding from the foot's partway into the oval of the foot's half-sizes (outline_w: down to w_top of
        # the foot's; all the way, the fixed molar's 4 x 8 cap on Shirley's oval crowded to aspect ~4, and a dome on
        # the patch's own grid alone read as a box, x4-3) and shrinking as rho^g per axis: g 1 (aniso False; X4c's
        # try at square cap cells, g from the cap's na / nj, made the bands of the fixed molar's 4 x 8 patch, cells
        # ~3 x 1.3 mm, aspect 13: the bands want the along size to shrink faster, the cap slower)
        # (the inset as a per-axis scale toward the patch's centre: the rims' sides and the ends move in `inset` mm and
        # the corners (inset, inset), each edge shrinking in proportion; a parallel offset shortened the corners' own
        # edges by `inset` each: the fixed molar's 1.3 mm rim-side edges went to 0.1-0.15 mm, aspect 13)
        F2 = np.column_stack([(D_patch @ e1) * (A_ / max(half_a, 1e-9)), (D_patch @ e2) * (B_ / max(half_b, 1e-9))])
        O2 = np.column_stack([D_loop @ e1, D_loop @ e2])
        ga = gb = 1.0
        if profile.get('aniso'):
            g_ = math.sqrt(A_ * B_)
            ga = math.log(profile['end'] * g_ * math.sqrt(na / nj) / A_) / math.log(profile['end'])
            gb = math.log(profile['end'] * g_ * math.sqrt(nj / na) / B_) / math.log(profile['end'])
            ga, gb = float(np.clip(ga, 0.6, 1.6)), float(np.clip(gb, 0.6, 1.6))

        def D_of(rho_):
            w_ = float(outline_w(rho_))
            x_ = (w_ * F2[:, 0] + (1.0 - w_) * O2[:, 0]) * rho_ ** ga
            y_ = (w_ * F2[:, 1] + (1.0 - w_) * O2[:, 1]) * rho_ ** gb
            return x_[:, None] * e1[None, :] + y_[:, None] * e2[None, :]
        foot_rings = [D_of(1.0)]
    else:
        P_mid, P_ft = on_clay(0.5 * (D_patch + D_loop)), on_clay(D_loop)
        use_mid = worst_aspect([V[loop], P_mid, P_ft]) < worst_aspect([V[loop], P_ft])
        foot_rings = [0.5 * (D_patch + D_loop), D_loop] if use_mid else [D_loop]
    n_foot = 0
    for Dr in foot_rings:
        P = c0 + Dr
        if field is not None:
            P = project(field, P, iters=4)
        ids_ = cg.add(P)
        for m in range(nb):
            q = (prev[m], prev[(m + 1) % nb], ids_[(m + 1) % nb], ids_[m])
            new_q.append(q if forward else q[::-1])
            n_foot += 1
        prev = ids_
    cb = P.mean(0)
    P_foot = P.copy()
    q_fn = None
    if profile.get('shape'):
        # X4c: the rings walked up the profile's own curve (FEAT profile's comment: each band the squarest the curve
        # allows, walk_profile), the foot's half-sizes setting the curve's radius
        a_eff = float(np.sqrt(max(A_, 1e-9) * max(B_, 1e-9)))
        curve = profile_curve(profile['shape'], a_eff, height, tip=tip)
        shares = walk_profile(curve, D_loop, height, profile['end'], D_of=D_of)
        if not shares:
            shares = [(profile['end'], float(np.interp(profile['end'], curve[0][::-1], curve[1][::-1])))]
        q_fn = (lambda r_, c_=curve: np.interp(r_, c_[0][::-1], c_[1][::-1]))       # noqa: E731
    elif not inner:                                     # a single face: its top is a last small ring at full height
        shares = shares + [(cap_share, 1.0)]
    # X4c: each raised point follows its own foot point's place on the clay, fading with the height share (the X4b
    # check: planar rings at fixed heights over the foot's centroid undercut a leaning knob on a curved margin, where the
    # projected foot spans 1.0-2.7 mm in height); a dome's rings lie ON the clay under their outline, lifted along the
    # axis by the profile's height
    d_foot = P_foot - (cb + D_loop)
    for rho, hq in shares:
        if inset_foot:
            P = on_clay(D_of(rho)) + hq * height * ax
        else:
            P = cb + rho * D_loop + hq * height * ax + ((1.0 - hq) * rho) * d_foot
        ids_ = cg.add(P)
        for m in range(nb):
            q = (prev[m], prev[(m + 1) % nb], ids_[(m + 1) % nb], ids_[m])
            new_q.append(q if forward else q[::-1])
        rings_pts.append(ids_)
        prev = ids_
    # the cap: the last ring as an na x nj grid's boundary (G's indexing), its interior at the full height
    last = prev
    Gc = {}
    for a in range(na + 1):
        Gc[(a, 0)] = last[a]
    for b in range(1, nj + 1):
        Gc[(na, b)] = last[na + b]
    for a in range(na - 1, -1, -1):
        Gc[(a, nj)] = last[na + nj + (na - a)]
    for b in range(nj - 1, 0, -1):
        Gc[(0, b)] = last[2 * na + nj + (nj - b)]
    if inner:
        # the grid cap's interior: the patch's interior grid places on the disc at the last ring's scale (x4-3's cap at
        # 0.2 of the patch stretched the molars' caps to aspect 11), its height rising from the last ring's to the full
        # height at the centre (1 - rho^2, rho the place's radius on the disc)
        D_in, rho_n = disc(inner)
        s_l, q_l = float(shares[-1][0]), float(shares[-1][1])
        if q_fn is not None:                            # X4c: on the profile's own curve
            hq_i = np.asarray(q_fn(np.clip(rho_n, 0.0, 1.0) * s_l), np.float64)
        else:
            hq_i = q_l + (1.0 - q_l) * (1.0 - np.clip(rho_n, 0.0, 1.0) ** 2)
        ids_i = [int(G[k_]) for k_ in inner]
        if inset_foot:                                  # X4c: the patch's own interior places (mapped onto the foot)
            #                                             mixed with the oval's as the last ring's outline is, at its
            #                                             scale, on the clay, lifted
            D_pin = V[ids_i] - c0
            px_, py_ = (D_pin @ e1) * (A_ / max(half_a, 1e-9)), (D_pin @ e2) * (B_ / max(half_b, 1e-9))
            w_ = float(outline_w(s_l))
            x_ = (w_ * px_ + (1.0 - w_) * (D_in @ e1)) * s_l ** ga
            y_ = (w_ * py_ + (1.0 - w_) * (D_in @ e2)) * s_l ** gb
            Pi = on_clay(x_[:, None] * e1[None, :] + y_[:, None] * e2[None, :]) + (hq_i * height)[:, None] * ax[None, :]
        else:
            Pi = cb + s_l * lam * D_in + (hq_i * height)[:, None] * ax[None, :]
        # (the patch's own interior vertices, freed with its quads, moved there: new ones left those unused, x04 gate 1,
        # and their limit points far off)
        cg.V[ids_i] = Pi
        Gc.update(dict(zip(inner, ids_i)))
    for b in range(nj):
        for a in range(na):
            q = (Gc[(a, b)], Gc[(a + 1, b)], Gc[(a + 1, b + 1)], Gc[(a, b + 1)])
            new_q.append(q if forward else q[::-1])
    keep = np.ones(len(cg.Q), bool)
    keep[got] = False
    reg = np.asarray(cg.meta['region'])
    cg.Q = [q for q, k_ in zip(cg.Q, keep) if k_] + new_q
    cg.meta['region'] = np.concatenate([reg[keep].astype('<U16'), np.array([region] * len(new_q), dtype='<U16')])
    rbar = float(np.mean(np.linalg.norm(D_of(1.0) if inset_foot else D_loop, axis=1)))
    cg.meta.setdefault('features', []).append(dict(name=name, region=region, c0=c0, axis=ax, normal=n0, height=height,
                                                   r_base=rbar, half=(A_, B_), quads=[tuple(int(v) for v in q)
                                                                                      for q in new_q],
                                                   n_foot=n_foot, loop=list(loop)))
    return cg.meta['features'][-1]


def swell_patch(cg, G, got, na, nj, e, height, region, name, plateau=0):
    """X4d (the lead's call 6): a SWELLING of the cage's own surface over the patch (tube_patch's G / got, na columns x
    nj rings of faces): every patch vertex moved along the patch's outward normal by height x B(along) x C(across), B =
    (1 - x^2)^1.5 over the patch's rings (x -1..1: zero on its first and last ring and level there), C = 1 over its
    middle columns (the occlusal band and both creased rims, which ride out whole: their runs and corners kept, and
    `plateau` flank columns a side past them) and a smoothstep to 0 over its other e - plateau outer columns a side (the
    swell's flanks onto the broad faces). No faces added, the creases untouched: n04's crusher molars, the whole biting
    side swelling out past the occlusal edge into a broad rounded hump (an extruded dome between the rims read as a
    tent with a crest from the front; extruded over the rims it folded the limit, x04 _x4d6). (x04 _x4d7: the flank
    column next to a rim, its edges 5.0-5.4 mm down the finger's side beside 1.4 mm rings, already near aspect 4, took
    the lift difference along its length: 4.8, hence `plateau`; _x4d8: each vertex along its own clay normal turned the
    rims' corners, their radii 0.32-0.60 mm, out of the class)
    Region per patch quad `region`; cg.meta['features'] records it as extrude_patch does (x04's gates: no foot, its
    outward from under its centre)"""
    V = cg.V
    Qa = np.asarray(cg.Q, int)
    loop = ([G[(a, 0)] for a in range(na + 1)] + [G[(na, b)] for b in range(1, nj + 1)]
            + [G[(a, nj)] for a in range(na - 1, -1, -1)] + [G[(0, b)] for b in range(nj - 1, 0, -1)])
    allv = np.array(sorted(set(G.values())))
    c0 = V[allv].mean(0)
    n0 = unit(np.cross(V[Qa[got, 2]] - V[Qa[got, 0]], V[Qa[got, 3]] - V[Qa[got, 1]]).sum(0))
    e1 = sum(V[G[(na, b)]] - V[G[(0, b)]] for b in range(nj + 1))
    e1 = unit(e1 - n0 * float(e1 @ n0))
    e2 = np.cross(n0, e1)
    half_a = 0.5 * abs(float(np.mean([(V[G[(na, b)]] - V[G[(0, b)]]) @ e1 for b in range(nj + 1)])))
    half_b = 0.5 * abs(float(np.mean([(V[G[(a, nj)]] - V[G[(a, 0)]]) @ e2 for a in range(na + 1)])))
    D_loop = V[loop] - c0
    rbar = float(np.mean(np.linalg.norm(D_loop - (D_loop @ n0)[:, None] * n0[None, :], axis=1)))
    ramp = max(e - plateau, 0)
    for (a, b), v in G.items():
        x = 2.0 * b / nj - 1.0
        c_ = min(1.0, min(a, na - a) / float(ramp)) if ramp > 0 else 1.0
        V[v] = V[v] + height * (1.0 - x * x) ** 1.5 * (c_ * c_ * (3.0 - 2.0 * c_)) * n0
    reg = np.asarray(cg.meta['region']).astype('<U16')
    reg[np.asarray(got, int)] = region
    cg.meta['region'] = reg
    cg.meta.setdefault('features', []).append(dict(name=name, region=region, c0=c0, axis=n0, normal=n0, height=height,
                                                   r_base=rbar, half=(half_a, half_b),
                                                   quads=[tuple(int(v) for v in Qa[q]) for q in got], n_foot=0,
                                                   loop=list(loop)))
    return cg.meta['features'][-1]


def crease_chain(cg, chain, s, fade):
    """a crease along the vertex chain (consecutive ids, each pair an edge of the cage), its sharpness s (a number, or
    one per edge) faded over its first and last edges (fade: the shares of s; arthropod_cage.CREASE_FADE's way); skips
    pairs that are not edges"""
    n_e = len(chain) - 1
    if n_e < 1:
        return 0
    s = np.broadcast_to(np.asarray(s, np.float64), (n_e,))
    w = np.ones(n_e)
    for i_, f_ in enumerate(fade):
        if i_ < n_e:
            w[i_] = min(w[i_], f_)
            w[n_e - 1 - i_] = min(w[n_e - 1 - i_], f_)
    edges = set()
    for q in cg.Q:
        for k in range(4):
            a, b = int(q[k]), int(q[(k + 1) % 4])
            edges.add((min(a, b), max(a, b)))
    n = 0
    for (a, b), w_, s_ in zip(zip(chain[:-1], chain[1:]), w, s):
        key = (min(a, b), max(a, b))
        if key in edges and w_ * s_ > 0:
            cg.sharp[key] = float(w_ * s_)
            n += 1
    return n


def knob_patch(cg, j, k, d):
    """a knob's patch round the face (band j, column k): as many columns / rings as keep its foot (d / 2) within FEAT
    knob_fill of the patch's half-size (2 at least), centred on the face, inside the spine's section. Returns (j0, nj,
    k0, na)"""
    ids = cg.meta['ring_ids']
    taus = np.asarray(cg.meta['taus'])
    K = cg.K
    V = cg.V
    col = 0.5 * (np.linalg.norm(V[ids[j, (k + 1) % K]] - V[ids[j, k]])
                 + np.linalg.norm(V[ids[j + 1, (k + 1) % K]] - V[ids[j + 1, k]]))
    ring = 0.5 * (np.linalg.norm(V[ids[j + 1, k]] - V[ids[j, k]])
                  + np.linalg.norm(V[ids[j + 1, (k + 1) % K]] - V[ids[j, (k + 1) % K]]))
    fill = FEAT['knob_fill']
    # (2 a side at least: x4-3's 1 x 2 patches, 6-point rings, made foot bands of aspect 8-11 and limit folds)
    na = max(2, int(math.ceil(d / (fill * col))))
    nj = max(2, int(math.ceil(d / (fill * ring))))
    okr = np.nonzero((taus >= 1.0) & (taus <= 2.0))[0]
    j0 = int(np.clip(j - (nj - 1) // 2, okr.min(), okr.max() - nj))
    return j0, nj, (k - (na - 1) // 2) % K, na


def free_patch(cg, j0, nj, k0, na):
    """tube_patch at (j0, k0), or one or two rings off it where a neighbouring knob holds a face (c11's last two palm
    tubercles 5.7 mm apart on 3.5 mm rings); None when every place is taken"""
    taus = np.asarray(cg.meta['taus'])
    okr = np.nonzero((taus >= 1.0) & (taus <= 2.0))[0]
    for dj in (0, -1, 1, -2, 2):
        j_ = j0 + dj
        if j_ < okr.min() or j_ + nj > okr.max():
            continue
        try:
            G, got = tube_patch(cg, j_, nj, k0, na)
            return j_, G, got
        except ValueError:
            continue
    return None


def spine_patch(cg, fs, a0, axis, u_end):
    """the face a segment spine fs (FEAT segment_spines) stands on and the patch knob_patch cuts round it, on cage cg:
    the face nearest u along the chitin (u_end its length: the carpus's to the wrist ring) and the spine's direction
    about the axis. Returns (jf, kf, j0, nj, k0, na). x6fix_x7 (11-11): one function for crusher_features (which cuts the
    patch) and spine_feet (which keeps the joint margins off it: the patch is not centred on the foot, knob_patch's
    k0 = k - (na - 1) // 2 puts a 2-face patch's second column on one side)"""
    ids = cg.meta['ring_ids']
    taus = np.asarray(cg.meta['taus'])
    sp = cg.meta['spine']
    axis = unit(axis)
    X = sp.X[0]
    Y = np.cross(sp.T[0], X)
    d1, d2, ang = fs['dir']
    dv = unit(math.cos(math.radians(ang)) * _dir_of(d1, axis) + math.sin(math.radians(ang)) * _dir_of(d2, axis))
    th_d = math.atan2(float(dv @ Y), float(dv @ X)) % (2.0 * np.pi)
    a_t = fs['u'] * u_end
    ring_a = np.array([float((cg.V[ids[j]].mean(0) - a0) @ axis) for j in range(len(ids))])
    ok = (taus >= 1.0) & (taus <= 2.0)
    th_r = np.asarray(cg.meta['th'])
    # the face at (u, the direction), then the knob's patch round it (knob_patch: FEAT knob_fill)
    mid = 0.5 * (ring_a[:-1] + ring_a[1:])
    okb = ok[:-1] & ok[1:]
    jf = int(np.argmin(np.where(okb, np.abs(mid - a_t), np.inf)))
    thm = np.angle(np.exp(1j * th_r) + np.exp(1j * np.roll(th_r, -1))) % (2.0 * np.pi)
    kf = int(np.argmin(np.abs((thm - th_d + np.pi) % (2.0 * np.pi) - np.pi)))
    j0, nj, k0, na = knob_patch(cg, jf, kf, fs['d'])
    # x6fix_x7 (11-11): an EVEN count of faces has a VERTEX at its middle, where extrude_patch stands the spine: that
    # vertex is the ring and the column nearest FEAT's (u, direction). knob_patch's face-centred rule (j - (n - 1) // 2)
    # put the merus's 2 x 2 patch one face distal and one column medial of its (u 0.90, dorsal): the spine at u 0.95, 22
    # deg medial, the patch's medial edge 0.4 mm inside the carpus at the bind and 1.4 mm at the knee's fold (x04 _a0g;
    # scratch x6fix_x7 claw/probe_merus_table.py); centred, every patch vertex stays 1.2 mm or more outside the carpus
    # over the knee's whole range (the same table, rings 18-21 x columns 7-9). An odd count keeps the face-centred patch
    okr = np.nonzero(ok)[0]
    if nj % 2 == 0:
        jc = int(np.argmin(np.where(ok, np.abs(ring_a - a_t), np.inf)))
        j0 = int(np.clip(jc - nj // 2, okr.min(), okr.max() - nj))
    if na % 2 == 0:
        kc = int(np.argmin(np.abs((th_r - th_d + np.pi) % (2.0 * np.pi) - np.pi)))
        k0 = (kc - na // 2) % cg.K
    return jf, kf, j0, nj, k0, na


def _dir_of(name, axis):
    """an anatomical direction (world, the LEFT side) made perpendicular to a segment's axis"""
    d = dict(dorsal=(0.0, 1.0, 0.0), ventral=(0.0, -1.0, 0.0), lateral=(1.0, 0.0, 0.0), medial=(-1.0, 0.0, 0.0))[name]
    v = np.asarray(d, np.float64)
    return unit(v - axis * float(v @ axis))


def stroke_record(field, P0, lean_dir, name, kind, d, height, lean, source):
    """X4c: one STROKE for X6's high (STROKES): P0 moved onto the clay (the shell's build field) along its normal, the
    clay's outward normal there, the stroke's axis that normal turned `lean` deg toward lean_dir; mm at life"""
    P = project(field, np.asarray(P0, np.float64)[None, :], iters=6)[0]
    nrm = field.normals(P[None, :])[0]
    ld = np.asarray(lean_dir, np.float64)
    ld = ld - nrm * float(ld @ nrm)
    ax = nrm if np.linalg.norm(ld) < 1e-9 else unit(math.cos(math.radians(lean)) * nrm + math.sin(math.radians(lean))
                                                     * unit(ld))
    return dict(name=name, kind=kind, anchor=P.tolist(), normal=nrm.tolist(), axis=ax.tolist(), d=float(d),
                height=float(height), lean=float(lean), source=source, moved=float(np.linalg.norm(P - P0)))


def crusher_features(out, fr, info, log=print, claw=True, kind='crusher'):
    """X4b, the lead's call 2 (FEAT's comment): the occlusal creases on the crusher's two claw parts (their columns
    already on the rims: claw_cage occlusal), the molars and the lump on the bands, the tubercle rows on the claw's
    margins, the carpus and the merus. claw False (X4c, the cutter's build): only the carpus's and the merus's (the
    proximal chain is both chelipeds', so the cutter's build carries the same spines and strokes and its proximal cages
    equal the crusher's). claw 'creases' (X4d, the lead's call 5: the CUTTER's cutting edges, kind 'cutter'): the claw's
    occlusal rims creased too, no domes (its saw is strokes, cutter_strokes, sitting on the band between the creased
    rims); A0 (x6fix_x7): its margin tubercles as strokes (STROKES claw_cutter), as c11 / c04 show them. Edits the cages
    in `out` in place; returns a summary (rows)"""
    rows = []
    cr = FEAT['crease']
    W, d, n = fr['W'], unit(fr['d']), unit(fr['n'])
    s_of = lambda P: (np.asarray(P) - W) @ d          # noqa: E731
    tg = '' if kind == 'crusher' else '_cutter'
    for part, nm in ((('propodus', f'cheliped_propodus{tg}_L'), ('dactyl', f'cheliped_dactyl{tg}_L')) if claw else ()):
        cg = out[nm]
        bd = FEAT['band'][part]
        ids = cg.meta['ring_ids']
        taus = np.asarray(cg.meta['taus'])
        K = cg.K
        k_occ = int(round(bd['centre'] / 360.0 * K)) % K
        occ_ = cg.meta.get('occlusal') or {}
        cols_ = int(occ_.get('cols', cr['cols']))       # (X4h: the warp's own, claw_cage; and the rims' corner below)
        nb_ = tuple(occ_.get('band_nb', (1, 2)))
        cs_ = float(occ_.get('corner_share', cr['corner_share']))
        ks = ((k_occ - cols_) % K, (k_occ + cols_) % K)
        lo_t = bd['tau'][0] if bd['tau'][0] is not None else 1.0
        sel = np.nonzero((taus >= lo_t - 1e-9) & (taus <= bd['tau'][1] + 1e-9))[0]
        if bd['s_from'] == 'gape':
            s_g = float(np.asarray(info['claws'][kind]['polys']['gape'])[0])
            sel = sel[np.array([s_of(cg.V[ids[j, k_occ]]) >= s_g for j in sel])]
        if margins_of(cg) and len(sel):                 # (X4d: no crease on the joint's membrane, the dactyl's base)
            sel = sel[np.array([bool(chitin_mask(cg, cg.V[ids[j, [ks[0], k_occ, ks[1]]]]).all()) for j in sel])]
        sock = info['claws'][kind].get('socket')
        if part == 'dactyl' and sock is not None and len(sel):   # (X4e: none on the fan: from the heel's front on. The
            sa_, ci_ = sock['angles'], info['claws'][kind]          # heel slides inside the collar, and its crisped rims
            ph_vis = sa_['phi_front'] + (ci_['want'] - sa_['open_c11'])        # stood 0.87 mm off the clay into it)
            sel = sel[hinge_angle(cg.V[ids[sel, k_occ]], sock)[0] > ph_vis]

        def dome_rings(dm):
            """the rings that COVER a dome's width along the finger (the last at or before its start, the first at or
            past its end), inside the spine's section (x4-3's rings strictly inside gave the dactyl's 6 mm molar 3.5;
            its patch over width / along, 14 mm on the fixed finger's curve, let the planar foot cross its own loop)"""
            s_j = np.array([s_of(cg.V[ids[j, k_occ]]) for j in range(len(ids))])
            ok_j = np.nonzero((taus >= 1.0) & (taus <= 2.0))[0]
            lo_s, hi_s = dm['s'] - 0.5 * dm['width'], dm['s'] + 0.5 * dm['width']
            before = ok_j[s_j[ok_j] <= lo_s + 1e-9]
            after = ok_j[s_j[ok_j] >= hi_s - 1e-9]
            j0 = int(before.max()) if len(before) else int(ok_j.min())
            j1 = int(after.min()) if len(after) else int(ok_j.max())
            return j0, max(j1 - j0, 2), s_j
        doms = [dm for dm in (FEAT['domes'] if claw is True else ()) if dm['shell'] == part]
        spans = []
        # the two rims' creases over the band's whole span (along a dome's base too: the rim runs on, the dome rising
        # from the band between the rims; x4-3 broke them there and the fixed finger's runs, 3-4 edges, never reached
        # their sharpness through the fade), faded at the ends
        n_cr = 0
        runs = []
        for j in sel:
            if runs and j == runs[-1][-1] + 1:
                runs[-1].append(int(j))
            else:
                runs.append([int(j)])
        moved = []
        for k, side in ((ks[0], 1), (ks[1], -1)):      # (side: the band's columns lie at k + side, k + 2 side)
            for run in runs:
                if len(run) < 3:
                    continue
                # the rim's targets toward each ring's virtual corner (FEAT crease: crisp by construction), weighted as
                # the crease's fade (its faded ends move less), the steps smoothed along the run (x4-3: per-ring corners
                # made the dactyl's rim wavy)
                n_r = len(run)
                steps = np.zeros((n_r, 3))
                for i_, j in enumerate(run):
                    w_ = 1.0
                    for e_, f_ in enumerate(cr['fade']):
                        if i_ <= e_ or i_ >= n_r - 1 - e_:
                            w_ = min(w_, f_)
                    # (X4h: a part's own band-side neighbours, CAGE dactyl_cutter band_nb: with the cutter dactyl's band
                    # in 8 columns the first two sat on the clay's rounded rim, the corner fell short and the rims read
                    # 0.385-0.447; at (2, 4) 0.204-0.293 and the limit tilted beside them on 267 faces, scratch r4)
                    B1, B2 = cg.V[ids[j, (k + nb_[0] * side) % K]], cg.V[ids[j, (k + nb_[1] * side) % K]]
                    F1, F2 = cg.V[ids[j, (k - side) % K]], cg.V[ids[j, (k - 2 * side) % K]]
                    u_, w3 = unit(B1 - B2), unit(F1 - F2)
                    b_ = float(u_ @ w3)
                    if abs(b_) > 0.97:
                        continue
                    r0 = B1 - F1
                    d_, e3 = float(u_ @ r0), float(w3 @ r0)
                    tt = (b_ * e3 - d_) / (1.0 - b_ * b_)
                    ss_ = (e3 - b_ * d_) / (1.0 - b_ * b_)
                    if not (0.0 <= tt <= 8.0 and 0.0 <= ss_ <= 8.0):
                        continue
                    C_ = 0.5 * ((B1 + tt * u_) + (F1 + ss_ * w3))
                    R_ = cg.V[ids[j, k]]
                    step = cs_ * w_ * (C_ - R_)
                    if float(np.linalg.norm(step)) > 2.0:  # (a guard: a rim far from its virtual corner is no rim)
                        continue
                    steps[i_] = step
                for _ in range(2):                      # (1-2-1 along the run, its ends held)
                    steps[1:-1] = 0.25 * steps[:-2] + 0.5 * steps[1:-1] + 0.25 * steps[2:]
                for i_, j in enumerate(run):
                    if float(np.linalg.norm(steps[i_])) > 1e-9:
                        cg.V[ids[j, k]] = cg.V[ids[j, k]] + steps[i_]
                        moved.append(float(np.linalg.norm(steps[i_])))
        # the DOMES on the band, after the rims' corners (a dome moves its patch's interior vertices up into its cap, so
        # the corners must read the band first; the crusher's only)
        for dm in doms:
            j0, nj, s_j = dome_rings(dm)
            e_ = int(dm.get('swell', 0))                # (X4d: a SWELL, the band and rims plus e_ flank columns a side)
            na_d = 2 * cols_ + 2 * e_
            G, got = tube_patch(cg, j0, nj, (ks[0] - e_) % K, na_d)
            if e_:
                f = swell_patch(cg, G, got, na_d, nj, e_, dm['height'], 'molar', dm['name'],
                                plateau=int(dm.get('plateau', 0)))
            else:
                # (X4c: the foot on the clay, field passed: the X4b check found the domes' planar feet left notches
                # 0.35-0.45 mm under the clay at the dactyl's molar's and lump's near ends, extrude_patch's docstring)
                f = extrude_patch(cg, G, got, na_d, nj, FEAT['profile']['dome'], dm['height'], 'molar', dm['name'],
                                  foot=dm.get('foot'), field=cg.meta.get('field'))
            spans.append((j0, j0 + nj))
            rows.append(f'{dm["name"]} on {nm}: rings {j0}..{j0 + nj} (s {s_j[j0]:.1f}-{s_j[j0 + nj]:.1f}), '
                        f'{na_d} x {nj} faces' + (f' (a swell: the band, its rims and {e_} flank columns a side, '
                                                  f'lifted)' if e_ else '')
                        + f', {dm["height"]:.1f} mm high, base r {f["r_base"]:.2f}')
        # one sharpness per part (FEAT band s, else FEAT crease s; x4-3 tried s from each edge's spacing across the rim:
        # the spread widened to 0.16-0.51 mm, the corner construction ruling the radius, not the spacing)
        s_part = bd.get('s', cr['s'])
        for k in ks:
            for run in runs:
                if len(run) >= 3:
                    n_cr += crease_chain(cg, [int(ids[j, k]) for j in run], s_part, cr['fade'])
        cg.meta.setdefault('creases', []).append(dict(cols=ks, rings=(int(sel.min()), int(sel.max())) if len(sel) else None,
                                                      edges=n_cr))
        rows.append(f'{nm}: the occlusal rims creased along columns {ks} over rings {int(sel.min())}..{int(sel.max())} '
                    f'({n_cr} edges, s {cr["s"]}, faded {cr["fade"]}; domes {spans}); {len(moved)} rim targets moved '
                    f'toward their corners, {np.mean(moved) if moved else 0.0:.2f} mm on average '
                    f'(max {max(moved) if moved else 0.0:.2f})')
        cg.meta['creases'][-1]['moved'] = moved
    # X4d, the lead's call 6: the crusher's small blunt teeth (the dactyl) and the fixed finger's bead row, STROKES for
    # X6 (STROKES crusher_teeth) along each finger's band middle (its occlusal column after the warp), at their pitch by
    # arc from the gape toward the tip, the domes' spans left free, leaning tipward
    tt = STROKES['crusher_teeth']
    for part, nm, tipward in ((('propodus', 'cheliped_propodus_L', d), ('dactyl', 'cheliped_dactyl_L', unit(fr['dd'])))
                              if claw is True else ()):
        cg = out[nm]
        spec_ = tt[part]
        ids = cg.meta['ring_ids']
        taus = np.asarray(cg.meta['taus'])
        k_occ = int(round(FEAT['band'][part]['centre'] / 360.0 * cg.K)) % cg.K
        s_g = float(np.asarray(info['claws']['crusher']['polys']['gape'])[0])
        js = [j for j in range(len(ids)) if 1.0 <= taus[j] <= 2.0]
        Pc = np.array([cg.V[ids[j, k_occ]] for j in js])
        sc_ = s_of(Pc)
        keep_ = (sc_ >= s_g) & chitin_mask(cg, Pc)     # (not on the joint's membrane)
        sock = info['claws']['crusher'].get('socket')
        if part == 'dactyl' and sock is not None:       # (X4e: none on the HEEL, which slides past the gape's bottom G
            sa_ = sock['angles']                        # 0.3 mm clear: from its front on)
            keep_ &= hinge_angle(Pc, sock)[0] > sa_['phi_front'] + (info['claws']['crusher']['want'] - sa_['open_c11'])
        Pc, sc_ = Pc[keep_], sc_[keep_]
        if len(Pc) < 2:
            continue
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))])
        free = [(dm['s'] - 0.5 * dm['width'] - tt['gap'], dm['s'] + 0.5 * dm['width'] + tt['gap'])
                for dm in FEAT['domes'] if dm['shell'] == part]
        n_t = 0
        for a_ in np.arange(0.5 * spec_['pitch'], arc[-1] - tt['tip_clear'], spec_['pitch']):
            P0 = np.array([np.interp(a_, arc, Pc[:, c3]) for c3 in range(3)])
            s0 = float(s_of(P0))
            if any(lo <= s0 <= hi for lo, hi in free):
                continue
            n_t += 1
            rec = stroke_record(cg.meta.get('field'), P0, tipward, f'{spec_["kind"]}_{part}_{n_t}', spec_['kind'],
                                spec_['d'], spec_['height'], tt['lean'], tt['source'] + f' (s {s0:.1f})')
            cg.meta.setdefault('strokes', []).append(rec)
        rows.append(f'{nm}: {n_t} {spec_["kind"]} STROKES for X6 (d {spec_["d"]}, {spec_["height"]} mm high, pitch '
                    f'{spec_["pitch"]} mm) on the band from the gape toward the tip, the domes {free} left free')
    # X4c, the lead's call 2: the claw margins' tubercles are STROKES for X6 (STROKES claw): each c11 point's nearest
    # place on the clay (the build field: the margin's mid-thickness), the clay's normal there, the lean distally
    # A0 (x6fix_x7): the cutter's own row too (STROKES claw_cutter), on its own frame (fr is the cutter's on its build)
    st = STROKES['claw'] if kind == 'crusher' else STROKES['claw_cutter']
    for part, nm, dist in ((('propodus', f'cheliped_propodus{tg}_L', d), ('dactyl', f'cheliped_dactyl{tg}_L',
                                                                          unit(fr['dd'])))
                           if claw is True or (claw == 'creases' and kind == 'cutter') else ()):
        cg = out[nm]
        fld = cg.meta.get('field')
        for i_, (s_, m_) in enumerate(st[part]):
            P0 = W + s_ * d + m_ * n
            rec = stroke_record(fld, P0, dist, f'tubercle_{part}_{i_ + 1}', st['kind'], st['d'], st['height'],
                                st['lean'], st['source'] + f' (s {s_:.1f}, m {m_:.1f})')
            cg.meta.setdefault('strokes', []).append(rec)
            rows.append(f'{rec["name"]} on {nm}: a STROKE for X6 ({st["kind"]}, d {st["d"]:.1f}, {st["height"]:.1f} mm '
                        f'high), {rec["moved"]:.1f} mm from c11\'s point onto the clay')
    # the carpus's and the merus's knobs and denticles: STROKES too (STROKES segment), placed as FEAT segment_spines
    for nm, specs in STROKES['segment'].items():
        cg = out[nm]
        a0, axis = cg.meta['a0'], unit(cg.meta['axis'])
        u_end = float(np.linalg.norm(cg.meta['b'] - a0))
        if 'cheliped_wrist_L' in cg.meta.get('record_ids', {}):
            u_end = float((cg.V[np.asarray(cg.meta['record_ids']['cheliped_wrist_L'])].mean(0) - a0) @ axis)
        for fs in specs:
            d1, d2, ang = fs['dir']
            dv = unit(math.cos(math.radians(ang)) * _dir_of(d1, axis) + math.sin(math.radians(ang)) * _dir_of(d2, axis))
            c_ = a0 + fs['u'] * u_end * axis
            t_ = float(cg.meta['field'].cast(c_[None, :], dv[None, :], 40.0)[0])
            rec = stroke_record(cg.meta['field'], c_ + t_ * dv, axis, fs['name'], fs['kind'], fs['d'], fs['height'],
                                fs['lean'], STROKES['segment_source'][nm] + f' (u {fs["u"]:.2f}, {d1}->{d2} {ang:.0f} deg)')
            cg.meta.setdefault('strokes', []).append(rec)
            rows.append(f'{fs["name"]} on {nm}: a STROKE for X6 ({fs["kind"]}, d {fs["d"]:.1f}, {fs["height"]:.1f} mm high)')
    # the carpus's and the merus's SPINES, the segment features the cage keeps (X4c)
    for nm, specs in FEAT['segment_spines'].items():
        cg = out[nm]
        a0, b, axis = cg.meta['a0'], cg.meta['b'], unit(cg.meta['axis'])
        L_ = float(np.linalg.norm(b - a0))
        # (the carpus's chitin ends at the wrist ring: u along a0 .. the wrist)
        u_end = L_
        if 'cheliped_wrist_L' in cg.meta.get('record_ids', {}):
            u_end = float((cg.V[np.asarray(cg.meta['record_ids']['cheliped_wrist_L'])].mean(0) - a0) @ axis)
        for fs in specs:
            d1, d2, ang = fs['dir']
            # the face at (u, the direction), then the knob's patch round it (spine_patch: the same for spine_feet)
            jf, kf, j0, nj_, k0, na_ = spine_patch(cg, fs, a0, axis, u_end)
            fp_ = free_patch(cg, j0, nj_, k0, na_)
            if fp_ is None:
                rows.append(f'{fs["name"]} on {nm}: SKIPPED (no free patch beside its neighbours)')
                continue
            j0, G, got = fp_
            prof = FEAT['profile']['spine']
            f = extrude_patch(cg, G, got, na_, nj_, prof, fs['height'], fs['kind'], fs['name'], lean_dir=axis,
                              lean_deg=fs['lean'], d=fs['d'], field=cg.meta.get('field'), tip=fs.get('tip'))
            rows.append(f'{fs["name"]} on {nm}: {na_} x {nj_} faces from ring {j0} column {k0} (u {fs["u"]:.2f}, '
                        f'{d1}->{d2} {ang:.0f} deg), {fs["height"]:.1f} mm, foot r {f["r_base"]:.2f}')
    # X4e (FEAT condyle): the two condyles on the hinge axis, each on the patch whose own CENTRE lies nearest where the axis
    # leaves the clay (X4e: face-centred patches collided and the second moved 8.7 mm, x04 _x4e3; vertex-centred ones sat
    # 3.8 mm off, in the fan's path). X4f: on BOTH claws (the cutter's build too), the axis leaving the cup's DISK
    # (decapod_parts SOCKET cup), n04's ball sized by the socket (condyle_d, condyle_h: x2.n04.condyle_r of |G - A|),
    # CENTRED on the axis's exit (a ball off the pivot reads wrong; the probe's first try sat 2.4-3.1 mm off on the patch
    # centre nearest).
    # X4f, 2nd session: n04's ball goes into the CAGE only where a centred loop holds it WHOLE, else it is a STROKE for X6
    # at n04's size, anchored where the hinge axis leaves the cup disk's face, its axis the hinge's (never a shrunk dome).
    # A cage dome STANDS ON THE HINGE AXIS (a solid of revolution about the hinge, as the joint is): its foot circle in the
    # plane normal to the axis through the exit, its rise along the axis (extrude_patch normal); a patch holds it when
    # that circle plus FEAT condyle_band mm lies inside the patch's LOOP projected onto that plane, no more eccentric
    # about the exit than FEAT condyle_ecc (its farthest vertex over its clearance), crossing no crease and holding none
    # of the rim's membrane / opening quads; the least n x n (n 2..5), then the least eccentric; the second condyle the
    # first's mirror. On this cage both claws' are STROKES: the propodus's faces round the exit are ~5 mm (the crusher)
    # and ~3.5 mm (the cutter), the ball at the cup's edge, and no centred loop holds it (scratch x4f probes a-i,
    # views/probe/grid_*.png): the first session's dome leaned ~20 deg with its patch's mean normal and its foot draped
    # over the disk's rim (53 / 50 limit folds); upright on that patch 227 / 164; on the widest loop (3 x 3, 4.52 mm
    # round the exit, its far corner 13.0 mm off) a 7.0 mm ball read min angle 13.8 / aspect 6.5 in its band; on the
    # most centred (2 x 2) a 4.1 mm ball 13.4 / 4.8; the cutter's at most 1.35 mm, its limit folded over itself.
    # A finer propodus grid round the hinge would let the ball into the cage (the report)
    sock = info['claws'][kind].get('socket') if claw in (True, 'creases') else None
    if sock is not None:
        cg = out[f'cheliped_propodus{tg}_L']
        cd = dict(d=float(sock['condyle_d']), height=float(sock['condyle_h']))
        ids = cg.meta['ring_ids']
        taus = np.asarray(cg.meta['taus'])
        ok_ = np.nonzero((taus >= 1.0) & (taus <= 2.0))[0]
        K_ = cg.K
        band_ = FEAT['condyle_band']
        sharp_ = {frozenset(int(v) for v in k_) for k_ in cg.sharp}

        def loop_of(G, np_):
            return ([G[(a, 0)] for a in range(np_ + 1)] + [G[(np_, b)] for b in range(1, np_ + 1)]
                    + [G[(a, np_)] for a in range(np_ - 1, -1, -1)] + [G[(0, b)] for b in range(np_ - 1, 0, -1)])

        def clearance(G, np_, Pc, ax_):
            """the least distance (mm) from the axis's exit to the patch's loop projected onto the plane normal to the
            axis (negative: the exit outside it), the loop's centroid's offset from the exit in that plane, and the
            loop's farthest vertex from the exit (its eccentricity about the exit: the foot band's long spokes)"""
            e1_ = unit(np.cross(ax_, [0.0, 0.0, 1.0]) if abs(ax_[2]) < 0.9 else np.cross(ax_, [1.0, 0.0, 0.0]))
            e2_ = np.cross(ax_, e1_)
            D_ = cg.V[loop_of(G, np_)] - Pc[None, :]
            P2 = np.column_stack([D_ @ e1_, D_ @ e2_])
            A2, B2 = P2, np.roll(P2, -1, axis=0)
            AB = B2 - A2
            tt_ = np.clip(-(A2 * AB).sum(1) / np.maximum((AB * AB).sum(1), 1e-12), 0.0, 1.0)
            dist_ = float(np.linalg.norm(A2 + tt_[:, None] * AB, axis=1).min())
            wind_ = float(np.sum(np.arctan2(A2[:, 0] * B2[:, 1] - A2[:, 1] * B2[:, 0], (A2 * B2).sum(1))))
            return ((dist_ if abs(wind_) > np.pi else -dist_), float(np.linalg.norm(P2.mean(0))),
                    float(np.linalg.norm(P2, axis=1).max()))

        def usable(G, got, np_):
            """no crease on the patch's inner edges (removed by the extrusion), none of the rim's membrane / opening"""
            if np.isin(np.asarray(cg.meta['region'])[got], ('membrane', 'opening')).any():
                return False
            inner_e = ([(G[(a, b)], G[(a + 1, b)]) for a in range(np_) for b in range(1, np_)]
                       + [(G[(a, b)], G[(a, b + 1)]) for a in range(1, np_) for b in range(np_)])
            return not any(frozenset(e_) in sharp_ for e_ in inner_e)
        pick1 = None
        for i_, Pc in enumerate(sock['condyles']):
            Pc = np.asarray(Pc, np.float64)
            ax_ = np.asarray(sock['t'], np.float64) * (1.0 if float((Pc - sock['C3']) @ sock['t']) > 0.0 else -1.0)
            rf = 0.5 * cd['d']
            cands = []
            tries = [(pick1[0], pick1[1], (K_ - pick1[2] - pick1[0]) % K_)] if pick1 not in (None, 'stroke') else []
            if pick1 is None:
                for np_ in (2, 3, 4, 5):
                    for j_ in range(int(ok_.min()), int(ok_.max()) - np_ + 1):
                        cen_ = np.stack([cg.V[ids[j_:j_ + np_ + 1][:, (np.arange(np_ + 1) + k_) % K_].ravel()].mean(0)
                                         for k_ in range(K_)])
                        tries += [(np_, j_, int(k_)) for k_ in np.nonzero(np.linalg.norm(cen_ - Pc[None, :], axis=1)
                                                                         < 3.0 * np_ + rf)[0]]
            for np_, j_, k_ in tries:
                try:
                    G, got = tube_patch(cg, j_, np_, k_, np_)
                except ValueError:                      # (a quad taken by another feature)
                    continue
                if not usable(G, got, np_):
                    continue
                cl_, off_, far_ = clearance(G, np_, Pc, ax_)
                if cl_ >= rf + band_ and far_ / cl_ <= FEAT['condyle_ecc']:
                    cands.append((np_, j_, k_, G, got, off_, cl_, far_))
            name_ = f'hinge_condyle_{i_ + 1}'
            if not cands:                               # (no centred loop holds the whole ball: X6's stroke carries it)
                pick1 = 'stroke'
                rec = stroke_record(cg.meta.get('field'), Pc, ax_, name_, 'knob', cd['d'], cd['height'], 0.0,
                                    f'n04\'s ball in its cup (x2.n04.condyle_r of this claw\'s |G - A|, condyle_h of it '
                                    f'high), on the hinge axis where it leaves the cup disk\'s face: X4f, no loop of the '
                                    f'{kind}\'s cage round the exit holds it whole (decapod_cage crusher_features)')
                cg.meta.setdefault('strokes', []).append(rec)
                rows.append(f'{name_} on {cg.name}: a STROKE for X6 (knob, n04\'s ball d {cd["d"]:.2f}, {cd["height"]:.2f} '
                            f'mm high, along the hinge axis; no centred loop of the cage round the exit holds it whole), '
                            f'{rec["moved"]:.2f} mm onto the clay')
                continue
            n_min = min(c_[0] for c_ in cands)
            np_, j0, k0, G, got, off_, cl_, far_ = min((c_ for c_ in cands if c_[0] == n_min),
                                                       key=lambda c_: c_[7] / c_[6])
            if pick1 is None:
                pick1 = (np_, j0, k0)
            f = extrude_patch(cg, G, got, np_, np_, FEAT['profile']['condyle'], cd['height'], 'condyle', name_,
                              d=cd['d'], field=cg.meta.get('field'), center=Pc, normal=ax_)
            rows.append(f'{name_} on {cg.name}: {np_} x {np_} faces from ring {j0} column {k0}, n04\'s ball d {cd["d"]:.2f} '
                        f'mm, {cd["height"]:.2f} mm high along the hinge axis, foot r {f["r_base"]:.2f} on the plane '
                        f'normal to it; its loop {cl_:.2f} mm round the exit, its centre {off_:.2f} mm off it, its farthest '
                        f'vertex {far_:.2f} mm')
    for nm in out:
        cg = out[nm]
        if cg.meta.get('features'):
            cg.orient()
    for r_ in rows:
        log('[decapod_cage] feature: ' + r_)
    return rows


def feature_masks(cg):
    """x04's view of a cage's features: (fq the feature quads, near the quads sharing a vertex with a feature's base
    loop, which: per quad its feature's index or -1, foot: the feature quads lying on the clay round its foot)"""
    Q = np.asarray(cg.Q, int)
    reg = np.asarray(cg.meta['region'])
    fq = np.isin(reg, FEATURE_REGIONS)
    which = np.full(len(Q), -1)
    foot = np.zeros(len(Q), bool)
    feats = cg.meta.get('features', [])
    if not feats:
        return fq, np.zeros(len(Q), bool), which, foot
    qkey = {frozenset(int(v) for v in q): i for i, q in enumerate(Q)}
    loops = set()
    for i, f in enumerate(feats):
        for i_q, q in enumerate(f['quads']):
            which[qkey[frozenset(q)]] = i
            foot[qkey[frozenset(q)]] = i_q < f.get('n_foot', 0)
        loops |= set(f['loop'])
    near = (~fq) & np.array([bool(set(int(v) for v in q) & loops) for q in Q])
    return fq, near, which, foot


def feature_outward(cg, P, which, foot=None):
    """the outward sense of the features at points P (per point its feature's index): on the foot (on the clay) the
    clay's own normal (X4f: the cage's build field; the patch's outward normal without one); on the raised part away
    from a point 0.6 of the foot's radius under the base centre, along the feature's axis (a dome's, a knob's, a
    spine's). (X4f, 2nd session: a foot's faces lie on the clay by construction, and the patch's single normal is their
    outward sense only on a flat patch: the hinge's condyles sit at the cup disk's edge, where their foot faces follow
    the clay over the rim, 90 deg from it; x04 gate 2 counted 36 / 34 such faces as folds that face the clay's way,
    beside 17 / 16 real ones, scratch x4f check_fold_ref. A fold faces against the clay: that is what is counted)"""
    P = np.asarray(P, np.float64)
    out = np.zeros_like(P)
    foot = np.zeros(len(P), bool) if foot is None else np.asarray(foot, bool)
    field = cg.meta.get('field')
    for i, f in enumerate(cg.meta.get('features', [])):
        m = (np.asarray(which) == i) & ~foot
        if m.any():
            o = f['c0'] - 0.6 * f['r_base'] * f['axis']
            v = P[m] - o
            out[m] = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
        mf = (np.asarray(which) == i) & foot
        if mf.any():
            out[mf] = field.normals(P[mf]) if field is not None else f['normal'][None, :]
    return out


def crease_radii(cg, V0, levels=None):
    """X4b, x04 gate 8 (plan §5.3's crease-radius gate): the limit's apex radius along each crease of cg: every second
    vertex of each chain where it is at the chain's top sharpness (its faded ends excluded; a short run: its sharpest
    vertex), the limit at `levels` (FEAT crease levels), B4's rule (stag_beetle_cage.edge_radius: a circle over
    +-half_arc of arc at the sharpest turn within `near`), half_arc / near scaled from the beetle's 0.06 / 0.4 mm (a
    0.05 mm class) to §5.3's 0.2-0.4 mm cutting edge. Returns a list of (r, turn deg, point, the sharpness there)"""
    from ..species import stag_beetle_cage as SBC
    cr = FEAT['crease']
    if not cg.sharp:
        return []
    lim, _ = limit_mesh(cg, V0, levels=levels or cr['levels'])
    # the chains: the creased edges' graph, walked from its ends
    adj = {}
    for (a, b), s_ in cg.sharp.items():
        adj.setdefault(a, []).append((b, s_))
        adj.setdefault(b, []).append((a, s_))
    seen, out = set(), []
    for v0 in [v for v, nb in adj.items() if len(nb) == 1]:
        if v0 in seen:
            continue
        chain = [v0]
        seen.add(v0)
        while True:
            nxt = [b for b, _ in adj[chain[-1]] if b not in seen]
            if not nxt:
                break
            chain.append(nxt[0])
            seen.add(nxt[0])
        # each interior vertex's sharpness: the lesser of its two edges'; sampled where it is the chain's own top
        # (every second such vertex), or at the chain's sharpest vertex when a short run has no two full edges
        sv = [(i, min(cg.sharp[(min(chain[i - 1], chain[i]), max(chain[i - 1], chain[i]))],
                      cg.sharp[(min(chain[i], chain[i + 1]), max(chain[i], chain[i + 1]))]))
              for i in range(1, len(chain) - 1)]
        if not sv:
            continue
        top = max(s_ for _, s_ in sv)
        # every second vertex past the fade (FEAT crease fade's edges at either end; the sharpness varies along a rim
        # with its spacing), or a short run's sharpest; along a dome's base too (its foot stands in from the rim).
        # (X4b check: vertex i lies between edges i - 1 and i, and edges 0 .. nf_ - 1 carry the fade, so the first
        # vertex with both edges at full sharpness is nf_ + 1; range(nf_, ...) sampled vertex nf_, at 0.75 s: the
        # 0.43 / 0.66 mm readings out of the class were that faded vertex on every rim)
        nf_ = len(cr['fade'])
        pick = list(range(nf_ + 1, len(chain) - 1 - nf_, 2)) or [i for i, s_ in sv if s_ >= top - 1e-9][:1]
        for i in pick:
            a, v, b = chain[i - 1], chain[i], chain[i + 1]
            p = cg.V[v]                                 # (a low vertex lies on the limit: the fit's targets)
            t = unit(cg.V[b] - cg.V[a])
            r, turn, apex = SBC.edge_radius(lim, p, t, half_arc=cr['half_arc'], near=cr['near'])
            out.append((float(r), float(turn), apex, float(top)))
    return out


# ============================================================================================ the cheliped
CHELIPED = ('coxa', 'basis', 'merus', 'carpus')
JOINT_PT = dict(coxa='M', basis='B', merus='I', carpus='K')      # decapod.solve_cheliped's points: each segment's joint


def axis_exit(parent, origin, axis, reach=25.0):
    """X3's rule (sleeve_cage): X0 where the line origin + t axis first leaves `parent` going distally (t up to `reach`
    mm), or None"""
    ts = np.arange(-2.0, reach, 0.01)
    fpar = parent.eval(origin[None, :] + ts[:, None] * axis[None, :])
    io = np.nonzero((fpar[:-1] < 0.0) & (fpar[1:] >= 0.0))[0]
    if not len(io):
        return None
    i = int(io[0])
    return origin + (ts[i] - fpar[i] * (ts[i + 1] - ts[i]) / (fpar[i + 1] - fpar[i])) * axis


def sleeve_depths(child, X0, axis):
    """X3's sleeve rule at X0 (sleeve_cage): (d, d_in, t_back, the child's mean radius there)"""
    r0 = np.linalg.norm(section_ring(child, X0, axis, n=48) - X0[None, :], axis=1)
    d = float(np.clip(SLV['step'] * np.median(r0), SLV['step_min'], SLV['step_max']))
    t_back = float(child.cast(X0[None, :], -axis[None, :], 30.0)[0])
    return d, (min(d, 0.5 * t_back) if np.isfinite(t_back) else d), t_back, float(np.mean(r0))


def record_angles(rec):
    """a ring record's own angles (rad, 0 .. 2 pi, vertex order) when it is SAG-SPACED (X3), else None"""
    if rec.get('sag', {}).get('spacing') != 'sag':
        return None
    return np.mod(np.radians(np.asarray(rec['angles_deg'], np.float64)), 2.0 * np.pi)


def hinge_angle(P, sock):
    """X4e: points P (any (..., 3)) as angles (deg) about the crusher's hinge axis in the fingers' plane, from the claw
    axis d toward n (decapod_parts.socket_parts' frame), and their radii from the axis"""
    Q = np.asarray(P, np.float64) - sock['C3']
    s_, m_ = Q @ sock['d'], Q @ sock['n']
    return np.degrees(np.arctan2(m_, s_)), np.hypot(s_, m_)


def notch_opening(cg, sock, field, dac_field, mo, log=print, tol=None, ring=3.0, cover=0.05):
    """X4e / X4f (decapod_parts SOCKET, the lead's call 2 on the X4d check): the propodus's RIM, the notch the dactyl's
    fan slides through (X4f: the gape ray, the top ray and the cup's arc round the condyle, decapod_parts notch_piece), as
    quads: a centre within tol mm of a piece's surface in the fingers' plane, the clay there facing the dactyl (the gape
    ray's toward + phi, the top ray's toward - phi, the cup's outward). Such a quad is the OPENING where the dactyl hides
    it at every pose of the claw (centre and corners MOTION margin inside its build field), else the CRESCENT (region
    'membrane', rigid on the propodus) while its centre lies under `ring` mm outside the dactyl's trace (decapod_parts
    rim_f: the rim's ring, r57282_7's dark crescent and top slit: the quads are wider than the ring, X5 / X9's mask reads
    rim_f), else it keeps its chitin. Relabels cg.meta['region'] in place; returns (opening, crescent) counts. X4f, 3rd
    session: tol None = the socket's bulge + 0.6 mm, at least 1.2 (the rims' clay stands up to `bulge` past each ray:
    with decapod_parts THE BLENDS, col_k 5, the notch faces stood 1.3-1.6 mm off the rays and kept their chitin, the
    crusher's 121 points 7.2 mm inside the dactyl's tongue at the bind in x04 gate 9). X4f, 4th session: a rim quad the
    dactyl's clay COVERS at some pose (its centre or a corner more than `cover` mm inside it) but not at every pose is the
    crescent too, whatever rim_f says: rim_f's trace on a ray is its arm's T(r), the joint's half-thickness HELD under the
    propodus's room, and where the dactyl's body past its band's cap crosses the notch face (the cutter's gape side, r 5-6
    mm, |t| 3.9-5.5) the real trace is wider; those quads kept their chitin and x04 gate 9 read the propodus 1.06 mm inside
    the dactyl at the bind (scratch x4f probe_g23 t3, probe_cutfill: the surface the base covers closed and leaves open is
    the crescent by the photos' reading, n04 / r57282_7)"""
    if tol is None:
        tol = max(1.2, float(sock['bulge']) + 0.6)
    V, Q = cg.V, np.asarray(cg.Q, int)
    cen = V[Q].mean(1)
    ph, r = hinge_angle(cen, sock)
    a_ = np.radians(ph)
    e_phi = -np.sin(a_)[:, None] * sock['d'][None, :] + np.cos(a_)[:, None] * sock['n'][None, :]   # (+ phi)
    e_r = np.cos(a_)[:, None] * sock['d'][None, :] + np.sin(a_)[:, None] * sock['n'][None, :]
    k_, dist = DPP.notch_piece(r, ph, sock)
    toward = np.where((k_ == 0)[:, None], e_phi, np.where((k_ == 1)[:, None], -e_phi, e_r))
    facing = (field.normals(cen) * toward).sum(1) > 0.4
    # (4th session: the CUP piece's face reaches the hub's surface: THE BLENDS carry it to the bearing, `bear`, past the
    # disk's r_cup that notch_piece measures from: the cutter's 4.26 on a 1.66 cup, its hub face's quads 833 / 862 at r
    # 3.99, covered by the dactyl at the bind, 2.34 mm from the arc against tol 2.2 (scratch x4f diag_bind); the crusher's
    # 6.57 on 5.07: its tol unchanged. In that wider band only the dactyl's cover makes a crescent: on the cup piece
    # rim_f is |t| less the dactyl's half-thickness, which would take the hub's whole face)
    tol_c = max(tol, float(sock.get('bear', sock['r_cup'])) - float(sock['r_cup']) + 0.6)
    face_x = (k_ == 2) & (dist >= tol) & (dist < tol_c) & facing
    face = ((dist < tol) & facing) | face_x
    hid = np.zeros(len(Q), bool)
    cov = np.zeros(len(Q), bool)
    if face.any():
        pts = np.concatenate([cen[face][:, None, :], V[Q[face]]], axis=1)
        hid[face] = posed_inside(dac_field, pts, mo, False, MOTION['margin']).all(axis=1)
        cov[face] = posed_inside_any(dac_field, pts, mo, False, cover).any(axis=1)
    rf = DPP.rim_f(cen, sock)
    ringq = face & ~hid & (((rf < ring) & ~face_x) | cov)
    reg = np.asarray(cg.meta['region']).astype(object)
    reg[face & hid] = 'opening'
    reg[ringq] = 'membrane'
    cg.meta['region'] = reg.astype(str)
    per = ', '.join(f'{nm_} {int((face & (k_ == i_)).sum())} ({int((face & hid & (k_ == i_)).sum())} opening, '
                    f'{int((ringq & (k_ == i_)).sum())} ring)' for i_, nm_ in enumerate(('gape ray', 'top ray', 'cup')))
    log(f'[decapod_cage] {cg.name}: its rim (X4f, the two-armed notch: {per}): {int((face & hid).sum())} quads the OPENING '
        f'(inside the dactyl at every pose), {int(ringq.sum())} the crescent (the rims\' ring; '
        f'{int((ringq & ~((rf < ring) & ~face_x)).sum())} of them by the dactyl\'s cover alone, past rim_f\'s ring or on the '
        f'hub past the disk), '
        f'{int((face & ~hid & ~ringq).sum())} keep their chitin')
    return int((face & hid).sum()), int(ringq.sum())


def dactyl_edge(cg, sock, want, log=print):
    """X4e (decapod_parts SOCKET wedge, the lead's call 2 on the X4d check, 'only the narrow crescent the photos show'):
    the crusher dactyl's fan behind its HARD EDGE (hard_edge_f < 0) is the joint's membrane, rigid on the dactyl: under the
    rim at every opening short of the wedge, past it the dark crescent, zero at the hinge and widest at the gape. Quads
    by their centres (region 'membrane'; X5 / X9's mask reads hard_edge_f). Its proximal cap's quads inside the bearing
    are 'lump': on the axle a corner shows at the widest openings (0.03 mm, x04 _x4e4), chitin that keeps its texels, as
    the propodus's knob. Returns the count"""
    Q = np.asarray(cg.Q, int)
    cen = cg.V[Q].mean(1)
    reg = np.asarray(cg.meta['region']).astype(object)
    b_ = (DPP.hard_edge_f(cen, sock, want) < 0.0) & (reg == 'chitin')
    reg[b_] = 'membrane'
    q_ = cg.V[Q] - sock['C3'][None, None, :]
    reg[(reg == 'cap') & (np.hypot(q_ @ sock['d'], q_ @ sock['n']).min(axis=1) < sock['r_cup'] - 2.0)] = 'lump'
    #   (X4f, 3rd session: the disk's radius, as X4e had it; the socket's `bear` is now the hub's measured reach)
    cg.meta['region'] = reg.astype(str)
    log(f'[decapod_cage] {cg.name}: {int(b_.sum())} quads behind its hard edge (X4e: the fan\'s membrane, under the rim until '
        f'{sock["angles"]["open_lim"] - sock["wedge"]:.0f} deg open)')
    return int(b_.sum())


def cheliped_cages(parts, info, chain, sc, seams, kind='crusher', log=print, spec=None, carpus_margin=None):
    """the LEFT cheliped carrying claw `kind` (the crusher at the bind; the cutter's claw is built on the left, then
    mirrored): its four proximal shells, the claw's propodus and dactyl, its five sleeves, as {name: Cage}. X3's
    records: cheliped_coxa_L (the thorax-coxa sleeve's ring 0), cheliped_ischium_L (a loop of the basi-ischium's own
    cage, uncreased), cheliped_carpus_L (the merus-carpus sleeve's ring 0), cheliped_wrist_L (the carpus's last
    chitin ring; the membrane past it in the same cage); the sag-spaced ones lay their own angles (and K) on the cages
    that carry or meet them (X4b). X4b (module docstring): the motion ranges (joint_motions), each condyle trimmed
    (cut_depth: CutField), the ends hidden over the range capped coarsely, the dactyl's planes started on its base face.
    Each Cage's meta: region per quad, ring ids, record_ids ({name: ring vertex ids}), spine, the joint, the build
    field, `trim` (the cut and its scan), `cap_c` (each end's hand-over); the returned dict's '_motions' and
    '_relations' entries (not cages) carry the motions and, per shell, the (field, motion, moves) relations for
    range_hidden.
    carpus_margin (x6fix_x7, 11-11): another build's wrist margin (a joint_margin dict) that the carpus's wrist is
    UNIONED with (union_margin): x04 hands the CRUSHER's build's to the cutter's. Since A0 BOTH carpi are one clay whose
    membrane crescent the crusher's sweep cut (decapod_parts ARM carpus `lips`), and the wrists' motions are the same
    (o, z, range). On its own sweep the cutter's ramp stood 0.19-0.54 on the membrane where its heel, 6.8 mm lateral
    of the hinge on the flat fingers' plane, leaves the carpus, and its proximal cap showed from +20.9 deg (x04 _a0f
    gate 11); the crusher's rides 0.92-1.00 there (the cap stays 1.37 mm inside at +43.4) but alone leaves chitin in
    the cutter's heel (x04 _a0g gate 9); the union does neither (scratch x6fix_x7 claw/probe_cutter_cap_skins.py)"""
    if spec is None:
        from ..species import lobster as LB
        spec = LB.SPEC
    R = seams['rings']
    pts = chain['cheliped']['pts']
    out = {}
    if kind == 'crusher':
        pn, dn = 'cheliped_propodus_L', 'cheliped_dactyl_L'
    else:                                               # the cutter's own programs evaluated on the left
        pn, dn = 'cheliped_propodus_cutter_onL', 'cheliped_dactyl_cutter_onL'
        for src, dst in (('cheliped_propodus_R', pn), ('cheliped_dactyl_R', dn)):
            p = parts[src]
            parts[dst] = DPP.Part(dst, p.region, p.joint[:-2] + '_L', p.prog, p.descs, parent=None)
    F = {n: Field(parts, [n], sc) for n in [f'cheliped_{s}_L' for s in CHELIPED] + ['ventral_thorax', pn, dn]}
    near = ['ventral_thorax', 'carapace'] + [f'cheliped_{s}_L' for s in CHELIPED] + [pn, dn]
    HID = {n: Field(parts, [o for o in near if o != n], sc) for n in near[2:]}    # x04's hidden: inside another shell
    tag = '' if kind == 'crusher' else '_cutter'
    MO = joint_motions(spec, chain, kind)
    JN = [f'cheliped_{s}_L' for s in CHELIPED] + ['cheliped_propodus_L', 'cheliped_dactyl_L']    # the joints, in order
    SH = [f'cheliped_{s}_L' for s in CHELIPED] + [pn, dn]                                    # their shells
    FIX = {j: Field(parts, ['ventral_thorax', 'carapace'] + SH[:i], sc) for i, j in enumerate(JN)}   # unmoved by j
    fr = claw_frames(info['claws'][kind])
    def lay_membrane(cg, mg, parent, child, partner_shell):
        """X4d (joint_margin): the faces past the margin become the joint's membrane; the margin is one of the cage's
        skins (skin_cages) between the joint's parent and child (x04 poses it by its child joint)"""
        mg.update(parent=parent, child=child, shell_name=partner_shell)
        past = margin_f(mg, cg.V[np.asarray(cg.Q, int)].mean(1)) > 0.0
        cg.meta['region'] = np.where(past, 'membrane', cg.meta['region'])
        cg.meta.setdefault('margins', []).append(mg)
    # ---- pass 1: each child's BUILD field (the clay, a lengthened condyle, X4b's cut) and its spine's start
    BLD = {}
    for i, seg in enumerate(CHELIPED):
        nm = f'cheliped_{seg}_L'
        a0, b, _, rho = tube_nodes(parts[nm])
        axis = unit(b - a0)
        par_nm = 'ventral_thorax' if seg == 'coxa' else SH[i - 1]
        half0 = np.asarray(parts[nm].descs[0]['scale'], np.float64)[0] + rho
        field, a0, cond = condyle(nm, F[nm], F[par_nm], a0, axis, rho, half0)
        cond['parent'] = par_nm
        X0 = axis_exit(F[par_nm], np.asarray(pts[JOINT_PT[seg]], np.float64), axis)
        d, d_in, t_back, rbar = sleeve_depths(field, X0, axis)
        t_min = max(d_in + MOTION['keep'], CONDYLE['depth'] * rbar)
        t_cut, ci = cut_depth(field, FIX[nm], MO[nm], X0, axis, t_back, t_min)
        if t_cut is not None:
            field = CutField(field, X0 - t_cut * axis, axis, CAGE['cut_k'])
            a0 = X0 - (t_cut - CAGE['cut_in'] * CAGE['cut_k']) * axis
        BLD[nm] = dict(field=field, a0=a0, b=b, axis=axis, rho=rho, cond=cond, par=par_nm,
                       trim=dict(ci, t=t_cut, X0=X0, axis=axis, d_in=d_in, rbar=rbar))
    # the propodus's base knob in the carpus: X0 the wrist W, the depth along -d, each section centred on the plan's
    # middle (decapod_parts.interval_at) through the claw's thickness
    pol = np.asarray(fr['propodus'], np.float64)

    def p_centre(t, W=fr['W'], d=fr['d'], n=fr['n']):
        iv = DPP.interval_at(pol, float(np.clip(-t, pol[:, 0].min() + 1e-6, pol[:, 0].max() - 1e-6)))
        return W - t * d + 0.5 * (iv[0] + iv[1]) * n
    c0 = p_centre(0.0)
    tb_p = float(F[pn].cast(c0[None, :], -fr['d'][None, :], 30.0)[0])
    rb_p = float(np.mean(np.linalg.norm(section_ring(F[pn], c0, fr['d'], n=48) - c0[None, :], axis=1)))
    t_cut, ci = cut_depth(F[pn], FIX['cheliped_propodus_L'], MO['cheliped_propodus_L'], fr['W'], fr['d'], tb_p,
                          CONDYLE['depth'] * rb_p, centre_fn=p_centre)
    fp, s_min_p = F[pn], None
    if t_cut is not None:
        fp = CutField(F[pn], fr['W'] - t_cut * fr['d'], fr['d'], CAGE['cut_k'])
        s_min_p = -t_cut
    BLD[pn] = dict(field=fp, s_min=s_min_p, trim=dict(ci, t=t_cut, X0=fr['W'], axis=fr['d'], rbar=rb_p))
    # the dactyl: its own spine from its base face along the face's normal (the lead's call 1); its cut searched along
    # that normal (the base swings out of the propodus as the claw opens: no depth stays hidden at 40 deg)
    sp_d0 = dactyl_spine(fr)
    nb = fr['base_normal']
    Xd = axis_exit(F[pn], sp_d0.P[0] - 2.0 * nb, nb)
    # X4f (the X4e check: a 10 deg longer tongue left the base normal's line inside the propodus past X3's 25 mm, axis_exit
    # gave None and sleeve_depths failed on it): a longer reach, then where the dactyl's own axis leaves the propodus from
    # the hinge (X3's sleeve rule), each X0 taken only inside the dactyl's clay (its section there is the sleeve's r)
    for o_, ax_, rch in ((sp_d0.P[0] - 2.0 * nb, nb, 80.0), (fr['o_d'], unit(fr['dd']), 80.0)):
        if Xd is not None and F[dn].eval(Xd[None, :])[0] < 0.0:
            break
        Xd = axis_exit(F[pn], o_, ax_, reach=rch)
    if Xd is None or F[dn].eval(Xd[None, :])[0] >= 0.0:
        raise ValueError(f'cheliped_cages ({kind}): no point where the dactyl\'s base normal or axis leaves the propodus '
                         f'inside the dactyl (its condyle frame, gate 5)')
    dd_, ddin, tb_d, rb_d = sleeve_depths(F[dn], Xd, nb)
    t_cut, ci = cut_depth(F[dn], FIX['cheliped_dactyl_L'], MO['cheliped_dactyl_L'], Xd, nb, tb_d,
                          max(ddin + MOTION['keep'], CONDYLE['depth'] * rb_d))
    fd = F[dn] if t_cut is None else CutField(F[dn], Xd - t_cut * nb, nb, CAGE['cut_k'])
    BLD[dn] = dict(field=fd, trim=dict(ci, t=t_cut, X0=Xd, axis=nb, d_in=ddin, rbar=rb_d))

    def fix_union(i):
        """the shells joint JN[i] does not move, as built (the body's clay and the build fields proximal of it)"""
        return _Union([Field(parts, ['ventral_thorax', 'carapace'], sc)] + [BLD[x]['field'] for x in SH[:i]])

    def rel_of(i):
        """shell SH[i]'s relations (range_hidden): hidden by the unmoved shells over its own joint's range, or by its
        child's build field over the child's joint's range"""
        r_ = [(fix_union(i), MO[JN[i]], True)]
        if i + 1 < len(SH):
            r_.append((BLD[SH[i + 1]]['field'], MO[JN[i + 1]], False))
        return r_

    def hide_fns(i):
        """the two ends' hidden-over-the-range tests for shell SH[i] (ring_taus hide): the proximal end inside the
        unmoved shells over its own joint's range; the distal end inside its child's build field over the child's"""
        r_ = rel_of(i)
        f0 = (lambda P, F_=r_[0][0], m_=r_[0][1]: bool(posed_inside(F_, P, m_, True, 0.05).all()))
        f1 = None
        if len(r_) > 1:
            f1 = (lambda P, F_=r_[1][0], m_=r_[1][1]: bool(posed_inside(F_, P, m_, False, 0.05).all()))
        return f0, f1

    def sight_fn(i):
        """relax_ends' test for shell SH[i]: faces (m, 5, 3) hidden over the motion range"""
        return lambda pts, r_=rel_of(i): range_hidden_pts(pts, r_)
    # ---- pass 2: the proximal shells
    for i, seg in enumerate(CHELIPED):
        nm = f'cheliped_{seg}_L'
        B_ = BLD[nm]
        field, a0, b, axis, cond, par_nm = B_['field'], B_['a0'], B_['b'], B_['axis'], B_['cond'], B_['par']
        K = CAGE['K'][f'cheliped_{seg}']
        X0 = plane_frame(axis)[1]
        L_ = float(np.linalg.norm(b - a0))
        recs, regions, fixed, capr, th = {}, None, (), ('cap', 'cap'), None
        rec_names = {}
        if seg == 'coxa':                               # X4b: the columns on the coxa ring's own (sag-spaced) angles
            r = R['cheliped_coxa_L']
            th = record_angles(r)
            K = int(r['K']) if th is not None else K
            X0 = np.asarray(r['frame']['creature']['X'], np.float64) if th is not None else X0
        if seg == 'basis':                              # the autotomy suture: X3's weld ring, a loop of this cage
            r = R['cheliped_ischium_L']
            X0 = np.asarray(r['frame']['creature']['X'], np.float64)
            recs = {tuple(r['frame']['creature']['origin_mm']): np.asarray(r['verts_mm'], np.float64)}
            rec_names = {'cheliped_ischium_L': tuple(r['frame']['creature']['origin_mm'])}
            th = record_angles(r)                       # X4b: sag-spaced (K 20): the whole cage on its angles
            K = int(r['K'])
        if seg == 'carpus':                             # X4d (the lead's call 1): X3's wrist ring a LOOP of the carpus's
            r = R['cheliped_wrist_L']                   # chitin, which runs on its own clay to its true distal margin
            X0 = np.asarray(r['frame']['creature']['X'], np.float64)    # (joint_margin), a closed shell like the
            cw = np.asarray(r['frame']['creature']['origin_mm'], np.float64)    # others; past the margin plane its
            recs = {tuple(cw): np.asarray(r['verts_mm'], np.float64)}           # faces are the membrane (relabelled
            rec_names = {'cheliped_wrist_L': tuple(cw)}                         # below; X4c's inset collar is gone)
            # A0c (11-11): the cage on the wrist ring's OWN K and angles, as the basis on its weld ring. The table's
            # 24 was the ring's K while the carpus was a tube (r 9.7); on the fist X3 gives the ring 28 and more
            # (x04 _a0d stopped in capped_tube: the record's 28 points among rings of 24), sag-spaced
            th = record_angles(r)
            K = int(r['K'])
        hf = hide_fns(i)
        rmin_, th_fn_ = None, None
        if seg == 'carpus':                             # (its distal end the wrist membrane's: no trim by hiding)
            hf = (hf[0], None)
            rmin_ = CAGE['cap_rmin_carpus']             # A0: its rings stop short of both poles (CAGE's comment)
            if th is not None:                          # A0: ... and its columns fan out evenly toward the knee

                def th_fn_(tau, a_=2.0 * np.pi * np.arange(K) / K, b_=np.asarray(th, np.float64), f_=CAGE['carpus_fan']):
                    x = float(np.clip((tau - 1.0 - f_[0]) / (f_[1] - f_[0]), 0.0, 1.0))
                    return a_ + x * x * (3.0 - 2.0 * x) * (b_ - a_)
        cg = segment_cage(nm, 'chitin', field, a0, b, X0, K, records=recs, th=th, regions=regions, fixed_extra=fixed,
                          cap_regions=capr, hidden=HID[nm], hide=hf, hidden_fn=sight_fn(i), cap_rmin=rmin_,
                          th_fn=th_fn_)
        # X4d (the lead's calls 1 and 3, joint_margin): its DISTAL END against its child swept over the child's joint:
        # the coxa-basis and ischium-merus joints, the knee window (the merus), the wrist (the carpus, this claw's: the
        # right carpus is the same cage carrying the cutter's); the X3 ring it carries kept inside its chitin
        ch_nm, ch_j = SH[i + 1], JN[i + 1]
        rv = {'basis': 'cheliped_ischium_L', 'carpus': 'cheliped_wrist_L'}.get(seg)
        mg_ = joint_margin(field, cg.meta['spine'], 'distal', (ch_nm, BLD[ch_nm]['field'], MO[ch_j], True),
                           ring_verts=np.asarray(R[rv]['verts_mm'], np.float64) if rv else None, label=nm,
                           log=log, reach=0.7 if seg == 'merus' else 0.5,
                           keep_out=spine_feet(nm, field, a0, b, axis,
                                               wrist=np.asarray(R[rv]['verts_mm'], np.float64).mean(0)
                                               if rv == 'cheliped_wrist_L' else None, cg=cg))
        if seg == 'carpus' and carpus_margin is not None:
            # x6fix_x7 (11-11): the cutter's build's wrist is the UNION of its own sweep's margin and the crusher's
            # (the docstring's carpus_margin; union_margin says why): the same cage, so the same profile samples
            mg_ = union_margin({k_: v_ for k_, v_ in carpus_margin.items() if k_ != '_tree'}, mg_,
                               label=f'{nm} (distal end; the crusher\'s margin and the {kind}\'s own)', log=log)
        lay_membrane(cg, mg_, nm, ch_j, ch_nm)
        # (the merus's reach 0.7: the knee's 30 deg fold lays the carpus along its flexor side, n04's window, x04 _x4d2:
        # its margin 15.9 mm from its start, tau ~1.35)
        if seg == 'carpus':     # X4e (the lead's call 4 on the X4d check; decapod_parts KNEE): its proximal end is the
            u_c = (cg.V[np.asarray(cg.Q, int)].mean(1) - a0) @ axis      # WHEEL, hard at every pose (r57282_6's ball
            cg.meta['region'] = np.where((cg.meta['region'] == 'cap') & (u_c < 0.0), 'lump',    # under the merus's rim),
                                         cg.meta['region'])         # chitin that keeps its texels, not a buried condyle
            cg.meta['wheel'] = True
        u_rec = {k_: v for k_, v in cg.meta['record_ids'].items()}
        cg.meta['record_ids'] = {rn: u_rec[min(u_rec, key=lambda t_: abs(t_ - (1.0 + float(
            (np.asarray(c_) - a0) @ axis) / L_)))] for rn, c_ in rec_names.items()}
        cg.meta.update(joint=nm, parent='body' if seg == 'coxa' else SH[i - 1], axis=axis, a0=a0, b=b, field=field,
                       condyle=cond, trim=B_['trim'])
        out[nm] = cg
        tr = B_['trim']
        log(f'[decapod_cage] {nm}: K {K}{" (sag-spaced angles)" if th is not None else ""}, {len(cg.meta["taus"])} rings, '
            f'{len(cg.Q)} quads' + (f'; records {list(cg.meta["record_ids"])}' if rec_names else '')
            + f'; its clay pole {cond["depth_clay"]:.2f} mm in {par_nm} ({cond["depth_clay"] / cond["rbar"]:.2f} r)'
            + (f', the condyle lengthened {cond["ext"]:.2f} mm (hidden): {cond["depth"]:.2f} mm' if cond['ext'] > 0
               else '') + f'; trim: {tr["why"]}' + (f' at {tr["t"]:.2f} mm behind X0 (of {tr["t_back"]:.2f})'
                                                     if tr['t'] is not None else ''))
    # ---- the claw: the propodus (palm and fixed finger, split at the gape's station for the regions), the dactyl
    s_gape = float(np.asarray(info['claws'][kind]['polys']['gape'])[0])
    feats = kind == 'crusher'                           # X4b: §5.3's features (the lead's call 2), the crusher's
    cc_ = CAGE['cap_c_cutter'] if kind == 'cutter' else {}     # each claw's ends' hand-over (the crusher's: CAGE cap_c)
    sock = info['claws'][kind].get('socket')            # X4e (decapod_parts SOCKET): the crusher's rim
    # (X4e: on the crusher the band's columns run on past the gape up the rim's arch to the knob, FEAT band notch: its
    # limit cut the rim's corner 0.875 mm with columns crossing it, x04 _x4e1)
    s_band = s_gape if sock is None else float(sock['angles']['H'][0]) + FEAT['band']['propodus']['notch']
    apex = []                                           # X4g: a ring through the notch's apex (CAGE station_gap's note)
    if sock is not None:                                # and through the far end of a ray steeper than CAGE ray_steep
        sa_ = sock['angles']
        b_ = math.radians(0.5 * (sa_['phi_n'] + sa_['phi_o']))
        pts2 = [np.asarray(sa_['H'], np.float64) + float(sock['r_cup']) * np.array([math.cos(b_), math.sin(b_)])]
        for ph_, P2_ in ((sa_['phi_n'], sa_['G']), (sa_['phi_o'], sa_['A'])):
            if abs(((ph_ + 90.0) % 180.0) - 90.0) > CAGE['ray_steep']:
                pts2.append(np.asarray(P2_, np.float64))
        apex = [fr['W'] + p_[0] * unit(fr['d']) + p_[1] * unit(fr['n']) for p_ in pts2]
    foot = {}                                           # X4g: the collar's wall columns (CAGE foot_pull) over the gape
    if sock is not None:                                # ray's span along the claw, 3 mm past each end
        hs_, gs_ = float(sock['angles']['H'][0]), float(sock['angles']['G'][0])
        foot = dict(foot_pull=CAGE['foot_pull'], foot_span=(min(hs_, gs_) - 3.0, max(hs_, gs_) + 3.0))
    cgp = claw_cage(pn, BLD[pn]['field'], fr['propodus'], fr['W'], fr['d'], fr['n'], CAGE['K']['propodus'],
                    fixed_at=apex,
                    hidden=HID[pn], s_min=BLD[pn]['s_min'], hide=(hide_fns(4)[0], None), hidden_fn=sight_fn(4),
                    turn_max=CAGE['turn_max_propodus'], cap_c=cc_.get('propodus'),
                    cap_rmin=CAGE['cap_rmin_cutter'].get('propodus') if kind == 'cutter' else None,
                    cap_roll=CAGE['cap_roll_cutter']['propodus'] if kind == 'cutter' else (0, 0),
                    anchor=CAGE['anchor_crusher'] if (sock is not None and kind == 'crusher') else None,   # (X4f: the
                    #                                   cutter socketed too keeps its own rings' phase: the anchor is the
                    #                                   crusher's cheek's, gate 10)
                    occlusal=dict(FEAT['band']['propodus'], s_from=s_band,     # (X4d: the cutter's too, call 5,
                                  tip_fade=4.0 if kind == 'cutter' else 0.0,   # its warp faded out at its narrow tip)
                                  **foot))
    sq = (cgp.V[np.asarray(cgp.Q, int)].mean(1) - fr['W']) @ fr['d']
    cgp.meta['region'] = np.where(cgp.meta['region'] == 'cap', 'cap', np.where(sq < s_gape, 'palm', 'finger'))
    if kind == 'crusher':       # X4d (the lead's call 1): the base's end is its ARTICULAR KNOB (decapod_parts CLAW lump),
        cgp.meta['region'] = np.where((cgp.meta['region'] == 'cap') & (sq < 0.5 * s_gape), 'lump',   # in sight below
                                      cgp.meta['region'])           # the carpus as c11's lump: chitin, not a buried cap
    cgp.meta.update(joint='cheliped_propodus_L', parent='cheliped_carpus_L', frames=fr, field=BLD[pn]['field'],
                    trim=BLD[pn]['trim'])
    out[f'cheliped_propodus{tag}_L'] = cgp
    dcu_ = CAGE['dactyl_cutter'] if kind == 'cutter' else {}      # (X4h: the cutter's band columns)
    cgd = claw_cage(dn, BLD[dn]['field'], fr['dactyl_local'], fr['o_d'], fr['dd'], fr['nd'],
                    dcu_.get('K', CAGE['K']['dactyl']),
                    hidden=HID[dn], spine=sp_d0, hidden_fn=sight_fn(5), cap_c=cc_.get('dactyl'),
                    cap_rmin=CAGE['cap_rmin_cutter'].get('dactyl') if kind == 'cutter' else None,
                    cap_roll=CAGE['cap_roll_cutter'].get('dactyl', (0, 0)) if kind == 'cutter' else (0, 0),
                    split_first=bool(dcu_.get('split_first', False)), anchor=dcu_.get('anchor'),
                    hide=(hide_fns(5)[0] if sock is not None else None, None),
                    occlusal=dict(FEAT['band']['dactyl'], **{k_: dcu_[k_] for k_ in ('cols', 'band_nb', 'corner_share')
                                                             if k_ in dcu_}))
    cgd.meta.update(joint='cheliped_dactyl_L', parent='cheliped_propodus_L', frames=fr, field=BLD[dn]['field'],
                    trim=BLD[dn]['trim'])
    out[f'cheliped_dactyl{tag}_L'] = cgd
    if sock is None:
        # X4d (the lead's call 2, joint_margin): THE CLAW'S JOINT on the dactyl's own clay: its base, which the close
        # drives into the propodus, past its margin is membrane riding the propodus (the cutter's claw keeps this)
        lay_membrane(cgd, joint_margin(BLD[dn]['field'], cgd.meta['spine'], 'proximal',
                                       (pn, BLD[pn]['field'], MO['cheliped_dactyl_L'], False), label=dn, log=log),
                     'cheliped_propodus_L', 'cheliped_dactyl_L', f'cheliped_propodus{tag}_L')
    else:
        # X4e (the lead's calls 1-2 on the X4d check, THE SOCKET): the dactyl's base is a FAN about the hinge axis
        # sliding through the propodus's rim (a concave arch) into its socket: no skinned membrane on the dactyl (its
        # heel and broad faces are chitin at every pose, its tongue's end a buried cap, hidden over the range, the fan
        # behind its hard edge the crescent past the wedge's opening); the rim's surface is the OPENING the base fills
        # at every pose, ringed by the crescent; the socket rides in the propodus's meta for x04's gate 9 (its chitin
        # without the socket)
        notch_opening(cgp, sock, BLD[pn]['field'], BLD[dn]['field'], MO['cheliped_dactyl_L'], log=log)
        dactyl_edge(cgd, sock, info['claws'][kind]['want'], log=log)
        cgp.meta['socket'] = sock
    for nm_, B_ in ((pn, BLD[pn]), (dn, BLD[dn])):
        tr = B_['trim']
        log(f'[decapod_cage] {nm_}: trim: {tr["why"]}' + (f' at {tr["t"]:.2f} mm behind X0 (of {tr["t_back"]:.2f})'
                                                         if tr['t'] is not None else '')
            + (f'; the hidden run {tr["run"][0]:.2f}-{tr["run"][1]:.2f} mm' if tr.get('run') else ''))
    log(f'[decapod_cage] the {kind}: propodus {len(cgp.Q)} quads ({len(cgp.meta["taus"])} rings), dactyl {len(cgd.Q)} '
        f'({len(cgd.meta["taus"])} rings; its planes start on the base face\'s normal)')
    # ---- the sleeves (§5.4): child, parent, the child's joint point, the record carried; on the children's build
    # fields (a trimmed condyle keeps its sleeve inside: cut_depth's t_min)
    sl_specs = [('thorax_coxa', 'cheliped_coxa_L', 'ventral_thorax', 'coxa', 'cheliped_coxa_L'),
                ('coxa_basis', 'cheliped_basis_L', 'cheliped_coxa_L', 'basis', None),
                ('ischium_merus', 'cheliped_merus_L', 'cheliped_basis_L', 'merus', None),
                ('merus_carpus', 'cheliped_carpus_L', 'cheliped_merus_L', 'carpus', 'cheliped_carpus_L')]
    for sname, child, parent, seg, rec_name in sl_specs:
        ccg = out[child]
        axis = ccg.meta['axis']
        th = None
        if rec_name is not None:
            r = R[rec_name]
            X = np.asarray(r['frame']['creature']['X'], np.float64)
            K = int(r['K'])
            rec = np.asarray(r['verts_mm'], np.float64)
            th = record_angles(r)
        else:
            X = plane_frame(axis)[1]
            K = ccg.K                                   # (the child's columns: the basi-ischium's K 20 since X4b)
            rec = None
        sc_ = sleeve_cage(f'sleeve_{sname}_L', BLD[child]['field'], F[parent],
                          np.asarray(pts[JOINT_PT[seg]], np.float64), axis, K, X, record=rec, th=th)
        sc_.meta.update(joint=child, parent=parent, record_ids={rec_name: sc_.meta['ring_ids'][0]} if rec_name else {})
        out[sc_.name] = sc_
    # X4d: NO propodus-dactyl sleeve: the claw's joint membrane is the dactyl's own base (joint_margin; X4c's sleeve,
    # rigid inside it, came out 0.36 mm past the base's membrane at 30 deg open: a cut). Its condyle frame stays for x04's
    # gate 5 (where the dactyl's axis leaves the propodus, X3's sleeve rule)
    cgd.meta['x0'] = dict(X0=Xd, axis=nb, t_back=tb_d, r_bar=rb_d, d=dd_, d_in=ddin)
    log('[decapod_cage] sleeves: ' + ', '.join(f'{n} K {c.K}' for n, c in out.items() if n.startswith('sleeve')))
    if feats:                                           # X4b, the lead's call 2: the features, on the built cages
        crusher_features(out, fr, info, log=log)
    else:                                               # X4c, the lead's call 3: the cutter's saw (strokes for X6), the
        crusher_features(out, fr, info, log=log, claw='creases', kind='cutter')     # proximal chain's own features (the
        cutter_strokes(out, fr, info, spec, log=log)    # crusher's); X4d (call 5): its claw's cutting edges creased
    # A0 (x6fix_x7, 11-11): THE CARPUS IS REFITTED TOO. On the fist its dorsal and ventral lobes end at RADIAL planes
    # (decapod_parts ARM carpus lips: `up`, `low`), so each lobe's rolled rim (k_rim 1.2, a step down to the membrane
    # that grows to ~2 mm by the wrist's end) runs ALONG the columns, between two of them 2.2-2.5 mm apart: the limit
    # stood 0.615 / 0.670 mm off the clay on 2 quads of the ventral lobe's tip (x04 _a0f gate 10; more rings did not
    # help: turn_max 24 / 18 read 0.710 / 0.489, scratch x6fix_x7 runs/arm_turn*.log). The claws' cure, the same
    # function; the wrist's X3 ring stays bit-exact (limit_refit holds a record with its one ring)
    for cg_ in (out['cheliped_carpus_L'], cgp, cgd):    # X4h (REFIT): the claw's cells that bridge the clay's blends
        relax_tilts(cg_, cg_.meta['field'], log=log)    # refitted to it (after the features, which stay fixed); the
        limit_refit(cg_, cg_.meta['field'], log=log)    # low's tilts relaxed first, and again if the refit made any
        if relax_tilts(cg_, cg_.meta['field'], log=log)[0]:
            limit_refit(cg_, cg_.meta['field'], log=log)
    skin_cages(out, log=log)                            # X4c, the lead's call 1: the membranes skinned to both shells
    # ---- X4b: the relations range_hidden reads, per shell: hidden by the unmoved shells over its own joint's range,
    # or by its child (and the child's own build field) over the child's joint's range
    rel = {}
    for i, s_ in enumerate(SH):
        rel[s_ if s_ in out else f'cheliped_{s_.split("_")[1]}{tag}_L'] = rel_of(i)
    out['_motions'] = MO
    out['_relations'] = rel
    return out


# X4d, the lead's calls 1-3, THE JOINTS' MARGINS (joint_margin): a shell's surface sampled on its own clay profile
# (cols columns, n_barrel stations over its barrel and n_end over the joint's end zone); a sample the swept partner comes
# within `clear` mm of (over the joint's range) lies past the margin; per column the margin is the first such sample
# from the far side, smoothed round the shell over `smooth` columns (never past the raw edge); an X3 ring on the shell
# must lie `keep` mm (of arc) on the chitin side of it on every column (a loop inside the chitin); the skin's ramp ends
# where every sample past it lies `inside` mm within the partner at the bind; margin_f interpolates a point's arc past
# the margin from its `knn` nearest samples
WRIST = dict(clear=0.3, keep=1.5, cols=48, n_barrel=161, n_end=80, smooth=1.5, inside=0.3, knn=4,
             fold_keep=0.35, fold_steps=(1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.4, 2.8, 3.4, 4.0), far=1.0, keep_ring=2.5,
             keep_vert=1.5)
# X4e (spine_feet): a hard feature's foot (a spine) lies `keep` mm of arc on the chitin side of its shell's margin on
# every column within keep_ring + its d / 2 of the foot, the margin held past it (and its neighbouring columns)
# x6fix_x7 (11-11): ... and every vertex of the PATCH the cage cuts for it (spine_patch) within keep_vert of a sample.
# The foot's circle was meant to hold "its patch and a ring of faces round it", but a 2 x 2 patch is not centred on
# the foot (knob_patch) and on the A0 merus (a club 21 mm deep, columns ~3.4 mm) its far edge stood 4.9 mm from the
# patch's middle: x04 _a0f gate 11 "cheliped_merus_L features on its membrane: 4 off rigid" (w up to 0.997; keep_ring
# 4.5 still left 1 at 0.011, scratch x6fix_x7 runs/arm_refit_keep45.log)
# x6fix_x7 (11-11 10:40): the PATCH's keep-out holds only the profile columns with a sample within keep_vert of one of
# its vertices, WITHOUT the foot's spread to the neighbouring columns (a foot point's circle guesses where its patch
# will be; a patch's vertices are known, and margin_f reads a vertex's WRIST knn nearest samples, ~0.3 mm apart along
# its own column, columns ~1.2 mm apart). The spread carried the merus's dorsal patch edge (profile columns 19-22,
# 47.5-48.2 mm) onto column 23, the knee window's edge, whose margin went 27.9 -> 47.5 mm: chitin where the carpus
# sweeps, x04 _a0h gate 9 'merus in carpus 43 pts 0.90 mm (at +61.4), 12 pts 0.50 (at the bind)', every point on
# column 23 (scratch x6fix_x7 claw/probe_knee_g9.py; with no patch keep-out: 0 pts)
# X4d (the posed folds, x04 gate 11): along a column the membrane's posed arc is about S + w(S) D(S) (D a partner-riding
# point's travel along the column at a pose, w the ramp's smoothstep, its slope up to 1.5 / L): a ramp ending at the
# partner's rim (x04 _x4d5) let the partner's travel back toward the margin fold the closing side's membrane inside out
# in sight at every joint (scratch probe_folds: the knee's window 196 mm^2 at the fold, the cutter's dactyl base 115 mm^2
# open). So each column's ramp is the shortest of fold_steps x its rim length whose posed segments each keep fold_keep
# of their length along their reference direction ((1 - w) e0 + w R e0) at every pose of the joint (joint_margin's
# folds_ok), at most `far` mm short of the column's end (a far part rides the partner fully), then dilated and smoothed
# round the columns (neighbours' ramps alike: no shear between columns)


def spine_feet(nm, field, a0, b, axis, wrist=None, cg=None):
    """X4e (the lead's call 4 on the X4d check: the merus's distal spine's foot smeared toward the carpus, 30 of its 92
    vertices skinned up to 0.80, 3.2 mm at the fold): the FEAT segment_spines of shell nm as KEEP-OUTS for its joint
    margins, (foot point on the clay, radius, name) each: placed as crusher_features places them (u along its chitin
    a0 -> b, or to the wrist ring's centre `wrist`, the direction about its axis, cast onto the clay), the radius the
    foot's d / 2 + WRIST keep_ring (its patch and a ring of faces round it), so no hard feature stands past a margin
    (the X4d check's (c)). x6fix_x7 (11-11): cg, the shell's cage as built (its rings and columns are the ones
    crusher_features cuts the patch on): one more keep-out per spine, (the patch's vertices (n, 3), WRIST keep_vert,
    name), WRIST's comment says why"""
    out = []
    axis = unit(axis)
    for fs in FEAT['segment_spines'].get(nm, ()):
        u_end = float(np.linalg.norm(np.asarray(b) - np.asarray(a0)))
        if wrist is not None:
            u_end = float((np.asarray(wrist, np.float64) - a0) @ axis)
        d1, d2, ang = fs['dir']
        dv = unit(math.cos(math.radians(ang)) * _dir_of(d1, axis) + math.sin(math.radians(ang)) * _dir_of(d2, axis))
        c_ = a0 + fs['u'] * u_end * axis
        t_ = float(field.cast(c_[None, :], dv[None, :], 40.0)[0])
        if np.isfinite(t_):
            out.append((c_ + t_ * dv, 0.5 * fs['d'] + WRIST['keep_ring'], fs['name']))
        if cg is not None:
            _, _, j0, nj_, k0, na_ = spine_patch(cg, fs, np.asarray(a0, np.float64), axis, u_end)
            ids = cg.meta['ring_ids']
            pv = [int(ids[j0 + b_, (k0 + a_) % cg.K]) for b_ in range(nj_ + 1) for a_ in range(na_ + 1)]
            out.append((np.asarray(cg.V, np.float64)[pv], WRIST['keep_vert'], f'{fs["name"]}\'s {na_} x {nj_} patch',
                        False))
    return out


def joint_margin(field, spine, end, partner, ring_verts=None, label='', log=print, reach=0.5, keep_out=()):
    """X4d, the lead's calls 1-3 (THE JOINTS AS M1 HAS THEM: the wrist, the claw, the knee window, and the proximal
    joints by the same rule): ONE MEMBRANE PER JOINT, on one of its two shells' own clay. The shell's chitin runs on its
    clay to its TRUE MARGIN, where the swept partner first reaches it: along each column of its profile (WRIST cols
    columns over its barrel and the joint's end zone; `spine` its cage's spine), the first sample from the far side that
    the partner (partner = (name, its build field, the joint's motion, True when the PARTNER moves with the joint:
    this shell the parent)) comes within WRIST clear of, over the joint's range. Past the margin the shell's faces are
    the joint's membrane, skinned toward the partner: they ride this shell at the margin and the partner where every
    sample lies WRIST inside within it at the bind (the membrane's end inside the partner on every side), a smoothstep
    over the arc between. end 'distal': the parent's distal end (the wrist's carpus, the knee's merus: X4's inset collar
    and its showing end gone); 'proximal': the child's proximal end (the claw's dactyl: the base the close drives into
    the propodus becomes membrane riding the propodus, so the band in sight at the bind is the crescent the close
    sweeps, widening toward the gape as r57282_7 shows, the chitin stops at contact and no base face is left to show;
    in the dactyl's frame the margin is the radial line the notch face sweeps, the lead's radial notch). By symmetry no
    partner chitin crosses this shell's chitin either: where it would, this shell's surface is within reach of it. The
    shell stays one closed cage; the margin is a smooth function on it (margin_f), not a loop of its rings (scratch x4d
    probe_margin / probe_plane2 / probe_union: at the wrist the margin is U-shaped; one tilted plane left ~2 mm more
    membrane in sight; one margin for both carpi, from both claws' sweeps, 3 mm more beside the crusher: each wrist
    takes its own claw's, on the same mirrored cage). ring_verts: an X3 ring on this shell, kept WRIST keep on the chitin
    side. reach: only the `reach` share of the barrel nearest the joint (and its end zone) can be the joint's: a touch
    farther off is another contact (the fingers meeting at the close), not this joint's membrane. keep_out (X4e): hard
    features' feet held on the chitin side (spine_feet). Returns the skin's
    profile data: dict(kind 'profile', samples (m, 3), f_s (m,) each sample's arc past the
    margin, L, flip (end 'proximal': the weight is the child's, this shell), slack (the X3 ring behind the margin, its
    least, or None), band (the membrane in sight at the bind per column, max / mean mm), lam, rows)"""
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d, minimum_filter1d
    name, fld, mo, partner_moves = partner
    K = WRIST['cols']
    th = 2.0 * np.pi * np.arange(K) / K
    nb = WRIST['n_barrel']
    if end == 'distal':
        taus = np.concatenate([1.0 + np.linspace(0.0, 1.0, nb), 2.0 + np.linspace(0.0, 1.0, WRIST['n_end'] + 1)[1:]])
    else:
        taus = np.concatenate([2.0 - np.linspace(0.0, 1.0, nb), 1.0 - np.linspace(0.0, 1.0, WRIST['n_end'] + 1)[1:]])
    Rs = cast_profile(field, spine, taus, th, math.radians(CAGE['phi_max']))
    seg = np.linalg.norm(np.diff(Rs, axis=0), axis=2)
    S = np.concatenate([np.zeros((1, K)), np.cumsum(seg, axis=0)])         # the arc along each column from its start
    P = Rs.reshape(-1, 3)
    o = np.asarray(mo['o'], np.float64)
    d_bind = fld.eval(P).reshape(Rs.shape[:2])
    d_min = d_bind.copy()
    for a in mo['angles']:
        Rm = rot_axis(mo['z'], a)
        Q = (P - o) @ Rm + o if partner_moves else (P - o) @ Rm.T + o      # this shell in the posed partner's frame
        d_min = np.minimum(d_min, fld.eval(Q).reshape(Rs.shape[:2]))
    tch = d_min < WRIST['clear']
    tch &= ((taus >= 2.0 - reach) if end == 'distal' else (taus <= 1.0 + reach))[:, None]   # (the joint's own share)
    if not tch.any():
        raise RuntimeError(f'joint_margin: {name} never reaches {label} over the joint\'s range')
    cols = np.arange(K)
    edge = np.array([int(np.nonzero(tch[:, k])[0][0]) if tch[:, k].any() else len(taus) - 1 for k in cols])
    lam_raw = S[edge, cols] - 0.05
    lam = np.minimum(gaussian_filter1d(minimum_filter1d(lam_raw, 3, mode='wrap'), WRIST['smooth'], mode='wrap'), lam_raw)
    kept = []
    for ko_ in keep_out:                                # X4e: hard features' feet on the chitin side (spine_feet)
        P_k, rad_k, nm_k = ko_[:3]                      # (x6fix_x7: a point or a feature patch's vertices)
        spread = ko_[3] if len(ko_) > 3 else True
        P_k = np.asarray(P_k, np.float64).reshape(-1, 3)
        near_k = np.zeros(Rs.shape[:2], bool)
        for p_ in P_k:
            near_k |= np.linalg.norm(Rs - p_[None, None, :], axis=2) < rad_k
        if not near_k.any():
            continue
        need = np.where(near_k.any(axis=0), np.where(near_k, S, -np.inf).max(axis=0) + WRIST['keep'], -np.inf)
        need = np.where(np.isfinite(need), need, -1.0e9)
        if spread:                                      # (a foot's circle: its neighbouring columns too, X4e; a known
            need = maximum_filter1d(need, 3, mode='wrap')   # patch: only the columns within keep_vert, WRIST's comment)
        moved = need > lam
        lam = np.maximum(lam, need)
        kept.append(f'{nm_k} kept {WRIST["keep"]} mm inside the chitin (the margin moved on {int(moved.sum())} columns, up '
                    f'to {float(np.max(np.where(moved, need - lam_raw, 0.0))):.1f} mm past the first touch)')
    slack = None
    if ring_verts is not None:                          # the X3 ring on each column (on the barrel), its arc
        ax_ = spine.T_end[0] if end == 'distal' else -spine.T_end[1]
        s_ring = float(((np.asarray(ring_verts, np.float64) - spine.P[0]) @ ax_).mean())
        j_ring = np.argmin(np.abs((Rs[:nb] - spine.P[0]) @ ax_ - s_ring), axis=0)
        slack = float((lam - S[j_ring, cols]).min())
    f_s = S - lam[None, :]
    out_ = (d_bind > -WRIST['inside']) & (f_s > 0.0)
    # the ramp PER COLUMN: each column rides the partner fully from where its own samples lie inside it (x04 _x4d4: one
    # ramp for all, set by the longest column, 7.7 mm on the carpus's condyle, left the knee sleeve's band inside it
    # blended differently from the membrane round it, 0.79 mm out at the fold)
    L_col = np.array([float(f_s[out_[:, k], k].max()) + 0.5 if out_[:, k].any() else 0.5 for k in cols])
    # X4d (WRIST fold_*): each column's ramp lengthened until the posed arc never folds (WRIST's comment)
    L_rim = L_col.copy()
    PPs = []                                            # per pose: a point riding the partner, posed, in this shell's
    for a in mo['angles']:                              # frame
        Rm = rot_axis(mo['z'], a)
        PPs.append(((P - o) @ Rm.T + o if partner_moves else (P - o) @ Rm + o).reshape(Rs.shape))
    e0 = np.diff(Rs, axis=0)
    l0 = np.maximum(np.linalg.norm(e0, axis=2), 1e-9)
    cap = np.maximum(f_s[-1] - WRIST['far'], L_col)     # (the column's arc past the margin to its end, less `far`)

    def folds_ok(Lc):
        """per column: every ramp segment's posed vector along its reference ((1 - w) e0 + w R e0, w the segment's
        mean: 1 for either shell's rigid motion) >= fold_keep of its length, at every pose (3D: x04 _x4d7's arc along
        the rest tangent read a rigid turn round a column's end as a fold)"""
        g_ = np.clip(f_s / Lc[None, :], 0.0, 1.0)
        w_ = g_ * g_ * (3.0 - 2.0 * g_)
        wm = 0.5 * (w_[1:] + w_[:-1])[..., None]
        span = (f_s[1:] > 0.0) & (f_s[:-1] < Lc[None, :])
        ok_ = np.ones(K, bool)
        for Pp in PPs:
            e1 = np.diff(Rs + w_[..., None] * (Pp - Rs), axis=0)
            tr = (1.0 - wm) * e0 + wm * np.diff(Pp, axis=0)
            r_ = (e1 * tr).sum(axis=2) / (np.maximum(np.linalg.norm(tr, axis=2), 1e-9) * l0)
            ok_ &= np.where(span, r_ >= WRIST['fold_keep'], True).all(axis=0)
        return ok_
    L_need = np.full(K, np.nan)
    for f_ in WRIST['fold_steps']:
        Lc = np.minimum(L_col * f_, cap)
        ok_ = folds_ok(Lc) & np.isnan(L_need)
        L_need[ok_] = Lc[ok_]
    n_cap = int(np.isnan(L_need).sum())                 # (columns no step frees: their ramp at the cap)
    L_need = np.where(np.isnan(L_need), cap, L_need)
    L_fold = np.minimum(np.maximum(L_need, gaussian_filter1d(maximum_filter1d(L_need, 3, mode='wrap'),
                                                             WRIST['smooth'], mode='wrap')), cap)
    n_long = int((L_fold > L_col + 1e-6).sum())
    still = int((~folds_ok(L_fold)).sum())
    L_col = L_fold
    g_s = np.clip(f_s / L_col[None, :], -1.0e3, 1.0e3)
    vis = (f_s > 0.0) & (d_bind >= 0.0)
    band = (seg * (vis[1:] & vis[:-1])).sum(axis=0)
    row = (f'{label} ({end} end, against {name}): the margin {np.percentile(lam, 5):.1f}-{lam.max():.1f} mm of arc from '
           f'the profile\'s {"start" if end == "distal" else "distal end"}'
           + (f'; the X3 ring {slack:.2f} mm behind it at least' + (' (UNDER WRIST keep)' if slack < WRIST['keep'] else '')
              if slack is not None else '')
           + f'; the membrane in sight at the bind per column max {band.max():.1f} / mean {band.mean():.1f} mm; the skin '
           f'ramp per column {L_col.min():.2f}-{L_col.max():.2f} mm ({int((g_s >= 1.0).sum())} samples past it, inside '
           f'{name} by {WRIST["inside"]} mm; from the rim\'s {L_rim.min():.2f}-{L_rim.max():.2f}, lengthened on {n_long} '
           f'of {K} columns so the posed arc never folds' + (f', {n_cap} at their cap' if n_cap else '')
           + (f', {still} STILL FOLDING' if still else '') + ')' + ''.join(f'; {k_}' for k_ in kept))
    log(f'[decapod_cage] joint margin (X4d): {row}')
    return dict(kind='profile', samples=P.copy(), f_s=f_s.reshape(-1), g_s=g_s.reshape(-1), L=float(L_col.max()),
                L_col=(float(L_col.min()), float(L_col.max())), flip=end == 'proximal',
                slack=slack, band=(float(band.max()), float(band.mean())), lam=lam, rows=[row])


def union_margin(a, b, label='', log=print):
    """x6fix_x7 (11-11): ONE membrane from two joint_margin dicts on the SAME profile (the same shell's samples): past
    the margin wherever EITHER is (f_s the larger: chitin only where both keep it) and riding the partner as much as
    either ramp does (g_s the larger: skin_w's smoothstep is monotone, so w = max of the two). For a carpus whose clay
    carries one claw's crescent and whose cage carries the other claw (cheliped_cages' carpus_margin): the cutter's
    wrist on the crusher's margin alone left chitin in the cutter's heel (x04 _a0g gate 9: 1.05 mm at the bind, 3.48 at
    +43.4); on its own its proximal cap showed from +20.9 deg (x04 _a0f gate 11). On the saved cages the union does
    neither: 0 chitin vertices > 0.3 mm in the cutter's propodus at any pose, the cap >= 1.37 mm inside, the 361
    vertices it gives w >= 0.999 all inside the cutter's propodus at the bind (scratch x6fix_x7
    claw/probe_cutter_cap_skins.py)"""
    if not np.allclose(a['samples'], b['samples'], atol=1e-9):
        raise ValueError(f'union_margin ({label}): the two margins are not on the same profile')
    gs_a, gs_b = np.asarray(a['g_s']), np.asarray(b['g_s'])
    out = dict(kind='profile', samples=np.asarray(a['samples']).copy(), f_s=np.maximum(a['f_s'], b['f_s']),
               g_s=np.maximum(gs_a, gs_b), L=float(max(a['L'], b['L'])),
               L_col=(float(min(a['L_col'][0], b['L_col'][0])), float(max(a['L_col'][1], b['L_col'][1]))),
               flip=bool(a.get('flip')), band=(float(max(a['band'][0], b['band'][0])), float(max(a['band'][1], b['band'][1]))),
               slack=(None if a.get('slack') is None or b.get('slack') is None else float(min(a['slack'], b['slack']))),
               lam=np.minimum(a['lam'], b['lam']))
    row = (f'{label}: the UNION of two margins (x6fix_x7): past either margin on {int((out["f_s"] > 0).sum())} of '
           f'{len(out["f_s"])} samples (the first {int((np.asarray(a["f_s"]) > 0).sum())}, the second '
           f'{int((np.asarray(b["f_s"]) > 0).sum())}); riding the partner fully (g >= 1) on {int((out["g_s"] >= 1).sum())} '
           f'(the first {int((gs_a >= 1).sum())}, the second {int((gs_b >= 1).sum())})')
    out['rows'] = list(a.get('rows', [])) + list(b.get('rows', [])) + [row]
    log(f'[decapod_cage] joint margin (X4d): {row}')
    return out


def margins_of(cg):
    """X4d: a shell's joint membranes (joint_margin dicts, lay order), [] for a rigid one"""
    return cg.meta.get('margins', [])


def chitin_mask(cg, P):
    """X4d: True where points P (any (..., 3)) lie on a shell's chitin: outside every one of its membranes"""
    m = np.ones(np.asarray(P).shape[:-1], bool)
    for mg in margins_of(cg):
        m &= margin_f(mg, P) <= 0.0
    return m


def skin_at(cg, joint):
    """X4d: the skin of cage cg that `joint` blends (its child joint: a membrane of a shell, a sleeve), or None (a
    shell may carry two: the carpus's buried condyle at the knee and its distal end at the wrist)"""
    sks = cg.meta.get('skins')
    if sks is None:
        sks = [cg.meta['skin']] if cg.meta.get('skin') else []
    return next((sk for sk in sks if sk['child'] == joint), None)


def margin_f(skin, P, key='f_s'):
    """X4d: a skinned cage's MARGIN COORDINATE at points P (any (..., 3)): mm past its parent's rim toward its child (<= 0
    on the parent's side). A shell's membrane (skin kind 'profile', joint_margin): the arc past the margin along the
    shell's clay profile, inverse-distance interpolated from the WRIST knn nearest samples (key 'g_s': the same as a
    share of each column's own ramp, skin_w's); a sleeve's (X4c): the distance along its own axis past s0"""
    P = np.asarray(P, np.float64)
    sh = P.shape[:-1]
    Q = P.reshape(-1, 3)
    if skin.get('kind') == 'profile':
        tree = skin.get('_tree')
        if tree is None:
            from scipy.spatial import cKDTree
            tree = skin['_tree'] = cKDTree(skin['samples'])
        d, i = tree.query(Q, k=WRIST['knn'])
        w = 1.0 / np.maximum(d, 1e-6)
        f = (skin[key][i] * w).sum(1) / w.sum(1)
    else:
        f = (Q - skin['origin']) @ unit(skin['axis']) - skin['s0']
    return f.reshape(sh)


def skin_w(skin, P):
    """X4c, the lead's call 1 (THE JOINTS AS THE ANIMAL BUILDS THEM): a skinned cage's child weight at points P (any
    (..., 3)): 0 on the parent's side of the membrane, 1 past the child's, a smoothstep between (cg.meta['skin']: parent,
    child; a sleeve's along its own axis: origin, axis, s0 the parent's rim, s1 the child's; X4d, a shell's membrane
    (kind 'profile', joint_margin) along its profile past its margin over the ramp L: margin_f, flipped on a child's
    proximal end, whose chitin is the child's and whose membrane's end rides the parent); a rigid cage has no skin"""
    if skin.get('kind') == 'profile':                   # (X4d: each column's own ramp, joint_margin g_s)
        x = np.clip(margin_f(skin, P, key='g_s'), 0.0, 1.0)
    else:
        x = np.clip(margin_f(skin, P) / max(skin['s1'] - skin['s0'], 1e-9), 0.0, 1.0)
    w = x * x * (3.0 - 2.0 * x)
    return 1.0 - w if skin.get('flip') else w


def skin_cages(out, log=print):
    """X4c, the lead's call 1: the MEMBRANES SKINNED TO BOTH SHELLS (the X4b check: the wrist membrane rigid on the carpus
    showed its capped end outside the propodus base at both wrist extremes). X4d: each joint's MEMBRANE on its shell's
    own clay (joint_margin: the faces past the shell's margin) rides that shell at the margin and the joint's other
    shell from the skin ramp's end on (every sample past it inside the partner at the bind), a smoothstep between along
    the shell's profile (the dactyl's flipped: its chitin is the child's); each SLEEVE rides its parent at its proximal
    ring (X3's record on the parent where it carries one) and its child from its distal ring on. The shells' chitin
    stays single-influence (plan §10.2). Writes cg.meta['skin'] (skin_w's dict) on the skinned cages"""
    rows = []
    for nm, cg in out.items():
        mgs = margins_of(cg)
        if not mgs:
            continue
        cg.meta['skins'] = list(mgs)                    # X4d: each ramp starts ON its margin (kind 'profile'); x04 blends
        cg.meta['skin'] = mgs[0]                        # the one whose child joint moves (skin_at); 'skin' the first
        for mg in mgs:
            rows.append(f'{nm}\'s membrane: {mg["parent"]} -> {mg["child"]} over {mg["L"]:.1f} mm past its margin'
                        + (' (flipped: the child\'s base)' if mg.get('flip') else ''))
    for nm, cg in out.items():
        if not nm.startswith('sleeve'):
            continue
        ch_cg = out.get(cg.meta['joint'])
        ax_, X0 = unit(cg.meta['axis']), np.asarray(cg.meta['X0'], np.float64)
        cs = cg.meta['centres']
        s0_, s1_ = float((cs[0] - X0) @ ax_), float((cs[-1] - X0) @ ax_)
        if ch_cg is not None and ch_cg.meta.get('wheel'):
            # X4e (decapod_parts KNEE): the sleeve lies wholly inside a carpus that turns on its wheel: nothing stretches
            # there, so it rides its child at every pose (ramp behind its first ring: weight 1). On a ramp from the merus its
            # proximal ring, 7 mm from K, stayed outside the 6 mm wheel as the carpus turned away (x04 _x4e2: 0.68 mm out,
            # the blue in sight at the fold)
            s0_, s1_ = s0_ - 2.0, s0_ - 1.0
        cg.meta['skin'] = dict(parent=cg.meta['parent'], child=cg.meta['joint'], origin=X0, axis=ax_, s0=s0_, s1=s1_)
        cg.meta['skins'] = [cg.meta['skin']]
        rows.append(f'{nm}: {cg.meta["parent"]} -> {cg.meta["joint"]}' + (' (wholly on its child: the wheel\'s)'
                                                                         if ch_cg is not None and ch_cg.meta.get('wheel')
                                                                         else ''))
    log('[decapod_cage] skinned (call 1): ' + '; '.join(rows))
    return rows


class _Union:
    """the union (min) of several fields (life mm), casts as Field"""

    def __init__(self, fields):
        self.fields = list(fields)

    def eval(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        return np.min(np.stack([f.eval(P) for f in self.fields]), axis=0)

    normals = Field.normals
    cast = Field.cast
