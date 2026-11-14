"""MEXICAN REDKNEE TARANTULA (Brachypelma hamorii, adult female): the Bestiary's D4 base, an ARACHNID
(work/bestiary/research/TARANTULA_PLAN.md with its CRITIC 11-10 and LEAD 11-10 marks). T1, the design animal, is the
genus's proportions at B. hamorii's own size (plan §0.1): CL 24.0 mm; the lengths are L1's five congener females' means
x 24 (the species' own table is in a closed paper); the layout of the coxae, the fang and the abdomen's plan are c37's
(the underside through glass); the leg directions, the slopes and the girths are i01's (the wild animal from above).

D4.0 (11-10): the SPEC, FOLDED from the JSON files, never retyped: research/tarantula_scripts/d40_fold_spec.py turns
tarantula_work/plan/plan_numbers.json and D4.0b's three JSONs (tarantula_work/data/d40b_c37_coxae.json,
d40b_i01_legs.json, d40b_i01_widths.json) into rows; work/bestiary/tests/d4_00_spec.py checks every such row here against
that fold, and d4_00b_measure.py recomputes D4.0b's JSONs from their tracings.

THE LEAD'S CALLS (11-10, plan §0 items 12-18) carried here: the abdomen 29.5 mm (F11: a well-fed female, the body 53.5
mm inside the species' own 52-54); one metatarsus design per leg pair (F3: legs.scopula_share, legs.spines_mt); the
anatomy decides the joint map (F4: rig.ik, rig.ranges); the skitter's stride comes down to the legs' reach (F13:
gait.skitter, set by D4.1).

UNITS: LIFE MILLIMETRES, degrees, linear RGB for the colour facts. The generator (families/arachnid.py, D4.1) multiplies
once by SPEC['author_scale'] = 8: T1 is built and exported at x8 with extras.bestiary.life_scale = 0.125 (plan §5.6).
THE PLAN FRAME: the carapace's front edge on the midline at z 0, +z forward, +y up from the GROUND, +x the creature's
LEFT (DESIGN.md). Every sided value is the LEFT side's; the right is its mirror p_R = M p_L.

TAGS holds every leaf's source in the plan's legend: [P] a photo reading (photo id), [L] literature L1-L6
(tarantula_work/data/literature.md), [C] compiled or textbook, [H] a house file, [D] a design decision (its reason in the
note), [E] an estimate (its gate in the note). Makers: -pn the plan's plan_numbers.py, -d40b the D4.0b measurements,
-d40 derived here by the rule in its note, -d41 the skeleton round (families/arachnid.py; tests/d4_01_skeleton.py).

MORPHS (plan §2.7): male, thin (i01's wild animal), fresh moult. morph(name) composes each from SPEC.
"""
import copy
import re

AUTHOR_SCALE = 8.0

