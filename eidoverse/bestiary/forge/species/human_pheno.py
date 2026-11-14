"""HUMAN H2: the BODY REFERENCE as MakeHuman draws it: hm08 (MPFB2 core assets, CC0, read as data) at the baseline
phenotype, set with MakeHuman's OWN targets instead of H1's station transforms (the lead's H2 brief: "if the
ANSUR-pinned MakeHuman is itself lumpy, fix the reference (its own phenotype targets at the measured baseline)").

WHY. H1's PinnedBody scaled the body per station (PCHIP curves of x / z / diagonal scales through the chest, waist and
buttock stations, a radial scale about each limb's axis, blended across the crotch and the shoulder by geometric
weights). Its renders (h1/ref/body_pinned_F/M.png) show what that does between stations: a sharp corner in the outline
at both hips where the trunk's x scale and the leg's radial scale meet over the 40 mm blend, a flattened trapezius on
the man. MakeHuman's targets are artist-made deltas over the whole region they shape, so any weighted sum of them stays
as smooth as hm08 itself: the body is moved only along directions an artist drew.

THE MODEL (MakeHuman 1.1's macro modifier rules, which MPFB2 keeps; targets/macrodetails/macro.json's combinations):
  race-gender-age          macrodetails/<race>-<gender>-<age>, weight race x gender x age (the three races a third each,
                           MakeHuman's default)
  universal                macrodetails/universal-<gender>-<age>-<muscle>-<weight>, weight gender x age x muscle x weight
  height                   macrodetails/height/<gender>-<age>-<muscle>-<weight>-<min|max>height
  proportions              macrodetails/proportions/<gender>-<age>-<muscle>-<weight>-<ideal|uncommon>proportions
  breast (female)          breast/female-<age>-<muscle>-<weight>-<cup>-<firmness>
with each variable's weights as MakeHuman computes them (age: 25 y = 0.5, 90 y = 1; muscle, weight, height, proportions,
cup and firmness: min / average / max about 0.5). Then the REGIONAL modifiers, each a signed value v in [-1, 1] on its
decr / incr pair (both sides at once where the target is sided): MakeHuman's measure modifiers (bust, underbust, waist,
hips, neck, upper arm, thigh, knee, calf, ankle, wrist circumferences; front chest, shoulder, nape-to-waist and
waist-to-hip distances; upper / lower arm lengths, upper / lower leg heights, neck height) and a few scale / volume
modifiers. One global uniform scale takes the stature's last millimetres.

THE SOLVE. Bounded least squares (scipy, trust region, finite differences) on ANSUR II's baseline (the regression body
at the sex's stature and BMI 25: human_ref.ansur_targets), every residual in the measure's residual sd, plus a ridge on
the regional values (each in sd units per unit value: RIDGE) so the body stays MakeHuman's where the measures don't ask.
The landmarks are vertex ids found by human_ref.mh_landmarks' surface rules, held fixed inside a solve (they jump between
vertices) and re-found between outer passes. The girths are taken on the faceted mesh; an outer pass measures them again
on the smooth surface the cage will carry (human_ref.mh_smooth's limit through the vertices) and carries the ratio into
the next pass's targets. Two things since the first solve (h2-pheno-2): the regional targets' deltas are low-passed
(LOWPASS: at high weight they printed their noise), and ANSUR's mid-neck girth is no longer pinned on hm08's own
mid-neck, which the cage cuts away (GNM's neck carries it); the seam with the head's ring is reported (SEAM).

    PhenoModel(sex)                  the targets and the build: V(params) (mm, ground at y 0, all hm08 vertices)
    Measurer(model, V)               ANSUR's measures on a body of hm08's topology (landmarks and stations fixed at V)
    Seam(ring0, gV, gF, stature)     the head's neck ring against hm08's surface (signed radial gaps; reported)
    solve(sex, log, seam) -> dict(V, params, report)   the baseline reference, written by work/bestiary/human/h2/h2_ref.py
"""
import gzip
import os
import site
import sys

sys.path.append(site.getusersitepackages())
import numpy as np

from . import human as HS
from . import human_ref as HR

VERSION = 'h3-pheno-4'          # -4 (H3): BACK_SMOOTH's mask kept on the upper back, off the armpit vault
#                                 -3: the man's upper-back corrective (BACK_SMOOTH); ANSUR's hip breadth, chest weights,
                                # the buttock and epicondyle rules and weights (the H2b notes at PINNED and
                                # Measurer.measure)
TGT = os.path.join(HR.MH_DIR, 'targets')
_T = {}

