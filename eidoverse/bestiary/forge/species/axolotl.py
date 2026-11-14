"""AXOLOTL (Ambystoma mexicanum, adult, wild type): the Bestiary's wet-skinned base (work/bestiary/research/
AXOLOTL_PLAN.md). A1, the design animal, is the literature's mean adult (SEMARNAT 2018 citing Ramirez-Bautista et al.
2009: SVL 133.3, tail 108.3, TL 241.6 mm) shaped by p01, the one true lateral with the vent seen (plan §2); the tail's
depth is p08's, the plan widths the radiograph p09's, the head box p13's, the filaments p17's, the hindlimb g06's.

AX0 (10-27) carries plan §2's SPEC with its tags, gill_scale, the zones and the morph palettes; AX0b's readings (the
forelimb from g06's loose forelimbs, the mouth corner, the eye's station, the tail's core, the gill postures, the trunk's
width, the grooves, the venter, the digits, the Zittau clip) are rows of their own beside the plan's, never written over
them: the plan's value and the reading stand side by side, and rig / rest say which one AX1 builds.

AX1 (10-28, families/sprawl.py, tests/ax01_skeleton.py) builds the bind and the 124-joint skeleton from rig / rest: the
humerus's retraction is SOLVED there (the palms rest.hands_apart_target_HW apart), not stored; the hand's carpus and the
foot's metatarsal are AX0b readings on g06 (hand_foot_split_g06), the rest of each split an estimate.

AX2b (10-28, the lead's one clay fix): r3 raised to +3 deg in the bind (gills.u_r3_x2b, a design row beside the plan's
u_r3) and the palms at 1.64 HW (rest.hands_apart_target_HW), so r3's comb clears the upper arm; the rami's taper and
fleshy roots are families/sprawl.CLAY's.

UNITS: LIFE MILLIMETRES, TL fractions (s, from the snout tip along the midline) and degrees, as each group's UNIT says.
The family generator (families/sprawl.py) multiplies once by SPEC['author_scale'] = 4: A1 is built and exported at x4
(0.966 m) with extras.bestiary.life_scale 0.25 (plan §5.3). THE PLAN FRAME (DESIGN.md): +Z forward, +Y up, +X the
creature's LEFT; the bind stands on y = 0. Every sided value is the LEFT side's; the right is its mirror p_R = M p_L.

TAGS holds every leaf's source (plan "Tags"): [P] a photo reading (photo named), [L] literature, [R] a game-repo
reading, [H] a house file, [C] textbook knowledge not in the sweep's sources, [E] an estimate with the gate that checks
it, [D] derived. Every [D] carries its maker: -ap printed by the plan's research/axolotl_work/plan/aplan_numbers.py
(APLAN maps each leaf to its line; tests/ax00_spec.py runs the script and compares), -x0 derived HERE from the AX0b
readings (research/axolotl_work/ax0b/ax0b_readings.json) by a rule ax00_spec.py recomputes, -sw the sweep's own
arithmetic in res_photos.json. [P] leaves with a value in the sweep's data files are listed in RES (ax00 compares).
TAG_RE is this species' own.
"""
import re

AUTHOR_SCALE = 4.0

