"""CROSSBREED M2: the SOCKET graft (work/bestiary/research/CROSSBREED_DESIGN.md §2.9 SOCKET, §8 M2; THE LEAD'S DECISIONS
1-13): the production octopus's arm R1 (arm0) past cut 8 replaced by the stag beetle's own leg from the knee on: the
TIBIA sunk in a soft MEMBRANE COLLAR that the octopus skin morphs into, then the five TARSOMERES and the two CLAWS, each
a closed rigid shell on a graft joint that follows the leg's own segments. M1's pipeline (forge/graft.py: the ring
record, the native group, the strip on the base's lattice, ASSEMBLE) carries the seam; this module adds what a socket
needs and M1's check left open:

  DONOR         the beetle's B4 leg cages (families/arthropod_cage.py b4l-2, read, never edited): the RIGHT fore leg (the
                left's exact mirror, as the beetle's right side is built), the tibia onward, at ONE author scale (the
                tibia's section where it leaves the femur at SOCKET['root_share'] of the ring's diameter: generated at the
                socket's size, never squashed), placed by a rigid map: the tibia's root axis on the ring's distal axis, its
                dorsal (the clay's section normal) on the arm's aboral side; the low = the cage at its limit positions,
                the high = its L4 limit mesh (as the legs build left them)
  COLLAR        the BAND (§2.7) of the SOCKET seam (§2.9): the ring (frozen bits), the native's own first loop past it
                (w = 0 over [0, h]), then designed rings morphing from the native's section to the LIP: a CREST standing
                SOCKET['lip_t'] proud of the tibia and a TUCK SOCKET['tuck'] inside it, so the membrane meets the shell
                at a steep angle (a shallow skirt would shimmer along the crossing, §2.1), never a gap. w is C1 (zero
                slope at both ends: a smoothstep, whose STEEPEST slope is 1.5 x its mean), so the morph length holds the
                design's taper |dr/dz| <= 0.25 at the steepest loop (G-R6's bar 0.35) and §2.7's bound |grad w| x
                |f_native - f_collar| <= 0.25 (the radius step plus the fold's relief): the band is lengthened, never
                the bound broken (v1 sized it by the mean taper: G-R6 0.388, the bound 0.46)
  HIGH          the collar's field: f = mix(f_native, f_collar, w), redistanced (§2.7's field MORPH: the field-blend
                kernel M1 left to M1b, morph_values); f_collar a radial membrane tube interpolated from the native's
                section to the lip, a soft transverse FOLD (the `membrane` dressing, §2.10), the rolled lip as a rounded
                cap tucked inside the shell
  RIG           the graft joints arm0_g09 (the tibia, at the beetle's own knee: the collar's lip rides it) .. g14 (t5),
                g15 (the claws), the beetle's own frames carried rigidly (x along the bone, + about z folds); the ring
                frozen, the native loop's weight on the dropped arm0_09.. moved to the graft root arm0_08, the collar
                ramping arm0_08 -> arm0_g09, the TUCK 100 % on arm0_g09 (the lip stays on the shell in every pose), the
                shells rigid (one influence), the beetle's sleeves ramps between their two joints
  GATES         G-R10 (the lip within 0.5 texel of the shell over 360 deg, the shell sunk >= 0.2 r and >= 3 texels, no
                daylight from the five standard views), the collar's G-R6 (taper, bend, folds, angles)

Units: metres in the octopus's creature frame (a creature faces +Z, +X is its left) unless named life mm (the beetle's
plan frame, families/arthropod_cage.py).
"""
import math

import numpy as np

TAU = 2.0 * math.pi
SOCKET = dict(pair='fore', side='R',
              root_share=0.88,     # the tibia's root width (where it leaves the femur: the knee sleeve's X) / the ring's
                                   # diameter: the collar gathers the arm's skin onto a narrower shell. The arm's ring is
                                   # oval (19.0 mm aboral-oral, 15.6 across): at 0.80 the taper at 0.25 needed a 22 mm
                                   # morph (a 30 mm neck, 2.2 r_shell, p_socket v1); 0.88 halves it; the design's 0.94
                                   # [E] leaves the sides flush
              lip_t=0.0012,        # the CREST's stand off the shell (m): ~4 texels at 3,492 px/m, the membrane's roll
              tuck=0.0008,         # the TUCK inside the shell (m)
              tuck_dz=0.0012,      # the tuck's step past the crest along the axis (m): the lip dives at ~55 deg (M2c:
                                   # softer, 0.9 mm then 1.2 at the restart; M2b's 0.6 mm dove at ~70 deg, a clean
                                   # machined rim)
              taper=0.25,          # the design's |dr/dz| at the steepest loop (G-R6's bar 0.35)
              lipschitz=0.25,      # §2.7: |grad w| x |f_native - f_collar| over the band, at most
              ring_step=0.0045,    # the designed rings' spacing at most (m)
              fold_a=0.0011, fold_s=0.0013,       # the membrane fold's relief and width (m; the high only)
              u_lip=None,          # the lip's station on the tibia (arc share; None: the knee sleeve's exit X)
              # (M2c, the lead's call 5: the amber cuff read as a hose ferrule: even width, horizontal ribbing, a clean
              # cylindrical lip) the cuff made UNEVEN round the arm by low harmonics of theta (cuff_wave): the crest's
              # stand off the shell varies by lip_var of itself, the two folds wander along the axis by fold_wander of the
              # morph and swell and fade by fold_var of their relief; the lip's roll SOFTER: rounded over roll_k x lip_t
              # in the high (M2b 1.4), diving over tuck_dz past the crest (M2b 0.6 mm, ~70 deg). (M2c restart: in the
              # first M2c stills the cuff still read as a ferrule, its lip one clean planar ring, the folds parallel
              # rings) the LIP'S LINE WAVES along the axis by lip_dz (lip_wave: the crest and the tuck at z_lip + dz(theta),
              # every designed ring at the same share of its own column; z_lip moves out by lip_dz so the shortest column
              # still holds the taper and the Lipschitz bound), the stand and the folds vary more, the roll rounder, the
              # dive softer
              lip_var=0.45, fold_wander=0.14, fold_var=0.80, roll_k=3.2, cuff_seed=7, lip_dz=0.0028)
# (M2d, the lead's call 2: up close the cuff still read as a SLEEVE on a polished pipe: a rolled rim standing 0.66-1.74 mm
# off the shell all round) the membrane's edge THINNER, lying closer on the shell, as tissue grown onto a hard part does (a
# nail fold, a coronary band, the lips round a beak: §1.1's SOCKET): the crest's stand 0.75 mm +- 30 % (0.53-0.98 mm; it
# never drops under G-R8's measured lip travel, 0.416 mm at most over 16 seeds x 20 s, so the shell never shows through
# the edge in motion), its roll over 2.4 x the stand (1.8 mm: the same soft dive, a thinner edge). The tuck, its step and
# the lip line's wave stay M2c's (G-R10 and G-R8 proved them). The rest of the grown read is the material's (GROWN_ROOT)
SOCKET.update(lip_t=0.00075, lip_var=0.30, roll_k=2.4)


def cuff_wave(theta, seed, n=3, falloff=0.6):
    """a smooth periodic wave round the arm in [-1, 1]: harmonics 1..n of theta, amplitudes falling by `falloff` per
    harmonic, phases seeded (the cuff's unevenness: a tissue's, never a machined ring's)"""
    th = np.asarray(theta, np.float64)
    rng = np.random.default_rng(int(seed))
    ph = rng.uniform(0.0, TAU, n)
    amp = falloff ** np.arange(n)
    w = sum(a * np.sin((k + 1) * th + p) for k, (a, p) in enumerate(zip(amp, ph)))
    return w / float(amp.sum())


def lip_wave(theta, lip_dz, seed):
    """(M2c restart) the LIP LINE's offset along the socket's axis at theta (m): lip_dz x a three-harmonic cuff_wave on
    its own seed (the cuff's seed + 9); the collar's crest and tuck stand at z_lip + this, morph_values and the material
    read the same function from the collar's report"""
    return float(lip_dz) * cuff_wave(theta, int(seed) + 9, n=3, falloff=0.55)
# the SOCKET's MEMBRANE DRESSING (CROSSBREED §2.10, the designed boundary; BEETLE_PLAN §5.4: soft, pale to amber,
# translucent): the collar's octopus skin changes into it over its last 60 % (m2_mat). The graft's OWN colour, defined here
# once: M2 took the B8 round's membrane row (10-28), which the beetle's own membranes have since left for M3v's dark
# red-brown (species/stag_beetle_skin.ZONE['membrane'], the six tarsal sleeves' source); the lead's look check read
# this amber sleeve as the graft's grown socket ("properly weird"), so the socket keeps it. Linear albedo; the roughness
# wetter than the skin's; the thin mask up (the membrane's translucency)
DRESSING_MEMBRANE = dict(albedo=(0.2500, 0.1500, 0.0700), rough=0.30, thin=0.85)
# (M2d, the lead's call 2) THE GROWN ROOT: where the octopus's flesh takes the chitin, the hard part reads GROWN OUT of the
# soft one, not slid into it. The design's SOCKET (CROSSBREED §1.1: a soft collar wrapping a hard shell sunk into it, "nail
# bed, antler pedicle, coronary band, articular membrane, a lip round a beak"; §2.9: the shell keeps its own material) is
# nature's junction of a hard tissue MADE by a soft one, and every one of those shows the same two things on the hard
# side: the cuticle (or horn, or nail) is YOUNG where it leaves the tissue, untanned, matte and a little translucent, and
# matures away from it (a squid's or an octopus's beak: soft, pale and hydrated where the buccal mass holds it, dark and
# hard at the tip; a nail's lunula; a hoof's periople), with growth STRIAE along its length; and the tissue's edge LIES ON
# it as a thin film (a nail's cuticle) rather than standing off it as a cut rim. M2c's tibia was mature, mirror-polished
# chitin up to the lip, round as the beetle's neck is there (the clay keeps it round to u 0.08-0.18: in the beetle that
# section hides in the femur's club): a polished pipe. So over the tibia, by the distance z' past each column's crest
# (the lip line's own wave):
#   FILM      the membrane's edge colour carried onto the shell for film[0]..film[1] (a 2.5 mm value noise picks the
#             reach per point: a ragged, adhering edge), matte (coat lost, base roughness `film_rough`), translucent
#   YOUNG     the cuticle young to z' `young`, mature by `mature` (smoothstep; the boundary wandering +- `wander` by a 6 mm
#             noise): its colour from the membrane's edge colour to the chitin's own, its coat `young_coat` of the mature
#             amount rising to all of it, the coat's and the base's roughness up by `young_rough` / `young_base`, the
#             thin mask up by `young_thin`
#   STRIAE    fine LONGITUDINAL growth ridges (the wavelengths `striae_l` round the root, bent along the axis, their
#             height `striae_h`), full over the young cuticle, fading to `striae_keep` of it by maturity: the reflection of
#             the sky breaks along them, where a mature round pipe mirrors it whole
# Metres at the part's scale; linear albedo (the film / young colour: a warm dark brown near the membrane's sclerotised
# edge, ~1.7 x the chitin's luminance, R/G 1.7); applied in the chain's material stage (m2_mat) on the tibia's texels
# through grown_root(). (M2d r1, LOOKED: m2d/look/r1/cuff_r1_4.png, stations_ba.png: at 1.5 x the chitin's luminance with
# R/G 1.7 and B/G 0.55 and a quarter more thin mask the young cuticle read as an ORANGE band under the sun from below, and
# striae kept at a quarter over the mature shell drew the whole tibia as BRUSHED METAL in the grazing stations: so the
# young cuticle darker and duller, over a shorter run, the striae finer and on the young cuticle only. (M2d r2, LOOKED:
# m2d/look/r2_cuff_ba.png, r2_cuff0_lip.png: from below the young cuticle still glowed orange-brown, all but matte under
# the sand's bounce and lit through its thin mask, and a dark film could not soften the membrane's pale edge) so the
# young cuticle keeps a third of its coat and no extra thin mask, and the FILM takes the LIP'S OWN COLOUR round the arm
# (the chain's material stage measures it on the collar: m2_mat lip_col), wet as the membrane is (rough 0.35), thin 0.20.
# (M2d r4, LOOKED: m2d/look/r3_st14_crop.png, r3_cuff_ba.png: over the young cuticle the striae still drew BRUSHED
# ALUMINIUM in the grazing stations; their finest set, 0.9 mm, is ~3.2 texels a period at the atlas's ~3,500 px/m, at the
# edge of what a texel resolves, so it aliased into streaks) the 0.9 mm set dropped, the 1.3 / 2.1 mm sets at half height
GROWN_ROOT = dict(film=(0.0012, 0.0034), film_cell=0.0025, film_rough=0.35, film_thin=0.20,
                  young=0.006, mature=0.022, wander=0.004, wander_cell=0.006,
                  young_col=(0.0300, 0.0175, 0.0120), young_coat=0.30, young_rough=0.22, young_base=0.12,
                  young_thin=0.0, striae_l=(0.0013, 0.0021), striae_h=(0.000003, 0.0000025),
                  striae_keep=0.0, seed=17)


