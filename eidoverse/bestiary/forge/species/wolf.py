"""WOLF (Canis lupus): the Bestiary's second realistic base and its first LIMBED one (work/bestiary/research/
WOLF_PLAN.md). W1, the target specimen: an adult male grey wolf of 40 kg (plan §2), one coherent animal, never an
average of incompatible specimens.

Units are metres and degrees. +Y is up, +Z forward, +X the creature's LEFT (DESIGN.md); the bind pose stands on y = 0
with the root on the ground under the hip joints (plan §6.1).

SPEC is §4.1's dict, with W2's photo fits where the live animals measured otherwise (TAGS names each change and its
evidence: the front half-widths, the hind stance's MTP 80 mm behind the hip, the ear's station and base, the paws'
standing widths, the toes' PIP height, the outer digits' splay), plus SPEC['skin'], the hairless clay's numbers
(families/limbed.py build_skin_sdf), plus what the skeleton (families/limbed.py, W1) needs:
  * values the plan states in prose (§2.1, §2.4, §2.5, §6.1, §10), marked 'W1 addition' in TAGS: the withers' soft
    tissue, the 0.100 m in z_fore = 1.10 WH - 0.100, the occiput's reach, the scapula-top and carpus half-widths, the
    pelvis and spine heights, the hind-foot check's calcaneus and digit lengths;
  * a few estimates of my own where the plan gives none (the paw's digit layout, the spine's vertebral layout, the
    volume helpers' offsets), tagged [E] with the rule that made each, for the W2 photo overlays to correct.
TAGS holds every leaf's source tag in the plan's legend (§0): [P] primary measurement, [C] compiled secondary source,
[R] reference game asset (measured, never copied), [H] house rule or prior finding, [D] derived, [E] estimate to verify
at a named gate, [S] seen only in a search summary. w00_spec.py prints that every leaf carries one.

REGIONS: the region ids 0-9 (plan §4.1), for the cage's part one-hot, the bake's region output and the recipe's mask
regions. muzzle (ahead of the stop) and mouth (the lips inward) are split from head; paw is the MCP or MTP ring and
everything distal to it.
"""
import re

SPEC = dict(
    mass=40.0, head_body=1.18, tail_len=0.40, n_caudal=18,
    skull=dict(cbl=0.237, tol=0.265, fal=0.157, mnal=0.097, pal=0.120, c1b=0.047, zyb=0.143, entb=0.047,
               lb=0.042, mb=0.079, sh=0.088, mdl=0.189, trl=0.085), head_len=0.280,
    bones=dict(scapula=0.163, humerus=0.215, radius=0.214, mc3=0.094, femur=0.226, tibia=0.236, mt3=0.109,
               pelvis=0.188),
    jc=dict(scapula=0.150, humerus=0.198, radius=0.207, carpus_mcp=0.114, femur=0.215, tibia=0.229, hock_mtp=0.134,
            mcp_h=0.028, mtp_h=0.026),
    rest=dict(shoulder=107.0, elbow=146.9, carpus_ext=20.5, radius_lean=3.0, stifle=140.0, hock=140.0,
              hind_paw_behind_hip=0.080, fore_pad_ahead_withers=0.074,
              body_len_wh=1.145487, neck_pitch=40.0, palate_pitch=-15.0, jaw_open=12.0,
              tail_pitch=-25.0,             # the W3 merge gate sets the final value (§2.4)
              tail_rest=(-62.0, 4.0),       # W2c: the posed review's rest hang (root pitch, bend per joint)
              neck_review=(38.79, 0.3892, -34.86),   # W2d: w01's neck carriage for the posed review (WOLF_BODY_PHOTOS)
              withers_soft=0.030, shoulder_hip_offset=0.100, occiput_ahead_wh=0.38),
    # W2: the front-view photo fit replaces §2.4's SPECIMEN half-widths (plan §2.4 "the front-view photo fit replaces
    # them at W2"; WOLF_BODY_PHOTOS.md §4.1: forepaws 1.0-1.25 IO apart, mid-forearms 1.18-1.23 IO, elbows' outer
    # surface 2.13-2.33 IO over the coat, shoulders 2.9 IO over the coat)
    half_width=dict(shoulder=0.070, elbow=0.056, forepaw=0.045, hip=0.060, stifle=0.066, hock=0.054, hindpaw=0.054,
                    scapula_top=0.035, carpus=0.048),
    ear=dict(height=0.0876, base=0.076, rim_half=0.002, base_half=0.006, station=0.891,
             # W2t: the named carriages about the bind (canid.EAR_OUT / EAR_BACK / EAR_SWIVEL), (swivel, splay, tilt) deg as
             # w02_ears.carriage_matrix turns the pinna about the rig's ear_0; the runtime blends them (patches/wolf_ear_poses.md)
             # W2u: re-derived on the face construction with the facing held (the bind's swivel now 30: these are about it)
             # W2w: re-derived about the bind at ease (canid 23 / 15 / -3), the ears standing (w02_ears STAND_MAX), the clay
             # read within each trace's span (w02_ears ear_side)
             poses=dict(alert=(-27.5, 9.4, -7.3), relaxed=(77.4, -18.1, 4.9))),
    eye=dict(station=0.53, half_spacing=0.036, fissure=0.024, ball_r=0.012, cant=17.0, splay=20.0),
    paw=dict(fore=(0.115, 0.085), hind=(0.105, 0.078), claw=(0.022, 0.018),
             digit_len=(0.088, 0.079), p1_share=0.37, side_digit=((0.875, 0.838), (0.886, 0.937)),
             spread=(0.13, 0.31), splay=(0.0, 6.0),
             setback=((0.0030, 0.0039), (0.0015, 0.0008)), side_raise=((0.0114, 0.0147), (0.0123, 0.0068)),
             pip_h=0.029, pip_h_side=0.0255, tip_h=0.0015,
             dewclaw=dict(h=0.055, tip_h=0.025, medial=0.025, reach=0.014), calcaneus=0.045),
    coat=dict(cell=0.006, g_t=0.30, scale=1.0, hat_scale=0.3, ear_outer=0.004),    # §4.3, §5.5
    spine=dict(pelvis=(0.60, 0.0), ls=(0.61, 0.050), ct_y=0.58, ct_behind_shoulder=0.054895, lumbar_unit=1.4,
               cervical=(1.0, 1.1, 1.2, 1.25, 1.25, 2.2, 0.8), tail_root=(0.578, -0.016), breath_y=(0.47, 0.50)),
    helpers=dict(olecranon=(0.028, 0.018), triceps=0.040, patella=0.025, tuber_plantar=0.025,
                 gluteal=(0.040, 0.020, 0.010)),
    rig=dict(n_tail=8, twist_upper=1.0 / 3.0, twist_lower=2.0 / 3.0),
    family='limbed', head_archetype='canid',
    # W2, THE HAIRLESS CLAY (families/limbed.py build_skin_sdf; WOLF_PLAN §4.2): metres. Fitted by eye to the traced
    # live animals at matched scale (work/bestiary/tests/w02_clay.py): side views scaled by the withers height and
    # set on the ground and the withers, front views by the eye spacing, head views by nose tip and eye centre
    skin=dict(
        # the trunk-and-neck sweep, C0 (inside the head) to the point of buttock: (name, z, y, r0, aspect, a3, a4),
        # the section centre (sagittal), half-depth along the dorsal normal, width / depth, keel (phi3 pi), loin
        trunk=(('C0', 0.852, 0.778, 0.070, 0.80, 0.00, 0.00), ('C2', 0.800, 0.756, 0.076, 0.788, 0.00, 0.00),
               ('C4', 0.733, 0.683, 0.078, 0.794, 0.00, 0.00), ('C6', 0.6659, 0.62715, 0.072, 0.990, 0.01, 0.00),
               ('C7', 0.6255, 0.5911, 0.0885, 0.955, -0.005, 0.00), ('T1', 0.5899, 0.54966, 0.116, 0.783, 0.010, 0.00),
               # W2l: T4-T13 back on WOLF_PLAN §4.2's sections (width / depth 0.705-0.75, the keel a3 0.03-0.06), each
               # centre raised by r0 x the keel's change so the back line and the chest floor stay (skin.trunk's tag)
               ('T4', 0.520, 0.51511, 0.146, 0.705, 0.050, 0.00), ('T6', 0.450, 0.51419, 0.1465, 0.71, 0.060, 0.00),
               ('T10', 0.330, 0.52317, 0.1335, 0.72, 0.050, 0.00), ('T13', 0.250, 0.53187, 0.1237, 0.75, 0.03, -0.01),
               ('L4', 0.150, 0.5515, 0.0995, 0.82, 0.00, -0.02), ('S1', 0.020, 0.535, 0.112, 0.85, 0.00, -0.02),
               ('ISC', -0.004, 0.530, 0.090, 0.87, 0.00, -0.02)),
        trunk_round=(0.080, 0.090, 0.50, 0.55), trunk_nodes=320, trunk_smooth=0.060,
        trunk_round_sections=(0.040, 0.030),
        trunk_dense=(('T1', 0.06, 1.5), ('T13', 0.05, 0.8), ('S1', 0.05, 1.0)),
        # the withers' interscapular mass, the manubrium (the prosternum point) and the croup (the gluteal mass over
        # the pelvis, spanning the hips): ((y, z), radii (x, y, z), k)
        withers=((0.6005, 0.527), (0.080, 0.058, 0.135), 0.028),
        croup=((0.570, 0.022), (0.098, 0.058, 0.068), 0.030),
        trunk_not_masses=('withers', 'croup'),
        # W2d: the manubrium INSIDE the keel (no knob): the superficial pectorals either side of the keel's front, so
        # the chest's front profile runs smooth from the throat to the sternum's point ((y, z), lateral, radii, k)
        pectorals=(('pectoral', (0.458, 0.624), 0.022, (0.030, 0.042, 0.024), 0.032),),
        # the neck's muscles in the trunk group, round cones between chain anchors ((a, b, t, (lateral, up, forward))
        # each end, radii, k): the brachiocephalicus from behind the jaw's angle (under the ear) along the lower side of
        # the neck to the point of the shoulder (the ventral neck, the sternocephalicus' line, is the trunk sweep's own
        # surface: W3 w3a's cone down the throat hung under it as a plate)
        neck_muscles=(('brachiocephalicus', ('head', None, 0.0, (0.018, -0.042, -0.004)),
                       ('shoulder', None, 0.0, (0.006, 0.020, 0.012)), 0.016, 0.024, 0.020),),
        # a limb: path rows (a, b, t, (lateral, up, forward) offset, r0, aspect) on the chain, theta = 0 cranial;
        # muscles (name, a, b, t, cranial, lateral, along, (r_along, r_cranial, r_lateral), k) in the bone a -> b's
        # frame; tendons (name, (a, b, t, cranial, lateral[, along]) x 2, r1, r2, k); the group's k into the body
        fore=dict(
            # W2d: THE FOREARM ONE TAPER (the lead's call 3: "from just below the elbow to the carpus, no bulb, no
            # waist; the carpus a slight flare with the accessory carpal pad behind"): the sweep alone carries it, the
            # muscle bellies (W3's spindles: a bulb under the elbow, a waist where they ran out, a carpal knob) gone;
            # its depth along N (cranial) and width by its aspect: just under the elbow 86 deep x 55 wide, mid-forearm
            # 64 x 40, above the carpus 47 x 38, the carpus 49 x 42 (the flare). The mange coyote r05's planted foreleg
            # (0.487 mm / px by its chest depth): 165 px deep below the elbow, 110 at mid-forearm (80 / 54 mm), the
            # caudal outline one straight taper into a ~5 mm bulge at the accessory carpal; w01's summer forearm (over
            # 5 mm of coat) one straight taper too (research/wolf_work/checks/w01_fore.png).
            # W2h (the lead's call 4): the forearm's sections cranial of the bone line (the radius and its extensors in
            # front, the flexors behind), their CAUDAL edge on w01's near forearm's (10-17 mm behind the bone line, its
            # taper all behind) and the lower forearm held to the carpus (t 0.92) so the back runs straight into it
            # W2l: the forearm's rows (t 0.18-0.92) moved back by W2i's far-leg strip less W2e's table (their fronts 7-10
            # mm back, their backs kept): the front on w01's NEAR front (skin.fore.path's tag)
            # W2l (the whole-animal look): the shoulder row 0.80 -> 0.62 wide, 30 mm of tissue lateral of the joint (was
            # 38): with skin.trunk's narrower thorax the shoulders stood wider than the ribs from the top (tag)
            path=(('scapula_top', 'shoulder', 0.45, (-0.008, 0.0, 0.0), 0.042, 1.00),
                  ('shoulder', None, 0.0, (0.0, 0.0, -0.012), 0.048, 0.62),
                  ('shoulder', 'elbow', 0.50, (0.0, 0.0, 0.0), 0.042, 0.80),
                  ('elbow', None, 0.0, (0.0, 0.0, 0.008), 0.035, 0.76),
                  ('elbow', 'carpus', 0.18, (0.0, 0.0, 0.0189), 0.0343, 0.75),
                  ('elbow', 'carpus', 0.50, (0.0, 0.0, 0.0095), 0.0232, 0.78),
                  ('elbow', 'carpus', 0.82, (0.0, 0.0, 0.0056), 0.0190, 0.88),
                  ('elbow', 'carpus', 0.92, (0.0, 0.0, 0.0066), 0.0174, 0.93),
                  ('carpus', None, 0.0, (0.0, 0.0, -0.001), 0.0245, 0.86),
                  ('cmc', None, 0.0, (0.0, 0.0, 0.0), 0.0200, 1.05),
                  ('mcp', None, 0.0, (0.0, 0.0, 0.0), 0.0195, 1.35)),
            muscles=(('triceps', 'shoulder', 'elbow', 0.55, -0.034, 0.004, 0.0, (0.068, 0.034, 0.030), 0.014),
                     ('deltoid', 'scapula_top', 'shoulder', 0.78, 0.004, 0.016, 0.0, (0.048, 0.024, 0.014), 0.014),
                     ('biceps', 'shoulder', 'elbow', 0.40, 0.020, 0.0, 0.0, (0.052, 0.018, 0.018), 0.012),
                     ('olecranon', 'elbow', 'carpus', 0.0, -0.023, 0.0, -0.010, (0.018, 0.014, 0.015), 0.006),
                     ('acc_carpal', 'carpus', 'cmc', 0.25, -0.013, 0.0, 0.0, (0.010, 0.007, 0.008), 0.006)),
            # W2h (the lead's call 4): THE CRANIAL MUSCLE MASS, the extensor group (the extensor carpi radialis, the common
            # and lateral digital extensors, the abductor pollicis longus) over the radius's distal half into the carpus'
            # front, so the forearm's front stands straight as w01's near forearm's does (its taper all behind)
            # W2h b: the FLEXOR mass behind (the deep digital flexor and the flexor carpi ulnaris over the radius's
            # caudal side): the body volume's flow drew the forearm's caudal edge 4-6 mm forward of the composed sweep's
            # at mid-forearm (the sweep is no inner limit), its column then leaning +3.5 deg (the photos to +2.1, +-1)
            # W2l: the extensors 10 mm back (35.0 -> 25.0 mm cranial: their inset front, the volume's inner limit, held
            # the lower forearm's front 8-10 mm ahead of w01's near front by W2i's strip; skin.fore.spindles' tag)
            spindles=(('extensors', 'elbow', 'carpus', 0.40, 0.975, 0.0250, 0.0, 0.0205, 0.0165, 0.012),
                      ('flexors', 'elbow', 'carpus', 0.45, 0.95, -0.0042, 0.0, 0.0075, 0.0100, 0.010)),
            # W2l (the lead's "the elbow's knob"): the ULNAR FLEXOR mass under the olecranon (skin.fore.tendons' tag)
            tendons=(('flexor_tendons', ('carpus', 'mcp', 0.15, -0.014, 0.0), ('carpus', 'mcp', 0.85, -0.011, 0.0),
                      0.008, 0.007, 0.006),
                     ('ulnar_flexor', ('elbow', 'carpus', 0.0, -0.026, 0.0), ('elbow', 'carpus', 0.20, -0.013, 0.0),
                      0.011, 0.008, 0.010)),
            not_masses=('olecranon', 'acc_carpal'),
            k=0.028, smooth=0.020),
        hind=dict(
            path=(('hip', None, 0.0, (0.0, 0.0, 0.0), 0.030, 1.00),
                  ('hip', 'stifle', 0.22, (0.0, 0.0, 0.004), 0.047, 0.85),
                  ('hip', 'stifle', 0.50, (0.0, 0.0, 0.006), 0.054, 0.80),
                  ('stifle', None, 0.0, (0.0, 0.0, 0.0), 0.040, 0.80),
                  ('stifle', 'hock', 0.20, (0.0, 0.0, 0.0), 0.034, 0.80),
                  ('stifle', 'hock', 0.55, (0.0, 0.0, 0.0), 0.026, 0.80),
                  ('stifle', 'hock', 0.85, (0.0, 0.0, 0.0), 0.019, 0.82),
                  ('hock', None, 0.0, (0.0, 0.0, 0.0), 0.018, 0.82),
                  ('tmt', None, 0.0, (0.0, 0.0, 0.0), 0.0175, 1.00),
                  ('mtp', None, 0.0, (0.0, 0.0, 0.0), 0.0185, 1.30)),
            muscles=(('quadriceps', 'hip', 'stifle', 0.45, 0.036, 0.004, 0.0, (0.085, 0.032, 0.034), 0.016),
                     ('biceps_femoris', 'hip', 'stifle', 0.38, -0.012, 0.010, 0.0, (0.090, 0.033, 0.034), 0.016),
                     ('gluteals', 'hip', 'stifle', 0.12, -0.012, 0.014, 0.0, (0.045, 0.040, 0.026), 0.016),
                     ('gastrocnemius', 'stifle', 'hock', 0.28, -0.024, 0.002, 0.0, (0.065, 0.022, 0.020), 0.014),
                     ('patella', 'stifle', 'hock', 0.0, 0.022, 0.0, -0.010, (0.015, 0.009, 0.013), 0.008)),
            # W2d: THE HOCK A POINT (the lead's call 3: "the calcaneus with the common calcanean tendon running up from
            # it, not a ball"): the tuber calcanei a short tapered lever from the hock joint's back to its tip (r05's
            # planted hind leg: a rounded point, tip radius ~12-15 mm), the common calcanean tendon from the
            # gastrocnemius down onto the tip and the plantar ligament from the tip down the cannon, so the two
            # outlines meet at the tuber as a corner (W2-W2c's calcaneus ellipsoid read as a ball)
            tendons=(('achilles', ('stifle', 'hock', 0.55, -0.026, 0.0), ('hock', 'tmt', 0.0, -0.023, 0.0, -0.041),
                      0.010, 0.0062, 0.008),
                     ('plantar', ('tmt', 'mtp', 0.0, -0.013, 0.0), ('tmt', 'mtp', 0.90, -0.010, 0.0),
                      0.007, 0.007, 0.006),
                     ('tuber', ('hock', 'tmt', 0.0, -0.010, 0.0, -0.012), ('hock', 'tmt', 0.0, -0.022, 0.0, -0.040),
                      0.0115, 0.0072, 0.006),
                     ('flexor_fill', ('stifle', 'hock', 0.50, -0.010, 0.0), ('hock', 'tmt', 0.0, -0.016, 0.0, -0.030),
                      0.016, 0.011, 0.016),
                     ('calc_plantar', ('hock', 'tmt', 0.0, -0.022, 0.0, -0.040), ('tmt', 'mtp', 0.35, -0.010, 0.0),
                      0.0072, 0.0072, 0.010)),
            not_masses=('patella', 'tuber'),
            k=0.022, smooth=0.035),
        # the paws: digit radii (MCP / MTP head, PIP, claw bed); II and V scaled; the claw bed this share of the claw
        # behind its tip and raised; the pads (lateral, height, along[, forward]); the PALM, the mass that holds the
        # digits together over the metapodial heads and the proximal phalanges (a rounded box: half extents lateral,
        # vertical, along; its centre's height and forward offset from the MCP / MTP head; its corner radius); the
        # carpal pad (lateral, radius, along, back, down); the dewclaw radii; ks
        # W2l: the claws short tapered hooks (claw_section, claw_dir, claw_tip_scale, claw_base, crest) and the heels'
        # backs one slope into a rounded heel (heel, heel_hind): their tags
        paw=dict(digit_r=(0.0115, 0.0112, 0.0105, 0.0090), digit_r_hind=(0.0110, 0.0107, 0.0100, 0.0086),
                 side_scale=0.88, dip=(0.38, 0.0075), crest=(0.645, 0.0045),
                 claw_section=((0.0110, 0.0062), (0.0096, 0.0054)), claw_dir=(28.0, 70.0), claw_tip_scale=0.18,
                 claw_taper=1.0, claw_fold=(0.0010, 0.0030, 0.0020),
                 claw_rho=0.0008, claw_base=(-0.0045, -0.0005), dewclaw_section=(0.0050, 0.0034), k_claw=0.0015,
                 web=(0.006, 0.002, 0.75, 0.004),
                 ramp=(0.020, 28.0, 0.010, 0.022, 0.012), ramp_hind=(0.018, 28.0, 0.009, 0.020, 0.012),
                 heel=(0.038, 0.006, -0.014, 0.020, 0.0062, 0.0100, 0.008, 0.006),
                 heel_hind=(0.028, 0.005, -0.013, 0.018, 0.0070, 0.0095, 0.008, 0.006), k_meta=0.008,
                 pad_digital=(0.0095, 0.0105, 0.0160), pad_digital_hind=(0.0090, 0.0100, 0.0150), pad_along=0.45,
                 pad_meta=(0.023, 0.0090, 0.020, -0.010, 0.0090), pad_meta_hind=(0.020, 0.0085, 0.018, -0.008, 0.0085),
                 knuckle=(0.036, 0.013, 0.017, 0.027, 0.012), knuckle_hind=(0.033, 0.012, 0.016, 0.025, 0.010),
                 pad_carpal=(0.0045, 0.0050, 0.0045, 0.017, 0.022), dewclaw_r=(0.0048, 0.0035), dew_claw=0.009,
                 k=0.008, k_digit=0.008, k_pad=0.006, k_palm=0.008),
        # the tail: path rows on the tail chain (from 33 mm inside the croup to near the tip), round; its k
        tail=dict(path=(('tail_0', None, 0.0, (0.0, -0.006, 0.030), 0.044, 1.40),
                        ('tail_0', None, 0.0, (0.0, 0.0, 0.004), 0.031, 1.15),
                        ('tail_0', 'tail_1', 0.6, (0.0, 0.0, 0.002), 0.023, 1.0),
                        ('tail_2', None, 0.0, (0.0, 0.0, 0.0), 0.020, 1.0),
                        ('tail_4', None, 0.0, (0.0, 0.0, 0.0), 0.015, 1.0),
                        ('tail_6', None, 0.0, (0.0, 0.0, 0.0), 0.011, 1.0),
                        ('tail_tip', 'tail_7', 0.15, (0.0, 0.0, 0.0), 0.006, 1.0)),
                  k=0.014, smooth=0.020, fillet=(0.140, 0.175)),
        # W2d: the body as GRID volumes on the head's method (species/wolf_body.py; families/limbed.build_volume_sdf)
        volume=True,
        # W2h (the lead's call 6: "the r03-derived bands carry their evidence in SPEC tags"): the head's bands that follow
        # the wet r03 (w02's skin depths over the skull, the muzzle at two stations): metres
        head_bands=dict(canine_skin=(0.008, 0.013), muzzle_width_d40=(0.061, 0.083)),
    ),
)