SPEC = dict(
    family='limbed', body_plan='sprawl', head_archetype='caudate', author_scale=AUTHOR_SCALE, life_scale=0.25,
    # ---- A1, the literature's mean adult (SEMARNAT 2018 p. 38): plan §2.1
    a1=dict(SVL=133.3, tail=108.3, TL=241.6, HL=42.7, HW=37.9, tail_height=25.8,
            SVL_sd=12.5, tail_sd=11.9, HL_sd=3.4, HW_sd=4.2, tail_height_sd=0.29),
    ratios=dict(SVL_TL=0.5517, HL_TL=0.1767, HW_HL=0.888, tail_height_TL=0.1068, HW_SVL=0.284,
                TL_x4=966.0, HL_x4=170.8, HW_x4=151.6, tail_height_x4=103.2),
    # ---- stations, fractions of TL from the snout tip: plan §2.1 (+ AX0b)
    stations=dict(naris=0.011, eye_c=0.048, eye_c_x0b=0.040, mouth_p01=0.037, commissure_plan=0.085,
                  commissure=0.080, commissure_lower=0.044, jaw_hinge=0.100, head_joint=0.110, head_joint_plan=0.115,
                  poll=0.125, throat=0.140, neck=0.160, gular_fold=0.176, gular_fold_plan=0.1675, gill_base=0.177,
                  shoulder=0.198, shoulder_joint=0.200, shoulder_p08=0.204, fin_origin=0.205, groin=0.448, hip=0.465,
                  hip_plan=0.490, hip_p01=0.4803, hip_p08=0.5121, vent=0.552, skull_end_mm=26.55,
                  skull_end_mm_plan=27.9),
    station_map=dict(head=0.991, trunk=1.083, tail=0.943),
    # ---- the side profile, fractions of TL: plan §2.2 (+ AX0b's tail core)
    profile=dict(
        core=((0.02, 0.0490), (0.04, 0.0644), (0.06, 0.0758), (0.08, 0.0858), (0.10, 0.0945), (0.12, 0.1028),
              (0.15, 0.1094), (0.18, 0.1145), (0.20, 0.1204), (0.25, 0.1217), (0.30, 0.1211), (0.35, 0.1195),
              (0.40, 0.1168), (0.45, 0.1136), (0.50, 0.1102)),
        dorsal_fin=((0.20, 0.0), (0.25, 0.0110), (0.30, 0.0140), (0.35, 0.0163), (0.40, 0.0198), (0.45, 0.0234),
                    (0.50, 0.0260)),
        tail_total=((0.552, 0.1111), (0.600, 0.1079), (0.632, 0.1083), (0.650, 0.1073), (0.700, 0.1036),
                    (0.750, 0.0968), (0.800, 0.0861), (0.850, 0.0713), (0.900, 0.0538), (0.950, 0.0323),
                    (0.980, 0.0173)),
        fin_scale=0.675, tail_core_share=0.55,
        tail_core_TL_x0b=((0.6070, 0.0913), (0.6589, 0.0744), (0.7108, 0.0605), (0.7627, 0.0561), (0.8146, 0.0500),
                          (0.8665, 0.0478), (0.9433, 0.0132)),
        tail_core_share_x0b=((0.6070, 0.846), (0.6589, 0.697), (0.7108, 0.593), (0.7627, 0.596), (0.8146, 0.611),
                             (0.8665, 0.729), (0.9433, 0.375)),
        tail_core_share_p01=(0.582, 0.469, 0.397, 0.398, 0.400, 0.472, 0.218),
        head_side_x2=((0.0, 0.0, 0.0), (0.0025, 0.0099, -0.0042), (0.005, 0.0137, -0.0085), (0.01, 0.0183, -0.0175),
                      (0.015, 0.0223, -0.0210), (0.02, 0.0257, -0.0235), (0.03, 0.0316, -0.0265),
                      (0.04, 0.0365, -0.0285), (0.05, 0.0408, -0.0301), (0.06, 0.0449, -0.0317),
                      (0.07, 0.0489, -0.0332), (0.08, 0.0520, -0.0344), (0.09, 0.0549, -0.0355),
                      (0.10, 0.0578, -0.0366), (0.11, 0.0604, -0.0384), (0.12, 0.0623, -0.0407),
                      (0.13, 0.0629, -0.0431), (0.14, 0.0630, -0.0450), (0.15, 0.0628, -0.0468),
                      (0.16, 0.0624, -0.0486), (0.17, 0.0617, -0.0510), (0.18, 0.0616, -0.0534)),
        head_pitch_p01_x2=17.87,
        fin_call_x2='tail_total', fin_scale_x2=0.3939, fin_blend_x2=(0.50, 0.60)),
    # ---- plan widths: plan §2.3 (+ AX0b)
    widths=dict(head_widest_s=0.0993, trunk_HW=0.95, trunk_mm=36.0, trunk_HW_p09=1.196, trunk_HW_p09_lit=1.108,
                trunk_HW_p12=0.650, radiograph_g_at_A1=123.6, gamel_g_at_A1=93.6, pelvis_HW=0.755, pelvis_mm=28.6,
                tailbase_HW=0.472, tailbase_mm=17.9, HW_SVL_p09=0.263,
                profile_x2=((0.025, 0.6727), (0.03, 0.7026), (0.035, 0.7271), (0.04, 0.7536), (0.045, 0.7669),
                            (0.05, 0.7847), (0.06, 0.8248), (0.07, 0.8631), (0.08, 0.9061), (0.09, 0.9431),
                            (0.10, 0.9656), (0.11, 0.9750), (0.12, 0.9768), (0.13, 0.9785), (0.14, 0.9846),
                            (0.15, 0.9950), (0.16, 1.0000), (0.17, 0.9953), (0.18, 0.9854), (0.19, 0.9734),
                            (0.20, 0.9633), (0.21, 0.9598), (0.22, 0.9718), (0.23, 1.0171), (0.24, 1.0229),
                            (0.26, 1.0281), (0.28, 1.0332), (0.30, 1.0384), (0.32, 1.0486), (0.34, 1.0798),
                            (0.36, 1.0844), (0.38, 1.0701), (0.40, 1.0257), (0.42, 0.9815), (0.44, 0.9305),
                            (0.46, 0.8638), (0.48, 0.7910), (0.50, 0.7384), (0.51, 0.7001), (0.53, 0.6803),
                            (0.55, 0.6538), (0.56, 0.5716), (0.57, 0.5039), (0.58, 0.4682), (0.59, 0.4472),
                            (0.60, 0.4315), (0.61, 0.4212), (0.62, 0.4183), (0.635, 0.4193)),
                trunk_HW_x2=1.0844, head_widest_s_x2=0.16),
    # ---- the head: plan §2.4 (+ AX0b)
    head=dict(height_HW=0.740, height_mm=28.1, eyes_apart_HW=0.494, eyes_apart_mm=18.7, eye_frontal=(0.356, 0.246),
              eye_d_TL=0.0163, eye_d_mm=3.94, eye_d_range=(0.0158, 0.0174), nares_apart_HW=0.334,
              naris_frontal=(0.474, 0.167), mouth_w_HW=0.893, mouth_w_mm=33.8, mouth_frontal=(0.613, 0.446),
              cheek_frontal=0.566, skull_len_g06=28.65, skull_W_g06=(23.46, 26.75), skull_WL=(0.82, 0.93),
              skull_len_A1=25.05, skull_len_A1_plan=26.4, iris_ring=0.6, pupil=0.35,
              eye_HL_x0b=(0.2278, 0.1796, 0.2123, 0.2416, 0.2741), commissure_HL_x0b=(0.4530, 0.2510)),
    # ---- the gills: plan §2.5 (+ AX0b's p18 posture and the Zittau clip)
    gills=dict(gill_scale=1.0, gill_scale_range=(0.7, 1.3),
               frontal_r1=(0.427, 0.456), frontal_r2=(0.340, 0.296), frontal_r3=(0.218, 0.311),
               emergence_r1=(0.162, 0.395), emergence_r2=(0.315, 0.473), emergence_r3=(0.445, 0.500),
               frontal_deg=(4.3, 41.3, 90.2), side_TL=(0.0542, 0.0598), side_elev=(9.3, -9.5),
               chord=(24.0, 16.0, 18.5), chord_raw=(20.9, 15.3, 17.6),
               chord_115=(24.0443850823, 15.9823470911, 18.4796295298),
               u_r1=(0.0602856026, 0.7977252949, 0.6000000000), u_r2=(0.5733308288, 0.6520023111, 0.4961700788),
               u_r3=(0.6235085400, -0.0016494819, 0.7818147989),
               u_r3_x2b=(0.6226548903, 0.0523359562, 0.7807444110),
               lower_bound=(19.2, 13.9, 14.4), lower_bound_raw=(16.7, 13.1, 14.4), r2_up_check=(9.1, 10.4, 2.1),
               perspective=1.15, r1_back=0.60, similar=(1.0, 0.6667, 0.7708), ramus_D=7.1022, root_D=1.3,
               D_mm=(3.39, 2.25, 2.60), filament_len_D=1.4931, filament_w_D=0.0741, filament_spacing_D=0.247,
               ranks=2, comb=0.80, per_rank=23, per_ramus=46, total=276, lod0_tris=66, lod1_tris=20,
               lod0_total=18216, lod1_total=5520,
               p18_elev=(59.66, 13.24, 23.78), p18_L_HL=(0.2560, 0.3764, 0.3474), p18_head_axis=10.27,
               rest_motion='still, flared'),
    # ---- the trunk: plan §2.6 (+ AX0b)
    trunk=dict(grooves=10, grooves_alt=11,
               groove_stations=(0.225, 0.244, 0.264, 0.285, 0.307, 0.329, 0.353, 0.378, 0.403, 0.430),
               groove_stations_11=(0.225, 0.242, 0.260, 0.278, 0.298, 0.318, 0.339, 0.360, 0.383, 0.406, 0.430),
               groove_spacing=(0.0195, 0.0274), groove_spacing_p01=(0.0253, 0.0225, 0.022, 0.0209, 0.0209, 0.0185,
                                                                     0.018),
               groove_mean=0.0212, groove_depth=(0.3, 0.5), crease_over_spacing=(0.05, 0.15, 0.20),
               section=(36.0, 29.0)),
    # ---- the fins and the tail: plan §2.7
    fins=dict(ventral_from='vent', half_thickness=(0.5, 0.12), backlit_ratio=(6.0, 8.0),
              backlit_Ylin=(0.1955, 0.2437, 0.0315)),
    # ---- the limbs: plan §2.8 (+ AX0b's g06 forelimbs and max-projection hindlimb)
    limbs=dict(upper_arm_p01=9.5, forearm_p01=10.1, hand_p01_min=4.5, hand_plan_TL=0.025, k06=0.922, g06_bony=126.8,
               femur=14.6, tibia=12.2, tarsus=8.7, mt_digit=17.2, adpressed=(25.6, 52.7, 78.3, 69.7, 8.6),
               humerus_x0b=16.8102, forearm_x0b=9.6333, hand_x0b=15.2716, femur_x0b=14.9395, tibia_x0b=12.2645,
               adpressed_x0b=(41.7151, 51.7680, 63.6737, 29.8094),
               k06_x2=0.874164, tarsus_x2=8.2696, mt_digit_x2=16.2944,
               radii=dict(upper_arm=2.0, forearm=1.6, thigh=2.6, shank=2.0, tarsus=1.5, digit=0.5),
               radii_x2=dict(upper_arm=2.45, forearm=2.15, thigh=3.0, shank=2.3, tarsus=1.7, digit=0.55),
               digits=(4, 5), hands_apart_HW=1.221, hands_apart_max_HW=1.8,
               phalanges=((1, 2, 3, 2), (1, 2, 3, 3, 2)), finger_rel=(0.45, 0.85, 1.0, 0.75),
               toe_rel=(0.40, 0.70, 0.95, 1.0, 0.65), webbing='none seen'),
    # ---- the skin: plan §2.9
    skin=dict(epidermis=(0.11, 0.12), leydig=(0.04, 0.03), spongiosum=0.19, compactum=0.06, whole=0.37, f0=0.020,
              f0_salamandretta=0.028, rough_body=(0.09, 0.20, 0.36), rough_head=(0.01, 0.14, 0.29),
              rough_limbs=(0.12, 0.17, 0.34), rough_fins=(0.02, 0.16, 0.29), rough_dorsum_venter=(0.17, 0.24),
              micro_tile=12.0, micro_strength=0.5),
    # ---- colour, palette data from uncalibrated photos: plan §2.10 (+ AX0b's venter)
    colour=dict(wild_flank='#363034', wild_flank_dark='#2D292D', wild_flank_light='#443D41', wild_head='#4B4240',
                wild_tail_trans='#907563', wild_fin_trans='#AA7E63', wild_filaments='#544346',
                gold_field='#B9A366', p06_flank='#616766', p06_gills='#22272B', p06_tail='#31342C',
                leucistic_body='#D7B3B4', leucistic_head='#E8CAC3', leucistic_gills='#C9787E',
                albino_body='#EFEDEB', albino_gills='#EAB4B0', venter_lit_p16='#C1CFBB', throat_p16='#A5A29C',
                flank_dark_share=0.583, spot_TL=0.0051, spot_nn_TL=0.0169, gold_hsv=(44.1, 0.449, 0.725)),
    # ---- the morphs: plan §5.11's composition, one texture set (M melanin cover, X xanthophore, I iridophore)
    morphs=dict(
        wild=dict(M=1.0, X=1.0, I=1.0, thin='#907563', eye='dark pupil, gold ring'),
        leucistic=dict(M=0.0, X=0.0, I=0.0, thin='#C9787E', eye='dark'),
        white_albino=dict(M=0.0, X=0.3, I=0.0, thin='#EAB4B0', eye='pink'),
        golden_albino=dict(M=0.0, X=1.5, I=1.5, thin='#D9A58A', eye='pink, gold iris'),
        melanoid=dict(M=1.4, X=0.3, I=0.0, thin='#3A2E2C', eye='dark, no ring'),
        axanthic=dict(M=1.0, X=0.0, I=0.0, thin='#6B6460', eye='dark')),
    # ---- motion facts: plan §2.11
    motion=dict(walk_TL_s=0.30, walk_mm_s=(77.0, 30.0), walk_TL_mm=257.0, contact=(36.3, 51.2), buoyancy=97.6,
                cycle_stride_TL=(0.60, 0.75), swim_wavelength=0.60, swim_amp=0.097, swim_stride=0.345,
                swim_max=3.3, swim_voluntary=1.0, swim_hz=(0.87, 2.90, 9.57), body_wave=(0.52, 1.74, 5.74),
                slip=0.57, tip_curvature=10.64, tip_radius_TL=0.094, tip_radius_mm=22.7, tail_step=0.0374,
                deg_per_tail_joint=22.8, gill_flutter_hz=0.0),
    # ---- the skeleton's places and ranges (plan §4.1); AX1 (families/sprawl.py) builds from these
    rig=dict(n_joints=124, n_spine=7, spine_from=0.490, spine_to=0.200, n_tail=12, tail_from=0.552, tail_to=0.963,
             gill_joints=4, shoulder_x=15.0, hip_x=12.0, glenoid_frac=0.30, acetabulum_frac=0.35, spine_frac=0.58,
             head_frac=0.55, jaw_frac=0.387, scapula_rise=8.0, scapula_x=10.0, carpus_len=2.3231, metacarpal=5.0,
             metatarsal=5.5639, palm_w=4.4, sole_w=6.0, digit_splay=(-30.0, -10.0, 10.0, 30.0),
             toe_splay=(-36.0, -18.0, 0.0, 18.0, 36.0), eye_r=1.97, eye_below_top=3.2, eye_axis=(0.6048, 0.6747, 0.4230),
             gill_base_inset=0.95, palm_h=0.9, sole_h=0.9, digit_mid=0.5, chin_s=0.008, chin_drop=1.5,
             tongue_s=(0.075, 0.035), tongue_drop=2.0, olecranon=(0.0, 0.0), knee_pt=(0.0, 0.0), vfin_share=0.30,
             helpers_x10b=('shoulder', 'hip', 'wrist', 'ankle'),
             twist_upper=0.5, twist_lower=0.5, throat_frac=0.25, breath_chest=0.25, breath_belly=0.40,
             r_spine=(12.0, 8.0, 5.0), r_neck=(20.0, -10.0, 35.0), r_jaw=(0.0, 40.0), r_talk=25.0, r_gaze=10.0,
             r_gill_fold=(-30.0, 40.0), r_gill_splay=20.0, r_gill_splay_in=15.0, r_gill_sway=(5.0, 15.0),
             r_humerus=(55.0, -30.0, 45.0, 21.0),
             r_elbow=(60.0, 165.0), r_wrist=60.0, r_wrist_ext=85.0, r_digit_curl=(-20.0, 70.0), r_digit_splay=15.0,
             r_femur=(60.0, -30.0, 45.0, 33.0), r_femur_back=95.0, r_knee=(65.0, 165.0), r_ankle=60.0,
             r_ankle_ext=85.0, r_tail=(30.0, 10.0, 5.0),
             r_curl=15.0),
    # ---- the bind pose (plan §4.3, AX1's design values with their gates)
    rest=dict(belly=3.0, belly_band=(1.0, 5.0), wrist_h=1.5, ankle_h=1.5, humerus_back_plan=30.0,
              hand_out=30.0, femur_fwd=20.0, foot_out=35.0, hands_apart_target_HW=1.64, forearm_tol=10.0,
              tail_tip_h=4.0, p01_femur_elev=0.0),
    # ---- where the sources disagree, and the call (plan §2.12), as data: (topic, the call)
    conflicts=(('SVL/TL 0.525 (p01) / 0.552 [L] / 0.574 (p08)', 'A1 = [L]; p01 mapped onto it'),
               ('tail depth 0.158 (p01) against 0.104-0.108 (p06, p08), 0.107 [L]', '[L] with p08; p01 fin x0.675'),
               ('mouth corner 0.037 (p01)', 'not used: AX0b reads 0.080 on p18 (0.085 [E] before)'),
               ('r3 shortest from the front', 'foreshortened: p01 makes r3 >= r2 likely'),
               ('gills flared (p13) against laid back (p01)', 'two postures: chords [E], the bounds measured'),
               ('11 pliegues [L] against 8 + 2 grooves (p01)', '10 grooves [D]; 11 the other reading'),
               ('hip 0.480 (p01) / 0.512 (p08)', '0.490 [E], AX1 gates the groin fold'),
               ('forelimb 25.6 mm (p01 bounds + 6 mm hand)', 'AX0b: g06 loose forelimbs, 43.99 mm at A1'),
               ('eye 0.048 (p01) against 0.032-0.043 (p18, p02, p22, p12)', 'AX1 builds the median 0.040'),
               ('trunk 0.95 HW [E] / 1.196 (p09) / 0.65 (p12, lean)', 'kept 0.95 for AX1; AX2 decides (1.11 offered)'),
               ('hip 0.490 [E] against p01\'s folded limb read with its femur near lateral (about 0.466)',
                'AX1 keeps 0.490: p01\'s knee is reached with the femur 32 deg forward; AX2\'s side overlay decides'),
               ('AX2: the hip on the side overlay (0.465 lateral femur / 0.490 forward)',
                '0.465: the forward femur shows its thigh over p01\'s bare flank (0.142 / 0.069 of the lobe); p08 (0.512) '
                'and the hips-near-the-vent prior disagree; every g06 length x 0.8742 / 0.922'),
               ('AX2: the vent, core + p01-scaled dorsal fin 0.136 TL at 0.50 against the tail total 0.111 at 0.552',
                'the tail total wins (p08 + [L]); the trunk\'s dorsal fin at the shared-core scale 0.394, not 0.675'),
               ('AX2: the trunk, 0.95 HW [E] / 1.196 (p09, the sweep) / 0.65 (p12, lean)',
                '1.084 HW: p09 traced at one threshold for head and trunk (profile_x2)'),
               ('AX2: r3\'s filament comb against the upper arm at the 30 deg stance (-0.31 mm skin to skin)',
                'AX2b: r3 raised to +3 deg (gills.u_r3_x2b) and the palms at 1.64 HW (35.3 deg back): +0.67 mm, the '
                'check\'s measured option')),
    # ---- the bars later rounds gate (plan §2.1-§2.8): (target, tolerance) in each row's unit
    bars=dict(vent_s=(0.552, 0.002), gill_base_s=(0.177, 0.003), gill_line_s=(0.177, 0.005), head_width=(37.9, 0.8),
              tail_height_TL=(0.107, 0.004), tail_height_at=(0.60, 0.66), groin_s=(0.448, 0.01),
              hands_apart_HW=(1.221, 1.8), forearm_vertical=(0.0, 10.0), belly=(1.0, 5.0)),
    # ---- AX7b's readings (10-30, gridded crops in work/bestiary/axolotl/ax7b_notes/ref/): the gills, the mouth, the
    # digits. Rows of their own beside the plan's (gills.*, limbs.*), never written over them; the builders read these
    ax7b=dict(
        # the stalk: flattened across its comb face (measured), bowed away from its comb side, deepest near the tip;
        # each oval turned by its graft ring's roll so the stacked rami carry r1's section exactly (the TAGS notes)
        ramus_aspect=1.37, ramus_aspect_built=1.37, ramus_aspect_ramp=0.25, ramus_arch=0.10, ramus_arch_peak=0.62,
        graft_share=0.1825, ring_shift=(0, 0, 1),
        # the fringe: two vanes (one along each edge of the posterior face), two staggered ranks in each
        vanes=2, ranks_per_vane=2, vane_root_deg=(70.0, 52.0), vane_splay_deg=(72.0, 50.0), vane_jitter_deg=7.0,
        fil_spacing_D1=0.20, comb_from=0.04, comb_to=1.0, fil_len_D1=1.50,
        fil_len_profile=((0.0, 0.70), (0.20, 1.0), (0.75, 1.0), (1.0, 0.60)), fil_w_D=0.085, fil_hang_deg=38.0,
        fil_droop=0.06,
        # the mouth: the line rises toward each corner (the smile): measured, and as built (the corners up, the front
        # down: the TAGS notes)
        smile_rise=1.8, smile_up_built=1.2, smile_down_built=0.35, smile_power=3.0,
        # the digits: base and tip radius (CLAY's digit_r convention: x limbs.radii_x2 digit / 0.5), no tip bulb
        digit_r=(0.58, 0.29)),
    # ---- AX7c's readings and builds (10-30, gridded crops in work/bestiary/axolotl/ax7c_notes/ref/; the clay measured
    # like the photos by ax7c_notes/probe_mouth.py): the smile across the front and its lip lobes (heads/caudate.py's
    # smile_y), rows of their own beside AX7b's
    ax7c=dict(
        corner_up=0.40, smile_U=1.7, smile_c=1.2, smile_xU=0.37,
        lobe_x=0.32, lobe_w=3.4, lobe_bulge=0.9, lobe_drop=0.1,
        # the digits as fleshy webbed cones and the palm's / sole's dorsum (families/sprawl._fleshy_digit)
        digit_base_k=0.125, digit_base_min=0.75, digit_tip_k=0.50, digit_tip_min=0.30, digit_taper_p=0.65,
        digit_aspect=1.2, ray_r0=0.55, ray_lat=0.55, k_digit=0.45, pad_t=(0.85, 0.90), pad_sag=0.35),
    # ---- AX8's readings and builds (10-31, gridded crops in work/bestiary/axolotl/ax8_notes/ref/): the lip's TWO BEADS a
    # side in place of AX7c's one lobe (heads/caudate.py's lobe record as beads), the digits' fine tips (families/sprawl.
    # _fleshy_digit: these digit rows override AX7c's of the same name), rows of their own beside AX7c's
    ax8=dict(
        beads_x=(0.265, 0.32), bead_w=1.15, bead_bulge=1.3, bead_drop=0.05,
        digit_tip_k=0.22, digit_tip_min=0.15, digit_taper_p=0.75),
    # ---- AX10's builds (11-01, the lead's AX10 calls; crops in work/bestiary/axolotl/ax10_notes/ref/, the clay judged
    # by ax10_notes/bead_lab.py): the beads as PEARLS (heads/caudate.py's pearl: round domes over round footprints under
    # the margin, the lower lip's rows dense there), the corner's FOLD (caudate.fold_weight), and the pads' blend into
    # the forearm and the shank. Rows of their own beside AX8's; the builders read these. (The ankle's L is the rig's:
    # species/axolotl_rig.STAND lifts the heels in the poses; a bind with the heels lifted and the shanks leaning
    # (sprawl.limb_rest's ax10 rows, tried 11-01: 15 / 8 deg) put AX4's knee wedge across its V crease, gate 2's folds)
    ax10=dict(
        beads_x=(0.248, 0.31), bead_ra=1.10, bead_rb=1.15, bead_dc=1.50, bead_h=1.65, bead_p=0.5, bead_hang=0.1,
        bead_up=0.6, bead_out=0.15, bead_drop=0.05,
        fold_s=(0.034, 0.052, 0.062), fold_drop=1.9, fold_corner=0.2, fold_out=0.9, fold_tuck=0.5, fold_end=0.007,
        k_pad=1.0),
    # ---- AX13's builds (11-02, the lead's AX13 calls: work/bestiary/PLAN.md "AXOLOTL AX10b DONE"): THE PEARLS AS
    # SEPARATE GLASS DROPLETS (species/axolotl_pearls.py) in place of AX10's skin pearls: the clay's beads come off the
    # skin (heads/caudate.py reads `pearls`), so the lower lip runs smooth under them and the bake shows the lip there;
    # four droplets (two a side) at AX10's places, round, resting OVER the lower lip's pale band, their tops tucked under
    # the upper lip's margin, one template on one UV shell, rigid on the lower lip's weights (the eyes' way: their own
    # part and material); the lips closed onto each other at the droplets and on to the corner (families/sprawl_body
    # LAY lip_gap_drop). Rows of their own beside AX10's; the builders read these
    ax13=dict(
        pearls='parts', drop_x=(0.248, 0.31), drop_r=(1.30, 1.08, 0.95), drop_n=8, drop_embed=0.22, drop_top=0.10,
        drop_touch=0.96, drop_lift=0.6, fold_tuck=0.0, fold_lift=0.8, fold_s=(0.034, 0.060, 0.064),
        drop_alpha=0.40, drop_transmission=0.90, drop_ior=1.36, drop_rough=0.05, drop_coat=1.0, drop_coat_rough=0.06,
        drop_tint='#E9EEEA', drop_thick=0.9),
)

# The part ids (plan §4.2) for the cage's part one-hot, the bake's region output and the recipe's mask regions; zones
# are plan §5.11's mask roles (the MASKS pack R thin / G ventral / B gill-fin-filament / A melanophore cover; the DISPLAY
# pack R iridophore / G xanthophore / B leucistic speckles / A mottle random). The check's open item 4: the octopus reads
# DISPLAY as R spots / G eye ring / B dark display, so a WELD band would mix meanings until AX9 decides a shared layout
REGIONS = ('head', 'mouth', 'eye', 'gill', 'filament', 'trunk', 'tail', 'fin', 'forelimb', 'hindlimb', 'hand', 'foot')
REGION_ID = {name: i for i, name in enumerate(REGIONS)}
ZONES = dict(thin='masks.r', ventral='masks.g', gill_fin='masks.b', melanin='masks.a', iridophore='display.r',
             xanthophore='display.g', speckles='display.b', mottle_random='display.a')
MORPH_ORDER = ('wild', 'leucistic', 'white_albino', 'golden_albino', 'melanoid', 'axanthic')

_AP = 'aplan_numbers.py '
_X0 = 'AX0b (ax0b_readings.json), '
TAGS = {
    'family': ('[H]', 'plan §5.2: the recipe family stays limbed, with a body-plan key'),
    'body_plan': ('[D]', 'plan §5.2: sprawl (forge/families/sprawl.py), beside the wolf\'s sagittal limbed.py'),
    'head_archetype': ('[D]', 'plan §5.2: forge/heads/caudate.py (AX2 onward)'),
    'author_scale': ('[D]', 'plan §5.3: built at x4, so the forge\'s metric constants sit at creature scale'),
    'life_scale': ('[D]', 'plan §5.3: the glb carries life_scale 0.25'),
}


def _tag(keys, tag, note):
    for k in keys:
        TAGS[k] = (tag, note)


_SEM = 'SEMARNAT 2018 p. 38 citing Ramirez-Bautista 2009 (literature.json)'
for _k, _n in (('SVL', 'SVL_mm'), ('tail', 'cloaca_to_tail_tip_mm'), ('HL', 'head_length_mm'), ('HW', 'head_width_mm'),
               ('tail_height', 'tail_height_mm')):
    TAGS[f'a1.{_k}'] = ('[L]', f'{_SEM}: {_n}, the mean')
    TAGS[f'a1.{_k}_sd'] = ('[L]', f'{_SEM}: {_n}, the spread' + (' (the check: +-0.29 looks like a typo)'
                                                                  if _k == 'tail_height' else ''))
