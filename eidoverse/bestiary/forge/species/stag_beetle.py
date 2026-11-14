"""STAG BEETLE (Lucanus cervus, major male): the Bestiary's third realistic base and its first ARTHROPOD
(work/bestiary/research/BEETLE_PLAN.md). B1, the target specimen, is M1 = NHMUK013741609 (England: Surrey, Reigate,
24.vi.1958), the photo strand's major male photographed dorsally on a mm card and laterally against a mm ruler (two
scales 0.27 % apart): one coherent animal (plan §0.3, §2.1). Its borrowed rows are tagged where used: femur : tibia
spans and the coxa spacing (M3), antenna lengths (E1, M2), mandible arm width (ENT0588940), the rest pose (P1), colour
(the ETH males). The fore tarsus is M1's own longer projection since B3 (10-21); the borrowed M3 row is kept as
legs.fore.tarsus_claw_M3 for the record. B3c (10-21, the lead's stance order): each leg segment's length is the MAX
over its projections (M1d, M3v, M1l where it shows; the fore tarsus with its claw M3v's 11.208, the fore tibia M1l's
12.435), the meso- and metacoxae at their own heights (M3v), the standing height read on P2's side view, the tibiae at
P2's and P3's own image angles, P1's plan foot spread yielding last (rest.*, plan §2.7 B3c). B3d (the lead 10-22): P2
and P3 solved as PERSPECTIVE cameras, the height their consensus (rest.stand, 5.064 mm), the tibiae's elevations from
P2's reconstruction (plan §2.7 B3d).

UNITS: LIFE MILLIMETRES and degrees (plan §0, "Units and frame"). The generator (families/arthropod.py) multiplies
once by SPEC['author_scale'] = 10: B1 is built and exported at x10 (0.594 m) with extras.bestiary.life_scale = 0.1
(plan §4.3). THE PLAN FRAME: the clypeal tip at z 0, +z forward, +y up, +x the creature's LEFT (DESIGN.md); a
landmark (z, h) is z in the dorsal frame and h above the venter's lowest point on M1l (plan §2.3); every sided value is
the LEFT side's, the right is its mirror p_R = M p_L (limbed's rule), so every bilateral measure is reduced to ONE
value by a stated rule (the tibia and claw the longer side, tarsomeres the mean: plan §2.6; the mandible and the eye
axis the mean of the two sides: [D-b0] below).

SPEC sources: work/bestiary/research/beetle_work/plan/plan_numbers.json (keys B1, B1_legs, B1.coxaeB, B1_antenna,
rest_pose, landmarks_M1l, accessories.eyes, allometry: PLAN_JSON maps each leaf to its key) and the photo strand's
beetle_work/data/res_<id>.json (RES_JSON maps those). work/bestiary/tests/b00_spec.py checks every leaf against its
source. NOT B1_coxaeA (placement A, rejected, plan §2.7): the coxae are placement B (B1.coxaeB). The eye axis is the
head margin's outward normal 101.3 / 102.5 deg off forward (accessories.eyes.splay_deg as plan_numbers.py now prints
it, B0 10-21; it read 78.7 / 77.5 before, the sign error of plan §2.4).

TAGS holds every leaf's source in the plan's legend (plan "Tags"): [P] primary source, [C] compiled secondary source,
[R] reference asset (measured, never copied), [H] house rule or prior finding, [E] estimate with the gate that verifies
it, [S] seen only in a search summary, [M] measured on a photo with a known scale or as a ratio inside one photo, [D]
derived by a script. [M] and [D] carry their maker: -ph the photo strand (bmeasure.py, bderive.py), -an the anatomy
strand (anat_*.py), -fo the forge strand (forge_*.py), -pl the plan (plan_numbers.py), -b0 derived HERE by the rule
in its note (b00_spec.py recomputes each), -b3 B3's outline rows (research/beetle_scripts/b3_outlines.py: M1's own
traced silhouettes resampled into the plan frame; b00_spec.py recomputes each). TAG_RE is this species' own (wolf.py's
lacks M and the makers).

MORPHS (plan §2.8, B12): the minor (S1's ratios on the ETH minor's EL, the minor branch's mandible), the female (F1, a
SPEC variant with her own head, pronotum and mandibles: sex, not size, sets her shape, plan §0.2) and E1 (B1's body
with the large-weapon head and mandible row, x1.231 at B1's EL). morph(name) composes each from SPEC.
ALLOMETRY (plan §2.8): Romiti 2017's segmented ML on EL, re-anchored through B1 (major) and the ETH minor; morphs key
on EL, never on Hardersen's PW (his scale does not match ours).
"""
import copy
import re

AUTHOR_SCALE = 10.0

