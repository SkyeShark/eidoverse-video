"""CANID head archetype (WOLF_PLAN.md §2.2, §2.5, §4.2, §6.1): the head's landmarks, placed once for the skeleton (W1)
and for the head block-out (build_head, W2, reads the same table: AG 05.4, joint positions from the geometry
builder's own pivot data).

THE PALATE FRAME: origin the atlanto-occipital joint (the occipital condyles' centre: the `head` joint, AG 05.3: the
head nods at the skull base); p forward along the hard palate, pitched SPEC rest.palate_pitch below the horizontal;
q dorsal, perpendicular to p in the sagittal plane; +X the creature's left. A landmark is (p, q, x) metres.

The plan's stations (eye 0.49 H, jaw joint 0.69 H, ear 0.73 H) are fractions of H (SPEC head_len: nose tip to the
poll's skin) from the nose, taken along p between the nose tip and the poll; W2 moved the eye (0.53: its VISIBLE
centre, the lid opening on the cornea, ball_r ahead of the eyeball's centre, at the photos' 0.48 H) and the ear (0.86)
to the photographs. Everything else here is an ESTIMATE [E] from canid skull anatomy, checked against the skull table
(w01 prints CbL and ToL from these landmarks) and re-fitted at W2 against the traced head profiles and fronts.

W2c (the lead's W2b review: "primitives read as primitives"): the head is no longer built from primitives. Its VOLUME is
heads/canid_hull.py's: the visual hull of the traced skin silhouettes (the profile, the top, the front photos) and the
skull's cross-sections (HEAD face / jaw below: the measured skull's half-sections, now a limit, not a swept polygon),
rounded by a constrained curvature flow with the skull's landmarks held at their skin depths, then sculpted (the domed
leather, the philtrum, the mouth line, the brows, the orbits and the eye openings); it enters the program as ONE grid
member (sdf.Program.grid, the staged patch work/bestiary/patches/sdf_grid.md). The ears are cupped shells on a base that
runs front to back along the head (HEAD ear), each over a muscle mound.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator

POLL = (-0.030, 0.076)       # [E] the poll's skin from the AO joint: the inion ~25 mm behind and ~70 mm over the
                             # condyles (ToL from the prosthion then 267 against 265), plus ~6-8 mm of skin and muscle
NOSE_Q = 0.018               # [E] the nose tip's height over the AO joint (the planum ~30 mm over the prosthion)
PROSTHION = (-0.015, -0.030)  # [E] the upper incisors' front from the nose tip (the palate ~12 mm under the condyles)
TMJ_STATION, TMJ_Q = 0.723, -0.009   # [P] W3 head: the jaw joint at the mandibular condyle of the two scaled skulls
                                     # (research/wolf_work/data/res_skull_s12092001.json, mapped by the occipital
                                     # condyle -> AO and the prosthion -> PROSTHION at CbL 237): d 193.4 / 202.0 mm back
                                     # from the nose, q -8.6 / -9.2 (3 mm over the palate's line, not 17 over it); TMJ to
                                     # the chin then 181 mm (MdL 189 [P] includes the condyle's back). §6.1 had 0.69 H, q 5
CHIN = (-0.004, -0.032)      # [E] closed: the lower incisors' front, p from the prosthion, q from the AO joint
EYE_Q, EYE_ELEV = 0.032, 12.0   # [P] [E] W2k (the lead's call: "seat the eyeball where the skull's orbit puts it"):
                                # the eye centres 32 mm over the AO joint, so the VISIBLE eye (ball_r along the optical
                                # axis) sits at q 34.5, the centre of MWNH 358's orbit rim (canid_skull SHAPE rim: its five
                                # points' mean (134.0, 34.5, 39.6)); the station (d) and the spacing (x) already put the
                                # visible eye at the rim's centre within 0.4 mm (they are the photos', 0.48 H and IO 80).
                                # W2-W2j's 28 [E] left it 4 mm low of the rim (W2i: "~3 mm ventral"). Optical axes 12 deg
                                # above the palate (about level at the bind's -15 deg palate), splayed SPEC eye.splay out
EYE_SEAT = (0.003, 0.003, 0.0015)  # [P] [E] W2t (the lead's call 1: "move the globe back as the bone says: MWNH 358's
                                   # orbit-rim centre (d 134 plus 8-10 mm) ... start at 3 mm and let the skull decide"):
                                   # p 6 -> 3 mm, the globe's centre at d 142.2 (W2n-W2s 139.2), reversing W2n's forward
                                   # move on two readings: the bone, and the side photos' gazes (W2s: +88..+101 deg out
                                   # from a 20 deg rest). THE SKULL: the uncarved bone stays 2.5-2.7 mm clear of the
                                   # globe at 0-4 mm back along d (2.2 at 6; canid_skull's periorbita 1.5:
                                   # work/bestiary/wolf/check_w2t/bone_clear.py), so it does not limit the move inside
                                   # the bone's window. THE SIDE GAZES (check_w2t/seat_gaze.py, the iris centre registered
                                   # on the canthi): turns from rest w11 80 -> 70, w01 55 -> 42, w04 52 -> 40, v031 68 ->
                                   # 59, v611 71 -> 59 deg at 3 mm: the seat moves them 10-13 deg, not to a plausible turn
                                   # (the canthi follow the seat ~40 %, carried through the cameras registered on the
                                   # visible eye). Traced on the FISSURE itself, three new Commons profiles solve at 29-41
                                   # deg of turn (check_w2t heldout_t.py, ref_profiles/trace.json), where those five are
                                   # traced on the dark zone's outer edge; every side photo's iris is round (facing its
                                   # camera). The cost here: the opening seen from the side moves back 2 mm (0.483 -> 0.490 H;
                                   # the profiles 0.476-0.483), so w02's stop reads 0.729 NE against 0.73.
                                   # W2n (the lead's call 2: "re-seat the globe and lids forward toward the profile
                                   # photos' corners ... measuring bone clearance"): p 2 -> 6 mm, the globe's centre at
                                   # d 139.2 (W2m 143.2). Measured under the like-for-like registration (canid_hull
                                   # .eye_landmark, the cameras re-solved for each seat): the opening seen from the side
                                   # (canid_hull.eye_opening_side, the profiles' own landmark) runs d 126.9 -> 141.7, its
                                   # middle 134.3 = 0.480 H (the profile photos 0.476-0.483; their canthi 123.9 -> 145.0,
                                   # middle 134.4); W2m's seat read 0.495 H, 6.5 mm forward 0.471 H. (With the corners
                                   # unpinned, canid_cage EYE pin: 126.8 -> 142.0, middle 134.4; the opening still 6 mm
                                   # shorter than the profiles' 21.1 mm: the canthi on the front rays sit 5.2 mm behind /
                                   # 3.7 mm ahead of the profiles' corners. W2n fresh eyes: eye_opening_side lets only the
                                   # ball hide the margin; with the skin hiding it too, the opening seen from the side runs
                                   # d 127.2 -> 140.2, 13.0 mm, middle 133.7 = 0.477 H, and the medial corner stays hidden,
                                   # behind the face skin: work/bestiary/wolf/check_w2n_fresh/corners.py.) The uncarved bone
                                   # stays 2.6 mm clear of the globe (canid_skull's periorbita 1.5; W2m 2.7); the centre
                                   # 4.2 mm behind MWNH 358's rim plane (W2m 6.4). The fresh eyes' ~6.5 mm was read on
                                   # W2m's apex-registered margin (its opening's middle at d 140.9): re-carrying the
                                   # corners through the like-for-like cameras moved the middle 2.4 mm forward by itself
                                   # (work/bestiary/wolf/check_w2n/seat_scan.py, logs/seat_scan_s0.txt). q and x kept: down
                                   # 1.5 mm costs 0.7 mm of clearance and 0.05 R of relief below; lateral 1.5 mm steepens
                                   # the cameras 2.7 deg (IO 81).
                                   # W2m (the lead's call 1: "move the globe FORWARD so the eye sits flush, as a real
                                   # canid's does ... so IO and the eye's station stay inside the photos' spread"): the
                                   # eyeball's centre moved (p forward, q, x lateral; m) from the W2k seat above, so the cornea
                                   # stands proud of MWNH 358's rim (the centre 6.4 mm behind its plane, was 9.9; the apex 3.7
                                   # in front, was 0.2) with the uncarved bone 2.7 mm clear of the globe (canid_skull's
                                   # periorbita 1.5). The move is a blend of the orbit's axis (26 up / 51 out: 3.5 mm along it)
                                   # held to the photos: the visible opening's middle (the photos' NE, "the middle of the lid
                                   # opening") at d 133.4 = 0.476 H (WOLF_BODY_PHOTOS 3.2: 0.476-0.483, n = 2; the apex 0.472),
                                   # the visible eyes 83 mm apart (IO 80 is the plan's estimate, unmeasured; the leather's 44 mm
                                   # is then 0.528 IO, the fronts 0.508-0.595, median 0.572). Along the orbit's axis alone a
                                   # flush seat needs 7-10 mm (NE 0.465-0.459 H, IO 90-94: outside both); x 3 mm (IO 86) tried
                                   # first: it steepened the solved cameras 8 deg (w12 49 -> 57) for 0.07 R of relief.
                                   # work/bestiary/wolf/check_w2m_head/eye_move.py scores the candidates. The SPEC's
                                   # eye.station / half_spacing still describe the W2 seat this offsets (wolf.py's tags)
LID_UP, LID_LO = 35.0, 30.0  # [E] the lid margins' centres this far above / below the optical axis (on the eyeball)
EAR_Q, EAR_X = 0.044, 0.044   # [E] W2u: 4 mm lower and 4 mm in (W2c-W2t 0.048 / 0.048), so the face construction's
                              # base line, turned round the head's corner by EAR_SWIVEL, enters the skin along its whole
                              # length with no column passing beside the head (check_w2u_ears frame_scan.py / f2: 0 of 55
                              # columns off the head). The rest of this note is W2c's:
                              # W2c: the ear root at the middle of the pinna's base (W2e: the pinna's reference, its
                              # tip SPEC ear.height along the axis from here; the rig's joint ear_0 is EAR_PIVOT), which runs
                              # front to back along the head (HEAD ear base: the side views' 76 mm base, d 207-213 ->
                              # 281-288 over the hair, WOLF_BODY_PHOTOS §3.2); the root at d 244 (SPEC ear.station
                              # 0.891). W3 (0.044, 0.042) at d 225 sat under a base chord that ran across the head, so
                              # the side view saw the pinna edge-on: a 38 mm spike (the W2b checker)
EAR_OUT, EAR_BACK, EAR_MID = 23.0, 15.0, 0.45  # [P] [E] W2w (the lead's call: "THE BIND reads as a wolf at ease: the
                                               # concha ~15-25 deg out of forward, between the alert pose (2 deg in of
                                               # forward) and the relaxed (79 deg out), with the splay and tilt mid-range
                                               # too, and the face construction's base re-fitted on the head's corner at
                                               # that carriage ... re-fit rather than rotate"): 23 out / 15 back with
                                               # EAR_SWIVEL -3 is W2u's bind (38 / 12 / +30) carried by (-26.3, -14.4,
                                               # +5.6) (work/bestiary/wolf/check_w2w_ears/bind_carriage.py), so the joint
                                               # axis leans 17 back and 15 out (W2u 15 / 28) and the photos' own poses,
                                               # re-derived about it (wolf.py ear.poses), sit either side of it in splay
                                               # and tilt; the tip at d 264 (w02's 245-268; 17-20 back put it at 267-271).
                                               # The face construction is laid out at this bind and its base found on the
                                               # skin there (every column enters the head: 0 of 51 off), not W2u's sheet
                                               # turned (which lifts its base off the skin)
                                               # W2t (the lead's call 4: "the bind at the joint fit 38 / 12 /
                                               # -9 (out / back / swivel): the middle of the range, so the skin deforms
                                               # least either way, and the best single carriage"): ONE carriage judged at
                                               # all 11 traced ears at once (check_w2s ear_joint.py j1, rebuilt exactly):
                                               # the mean outside excess 7.08 mm (W2s's 42 / 12 / 6 8.92, W2r's 34 / 8 / 0
                                               # 8.66, the per-axis median 10.84); the alert fronts and the relaxed sides
                                               # pull apart, so each has its own named pose about this bind (EAR_POSES)
                                               # (W2s, the lead's call 5, "the bind carriage from the solved
                                               # photo carriages (their median, relaxed and set wider)"): every traced
                                               # ear solved at the measured rim (w02_ears RIM 7.5 / 4 / 3.5; check_w2s
                                               # ear_bind.py e0): the carriages' median (swivel, splay, tilt) all (6,
                                               # -3, -6) deg, the inner-face ears (-1, -3, +1): the W2e bind itself (the
                                               # photos' ears scatter both ways round it: w12's swivelled in 29-41, w08's
                                               # turned out 60-122, r03's out 6-24), which stood tall and close in every
                                               # review render (the W2r fresh eyes: Doberman / jackal). RELAXED, tipped
                                               # back 4 deg more (8 -> 12), SET WIDER, 8 deg further out of the head's
                                               # dorsal direction (34 -> 42), the opening swivelled out by the median's
                                               # 6 (EAR_SWIVEL): the tips 196 -> 215 mm apart (r03 208, the alert fronts
                                               # 163-180, w08 242 rotated), 8 mm lower, the tip at d 258 (the photos
                                               # 253-264 over the hair)
                                               # (W2e head, the lead's call 1, "carry it at the front photos' consensus
                                               # angle, not upright": 34 out of the dorsal direction (W2d 24): each
                                               # traced front tip in its solved camera (work/bestiary/wolf/scratch_w2e/
                                               # ear_measure.py) against the bind's tip: |clay - photo| median over w08
                                               # / w12 / r03 9.6 mm at 32, 13.7 at 36 (r03's own two tips give 36.5 /
                                               # 36.7; W2d's 24: 18.7); 8 back, the SIDE views' (the tip at d 250, the
                                               # photos 253-264 over the hair)); ear_1 (the mid fold) at 0.45 of the way
                                               # from the joint to the tip
EAR_TIP_R = 0.010            # [P] [E] W2e head: the tip a 10 mm arc, the w02 gate's floor (rounded: 10-20): the wet r03's
                             # leather tip is narrower (12-14 mm across 9 mm under the tip, 7-9 at 4.5 on its ear plane:
                             # a ~6 mm radius; scratch_w2e/out/r03_pinna.json); W3 13 (w12's and w01's furred tips)
EAR_PIVOT = (236.0, 28.0, 52.0)   # [E] W2e head: the rig's ear JOINT (ear_0), (d, q, |x|) mm in the palate frame: the
                             # concha's base on the skin, low and lateral in the base (the auricle turns on its
                             # cartilaginous canal, not about the base's middle). About the base's middle (244, 48, 48)
                             # the w08 ears (rotated out, their medial edges leaving the fur 56 mm out) stay outside
                             # their furred outlines: this pinna w08_L / w08_R +3.5 / +8.6 mm p95 at the solver's best,
                             # pivots between (240, 38, 50) / (238, 32, 50) +2.6 / +4.9 and +3.7 / +2.2 (scratch_w2e
                             # ear_lab.py); about this pivot every traced ear fits.
                             # None: the joint at the base's middle (EAR_Q, EAR_X, SPEC ear.station: the pinna's own
                             # reference, its height and axis measured from there in either case)
EAR_SWIVEL = -3.0            # W2d head: the bind's opening normal (ear_frame e_n) swivelled this far (deg) about the
                             # axis, + turning it outward (set by the ear fit, work/bestiary/tests/w02_ears.py; W2t -9: the
                             # joint fit, EAR_OUT's note; W2s 6: the solved photo carriages' median swivel; W2d-W2r 0).
                             # W2w -3 (the lead's call: the bind at ease, EAR_OUT's note): the opening faces 20 deg out of
                             # forward and 6 up (ear_face_frame), between the alert fronts' (about forward) and the relaxed
                             # profiles' (about 88 out). The face plane stands nearer across the head than W2u's, and the
                             # base still meets the skin along every column on the head's corner (the anchor's turn below
                             # the feet); its front is carried forward along the crown by HEAD ear face 'reach'.
                             # W2u 30: the face construction lays its base along the face plane, so the swivel also sets
                             # where the base meets the head: at -9 the face plane stood across the head (the opening 10
                             # deg out) and the base ran from the crown down the back of the skull with the lateral
                             # columns off the head; +30 to +45 lays it diagonally round the head's corner (frame_scan),
                             # 30 the least turned. The bind's opening then faces 41 deg out of forward and 19.5 down
                             # (ear_face_frame), between the alert fronts' (the concha turned in 50 deg from here) and
                             # the relaxed profiles' (out 37): the bind stays mid-range in swivel (wolf.py ear.poses)
# W2d head (the lead's call 6): THE EAR JOINT'S RANGE for the per-photo carriage (w02_ears.py), about the root, from
# the bind: the swivel about the ear's own axis (+ the opening turned outward), the splay about the head's long axis
# (+ the ear tipped outward), the tilt about the lateral axis (+ tipped back); deg. [E]: a canid's pinna turns its
# opening from forward round to the side and back (the auricular muscles: w08's left ear shows its back to the camera),
# brings its tips together when pricked (w03), lies flat sideways when relaxed and back against the neck when cowed,
# and pricks forward when alert; no measured wolf range was found
# W2w: shifted with the bind (EAR_OUT's note: W2u's bind carried by (-26.3, -14.4, +5.6)) so the joint's ABSOLUTE window
# stays W2d-W2u's (-60..150, -40..60, -45..70 about W2u's bind; the W2w solve auditor: "do not widen it: the inward bound
# near -30 absolute is anatomical"; bind_carriage.py: -33.7..176.3, -25.6..74.4, -50.6..64.4), rounded to whole degrees
EAR_RANGE = ((-34.0, 176.0), (-26.0, 74.0), (-51.0, 64.0))
SNOUT = (0.22, 0.022)        # [E] the nose-wrinkle joint: station 0.22 H, inside the muzzle under its dorsum
NOSE_J = (0.012, -0.004)     # [E] the planum's centre: behind and under the nose tip
BROW = (0.006, 0.020, 0.037)     # [E] over each eye: forward, up, lateral
LIP_UP = (-0.028, -0.020, 0.029)  # [E] the upper lip over the canine: p from the prosthion, q, lateral (C1B 47 + lips)
LIP_LO = (-0.030, -0.036, 0.025)  # [E] the lower lip at the same station (closed; it rides the jaw)
TONGUE = (0.040, 0.085, 0.130, 0.165)   # [E] tongue_0..2 and the tip along the jaw line from the jaw joint (the tip
                                        # ~12 mm behind the chin)


def poll_offset(spec):
    """the poll's skin in the palate frame (p, q): the neck's reach is solved so the poll sits SPEC
    rest.occiput_ahead_wh ahead of the withers"""
    return np.array(POLL, np.float64)


def nose_p(spec):
    """the nose tip's p: |nose - poll| = head_len exactly"""
    return POLL[0] + float(np.sqrt(spec['head_len'] ** 2 - (POLL[1] - NOSE_Q) ** 2))