TAGS['a1.TL'] = ('[D]', 'SVL + tail, exactly (plan §2.1)')
_tag(('ratios.SVL_TL', 'ratios.HL_TL', 'ratios.HW_HL', 'ratios.tail_height_TL', 'ratios.TL_x4', 'ratios.HL_x4',
      'ratios.HW_x4', 'ratios.tail_height_x4'), '[D-ap]', _AP + '§1: A1\'s ratios and the x4 build')
TAGS['ratios.HW_SVL'] = ('[D-ap]', _AP + '§4: HW/SVL, the literature\'s')
# stations
_tag(('stations.naris', 'stations.eye_c', 'stations.mouth_p01', 'stations.gill_base', 'stations.shoulder',
      'stations.fin_origin', 'stations.groin'), '[D-ap from P p01]',
     _AP + '§2: p01\'s station mapped onto A1 (the head x0.991, gill base -> vent x1.083)')
TAGS['stations.mouth_p01'] = ('[D-ap from P p01]', _AP + '§2: p01\'s mouth corner, flagged uncertain by the sweep (the '
                                                         'lip fold fades in shadow): not used')
TAGS['stations.eye_c_x0b'] = ('[D-x0 from P p18 p02 p22 p12 p01]', _X0 + 'the median of five photos\' eye stations, '
                                                                     'each a fraction of HL x A1\'s HL/TL (head.eye_HL_x0b); '
                                                                     'AX1 places the eye joints here (plan\'s 0.048 = p01 alone)')
TAGS['stations.commissure_plan'] = ('[E]', 'the plan\'s 0.085 (§2.1), superseded by the AX0b reading below')
TAGS['stations.commissure'] = ('[D-x0 from P p18]', _X0 + 'p18 (pale, lateral head): the mouth slit\'s crisp end at '
                                                        '0.453 HL on the head\'s mid-depth axis, x A1\'s HL/TL; +-0.014 '
                                                        'for an unknown head yaw. AX1 and AX3 use it')
TAGS['stations.commissure_lower'] = ('[D-x0 from P p02]', _X0 + 'p02 (dark): the lip line lost under the cheek at 0.251 '
                                                              'HL: a lower bound')
TAGS['stations.jaw_hinge'] = ('[E]', '§2.1: behind the commissure at the skull\'s rear third ([C] the quadrate at the '
                                     'posterolateral skull corner): AX1')
TAGS['stations.head_joint'] = ('[E]', '§4.1 (the check): the atlanto-occipital joint at the skull\'s rear (skull_end_mm, '
                                      '26.55 mm at AX2\'s hip)')
TAGS['stations.head_joint_plan'] = ('[E]', 'the plan\'s AO station (27.9 mm, g06 x 0.922 at the plan\'s hip)')
TAGS['stations.poll'] = ('[E]', '§6.2: the poll ring between the jaw\'s loops and the gill ports (AX3 places it)')
TAGS['stations.throat'] = ('[D]', '§4.1: the throat joint under the gular region')
TAGS['stations.neck'] = ('[D]', '§4.1: neck_0 at the gill region')
TAGS['stations.gular_fold'] = ('[P p16]', 'AX2 (the lead\'s call): the gular loop at the gill line: p16 shows the fold level '
                                           'with the gill bases, just ahead of the forelimbs; heads/caudate.py creases the '
                                           'gill line\'s ring (0.177) across the throat, this row 0.001 ahead of it so the '
                                           'station order holds')
TAGS['stations.gular_fold_plan'] = ('[C]', '§2.4: 0.165-0.17 TL (salamander anatomy)')
TAGS['stations.gill_base'] = ('[D-ap from P p01]', _AP + '§2: p01\'s gill base mapped = A1\'s HL (0.177 [L])')
TAGS['stations.shoulder_joint'] = ('[D]', '§4.1: the shoulder joint at s 0.200')
TAGS['stations.shoulder_p08'] = ('[D-ap from P p08]', _AP + '§2: p08\'s shoulder (cross-check)')
TAGS['stations.hip'] = ('[P p01]', 'AX2, settled on the side overlay (the lead\'s call, tests/ax02_clay.py, ax02_hip.png): '
                                   'p01\'s folded hindlimb is a free-standing lobe (no thigh root shows against the flank: '
                                   'ax2_readings p01_hindlimb), so the femur points out at the camera and the knee\'s dome '
                                   'centre (x 2645, A1 s 0.4654) sits over the hip; posed on the clay, the femur forward to '
                                   'the same knee from 0.490 puts its thigh over p01\'s bare flank (0.142 of the lobe '
                                   'against 0.069). p12 (dorsal) reads hip / HL 2.62 (0.463 at A1\'s trunk proportion). '
                                   'Against it: p08\'s 0.512 (its hip / its estimated SVL) and the hips-near-the-vent '
                                   'expectation; every g06 length follows (k06_x2)')
TAGS['stations.hip_plan'] = ('[E]', '§2.1: the plan\'s 0.490, between p01\'s groin + 0.03 and p08\'s hip / SVL (AX1 built it)')
_tag(('stations.hip_p01', 'stations.hip_p08'), '[D-ap]', _AP + '§2: the hip cross-checks')
TAGS['stations.vent'] = ('[L]', 'A1\'s SVL / TL, rounded (the male\'s cloacal mound at its front [P p01])')
TAGS['stations.skull_end_mm'] = ('[D]', '§2.1\'s rule at AX2\'s hip: g06\'s skull 28.65 x k06_x2 0.8742 + 1.5 mm of soft '
                                        'snout, life mm')
TAGS['stations.skull_end_mm_plan'] = ('[D]', '§2.1: g06\'s skull 28.65 x 0.922 + 1.5 mm (the plan\'s hip)')
_tag(('station_map.head', 'station_map.trunk', 'station_map.tail'), '[D-ap]', _AP + '§2: p01 -> A1, the gill base on HL '
                                                                                  'and the vent on SVL')
# profile
_tag(('profile.core', 'profile.dorsal_fin', 'profile.tail_total', 'profile.fin_scale'), '[D-ap from P p01 p08]',
     _AP + '§3: the trunk core = p01 less its dorsal fin; the fin x k = 0.107 / 0.158; the tail total = p08 by the tail\'s '
           'share')
TAGS['profile.tail_core_share'] = ('[E]', '§2.2: the plan\'s single core share; AX0b reads a profile')
TAGS['profile.tail_core_TL_x0b'] = ('[D-x0 from P p01]', _X0 + 'p01 backlit: the opaque core\'s span / TL_px at seven '
                                                             'x, mapped to A1 stations (the tail x0.943); crisp near the '
                                                             'vent, rough mid-tail, a lower bound at the tip')
TAGS['profile.tail_core_share_x0b'] = ('[D-x0 from P p01 p08]', _X0 + 'the SHARED-CORE reading: p01\'s core in TL over A1\'s '
                                                                  'total (profile.tail_total) at the same station; the '
                                                                  'fins are A1 total - core')
TAGS['profile.tail_core_share_p01'] = ('[D-x0 from P p01]', _X0 + 'p01\'s own core share (a tall-finned male): the other '
                                                                'bound')
_X2 = 'AX2 (ax2_readings.json, tests/ax02_clay.py recomputes), '
TAGS['profile.head_side_x2'] = ('[D-x2 from P p01]', _X2 + 'the head\'s dorsal and ventral outlines LEVEL: p01\'s traced lines '
                                                       'rotated about the snout tip by the head axis\'s pitch '
                                                       '(head_pitch_p01_x2), (s, top, bottom) in TL about the snout '
                                                       'tip\'s level at A1 stations (the head x0.991); their depth is §2.2\'s '
                                                       'core within 0.0005 TL (heads/caudate.py builds the head from it)')
TAGS['profile.head_pitch_p01_x2'] = ('[D-x2 from P p01]', _X2 + 'p01\'s head axis (the snout tip to the mid-depth at the gill '
                                                            'base\'s x) above the image horizontal, deg')
TAGS['profile.fin_call_x2'] = ('[D]', 'AX2\'s one call at the vent (the check\'s open item): the tail\'s TOTAL depth wins '
                                      '(§2.2\'s p08 profile, the literature\'s 25.8 mm; p08\'s tail is mostly core with low '
                                      'fins) over the core + p01-scaled fin, so the fins are the total less AX0b\'s shared '
                                      'core (species/axolotl_fins.py)')
TAGS['profile.fin_scale_x2'] = ('[D-x2 from P p01 p08]', _X2 + 'the dorsal fin over the trunk = p01\'s own x this: the mean over '
                                                         'AX0b\'s seven core stations of A1\'s fins (tail_total - core) over '
                                                         'p01\'s (core / its own share - core); the plan\'s 0.675 assumed the '
                                                         'fins scale with the whole tail (the check\'s item 9: nearer 0.48 '
                                                         'with a shared core)')
TAGS['profile.fin_blend_x2'] = ('[D]', 'AX2: the dorsal fin eases from the trunk\'s form into the tail\'s across the vent over '
                                       'these stations (no step where the two tables meet)')
# widths
TAGS['widths.head_widest_s'] = ('[D-ap from P p09]', _AP + '§4: the radiograph\'s widest head station x A1\'s SVL/TL')
TAGS['widths.trunk_HW'] = ('[E]', '§2.3: 0.95 HW until p12; AX1 builds with it (the clay decides at AX2)')
TAGS['widths.trunk_mm'] = ('[D-ap]', _AP + '§4: 0.95 HW')
TAGS['widths.trunk_HW_p09'] = ('[D-ap from P p09]', _AP + '§4: the radiograph\'s trunk over its own head width')
TAGS['widths.trunk_HW_p09_lit'] = ('[D-x0 from P p09 L]', _X0 + 'the radiograph\'s trunk (0.315 of its SVL proxy) over '
                                                             'the literature\'s HW/SVL 0.284: offered to AX2')
TAGS['widths.trunk_HW_p12'] = ('[D-x0 from P p12]', _X0 + 'p12 (dorsal, a LEAN animal regrowing its forelimbs): the '
                                                        'mid-trunk over the cheeks; a floor, not a target')
TAGS['widths.radiograph_g_at_A1'] = ('[D-x0 from L]', _X0 + 'the radiograph animal (159.5 g at 26.3 cm) scaled to A1\'s '
                                                         'length by L^3: the SDZWA male mean (125-130 g)')
TAGS['widths.gamel_g_at_A1'] = ('[D-x0 from L]', _X0 + 'Gamel\'s walkers (112.7 g at 25.7 cm) at A1\'s length: lean')
_tag(('widths.pelvis_HW', 'widths.pelvis_mm', 'widths.tailbase_HW', 'widths.tailbase_mm'), '[D-ap from P p09]',
     _AP + '§4: the radiograph\'s ratio to its own head width')
TAGS['widths.HW_SVL_p09'] = ('[D-ap from P p09]', _AP + '§4: the radiograph\'s HW / SVL proxy')
TAGS['widths.profile_x2'] = ('[D-x2 from P p09]', _X2 + 'p09\'s plan widths along the body: each row\'s soft-tissue edges where '
                                                    'the brightness passes 0.15 of the way from the background to the '
                                                    'row\'s plateau (a round section\'s half-maximum sits at 0.87 of its '
                                                    'radius, so the outer foot is read), a 5-row running mean, over the '
                                                    'head\'s maximum, at A1 stations by the SVL proxy; the forelimb and '
                                                    'hindlimb rows interpolated over. heads/caudate.py builds the plan from '
                                                    'it (the snout\'s last 0.025 TL by the apex rule)')
TAGS['widths.trunk_HW_x2'] = ('[D-x2 from P p09]', _X2 + 'the trunk\'s widest in profile_x2 (s 0.36): AX2\'s call on the '
                                                     'trunk (the plan\'s 0.95 [E]): one threshold for head and trunk, so '
                                                     'the ratio holds whatever the edge\'s blur (0.3 and 0.5 give 1.08 and '
                                                     '1.10)')
TAGS['widths.head_widest_s_x2'] = ('[D-x2 from P p09]', _X2 + 'the head\'s widest station in profile_x2: just ahead of the gill '
                                                          'line (the plan\'s 0.099 was the sweep\'s chosen row, 0.94 HW '
                                                          'wide on this trace)')
# head
_tag(('head.height_HW', 'head.height_mm', 'head.eyes_apart_HW', 'head.eyes_apart_mm', 'head.nares_apart_HW',
      'head.mouth_w_HW', 'head.mouth_w_mm'), '[D-ap from P p13]', _AP + '§5: p13 in HW')
_tag(('head.eye_frontal', 'head.naris_frontal', 'head.mouth_frontal', 'head.cheek_frontal'), '[D-ap from P p13]',
     _AP + '§5: p13\'s points: below the head top / off the midline')
TAGS['head.eye_d_TL'] = ('[P p01]', 'p01: the visible lidless eye (res_photos eye_TL)')
TAGS['head.eye_d_mm'] = ('[D-ap]', _AP + '§5: the eye in life mm')
TAGS['head.eye_d_range'] = ('[P p08 p06]', 'the other two photos (res_photos eye_TL)')
TAGS['head.skull_len_g06'] = ('[P g06]', 'g06\'s skull, ruler 16.198 px/mm (res_photos)')
TAGS['head.skull_W_g06'] = ('[P g06]', 'g06\'s skull width mid and rear (res_photos; the rear may include the hyoid)')
TAGS['head.skull_WL'] = ('[D-sw from P g06]', 'the sweep\'s skull W/L range')
TAGS['head.skull_len_A1'] = ('[D]', 'g06\'s 28.65 x k06_x2 (AX2\'s hip)')
TAGS['head.skull_len_A1_plan'] = ('[D]', 'g06\'s 28.65 x 0.922 (the plan\'s hip)')
TAGS['head.iris_ring'] = ('[P p01]', 'the plan check\'s reading on p01_face: the gold ring ~0.6 of the visible eye')
TAGS['head.pupil'] = ('[P p01]', 'the plan check\'s reading on p01_face: the pupil ~0.35 of the visible eye')
TAGS['head.eye_HL_x0b'] = ('[D-x0 from P p18 p02 p22 p12 p01]', _X0 + 'the eye centre / HL on the head\'s mid-depth axis: '
                                                                  'p18, p02, p22 (lateral), p12 (dorsal), p01 (the sweep)')
TAGS['head.commissure_HL_x0b'] = ('[D-x0 from P p18 p02]', _X0 + 'the mouth corner / HL: p18, p02 (a lower bound)')
# gills
TAGS['gills.gill_scale'] = ('[D]', '§2.5: 1.0 = p13\'s fan, the iconic read')
TAGS['gills.gill_scale_range'] = ('[D]', '§2.5: gill size varies with the animal and its water [C]')
_tag(('gills.frontal_r1', 'gills.frontal_r2', 'gills.frontal_r3'), '[P p13]', 'p13 frontal: L / R stalk lengths in HW '
                                                                             '(res_photos), the base hidden behind the head')
_tag(('gills.emergence_r1', 'gills.emergence_r2', 'gills.emergence_r3'), '[D-ap from P p13]',
     _AP + '§5: where each stalk leaves the head\'s outline (below the top / off the midline)')
_tag(('gills.frontal_deg', 'gills.chord_raw', 'gills.u_r1', 'gills.u_r2', 'gills.u_r3', 'gills.lower_bound',
      'gills.lower_bound_raw', 'gills.r2_up_check', 'gills.D_mm'), '[D-ap from P p13 p01]',
     _AP + '§6-§7: the rami from p13\'s front and p01\'s side; two postures, so the vectors are a flared design pose')
TAGS['gills.u_r3_x2b'] = ('[D]', 'the lead\'s call at AX2b (10-28), the AX2 check\'s measured option: r3\'s bind direction '
                                 'raised to +3.0 deg elevation (u_r3\'s horizontal part, its plan azimuth kept, x cos 3 '
                                 'deg, the up sin 3 deg) so its comb clears the upper arm (+0.67 mm with the palms at '
                                 '1.64 HW); families/sprawl.rest_chain builds it in place of u_r3, which stays the plan\'s '
                                 'p13 / p01 solve (its frontal angle 90.2 deg, this one 85.2: inside AX2\'s +-10 deg and '
                                 'p13\'s own +-16 deg L / R tilt)')
