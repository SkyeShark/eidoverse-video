"""The PEAKED CAP (Schirmmuetze) of a GDR GENERAL: the third Bestiary accessory, built the forge way at real size
(research/CAP_GDR.md and CAP_REFERENCE.md: measured, never copied; top_hat.py / round_glasses.py the models it follows).

Skye asked (10-21) "for peaked caps try marschall der ddr"; no Marschall der DDR cap was ever made (the rank was never
conferred), and the cap is the GDR GENERAL'S peaked cap AS SKYE'S REFERENCES SHOW IT (10-22: work/bestiary/props/ref/,
egmar3b.jpg and images.jpg a general's cap from the front, the webp the state cockade close up), cross-checked only on
GDR photos (research/cap_web g01, g02, o01-o05): a stone-grey worsted crown with red piping round its edge over a
scarlet band, a large STAMPED GILT oak-leaf wreath round the state cockade on the band, two thick twisted gold cords at
ONE height round the band's front from button to button, and a PLAIN black lacquered visor. Nothing Soviet: no visor
sprays, no edge cord, no Soviet number (CAP_GDR §2's audit; forges 1-v3 built the Soviet marshal's visor).

  parts -> block-out SDF:  the cloth (band, the rolled wall, the stretched top) as ONE SHELL over its mid-surface (the
                           crown is oval and saddled: no REVOLVE), the visor a SHELL over its moulded mid-surface, the
                           crown-edge and band-top pipings, the visor's rolled rim and the two cords as SWEEPs, the
                           sliding knots as barrel SWEEPs round both cords, the buttons (head + split-pin shank, the
                           head over the cords' loop) and the cockade (its rings and steps) as REVOLVEs about the band's
                           normal
  -> the low:              the crown one ring loft (K_LOW columns; grid caps on the top and on the lining), the visor two
                           (s, xi) grids and a rim strip round its edge, the cords 8-round tubes (welded behind the
                           buttons), the knots 12-round barrels with grid caps, the buttons revolve pieces, the cockade a
                           revolve whose FACE is one planar island
  -> UV islands:           one texel density for the outside, the inside at a quarter, the band's front island (the
                           wreath) and the knots at twice, the COCKADE at COCKADE_SHARE (~13 px/mm: its emblem reads in
                           close-ups); the right knot and button stacked on the left; packed by a bisected density search
  -> sculpt plan:          the wall's front and back seams and the band's back seam, the cords' 3-ply twist, the knots'
                           over-under braid, the STAMPED METAL wreath (one solid relief: the top-most leaf's domed top
                           over each 0.1 mm cell, crisp edges, each upper leaf a step over the one under it, each lobe
                           its own pillow (cap v5.1), beaded midribs, acorns; a scarlet ring left round the cockade), the
                           cockade's relief (the hammer and
                           compass, the hinge boss, the rye's grains)
  -> voxel high + bake     (voxel.SparseSDF at 0.15 mm where detail lives, keep_region; bake.bake, GPU; forge() below):
                           the triangles buried in another part left out, the missed texels in contact crevices hidden;
                           both dilate
  -> material pass:        worsted twill crown (steingrau, no handling shine: cap v5), scarlet felt band and piping, the
                           wreath's scalloped backing (a deeper felt, its outline darker), gold-anodised twisted cords,
                           gilt metal (the wreath, the cockade's rings, rye and arms, the grained buttons; the rye's fine
                           grains and awns the texture's), the cockade's enamels (the red over its pebbled base, the
                           ribbon's black, red and yellow wrapping the ring), the lacquered visor (micro-scratches, a satin
                           grip band, edge scuffs), a leather sweatband and a linen lining; the gold's occlusion never
                           below AO_FLOOR_GOLD
  -> a static glb carrying its FIT data (the hat archetype's contract plus the visor's probes) and its conform morphs
  -> the fit: validate_fit (cap v3's: the cap's own proportions, the band's horizontal give, the parts carried rigidly,
     the visor's hinge within the GDR caps' measured pitch, the seat a support, the daylight under the band, the front
     read); checked in tests/t27_peaked_cap.py
BUDGET: about 6000 triangles (DESIGN.md's bar 6k; the top hat 5120, the glasses 5936); one 2048^2 set at ~3100 px/m

Frame: metres, +Y up = the seat axis, the origin at the centre of the head opening on the SEAT PLANE (y = 0: the band's
lowest edge), +Z forward (the visor), +X the wearer's left. The visor droops BELOW the seat plane at the front.

THE PROPORTIONS ARE SKYE'S CAP'S (cap v4, 10-22): egmar3b's measured pixels (CAP_GDR §3-§4: the seam, the cockade, the
cords per column, the visor's outline, the crown's and the band's widths, the piping's arc, the top seen behind it)
against this cap's geometry through a pinhole camera fitted JOINTLY with the band, crown, saddle, visor, cockade and
cords, the head opening held at size 57 [C] (tests/out/cap/v4/scratch/cam_fit2.py: rms 2.5 px over 70 landmarks; the
camera 0.52 m off, 21 deg above, 7 deg to the right). The ANCHOR: the head (size 57); the cockade follows at 26.4 mm
(the 21 mm record, Runde Ecke 10720, is the winter caps' aluminium cockade, and would make egmar3b's cap a size 44; the
45 mm band of the officers' records a size 37). REAL-SIZE NUMBERS (SPEC; tags: [C] a record, [M] measured, [E] an
estimate with its gate):
  * size 57: the opening 570 mm round [C Runde Ecke 09697], an oval 1.059 long : wide, the GDR crown's own 270 / 255 [C];
  * the band 68.8 mm, seam to the seat plane [M egmar3b fit]; its wall 4 mm [E]; the crown 280 x 297 in plan with its
    piping, 1.52 x the band's width [M egmar3b fit; the officers' 255 x 270 [C] keep the oval];
  * the crown edge above the band top: 74 mm at the front, 22 at the sides and back [M egmar3b fit: the piping's arc,
    the top seen behind it], h(phi) = 22 + 52 max(0, cos phi)^2; the top a stretched membrane sagging 3 mm [E]; the
    wall's meridian taut at the front, a roll at the sides and back [M o05, o01];
  * CAP V5 (the lead's eight decisions, 10-22; CAP_GDR §10): the crown's outline refitted on egmar3b (282.7 x 299.3,
    rise 74.1 / 27.4 / 18.2 at the front / sides / back by rise_w, k 0.65), its piping 4.6 mm; the colours her photos'
    lit medians (MATERIAL); the cords two twisted ROPES, past the visor's ends rising to 16 mm by 108 deg, the knots and
    buttons beyond, hidden from her camera; the wreath redrawn (long curving shallow-lobed leaves) on a scalloped scarlet
    BACKING; the cockade's rye fine (texture) and its ribbon five wrapping bands; the fit's gates decision 8's (a
    perched cap: the visor's and the back's contacts, no daylight from dead front and dead back). The v4 notes follow:
  * the piping 2.2 mm [M o04] (v5: 4.6 [M egmar3b]); the visor 172 mm end to end, 38 deep in plan, its ends 45 mm in front of the opening's
    widest line [M egmar3b fit; the depth trades against the fit (30 mm: rms 2.3 px, 45: 2.9, 58: 4.4), 38 the
    least that keeps every other number off its bound], its pitch 39.4 deg, the low end of the GDR caps' measured
    39.4-47.5 (VISOR_PITCH: the photo pulls it to that bound), 2.0 mm thick, a rolled rim [E o03, o04 by eye];
  * the cords 8.3 mm, two, stacked at the band's face, 3-ply, a lay of 1.05 cord diameters [M egmar3b fit: the pair 0.6
    D; plies E; the lay o03]; at ONE height round the front from button to button, the lower resting on the visor's
    root; the sliding knot at the visor's end 1.2 x the pair tall, the button 0.76 x the pair, the knot's centre 0.96 x
    the pair from the button's [M o03 at 1:1, ratios]; the buttons grained, domed, each HEAD over its cords' loop round
    the split-pin shank [C Runde Ecke "Splintknoepfe"; o03, o01];
  * the cockade 26.4 mm, its centre 41.8 mm up the band [M egmar3b fit], its face the state cockade measured on Skye's
    close-up (CK_*, CAP_GDR §6); the wreath stamped gilt metal, four broad lobed leaves a side [M egmar3b back-projected:
    wreath_layout], 4.5 x 2.1 cockade diameters;
  * colours [M]: crown (0.105, 0.086, 0.058), band (0.573, 0.050, 0.018) [g02 / o04 white-balanced]; the cockade's
    enamels from the close-up (red 0.325, 0.005, 0.012; ribbon red 0.517, 0.020, 0.019; yellow 0.774, 0.453, 0.0); gold
    F0 (1.0, 0.773, 0.307) [C physicallybased.info]; the visor near black, lacquer roughness 0.05-0.10 [E].

The forge calls it makes: sdf.Program (.shell, .sweep, .revolve, .eval, .project, .normals), voxel.SparseSDF (+
STROKE_CONE strokes), bake.bake / low_frames / dilate_all, uv.lscm / arap / self_overlap / footprint / island_density /
pack, material.low_at / to_world / to_tangent / surface_grad / mix3 / uv_bvh / corner_arrays / driver_arrays,
calib.relief_drivers, proc.noise3 / fbm3 / cellular3 / smoothstep, loft.cap / rmf, gltf.GLB; round_glasses.ring_tube
and .revolve_piece (the generic tube and lathe lows).

    prog = build_sdf();  low = build_low(prog);  uvs = unwrap(low);  L = low_arrays(low, uvs)
    plan = plan_cap(prog);  G = SparseSDF(...); plan.apply(G);  res = bake.bake(G, ...)          (GPU)
    maps = run_material(L, res, size, 1 / px_per_m);  export_glb(path, L, maps)
    or all of it: forge('work/bestiary/props')
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .. import sdf
from ..mesh import QuadMesh

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})   # forward-only; noise neighbour loops left rolled

SPEC = dict(
    head_circ=0.570,        # the opening's circumference (m): size 57 [C Runde Ecke 09697]: THE ANCHOR
    oval=1.059,             # the opening long : wide: the GDR crown's own 270 / 255 [C Runde Ecke 09697]
    band_h=0.0688,          # the band, its top seam over the seat plane [M egmar3b, the joint fit; the officers' caps'
                            # 45 [C] are not Skye's cap: egmar3b's band is 0.37 of its width, theirs 0.245]
    band_t=0.0040,          # its wall: felt, stiffener, sweatband [E]
    sweat_h=0.045,          # the leather sweatband's height and thickness [E]
    sweat_t=0.0009,
    crown_w=0.2779,         # the crown's PIPING in plan, its outer edge, side to side [M egmar3b, cap v6: the new crown
    crown_d=0.2939,         # refitted through t27's camera, tests/out/cap/v6/scratch/crown_fit_v6.py; the plan's oval
                            # free 1.00-1.08 lands on 1.057 against the GDR crown's recorded 270 / 255 = 1.059 [C]]; the
                            # roll stands over it (roll_out: +1.0 mm at the sides, inside it at the front)
    rise_side=0.0228,       # the piping's centre over the band's top at the sides, the front and the back, by rise_w [M
    rise_front=0.0735,      # egmar3b, cap v6: the top silhouette, the front piping's visible red run (its top and its
    rise_back=0.0115,       # bottom), the side tips and the sides' lower outline: rms 2.8 / 1.8 / 1.7 / 1.7 px, no back
    rise_round=0.72,        # piping on the silhouette, grey cloth beyond the piping at both tips; the back held 10-30 mm
                            # (a front view cannot part its depth from its height: free, it ran to 0), her photographed
                            # crown rolled 1.4 deg on its band, not forged (CAP_GDR §11). v5 (the piping at the top's
                            # edge): 27.4 / 74.1 / 18.2 / 0.65]
    flare=((0.95, 0.42), (0.81, 0.10)),   # the wall's meridian: a quadratic Bezier's control point (radial share,
                            # height share) at the front and at the sides and back [M egmar3b, cap v5: the crown's lower
                            # outline at its sides (v4 0.70, 0.25 from o05)], blended by max(0, cos phi)^2. Cap v7 (the
                            # lead's decision 6: "the front's profile convex, rounding over bluntly as g02"): the front
                            # SWELLS forward from the band (leaving it at ~31 deg) and turns up to near-vertical as it
                            # reaches the piping, so the front rounds over the roll instead of meeting the top in a wedge
                            # [g02 side-on: the front wall's silhouette near-vertical under its edge; E]. v6's (0.55,
                            # 0.45) arrived at the piping still climbing forward at ~60-74 deg: with the top falling away
                            # behind it, the narrow pointed prow the v6 check saw
    # cap v6 (the lead's decision 1): the crown's ROLLED TOP EDGE: the top's cloth rolled over its spring ring, standing
    # over the piping, which is a sweep on the wall BELOW it (egmar3b: the grey top 7-12 px over the front piping all
    # along, no back piping on the top silhouette, each side tip grey cloth rounding over the piping's end; o01 and
    # images.jpg the same construction). Per azimuth, about the piping's centre E in the meridian half-plane: the roll's
    # OUTER radius, its overhang beyond the piping's outer edge and its top over E, at the sides (and back) and at the
    # front, blended by max(0, cos phi)^2 (roll_geom) [M egmar3b through t27's camera: crown_fit_v6.py, CAP_GDR §11: its
    # top 7.6 mm over the piping's centre at the sides, 7.9 at the front (the lead's ~8), 1.0 mm beyond the piping's
    # outer edge at the sides (her tips' grey 1-4 px beyond the piping's end), 1.5 inside it at the front (her front
    # piping fully seen, 6-7 px)]
    roll_r=(0.00415, 0.00360),      # cap v7: the front roll rounder (v6 2.75 mm), its top and overhang held (her fit)
    roll_out=(0.00098, -0.00151),
    roll_h=(0.00756, 0.00785),
    # cap v6 (the lead's decision 6): the band's top SEAM raised at the front centre by seam_rise over |u| < seam_flat,
    # eased to nothing by seam_edge (u the band's arc from the front) [M egmar3b: her crown-to-band boundary per column
    # through t27's camera (v6_measure.py), fitted: rms 1.3 px against a level seam's 4.6 (crown_fit_v6.py)]
    seam_rise=0.0056, seam_flat=0.0116, seam_edge=0.0316,
    # cap v6 (the lead's decision 1: "the front rounds over as o01 / g02 show, no beak in profile"): the top's membrane
    # DOMED behind the front roll, (lift, reach): up to `lift` over the harmonic membrane, rising within `reach` of the
    # rim, weighted max(0, cos phi)^2 rho^2 (top_dome) [E: the GDR crowns of o01 and g02 round over at the front; the
    # front view leaves it free: the silhouette egmar3b shows is the back roll's]
    # cap v7 (decision 6, "rounding over bluntly"): the dome higher and broader (8 mm within 20 mm: the top LEAVES the
    # front roll rising, ~+3 deg, and stays up over the first 15-50 mm behind it, +2.7..3.9 mm; v6's 3.5 within 12 mm
    # left it at -4.8 deg and falling: the prow); the front view's top silhouette is the back roll's (untouched)
    top_dome=(0.0080, 0.020),
    sag=0.003,              # the top's sag [E 2-4]
    cloth_t=0.0012,         # the crown's shell: worsted and lining [E]
    pipe_d=0.0042,          # the crown edge's piping [M egmar3b, cap v5: 6-7 px = 0.16-0.19 D, 4.2-5.0 mm at this cap's
                            # cockade (the lead's decision 5); the low end, as the piping at the crown's front edge stands
                            # ~50 mm nearer her camera than the cockade (4.6 read 8.3 px there against her 6-7, t27 gate 15);
                            # v4's 2.2 was o04's, an officer's]
    band_pipe_d=0.0022,     # the band-top piping [M o04 2.0-2.3; unresolved on egmar3b, red on red]
    visor_w=0.172,          # the visor in plan: end to end [M egmar3b fit], depth at the centre [M egmar3b fit, the
    visor_d=0.038,          # depth traded against the fit: the least that keeps every other number off its bound]
    visor_end_z=0.0454,     # its ends meet the band this far in front of the opening's widest line [M egmar3b fit]
    visor_round=2.0,        # its outer edge in plan: a superellipse from corner to corner [M egmar3b fit]
    droop=(30.0, 48.0),     # the visor's slope at the root and at the tip, degrees below the horizontal: the chord's
                            # PITCH 39.4, the GDR caps' measured low end (VISOR_PITCH; egmar3b's fit pulls to it)
    visor_y=0.0012,         # the visor's top surface where it leaves the band's face (the band's lip sits on it)
    visor_t=0.0020,         # its thickness, and at the rim [E]
    rim_t=0.0025,
    visor_root=0.0025,      # its root buried this deep into the band wall
    cord_d=0.0083,          # the two cords [M egmar3b: the pair 23.5 px at the front centre through t27's camera = 1.935
                            # cord diameters stacked, 8.3 mm (cap v6 re-measured, CAP_GDR §11)]
    cord_ply_lay=0.0110,    # cap v6 (the lead's decision 3): each cord a TWO-PLY rope (two plies twisted on this lay,
    cord_bundle_lay=0.0045,  # each ply of three fine fibre BUNDLES twisted the other way on this one) [M egmar3b: the
                            # rhythm of the small slanted bumps along her lower cord 7.8 px = 5.3 mm (5.8 the v5 check's),
                            # a ply crest every half lay; research/cap_gdr_scripts/v6_rope.py; the prototype
                            # tests/out/cap/v6/scratch/rope_proto.py]. v5's three strands on a 45 mm lay with an 8.7 mm
                            # yarn twist read as diagonal ridged bars (the v5 check)
    cord_side_y=0.0172,     # the pair's centre at the knot and the button, past its rise along the band from the visor's
    knot_deg=82.9,          # end; the knot's centre azimuth: cap v6 (the lead's decision 3) the SLIDE KNOTS AT HER BAND
    knot_step=0.0,          # SILHOUETTES, seen edge-on (egmar3b's bulky rope masses, left rows 140-184 out to x 67, right
                            # rows 126-176 out to x 338), the buttons with them [M egmar3b through t27's camera:
                            # knot_fit_v6.py, rms 3.5 / 2.7 px over 27 / 27 rows; CAP_GDR §11]; the rise ends knot_step
                            # before the knot's front end. v5 hid them at 116 deg. The second forge (10-26): the fit's
                            # 16.8 mm read the ropes' tops at her two band silhouettes -3.2 / +4.2 px off hers (t27 gate
                            # 13's bar 4: her photo rolled ~1.4 deg on a symmetric cap); 17.2 centres them (~ +-3.7)
    knot_l=0.0163,          # the sliding knot: its sweep's axis between the end nodes (the sweep caps each end with its
                            # end radius), the barrel's height and outward depth, its back on the band. Cap v6: her knots
    knot_h=0.0295,          # are BULKIER than o03's (an officer's cap, 1:1: overall 1.14 x the pair long, 1.2 x tall):
    knot_w=0.0166,          # 1.66 x o03's ratios [M egmar3b through t27's camera, knot_fit_v6.py: the masses' outer edge
                            # per row; o03's size left them 6-12 px short]; v5 9.8 / 17.8 / 10.0. Cap v7 (the lead's
    knot_drop=0.0,          # decision 5, gate 12's rows 166-176) searched heights 29.5-35 mm, drops 0-5 mm, depths
                            # 16.6-18.6 and azimuths 80.9-84.9 deg [M egmar3b through t27's camera, tests/out/cap/v7/
                            # scratch/knot_fit_v7.py]: the right mass stays over the bar 5 whatever the knot (her right
                            # mass's three dark top rows 126-130, 15 px each: a 4.7 px floor no symmetric knot clears);
                            # its middle hung 2.5 mm under the pair's centre (knot_curve; left 3.0, right 5.1 px) the
                            # second v7 forge's bake FAILED: the bent axis fans the low's rings apart under the barrel,
                            # which falls 1.7 mm inside it there (0.3 unbent), and with the braid's lift the bake's
                            # search ran out of reach (a 467-texel miss cluster; scratch/knot_chord_v7.py,
                            # miss_where_v7.py; 1.0 mm still sank it 1.3 mm); 33 mm tall unbent (the third v7 forge:
                            # left 4.0, right 5.6) its bulk hid the cords' rise toward it and t27 gate 13's left rope top
                            # fell to 147.8 px against her 140 (bar 4): v6's height kept
    knot_gap=0.0191,        # the knot's centre to the button's: o03's 0.96 x the pair plus the bigger knot's extra half
                            # length [M o03; E]
    button_d=0.0126,        # the buttons: 0.76 x the pair [M o03 at 1:1]; the dome's height [E]
    button_h=0.0027,
    shank_d=0.0020,         # the split pin's shank under the head, through the band [E; C Runde Ecke 09697 "gekoernte
                            # Splintknoepfe"]: the cords' loop runs round it, the head clamps the loop [o03, o01]
    cockade_d=0.0264,       # [M egmar3b fit at size 57]; its centre over the seat plane [M egmar3b fit]
    cockade_y=0.0418,
    cockade_h=0.0019,       # its face's height over the band (CK_Z) [E]
)
REGIONS =('top', 'wall', 'band', 'visor_top', 'visor_under', 'visor_rim', 'cord', 'knot', 'button', 'cockade',
           'inside')
R_ = {n: i for i, n in enumerate(REGIONS)}
INNER_SHARE = 0.20          # the inside's texel density relative to the outside's (cap v5 0.20, v4 0.25: the longer cords'
                            # texels; the lining is seen only looking into the cap)
COCKADE_SHARE = 4.6         # the cockade's: about 13 px/mm at the cap's ~2.85, its emblem reading in close-ups (the
                            # hinge's rings 0.1-0.3 mm apart, the rye's grains 0.9 mm, the ribbon's gilt lines 0.2-0.3 mm)
WREATH_SHARE = 1.8          # the band's front island round the wreath: its veins and beads (0.3-0.5 mm; cap v5 1.8, v4 2.0:
                            # the beads and the midribs are the relief's own now, the veins texture)
KNOT_SHARE = 2.0            # the knots (stacked: one pair of islands): the braid's flat bundles of threads 0.5 mm apart
                            # [M o03: bundles of 5 threads (4-6), 2.4 mm wide] need 3.2 texels
PALETTE = ('crown', 'band', 'gold', 'visor')     # the runtime's four zones (masks B 0, 1/3, 2/3, 1)

MATERIAL = dict(
    # cap v5 (the lead's decision 3): the colours measured on SKYE'S photos under their own light (research/cap_gdr_
    # scripts/v5_front.py, CAP_REFERENCE §4): the white balance from egmar3b's white surround (clipped at 255 on all three
    # channels: already balanced, gains 1; images.jpg has no neutral, its beige lace only bounds it), each zone's LIT
    # MEDIAN (its pixels' upper half by luminance, linear). Linear albedo:
    #   the crown, egmar3b's greenish stone-grey (its lit median G/R 1.03-1.07, B/R 0.69-0.78; images.jpg's reads bluish,
    #   B/R 1.4, under its warm light and no neutral: not the GDR's steingrau, a grey with a green-olive cast), its
    #   luminance 0.095 between her shaded wall (0.051) and her lit top (0.146) [M]; cap v8 (the lead's decision 4: "its
    #   colour less olive (Neutral chroma ~5 at L* ~22 as hers, now 9)"): the blue deficit and the green excess halved
    #   (G/R 1.02, B/R 0.86; v5-v7 1.04 / 0.73 read 9.2 under the studio through Neutral against her 5.4 [M the v7 check's
    #   boxes])
    wool=(0.094, 0.096, 0.081),           # steingrau
    #   the band, her deep scarlet, sRGB G/R 0.18 (egmar3b's lit median 0.207, its shade 0.117, images.jpg 0.17-0.19;
    #   the lead's 0.14-0.21), R 0.60 (her lit band 0.70 against a white clipped at 255) [M]; v4 g02's (0.573, 0.050,
    #   0.018), sRGB G/R 0.32, read orange-red
    felt=(0.600, 0.0137, 0.0107),         # hochrot (the general's band and piping)
    # metals: base colour = F0, its HUE her lit medians': the cords MUSTARD gold (egmar3b G/R 0.714, B/R 0.19; images.jpg
    # 0.67 / 0.24) [M], the gilt (the wreath, the cockade, the buttons) RICH YELLOW, her wreath's lit median (G/R 0.69,
    # B/R 0.26; images.jpg 0.79 / 0.40) [M]; v4: (0.96, 0.70, 0.27) and gold's own F0 (1.0, 0.77, 0.31), read khaki and
    # champagne (the v4 check)
    cord_gold=(0.96, 0.685, 0.182), gilt=(1.0, 0.69, 0.26),
    tarnish=(0.36, 0.22, 0.08),           # the darkened gold in the twist valleys and the stamping's recesses [E]
    lacquer=(0.012, 0.012, 0.013),        # the visor's black [E linear 0.01-0.02]
    # the cockade's enamels, the close-up's medians (white background, linear) [M ref_colours.py]: the translucent red
    # over the pebbled base, the ribbon's red and yellow; its black [E: the photo's is the gilt's reflection]
    enamel=(0.325, 0.005, 0.012), ribbon_black=(0.020, 0.018, 0.016), ribbon_red=(0.517, 0.020, 0.019),
    ribbon_yellow=(0.774, 0.453, 0.0005),
    leather=(0.20, 0.11, 0.055),          # the sweatband [E brown]
    linen=(0.60, 0.56, 0.48),             # the lining [C linen; colour E]
    ink=(0.07, 0.06, 0.12),               # the lining's maker's stamp
    worn=(1.0, 0.86, 0.56),               # gold rubbed bright where fingers slide it (CAP_REFERENCE §5.3) [E]
    dust=(0.40, 0.36, 0.31),              # dust in the band's nap at its foot, where the cords rub (§5.5) [E]
    # roughness. Cap v7: the cords' gold bullion THREAD matte, rough at the macro scale (gold_rough 0.46; its fine fibre
    # glints the texture's: cord_fibre_*; v6's 0.30 read as polished metal, the v6 check). Cap v8 (the lead's decision 1:
    # "a SATIN stamped surface (no glossy melted gold)"): the wreath's gilt 0.30 with the die's stipple (leaf_stipple,
    # 0.012 mm at 0.5 mm: height_at) breaking each highlight; v7's 0.26 on smooth pillows read as melted gold, the first
    # v8 forge's 0.40 spread the sweep's light over the leaves (the gilt's L* median 66 through Neutral against her 55)
    wool_rough=0.80, shine_rough=0.18, felt_rough=0.90, lacquer_rough=0.06, under_rough=0.22, scratch_rough=0.14,
    grip_rough=0.20, gold_rough=0.55, wreath_rough=0.30, gilt_rough=0.20, enamel_rough=0.05, leather_rough=0.52,
    linen_rough=0.84, leaf_stipple=0.000012,
    # cap v8 (the lead's decision 4: "a fine, regular DIAGONAL TWILL ... at her strength"): the wales 1.1 mm apart (3.4
    # texels at the cap's ~3.1 px/mm: resolved; the cloth's own 0.7 mm [M o04, o03] fell under the texel floor and v5-v7
    # showed no twill at all), their relief and their tone (twill_col each way) [the strength M egmar3b's wall, 2.1-2.7 L*
    # rms high-passed, research/cap_gdr_scripts/v6_measure.py; t27 reads ours through her camera], the seams'
    # topstitching stitch_off either side of each seam [E]
    twill=0.0011, twill_amp=0.000060, twill_col=0.20, stitch_off=0.0020,   # (the first v8 forge's 0.04 mm / 0.12
    #                                     read 1.5 L* rms through Neutral against her 2.4)
    # cap v7 (the lead's decision 6: "the twill an irregular wool weave at her strength (2.4 L* rms), not carbon-fibre
    # stripes and no chevrons on the roll"): the worsted's visible GRAIN an IRREGULAR weave (twill_grain): yarn-scale
    # noise in solid (3D) cloth space, so no frame meets another on the roll; its yarn scale, its relief and its tone each
    # way [the contrast M egmar3b's crown wall, 2.1-2.7 L* rms high-passed, research/cap_gdr_scripts/v6_measure.py; t27
    # reads ours through her camera]. v6: cos streaks 1.4 mm apart in two frames (+-18 %, 0.045 mm): carbon fibre and
    # chevrons where the top's frame met the wall's
    twill_grain=0.0012, twill_grain_amp=0.000020, twill_grain_col=0.25,   # cap v8: a trace under the regular wales (v7
    #                                     0.06 mm / 0.90 alone: mottled fleece; the first v7 forge's 0.55 / 0.04 read 1.2)
    # cap v6 (the lead's decision 2): the wreath's VELVET backing: its albedo a share of the band's felt, its sheen
    # (masks R) and its roughness [the share M egmar3b: L* 44-46 beside the band's 48-49 under the same light; the
    # velvet's response E]; cap v7 (decision 3) its rolled edge darkened by velvet_edge over WREATH_BACK_ROLL
    # cap v8 (the lead's decision 6: "THE BACKING a richer crimson as hers (Neutral chroma ~64 in the V, now 54)"): its
    # green and blue a share velvet_gb of the band's (a deeper dyed pile, its red the band's share velvet)
    velvet_gb=0.45,
    # cap v8 (gate 20 over the whole velvet region): its red share 0.50 (the v8 forge at 0.565 read 5.6 L* under the band
    # beside it through Neutral, hers 7.4)
    velvet=0.50, velvet_fuzz=0.25, velvet_rough=0.97, velvet_edge=0.20,  # (cap v7: v6 0.62; the first v7 forge read
    #                                     the backing barely under the band, its roll the main part seen: darker, evener;
    #                                     0.55 put the V over the cockade at 21.7 L* in the crown's shadow, hers 25.9,
    #                                     0.58 the backing 2.4 under the band in her boxes, hers 3.9)
    # cap v7 (the lead's decision 4): the cords' FIBRES, fine grooves along the threads at cord_fibre_deg off the cord's
    # axis [M egmar3b: her stripes 5-15 deg off the axis, the v6 check's structure tensor], cord_fibres round the cord (an
    # integer: the pattern closes round the tube), their relief
    # (the second v7 forge's 0.018 mm x 30 left each ply's crest one smooth polished highlight at her camera, where her
    # cords read as matte thread: 0.05 mm x 24, 1.1 mm apart, break it into fibre glints; the gold rougher, gold_rough
    # 0.52 (v6 0.46 in the material, 0.38 read); 0.62 spread the key's highlight over the lit stretch: the ropes' L*
    # median 67.6 through Neutral against her 60.8, t27 (8)'s bar 4)
    cord_fibre_amp=0.000050, cord_fibres=24, cord_fibre_deg=10.0,
    # cap v7 (the lead's decision 7): the enamel's pebbled base in the NORMAL map (each pebble a dome this high: crisp
    # glints in the glossy ruby; v6's 0.012 mm read as a faint mottle, the v6 check)
    pebble_amp=0.000070,
    felt_amp=0.00004, vein_amp=0.00008, ply_amp=0.00003, grain=0.0003,   # (cap v5: the leaves' veins 2x v4's)
    cloud=0.04,                           # the cloth's dye density cloud, ln L amplitude
    seed=57,
)


# ----------------------------------------------------------------------------------------------------- dimensions
def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)


def dims(spec=SPEC):
    """the opening's semi-axes (Ramanujan's perimeter at the oval's ratio), the band's outer face, the crown edge's
    piping centreline, the visor's root azimuth and its end width"""
    C, q = spec['head_circ'], spec['oval']
    h = ((q - 1.0) / (q + 1.0)) ** 2
    rx_o = C / (np.pi * (1.0 + q) * (1.0 + 3.0 * h / (10.0 + np.sqrt(4.0 - 3.0 * h))))
    rz_o = q * rx_o
    bt = spec['band_t']
    rp = 0.5 * spec['pipe_d']
    d = dict(rx_o=float(rx_o), rz_o=float(rz_o), rx_b=float(rx_o + bt), rz_b=float(rz_o + bt), rp=rp,
             rpb=0.5 * spec.get('band_pipe_d', spec['pipe_d']),
             Rx=0.5 * spec['crown_w'] - rp, Rz=0.5 * spec['crown_d'] - rp, bh=spec['band_h'])
    d['phi_e'] = float(np.arccos(spec['visor_end_z'] / d['rz_b']))
    nx, nz = np.sin(d['phi_e']) / d['rx_b'], np.cos(d['phi_e']) / d['rz_b']
    ln = np.hypot(nx, nz)
    d['L_end'] = float((0.5 * spec['visor_w'] - d['rx_b'] * np.sin(d['phi_e'])) / (nx / ln))
    d['xc'] = 0.5 * spec['visor_w']                      # the visor's corners in plan (its widest points)
    d['zc'] = float(spec['visor_end_z'] + nz / ln * d['L_end'])
    return d


def rise_w(c, k):
    """the saddle's weight over c = max(0, +-cos phi): c^2 (1 + k (1 - c)). k 0 is cap v4's cos^2 law, whose crown edge
    meets the front at a slope of 2 (rise_front - rise_side) / Rz in profile (35 deg: the pointed PROW the v4 check
    saw from the side); k 2 is the smoothstep 3 c^2 - 2 c^3, level in profile at the front and at the sides alike (a
    ROUNDED front, as the GDR crowns of o01 and g02 show it from the side); always level where it meets the sides"""
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    return c * c * (1.0 + k * (1.0 - c))


def rise(phi, spec=SPEC):
    """the crown edge above the band's top at azimuth phi (0 = the front): the saddle, rise_side at the sides, rising
    to rise_front at the front and to rise_back at the back by rise_w (cap v5: the sides, the back and the rounding
    fitted to egmar3b's outline through its camera, research/CAP_GDR.md §10; v4: rise_back = rise_side, k 0)"""
    c = np.cos(np.asarray(phi, np.float64))
    k = spec.get('rise_round', 0.0)
    rb = spec.get('rise_back', spec['rise_side'])
    return (spec['rise_side'] + (spec['rise_front'] - spec['rise_side']) * rise_w(np.maximum(c, 0.0), k)
            + (rb - spec['rise_side']) * rise_w(np.maximum(-c, 0.0), k))


_ARC = {}


def band_arc(spec=SPEC):
    """the band's outer face: azimuth -> arc length from the front centre (+ toward +X), a dense table"""
    key = (spec['head_circ'], spec['oval'], spec['band_t'])
    if key not in _ARC:
        d = dims(spec)
        ph = np.linspace(-np.pi, np.pi, 8193)
        ds = np.hypot(d['rx_b'] * np.cos(ph), d['rz_b'] * np.sin(ph))
        s = np.concatenate([[0.0], np.cumsum(0.5 * (ds[1:] + ds[:-1]) * np.diff(ph))])
        _ARC[key] = (ph, s - np.interp(0.0, ph, s))
    return _ARC[key]


def u_to_phi(u, spec=SPEC):
    ph, s = band_arc(spec)
    return np.interp(u, s, ph)


def phi_to_u(phi, spec=SPEC):
    """the band's arc from the front centre at azimuths phi, PERIODIC: phi wrapped into (-pi, pi] first. Cap v6's first
    forge (10-26) passed band_top the crown patch's and the low's azimuths over 0 .. 2 pi, and np.interp clamped every
    phi past pi to the back: the raised seam stood on one side of the front centre only (the band piping's sweep, the
    band's rows, the wall's foot and the low's rings; t27 gate 17 read +7 .. +10 px on that side)"""
    ph, s = band_arc(spec)
    return np.interp(np.angle(np.exp(1j * np.asarray(phi, np.float64))), ph, s)


def band_frame(phi, y, w=0.0, spec=SPEC):
    """the band's outer face at azimuth phi and height y, pushed w along its outward normal: points P, normals N
    (horizontal, outward) and tangents T (toward increasing phi), each (..., 3)"""
    d = dims(spec)
    phi, y, w = np.broadcast_arrays(np.asarray(phi, np.float64), np.asarray(y, np.float64),
                                    np.asarray(w, np.float64))
    nx, nz = np.sin(phi) / d['rx_b'], np.cos(phi) / d['rz_b']
    ln = np.hypot(nx, nz)
    nx, nz = nx / ln, nz / ln
    z0 = np.zeros_like(phi)
    P = np.stack([d['rx_b'] * np.sin(phi) + nx * w, y, d['rz_b'] * np.cos(phi) + nz * w], -1)
    return P, np.stack([nx, z0, nz], -1), np.stack([nz, z0, -nx], -1)


# ---------------------------------------------------------------------------------------------------- the crown
def seam_bump(u, spec=SPEC):
    """cap v6 (the lead's decision 6): the band's top SEAM's rise at band arc u (from the front centre): seam_rise over
    |u| < seam_flat, eased to nothing by seam_edge (egmar3b's crown-to-band boundary through t27's camera,
    research/CAP_GDR.md §11)"""
    u = np.abs(np.asarray(u, np.float64))
    a = spec.get('seam_rise', 0.0)
    if a == 0.0:
        return np.zeros_like(u)
    return a * _smoothstep(spec['seam_edge'], spec['seam_flat'], u)


def band_top(phi, spec=SPEC):
    """the band's top seam over the seat plane at azimuth phi (cap v6: raised at the front centre by seam_bump; v5 a
    level band_h)"""
    return spec['band_h'] + seam_bump(phi_to_u(phi, spec), spec)


def roll_geom(phi, spec=SPEC):
    """cap v6 (the lead's decision 1): the crown's ROLLED TOP EDGE at azimuth phi, in the meridian half-plane about the
    piping's centre E (out along the radial, up): its circle's centre (dx, dy) and its OUTER radius rho, from its
    overhang O beyond the piping's outer edge and its top's height H over E (SPEC roll_r, roll_out, roll_h: the sides
    and the front, blended by max(0, cos phi)^2; the back takes the sides'). Returns dx, dy, rho, O, H"""
    phi = np.asarray(phi, np.float64)
    w = np.maximum(np.cos(phi), 0.0) ** 2
    (rs, rf), (os_, of), (hs, hf) = spec['roll_r'], spec['roll_out'], spec['roll_h']
    rho = rs + (rf - rs) * w
    O = os_ + (of - os_) * w
    H = hs + (hf - hs) * w
    return O + 0.5 * spec['pipe_d'] - rho, H - rho, rho, O, H


def pipe_centre(phi, spec=SPEC):
    """the crown piping's centreline E at azimuth phi (the wall's seam under the roll; v5's crown edge): the piping's
    semi-axes (Rx, Rz) and its rise over band_h"""
    d = dims(spec)
    phi = np.asarray(phi, np.float64)
    return np.stack([d['Rx'] * np.sin(phi), spec['band_h'] + rise(phi, spec), d['Rz'] * np.cos(phi)], -1)


_RIM = {}
_RIM_N = 4097


def _rim_key(spec):
    return tuple(str(spec.get(k)) for k in ('rise_side', 'rise_front', 'rise_back', 'rise_round', 'roll_r', 'roll_out',
                                             'roll_h', 'crown_w', 'crown_d', 'pipe_d', 'cloth_t', 'sag', 'band_h',
                                             'head_circ', 'oval', 'band_t', 'top_dome'))


def top_dome(rho, phi, R_rim, spec=SPEC):
    """cap v6: the top's FRONT DOME over the harmonic membrane at rho (1 the rim), azimuth phi, the rim's radius R_rim
    there: lift max(0, cos phi)^2 rho^2 (1 - exp(-(1 - rho) R_rim / reach)) (SPEC top_dome), and its d / d rho"""
    lift, reach = spec.get('top_dome', (0.0, 0.01))
    rho = np.asarray(rho, np.float64)
    w = np.maximum(np.cos(phi), 0.0) ** 2
    e = np.exp(-np.clip(1.0 - rho, 0.0, None) * R_rim / reach)
    return lift * w * rho * rho * (1.0 - e), lift * w * (2.0 * rho * (1.0 - e) - rho * rho * e * R_rim / reach)


def crown_rim(spec=SPEC, n_harm=128):
    """cap v6: the crown's ROLL and its TOP's rim on a dense table over phi (-pi .. pi). In the meridian half-plane
    about E (out, up): the cloth's mid-surface leaves the piping's seam along the TANGENT to the roll's mid circle
    (centre (dx, dy), radius rm = rho - cloth_t / 2) on its outer side (direction dirt, length tl; the tangent point at
    th1 about the centre), wraps the roll over its outer side and its top to th_e = 90 deg - beta, where it leaves the
    roll TANGENT to the top's membrane (beta the membrane's own slope going inward: up at the sides and back, down at the
    high front; no crease), at the rim's radial offset dr from E and height g over band_h. The membrane is the harmonic
    extension of g (its Fourier cosine coefficients A) less the sag; beta and g are a fixed point (three passes)"""
    key = _rim_key(spec)
    if key in _RIM:
        return _RIM[key]
    d = dims(spec)
    ph = np.linspace(-np.pi, np.pi, _RIM_N)
    dx, dy, rho, O, H = roll_geom(ph, spec)
    rm = rho - 0.5 * spec['cloth_t']
    cl = np.hypot(dx, dy)
    assert np.all(cl > rm + 1e-5), 'crown_rim: the piping centre inside the roll'
    dirt = np.arctan2(dy, dx) - np.arcsin(rm / cl)       # the outer tangent from E (the circle lies up from E)
    tl = np.sqrt(cl * cl - rm * rm)
    th1 = np.arctan2(tl * np.sin(dirt) - dy, tl * np.cos(dirt) - dx)
    rs = rise(ph, spec)
    pg = np.linspace(-np.pi, np.pi, 40001)
    k = np.arange(n_harm + 1)
    beta = np.zeros_like(ph)
    for _ in range(3):
        th_e = 0.5 * np.pi - beta
        dr = dx + rm * np.cos(th_e)
        g = rs + dy + rm * np.sin(th_e)
        gg = np.interp(pg, ph, g)
        A = np.array([np.trapezoid(gg, pg) / (2.0 * np.pi)] +
                     [np.trapezoid(gg * np.cos(j * pg), pg) / np.pi for j in range(1, n_harm + 1)])
        cosk = np.cos(np.outer(ph, k))
        s1 = cosk @ A
        R_rim = np.hypot((d['Rx'] + dr) * np.sin(ph), (d['Rz'] + dr) * np.cos(ph))
        # d h / d rho at rho 1: the harmonic membrane's, the sag's and the front dome's
        dh = cosk @ (k * A) + 2.0 * (g - s1) + 2.0 * spec['sag'] * (1.0 - 0.5 * np.cos(ph)) + \
            top_dome(np.ones_like(ph), ph, R_rim, spec)[1]
        beta = np.arctan(-dh / R_rim)
    out = dict(ph=ph, dx=dx, dy=dy, rho=rho, rm=rm, dirt=dirt, tl=tl, th1=th1, th_e=th_e, dr=dr, g=g, A=A, beta=beta,
               O=O, H=H, len=tl + rm * (th_e - th1))
    _RIM[key] = out
    return out


def _rim_at(phi, name, spec=SPEC):
    """a crown_rim table's value at azimuths phi (periodic, linear)"""
    T = crown_rim(spec)
    p = np.angle(np.exp(1j * np.asarray(phi, np.float64)))
    return np.interp(p, T['ph'], T[name])


def harm_rise(rho, phi, spec=SPEC):
    """the harmonic extension of the top's rim height over band_h (crown_rim's g: the roll's top where the membrane
    leaves it) into the unit disc, exact on its rim (the truncation's residue folded back in by rho^2). Cap v5 extended
    the piping's own rise: its top met the piping, and the back piping drew the top silhouette"""
    T = crown_rim(spec)
    A = T['A']
    rho, phi = np.broadcast_arrays(np.asarray(rho, np.float64), np.asarray(phi, np.float64))
    r, p = rho.ravel(), phi.ravel()
    k = np.arange(len(A))
    out = np.empty(len(r))
    for a in range(0, len(r), 65536):
        rr, pp = r[a:a + 65536], p[a:a + 65536]
        s = (A[None, :] * rr[:, None] ** k[None, :] * np.cos(np.outer(pp, k))).sum(1)
        s1 = (A[None, :] * np.cos(np.outer(pp, k))).sum(1)
        out[a:a + 65536] = s + rr * rr * (_rim_at(pp, 'g', spec) - s1)
    return out.reshape(rho.shape)


def top_height(rho, phi, spec=SPEC):
    """the top's mid-surface height at rho (1 = its rim, where it leaves the roll) and azimuth phi: the harmonic
    membrane over the rolled rim, sagging toward the back, domed behind the front roll (top_dome)"""
    rho, phi = np.broadcast_arrays(np.asarray(rho, np.float64), np.asarray(phi, np.float64))
    d = dims(spec)
    dr = _rim_at(phi, 'dr', spec)
    R_rim = np.hypot((d['Rx'] + dr) * np.sin(phi), (d['Rz'] + dr) * np.cos(phi))
    return (spec['band_h'] + harm_rise(rho, phi, spec)
            - spec['sag'] * (1.0 - rho * rho) * (1.0 - 0.5 * rho * np.cos(phi)) + top_dome(rho, phi, R_rim, spec)[0])


def top_point(rho, phi, spec=SPEC):
    """the top's mid-surface: its rim (rho 1) the roll's leaving line, (Rx + dr, Rz + dr) about the axis"""
    d = dims(spec)
    rho, phi = np.broadcast_arrays(np.asarray(rho, np.float64), np.asarray(phi, np.float64))
    dr = _rim_at(phi, 'dr', spec)
    return np.stack([(d['Rx'] + dr) * rho * np.sin(phi), top_height(rho, phi, spec), (d['Rz'] + dr) * rho * np.cos(phi)],
                    -1)


def roll_local(s, phi, spec=SPEC):
    """the roll's mid-surface in the meridian half-plane about E at s (0 the piping's seam, 1 the top's rim; by arc
    length): along the tangent, then round the roll. Returns (delta out, h up) (..., 2)"""
    s, phi = np.broadcast_arrays(np.asarray(s, np.float64), np.asarray(phi, np.float64))
    g = lambda nm: _rim_at(phi, nm, spec)
    tl, rm, th1, th_e, dirt, dx, dy = (g(n) for n in ('tl', 'rm', 'th1', 'th_e', 'dirt', 'dx', 'dy'))
    L = tl + rm * (th_e - th1)
    a = s * L
    on_t = a <= tl
    th = th1 + (a - tl) / np.maximum(rm, 1e-9)
    de = np.where(on_t, a * np.cos(dirt), dx + rm * np.cos(th))
    h = np.where(on_t, a * np.sin(dirt), dy + rm * np.sin(th))
    return np.stack([de, h], -1)


def _local_to_world(loc, phi, spec=SPEC):
    """meridian half-plane offsets about E (delta out along the piping ellipse's radial, h up) -> cap space"""
    d = dims(spec)
    phi = np.asarray(phi, np.float64)
    de, h = loc[..., 0], loc[..., 1]
    return np.stack([(d['Rx'] + de) * np.sin(phi), spec['band_h'] + rise(phi, spec) + h, (d['Rz'] + de) * np.cos(phi)],
                    -1)


def roll_point(s, phi, spec=SPEC):
    """the roll's mid-surface point at s (0 the seam at E, 1 the top's rim) and azimuth phi"""
    return _local_to_world(roll_local(s, phi, spec), phi, spec)


def roll_normal(s, phi, spec=SPEC):
    """the roll's mid-surface outward normal"""
    s = np.clip(np.asarray(s, np.float64), 1e-4, 1.0 - 1e-4)
    n, _, _ = _fd_normal(lambda a, b: roll_point(a, b, spec), s, np.asarray(phi, np.float64))
    loc = roll_local(s, phi, spec)
    c = np.stack([_rim_at(phi, 'dx', spec), _rim_at(phi, 'dy', spec)], -1)
    out = _local_to_world(loc + 0.001 * _unit(loc - c), phi, spec) - roll_point(s, phi, spec)
    return n * np.sign((n * out).sum(-1, keepdims=True) + 1e-12)


def _wall_ax(spec):
    d = dims(spec)
    o = spec['band_t'] - 0.5 * spec['cloth_t']
    return d['rx_o'] + o, d['rz_o'] + o, d['Rx'], d['Rz']


def wall_point(t, phi, spec=SPEC):
    """the wall's mid-surface: from the band's top seam (t = 0; cap v6 band_top, raised at the front centre) to the
    piping's centreline under the roll (t = 1), the meridian a quadratic Bezier whose control point (radial share,
    height share) runs from SPEC['flare'][0] at the front to SPEC['flare'][1] at the sides and back by max(0, cos phi)^2
    (the saddle's own weight): at the front the cloth is taut over the stiffener, nearly straight; at the sides and back
    it is a ROLL, leaving the band almost level and turning up into the piping (o05, both sides; o01). Forges 1-5 drew a
    trumpet, steep off the band and flat into the piping, the mirror of every photo: the crown read as a flange on a
    stalk (check 10-21, sil_proto_meridian.png)"""
    t, phi = np.broadcast_arrays(np.asarray(t, np.float64), np.asarray(phi, np.float64))
    ax0, az0, ax1, az1 = _wall_ax(spec)
    (fa0, fb0), (fa1, fb1) = spec['flare']
    w = np.maximum(np.cos(phi), 0.0) ** 2
    fa = fa1 + (fa0 - fa1) * w
    fb = fb1 + (fb0 - fb1) * w
    a = 2.0 * (1.0 - t) * t * fa + t * t
    b = 2.0 * (1.0 - t) * t * fb + t * t
    ax = ax0 + (ax1 - ax0) * a
    az = az0 + (az1 - az0) * a
    y0 = band_top(phi, spec)
    y1 = spec['band_h'] + rise(phi, spec)
    return np.stack([ax * np.sin(phi), y0 + (y1 - y0) * b, az * np.cos(phi)], -1)


def _fd_normal(f, a, b, ea=1e-5, eb=1e-5):
    """a surface f(a, b) -> (..., 3): its unit normal cross(f_a, f_b) by central differences"""
    fa = (f(a + ea, b) - f(a - ea, b)) / (2 * ea)
    fb = (f(a, b + eb) - f(a, b - eb)) / (2 * eb)
    return _unit(np.cross(fa, fb)), fa, fb


def top_normal(rho, phi, spec=SPEC):
    """the top's mid-surface outward (upward) normal"""
    rho = np.clip(np.asarray(rho, np.float64), 2e-5, None)
    n, _, _ = _fd_normal(lambda r, p: top_point(r, p, spec), rho, np.asarray(phi, np.float64))
    return n * np.sign(n[..., 1:2] + 1e-12)


def wall_normal(t, phi, spec=SPEC):
    """the wall's mid-surface outward normal (away from the head: outward and down)"""
    t = np.asarray(t, np.float64)
    phi = np.asarray(phi, np.float64)
    n, _, _ = _fd_normal(lambda a, b: wall_point(a, b, spec), t, phi)
    rad = np.stack([np.sin(phi), np.zeros_like(phi), np.cos(phi)], -1)
    return n * np.sign((n * rad).sum(-1, keepdims=True) + 1e-12)


def crown_patch(spec=SPEC, n_phi=720):
    """the cloth's mid-surface as one sheet for the SHELL: the band (its mid at half its wall, the sweatband's top a
    step on the inside), the band top's transition into the cloth, the flared wall, the crease at the crown edge and
    the top in to its centre; facets ~0.5 mm on the band and the wall's flare, ~1 mm on the top (a shell thinner
    than its facets keeps them: the octopus web's lesson; here every dihedral stays under 1.3 deg). Returns V, F and
    the per-vertex half-thickness"""
    d = dims(spec)
    bt, st, ct, bh, sh = spec['band_t'], spec['sweat_t'], spec['cloth_t'], spec['band_h'], spec['sweat_h']
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    rows, half = [], []
    # cap v6: the band's rows scaled to its top seam per azimuth (raised at the front centre, band_top), its foot level
    yt = band_top(phi, spec)

    def ring(o, y):
        return np.column_stack([(d['rx_o'] + o) * np.sin(phi), y, (d['rz_o'] + o) * np.cos(phi)])
    for y in np.arange(0.5 * bt, bh - 0.0015 + 1e-9, 0.0005):
        # the sweatband's top: a step on the inside eased over 6 mm (over 0.6 mm the shell's slanted mid-surface cut a
        # 0.08 mm groove round the band's OUTSIDE at sh: cap v4's first forge showed it as a line round the tall band);
        # level (by each row's own height) where the rows rise with the seam
        yy = 0.5 * bt + (y - 0.5 * bt) * (yt - 0.0015 - 0.5 * bt) / (bh - 0.0015 - 0.5 * bt)
        r = _smoothstep(sh - 0.003, sh + 0.003, yy)
        rows.append(ring(0.5 * bt + 0.5 * st * r, yy))
        half.append(0.5 * bt - 0.5 * st * r)
    for y in np.linspace(bh - 0.0015, bh, 7)[1:]:
        r = float(_smoothstep(bh - 0.0015, bh, y))
        o = 0.5 * (bt + st) + (bt - 0.5 * ct - 0.5 * (bt + st)) * r
        rows.append(ring(o, yt - (bh - y)))
        half.append(np.full(n_phi, 0.5 * (bt - st) + (0.5 * ct - 0.5 * (bt - st)) * r))
    # the wall: t uniform in the front meridian's arc length (the longest), ~0.4 mm
    tt = np.linspace(0.0, 1.0, 2001)
    Wm = wall_point(tt, np.zeros_like(tt), spec)
    sw = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Wm, axis=0), axis=1))])
    for t in np.interp(np.linspace(0.0, sw[-1], int(np.ceil(sw[-1] / 0.0004)) + 1), sw, tt)[1:]:
        rows.append(wall_point(np.full(n_phi, t), phi, spec))
        half.append(np.full(n_phi, 0.5 * ct))
    # cap v6: the ROLL, from the piping's seam (the wall's end) along the tangent and round the rolled edge to the top's
    # rim, 0.3 mm steps (its 3-4 mm round carries ~35 rows: every dihedral under 1 deg)
    Lr = float(crown_rim(spec)['len'].max())
    for s in np.linspace(0.0, 1.0, int(np.ceil(Lr / 0.0003)) + 1)[1:]:
        rows.append(roll_point(np.full(n_phi, s), phi, spec))
        half.append(np.full(n_phi, 0.5 * ct))
    # the top: rho from the rim inward, 0.3 mm steps at the rim growing to 1.2 mm
    rho, r = [], 1.0
    while r > 0.012:
        r -= (0.0003 + 0.0009 * _smoothstep(0.98, 0.88, r)) / d['Rz']
        rho.append(r)
    for r in rho:
        rows.append(top_point(np.full(n_phi, r), phi, spec))
        half.append(np.full(n_phi, 0.5 * ct))
    V = np.concatenate(rows + [top_point(np.array([0.0]), np.array([0.0]), spec)])
    H = np.concatenate(half + [np.array([0.5 * ct])])
    nr = len(rows)
    i = np.arange(nr - 1)[:, None]
    j = np.arange(n_phi)[None, :]
    j1 = (j + 1) % n_phi
    a, b, c, e = i * n_phi + j, i * n_phi + j1, (i + 1) * n_phi + j1, (i + 1) * n_phi + j
    F = [np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, e], -1).reshape(-1, 3)]
    last = (nr - 1) * n_phi
    F.append(np.column_stack([last + np.arange(n_phi), last + (np.arange(n_phi) + 1) % n_phi,
                              np.full(n_phi, len(V) - 1)]))
    return V, np.concatenate(F), H


LINING_T = 0.0004           # cap v6: the lining's top panel (satin on its interlining), its thickness [E]


def lining_patch(spec=SPEC, n_phi=720, n_s=24):
    """cap v6 (the first forge's bake gate, 10-26): the LINING's top panel where it spans the roll's pocket, a ruled
    strip per azimuth from the wall's inner face just under the seam (the low's lining ring 'ie') to the top's inner
    face (its ring 'ic'), as a real lining is sewn into the crown's seam and stretched under the top. Without it the
    low's lining strip between those rings crossed the mouth of the roll's pocket in the air, 4-8 mm from any surface
    of the block-out, and the bake missed 2.7 % of its island (inside #18). Its mid-surface passes through the rings'
    analytic points, so the low's strip lies inside it. Returns V, F, H for sdf.Program.shell (H the half thickness)"""
    st = {s[0]: s for s in crown_stations(spec)}
    half = 0.5 * spec['cloth_t']
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    t_e, r_c = np.full(n_phi, st['ie'][2]), np.full(n_phi, st['ic'][2])
    A = wall_point(t_e, phi, spec) - half * wall_normal(t_e, phi, spec)
    B = top_point(r_c, phi, spec) - half * top_normal(r_c, phi, spec)
    s = np.linspace(0.0, 1.0, n_s)
    V = (A[None, :, :] + s[:, None, None] * (B - A)[None, :, :]).reshape(-1, 3)
    i = np.arange(n_s - 1)[:, None]
    j = np.arange(n_phi)[None, :]
    a, b = i * n_phi + j, i * n_phi + (j + 1) % n_phi
    c, e = a + n_phi, b + n_phi
    F = np.concatenate([np.stack([a, b, e], -1).reshape(-1, 3), np.stack([a, e, c], -1).reshape(-1, 3)])
    return V, F, np.full(len(V), 0.5 * LINING_T)


# ----------------------------------------------------------------------------------------------------- the visor
def visor_outline(s, spec=SPEC):
    """the visor's outer edge in plan at s in [-1, 1]: a superellipse arc (exponent visor_round) from corner to corner
    (its widest points visor_w apart, visor_end_z in front of the opening's widest line) through the tip visor_d in
    front of the band: 172, 45.4 and 38 mm, the outline 2.0 [M egmar3b fit, CAP_REFERENCE §3.0, §3.5]"""
    d = dims(spec)
    n = spec['visor_round']
    th = np.asarray(s, np.float64) * (0.5 * np.pi)
    D = d['rz_b'] + spec['visor_d'] - d['zc']
    return (d['xc'] * np.sign(np.sin(th)) * np.abs(np.sin(th)) ** (2.0 / n),
            d['zc'] + D * np.abs(np.cos(th)) ** (2.0 / n))


def visor_s_arc(n, spec=SPEC, curv=0.0):
    """n values of s in [-1, 1] at equal arc length along the visor's outer edge (spaced by s itself, the
    superellipse put 24 mm chords at the front: the low's silhouette a polygon there, forge 10-21); curv > 0 weights
    the arc by 1 + curv sqrt(kappa / its mean) (a chord's sag goes as its length squared times the curvature: the
    corners, where the outline turns hardest, take the columns the gently curved front can spare)"""
    s = np.linspace(-1.0, 1.0, 4001)
    x, z = visor_outline(s, spec)
    seg = np.hypot(np.diff(x), np.diff(z))
    w = seg
    if curv > 0.0:
        th = np.unwrap(np.arctan2(np.diff(z), np.diff(x)))
        k = np.abs(np.gradient(th)) / np.maximum(seg, 1e-12)
        k = np.convolve(k, np.ones(41) / 41.0, mode='same')
        w = seg * (1.0 + curv * np.sqrt(k / k.mean()))
    a = np.concatenate([[0.0], np.cumsum(w)])
    return np.interp(np.linspace(0.0, a[-1], n), a, s)


VISOR_COLS = 35             # the visor grids' columns (34 segments along the edge, by visor_s_arc's curvature weight; cap v3
                            # 35 for 33 with the outer row smoothed (visor_columns): the rim strip's sections turn 7.8 deg at
                            # most, 4.4 at the corners, against 9.2 and 5.9; 37 put the cap at 6060 triangles)
VISOR_CURV = 1.0            # VISOR_CURV: cap v2, against forges 1-6's 24 at equal arc length, whose 12 mm rim segments
                            # showed as facets on the visor's rim at 28-50 mm framing)
VISOR_ROWS = np.array([0.0, 0.18, 0.48, 0.78, 1.0])    # the grids' rows from the buried root out (the drooping plate's
                            # chord sag across a row under 0.3 mm; forges 1-6 carried five quad rows)


def visor_spoke(s, spec=SPEC):
    """the visor's spoke at s: its root on the band's face (azimuth s phi_e), its plan direction to the outline and
    its plan length"""
    d = dims(spec)
    s = np.asarray(s, np.float64)
    P0, N0, _ = band_frame(s * d['phi_e'], 0.0, 0.0, spec)
    x, z = visor_outline(s, spec)
    dx, dz = x - P0[..., 0], z - P0[..., 2]
    L = np.hypot(dx, dz)
    return P0, np.stack([dx / L, np.zeros_like(L), dz / L], -1), L


def visor_L(s, spec=SPEC):
    """the visor's plan depth along its spoke at s (60 mm at the centre, 10.8 at the ends)"""
    return visor_spoke(s, spec)[2]


def visor_drop(xi, spec=SPEC):
    """the visor's fall below its root at plan distance xi from the band's face: the slope turns from droop[0] at the
    root to droop[1] at the centre's tip (mean ~40 deg); inside the band (xi < 0) it continues straight"""
    a0, a1 = np.radians(spec['droop'][0]), np.radians(spec['droop'][1])
    k = (a1 - a0) / spec['visor_d']
    xi = np.asarray(xi, np.float64)
    pos = np.log(np.cos(a0) / np.cos(a0 + k * np.clip(xi, 0.0, None))) / k
    return np.where(xi >= 0.0, pos, xi * np.tan(a0))


def visor_slope(xi, spec=SPEC):
    a0, a1 = np.radians(spec['droop'][0]), np.radians(spec['droop'][1])
    return a0 + (a1 - a0) / spec['visor_d'] * np.clip(np.asarray(xi, np.float64), 0.0, None)


def visor_half(s, xi, spec=SPEC):
    """the visor's half-thickness: 1.0 mm, 1.25 over its last 4 mm"""
    L = visor_L(s, spec)
    return 0.5 * spec['visor_t'] + 0.5 * (spec['rim_t'] - spec['visor_t']) * _smoothstep(L - 0.004, L - 0.001, xi)


def visor_mid(s, xi, spec=SPEC):
    """the visor's mid-surface at s (across) and xi (plan distance from the band's face along its spoke); its top
    surface leaves the band's face at SPEC['visor_y']"""
    s, xi = np.broadcast_arrays(np.asarray(s, np.float64), np.asarray(xi, np.float64))
    P0, D, _ = visor_spoke(s, spec)
    a0 = np.radians(spec['droop'][0])
    y0 = spec['visor_y'] - 0.5 * spec['visor_t'] / np.cos(a0)
    P = P0 + D * xi[..., None]
    P[..., 1] = y0 - visor_drop(xi, spec)
    return P


def visor_normal(s, xi, spec=SPEC):
    """the visor's mid-surface upward normal"""
    n, _, _ = _fd_normal(lambda a, b: visor_mid(a, b, spec), np.asarray(s, np.float64), np.asarray(xi, np.float64))
    return n * np.sign(n[..., 1:2] + 1e-12)


def visor_top(s, xi, spec=SPEC, lift=0.0):
    """a point on the visor's top surface (lift above it) and its normal"""
    n = visor_normal(s, xi, spec)
    return visor_mid(s, xi, spec) + n * (visor_half(s, xi, spec) + lift)[..., None], n


def visor_patch(spec=SPEC, n_s=361, n_xi=141):
    """the visor's mid-surface as a sheet for the SHELL (its boundary rounds by its half-thickness), from its root
    buried in the band to its edge"""
    s = visor_s_arc(n_s, spec)
    tt = np.linspace(0.0, 1.0, n_xi)
    S, T = np.meshgrid(s, tt, indexing='ij')
    L = visor_L(S, spec)
    XI = -spec['visor_root'] + (L + spec['visor_root']) * T
    V = visor_mid(S, XI, spec).reshape(-1, 3)
    H = visor_half(S, XI, spec).reshape(-1)
    i = np.arange(n_s - 1)[:, None]
    j = np.arange(n_xi - 1)[None, :]
    a, b, c, e = i * n_xi + j, (i + 1) * n_xi + j, (i + 1) * n_xi + j + 1, i * n_xi + j + 1
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, e], -1).reshape(-1, 3)])
    return V, F, H


def _chaikin(P, iters=3, closed=False):
    P = np.asarray(P, np.float64)
    for _ in range(iters):
        Q = 0.75 * P[:-1] + 0.25 * P[1:]
        R = 0.25 * P[:-1] + 0.75 * P[1:]
        P = np.vstack([P[:1], np.column_stack([Q, R]).reshape(-1, 3), P[-1:]])
    return P


def _resample(P, step):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(2, int(np.ceil(s[-1] / step)) + 1)
    st = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(st, s, P[:, k]) for k in range(3)]), st


RIM_R = 0.00125             # the visor's moulded rounded edge: its round, its centre in from the outer edge along the
RIM_INSET = 0.00125         # spoke, over the mid-surface (a glossy rounded edge [E: o03, o04 by eye; Skye's photos
RIM_LIFT = 0.0              # resolve no rim and no binding: CAP_GDR §3.4]). Cap v6 (the lead's decision 5: ONE soft
                            # rounded edge): the round the plate's own half-thickness at its rim, flush with its top and
                            # its outer edge, so the plate's rounded boundary is the one edge; v5's 1.3 mm bead 0.5 mm
                            # proud and 1.0 mm in drew a doubled highlight line, like a binding (the v5 check). The plain
                            # black lacquer has no cord, no gold


def rim_curve(spec=SPEC, step=0.0003):
    """the visor's moulded ROLLED RIM: its centreline round the visor's boundary (up one end, along the edge, down the
    other: its ends buried in the band), the corners rounded. Returns points, frame normals (the visor's up), its
    radius"""
    r, inset = RIM_R, RIM_INSET
    d = dims(spec)
    # the boundary in (s, xi): the end edge s = -1 from the root out, the edge, the other end back
    xs = np.linspace(-0.0010, visor_L(1.0, spec) - inset, 12)
    se = visor_s_arc(401, spec)
    # the end edges inset in s: inset mm along the band at the visor's ends
    ds = inset / (phi_to_u(d['phi_e'], spec) / 1.0)
    pts = [np.column_stack([np.full(len(xs), -1.0 + ds), xs]), np.column_stack([se * (1.0 - ds), visor_L(se, spec)
                                                                                 - inset]),
           np.column_stack([np.full(len(xs), 1.0 - ds), xs[::-1]])]
    SX = np.concatenate(pts)
    P = visor_mid(SX[:, 0], SX[:, 1], spec)
    n = visor_normal(SX[:, 0], np.maximum(SX[:, 1], 0.0), spec)
    P0 = P + n * RIM_LIFT
    P = _chaikin(P0, 3)
    P, _ = _resample(P, step)
    # the frames: the visor's up at each point (nearest sample)
    from scipy.spatial import cKDTree
    _, idx = cKDTree(P0).query(P)
    return P, n[idx], r


# ------------------------------------------------------------------------------------------- cords, knots, buttons
_VTOP = {}


def visor_height(x, z, spec=SPEC):
    """the visor's TOP surface height over the plan point (x, z) and its slope along the band's normal there's
    gradient (a linear interpolant over a dense (s, xi) grid of the top surface); nan off the visor"""
    from scipy.interpolate import LinearNDInterpolator
    key = tuple(sorted((k, str(v)) for k, v in spec.items()))
    if key not in _VTOP:
        s = np.linspace(-1.0, 1.0, 241)
        tt = np.linspace(0.0, 1.0, 121)
        S, T = np.meshgrid(s, tt, indexing='ij')
        P, _ = visor_top(S, -0.0005 + (visor_L(S, spec) + 0.0005) * T, spec)
        P = P.reshape(-1, 3)
        _VTOP[key] = LinearNDInterpolator(P[:, [0, 2]], P[:, 1])
    f = _VTOP[key]
    x, z = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(z, np.float64))
    h = 0.0002
    y = f(x, z)
    gx = (f(x + h, z) - f(x - h, z)) / (2 * h)
    gz = (f(x, z + h) - f(x, z - h)) / (2 * h)
    return y, gx, gz


def _visor_rest(phi, w, spec, r):
    """the centre height of a cord of radius r resting on the visor at band azimuth phi, w off the band's face: the
    top surface under it plus r over the cosine of its slope along the band's normal (-inf off the visor)"""
    P, N, _ = band_frame(phi, 0.0, w, spec)
    y, gx, gz = visor_height(P[..., 0], P[..., 2], spec)
    g = gx * N[..., 0] + gz * N[..., 2]
    out = y + r * np.sqrt(1.0 + g * g)
    return np.where(np.isfinite(out), out, -np.inf)


_REST = {}


def cord_rest(spec=SPEC):
    """the LOWER cord's centre height where it rests on the visor's root against the band's face (its centre r + 0.1 mm
    off the face, r over the root's top surface along its slope), the highest over the front (the cord never sinks into
    the visor): the cords' one height"""
    key = tuple(sorted((k, str(v)) for k, v in spec.items()))
    if key not in _REST:
        d = dims(spec)
        r = 0.5 * spec['cord_d']
        y = _visor_rest(np.linspace(-0.97, 0.97, 41) * d['phi_e'], r + 0.0001, spec, r)
        _REST[key] = float(np.max(y[np.isfinite(y)]))
    return _REST[key]


def cord_layout(spec=SPEC):
    """the cords' plan in band-surface coordinates (u: arc length along the band's face from the front, w: off its
    face, y: height), the LEFT half; the right mirrors it. The pair STACKED at the band's face at ONE HEIGHT round the
    front from button to button (Skye, 10-22: no bend; egmar3b, images.jpg, o03, g02: the lower cord on the visor's top
    edge at every column, the knot and the button at the cords' height, CAP_GDR §4): the lower resting on the visor's
    root (cord_rest), the upper on it; the knot at the visor's end, its front end there; the button knot_gap behind the
    knot's centre, its centre at the pair's middle (yb); the LOOP round the button's shank under its head (the upper
    cord over the shank, the lower under it, meeting behind it; the head clamps the loop's end: o03, o01). Forges 1-v3
    rested the pair side by side on the root and CLIMBED from 20 mm before the visor's end to a knot 12 mm up: the bend
    Skye saw"""
    d = dims(spec)
    r = 0.5 * spec['cord_d']
    yl = cord_rest(spec)
    u_e = float(phi_to_u(d['phi_e'], spec))
    # cap v6 (the lead's decision 3): the slide KNOT at knot_deg, at egmar3b's band silhouettes (her bulky rope masses:
    # the knots seen edge-on); past the visor's end the pair RISES along the band (a smoothstep from u_e to u_r, the
    # knot's front end) to cord_side_y, the button knot_gap behind the knot. v5 rose to 108 deg and hid the knots and the
    # buttons beyond it; v4 put the knot at the visor's end (o03's place)
    ys = spec.get('cord_side_y', yl + r)
    u_k = float(phi_to_u(np.radians(spec['knot_deg']), spec))
    u_r = u_k - 0.5 * spec['knot_l'] - 0.0005 - spec.get('knot_step', 0.0)
    u_b = u_k + spec['knot_gap']
    R_e = 0.5 * spec['shank_d'] + r + 0.0002
    w0 = r + 0.0001
    return dict(r=r, yl=yl, yb=yl + r, ys=ys, u_e=u_e, u_s=u_e, u_r=max(u_r, u_e + 1e-4), u_k=u_k, u_b=u_b, R_e=R_e,
                w0=w0, u_kb=u_k + 0.5 * spec['knot_l'], u_f=u_b + R_e, u_1=u_e - 0.010, u_2=u_e + 0.002)


def cord_centre_y(u, lay):
    """the pair's centre height at band arc u (|u|): level at the front, rising by a smoothstep past the visor's end"""
    t = np.clip((np.abs(np.asarray(u, np.float64)) - lay['u_s']) / (lay['u_r'] - lay['u_s']), 0.0, 1.0)
    return lay['yb'] + (lay['ys'] - lay['yb']) * t * t * (3.0 - 2.0 * t)


def cord_paths(spec=SPEC, step=0.0003):
    """the two cords' centrelines (dense: the SWEEPs), right eye -> right knot -> the front on the visor -> left knot
    -> left eye; and their band-frame normals. Returns dict(upper, lower: (P, N)), the layout"""
    lay = cord_layout(spec)
    r, u_b, ys, R_e, w0 = (lay[k] for k in ('r', 'u_b', 'ys', 'R_e', 'w0'))
    out = {}
    uu = np.arange(0.0, lay['u_kb'] + 1e-9, 0.0005)
    yc = cord_centre_y(uu, lay)
    du, dy = np.gradient(uu), np.gradient(yc)
    ln = np.hypot(du, dy)
    nu, ny = -dy / ln, du / ln                     # the path's normal in the band's (u, y): the pair stacked across it
    for k, nm in enumerate(('upper', 'lower')):
        sg = 1.0 if k == 0 else -1.0
        # the front to the knot's back end: ONE height across the front (the upper on the lower), then the rise past
        # the visor's end, the pair stacked across its path
        pts = [(u + sg * r * a, w0, y + sg * r * b) for u, y, a, b in zip(uu, yc, nu, ny)]
        # the loop: a cubic from the knot's back end to the shank's top (bottom), then a quarter circle behind it, all
        # under the button's head (button_frame)
        u0, y0 = lay['u_kb'], ys + sg * r
        P0, P3 = np.array([u0, y0]), np.array([u_b, ys + sg * R_e])
        P1, P2 = P0 + np.array([0.4 * (u_b - u0), 0.0]), P3 - np.array([0.4 * (u_b - u0), 0.0])
        for t in np.linspace(0.0, 1.0, 24)[1:]:
            q = (1 - t) ** 3 * P0 + 3 * t * (1 - t) ** 2 * P1 + 3 * t * t * (1 - t) * P2 + t ** 3 * P3
            pts.append((q[0], w0, q[1]))
        for th in np.linspace(np.pi / 2, 0.0, 30)[1:]:
            pts.append((u_b + R_e * np.cos(th), w0, ys + sg * R_e * np.sin(th)))
        A = np.array(pts)
        A = np.vstack([A[::-1] * [-1.0, 1.0, 1.0], A[1:]])      # the right half, mirrored, then the left
        phi = u_to_phi(A[:, 0], spec)
        P, N, _ = band_frame(phi, A[:, 2], A[:, 1], spec)
        P, s = _resample(P, step)
        from scipy.spatial import cKDTree
        _, idx = cKDTree(band_frame(phi, A[:, 2], A[:, 1], spec)[0]).query(P)
        out[nm] = (P, N[idx])
    return out, lay


def knot_curve(spec=SPEC, side=1, n=41):
    """a sliding knot's axis (the pair's centre through it, at the cords' one height) and its barrel section: the
    semi-axis off the band (r0) and the height's ratio to it (aspect), swelling from the ends (round the pair: two
    cords stacked) to the middle"""
    lay = cord_layout(spec)
    r = lay['r']
    u = np.linspace(lay['u_k'] - 0.5 * spec['knot_l'], lay['u_k'] + 0.5 * spec['knot_l'], n)
    t = np.linspace(0.0, 1.0, n)
    bulge = np.sin(np.pi * t) ** 0.6
    aw0, ay0 = r + 0.0004, 2.0 * r + 0.0005
    a_w = aw0 + (0.5 * spec['knot_w'] - aw0) * bulge
    a_y = ay0 + (0.5 * spec['knot_h'] - ay0) * bulge
    # cap v6: the barrel's back rests on the band (its axis out from the pair's centre, sin^2 along it, its slope zero at
    # the ends: the swell's own steep ends folded the low's end quads; egmar3b's bulky knots, knot_fit_v6.py), its ends
    # round the pair
    w_ax = lay['w0'] + max(0.0, 0.5 * spec['knot_w'] - 0.0003 - lay['w0']) * np.sin(np.pi * t) ** 2
    # cap v7 (the lead's decision 5: gate 12 "including rows 166-176 where hers bulge 6-10 px further out than v6's"): the
    # knot's middle hangs knot_drop below the pair's centre (sin^2 along it: its ends still round the pair), its bulk
    # lower on the band's silhouette, as her masses show it [M egmar3b through t27's camera: tests/out/cap/v7/scratch/
    # knot_fit_v7.py]
    yk = lay['ys'] - spec.get('knot_drop', 0.0) * np.sin(np.pi * t) ** 2
    P, N, T = band_frame(u_to_phi(u, spec), yk, w_ax, spec)
    if side < 0:
        P = P * [-1.0, 1.0, 1.0]
        N = N * [-1.0, 1.0, 1.0]
        P, N, a_w, a_y = P[::-1], N[::-1], a_w[::-1], a_y[::-1]
    return P, N, a_w, a_y / a_w


def button_head_w(spec=SPEC):
    """the button head's underside off the band's face: on the cords' loop (their outer line, cord_layout's w0 + r),
    pressing it 0.2 mm"""
    return spec['cord_d'] + 0.0001 - 0.0002


def button_frame(spec=SPEC, side=1):
    """the button HEAD's frame: the centre of its underside (button_head_w off the band's face, over the shank's axis)
    and the band's outward normal; button_profile's zeta 0"""
    lay = cord_layout(spec)
    P, N, T = band_frame(u_to_phi(lay['u_b'], spec), lay['ys'], button_head_w(spec), spec)
    if side < 0:
        P, N = P * [-1.0, 1.0, 1.0], N * [-1.0, 1.0, 1.0]
    return P, N


def _chaikin2(P, iters=2):
    """a 2D open polyline's corners rounded (Chaikin), its two ends held"""
    P = np.asarray(P, np.float64)
    for _ in range(iters):
        Q = 0.75 * P[:-1] + 0.25 * P[1:]
        R = 0.25 * P[:-1] + 0.75 * P[1:]
        P = np.vstack([P[:1], np.column_stack([Q, R]).reshape(-1, 2), P[-1:]])
    return P


def button_profile(spec=SPEC):
    """the domed button as a closed (rho, zeta) polygon about the band's normal (zeta 0 on the head's underside,
    button_frame's): the split-pin shank down through the cords' loop into the band, the head's flat underside, a short
    rim edge, the dome (a paraboloid's cap), its corners rounded"""
    rb, h, rs = 0.5 * spec['button_d'], spec['button_h'], 0.5 * spec['shank_d']
    zs = -button_head_w(spec) - 0.0006                  # the shank's foot, buried in the band
    rr = np.linspace(rb - 0.0002, 0.0, 14)
    dome = np.column_stack([rr, 0.0008 + (h - 0.0008) * (1.0 - (rr / (rb - 0.0002)) ** 2) ** 0.85])
    P = np.vstack([[[0.0, zs], [rs, zs], [rs, -0.0004], [rs, 0.0], [rb - 0.0004, 0.0], [rb, 0.0003], [rb, 0.0006]],
                   dome])                              # ([rs, -0.4 mm]: Chaikin rounds the shank's top 0.1 mm, not 1.5)
    P = _chaikin2(P, 2)
    P[0] = [0.0, zs]
    P[-1, 0] = 0.0
    return P


def cockade_frame(spec=SPEC):
    P, N, T = band_frame(0.0, spec['cockade_y'], 0.0, spec)
    return P, N


# ------------------------------------------------------------------------------------------- the cockade's face
# The GDR STATE COCKADE, measured on Skye's close-up (research/CAP_GDR.md §6), in units of its diameter D: u to the
# viewer's right, v up, the outer circle's centre the origin. Built from those MEASUREMENTS, never from the photo's
# pixels: the rings' radii (§6.2), the hammer's head from its measured edges and ends (§6.6), the handle's sides and
# its rounded foot, the hinge boss's circle and rings (§6.7), the compass legs on their measured outer-edge LINES
# (RANSAC, 27.6 / 31.3 deg off the axis), their inner edges (37-40 deg) and tips, the arc on its measured lower-edge
# circle with the windows' bottoms over it, flush with the left leg and running past the right as a rounded tab, the
# ribbon's five parts (§6.4: ck_overlays.py's idealised quadrilaterals, black over red over yellow), the rye ring's
# zones from the top on each side (§6.3). Forges 1-v3 drew the rye as dots inside a 0.357 D field, the hammer's head
# BELOW the hinge, no arc and a ribbed rim (CAP_GDR §6.10)
CK_RINGS = dict(outer=0.500, rim_in=0.472, ears_in=0.326, lip=0.297, disc=0.2912)
CK_DISC_C = (0.0057, -0.0058)                  # the red disc's centre (its circle fit, rms 2.1 px)
CK_HINGE = (0.004, 0.122, 0.052)               # the hinge boss: centre, outer radius (77 edge points)
CK_HINGE_RINGS = ((0.0080, 1.0), (0.0170, -1.0), (0.0280, 1.0), (0.0340, -1.0), (0.0370, 1.0), (0.0440, -1.0))
#                                              # its radial profile: + a raised ring, - a groove (the centre pin < 0.008)
CK_LEG_LINES = (((-0.128, -0.032), 27.6), ((0.148, -0.052), -31.3))   # the legs' outer edges: a point, the angle off
#                                              # the axis (+ leaning right going up); produced they meet at (-0.007, 0.201)
CK_TIPS = ((-0.207, -0.182), (0.2155, -0.1805))
CK_LEG_IN = (((-0.0585, -0.0055), (-0.1955, -0.1755)), ((0.0505, 0.0215), (0.2085, -0.1775)))  # the inner edges
CK_WIN_APEX = ((-0.0465, -0.0005), (0.0505, 0.0215))   # the windows' apexes (the red seen inside the compass)
CK_ARC_LOW = ((0.007, 0.108), 0.257)           # the arc's lower edge (188 points, rms 0.0015)
CK_ARC_UP = ((-0.080, -0.0875), (0.000, -0.083), (0.170, -0.0375))  # its upper edge: the windows' bottoms and the
#                                              # tab's top edge (a circle through these)
CK_ARC_END = -37.5                             # the tab's end about the lower edge's centre (deg; it reaches (0.2105,
#                                              # -0.0475))
CK_BAR = (0.011, 0.010, 0.312, 0.455)          # the parting bar at the top: centre u, half-width, v0, v1
CK_BAR_W = (0.0085, 0.0145)                    # cap v6: its half-widths at v0 (the inner ring) and v1 (the rim): a wedge
# cap v5 (the lead's decision 6): the ribbon's FIVE PARTS as bands, each WRAPPING the ring: a top edge (its height vtop
# at the part's ends, u_c +- half, a slope, the middle SAGGING by sag half^2: the parts curve under the bottom, as the
# close-up shows), the stripes stacked down from it at one width each (CK_STRIPES: black, a raised gilt line, red, a gilt
# line, yellow [M CAP_GDR §6.4: 0.020 / 0.026 / 0.027, the lines 0.006-0.012]), each end a half-plane (a point and its
# kept side's normal; zero: the ring's own edge ends it) cut on the slant where the stalks cross over the ribbon. Fitted to
# v4's quads below (measured: ck_ribbon.py / ck_ring.py), whose bottom parts' stripes did not line up (the v4 check: "15
# flat straight horizontal bars, the bottom parts misaligned fragments")
CK_STRIPES = ((0.000, 0.019, 1), (0.019, 0.027, 4), (0.027, 0.055, 2), (0.055, 0.063, 4), (0.063, 0.092, 3))
CK_RIBBON_W = 0.092
CK_RIBBON_PARTS = (   # (u_c, vtop, slope, sag, half), end 0 (x, y, nx, ny), end 1
    ((-0.348, -0.1605, 0.000, 0.60, 0.07), (0.0, 0.0, 0.0, 0.0), (-0.290, -0.161, -0.810, -0.587)),      # left loop
    ((0.348, -0.1760, 0.000, 0.60, 0.07), (0.278, -0.176, 0.9725, 0.2326), (0.0, 0.0, 0.0, 0.0)),        # right loop
    ((0.007, -0.3410, -0.0148, 0.30, 0.135), (-0.129, -0.340, 1.0, 0.0), (0.142, -0.343, -0.9927, 0.1213)),  # bottom
    ((-0.216, -0.3230, 0.0909, 0.40, 0.07), (-0.282, -0.329, 0.769, 0.6395), (-0.148, -0.330, -1.0, 0.0)),   # b. left
    ((0.220, -0.3295, -0.1214, 0.40, 0.07), (0.148, -0.330, 1.0, 0.0), (0.302, -0.370, -0.316, 0.949)))      # b. right
# v4's measured stripe quadrilaterals (u: left top, right top, right bottom, left bottom; v the same; 1 black, 2 red,
# 3 yellow), kept as the measurement the parts above are fitted to
CK_RIBBON = (
    ((-0.406, -0.290, -0.282, -0.408), (-0.160, -0.161, -0.176, -0.176), 1),
    ((-0.410, -0.266, -0.252, -0.412), (-0.187, -0.188, -0.218, -0.218), 2),
    ((-0.392, -0.240, -0.224, -0.388), (-0.223, -0.224, -0.252, -0.252), 3),
    ((-0.282, -0.150, -0.150, -0.270), (-0.329, -0.317, -0.331, -0.343), 1),
    ((-0.246, -0.150, -0.150, -0.240), (-0.362, -0.348, -0.377, -0.390), 2),
    ((-0.212, -0.140, -0.140, -0.208), (-0.391, -0.382, -0.414, -0.418), 3),
    ((-0.128, 0.142, 0.142, -0.128), (-0.339, -0.343, -0.356, -0.352), 1),
    ((-0.123, 0.145, 0.145, -0.123), (-0.368, -0.373, -0.399, -0.392), 2),
    ((-0.131, 0.131, 0.131, -0.131), (-0.403, -0.406, -0.435, -0.433), 3),
    ((0.150, 0.290, 0.296, 0.150), (-0.321, -0.338, -0.350, -0.337), 1),
    ((0.170, 0.300, 0.300, 0.172), (-0.343, -0.345, -0.372, -0.389), 2),
    ((0.145, 0.214, 0.214, 0.150), (-0.391, -0.395, -0.415, -0.415), 3),
    ((0.280, 0.410, 0.412, 0.290), (-0.176, -0.176, -0.190, -0.190), 1),
    ((0.274, 0.420, 0.416, 0.290), (-0.199, -0.195, -0.231, -0.233), 2),
    ((0.282, 0.386, 0.380, 0.300), (-0.234, -0.240, -0.266, -0.266), 3))
# the rye ring's zones, theta' from the top toward each side (deg), right / left (§6.3: the left's end 5-12 deg sooner)
CK_RYE = dict(right=dict(awns=(4.0, 20.0), half=(20.0, 52.0), full=(55.0, 105.0), stalks=(105.0, 112.0)),
              left=dict(awns=(3.0, 15.0), half=(15.0, 47.0), full=(50.0, 93.0), stalks=(93.0, 110.0)))
CK_GAPS = ((128.0, 145.0), (127.0, 145.0))     # where the stalks cross over the ribbon below the loops (right, left)
# the relief [E: a square-on photo gives no heights], over the band's face: the rim's top, the ear field, the inner
# ring and its lip, the enamel (domed a little), the arms' tops and the hinge boss's; cap v5: all lifted by CK_LIFT, the
# wreath's backing the cockade sits on (WREATH_BACK_H)
CK_LIFT = 0.0012
# cap v8 (the lead's decision 5: "the hammer and compass bright, high-relief yellow gold"): the arms 0.60 mm over the
# enamel (v7 0.38: they read flat beside her close-up's), the hinge boss 0.08 over them
CK_Z = dict(rim=0.00190 + CK_LIFT, field=0.00166 + CK_LIFT, ring=0.00176 + CK_LIFT, lip=0.00181 + CK_LIFT,
            enamel=0.00146 + CK_LIFT, enamel_dome=0.00006, arms=0.00206 + CK_LIFT, boss=0.00214 + CK_LIFT, grain=0.00024)


def _circ3(a, b, c):
    """the circle through three points: centre, radius"""
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return np.array([ux, uy]), float(np.hypot(ax - ux, ay - uy))


def _line_circle(p, dvec, c, r):
    """the parameters t where p + t d meets the circle (c, r), ascending"""
    p, dvec, c = (np.asarray(x, np.float64) for x in (p, dvec, c))
    f = p - c
    a, b, cc = dvec @ dvec, 2.0 * f @ dvec, f @ f - r * r
    s = np.sqrt(max(b * b - 4 * a * cc, 0.0))
    return (-b - s) / (2 * a), (-b + s) / (2 * a)


_CKP = {}


def ck_polys():
    """the cockade's gold arms as polygons (D units): the hammer's head, its handle, the two compass legs, the arc with
    its tab; the hinge boss is CK_HINGE's disc. Each an (n, 2) array, counter-clockwise"""
    if 'p' in _CKP:
        return _CKP['p']
    # the HEAD (§6.6): the flat left face u -0.1165 (v 0.164-0.197) with its top lip out to -0.1365 (v 0.200-0.219),
    # the top edge v 0.234-0.238 from u -0.08 to +0.06 falling through 0.228 (u 0.094), 0.217 (0.121), 0.201 (0.156)
    # to the blunt right point (0.158, 0.190), the bottom edge 0.150-0.157 rising through 0.164 (0.10) and 0.182 (0.155)
    head = [(-0.1150, 0.1645), (-0.0950, 0.1570), (-0.0360, 0.1500), (0.0480, 0.1520), (0.1000, 0.1640),
            (0.1545, 0.1815), (0.1585, 0.1880), (0.1560, 0.2010), (0.1210, 0.2170), (0.0940, 0.2280),
            (0.0600, 0.2340), (-0.0100, 0.2370), (-0.0800, 0.2345), (-0.1150, 0.2240), (-0.1170, 0.2160),
            (-0.1350, 0.2185), (-0.1365, 0.2005), (-0.1335, 0.1975), (-0.1165, 0.1965)]
    # the HANDLE: 0.070 wide below the arc (u -0.031 .. +0.0385), its foot at v -0.272 rounded at about 0.015;
    # between the windows 0.072-0.083 wide, widening upward, to the hinge
    handle = [(-0.0310, -0.2580), (-0.0230, -0.2690), (-0.0100, -0.2725), (0.0200, -0.2725), (0.0320, -0.2680),
              (0.0385, -0.2570), (0.0390, -0.1500), (0.0445, -0.0700), (0.0450, 0.0200), (0.0300, 0.1000),
              (-0.0250, 0.1000), (-0.0390, 0.0000), (-0.0265, -0.0600), (-0.0330, -0.1500)]
    # the LEGS: the outer edges on their measured lines to the feet, the tips, the inner edges up to the windows'
    # apexes, closed under the hinge boss
    apex = None
    lines = []
    for (p, ang) in CK_LEG_LINES:
        t = np.radians(ang)
        lines.append((np.array(p), np.array([np.sin(t), np.cos(t)])))      # pointing up the leg
    (p0, d0), (p1, d1) = lines
    M = np.column_stack([d0, -d1])
    t0 = np.linalg.solve(M, p1 - p0)[0]
    apex = p0 + t0 * d0                                                   # (-0.007, 0.201)
    on = lambda k, vv: lines[k][0] + lines[k][1] * (vv - lines[k][0][1]) / lines[k][1][1]
    # the left leg's outer edge straight to v -0.135 (where the arc's left end meets it), its foot flaring to the tip
    legL = [tuple(apex), (CK_HINGE[0], CK_HINGE[1]), (-0.0320, 0.0200), (-0.0385, -0.0095), CK_WIN_APEX[0],
            CK_LEG_IN[0][0], CK_LEG_IN[0][1], CK_TIPS[0], (-0.2045, -0.1615), tuple(on(0, -0.135))][::-1]
    legR = [tuple(apex), tuple(on(1, -0.1555)), CK_TIPS[1], CK_LEG_IN[1][1], CK_LEG_IN[1][0], CK_WIN_APEX[1],
            (0.0445, 0.0085), (0.0420, 0.0400), (CK_HINGE[0], CK_HINGE[1])][::-1]
    # the ARC: the band between its lower-edge circle and the upper-edge circle, cut flush along the left leg's outer
    # edge line, its right end a rounded tab at CK_ARC_END
    (cl, rl) = np.array(CK_ARC_LOW[0]), CK_ARC_LOW[1]
    cu, ru = _circ3(*CK_ARC_UP)
    pL, dL = lines[0]
    ang = lambda q, c_: float(np.arctan2(q[1] - c_[1], q[0] - c_[0]))
    circ = lambda c_, r_, a: c_ + r_ * np.column_stack([np.cos(a), np.sin(a)])
    # the left end: the leg line's LOWER crossing of each edge circle (the line runs up the leg)
    q_lo = pL + min(_line_circle(pL, dL, cl, rl)) * dL
    q_up = pL + min(_line_circle(pL, dL, cu, ru)) * dL
    aE = np.radians(CK_ARC_END)
    lo = circ(cl, rl, np.linspace(ang(q_lo, cl), aE, 40))              # the lower edge, left end -> the tab's end
    e_lo = lo[-1]
    e_up = cu + ru * (e_lo - cu) / np.linalg.norm(e_lo - cu)            # the upper edge's end across from it
    a_u0, a_u1 = ang(e_up, cu), ang(q_up, cu)
    up_ = circ(cu, ru, np.linspace(a_u0, a_u1, 40))                    # the upper edge, back to the left end
    # the tab's rounded end: a half-circle from the lower edge's end to the upper edge's, bulging along the band
    m = 0.5 * (e_lo + e_up)
    rad = 0.5 * np.linalg.norm(e_lo - e_up)
    tng = np.array([-np.sin(aE), np.cos(aE)])
    a0 = ang(e_lo, m)
    sw = np.pi if np.dot([np.cos(a0 + 0.5 * np.pi), np.sin(a0 + 0.5 * np.pi)], tng) > 0.0 else -np.pi
    cap = circ(m, rad, a0 + np.linspace(0.0, sw, 9))
    arc = np.vstack([lo, cap[1:-1], up_])
    out = []
    for P in (head, handle, legL, legR, arc):
        P = np.asarray(P, np.float64)
        a2 = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        out.append(P if a2 > 0 else P[::-1].copy())
    _CKP['p'] = out
    return out


def _poly_sd_np(X, P):
    """the signed distance (negative inside) of points X (n, 2) to the polygon P (m, 2): the nearest edge, the sign by
    the crossing number"""
    X = np.asarray(X, np.float64)
    A, B = P, np.roll(P, -1, axis=0)
    E = B - A
    W = X[:, None, :] - A[None, :, :]
    t = np.clip((W * E[None]).sum(-1) / np.maximum((E * E).sum(-1), 1e-20)[None], 0.0, 1.0)
    d = np.sqrt(((W - t[..., None] * E[None]) ** 2).sum(-1)).min(1)
    y = X[:, 1:2]
    cr = ((A[None, :, 1] > y) != (B[None, :, 1] > y)) & \
        (X[:, 0:1] < A[None, :, 0] + (y - A[None, :, 1]) * E[None, :, 0] / np.where(np.abs(E[None, :, 1]) < 1e-20,
                                                                                    1e-20, E[None, :, 1]))
    inside = (cr.sum(1) % 2) == 1
    return np.where(inside, -d, d)


def ck_arms_sd_np(u, v):
    """the signed distance (D units, negative inside) to the gold arms: the union of ck_polys() and the hinge boss"""
    X = np.column_stack([np.ravel(u), np.ravel(v)])
    d = np.hypot(X[:, 0] - CK_HINGE[0], X[:, 1] - CK_HINGE[1]) - CK_HINGE[2]
    for P in ck_polys():
        for a in range(0, len(X), 20000):
            d[a:a + 20000] = np.minimum(d[a:a + 20000], _poly_sd_np(X[a:a + 20000], P))
    return d.reshape(np.shape(u))


def ck_ribbon_parts_np(u, v):
    """the ribbon's parts (CK_RIBBON_PARTS) under (u, v), D units: the class (0 none, 1 black, 2 red, 3 yellow, 4 a gilt
    line between stripes), the depth across the part (0 its top edge .. 1 its bottom), the distance in from its nearer
    end (D). The kernel's ck_ribbon is its twin"""
    u, v = np.ravel(np.asarray(u, np.float64)), np.ravel(np.asarray(v, np.float64))
    cls = np.zeros(len(u), np.int32)
    acr = np.zeros(len(u))
    dend = np.zeros(len(u))
    for (uc, vt, sl, sg, hl), e0, e1 in CK_RIBBON_PARTS:
        du = u - uc
        top = vt + sl * du - sg * np.maximum(hl * hl - du * du, 0.0)
        x = top - v
        d0 = (u - e0[0]) * e0[2] + (v - e0[1]) * e0[3] if (e0[2] or e0[3]) else np.full(len(u), 9.0)
        d1 = (u - e1[0]) * e1[2] + (v - e1[1]) * e1[3] if (e1[2] or e1[3]) else np.full(len(u), 9.0)
        ins = (x >= 0.0) & (x <= CK_RIBBON_W) & (d0 >= 0.0) & (d1 >= 0.0) & (np.abs(du) <= hl + 0.08) & (cls == 0)
        for a, b, k in CK_STRIPES:
            m = ins & (x >= a) & (x < b + (1e-9 if b == CK_RIBBON_W else 0.0))
            cls[m] = k
        acr[ins] = x[ins] / CK_RIBBON_W
        dend[ins] = np.minimum(d0, d1)[ins]
    return cls.reshape(np.shape(u)), acr.reshape(np.shape(u)), dend.reshape(np.shape(u))


def ck_ribbon_np(u, v):
    """the ribbon's enamel under (u, v): 0 none (or a gilt line between its stripes), 1 black, 2 red, 3 yellow"""
    c = ck_ribbon_parts_np(u, v)[0]
    return np.where(c == 4, 0, c)


def ck_face_np(u, v):
    """the face's class under (u, v) (D units): 0 off it, 1 gilt (the rings, the rye field, the lip), 2 the red
    enamel, 3 / 4 / 5 the ribbon's black / red / yellow enamel, 6 the gilt arms; and the arms' signed distance"""
    u, v = np.ravel(u), np.ravel(v)
    r = np.hypot(u, v)
    rd = np.hypot(u - CK_DISC_C[0], v - CK_DISC_C[1])
    arm = ck_arms_sd_np(u, v)
    cls = np.where(r <= CK_RINGS['outer'], 1, 0).astype(np.int32)
    disc = rd < CK_RINGS['disc']
    cls[disc] = 2
    cls[disc & (arm < 0.0)] = 6
    rib = ck_ribbon_np(u, v)
    ring = (r > CK_RINGS['ears_in']) & (r < CK_RINGS['rim_in']) & (rib > 0)
    cls[ring] = 2 + rib[ring]
    return dict(cls=cls, arm=arm)


def ck_rye_bodies():
    """cap v5: the rye ring's embossed MASSES as capsules in the face's (u, v) (D units), the sculpt's share (its FINE
    grains, awns and stalks are the texture's, ck_rye_h, at the cockade's 13 px/mm; the 0.15 mm voxels drew v4's grains
    as fat chevrons and its awns as a few fat bars, the v4 check): per side from the top (§6.3) the awn field, the two
    half-width ears side by side, the full ear and the stalks, each a chain of balls along its axis whose caps stand a
    low smooth mound over the field (the ears CK_Z['grain'], the awns and stalks 0.45 of it); the stalks crossing the
    ribbon in its gaps. Returns (A (n, 2), B (n, 2), radius (n,), the cap's top over the field (n,), D units)"""
    A, B, R, T = [], [], [], []

    def pol(rr, th_deg, side):
        t = np.radians(th_deg)
        return np.array([side * rr * np.sin(t), rr * np.cos(t)])

    def chain(side, t0, t1, ra, rb, top, rad_share=0.85):
        rm, hw = 0.5 * (ra + rb), 0.5 * (rb - ra)
        n = max(2, int(np.ceil(rm * np.radians(t1 - t0) / (0.6 * hw))))
        th = np.linspace(t0, t1, n + 1)
        for a, b in zip(th[:-1], th[1:]):
            A.append(pol(rm, a, side))
            B.append(pol(rm, b, side))
            R.append(rad_share * hw)
            T.append(top)
    g = CK_Z['grain']
    for side, nm in ((1.0, 'right'), (-1.0, 'left')):
        z = CK_RYE[nm]
        chain(side, z['awns'][0] + 0.5, z['awns'][1] + 2.0, 0.336, 0.464, 0.45 * g, 0.9)
        chain(side, z['half'][0], z['half'][1], 0.400, 0.468, g)
        chain(side, z['half'][0] + 2.0, z['half'][1], 0.330, 0.394, g)
        chain(side, z['full'][0], z['full'][1], 0.332, 0.466, g)
        chain(side, z['stalks'][0] - 3.0, z['stalks'][1] + 3.0, 0.342, 0.454, 0.45 * g, 0.9)
        g0, g1 = CK_GAPS[0 if side > 0 else 1]
        chain(side, g0 - 2.0, g1 + 2.0, 0.346, 0.444, 0.45 * g, 0.9)
    return np.array(A), np.array(B), np.array(R), np.array(T)


def ck_rye_strokes():
    """CAP V4's rye ring relief (kept for comparison; cap v5 sculpts ck_rye_bodies and paints the grains): capsules in
    the face's (u, v) (D units): (A, B, radius) per stroke, each lying on the ear field. Per side from the top (§6.3):
    the awns (8 long tangential lines), two half-width ears side by side (6-7 grain chevrons each, 4-5 deg apart), one
    full-width ear (8-9 chevrons 5 deg apart), the stalks; the chevrons open toward the top (the ears point up, the
    sheaves meet at the parting bar); below the ribbon's loops the stalks cross over the ribbon. Returns (A (n, 2), B
    (n, 2), r (n,))"""
    A, B, R = [], [], []

    def pol(rr, th_deg, side):
        t = np.radians(th_deg)
        return np.array([side * rr * np.sin(t), rr * np.cos(t)])

    def ear(side, th0, th1, ra, rb, n, rg):
        # chevrons from the tip (th0, the top) to the stalk (th1): each two grains from the ear's axis (stalk side)
        # out to its two edges (tip side)
        rm = 0.5 * (ra + rb)
        dth = (th1 - th0) / n
        for k in range(n):
            tk = th0 + (k + 0.5) * dth
            for re_ in (rb - 0.35 * (rb - ra) * 0.5, ra + 0.35 * (rb - ra) * 0.5):
                A.append(pol(rm, tk + 0.35 * dth, side))
                B.append(pol(re_, tk - 0.25 * dth, side))
                R.append(rg)
        # its spine (the rachis) under the grains
        for k in range(n):
            A.append(pol(rm, th0 + k * dth + 0.3 * dth, side))
            B.append(pol(rm, th0 + (k + 1) * dth + 0.3 * dth, side))
            R.append(0.45 * rg)
    for side, nm in ((1.0, 'right'), (-1.0, 'left')):
        z = CK_RYE[nm]
        # the awns: 8 long tangential lines across the field
        for k in range(8):
            rr = 0.338 + (0.462 - 0.338) * k / 7.0
            A.append(pol(rr, z['awns'][0], side))
            B.append(pol(rr, z['awns'][1] + 2.0, side))
            R.append(0.0055)
        h0, h1 = z['half']
        ear(side, h0, h1, 0.400, 0.470, 7, 0.0135)
        ear(side, h0 + 2.0, h1, 0.330, 0.392, 6, 0.0125)
        f0, f1 = z['full']
        ear(side, f0, f1, 0.332, 0.462, 9, 0.0170)
        # the stalks: tangential lines from the full ear's foot to the ribbon's loop
        s0, s1 = z['stalks']
        for k in range(5):
            rr = 0.345 + (0.450 - 0.345) * k / 4.0
            A.append(pol(rr, s0 - 3.0, side))
            B.append(pol(rr, s1 + 3.0, side))
            R.append(0.0075)
        g0, g1 = CK_GAPS[0 if side > 0 else 1]
        for k in range(4):
            rr = 0.350 + (0.440 - 0.350) * k / 3.0
            A.append(pol(rr, g0 - 2.0, side))
            B.append(pol(rr, g1 + 2.0, side))
            R.append(0.0075)
    return np.array(A), np.array(B), np.array(R)


def cockade_profile(spec=SPEC):
    """the cockade as a closed (rho, zeta) polygon about the band's normal (the block-out): the back buried, the
    edge, the plain outer band 0.472-0.500 D at its top (CK_Z), the step down onto the rye ring's field (0.326-0.472),
    the plain inner ring (0.297-0.326) and its gilt lip (0.291-0.297), the step down onto the domed red enamel (r <
    0.291 D); the arms, the rye's grains and the parting bar are the sculpt's (plan_cap), the hinge's rings, the
    ribbon's cells and the pebbled base under the enamel the texture's"""
    D = spec['cockade_d']
    R = 0.5 * D
    z = CK_Z
    pts = [[0.0, -0.0004], [R - 0.0002, -0.0004], [R, 0.0], [R, z['rim'] - 0.0005], [R - 0.00015, z['rim'] - 0.0001],
           [R - 0.0004, z['rim']], [CK_RINGS['rim_in'] * D + 0.0001, z['rim']],
           [CK_RINGS['rim_in'] * D - 0.0001, z['field']], [CK_RINGS['ears_in'] * D + 0.0001, z['field']],
           [CK_RINGS['ears_in'] * D - 0.0001, z['ring']], [CK_RINGS['lip'] * D + 0.00005, z['ring']],
           [CK_RINGS['lip'] * D - 0.00005, z['lip']], [CK_RINGS['disc'] * D + 0.00005, z['lip']],
           [CK_RINGS['disc'] * D - 0.00005, z['enamel']]]
    rr = np.linspace(CK_RINGS['disc'] * D - 0.0003, 0.0, 7)
    dome = np.column_stack([rr, z['enamel'] + z['enamel_dome'] * (1.0 - (rr / (CK_RINGS['disc'] * D)) ** 2)])
    return np.vstack([pts, dome])


# ----------------------------------------------------------------------------------------------------- block-out
def build_sdf(spec=SPEC, parts=None, rope_core=False):
    """the block-out. parts: None (everything) or a subset of ('crown', 'visor', 'pipings', 'edge', 'cords', 'knots',
    'buttons', 'cockade'; 'cord_upper' / 'cord_lower' one cord alone): a part's own program for its low's projection
    (a band ring under the cockade must land on the band, not on the cockade) and for buried_triangles. Hard unions,
    the small parts seated with 0.25-0.3 mm fillets. rope_core (cap v6, the high's own block-out): the cords as their
    thin cores (ROPE_CORE), round which the plan adds the plies' bundles (_rope)"""
    d = dims(spec)
    want = (lambda p: True) if parts is None else (lambda p: p in parts)
    prog = sdf.Program()
    if want('crown'):
        V, F, H = crown_patch(spec)
        prog.shell(V, F, H, k=0.0, maxd=0.03, name='crown cloth')
        # cap v6: the lining's top panel across the roll's pocket (lining_patch): the high of the low's lining strip
        V, F, H = lining_patch(spec)
        prog.shell(V, F, H, k=0.0, maxd=0.01, name='lining')
    if want('visor'):
        V, F, H = visor_patch(spec)
        prog.shell(V, F, H, k=0.0, maxd=0.03, name='visor')
    if want('pipings'):
        ph = np.linspace(-0.15, 2.0 * np.pi + 0.15, 6000)
        # the crown piping on the wall's seam UNDER the roll (cap v6; v5's lay at the top's edge), the band's on its top
        # seam (raised at the front centre)
        prog.sweep(pipe_centre(ph, spec), np.column_stack([np.sin(ph), np.zeros_like(ph), np.cos(ph)]), d['rp'], k=0.0,
                   name='crown piping')
        Pb, Nb, _ = band_frame(ph, band_top(ph, spec), 0.00025, spec)
        prog.sweep(Pb, Nb, d['rpb'], k=0.0, name='band piping')
    if want('edge'):
        Pe, Ne, re = rim_curve(spec)
        prog.sweep(Pe, Ne, re, k=0.0003, name='visor rim')
    if want('cords') or want('cord_upper') or want('cord_lower'):
        paths, _ = cord_paths(spec)
        for nm, (P, N) in paths.items():
            if want('cords') or want(f'cord_{nm}'):
                prog.sweep(P, N, 0.5 * spec['cord_d'] * (ROPE_CORE if rope_core else 1.0), k=0.0, name=f'cord {nm}')
    if want('knots'):
        for side in (1, -1):
            P, N, r0, asp = knot_curve(spec, side)
            prog.sweep(P, N, r0, aspect=asp, k=0.0003, name=f'knot {side:+d}')
    if want('buttons'):
        bp = button_profile(spec)
        for side in (1, -1):
            c, n = button_frame(spec, side)
            prog.revolve(bp, c, n, k=0.00025, name=f'button {side:+d}')
    if want('cockade'):
        c, n = cockade_frame(spec)
        prog.revolve(cockade_profile(spec), c, n, k=0.0003, name='cockade')
    prog.cap = dict(spec=spec, dims=d, parts=parts)
    return prog


def bounds(spec=SPEC, pad=0.005):
    d = dims(spec)
    tip = visor_mid(0.0, spec['visor_d'], spec)
    T = crown_rim(spec)
    ytop = spec['band_h'] + float((rise(T['ph'], spec) + T['dy'] + T['rho']).max())      # the roll's top (cap v6)
    out = d['rp'] + max(0.0, float(T['O'].max()))                                       # the roll's overhang
    return (np.array([-d['Rx'] - out, tip[1] - 0.006, -d['Rz'] - out]) - pad,
            np.array([d['Rx'] + out, ytop + 0.002, tip[2] + 0.006]) + pad)


# ----------------------------------------------------------------------------------------------------------- low
# A PIECE (round_glasses' assembly): welded V, quads Q (outward), per quad its region, per vertex ATTR (a0, a1, a2,
# part) and its UV ISLANDS (split vertices, each a welded id, with UVs in metres and the island's texel share)
def _piece(V, Q, region, attr, islands):
    return dict(V=np.asarray(V, np.float64), Q=np.asarray(Q, np.int64),
                region=np.broadcast_to(np.asarray(region, np.int64), (len(Q),)).copy(),
                attr=np.asarray(attr, np.float64), islands=islands)


def _project(prog, P, dirs, maxd=0.006):
    """points pulled onto a program's surface along their (outward) directions (sdf.Program.project's convention);
    a point the march could not settle keeps its place"""
    p, st = prog.project(P, dirs, maxd=maxd)
    ok = (st <= 1) & np.isfinite(p).all(1)
    out = np.asarray(P, np.float64).copy()
    out[ok] = p[ok]
    return out, ok


def crown_stations(spec=SPEC):
    """the crown low's rings in order, each (name, kind, value, columns): the top's cap ring out across the membrane,
    over the ROLL (cap v6: its upper outer side, its outermost, its underside, as angles about the roll's centre), the
    piping's outer and lower faces under it, down the wall, the band-top piping, the band, round its bottom, up the
    sweatband and the lining to the lining's cap ring. Cap v6 (the lead's decision 1: the rim's silhouette columns at
    least doubled, the triangles from the flat regions): the roll, the piping and the upper wall carry K_RIM columns (9.5
    mm chords round the 0.9 m rim: v5's 44 put 20 mm chords on it, facets on its silhouette), the lower wall and the band
    K_BAND, the lining K_IN; a 4 -> 2 reduction strip joins each change (loft.reduce_ring's pattern). The LINING's wall
    ring sits at the outer wall's own t, so its chord runs under its outer one; its last ring is on the wall's inner face
    just under the seam, and its chord to the lining's top runs under the roll's hollow (inside the cap, clear of the
    cloth). The top's membrane is flat to 0.45 mm across its coarse cap"""
    return [('tc', 'top', 0.55, K_IN), ('t2', 'top', 0.90, K_BAND), ('t3', 'top', 0.982, K_RIM),
            ('r1', 'roll', 62.0, K_RIM), ('r2', 'roll', 12.0, K_RIM), ('r3', 'roll', -28.0, K_RIM),
            ('po', 'pipe', -5.0, K_RIM), ('pu', 'pipe', -62.0, K_RIM),
            ('w1', 'wall', 0.90, K_RIM), ('w2', 'wall', 0.66, K_RIM), ('w3', 'wall', 0.38, K_BAND),
            ('w4', 'wall', 0.13, K_BAND), ('bp', 'bandpipe', 0.0, K_BAND),
            ('bb', 'bandbot', -0.25 * np.pi, K_BAND), ('bo', 'bandbot', -0.5 * np.pi, K_BAND),
            ('st', 'inner', spec['sweat_h'] + 0.0035, K_BAND),
            ('ib', 'innerwall', 0.0, K_IN), ('ie', 'innerwall', 0.96, K_IN), ('ic', 'innertop', 0.40, K_IN)]


K_RIM, K_BAND, K_IN = 96, 48, 24
# the islands between rings, each cut down the columns at these QUARTERS round (0 the front, 2 the back): the top's
# membrane whole; the ROLL with the piping's outer face (the crown's silhouette, unrolled as four strips); the wall's
# front and back seams are real seams; the band's front island (+-0.55 quarter: 7 of K_BAND 48's columns a side, +-52 deg,
# round the wreath's +-37) is whole and takes WREATH_SHARE
# cap v7 (the lead's decision 6: "remove the piping's seam line on the low's po ring"): the roll's island runs on over
# the piping's outer face to its underside ('pu'), so the cut between the roll's and the wall's islands lies under the
# piping, out of sight (v6 cut at 'po', the piping's outer face, and its island border drew a thin olive line along the
# front piping); and the roll's strips are cut on the DIAGONALS (45 / 135 / 225 / 315 deg, rim columns 12, 36, 60, 84):
# v6 cut them at the front centre and at the side tips, the three places the crown's edge is looked at most (the front
# centre's V wedge and the tips' corners both sat on those cuts)
CROWN_ISLANDS = (('top', 0, 't3', ()), ('roll', 't3', 'pu', (0.5, 1.5, 2.5, 3.5)), ('wall', 'pu', 'bp', (0, 1, 2, 3)),
                 ('band', 'bp', 'bo', (0.5833, 1, 2, 3, 3.4167)), ('inside', 'bo', 'st', (0, 2)),
                 ('inside', 'st', 'ie', (0, 2)), ('inside', 'ie', None, ()))


def _crown_ring(st, phi, spec, prog):
    """one station's K points on the crown's surface (analytic, then projected onto the crown's own program) and
    their outward directions"""
    d = dims(spec)
    nm, kind, val = st[:3]
    K = len(phi)
    half = 0.5 * spec['cloth_t']
    if kind in ('top', 'innertop'):
        r = np.full(K, val)
        n = top_normal(r, phi, spec)
        sg = 1.0 if kind == 'top' else -1.0
        P = top_point(r, phi, spec) + sg * half * n
        D = sg * n
    elif kind in ('wall', 'innerwall'):
        t = np.full(K, val)
        n = wall_normal(t, phi, spec)
        sg = 1.0 if kind == 'wall' else -1.0
        P = wall_point(t, phi, spec) + sg * half * n
        D = sg * n
    elif kind in ('roll', 'pipe'):
        # cap v6: on the ROLL's outer surface at the angle val (deg) about its circle's centre, held inside the arc it
        # wraps (th1 .. th_e: at the high front the cloth comes up from the seam nearly upright), or on the PIPING's tube
        # at the angle val about its centre E; each out along its own radius, in the meridian half-plane
        ph_ = np.angle(np.exp(1j * phi))
        if kind == 'roll':
            th = np.clip(np.radians(val), _rim_at(ph_, 'th1', spec) + np.radians(3.0),
                         _rim_at(ph_, 'th_e', spec) - np.radians(3.0))
            c = np.stack([_rim_at(ph_, 'dx', spec), _rim_at(ph_, 'dy', spec)], -1)
            r = _rim_at(ph_, 'rho', spec)
        else:
            th = np.full(K, np.radians(val))
            c = np.zeros((K, 2))
            r = np.full(K, d['rp'])
        u = np.stack([np.cos(th), np.sin(th)], -1)
        P = _local_to_world(c + r[:, None] * u, ph_, spec)
        D = _unit(_local_to_world(c + (r[:, None] + 0.001) * u, ph_, spec) - P)
    elif kind == 'bandpipe':
        # cap v5: the ring on the band-top piping's LOWER-OUTER quadrant, projected outward and down: at the sides the
        # wall's cloth now leaves the band almost level (the side roll fitted to egmar3b) and buries the piping's top,
        # and the ring projected straight out along the band's normal slid under the wall to 5.9-6.7 mm off the band
        # (the first v5 forges: the band's low leaned out ~1.4 mm at the cords' height, the cords swallowed it, band
        # islands #6 / #7 failed the bake gate; tests/out/cap/v5/scratch/miss_map.py). Cap v6: on the raised seam
        P0, N, _ = band_frame(phi, band_top(phi, spec) - 0.70710678 * d['rpb'], 0.00025 + 0.70710678 * d['rpb'], spec)
        P, D = P0, _unit(N - np.array([0.0, 1.0, 0.0]))
    elif kind == 'band':
        P, D, _ = band_frame(phi, val, 0.0, spec)
    elif kind == 'bandbot':
        bt = spec['band_t']
        Pc, N, _ = band_frame(phi, 0.5 * bt, -0.5 * bt, spec)
        D = np.cos(val) * N + np.sin(val) * np.array([0.0, 1.0, 0.0])
        P = Pc + 0.5 * bt * D
    else:                                                            # 'inner': the sweatband's face
        w = -spec['band_t'] + (spec['sweat_t'] if val > spec['sweat_h'] else 0.0)
        P, N, _ = band_frame(phi, val, w, spec)
        D = -N
    if prog is not None:
        P, _ = _project(prog, P, D)
    return P, D


def _reduce_strip(fine, coarse, mids, fine_first):
    """the quads of a 4 -> 2 REDUCTION strip between a ring of K ids (fine) and one of K / 2 (coarse), K % 4 == 0, with
    K / 4 middle vertices (loft.reduce_ring's pattern): per unit of four fine edges o0..o4 and two coarse i0 i1 i2, one
    middle vertex m and four quads (o0 o1 m i0) (o1 o2 o3 m) (o3 o4 i2 m) (i0 m i2 i1); wound as a plain strip from the
    first ring to the second (fine_first: the fine ring comes first in the station order, else each quad reversed)"""
    K = len(fine)
    Q = []
    for u in range(K // 4):
        o = [fine[(4 * u + j) % K] for j in range(5)]
        i0, i1, i2 = coarse[(2 * u) % (K // 2)], coarse[(2 * u + 1) % (K // 2)], coarse[(2 * u + 2) % (K // 2)]
        m = mids[u]
        for q in ([o[0], o[1], m, i0], [o[1], o[2], o[3], m], [o[3], o[4], i2, m], [i0, m, i2, i1]):
            Q.append(q if fine_first else q[::-1])
    return np.array(Q, np.int64)


def crown_piece(spec=SPEC, prog=None, log=print):
    """the crown's designed low: a ring per station (its own column count, crown_stations), quads between consecutive
    rings (a 4 -> 2 reduction strip where the count halves or doubles, its middle vertices projected onto the surface),
    6 x 6 grid caps on the top's ring and the lining's (their inner points onto the top's surfaces); the islands by LSCM
    + ARAP per island (top_hat's unwrap: the depth with the smallest worst-direction footprint that lies flat), cut down
    the columns CROWN_ISLANDS names (the wall's front and back seams are real seams; every cut lies on a column of every
    ring it crosses: the cuts sit on multiples of four rim columns)"""
    from .. import loft
    from .. import uv as U
    S = crown_stations(spec)
    names = [s[0] for s in S]
    rings, dirs, ids, nv = [], [], [], 0
    for st in S:
        Ks = st[3]
        ph = 2.0 * np.pi * np.arange(Ks) / Ks
        P, D = _crown_ring(st, ph, spec, prog)
        rings.append(P)
        dirs.append(D)
        ids.append(np.arange(nv, nv + Ks))
        nv += Ks
    V = list(rings)
    Q, strip_q = [], []
    for i in range(len(S) - 1):
        A, B = ids[i], ids[i + 1]
        if len(A) == len(B):
            k = np.arange(len(A))
            q = np.stack([A[k], A[(k + 1) % len(A)], B[(k + 1) % len(A)], B[k]], -1)
        else:
            fine_first = len(A) > len(B)
            fi, co = (A, B) if fine_first else (B, A)
            Pf, Df = (rings[i], dirs[i]) if fine_first else (rings[i + 1], dirs[i + 1])
            Pc, Dc = (rings[i + 1], dirs[i + 1]) if fine_first else (rings[i], dirs[i])
            assert len(fi) == 2 * len(co) and len(fi) % 4 == 0, (names[i], len(A), len(B))
            u = np.arange(len(fi) // 4)
            Pm = 0.5 * (Pf[4 * u + 2] + Pc[2 * u + 1])
            Dm = _unit(Df[4 * u + 2] + Dc[2 * u + 1])
            if prog is not None:
                Pm, _ = _project(prog, Pm, Dm)
            mids = np.arange(nv, nv + len(u))
            nv += len(u)
            V.append(Pm)
            q = _reduce_strip(fi, co, mids, fine_first)
        Q.append(q)
        strip_q.append(np.full(len(q), i))
    V = np.concatenate(V)
    Q = np.concatenate(Q)
    strip_of = np.concatenate(strip_q)
    mesh = QuadMesh(V, Q)
    # the winding: the band's quads face away from the axis (the strip from the band-top piping down the band)
    qs = np.nonzero(strip_of == names.index('bp'))[0]
    c = V[Q[qs]].mean(1)
    if (mesh.face_normals()[qs] * (c * [1.0, 0.0, 1.0])).sum() < 0.0:
        Q = Q[:, ::-1].copy()
        mesh = QuadMesh(V, Q)
    # regions per strip: the top's membrane and the roll (the top's own cloth), the piping and the wall, the band, the
    # inside
    i_r3, i_bp, i_bo = names.index('r3'), names.index('bp'), names.index('bo')
    region = np.where(strip_of < i_r3, R_['top'], np.where(strip_of < i_bp, R_['wall'],
                                                           np.where(strip_of < i_bo, R_['band'], R_['inside'])))
    mesh, G_top = loft.cap(mesh, ids[0], [0.0, 1.0, 0.0])
    mesh, G_in = loft.cap(mesh, ids[-1], [0.0, -1.0, 0.0])
    d = dims(spec)
    for G, sg in ((G_top, 1.0), (G_in, -1.0)):
        inner = G[1:-1, 1:-1].ravel()
        Pi = mesh.V[inner]
        pp = np.arctan2(Pi[:, 0] / d['Rx'], Pi[:, 2] / d['Rz'])
        for _ in range(2):                                    # the membrane's own (Rx + dr, Rz + dr) about the axis
            dr = _rim_at(pp, 'dr', spec)
            pp = np.arctan2(Pi[:, 0] / (d['Rx'] + dr), Pi[:, 2] / (d['Rz'] + dr))
        rr = np.hypot(Pi[:, 0] / (d['Rx'] + dr), Pi[:, 2] / (d['Rz'] + dr))
        n = top_normal(rr, pp, spec)
        P = top_point(rr, pp, spec) + sg * 0.5 * spec['cloth_t'] * n
        if prog is not None:
            P, _ = _project(prog, P, sg * n)
        mesh.V[inner] = P
    n_top = (G_top.shape[0] - 1) * (G_top.shape[1] - 1)
    n_in = (G_in.shape[0] - 1) * (G_in.shape[1] - 1)
    region = np.concatenate([region, np.full(n_top, R_['top']), np.full(n_in, R_['inside'])])
    # the islands: label the quads by station strips (the caps join the first / last island), cut by azimuth (each
    # cut on a column of every ring: the quads' centroids fall on one side)
    strip_of = np.concatenate([strip_of, np.full(n_top, -1), np.full(n_in, len(S) - 1)])
    cq = mesh.V[mesh.Q].mean(1)
    az = np.mod(np.arctan2(cq[:, 0] / d['Rx'], cq[:, 2] / d['Rz']), 2.0 * np.pi)       # 0 the front, + the wearer's left
    islands = []
    quads_all = np.arange(len(mesh.Q))
    for name, a, b, cuts in CROWN_ISLANDS:
        ia = 0 if a == 0 else names.index(a)
        ib_ = len(S) - 1 if b is None else names.index(b)
        sel = (strip_of >= ia) & (strip_of < ib_)
        if a == 0:
            sel |= strip_of == -1
        if b is None:
            sel |= strip_of == len(S) - 1
        cuts = sorted(c * 0.5 * np.pi for c in cuts)
        if cuts:
            groups = []
            for gi, c0 in enumerate(cuts):
                c1 = cuts[(gi + 1) % len(cuts)]
                span = np.mod(az - c0, 2.0 * np.pi) < (np.mod(c1 - c0, 2.0 * np.pi) or 2.0 * np.pi)
                groups.append((sel & span, c0 <= 1e-9 or c1 < c0, c0))
        else:
            groups = [(sel, True, 0.0)]
        for gsel, front, c0g in groups:
            share = INNER_SHARE if name == 'inside' else (WREATH_SHARE if name == 'band' and front else 1.0)
            qid = quads_all[gsel]
            if not len(qid):
                continue
            Qg = mesh.Q[qid]
            vs = np.unique(Qg)
            loc = -np.ones(len(mesh.V), np.int64)
            loc[vs] = np.arange(len(vs))
            Fl = U._tri(loc[Qg])
            Pv = mesh.V[vs]
            if name == 'roll':
                # cap v6: the ROLL's strip unrolled analytically, straight (the visor rim's way): u along the rim by the
                # rings' mean arc length, v across them by each column's own (its rings' radii differ by ~3 %: LSCM bent
                # the four strips into arcs that packed at 0.4 of their boxes)
                ring_of = np.searchsorted(np.array([ii[0] for ii in ids]), vs, side='right') - 1
                col = vs - np.array([ids[j][0] for j in ring_of])
                cmin = int(round(c0g / (2.0 * np.pi) * K_RIM)) % K_RIM
                colw = np.where(col < cmin, col + K_RIM, col) - cmin
                rings_here = sorted(set(ring_of.tolist()))
                ncol = int(colw.max()) + 1
                G = np.zeros((len(rings_here), ncol, 3))
                for a_, j in enumerate(rings_here):
                    m_ = ring_of == j
                    G[a_, colw[m_]] = Pv[m_]
                uu = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(G, axis=1), axis=2).mean(0))])
                vv = np.concatenate([np.zeros((1, ncol)), np.cumsum(np.linalg.norm(np.diff(G, axis=0), axis=2), 0)])
                uv = np.column_stack([uu[colw], vv[[rings_here.index(j) for j in ring_of], colw]])
                d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
                if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
                    uv[:, 0] = -uv[:, 0]
                islands.append(dict(Q=loc[Qg], orig=vs, UV=uv / U.island_density(Pv, Fl, uv), quads=qid, share=share))
                continue
            uv = U.lscm(Pv, Fl)
            best, cand, done = None, uv, 0
            for it in (0, 2, 4, 8):
                if it > done:
                    cand, done = U.arap(Pv, Fl, cand, it - done), it
                if U.self_overlap(cand, Fl):
                    continue
                fp = U.footprint(Pv, Fl, cand)
                if best is None or fp < best[0]:
                    best = (fp, cand)
            uv = (best or (None, uv))[1]
            d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
            if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
                uv[:, 0] = -uv[:, 0]
            uv = uv / U.island_density(Pv, Fl, uv)                   # metres
            islands.append(dict(Q=loc[Qg], orig=vs, UV=uv, quads=qid, share=share))
    attr = np.zeros((len(mesh.V), 4))
    log(f'[peaked_cap] crown low: {len(mesh.V)} verts, {len(mesh.Q)} quads, {len(S)} rings (columns '
        f'{"/".join(str(s[3]) for s in S)}); {len(islands)} islands; check {mesh.check()}')
    return _piece(mesh.V, mesh.Q, region, attr, islands)


def _grid_islands(Vg, Qg, quads, share):
    """one island by LSCM (+ the flattest ARAP depth) over a quad grid (welded ids)"""
    from .. import uv as U
    vs = np.unique(Qg)
    loc = -np.ones(int(Qg.max()) + 1, np.int64)
    loc[vs] = np.arange(len(vs))
    Fl = U._tri(loc[Qg])
    Pv = Vg[vs]
    uv = U.lscm(Pv, Fl)
    best = None
    cand, done = uv, 0
    for it in (0, 3, 8):
        if it > done:
            cand, done = U.arap(Pv, Fl, cand, it - done), it
        if U.self_overlap(cand, Fl):
            continue
        fp = U.footprint(Pv, Fl, cand)
        if best is None or fp < best[0]:
            best = (fp, cand)
    uv = (best or (None, uv))[1]
    d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        uv[:, 0] = -uv[:, 0]
    return dict(Q=loc[Qg], orig=vs, UV=uv / U.island_density(Pv, Fl, uv), quads=quads, share=share)


def _relax_island(V, isl, iters=(0, 3, 8)):
    """cap v6: an island's UVs (its split quads isl['Q'] over the welded points V[isl['orig']]) re-solved by LSCM and the
    flattest ARAP depth that lies flat (_grid_islands' way), in metres: the analytic ring UVs of the bigger knots'
    swollen barrels stretched their girth 4.4 x (the footprint), the loops' end islands and the buttons' 1.9 x"""
    from .. import uv as U
    P = V[isl['orig']]
    Fl = U._tri(isl['Q'])
    uv = U.lscm(P, Fl)
    best, cand, done = None, uv, 0
    for it in iters:
        if it > done:
            cand, done = U.arap(P, Fl, cand, it - done), it
        if U.self_overlap(cand, Fl):
            continue
        fp = U.footprint(P, Fl, cand)
        if best is None or fp < best[0]:
            best = (fp, cand)
    if best is None or best[0] >= U.footprint(P, Fl, isl['UV']):
        return isl
    uv = best[1]
    d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        uv[:, 0] = -uv[:, 0]
    return dict(isl, UV=uv / U.island_density(P, Fl, uv))


def visor_columns(s, u_e, Pe, re, spec=SPEC, clear=0.0008):
    """the visor grids' boundary kept off the rolled rim (the rim strip's sections start on the visor's top, `clear`
    off the rim's round, and wrap it from there). Returns the columns' s (the top's and the underside's ALIKE) and the
    top grid's outer xi per column.
    * The columns: the outer edge's equal-arc columns s drawn in toward the centre proportionally (no two cross), by
      the least factor that keeps the END columns, every row of them, re + clear off the rim's axis (on the end edge
      itself the end sections began under the rim and folded back across it, forge 10-21).
    * The grids' outer row: 2 mm in from the edge along the spoke, or nearer the root where that point lies within
      re + clear of the rim's axis; the underside's outer row takes the same xi, so each rim section's ends lie across
      the visor from each other, square to the rim. The rim's ring points lie on its round by construction; only those
      sunk in the visor go out onto the visor alone"""
    from scipy.spatial import cKDTree
    tree = cKDTree(Pe)
    inset_t = 0.0020
    root = spec['visor_root']
    need = re + clear
    tt = VISOR_ROWS

    def outer_xi(sc):
        L = float(visor_L(sc, spec))
        xs = np.linspace(L - inset_t, 0.35 * L, 200)
        P, _ = visor_top(np.full(len(xs), sc), xs, spec)
        ok = tree.query(P)[0] >= need
        return float(xs[np.argmax(ok)]) if ok.any() else float(xs[-1])

    def end_gap(f):
        sc = float(s[0]) * f
        xo = outer_xi(sc)
        xi = -root + (xo + root) * tt
        ss = np.full(len(xi), sc)
        n = visor_normal(ss, np.maximum(xi, 0.0), spec)          # the grid's own points (visor_piece)
        P = visor_mid(ss, xi, spec) + visor_half(ss, xi, spec)[:, None] * n
        return float(tree.query(P)[0].min())

    f = 1.0 - inset_t / u_e
    while end_gap(f) < need and f > 0.85:
        f -= 0.002
    Sc = np.asarray(s, np.float64) * f
    XIo = np.array([outer_xi(sc) for sc in Sc])
    # cap v3: the outer row's inset from the edge smoothed over the interior columns (its upper envelope: a row never
    # moves toward the cord). Where the cord's footprint along the oblique spokes starts to reach past 5 mm (s +-0.4) the
    # row stepped in by a column and the rim strip's sections turned 9-11 deg there: facets on the rim at 40 mm framing
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    Ls = visor_L(Sc, spec)
    dI = Ls - XIo
    dS = gaussian_filter1d(maximum_filter1d(dI, 5, mode='nearest'), 2.0, mode='nearest')
    keep = np.zeros(len(Sc), bool)
    keep[[0, -1]] = True
    XIo = np.where(keep, XIo, np.minimum(XIo, Ls - dS))
    return Sc, XIo


def visor_piece(spec=SPEC, prog=None, log=print):
    """the visor's designed low: its top and its underside as (s, xi) grids (VISOR_COLS columns along the outer edge,
    denser where it turns, VISOR_ROWS from the buried root out), and a RIM strip round its boundary (up one end, along
    the edge, down the other) whose section runs from the top grid's outer row over the rolled rim's crest (120 and 60
    deg on its round) and round the plate's own rounded edge (its shoulders at +-45 deg) to the underside grid's outer
    row. ATTR = (s, tau = xi / L, xi, 1)"""
    ns, nr = VISOR_COLS, len(VISOR_ROWS)
    s = visor_s_arc(ns, spec, VISOR_CURV)
    Pe, Ne, re = rim_curve(spec)
    inset_t = 0.0020
    tt = VISOR_ROWS
    u_e = float(phi_to_u(dims(spec)['phi_e'], spec))
    Sc, XIo = visor_columns(s, u_e, Pe, re, spec)
    Sg, T = np.meshgrid(Sc, tt, indexing='ij')
    # the grids land on the visor's own surface (on the visor and the cord together, a grid point near the cord could
    # settle on the cord's fillet)
    pv = build_sdf(spec, parts=('visor',)) if prog is not None else None
    out = []
    for side in (1.0, -1.0):
        XI = -spec['visor_root'] + (XIo[:, None] + spec['visor_root']) * T
        n = visor_normal(Sg, np.maximum(XI, 0.0), spec)
        P = visor_mid(Sg, XI, spec) + side * visor_half(Sg, XI, spec)[..., None] * n
        if pv is not None:
            P = _project(pv, P.reshape(-1, 3), (side * n).reshape(-1, 3))[0].reshape(P.shape)
        out.append((P, XI, n, Sg))
    Ptop, XIt, ntop, St = out[0]
    Pund, XIu, nund, Su = out[1]
    # the boundary loop (excluding the root row) on each grid: column 0 root -> edge, the edge row, column -1 edge -> root
    loop = [(0, j) for j in range(nr)] + [(i, nr - 1) for i in range(1, ns)] + [(ns - 1, j) for j in range(nr - 2, -1, -1)]
    from scipy.spatial import cKDTree
    a_list = np.radians([120.0, 60.0])         # the rim's crest; its lower round lies inside the plate's rounded edge
    Tg = _unit(np.gradient(Pe, axis=0))
    Bl = np.array([Ptop[i, j] for i, j in loop])
    # each loop point's cord station: the nearest, then made strictly increasing along the loop (the nearest ones
    # repeated at the corners and the buried root ends, and the strip's quads there came out degenerate and folded:
    # 18 folds, zero-length edges, smoke 10-21)
    cis = cKDTree(Pe).query(Bl)[1].astype(np.int64)
    for k in range(1, len(cis)):
        cis[k] = max(cis[k], cis[k - 1] + 2)
    cis[-1] = min(cis[-1], len(Pe) - 1)
    for k in range(len(cis) - 2, -1, -1):
        cis[k] = min(cis[k], cis[k + 1] - 2)

    def inward(i, j):
        return (1 if i == 0 else (ns - 2 if i == ns - 1 else i)), (nr - 2 if j == nr - 1 else j)
    secs = []
    for k, (i, j) in enumerate(loop):
        b = Bl[k]
        c, Tc = Pe[cis[k]], Tg[cis[k]]
        up = _unit(Ne[cis[k]] - Tc * np.dot(Ne[cis[k]], Tc))
        # outward = across the loop in the visor's plane, away from the grid's interior (by the grid itself: the sign
        # from the cord's offset was a coin toss at the root ends, where the cord runs along the loop)
        tl = _unit(Bl[min(k + 1, len(loop) - 1)] - Bl[max(k - 1, 0)])
        o = np.cross(tl, ntop[i, j])
        if np.dot(o, b - Ptop[inward(i, j)]) < 0.0:
            o = -o
        outv = _unit(np.cross(Tc, up))
        if np.dot(outv, o) < 0.0:
            outv = -outv
        # the rim's crest on its own round (its sweep's section about this station): exact by construction
        ring = [b] + [c + re * (np.cos(a) * outv + np.sin(a) * up) for a in a_list]
        # past the crest, the plate's own ROUNDED EDGE (the shell rounds its boundary by its half-thickness): its upper
        # and lower shoulders at +-45 deg about the mid-surface's edge line, on the edge this loop point lies across
        # from (the outline for the edge row, the end edge s = -+1 for the end columns)
        s_e = (-1.0 if i == 0 else (1.0 if i == ns - 1 else float(St[i, j])))
        xi_e = float(visor_L(s_e, spec)) if j == nr - 1 else float(XIt[i, j])
        E = visor_mid(s_e, xi_e, spec)
        n_e = visor_normal(s_e, max(xi_e, 0.0), spec)
        o_e = _unit(outv - n_e * np.dot(outv, n_e))
        h_e = float(visor_half(s_e, xi_e, spec))
        d_up, d_dn = _unit(o_e + n_e), _unit(o_e - n_e)
        Ed = np.array([E + h_e * d_up, E + h_e * d_dn])
        if pv is not None:
            Ed = _project(pv, Ed, np.array([d_up, d_dn]))[0]
        ring += [Ed[0], Ed[1]]
        ring.append(Pund[i, j])
        secs.append(np.array(ring))
    secs = np.array(secs)                                          # (n_loop, m, 3)
    m = secs.shape[1]
    # assemble: top grid, under grid, rim's middle points (the rim's first and last points ARE grid vertices)
    nt = ns * nr
    V = [Ptop.reshape(-1, 3), Pund.reshape(-1, 3), secs[:, 1:-1].reshape(-1, 3)]
    gid = lambda i, j: i * nr + j
    Q, reg, isl_q = [], [], {}
    for g, off in ((0, 0), (1, nt)):
        qq = []
        for i in range(ns - 1):
            for j in range(nr - 1):
                q = [off + gid(i, j), off + gid(i + 1, j), off + gid(i + 1, j + 1), off + gid(i, j + 1)]
                qq.append(q if g == 0 else q[::-1])
        isl_q[g] = (len(Q), len(Q) + len(qq))
        Q += qq
        reg += [R_['visor_top'] if g == 0 else R_['visor_under']] * len(qq)
    rim0 = 2 * nt
    nm = m - 2

    def rim_id(li, k):
        i, j = loop[li]
        if k == 0:
            return gid(i, j)
        if k == m - 1:
            return nt + gid(i, j)
        return rim0 + li * nm + (k - 1)
    q0 = len(Q)
    for li in range(len(loop) - 1):
        for k in range(m - 1):
            Q.append([rim_id(li, k), rim_id(li, k + 1), rim_id(li + 1, k + 1), rim_id(li + 1, k)])
    isl_q[2] = (q0, len(Q))
    reg += [R_['visor_rim']] * (len(Q) - q0)
    V = np.concatenate(V)
    Q = np.array(Q, np.int64)
    # the winding: the top grid faces up; the rim follows the grids (each of its boundary edges the grid's the other
    # way round: built the same way round, all 60 were duplicated, smoke 10-21)
    if QuadMesh(V, Q).face_normals()[:isl_q[0][1]][:, 1].sum() < 0.0:
        Q = Q[:, ::-1].copy()
    a2, b2 = isl_q[2]
    if QuadMesh(V, Q).check()['flipped_or_dup_directed'] > 0:
        Q[a2:b2] = Q[a2:b2, ::-1]
    mesh = QuadMesh(V, Q)
    # the rim's island unrolled analytically: u along the cord's centreline, v round the section from its outermost
    # point (a straight strip that packs: LSCM bends an annular strip into an arc)
    nl = len(loop)
    u_l = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pe[cis], axis=0), axis=1))])
    v_l = np.concatenate([np.zeros((nl, 1)), np.cumsum(np.linalg.norm(np.diff(secs, axis=1), axis=2), axis=1)], 1)
    k_out = 1 + int(np.argmin(np.abs(a_list)))
    v_l = v_l - v_l[:, k_out:k_out + 1]
    orig_r = np.array([[rim_id(li, k) for k in range(m)] for li in range(nl)]).ravel()
    sid = np.arange(nl * m).reshape(nl, m)
    Q_r = np.stack([sid[:-1, :-1], sid[:-1, 1:], sid[1:, 1:], sid[1:, :-1]], -1).reshape(-1, 4)
    if not np.array_equal(orig_r[Q_r[0]], Q[a2]):
        Q_r = Q_r[:, ::-1].copy()
    UV_r = np.stack([np.repeat(u_l[:, None], m, 1), v_l], -1).reshape(-1, 2)
    d1, d2 = UV_r[Q_r[:, 1]] - UV_r[Q_r[:, 0]], UV_r[Q_r[:, 2]] - UV_r[Q_r[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        UV_r[:, 0] = -UV_r[:, 0]
    islands = [_grid_islands(V, Q[a:b], np.arange(a, b), 1.0) for (a, b) in (isl_q[0], isl_q[1])]
    islands.append(dict(Q=Q_r, orig=orig_r, UV=UV_r, quads=np.arange(a2, b2), share=1.0))
    attr = np.zeros((len(V), 4))
    attr[:, 3] = 1.0
    SS = np.concatenate([St.ravel(), Su.ravel(), np.repeat([St[i, j] for i, j in loop], nm)])
    XX = np.concatenate([XIt.ravel(), XIu.ravel(), np.repeat([XIt[i, j] + inset_t * 0.8 for i, j in loop], nm)])
    attr[:, 0] = SS
    attr[:, 2] = XX
    attr[:, 1] = XX / visor_L(SS, spec)
    log(f'[peaked_cap] visor low: {len(V)} verts, {len(Q)} quads (top {isl_q[0][1] - isl_q[0][0]}, under '
        f'{isl_q[1][1] - isl_q[1][0]}, rim {isl_q[2][1] - isl_q[2][0]}); check {mesh.check()}')
    return _piece(V, Q, reg, attr, islands)


def _stations(P, step, turn_deg=10.0):
    """indices along a dense polyline: every `step` of arc, and wherever it has turned turn_deg since the last"""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    keep = [0]
    for i in range(1, len(P) - 1):
        t0 = _unit(P[i] - P[keep[-1]])
        t1 = _unit(P[i + 1] - P[i])
        if s[i] - s[keep[-1]] >= step or np.degrees(np.arccos(np.clip(np.dot(t0, t1), -1, 1))) > turn_deg:
            keep.append(i)
    keep.append(len(P) - 1)
    return np.array(keep), s


def cord_piece(spec=SPEC, log=print):
    """the two chin cords' lows: 8-round tubes on the SWEEPs' radius, a station every 7 mm on the straight runs and
    wherever the path turns 12 deg (the climbs, the eyes; the 3-ply twist is the bake's). Unique texels (a twisted cord
    mirrored would twist the wrong way); islands at most 100 mm long. ATTR = (s, cos theta, sin theta, 2 upper / 3
    lower)"""
    from .round_glasses import ring_tube
    paths, _ = cord_paths(spec)
    r = 0.5 * spec['cord_d']
    out = []
    for k, nm in enumerate(('upper', 'lower')):
        P, N = paths[nm]
        # a station every 14 mm and wherever the path turns 18 deg (cap v6; v5 11.5 mm / 16, v4 7 mm / 12): the low keeps
        # DESIGN.md's 6k with the crown's doubled rim (a 14 mm chord on the band's ~95 mm curvature sags 0.26 mm, inside
        # the 8.3 mm tube's 8-gon sag of 0.32 mm; the rope's plies stand proud of the tube by up to 0.1 mm anyway)
        sel, s = _stations(P, 0.0140, 18.0)
        # islands of EQUAL length (a fixed 100 mm left a two-station end island of 154 texels, which two missed texels
        # failed in the gate, forge 10-21)
        L_tot = float(s[sel][-1] - s[sel][0])
        cut = L_tot / np.ceil(L_tot / 0.10) + 0.004
        # the seam column against the band (theta 0 is the band's outward normal: there it ran down the cords'
        # outermost line, forge 10-21)
        V, Q, attr, isl = ring_tube(P[sel], N[sel], lambda i, th: r, 8, s=s[sel], theta0=np.pi, part=2.0 + k,
                                    cut_len=cut)
        isl = [_relax_island(V, d_) for d_ in isl]            # cap v6: the loops' tight turns (footprint 1.9)
        out.append(_piece(V, Q, R_['cord'], attr, isl))
    log(f'[peaked_cap] cords low: ' + ', '.join(f'{len(p["Q"])} quads' for p in out))
    return out


def knot_piece(spec=SPEC, log=print):
    """the LEFT sliding knot's low (the right mirrors it, stacked): a 12-round barrel over the SWEEP's elliptic
    section, 3 x 3 grid caps on its ends lifted onto the sweep's end domes. ATTR = (s, cos, sin, 4)"""
    from .. import loft
    from .round_glasses import ring_tube
    P, N, r0, asp = knot_curve(spec, 1)
    sel = np.linspace(0, len(P) - 1, 9).round().astype(int)
    sect = lambda i, th: r0[sel][i] * asp[sel][i] / np.sqrt(asp[sel][i] ** 2 * np.cos(th) ** 2 + np.sin(th) ** 2)
    # u by the barrel's MERIDIAN length (along the axis it stretched the swell's steep ends 3x, smoke 10-21)
    rm = np.array([np.mean([sect(i, t) for t in 2.0 * np.pi * np.arange(12) / 12]) for i in range(len(sel))])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.linalg.norm(np.diff(P[sel], axis=0), axis=1), np.diff(rm)))])
    V, Q, attr, isl = ring_tube(P[sel], N[sel], sect, 12, s=s, theta0=np.pi, part=4.0, cut_len=0.05)   # seam inward
    isl = [_relax_island(V, d_) for d_ in isl]                # cap v6: the swollen barrel's girth (footprint 4.4)
    m = QuadMesh(V, Q, {'attr': attr})
    nq = len(Q)
    caps = []
    for end, ring in ((0, np.arange(12)), (1, np.arange(len(V) - 12, len(V)))):
        ax = _unit(P[sel][0] - P[sel][1]) if end == 0 else _unit(P[sel][-1] - P[sel][-2])
        nq_before = len(m.Q)
        # the dome 0.9 of the sweep's cap (its end radius along the outward meridian): the low reads the knot's 17 mm
        m, G = loft.cap(m, ring, ax, dome=0.9 * r0[sel][0 if end == 0 else -1])
        caps.append((G, nq_before, len(m.Q), ax))
    for G, a, b, ax in caps:
        vs = np.unique(G)
        loc = -np.ones(len(m.V), np.int64)
        loc[vs] = np.arange(len(vs))
        e1 = _unit(np.cross(ax, [0.0, 1.0, 0.0]))
        e2 = np.cross(ax, e1)
        c = m.V[vs].mean(0)
        isl.append(dict(Q=loc[m.Q[a:b]], orig=vs, UV=np.column_stack([(m.V[vs] - c) @ e1, (m.V[vs] - c) @ e2]),
                        quads=np.arange(a, b), share=1.0))
    for d_ in isl:
        d_['share'] = KNOT_SHARE                     # the braid's threads, 0.5 mm apart, need 3 texels (cap v2)
    log(f'[peaked_cap] knot low: {len(m.V)} verts, {len(m.Q)} quads ({nq} barrel)')
    return _piece(m.V, m.Q, R_['knot'], m.attrs['attr'], isl)


def button_piece(spec=SPEC, log=print):
    """the LEFT button's low (the right mirrors it, stacked): a 16-round revolve of the head's profile from its flat
    underside (on the cords' loop; the shank under it is hidden by the loop and the head) over the rim and the dome, a
    4 x 4 grid cap at the dome's crown lifted onto it"""
    from .round_glasses import revolve_piece
    c, n = button_frame(spec, 1)
    rb, h = 0.5 * spec['button_d'], spec['button_h']
    dome = lambda r: 0.0008 + (h - 0.0008) * (1.0 - (r / (rb - 0.0002)) ** 2) ** 0.85
    prof = np.array([[0.5 * spec['shank_d'], 0.0], [rb - 0.0012, 0.0], [rb - 0.00015, 0.00012], [rb, 0.0006],
                     [rb - 0.0012, dome(rb - 0.0012)], [rb - 0.0030, dome(rb - 0.0030)], [0.0019, dome(0.0019)]])
    e1 = _unit(np.cross(n, [0.0, 1.0, 0.0]))
    # 16 round (cap v6: the buttons sit behind the bulky knots at the band's silhouettes, their 0.11 mm sag hidden there;
    # the triangles went to the crown's rim. Cap v2 took 20 for the buttons by the visor's ends, seen at 50 mm framing)
    V, Q, reg, attr, isl = revolve_piece(prof, c, n, 16, e1=e1, cap1=True, region_of=lambda j: R_['button'],
                                         part=5.0, cuts=[8])
    loc_r = np.linalg.norm((V - c) - np.outer((V - c) @ n, n), axis=1)
    top = ((V - c) @ n > 0.5 * h) & (loc_r < 0.0019 - 1e-7)
    V[top] = V[top] + np.outer(dome(loc_r[top]) - (V[top] - c) @ n, n)
    isl = [_relax_island(V, d_) for d_ in isl]                # cap v6: the dome's annular halves (footprint 1.9)
    log(f'[peaked_cap] button low: {len(V)} verts, {len(Q)} quads')
    return _piece(V, Q, R_['button'], attr, isl)


def cockade_piece(spec=SPEC, log=print):
    """the cockade's low: a 40-round revolve of its EDGE (the buried foot, the side, the rim's rounded top edge) closed
    by a 10 x 10 grid cap over its FACE, flat at the rim's height (the face's relief, the steps down to the field and
    the enamel, the rye and the arms, is the bake's: 0.45 mm at most). The face is ONE PLANAR island, its UVs the face's
    own (u, v) in metres (square-on: the emblem's texels undistorted), at COCKADE_SHARE (~13 px/mm); the edge strip's two
    halves are islands of their own at the same density. The 40-gon's sag on the 13.2 mm rim is 0.04 mm"""
    from .round_glasses import revolve_piece
    c, n = cockade_frame(spec)
    R = 0.5 * spec['cockade_d']
    zr = CK_Z['rim']
    prof = np.array([[R - 0.0002, -0.0004], [R, 0.0003], [R, zr - 0.0004], [R - 0.00012, zr - 0.00012],
                     [R - 0.0004, zr]])
    V, Q, reg, attr, isl = revolve_piece(prof, c, n, 40, e1=np.array([1.0, 0.0, 0.0]), cap1=True,
                                         region_of=lambda j: R_['cockade'], part=6.0, cuts=[20],
                                         share=COCKADE_SHARE)
    log(f'[peaked_cap] cockade low: {len(V)} verts, {len(Q)} quads (the face a planar island)')
    return _piece(V, Q, R_['cockade'], attr, isl)


def _mirror_piece(pc):
    """the right copy of a left piece: x mirrored, winding flipped, its islands SHARED (stacked)"""
    V = pc['V'].copy()
    V[:, 0] = -V[:, 0]
    return dict(pc, V=V, Q=pc['Q'][:, ::-1].copy())


def build_low(spec=SPEC, prog=None, log=print):
    """the designed low: the crown, the visor, the two cords, the cockade (unique texels), the left knot and button and
    their mirrors (stacked). prog (optional): the block-out, whose parts' own programs the crown's and the visor's
    points are projected onto. Returns a dict: V, Q (welded), region per quad, ATTR, the split mesh (orig, UV in
    metres, island per split quad, share per island, groups), side per quad, names"""
    progs = {}
    if prog is not None:
        progs['crown'] = build_sdf(spec, parts=('crown', 'pipings'))
        progs['visor'] = build_sdf(spec, parts=('visor', 'edge'))
    pieces = [('crown', crown_piece(spec, progs.get('crown'), log=log)),
              ('visor', visor_piece(spec, progs.get('visor'), log=log))]
    pieces += [(f'cord_{k}', p) for k, p in zip(('upper', 'lower'), cord_piece(spec, log=log))]
    pieces.append(('cockade', cockade_piece(spec, log=log)))
    left = [('knot', knot_piece(spec, log=log)), ('button', button_piece(spec, log=log))]
    Vs, Qs, R, A, S = [], [], [], [], []
    split = dict(Q=[], orig=[], UV=[], island=[], wq=[], share=[], groups=[])
    cnt = dict(v=0, q=0, s=0, isl=0)

    def add(pc, side, isl_ids=None):
        Q_ = pc['Q']
        Vs.append(pc['V'])
        Qs.append(Q_ + cnt['v'])
        R.append(pc['region'])
        A.append(pc['attr'])
        S.append(np.full(len(Q_), side))
        ids_here = []
        for k_, isl in enumerate(pc['islands']):
            Qi = isl['Q'] if side >= 0 else isl['Q'][:, ::-1]
            iid = cnt['isl'] if isl_ids is None else isl_ids[k_]
            if isl_ids is None:
                split['share'].append(isl['share'])
                cnt['isl'] += 1
            split['Q'].append(Qi + cnt['s'])
            split['orig'].append(isl['orig'] + cnt['v'])
            split['UV'].append(isl['UV'])
            split['island'].append(np.full(len(Qi), iid))
            split['wq'].append(isl['quads'] + cnt['q'])
            split['groups'].append((iid, cnt['s'], len(isl['orig'])))
            ids_here.append(iid)
            cnt['s'] += len(isl['orig'])
        cnt['v'] += len(pc['V'])
        cnt['q'] += len(Q_)
        return ids_here
    names, ranges = [], {}
    for nm, pc in pieces:
        v_before = cnt['v']
        add(pc, 0)
        ranges[nm] = (v_before, cnt['v'])
        names.append(nm)
    for nm, pc in left:
        ids_ = add(pc, 1)
        add(_mirror_piece(pc), -1, ids_)
        names += [nm + '_L', nm + '_R']
    low = dict(V=np.concatenate(Vs), Q=np.concatenate(Qs), region=np.concatenate(R), attr=np.concatenate(A),
               side=np.concatenate(S), names=names,
               split=dict(Q=np.concatenate(split['Q']), orig=np.concatenate(split['orig']),
                          UV=np.concatenate(split['UV']), island=np.concatenate(split['island']),
                          wq=np.concatenate(split['wq']), share=np.asarray(split['share']), groups=split['groups']))
    # ATTR per SPLIT vertex, each piece's own (before the weld below gives the lower cord's end rings the upper's)
    low['split']['attr'] = low['attr'][low['split']['orig']]
    # the two cords meet head-on behind each button (the upper over it, the lower under it) and their END rings (the
    # first and last 8 vertices of each tube) meet there: WELDED, each loop is one surface (as two open rings their
    # normals were one-sided and the junction read as a crack across the loop, forge 10-21). Each tube's end frame comes
    # from its own last segment, so the rings stand turned (the left loop's 0.15 mm apart, the right's up to 1.13 mm):
    # each lower-cord end vertex is snapped to its nearest upper-cord end vertex within 0.45 of the cord's radius (the
    # pairing comes out the mirror one, 0-0, 1-7, 2-6, ...; under half the ring's vertex spacing, one to one: the 8.3 mm
    # cord's rings stand tilted up to 1.7 mm, weld_probe.py, cap v4); kept only if every end vertex pairs and the mesh
    # stays manifold and consistent
    from scipy.spatial import cKDTree
    (a0, a1), (b0, b1) = ranges['cord_upper'], ranges['cord_lower']
    ends = lambda v0, v1: np.r_[v0:v0 + 8, v1 - 8:v1]
    ea, eb = ends(a0, a1), ends(b0, b1)
    dd_, jj_ = cKDTree(low['V'][ea]).query(low['V'][eb])
    ok_ = (dd_ < 0.225 * spec['cord_d']) if len(np.unique(jj_)) == len(jj_) else np.zeros(len(eb), bool)
    if not ok_.all():
        ok_[:] = False
    dup, tgt = eb[ok_], ea[jj_[ok_]]
    remap = np.arange(len(low['V']))
    remap[dup] = tgt
    keep = np.ones(len(low['V']), bool)
    keep[dup] = False
    final = (np.cumsum(keep) - 1)[remap]
    chk = QuadMesh(low['V'][keep], final[low['Q']]).check()
    if len(dup) and chk['flipped_or_dup_directed'] == 0 and chk['nonmanifold_edges'] == 0:
        low['Q'] = final[low['Q']]
        low['V'], low['attr'] = low['V'][keep], low['attr'][keep]
        low['split']['orig'] = final[low['split']['orig']]
        log(f'[peaked_cap] the cords welded behind the buttons: {len(dup)} end-ring vertices')
    else:
        log(f'[peaked_cap] the cords NOT welded ({len(dup)} coincident end-ring vertices; the welded check {chk})')
    mesh = QuadMesh(low['V'], low['Q'])
    log(f'[peaked_cap] low: {len(low["V"])} verts, {len(low["Q"])} quads ({2 * len(low["Q"])} tris); '
        + ', '.join(f'{REGIONS[r]} {int((low["region"] == r).sum()) * 2}' for r in range(len(REGIONS)))
        + f' tris; check {mesh.check()}')
    if prog is not None:
        for nm, pr in (('crown', progs['crown']), ('visor', progs['visor'])):
            sel = np.isin(low['region'], [R_['top'], R_['wall'], R_['band'], R_['inside']] if nm == 'crown' else
                          [R_['visor_top'], R_['visor_under'], R_['visor_rim']])
            f = pr.eval(low['V'][np.unique(low['Q'][sel])])
            log(f'[peaked_cap] {nm} low on its block-out: |sdf| p50 {np.median(np.abs(f)) * 1e6:.1f} um, p99 '
                f'{np.percentile(np.abs(f), 99) * 1e6:.1f} um, max {np.abs(f).max() * 1e6:.1f} um')
    return low


# ----------------------------------------------------------------------------------------------------------- UVs
def _min_box(uv):
    """cap v6: an island's UVs turned to their MINIMUM-AREA bounding rectangle (rotating calipers over the convex hull's
    edges), its long side along u: LSCM leaves each island at an arbitrary turn, and the skyline packer packs boxes (the
    band's quarter strips, turned ~30 deg, filled half their boxes)"""
    from scipy.spatial import ConvexHull
    uv = np.asarray(uv, np.float64)
    try:
        H = uv[ConvexHull(uv).vertices]
    except Exception:
        return uv
    E = np.roll(H, -1, axis=0) - H
    best = None
    for e in E:
        ln = np.hypot(e[0], e[1])
        if ln < 1e-12:
            continue
        c, s = e[0] / ln, e[1] / ln
        R = np.array([[c, s], [-s, c]])
        q = H @ R.T
        ext = q.max(0) - q.min(0)
        if best is None or ext[0] * ext[1] < best[0]:
            best = (ext[0] * ext[1], R if ext[0] >= ext[1] else np.array([[-s, c], [-c, -s]]))
    if best is None:
        return uv
    out = uv @ best[1].T
    return out - out.min(0)


def unwrap(low, size=2048, pad=8, log=print):
    """every island (each at density 1 already: metres) packed at ONE texel density times its share (the inside a
    quarter, the cockade twice); the right knot and button take their left twins' places (stacked). The density is
    searched so the sheet fills (uv.pack's skyline height 93-98.5 %), as top_hat's and round_glasses' unwraps do"""
    from .. import uv as U
    sp = low['split']
    n_isl = len(sp['share'])
    first = {}
    for iid, v0, nv in sp['groups']:
        first.setdefault(iid, (v0, nv))
    uvs = [_min_box(sp['UV'][first[i][0]:first[i][0] + first[i][1]]) for i in range(n_isl)]
    area = 0.0
    for i in range(n_isl):
        q = sp['Q'][sp['island'] == i]
        v0 = first[i][0]
        mine = (q >= v0).all(1) & (q < v0 + first[i][1]).all(1)
        Pq = low['V'][sp['orig'][q[mine]]]
        area += 0.5 * np.linalg.norm(np.cross(Pq[:, 2] - Pq[:, 0], Pq[:, 3] - Pq[:, 1]), axis=1).sum() * \
            sp['share'][i] ** 2
    # the density: grown toward the fill, then BISECTED between the densest pack that fitted and the least that did
    # not (a fixed 15 % step back after every overflow left the sheet 84 % full at 3072 px/m, forge 10-21)
    px = np.sqrt(0.62 * size * size / area)
    fit_px, over_px, best = 0.0, np.inf, None
    for _ in range(28):
        try:
            pk, used = U.pack(uvs, [px * sp['share'][i] for i in range(n_isl)], size, pad)
        except ValueError:
            pk, used = None, 9.9
        if used <= 0.985:
            if best is None or px > best[0]:
                best = (px, pk, used)
            fit_px = max(fit_px, px)
            if used >= 0.93:
                break
        else:
            over_px = min(over_px, px)
        if np.isfinite(over_px) and fit_px > 0.0:
            if over_px - fit_px < 0.002 * over_px:
                break
            px = 0.5 * (fit_px + over_px)
        else:
            px *= (0.965 / used) ** 0.5 if used < 9.0 else 0.85
    while best is None:
        px *= 0.9
        try:
            pk, used = U.pack(uvs, [px * sp['share'][i] for i in range(n_isl)], size, pad)
            if used <= 1.0:
                best = (px, pk, used)
        except ValueError:
            pass
    px, packed, used = best
    UV = np.zeros_like(sp['UV'])
    for iid, v0, nv in sp['groups']:
        UV[v0:v0 + nv] = packed[iid]
    worst, over = 0.0, 0
    for i in range(n_isl):
        v0, nv = first[i]
        q = sp['Q'][(sp['island'] == i)]
        q = q[(q >= v0).all(1) & (q < v0 + nv).all(1)] - v0
        F = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
        Pv = low['V'][sp['orig'][v0:v0 + nv]]
        worst = max(worst, U.footprint(Pv, F, packed[i]))
        over += U.self_overlap(packed[i], F, res=256)
    log(f'[peaked_cap] uv: {n_isl} islands (the right knot and button stacked on the left), {px:.0f} px/m at {size} '
        f'({1000 / px:.3f} mm/texel; the inside {px * INNER_SHARE:.0f}, the cockade {px * COCKADE_SHARE:.0f}), '
        f'height used {used * 100:.0f} %, worst footprint p95 {worst:.2f}, self-overlapping texels {over}')
    return dict(UV=UV, px_per_m=float(px), size=size, used=float(used))


def low_arrays(low, uvs):
    """the export's arrays per SPLIT vertex: triangles along each quad's shorter diagonal, normals from the WELDED
    low, MikkT-style tangents, the region and side per triangle, ATTR, and 'bake': the triangles the bake and the paint
    see, the UNIQUE copies (the right knot and button lie on their left twins' texels: baked together, each texel took
    whichever copy its UV ray met first, the mirror's tangent-space normals in patches across both, forge 10-21;
    round_glasses bakes its left half the same way)"""
    from .. import bake
    sp = low['split']
    Vn = low['V'][sp['orig']]
    Qn = sp['Q']
    d02 = np.linalg.norm(Vn[Qn[:, 0]] - Vn[Qn[:, 2]], axis=1)
    d13 = np.linalg.norm(Vn[Qn[:, 1]] - Vn[Qn[:, 3]], axis=1)
    short = d02 <= d13
    F = np.concatenate([np.where(short[:, None], Qn[:, [0, 1, 2]], Qn[:, [0, 1, 3]]),
                        np.where(short[:, None], Qn[:, [0, 2, 3]], Qn[:, [1, 2, 3]])])
    fq = np.concatenate([sp['wq'], sp['wq']])
    Nw = QuadMesh(low['V'], low['Q']).vertex_normals()
    N, TAN = bake.low_frames(Vn, F, uvs['UV'], Nw[sp['orig']])
    return dict(V=Vn, F=F, UV=uvs['UV'], N=N, TAN=TAN, region=low['region'][fq].astype(np.int32),
                side=low['side'][fq], ATTR=sp['attr'] if 'attr' in sp else low['attr'][sp['orig']], orig=sp['orig'],
                bake=low['side'][fq] >= 0,
                px_per_m=uvs['px_per_m'], size=uvs['size'])


# --------------------------------------------------------------------------------------------------- sculpt plan
# cap v8 (the lead's decision 1: "THE LEAVES TRACED, not described ... the way the cockade was built: outlines measured on
# the photo, then relief"): every leaf of both sprays TRACED BY EYE on Skye's egmar3b in her pixels (on 10x-16x zooms and
# their high-passed relief, research/cap_gdr_work/v8_*_x*.png; the free edges snapped onto her photo's own gold/red
# contour), each leaf's VISIBLE region (the regions tile her gold: IoU 0.973 with her gold class above the cords, off the
# cockade), its MIDRIB from the base to the tip (her beaded lines and ridges) and the ACORN KNOBS, back-projected through
# t27's camera fitted to the photo onto the band lifted 2.2 mm (research/cap_gdr_scripts/v8_trace.py, cap_gdr_work/
# v8_leaves_trace.json -> v8_leaves_band.json) [M egmar3b]. Band coordinates (u along the band's face from the front, +
# toward the wearer's left = the viewer's right; y up from the band's foot), mm. FIVE leaves a side fan from the base
# where the stalks cross: the INNER leaf rising beside the cockade, its tip curling in over it (17-18 mm across its lobes,
# its midrib bowed out), the SECOND (13 mm), a slender MIDDLE leaf (7 mm) whose beaded midrib ends in a knob between the
# second and the inner, the THIRD and the FOURTH (along the cords); red shows between their upper halves. Each: (name,
# layer (higher lies on top), its visible outline, its midrib from the base to the tip). v4-v7 drew four leaves a side
# from an analytic law (an envelope with N lobes a side: v6 8-8.5 small, v7 4-5 big pillowed): her leaves are neither
LEAF_TRACE = (
    ('VL inner', 3,
     ((-26.4, 48.9), (-25.2, 50.0), (-23.9, 50.8), (-23.5, 52.1), (-23.7, 53.5), (-23.8, 54.8), (-23.8, 56.2),
      (-23.6, 57.6), (-23.1, 59.0), (-22.4, 60.3), (-21.3, 61.3), (-20.0, 61.8), (-18.7, 62.0), (-17.6, 62.9),
      (-17.1, 64.2), (-16.7, 65.6), (-16.4, 66.9), (-15.5, 68.1), (-14.3, 68.7), (-13.0, 68.8), (-11.9, 68.4),
      (-10.7, 68.0), (-9.5, 68.4), (-8.2, 68.7), (-7.0, 68.5), (-5.9, 68.0), (-5.2, 67.0), (-4.9, 65.8),
      (-4.8, 64.4), (-5.4, 63.2), (-6.0, 62.0), (-6.7, 60.8), (-6.4, 59.6), (-6.2, 58.3), (-6.6, 57.0),
      (-7.7, 56.2), (-9.0, 56.0), (-10.3, 55.9), (-11.0, 54.9), (-10.5, 53.7), (-10.6, 52.4), (-11.5, 51.3),
      (-12.6, 50.4), (-13.8, 49.6), (-14.5, 48.4), (-14.9, 45.6), (-15.4, 42.6), (-15.8, 40.0), (-15.9, 37.5),
      (-14.7, 36.5), (-13.7, 34.9), (-12.7, 32.9), (-11.3, 30.8), (-10.1, 28.9), (-8.6, 26.9), (-6.7, 24.9),
      (-4.4, 23.4), (-1.8, 22.4), (-0.5, 21.8), (-0.6, 20.9), (-1.5, 21.1), (-4.2, 21.6), (-7.8, 22.2),
      (-11.5, 23.3), (-14.8, 24.9), (-17.2, 27.4), (-18.8, 31.0), (-20.6, 34.2), (-22.6, 37.1), (-24.6, 39.8),
      (-25.9, 42.0), (-25.9, 43.2), (-26.3, 44.3), (-26.4, 45.6), (-26.7, 47.1), (-27.0, 48.3)),
     ((-0.9, 20.2), (-6.6, 20.6), (-10.6, 22.0), (-13.8, 24.1), (-16.4, 27.0), (-18.5, 30.9), (-20.1, 35.3),
      (-20.9, 39.9), (-20.8, 44.3), (-19.6, 49.1), (-18.0, 53.7), (-16.0, 57.9), (-13.6, 61.1), (-11.3, 64.2),
      (-9.6, 66.2), (-8.7, 67.6))),
    ('VL second', 2,
     ((-41.5, 44.5), (-40.0, 45.5), (-38.9, 46.9), (-38.6, 48.3), (-38.9, 49.6), (-39.4, 50.7), (-39.6, 52.0),
      (-39.7, 53.5), (-39.4, 54.9), (-38.6, 56.3), (-37.2, 57.3), (-35.7, 58.1), (-35.2, 59.5), (-34.2, 60.7),
      (-32.8, 61.4), (-31.4, 61.2), (-30.6, 60.2), (-30.2, 59.0), (-29.7, 57.8), (-29.3, 56.6), (-28.4, 55.7),
      (-27.5, 54.9), (-27.0, 53.9), (-27.1, 52.4), (-27.6, 51.0), (-28.0, 49.6), (-27.6, 48.3), (-26.9, 48.4),
      (-26.7, 47.1), (-26.4, 45.6), (-26.3, 44.3), (-27.2, 44.7), (-28.2, 44.4), (-29.1, 43.8), (-29.9, 42.9),
      (-30.7, 41.5), (-31.2, 40.4), (-33.5, 39.2), (-35.9, 39.4), (-37.7, 40.4), (-39.1, 42.0), (-40.4, 43.5)),
     ((-2.3, 19.1), (-6.6, 19.7), (-12.0, 21.3), (-17.3, 24.3), (-22.0, 28.2), (-26.1, 32.2), (-29.6, 35.7),
      (-32.0, 38.5), (-33.8, 41.0), (-33.8, 44.3), (-33.7, 47.6), (-33.9, 50.2), (-33.9, 56.3), (-33.1, 60.6))),
    ('VL mid', 4,
     ((-29.1, 43.8), (-28.2, 44.4), (-27.2, 44.7), (-26.3, 44.3), (-25.9, 43.2), (-25.9, 42.0), (-24.6, 39.8),
      (-22.6, 37.1), (-20.6, 34.2), (-18.8, 31.0), (-17.2, 27.4), (-14.8, 24.9), (-11.5, 23.3), (-7.8, 22.2),
      (-4.2, 21.6), (-1.5, 21.1), (-0.6, 20.9), (-0.7, 18.7), (-1.7, 18.7), (-5.3, 18.4), (-9.7, 19.1),
      (-14.1, 20.5), (-17.4, 22.9), (-18.1, 23.9), (-21.4, 26.7), (-24.9, 29.4), (-28.4, 32.0), (-30.9, 34.0),
      (-32.0, 36.4), (-31.7, 39.1), (-31.2, 40.4), (-30.7, 41.5), (-29.9, 42.9)),
     ((-0.7, 19.8), (-5.9, 20.1), (-10.0, 20.5), (-13.7, 21.6), (-16.7, 23.4), (-18.5, 25.6), (-20.0, 28.3),
      (-21.6, 30.9), (-23.3, 33.5), (-25.1, 36.0), (-26.7, 38.4), (-27.5, 40.8), (-27.5, 43.2))),
    ('VL third', 1,
     ((-44.7, 27.9), (-44.5, 29.5), (-44.6, 30.8), (-45.6, 31.7), (-47.1, 32.1), (-48.4, 32.8), (-49.3, 33.8),
      (-50.0, 34.8), (-49.9, 36.3), (-49.3, 37.9), (-48.9, 39.4), (-49.2, 40.7), (-48.9, 42.3), (-47.8, 43.8),
      (-46.0, 44.5), (-44.5, 44.3), (-43.1, 43.9), (-42.2, 44.0), (-40.4, 43.5), (-39.1, 42.0), (-37.7, 40.4),
      (-35.9, 39.4), (-33.5, 39.2), (-31.2, 40.4), (-31.7, 39.1), (-32.0, 36.4), (-30.9, 34.0), (-28.4, 32.0),
      (-24.9, 29.4), (-21.4, 26.7), (-18.1, 23.9), (-17.4, 22.9), (-18.1, 21.3), (-19.5, 19.4), (-21.3, 18.4),
      (-23.5, 18.4), (-26.4, 19.2), (-29.4, 20.5), (-32.3, 22.4), (-35.3, 24.1), (-38.5, 25.6), (-41.8, 26.7),
      (-45.2, 27.1)),
     ((-20.2, 19.1), (-23.4, 19.5), (-25.6, 20.6), (-29.0, 22.5), (-31.3, 24.6), (-33.7, 26.7), (-36.2, 28.7),
      (-38.8, 30.8), (-41.9, 33.9), (-44.8, 37.0), (-46.3, 40.2), (-47.4, 43.1))),
    ('VL fourth', 0,
     ((-54.8, 15.2), (-55.1, 16.5), (-56.5, 17.2), (-57.7, 18.0), (-58.8, 18.9), (-59.3, 20.1), (-58.9, 21.7),
      (-57.6, 23.4), (-55.8, 24.9), (-54.4, 26.5), (-52.5, 27.6), (-50.6, 28.0), (-48.9, 27.9), (-47.5, 27.5),
      (-46.0, 27.1), (-45.2, 27.1), (-41.8, 26.7), (-38.5, 25.6), (-35.3, 24.1), (-32.3, 22.4), (-29.4, 20.5),
      (-26.4, 19.2), (-23.5, 18.4), (-21.3, 18.4), (-19.5, 19.4), (-18.1, 21.3), (-17.4, 22.9), (-14.1, 20.5),
      (-9.7, 19.1), (-5.3, 18.4), (-1.7, 18.7), (-0.7, 18.7), (-0.8, 15.3), (-6.9, 15.0), (-11.4, 14.3),
      (-15.8, 15.6), (-19.6, 16.5), (-22.7, 14.3), (-26.1, 14.4), (-29.1, 14.0), (-33.8, 14.3), (-38.7, 14.6),
      (-43.9, 14.8), (-47.6, 14.9), (-51.5, 14.7), (-54.0, 14.5)),
     ((-1.1, 17.0), (-6.8, 16.6), (-11.6, 16.6), (-15.7, 17.5), (-19.9, 17.7), (-24.4, 16.7), (-28.9, 16.9),
      (-33.5, 17.7), (-38.4, 18.4), (-43.4, 19.5), (-48.8, 20.5), (-53.7, 20.9), (-58.1, 20.8))),
    ('VR inner', 3,
     ((11.9, 46.3), (13.0, 46.3), (14.1, 47.0), (15.0, 47.9), (15.1, 48.5), (14.2, 49.5), (13.3, 50.4),
      (12.3, 51.3), (11.6, 52.4), (11.5, 53.7), (11.8, 55.1), (11.0, 55.9), (9.8, 56.2), (8.6, 56.4),
      (7.4, 56.8), (6.8, 57.8), (7.2, 59.1), (7.8, 60.2), (7.8, 61.5), (7.2, 62.6), (6.4, 63.7), (5.9, 64.9),
      (6.1, 66.3), (6.7, 67.4), (7.8, 68.1), (9.0, 68.3), (10.1, 68.3), (11.3, 68.1), (12.5, 68.3), (13.7, 68.7),
      (14.9, 68.6), (16.0, 68.1), (17.0, 67.4), (17.7, 66.2), (18.1, 65.0), (18.3, 63.7), (18.6, 62.4),
      (19.6, 61.6), (20.8, 61.3), (21.9, 60.8), (23.0, 60.1), (23.6, 58.9), (23.9, 57.6), (24.2, 56.2),
      (24.3, 54.9), (24.4, 53.5), (24.2, 52.1), (24.2, 50.8), (24.9, 49.6), (26.0, 48.8), (26.8, 47.7),
      (27.3, 47.3), (27.4, 45.0), (27.5, 42.7), (27.3, 39.5), (26.8, 38.5), (25.8, 37.6), (24.4, 36.1),
      (21.8, 31.2), (18.4, 26.9), (13.5, 23.6), (8.8, 21.7), (5.0, 20.3), (1.1, 19.9), (0.1, 20.0), (0.1, 21.7),
      (0.8, 22.5), (2.9, 23.9), (5.3, 25.7), (7.7, 28.2), (9.7, 30.3), (10.5, 31.2), (11.2, 32.6), (12.2, 34.6),
      (14.1, 36.0), (15.6, 37.3), (15.9, 40.2), (15.2, 42.3), (13.4, 44.2)),
     ((0.4, 20.8), (5.4, 21.3), (9.4, 23.1), (12.8, 25.6), (15.8, 29.1), (18.3, 33.4), (20.1, 38.3),
      (20.7, 42.6), (20.6, 44.5), (19.5, 49.1), (17.7, 53.7), (15.4, 58.4), (12.8, 62.5), (10.2, 65.7),
      (9.1, 67.1))),
    ('VR second', 2,
     ((27.9, 47.4), (28.8, 48.2), (28.5, 49.6), (27.9, 50.8), (27.4, 52.1), (27.6, 53.5), (28.4, 54.3),
      (29.4, 55.2), (30.1, 56.2), (30.4, 57.5), (31.0, 58.6), (31.9, 59.5), (33.0, 60.0), (34.3, 59.9),
      (35.4, 59.1), (36.0, 57.9), (36.8, 56.7), (38.0, 56.0), (39.1, 55.0), (39.8, 53.8), (40.2, 52.4),
      (40.2, 51.0), (40.1, 49.6), (39.7, 48.3), (39.0, 47.3), (39.0, 45.9), (39.5, 44.6), (40.1, 43.2),
      (41.2, 42.4), (40.3, 40.4), (39.0, 38.6), (37.8, 37.6), (36.2, 37.1), (34.3, 37.2), (32.5, 37.9),
      (31.3, 38.2), (30.6, 39.5), (29.5, 40.2), (28.3, 40.2), (27.3, 39.5), (27.5, 42.7), (27.4, 45.0),
      (27.4, 47.3)),
     ((1.0, 18.7), (9.3, 19.9), (14.3, 21.8), (19.0, 24.8), (23.1, 28.4), (26.2, 32.5), (28.8, 36.1),
      (30.7, 39.6), (31.8, 43.7), (32.7, 47.9), (33.6, 52.0), (34.2, 55.5), (34.0, 59.3))),
    ('VR mid', 4,
     ((26.8, 38.5), (27.3, 39.5), (28.3, 40.2), (29.5, 40.2), (30.6, 39.5), (31.3, 38.2), (31.5, 36.8),
      (31.1, 35.4), (29.7, 33.9), (28.0, 32.1), (25.8, 27.9), (22.6, 23.7), (18.2, 20.6), (13.5, 18.7),
      (9.2, 17.8), (5.5, 17.4), (2.0, 17.3), (-0.1, 17.3), (0.0, 19.4), (1.8, 19.4), (5.0, 20.3), (8.8, 21.7),
      (13.5, 23.6), (18.4, 26.9), (21.8, 31.2), (24.4, 36.1), (25.8, 37.6)),
     ((0.2, 18.4), (4.0, 18.8), (7.3, 19.1), (10.6, 20.0), (15.3, 21.9), (20.2, 25.1), (23.6, 29.5),
      (26.2, 34.4), (27.9, 36.7), (29.2, 38.0))),
    ('VR third', 1,
     ((41.9, 42.0), (43.3, 41.8), (44.5, 42.2), (45.9, 42.3), (47.3, 42.0), (48.4, 41.0), (48.8, 39.5),
      (49.0, 38.1), (49.5, 36.7), (50.3, 35.3), (50.3, 33.8), (49.9, 32.6), (49.2, 31.5), (48.1, 30.8),
      (47.0, 30.1), (45.9, 29.4), (44.9, 28.7), (44.5, 27.4), (44.5, 25.9), (44.8, 25.2), (45.4, 24.7),
      (42.9, 24.6), (40.2, 24.3), (37.3, 23.6), (34.4, 22.2), (31.6, 20.7), (28.8, 19.0), (26.1, 17.7),
      (24.0, 17.2), (21.8, 17.3), (20.1, 18.7), (19.6, 20.7), (20.2, 21.6), (22.6, 23.7), (25.8, 27.9),
      (28.0, 32.1), (29.7, 33.9), (31.1, 35.4), (31.5, 36.8), (31.3, 38.2), (32.5, 37.9), (34.3, 37.2),
      (36.2, 37.1), (37.8, 37.6), (39.0, 38.6), (40.3, 40.4)),
     ((21.4, 18.4), (24.7, 19.7), (29.7, 23.3), (34.7, 27.7), (39.9, 33.1), (45.1, 38.2), (47.7, 40.1))),
    ('VR fourth', 0,
     ((46.1, 24.6), (47.4, 25.0), (48.6, 25.4), (50.0, 25.4), (51.5, 25.2), (53.1, 24.6), (54.2, 23.4),
      (55.4, 22.1), (56.7, 20.9), (57.7, 19.5), (58.1, 17.9), (58.0, 16.5), (57.1, 15.6), (55.9, 14.9),
      (55.4, 14.4), (52.5, 13.8), (49.3, 13.4), (46.7, 13.3), (44.0, 13.1), (40.3, 13.1), (36.7, 13.0),
      (33.2, 13.2), (29.0, 14.0), (26.3, 15.2), (23.3, 15.0), (19.9, 14.8), (17.3, 15.6), (13.7, 14.9),
      (9.7, 14.8), (5.8, 14.9), (2.5, 15.1), (-0.2, 15.2), (-0.1, 17.3), (2.0, 17.3), (5.5, 17.4), (9.2, 17.8),
      (13.5, 18.7), (18.2, 20.6), (20.2, 21.6), (19.6, 20.7), (20.1, 18.7), (21.8, 17.3), (24.0, 17.2),
      (26.1, 17.7), (28.8, 19.0), (31.6, 20.7), (34.4, 22.2), (37.3, 23.6), (40.2, 24.3), (42.9, 24.6),
      (45.8, 24.6)),
     ((0.2, 16.0), (4.5, 15.9), (7.8, 16.0), (12.4, 16.1), (17.0, 16.3), (21.7, 16.6), (26.4, 16.9),
      (31.2, 17.3), (36.1, 17.9), (41.1, 18.4), (46.3, 18.7), (51.8, 18.7), (57.0, 18.4))))
# the ACORN KNOBS [M egmar3b, the same trace]: small round bosses at the leaves' bases, two on the third leaf and two on
# the inner a side, and the middle leaf's tip knob: (centre u, y mm; radius mm)
ACORN_TRACE = (((-37.7, 37.4), 0.87), ((-32.5, 31.3), 0.81), ((-23.2, 39.2), 0.94), ((-20.1, 32.5), 0.87),
               ((37.9, 36.1), 0.87), ((32.1, 30.4), 0.87), ((22.0, 38.5), 0.94), ((17.6, 32.0), 0.87),
               ((-27.5, 43.1), 1.07), ((29.2, 38.0), 1.07))
# the stalks behind the cords, crossing in an X just over them at the centre (cap v5's, kept: hidden but for the X)
WREATH_STEM = ((-5.0, 16.9), (-1.0, 17.8), (3.0, 18.7), (7.0, 19.3), (11.0, 19.8))
LEAF_UNDER = 0.0015         # a leaf under another runs on beneath it this far (its region dilated, inside the upper
                            # leaves only): the upper leaf's edge steps over a blade that continues, as a stamped
                            # overlap does, and no red slot opens along a traced shared boundary


WREATH_BACK_H = CK_LIFT     # cap v5 (the lead's decision 2): the SCALLOPED SCARLET BACKING under the wreath, a felt patch
WREATH_BACK_MARGIN = 0.0026  # standing this proud of the band [E: a front view gives no height; its edge's shadow line
WREATH_BACK_CLOSE = 0.0045  # reads 1-2 px on egmar3b], its edge MARGIN beyond the leaves (0.10 D: the lead's 0.05-0.15 D;
WREATH_BACK_SHOULDER = 0.00015  # egmar3b's red-contrast zoom 3-12 px, research/cap_gdr_work/v5_wreath_x6_red.png; g02),
                            # the outline's gaps between the leaves' tips closed over CLOSE (its scallops follow the
                            # leaves), filling the V between the inner leaves over the cockade up to under the seam; its
                            # velvet edge a crisp CUT (cap v6: rounded over SHOULDER 0.15 mm, one voxel; v5's 0.8 mm
                            # shoulder faced the key and read as a light rim, the v5 check). The leaves and the cockade
                            # sit ON it
WREATH_BACK_ROLL = 0.0030   # cap v7 (the lead's decision 3: "its edge rolling flush into the band so it catches NO light
                            # rim"): the backing rises from the band's face to its full height over this from its edge,
                            # a smoothstep (no step, no vertical face; v6's cut stood 0.42 mm proud at its outline and
                            # its face toward the key caught the rim the v6 check saw), its edge's paint darkened over
                            # the same width (paint)
WREATH_BASE = 0.00035       # the stamped wreath [E: the heights of a stamped piece cannot be read from a front view; its
WREATH_DOME = 0.00110       # crisp specular edges, rounded lobes and raised beaded midribs can, CAP_GDR §5]: the lowest
WREATH_LAYER = 0.00020      # leaf's edge BASE over the backing, each leaf DOMED this much from its edge up to its
                            # midrib, each layer of the overlap this much over the one under it, an upper leaf DRAPING
                            # over a leaf under it (never dipping into it). Cap v8 (decision 1, "relief heights from
                            # images.jpg's angle and the photos' highlights"): the dome 1.1 mm on the traced leaves'
                            # 3.5-9 mm half-widths (her leaves at images.jpg's 9 deg read as bright crests with a dark
                            # edge each side; on egmar3b the crests carry the highlights, her gilt's L* span 29 with
                            # the beads; v7's 1.4 mm on 7-9 mm half-widths of pillowed lobes)
WREATH_MID = (0.00026, 0.00034)  # cap v8: the MIDRIB a raised ridge (its height, its half-width) carrying BEADS (WREATH_BEAD:
WREATH_BEAD = (0.00085, 0.00032, 0.00022)  # their pitch along it, radius, height over the ridge) [M egmar3b: the beads
                            # 1.2-1.3 of her pixels apart along the midribs at 1.49 px/mm on the 16x relief zooms,
                            # research/cap_gdr_work/v8_left_mid_relief_x16.png: 0.85 mm; "strongly BEADED", the lead's
                            # decision 1]; v7 a smooth ridge, v5-v6 0.22 mm balls every 0.6 mm
WREATH_EDGE_ROLL = 0.00030  # each leaf's stamped edge rounds over this width (a crisp wall under a short roll)
WREATH_GRID = 0.00010       # the relief's raster: vertical cylinders this far apart on the band's face, each of this
                            # radius with its top's edge rounded 0.02 mm, so a cell's corner (0.071 mm out) lies on the
                            # cylinders' flat tops (cap v4's second forge: 0.2 mm apart, 0.15 mm radius, 0.03 mm round:
                            # the corners fell in the roundings, and the leaves baked striped)
WREATH_CELL_R = 0.00020     # cap v7: each raster cell's stroke radius and its top's rounding (_wreath_relief)
WREATH_RING = 0.00080       # the scarlet RING between the cockade's rim and the wreath, 0.03 D [M egmar3b: 0.03-0.08 D,
                            # CAP_GDR §5]: the leaves stop this far outside the rim, in the relief and in the paint
                            # (cap v4's second forge ran them under the rim: the cockade's side baked buried)


def midrib_field(M, P):
    """each point of P (n, 2: band u, y in m)'s nearest point on the midrib polyline M (k, 2, from the base to the tip):
    its distance (m) and the way along the midrib there (0 the base, 1 the tip)"""
    M = np.asarray(M, np.float64)
    A, E = M[:-1], np.diff(M, axis=0)
    L = np.linalg.norm(E, axis=1)
    s0 = np.concatenate([[0.0], np.cumsum(L)])
    best = np.full(len(P), np.inf)
    sv = np.zeros(len(P))
    for j in range(len(A)):
        W = P - A[j]
        t = np.clip((W @ E[j]) / max(L[j] ** 2, 1e-18), 0.0, 1.0)
        d = np.linalg.norm(W - t[:, None] * E[j], axis=1)
        m = d < best
        best[m] = d[m]
        sv[m] = s0[j] + t[m] * L[j]
    return best, sv / s0[-1], s0[-1]


WREATH_BLUR = 0.0010        # cap v8: the blade's dome is the leaf's region BLURRED this much (a Gaussian, m): smooth over
                            # every lobe and sinus, rising from 0 at the outline (the blur's 0.5) to the full dome inside;
                            # the distance in from the outline (the first v8 probe's u = d_edge / (d_edge + d_mid)) has
                            # creases along the region's medial axis, which shaded as streaks fanning to the edge
WREATH_MID_RISE = 0.0025    # the blade rising toward its midrib over this (the stamping's fold along the vein)


def leaf_top(layer, d_edge, d_mid, s, Lm, blur):
    """cap v8 (the lead's decision 1): a TRACED leaf's own top surface over the backing's top, per point by its distance
    in from the leaf's outline (d_edge: its region run on under the leaves above it, LEAF_UNDER), its distance to the
    leaf's midrib (d_mid), the way along it (s, 0 the base .. 1 the tip; Lm its length) and its region blurred
    (WREATH_BLUR: 0.5 on the outline, 1 well inside): BASE + its layer, its stamped edge rolling over WREATH_EDGE_ROLL;
    the blade DOMED smoothly from the outline inward (the blur, so each small lobe the traced outline carries rounds over
    by itself: no lobe law, no crease) and rising toward the midrib (WREATH_MID_RISE), a little lower toward the stalk
    and the tip; the MIDRIB a raised ridge (WREATH_MID) carrying BEADS (WREATH_BEAD: a string of round beads,
    "strongly BEADED"); no creases, no pillows. Its twin: wreath_raster"""
    edge = np.clip(d_edge / WREATH_EDGE_ROLL, 0.0, 1.0)
    roll = np.sqrt(edge * (2.0 - edge))
    inflate = np.clip((blur - 0.5) / 0.45, 0.0, 1.0)
    inflate = inflate * inflate * (3.0 - 2.0 * inflate)
    taper = 0.55 + 0.45 * np.sin(np.pi * np.clip(s, 0.0, 1.0)) ** 0.5
    vein = 0.55 + 0.45 * np.exp(-(d_mid / WREATH_MID_RISE) ** 2)
    rib = np.clip((s - 0.02) / 0.06, 0.0, 1.0) * np.clip((0.985 - s) / 0.04, 0.0, 1.0)
    ridge = WREATH_MID[0] * np.exp(-(d_mid / WREATH_MID[1]) ** 2) * rib
    pitch, rb, hb = WREATH_BEAD
    da = (np.mod(s * Lm / pitch, 1.0) - 0.5) * pitch
    bead = hb * np.sqrt(np.clip(1.0 - (da * da + d_mid * d_mid) / (rb * rb), 0.0, 1.0)) * rib
    return (WREATH_BASE + layer * WREATH_LAYER) * (0.4 + 0.6 * roll) + WREATH_DOME * inflate * vein * taper + \
        ridge + bead


_LEAVES = {}


def wreath_grid(spec=SPEC, g=WREATH_GRID):
    """the wreath's raster on the band's face (band coordinates, metres): u across the front, y from the cords' pair
    bottom to 1.5 mm under the raised seam; the backing, the leaves and the relief share it"""
    lay = cord_layout(spec)
    u = np.arange(-0.085, 0.085 + 1e-9, g)
    y = np.arange(lay['yb'], spec['band_h'] + spec.get('seam_rise', 0.0) - 0.0015 + 1e-9, g)
    return u, y


def wreath_leaves(spec=SPEC, g=WREATH_GRID):
    """cap v8 (the lead's decision 1): the TRACED leaves (LEAF_TRACE) on the wreath's raster: per leaf (top layer first)
    its visible region (the trace), its FULL region (the visible one run on LEAF_UNDER beneath the leaves above it: an
    overlap, never into the red) and the distance in from the full region's outline (m), its outline and midrib in
    metres. The sculpt (wreath_raster), the backing and the cover share it; the paint takes the visible outlines
    (material_tables' LQ), which tile the same regions"""
    key = (tuple(sorted((k, str(v)) for k, v in spec.items())), g)
    if key in _LEAVES:
        return _LEAVES[key]
    from scipy import ndimage as ndi
    from skimage.draw import polygon as fill_poly
    u, y = wreath_grid(spec, g)
    shape = (len(y), len(u))
    leaves = []
    for name, layer, outline, midrib in LEAF_TRACE:
        P = np.asarray(outline, np.float64) * 1e-3
        Mr = np.asarray(midrib, np.float64) * 1e-3
        vis = np.zeros(shape, bool)
        rr, cc = fill_poly((P[:, 1] - y[0]) / g, (P[:, 0] - u[0]) / g, shape)
        vis[rr, cc] = True
        leaves.append(dict(name=name, layer=layer, poly=P, midrib=Mr, vis=vis, side=1 if P[:, 0].mean() > 0 else -1,
                           inner=name.endswith('inner'), tip=Mr[-1], q0=Mr[0],
                           len=float(np.linalg.norm(np.diff(Mr, axis=0), axis=1).sum())))
    r = int(round(LEAF_UNDER / g))
    disk = np.add.outer(np.arange(-r, r + 1) ** 2, np.arange(-r, r + 1) ** 2) <= r * r
    for lf in leaves:
        above = np.zeros(shape, bool)
        for o in leaves:
            if o['layer'] > lf['layer'] and o['side'] == lf['side']:
                above |= o['vis']
        lf['full'] = lf['vis'] | (ndi.binary_dilation(lf['vis'], structure=disk) & above)
        lf['edt'] = ndi.distance_transform_edt(lf['full']) * g
        lf['blur'] = ndi.gaussian_filter(lf['full'].astype(np.float32), WREATH_BLUR / g)
    leaves.sort(key=lambda lf: -lf['layer'])
    out = dict(U=u, Y=y, leaves=leaves, g=g)
    _LEAVES[key] = out
    return out


_BACKING = {}


def wreath_backing(spec=SPEC, g=WREATH_GRID):
    """the SCALLOPED SCARLET BACKING (cap v5, the lead's decision 2) in band coordinates: the wreath's cover (the leaves,
    the stalks, the acorns, the cockade's disc with its ring, and the V between the inner leaves over the cockade up to
    their tips) dilated by WREATH_BACK_MARGIN and closed over WREATH_BACK_CLOSE, kept between the cords' pair centre
    (it runs on behind the cords) and 1.5 mm under the band's top seam (clear of the band-top piping). Returns dict(U, Y
    the raster's axes, mask, din: each cell's distance in from the backing's edge (m), poly: its outline (n, 2), the
    cover mask, the leaves-to-edge distances)"""
    key = tuple(sorted((k, str(v)) for k, v in spec.items()))
    if key in _BACKING:
        return _BACKING[key]
    from scipy import ndimage as ndi
    from skimage import measure
    T = material_tables(spec, backing=False)
    u, y = wreath_grid(spec, g)
    UU, YY = np.meshgrid(u, y)
    btop = (spec['band_h'] + seam_bump(UU, spec)).ravel()        # cap v6: the band's seam, raised at the front centre
    X = np.column_stack([UU.ravel(), YY.ravel(), np.zeros(UU.size)])
    # cap v8: the traced leaves' visible regions (wreath_leaves)
    WL = wreath_leaves(spec, g)
    cover = np.zeros(UU.size, bool)
    for lf in WL['leaves']:
        cover |= lf['vis'].ravel()
    leaves = cover.copy()
    for c in T['AC']:
        cover |= (X[:, 0] - c[0]) ** 2 + (X[:, 1] - c[1]) ** 2 < c[2] ** 2
    for s0, n, _ in T['SI']:
        P = T['SP'][s0:s0 + n]
        for j in range(n - 1):
            a, ab = P[j], P[j + 1] - P[j]
            tt = np.clip(((X - a) @ ab) / max(ab @ ab, 1e-20), 0, 1)
            cover |= np.linalg.norm(X - (a + tt[:, None] * ab), axis=1) < T['stalk_r']
    R = 0.5 * spec['cockade_d']
    cy = spec['cockade_y']
    cover |= X[:, 0] ** 2 + (X[:, 1] - cy) ** 2 < (R + WREATH_RING) ** 2
    # the V over the cockade between the inner leaves, up to their tips and (cap v6) on up under the raised seam
    # (egmar3b: the backing arches over the cockade 2-4 mm under the seam, research/cap_gdr_work/v5_wreath_x6_red.png)
    tips = [lf for lf in leaf_instances(spec) if lf['inner']]
    ty = min(float(lf['tip'][1]) for lf in tips)
    tu = max(abs(float(lf['tip'][0])) for lf in tips)
    wv = np.minimum(R + (tu - R) * (X[:, 1] - cy) / max(ty - cy, 1e-6), tu)
    vfill = (X[:, 1] >= cy) & (X[:, 1] <= np.maximum(ty, btop - 0.0025 - WREATH_BACK_MARGIN)) & (np.abs(X[:, 0]) <= wv)
    cover |= vfill
    M = cover.reshape(UU.shape)
    rd = int(round(WREATH_BACK_MARGIN / g))
    rc = int(round(WREATH_BACK_CLOSE / g))
    disk = lambda r: (np.add.outer(np.arange(-r, r + 1) ** 2, np.arange(-r, r + 1) ** 2) <= r * r)
    B = ndi.binary_dilation(M, structure=disk(rd))
    B = ndi.binary_closing(np.pad(B, rc + 2), structure=disk(rc))[rc + 2:-rc - 2, rc + 2:-rc - 2]
    B = ndi.binary_fill_holes(B)
    B &= (YY <= btop.reshape(UU.shape) - 0.0015)                  # kept 1.5 mm under the band's seam
    din = ndi.distance_transform_edt(B) * g
    # the outline: the 0.5 iso-line of the mask (skimage), the longest contour, in metres
    cs = measure.find_contours(np.pad(B.astype(float), 1), 0.5)
    cmax = max(cs, key=len) - 1.0
    poly = np.column_stack([u[0] + cmax[:, 1] * g, y[0] + cmax[:, 0] * g])
    keepv = np.r_[True, np.linalg.norm(np.diff(poly, axis=0), axis=1) > 0.4 * g]
    poly = poly[keepv]
    poly = poly[::max(1, len(poly) // 480)]
    # the leaves' outline to the backing's edge (the gate: 0.05-0.15 D): over the leaves' boundary cells above the cords
    Lm = leaves.reshape(UU.shape)
    edge_l = Lm & ~ndi.binary_erosion(Lm)
    dout = ndi.distance_transform_edt(~B) * g
    d_leaf = ndi.distance_transform_edt(~edge_l) * g
    out = dict(U=u, Y=y, mask=B, din=din, poly=poly, cover=M, leaves=Lm, dout=dout, d_leaf=d_leaf)
    _BACKING[key] = out
    return out


def wreath_raster(spec=SPEC, ra=WREATH_GRID, g=WREATH_GRID):
    """the STAMPED WREATH's relief ON ITS BACKING as a height field on the band (band coordinates u, y; metres): per
    raster cell inside the backing or a leaf, its top surface over the band's felt and the TOP-MOST leaf's index in
    leaf_instances() (the leaves laid bottom layer first, each covering what lies under it; -2 the backing alone). The
    backing WREATH_BACK_H, its edge rolling flush into the band; a leaf's cell (at least 1.5 cells inside its full
    region: the traced outline run on under the leaves above it) the backing plus leaf_top (cap v8: the traced leaf's
    dome, its beaded midrib), and where a leaf under it stands higher, the top-most leaf DRAPES over it (0.06 mm above
    it). Returns U, Y, H, owner (flat arrays over the cells)"""
    bk = wreath_backing(spec, g)
    UU, YY = np.meshgrid(bk['U'], bk['Y'])
    U, Y = UU.ravel(), YY.ravel()
    din = bk['din'].ravel()
    # cap v7: the edge ROLLS flush into the band over WREATH_BACK_ROLL (v6: 0.35 of the height at the outline, then a
    # 0.15 mm shoulder)
    t_ = np.clip(din / WREATH_BACK_ROLL, 0.0, 1.0)
    Hb = np.where(bk['mask'].ravel(), WREATH_BACK_H * t_ * t_ * (3.0 - 2.0 * t_), -1.0)
    own = np.where(bk['mask'].ravel(), -2, -1).astype(np.int64)
    H = Hb.copy()
    under = np.full(U.size, -1.0)                  # the highest leaf surface laid so far (the drape's floor)
    lfs = leaf_instances(spec)
    for i in range(len(lfs) - 1, -1, -1):          # the bottom layer first (leaf_instances lists the top first)
        lf = lfs[i]
        edt = lf['edt'].ravel()
        ins = edt >= 1.5 * g
        P = np.column_stack([U[ins], Y[ins]])
        d_mid, s, Lm = midrib_field(lf['midrib'], P)
        top = np.full(U.size, -1.0)
        top[ins] = WREATH_BACK_H + leaf_top(lf['layer'], edt[ins] - 0.5 * g, d_mid, s, Lm, lf['blur'].ravel()[ins])
        top = np.maximum(top, np.where(under > 0.0, under + 0.00006, -1.0))
        H[ins] = top[ins]
        own[ins] = i
        under = np.where(ins, np.maximum(under, top), under)
    m = own != -1
    return U[m], Y[m], H[m], own[m]


def _wreath_relief(plan, spec, keep, stroke_cyl, ra=WREATH_GRID):
    """the STAMPED GILT WREATH: wreath_raster's height field as vertical cylinders (radius ra, their tops rounded
    0.02 mm) from 0.2 mm inside the felt up to the top-most leaf's surface: crisp vertical edges on the outlines, each
    upper leaf's edge a step over the leaf under it, SOLID from the felt up (cap v4's first forge floated the leaves
    0.3 mm off the felt on capsule sheets: the bake's search took the felt under them, and the wreath baked flat, its
    occlusion black). Cap v8: each leaf's beaded MIDRIB is in the height field itself (leaf_top), where that leaf is the
    top-most. keep(points) -> the strokes kept (the leaves' feet pass behind the cords; the inner leaves stop short of
    the cockade's rim). Returns the raster (for the acorns' seats)"""
    U, Y, H, own = wreath_raster(spec, ra)
    A = band_frame(u_to_phi(U, spec), Y, -0.0002, spec)[0]
    B = band_frame(u_to_phi(U, spec), Y, H - 0.00002, spec)[0]
    ok = keep(B, own >= 0)
    # cap v7 (the lead's decision 2: "no crinkled-foil micro-normal"): each cell a FULLY ROUNDED stroke of WREATH_CELL_R
    # (twice the raster's spacing, its top a hemisphere): the top surface the smooth envelope of overlapping domes
    # (scallops ~0.006 mm), the outlines' walls still vertical. v4-v6's flat-topped 0.1 mm cylinders left a terrace at
    # every cell on the pillows' slopes (0.03-0.05 mm steps), which the 0.15 mm voxels and the bake aliased into the
    # fine diagonal hatching on the gilt (tests/out/cap/v7/look1/t27_leaves_vs_egmar3b.png)
    plan.add(stroke_cyl, A[ok], B[ok], WREATH_CELL_R, WREATH_CELL_R, 'add', 0.00003, 'wreath relief (on its backing)')
    return U, Y, H, own


def wreath_layout(spec=SPEC):
    """the general's WREATH, STAMPED GILT METAL (research/CAP_GDR.md §5 and §13): cap v8 its leaves and acorn knobs
    TRACED on egmar3b (LEAF_TRACE, ACORN_TRACE: wreath_leaves, acorn_parts); here its STALKS (control points in band
    coordinates, metres), which cross in an X just over the cords at the centre (her photo's x 180-195, y 200-206) and
    run on behind them"""
    mm = 1.0e-3
    return dict(stem=np.array(WREATH_STEM) * mm)


def acorn_parts(spec=SPEC):
    """cap v8: each ACORN KNOB in band coordinates (ACORN_TRACE, measured on egmar3b): (its centre (u, y), its radius),
    m. The plan strokes each as a round boss seated on the relief; the material's circles follow them"""
    return [(np.array(c) * 1e-3, r * 1e-3) for c, r in ACORN_TRACE]


def _catmull(P, n):
    from ..loft import resample
    if P.shape[1] == 2:
        Q = resample(np.column_stack([P, np.zeros(len(P))]), n)
        return Q[:, :2]
    return resample(P, n)


def leaf_instances(spec=SPEC):
    """cap v8: every TRACED wreath leaf (wreath_leaves: the paint's outlines and the sculpt's relief share it), top layer
    first: name, layer, side (+1 the viewer's right), poly (its visible outline, band coordinates, m), midrib (base ->
    tip), len (the midrib's), inner, tip, q0 (the midrib's base), and its raster regions (vis, full, edt)"""
    return wreath_leaves(spec)['leaves']


def plan_cap(prog=None, spec=SPEC, rng=None, log=print):
    """the sculpt plan (features of ~0.3 mm and up, every stroke placed analytically on the block-out):
      * SEAMS: the wall's front and back centre seams (a pressed groove with its allowances under the cloth either
        side) and the band's back seam;
      * the CORDS' 3-ply twist: three helical grooves a cord, never where a groove would cut a part it lies against;
      * the KNOTS' braid: a multi-pass Turk's head, flat bundles of threads curving over and under round the barrel;
      * the band's WREATH: stamped gilt metal leaves (domed sheets, crisp edges, raised beaded midribs), stalks behind
        the cords, acorns on the leaves;
      * the COCKADE's relief (its face: ck_*): the hammer and the compass raised off the enamel as flat-topped
        stamped metal with crisp edges, the hinge's boss over them, the rye ring's grains, awns and stalks embossed
        on its field, the parting bar at the top"""
    from ..species.octopus_sculpt import Plan
    from ..voxel import STROKE_CONE, STROKE_CYL
    rng = rng or np.random.default_rng(7)
    plan = Plan()
    half = 0.5 * spec['cloth_t']
    # 1. seams. Cap v6: each ends a clearance short of the pipings (the crown piping's tube round E, now on the wall's
    # seam under the roll, and the band piping on the raised seam): run from t 0.02 to 0.985 as in v5, the groove and
    # its 0.7 mm allowances pushed a lump through the crown piping at the front (the first v6 forge, t27's
    # crown_front_profile); the wall's meridian is ~80 mm long at the front and ~20 at the back, so the ends go per seam
    dd = dims(spec)
    for phv in (0.0, np.pi):
        tt = np.linspace(0.0, 1.0, 2001)
        Pw = wall_point(tt, np.full_like(tt, phv), spec) + half * wall_normal(tt, np.full_like(tt, phv), spec)
        E_ = pipe_centre(np.array([phv]), spec)[0]
        B_ = band_frame(phv, band_top(phv, spec), 0.00025, spec)[0]
        # cap v7: 2.5 mm short of the crown piping (v6 1.2: its groove and allowances, with the slab's voxels, left the
        # stair-stepped V wedge at the front centre), 1.2 of the band's
        clear_ = (np.linalg.norm(Pw - E_, axis=1) > dd['rp'] + 0.0025) & \
            (np.linalg.norm(Pw - B_, axis=1) > dd['rpb'] + 0.0012)
        t = np.linspace(float(tt[clear_].min()), float(tt[clear_].max()), 180)
        n = wall_normal(t, np.full_like(t, phv), spec)
        P = wall_point(t, np.full_like(t, phv), spec) + half * n
        # cap v8 (the lead's decision 4: "the dark pinpoint at the front centre traced to its cause"): the groove and its
        # allowances FADE over their last 3 mm at each end (the carve's centre rising to the cloth, the allowances
        # thinning to nothing); v7's groove ended in its stroke's round cap, a 0.25 mm pit under the front piping
        # that the occlusion turned into a dark pinpoint
        sa = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        fe = np.clip(np.minimum(sa, sa[-1] - sa) / 0.003, 0.0, 1.0)
        fe = fe * fe * (3.0 - 2.0 * fe)
        lift = 0.00015 + 0.00025 * (1.0 - fe)
        plan.add(STROKE_CONE, (P + n * lift[:, None])[:-1], (P + n * lift[:, None])[1:], 0.0004, 0.0004, 'carve',
                 0.00012, 'wall seam')
        tg = _unit(np.cross(n, np.gradient(P, axis=0)))
        ra_ = 0.0007 - 0.00012 * (1.0 - fe)
        for sg in (1.0, -1.0):
            Q = P + sg * tg * 0.0016 - n * 0.0006
            plan.add(STROKE_CONE, Q[:-1], Q[1:], ra_[:-1], ra_[1:], 'add', 0.0003, 'seam allowance')
    y = np.linspace(0.0025, spec['band_h'] - 0.0006, 120)
    Pb, Nb, _ = band_frame(np.pi, y, 0.0, spec)
    plan.add(STROKE_CONE, Pb[:-1] + Nb[:-1] * 0.0002, Pb[1:] + Nb[1:] * 0.0002, 0.00045, 0.00045, 'carve', 0.00012,
             'band seam')
    # 2. the cords: cap v6 (the lead's decision 3) each a TWO-PLY ROPE of fine fibre bundles added round the high's thin
    # core (_rope), its bundles kept off the visor's lacquer and its rim where the lower cord rests on the root
    seen = build_sdf(spec, parts=('visor', 'edge'))
    paths, _ = cord_paths(spec)
    r = 0.5 * spec['cord_d']
    for nm, (P, N) in paths.items():
        _rope(plan, P, N, r, spec['cord_ply_lay'], spec['cord_bundle_lay'], f'rope {nm}', visible=seen, hand=1.0)
    # 3. the knots' braid
    for side in (1, -1):
        _braid(plan, *knot_curve(spec, side), tag=f'knot braid {side:+d}')
    # 4. the band's WREATH: the leaves' feet pass BEHIND the cords at the band's foot (their strokes stop 1.3 mm short of
    # the upper cord: v2's first forge stood the relief into the cord, and the bake missed its band side at the front)
    cords = build_sdf(spec, parts=('cords',))
    behind = lambda P: np.asarray(cords.eval(np.asarray(P).reshape(-1, 3)), np.float64) > 0.0013
    # and the inner leaves stop short of the cockade: a scarlet ring WREATH_RING wide shows between its rim and them
    # (egmar3b), its side standing clear
    cc_, cn_ = cockade_frame(spec)
    R_ck = 0.5 * spec['cockade_d']

    def keep_w(P, leaf):
        """a wreath stroke kept: behind the cords' clearance always; a LEAF's (and a bead's) also outside the cockade's
        rim + WREATH_RING (the backing runs on to the rim and under it: the scarlet ring IS the backing)"""
        P = np.asarray(P).reshape(-1, 3)
        dd = P - cc_[None, :]
        rr = np.linalg.norm(dd - np.outer(dd @ cn_, cn_), axis=1)
        return behind(P) & ((rr > R_ck + WREATH_RING) | ~np.asarray(leaf, bool))
    Ur, Yr, Hr, _ = _wreath_relief(plan, spec, keep_w, STROKE_CYL)
    wl = wreath_layout(spec)
    st = _catmull(wl['stem'], 80)
    for side in (1, -1):
        # the stalks lie ON the backing (sunk 0.2 mm into it: solid, no gap under them for the bake to find), crossing
        # in an X just over the cords at the centre (cap v5)
        P = band_frame(u_to_phi(st[:, 0] * side, spec), st[:, 1], WREATH_BACK_H + 0.0005, spec)[0]
        ok = behind(P[:-1]) & behind(P[1:])
        if ok.any():
            plan.add(STROKE_CONE, P[:-1][ok], P[1:][ok], 0.0007, 0.0007, 'add', 0.0001, 'wreath stalks')
    # cap v8: the ACORN KNOBS (ACORN_TRACE): round bosses ON the leaves where her photo shows them, each a ball of its
    # traced radius seated on the relief under it (its centre a quarter radius over the leaf: the knob stands 1.25 r
    # proud, its foot sunk into the leaf, no gap under it)
    bp = lambda q, w: band_frame(u_to_phi(q[0], spec), q[1], w, spec)[0]

    def seat(q):
        k = int(np.argmin((Ur - q[0]) ** 2 + (Yr - q[1]) ** 2))
        return float(Hr[k]) if np.hypot(Ur[k] - q[0], Yr[k] - q[1]) < 2.0 * WREATH_GRID else 0.0
    for c_, r_ in acorn_parts(spec):
        h_ = seat(c_) + 0.25 * r_
        plan.add(STROKE_CONE, bp(c_, h_)[None], bp(c_, h_)[None], r_, r_, 'add', 0.00008, 'acorn knob')
    # 5. the COCKADE's relief, in its face's frame (D units -> metres on the band's normal at its centre)
    c, n = cockade_frame(spec)
    e1 = np.array([1.0, 0.0, 0.0])
    e2 = np.cross(n, e1)
    D = spec['cockade_d']
    face = lambda uu, vv, z: c[None, :] + n[None, :] * np.asarray(z, np.float64).reshape(-1, 1) + \
        (np.asarray(uu)[:, None] * e1[None, :] + np.asarray(vv)[:, None] * e2[None, :]) * D
    # the arms: a raster of short cylinders (0.1 mm apart, 0.075 mm radius, their edges rounded 0.03 mm) from under
    # the enamel up to the arms' top, wherever the cylinder lies inside the arms' outline: a flat top, crisp sides on
    # the outline; the hinge boss the same, higher
    ra = 0.000075
    g = np.arange(-0.27, 0.27, 0.0001 / D)
    UU, VV = np.meshgrid(g, g)
    sd = ck_arms_sd_np(UU, VV) * D
    for nm_, m, ztop in (('arms', sd <= -ra, CK_Z['arms']),
                         ('hinge boss', np.hypot(UU - CK_HINGE[0], VV - CK_HINGE[1]) * D <= CK_HINGE[2] * D - ra,
                          CK_Z['boss'])):
        uu, vv = UU[m], VV[m]
        plan.add(STROKE_CYL, face(uu, vv, np.full(len(uu), CK_Z['enamel'] - 0.0002)),
                 face(uu, vv, np.full(len(uu), ztop - 0.00003)), ra, 0.00003, 'add', 0.00003, f'cockade {nm_}')
    # the rye: cap v5 sculpts NO rye (its fine grains, awns and stalks are the texture's, ck_rye_h, read through the
    # gilt's reflections; the first v5 forges' smooth ear mounds, ck_rye_bodies, ran together into concentric rings that
    # fought the grains, t27_cockade_vs_closeup.png); only the parting bar at the top below
    # cap v6 (the lead's decision 4): the parting bar a STAMPED WEDGE, flat-topped with crisp sides (a raster of short
    # cylinders like the arms), CK_BAR_W wide at its inner and outer ends [M the close-up's top: ~22 px (0.029 D) at the
    # rim narrowing to ~13 px (0.017 D) at the inner ring, research/cap_gdr_work/v6_ck_top_x4.png]; v5 a round capsule
    u_b, hw_b, v0_b, v1_b = CK_BAR
    gb = np.arange(-0.02, 0.02, 0.0001 / D)
    UB, VB = np.meshgrid(u_b + gb, np.arange(v0_b, v1_b, 0.0001 / D))
    hwv = CK_BAR_W[0] + (CK_BAR_W[1] - CK_BAR_W[0]) * (VB - v0_b) / (v1_b - v0_b)
    mb = (np.abs(UB - u_b) * D <= hwv * D - ra) & (np.hypot(UB, VB) <= CK_RINGS['rim_in'] - 0.004)
    zt = CK_Z['field'] + 0.8 * CK_Z['grain']
    plan.add(STROKE_CYL, face(UB[mb], VB[mb], np.full(int(mb.sum()), CK_Z['field'] - 0.0002)),
             face(UB[mb], VB[mb], np.full(int(mb.sum()), zt - 0.00003)), ra, 0.00003, 'add', 0.00003,
             'cockade parting bar (a stamped wedge)')
    log('[peaked_cap] plan: ' + ', '.join(f'{o["tag"]} {len(o["A"])}' for o in plan.ops) +
        f'; {sum(len(o["A"]) for o in plan.ops)} strokes')
    return plan


TWIST_KEEP = 0.0002         # a rope's bundles keep this far off a VISIBLE part (the visor's lacquer and its rim): a bite
                            # there is a dimple in the gloss, a white speck
ROPE_CORE = 0.42            # cap v6: the rope's core in the high, a share of the cord's radius (the block-out's sweep for
                            # the voxels: build_sdf(rope_core=True)); its plies' bundles are the plan's ADDS round it
ROPE_PLY = (0.30, 0.70)     # a ply's centre off the rope's axis and its radius (shares of the cord's radius: two plies
                            # filling the rope, its envelope the low's tube). Cap v7 (the lead's decision 4: "tightly
                            # twisted strands", her along-cord L* swing 5-9 against v6's 13-19): the plies OVERLAP deeply
                            # (their valley 0.28 mm deep; v6's 0.50 / 0.50 touched at the axis: 1 mm valleys, and the
                            # first v7 forge's 0.44 / 0.56 0.9 mm still swung 15-19)
ROPE_BUNDLE = (0.38, 0.64)  # a bundle's centre off its ply's axis and its radius (shares of the ply's radius: three
                            # bundles a ply). Cap v7: overlapping deeply (their valleys 0.21 mm; v6 0.53 / 0.50): a tight
                            # twist of fine fibres (the texture's, cord_fibre), not glossy bundles with dark gaps. Cap v8
                            # (the lead's decision 2, the thread at her 5-15 deg off the cord's axis): the bundles' grooves
                            # a little deeper (0.30 mm) so the thread's lines read at her camera; the envelope still the
                            # cord's radius (0.30 + 0.70 x (0.38 + 0.64) = 1.014)


def _rope(plan, P, N, r, lay_p, lay_b, tag, visible=None, step=0.00025, hand=1.0):
    """cap v6 (the lead's decision 3): a TWO-PLY ROPE of fine fibre bundles along the cord's centreline P (frames from
    N, rotation-minimised: b = t x n), ADDED round the high's thin core (ROPE_CORE): two plies (ROPE_PLY) twisted on
    lay_p (hand +1: a right-handed helix, its crest on the face toward the viewer running down to the right as egmar3b's
    slanted bumps), each of three bundles (ROPE_BUNDLE) twisted the other way on lay_b, each bundle a chain of capsules;
    a capsule that would reach a VISIBLE part (the visor's lacquer and its rim, where the lower cord rests on the root)
    is thinned to keep TWIST_KEEP off it (the rope flattens there, never bites the gloss). v5 carved three strand
    grooves (45 mm lay) and an opposite yarn twist into a full tube: it read as diagonal ridged bars (the v5 check)"""
    from scipy.ndimage import gaussian_filter1d, minimum_filter1d

    from ..loft import rmf
    from ..voxel import STROKE_CONE
    Pd, s = _resample(P, step)
    n, b, t = rmf(Pd, ref=N[0])
    ds = max(float(np.mean(np.diff(s))), 1e-9)
    r_pc, r_ply = ROPE_PLY[0] * r, ROPE_PLY[1] * r
    r_bc, r_b = ROPE_BUNDLE[0] * r_ply, ROPE_BUNDLE[1] * r_ply
    for k in range(2):
        th = 2.0 * np.pi * (0.5 * k + hand * s / lay_p)
        u0 = np.cos(th)[:, None] * n + np.sin(th)[:, None] * b
        Cp = Pd + r_pc * u0
        tp = _unit(np.gradient(Cp, axis=0))
        u = _unit(u0 - tp * (u0 * tp).sum(1, keepdims=True))
        v = np.cross(tp, u)
        for j in range(3):
            ps = 2.0 * np.pi * (j / 3.0 - hand * s / lay_b)
            G = Cp + r_bc * (np.cos(ps)[:, None] * u + np.sin(ps)[:, None] * v)
            rad = np.full(len(G), float(r_b))
            if visible is not None:
                # the capsule's surface keeps TWIST_KEEP off the visible part (its own clearance less its radius)
                rad = np.minimum(rad, visible.eval(G).astype(np.float64) - TWIST_KEEP)
                rad = np.minimum(rad, gaussian_filter1d(minimum_filter1d(rad, max(3, int(0.0006 / ds)), mode='nearest'),
                                                        max(1.0, 0.0003 / ds), mode='nearest'))
            ok = (rad[:-1] > 0.00012) & (rad[1:] > 0.00012)
            if ok.any():
                plan.add(STROKE_CONE, G[:-1][ok], G[1:][ok], rad[:-1][ok], rad[1:][ok], 'add', 0.00006,
                         f'{tag} ply {k} bundle {j}')


TURKS_HEAD = dict(leads=9, bights=8, threads=6, pitch=0.00064, margin=0.0016, sq=0.7)
# cap v8 (the lead's decision 3: "THE KNOTS woven from wide flat RIBBONS of 5-6 parallel threads covering the whole
# surface and bulging the outline, as o03 shows"): each pass a flat ribbon of SIX threads 0.64 mm apart (3.8 mm across:
# o03's bundles of 5 (4-6) threads [M o03 at 3x, tests/out/cap/v2/photo/o03_knot_v2b.png], at this knot's 1.66 x),
# NINE leads (18 passes on the ~74 mm girth, 4.1 mm a pass: the ribbons nest edge to edge, no barrel between them), each
# thread 0.36 mm round (BRAID_THREAD: 4.8 voxels across, the threads touching: a ribbon with grooves between its threads),
# riding higher over a crossing (BRAID_LIFT) so the crossings bulge the outline. v7: strands of four 0.5 mm yarns 0.95
# mm apart, a barrel with thin crossing ridges and gaps
BRAID_THREAD = 0.00036


def turks_head(Lk, r_eff, leads=7, bights=8, threads=5, pitch=0.0005, margin=0.0015, sq=1.0, n_per=240):
    """the sliding knot's braid as a multi-pass TURK'S HEAD on its barrel unrolled (s along the axis, 0..Lk; theta
    round it): ONE strand goes round the barrel `leads` times while it swings from end to end and back `bights`
    times, s = Lk/2 + A sin(m theta) (m = bights / leads, coprime, so the strand closes on itself only after meeting
    every other pass; A keeps the bights `margin` inside the knot's ends), followed `threads` times side by side: a
    flat bundle, the threads `pitch` apart across the strand in the unrolled plane. Over and under alternate at every
    crossing along the strand (an alternating diagram: each crossing's two visits take opposite turns, asserted).
    Returns the threads [(theta, s), ...] (theta unwrapped, 0..2 pi leads) and the over/under wave at each sample
    (+1 over .. -1 under: a rounded square wave of sharpness sq, flat over a crossing, diving between)"""
    from math import gcd
    assert gcd(leads, bights) == 1, (leads, bights)
    A = 0.5 * Lk - margin
    m = bights / leads
    Tt = 2.0 * np.pi * leads
    th = np.linspace(0.0, Tt, n_per * leads, endpoint=False)
    s = 0.5 * Lk + A * np.sin(m * th)
    # the crossings: the strand at theta meets itself at theta + 2 pi k (k = 1 .. leads - 1) where sin(m theta) =
    # sin(m theta + c), c = 2 pi k m: m theta = (pi - c) / 2 + pi j. Each visit once, beside its crossing's other visit
    vis, mate = [], []
    for k in range(1, leads):
        x0 = 0.5 * (np.pi - 2.0 * np.pi * k * m)
        j = np.arange(np.floor(-x0 / np.pi) - 1, np.ceil((m * Tt - x0) / np.pi) + 2)
        v = (x0 + np.pi * j) / m
        v = v[(v >= 0.0) & (v < Tt - 1e-9)]                          # a visit on the wrap counted once
        vis.append(v)
        mate.append(np.mod(v + 2.0 * np.pi * k, Tt))
    vis, mate = np.concatenate(vis), np.concatenate(mate)
    order = np.argsort(vis)
    vs = vis[order]
    sign = np.empty(len(vs))
    sign[0::2], sign[1::2] = 1.0, -1.0
    dd = np.abs(vs[None, :] - np.mod(mate[order], Tt)[:, None])
    pos = np.argmin(np.minimum(dd, Tt - dd), axis=1)                    # each visit's mate, round the wrap
    assert len(vs) == 2 * bights * (leads - 1) and np.all(sign[pos] == -sign), 'not an alternating Turk\'s head'
    # the wave between consecutive visits (cyclic): +-1 at the visits, a rounded square wave between
    i = np.searchsorted(vs, th, side='right') - 1                        # the visit at or before each sample
    v0 = np.where(i >= 0, vs[np.maximum(i, 0)], vs[-1] - Tt)
    s0 = np.where(i >= 0, sign[np.maximum(i, 0)], sign[-1])
    v1 = np.where(i + 1 < len(vs), vs[np.minimum(i + 1, len(vs) - 1)], vs[0] + Tt)
    w = s0 * np.cos(np.pi * (th - v0) / np.maximum(v1 - v0, 1e-9))
    if sq > 0:
        w = np.tanh(sq * w) / np.tanh(sq)
    # the bundle's threads, offset across the strand in the unrolled plane (u = r_eff theta, s)
    tu, ts = np.full_like(th, r_eff), A * m * np.cos(m * th)
    ln = np.hypot(tu, ts)
    nu, ns = -ts / ln, tu / ln
    out = []
    for q in range(threads):
        o = (q - 0.5 * (threads - 1)) * pitch
        out.append((th + o * nu / r_eff, s + o * ns))
    return out, w


def _ellipse_phi(f, aa, n=721):
    """the parameter phi at a fraction f (-0.5..0.5) of an ellipse's perimeter from phi = 0 (the point cos(phi),
    aa sin(phi)): a knot's braid spaced by ARC LENGTH round its oval barrel (taken as an angle, the braid stretched
    39 % on the knot's flat outer face, where the barrel's 17 mm height runs, and pinched at its top and bottom)"""
    phi = np.linspace(-np.pi, np.pi, n)
    out = np.empty_like(f)
    aq = np.round(aa, 2)
    for a in np.unique(aq):
        sp = np.sqrt(np.sin(phi) ** 2 + (a * np.cos(phi)) ** 2)
        E = np.concatenate([[0.0], np.cumsum(0.5 * (sp[1:] + sp[:-1]) * np.diff(phi))])
        k = aq == a
        out[k] = np.interp(f[k], E / E[-1] - 0.5, phi)
    return out


def knot_girth(r0, asp):
    """the knot barrel's perimeter per station (Ramanujan's, semi-axes r0 and r0 asp)"""
    a, b = r0, r0 * asp
    return np.pi * (3.0 * (a + b) - np.sqrt((3.0 * a + b) * (a + 3.0 * b)))


BRAID_LIFT = (0.00105, 0.00062)   # a braid thread's centre over the knot's barrel, mean and over/under swing: cap v8 under
                            # at 0.43 mm (the 0.36 mm thread just over the barrel, solid under it), over at 1.67 (riding
                            # on the ribbon it crosses, a ribbon's thickness up and more: the crossings bulge the
                            # outline). Cap v7 0.95 / 0.50 with 0.5 mm yarns; v5-v6 thin threads on a solid bundle body


def _braid(plan, P, N, r0, asp, tag, r_thread=BRAID_THREAD, span=np.radians(108.0), th_=None):
    """a sliding knot's braid [M o03 at 3x, 14.6 px/mm (tests/out/cap/v2/photo/o03_knot_v2b.png): FLAT BUNDLES of 5
    metal threads (4-6) about 0.48 mm apart (7 px), 2.4 mm across (35 px), crossing at about 110 deg (each ~55 deg to
    the knot's axis in the middle), CURVING into bights at the knot's ends (about four a side across the visible
    face), each bundle over one and under the next with a step as deep as a thread]: a TURK'S HEAD (turks_head,
    TURKS_HEAD: 7 leads x 8 bights, the bundle 5 threads 0.5 mm apart: 2.9 mm apart across the middle, so the
    bundles nest with a thin gap) over the barrel's outer side (theta, a fraction of its girth, within +-span of its
    outward normal: past the oval's top and bottom, short of its back on the band), each thread a chain of balls of
    r_thread whose centre rides 0.17 mm over the barrel where its bundle passes under another and 0.65 mm where it
    passes over (a step of one thread's thickness, the bundle under ALWAYS above the barrel: the second v2 forge pressed
    it 0.23 mm into the barrel, and every bundle's under half vanished into dark rhombi). Forges 1-6 drew each bundle
    as one chain of 0.9 mm balls lifted +-0.22 mm (fine zigzag ripples); the first v2 forge (straight helices: 8
    bundles of 4 threads a family) read as a fine knitted herringbone, as a straight plain weave seen square-on always
    does (tests/out/cap/v2/braid_preview.png): the photo's bundles curve"""
    from ..voxel import STROKE_CONE, STROKE_CYL
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    Lk = s[-1]
    T = _unit(np.gradient(P, axis=0))
    Nn = _unit(N - T * (N * T).sum(1, keepdims=True))
    Bn = np.cross(T, Nn)
    r_eff = float(np.mean(knot_girth(r0, asp))) / (2.0 * np.pi)        # the barrel's mean girth as a radius
    threads, w = turks_head(Lk, r_eff, **(th_ or TURKS_HEAD))
    lift_all = BRAID_LIFT[0] + BRAID_LIFT[1] * w
    for qi, (thq, ssq) in enumerate(threads):
        thw = np.mod(thq + np.pi, 2.0 * np.pi) - np.pi                  # round the barrel, 0 = its outward normal
        keep = (np.abs(thw) <= span) & (ssq >= 0.0) & (ssq <= Lk)
        seg = keep[:-1] & keep[1:] & (np.abs(np.diff(thw)) < 0.5)
        if not seg.any():
            continue
        ss = np.clip(ssq, 0.0, Lk)
        j = np.clip(np.searchsorted(s, ss), 1, len(s) - 1)
        f = ((ss - s[j - 1]) / np.maximum(s[j] - s[j - 1], 1e-12))[:, None]
        C = P[j - 1] * (1 - f) + P[j] * f
        nn_, bb_ = Nn[j - 1] * (1 - f) + Nn[j] * f, Bn[j - 1] * (1 - f) + Bn[j] * f
        rr = (r0[j - 1] * (1 - f[:, 0]) + r0[j] * f[:, 0])
        aa = (asp[j - 1] * (1 - f[:, 0]) + asp[j] * f[:, 0])
        ph = _ellipse_phi(thw / (2.0 * np.pi), aa)                       # by arc length round the oval
        surf = C + (rr * np.cos(ph))[:, None] * nn_ + (rr * aa * np.sin(ph))[:, None] * bb_
        nrm = _unit((np.cos(ph) / rr)[:, None] * nn_ + (np.sin(ph) / (rr * aa))[:, None] * bb_)
        Q = surf + nrm * lift_all[:, None]                              # the yarn's centre over the barrel
        # cap v8: the ribbon's threads blended into each other over 0.08 mm (a flat ribbon with a groove between each
        # pair of its threads; v7's 0.15 mm fillet on four fat yarns read as one smooth strap)
        plan.add(STROKE_CONE, Q[:-1][seg], Q[1:][seg], r_thread, r_thread, 'add', 0.00008, tag)
        # and SOLID under it down into the barrel (cap v4): a short cylinder at each of the yarn's points from 0.1 mm
        # inside the barrel up to its centre. Floating over the barrel (0.13-0.73 mm of air under the threads) the bake's
        # search took the barrel under them: the knots baked as smooth sleeves, their occlusion black
        kp = keep & np.concatenate([seg, [False]]) | keep & np.concatenate([[False], seg])
        if kp.any():
            plan.add(STROKE_CYL, (surf - nrm * 0.0001)[kp], Q[kp], 0.8 * r_thread, 0.00003, 'add', 0.00006,
                     tag + ' (solid)')


# ------------------------------------------------------------------------------------------------- material pass
# Each sub-sample is CLASSIFIED by the block-out point under it (the low pushed to the bake's base: the pipings, the
# wreath's leaves, the cockade's face are block-out or plan geometry, so the paint and the sculpt agree by
# construction), then PAINTED; the texture tier's height is evaluated at the low's neighbouring sub-samples with the
# class held (no class flips inside one gradient) and composed into the baked normal
K_WOOL = wp.constant(0)       # the crown's worsted (top, wall)
K_FELT = wp.constant(1)       # the scarlet band and both pipings
K_CORD = wp.constant(3)       # twisted gold cord: the chin cords, the knots' braid
K_GILT = wp.constant(4)       # gilt metal: the grained buttons (sub 0), the cockade's rings and rye (1) and its arms (2),
                              # the stamped wreath (3)
K_LACQUER = wp.constant(5)    # the visor's lacquered top and rim
K_UNDER = wp.constant(6)      # the visor's underside
K_ENAMEL = wp.constant(7)     # the cockade's enamels: the red over its pebbled base (sub 0), the ribbon's black (1), red
                              # (2), yellow (3)
K_LEATHER = wp.constant(8)    # the sweatband
K_LINEN = wp.constant(9)      # the lining
# a wreath leaf's relief ends in a vertical edge at its outline (_wreath_relief); the paint takes the leaf this far past
# it, so the crisp edge is gold, never felt
LEAF_REACH = wp.constant(0.00012)
CK_RIB_W = wp.constant(CK_RIBBON_W)             # the ribbon's width (its stripes CK_STRIPES, written out in ck_ribbon)
assert tuple(round(b, 3) for _, b, _ in CK_STRIPES) == (0.019, 0.027, 0.055, 0.063, 0.092), 'ck_ribbon: CK_STRIPES'
WREATH_RING_K = wp.constant(WREATH_RING)       # the paint's twin of the relief's scarlet ring round the cockade
# the bake's occlusion reach scaled to the cap's relief, twice its tallest (the acorns on the wreath, 3 mm over the
# felt; v2's 15 mm read the cockade's rim over the wreath as pure black crescents), and the GOLD's occlusion never below
# AO_FLOOR_GOLD (metal under a rim is shaded, never black: the lead's decision 7, p1 >= 0.3 on the gold)
RELIEF_MAX = 0.0055            # cap v5: the wreath on its 1.2 mm backing, its leaves up to ~3.8 mm and its acorns ~5 mm
                               # over the felt (v4 3.0): the bake's cage follows it (forge)
AO_REACH = 0.009               # the occlusion's reach held at v5's first 9 mm (twice v4's relief; v2's 15 mm read the
                               # cockade's rim over the wreath as black crescents)
AO_FLOOR_GOLD = wp.constant(0.32)


@wp.struct
class Leaf:
    on: int             # 0 none, 1 a leaf, 2 a stalk, 3 an acorn
    idx: int            # which
    al: float           # a leaf: the way along it from its stalk (0..1); an acorn: the way out from its centre
    be: float           # a leaf: its offset across, over its half-width there (-1..1)
    edge: float         # the distance in from the outline (m; negative outside)


@wp.struct
class Kind:
    k: int              # K_*
    sub: int            # felt: 1 a piping; gilt: 0 a button, 1 the cockade's rings and rye, 2 its arms, 3 / 4 / 5 the
                        # wreath's leaf / stalk / acorn; enamel: 0 the red, 1 / 2 / 3 the ribbon's black / red / yellow
    idx: int            # the wreath: the leaf's, stalk's or acorn circle's index
    st: float           # the wreath: Leaf.al; the cockade: u (D)
    edge: float         # the wreath: Leaf.be; the cockade: v (D)


@wp.struct
class Finish:
    col: wp.vec3        # base colour (linear; a metal's F0)
    rough: float
    metal: float
    fuzz: float         # masks R: the runtime's fuzz / sheen (cloth only: 0 on metal, lacquer and enamel)
    cls: float          # masks G: 0 worsted, 1/3 felt, 2/3 leather and linen, 1 hard (metal, lacquer, enamel)
    zone: float         # masks B: the palette zone (PALETTE: 0 crown and the inside, 1/3 band and pipings, 2/3 gold,
                        # 1 visor)
    wear: float         # masks A: handling wear
    ao_floor: float     # the baked occlusion's floor here (ORM R): AO_FLOOR_GOLD on the gold, 0 elsewhere


@wp.func
def _tab(t: wp.array(dtype=wp.float32), x: float):
    """a table over [0, 1], linear"""
    n = t.shape[0]
    f = wp.clamp(x, 0.0, 1.0) * float(n - 1)
    i = wp.min(int(f), n - 2)
    g = f - float(i)
    return t[i] * (1.0 - g) + t[i + 1] * g


@wp.func
def seg_dist(p: wp.vec3, a: wp.vec3, b: wp.vec3):
    ab = b - a
    t = wp.clamp(wp.dot(p - a, ab) / wp.max(wp.dot(ab, ab), 1.0e-20), 0.0, 1.0)
    return wp.length(p - (a + ab * t))


@wp.func
def seg2(x: float, y: float, ax: float, ay: float, bx: float, by: float):
    return seg_dist(wp.vec3(x, y, 0.0), wp.vec3(ax, ay, 0.0), wp.vec3(bx, by, 0.0))


@wp.func
def band_uy(p: wp.vec3, rxb: float, rzb: float, utab: wp.array(dtype=wp.float32)):
    """a point's BAND coordinates (u the arc along the band's face from the front, + toward +X; y its height; 0)"""
    phi = wp.atan2(p[0] / rxb, p[2] / rzb)
    return wp.vec3(_tab(utab, (phi + 3.14159265) / 6.2831853), p[1], 0.0)


@wp.func
def band_pt(phi: float, y: float, w: float, rxb: float, rzb: float):
    """band_frame's point: the band's outer face at azimuth phi and height y, w along its normal"""
    nx = wp.sin(phi) / rxb
    nz = wp.cos(phi) / rzb
    ln = wp.sqrt(nx * nx + nz * nz)
    return wp.vec3(rxb * wp.sin(phi) + nx / ln * w, y, rzb * wp.cos(phi) + nz / ln * w)


@wp.func
def pipe_E(phc: float, S: wp.array(dtype=wp.float32)):
    """the crown piping's centreline at the elliptic azimuth phc (pipe_centre's twin)"""
    cf = wp.max(wp.cos(phc), 0.0)
    cb = wp.max(-wp.cos(phc), 0.0)
    wf = cf * cf * (1.0 + S[26] * (1.0 - cf))          # rise_w's twin (S[26] rise_round, S[27] rise_back)
    wb = cb * cb * (1.0 + S[26] * (1.0 - cb))
    return wp.vec3(S[0] * wp.sin(phc), S[2] + S[3] + (S[4] - S[3]) * wf + (S[27] - S[3]) * wb, S[1] * wp.cos(phc))


@wp.func
def crown_pipe_near(p: wp.vec3, S: wp.array(dtype=wp.float32)):
    """cap v7: the crown piping's centreline point nearest p (pipe_dist's crown half: the point's own azimuth refined by
    two Gauss-Newton steps)"""
    phc = float(wp.atan2(p[0] / S[0], p[2] / S[1]))
    E = wp.vec3(pipe_E(phc, S))
    for it in range(2):
        dE = (pipe_E(phc + 0.001, S) - pipe_E(phc - 0.001, S)) / 0.002
        phc = phc + wp.dot(p - E, dE) / wp.max(wp.dot(dE, dE), 1.0e-12)
        E = pipe_E(phc, S)
    return E


@wp.func
def pipe_dist(p: wp.vec3, S: wp.array(dtype=wp.float32), utab: wp.array(dtype=wp.float32)):
    """the distances to the crown piping's centreline (cap v6: on the wall's seam under the roll) and to the band top's
    (on its seam, raised at the front centre: band_top's twin, S[32..34]). Cap v6 (10-26): the centreline's NEAREST
    point, the point's own azimuth refined by two Gauss-Newton steps: at that azimuth alone the distance read up to
    0.14 mm past the tube's radius on its top and bottom where the piping climbs the front (the tube square to a sloped
    centreline; scratch/piping_dist_probe.py), so a tight paint tolerance greyed a line along the piping"""
    phc = float(wp.atan2(p[0] / S[0], p[2] / S[1]))
    E = wp.vec3(pipe_E(phc, S))
    for it in range(2):
        dE = (pipe_E(phc + 0.001, S) - pipe_E(phc - 0.001, S)) / 0.002
        phc = phc + wp.dot(p - E, dE) / wp.max(wp.dot(dE, dE), 1.0e-12)
        E = pipe_E(phc, S)
    phb = wp.atan2(p[0] / S[6], p[2] / S[7])
    ub = wp.abs(_tab(utab, (phb + 3.14159265) / 6.2831853))
    yb = S[2] + S[32] * proc.smoothstep(S[34], S[33], ub)
    B = band_pt(phb, yb, 0.00025, S[6], S[7])
    return wp.vec2(wp.length(p - E), wp.length(p - B))


@wp.func
def twill_grain(p: wp.vec3, reg: int, S: wp.array(dtype=wp.float32), seed: int):
    """cap v7 (the lead's decision 6: "the twill an irregular wool weave at her strength (2.4 L* rms), not carbon-fibre
    stripes and no chevrons on the roll"): the worsted's visible GRAIN as an IRREGULAR weave, 0..1 (0.5 its mean): the
    yarns' lit and shaded crossings at the yarn scale S[29] and half of it, and the slubs (the yarn's uneven thickness)
    at three times it, all SOLID noise in the cloth's own space (one field over the top, the roll and the wall: no frame
    meets another, no chevron), no period [the contrast M egmar3b's crown wall: a fine texture of 2.1-2.7 L* rms
    high-passed whose spectrum holds only a weak diagonal share (0.05-0.20), research/cap_gdr_scripts/v6_measure.py].
    The 0.7 mm wales themselves (2 texels at the cap's density) fade out under the texel floor. Cap v6: cos streaks 1.4 mm
    apart in the top's (x, z) and the wall's (arc, y) frames: carbon-fibre stripes, chevrons on the roll"""
    n1 = proc.noise3(p / S[29], seed + 61)
    n2 = proc.noise3(p / (0.5 * S[29]), seed + 62)
    n3 = proc.noise3(p / (3.0 * S[29]), seed + 64)
    # (the second v7 forge's slubs at 0.22 mottled the wall in centimetre blotches at her camera, where her wool reads as
    # a fine even texture: the slubs now a trace, the yarn scales carry the grain)
    return wp.clamp(0.5 + 0.34 * n1 + 0.26 * n2 + 0.07 * n3, 0.0, 1.0)


@wp.func
def twill_wale(p: wp.vec3, reg: int, S: wp.array(dtype=wp.float32)):
    """cap v8 (the lead's decision 4: "the cloth a fine, regular DIAGONAL TWILL whose direction changes across a crisp
    stitched front seam (c_twill.png), at her strength, not directionless mottled noise"): the worsted's WALES, 0..1 (1
    a wale's crown), S[14] apart at 45 deg: on the wall in its own (arc, height) frame with the arc taken from the front
    seam each way (|azimuth|: the two side panels cut mirror-wise, so the wales rise away from the front seam on both
    sides and meet it in a V, and meet again at the back seam), on the top panel (the roll with it) one diagonal across
    it; a rounded ridge with a narrow groove (cos^0.6) [M egmar3b's crown wall at 9x, tests/out/cap/v7check/c_twill.png:
    a regular diagonal either side of the stitched front seam]. v7's twill_grain alone read as mottled fleece"""
    x = (p[0] + p[2]) * 0.70710678
    if reg == 1:
        a = wp.abs(wp.atan2(p[0], p[2])) * wp.sqrt(p[0] * p[0] + p[2] * p[2])
        x = (p[1] - a) * 0.70710678
    c = 0.5 + 0.5 * wp.cos(6.2831853 * x / S[14])
    return wp.pow(c, 0.6)


@wp.func
def seam_stitch(p: wp.vec3, reg: int, S: wp.array(dtype=wp.float32)):
    """cap v8 (decision 4, "a crisp stitched front seam"): the wall's front and back seams' TOPSTITCHING, 0..1 (1 a
    stitch's hole): a row of stitches each side S[44] from the seam's centre, 1.8 mm apart up the wall [E: a worsted
    cap's topstitch; her seam at 9x a dark line with a stitched edge]"""
    out = float(0.0)
    if reg == 1:
        ang = wp.abs(wp.atan2(p[0], p[2]))
        a = wp.min(ang, 3.14159265 - ang) * wp.sqrt(p[0] * p[0] + p[2] * p[2])
        d = a - S[44]
        f = p[1] / 0.0018
        e = (f - wp.floor(f) - 0.5) * 0.0018 * 0.55
        out = 1.0 - proc.smoothstep(0.00022, 0.00042, wp.sqrt(d * d + e * e))
    return out


@wp.func
def cord_fibre(at: wp.vec4, S: wp.array(dtype=wp.float32), seed: int):
    """cap v7 (the lead's decision 4: "gold bullion thread, matte ... fine anisotropic fibre glints"): a cord's FIBRES
    at a low point's attributes (ring_tube's: s its arc along the cord, cos / sin of its angle round the tube), 0..1 (1 a
    fibre's crown): fine grooves running S[41] off the cord's axis [M egmar3b: 5-15 deg], S[40] of them round the cord (an
    integer, so the pattern closes on itself round the tube), their spacing wandering a little along it"""
    th = wp.atan2(at[2], at[1])
    lam = 6.2831853 * S[45] * wp.cos(S[41]) / S[40]
    c = (-at[0] * wp.sin(S[41]) + S[45] * th * wp.cos(S[41])) / lam
    c = c + 0.30 * proc.noise3(wp.vec3(at[0] / 0.004, 1.3 * at[1], 1.3 * at[2]), seed + 81)
    return 0.5 + 0.5 * wp.cos(6.2831853 * c)


@wp.func
def poly_sd(x: float, y: float, P: wp.array(dtype=wp.vec2), s0: int, n: int):
    """the signed distance (negative inside) of (x, y) to the polygon P[s0 : s0 + n]: _poly_sd_np's twin"""
    d = float(1.0e9)
    inside = int(0)
    for k in range(n):
        a = P[s0 + k]
        b = P[s0 + (k + 1) % n]
        e = b - a
        w = wp.vec2(x - a[0], y - a[1])
        t = wp.clamp(wp.dot(w, e) / wp.max(wp.dot(e, e), 1.0e-20), 0.0, 1.0)
        d = wp.min(d, wp.length(w - e * t))
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * e[0] / e[1]:
                inside = 1 - inside
    if inside == 1:
        d = -d
    return d


@wp.func
def ck_arms_sd(u: float, v: float, CKP: wp.array(dtype=wp.vec2), CKI: wp.array(dtype=wp.vec2i),
               S: wp.array(dtype=wp.float32)):
    """the cockade's gold arms (D units, negative inside): the hinge boss and ck_polys()'s polygons, ck_arms_sd_np's
    twin"""
    d = wp.sqrt((u - S[22]) * (u - S[22]) + (v - S[23]) * (v - S[23])) - S[24]
    for k in range(CKI.shape[0]):
        si = CKI[k]
        d = wp.min(d, poly_sd(u, v, CKP, si[0], si[1]))
    return d


@wp.func
def ck_ribbon(u: float, v: float, RIB: wp.array(dtype=wp.vec4)):
    """the ribbon's parts under (u, v) (CK_RIBBON_PARTS, packed 4 vec4 a part: (u_c, vtop, slope, sag), (half, -, -, -),
    end 0, end 1): (class 0 none / 1 black / 2 red / 3 yellow / 4 a gilt line, the depth across 0..1, the distance in
    from the nearer end); ck_ribbon_parts_np's twin"""
    cls = float(0.0)
    acr = float(0.0)
    dend = float(0.0)
    for k in range(RIB.shape[0] // 4):
        if cls == 0.0:
            a = RIB[4 * k]
            hl = RIB[4 * k + 1][0]
            e0 = RIB[4 * k + 2]
            e1 = RIB[4 * k + 3]
            du = u - a[0]
            top = a[1] + a[2] * du - a[3] * wp.max(hl * hl - du * du, 0.0)
            x = top - v
            d0 = float(9.0)
            if e0[2] != 0.0 or e0[3] != 0.0:
                d0 = (u - e0[0]) * e0[2] + (v - e0[1]) * e0[3]
            d1 = float(9.0)
            if e1[2] != 0.0 or e1[3] != 0.0:
                d1 = (u - e1[0]) * e1[2] + (v - e1[1]) * e1[3]
            if x >= 0.0 and x <= CK_RIB_W and d0 >= 0.0 and d1 >= 0.0 and wp.abs(du) <= hl + 0.08:
                cls = 3.0
                if x < 0.019:
                    cls = 1.0
                elif x < 0.027:
                    cls = 4.0
                elif x < 0.055:
                    cls = 2.0
                elif x < 0.063:
                    cls = 4.0
                acr = x / CK_RIB_W
                dend = wp.min(d0, d1)
    return wp.vec3(cls, acr, dend)


@wp.func
def ck_ribbon_h(rb: wp.vec3, gilt: int):
    """cap v6 (the lead's decision 4): the ribbon's relief (m) under a ck_ribbon sample rb = (class, depth across 0..1,
    the distance in from its nearer end, D): each part WRAPPING the ring, bulging 0.24 mm across its width; at each end
    a FOLD where it turns under the stalks (it dips over 0.02 D and creases 0.012 D in); its stripes' enamel fields
    slightly domed between RAISED GILT WALLS standing 0.10 mm over them, crisp (gilt 1: a wall sample; 0: an enamel
    stripe) [M the close-up: the gilt lines 0.006-0.012 D between the stripes, the parts within 10 deg of horizontal,
    their ends cut on the slant under the stalks (CAP_GDR §6.4); the heights E]. v5's 0.11 mm bulge with its gilt lines
    0.03 mm over the enamel read as flat striped bars (the v5 check)"""
    acr = rb[1]
    wrap = 0.00024 * (1.0 - (2.0 * acr - 1.0) * (2.0 * acr - 1.0))
    fold = proc.smoothstep(0.0, 0.02, rb[2]) - 0.25 * wp.exp(-((rb[2] - 0.012) / 0.003) * ((rb[2] - 0.012) / 0.003))
    xr = acr * CK_RIB_W
    if gilt == 1:
        # the wall's crisp profile across its own width (the stripes' boundaries at 0.019 / 0.027 and 0.055 / 0.063)
        a = float(0.019)
        if xr >= 0.041:
            a = 0.055
        t = wp.clamp((xr - a) / 0.008, 0.0, 1.0)
        top = proc.smoothstep(0.0, 0.18, t) * (1.0 - proc.smoothstep(0.82, 1.0, t))
        return wrap * fold + 0.00004 + 0.00010 * top
    sa = float(0.063)
    sb = float(0.092)
    if xr < 0.019:
        sa = 0.0
        sb = 0.019
    elif xr < 0.055:
        sa = 0.027
        sb = 0.055
    ts = wp.clamp((xr - sa) / (sb - sa), 0.0, 1.0)
    return wrap * fold + 0.00003 * (1.0 - (2.0 * ts - 1.0) * (2.0 * ts - 1.0))


@wp.func
def ck_pebble(u: float, v: float, s: float):
    """the enamel's pebbled base: a hexagonal lattice of pebbles s apart (D units; CAP_GDR §6.5: 0.027-0.031 D,
    staggered), 1 on a pebble's crown, 0 in the gaps. Cap v8 (the lead's decision 5: "the disc's pebbles crisp glassy
    glints"): each pebble a round DOME of radius 0.46 s over its nearest lattice point, steep at its foot (sqrt(1 -
    (d / R)^2)) with flat narrow gaps, so each catches its own glint through the glossy enamel; v6-v7 three plane waves
    60 deg apart: a soft regular dimpling"""
    # the lattice a1 = (s, 0), a2 = (s / 2, s sqrt 3 / 2): the point's fractional coordinates, the nearest of the 4 + 2
    # candidate points round it
    fb = v / (0.8660254 * s)
    fa = u / s - 0.5 * fb
    ia = wp.floor(fa)
    ib = wp.floor(fb)
    best = float(1.0e9)
    for da in range(-1, 3):
        for db in range(-1, 3):
            a_ = ia + float(da)
            b_ = ib + float(db)
            cu = (a_ + 0.5 * b_) * s
            cv = b_ * 0.8660254 * s
            best = wp.min(best, (u - cu) * (u - cu) + (v - cv) * (v - cv))
    q = wp.sqrt(best) / (0.46 * s)
    return wp.sqrt(wp.max(1.0 - q * q, 0.0))


@wp.func
def ck_ear_chevrons(r: float, th: float, t0: float, t1: float, ra: float, rb: float, pitch: float):
    """cap v8 (the lead's decision 5: "the rye as ONE wide ear of stacked V chevrons each side ... as her close-up
    shows"), 0..1: one ear across the ring's whole width (its spine at mid-radius), from its tip (t0, toward the
    parting bar) to its foot (t1): CHEVRONS `pitch` apart (D) along it, each two arms from the spine back and out to the
    ear's edges at 55 deg to the spine (their apex toward the tip), each arm a stamped ridge 0.012 D across of three
    grains end to end (a crisp plateau, 1 - q^3) [M the close-up's right side at 39 px/mm, tests/out/cap/v7check/
    c_rye_side.png: chevrons ~1.2 mm apart spanning the ring, apex up]. v6-v7: four concentric rows of small grains"""
    rm = 0.5 * (ra + rb)
    hw = 0.5 * (rb - ra)
    s = rm * (th - t0) * 0.017453293
    L = rm * (t1 - t0) * 0.017453293
    c = wp.abs(r - rm)
    out = float(0.0)
    if s >= 0.0 and s <= L and c < hw:
        cot = 0.70020754                              # cot 55 deg
        q = s - c * cot
        k = wp.floor(q / pitch + 0.5)
        sk = k * pitch
        if sk >= -0.25 * pitch and sk <= L:
            d = (q - sk) * 0.81915204                  # the distance to the arm (sin 55 deg)
            w = d / 0.0060
            ridge = wp.max(1.0 - w * w * w * w, 0.0)
            g = 0.5 + 0.5 * wp.cos(6.2831853 * c / (hw / 3.0))
            grains = 0.55 + 0.45 * wp.sqrt(g)
            edge = proc.smoothstep(hw, 0.88 * hw, c)
            out = ridge * grains * edge
    return out


@wp.func
def ck_rye_h(u: float, v: float):
    """the rye ring's FINE relief (cap v5, the lead's decision 6), 0..1 over the ear field (r 0.330-0.468 D): per side
    from the top (CK_RYE's zones) the AWNS, eight long fine concentric lines from the parting bar to the half ears (fine:
    0.0064 D across, 0.17 mm), the two half-width ears' grains side by side and the full ear's (ck_ear_grains), the
    stalks' fine lines, and the stalks crossing the ribbon in its gaps (CK_GAPS). Cap v4 carved fat chevrons and a few
    fat awn bars in the sculpt (0.15 mm voxels); its ear bodies stay there, these grains are the texture's (13 px/mm)"""
    r = wp.sqrt(u * u + v * v)
    h = float(0.0)
    if r > 0.330 and r < 0.468:
        th = wp.atan2(wp.abs(u), v) * 57.29578
        a0 = float(4.0)
        h0 = float(20.0)
        h1 = float(52.0)
        f0 = float(55.0)
        f1 = float(105.0)
        s0 = float(105.0)
        s1 = float(112.0)
        g0 = float(128.0)
        g1 = float(145.0)
        if u < 0.0:
            a0 = 3.0
            h0 = 15.0
            h1 = 47.0
            f0 = 50.0
            f1 = 93.0
            s0 = 93.0
            s1 = 110.0
            g0 = 127.0
            g1 = 145.0
        if th > a0 and th < h0 + 3.0:
            # cap v7 (the lead's decision 7: "fine awns"): the AWNS ten FINE stamped hairlines 0.0136 D (0.36 mm) apart
            # across the ring, each 0.0024 D (0.06 mm) across, from the parting bar into the half ears [M the close-up's
            # top, research/cap_gdr_work/v6_ck_top_x4.png]; v6's 0.0058 D flat-topped ridges read as bold concentric
            # grooves (the v6 check)
            w = proc.smoothstep(a0, a0 + 0.8, th) * (1.0 - proc.smoothstep(h0 + 0.5, h0 + 3.0, th))
            b = float(0.0)
            for k in range(10):
                rk = 0.3355 + 0.0136 * float(k)
                b = wp.max(b, 1.0 - proc.smoothstep(0.0008, 0.0016, wp.abs(r - rk)))
            h = wp.max(h, 0.85 * w * b)
        # cap v8 (the lead's decision 5): ONE wide ear of stacked chevrons a side, from under the awns to the full ear's
        # end (ck_ear_chevrons), then LONG FINE STALKS below it down to the ribbon's loops: nine hairlines along the ring
        # 0.0025 D across (her close-up's lower ring). v7: two half ears beside each other over a full ear, four
        # concentric rows round the ring
        if th >= h0 and th <= f1:
            h = wp.max(h, ck_ear_chevrons(r, th, h0, f1, 0.334, 0.466, 0.046))
        if th > f1 - 2.0 and th < g0:
            ws = proc.smoothstep(f1 - 2.0, f1 + 2.0, th)
            b = float(0.0)
            for k in range(9):
                rk = 0.342 + (0.458 - 0.342) * float(k) / 8.0
                b = wp.max(b, 1.0 - proc.smoothstep(0.0007, 0.0014, wp.abs(r - rk)))
            h = wp.max(h, 0.75 * ws * b)
        if th >= g0 - 2.0 and th <= g1 + 2.0:
            # the stalks, where they cross over the ribbon below its loops: fine lines (0.0030 D), not bold grooves
            b = float(0.0)
            for k in range(6):
                rk = 0.345 + (0.450 - 0.345) * float(k) / 5.0
                b = wp.max(b, 1.0 - proc.smoothstep(0.0010, 0.0020, wp.abs(r - rk)))
            h = wp.max(h, 0.7 * b)
    return h


@wp.func
def ck_hinge(rh: float):
    """the hinge boss's radial relief at rh (D units; CAP_GDR §6.7): the centre pin, the grooves at 0.017, 0.034 and
    0.044, the raised rings at 0.028 and 0.037 (CK_HINGE_RINGS), in units of their height"""
    h = 0.6 * (1.0 - proc.smoothstep(0.004, 0.008, rh))
    h = h - wp.exp(-((rh - 0.017) / 0.0035) * ((rh - 0.017) / 0.0035))
    h = h + 0.8 * wp.exp(-((rh - 0.028) / 0.0035) * ((rh - 0.028) / 0.0035))
    h = h - 0.8 * wp.exp(-((rh - 0.034) / 0.0020) * ((rh - 0.034) / 0.0020))
    h = h + 0.6 * wp.exp(-((rh - 0.037) / 0.0020) * ((rh - 0.037) / 0.0020))
    h = h - wp.exp(-((rh - 0.044) / 0.0025) * ((rh - 0.044) / 0.0025))
    return h


@wp.func
def wreath_at(q: wp.vec3, LQ: wp.array(dtype=wp.vec2), LQI: wp.array(dtype=wp.vec2i), SP: wp.array(dtype=wp.vec3),
              SI: wp.array(dtype=wp.vec3i), AC: wp.array(dtype=wp.vec4), r_s: float):
    """the wreath's part under a band point (q: band coordinates): an acorn knob (they lie on the leaves), a leaf (cap
    v8: inside its TRACED outline, LQ / LQI top layer first, or within LEAF_REACH of it: the distance in from the
    outline) or a stalk (under the leaves)"""
    on = int(0)
    idx = int(-1)
    al_ = float(0.0)
    be_ = float(0.0)
    edge = float(-1.0)
    for k in range(AC.shape[0]):
        ac = AC[k]
        dd = wp.length(wp.vec2(q[0] - ac[0], q[1] - ac[1]))
        if on == 0 and dd < ac[2]:
            on = 3
            idx = k
            al_ = dd / ac[2]
            edge = ac[2] - dd
    for k in range(LQI.shape[0]):
        if on == 0:
            li = LQI[k]
            sdl = poly_sd(q[0], q[1], LQ, li[0], li[1])
            if sdl < LEAF_REACH:
                on = 1
                idx = k
                edge = -sdl
    if on == 0:
        for k in range(SI.shape[0]):
            sk = SI[k]
            if on == 0:
                best = float(1.0e9)
                for j in range(sk[0], sk[0] + sk[1] - 1):
                    a = SP[j]
                    ab = SP[j + 1] - a
                    t = wp.clamp(wp.dot(q - a, ab) / wp.max(wp.dot(ab, ab), 1.0e-20), 0.0, 1.0)
                    best = wp.min(best, wp.length(q - (a + ab * t)))
                if best < r_s:
                    on = 2
                    idx = k
                    edge = r_s - best
    out = Leaf()
    out.on = on
    out.idx = idx
    out.al = al_
    out.be = be_
    out.edge = edge
    return out


@wp.func
def classify(hp: wp.vec3, reg: int, S: wp.array(dtype=wp.float32), G3: wp.array(dtype=wp.vec3),
             utab: wp.array(dtype=wp.float32), LQ: wp.array(dtype=wp.vec2), LQI: wp.array(dtype=wp.vec2i),
             SP: wp.array(dtype=wp.vec3), SI: wp.array(dtype=wp.vec3i), AC: wp.array(dtype=wp.vec4),
             CKP: wp.array(dtype=wp.vec2), CKI: wp.array(dtype=wp.vec2i), RIB: wp.array(dtype=wp.vec4),
             BKP: wp.array(dtype=wp.vec2)):
    """the material under a block-out point hp on region reg (S, G3: run_material's constants; RIB the cockade's ribbon
    parts; BKP the wreath's backing outline in band coordinates)"""
    k = int(K_WOOL)
    sub = int(0)
    idx = int(-1)
    st = float(0.0)
    edge = float(0.0)
    if reg == 0 or reg == 1:
        # cap v6 (the second forge's gate 15, 10-26): the crown piping within 0.03 mm of its tube (v5 0.15): hp is the
        # analytic block-out's point, exact on the tube, and 0.15 mm painted the cloth red for ~0.8 mm where it leaves
        # the tube above (the collar up to the roll) and below (the wall): ~1 px over her piping's 6-7 px at her camera
        if pipe_dist(hp, S, utab)[0] < S[5] + 0.00003:
            k = K_FELT
            sub = 1
    elif reg == 2:
        k = K_FELT
        if pipe_dist(hp, S, utab)[1] < S[28] + 0.00015:
            sub = 1
        else:
            q = band_uy(hp, S[6], S[7], utab)
            e = wreath_at(q, LQ, LQI, SP, SI, AC, S[12])
            # the scarlet ring round the cockade (WREATH_RING): the backing's felt, as the leaves stop there
            dc = hp - G3[0]
            rc = wp.length(dc - G3[1] * wp.dot(dc, G3[1]))
            if rc < 0.5 * S[9] + WREATH_RING_K:
                e.on = 0
            if e.on > 0:
                k = K_GILT
                sub = 2 + e.on
                idx = e.idx
                st = e.al
                edge = e.be
            else:
                # cap v5: the SCALLOPED BACKING (wreath_backing): felt, its distance in from its edge for the outline
                sdb = poly_sd(q[0], q[1], BKP, 0, BKP.shape[0])
                if sdb < 0.0:
                    sub = 2
                    edge = sdb
    elif reg == 3 or reg == 5:
        k = K_LACQUER
    elif reg == 4:
        k = K_UNDER
    elif reg == 6 or reg == 7:
        k = K_CORD
    elif reg == 8:
        k = K_GILT
    elif reg == 9:
        # the cockade's face (CK_*): its own (u, v) in D, the red disc and the arms on it, the ribbon on the rye ring
        d = hp - G3[0]
        u = wp.dot(d, G3[2]) / S[9]
        v = wp.dot(d, G3[3]) / S[9]
        k = K_GILT
        sub = 1
        rd = wp.sqrt((u - S[10]) * (u - S[10]) + (v - S[11]) * (v - S[11]))
        r = wp.sqrt(u * u + v * v)
        if rd < S[13]:
            if ck_arms_sd(u, v, CKP, CKI, S) < 0.0:
                sub = 2
            else:
                k = K_ENAMEL
                sub = 0
        elif r > S[17] and r < S[18]:
            rb = ck_ribbon(u, v, RIB)
            if rb[0] > 0.5 and rb[0] < 3.5:
                k = K_ENAMEL
                sub = int(rb[0] + 0.5)
        st = u
        edge = v
    else:
        k = K_LINEN
        if hp[1] < S[8] + 0.0003:
            k = K_LEATHER
    out = Kind()
    out.k = k
    out.sub = sub
    out.idx = idx
    out.st = st
    out.edge = edge
    return out


@wp.func
def height_at(p: wp.vec3, kd: Kind, reg: int, at: wp.vec4, tex: float, S: wp.array(dtype=wp.float32),
              G3: wp.array(dtype=wp.vec3), utab: wp.array(dtype=wp.float32), vtab: wp.array(dtype=wp.float32),
              RIB: wp.array(dtype=wp.vec4), CKP: wp.array(dtype=wp.vec2), CKI: wp.array(dtype=wp.vec2i), seed: int):
    """the texture tier's height (m) at p with the class held; every octave fades out below 3 texels of THIS island
    (tex: its own texel, so the 2x wreath island and the 4x cockade keep what the 1x crown cannot)"""
    h = float(0.0)
    if kd.k == K_WOOL:
        # cap v8 (the lead's decision 4): the worsted's regular diagonal TWILL (twill_wale, S[14] apart: 3.4 texels at
        # the cap's density, resolved), its yarns' irregularity a trace (twill_grain), the seams' topstitching
        h = S[15] * (twill_wale(p, reg, S) - 0.6) * proc.smoothstep(2.2, 3.0, S[14] / tex)
        h = h + S[30] * (twill_grain(p, reg, S, seed) - 0.5) * proc.smoothstep(2.5, 4.0, S[29] / tex)
        h = h - 0.00005 * seam_stitch(p, reg, S) * proc.smoothstep(1.6, 2.4, 0.0008 / tex)
    elif kd.k == K_FELT:
        lam = float(0.0024)
        amp = float(1.0)
        for i in range(3):
            h = h + S[16] * amp * proc.smoothstep(2.5, 4.0, lam / tex) * proc.noise3(p / lam, seed + 11 + i)
            lam = lam * 0.5
            amp = amp * 0.7
    elif reg == 9:
        # the cockade: the pebbled base under the red enamel (its bumps catch the light through it), the hinge boss's
        # rings (CAP_GDR §6.5, §6.7), the rye's grains and awns and the ribbon's walls; the arms and the boss itself are
        # the sculpt's. Cap v6 (10-26): (u, v) from THIS sample's point p, as classify computes them; they were read from
        # kd (the texel's first sample's), so the gradient's two neighbours (k_cap's pbx, pby) saw the same (u, v) and
        # every relief here came out flat: no rye, no pebbles, no hinge rings, no ribbon walls in the normal map through
        # v6's third forge (the albedo, painted from kd, carried them)
        dc = p - G3[0]
        u = wp.dot(dc, G3[2]) / S[9]
        v = wp.dot(dc, G3[3]) / S[9]
        if kd.k == K_ENAMEL and kd.sub == 0:
            # cap v7 (the lead's decision 7): the pebbles in the NORMAL map, each a dome S[42] high; cap v8 (decision 5)
            # each a crisp round dome with steep sides (ck_pebble), so each throws its own glint in the glossy ruby
            pb = ck_pebble(u, v, S[25])
            h = S[42] * (pb - 0.45) * proc.smoothstep(2.5, 4.0, S[25] * S[9] / tex)
        elif kd.k == K_GILT and kd.sub == 2:
            # cap v7 (decision 7: "the hammer and compass bright gilt with readable relief"): each stamped face falls
            # 0.09 mm over its last 0.010 D (0.26 mm) to its edge, a rounded chamfer that catches the light; the hinge
            # boss's rings inside it
            sd = ck_arms_sd(u, v, CKP, CKI, S)
            # cap v8 (decision 5, "bright, high-relief"): each stamped face ROUNDS over 0.14 mm across its last 0.022 D
            # (0.58 mm: a convex bevel whose slopes take the key and the softbox; v7's 0.09 mm over 0.010 D left a flat
            # top that mirrored the dim studio square-on)
            qb = proc.smoothstep(0.0, 0.022, -sd)
            h = 0.00014 * (wp.sqrt(qb) - 1.0) * proc.smoothstep(2.0, 3.5, 0.010 * S[9] / tex)
            rh = wp.sqrt((u - S[22]) * (u - S[22]) + (v - S[23]) * (v - S[23]))
            if rh < S[24]:
                h = h + 0.000030 * ck_hinge(rh) * proc.smoothstep(2.0, 3.5, 0.006 * S[9] / tex)
        elif kd.k == K_GILT and kd.sub == 1:
            # the rye ring's grains, awns and stalks (ck_rye_h: cap v6 a dense crisp stamped herringbone, its fade by
            # the grain's own 0.0094 D width), and the ribbon's RAISED gilt lines (ck_ribbon_h)
            h = 0.00012 * ck_rye_h(u, v) * proc.smoothstep(2.0, 3.5, 0.0094 * S[9] / tex)
            rb = ck_ribbon(u, v, RIB)
            if rb[0] > 3.5:
                h = ck_ribbon_h(rb, 1)
        if kd.k == K_ENAMEL and kd.sub > 0:
            h = ck_ribbon_h(ck_ribbon(u, v, RIB), 0)
    elif kd.k == K_GILT and kd.sub >= 3 and kd.sub <= 5:
        # a wreath leaf, stalk or acorn knob: cap v8 (the lead's decision 1: "a SATIN stamped surface (no glossy melted
        # gold, no crinkled foil, no crease streaks)"): the die's fine STIPPLE, a soft grain at 0.5 mm (2.7 texels on
        # the band's 1.8x island) only 0.012 mm deep, which breaks each broad highlight into a satin sheen with the
        # roughness (wreath_rough); the dome, the beaded midrib and the knobs are the sculpt's (leaf_top)
        h = S[46] * proc.noise3(p / 0.0005, seed + 101) * proc.smoothstep(2.0, 3.0, 0.0005 / tex)
    elif kd.k == K_CORD:
        if reg == 6:
            # cap v7 (the lead's decision 4): the cords' fine FIBRES (cord_fibre), their grooves along the threads
            lam = 6.2831853 * S[45] * wp.cos(S[41]) / S[40]
            h = S[39] * (cord_fibre(at, S, seed) - 0.5) * proc.smoothstep(1.8, 2.8, lam / tex)
        else:
            # the knots' strands: a fine thread grain (their direction turns over the Turk's head: no one frame)
            h = 0.000014 * proc.noise3(p / 0.0006, seed + 83) * proc.smoothstep(2.0, 3.5, 0.0006 / tex)
    elif kd.k == K_GILT and reg == 8:
        cl = proc.cellular3(p / S[20], 0.9, seed + 71)                 # the buttons' graining
        h = 0.000008 * (proc.smoothstep(0.0, 0.2, cl.edge) - 0.5) * proc.smoothstep(2.5, 4.0, S[20] / tex)
    elif kd.k == K_LEATHER:
        cl = proc.cellular3(p / 0.0011, 0.9, seed + 51)
        h = 0.00002 * (proc.smoothstep(0.0, 0.18, cl.edge) - 0.5) * proc.smoothstep(2.5, 4.0, 0.0011 / tex)
    return h


@wp.func
def paint(kd: Kind, p: wp.vec3, n: wp.vec3, reg: int, at: wp.vec4, aol: float, cav: float,
          C: wp.array(dtype=wp.vec3), R: wp.array(dtype=wp.float32), S: wp.array(dtype=wp.float32),
          G3: wp.array(dtype=wp.vec3), vtab: wp.array(dtype=wp.float32), seed: int):
    """one sub-sample's finish (CAP_REFERENCE §4 colours, §5 wear where hands handle a cap)"""
    col = wp.vec3(0.5)
    rough = float(0.5)
    metal = float(0.0)
    fuzz = float(0.0)
    cls = float(1.0)
    zone = float(0.0)
    wear = float(0.0)
    ao_floor = float(0.0)
    # the metals' valleys: the bake's local AO and cavity (the twist's and the braid's grooves, the stitches' gaps)
    tv = wp.clamp(wp.clamp(-aol * 30.0, 0.0, 1.0) * 0.5 + (1.0 - proc.smoothstep(0.55, 0.85, cav)) * 0.7, 0.0, 1.0)
    if kd.k == K_WOOL:
        cloud = S[19] * 4.0 * (0.6 * proc.fbm3(p / 0.02, 3, 2.0, 0.5, seed + 31) +
                               0.4 * proc.noise3(p / 0.006, seed + 37))
        # cap v5 (the lead's decision 3): NO handling shine on the crown (no GDR photo shows one; g01 and g02 are clean;
        # v4 painted one at the front rim from ACCESSORY_REFERENCE's non-GDR caps); cap v6 (decision 6): the twill's
        # visible grain in the cloth's tone too (twill_grain: its ribs' lit and shaded yarns, S[31] each way)
        # cap v8 (decision 4): the wales' lit crowns and shaded grooves in the tone too (S[43] each way), the yarns'
        # irregularity a trace (S[31]), the topstitches' holes darker
        col = C[0] * wp.exp(cloud + 0.8 * aol) * (1.0 + 2.0 * S[31] * (twill_grain(p, reg, S, seed) - 0.5)) * \
            (1.0 + 2.0 * S[43] * (twill_wale(p, reg, S) - 0.55)) * (1.0 - 0.35 * seam_stitch(p, reg, S))
        rough = R[0]
        fuzz = 0.45
        cls = 0.0
        wear = 0.0
    elif kd.k == K_FELT:
        cloud = S[19] * 3.0 * (0.6 * proc.fbm3(p / 0.02, 3, 2.0, 0.5, seed + 33) +
                               0.4 * proc.noise3(p / 0.006, seed + 39))
        col = C[1] * wp.exp(cloud + 0.5 * aol)
        rough = R[2]
        if reg == 2 and kd.sub == 2:
            # the wreath's BACKING (cap v6, the lead's decision 2): a darker VELVET patch, its albedo S[35] of the band's
            # (egmar3b: L* 44-46 beside the band's 48-49 beyond the leaves, 26 in the V over the cockade: v6_measure.py),
            # rougher and with less sheen than the felt (a cut pile drinks the light; the runtime's sheen off its edge),
            # its edge a crisp cut with a dark outline (WREATH_BACK_SHOULDER): v5's 0.74 under a rounded 0.8 mm shoulder
            # read as light as the band, its edge a LIGHT rim under the studio key (the v5 check)
            # cap v7 (the lead's decision 3): its edge ROLLS flush into the band (WREATH_BACK_ROLL), the roll darkened over
            # its width (S[38]: a cut pile's side drinks the light; the roll faces the key and would read as a light rim)
            col = col * S[35] * (1.0 - S[38] * (1.0 - proc.smoothstep(0.0, 0.0030, -kd.edge)))
            col = wp.vec3(col[0], col[1] * S[47], col[2] * S[47])      # cap v8: a richer crimson (decision 6)
            rough = S[37]
        # cap v6 (the lead's decision 6): no dust and no pills on the band (her cap is clean; v5 tinted 8 % of the band's
        # felt with dust at its foot, after ACCESSORY_REFERENCE §5's worn caps)
        fuzz = 0.70
        if reg == 2 and kd.sub == 2:
            fuzz = S[36]                       # the velvet backing's sheen, low (its edge catches no rim)
        cls = 1.0 / 3.0
        zone = 1.0 / 3.0
    elif kd.k == K_CORD:
        # cap v7 (the lead's decisions 4 and 5): gold bullion THREAD, matte (R[7] 0.46, rough at the macro scale), the
        # twist's valleys only a little darker (0.22 tv; v6's 0.55 tv and 0.30 roughness swung the cord's L* 13-19 along
        # it against her 5-9: polished metal), the fibres' crowns a touch glossier than their grooves (cord_fibre: fine
        # glints along the threads); the knots' strands the same thread
        # cap v8 (the lead's decision 2: "fine, matte, tightly twisted metallic thread ... no chunky white flecks on the
        # bumps (a rougher macro response with fine fibre glints)"): gold_rough 0.55 (v7 0.52), the twist's valleys
        # toned DEEP (0.65 tv) and rougher (+0.10 tv), so the lit stretch keeps its thread's swing and its median down
        # (the first v8 forges at 0.60 / 0.30 tv: its key side an even sheen, L* median 81 with a swing of 2.6 against
        # her 68 / 5-9), the fibres' crowns only a shade glossier than their grooves (+-0.02; v7's +-0.05 left each
        # ply's crest a chain of white flecks under the key)
        col = M.mix3(C[2], C[5], 0.65 * tv)
        rough = R[7] + 0.10 * tv
        if reg == 6:
            rough = rough - 0.04 * (cord_fibre(at, S, seed) - 0.5)
        patch = wp.clamp(0.5 + 0.6 * proc.fbm3(p / 0.004, 2, 2.0, 0.5, seed + 47), 0.0, 1.0)
        phb = wp.atan2(p[0] / S[6], p[2] / S[7])
        nb = wp.normalize(wp.vec3(wp.sin(phb) / S[6], 0.0, wp.cos(phb) / S[7]))
        if reg == 7:
            # the knot's crown, slid by fingers (cap v7: softer, the knot the same matte thread as the cords; v6 0.7)
            wear = 0.15 * proc.smoothstep(0.3, 0.8, wp.dot(n, nb)) * patch    # cap v8: matte as the cords (v7 0.35)
        if reg == 6:
            bc = G3[4]
            if p[0] < 0.0:
                bc = wp.vec3(-bc[0], bc[1], bc[2])
            wear = 0.5 * (1.0 - proc.smoothstep(0.009, 0.014, wp.length(p - bc))) * patch   # the loop on the button
        wear = wp.clamp(wear, 0.0, 1.0)
        col = M.mix3(col, C[13], 0.35 * wear)
        rough = rough - 0.12 * wear
        metal = 1.0
        zone = 2.0 / 3.0
        ao_floor = AO_FLOOR_GOLD
    elif kd.k == K_GILT:
        col = M.mix3(C[4], C[5], 0.4 * tv)
        rough = R[9] + 0.08 * tv
        if reg == 8:
            # grained ("gekoernt"): the grain as roughness at this density; the dome polished on its crown (§5.4)
            cl = proc.cellular3(p / S[20], 0.9, seed + 71)
            rough = rough + 0.14 * proc.smoothstep(0.0, 0.2, cl.edge)
            bn = G3[5]
            if p[0] < 0.0:
                bn = wp.vec3(-bn[0], bn[1], bn[2])
            wear = proc.smoothstep(0.85, 0.97, wp.dot(n, bn))
        if reg == 9:
            # the cockade's gilt: its high points (the rim's flat, the grains' crowns, the arms' tops) polished by
            # handling, its recesses toned; the stamped arms a shade satin; cap v5: the rye's fine grains and awns
            # (texture relief, ck_rye_h) bright on their crowns, toned between them (the close-up's dark gaps)
            wear = 0.45 * proc.smoothstep(0.72, 0.92, cav)
            if kd.sub == 2:
                # cap v8 (the lead's decision 5: "the hammer and compass bright, high-relief yellow gold"): the stamped
                # faces stand 0.60 mm over the enamel (CK_Z arms, v7 0.38), barely toned (0.06 tv) and rubbed bright,
                # their satin (gilt_rough + 0.06) taking the key and the softbox broadly: v7's polished faces (0.15)
                # mirrored the dim studio square-on and read flat and khaki
                col = M.mix3(C[4], C[5], 0.06 * tv)
                rough = R[9] + 0.06
                wear = wp.max(wear, 0.30)
            if kd.sub == 1:
                rr_ = wp.sqrt(kd.st * kd.st + kd.edge * kd.edge)
                th_ = wp.atan2(wp.abs(kd.st), kd.edge) * 57.29578
                if rr_ > 0.330 and rr_ < 0.468 and th_ < 112.0:       # the ears and awns (the ribbon's gilt lines below)
                    rh = ck_rye_h(kd.st, kd.edge)
                    col = M.mix3(col, C[5], 0.60 * (1.0 - rh))
                    wear = wp.max(wear, 0.5 * rh)
        if kd.sub >= 3:
            # the stamped wreath: cap v8 (the lead's decision 1) a SATIN stamped gilt (wreath_rough 0.40 and the die's
            # stipple, height_at: no glossy melted gold), toned in the recesses between the beads and under each upper
            # leaf's edge (0.25 tv), the beads' and the knobs' crowns rubbed a little brighter (wear on the cavity's
            # highs). v7: a smooth glossy gilt (0.26) whose pillows read as melted gold
            col = M.mix3(C[4], C[5], 0.25 * tv)
            rough = R[8] + 0.05 * tv
            wear = 0.25 * proc.smoothstep(0.78, 0.95, cav)
        col = M.mix3(col, C[13], 0.25 * wear)
        rough = rough - 0.10 * wear
        metal = 1.0
        zone = 2.0 / 3.0
        ao_floor = AO_FLOOR_GOLD
    elif kd.k == K_LACQUER:
        col = C[6]
        # micro-scratches (§5.1, by eye on o04): streaks 4 mm long, 0.08 mm across, wiped side to side
        q = wp.vec3(p[0] / 0.004, (0.6 * p[1] + 0.8 * p[2]) / 0.00008, 3.7)
        n1 = proc.noise3(q, seed + 91) + 0.5 * proc.noise3(q * 2.3, seed + 93)
        scr = proc.smoothstep(0.62, 0.95, wp.abs(n1)) * (0.5 + 0.5 * proc.noise3(p / 0.004, seed + 95))
        grip = float(0.0)
        if reg == 3:
            # the grip: a satin band along the front edge and the top's middle under the thumb (§5.1)
            g1 = proc.smoothstep(0.78, 0.95, at[1]) * (1.0 - proc.smoothstep(0.30, 0.55, wp.abs(at[0])))
            g2 = 0.7 * (1.0 - proc.smoothstep(0.12, 0.30, wp.abs(at[0]))) * proc.smoothstep(0.25, 0.40, at[1]) * \
                (1.0 - proc.smoothstep(0.62, 0.78, at[1]))
            grip = wp.max(g1, g2) * (0.55 + 0.45 * proc.fbm3(p / 0.006, 2, 2.0, 0.5, seed + 97))
        if reg == 5:
            # scuffs on the moulded rim, most at the front
            sc = proc.smoothstep(0.35, 0.75, proc.fbm3(p / 0.003, 3, 2.0, 0.5, seed + 99)) * \
                (1.0 - proc.smoothstep(0.4, 0.8, wp.abs(at[0])))
            grip = 0.6 * sc
            col = M.mix3(col, wp.vec3(0.035, 0.035, 0.036), 0.6 * sc)
        grip = wp.clamp(grip, 0.0, 1.0)
        rough = R[3] + (R[6] - R[3]) * grip + R[5] * scr
        wear = grip
        zone = 1.0
    elif kd.k == K_UNDER:
        col = C[6] * 1.25                     # the plain moulded underside (no GDR underside seen: no border)
        rough = R[4]
        zone = 1.0
    elif kd.k == K_ENAMEL:
        col = C[7]
        rough = R[10]
        if kd.sub == 0:
            # the translucent red over the pebbled gilt base: each bump's crown brighter through the enamel, the
            # hollows deep red (the close-up's 110-154 dark, 220-242 lit) [M CAP_GDR §6.9]
            col = C[7] * (0.62 + 0.76 * ck_pebble(kd.st, kd.edge, S[25]))
        if kd.sub == 1:
            col = C[8]
            rough = R[10] + 0.03
        if kd.sub == 2:
            col = C[9]
            rough = R[10] + 0.03
        if kd.sub == 3:
            col = C[3]
            rough = R[10] + 0.03
        col = col * (1.0 - 0.2 * (1.0 - proc.smoothstep(0.55, 0.85, cav)))
        zone = 2.0 / 3.0
    elif kd.k == K_LEATHER:
        cl = proc.cellular3(p / 0.0011, 0.9, seed + 51)
        g = proc.smoothstep(0.0, 0.18, cl.edge)
        col = C[10] * (0.90 + 0.10 * g) * wp.exp(aol) * (1.0 - 0.2 * (1.0 - proc.smoothstep(0.003, 0.012, p[1])))
        rough = R[11] + 0.06 * (g - 0.5)
        fuzz = 0.05
        cls = 2.0 / 3.0
    else:
        ink = float(0.0)
        if p[1] > S[2] + 0.012:
            # the maker's stamp on the lining's top: two ovals
            e = wp.sqrt((p[0] / 0.030) * (p[0] / 0.030) + (p[2] / 0.022) * (p[2] / 0.022))
            ink = wp.max(1.0 - proc.smoothstep(0.03, 0.06, wp.abs(e - 1.0)),
                         1.0 - proc.smoothstep(0.03, 0.06, wp.abs(e - 0.82)))
        col = M.mix3(C[11] * wp.exp(0.5 * aol), C[12], 0.9 * ink)
        rough = R[12]
        fuzz = 0.15
        cls = 2.0 / 3.0
    out = Finish()
    out.col = col
    out.rough = rough
    out.metal = metal
    out.fuzz = fuzz
    out.cls = cls
    out.zone = zone
    out.wear = wear
    out.ao_floor = ao_floor
    return out


@wp.kernel
def k_cap(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
          ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
          d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_cav: wp.array(dtype=wp.float32),
          d_aol: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4), C: wp.array(dtype=wp.vec3),
          R: wp.array(dtype=wp.float32), S: wp.array(dtype=wp.float32), G3: wp.array(dtype=wp.vec3),
          utab: wp.array(dtype=wp.float32), vtab: wp.array(dtype=wp.float32), LQ: wp.array(dtype=wp.vec2),
          LQI: wp.array(dtype=wp.vec2i), SP: wp.array(dtype=wp.vec3), SI: wp.array(dtype=wp.vec3i),
          AC: wp.array(dtype=wp.vec4), CKP: wp.array(dtype=wp.vec2), CKI: wp.array(dtype=wp.vec2i),
          RIB: wp.array(dtype=wp.vec4), BKP: wp.array(dtype=wp.vec2), texel: float,
          seed: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3),
          o_mask: wp.array(dtype=wp.vec4)):
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    base = d_base[tid]
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_m = float(0.0)
    acc_ao = float(0.0)
    acc_k = wp.vec4(0.0)
    hits = int(0)
    hb = float(0.0)
    have_hb = int(0)
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            # cap v7 (the lead's decision 6: "the black dashed line under the front piping (trace its cause first)"):
            # EACH sub-sample's offset to the bake's base point along its own normal (the base point's plane). v6 held
            # the texel's first sub-sample's offset for all 16: where the low is a chord across the crown piping's tube
            # (the 'po' -> 'pu' strip on its lower face, 28 deg off the tube at the strip's edges) it was off by up to
            # ~0.08 mm, the paint's 0.03 mm piping tolerance failed there, and those sub-samples painted wool, dark in
            # the crevice's occlusion: blocky grey bands in the strip's albedo (v6check/c_maps_piping.png), a dashed
            # dark line under the piping in the engine (v6check/c_redfleck2.png)
            if have_hb == 0:
                have_hb = 1
            if base[3] > 0.5:
                hb = wp.dot(wp.vec3(base[0], base[1], base[2]) - lo.p, lo.n)
            reg = lreg[lo.face]
            pb0 = lo.p + lo.n * hb
            kd = classify(pb0, reg, S, G3, utab, LQ, LQI, SP, SI, AC, CKP, CKI, RIB, BKP)
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            nw = M.to_world(lo, tn_b)
            # cap v7 (the lead's decision 6, the defects at the crown piping traced to one cause): where the low's
            # chords cross the piping's tube (the 'po' -> 'pu' strip, up to 0.25 mm inside it), the bake's ray finds
            # the high unreliably (its low-to-high distance swings 0.3 mm along the rim within one texel column, the
            # first v7 forge's drivers): its base point, normal and occlusion band row by row, and the paint's piping
            # test (on that base point) failed in the same bands: grey-red combs along the piping (the dashed dark line
            # under it, the smear on the right tip, the notch at the front centre). The piping is an analytic tube
            # with no sculpt on it: a sub-sample whose LOW point lies inside the tube is piping, and every piping
            # sub-sample takes the tube's own normal (from its nearest centreline point), not the bake's
            if reg == 0 or reg == 1:
                Ec = crown_pipe_near(lo.p, S)
                dlo = wp.length(lo.p - Ec)
                if kd.k == K_WOOL and dlo < S[5] - 0.00002:
                    kd.k = K_FELT
                    kd.sub = 1
                if kd.k == K_FELT and kd.sub == 1 and dlo > 1.0e-6:
                    # the tube's normal where the low's normal ray meets its surface (the bake's own construction:
                    # inside the tube its exit, ahead; outside its entry, if ahead). The radial direction at the low
                    # point itself turned past 90 deg off the low's face where a chord crosses the tube's far side:
                    # 450 texels at 29 deg round the front shaded black (the fourth v7 forge; the engine's close
                    # crown station s22, t27_whole's three-quarter)
                    pdv = lo.p - Ec
                    pbq = wp.dot(pdv, lo.n)
                    pcq = wp.dot(pdv, pdv) - S[5] * S[5]
                    pdisc = pbq * pbq - pcq
                    hit_t = int(0)
                    if pdisc >= 0.0:
                        ptq = -pbq + wp.sqrt(pdisc)
                        if pcq > 0.0:
                            ptq = -pbq - wp.sqrt(pdisc)
                        if ptq >= 0.0:
                            nw = wp.normalize(lo.p + lo.n * ptq - Ec)
                            hit_t = 1
                    if hit_t == 0:
                        # cap v8 (the lead's decision 4: "the dent at about 29 deg ... traced to its cause"): where the
                        # low's normal ray misses the tube (a chord ABOVE the tube's far side: the low outside it, the
                        # tube behind), the tube's radial normal at the bake's own hit point (on the tube's surface);
                        # v7 kept the bake's normal there, bent by the chord: the dent and its dark crease at ~29 deg
                        Eb = crown_pipe_near(pb0, S)
                        db = pb0 - Eb
                        if wp.abs(wp.length(db) - S[5]) < 0.00015 and wp.dot(db, lo.n) > 0.0:
                            nw = wp.normalize(db)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                tex = wp.max(wp.length(lx.p - lo.p) / dlt, 1.0e-6)        # THIS island's texel (its share)
                hbx = hb
                hby = hb
                if base[3] > 0.5:
                    hbx = wp.dot(wp.vec3(base[0], base[1], base[2]) - lx.p, lx.n)
                    hby = wp.dot(wp.vec3(base[0], base[1], base[2]) - ly.p, ly.n)
                pbx = lx.p + lx.n * hbx
                pby = ly.p + ly.n * hby
                h0 = height_at(pb0, kd, reg, lo.attr, tex, S, G3, utab, vtab, RIB, CKP, CKI, seed)
                hx = height_at(pbx, kd, reg, lx.attr, tex, S, G3, utab, vtab, RIB, CKP, CKI, seed)
                hy = height_at(pby, kd, reg, ly.attr, tex, S, G3, utab, vtab, RIB, CKP, CKI, seed)
                g = M.surface_grad(pb0, pbx, pby, h0, hx, hy)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            f = paint(kd, pb0, nw, reg, lo.attr, d_aol[tid], d_cav[tid], C, R, S, G3, vtab, seed)
            acc_a = acc_a + f.col
            acc_r = acc_r + wp.clamp(f.rough, 0.03, 1.0)
            acc_m = acc_m + f.metal
            acc_ao = acc_ao + wp.max(d_ao[tid], f.ao_floor)
            acc_k = acc_k + wp.vec4(f.fuzz, f.cls, f.zone, f.wear)
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    # Toksvig (craft guide 00.48, 11.44): the averaged normal's lost length widens the highlight
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    # the gold's occlusion floor holds for the TEXEL too: a texel half gold or more (ORM B reads gold) never darker than
    # AO_FLOOR_GOLD (the sub-samples' floors alone averaged the gold's edge texels with the felt's crevice, 0.25)
    mf = acc_m / fh
    o_orm[tid] = wp.vec3(wp.max(acc_ao / fh, AO_FLOOR_GOLD * proc.smoothstep(0.30, 0.50, mf)), wp.clamp(rr, 0.0, 1.0),
                         mf)
    o_mask[tid] = acc_k / fh


def material_tables(spec=SPEC, backing=True):
    """the material pass's geometry, from the same functions the block-out and the plan use: the band's arc table,
    the visor's depth table, the wreath's leaves (band coordinates, top first), its stalks and acorn circles, its
    BACKING's outline (cap v5: BKP, band coordinates; backing=False leaves it out, for wreath_backing itself), the
    cockade's face (its arms' polygons, its ribbon's parts: D units) and frame, the left button's frame"""
    utab = phi_to_u(np.linspace(-np.pi, np.pi, 4097), spec)
    vtab = visor_L(np.linspace(-1.0, 1.0, 129), spec)
    # cap v8: the traced leaves' visible outlines (top layer first), concatenated with each one's (start, count)
    leaves = leaf_instances(spec)
    LQ = np.concatenate([lf['poly'] for lf in leaves])
    LQI = np.array([[sum(len(o['poly']) for o in leaves[:k]), len(leaves[k]['poly'])] for k in range(len(leaves))],
                   np.int32)
    SP, SI = [], []
    wl = wreath_layout(spec)
    st = _catmull(wl['stem'], 80)
    for side in (1, -1):
        SI.append([sum(len(x) for x in SP), len(st), 1])
        SP.append(np.column_stack([st[:, 0] * side, st[:, 1], np.zeros(len(st))]))
    # the acorn knobs as plan_cap strokes them, as circles in band coordinates; tested BEFORE the leaves they lie on
    # (wreath_at)
    AC = [[c_[0], c_[1], r_, 0.0] for c_, r_ in acorn_parts(spec)]
    polys = ck_polys()
    CKP = np.concatenate(polys)
    CKI = np.array([[sum(len(p) for p in polys[:k]), len(polys[k])] for k in range(len(polys))], np.int32)
    RIB = np.array([v_ for (a_, e0, e1) in CK_RIBBON_PARTS for v_ in (a_[:4], (a_[4], 0.0, 0.0, 0.0), e0, e1)])
    cc, cn = cockade_frame(spec)
    e1 = np.array([1.0, 0.0, 0.0])                       # the viewer's right, looking at the cap's front
    bc, bn = button_frame(spec, 1)
    out = dict(utab=utab, vtab=vtab, LQ=LQ, LQI=LQI, SP=np.concatenate(SP),
               SI=np.array(SI, np.int32), AC=np.array(AC), CKP=CKP, CKI=CKI, RIB=RIB, stalk_r=0.0007,
               G3=np.array([cc, cn, e1, np.cross(cn, e1), bc, bn]), n_leaves=len(leaves))
    if backing:
        out['BKP'] = wreath_backing(spec)['poly']
    return out


# egmar3b's wreath: GOLD over 63.1 % of its box, the cockade and the cords out (CAP_GDR §5; the gold mask hue 18-70 deg,
# value > 0.40) [M]
WREATH_PHOTO = dict(egmar3b_box=0.631)


def wreath_cover(spec=SPEC, g=0.0001):
    """the wreath's GOLD COVER from the layout the paint and the sculpt share (material_tables: the leaves, stalks and
    acorns; wreath_at's test in numpy, no reach margin) in band coordinates: its box over the band above the cords'
    top, the cockade's disc out (WREATH_PHOTO's box, read on the band; t27 also measures it through the camera fitted
    to egmar3b on the SHIPPED maps); the leaves' overlap (the share of the gold two deep), their count a side, the gap
    between the inner leaves and the cockade's rim, the box in mm and in cockade diameters"""
    T = material_tables(spec)
    SP, SI = T['SP'], T['SI']
    lay = cord_layout(spec)
    y_ct = lay['yb'] + 2.0 * lay['r']                    # the cords' top at the front
    uu, yy = np.meshgrid(np.arange(-0.075, 0.075, g) + 0.5 * g, np.arange(y_ct, spec['band_h'], g) + 0.5 * g)
    X = np.column_stack([uu.ravel(), yy.ravel(), np.zeros(uu.size)])
    # cap v8: the traced leaves' visible outlines (they tile her gold; the overlap share counts where two meet within a
    # cell), rasterised on this grid
    from skimage.draw import polygon as fill_poly
    cnt = np.zeros(uu.shape, int)
    for lf in leaf_instances(spec):
        m = np.zeros(uu.shape, bool)
        rr, cc = fill_poly((lf['poly'][:, 1] - yy[0, 0]) / g, (lf['poly'][:, 0] - uu[0, 0]) / g, uu.shape)
        m[rr, cc] = True
        cnt += m.astype(int)
    cnt = cnt.ravel()
    # the scarlet ring round the cockade (WREATH_RING): no leaf there, as in the relief and the paint
    cnt[np.hypot(X[:, 0], X[:, 1] - spec['cockade_y']) < 0.5 * spec['cockade_d'] + WREATH_RING] = 0
    hit = cnt > 0
    for c in T['AC']:
        hit |= (X[:, 0] - c[0]) ** 2 + (X[:, 1] - c[1]) ** 2 < c[2] ** 2
    for s0, n, _ in SI:
        P = SP[s0:s0 + n]
        for j in range(n - 1):
            a, ab = P[j], P[j + 1] - P[j]
            t = np.clip(((X - a) @ ab) / max(ab @ ab, 1e-20), 0, 1)
            hit |= np.linalg.norm(X - (a + t[:, None] * ab), axis=1) < T['stalk_r']
    U, Y = X[hit, 0], X[hit, 1]
    box = (U.min(), U.max(), Y.min(), Y.max())
    R = 0.5 * spec['cockade_d']
    cock = (X[:, 0] ** 2 + (X[:, 1] - spec['cockade_y']) ** 2) < R ** 2
    inb = (X[:, 0] >= box[0]) & (X[:, 0] <= box[1]) & (X[:, 1] >= box[2]) & (X[:, 1] <= box[3]) & ~cock
    lp = X[cnt >= 1]
    D = spec['cockade_d']
    return dict(box_mm=[round((box[1] - box[0]) * 1e3, 1), round((box[3] - box[2]) * 1e3, 1), round(box[2] * 1e3, 1),
                        round(box[3] * 1e3, 1)],
                box_D=[round((box[1] - box[0]) / D, 2), round((box[3] - box[2]) / D, 2)],
                egmar3b_box=float(hit[inb].mean()), overlap_share=float((cnt >= 2).sum() / max((cnt >= 1).sum(), 1)),
                leaves_a_side=len(T['LQI']) // 2,
                gap_to_cockade_mm=round(float((np.sqrt(lp[:, 0] ** 2 + (lp[:, 1] - spec['cockade_y']) ** 2) - R).min())
                                        * 1e3, 2),
                top_below_seam_mm=round((spec['band_h'] - box[3]) * 1e3, 1))


def run_material(L, drivers, size, texel, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the cap's texture set. L: low_arrays(); drivers: the bake's result (image order).
    Returns image-order uint8 maps: albedo (sRGB), normal (GL), orm (AO, roughness, metalness), masks (R fuzz / sheen,
    G material class, B palette zone, A handling wear), palette_base (each zone's median linear albedo, for the
    runtime's recolour) and the coverage"""
    import time
    from .. import calib
    from ..bake import dilate_all
    t0 = time.time()
    d = dims(spec)
    T = material_tables(spec)
    sel = L['bake']                                    # the unique copies the bake saw (the stacked twins share them)
    uvm = M.uv_bvh(L['F'][sel], L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], L['F'][sel], L['N'], L['TAN'], L['ATTR'])
    D = M.driver_arrays({**drivers, **calib.relief_drivers(drivers, 1.0 / texel, ao_sigma_mm=3.0, fine_sigma_mm=0.3,
                                                           mid_sigma_mm=1.5)})
    r = recipe
    C = wp.array(np.array([r['wool'], r['felt'], r['cord_gold'], r['ribbon_yellow'], r['gilt'], r['tarnish'],
                           r['lacquer'], r['enamel'], r['ribbon_black'], r['ribbon_red'], r['leather'], r['linen'],
                           r['ink'], r['worn'], r['dust']], np.float32), dtype=wp.vec3)
    R = wp.array(np.array([r['wool_rough'], r['shine_rough'], r['felt_rough'], r['lacquer_rough'], r['under_rough'],
                           r['scratch_rough'], r['grip_rough'], r['gold_rough'], r['wreath_rough'], r['gilt_rough'],
                           r['enamel_rough'], r['leather_rough'], r['linen_rough']], np.float32), dtype=wp.float32)
    # S: the crown and band (0-8), the cockade's diameter, its red disc's centre (u, v) and radius (D), the wreath's
    # stalks' radius, the cloth's numbers (14-16, 19, 20), the rye field's rings (17, 18), the veins' relief (21), the
    # hinge boss (22-24), the pebbles' spacing (25, D)
    S = np.zeros(56, np.float32)
    S[:9] = [d['Rx'], d['Rz'], spec['band_h'], spec['rise_side'], spec['rise_front'], d['rp'], d['rx_b'], d['rz_b'],
             spec['sweat_h']]
    # cap v8 (the lead's decision 5: "the hairline arc on the disc's lower-right rim removed"): the painted red disc
    # CONCENTRIC with the sculpt's (cockade_profile revolves its lip and the step down onto the enamel about the face's
    # centre); painted about CK_DISC_C (its measured 0.15 mm offset to the lower right), the red ran 0.2 mm up the step
    # and onto the lip on the lower right, a hairline arc in the glossy enamel
    S[9:14] = [spec['cockade_d'], 0.0, 0.0, T['stalk_r'], CK_RINGS['disc']]
    S[14:22] = [r['twill'], r['twill_amp'], r['felt_amp'], CK_RINGS['ears_in'], CK_RINGS['rim_in'], r['cloud'],
                r['grain'], r['vein_amp']]
    S[22:26] = [CK_HINGE[0], CK_HINGE[1], CK_HINGE[2], 0.029]
    S[26:29] = [spec.get('rise_round', 0.0), spec.get('rise_back', spec['rise_side']), d['rpb']]
    # cap v6: the twill's visible grain (29-31), the band's raised seam (32-34), the velvet backing (35-37)
    S[29:32] = [r['twill_grain'], r['twill_grain_amp'], r['twill_grain_col']]
    S[32:35] = [spec.get('seam_rise', 0.0), spec.get('seam_flat', 0.01), spec.get('seam_edge', 0.02)]
    S[35:38] = [r['velvet'], r['velvet_fuzz'], r['velvet_rough']]
    # cap v7: the backing's rolled edge (38), the cords' fibres (39-41, 45 the cord's radius), the pebbles' relief (42)
    S[38] = r['velvet_edge']
    S[39:42] = [r['cord_fibre_amp'], r['cord_fibres'], np.radians(r['cord_fibre_deg'])]
    S[42] = r['pebble_amp']
    S[45] = 0.5 * spec['cord_d']
    S[46] = r['leaf_stipple']                            # cap v8: the wreath's satin stipple
    S[43:45] = [r['twill_col'], r['stitch_off']]         # cap v8: the twill's tone, the seams' topstitch offset
    S[47] = r['velvet_gb']                               # cap v8: the velvet's richer crimson
    arr = lambda a, t: wp.array(np.asarray(a, np.float32), dtype=t)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask = wp.zeros(n, dtype=wp.vec4)
    wp.launch(k_cap, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                    wp.array(np.asarray(L['region'][sel], np.int32), dtype=wp.int32), D['normal'],
                                    D['ao'],
                                    D['cavity'], D['ao_local'], D['base'], C, R, arr(S, wp.float32),
                                    arr(T['G3'], wp.vec3), arr(T['utab'], wp.float32), arr(T['vtab'], wp.float32),
                                    arr(T['LQ'], wp.vec2), wp.array(T['LQI'], dtype=wp.vec2i), arr(T['SP'], wp.vec3),
                                    wp.array(T['SI'], dtype=wp.vec3i), arr(T['AC'], wp.vec4), arr(T['CKP'], wp.vec2),
                                    wp.array(T['CKI'], dtype=wp.vec2i), arr(T['RIB'], wp.vec4),
                                    arr(T['BKP'], wp.vec2), float(texel), int(r['seed']), o_alb, o_nrm, o_orm, o_mask])
    wp.synchronize()
    cov = np.asarray(drivers['normal'])[..., 3] > 0
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    alb, nrm, orm, msk = img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4)
    zone = np.rint(msk[..., 2] * 3.0).astype(int)
    pal = {}
    for zi, nm in enumerate(PALETTE):
        s_ = cov & (zone == zi)
        if s_.sum() > 16:
            pal[nm] = [float(x) for x in np.median(alb[s_], axis=0)]
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb,
                                 orm=orm, msk=msk), 16)
    alb_s = M.srgb_oetf(np.where(grown[..., None], dil['alb'], 0.05))
    nrm_t = np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0])
    out = dict(albedo=(alb_s * 255 + 0.5).astype(np.uint8),
               normal=np.clip((nrm_t * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8),
               orm=np.clip(np.where(grown[..., None], dil['orm'], [1.0, 0.8, 0.0]) * 255 + 0.5, 0, 255).astype(np.uint8),
               masks=np.clip(np.where(grown[..., None], dil['msk'], 0.0) * 255 + 0.5, 0, 255).astype(np.uint8),
               palette_base=pal, coverage=float(cov.mean()), linear=dict(albedo=alb, orm=orm, masks=msk, cov=cov))
    log(f'[peaked_cap] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s ({T["n_leaves"]} wreath leaves, {len(T["SI"])} '
        f'stalks, {len(T["AC"])} acorn circles, the backing\'s {len(T["BKP"])}-point outline, the cockade\'s '
        f'{len(T["CKI"])} arms polygons and {len(T["RIB"]) // 4} ribbon parts); coverage {cov.mean() * 100:.1f} %; '
        f'palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in pal.items()))
    return out


# ------------------------------------------------------------------------------------------------------ fit data
def fit_data(spec=SPEC, n_probe=32):
    """what forge/fit.py's fit_hat and the runtime's hat fit (accessories.js wear, hatPlacement) need from the cap,
    prop space (metres; top_hat.fit_data's contract): the seat frame, the head opening (its semi-axes on the seat
    plane), the crown's inner ceiling, the crown's, band's and visor's extents, and clearance PROBES: 'opening' (the
    band's inner rim on the seat plane: it rests on the wearer), 'brim_under' (everything that hangs over the wearer
    and must clear its skin: the visor's underside, the crown's overhang, the cords' lowest line), and
    ACCESSORY_REFERENCE §3's 'peak_under' (the visor's underside alone) and 'peak_rear' (where it leaves the band)"""
    d = dims(spec)
    ph = np.linspace(0.0, 2.0 * np.pi, n_probe, endpoint=False)
    opening = np.column_stack([d['rx_o'] * np.sin(ph), np.zeros_like(ph), d['rz_o'] * np.cos(ph)])
    Sg, Tg = np.meshgrid(np.linspace(-0.95, 0.95, 19), np.array([0.1, 0.4, 0.7, 0.97]), indexing='ij')
    XI = visor_L(Sg, spec) * Tg
    under = (visor_mid(Sg, XI, spec) - visor_half(Sg, XI, spec)[..., None] * visor_normal(Sg, XI, spec)).reshape(-1, 3)
    rear = visor_top(np.linspace(-1.0, 1.0, 17), np.zeros(17), spec)[0]
    tw = np.array([0.3, 0.6, 0.9])[:, None]
    wall = (wall_point(tw, ph[None, :], spec) + 0.5 * spec['cloth_t'] * wall_normal(tw, ph[None, :], spec))
    paths, _ = cord_paths(spec)
    cords = [P[::30] - np.array([0.0, 0.5 * spec['cord_d'], 0.0]) for P, _ in paths.values()]
    brim_under = np.concatenate([under, wall.reshape(-1, 3)] + cords)
    rr, pp = np.meshgrid(np.linspace(0.0, 0.75, 16), ph, indexing='ij')
    ceiling = float((top_height(rr, pp, spec) - 0.5 * spec['cloth_t']).min())
    tip = visor_mid(0.0, spec['visor_d'], spec)
    rnd = lambda a: np.round(np.asarray(a, np.float64), 5).tolist()
    # cap v6: the crown's outer extent the roll's (or the piping's, where the roll stands inside it at the front)
    T = crown_rim(spec)
    i_s = int(np.argmin(np.abs(T['ph'] - 0.5 * np.pi)))
    i_f = int(np.argmin(np.abs(T['ph'])))
    out_s = max(T['dx'][i_s] + T['rho'][i_s], d['rp'])
    out_f = max(T['dx'][i_f] + T['rho'][i_f], d['rp'])
    return dict(archetype='hat', prop='peaked_cap',
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                # the cap keeps its proportions (cap v2): the runtime clamps its per-axis seat scale to this ratio
                # (each axis within 3 % of their geometric mean), not the top hat's 1.25
                max_aniso=round(((1.0 + FIT_ANISO) / (1.0 - FIT_ANISO)), 4),
                opening=dict(rx=round(d['rx_o'], 5), rz=round(d['rz_o'], 5), y=0.0, circumference=spec['head_circ']),
                crown_inner_height=round(ceiling, 5),
                crown_outer=dict(rx=round(d['Rx'] + out_s, 5), rz=round(d['Rz'] + out_f, 5),
                                 height_front=round(spec['band_h'] + spec['rise_front'] + T['H'][i_f], 5),
                                 height_side=round(spec['band_h'] + spec['rise_side'] + T['H'][i_s], 5)),
                band=dict(height=spec['band_h'], rx=round(d['rx_b'], 5), rz=round(d['rz_b'], 5)),
                visor=dict(width=spec['visor_w'], depth=spec['visor_d'], tip=rnd(tip), droop_deg=list(spec['droop']),
                           y_min=round(float(under[:, 1].min()), 5)),
                probes=dict(brim_under=rnd(brim_under), opening=rnd(opening), peak_under=rnd(under),
                            peak_rear=rnd(rear)))


@wp.kernel
def k_near(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=float)):
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, pts[i], maxd)
    out[i] = maxd
    if q.result:
        out[i] = wp.length(pts[i] - wp.mesh_eval_position(mesh, q.face, q.u, q.v))


def _bvh(V, F):
    return wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3),
                   indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32))


def _near(mesh, P, maxd=0.2):
    out = wp.zeros(len(P), dtype=float)
    wp.launch(k_near, dim=len(P), inputs=[mesh.id, wp.array(np.asarray(P, np.float32), dtype=wp.vec3), maxd, out])
    return out.numpy().astype(np.float64)


class MeshGap:
    """validate_fit's `avoid` for a mesh (Vm, Fm) in creature space (the posed glasses, the eyeballs): called f(the
    placed cap's vertices, its triangles) -> the least distance between the two, both ways (the cap's vertices to the
    mesh, the mesh's vertices to the cap); .points(W) -> each point's distance to the mesh (one way: the pose search's
    rest scan)"""

    def __init__(self, Vm, Fm):
        self.Vm = np.asarray(Vm, np.float64)
        self.mesh = _bvh(self.Vm, Fm)

    def points(self, W):
        return _near(self.mesh, np.asarray(W, np.float64).reshape(-1, 3))

    def __call__(self, Vw, Fc):
        return min(float(_near(self.mesh, Vw).min()), float(_near(_bvh(Vw, Fc), self.Vm).min()))


def mesh_gap(Vm, Fm):
    return MeshGap(Vm, Fm)


def pose_matrix(origin, R, translation, scale, tilt_deg=0.0):
    """prop -> creature (4 x 4) as the runtime places a hat (accessories.js wear, the staged patch): the seat frame, the
    prop's origin at `translation` (the seat's frame), turned back by tilt_deg about the seat's x (rotateX(-tilt): +
    leans back), scaled per axis"""
    t = np.radians(tilt_deg)
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, np.cos(t), np.sin(t)], [0.0, -np.sin(t), np.cos(t)]])
    M = np.eye(4)
    M[:3, :3] = np.asarray(R, np.float64) @ Rx @ np.diag(np.asarray(scale, np.float64))
    M[:3, 3] = np.asarray(origin, np.float64) + np.asarray(R, np.float64) @ np.asarray(translation, np.float64)
    return M


def placement(table, opening, origin, R, depth, tilt_deg=0.0, lift=0.0):
    """the runtime's table placement (forges 1-6's fit: the table's per-axis scale at `depth`, its translation plus
    `lift`, then the tilt). Returns (fit.hat_placement's dict, prop -> creature 4 x 4)"""
    from .. import fit as FIT
    pl = FIT.hat_placement(table, opening, depth=depth)
    return pl, pose_matrix(origin, R, np.asarray(pl['translation']) + np.array([0.0, lift, 0.0]), pl['scale'], tilt_deg)


FIT_ANISO = 0.029           # (a) the cap KEEPS ITS PROPORTIONS: each axis's scale within 3 % of their geometric mean
GIVE_MAX = 0.008            # cap v3 (the lead's decision 1, NO STRETCH): the band's GIVE, its lower edge in or out along
                            # the band's HORIZONTAL normal, at most this in the CAP'S OWN units, fading up the band to
                            # nothing at its top seam. v2's conform morph reached 8 mm on the WORN cap toward the skin's
                            # nearest point: 16 mm in the cap's units and mostly vertical, a STRETCH (the band +30 % tall,
                            # the cockade a 20 x 27 mm egg, the visor squeezed; check 10-22)
GIVE_FADE = np.radians(15.0)  # the band's front (the visor's root sewn on its stiffener) gives nothing; the give fades in
                            # over this past the visor's ends (the knots and the buttons ride the fade)
CONTACT_GAP = 0.002         # (decision 2, the seat is a SUPPORT) a CONTACT: a rim station, or the visor's underside on
                            # the forehead, within this of the skin (worn, m)
CONFORM_GAP = 0.0003        #     the give's target gap off the skin (worn)
REST_GAP = 0.0002           #     nothing nearer the skin than this (worn): the visor may REST on the forehead
CONTACT_SHARE = 0.85        # v2's (b), now only reported (decision 2 replaced it: unreachable on the octopus unstretched)
VISOR_PITCH = (39.4, 47.5)  # the reference caps' VISOR PITCH, the centre spoke's chord below the band's foot plane (deg)
                            # [CAP_REFERENCE §3.12, cap v3: the VP general's cap standing 13.5 cm on band back and visor tip
                            # [C] through this crown is 39.4; o01's front silhouette, a GDR cap of this construction seen
                            # from the front-left at band height, droops at least 47.5 [M]]: the hinge's range
HINGE_W = 0.010             # the visor's HINGE zone along each spoke from its root (cap units): the plate beyond it turns
                            # rigidly, the zone bends ("a real visor bends at its root")
DAYLIGHT_TOL = 0.25         # when no supported pose is daylight-free: the poses within this share of the least daylight
                            # compete on the tilt (the least), the front read, the contact share and the size
STANDARD_VIEWS = ((0.0, 0.42, 0.012), (40.0, 0.42, 0.012), (90.0, 0.42, 0.010), (145.0, 0.42, 0.012),
                  (35.0, 0.22, 0.006), (180.0, 0.42, 0.012))   # the five standard engine views (scene_cap_v2.js) and
                            # cap v5's DEAD BACK (the lead's decision 8): azimuth from the cap's front (deg, + toward the
                            # wearer's left), distance from its centre (m), the camera's height over the cap's origin (m);
                            # the daylight check looks from each
EYE_VIEWS_AZ = (0.0, 40.0, -40.0)   # cap v8 (the lead's decision 7): the perched fit's bar, daylight from the eyes'
                            # height dead front and at the two three-quarters (measure_pose; decision 9's rim-contact
                            # gates retired: no pose on the octopus meets them at the worn size, CAP_GDR §13)
DEAD_VIEWS = (0, 5)         # cap v5 (decision 8, a PERCHED cap accepted): the views whose daylight is GATED (none from dead
                            # front, none from dead back); the others' (the sides') reported, not gated
BACK_ARC = np.radians(45.0)  # a BACK contact: a rim station within CONTACT_GAP of the skin within this of the back
# cap v7 (the lead's decision 9): the FIT's gates once the band gives in as well as out: its foot within CONTACT_GAP of
# the skin over at least FIT_SHARE of the rim, no point of it more than FIT_GAP off (worn), and no daylight within 10 deg
# of dead front and dead back (NEAR_DEAD_VIEWS: 0, +-5, +-10 and 180, 180 +-5, 180 +-10 deg, at the band's foot (3 mm
# over the cap's origin) and at the standard height (12 mm); the v6 check found 19-24 rays 5 deg off dead back and 12 at
# +-10 deg off dead front, where the two dead views alone read 0), and no cap vertex inside the head
FIT_SHARE = 0.50
FIT_GAP = 0.005
NEAR_DEAD_VIEWS = tuple((float(a), 0.42, h) for h in (0.003, 0.012)
                        for a in (0.0, -5.0, 5.0, -10.0, 10.0, 180.0, 175.0, 185.0, 170.0, 190.0))


def gate_fit(r):
    """cap v7's fit gate (decision 9) on a pose's row: the share of the rim within CONTACT_GAP, its largest gap, the
    daylight from NEAR_DEAD_VIEWS (r['daylight_near'], cast for the leaders), nothing inside the head; and the shortfall
    (0 when met) the choice ranks by when no pose meets it"""
    dn = r.get('daylight_near')
    short = (max(0.0, FIT_SHARE - r['contact_share']) / FIT_SHARE + max(0.0, r['largest_gap'] - FIT_GAP) / FIT_GAP +
             (0.02 * sum(dn) if dn is not None else 9.0) + max(0.0, -min(r['band_min'], r['others_min'])) / 0.001)
    return short <= 1e-9, short


def rim_probes(spec=SPEC, n=96):
    """the band's lower rim, where it sits on a head (its inner face on the seat plane), at n stations of equal arc
    length; the band's outward normals there and the stations' azimuths (prop space)"""
    d = dims(spec)
    ph = np.linspace(-np.pi, np.pi, 4001)
    x, z = d['rx_o'] * np.sin(ph), d['rz_o'] * np.cos(ph)
    a = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(z)))])
    phs = np.interp(np.linspace(0.0, a[-1], n, endpoint=False), a, ph)
    P = np.column_stack([d['rx_o'] * np.sin(phs), np.zeros(n), d['rz_o'] * np.cos(phs)])
    nx, nz = np.sin(phs) / d['rx_o'], np.cos(phs) / d['rz_o']
    ln = np.hypot(nx, nz)
    return P, np.column_stack([nx / ln, np.zeros(n), nz / ln]), phs


def visor_pitch(spec=SPEC):
    """the visor's PITCH: its centre spoke's chord, root to tip, below the band's foot plane (deg)"""
    return float(np.degrees(np.arctan2(float(visor_drop(spec['visor_d'], spec)), spec['visor_d'])))


def hinge_range(spec=SPEC):
    """the HINGE's range (deg, + droops the visor further, - lifts it): the reference caps' measured pitch range
    (VISOR_PITCH) less the forged visor's own pitch (a rigid turn about the hinge turns the chord by its angle)"""
    p = visor_pitch(spec)
    return VISOR_PITCH[0] - p, VISOR_PITCH[1] - p


_HAX = {}


def hinge_axis(spec=SPEC):
    """the visor's HINGE: an x-parallel axis through the middle of the hinge zone's outer edge (the curve HINGE_W out
    along every spoke longer than that; the (y, z) centroid of its points by arc length). The root is curved (the band's
    front arc, 42 mm deep from its ends to its centre), so no straight axis lies on it: the rigid plate turns about this
    one and the zone between it and the root, which stays on the band, bends least"""
    key = (spec['visor_w'], spec['visor_d'], tuple(spec['droop']), spec['head_circ'], spec['visor_end_z'])
    if key not in _HAX:
        s = visor_s_arc(801, spec)
        ok = visor_L(s, spec) > HINGE_W
        P = visor_mid(s[ok], np.full(int(ok.sum()), HINGE_W), spec)
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        w = np.concatenate([[0.0], seg]) + np.concatenate([seg, [0.0]])
        _HAX[key] = (float(np.average(P[:, 1], weights=w)), float(np.average(P[:, 2], weights=w)))
    return _HAX[key]


def hinge_disp(P, xi, hinge_deg, spec=SPEC):
    """the visor's points P (cap space; xi their plan distances from the band's face along their spokes) pitched by the
    HINGE (deg, + droops): beyond HINGE_W the plate turns RIGIDLY about hinge_axis; the zone blends from its root
    (unmoved, on the band) by smoothstep(0, HINGE_W, xi). Returns the displacements"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    th = np.radians(hinge_deg)
    yA, zA = hinge_axis(spec)
    dy, dz = P[:, 1] - yA, P[:, 2] - zA
    b = _smoothstep(0.0, HINGE_W, np.asarray(xi, np.float64))
    D = np.zeros_like(P)
    D[:, 1] = b * (dy * np.cos(th) - dz * np.sin(th) - dy)
    D[:, 2] = b * (dy * np.sin(th) + dz * np.cos(th) - dz)
    return D


_VXI = {}


def visor_xi(P, spec=SPEC):
    """the plan distance xi (from the band's face along its spoke) of the visor's mid-surface point nearest each P (a
    dense (s, xi) table): the hinge's blend for a visor vertex, and where a cord section rests on the visor's root"""
    from scipy.spatial import cKDTree
    key = tuple(sorted((k, str(v)) for k, v in spec.items()))
    if key not in _VXI:
        s = np.linspace(-1.0, 1.0, 321)
        tt = np.linspace(0.0, 1.0, 161)
        S, Tt = np.meshgrid(s, tt, indexing='ij')
        XI = -spec['visor_root'] + (visor_L(S, spec) + spec['visor_root']) * Tt
        _VXI[key] = (cKDTree(visor_mid(S, XI, spec).reshape(-1, 3)), XI.ravel())
    tree, xi = _VXI[key]
    return xi[tree.query(np.asarray(P, np.float64).reshape(-1, 3))[1]]


def give_mask(phi, spec=SPEC):
    """the share of GIVE_MAX a rim station at azimuth phi may take: 0 over the visor's root (the band's front, held by
    the visor and its stiffener), 1 from GIVE_FADE past the visor's ends"""
    pe = dims(spec)['phi_e']
    return _smoothstep(pe, pe + GIVE_FADE, np.abs(np.angle(np.exp(1j * np.asarray(phi, np.float64)))))


def give_at(phi, g, phs):
    """the give (cap units, + out) at azimuths phi: the stations' gives g at their azimuths phs, periodic, linear"""
    o = np.argsort(phs)
    pp, gg = np.asarray(phs, np.float64)[o], np.asarray(g, np.float64)[o]
    xp = np.concatenate([pp - 2.0 * np.pi, pp, pp + 2.0 * np.pi])
    return np.interp(np.angle(np.exp(1j * np.asarray(phi, np.float64))), xp, np.concatenate([gg] * 3))


def band_normal(phi, spec=SPEC):
    return band_frame(phi, 0.0, 0.0, spec)[1]


def band_phi(P, spec=SPEC):
    """the band's azimuth of points (cap space)"""
    d = dims(spec)
    P = np.asarray(P, np.float64).reshape(-1, 3)
    return np.arctan2(P[:, 0] / d['rx_b'], P[:, 2] / d['rz_b'])


def give_disp(P, g, phs, spec=SPEC):
    """the band's GIVE at the cloth's points P (cap space): HORIZONTAL, along the band's outward normal at the point's
    azimuth, the stations' gives interpolated round the band; whole at and below its foot, fading linearly to nothing at
    its top seam. No point moves up or down (the band keeps its 45 mm); the crown above it does not move"""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    phi = band_phi(P, spec)
    f = np.clip(1.0 - P[:, 1] / spec['band_h'], 0.0, 1.0)
    return (give_at(phi, g, phs) * f)[:, None] * band_normal(phi, spec)


def band_carry(phi_a, y_a, g, phs, spec=SPEC):
    """the RIGID motion of the band's local frame at (phi_a, y_a) under the give: what is sewn or pinned there rides it
    unstretched (the cockade, a button, a knot, a cord's section). Returns A (the band's face there), R and t: a point P
    of the part goes to A + t + R (P - A). Vectorised over stations"""
    phi_a = np.atleast_1d(np.asarray(phi_a, np.float64))
    y_a = np.broadcast_to(np.asarray(y_a, np.float64), phi_a.shape)
    hb = spec['band_h']

    def deformed(ph_, y_):
        Pb, Nb, _ = band_frame(ph_, y_, 0.0, spec)
        return Pb + Nb * (give_at(ph_, g, phs) * np.clip(1.0 - y_ / hb, 0.0, 1.0))[:, None]
    hp, hy = 1.0e-3, 1.0e-3
    A = band_frame(phi_a, y_a, 0.0, spec)[0]
    T0 = _unit(band_frame(phi_a + hp, y_a, 0.0, spec)[0] - band_frame(phi_a - hp, y_a, 0.0, spec)[0])
    V0 = np.broadcast_to(np.array([0.0, 1.0, 0.0]), T0.shape)
    N0 = np.cross(T0, V0)
    T1 = _unit(deformed(phi_a + hp, y_a) - deformed(phi_a - hp, y_a))
    V1 = _unit(deformed(phi_a, y_a + hy) - deformed(phi_a, y_a - hy))
    N1 = _unit(np.cross(T1, V1))
    V1 = np.cross(N1, T1)
    B0, B1 = np.stack([T0, V0, N0], -1), np.stack([T1, V1, N1], -1)
    return A, B1 @ np.transpose(B0, (0, 2, 1)), deformed(phi_a, y_a) - A


def vertex_parts(L, spec=SPEC):
    """each vertex of the low (L: low_arrays) named for the conform morph: its region, its side (x sign), the cords'
    stations (ATTR s: their path's arc length) and part (2 the upper, 3 the lower), the visor's plan distance xi"""
    V = np.asarray(L['V'], np.float64)
    reg_v = np.full(len(V), -1)
    for r in range(len(REGIONS)):
        reg_v[np.unique(L['F'][L['region'] == r])] = r
    A = np.asarray(L['ATTR'], np.float64)
    vis = np.isin(reg_v, [R_['visor_top'], R_['visor_under'], R_['visor_rim']])
    xi = np.zeros(len(V))
    xi[vis] = visor_xi(V[vis], spec)
    return dict(reg=reg_v, side=np.where(V[:, 0] >= 0.0, 1, -1), s=A[:, 0], part=np.rint(A[:, 3]).astype(int), xi=xi,
                vis=vis)


def conform_disp(L, g, phs, hinge_deg, spec=SPEC, parts=None):
    """the CONFORM MORPH (cap v3) at every vertex of the low (L: low_arrays; parts: vertex_parts): the band's GIVE on
    its cloth (give_disp: horizontal, at most GIVE_MAX in the cap's units, fading up the band); every RIGID part carried
    by the band's local frame where it is attached (band_carry: the cockade at its centre, each button and each knot at
    its own; the cords section by section, and over the visor's root by the visor under them, the stacked pair as one
    by the lower cord's contact, blended to the band's frame past the visor's end); the visor pitched by its HINGE
    (hinge_disp: rigid beyond HINGE_W). Cap space: the morph target's deltas"""
    parts = parts or vertex_parts(L, spec)
    V = np.asarray(L['V'], np.float64)
    reg, side = parts['reg'], parts['side']
    D = np.zeros_like(V)
    cloth = np.isin(reg, [R_['top'], R_['wall'], R_['band'], R_['inside']])
    D[cloth] = give_disp(V[cloth], g, phs, spec)
    vis = parts['vis']
    D[vis] = hinge_disp(V[vis], parts['xi'][vis], hinge_deg, spec)

    def rigid(m, phi_a, y_a):
        if m.any():
            A, Rm, t = band_carry(phi_a, y_a, g, phs, spec)
            D[m] = A[0] + t[0] + (V[m] - A[0]) @ Rm[0].T - V[m]
    lay = cord_layout(spec)
    rigid(reg == R_['cockade'], 0.0, spec['cockade_y'])
    for sd in (1, -1):
        rigid((reg == R_['button']) & (side == sd), sd * float(u_to_phi(lay['u_b'], spec)), lay['ys'])
        rigid((reg == R_['knot']) & (side == sd), sd * float(u_to_phi(lay['u_k'], spec)), lay['ys'])
    paths, _ = cord_paths(spec)
    for k, nm in enumerate(('upper', 'lower')):
        m = (reg == R_['cord']) & (parts['part'] == 2 + k)
        if not m.any():
            continue
        P, _N = paths[nm]
        sp_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        Cc = np.column_stack([np.interp(parts['s'][m], sp_, P[:, j]) for j in range(3)])
        ph_c = band_phi(Cc, spec)
        A, Rm, t = band_carry(ph_c, Cc[:, 1], g, phs, spec)
        Db = A + t + np.einsum('nij,nj->ni', Rm, V[m] - A) - V[m]
        wv = 1.0 - _smoothstep(lay['u_1'], lay['u_2'], np.abs(phi_to_u(ph_c, spec)))
        Cl = Cc.copy()
        Cl[:, 1] = lay['yl']                             # the lower cord's contact on the root: the pair moves as one
        Dv = hinge_disp(Cc, visor_xi(Cl, spec), hinge_deg, spec)
        D[m] = wv[:, None] * Dv + (1.0 - wv[:, None]) * Db
    return D


def rim_stations(spec=SPEC, n=96):
    """the band's foot at n stations of equal arc length (rim_probes'): its inner edge (the sweatband's foot), its outer
    edge (the felt's), the band's outward normals and the stations' azimuths"""
    Pi, _, _ = rim_probes(spec, n)
    phs = band_phi(Pi, spec)
    return Pi, band_frame(phs, 0.0, 0.0, spec)[0], band_normal(phs, spec), phs


SECTORS = 12                # the rim's SECTORS for the support gate: 30 deg each, the first centred on the front


def contact_sectors(on, phs, extra=()):
    """the contacts round the rim: the SECTORS (SECTORS equal arcs of the azimuth, the first centred on the front) that
    hold a rim station in contact or an extra contact (the visor's underside on the forehead, at its azimuth), the
    contact REGIONS (runs of neighbouring stations in contact, round the circle; an extra contact outside them a region
    of its own) and the SPAN: 360 deg less the largest gap between consecutive contacts (more than 180: they do not all
    lie on one side of the cap). Returns (sectors held, regions' azimuths (rad), span (rad))"""
    o = np.argsort(phs)
    on, ph = np.asarray(on, bool)[o], np.asarray(phs, np.float64)[o]
    n = len(on)
    runs = []
    if on.all():
        runs = [ph]
    elif on.any():
        k0 = int(np.nonzero(~on)[0][0])
        cur = []
        for j in range(1, n + 1):
            i = (k0 + j) % n
            if on[i]:
                cur.append(ph[i])
            elif cur:
                runs.append(np.array(cur))
                cur = []
        if cur:
            runs.append(np.array(cur))
    cents = [float(np.angle(np.exp(1j * r).mean())) for r in runs]
    allc = list(ph[on])
    for e in extra:
        allc.append(float(e))
        inside = any(np.min(np.abs(np.angle(np.exp(1j * (r - e))))) < 2.0 * np.pi / max(n, 1) for r in runs)
        if not inside:
            cents.append(float(e))
    if not allc:
        return 0, [], 0.0
    w = 2.0 * np.pi / SECTORS
    held = len(np.unique(np.floor(np.mod(np.asarray(allc) + 0.5 * w, 2.0 * np.pi) / w).astype(int)))
    a = np.sort(np.mod(np.asarray(allc), 2.0 * np.pi))
    gaps = np.diff(np.concatenate([a, [a[0] + 2.0 * np.pi]]))
    return held, cents, float(2.0 * np.pi - gaps.max())


def support_margin(Pc, com, up=(0.0, 1.0, 0.0)):
    """the cap's centre of mass against the SUPPORT POLYGON of its contact points Pc (world), seen along gravity: the
    signed distance (m) from the COM to the polygon's boundary, + inside; nan with fewer than three non-collinear
    contacts"""
    from scipy.spatial import ConvexHull
    up = _unit(up)
    e1 = _unit(np.cross(up, [1.0, 0.0, 0.0] if abs(up[0]) < 0.9 else [0.0, 0.0, 1.0]))
    e2 = np.cross(up, e1)
    Pc = np.asarray(Pc, np.float64).reshape(-1, 3)
    if len(Pc) < 3:
        return float('nan')
    Q = np.column_stack([Pc @ e1, Pc @ e2])
    c = np.array([np.dot(com, e1), np.dot(com, e2)])
    try:
        h = ConvexHull(Q)
    except Exception:  # noqa: BLE001 (collinear contacts)
        return float('nan')
    return float(-(h.equations[:, :2] @ c + h.equations[:, 2]).max())


@wp.kernel
def k_ray(mesh: wp.uint64, o: wp.array(dtype=wp.vec3), dr: wp.array(dtype=wp.vec3), tmax: float,
          t_out: wp.array(dtype=float), f_out: wp.array(dtype=int)):
    i = wp.tid()
    q = wp.mesh_query_ray(mesh, o[i], dr[i], tmax)
    t_out[i] = -1.0
    f_out[i] = -1
    if q.result:
        t_out[i] = q.t
        f_out[i] = q.face


_SCENE_BVH = {}


def cast(V, F, O, Dr, tmax=10.0, static=None):
    """rays O + t Dr (unit Dr) against the triangles (V, F) and, if given, a static mesh static = (Vs, Fs) (its BVH
    built once): each ray's first hit (t, -1 none) and face (the static mesh's faces first, then F's offset by its
    count)"""
    O32 = wp.array(np.asarray(O, np.float32), dtype=wp.vec3)
    D32 = wp.array(np.asarray(Dr, np.float32), dtype=wp.vec3)
    n = len(O)

    def run(mesh):
        t = wp.zeros(n, dtype=float)
        f = wp.zeros(n, dtype=int)
        wp.launch(k_ray, dim=n, inputs=[mesh.id, O32, D32, float(tmax), t, f])
        return t.numpy().astype(np.float64), f.numpy()
    t, f = run(_bvh(V, F))
    if static is None:
        return t, f
    key = (id(static[0]), len(static[0]), len(static[1]))
    if key not in _SCENE_BVH:
        _SCENE_BVH.clear()
        _SCENE_BVH[key] = _bvh(static[0], static[1])
    ts, fs = run(_SCENE_BVH[key])
    use_s = (ts >= 0.0) & ((t < 0.0) | (ts < t))
    return np.where(use_s, ts, t), np.where(use_s, fs, np.where(f >= 0, f + len(static[1]), -1))


def view_stations(M, views=STANDARD_VIEWS, world_up=(0.0, 1.0, 0.0)):
    """the engine scene's camera stations about the posed cap (scene_cap_v2.js): its centre C (the cap's (0, 0.03,
    0)), its origin's height (the 'rim'), its forward along the ground; per view (az, dist, dh) the camera's position
    and target"""
    C = M[:3, :3] @ np.array([0.0, 0.03, 0.0]) + M[:3, 3]
    rim = M[:3, 3]
    up = _unit(world_up)
    Rn = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0, keepdims=True)
    fwd = Rn @ np.array([0.0, 0.0, 1.0])
    fwd = _unit(fwd - up * np.dot(fwd, up))
    left = _unit(np.cross(up, fwd))
    out = []
    for az, dist, dh in views:
        a = np.radians(az)
        dr = fwd * np.cos(a) + left * np.sin(a)
        tgt = C.copy()
        tgt = tgt + up * (np.dot(rim, up) + 0.5 * dh - np.dot(tgt, up))
        pos = tgt + dr * dist
        pos = pos + up * (np.dot(rim, up) + dh - np.dot(pos, up))
        out.append((pos, tgt))
    return out, C, fwd, left


def daylight(Wcap, Fcap, Vs, Fs, M, rim_w, prog, drops=(0.0003, 0.0008, 0.0015, 0.003, 0.005), views=STANDARD_VIEWS,
             world_up=(0.0, 1.0, 0.0)):
    """DAYLIGHT under the band from the standard views (view_stations): points in the air just under the band's foot
    (each rim point rim_w dropped along the world's down by `drops`, kept where they lie outside the skin), a ray from
    each camera through each: one that reaches its point unoccluded and then hits NOTHING shows background through the
    gap (the cap floats); one that meets the head (Vs, Fs: the skin, the eyes, the glasses) behind it is a crevice
    against the head's own skin (a contact shadow). Returns per view (the daylight rays, the visible rays, the worst
    daylight point's drop below the rim)"""
    up = _unit(world_up)
    Q = (np.asarray(rim_w, np.float64)[:, None, :] - up[None, None, :] * np.asarray(drops)[None, :, None]).reshape(-1, 3)
    dq = np.repeat(np.asarray(drops)[None, :], len(rim_w), 0).ravel()
    outside = np.asarray(prog.eval(Q), np.float64) > 0.0
    Q, dq = Q[outside], dq[outside]
    stations, _, _, _ = view_stations(M, views, world_up)
    res = []
    for pos, _tgt in stations:
        dr = Q - pos[None, :]
        tq = np.linalg.norm(dr, axis=1)
        dr = dr / tq[:, None]
        t, f = cast(Wcap, Fcap, np.repeat(pos[None], len(Q), 0), dr, 20.0, static=(Vs, Fs))
        visible = (t < 0.0) | (t > tq - 1e-5)
        sky = visible & (t < 0.0)
        res.append((int(sky.sum()), int(visible.sum()), float(dq[sky].max()) if sky.any() else 0.0))
    return res


def front_read(Wcap, Fcap, reg_tri, Vs, Fs, M, eye_y, dist=0.42, fov_deg=30.0, size=(1280, 720),
               world_up=(0.0, 1.0, 0.0)):
    """the visor seen FROM THE FRONT AT EYE HEIGHT (the engine's camera: 1280 x 720, fov 30 deg; `dist` straight ahead
    of the cap's centre, at the eyes' height, aimed at the cap's centre): per pixel column across the middle half of the
    visor the run of pixels whose first hit is its UNDERSIDE, and the run of its top and rim. Returns the medians (px)
    and the underside's in mm at the visor's distance"""
    up = _unit(world_up)
    stations, C, fwd, left = view_stations(M, ((0.0, dist, 0.0),), world_up)
    pos = C + fwd * dist
    pos = pos + up * (eye_y - np.dot(pos, up))
    zc = _unit(C - pos)
    xc = _unit(np.cross(zc, up))
    yc = np.cross(xc, zc)
    W, H = size
    fpx = 0.5 * H / np.tan(0.5 * np.radians(fov_deg))
    nf = len(Fs)
    vis_t = np.isin(reg_tri, [R_['visor_top'], R_['visor_under'], R_['visor_rim']])
    Pv = np.asarray(Wcap, np.float64)[np.unique(np.asarray(Fcap)[vis_t])]
    rel = Pv - pos
    px = W / 2 + fpx * (rel @ xc) / (rel @ zc)
    py = H / 2 - fpx * (rel @ yc) / (rel @ zc)
    x0, x1 = np.percentile(px, [1, 99])
    y0, y1 = int(max(0, py.min() - 4)), int(min(H - 1, py.max() + 4))
    cols = np.arange(int(x0 + 0.25 * (x1 - x0)), int(x1 - 0.25 * (x1 - x0)) + 1, 2)
    rows = np.arange(y0, y1 + 1)
    CX, CY = np.meshgrid(cols, rows, indexing='ij')
    dr = _unit((CX.ravel() - W / 2)[:, None] / fpx * xc + (H / 2 - CY.ravel())[:, None] / fpx * yc + zc)
    t, f = cast(Wcap, Fcap, np.repeat(pos[None], len(dr), 0), dr, 5.0, static=(Vs, Fs))
    hit_cap = (f >= nf)
    rg = np.full(len(f), -1)
    rg[hit_cap] = np.asarray(reg_tri)[f[hit_cap] - nf]
    under = (rg == R_['visor_under']).reshape(CX.shape)
    top = np.isin(rg, [R_['visor_top'], R_['visor_rim']]).reshape(CX.shape)
    ru, rt = np.median(under.sum(1)), np.median(top.sum(1))
    dv = float(np.median(np.abs((Pv - pos) @ zc)))
    return dict(under_px=float(ru), top_px=float(rt), under_mm=float(ru * dv / fpx * 1e3), cam=pos.tolist())


def _give_solve(G, gap, gmax):
    """the band's GIVE per rim station from its gaps off the skin at the trial gives G (cap units, + out; gap (n, len(G)),
    worn metres) and its allowance gmax (GIVE_MAX x give_mask): where the foot lies within CONFORM_GAP of the skin (or
    in it) it is pushed OUT to CONFORM_GAP (the head presses the felt out), where it stands off it is drawn IN toward
    CONFORM_GAP as far as its allowance reaches (the felt hugs the head); smoothed round the band (the felt does not
    kink), never less than the push that keeps the foot REST_GAP off the skin, never past its allowance. Returns the
    gives, the gaps there and the least give each station needs (its floor: negative where it may draw in).
    Cap v7 (the lead's decision 9: "'_give_solve' must give IN as well as out, as its docstring and the doc's section 3
    say"): `need` is the least give that keeps the foot REST_GAP off the skin over the WHOLE allowance, from its full
    inward -gmax (a station clear even fully drawn in may go all the way in). Cap v3-v6 started it at 0 and searched only
    outward gives for it, so np.maximum(g, need) cancelled every inward give: the band only ever pushed out (v6's give was
    0 everywhere, its foot up to 7.6 mm off the skin at the sides)"""
    n = len(gap)
    g = np.zeros(n)
    need = -np.asarray(gmax, np.float64).copy()
    for i in range(n):
        ok = (G >= -gmax[i] - 1e-12) & (G <= gmax[i] + 1e-12)
        gi, ai = G[ok], gap[i, ok]                                # the gap grows with the give (out: off the skin)
        k = np.nonzero(ai >= REST_GAP)[0]
        need[i] = (np.interp(REST_GAP, ai[k[0] - 1: k[0] + 1], gi[k[0] - 1: k[0] + 1]) if len(k) and k[0] > 0 else
                   (gi[k[0]] if len(k) else gmax[i]))
        ok = (G >= -1e-12) & (G <= gmax[i] + 1e-12)
        gi, ai = G[ok], gap[i, ok]
        if gap[i, np.argmin(np.abs(G))] <= CONFORM_GAP:
            k = np.nonzero(ai >= CONFORM_GAP)[0]
            g[i] = (np.interp(CONFORM_GAP, ai[: k[0] + 1], gi[: k[0] + 1]) if len(k) and k[0] > 0 else
                    (gi[k[0]] if len(k) else gmax[i]))
        else:
            m = (G <= 1e-12) & (G >= -gmax[i] - 1e-12)
            gi, ai = G[m][::-1], gap[i, m][::-1]                  # from 0 inward
            k = np.nonzero(ai <= CONFORM_GAP)[0]
            if len(k):
                g[i] = np.interp(CONFORM_GAP, ai[: k[0] + 1][::-1], gi[: k[0] + 1][::-1]) if k[0] > 0 else gi[k[0]]
            elif len(ai):
                g[i] = gi[-1]
    k3 = np.exp(-0.5 * (np.arange(-3, 4) / 1.2) ** 2)
    k3 /= k3.sum()
    g = np.convolve(np.concatenate([g[-3:], g, g[:3]]), k3, mode='valid')
    g = np.clip(np.maximum(g, need), -gmax, gmax)
    gap_g = np.array([np.interp(g[i], G, gap[i]) for i in range(n)])
    return g, gap_g, need


def gate_perched(r):
    """cap v5's fit gate (the lead's decision 8, a PERCHED cap accepted): the support as before (contacts in three
    sectors spanning more than 180 deg, the centre of mass inside their polygon), the contacts including the visor's
    underside on the forehead AND the back, and no daylight from dead front and dead back (DEAD_VIEWS)"""
    dl = r.get('daylight')
    return bool(r.get('supported') and r.get('visor_contact') and r.get('back_contact') and dl is not None and
                all(dl[k] == 0 for k in DEAD_VIEWS))


def validate_fit(prog, origin, R, table, L, avoid=None, spec=SPEC, species='octopus', scene=None, eyes=None,
                 turrets=None, tilts=tuple(np.arange(0.0, 30.01, 2.0)), scales=tuple(np.arange(0.40, 0.611, 0.03)),
                 shifts=tuple(np.arange(-0.056, 0.0161, 0.008)), hinges=None, clear=0.0015, refine=True, n_lead=16,
                 log=print):
    """the cap on a hat seat (cap v3, the lead's decisions of 10-22). The pose is searched:
      (a) the cap KEEPS ITS PROPORTIONS: one scale s, each axis within FIT_ANISO of it (toward the head's elongation);
      (1) NO STRETCH: the band's GIVE is horizontal only, its lower edge in or out at most GIVE_MAX in the cap's own
          units, fading up the band, none at the front over the visor's root (give_mask); every rigid part rides the
          band's local frame; the visor is rigid but for its HINGE at the root, within the reference caps' measured
          pitch range (hinge_range, VISOR_PITCH) - all of it the conform morph (conform_disp);
      (2) the seat is a SUPPORT: at each pose (tilt back about the seat's x, s, a shift fore and aft, the hinge) the cap
          is LOWERED until it rests (the lowest height at which the rim, pushed out by at most its allowance, keeps
          REST_GAP off the skin, the visor REST_GAP off it, its turret zone, the eyes and the glasses `clear` off, the
          other parts clear / 2: the visor may rest on the forehead); then the give draws each station to CONFORM_GAP
          where it can (_give_solve). The gates: CONTACTS (rim stations within CONTACT_GAP; the visor's underside on the
          forehead counts as one) in at least three SECTORS spanning more than 180 deg round the rim (contact_sectors),
          the cap's centre of mass inside their SUPPORT POLYGON seen along gravity (support_margin), and for the leaders
          NO DAYLIGHT under the band from the five standard views (daylight; `scene` the head's meshes);
      (3) the visor READS AS A PEAK from the front at eye height (front_read: its underside's run in pixels; `eyes` the
          eyes' height), traded against (2).
    The choice: the supported poses; among them the daylight-free, else those within DAYLIGHT_TOL of the least
    daylight; of those the least tilt, then the front read, the contact share, the size nearest 0.50.
    turrets: [(centre, radii)] the eye mounds (creature space): the visor's skin distance counts against `clear` where
    its nearest skin point lies within 1.15 of a mound. A coarse grid, then a finer one round the leaders. L:
    low_arrays() (the shipped glb's vertices). Returns (entry: the seat's validated record, rows: every pose's numbers,
    conform: the chosen pose's give per rim station, its hinge and gap map, for the glb's morph target
    conform_<species>)"""
    d = dims(spec)
    parts = vertex_parts(L, spec)
    reg_v, vis = parts['reg'], parts['vis']
    V = np.asarray(L['V'], np.float64)
    F = np.asarray(L['F'], np.int64)
    reg_t = np.asarray(L['region'])
    avoid = avoid or {}
    T = np.asarray(table, np.float64)
    q = float(np.median(T[:, 2] / T[:, 1])) / (d['rz_o'] / d['rx_o'])
    alpha = float(np.clip((q - 1.0) / (q + 1.0), -FIT_ANISO, FIT_ANISO))
    an = np.array([1.0 - alpha, 1.0 / ((1.0 - alpha) * (1.0 + alpha)), 1.0 + alpha])
    mid = len(T) // 2
    cx0, cz0 = float(T[mid, 3]), float(T[mid, 4])
    R = np.asarray(R, np.float64)
    up = R[:, 1]
    world_up = np.array([0.0, 1.0, 0.0])
    h_lo, h_hi = hinge_range(spec)
    if hinges is None:
        # the lift end of the measured range and the forged pitch: a hinge that droops the visor further only lowers it
        # onto the forehead and the eyes (the cap must then stand higher). Cap v4's visor is forged at the range's low
        # end (egmar3b's pitch), so the lift end IS the forged pitch: one hinge, not the same poses twice
        hinges = (round(h_lo, 3), 0.0) if h_lo < -0.5 else (0.0,)
    Pi, Po, Nr, phs = rim_stations(spec)
    n_st = len(phs)
    gmax = GIVE_MAX * give_mask(phs, spec)
    G = np.linspace(-1.0, 1.0, 9) * GIVE_MAX
    xi_vis = parts['xi'][vis]
    band_in = np.isin(reg_v, [R_['band'], R_['inside']])
    oth = np.nonzero(~vis & ~band_in)[0]
    oth_s = oth[::3]
    tri_P = V[F]
    tri_a = 0.5 * np.linalg.norm(np.cross(tri_P[:, 1] - tri_P[:, 0], tri_P[:, 2] - tri_P[:, 0]), axis=1)
    tri_c = tri_P.mean(1)
    tri_vis = np.isin(reg_t, [R_['visor_top'], R_['visor_under'], R_['visor_rim']])
    tri_cloth = np.isin(reg_t, [R_['band'], R_['inside']])
    xi_tc = visor_xi(tri_c[tri_vis], spec)
    turrets = turrets or []
    perim = lambda W: float(np.linalg.norm(np.diff(np.vstack([W, W[:1]]), axis=0), axis=1).sum())
    tip_s = np.array([visor_mid(0.0, spec['visor_d'] - 0.004, spec), visor_mid(0.0, spec['visor_d'], spec)])

    def in_turret(Q):
        m = np.zeros(len(Q), bool)
        for c_, r_ in turrets:
            m |= np.linalg.norm((Q - np.asarray(c_)) / (1.15 * np.asarray(r_)), axis=1) <= 1.0
        return m

    def turret_min(W, f):
        """the least skin distance of the points W whose nearest skin point lies in a turret's zone"""
        m = f < 0.006
        if not m.any() or not turrets:
            return 1.0
        n = np.asarray(prog.normals(W[m]), np.float64)
        Q = W[m] - f[m, None] * n
        t = in_turret(Q)
        return float(f[m][t].min()) if t.any() else 1.0

    def avoid_min(W):
        out = {}
        for nm, fn in avoid.items():
            out[nm] = float(fn.points(W).min()) if hasattr(fn, 'points') else 1.0
        return out
    dys = np.linspace(0.040, -0.040, 33)
    cache = {}

    def evaluate(tilt, s, dz, hg):
        key = (round(float(tilt), 3), round(float(s), 4), round(float(dz), 5), round(float(hg), 3))
        if key in cache:
            return cache[key]
        S3 = s * an
        tr = np.array([cx0, 0.0, cz0 + dz])
        M0 = pose_matrix(origin, R, tr, S3, tilt)
        A, b0 = M0[:3, :3], M0[:3, 3]
        Pv = V[vis] + hinge_disp(V[vis], xi_vis, hg, spec)
        Pr = np.concatenate([Pi + gmax[:, None] * Nr, Po + gmax[:, None] * Nr])
        W0 = np.concatenate([Pr, Pv, V[oth_s]]) @ A.T + b0
        nr, nv = len(Pr), len(Pv)

        def probe(dy):
            W = W0 + dy * up
            f = np.asarray(prog.eval(W), np.float64)
            return W, f

        def ok_basic(f):
            return (np.minimum(f[:n_st], f[n_st:nr]).min() >= REST_GAP and f[nr:nr + nv].min() >= REST_GAP and
                    f[nr + nv:].min() >= 0.5 * clear)

        def ok_full(dy):
            W, f = probe(dy)
            if not ok_basic(f):
                return False
            if turret_min(W[nr:nr + nv], f[nr:nr + nv]) < clear:
                return False
            return all(v >= clear for v in avoid_min(W[nr:]).values())
        Wk = W0[None, :, :] + dys[:, None, None] * up[None, None, :]
        fk = np.asarray(prog.eval(Wk.reshape(-1, 3)), np.float64).reshape(len(dys), -1)
        okk = np.array([ok_basic(fk[k]) for k in range(len(dys))])
        row = dict(tilt_deg=float(tilt), s=round(float(np.prod(S3)) ** (1.0 / 3.0), 5),
                   scale=[round(float(x), 5) for x in S3], dz=round(float(dz), 4), hinge_deg=float(hg), ok=False,
                   supported=False)
        if not okk[0]:
            cache[key] = (row, None)
            return row, None
        k1 = int(np.argmin(okk)) if not okk.all() else len(dys) - 1
        hi_dy = dys[max(k1 - 1, 0)] if not okk.all() else dys[-1]
        lo_dy = dys[k1] if not okk.all() else dys[-1] - 0.01
        while not ok_full(hi_dy) and hi_dy < dys[0] + 0.03:
            lo_dy, hi_dy = hi_dy, hi_dy + 0.0025
        if not ok_full(hi_dy):
            cache[key] = (row, None)
            return row, None
        for _ in range(9):
            mid_dy = 0.5 * (lo_dy + hi_dy)
            if ok_full(mid_dy):
                hi_dy = mid_dy
            else:
                lo_dy = mid_dy
        dy = hi_dy
        tr[1] = dy
        M = pose_matrix(origin, R, tr, S3, tilt)
        A, b = M[:3, :3], M[:3, 3]
        # the give at the rest
        Wg = np.concatenate([(Pi[:, None, :] + G[None, :, None] * Nr[:, None, :]),
                             (Po[:, None, :] + G[None, :, None] * Nr[:, None, :])], 1).reshape(-1, 3) @ A.T + b
        fg = np.asarray(prog.eval(Wg), np.float64).reshape(n_st, 2, len(G))
        gap = fg.min(1)
        g, gap_g, need = _give_solve(G, gap, gmax)
        D = conform_disp(L, g, phs, hg, spec, parts)
        Wf = (V + D) @ A.T + b
        ff = np.asarray(prog.eval(Wf), np.float64)
        on = gap_g <= CONTACT_GAP
        iv = int(np.argmin(np.where(vis, ff, np.inf)))
        extra = [float(band_phi((V + D)[iv][None], spec)[0])] if ff[iv] <= CONTACT_GAP else []
        held, regions, span = contact_sectors(on, phs, extra)
        back = bool(np.any(on & (np.abs(np.angle(np.exp(1j * (phs - np.pi)))) <= BACK_ARC)))
        # the support polygon: the contact stations' nearer feet (with their give), the visor's contact point
        Pin = (Pi + g[:, None] * Nr) @ A.T + b
        Pout = (Po + g[:, None] * Nr) @ A.T + b
        inner_nearer = fg[np.arange(n_st), 0, np.argmin(np.abs(G[None, :] - g[:, None]), axis=1)] <= \
            fg[np.arange(n_st), 1, np.argmin(np.abs(G[None, :] - g[:, None]), axis=1)]
        Pc = np.where(inner_nearer[:, None], Pin, Pout)[on]
        if extra:
            Pc = np.vstack([Pc, Wf[iv][None]])
        # the centre of mass: the posed triangles' centroids by area (the visor's hinged, the band's given)
        cen = tri_c.copy()
        cen[tri_vis] += hinge_disp(tri_c[tri_vis], xi_tc, hg, spec)
        cen[tri_cloth] += give_disp(tri_c[tri_cloth], g, phs, spec)
        com = np.average(cen, axis=0, weights=tri_a) @ A.T + b
        margin = support_margin(Pc, com, world_up)
        # the visor tip's droop below the world's horizontal and the sight line from the eye-height front camera
        tw = (tip_s + hinge_disp(tip_s, np.array([spec['visor_d'] - 0.004, spec['visor_d']]), hg, spec)) @ A.T + b
        tdir = _unit(tw[1] - tw[0])
        droop_w = float(np.degrees(np.arcsin(-np.dot(tdir, world_up))))
        proxy = np.nan
        if eyes is not None:
            _, Cc, fwd, _ = view_stations(M, ((0.0, 0.42, 0.0),))
            cam = Cc + fwd * 0.42
            cam = cam + world_up * (eyes['y'] - np.dot(cam, world_up))
            vct = tw[1] - cam
            sight = float(np.degrees(np.arctan2(np.dot(vct, world_up), np.linalg.norm(vct - world_up *
                                                                                          np.dot(vct, world_up)))))
            proxy = sight - droop_w
        av = {nm: float(fn(Wf, F)) for nm, fn in avoid.items()}
        row.update(translation=np.round(tr, 5).tolist(), ok=True, dy=round(float(dy), 5),
                   rim_before=round(float(np.percentile(gap[:, int(np.argmin(np.abs(G)))], 85.0)), 5),
                   contact_share=round(float(on.mean()), 4), largest_gap=round(float(gap_g.max()), 5),
                   residual=round(float(np.percentile(gap_g, 100.0 * CONTACT_SHARE)), 5),
                   sectors=int(held), regions=len(regions),
                   region_deg=[round(float(np.degrees(c_)), 1) for c_ in regions],
                   span_deg=round(float(np.degrees(span)), 1), com_margin=round(float(margin), 5),
                   visor_contact=bool(extra), back_contact=back, visor_min=round(float(ff[vis].min()), 5),
                   visor_turret=round(turret_min(Wf[vis], ff[vis]), 5), band_min=round(float(ff[band_in].min()), 5),
                   others_min=round(float(ff[oth].min()), 5), give_max=round(float(np.abs(g).max()), 5),
                   give_out=round(float(g.max()), 5), give_in=round(float(g.min()), 5),
                   tip=tw[1].round(5).tolist(), tip_droop_deg=round(droop_w, 2), front_proxy_deg=round(float(proxy), 2),
                   s_head=round(float(np.prod(S3)) ** (1.0 / 3.0) * perim(Pout) / perim(Po @ A.T + b), 5), **av)
        row['clear_ok'] = bool(row['visor_min'] >= REST_GAP - 1e-6 and row['visor_turret'] >= clear - 1e-6 and
                               row['others_min'] >= 0.5 * clear - 1e-6 and row['band_min'] >= -0.0003 and
                               all(av[nm] >= clear - 1e-6 for nm in av))
        row['supported'] = bool(row['clear_ok'] and row['sectors'] >= 3 and span > np.pi and margin > 0.0)
        cf = dict(g=g, gap_before=gap[:, int(np.argmin(np.abs(G)))], gap_after=gap_g, need=need, on=on, phs=phs,
                  hinge=float(hg), M=M, Wf=Wf, rim_w=Pout, regions=regions, Pc=Pc, com=com)
        cache[key] = (row, cf)
        return row, cf

    def pre(r):
        # the leaders' order (their daylight and front read are cast next): the band's largest gap off the head first
        # (daylight shows through gaps), then the visor's lift toward the eye-height camera's sight line
        return (round(r['largest_gap'], 3), -(r['front_proxy_deg'] if np.isfinite(r['front_proxy_deg']) else -90.0),
                -r['contact_share'], abs(np.log(r['s'] / r['s_head'])), r['tilt_deg'])
    for hg in hinges:
        for tilt in tilts:
            for s in scales:
                for dz in shifts:
                    evaluate(tilt, s, dz, hg)
    if refine:
        sup = sorted([v[0] for v in cache.values() if v[0]['supported']], key=pre)[:6]
        if not sup:
            sup = sorted([v[0] for v in cache.values() if v[0]['ok']],
                         key=lambda r: (-r['sectors'], -r['span_deg'], -np.nan_to_num(r['com_margin'], nan=-1.0)))[:4]
        for r in sup:
            for hg in np.clip(r['hinge_deg'] + np.array([-1.0, 0.0, 1.0]), h_lo, h_hi):
                for tilt in r['tilt_deg'] + np.array([-1.0, 0.0, 1.0]):
                    for s in r['s'] + np.array([-0.015, 0.0, 0.015]):
                        for dz in r['dz'] + np.array([-0.004, 0.0, 0.004]):
                            if 0.0 <= tilt <= 40.0:
                                evaluate(tilt, s, dz, hg)
    rows = [v[0] for v in cache.values()]
    sup = sorted([v for v in cache.values() if v[0]['supported']], key=lambda v: pre(v[0]))
    if not sup:
        log('[peaked_cap] validate_fit: NO pose meets the support gates; the best is reported')
        sup = sorted([v for v in cache.values() if v[0]['ok'] and v[0]['clear_ok']],
                     key=lambda v: (-v[0]['sectors'], -v[0]['span_deg'], -np.nan_to_num(v[0]['com_margin'], nan=-1.0),
                                    -v[0]['contact_share']))
    if not sup:
        log('[peaked_cap] validate_fit: no pose rests clear of the eyes, the turrets and the glasses')
        return None, rows, None
    # daylight from the standard views for every candidate (up to 400: cap v5, the poses touching at the visor AND at
    # the back first, decision 8's contacts, then by the order above), then the front read at eye height for the leaders
    sup = sorted(sup, key=lambda v: (not (v[0]['visor_contact'] and v[0]['back_contact']), pre(v[0])))
    cands = sup[:400]
    if scene is not None:
        for r, cf in cands:
            dl = daylight(cf['Wf'], F, scene[0], scene[1], cf['M'], cf['rim_w'], prog)
            r['daylight'] = [x[0] for x in dl]
            r['daylight_seen'] = [x[1] for x in dl]
            r['daylight_drop'] = [round(x[2], 4) for x in dl]
        cands = sorted(cands, key=lambda v: (sum(v[0]['daylight']), pre(v[0])))
        for lo_t, hi_t in ((0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 41.0)):
            band_ = [v[0] for v in cands if lo_t <= v[0]['tilt_deg'] < hi_t]
            if band_:
                b_ = min(band_, key=lambda r: sum(r['daylight']))
                log(f'[peaked_cap]   tilt {lo_t:.0f}-{hi_t:.0f} deg: the least daylight {sum(b_["daylight"])} rays '
                    f'{b_["daylight"]} (tilt {b_["tilt_deg"]:.1f}, s {b_["s"]:.3f}, shift {b_["dz"] * 1e3:+.0f} mm, '
                    f'{b_["sectors"]} sectors, span {b_["span_deg"]:.0f}, the largest gap {b_["largest_gap"] * 1e3:.1f} mm) '
                    f'of {len(band_)} supported poses')
    # the choice: (2) first, the supported poses (if any); among them the daylight-free, else those within
    # DAYLIGHT_TOL of the least daylight (none on the octopus: its mantle falls away from the band's sides and back,
    # and the least daylight is bought by pushing the cap back 31 deg, the checker's complaint at 16); of those the
    # least tilt, then (3) the front read, the contact share and the size nearest v2's 0.50 (the look the lead passed)
    pool = [v for v in cands if v[0]['supported']] or cands
    if scene is not None:
        # cap v5 (the lead's decision 8): a PERCHED cap is accepted (no pose on this mantle is daylight-free and
        # stretching is forbidden): the gates are the contacts at the visor's underside AND at the back with the support
        # polygon as before, and NO daylight from dead front and dead back (DEAD_VIEWS); the sides' gaps are reported,
        # not gated. Among the poses that meet them, the least tilt, the front read, the contact share, the size
        g8 = [v for v in pool if gate_perched(v[0])]
        if g8:
            log(f'[peaked_cap] validate_fit: {len(g8)} of {len(pool)} supported poses meet decision 8 (visor + back '
                f'contacts, no daylight from dead front and dead back)')
            pool = g8
        else:
            dead = lambda r: sum(r['daylight'][k] for k in DEAD_VIEWS)
            dmin = min(dead(v[0]) for v in pool)
            log(f'[peaked_cap] validate_fit: NO pose meets decision 8; the least daylight from the dead views is {dmin}')
            pool = [v for v in pool if dead(v[0]) <= dmin]
        # cap v8 (the lead's decision 7: "the PERCHED fit at the worn size is accepted (s ~0.385, tilt ~18 deg) ...
        # decision 9's '2 mm over half the rim' bar is retired"): the cap keeps its WORN SIZE (the least scale band that
        # perches: a bigger cap sits wrong, the v7 record's 1.5 x cap on the back of the mantle) and the pose the lead
        # accepted: decision 9's shortfall (gate_fit) only ORDERS the worn size's poses now (no longer a gate), as it
        # did when that pose was chosen. The lead's new bar (no daylight at the eyes' height dead front and at the
        # three-quarters) is cast for every worn-size pose and logged: none reaches 0 (the first v8 remat chose by it:
        # least 28 rays, at tilt 28 deg pushed 56 mm back with an 8.8 mm gap; the accepted pose 0 + 22 + 22), so it is
        # REPORTED (measure_pose, t27 (7)), not used to move the accepted pose
        for r, cf in pool:
            dl = daylight(cf['Wf'], F, scene[0], scene[1], cf['M'], cf['rim_w'], prog, views=NEAR_DEAD_VIEWS)
            r['daylight_near'] = [x[0] for x in dl]
            r['fit_gate'], r['fit_short'] = gate_fit(r)
        s_lo_ = min(v[0]['s'] for v in pool)
        sized = [v for v in pool if v[0]['s'] < s_lo_ + 0.03 - 1e-6]
        smin_s = min(v[0]['fit_short'] for v in sized)
        if eyes is not None:
            for r, cf in sized:
                dh_e = float(eyes['y']) - float(cf['M'][1, 3])
                de = daylight(cf['Wf'], F, scene[0], scene[1], cf['M'], cf['rim_w'], prog,
                              views=tuple((a_, 0.42, dh_e) for a_ in EYE_VIEWS_AZ))
                r['daylight_eye'] = [x[0] for x in de]
            log(f'[peaked_cap] validate_fit: the daylight from the eyes\' height (az {EYE_VIEWS_AZ} deg, decision 7) on '
                f'the worn size\'s {len(sized)} poses: least {min(sum(v[0]["daylight_eye"]) for v in sized)} rays (bar 0; '
                f'{sorted(sum(v[0]["daylight_eye"]) for v in sized)[:12]})')
        log(f'[peaked_cap] validate_fit: the worn size kept (s {s_lo_:.3f}-{s_lo_ + 0.03:.3f}, {len(sized)} poses), '
            f'ordered by decision 9\'s shortfall (least {smin_s:.3f}; retired as a gate)')
        pool = sorted([v for v in sized if v[0]['fit_short'] <= smin_s + 0.05], key=lambda v: pre(v[0]))
    leaders = pool[:max(n_lead, len(pool))]
    for r, cf in leaders:
        if scene is not None and eyes is not None:
            fr = front_read(cf['Wf'], F, reg_t, scene[0], scene[1], cf['M'], eyes['y'])
            r['front_under_px'], r['front_top_px'], r['front_under_mm'] = fr['under_px'], fr['top_px'], fr['under_mm']

    def final(v):
        r = v[0]
        return (r['tilt_deg'], -r.get('front_under_px', 0.0), -r['contact_share'], abs(np.log(r['s'] / 0.5)))
    pick, cf = min(leaders, key=final)
    entry = {k: v for k, v in pick.items() if k not in ('tip',)}
    entry['perched_gate'] = gate_perched(pick)
    entry['visor_tip'] = np.round(pick['tip'], 5).tolist()
    entry['morph'] = f'conform_{species}'
    conform = dict(target=f'conform_{species}', g=cf['g'], phs=cf['phs'], hinge=cf['hinge'], before=cf['gap_before'],
                   after=cf['gap_after'], need=cf['need'], on=cf['on'], mode='give+hinge')
    log(f'[peaked_cap] validate_fit ({len(rows)} poses, {sum(r["ok"] for r in rows)} resting clear, '
        f'{sum(r["supported"] for r in rows)} supported): tilt {pick["tilt_deg"]:.1f} deg, hinge {pick["hinge_deg"]:+.2f}, '
        f'scale {pick["scale"]} (s {pick["s"]:.3f}), shift {pick["dz"] * 1e3:+.0f} mm; {pick["sectors"]} contact sectors '
        f'spanning {pick["span_deg"]:.0f} deg, the COM {pick["com_margin"] * 1e3:+.1f} mm inside; the rim within '
        f'{CONTACT_GAP * 1e3:.0f} mm on {pick["contact_share"] * 100:.0f} %, the largest gap '
        f'{pick["largest_gap"] * 1e3:.1f} mm; daylight {pick.get("daylight")}; the front read '
        f'{pick.get("front_under_px", float("nan")):.0f} px of underside')
    return entry, rows, conform


def measure_pose(prog, origin, R, L, Dm, pose, avoid=None, spec=SPEC, scene=None, eyes=None, turrets=None,
                 clear=0.0015):
    """a cap POSE re-measured independently of the search (t27 on the shipped glb): its vertices L['V'] displaced by
    Dm (the glb's own morph target, cap space), placed by pose (tilt_deg, scale, translation). The rim stations take the
    give the morph gives the band's foot (its horizontal displacement at the foot's vertices, round the band); then the
    support gates (contacts, sectors, span, the centre of mass against their polygon), the clearances (the visor off
    the skin and off the turrets, the band, the other parts, `avoid`), the daylight from the five standard views and the
    front read at eye height. Returns a dict"""
    V = np.asarray(L['V'], np.float64)
    F = np.asarray(L['F'], np.int64)
    Dm = np.asarray(Dm, np.float64)
    parts = vertex_parts(L, spec)
    reg_v, vis = parts['reg'], parts['vis']
    band_in = np.isin(reg_v, [R_['band'], R_['inside']])
    M = pose_matrix(origin, R, pose['translation'], pose['scale'], pose['tilt_deg'])
    A, b = M[:3, :3], M[:3, 3]
    Pi, Po, Nr, phs = rim_stations(spec)
    foot = band_in & (V[:, 1] < 0.0005)
    phf = band_phi(V[foot], spec)
    gf = (Dm[foot] * band_normal(phf, spec)).sum(1)
    g = give_at(phs, gf, phf)
    Wf = (V + Dm) @ A.T + b
    ff = np.asarray(prog.eval(Wf), np.float64)
    Pin, Pout = (Pi + g[:, None] * Nr) @ A.T + b, (Po + g[:, None] * Nr) @ A.T + b
    fi, fo = np.asarray(prog.eval(Pin), np.float64), np.asarray(prog.eval(Pout), np.float64)
    gap = np.minimum(fi, fo)
    on = gap <= CONTACT_GAP
    iv = int(np.argmin(np.where(vis, ff, np.inf)))
    extra = [float(band_phi((V + Dm)[iv][None], spec)[0])] if ff[iv] <= CONTACT_GAP else []
    held, regions, span = contact_sectors(on, phs, extra)
    back = bool(np.any(on & (np.abs(np.angle(np.exp(1j * (phs - np.pi)))) <= BACK_ARC)))
    Pc = np.where((fi <= fo)[:, None], Pin, Pout)[on]
    if extra:
        Pc = np.vstack([Pc, Wf[iv][None]])
    tri = Wf[F]
    ta = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    com = np.average(tri.mean(1), axis=0, weights=ta)
    margin = support_margin(Pc, com, (0.0, 1.0, 0.0))
    tur = 1.0
    if turrets:
        m = vis & (ff < 0.006)
        if m.any():
            n = np.asarray(prog.normals(Wf[m]), np.float64)
            Q = Wf[m] - ff[m, None] * n
            zone = np.zeros(len(Q), bool)
            for c_, r_ in turrets:
                zone |= np.linalg.norm((Q - np.asarray(c_)) / (1.15 * np.asarray(r_)), axis=1) <= 1.0
            tur = float(ff[m][zone].min()) if zone.any() else 1.0
    out = dict(contact_share=float(on.mean()), largest_gap=float(gap.max()), gap=gap, phs=phs, give=g,
               sectors=int(held), regions=[float(np.degrees(r_)) for r_ in regions], span_deg=float(np.degrees(span)),
               com_margin=float(margin), visor_contact=bool(extra), back_contact=back, visor_min=float(ff[vis].min()),
               visor_turret=tur,
               band_min=float(ff[band_in].min()), others_min=float(ff[~vis & ~band_in].min()), all_min=float(ff.min()),
               M=M, Wf=Wf)
    for nm, fn in (avoid or {}).items():
        out[nm] = float(fn(Wf, F))
    out['supported'] = bool(out['sectors'] >= 3 and span > np.pi and margin > 0.0)
    if scene is not None:
        dl = daylight(Wf, F, scene[0], scene[1], M, Pout, prog)
        out['daylight'] = [x[0] for x in dl]
        out['daylight_seen'] = [x[1] for x in dl]
        out['perched_gate'] = gate_perched(out)
        # cap v7 (decision 9): the daylight within 10 deg of dead front and dead back, and the fit's gates
        dn = daylight(Wf, F, scene[0], scene[1], M, Pout, prog, views=NEAR_DEAD_VIEWS)
        out['daylight_near'] = [x[0] for x in dn]
        out['fit_gate'], out['fit_short'] = gate_fit(out)
        if eyes is not None:
            # cap v8 (the lead's decision 7: "no daylight at eye height from the front and the three-quarters ... dark
            # wedges with the head behind them are acceptable for a perched cap"): the daylight from cameras at the eyes'
            # height, dead front and the two three-quarters
            dh_e = float(eyes['y']) - float(M[1, 3])
            de = daylight(Wf, F, scene[0], scene[1], M, Pout, prog,
                          views=tuple((a_, 0.42, dh_e) for a_ in EYE_VIEWS_AZ))
            out['daylight_eye'] = [x[0] for x in de]
            out['daylight_eye_seen'] = [x[1] for x in de]
            out['eye_gate'] = all(x[0] == 0 for x in de)
        if eyes is not None:
            out['front'] = front_read(Wf, F, np.asarray(L['region']), scene[0], scene[1], M, eyes['y'])
    return out


# -------------------------------------------------------------------------------------------------------- export
def export_glb(path, L, maps, spec=SPEC, conform=None):
    """a static glb: one mesh, one material (base, normal, the ORM lossless: its B is the metalness of the gold, the
    masks in KHR_materials_volume's thickness slot as the creatures carry theirs), the fit data in the root node's and
    the file's extras. conform: [(the validated entry, validate_fit's conform)] per species: each a MORPH TARGET on
    the mesh (POSITION deltas, prop space: conform_disp over every vertex, the band's horizontal give, the parts it
    carries rigidly, the visor's hinge; mesh.extras.targetNames, its weight 0), named in the fit data's `conform` for
    that species with the pose it was computed for (the runtime sets its weight to 1 when the cap is worn on that
    species at exactly that pose)"""
    from .. import gltf
    g = gltf.GLB()
    # cap v6 (the lead's decision 4): the albedo LOSSLESS (PNG), the cockade's 13 px/mm island with it (v5's JPEG q94
    # blurred the red disc's pebbles and the rye's grains, the v5 check)
    t_base = g.texture(maps['albedo'], fmt='png')
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='png')
    t_msk = g.texture(maps['masks'], fmt='png')
    mat = g.material('peaked_cap', base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop='peaked_cap', masks=t_msk,
        masks_channels='R fuzz / sheen amount (cloth only), G material (0 worsted, 1/3 felt, 2/3 leather and linen, '
                       '1 hard: metal, lacquer, enamel), B palette zone (0 crown and the inside, 1/3 band and pipings, '
                       '2/3 gold, 1 visor), A handling wear',
        palette_zones=list(PALETTE), palette_base=maps.get('palette_base', {}),
        metalness='ORM B: 1 on the gold (cords, knots, buttons, the stamped wreath, the cockade\'s rings, rye and '
                  'arms)'))
    mesh = g.mesh('peaked_cap', L['V'], L['N'], L['TAN'], L['UV'], [(L['F'], mat)])
    fit = fit_data(spec)
    if conform:
        names, targets = [], []
        fit['conform'] = {}
        for entry, cf in conform:
            Dm = conform_disp(L, cf['g'], cf['phs'], cf['hinge'], spec).astype(np.float32)
            targets.append({'POSITION': g.accessor(Dm, 'VEC3', 34962, minmax=True)})
            names.append(cf['target'])
            sp = cf['target'].split('conform_', 1)[-1]
            fit['conform'][sp] = dict(
                target=cf['target'], mode=cf['mode'], give_max_mm=round(float(np.abs(cf['g']).max()) * 1e3, 2),
                give_units='the cap\'s own', hinge_deg=round(cf['hinge'], 3), visor_pitch_deg=round(visor_pitch(spec) +
                                                                                                    cf['hinge'], 2),
                supported=entry['supported'], sectors=entry['sectors'], span_deg=entry['span_deg'],
                com_margin_mm=round(entry['com_margin'] * 1e3, 2), contact_share=entry['contact_share'],
                largest_gap_mm=round(entry['largest_gap'] * 1e3, 2), daylight=entry.get('daylight'),
                back_contact=entry.get('back_contact'), perched_gate=entry.get('perched_gate'),
                front_under_px=entry.get('front_under_px'), daylight_near=entry.get('daylight_near'),
                fit_gate=entry.get('fit_gate'), give_in_mm=round(float(-np.min(cf['g'])) * 1e3, 2),
                pose=dict(tilt_deg=entry['tilt_deg'], scale=entry['scale'], translation=entry['translation']))
        mj = g.j['meshes'][mesh]
        for p in mj['primitives']:
            p['targets'] = targets
        mj['weights'] = [0.0] * len(targets)
        mj['extras'] = dict(targetNames=names)
    g.node('peaked_cap', mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(path, extras=dict(bestiary=dict(prop='peaked_cap', archetype='hat', units='m', up='+Y',
                                                  forward='+Z', left='+X', triangles=int(len(L['F'])),
                                                  pattern='the GDR general\'s peaked cap (Skye\'s references, 10-22)',
                                                  fit=fit)))


# --------------------------------------------------------------------------------------------- the whole forge
def buried_triangles(L, spec=SPEC, depth=0.00005):
    """the low's triangles lying WHOLLY inside ANOTHER part of the block-out, their centre and their three corners (a
    cord inside its knot or under the other cord's end behind the button, the buttons' and the visor's roots in the
    band): hidden, so not baked; their texels dilate from their neighbours (round_glasses' rule, here judged by the
    other parts' own programs, since a part's own chords lie up to half a millimetre inside its own round). Baked,
    they failed the first forge's gate (the cords 5.8-6.8 % of their texels missed). By the centre alone, the band's
    15 x 23 mm front triangles, centred under the cockade, went unbaked whole: a wedge of dilated texels over the
    cockade, forge 10-21; a triangle only partly covered is baked, its covered texels hidden by contact_hidden"""
    cen = L['V'][L['F']].mean(1)
    corners = [L['V'][L['F'][:, k]] for k in range(3)]
    cord_of = np.rint(L['ATTR'][L['F'][:, 0], 3]).astype(int)          # ring_tube's part: 2 the upper, 3 the lower
    every = ('crown', 'visor', 'pipings', 'edge', 'cord_upper', 'cord_lower', 'knots', 'buttons', 'cockade')
    groups = [((R_['top'], R_['wall'], R_['band'], R_['inside']), ('crown', 'pipings'), None),
              ((R_['visor_top'], R_['visor_under'], R_['visor_rim']), ('visor', 'edge'), None),
              ((R_['cord'],), ('cord_upper',), 2), ((R_['cord'],), ('cord_lower',), 3),
              ((R_['knot'],), ('knots',), None), ((R_['button'],), ('buttons',), None),
              ((R_['cockade'],), ('cockade',), None)]
    out = np.zeros(len(cen), bool)
    for regs, own, cord in groups:
        sel = np.isin(L['region'], regs) & ((cord_of == cord) if cord is not None else True)
        if sel.any():
            others = build_sdf(spec, parts=tuple(p for p in every if p not in own))
            inside = others.eval(cen[sel]).astype(np.float64) < -depth
            for Pk in corners:
                inside &= others.eval(Pk[sel]).astype(np.float64) < -depth
            out[sel] = inside
    return out


def contact_hidden(spec=SPEC, reach=0.0011):
    """bake.bake's `exclude` (its hook for texels under a growth): a MISSED texel whose low point lies within `reach`
    of two parts of the block-out, or inside one of them, is hidden in a contact crevice (the cords lying on the
    visor's root, a knot's or a button's rim on the band, the visor rim's ends going under the cords into the band): it
    stays out of the miss bar and the gate and its texels dilate from their neighbours. The second forge's every
    remaining failure was one of these (the visor's root under the cords, the rim's ends, the band at the knots'
    edges, a cord's end island behind its button). Cap v5: the reach 1.1 mm (v4 0.5): the cords now lie along the
    band's sides from the visor's ends to the hidden buttons (62-130 deg), where the band's low is one slanted strip up
    to ~1 mm inside the felt's face, the cords 0.1 mm off that face: the band's texels under the pair lay 0.6-0.9 mm
    from the cord, and the first v5 forge failed band islands #6 / #7 on them (2.9 % fully missed, tests/out/cap/v5/
    scratch/miss_map.py: every miss at 75-135 deg, 10-25 mm up, under the pair)"""
    groups = [('crown', 'pipings'), ('visor', 'edge'), ('cord_upper',), ('cord_lower',), ('knots',), ('buttons',),
              ('cockade',)]
    progs = [build_sdf(spec, parts=g) for g in groups]

    def exclude(P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        if not len(P):
            return np.zeros(0, bool)
        D = np.sort(np.stack([p.eval(P).astype(np.float64) for p in progs], 1), axis=1)
        return D[:, 1] < reach
    return exclude


def keep_region(spec=SPEC, margin=0.008):
    """the voxel grid's cells: where sculpt detail lives (the band's front half and all on it: the wreath, the cockade,
    the cords, knots and buttons; the visor and its rim; the wall's and the band's seams in the slab |x| < 6 mm). The
    crown's top, the band's back half and the lining carry none: the analytic block-out is their high (the bake samples
    it outside the grid), as the octopus's grid lives only round its head and one arm"""
    detail = build_sdf(spec, parts=('visor', 'edge', 'cords', 'knots', 'buttons', 'cockade'))
    top = spec['band_h'] + spec.get('seam_rise', 0.0) + 0.005          # cap v6: the band's seam raised at the front
    # cap v7 (the lead's decision 6: "the stair-stepped V wedge at the front centre"): the seams' slab |x| < 6 mm stops
    # 3.4 mm under each piping's centre (the seams end 2.5 mm short of its surface, plan_cap): v6's slab ran on up over
    # the front piping, the roll and the top, which the 0.15 mm voxels drew stair-stepped in a 12 mm strip at the front
    # centre (beside the analytic surface either side of it: the V wedge the v6 check saw at close range)
    dd = dims(spec)
    y_front = spec['band_h'] + spec['rise_front'] - dd['rp'] - 0.0034
    y_back = spec['band_h'] + spec.get('rise_back', spec['rise_side']) - dd['rp'] - 0.0034

    def keep(pts):
        pts = np.asarray(pts, np.float64)
        slab = (np.abs(pts[:, 0]) < 0.006) & (pts[:, 1] < np.where(pts[:, 2] > 0.0, y_front, y_back))
        return ((pts[:, 1] < top) & (pts[:, 2] > -0.02)) | slab | (detail.eval(pts).astype(np.float64) < margin)
    return keep


def forge(out_dir, size=2048, voxel_size=0.00015, band=0.0009, ss=2, seed=7, spec=SPEC, conform=None, log=print):
    """block-out -> low (+ gates) -> UVs -> [the per-species fits and conform morphs] -> plan -> voxel high (GPU) ->
    bake (GPU) -> material -> glb; returns the glb's path. 0.15 mm voxels (the satin stitches lie 0.55 mm apart: 3.7
    voxels a stitch) in a +-0.9 mm band where keep_region says; the bake at 2048 x ss 2. conform: {species: dict(prog,
    origin, R, table, avoid)} (validate_fit's inputs on that species' seat): each fit's morph ships as a morph target,
    its pose in the fit data's `conform` (export_glb)"""
    import os
    import time

    from PIL import Image

    from .. import bake, gates, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    prog = build_sdf(spec)
    low = build_low(spec, prog=prog, log=log)
    part = np.zeros((len(low['V']), len(REGIONS)))
    for k in range(4):
        part[low['Q'][:, k], low['region']] = 1.0
    q, txt = gates.quad_quality(QuadMesh(low['V'], low['Q'], {'part': part}), prog,
                                region_names=dict(enumerate(REGIONS)))
    log('[peaked_cap] gates:\n' + txt)
    uvs = unwrap(low, size=size, log=log)
    L = low_arrays(low, uvs)
    fits = []
    for sp, ci in (conform or {}).items():
        entry, rows, cf = validate_fit(ci['prog'], ci['origin'], ci['R'], ci['table'], L, avoid=ci.get('avoid'),
                                       spec=spec, species=sp, scene=ci.get('scene'), eyes=ci.get('eyes'),
                                       turrets=ci.get('turrets'), log=log)
        if entry is not None:
            fits.append((entry, cf))
    buried = buried_triangles(L, spec) & L['bake']
    L['bake'] = L['bake'] & ~buried
    log(f'[peaked_cap] the bake set: {int(L["bake"].sum())} of {len(L["F"])} triangles (the stacked right knot and button '
        f'left to their left twins; {int(buried.sum())} buried in another part, not baked: their texels dilate)')
    plan = plan_cap(prog, spec, np.random.default_rng(seed), log=log)
    lo, hi = bounds(spec)
    # cap v6: the high's own block-out carries the cords as their thin cores: the plan adds the ropes' plies round them
    prog_high = build_sdf(spec, rope_core=True)
    G = voxel.SparseSDF(prog_high, lo, hi, voxel=voxel_size, band=band, extra=plan.bounds(prog_high, band),
                        keep=keep_region(spec), log=log)
    plan.apply(G, log=log)
    sel = L['bake']
    # cap v5: the cage past the relief's tallest (RELIEF_MAX + 0.7 mm): the acorns on the leaves on the backing reach
    # ~4.3 mm over the felt, and v4's 4 mm cage started the search inside the right acorn (a 21-texel miss cluster, the
    # third v5 forge; tests/out/cap/v5/scratch/texel_where.py)
    cage = max(0.004, RELIEF_MAX + 0.0007)
    res = bake.bake(G, L['V'], L['F'][sel], L['UV'], L['N'], L['TAN'], L['region'][sel], size=size, ss=ss, cage=cage,
                    ao_r=AO_REACH, cav_r=0.0015, n_ao=24, n_cav=12, n_thk=1, thk_max=0.005, seed=seed,
                    region_names=dict(enumerate(REGIONS)), exclude=contact_hidden(spec), log=log)
    keep_ = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
             if k != 'position'}
    np.savez_compressed(os.path.join(out_dir, 'drivers_peaked_cap.npz'), **keep_)
    # cap v6: the material pass at 4 x 4 sub-samples a texel (v5 the bake's 2 x 2: the cockade's ribbon stripes and the
    # rye's grains came out stair-stepped, the v5 check); its kernel is cheap beside the bake
    maps = run_material(L, res, size, 1.0 / L['px_per_m'], spec, ss=4, log=log)
    for k in ('albedo', 'normal', 'orm', 'masks'):
        Image.fromarray(maps[k]).save(os.path.join(out_dir, f'T_peaked_cap_{k}.png'))
    path = os.path.join(out_dir, 'peaked_cap.glb')
    nbytes = export_glb(path, L, maps, spec, conform=fits)
    log(f'[peaked_cap] wrote {path} ({nbytes / 1e6:.1f} MB, {len(L["F"])} triangles) in {time.time() - t0:.0f}s')
    return path


def remat(out_dir, size=2048, spec=SPEC, conform=None, log=print):
    """cap v8: the forge's TAIL on its own bake: the low, its UVs and the fits rebuilt exactly as forge() builds them,
    the bake's drivers read back from out_dir/drivers_peaked_cap.npz (forge() wrote them: float16 widened back), then
    the material pass and the glb. For a change to the PAINT only (the material kernel, MATERIAL): the sculpt and its
    bake must be the ones the npz was baked from (the same plan_cap); returns the glb's path"""
    import os
    import time

    from PIL import Image
    t0 = time.time()
    prog = build_sdf(spec)
    low = build_low(spec, prog=prog, log=log)
    L = low_arrays(low, unwrap(low, size=size, log=log))
    fits = []
    for sp, ci in (conform or {}).items():
        entry, rows, cf = validate_fit(ci['prog'], ci['origin'], ci['R'], ci['table'], L, avoid=ci.get('avoid'),
                                       spec=spec, species=sp, scene=ci.get('scene'), eyes=ci.get('eyes'),
                                       turrets=ci.get('turrets'), log=log)
        if entry is not None:
            fits.append((entry, cf))
    L['bake'] = L['bake'] & ~(buried_triangles(L, spec) & L['bake'])
    Dz = np.load(os.path.join(out_dir, 'drivers_peaked_cap.npz'), allow_pickle=True)
    res = {k: (Dz[k].astype(np.float32) if Dz[k].dtype == np.float16 else Dz[k]) for k in Dz.files}
    log(f'[peaked_cap] remat: the bake read back from {out_dir} ({len(res)} drivers)')
    maps = run_material(L, res, size, 1.0 / L['px_per_m'], spec, ss=4, log=log)
    for k in ('albedo', 'normal', 'orm', 'masks'):
        Image.fromarray(maps[k]).save(os.path.join(out_dir, f'T_peaked_cap_{k}.png'))
    path = os.path.join(out_dir, 'peaked_cap.glb')
    nbytes = export_glb(path, L, maps, spec, conform=fits)
    log(f'[peaked_cap] remat wrote {path} ({nbytes / 1e6:.1f} MB) in {time.time() - t0:.0f}s')
    return path