SPEC = dict(
    family='arthropod', body_plan='arachnid', author_scale=AUTHOR_SCALE, sex='female', species='Brachypelma hamorii',
    # ---- raw readings kept beside the rows made from them (D4.0b; build_NOTES B2-B6)
    photos=dict(
        c37=dict(sternum=(9.33, 9.61), labium=(3.16, 3.79), fang=7.16, abdomen=(28.8, 19.1), abd_front_z=-22.8,
                 furrow=7.4, pad=(0.543, 0.548, 0.376)),
        i01=dict(dense=dict(patella=4.71, tibia=4.72, metatarsus=3.47, tarsus=3.75),
                 height=dict(r1=(8.3, 16.24, 10.98), r4=(11.35, 21.13, 7.79)), mt_slope=(35.2, 35.6, 36.2),
                 femur_rise=(29.2, 19.3, 53.9, 42.9, 28.6, 44.9, 42.2, 53.1), chel_ahead=0.191, tubercle_w=0.0845, palp_girth=0.65, envelope=(1.029, 1.177, 0.867, 2.87),
                 flame_mm=4.1, flame_across=0.871),
        i04=dict(palp_tibia_band=0.35),
        c15=dict(guard_per_mm2=0.6, guard_len=(1.3, 4.2), guard_lie=(20.0, 40.0)),
        # the sweep's items 6 and 7 (11-11; build_NOTES B22): the knee's pattern on the fresh moult's eight patellae
        # seen face-on; guard setae along a leg's edge; the tibia's bare line
        c38=dict(flame_across=0.844, far_rim=0.178, pale_side=0.07),
        c13=dict(guard_per_mm_edge=(1.98, 1.56)),
        c14=dict(tibia_line=(0.1, 1.0, 0.05)),
        v01=dict(period=1.85, lag_I=0.37)),
    # ---- the body (plan §2.1): lengths L1 x 24; heights [E]
    body=dict(CL=24.0, CW=22.114, abd_len=29.5, body_len=53.5, abd_W=19.2, abd_H=17.3, abd_front_z=-22.8, pedicel_r=2.4,
              sternum=(10.663, 9.506), labium=(2.88, 3.828), fovea_w=5.455, fovea_z=-15.4,
              height=9.6, edge_h=4.3, front_h=5.0, rear_h=5.5, fovea_dip=1.2),
    eyes=dict(tubercle=(2.664, 2.412), tubercle_z=-1.6, AME=0.499, ALE=0.598, PME=0.389, PLE=0.552,
              gap=(0.554, 0.283, 1.332, 0.103, 0.302)),
    chelicera=dict(L=10.1, W=4.7, ahead=4.58, fang=6.86, pair_w=10.74, teeth=(9, 11)),
    spinnerets=dict(PLS=(4.222, 3.218, 3.602), PMS=2.551),
    # ---- the legs (plan §2.2): femur to tarsus L1 x 24; coxae and trochanter c37; girths i01
    legs=dict(
        I=dict(coxa=10.54, femur=15.919, patella=9.948, tibia=12.614, metatarsus=11.988, tarsus=8.201),
        II=dict(coxa=9.03, femur=14.602, patella=9.449, tibia=10.91, metatarsus=11.1, tarsus=8.206),
        III=dict(coxa=7.03, femur=13.764, patella=8.746, tibia=9.679, metatarsus=12.646, tarsus=7.872),
        IV=dict(coxa=9.01, femur=16.69, patella=9.108, tibia=12.66, metatarsus=17.1, tarsus=9.048),
        trochanter=3.23,
        # each coxa's joint on the sternum's margin (x from the midline, z from the carapace front) and the way it points
        # (degrees from forward toward the side), the LEFT side
        coxae=dict(I=(3.72, -11.62, 45.9), II=(4.7, -14.0, 70.4), III=(4.49, -16.67, 99.6), IV=(2.46, -19.05, 132.3)),
        diam=dict(coxa=4.7, trochanter=3.3, femur=4.5, patella=3.8, tibia=3.8, metatarsus=2.6, tarsus=2.9),
        pair_girth=dict(I=1.0, II=1.0, III=1.0, IV=1.05),
        scopula_share=dict(I=1.0, II=0.9, III=0.6, IV=0.4), spines_mt=dict(I=(1, 4), IV=(14, 18)),
        claws=2, claw=1.6),
    palp=dict(coxa=9.78, trochanter=3.0, femur=11.935, patella=7.075, tibia=8.935, tarsus=8.878,
              coxae=(2.1, -10.0, 28.3), maxilla=(8.47, 4.24), girth=0.65, claws=1),
    # ---- the coat's depths and counts (plan §2.3; D4.0b's count)
    coat=dict(velvet=0.6, band=(1.0, 2.5), guard_reach=3.0, abd_long=(2.9, 7.3), fringe=1.3, tactile=4.0,
              urticating=(0.3, 1.8), guard_per_mm2=0.6),
    # ---- the pattern as shares (plan §2.4 with the critic's ramps)
    pattern=dict(patella_flame=0.86, tibia_ramp=(0.59, 0.44, 0.15), metatarsus_ramp=(0.46, 0.25, 0.09),
                 carapace_border=0.2, carapace_border_fresh=0.08, patch_w=0.615, patch_low=0.25,
                 palp_tibia_band=0.35, palp_patella='pale orange-tan, not the flame',
                 # the knee (the sweep's item 6): the flame's width over the patella's; the pale margin each side of
                 # it; the two bare lengthwise lines: (their places across, A and B), (their run along), (their width)
                 flame_across=0.86, patella_pale_side=0.07,
                 patella_lines=((0.343, 0.617), (0.18, 0.715), 0.053),
                 # the carapace's dark disc, the default (i01's) look: (share of the carapace's length from its front
                 # edge, the disc's half-width there / CL); where it starts and ends along the midline
                 carapace_disc=((0.1, 0.099), (0.15, 0.157), (0.2, 0.223), (0.25, 0.231), (0.3, 0.273), (0.35, 0.301),
                                (0.4, 0.282), (0.45, 0.279), (0.5, 0.251), (0.55, 0.192)),
                 carapace_disc_ends=(0.044, 0.592)),
    # ---- colour, linear RGB, white-balanced on i01's paper (plan §2.5)
    colour=dict(black_pile=(0.034, 0.031, 0.040), flame=(0.633, 0.126, 0.043), tibia_pale=(0.713, 0.308, 0.140),
                metatarsus_pale=(0.499, 0.299, 0.206), carapace_border=(0.421, 0.146, 0.064),
                carapace_disc=(0.058, 0.040, 0.043), cheliceral_setae=(0.282, 0.161, 0.109),
                abdomen_pile=(0.110, 0.055, 0.050)),
    # ---- i01's stance, each pair's two sides (right mirrored), seen from the coxa joint: az = (knee azimuth lo, hi,
    # tip azimuth lo, hi); mid = the two sides' MEAN azimuths of (the knee, the tibia-metatarsus joint, the tip): the
    # bind stands on these; the tips (x, z)
    rest=dict(az=dict(I=(9.9, 26.1, 2.4, 37.7), II=(20.3, 33.1, 37.4, 37.4), III=(78.2, 97.8, 102.5, 103.3),
                      IV=(65.7, 156.5, 107.7, 167.6)),
              mid=dict(I=(18.0, 17.8, 20.1), II=(26.7, 37.2, 37.4), III=(88.0, 96.0, 102.9), IV=(111.1, 131.3, 137.7)),
              tips=dict(I=((6.2, 45.4), (42.2, 38.2)), II=((30.5, 19.7),), III=((58.0, -28.5), (52.1, -27.9)),
                        IV=((41.8, -31.6), (15.6, -78.7)))),
    # ---- the gait (plan §11.2): (duty, stride, step rate, speed); the phase by label L1 R1 L2 R2 L3 R3 L4 R4; center:
    # where in its stance each pair's foot stands under its rest place (the glb's motion.walk.center, by label)
    gait=dict(walk=(0.59, 40.3, 0.65, 26.4), skitter=(0.5, 44.0, 3.5, 154.0),
              phase=(0.42, 0.0, 0.0, 0.49, 0.44, 0.0, 0.94, 0.43), lift=2.9, f_min=0.5, coxa_range=2.5,
              center=dict(I=0.2, II=0.15, III=0.5, IV=0.5),
              # D4.1b: the WALK's stance place of a pair's foot from its rest place (dx outward, dz forward, mm; the
              # glb's motion.walk.place by label), and a pair's own swing lift (mm; motion.walk.liftBy by label)
              place=dict(II=(18.0, 3.0)), lift_by=dict(I=15.9),
              # D4.1b fix: a pair's lift on its re-placing step between its rest place and its walk place (mm; the glb's
              # motion.walk.liftPlace by label): the engine plants a walk place only while the animal walks
              lift_place=dict(II=15.9)),
    # ---- D4.1's design rows (families/arachnid.py): the bind is the WALKING STANCE
    rig=dict(
        ride=10.0, coxa_h=2.35, body_frac=0.5, pedicel=(-23.5, 4.0), opisthosoma_z=-25.0, abd_sag=1.0,
        femur_rise=dict(I=24.3, II=48.4, III=36.8, IV=47.7), az_pad=15.0, tm_bend=12.0, tarsus_h=1.4,
        chelicera=dict(x=2.6, z=-1.5, up=4.0),
        fang=dict(rest=10.0, base_xz=(2.42, 2.44), base_h=-0.5, back_xz=(-2.42, -6.44), back_h=-0.5),
        palp=dict(az=-15.0, femur_e=35.0, tarsus_bend=10.0, tip_h=1.0, coxa_h=1.5),
        spinneret=dict(pls=(1.75, 3.0, 0.3), pms=(0.7, 2.2, 0.8), pitch=15.0, splay=6.0),
        # the solver's four joints per leg: the yaw at the coxa, the lift at the trochanter (the lead's F4 call); the
        # knee the one hinge; the PLANTED joint the metatarsus-tarsus joint (D4.1 on the stick figure: the plan's
        # metatarsus drove the tibia-metatarsus joint straight)
        ik=dict(coxa='coxa', femur='trochanter', tibia='patella', tarsus='tarsus', hinge2='metatarsus'),
        # D4.1b, THE SECOND HINGE (the lead's call 11-11 (a), families/arachnid.py TarsusLeg.solve2): the tibia-
        # metatarsus joint shares the reach; per pair the femur's band (deg above level, knob to knee), the hinge's
        # included range and the knee's included range the solver holds (the walking animal's, L7)
        hinge2=dict(band=dict(I=(22.2, 70.0), II=(24.0, 70.0), III=(25.3, 70.0), IV=(21.3, 70.0)),
                    range=dict(I=(138.0, 175.0), II=(140.0, 175.0), III=(60.0, 175.0), IV=(60.0, 175.0)),
                    knee=dict(I=(74.0, 132.0), II=(98.0, 146.0), III=(85.0, 126.0), IV=(92.0, 142.0))),
        # limits per skeleton joint, AS DRIVEN (plan §10.3 re-derived at D4.1 from the walk on the stick figure)
        ranges=dict(coxa=(-2.5, 2.5), trochanter=(-20.0, 80.0), trochanter_swing=(-60.0, 128.0),
                    femur=(-10.0, 10.0), patella=(40.0, 170.0), tibia=(-15.0, 15.0), metatarsus=(60.0, 175.0),
                    tarsus=(-85.0, 25.0), tarsus_side=(-10.0, 10.0),
                    chelicera_lift=(0.0, 25.0), chelicera_spread=(-8.0, 8.0), fang=(0.0, 90.0),
                    pedicel_pitch=(-25.0, 35.0), pedicel_yaw=(-15.0, 15.0), pedicel_roll=(-10.0, 10.0),
                    spinneret=(-30.0, 30.0)),
        # the poses over the bind
        crouch=dict(clear=1.0),
        threat=dict(rear=55.0, lift=(20.0, 5.0), knee=150.0, palp_lift=40.0, chelicera=20.0, fang=70.0, pedicel=-25.0),
        kick=dict(pedicel=-10.0, stroke=((0.86, 0.45), (0.95, 0.1)))),
)

ZONES = dict(primary='1 - masks.r', soft='masks.r', setae='masks.g', accent='masks.b', pattern='masks.a')
LEGS = ('I', 'II', 'III', 'IV')
SEGS = ('coxa', 'trochanter', 'femur', 'patella', 'tibia', 'metatarsus', 'tarsus')
PALP_SEGS = ('coxa', 'trochanter', 'femur', 'patella', 'tibia', 'tarsus')

_L1 = 'L1\'s five congener females\' mean / CL x 24 (plan_numbers.json genus.F)'
_C37 = ('c37\'s underside at 14.26 px / mm (the sternum\'s and the labium\'s widths against L1\'s, 2 % apart): '
        'd40b_c37_coxae.json')