def station_p(spec, s):
    """p of the station s H from the nose (along p, between the nose tip and the poll)"""
    n = nose_p(spec)
    return n + s * (POLL[0] - n)


def _rot_pq(v, deg):
    """rotate a (p, q) vector by deg toward +q (negative opens the jaw)"""
    a = np.radians(deg)
    return np.array([v[0] * np.cos(a) - v[1] * np.sin(a), v[0] * np.sin(a) + v[1] * np.cos(a)])


def landmarks_pqx(spec):
    """every landmark in the palate frame: name -> (p, q, x) for points, and unit (p, q, x) directions for the axes
    (names ending in _dir); the left side only (x > 0, names ending _L), the right is its mirror"""
    H = spec['head_len']
    np_ = nose_p(spec)
    pro = np.array([np_ + PROSTHION[0], NOSE_Q + PROSTHION[1]])
    tmj = np.array([station_p(spec, TMJ_STATION), TMJ_Q])
    chin_c = np.array([pro[0] + CHIN[0], CHIN[1]])
    jaw_len = float(np.linalg.norm(chin_c - tmj))
    open_ = -spec['rest']['jaw_open']
    jd = _rot_pq((chin_c - tmj) / jaw_len, open_)
    on_jaw = lambda pq: tmj + _rot_pq(np.asarray(pq, np.float64) - tmj, open_)      # closed -> bound open
    L = dict(nose_tip=(np_, NOSE_Q, 0.0), poll=(POLL[0], POLL[1], 0.0), prosthion=(pro[0], pro[1], 0.0),
             tmj=(tmj[0], tmj[1], 0.0), chin_closed=(chin_c[0], chin_c[1], 0.0))
    ch = tmj + jaw_len * jd
    L['chin'] = (ch[0], ch[1], 0.0)
    L['jaw_dir'] = (jd[0], jd[1], 0.0)
    for k, d in enumerate(TONGUE):
        t = tmj + d * jd
        L['tongue_tip' if k == 3 else f'tongue_{k}'] = (t[0], t[1], 0.0)
    # eyes: elevation e above the p-x plane, azimuth s from p toward +x
    e, s, r = np.radians(EYE_ELEV), np.radians(spec['eye']['splay']), spec['eye']['ball_r']
    sph = lambda el: np.array([np.cos(s) * np.cos(el), np.sin(el), np.sin(s) * np.cos(el)])
    eye = np.array([station_p(spec, spec['eye']['station']), EYE_Q, spec['eye']['half_spacing']]) + np.asarray(EYE_SEAT)
    L['eye_L'] = tuple(eye)
    L['eye_dir_L'] = tuple(sph(e))
    L['lid_up_tip_L'] = tuple(eye + r * sph(e + np.radians(LID_UP)))
    L['lid_lo_tip_L'] = tuple(eye + r * sph(e - np.radians(LID_LO)))
    L['brow_L'] = (eye[0] + BROW[0], eye[1] + BROW[1], BROW[2])
    # ears: the tip from the base's middle (the pinna's reference), the joint at the pivot (ear_pivot), the mid fold
    # EAR_MID of the way from the joint to the tip
    root = np.array([station_p(spec, spec['ear']['station']), EAR_Q, EAR_X])
    ax = np.array([-np.tan(np.radians(EAR_BACK)), 1.0, np.tan(np.radians(EAR_OUT))])
    ax /= np.linalg.norm(ax)
    tip = root + spec['ear']['height'] * ax
    piv = ear_pivot(spec, 1)
    L['ear_0_L'] = tuple(piv)
    L['ear_1_L'] = tuple(piv + EAR_MID * (tip - piv))
    L['ear_tip_L'] = tuple(tip)
    # the face
    L['snout'] = (station_p(spec, SNOUT[0]), SNOUT[1], 0.0)
    L['nose'] = (np_ - NOSE_J[0], NOSE_Q + NOSE_J[1], 0.0)
    L['lip_up_L'] = (pro[0] + LIP_UP[0], LIP_UP[1], LIP_UP[2])
    lo = on_jaw((pro[0] + LIP_LO[0], LIP_LO[1]))
    L['lip_lo_L'] = (lo[0], lo[1], LIP_LO[2])
    L['jaw_len'] = jaw_len
    L['H'] = H
    return L


def landmarks(spec, ao, p_ax, q_ax):
    """the landmarks in world space for a head joint at `ao` with the palate frame's axes p_ax, q_ax (unit, in the
    sagittal plane): name -> np.array(3) (points and unit directions, left side and midline; mirror for _R), plus the
    scalars jaw_len and H"""
    X = np.array([1.0, 0.0, 0.0])
    out = {}
    for k, v in landmarks_pqx(spec).items():
        if np.isscalar(v):
            out[k] = float(v)
        elif k.endswith('_dir') or '_dir_' in k:
            out[k] = v[0] * p_ax + v[1] * q_ax + v[2] * X
        else:
            out[k] = np.asarray(ao, np.float64) + v[0] * p_ax + v[1] * q_ax + v[2] * X
    return out