# the regional modifiers: name -> (decr files, incr files) relative to targets/ (a {s} in a name is each side, l and r)
REGIONAL = dict(
    bust=('torso/measure-bust-circ-decr', 'torso/measure-bust-circ-incr'),
    underbust=('torso/measure-underbust-circ-decr', 'torso/measure-underbust-circ-incr'),
    waist=('torso/measure-waist-circ-decr', 'torso/measure-waist-circ-incr'),
    hips=('torso/measure-hips-circ-decr', 'torso/measure-hips-circ-incr'),
    frontchest=('torso/measure-frontchest-dist-decr', 'torso/measure-frontchest-dist-incr'),
    shoulder_dist=('torso/measure-shoulder-dist-decr', 'torso/measure-shoulder-dist-incr'),
    napetowaist=('torso/measure-napetowaist-dist-decr', 'torso/measure-napetowaist-dist-incr'),
    waisttohip=('torso/measure-waisttohip-dist-decr', 'torso/measure-waisttohip-dist-incr'),
    torso_depth=('torso/torso-scale-depth-decr', 'torso/torso-scale-depth-incr'),
    torso_horiz=('torso/torso-scale-horiz-decr', 'torso/torso-scale-horiz-incr'),
    torso_vert=('torso/torso-scale-vert-decr', 'torso/torso-scale-vert-incr'),
    hip_depth=('hip/hip-scale-depth-decr', 'hip/hip-scale-depth-incr'),
    hip_horiz=('hip/hip-scale-horiz-decr', 'hip/hip-scale-horiz-incr'),
    hip_waist=('hip/hip-waist-down', 'hip/hip-waist-up'),
    buttocks=('buttocks/buttocks-volume-decr', 'buttocks/buttocks-volume-incr'),
    belly=('stomach/stomach-pregnant-decr', 'stomach/stomach-pregnant-incr'),
    thigh=('legs/measure-thigh-circ-decr', 'legs/measure-thigh-circ-incr'),
    knee=('legs/measure-knee-circ-decr', 'legs/measure-knee-circ-incr'),
    calf=('legs/measure-calf-circ-decr', 'legs/measure-calf-circ-incr'),
    upperleg_h=('legs/measure-upperleg-height-decr', 'legs/measure-upperleg-height-incr'),
    lowerleg_h=('legs/measure-lowerleg-height-decr', 'legs/measure-lowerleg-height-incr'),
    upperlegs_h=('legs/upperlegs-height-decr', 'legs/upperlegs-height-incr'),
    lowerlegs_h=('legs/lowerlegs-height-decr', 'legs/lowerlegs-height-incr'),
    ankle=('feet/measure-ankle-circ-decr', 'feet/measure-ankle-circ-incr'),
    foot_len=('feet/{s}-foot-scale-depth-decr', 'feet/{s}-foot-scale-depth-incr'),
    foot_br=('feet/{s}-foot-scale-horiz-decr', 'feet/{s}-foot-scale-horiz-incr'),
    foot_vert=('feet/{s}-foot-scale-vert-decr', 'feet/{s}-foot-scale-vert-incr'),
    upperarm=('arms/measure-upperarm-circ-decr', 'arms/measure-upperarm-circ-incr'),
    upperarm_len=('arms/measure-upperarm-length-decr', 'arms/measure-upperarm-length-incr'),
    lowerarm_len=('arms/measure-lowerarm-length-decr', 'arms/measure-lowerarm-length-incr'),
    forearm_d=('arms/{s}-lowerarm-scale-depth-decr', 'arms/{s}-lowerarm-scale-depth-incr'),
    forearm_h=('arms/{s}-lowerarm-scale-horiz-decr', 'arms/{s}-lowerarm-scale-horiz-incr'),
    wrist=('hands/measure-wrist-circ-decr', 'hands/measure-wrist-circ-incr'),
    hand=('hands/{s}-hand-scale-decr', 'hands/{s}-hand-scale-incr'),
    fingers_len=('hands/{s}-hand-fingers-length-decr', 'hands/{s}-hand-fingers-length-incr'),
    fingers_dist=('hands/{s}-hand-fingers-distance-decr', 'hands/{s}-hand-fingers-distance-incr'),
    fingers_diam=('hands/{s}-hand-fingers-diameter-decr', 'hands/{s}-hand-fingers-diameter-incr'),
    neck=('neck/measure-neck-circ-decr', 'neck/measure-neck-circ-incr'),
    neck_h=('neck/measure-neck-height-decr', 'neck/measure-neck-height-incr'),
    neck_v=('neck/neck-trans-down', 'neck/neck-trans-up'),
    neck_horiz=('neck/neck-scale-horiz-decr', 'neck/neck-scale-horiz-incr'),
    neck_depth=('neck/neck-scale-depth-decr', 'neck/neck-scale-depth-incr'),
)
# the ridge on each regional value, in residual sd per unit value [E: H2, read on the solved values and looked at]. At
# 0.35 the first solve drove 11 of 37 values to their +-1 bounds and the woman read muscular (broad trapezius, bulging
# calves): 0.6 keeps values nothing strongly asks for near MakeHuman's 0
RIDGE = 0.6
# the macro variables solved (bounds); age is the SPEC baseline's (not solved), the races a third each. MACRO_RIDGE
# holds weight, muscle and proportions toward MakeHuman's average (sd per unit away from 0.5): unheld, the first solve
# took the woman to maximum weight (0.999) and shrank her back with the global scale (0.915), a degenerate trade that
# printed a heavy-set athlete's forms at the right girths
# MUSCLE is held at MakeHuman's average (0.5), not solved: free (held by a ridge of 3 sd per unit), it went to 0.70 on
# the woman and 0.67 on the man, and the woman read as an athlete (an abdominal groove, the back's muscles drawn, the
# calves bulging; look/ref_before_after_F of the second solve, kept in scratch/). The baseline is an average adult;
# fitness is one of H5's axes
MACRO = dict(height=(0.0, 1.0), weight=(0.0, 1.0), proportions=(0.3, 0.7))
MACRO_F = dict(cup=(0.0, 1.0), firmness=(0.2, 0.8))
MACRO_FIXED = dict(muscle=0.5)
MACRO_RIDGE = dict(weight=2.0, proportions=1.5, cup=1.0, firmness=1.0)
# the global scale only takes the stature's last millimetres (the height macro does the rest)
SCALE_BOUNDS = (0.98, 1.02)
# MakeHuman's REGIONAL targets at high weight print their sculpting noise: the man's first solve set bust-circ-decr 0.71,
# napetowaist-decr 0.97 and underbust-incr 0.98, and his upper back read mottled, his nipples crumpled (look/ba_M_close
# of the first build; work/bestiary/human/h2/scratch/p09_lowpass_regional.py). Their deltas are low-passed over hm08's
# topology (LOWPASS half-weighted umbrella passes over the band each target moves, grown by as many rings so its edge
# fades): the intent stays (a girth or a length over a region), the vertex-scale noise goes; on the first solve's values
# the measures moved < 0.3 sd. The hands' and feet's targets stay raw (local by design, on thin dense parts, where the
# umbrella would average a finger's opposite sides); so do the macro targets (they carry the forms)
LOWPASS = 4
LOWPASS_RAW = ('hands/', 'feet/')
# ANSUR's chest height is the bust point (the nipple): hm08's left areola ring and the nipple inside it, by vertex id
# (hm08's topology, the same on both sexes); mh_landmarks' rule (the most anterior chest point) found the man's lower
# ribs, 82 mm under his nipples, and the chest's sections followed it (chest height -4.5 sd in the first solve)
NIPPLE_L = tuple(range(8434, 8466))
# the measures pinned (ANSUR II names) and their weights in the least squares. NOT the mid-neck girth: the cage cuts
# hm08's neck away above its loop X and GNM's neck carries ANSUR's mid-neck girth (conditioned in H1, gated on the
# clay); pinned on hm08's own mid-neck it shrank the man's neck and opened the seam (SEAM below). The buttock height and
# the epicondyle were weighted 0.4 / 0.3 while their surface rules were thought to read MakeHuman's buttock and knee
# loosely (H1 and H2 missed both). H2b read them again (h2b/scratch/p07, p10): the knee's lateral skin is flat over
# ~70 mm, so the epicondyle is now read level with the patella's upper half (human_ref.mh_landmarks); the buttock's
# posterior reach, read on the sections, is one smooth peak (the woman's at 857 mm, 104.0 mm back; within 3 mm of it
# from 832 to 880), so the old extreme WAS the apex: MakeHuman's buttock apex sits ~27 mm over ANSUR's buttock height,
# a SHAPE, not a rule miss. At the full weight the targets could not move it (the woman +1.10 -> +1.21 sd) and the
# solve lowered her hips instead (trochanterion -0.10 -> -0.81: logs/run_h2b_ref_v2.txt), so the buttock height keeps
# H2's 0.4; the epicondyle, read where the bone is, takes the full weight (the man +1.52 -> +0.16)
PINNED = dict(
    stature=2.0, acromialheight=1.0, axillaheight=1.0, chestheight=0.7, suprasternaleheight=1.0, cervicaleheight=1.0,
    waistheightomphalion=1.0, trochanterionheight=1.0, crotchheight=1.0, buttockheight=0.4, kneeheightmidpatella=1.0,
    lateralfemoralepicondyleheight=1.0, lateralmalleolusheight=0.6,
    biacromialbreadth=1.0, chestbreadth=1.0, chestdepth=1.0, waistbreadth=1.0, waistdepth=1.0, hipbreadth=1.0,
    buttockdepth=1.0,
    neckcircumferencebase=1.0, chestcircumference=1.5, waistcircumference=1.5,
    buttockcircumference=1.5, thighcircumference=1.0, lowerthighcircumference=1.0, calfcircumference=1.0,
    anklecircumference=1.0, bicepscircumferenceflexed=1.0, forearmcircumferenceflexed=1.0, wristcircumference=1.0,
    handcircumference=1.0,
    acromionradialelength=1.0, radialestylionlength=1.0, handlength=1.0, footlength=1.0, footbreadthhorizontal=1.0,
)
# per-sex weights over PINNED (H2b, the lead's call: "the man's chest with its girth weighted first, breadth and depth
# as close as a rounded chest allows"). ANSUR's man's chest (breadth 282, depth 239, girth 1006) implies a section whose
# tape is 0.97 of its bounding box's perimeter; MakeHuman's rounded chest is 0.87 (H2's scratch/p08), so no smooth chest
# meets all three: the girth leads, and breadth and depth follow as far as the rounded section lets them. At girth 1006
# a 0.87 section needs breadth + depth ~578 mm against ANSUR's 521, so "as close as it allows" is that excess SHARED
# (about +2.3 sd each). Breadth and depth keep the full weight 1.0 for that: at 0.3 each the other terms chose the
# split and put it all in the breadth (339 mm, +4.4 sd; depth +1.0: h2b/logs/run_h2b_ref_v1_buttockbug.txt). The girth
# at 3.0 still gave way to them (-0.33 sd, breadth +2.26, depth +1.91: logs/run_h2b_ref_v2.txt): 6.0 puts it first
PINNED_SEX = dict(M=dict(chestcircumference=6.0, chestbreadth=1.0, chestdepth=1.0))
# THE MAN'S UPPER BACK (H2b, the lead's call 2). MakeHuman's race targets (macrodetails/<race>-<gender>-<age>, a third
# each) carry the whole male shape over hm08's neutral base (68 mm on the upper back) and scan noise with it: soft
# blotches over the scapulae and along the spine (each race alone about as rough as the mix; H2's look:h2). Smoothing
# their DELTA brings hm08's bony scapulae back (h2b/scratch/p05_back.py: at 10-24 mm the base's sharp medial borders
# return); low-passing the macro deltas over the trunk inflated the nipples and the navel (H2's p12). So the corrective
# smooths the FINAL surface, inside a feathered mask over the upper back only, with Taubin's non-shrinking lambda / mu
# passes over hm08's one-ring: the mottle's scale (one or two of hm08's ~18 mm quads) goes, the forms several quads
# across stay (the scapulae, the erector spinae, the trapezius); the mask's weight is eased toward the midline (the
# spinal furrow is one quad wide). At 16 passes the back reads clean beside the body study's male backs, the scapulae
# still soft forms; 8 left a faint unevenness at the scapular border, 32 flattened the blades (p06_back_taubin.py); the
# measures move < 0.12 sd (chest depth). The woman is left out: her back reads clean, its furrow and erector columns
# defined, which the filter would soften. The mask: the trunk's back (normals facing back), from 170 mm under the
# axilla to 5 mm under the cervicale, to the posterior axillary lines, feathered over 35 mm; found once per sex on its
# default young phenotype (human_ref.MHBody), so it is a fixed weight per hm08 vertex for every solve.
# H3 (the lead's H3 call 3): KEPT ON THE UPPER BACK, OFF THE ARMPIT VAULT. The H2b mask ran to the axilla's x + 10 mm
# and let side-facing normals in at ~0.4, so the vault took weights up to 1.0 within 40 mm of the axilla and was
# smoothed by up to 4.1 mm (the axillary notch went soft seen from below: h2b review p05_armpit.png). Now: the lateral
# limit `lateral` mm inside the axilla's x (feathered inward over `feather`), normals that FACE BACK (`facing`: none at
# n_z >= -0.30, full at n_z <= -0.60; the posterior axillary line and the vault's side faces stay out), never DOWN
# (`down`: none at n_y <= -0.60, full at >= -0.30: the vault's roof), and nothing within `axilla_clear` mm of either
# axilla landmark (none within 55, full beyond 95)
BACK_SMOOTH = dict(sexes=('M',), passes=16, lam=0.5, mu=-0.53, below_axilla=170.0, below_cervicale=5.0, feather=35.0,
                   mid_ease=30.0, mid_floor=0.35, lateral=25.0, facing=(-0.30, -0.60), down=(-0.60, -0.30),
                   axilla_clear=(55.0, 95.0))