REGIONS = ('torso', 'neck', 'head', 'muzzle', 'mouth', 'ear', 'forelimb', 'hindlimb', 'paw', 'tail')
REGION_ID = {name: i for i, name in enumerate(REGIONS)}

_HW = '[E]', '§2.4: the SPECIMEN reconstruction standard (unsourced); the W2 front-view photo fit replaces it'
_HWF = ('[P] [E]', 'W2 front-view photo fit (WOLF_BODY_PHOTOS §4.1, w08 near-level, w07 camera above; IO = 80 mm, the '
                   'paws about 10 % farther from the camera than the eyes): forepaw centres 1.0-1.25 IO apart, '
                   'mid-forearm centres 1.18-1.23 IO, elbows 2.13-2.33 IO over the coat, shoulders 2.9 IO over the '
                   'coat; §2.4\'s SPECIMEN half-widths (+-72 paws, +-77 elbows, +-94 shoulders) stood the wolf like a '
                   'mastiff')
_HWH = ('[E]', 'W2: no rear view among the photos; narrowed with the front (the hips no wider than the shoulders, the '
               'hind paws in line with the narrow fore track, as w06\'s three-quarter view shows); §2.4 had hips +-74, '
               'stifles +-77, hocks +-61, hind paws +-67')
TAGS = {
    'mass': ('[C] [P]', '§2.1: mean 40 kg (Macdonald 2001 via Wikipedia "Wolf"); Slovak males mean 39.9 '
                        '(Comor & Canady 2011)'),
    'head_body': ('[P] [C]', '§2.1: nose tip to tail base on the curve; Slovak males mean 118.1 cm; 1.05-1.60 m '
                             '(Heptner & Naumov)'),
    'tail_len': ('[P] [C]', '§2.1: vertebrae, hair excluded; Slovak males mean 39.2 cm; 0.29-0.50 m'),
    'n_caudal': ('[P]', '§2.1: 20 (Flower) and 17 (USNM 3138), Stock, Lance & Nigra 1946; W1 takes 18'),
    'skull.cbl': ('[P]', '§2.2: Andersone & Ozolins 2000, Latvian males: condylobasal length, mean 237 (208-259)'),
    'skull.tol': ('[P]', '§2.2: prosthion to sagittal crest, mean 265 (230-288)'),
    'skull.fal': ('[P]', '§2.2: frontal midpoint to prosthion, mean 157'),
    'skull.mnal': ('[P]', '§2.2: nasal length MNaL, mean 97'),
    'skull.pal': ('[P]', '§2.2: palate length, mean 120'),
    'skull.c1b': ('[P]', '§2.2: breadth across the upper canines, mean 47'),
    'skull.zyb': ('[P]', '§2.2: zygomatic breadth, mean 143 (118-161)'),
    'skull.entb': ('[P]', '§2.2: interorbital breadth, mean 47'),
    'skull.lb': ('[P]', '§2.2: postorbital constriction, mean 42'),
    'skull.mb': ('[P]', '§2.2: mastoid breadth, mean 79'),
    'skull.sh': ('[P]', '§2.2: skull height, mean 88'),
    'skull.mdl': ('[P]', '§2.2: mandible length, mean 189'),
    'skull.trl': ('[P]', '§2.2: upper tooth row P1-M2, mean 85'),
    'head_len': ('[E]', '§2.5: external head length, nose tip to the occiput skin: ToL 265 [P] plus soft tissue'),
    'bones.scapula': ('[P] [D]', '§2.3: 0.76 x humerus (Allen 1885: wolf scapula : humerus = 76 : 100)'),
    'bones.humerus': ('[P]', '§2.3: Samuels, Meachen & Sakai 2013 212.1; Iberian 180-228 [S]; Allen 1885 ~210'),
    'bones.radius': ('[P] [D]', '§2.3: R/H 0.994 (Samuels 2013: 210.94 / 212.12)'),
    'bones.mc3': ('[E]', '§2.3: 0.44 R (dire wolf 0.42, Nigra & Lance 1947; grey wolf distal segments relatively '
                         'longer [P])'),
    'bones.femur': ('[P] [D]', '§2.3: H/F 0.951 (Stock & Lance 1948 humerofemoral index, C. lupus n = 8)'),
    'bones.tibia': ('[P] [D]', '§2.3: R/T 0.906 (Stock & Lance 1948 radiotibial index)'),
    'bones.mt3': ('[E]', '§2.3: 0.46 T (dire wolf 0.41; grey wolf metatarsus "significantly longer", Stock & Lance '
                         '1948)'),
    'bones.pelvis': ('[P] [D]', '§2.3: 0.83 F (Allen 1885: wolf pelvis : femur = 83 : 100)'),
    'jc.scapula': ('[D] [E]', '§2.3: glenoid to the dorsal border, 0.92 x greatest length (factor [E])'),
    'jc.humerus': ('[D] [E]', '§2.3: 0.92 x greatest length (factor [E])'),
    'jc.radius': ('[D] [E]', '§2.3: 0.97 x greatest length (factor [E])'),
    'jc.carpus_mcp': ('[E]', '§2.3: carpus joint to MCP: the carpal row (~20 mm [E]) plus MC III'),
    'jc.femur': ('[D] [E]', '§2.3: 0.95 x greatest length (factor [E])'),
    'jc.tibia': ('[D] [E]', '§2.3: 0.97 x greatest length (factor [E])'),
    'jc.hock_mtp': ('[E]', '§2.3: hock to MTP: the distal tarsal rows (~25 mm [E]) plus MT III'),
    'jc.mcp_h': ('[E]', '§2.4: the MCP joint centre over the ground under load (digit and pad stack)'),
    'jc.mtp_h': ('[E]', '§2.4: the MTP joint centre over the ground under load'),
    'rest.shoulder': ('[P]', 'W2e: 107, the LRD\'s (Humphries et al. 2020 S4 Table, 180 - flexion: LRD 104-110, GSD '
                             '120-121, SD 8-10), the flatter scapula of the side photos\' stance (the forelimb placed by '
                             'the pad contact and the forearm\'s lean, rest.fore_pad_ahead_withers); W1 110'),
    'rest.elbow': ('[P] [D]', 'W2h (the lead\'s call 4: "put W0\'s humerus band and W1\'s elbow band back on the WOLF '
                              'evidence (w01\'s 53.2 deg lies inside the old band); make the forearm\'s front by its '
                              'CRANIAL MUSCLE MASS"): 146.9 with the radius 3.0 and the metacarpus 20.5, placed with the '
                              'clay\'s bones (work/bestiary/wolf/scratch_w2h/stance.py place 146.9 3.0 107 20.5): the '
                              'humerus 59.9 (W0 40-60, AG 05.5; w01\'s own 53.2 inside), the elbow inside W1\'s 129.9-147.0 '
                              '(w01\'s own 138.2 inside), the forepad +74.7 (w02 the stance: +74 +-10). Under the humerus '
                              'ceiling the elbow joint stands +2.8 ahead of the withers (W2g +11.8): the radius is held '
                              'at 3.0 so the elbow point\'s line to the carpus stays inside the photos\' 5.3-14.2 (+-1; at '
                              '5.0 it read ~16 on the composed forelimb, scratch_w2h/fore_probe.py), and the forearm\'s '
                              'front stands on w01\'s by the extensors (skin.fore.spindles) and the sweep\'s cranial '
                              'offsets (skin.fore.path). '
                              'W2g (the lead\'s call 5: "W0\'s humerus band follows the WOLF evidence as W1\'s elbow band '
                              'did ... so the forearm stands as a COLUMN under the shoulder, its front within about 10 mm '
                              'of w01\'s traced front less the coat, the pastern at w01\'s measured lean (not 19.5 deg), '
                              'the forepad still at +73-75"): 149.34, solved with the clay\'s bones for the forepad +74, '
                              'the radius 2.4 (the forearm\'s column ~+0.1 on this clay: w01 +0.1), the metacarpus 16.5 '
                              '(w01\'s, WOLF_BODY_PHOTOS §3.3) and the shoulder 107 (work/bestiary/wolf/scratch_w2g/'
                              'forelimb.py): the humerus 61.7 deg below the horizontal (W0\'s band now 40-62.5: AG 05.5 '
                              'stops at 60) and the elbow 149.3 (W1\'s band now 129.9-150.0); the elbow joint 10 mm and the '
                              'carpus 5.5 mm forward of W2f\'s, so the forearm stands under the shoulder with its front at '
                              'w01\'s near front (w02 the stance). THE WOLF EVIDENCE: w01 is the one square side view with '
                              'the point of the shoulder traced (w02 stands square in winter coat, its shoulder under the '
                              'mane). Its joints read from its surface points by the clay\'s own offsets (the elbow point '
                              '40 mm caudal of and 6.5 mm under the elbow joint, measured on the W2f clay; the point of the '
                              'shoulder 32 +- 10 mm cranial of its joint [E]) give the humerus 53.2 (50.2-56.3), the elbow '
                              '138.2 (135.2-141.3) and the shoulder 96.1 (92.3-100.5), but its elbow joint then stands 32 '
                              'mm over the clay\'s (0.57 WH), its humerus reads 178 mm for the bones\' 198 and its radius '
                              '255 for 207: those points do not carry the bones\' angles, the stance does (the pad, the '
                              'column, the pastern, the front: what the photo shows), as W2f found for the elbow. '
                              'W2f: 146.1. '
                              'W2f (the lead\'s call 4: "put the forepad at w01\'s +73 / the two-pad median +75 ... where '
                              'W1\'s dog angle bands stop it, measure w01\'s own joint angles ... and let the band follow '
                              'the WOLF evidence"): 146.1, solved with the clay\'s bones to w01\'s SQUARE stance '
                              '(work/bestiary/wolf/scratch_w2f/stance_solve.py, stance_feasible.py): the pad contact +74 '
                              'ahead of the withers (w01 +73, the two-pad median +75), the forearm\'s column as the '
                              'photos\' (radius 3.6, its midline ~+1.3; the photos -6.7..+2.5, w01 -0.1), the metacarpus '
                              '19.5 from vertical (the photos 2.4-20.0; rest.carpus_ext), the shoulder kept at 107 (WH '
                              'within 2.3 mm: the photos\' scale; the trunk is absolute) and the humerus at W0\'s AG 05.5 '
                              'ceiling (59.7 of 40-60). The dog band (Humphries 2020 S4, every breed and side\'s mean +- 1 '
                              'SD: 129.9-143.4) stops at 143.4, where the pad +74 needs the radius 6.2 deg forward (the '
                              'column ~3.9, past the photos\' +2.5) and the carpus 8.8 dorsiflexed (W1 10-20); the band now '
                              '129.9-147.0 (w01_skeleton.py). w01\'s own joints read from its surface points by the '
                              'clay\'s landmark offsets (scratch_w2f/w01_joints.py) give 135-141 for the elbow and 92-100 '
                              'for the shoulder, but its traced carpus (the accessory carpal bulge) and MCP stand 20-30 mm '
                              'off the joints (its radius reads 258 mm for the 207 of the bones): the stance, not those '
                              'points, is the measure. W2e 143; W1 137 (the two breed means)'),
    'rest.carpus_ext': ('[P] [E]', 'W2h (the lead\'s call 4: "the pastern at w01\'s +22.7 deg (+-3)", the skin read like '
                                   'for like in w02): 20.5, the bone\'s lean that carries the skin\'s pastern to w01\'s '
                                   '+22.7 (W2g\'s 16.5 read +19.6 on the skin; the composed forelimb reads +20.9 at 20.5 '
                                   'and w02\'s skin read ~1.4 more on W2g, scratch_w2h/fore_probe.py), the carpus '
                                   'dorsiflexed 17.5 (W1 10-20). '
                                   'W2g (the lead\'s call 5: "the pastern at w01\'s measured lean (not 19.5 deg)"): 16.5, '
                                   'w01\'s metacarpus column (WOLF_BODY_PHOTOS §3.3; its traced edges\' midline from 5 px '
                                   'under the carpus to the MCP 15.9, scratch_w2g/forelimb.py), the carpus dorsiflexed 14.1 '
                                   '(W1 10-20); the clay\'s pastern read on its skin like for like in w02 (the stance). '
                                   'W2f (call 4): 19.5, the metacarpus 19.5 deg from vertical, inside the side photos\' '
                                   'carpus-to-MCP columns (WOLF_BODY_PHOTOS §3.3: 2.4-20.0, median 12.7, w01 16.5), the '
                                   'carpus dorsiflexed 15.9 (§2.4 "standing dogs dorsiflex 10-20 deg"): with the elbow '
                                   'and the radius it carries the forepad to w01\'s square stance under W0\'s humerus '
                                   'ceiling (rest.elbow); W2e 15 (the metacarpus 75 deg above the horizontal [E])'),
    'rest.radius_lean': ('[P] [D]', 'W2h (call 4): 3.0 deg (distal end forward), with the elbow 146.9 (rest.elbow): on the '
                                    'composed forelimb the elbow point\'s line to the carpus reads 13.2 deg (the photos '
                                    '5.3-14.2, +-1; w02 ~1.2 more) and the column\'s midline +2.6 (the photos -7.1..+2.1, '
                                    '+-1; w01\'s near forearm +3.0 with the far leg\'s lead taken off its traced front). '
                                    'W2g (call 5, "the forearm stands as a COLUMN under the shoulder"): 2.4 deg, the '
                                    'column\'s midline ~+0.1 on this clay (lean - 2.3, W2e/W2f) for w01\'s +0.1 (its near '
                                    'forearm\'s front vertical on the photo: scratch_w2eb/out/w01_fore_front.png), with the '
                                    'elbow 149.34 and the metacarpus 16.5 (rest.elbow). '
                                    'W2f (call 4): 3.6 deg (distal end forward), with the elbow 146.1 and the carpus 19.5 '
                                    'the forepad at w01\'s square +74 (rest.elbow); the forearm\'s column (the midline of '
                                    'its edges) ~+1.3 on this clay, inside the side photos\' -6.7..+2.5 (WOLF_BODY_PHOTOS '
                                    '§3.3). W2e 2.53 (the pad at the near forepads\' median +41, the column +0.2); W2d 4.0; '
                                    '§2.4 4 [E]'),
    'rest.fore_pad_ahead_withers': ('[P]', 'W2f (the lead\'s call 4: "the clay stands square: put the forepad at w01\'s '
                                           '+73 / the two-pad median +75"): the forepaw\'s ground contact 74 mm ahead of '
                                           'the withers\' skin. W2e built +41, the median of the five side views\' traced '
                                           'NEAR forepads (w01 +73, w02 +41, w03 +13, w04 +44, w05 -24 mm at WH 657), three '
                                           'of which stand staggered with the near foreleg back (their far forepads +109, '
                                           '+118, +81): the square stance\'s like for like is w01\'s +73 or each photo\'s two '
                                           'forepads\' mean, median +75. Gated in w02 (the stance); the clay\'s contact is '
                                           'the paw\'s ground vertices\' centre, ~21 mm ahead of the MCP'),
    'rest.stifle': ('[P]', '§2.4: Milgram 2004 138 (cited), Giansetto 2022 145, GSD 136, LRD 146; W1 140'),
    'rest.hock': ('[P]', '§2.4: GSD 123 (bred over-angulated), LRD 153; W1 140'),
    'rest.hind_paw_behind_hip': ('[E] [P]', 'W2 side-photo check (plan §8: "the steep femur ... must survive the W2 '
                                            'side-photo check"): the MTP 80 mm behind the hip joint, §2.6\'s own '
                                            'row (140, 140, 80): metatarsus 83, tibia 57, femur 83 deg. W1 had 40 '
                                            '(metatarsus 11.5 deg off vertical); the live side views stand it near '
                                            'vertical (median 0.0, -13.5 to +11.4) under a gaskin leaning 37 deg '
                                            '(WOLF_BODY_PHOTOS §3.3), and w01\'s square stance puts its MTP about '
                                            '110 mm behind the trochanter; 80 is the steepest posture inside the '
                                            'measured dog stance (W0 gate)'),
    'rest.body_len_wh': ('[E] [D] [P]', 'W2h: 1.145487, solved with the W2h stance (scratch_w2h/stance.py) so the '
                                        'withers stays at 545.5 mm. '
                                        'W2g: 1.14661, solved with the W2g stance (scratch_w2g/forelimb.py) so the '
                                        'withers stays at 545.52 mm. '
                                        'W2f: 1.1439, solved with the stance (scratch_w2f/stance_solve.py) so the '
                                        'withers stays at its W2d / W2e z (545.5 mm) while the elbow, the radius and the '
                                        'carpus carry the forepad to +74; W2e: 1.1273, solved with the stance '
                                        '(stance_solve.py) so the withers (the '
                                        'scapula\'s dorsal end, the photos\' registration point) stays at its W2d z while '
                                        'the flatter scapula carries the shoulder joint 16 mm forward: the trunk, the '
                                        'spine and the photos\' lines keep their places. w01 measures 1.117 (point of '
                                        'shoulder to ischium, WOLF_BODY_PHOTOS §3.1); §2.4: point of shoulder to point of '
                                        'buttock 1.10 WH (GSD standard 1.10-1.17; Sol 1.16)'),
    'rest.neck_pitch': ('[E] [R]', '§2.4: the neck axis rises 40 deg from the withers; the study-T canine neck rises '
                                   '39.6 deg [R]'),
    'rest.palate_pitch': ('[E]', '§2.4: hard palate 15 deg below the horizontal'),
    'rest.jaw_open': ('[H]', '§2.4: bound 12 deg open, closed by the runtime (SPECIMEN bound at 0.35 rad; AG 05.13)'),
    'rest.tail_pitch': ('[E]', '§2.4: 25 deg below the horizontal at bind; the W3 merge gate sets the final value'),
    'rest.tail_rest': ('[P] [E]', 'W2c: the posed review\'s REST HANG (the bind keeps tail_pitch, straight): the root '
                                  '62 deg below the horizontal, 4 deg more per joint (8 joints: the last segment 90), '
                                  'so the root-to-tip chord hangs 76 deg and the tip sits 0.30 WH over the ground: the '
                                  'side photos\' tails hang 53-92 deg (median 82.6) root to fur tip, the tip at the '
                                  'hock, 0.16-0.53 WH (WOLF_BODY_PHOTOS §3.4); the bend is [E]'),
    'rest.neck_review': ('[P]', 'W2d (the lead\'s call 5: "the REVIEW POSE carries the head and neck at w01\'s measured '
                                'neck pitch, so the side overlays compare like with like (the bind unchanged)"): w01\'s '
                                'neck angle withers (skin) to occiput 38.79 deg, its length 0.3892 WH, the head\'s '
                                'occiput-to-nose line -34.86 deg (research/wolf_work/data/res_w01.json: neck_angle, '
                                'neck_len, head_pitch); limbed.solve_neck_pose turns C7/T1, C4, C1 and the head to them '
                                '(the bind\'s 0.470 WH at 36.1 deg, the head -27.0)'),
    'rest.withers_soft': ('[E]', 'W1 addition, §2.4 table: withers (skin) 658 = the scapula\'s dorsal border 628 + 30 '
                                 '(spinous tips and skin: wolf_numbers.py WITHERS_SOFT)'),
    'rest.shoulder_hip_offset': ('[E]', 'W1 addition, §2.4 / §10: body length 724 minus the hip joint 624 behind the '
                                        'shoulder joint (z_fore = 1.10 WH - 0.100)'),
    'rest.occiput_ahead_wh': ('[E]', 'W1 addition, §2.4: occiput to withers projected 0.38 WH = 250 mm'),
    'half_width.shoulder': _HWF, 'half_width.elbow': _HWF,
    'half_width.forepaw': ('[P] [E]', 'W3: the forepaw centres 88 mm apart (1.1 IO, inside the front views\' 1.0-1.25 '
                                      'IO: w08 80, w07 100 mm), so the legs converge from the elbows (112 mm) to the '
                                      'paws as the photos\' lateral edges do (3-6 deg, paws inward; WOLF_BODY_PHOTOS '
                                      '§4.1); W2 96 mm. W2c 90 mm (1.13 IO): W2c\'s fuller digits (the bun paws) left '
                                      'the two digit IIs 2.0-2.8 mm apart at the PIP, where their two capsules\' blend '
                                      'swells the joint (AG 05.13 asks 3)'),
    'half_width.hip': _HWH,
    'half_width.stifle': _HWH, 'half_width.hock': _HWH, 'half_width.hindpaw': _HWH,
    'half_width.scapula_top': ('[E]', 'W1 addition, §6.1 joint table: scapula top (+-0.035, 0.628, 0.547)'),
    'half_width.carpus': _HWF,
    'ear.height': ('[C] [P]', 'W2u (the lead\'s call: "SPEC ear.height and the named poses re-derived" with the pinna '
                              'rebuilt face-on): 87.6 mm from the face construction\'s root (canid ear_frame at EAR_Q / '
                              'EAR_X 44 mm), the face outline\'s height fitted with every traced ear\'s carriage and the '
                              'facing held per photo (work/bestiary/wolf/check_w2u_ears: joint fit j1, re-scored on the '
                              'face normal, s3 / s4): 84 / 92 / 96 each lose a gate (H 92 / 96 w07_R, 84 w08_L), r03\'s '
                              'wet ears filled at their 3.5 mm rim (gaps 3.2 / 3.3, fit u3) at 87.6. '
                              'W2t (the lead\'s call 4: "re-derive SPEC ear.height at the measured 3.5 mm wet rim"): 88 '
                              'mm, the mean of r03\'s two leather pinnae with the MEASURED wet rim hair (w02_ears RIM wet '
                              '3.5, W2s: the wet r03\'s own fur gap 3.5 / 3.7) and the bind\'s tilt back (canid.EAR_BACK '
                              '12): the tips 90.1 / 93.0 mm from the root less 3.5, 86.6 / 89.5 (the W2e tool re-run, '
                              'work/bestiary/wolf/check_w2t/out/r03_pinna.json via scratch_w2e/ear_measure.py 12). '
                              'W2e: 90 mm from the base\'s middle (canid ear_frame\'s root; the joint ear_0 is the '
                              'concha\'s pivot, canid.EAR_PIVOT), the WET wolf r03\'s leather pinna (the lead: "the '
                              'height from r03 ... the SPEC ear height yields"): its two traced tips in its solved camera '
                              'with the fore / back tilt held at the side views\' 8 deg give 89.3 / 94.3 mm less the 1.5 '
                              'mm wet rim, 87.8 / 92.8 (work/bestiary/wolf/scratch_w2e/ear_measure.py; a tilt 5 deg '
                              'further back or forward moves it 4-5 mm). W2d: 97.7 from the root, the ear fit\'s '
                              '(one pinna inside the furred outlines of w12, r03, w07, w08, w01 and w03, work/bestiary/'
                              'tests/w02_ears.py). W3: 100 mm at the skin from the root (the lead\'s review: "about 100 mm at '
                              'the skin, 112 with hair"; the side views 112 tip to notch over the rim hair, '
                              'WOLF_BODY_PHOTOS §3.2); §2.5 105 from the notch (Heptner 90-110 [C]); Slovak mean 12.7 '
                              'cm, method unstated [P]'),
    'ear.poses.alert': ('[P]', 'W2w (the lead\'s call: "the named poses re-derived about the new bind"): the MEDIAN of '
                               'the head fronts\' solved carriages about the W2w bind at ease (23 / 15 / -3: canid '
                               'EAR_OUT / EAR_BACK / EAR_SWIVEL; w12, r03, w07 both ears, w08 left out), each solved with '
                               'the facing held per photo, the clay read within each trace\'s span (w02_ears ear_side) and '
                               'the ears standing (w02_ears STAND_MAX: no high front\'s depth-reversal twin), w02 _w2we1 '
                               '(tests/out/wolf/w02_ears_fit_w2we1.json; work/bestiary/wolf/check_w2w_ears/poses.py): the '
                               'concha turned in 27.5 deg, so the opening faces 4 deg in of forward and 7 up (the bind: 20 '
                               'out, 6 up), the joint axis 11 back and 24 out (the bind 17 / 15); all six fronts stand '
                               '(their axes 2-21 back) inside their furred outlines with the concha toward the camera '
                               '(cos 0.70-0.88, the concha share 0.85-0.98). '
                               'W2u: the MEDIAN of the head fronts\' solved carriages about the W2u bind (38 / 12 / +30: '
                               'canid EAR_OUT / EAR_BACK / EAR_SWIVEL; w12, r03, w07 both ears, w08 left out as W2t did), '
                               'each solved with the facing held on the face normal (w02_ears FACE_FLOORS, '
                               'canid.ear_face_frame; work/bestiary/wolf/check_w2u_ears fit u3 at w02\'s precision, '
                               'out/gate_poses_u3.json): the concha turned IN 50 deg, so the opening faces 2 deg in of '
                               'forward and 13.7 up (the bind: 41 out, 19.5 down); every front shows its concha (cos '
                               '0.68-0.93, the concha share 0.93-0.99). Three right ears (w12, w07, w08) solve tipped back '
                               '58-67 deg, their lefts at -4.5..12.4: the median keeps 8.4. '
                               'W2t (the lead\'s call 4: "fit the alert carriage (the fronts) and the relaxed one (the '
                               'sides) separately and record both as named ear poses the runtime can blend"): the MEDIAN of '
                               'the head-front photos\' own solved carriages about the bind 38 / 12 / -9 (w02 _w2t1, '
                               'tests/out/wolf/w02_ears_fit_w2t1.json: w12, r03, w07 both ears; w08 left out, one ear turned '
                               'to show its back, the other tipped back 59): nearly the bind itself, splayed 7 deg in; the '
                               'leather at p95 w12 L -3.1 / R +8.4, r03 +2.6 / +0.9, w07 +1.3 / +3.3 mm off the furred '
                               'outlines, filling them to 6.5-13 mm (work/bestiary/wolf/check_w2t/out/ear_poses_med.json, '
                               'ear_poses_on_photos_med.png). One carriage fitted to the fronts at once (check_w2t '
                               'ear_poses.py p1-p3, by the outside excess or w02_ears\' objective) folds the ear toward the '
                               'cameras into a stub 23-34 mm short of the fur: the fronts\' ears are turned differently in '
                               'each photo, the left and right in opposite senses in every one (w12 +32 / -32, r03 +12 / '
                               '-49, w07 +10 / -12 deg of swivel)'),
    'ear.poses.relaxed': ('[P]', 'W2w: the mean of the profiles\' near ears\' carriages about the W2w bind (w01 L, w03 R; '
                                 'w02 _w2we1): the opening swivelled 77 deg OUT (it faces 93 deg out of forward, 3 down), '
                                 'splayed 18 in (the joint axis 3 deg in of vertical), tipped 5 back (the axis 21.5 back); '
                                 'w01 L p95 -0.2, w03 R -1.3 mm. Two ears, the splay along the side camera\'s line of '
                                 'sight: a weak read (the bind\'s splay sits 4 deg from the middle of alert and relaxed, '
                                 'toward the alert fronts, which see the splay). '
                                 'W2u: the mean of the profiles\' near ears\' carriages about the W2u bind (w01 L, w03 R, '
                                 'fit u3 with the facing held): the opening swivelled 37 deg OUT (it faces 79 deg out of '
                                 'forward, 9 down), splayed 25 in (more upright), tipped 7 back; w01 L p95 -1.4, w03 R -1.7 '
                                 'mm (the gaps 12.4 / 18.3: both side photos\' ears stand larger than r03\'s leather). Two '
                                 'ears: a weak read, the splay along the side camera\'s line of sight. '
                                 'W2t: the mean of the profiles\' near ears\' solved carriages (w01 L, w03 R; w01\'s far ear '
                                 'mostly hidden): the opening swivelled 21.5 deg OUT, splayed 23 IN (more upright), tipped '
                                 '7.5 back; w01 L p95 -1.1, w03 R -0.9 mm, filling to 9.0 / 14.8 (the bind +2.5 / +2.1). '
                                 'Two ears: a weak read'),
    'ear.base': ('[P] [E]', 'W3: 76 mm, the side views\' base front to back over its hair (WOLF_BODY_PHOTOS §3.2); the '
                            'pinna\'s base arc on the chord HEAD ear.span with its cup; W2 72, §2.5 about 65'),
    'ear.rim_half': ('[E]', '§4.2: membrane half-thickness 1.5 mm at the rim (2-4 mm thick, §2.5); W2 2.0 (4 mm, the '
                            'upper end): the gradient gate\'s 5 mm band straddles a thinner shell\'s mid-surface, where '
                            'any distance field of a sheet has a ridge'),
    'ear.base_half': ('[E]', '§4.2: half-thickness 5 mm at the base (8-12 mm thick, §2.5); W2 6.0 (12 mm, the upper '
                             'end), as the rim'),
    'ear.station': ('[P] [E]', 'W2c: the ear root (the rig\'s ear_0, the middle of the pinna\'s base) at 0.891 H from '
                               'the nose (along p, d 244 mm): the base now runs front to back along the head (canid '
                               'HEAD ear base, d 212 -> 275 on the skin), as the side views measure it (the base front '
                               'to back 76 mm over the hair, d 207-213 -> 281-288 in the palate frame matched on the '
                               'nose and the visible eye; its front 1.56-1.69 NE: WOLF_BODY_PHOTOS §3.2, w01 and w03). '
                               'W3 0.821 H under a chord that ran across the head (the side view saw a 38 mm spike); '
                               'W2 0.88 H; §2.5 about 0.73 H'),
    'eye.station': ('[P] [E]', 'W2: the EYEBALL\'s centre at 0.53 H from the nose (along p), so its VISIBLE centre '
                               '(the lid opening on the cornea, ball_r along the optical axis: ~11 mm ahead of the '
                               'ball\'s centre at 20 deg splay) sits at the photos\' NE 0.206 WH = 135 mm = 0.48 H '
                               '(WOLF_BODY_PHOTOS §3.1-3.2, w01 and w03: nose to the middle of the lid opening). §2.5 '
                               'had "eye centre about 137 mm (0.49 H)" for the ball, which put the visible eye at '
                               '0.44 H, 11 mm too far forward. NOW OFFSET by canid.EYE_SEAT (p, q, x): the eyeball\'s '
                               'centre sits 6 mm forward of this station (W2m 2, W2n 6: d 145.2 -> 139.2 in the '
                               'palate frame), 3 mm over canid.EYE_Q and 1.5 mm out; this tag is W2\'s seat, which the '
                               'offset is measured from. Since W2n the visible eye the photos are matched on is the '
                               'middle of the clay\'s lid opening (canid_hull.eye_landmark; from the side '
                               'canid_hull.eye_opening_side: d 135.1 = 0.483 of the 280 mm head, W2o: the cage\'s '
                               'corners ON THE FACE at the profile-rule canthi, d 124.5 -> 145.8 (canid_cage EYE '
                               'face; W2n 134.4 = 0.480 with the corners on the cameras\' limb planes); with the skin '
                               'hiding as well, W2o\'s lateral corner lay behind the skin over the zygomatic arch, d '
                               '124.5 -> 142.8, 0.477; W2p (canid_skull: MWNH 358\'s arch over the orbit, 4.3 mm lower '
                               'there; the corner on the face) d 124.3 -> 145.6 seen from the side, 0.482; the '
                               'profiles\' canthi 123.9 -> 145.0, 0.480), not the cornea\'s apex. W2q: the clay\'s '
                               'lids REST at a neutral gaze (W2q-W2r level and forward along the palate; W2s along the '
                               'canid\'s visual axis, eye.splay; canid_hull\'s W2q / W2s notes: the lids follow the gaze '
                               'about the canthus axis by fitted ratios and along the fissure by a warp, each photo '
                               'compared at its own iris gaze), and from the side at rest the opening runs canthus to '
                               'canthus, d 124.5 -> 145.8 (both corners seen), its middle 135.1 = 0.483 H; the '
                               'profiles\' own readings are taken at their own gazes (w02 the eyes at their own gaze)'),
    'eye.half_spacing': ('[P] [E]', 'W2: the eyeballs\' centres 72 mm apart, so the visible eyes (the lid openings, '
                                    '4 mm lateral of the balls\' centres at 20 deg splay) stand 80 mm apart, the IO '
                                    'the front-view photos are scaled by (WOLF_BODY_PHOTOS §4.1); EntB 47 [P] plus '
                                    'the 24 mm balls against the orbits\' medial walls. §2.5 had 80 for the balls. '
                                    'NOW OFFSET by canid.EYE_SEAT x: each centre 1.5 mm out (W2m), 75 mm apart; this '
                                    'tag is W2\'s spacing, which the offset is measured from. Since W2n the IO the '
                                    'front photos are scaled by is the clay\'s lid openings\' middles (canid_hull'
                                    '.eye_landmark), 78.8 mm apart (the cornea\'s apices 83)'),
    'eye.fissure': ('[P] [E]', 'W2e: 24 mm canthus to canthus, the lead\'s 22-25 from the level front w08 (21.8 / 25.4 '
                               'mm at IO 80, lm_w08): canid_hull STROKES eye half-length 12 (W2d 14: 27 mm in w08\'s '
                               'camera); §2.5: palpebral fissure 26-30 mm, almond'),
    'eye.ball_r': ('[E]', '§2.5: eyeball about 24 mm across (no wolf ocular biometry found)'),
    'eye.cant': ('[P] [E]', 'W2e: 17 deg, the lateral canthus over the interocular line in the near-level front w08 '
                            '(16.8 / 17.2, WOLF_BODY_PHOTOS §4.1; the lead\'s 15-19): canid_hull STROKES eye cant_q '
                            '3.2 mm (W2d 9-14 deg in w08\'s camera); §2.5: inner corner lower, canted about 10 deg '
                            '(SPECIMEN reference-photo description [H])'),
    'eye.splay': ('[C]', 'W2s: each eye\'s visual axis 20 deg lateral of the midline, level (the review read in full, '
                         'its OCR text layer): Miller PE, Murphy CJ '
                         '(1995) "Vision in dogs", JAVMA 207(12):1623-1634, p. 1625: "In dogs, the eyes typically are '
                         'placed so as to deviate approximately 20 deg lateral to the midline, whereas in people, the '
                         'eyes do not deviate but look straight ahead" (their ref.: Duke-Elder, System of Ophthalmology '
                         'vol. 1, The eye in evolution, 1958); the same page: each eye sees from 120 deg ipsilateral to '
                         '15-30 deg contralateral, the binocular overlap 30-60 deg (behaviour). The clay\'s REST GAZE '
                         '(canid_hull GAZE rest: the iris painted and the lids at rest there); not the orbit\'s axis '
                         '(Miller\'s Anatomy of the Dog: the orbital axes ~60 deg apart in mesocephalic dogs). '
                         '§2.5 had it as [E]: optical axes about 20 deg off the midline each side (dogs: 240-250 deg '
                         'field, 30-60 deg binocular)'),
    'paw.fore': ('[S] [P] [E]', '§2.5: front track 8.9-12.4 cm (NPS) or 9.7-11.7 cm without claws (ODFW) [S]; W1 '
                                '115 long; W2 85 wide: the standing paw, not the track spread under load (w08: the '
                                'forepaws 1.0 IO apart nearly touch; WOLF_BODY_PHOTOS §4.1)'),
    'paw.hind': ('[S] [E]', '§2.5: hind track 8.6-11.6 cm or 8.6-10.7 cm [S]; W1 105 long; W2 78 wide (the fore '
                            'paw\'s standing width ratio)'),
    'paw.claw': ('[S] [E]', '§2.5: front claws longer than hind [S]; W1 22 and 18 mm exposed [E]'),
    'paw.digit_len': ('[E] [P]', 'W2d: digit III, MCP or MTP joint to claw tip: fore 88, hind 79 mm, so the standing '
                                 'paw with its claws spans the SPEC\'s 115 / 105 (paw.fore, paw.hind) from the '
                                 'metapodial pad\'s back: w01\'s forepaw from the pastern\'s caudal line to its claw tips '
                                 '290 px = 116 mm (0.176 WH; research/wolf_work/data/lm_w01.json, 0.3996 mm / px) [P]; '
                                 'the hind foot check 45 + 134 + 79 = 258 mm [0.24-0.27, the Slovak mean 257]. W1 82 / '
                                 '75 (§2.1 "digits and claw (about 75)", fore x 115 / 105) left the paw 103 mm long'),
    'paw.p1_share': ('[E]', 'W1 estimate: the proximal phalanx 0.37 of the digit (about 30 of 82 mm)'),
    'paw.side_digit': ('[P] [E]', 'W2d, THE PAWS FROM THE BONES: digits II and V (fore, hind) as long as their '
                                  'metapodials\' share of III\'s: MC II 7.71 / MC III 8.81 / MC V 7.385 cm, MT II 8.335 / '
                                  'MT III 9.405 / MT V 8.81 cm (Aenocyon, Nigra & Lance 1947 Table 1, n 1088-1298 each: '
                                  'research/wolf_web/nigra_lance_1947_direwolf_metapodials.txt [P]), the phalanges taken '
                                  'in the same share [E]; W1 0.87 for both'),
    'paw.spread': ('[E]', 'W2d: the MCP / MTP heads of III-IV and II-V at 0.13 and 0.31 paw widths from the paw axis '
                          '(0.33 until the arched toes: their DIP, now level with the PIP, brought the two forepaws\' '
                          'digits II within 2.1 mm, x 1 y 27 mm; AG 05.13 asks 3): '
                          'the toes 22-23 mm wide (w08\'s central toes 34-38 px at 0.61 mm / px, the paws ~10 % farther '
                          'than the eyes) packed so neighbours touch with shallow grooves (the lead: "tight lobes"); W3 '
                          '0.115 / 0.29 under 29 mm toes (the bun)'),
    'paw.splay': ('[E]', 'W1 estimate: digits III-IV and II-V point 4 and 14 deg outward; W2 2 and 6: the standing '
                         'paw is compact, its toes touching (the track\'s splay is under load), and with the paws '
                         '1.0-1.25 IO apart (w08, w07) 14 deg brought the two forepaws\' medial toes within 1.4 mm '
                         '(AG 05.13). W2d check: III-IV 0 (parallel): w08\'s front shows the central toes touching '
                         'along their whole length (a groove of 1-2 mm between them); at 2 deg the toes, tapering to '
                         '18 mm across at the crest, stood 26-28 mm apart there: a 5-10 mm slot down the paw\'s middle '
                         'from the front (check_w2d/out/paw_cmp_base.png, pt_front_pair.png)'),
    'paw.setback': ('[D] [P]', 'W2d: the heads of II and V (fore, hind) behind III\'s by their metapodials\' shortfall '
                               '(paw.side_digit\'s Table 1) times the cosine of the metapodial\'s angle (75 deg fore, '
                               '83 deg hind): 3.0 / 3.9 and 1.5 / 0.8 mm; with the shorter digits their claw tips land '
                               '~20 / ~28 mm behind III\'s (w01\'s near toe V: its claw tip 112 px = 45 mm behind the '
                               'farthest, the paw turned a little to the camera); W1 12 mm'),
    'paw.side_raise': ('[D] [P]', 'W2d: the heads of II and V raised by the same shortfall times the sine of the '
                                  'metapodial\'s angle: 11.4 / 14.7 mm fore, 12.3 / 6.8 hind (the metapodials meet the '
                                  'carpus and tarsus at about one level); W1 3 mm'),
    'paw.pip_h': ('[E] [P]', 'W2d: the PIP joints 29 mm over the ground, level with the MCP / MTP heads (28 / 26): the '
                             'KNUCKLES HIGH (the lead: "the toes ARCHED with the knuckles high, w01 side"), the dorsum '
                             'over them 40 mm (WOLF_BODY_PHOTOS\' w01 reading 47-49 over ~5 mm of coat; the platform\'s '
                             'white edge hides w01\'s paw dorsum in the W2d crop), the toes dropping steeply from the DIP '
                             'to the claw (SPEC skin.paw dip, crest); W2 22 mm'),
    'paw.pip_h_side': ('[E] [P]', 'W2e: the PIPs of digits II and V 25.5 mm over the ground (pip_h x side_scale: their '
                                  'phalanges smaller), so the paw is domed from the front as w08\'s (the outer toes\' tops '
                                  'lower than III / IV\'s); W2d had every PIP at 29'),
    'paw.tip_h': ('[E] [P]', 'W2e: the claw tips 1.5 mm over the ground, touching it (the lead: "dark HOOKED claws '
                             'curving down to touch the ground ahead of the toes (w01, w08)"); W1 3 mm (wolf claws register '
                             'in tracks, §2.5 [S])'),
    'paw.dewclaw.h': ('[E]', 'W1 estimate: the dewclaw\'s joint (MC I head) 55 mm up the metacarpus, medial'),
    'paw.dewclaw.tip_h': ('[S] [E]', '§2.5: digit I, forelimb only, medial, about 25 mm above the ground, not '
                                     'registering [S]'),
    'paw.dewclaw.medial': ('[E]', 'W1 estimate: 25 mm medial of the paw axis'),
    'paw.dewclaw.reach': ('[E]', 'W1 estimate: the claw tip 14 mm ahead of its joint'),
    'paw.calcaneus': ('[E]', 'W1 addition, §2.1 hind-foot check: calcaneus "about 45" (the tuber\'s share of the '
                             'calcaneal-tuber-to-claw-tip length)'),
    'coat.cell': ('[D]', '§4.3: the coat grid\'s 6 mm cells (about 5.0 M floats, 20 MB)'),
    'coat.g_t': ('[D]', '§4.3: the Lipschitz target; 0.30 gives the exact bound g 0.52 on the toy (wolf_checks.py '
                        '§4)'),
    'coat.scale': ('[H]', '§4.3: coat scale s = 1 is the full coat, 0 the hairless remix on the same cage'),
    'coat.hat_scale': ('[E]', '§5.5: fit.seat runs on the envelope at coat scale 0.3'),
    'coat.ear_outer': ('[E]', '§4.2: the ear shell\'s outer coat t_o 4 mm (3-5 mm)'),
    'spine.pelvis': ('[E]', 'W1 addition, §6.1: pelvis (0, 0.60, 0)'),
    'spine.ls': ('[E]', '§6.1: the spine from about 0.61 m at L7 [E]; its z, the lumbosacral joint 50 mm ahead of '
                        'the hip joints, a W1 estimate [E]'),
    'spine.ct_y': ('[E]', 'W1 addition, §6.1: the spine to about 0.58 m at T1'),
    'spine.ct_behind_shoulder': ('[E] [D]', 'W2h: 54.895 mm, solved with the W2h stance (scratch_w2h/stance.py) so C7/T1 '
                                            'stays where it stood. '
                                            'W2g: 58.37 mm, solved with the W2g stance (scratch_w2g/forelimb.py) so C7/T1 '
                                            'stays at 592.74 mm. '
                                            'W2f: 54.5 mm, solved with the W2f stance (scratch_w2f/stance_solve.py) so '
                                            'C7/T1 stays at its W2d z; W2e: 46.2 mm, solved with the stance so C7/T1 stays at its W2d z (the '
                                            'spine and the neck with the trunk) while the shoulder joint moves 16 mm '
                                            'forward; W1 estimate: the C7/T1 junction 30 mm behind the shoulder joint '
                                            '(the T6/T7 joint then lands within 10 mm of §4.2\'s T6 station)'),
    'spine.lumbar_unit': ('[E]', 'W1 estimate: a lumbar body 1.4 thoracic bodies long (formula C7 T13 L7, §2.1)'),
    'spine.cervical': ('[E]', 'W1 estimate: C7, C6, C5, C4, C3, C2, C1 body lengths in units (C2 the longest)'),
    'spine.tail_root': ('[E] [H] [P]', 'the first caudal joint just behind the sacrum over the hip joints, at or above '
                                       'hip height (AG 05.5 [H]). W2: 17 mm lower and 4 mm forward than W1\'s (0.595, '
                                       '-0.020): its tail stood as a bump above the croup\'s rounded end (a crease at '
                                       'the root, w02 i11), where the side views put the tail root\'s dorsal skin 0.09 '
                                       'WH below the croup top, level with the hip joint (0.873 WH; WOLF_BODY_PHOTOS '
                                       '§3.1)'),
    'spine.breath_y': ('[E] [R]', 'W1 estimate: the breathers mid-thorax and mid-abdomen (the study-T canine pattern '
                                  '[R], §6.1)'),
    'helpers.olecranon': ('[E]', 'W1 estimate: the elbow point 28 mm up the ulna and 18 mm caudal (AG 06.21 helper)'),
    'helpers.triceps': ('[E]', 'W1 estimate: the triceps long head 40 mm caudal of the humerus\'s midpoint'),
    'helpers.patella': ('[E]', 'W1 estimate: the patella 25 mm cranial of the stifle\'s centre'),
    'helpers.tuber_plantar': ('[E]', 'W1 estimate: the calcaneal tuber 25 mm plantar of the metatarsal axis'),
    'helpers.gluteal': ('[E]', 'W1 estimate: the middle gluteal 40 mm up, 20 mm lateral and 10 mm forward of the hip '
                               'joint'),
    'rig.n_tail': ('[H]', '§6.1: tail_0..7, about 0.05 m apart on the 0.40 m tail'),
    'rig.twist_upper': ('[H]', 'AG 06.17: upper-arm and thigh twist joints near the root (a third along)'),
    'rig.twist_lower': ('[H]', 'AG 06.17: forearm and gaskin twist joints two thirds along'),
    'family': ('[H]', '§4.1, DESIGN.md: the family generator forge/families/limbed.py'),
    'head_archetype': ('[H]', '§4.1: the head archetype forge/heads/canid.py'),
    # ---- W2, the hairless clay (WOLF_PLAN §4.2, §10 step 2; fitted in work/bestiary/tests/w02_clay.py)
    'skin.trunk': ('[E] [P]', 'W2l (the lead\'s W2l brief: "the chest\'s depth and keel ... fix what you can prove from '
                              'the photos and the skeleton"): T4 / T6 / T10 / T13 width / depth 0.705 / 0.71 / 0.72 / '
                              '0.75 (W2-W2k 0.785 / 0.785 / 0.80 / 0.81) and the keel a3 0.050 / 0.060 / 0.050 / 0.03 '
                              '(W2-W2k 0.015 / 0.015 / 0.015 / 0.01): §4.2\'s own sections (its T1 0.70 / 0.04, T6 0.71 / '
                              '0.06, T10 0.72 / 0.05, T13 0.75 / 0.03; T4 between T1 and T6), each centre y raised by '
                              'r0 x the keel\'s change (5.1 / 6.6 / 4.7 / 2.5 mm: the a3 term takes a3 r0 off the top and '
                              'adds it under the floor) so the back line and the chest floor stay where the side views put '
                              'them (floor 364, top 647 mm at T5, unchanged). Why: (1) THE GIRTH: the W2k clay\'s trunk '
                              'at the largest circumference behind the foreleg (T5-T6) measured 825-828 mm AT THE SKIN '
                              '(230 wide x 283 deep) on a clay whose volume is 39.6 L (41-42 kg at 1.03-1.06 kg/L, W1 40 '
                              'kg); Hart & Jamieson 2002 (Canadian Field-Naturalist 116: 313-314; 114 Minnesota wolves, '
                              'kg = 0.8916 girth cm - 30.59, a snug tape behind the foreleg; research/wolf_web/'
                              'girth_hart_jamieson_2002) give 79.2 cm OVER the coat at 40 kg: the clay\'s skin girth stood '
                              '3.3 cm over even with no coat, ~6 cm (1.7 residual SDs) with 2-3 cm of compressed coat. The '
                              'depth is the side photos\' (above), so the excess was the width. Now 801 mm at T5 (scratch_'
                              'w2lb probe k1), the regression\'s value. (2) w08 (front, winter): the elbows 170 mm and the '
                              'shoulders 232 mm OVER the coat where the clay stood 165 / 230 mm at the skin. (3) THE KEEL: '
                              'the chest from the front read as a broad flat shield with a U-shaped brisket (W2k '
                              'closeups, "the chest from the front"), where WOLF_BODY_PHOTOS §6.1 asks for elbows tucked '
                              'against a narrow keel-shaped chest; the widths at 10 / 25 / 50 / 75 % of T5\'s depth went '
                              '131 / 191 / 229 / 212 -> 111 / 160 / 202 / 203 mm: the lower chest narrows most. The W2 '
                              'limits below (width / depth >= 0.77, a3 <= 0.02 for the old sweep\'s gradient gate) '
                              'predate the body volume (W2d-W2e): the trunk now reaches the review mesh through the flowed, '
                              're-distanced body volume, not as the sweep\'s own field. '
                              'W2: §4.2\'s stations re-fitted by eye to the side views\' skin lines set on the withers '
                              '(w01 summer first, w02, w03, w05; WOLF_BODY_PHOTOS §3.1): chest depth 0.43 WH at T6 '
                              '(§4.2 0.48; photos 0.405-0.498, median 0.45), its floor at 0.56 WH (§4.2 0.52), the '
                              'belly rising to 0.69 WH at the groin (w01), the back near level (croup 0.95 WH). '
                              'Width / depth >= 0.77 (§4.2 0.70-0.87) and the keel a3 <= 0.02 (§4.2 0.04-0.06): '
                              'flatter sections broke the gradient gate (|grad| up to 1.17); T6 is 228 mm wide (§4.2 '
                              '224), the limbs\' shoulder masses carry the upper chest\'s breadth. W2 r14: the neck '
                              'widens into the shoulders (C4-C7 width / depth 0.86-0.95, T1 0.77), so the top view '
                              'has no square corners at the neck base; C0 sits 12 mm further into the head and the '
                              'start eases over 80 mm to 0.5 (the neck\'s start ease on the bend\'s concave side put '
                              '|grad| over 1.05 behind the ears); the point of buttock 8 mm forward (w01\'s thigh '
                              'and ischium stood 16-24 mm in front of i11\'s). W3 (the lead: "the neck at the skin '
                              'thicker and muscled"): the neck\'s side depth stays on w01\'s summer skin lines (its '
                              'dorsal and throat lines within 6-9 mm), its width / depth 0.92-1.00 at C0-C6 (W2 '
                              '0.84-0.95): a canid\'s muscled neck is about as wide as deep (the mange coyote r05\'s '
                              'neck 0.68-0.79 of its chest depth in side view, the brachiocephalicus and the throat '
                              'filling it); the muscles themselves are SPEC skin.neck_muscles. W3: the chest floor 9-10 '
                              'mm lower at T4-T6 (the back kept: y down and r0 up by the same 4.5-5 mm, width / depth '
                              '0.785), so the elbow\'s point hangs under it as the side views have it (w3b: the clay\'s '
                              'floor at 0.564 WH against the photos\' 0.550, the elbow point at 0.510 against 0.512, '
                              'the gap 0.055 WH against 0.014-0.050). W2c (the W2b checker: "the neck a tube as wide '
                              'as the head", 147-152 mm behind the head, 155 at C4): the neck narrows from the head, '
                              'width / depth C0 0.80, C2 0.82, C4 0.86, C6 0.94 (the plan\'s C1 112 / C4 125 mm: no '
                              'wet or mange reference shows the neck clear in a front or top view; >= 0.78 for the '
                              'distance bound). W2e (the lead\'s call 5: "the neck ... 13 mm shallow at C4 (143 vs 156): '
                              'measure the neck\'s length and depth on every side photo where it is clear; if they agree '
                              'with w01, change ..."): only w01 and w03 show the neck clear (w02 / w04 / w05 turn the head '
                              'or bury it in the mane); their withers-to-occiput lengths DISAGREE (w01 0.389 WH head up, '
                              'w03 0.581 head out: posture), so the cervical lengths stay; their depths agree, deeper than '
                              'the clay\'s for the chest (w01 150-153 mm across the withers-occiput line at 30-60 %, 0.56-'
                              '0.59 of its chest depth; w03 0.70-0.80 in winter; the mange coyote r05 0.68 / 0.79; the '
                              'clay 0.50-0.52): C4 to w01\'s 156 deep (r0 72 -> 78 mm, the width kept by the aspect, 0.794), '
                              'C2 r0 76 (0.788). W2e (call 6, "compose the chest INSIDE the w01 line instead of carving a '
                              'flat facet"): the body volume\'s hull is the composition CUT AT the side lines themselves '
                              '(wolf_body.hull_limits; the flow may then stand out to the line plus its tolerance), so a '
                              'composition past the line is cut flat. The trunk sweep stood 6-18 mm past w01\'s throat-'
                              'chest skin line at y 470-590 (the facet through the keel); a first pass (C6 / C7 / T1 3 / '
                              '7.5 / 2 mm dorsally, r0 75 / 92.5 / 122, C7\'s keel a3 -0.005) left 8 mm at the keel, and '
                              'the limb\'s shoulder section and the brachiocephalicus\' end, come forward with the stance, '
                              'stood 8-17 mm past at x 65-72 (the hull cut them into two discs: rings on the chest\'s front '
                              'at 0.5 mm, scratch_w2eb/out/proof_fields_w2eb2.png). Now C6 r0 72 (y +3 mm), C7 r0 88.5 '
                              '(y +2), T1 r0 116 (y +3, z -5, keel a3 0.010), with skin.fore.path\'s shoulder section 12 '
                              'mm caudal and skin.neck_muscles\' brachiocephalicus end 22 mm back: the composition\'s side '
                              'silhouette -9..+1.6 mm of the line over y 470-590 in both poses (scratch_w2eb/'
                              'chest_probe.py), the shoulder\'s bony point 7.8 mm inside it'),
    'skin.trunk_not_masses': ('[H] [P]', 'W2e (the lead\'s call 6: "blend away the croup\'s horseshoe rim (... the croup '
                                         'mass\'s yield edge ...) and the withers\' oval"): the withers\' and the croup\'s '
                                         'masses shape the composed start only, not the volume\'s inner limits (their inset '
                                         'outlines held the flowed skin as rims: the oval from the top, the horseshoe round '
                                         'the tail\'s root where the croup mass yielded to the back lines)'),
    'skin.neck_muscles': ('[E] [P]', 'W3: the brachiocephalicus (from the mastoid region under the ear along the lower '
                                     'side of the neck to the point of the shoulder) as a round cone in the trunk '
                                     'group: the mange coyote r05 shows it as the neck\'s lower half joining the '
                                     'head\'s throat broadly and the shoulder\'s point (research/wolf_work/data/src/'
                                     'ref_r05.json); W2\'s neck joined both as a narrower tube. W2c: slimmer and nearer '
                                     'the midline (16 -> 26 mm, from 18 mm off it under the ear, k 20 mm): at 26-34 mm '
                                     '34 mm out it stood the neck 155 mm wide at C4. W2e (call 6): its shoulder end 22 '
                                     'mm back (34 -> 12 mm ahead of the joint) and r 26 -> 24 mm: with the stance\'s '
                                     'limb it stood 10-17 mm past w01\'s throat-chest skin line at x 65-72 and the hull '
                                     'cut it flat there (a ring on each side of the chest\'s front; skin.trunk\'s W2e '
                                     'note)'),
    'skin.trunk_round': ('[H] [D]', '§4.2 rounds the ends over 60 mm (C1) and 100 mm (ischia); W2 eases them '
                                    '(limbed.end_taper: start ease, end ease, start and end fractions) into the '
                                    'kernel\'s hemisphere cap instead of the octopus factor, whose radius-0 end node '
                                    'made the field read up to 20x short past it (culling seams, gradient gate). W2 '
                                    'review: the point of buttock eases to 0.55 over 90 mm (r17 0.5 over 75 mm: the '
                                    'smoothstep\'s start bent the top line at ~60 /m, a 21 deg turn within 10 mm at z '
                                    '0.05, printed as a band across the rump in the top and 3/4 views; now 12 deg)'),
    'skin.trunk_nodes': ('[H]', '§4.2: about 320 nodes, clustered toward both ends and where the radius changes fast'),
    'skin.trunk_smooth': ('[H] [D]', 'W2: the axis Gaussian-smoothed over 60 mm of arclength: PCHIP\'s curvature spike '
                                     'at T1 (curvature x dorsal radius 2.5) folded the sweep across the withers, and '
                                     'at 45 mm the bend (0.72) still amplified the radius change into |grad| > 1.05; '
                                     'the octopus t24 lesson (a turn spread over the whole bend)'),
    'skin.fore.smooth': ('[H] [D]', 'W2: the limb axis smoothed over 20 mm (the shoulder\'s turn had curvature x '
                                    'radius 1.7)'),
    'skin.hind.smooth': ('[H] [D]', 'W2: the limb axis smoothed over 35 mm (the hip\'s turn had curvature x radius '
                                    '3.3; the stifle\'s concave side amplified the radius change, |grad| > 1.05)'),
    'skin.trunk_dense': ('[H]', '§4.2: node clusters at the withers, the last rib and the pelvis (s, width, gain)'),
    'skin.trunk_round_sections': ('[H] [D]', 'W2: the end sections ease to circles over the first 40 and last 30 mm: '
                                             'a non-round end section pinches the kernel\'s hemisphere cap into a star '
                                             '(r05\'s poll and thighs, traced close-ups)'),
    'skin.croup': ('[E] [P]', 'W2: the croup, the gluteal mass over the pelvis spanning the hips (~170 mm across, its '
                              'top 0.95 WH): the trunk sweep rounds to the point of buttock over the hip joints, so '
                              'i01-r05\'s thighs stood as two pillars with lumps on the croup and a dip between them '
                              '(the top and rear views); the side views put the croup skin at 0.96 WH, the hip 0.86, '
                              'the ischium 0.82 (WOLF_BODY_PHOTOS §3.1). W2 review: 196 mm across (was 168), 2 mm '
                              'higher and 16 mm longer: 80 mm off the midline the top line had a 4 mm groove at z 0.04 '
                              'between the trunk\'s eased end and the gluteals (a +29 / -35 deg turn pair, the crisp '
                              'band across the rump under a grazing light); the wider mass spans that junction'),
    'skin.withers': ('[E] [D]', '§4.2: the withers\' interscapular mass, a dorsal ellipsoid in the trunk group (k 10 '
                                'mm). W2 sizes it to sit 1-7 mm proud of the sweep over the neck-chest bend\'s dorsal '
                                'side: on a bend\'s concave side the foot point moves 1 / (1 - curvature x radius) '
                                'faster than the point and amplifies the radius change, |grad| 1.08-1.20 there '
                                '(w02 i05); an ellipsoid\'s field is ~1 (scratch probe p08_withers.py). W2c (the W2b '
                                'checker: ring bands across the withers under a grazing light, its edges at k 10 mm): '
                                'k 28 mm, 270 mm long, 2-3 mm narrower, so its ends run out into the sweep'),
    'skin.pectorals': ('[E] [P]', 'W2f (the lead\'s call 6: "the chest\'s two pectoral blobs ... smoothed"): 22 mm either '
                                  'side of the keel (W2d 30), 60 x 84 x 48 mm, k 32 (W2d 20), their front 4 mm back: the two '
                                  'masses merge across the keel into one breast instead of standing as two blobs. W2d (the lead\'s call 4: "the manubrium inside the chest\'s keel, a smooth front '
                                  'profile from the throat to the sternum\'s point, the pectoral masses either side, '
                                  'measured on the side references"): no manubrium knob (W2-W2c\'s ellipsoid read as a '
                                  'ball on the chest); the superficial pectorals 30 mm either side of the keel, 56 x 80 x '
                                  '52 mm, their front at z 654 mm, y 418-498: w01\'s prosternum (2770, 1470 px) lands at '
                                  'z 673, y 449 and its point of the shoulder (2820, 1325) at z 692, y 507 on the clay\'s '
                                  'frame (WH-scaled, withers matched), and its throat-chest skin line carves the front as '
                                  'an outer limit (species/wolf_body_refs.py) [P]; the masses\' size [E]'),
    'skin.fore.path': ('[E] [P]', 'W2l (the whole-animal look, with skin.trunk\'s W2l thorax): the shoulder row\'s width / '
                                  'depth 0.80 -> 0.62, so 30 mm of tissue lateral of the joint centre (was 38: the humeral '
                                  'head and greater tubercle ~20 mm, the deltoid\'s tendon and the skin ~10 [E]); the '
                                  'clay from the top 207-208 mm across the shoulders (was 216) against 213 at the ribs, '
                                  'the ribs again the widest as a canid\'s thorax is behind its shoulders (the thorax '
                                  'alone narrowed, the shoulders stood 3 mm wider than the ribs: scratch_w2lb probes s1 / '
                                  'k2, top_widths.py). w08 (front, winter): the shoulders 232 mm over the coat at IO 80 '
                                  '(244-250 with the shoulders ~5-8 % farther than the eyes), less 25-35 mm of winter '
                                  'coat a side (WOLF_BODY_PHOTOS §3.5 between the back\'s 38 and the chest floor\'s 22): '
                                  '174-200 at the skin; the clay now 208 at its widest there (213 at the ribs behind). '
                                  'W2l (the lead\'s W2l brief: "the forearm\'s front (it stands 8.2-12.4 mm ahead of '
                                  'w01\'s near front now that its gates read the far-leg strip)"): W2h set these rows on '
                                  'w01\'s near front by W2e\'s far-lead table (2 / 12 / 20 mm at 148 / 248 / 308 mm up), '
                                  'which W2i\'s full-resolution strip (15 / 21 / 26.5) puts 13 / 8.5 / 6.5 mm too far '
                                  'forward. The rows at t 0.18 / 0.50 / 0.82 / 0.92: centres 3.5 / 5.0 / 5.0 / 5.0 mm more '
                                  'caudal (18.9 / 9.5 / 5.6 / 6.6 mm cranial), half-depths 3.5 / 5.0 / 5.0 / 5.0 mm less '
                                  '(34.3 / 23.2 / 19.0 / 17.4), so each front stands 7-10 mm back and each back where it '
                                  'was (on w01\'s near caudal edge less its coat, within 3 mm: their caudal edges agree, the '
                                  'strip is all at the front); the aspects 0.75 / 0.78 / 0.88 / 0.93 (W2h 0.71 / 0.70 / '
                                  '0.79 / 0.84) so the widths hold (49.6 / 40.3 mm at 25 / 60 %, the girth gate 47-58 / '
                                  '32-42). With skin.fore.spindles (the extensors 10 mm back), measured on the volume '
                                  '(work/bestiary/wolf/scratch_w2lb/body_probe.py, the bind\'s stage A and 1 mm forelimb, '
                                  'w02\'s own measures; run fin): the front -0.2..+2.7 mm of w01\'s near front by the strip '
                                  '(W2k +8.2..+12.4), the column +2.6 deg (W2k +3.0 on the whole outline, +3.6 on w02\'s '
                                  'on_fore outline; the photos to +3.2), the depth 66.4 / 56.5 at 25 / 60 % (targets 74 / '
                                  '53 +-10), the prow 75 (w01 73 +-15). '
                                  'W2h (the lead\'s call 4: the forearm\'s front on w01\'s by its cranial muscle mass): '
                                  'w01\'s NEAR forearm read in w02\'s stance frame (its traced edges less the 5 mm coat, '
                                  'the far leg\'s lead off the cranial trace; scratch_w2h/fore_trace.py) has its front '
                                  'vertical at +59-65 mm ahead of the withers and its caudal edge 10-17 mm behind the '
                                  'clay\'s bone line all the way down (+2.6 at y 158 to -11 at 308), 60-75 mm deep: the '
                                  'sections\' centres move cranial of the bone line (the elbow 8 mm, t 0.18 / 0.50 / 0.82 '
                                  '22.4 / 14.5 / 10.6 mm, a new row at t 0.92 11.6 mm), their half-depths 37.8 / 28.2 / '
                                  '24.0 / 22.4 so the caudal edge stands on w01\'s near caudal edge 1-5 mm deeper, and '
                                  'the t 0.92 row holds the lower forearm\'s back into the carpus (without it the carpus '
                                  'row\'s deeper back drew the last 20 mm back: the one taper rose 2 mm); widths / depths '
                                  '0.71-0.84 (53 / 40 mm wide at 25 / 60 %, the girth gate). On the composed forelimb '
                                  '(scratch_w2h/fore_probe.py, which reads W2g\'s front, column and depths as w02 did): '
                                  'the front within -0.3..+3.7 of w01\'s near front, depth 74 / 66 at 25 / 60 %, the one '
                                  'taper without a rise. '
                                  '§4.2 muscle profile re-fitted to the side views\' leg depths (forearm 70-80 mm deep '
                                  'at the skin, pastern ~50; WOLF_BODY_PHOTOS §3.3) and the front views (forearm ~42 '
                                  'mm wide); width / depth 0.80-0.92 (the distance bound), the depth from the spindles. '
                                  'W2 r13: the sweep starts 45 % down the scapula, 8 mm medial, round (its cap inside '
                                  'the chest wall: a start at 35 % stood two epaulette lumps at the neck base, the top '
                                  'view); the paw end round and wider than deep (the metacarpals side by side). W3: the '
                                  'metacarpus widens to the paw (width / depth 1.05 at the carpometacarpal joint, 1.35 '
                                  'at the MCP: 53 mm across the heads) so the pastern flares into the palm instead of '
                                  'standing as a stick on it. W2e: the forearm\'s top 8-10 mm forward of the radius (the '
                                  'rows at the elbow, 0.18 and 0.50 from 4 / 4 / 2 mm caudal to 4 / 6 / 2 mm cranial), '
                                  'with the olecranon 6 mm forward (wolf_body.BONES, the stroke, the olecranon mass): '
                                  'w01\'s forearm tapers evenly, its cranial edge leaning back 5.2 deg and its caudal '
                                  'forward 5.5 (WOLF_BODY_PHOTOS §3.3, scratch_w2eb/m_side.py), the W2d clay\'s -2.8 / '
                                  '+14.2 (its bulk behind at the top): the column\'s midline then reads as the photos\'. '
                                  'W2e (call 6): the shoulder\'s section 12 mm caudal of the joint: with the stance it '
                                  'stood 8-14 mm past w01\'s throat-chest skin line at x 65-72 and the hull cut it flat '
                                  '(skin.trunk\'s W2e note); the shoulder\'s bony point stays 7.8 mm inside'),
    'skin.fore.muscles': ('[E] [P]', 'W2l (the carpus\'s knob, the W2i checker: "the carpal pad is a distinct knob at '
                                     'the back of the carpus"): the accessory carpal mass 13 mm caudal of the bone line '
                                     '(was 17) and 7 mm deep (was 8), with wolf_body.BONES\' carpus ball 3 mm forward and '
                                     'wolf_strokes\' pad bump 2.5 mm over sigma 7.5 (was 4.0 over 5.5): the bulge behind the '
                                     'carpus 3-5 mm proud of the line from the forearm\'s back to the pastern\'s, r05\'s ~5 mm '
                                     '(W2k ~10 with notches above and below). '
                                     'W2i (the lead\'s call 5: "olecranon tucks up under the chest with its point at '
                                     'w01\'s elbow landmark"): the olecranon 10 mm up the bone from the elbow joint '
                                     '(along -0.010): w01\'s elbow landmark stands 363.6 mm up, 22 mm over the clay\'s '
                                     'joint (341.5); the point rises toward it as far as the forelegs\' stance band '
                                     'allows (the point 0.014-0.050 WH under the chest floor at 363: no higher than '
                                     '~354), the rest of the gap the clay\'s chest floor\'s own height against w01\'s. '
                                     '§4.2: triceps long head, deltoid, biceps, the forearm flexors and extensors, the '
                                     'olecranon and the accessory carpal bone (k 3-6 mm). W3: the olecranon is the '
                                     'elbow\'s point, the forelimb\'s most caudal turn, 43 mm behind the bone line and '
                                     'centred at the elbow joint\'s height (18 / 14 / 15 mm, k 6), so it shows under '
                                     'the chest floor as the side views have it (0.01-0.05 WH under the floor, median '
                                     '0.032: WOLF_BODY_PHOTOS §3.1, which also finds the plan\'s elbow joint 0.03-0.05 WH '
                                     'high for the photos\' 0.512 WH point); the forearm\'s flexors slope forward under '
                                     'it (W2-w3e had it 7 mm inside the flexor belly\'s top, which stood as the elbow\'s '
                                     'point). W2c: the CARPUS marked (the W2b checker: the pastern a straight column '
                                     'into the paw): a carpal knob on the joint\'s front (24 x 18 x 30 mm, k 8) over a '
                                     'forearm narrowed to 40 mm just above it. W2e: the olecranon 23 mm caudal of the '
                                     'bone line (W2d 29), with the forearm\'s top moved forward (skin.fore.path)'),
    'skin.fore.tendons': ('[E] [P]', 'W2l (the lead\'s "the elbow\'s knob"; the W2i checker: "the olecranon is still a '
                                     'pointed knob under the chest"): THE ULNAR FLEXOR, the flexor carpi ulnaris\' ulnar head '
                                     'and the deep digital flexor\'s, from the olecranon down the forearm\'s caudal face: a '
                                     'round cone from the elbow joint\'s level, 26 mm caudal of the bone line (r 11), to t '
                                     '0.20, 13 mm caudal (r 8), a mass (the volume\'s inner limit, inset 4 mm). The W2k '
                                     'clay\'s caudal outline ran 17 mm forward in the 18 mm under the elbow\'s point (the bony '
                                     'ball of wolf_body.BONES standing proud of a forearm cut in under it: a pendant knob from '
                                     'the side, a teardrop from behind); now one convex corner from the point (343 mm up, 33 '
                                     'behind the withers) to the forearm\'s straight back ~45 mm under it, as w01\'s near '
                                     'caudal line turns from its point (364 mm) to its straight back by ~320 (research/'
                                     'wolf_work/data/lm_w01.json, fore_near_caudal; the clay\'s point is 21 mm lower with '
                                     'its 25 mm deeper chest, the photos\' median). Ending at t 0.30 (scratch_w2lb run v4) it '
                                     'filled the forearm\'s upper back 5-8 mm behind w01\'s and leaned the column +3.2. '
                                     '§4.2: the digital flexors behind the metacarpus (round cones)'),
    'skin.fore.not_masses': ('[H]', 'W2d: the bony points among the muscles (the olecranon, the accessory carpal) are '
                                    'not the body volume\'s mass limits: they are its bones and strokes '
                                    '(species/wolf_body.BONES, wolf_strokes.py)'),
    'skin.hind.not_masses': ('[H]', 'W2d: the patella and the tuber calcanei are the volume\'s bones and strokes, not '
                                    'mass limits'),
    'skin.volume': ('[H]', 'W2d (the lead\'s call 1: "the body on the head\'s method"): the body sampled into grid '
                           'volumes (2 / 1 / 0.5 mm), carved by the side skin silhouettes, flowed between the outer and '
                           'inner limits, stroked (species/wolf_body.py, families/limbed.build_volume_sdf)'),
    'skin.fore.spindles': ('[E] [P]', 'W2l (skin.fore.path\'s W2l note): the extensors 25.0 mm cranial of the bone line '
                                      '(W2h 35.0), r 20.5 -> 16.5 kept: their inset front is the volume\'s inner limit on '
                                      'the lower forearm (the flowed front sat on it at 150-210 mm up, scratch_w2lb run '
                                      'base2), 8-10 mm ahead of w01\'s near front by W2i\'s strip; now +50.5..+51.2 mm ahead '
                                      'of the withers at 154-204 mm up against w01\'s +49.8..+51.1. '
                                      'W2h (the lead\'s call 4: "make the forearm\'s front by its CRANIAL MUSCLE MASS (the '
                                      'extensor group over the radius\'s distal half, read on w01 and the mange r05 side)"): '
                                      'the extensors, a tapered round cone from 0.40 to 0.975 of the radius, 35.0 mm '
                                      'cranial of the bone line, r 20.5 -> 16.5 mm (its front 55.5 -> 51.5 mm ahead of the '
                                      'bone line; the W2h first run read the volume\'s front 3-5 mm under w01\'s near front '
                                      'over its last 60 mm at 33.8 / 15.5), its round end over the carpus\'s front and clear '
                                      'of the pastern 10 mm under the joint (the pastern gate\'s window); the FLEXORS, a '
                                      'round cone over the radius\'s distal half (0.45 to 0.95), 4.2 mm caudal of the bone '
                                      'line, r 7.5 -> 10 mm (its back 11.7 -> 14.2 mm behind the line: the caudal outline '
                                      'full into the carpus as w01\'s near forearm\'s, +2.6 mm ahead of the withers at 158 '
                                      'mm up, and the accessory carpal\'s region behind). The body volume keeps the masses '
                                      '(its inner limits, inset) and flows the sweep away: the forearm\'s column there is '
                                      'the masses\' midline, which leaned with the bone line (+3 deg) and read +3.5 without '
                                      'a flexor and +4.1 with one from 0.30 at r 12 -> 7 (the photos to +2.1, +-1); the '
                                      'extensors narrowing 4 mm and the flexors widening 2.5 mm down the half tilt it back '
                                      '~1 deg. w01\'s near front less the coat stands 49-55 '
                                      'mm ahead of the clay\'s bone line from 0.4 down to the carpus (scratch_w2h/'
                                      'fore_trace.py), straight into the carpus as r05\'s planted forearm\'s front is. The '
                                      'bones the wolf bands allow stand the forearm ~10-15 mm behind w01\'s (rest.elbow): '
                                      'the mass is that much fuller than a wolf\'s extensors over the radius\'s distal '
                                      'half, where the photo, not the dissection, sets it. '
                                      'W2: the forearm extensors and flexors as tapered bellies (limbed._spindles: '
                                      'round cones, exact), deepening the forearm to w01\'s summer leg (70-80 mm at '
                                      'the skin). W3: the lateral and medial bellies widen the upper forearm in the '
                                      'front view and taper it to the carpus (the mange coyote r07: 0.64-0.71 / 0.49 / '
                                      '0.41 IO below the elbow, mid-forearm, at the carpus); the extensor and flexor '
                                      'bellies each in two cones: the extensors swell from the elbow (18 mm) to their '
                                      'widest a fifth of the way down (26 mm, the cranial outline ~47 mm ahead of the '
                                      'bone line), the flexors stay under the olecranon\'s line and slope forward (36 mm '
                                      'behind it at 0.15, 25 at 0.55), both running out flush into the sweep above the '
                                      'carpus: the upper forearm ~85 mm deep and ~60 wide, ~56 x 42 at mid-forearm (a '
                                      '28 mm extensor stood the forearm 63 mm wide, over the front view\'s 51-62; w3b: '
                                      '71 / 55 against '
                                      'w01\'s summer forearm 97 / 80 over the coat and the mange coyote r05\'s 0.31 / '
                                      '0.19 of its chest depth, 88 / 53 mm on the clay\'s chest; w3d\'s bellies set 4-5 '
                                      'mm further out ended 2-4 mm proud of the sweep, a cuff with a step at mid-forearm; '
                                      'w3e\'s single cones widest at the elbow capped the forearm\'s top like a plugged-in '
                                      'cylinder). W2c (the W2b checker: the bulge at the top of each forearm reads as a '
                                      'knee): the extensor belly starts above the elbow (t -0.06) so the upper arm flows '
                                      'into it, its widest 21 mm; the lateral and medial masses 13 / 12 mm, set 10 / 8 '
                                      'mm out (r1 23, 15 / 13, 11 / 9 read 58 mm, the band\'s edge): the upper forearm '
                                      'in the front view against r07\'s CORRECTED 0.59-0.66 IO (47-53 at IO 80; its '
                                      'traced eyes and nose were on the fur and the throat)'),
    'skin.fore.k': ('[H]', '§4.2: each limb group blends into the trunk with k 15-25 mm; W2c 28 (the W2b checker: a '
                           'crease across the chest at the shoulder points)'),
    'skin.hind.path': ('[E] [P]', '§4.2 muscle profile (thigh 60-70, gaskin 35-40, hock 14, metapodials 14-16 mm) '
                                  're-fitted to the side views (the gaskin ~85 mm deep, the cannon ~45); the sweep starts '
                                  'at the hip joint, small and round (a start above it turned with curvature x radius 3.3 '
                                  'and poked through the croup; r05\'s full 58 mm start stood the thighs as pillars), '
                                  'the mid-thigh 54 mm set 6 mm cranial (r17: w01\'s summer caudal thigh skin stood '
                                  '20 mm inside the clay, its cranial edge 8 mm outside; the plan\'s 60-70 is an '
                                  'estimate). W3: the metatarsus widens to the paw (1.00 at the tarsometatarsal joint, '
                                  '1.30 at the MTP)'),
    'skin.hind.muscles': ('[E]', '§4.2: quadriceps, biceps femoris, gluteals, gastrocnemius, the calcaneal tuber and '
                                 'the patella'),
    'skin.hind.tendons': ('[E]', '§4.2: the common calcaneal (Achilles) tendon to the tuber; the plantar tendons. W2 '
                                 'review: the deep digital flexor (tibia to tuber) and the plantar ligament (tuber down '
                                 'the cannon), so the point of the hock is the leg\'s own angle: the tuber had stood as a '
                                 'ball on the Achilles rod, 12 mm clear of the tibia (the side and rear views)'),
    'skin.hind.k': ('[H]', '§4.2: each limb group blends into the trunk with k 15-25 mm'),
    'skin.paw.digit_r': ('[E] [S]', 'W2d: the fore toe\'s radii at the head, the PIP, the DIP and the crest, 23 / 22 / '
                                    '17 / 13 mm across: four toes 22-23 mm wide packed tight across the standing paw\'s '
                                    '85 mm (SPEC paw.fore; w08\'s central toes 21-23 mm), II and V x side_scale. '
                                    '§4.2: the fore digits as round-cone chains (MCP head, PIP, claw bed radii). W3: '
                                    '28 / 26 / 18 mm across (W2 26 / 24 / 20; a bed nearly as wide as the PIP ended '
                                    'each toe as a ball), so four tight toes span the standing '
                                    'paw\'s 85 mm (SPEC paw.fore) as the photos\' forepaws do (w08: 1.0 IO apart, '
                                    'nearly touching; the tracks 73-124 mm wide spread under load, NPS: research/'
                                    'wolf_web/nps_tracks)'),
    'skin.paw.digit_r_hind': ('[E] [S]', '§4.2: the hind digits; W3 26 / 25 / 17 mm across (the hind track 67-98 mm '
                                         'wide against the fore 73-124, NPS: the forepaw broader)'),
    'skin.paw.side_scale': ('[E]', '§2.5: digits II and V smaller and set back; W2c 0.88, the skeleton\'s own ratio '
                                   'for them (paw.side_digit 0.87): at 0.97 and 0.94 the two forepaws came within 2.0 '
                                   'mm of each other at digit II\'s PIP (x 0, y 19 mm; AG 05.13 asks 3)'),
    'skin.paw.dip': ('[E] [P]', 'W2e: the toe\'s DIP (a soft-tissue point, not a rig joint) 0.38 of the way from the PIP '
                                'to the claw tip and 7.5 mm over that chord (x side_scale): 3 mm under the PIP, so the toes\' '
                                'line falls from the knuckles to the claws in one convex curve (w01\'s paw from the side: '
                                'highest at the knuckles, steep in front); W2d 0.45 / 10.7 (level with the PIP: a long '
                                'flat toe shelf, the "bird foot")'),
    'skin.paw.crest': ('[E] [P]', 'W2l: 0.645 of the way (W2f 0.66): the toe\'s tip 0.7 mm back along the chord, so the '
                                  'shorter, lower claw (skin.paw.claw_dir, claw_base) still reaches the ground >= 5 mm '
                                  'ahead of the soft toe on digit V (5.6; at 0.66 with the lower claw 4.7). '
                                  'W2f (the lead\'s call 5: "the claws leaving at the TOE TIPS near the ground (w08), not '
                                  'high on the toe\'s front (pins from the front, talons in three-quarter)"): 0.66 of the way '
                                  'from the PIP to the claw tip and 4.5 mm over the chord (fore III ~15 mm high, W2e ~22): '
                                  'the soft toe rounds down to its tip and the claw leaves there, a short hook still ahead of '
                                  'the toe (w02 the paw\'s forms: >= 5 mm). W2e: the UNGUAL CREST (the skin fold the claw leaves) 0.58 of the way from the PIP to '
                                  'the claw tip, 9.5 mm over the chord (fore III ~22 mm high): the soft toe ends ~12 mm '
                                  'behind the claw\'s tip, so the hooked claw reaches the ground AHEAD of the toe (w01: the '
                                  'claws leave the toes ~20 mm up and touch the ground 15-20 mm ahead; the soft paw from the '
                                  'pastern\'s caudal line ~99 of its 116 mm); W2d 0.80 / 11.8 (the claw 10 mm long, '
                                  'falling 60 deg from the toe\'s front: a peg)'),
    'skin.paw.claw_section': ('[E] [P]', 'W2l (the lead\'s "the claws\' wedge read"): 11.0 x 6.2 mm at the base (hind 9.6 x '
                                         '5.4; W2i 10.0 / 8.8 deep): with the stronger taper (claw_tip_scale 0.18) and the '
                                         'lower base (claw_base) the claw still leaves its nail fold at the measured 9.0 +- '
                                         '1.0 x 5.0 +- 0.5 mm (III / IV 8.2 x 4.9, 11.5 mm up; scratch_w2lb run fin). '
                                         'W2i (the lead\'s call 6: "claws short, broad at base, blunt (worn tips) ... '
                                         'from front short wedges not pins"): 10.0 x 6.2 at the base (hind 8.8 x 5.4), '
                                         'the width 0.7 / 0.6 mm up on W2h\'s so the wedge reads from the front, held to '
                                         'the measured exit (w08\'s front ~4-5 mm across where the claw leaves the toe '
                                         'hair; w02 the paw\'s forms 5.0 +- 0.5: run w2i1\'s 6.4 left the toe 5.6 wide). '
                                         'W2g (the lead\'s call 6: "the claws as claws: the measured section at the base '
                                         '(9.0 x 5.0 mm), curving down from the toe tips with the nail bed\'s fold, never '
                                         'thin pins from the front"): 10.0 x 5.5 at the base (hind 8.8 x 4.8), the base '
                                         'just under the toe\'s front (claw_base), so the claw leaves its nail fold at the '
                                         'toe\'s tip 9.1 x 5.1 mm (III / IV, 12.9 mm over the ground; II / V 7.9 x 4.4 and '
                                         '7.7 x 4.3 at 11.1 / 10.6 mm, the side_scale: w02 run w2g2, the final paw) and '
                                         'stays 4.1-4.6 mm wide down half its visible length (claw_taper), not the W2f '
                                         'claw\'s 7.9 x 4.5 exit 9.8 mm up thinning to 3.3 (work/bestiary/wolf/scratch_w2g/'
                                         'paw_probe.py, the composed paw). '
                                         'W2e: the claw\'s section, a laterally compressed oval 11.5 deep by 6.2 mm wide '
                                         'at the base (fore; hind 10.1 x 5.5), x side_scale for II and V, so that WHERE IT '
                                         'LEAVES THE TOE\'S SKIN (0.41-0.47 of its length from the base, 14-17 mm up: '
                                         'check_w2e/claw_exit.py) it is 9.0 x 5.0 mm (III / IV; II / V 7.6 x 4.4, hind III '
                                         '7.8 x 4.3): w01\'s near claw 8-11 mm deep where it leaves the crest (the W2e check '
                                         'read ~8 mm on w01_foreclaws_8x.png, 0.40 mm / px), w08\'s front ~4-5 mm across. '
                                         'The W2e build put 8.5 x 5.2 at the buried base, so the claws left the toes 5.8-6.8 '
                                         'x 3.7-4.3 and were 5.4 x 3.6 at 10 mm over the ground (now 7.0 x 4.1; w01\'s '
                                         'visible near claw ~7-8 mm deep along its length): pins from the front, check_w2e/'
                                         'out/claws_ba.png. W2d round '
                                         'cones 11 mm across, pegs (the lead: "not straight 11 mm pegs"). The claws are '
                                         'parts of their own (keratin), never flowed; a PSWEEP each'),
    'skin.paw.claw_dir': ('[E] [P]', 'W2l (the lead\'s "the claws\' wedge read"): leaving at 28 deg below the horizontal, '
                                     'arriving at 70 (W2h-W2k 14 / 82): w01\'s near claws leave the toe going forward and '
                                     'down and curve onto the ground (research/wolf_photos/w01, the forepaw at full '
                                     'resolution), and w08\'s front sees them foreshortened, wedges; arriving at 82 the '
                                     'claw\'s last half fell straight down, a vertical PIN from the front with parallel sides. '
                                     'The turn 41 deg (w02 >= 35). Leaving flatter (10-26) with the lower base broke '
                                     'PSWEEP\'s band check on digit II / V claws or folds (scratch_w2lb, a CPU sweep). '
                                     'W2i: kept (arriving at 72 the hind claws\' axes turned back on themselves: the '
                                     'tip lies steeper than 72 below the base, PSWEEP\'s band check H -0.19; the worn, '
                                     'blunt look is claw_tip_scale\'s and claw_section\'s). '
                                     'W2h (the lead\'s call 5: "the claws as short dark hooks, broad at the base, curving '
                                     'down from the toe tips (w08), not pins"): leaving the toe at 14 deg below the '
                                     'horizontal and arriving at the ground at 82: a hook whose back curves over from the '
                                     'toe\'s tip (w08\'s front: the claws\' backs arch forward out of the toe hair before '
                                     'turning down). '
                                     'W2g: leaving at 32 deg (the shorter claw from the toe\'s tip turns 44 deg onto the '
                                     'ground: 25 turned too sharply for its section, PSWEEP\'s band check). '
                                     'W2e: the claw leaves its base 25 deg below the horizontal along the toe and arrives '
                                     'at its tip 76 deg below it (limbed.claw_points: a quadratic curve, its back convex, '
                                     'the point turned down onto the ground: w01\'s near claws, side)'),
    'skin.paw.claw_tip_scale': ('[E]', 'W2l (the lead\'s "the claws\' wedge read"): 0.18, the tip 2.4 mm wide and ~2.9 '
                                       'deep with the 0.8 mm corner radius (a blunt worn end, not a point) from a 4.9 mm '
                                       'exit: the claw TAPERS to it, a wedge from the front; W2i\'s 0.42 kept the tip 3.5 '
                                       'wide under a 5.4 exit, parallel sides: the pins. Its talon read (W2h 0.22) was the '
                                       'claw\'s length and fall, now 12.3 mm visible on III / IV (W2k 14.3) falling at 70. '
                                       'W2i (call 6, "blunt (worn tips)"): 0.42, the point ~4.2 x 2.7 mm plus the corner '
                                       'radius: a worn end, not a point (W2h 0.22 printed a talon). '
                                       'W2h (call 5, "broad at the base"): 0.22, the point ~2.2 x 1.2 mm, the claw a cone '
                                       'from its measured base. '
                                       'W2g: 0.32 (a blunt point ~4.3 x 2.9 mm). '
                                       'W2e: the claw\'s section at its tip 0.28 of the base\'s core (plus claw_rho): a '
                                       'blunt point ~4.4 x 2.9 mm (fore III; the W2e check\'s thicker section)'),
    'skin.paw.claw_rho': ('[E]', 'W2e: the claw section\'s corner radius, 0.8 mm (the PSWEEP\'s offset: the tip rounded)'),
    'skin.paw.claw_base': ('[E]', 'W2l: 4.5 mm ahead of the crest and 0.5 mm DOWN (W2g 5.5 ahead, 1.5 up): the claw '
                                  'leaves the toe lower (III / IV 11.5 mm over the ground, W2k 14.3), nearer the toe\'s tip '
                                  'as w01\'s and w08\'s do, and its fold 1 mm further back on the shortest toe (digit V\'s '
                                  'claw 5.6 mm ahead of its toe). '
                                  'W2g (call 6, "curving down from the toe tips"): the claw\'s base 5.5 mm AHEAD of the '
                                  'crest along the toe and 1.5 mm up (x side_scale), ~3.5 mm under the toe\'s round front: '
                                  'the claw leaves the toe\'s tip with its full section instead of passing 9 mm of toe '
                                  'and showing only its thin end under it. '
                                  'W2e: the claw\'s base 2 mm back along the toe from the crest and 1.5 mm up (x '
                                  'side_scale), inside the toe\'s end'),
    'skin.paw.claw_taper': ('[E]', 'W2h (call 5, "short dark hooks, broad at the base ... not pins"): 1.0, the section '
                                   'tapers evenly from the base to the point (W2g\'s 1.6 kept it near its base size down '
                                   'its length: a rod). '
                                   'W2g (call 6, "never thin pins from the front"): the section scales 1 - (1 - tip_scale) '
                                   'u^1.6 along the claw (W2e u^1.2): broad down its visible length, then the point '
                                   '(limbed.claw_args)'),
    'skin.paw.claw_fold': ('[E] [P]', 'W2g (call 6, "with the nail bed\'s fold"): THE NAIL BED\'S FOLD, the skin\'s lip '
                                      'round the claw\'s root: the claw\'s own section 1.0 mm larger all round over its '
                                      'first 3.0 mm of axis (with its 1.8 mm rounded end ~1.5 mm out past the toe\'s skin; '
                                      'at 4.5 the fold carried the side toes\' fronts forward and their claws\' lead fell '
                                      'under w02\'s 5 mm, run w2g1), k 2 mm (limbed.claw_fold): a skin '
                                      'member of the paw, flowed with it, the claw a primitive leaving it (w01 / w08: the '
                                      'claw leaves a fold of skin at the toe\'s tip)'),
    'skin.paw.k_meta': ('[E]', 'W2g (call 6, "no rounded block with a crease along its top"): the metacarpal / metatarsal '
                               'pad blended by 8 mm (the digital pads keep k_pad 6), within the paw group\'s k (a member '
                               'k past its group\'s is culled short at its box: a seam)'),
    'skin.paw.dewclaw_section': ('[E]', 'W2e: the dewclaw\'s claw 5.0 x 3.4 mm at its base (W2d a round cone 5.6 mm)'),
    'skin.paw.k_claw': ('[E]', 'W2d: the claw into the toe at its crest (a 1.5 mm fillet: the crest\'s fold)'),
    'skin.paw.web': ('[E] [P]', 'W2e: THE WEB between neighbouring toes (the lead: "one COMPACT rounded mass as w08 shows '
                                '(toes held tight, shallow grooves with skin between, not sausages grooved to the '
                                'ground)"): a round cone along each pair\'s mid-line from their PIPs to 0.75 of the way to '
                                'their DIPs, its axis 6 mm under theirs, its radius theirs - 2 + 6 mm (its top a 2 mm '
                                'groove under the toes\' tops, its bottom ~8 mm over the ground), k 4 mm; the toes\' fronts '
                                'stay free lobes (w08)'),
    'skin.paw.ramp': ('[E] [P]', 'W2e: THE RAMP (the lead: "the pastern meeting the paw\'s dorsum in one curve (~130 deg, '
                                 'w01), not ~95"): a rounded box whose top runs at 28 deg from the pastern\'s front 20 mm '
                                 'over the MCP head down to the knuckles over III / IV (half width 22, radius 10 mm, k 12): '
                                 'the dorsum then meets the pastern\'s front (75 deg) at ~133 deg; W2d\'s knuckle box '
                                 'met it flat at ~95-105'),
    'skin.paw.ramp_hind': ('[E]', 'W2e: the hind ramp, 18 mm over the MTP head, half width 20, radius 9'),
    'skin.paw.heel': ('[E] [P]', 'W2l (the lead\'s "the heels\' slope"; the W2i checker: "the heel is a block with a '
                                 'vertical back"): the cones\' lower ends 14 mm under the MCP head and 20 behind (W2i 5 / '
                                 '17), r 10 (was 11), 6 mm either side of the midline (was 11): the W2k paw\'s back stood '
                                 'at -27..-30 mm from the head from 2 to 35 mm up (the pad\'s rounded end and the cone\'s '
                                 'lower sphere stacked at one depth: a wall), 4-15 mm behind the leaning pastern\'s line; '
                                 'now it slopes back from the pastern (-26 at 35 mm) to the heel\'s most caudal point (-32 '
                                 'at 11-14 mm) and rounds forward under it to the pad (-28 at 2 mm), as w01\'s does (its '
                                 'back leaning ~11 deg from 40 mm down to its most caudal point at ~16 mm, then rounding '
                                 'under; research/wolf_photos/w01, the near forepaw at full resolution); the cones closer '
                                 'together so the heel reads as one rounded mass from behind, not two lobes. '
                                 'W2i (the lead\'s call 6: "metacarpal pad rounded, its back sloping into the '
                                 'metacarpus"): the cones from 38 mm up the pastern\'s back (W2h 30), r 6.2 there (W2h '
                                 '7.5) -> 11: the pad\'s back a longer, lower slope up the metacarpus (w01\'s caudal '
                                 'outline, research/wolf_work/checks/w01_fore.png). '
                                 'W2h (the lead\'s call 5: "the heel a low metacarpal pad (w01), not a block"): the two '
                                 'tapered cones from 30 mm up the pastern\'s back (W2g 42) down to 5 under the head and 17 '
                                 'behind (W2g 6, 19), r 7.5 -> 11 (W2g 8.5 -> 12.5): w01\'s caudal outline runs from the '
                                 'pastern down into a low pad (research/wolf_work/checks/w01_fore.png). '
                                 'W2g (the lead\'s call 6: "the heel the carpal / metacarpal pad\'s mass read on w01 / w08 '
                                 '(no rounded block with a crease along its top)"): the tapered cone TWICE, 11 mm either '
                                 'side of the midline (the 8th value), from 42 mm over the MCP head and 6 behind (r 8.5, '
                                 'in the pastern\'s back) down to 6 under it and 19 behind (r 12.5), k 8: the heel spans '
                                 'the metacarpal pad\'s 46 mm at the ground and narrows up the pastern\'s back and sides, '
                                 'so the back of the paw rises from the pad into the pastern as one mass (w01\'s caudal '
                                 'outline one curve, its sides with no ledge). W2f\'s one cone on the midline (r 8-9) left '
                                 'the pad box\'s lateral thirds standing out of the pastern\'s foot: the block\'s top, the '
                                 'crease (work/bestiary/wolf/scratch_w2g/out/paw_p0.png against paw_p5.png). '
                                 'W2f (the lead\'s call 5: "the heel ball behind the pastern blended into the pad (w01\'s '
                                 'caudal line one curve)"): a TAPERED cone from 22 mm over the MCP head and 17 behind (r 8) '
                                 'down to 8 mm under it and 21 behind (r 9), k 10: it fills the dent between the pastern\'s '
                                 'back and the metacarpal pad\'s rounded back corner, so the caudal outline runs down into '
                                 'the pad in one slope (families/limbed._paw_group: 7 values, the two radii). W2e: THE HEEL, a round cone (r 7.5 mm, k 6) from 6 mm over the MCP head and 12 behind '
                                 'it down to 12 mm under it and 20 behind: the pastern\'s caudal line runs on into the '
                                 'metacarpal pad (the lead: "the metacarpal pad tucked under, not ... a ball behind the '
                                 'pastern"; w01\'s caudal outline one curve into the pad); W2d left a notch over the pad'),
    'skin.paw.heel_hind': ('[E]', 'W2l: as the fore (skin.paw.heel): 13 under the MTP head and 18 behind, r 9.5, 6 mm '
                                  'either side. '
                                  'W2h: lowered as the fore (28 up, 4 under, 15 behind; r 7.0 -> 10.5). '
                                  'W2g: the hind heel as the fore, two cones 10 mm either side, 38 up / 5 behind (r 7.8) '
                                  'to 5 under / 17 behind (r 11.5), k 8. '
                                  'W2f: the hind heel tapered as the fore, 20 mm up / 15 behind (r 7.2) to 7 under / 19 '
                                  'behind (r 8.2), k 9; W2e: r 7 mm, 11 / 18 mm behind the MTP head'),
    'skin.paw.knuckle': ('[E]', 'W2e: the KNUCKLE MASS 72 x 26 x 34 mm, its centre 27 mm up and 12 mm ahead of the heads '
                                '(W2d 44 mm long, 6 ahead: its back corners stood out beside the pastern, lumps from '
                                'three-quarter back); W2d: the interdigital web over the metacarpal heads and the proximal '
                                'phalanges (a rounded box, corner radius 10, its flat top level with the toes\' dorsum '
                                'across II\'s and V\'s raised heads: an ellipsoid\'s top fell away there and their proximal '
                                'phalanges stood out as rods, W2d b2); W3-W2c\'s palm box (60 x 22 x 52 mm) read as a flat '
                                'plate under the toes'),
    'skin.paw.knuckle_hind': ('[E]', 'W2e: the hind knuckle mass, 66 x 24 x 32 mm, 10 mm ahead (W2d 40 long, 5 ahead)'),
    'skin.paw.dew_claw': ('[E] [S]', 'W2d: the dewclaw\'s exposed claw 9 mm beyond its crest (§2.5: digit I high on '
                                     'the medial side, not registering [S]); the claw its own part'),
    'skin.paw.pad_digital': ('[E] [S]', 'W2e: the digital pads 10.5 mm high (radius), 32 mm long (W2d 8.5 / 24): each '
                                        'toe\'s distal half now reaches the ground as one lobe (W2d\'s pad stood under the '
                                        'toe as a second ball, a pinched neck between: the front view\'s "sausages"); '
                                        '§2.5, §4.2: four digital pads under the middle phalanges (capsules along the '
                                        'digit: radius = the height; W2 replaced §4.2\'s flattened ellipsoids, whose '
                                        'estimate broke the gradient gate)'),
    'skin.paw.pad_digital_hind': ('[E] [S]', 'W2e: the hind digital pads 10 mm high, 30 long; §2.5: a little smaller'),
    'skin.paw.pad_along': ('[E]', 'W2: each digital pad\'s place between the PIP and the claw bed'),
    'skin.paw.pad_meta': ('[E] [S]', 'W2h (call 5, "a low metacarpal pad"): its half-height and corner radius 9.0 mm (W2d '
                                     '10.5: a 21 mm block behind the toes). '
                                     '§2.5: the metacarpal pad, single-lobed front edge; W2d its corner radius its '
                                     'half-height, 10.5 mm (a rounded profile from the side: b4\'s radius 9 read as a heel '
                                     'block); its place kept (moved 6 mm forward the forepaw came to 105 mm with its '
                                     'claws, the SPEC 115, w01 116); W3 a rounded box 48 x 22 x '
                                     '40 mm, its edges fully rounded (radius 11), centred 6 mm behind the heads (W2-w3c: '
                                     'a capsule across the paw, 22 mm long), so the standing forepaw runs ~98 mm from the '
                                     'pad\'s back to the toes\' front (w3c 92 at the ground; ODFW 97-117 without claws, '
                                     'WOLF_PLAN §2.5 sources) and the pad\'s back stands ~6 mm behind the pastern\'s '
                                     'line (w3d\'s 9 mm further back, radius 9, stood as a heel block); the palm carries '
                                     'the paw\'s width'),
    'skin.head_bands.canine_skin': ('[P] [E]', 'W2g / W2h (the lead\'s W2g call 1: "WHERE THE WET PHOTO AND THE '
                                               'SKULL-ESTIMATE SKIN BAND DISAGREE, THE PHOTO WINS"; W2h call 6: the evidence '
                                               'in the SPEC): the skin over the canine eminence (canid.SKULL canine, along '
                                               '+x) 8-13 mm: the wet r03 in its solved camera (47.6 deg over the palate) shows '
                                               'its flat wet outline beside the canine 5.1-6.1 mm outside the W2f clay\'s 4.9 '
                                               '(work/bestiary/wolf/scratch_w2g/rim_probe.py): 10.0-11.0, +-2 for the wet hair '
                                               'and the outline\'s reading; the dog-anatomy estimate 3-9 [E] (canid.SKULL '
                                               'depths) is exceeded by the photo'),
    'skin.head_bands.muzzle_width_d40': ('[P] [E]', 'W2i (the lead\'s calls 4 and 8: the face judged against the '
                                                    'INDIVIDUALS\' SPREAD, the bands re-derived from the photos with '
                                                    'their sources): 61-83 mm, the spread of the two wolves at d 40: '
                                                    'r03 (wet) 78-81 [P] (below) +-2; w08 (the narrower-muzzled wolf) '
                                                    'r03\'s scaled by the two leathers\' share of their eye spacing, '
                                                    '0.509 / 0.595 [P] (w02 nose read): 66.7-69.3 [E], +-3 a side for '
                                                    'its winter pad coat\'s uncertainty (canid_hull FRONT_MUZZLE tol). '
                                                    'The width is no longer a mass tuned to it (call 4: whisker_pad_'
                                                    'caudal removed; the lips\' hull and the tissue rows give 64-65). '
                                                    'W2g / W2h (as canine_skin): the muzzle\'s width at d 40, 74-85 mm: '
                                                    'the wet r03\'s outline at the flank (d 40-50) 7.5-9.1 mm a side outside '
                                                    'the W2f clay\'s 63, so 78-81 at the skin, +-2 a side (the wet hair, '
                                                    'the reading); the estimate 53-65 (C1B 47 [P] plus 3-9 of lip a side) '
                                                    'is exceeded by the photo'),
    'skin.paw.pad_meta_hind': ('[E] [S]', 'W2h: lowered as the fore, 8.5 mm. '
                                          '§2.5: the metatarsal pad; W2d its corner radius its half-height, 9.5 mm; W3 a '
                                          'rounded box 42 x 20 x 36 mm (radius 10), the '
                                          'standing hindpaw ~90 mm (w3c 82 at the ground; ODFW 86-107)'),
    'skin.paw.k_palm': ('[E]', 'W3: the palm into the digits, the pads and the pastern (the interdigital skin\'s web; '
                               'at 8 mm its top edge stood as a collar round the pastern); W2d the knuckle mass, 8 mm'),
    'skin.paw.pad_carpal': ('[E] [S]', 'W2i (the lead\'s call 6: "carpal pad small"): 9 mm across, r 5.0 (W2h 12, r 6.8). '
                                       '§2.5: the carpal pad, forelimb only, high on the back of the carpus (it does '
                                       'not register); W3 14 mm across, 22 mm under and 17 behind the carpal joint, '
                                       'below the accessory carpal (W2 12 mm and 22 behind: a ball off the wrist)'),
    'skin.paw.dewclaw_r': ('[E] [S]', '§2.5: digit I, medial, high (a round cone; the pad is the cone\'s tip)'),
    'skin.paw.k': ('[E]', '§4.2: the paw group into the limb; W3 8 mm (w3b-w3d\'s 6 mm left a crisp collar where '
                          'the pastern meets the palm, the paw views; w3e\'s 10 mm swelled the forepaws\' medial sides '
                          'to 2.8 mm apart, under AG 05.13\'s 3)'),
    'skin.paw.k_digit': ('[E]', '§4.2: interdigital skin between the round cones; W3 8 mm (the palm fills the web); W2d '
                                '8 mm (b2\'s 6 left grooves the toes\' full length: fingers in the three-quarter view)'),
    'skin.paw.k_pad': ('[E]', '§4.2: the pads onto the digits'),
    'skin.tail.path': ('[E] [H]', 'W2g (the lead\'s call 8: "THE TAIL ROOT with no collar: a lofted transition from the '
                                  'croup\'s section into the tail\'s by construction, not a k-fillet"): the sweep starts 30 '
                                  'mm forward of the first caudal joint and 6 mm under it, INSIDE the croup, as a broad '
                                  'flattened section (r 44 mm, width / depth 1.40), narrowing through tail_0 (31, 1.15) '
                                  'to the tail\'s own round 23 mm 0.6 of the way to tail_1: the root leaves the croup at a '
                                  'shallow angle along its whole rim instead of a 25 mm tube unioned with a 32 mm fillet '
                                  '(the horseshoe collar from behind: work/bestiary/wolf/scratch_w2g/out/tail_ba_w2g.png); '
                                  'the sweep slope 0.686 (gate 0.7). '
                                  '§4.2: 23 mm at the root, 6 mm at the tip, at the bind pitch; W2 starts it at the first '
                              'caudal joint (its cap buried in the rump): §4.2\'s start 30 mm inside along the tail\'s '
                              'own axis lies forward AND up of the root at a 25 deg pitch, and its cap broke through '
                              'the croup ahead of the tail (w02 final review, a crack at z 0.03, y 0.63)'),
    'skin.tail.k': ('[H]', 'W2g (call 8): k 14 mm, a small fillet where the lofted root (skin.tail.path) meets the croup '
                           'at a shallow angle (the transition is the loft\'s, not the fillet\'s). '
                           'W2f (the lead\'s call 6: "the collar round the tail root (the k 24 fillet) blended away"): k 32 '
                           'mm, the fillet\'s curvature step at its edge a third softer again (~1/k); the smin bridges a gap '
                           'only under k / 2 = 16 mm and the tail clears the body by 20.6 mm 130 mm down. §4.2: the tail group blends into the croup at k 15 mm. W2e (the lead\'s call 6: "blend away '
                           'the croup\'s horseshoe rim (the tail fillet k 16, ...)"): k 24 mm, the fillet half again as '
                           'wide (the quadratic smin\'s curvature step at its edge, the rim from behind, ~1/k): the tail '
                           'clears the body by 20.6 mm 130 mm down at its rest hang and more below (scratch_w2eb/'
                           'tail_gap.py, the composed body), and the smin bridges a gap only under k / 2 = 12 mm'),
    'skin.tail.smooth': ('[H] [D]', 'W2g: 20 mm (the loft\'s turn from the croup\'s forward run into the hang). W2: the '
                                    'tail axis smoothed over 15 mm (PCHIP is C1: its curvature jump at a '
                                    'control point creases a sweep, heads/canid._curve)'),
    'skin.tail.fillet': ('[D] [P]', 'W2g: (0.140, 0.175), the W2f check\'s split moved 25-30 mm along with the sweep\'s new '
                                    'start 30 mm inside the croup. '
                                    'W2f CHECK: the k fillet only on the tail\'s first 0.150 m, the rest (from 0.115 m, '
                                    'the overlap coinciding) a hard union at its own radius (families/limbed._tail_group): '
                                    'the smooth union met the body GRID members\' CLAMPED far fields (+-10 mm) past their '
                                    'boxes and swelled the hanging tail +7.0 mm laterally / +2.5 caudally below the hind '
                                    'limbs\' box tops (y 318 mm), a flat-sided slab with a step at hock height in every '
                                    'side and back view (work/bestiary/wolf/check_w2f/probe_tail.py: k 32 against 10 / D '
                                    '= 9.0 mm gives exactly 7.0). The root\'s measured swell (the croup\'s fillet) is gone '
                                    'by 0.11 m (+0.3 mm at 0.108, 0.0 from 0.115 to 0.156): the overlap lies where the '
                                    'smin adds nothing'),
}

TAG_RE = re.compile(r'\[(P|C|R|H|D|E|S)\]')


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