TAGS = {
    'family': ('[H]', 'remix/recipe.py FAMILIES: one cuticle material, one step solver'),
    'body_plan': ('[D]', 'arachnid: eight legs, a pedicel, chelicerae with fangs, palps (plan §5.1)'),
    'author_scale': ('[D]', 'x8: the thinnest leg segment lands at 21 mm, where the forge\'s constants were proven '
                            '(plan §5.6)'),
    'sex': ('[D]', 'T1 is the adult female (plan §0.1)'),
    'species': ('[D]', 'B. hamorii holds (TARANTULA_BODY_PHOTOS: the species check)'),
    # ---- photos
    'photos.c37.sternum': ('[P c37]', '(length as seen, width): its rear tip lies under the coxae IV\'s hair, so the '
                                      'length reads short of L1\'s 10.66'),
    'photos.c37.labium': ('[P c37]', '(length, width) at the body\'s scale: L1 gives 2.88 x 3.83'),
    'photos.c37.fang': ('[P c37]', 'the folded fang\'s chord at the sternum\'s scale, both sides (102.5, 101.8 px)'),
    'photos.c37.abdomen': ('[P c37]', '(length, width) from below; up to 10 % large where it bulges toward the glass'),
    'photos.c37.abd_front_z': ('[P c37]', 'the abdomen\'s front: it tucks 1.2 mm under the carapace\'s rear edge'),
    'photos.c37.furrow': ('[P c37]', 'the epigastric furrow behind the abdomen\'s front'),
    'photos.c37.pad': ('[P c37]', 'the metatarsus\'s dark pad, share from its far end, legs II, III, IV (IV the two '
                                  'sides\' mean): what is PRESSED on the glass, a lower bound on the scopula'),
    'photos.i01.dense.patella': ('[P i01]', 'd40b_i01_widths.py: cuticle + velvet + lying setae, median of 7 legs'),
    'photos.i01.dense.tibia': ('[P i01]', 'as the patella\'s'),
    'photos.i01.dense.metatarsus': ('[P i01]', 'as the patella\'s'),
    'photos.i01.dense.tarsus': ('[P i01]', 'as the patella\'s: the tarsus is NOT thinner than the metatarsus'),
    'photos.i01.height.r1': ('[P i01]', 'leg I right, from seen / true lengths: (tibia-metatarsus joint, knee, the '
                                        'femur\'s base) above the ground, the tarsus flat'),
    'photos.i01.height.r4': ('[P i01]', 'leg IV right, as r1'),
    'photos.i01.mt_slope': ('[P i01]', 'the metatarsus\'s slope on the three legs that stand on a flat tarsus (I R, '
                                       'IV R, III L)'),
    'photos.i01.femur_rise': ('[P i01]', 'the eight femora\'s rise, l1 r1 l2 r2 l3 r3 l4 r4: seen / true length from '
                                         'c37\'s femur base to i01\'s knee (two animals laid together: +-10 deg); the '
                                         'three legs standing on a flat tarsus are r1, l3, r4'),
    'photos.i01.chel_ahead': ('[P i01]', 'the chelicerae\'s front ahead of the carapace\'s, / CL (src_i01.json)'),
    'photos.i01.tubercle_w': ('[P i01]', 'the eye tubercle\'s width / CL as the dark bump shows: 24 % under L1\'s '
                                         '0.111, which eyes.tubercle takes (a microscope measure, 5 animals)'),
    'photos.i01.palp_girth': ('[P i01]', 'the palp\'s girth over leg I\'s, by hand: patella 3.1-3.5 against 5.2 mm, '
                                         'femur 4.2 against 6.3-7.0'),
    'photos.i01.envelope': ('[P i01]', 'the setae\'s outline: carapace width / length, abdomen length and width / '
                                       'CL, tibia envelope / core (plan §2.3\'s checks)'),
    'photos.i04.palp_tibia_band': ('[P i04]', 'the palp tibia\'s pale far band, share of its length (+-0.1)'),
    'photos.c15.guard_per_mm2': ('[P c15]', '12 standing guard setae on a 4.2 x 4.9 mm face of a metatarsus; 0.4-0.9 '
                                            'with the scale\'s doubt'),
    'photos.c15.guard_len': ('[P c15]', 'their lengths'),
    'photos.c15.guard_lie': ('[P c15]', 'their angle off the surface, toward the tip'),
    # ---- the sweep's items 6 and 7 (11-11): d40b_item6_pattern.json, d40b_setae_edges.json
    'photos.i01.flame_mm': ('[P i01]', 'the flame\'s width across the patella, the median of seven patellae (3.4-4.6 mm '
                                       'at 14.4 px / mm); leg III left is left out: its flame blob joined the tibia\'s '
                                       'orange (d40b_item6_pattern.json)'),
    'photos.i01.flame_across': ('[P i01]', 'photos.i01.flame_mm over photos.i01.dense.patella'),
    'photos.c38.flame_across': ('[P c38]', 'the flame\'s width over the patella\'s warm band, the median of seven '
                                           'patellae seen face-on (0.77-0.88); flame = orange of saturation 0.5 or '
                                           'more: the middle of the ramp from the red to the cream'),
    'photos.c38.far_rim': ('[P c38]', 'the pale rim at the patella\'s far end, share of the band\'s length (0.15-0.27); '
                                      'i01 reads 0.12-0.14 (pattern.patella_flame)'),
    'photos.c38.pale_side': ('[P c38]', 'the pale margin beside the flame, each side, share of the band\'s width'),
    'photos.c13.guard_per_mm_edge': ('[P c13]', 'lit guard setae crossing a line 0.6-1.5 mm outside the pile, per mm of '
                                                'edge: (the tibia, the patella) of one leg at 40 px / mm +-20 %: 1.2-2.4 '
                                                'with the scale\'s doubt, a LOWER bound where setae are out of focus. '
                                                'c15\'s 0.6 per mm2 over a standing band about 3 mm deep gives 1.8: they '
                                                'agree'),
    'photos.c14.tibia_line': ('[P c14]', 'the tibia\'s bare lengthwise line on two legs seen from the front: (from, to) '
                                         'of the tibia\'s BLACK part (it ends where the pale band begins), its width '
                                         'over the tibia\'s (8-10 of 170-190 px). ONE line shows a leg; its place across '
                                         'and the second line cannot be measured in the sweep (c13\'s tibia shows none '
                                         'under its lying setae): D4.9 carries the patella\'s two places [E]'),
    'photos.v01.period': ('[P v01]', 'a front leg reaches forward every 1.85 +-0.25 s (0.54 steps a second)'),
    'photos.v01.lag_I': ('[P v01]', 'the two front legs this share of a cycle apart (L4: 0.42 +-0.15)'),
    # ---- body
    'body.CL': ('[D from C]', 'between 22.5 (from the species\' body length) and 24.9 (from its leg IV); L2 compiled'),
    'body.CW': ('[L1]', _L1),
    'body.abd_len': ('[D]', 'THE LEAD\'S CALL (F11): 29-30 mm, a well-fed female; c37\'s abdomen reads 28.8'),
    'body.body_len': ('[D-d40]', 'CL + abd_len: inside B. hamorii\'s own 52-54 mm (L2, compiled); the genus\'s spread '
                               '(2.28-2.57 CL) is other species\''),
    'body.abd_W': ('[P c37]', '19.1 from below; i01\'s envelope less its setae gave 19.2'),
    'body.abd_H': ('[E]', '0.72 CL; no side view in the sweep: gate D4.2\'s clay beside c19 / i06'),
    'body.abd_front_z': ('[P c37]', 'photos.c37.abd_front_z'),
    'body.pedicel_r': ('[E]', '0.10 CL; hidden in every photo: gate D4.2'),
    'body.sternum': ('[L1]', '(length, width): ' + _L1),
    'body.labium': ('[L1]', '(length, width): ' + _L1),
    'body.fovea_w': ('[L1]', _L1),
    'body.fovea_z': ('[E from L4]', '0.64 CL behind the front (L4\'s male: 10.29 of 16.1 mm); c37\'s sternum is '
                                    'centred there'),
    'body.height': ('[E]', 'the sternum\'s plane to the caput\'s top, 0.40 CL: NO side view in the sweep can be '
                           'measured (build_NOTES B7): gate D4.2\'s clay beside c19 / i04 / i06'),
    'body.edge_h': ('[E]', 'the carapace\'s rim above the sternum\'s plane; gate D4.2'),
    'body.front_h': ('[E]', 'the carapace\'s front edge above the sternum\'s plane; gate D4.2'),
    'body.rear_h': ('[E]', 'the carapace\'s rear edge above the sternum\'s plane; gate D4.2'),
    'body.fovea_dip': ('[E]', 'the fovea below the caput\'s top; gate D4.2'),
    'eyes.tubercle': ('[L1]', '(width, length): ' + _L1),
    'eyes.tubercle_z': ('[P i01]', 'its centre 0.066 CL behind the front edge'),
    'eyes.AME': ('[L1]', _L1), 'eyes.ALE': ('[L1]', _L1), 'eyes.PME': ('[L1]', _L1), 'eyes.PLE': ('[L1]', _L1),
    'eyes.gap': ('[L1]', 'AME-AME, AME-ALE, PME-PME, PME-PLE, ALE-PLE: ' + _L1 + '; the arrangement is the textbook\'s, '
                         'seen as glints on i04 at 10x (no positions measured)'),
    'chelicera.L': ('[E]', '0.42 CL from c101 and c37; gate D4.2'),
    'chelicera.W': ('[E]', '0.195 CL each; c37 shows the pair 10.7 wide with its setae'),
    'chelicera.ahead': ('[P i01]', 'photos.i01.chel_ahead x CL: what shows from above'),
    'chelicera.fang': ('[P c37]', 'photos.c37.fang / 1.045: the chelicerae hang about 4 mm nearer the glass than the '
                                  'sternum (camera 88 mm) [E]; the plan had 6.5, c101 "0.42 of the chelicera" (a fang '
                                  'hanging open, seen end-on)'),
    'chelicera.pair_w': ('[P c37]', 'the two chelicerae from below with their setae, / 1.045 as the fang'),
    'chelicera.teeth': ('[C]', 'furrow teeth; sculpted (plan §5.5)'),
    'spinnerets.PLS': ('[L1]', 'three segments: ' + _L1),
    'spinnerets.PMS': ('[L1]', _L1),
    # ---- legs
    **{f'legs.{R}.{s}': ('[L1]', _L1) for R in ('I', 'II', 'III', 'IV')
       for s in ('femur', 'patella', 'tibia', 'metatarsus', 'tarsus')},
    **{f'legs.{R}.coxa': ('[P c37]', 'its joint on the sternum\'s margin to the knob less half a knob: ' + _C37
                                     + '; the plan\'s estimates were 17-46 % shorter')
       for R in ('I', 'II', 'III', 'IV')},
    'legs.trochanter': ('[P c37]', 'a knob\'s length along the leg (46 px on leg II); the plan had 2.6'),
    **{f'legs.coxae.{R}': ('[P c37, i01]', '(x, z, azimuth): ' + _C37 + '; z from the carapace front, put 0.191 CL '
                                           'behind the chelicerae\'s front (i01), +-0.045 CL [E]')
       for R in ('I', 'II', 'III', 'IV')},
    'legs.diam.coxa': ('[E from P c37]', 'four coxae a side share the sternum\'s rim: about 4.7 mm each at mid-length'),
    'legs.diam.trochanter': ('[P c37]', 'a knob across'),
    'legs.diam.femur': ('[E from P i01]', 'i01\'s femur envelope 5.9 less its pile; gate D4.2'),
    'legs.diam.patella': ('[P i01]', 'photos.i01.dense less 0.9 mm of pile [E]'),
    'legs.diam.tibia': ('[P i01]', 'photos.i01.dense less 0.9 mm of pile [E]'),
    'legs.diam.metatarsus': ('[P i01]', 'photos.i01.dense less 0.9 mm of pile [E]'),
    'legs.diam.tarsus': ('[P i01]', 'photos.i01.dense less 0.9 mm of pile [E]: its pad spreads it'),
    **{f'legs.pair_girth.{R}': ('[P i01]', 'the pair\'s girth over leg I\'s: the tibiae read 4.6 / 4.5 / 4.65 / 4.86 '
                                           '(+-0.5): only leg IV stands out')
       for R in ('I', 'II', 'III', 'IV')},
    **{f'legs.scopula_share.{R}': ('[L1]', 'the metatarsus\'s foot pad, share from its far end (females of B. boehmei '
                                           'and B. emilia); c37 reads III 0.55 and IV 0.38 (photos.c37.pad)')
       for R in ('I', 'II', 'III', 'IV')},
    'legs.spines_mt.I': ('[L1]', 'ventral spines on the metatarsus, leg I'),
    'legs.spines_mt.IV': ('[L1]', 'ventral spines on the metatarsus, leg IV: c37 shows it bristly underneath'),
    'legs.claws': ('[C]', 'two tarsal claws and a claw tuft'),
    'legs.claw': ('[E]', 'a claw\'s length, hidden in its tuft; gate D4.4'),
    'palp.coxa': ('[P c37]', 'the maxilla\'s near end to the palp\'s knob less half a knob'),
    'palp.trochanter': ('[E from P c37]', 'its knob reads as large as a leg\'s; +-0.5'),
    'palp.femur': ('[L1]', _L1), 'palp.patella': ('[L1]', _L1), 'palp.tibia': ('[L1]', _L1),
    'palp.tarsus': ('[L1]', _L1),
    'palp.coxae': ('[P c37, i01]', '(x, z, azimuth) of the maxilla, as legs.coxae'),
    'palp.maxilla': ('[P c37]', 'the lobe (length, width)'),
    'palp.girth': ('[P i01]', 'photos.i01.palp_girth: the palp\'s diameters are legs.diam x this (the plan\'s script '
                              'had 0.72)'),
    'palp.claws': ('[C]', 'one claw'),
    # ---- coat, pattern, colour
    'coat.velvet': ('[P i01]', 'no gap shows cuticle at 14 px / mm: under 0.6'),
    'coat.band': ('[P i01]', 'band setae'), 'coat.guard_reach': ('[P i01]', 'past the tibia\'s core'),
    'coat.abd_long': ('[P i01]', 'abdominal long setae'), 'coat.fringe': ('[P i01]', 'past the carapace\'s margin'),
    'coat.tactile': ('[L3]', 'tactile setae'), 'coat.urticating': ('[L3]', 'type III'),
    'coat.guard_per_mm2': ('[P c15]', 'photos.c15: the plan\'s guard strips (1 per 6 mm2 x 3 strands) match it'),
    'pattern.patella_flame': ('[P i01]', 'share of the patella\'s length'),
    'pattern.tibia_ramp': ('[P i01]', 'the pale band, shares from the far joint (start, half, full): the critic\'s'),
    'pattern.metatarsus_ramp': ('[P i01]', 'as the tibia\'s'),
    'pattern.carapace_border': ('[P i01]', 'share of the width a side'),
    'pattern.carapace_border_fresh': ('[P c38]', 'a fresh moult'),
    'pattern.patch_w': ('[P c41]', 'share of the abdomen\'s width'),
    'pattern.patch_low': ('[P c41]', 'its lower edge above the spinnerets, share of the width'),
    'pattern.palp_tibia_band': ('[P i04]', 'photos.i04'),
    'pattern.palp_patella': ('[P i01, i04]', 'the critic\'s F1'),
    'pattern.flame_across': ('[P c38, i01]', 'the flame\'s width over the patella\'s dense width: the mean of '
                                             'photos.c38.flame_across and photos.i01.flame_across (two photos, two '
                                             'animals, 0.03 apart)'),
    'pattern.patella_pale_side': ('[P c38]', 'photos.c38.pale_side: the pale margin each side of the flame'),
    'pattern.patella_lines': ('[P c38]', 'THE TWO BARE LENGTHWISE LINES: (their places across the band, 0 = one edge: A, '
                                         'B), (their run along it from the knee), (a line\'s width over the band\'s). '
                                         'Read by eye on the five patellae that show both, rings checked on the strips '
                                         '(+-0.04): A 0.30-0.37, B 0.57-0.64, 0.22 apart at the knee and 0.25 at the far '
                                         'end. c13 and c14 show the same two lines, aslant'),
    'pattern.carapace_disc': ('[P i01]', 'the dark disc\'s half-width / CL at stations along the carapace, the two '
                                         'sides\' mean (the animal\'s left reads up to 0.14 wider: it is rolled toward '
                                         'the lens). Dark against tan at the middle value between the disc\'s own dark '
                                         'and the rear border\'s tan. Its widest is 0.59 of the carapace\'s width: the '
                                         'border 0.21 a side, as pattern.carapace_border. Two orange wedges enter it '
                                         'from the front, each side of the midline (holes, not outline)'),
    'pattern.carapace_disc_ends': ('[P i01]', 'where the disc starts and ends along the midline, / CL: from the eye '
                                              'tubercle to the fovea (body.fovea_z is 0.64 CL back): the rear 0.4 of the '
                                              'carapace is orange-tan'),
    **{f'colour.{k}': ('[P i01]', 'tcolour box median, white-balanced on the paper (plan §2.5)')
       for k in ('black_pile', 'flame', 'tibia_pale', 'metatarsus_pale', 'carapace_border', 'carapace_disc',
                 'cheliceral_setae', 'abdomen_pile')},
    # ---- rest, gait
    **{f'rest.az.{R}': ('[P i01]', 'd40b_i01_legs.json: the pair\'s two sides; they stand differently (a standing or '
                                   'turning animal, one front leg out as a feeler)')
       for R in ('I', 'II', 'III', 'IV')},
    **{f'rest.mid.{R}': ('[P i01]', 'd40b_i01_legs.json: the two sides\' mean azimuths of (the knee, the tibia-'
                                    'metatarsus joint, the tip) seen from the coxa joint: the SYMMETRIC stance between '
                                    'the photo\'s two sides; the bind stands on it. (First read as "two phases half a '
                                    'cycle apart, so the mean is the mid-stance": but i01\'s front feet stand 36 mm '
                                    'apart sideways and 7 fore-aft, which no straight walk does)')
       for R in ('I', 'II', 'III', 'IV')},
    **{f'rest.tips.{R}': ('[P i01]', 'the tarsi\'s ends (x, z), the right side mirrored')
       for R in ('I', 'II', 'III', 'IV')},
    'gait.walk': ('[L4]', '(duty, stride, rate, speed): L4\'s male scaled by leg length, k 1.228 (plan §11.2); v01 '
                          'agrees on the rate'),
    'gait.skitter': ('[D-d41]', '(duty, stride, rate, speed): THE STRIDE CAME DOWN (the lead\'s F13 call), and THE LEAD\'S '
                                'CALL 11-11 (b): 44 mm, 154 mm/s at 3.5 steps a second. A gait that must carry terrain '
                                'and turning does not stand on its edge: the largest stride the one-hinge solver kept '
                                'inside 40-170 at the scheduler\'s 0.59 was 46 (the knee 6.6 deg in hand, the knee 0.58 '
                                'mm over its base) against 44 (10.1, 2.15); 54 at duty 0.5. d4_01 checks 44 holds'),
    'gait.phase': ('[L4]', 'Table 5A\'s trot: L1 R1 L2 R2 L3 R3 L4 R4'),
    'gait.lift': ('[E]', '0.05 of leg I'), 'gait.f_min': ('[L4]', 'the slow walk\'s rate; v01 0.54'),
    'gait.coxa_range': ('[D-d41]', 'the body-coxa joint\'s yaw clamp (the scheduler\'s one coxaRange), FROM ITS '
                                   'NEIGHBOURS: adjacent coxae step in antiphase; their far ends stand 2.26 mm apart at '
                                   'rest, 1.46 at +-2.5 deg, 0.66 at 5, touching at 7.5 (bar 0.9 mm: their two piles). '
                                   'The stride needs 12-17 deg of swing a leg: the rest is the coxa-trochanter joint\'s, '
                                   'by the solver\'s aim (d4_01). The plan had +-15, the solver\'s default is 35'),
    **{f'gait.center.{R}': ('[D-d41]', 'the share of its stance at which the pair\'s foot stands under its WALK place '
                                       '(rest + gait.place; the scheduler\'s L.center): d4_01 takes the one nearest 0.5 '
                                       'that keeps the solver\'s miss 0 and 10 deg of the knee\'s range in hand through '
                                       'the walk (D4.1b: with the second hinge). Leg I is bound near its full reach (i01 '
                                       'has both of them forward) and pulls')
       for R in ('I', 'II', 'III', 'IV')},
    'gait.place.II': ('[D-d41 from L7, P c34]', 'THE WALK\'S STANCE PLACE of leg II, (dx outward, dz forward) mm from '
                                                'its rest place (the bind is a STANDING animal\'s leg II, drawn forward '
                                                'and folded: knee 79.5). L7\'s walking knee (98-146) and tibia-'
                                                'metatarsus joint (140-176) on this leg keep its foot 34.0-47.5 mm from '
                                                'its knob (d41b h4_l7_reach), so a walking leg II plants about 46-58 mm '
                                                'from the midline, square to the body: c34\'s walking leg II stands '
                                                'square at about 50. +18 out, +3 forward clears thighs I and II by 0.6 '
                                                'mm at 5.9 mm bars through the walk and the skitter (d4_01 gate 10b): THIS '
                                                'PLACE IS WHAT CURED THEIR CROSSING (one hinge with it: 0 % of the cycle '
                                                'crossed; the second hinge without it: 57 %; check_d41b K10). The rest pose '
                                                'is untouched (the lead\'s call 11-11 (a)), and the engine plants this '
                                                'place ONLY WHILE THE ANIMAL WALKS: standing leg II stands on the bind\'s '
                                                'place; after a stop it settles in two cycles, the second stepping leg II '
                                                'back in over leg I\'s base only once leg I stands (d41b fix, the check\'s F1)'),
    'gait.lift_by.I': ('[D-d41 from P v01]', 'leg I\'s own swing lift (mm): v01 carries the swinging front leg nearly '
                                             'straight at the height of the body\'s top (the checker\'s C6d): 15.9 mm '
                                             'puts the swinging joint there. The test passes gate 10b with it (thighs '
                                             'I / II +0.56 mm at 5.9 mm bars in the skitter; check_d41b K9). (D4.1b '
                                             'shipped 14 on a study harness\'s "+0.49, 0.01 short", which read those '
                                             'thighs 0.075 mm low: the fix round\'s F3.) The other pairs keep gait.lift'),
    'gait.lift_place.II': ('[D-d41 from P v01]', 'leg II\'s lift (mm) on its RE-PLACING step between the bind\'s place and '
                                                 'its walk place (the glb\'s motion.walk.liftPlace by label): unfolding out '
                                                 'from over leg I\'s base at a start, folding back after a stop. v01\'s '
                                                 'swinging front leg\'s height, the only swing height measured; at the '
                                                 'gait\'s 2.9 the coats of thighs I and II overlap 0.92 mm at a start, at '
                                                 '15.9 0.26 (d41b fix E5; the cuticles 1.15 mm apart)'),
    # ---- rig
    'rig.ride': ('[E from P i01]', 'the coxa joints above the ground: photos.i01.height\'s femur bases 11.0 and 7.8; '
                                   'L4\'s leggier male, scaled, would stand higher'),
    'rig.coxa_h': ('[E]', 'a coxa joint above the sternum\'s plane: half legs.diam.coxa'),
    'rig.body_frac': ('[D]', 'the body joint this share of body.height above the sternum\'s plane'),
    'rig.pedicel': ('[E]', '(z, height above the sternum\'s plane): under the carapace\'s rear edge; hidden in every '
                           'photo'),
    'rig.opisthosoma_z': ('[E]', 'the abdomen\'s joint: the pedicel is one short waist'),
    'rig.abd_sag': ('[E]', 'the abdomen\'s underside below the sternum\'s plane'),
    **{f'rig.femur_rise.{R}': ('[P i01]', 'trochanter + femur above level at the bind: the PAIR\'s two sides\' mean on '
                                          'i01 (photos.i01.femur_rise: I 29.2 / 19.3, II 53.9 / 42.9, III 28.6 / 44.9, IV '
                                          '42.2 / 53.1), folded by d40_fold_spec. One value for the eight legs (34, the '
                                          'run before) laid femora I and II, which run side by side 2 mm apart in plan, in '
                                          'one sheet: 0.19 mm through each other at the bind. On the pairs\' own rises '
                                          'they are STACKED as the photo has them (leg II\'s knee over leg I\'s base): 1.98 '
                                          'mm clear at the bind (d4_01)')
       for R in ('I', 'II', 'III', 'IV')},
    'rig.az_pad': ('[E]', 'a direction\'s doubt on i01: joints under band setae, an animal whose two sides stand '
                          'differently'),
    'rig.tm_bend': ('[D from P i01]', 'the tibia-metatarsus joint\'s bend at the bind: i01\'s flat-footed legs 9-16. '
                                      'The metatarsus then falls 39-42 deg (i01\'s three standing legs: 35-36, each at '
                                      'an end of its stance, stretched)'),
    'rig.tarsus_h': ('[E]', 'the metatarsus-tarsus joint above the ground: the tarsus\'s half-thickness with its pad'),
    'rig.chelicera.x': ('[E from P c37]', 'its joint from the midline: a quarter of chelicera.pair_w'),
    'rig.chelicera.z': ('[E]', 'its joint behind the front edge'),
    'rig.chelicera.up': ('[E]', 'its joint above the sternum\'s plane, under the carapace\'s front edge; no side view '
                                'in the sweep: gate D4.2'),
    'rig.fang.rest': ('[C]', 'folded, 10 degrees open (plan §10.3)'),
    'rig.fang.base_xz': ('[P c37]', 'the fang\'s joint (x, z), where the chelicera\'s bone ends: c37\'s fang base / '
                                    '1.045 (nearer the glass). The chelicera\'s SHELL (chelicera.L) runs past it'),
    'rig.fang.base_h': ('[E]', 'the fang\'s joint under the sternum\'s plane: the fang folds along the chelicera\'s '
                               'underside at the mouth\'s level; gate D4.2'),
    'rig.fang.back_xz': ('[P c37]', 'the folded fang\'s run in plan from its joint (x, z) / 1.045: its tip on the '
                                    'midline, before the labium'),
    'rig.fang.back_h': ('[E]', 'the folded fang\'s tip under its joint: with base_h it hangs rig.abd_sag under the '
                               'sternum\'s plane, so the crouch rests fangs and belly together'),
    'rig.palp.az': ('[D from P i01]', 'the palp\'s plane from its knob: its knees stand 21 and its tips 15 degrees '
                                      'inside forward on i01'),
    'rig.palp.femur_e': ('[D from P i01]', 'its femur\'s rise: seen / true 0.84 and 0.58'),
    'rig.palp.tarsus_bend': ('[D]', 'its tarsus past the tibia'),
    'rig.palp.tip_h': ('[D]', 'the palp\'s tip hovers: it is not a foot; the patella + tibia\'s fall is solved from '
                              'it (the knee\'s included angle comes out 106)'),
    'rig.palp.coxa_h': ('[E]', 'the maxilla\'s joint above the sternum\'s plane'),
    'rig.spinneret.pls': ('[P c37]', '(x, height above the sternum\'s plane [E], ahead of the abdomen\'s rear)'),
    'rig.spinneret.pms': ('[E]', 'as pls'), 'rig.spinneret.pitch': ('[E]', 'up from level'),
    'rig.spinneret.splay': ('[E]', 'out from straight back'),
    **{f'rig.ik.{k}': ('[D]', 'THE LEAD\'S CALL (F4): the leg yaws at the coxa and lifts at the coxa-trochanter joint; '
                              'the knee is the femur-patella hinge; the METATARSUS-TARSUS joint (tarsus_<n>) is the '
                              'planted one (D4.1 on the stick figure; the plan\'s first map planted the tibia-'
                              'metatarsus joint and drove it straight)')
       for k in ('coxa', 'femur', 'tibia', 'tarsus')},
    'rig.ik.hinge2': ('[D-d41]', 'the TIBIA-METATARSUS joint (metatarsus_<n>) is a second hinge of the step solver '
                                 '(families/arachnid.py TarsusLeg.solve2, the staged runtime tarsus2), the walking '
                                 'animal\'s (L7 measures that joint working 16-53 deg a cycle): it holds each knee inside '
                                 'L7\'s walking range in mid-stance and carries thighs III and IV over the 5.9 mm gate '
                                 '(+0.43 -> +0.71 mm). It did NOT cure the crossing of thighs I and II that the lead\'s call '
                                 '11-11 (a) named: gait.place.II did (check_d41b K10); femur I still swings 5-68 deg a '
                                 'cycle. Its rules are the walking animal\'s: a standing leg is the bind (d41b fix, F1)'),
    **{f'rig.hinge2.band.{R}': ('[D-d41]', 'the femur\'s band (knob to knee above level, deg) the second hinge holds, as '
                                           'a GUARD: from the rise at which the knee stands at the carapace\'s top '
                                           '(17.25 [E]; the walking animal\'s knees ride above its back: v01, c33-c35) '
                                           'to 70. NOT i01\'s two sides (a STANDING animal\'s): no walk can hold them '
                                           '(d41b h4_study4: leg I leaves them by 23-33 deg at the end of every stance); '
                                           'no free source measures a walking femur\'s rise (L7 marked no coxa or '
                                           'trochanter)')
       for R in ('I', 'II', 'III', 'IV')},
    **{f'rig.hinge2.range.{R}': (('[L7]', 'the tibia-metatarsus joint\'s included angle the hinge may use: L7 (Hao et al. '
                                          '2019, Table 3, hard ground) ' + ('147.6-165.7' if R == 'I' else '150.5-166.2')
                                  + ' widened 10 deg each way, the top held to rig.ranges.metatarsus\'s 175')
                                 if R in ('I', 'II') else
                                 ('[D-d41]', 'rig.ranges.metatarsus: L7\'s ' + ('90.5-143.4' if R == 'III' else '123.4-152.3')
                                  + ' lie under this bind\'s 165-167 (the stick figure\'s hind legs stand straighter at '
                                    'this joint than L7\'s animals walk: rig.tm_bend, gate D4.2)'))
       for R in ('I', 'II', 'III', 'IV')},
    **{f'rig.hinge2.knee.{R}': ('[L7]', 'the knee\'s (femur-patella) included angle the second hinge holds: L7\'s hard-'
                                        'ground extremes (I 83.5-121.5, II 108.3-135.5, III 95.3-116.4, IV 102.5-131.6) '
                                        'widened 10 deg each way (about one s.d. of its extremes), to the degree')
       for R in ('I', 'II', 'III', 'IV')},
    'rig.ranges.coxa': ('[D-d41]', 'yaw: gait.coxa_range, the clamp its neighbours leave it (d4_01). At the plan\'s '
                                   '+-15 adjacent coxae pass 1.7 mm through each other, at the solver\'s default 35, '
                                   '2.2. In the animal too the coxa-trochanter joint carries the swing'),
    'rig.ranges.trochanter': ('[D-d41]', 'lift: the femur\'s rise above level, AS DRIVEN: the bind stands at 24-48, '
                                         'the walk and the skitter use 10-64, the crouch 34-60, the threat up to 66 '
                                         '(d4_01); the plan\'s -20 / +50 was the animal\'s estimate'),
    'rig.ranges.trochanter_swing': ('[D-d41]', 'the femur forward of the coxa\'s axis, in plan (the coxa-trochanter '
                                               'joint\'s swing), AS DRIVEN: -8 to 104 over the walk, the skitter, the '
                                               'crouch and the threat (d4_01); the plan had +-35 about the bind. D4.1b: '
                                               'leg I reaches its femur forward to 127.6 in the skitter at 44 (its swing '
                                               'lifted v01\'s 15.9 mm, the second hinge free through the swing)'),
    'rig.ranges.femur': ('[C]', 'the trochanter-femur joint barely moves; not driven'),
    'rig.ranges.patella': ('[C]', 'the knee, included angle; extension is hydraulic: no further'),
    'rig.ranges.tibia': ('[C]', 'patella-tibia, sideways; not driven'),
    'rig.ranges.metatarsus': ('[C]', 'tibia-metatarsus, included angle'),
    'rig.ranges.tarsus': ('[D-d41 from P i01]', 'metatarsus-tarsus, from the metatarsus\'s line (+ curls ventrally), '
                                                'AS DRIVEN: the planted tarsus lies flat under a metatarsus that the '
                                                'solver stands up to 64 deg at the end of a front leg\'s stance: -16 to '
                                                '-65 over the walk, the skitter and the poses (d4_01), the bind -27 to '
                                                '-42. The plan\'s +-25 is the animal\'s: i01\'s standing legs read 22-27. '
                                                'The gap is the solver\'s rigid patella + tibia + metatarsus. D4.1b: -10 '
                                                'to -80 with the walk\'s stance places (legs II -80, IV -77, I -70): a '
                                                'planted tarsus keeps its heading while the leg rows round its knob, so '
                                                'the joint takes the twist (L7 measures leg IV\'s at 77-92 off straight, '
                                                'legs I-II\'s at 17-44: a look item for D4.11\'s foot)'),
    'rig.ranges.tarsus_side': ('[C]', 'sideways'),
    'rig.ranges.chelicera_lift': ('[E]', 'plan §10.3'), 'rig.ranges.chelicera_spread': ('[E]', 'plan §10.3'),
    'rig.ranges.fang': ('[C]', '0 folded to 90 struck'),
    'rig.ranges.pedicel_pitch': ('[E]', 'plan §10.3'), 'rig.ranges.pedicel_yaw': ('[E]', 'plan §10.3'),
    'rig.ranges.pedicel_roll': ('[E]', 'plan §10.3'), 'rig.ranges.spinneret': ('[E]', 'a segment'),
    'rig.crouch.clear': ('[D]', 'the rest pose: the sternum\'s plane this far off the ground, the belly down'),
    'rig.threat.rear': ('[C]', 'the prosoma reared (plan §11.3: 50-70)'),
    'rig.threat.lift': ('[D]', 'legs I and II raised: their femora\'s extra rise over the bind\'s (24.3 and 48.4), '
                               'on a prosoma reared 55: both femora stand near upright (99 and 108 from level)'),
    'rig.threat.knee': ('[D]', 'their knees opened to this'),
    'rig.threat.palp_lift': ('[D]', 'the palps raised'), 'rig.threat.chelicera': ('[D]', 'lifted'),
    'rig.threat.fang': ('[D]', 'out'),
    'rig.threat.pedicel': ('[D]', 'the waist bent to its range\'s end, the abdomen\'s rear UP against the prosoma (a '
                                  'negative turn: + dips the rear). The abdomen then points 30 down behind a prosoma '
                                  'reared 55 and rests its rear on the ground (the run before had +35: the abdomen '
                                  'pointed straight down, 27 mm under the ground)'),
    'rig.kick.pedicel': ('[D-d41]', 'the abdomen pitched up at the waist (a negative turn): THE REACH DECIDES HOW FAR. '
                                    'The hind tarsus\'s tip reaches the patch from 0.78 along and back with the abdomen '
                                    'level, from 0.85 and back pitched up 10; at 15 the stroke\'s end has 0.00 mm off '
                                    'the skin; at 25 (the first guess) the tip stops 5.9-9.7 mm short everywhere on the '
                                    'patch: a pitched abdomen lifts the patch over the knee\'s own height (29.6 mm with '
                                    'the femur upright) (d4_01)'),
    'rig.kick.stroke': ('[D-d41 from P c41]', 'the two ends of the hind tarsus\'s stroke on the abdomen\'s back, each '
                                              '(share of its length from the front, share of its half-width from the '
                                              'midline, toward the leg\'s own side): on the REAR part of c41\'s bald '
                                              'patch, which is where a leg this long can put its tip (families/'
                                              'arachnid.kick_pose). 4.6 mm of stroke, 6 deg of turn between the ends. '
                                              'NOT YET A BELIEVABLE KICK: inside the plan\'s joint ranges the leg stands '
                                              'as a tall hook (its tibia-metatarsus joint 48 mm up) and the metatarsus '
                                              'cannot be laid on the patch at all (0 of 155 starts): D4.11 with a kick '
                                              'film, and probably the abdomen yawed and rolled toward the leg'),
}