GIRTHS = ('neckcircumference', 'neckcircumferencebase', 'chestcircumference', 'waistcircumference',
          'buttockcircumference', 'thighcircumference', 'lowerthighcircumference', 'calfcircumference',
          'anklecircumference', 'bicepscircumferenceflexed', 'forearmcircumferenceflexed', 'wristcircumference',
          'handcircumference')
# THE NECK SEAM (H2's cage: GNM owns the neck down to the head's mid-neck ring, hm08 from its loop X under it). The
# man's first solve left the head's ring 17 mm outside his hm08 neck at the back (9 at the sides, 2 at the front) and his
# nape printed a ridge at the ring over a groove at X (look/p06_neck_sagittal_M.png of the first build; the woman's
# 3.8 mm p95 read clean). The seam was tried as RESIDUALS here (the ring's radial gaps to hm08, 2.5 mm a unit, weight
# 0.4, with neck-back depth and neck-forward modifiers to close it): unstable, because the head's placement reads the
# suprasternale and the cervicale, which the profile rules re-find between the outer passes (the man's seam went 7 ->
# 20 -> 16 mm over three passes and 11 of 37 measures held; the woman's two landmarks jumped 7 and 17 mm up and her
# base girth fell 1.8 sd: logs/run_h2_ref_v3.txt). So the seam is REPORTED here (Seam, SEAM_N of the ring's points) and
# closed in the build, where the landmarks are fixed: human_hmcage.NeckConform
SEAM_N = 12