# ------------------------------------------------------------------------------------------------ the head (W2)
# THE CANID HEAD, SKULL FIRST (the lead's W2 review: "build it over the measured skull, then the masses, then the
# skin"), in the palate frame: distances d run back from the nose tip along p (p = nose_p - d), q is dorsal, x lateral
# (the left; the right mirrors); in SKULL and HEAD they are MILLIMETRES (build_head converts).
#
# THE SKULL (SKULL below, [P]): two photographed skulls, measured by research/wolf_work/scripts/skull_measure.py on their
# segmented silhouettes (research/wolf_work/checks/s12092001_right_lateral.png, mwnh358_lateral_lateral.png,
# s12092001_top_dorsal.png): Specimen 12092001 (Canis lupus, a ruler in frame: 90.2 px/cm on the cloth) and Museum
# Wiesbaden MWNH 358 (Canis lupus, no scale), each mapped into this frame by its occipital condyle -> the AO joint and
# its prosthion -> PROSTHION, i.e. at the SPEC's CbL 237 [P] (Andersone & Ozolins 2000); breadths are the Latvian means
# (ZyB 143, C1B 47, EntB 47, LB 42, MB 79 [P]) on specimen 12092001's dorsal outline shape. They agree within 3 mm on the
# dorsal profile; the Wiesbaden orbit's opening centre (d 134, q 34.5) holds the SPEC's visible eye (d 134, q 30.5)
# within 4 mm, so the photo-fitted eye stands; specimen 12092001's orbit sits 7 mm further forward (individual).
# What the skull changed against W2 r17's coat-line fit: the forehead stood 6-11 mm UNDER the frontal bone at d 115-150
# (the "small cranium"); the jaw's hinge 14 mm lower (TMJ_Q); the head's widest at the zygomatic arches (155 mm at the
# skin, ZyB 143 + 2 x 6), the muzzle's flare at the carnassials, the narrow braincase behind the arches.
#
# THE CONSTRUCTION: the planes a modeller blocks in, as PSWEEPs (sdf.Program.psweep: a swept polygon, exact 2D distance,
# convex corners rounded by rho): the UPPER HEAD is one swept section from the muzzle's front to inside the neck; each
# key station is a half-section of nine points (the top midline, the dorsolateral edge of the flat top, the upper side,
# the mid side, the lower side, the lower side turning in, the lip margin, the inner lip, the bottom midline), each point
# keeping its role along the head (muzzle: the nasal dorsum's flat top, the steep flank, the lip flare; eye stations:
# the broad flat forehead, the brow over the orbit, the zygomatic arch; behind: the crown over the temporalis, the
# arch's root, the cheek). The stations are the skull's dorsal profile plus the skin (nasal 3.5 mm, frontal 4, crest 4
# [E]: no canine soft-tissue depths found), its breadths plus the skin and the temporal muscles (to the crest), the
# orbit's rim. The LOWER JAW is a second PSWEEP (the mandible's two bodies and the floor in one rounded section) that
# opens about the jaw joint; the NOSE LEATHER a short PSWEEP extruded along p from the photos' outline (a flat front
# face rounded by its own rho); the philtrum and the orbit's recess are SUBTRACT members; the masseters round cones from
# under the arches to the mandible's angles; the lips sweeps along the two margins. W2 r01-r17's single round sweep with
# lumps (brows, arches, nasal flanks, a disc nose) read as a pig-dog: a tube muzzle, no planes.
SKULL = dict(
    # the dorsal outline q (mm) at d (mm), the two specimens' mean (lateral silhouettes; mean |difference| 2.1 mm)
    dorsal=((44, 20.0), (54, 22.5), (64, 25.0), (74, 27.0), (84, 29.5), (94, 34.0), (104, 39.0), (114, 44.5), (124, 52.0),
            (134, 58.0), (144, 62.0), (154, 64.0), (164, 64.5), (174, 65.0), (184, 65.5), (194, 65.5), (204, 65.5),
            (214, 65.5), (224, 67.5), (234, 67.5), (244, 65.5), (254, 59.0)),
    # the mandible's ventral border (the mean; Wiesbaden's 6-8 mm shallower)
    ventral=((34, -42.0), (54, -49.5), (74, -52.5), (94, -55.5), (114, -56.5), (134, -56.5), (154, -52.0), (174, -42.0),
             (194, -39.0)),
    # landmarks (d, q, |x|) mm: |x| from the breadths (half), 0 on the midline
    prosthion=(15.0, -12.0, 0.0), rhinion=(36.0, 13.0, 0.0), stop=(84.0, 29.5, 0.0), canine=(30.0, -14.0, 23.5),
    entorbitale=(121.0, 40.0, 23.5), orbit=(134.0, 34.5, 34.0), postorbital=(141.0, 50.0, 33.0),
    postorbital_constriction=(169.0, 40.0, 21.0), zygion=(173.0, 15.0, 71.5), meatus=(213.0, -2.0, 44.0),
    # W2i (the lead's call 8): the otion RE-READ on s12092001_top at the real mastoid shoulders (the outline's posterior
    # corners, (2275, 778) / (2255, 1455) px: research/wolf_work/data/src/sk_s12092001_top.json; work/bestiary/wolf/
    # scratch_w2i/out/otion_top_R.png, otion_top_L.png): d 217.2, |x| 37.7 (MB 75.3, Latvian 79); W2h's (229.0, 39.5) was
    # read at (2390, 760) / (2390, 1455), in the photo's black background ~17 mm off the bone, and the flow's 2 mm ball
    # round it pushed the flowed head out at d 229 behind the skull's narrowing
    otion=(217.2, -4.0, 37.7), tmj=(198.0, -9.0, 36.0), inion=(254.0, 57.0, 0.0), crest=(194.0, 65.5, 0.0),
    frontal=(134.0, 58.0, 0.0), nasal=((54.0, 22.5, 0.0), (84.0, 29.5, 0.0)), mandible=(94.0, -55.5, 0.0),
    # the lower incisors' alveolus (the mandible's front between the central incisors; s12092001 only, MWNH 358's is
    # hidden by its canines): the lower lip and the procumbent incisor crowns stand in front of it; the lower incisor
    # crowns' labial face at the occlusal line, read off both lateral skulls under the closed head at the SPEC scale
    # (the condyle -> AO, prosthion -> PROSTHION similarity; +-1.5 mm): a closed mouth's lower lip covers it (W3 check)
    infradentale=(24.6, -34.8, 0.0), incisor_lo=(16.0, -20.5, 0.0),
    # the gate's skin depths over the bone (mm), [E] from dog head anatomy (no wolf or dog soft-tissue table found:
    # a web search returned human facial-depth studies only): skin 1.5-2.5 mm plus fascia, thicker where muscle lies;
    # the chin's forward from the infradentale: the incisor crowns (~5 mm forward of their alveoli) plus the lower lip
    depths=dict(nasal=(2.0, 7.0), stop=(3.0, 12.0), frontal=(3.0, 8.0), crest=(3.0, 10.0), zygion=(3.0, 10.0),
                canine=(3.0, 9.0), mandible=(4.0, 14.0), chin=(6.0, 16.0)),
)
HEAD = dict(
    # W2j (the lead, SURFACE FIRST): 'cage': the head is ONE SUBDIVISION SURFACE (heads/canid_cage.py: a quad cage whose
    # loops sit on the traced features, creased semi-sharp where the face has edges, its limit mesh the head's GRID by the
    # exact distance), the globes the only analytic members; W2h (the lead's call 1, THE HEAD SKULL-FIRST) 'skull': the
    # head's base volume the SKIN OVER THE SKULL (heads/canid_skull.py, canid_skin.py: the wolf skull from its museum
    # views, the fossae's muscles, the tissue depths), the features on it (canid_hull.sculpt_skull); 'hull': W2c-W2g's
    # visual hull of the furred silhouettes, flowed, sculpted
    method='cage',
    k_group=0.022,            # the head group into the neck (m): at 0.012 the junction read as a collar (r03)
    stop=100.0,               # the skin's stop (mm back from the nose: the lead's 0.76 NE; the bone breaks at d 84,
                              # SKULL stop: the photos' 0.757 NE is the COAT's break, the forehead hair 5-10 mm deeper
                              # than the muzzle's); the muzzle region ahead of it (species REGIONS)
    # ---- the upper head (PSWEEP): the centreline (straight, along p at q mm), the corner radius, the node step and the
    # smoothing of the key points along d (mm), and the key stations (d, nine (|x|, q) points: top midline, dorsolateral
    # edge, upper side, mid side, lower side, lower side turning in, lip margin, inner lip, bottom midline)
    face_sigma=8.0,           # W2c: the stations' smoothing along d (mm) where canid_hull reads them as the skull's
                              # cross-sections (W2b swept them as a PSWEEP of corner radius 7 mm: the faceted plank)
    face=(
        # the muzzle's front (the upper lip's front face, 4 mm behind the leather's face once rounded): narrower than the
        # leather at the leather's height, so the leather's alae stand proud of the bridge and its back half sinks into
        # it; the lips widening below it and hanging to q -20, over the chin's top (-21.5): a closed mouth's upper lip
        # covers the lower (W3 w3b's front ended at -16, 5 mm over the chin, and the mouth read as a slot). Shapes
        # shorter than ~20 mm along d do not survive face_sigma's smoothing (W3 h10: an arched lip margin over d 11-19
        # printed as nothing)
        (11, ((0, 25.0), (10.0, 24.5), (14.5, 19.5), (18.0, 8.0), (20.0, -4.0), (19.5, -11.0), (15.5, -17.0),
              (7.5, -19.5), (0, -20.0))),
        # the canines (C1B 47 + the lips: 56 mm at the lip flare); the nasal dorsum flat, 26 mm wide
        (28, ((0, 26.0), (13, 25.5), (21, 18.0), (25.5, 5.0), (28.0, -8.0), (27.0, -16.0), (20, -21.0), (9, -23.0),
              (0, -23.5))),
        (50, ((0, 26.5), (14.5, 26.0), (22.5, 18.0), (26.5, 4.0), (28.5, -12.0), (27.5, -22.0), (20, -28.0), (9, -30.0),
              (0, -30.5))),
        (75, ((0, 31.0), (15.5, 30.5), (25, 21.0), (29.5, 5.0), (31.5, -15.0), (30.5, -27.0), (22, -35.0),
              (10, -37.0), (0, -37.5))),
        # the carnassial (the maxilla's flare) and the commissure
        (95, ((0, 38.5), (17, 38.0), (28, 28.0), (37, 10.0), (40.0, -14.0), (39.0, -28.0), (29, -37.0), (12, -39.0),
              (0, -39.5))),
        # the stop; the forehead broadens, the jugal's front root flares the cheek: the arch point rises evenly from
        # here to the zygion (~0.5 mm per mm, the skull's own outline: a steeper flare raised the PSWEEP's divisor, so
        # the whole face's field read weaker)
        (110, ((0, 46.0), (19, 45.0), (30, 37.0), (44, 15.0), (45.0, -11.0), (43.0, -26.0), (33, -36.0), (13, -38.0),
               (0, -38.5))),
        (125, ((0, 56.5), (22, 55.0), (31, 47.0), (51.5, 15.0), (50.0, -9.0), (47.0, -24.0), (37, -33.0), (15, -36.0),
               (0, -36.5))),
        # the eye: the broad flat forehead, the brow (the supraorbital margin, x 33 at q 54), the arch under the orbit
        (140, ((0, 64.5), (24, 63.0), (34, 54.0), (60, 15.0), (57.0, -8.0), (52.0, -22.0), (41, -30.0), (16, -34.0),
               (0, -34.5))),
        (155, ((0, 68.0), (25, 66.5), (37, 58.0), (69, 15.0), (65.0, -7.0), (57.0, -21.0), (46, -28.0), (17, -32.0),
               (0, -32.5))),
        # the zygion (ZyB 143 + 2 x 5.5 of skin after the rounding and the smoothing: W3 w3b's 75.5 printed 146 at the
        # skin, 1.2 mm over the arch); the crown over the temporal muscles to the crest
        (175, ((0, 69.5), (24, 68.0), (42, 59.0), (79.5, 14.0), (69.0, -8.0), (60.0, -21.0), (49, -28.0), (18, -31.0),
               (0, -31.5))),
        (195, ((0, 70.0), (24, 68.5), (42, 60.0), (72.5, 13.0), (61.0, -9.0), (54.0, -21.0), (44, -27.0), (17, -30.0),
               (0, -30.5))),
        # behind the arches: the braincase under the temporalis, the ear bases, the mastoids (MB 79)
        (215, ((0, 70.5), (23, 69.0), (39, 60.0), (61, 17.0), (51.0, -4.0), (46.0, -15.0), (37, -21.0), (15, -25.0),
               (0, -25.5))),
        (235, ((0, 71.5), (22, 70.0), (37, 61.0), (51.5, 19.0), (44.0, 0.0), (40.0, -10.0), (32, -16.0), (13, -20.0),
               (0, -20.5))),
        # the poll (the inion d 254), then into the neck
        (255, ((0, 63.0), (20, 61.5), (34, 53.0), (45, 17.0), (40.0, 0.0), (36.0, -8.0), (28, -13.0), (12, -17.0),
               (0, -17.5))),
        (275, ((0, 52.0), (17, 51.0), (29, 45.0), (39, 15.0), (35.0, 0.0), (31.0, -6.0), (24, -10.0), (10, -12.0),
               (0, -12.5))),
        (290, ((0, 42.0), (14, 41.0), (24, 36.0), (32, 13.0), (29.0, 1.0), (26.0, -3.0), (20, -6.0), (8, -8.0),
               (0, -8.5))),
    ),
    # ---- the lower jaw (PSWEEP), closed (the bind opens it about the jaw joint): stations (d, nine (|x|, q): the top
    # midline inside the mouth, the lower lip's margin, the mandible's upper side, mid side, widest, lower side, the
    # ventral border, the floor, the bottom midline); its ventral line the skull's mandible plus 6-8 mm of skin and the
    # digastric, behind d 150 the intermandibular soft tissue to the throat (the photos' jaw line, w10 / w11)
    jaw=(
        # the lower lip's front (W3 check): the d 22 section scaled about its top midline (|x| 0.85, the depth under the
        # top 0.80), so the chin runs from under the upper lip down and back into it, its skin at d ~11 (the PSWEEP's
        # rounded cap stands rho ahead of its first node). With the front cap at d 22 the chin's skin stood at d 15-16,
        # 11 mm behind the upper lip's front (the photos' lower lip front d 3-12: w10, w01, w11), and the lower incisor
        # crowns (SKULL incisor_lo) stood outside the closed head at the mouth line (work/bestiary/wolf/review_w03/
        # run_chin.txt; the scaled skulls under the profile: review_w03/out/ov_skull_*)
        (17, ((0, -21.0), (8.5, -21.0), (11.5, -24.2), (12.3, -27.8), (11.9, -31.4), (10.2, -34.6), (6.8, -36.2),
              (3.0, -36.6), (0, -36.6))),
        # the chin: the lower lip 10 mm behind the upper lip's front face (the lower incisors inside the upper), rounded
        (22, ((0, -21.0), (10, -21.0), (13.5, -25.0), (14.5, -29.5), (14.0, -34.0), (12.0, -38.0), (8, -40.0),
              (3.5, -40.5), (0, -40.5))),
        (30, ((0, -24.0), (14, -23.0), (17.5, -28.0), (18.5, -34.0), (18.0, -40.0), (15.0, -45.0), (9, -48.0),
              (4, -48.5), (0, -48.5))),
        (60, ((0, -31.0), (19, -29.5), (23, -35.0), (24.0, -42.0), (23.5, -49.0), (20.0, -54.0), (13, -56.5),
              (5, -57.0), (0, -57.0))),
        (95, ((0, -37.0), (25, -36.5), (29, -42.0), (30.5, -49.0), (30.0, -56.0), (27.0, -61.0), (19, -63.0),
              (7, -63.5), (0, -63.5))),
        (130, ((0, -39.0), (31, -38.5), (35, -44.0), (36.5, -51.0), (36.0, -58.0), (33.0, -63.0), (25, -65.0),
               (9, -65.5), (0, -65.5))),
        (165, ((0, -36.0), (35, -35.0), (39, -41.0), (40.5, -49.0), (40.0, -56.0), (37.0, -61.5), (29, -64.0),
               (11, -64.5), (0, -64.5))),
        (195, ((0, -28.0), (37, -27.0), (41, -34.0), (42.5, -42.0), (42.0, -50.0), (38.0, -55.0), (30, -57.5),
               (12, -58.0), (0, -58.0))),
        (212, ((0, -22.0), (34, -21.0), (38, -27.0), (39.0, -34.0), (38.0, -41.0), (34.0, -46.0), (27, -48.0),
               (10, -48.5), (0, -48.5))),
    ),
    # ---- the nose leather: its front outline as a half polygon (|x|, z) mm about its centre q (the photos: 41-46 mm
    # wide, 25-30 tall in profile; w12's traced outline: a broad top arc, the alae widest just under the middle,
    # narrowing to the philtrum). W2c: the nose's cross-sections ahead of the face's first station (canid_hull's
    # section field, fitted to the profile and top views) and the domed leather's outline (canid_hull.STROKES)
    nose=dict(outline=((0, 13.5), (9, 13.0), (16, 11.3), (20.5, 7.2), (22.0, 1.0), (21.0, -4.5), (17.5, -9.0),
                       (11.5, -12.0), (5, -13.0), (0, -13.2)),
              centre_q=12.5),
    # ---- W2d head (the lead's call 7): THE NARES, analytic members over the head's grid (canid_hull.nares_members, a
    # SUBTRACT group in build_head): smooth at any scale (the W2c check carved them into the 1 mm grid: ragged rims).
    # Measured on w12 (5.56 px/mm at IO 80; work/bestiary/wolf/scratch_w2dh/out/w12_nose.png): each opening 11-13 mm
    # across at |x| 5.5-16 (the septum 11 mm), in the lower half of the front face, the ala a rounded lobe lateral to it
    # (canid_hull STROKES alae) and the slit running out, down and back round the ala (w06's three-quarter: the comma).
    # Here: the opening's centre (|x| 10.5, q 8) on the leather's skin, sunk 2.5 mm, half-axes across / up / in
    # (6.6, 3.4, 8.0) mm, its long axis turned down laterally tilt_uv 28 deg (the comma's head medial, its tail
    # lateral), its canal into the head tipped up and medial; the slit through (|x|, q, radius) mm on the skin, 0.4 mm
    # under it; k the group's smooth subtraction, slit_k the members' union (mm). In w12's own camera (scratch_w2dh/
    # leather_vs_w12.py) the W2c check's q 5 (w12's image proportions read onto the front face, the planum seen from
    # above ignored) put the openings 8-9 mm below w12's; q 8 (3 mm under the tip) leaves 7-8, 11 mm across (w12
    # 10.8-13); higher would put them at the tip's height in profile. OPEN (W2d report): down the leather as the clay
    # shows it (the skin within 3 mm of canid_hull's pad), the openings sit 0.91 in w12's camera (w12 0.65-0.68) and
    # 0.86 in w08's (w08 0.56; scratch_w2dh/leather_vs_w08.py), while the profile w11 shows its naris 0.60 down its
    # traced leather (the clay 0.54) and the clay's midline profile keeps the traced one within 1 mm: the fronts see the
    # leather's sides (the round dome's rim 13 mm behind the front) lifted over the openings
    # W2e head (the lead's call 2: "the nares at 0.56-0.68 down as commas with the alar slits rising up and out"): the
    # openings at q 12.5 (W2d 8), at the profile's tip height (the midline's front-most point q 10.0: they stay at the
    # front in profile), faced a little more laterally (tilt_in 0.45; W2d 0.30) as the profiles show the comma on the
    # side face; the slit short and on the leather's front, from the opening's lateral rim UP and OUT round the ala
    # (w12: scratch_w2e/out/w12_nares.png; W2d's ran out and down). Down the leather in the solved cameras
    # (scratch_w2e/nose_lab.py): w08 0.67 [w08 0.56; W2d 0.86], w12 0.74 [w12's own on its traced leather 0.69; W2d
    # 0.91]; higher would put them over the profile's tip (q 15 for w12's 0.69)
    # W2e check: |x| 9.3 (was 10.5), the slit moved with them: the leather narrowed (89 -> 77 px in w08's camera) while
    # the openings stayed, so they stood 0.50 of its width apart in both solved cameras against w08's 0.44 and w12's
    # 0.45 (check_w2e/nose_lab.py: 0.44 / 0.44 now). OPEN: in w12's camera each opening shows 10.5 x 3.8 mm (aspect
    # 2.8) against w12's own 11.1-11.5 x 8.1-8.2 (1.37): flat slots; simply rounder ellipsoids read as drilled coins
    # (check_w2e/out/nose_chk_n1.png): the comma needs the ala as a rolled lobe over the opening's lateral part
    # W2f (the lead's call 2: "each nostril's comma and the thick rolled ALAR LOBE over its lateral part ... the nares at
    # 0.56-0.69 down the leather"): the opening where w12's traced naris centre lands on the leather through its solved
    # camera (canid_hull.NOSE_W12 opening; work/bestiary/wolf/scratch_w2f/nares_place.py: d 1.8, q 11.7, |x| 12.1), rounder
    # (w12's own openings 11.1-11.5 x 8.1-8.2 mm, aspect 1.37), the comma's tail the traced dark core's lateral run carried
    # onto the skin the same way (|x| 15.0 / 16.8 / 18.2 at q 9.7 / 9.0 / 8.4: out and a little DOWN, under the alar lobe,
    # canid_hull.STROKES alar_lobes), sunk slit_sink under the lobe's edge so the lobe overhangs it; the canal 13 mm deep
    # (half-axis in; W2e 8): a shallower cavity rendered as a lit dish, a drilled oval, not an opening into the nose
    # W2g (the lead's call 3: "the nostrils dark COMMAS: deep canals turning laterally under THICK rolled alar folds ...;
    # the philtrum a real GROOVE splitting the upper lip"; canid_hull.nose_members, analytic_groups): round the opening's
    # centre S (the same place, w12's traced naris centre through its solved camera: |x| 12.1, q 11.7) in the skin's frame
    # (the outward normal, lateral, dorsal): the ALA a thick roll (r up to 4.3 mm, its crest ~2.2 mm proud) round the
    # opening's dorsolateral and lateral rim from 60 deg over lateral to 88 under it, 6.4-7.9 mm out (w12: the pale crest
    # of each ala 5.1-6.7 mm from its opening's centre, the fold's outer slope out to the leather's edge 11-12 mm,
    # NOSE_W12 ala; with the W2d bump STROKES alae under it); the MOUTH an ellipsoid 9.0 x 6.2 mm (w12's openings
    # 11.3 x 8.15) turned 14 deg (the comma's lateral
    # end down), its long axis INTO the head along the CANAL, which runs in and down (back along w12's line of sight,
    # 51 deg over the palate: a canal turning up and back showed its lit floor, W2f's "lit flat-floored holes") 15 mm,
    # narrowing 3.3 -> 2.4 mm; the ALAR SLIT the comma's tail out and down under the ala's lower end; in w12's camera the
    # openings read dark over 6.4 % of the leather (the photo 8.1 %: w02 'the nose's read'); the PHILTRUM a chain
    # widening down the lip (r 1.8 -> 3.2 mm, 0.6 -> 1.3 deep) from between the openings to under the lip margin.
    # W2f's ellipsoid openings, slit cones and alar_lobes stroke replaced. Chains hard-unioned (step 1 mm: beads at W2f)
    # W2h (the lead's call 2): on the traced rhinarium a round mouth 10.0 x 8.8 mm turned 25 deg, the canal down w12's
    # line of sight 18 mm (5.0 -> 3.1), the alar roll from 100 deg to -75: from the front two near-circular drilled holes
    # with raised rings, low on the pillow (0.74-0.76 down), their floors lit grey (the canal along the line of sight
    # shows its far end to the camera), the alae lumps above them (the W2h checker; the lead's W2i list).
    # W2i (the lead's call 2: "THE NOSE TRACED, not described ... each opening as its traced outline swept INTO the
    # leather, the canal turning up and back after about 5 mm (the vestibule) so its end self-shadows from every front
    # camera; the alar fold the rolled rim over the comma's head and outer side; the nostrils at w12's height on the
    # leather"): canid_hull.nostrils_traced on the tracings canid_hull.NOSE_W12 open_*, fold_in_*, fold_out_* (traced on
    # w12 at 7x, work/bestiary/wolf/scratch_w2i/out/w12_naris_*_trace.png), carried onto the leather through w12's solved
    # camera, so the openings' outline, size and height come from the photo itself. opening: the PSWEEP's start 'out' mm
    # outside the skin, the vestibule 'vest' mm in along the inward normal, widening 'under' mm toward the fold's side
    # over under_d mm (key 1), its section scaled to vest_scale at its end; the canal turning toward 'turn' deg up from
    # the palate's back direction on an arc of arc_r mm (>= the section's reach / 0.8: the PSWEEP's band), then 'canal'
    # mm on, its section to end_scale; corners rounded rho (mm). fold_r: the alar roll's radius clamp (mm), fold_h its
    # axis along the normal from the skin (mm), fold_kg the fold group's union into the head (mm). slit: (length mm, rise
    # per mm back, radius at its start and end, its axis' sink under the skin) from the opening's lateral end back along
    # the side; slit_k the slit chain's own union, k the subtract group's (the rims' rounding, mm)
    # W2i h3: the traced opening (the dark comma and the lit vestibule floor round it, NOSE_W12 open_*) a 'recess' mm
    # recess; the traced DARK core (NOSE_W12 dark_*) the canal's mouth: in along the line of sight 'vest' mm narrowing to
    # vest_scale (the throat), then the turn (h2's 5 mm vestibule of the whole outline then an 11 mm arc showed the
    # bend's wall face-on to w12's camera, lit: 1.4 % dark against the photo's 8.1 %)
    nares=dict(opening=dict(out=2.5, vest=9.0, under=0.0, under_d=(0.5, 3.0), vest_scale=0.5, turn=50.0,
                            arc_r=9.0, canal=5.0, end_scale=0.4, rho=0.5),
               fold_r=(1.2, 2.4), fold_h=-0.3, fold_kg=1.2, slit=(9.0, 0.35, 1.0, 0.5, 0.5), slit_k=0.6, k=0.8,
               step=1.0,
               # W2h (the lead's call 2: "the philtrum a groove splitting only the upper lip"): from between the openings
               # to the lip margin (LIP_LINE q -21 at the front), its depth easing out over the last rows (W2g's ran to q
               # -24 at 1.3 mm, past the margin into the mouth crease)
               philtrum=dict(q=(4, 1, -2, -5, -8, -11, -14, -17, -19.5),
                             r=(1.6, 1.7, 1.8, 2.0, 2.2, 2.3, 2.4, 2.3, 2.0),
                             groove=(0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 0.9, 0.55, 0.15), step=1.0)),
    # ---- the ears (W2c, SHELL): a cupped, rolled pinna on a BASE that runs front to back along the head, so the side
    # view sees its broad base (the photos' 76 mm over the hair, d 207-213 -> 281-288; the W2b checker's targets: the
    # side-view base 62-80 mm at the skin, the tip at d 245-268, the inner bases 75-81 mm apart, the tips 165-180):
    # base (d, |x|) mm on the skin (their q found on the head's surface, then sunk sink_base mm), from the medial-front
    # end on the crown, round the head's top side, to the posterior end over the occiput; the sheet lofted from the base
    # to the tip's 13 mm arc (EAR_TIP_R round the rig's ear tip), cupped `cup` m at mid-base (the concave side forward
    # and out), its edges rolled `roll` m inward (toward the base's middle), continued `sink` m below the base inside
    # the head; facet m; k into the head; the MOUND, the auricular muscles, a round cone ((d, q, |x|) mm, radii m, k)
    # under the base's middle
    # W2c r3 (looked at on the cached head, scratch_w2c/ear_view.py): the base (d, |x|) runs front to back on the
    # head's dorsolateral skin, sliding down the back of the cranium (q 65 -> 30); r1's last point (275, 34) lay off
    # the head grid (its footprint ends at d ~272, half-width 32 mm at d 270), so its q fell back to the profile's top and
    # that corner floated: the side view read 86 mm. A C base opening forward and out (looked at: variants cB, cC)
    # rolls the shell into a horn on this head (its half-width falls to 40 mm at d 265); the cup now bends the sheet along
    # its own normal (r1's along e_n slid it within itself) and the rims roll toward the inside
    # W2c CHECK (the clay drawn on the photos, work/bestiary/wolf/check_w2c/out/ov_front_*.png): that sheet's base ran
    # front to back at |x| 32-38, so every front camera saw it edge-on: on w12, r03, w07 and w08 (w08 and w07 never
    # carved the hull) the clay's ear was the photo ear's MEDIAL EDGE ONLY (its base 6-9 mm across the image against
    # the photos' 58-66 mm ear; r03's traced lateral edge, front_r03.json notes, runs down to meet the cheek outline).
    # The pinna is now a cone-like sheet whose section is a C (the concha's back) opening forward and out: three
    # borders from a base on the skin to the tip's arc -- MEDIAL from the crown (m0: the inner bases 74 mm apart, the
    # W2b checker's 75-81), the C's BACK from behind the crown (k0), LATERAL from the side of the head (l0), turning
    # out fast (the concha's wall) and rising nearly vertical, as the photos' outer edge does from the tip down to the
    # temple -- each height's section a quadratic through the three, the two edges rolled inward. The base points are
    # (d, |x|) mm on the closed head's skin (sunk sink_base); the controls (v, d, |x|) mm along each border (v the height
    # fraction; q runs straight from the base to the tip's arc); the tip, the axis and the height stay the rig's
    # (ear_frame, SPEC ear), so the skeleton is unchanged. Trials t1-t5 on the cached head: check_w2c/ear_proto.py
    # W2d head (the lead's call 6: the ears inside every furred outline): the borders are now straight lines from the
    # base to the arc plus one bulge each (ear_shell): bm the medial out medially, bl the lateral out laterally (its
    # profile sin(pi v)^gl), bk the back backward (0: the fit left the cup's depth to the base, k0 behind the m0-l0
    # chord); one pinna shape fitted with each traced ear's carriage on the furred outlines of the fronts w12, r03, w07,
    # w08 and the profiles w01, w03 (research/wolf_work/data/src/ears_w2d.json; work/bestiary/wolf/scratch_w2dh/
    # fit_ears2.py fit E: the rig's root, the base held on the skull's surface, each ear's visible face honoured): the
    # lateral base at (231, 56) on the side of the head, bm 4.2, bl 22.6 (the lateral border 22.6 mm out at mid-height:
    # the fronts' lateral edges stand at |x| 98-123 over the fur), the height 97.7 mm from the root (SPEC ear); the
    # inner base then set at (205, 38) (76 apart: the fronts 71-81 where the medial edge leaves the crown fur; fit E's
    # 42 off the midline put it under the side view's crown line) and the back at d 266: the side-view base 70 mm, the
    # gate's 62-80 (scratch_w2dh/sideview_base.py, the program's own blend and mound; fit E's 53)
    # W2e head (the lead's call 1: "the leather pinna's height, base and outline from the WET wolf r03 ... inside EVERY
    # furred outline ... at the front photos' consensus angle"): r03's two wet ears in its solved camera, the fore / back
    # tilt held at the side views' (EAR_BACK), give the tip (H 89.3 / 94.3 mm from the base's middle, the leather 87.8 /
    # 92.8 less the wet rim: SPEC 0.090) and on each ear's plane a broad-based triangle (the widths, less the rim: 53 mm at
    # 0.40 of the height, 45 at 0.50, 36 / 37 at 0.60, 29 / 30 at 0.70, 21 / 22 at 0.80, 12 / 14 at 0.90; the medial edge
    # nearly straight 15-18 mm in of the axis, the lateral bulging low: work/bestiary/wolf/scratch_w2e/ear_measure.py,
    # out/r03_pinna.json). W2d's bulges ran along the base chord (back and out: a front camera saw them foreshortened)
    # and peaked at mid-height (the leaf); now along the opening's across direction (bulge_dir 'across'), the lateral
    # peaking at 0.30 of the height (kl 0.576, 24 mm, gl 1.5). The medial base out at the side of the crown (m0 (214, 55),
    # W2d (205, 38)) and its border bowed in low (bm -6 at 0.34, km 0.55): w12_R's and w08's medial edges leave the fur
    # 50-56 mm out, and their chord LINES count the clay above them (scratch_w2e chord_probe.py); the medial border's foot
    # reaching FORWARD along the crown at the head line's height (bf 26 mm at 0.34, kf 0.65) so the side view's base
    # starts at d ~204 (the photos 207-213 over the hair). Every traced ear inside at the gate's own solve (ear_lab.py,
    # j3 / n1: worst p95 +1.5-1.7 mm, w12_R +0.8, w08_R +1.5); r03 filled at the held tilt (p95 +1.9 / -0.2, the rim's
    # gap 4.4 mm median). The back (k0) stays at d 266, |x| 38: further back (268-276) its region stood above w12_R's
    # chord line inside the crown fur's place (+7 at 268)
    # W2f (the lead's call 6: "the ears' medial base rounded into the head (no thin fin), the pinna's cup deep enough not
    # to read as a flat blade in three-quarter"): the cup's back bulged 3 mm behind the opening (bk; W2d / W2e 0: the C
    # only as deep as its base; at 5 the solved w07_R stood +3.6 mm outside its furred outline at p95, at 3 every traced
    # ear inside within 2 mm, the worst w08_R +1.6: scratch_w2f/out/ears_bk3.json), the shell into the head with k 20 mm (W2e 12: the medial foot's thin edge stood as a fin
    # along the crown), the auricular mound under the medial foot (a forward to d 212, |x| 44; r 13 / 10 mm, k 16) so the
    # foot rises out of a muscular swelling instead of lying on the crown as a flap
    # W2g (the lead's call 7: "a real CUP: the pinna a thin curled sheet (about 2-3 mm) whose outer silhouette stays inside
    # every furred outline while its inner face is concave (not a 3 mm-deep blade); the medial base kept"): thin, the
    # sheet thinned FROM THE INSIDE (its back, the silhouette, kept) to 2.8 mm over most of its height, thickening as
    # (1 - v)^4 to the base's own (ear_shell: half-thickness 1.4 at the rims, W2f 2.0-6.0, median 3.9); at 2.2 mm (run
    # w2g2) the 1 mm meshes of the head views tore the tips' rims
    ear=dict(m0=(214.0, 55.0), k0=(266.0, 38.0), l0=(230.8, 56.0),
             bm=-6.0, bl=24.0, bk=3.0, gm=1.0, gl=1.5, gk=1.0, kv=1.0, km=0.55, kl=0.576, bulge_dir='across',
             bf=26.0, kf=0.65, gf=1.0, thin=dict(rim=0.0014, exp=4.0),
             arc=65.0, sink_base=3.0, roll=0.004, roll_w=0.12, sink=0.014, facet=0.001, k=0.020,
             tip_fade=(0.80, 0.15),            # W2h: the rims' roll eased out over the top fifth (ear_shell; no fork)
             # the auricular muscles' MOUND under the base. W2l (the lead: "broader and lower, so they read as the ear's
             # base; keep the W2f fix for the medial-foot fin"): an ellipsoid in the head surface's own frame at the
             # footprint centre c (d, |x| mm; on the old capsule's line, d 212-250 at |x| 44), its radii along the
             # surface (back), across it and along its normal (mm), its top `sink` mm UNDER the skin (ear_mound_frame):
             # the ear group's union with the head (HEAD ear k 20 mm) lifts the skin over it by (k - sink)^2 / 4k,
             # ~1.5 mm, eased out over its 52 x 32 mm footprint. (W2c-W2k: a round cone r 13 / 10 mm from (212, 52) to
             # (250, 40) at |x| 44, 2 mm proud of the skin before the k 20 union: two round bumps ~5-6 mm proud behind
             # the brow, the W2k fresh eyes)
             mound=dict(c=(230.0, 44.0), radii=(26.0, 16.0, 9.0), sink=9.0, k=0.016),
             # W2u (the lead's call: "the pinna rebuilt face-on against the photos that show the concha, the solver's
             # facing held to the concha's side so no fit can cheat edge-on"): THE FACE CONSTRUCTION (ear_shell_face; its
             # presence switches ear_shell to it, the fields above stay for ear_frame / the mound / the old sheet). mm in
             # the face plane (u across, + lateral; y up the axis from ear_frame's root). Measured: seen along its
             # opening W2t's sheet was 18.5 mm across at the base and 34 at mid-height with a trough as deep as wide, so
             # every symmetric front solved it edge-on (twin +-32 deg swivels at the 0.2 floor). This outline is W2e's
             # WET r03 leather (scratch_w2e/out/r03_pinna.json, less its 3.5 mm rim: 49 / 41 / 25 mm at 0.4 / 0.5 /
             # 0.7 H; here 43.5 / 39.6 / 29.7), asymmetric as r03's (the medial margin near-straight 15-21 mm in of
             # the axis, the lateral flaring low: bl 10.8 peaking 0.32 of the way up); the tip EAR_TIP_R's 10 mm arc
             # (the joint fit's 9.7; r03's ~6, w12's furred 17-23; w02's ear gate reads EAR_TIP_R, rounded 10-20); the
             # cup 25.8 mm deep at the base (the concha) easing to 3.4 at the tip as
             # (1 - y / H)^2 (the scapha a shallow curve: 9 mm at mid-height); the rims rolled 3 mm toward the opening
             # over their outer 12 %; the marginal pouch a 3 mm lobe low on the lateral margin (0.06-0.26 of the way
             # up) with its notch. Fitted at every traced ear's own carriage with the facing held per photo (w02_ears
             # FACE_FLOORS) on the face normal (ear_face_frame), work/bestiary/wolf/check_w2u_ears (the predecessor's
             # joint fit j1, re-scored with the right normal: s3 / s4 / s5; final fit u3 at w02's precision): the gate 10
             # of 11 (w12_R's narrow outline, 77 mm over a 49 mm chord, fits no carriage of a pinna as wide as r03's:
             # landscape.py, 0 of 468), the facing held 11 of 11 (the concha share 0.93-0.99 on every concha-facing ear),
             # r03's wet ears filled at their rim (gaps 3.2 / 3.3 against 3.5) with the concha toward the camera
             # W2u left 'reach' unset: without it w02's side-view base read 56-57 mm (d 233 -> 273) against 62-80, the
             # face plane setting the medial foot on the crown under its line; b 12-20 passed it but broke the three right
             # fronts, which then solved tipped back 58-67 deg
             # W2w (the lead's calls: "THE INNER (FRONT) EDGE reaches forward until the side view's base reads 62-80 (its
             # front at d ~207-213 where w01 / w03 put it) with every front's facing held"; "the antitragus fold low in the
             # concha (w12 L / R), the concha floor's ripple at the base and the marginal pouch's knob in profile
             # cleaned"), on the bind at ease (EAR_OUT's note), work/bestiary/wolf/check_w2w_ears/NOTES.md:
             #   - REACH ON: the medial crus bowed forward along the crown, b 26 mm peaking 0.34 of the way up (k 0.65), its
             #     foot 8 mm forward easing out by 0.35: w02 _w2we1's side-view base 72 mm (d 211 -> 276; W2u 57, d 233 ->
             #     279), the base's front 1.61 NE. The W2w solve auditor cleared it: its right-front failures came from
             #     w02_ears reading the clay along a trace chord's infinite line (the span now) and the high fronts'
             #     depth-reversal twins (w02_ears STAND_MAX now); with both, 9 of 11 traced ears inside with the facing
             #     held, every front standing (the w08 pair open: w08_L median 0.5 mm short, w08_R leaning out p95 +1.6)
             #   - THE THICKNESS ALONG THE SHEET ('thick', ear_shell_face): the arc distance from the skin up each column,
             #     thinner toward the margins (35 % of the base's excess at the margin, over the outer 30 %): the
             #     pouch's 12 mm-thick knob in profile gone, the concha floor at the base smooth (its ripple was the thick
             #     shell's; check_w2w_ears/sdfview.py, the program's union marched at 0.5 mm); w02's field-gradient max
             #     2.77 (W2u 2.63, the reach alone 3.29; the gate's p1 / p99 0.695 / 1.000)
             #   - THE ANTITRAGUS ('antitragus'): a rounded ridge 3 mm toward the opening with its crease under it, on an
             #     arc from the lateral margin 14 mm above the root rising medially to the concha's middle at 25 mm (bowed
             #     3.5 mm up), faded over its medial 45 %: the fold low in the concha that w12 L / R and w08_R show
             #     (and the thin-coated coyote research/wolf_web/mange_r07); placed by eye on those photos, [E]
             #   - THE POUCH a thin fold: its lobe 2 mm out (3) folded 1.5 mm back (3), the notch 1.5 deep (2)
             face=dict(m_foot=(-21.4, 0.0), l_foot=(25.8, -9.1), tip_u=0.0, bm=0.4, km=1.0, bl=10.8, kl=0.60,
                       bulge_w=0.6, depth=(25.8, 3.4, 2.0), back_at=0.15, roll=(3.0, 0.12, 1.5), tip_fade=(0.8, 0.15),
                       pouch=dict(t0=0.06, t1=0.26, w=0.25, out=(2.0, 1.5, 1.5)), anchor=25.0, blend=8.0, t_low=-1.2,
                       reach=dict(b=26.0, k=0.65, g=1.0, w=0.5, foot=8.0, t_foot=0.35),
                       thick=dict(margin=0.35, margin_w=0.3),
                       antitragus=dict(a=(29.0, 14.0), b=(5.0, 25.0), bow=3.5, h=3.0, w=3.2, crease=0.4, fade=0.45))),
)