def grown_root(P, O, R, z_crest_of, value_noise, opts=None):
    """THE GROWN ROOT's per-point weights (GROWN_ROOT above) at points P (n, 3) of the tibia (the shells' position
    driver, the bind's creature frame): O, R the socket frame (columns X, Y, Z), z_crest_of(theta) each column's crest
    station along Z, value_noise(P, cell, seed) the cuticle pass's own noise (families/arthropod_skin.value_noise: a
    smooth [0, 1] field in 3D). Returns dict(zp (the distance past the crest, m), film (0..1), young (0..1: 1 young, 0
    mature), striae (the growth ridges' height, m: slopes are taken within each island by the caller), theta)"""
    o = dict(GROWN_ROOT, **(opts or {}))
    P = np.asarray(P, np.float64)
    q = (P - np.asarray(O, np.float64)[None]) @ np.asarray(R, np.float64)
    th = np.arctan2(q[:, 1], q[:, 0])
    zp = q[:, 2] - z_crest_of(th)
    sd = int(o['seed'])
    f0, f1 = o['film']
    reach = f0 + (f1 - f0) * value_noise(P, o['film_cell'], sd)
    film = np.where(zp > -0.002, 1.0 - smooth01(zp / np.maximum(reach, 1e-6)), 0.0)
    wb = o['wander'] * (2.0 * value_noise(P, o['wander_cell'], sd + 1) - 1.0)
    young = 1.0 - smooth01((zp - o['young'] - wb) / max(o['mature'] - o['young'], 1e-6))
    young = np.where(zp > -0.002, young, 0.0)
    rho = np.hypot(q[:, 0], q[:, 1])
    circ = TAU * float(np.median(rho)) if len(rho) else TAU
    h = np.zeros(len(P))
    for k, (lam, a) in enumerate(zip(o['striae_l'], o['striae_h'])):
        bend = 0.9 * cuff_wave(q[:, 2] * TAU / 0.02, sd + 3 + k, n=3)        # each ridge set wanders along the axis
        env = 0.55 + 0.45 * value_noise(P, 0.004, sd + 7 + k)                # and swells and fades along its run
        # (M2d r6) a WHOLE number of ridges round the root, so the phase closes where theta wraps at +-pi (the arc length
        # over lam left a ~half-period jump there, a faint seam along the young cuticle)
        n_k = max(1, int(round(circ / lam)))
        h += a * env * np.sin(n_k * th + bend + k * 1.7)
    keep = o['striae_keep'] + (1.0 - o['striae_keep']) * young
    return dict(zp=zp, film=film, young=young, striae=h * keep * (zp > -0.002), theta=th)


def _unit(v):
    v = np.asarray(v, np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-300)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ============================================================================================ the donor: the leg
LEG_SEGS = ('tibia', 'tarsus_1', 'tarsus_2', 'tarsus_3', 'tarsus_4', 'tarsus_5', 'claw_a', 'claw_b')
SLEEVE_CHILDREN = ('tarsus_1', 'tarsus_2', 'tarsus_3', 'tarsus_4', 'tarsus_5', 'claw')     # the ankle on: the part's own


def leg_donor(legs, spec, chain, clay, pair='fore', side='R'):
    """the donor's segments in LIFE MM (the beetle's plan frame), the right side the left mirrored (p_R = M p_L, quads
    reversed, the vertex numbering kept: arthropod_cage.mirror_legs): per segment the low (V, Q: the cage at its limit
    positions), the high (lim_V, lim_F: the L4 limit), its creases, spine (P, N mirrored), joint and parent, and the
    tube RINGS in the cached numbering (re-made by arthropod_cage.leg_cages on the same clay and checked bit for bit
    against the cache: the cache keeps no rings). The sleeves from the ankle on. Returns dict"""
    from .families import arthropod_cage as AC
    M = np.array([-1.0, 1.0, 1.0]) if side == 'R' else np.array([1.0, 1.0, 1.0])
    segs_L = legs['pairs'][pair]
    cages = AC.leg_cages(spec, chain, clay, pair)
    out = dict(pair=pair, side=side, segs={}, sleeves=[])
    for nm in LEG_SEGS:
        s_ = segs_L[nm]
        V, Q = np.asarray(s_['V'], np.float64), np.asarray(s_['Q'], np.int64)
        src = cages['claw_a'] if nm == 'claw_b' else cages[nm]
        Qc = np.asarray(src.Q, np.int64)
        used = np.zeros(len(src.V), bool)
        used[Qc.ravel()] = True
        new = -np.ones(len(src.V), np.int64)
        new[used] = np.arange(int(used.sum()))
        if nm != 'claw_b':
            assert np.array_equal(src.V[used], V), f'{nm}: leg_cages does not re-make the cached cage'
        rings = new[np.asarray(src.rings, np.int64)] if src.rings is not None else None
        assert rings is None or (rings >= 0).all(), f'{nm}: a ring vertex left out of the cage'
        P, N = (np.asarray(a, np.float64) for a in s_['spine'])
        if side == 'R':
            V, Q = V * M, Q[:, ::-1].copy()
            lV, lF = np.asarray(s_['lim_V']) * M, np.asarray(s_['lim_F'])[:, ::-1].copy()
            P, N = P * M, N * M
        else:
            lV, lF = np.asarray(s_['lim_V'], np.float64), np.asarray(s_['lim_F'])
        cq = src.meta.get('cap_quads')
        # (the tibia's caps: their interior vertices in the cached numbering; their quad indices shift when a feature
        # takes cap quads, the vertex ids do not)
        cap_int = None if cq is None else [new[np.asarray(cq[e]['interior'], np.int64)].tolist() for e in (0, 1)]
        out['segs'][nm] = dict(V=V, Q=Q, lim_V=lV, lim_F=lF, sharp=dict(s_['sharp']), spine=(P, N),
                               joint=s_['joint'] + ('_' + side), parent=s_['parent'], rings=rings, kind=s_['kind'],
                               copy_of=s_.get('copy_of'), cap_interior=cap_int)
    for sl in legs['sleeves'][pair]:
        if sl['child'] not in SLEEVE_CHILDREN:
            continue
        V, Q = np.asarray(sl['V'], np.float64), np.asarray(sl['Q'], np.int64)
        if side == 'R':
            V, Q = V * M, Q[:, ::-1].copy()
        out['sleeves'].append(dict(name=sl['name'], parent=sl['parent'], child=sl['child'], K=int(sl['K']), V=V, Q=Q,
                                   parent_joint=sl['parent_joint'][:-2] + '_' + side,
                                   child_joint=sl['child_joint'][:-2] + '_' + side))
    kn = next(x for x in legs['sleeves'][pair] if x['child'] == 'tibia')
    out['knee_X'] = np.asarray(kn['X'], np.float64) * M
    out['tibia_root'] = legs['tibia_root'][pair]
    return out


# ============================================================================================ M2c: the donor FORGED FOR ITS
# SOCKET (CROSSBREED §0 point 2, §3.4 step 3, §9 R11: "length and taper laws scaled from the ring, never the donor's
# absolute size"; the lead's M2c call 1). M2 / M2b scaled the beetle's leg by ONE author scale set by the ring (the
# tibia's root at root_share of its diameter), so the leg kept the beetle's own proportions at the ring's size: a 316 mm
# tibia, the claws' tip 522 mm past the ring of an arm whose native part past the ring is ~400 mm, a black spear lying on
# the sand. M2c forges it for its socket: its SECTIONS by the ring (the same author scale), its LENGTH by the host (the
# leg from the ring to the claws' tip as long as SOCKET_FORGE['share'] x the native arm it continues, from the ring to
# that arm's tip), every segment of the leg shortened by ONE factor lam (lengths x lam at the sections' scale), the
# beetle's own features kept at their own size (the tibia's teeth, the tarsomeres' beads and lobes, the claws' hooks):
# a stocky beetle limb. It runs the BEETLE'S OWN GENERATOR (arthropod_cage.clay_programs, leg_cages, limit) on a rest
# chain re-proportioned from the knee on (socket_chain), in memory: the beetle's files and its legs cache are read, never
# written. Its SHIPPED LOW is the cage subdivided on its limit (the lead's M2c call 3: the beetle's 80-triangle tarsal
# lows faceted at the close cameras and sat 1.2-1.8 mm p95 inside their highs), and its SLEEVES are built on those
# shipped lows (the M2b check: built on the limit at 0.84 of its section, they poked through the lows at every tarsal
# joint)
SOCKET_FORGE = dict(share=1.0,        # the leg's length from the ring to the claws' tip / the native arm's from the
                                      # ring to its tip (bind lengths along each chain)
                    low_levels=dict(tibia=1, tarsus=2, claw=2),   # the shipped low: the cage subdivided this many
                                                                  # levels, its vertices on the limit
                    tooth_shrink=0.30,    # a fore tooth is kept while the cage's min_gap shrinks its base by at most
                                          # this share of its length on the side it shares with a bigger kept tooth
                                          # (tibia_cage shrinks closer spans toward their centres); else dropped
                    # (M2d, the lead's call 4: the 9 fore teeth read as a COMB, a rasp at creature distance: the beetle's
                    # B3b table, arthropod_parts.FORE_TEETH, has its small teeth all 0.24-0.28 mm at an even 0.065-0.075
                    # of the length) the SOCKET'S OWN tooth table (fraction from the knee, protrusion, base length; mm
                    # life, FORE_TEETH's convention), read off the same photo (M1d, the left fore tibia, s01a at 64.527
                    # px/mm: m2d/tools/teeth_trace.py, the outer edge by perpendicular rays, each tooth's protrusion over
                    # the edge's own smooth envelope; LOOKED, m2d/look/photos/teeth_trace.png): the small teeth IRREGULAR,
                    # 0.06-0.21 mm over the envelope at spacings 0.04-0.13 of the length, two of them hardly more than
                    # bumps; their fractions mapped onto B3b's (the two readings' big teeth 0.682 / 0.909 = B3b's 0.64 /
                    # 0.88), their protrusions x 1.3 (B3b read from the shaft's line, the trace from its envelope; the
                    # bumps kept at 0.12, the forge's smallest stroke that still reads), the bases as traced. B3b's three
                    # big teeth (0.64, 0.88 and the terminal 0.98, past the trace's apex station) kept as B3b read them.
                    # socket_teeth still drops what the shorter tibia crowds (the smaller first). The beetle's own table
                    # is untouched (its file read-only): this is the graft's
                    teeth=((0.190, 0.25, 0.50), (0.257, 0.12, 0.39), (0.357, 0.27, 0.61), (0.423, 0.12, 0.40),
                           (0.500, 0.17, 0.53), (0.640, 0.60, 0.50), (0.725, 0.19, 0.32), (0.765, 0.13, 0.32),
                           (0.838, 0.16, 0.64), (0.880, 0.75, 0.60), (0.980, 0.95, 0.70)))


