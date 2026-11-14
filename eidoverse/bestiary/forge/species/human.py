"""HUMAN (Homo sapiens): the Bestiary's human generator, family 'hominid' (work/bestiary/research/HUMAN_PLAN.md). H0, the
SPEC: the measured tables the generator samples and the clay is judged against, every value with its source.

UNITS: millimetres, kilograms, years, degrees (the research files' units; the forge converts to metres where it builds).
Frame where one is meant: +Y up, +Z forward, +X the creature's LEFT (DESIGN.md).

WHAT IS HERE (HUMAN_PLAN §9.2 H0: "the two tables, the regressions, the residual loadings, the head means and sds, the
rules, and the skeleton proportions per sex"):
  baseline      the two baseline adults: ANSUR II's regression body at the sex's median stature and BMI 25 (B §0)
  population    the two tables: ANSUR II (soldiers: stature, log-normal BMI, BMI independent of stature) and NHANES
                2021-23 (US civilians by age decade) (B §3.1, §3.6). Sex is two tables, never pooled
  reg           per sex and ANSUR II measure: (mean, sd, a, b per mm of stature, c per BMI unit, R2, residual sd); every
                measure of a body = a + b stature + c BMI (B §3.2-3.4). The H1 pins and the head's stature regressions
  axes          the four residual shape axes (the PCA of ANSUR II's standardised residuals): share and leading loadings
                (B §3.5)
  allometry     elasticities to stature and BMI with R2 (B §3.4)
  head          per sex the head and face means and sds with their source (B §4.1); head_age the NIOSH changes with age
                (B §4.2); ear growth (Heathcote); NIOSH's two face axes (B §4.3); the NIOSH medium headform's measures
  rules         what is placed by rule, not drawn: the eyeball, the cornea, the lips, the bite, the incisor display,
                heads never scaled with the body (plan §3.3; B §5.5, §6.2-6.3)
  mouth         the crown table: every tooth to the first molar, width and depth, by sex (B §6.3; plan §2.6)
  skeleton      joint heights and segment lengths as shares of stature per sex (plan §4.1; B §5.2): the hip and knee at
                their ANSUR landmarks (see TAGS for the hip's offset and why the technician's 0.5245 was not taken), the
                rest by the technician's joint-to-landmark offsets [E: H4's regressor]
  rings         the graft rings' vertex counts on the low and the ports (plan §6.2) [D]
  budget        the plan's budgets: joints, triangles, buffers, targets, texture sets (plan §7, §8)
TAGS holds every leaf's source in HUMAN_PLAN's legend: [B §n] HUMAN_BODY_PHOTOS.md (its data files named in the note),
[S §n] HUMAN_SYSTEMS.md, [X §n] CROSSBREED_DESIGN.md, [H] house code or plans, [N] hp_numbers.json, [E] an estimate with
the round or gate that checks it, [D] a decision of the plan (its section), [P] a primary source read in H0 (named).
work/bestiary/tests/h00_spec.py prints that every leaf carries one and checks every sourced leaf against its file.
"""
import re

