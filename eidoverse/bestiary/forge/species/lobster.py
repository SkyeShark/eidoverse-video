"""EUROPEAN LOBSTER (Homarus gammarus, adult male): the Bestiary's fourth realistic base, a DECAPOD
(work/bestiary/research/LOBSTER_PLAN.md). L1, the design animal, is a COMPOSITE, one source per region (plan §0.1): the
dorsal body and both claws from the Wiesbaden mount M1 (c11); the lateral depths and standing heights from the live P2
(c06); the walking legs from M4 (n01) as ratios to its fan; the dentition and palm surface from M3 (n04); the length of
the stretched body from Pope 1955 [L1].

THE BIND'S LENGTH (the lead's decision on plan question 1b, 10-27: option (a)): the abdomen is bound STRAIGHT at Pope's
stretched length, male TL = 2.507 CL + 25.9 = 276.6 mm at CL 100 (2.766 CL), so the abdomen (carapace margin to telson
tip) is TL - CL - rostrum = 1.540 CL, cut into M1's tergite proportions. A hinged abdomen of rigid tergites is longest
when straight, so the photos' TL 2.51 (M1, a mount) and 2.58 CL (P1, live, its tail sloping from the raised carapace to
the floor) are REST poses' projections, never the bind: work/bestiary/tests/x00_spec.py checks them against rest poses
of this abdomen (its 'rest pose' gate). The plan's earlier row (TL 258.1 straight, from P1's 1.355 CL abdomen) is kept
only as length.abdomen_P1, a lower bound.

UNITS: LIFE MILLIMETRES, degrees, sRGB8 for the palette facts. The generator (families/decapod.py, X1) multiplies once by
SPEC['author_scale'] = 4: L1 is built and exported at x4 (1.11 m at the bind) with extras.bestiary.life_scale = 0.25
(plan §5.8). THE PLAN FRAME: the orbit (its posterior margin) on the midline at z 0, +z forward (the rostrum's tip at
+22.6), +y up from the GROUND, +x the creature's LEFT (DESIGN.md). Every sided value is the LEFT side's; the right is its
mirror p_R = M p_L, EXCEPT the chelae: the crusher is the left cheliped's own part and the cutter the right's (handedness
'L', plan §2.3), and a handedness flip swaps them, never mirrors one.

SOURCES: the sweep's tracings work/bestiary/research/lobster_work/data/src/src_<id>.json (PHOTO_SRC maps each photos.*
leaf to its measure; x00_spec.py recomputes every one through the sweep's own lmeasure.evaluate), the literature
(lobster_work/data/literature.md L1-L16) and the plan's arithmetic (research/lobster_work/plan/lplan_numbers.py). The
X0b top-ups (research/lobster_work/x0b/) add their own rows, tagged with the x0b maker; x00b_measure.py recomputes
them.

TAGS holds every leaf's source in the plan's legend ("Tags"): [P] a photo reading (photo id), [L] literature L1-L16,
[G] a game asset, [H] a house file, [D] a design decision (its reason in the note), [E] an estimate (its gate in the
note), [C] textbook knowledge outside the sweep's sources, [S] a search summary only. Derived rows carry a maker: -lp
the plan's lplan_numbers.py rule, -x0 derived HERE by the rule in its note, -x0b the X0b measurements, -x1 the X1
skeleton round (the rig.* design rows and the x1.* leg readings); x00_spec.py / x00b_measure.py / x01_skeleton.py
recompute each.

X1 (10-28, the skeleton: families/decapod.py): rig.* holds the bind's design values (the lead's call: RAISED, the
walking stance, joints near mid-range, the dorsum at c10's margin + L1's depth; c06's crouch the REST pose), each
tagged; x1.* holds the walking legs' knees and tips read on c03 / c01 in each photo's body frame (research/
lobster_work/x1/data/src_c03_x1.json, src_c01_x1.json), whose medians set the legs' plan directions (rig.leg_az).

X2 (10-28, the clay; families/decapod_parts.py): the CHELIPED MEASURED before the arms' clay (the lead's call after the
X1 review). x2.* holds the readings (research/lobster_work/x2/data/src_<id>_x2.json through lmeasure): M1's own two
carpi and wrists (c11: the carpus IS the large knobby segment attached to the claw, as on M3, M4 and the Cambridge
mount), M3's attached crusher chain lying flat (n04, ratios only), M4's pinned chelipeds (n01) and c13's chain (a
cross-check). rig.cheliped.seg is now derived from them (the carpus c11's, the merus and the basi-ischium by the flat
chains' ratios to it), and rig.cheliped.wrist_z holds the bind's wrists at c11's traced mean; work/bestiary/tests/
x02_clay.py recomputes every -x2 row.

X2b (10-29, the one clay fix; the lead's calls on the X2 check): chela.cutter_len is M1's WHOLE cutter (its fixed finger
continued under the crusher's dactyl to c13's narrow rounded tip, x2.c13.tip_palm; M1's traced 107.7 was a lower bound),
the cutter's frame turned rig.cheliped.cutter_axis onto its true axis (its hinge and dactyl rows follow); pleopods 2-5
lie tucked forward along the sternites (rig.pleopod.tilt / len / drop_25 / at_25; the rest's fold 0).

X2c (10-29, a short touch-up; the lead's calls on the X2b check): the cutter's fixed-finger cap rig.cheliped.cutter_cap
is FITTED to c13's tip profile (x2.c13.tip_profile at x2.c13.tip_stations, like for like: across the finger's own axis,
c13's tip scaled by its palm), so chela.cutter_len, rig.cheliped.cutter_axis, cutter_hinge b and cutter_dactyl follow
from the new tip; pleopods 2-5 folded forward in the slot beside the deeper sternites (rig.pleopod.drop_25 per somite,
x_25, splay_25; decapod_parts ABD floor / stern / slot: the sternal band shows in the notches between the tongues).

MORPHS (plan §2.8): female, giant (M2), regenerating claw, two crushers. morph(name) composes each from SPEC.
"""
import copy
import re

AUTHOR_SCALE = 4.0

SPEC = dict(
    family='arthropod', body_plan='decapod', author_scale=AUTHOR_SCALE, sex='male', handedness='L',
    # ---- the photos' readings, each a ratio to its photo's unit (CL, M3's crusher propodus, M4's fan), as the sweep's
    # tracings give them (lmeasure.py; x00 recomputes each from src_<id>.json); M1 c11, M2 n03, P1 c03, P2 c06, M3 n04, M4 n01
    photos=dict(
        M1=dict(rostrum=0.22700, cervical=0.50460, cara_width=0.53681, eye_spacing=0.14417, cornea=0.05215,
                antscale=0.33743, segs=(0.16104, 0.21012, 0.18865, 0.19325, 0.19018, 0.16567, 0.17485),
                abdomen=1.28376, TL=2.51076, abd2_w=0.44325, abd5_w=0.43098, fan=1.04601, cr_len=1.15338,
                cr_palm=0.58666, cr_free=0.41719, cu_len=1.07692, cu_palm=0.34033),
        M2=dict(rostrum=0.22523, cara_width=0.60591, cr_len=1.26915, cr_palm=0.52412, cu_len=0.97991, cu_palm=0.38531,
                CL_bar=158.93),
        P1=dict(cara_width=0.45384, abd2_w=0.52093, fan=0.97082, abdomen=1.35518, TL=2.58438, antenna_chord=1.70447,
                claw_U=1.05859, claw_L=1.05770),
        P2=dict(cervical=0.50176, cara_depth=0.58139, abd2_depth=0.43992, dorsum_ub=0.84302, margin_ub=0.26163,
                cornea=0.06008),
        M3=dict(prop_bar=237.40, dactyl=0.45227, palm=0.46337, molar_dac=0.05175, molar_fix=0.08625, saw=0.23964),
        M4=dict(P4=(0.35165, 0.13740, 0.28287, 0.17298, 1.02849), P5=(0.29241, 0.13703, 0.30186, 0.14428, 0.98338),
                fan_bar=68.73)),
    # ---- L1's body and cephalothorax (plan §2.1)
    body=dict(CL=100.0, rostrum=22.611, cervical=50.318, cara_width=53.681, cara_depth=48.820, deepest_z=-72.674,
              cornea=(5.215, 6.008), cornea_spacing=14.417, eye_z=4.651, antscale_tips=33.743, rostral_teeth=3),
    # ---- lengths: the bind straight at Pope's stretched length (question 1b, option (a))
    length=dict(TL_bind=276.600, TL_stretched=276.600, TL_stretched_f=283.200, abdomen=153.989, abdomen_M1=128.376,
                abdomen_P1=135.518, TL_M1=251.076, TL_P1=258.438, mass=0.6817, mass_f=0.6375),
    # ---- abdomen and tail fan (plan §2.2): T1..T6, telson along the dorsal midline at the bind
    abdomen=dict(segs=(19.317, 25.204, 22.629, 23.180, 22.813, 19.872, 20.974), w2=44.325, w5=43.098, d2=35.430,
                 fan_spread=100.0, overlap=(0.15, 0.25), pleopod_pairs=5, uropod_reach=1.0),
    # ---- the chelipeds (plan §2.3): the crusher on the LEFT, the cutter on the RIGHT (handedness 'L')
    chela=dict(crusher_len=115.338, crusher_palm=58.666, cutter_len=114.993, cutter_palm=34.033, crusher_free=41.719,
               crusher_dactyl=52.164, molar_fixed=9.948, molar_dactyl=5.969, saw_run=41.104, saw_run_M3=27.639,
               saw_denticles=(20, 30), crusher_base=23.059, cutter_base=21.321,
               granule=(0.25, 0.40), granule_spacing=(0.8, 1.2), setal_pit=(0.40, 0.65), tubercles=(5, 7),
               crusher_thick=30.0, cutter_thick=20.0, dactyl_open=(40.0, 55.0)),
    # ---- walking legs (plan §2.4), L1 at the design fan 1.00 CL from M4's ratios: BASIS to tip (the coxa NOT included)
    legs=dict(P4=dict(basis_tip=102.849, basis_ischium=8.359, merus=35.165, carpus=13.740, propodus=28.287,
                      dactyl=17.298, coxa=11.096),
              P5=dict(basis_tip=98.338, basis_ischium=10.781, merus=29.241, carpus=13.703, propodus=30.186,
                      dactyl=14.428, coxa=10.246),
              P2=dict(basis_tip=102.849), P3=dict(basis_tip=102.849),
              coxa=10.671, merus_width=6.0,
              # each coxa (x of its medial articulation, z from the orbit, x of its coxa-basis joint), the LEFT side
              coxae=dict(P1=(6.557, -25.410, 19.672), P2=(6.557, -42.486, 18.989), P3=(6.557, -59.563, 18.306),
                         P4=(6.557, -76.639, 17.623), P5=(6.557, -93.443, 16.803))),
    # ---- antennae, antennules (plan §2.5)
    antenna=dict(total=180.0, peduncle=30.0, flagellum=150.0, antennule=30.0),
    # ---- the rest pose (plan §2.1): P2 (c06) resting on sand. The sweep read the ground at the sand line against the
    # glass (y 795), where only the nearest dactyl stands: every height here is an UPPER BOUND (checker 10-27) until
    # X0b (9) solves c06's camera. (z, h): z from the orbit (+ forward), h above that line, life mm
    rest=dict(c06_ub=dict(orbit=(0.0, 80.620), eye_c=(4.651, 80.620), front_top=(17.442, 83.527),
                          cervical=(-50.194, 85.078), post_top=(-100.0, 80.233), deep_top=(-72.674, 84.302),
                          deep_bot=(-72.674, 26.163), abd2_top=(-119.186, 81.783), abd2_pleuron=(-119.186, 37.791)),
              # X0b (9), round 2: c06 SOLVED (the resting crouch): the central camera's heights above the ground under
              # each landmark's own lateral offset; its band; and c10's raised standing posture (the bind's other
              # candidate: the lead's choice)
              c06=dict(orbit=(0.0, 62.61), eye_c=(4.651, 62.42), front_top=(17.442, 60.75), cervical=(-50.194, 65.03),
                       post_top=(-100.0, 62.15), deep_top=(-72.674, 65.15), deep_bot=(-72.674, 16.33),
                       abd2_top=(-119.186, 64.48), abd2_pleuron=(-119.186, 29.05)),
              c06_camera=dict(phi_w=19.0, ground_row=702.0, tilt_share=0.85, margin_offset=0.235),
              c06_band=dict(dorsum=(52.7, 74.7), margin=(5.8, 23.6)),
              c10=dict(dorsum=89.1, margin=38.3),
              c10_camera=dict(phi_w=26.75, roll=0.25, fan_tip_offset=0.08, margin_offset=0.235),
              c10_band=dict(dorsum=(81.2, 96.1), margin=(33.5, 44.1)),
              abd_flex_max=35.0, abd_ext_max=8.0),
    # ---- literature constants (lobster_work/data/literature.md)
    lit=dict(pope_m=(2.507, 25.9), pope_f=(2.678, 15.4), pope_n=186, weight_m=(3.551, -7.29),
             weight_f=(3.039, -6.10), sord_m=(0.29, -26.8), sord_f=(0.18, -4.3), sord_mpa=1.08,
             regen=(0.034, 0.038), missing_crusher=0.043, eu_min_CL=87.0, TL_max=600.0),
    # ---- colour: camera JPEG medians, white-balanced (palette facts, not albedo: plan §2.6, §9)
    colour=dict(dorsum_sun=(23, 21, 25), dorsum_indoor=(16, 16, 15), abdomen_sky=(56, 65, 86),
                fan_blade=((8, 11, 18), (24, 26, 30)), spots=(73, 43, 30), spots_dim=(20, 17, 13),
                edges=(215, 206, 202), cooked_carapace=(173, 53, 43), cooked_mottle=(180, 49, 26),
                cooked_claw=(170, 43, 24), cooked_tergite=(158, 29, 21), dorsum_albedo=(0.012, 0.020)),
    # ---- motion facts (plan §2.7)
    motion=dict(cutter_close_ms=20.0, crusher_ma=2.8, giant_ms=20.0, nongiant_ms=(60.0, 150.0)),
    # ---- X0b's raw readings (research/lobster_work/x0b/data/src_*.json through the sweep's lmeasure; the cameras from
    # x0b_cameras.py): each a ratio to its photo's unit; work/bestiary/tests/x00b_measure.py recomputes every one
    x0b=dict(
        c20=dict(cervical=0.504505, cara_depth=0.490991, deep_station=0.729730),
        c11=dict(cr_base=0.230589, cu_base=0.213211, saw_run=0.411044),
        n01=dict(P1_coxa=0.139585, P4_coxa=0.110959, P5_coxa=0.102459, P1_ahead=0.745902, P4_ahead=0.233607,
                 P5_ahead=0.065574, medial=0.065574, P1_basis_x=0.196721, P4_basis_x=0.176230, P5_basis_x=0.168033,
                 proxy_fan_CL=0.779553),
        n04=dict(legA_basis_tip=0.780388, legA_coxa_tip=0.839707, legA_coxa=0.059318, rostrum_ratio=0.227,
                 depth_factor=(1.08, 1.13)),
        depth=dict(c20=0.491, c10_own=(0.425, 0.550, 0.611), r57282_4=(0.405, 0.445, 0.485),
                   c06_solved=(0.446, 0.488, 0.520))),
    # ---- X1, the skeleton (families/decapod.py; work/bestiary/tests/x01_skeleton.py recomputes every -x1 row): the bind
    # RAISED in the walking stance with the joints near mid-range, c06's crouch the REST pose (the lead's call, 10-28).
    # Life mm unless the unit says otherwise; positions are the LEFT side's in the plan frame
    rig=dict(
        lift=21.970, body_z=-59.508, body_frac=0.5, coxa_drop=3.0, abd_hinge=0.40,
        pleopod=dict(x=10.0, drop=0.45, len1=15.0, len=15.0, tilt1=50.0, tilt=-89.0,
                     drop_25=(0.56331, 0.54531, 0.51531, 0.47331), at_25=0.75, x_25=11.0, splay_25=15.0),
        uropod=dict(base=(18.0, 3.0), endo=(20.0, -4.0), endo_tip_x=13.0, exo=(24.0, -2.0), exo_dist=(40.0, -9.0),
                    exo_tip_dz=-12.0),
        eyestalk=dict(base=(3.0, -1.0, -2.0), mid=0.5),
        antenna=dict(base=(9.0, -6.0, 1.0), ped=(12.0, 10.0, 8.0), yaw=50.0, pitch=0.0, n_flag=16),
        antennule=dict(base=(2.5, -4.0, 2.0), ped=(6.0, 5.0, 4.0), yaw=10.0, pitch=15.0, split=12.0, n_flag=4),
        mxp3=dict(base=(3.5, 4.0, -10.0), seg=(14.0, 10.0, 12.0), yaw=5.0, pitch=-10.0),
        cheliped=dict(coxa=13.959, seg=(13.021, 44.204, 40.103), wrist_z=33.589, cutter_dactyl=0.550973, claw_yaw=-20.0,
                      claw_pitch=10.0, claw_plane=0.0, tip_h=36.925, low_clear=31.41, low_point=(68.515, -15.934, 12.875),
                      wrist_x=(30.0, 65.0), dactyl_open=10.0,
                      hinge=(0.192767, 0.079545), cutter_hinge=(0.289511, 0.111246), cutter_axis=3.4333,
                      cutter_cap=1.70294, hinge_s=0.564377, cutter_hinge_s=0.438083),
        p23=(8.359, 35.165, 13.740, 28.287, 17.298),
        leg_az=dict(P2=(70.771, 31.433), P3=(80.984, 66.648), P4=(75.965, 68.481), P5=(99.834, 143.938)),
        tip_x=(0.40, 0.70), rest_tip_x=(0.513, 0.573), knee_sigma=15.0, az_pad=4.0, fan_contact_z=-181.589,
        rest_tip_z=dict(P2=-7.171, P3=-62.984, P4=-80.814, P5=-117.248), rest_pleopod_fold=0.0,
        rest_curl_back=35.0,
        ranges=dict(walking=dict(promotion=(-30.0, 30.0), levation=(-20.0, 70.0), ischium_merus=(-10.0, 10.0),
                                 knee=(30.0, 160.0), carpus_propodus=(-45.0, 45.0), dactyl=(0.0, 60.0)),
                    cheliped=dict(promotion=(-10.0, 70.0), levation=(-20.0, 60.0), knee=(30.0, 150.0),
                                  wrist=(-30.0, 52.5), crusher=(0.0, 40.0), cutter=(0.0, 55.0)),
                    abdomen=(-8.0, 35.0), uropod=(0.0, 40.0), eyestalk_yaw=(-30.0, 30.0),
                    eyestalk_pitch=(-20.0, 20.0), antenna_yaw=(-10.0, 90.0), antenna_pitch=(-30.0, 30.0),
                    flagellum=(-15.0, 15.0))),
    # ---- X1's readings: the walking legs' knees (merus-carpus joints) and dactyl tips in plan, (z, x) in CL in each
    # photo's body frame (z forward from the orbit, x the creature's left; a right-side point mirrored to +x), from
    # research/lobster_work/x1/data/src_c03_x1.json and src_c01_x1.json through the sweep's lmeasure (x01 recomputes)
    x1=dict(
        c03=dict(P2_R_knee=(-0.234273, 0.372896), P3_R_knee=(-0.549252, 0.503923), P3_R_tip=(-0.317771, 0.360386),
                 P4_R_knee=(-0.638927, 0.535135), P4_R_tip=(-0.531797, 0.645526), P5_R_knee=(-1.286871, 0.442169),
                 P5_R_tip=(-1.683539, 0.406464), P2_L_knee=(-0.360402, 0.618166), P3_L_knee=(-0.696361, 0.517930),
                 P3_L_tip=(-0.284079, 0.787191), P4_L_knee=(-0.947636, 0.575192), P4_L_tip=(-0.829478, 1.085791),
                 P5_L_knee=(-1.035908, 0.508462), P5_L_tip=(-1.452511, 0.448517)),
        c01=dict(P3_L_knee=(-0.482128, 0.599860), P3_L_tip=(-0.384092, 0.749657), P4_L_knee=(-0.611452, 0.507152),
                 P4_L_tip=(-0.378202, 0.400265), P5_L_knee=(-0.990215, 0.535930), P5_L_tip=(-1.365238, 0.374618),
                 P2_R_tip=(0.271299, 0.491056), P3_R_knee=(-0.459302, 0.602150), P4_R_knee=(-0.638891, 0.623060),
                 P4_R_tip=(-0.395108, 1.032035), P5_R_knee=(-0.969850, 0.657604),
                 P5_R_tip=(-1.209271, 0.637068))),
    # ---- X2's cheliped readings (research/lobster_work/x2/data/src_<id>_x2.json through the sweep's lmeasure; x02
    # recomputes each): each a ratio to its photo's unit (c11 CL; n04 a ratio to the carpus or the crusher propodus;
    # n01 a ratio to the carpus or M4's fan; c13 a ratio inside its chain)
    x2=dict(
        c11=dict(carpus=(0.389668, 0.412395), wrist_z=(0.298084, 0.373689), wrist_x=(0.675466, 0.677527),
                 elbow_z=(-0.047560, 0.010793), elbow_x=(0.495545, 0.481628),
                 cr_artic=(0.654518, 0.182736), cu_artic=(0.514208, 0.159290), cr_dactyl_tip=(1.182219, 0.190895),
                 cu_dactyl_tip=(1.042365, 0.116254)),
        n04=dict(merus_carpus=1.065153, bi_carpus=0.346239, carpus_propodus=0.369206, suture_frac=0.399608,
                 condyle=(0.201168, 0.156788), condyle_r=0.149776),
        n01=dict(merus_carpus=1.139344, bi_carpus=0.303152, carpus_fan=(0.382379, 0.379270),
                 mb_carpus=(1.403205, 1.477213)),
        c13=dict(merus_carpus=1.381201, carpus_propodus=0.317059, tip_palm=(0.125280, 0.169558),
                 tip_profile=(0.061790, 0.082564, 0.097218, 0.104733),
                 tip_stations=(0.011799, 0.023599, 0.035398, 0.047198, 0.066858))),
)