def ear_mound_frame(md, surface_q):
    """W2l: the ear MOUND's frame on the head's skin (HEAD ear mound): at its footprint centre (d, |x|) the skin's point
    (surface_q: the top skin at (d, |x|) mm), its normal from the skin's slopes (central differences over 3 mm), the
    tangent back along d made normal to it, the tangent across (outward); the centre `sink` plus the normal radius under
    the skin. Returns (centre, t_back, t_across, normal), the palate frame (d, q, |x|) mm"""
    d0, x0 = (float(v) for v in md['c'])
    e = 3.0
    q0 = surface_q(d0, x0)
    gd = (surface_q(d0 + e, x0) - surface_q(d0 - e, x0)) / (2.0 * e)
    gx = (surface_q(d0, x0 + e) - surface_q(d0, x0 - e)) / (2.0 * e)
    n = np.array([-gd, 1.0, -gx])
    n /= np.linalg.norm(n)
    t = np.array([1.0, gd, 0.0])
    t -= (t @ n) * n
    t /= np.linalg.norm(t)
    a = np.cross(n, t)
    a *= 1.0 if a[2] >= 0.0 else -1.0
    c = np.array([d0, q0, x0]) - (md['sink'] + md['radii'][2]) * n
    return c, t, a, n


def _pqx(frame):
    """the palate frame to world: (p, q, x) -> point"""
    ao = np.asarray(frame['origin'], np.float64)
    pa, qa = np.asarray(frame['p'], np.float64), np.asarray(frame['q'], np.float64)
    X = np.array([1.0, 0.0, 0.0])
    return lambda v: ao + v[..., 0:1] * pa + v[..., 1:2] * qa + v[..., 2:3] * X, \
        lambda d: d[..., 0:1] * pa + d[..., 1:2] * qa + d[..., 2:3] * X