# ============================================================================================ the tables
# reg[sex][measure] = (mean, sd, a, b per mm stature, c per BMI unit, R2, residual sd); stature and weight_kg are the
# inputs (mean, sd). ANSUR II public working databases (1,986 F, 4,082 M), hb_ansur.py -> ansur2_stats.json
_REG_F = dict(
    stature=(1628.47, 64.20),
    weight_kg=(67.76, 10.98),
    acromialheight=(1335.10, 58.08, -112.481, 0.87710, 0.7546, 0.947, 13.41),
    axillaheight=(1239.03, 55.80, -122.448, 0.84210, -0.3865, 0.937, 14.05),
    chestheight=(1171.64, 55.50, -91.511, 0.79492, -1.2299, 0.844, 21.94),
    waistheightomphalion=(980.15, 50.02, -138.721, 0.71305, -1.6597, 0.839, 20.05),
    iliocristaleheight=(995.73, 49.69, -162.436, 0.70782, 0.2153, 0.838, 19.99),
    trochanterionheight=(845.35, 44.68, -130.961, 0.59646, 0.1961, 0.736, 22.95),
    crotchheight=(782.32, 44.64, -160.997, 0.59295, -0.8740, 0.726, 23.39),
    kneeheightmidpatella=(449.05, 25.99, -110.798, 0.34087, 0.1862, 0.712, 13.96),
    lateralfemoralepicondyleheight=(465.94, 27.14, -91.830, 0.33688, 0.3593, 0.641, 16.27),
    lateralmalleolusheight=(62.75, 5.11, 5.264, 0.03474, 0.0358, 0.192, 4.59),
    cervicaleheight=(1395.67, 59.52, -94.316, 0.91200, 0.1886, 0.969, 10.51),
    suprasternaleheight=(1329.69, 57.18, -112.389, 0.87132, 0.9081, 0.966, 10.53),
    tenthribheight=(1056.26, 50.01, -141.518, 0.73042, 0.3260, 0.882, 17.19),
    buttockheight=(833.74, 45.73, -155.881, 0.59637, 0.7238, 0.709, 24.68),
    sittingheight=(856.63, 33.05, 216.007, 0.39352, -0.0085, 0.584, 21.33),
    wristheight=(794.19, 38.19, -49.668, 0.50598, 0.7800, 0.735, 19.67),
    tragiontopofhead=(126.48, 6.55, 84.760, 0.02148, 0.2643, 0.067, 6.33),
    neckcircumference=(329.80, 19.22, 104.231, 0.07661, 3.9541, 0.601, 12.14),
    neckcircumferencebase=(371.16, 19.66, 95.556, 0.11569, 3.4204, 0.537, 13.39),
    chestcircumference=(946.86, 82.70, 0.098, 0.27724, 19.4259, 0.738, 42.34),
    waistcircumference=(860.91, 99.93, -221.893, 0.28544, 24.2377, 0.768, 48.20),
    buttockcircumference=(1021.25, 75.89, -87.925, 0.39391, 18.3441, 0.854, 29.04),
    thighcircumference=(616.15, 55.81, -116.236, 0.23478, 13.7296, 0.836, 22.62),
    lowerthighcircumference=(400.71, 35.16, -49.277, 0.15386, 7.8219, 0.706, 19.08),
    calfcircumference=(373.26, 28.52, 2.213, 0.13468, 5.9509, 0.647, 16.95),
    anklecircumference=(215.74, 14.89, 33.350, 0.07926, 2.0912, 0.375, 11.78),
    bicepscircumferenceflexed=(305.58, 30.76, -44.370, 0.09648, 7.5632, 0.796, 13.88),
    forearmcircumferenceflexed=(264.08, 18.52, 14.754, 0.09135, 3.9444, 0.679, 10.50),
    wristcircumference=(154.79, 7.83, 23.722, 0.06294, 1.1210, 0.544, 5.29),
    handcircumference=(186.55, 8.82, 62.557, 0.06216, 0.8932, 0.347, 7.13),
    shouldercircumference=(1028.19, 52.92, 167.947, 0.36739, 10.2742, 0.691, 29.44),
    biacromialbreadth=(365.35, 18.30, 82.493, 0.15833, 0.9814, 0.355, 14.71),
    bideltoidbreadth=(450.32, 28.69, 53.667, 0.14115, 6.5423, 0.761, 14.03),
    chestbreadth=(269.33, 18.58, 37.617, 0.09044, 3.3118, 0.506, 13.07),
    waistbreadth=(299.89, 32.96, -84.426, 0.11928, 7.4551, 0.698, 18.13),
    hipbreadth=(353.84, 26.67, -24.702, 0.14427, 5.6319, 0.692, 14.81),
    bicristalbreadth=(273.30, 22.26, -19.625, 0.12293, 3.6375, 0.473, 16.17),
    chestdepth=(247.40, 27.34, -41.898, 0.07948, 6.2705, 0.692, 15.17),
    waistdepth=(213.03, 31.37, -66.184, 0.05387, 7.5104, 0.721, 16.59),
    buttockdepth=(232.93, 24.33, -39.146, 0.07401, 5.9439, 0.784, 11.32),
    acromionradialelength=(311.20, 17.16, -44.742, 0.21046, 0.5181, 0.640, 10.31),
    radialestylionlength=(241.33, 15.24, -30.842, 0.16232, 0.3076, 0.478, 11.02),
    handlength=(181.08, 10.06, 6.449, 0.09984, 0.4725, 0.444, 7.50),
    handbreadth=(78.15, 3.84, 25.607, 0.02736, 0.3136, 0.304, 3.21),
    footlength=(246.29, 12.44, 5.347, 0.13802, 0.6351, 0.553, 8.32),
    footbreadthhorizontal=(92.71, 4.78, 32.599, 0.02924, 0.4904, 0.298, 4.01),
    span=(1660.29, 82.97, -100.376, 1.05336, 1.7763, 0.676, 47.22),
    headcircumference=(561.12, 19.36, 378.849, 0.09090, 1.3432, 0.157, 17.78),
    headlength=(189.82, 7.45, 113.785, 0.04033, 0.4061, 0.164, 6.81),
    headbreadth=(147.77, 5.19, 121.716, 0.01186, 0.2643, 0.056, 5.05),
    bizygomaticbreadth=(133.77, 5.56, 94.790, 0.01463, 0.5940, 0.174, 5.06),
    mentonsellionlength=(113.09, 6.09, 60.054, 0.02725, 0.3400, 0.127, 5.69),
    interpupillarybreadth=(61.71, 3.62, 39.839, 0.01080, 0.1677, 0.066, 3.50),
    earlength=(59.36, 3.88, 34.071, 0.01244, 0.1975, 0.078, 3.73),
    earbreadth=(33.22, 2.77, 21.456, 0.00595, 0.0813, 0.031, 2.73),
    earprotrusion=(20.39, 2.66, 16.354, 0.00282, -0.0216, 0.005, 2.65),
    bitragionchinarc=(311.01, 14.16, 159.527, 0.06748, 1.6314, 0.269, 12.12),
    bitragionsubmandibulararc=(287.98, 15.30, 123.012, 0.06902, 2.0618, 0.320, 12.62),
)
_REG_M = dict(
    stature=(1756.21, 68.55),
    weight_kg=(85.52, 14.22),
    acromialheight=(1440.74, 63.29, -162.340, 0.89245, 1.2907, 0.942, 15.30),
    axillaheight=(1329.08, 59.52, -140.876, 0.84133, -0.2743, 0.939, 14.66),
    chestheight=(1291.12, 56.96, -93.591, 0.78757, 0.0565, 0.899, 18.15),
    waistheightomphalion=(1056.49, 52.15, -110.329, 0.69139, -1.7123, 0.843, 20.68),
    iliocristaleheight=(1061.63, 52.02, -137.508, 0.69017, -0.4676, 0.828, 21.55),
    trochanterionheight=(900.93, 49.17, -150.632, 0.60984, -0.7026, 0.726, 25.75),
    crotchheight=(845.93, 46.50, -143.001, 0.58223, -1.2129, 0.747, 23.37),
    kneeheightmidpatella=(488.39, 28.13, -111.123, 0.34194, -0.0368, 0.695, 15.55),
    lateralfemoralepicondyleheight=(491.66, 26.58, -89.466, 0.33301, -0.1338, 0.738, 13.61),
    lateralmalleolusheight=(72.90, 5.67, -1.810, 0.03864, 0.2473, 0.250, 4.91),
    cervicaleheight=(1517.30, 63.28, -100.385, 0.90834, 0.8105, 0.971, 10.74),
    suprasternaleheight=(1438.59, 61.25, -132.282, 0.87677, 1.1225, 0.969, 10.82),
    tenthribheight=(1120.67, 53.61, -165.232, 0.72356, 0.5479, 0.858, 20.21),
    buttockheight=(887.87, 49.92, -154.720, 0.60155, -0.5006, 0.684, 28.07),
    sittingheight=(918.29, 35.70, 194.998, 0.40565, 0.3931, 0.609, 22.33),
    wristheight=(847.51, 41.66, -116.239, 0.52015, 1.8151, 0.764, 20.23),
    tragiontopofhead=(131.15, 6.16, 96.440, 0.01783, 0.1226, 0.046, 6.02),
    neckcircumference=(397.65, 25.78, 129.350, 0.07275, 5.0761, 0.671, 14.79),
    neckcircumferencebase=(434.60, 25.67, 126.209, 0.10327, 4.5879, 0.598, 16.28),
    chestcircumference=(1058.71, 87.44, -29.063, 0.31314, 19.4255, 0.867, 31.94),
    waistcircumference=(940.58, 111.71, -335.248, 0.33570, 24.7873, 0.847, 43.75),
    buttockcircumference=(1019.52, 76.68, -105.119, 0.37784, 16.6531, 0.885, 26.02),
    thighcircumference=(625.14, 58.45, -109.597, 0.21612, 12.8292, 0.851, 22.55),
    lowerthighcircumference=(409.29, 31.87, -16.580, 0.13882, 6.5759, 0.785, 14.79),
    calfcircumference=(392.26, 29.71, 28.388, 0.11452, 5.8783, 0.710, 16.02),
    anklecircumference=(229.34, 14.65, 28.472, 0.07856, 2.2722, 0.529, 10.06),
    bicepscircumferenceflexed=(358.14, 34.62, -4.501, 0.09596, 7.0111, 0.706, 18.77),
    forearmcircumferenceflexed=(310.06, 21.99, 27.748, 0.09611, 4.1000, 0.658, 12.87),
    wristcircumference=(175.92, 8.96, 29.364, 0.06385, 1.2432, 0.555, 5.98),
    handcircumference=(212.28, 10.24, 60.295, 0.06935, 1.0909, 0.401, 7.93),
    shouldercircumference=(1178.59, 63.59, 215.412, 0.35814, 12.0712, 0.738, 32.53),
    biacromialbreadth=(415.68, 19.16, 104.285, 0.14841, 1.8330, 0.432, 14.44),
    bideltoidbreadth=(510.42, 32.51, 65.430, 0.14756, 6.7127, 0.794, 14.76),
    chestbreadth=(289.44, 18.28, 52.126, 0.09078, 2.8134, 0.503, 12.89),
    waistbreadth=(326.44, 34.74, -97.098, 0.12533, 7.3477, 0.792, 15.84),
    hipbreadth=(345.73, 24.17, -16.348, 0.13461, 4.5392, 0.723, 12.73),
    bicristalbreadth=(275.43, 17.51, -10.240, 0.12928, 2.1173, 0.496, 12.44),
    chestdepth=(253.85, 26.25, -46.799, 0.08360, 5.5560, 0.780, 12.32),
    waistdepth=(237.77, 34.73, -106.234, 0.07848, 7.4471, 0.775, 16.49),
    buttockdepth=(245.85, 26.46, -58.534, 0.08212, 5.7850, 0.826, 11.04),
    acromionradialelength=(335.24, 17.48, -27.273, 0.20279, 0.2304, 0.635, 10.56),
    radialestylionlength=(267.88, 15.42, -15.883, 0.16075, 0.0527, 0.511, 10.78),
    handlength=(193.28, 9.95, 13.452, 0.09764, 0.3018, 0.468, 7.26),
    handbreadth=(88.26, 4.39, 25.020, 0.02980, 0.3940, 0.349, 3.54),
    footlength=(271.18, 13.10, 15.146, 0.13719, 0.5456, 0.544, 8.85),
    footbreadthhorizontal=(101.86, 5.23, 27.179, 0.03430, 0.5218, 0.365, 4.17),
    span=(1814.15, 84.63, -10.239, 1.01605, 1.4445, 0.682, 47.72),
    headcircumference=(574.37, 16.05, 391.009, 0.08000, 1.5480, 0.269, 13.72),
    headlength=(199.50, 7.02, 121.293, 0.03777, 0.4291, 0.197, 6.30),
    headbreadth=(154.33, 5.53, 130.825, 0.00600, 0.4685, 0.123, 5.18),
    bizygomaticbreadth=(142.62, 6.22, 97.597, 0.01277, 0.8160, 0.301, 5.20),
    mentonsellionlength=(122.64, 6.67, 63.641, 0.02939, 0.2669, 0.118, 6.26),
    interpupillarybreadth=(64.02, 3.42, 43.049, 0.00898, 0.1877, 0.082, 3.28),
    earlength=(64.21, 4.51, 33.718, 0.01267, 0.2978, 0.109, 4.26),
    earbreadth=(36.06, 3.02, 23.075, 0.00591, 0.0941, 0.034, 2.97),
    earprotrusion=(23.17, 3.00, 21.940, 0.00057, 0.0083, 0.000, 3.00),
    bitragionchinarc=(331.65, 14.04, 173.001, 0.06013, 1.9160, 0.391, 10.96),
    bitragionsubmandibulararc=(315.71, 16.65, 134.241, 0.06193, 2.6263, 0.472, 12.10),
)