TAG_RE = re.compile(r'\[(P|L|H|D|E|C)(?:\d)?(?:-(?:pn|d40|d40b|d41))?(?:[ ,][^\]]*)?\]')
PHOTO_RE = re.compile(r'\b(c\d{2,3}b?|i0\d|v0\d)\b')

# The leaves' units (d4_00 checks every leaf has one; morph() scales the 'mm' leaves): the group's unit unless listed
UNIT_GROUP = dict(family='text', body_plan='text', author_scale='1', sex='text', species='text', photos='ratio',
                  body='mm', eyes='mm', chelicera='mm', spinnerets='mm', legs='mm', palp='mm', coat='mm',
                  pattern='frac', colour='linear', rest='deg', gait='mix', rig='mm')
UNIT_KEY = {
    'photos.c37.sternum': 'mm', 'photos.c37.labium': 'mm', 'photos.c37.fang': 'mm', 'photos.c37.abdomen': 'mm',
    'photos.c37.abd_front_z': 'mm', 'photos.c37.furrow': 'mm', 'photos.c37.pad': 'frac',
    **{f'photos.i01.dense.{s}': 'mm' for s in ('patella', 'tibia', 'metatarsus', 'tarsus')},
    'photos.i01.height.r1': 'mm', 'photos.i01.height.r4': 'mm', 'photos.i01.mt_slope': 'deg',
    'photos.i04.palp_tibia_band': 'frac', 'photos.c15.guard_per_mm2': 'per_mm2', 'photos.c15.guard_len': 'mm',
    'photos.c15.guard_lie': 'deg', 'photos.v01.period': 's', 'photos.v01.lag_I': 'frac',
    'photos.i01.flame_mm': 'mm', 'photos.c38.flame_across': 'frac', 'photos.c38.far_rim': 'frac',
    'photos.c38.pale_side': 'frac', 'photos.c13.guard_per_mm_edge': 'per_mm', 'photos.c14.tibia_line': 'frac',
    'chelicera.teeth': 'count', 'legs.claws': 'count', 'palp.claws': 'count', 'palp.girth': 'ratio',
    'legs.spines_mt.I': 'count', 'legs.spines_mt.IV': 'count',
    **{f'legs.pair_girth.{R}': 'ratio' for R in ('I', 'II', 'III', 'IV')},
    **{f'legs.scopula_share.{R}': 'frac' for R in ('I', 'II', 'III', 'IV')},
    **{f'legs.coxae.{R}': 'mm_mm_deg' for R in ('I', 'II', 'III', 'IV')}, 'palp.coxae': 'mm_mm_deg',
    'coat.guard_per_mm2': 'per_mm2', 'pattern.palp_patella': 'text',
    **{f'rest.tips.{R}': 'mm' for R in ('I', 'II', 'III', 'IV')},
    'rig.body_frac': 'frac', **{f'rig.femur_rise.{R}': 'deg' for R in ('I', 'II', 'III', 'IV')}, 'rig.az_pad': 'deg',
    'photos.i01.femur_rise': 'deg',
    **{f'gait.center.{R}': 'frac' for R in ('I', 'II', 'III', 'IV')},
    'gait.place.II': 'mm', 'gait.lift_by.I': 'mm', 'gait.lift_place.II': 'mm', 'rig.ik.hinge2': 'text',
    **{f'rig.hinge2.{k}.{R}': 'deg' for k in ('band', 'range', 'knee') for R in ('I', 'II', 'III', 'IV')},
    'rig.tm_bend': 'deg', 'rig.fang.rest': 'deg', 'rig.palp.az': 'deg',
    'rig.palp.femur_e': 'deg', 'rig.palp.tarsus_bend': 'deg', 'rig.spinneret.pitch': 'deg',
    'rig.spinneret.splay': 'deg', **{f'rig.ik.{k}': 'text' for k in ('coxa', 'femur', 'tibia', 'tarsus')},
    **{f'rig.ranges.{k}': 'deg' for k in SPEC['rig']['ranges']},
    'rig.threat.rear': 'deg', 'rig.threat.lift': 'deg', 'rig.threat.knee': 'deg', 'rig.threat.palp_lift': 'deg',
    'rig.threat.chelicera': 'deg', 'rig.threat.fang': 'deg', 'rig.threat.pedicel': 'deg', 'rig.kick.pedicel': 'deg',
    'rig.kick.stroke': 'frac',
}