TAGS['gills.side_TL'] = ('[P p01]', 'p01 side: r2 and r3 stalks in TL (res_photos)')
TAGS['gills.side_elev'] = ('[D-ap from P p01]', _AP + '§6: p01\'s r2 / r3 chords from the image horizontal')
TAGS['gills.chord'] = ('[E]', '§2.5: the design chords (p13\'s out added to p01\'s side; r1\'s back share assumed)')
TAGS['gills.chord_115'] = ('[D-x0 from P p13 p01]', _X0 + 'the plan\'s solve at full precision (ax00 recomputes it); '
                                                        'aplan prints 24.0 / 16.0 / 18.5')
TAGS['gills.perspective'] = ('[E]', '§2.5: p13\'s close camera reads the rami 10-20 % short (x1.15)')
TAGS['gills.r1_back'] = ('[E]', '§2.5: r1\'s back share, assumed (E_R1_BACK)')
TAGS['gills.similar'] = ('[D-x0]', 'the design chords over r1\'s (exact similar copies stack on r1\'s shells)')
TAGS['gills.ramus_D'] = ('[P p17]', 'p17: the ramus 7.1 D long (res_photos)')
TAGS['gills.root_D'] = ('[E]', '§2.5: a fleshy root 1.3 D')
_tag(('gills.filament_len_D', 'gills.filament_w_D', 'gills.filament_spacing_D', 'gills.ranks'), '[P p17]',
     'p17: filament ratios to D (res_photos)')
TAGS['gills.comb'] = ('[E]', '§2.5: the comb along 0.8 of the ramus (E_COMB)')
_tag(('gills.per_rank', 'gills.per_ramus', 'gills.total', 'gills.lod0_tris', 'gills.lod1_tris', 'gills.lod0_total',
      'gills.lod1_total'), '[D-ap]', _AP + '§7: counts and LOD triangles')
TAGS['gills.p18_elev'] = ('[D-x0 from P p18]', _X0 + 'p18\'s rami chords above the image horizontal (backward): a third '
                                                   'posture (r1 steep, r2 / r3 gentle); its head axis rises 10.27 deg back')
TAGS['gills.p18_L_HL'] = ('[D-x0 from P p18]', _X0 + 'p18\'s side projections over HL: lower bounds (r2 x A1 HL = 16.1 '
                                                   'mm, the plan\'s chord 16.0)')
TAGS['gills.p18_head_axis'] = ('[D-x0 from P p18]', _X0 + 'p18\'s head axis above the image horizontal (toward the back)')
TAGS['gills.rest_motion'] = ('[P v03]', _X0 + 'the Zittau clip: at rest the rami hold still and flared for 11.4 s (no '
                                             'flutter; the slow drift is the whole head\'s)')
# trunk
TAGS['trunk.grooves'] = ('[D]', '§2.6: 10 grooves (p01 8 + 2 faint, p23 9-10, p03 10-11)')
TAGS['trunk.grooves_alt'] = ('[L]', 'SEMARNAT\'s "11 pliegues intercostales": the other reading')
_tag(('trunk.groove_stations', 'trunk.groove_stations_11', 'trunk.groove_spacing'), '[D-ap from P p01]',
     _AP + '§8: spacing growing toward the groin by p01\'s ratio, x the trunk stretch')
_tag(('trunk.groove_spacing_p01', 'trunk.groove_mean'), '[P p01]', 'p01\'s groove spacings, groin -> axilla '
                                                                  '(res_photos)')
TAGS['trunk.groove_depth'] = ('[E]', '§2.6: a soft V 0.3-0.5 mm; AX0b could not scale it')
TAGS['trunk.crease_over_spacing'] = ('[P p23 p19]', _X0 + 'narrow V creases between convex segments: the crease 0.05 of '
                                                         'the spacing (p23), 0.15-0.20 on p19\'s deeply folded old male')
TAGS['trunk.section'] = ('[E]', '§2.6: 36 x 29 mm (the width [E], the depth [P p01])')
# fins
TAGS['fins.ventral_from'] = ('[P p01]', 'the ventral fin starts at the vent\'s back')
TAGS['fins.half_thickness'] = ('[E]', '§2.7: root 0.5, margin 0.12 mm life; the backlit render gates it')
TAGS['fins.backlit_ratio'] = ('[P p01]', '§2.7: backlit fins and thin tail 6-8x the flank')
TAGS['fins.backlit_Ylin'] = ('[P p01]', 'p01 tail flank, dorsal fin, trunk flank Ylin (res_colour)')
# limbs
_tag(('limbs.upper_arm_p01', 'limbs.forearm_p01', 'limbs.hand_p01_min'), '[D-ap from P p01]',
     _AP + '§9: p01\'s surface readings at A1, lower bounds (the upper arm angled toward the camera, the digits curled)')
TAGS['limbs.hand_plan_TL'] = ('[E]', 'the plan\'s hand with its longest finger (superseded by hand_x0b)')
_tag(('limbs.k06', 'limbs.g06_bony'), '[D-ap from P g06]', _AP + '§9: g06 -> A1 by the hip station')
_tag(('limbs.femur', 'limbs.tibia', 'limbs.tarsus', 'limbs.mt_digit'), '[D-ap from P g06]',
     _AP + '§9: g06\'s card hindlimb x 0.922')
TAGS['limbs.adpressed'] = ('[D-ap]', _AP + '§9: fore + hind against shoulder-to-hip')
_tag(('limbs.humerus_x0b', 'limbs.forearm_x0b', 'limbs.hand_x0b'), '[D-x0 from P g06]',
     _X0 + 'g06\'s two LOOSE forelimbs (not identified by the sweep): each segment the larger of its two readings, '
           'x k06 at stations.hip (0.8742 since AX2 settled the hip at 0.465; AX1 built 0.922). The skeleton builds with '
           'these')
_tag(('limbs.femur_x0b', 'limbs.tibia_x0b'), '[D-x0 from P g06]',
     _X0 + 'the larger of g06\'s two hindlimbs (the folded left reads 8 % / 6 % longer than the card limb), x k06 at '
           'stations.hip (0.8742 since AX2). The skeleton builds with these')
TAGS['limbs.k06_x2'] = ('[D-x2 from P g06]', _X2 + 'g06 -> A1 at the settled hip: (hip x TL - 1.5 mm of soft snout) / g06\'s '
                                             'skull + trunk 126.8 mm (the plan\'s rule; the plan\'s 0.922 at its 0.490)')
_tag(('limbs.tarsus_x2', 'limbs.mt_digit_x2'), '[D-x2 from P g06]',
     _X2 + 'g06\'s tarsus 9.46 / metatarsal + longest digit 18.64 mm x k06_x2 (the plan\'s rows are x 0.922); '
           'families/sprawl.rest_chain builds with these')
TAGS['limbs.adpressed_x0b'] = ('[D-x0]', _X0 + 'fore (humerus + forearm + hand) + hind (femur + tibia + tarsus + MT '
                                              'digit) against shoulder-to-hip, and the overlap')
_tag(tuple(f'limbs.radii.{k}' for k in SPEC['limbs']['radii']), '[E]', '§2.8: limb radii, AX2\'s look and AX0b\'s '
                                                                         'p13 / p16 widths (not resolved: blurred)')
TAGS['limbs.radii_x2.forearm'] = ('[P p08]', 'AX2: p08 (standing, side on) the forearm 28 px wide over its TL 1578 px = 4.29 '
                                             'mm at A1, half of it (the plan\'s 1.6 [E]); p01\'s propped forearm reads wider '
                                             '(its elbow and hand overlap, not used)')
TAGS['limbs.radii_x2.shank'] = ('[P p08]', 'AX2: p08\'s shank 30 px = 4.59 mm at A1, half of it')
TAGS['limbs.radii_x2.upper_arm'] = ('[P p13]', 'AX2: p13\'s upper arms ~0.13 HW wide where they leave the body (blurred, '
                                               '+-0.02 HW) = 4.9 mm, half of it')
TAGS['limbs.radii_x2.thigh'] = ('[P p01]', 'AX2: p01\'s folded hindlimb, the knee seen end on: the dome\'s radius 73 px = 3.9 '
                                           'mm at A1 less the knee\'s bulge (sprawl.CLAY knee 1.10) and the folded shank')
_tag(('limbs.radii_x2.tarsus', 'limbs.radii_x2.digit'), '[E]', 'AX2: the tarsus between the shank and the sole; the digits '
                                                             '1.0-1.2 mm wide on p08 (6-8 px), long and thin [L]')
TAGS['limbs.digits'] = ('[L]', 'four fingers, five toes, no claws (SEMARNAT genus page; p23, g06)')
TAGS['limbs.hands_apart_HW'] = ('[D-ap from P p13]', _AP + '§5: a lower bound (the hands lie behind the face plane)')
TAGS['limbs.hands_apart_max_HW'] = ('[D]', 'the lead\'s call at AX2 (10-28): 1.8 HW (AX1\'s 1.6 [E] was set with the 9.5 mm '
                                            'humerus; g06\'s longer humerus at the plan\'s 30 deg back spreads the palms '
                                            'past it); the AX2b stance builds 1.64 HW inside it')
TAGS['limbs.phalanges'] = ('[C]', 'Ambystoma\'s phalangeal formulae, manus 1-2-3-2, pes 1-2-3-3-2 (the rig keeps two '
                                  'joints a digit)')
_tag(('limbs.finger_rel', 'limbs.toe_rel'), '[E]', 'digit lengths over the longest, the central digits longest (p23 '
                                                  'shows it; not measured: foreshortened)')
TAGS['limbs.webbing'] = ('[P p23]', _X0 + 'the digits separate to their bases at p23\'s resolution')
# skin
_tag(('skin.epidermis', 'skin.leydig', 'skin.spongiosum', 'skin.compactum'), '[P s01]',
     'Seifert 2012 Fig. 1, 100 um bars (res_photos s01)')
TAGS['skin.whole'] = ('[D]', 'epidermis + spongiosum + compactum')
TAGS['skin.f0'] = ('[R]', 'water, the study-T salamander creature\'s body (REF_SKIN_STUDY §2)')
TAGS['skin.f0_salamandretta'] = ('[R]', 'its head and fin sets')
_tag(('skin.rough_body', 'skin.rough_head', 'skin.rough_limbs', 'skin.rough_fins', 'skin.rough_dorsum_venter',
      'skin.micro_tile', 'skin.micro_strength'), '[R]', 'the study-T salamander creature: roughness p5 / p50 / p95 per set, the '
                                                         'micro-normal (plan §2.9)')
# colour
_tag(('colour.wild_flank', 'colour.wild_flank_dark', 'colour.wild_flank_light', 'colour.wild_head',
      'colour.wild_tail_trans', 'colour.wild_fin_trans', 'colour.wild_filaments', 'colour.flank_dark_share',
      'colour.spot_TL', 'colour.spot_nn_TL'), '[P p01]', 'p01 backlit, near neutral (res_colour)')
_tag(('colour.gold_field', 'colour.p06_flank', 'colour.p06_gills', 'colour.p06_tail', 'colour.gold_hsv'), '[P p06]',
     'p06 zoo light (res_colour)')
_tag(('colour.leucistic_body', 'colour.leucistic_head', 'colour.leucistic_gills'), '[P p03]', 'p03 tank light '
                                                                                            '(res_colour)')
_tag(('colour.albino_body', 'colour.albino_gills'), '[P p08]', 'p08 white albino, cyan cast (res_colour)')
_tag(('colour.venter_lit_p16', 'colour.throat_p16'), '[P p16]', _X0 + 'p16 from below through teal water (acolour '
                                                                     'RESULT p16; out of focus, palette only)')
# morphs
for _m in MORPH_ORDER:
    _c = _m in ('golden_albino', 'melanoid', 'axanthic')
    _tag((f'morphs.{_m}.M', f'morphs.{_m}.X', f'morphs.{_m}.I'), '[C]' if _c else '[D]',
         '§5.11\'s morph table: pigment-layer weights over one texture set (the study-B larva-creature model)' +
         ('; not photographed' if _c else ''))
    TAGS[f'morphs.{_m}.eye'] = ('[C]' if _c else '[P p13 p03 p08]', '§2.4 / §5.11: the eye look')
TAGS['morphs.wild.thin'] = ('[P p01]', 'the backlit tail\'s melanin-filtered transmission #907563')
TAGS['morphs.leucistic.thin'] = ('[P p03]', 'blood red through thin tissue (p03\'s gills)')
TAGS['morphs.white_albino.thin'] = ('[P p08]', 'pale pink (p08\'s gills)')
_tag(('morphs.golden_albino.thin', 'morphs.melanoid.thin', 'morphs.axanthic.thin'), '[E]',
     'thin-tissue colour by the morph\'s pigments ([C] golden pink-gold, melanoid dark, axanthic grey-brown); AX9')
TAGS['morphs.white_albino.X'] = ('[E]', '§5.11: "faint" xanthophores, 0.3 [E]')
TAGS['morphs.golden_albino.X'] = ('[E]', '§5.11 [C]: strong xanthophores, 1.5 [E]')
TAGS['morphs.golden_albino.I'] = ('[E]', '§5.11 [C]: strong iridophores, 1.5 [E]')
TAGS['morphs.melanoid.M'] = ('[E]', '§5.11: full cover, 1.4 [E]')
TAGS['morphs.melanoid.X'] = ('[E]', '§5.11 [C]: low xanthophores, 0.3 [E]')
# motion
_tag(('motion.walk_mm_s', 'motion.walk_TL_mm', 'motion.contact', 'motion.buoyancy'), '[L]',
     'Gamel, Pinti & Astley 2024 (literature.json): contact = shares of the whole trial')
TAGS['motion.walk_TL_s'] = ('[D-ap from L]', _AP + '§14: 77 mm/s at TL 257 mm')
TAGS['motion.cycle_stride_TL'] = ('[D-ap from P v01]', _AP + '§14: v01\'s 2-2.5 s cycle at Gamel\'s speed (low '
                                                            'confidence)')
_tag(('motion.swim_wavelength', 'motion.swim_amp', 'motion.swim_stride', 'motion.swim_max', 'motion.swim_voluntary'),
     '[L]', 'D\'Aout & Aerts 1999 (literature.json), adults')
_tag(('motion.swim_hz', 'motion.body_wave', 'motion.slip', 'motion.tip_curvature', 'motion.tip_radius_TL',
      'motion.tip_radius_mm', 'motion.tail_step', 'motion.deg_per_tail_joint'), '[D-ap from L]',
     _AP + '§14: the swim at 0.3 / 1.0 / 3.3 TL/s, the tip curvature and the 12 tail joints')
TAGS['motion.gill_flutter_hz'] = ('[P v03]', _X0 + 'none seen at rest in the Zittau clip (11.4 s at 25 fps): the idle '
                                                  'sway stays [E] and small')
# rig and rest
TAGS['rig.n_joints'] = ('[D-ap]', _AP + '§15: 124 joints')
_tag(('rig.n_spine', 'rig.spine_from', 'rig.spine_to', 'rig.n_tail', 'rig.tail_from', 'rig.tail_to', 'rig.gill_joints'),
     '[D]', '§4.1\'s chains: spine_0..6 from the hips to the shoulders, tail_0..11 from the vent, 4 joints a ramus')
TAGS['rig.shoulder_x'] = ('[D]', '§4.1: the shoulder joint +-15 mm out')
TAGS['rig.hip_x'] = ('[E]', '§4.1: the hip +-12 mm out')
_tag(('rig.glenoid_frac', 'rig.acetabulum_frac', 'rig.spine_frac', 'rig.head_frac'), '[E]',
     'AX1: joint heights as fractions of the local core depth above the belly line (the glenoid and the acetabulum low '
     'in the section, the vertebral column dorsal of centre [C])')
TAGS['rig.jaw_frac'] = ('[D-x0 from P p13]', 'the mouth line\'s height above the chin: 1 - head.mouth_frontal[0] of the '
                                             'frontal height (p13)')
_tag(('rig.scapula_rise', 'rig.scapula_x'), '[E]', 'AX1: the scapula blade\'s dorsal end above and medial of the glenoid')
TAGS['rig.carpus_len'] = ('[D-x0 from P g06]', _X0 + 'hand_foot_split_g06: limb A\'s wrist to its carpometacarpal row '
                                                     '(43 px +-8) / 16.198 x k06')
TAGS['rig.metatarsal'] = ('[D-x0 from P g06]', _X0 + 'hand_foot_split_g06: the card foot\'s tarsal block to the longest '
                                                    'toe\'s metatarsal head (103 px +-15) / 16.198 x k06')