def target(rel):
    """a target's per-vertex offsets (MakeHuman decimetres) over all hm08 vertices, or None if there is no such file"""
    if rel in _T:
        return _T[rel]
    path = os.path.join(TGT, rel + '.target.gz')
    D = None
    if os.path.exists(path):
        D = np.zeros_like(HR.mh_data()['V'])
        with gzip.open(path, 'rt') as fh:
            rows = [ln.split() for ln in fh if ln.strip() and not ln.startswith('#')]
        rows = [r for r in rows if len(r) >= 4]
        if rows:
            A = np.array(rows, np.float64)
            D[A[:, 0].astype(np.int64)] = A[:, 1:4]
    _T[rel] = D
    return D


_LP = {}
_UMB = []


def _umbrella():
    """hm08's body umbrella operator (the one-ring mean, scipy sparse, row-normalised) and its adjacency pattern"""
    if not _UMB:
        import scipy.sparse as sp
        d = HR.mh_data()
        nb = d['nb']
        Q = np.asarray(d['Q'], np.int64)
        E = np.unique(np.sort(np.vstack([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]]), 1), axis=0)
        A = sp.coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
                          shape=(nb, nb)).tocsr()
        deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1.0)
        _UMB.append((sp.diags(1.0 / deg) @ A, A))
    return _UMB[0]


def regional_delta(rel):
    """a REGIONAL target's offsets (as target()), low-passed on the body vertices (LOWPASS, the note there), or None"""
    if rel in _LP:
        return _LP[rel]
    D = target(rel)
    if D is not None and LOWPASS > 0 and not rel.startswith(LOWPASS_RAW):
        U, A = _umbrella()
        nb = U.shape[0]
        zone = np.linalg.norm(D[:nb], axis=1) > 0
        for _ in range(LOWPASS):
            zone = zone | (A @ zone.astype(np.float64) > 0)
        Y = D[:nb].copy()
        for _ in range(LOWPASS):
            Y = np.where(zone[:, None], 0.5 * Y + 0.5 * (U @ Y), Y)
        D = D.copy()
        D[:nb] = Y
    _LP[rel] = D
    return D


def _three(v):
    """MakeHuman's min / average / max weights of a variable about 0.5"""
    mx = max(0.0, 2.0 * v - 1.0)
    mn = max(0.0, 1.0 - 2.0 * v)
    return dict(min=mn, average=1.0 - mx - mn, max=mx)


def age_value(years):
    """MakeHuman's age modifier for an age in years: 1 y = 0, 11 y = 0.1875, 25 y = 0.5, 90 y = 1"""
    if years >= 25.0:
        return 0.5 + 0.5 * (years - 25.0) / 65.0
    if years >= 11.0:
        return 0.1875 + (0.5 - 0.1875) * (years - 11.0) / 14.0
    return 0.1875 * (years - 1.0) / 10.0


def _ages(a):
    if a < 0.5:
        young = max(0.0, (a - 0.1875) * 3.2)
        baby = max(0.0, 1.0 - a * 5.333)
        child = max(0.0, min(1.0, 5.333 * a) - young)
        return dict(baby=baby, child=child, young=young, old=0.0)
    old = max(0.0, 2.0 * a - 1.0)
    return dict(baby=0.0, child=0.0, young=1.0 - old, old=old)


def macro_list(sex, age, height, weight, muscle, proportions, cup=0.5, firmness=0.5):
    """[(target rel, weight)] of the macro modifiers (MakeHuman's combinations), weights below 1e-9 dropped"""
    g = 'female' if sex == 'F' else 'male'
    A = {k: v for k, v in _ages(age_value(age)).items() if v > 0.0}
    M = {k: v for k, v in _three(muscle).items() if v > 0.0}
    W = {k: v for k, v in _three(weight).items() if v > 0.0}
    H = _three(height)
    P = _three(proportions)
    C = _three(cup)
    Fm = _three(firmness)
    out = []
    for race in ('african', 'asian', 'caucasian'):
        for a, wa in A.items():
            out.append((f'macrodetails/{race}-{g}-{a}', wa / 3.0))
    for a, wa in A.items():
        for m, wm in M.items():
            for w, ww in W.items():
                base = f'{g}-{a}-{m}muscle-{w}weight'
                out.append((f'macrodetails/universal-{base}', wa * wm * ww))
                for h in ('min', 'max'):
                    if H[h] > 0.0:
                        out.append((f'macrodetails/height/{base}-{h}height', wa * wm * ww * H[h]))
                if P['max'] > 0.0:
                    out.append((f'macrodetails/proportions/{base}-idealproportions', wa * wm * ww * P['max']))
                if P['min'] > 0.0:
                    out.append((f'macrodetails/proportions/{base}-uncommonproportions', wa * wm * ww * P['min']))
                if sex == 'F':
                    for c, wc in C.items():
                        for f_, wf in Fm.items():
                            if (c, f_) == ('average', 'average') or wc * wf <= 0.0:
                                continue
                            out.append((f'breast/female-{a}-{m}muscle-{w}weight-{c}cup-{f_}firmness',
                                        wa * wm * ww * wc * wf))
    return [(r, w) for r, w in out if w > 1e-9]


def regional_list(name, v):
    """[(target rel, weight)] of one regional modifier at the signed value v (both sides of a sided one)"""
    if abs(v) < 1e-12:
        return []
    rel = REGIONAL[name][1 if v > 0 else 0]
    sides = ('l', 'r') if '{s}' in rel else ('',)
    return [(rel.format(s=s) if s else rel, abs(v)) for s in sides]