# The part ids (plan §4: one closed shell per sclerite) for the cage's part one-hot, the bake's region output and the
# recipe's mask regions; zones are the material roles of plan §9 (the packs' channels)
REGIONS = ('carapace', 'rostrum', 'ventral_thorax', 'eyestalk', 'cornea', 'antennule', 'antenna', 'flagellum',
           'maxilliped', 'cheliped', 'propodus', 'dactyl', 'walking_leg', 'tergite', 'sternite', 'pleopod', 'telson',
           'uropod', 'membrane', 'setae')
REGION_ID = {name: i for i, name in enumerate(REGIONS)}
ZONES = dict(primary='1 - masks.r', soft='masks.r', setae='masks.g', accent='masks.b', pattern='masks.a')

_C11 = 'M1 (c11, the Wiesbaden mount, dorsal; ratios; lmeasure on src_c11.json)'
_UB = ('UPPER BOUND: the sweep read the ground at the sand line against the glass (y 795), where only the nearest '
       'dactyl stands; the camera looks down on the receding sand, so the ground under the midline images higher '
       '(checker 10-27); X0b (9) solves the camera')
TAGS = {
    'family': ('[H]', 'plan §5.1: the recipe family stays arthropod (remix/recipe.py), with a body plan key'),
    'body_plan': ('[D]', 'plan §5.1 / question 3: the decapod body plan; the generator forge/families/decapod.py (X1)'),
    'author_scale': ('[D]', 'plan §5.8: built at x4 (life_scale 0.25): the walking legs land at the beetle\'s x10 leg '
                            'scale, where the forge\'s mm constants were proven'),
    'sex': ('[D]', 'plan §2: L1 is a male (claw dimorphism; M2\'s label and M4\'s stiff first pleopods)'),
    'handedness': ('[P c11, n03] [D]', 'the crusher on the LEFT in both animals whose side reads (M1, M2; the checker '
                                       're-read both); the default; the recipe rolls L / R 50:50 (set by juvenile use '
                                       '[L7, S])'),
    # photos (each a ratio to its photo's unit, as lmeasure prints it)
    'photos.M1.rostrum': ('[P c11]', _C11 + ': rostrum tip ahead of the orbit / CL'),
    'photos.M1.cervical': ('[P c11]', _C11 + ': the cervical groove\'s midline crossing behind the orbit / CL'),
    'photos.M1.cara_width': ('[P c11]', _C11 + ': carapace width at its widest / CL'),
    'photos.M1.eye_spacing': ('[P c11]', _C11 + ': the corneas\' centres apart / CL'),
    'photos.M1.cornea': ('[P c11]', _C11 + ': cornea diameter from above / CL'),
    'photos.M1.antscale': ('[P c11]', _C11 + ': the scaphocerites\' tips apart / CL'),
    'photos.M1.segs': ('[P c11]', _C11 + ': T1..T6 and the telson along the midline (the yellow hinge lines; T1 from '
                                         'the carapace margin) / CL'),
    'photos.M1.abdomen': ('[P c11]', _C11 + ': carapace margin to telson tip / CL (a mount telescopes: lower bound)'),
    'photos.M1.TL': ('[P c11]', _C11 + ': rostrum tip to telson tip / CL (a lower bound)'),
    'photos.M1.abd2_w': ('[P c11]', _C11 + ': somite 2 width / CL'),
    'photos.M1.abd5_w': ('[P c11]', _C11 + ': somite 5 width / CL'),
    'photos.M1.fan': ('[P c11]', _C11 + ': tail fan spread / CL'),
    'photos.M1.cr_len': ('[P c11]', _C11 + ': crusher propodus, carpal joint to the fixed finger\'s tip / CL'),
    'photos.M1.cr_palm': ('[P c11]', _C11 + ': crusher palm width across the axis, in the fingers\' plane / CL'),
    'photos.M1.cr_free': ('[P c11]', _C11 + ': the crusher\'s free finger, gape to tip / CL'),
    'photos.M1.cu_len': ('[P c11]', _C11 + ': cutter propodus / CL, a LOWER BOUND: cu_tip lies on the crusher\'s '
                                           'dactyl, which hides the cutter\'s tips (the X2 check, 10-28); the whole '
                                           'cutter is chela.cutter_len (X2b)'),
    'photos.M1.cu_palm': ('[P c11]', _C11 + ': cutter palm width / CL'),
    'photos.M2.rostrum': ('[P n03]', 'M2 (n03, NHMUK 2026.19, dried giant, dorsal): rostrum / CL'),
    'photos.M2.cara_width': ('[P n03]', 'M2: carapace width / CL (dried, flattened giant)'),
    'photos.M2.cr_len': ('[P n03]', 'M2: crusher propodus / CL'),
    'photos.M2.cr_palm': ('[P n03]', 'M2: crusher palm width / CL'),
    'photos.M2.cu_len': ('[P n03]', 'M2: cutter propodus / CL'),
    'photos.M2.cu_palm': ('[P n03]', 'M2: cutter palm width / CL'),
    'photos.M2.CL_bar': ('[P n03]', 'M2: CL in mm at the bar\'s plane (10.23 px/mm; the dorsum 8-10 cm nearer: '
                                    '136-141 mm corrected [E])'),
    'photos.P1.cara_width': ('[P c03]', 'P1 (c03, live, dorsal, 960 px; the orbit placed by M1\'s rostrum ratio, '
                                        '+-3 % on every /CL): carapace width / CL'),
    'photos.P1.abd2_w': ('[P c03]', 'P1: somite 2 width / CL'),
    'photos.P1.fan': ('[P c03]', 'P1: tail fan spread / CL'),
    'photos.P1.abdomen': ('[P c03]', 'P1: carapace margin to telson tip / CL: a top view of a tail sloping from the '
                                     'raised carapace to the floor (checker): a lower bound'),
    'photos.P1.TL': ('[P c03]', 'P1: rostrum tip to telson tip / CL (a rest pose\'s projection)'),
    'photos.P1.antenna_chord': ('[P c03]', 'P1: the intact antenna\'s chord / CL (a lower bound)'),
    'photos.P1.claw_U': ('[P c03]', 'P1: the upper claw\'s propodus / CL (which claw is which not certain at 960 px)'),
    'photos.P1.claw_L': ('[P c03]', 'P1: the lower claw\'s propodus / CL'),
    'photos.P2.cervical': ('[P c06]', 'P2 (c06, live, left lateral through aquarium glass): the cervical groove / CL'),
    'photos.P2.cara_depth': ('[P c06]', 'P2: carapace depth, top to the lower margin, at the deepest station / CL '
                                        '(a downward view inflates it by about the margin\'s half-width x tan of the '
                                        'tilt: X0b (9))'),
    'photos.P2.abd2_depth': ('[P c06]', 'P2: somite 2 depth, tergite top to the pleuron\'s tip / CL'),
    'photos.P2.dorsum_ub': ('[P c06]', 'P2: the dorsum above the sand line at the glass / CL: ' + _UB),
    'photos.P2.margin_ub': ('[P c06]', 'P2: the carapace\'s lower margin above the sand line at the glass / CL: '
                                       + _UB),
    'photos.P2.cornea': ('[P c06]', 'P2: cornea diameter from the side / CL'),
    'photos.M3.prop_bar': ('[P n04]', 'M3 (n04, NHMUK 1906.5.31.1, disarticulated giant): the crusher propodus in mm '
                                      'at the bar (12.21 px/mm; x 0.88-0.93 corrected [E])'),
    'photos.M3.dactyl': ('[P n04]', 'M3: the crusher dactyl, articulation to tip / the propodus'),
    'photos.M3.palm': ('[P n04]', 'M3: the crusher palm width / the propodus'),
    'photos.M3.molar_dac': ('[P n04]', 'M3: the dactyl\'s large molar, its width / the propodus'),
    'photos.M3.molar_fix': ('[P n04]', 'M3: the fixed finger\'s large molar, its width / the propodus'),
    'photos.M3.saw': ('[P n04]', 'M3: the cutter\'s saw run / the CRUSHER propodus (the same giant)'),
    'photos.M4.P4': ('[P n01]', 'M4 (n01, NHMUK 2026.17, dried, ventral; the animal\'s left legs): P4 merus, carpus, '
                                'propodus, dactyl, basis-to-tip / the fan spread (the polylines start at the coxa\'s '
                                'distal end: checker)'),
    'photos.M4.P5': ('[P n01]', 'M4: P5 merus, carpus, propodus, dactyl, basis-to-tip / the fan spread'),
    'photos.M4.fan_bar': ('[P n01]', 'M4: the fan spread in mm at the bar (17.75 px/mm; legs 3-6 cm nearer: x '
                                     '0.89-0.94 [E])'),
    # body
    'body.CL': ('[D]', 'plan §2.1: L1\'s carapace length, orbit to the posterior margin (Pope\'s definition [L1]); '
                       'the Norwegian samples\' CL 85-100 [L6 with L1]; the EU minimum 87'),
    'body.rostrum': ('[D-x0 from P c11, n03]', 'the mean of M1 0.2270 and M2 0.2252 x CL (the plan 22.6)'),
    'body.cervical': ('[D-x0 from P c11, c06]', 'the cervical groove\'s midline crossing BEHIND the orbit: the mean of '
                                                'M1 0.5046 (dorsal) and P2 0.5018 (lateral) x CL (the plan 50.3)'),
    'body.cara_width': ('[P c11]', 'M1 x CL; M2 0.606 (dried, flat), P1 0.454 (live, low-res); X0b (2) re-reads c01'),
    'body.cara_depth': ('[D-x0b from P c06, c20, c10, r57282_4]', 'the TRUE depth (X0b (9), round 2): P2\'s apparent '
                                                                  '0.581 (photos.P2.cara_depth) through c06\'s solved '
                                                                  'camera (rest.c06 deep_top - deep_bot; band 0.446-0.520), '
                                                                  'the band set by c20\'s drawing (no camera) 0.491 +-0.03 '
                                                                  'and r57282_4\'s box camera 0.445; c06 alone (no depth '
                                                                  'band) allows 0.44-0.56, median 0.50; c10\'s own camera '
                                                                  'reads deeper, 0.550 (0.425-0.611), once its landmarks '
                                                                  'were re-read (review 10-28; 0.485 with post_top on T2): '
                                                                  'consistent, not confirming (x0b.depth). Known to about '
                                                                  '+-0.05 CL; a scaled lateral view would tighten it'),
    'body.deepest_z': ('[D-lp from P c06]', 'the deepest station\'s z: c06 x 1150 against the orbit x 775, CL 516 px'),
    'body.cornea': ('[P c11, c06]', 'cornea diameter from above (M1) and from the side (P2) x CL; the eye grows '
                                    'isometrically [L13, S]'),
    'body.cornea_spacing': ('[P c11]', 'M1 x CL'),
    'body.eye_z': ('[D-lp from P c06]', 'the cornea\'s centre ahead of the orbit: c06 x 751 against x 775'),
    'body.antscale_tips': ('[P c11]', 'M1 x CL'),
    'body.rostral_teeth': ('[P c11]', 'about 3 pale tubercles a side, by eye at 4x, one animal; X4 counts on c11'),
    # length (question 1b, option (a))
    'length.TL_bind': ('[L1] [D]', 'THE BIND: rostrum + CL + abdomen, straight, = Pope\'s male stretched TL (the '
                                   'lead\'s option (a), 10-27)'),
    'length.TL_stretched': ('[L1]', 'Pope 1955: male TL = 2.507 CL + 25.9 mm, "abdomen fully extended", n 186'),
    'length.TL_stretched_f': ('[L1]', 'Pope 1955: female TL = 2.678 CL + 15.4 mm at L1\'s CL'),
    'length.abdomen': ('[D-x0 from L1, P c11, n03]', 'carapace margin to telson tip at the bind: Pope\'s TL - CL - '
                                                     'rostrum (1.540 CL)'),
    'length.abdomen_M1': ('[P c11]', 'M1\'s abdomen x CL: a mount\'s telescoped projection (a lower bound)'),
    'length.abdomen_P1': ('[P c03]', 'P1\'s abdomen x CL: a top view of a sloping tail (a lower bound; the plan\'s old '
                                     'bind, option (b), not taken)'),
    'length.TL_M1': ('[P c11]', 'M1\'s TL x CL: the rest-pose check\'s lower photo value'),
    'length.TL_P1': ('[P c03]', 'P1\'s TL x CL: the rest-pose check\'s upper photo value'),
    'length.mass': ('[L2]', 'Pope 1955: log10 W(oz) = 3.551 log10 TL - 7.29 at the male TL (kg)'),
    'length.mass_f': ('[L2]', 'Pope 1955: log10 W(oz) = 3.039 log10 TL - 6.10 at the female TL (kg)'),
    # abdomen
    'abdomen.segs': ('[D-x0 from P c11, L1]', 'T1..T6, telson: M1\'s midline fractions of its abdomen (0.125 / 0.164 '
                                              '/ 0.147 / 0.151 / 0.148 / 0.129 / 0.136) x the bind\'s abdomen; T2 the '
                                              'longest; T1 slides under the carapace margin'),
    'abdomen.w2': ('[P c11]', 'somite 2 width, M1 x CL (P1 0.521)'),
    'abdomen.w5': ('[P c11]', 'somite 5 width, M1 x CL: the abdomen barely tapers until T6'),
    'abdomen.d2': ('[D-x0b from P c06]', 'somite 2\'s TRUE depth, tergite top to the pleuron tip: P2\'s apparent 0.440 '
                                         '(photos.P2.abd2_depth) through c06\'s solved camera (rest.c06 abd2_top - '
                                         'abd2_pleuron; the pleuron tip 0.18-0.24 CL toward the camera)'),
    'abdomen.fan_spread': ('[D]', 'the mean of M1 1.046 and P1 0.971 (1.008), rounded to 1.00 CL (plan §2.2)'),
    'abdomen.overlap': ('[E]', 'each tergite\'s anterior flange under the one before: 15-25 % of the segment by eye on '
                               'c11\'s hinge lines; X0b measures it; gate X10\'s tail flip'),
    'abdomen.pleopod_pairs': ('[P n01]', 'pleopods on somites 1-5; pair 1 the male\'s stiff rods'),
    'abdomen.uropod_reach': ('[E]', 'the uropods reach about the telson\'s tip (c11 by eye), as a fraction of the '
                                    'telson'),
    # chela
    'chela.crusher_len': ('[P c11]', 'M1 x CL: carpal joint to the fixed finger\'s tip; M2 1.269, P1 1.058'),
    'chela.crusher_palm': ('[P c11]', 'M1 x CL: across the axis in the fingers\' plane; M2 0.524; [L6] male 0.534 at '
                                      'CL 100 (MPA males up to 8 % more): one animal\'s claw'),
    'chela.cutter_len': ('[D-x2 from P c11, c13]', 'the cutter propodus, carpal joint to the fixed finger\'s tip, M1\'s '
                                                   'WHOLE cutter (X2b, 10-29): c11\'s crusher dactyl lies across both '
                                                   'cutter fingers, so M1\'s traced length (photos.M1.cu_len, 107.7) stops '
                                                   'on its edge, a lower bound (the X2 check). The fixed finger continued '
                                                   'under it (decapod_parts.cutter_fixed_tip: the circle fitted to its '
                                                   'lateral edge\'s last 23 mm, X0b\'s saw line, a round cap; X2c: the '
                                                   'cap rig.cheliped.cutter_cap, fitted to c13\'s tip profile, was X2b\'s '
                                                   'fillet of half c13\'s L/40 width) ends 115.0 mm from the wrist (X2b '
                                                   '114.7), still under the crusher\'s dactyl (its far edge, M1\'s open '
                                                   'crusher gape where no cutter shows, at s 118.5-122). c13\'s length ratios do '
                                                   'not carry to M1 (its knob at 0.52 of its propodus, M1\'s at <= 0.48); '
                                                   'n04\'s cutter is not whole (its carpal end broken, its tips under the '
                                                   'crusher chain). M2 0.980, P1 1.058'),
    'chela.cutter_palm': ('[P c11]', 'M1 x CL; M2 0.385'),
    'chela.crusher_free': ('[P c11]', 'M1 x CL: the free finger, gape to tip'),
    'chela.crusher_dactyl': ('[D-x0 from P n04, c11]', 'M3\'s dactyl / propodus x L1\'s crusher propodus'),
    'chela.molar_fixed': ('[D-x0 from P n04, c11]', 'M3\'s fixed-finger molar / propodus x L1\'s crusher propodus: one '
                                                    'large rounded molar per finger, a second lump by the dactyl\'s '
                                                    'articulation, small blunt teeth toward the tips'),
    'chela.molar_dactyl': ('[D-x0 from P n04, c11]', 'M3\'s dactyl molar / propodus x L1\'s crusher propodus'),
    'chela.saw_run': ('[D-x0b from P c11]', 'M1\'s OWN cutter saw (L1\'s claws are M1\'s; X0b (5)): the row of '
                                            'denticles along the fixed finger, x0b.c11.saw_run x CL, from its first nub '
                                            '(0.96 of the claw\'s length, just clear of the crusher\'s dactyl that crosses '
                                            'the cutter\'s tips) to its last (review 10-28: the first reading started on '
                                            'that dactyl, past the cutter\'s tip: 49.1 mm)'),
    'chela.saw_run_M3': ('[D-x0 from P n04, c11]', 'the plan\'s first value: M3\'s cutter saw run / its CRUSHER propodus '
                                                   'x L1\'s crusher propodus (superseded by M1\'s own saw_run)'),
    'chela.saw_denticles': ('[P c11, n04]', 'about 22 (20-24) resolved on M1 at x10 at about 1.9 mm pitch (review '
                                            '10-28; c11: finer ones may be below 6.5 px per mm); 25-30 by eye on M3 '
                                            '(n04)'),
    'chela.crusher_base': ('[D-x0b from P c11]', 'the crusher PROPODUS BASE just distal of the carpal articulation, '
                                                 'across its axis (x0b.c11.cr_base x CL): it sizes the wrist ring (plan '
                                                 '§6.1, question 7b)'),
    'chela.cutter_base': ('[D-x0b from P c11]', 'the cutter propodus base, as the crusher\'s: crusher / cutter 1.08, so '
                                                'the two wrist rings are near but not equal (+-20 px on each)'),
    'chela.granule': ('[P n04]', 'palm granules across (mm), M3 at 2.5x (a giant: L1\'s may be finer [E]); [L5] '
                                 '"only slightly granular"'),
    'chela.granule_spacing': ('[P n04]', 'palm granules\' spacing (mm), M3'),
    'chela.setal_pit': ('[P n04]', 'sparse setal pits across (mm), M3'),
    'chela.tubercles': ('[P c11, c04] [L14]', '5-7 large white-tipped tubercles per row along the claws\' inner '
                                              'margins and over the carpus and merus: seen, not counted on a second '
                                              'animal'),
    'chela.crusher_thick': ('[E]', 'thickness perpendicular to the fingers\' plane, 0.30 CL: NOT measured; X0b (3), (4) '
                                   '(c08 frontal, r57282_6-8 as ratios)'),
    'chela.cutter_thick': ('[E]', '0.20 CL: NOT measured; X0b (3), (4)'),
    'chela.dactyl_open': ('[E]', 'the dactyl\'s open limit (deg), crusher and cutter: plan §10.3; X0b (3) reads c08\'s '
                                 'open claws'),
    # legs
    'legs.P4.basis_tip': ('[D-lp from P n01]', 'BASIS TO TIP, the coxa NOT included (n01\'s polylines start at the '
                                               'coxa\'s distal end: checker): M4\'s P4 / its fan x L1\'s fan 1.00 CL'),
    'legs.P4.basis_ischium': ('[D-lp from P n01]', 'the basi-ischium only: basis-to-tip minus the four distal segments'),
    'legs.P4.merus': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL; joints at the membranes\' dark rings, +-1.5 mm on L1'),
    'legs.P4.carpus': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL (the merus / carpus boundary the least sure)'),
    'legs.P4.propodus': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL'),
    'legs.P4.dactyl': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL: a simple point with setal tufts'),
    'legs.P5.basis_tip': ('[D-lp from P n01]', 'BASIS TO TIP, the coxa NOT included: M4\'s P5 / its fan x 1.00 CL'),
    'legs.P5.basis_ischium': ('[D-lp from P n01]', 'the basi-ischium only'),
    'legs.P5.merus': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL'),
    'legs.P5.carpus': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL'),
    'legs.P5.propodus': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL'),
    'legs.P5.dactyl': ('[D-lp from P n01]', 'M4 / fan x 1.00 CL'),
    'legs.P2.basis_tip': ('[E]', 'chelate; NOT measured (overlaps P3 on M4): P4\'s +-10 %, basis to tip; X0b reads c11\'s '
                                 'projections (lower bounds)'),
    'legs.P3.basis_tip': ('[E]', 'chelate; NOT measured: P4\'s +-10 %, basis to tip; X0b'),
    'legs.coxa': ('[E]', 'the P2 / P3 coxa (not readable on n01: the tape and overlap): the mean of P4\'s and P5\'s '
                         'measured coxae; M3\'s leg A coxa reads 7.9-8.3 mm (x0b.n04), so +-25 %'),
    'legs.P4.coxa': ('[D-x0b from P n01]', 'M4\'s P4 coxa / its fan x 1.00 CL (X0b (6)): sternal crease to the coxa-basis '
                                           'joint, in the ventral view'),
    'legs.P5.coxa': ('[D-x0b from P n01]', 'M4\'s P5 coxa / its fan x 1.00 CL (X0b (6))'),
    'legs.coxae.P1': ('[D-x0b from P n01] [E]', 'the cheliped\'s coxa: z = -CL + its medial articulation\'s distance '
                                                'ahead of the thorax-abdomen junction (taken as the carapace\'s posterior '
                                                'margin, +-30 px = +-0.025 CL), x of its coxa-basis joint, both / M4\'s fan x '
                                                '1.00 CL; the medial x [E] as P4 / P5\'s'),
    'legs.coxae.P2': ('[E]', 'P2\'s coxa: one third of the way from P1\'s to P4\'s (not readable on n01: the tape)'),
    'legs.coxae.P3': ('[E]', 'P3\'s coxa: two thirds of the way from P1\'s to P4\'s'),
    'legs.coxae.P4': ('[D-x0b from P n01]', 'P4\'s coxa (x medial, z, x coxa-basis) as P1\'s, all three read'),
    'legs.coxae.P5': ('[D-x0b from P n01]', 'P5\'s coxa (x medial, z, x coxa-basis) as P1\'s, all three read'),
    'legs.merus_width': ('[E]', 'the walking legs\' segment width, 0.06 CL: c11\'s distal segments read 0.054-0.069 CL by '
                                'eye (x0b/data/src_c11_x0b.json notes), not traced'),
    # antenna
    'antenna.total': ('[D]', 'at least P1\'s 1.70 CL chord (a lower bound), 0.70 of P1\'s rest TL (the sweep\'s [E] '
                             '0.65-0.70 TL is P1\'s own ratio, 0.66)'),
    'antenna.peduncle': ('[E]', 'the thick segmented peduncle, about 0.30 CL (c11, c04 seen)'),
    'antenna.flagellum': ('[E]', 'the red-maroon whip: total - peduncle'),
    'antenna.antennule': ('[E]', 'two thin flagella a side on a three-article peduncle, about 0.3 CL (c11 at 4x); not '
                                 'measured'),
    # rest (c06's upper bounds)
    'rest.c06_ub.orbit': ('[D-lp from P c06]', 'the orbit: ' + _UB),
    'rest.c06_ub.eye_c': ('[D-lp from P c06]', 'the cornea\'s centre: ' + _UB),
    'rest.c06_ub.front_top': ('[D-lp from P c06]', 'the carapace\'s front top: ' + _UB),
    'rest.c06_ub.cervical': ('[D-lp from P c06]', 'the cervical groove on the dorsal outline: ' + _UB),
    'rest.c06_ub.post_top': ('[D-lp from P c06]', 'the carapace\'s posterior margin, top: ' + _UB),
    'rest.c06_ub.deep_top': ('[D-lp from P c06]', 'the dorsum at the deepest station (h_dorsum): ' + _UB),
    'rest.c06_ub.deep_bot': ('[D-lp from P c06]', 'the carapace\'s lower margin at the deepest station (h_margin): '
                                                  + _UB),
    'rest.c06_ub.abd2_top': ('[D-lp from P c06]', 'somite 2\'s tergite top: ' + _UB),
    'rest.c06_ub.abd2_pleuron': ('[D-lp from P c06]', 'somite 2\'s pleuron tip: ' + _UB),
    **{f'rest.c06.{nm}': ('[D-x0b from P c06]', f'{nm}: (z, h) at c06\'s SOLVED central camera (rest.c06_camera; X0b '
                                                f'(9) round 2): h above the ground under the landmark\'s own lateral '
                                                f'offset; no longer an upper bound')
       for nm in ('orbit', 'eye_c', 'front_top', 'cervical', 'post_top', 'deep_top', 'deep_bot', 'abd2_top',
                  'abd2_pleuron')},
    'rest.c06_camera.phi_w': ('[D-x0b from P c06]', 'the central camera\'s in-water depression (deg): the median of the '
                                                    'feasible set (12-24) in x0b_cameras.py; in air about 25.7'),
    'rest.c06_camera.ground_row': ('[D-x0b from P c06]', 'the ground\'s image row under the midline at x 1146 (px; the '
                                                         'sweep read 795 at the glass): the feasible set\'s median'),
    'rest.c06_camera.tilt_share': ('[D-x0b from P c06]', 'the share of the frame line\'s 3.6 deg tilt the sand under the '
                                                         'animal shares (0.75-1.0: roll 1.0, a yawed camera about 0.87)'),
    'rest.c06_camera.margin_offset': ('[E]', 'the carapace\'s lower margin\'s lateral offset toward the camera (CL), '
                                             '0.20-0.27 in the solve'),
    'rest.c06_band.dorsum': ('[D-x0b from P c06]', 'the dorsum at the deepest station over EVERY feasible camera '
                                                   '(min, max): the fan 0.15-0.50 and the glass 0.40-1.05 CL out dominate '
                                                   'it; round 1\'s two readings (the pale rings on the sand, the glass >= '
                                                   '0.55) give 0.615 / 0.130'),
    'rest.c06_band.margin': ('[D-x0b from P c06]', 'the carapace\'s lower margin over every feasible camera'),
    'rest.c10.dorsum': ('[D-x0b from P c10]', 'the RAISED standing posture (c10, the Karlsruhe animal): the dorsum at '
                                              'the deepest station at its central camera, the folded fan\'s tip on the '
                                              'midline the ground point, inside the depth band. Its carapace landmarks '
                                              'were re-read by the review (10-28: post_top had sat on T2 and the orbit '
                                              'on the cornea, so CL read 631 px for 551; x0b_cameras.json review_note): '
                                              'the in-band cameras now look down 23.5-32 deg in water (32-45 in air), '
                                              'steeper than c06\'s 12-24'),
    'rest.c10.margin': ('[D-x0b from P c10]', 'c10\'s carapace margin above the ground under it'),
    'rest.c10_camera.phi_w': ('[D-x0b from P c10]', 'c10\'s central camera, in-water depression (deg)'),
    'rest.c10_camera.roll': ('[D-x0b from P c10]', 'c10\'s central camera roll (deg), +-1.5 searched'),
    'rest.c10_camera.fan_tip_offset': ('[D-x0b from P c10]', 'the folded fan\'s tip\'s lateral offset (CL), 0-0.08 '
                                                             'searched; the central camera sits at the edge, 0.08'),
    'rest.c10_camera.margin_offset': ('[E]', 'the margin\'s lateral offset (CL), as c06\'s'),
    'rest.c10_band.dorsum': ('[D-x0b from P c10]', 'c10\'s dorsum over every camera inside the depth band (min, max)'),
    'rest.c10_band.margin': ('[D-x0b from P c10]', 'c10\'s margin over every camera inside the depth band'),
    # X0b raw readings
    'x0b.c20.cervical': ('[P c20]', 'Calman 1911\'s side DRAWING (no camera): the cervical groove behind the orbit / CL'),
    'x0b.c20.cara_depth': ('[P c20]', 'c20: carapace depth at the deepest station / CL (a drawing: no perspective; its '
                                      'rostrum and eye are drawn 1.6-1.9x, so only the main outline is used)'),
    'x0b.c20.deep_station': ('[P c20]', 'c20: the deepest station behind the orbit / CL'),
    'x0b.c11.cr_base': ('[P c11]', 'M1: the crusher propodus base across its axis / CL (+-20 px)'),
    'x0b.c11.cu_base': ('[P c11]', 'M1: the cutter propodus base across its axis / CL (+-20 px)'),
    'x0b.c11.saw_run': ('[P c11]', 'M1: the cutter\'s saw, the denticle row along the fixed finger, first nub to last '
                                   '/ CL (saw_a re-read by the review, 10-28: src_c11_x0b.json review_note)'),
    'x0b.n01.P1_coxa': ('[P n01]', 'M4: the cheliped\'s coxa, sternal crease to the coxa-basis joint / fan (+-20 px)'),
    'x0b.n01.P4_coxa': ('[P n01]', 'M4: P4\'s coxa / fan (+-10 px)'),
    'x0b.n01.P5_coxa': ('[P n01]', 'M4: P5\'s coxa / fan (+-10 px)'),
    'x0b.n01.P1_ahead': ('[P n01]', 'M4: the cheliped coxa\'s medial articulation ahead of the thorax-abdomen junction, '
                                    'along the midline / fan'),
    'x0b.n01.P4_ahead': ('[P n01]', 'M4: P4\'s, likewise / fan'),
    'x0b.n01.P5_ahead': ('[P n01]', 'M4: P5\'s, likewise / fan'),
    'x0b.n01.medial': ('[P n01]', 'M4: P4 / P5\'s medial articulations off the midline / fan'),
    'x0b.n01.P1_basis_x': ('[P n01]', 'M4: the cheliped\'s coxa-basis joint off the midline / fan'),
    'x0b.n01.P4_basis_x': ('[P n01]', 'M4: P4\'s coxa-basis joint off the midline / fan'),
    'x0b.n01.P5_basis_x': ('[P n01]', 'M4: P5\'s coxa-basis joint off the midline / fan'),
    'x0b.n01.proxy_fan_CL': ('[P n01] [E]', 'M4\'s fan / a PROXY CL (the antennal bases to the junction): 0.78, with '
                                            'the abdomen-width proxy 0.77-0.91: M4\'s own CL is NOT measurable in a '
                                            'ventral view (the orbits hidden); information only, not used'),
    'x0b.n04.legA_basis_tip': ('[P n04]', 'M3 (the giant): leg A, a complete simple-dactyl walking leg, basis to tip / '
                                          'the rostrum-tip-to-posterior-margin length'),
    'x0b.n04.legA_coxa_tip': ('[P n04]', 'M3: leg A, coxa to tip / the same length'),
    'x0b.n04.legA_coxa': ('[P n04]', 'M3: leg A\'s coxa / the same length'),
    'x0b.n04.rostrum_ratio': ('[P c11]', 'M1\'s rostrum / CL (0.227) that places M3\'s orbit (its eyes are gone), as '
                                         'the sweep placed c03\'s'),
    'x0b.n04.depth_factor': ('[E]', 'the carapace\'s dorsal midline (about 7 cm above the foam) images 1.08-1.13x larger '
                                    'relative to the legs (about 1 cm): the camera 589 mm from the bar (the sweep\'s EXIF '
                                    'estimate)'),
    'x0b.depth.c20': ('[P c20]', 'the true carapace depth / CL from the drawing (x0b.c20.cara_depth, 3 decimals)'),
    'x0b.depth.c10_own': ('[D-x0b from P c10, c08]', 'c10\'s own camera (the folded fan\'s tip on the midline, the near '
                                                     'tips at c08\'s stance), NO depth constraint: (min, median, max), with '
                                                     'its carapace landmarks re-read by the review (10-28; 0.386 / 0.485 / '
                                                     '0.537 with post_top on T2)'),
    'x0b.depth.r57282_4': ('[D-x0b from P r57282_4]', 'r57282_4\'s box-solved camera (in air, 38.6 deg down): (min, '
                                                      'median, max)'),
    'x0b.depth.c06_solved': ('[D-x0b from P c06]', 'c06\'s feasible set (constrained by c20 +-0.03 to r57282_4\'s '
                                                   'median): (min, central, max)'),
    'rest.abd_flex_max': ('[E]', 'each abdominal joint\'s flexion limit (deg): 6 x 35 = 210, so the flip folds the fan '
                                 'under the body [L11]; plan §10.3, gate a tail-flip source'),
    'rest.abd_ext_max': ('[E]', 'each abdominal joint\'s extension past straight (deg): plan §10.3'),
    # literature
    'lit.pope_m': ('[L1]', 'male TL = a CL + b (mm), abdomen stretched'),
    'lit.pope_f': ('[L1]', 'female TL = a CL + b (mm)'),
    'lit.pope_n': ('[L1]', 'Pope\'s sample size'),
    'lit.weight_m': ('[L2]', 'male log10 W(oz) = a log10 TL(mm) + b'),
    'lit.weight_f': ('[L2]', 'female log10 W(oz) = a log10 TL(mm) + b'),
    'lit.sord_m': ('[L6]', 'Sørdalen et al. 2020: male crusher width CW = a TL + b (mm), fished areas'),
    'lit.sord_f': ('[L6]', 'Sørdalen et al. 2020: female CW = a TL + b (mm)'),
    'lit.sord_mpa': ('[L6]', 'MPA males\' crushers up to 8 % larger'),
    'lit.regen': ('[L6]', 'the fraction of males carrying a regenerated crusher'),
    'lit.missing_crusher': ('[L6]', 'the fraction of males missing a crusher'),
    'lit.eu_min_CL': ('[L3, L5]', 'the EU minimum landing size (CL, mm), the fisheries\' landmarks'),
    'lit.TL_max': ('[L3]', 'adults up to TL about 60 cm (Holthuis 1991)'),
    # colour
    'colour.dorsum_sun': ('[P c04]', 'carapace dorsal, sunlit: L* 7.1, hue 272, S 0.16'),
    'colour.dorsum_indoor': ('[P c01]', 'carapace dorsal, indoor: near-neutral black, L* 4.7'),
    'colour.abdomen_sky': ('[P c04]', 'abdomen tergite, sky-lit: hue 222, S 0.34'),
    'colour.fan_blade': ('[P c03, c01]', 'tail-fan blades: hue 221-222, S 0.19-0.55'),
    'colour.spots': ('[P c04]', 'spots on the pleura and carapace side: hue 18, S 0.59'),
    'colour.spots_dim': ('[P c03]', 'a dimmer spot read: hue 33, S 0.36'),
    'colour.edges': ('[P c04]', 'claw cutting edges and tubercle tips: cream'),
    'colour.cooked_carapace': ('[P c02] [L12]', 'cooked (a palette fact): heat frees astaxanthin from crustacyanin'),
    'colour.cooked_mottle': ('[P c02]', 'cooked mottle: the live marbling, lighter'),
    'colour.cooked_claw': ('[P c02]', 'cooked claw palm'),
    'colour.cooked_tergite': ('[P c02]', 'cooked abdominal tergite'),
    'colour.dorsum_albedo': ('[E]', 'the dorsum\'s linear albedo L: above the house floor 0.010 (REF R2); the camera\'s '
                                    'L* 1-7 is exposure; gate look-dev beside c01 / c04 (plan §9)'),
    # motion
    'motion.cutter_close_ms': ('[L10, S]', 'the cutter closes in under 20 ms (H. americanus)'),
    'motion.crusher_ma': ('[L8, S]', 'the crusher\'s mechanical advantage over the cutter\'s (all slow muscle)'),
    'motion.giant_ms': ('[L11]', 'giant-fibre tail flips start within about 20 ms of a stimulus (crayfish work as '
                                 'summarised by Jackson & Macmillan 2000): a LATENCY'),
    'motion.nongiant_ms': ('[L11]', 'non-giant flips start after at least about 60 ms, usually about 150 ms: LATENCIES '
                                    'from the stimulus, not intervals between flips (checker, read in the PDF)'),
    # X1, the skeleton (families/decapod.py; x01_skeleton.py recomputes the -x1 rows)
    'rig.lift': ('[D-x1 from P c10, c06]', 'the bind\'s lift over c06\'s solved crouch: rest.c10.margin - rest.c06 '
                                           'deep_bot (the lead\'s call, 10-28: RAISED, the carapace\'s lower margin at '
                                           'c10\'s 38.3 mm and its dorsum at that + L1\'s own depth body.cara_depth, 87.1 '
                                           'mm; c06\'s level profile kept)'),
    'rig.body_z': ('[D-x1 from P n01]', 'the body joint\'s z: the mean of the five coxae\'s z (legs.coxae)'),
    'rig.body_frac': ('[D]', 'the body joint this fraction of the way up from the carapace\'s lower margin to its dorsum '
                             'at the deepest station: the cephalothorax\'s middle, the root on the ground under it'),
    'rig.coxa_drop': ('[E]', 'the coxae (both ends: the coxa level) this far below the carapace\'s lower margin: c20 '
                             '(Calman\'s side drawing) shows the walking legs\' bases 0.02-0.11 CL under the margin line '
                             '(by eye on the X0b check); gate X2\'s clay (the coxae inside the ventral thorax)'),
    'rig.abd_hinge': ('[E]', 'the abdominal hinge line this fraction of abdomen.d2 below somite 2\'s top: about the '
                             'tergo-pleural articulations [C]; gate X10\'s tail flip (the flanges cover the membranes)'),
    'rig.pleopod.x': ('[E]', 'the pleopods\' bases off the midline (the sternites\' edges): not measured (plan §2.2)'),
    'rig.pleopod.drop': ('[E]', 'the pleopods\' bases this fraction of abdomen.d2 below the hinge line (the sternites)'),
    'rig.pleopod.len1': ('[E]', 'pleopod 1, the male\'s stiff gonopod: seen on n01, not measured'),
    'rig.pleopod.len': ('[E]', 'pleopods 2-5: not resolved on n01. X2b (10-29): 15 mm, was 20: folded forward under '
                               'the tongue pleura (rig.pleopod.tilt) a 20 mm pleopod from mid-somite reaches the somite '
                               'in front, where it either runs into that deeper sternite (T2\'s) or shows under that '
                               'pleuron\'s rounded front; 15 mm from at_25 ends 2 mm behind its own somite\'s front'),
    'rig.pleopod.drop_25': ('[D-x2 from E]', 'pleopods 2-5\'s bases this fraction of abdomen.d2 below the hinge line, one '
                                             'per somite (X2b: one value, 0.385, at the sternites\' underside). X2c: '
                                             'folded in the slot beside the sternite (decapod_parts PLEO_FOLD), each '
                                             'pleopod\'s base lowest PLEO_FOLD lift (0.3 mm) over its pleura\'s depth at '
                                             'their back, the tongue line: (D_k - lift - its base\'s vertical half-size - '
                                             'rig.abd_hinge D_k) / d2, D_k = ABD depth_k x d2 [E]; so they show in the '
                                             'notches between the tongues (the lead\'s call) and never below them; x02 '
                                             'recomputes it'),
    'rig.pleopod.x_25': ('[D]', 'X2c: pleopods 2-5\'s bases off the midline, inside their sternite\'s lateral face (the '
                                'protopods sit at the sternites\' lateral ends; the sternite\'s half-width 11.3-13.5 mm on '
                                'somites 2-5), so each base is seated in its sternite (X2b: 10, under it)'),
    'rig.pleopod.splay_25': ('[D]', 'X2c: the folded pleopods 2-5 turned this far outward from forward, so their tips lie '
                                    'in the slot between the sternite and the pleuron (its middle 13.8-16.0 mm off the '
                                    'midline; the tips at 14.9)'),
    'rig.pleopod.at_25': ('[E]', 'X2b: pleopods 2-5\'s bases this fraction of their somite back from its front (pleopod '
                                 '1 mid-somite): folded forward they stay within their own somite'),
    'rig.pleopod.tilt1': ('[E]', 'pleopod 1 lies forward along the sternum, this far below the horizontal (X2: 50, was 20: '
                                 'at 20 the gonopod\'s tip ran 2.9 mm into the clay\'s carapace under its hind margin; at '
                                 '50 it ends just behind it, down along the last sternites; gate X10\'s pose sweeps)'),
    'rig.pleopod.tilt': ('[D]', 'pleopods 2-5 this far back of the vertical (- forward): X2b (10-29, the lead\'s call): '
                                'TUCKED under the pleura, lying forward along the sternites 1 deg below the horizontal '
                                '(c06, c10, c04 show none below the pleura; X2 hung them 20 back of the vertical, rods '
                                'under the boxes); the fold axis stays perpendicular to the caudal (a positive turn '
                                'swings the tip down and back, the power stroke)'),
    'rig.uropod.base': ('[E]', 'the protopod\'s joint (x, dz from the telson\'s joint): T6\'s posterolateral corner, by '
                               'eye on c11 (M1\'s T6 about 0.21 CL wide each side at its hind margin), on L1\'s fan; X2 '
                               'traces the fan'),
    'rig.uropod.endo': ('[E]', 'the endopod\'s base (x, dz from the telson\'s joint), by eye on c11'),
    'rig.uropod.endo_tip_x': ('[E]', 'the endopod\'s tip off the midline; its dz is the telson\'s length x '
                                     'abdomen.uropod_reach (the uropods reach about the telson\'s tip, c11)'),
    'rig.uropod.exo': ('[E]', 'the exopod\'s base (x, dz from the telson\'s joint), by eye on c11'),
    'rig.uropod.exo_dist': ('[E]', 'the exopod\'s joint at the diaeresis (x, dz), by eye on c11 (the beaded suture)'),
    'rig.uropod.exo_tip_dz': ('[E]', 'the exopod\'s outer distal corner, dz from the telson\'s joint; its x is half '
                                     'abdomen.fan_spread, so the two exopods\' tips span the fan (M1\'s widest points '
                                     'sit just behind the telson\'s base, c11)'),
    'rig.eyestalk.base': ('[E]', 'the eyestalk\'s socket (x, dy from the cornea\'s height, z): close under the rostrum\'s '
                                 'base, behind the orbit (c11; [L5])'),
    'rig.eyestalk.mid': ('[E]', 'the second article\'s joint this fraction of the way from the socket to the cornea'),
    'rig.antenna.base': ('[E]', 'the antennal peduncle\'s base (x, dy from the cornea\'s height, z): lateral of and '
                                'below the eyestalk (c11: about 0.10 CL out)'),
    'rig.antenna.ped': ('[E]', 'the three visible peduncle articles, summing to antenna.peduncle'),
    'rig.antenna.yaw': ('[D]', 'the antenna\'s plan direction at the bind (deg from forward toward the left): 40 forward '
                               'of lateral, the middle of the peduncle\'s yaw range (rig.ranges.antenna_yaw, from '
                               'lateral); the flagellum straight along it (the octopus arm\'s rule: one tube on equal '
                               'straightened steps)'),
    'rig.antenna.pitch': ('[D]', 'the antenna\'s pitch at the bind: the middle of its range'),
    'rig.antenna.n_flag': ('[H]', 'plan §10.1: flagellum_00..15, the flagellum on 16 equal straightened steps'),
    'rig.antennule.base': ('[E]', 'the antennular peduncle\'s base (x, dy from the cornea\'s height, z): between the '
                                  'eyestalks, under the rostrum'),
    'rig.antennule.ped': ('[E]', 'the three peduncle articles; the two flagella take the rest of antenna.antennule'),
    'rig.antennule.yaw': ('[E]', 'the antennule\'s plan direction (deg from forward toward the left): forward, a little '
                                 'out (c11)'),
    'rig.antennule.pitch': ('[E]', 'the antennule\'s rise: the flagella point forward and up (c11, c08)'),
    'rig.antennule.split': ('[E]', 'each flagellum\'s yaw off the peduncle\'s line: the lateral one out, the medial in'),
    'rig.antennule.n_flag': ('[H]', 'plan §10.1: 2 x 4 flagellum joints a side'),
    'rig.mxp3.base': ('[E]', 'the third maxilliped\'s base (x, dy above the carapace\'s margin, z): in front of the mouth, '
                             'under the head (c09, n01: seen, not measured)'),
    'rig.mxp3.seg': ('[E]', 'its three visible articles (plan §4), about 0.36 CL in all'),
    'rig.mxp3.yaw': ('[E]', 'its plan direction (deg from forward toward the left)'),
    'rig.mxp3.pitch': ('[E]', 'its pitch (- down)'),
    'rig.cheliped.coxa': ('[D-x1 from P n01]', 'the cheliped\'s coxa: x0b.n01.P1_coxa x CL (X0b (6))'),
    'rig.cheliped.seg': ('[D-x2 from P c11, n04, n01]', 'the cheliped\'s basi-ischium, merus and carpus, MEASURED at X2 '
                                                        '(10-28; X1 had them [E] 20 / 50 / 37.5). The CARPUS is the large '
                                                        'knobby segment attached to the claw (M1 c11, M3 n04, M4 n01, c13 '
                                                        'agree: no shorter knob lies between it and the propodus, so the X1 '
                                                        'review\'s 0.15-0.2 CL reading does not hold): the mean of M1\'s two '
                                                        'traced carpi, wrist to the middle of the merus-carpus joint line '
                                                        '(x2.c11.carpus, 0.390 / 0.412) x CL, projections on a mount, so a '
                                                        'lower bound; M4 pinned flat reads 0.382 / 0.379 of its fan, M3\'s '
                                                        'carpus / crusher propodus 0.369 gives 0.426 CL on L1\'s crusher, '
                                                        'c13\'s 0.317 gives 0.366. The MERUS and the BASI-ISCHIUM: the '
                                                        'carpus x the mean ratio of the two chains that lie FLAT with the '
                                                        'segment ends readable (x2.n04 M3\'s attached crusher chain on its '
                                                        'side, x2.n01 M4\'s image-left cheliped pinned ventral): merus / '
                                                        'carpus 1.065 / 1.139, basi-ischium / carpus 0.346 / 0.303 (n01\'s '
                                                        'coxa-basis end mirrored [E]); c13 (a mount, its carpus raised) '
                                                        'reads the merus 1.38 of its carpus, the spread\'s top. c11 shows '
                                                        'the merus for only 0.2-0.4 CL before it runs steeply under the '
                                                        'carapace: not read there. Joints +-3-4 % of a segment'),
    'rig.cheliped.wrist_z': ('[D-x2 from P c11]', 'the bind\'s wrists (the carpal joints) this far AHEAD of the orbit: '
                                                  'the mean of M1\'s two traced wrists (x2.c11.wrist_z, the crusher '
                                                  '0.298, the cutter 0.374 CL), the lead\'s call (X2: the wrists near '
                                                  'c11\'s). The mid-range solve with the measured segments alone puts '
                                                  'them 0.43 CL ahead (X1\'s [E] segments: 0.55): solve_cheliped holds '
                                                  'the wrist\'s z here and leaves its x and the arm to the mid-range '
                                                  'rule; c06 shows its wrists about 0.3 CL ahead by eye, v01 about level '
                                                  'with the eyes'),
    'rig.cheliped.cutter_dactyl': ('[D-x2 from P c11]', 'the cutter\'s dactyl / its propodus, MEASURED at X2 (10-28; X1 had '
                                                        'M3\'s crusher ratio 0.452 [E]): the dactyl from its pivot, M1\'s '
                                                        'articulation knob (x2.c11.cu_artic), to its closed tip at the fixed '
                                                        'tip lifted rig.cheliped.cutter_hinge c, by X1\'s claw rule: '
                                                        'sqrt((L - a)^2 + ((b - c) palm)^2) / L. M1\'s cutter tip lies behind '
                                                        'the crusher\'s dactyl (its estimate, x2.c11.cu_dactyl_tip, gives a '
                                                        'lower bound 0.49): a cutter\'s fingers run longer to its palm than a '
                                                        'crusher\'s. X2b (10-29): with the whole cutter (chela.cutter_len '
                                                        '114.7, was the occluded 107.7) and the knob read on the cutter\'s own '
                                                        'axis (rig.cheliped.cutter_axis): 0.553, was 0.538. X2c (10-29): '
                                                        'the tip fitted to c13 (rig.cheliped.cutter_cap): 0.5533. X4f '
                                                        '(11-01): the rule unchanged, its c now the cutter\'s CLAY contact '
                                                        '(rig.cheliped.cutter_hinge): 0.5510, the tip 0.27 mm nearer the '
                                                        'knob (iterated with c to their fixed point). A0 (x6fix_x7, 11-10): '
                                                        '0.551002 -> 0.550973 with the cutter\'s new c'),
    'rig.cheliped.claw_yaw': ('[D]', 'the claws\' axes at the bind (deg toward the left of forward; - toward the '
                                     'midline): forward (v01: carried forward, side by side) and converging, the '
                                     'arm out and the wrist turned in as c11 (the crusher\'s axis 23 deg in) and c08 '
                                     '(both claws turned in before the face) show'),
    'rig.cheliped.claw_pitch': ('[D]', 'the claws\' axes pitched down: low, carried near the ground (v01)'),
    'rig.cheliped.claw_plane': ('[D-x1 from P c10, c06, v01, c01, c03, c11]',
                                'A0 (x6fix_x7, 11-10; the lead\'s shape audit, point 4: "narrow from above, very deep from '
                                'the side"): the FINGERS\' PLANE, deg up from flat (decapod.claw: at 0 the dactyl is the '
                                'MEDIAL finger, the broad faces dorsal and ventral, the wrist\'s hinge axis the claw\'s '
                                'thickness; 90 = X1-X4h\'s vertical plane, the dactyl up). MEASURED on the photos '
                                '(lobster/x6fix_x7_NOTES.md, the A0 table; apparent palm width / propodus length a at each '
                                'camera): the walking and resting animals carry both claws FLAT: c10 (standing in water, '
                                'X0b\'s camera 26.75 deg down) a 0.23 where a flat cutter reads 0.25 and a vertical one '
                                '0.33; c06 (the crouch, 19 deg down) 0.23 near and 0.24 far, the near claw seen along its '
                                'lateral margin with no gape; v01 (walking) broad paddles from above; c01 / c03 (live, on a '
                                'table, dorsal) and M1\'s mount (c11) face-on from above. Only the DEFENSIVE postures roll '
                                'the plane up: c08 (guarding its burrow, the claws crossed before the face) and c04 (in air '
                                'on a rock) a 0.49-0.52, face-on to a side or front camera. X0b had read c06 / c10\'s '
                                'visible dorsal faces (the cameras look down) as a vertical plane'),
    'rig.cheliped.tip_h': ('[D-x2 from P c11, c10]',
                                                'A0 (11-10, second step, 17:00): 36.925 again, X2\'s value, now with the FLAT '
                                                'plane: the wrist 57 mm up, the claws CARRIED. c10 (the standing animal the '
                                                'bind\'s lift comes from; X0b\'s camera 26.75 deg down in water, 551 px a CL) '
                                                'carries its near claw clear of the gravel: its wrist images 74 px above the '
                                                'carapace\'s lower margin (38.3 mm up) and stands nearer the camera, so 55-70 '
                                                'mm up for a wrist 30-59 mm off the midline, its claw\'s underside about 50 '
                                                '(scratch x6fix_x7/org; the sheet lobster_organic_A0_c10_claw_carried). The '
                                                'first step (16:00) had stood the flat claw\'s lowest point 2 mm over the '
                                                'ground (tip_h 7.513, the wrist 27.5): the merus then lay level through the '
                                                'second walking leg (x02 _a0b: 3.8 mm inside its propodus and carpus), which '
                                                'passes UNDER the cheliped\'s rising merus (c06, c10). x02 gates the clay\'s '
                                                'lowest point at rig.cheliped.low_clear. '
                                                'BEFORE A0, on the vertical plane (36.925): '
                                                'the crusher\'s fixed finger tip above the ground at the bind, set at X2 '
                                                '(10-28; X1 had 10 [D] from the stick) so the CLAW rests low (v01) on '
                                                'its real shape: the lowest point of the crusher\'s propodus (M1\'s '
                                                'outline in the fingers\' plane, decapod_parts.claw_polys: the palm '
                                                'bulges 42 mm to the FIXED finger\'s side of the axis, the side that '
                                                'faces down with the dactyl up) stands rig.cheliped.low_clear over the '
                                                'ground at rig.cheliped.claw_pitch: low_clear + L d_y - min(s d_y + m '
                                                'n_y). X1\'s 10 put that palm 25 mm under the ground. The wrist then '
                                                'stands 57 mm up (c06\'s crouch shows its wrist about 31 mm over the '
                                                'sand, 53 at the bind\'s lift); the cutter follows on the shared axis'),
    'rig.cheliped.low_clear': ('[D-x2 from P c10]', 'the crusher\'s lowest point this far over the ground at the bind. A0 '
                                                    '(11-10): 31.41, the flat claw\'s ventral face at X2\'s wrist height '
                                                    '(rig.cheliped.tip_h: c10 carries its claws; x02 holds the clay\'s lowest '
                                                    'point here +- 0.15). X2-X4h, on the vertical plane: 2.0, low, just clear '
                                                    '(c06 rests the crusher on the sand at the crouch: the REST pose still '
                                                    'does, decapod.rest_pose)'),
    'rig.cheliped.low_point': ('[D-x2 from P c11]', 'A0 (11-10, the flat plane): (s, m, t), t along the claw\'s thickness '
                                                    'd x n (down on the left): the clay\'s lowest point at the bind, on the '
                                                    'palm\'s ventral face (scratch x6fix_x7/p4/probe_flat.py; x02 reads the '
                                                    'mesh\'s within 1.5 mm); decapod.claw_low_point carries it for the rest '
                                                    'pose without the clay (x01). BEFORE A0 (78.71, -41.92), on the vertical '
                                                    'plane: '
                                                    'the crusher propodus\'s lowest point at the bind (s along the claw '
                                                    'axis from the wrist, m toward the dactyl, life mm): the point of M1\'s '
                                                    'traced propodus (decapod_parts.claw_polys) lowest at '
                                                    'rig.cheliped.claw_pitch, on the palm\'s lateral margin; tip_h stands '
                                                    'it low_clear over the ground, and the rest pose rests it on the sand'),
    'rig.cheliped.wrist_x': ('[E]', 'the band the wrist (the carpal joint) may take off the midline, the mid-range solve '
                                    'picking inside it: from the claws side by side before the face (v01; the '
                                    'crusher\'s [E] 0.30 CL thickness clear of the head) out to c08\'s wide wrists (c11\'s '
                                    'mount holds them at 0.68 CL)'),
    'rig.cheliped.dactyl_open': ('[D]', 'both dactyls open: slightly (v01), a quarter of the crusher\'s 0-40 range'),
    'rig.cheliped.hinge': ('[D-x2 from P n04, c11]', 'the CRUSHER\'s dactyl hinge (b) and its closed tip (c) off the '
                                                     'claw axis toward the dactyl, fractions of the palm, IN the fingers\' '
                                                     'plane (A0, 11-10: that plane is rig.cheliped.claw_plane, flat, the '
                                                     'dactyl the MEDIAL finger; X1-X4h held it VERTICAL, the dactyl the '
                                                     'upper finger, on X0b\'s reading of c06 / c10 / c08: the claw_plane '
                                                     'row). X4f (10-31, the lead\'s call 1 on the X4e '
                                                     'check): the hinge is the CONDYLE\'s axis, n04\'s ball on the broad '
                                                     'face (x2.n04.condyle) set on M1\'s own claw plan (decapod_parts '
                                                     'condyle_hinge: from M1\'s knob x2.c11.cr_artic toward its gape\'s '
                                                     'bottom and into the palm), 7.0 mm under the top margin: b its offset '
                                                     'from the axis / the palm (X2 - X4e: 0.31149, M1\'s knob itself, which '
                                                     'left no room for r57282_7\'s top slit and put the condyles on the '
                                                     'shoulders); its place along the axis rig.cheliped.hinge_s. c the '
                                                     'closed tip\'s height at the fixed tip\'s s: the rig\'s 0 is where the '
                                                     'fingers\' CLAY first meets closing about that hinge (decapod_parts '
                                                     'clay_contact, the molars at s 115; X4f\'s first value 0.085272 put '
                                                     'the PLAN contact there, plan_contact 15.49 deg from M1\'s pose, and '
                                                     'the clay\'s rounded edges met 0.38-0.43 deg later: x04 _x4f3 gate '
                                                     '12 read -0.42 on the limits, 0.25 mm apart at 0; X2 - X4e: 0.06 [E], '
                                                     'which put the rig\'s 0 at the contact by luck on the old hinge); '
                                                     'x02 recomputes both (c: the clay contact at the rig\'s 0). A0 '
                                                     '(x6fix_x7, 11-10): c 0.079461 -> 0.079545 on the round-margin '
                                                     'clay (decapod_parts CLAW round: its fingers meet 0.0055 deg later)'),
    'rig.cheliped.hinge_s': ('[D-x2 from P n04, c11]', 'X4f: the crusher\'s hinge along the claw axis / the propodus '
                                                       '(chela.crusher_len), from the wrist: the condyle\'s place as '
                                                       'rig.cheliped.hinge b, so decapod.claw no longer derives it by the '
                                                       'claw rule (with M3\'s dactyl, chela.crusher_dactyl, the rule puts the '
                                                       'condyle 1.3 mm short of the photo\'s place; M1\'s dactyl tip lies '
                                                       '53.70 mm from it, the bone stays 52.164); x02 recomputes it'),
    'rig.cheliped.cutter_hinge': ('[D-x2 from P n04, c11, r57282_7]', 'the CUTTER\'s, as rig.cheliped.hinge: X4f, the '
                                                                          'lead\'s call 2 (socket the cutter the same '
                                                                          'way): its condyle placed as the crusher\'s, '
                                                                          'n04\'s reading (x2.n04.condyle) on M1\'s cutter '
                                                                          'plan (its knob x2.c11.cu_artic turned onto the '
                                                                          'cutter\'s own axis, rig.cheliped.cutter_axis, and '
                                                                          'its gape\'s bottom), 3.6 mm under its top '
                                                                          'margin: no photo in the sweep shows a cutter\'s '
                                                                          'broad face square at the hinge (n04\'s cutter '
                                                                          'lies closed on its side); r57282_7\'s cutter '
                                                                          'shows the crusher\'s arrangement, a top slit and '
                                                                          'the gape-side crescent meeting at a boss (X2 - '
                                                                          'X4e: b 0.37672, the knob). c as the crusher\'s: '
                                                                          'the rig\'s 0 is where its fingers\' CLAY first '
                                                                          'meets (decapod_parts clay_contact: the tips, s '
                                                                          '112; X2 - X4f\'s first value 0.06 [E] left it '
                                                                          '1.55 deg past the contact about the moved hinge, '
                                                                          'its fingers 1.2 mm into each other at 0; M1\'s '
                                                                          'cutter reads 0.08 deg open of it now, at contact '
                                                                          'as c11 shows); x02 recomputes both. A0 (x6fix_x7, '
                                                                          '11-10): c 0.110559 -> 0.111246 on the round-margin '
                                                                          'clay (its fingers meet 0.0206 deg later)'),
    'rig.cheliped.cutter_hinge_s': ('[D-x2 from P n04, c11, r57282_7]', 'X4f: the cutter\'s hinge along its claw axis / '
                                                                        'its propodus (chela.cutter_len), as '
                                                                        'rig.cheliped.hinge_s; x02 recomputes it'),
    'rig.cheliped.cutter_axis': ('[D-x2 from P c11, c13]', 'the cutter\'s claw axis, the wrist to its fixed tip as the '
                                                           'crusher\'s, turned this far (deg) toward the dactyl from M1\'s '
                                                           'traced axis (the wrist to cu_tip, where the tip goes out of '
                                                           'sight under the crusher\'s dactyl): the fixed tip continued '
                                                           'past it (chela.cutter_len\'s construction) lies 6.9 mm off that '
                                                           'line (X2b 6.3; X2c\'s tip fitted to c13), the fingers curving in '
                                                           '(c13\'s free fingers run 21-23 deg off its own axis). '
                                                           'decapod_parts.Outline turns the cutter\'s frame by it; x02 '
                                                           'recomputes it'),
    'rig.cheliped.cutter_cap': ('[D-x2 from P c13]', 'X2c (10-29, the lead\'s call: "the cutter\'s fixed-finger tip cap at '
                                                     'r ~1.4 mm", from the X2b check\'s estimate): the cap\'s radius (mm) '
                                                     'whose tip best matches c13\'s whole cutter, least squares over '
                                                     'x2.c13.tip_profile and tip_palm[0] at x2.c13.tip_stations '
                                                     '(decapod_parts.fit_cutter_cap), LIKE FOR LIKE: chords across the '
                                                     'finger\'s own axis at the tip, as c13\'s are read, at c13\'s stations '
                                                     'scaled by the palm, as its widths are. 1.70 mm, rms 0.0024 palm, '
                                                     'every station within -3 / +5 %; the check\'s 1.4 (an estimate on '
                                                     'stations scaled by the claw\'s length with chords across the claw '
                                                     'axis) reads 7-13 % narrower than c13 here, X2b\'s fillet 2.13 mm 10-19 '
                                                     '% wider; x02 recomputes it'),
    'rig.p23': ('[E]', 'P2 / P3\'s basi-ischium, merus, carpus, propodus, dactyl: P4\'s (plan §2.4: P2 = P3 = P4 +- 10 %; '
                       'not measured, they overlap on M4); M3\'s loose chelate leg (n04, leg D) is the reading for X2'),
    **{f'rig.leg_az.{lg}': ('[D-x1 from P c03, c01]', f'{lg}\'s plan directions at the bind (deg from forward toward the '
                                                      f'left, seen from its coxa\'s medial articulation, legs.coxae): '
                                                      f'(the knee, the dactyl\'s tip), the MEDIANS of the x1.* readings '
                                                      f'(c03 and c01, both sides, the right mirrored)'
                                                      + ('; the tip rests on one probable reading (c01\'s right chela)'
                                                         if lg == 'P2' else ''))
       for lg in ('P2', 'P3', 'P4', 'P5')},
    'rig.tip_x': ('[P c08]', 'the walking legs\' tips off the midline in the RAISED stance (CL): c08\'s frontal reading '
                             'of the Karlsruhe animal c10 shows, both sides 0.41-0.65, widened (X0b: '
                             'x0b_cameras.TIP10_BAND)'),
    'rig.rest_tip_x': ('[D-x1 from P c06]', 'the walking legs\' tips off the midline in the REST pose (CL): c06\'s near '
                                            'P2 and P5 tips (and P3\'s or a maxilliped\'s) touch the glass, and through '
                                            'c06\'s CENTRAL camera (rest.c06_camera, the camera rest.c06\'s heights come '
                                            'from) the glass stands 0.513-0.573 CL out at their image x (x0b_cameras.json '
                                            'c06.glass_tips; the frame line\'s residual tilt over x 812-1380; x00b\'s d_g '
                                            '0.556 at the reference x). The X1 review (10-28) replaced X0b\'s all-camera '
                                            'band (x0b_cameras.GLASS_BAND 0.40-1.05), which stood the feet about 1.0 CL out, '
                                            'past the glass of the camera that sets the body. P3 / P4\'s own c06 ends (the '
                                            'pale legs, rig.rest_tip_z) are not at the glass: their lateral offset waits on '
                                            'c06\'s legs traced (X2)'),
    'rig.knee_sigma': ('[D]', 'the pull of the photos\' medians in the mid-range solve: (the knee\'s azimuth - leg_az[0]) '
                              '/ knee_sigma and (the tip\'s - leg_az[1]) / knee_sigma beside each joint\'s (angle - '
                              'middle) / half-range'),
    'rig.az_pad': ('[E]', 'the readings\' uncertainty on a leg direction (deg): the orbits PLACED by M1\'s rostrum ratio '
                          '(+-3 % CL along the axis, about 3 deg at a leg\'s reach) and +-3-5 px on each point; the '
                          'build\'s knee and tip azimuths must lie inside the photos\' spread widened by it'),
    'rig.fan_contact_z': ('[D-x1 from P c06]', 'the REST pose\'s fan contact: c06\'s near exopod on the sand '
                                               '(x0b_cameras.json c06.fan_contact, x 1712) in c06\'s frame, z = -(x - '
                                               'the orbit\'s 775) / its CL 516 px x CL'),
    **{f'rig.rest_tip_z.{lg}': ('[D-x1 from P c06]', f'the REST pose\'s {lg} tip z: c06\'s near {lg} tip ('
                                                     + dict(P2='x0b_cameras.json c06.glass_tips P2_near, x 812',
                                                            P3='the first pale near leg\'s end on the sand, ref_contacts '
                                                               'x 1100 (P3 by position, X0b)',
                                                            P4='the second pale near leg\'s end, ref_contacts x 1192 (P4 '
                                                               'by position, X0b)',
                                                            P5='glass_tips P5_near, x 1380')[lg]
                                                     + ') in c06\'s frame, z = -(x - the orbit\'s 775) / its CL 516 px x '
                                                       'CL; its lateral offset free in rig.rest_tip_x')
       for lg in ('P2', 'P3', 'P4', 'P5')},
    'rig.rest_pleopod_fold': ('[D]', 'the REST pose folds pleopods 2-5 forward along the sternites by this much about '
                                     'their own axis (their power stroke\'s, so -), clear of the sand in the crouch. X2b: '
                                     '0, was -90: the bind already lies them forward along the sternites (rig.pleopod.tilt)'),
    'rig.rest_curl_back': ('[D]', 'the REST pose turns the fan down (c06): abd_5, abd_6 and the telson flexed to their '
                                  '[E] limit (rig.ranges.abdomen), abd_2..4 then solved so the abdomen\'s lowest point '
                                  'rests on the sand. c06\'s own contact (rig.fan_contact_z, 0.82 CL behind the carapace) '
                                  'would need about 49 deg on each of the three: L1\'s abdomen is Pope\'s straight 1.54 CL, '
                                  'longer than the photos\' animals\' 1.28-1.36'),
    'rig.ranges.walking.promotion': ('[E]', 'plan §10.3: the thorax-coxa promotion (+ forward) from n01\'s pinned coxae '
                                            '(lateral: azimuth 90); gate v01 at 25 fps'),
    'rig.ranges.walking.levation': ('[E]', 'plan §10.3\'s coxa-basis levation (+ up) from the coxa\'s line, -20 / +40, '
                                           'WIDENED by the X1 review (10-28) to +70 by c06: its crouch folds the near '
                                           'legs into a tall arch, the knees high beside the carapace and the tips down '
                                           'at the glass (rig.rest_tip_x), which these legs reach only at 58-68 deg (P3 '
                                           'the most); the bind\'s levations move 1-3 deg with the range\'s middle; gate '
                                           'v01 at 25 fps and c06\'s traced legs (X2 / X10)'),
    'rig.ranges.walking.ischium_merus': ('[E]', 'plan §10.3: the basis-merus rotation, 0 straight'),
    'rig.ranges.walking.knee': ('[E]', 'plan §10.3: the merus-carpus INCLUDED angle; gate n01\'s pinned legs, v01'),
    'rig.ranges.walking.carpus_propodus': ('[E]', 'the carpus-propodus deflection (+ the distal leg back), 0 in line: '
                                                  'WIDENED by X1 from plan §10.3\'s +-30 to +-45, because the photos\' '
                                                  'stances need it: c03\'s P3 tips stand about 37 deg forward of their '
                                                  'knees in plan on both sides, P5\'s up to 44 deg back, and P2\'s tip '
                                                  'reads far forward (c01; corroborated by c10\'s raised stance, whose '
                                                  'near P2 chela stands about 0.4 CL ahead of the orbit); with +-30 no '
                                                  'P2 stance meets its reading inside c08\'s band; gate v01 at 25 fps '
                                                  '(X10)'),
    'rig.ranges.walking.dactyl': ('[E]', 'plan §10.3: the propodus-dactyl flexion from straight (P2 / P3: the small '
                                         'chela\'s opening)'),
    'rig.ranges.cheliped.promotion': ('[E]', 'the cheliped\'s thorax-coxa promotion (+ forward) from n01\'s lateral coxa: '
                                             'NOT in plan §10.3 (its promotion row is the walking legs\'); c11 shows the '
                                             'merus about 40 deg from forward (promotion about 50) and the claws reach '
                                             'the front of the face only with the coxa swung forward; gate v01, X10'),
    'rig.ranges.cheliped.levation': ('[E]', 'plan §10.3: the cheliped\'s coxa-basis, raised in the threat display; gate '
                                            'a threat-display photo'),
    'rig.ranges.cheliped.knee': ('[E]', 'plan §10.3: the cheliped\'s merus-carpus INCLUDED angle'),
    'rig.ranges.cheliped.wrist': ('[E]', 'plan §10.3: the carpus-propodus (+ adduction: the claw swings medially, the '
                                         'claws folding before the face, v01\'s burrow). X4f (11-01, the lead\'s call 4: '
                                         'gate the rig\'s whole range, else shrink it to what passes): -30..+60 gated, '
                                         'the cutter\'s base cap (its propodus\'s proximal grid cap) came out of the '
                                         'carpus from +58.5 (0.04 mm short of x04 gate 11\'s 0.05 at +58.5, 0.03 mm out '
                                         'at +60; scratch x4f probe_wrist_cap on _x4f3): +57.5. (decapod.solve_cheliped '
                                         'reads the range\'s middle, so the bind\'s wrist moved 0.6 mm with it.) The bind\'s '
                                         'move re-laid that cap: its rings walked to its round pole (cap_c 1.0 never fires '
                                         'there), 2 of its 0.1 mm centre quads folding the limit (x04 gate 2), and larger '
                                         'hand-overs stood out of the carpus over the range: 3rd session +55; 4th session the '
                                         'rings stop at a 1 mm radius (decapod_cage CAGE cap_rmin_cutter: no folds), its cap '
                                         '0.04 mm inside the carpus at +55 against gate 11\'s 0.05 (scratch x4f probe_g23 '
                                         'y3): +52.5'),
    'rig.ranges.cheliped.crusher': ('[E]', 'plan §10.3: the crusher\'s dactyl, 0 closed (X4f: 0 is the clay\'s contact, '
                                           'rig.cheliped.hinge c); gate c08\'s open claws'),
    'rig.ranges.cheliped.cutter': ('[E]', 'plan §10.3: the cutter\'s dactyl, 0 closed (X4f: 0 is the clay\'s contact, '
                                          'rig.cheliped.cutter_hinge c). X4f, 4th session (the lead\'s call 4\'s rule: '
                                          'shrink a range to what passes): 0..55 gated, the dactyl\'s base swept into the '
                                          'propodus\'s face by the top ray past the knob from 50 (x04 gate 9 newly, the '
                                          'propodus in the dactyl: 0.31 mm at 50, 0.54 at 52.5, 0.77 at 55; 0.08 at 47.5; '
                                          'scratch x4f probe_g23 x1 / y1): 47.5. The clay\'s socket keeps '
                                          'chela.dactyl_open\'s 55. X4g (the lead\'s call 1 on the X4f check: clear the '
                                          'clay at its full socket range, don\'t shrink the rig): the overlap was the '
                                          'hub\'s fill and the top collar\'s union swell past the knob, which gate 9 '
                                          'sampled at level 2 read short (decapod_parts SOCKET, THE TOP SLIT): with the '
                                          'boss-sized cup it clears; back to the socket\'s 55, x04 gate 9 on the level-3 '
                                          'limits'),
    'rig.ranges.abdomen': ('[E]', 'plan §10.3: each abdominal joint, extension - / flexion +; 6 x 35 folds the fan '
                                  'under the body [L11]'),
    'rig.ranges.uropod': ('[E]', 'plan §10.3: the uropods\' spread, 0 folded to 40 spread (1.0 CL; c11, c03)'),
    'rig.ranges.eyestalk_yaw': ('[E]', 'plan §10.3'),
    'rig.ranges.eyestalk_pitch': ('[E]', 'plan §10.3'),
    'rig.ranges.antenna_yaw': ('[E]', 'plan §10.3: the antennal peduncle\'s yaw FROM LATERAL, -10 back / +90 forward; '
                                      'gate v01\'s burrow minutes'),
    'rig.ranges.antenna_pitch': ('[E]', 'plan §10.3'),
    'rig.ranges.flagellum': ('[E]', 'plan §10.3: each flagellum joint'),
    **{f'x1.c03.{nm}': ('[P c03]', f'P1 (c03, live, dorsal, on a floor): {nm.replace("_", " ")}, (z, x) in CL in its body '
                                   f'frame (the sweep\'s orbit, placed by M1\'s rostrum ratio: +-3 %), the right side '
                                   f'mirrored; src_c03_x1.json')
       for nm in ('P2_R_knee', 'P3_R_knee', 'P3_R_tip', 'P4_R_knee', 'P4_R_tip', 'P5_R_knee', 'P5_R_tip', 'P2_L_knee',
                  'P3_L_knee', 'P3_L_tip', 'P4_L_knee', 'P4_L_tip', 'P5_L_knee', 'P5_L_tip')},
    **{f'x1.c01.{nm}': ('[P c01]', f'P4 (c01, live, dorsal, on a sink): {nm.replace("_", " ")}, (z, x) in CL in its body '
                                   f'frame (the orbit placed by M1\'s rostrum ratio, as the sweep placed c03\'s: +-3 %), '
                                   f'the right side mirrored; src_c01_x1.json'
                                   + (' (PROBABLY P2\'s chela, seen past the cheliped\'s carpus)' if nm == 'P2_R_tip'
                                      else ''))
       for nm in ('P3_L_knee', 'P3_L_tip', 'P4_L_knee', 'P4_L_tip', 'P5_L_knee', 'P5_L_tip', 'P2_R_tip', 'P3_R_knee',
                  'P4_R_knee', 'P4_R_tip', 'P5_R_knee', 'P5_R_tip')},
    # X2's cheliped readings (src_<id>_x2.json; x02_clay.py recomputes each)
    'x2.c11.carpus': ('[P c11]', 'M1 (L1\'s claws): the crusher\'s and the cutter\'s carpus, the wrist (the sweep\'s '
                                 'cr_joint / cu_joint) to the middle of the merus-carpus joint line / CL: projections on a '
                                 'mount that raises the chelae (lower bounds); src_c11_x2.json'),
    'x2.c11.wrist_z': ('[P c11]', 'M1: the crusher\'s and the cutter\'s wrists ahead of the orbit along the body axis / CL '
                                  '(the sweep\'s points)'),
    'x2.c11.wrist_x': ('[P c11]', 'M1: the two wrists off the midline / CL'),
    'x2.c11.elbow_z': ('[P c11]', 'M1: the two elbows (the merus-carpus joint lines\' middles) along the body axis / CL '
                                  '(- behind the orbit): information; the mount raises the arms, so the merus runs steeply '
                                  'and the elbows sit nearer the body in plan than a carriage with level meri'),
    'x2.c11.elbow_x': ('[P c11]', 'M1: the two elbows off the midline / CL (information)'),
    'x2.c11.cr_artic': ('[P c11]', 'M1\'s crusher articulation knob (src_c11_outline_x2.json cr_artic, on the claw\'s '
                                   'silhouette, research/lobster_work/scripts/loutline.py): along the claw axis (the '
                                   'carpal joint cr_joint to the fixed tip cr_tip) and off it toward the dactyl / CL'),
    'x2.c11.cu_artic': ('[P c11]', 'M1\'s cutter articulation knob (cu_artic), as x2.c11.cr_artic on its own axis'),
    'x2.c11.cr_dactyl_tip': ('[P c11]', 'the crusher\'s dactyl tip (the sweep\'s cr_tip_inner) along and off its axis / '
                                        'CL: with cr_artic, c11\'s opening (17.4 deg; x02 poses the clay\'s dactyl there '
                                        'for the outline gate)'),
    'x2.c11.cu_dactyl_tip': ('[P c11] [E]', 'the cutter\'s dactyl tip, behind the crusher\'s dactyl: the first X2 '
                                            'tracing\'s estimate (+-15 px), along and off its axis / CL'),
    'x2.n04.merus_carpus': ('[P n04]', 'M3 (the disarticulated giant): its crusher\'s ATTACHED chain lying on its side, '
                                       'merus / carpus, joint to joint (the elbow at the carpus\'s condyle in the merus\'s '
                                       'distal membrane window, the merus-ischium joint at its folded membranes; an oval '
                                       'cleaning hole in the merus is not a joint); src_n04_x2.json'),
    'x2.n04.bi_carpus': ('[P n04]', 'M3: the basi-ischium (the merus-ischium joint to the broken coxa-basis '
                                    'articulation) / the carpus'),
    'x2.n04.carpus_propodus': ('[P n04]', 'M3: the carpus / the crusher propodus (a giant: its crusher about 1.57 of its CL, '
                                          'src_n04_x0b.json; information)'),
    'x2.n04.suture_frac': ('[P n04]', 'M3: the basi-ischial suture (the autotomy plane) along the basi-ischium from the '
                                      'merus-ischium joint, a fraction (information for the X3 ring)'),
    'x2.n04.condyle': ('[P n04]', 'X4f (the lead\'s call 1 on the X4e check): M3\'s crusher, lying with its broad face up, '
                                  'the propodus-dactyl CONDYLE, the hard ball in its cup between the dactyl\'s base and the '
                                  'palm: its centre along the knob -> the gape\'s bottom chord (f) and into the palm across '
                                  'it (e), both / that chord (src_n04_x2.json cr_knob, cr_gape, cr_condyle, read at full '
                                  'size: x4f_notes, +-10 px on the ball, +-15 px on the knob and the gape; f 131.6 / e 102.6 '
                                  'of 654.3 px). The rim on the face bends there from the knob down to the gape: r57282_7\'s '
                                  'top slit and gape-side crescent meet at the same boss, r57282_6 shows the outer slit, '
                                  'c05\'s C-shaped rim wraps the base on both sides (rig.cheliped.hinge)'),
    'x2.n04.condyle_r': ('[P n04]', 'X4f: that ball\'s radius / the knob -> gape chord (cr_condyle_rim): the condyles\' '
                                    'size on L1 (decapod_cage FEAT condyle)'),
    'x2.n01.merus_carpus': ('[P n01]', 'M4 (pinned flat, ventral): the image-left (the animal\'s right) cheliped\'s merus / '
                                       'carpus; src_n01_x2.json'),
    'x2.n01.bi_carpus': ('[P n01] [E]', 'M4: that cheliped\'s basi-ischium / carpus, its coxa-basis end X0b\'s image-right '
                                        'joint mirrored about the sternal crease [E] (the maxillipeds cover it)'),
    'x2.n01.carpus_fan': ('[P n01]', 'M4: the two carpi / its fan (information: L1\'s legs carry M4\'s fan as 1.00 CL)'),
    'x2.n01.mb_carpus': ('[P n01]', 'M4: the merus + basi-ischium / the carpus, both sides (the image-right merus-ischium '
                                    'joint is not readable; information)'),
    'x2.c13.merus_carpus': ('[P c13]', 'the Cambridge mount: its right cheliped\'s merus / carpus (a mount, the carpus '
                                       'raised: the spread\'s top; information); src_c13_x2.json'),
    'x2.c13.carpus_propodus': ('[P c13]', 'the Cambridge mount: its right carpus / its propodus (its claws 1.6 CL long; '
                                          'information)'),
    'x2.c13.tip_palm': ('[P c13]', 'the Cambridge mount\'s WHOLE cutter (its right claw, X2b): each finger\'s width, the '
                                   'fixed finger\'s and the dactyl\'s, across its own centreline L/40 behind its tip, where '
                                   'the round cap begins / the palm\'s widest width across the claw axis (src_c13_x2.json '
                                   'R_fx_a / _b, R_dc_a / _b, R_palm_lat / _med, read from the claw\'s silhouette): the '
                                   'X2 check\'s "narrow rounded tips", an eighth and a sixth of the palm; c06\'s live '
                                   'cutter, face-on, shows the same form; the clay\'s two cutter tips take these widths '
                                   'on M1\'s palm'),
    'x2.c13.tip_profile': ('[P c13]', 'X2c: the fixed finger\'s width / the palm 4, 8, 12 and 16 px behind its tip, across '
                                      'its own centreline (src_c13_x2.json R_fx4_a / _b .. R_fx16_a / _b: the X2b reading '
                                      'from the claw\'s silhouette re-run as edge pairs; +-2 px on the edge): a little '
                                      'more pointed than a half circle. With tip_palm[0] (L/40) the profile '
                                      'rig.cheliped.cutter_cap is fitted to'),
    'x2.c13.tip_stations': ('[P c13]', 'X2c: those five stations behind c13\'s fixed tip (4 / 8 / 12 / 16 px, and L/40 = '
                                       'R_propodus / 40) / its palm\'s 339.0 px (R_palm): c13\'s tip region on L1 scaled by '
                                       'the palm, as its widths are'),
}