def _rodrigues(axis, ang):
    k = _unit(axis)
    K_ = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + math.sin(ang) * K_ + (1.0 - math.cos(ang)) * (K_ @ K_)


def socket_chain(chain, pair, lam):
    """the beetle's rest chain (arthropod.rest_chain: life mm) with the leg from the KNEE on re-proportioned: every
    segment vector (knee -> ankle -> the tarsal joints -> the claw joint -> the claws' tip) x lam, so the leg keeps its
    own joint angles, then the shortened sub-leg PITCHED about the knee (a horizontal axis across its plan direction: the
    sprawled fore leg's own knee hinge stands near vertical and cannot lower it) until the claws' tip stands at its own
    height again (arthropod_parts.leg_parts lays the claws' end on the ground: left lifted, the hook would stretch down
    to it). The graft keeps only the sub-leg's own relative angles; the knee's angle to the beetle's femur is not
    grafted. Both sides (the right the left mirrored); solve_leg's dict likewise. Returns (chain', info)"""
    c = pair[0]
    P0 = chain['pos']
    names = [f'tibia_{c}_L'] + [f'tarsus_{n}_{c}_L' for n in range(1, 6)] + [f'claw_{c}_L', f'claw_tip_{c}_L']
    K = np.asarray(P0[names[0]], np.float64)
    pts = [K]
    for a, b in zip(names[:-1], names[1:]):
        pts.append(pts[-1] + float(lam) * (np.asarray(P0[b], np.float64) - np.asarray(P0[a], np.float64)))
    pts = np.array(pts)
    dh = pts[-1] - K
    dh[1] = 0.0
    nh = _unit(np.cross(_unit(dh), np.array([0.0, 1.0, 0.0])))      # horizontal, across the sub-leg's plan direction
    y_tip = float(P0[names[-1]][1])
    turn = lambda a: K[None] + (pts - K[None]) @ _rodrigues(nh, a).T          # noqa: E731
    f = lambda a: float(turn(a)[-1, 1] - y_tip)                                 # noqa: E731
    # the root nearest no turn: scan both ways from 0 for the first sign change, then bisect
    best = None
    for sgn in (1.0, -1.0):
        a0, f0 = 0.0, f(0.0)
        for k in range(1, 181):
            a1 = sgn * math.radians(k * 0.5)
            f1 = f(a1)
            if f0 == 0.0 or f0 * f1 < 0.0:
                lo, hi = a0, a1
                for _ in range(60):
                    mid = 0.5 * (lo + hi)
                    if f(lo) * f(mid) <= 0.0:
                        hi = mid
                    else:
                        lo = mid
                a = 0.5 * (lo + hi)
                if best is None or abs(a) < abs(best):
                    best = a
                break
            a0, f0 = a1, f1
    assert best is not None, 'socket_chain: no turn about the knee puts the claws\' tip back at its height'
    new = turn(best)
    out = dict(chain, pos=dict(P0), legs=dict(chain['legs']))
    M = np.array([-1.0, 1.0, 1.0])
    for nm, p in zip(names, new):
        out['pos'][nm] = p
        out['pos'][nm[:-2] + '_R'] = p * M
    lg = dict(chain['legs'][pair])
    if 'tarsus' in lg:
        lg['tarsus'] = [new[1 + n] for n in range(len(new) - 1)]
    out['legs'][pair] = lg
    seg0 = np.linalg.norm(np.diff(np.array([P0[n] for n in names], np.float64), axis=0), axis=1)
    return out, dict(lam=float(lam), turn_deg=math.degrees(best), hinge=nh.tolist(),
                     life_len=float(seg0.sum()), life_len_new=float(lam * seg0.sum()))


def socket_teeth(L_t, teeth, min_gap, shrink):
    """the fore tibia's tooth table (arthropod_parts.FORE_TEETH: (fraction from the knee, protrusion, base length) mm) for
    a tibia L_t mm long from its neck to the ankle: each tooth keeps its own size (a feature, not a length); biggest
    first, a tooth is kept while tibia_cage's min_gap would shrink its base by at most `shrink` of its length against
    every kept neighbour, else dropped (the crowding a shorter tibia brings). Returns (kept table, dropped table)"""
    rows = []
    for fr, ln, wb in teeth:
        q = min(fr, 1.0 - 0.5 * wb / L_t)
        rows.append((fr, ln, wb, q * L_t, 0.5 * wb))
    kept = []
    for r in sorted(rows, key=lambda r: (-r[1], -r[0])):
        ok = True
        for k in kept:
            gap = abs(r[3] - k[3]) - r[4] - k[4]
            need = 0.5 * max(min_gap - gap, 0.0)                     # each side's shrink toward its centre
            if need > shrink * 2.0 * min(r[4], k[4]):
                ok = False
                break
        if ok:
            kept.append(r)
    kept.sort(key=lambda r: r[0])
    tk = tuple((r[0], r[1], r[2]) for r in kept)
    return tk, tuple((fr, ln, wb) for fr, ln, wb in teeth if (fr, ln, wb) not in tk)


def subdivide_topology(Q, levels):
    """subdiv_sharp.level's TOPOLOGY alone, `levels` times (each quad's four children in its own order, each child's
    corners its corner vertex, two edge points and the face point): the split (UV-island) copy of a cage subdivides in
    step with the closed cage, child for child and corner for corner. Returns Q at the last level"""
    from . import subdiv_sharp as SS
    from .mesh import QuadMesh
    q = np.asarray(Q, np.int64)
    for _ in range(levels):
        m = QuadMesh(np.zeros((int(q.max()) + 1, 3)), q)
        E, _ = m.edges()
        _, q, _ = SS.level(m, np.zeros(len(E)))
        q = np.asarray(q, np.int64)
    return q


def split_to_closed(Qs_L, Qc_L, n_split):
    """each vertex of the subdivided split copy -> its vertex of the subdivided closed cage (the same child quads, corner
    for corner); asserts the map is one-valued"""
    vm = -np.ones(n_split, np.int64)
    a, b = np.asarray(Qs_L).ravel(), np.asarray(Qc_L).ravel()
    vm[a] = b
    assert (vm[a] == b).all(), 'split_to_closed: a split vertex maps to two closed vertices'
    assert (vm >= 0).all(), 'split_to_closed: a split vertex in no child quad'
    return vm