class PhenoModel:
    """the targets and the build for one sex: V(params) in mm over all hm08 vertices (helpers and joint cubes too), the
    ground (MakeHuman's joint-ground cube) at y 0"""

    def __init__(self, sex):
        self.sex = sex
        self.d = HR.mh_data()
        self.age = HS.SPEC['baseline'][sex]['age']
        self.macro = dict(MACRO, **(MACRO_F if sex == 'F' else {}))
        self.names = list(self.macro) + list(REGIONAL) + ['scale']
        self.n_macro = len(self.macro)
        lo = [b[0] for b in self.macro.values()] + [-1.0] * len(REGIONAL) + [SCALE_BOUNDS[0]]
        hi = [b[1] for b in self.macro.values()] + [1.0] * len(REGIONAL) + [SCALE_BOUNDS[1]]
        self.bounds = (np.array(lo), np.array(hi))
        self.x0 = np.array([0.5] * self.n_macro + [0.0] * len(REGIONAL) + [1.0])
        # the hm08 mirror map (hm08.mirror: "i j side"); the midline maps to itself
        mir = np.arange(len(self.d['V']))
        with open(os.path.join(HR.MH_DIR, 'mesh_metadata', 'hm08.mirror'), encoding='utf-8') as fh:
            for ln in fh:
                p = ln.split()
                if len(p) >= 2:
                    mir[int(p[0])] = int(p[1])
        self.mirror = mir

    def params(self, x):
        return dict(zip(self.names, [float(v) for v in x]))

    def build(self, x, symmetric=True):
        p = self.params(x)
        mk = dict(MACRO_FIXED, **{k: p[k] for k in self.macro})
        lst = macro_list(self.sex, self.age, mk['height'], mk['weight'], mk['muscle'], mk['proportions'],
                         mk.get('cup', 0.5), mk.get('firmness', 0.5))
        reg = []
        for name in REGIONAL:
            reg += regional_list(name, p[name])
        Vd = self.d['V'].copy()
        for rel, w in lst:
            D = target(rel)
            if D is not None:
                Vd += w * D
        for rel, w in reg:
            D = regional_delta(rel)
            if D is not None:
                Vd += w * D
        if symmetric:
            # MakeHuman's macro targets carry a little asymmetry (scan-derived); the baseline is symmetric
            Vm = Vd[self.mirror] * np.array([-1.0, 1.0, 1.0])
            Vd = 0.5 * (Vd + Vm)
            mid = self.mirror == np.arange(len(Vd))
            Vd[mid, 0] = 0.0
        # the ground at the SOLE (the body's lowest vertex), where ANSUR's heights start. MakeHuman's joint-ground cube
        # sat 13.7 / 16.4 mm over the solved soles (the foot and lower-leg targets move the sole, not the cube), so the
        # first solves measured every height from a floor the feet stood through (the turntable's floor cut the toes)
        ground_y = float(Vd[:self.d['nb'], 1].min())
        V = (Vd - np.array([0.0, ground_y, 0.0])) * 100.0
        # the global scale about the ground under the body's centre
        c = np.array([0.0, 0.0, 0.0])
        V = c + (V - c) * p['scale']
        if self.sex in BACK_SMOOTH['sexes']:
            V = self.back_corrective(V)
        return V

    def back_mask(self):
        """BACK_SMOOTH's feathered upper-back weight per body vertex, found once on the sex's default young phenotype"""
        if getattr(self, '_back_w', None) is None:
            cfg = BACK_SMOOTH
            B = HR.MHBody(self.sex)
            L = HR.mh_landmarks(B, log=lambda *a: None)
            Vb = B.Vb
            vn = HR.vertex_normals(Vb, B.F)

            def ss(t):
                t = np.clip(t, 0.0, 1.0)
                return t * t * (3.0 - 2.0 * t)
            f = cfg['feather']
            y_lo = float(Vb[L['axilla'], 1]) - cfg['below_axilla']
            y_hi = float(Vb[L['cervicale'], 1]) - cfg['below_cervicale']
            # (H3) the lateral limit inside the axilla, back-facing and not down-facing normals, clear of both axillae
            x_lim = abs(float(Vb[L['axilla'], 0])) - cfg['lateral']
            f0, f1 = cfg['facing']
            d0, d1 = cfg['down']
            r0, r1 = cfg['axilla_clear']
            ax = Vb[L['axilla']]
            d_ax = np.minimum(np.linalg.norm(Vb - ax, axis=1),
                              np.linalg.norm(Vb - ax * np.array([-1.0, 1.0, 1.0]), axis=1))
            w = ss((Vb[:, 1] - y_lo) / f) * ss((y_hi - Vb[:, 1]) / f) * ss((x_lim - np.abs(Vb[:, 0])) / f) * \
                ss((f0 - vn[:, 2]) / (f0 - f1)) * ss((vn[:, 1] - d0) / (d1 - d0)) * ss((d_ax - r0) / (r1 - r0))
            w *= cfg['mid_floor'] + (1.0 - cfg['mid_floor']) * ss(np.abs(Vb[:, 0]) / cfg['mid_ease'])
            trunk = np.isin(B.part, ('trunk', 'neck')) | (B.w('trunk') > 0.5)
            w = np.where(trunk & (vn[:, 2] < f0), w, 0.0)
            # symmetric (the default phenotype carries MakeHuman's scan asymmetry; the baseline is mirrored)
            self._back_w = 0.5 * (w + w[self.mirror[:len(w)]])
        return self._back_w

    def back_corrective(self, V):
        """V (all hm08 vertices, mm) with BACK_SMOOTH's corrective: Taubin passes over the mask and two rings round it
        (the rest held), blended in by the mask's weight"""
        cfg = BACK_SMOOTH
        nb = self.d['nb']
        w = self.back_mask()
        U, A = _umbrella()
        act = w > 0
        for _ in range(2):
            act = act | (A @ act.astype(np.float64) > 0)
        X = V[:nb].copy()
        m = act[:, None]
        for _ in range(cfg['passes']):
            X = np.where(m, X + cfg['lam'] * (U @ X - X), X)
            X = np.where(m, X + cfg['mu'] * (U @ X - X), X)
        V = V.copy()
        V[:nb] += w[:, None] * (X - V[:nb])
        return V

    def missing(self):
        """the target files the model names that do not exist (should be none past the empty 'average' universals)"""
        x = self.x0.copy()
        out = []
        for name in REGIONAL:
            for v in (-1.0, 1.0):
                for rel, _ in regional_list(name, v):
                    if target(rel) is None:
                        out.append(rel)
        return out