SPEC = dict(
    family='arthropod', head_archetype='insect', author_scale=AUTHOR_SCALE,
    # ---- M1d, the dorsal photo (card 64.527 px/mm): plan §2.2
    body=dict(TL=59.404, BL=43.587, BLc=42.563, HL=9.671, HLc=8.647, HW=17.627, HW_ant=16.737, HW_post=15.884,
              PL=8.336, PW=15.651, PW_front=13.776, PW_back=14.598, pron_widest=5.351, EL=25.239, EL_sut=22.853,
              EW=18.617, EW_hum=16.787, ely_widest=8.926, scut=2.386, waist=0.341, ely_plate=0.27),
    # ---- M1l, the lateral photo (ruler 76.985 px/mm): plan §2.3
    lateral=dict(TL=59.244, EL_h=24.903, EL_chord=25.524, ely_chord_pitch=12.664, depth=12.766, ely_top_pos=7.690,
                 ely_top_above_base=1.174, ely_side_h=6.939, venter_below_margin=5.827, apex_below_top=6.769,
                 pron_depth=11.545, PL=8.559, pron_front_above_back=1.861, HL=8.043, head_h_eye=6.722,
                 crest_above_head_top=1.557, crest_above_ely_top=3.260),
    # ---- M1l's landmarks in the plan frame: (z, h above the venter), plan §2.3's table
    landmarks=dict(frons_top=(-2.081, 15.289), head_crest=(-8.653, 16.027), head_top_eye=(-4.115, 14.470),
                   head_under_eye=(-5.019, 7.748), eye_c=(-4.095, 11.456), mand_base_dors=(-1.100, 14.178),
                   mand_base_vent=(0.631, 9.838), mand_tip=(15.658, 5.945), pron_mid_top=(-14.278, 13.246),
                   pron_back_top=(-18.426, 11.893), procoxa_low=(-15.825, 1.701), ely_base_top=(-18.684, 11.593),
                   ely_top=(-26.374, 12.766), ely_marg_top=(-26.140, 5.827), ely_apex=(-43.587, 5.997),
                   venter=(-25.387, 0.000)),
    # ---- outline profiles, width / maximum at fractions of the length from the front: plan §2.2
    profiles=dict(
        elytra=((0.02, 0.903), (0.20, 0.979), (0.25, 0.996), (0.30, 1.000), (0.35, 0.996), (0.40, 0.993),
                (0.45, 0.986), (0.50, 0.973), (0.75, 0.823), (0.80, 0.761), (0.85, 0.685), (0.90, 0.577),
                (0.95, 0.410), (0.98, 0.111)),
        pronotum=((0.02, 0.936), (0.10, 0.884), (0.20, 0.891), (0.30, 0.917), (0.40, 0.960), (0.50, 0.981),
                  (0.60, 1.000), (0.70, 0.980), (0.80, 0.944), (0.90, 0.914), (0.97, 0.751))),
    # ---- B3's outline rows: M1's own traced silhouettes in the plan frame (research/beetle_scripts/b3_outlines.py)
    outline=dict(
        head_half=((-0.75, 8.345, -0.2775), (-1.0, 8.5275, -0.155), (-1.5, 8.74, -0.1275), (-2.0, 8.755, -0.0275),
                   (-2.5, 8.5875, -0.025), (-3.0, 8.395, -0.0625), (-3.5, 8.52, -0.1725), (-4.0, 8.5475, -0.07),
                   (-4.5, 8.3825, -0.075), (-5.0, 8.1225, -0.06)),
        pron_half=((-11.0, 6.93, -0.3875), (-11.5, 7.005, -0.4675), (-12.0, 7.0525, -0.58), (-12.5, 7.2175, -0.6),
                   (-13.0, 7.4475, -0.495), (-13.5, 7.5925, -0.48), (-14.0, 7.675, -0.4925), (-14.5, 7.7825, -0.51),
                   (-15.0, 7.7825, -0.425), (-15.5, 7.69, -0.3675), (-16.0, 7.52, -0.3475), (-16.5, 7.37, -0.3375),
                   (-17.0, 7.215, -0.3025), (-17.5, 6.5875, 0.07)),
        pron_profile_z=(-9.9804, 8.0276),
        pron_keel=((-17.764, 9.975), (-16.718, 8.969), (-15.412, 8.016), (-14.110, 7.427), (-13.135, 7.317),
                   (-12.167, 8.285), (-10.877, 9.605), (-9.585, 10.705)),
        dorsal_line=((-2.0, 15.3306), (-2.5, 15.1225), (-3.0, 15.0931), (-3.5, 14.7832), (-4.0, 14.4734),
                     (-4.5, 14.4959), (-5.0, 14.5442), (-5.5, 14.5917), (-6.0, 14.5885), (-6.5, 14.6354),
                     (-7.0, 14.8619), (-7.5, 15.1146), (-8.0, 15.6984), (-8.5, 15.9756), (-9.0, 15.5519),
                     (-9.5, 13.8885), (-10.0, 13.7449), (-10.5, 13.7415), (-11.0, 13.5835), (-11.5, 13.479),
                     (-12.0, 13.4496), (-12.5, 13.2931), (-13.0, 13.2385), (-13.5, 13.2862), (-14.0, 13.283),
                     (-14.5, 13.2286), (-15.0, 13.1737), (-15.5, 13.069), (-16.0, 12.9632), (-16.5, 12.7805),
                     (-17.0, 12.5991), (-17.5, 12.366), (-18.0, 12.0301), (-18.5, 11.924), (-19.0, 11.5636),
                     (-19.5, 11.7651), (-20.0, 12.0032), (-20.5, 12.1923), (-21.0, 12.3668), (-21.5, 12.4925),
                     (-22.0, 12.6161), (-22.5, 12.6638), (-23.0, 12.7124), (-23.5, 12.7335), (-24.0, 12.7304),
                     (-24.5, 12.6765), (-25.0, 12.7238), (-25.5, 12.6958), (-26.0, 12.7171), (-26.5, 12.7658),
                     (-27.0, 12.6338), (-27.5, 12.5031), (-28.0, 12.4233), (-28.5, 12.3172), (-29.0, 12.2374),
                     (-29.5, 12.1326), (-30.0, 12.0266), (-30.5, 11.8961), (-31.0, 11.7901), (-31.5, 11.6465),
                     (-32.0, 11.5028), (-32.5, 11.3721), (-33.0, 11.2403), (-33.5, 11.0967), (-34.0, 10.966),
                     (-34.5, 10.8224), (-35.0, 10.6775), (-35.5, 10.5092), (-36.0, 10.3265), (-36.5, 10.1063),
                     (-37.0, 9.8848), (-37.5, 9.6398), (-38.0, 9.3805), (-38.5, 9.1083), (-39.0, 8.8115),
                     (-39.5, 8.4899), (-40.0, 8.128), (-40.5, 7.7545), (-41.0, 7.355), (-41.5, 7.097),
                     (-42.0, 6.7481), (-42.5, 6.5526), (-43.0, 6.3452), (-43.5, 6.1119), (-43.587, 6.0607)),
        ely_margin=((-18.7422, 6.7211), (-23.1149, 5.9905), (-26.1405, 5.8274), (-30.049, 5.6065),
                    (-36.9715, 5.4434), (-42.9745, 5.7021)),
        mand_outer=((0.0, 0.00066), (0.05, 0.04389), (0.1, 0.08413), (0.15, 0.11671), (0.2, 0.14257),
                    (0.25, 0.16369), (0.3, 0.18004), (0.35, 0.19272), (0.4, 0.20219), (0.45, 0.21187),
                    (0.5, 0.21382), (0.55, 0.21529), (0.6, 0.21067), (0.65, 0.20205), (0.7, 0.18942),
                    (0.75, 0.17176), (0.8, 0.15069), (0.85, 0.12758), (0.9, 0.10368), (0.95, 0.06863),
                    (1.0, 0.01189)),
        mand_inner=((0.0, -0.27114), (0.05, -0.24723), (0.1, -0.18073), (0.15, -0.10246), (0.2, -0.04076),
                    (0.25, -0.00545), (0.3, 0.01969), (0.35, 0.03515), (0.4, 0.03943), (0.45, 0.0394),
                    (0.5, 0.03455), (0.55, 0.05669), (0.6, 0.07132), (0.65, 0.07463), (0.7, 0.07409),
                    (0.75, 0.07115), (0.8, 0.07114), (0.85, 0.06728), (0.9, 0.05256), (0.95, 0.03602),
                    (1.0, 0.0343)),
        mand_dorsal=((-1.0, 14.1772), (-0.5, 14.3185), (0.0, 14.3019), (0.5, 14.2745), (1.0, 14.2258),
                     (1.5, 14.1525), (2.0, 14.0792), (2.5, 13.9799), (3.0, 13.8799), (3.5, 13.7567),
                     (4.0, 13.6286), (4.5, 13.4828), (5.0, 13.3271), (5.5, 13.1641), (6.0, 13.0004),
                     (6.5, 12.7864), (7.0, 12.6564), (7.5, 12.4835), (8.0, 12.3059), (8.5, 12.0815),
                     (9.0, 11.8421), (9.5, 11.5495), (10.0, 11.1857), (10.5, 10.7378), (11.0, 10.1984),
                     (11.5, 9.5779), (12.0, 8.8316), (12.5, 8.0595), (13.0, 7.2345), (13.5, 6.5686),
                     (14.0, 6.2913), (14.5, 6.11), (15.0, 6.0161), (15.5, 6.0961)),
        mand_ventral=((1.0, 10.2893), (1.5, 10.5371), (2.0, 10.7071), (2.5, 10.839), (3.0, 10.9177),
                      (3.5, 10.947), (4.0, 10.9503), (4.5, 10.8523), (5.0, 10.7271), (5.5, 10.5771),
                      (6.0, 10.4025), (6.5, 10.2237), (7.0, 10.009), (7.5, 9.7695), (8.0, 9.4702),
                      (8.5, 9.1638), (9.0, 8.7611), (9.5, 8.2777), (10.0, 7.6578), (10.5, 6.9103),
                      (11.0, 5.2621)),
        mand_plan=((0.00295, -0.00011), (0.00407, -0.00544), (0.00620, -0.01055), (0.00833, -0.01566), (0.01046, -0.02077),
                   (0.01259, -0.02587), (0.01472, -0.03098), (0.01685, -0.03609), (0.01898, -0.04119), (0.02111, -0.04630),
                   (0.02324, -0.05141), (0.02537, -0.05652), (0.02750, -0.06162), (0.02963, -0.06673), (0.03176, -0.07184),
                   (0.03389, -0.07694), (0.03602, -0.08205), (0.03815, -0.08716), (0.04028, -0.09227), (0.04241, -0.09737),
                   (0.04454, -0.10248), (0.04668, -0.10759), (0.04881, -0.11269), (0.05094, -0.11780), (0.05307, -0.12291),
                   (0.05520, -0.12801), (0.05733, -0.13312), (0.05946, -0.13823), (0.06159, -0.14334), (0.06372, -0.14844),
                   (0.06585, -0.15355), (0.06798, -0.15866), (0.07011, -0.16376), (0.07224, -0.16887), (0.07437, -0.17398),
                   (0.07650, -0.17909), (0.07863, -0.18419), (0.08076, -0.18930), (0.08289, -0.19441), (0.08502, -0.19951),
                   (0.08715, -0.20462), (0.08928, -0.20973), (0.09141, -0.21484), (0.09355, -0.21994), (0.09568, -0.22505),
                   (0.09805, -0.23005), (0.10248, -0.23275), (0.10801, -0.23269), (0.11354, -0.23259), (0.11907, -0.23240),
                   (0.12294, -0.22873), (0.12580, -0.22400), (0.12936, -0.21977), (0.13302, -0.21562), (0.13619, -0.21109),
                   (0.13984, -0.20694), (0.14384, -0.20313), (0.14846, -0.20009), (0.15310, -0.19710), (0.15562, -0.19222),
                   (0.15797, -0.18721), (0.16047, -0.18227), (0.16316, -0.17744), (0.16574, -0.17255), (0.16862, -0.16783),
                   (0.17122, -0.16295), (0.17438, -0.15840), (0.17693, -0.15350), (0.17974, -0.14874), (0.18227, -0.14382),
                   (0.18497, -0.13900), (0.18761, -0.13415), (0.19064, -0.12953), (0.19374, -0.12495), (0.19680, -0.12034),
                   (0.20002, -0.11584), (0.20297, -0.11116), (0.20614, -0.10662), (0.20937, -0.10213), (0.21280, -0.09780),
                   (0.21637, -0.09358), (0.21939, -0.08895), (0.22174, -0.08395), (0.22388, -0.07885), (0.22576, -0.07366),
                   (0.22734, -0.06836), (0.23022, -0.06367), (0.23468, -0.06049), (0.23948, -0.05777), (0.24437, -0.05519),
                   (0.24923, -0.05255), (0.25402, -0.04978), (0.25854, -0.04659), (0.26258, -0.04283), (0.26634, -0.03877),
                   (0.26941, -0.03418), (0.27247, -0.02957), (0.27532, -0.02483), (0.27918, -0.02088), (0.28398, -0.01813),
                   (0.28910, -0.01606), (0.29418, -0.01394), (0.29906, -0.01135), (0.30373, -0.00839), (0.30863, -0.00582),
                   (0.31338, -0.00301), (0.31846, -0.00083), (0.32351, 0.00137), (0.32846, 0.00384), (0.33350, 0.00611),
                   (0.33854, 0.00839), (0.34350, 0.01083), (0.34823, 0.01369), (0.35313, 0.01625), (0.35790, 0.01902),
                   (0.36294, 0.02131), (0.36799, 0.02358), (0.37302, 0.02589), (0.37801, 0.02826), (0.38331, 0.02978),
                   (0.38882, 0.02989), (0.39360, 0.02715), (0.39778, 0.02357), (0.40312, 0.02317), (0.40816, 0.02537),
                   (0.41262, 0.02860), (0.41726, 0.03158), (0.42174, 0.03483), (0.42685, 0.03667), (0.43212, 0.03514),
                   (0.43584, 0.03123), (0.43804, 0.02615), (0.44148, 0.02198), (0.44690, 0.02092), (0.45233, 0.01990),
                   (0.45750, 0.01794), (0.46239, 0.01536), (0.46704, 0.01237), (0.47224, 0.01051), (0.47752, 0.00887),
                   (0.48301, 0.00821), (0.48836, 0.00939), (0.49272, 0.01268), (0.49536, 0.01754), (0.49802, 0.02239),
                   (0.50130, 0.02666), (0.50676, 0.02660), (0.51192, 0.02470), (0.51580, 0.02082), (0.51825, 0.01586),
                   (0.52112, 0.01114), (0.52259, 0.00581), (0.52498, 0.00082), (0.52659, -0.00446), (0.52976, -0.00889),
                   (0.53274, -0.01353), (0.53572, -0.01819), (0.53927, -0.02240), (0.54221, -0.02708), (0.54559, -0.03146),
                   (0.54855, -0.03612), (0.55219, -0.04027), (0.55529, -0.04484), (0.55886, -0.04905), (0.56206, -0.05353),
                   (0.56562, -0.05777), (0.56935, -0.06184), (0.57210, -0.06663), (0.57559, -0.07092), (0.57930, -0.07501),
                   (0.58341, -0.07868), (0.58823, -0.08125), (0.59365, -0.08239), (0.59914, -0.08268), (0.60198, -0.07825),
                   (0.60256, -0.07275), (0.60286, -0.06724), (0.60242, -0.06173), (0.60133, -0.05631), (0.60045, -0.05084),
                   (0.59941, -0.04543), (0.59798, -0.04010), (0.59697, -0.03466), (0.59615, -0.02919), (0.59569, -0.02368),
                   (0.59566, -0.01815), (0.59521, -0.01264), (0.59529, -0.00711), (0.59521, -0.00158), (0.59556, 0.00394),
                   (0.59529, 0.00946), (0.59549, 0.01499), (0.59606, 0.02050), (0.59666, 0.02600), (0.59729, 0.03149),
                   (0.59819, 0.03695), (0.59910, 0.04241), (0.60020, 0.04782), (0.60164, 0.05316), (0.60475, 0.05759),
                   (0.60979, 0.05986), (0.61484, 0.06208), (0.62016, 0.06359), (0.62563, 0.06433), (0.63116, 0.06419),
                   (0.63668, 0.06458), (0.64208, 0.06577), (0.64754, 0.06606), (0.65272, 0.06416), (0.65820, 0.06406),
                   (0.66370, 0.06348), (0.66890, 0.06164), (0.67409, 0.05974), (0.67937, 0.05809), (0.68476, 0.05726),
                   (0.68986, 0.05932), (0.69449, 0.06234), (0.69954, 0.06435), (0.70475, 0.06260), (0.70913, 0.05983),
                   (0.71107, 0.05478), (0.71142, 0.04926), (0.71230, 0.04381), (0.71287, 0.03831), (0.71342, 0.03281),
                   (0.71393, 0.02731), (0.71412, 0.02178), (0.71465, 0.01629), (0.71523, 0.01079), (0.71576, 0.00529),
                   (0.71604, -0.00023), (0.71651, -0.00574), (0.71662, -0.01127), (0.71750, -0.01673), (0.71829, -0.02218),
                   (0.71864, -0.02770), (0.71941, -0.03316), (0.72032, -0.03861), (0.72142, -0.04400), (0.72239, -0.04945),
                   (0.72373, -0.05481), (0.72536, -0.06009), (0.72744, -0.06521), (0.72973, -0.07025), (0.73279, -0.07483),
                   (0.73746, -0.07767), (0.74296, -0.07770), (0.74758, -0.07486), (0.75022, -0.07006), (0.75170, -0.06473),
                   (0.75216, -0.05923), (0.75202, -0.05370), (0.75225, -0.04817), (0.75244, -0.04264), (0.75243, -0.03712),
                   (0.75288, -0.03160), (0.75334, -0.02610), (0.75387, -0.02059), (0.75442, -0.01509), (0.75489, -0.00958),
                   (0.75546, -0.00408), (0.75648, 0.00134), (0.75737, 0.00679), (0.75863, 0.01218), (0.75995, 0.01754),
                   (0.76156, 0.02283), (0.76332, 0.02807), (0.76547, 0.03316), (0.76826, 0.03794), (0.77119, 0.04262),
                   (0.77464, 0.04695), (0.77850, 0.05092), (0.78285, 0.05434), (0.78711, 0.05786), (0.79173, 0.06089),
                   (0.79699, 0.06259), (0.80228, 0.06418), (0.80764, 0.06541), (0.81306, 0.06639), (0.81858, 0.06669),
                   (0.82411, 0.06686), (0.82962, 0.06665), (0.83512, 0.06611), (0.84059, 0.06533), (0.84606, 0.06453),
                   (0.85151, 0.06361), (0.85693, 0.06247), (0.86226, 0.06101), (0.86752, 0.05930), (0.87295, 0.05829),
                   (0.87824, 0.05691), (0.88348, 0.05517), (0.88867, 0.05323), (0.89364, 0.05081), (0.89881, 0.04886),
                   (0.90415, 0.04740), (0.90933, 0.04546), (0.91435, 0.04318), (0.91914, 0.04046), (0.92444, 0.03890),
                   (0.92942, 0.03654), (0.93413, 0.03364), (0.93908, 0.03118), (0.94399, 0.02864), (0.94870, 0.02574),
                   (0.95329, 0.02267), (0.95780, 0.01947), (0.96212, 0.01601), (0.96663, 0.01281), (0.97115, 0.00963),
                   (0.97547, 0.00617), (0.97998, 0.00296), (0.98450, -0.00023), (0.98925, -0.00301), (0.99451, -0.00472),
                   (0.99986, -0.00471), (1.00233, -0.00015), (1.00206, 0.00537), (1.00039, 0.01063), (0.99855, 0.01582),
                   (0.99553, 0.02045), (0.99212, 0.02481), (0.98893, 0.02933), (0.98606, 0.03402), (0.98264, 0.03834),
                   (0.97917, 0.04265), (0.97595, 0.04710), (0.97216, 0.05111), (0.96844, 0.05519), (0.96456, 0.05912),
                   (0.96050, 0.06286), (0.95618, 0.06633), (0.95168, 0.06954), (0.94728, 0.07289), (0.94222, 0.07504),
                   (0.93847, 0.07911), (0.93398, 0.08231), (0.92929, 0.08526), (0.92468, 0.08829), (0.91993, 0.09110),
                   (0.91511, 0.09381), (0.91014, 0.09622), (0.90491, 0.09789), (0.90085, 0.10163), (0.89577, 0.10380),
                   (0.89076, 0.10610), (0.88597, 0.10882), (0.88080, 0.11078), (0.87562, 0.11274), (0.87062, 0.11510),
                   (0.86575, 0.11771), (0.86065, 0.11987), (0.85565, 0.12222), (0.85049, 0.12421), (0.84571, 0.12697),
                   (0.84066, 0.12923), (0.83569, 0.13165), (0.83056, 0.13371), (0.82559, 0.13615), (0.82043, 0.13814),
                   (0.81552, 0.14064), (0.81063, 0.14319), (0.80566, 0.14563), (0.80052, 0.14768), (0.79569, 0.15036),
                   (0.79055, 0.15239), (0.78548, 0.15460), (0.78054, 0.15709), (0.77561, 0.15959), (0.77037, 0.16136),
                   (0.76527, 0.16349), (0.76014, 0.16556), (0.75499, 0.16759), (0.74998, 0.16991), (0.74476, 0.17175),
                   (0.73960, 0.17372), (0.73446, 0.17578), (0.72932, 0.17782), (0.72410, 0.17966), (0.71878, 0.18116),
                   (0.71353, 0.18289), (0.70819, 0.18435), (0.70290, 0.18596), (0.69763, 0.18763), (0.69229, 0.18908),
                   (0.68693, 0.19043), (0.68156, 0.19173), (0.67621, 0.19315), (0.67095, 0.19486), (0.66561, 0.19631),
                   (0.66026, 0.19774), (0.65491, 0.19912), (0.64946, 0.20005), (0.64410, 0.20140), (0.63876, 0.20285),
                   (0.63334, 0.20396), (0.62788, 0.20486), (0.62241, 0.20564), (0.61714, 0.20733), (0.61173, 0.20843),
                   (0.60622, 0.20798), (0.60071, 0.20832), (0.59526, 0.20926), (0.58977, 0.20987), (0.58428, 0.21050),
                   (0.57882, 0.21138), (0.57334, 0.21207), (0.56783, 0.21238), (0.56232, 0.21218), (0.55682, 0.21272),
                   (0.55131, 0.21279), (0.54579, 0.21292), (0.54026, 0.21282), (0.53473, 0.21296), (0.52920, 0.21293),
                   (0.52368, 0.21283), (0.51814, 0.21283), (0.51263, 0.21272), (0.50714, 0.21222), (0.50161, 0.21230),
                   (0.49611, 0.21176), (0.49061, 0.21154), (0.48511, 0.21113), (0.47958, 0.21092), (0.47407, 0.21129),
                   (0.46859, 0.21197), (0.46310, 0.21237), (0.45757, 0.21235), (0.45224, 0.21097), (0.44725, 0.20865),
                   (0.44185, 0.20746), (0.43635, 0.20683), (0.43094, 0.20578), (0.42549, 0.20487), (0.41999, 0.20439),
                   (0.41461, 0.20308), (0.40912, 0.20258), (0.40368, 0.20160), (0.39819, 0.20095), (0.39291, 0.19933),
                   (0.38742, 0.19868), (0.38206, 0.19730), (0.37660, 0.19649), (0.37121, 0.19529), (0.36570, 0.19485),
                   (0.36033, 0.19353), (0.35497, 0.19232), (0.34955, 0.19127), (0.34421, 0.18984), (0.33889, 0.18837),
                   (0.33344, 0.18748), (0.32810, 0.18605), (0.32282, 0.18441), (0.31746, 0.18308), (0.31199, 0.18235),
                   (0.30669, 0.18078), (0.30128, 0.17976), (0.29592, 0.17838), (0.29058, 0.17694), (0.28543, 0.17494),
                   (0.28016, 0.17327), (0.27497, 0.17136), (0.26956, 0.17024), (0.26438, 0.16832), (0.25922, 0.16633),
                   (0.25400, 0.16453), (0.24894, 0.16229), (0.24365, 0.16070), (0.23857, 0.15852), (0.23352, 0.15626),
                   (0.22824, 0.15461), (0.22314, 0.15246), (0.21810, 0.15018), (0.21293, 0.14824), (0.20771, 0.14644),
                   (0.20286, 0.14380), (0.19805, 0.14109), (0.19301, 0.13881), (0.18796, 0.13653), (0.18295, 0.13420),
                   (0.17826, 0.13127), (0.17324, 0.12894), (0.16824, 0.12657), (0.16357, 0.12362), (0.15860, 0.12119),
                   (0.15389, 0.11829), (0.14899, 0.11574), (0.14451, 0.11249), (0.13966, 0.10985), (0.13499, 0.10689),
                   (0.13012, 0.10427), (0.12579, 0.10086), (0.12098, 0.09816), (0.11666, 0.09476), (0.11197, 0.09184),
                   (0.10721, 0.08903), (0.10286, 0.08563), (0.09910, 0.08163), (0.09451, 0.07856), (0.08961, 0.07603),
                   (0.08523, 0.07267), (0.08147, 0.06864), (0.07692, 0.06550), (0.07231, 0.06249), (0.06796, 0.05913),
                   (0.06378, 0.05553), (0.05919, 0.05244), (0.05470, 0.04920), (0.05105, 0.04505), (0.04704, 0.04128),
                   (0.04293, 0.03759), (0.03868, 0.03406), (0.03444, 0.03054), (0.03012, 0.02710), (0.02602, 0.02341),
                   (0.02241, 0.01922), (0.01837, 0.01544), (0.01456, 0.01144), (0.01058, 0.00760), (0.00647, 0.00392)),
        mand_fork=((15.6574, 5.9568), (15.6333, 5.8673), (15.5902, 5.7862), (15.5209, 5.7152), (15.4512, 5.6446),
                   (15.3736, 5.5920), (15.2874, 5.5595), (15.2113, 5.5044), (15.1415, 5.4339), (15.0718, 5.3634),
                   (14.9984, 5.3016), (14.9215, 5.2492), (14.8436, 5.1980), (14.7629, 5.1536), (14.6782, 5.1186),
                   (14.5996, 5.0691), (14.5113, 5.0425), (14.4221, 5.0172), (14.3338, 4.9907), (14.2456, 4.9641),
                   (14.1577, 4.9375), (14.0689, 4.9122), (13.9697, 4.9116), (13.8814, 4.8850), (13.7915, 4.8622),
                   (13.6939, 4.8578), (13.5947, 4.8571), (13.5055, 4.8319), (13.4062, 4.8312), (13.3133, 4.8157),
                   (13.2187, 4.8040), (13.1209, 4.7999), (13.0303, 4.7780), (12.9311, 4.7774), (12.8432, 4.7508),
                   (12.7549, 4.7242), (12.6658, 4.6989), (12.5775, 4.6724), (12.4892, 4.6458), (12.4032, 4.6133),
                   (12.3226, 4.5681), (12.2343, 4.5415), (12.1486, 4.5095), (12.0638, 4.4752), (11.9793, 4.4406),
                   (11.8919, 4.4119), (11.8027, 4.3866), (11.7166, 4.3549), (11.6261, 4.3335), (11.5374, 4.3082),
                   (11.4381, 4.3076), (11.3389, 4.3069))),
    # ---- the compound eye: plan §2.4
    eye=dict(along=1.948, across=2.365, eqd=2.112, sliver=0.791, c_from_frons=2.014, c_below_top=3.014,
             radius=1.2691, spacing=15.964, splay_LR=(101.275, 102.457), splay=101.866),
    # ---- the antenna: plan §2.4 (each segment the LONGEST male projection in PW x B1's PW)
    antenna=dict(scape=8.021, funicle=3.784, club=2.587, n_antennomeres=10, n_funicle=5, n_lamellae=4,
                 lamella_reach=(0.95, 1.60)),
    # ---- the mandibles: plan §2.5 (M1's left / right, then the ONE mirrored mandible the rig builds)
    mandible=dict(
        chord_LR=(17.864, 17.198), outer_LR=(21.005, 19.399), sagitta_LR=(0.213, 0.217), turn_LR=(89.2, 93.6),
        closed_LR=(27.216, 22.121), rest_LR=(14.912, 18.007), base_span=14.565, base_behind_LR=(0.456, 0.115),
        reach=15.817, tips_gap_closed=0.395, ML_rest=16.717,
        fork_frac_LR=(0.757, 0.741), fork_off_LR=(1.221, 1.211), big_frac_LR=(0.584, 0.598),
        big_off_LR=(1.299, 1.503), row_frac_L=(0.632, 0.679), row_off_L=(-1.145, -1.287),
        row_frac_R=(0.599, 0.697), row_off_R=(-0.923, -1.123), basal_frac_L=(0.479, 0.406),
        basal_off_L=(-0.339, -0.457), basal_frac_R=(0.485,), basal_off_R=(-0.001,),
        side_chord=18.671, side_pitch=26.167, tip_below_base=8.234, dorsal_arc=19.740, dorsal_sagitta=0.126,
        dorsal_turn=14.5, depth_at=(0.27, 0.39, 0.58), depth=(2.836, 2.603, 2.963), fork_drop=1.61,
        tine_gap=4.607, width=3.0, width_range=(3.0, 3.5), hinge_tilt=15.0, open_max=35.0,
        # the ONE mandible the mirrored rig builds: each the mean of M1's two sides
        chord=17.531, outer=20.202, closed=24.6685, rest=16.4595, open_rest=8.209, base_behind=0.2855),
    # ---- the legs: plan §2.6 (coxa-to-knee includes the trochanter; tarsus + claw from the ankle to the claw tip).
    # B3c (the lead, 10-21): each segment the MAX over its projections (M1d's sides, M3v EW-scaled, M1l's near legs)
    legs=dict(
        fore=dict(coxa_knee=11.2532, coxa_knee_plan=12.205, span_over_tibia_M3=1.0334, tibia=12.4353,
                  tibia_M1d=11.811, tibia_LR=(10.988, 11.811), tibia_M1l=12.4353,
                  tibia_M1l_px=((3214.0, 3424.0), (2321.0, 3769.0)), t1_4=4.848, t5=4.154,
                  tarsomeres=(1.4905, 1.3237, 1.181, 1.0969, 4.3631), tarsus=9.4552, claw=1.753, claw_LR=(1.753, 1.747),
                  tarsus_claw=11.2082, tarsus_claw_M1d=10.755, tarsus_claw_M3=12.1515),
        mid=dict(coxa_knee=10.2223, coxa_knee_plan=9.819, span_over_tibia_M3=1.0039, tibia=10.1821, tibia_M1d=9.781,
                 tibia_LR=(8.544, 9.781), tarsomeres=(1.7235, 1.510, 1.414, 1.298, 4.047), tarsus=9.9925, claw=2.190,
                 claw_LR=(1.831, 2.190), tarsus_claw=12.1825),
        hind=dict(coxa_knee=9.527, coxa_knee_plan=9.1935, span_over_tibia_M3=0.8066, tibia=11.8115, tibia_M1d=11.398,
                  tibia_LR=(10.895, 11.398), tibia_M1l=11.2151, tibia_M1l_px=((5676.0, 3390.0), (6525.0, 3547.0)),
                  tarsomeres=(1.815, 1.633, 1.388, 1.305, 4.281), tarsus=10.422, claw=1.814, claw_LR=(1.177, 1.814),
                  tarsus_claw=12.236)),
    # ---- the coxae, placement B (the femur's exit: x off the midline, z): plan §2.6-§2.7
    coxae=dict(pro=(2.5177, -12.5946), meso=(2.7547, -20.4068), meta=(2.5177, -31.4265)),
    # ---- the rest pose (plan §2.7): P1's live plan closed on B1's lengths; per leg (fore, mid, hind)
    rest=dict(coxa_h=7.5152, ankle_h=0.28, coxa_over_procoxa=0.75, stand_P3=2.644,
              stand_P2_ortho=8.3921, P2_venter_px=(800.0, 785.0), coxa_h_mh=(0.2174, 0.4311), coxa_over_venter=(-0.40, -0.30),
              # B3d (the lead 10-22): P2 and P3 solved as PERSPECTIVE cameras (arthropod.py "the cameras"), the venter's
              # height their consensus (stand), the tibiae's elevations from P2's reconstruction
              P3_f_px=8536.3726, P3_EW_px=683.0, P3_size=(2816.0, 2112.0), P3_contact_rows=(1589.0, 1383.0),
              P3_tip_rows=(1525.0, 1521.0), P3_venter_px=(1356.0, 1426.0), P3_pitch=16.6792, P3_axis_h=14.9961,
              stand_P3_persp=4.9993, P2_size=(1856.0, 1232.0),
              P2_body_px=((273.0, 699.0), (655.0, 480.0), (813.0, 513.0)),
              P2_knee_px=((1054.0, 682.0), (961.0, 753.0), (699.0, 764.0)),
              P2_foot_px=((1299.0, 819.0), (1135.0, 999.0), (622.0, 972.0)), P2_horizon_px=(600.0, 616.0),
              P2_tol_px=10.0, P2_D=56.5469, stand_P2_persp=5.4698, tibia_e_P2=(49.8561, 36.9104), femur_e_P2_fore=6.5694,
              stand_sd=(0.50, 0.20), stand=5.0642,
              claw_drop_P3_px=(66.0, 71.0), P3_elev=20.45, claw_stand=62.8766,
              tibia_P2=(29.2132, 54.7276, 110.3142),
              tibia_P3_px=((1759.0, 1382.0, 1930.0, 1769.0), (887.0, 1343.0, 736.0, 1756.0),
                           (1827.0, 1263.0, 2106.0, 1548.0), (856.0, 1226.0, 640.0, 1538.0)),
              tibia_P3=(68.039, 50.4572), knee_dir_P1=(91.5151, 94.932, 89.7938), femur_band=15.0,
              tibia_dir=(37.627, 110.0755, 135.122),
              tibia_dir_LR=((41.126, 34.128), (105.658, 114.493), (131.347, 138.897)),
              tarsus_dir=(28.1015, 100.2695, 116.565),
              tarsus_plan_PW=(0.54725, 0.68338, 0.70725), tibia_plan_PW=(0.47345, 0.54236, 0.65857),
              tibia_plan_EL=(0.28233, 0.32342, 0.39272), claw_span_PW=(2.68288, 3.94769, 3.73752),
              claw_z_PW=(0.03605, -0.49075, -1.61388), mid_span_EW=3.2943,
              antenna_dir=(78.5, 76.0, 74.0), antenna_elev=(20.0, 0.0, 0.0), lamella_fan=0.0),
    # ---- joint places with no measured anchor of their own (plan §6.1): life mm in the plan frame
    rig=dict(neck_h=11.0, waist_h=6.80, body=(-25.2, 6.4), abdomen=((-33.0, 4.5), (-38.0, 4.8), (-42.8, 5.0)),
             elytron=(2.0, -18.9, 10.6), elytron_tip_x=0.25,
             wing=((4.2, -21.5, 10.4), (5.0, -30.5, 10.2), (4.2, -37.5, 8.0), (2.8, -41.0, 6.6)),
             coxa_len=2.25, coxa_medial=0.692, trochanter=2.0, pedicel_frac=0.2,
             lamella_at=(0.125, 0.375, 0.625, 0.875)),
    # ---- the mandible allometry (plan §2.8): Romiti's ML (clypeus to the fork's outer tooth) on EL
    allometry=dict(switch_EL=22.19, switch_sd=1.01, slope_minor=1.78, slope_major=3.29,
                   slope_minor_range=(0.66, 1.92), slope_major_range=(2.26, 3.64), major_anchor=(25.239, 16.717),
                   minor_anchor=(19.5, 8.9), E1_anchor=(25.9, 22.4), E1_over_B1=1.2307,
                   anatomy_rule=(22.19, 11.2, 13.5), hardersen_PW50=18.4, hardersen_PW50_season=(17.4, 19.0),
                   romiti_mass_g=(1.7, 2.4), romiti_EL_median=(21.0, 23.0), mass_g=3.095, fill=0.580),
)