TAG_RE = re.compile(r'\[(P|L|G|H|D|E|C|S)(?:\d{1,2})?(?:-(?:lp|x0|x0b|x1|x2))?(?:[ ,][^\]]*)?\]')
MAKER_RE = re.compile(r'\[D(-(?:lp|x0|x0b|x1|x2))?[ \]]')
PHOTO_RE = re.compile(r'\b(c\d\d|n0\d|r57282_\d|v0\d)\b')

# The leaves' units (x00 checks every leaf has one; morph() scales the 'mm' leaves): the group's unit unless listed
UNIT_GROUP = dict(family='text', body_plan='text', author_scale='1', sex='text', handedness='text', photos='ratio',
                  body='mm', length='mm', abdomen='mm', chela='mm', legs='mm', antenna='mm', rest='mm', lit='pop',
                  colour='srgb8', motion='ms', x0b='ratio', rig='mm', x1='ratio', x2='ratio')
UNIT_KEY = {'photos.M2.CL_bar': 'mm', 'photos.M3.prop_bar': 'mm', 'photos.M4.fan_bar': 'mm',
            'body.rostral_teeth': 'count', 'length.mass': 'kg', 'length.mass_f': 'kg', 'abdomen.overlap': 'frac',
            'abdomen.pleopod_pairs': 'count', 'abdomen.uropod_reach': 'frac', 'chela.saw_denticles': 'count',
            'chela.tubercles': 'count', 'chela.dactyl_open': 'deg', 'rest.abd_flex_max': 'deg',
            'rest.abd_ext_max': 'deg', 'lit.eu_min_CL': 'mm', 'lit.TL_max': 'mm', 'colour.dorsum_albedo': '1',
            'motion.crusher_ma': '1', 'rest.c06_camera.phi_w': 'deg',
            'rest.c06_camera.ground_row': 'px', 'rest.c06_camera.tilt_share': 'frac',
            'rest.c06_camera.margin_offset': 'ratio', 'rest.c10_camera.phi_w': 'deg', 'rest.c10_camera.roll': 'deg',
            'rest.c10_camera.fan_tip_offset': 'ratio', 'rest.c10_camera.margin_offset': 'ratio',
            'x0b.n04.depth_factor': '1',
            # X1's rig rows that are not life mm
            'rig.body_frac': 'frac', 'rig.abd_hinge': 'frac', 'rig.pleopod.drop': 'frac', 'rig.pleopod.tilt1': 'deg',
            'rig.pleopod.drop_25': 'frac', 'rig.pleopod.at_25': 'frac', 'rig.pleopod.splay_25': 'deg',
            'rig.pleopod.tilt': 'deg', 'rig.eyestalk.mid': 'frac', 'rig.antenna.yaw': 'deg', 'rig.antenna.pitch': 'deg',
            'rig.antenna.n_flag': 'count', 'rig.antennule.yaw': 'deg', 'rig.antennule.pitch': 'deg',
            'rig.antennule.split': 'deg', 'rig.antennule.n_flag': 'count', 'rig.mxp3.yaw': 'deg', 'rig.mxp3.pitch': 'deg',
            'rig.cheliped.cutter_dactyl': 'frac', 'rig.cheliped.claw_yaw': 'deg', 'rig.cheliped.claw_pitch': 'deg',
            'rig.cheliped.claw_plane': 'deg',
            'rig.cheliped.dactyl_open': 'deg', 'rig.cheliped.hinge': 'frac', 'rig.cheliped.cutter_hinge': 'frac',
            'rig.cheliped.cutter_axis': 'deg', 'rig.cheliped.hinge_s': 'frac', 'rig.cheliped.cutter_hinge_s': 'frac',
            'rig.tip_x': 'ratio',
            'rig.rest_tip_x': 'ratio', 'rig.rest_pleopod_fold': 'deg', 'rig.rest_curl_back': 'deg',
            'rig.knee_sigma': 'deg', 'rig.az_pad': 'deg',
            **{f'rig.leg_az.{lg}': 'deg' for lg in ('P2', 'P3', 'P4', 'P5')},
            **{f'rig.ranges.{g}.{k}': 'deg' for g, d in SPEC['rig']['ranges'].items() if isinstance(d, dict) for k in d},
            **{f'rig.ranges.{g}': 'deg' for g, d in SPEC['rig']['ranges'].items() if not isinstance(d, dict)}}