TAGS['rig.metacarpal'] = ('[E]', 'AX1: the metacarpal-phalangeal joints are not resolved on g06 (hand_foot_split_g06); '
                                 'the longest finger is the hand\'s rest (limbs.hand_x0b - carpus - metacarpal)')
_tag(('rig.palm_w', 'rig.sole_w', 'rig.digit_splay', 'rig.toe_splay'), '[E]',
     'AX1: the palm\'s and sole\'s width across the digit bases and the digits\' splay (p23 shows a fan, not measured)')
_tag(('rig.palm_h', 'rig.sole_h'), '[E]', 'AX1: the carpometacarpal and tarsometatarsal joints above the floor (the '
                                           'flat palm\'s and sole\'s half thickness)')
TAGS['rig.digit_mid'] = ('[E]', 'AX1: each digit\'s second joint at this fraction of the digit (two joints a digit, plan '
                                '§4.1; the phalangeal formulae are in limbs.phalanges)')
_tag(('rig.chin_s', 'rig.chin_drop'), '[E]', 'AX1: the jaw\'s tip (the mandible\'s front) a little behind the snout '
                                             'tip and below the mouth line')
_tag(('rig.tongue_s', 'rig.tongue_drop'), '[E]', 'AX1: the tongue pad on the mouth floor, its joint and tip stations '
                                                 'and its depth under the mouth line')
TAGS['rig.olecranon'] = ('[D]', 'AX10 (11-02): the elbow helper ON the elbow\'s axis (0, 0: along -x and -y of the '
                                'forearm\'s frame), a half-angle joint: it turns half the elbow\'s bend about the elbow '
                                'and carries the bend\'s blend (species/axolotl_rig.py HELPER), so the skin blends over '
                                'half the angle (LBS lost 13.8 % at 152 deg and 17.2 % at 42 deg with the bend alone; '
                                'AX1 had it 1.0 / 1.5 mm out behind the elbow, unweighted)')
TAGS['rig.knee_pt'] = ('[D]', 'AX10 (11-02): the knee helper ON the knee\'s axis (0, 0), a half-angle joint as the '
                              'elbow\'s (rig.olecranon\'s note: the knee lost 16.0 % at 145 deg and 22.4 % at 155 with '
                              'the bend alone)')
TAGS['rig.helpers_x10b'] = ('[D]', 'AX10b (11-02): half-angle helpers at the limbs\' ROOTS (shoulder_pt under the '
                                   'scapula, hip_pt under the pelvis) and at the WRISTS / ANKLES (wrist_pt under the '
                                   'radius, ankle_pt under the tibia), the elbow\'s and the knee\'s construction '
                                   '(families/sprawl.skeleton, species/axolotl_rig.py): the swim\'s thighs laid back 93 '
                                   'deg kept 39-48 % of the hip root\'s volume per vertex, the straightened wrist 61 % '
                                   '(the AX10 check). Eight joints past the plan\'s 124 (§4.1): 132')
TAGS['rig.vfin_share'] = ('[E]', 'AX1: the ventral fin\'s share of the tail\'s fins (p01 backlit reads 0.26 on a '
                                 'tall-finned male), only for the tail\'s floor clearance estimate')
TAGS['rig.eye_r'] = ('[D]', 'half the visible eye (head.eye_d_TL x TL / 2)')
TAGS['rig.eye_below_top'] = ('[P p01]', 'p01: the eye centre 61 px (3.2 mm at A1) below the head\'s dorsal outline')
TAGS['rig.eye_axis'] = ('[D from P p13 p15]', 'AX7 (10-29, the eye round): the lidless eye looks out, up and forward '
                                             '(out, up, forward; unit). AX1\'s (0.80, 0.45, 0.40) [E] lay 21.4 deg '
                                             'off the head\'s local normal round the eye (caudate\'s natural surface, '
                                             'its plane over 1.5-2.8 r_e: (0.548, 0.722, 0.423)), so the skin stood '
                                             '0.9-1.4 mm over the edge plane behind and below: the eye sat in a '
                                             'socket where p13 / p14 / p15 / p18 show it proud all round with an even '
                                             'soft rim. Turned 0.8 of the way to that normal: its frontal tilt (the '
                                             'opening\'s minor axis over the horizontal) is 48 deg against p13 / '
                                             'p15\'s pair means 35 / 43.5 (ellipse fits: 28 / 42, 61 / 26; the old '
                                             'axis 29, the normal 53). The clay\'s eye axes decide the glasses\' lens '
                                             'yaw (plan §10)')
TAGS['rig.gill_base_inset'] = ('[E]', 'AX1: the true bases a little medial of p13\'s emergence points (§2.5)')
_tag(('rig.twist_upper', 'rig.twist_lower'), '[E]', 'twist leaves at mid-bone')
TAGS['rig.throat_frac'] = ('[E]', 'AX1: the throat joint at the buccal floor, this fraction of the local core depth '
                                  'above the belly line')
_tag(('rig.breath_chest', 'rig.breath_belly'), '[E]', 'AX1: the breathers\' heights as fractions of the core depth')
_tag(('rig.r_spine', 'rig.r_neck', 'rig.r_jaw', 'rig.r_talk', 'rig.r_gaze', 'rig.r_gill_fold', 'rig.r_gill_splay',
      'rig.r_gill_sway', 'rig.r_digit_curl', 'rig.r_digit_splay', 'rig.r_tail', 'rig.r_curl', 'rig.r_wrist',
      'rig.r_ankle'), '[E]', '§4.1\'s ranges ([C] salamander kinematics); AX10 sweeps them')
# AX10 (11-02): the limbs' ranges from salamander WALKING kinematics, the urodele table of maximum limb segment angles in
# forward walking (Integrative Organismal Biology 2020, Table 4: A. tigrinum, Kawano et al. 2016, the axolotl's closest
# measured relative; P. waltl, Karakasiliotis et al. 2013; D. tenebrosus, Ashley-Ross 1994b; T. torosa, Ashley-Ross et al.
# 2009), widened by the swim's and the rest's postures the sweeps also pose (the limbs laid back along the body)
_W10 = '[L urodele walking table: Kawano 2016, Karakasiliotis 2013, Ashley-Ross 1994b, 2009]'
TAGS['rig.r_gill_splay_in'] = ('[D]', 'AX10 (11-02): the rami\'s splay toward each other, summed over a stalk\'s four '
                                      'joints, that the combs clear: 26 filament edges crossed a neighbouring ramus '
                                      'at -20, none at -15 (tests/ax10_rig.py --only hinge); out to +35 none. The '
                                      'AX10 sweeps read r_gill_fold and the splay as sums over the four joints')
TAGS['rig.r_humerus'] = (_W10, 'AX10: protraction / retraction +-55 about the bind (walking: 80-130 deg from the body\'s '
                               'axis in A. tigrinum, 60-142 across the table: the bind at 125 sits near the retracted '
                               'end, so -45 / +5 walking, +50 the swim\'s fold-back); elevation -30 / +45 (adduction 80 / '
                               'abduction 110, +-15 walking); long-axis rotation +-21 (P. waltl\'s 41 in all)')
TAGS['rig.r_elbow'] = (_W10, 'AX10: the elbow 60-165 deg included (walking: A. tigrinum 75-130, the table 60-147; the '
                             'swim\'s adpressed forelimb, laid back along the flank, opens it to ~163: axolotl_rig '
                             'ADPRESS; the plan\'s 40-170 was wider than any of them)')
TAGS['rig.r_femur'] = (_W10, 'AX10: protraction / retraction +-60 about the bind (A. tigrinum 50-130 from the body\'s '
                             'axis, the bind 20 deg forward of lateral: +20 / -60; the swim\'s fold-back -55); elevation '
                             '-30 / +45; long-axis rotation +-33 (P. waltl\'s 66 in all)')
TAGS['rig.r_knee'] = (_W10, 'AX10: the knee 65-165 deg included (A. tigrinum 90-145 in stance, the table to 173; the '
                            'walk\'s swing, the foot lifted 2.6 mm, flexes it to 69; the swim\'s adpressed hindlimb '
                            'opens it to ~158)')
_tag(('rig.r_wrist_ext', 'rig.r_ankle_ext', 'rig.r_femur_back'), '[D]',
     'AX10 (11-02): the swim\'s ADPRESSED limbs (plan §9.3: "folded back along the body"; §2.8\'s adpressed limbs) past '
     'the walk\'s ranges: the wrist and the ankle straightened in line with the forearm and the shank (the carpus\'s / '
     'tarsus\'s fold to +77 / +83 from the bind\'s 105 / 94 deg), the thigh laid back along the tail (the femur\'s fold '
     'to -93: 73 deg behind lateral, where walking retracts it 40-55; -88 since AX10b opened the upper bones off the '
     'flank, which the roots had crossed); species/axolotl_rig.py ADPRESS')
TAGS['rest.belly'] = ('[D]', 'AX1: the belly 3 mm off the floor, inside §4.3\'s 1-5 mm [E]')
TAGS['rest.belly_band'] = ('[E]', '§4.3: the body held clear of the floor (v01)')
_tag(('rest.wrist_h', 'rest.ankle_h'), '[E]', 'AX1: the wrist and ankle joints above the floor (the flat hand\'s and '
                                              'foot\'s thickness)')
TAGS['rest.humerus_back_plan'] = ('[E]', '§4.3: out and 30 deg back, with the old 9.5 mm humerus (AX1 solves the '
                                          'retraction instead: the hands at rest.hands_apart_target_HW)')
TAGS['rest.hand_out'] = ('[E]', 'AX1: the hand points forward and this far out')
TAGS['rest.femur_fwd'] = ('[E]', '§4.3: the femur out and slightly forward')
TAGS['rest.foot_out'] = ('[E]', 'AX1: the foot points forward and this far out')
TAGS['rest.hands_apart_target_HW'] = ('[D]', 'the lead\'s call at AX2b (10-28), replacing AX2\'s 1.68428 (the plan\'s 30 deg '
                                             'back): the palms 1.64 HW apart, so the solver builds 35.3 deg back with AX2\'s '
                                             'limb lengths (k06 0.8742), about 20 deg of retraction left for the walk; with '
                                             'r3 raised 3 deg (gills.u_r3_x2b) r3\'s comb clears the upper arm by +0.67 mm '
                                             '(AX2\'s 30 deg stance put it at -0.31 mm). AX1 built 1.5 HW = 51.7 deg back')
TAGS['rest.forearm_tol'] = ('[D]', 'plan §11 AX1: the forearms within 10 deg of vertical')
TAGS['rest.tail_tip_h'] = ('[E]', '§4.3: the tail trailing low (v01); 4 mm keeps the estimated ventral fin edge just '
                                  'off the floor (ax01 prints it)')
TAGS['rest.p01_femur_elev'] = ('[E]', 'AX1, p01\'s folded hindlimb: the knee looks level with the hip (the limb\'s top '
                                      'about 205 px = 10.9 mm above the floor, the knee\'s radius below it, the hip '
                                      '~9.4 mm up on a belly lying on the floor; ax1/grids/p01_hind_gamma.png)')
TAGS['conflicts'] = ('[D]', 'plan §2.12\'s table as data, with AX0b\'s three new rows and AX1\'s two (the trunk, '
                            'the hip)')
_tag(tuple(f'bars.{k}' for k in SPEC['bars']), '[D]', 'plan §2.1-§2.8 / §11: the bars the later rounds gate')
TAGS['bars.hands_apart_HW'] = ('[D]', 'plan §11 AX1: p13\'s 1.221 a lower bound; the upper bar raised from 1.6 to 1.8 by the '
                                      'lead\'s call at AX2 (the stance at the plan\'s 30 deg back); AX2b\'s 1.64 HW stance '
                                      'sits inside it')

# AX7b (10-30): the gills, the mouth and the digits read on gridded crops (work/bestiary/axolotl/ax7b_notes/ref/, the
# sweep's aview.py; D = p17's top ramus seen side-on, 290 px; NOTES.md there has every count)
_X7 = 'AX7b (ax7b_notes/ref crops), '
TAGS['ax7b.ramus_aspect'] = ('[P p17 p13]', _X7 + 'p17\'s top ramus side-on 290 px against its middle ramus face-on 415 px '
                                             '(one animal, both in focus) = 1.43; p13\'s r1 frontal 0.117 HW against the '
                                             'side-on D 3.39 mm (0.089 HW) = 1.31: the stalk broad across its comb face')
TAGS['ax7b.ramus_aspect_built'] = ('[D]', _X7 + 'the aspect the clay builds (the measured 1.37). The six stalks stack on '
                                          'r1\'s UVs (AX5) through ring-index maps (r3 one 30 deg step) and the rings '
                                          'follow the crossbreed contract (vertex 0 on each ramus\'s own port frame): a '
                                          'roll maps a round stalk onto itself, an oval only when each oval sits in its '
                                          'ring frame where r1\'s does, so families/sprawl.gill_rami turns r2 / r3 '
                                          'WHOLE (bow, root, oval and vanes) about their graft ring\'s axis at '
                                          'graft_share (+4.81 / -4.79 deg), keeping each r1\'s exact similar copy, and '
                                          'AX3 gives their rings r1\'s angle table re-based by ring_shift (the first '
                                          'AX7b build was round: 1.0; the second turned only the oval and the vanes, '
                                          'the bow left behind: 2.5 texels off r1 at AX3 gate 5)')
TAGS['ax7b.graft_share'] = ('[D]', _X7 + 'the stalk share where AX3 lays the six graft rings (its first clean '
                                                  'share on the bowed OVAL stalks: r3\'s, the last of the six to clear '
                                                  'its port fillet; on round bowed stalks 0.17, round 6 0.2425): '
                                                  'gill_rami reads each ring\'s frame here, AX3 checks it lays them here')
TAGS['ax7b.ring_shift'] = ('[D]', _X7 + 'each ramus\'s ring-index shift onto r1\'s (axolotl_uv.RAMUS_SHIFT: the least '
                                     'roll): r1, r2, r3')
TAGS['ax7b.ramus_aspect_ramp'] = ('[D]', _X7 + 'round where the stalk grows out of the head, the full aspect by 0.25 of '
                                         'its length (the fleshy root stays round)')
TAGS['ax7b.ramus_arch'] = ('[P p17]', _X7 + 'p17\'s top ramus: its centre 0.085 L (at 0.36 L) and 0.107 L (at 0.68 L) off '
                                     'the base-tip chord, the tip bent toward the comb side (CLAY gill_arch 0.05 was '
                                     'symmetric)')
TAGS['ax7b.ramus_arch_peak'] = ('[P p17]', _X7 + 'the bow\'s deepest share along the stalk (0.6-0.7 L on p17\'s top ramus)')
_tag(('ax7b.vanes', 'ax7b.ranks_per_vane'), '[P p17 p18]',
     _X7 + 'p17\'s middle ramus (seen face-on from behind) carries filaments from BOTH edges; p18 shows an up-back and a '
           'down-back vane on every ramus, like a feather; p17\'s front row has a staggered rank behind it and p18\'s '
           'vanes run 0.08-0.10 of the stalk width a strand: two ranks a vane at 0.20 D')
TAGS['ax7b.vane_root_deg'] = ('[D from P p17 p18]', _X7 + 'each rank\'s root azimuth off the comb direction on the oval '
                                                       'stalk (outer, inner): near the edges of the posterior face')
TAGS['ax7b.vane_splay_deg'] = ('[D from P p17 p18]', _X7 + 'each rank\'s strand direction off the comb direction (outer, '
                                                        'inner): p17\'s middle ramus\'s vanes leave sideways, p18\'s '
                                                        'up-back and down-back')
TAGS['ax7b.vane_jitter_deg'] = ('[E]', _X7 + 'the strands\' spread about their rank\'s angles')
TAGS['ax7b.fil_spacing_D1'] = ('[P p17]', _X7 + 'p17\'s front row 50-60 px apart (0.18-0.21 D) on every crop along the top '
                                         'ramus (the sweep read 67 px); the same absolute spacing on every ramus')
_tag(('ax7b.comb_from', 'ax7b.comb_to'), '[P p17 p18]',
     _X7 + 'the first strand at x 1770 against the stalk\'s base at 1740 (p17), and the vanes run to and past the tip '
           '(p17, p18): ~0.95 L (gills.comb 0.80 was [E])')