# The part ids (plan §4.2, one closed shell per sclerite) for the cage's part one-hot, the bake's region output and the
# recipe's mask regions; zones are the material roles of plan §5.5 (remix/elements.py's element roles)
REGIONS = ('head', 'eye', 'mandible', 'antenna', 'mouthparts', 'pronotum', 'scutellum', 'elytron', 'venter', 'coxa',
           'trochanter', 'femur', 'tibia', 'tarsus', 'claw', 'membrane', 'hindwing')
REGION_ID = {name: i for i, name in enumerate(REGIONS)}
ZONES = dict(primary='1 - masks.r', soft='masks.r', accent='masks.b', pattern='masks.a')

_PJ = 'plan_numbers.json '
TAGS = {
    'family': ('[H]', 'plan §4.1: the family generator forge/families/arthropod.py'),
    'head_archetype': ('[H]', 'plan §4.1: the head archetype forge/heads/insect.py'),
    'author_scale': ('[H] [D-fo]', 'plan §4.3: built and exported at x10 (life_scale 0.1); the forge\'s metric constants '
                                   'hold at a creature\'s scale (the sucker template\'s precedent)'),
    # body (M1d)
    'body.TL': ('[M-ph]', 'mandible tips to the elytral apex, pinned closed (B1.TL; the lateral ruler gives 59.244)'),
    'body.BL': ('[M-ph]', 'the clypeal tip (the photo strand\'s "frons") to the apex (B1.BL)'),
    'body.BLc': ('[M-ph]', 'the head\'s front margin to the apex (B1.BLc)'),
    'body.HL': ('[M-ph]', 'the clypeal tip to the neck, 0.618 PW (B1.HL)'),
    'body.HLc': ('[M-ph]', 'the head\'s front margin to the neck (B1.HLc)'),
    'body.HW': ('[M-ph]', 'head width at the anterior angles, its maximum, 1.126 PW (B1.HW)'),
    'body.HW_ant': ('[M-ph]', 'head width at the front corners beside the mandible bases (B1.HW_ant)'),
    'body.HW_post': ('[M-ph]', 'head width behind the eyes, 1.015 PW (B1.HW_post)'),
    'body.PL': ('[M-ph]', 'pronotum length on the midline, 0.533 PW (B1.PL)'),
    'body.PW': ('[M-ph]', 'pronotum width (B1.PW)'),
    'body.PW_front': ('[M-ph]', 'pronotum front width, 0.880 PW (B1.PW_front)'),
    'body.PW_back': ('[M-ph]', 'pronotum hind width, 0.933 PW (B1.PW_back)'),
    'body.pron_widest': ('[M-ph]', 'the pronotum widest 5.35 behind the neck, 0.64 PL (res_s01a pron_angle_pos)'),
    'body.EL': ('[M-ph]', 'elytral base to apex along the body axis, 1.613 PW (B1.EL)'),
    'body.EL_sut': ('[M-ph]', 'the scutellum\'s apex to the apex (B1.EL_sut)'),
    'body.EW': ('[M-ph]', 'width of both elytra, 1.190 PW (B1.EW)'),
    'body.EW_hum': ('[M-ph]', 'humeral width, 0.902 EW (B1.EW_hum)'),
    'body.ely_widest': ('[M-ph]', 'the elytra widest 8.93 behind the base, 0.354 EL (res_s01a ely_widest_pos_L)'),
    'body.scut': ('[M-ph]', 'the visible scutellum, 0.095 EL (B1.scut)'),
    'body.waist': ('[D-pl from M-ph]', 'the visible waist, the pronotum\'s hind edge to the elytral base on the midline '
                                       '(waist_gap_M1d; E1 1.7: the waist joint\'s pitch, set by each preparation)'),
    # lateral (M1l)
    'lateral.TL': ('[M-ph]', 'TL by the lateral ruler: the scale check, 0.27 % from the card (res_s01c TL_h)'),
    'lateral.EL_h': ('[M-ph]', 'elytral length, horizontal (res_s01c EL_h)'),
    'lateral.EL_chord': ('[M-ph]', 'elytral chord, base to apex (B1.EL_chord)'),
    'lateral.ely_chord_pitch': ('[M-ph]', 'the chord\'s pitch, apex lower, pinned: the bind keeps it (plan §2.7: the '
                                          'body\'s attitude at rest is free until a relaxed side view; res_s01c)'),
    'lateral.depth': ('[M-ph]', 'body depth, elytral top to venter (setae about 0.2 mm included), 0.500 chord '
                                '(B1.depth)'),
    'lateral.ely_top_pos': ('[M-ph]', 'the elytral top 7.69 behind the base, 0.301 chord (res_s01c ely_top_pos)'),
    'lateral.ely_top_above_base': ('[M-ph]', 'the elytral top above the base point (res_s01c)'),
    'lateral.ely_side_h': ('[M-ph]', 'elytral side height, top to the lateral margin (B1.ely_side_h)'),
    'lateral.venter_below_margin': ('[M-ph]', 'the venter below the lateral margin (B1.venter_below_margin)'),
    'lateral.apex_below_top': ('[M-ph]', 'the apex below the top (res_s01c apex_below_top)'),
    'lateral.pron_depth': ('[M-ph]', 'pronotum depth, top to the procoxa (B1.pron_depth)'),
    'lateral.PL': ('[M-ph]', 'pronotum length at the side (res_s01c PL_h)'),
    'lateral.pron_front_above_back': ('[M-ph]', 'the pronotum\'s front above its back edge, pinned (res_s01c)'),
    'lateral.HL': ('[M-ph]', 'head length in the side view (res_s01c HL_h)'),
    'lateral.head_h_eye': ('[M-ph]', 'head height at the eye (B1.head_h_eye)'),
    'lateral.crest_above_head_top': ('[M-ph]', 'the vertex crest above the head top at the eye (res_s01c)'),
    'lateral.crest_above_ely_top': ('[M-ph]', 'the vertex crest above the elytral top, pinned (res_s01c)'),
    # profiles
    'profiles.elytra': ('[M-ph]', 'plan §2.2: stations 0.05-0.15 and 0.55-0.70 missing (legs touch the outline); M2 '
                                  'matches within +-0.013 from 0.75 to 0.95 (res_s01a prof_ely)'),
    'profiles.pronotum': ('[M-ph]', 'plan §2.2: the front angles stand out slightly (res_s01a prof_pron)'),
    'body.ely_plate': ('[P]', 'the elytron plate 0.27 mm (Kundanati et al. 2019 on L. cervus; plan §2.10.16): the '
                              'elytron shell\'s thickness (B3)'),
    # B3's outline rows (research/beetle_scripts/b3_outlines.py; b00 recomputes each): M1's own silhouettes
    'outline.head_half': ('[D-b3 from M-ph]', 'M1d: the head\'s dorsal half-width at z (the eye\'s sliver included), the '
                                              'mean of both sides about the run through the midline, and that run\'s '
                                              'centre (the specimen sits off its frons-apex axis); z -0.75 .. -5.0, '
                                              'where no antenna or leg crosses the outline'),
    'outline.pron_half': ('[D-b3 from M-ph]', 'M1d: the pronotum\'s half-width at z -11.0 .. -17.5, as head_half'),
    'outline.pron_keel': ('[M-ph]', 'B3b 10-21, traced on a bview.py grid of M1l (beetle/scratch_b03b/g_m1l_pron.png): '
                                    'the pronotum\'s lateral margin seen from the side (the lower edge of its dorsal '
                                    'plate over the hypomeron), at px x 3600 .. 4230, converted by b3_outlines.Frames.'
                                    'lat (z, h): it dips to 7.3 at z -13.1 and rises to the front and back; the '
                                    'section\'s widest point (families/arthropod_parts.pronotum_descs)'),
    'outline.pron_profile_z': ('[D-b3 from M-ph]', 'M1d: pron_front\'s z and the length res_s01a prof_pron\'s '
                                                   'stations are fractions of (the profile\'s plan frame)'),
    'outline.dorsal_line': ('[D-b3 from M-ph]', 'M1l: the dorsal silhouette\'s height above the venter at z, the frons '
                                                'top to the elytral apex (plan_numbers.py\'s landmark transform)'),
    'outline.ely_margin': ('[D-b3 from M-ph]', 'M1l: the elytral lateral margin, the photo strand\'s margin points '
                                               'ely_marg_a .. e as (z, h)'),
    'outline.mand_outer': ('[D-b3 from M-ph]', 'M1d: the mandible\'s outer edge (md_*_outer) in its chord frame, v / '
                                               'chord at u = 0 .. 1 (+ away from the midline): the mean of the left and '
                                               'the mirrored right (the one mirrored mandible)'),
    'outline.mand_inner': ('[D-b3 from M-ph]', 'M1d: the inner edge\'s envelope (md_*_inner without its teeth): '
                                               'distal of the large tooth (u from 0.68) a closing over +-0.06 of the '
                                               'chord (the largest v, then the smallest of those), to 0.62 the '
                                               'largest v alone, blended between, a running mean (b3_outlines.py '
                                               'mand_edges.envelope says why); as mand_outer; real from u ~0.12 (the '
                                               'inner base); the two sides 0.9 mm apart in width at u 0.2 (L 4.86, '
                                               'R 3.98)'),
    'outline.mand_dorsal': ('[D-b3 from M-ph]', 'M1l: the mandible\'s dorsal edge (md_lat_dorsal) as (z, h), pinned '
                                                'closed'),
    'outline.mand_ventral': ('[D-b3 from M-ph]', 'M1l: its ventral edge (md_lat_ventral) as (z, h), to the fork'),
    'outline.mand_plan': ('[D-b0 from M-ph]', 'B3b (the lead, 10-21): the one mirrored mandible\'s plan shape INCLUDING '
                                              'THE BASE, M1d\'s closed outline: per side the md_*_outer and md_*_inner '
                                              'stretches and the base edge (where the head\'s front margin covers the '
                                              'mandible) in its own chord frame (u, v / chord, + away from the midline), '
                                              'the right mirrored and fitted rigidly onto the left (turn -0.73 deg), '
                                              'the zero set of the mean of the two signed distance fields (smoothed over '
                                              '2 cells of 0.0008 chord), 520 points from the outer base, counter-'
                                              'clockwise (arthropod_parts.m1_mandible_loops, mean_outline); each side '
                                              'within p90 0.22 / 0.18 mm of it'),
    'outline.mand_fork': ('[D-b0 from M-ph]', 'B3b: M1l\'s fork edge, the contour from the tip (mand_tip) back to the '
                                              'tine\'s lowest point (md_tine_b) the short way, (z, h) every 0.1 mm of '
                                              'arc (arthropod_parts.m1_fork_edge): the side prism\'s lower front and '
                                              'the lateral gate\'s third stretch'),
    # eye
    'eye.along': ('[M-ph]', 'the eye\'s lateral outline, long (B1.eye_along)'),
    'eye.across': ('[M-ph]', 'the eye\'s lateral outline, tall (B1.eye_across)'),
    'eye.eqd': ('[M-ph]', 'equal-area diameter, 0.085 EL = 0.135 PW (B1.eye_eqd)'),
    'eye.sliver': ('[M-ph]', 'the dorsal sliver behind the canthus, the mean of both sides (B1.eye_sliver)'),
    'eye.c_from_frons': ('[M-ph]', 'the centre 2.01 behind the frons top (res_s01c eye_c_from_frons)'),
    'eye.c_below_top': ('[M-ph]', 'the centre 3.01 below the head\'s top (res_s01c eye_c_below_head_top)'),
    'eye.radius': ('[D-b0 from M-ph]', 'the dome\'s sphere through M1l\'s exposed outline (B3b 10-21: the built '
                                       'dome, heads/insect.py, reads it): its base circle the outline\'s height (across '
                                       '/ 2) where it leaves the capsule, its rise there the dorsal sliver along the '
                                       'axis (sliver / sin splay): R = (a^2 + p^2) / 2p. The canthus covers the front '
                                       'of the circle, so the exposed outline is 1.95 long x 2.37 tall (B3\'s gate). '
                                       'The plan\'s 1.078 (accessories.eyes.radius_life_mm) was the outline\'s mean '
                                       'semi-axis, which a dome 2.37 tall where it leaves the capsule 0.79 proud '
                                       'cannot have'),
    'eye.spacing': ('[D-pl from M-ph] [E]', 'the eye centres apart: the head\'s width at the eye less the sliver '
                                            '(accessories.eyes.spacing_life_mm)'),
    'eye.splay_LR': ('[D-pl from M-ph]', 'the head margin\'s outward normal at the eye, head_L to head_post_L on M1d, '
                                         'left / right: 90 + conv (plan §2.4; accessories.eyes.splay_deg as fixed B0 '
                                         '10-21); it stands in for the eye\'s axis until B3 fits the dome'),
    'eye.splay': ('[D-b0 from D-pl]', 'the mirrored rig\'s one eye axis: the mean of splay_LR'),
    # antenna
    'antenna.scape': ('[D-pl from M-an]', 'the longest male projection in PW (E1, 0.5125 PW) x B1\'s PW '
                                          '(B1_antenna.scape)'),
    'antenna.funicle': ('[D-pl from M-ph]', 'the longest projection (M2 right, 0.2417 PW) x PW (B1_antenna.funicle)'),
    'antenna.club': ('[D-pl from M-ph]', 'the longest projection (M2 left, 0.1653 PW) x PW; inside Bardiani\'s 1/5-1/4 '
                                         'of the fore tibia, 2.36-2.95 (B1_antenna.club)'),
    'antenna.n_antennomeres': ('[C]', 'geniculate, 10 antennomeres (DELTA Lucanidae)'),
    'antenna.n_funicle': ('[C] [D-b0]', 'the beads between the scape and the club, pedicel included: 10 - 1 - 4 '
                                        '(plan §2.4 has "5-6"; the cage count of §4.6 takes 6)'),
    'antenna.n_lamellae': ('[M-ph] [C]', 'a club of 4 lamellae (M4, F1; Bardiani: 4, rarely 5)'),
    'antenna.lamella_reach': ('[M-ph]', 'lamellae reach 0.95-1.60 out from the club\'s axis (M4, ratios only); the '
                                        'rig takes the mean (plan_numbers.py\'s 1.27 plate)'),
    # mandible
    'mandible.chord_LR': ('[M-ph]', 'chord, outer base to tip, left / right (B1.ML_L, ML_R)'),
    'mandible.outer_LR': ('[M-ph]', 'the outer edge, sigma 10 px (B1.md_outer_L, md_outer_R)'),
    'mandible.sagitta_LR': ('[M-ph]', 'sagitta / chord (res_s01a md_L_outer, md_R_outer)'),
    'mandible.turn_LR': ('[M-ph]', 'the outer edge\'s tangent turn (res_s01a)'),
    'mandible.closed_LR': ('[M-ph]', 'chord direction pinned closed, deg inward, tips 0.40 apart (B1.chord_dir_L, _R)'),
    'mandible.rest_LR': ('[M-ph]', 'chord direction live at rest, P1, deg inward (B1.mand_rest_dir)'),
    'mandible.base_span': ('[M-ph]', 'the outer bases apart, 0.931 PW (res_s01a mand_base_span)'),
    'mandible.base_behind_LR': ('[D-b0 from M-ph]', 'the outer bases behind the clypeal tip along M1d\'s axis '
                                                    '(res_s01a points mand_base_out_L/R, frons)'),
    'mandible.reach': ('[M-ph]', 'the tips ahead of the clypeal tip, pinned closed: Romiti\'s ML pinned '
                                 '(B1.mand_reach)'),
    'mandible.tips_gap_closed': ('[M-ph]', 'the tips apart, pinned closed (res_s01a tips_gap)'),
    'mandible.ML_rest': ('[D-pl from M-ph]', 'Romiti\'s ML at P1\'s live rest angles, the major branch\'s anchor '
                                             '(B1.ML_romiti_rest)'),
    'mandible.fork_frac_LR': ('[M-ph]', 'the fork\'s inner tine, fraction of the chord (res_s01a md_*_fork_off)'),
    'mandible.fork_off_LR': ('[M-ph]', 'its height inward of the chord (res_s01a)'),
    'mandible.big_frac_LR': ('[M-ph]', 'the large inner tooth, fraction of the chord; M2 0.583 / 0.588, M4 0.586 '
                                       '(res_s01a md_*_big_off)'),
    'mandible.big_off_LR': ('[M-ph]', 'its height inward (res_s01a)'),
    'mandible.row_frac_L': ('[M-ph]', 'the row of small teeth, left: 4-5 by eye between these fractions (res_s01a '
                                      'md_L_row0/1_off)'),
    'mandible.row_off_L': ('[M-ph]', 'the row\'s offsets, - = outside the chord (res_s01a)'),
    'mandible.row_frac_R': ('[M-ph]', 'the row, right (res_s01a md_R_row0/1_off)'),
    'mandible.row_off_R': ('[M-ph]', 'the row\'s offsets, right, - = outside (res_s01a)'),
    'mandible.basal_frac_L': ('[M-ph]', 'basal teeth, left (res_s01a md_L_basal_off, md_L_basal2_off); M4: about 10 '
                                        'denticles at 0.343-0.491'),
    'mandible.basal_off_L': ('[M-ph]', 'their offsets, - = outside (res_s01a)'),
    'mandible.basal_frac_R': ('[M-ph]', 'basal tooth, right (res_s01a md_R_basal_off)'),
    'mandible.basal_off_R': ('[M-ph]', 'its offset (res_s01a)'),
    'mandible.side_chord': ('[M-ph]', 'side view: the chord (res_s01c ML_lat)'),
    'mandible.side_pitch': ('[M-ph]', 'side view: the chord 26.2 deg below the horizontal, pinned (res_s01c '
                                      'mand_pitch); the head keeps M1\'s pitch at rest (plan §2.7)'),
    'mandible.tip_below_base': ('[M-ph]', 'side view: the tip below the base (res_s01c)'),
    'mandible.dorsal_arc': ('[M-ph]', 'side view: the dorsal edge\'s arc (res_s01c md_lat_dorsal)'),
    'mandible.dorsal_sagitta': ('[M-ph]', 'side view: its sagitta / chord (res_s01c)'),
    'mandible.dorsal_turn': ('[M-ph]', 'side view: its turn (res_s01c)'),
    'mandible.depth_at': ('[M-ph]', 'the stations of the dorsoventral depth, fractions of the length (plan §2.5)'),
    'mandible.depth': ('[M-ph]', 'dorsoventral depth there (res_s01c md_depth_prox / mid / dist)'),
    'mandible.fork_drop': ('[M-ph]', 'the fork\'s lowest point below the tip (res_s01c points md_tine_b, mand_tip)'),
    'mandible.tine_gap': ('[M-ph]', 'the tine gap (res_s01c md_tine_gap)'),
    'mandible.width': ('[E]', 'arm width at mid-length: the low end of ENT0588940\'s 3.0-3.5 (a TL 69.7 major; B1 is '
                              'smaller); gate B3'),
    'mandible.width_range': ('[M-an]', 'arm width at mid-length on ENT0588940 (TL 69.7)'),
    'mandible.hinge_tilt': ('[E-an]', 'the dicondylic hinge axis: near dorso-ventral, tilted 10-20 deg top-forward; '
                                      'the middle; gate: the condyles in the s04 lateral views'),
    'mandible.open_max': ('[E-an]', 'the rig\'s range, 0 (M1\'s closure) to 35 deg open per side; gate: a measured '
                                    'threat display (plan §6.3)'),
    'mandible.chord': ('[D-b0 from M-ph]', 'the one mirrored mandible: the mean of chord_LR'),
    'mandible.outer': ('[D-b0 from M-ph]', 'the mean of outer_LR'),
    'mandible.closed': ('[D-b0 from M-ph]', 'the mean of closed_LR: the closed (pinned) direction'),
    'mandible.rest': ('[D-b0 from M-ph]', 'the mean of rest_LR: the bind\'s direction (P1)'),
    'mandible.open_rest': ('[D-b0 from M-ph]', 'closed - rest: the bind 8.2 deg open per side (plan §2.5: 12.3 left, '
                                               '4.1 right against M1\'s asymmetric closure, "8 on average")'),
    'mandible.base_behind': ('[D-b0 from M-ph]', 'the mean of base_behind_LR: the hinge\'s z is minus this (plan §6.1 '
                                                 '"z about -0.3")'),
    # legs
    'legs.fore.coxa_knee': ('[D-b0 from M-ph]', 'B3c (the lead, 10-21): the MAX over its projections (a projection only '
                                                'shortens): M3v\'s femur from the coxa to the knee (res_c07 L1_L.'
                                                'femur_vis) x B1 / M3 EW (0.9222, M3v\'s transfer since placement B), '
                                                'M1d\'s femur_vis (the longer side, the femur mostly hidden); M1l\'s '
                                                'near femur is hidden in the body. The plan\'s ratio rule '
                                                '(coxa_knee_plan) is not a projection'),
    'legs.fore.coxa_knee_plan': ('[D-pl from M-ph]', 'the plan\'s rule, kept for the record: M1d\'s tibia x M3\'s span / '
                                                     'tibia (B1_legs.fore.coxa_knee)'),
    'legs.fore.span_over_tibia_M3': ('[M-ph]', 'M3v\'s coxa-to-knee span over its tibia (B1_legs)'),
    'legs.fore.tibia': ('[D-b0 from M-ph]', 'B3c: the MAX over its projections: M1d\'s longer side (tibia_M1d), M3v\'s '
                                            '(res_c07 L1_L.tibia) x 0.9222, M1l\'s near leg (tibia_M1l): M1l\'s'),
    'legs.fore.tibia_M1d': ('[M-ph]', 'the longer side of M1d: dorsal projections only shorten (B1_legs.fore.tibia)'),
    'legs.fore.tibia_M1l': ('[D-b0 from M-ph]', 'M1l\'s near (left) fore tibia in the side view, tibia_M1l_px through '
                                                'b3_outlines.Frames.lat (the ruler\'s 76.985 px/mm)'),
    'legs.fore.tibia_M1l_px': ('[M-ph]', 'B3c 10-21, traced on a bview.py grid of M1l (beetle/scratch_b03c/'
                                         'g_m1l_foretib.png, 1.33x): the near fore tibia\'s proximal end at the knee boss '
                                         'and its distal end at the tarsal insertion, px (+-10)'),
    'legs.fore.tibia_LR': ('[M-ph]', 'left / right projections (B1_legs)'),
    'legs.fore.t1_4': ('[M-ph]', 'M1\'s own longer projection, the left leg (res_s01a L1_L.t1-4; right 4.334): the '
                                 'fore tarsus is M1\'s own, not the borrowed M3 row (the lead, B3 10-21: the borrowed '
                                 '10.40 mm tarsus stood 1.83 mm past P1\'s chord and arched the tarsus)'),
    'legs.fore.t5': ('[M-ph]', 'the left leg\'s t5 (res_s01a L1_L.t5; right 4.072, mean 4.113): the fore tarsus is '
                               'one projection, its longer side'),
    'legs.fore.tarsomeres': ('[D-b0 from M-ph]', 't1_4 split by the mid and hind legs\' mean t1 : t2 : t3 : t4 '
                                                 '(the fore tarsomeres 1-4 are too foreshortened to split), then t5, '
                                                 'all scaled to the tarsus (B3c: M3v\'s longer projection)'),
    'legs.fore.tarsus': ('[D-b0 from M-ph]', 'B3c: tarsus_claw - claw (M3v\'s projection, the longer; M1\'s own t1_4 + '
                                             't5 is 9.00)'),
    'legs.fore.claw': ('[M-ph]', 'the longer side: claws curve and turn (B1_legs.fore.claw)'),
    'legs.fore.claw_LR': ('[M-ph]', 'left / right (B1_legs)'),
    'legs.fore.tarsus_claw': ('[D-b0 from M-ph]', 'B3c: the MAX over its projections: M1d\'s own (tarsus_claw_M1d) and '
                                                  'M3v\'s (res_c07 L1_L.tarsus+claw) x 0.9222: M3v\'s'),
    'legs.fore.tarsus_claw_M1d': ('[D-b0 from M-ph]', 't1_4 + t5 + claw: M1\'s own longer projection (the left leg\'s '
                                                      '10.755; B3\'s fore tarsus)'),
    'legs.fore.tarsus_claw_M3': ('[D-pl from M-ph]', 'the REJECTED borrowed row, kept for the record: M3\'s fore / mid '
                                                     'ratio x B1\'s mid tarsus + claw (B1_legs.fore.tarsus_claw), '
                                                     '0.885x M1\'s own projection'),
    'legs.mid.coxa_knee': ('[D-b0 from M-ph]', 'B3c: the MAX over its projections, M3v\'s (res_c07 L2_L.femur_vis) x '
                                               '0.9222 against M1d\'s femur_vis (hidden): M3v\'s'),
    'legs.mid.coxa_knee_plan': ('[D-pl from M-ph]', 'the plan\'s rule: tibia x M3\'s span / tibia '
                                                    '(B1_legs.mid.coxa_knee)'),
    'legs.mid.span_over_tibia_M3': ('[M-ph]', 'M3v (B1_legs)'),
    'legs.mid.tibia': ('[D-b0 from M-ph]', 'B3c: the MAX over its projections, M1d\'s longer side against M3v\'s x 0.9222 '
                                           '(M1l\'s near mid leg is hidden under the body): M3v\'s 10.18 (the checker\'s '
                                           'case (a)); the mid tibia is still the shortest'),
    'legs.mid.tibia_M1d': ('[M-ph]', 'the longer side of M1d (B1_legs.mid.tibia)'),
    'legs.mid.tibia_LR': ('[M-ph]', 'left / right (B1_legs)'),
    'legs.mid.tarsomeres': ('[M-ph]', 'the mean of the sides: they lie on the board (B1_legs.mid.tarsomeres)'),
    'legs.mid.tarsus': ('[M-ph]', 'the sum (B1_legs.mid.tarsus)'),
    'legs.mid.claw': ('[M-ph]', 'the longer side (B1_legs.mid.claw)'),
    'legs.mid.claw_LR': ('[M-ph]', 'left / right (B1_legs)'),
    'legs.mid.tarsus_claw': ('[D-pl from M-ph]', 'tarsus + claw (B1_legs.mid.tarsus_claw)'),
    'legs.hind.coxa_knee': ('[D-b0 from M-ph]', 'B3c: the MAX over its projections, M3v\'s (res_c07 L3_L.femur_vis) x '
                                                '0.9222 against M1d\'s femur_vis (hidden; M1l\'s near femur leaves the '
                                                'body hidden): M3v\'s'),
    'legs.hind.coxa_knee_plan': ('[D-pl from M-ph]', 'the plan\'s rule: tibia x M3\'s span / tibia; M3\'s hind femur may '
                                                     'be a lower bound (B1_legs.hind.coxa_knee)'),
    'legs.hind.span_over_tibia_M3': ('[M-ph]', 'M3v (B1_legs)'),
    'legs.hind.tibia': ('[D-b0 from M-ph]', 'B3c: the MAX over its projections: M1d\'s longer side, M3v\'s x 0.9222, '
                                            'M1l\'s near leg: M3v\'s'),
    'legs.hind.tibia_M1d': ('[M-ph]', 'the longer side of M1d (B1_legs.hind.tibia)'),
    'legs.hind.tibia_M1l': ('[D-b0 from M-ph]', 'M1l\'s near (left) hind tibia, tibia_M1l_px through Frames.lat'),
    'legs.hind.tibia_M1l_px': ('[M-ph]', 'B3c 10-21, traced on beetle/scratch_b03c/g_m1l_hindtib.png (1.14x): the knee '
                                         'ring and the tarsal insertion, px (+-10)'),
    'legs.hind.tibia_LR': ('[M-ph]', 'left / right (B1_legs)'),
    'legs.hind.tarsomeres': ('[M-ph]', 'the mean of the sides; E1\'s hind tarsus sums to 12.15 with its claws '
                                       '(B1_legs.hind.tarsomeres)'),
    'legs.hind.tarsus': ('[M-ph]', 'the sum (B1_legs.hind.tarsus)'),
    'legs.hind.claw': ('[M-ph]', 'the longer side (B1_legs.hind.claw)'),
    'legs.hind.claw_LR': ('[M-ph]', 'left / right (B1_legs)'),
    'legs.hind.tarsus_claw': ('[D-pl from M-ph]', 'tarsus + claw (B1_legs.hind.tarsus_claw)'),
    # coxae
    'coxae.pro': ('[D-pl from M-ph]', 'placement B: from the elytral apex by M3v\'s ratios in EW (B1.coxaeB.pro); M1\'s '
                                      'own procoxa (its lowest bulge, z -15.82) is not the femur\'s exit'),
    'coxae.meso': ('[D-pl from M-ph]', 'placement B (B1.coxaeB.meso)'),
    'coxae.meta': ('[D-pl from M-ph]', 'placement B (B1.coxaeB.meta)'),
    # rest
    'rest.coxa_h': ('[D-b0 from M-ph]', 'THE BIND STANDS (the lead, B3b 10-21; plan §8 Q2) at the venter\'s height off the '
                                        'ground (B3d, the lead 10-22: the CONSENSUS of P2 and P3 solved in perspective, '
                                        'rest.stand) + the procoxa above the venter (M1l 1.701) + coxa_over_procoxa (B3c '
                                        'read P2 as an orthographic side view: 8.672, the clay on stilts; B3b: P3\'s '
                                        '2.644 over the tips, 2.92); the rig lowers it to rest later'),
    'rest.stand': ('[D-b0 from M-ph] [E]', 'B3d (the lead 10-22): the venter\'s lowest point off the ground, the '
                                           'consensus of P2\'s and P3\'s perspective readings (stand_P2_persp, '
                                           'stand_P3_persp), weighted by 1 / stand_sd^2 [E]'),
    'rest.stand_sd': ('[E]', 'B3d: the readings\' spreads, P2 / P3: P2 is an upper bound at its farthest admissible camera '
                             '(a closer one lowers it: 3.3 at D 48, BEETLE_PLAN §2.7 B3d), its body fit 9.8 px rms, its '
                             'horizon row +-8 px (5.38 / 5.56); P3 moves 4.81-5.13 over pitches 10-20.45 deg and +-0.14 '
                             'over +-5 px'),
    'rest.stand_P3_persp': ('[D-b0 from M-ph]', 'B3d: the venter off the ground through P3\'s pinhole camera '
                                                '(arthropod.p3_stand): the camera\'s axis height and the venter solved '
                                                'so P1\'s mid tarsus tips (the claws\' lift up) and the venter\'s midline '
                                                'point project on P3_tip_rows and P3_venter_px'),
    'rest.P3_f_px': ('[D-b0 from M-ph]', 'B3d: P3\'s focal length in px from its EXIF (NIKON COOLPIX S6, FocalLength '
                                         '17.4 mm, its full tele; 1/2.5" CCD 5.744 mm wide on 2816 px: 8530; its 35 mm '
                                         'equivalent 105 mm by the diagonal: 8542), the mean'),
    'rest.P3_EW_px': ('[M-ph]', 'P3\'s elytral width seen from the front (res_c05 EW_front), px'),
    'rest.P3_size': ('[M-ph]', 'P3\'s image size, px (its principal point the centre)'),
    'rest.P3_contact_rows': ('[M-ph]', 'B3d, read on bview.py crops (beetle/scratch_b03d/v_p3_claws_L.png, _R.png): '
                                       'the mid claws\' ground contacts (the claw tips) at rows 1593 / 1585 and the hind '
                                       'claws\' at 1378 / 1388 (blurred, +-8 px), the means (res_c05\'s L2 / L3 claw points '
                                       'sit on the hooks, 1540-1570 / 1352-1367)'),
    'rest.P3_tip_rows': ('[M-ph]', 'P3\'s mid tarsus tips\' rows (B3b re-trace, stand_P3: (243, 1525), (2481, 1521))'),
    'rest.P3_venter_px': ('[M-ph]', 'P3\'s venter on the midline, the silhouette\'s bottom (B3b re-trace, stand_P3)'),
    'rest.P3_pitch': ('[D-b0 from M-ph]', 'B3d: P3\'s camera pitch in perspective (arthropod.p3_pitch): the camera at '
                                          'P3_f_px x EW / P3_EW_px from the elytra\'s widest station, its pitch and '
                                          'axis height so P1\'s mid and hind foot points (the claw tips) project on '
                                          'P3_contact_rows (B3b read 20.45 orthographically against all three pairs; the '
                                          'fore feet are braced forward in the display)'),
    'rest.P3_axis_h': ('[D-b0 from M-ph]', 'B3d: P3\'s camera axis over the ground at the elytral station, from the same '
                                           'solve as P3_pitch'),
    'rest.P2_size': ('[M-ph]', 'P2\'s image size, px (a 35 mm slide scan; its principal point the centre)'),
    'rest.P2_body_px': ('[M-ph]', 'P2\'s body points (res_l01 ely_apex, ely_top, ely_base_top), px (+-6)'),
    'rest.P2_knee_px': ('[M-ph]', 'P2\'s near knees (res_l01 L1-L3_knee), px (+-10, soft focus)'),
    'rest.P2_foot_px': ('[M-ph]', 'P2\'s near tibiae\'s visible ends (res_l01 L1-L3_foot: the litter hides the feet), px'),
    'rest.P2_horizon_px': ('[M-ph]', 'B3d: P2\'s far litter edge behind the beetle, rows 600-616 (beetle/scratch_b03d/'
                                     'v_p2_all.png): a level camera\'s horizon (its pitch from it)'),
    'rest.P2_tol_px': ('[E]', 'B3d: the reconstruction\'s image tolerance on P2\'s knees and feet (the trace\'s +-10 px '
                              'on the blurred near legs)'),
    'rest.P2_D': ('[D-b0 from M-ph]', 'B3d: P2\'s camera distance from the body\'s midline (arthropod.p2_reconstruct): the '
                                      'farthest at which the near mid and hind legs meet the trace on one level ground '
                                      '(the mean over the horizon rows); f = s D (s 22.74 px / mm)'),
    'rest.stand_P2_persp': ('[D-b0 from M-ph]', 'B3d: P2\'s venter off its ground at P2_D (the mean over the horizon '
                                                'rows: 5.38 / 5.56): an upper bound at P2\'s own proportions (a closer '
                                                'camera reads lower)'),
    'rest.tibia_e_P2': ('[D-b0 from M-ph]', 'B3d (d): P2\'s near mid and hind tibiae\'s elevations below the ground in '
                                            'its perspective reconstruction (the mean over the horizon rows): what P2 '
                                            'measures once its camera is undone (its image directions read at another '
                                            'stance\'s plan direction mix two stances)'),
    'rest.femur_e_P2_fore': ('[D-b0 from M-ph]', 'B3d (d): P2\'s near fore femur\'s elevation (its knee on the knee\'s ray '
                                                 'at the femur\'s length from the procoxa joint, the near root): P2\'s fore '
                                                 'foot stands on raised litter (5-7 mm over the mid and hind feet\'s '
                                                 'ground in the reconstruction), so its tibia is no flat-ground '
                                                 'direction; the femur is'),
    'rest.stand_P2_ortho': ('[D-b0 from M-ph]', 'B3c 10-21 (SUPERSEDED, B3d: P2 is a perspective photo): P2\'s venter '
                                          'above its mid and hind ankles (res_l01 L2_foot, '
                                          'L3_foot: the tibiae\'s ends, where the tarsi leave them), the mean, in the '
                                          'body\'s own depth on the same photo (P2_venter_px under res_l01 ely_top = '
                                          'lateral.depth): a side view measures it directly. P2\'s camera is near level '
                                          '(its elytral margin stands 7.2 mm under the top at the depth scale, M1l\'s '
                                          '6.94: a camera 10 deg above would show 5.2). Not verified: P2 stands on '
                                          'litter (its feet may stand lower than the ground under the body) and its '
                                          'venter is dark on dark (+-15 px = +-0.6 mm); by its EL chord it reads 8.96, by '
                                          'its tibiae 5.6-9.4'),
    'rest.P2_venter_px': ('[M-ph]', 'B3c 10-21, read on bview.py grids of P2 (beetle/scratch_b03c/g_p2_venter.png 3x, '
                                    'g_p2_low.png): the body\'s lowest silhouette point between the mid and hind legs, '
                                    'just under the glossy coxae (745-775 px); B1\'s venter-below-margin proportion puts '
                                    'it at 791; px (+-15)'),
    'rest.coxa_h_mh': ('[D-b0 from M-ph] [E]', 'B3c (the lead): the meso- and metacoxa joints (the femur\'s exit) at their '
                                           'OWN height above the venter\'s lowest point: the venter\'s lower surface at '
                                           'the coxa\'s (x, z) (arthropod_parts.venter_descs at clearance 0, the first '
                                           'inside point from below, bisected) + coxa_over_venter. B3b used the '
                                           'procoxa\'s rule for all three (2.45): the femora ran 1.9 mm inside the venter'),
    'rest.coxa_over_venter': ('[E]', 'B3d: mid / hind (the femora now RISE to their knees, the lead\'s B3d gate: from an '
                                     'exit inside the flat mesosternum the mid femur and trochanter ran 0.25-0.35 mm '
                                     'inside the venter for 3 mm, so the venter\'s carve took the femur\'s seat: femur~'
                                     'trochanter 1.36 at x10, b03 _b3dq1; the mid exit now 0.40 UNDER the surface, at the '
                                     'coxa plate\'s face; the hind 0.30 under it: at B3c\'s +0.25 the venter\'s carve '
                                     'left the hind trochanter apart from its coxa, b03 _b3dq3). '
                                     'B3c: the femur\'s exit this far over the venter\'s lower surface: the trochanter '
                                     '(radius 0.5) straddles the surface beside its coxa plate; gate b03 (shells, '
                                     'the femora on the ventral surface)'),
    'rest.claw_drop_P3_px': ('[M-ph]', 'P3\'s mid claw tips meet the ground 66-71 px under the tarsus tips (B3b re-trace, '
                                       'BEETLE_BODY_PHOTOS §7, beetle/scratch_b03b/g_p3_claw*.png)'),
    'rest.P3_elev': ('[M-ph]', 'P3\'s camera above the ground, the mean of its fore / mid / hind ground contacts '
                               'against P1\'s foot spacing, 20.7 / 20.2 deg (plan §2.7)'),
    'rest.claw_stand': ('[D-b0 from M-ph]', 'B3c (the lead: the claws standing on their tips, P3): the mid claw\'s angle '
                                            'below the horizontal, asin(drop / legs.mid.claw), the drop the mean of '
                                            'claw_drop_P3_px at P3\'s EW_front (res_c05) x B1\'s EW, / cos P3_pitch (B3d: '
                                            'P3\'s perspective pitch; B3c / cos P3_elev 20.45: 65.50); every claw stands at '
                                            'it (the claw joint claw x sin up)'),
    'rest.tibia_P2': ('[D-b0 from M-ph]', 'B3c: P2\'s tibiae as IMAGE directions, knee to foot (res_l01 L<i>_knee, '
                                          'L<i>_foot), degrees below the image horizontal measured from forward (P2 '
                                          'faces image-right): the fore and mid ankles stand ahead of their knees, the '
                                          'hind\'s behind (110.3 = 69.7 back). P2 is alert on litter (plan §2.7)'),
    'rest.tibia_P3_px': ('[M-ph]', 'B3c 10-21, traced on bview.py grids of P3 (beetle/scratch_b03c/g_p3_legsL.png, '
                                   'g_p3_legsR.png, g_p3_fore.png): knee (x, y) and ankle (x, y), px, for the fore left, '
                                   'fore right, mid left, mid right tibiae (the knee at the femur\'s tip, the ankle at '
                                   'the tarsal insertion; +-8 px); the hind tibiae hide behind the mid legs'),
    'rest.tibia_P3': ('[D-b0 from M-ph]', 'P3\'s fore and mid tibiae as image directions below the horizontal, '
                                          'measured outward, the mean of both sides from tibia_P3_px (fore 66.2 / 69.9, '
                                          'mid 45.6 / 55.3)'),
    'rest.knee_dir_P1': ('[D-b0 from M-ph]', 'P1\'s knees\' plan directions from the coxae (placement B), the mean of '
                                             'both sides (res_c02 L<i><s>_knee, PW-scaled as the closure reads P1): the '
                                             'femur\'s plan direction yields with P1\'s feet, within femur_band of it'),
    'rest.femur_band': ('[E]', 'B3c: the femur\'s plan direction kept within this of P1\'s knee direction while P1\'s foot '
                                'yields (P1\'s knees stand straight out from the coxae); gate b01\'s foot movement'),
    'rest.ankle_h': ('[E]', 'tarsomeres 1-4 lie FLAT on the ground (plan §2.7, §6.4\'s flat IK neutral; B3c: t5 arches up '
                            'to the claws): their joints at the thinned tarsus\'s half-thickness (B3b 10-21): half the '
                            'widest tarsomere plan width on M1d, the hind t1-t4\'s 0.56 mm (beetle/scratch_b03check/'
                            'leg_widths.py; arthropod_parts TARSO_W), a round section assumed'),
    'rest.stand_P3': ('[M-ph]', 'B3c: printed, no longer the bind (P2\'s side view sets the height; P3 reads 2.644 over '
                                'its tips + the claws\' lift = 4.6-4.8). B3b 10-21, re-traced on bview.py grids '
                                '(BEETLE_BODY_PHOTOS.md §7, beetle/scratch_b03b/'
                                'g_p3_*.png): P3\'s venter on the midline (the silhouette\'s bottom, 1356, 1426 px; the '
                                'photo strand\'s body_low lay 24 px down in the cast shadow) 97.0 px above the line '
                                'through the mid tarsus tips (243, 1525) - (2481, 1521), P1\'s "claw" points, at '
                                'EW_front 683 px = B1\'s EW: 2.644 mm +- 0.14 (+- 5 px). Above the TIPS carries to B1 '
                                'with P1\'s foot points; the venter\'s height above the ground is not read off P3: '
                                'its claws stand steep (their ground contacts 66-71 px under the tips) and its camera '
                                'looks down about 20 deg (its fore / mid / hind ground contacts against P1\'s foot '
                                'spacing: 20.7 / 20.2 deg), so a silhouette point 5 mm off the tips\' depth moves the '
                                'reading 1.7 mm'),
    'rest.coxa_over_procoxa': ('[E]', 'the coxa joint 0.75 above the procoxa\'s lowest point (plan §2.7): it sets the '
                                      'venter\'s clearance'),
    'rest.tibia_dir': ('[D-pl from M-ph]', 'P1\'s tibia plan directions from forward, the mean of both sides '
                                           '(pose.B.<leg>.tibia_dir): B3c, the hind tibia\'s (P3 does not show it; P2 '
                                           'sets its elevation); P2 and P3 set the fore and mid tibiae '
                                           '(arthropod.tibia_from_photos)'),
    'rest.tibia_dir_LR': ('[M-ph]', 'P1\'s own left and right tibia plan directions per leg (res_c02 tib<i>_dir_L / '
                                    '_R, unsigned): printed beside the bind\'s (B3 and B3b chose among them; B3c sets '
                                    'the tibiae from P2 and P3)'),
    'rest.tarsus_dir': ('[D-pl from M-ph]', 'P1\'s tarsus plan directions, the mean of both sides '
                                            '(pose.B.<leg>.tarsus_dir)'),
    'rest.tarsus_plan_PW': ('[D-b0 from M-ph]', 'P1\'s tarsus plan length (ankle to the claw point), the mean of both '
                                                'sides / P1\'s PW (res_c02)'),
    'rest.tibia_plan_PW': ('[D-b0 from M-ph]', 'P1\'s tibia plan length / PW: the PW-scaled foreshortening bound '
                                               '(res_c02)'),
    'rest.tibia_plan_EL': ('[D-b0 from M-ph]', 'P1\'s tibia plan length / EL: the EL-scaled bound, B1\'s gate '
                                               '(res_c02; pose.B.<leg>.tibia_bound_EL)'),
    'rest.claw_span_PW': ('[M-ph]', 'P1\'s "claws" apart, fore / mid / hind (res_c02 claw<i>_span / PW): P1\'s claw '
                                    'point is the TARSUS\'S TIP between the claws (res_c02 notes; the claws hook beyond '
                                    'it, checks/p1_pose_dorsal.png); B3c: P1 yields last, B1\'s tips land nearest it'),
    'rest.claw_z_PW': ('[D-pl from M-ph]', 'P1\'s claw points (the tarsus tips) along the body: fore ahead of the '
                                           'clypeal tip, mid and hind '
                                           'from the elytral base (claws_P1_units.<leg>.z). The fore claws are SIGNED '
                                           'from P1\'s points: the left 0.119 PW ahead, the right 0.047 PW behind '
                                           '(bmeasure.py\'s rows are unsigned; plan_numbers.py fixed in the B1 check '
                                           '10-21: it read 0.0826 PW, plan §2.7 "0.12 / 0.05 PW ahead")'),
    'rest.mid_span_EW': ('[M-ph]', 'P3, the front view: the mid claws apart in EW (res_c05 claw2_span / EW_front)'),
    'rest.antenna_dir': ('[E]', 'the bind\'s scape, funicle and club plan directions from forward: P1 read by eye '
                                '(work/bestiary/beetle/scratch_b01/p1_*_antenna.png, a 50 px grid; right: socket '
                                '(1125, 1045), elbow (1290, 1010), club base (1400, 980), tip (1487, 955); left: '
                                '(655, 1050), (485, 1018), (375, 993), (288, 963)); the plan gives no antenna rest; '
                                'gate: the scape clears the mandible base and the fore femur (plan §6.3)'),
    'rest.antenna_elev': ('[E]', 'the scape raised 20 deg (P1\'s scape plan 0.43 PW against its 0.51 PW length), the '
                                 'funicle and club level; the elbow then 157 deg, inside 30-160'),
    'rest.lamella_fan': ('[E]', 'lamellae closed at the bind (fan 0-30, plan §6.3); P1 shows them fanned: the runtime\'s '
                                'club fanning'),
    # rig
    'rig.neck_h': ('[D-pl from M-ph]', 'the head-prothorax joint at the neck, z -HL, h "about 11" (plan §6.1)'),
    'rig.waist_h': ('[E]', 'the waist (pronotum) joint at the elytral base, z -(BL - EL) (plan §6.1); h midway between '
                           'the pronotum\'s back top (11.89) and the procoxa\'s lowest point (1.70); gate B9: the '
                           'visible waist never over 3 mm'),
    'rig.body': ('[E]', 'body = the thorax centre (plan §6.1): z halfway from the elytral base (-18.35) to behind the '
                        'metacoxae (~-32); h half the body depth there; the root on the ground under it'),
    'rig.abdomen': ('[E]', 'abdomen_0, abdomen_1 and the pygidium: on the abdomen\'s axis behind the metacoxae, under '
                           'the elytra (study T\'s breather pattern [R]); gate B9\'s pumping'),
    'rig.elytron': ('[E]', 'the elytral hinge: under the pronotum\'s hind edge (ANATOMY §4.2), beside the scutellum, '
                           '1 mm under the elytral base\'s top; it turns about Frantsevich\'s axis (azimuth 143, '
                           'elevation 49 [P]), whose frame B9 sets on flight photographs'),
    'rig.elytron_tip_x': ('[E]', 'the elytron\'s bone runs to the apex, 0.25 off the midline (the sutural half gap)'),
    'rig.wing': ('[E]', 'wing_0..2 and the folded tip: the hindwing folded under the elytron, the median and apical '
                        'folds at ~0.5 and ~0.75 of EL, each ~1.5-2 mm under the elytral dorsal line (plan §2.3\'s '
                        'side profile); B14 measures s09 and designs the fold'),
    'rig.coxa_len': ('[E]', 'the coxa\'s own pivot sits medial and dorsal of the femur\'s exit by the coxa\'s length, '
                            'about 1.5-3 mm (plan §6.1): the middle'),
    'rig.coxa_medial': ('[D-b0 from M-ph]', 'M3v: "the coxal pivot lies 0.5-1 mm medial of" the femur\'s exit '
                                            '(res_c07 notes), the middle x B1 / M3 EW (18.617 / 20.187)'),
    'rig.trochanter': ('[E-fo]', 'the trochanter, 2 mm of the coxa-to-knee span (plan_numbers.py\'s parts: "femur '
                                 '(coxa-to-knee less a 2 mm trochanter)")'),
    'rig.pedicel_frac': ('[E]', 'antenna_2 (pedicel / funicle) 1/5 along the funicle: the pedicel is the first of its '
                                '5 beads'),
    'rig.lamella_at': ('[E]', 'the 4 lamellae evenly along the club (fractions of its length)'),
    # allometry
    'allometry.switch_EL': ('[P]', 'Romiti et al. 2017: ML on EL segmented, the switch at EL 22.19 +- 1.01'),
    'allometry.switch_sd': ('[P]', 'Romiti 2017'),
    'allometry.slope_minor': ('[P]', 'Romiti 2017, pooled'),
    'allometry.slope_major': ('[P]', 'Romiti 2017, pooled'),
    'allometry.slope_minor_range': ('[P]', 'Romiti 2017 by population (ANATOMY_NOTES §2.4)'),
    'allometry.slope_major_range': ('[P]', 'Romiti 2017 by population'),
    'allometry.major_anchor': ('[D-pl from M-ph]', 'the major branch runs through B1: (EL, ML at rest) (plan §2.8)'),
    'allometry.minor_anchor': ('[M-an]', 'the minor branch runs through the ETH minor ENT0588987 (plan §2.8)'),
    'allometry.E1_anchor': ('[M-an]', 'E1 = ETHZ-ENT0588937: (EL, ML), measured open (3-8 deg inward)'),
    'allometry.E1_over_B1': ('[D-pl]', 'E1 against B1 at equal EL by the major slope: the individual scatter in the '
                                       'weapon; the large-weapon row (allometry.E1_over_B1)'),
    'allometry.anatomy_rule': ('[D-an]', 'the anatomy strand\'s rule (switch, minor and major ML there), anchored on '
                                         'E1: it predicts 20.62 at B1\'s EL, 1.23x what B1 measures'),
    'allometry.hardersen_PW50': ('[P]', 'Hardersen et al. 2011: 50 % major at PW 1.84 cm; NOT used: by it both '
                                        'photographed majors read as probable minors (plan §2.8)'),
    'allometry.hardersen_PW50_season': ('[P]', 'Hardersen 2011: 1.74 cm early in the season, 1.90 late'),
    'allometry.romiti_mass_g': ('[P]', 'Romiti 2017: male median mass by population'),
    'allometry.romiti_EL_median': ('[P]', 'Romiti 2017: male median EL by population'),
    'allometry.mass_g': ('[D-pl from P]', 'Romiti\'s median male (2.05 g at EL ~22) scaled by EL^3 to B1 '
                                          '(mass.romiti_scaled_g)'),
    'allometry.fill': ('[D-pl from M-ph] [E]', 'mass / (the part model\'s solid volume x 1.05 g/cm3): the subelytral '
                                               'air space, tracheae and shell voids (mass.fill)'),
}