def _curve(C, n, sigma=0.0):
    """n points evenly by arclength on a PCHIP curve through C (k, 3), Gaussian-smoothed over sigma (m of arclength,
    the ends extended along their tangents first, so they keep their place and direction): returns the points, each
    control point's arclength, the points' arclengths and the length.

    THE SMOOTHING (W2 r04): PCHIP is only C1, its curvature JUMPS at every control point, and sd_sweep's foot point
    turns that jump into a crease: its root of g(s) = (p - C(s)) . T(s) moves at a rate set by the tangent's change
    across the segment, so where the curvature jumps between two segments the foot's speed jumps, by ~25 % for a point
    40 mm off the muzzle's axis (p18_sweep_np.py), and every row of the upper head printed a ring round the muzzle
    (r04's traced close-up, p16_normals.py: a 14 deg normal turn within 0.1 mm at a row). limbed._pchip_curve's same
    smoothing fixed the trunk's withers fold"""
    C = np.asarray(C, np.float64)
    t = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    tt = np.linspace(0.0, t[-1], 4096)
    D = np.column_stack([PchipInterpolator(t, C[:, k])(tt) for k in range(3)])
    if sigma > 0:
        from scipy.ndimage import gaussian_filter1d
        ds = tt[1] - tt[0]
        m = int(np.ceil(3.0 * sigma / ds))
        t0 = (D[1] - D[0]) / np.linalg.norm(D[1] - D[0])
        t1 = (D[-1] - D[-2]) / np.linalg.norm(D[-1] - D[-2])
        j = np.arange(1, m + 1)[:, None] * ds
        E = np.vstack([D[0] - j[::-1] * t0, D, D[-1] + j * t1])
        D = gaussian_filter1d(E, sigma / ds, axis=0, mode='nearest')[m:m + len(tt)]
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    sn = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(sn, s, D[:, k]) for k in range(3)]), np.interp(t, tt, s), sn, s[-1]


def _rot_about(v, c, deg):
    """rotate (p, q, x) points about the lateral axis through c by deg toward +q (negative opens the jaw)"""
    v = np.array(v, np.float64)
    r = _rot_pq((v[..., :2] - c[:2]).T, deg).T + c[:2]
    v[..., :2] = r
    return v


def _stations(rows, d_nodes, sigma):
    """the key stations' half-section points ((d, nine (|x|, q)), ...) mm at the node distances d_nodes (mm, even):
    each point's |x| and q PCHIP-interpolated over the stations' d, then Gaussian-smoothed over sigma mm (PCHIP is C1:
    its curvature jumps at a station would print a ring round the head, _curve), the ends held. (n, 9, 2) mm"""
    from scipy.ndimage import gaussian_filter1d
    d = np.array([r[0] for r in rows], np.float64)
    P = np.array([r[1] for r in rows], np.float64)
    out = np.empty((len(d_nodes), P.shape[1], 2))
    step = float(d_nodes[1] - d_nodes[0])
    for i in range(P.shape[1]):
        for c in range(2):
            v = PchipInterpolator(d, P[:, i, c])(d_nodes)
            out[:, i, c] = gaussian_filter1d(v, sigma / step, mode='nearest') if sigma > 0 else v
    return out