SPEC = dict(
    family='hominid', stance='biped', sexes=('F', 'M'),
    # ---- the two baseline adults (B §0, §3.2)
    baseline=dict(F=dict(stature=1626.0, bmi=25.0, mass=66.1, age=29.0),
                  M=dict(stature=1755.0, bmi=25.0, mass=77.0, age=30.0)),
    # ---- the two population tables (B §3.1, §3.6)
    population=dict(
        ansur=dict(
            F=dict(n=1986, age=(17.0, 58.0, 28.9), stature=(1628.47, 64.20),
                   stature_pct=(1482.5, 1525.0, 1626.0, 1740.0, 1777.6), stature_range=(1409.0, 1829.0),
                   mass=(67.76, 51.3, 87.07), log_bmi=(3.2293, 0.1354),
                   bmi_pct=(25.50, 20.26, 25.27, 31.66, 34.82), bmi_max=40.78, r_stature_bmi=0.054),
            M=dict(n=4082, age=(17.0, 58.0, 30.2), stature=(1756.21, 68.55),
                   stature_pct=(1601.6, 1648.0, 1755.0, 1870.0, 1927.0), stature_range=(1491.0, 1993.0),
                   mass=(85.52, 64.4, 110.69), log_bmi=(3.3103, 0.1458),
                   bmi_pct=(27.69, 21.40, 27.46, 34.80, 38.19), bmi_max=43.45, r_stature_bmi=0.002)),
        # NHANES 2021-23, survey weighted: per decade (mean, p5, p50, p95); '20+' = 20 and older; a percentile the report
        # leaves blank (too few people in the cell) is None
        nhanes=dict(
            F=dict(stature_cm={'20+': (161.2, 149.6, 161.2, 172.5), '20-29': (163.5, 153.2, 163.3, 174.6),
                               '30-39': (162.5, 150.1, 162.8, 172.9), '40-49': (161.7, 149.8, 162.0, 172.1),
                               '50-59': (161.2, 150.4, 160.8, 172.4), '60-69': (160.5, 149.6, 160.4, 171.2),
                               '70-79': (158.3, 148.6, 157.9, 168.2), '80+': (156.8, 143.7, 156.9, None)},
                   bmi={'20+': (30.0, 19.7, 28.3, 44.9), '20-29': (28.0, 18.6, 25.5, 45.6), '30-39': (30.5, 19.7, 28.6, 47.4),
                        '40-49': (30.7, 19.7, 28.5, 45.6), '50-59': (31.4, 20.8, 30.0, 45.9), '60-69': (30.1, 20.0, 28.8, 42.5),
                        '70-79': (29.5, 20.7, 28.0, 42.2), '80+': (27.7, 19.2, 26.9, 36.3)},
                   waist_cm={'20+': (97.9, 73.8, 95.7, 129.2), '20-29': (90.5, 68.5, 85.3, 127.3),
                             '30-39': (97.8, 72.6, 93.1, 133.6), '40-49': (98.2, 75.3, 95.7, 130.8),
                             '50-59': (101.5, 77.7, 100.8, 130.8), '60-69': (100.3, 77.1, 99.6, 125.5),
                             '70-79': (99.6, 76.7, 98.9, 123.7), '80+': (96.5, 76.4, 94.4, 119.1)},
                   hip_cm={'20+': (109.8, 89.7, 106.8, 138.4), '20-29': (107.0, 87.1, 104.4, 135.7),
                           '30-39': (111.6, 91.0, 108.1, 142.0), '40-49': (111.1, 90.3, 107.4, 139.7),
                           '50-59': (111.5, 90.1, 108.3, 139.2), '60-69': (110.1, 88.9, 108.0, 137.3),
                           '70-79': (108.6, 89.4, 106.4, 134.4), '80+': (104.7, 87.7, 103.1, None)},
                   upper_leg_cm={'20+': (36.8, 31.9, 36.9, 41.4), '20-29': (38.4, 34.3, 38.2, 42.4),
                                 '30-39': (37.6, 32.9, 37.6, 42.2), '40-49': (37.1, 32.7, 37.2, 41.2),
                                 '50-59': (36.4, 31.6, 36.5, 40.9), '60-69': (36.0, 31.2, 36.2, 40.2),
                                 '70-79': (35.4, 31.2, 35.5, 39.5), '80+': (35.3, 30.2, 35.1, 40.0)},
                   mass_kg={'20+': (77.9, 50.7, 73.5, 119.2), '20-29': (74.8, 47.6, 68.9, 121.3),
                            '30-39': (80.9, 51.4, 75.0, 125.9), '40-49': (80.4, 52.8, 74.8, 123.7),
                            '50-59': (81.6, 53.1, 78.5, 121.4), '60-69': (77.5, 51.6, 74.3, 109.3),
                            '70-79': (73.8, 49.8, 71.7, 103.5), '80+': (67.9, 46.8, 65.7, 94.2)}),
            M=dict(stature_cm={'20+': (175.1, 162.2, 175.2, 187.2), '20-29': (176.3, 162.0, 176.1, 188.1),
                               '30-39': (176.1, 163.6, 176.4, 187.1), '40-49': (176.4, 162.3, 176.2, 189.9),
                               '50-59': (174.3, 163.0, 174.5, 185.6), '60-69': (174.7, 161.8, 175.0, 186.6),
                               '70-79': (172.4, 159.5, 172.7, 184.1), '80+': (170.5, 158.3, 169.9, None)},
                   bmi={'20+': (29.4, 20.9, 28.2, 42.1), '20-29': (27.8, 18.9, 27.0, 39.6), '30-39': (29.5, 21.2, 27.8, 42.5),
                        '40-49': (30.5, 22.2, 28.9, 45.0), '50-59': (30.2, 21.6, 29.0, 44.6), '60-69': (29.2, 21.2, 28.3, 39.9),
                        '70-79': (29.4, 21.6, 28.8, 39.2), '80+': (27.8, 21.1, 27.2, 34.8)},
                   waist_cm={'20+': (103.0, 79.3, 100.9, 133.2), '20-29': (95.1, 71.3, 93.4, 124.4),
                             '30-39': (101.3, 80.3, 98.6, 130.5), '40-49': (104.7, 83.7, 101.5, 139.6),
                             '50-59': (106.4, 83.2, 104.3, 137.0), '60-69': (105.4, 84.2, 104.5, 132.2),
                             '70-79': (107.5, 84.6, 106.6, 131.3), '80+': (104.1, 84.5, 102.6, 126.0)},
                   hip_cm={'20+': (105.6, 89.5, 103.6, 129.1), '20-29': (104.5, 87.0, 103.0, 127.8),
                           '30-39': (106.3, 91.0, 104.7, 127.6), '40-49': (107.4, 92.1, 104.3, 133.8),
                           '50-59': (106.2, 89.7, 103.7, 134.8), '60-69': (104.2, 89.5, 103.0, 123.6),
                           '70-79': (105.0, 90.0, 103.2, 126.1), '80+': (102.5, 90.3, 101.4, 123.0)},
                   upper_leg_cm={'20+': (41.0, 35.8, 41.0, 45.9), '20-29': (42.3, 38.1, 42.0, 46.4),
                                 '30-39': (41.9, 37.5, 41.7, 46.2), '40-49': (41.3, 36.0, 41.4, 45.9),
                                 '50-59': (40.4, 35.4, 40.3, 45.1), '60-69': (40.4, 35.0, 40.5, 45.1),
                                 '70-79': (39.4, 34.4, 39.4, 43.7), '80+': (39.4, None, 39.7, 43.7)},
                   mass_kg={'20+': (90.3, 60.9, 86.6, 131.8), '20-29': (86.8, 57.0, 83.7, 128.3),
                            '30-39': (91.4, 63.6, 87.1, 132.5), '40-49': (95.3, 66.0, 88.4, 141.9),
                            '50-59': (92.1, 61.0, 87.8, 138.7), '60-69': (89.2, 62.6, 86.9, 123.9),
                            '70-79': (87.7, 60.8, 86.6, 121.3), '80+': (81.7, 58.0, 79.9, 108.5)})),
        default='us_civilian'),
    # ---- the regressions (B §3.2-3.4)
    reg=dict(F=_REG_F, M=_REG_M),
    # ---- the four residual shape axes (B §3.5): share of the standardised residual variance, leading loadings
    axes=dict(
        F=dict(leg_trunk=dict(share=0.2014, loadings=(('sittingheight', -0.199), ('crotchheight', 0.198),
                                                      ('kneeheightsitting', 0.197), ('forearmhandlength', 0.193),
                                                      ('eyeheightsitting', -0.191), ('trochanterionheight', 0.184),
                                                      ('tibialheight', 0.183), ('kneeheightmidpatella', 0.183),
                                                      ('buttockheight', 0.183), ('span', 0.181))),
               robust=dict(share=0.0848, loadings=(('balloffootcircumference', 0.221), ('handcircumference', 0.212),
                                                   ('wristcircumference', 0.208), ('footbreadthhorizontal', 0.195),
                                                   ('heelanklecircumference', 0.195), ('bimalleolarbreadth', 0.194),
                                                   ('handbreadth', 0.191), ('anklecircumference', 0.159),
                                                   ('waistcircumference', -0.158), ('biacromialbreadth', 0.156))),
               mass_upper=dict(share=0.0774, loadings=(('lowerthighcircumference', -0.245), ('chestcircumference', 0.242),
                                                       ('thighcircumference', -0.232), ('waistcircumference', 0.23),
                                                       ('calfcircumference', -0.207), ('bideltoidbreadth', 0.2),
                                                       ('waistdepth', 0.199), ('chestdepth', 0.189),
                                                       ('chestbreadth', 0.188), ('crotchlengthomphalion', -0.185))),
               shoulder=dict(share=0.0447, loadings=(('wristheight', 0.281), ('shoulderlength', -0.253),
                                                     ('biacromialbreadth', -0.219), ('buttockcircumference', -0.211),
                                                     ('overheadfingertipreachsitting', -0.207), ('acromialheight', 0.193),
                                                     ('hipbreadthsitting', -0.189), ('sleevelengthspinewrist', -0.188),
                                                     ('span', -0.182), ('thighcircumference', -0.179))),
               cumulative_12=0.6237),
        M=dict(leg_trunk=dict(share=0.1821, loadings=(('sittingheight', -0.209), ('crotchheight', 0.2),
                                                      ('kneeheightsitting', 0.199), ('eyeheightsitting', -0.198),
                                                      ('forearmhandlength', 0.192), ('poplitealheight', 0.191),
                                                      ('lateralfemoralepicondyleheight', 0.184),
                                                      ('kneeheightmidpatella', 0.184), ('trochanterionheight', 0.178),
                                                      ('radialestylionlength', 0.177))),
               robust=dict(share=0.0876, loadings=(('waistcircumference', -0.23), ('waistdepth', -0.212),
                                                   ('abdominalextensiondepthsitting', -0.196),
                                                   ('balloffootcircumference', 0.195), ('handcircumference', 0.195),
                                                   ('wristcircumference', 0.182), ('handbreadth', 0.181),
                                                   ('waistbreadth', -0.176), ('bimalleolarbreadth', 0.176),
                                                   ('footbreadthhorizontal', 0.176))),
               mass_upper=dict(share=0.0635, loadings=(('chestcircumference', 0.275), ('thighcircumference', -0.26),
                                                       ('lowerthighcircumference', -0.234), ('shouldercircumference', 0.229),
                                                       ('bideltoidbreadth', 0.227), ('interscyei', 0.22),
                                                       ('buttockcircumference', -0.217), ('interscyeii', 0.215),
                                                       ('neckcircumference', 0.202), ('neckcircumferencebase', 0.195))),
               shoulder=dict(share=0.046, loadings=(('shouldercircumference', -0.22), ('thighcircumference', -0.215),
                                                    ('bideltoidbreadth', -0.21), ('biacromialbreadth', -0.204),
                                                    ('shoulderlength', -0.198), ('waistbacklength', 0.19),
                                                    ('waistdepth', 0.188), ('handcircumference', 0.184),
                                                    ('buttockcircumference', -0.176), ('handbreadth', 0.174))),
               cumulative_12=0.6046)),
    # ---- elasticities (B §3.4): measure -> (to stature, to BMI, R2)
    allometry=dict(
        F=dict(kneeheightmidpatella=(1.236, 0.011, 0.712), crotchheight=(1.234, -0.028, 0.726),
               acromialheight=(1.070, 0.014, 0.947), span=(1.033, 0.027, 0.676), footlength=(0.913, 0.066, 0.553),
               handlength=(0.898, 0.067, 0.444), sittingheight=(0.748, -0.000, 0.584),
               biacromialbreadth=(0.706, 0.068, 0.355), hipbreadth=(0.664, 0.406, 0.692),
               buttockcircumference=(0.628, 0.458, 0.854), thighcircumference=(0.621, 0.568, 0.836),
               waistcircumference=(0.540, 0.718, 0.768), chestcircumference=(0.477, 0.523, 0.738),
               neckcircumference=(0.378, 0.306, 0.601), mentonsellionlength=(0.392, 0.077, 0.127),
               headlength=(0.346, 0.055, 0.164), earlength=(0.341, 0.085, 0.078),
               interpupillarybreadth=(0.285, 0.069, 0.066), headcircumference=(0.264, 0.061, 0.157),
               bizygomaticbreadth=(0.178, 0.113, 0.174), headbreadth=(0.131, 0.046, 0.056)),
        M=dict(kneeheightmidpatella=(1.230, -0.002, 0.695), crotchheight=(1.209, -0.040, 0.747),
               acromialheight=(1.088, 0.025, 0.942), span=(0.984, 0.022, 0.682), footlength=(0.888, 0.056, 0.544),
               handlength=(0.887, 0.043, 0.468), sittingheight=(0.776, 0.012, 0.609),
               biacromialbreadth=(0.627, 0.122, 0.432), hipbreadth=(0.684, 0.363, 0.723),
               buttockcircumference=(0.651, 0.452, 0.885), thighcircumference=(0.607, 0.568, 0.851),
               waistcircumference=(0.627, 0.730, 0.847), chestcircumference=(0.519, 0.508, 0.867),
               neckcircumference=(0.321, 0.353, 0.671), mentonsellionlength=(0.421, 0.060, 0.118),
               headlength=(0.332, 0.060, 0.197), earlength=(0.347, 0.128, 0.109),
               interpupillarybreadth=(0.246, 0.081, 0.082), headcircumference=(0.245, 0.075, 0.269),
               bizygomaticbreadth=(0.157, 0.158, 0.301), headbreadth=(0.068, 0.084, 0.123))),
    # ---- the head (B §4.1): (mean, sd, source); ANSUR II first, then NIOSH, then Farkas (NAW 18-25)
    head=dict(
        F=dict(head_length=(189.82, 7.45, 'ansur'), head_breadth=(147.77, 5.19, 'ansur'),
               head_circumference=(561.12, 19.36, 'ansur'), tragion_top_of_head=(126.48, 6.55, 'ansur'),
               bitragion_coronal_arc=(341.05, 15.59, 'niosh'), bitragion_chin_arc=(311.01, 14.16, 'ansur'),
               face_width=(133.77, 5.56, 'ansur'), jaw_width=(111.64, 9.27, 'niosh'),
               face_length=(113.09, 6.09, 'ansur'), nose_length=(47.68, 3.81, 'niosh'),
               nose_breadth=(35.81, 4.92, 'niosh'), nose_protrusion=(18.94, 2.68, 'niosh'),
               mouth_width=(49.15, 4.47, 'niosh'), interpupillary=(61.71, 3.62, 'ansur'),
               intercanthal=(31.6, 2.4, 'farkas'), biocular=(86.8, 4.0, 'farkas'), upper_face=(68.1, 3.4, 'farkas'),
               lower_face=(65.5, 4.5, 'farkas'), upper_lip=(19.6, 2.4, 'farkas'),
               upper_vermilion=(None, None, 'farkas'), lower_vermilion=(9.7, 1.6, 'farkas'),
               ear_length=(59.36, 3.88, 'ansur'), ear_breadth=(33.22, 2.77, 'ansur'),
               ear_protrusion=(20.39, 2.66, 'ansur')),
        M=dict(head_length=(199.50, 7.02, 'ansur'), head_breadth=(154.33, 5.53, 'ansur'),
               head_circumference=(574.37, 16.05, 'ansur'), tragion_top_of_head=(131.15, 6.16, 'ansur'),
               bitragion_coronal_arc=(350.74, 14.09, 'niosh'), bitragion_chin_arc=(331.65, 14.04, 'ansur'),
               face_width=(142.62, 6.22, 'ansur'), jaw_width=(120.70, 10.70, 'niosh'),
               face_length=(122.64, 6.67, 'ansur'), nose_length=(51.88, 4.12, 'niosh'),
               nose_breadth=(37.81, 4.80, 'niosh'), nose_protrusion=(20.80, 2.75, 'niosh'),
               mouth_width=(51.65, 4.27, 'niosh'), interpupillary=(64.02, 3.42, 'ansur'),
               intercanthal=(32.9, 2.7, 'farkas'), biocular=(89.4, 3.6, 'farkas'), upper_face=(74.0, 4.2, 'farkas'),
               lower_face=(71.9, 6.0, 'farkas'), upper_lip=(21.8, 2.0, 'farkas'),
               upper_vermilion=(8.9, 1.5, 'farkas'), lower_vermilion=(10.4, 1.9, 'farkas'),
               ear_length=(64.21, 4.51, 'ansur'), ear_breadth=(36.06, 3.02, 'ansur'),
               ear_protrusion=(23.17, 3.00, 'ansur'))),
    # NIOSH: the change from 18-29 at 30-44 and at 45-66, race groups as covariates (B §4.2)
    head_age=dict(
        F=dict(nose_breadth=(0.59, 2.08), mouth_width=(1.63, 2.40), nose_length=(0.32, 1.23), face_length=(0.52, 1.08),
               face_width=(0.85, 1.09), jaw_width=(2.42, 3.51), bitragion_chin_arc=(2.37, 3.37),
               neck_circumference=(16.10, 20.20), interpupillary=(0.46, 1.13), head_breadth=(-0.12, 0.71),
               head_length=(-1.18, -1.07), head_circumference=(-1.36, -1.54)),
        M=dict(nose_breadth=(0.77, 2.40), mouth_width=(1.54, 2.68), nose_length=(1.25, 2.28), face_length=(2.26, 3.51),
               face_width=(1.25, 3.32), jaw_width=(1.94, 4.02), bitragion_chin_arc=(5.00, 8.56),
               neck_circumference=(11.85, 18.60), interpupillary=(1.14, 1.92), head_breadth=(0.85, 2.12),
               head_length=(0.89, 0.30), head_circumference=(2.64, 3.30))),
    ear_growth=dict(intercept=55.9, per_year=0.22, ci95=(0.17, 0.27)),
    niosh_pca=dict(
        pc1_size=(('min_frontal_breadth', 0.343), ('face_width', 0.426), ('bigonial', 0.373), ('face_length', 0.330),
                  ('interpupillary', 0.363), ('head_breadth', 0.372), ('nose_protrusion', 0.114),
                  ('nose_breadth', 0.301), ('nasal_root_breadth', 0.202), ('nose_length', 0.194)),
        pc2_long_narrow=(('face_length', 0.360), ('nose_protrusion', 0.552), ('nose_length', 0.584),
                         ('nose_breadth', -0.211), ('nasal_root_breadth', -0.341))),
    headform=dict(length=194.0, breadth=152.2, breadth_ears=172.7, vertex_menton=226.0, sellion_menton=122.0,
                  nose_projection=21.3),
    # ---- the rules (plan §3.3)
    rules=dict(
        eyeball=dict(transverse=(24.156, 1.9), range=(21.5, 26.8), sagittal=(23.799, 1.6), axial=(23.42, 1.9)),
        cornea=dict(white_to_white=(11.71, 0.42), radius=(7.81, 7.66), thickness=0.558),
        lips=dict(lower_at_least_upper=True, lower_vermilion=(9.7, 10.4), upper_vermilion_m=8.9),
        bite=dict(overbite=2.9, overjet=3.5, overjet_6mm_share=0.10),
        incisor_display=dict(F=3.40, M=1.91, by_age=((29.0, 3.31), (39.0, 1.58), (49.0, 0.95), (59.0, 0.46),
                                                     (60.0, 0.04))),
        head_not_scaled=True),
    # ---- the crown table (B §6.3): tooth -> (mesiodistal F, M; buccolingual F, M), maxilla and mandible
    mouth=dict(
        upper=dict(central_incisor=(8.772, 8.984, 7.354, 7.697), lateral_incisor=(6.933, 7.081, 6.641, 6.945),
                   canine=(7.922, 8.202, 7.895, 8.351), first_premolar=(7.289, 7.412, 9.250, 9.588),
                   second_premolar=(7.055, 7.150, 9.431, 9.786), first_molar=(10.282, 10.567, 11.313, 11.809)),
        lower=dict(central_incisor=(5.659, 5.727, 6.118, 6.392), lateral_incisor=(6.073, 6.302, 6.477, 6.618),
                   canine=(6.798, 7.154, 7.283, 7.670), first_premolar=(7.311, 7.418, 7.820, 8.161),
                   second_premolar=(7.420, 7.600, 8.580, 8.898), first_molar=(11.085, 11.444, 10.616, 11.018)),
        upper_central_crown_length=(9.20, 10.25)),
    # ---- the skeleton (plan §4.1; B §5.2): shares of stature
    skeleton=dict(
        F=dict(hip=0.51536, knee=0.28604, ankle=0.05435, shoulder=0.79620, neck_01=0.82880, head=0.91033,
               upper_arm=0.16056, forearm=0.14317, hips_apart=0.10326, shoulders_apart=0.20109),
        M=dict(hip=0.51234, knee=0.27987, ankle=0.05733, shoulder=0.79670, neck_01=0.83574, head=0.91331,
               upper_arm=0.16036, forearm=0.14752, hips_apart=0.09356, shoulders_apart=0.21217),
        hjc_below_trochanterion_mm=dict(F=5.9, M=0.9),
        technician=dict(hip=0.52446, knee=0.28804, thigh=0.23780)),
    # ---- the graft rings: vertices on the low (plan §6.2)
    rings=dict(neck=48, shoulder=32, elbow=32, wrist=24, hip=48, knee=32, ankle=24, waist=64, back_limb=24,
               back_shell=32, tail=16, horn=16, gill=12, ear=24, scalp=(12, 16), back_ports=4, gill_ports=6,
               nail_collars=20),
    # ---- budgets (plan §7, §8; hp_numbers.json)
    budget=dict(joints_body=94, joints_face_v1=40, joints_face_v2=82, joints_max=256, influences=4,
                vertex_buffers=7, morph_targets=32, tris_lod0=75300, tris_hero=150000,
                head_cage_quads=2600, body_cage_quads=3300,
                sets=dict(HEAD=4096, BODY=4096, EYES=1024, MOUTH=1024, HAIR=2048)),
)