_LM = dict(frons_top='the frons top (the lateral one lies 2.08 behind the dorsal clypeal tip)',
           head_crest='the vertex crest: the head\'s highest point, at its hind edge (socket_crown)',
           head_top_eye='the head top at the eye', head_under_eye='the head under the eye (+-10 px)',
           eye_c='the eye centre', mand_base_dors='the mandible base, dorsal', mand_base_vent='the mandible base, ventral',
           mand_tip='the mandible tip at M1\'s pinned pitch', pron_mid_top='the pronotum top, mid',
           pron_back_top='the pronotum top, back', procoxa_low='the procoxa\'s lowest point (its ventral bulge)',
           ely_base_top='the elytral base, top', ely_top='the elytral top',
           ely_marg_top='the elytral lateral margin\'s highest point', ely_apex='the elytral apex',
           venter='the venter\'s lowest point: h 0')
for _k, _note in _LM.items():
    TAGS[f'landmarks.{_k}'] = ('[D-pl from M-ph]', f'M1l: {_note}; z in the dorsal frame through the shared elytral '
                                                   f'apex, h above the venter (landmarks_M1l.{_k})')

TAG_RE = re.compile(r'\[(P|C|R|H|D|E|S|M)(?:-(?:ph|an|fo|pl|b0|b3))?(?: from [^\]]+)?\]')
MAKER_RE = re.compile(r'\[(M|D)(-(?:ph|an|fo|pl|b0|b3))?[ \]]')