def forge_leg_donor(spec, chain, legs, pair='fore', side='R', lam=1.0, low_levels=None, log=print):
    """THE DONOR FORGED FOR ITS SOCKET (the block comment above): the beetle's own generator on socket_chain(chain, pair,
    lam) for the segments from the tibia on, each segment's controls fitted and its L4 limit (the HIGH) as build_legs makes
    them, its SHIPPED LOW the closed cage subdivided low_levels[kind] levels with its vertices on the limit
    (subdiv_sharp.subdivide: the same child order subdivide_topology gives the split copy), the claws' b a rigid copy of
    a; the SLEEVES from the ankle on built by arthropod_cage.sleeve on the SHIPPED lows (the child's low section x
    in_child: hidden inside the drawn shell by construction); the knee sleeve on the cached femur's limit and the new
    tibia's (its exit X and the tibia's root: the author scale and the lip's station). legs: the cached legs
    (build_legs: the femur's limit). The right side the left mirrored (p_R = M p_L, quads reversed) before any
    subdivision, so the closed and the split copies subdivide from the same quads. Returns leg_donor's dict (life mm)
    with per segment cage = dict(V, Q, ctrl, sharp, rings, cap_interior) and V, Q the shipped low, plus chain, socket
    (socket_chain's info), teeth (kept, dropped)"""
    from . import subdiv_sharp as SS
    from .families import arthropod_cage as AC
    from .families import arthropod_parts as AP
    from .mesh import QuadMesh
    lv = dict(SOCKET_FORGE['low_levels'], **(low_levels or {}))
    c = pair[0]
    chain_m, info = socket_chain(chain, pair, lam)
    kn = AP.KNEE
    Pm = chain_m['pos']
    K_, J0 = np.asarray(Pm[f'tibia_{c}_L']), np.asarray(Pm[f'tarsus_1_{c}_L'])
    start = K_ + (kn['club_neck_in'] if kn['club'] else kn['neck_in']) * _unit(J0 - K_)
    L_t = float(np.linalg.norm(J0 - start))
    table = SOCKET_FORGE.get('teeth') or AP.FORE_TEETH     # (M2d: the socket's own irregular table; None: the beetle's)
    teeth, dropped = socket_teeth(L_t, table, AC.LAYOUT['tibia']['min_gap'], SOCKET_FORGE['tooth_shrink'])
    log(f'[socket forge] lam {lam:.4f}: the leg from the knee {info["life_len"]:.3f} -> {info["life_len_new"]:.3f} life mm, '
        f'the sub-leg turned {info["turn_deg"]:+.2f} deg about the knee; the tibia {L_t:.3f} mm from its neck: teeth kept '
        f'{len(teeth)} of {len(table)} (dropped {[d[0] for d in dropped]})')
    saved = AP.FORE_TEETH
    try:
        AP.FORE_TEETH = teeth                       # (the socket's tooth table, in memory only, restored below)
        clay = AC.clay_programs(spec, chain_m)
        cages = AC.leg_cages(spec, chain_m, clay, pair)
    finally:
        AP.FORE_TEETH = saved
    M = np.array([-1.0, 1.0, 1.0]) if side == 'R' else np.array([1.0, 1.0, 1.0])
    mir = side == 'R'
    out = dict(pair=pair, side=side, segs={}, sleeves=[], chain=chain_m, socket=info, teeth=(teeth, dropped))
    left = {}
    for nm in LEG_SEGS:
        if nm == 'claw_b':
            continue
        cg = cages[nm]
        lim, V0, res, mc, sh = AC.limit(cg)
        Qc = np.asarray(cg.Q, np.int64)
        used = np.zeros(len(cg.V), bool)
        used[Qc.ravel()] = True
        new = -np.ones(len(cg.V), np.int64)
        new[used] = np.arange(int(used.sum()))
        rings = new[np.asarray(cg.rings, np.int64)] if cg.rings is not None else None
        cq = cg.meta.get('cap_quads')
        cap_int = None if cq is None else [new[np.asarray(cq[e]['interior'], np.int64)].tolist() for e in (0, 1)]
        left[nm] = dict(T=mc.V, Q=np.asarray(mc.Q, np.int64), ctrl=V0[used], sharp=dict(sh), lim_V=lim.V,
                        lim_F=lim.tris(), spine=(cg.meta['spine'].P, cg.meta['spine'].N), rings=rings,
                        cap_interior=cap_int, kind=cg.kind, joint=cg.meta['joint'], parent=cg.meta['parent'],
                        res=float(res))
        log(f'[socket forge]   {nm}: cage {len(mc.Q)} quads, {len(sh)} creases, fit {res:.1e}, limit {len(lim.Q)} quads')
    # claw b: claw a under the rigid turn (build_legs' to_b)
    ca, cb = cages['claw_a'], cages['claw_b']
    Ra, Rb, J5 = ca.meta['R'], cb.meta['R'], ca.meta['joint_pt']
    to_b = lambda P: J5[None, :] + ((np.asarray(P) - J5[None, :]) @ Ra) @ Rb.T                # noqa: E731
    A_ = left['claw_a']
    left['claw_b'] = dict(A_, T=to_b(A_['T']), ctrl=to_b(A_['ctrl']), lim_V=to_b(A_['lim_V']),
                          spine=(to_b(A_['spine'][0]), A_['spine'][1] @ Ra @ Rb.T), copy_of='claw_a')
    # mirror (the right side), then the shipped lows from the (mirrored) cages
    for nm, s_ in left.items():
        Q = s_['Q'][:, ::-1].copy() if mir else s_['Q']
        lF = np.asarray(s_['lim_F'])[:, ::-1].copy() if mir else np.asarray(s_['lim_F'])
        P_, N_ = s_['spine']
        L = lv['tibia'] if nm == 'tibia' else (lv['claw'] if nm.startswith('claw') else lv['tarsus'])
        ctrl = s_['ctrl'] * M
        dense, _, parent, _ = SS.subdivide(QuadMesh(ctrl, Q), s_['sharp'], L)
        assert np.array_equal(np.asarray(dense.Q, np.int64), subdivide_topology(Q, L)), f'{nm}: subdivision order'
        out['segs'][nm] = dict(V=np.asarray(dense.V, np.float64), Q=np.asarray(dense.Q, np.int64), low_level=L,
                               low_parent=np.asarray(parent), lim_V=s_['lim_V'] * M, lim_F=lF,
                               cage=dict(V=s_['T'] * M, Q=Q, ctrl=ctrl, sharp=s_['sharp'], rings=s_['rings'],
                                         cap_interior=s_['cap_interior']),
                               sharp=s_['sharp'], spine=(P_ * M, N_ * M), joint=s_['joint'] + '_' + side,
                               parent=s_['parent'], rings=s_['rings'], kind=s_['kind'],
                               copy_of=s_.get('copy_of'), cap_interior=s_['cap_interior'], fit_res=s_.get('res'))
    # THE SLEEVES on the SHIPPED lows (left side: arthropod_cage.sleeve works in the beetle's own frame, then mirrored)
    Mi = np.array([-1.0, 1.0, 1.0]) if mir else np.array([1.0, 1.0, 1.0])
    low_L = {nm: (s_['V'] * Mi, (np.asarray(s_['Q'])[:, ::-1] if mir else np.asarray(s_['Q'])))
             for nm, s_ in out['segs'].items()}
    Q_ = {nm: AC.MeshQ(V, tris_of(Q)) for nm, (V, Q) in low_L.items()}
    chained = ['tibia', 'tarsus_1', 'tarsus_2', 'tarsus_3', 'tarsus_4', 'tarsus_5']
    for par, chd in list(zip(chained[:-1], chained[1:])) + [('tarsus_5', 'claw')]:
        if chd == 'claw':
            o = np.asarray(Pm[f'claw_{c}_L'])
            ta = _unit(left['claw_a']['spine'][0][1] - left['claw_a']['spine'][0][0])
            tb = _unit(left['claw_b']['spine'][0][1] - left['claw_b']['spine'][0][0])
            s_ = AC.sleeve(f'{pair} claws', o, _unit(ta + tb), Q_['tarsus_5'].sdf, Q_['claw_a'], child_extra=[Q_['claw_b']])
        else:
            sp_P = left[chd]['spine'][0]
            s_ = AC.sleeve(f'{pair} {par}-{chd}', sp_P[0], _unit(sp_P[1] - sp_P[0]), Q_[par].sdf, Q_[chd],
                           graft=(chd == 'tarsus_1'))
        V, Qs = (s_['V'] * Mi, s_['Q'][:, ::-1].copy()) if mir else (s_['V'], s_['Q'])
        pj = left[par]['joint'] + '_' + side
        cj = f'claw_{c}_{side}' if chd == 'claw' else left[chd]['joint'] + '_' + side
        out['sleeves'].append(dict(name=s_['name'], parent=par, child=chd, K=int(s_['K']), V=V, Q=Qs, parent_joint=pj,
                                   child_joint=cj, on='shipped lows', step=s_['step'], step_in=s_['step_in']))
    # the KNEE sleeve (not shipped: the collar is the knee): its exit X and the tibia's root, on the cached femur's limit
    # and the new tibia's limit (the root measure M2b's author scale used)
    fe = legs['pairs'][pair]['femur']
    fq = AC.MeshQ(fe['lim_V'], fe['lim_F'])
    tq = AC.MeshQ(left['tibia']['lim_V'], left['tibia']['lim_F'])
    sp_P = left['tibia']['spine'][0]
    kn_s = AC.sleeve(f'{pair} femur-tibia', sp_P[0], _unit(sp_P[1] - sp_P[0]), fq.sdf, tq, graft=True)
    out['knee_X'] = np.asarray(kn_s['X'], np.float64) * Mi
    out['tibia_root'] = AC.tibia_root([dict(kn_s, child='tibia')])
    # (M2d) THE ROOT MEASURED ON THE BEETLE'S OWN TOOTH TABLE. The socket's own table puts its first tooth at 0.190 of the
    # tibia (B3b's first at 0.31), close enough to the root that tibia_cage's rings there moved and the root measured 1.237
    # mm (M2c 1.247): the author scale went 24.410 -> 24.595 and lam 0.6433 -> 0.6400, so EVERY segment came out a little
    # different and G-R8 found tarsus 3 two vertices inside tarsus 4 in motion (m2d r3: seed 1 at rest and stepping; M2c's
    # glb on M2d's pose passes, r3's glb on M2c's pose fails: the geometry, not the pose). A tooth is a surface feature, so
    # the knee sleeve's exit and the root (the author scale, the lip's station, through them lam) are measured on the tibia
    # the beetle's own table makes (socket_teeth-filtered, as M2c built it); the shipped tibia keeps the socket's teeth and
    # the collar is built on it as before. None / False: measured on the shipped tibia (M2c's code path)
    if SOCKET_FORGE.get('teeth') and SOCKET_FORGE.get('measure_on_beetle_teeth', True):
        teeth0, _ = socket_teeth(L_t, AP.FORE_TEETH, AC.LAYOUT['tibia']['min_gap'], SOCKET_FORGE['tooth_shrink'])
        try:
            AP.FORE_TEETH = teeth0
            cg0 = AC.leg_cages(spec, chain_m, AC.clay_programs(spec, chain_m), pair)['tibia']
        finally:
            AP.FORE_TEETH = saved
        lim0 = AC.limit(cg0)[0]
        sp0 = cg0.meta['spine'].P
        kn0 = AC.sleeve(f'{pair} femur-tibia (the measure)', sp0[0], _unit(sp0[1] - sp0[0]), fq.sdf,
                        AC.MeshQ(lim0.V, lim0.tris()), graft=True)
        d_ship = out['tibia_root']['d_max']
        out['knee_X'] = np.asarray(kn0['X'], np.float64) * Mi
        out['tibia_root'] = AC.tibia_root([dict(kn0, child='tibia')])
        log(f'[socket forge] the root measured on the beetle\'s own teeth ({len(teeth0)} kept): d_max '
            f'{out["tibia_root"]["d_max"]:.4f} mm (the shipped tibia\'s {d_ship:.4f})')
    log(f'[socket forge] sleeves on the shipped lows: {[s_["child"] for s_ in out["sleeves"]]}; the tibia\'s root '
        f'{out["tibia_root"]["d_max"]:.4f} mm (d_max)')
    return out


def spine_station(P, u):
    """a spine's point and unit tangent at the arc share u"""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    x = float(np.clip(u, 0.0, 1.0)) * cum[-1]
    i = int(np.clip(np.searchsorted(cum, x) - 1, 0, len(P) - 2))
    w = (x - cum[i]) / max(cum[i + 1] - cum[i], 1e-300)
    return (1 - w) * P[i] + w * P[i + 1], _unit(P[i + 1] - P[i]), cum


def placement(rec, donor, z_lip, author_scale, ankle_R, u_lip=None):
    """THE RIGID MAP of the donor (life mm, the beetle's frame) into the socket: x_oct = O + R (s (x - P_lip)) + z_lip Z,
    s = author_scale 1e-3 (m per life mm). The tibia's ROOT AXIS (its spine from the knee to the lip's station) goes
    onto the ring's distal axis Z. Its ROLL about that axis keeps the tibia-tarsus-claw assembly the beetle's own and
    lays the leg in ONE vertical plane: the ankle's (tarsus_1's) bind frame, ankle_R (arthropod.skeleton: x along the
    bone, + about z folds the joint, the tarsomeres' fold side VENTRAL), its fold side goes to the arm's ORAL side (-Y),
    so every tarsal hinge lies horizontal across the arm (the ring frame's X) and the tarsus can lie flat with its
    claws hooked down, the leg's plane the vertical plane through the arm where the step solver works (BEETLE_PLAN
    §6.4). (The beetle's own knee folds toward its trochanter, nearly horizontally on the sprawled fore leg: 90 deg
    from its tarsal hinges. The femur and its condyles are not grafted; the collar is the knee, and graft_joints gives
    the graft knee a horizontal hinge in the leg's plane.) The lip's station P_lip (the knee sleeve's exit X by
    default: the tibia's section where it leaves the femur) at z_lip past the ring's centre. Returns dict(R, s, P_lip,
    T (life mm -> m, a callable), u_lip)"""
    P, N = donor['segs']['tibia']['spine']
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if u_lip is None:
        u_lip = float(cum[int(np.linalg.norm(P - donor['knee_X'][None], axis=1).argmin())] / cum[-1])
    P_lip, _, _ = spine_station(P, u_lip)
    t0 = _unit(P_lip - P[0])                            # the root axis: the knee to the lip's station
    fold = np.asarray(ankle_R, np.float64)[:, 1]         # the tarsomeres' fold side (ventral)
    fold = _unit(fold - t0 * float(fold @ t0))
    n0 = -fold                                          # its opposite -> the arm's aboral side (+Y)
    b0 = np.cross(n0, t0)                               # (b, n, t) right-handed as the ring's (X, Y, Z): X = Y x Z
    A = np.column_stack([b0, n0, t0])                   # donor (b, n, t) in the beetle frame
    O = np.asarray(rec['frame']['creature']['origin'], np.float64)
    Rr = np.asarray(rec['frame']['creature']['R'], np.float64)       # columns X, Y, Z
    B = np.column_stack([Rr[:, 0], Rr[:, 1], Rr[:, 2]])
    R = B @ A.T
    assert abs(np.linalg.det(R) - 1.0) < 1e-9
    s = float(author_scale) * 1e-3
    shift = O + z_lip * Rr[:, 2]

    def T(X):
        X = np.asarray(X, np.float64)
        return (X - P_lip) * s @ R.T + shift
    return dict(R=R, s=s, P_lip=P_lip, u_lip=u_lip, T=T, shift=shift, author_scale=float(author_scale), z_lip=z_lip)


def place_donor(donor, pl):
    """every segment's low and high, the sleeves and the spines in the octopus's creature frame (metres)"""
    out = {}
    for nm, s_ in donor['segs'].items():
        P, N = s_['spine']
        out[nm] = dict(s_, V=pl['T'](s_['V']), lim_V=pl['T'](s_['lim_V']), spine=(pl['T'](P), _unit(N @ pl['R'].T)))
        if 'cage' in s_:                                 # (M2c: the cage the shipped low subdivides, its islands' cuts)
            out[nm]['cage'] = dict(s_['cage'], V=pl['T'](s_['cage']['V']), ctrl=pl['T'](s_['cage']['ctrl']))
    sl = [dict(x, V=pl['T'](x['V'])) for x in donor['sleeves']]
    return out, sl


def tube_radius(Vt, Ft, origin, Rr, z, thetas):
    """the radius of a closed mesh (Vt, Ft) from the axis point origin + z Z along the directions theta in the frame
    (X, Y) (numpy ray-triangle, the outermost exit): (len(thetas),)"""
    X, Y, Z = Rr[:, 0], Rr[:, 1], Rr[:, 2]
    c = origin + z * Z
    D = np.cos(thetas)[:, None] * X[None] + np.sin(thetas)[:, None] * Y[None]
    A, B, C = Vt[Ft[:, 0]], Vt[Ft[:, 1]], Vt[Ft[:, 2]]
    e1, e2 = B - A, C - A
    out = np.full(len(D), np.nan)
    for i, d in enumerate(D):
        pv = np.cross(d, e2)
        det = (e1 * pv).sum(1)
        ok = np.abs(det) > 1e-18
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = c - A
        u = (tv * pv).sum(1) * inv
        qv = np.cross(tv, e1)
        v = (qv * d).sum(1) * inv
        t = (qv * e2).sum(1) * inv
        hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 0)
        if hit.any():
            out[i] = float(t[hit].max())
    return out