REGIONS = ('head', 'face', 'ear', 'neck', 'trunk', 'arm', 'hand', 'leg', 'foot', 'mouth', 'eye', 'nail')
REGION_ID = {name: i for i, name in enumerate(REGIONS)}

# ============================================================================================ the sources
_B = 'research/human_work/data/'
TAGS = {
    'family': ('[D §6.1]', 'a new base family, hominid, with its own generator (plan §0 item 1, §6.1)'),
    'stance': ('[D §6.1]', 'stance biped (plan §6.1); humans move through the eidoverse VRM controller (decision 2)'),
    'sexes': ('[B §0] [D §3.1]', 'two tables, never pooled (the ANSUR II memorandum, para 7)'),
    'population.default': ('[D §3.4]', '"population is US civilian by default: NHANES draws stature and BMI by age, ANSUR '
                                       'shapes the body"'),
    'ear_growth.intercept': ('[B §3.6] [B §4.2]', 'Heathcote 1995 (BMJ, n 206, 30-93 y): ear length = 55.9 + 0.22 age mm; '
                                                  + _B + 'literature_values.json ageing.ear_length'),
    'ear_growth.per_year': ('[B §4.2]', 'Heathcote 1995: 0.22 mm a year (95 % CI 0.17-0.27)'),
    'ear_growth.ci95': ('[B §4.2]', 'Heathcote 1995'),
    'headform.length': ('[B §4.3]', 'the NIOSH ISO medium headform, measured by hb_headform.py (niosh_headform_medium.json)'),
    'headform.breadth': ('[B §4.3]', 'above the ears'),
    'headform.breadth_ears': ('[B §4.3]', 'across the ears'),
    'headform.vertex_menton': ('[B §4.3]', 'about 226 (2 mm sampling, a smooth averaged chin)'),
    'headform.sellion_menton': ('[B §4.3]', ''),
    'headform.nose_projection': ('[B §4.3]', 'ahead of sellion'),
    'niosh_pca.pc1_size': ('[B §4.3]', 'NIOSH methods PDF: PC1, overall size'),
    'niosh_pca.pc2_long_narrow': ('[B §4.3]', 'NIOSH methods PDF: PC2, long-narrow against short-wide, with nose shape'),
    'rules.eyeball.transverse': ('[B §6.2] [D §3.3]', 'Bekerman et al. 2014 (CT, 250 adults 18-93; right eye; no sex or age '
                                                      'difference): 24.156 (1.9); "Eyeballs are 24.2 mm at every adult size"'),
    'rules.eyeball.range': ('[B §6.2] [D §3.3]', 'Bekerman 2014: 21.5-26.8; identities draw inside it'),
    'rules.eyeball.sagittal': ('[B §6.2]', 'Bekerman 2014'),
    'rules.eyeball.axial': ('[B §6.2]', 'Bekerman 2014, emmetropes'),
    'rules.cornea.white_to_white': ('[B §6.2]', 'Rüfer et al. 2005 (n 390), via a search summary'),
    'rules.cornea.radius': ('[B §6.2]', 'LIFE-Adult abstract: anterior radius flat / steep'),
    'rules.cornea.thickness': ('[B §6.2]', 'LIFE-Adult abstract: central thickness 558 um'),
    'rules.lips.lower_at_least_upper': ('[B §5.5] [D §3.3]', '"The lower vermilion is at least the upper\'s height"; the '
                                                             'technician inverted it (10.8 upper, 7.3 lower)'),
    'rules.lips.lower_vermilion': ('[B §4.1] [B §5.5]', 'Farkas NAW: 9.7 (F), 10.4 (M)'),
    'rules.lips.upper_vermilion_m': ('[B §4.1]', 'Farkas NAW men 8.9 (the women\'s value is misprinted in the reproduction)'),
    'rules.bite.overbite': ('[B §6.3] [D §3.3]', 'NHANES III mean overbite 2.9 mm (Brunelle, Bhat & Lipton 1996, J Dent Res '
                                                 '75:706-713, PMID 8594094; abstract re-read in H0 via Europe PMC)'),
    'rules.bite.overjet': ('[E] [B §6.3]', 'study T\'s neutral head (one game head, not a population value; plan §3.3). H0\'s '
                                           'lookup: NHANES III gives no mean in its abstract, only "less than 10% had '
                                           'overjet of 6 mm or more" (Brunelle 1996); the full tables (Brunelle 1996; Proffit, '
                                           'Fields & Moray 1998) were not reachable (paywall / 403). Checked at H4 (the teeth '
                                           'inside the lips at rest)'),
    'rules.bite.overjet_6mm_share': ('[P]', 'Brunelle 1996 abstract (Europe PMC, PMID 8594094): "less than 10% had overjet of '
                                            '6 mm or more" (NHANES III, ages 8-50): a bound the overjet draw keeps'),
    'rules.incisor_display.F': ('[B §6.3]', 'Vig & Brundo 1978 via reproductions: 3.40 mm women'),
    'rules.incisor_display.M': ('[B §6.3]', 'Vig & Brundo 1978: 1.91 mm men'),
    'rules.incisor_display.by_age': ('[B §6.3]', 'Vig & Brundo 1978: 3.31 (<29), 1.58 (30s), 0.95 (40s), 0.46 (50s), 0.04 '
                                                 '(60+); rows (age up to, mm), except the last: (60, 0.04) holds for 60 '
                                                 'and over'),
    'rules.head_not_scaled': ('[D §3.3] [B §3.4]', '"Heads are never scaled with the body": head circumference grows 0.25-0.26 '
                                                   '% per 1 % of stature, R2 0.16-0.27'),
    'mouth.upper_central_crown_length': ('[B §6.3]', 'Vadavadagi et al. 2015 (casts of 70 students): F 9.14-9.26, M '
                                                     '10.17-10.32 (right / left); here (F, M) their means'),
    'skeleton.hjc_below_trochanterion_mm.F': ('[E]', 'the femoral head centre below the greater trochanter\'s tip by the '
                                                     'articulotrochanteric distance less the head radius: women ATD 16 (3.6) '
                                                     'mm (Langenskiöld & Salenius, via a review: a search summary, not the '
                                                     'paper) and head diameter 43.7 (2.4) mm (a hip cohort, search summary): '
                                                     '16 - 21.9 = -5.9; checked by H4\'s regressor and pose sweeps'),
    'skeleton.hjc_below_trochanterion_mm.M': ('[E]', 'men ATD 23 (4) mm, head diameter 47.7 (2.8): 23 - 23.9 = -0.9 (the '
                                                     'same secondary sources and check)'),
    'skeleton.technician.hip': ('[B §5.2]', 'technician_measures.json: hip joint 965 / 1840. NOT taken: it sits 0.55 % of '
                                            'stature (9 mm at 1626) ABOVE ANSUR women\'s trochanterion (0.519), outside the '
                                            'plan\'s own 0.5 % gate (the plan rounded it to 0.524 against 0.519), and the ATD '
                                            'data put the femoral head\'s centre 1-6 mm BELOW the trochanter\'s tip'),
    'skeleton.technician.knee': ('[B §5.2]', 'technician_measures.json: 530 / 1840, +0.20 % of stature over the epicondyle'),
    'skeleton.technician.thigh': ('[B §5.2]', 'technician_measures.json: hip-knee joints 437.55 / 1840'),
    'rings.neck': ('[D §6.2] [N]', 'mid-neck; also the HEAD | BODY seam (K 48)'),
    'rings.shoulder': ('[D §6.2]', 'the armscye loop (K 32)'),
    'rings.elbow': ('[D §6.2]', 'distal upper arm (K 32)'),
    'rings.wrist': ('[D §6.2]', 'distal forearm (K 24)'),
    'rings.hip': ('[D §6.2]', 'the leg root (K 48)'),
    'rings.knee': ('[D §6.2]', 'distal thigh (K 32)'),
    'rings.ankle': ('[D §6.2]', 'distal shank (K 24)'),
    'rings.waist': ('[D §6.2]', 'at the omphalion (K 64): Hege\'s cross'),
    'rings.back_limb': ('[D §6.2]', '3 x 3 cage plugs, K 24 on the low: the sisters\' tentacle ports'),
    'rings.back_shell': ('[D §6.2] [E]', 'a 4 x 4 cage plug on the dorsal midline [E: H1 places and sizes it]'),
    'rings.tail': ('[D §6.2]', 'the sacral 2 x 2 plug (K 16)'),
    'rings.horn': ('[D §6.2]', '2 x 2 plugs on the frontal bone (K 16)'),
    'rings.gill': ('[D §6.2]', '1 x 2 plugs behind the jaw angle (K 12)'),
    'rings.ear': ('[D §6.2] [E]', 'the auricle\'s root ring (K 24) [E: H1]. H0 probe 1 built the ear as one tube of rings '
                                  'from the ears group\'s outline to the concha, 28 spokes (plan box) or 42 (dense box): '
                                  'every variant FOLDED in both fits (12-14 % of the ear\'s limit area turned past 90 deg '
                                  'from GNM\'s, fins to 4.5 mm; the H0 review, work/bestiary/human/scratch_h0/review), '
                                  'so the ear block\'s spoke count is not established, and whether this graft ring is the '
                                  'block\'s own root or a coarser ring outside it is H1\'s ear design'),
    'rings.scalp': ('[D §6.2] [E]', '6-12 plugs of 1 x 2 or 2 x 2 cage quads (K 12-16) [E: Skye\'s taste]'),
    'rings.back_ports': ('[D §6.2]', 'two scapular, two lumbar'),
    'rings.gill_ports': ('[D §6.2]', 'three a side'),
    'rings.nail_collars': ('[D §6.2]', 'claws replace nails'),
    'budget.joints_body': ('[N] [D §4.1]', 'hp_numbers.json joints.body_total'),
    'budget.joints_face_v1': ('[N] [D §4.3]', 'hp_numbers.json joints.face_v1'),
    'budget.joints_face_v2': ('[N] [D §4.3]', 'hp_numbers.json joints.face_full'),
    'budget.joints_max': ('[X §4.6] [N]', '256 per creature'),
    'budget.influences': ('[S §4.1] [D §8]', 'SkinningNode reads 4'),
    'budget.vertex_buffers': ('[X §4.6] [D §8]', 'at most 7 per primitive'),
    'budget.morph_targets': ('[S §4.1] [D §8]', 'at most 32 per geometry'),
    'budget.tris_lod0': ('[N] [E]', 'hp_numbers.json tris_lod0.total'),
    'budget.tris_hero': ('[H] [N]', 'the 150k hero tier (PLAN.md\'s CYBORG R0 entry, 10-21)'),
    'budget.head_cage_quads': ('[E] [D §2.3]', 'about 2,600 control quads [E]. H0 probe 1 (work/bestiary/human/h0/probe1): '
                                               'the box layout at 3,972-4,032 quads (the head block to GNM\'s neck cut) failed '
                                               'the nose (1.10-2.72 mm against 0.8, the H0 review\'s plan_groove2 with the '
                                               'final groove trace included) and, faired at lam 0.2, the lids; at 8,228 quads '
                                               'with a loop on the traced alar-facial and supra-alar groove (dense_groove2) '
                                               'every region passed its p95 bar in both fits (faired: nose 0.64, lids 0.44, '
                                               'lips 0.62, nostrils 0.36, ears 0.61, face 0.28 mm), the ears only on the '
                                               'number: they fold in every variant. That box is denser everywhere (the cranium '
                                               'and neck at 0.1-0.3 mm against bars of 2), so 8.2k is an upper bound for this '
                                               'method, and this value is low; H1 sets it (an adaptive layout) and whether the '
                                               'head\'s low is level 0 or 1'),
    'budget.body_cage_quads': ('[E] [D §2.4]', 'about 3,300 control quads [E: H1]'),
    'budget.sets.HEAD': ('[D §7] [N]', 'unique, about 10,000 px/m'),
    'budget.sets.BODY': ('[D §7] [N]', 'mirrored limbs'),
    'budget.sets.EYES': ('[D §7]', 'one eye, its twin stacked'),
    'budget.sets.MOUTH': ('[D §7]', 'teeth by mirrored pairs'),
    'budget.sets.HAIR': ('[D §7]', 'one strand atlas'),
}
for _sx, _st, _ms, _ag in (('F', 1626.0, 66.1, 29.0), ('M', 1755.0, 77.0, 30.0)):
    TAGS[f'baseline.{_sx}.stature'] = ('[B §0] [B §3.2]', f'ANSUR II median stature ({_B}baseline_figures.json)')
    TAGS[f'baseline.{_sx}.bmi'] = ('[B §0] [D §2.5]', 'BMI 25: "a neutral, sourced base, not the average American"')
    TAGS[f'baseline.{_sx}.mass'] = ('[B §0]', 'BMI 25 x stature^2 (baseline_figures.json body_at_p50_stature_bmi25)')
    TAGS[f'baseline.{_sx}.age'] = ('[B §3.1] [E]', 'about ANSUR II\'s mean age (28.9 F, 30.2 M) [E: the age curves enter at H5]')
    a = f'population.ansur.{_sx}.'
    for k, note in (('n', 'subjects'), ('age', '(min, max, mean)'), ('stature', '(mean, sd)'),
                    ('stature_pct', '(p1, p5, p50, p95, p99)'), ('stature_range', '(min, max)'),
                    ('mass', '(mean, p5, p95) kg'), ('log_bmi', '(mean, sd) of ln BMI: the log-normal draw'),
                    ('bmi_pct', '(mean, p5, p50, p95, p99)'), ('bmi_max', ''),
                    ('r_stature_bmi', 'BMI independent of stature')):
        TAGS[a + k] = ('[B §3.1]', f'ANSUR II {note} ({_B}ansur2_stats.json)')
    for tab in ('stature_cm', 'bmi', 'waist_cm', 'hip_cm', 'upper_leg_cm', 'mass_kg'):
        TAGS[f'population.nhanes.{_sx}.{tab}'] = ('[B §3.6] [B §3.1]', f'NHANES 2021-23 (Fryar et al. 2025), survey weighted '
                                                                       f'({_B}nhanes_2021_2023.csv, every decade 20-29 .. 80+ '
                                                                       f'and 20 and older)')
    for m in (_REG_F if _sx == 'F' else _REG_M):
        TAGS[f'reg.{_sx}.{m}'] = ('[B §3.2] [B §3.4]', f'ANSUR II {"(mean, sd)" if m in ("stature", "weight_kg") else "regression on stature and BMI"} '
                                                       f'({_B}ansur2_stats.json {"female" if _sx == "F" else "male"}.{m})')
    for ax in ('leg_trunk', 'robust', 'mass_upper', 'shoulder'):
        TAGS[f'axes.{_sx}.{ax}.share'] = ('[B §3.5]', f'{_B}ansur2_residual_pca.json')
        TAGS[f'axes.{_sx}.{ax}.loadings'] = ('[B §3.5]', f'the ten leading loadings ({_B}ansur2_residual_pca.json)')
    TAGS[f'axes.{_sx}.cumulative_12'] = ('[B §3.5]', 'components 1-12')
    for m in SPEC['allometry'][_sx]:
        TAGS[f'allometry.{_sx}.{m}'] = ('[B §3.4]', f'{_B}allometry.csv')
    for m, (_, _, src) in SPEC['head'][_sx].items():
        TAGS[f'head.{_sx}.{m}'] = ('[B §4.1]', f'{src} ({_B}baseline_figures.json head_means_mm; NIOSH and Farkas as B §4.1 '
                                               f'reads them)')
    for m in SPEC['head_age'][_sx]:
        TAGS[f'head_age.{_sx}.{m}'] = ('[B §4.2]', f'NIOSH, least squares with race groups as covariates ({_B}'
                                                   f'niosh_headface_stats.json age_effect_vs_18_29)')
    for k in ('hip', 'knee'):
        TAGS[f'skeleton.{_sx}.{k}'] = ('[B §3.3] [B §5.2] [D §4.1]',
                                       'ANSUR II\'s ' + ('trochanterion less hjc_below_trochanterion_mm' if k == 'hip' else
                                                         'lateral femoral epicondyle (the transepicondylar axis as the '
                                                         'knee\'s flexion axis [E])') + f' ({_B}baseline_figures.json '
                                       'skeleton_compare); the H0 gate: within 0.5 % of stature of the landmark')
    for k, lm in (('ankle', 'lateral malleolus'), ('shoulder', 'acromion'), ('neck_01', 'cervicale'), ('head', 'tragion')):
        TAGS[f'skeleton.{_sx}.{k}'] = ('[B §5.2] [E]', ('the technician\'s ratio' if _sx == 'F' else
                                                        f'ANSUR II men\'s {lm} ratio plus the technician\'s joint-to-landmark '
                                                        f'offset') + ' (technician_measures.json, baseline_figures.json); '
                                                                     'de Leva 1996\'s joint centres could not be read in H0 '
                                                                     '(403 / 429) [E: H4\'s regressor]')
    for k, lm in (('upper_arm', 'acromion-radiale'), ('forearm', 'radiale-stylion')):
        TAGS[f'skeleton.{_sx}.{k}'] = ('[B §5.2] [E]', ('the technician\'s joint length' if _sx == 'F' else
                                                        f'the technician\'s length plus the men-women difference of ANSUR '
                                                        f'II\'s {lm} share') + ' [E: H4]')
    TAGS[f'skeleton.{_sx}.hips_apart'] = ('[B §5.2] [E]', 'the technician\'s hip joints apart' if _sx == 'F' else
                                          'the technician\'s, scaled by ANSUR II hip breadth share M / F [E: H4]')
    TAGS[f'skeleton.{_sx}.shoulders_apart'] = ('[B §5.2] [E]', 'the technician\'s shoulder joints apart' if _sx == 'F' else
                                               'the technician\'s, scaled by ANSUR II biacromial share M / F [E: H4]')