# The leaves' units (b00 checks every leaf has one; morph() scales the 'mm' leaves outside the allometry): the group's
# unit unless listed
UNIT_GROUP = dict(family='text', head_archetype='text', author_scale='1', body='mm', lateral='mm', landmarks='mm',
                  profiles='frac', outline='mm', eye='mm', antenna='mm', mandible='mm', legs='mm', coxae='mm',
                  rest='mm', rig='mm', allometry='mm')
UNIT_KEY = {'lateral.ely_chord_pitch': 'deg', 'eye.splay_LR': 'deg', 'eye.splay': 'deg',
            'outline.mand_outer': 'frac', 'outline.mand_inner': 'frac', 'outline.mand_plan': 'frac',
            'antenna.n_antennomeres': 'count', 'antenna.n_funicle': 'count', 'antenna.n_lamellae': 'count',
            'mandible.sagitta_LR': '1', 'mandible.turn_LR': 'deg', 'mandible.closed_LR': 'deg',
            'mandible.rest_LR': 'deg', 'mandible.fork_frac_LR': 'frac', 'mandible.big_frac_LR': 'frac',
            'mandible.row_frac_L': 'frac', 'mandible.row_frac_R': 'frac', 'mandible.basal_frac_L': 'frac',
            'mandible.basal_frac_R': 'frac', 'mandible.side_pitch': 'deg', 'mandible.dorsal_sagitta': '1',
            'mandible.dorsal_turn': 'deg', 'mandible.depth_at': 'frac', 'mandible.hinge_tilt': 'deg',
            'mandible.open_max': 'deg', 'mandible.closed': 'deg', 'mandible.rest': 'deg', 'mandible.open_rest': 'deg',
            'legs.fore.span_over_tibia_M3': '1', 'legs.mid.span_over_tibia_M3': '1',
            'legs.hind.span_over_tibia_M3': '1', 'rest.tibia_dir': 'deg', 'rest.tibia_dir_LR': 'deg',
            'rest.tarsus_dir': 'deg',
            'rest.tarsus_plan_PW': 'PW', 'rest.tibia_plan_PW': 'PW', 'rest.tibia_plan_EL': 'EL',
            'rest.claw_span_PW': 'PW', 'rest.claw_z_PW': 'PW', 'rest.mid_span_EW': 'EW', 'rest.antenna_dir': 'deg',
            'rest.P2_venter_px': 'px', 'rest.claw_drop_P3_px': 'px', 'rest.tibia_P3_px': 'px', 'rest.P3_elev': 'deg',
            'rest.claw_stand': 'deg', 'rest.tibia_P2': 'deg', 'rest.tibia_P3': 'deg', 'rest.knee_dir_P1': 'deg',
            'rest.femur_band': 'deg', 'legs.fore.tibia_M1l_px': 'px', 'legs.hind.tibia_M1l_px': 'px',
            'rest.P3_f_px': 'px', 'rest.P3_EW_px': 'px', 'rest.P3_size': 'px', 'rest.P3_contact_rows': 'px',
            'rest.P3_tip_rows': 'px', 'rest.P3_venter_px': 'px', 'rest.P3_pitch': 'deg', 'rest.P2_size': 'px',
            'rest.P2_body_px': 'px', 'rest.P2_knee_px': 'px', 'rest.P2_foot_px': 'px', 'rest.P2_horizon_px': 'px',
            'rest.P2_tol_px': 'px', 'rest.tibia_e_P2': 'deg', 'rest.femur_e_P2_fore': 'deg',
            'rest.antenna_elev': 'deg', 'rest.lamella_fan': 'deg', 'rig.pedicel_frac': 'frac',
            'rig.lamella_at': 'frac', 'allometry.switch_EL': 'pop', 'allometry.switch_sd': 'pop',
            'allometry.slope_minor': '1', 'allometry.slope_major': '1', 'allometry.slope_minor_range': '1',
            'allometry.slope_major_range': '1', 'allometry.major_anchor': 'pop', 'allometry.minor_anchor': 'pop',
            'allometry.E1_anchor': 'pop', 'allometry.E1_over_B1': '1', 'allometry.anatomy_rule': 'pop',
            'allometry.hardersen_PW50': 'pop', 'allometry.hardersen_PW50_season': 'pop', 'allometry.romiti_mass_g': 'g',
            'allometry.romiti_EL_median': 'pop', 'allometry.mass_g': 'g', 'allometry.fill': '1'}