def ear_frame(spec, side=1):
    """the left (side 1) or right (-1) ear's root, axis (to the tip), base direction (from the base's posterior end to
    its medial-front end, HEAD ear base, made normal to the axis) and opening normal (forward and out), in the palate
    frame; the skeleton's ear joints use the same root and axis (landmarks_pqx)"""
    root = np.array([station_p(spec, spec['ear']['station']), EAR_Q, EAR_X])
    ax = np.array([-np.tan(np.radians(EAR_BACK)), 1.0, np.tan(np.radians(EAR_OUT))])
    ax /= np.linalg.norm(ax)
    b = np.asarray([HEAD['ear']['m0'], HEAD['ear']['k0']], np.float64)        # the medial-front and posterior bases
    e_w = np.array([b[-1, 0] - b[0, 0], 0.0, b[0, 1] - b[-1, 1]]) * 1.0e-3      # p = nose_p - d: forward is -d
    e_w = e_w - (e_w @ ax) * ax
    e_w /= np.linalg.norm(e_w)
    f = np.array([1.0, 0.15, 0.45])                    # the opening: forward and out (the alert fronts w12, w07)
    e_n = f - (f @ ax) * ax
    e_n /= np.linalg.norm(e_n)
    if EAR_SWIVEL:                                     # W2d head: the fit's bind swivel, + outward (toward +x)
        th = np.radians(-EAR_SWIVEL)
        K = np.array([[0.0, -ax[2], ax[1]], [ax[2], 0.0, -ax[0]], [-ax[1], ax[0], 0.0]])
        e_n = (np.eye(3) + np.sin(th) * K + (1.0 - np.cos(th)) * K @ K) @ e_n
    if side < 0:
        m = np.array([1.0, 1.0, -1.0])
        return root * m, ax * m, e_w * m, e_n * m
    return root, ax, e_w, e_n


def ear_pivot(spec, side=1):
    """W2e head: the rig's ear JOINT (ear_0) in the palate frame (p, q, x) m for the left (side 1) or right (-1) ear:
    EAR_PIVOT when set (the auricle turns about the concha's base on its cartilaginous canal, low and lateral in the
    base, not about the base's middle), else ear_frame's root (the base's middle)"""
    if EAR_PIVOT is None:
        return ear_frame(spec, side)[0]
    d, q, x = EAR_PIVOT
    return np.array([nose_p(spec) - d * 1.0e-3, q * 1.0e-3, side * x * 1.0e-3])


def ear_shell(spec, side, surface_q):
    """THE PINNA (W2c, its sheet rebuilt by the W2c check, its borders re-fitted at W2d), palate frame metres: a
    cone-like sheet whose cross-section is a C opening forward and out, between three BORDERS that run from a base on
    the skin to the tip's arc: the medial border from m0 (on the crown), the C's back from k0 (behind the crown), the
    lateral border from l0 (on the side of the head; HEAD ear: (d, |x|) mm, their q from surface_q(d, x) -> the head's
    top skin q in mm at that x, sunk sink_base); the tip's arc is EAR_TIP_R round the rig's ear tip (ear_frame's root
    + SPEC ear.height along the axis), spanning the opening from the medial border's end over the tip to the lateral's.
    W2d head: each border is the straight line from its base to its end on the arc plus ONE bulge normal to the axis,
    b sin(pi v^kv)^g at the height fraction v (HEAD ear bm, bl, bk mm: the medial border out medially, the lateral out
    laterally, the back backward from the opening, ear_frame's e_n: the cup's depth); W2c's per-border PCHIP controls
    flared the lateral border forward and out into a scoop (the lead: "flare like flaps from the top"). The bulges, the
    height and the bind's carriage come from the ear fit on the photos' furred outlines (work/bestiary/tests/
    w02_ears.py). Each height's section is the quadratic through its three border points; the two edges roll toward the
    section's chord middle (the pinna's rolled rim); every border continues `sink` below the base into the head; the
    half-thickness runs from SPEC ear.rim_half at the tip to ear.base_half at the base. Returns V (n, 3), F, the
    half-thickness, and the base's points (the bottom section, medial-front end first; palate frame m)"""
    if 'face' in HEAD['ear']:
        return ear_shell_face(spec, side, surface_q)
    E, eh = spec['ear'], HEAD['ear']
    root, ax, _, e_n = ear_frame(spec, 1)
    npn = nose_p(spec)
    tip = root + E['height'] * ax
    mm = 1.0e-3

    def on_skin(dx):
        q = surface_q(dx[0], dx[1]) - eh['sink_base']
        return np.array([npn - dx[0] * mm, q * mm, dx[1] * mm])
    M0, K0, L0 = (on_skin(eh[k]) for k in ('m0', 'k0', 'l0'))
    e_c = L0 - M0                                       # across the opening, normal to the axis
    e_c = e_c - (e_c @ ax) * ax
    e_c /= np.linalg.norm(e_c)
    Tc = tip - EAR_TIP_R * ax
    th = np.radians(eh['arc'])
    M1 = Tc + EAR_TIP_R * (np.sin(th) * -e_c + np.cos(th) * ax)
    L1 = Tc + EAR_TIP_R * (np.sin(th) * e_c + np.cos(th) * ax)
    height = float(np.linalg.norm(tip - K0))
    nv = int(np.ceil(height / eh['facet'])) + 1
    ns = int(np.ceil((np.linalg.norm(K0 - M0) + np.linalg.norm(L0 - K0)) / eh['facet'])) + 1
    v = np.linspace(0.0, 1.0, nv)

    def nrm(u):
        u = u - (u @ ax) * ax
        return u / np.linalg.norm(u)
    # W2e head: the medial and lateral bulges along the OPENING's across direction (ax x e_n: normal to the axis and to
    # the opening normal, the width a camera facing the concha sees) when HEAD ear bulge_dir is 'across' (W2d: along
    # the base chord e_c, which runs back and out from m0 to l0, so a front camera saw the bulges foreshortened); each
    # border's peak at the height fraction 0.5^(1 / k) (HEAD ear km, kl; W2d 1: mid-height, the leaf)
    if eh.get('bulge_dir', 'chord') == 'across':
        e_a = nrm(np.cross(ax, e_n))
        if e_a @ e_c < 0:
            e_a = -e_a
        d_m, d_l = -e_a, e_a
    else:
        d_m, d_l = nrm(-e_c), nrm(e_c)
    bulge = dict(m=(eh['bm'], eh['gm'], d_m, eh.get('km', 1.0)), k=(eh['bk'], eh['gk'], nrm(-e_n), eh['kv']),
                 l=(eh['bl'], eh['gl'], d_l, eh.get('kl', 1.0)))

    def border(B0, B1, key):
        b, g, n, kv = bulge[key]
        prof = np.sin(np.pi * v ** kv) ** g
        return (1 - v)[:, None] * B0[None] + v[:, None] * B1[None] + (b * mm * prof)[:, None] * n[None]
    Bs = [border(M0, M1, 'm'), border(K0, tip, 'k'), border(L0, L1, 'l')]
    if eh.get('bf', 0.0):
        # W2e head: the medial border reaches FORWARD along the crown at the head line's height (HEAD ear bf mm along
        # the head's forward direction normal to the axis, its peak at 0.5^(1 / kf)): the medial margin's foot sweeping
        # forward onto the crown, so the side view's base starts at the photos' front (d ~210) while the medial base
        # sits out at the side of the crown (the fronts w12 / w08: their medial edges leave the fur 50-56 mm out)
        Bs[0] = Bs[0] + (eh['bf'] * mm * np.sin(np.pi * v ** eh.get('kf', 1.0)) ** eh.get('gf', 1.0))[:, None] * \
            nrm(np.array([1.0, 0.0, 0.0]))[None]
    # the sink: each border continued below its base along its own direction there
    n_sink = max(2, int(np.ceil(eh['sink'] / eh['facet'])))
    w_s = np.linspace(1.0, 0.0, n_sink + 1)[:-1]
    for i, B in enumerate(Bs):
        dB = (B[1] - B[0]) / np.linalg.norm(B[1] - B[0])
        Bs[i] = np.vstack([B[0][None] - (w_s * eh['sink'])[:, None] * dB[None], B])
    Mv, Kv, Lv = Bs
    vv = np.concatenate([-w_s * eh['sink'] / height, v])
    t = np.linspace(0.0, 1.0, ns)[None, :, None]
    ctrl = 2.0 * Kv - 0.5 * (Mv + Lv)                   # the quadratic through K at t 0.5
    P = (1 - t) ** 2 * Mv[:, None] + 2 * (1 - t) * t * ctrl[:, None] + t ** 2 * Lv[:, None]
    # the rolled rims: each edge curls toward its section's chord middle
    Ss = t[0, :, 0]
    edge = np.maximum(0.0, 1.0 - Ss / eh['roll_w']) ** 2 + np.maximum(0.0, 1.0 - (1.0 - Ss) / eh['roll_w']) ** 2
    lift = np.clip(vv / 0.15, 0.0, 1.0)
    lift = lift * lift * (3 - 2 * lift)
    if eh.get('tip_fade'):
        # W2h (the lead's call 2: "the ear tips without the fork"): the rims' roll eased out toward the tip (from the
        # height fraction tip_fade[0] over tip_fade[1]): on the short sections under the tip's arc the two rolled rims
        # curled toward the chord's middle stood apart as two prongs
        v0_, dv_ = eh['tip_fade']
        tf_ = np.clip((vv - v0_) / dv_, 0.0, 1.0)
        lift = lift * (1.0 - tf_ * tf_ * (3 - 2 * tf_))
    inward = 0.5 * (Mv + Lv)[:, None] - P
    inward /= np.maximum(np.linalg.norm(inward, axis=2, keepdims=True), 1.0e-12)
    P = P + (eh['roll'] * edge[None, :] * lift[:, None])[..., None] * inward
    vc = np.clip(vv, 0.0, 1.0)[:, None] * np.ones((1, ns))
    ht = E['rim_half'] + (E['base_half'] - E['rim_half']) * (1.0 - vc) ** 1.3
    if eh.get('thin'):
        # W2g (the lead's call 7: "a real CUP: the pinna a thin curled sheet (about 2-3 mm) whose outer silhouette stays
        # inside every furred outline while its inner face is concave (not a 3 mm-deep blade); the medial base kept"): the
        # sheet THINNED FROM THE INSIDE. Its back face stays where W2f's was (the mid-surface moved toward the back, away
        # from the opening e_n, by the old half-thickness less the new), so the outer silhouette is kept, and the inner
        # face recedes by twice that: the cup deepens by ~4 mm at mid-height. The new half-thickness: thin['rim'] (m) over
        # most of the height, thickening to SPEC ear.base_half only near the base (exponent thin['exp'] on 1 - v), so the
        # medial base and the root keep W2f's mass
        th_ = eh['thin']
        ht_new = th_['rim'] + (E['base_half'] - th_['rim']) * (1.0 - vc) ** th_['exp']
        dPv = np.gradient(P, axis=0)
        dPs = np.gradient(P, axis=1)
        nrm_ = np.cross(dPv, dPs)
        nrm_ /= np.maximum(np.linalg.norm(nrm_, axis=2, keepdims=True), 1.0e-12)
        # toward the back, ONE sign for the whole sheet (its grid orientation is consistent; a per-vertex sign flipped
        # across the rolled rims, where the normal turns past the opening's plane, and printed teeth along them)
        nrm_ *= -1.0 if float(np.mean(nrm_ @ e_n)) > 0.0 else 1.0
        P = P + ((ht - ht_new)[..., None]) * nrm_
        ht = ht_new
    nr = len(vv)
    idx = np.arange(nr * ns).reshape(nr, ns)
    a, b_, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    F = np.concatenate([np.column_stack([a, b_, c]), np.column_stack([a, c, d])]).astype(np.int32)
    V = P.reshape(-1, 3)
    B5 = P[n_sink].copy()                               # the base: the section at v 0, from m0 round k0 to l0
    if side < 0:
        m = np.array([1.0, 1.0, -1.0])
        V, B5 = V * m, B5 * m
        F = F[:, ::-1].copy()
    return V, F, ht.ravel(), B5


def _smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ear_outline(fc, H):
    """W2u: THE PINNA'S FACE-ON OUTLINE in the ear's face plane, (u across, + toward the lateral margin; y up the axis from
    the root) mm (HEAD ear face): the medial margin the straight line from its foot m_foot to its tangent point on the
    tip's circle (radius tip_r, its top the tip (tip_u, H)), the lateral margin likewise from l_foot, the circle's arc over
    the top between the two tangent points. Returns dict(m_foot, l_foot, m_tan, l_tan, centre (2,) mm, r mm, th_m, th_l:
    the tangent points' angles on the circle (radians from +u, so the tip is pi / 2))"""
    r = float(fc.get('tip_r', 1000.0 * EAR_TIP_R))      # (W2u: EAR_TIP_R unless the face sets its own; w02's ear gate
    c = np.array([float(fc.get('tip_u', 0.0)), H - r])  # reads EAR_TIP_R, so the default keeps the gate on the real tip)
    out = dict(centre=c, r=r)
    for key, sgn in (('m', -1.0), ('l', 1.0)):
        F = np.asarray(fc[key + '_foot'], np.float64)
        d = F - c
        L = float(np.linalg.norm(d))
        a = np.arccos(min(1.0, r / L))
        b = np.arctan2(d[1], d[0])
        th = max((b + a, b - a), key=lambda t: sgn * np.cos(t))      # the outer tangent: on the margin's own side
        out[key + '_foot'] = F
        out[key + '_tan'] = c + r * np.array([np.cos(th), np.sin(th)])
        out['th_' + key] = float(np.mod(th, 2.0 * np.pi))
    return out


def ear_face_frame(spec, side=1):
    """W2u: the face construction's frame (ear_shell_face), palate frame: the root, the axis to the tip, the across
    direction e_l (+ toward the lateral margin) and the FACE NORMAL e_z toward the opening (ear_frame's opening e_n made
    normal to e_l: the cup opens along it). The facing test reads e_z as the opening (w02_ears.clay_ear): the old sheet's
    reading (opening_normal: grid row 55 %, middle column -> the edges' middle) is not level on this grid, since each
    column enters the head at its own depth, and on the W2u fits it tipped the opening 30 deg down (elev -48.6 against
    e_z's -19.5; check_w2u_ears/en_check.py), so every facing-held solve tilted the ear 50-70 deg back to bring it up"""
    root, ax, _, e_n = ear_frame(spec, 1)
    e_l = np.cross(ax, e_n)
    e_l /= np.linalg.norm(e_l)
    if e_l[2] < 0:
        e_l = -e_l
    e_z = np.cross(e_l, ax)
    e_z /= np.linalg.norm(e_z)
    if e_z @ e_n < 0:
        e_z = -e_z
    if side < 0:
        m = np.array([1.0, 1.0, -1.0])
        return root * m, ax * m, e_l * m, e_z * m
    return root, ax, e_l, e_z