# Each photos.* leaf's source: (photo id, the tracing's measure name, or a tuple of names for a tuple value); a leaf
# named *_bar is the unit's length in mm at the photo's bar (the unit's px / the scale's px_per_mm)
PHOTO_SRC = {
    'photos.M1.rostrum': ('c11', 'rostrum_from_orbit'), 'photos.M1.cervical': ('c11', 'orbit_to_cervical'),
    'photos.M1.cara_width': ('c11', 'carapace_width'), 'photos.M1.eye_spacing': ('c11', 'eye_spacing'),
    'photos.M1.cornea': ('c11', 'cornea_diam'), 'photos.M1.antscale': ('c11', 'antscale_tips_apart'),
    'photos.M1.segs': ('c11', ('T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'telson')), 'photos.M1.abdomen': ('c11', 'abdomen'),
    'photos.M1.TL': ('c11', 'TL'), 'photos.M1.abd2_w': ('c11', 'abd2_width'), 'photos.M1.abd5_w': ('c11', 'abd5_width'),
    'photos.M1.fan': ('c11', 'fan_width'), 'photos.M1.cr_len': ('c11', 'crusher_length'),
    'photos.M1.cr_palm': ('c11', 'crusher_palm_width'), 'photos.M1.cr_free': ('c11', 'crusher_finger_gape_to_tip'),
    'photos.M1.cu_len': ('c11', 'cutter_length'), 'photos.M1.cu_palm': ('c11', 'cutter_palm_width'),
    'photos.M2.rostrum': ('n03', 'rostrum_from_orbit'), 'photos.M2.cara_width': ('n03', 'carapace_width'),
    'photos.M2.cr_len': ('n03', 'crusher_length'), 'photos.M2.cr_palm': ('n03', 'crusher_palm_width'),
    'photos.M2.cu_len': ('n03', 'cutter_length'), 'photos.M2.cu_palm': ('n03', 'cutter_palm_width'),
    'photos.M2.CL_bar': ('n03', 'CL'),
    'photos.P1.cara_width': ('c03', 'carapace_width'), 'photos.P1.abd2_w': ('c03', 'abd2_width'),
    'photos.P1.fan': ('c03', 'fan_width'), 'photos.P1.abdomen': ('c03', 'abdomen'), 'photos.P1.TL': ('c03', 'TL'),
    'photos.P1.antenna_chord': ('c03', 'antenna_chord'), 'photos.P1.claw_U': ('c03', 'clawU_length'),
    'photos.P1.claw_L': ('c03', 'clawL_length'),
    'photos.P2.cervical': ('c06', 'orbit_to_cervical'), 'photos.P2.cara_depth': ('c06', 'carapace_depth'),
    'photos.P2.abd2_depth': ('c06', 'abd2_depth'), 'photos.P2.dorsum_ub': ('c06', 'dorsum_above_ground'),
    'photos.P2.margin_ub': ('c06', 'carapace_margin_above_ground'), 'photos.P2.cornea': ('c06', 'eye_diam'),
    'photos.M3.prop_bar': ('n04', 'crusher_propodus'), 'photos.M3.dactyl': ('n04', 'crusher_dactyl'),
    'photos.M3.palm': ('n04', 'crusher_palm_width'), 'photos.M3.molar_dac': ('n04', 'dactyl_molar_width'),
    'photos.M3.molar_fix': ('n04', 'fixed_molar_width'), 'photos.M3.saw': ('n04', 'cutter_saw_run'),
    'photos.M4.P4': ('n01', ('P4_merus', 'P4_carpus', 'P4_propodus', 'P4_dactyl', 'P4_coxa_to_tip')),
    'photos.M4.P5': ('n01', ('P5_merus', 'P5_carpus', 'P5_propodus', 'P5_dactyl', 'P5_coxa_to_tip')),
    'photos.M4.fan_bar': ('n01', 'fan_spread'),
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
    """a leaf's unit: mm, deg, ratio, frac, count, kg, ms, srgb8, pop (a population constant), 1 or text"""
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


# --------------------------------------------------------------------------------------------- the literature
def pope_tl(CL, sex='m', spec=None):
    """Pope 1955's stretched TL (mm) at CL (mm)"""
    a, b = (SPEC if spec is None else spec)['lit']['pope_' + sex]
    return a * CL + b


def pope_mass(TL, sex='m', spec=None):
    """Pope 1955's weight (kg) at TL (mm): log10 W(oz) = a log10 TL + b"""
    import math
    a, b = (SPEC if spec is None else spec)['lit']['weight_' + sex]
    return 10.0 ** (a * math.log10(TL) + b) * 0.0283495


def sord_cw(TL, sex='m', spec=None):
    """Sørdalen et al. 2020's crusher width (mm) at TL (mm)"""
    a, b = (SPEC if spec is None else spec)['lit']['sord_' + sex]
    return a * TL + b


# --------------------------------------------------------------------------------------------- the morphs (plan §2.8)
# Each morph: its CL (the length scale), then its measured rows (key: (value, tag, note)). morph() scales every 'mm'
# leaf outside photos / lit by CL / 100, then sets the rows. Unmeasured shape stays the scaled male's.
MORPHS = dict(
    female=dict(
        what='the female (sex, not size, sets her claws and abdomen): the crusher palm by Sørdalen\'s female line, the '
             'abdomen by Pope\'s female TL; the abdomen broader to brood eggs [E]; the first pleopods soft, not '
             'gonopods',
        CL=100.0,
        set={
            'sex': ('female', '[D]', 'the female morph'),
            'length.TL_bind': (283.2, '[L1] [D]', 'Pope\'s female stretched TL at CL 100: the bind, straight'),
            'length.abdomen': (160.589, '[D-x0 from L1]', 'Pope\'s female TL - CL - rostrum'),
            'chela.crusher_palm': (46.676, '[L6, L1]', 'Sørdalen\'s female CW = 0.18 TL - 4.3 at her TL 283.2'),
            'abdomen.w2': (48.758, '[E]', 'M1\'s somite 2 x 1.10: broader to brood eggs; gate a measured female photo'),
            'abdomen.w5': (47.408, '[E]', 'M1\'s somite 5 x 1.10'),
            'length.mass': (0.6375, '[L2]', 'Pope\'s female weight at her TL'),
        }),
    giant=dict(
        what='the giant row (M2, NHMUK 2026.19): CL 140 (its corrected 136-141 [E]); its own claws (crusher 1.27 CL, '
             'cutter 0.98) and carapace width; TL by Pope\'s male line at CL 140',
        CL=140.0,
        set={
            'chela.crusher_len': (177.681, '[P n03]', 'M2\'s 1.26915 CL x 140'),
            'chela.crusher_palm': (73.377, '[P n03]', 'M2\'s 0.52412 CL x 140'),
            'chela.cutter_len': (137.187, '[P n03]', 'M2\'s 0.97991 CL x 140'),
            'chela.cutter_palm': (53.943, '[P n03]', 'M2\'s 0.38531 CL x 140'),
            'body.cara_width': (84.827, '[P n03]', 'M2\'s 0.60591 CL x 140 (dried, flattened: an upper bound)'),
            'length.TL_bind': (376.880, '[L1] [D]', 'Pope\'s male TL at CL 140: the bind, straight'),
            'length.abdomen': (205.224, '[D-x0 from L1]', 'Pope\'s TL - CL - rostrum at CL 140 (1.466 CL: TL / CL '
                                                          'falls with size)'),
        }),
    regenerating=dict(
        what='a regenerating crusher: the left chela at x0.7 of its size [E] (x0.6-0.8); 3.4-3.8 % of males carry a '
             'regenerated crusher [L6]',
        CL=100.0,
        set={
            'chela.crusher_len': (80.737, '[E]', 'L1\'s x 0.7 (x0.6-0.8 [E]); gate a regenerating claw photo'),
            'chela.crusher_palm': (41.066, '[E]', 'L1\'s x 0.7'),
            'chela.crusher_dactyl': (36.515, '[E]', 'L1\'s x 0.7'),
        }),
    two_crushers=dict(
        what='both chelae of the crusher type (rare [L15]): the right cheliped carries the crusher\'s part',
        CL=100.0,
        set={
            'chela.cutter_len': (115.338, '[L15] [D]', 'the crusher\'s length on the right'),
            'chela.cutter_palm': (58.666, '[L15] [D]', 'the crusher\'s palm on the right'),
        }),
)


def morph(name):
    """(spec, tags): the morph's full SPEC and its tags (L1's, with the morph's rows retagged). name in MORPHS or 'L1'"""
    spec, tags = copy.deepcopy(SPEC), dict(TAGS)
    if name == 'L1':
        return spec, tags
    m = MORPHS[name]
    s = m['CL'] / SPEC['body']['CL']
    if s != 1.0:
        for key, v in leaves(SPEC):
            if unit(key) != 'mm' or key.split('.')[0] in ('photos', 'lit'):
                continue
            if isinstance(v, tuple) and v and isinstance(v[0], tuple):
                put(spec, key, tuple(tuple(x * s for x in row) for row in v))
            elif isinstance(v, tuple):
                put(spec, key, tuple(x * s for x in v))
            else:
                put(spec, key, v * s)
            tags[key] = ('[D-x0]', f'L1\'s x {s:.4f} (the morph\'s CL / L1\'s): ' + TAGS[key][1])
    for key, (v, tag, note) in m['set'].items():
        put(spec, key, v)
        tags[key] = (tag, note)
    if 'length.abdomen' in m['set']:
        # the tergites keep M1's proportions on the morph's own straight abdomen
        segs = spec['abdomen']['segs']
        k = spec['length']['abdomen'] / sum(segs)
        spec['abdomen']['segs'] = tuple(x * k for x in segs)
        tags['abdomen.segs'] = ('[D-x0 from P c11, L1]', 'M1\'s midline fractions x the morph\'s straight abdomen')
    return spec, tags