for jaw in ('upper', 'lower'):
    for tooth in SPEC['mouth'][jaw]:
        TAGS[f'mouth.{jaw}.{tooth}'] = ('[B §6.3]', 'Uslu Akçam & Yıldız 2025 (BMC Oral Health, 200 people 10-26): '
                                                    '(md F, md M, bl F, bl M); literature_values.json teeth')

TAG_RE = re.compile(r'\[(B|S|X|H|N|E|D|P)(?: §[0-9.]+)?\]')


def leaves(spec=None, prefix=''):
    """every SPEC value as (dotted key, value); a tuple is one value, and so is a table keyed by age group (a dict whose
    keys are not identifiers: NHANES's decades)"""
    out = []
    for k, v in (SPEC if spec is None else spec).items():
        key = f'{prefix}{k}'
        if isinstance(v, dict) and all(str(kk).isidentifier() for kk in v):
            out += leaves(v, key + '.')
        else:
            out.append((key, v))
    return out


def untagged(spec=None, tags=None):
    """the keys whose value has no source tag in the plan's legend, and the tag keys that name no value"""
    tags = TAGS if tags is None else tags
    keys = [k for k, _ in leaves(spec)]
    missing = [k for k in keys if k not in tags or tags[k] is None or not TAG_RE.search(tags[k][0])]
    stale = sorted(set(tags) - set(keys))
    return missing, stale