TAGS['ax7b.fil_len_D1'] = ('[P p17]', _X7 + 'p17\'s front row from y 480 to 880-950 at mid-ramus: 1.4-1.5 D (the sweep\'s '
                                     '1.49); the same absolute length on p17\'s middle ramus and p18\'s three')
TAGS['ax7b.fil_len_profile'] = ('[E from P p17 p18]', _X7 + 'the strand length along the comb over fil_len_D1: shorter '
                                                         'at the base and past the tip')
TAGS['ax7b.fil_w_D'] = ('[P p17]', _X7 + 'mid-shaft 23-31 px on p17_top_b at 1.75x (0.08-0.11 D); gills.filament_w_D '
                                  '0.074 is the thin end')
TAGS['ax7b.fil_hang_deg'] = ('[P p18 p14]', _X7 + 'the strands lean toward the ramus tip like a feather\'s barbs (p18) '
                                           'and curve the same way like lashes (p14)')
TAGS['ax7b.fil_droop'] = ('[E]', _X7 + 'the share of world-down in a strand (they float: p13 / p14 show little sag)')
TAGS['ax7b.smile_rise'] = ('[P p15 p18 p13]', _X7 + 'the mouth line at each corner over its front: p15 frontal 20-25 px of '
                                                 'HW 395 (0.05-0.06 HW); p18 lateral 2.6 mm (its lowest point at the '
                                                 'front\'s curve); p13 0.01-0.02 HW where its lobes hide the corners')
TAGS['ax7b.smile_power'] = ('[E from P p15 p14]', _X7 + 'the line flat across the front and rising toward the corners '
                                                      '(p15\'s U): rise x (s / s_c)^p; 3 (the first build 1.6 spread '
                                                      'the rise along the whole line, a gentle curve where p14 / p15\'s '
                                                      'corners hook up sharply)')
TAGS['ax7b.smile_up_built'] = ('[D]', _X7 + 'the corners raised over p13\'s 0.613 (AX2 gate 5 holds them within 0.03 HW: '
                                         '1.2 mm = 0.032 HW, from the clay\'s 0.620; p13\'s corners lie under its lip '
                                         'lobes, so its reading is the line\'s visible end, low)')
TAGS['ax7b.smile_down_built'] = ('[D]', _X7 + 'the front lowered: bounded by the snout\'s section, whose bottom at ring 0 '
                                           '(s 0.008) is 12.75 mm, 1.41 mm under the corner height (the first build\'s '
                                           '1.8 mm drop put the mouth row under it and folded the snout cap: AX2 gate 1, '
                                           'ax7b_notes/ref/snout_profile.png); 0.35 keeps the row 1.06 mm over it. The '
                                           'smile built: 1.55 mm, inside the readings (p13 0.4-0.9, p15 1.9-2.4, p18 2.6)')
TAGS['ax7b.digit_r'] = ('[P p23 p04 p05]', _X7 + 'the digits taper to about half their base width at a rounded tip with '
                                             'no bulb: p23 toe 22-24 -> 11-12 px, p04 25 -> 12 px, p05 the same')

# AX7c (10-30): the smile and the lobes read on gridded crops (work/bestiary/axolotl/ax7c_notes/ref/, the sweep's aview.py;
# NOTES.md there has every reading), built across the front by heads/caudate.smile_y and judged on the clay in the photos'
# own views by ax7c_notes/probe_mouth.py
_X7C = 'AX7c (ax7c_notes/ref crops, probe_mouth.py), '
TAGS['ax7c.corner_up'] = ('[D]', _X7C + 'the commissure over p13\'s 0.613 level (AX2 gate 5 holds it within 0.03 HW = 1.1 '
                                      'mm); 0.40 keeps the whole line under each section\'s widest level but at the snout\'s '
                                      'front stations (AX7b asked 1.2, which the widest level capped at 14.90)')
TAGS['ax7c.smile_U'] = ('[P p13 p15 p14]', _X7C + 'the mouth line\'s rise from the midline to the U\'s end (smile_xU), seen '
                                              'level from the front: p13 (eye level) 0.015 HW under the traced corners\' '
                                              'chord, ~0.04 HW behind its lobes; p15 (camera a little raised) 0.06 HW; p14 '
                                              '(3/4) a ~0.03 HW sag; 1.7 mm = 0.045 HW, which from probe_mouth.py\'s 6 deg '
                                              'raised view measures 0.065 HW to 0.37 HW, p15\'s own span. AX7b\'s 1.55 mm rose '
                                              'along the side, unseen from the front')
TAGS['ax7c.smile_c'] = ('[P p15]', _X7C + 'the U\'s shape, h(u) = (1 + c) u^2 / (u^2 + c) over u = |x| / the U\'s end: p15 '
                                      'curves all the way across, 0.25 / 0.58 / 1.0 of its rise at 0.15 / 0.25 / 0.37 HW; '
                                      'c 1.2 gives 0.26 / 0.61 / 1.0 and measures 0.27 / 0.61 / 1.00 on the clay at eye '
                                      'level; a power law fitting those (1.5) has a soft V at the midline')
TAGS['ax7c.smile_xU'] = ('[P p15]', _X7C + 'where the U ends, off the midline: p15\'s line has done its whole rise by 0.37 '
                                       'HW, where its dark slit ends over the lobes; from there a soft shoulder to the '
                                       'commissure (0.45 HW), the faint fold p14 shows. A U spread to the commissure '
                                       'read as a wide flat line running to the outline')
TAGS['ax7c.lobe_x'] = ('[P p13 p15]', _X7C + 'the lobes\' centre off the midline: p13 0.30-0.36 HW (its left lobe 0.23-'
                                          '0.36, right 0.27-0.42), p15 0.22-0.37 (two lobes a side): under the U\'s ends')
TAGS['ax7c.lobe_w'] = ('[P p13 p15 p14]', _X7C + 'the lobe\'s half-width along the line (life mm; its bump (1 - |t|^3)^2 is '
                                              'flat-bottomed, round): p13 0.13 HW wide, p15 0.065-0.08, p14 ~0.07, the '
                                              'built lobe ~5.5 mm across, p13\'s size (one lobe a side where p15 has two); '
                                              '1.9 read as a notch on the clay')
TAGS['ax7c.lobe_bulge'] = ('[E from P p14 p13]', _X7C + 'how far the lobe stands out of the lower lip\'s rows (life mm): '
                                                    'p14\'s 3/4 shows it about its own half-height proud, p13 swollen')
TAGS['ax7c.lobe_drop'] = ('[D]', _X7C + 'how far the MARGIN hangs lower at the lobe (life mm): a touch: the lobes hang '
                                     'under the margin, as p14 / p15\'s do (FEATURES mouth lobe_rows); 0.9 on the margin '
                                     'flattened the U into a trapezoid with fangs, and stood a beak in the 3/4 silhouette')
TAGS['ax7c.digit_base_k'] = ('[P p04 p23]', _X7C + 'a digit\'s base half-width over its own length (d0 to the tip): p04\'s '
                                              'toe 39 px wide at its web over 118 px free (0.33), p23\'s middle finger '
                                              '31 over 68 (0.46), its toes 0.25-0.35 (the AX7b check: 0.30-0.37 against '
                                              'the clay\'s 0.12-0.14); 0.125 x 2 = 0.25 of the whole digit, measured on the '
                                              'clay at the web\'s end 0.32-0.36 of the free part (the short digits more; '
                                              'ax7c_notes/probe_hand.py h_v2b). The g06 bone lengths are kept (the one '
                                              'calibrated reading; AX0b read p23\'s digits long), so the ratio comes from '
                                              'flesh')
TAGS['ax7c.digit_base_min'] = ('[D]', _X7C + 'the short digits\' base half-width (life mm; AX7b built 0.64 on every digit)')
TAGS['ax7c.digit_tip_k'] = ('[P p04 p23]', _X7C + 'the round tip\'s half-width over the base\'s: p04 39 -> ~12 px, p23 31 '
                                             '-> 16 px near the tip; 0.5 with the full profile (0.35 with a straighter '
                                             'cone read as spikes on the clay: h_v1b)')
TAGS['ax7c.digit_tip_min'] = ('[D]', _X7C + 'the smallest tip half-width (life mm): a round end, not a point')
TAGS['ax7c.digit_taper_p'] = ('[E from P p04 p23]', _X7C + 'the cone\'s profile (1 - u)^p: under 1 the digit stays full '
                                                     'along its length and rounds off near the tip (p23\'s fleshy '
                                                     'fingers), no bulb')
TAGS['ax7c.digit_aspect'] = ('[E from P p04 p23]', _X7C + 'half-width over half-height: the digits lie flat on the floor '
                                                    'a little broader than deep')
TAGS['ax7c.ray_r0'] = ('[D]', _X7C + 'each digit\'s ray (its metapodial under the skin) at the palm\'s / sole\'s proximal row '
                                   'over the digit\'s base: the rays rise out of the slab into ridges toward the digits '
                                   '(AX7c item 3: the slab\'s flat top caught the studio key as a chrome sheet); 0.85 '
                                   'stood their start caps over the sole as a lump (h_v1b)')
TAGS['ax7c.ray_lat'] = ('[D]', _X7C + 'the rays\' start at the proximal row as a share of their digit\'s lateral offset: '
                                    'they fan from the carpus / tarsus to the digit bases')
TAGS['ax7c.k_digit'] = ('[D]', _X7C + 'each digit\'s blend into its limb (life mm; CLAY k_digit 0.35): a softer web and '
                                    'knuckle fillet')
TAGS['ax7c.pad_t'] = ('[D]', _X7C + 'the palm\'s and the sole\'s half thickness (life mm; CLAY palm_t / sole_t): their '
                                  'soles stay on the floor at AX1\'s palm_h / sole_h')
TAGS['ax7c.pad_sag'] = ('[D]', _X7C + 'the pads\' dome across (life mm; CLAY slab_sag 0.25, capped at 0.12 of the row\'s half '
                                    'width by _flat_patch\'s gradient bound): a rounder dorsum between the rays')

# AX8 (10-31): the lip's beads and the digits' tips read on gridded crops (work/bestiary/axolotl/ax8_notes/ref/, the sweep's
# aview.py), built by heads/caudate.py (the beads on the lower lip's rows, on rings 0.42 mm apart over their span) and
# families/sprawl._fleshy_digit (the tips)
_X8 = 'AX8 (ax8_notes/ref crops), '
TAGS['ax8.beads_x'] = ('[P p15 p14]', _X8 + 'the two beads\' centres off the midline: p15 (front, a little raised; HW 415 px '
                                       'from its eyes 205 px apart) left 0.31 / 0.23 HW, right 0.27 / 0.29: two round glassy '
                                       'beads a side, side by side along the lip under the margin, touching (p15_mouth_mid.png); '
                                       'p14\'s near corner a pair side by side (p14_corner_near.png). The places asked on the '
                                       'margin: the bulged rows hang under it, where the section curves in, so the beads '
                                       'measure ~0.04 HW nearer the midline (ax8_notes/measure_beads.py: 0.226 / 0.278 HW); the '
                                       'lateral one ends where the beads\' rings end (s 0.0275, the eye block\'s first ring), '
                                       'so it cannot go further out without a lump on its back half (0.28 / 0.34 measured one)')
TAGS['ax8.bead_w'] = ('[P p15 p14]', _X8 + 'a bead\'s half-length along the line (life mm; its bump (1 - |t|^3)^2): p15\'s beads '
                                      '29-32 px = 0.07-0.077 HW across in x; built 1.15 on the fitted controls (caudate '
                                      'FEATURES mouth bead_post) they measure 0.070 / 0.068 HW across at half their peak, the '
                                      'pass between them 0.64 of the lower (the rings\' resolution: 1.05 gave 0.63)')
TAGS['ax8.bead_bulge'] = ('[E from P p14 p15]', _X8 + 'how far a bead\'s controls move out of the lower lip\'s rows (life mm): '
                                                  'the subdivision\'s bump stands ~0.68 of it, 0.88 / 0.87 mm measured: p14\'s '
                                                  'near pair stands about a third of its width proud')
TAGS['ax8.bead_drop'] = ('[D]', _X8 + 'how far the MARGIN dips at each bead (life mm): AX7c\'s lobe_drop 0.1 halved, so two '
                                    'dips along the U never make the line fall going out (AX2 gate 5b)')
TAGS['ax8.digit_tip_k'] = ('[P p04 p23]', _X8 + 'the tip\'s half-width over the base\'s: p04\'s toes run from 22-25 px at '
                                            'the web\'s end to dark points 5-6 px across (0.22-0.25; p04_foot_grid.png), p23\'s '
                                            'fingers narrow to rounded points (p23_hand.png); AX7c\'s 0.5 left the hands a '
                                            'little human (the AX7c check)')
TAGS['ax8.digit_tip_min'] = ('[D]', _X8 + 'the smallest tip half-width (life mm): 0.6 mm x4, 2.4 of the high\'s 0.25 mm voxels '
                                        '(AX7c 0.30)')
TAGS['ax8.digit_taper_p'] = ('[E from P p04 p23]', _X8 + 'the cone\'s profile (1 - u)^p: 0.75 keeps a digit fleshy to its '
                                                     'middle (0.68 of its base at half length with the tip at 0.22) and closes '
                                                     'it to the fine tip over its last third; 1.0 is a straight cone (AX7c\'s '
                                                     'h_v1b read as spikes)')

# AX10 (11-01): the beads as pearls, the corner's fold, the wrist's and ankle's bend, read on crops in
# work/bestiary/axolotl/ax10_notes/ref/ and judged on the clay by ax10_notes/bead_lab.py beside them (heads/caudate.py's
# pearl and fold_weight, families/sprawl.limb_rest)
_X10 = 'AX10 (ax10_notes/ref crops, bead_lab), '
TAGS['ax10.beads_x'] = ('[P p15 p14]', _X10 + 'the two pearls\' places asked on the margin: p15 left 0.31 / 0.23 HW, right '
                                        '0.27 / 0.29; measured on the clay 0.223 / 0.296 HW (AX8\'s asked 0.265 / 0.32 put '
                                        'the lateral pearl\'s back third past the low\'s eye-block ring at s 0.0247, '
                                        'where the low has a 1.68 mm cell to carry it)')
TAGS['ax10.bead_ra'] = ('[P p15 p14]', _X10 + 'a pearl\'s half-size along the line (life mm, its footprint\'s): p15\'s beads '
                                        '29-32 px = 0.07-0.077 HW across (2.65-2.9 mm); built 1.10, they measure 0.064-0.074 '
                                        'HW across at half their peak, the pass between them 0.39 of the lower peak')
TAGS['ax10.bead_rb'] = ('[P p15 p14]', _X10 + 'its half-size down the lip below its centre (life mm): p15 / p14 show the beads '
                                        'as round as they are wide')
TAGS['ax10.bead_dc'] = ('[E from P p14 p15]', _X10 + 'its centre\'s arc under the margin (life mm): the pearl hangs from the '
                                               'lower lip just under the slit (its top ~0.8 mm under the margin, where '
                                               'the low\'s lower lip runs: AX4\'s first try at 1.30 put the low\'s slit '
                                               'through the pearls\' tops, its lips zigzagging over them)')
TAGS['ax10.bead_h'] = ('[E from P p14 p15]', _X10 + 'how far its controls stand out at its centre (life mm): the limit peaks '
                                              '1.39-1.44 mm, about half its width, a dome (AX8 0.88: a third of its width, '
                                              'a flat lobe)')
TAGS['ax10.bead_p'] = ('[D]', _X10 + 'the dome\'s profile (1 - r^2)^p over its round footprint: 0.5 a hemisphere, so its sides '
                                   'stand steep (AX8\'s (1 - |t|^3)^2 along the line was a plateau with a broad skirt)')
TAGS['ax10.bead_hang'] = ('[E from P p14]', _X10 + 'the share of the push tipped down the lip (p14\'s near pair hangs over the '
                                             'lower lip); 0.3 made teardrops, 0.1 round')
TAGS['ax10.bead_up'] = ('[D]', _X10 + 'the footprint\'s half-size above the centre over below: its top pinched under the '
                                    'margin, its round bottom free')