# Each leaf's source key in plan_numbers.json ('a.b.c', or a tuple of keys for a tuple value): b00 compares
PLAN_JSON = {
    'body.TL': 'B1.TL', 'body.BL': 'B1.BL', 'body.BLc': 'B1.BLc', 'body.HL': 'B1.HL', 'body.HLc': 'B1.HLc',
    'body.HW': 'B1.HW', 'body.HW_ant': 'B1.HW_ant', 'body.HW_post': 'B1.HW_post', 'body.PL': 'B1.PL',
    'body.PW': 'B1.PW', 'body.PW_front': 'B1.PW_front', 'body.PW_back': 'B1.PW_back', 'body.EL': 'B1.EL',
    'body.EL_sut': 'B1.EL_sut', 'body.EW': 'B1.EW', 'body.EW_hum': 'B1.EW_hum', 'body.scut': 'B1.scut',
    'body.waist': 'waist_gap_M1d', 'lateral.EL_chord': 'B1.EL_chord', 'lateral.depth': 'B1.depth',
    'lateral.ely_side_h': 'B1.ely_side_h', 'lateral.venter_below_margin': 'B1.venter_below_margin',
    'lateral.pron_depth': 'B1.pron_depth', 'lateral.head_h_eye': 'B1.head_h_eye',
    'eye.along': 'B1.eye_along', 'eye.across': 'B1.eye_across', 'eye.eqd': 'B1.eye_eqd', 'eye.sliver': 'B1.eye_sliver',
    'eye.spacing': 'accessories.eyes.spacing_life_mm',
    'eye.splay_LR': ('accessories.eyes.splay_deg[0]', 'accessories.eyes.splay_deg[1]'),
    'antenna.scape': 'B1_antenna.scape.mm', 'antenna.funicle': 'B1_antenna.funicle.mm',
    'antenna.club': 'B1_antenna.club.mm',
    'mandible.chord_LR': ('B1.ML_L', 'B1.ML_R'), 'mandible.outer_LR': ('B1.md_outer_L', 'B1.md_outer_R'),
    'mandible.closed_LR': ('B1.chord_dir_L', 'B1.chord_dir_R'),
    'mandible.rest_LR': ('B1.mand_rest_dir[0]', 'B1.mand_rest_dir[1]'), 'mandible.reach': 'B1.mand_reach',
    'mandible.ML_rest': 'B1.ML_romiti_rest',
    'coxae.pro': ('B1.coxaeB.pro.x', 'B1.coxaeB.pro.z'), 'coxae.meso': ('B1.coxaeB.meso.x', 'B1.coxaeB.meso.z'),
    'coxae.meta': ('B1.coxaeB.meta.x', 'B1.coxaeB.meta.z'),
    'rest.tibia_dir': ('pose.B.fore.tibia_dir', 'pose.B.mid.tibia_dir', 'pose.B.hind.tibia_dir'),
    'rest.tarsus_dir': ('pose.B.fore.tarsus_dir', 'pose.B.mid.tarsus_dir', 'pose.B.hind.tarsus_dir'),
    'rest.claw_z_PW': ('claws_P1_units.fore.z', 'claws_P1_units.mid.z', 'claws_P1_units.hind.z'),
    'allometry.major_anchor': ('B1.EL', 'allometry.B1_rest'), 'allometry.E1_over_B1': 'allometry.E1_over_B1',
    'allometry.mass_g': 'mass.romiti_scaled_g', 'allometry.fill': 'mass.fill',
}
for _p in ('fore', 'mid', 'hind'):
    for _k in ('span_over_tibia_M3', 'claw') + (() if _p == 'fore' else ('tarsus', 'tarsus_claw')):
        PLAN_JSON[f'legs.{_p}.{_k}'] = f'B1_legs.{_p}.{_k}'
    PLAN_JSON[f'legs.{_p}.coxa_knee_plan'] = f'B1_legs.{_p}.coxa_knee'        # B3c: the plan's, kept beside the max
    PLAN_JSON[f'legs.{_p}.tibia_M1d'] = f'B1_legs.{_p}.tibia'
    PLAN_JSON[f'legs.{_p}.tibia_LR'] = (f'B1_legs.{_p}.tibia_LR[0]', f'B1_legs.{_p}.tibia_LR[1]')
    PLAN_JSON[f'legs.{_p}.claw_LR'] = (f'B1_legs.{_p}.claw_LR[0]', f'B1_legs.{_p}.claw_LR[1]')