# ============================================================================================ measuring
class Measurer:
    """ANSUR II's measures on a body of hm08's topology. Built on a body V0: the landmark ids (human_ref.mh_landmarks'
    surface rules) and the limb stations (as chain parameters on the joint cubes' axes, H1 PinnedBody's definitions:
    thigh 35 mm under the crotch, lower thigh 70 mm over mid-patella, the calf at the shank's widest section, the ankle
    45 mm over the malleolus; biceps / forearm / wrist at arm chain parameters 0.5 / 1.25 / 1.92, the hand round the
    knuckles) are fixed there; measure(V) reads them on any later V of the same topology. surface=(Vs, Fs, quad) measures
    the sections on another surface (the clay, or the smooth reference) whose triangles descend from hm08 quads `quad`
    (-1: no hm08 quad, e.g. the head's), while the landmarks and joints stay V's"""

    def __init__(self, sex, V0):
        self.sex = sex
        self.B0 = HR.MHBody(sex, V0)
        self.L = HR.mh_landmarks(self.B0, log=lambda *a: None)
        B = self.B0
        V = B.Vb
        J = B.joints
        nip = np.array(NIPPLE_L)
        self.L['chest'] = int(nip[np.argmax(V[nip, 2])])
        self.T = HR.ansur_targets(sex)
        self.flex = {m: HR.FLEX_RATIO[sex] for m in ('bicepscircumferenceflexed', 'forearmcircumferenceflexed')}
        Q = B.Q
        self.nq = len(Q)
        # per hm08 QUAD the region each section reads (a triangle of hm08's F descends from quad t % nq)
        armw = B.w('arm_L', 'arm_R', 'hand_L', 'hand_R')
        legm = (B.part == 'leg_L') | (B.w('leg_L') > 0.3)
        armm = (B.part == 'arm_L') | (B.w('arm_L') > 0.3)
        thumb = (B.bone_w('finger1', 'L') + B.bone_w('metacarpal1', 'L')) > 0.5
        hm = ((B.part == 'hand_L') | (B.w('hand_L') > 0.3)) & ~thumb
        self.qmask = dict(trunk=(armw < 0.5)[Q].all(1), neck=np.isin(B.part, ('trunk', 'neck', 'head'))[Q].all(1),
                          leg=legm[Q].any(1), arm=armm[Q].any(1), hand=hm[Q].all(1))
        tq = np.arange(len(B.F)) % self.nq
        self.F_trunk, self.F_neck, self.F_leg, self.F_arm, self.F_hand = (
            B.F[self.qmask[k][tq]] for k in ('trunk', 'neck', 'leg', 'arm', 'hand'))
        self.foot = B.part == 'foot_L'
        y = lambda k: V[self.L[k], 1]           # noqa: E731
        legA = self._leg_axis(J)
        self.leg_st = dict(thigh=self._axis_t(legA, y('crotch') - 35.0),
                           lowerthigh=self._axis_t(legA, y('mid_patella') + 70.0),
                           ankle=self._axis_t(legA, y('malleolus') + 45.0))
        best, bt = 0.0, 1.3
        for t in np.linspace(1.15, 1.6, 19):
            g = self._limb_girth(V, self.F_leg, legA, t)
            if g > best:
                best, bt = g, t
        self.leg_st['calf'] = bt
        armA = self._arm_axis(J, V)
        wr, tip = armA[2], armA[3]
        mcp = J['l-finger-3-1']
        self.arm_st = dict(biceps=0.5, forearm=1.25, wrist=1.92)
        self.hand_t = 2.0 + float((mcp - wr) @ (tip - wr) / ((tip - wr) @ (tip - wr))) - 0.02

    # ---------------------------------------------------------------------------------- chains
    @staticmethod
    def _leg_axis(J):
        return np.array([J['l-upper-leg'], J['l-knee'], J['l-ankle']])

    def _arm_axis(self, J, V):
        return np.array([J['l-shoulder'], J['l-elbow'], J['l-hand'], V[self.L['fingertip']]])

    @staticmethod
    def _axis_t(A, yh):
        for s in range(len(A) - 1):
            a, b = A[s], A[s + 1]
            if min(a[1], b[1]) <= yh <= max(a[1], b[1]):
                return s + (a[1] - yh) / (a[1] - b[1])
        return 0.0 if yh > A[0][1] else len(A) - 1.0

    @staticmethod
    def chain_point(A, t):
        s = int(np.clip(np.floor(t), 0, len(A) - 2))
        f = t - s
        return A[s] * (1 - f) + A[s + 1] * f, (A[s + 1] - A[s]) / np.linalg.norm(A[s + 1] - A[s])

    @staticmethod
    def _loop_tape(S, c, e1, e2):
        """the tape round the section loop enclosing c (else the loop nearest it)"""
        from matplotlib.path import Path as MPath
        best, bd = None, np.inf
        for lp in HR.section_loops(S):
            if len(lp) < 4:
                continue
            P2 = np.column_stack([(lp - c) @ e1, (lp - c) @ e2])
            if MPath(P2).contains_point((0.0, 0.0)):
                return HR.hull_perimeter(P2), P2
            d = np.linalg.norm(P2, axis=1).min()
            if d < bd:
                best, bd = P2, d
        return (HR.hull_perimeter(best), best) if best is not None else (0.0, None)

    def _limb_girth(self, V, F, A, t, radius=None):
        c, ax = self.chain_point(A, t)
        S, _ = HR.plane_section(V, F, c, ax)
        if len(S) == 0:
            return 0.0
        if radius is not None:
            S = S[np.linalg.norm(S.mean(1) - c, axis=1) < radius]
        e1, e2, _ = HR.plane_basis(ax)
        return self._loop_tape(S, c, e1, e2)[0]

    def _trunk_section(self, V, F, yh, cz):
        S, _ = HR.plane_section(V, F, np.array([0.0, yh, 0.0]), np.array([0.0, 1.0, 0.0]))
        if len(S) == 0:
            return None
        tape, P2 = self._loop_tape(S, np.array([0.0, yh, cz]), np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0]))
        return P2

    # ---------------------------------------------------------------------------------- the measures
    def measure(self, Vall, surface=None, hip_step=10.0):
        """the measures (mm) of the body Vall (all hm08 vertices: the landmarks, joints and, unless surface is given,
        the sections' faces)"""
        B = HR.MHBody(self.sex, Vall)
        V = B.Vb
        J = B.joints
        L = self.L
        if surface is None:
            Vs, Ft, Fn, Fl, Fa, Fh = V, self.F_trunk, self.F_neck, self.F_leg, self.F_arm, self.F_hand
        else:
            Vs, Fs, qp = surface
            ok = qp >= 0

            def sel(k, keep_unmapped=False):
                m = np.zeros(len(Fs), bool)
                m[ok] = self.qmask[k][qp[ok]]
                if keep_unmapped:
                    m |= ~ok
                return Fs[m]
            # (the neck's sections also read the triangles of no hm08 quad: the head's and the neck's own rings)
            Ft, Fn, Fl, Fa, Fh = sel('trunk'), sel('neck', True), sel('leg'), sel('arm'), sel('hand')
        p = lambda k: V[L[k]]                   # noqa: E731
        m = {}
        for lm, key in (('acromion', 'acromialheight'), ('axilla', 'axillaheight'), ('chest', 'chestheight'),
                        ('suprasternale', 'suprasternaleheight'), ('cervicale', 'cervicaleheight'),
                        ('omphalion', 'waistheightomphalion'), ('trochanterion', 'trochanterionheight'),
                        ('crotch', 'crotchheight'), ('buttock', 'buttockheight'), ('mid_patella', 'kneeheightmidpatella'),
                        ('epicondyle', 'lateralfemoralepicondyleheight'), ('malleolus', 'lateralmalleolusheight')):
            m[key] = float(p(lm)[1])
        m['stature'] = float(V[:, 1].max()) if surface is None else float(Vs[:, 1].max())
        m['biacromialbreadth'] = 2.0 * float(p('acromion')[0])
        m['acromionradialelength'] = float(np.linalg.norm(p('acromion') - p('radiale')))
        m['radialestylionlength'] = float(np.linalg.norm(p('radiale') - p('stylion')))
        m['handlength'] = float(np.linalg.norm(p('stylion') - p('fingertip')))
        m['footlength'] = float(np.linalg.norm((p('toe') - p('heel'))[[0, 2]]))
        m['footbreadthhorizontal'] = float(np.ptp(V[self.foot, 0]))
        # the trunk: horizontal sections at the landmarks' heights, the loop round the trunk's centre (the mid z of
        # the front and back landmarks)
        cz_chest = 0.5 * (p('chest')[2] + p('cervicale')[2])
        cz_low = 0.5 * (p('omphalion')[2] + p('buttock')[2])
        for lm, gm, bm, dm, cz in (('chest', 'chestcircumference', 'chestbreadth', 'chestdepth', cz_chest),
                                   ('omphalion', 'waistcircumference', 'waistbreadth', 'waistdepth', cz_low),
                                   ('buttock', 'buttockcircumference', None, 'buttockdepth', cz_low)):
            P2 = self._trunk_section(Vs, Ft, float(p(lm)[1]), cz)
            if P2 is None:
                m[gm] = 0.0
                continue
            m[gm] = HR.hull_perimeter(P2)
            if bm:
                m[bm] = float(np.ptp(P2[:, 0]))
            m[dm] = float(np.ptp(P2[:, 1]))
        # ANSUR's hip breadth is taken standing with the heels together: in the A-pose the thighs splay, so a section
        # under the hips reads them apart (H2's maximum always fell at the search's lowest height, crotch + 20: +2.0 /
        # +1.5 sd). The search starts at the greater trochanter's height (the lead's H2b call), where the thighs leave
        # the pelvis
        best = 0.0
        for yh in np.arange(p('trochanterion')[1], p('omphalion')[1] - 40.0, hip_step):
            P2 = self._trunk_section(Vs, Ft, float(yh), cz_low)
            if P2 is not None:
                best = max(best, float(np.ptp(P2[:, 0])))
        m['hipbreadth'] = best
        # the neck: mid-neck (perpendicular to the axis through hm08's neck and head joints, at their midpoint: GNM's
        # definition, human_ref.neck_plane) and its base (the plane through the suprasternale and the cervicale)
        o, n = self.neck_plane(J)
        S, _ = HR.plane_section(Vs, Fn, o, n)
        if len(S):
            S = S[np.linalg.norm(S.mean(1) - o, axis=1) < 100.0]
            e1, e2, _ = HR.plane_basis(n)
            m['neckcircumference'] = self._loop_tape(S, o, e1, e2)[0]
        ob, nb = self.neck_base_plane(V)
        S, _ = HR.plane_section(Vs, Fn, ob, nb)
        if len(S):
            S = S[np.linalg.norm(S.mean(1) - ob, axis=1) < 110.0]
            e1, e2, _ = HR.plane_basis(nb)
            Pp = S.reshape(-1, 3) - ob
            m['neckcircumferencebase'] = HR.hull_perimeter(np.column_stack([Pp @ e1, Pp @ e2]))
        # the limbs
        legA = self._leg_axis(J)
        for st, key in (('thigh', 'thighcircumference'), ('lowerthigh', 'lowerthighcircumference'),
                        ('calf', 'calfcircumference'), ('ankle', 'anklecircumference')):
            m[key] = self._limb_girth(Vs, Fl, legA, self.leg_st[st], radius=130.0)
        armA = self._arm_axis(J, V)
        for st, key in (('biceps', 'bicepscircumferenceflexed'), ('forearm', 'forearmcircumferenceflexed'),
                        ('wrist', 'wristcircumference')):
            m[key] = self._limb_girth(Vs, Fa, armA, self.arm_st[st], radius=80.0)
        # the hand round the knuckles (thumb left out): the tape round EVERY segment of the section within 80 mm, as
        # H1 took it (the plane at the knuckles splits into the fingers' loops: the enclosing loop alone read 70 mm)
        wrj, mcp = J['l-hand'], J['l-finger-3-1']
        axh = (mcp - wrj) / np.linalg.norm(mcp - wrj)
        c = mcp - 5.0 * axh
        S, _ = HR.plane_section(Vs, Fh, c, axh)
        if len(S):
            S = S[np.linalg.norm(S.mean(1) - c, axis=1) < 80.0]
            e1, e2, _ = HR.plane_basis(axh)
            Pp = S.reshape(-1, 3) - c
            m['handcircumference'] = HR.hull_perimeter(np.column_stack([Pp @ e1, Pp @ e2]))
        return m

    @staticmethod
    def neck_plane(J):
        a, b = np.asarray(J['neck']), np.asarray(J['head'])
        n = (b - a) / np.linalg.norm(b - a)
        return 0.5 * (a + b), n

    def neck_base_plane(self, V):
        a, c = V[self.L['suprasternale']], V[self.L['cervicale']]
        u = (c - a) / np.linalg.norm(c - a)
        nrm = np.cross(np.array([1.0, 0.0, 0.0]), u)
        nrm *= np.sign(nrm[1])
        return 0.5 * (a + c), nrm

    def target_of(self, key):
        v = self.T[key]
        return v * self.flex[key] if key in self.flex else v

    def sd_of(self, key):
        reg = HS.SPEC['reg'][self.sex]
        return reg['stature'][1] if key == 'stature' else reg[key][6]

    def table(self, m):
        """per measure: value, target, residual sd, z"""
        out = {}
        for k, v in m.items():
            if k != 'stature' and k not in HS.SPEC['reg'][self.sex]:
                continue
            t, s = self.target_of(k), self.sd_of(k)
            out[k] = dict(value=float(v), target=float(t), sd=float(s), z=float((v - t) / s))
        return out