def ear_shell_face(spec, side, surface_q):
    """W2u (the lead's call: "the pinna rebuilt face-on against the photos that show the concha, the solver's facing held to
    the concha's side so no fit can cheat edge-on"): THE PINNA AS A FACE-ON OUTLINE WITH A SHALLOW CUP, palate frame metres,
    the same contract as ear_shell (a regular grid: rows up the ear, columns medial -> back -> lateral; V, F, the
    half-thickness, the base section on the skin medial-front end first).

    W2c-W2t's sheet ran its base front to back along the head (the side views' 76 mm base read as the bind's own), so seen
    along its opening it was 18.5 mm across at the base and 34 at mid-height (r03's wet leather 45) and its cup a trough as
    deep as wide (the back 36 mm behind the rims' chord at mid-height): turned 30 deg about its axis it showed chord cos +
    depth sin, wider than face-on, so the carriage solve turned it edge-on (twin +-32 deg swivels, w12 / r03 / w07;
    work/bestiary/wolf/check_w2u_ears/NOTES.md). Here the sheet is laid out in the ear's FACE PLANE (ear_frame: the root,
    the axis to the tip, the opening normal n; across e = axis x n, + toward the lateral margin, lateral and down): u
    across, y up the axis (mm), z toward the opening.
      - THE OUTLINE (ear_outline, HEAD ear face): straight margins from their feet to the tip's circle, the circle's arc
        over the tip; each margin bulged outward (bm / bl mm, peaking km / kl of the way up, spread over the outer
        `bulge_w` of the section); the columns run from the base line (the feet) to the arc, the margins' columns along
        the margins, so the face-on outline is the outline itself.
      - THE CUP: z = -D(y) (1 - ((s - back_at) / (1 -+ back_at))^2) at the column fraction s (-1 medial .. +1 lateral), the
        depth D falling from depth[0] at the base to depth[1] at the tip as (1 - y / H)^depth[2]: the concha deep at the
        base, the scapha a shallow curve.
      - THE ROLLED RIM: the outer roll[1] of the section curls roll[0] mm toward the opening and roll[2] mm inward, eased
        in over the base's first 15 % and out toward the tip (tip_fade).
      - THE MARGINAL POUCH (pouch): on the lateral margin from t0 to t1 of the way up, a lobe out[0] mm outward folded
        out[1] mm back, a notch out[2] mm deep at its top, over the outer `w` of the section.
      - W2w: THE ANTITRAGUS (antitragus): a rounded ridge h mm toward the opening along an arc low in the concha from the
        lateral margin rising medially, a crease under it.
      - THE MEDIAL CRUS REACHING FORWARD (reach): the medial columns carried forward along the head (place()'s note).
      - THE BASE: each column extended below its foot along its own line until it enters the closed head (its 1 mm
        lattice, surface_q.phi when given; else under surface_q's top skin), then `sink` mm further; the row on the skin
        is the base section.
      - THE THICKNESS: thin['rim'] over the sheet, thickening to SPEC ear.base_half toward the base as (1 - y / H)^exp;
        W2w (thick): y the arc distance from the skin up each column, the base's excess thinned toward the margins."""
    E, eh = spec['ear'], HEAD['ear']
    fc = eh['face']
    root, ax, e_l, e_z = ear_face_frame(spec, 1)         # e_z: the face's normal, toward the opening
    npn = nose_p(spec)
    mm = 1.0e-3
    H = 1000.0 * float(E['height'])
    O = ear_outline(fc, H)
    facet = 1000.0 * float(eh['facet'])
    ns = int(np.ceil(max(np.linalg.norm(O['l_foot'] - O['m_foot']),
                         O['r'] * abs(O['th_m'] - O['th_l'])) / facet)) + 1
    ns += 1 - ns % 2                                     # odd: a middle column (w02_ears.opening_normal reads it)
    s = np.linspace(-1.0, 1.0, ns)
    f01 = 0.5 * (s + 1.0)
    Bot = (1.0 - f01)[:, None] * O['m_foot'][None] + f01[:, None] * O['l_foot'][None]
    th = (1.0 - f01) * O['th_m'] + f01 * O['th_l']
    Top = O['centre'][None] + O['r'] * np.column_stack([np.cos(th), np.sin(th)])
    Top[0], Top[-1] = O['m_tan'], O['l_tan']
    # each column's own line in the face plane, t 0 at its foot, 1 at the arc; extended below the foot for the skin search
    def face_pts(t):                                     # t (nr, ns) -> u, y (mm), before the bulges
        return (Bot[None, :, 0] + t * (Top - Bot)[None, :, 0], Bot[None, :, 1] + t * (Top - Bot)[None, :, 1])
    bw = float(fc.get('bulge_w', 0.6))
    w_m = np.clip(1.0 - (s + 1.0) / bw, 0.0, 1.0) ** 2
    w_l = np.clip(1.0 - (1.0 - s) / bw, 0.0, 1.0) ** 2
    pc = fc.get('pouch')
    rc = fc.get('reach')
    fwd = np.array([1.0, 0.0, 0.0]) - ax[0] * ax          # the head's forward (+p) normal to the ear's axis
    fwd /= np.linalg.norm(fwd)
    sb = float(fc.get('back_at', 0.0))
    cup = 1.0 - ((s - sb) / np.where(s >= sb, 1.0 - sb, 1.0 + sb)) ** 2
    rw = fc['roll']

    def place(t):
        """(nr, ns) column parameters -> (nr, ns, 3) palate-frame points (m) and the face-plane y (mm)"""
        u, y = face_pts(t)
        tc = np.clip(t, 0.0, 1.0)
        prof_m = np.sin(np.pi * tc ** fc.get('km', 1.0)) ** fc.get('gm', 1.0)
        prof_l = np.sin(np.pi * tc ** fc.get('kl', 1.0)) ** fc.get('gl', 1.0)
        u = u - fc.get('bm', 0.0) * prof_m * w_m[None] + fc.get('bl', 0.0) * prof_l * w_l[None]
        yn = np.clip(y / H, 0.0, 1.0)
        D = fc['depth'][1] + (fc['depth'][0] - fc['depth'][1]) * (1.0 - yn) ** fc['depth'][2]
        z = -D * cup[None]
        tr = np.clip((np.abs(s) - (1.0 - rw[1])) / rw[1], 0.0, 1.0) ** 2
        lift = _smooth01(y / (0.15 * H))
        if fc.get('tip_fade'):
            lift = lift * (1.0 - _smooth01((yn - fc['tip_fade'][0]) / fc['tip_fade'][1]))
        z = z + rw[0] * tr[None] * lift
        u = u - np.sign(s)[None] * rw[2] * tr[None] * lift
        if pc:
            tp = np.clip((tc - pc['t0']) / (pc['t1'] - pc['t0']), 0.0, 1.0)
            bump = np.sin(np.pi * tp) ** 2 * (tc > pc['t0']) * (tc < pc['t1'])
            wp = np.clip(1.0 - (1.0 - s) / pc['w'], 0.0, 1.0) ** 2
            notch = np.exp(-((tc - pc['t1']) / (0.25 * (pc['t1'] - pc['t0']))) ** 2)
            u = u + (pc['out'][0] * bump - pc['out'][2] * notch) * wp[None]
            z = z - pc['out'][1] * bump * wp[None]
        at = fc.get('antitragus')
        if at:
            # W2w: THE ANTITRAGUS FOLD, low in the concha (w12 L / R, w08_R; the mangy coyote research/wolf_web/
            # mange_r07): a rounded ridge standing h mm toward the opening along an arc from its lateral end a to its
            # medial end b (face-plane (u, y) mm; its middle bowed `bow` mm up the ear: a quadratic curve), its section a
            # Gaussian of half-width w with a crease `crease` h deep just under it (the fold's shadowed lower side),
            # faded over the medial `fade` of its length
            a_ = np.asarray(at['a'], float)
            b_ = np.asarray(at['b'], float)
            ab = b_ - a_
            nrm = np.array([-ab[1], ab[0]]) / np.linalg.norm(ab)
            nrm = nrm if nrm[1] >= 0.0 else -nrm                     # + toward the fold's upper side (up the ear)
            c_ = 0.5 * (a_ + b_) + 2.0 * float(at.get('bow', 0.0)) * nrm   # the control point: the middle bowed `bow`
            lt = np.linspace(0.0, 1.0, 41)
            C = ((1 - lt) ** 2)[:, None] * a_ + (2 * lt * (1 - lt))[:, None] * c_ + (lt ** 2)[:, None] * b_
            Tn = np.gradient(C, axis=0)
            Tn /= np.linalg.norm(Tn, axis=1, keepdims=True)
            Nn = np.column_stack([-Tn[:, 1], Tn[:, 0]])
            Nn *= np.where(Nn[:, 1:2] >= 0.0, 1.0, -1.0)
            du_ = u[..., None] - C[:, 0]
            dy_ = y[..., None] - C[:, 1]
            d2 = du_ * du_ + dy_ * dy_
            k_ = np.argmin(d2, axis=-1)
            dd = np.sqrt(np.take_along_axis(d2, k_[..., None], -1)[..., 0])
            sd = np.take_along_axis(du_, k_[..., None], -1)[..., 0] * Nn[k_, 0] + \
                np.take_along_axis(dy_, k_[..., None], -1)[..., 0] * Nn[k_, 1]
            lam = lt[k_]
            fd = max(float(at.get('fade', 0.4)), 1e-6)
            fade = (1.0 - _smooth01((lam - (1.0 - fd)) / fd)) * _smooth01(lam / 0.12 + 0.5)
            ridge = np.exp(-(dd / at['w']) ** 2) - at.get('crease', 0.35) * np.exp(-((sd + 1.1 * at['w']) /
                                                                                     (0.5 * at['w'])) ** 2)
            z = z + at['h'] * ridge * fade
        P = root[None, None] + mm * (u[..., None] * e_l + y[..., None] * ax + z[..., None] * e_z)
        if rc:
            # THE MEDIAL CRUS REACHING FORWARD (reach): the medial columns (the outer w of the section) carried
            # forward along the head (its +p made normal to the axis): a bow of b mm, sin(pi t^k)^g up the column (its
            # peak 0.5^(1 / k) of the way up: where the margin stands above the crown's line in a side view, W2e's bf),
            # plus `foot` mm at the foot eased out by t_foot (the foot itself sits under the crown's line there)
            wr = np.clip(1.0 - (s + 1.0) / rc['w'], 0.0, 1.0) ** 2
            pr = rc.get('b', 0.0) * np.sin(np.pi * tc ** rc.get('k', 0.65)) ** rc.get('g', 1.0)
            if rc.get('foot'):
                pr = pr + rc['foot'] * (1.0 - _smooth01(tc / rc.get('t_foot', 0.35)))
            P = P + (mm * wr[None] * pr)[..., None] * fwd[None, None]
        return P, y

    # the base: where each column enters the closed head. Above its foot (t >= 0) a column is the face plane's line; below
    # it, it turns toward the ANCHOR (the concha's canal, `anchor` mm down the axis from the root, inside the head) over
    # `blend` mm, so a column whose own line would pass beside the head (the lateral margin, the head narrowing under the
    # ear) still meets the skin; the turn is tangent to the column at the foot
    clen = np.linalg.norm(Top - Bot, axis=1)            # mm per unit t along each column
    A = root - mm * float(fc.get('anchor', 25.0)) * ax
    P0, _ = place(np.zeros((1, ns)))
    P1, _ = place(np.full((1, ns), 0.02))
    dcol = (P0 - P1)[0]
    dcol /= np.linalg.norm(dcol, axis=1, keepdims=True)
    dA = A[None] - P0[0]
    dA /= np.linalg.norm(dA, axis=1, keepdims=True)
    blend = float(fc.get('blend', 8.0))

    def place_all(t):
        """place() above the feet, the turned extension below them; (nr, ns) -> points (m), face y (mm)"""
        P, y = place(np.maximum(t, 0.0))
        ell = np.maximum(-t, 0.0) * clen[None]          # mm below the foot along the column
        w = _smooth01(ell / blend)[..., None]
        dirv = (1.0 - w) * dcol[None] + w * dA[None]
        dirv /= np.linalg.norm(dirv, axis=2, keepdims=True)
        P = np.where((t < 0.0)[..., None], P0[0][None] + mm * ell[..., None] * dirv, P)
        return P, np.where(t < 0.0, y - ell, y)
    phi = getattr(surface_q, 'phi', None)
    tt = np.linspace(1.0, float(fc.get('t_low', -1.2)), 441)[:, None] * np.ones((1, ns))
    Pt, _ = place_all(tt)
    dqx = np.stack([1000.0 * (npn - Pt[..., 0]), 1000.0 * Pt[..., 1], 1000.0 * Pt[..., 2]], -1)
    if phi is not None:
        f = phi(dqx.reshape(-1, 3)).reshape(dqx.shape[:2])
    else:
        f = np.array([[dqx[i, j, 1] - surface_q(dqx[i, j, 0], dqx[i, j, 2]) for j in range(ns)]
                      for i in range(len(tt))])
    t_skin = np.empty(ns)
    for j in range(ns):
        ins = np.nonzero(f[:, j] < 0.0)[0]
        if len(ins) == 0:
            t_skin[j] = tt[int(np.argmin(f[:, j])), j]      # never enters the head: its closest approach
            continue
        i = int(ins[0])
        if i == 0:
            t_skin[j] = tt[0, j]
            continue
        a_, b_ = f[i - 1, j], f[i, j]
        t_skin[j] = tt[i - 1, j] + (tt[i, j] - tt[i - 1, j]) * a_ / (a_ - b_)
    t_sink = t_skin - 1000.0 * float(eh['sink']) / clen
    n_sink = max(2, int(np.ceil(1000.0 * float(eh['sink']) / facet)))
    nv = int(np.ceil(float(np.max((1.0 - t_skin) * clen)) / facet)) + 1
    w_s = np.linspace(0.0, 1.0, n_sink + 1)[:-1]
    w_v = np.linspace(0.0, 1.0, nv)
    T = np.vstack([t_sink[None] + w_s[:, None] * (t_skin - t_sink)[None],
                   t_skin[None] + w_v[:, None] * (1.0 - t_skin)[None]])
    P, Y = place_all(T)
    th_ = eh['thin']
    tk = fc.get('thick')
    if tk:
        # W2w: THE THICKNESS ALONG THE SHEET (the solve auditor: "make ht continuous along the sheet (a function of distance
        # from the skin along each column)"): the face-plane height clipped at 0 thickened the lateral columns 9 mm lower
        # than the medial (their feet lie lower in the plane), so the pouch's lobe (ht 6.0-4.05) sat beside the margin
        # above its notch (3.89-3.38) and the sink's bottom row (6.0) under the medial margin's foot (4.3-4.6): the shell's
        # field stepped 0.7-2.1 mm where the closest point jumped between them (w02's field-gradient max 2.63; the knob the
        # pouch makes in profile). Now the profile runs on the arc distance from the skin up each column (0 at the skin,
        # the sink at base_half), and thins toward the margins (the helix and the pouch are folds of skin, the concha's
        # floor the thick part): by `margin` of the base's excess at the margin, over the outer `margin_w` of the section
        dist = (T - t_skin[None]) * clen[None]
        yn = np.clip(dist / H, 0.0, 1.0)
        ht = th_['rim'] + (E['base_half'] - th_['rim']) * (1.0 - yn) ** th_['exp']
        mw = float(tk.get('margin_w', 0.25))
        ms = 1.0 - (1.0 - float(tk.get('margin', 1.0))) * np.clip((np.abs(s) - (1.0 - mw)) / mw, 0.0, 1.0) ** 2
        ht = th_['rim'] + (ht - th_['rim']) * ms[None]
    else:
        yn = np.clip(Y / H, 0.0, 1.0)
        ht = th_['rim'] + (E['base_half'] - th_['rim']) * (1.0 - yn) ** th_['exp']
    nr = T.shape[0]
    idx = np.arange(nr * ns).reshape(nr, ns)
    a, b_, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    F = np.concatenate([np.column_stack([a, b_, c]), np.column_stack([a, c, d])]).astype(np.int32)
    V = P.reshape(-1, 3)
    B5 = P[n_sink].copy()                               # the base: the row on the skin, the medial foot first
    if side < 0:
        m = np.array([1.0, 1.0, -1.0])
        V, B5 = V * m, B5 * m
        F = F[:, ::-1].copy()
    return V, F, ht.ravel(), B5