def tris_of(Q):
    Q = np.asarray(Q, np.int64)
    return np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])


# ============================================================================================ the collar
def collar(base, cage, rec, arms, tib, pl, opts=None, log=print):
    """THE COLLAR'S CAGE (module docstring) in the native cage's topology up to the native loop: rings ic - apron ..
    ic + 1 the base's own vertices (the apron baked, never shipped; the ring frozen; ic + 1 the native's first loop,
    w = 0), then the designed rings to the CREST, then the TUCK. tib: the placed tibia (V, Q: its low). Returns dict(V,
    Q, ring_no (cage ring number, designed rings ic + 2 ..), z (per ring, along the ring's Z from its centre), w (per
    ring), fixed (the base's vertices: apron, ring, native loop), cage_ids (-1 for designed vertices), copies, i0, ic,
    i_last, n_designed, crest, tuck, r_tib, theta)"""
    o = dict(SOCKET, **(opts or {}))
    rings = cage['rings']
    ic, apron = int(rec['ring_index']), int(rec['apron_rings'])
    L = base['low']
    copies = {}
    for i in range(base['n_low']):
        copies.setdefault(int(L['orig'][i]), []).append(i)
    O = np.asarray(rec['frame']['creature']['origin'], np.float64)
    Rr = np.asarray(rec['frame']['creature']['R'], np.float64)
    X, Y, Z = Rr[:, 0], Rr[:, 1], Rr[:, 2]
    K = int(rec['K'])
    th = TAU * np.arange(K) / K
    pos = lambda i: np.array([base['V32'][copies[int(c)][0]] for c in rings[i]]).astype(np.float64)
    nat = [pos(i) for i in range(ic - apron, ic + 2)]
    P1 = nat[-1]                                        # the native's first loop past the ring
    c1 = P1.mean(0)
    z1 = float((c1 - O) @ Z)
    # the native section at ic + 1 in the ring's frame about its own centre; its taper from ring ic to ic + 1
    loc1 = (P1 - c1) @ np.column_stack([X, Y])
    r_nat1 = np.hypot(loc1[:, 0], loc1[:, 1])
    P0 = nat[apron]
    r_nat0 = np.hypot(*((P0 - P0.mean(0)) @ np.column_stack([X, Y])).T)
    dr_dz = float((r_nat1.mean() - r_nat0.mean()) / max(z1, 1e-9))
    t_nat = _unit(c1 - P0.mean(0))
    bend_nat = float(np.degrees(np.arccos(np.clip(t_nat @ Z, -1, 1))))
    Vt, Ft = tib['V'], tris_of(tib['Q'])
    # the morph length from the native loop to the crest (the crest's radius from the tibia's at the lip): the C1
    # smoothstep's steepest slope is 1.5 x its mean, so 1.5 x the radius step over o['taper'] (the taper at the steepest
    # loop) and 1.5 x (the radius step plus the fold's relief) over o['lipschitz'] (§2.7's bound), the longer; at least
    # one ring step; z_crest = z1 + that length, the lip's station there
    zc0 = float(pl['z_lip'])
    # (M2c restart) the LIP LINE waves along the axis round the arm (lip_wave): the crest at zc0 + dz(theta_k), every
    # designed ring at the same share u_j of its own column from the native loop to the crest, the tuck tuck_dz past the
    # crest in each column (zc0 is the line's mean station; the prep puts it lip_dz past the taper's need)
    lip_dz, lip_seed = float(o.get('lip_dz', 0.0)), int(o.get('cuff_seed', 7))
    zc_k = zc0 + lip_wave(th, lip_dz, lip_seed)
    r_tib_c = np.array([tube_radius(Vt, Ft, O, Rr, float(zc_k[k]), th[k:k + 1])[0] for k in range(K)])
    assert np.isfinite(r_tib_c).all(), 'the axis misses the tibia at the lip'
    # (M2c) the crest's stand off the shell uneven round the arm (cuff_wave: lip_var of lip_t)
    r_crest = r_tib_c + o['lip_t'] * (1.0 + o.get('lip_var', 0.0) * cuff_wave(th, o.get('cuff_seed', 7)))
    r_nat_at = lambda z: r_nat1 + dr_dz * (z - z1)
    dr_max = float(np.max(np.abs(r_nat_at(zc_k) - r_crest)))
    fold_max = o['fold_a'] * (1.0 + o.get('fold_var', 0.0))          # (M2c: the folds swell to this)
    dz_need = 1.5 * max(dr_max / o['taper'], (dr_max + fold_max) / o['lipschitz'])
    n_m = max(1, int(math.ceil((zc0 - z1) / o['ring_step'])))
    rows, wz, zrow = [], [], []
    for j in range(1, n_m + 1):
        u = j / n_m
        w = float(smooth01(u))
        z = z1 + (zc_k - z1) * u                                           # (K,): each column's own station
        r = (1 - w) * r_nat_at(z) + w * r_crest
        c = (1 - w) * (c1[None] + (z - z1)[:, None] * t_nat[None]) + w * (O[None] + z[:, None] * Z[None])
        rows.append(c + r[:, None] * (np.cos(th)[:, None] * X[None] + np.sin(th)[:, None] * Y[None]))
        wz.append(w)
        zrow.append(z)
    z_tk = zc_k + o['tuck_dz']
    r_tib_t = np.array([tube_radius(Vt, Ft, O, Rr, float(z_tk[k]), th[k:k + 1])[0] for k in range(K)])
    r_tuck = r_tib_t - o['tuck']
    rows.append(O[None] + z_tk[:, None] * Z[None] + r_tuck[:, None] * (np.cos(th)[:, None] * X[None] +
                                                                       np.sin(th)[:, None] * Y[None]))
    wz.append(1.0)
    zrow.append(z_tk)
    z_t = float(np.mean(z_tk))
    n_d = len(rows)
    nat_n = len(nat)
    V = np.concatenate(nat + rows)
    n_r = nat_n + n_d
    ring_no = np.repeat(np.arange(ic - apron, ic - apron + n_r), K)
    cage_ids = np.concatenate([np.asarray(rings[i]) for i in range(ic - apron, ic + 2)] + [-np.ones(K * n_d, int)])
    # quads ring to ring in the native's winding (vertex k of every ring at the same standard angle: the base's rings
    # are the cage's, k by the cage's alpha; the designed rings at theta_k)
    kmap = np.asarray(cage['ring_k'])
    # the native rings' vertex order is the cage's; their k from the cage's alpha (ring_k is the cut ring's): every
    # native ring lists its vertices in the same k order (the cage builds rings that way), checked here
    def k_of(Pr, c):
        a = np.arctan2((Pr - c) @ Y, (Pr - c) @ X)
        return np.round(((a % TAU) / TAU) * K).astype(int) % K
    for j in range(nat_n):
        kk = k_of(nat[j], nat[j].mean(0))
        assert np.array_equal(kk, kmap), f'native ring {ic - apron + j}: its k order {kk} is not the cut ring\'s {kmap}'
    # reorder the designed rings to the native rings' vertex order (k by kmap)
    for j in range(n_d):
        blk = slice((nat_n + j) * K, (nat_n + j + 1) * K)
        V[blk] = V[blk][kmap]
    Q = []
    for j in range(n_r - 1):
        a, b = j * K, (j + 1) * K
        for m in range(K):
            Q.append((a + m, a + (m + 1) % K, b + (m + 1) % K, b + m))
    Q = np.array(Q, np.int64)
    # outward winding: the native's (its quads' normal against the radial)
    c_ = V[Q].mean(1)
    rad = c_ - (O + ((c_ - O) @ Z)[:, None] * Z[None])
    fn = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    if float(np.sum(np.einsum('ij,ij->i', fn[:K * (nat_n - 1)], rad[:K * (nat_n - 1)]))) < 0:
        Q = Q[:, ::-1].copy()
    fixed = np.zeros(len(V), bool)
    fixed[:nat_n * K] = True
    # (each designed ring's z: its columns' mean; the columns themselves in the report, theta_k order)
    z_r = np.array([float((Vr.mean(0) - O) @ Z) for Vr in nat] + [float(np.mean(zz)) for zz in zrow])
    w_r = np.array([0.0] * nat_n + wz)
    zc_min = float(zc_k.min())
    rep = dict(z1=z1, z_crest=zc0, z_tuck=z_t, dz_need=dz_need, morph=zc0 - z1, n_designed=n_d, dr_dz_native=dr_dz,
               bend_native_deg=bend_nat, r_nat1_mean=float(r_nat1.mean()), r_tib_crest=r_tib_c.tolist(),
               r_crest_mean=float(r_crest.mean()), taper_max=float(np.max(np.abs(r_nat_at(zc_k) - r_crest)) /
                                                                   max(zc_min - z1, 1e-9) * 1.5),
               lipschitz_est=float(1.5 * (dr_max + fold_max) / max(zc_min - z1, 1e-9)),
               lip_dz=lip_dz, lip_seed=lip_seed, z_crest_k=zc_k.tolist(), z_tuck_k=z_tk.tolist(),
               z_crest_min=zc_min, z_crest_max=float(zc_k.max()))
    log(f'[socket] collar: native loop at z {z1 * 1e3:.2f} mm (r {r_nat1.mean() * 1e3:.2f}, native taper '
        f'{dr_dz:+.4f}, its axis {bend_nat:.2f} deg off Z), the crest at z {zc0 * 1e3:.2f} mm (its line waving '
        f'{zc_min * 1e3:.2f}..{zc_k.max() * 1e3:.2f}; r {r_crest.mean() * 1e3:.2f} = the tibia {r_tib_c.mean() * 1e3:.2f} '
        f'+ {o["lip_t"] * 1e3:.1f}), the morph {(zc0 - z1) * 1e3:.2f} mm in {n_m} rings (the shortest column '
        f'{(zc_min - z1) * 1e3:.2f}; the taper needs {dz_need * 1e3:.2f}), the tuck at z {z_t * 1e3:.2f} mm r '
        f'{r_tuck.mean() * 1e3:.2f}')
    return dict(V=V, Q=Q, ring_no=ring_no, z=z_r, w=w_r, fixed=fixed, cage_ids=cage_ids, copies=copies, K=K,
                i0=ic - apron, ic=ic, nat_n=nat_n, n_designed=n_d, i_last=ic - apron + n_r - 1, crest=ic + 1 + n_m,
                tuck=ic + 1 + n_m + 1, theta=th, kmap=kmap, r_tib_crest=r_tib_c, r_tib_tuck=r_tib_t, report=rep,
                O=O, R=Rr)