class Seam:
    """the head's neck ring against hm08's surface (SEAM's note). ring0: (K, 3) the head cage's neck ring on the sex's
    conditioned GNM (human_head.place(TH, g)['P'][TH.neck_ring], GNM's frame); gV, gF: GNM's mesh in that frame;
    stature: the sex's (mm). The head is placed as h2_build places it: its top at the stature, GNM's lower neck centred
    on the body's (human_hmcage.neck_align, on hm08's faceted body here)"""

    def __init__(self, ring0, gV, gF, stature, n=SEAM_N):
        self.ring0 = np.asarray(ring0, np.float64)
        self.gV, self.gF = np.asarray(gV, np.float64), np.asarray(gF, np.int64)
        self.t_y = float(stature) - float(self.gV[:, 1].max())
        K = len(self.ring0)
        self.pick = np.unique(np.round(np.linspace(0, K, n, endpoint=False)).astype(np.int64) % K)

    def gaps(self, V, L, F, all_points=False):
        """the signed radial gaps (mm, + = hm08 outside the ring) in the ring's plane at the picked ring points (every
        point with all_points; a miss is nan), the head's z shift, and the ring placed; V: all hm08 vertices (mm), L:
        the landmark ids, F: hm08's body triangles"""
        from .human_hmcage import neck_align
        Vb = np.asarray(V, np.float64)[:HR.mh_data()['nb']]
        S_, C_ = Vb[L['suprasternale']], Vb[L['cervicale']]
        t_z, _, _ = neck_align(Vb, F, S_, C_, self.gV + np.array([0.0, self.t_y, 0.0]), self.gF)
        R = self.ring0 + np.array([0.0, self.t_y, t_z])
        c = R.mean(0)
        nrm = np.linalg.svd(R - c)[2][2]
        D = (R - c) - np.outer((R - c) @ nrm, nrm)
        r = np.linalg.norm(D, axis=1)
        D /= r[:, None]
        idx = np.arange(len(R)) if all_points else self.pick
        t, _, _ = HR.TriMesh(Vb, F).ray(np.repeat(c[None, :], len(idx), 0), D[idx], 400.0)
        return np.where(t > 0, t - r[idx], np.nan), t_z, R

    def report(self, V, L, F):
        g, t_z, R = self.gaps(V, L, F, all_points=True)
        a = np.abs(g[np.isfinite(g)])
        i_f, i_b, i_s = int(np.argmax(R[:, 2])), int(np.argmin(R[:, 2])), int(np.argmax(R[:, 0]))
        return dict(p95=float(np.percentile(a, 95)), max=float(a.max()), front=float(g[i_f]), back=float(g[i_b]),
                    side=float(g[i_s]), misses=int((~np.isfinite(g)).sum()), t_z=float(t_z))