TAGS['ax10.bead_out'] = ('[D]', _X10 + 'a push out from the pearl\'s centre within the skin (x bead_h x r sqrt(1 - r^2)): its '
                                     'equator wider than its foot, the round outline the photos\' beads show from any '
                                     'side; 0.35, not 0.6: the low\'s rays from the section\'s centre meet a milder '
                                     'undercut; 0.15 (the successor, 11-02): with the low\'s band on the clay\'s own '
                                     'section (sprawl_body clay_band) AX4 gates 9 / 10 pass at 0.15 and fail at 0.35 '
                                     '(2 tilts, the head\'s p1 24.0 deg); the pearls a little narrower at the top, '
                                     'gate 5b 2 a side, pass 0.20 (ax10_notes/try/bl_cmp.png)')
TAGS['ax10.bead_drop'] = ('[D]', _X10 + 'how far the MARGIN dips at each pearl (life mm): AX8\'s 0.05 (gate 5b\'s no W)')
TAGS['ax10.fold_s'] = ('[P p14 p15]', _X10 + 'the corner\'s fold by station: rising from the U\'s end (s 0.034, x 0.37 HW) to '
                                       'full at 0.052, held to 0.062, then rolling back toward the commissure (0.080): p14\'s '
                                       'near end, the margin sagging past the beads into a fleshy lobe over the lower lip '
                                       '(p14_whole.png); p15\'s line hooking down past its beads')
TAGS['ax10.fold_drop'] = ('[E from P p14]', _X10 + 'how far the margin sags at the fold\'s full (life mm): p14\'s lobe hangs '
                                             'about a bead\'s height under the line before it (0.8 read as a lip roll only, '
                                             'bead_lab lab_f1; 2.2 a hard hook from the front, lab_f3)')
TAGS['ax10.fold_corner'] = ('[E from P p14]', _X10 + 'the sag\'s share left at the commissure: the lobe rolls back up into '
                                               'the cheek at the corner')
TAGS['ax10.fold_out'] = ('[E from P p14]', _X10 + 'how far the margin and the two rows above it stand out at the fold (life '
                                            'mm; x 1 / 0.75 / 0.35): a thick rounded upper lip over the corner')
TAGS['ax10.fold_tuck'] = ('[D]', _X10 + 'the lower lip\'s extra tuck under the fold (life mm), so the lobe overhangs it')
TAGS['ax10.fold_end'] = ('[D]', _X10 + 'how far past the commissure the roll fades into the cheek (TL)')
TAGS['ax10.k_pad'] = ('[D]', _X10 + 'the palm\'s and the sole\'s blend into the forearm / shank (life mm; CLAY k_palm 0.6): a '
                                  'filleted bend, not a crease')
# AX13 (11-02): THE PEARLS AS SEPARATE GLASS DROPLETS (species/axolotl_pearls.py; the lead's call over a local cage
# refinement: AX10b found a K 64 ring cannot refine locally, and the low's peg outline is what read as teeth)
_X13 = 'AX13 (the lead\'s call, PLAN.md "AXOLOTL AX10b DONE"; ax13_notes), '
TAGS['ax13.pearls'] = ('[D]', _X13 + '\'parts\': the clay\'s beads come off the skin (heads/caudate.py: no pearl domes, no '
                                   'margin dip, no dense lower-lip rows) and the droplets are their own part and '
                                   'material; anything else keeps AX10\'s skin pearls')
TAGS['ax13.drop_x'] = ('[P p15 p14]', _X13 + 'the two droplets\' centres off the midline: AX10\'s beads_x (p15 left 0.31 / '
                                       '0.23 HW, right 0.27 / 0.29)')
TAGS['ax13.drop_r'] = ('[P p15 p14]', _X13 + 'a droplet\'s semi-axes (life mm): along the lip line, down the lip, out of the '
                                       'skin; p15\'s beads 0.07-0.077 HW across (2.65-2.9 mm) and 0.05-0.06 HW tall '
                                       '(1.9-2.3 mm) whole, touching side by side, round from the front; out a little '
                                       'less (a drop lying on the lip, not a ball)')
TAGS['ax13.drop_n'] = ('[D]', _X13 + 'the template\'s cube-sphere grid per face: 8 x 8 (384 quads, 32 segments round the '
                                   'equator) stays round at the x4 hero close-up with the welded normals')
TAGS['ax13.drop_embed'] = ('[D]', _X13 + 'the share of the out semi-axis sunk into the lower lip: a contact, so the droplet '
                                       'rests on the band rather than floating on it')
TAGS['ax13.drop_top'] = ('[D]', _X13 + 'the droplet top\'s place under the upper lip\'s margin along the lower lip (life mm): '
                                     'tucked just under it, as p15 / p14\'s lie under the margin\'s edge')
TAGS['ax13.drop_touch'] = ('[D]', _X13 + 'the pair\'s along-line semi-axis capped at this share of half the gap between '
                                       'their centres: touching, never merged (p15\'s pair touch)')
TAGS['ax13.drop_lift'] = ('[D from P p15 p14]', _X13 + 'the share of the lower lip\'s tuck taken back under the droplets (by '
                                                  'the beads\' weight along the line): the lips meet behind them, no slit '
                                                  'opening up there (p15 / p14: no dark gap behind the droplets)')
TAGS['ax13.fold_tuck'] = ('[D from P p14]', _X13 + 'the lower lip\'s extra tuck under the corner\'s fold, in place of AX10\'s '
                                             '0.5 (life mm): p14\'s lobe rests ON the lower lip; tucked along a normal '
                                             'that points out and down, AX10\'s lower lip row rose above the fold\'s hem, '
                                             'a 2.5 mm shelf under the fold and the low\'s slit opening upward (the dark '
                                             'corner wedges, ax13_notes/try/before_lip_sections.png)')
TAGS['ax13.fold_lift'] = ('[D from P p14]', _X13 + 'the share of the lower lip\'s own tuck taken back under the fold (by '
                                             'its weight), so the lower lip meets the fold\'s hem')
TAGS['ax13.fold_s'] = ('[D from P p14 p15]', _X13 + 'the corner\'s fold by station, in place of AX10\'s (0.034, 0.052, '
                                              '0.062): its sag rising to full by 0.060 and held to 0.064, so the low\'s '
                                              '1.68 mm rings sample the rise with three cells: over two the lip loop drew '
                                              'the hem as a V point at the corner, a zigzag in both runs (AX4 gate 18)')
TAGS['ax13.drop_alpha'] = ('[D from C, P p15]', _X13 + 'the glass\'s opacity factor (a MATERIAL factor, never a texture '
                                                     'alpha: the engine\'s image decode divides an RGBA texture\'s colour '
                                                     'by its alpha): the engine\'s glass recipe carries the see-through '
                                                     'in the opacity (tools-guides/stack-notes.md: transmission alone '
                                                     'samples a black backdrop here); 0.30 -> 0.40 at the AX13 restart: '
                                                     'p15\'s droplets a milky grey-white over the lip, ours fainter')
TAGS['ax13.drop_transmission'] = ('[D from C]', _X13 + 'the refraction on top of the opacity (the stack notes\' recipe)')
TAGS['ax13.drop_ior'] = ('[C]', _X13 + 'mucus / a watery droplet ~1.33-1.38 in air; the underwater look KEEPS it (AX13 '
                                     'restart, engine_test/axolotl_scene.js pearlMaterial: relative to water, 1.02, the '
                                     'droplets vanished into faint discs, where p14 / p15 underwater show a glint and a '
                                     'rim on each)')
TAGS['ax13.drop_rough'] = ('[D from P p14 p15]', _X13 + 'a small sharp glint on each droplet, as p14 / p15\'s')
TAGS['ax13.drop_coat'] = ('[D]', _X13 + 'a clear coat over the glass (the sharp highlight)')
TAGS['ax13.drop_coat_rough'] = ('[D from P p15]', _X13 + 'the coat\'s roughness: 0.03 -> 0.06 at the AX13 restart, '
                                                       'the glint a soft spot as p15\'s, not a pin-point')
TAGS['ax13.drop_tint'] = ('[P p15]', _X13 + 'the glass\'s faint tint: p15\'s droplets a clear cool grey-white over the lip')
TAGS['ax13.drop_thick'] = ('[D]', _X13 + 'the glass\'s thickness for the refraction (life mm, about the droplet\'s depth)')

TAG_RE =re.compile(r'\[(P|L|R|H|D|E|C)(?:-(?:ap|x0|x2|sw))?(?: (?:from )?[^\]]+)?\]')
MAKER_RE = re.compile(r'\[D-(ap|x0|x2|sw)[ \]]')      # a derived value's maker; a bare [D] is a design decision

# Each leaf's unit (ax00 checks every leaf has one): the group's unless listed
UNIT_GROUP = dict(family='text', body_plan='text', head_archetype='text', author_scale='1', life_scale='1', a1='mm',
                  ratios='1', stations='TL', station_map='1', profile='TL', widths='HW', head='HW', gills='1',
                  trunk='TL', fins='mm', limbs='mm', skin='mm', colour='srgb', morphs='1', motion='1', rig='mm',
                  rest='mm', conflicts='text', bars='1', ax7b='1', ax7c='mm', ax8='mm', ax10='mm', ax13='mm')
UNIT_KEY = {'stations.skull_end_mm': 'mm', 'ratios.TL_x4': 'mm', 'ratios.HL_x4': 'mm', 'ratios.HW_x4': 'mm',
            'ratios.tail_height_x4': 'mm', 'widths.head_widest_s': 'TL', 'widths.trunk_mm': 'mm',
            'widths.pelvis_mm': 'mm', 'widths.tailbase_mm': 'mm', 'widths.radiograph_g_at_A1': 'g',
            'widths.gamel_g_at_A1': 'g', 'widths.HW_SVL_p09': '1', 'head.height_mm': 'mm', 'head.eyes_apart_mm': 'mm',
            'head.eye_frontal': 'frac', 'head.naris_frontal': 'frac', 'head.mouth_frontal': 'frac',
            'head.cheek_frontal': 'frac', 'head.eye_d_TL': 'TL', 'head.eye_d_mm': 'mm', 'head.eye_d_range': 'TL',
            'head.mouth_w_mm': 'mm', 'head.skull_len_g06': 'mm', 'head.skull_W_g06': 'mm', 'head.skull_WL': '1',
            'head.skull_len_A1': 'mm', 'head.iris_ring': 'frac', 'head.pupil': 'frac', 'head.eye_HL_x0b': 'HL',
            'head.commissure_HL_x0b': 'HL', 'gills.frontal_r1': 'HW', 'gills.frontal_r2': 'HW', 'gills.frontal_r3': 'HW',
            'gills.emergence_r1': 'frac', 'gills.emergence_r2': 'frac', 'gills.emergence_r3': 'frac',
            'gills.frontal_deg': 'deg', 'gills.side_TL': 'TL', 'gills.side_elev': 'deg', 'gills.chord': 'mm',
            'gills.chord_raw': 'mm', 'gills.chord_115': 'mm', 'gills.lower_bound': 'mm', 'gills.lower_bound_raw': 'mm',
            'gills.r2_up_check': 'mm', 'gills.ramus_D': 'D', 'gills.root_D': 'D', 'gills.D_mm': 'mm',
            'gills.filament_len_D': 'D', 'gills.filament_w_D': 'D', 'gills.filament_spacing_D': 'D',
            'gills.ranks': 'count', 'gills.per_rank': 'count', 'gills.per_ramus': 'count', 'gills.total': 'count',
            'gills.lod0_tris': 'count', 'gills.lod1_tris': 'count', 'gills.lod0_total': 'count',
            'gills.lod1_total': 'count', 'gills.p18_elev': 'deg', 'gills.p18_L_HL': 'HL', 'gills.p18_head_axis': 'deg',
            'gills.rest_motion': 'text', 'trunk.grooves': 'count', 'trunk.grooves_alt': 'count',
            'trunk.groove_depth': 'mm', 'trunk.crease_over_spacing': '1', 'trunk.section': 'mm',
            'fins.ventral_from': 'text', 'fins.backlit_ratio': '1', 'fins.backlit_Ylin': '1',
            'limbs.hand_plan_TL': 'TL', 'limbs.k06': '1', 'limbs.digits': 'count', 'limbs.hands_apart_HW': 'HW',
            'limbs.hands_apart_max_HW': 'HW', 'limbs.phalanges': 'count', 'limbs.finger_rel': '1',
            'limbs.toe_rel': '1', 'limbs.webbing': 'text', 'skin.f0': '1', 'skin.f0_salamandretta': '1',
            'skin.rough_body': '1', 'skin.rough_head': '1', 'skin.rough_limbs': '1', 'skin.rough_fins': '1',
            'skin.rough_dorsum_venter': '1', 'skin.micro_tile': '1', 'skin.micro_strength': '1',
            'colour.flank_dark_share': '1', 'colour.spot_TL': 'TL', 'colour.spot_nn_TL': 'TL', 'colour.gold_hsv': 'hsv',
            'motion.walk_mm_s': 'mm/s', 'motion.walk_TL_mm': 'mm', 'motion.contact': '%', 'motion.buoyancy': '%',
            'motion.swim_hz': 'Hz', 'motion.tip_radius_mm': 'mm', 'motion.deg_per_tail_joint': 'deg',
            'motion.gill_flutter_hz': 'Hz', 'motion.tail_step': 'TL', 'motion.tip_radius_TL': 'TL',
            'rig.n_joints': 'count', 'rig.n_spine': 'count', 'rig.n_tail': 'count', 'rig.gill_joints': 'count',
            'rig.helpers_x10b': 'text', 'rig.spine_from': 'TL', 'rig.spine_to': 'TL', 'rig.tail_from': 'TL', 'rig.tail_to': 'TL',
            'rig.glenoid_frac': 'frac', 'rig.acetabulum_frac': 'frac', 'rig.spine_frac': 'frac',
            'rig.head_frac': 'frac', 'rig.jaw_frac': 'frac', 'rig.digit_splay': 'deg', 'rig.toe_splay': 'deg',
            'rig.gill_base_inset': '1', 'rig.eye_axis': '1', 'rig.twist_upper': 'frac', 'rig.twist_lower': 'frac',
            'rig.breath_chest': 'frac', 'rig.breath_belly': 'frac', 'rest.humerus_back_plan': 'deg',
            'rest.hand_out': 'deg', 'rest.femur_fwd': 'deg', 'rest.foot_out': 'deg',
            'rest.hands_apart_target_HW': 'HW', 'rest.forearm_tol': 'deg', 'rest.p01_femur_elev': 'deg',
            'rig.throat_frac': 'frac', 'rig.chin_s': 'TL', 'rig.tongue_s': 'TL', 'rig.digit_mid': 'frac',
            'rig.vfin_share': 'frac', 'profile.head_pitch_p01_x2': 'deg', 'widths.head_widest_s_x2': 'TL',
            'profile.fin_call_x2': 'text', 'profile.fin_scale_x2': '1', 'limbs.k06_x2': '1',
            'stations.skull_end_mm_plan': 'mm',
            'ax7b.ramus_aspect_ramp': 'frac', 'ax7b.ramus_arch': 'frac', 'ax7b.ramus_arch_peak': 'frac',
            'ax7b.ramus_aspect_built': '1', 'ax7b.graft_share': 'frac', 'ax7b.ring_shift': 'count',
            'ax7b.vanes': 'count', 'ax7b.ranks_per_vane': 'count', 'ax7b.vane_root_deg': 'deg',
            'ax7b.vane_splay_deg': 'deg', 'ax7b.vane_jitter_deg': 'deg', 'ax7b.fil_spacing_D1': 'D',
            'ax7b.comb_from': 'frac', 'ax7b.comb_to': 'frac', 'ax7b.fil_len_D1': 'D', 'ax7b.fil_len_profile': 'frac',
            'ax7b.fil_w_D': 'D', 'ax7b.fil_hang_deg': 'deg', 'ax7b.smile_rise': 'mm', 'ax7b.digit_r': 'mm',
            'ax7b.smile_up_built': 'mm', 'ax7b.smile_down_built': 'mm',
            'ax7c.smile_c': '1', 'ax7c.smile_xU': 'HW', 'ax7c.lobe_x': 'HW', 'ax7c.digit_base_k': '1', 'ax7c.digit_tip_k': '1',
            'ax7c.digit_taper_p': '1', 'ax7c.digit_aspect': '1', 'ax7c.ray_r0': '1', 'ax7c.ray_lat': '1',
            'ax8.beads_x': 'HW', 'ax8.digit_tip_k': '1', 'ax8.digit_taper_p': '1',
            'ax10.beads_x': 'HW', 'ax10.bead_p': '1', 'ax10.bead_hang': '1', 'ax10.bead_up': '1', 'ax10.bead_out': '1',
            'ax10.fold_s': 'TL', 'ax10.fold_corner': '1', 'ax10.fold_end': 'TL',
            'ax13.pearls': 'text', 'ax13.drop_x': 'HW', 'ax13.drop_n': 'count', 'ax13.drop_embed': '1',
            'ax13.drop_lift': '1', 'ax13.fold_lift': '1', 'ax13.fold_s': 'TL',
            'ax13.drop_touch': '1', 'ax13.drop_alpha': '1', 'ax13.drop_transmission': '1', 'ax13.drop_ior': '1',
            'ax13.drop_rough': '1', 'ax13.drop_coat': '1', 'ax13.drop_coat_rough': '1', 'ax13.drop_tint': 'srgb'}