for _k in ('frons_top', 'head_crest', 'head_top_eye', 'head_under_eye', 'eye_c', 'mand_base_dors', 'mand_base_vent',
           'mand_tip', 'pron_mid_top', 'pron_back_top', 'procoxa_low', 'ely_base_top', 'ely_top', 'ely_marg_top',
           'ely_apex', 'venter'):
    PLAN_JSON[f'landmarks.{_k}'] = (f'landmarks_M1l.{_k}.z', f'landmarks_M1l.{_k}.h')
PLAN_JSON['legs.fore.tarsus_claw_M3'] = 'B1_legs.fore.tarsus_claw'
PLAN_JSON['legs.mid.tarsomeres'] = tuple(f'B1_legs.mid.tarsomeres[{i}]' for i in range(5))
PLAN_JSON['legs.hind.tarsomeres'] = tuple(f'B1_legs.hind.tarsomeres[{i}]' for i in range(5))

# Each leaf's source row in the photo strand's beetle_work/data/res_<id>.json: (id, row, field) per element
RES_JSON = {
    'body.pron_widest': ('s01a', 'pron_angle_pos', 'mm'), 'body.ely_widest': ('s01a', 'ely_widest_pos_L', 'mm'),
    'lateral.TL': ('s01c', 'TL_h', 'mm'), 'lateral.EL_h': ('s01c', 'EL_h', 'mm'),
    'lateral.ely_chord_pitch': ('s01c', 'ely_chord_pitch', '-value'), 'lateral.ely_top_pos': ('s01c', 'ely_top_pos', 'mm'),
    'lateral.ely_top_above_base': ('s01c', 'ely_top_above_base', 'mm'),
    'lateral.apex_below_top': ('s01c', 'apex_below_top', 'mm'), 'lateral.PL': ('s01c', 'PL_h', 'mm'),
    'lateral.pron_front_above_back': ('s01c', 'pron_front_above_back', 'mm'), 'lateral.HL': ('s01c', 'HL_h', 'mm'),
    'lateral.crest_above_head_top': ('s01c', 'crest_above_head_top', 'mm'),
    'lateral.crest_above_ely_top': ('s01c', 'crest_above_ely_top', 'mm'),
    'eye.c_from_frons': ('s01c', 'eye_c_from_frons', 'mm'), 'eye.c_below_top': ('s01c', 'eye_c_below_head_top', 'mm'),
    'mandible.sagitta_LR': (('s01a', 'md_L_outer', 'sagitta_over_chord'), ('s01a', 'md_R_outer', 'sagitta_over_chord')),
    'mandible.turn_LR': (('s01a', 'md_L_outer', 'turn_deg'), ('s01a', 'md_R_outer', '-turn_deg')),
    'mandible.base_span': ('s01a', 'mand_base_span', 'mm'), 'mandible.tips_gap_closed': ('s01a', 'tips_gap', 'mm'),
    'mandible.fork_frac_LR': (('s01a', 'md_L_fork_off', 'frac'), ('s01a', 'md_R_fork_off', 'frac')),
    'mandible.fork_off_LR': (('s01a', 'md_L_fork_off', 'mm'), ('s01a', 'md_R_fork_off', '-mm')),
    'mandible.big_frac_LR': (('s01a', 'md_L_big_off', 'frac'), ('s01a', 'md_R_big_off', 'frac')),
    'mandible.big_off_LR': (('s01a', 'md_L_big_off', 'mm'), ('s01a', 'md_R_big_off', '-mm')),
    'mandible.row_frac_L': (('s01a', 'md_L_row1_off', 'frac'), ('s01a', 'md_L_row0_off', 'frac')),
    'mandible.row_off_L': (('s01a', 'md_L_row1_off', 'mm'), ('s01a', 'md_L_row0_off', 'mm')),
    'mandible.row_frac_R': (('s01a', 'md_R_row1_off', 'frac'), ('s01a', 'md_R_row0_off', 'frac')),
    'mandible.row_off_R': (('s01a', 'md_R_row1_off', '-mm'), ('s01a', 'md_R_row0_off', '-mm')),
    'mandible.basal_frac_L': (('s01a', 'md_L_basal_off', 'frac'), ('s01a', 'md_L_basal2_off', 'frac')),
    'mandible.basal_off_L': (('s01a', 'md_L_basal_off', 'mm'), ('s01a', 'md_L_basal2_off', 'mm')),
    'mandible.basal_frac_R': (('s01a', 'md_R_basal_off', 'frac'),),
    'mandible.basal_off_R': (('s01a', 'md_R_basal_off', '-mm'),),
    'mandible.side_chord': ('s01c', 'ML_lat', 'mm'), 'mandible.side_pitch': ('s01c', 'mand_pitch', '-value'),
    'mandible.tip_below_base': ('s01c', 'mand_tip_below_base', 'mm'),
    'mandible.dorsal_arc': ('s01c', 'md_lat_dorsal', 'mm'),
    'mandible.dorsal_sagitta': ('s01c', 'md_lat_dorsal', 'sagitta_over_chord'),
    'mandible.dorsal_turn': ('s01c', 'md_lat_dorsal', '-turn_deg'),
    'mandible.depth': (('s01c', 'md_depth_prox', 'mm'), ('s01c', 'md_depth_mid', 'mm'), ('s01c', 'md_depth_dist', 'mm')),
    'mandible.tine_gap': ('s01c', 'md_tine_gap', 'mm'),
    'rest.mid_span_EW': ('c05', 'claw2_span/EW_front', 'value'),
    'legs.fore.t1_4': ('s01a', 'L1_L.t1-4', 'mm'), 'legs.fore.t5': ('s01a', 'L1_L.t5', 'mm'),
    'rest.tibia_dir_LR': tuple((('c02', f'tib{_i}_dir_L', '-value'), ('c02', f'tib{_i}_dir_R', 'value'))
                               for _i in (1, 2, 3)),
    'rest.claw_span_PW': (('c02', 'claw1_span/PW', 'value'), ('c02', 'claw2_span/PW', 'value'),
                          ('c02', 'claw3_span/PW', 'value')),
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
    """the keys whose value has no source tag in the plan's legend (empty when the SPEC is fully tagged), and the
    tag keys that name no value"""
    tags = TAGS if tags is None else tags
    keys = [k for k, _ in leaves(spec)]
    missing = [k for k in keys if k not in tags or not TAG_RE.search(tags[k][0])]
    stale = sorted(set(tags) - set(keys))
    return missing, stale


def makerless(tags=None):
    """the keys with an [M] or [D] tag that carries no maker (the plan's rule: every [M] and [D] can be rerun)"""
    tags = TAGS if tags is None else tags
    return sorted(k for k, (t, _) in tags.items() for m in MAKER_RE.finditer(t + ' ') if not m.group(2))


def unit(key):
    """a leaf's unit: mm, deg, frac, PW, EL, EW, count, g, pop (a population constant), 1 or text"""
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


# --------------------------------------------------------------------------------------------- the allometry
def ml_minor(EL, spec=None):
    """Romiti's ML on the minor branch, through the ETH minor (plan §2.8)"""
    a = (SPEC if spec is None else spec)['allometry']
    el0, ml0 = a['minor_anchor']
    return ml0 * (EL / el0) ** a['slope_minor']


def ml_major(EL, spec=None):
    """Romiti's ML on the major branch, through B1 at its live rest angle (plan §2.8)"""
    a = (SPEC if spec is None else spec)['allometry']
    el0, ml0 = a['major_anchor']
    return ml0 * (EL / el0) ** a['slope_major']


def morph_of(EL, spec=None):
    """'minor' below Romiti's switch, 'major' at or above it: morphs key on EL, never on Hardersen's PW"""
    return 'minor' if EL < (SPEC if spec is None else spec)['allometry']['switch_EL'] else 'major'


def ml(EL, spec=None):
    """Romiti's ML at EL: the minor branch below the switch, the major above (the step at the switch -0.26 mm)"""
    return ml_minor(EL, spec) if morph_of(EL, spec) == 'minor' else ml_major(EL, spec)


# --------------------------------------------------------------------------------------------- the morphs (B12)
# Each morph: the length scale (its EL over B1's), a vertical scale where a side view measured one, then its measured
# rows (key: (value, tag, note)). morph() scales every 'mm' leaf outside the allometry, sets the rows, and remaps the
# landmarks', coxae's and rig's z piecewise (head, prothorax with the waist, hind body) onto the morph's own HL, PL +
# waist and EL, so its stations sit where its measures put them. Unmeasured shape (the minor's thickset mandible, the
# female's head landmarks, E1's head front) stays the scaled male's until B12 fits each part to its photographs.
_S1 = 'S1 (RMNH.INS.1488349, no scale) in its own EL x Em\'s EL 19.5 (res_s08)'
_F1 = 'F1 (NHMUK013741596, card 42.558 px/mm, res_s05g)'
_E1 = 'E1\'s ratio to its PW 16.0 (ANATOMY_NOTES §2.3) x B1\'s PW'
MORPHS = dict(
    minor=dict(
        what='the minor male: S1\'s shape on the ETH minor\'s EL (19.5), the minor branch\'s mandible: "thickset, '
             'little curved, teeth barely outlined" [C]; HW/PW 0.89-0.90 (plan §2.8)',
        EL=19.5, vertical=None,
        set={
            'body.EL': (19.5, '[M-an]', 'Em = ENT0588987, manual +-0.35 mm: the minor branch\'s anchor'),
            'body.TL': (39.028, '[D-b0 from M-ph]', _S1 + ': TL/EL 2.001 (Em\'s own TL 41.4 [M-an])'),
            'body.BL': (32.370, '[D-b0 from M-ph]', _S1 + ': BL/EL 1.660'),
            'body.HL': (5.719, '[D-b0 from M-ph]', _S1 + ': HL 0.485 PW'),
            'body.HW': (10.499, '[D-b0 from M-ph]', _S1 + ': HW/PW 0.890 (Em 0.904 [M-an])'),
            'body.HW_post': (8.789, '[D-b0 from M-ph]', _S1 + ': HW_post/PW 0.745'),
            'body.PL': (6.941, '[D-b0 from M-ph]', _S1 + ': PL/PW 0.589'),
            'body.PW': (11.793, '[D-b0 from M-ph]', _S1 + ': EL/PW 1.653 (Em\'s PW 12.5 [M-an])'),
            'body.PW_front': (10.325, '[D-b0 from M-ph]', _S1 + ': 0.875 PW'),
            'body.PW_back': (11.056, '[D-b0 from M-ph]', _S1 + ': 0.938 PW'),
            'body.EW': (14.092, '[D-b0 from M-ph]', _S1 + ': EW/PW 1.195, EW/EL 0.723'),
            'body.EW_hum': (12.105, '[D-b0 from M-ph]', _S1 + ': 0.859 EW'),
            'body.ely_widest': (7.749, '[D-b0 from M-ph]', _S1 + ': at 0.397 EL'),
            'body.scut': (1.500, '[D-b0 from M-ph]', _S1 + ': 0.077 EL'),
            'body.waist': (0.5, '[M-an]', 'Em\'s visible neck'),
            'mandible.chord_LR': ((7.347, 7.190), '[D-b0 from M-ph]', _S1 + ': chords 0.377 / 0.369 EL (plan §2.8 '
                                                                         '"mandible chord / EL 0.373")'),
            'mandible.chord': (7.268, '[D-b0 from M-ph]', 'the mean'),
            'mandible.reach': (6.658, '[D-b0 from M-ph]', _S1 + ': the tips meeting over the midline, 0.341 EL'),
            'mandible.base_span': (7.150, '[D-b0 from M-ph]', _S1 + ': 0.367 EL'),
            'mandible.ML_rest': (8.9, '[M-an]', 'Em\'s ML: the minor branch at EL 19.5'),
        }),
    female=dict(
        what='the female, a SPEC variant (sex, not size, sets her shape: plan §0.2): F1\'s own head, pronotum and '
             'mandibles, her body depth from F1l; legs and the rest scaled by her EL until B12 measures them',
        EL=23.913, vertical=('lateral.depth', 13.409),
        set={
            'body.TL': (38.815, '[M-ph]', _F1 + ': TL (Ef 38.8 [M-an])'),
            'body.BL': (36.423, '[M-ph]', _F1 + ': BL'),
            'body.HL': (3.783, '[M-ph]', _F1 + ': HL 0.261 PW'),
            'body.HW': (9.259, '[M-ph]', _F1 + ': HW 0.639 PW (Ef 0.601 [D-an])'),
            'body.HW_post': (9.326, '[M-ph]', _F1 + ': widest behind'),
            'body.PL': (8.368, '[M-ph]', _F1 + ': PL 0.577 PW'),
            'body.PW': (14.497, '[M-ph]', _F1 + ': PW (Ef 15.8 [M-an])'),
            'body.PW_front': (9.397, '[M-ph]', _F1 + ': the pronotum\'s front 0.648 PW, against 0.875-0.929 in males'),
            'body.PW_back': (13.936, '[M-ph]', _F1 + ': hind 0.961 PW: widest behind'),
            'body.pron_widest': (5.666, '[M-ph]', _F1 + ': 0.677 PL behind the neck'),
            'body.EL': (23.913, '[M-ph]', _F1 + ': EL (Ef 22.7 [M-an])'),
            'body.EW': (17.058, '[M-ph]', _F1 + ': EW'),
            'body.EW_hum': (16.140, '[M-ph]', _F1 + ': humeri 0.946 EW'),
            'body.ely_widest': (10.321, '[M-ph]', _F1 + ': widest at 0.432 EL'),
            'body.scut': (3.336, '[M-ph]', _F1 + ': 0.140 EL'),
            'body.waist': (0.0, '[M-an]', 'Ef: no visible neck'),
            'lateral.EL_chord': (25.013, '[D-b0 from M-ph]', 'F1l: chord / horizontal 1.046 x her dorsal EL (F1l\'s bar '
                                                             'plane is unknown: ratios only, res_s05e)'),
            'lateral.depth': (13.409, '[D-b0 from M-ph]', 'F1l: depth 0.536 of the chord'),
            'lateral.ely_chord_pitch': (17.062, '[M-ph]', 'F1l: pinned'),
            'lateral.ely_top_pos': (4.647, '[D-b0 from M-ph]', 'F1l: the top at 0.186 of the chord'),
            'lateral.ely_top_above_base': (0.671, '[D-b0 from M-ph]', 'F1l: 0.027 of the chord'),
            'lateral.apex_below_top': (8.010, '[D-b0 from M-ph]', 'F1l: 0.320 of the chord'),
            'mandible.chord_LR': ((3.593, 2.967), '[M-ph]', _F1 + ': short, hooked inward, one inner tooth each'),
            'mandible.chord': (3.280, '[D-b0 from M-ph]', 'the mean'),
            'mandible.reach': (2.393, '[M-ph]', _F1 + ': tips 62 px apart'),
            'mandible.base_span': (6.181, '[M-ph]', _F1),
            'mandible.ML_rest': (2.393, '[E]', 'no ML measured on a female (Ef\'s closed mandibles cover the clypeus): '
                                               'her reach stands in; B12'),
        }),
    E1=dict(
        what='the large-weapon major: B1\'s body (they agree within 0.9 % on every non-weapon ratio) with E1\'s head '
             '(HW/PW 1.30, widest behind the eyes: the postocular lobes) and the mandible row x1.231 at B1\'s EL '
             '(plan §0.3, §2.4, §6.7)',
        EL=None, vertical=None,
        set={
            'body.HW': (20.346, '[D-b0 from M-an]', _E1 + ': HW 20.8 at the postocular angles'),
            'body.HW_post': (20.346, '[D-b0 from M-an]', 'E1 is widest behind the eyes (e0588937_headpro.png)'),
            'body.HLc': (9.488, '[D-b0 from M-an]', _E1 + ': 9.7 to the frons edge'),
            'body.HL': (12.032, '[D-b0 from M-an]', _E1 + ': 12.3 to the clypeal process tip (~2.5 proud)'),
            'body.BL': (45.948, '[D-b0]', 'B1\'s BL + the head\'s extra 2.361: B1\'s body behind the neck'),
            'body.BLc': (43.404, '[D-b0]', 'B1\'s BLc + the extra 0.841 to the front margin'),
            'body.TL': (65.414, '[D-b0]', 'BL + the pinned reach 19.466 (E1\'s own TL 71.7 [M-an], at EL 25.9 and '
                                          'measured open)'),
            'mandible.chord_LR': ((21.985, 21.166), '[D-b0 from D-pl]', 'B1\'s x E1_over_B1 1.2307'),
            'mandible.outer_LR': ((25.851, 23.874), '[D-b0 from D-pl]', 'B1\'s x 1.2307'),
            'mandible.chord': (21.576, '[D-b0 from D-pl]', 'B1\'s mean x 1.2307'),
            'mandible.outer': (24.863, '[D-b0 from D-pl]', 'B1\'s mean x 1.2307'),
            'mandible.reach': (19.466, '[D-b0 from D-pl]', 'B1\'s x 1.2307'),
            'mandible.ML_rest': (20.573, '[D-b0 from D-pl]', 'B1\'s 16.717 x 1.2307: E1\'s 22.4 at EL 25.9 brought to '
                                                             'B1\'s EL by the major slope'),
            'mandible.side_chord': (22.978, '[D-b0 from D-pl]', 'B1\'s x 1.2307'),
            'mandible.dorsal_arc': (24.294, '[D-b0 from D-pl]', 'B1\'s x 1.2307'),
            'mandible.width': (3.25, '[M-an]', 'ENT0588940 (TL 69.7, E1\'s size): 3.0-3.5, the middle'),
        }),
)


def _remap_z(z, old, new):
    """a z (life mm, the plan frame) carried piecewise-linearly from the stations old to new (each a descending
    tuple: 0, -HL, -(BL - EL), -BL); ahead of the first and behind the last station it shifts with that station"""
    if z >= old[0]:
        return z - old[0] + new[0]
    for k in range(len(old) - 1):
        a0, a1, b0, b1 = old[k], old[k + 1], new[k], new[k + 1]
        if z >= a1:
            return b0 + (z - a0) * (b1 - b0) / (a1 - a0)
    return z - old[-1] + new[-1]


def _stations(spec):
    b = spec['body']
    return (0.0, -b['HL'], -(b['BL'] - b['EL']), -b['BL'])


def morph(name):
    """(spec, tags): the morph's full SPEC and its tags (B1's, with the morph's rows retagged). name in MORPHS or
    'B1'"""
    spec, tags = copy.deepcopy(SPEC), dict(TAGS)
    if name == 'B1':
        return spec, tags
    m = MORPHS[name]
    s = 1.0 if m['EL'] is None else m['EL'] / SPEC['body']['EL']
    sv = s if m['vertical'] is None else m['vertical'][1] / get(SPEC, m['vertical'][0])
    for key, v in leaves(SPEC):
        if unit(key) != 'mm' or key.startswith('allometry.') or s == 1.0:
            continue
        if key.startswith('landmarks.'):
            put(spec, key, (v[0] * s, v[1] * sv))
        elif isinstance(v, tuple) and v and isinstance(v[0], tuple):
            put(spec, key, tuple(tuple(x * s for x in row) for row in v))
        elif isinstance(v, tuple):
            put(spec, key, tuple(x * s for x in v))
        else:
            put(spec, key, v * s)
        tags[key] = ('[D-b0]', f'B1\'s x {s:.4f} (the morph\'s EL / B1\'s): ' + TAGS[key][1])
    old = _stations(spec)
    for key, (v, tag, note) in m['set'].items():
        put(spec, key, v)
        tags[key] = (tag, note)
    new = _stations(spec)
    if old != new:
        for k, (z, h) in spec['landmarks'].items():
            if k == 'mand_tip':
                continue
            spec['landmarks'][k] = (_remap_z(z, old, new), h)
        mt = spec['landmarks']['mand_tip']
        spec['landmarks']['mand_tip'] = (spec['mandible']['reach'], mt[1])
        for k, (x, z) in spec['coxae'].items():
            spec['coxae'][k] = (x, _remap_z(z, old, new))
        r = spec['rig']
        r['body'] = (_remap_z(r['body'][0], old, new), r['body'][1])
        r['abdomen'] = tuple((_remap_z(z, old, new), h) for z, h in r['abdomen'])
        r['elytron'] = (r['elytron'][0], _remap_z(r['elytron'][1], old, new), r['elytron'][2])
        r['wing'] = tuple((x, _remap_z(z, old, new), h) for x, z, h in r['wing'])
        for k in ('landmarks.' + n for n in spec['landmarks']):
            tags[k] = ('[D-b0]', tags[k][1] + ' (z remapped onto the morph\'s HL, PL + waist and EL)')
    return spec, tags