def smooth_surface(V, levels=2):
    """hm08's SMOOTH surface through the body vertices of V (human_ref.mh_smooth's construction: the Catmull-Clark cage
    whose limit interpolates them, subdivided `levels` levels to the limit), with each triangle's hm08 quad. Returns
    (Vs, Fs, quad)"""
    from ..mesh import QuadMesh
    from .. import subdiv_sharp as SS
    d = HR.mh_data()
    Vb = np.asarray(V, np.float64)[:d['nb']]
    cage = QuadMesh(Vb, d['Q'])
    V0, _ = SS.fit_controls(cage, {}, Vb, 0)
    lim, _, par, _ = SS.subdivide(QuadMesh(V0, d['Q']), {}, levels)
    F = lim.tris()
    return lim.V, F, np.asarray(par)[np.arange(len(F)) % len(lim.Q)]


# ============================================================================================ the solve
def solve(sex, log=print, outer=3, smooth_ratio=True, max_nfev=60, seam=None):
    """MakeHuman's own phenotype at ANSUR II's baseline (the module's docstring); seam: a Seam (the head's ring) reported
    after each pass and on the result (not solved for: SEAM's note). Returns dict(V (all hm08 vertices, mm), x, params,
    table (the faceted body's measures), smooth_table, landmarks, history, seam (its report, or None))"""
    from scipy.optimize import least_squares
    model = PhenoModel(sex)
    miss = model.missing()
    if miss:
        log(f'[pheno] {sex}: missing target files {miss}')
    x = model.x0.copy()
    keys = [k for k in PINNED]
    wts = np.array([PINNED_SEX.get(sex, {}).get(k, PINNED[k]) for k in keys])
    ratio = {k: 1.0 for k in GIRTHS}
    hist = []
    meas = None
    nreg = len(REGIONAL)
    for it in range(outer):
        V0 = model.build(x)
        meas = Measurer(sex, V0)
        T = np.array([meas.target_of(k) / (ratio[k] if k in ratio else 1.0) for k in keys])
        S = np.array([meas.sd_of(k) for k in keys])

        mr = np.array([MACRO_RIDGE.get(k, 0.0) for k in model.macro])

        def resid(xx):
            m = meas.measure(model.build(xx))
            r = np.array([(m.get(k, 0.0) - t) / s for k, t, s in zip(keys, T, S)]) * wts
            reg = RIDGE * xx[model.n_macro:model.n_macro + nreg]
            return np.concatenate([r, reg, mr * (xx[:model.n_macro] - 0.5)])
        r0 = resid(x)
        res = least_squares(resid, x, bounds=model.bounds, method='trf', diff_step=1e-3, x_scale='jac',
                            max_nfev=max_nfev, verbose=0)
        x = res.x
        r1 = res.fun[:len(keys)] / wts
        worst = int(np.argmax(np.abs(r1)))
        sr = ''
        if seam is not None:
            s_ = seam.report(model.build(x), meas.L, meas.B0.F)
            sr = (f'; the seam p95 {s_["p95"]:.2f} mm (front {s_["front"]:+.1f}, side {s_["side"]:+.1f}, back '
                  f'{s_["back"]:+.1f})')
        log(f'[pheno] {sex} pass {it}: cost {0.5 * float(r0 @ r0):.2f} -> {res.cost:.2f} in {res.nfev} evaluations; '
            f'worst {keys[worst]} {r1[worst]:+.3f} sd; {int((np.abs(r1) > 0.25).sum())} of {len(keys)} over 0.25 sd'
            + sr)
        hist.append(dict(it=it, cost=float(res.cost), nfev=int(res.nfev), worst=keys[worst],
                         worst_z=float(r1[worst])))
        if smooth_ratio:
            # the girths again on the smooth surface the cage carries (the limit through the vertices): their ratio to
            # the faceted mesh's goes into the next pass's targets
            Vb = model.build(x)
            mf = meas.measure(Vb)
            ms = meas.measure(Vb, surface=smooth_surface(Vb))
            for k in GIRTHS:
                if mf.get(k, 0) > 0 and ms.get(k, 0) > 0:
                    ratio[k] = ms[k] / mf[k]
            log(f'[pheno] {sex}: smooth / faceted girth ratios ' +
                ', '.join(f'{k[:10]} {ratio[k]:.4f}' for k in GIRTHS))
    V = model.build(x)
    meas = Measurer(sex, V)
    tab = meas.table(meas.measure(V))
    out = dict(V=V, x=x, params=model.params(x), table=tab, landmarks=meas.L, history=hist, ratio=ratio,
               seam=seam.report(V, meas.L, meas.B0.F) if seam is not None else None)
    if smooth_ratio:
        sm = smooth_surface(V)
        out['smooth_table'] = meas.table(meas.measure(V, surface=sm))
        out['smooth'] = sm
    return out