def collar_weights(base, col, rec, root, graft_root, smooth_iters=3):
    """THE COLLAR'S WEIGHTS as (joint name -> column) over the collar's vertices: the apron and the ring the base's bits
    (frozen: §2.6's Dirichlet boundary); the native loop the base's with every weight on a dropped joint (the native
    group's arm0_09 ..) moved to the graft root arm0_08; the designed rings ramp from the native loop's pattern to
    arm0_08, then to the tibia's joint toward the lip (w_g = smooth01 over the morph's second half), the TUCK 100 % on
    the tibia's joint; smoothed with the base's rings, the native loop and the tuck pinned; at most 4 influences.
    Returns (names, W (n, len(names)))"""
    from . import rig as RG
    names = base['jnames']
    native = set(rec['native']['joints'])
    cols = []

    def col_of(nm):
        if nm not in cols:
            cols.append(nm)
        return cols.index(nm)
    K = col['K']
    n = len(col['V'])
    rows = [dict() for _ in range(n)]
    for i in range(col['nat_n'] * K):
        v = col['copies'][int(col['cage_ids'][i])][0]
        for q in range(4):
            w = float(base['W32'][v, q])
            if w > 0.0:
                nm = names[int(base['J'][v, q])]
                if nm in native:
                    assert i >= (col['nat_n'] - 1) * K, f'a base ring before the native loop weighted on {nm}'
                    nm = root
                rows[i][nm] = rows[i].get(nm, 0.0) + w
    nat_last = rows[(col['nat_n'] - 1) * K:col['nat_n'] * K]
    z = col['z']
    z1, zc = z[col['nat_n'] - 1], z[-2]
    for j in range(col['n_designed']):
        rj = col['nat_n'] + j
        u = (z[rj] - z1) / max(zc - z1, 1e-12)
        a = float(smooth01(u * 1.6))                       # the native loop's pattern fades over the first part
        g = 1.0 if j == col['n_designed'] - 1 else float(smooth01((u - 0.35) / 0.65)) * 0.85
        for k in range(K):
            d = {nm: (1 - a) * w for nm, w in nat_last[k].items()}
            d[root] = d.get(root, 0.0) + a * (1 - g)
            d[graft_root] = d.get(graft_root, 0.0) + a * g
            rows[rj * K + k] = d
    for r in rows:
        for nm in r:
            col_of(nm)
    W = np.zeros((n, len(cols)))
    for i, r in enumerate(rows):
        for nm, w in r.items():
            W[i, cols.index(nm)] += w
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    pin = np.zeros(n, bool)
    pin[:col['nat_n'] * K] = True
    pin[(col['nat_n'] + col['n_designed'] - 1) * K:] = True          # the tuck
    W0 = W.copy()
    W = RG.smooth_field(W, col['Q'], iters=smooth_iters, alpha=0.5, pinned=np.nonzero(pin)[0])
    J4, W4 = RG.limit_influences(W, 4)
    Wd = np.zeros_like(W)
    np.put_along_axis(Wd, J4.astype(np.int64), W4.astype(np.float64), axis=1)
    Wd[pin] = W0[pin]
    return cols, Wd


def ring_suckers(I, rec, col, margin=0.0005, reach=0.55):
    """the suckers ROOTED PAST THE RING that the part keeps (re-made on it): every one whose footprint CROSSES the ring
    (the base's skin under it is baked black: the canonical's own texels, never re-baked, would show on the base's side
    the moment the sucker went), and every one whose footprint ends by the native loop (+ margin: w is ~0 there, the
    band the native's own surface, so the base's sucker sits on it). The footprint: the root +- reach x its diameter
    along the axis (measured on the base's sucker primitive: 0.52-0.53 d; p04_suckers.py). I: octopus_suckers'
    instances (p, d, arm, s). Returns a bool mask over the instances"""
    jn = int(rec['chain'][3:])
    z = (np.asarray(I['p'], np.float64) - col['O']) @ col['R'][:, 2]
    d = np.asarray(I['d'], np.float64)
    past = (np.asarray(I['arm']) == jn) & (np.asarray(I['s']) > rec['st_s'])
    return past & ((z - reach * d < 0.0) | (z + reach * d < col['report']['z1'] + margin))


def morph_values(q, col, tib=None, opts=None):
    """THE FIELD MORPH's inputs (§2.7: f = mix(f_native, f_collar, w), then relevelled; the field-blend kernel M1 left
    to M1b) at points q in the socket frame (x, y along the ring frame's X, Y; z along Z from the ring's centre):
      w         C1 in z (smoothstep: zero slope at both ends) from the native loop (z1: the band is the native over
                [0, h]) to the crest (w = 1 beyond: the native arm past the collar is gone)
      f_collar  the MEMBRANE: a tube at the crest ring's radii (the tibia's section at the lip plus the lip's stand),
                two soft transverse FOLD ridges in the morph's second half (the `membrane` dressing, §2.10: fold_a and
                0.7 fold_a, width fold_s), closed by the LIP: a smooth max with the plane z = z_tuck (radius 1.4 lip_t),
                the membrane's rim rolled onto the shell (the cap lies inside the tibia: never baked, never seen); (M2c
                restart) z_crest and z_tuck each column's own, the lip line's wave (lip_wave)
    The blended zero set is then the radius interpolation (1 - w) r_native + w r_crest the low's designed rings take.
    Returns dict(w, f, lipschitz (|dw/dz| max x the largest |f_native - f_collar| near the surface, from the radii))"""
    o = dict(SOCKET, **(opts or {}))
    q = np.asarray(q, np.float64)
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    rep = col['report']
    z1, zc, zt = rep['z1'], rep['z_crest'], rep['z_tuck']
    rho = np.hypot(x, y)
    th = np.arctan2(y, x) % TAU
    # (M2c restart) THE LIP LINE'S WAVE: each column's own crest and tuck (the collar's report: lip_dz, its seed), the
    # morph's w by the column's own length, the folds at shares of it
    dzl = lip_wave(th, rep.get('lip_dz', 0.0), rep.get('lip_seed', 7))
    zc_t, zt_t = zc + dzl, zt + dzl
    w = smooth01((z - z1) / (zc_t - z1))
    K = col['K']
    j = col['nat_n'] + col['n_designed'] - 2               # the crest ring
    Vr = col['V'][j * K:(j + 1) * K]
    loc = (Vr - col['O']) @ col['R']
    tk = np.arctan2(loc[:, 1], loc[:, 0]) % TAU
    rk = np.hypot(loc[:, 0], loc[:, 1])
    rk0 = rk.copy()                                        # (k order: the native loop's vertex k at the same angle)
    srt = np.argsort(tk)
    tk, rk = tk[srt], rk[srt]
    r_th = np.interp(th, np.concatenate([tk - TAU, tk, tk + TAU]), np.concatenate([rk, rk, rk]))
    # (M2c) the folds WANDER along the axis round the arm and swell and fade (cuff_wave, two seeds each): a tissue's
    # folds, not two machined ribs
    sd = int(o.get('cuff_seed', 7))
    wz, wv = o.get('fold_wander', 0.0) * (zc_t - z1), o.get('fold_var', 0.0)
    zf1 = z1 + 0.55 * (zc_t - z1) + wz * cuff_wave(th, sd + 1)
    zf2 = z1 + 0.85 * (zc_t - z1) + wz * cuff_wave(th, sd + 2)
    a1 = o['fold_a'] * (1.0 + wv * cuff_wave(th, sd + 3))
    a2 = 0.7 * o['fold_a'] * (1.0 + wv * cuff_wave(th, sd + 4))
    fold = a1 * np.exp(-((z - zf1) / o['fold_s']) ** 2) + a2 * np.exp(-((z - zf2) / o['fold_s']) ** 2)
    a = rho - (r_th + fold)
    b = z - zt_t
    k = o.get('roll_k', 1.4) * o['lip_t']
    m = np.maximum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    f = m + h * h * k * 0.25
    # the Lipschitz estimate: smoothstep's slope peaks at 1.5 / (zc - z1) (the SHORTEST column's, M2c restart); |f_native
    # - f_collar| near the surface is the radius difference (the native loop's radii against the crest's) plus the fold
    rn = np.hypot(*(((col['V'][(col['nat_n'] - 1) * K:col['nat_n'] * K] - col['O']) @ col['R'])[:, :2]).T)
    lip = 1.5 / (rep.get('z_crest_min', zc) - z1) * (float(np.max(np.abs(rn - rk0))) + o['fold_a'] * (1.0 + wv))
    return dict(w=w, f=f, lipschitz=float(lip))


def graft_joints(spec, chain, donor, pl, base, root, rec, stem='arm0', side='R'):
    """the GRAFT JOINTS (§4.2: <stem>_g<kk>): the tibia (the graft KNEE: at the beetle's knee point, inside the
    collar), tarsus_1..5, the claw joint. The tarsal and claw joints keep the beetle's own bind frames (arthropod.skeleton
    at the author scale: x along the bone to its child, a positive turn about z folds the joint anatomically; the right
    side's frames as the beetle's right is built) carried by the placement's rotation. The graft knee's frame is the
    socket's: x from the knee to the ankle, z the ring frame's X made perpendicular (the hinge horizontal across the
    arm, in the leg's plane: placement's roll), y = z x x (+ about z folds the tibia toward the oral side, -Y).
    Returns [dict(name, role, beetle, parent, world)] parent-first, and {beetle joint: graft name}"""
    from .families import arthropod as AR
    sk = AR.skeleton(spec, chain, scale=pl['s'])
    c = donor['pair'][0]
    roles = ['tibia'] + [f'tarsus_{n}' for n in range(1, 6)] + ['claw']
    bnames = [f'{r}_{c}_{side}' for r in roles]
    out, gmap = [], {}
    Xr = np.asarray(rec['frame']['creature']['R'], np.float64)[:, 0]
    for k, (r, bn) in enumerate(zip(roles, bnames)):
        Wb = sk.world[sk.index(bn)]
        Rb, pb = Wb[:3, :3], Wb[:3, 3] / pl['s']           # (life mm)
        W = np.eye(4)
        W[:3, :3] = pl['R'] @ Rb
        W[:3, 3] = pl['T'](pb[None])[0]
        if k == 0:
            pa = pl['T']((sk.world[sk.index(bnames[1])][:3, 3] / pl['s'])[None])[0]
            x = _unit(pa - W[:3, 3])
            z = _unit(Xr - x * float(Xr @ x))
            W[:3, :3] = np.column_stack([x, np.cross(z, x), z])
        nm = f'{stem}_g{9 + k:02d}'
        out.append(dict(name=nm, role=r, beetle=bn, parent=root if k == 0 else out[-1]['name'], world=W,
                        fold_axis=W[:3, 2].tolist()))
        gmap[bn] = nm
    return out, gmap


# ============================================================================================ M2d: the tarsal setae
# (M2d, the lead's call 3: at macro range the tarsal brush read as flat khaki paint with a dithered edge: M2c's setae were
# colour and sheen only, the beetle's own T tier, "fringe cards later", BEETLE_PLAN §5.4) THE TARSAL SETAE AS HAIRS, as the
# stag beetle's tarsi carry them (BEETLE_BODY_PHOTOS' sources, read for this: c07, the MHNT male's ventral view, its tarsi
# 1-4 each with a golden setal PAD on the ventral face, densest toward the tarsomere's distal lobe, tarsus 5 with a ventral
# LINE of them, two longer setae on the empodium between the claws; M1d's dorsal tarsi, pale setae tips standing past each
# tarsomere's distal-ventral end, the setae lying distally). Each seta a thin tapered tube of three-sided rings (base sunk
# into the shell: never floating; mid; near the tip) closed at a tip vertex, rooted on the SHIPPED low's ventral face,
# leaning distally off the surface and bending further along the tarsus near its tip; its length and lean drawn per seta
# (seeded), its density the painted brush's own coverage (the part's masks G there: the cuticle pass's setae layout, so
# the hairs stand where the brush is painted) times a distal ramp, thinned to a minimum spacing. Sizes at the AUTHOR scale
# (a cuticle feature keeps its size as the teeth and lobes do, forge_leg_donor): the brushes' setae 0.11-0.22 mm long and
# ~7 um thick at life (c07 / M1d: shorter than a tarsomere's width) -> 2.6-5.5 mm, 0.17 mm thick at the base. Rigid on
# their tarsomere's joint (one influence: they ride the shell they grow on); their UVs all on ONE small strip of the part's
# atlas (stacked: Skye's rule, repeats share texels), painted base to tip by the chain's setae stage (m2d_setae.py)
TARSAL_SETAE = dict(
    pads=dict(s=(0.20, 0.97), cos_ventral=0.47, spacing=0.00042, length=(0.0013, 0.0029), distal_gain=0.45),
    line=dict(s=(0.10, 0.92), cos_ventral=0.82, spacing=0.0008, length=(0.0014, 0.0028), distal_gain=0.20),
    empodium=dict(n=2, length=0.014, splay_deg=9.0, r0=0.00010),
    r0=0.000085, r_tip=0.000018, sink=0.00015, lean=(0.55, 0.85), jitter_deg=14.0, bend_deg=(8.0, 22.0),
    rings=(0.0, 0.5, 0.86), seed=23,
    # (the dry run on M2c's build, m2d/runs/setae_try: at 2.6-5.5 mm, leaning 0.55-0.80 off the surface, the brushes read
    # as long streaming hair; c07's pads are a short dense felt, M1d's setae standing past each tarsomere's distal-ventral
    # end the longest) shorter and denser, more upright, the length rising toward each tarsomere's distal end:
    # x (len_base + len_distal s^3). (M2d r1 in the engine, m2d/look/r1/t15_crop.png, t12_crop.png: golden hairs, from below
    # a little sparse and combed flat along the tarsus) the pads 0.62 -> 0.54 mm apart, the tips bending 8-22 deg (15-32).
    # (M2d r4, LOOKED beside c07's fore and hind tarsi: m2d/look/r3_setae_vs_c07.png: r3's pads read as separate copper
    # hairs over the dark cuticle, where c07's are a dense golden FELT lying on the ventral face, the cuticle hidden under
    # it) the pads 0.54 -> 0.42 mm apart (x1.65 the hairs), x0.8 shorter, lying flatter (lean 0.80-1.10 -> 0.55-0.85: 29-40
    # deg off the surface, from 39-48), tarsus 5's line 1.1 -> 0.8 mm apart
    len_base=0.70, len_distal=0.80)