def leaves(spec=None, prefix=''):
    """every SPEC value as (dotted key, value); a tuple is one value"""
    out = []
    for k, v in (SPEC if spec is None else spec).items():
        key = f'{prefix}{k}'
        if isinstance(v, dict):
            out += leaves(v, key + '.')
        else:
            out.append((key, v))
    return out


def untagged(spec=None, tags=None):
    """the keys whose value has no source tag in the plan's legend, and the tag keys that name no value"""
    tags = TAGS if tags is None else tags
    keys = [k for k, _ in leaves(spec)]
    missing = [k for k in keys if k not in tags or not TAG_RE.search(tags[k][0])]
    stale = sorted(set(tags) - set(keys))
    return missing, stale


def photoless(tags=None):
    """the keys with a [P] tag that names no photo id (the plan's rule: a photo reading carries its photo)"""
    tags = TAGS if tags is None else tags
    return sorted(k for k, (t, _) in tags.items() if re.search(r'\[P', t) and not PHOTO_RE.search(t))


def unit(key):
    """a leaf's unit: mm, deg, ratio, frac, count, linear, s, per_mm2, per_mm, mm_mm_deg, mix, 1 or text"""
    return UNIT_KEY.get(key, UNIT_GROUP[key.split('.')[0]])


def get(spec, key):
    """the value at a dotted key"""
    v = spec
    for k in key.split('.'):
        v = v[k]
    return v