def analytic_groups(phi, G, spec=None):
    """the head's analytic members over its grid, in program order: W2i (HEAD nares with 'opening'): the traced alar
    folds (a UNION group) then the traced openings' PSWEEPs, the slits and the philtrum (a SUBTRACT group),
    canid_hull.nostrils_traced; W2g-W2h (with 'canal'): canid_hull.nose_members; before W2g the nares alone
    (canid_hull.nares_members). [(kind 'union' | 'sub', (members, k_union, k_group))]"""
    from . import canid_hull as CH
    hn = HEAD['nares']
    if HEAD.get('method') == 'cage':
        # W2j: the nostrils, the lids and the fissures are the cage's own surface; only the GLOBES stay analytic (exact
        # spheres over the lids' pocket, at any scale)
        globes = [('sphere', CH.lid_frame(spec, s)['centre'], CH.lid_frame(spec, s)['R'], 'union') for s in ('L', 'R')]
        return [('union', (globes, 0.0, CH.STROKES_SKULL['eye']['globe_k']), 'globes')]
    if 'opening' in hn:
        fold, sub = CH.nostrils_traced(phi, G, hn, spec)
        # W2i (the lead's call 3): the eyes' fissures cut through the lid shell only, then the globes (eye_members)
        eyes = CH.eye_members(spec, phi, G) if 'fis_rho' in CH.STROKES_SKULL['eye'] else []
        return ([('union', fold)] if fold[0] else []) + [('sub', sub)] + eyes
    if 'canal' in hn:
        ala, sub = CH.nose_members(phi, G, hn)
        return ([('union', ala)] if ala[0] else []) + [('sub', sub)]
    return [('sub', CH.nares_members(phi, G, hn))]


def build_head(prog, spec, frame, info):
    """W2c: the head GROUP is ONE GRID member, canid_hull.head_volume (the visual hull of the traced skin silhouettes
    and the skull's sections, rounded by the constrained curvature flow, sculpted; the bind's jaw opened about the jaw
    joint by SPEC rest.jaw_open, the posed review's closed), blended into the neck by HEAD k_group; each ear its own
    SHELL group with its muscle mound (ear_shell). No mouth-slit primitive: the mouth line is sculpted into the grid.
    Returns the head's info: the lip curves (the closed upper lip's margin; the lower lip's, opened with the jaw), the
    stop, the grid's numbers, the hull's silhouette errors and the sculpt's curves (palate frame mm)"""
    from ..families.limbed import _tag
    from .. import sdf as S_
    from . import canid_hull as CH
    assert hasattr(S_.Program, 'grid'), ('the W2c head is a GRID member: land work/bestiary/patches/sdf_grid.md, or load '
                                         'its staged module (work/bestiary/tests/w02_clay.py --sdf)')
    hd = HEAD
    to_w, dir_w = _pqx(frame)
    npn = nose_p(spec)
    mm = 1.0e-3
    jaw = spec['rest']['jaw_open']
    head_axis = to_w(np.array([[npn, NOSE_Q, 0.0], [POLL[0], POLL[1], 0.0]]))      # the coat's head chain
    out = dict(groups=[])
    if hd.get('method') == 'cage':
        from . import canid_cage as CC
        vol = CC.head_volume(spec, jaw)
    else:
        vol = CH.head_volume(spec, jaw)
    G = vol['grid']
    # the grid's frame: index i back along d (-p), j along q, k along x (the creature's left)
    origin = to_w(np.array([[npn - G.lo[0] * mm, G.lo[1] * mm, G.lo[2] * mm]]))[0]
    axes = np.column_stack([dir_w(np.array([[-1.0, 0.0, 0.0]]))[0], dir_w(np.array([[0.0, 1.0, 0.0]]))[0],
                            dir_w(np.array([[0.0, 0.0, 1.0]]))[0]])
    lo = len(prog.kind)
    prog.begin_group(S_.UNION, hd['k_group'])
    i_head = prog.grid(origin, axes, G.h * mm, vol['values'] * mm, name='head')
    _tag(prog, i_head, 'head', head_axis)
    prog.end_group()
    out['groups'].append(dict(name='head', region='head', lo=lo, hi=len(prog.kind)))
    info['groups'].append(dict(name='head', region='head', lo=lo, hi=len(prog.kind)))
    C = vol['closed']
    Gc = CH.Grid(C['lo'], C['lo'] + (np.array(C['phi'].shape) - 1) * float(C['h']), float(C['h']))
    # ---- W2d head: THE NARES, analytic members subtracted over the grid (HEAD nares; canid_hull.nares_members places
    # them on the closed head's leather): the openings ellipsoids, the alar slits round cones, unioned smoothly, the
    # group subtracted with its own k; region None (the owner of their walls is the head). W2g: analytic_groups, the
    # alar folds a UNION group (region head) before the SUBTRACT group of the canals, the slits, the philtrum and the
    # leather's border (canid_hull.nose_members)
    pw = lambda P: to_w(np.array([[npn - P[0] * mm, P[1] * mm, P[2] * mm]]))[0]
    for grp_ in analytic_groups(C['phi'], Gc, spec):
        kind_, (mem, k_u, k_g) = grp_[0], grp_[1]
        gname_ = grp_[2] if len(grp_) > 2 else None
        lo = len(prog.kind)
        prog.begin_group(S_.UNION if kind_ == 'union' else S_.SUBTRACT, k_g * mm)
        ops_ = dict(union=S_.UNION, intersect=S_.INTERSECT, subtract=S_.SUBTRACT)
        for m in mem:
            if m[0] == 'psweep':
                # W2i: a traced opening swept into the leather (canid_hull.nostrils_traced) or a fissure's prism
                # (eye_members): its centreline and start normal to world, its sections and rho in metres, its per-node
                # keys and scale; its op (a fissure's prism is intersected with the lid's band in its own group)
                Pw = np.array([pw(p_) for p_ in m[1]])
                nw_ = dir_w(np.array([[-m[6][0], m[6][1], m[6][2]]]))[0]
                prog.psweep(Pw, np.asarray(m[2], np.float64) * mm, rho=m[3] * mm, key=m[4], scale=m[5], normal=nw_,
                            op=ops_[m[9] if len(m) > 9 else 'union'], k=k_u * mm,
                            name='naris' if len(m) <= 9 else 'fissure')
            elif m[0] == 'sphere':
                # W2i: a sphere (the globes: canid_hull.eye_members) with its own op
                i_s = prog.ellipsoid(pw(m[1]), np.full(3, m[2] * mm), op=ops_[m[3]], k=k_u * mm,
                                     name='globe' if m[3] == 'union' else 'lid_band')
                if m[3] == 'union':
                    _tag(prog, i_s, 'head', head_axis)
            elif m[0] == 'ellip':
                # W2i: an oriented ellipsoid (the lid band's bounds: canid_hull.eye_members), its axes rows (palate)
                axw = np.column_stack([dir_w(np.array([[-a_[0], a_[1], a_[2]]]))[0] for a_ in m[2]])
                prog.ellipsoid(pw(m[1]), np.asarray(m[3], np.float64) * mm, axes=axw, op=ops_[m[4]], k=k_u * mm,
                               name='lid_band')
            elif m[0] == 'ellipsoid':
                axw = np.column_stack([dir_w(np.array([[-a_[0], a_[1], a_[2]]]))[0] for a_ in m[2]])
                prog.ellipsoid(pw(m[1]), np.asarray(m[3], np.float64) * mm, axes=axw, op=S_.UNION, k=k_u * mm,
                               name='naris')
            else:
                km_ = m[5] if len(m) > 5 else k_u          # W2g: a chain's own union k (canid_hull._chain)
                # W2i: a round cone may carry its op (the fissure group's capsule clip, the canthal grooves)
                i_ = prog.roundcone(pw(m[1]), pw(m[2]), m[3] * mm, m[4] * mm, op=ops_[m[6] if len(m) > 6 else 'union'],
                                    k=km_ * mm, name='ala' if kind_ == 'union' else 'naris_slit')
                if kind_ == 'union':
                    _tag(prog, i_, 'head', head_axis)
        prog.end_group()
        nm_ = gname_ or ('alae' if kind_ == 'union' else 'nares')
        rg_ = 'head' if kind_ == 'union' else None
        out['groups'].append(dict(name=nm_, region=rg_, lo=lo, hi=len(prog.kind)))
        info['groups'].append(dict(name=nm_, region=rg_, lo=lo, hi=len(prog.kind)))
        out[nm_] = mem
    if 'nares' in vol:
        out['nares'] = vol['nares']           # W2j: the cage's nostrils as the measures read them (canid_cage.nares_members)
    # ---- the ears: their bases on the closed head's skin
    qline = np.arange(95.0, -60.0, -0.25)
    dors = np.asarray(CH.PROFILE, np.float64)[CH.PROFILE_BACK[1]:][::-1]      # the profile's dorsal run, d rising

    def surface_q(d, x):
        """the head's top skin at (d, |x|) mm: the first crossing marching down; off the head, the profile's top"""
        f = CH.sample3(C['phi'], Gc, np.column_stack([np.full(len(qline), d), qline, np.full(len(qline), x)]))
        j = int(np.argmax(f < 0))
        if f[j] >= 0 or j == 0:
            return float(np.interp(d, dors[:, 0], dors[:, 1]))
        return float(qline[j - 1] + 0.25 * f[j - 1] / (f[j - 1] - f[j]))
    # W2u: the closed head's signed distance (mm) at (d, q, x) mm points, for ear_shell_face's base (w02_ears' same rule)
    surface_q.phi = lambda P: CH.sample3(C['phi'], Gc, np.asarray(P, np.float64))
    for sx, nm in ((1, 'ear_L'), (-1, 'ear_R')):
        V, F, ht, base = ear_shell(spec, sx, surface_q)
        lo = len(prog.kind)
        prog.begin_group(S_.UNION, hd['ear']['k'])
        Vw = to_w(V)
        # W2x: the CONTINUOUS shell (sdf.py sd_shell_c, opt-in): the ear's half-thickness varies across the curled
        # sheet (W2w 'thick': the buried medial margin 3.0 mm beside the concha floor 5.5-5.9), so the default rule's
        # field stepped up to 3.1 mm where the closest point jumps, inside this group's k 20 union: a crack on the skin
        # in front of and under each ear's base (W2w fresh eyes)
        i = prog.shell(Vw, F, ht, k=0.0, maxd=0.05, name=nm, continuous=True)
        _tag(prog, i, 'ear')
        md = hd['ear']['mound']
        mc, mt, mx, mn = ear_mound_frame(md, surface_q)
        to_dir = lambda v: np.array([-v[0], v[1], sx * v[2]])                  # noqa: E731 (a palate (d, q, x) direction)
        axes = np.column_stack([dir_w(to_dir(a)) for a in (mt, mx, mn)])
        cw = to_w(np.array([npn - mc[0] * mm, mc[1] * mm, sx * mc[2] * mm]))
        _tag(prog, prog.ellipsoid(cw, np.asarray(md['radii'], np.float64) * mm, axes=axes, k=md['k'], name=nm + '_mound'),
             'head', head_axis)
        prog.end_group()
        out['groups'].append(dict(name=nm, region='ear', lo=lo, hi=len(prog.kind)))
        info['groups'].append(dict(name=nm, region='ear', lo=lo, hi=len(prog.kind)))
        out[nm] = dict(V=Vw, F=F, ht=ht, base=to_w(base))
    # ---- the lips for the regions and the review: the sculpted mouth line (closed), the lower lip's copy opened with
    # the jaw about the jaw joint (the bind)
    L = landmarks_pqx(spec)
    tmj = np.array(L['tmj'], np.float64)
    lip = np.asarray(C['curve_mouth_line'], np.float64)
    lip_pqx = np.column_stack([npn - lip[:, 0] * mm, lip[:, 1] * mm, lip[:, 2] * mm])
    lip_lo = _rot_about(lip_pqx, tmj, -jaw)
    comm = lip_pqx[int(np.argmax(lip_pqx[:, 2]))]
    out.update(lip_up=to_w(lip_pqx), lip_lo=to_w(lip_lo), head_axis=head_axis, stop_p=npn - hd['stop'] * mm,
               nose_p=npn, i_head=i_head, commissure=to_w(comm[None])[0], volume=vol, curves={
                   k[6:]: C[k] for k in C if k.startswith('curve_')})
    info.setdefault('grids', {})
    info['grids']['head'] = dict(index=i_head, divisor=float(prog.par[i_head][17]), shape=tuple(vol['values'].shape),
                                 cell=G.h)
    return out