def tarsal_setae(pieces, coverage_at, opts=None, log=print):
    """THE TARSAL SETAE (the block comment above). pieces: [dict(name, kind 'pads' | 'line', V (n, 3), F (m, 3), N (n, 3),
    UV (n, 2), joint (its name), frame (4 x 4: the tarsomere's bind joint, x along the bone, +y its fold side, ventral),
    length (m: to the next joint), claws (for tarsus 5: the claw joint's world point and the two claws' tips, for the
    empodium) )], coverage_at(uv (k, 2)) -> the painted brush's coverage (k,) in [0, 1]. Returns dict(V, N, TAN (n, 4),
    F, T (each vertex's share along its seta, 0 base .. 1 tip), J (joint names per vertex), roots, counts)"""
    o = dict(TARSAL_SETAE, **(opts or {}))
    rng = np.random.default_rng(int(o['seed']))
    Vs, Ns, Ts, Fs, Tt, Js, roots, counts = [], [], [], [], [], [], [], {}
    nv = 0

    def perp(d):
        # a unit vector perpendicular to d (the least aligned world axis crossed with it)
        e = np.eye(3)[int(np.argmin(np.abs(d)))]
        return _unit(np.cross(d, e))

    def one(root, n_s, x_d, L, joint, r0):
        nonlocal nv
        # the seta's centreline: from the root (sunk along -n) leaning distally, bending further toward x_d by bend
        lean = rng.uniform(*o['lean'])
        cx = np.cross(n_s, x_d)
        tang = _unit(cx) if np.linalg.norm(cx) > 1e-6 else perp(_unit(x_d))
        jit = math.radians(o['jitter_deg'])
        d0 = _unit(lean * n_s + x_d + rng.normal(0.0, jit) * tang + rng.normal(0.0, 0.5 * jit) * n_s)
        bend = math.radians(rng.uniform(*o['bend_deg']))
        axis = _unit(np.cross(d0, x_d)) if np.linalg.norm(np.cross(d0, x_d)) > 1e-6 else tang
        ts = list(o['rings']) + [1.0]
        pts, dirs = [], []
        p = root - o['sink'] * n_s
        last_t = 0.0
        for t in ts:
            dt_ = t - last_t
            dcur = _rodrigues(axis, bend * last_t) @ d0
            p = p + dcur * L * dt_ if t > 0 else p
            pts.append(p.copy())
            dirs.append(_rodrigues(axis, bend * t) @ d0)
            last_t = t
        e1 = _unit(np.cross(dirs[0], n_s)) if np.linalg.norm(np.cross(dirs[0], n_s)) > 1e-6 else perp(_unit(dirs[0]))
        V_, N_, T_ = [], [], []
        for k, t in enumerate(ts[:-1]):
            dk = _unit(dirs[k])
            a1 = _unit(e1 - dk * float(e1 @ dk))
            a2 = np.cross(dk, a1)
            r = r0 * (1.0 - (1.0 - o['r_tip'] / r0) * min(t / ts[-2], 1.0) ** 0.8) if t > 0 else r0
            for j in range(3):
                ang = TAU * j / 3.0
                rad = math.cos(ang) * a1 + math.sin(ang) * a2
                V_.append(pts[k] + r * rad)
                N_.append(_unit(rad + 0.12 * dk))
                T_.append(np.append(dk, 1.0))
        V_.append(pts[-1])
        N_.append(_unit(dirs[-1]))
        T_.append(np.append(_unit(np.cross(a1, dirs[-1])), 1.0))
        F_ = []
        for k in range(len(ts) - 2):
            for j in range(3):
                a, b = k * 3 + j, k * 3 + (j + 1) % 3
                c, d = (k + 1) * 3 + (j + 1) % 3, (k + 1) * 3 + j
                F_ += [(a, b, c), (a, c, d)]
        tipi = 3 * (len(ts) - 1)
        k = len(ts) - 2
        for j in range(3):
            F_.append((k * 3 + j, k * 3 + (j + 1) % 3, tipi))
        Vs.append(np.array(V_))
        Ns.append(np.array(N_))
        Ts.append(np.array(T_))
        Fs.append(np.array(F_, np.int64) + nv)
        Tt.append(np.array([t for t in ts[:-1] for _ in range(3)] + [1.0]))
        Js.extend([joint] * len(V_))
        roots.append(root)
        nv += len(V_)

    for pc in pieces:
        kind = pc['kind']
        ko = o[kind]
        V, F, N, UV = (np.asarray(pc[k], np.float64) for k in ('V', 'F', 'N', 'UV'))
        F = np.asarray(F, np.int64)
        W = np.asarray(pc['frame'], np.float64)
        p0, x_ax, y_v = W[:3, 3], _unit(W[:3, 0]), _unit(W[:3, 1])
        a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
        area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        n_tri = _unit(np.cross(b - a, c - a))
        # outward: the triangle normal against the vertex normals' mean (the low's winding is outward; checked)
        n_tri = np.where(((n_tri * N[F].mean(1)).sum(1) < 0)[:, None], -n_tri, n_tri)
        # candidates: area-weighted samples, 6 per spacing^2 of the ventral area
        ven = (n_tri @ y_v) > ko['cos_ventral']
        s_tri = (((a + b + c) / 3.0 - p0) @ x_ax) / float(pc['length'])
        ok = ven & (s_tri >= ko['s'][0] - 0.05) & (s_tri <= ko['s'][1] + 0.05)
        A_ok = float(area[ok].sum())
        n_c = int(6.0 * A_ok / ko['spacing'] ** 2) + 1
        if not ok.any():
            counts[pc['name']] = 0
            continue
        pr = area * ok
        tri = rng.choice(len(F), size=n_c, p=pr / pr.sum())
        u_, v_ = rng.random(n_c), rng.random(n_c)
        flip = u_ + v_ > 1.0
        u_[flip], v_[flip] = 1.0 - u_[flip], 1.0 - v_[flip]
        w0 = 1.0 - u_ - v_
        P = w0[:, None] * a[tri] + u_[:, None] * b[tri] + v_[:, None] * c[tri]
        uv = (w0[:, None] * UV[F[tri, 0]] + u_[:, None] * UV[F[tri, 1]] + v_[:, None] * UV[F[tri, 2]])
        nP = n_tri[tri]
        sP = ((P - p0) @ x_ax) / float(pc['length'])
        keep = (sP >= ko['s'][0]) & (sP <= ko['s'][1]) & ((nP @ y_v) > ko['cos_ventral'])
        cov = np.clip(coverage_at(uv), 0.0, 1.0)
        dens = cov * (1.0 - ko['distal_gain'] + ko['distal_gain'] * np.clip((sP - ko['s'][0]) /
                                                                             max(ko['s'][1] - ko['s'][0], 1e-6), 0, 1))
        keep &= rng.random(n_c) < np.clip(dens, 0.0, 1.0)
        idx = np.nonzero(keep)[0]
        # Poisson thinning: the candidates in random order, each kept if no kept root lies within the spacing
        rng.shuffle(idx)
        kept, pts_k = [], []
        for i in idx:
            if pts_k and np.min(np.linalg.norm(np.asarray(pts_k) - P[i], axis=1)) < ko['spacing']:
                continue
            kept.append(i)
            pts_k.append(P[i])
        for i in kept:
            L0, L1 = ko['length']
            Ls = (L0 + (L1 - L0) * rng.random() ** 1.3) * (o['len_base'] + o['len_distal'] *
                                                             float(np.clip(sP[i], 0, 1)) ** 3)
            one(P[i], nP[i], x_ax, Ls, pc['joint'], o['r0'])
        counts[pc['name']] = len(kept)
        if pc.get('claws') is not None:
            # THE EMPODIUM's two setae: from tarsus 5's end, between the claws, pointing between their tips
            eo = o['empodium']
            cj, ta, tb = (np.asarray(v, np.float64) for v in pc['claws'])
            mid = 0.5 * (ta + tb)
            dmid = _unit(mid - cj)
            side = _unit(ta - tb)
            for k in range(int(eo['n'])):
                sgn = -1.0 if k == 0 else 1.0
                dk = _unit(dmid + math.tan(math.radians(eo['splay_deg'])) * sgn * side)
                one(cj - 0.002 * x_ax, _unit(dk - x_ax * 0.0), dk, eo['length'], pc['joint'], eo['r0'])
            counts['empodium'] = int(eo['n'])
    V = np.concatenate(Vs)
    out = dict(V=V, N=np.concatenate(Ns), TAN=np.concatenate(Ts), F=np.concatenate(Fs), T=np.concatenate(Tt),
               J=np.array(Js, object), roots=np.array(roots), counts=counts)
    log(f'[setae] {sum(v for k, v in counts.items())} setae ({counts}): {len(V)} vertices, {len(out["F"])} triangles')
    return out


# ============================================================================================ islands and the atlas
def lscm_pinned(P, F, pin, pin_uv):
    """the least-squares conformal map (uv.lscm's construction) with MANY pinned vertices (Dirichlet data): pin (m,)
    vertex ids, pin_uv (m, 2) their fixed coordinates; the free vertices solve the conformal energy over every
    triangle. Returns UV (n, 2)"""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    n = len(P)
    p0, p1, p2 = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    x = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-20)
    nrm = np.cross(e1, e2)
    a2 = np.linalg.norm(nrm, axis=1)
    z = nrm / np.maximum(a2[:, None], 1e-20)
    y = np.cross(z, x)
    q = np.zeros((len(F), 3, 2))
    q[:, 1, 0] = np.linalg.norm(e1, axis=1)
    q[:, 2, 0] = (e2 * x).sum(1)
    q[:, 2, 1] = (e2 * y).sum(1)
    s = np.sqrt(np.maximum(a2, 1e-30))
    Wr, Wi = np.zeros((len(F), 3)), np.zeros((len(F), 3))
    for j in range(3):
        k, l_ = (j + 1) % 3, (j + 2) % 3
        Wr[:, j] = (q[:, l_, 0] - q[:, k, 0]) / s
        Wi[:, j] = (q[:, l_, 1] - q[:, k, 1]) / s
    pin = np.asarray(pin, np.int64)
    fixed = np.zeros(n, bool)
    fixed[pin] = True
    puv = np.zeros((n, 2))
    puv[pin] = pin_uv
    fidx = -np.ones(n, np.int64)
    fidx[~fixed] = np.arange(int((~fixed).sum()))
    nf = int((~fixed).sum())
    rows, cols, vals = [], [], []
    br = np.zeros(2 * len(F))
    t = np.arange(len(F))
    for j in range(3):
        vj = F[:, j]
        for (off, wr, wi) in ((0, Wr[:, j], -Wi[:, j]), (len(F), Wi[:, j], Wr[:, j])):
            fr = fidx[vj]
            m = fr >= 0
            rows += list(t[m] + off) + list(t[m] + off)
            cols += list(fr[m]) + list(fr[m] + nf)
            vals += list(wr[m]) + list(wi[m])
            mp = ~m
            br[t[mp] + off] -= wr[mp] * puv[vj[mp], 0] + wi[mp] * puv[vj[mp], 1]
    A = sp.csr_matrix((vals, (rows, cols)), shape=(2 * len(F), 2 * nf))
    sol = spla.lsqr(A, br, atol=1e-14, btol=1e-14, iter_lim=50000)[0]
    UV = puv.copy()
    UV[~fixed, 0] = sol[:nf]
    UV[~fixed, 1] = sol[nf:]
    return UV