def put(spec, key, value):
    ks = key.split('.')
    d = spec
    for k in ks[:-1]:
        d = d[k]
    if ks[-1] not in d:
        raise KeyError(key)
    d[ks[-1]] = value


def segments(spec, leg):
    """(coxa, trochanter, femur, patella, tibia, metatarsus, tarsus) of a leg 'I'..'IV', life mm"""
    L = spec['legs'][leg]
    return (L['coxa'], spec['legs']['trochanter'], L['femur'], L['patella'], L['tibia'], L['metatarsus'], L['tarsus'])


def palp_segments(spec):
    """(coxa, trochanter, femur, patella, tibia, tarsus) of the palp, life mm"""
    p = spec['palp']
    return (p['coxa'], p['trochanter'], p['femur'], p['patella'], p['tibia'], p['tarsus'])


# --------------------------------------------------------------------------------------------- the morphs (plan §2.7)
# Each morph: its CL (the length scale), then its rows (key: (value, tag, note)). morph() scales every 'mm' leaf outside
# photos by CL / 24, then sets the rows. Unmeasured shape stays the scaled female's.
MORPHS = dict(
    male=dict(
        what='the adult male: longer legs on a smaller carapace (L1\'s five males\' means x CL 22.2), a smaller '
             'abdomen; the tibial spurs and the palpal bulb are D4.14\'s unique shells',
        CL=22.2,
        set={
            'sex': ('male', '[D]', 'the male morph'),
            **{f'legs.{R}.{s}': (v, '[L1]', 'L1\'s five males\' mean / CL x 22.2 (plan_numbers.json genus.M)')
               for R, row in (('I', (19.298, 10.343, 14.754, 15.615, 10.514)),
                              ('II', (17.693, 10.108, 13.165, 14.221, 9.835)),
                              ('III', (16.244, 8.955, 12.232, 15.169, 9.582)),
                              ('IV', (19.287, 9.653, 15.413, 19.851, 10.862)))
               for s, v in zip(('femur', 'patella', 'tibia', 'metatarsus', 'tarsus'), row)},
            'body.CW': (21.325, '[L1]', 'the males\' 0.9606 CL'),
            'body.abd_len': (22.0, '[E]', 'the males\' body 2.146 CL less the carapace, x 0.86: gate a measured male'),
            'body.body_len': (44.2, '[D-d40]', 'CL + abd_len'),
        }),
    thin=dict(
        what='i01\'s thin wild animal: the abdomen the plan first drew (27.6 mm), before the lead\'s call',
        CL=24.0,
        set={
            'body.abd_len': (27.6, '[E from P i01]', 'i01\'s envelope 1.18 CL less its setae'),
            'body.body_len': (51.6, '[D-d40]', 'CL + abd_len: under the species\' own 52-54'),
        }),
    fresh=dict(
        what='a fresh moult (c38): a narrow pink border; the palette rows are D4.9\'s',
        CL=24.0,
        set={
            'pattern.carapace_border': (0.08, '[P c38]', 'the fresh moult\'s border'),
        }),
)


def morph(name):
    """(spec, tags): the morph's full SPEC and its tags (T1's, with the morph's rows retagged). name in MORPHS or 'T1'"""
    spec, tags = copy.deepcopy(SPEC), dict(TAGS)
    if name == 'T1':
        return spec, tags
    m = MORPHS[name]
    s = m['CL'] / SPEC['body']['CL']
    if s != 1.0:
        for key, v in leaves(SPEC):
            if unit(key) not in ('mm', 'mm_mm_deg') or key.split('.')[0] == 'photos':
                continue
            if unit(key) == 'mm_mm_deg':
                put(spec, key, (v[0] * s, v[1] * s, v[2]))
            elif isinstance(v, tuple) and v and isinstance(v[0], tuple):
                put(spec, key, tuple(tuple(x * s for x in row) for row in v))
            elif isinstance(v, tuple):
                put(spec, key, tuple(x * s for x in v))
            else:
                put(spec, key, v * s)
            tags[key] = ('[D-d40]', f'T1\'s x {s:.4f} (the morph\'s CL / T1\'s): ' + TAGS[key][1])
    for key, (v, tag, note) in m['set'].items():
        put(spec, key, v)
        tags[key] = (tag, note)
    return spec, tags