# ============================================================================================ the helpers
def predict(sex, measure, stature, bmi):
    """an ANSUR II measure (mm; kg for weight) of a body of `stature` (mm) and `bmi` by the sex's regression"""
    r = SPEC['reg'][sex][measure]
    if measure == 'weight_kg':
        return bmi * (stature / 1000.0) ** 2
    if measure == 'stature':
        return stature
    return r[2] + r[3] * stature + r[4] * bmi


def body(sex, stature=None, bmi=None):
    """every regression measure of a body (the baseline's stature and BMI where not given)"""
    b = SPEC['baseline'][sex]
    stature = b['stature'] if stature is None else stature
    bmi = b['bmi'] if bmi is None else bmi
    return {m: predict(sex, m, stature, bmi) for m in SPEC['reg'][sex]}


def mass(stature, bmi):
    return bmi * (stature / 1000.0) ** 2


def joints(sex, stature=None):
    """joint heights (mm) of the sex's skeleton at `stature` (the baseline's where not given), and the segment lengths"""
    st = SPEC['baseline'][sex]['stature'] if stature is None else stature
    sk = SPEC['skeleton'][sex]
    out = {k: v * st for k, v in sk.items()}
    out['thigh'] = (sk['hip'] - sk['knee']) * st
    out['calf'] = (sk['knee'] - sk['ankle']) * st
    return out