for _k in SPEC['rig']:
    if _k.startswith('r_'):
        UNIT_KEY[f'rig.{_k}'] = 'deg'
for _m in MORPH_ORDER:
    UNIT_KEY[f'morphs.{_m}.thin'] = 'srgb'
    UNIT_KEY[f'morphs.{_m}.eye'] = 'text'

# Each [D-ap] leaf's line in aplan_numbers.py's output, as ax00_spec.py's parser names it, and the printed precision
# (ax00 compares within half a unit of the last printed digit). A tuple value compares elementwise to a tuple key
_S = ('naris', 'mouth', 'eye', 'gill', 'shoulder', 'fin', 'groin')
APLAN = {
    'ratios.SVL_TL': ('svl_tl', 4), 'ratios.HL_TL': ('hl_tl', 4), 'ratios.HW_HL': ('hw_hl', 3),
    'ratios.tail_height_TL': ('th_tl', 4), 'ratios.HW_SVL': ('w.hw_svl_lit', 3), 'ratios.TL_x4': ('x4.tl', 0),
    'ratios.HL_x4': ('x4.hl', 1), 'ratios.HW_x4': ('x4.hw', 1), 'ratios.tail_height_x4': ('x4.th', 1),
    'stations.naris': ('st.naris', 3), 'stations.mouth_p01': ('st.mouth', 3), 'stations.eye_c': ('st.eye', 3),
    'stations.gill_base': ('st.gill', 3), 'stations.shoulder': ('st.shoulder', 3), 'stations.fin_origin': ('st.fin', 3),
    'stations.groin': ('st.groin', 3), 'stations.shoulder_p08': ('st.p08_shoulder', 3),
    'stations.hip_p01': ('hip.p01', 4), 'stations.hip_p08': ('hip.p08', 4),
    'station_map.head': ('map.head', 3), 'station_map.trunk': ('map.trunk', 3), 'station_map.tail': ('map.tail', 3),
    'profile.core': ('core', 4), 'profile.dorsal_fin': ('finx', 4), 'profile.tail_total': ('tail', 4),
    'profile.fin_scale': ('fin_k', 3),
    'widths.head_widest_s': ('w.head_wmax', 4), 'widths.trunk_mm': ('w.trunk_design_mm', 1),
    'widths.trunk_HW_p09': ('w.trunk_gravel', 3), 'widths.pelvis_HW': ('w.pelvis', 3),
    'widths.pelvis_mm': ('w.pelvis_mm', 1), 'widths.tailbase_HW': ('w.tailbase', 3),
    'widths.tailbase_mm': ('w.tailbase_mm', 1), 'widths.HW_SVL_p09': ('w.hw_svl_p09', 3),
    'head.height_HW': ('h.height', 3), 'head.height_mm': ('h.height_mm', 1), 'head.eyes_apart_HW': ('h.eyes', 3),
    'head.eyes_apart_mm': ('h.eyes_mm', 1), 'head.nares_apart_HW': ('h.nares', 3), 'head.mouth_w_HW': ('h.mouth', 3),
    'head.mouth_w_mm': ('h.mouth_mm', 1), 'head.eye_d_mm': ('h.eye_d_mm', 2), 'head.eye_frontal': ('f.eye', 3),
    'head.naris_frontal': ('f.naris', 3), 'head.mouth_frontal': ('f.mouth', 3), 'head.cheek_frontal': ('f.cheek', 3),
    'gills.emergence_r1': ('f.r1', 3), 'gills.emergence_r2': ('f.r2', 3), 'gills.emergence_r3': ('f.r3', 3),
    'gills.frontal_deg': ('g.theta', 1), 'gills.side_elev': ('g.elev', 1), 'gills.chord_raw': ('g.L_raw', 1),
    'gills.chord_115': ('g.L_115', 1), 'gills.chord': ('g.L_115', 1), 'gills.u_r1': ('g.u.r1', 2),
    'gills.u_r2': ('g.u.r2', 2), 'gills.u_r3': ('g.u.r3', 2), 'gills.lower_bound': ('g.bound_115', 1),
    'gills.lower_bound_raw': ('g.bound_raw', 1), 'gills.r2_up_check': ('g.r2_up', 1), 'gills.D_mm': ('fil.D', 2),
    'gills.per_rank': ('fil.per_rank', 0), 'gills.per_ramus': ('fil.per_ramus', 0), 'gills.total': ('fil.total', 0),
    'gills.lod0_tris': ('fil.lod0', 0), 'gills.lod1_tris': ('fil.lod1', 0), 'gills.lod0_total': ('fil.lod0_total', 0),
    'gills.lod1_total': ('fil.lod1_total', 0),
    'trunk.groove_stations': ('gr.10', 3), 'trunk.groove_stations_11': ('gr.11', 3), 'trunk.groove_spacing': ('gr.map', 4),
    'limbs.upper_arm_p01': ('limb.upper_arm_mm', 1), 'limbs.forearm_p01': ('limb.forearm_mm', 1),
    'limbs.hand_p01_min': ('limb.hand_mm', 1), 'limbs.k06': ('limb.k06', 3), 'limbs.g06_bony': ('limb.bony', 1),
    'limbs.femur': ('limb.femur', 1), 'limbs.tibia': ('limb.tibia', 1), 'limbs.tarsus': ('limb.tarsus', 1),
    'limbs.mt_digit': ('limb.mt_digit', 1), 'limbs.adpressed': ('limb.adpressed', 1),
    'limbs.hands_apart_HW': ('h.hands', 3),
    'motion.walk_TL_s': ('mo.walk_TL_s', 2), 'motion.cycle_stride_TL': ('mo.cycle', 2), 'motion.swim_hz': ('mo.hz', 2),
    'motion.body_wave': ('mo.wave', 2), 'motion.slip': ('mo.slip', 2), 'motion.tip_curvature': ('mo.kappa', 2),
    'motion.tip_radius_TL': ('mo.radius', 3), 'motion.tip_radius_mm': ('mo.radius_mm', 1),
    'motion.tail_step': ('mo.tail_step', 4), 'motion.deg_per_tail_joint': ('mo.deg_joint', 1),
    'rig.n_joints': ('rig.joints', 0),
}

# Each [P] / [L] leaf with a value in the sweep's data files: (file, dotted path[, index]) per element; files are
# 'photos' (data/res_photos.json), 'lit' (data/literature.json), 'colour' (data/res_colour.json)
_SEMK = 'SEMARNAT_2018_PACE_citing_Ramirez-Bautista_2009'
_DA = 'DAout_Aerts_1999_BelgJZool_129_305'
_GA = 'Gamel_Pinti_Astley_2024_IntegrOrgBiol_6_obae013'
_C1, _C6, _C3, _C8 = ('p01_wildtype_backlit_neutral', 'p06_wildtype_zoo_light', 'p03_leucistic_tank_light',
                      'p08_white_albino_cyan_cast')
RES = {
    'a1.SVL': ('lit', f'{_SEMK}.SVL_mm', 0), 'a1.tail': ('lit', f'{_SEMK}.cloaca_to_tail_tip_mm', 0),
    'a1.HL': ('lit', f'{_SEMK}.head_length_mm', 0), 'a1.HW': ('lit', f'{_SEMK}.head_width_mm', 0),
    'a1.tail_height': ('lit', f'{_SEMK}.tail_height_mm', 0), 'a1.SVL_sd': ('lit', f'{_SEMK}.SVL_mm', 1),
    'a1.tail_sd': ('lit', f'{_SEMK}.cloaca_to_tail_tip_mm', 1), 'a1.HL_sd': ('lit', f'{_SEMK}.head_length_mm', 1),
    'a1.HW_sd': ('lit', f'{_SEMK}.head_width_mm', 1), 'a1.tail_height_sd': ('lit', f'{_SEMK}.tail_height_mm', 1),
    'trunk.grooves_alt': ('lit', f'{_SEMK}.costal_folds'),
    'head.eye_d_TL': ('photos', 'p01.eye_TL'), 'head.eye_d_range': (('photos', 'p08.eye_TL'), ('photos', 'p06.eye_TL')),
    'head.skull_len_g06': ('photos', 'g06.skull_length_mm'),
    'head.skull_W_g06': (('photos', 'g06.skull_width_mid_mm'), ('photos', 'g06.skull_width_rear_max_mm')),
    'gills.frontal_r1': (('photos', 'p13.r1_dorsal_stalk_HW', 0), ('photos', 'p13.r1_dorsal_stalk_HW', 1)),
    'gills.frontal_r2': (('photos', 'p13.r2_middle_stalk_HW', 0), ('photos', 'p13.r2_middle_stalk_HW', 1)),
    'gills.frontal_r3': (('photos', 'p13.r3_ventral_stalk_HW', 0), ('photos', 'p13.r3_ventral_stalk_HW', 1)),
    'gills.side_TL': (('photos', 'p01.gill_r2_stalk_TL'), ('photos', 'p01.gill_r3_stalk_TL')),
    'gills.ramus_D': ('photos', 'p17.ramus_length_D'), 'gills.filament_len_D': ('photos', 'p17.filament_length_D'),
    'gills.filament_w_D': ('photos', 'p17.filament_width_D'),
    'gills.filament_spacing_D': ('photos', 'p17.filament_root_spacing_D'), 'gills.ranks': ('photos', 'p17.ranks'),
    'trunk.groove_spacing_p01': tuple(('photos', 'p01.groove_spacing_TL', i) for i in range(7)),
    'trunk.groove_mean': ('photos', 'p01.groove_spacing_mean_TL'),
    'fins.backlit_Ylin': (('colour', f'{_C1}.tail_flank_transmitted.Ylin'), ('colour', f'{_C1}.dorsal_fin_transmitted.Ylin'),
                          ('colour', f'{_C1}.trunk_flank.Ylin')),
    'skin.spongiosum': ('photos', 's01.stratum_spongiosum_mm'), 'skin.compactum': ('photos', 's01.stratum_compactum_mm'),
    'skin.leydig': (('photos', 's01.leydig_cell_mm', 0), ('photos', 's01.leydig_cell_mm', 1)),
    'colour.wild_flank': ('colour', f'{_C1}.trunk_flank.median'), 'colour.wild_flank_dark': ('colour', f'{_C1}.trunk_flank.dark'),
    'colour.wild_flank_light': ('colour', f'{_C1}.trunk_flank.light'), 'colour.wild_head': ('colour', f'{_C1}.head_dorsal.median'),
    'colour.wild_tail_trans': ('colour', f'{_C1}.tail_flank_transmitted.median'),
    'colour.wild_fin_trans': ('colour', f'{_C1}.dorsal_fin_transmitted.median'),
    'colour.wild_filaments': ('colour', f'{_C1}.gill_filaments.median'),
    'colour.flank_dark_share': ('colour', f'{_C1}.trunk_flank.dark_share'),
    'colour.spot_TL': ('colour', f'{_C1}.tail_flank_transmitted.spots_deq_median_TL'),
    'colour.spot_nn_TL': ('colour', f'{_C1}.tail_flank_transmitted.spots_nn_median_TL'),
    'colour.gold_field': ('colour', f'{_C6}.head_dorsal_gold.median'), 'colour.p06_flank': ('colour', f'{_C6}.body_flank.median'),
    'colour.p06_gills': ('colour', f'{_C6}.gills.median'), 'colour.p06_tail': ('colour', f'{_C6}.tail.median'),
    'colour.gold_hsv': tuple(('colour', f'{_C6}.head_dorsal_gold.HSV', i) for i in range(3)),
    'colour.leucistic_body': ('colour', f'{_C3}.body_flank.median'), 'colour.leucistic_head': ('colour', f'{_C3}.head.median'),
    'colour.leucistic_gills': ('colour', f'{_C3}.gills.median'), 'colour.albino_body': ('colour', f'{_C8}.body.median'),
    'colour.albino_gills': ('colour', f'{_C8}.gills.median'),
    'motion.walk_mm_s': (('lit', f'{_GA}.walking_speed_cm_s', 0, 10.0), ('lit', f'{_GA}.walking_speed_cm_s', 1, 10.0)),
    'motion.walk_TL_mm': ('lit', f'{_GA}.TL_cm', 0, 10.0),
    'motion.contact': (('lit', f'{_GA}.limb_contact_percent.fore'), ('lit', f'{_GA}.limb_contact_percent.hind')),
    'motion.buoyancy': ('lit', f'{_GA}.buoyant_support_percent'),
    'motion.swim_wavelength': ('lit', f'{_DA}.adult_specific_wavelength_L'),
    'motion.swim_amp': ('lit', f'{_DA}.adult_tail_tip_amplitude_L'),
    'motion.swim_stride': ('lit', f'{_DA}.adult_specific_stride_length_L'),
    'motion.swim_max': ('lit', f'{_DA}.adult_max_speed_L_per_s'),
    'motion.swim_voluntary': ('lit', f'{_DA}.adult_voluntary_speed_L_per_s'),
}

# The landmarks that must strictly increase along the body (plan §2: "stations strictly increase along the body"):
# the built animal's order from the snout, with the stations AX1 builds (the AX0b commissure and eye)
STATION_ORDER = ('naris', 'eye_c_x0b', 'commissure', 'jaw_hinge', 'head_joint', 'poll', 'throat', 'neck', 'gular_fold',
                 'gill_base', 'shoulder', 'shoulder_joint', 'fin_origin', 'groin', 'hip', 'vent')


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


def by_maker(maker, tags=None):
    """the keys whose tag names this derived value's maker ('ap', 'x0' or 'sw'): each must be rerunnable"""
    tags = TAGS if tags is None else tags
    return sorted(k for k, (t, _) in tags.items() if any(m.group(1) == maker for m in MAKER_RE.finditer(t + ' ')))


def unit(key):
    """a leaf's unit: mm, TL, HW, HL, D, frac, deg, count, srgb, hsv, g, Hz, %, mm/s, 1 or text"""
    return UNIT_KEY.get(key, UNIT_GROUP[key.split('.')[0]])


def get(spec, key):
    """the value at a dotted key"""
    v = spec
    for k in key.split('.'):
        v = v[k]
    return v


def mm(s):
    """a TL fraction in life mm on A1"""
    return s * SPEC['a1']['TL']


def interp(table, s):
    """a (s, value) table at s: linear inside, its end values outside"""
    if s <= table[0][0]:
        return table[0][1]
    for (a, va), (b, vb) in zip(table, table[1:]):
        if a <= s <= b:
            return va + (vb - va) * (s - a) / (b - a)
    return table[-1][1]


def core_depth(s):
    """the body core's depth (TL) at station s: the trunk core table to 0.50, then the tail's core (AX0b's shared-core
    reading) to the tip, blended linearly across 0.50 -> the first tail reading; tapering to 0 at s = 1"""
    p = SPEC['profile']
    if s <= p['core'][-1][0]:
        return interp(p['core'], s)
    tail = ((p['core'][-1][0], p['core'][-1][1]),) + p['tail_core_TL_x0b'] + ((1.0, 0.0),)
    return interp(tail, s)