def collar_uv(base, col, rec):
    """THE COLLAR'S ISLAND on the BASE'S LATTICE: the collar's quads split along the arm's oral seam (vertex seam_k of
    every ring, octopus_uv's hidden line: graft.part_islands' rule), the native quads' corners the base low's own
    vertices (graft.strip_base_corners: the split copy on the quad's side of the seam) at the base set's UVs (texels of
    its 1280 set), and the designed rings' vertices continued by the conformal map with every native vertex PINNED
    (lscm_pinned: the conformal continuation M1's check left to M1b). Returns dict(Vn, Qn, orig, T (texels in the base
    set's frame, v up), base_v {split vertex: base low vertex}, native_q, seam)"""
    from . import graft as GF
    from . import uv as U
    K, sk = col['K'], int(rec['seam_k'][0])
    nr = len(col['V']) // K
    seams = [(j * K + sk, (j + 1) * K + sk) for j in range(nr - 1)]
    lab = U.islands(col['Q'], seams)
    assert lab.max() == 0, 'the collar is one island'
    Vn, Qn, orig = U.split(col['V'], col['Q'], lab, seams)
    rq = col['ring_no'][col['Q']]
    native_q = np.nonzero(rq.max(1) <= col['ic'] + 1)[0]
    part = dict(cage_ids=col['cage_ids'])
    bc = GF.strip_base_corners(base, part, Qn, orig, native_q)
    S = int(rec['set_size'])
    pin = np.array(sorted(bc))
    bv = np.array([bc[v] for v in pin])
    T_pin = base['low']['UV'][bv] * S
    F = U._tri(Qn)
    T = lscm_pinned(Vn, F, pin, T_pin)
    d1, d2 = T[F[:, 1]] - T[F[:, 0]], T[F[:, 2]] - T[F[:, 0]]
    cr = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    return dict(Vn=Vn, Qn=Qn, orig=orig, T=T, base_v=dict(zip(pin.tolist(), bv.tolist())), native_q=native_q,
                seam=seams, flipped=int((cr <= 0).sum()), F=F)


def unwrap_island(P, F, arap_iters=8):
    """one island: LSCM, then the ARAP depth whose worst-direction footprint is smallest among those that do not fold
    (graft.unwrap_part's rule, octopus_uv's), counter-clockwise, turned to its smallest bounding box. Returns (uv in
    metres-like units, footprint p95, ARAP depth)"""
    from . import uv as U
    uv = U.lscm(P, F)
    best, cand, done = None, uv, 0
    for it in (0, 2, max(arap_iters // 2, 3), arap_iters):
        if it > done:
            cand, done = U.arap(P, F, cand, it - done), it
        if U.self_overlap(cand, F):
            continue
        fp = U.footprint(P, F, cand)
        if best is None or fp < best[0]:
            best = (fp, it, cand)
    if best is None:
        best = (U.footprint(P, F, uv), 0, uv)
    uv = best[2]
    d1, d2 = uv[F[:, 1]] - uv[F[:, 0]], uv[F[:, 2]] - uv[F[:, 0]]
    if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
        uv[:, 0] = -uv[:, 0]
    ba, bar = 0.0, None
    for a in np.radians(np.arange(0.0, 90.0, 0.5)):
        c_, s_ = np.cos(a), np.sin(a)
        rt = uv @ np.array([[c_, -s_], [s_, c_]])
        ar = float(np.ptp(rt[:, 0]) * np.ptp(rt[:, 1]))
        if bar is None or ar < bar - 1e-15:
            ba, bar = a, ar
    c_, s_ = np.cos(ba), np.sin(ba)
    return uv @ np.array([[c_, -s_], [s_, c_]]), float(best[0]), int(best[1])


def column_seam(V, rings, side_dir):
    """a tube's longitudinal seam: the ring column k whose vertices point most along side_dir from each ring's centre
    (the hidden side), as edges ring j -> j + 1; returns (edges, k)"""
    R = np.asarray(rings)
    best = None
    for k in range(R.shape[1]):
        d = np.mean([float(_unit(V[R[j, k]] - V[R[j]].mean(0)) @ side_dir) for j in range(len(R))])
        if best is None or d > best[0]:
            best = (d, k)
    k = best[1]
    return [(int(R[j, k]), int(R[j + 1, k])) for j in range(len(R) - 1)], k


def ring_loop(ring):
    r = list(np.asarray(ring).tolist())
    return [(r[m], r[(m + 1) % len(r)]) for m in range(len(r))]


def feature_cuts(Q, rings, cap_interior):
    """the tibia's EXTRUDED FEATURES (arthropod_cage.extrude: the teeth and the spur, added after the shaft's rings and
    caps; the cache keeps no base loops) recovered from the topology: the vertices in no shaft ring and in neither
    cap's interior (the cage's own lists, cap_interior) are the features'; their quads, grouped by shared feature
    vertices, one feature each (the fore tibia's inner spur stands on two of the apex cap's quads); its seam the edges
    its quads share with the rest. Returns (list of quad index arrays, seam edges)"""
    Q = np.asarray(Q, np.int64)
    R = np.asarray(rings)
    in_ring = np.zeros(int(Q.max()) + 1, bool)
    in_ring[R.ravel()] = True
    cap_v = set(int(v) for e in cap_interior for v in e)
    feat_v = np.array([v for v in range(len(in_ring)) if not in_ring[v] and v not in cap_v], np.int64)
    fv = np.zeros(len(in_ring), bool)
    fv[feat_v] = True
    fq = np.nonzero(fv[Q].any(1))[0]
    # group by shared FEATURE vertices (two teeth share none)
    parent = {int(q): int(q) for q in fq}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    owner = {}
    for q in fq:
        for v in Q[q]:
            if fv[v]:
                if v in owner:
                    ra, rb = find(int(q)), find(owner[v])
                    if ra != rb:
                        parent[ra] = rb
                else:
                    owner[int(v)] = int(q)
    groups = {}
    for q in fq:
        groups.setdefault(find(int(q)), []).append(int(q))
    feats = [np.array(sorted(g)) for g in groups.values()]
    # seams: the edges of feature quads also used by a non-feature quad
    isf = np.zeros(len(Q), bool)
    isf[fq] = True
    edges = {}
    for qi, q in enumerate(Q.tolist()):
        for m in range(4):
            e = (min(q[m], q[(m + 1) % 4]), max(q[m], q[(m + 1) % 4]))
            edges.setdefault(e, []).append(qi)
    seams = [e for e, qs in edges.items() if len(qs) == 2 and isf[qs[0]] != isf[qs[1]]]
    # each feature SLIT from its base to its tip along its first template column (extrude adds ring 1's nb vertices,
    # then ring 2's, in the template's order): a closed cup unrolled whole compressed its tip (footprint p95 3-45, v3)
    for f in feats:
        fvs = sorted({int(v) for v in Q[f].ravel() if fv[v]})
        nb = len(fvs) // 2
        r1, r2 = fvs[:nb], fvs[nb:2 * nb]
        nbr = set()
        for q in Q[f].tolist():
            for m in range(4):
                a, b = q[m], q[(m + 1) % 4]
                if a == r1[0] and not fv[b]:
                    nbr.add(b)
                if b == r1[0] and not fv[a]:
                    nbr.add(a)
        if len(nbr) == 1:
            b0 = nbr.pop()
            seams += [(min(b0, r1[0]), max(b0, r1[0])), (min(r1[0], r2[0]), max(r1[0], r2[0]))]
    return feats, seams


def pack_fft(collar_mask, collar_loc0, isl_T, isl_F, pad=8, align=16, sizes=range(512, 4097, 32), log=print):
    """THE ATLAS: the COLLAR first, at the lowest-leftmost slot whose offset from the base's texels is a whole number
    of `align` texels (its mask collar_mask (h, w) from texel collar_loc0 in the base's frame), then every other island
    (isl_T: texel coordinates from 0, isl_F their triangles) largest first at the lowest free spot in either
    orientation (0 / 90 deg), found by an FFT overlap test against the padded occupancy. sizes: square sizes tried in
    order. Returns (size, collar offset (2,), {i: placed texels})"""
    from scipy import ndimage
    from scipy.signal import fftconvolve
    from . import graft as GF
    order = sorted(range(len(isl_T)), key=lambda i: -float(np.ptp(isl_T[i][:, 0]) * np.ptp(isl_T[i][:, 1])))
    masks = {}
    for i in order:
        for rot in (0, 1):
            T = isl_T[i] if rot == 0 else np.column_stack([isl_T[i][:, 1], np.ptp(isl_T[i][:, 0]) - isl_T[i][:, 0]])
            T = T - T.min(0) + pad
            w, h = int(np.ceil(T[:, 0].max())) + pad + 1, int(np.ceil(T[:, 1].max())) + pad + 1
            m = GF.raster_mask(T, isl_F[i], (h, w))
            md = ndimage.binary_dilation(m, structure=np.ones((3, 3), bool), iterations=pad)
            masks[(i, rot)] = (T, m, md)
    ch, cw = collar_mask.shape
    for size in sizes:
        occ = np.zeros((size, size), bool)
        # the collar: offsets (x0 + jx align, y0 + jy align) with its texels inside the sheet, pad clear of the edges
        x0, y0 = int(collar_loc0[0]), int(collar_loc0[1])
        jx0, jy0 = int(np.ceil((pad - x0) / align)), int(np.ceil((pad - y0) / align))
        ox, oy = x0 + jx0 * align, y0 + jy0 * align
        if ox + cw + pad > size or oy + ch + pad > size:
            continue
        cmd = ndimage.binary_dilation(collar_mask, structure=np.ones((3, 3), bool), iterations=pad)
        occ[oy:oy + ch, ox:ox + cw] |= cmd
        placed, ok = {}, True
        for i in order:
            best = None
            for rot in (0, 1):
                T, m, md = masks[(i, rot)]
                h, w = md.shape
                if h > size or w > size:
                    continue
                ov = fftconvolve(occ.astype(np.float32), md[::-1, ::-1].astype(np.float32), mode='valid')
                free = np.argwhere(ov < 0.5)
                if not len(free):
                    continue
                # lowest y first, then lowest x
                k = int(np.lexsort((free[:, 1], free[:, 0]))[0])
                y, x = int(free[k, 0]), int(free[k, 1])
                if best is None or (y, x) < (best[0], best[1]):
                    best = (y, x, rot)
            if best is None:
                ok = False
                break
            y, x, rot = best
            T, m, md = masks[(i, rot)]
            occ[y:y + md.shape[0], x:x + md.shape[1]] |= md
            placed[i] = T + np.array([x, y], np.float64)
        if ok:
            log(f'[socket uv] atlas {size}^2: the collar at offset ({ox - x0}, {oy - y0}) (multiples of {align}), '
                f'{len(placed)} islands')
            return size, np.array([ox - x0, oy - y0], np.float64), placed
    raise ValueError('no atlas up to the largest size holds the part')

