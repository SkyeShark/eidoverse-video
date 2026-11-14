"""B6 THE HIGH for the beetle (the Bestiary lead's round 10-28): each part's LIMIT SURFACE plus the chitin's MEASURED micro
detail (work/bestiary/beetle/b06b_measure.py on M1d / M1l / M3v / M4h; out_b58/photo/micro.json).

THE HIGH IS TWO LAYERS, evaluated where the bake needs them:
  MACRO  the limit surface's EXACT distance (the creased subdivision limit at L5, L6 where an L5 edge passes 0.5 mm at
         x10), sampled on the house voxel grid (voxel.SparseSDF: 0.12 mm voxels at x10, a +-0.4 mm band; outside the band
         the exact unsigned distance to the limit mesh, the house SHELL primitive) and baked by bake.py, its search, its
         gates and its wrong-surface rejection as they stand;
  MICRO  the relief h(q) (life mm) on the limit surface, a function of the surface point q evaluated EXACTLY at every
         sub-sample's own point on the limit and composed into the baked normal as the high's normal n' = normalize(n -
         grad_s h) (first order in h: h <= 0.03 mm against curvature radii of 0.5 mm and up). The measured features are
         0.02-0.12 mm across at life (0.2-1.2 mm at x10): voxelised at the macro grid's 0.012 mm (life) a 0.035 mm puncture
         is three voxels and a 0.02 mm seta two, and a grid fine enough for them (0.005 mm at life) would be ~1 G voxels for
         the venter alone; evaluated per sub-sample they keep their measured size at the texel (10.8 um at life).

THE MICRO LAYERS (life mm; [M] read on the photos by b06b, [E] estimated with its gate, the ring-light render's contrast
against the photo crop's in b06):
  cells   a jittered 3D Worley network (proc.cellular3's exact border distance on a domain-warped point) at `spacing`:
          walls `border` cells wide rising to soft crests on the cell borders, flat floors with a shallow dish, the
          cells sunk by `amp` (head: the rugose-reticulate dorsum, 0.115 mm [M]; elytra: the satin microsculpture,
          0.09 mm [M]; the venter and pronotum: a whisper under their punctures)
  pits    punctures at the sites of a jittered lattice within `r` of the surface, a smooth dimple of radius r and `depth`,
          thinned by the density mask (pronotal disc 87 / mm^2 [M], its sides 39 [M]; venter 82 [M]; mandible 30 [M])
  setae   streaks lying along the part's distal direction (the golden brushes of the tarsi [M: 20-24 % of the leg's plan,
          a fringe 0.14-0.47 mm], the tibiae's inner edges [M: 12.5 %], the venter's pubescence, the pronotal margins'
          fringes [M-an 0.3-0.5 mm bands]): `len`, a rounded section `w` wide and `ht` high
  grooves the sutures (the ventrites' four, FWHM 0.14-0.33 mm [M], the metaventral midline) as per-vertex profiles
Every layer's MASK lives per limit vertex (micro_masks), so the material pass reads the same numbers (setae golden, pits
duller): the colour follows the relief by construction.
"""
import numpy as np
import warp as wp

from .. import proc as PR
from .. import sdf as S_

wp.set_module_options({'enable_backward': False})

# per region: cells (spacing, amp, border share), pits (spacing, r, depth), setae (spacing, len, w, ht), groove depth
#   the depths [E] were set by b06's ring-light contrast against the photos' (first pass: head 1.34 against 0.88, elytra
#   1.24 against 0.53, mandible 0.11 against 0.34, ventrites 0.57 against 0.84, pronotal disc 1.03 against 1.08): the
#   relief's amplitudes scaled by the ratio where they missed (the contrast is close to linear in the relief's slope)
#   b06's first look: cells whose floors saturate at 0.3 of the spacing read as a crisp tiled mosaic (the photos show
#   rounded pits and soft rugae): the bowls now round over half the spacing, and the pronotum's cells are weak so its
#   punctures (round, bright-rimmed under the ring light on M1d) carry its texture
#   10-28 (the continuing builder; b06 trials t1-t3, out_b58/b06_stations_t*.png): the cells are the border network of
#   relief() (the border share is now the WALL's width in lattice units), which at a given amplitude carries ~1.5x the
#   old contrast; amplitudes scaled by each station's ratio to its photo (contrast ~ linear in the relief's slope):
#   head 1.286 -> x0.68 (photo 0.880); pronotum: the punctures larger and deeper (r 0.030, depth 0.020; the disc's 87 /
#   mm^2 kept: spacing 0.088) with weak cells, as M1d shows punctures, not a network; elytra 0.846 -> x0.63 (0.532);
#   venter: punctures over setae as M3v shows them (t3's network carried its contrast, 1.234 / 1.098 against 0.844 /
#   1.102, but M3v shows punctures: the pronotum's puncture size r 0.030, depth 0.020, spacing 0.088 for M3v's 82 /
#   mm^2, the cells weak: t4 ventrites 0.707, metaventrite 0.904). Final contrasts (b06_report_final.json, the venter
#   from b06_report_t4.json): head 1.099
#   (photo 0.880), pronotal disc 0.975 (1.078), side 0.635 (0.966), elytra 0.609 (0.532), mandible 0.331 (0.335).
#   Parts no photo station measures (legs, tarsi, antennae, palps, scutellum, sleeves) [E]: their cells scaled by the
#   same 1.5x so they read as before
#   10-28 after the first bake (the engine's close stills beside M1d: the head a crisp cobbled glaze of large cells, the
#   pronotum sparse punctures of every size over a visible cell crackle, the elytra smooth): t5 / t6 the head's cells
#   finer (0.085, the border 0.15, a stronger warp), the pronotum's and venter's punctures ONE size in one layer
#   (pit_mode 1) with a raised lip, their cells a whisper, the elytra's microsculpture domed granules (a negative
#   amplitude). t6: pronotal disc 1.079 (photo 1.078), side 1.396 (0.966: its density is M1d's measured 39 / 87, the
#   overshoot is left), ventrites 0.493 (0.844) and metaventrite 0.693 (1.102: M3v's contrast is half golden setae,
#   which are albedo, painted by the chitin pass, not relief), head 1.010 (0.880), elytra 0.684 (0.532). (10-28 restart)
#   the head and the elytra scaled by their ratios (contrast ~ linear in the slope over the limit's own 0.16 / 0.12):
#   head 0.0033 -> 0.0028, elytra -0.00064 -> -0.00050 (b06_report_t7.json)
#   10-29 (B5, the close-range round; the engine's close stills beside M1d at the photo's own resolution, b06 now blurs
#   the station to the photo's 15.5 um pixel before it measures: the earlier contrasts compared a 5 um render with a
#   15.5 um photo, and the gate held the relief ~3-8x too shallow): the CELLS take a MODE (cell_mode): 0 the border
#   network above (the pronotum's, the venter's and the legs' whispers); 1 VERMICULATE, the head: the superlevel set of a
#   domain-warped gradient noise at threshold cell_shape, worm-like ridges with rounded crests over narrow hollows (M1d's
#   bright wormy ridges over black, where the network gave wide flat cells with thin walls); 2 BEADS, the elytra: round
#   domes of radius cell_shape x the spacing at one layer of jittered sites (M1d's silky shagreen of round beads, where
#   the inverted network gave polygonal crackle). The setae's relief scaled per region (setae_relief: the venter's and
#   the legs' hairs 1-2 texels wide averaged into speckle that read as matte cork; their colour and gloss are the chitin
#   pass's sheen now). The head's groove is the MENTUM's suture (heads/insect_cage MENTUM, out of the cage since b3h-2)
#   (10-29, B5 trials t1-t3, out_b58/b06_stations_b5t*.png, M1d read at its own 15.5 um pixel: the head's worms 1-2 px
#   wide, their crests 3-4 px apart; the elytral beads 2 px, ~3 px apart; the pronotal pits 4-5 px rings) t1's worms
#   (spacing 0.105) and beads (r 0.026) were twice the photo's; t2 at the photo's scale (head 0.060, elytra 0.048 / r
#   0.016) under the thin ring: photo-resolution contrasts head 0.34, pronotum 0.51, elytra 0.30, mandible 0.17 (photo
#   0.88 / 1.08 / 0.53 / 0.34); an annulus light (t3) lit the macro surface's own 10-22 deg tilts and greyed every ground
#   (0.17 / 0.36 / 0.15 / 0.17), so the comparisons keep the thin ring. b06's render is ONE roughness and ONE albedo: the
#   photo's contrast also holds the material (a glossy black ground that mirrors the dark lens, the relief's flanks
#   rougher by the bake's sub-texel spread, the hollows' darker albedo), so the relief keeps the photo's SCALE and its
#   slopes (~17 deg on the worms' and beads' flanks) and the chitin pass, read in the engine beside M1d, brings the rest:
#   head worms at 0.065 (threshold -0.10: the ridges ~64 % of the surface, the hollows narrow), elytral beads at 0.050
#   with radius 0.36 of it, the pronotal punctures deeper (0.014) with a stronger lip (0.6), the mandible's sparse
#   punctures larger (r 0.022, 0.010 deep) with a bright lip (0.7) as M1d's bright specks
#   10-29 (B6, the relief judged in the ENGINE with the real material before the one re-bake: work/bestiary/beetle/
#   b6_trials, trial patches re-composed with b07's own kernel on B5's macro bake, rendered under the museum dome beside
#   M1d at its own pixel; B5's recipe through the same path matched B5's bake texel for texel in every patch interior):
#   B5's head worms (mode 1, the superlevel set) drew connected plateaus, grey blobs; the head now RIDGES (mode 3) along
#   the zero set of the warped noise, 0.065 apart, half-width 0.18 lattice units (~12 um), rounded crests (prof 2), 3.5 um
#   high (flanks under ~30 deg: steeper ones mirrored past the dome's 60 deg ring and split each ridge into lines, the
#   flat-patch tests t04): thin curly worms as M1d's. The pronotal punctures SMALLER AND CROWDED (r 0.025 at 0.075: 178 /
#   mm^2 against 87; 0.010 deep, the lip 0.35): under the dome the pronotum's ratio to the elytral disc 0.656 (M1d 0.639;
#   B5 0.815), with the skin's pit-wall occlusion. The elytral beads ROUNDED (prof 1.5: the dome's slopes on every bead,
#   no crease at the foot), radius 0.50 of the 0.050 spacing, 7.5 um, elongated 1.6 : 1 at 0.6 rad from the elytron's
#   axis (M1d's granules in rows): the shagreen reads across the whole disc, not only inside the highlight. The
#   mandible's punctures SPARSE (0.29 apart: ~12 / mm^2 against B5's 44; r 0.018, 0.009 deep, the lip 0.5 so each still
#   reads as a speck at the photo's pixel; at 0.15 / 0.006 none did)
#   10-29 (B7, the last material round: work/bestiary/beetle/b7_trials, B6's trial path on B6's bake, rendered under the
#   CONTINUOUS comparison dome, gated by t07 on M1d's own measures at its pixel). B6's relief came out 1.5-1.9x finer than
#   M1d's (b6_compare's spectral peaks), so at 1-2 texels of 10.8 um the bake turned it into roughness (satin at distance,
#   half the close contrast, the pits dots). Back at M1d's scale, B6's character kept: the head's ridges 0.100 apart,
#   half-width 0.16 (16 um: ~3 texels across), 5 um high, and BROKEN (cell_break 0.40: M1d's worms are short C / S
#   fragments, hooks and small loops, where a zero set of smooth noise is one labyrinth); the pronotal punctures at M1d's
#   measured density (0.100: 100 / mm^2; [M] 87) and ring size (r 0.034: rings ~82 um across, the B6 check's eye 80-90),
#   0.013 deep, the lip 0.40, in mild CLUSTERS (PIT_CLUSTER 0.30); the elytral beads DENSE at 0.060 (~280 / mm^2 over
#   the disc's rows), radius 0.58 of it, elongated 1.8 : 1, 9 um high. The t07 gate, the render blurred by M1d's own
#   spread (0.8 px: unblurred a render at M1d's spacing reads finer than the photo), against M1d: head peak 0.107 mm
#   (0.115) / ACF 24.2 um (23.9), elytra 0.091 (0.091) / 19.6 (20.8), pronotum 0.085 (0.134) / 23.5 (22.7): the
#   pronotum's peak does not move with the pits (a field at M1d's density peaks at ~0.87 of its spacing; the photo's sits
#   at its broader structure), its density, ring size and ACF match. The bake's sub-texel spread is gone with it (coat
#   roughness p50 at mip 0: head 0.17 against B6's 0.31): no finer texels needed
#   10-30 (B8, the macro round, b8/trials): THE ELYTRA PACKED, the lead's call after B7b's close still (sparse beads, one way, where M1d's
#   grain packs tight with dark crevices and turns over millimetres). cell_mode 4, grain_beads on grain_sheet (the note there): a
#   staggered lattice bent by a divergence-free flow. Beads at 0.62 of a cell merged, their crevices under the texel (g1); at
#   0.44 of a cell, 0.080 apart x 1.5 elongated, the ground between them a thin even network (B7b's 36 % open ground was
#   blotches because its layout was random; this is 7 %, in lines), g4a beside M1d at its pixel: peak 0.091 mm (M1d 0.091), ACF
#   19.8 um (20.8), dome L 0.038 (0.0367; B7b 0.051), contrast 0.292 (B7b 0.196, M1d 0.56), the distant gloss on B7b's
#   8-bit floor at mips 3-5 (t10 0.323-0.325). THE HEAD'S RIDGES 5 -> 4.2 um: a low sun glinted off their resolved flanks (slopes to
#   ~26 deg, just reaching the mirror direction in the grazing station: the head's back reading silver, b8_notes). THE MENTUM's
#   dome (mentum_dome) 0.45 mm: M3v's raised cushion
#   10-31 (B9, the grain as IRREGULAR GRANULES, the lead's call after the B8 check): B8's lattice had rows, so its flow curled them
#   into a fingerprint of whorls at the 9 s station, and the flow, a displacement of the sheet, stretched the beads about as much as
#   it turned them (b8_check k04: p50 1.62x, 26 % of the disc over 2x), where M1d shows irregular granules with a faint flow. The
#   elytra now draw GRANULES AT SITES ON THE LIMIT ITSELF (cell_mode 5, grain_granules: the sites a relaxed Poisson set packed in
#   an anisotropic metric along a faint direction field, grain_sites), each granule a dome in its own site's tangent plane: no
#   sheet, so nothing can stretch a bead, and no lattice, so no rows exist to curl. The flow only TURNS each granule in its own
#   frame. The cells' amplitude is 0 here (relief()'s network branch stays off: relief() itself is untouched, so the families that
#   read it, arthropod_skin's leg zones, keep their compiled kernels and their numbers); the granules' amplitude and ground are
#   `grain`, added in relief_grad. cell_mode 4 (grain_beads on grain_sheet) is kept for B8's reproduction
RECIPE = dict(
    head=dict(cells=(0.100, 0.0042, 0.15), pits=(0.10, 0.016, 0.004), setae=(0.07, 0.20, 0.022, 0.010), groove=0.030,
              warp=(1.3, 0.35), cell_mode=3.0, cell_shape=0.16, cell_prof=2.0, cell_break=0.40, dome=0.45),
    pronotum=dict(cells=(0.134, 0.0006, 0.22), pits=(0.100, 0.034, 0.013), setae=(0.05, 0.35, 0.024, 0.012),
                  groove=0.0, pit_mode=1.0, pit_rim=0.40),
    scutellum=dict(cells=(0.11, 0.0010, 0.22), pits=(0.10, 0.016, 0.006), setae=(0.06, 0.2, 0.02, 0.01), groove=0.0),
    # (10-29, B7b, the lead's call: the elytra satin at distance in B7, the Toksvig coat 0.45-0.50 at mips 2-5 against B5's
    # 0.31-0.33: the beads' slope variance) the beads at M1d's scale by the photo's SHARP band (b7b_trials t09: periods
    # over 66 um, where its MTF passes 0.5; in-band share 0.92 = M1d's, B7 0.81), LOWER (3.5 um) and FLAT-TOPPED (cell_flat
    # 3), 2.2 : 1: the runtime's Toksvig back on the 8-bit normal map's floor at mips 3-5 (0.33, as B5), the gloss band at
    # the turntable's 5.0 s back (b7b_trials/out/whole/tt5_whole_x1.png); up close elongated granules (trials r1-r5)
    # (10-31, B9) cell_mode 5: the granules at grain_sites' sites (GRAIN_SITES below), their amplitude and ground in `grain` (mm at
    # life, the ground a share of the amplitude as B8's 0.35); the cells' own amplitude 0 (relief()'s network off). B8's mode-4 keys
    # (cell_shape, cell_aniso, cell_jit; the amplitude was cells[1] 0.0030) stay for its reproduction
    # (11-01, B9, b9/trials g1-g5 on the B8 bake beside M1d at its pixel: the ground at 0.60 of the 4 um amplitude puts the median
    # texel low enough on its granule that the cavity term and CREVICE_OCC keep B8's dark net and the disc's tone, L 0.035 against
    # M1d's 0.0367; at 0.35 / 3 um the granules' tops brightened the albedo to L 0.050)
    elytron=dict(cells=(0.080, 0.0, 0.18), pits=(0.12, 0.012, 0.0013), setae=(0.06, 0.2, 0.02, 0.01), groove=0.0,
                 warp=(1.2, 0.35), cell_mode=5.0, cell_shape=0.44, cell_prof=1.0, cell_flat=2.0, cell_aniso=1.5,
                 cell_jit=0.30, grain=dict(amp=0.0040, base=0.60)),
    mandible=dict(cells=(0.10, 0.0008, 0.22), pits=(0.29, 0.018, 0.009), setae=(0.06, 0.2, 0.02, 0.01), groove=0.0,
                  pit_mode=1.0, pit_rim=0.50),
    # (10-29, B5) the venter's hairs 0.15 of their relief: 1-2 texels wide they cannot draw as hairs, and the bake's
    # sub-texel spread (nlen) would turn their relief into a rough coat under them, the matte cork again; their look is
    # the runtime's sheen over the kept coat
    venter=dict(cells=(0.169, 0.0008, 0.22), pits=(0.110, 0.020, 0.010), setae=(0.05, 0.16, 0.018, 0.006),
                groove=0.030, pit_mode=1.0, pit_rim=0.60, setae_relief=0.15),
    coxa=dict(cells=(0.12, 0.0013, 0.22), pits=(0.10, 0.015, 0.005), setae=(0.06, 0.22, 0.02, 0.010), groove=0.0,
              setae_relief=0.6),
    trochanter=dict(cells=(0.12, 0.0013, 0.22), pits=(0.10, 0.015, 0.005), setae=(0.06, 0.22, 0.02, 0.010), groove=0.0,
                    setae_relief=0.6),
    femur=dict(cells=(0.12, 0.0013, 0.22), pits=(0.10, 0.015, 0.005), setae=(0.06, 0.25, 0.02, 0.010), groove=0.0,
               setae_relief=0.6),
    tibia=dict(cells=(0.12, 0.0013, 0.22), pits=(0.10, 0.015, 0.005), setae=(0.05, 0.30, 0.022, 0.012), groove=0.0,
               setae_relief=0.6),
    tarsus=dict(cells=(0.10, 0.0010, 0.22), pits=(0.11, 0.012, 0.004), setae=(0.035, 0.32, 0.020, 0.014), groove=0.0),
    claw=dict(cells=(0.10, 0.0, 0.22), pits=(0.10, 0.0, 0.0), setae=(0.05, 0.2, 0.02, 0.0), groove=0.0),
    antenna=dict(cells=(0.10, 0.0006, 0.22), pits=(0.10, 0.012, 0.004), setae=(0.04, 0.10, 0.012, 0.004), groove=0.0,
                 setae_relief=0.5),
    mouthparts=dict(cells=(0.10, 0.0013, 0.22), pits=(0.10, 0.012, 0.004), setae=(0.04, 0.20, 0.016, 0.008), groove=0.0),
    eye=dict(cells=(0.05, 0.0, 0.22), pits=(0.1, 0.0, 0.0), setae=(0.05, 0.2, 0.02, 0.0), groove=0.0),
    # (10-29, B5) the membranes WRINKLED (the neck sleeve read as a smooth disc): the vermiculate mode at a coarse spacing,
    # soft folds ~0.06 mm wide [E]
    membrane=dict(cells=(0.14, 0.0060, 0.30), pits=(0.1, 0.0, 0.0), setae=(0.05, 0.2, 0.02, 0.0), groove=0.0,
                  warp=(1.6, 0.5), cell_mode=1.0, cell_shape=0.0),
)
NPAR = 37
# the ventrites' sutures (M3v, b06b's midline profile through the abdomen; z life mm in B1's frame) and their FWHM
VENTRITE_SUTURES = None             # filled from micro.json by micro_masks (venter) when present


def params(region, seed, grain_ok=False):
    """the region's relief parameters (NPAR floats). (10-31, B9) a region that draws GRANULES (its recipe's `grain`) needs its
    sites' table after these, which only params_full can build (it takes the limit): asked here for such a region, this
    refuses, unless grain_ok (params_full's own call), so no caller can bake the elytra without their granules unnoticed"""
    r = RECIPE[region]
    if r.get('grain') and not grain_ok:
        raise ValueError(f'stag_beetle_sculpt.params: {region} draws granules (cell_mode 5): call params_full(region, seed, V, F, '
                         f'N, M4) with its limit, which appends the sites\' table')
    p = np.zeros(NPAR, np.float32)
    p[0:3] = r['cells']
    p[3:6] = r['pits']
    p[6:10] = r['setae']
    p[10] = r['groove']
    p[11] = float(seed)
    # (10-28, the engine's close stills beside M1d) the cells' domain warp per region (feature size in cells, its
    # displacement in cells; 1.6 / 0.22 as before unless a row says), the punctures' raised lip (a share of their depth)
    # and their MODE: 0 the sites within r of the surface (sections of every size), 1 ONE layer of sites (|dn| < half the
    # spacing), each a full dimple of radius r: M1d's pronotal punctures are one size, nearly touching, bright-lipped
    p[12:14] = r.get('warp', (1.6, 0.22))
    p[14] = r.get('pit_rim', 0.0)
    p[15] = r.get('pit_mode', 0.0)
    # (10-29, B5) the cells' MODE (0 the border network, 1 vermiculate worms, 2 round beads) and its shape (the worms'
    # noise threshold; the beads' radius as a share of the spacing), the setae's relief scale
    p[16] = r.get('cell_mode', 0.0)
    p[17] = r.get('cell_shape', 0.0)
    p[18] = r.get('setae_relief', 1.0)
    # (10-29, B6) the cells' PROFILE: the beads' dome exponent ((1 - u^2)^prof: 2 B5's, flat-topped at this amplitude; 1 a
    # paraboloid, rounded to its foot), the ridges' crest shape (mode 3); the beads' ELONGATION (the footprint's long to
    # short axis, area kept; 1 round) and its long axis's angle (radians) from the part's direction d in the tangent plane
    p[19] = r.get('cell_prof', 2.0)
    p[20] = r.get('cell_aniso', 1.0)
    p[21] = r.get('cell_angle', 0.0)
    # (10-29, B7) the ridges' BREAK share (mode 3): 0 continuous worms (B6), up to ~0.6 short fragments
    p[22] = r.get('cell_break', 0.0)
    # (10-29, B7b) the beads' FLATNESS (mode 2): the profile (1 - u^k)^prof's k; 2 the round dome (B5-B7), 3-6 flat-topped;
    # and the rows' WANDER (radians x a gradient noise of 2 spacings about cell_angle; 0: every bead along cell_angle, B6-B7)
    p[23] = r.get('cell_flat', 2.0)
    p[24] = r.get('cell_angle_jit', 0.0)
    # (10-30, B8) the PACKED GRAIN's site jitter (mode 4, lattice units) and the MENTUM's dome height (mm at life, the head
    # only): 0 off, every other region's arrays as before
    p[25] = r.get('cell_jit', 0.0)
    p[26] = r.get('dome', 0.0)
    # (10-31, B9) THE GRANULES (cell_mode 5): 27 on (params_full sets it with the table), 28 their amplitude (mm), 29 their ground
    # (a share of it), 30-32 the table's grid origin (mm), 33 its cell (mm), 34-36 its cells along x, y, z; the grid's site
    # offsets start at NPAR, the sites' records after them (grain_table). 0 here: no table, no granules
    g = r.get('grain')
    if g:
        p[28] = g['amp']
        p[29] = g.get('base', 0.35)
    return p


# ============================================================================================ the relief (Warp)
@wp.func
def smooth_step(a: float, b: float, x: float):
    t = wp.clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@wp.func
def grain_beads(u: float, v: float, par: wp.array(dtype=wp.float32), o: int, seed: int):
    """(10-30, B8) THE PACKED GRAIN (cell_mode 4, the elytra), 0..~1.15 at the sheet point (u, v) (mm: grain_sheet, the flowed
    sheet coordinates): round domes on a STAGGERED 2D lattice, the columns sp / sqrt(aniso) apart across the body, the beads
    along a column sp x sqrt(aniso) apart, odd columns offset half a cell ALONG the body, so the long beads' tips interlock in
    lines along it as M1d's do (offset the other way they stack in courses, running-bond brick), each dome of radius
    cell_shape (lattice units, +-10 %) and height +-15 %, the ground between them a thin even network with small
    triangles at its corners: M1d's dark pits, where a random layout leaves blotches. One layer of sites, so no surface
    crosses layers and draws faults, and 9 sites where mode 2 walks 27"""
    sp = par[o + 0]
    sq = wp.sqrt(wp.max(par[o + 20], 1.0e-3))
    px = u * sq / sp
    py = v / (sp * sq)
    r0 = par[o + 17]
    jit = par[o + 25]
    ci = int(wp.floor(px))
    hb = float(0.0)
    for a in range(-1, 2):
        i = ci + a
        off = 0.5 * float(wp.abs(i) % 2)
        cj = int(wp.floor(py - off))
        for b in range(-1, 2):
            j = cj + b
            r1 = PR.rnd3(PR.hash3i(i, j, 3, seed + 41))
            r2 = PR.rnd3(PR.hash3i(i, j, 5, seed + 43))
            dx = px - (float(i) + 0.5 + jit * (r1[0] - 0.5))
            dy = py - (float(j) + 0.5 + off + jit * (r1[1] - 0.5))
            rs = r0 * (0.90 + 0.20 * r2[0])
            uu = (dx * dx + dy * dy) / (rs * rs)
            if uu < 1.0:
                w = wp.pow(1.0 - wp.pow(uu, 0.5 * par[o + 23]), par[o + 19]) * (0.85 + 0.30 * r2[1])
                hb = wp.max(hb, w)
    return hb


@wp.func
def mentum_dome(q: wp.vec3, n: wp.vec3, hd: float):
    """(10-30, B8) THE MENTUM'S DOME (mm at life) at the head's limit point q with its normal n: M3v's plate is a raised cushion
    (one tight glint, its flanks rolling into a dark suture), the model's a flat tint. A height over MENTUM_PLATE's superellipse
    (these literals: the assert under its table), (1 - u^4) of the outline's own radius u, on the underside only. Composed into
    the normal by relief_grad alone: it never enters h, which drives the cavity's albedo and the crevices, and it stays
    out of the silhouette (first order on the underside, like the micro layer)"""
    if q[1] >= 14.9:
        return 0.0
    zr = (q[2] + 6.72) / 2.18
    xr = q[0] / (2.55 * (1.0 - 0.04 * zr))
    u = wp.pow(wp.pow(wp.abs(xr), 3.5) + wp.pow(wp.abs(zr), 3.5), 1.0 / 3.5)
    if u >= 1.0:
        return 0.0
    return hd * (1.0 - u * u * u * u) * smooth_step(0.30, 0.60, -n[1])


@wp.func
def relief(q: wp.vec3, n: wp.vec3, m: wp.vec4, d: wp.vec3, par: wp.array(dtype=wp.float32), o: int):
    """the micro relief at the limit point q (life mm) with its normal n: (h, pit, seta, groove) as a vec4. m = (pit
    density, setae amount, groove profile, cells amount); d = the setae's direction (tangent)"""
    seed = int(par[o + 11])
    h = float(0.0)
    pit = float(0.0)
    seta = float(0.0)
    # cells: the borders stand, the cells sink. (10-28, the continuing builder, after three b06 looks: the first recipe's
    # walls, linear ramps from the exact border distance over half a cell, met along each cell's medial skeleton and
    # creased every floor into facets (a tiled foil); a smooth Voronoi of the sites' own distances left isolated craters,
    # since projected lattice sites are a near-Poisson set: past 0.46 cells from the nearest site lies ~53 % of the area.)
    # Now the exact border distance e (it tiles the slice: every point lies in a cell), on a DOMAIN-WARPED point (0.22 of a
    # cell at 1.6 cells: curved walls, rugae), a WALL that rises over the border share b of a cell with zero slope at both
    # ends (smooth crest, flat floor beyond, so walls from opposite sides meet only in the narrowest cells), a shallow DISH
    # in the floor toward the site that fades out before the crest (the floor's shading varies, the crest stays smooth),
    # and a crest height that wanders along each ridge (+-30 %). A negative amplitude inverts it (domed granules)
    cmode = int(par[o + 16] + 0.5)
    if m[3] > 0.0 and par[o + 1] != 0.0 and cmode == 1:
        # (10-29, B5) VERMICULATE: the superlevel set of a domain-warped gradient noise (one lattice unit = the spacing) at
        # threshold cell_shape: the ridges where the noise stands over it, their flanks over 0.45 noise units, their crests
        # the noise's own rounded maxima, the hollows the narrow channels between (a threshold under 0: the ridges take
        # ~60 % of the surface); a band-limited noise's superlevel set is a field of short curved worms, joined here and
        # there, as M1d's head shows
        sp = par[o + 0]
        pw = PR.warp3(q / sp, par[o + 12], par[o + 13], seed + 5)
        nv = PR.noise3(pw, seed)
        th = par[o + 17]
        h = h + m[3] * par[o + 1] * (smooth_step(th - 0.05, th + 0.40, nv) - 0.5)
    elif m[3] > 0.0 and par[o + 1] != 0.0 and cmode == 2:
        # (10-29, B5) BEADS: round domes at ONE layer of jittered sites (a site within half a spacing of the surface,
        # fading over the slab's last fifth), each of radius cell_shape x the spacing (+-15 %) and height +-20 %; their
        # union over a flat ground
        sp = par[o + 0]
        r0 = par[o + 17] * sp
        ps = q / sp
        ci = int(wp.floor(ps[0]))
        cj = int(wp.floor(ps[1]))
        ck = int(wp.floor(ps[2]))
        hb = float(0.0)
        # (10-29, B6) the footprint's axes in the tangent plane: the long one at cell_angle from d (M1d's elytral granules
        # are elongated ~2:1 in rows across the disc), stretched by sqrt(cell_aniso), the short one shrunk by it
        ta = d - n * wp.dot(d, n)
        if wp.length(ta) < 1.0e-6:
            ta = wp.cross(n, wp.vec3(0.0, 0.0, 1.0))
            if wp.length(ta) < 1.0e-6:
                ta = wp.cross(n, wp.vec3(1.0, 0.0, 0.0))
        ta = wp.normalize(ta)
        tb = wp.cross(n, ta)
        ang = par[o + 21]
        if par[o + 24] > 0.0:
            # (10-29, B7b) the rows' angle WANDERS over the surface (M1d's granules lie in loose rows whose direction
            # turns every few grains, not along one diagonal): cell_angle + cell_angle_jit x a gradient noise of 2 spacings
            # (one field per evaluation, outside the beads' loop: a per-bead turn inside the unrolled loop overran the
            # CUDA compiler's memory)
            ang = ang + par[o + 24] * PR.noise3(q / (2.0 * sp), seed + 47)
        ca = wp.cos(ang)
        sa = wp.sin(ang)
        ea = ta * ca + tb * sa
        eb = tb * ca - ta * sa
        sq = wp.sqrt(wp.max(par[o + 20], 1.0e-3))
        for a in range(-1, 2):
            for b in range(-1, 2):
                for cc in range(-1, 2):
                    s = PR.site_of(wp.vec3i(ci + a, cj + b, ck + cc), 0.85, seed + 41) * sp
                    rbead = PR.rnd3(PR.hash3i(ci + a, cj + b, ck + cc, seed + 43))
                    dv = q - s
                    dn = wp.dot(dv, n)
                    ad = wp.abs(dn)
                    if ad < 0.5 * sp:
                        fade = 1.0 - smooth_step(0.4 * sp, 0.5 * sp, ad)
                        rs = r0 * (0.85 + 0.30 * rbead[0])
                        u = wp.sqrt((wp.dot(dv, ea) / (rs * sq)) * (wp.dot(dv, ea) / (rs * sq)) +
                                    (wp.dot(dv, eb) * sq / rs) * (wp.dot(dv, eb) * sq / rs))
                        if u < 1.0:
                            # (10-29, B6) the dome's profile (1 - u^2)^cell_prof: B5's 2 at this amplitude put every
                            # bead's slopes under 15 deg with a flat top, so a bead lit only where the macro surface
                            # itself mirrored the light (M1d: pebbled shagreen everywhere); a lower exponent rounds the
                            # top down to the foot, every bead holding the tilts the dome's rings need
                            uk = u * u
                            if par[o + 23] > 2.0:
                                # (10-29, B7b) FLAT-TOPPED beads (1 - u^k)^cell_prof, k = cell_flat: the slope lives in
                                # a ring at the foot, the top a level facet (2: the round profile above, unchanged)
                                uk = wp.pow(u, par[o + 23])
                            w = wp.pow(1.0 - uk, par[o + 19])
                            hb = wp.max(hb, w * fade * (0.8 + 0.4 * rbead[1]))
        h = h + m[3] * par[o + 1] * (hb - 0.35)
    elif m[3] > 0.0 and par[o + 1] != 0.0 and cmode == 4:
        # (10-30, B8) THE PACKED GRAIN: d carries the flowed sheet coordinates here (grain_sheet; the elytra have no setae)
        h = h + m[3] * par[o + 1] * (grain_beads(d[0], d[1], par, o, seed) - 0.35)
    elif m[3] > 0.0 and par[o + 1] != 0.0 and cmode == 3:
        # (10-29, B6) RIDGES: thin curly ridges along the ZERO SET of a domain-warped gradient noise (one lattice unit =
        # the spacing), each a rounded crest (1 - x^2)^2 of half-width cell_shape (lattice units) across it, x the
        # distance to the zero set to first order (|noise| / its gradient along the surface, the gradient floored so a
        # saddle cannot balloon a ridge into a blob), its height wandering along the ridge. B5's mode 1 (the noise's
        # superlevel set) drew wide connected plateaus with sharp rims (grey blobs at distance, outlines close up); M1d's
        # head shows thin curly ridges 15-20 um wide, 50-60 um apart, C / S shapes and small loops, over black
        sp = par[o + 0]
        pw = PR.warp3(q / sp, par[o + 12], par[o + 13], seed + 5)
        nv = PR.noise3(pw, seed)
        e = 0.04
        g3 = wp.vec3(PR.noise3(pw + wp.vec3(e, 0.0, 0.0), seed) - nv, PR.noise3(pw + wp.vec3(0.0, e, 0.0), seed) - nv,
                     PR.noise3(pw + wp.vec3(0.0, 0.0, e), seed) - nv) / e
        gt = g3 - n * wp.dot(g3, n)
        x = wp.abs(nv) / (wp.max(wp.length(gt), 0.45) * wp.max(par[o + 17], 1.0e-3))
        rr = float(0.0)
        if x < 1.0:
            rr = wp.pow(1.0 - x * x, par[o + 19])
        wander = 0.75 + 0.5 * smooth_step(-0.6, 0.6, PR.noise3(pw * 1.7, seed + 9))
        if par[o + 22] > 0.0:
            # (10-29, B7) the worms BROKEN into short C / S fragments, hooks and small loops (M1d's head at its own
            # pixel; a zero set of smooth noise is one connected labyrinth): the ridge fades out where a second noise
            # falls under the break share, over a short taper so each fragment's end rounds off
            wander = wander * smooth_step(-0.12, 0.12, PR.noise3(pw * 2.1, seed + 13) + 0.45 - 0.9 * par[o + 22])
        h = h + m[3] * par[o + 1] * (rr * wander - 0.25)
    elif m[3] > 0.0 and par[o + 1] != 0.0:
        sp = par[o + 0]
        pw = PR.warp3(q / sp, par[o + 12], par[o + 13], seed + 5)
        c = PR.cellular3(pw, 0.85, seed)
        ridge = 1.0 - smooth_step(0.0, par[o + 2], c.edge)
        bowl = 1.0 - smooth_step(0.0, 0.85, c.f1)
        wander = 0.7 + 0.6 * smooth_step(-0.6, 0.6, PR.noise3(pw * 2.3, seed + 9))
        h = h + m[3] * par[o + 1] * (ridge * wander - 0.5 - 0.35 * bowl * (1.0 - ridge))
    # pits: sites within r of the surface, thinned by the density mask
    if m[0] > 0.0 and par[o + 5] > 0.0:
        sp = par[o + 3]
        r = par[o + 4]
        ps = q / sp
        ci = int(wp.floor(ps[0]))
        cj = int(wp.floor(ps[1]))
        ck = int(wp.floor(ps[2]))
        for a in range(-1, 2):
            for b in range(-1, 2):
                for cc in range(-1, 2):
                    s = PR.site_of(wp.vec3i(ci + a, cj + b, ck + cc), 0.9, seed + 31) * sp
                    keep = PR.u01(PR.hash3i(ci + a, cj + b, ck + cc, seed + 57))
                    if keep < m[0]:
                        dv = q - s
                        dn = wp.dot(dv, n)
                        if par[o + 15] > 0.5:
                            # one layer: a site within half a spacing of the surface makes a full dimple of radius r
                            # (fading over the slab's last fifth, so a curved surface never cuts one in half) with a
                            # raised lip just outside it
                            ad = wp.abs(dn)
                            if ad < 0.5 * sp:
                                fade = 1.0 - smooth_step(0.4 * sp, 0.5 * sp, ad)
                                u = wp.length(dv - n * dn) / r
                                if u < 1.6:
                                    if u < 1.0:
                                        w = (1.0 - u * u) * (1.0 - u * u)
                                        h = h - par[o + 5] * w * fade
                                        pit = wp.max(pit, w * fade)
                                    xl = (u - 1.0) / 0.28
                                    h = h + par[o + 14] * par[o + 5] * fade * wp.exp(-xl * xl)
                        else:
                            rr = r * r - dn * dn
                            if rr > 0.0:
                                re = wp.sqrt(rr)
                                dt = wp.length(dv - n * dn)
                                if dt < re:
                                    u = dt / re
                                    w = (1.0 - u * u) * (1.0 - u * u)
                                    h = h - par[o + 5] * w * (re / r)
                                    pit = wp.max(pit, w)
    # setae: streaks along d from each kept site, lying in the tangent plane
    if m[1] > 0.0 and par[o + 9] > 0.0:
        sp = par[o + 6]
        L = par[o + 7]
        wd = par[o + 8]
        t = d - n * wp.dot(d, n)
        tl = wp.length(t)
        if tl > 1.0e-6:
            t = t / tl
            ps = q / sp
            ci = int(wp.floor(ps[0]))
            cj = int(wp.floor(ps[1]))
            ck = int(wp.floor(ps[2]))
            reach = int(wp.ceil(0.5 * L / sp)) + 1
            for a in range(-reach, reach + 1):
                for b in range(-reach, reach + 1):
                    for cc in range(-reach, reach + 1):
                        hh = PR.hash3i(ci + a, cj + b, ck + cc, seed + 101)
                        if PR.u01(hh) < m[1]:
                            s = PR.site_of(wp.vec3i(ci + a, cj + b, ck + cc), 1.0, seed + 103) * sp
                            dv = q - s
                            dn = wp.dot(dv, n)
                            if wp.abs(dn) < 0.6 * sp:
                                dv = dv - n * dn
                                # each seta's own length and a small turn about the normal
                                r3 = PR.rnd3(hh)
                                Ls = L * (0.6 + 0.8 * r3[0])
                                ang = (r3[1] - 0.5) * 0.6
                                b2 = wp.cross(n, t)
                                tt = t * wp.cos(ang) + b2 * wp.sin(ang)
                                along = wp.dot(dv, tt)
                                if along > -0.05 * Ls and along < Ls:
                                    perp = wp.length(dv - tt * along)
                                    if perp < wd:
                                        # the seta tapers to its tip; rounded section
                                        taper = 1.0 - 0.6 * wp.clamp(along / Ls, 0.0, 1.0)
                                        u = perp / (wd * 0.5 * (1.0 + taper))
                                        if u < 1.0:
                                            prof = wp.sqrt(1.0 - u * u) * taper
                                            # a seta lies ON the surface ((10-29, B5) its relief scaled by setae_relief)
                                            h = wp.max(h, m[1] * par[o + 9] * par[o + 18] * prof)
                                            seta = wp.max(seta, prof)
    # grooves (the per-vertex profile)
    groove = m[2]
    h = h - groove * par[o + 10]
    return wp.vec4(h, pit, seta, groove)


@wp.func
def grain_granules(q: wp.vec3, n: wp.vec3, par: wp.array(dtype=wp.float32), o: int):
    """(10-31, B9) THE GRANULES (cell_mode 5, the elytra), 0..~1.4 at the limit point q (life mm) with its normal n: the union of
    domes (1 - u^cell_flat)^cell_prof x the site's height, u the point's distance from a site in that site's own ellipse, laid in
    the tangent plane at q (the long axis the site's, projected; the short one n x it). The sites (grain_sites: a relaxed Poisson
    set on the limit itself) sit in a dense grid after the parameters (grain_table): the grid's cell is at least twice the largest
    semi-axis, so the 2 x 2 x 2 cells nearest q hold every granule that can reach it; a site more than half a cell off the
    tangent plane belongs to another sheet of the part and is skipped. Nothing here is a coordinate of a sheet: each granule keeps
    its designed size and shape wherever it lies"""
    c = par[o + 33]
    nx = int(par[o + 34] + 0.5)
    ny = int(par[o + 35] + 0.5)
    nz = int(par[o + 36] + 0.5)
    g0 = o + 37                                  # NPAR: the grid's site offsets (nx ny nz + 1)
    rec = g0 + nx * ny * nz + 1                  # the sites' records, 9 floats each
    i0 = int(wp.floor((q[0] - par[o + 30]) / c - 0.5))
    j0 = int(wp.floor((q[1] - par[o + 31]) / c - 0.5))
    k0 = int(wp.floor((q[2] - par[o + 32]) / c - 0.5))
    prof = par[o + 19]
    flat = par[o + 23]
    hb = float(0.0)
    for a in range(2):
        i = i0 + a
        if i >= 0 and i < nx:
            for b in range(2):
                j = j0 + b
                if j >= 0 and j < ny:
                    for cc in range(2):
                        k = k0 + cc
                        if k >= 0 and k < nz:
                            cell = (i * ny + j) * nz + k
                            s0 = int(par[g0 + cell] + 0.5)
                            s1 = int(par[g0 + cell + 1] + 0.5)
                            for s in range(s0, s1):
                                rb = rec + 9 * s
                                dv = q - wp.vec3(par[rb], par[rb + 1], par[rb + 2])
                                if wp.abs(wp.dot(dv, n)) < 0.5 * c:
                                    ax = wp.vec3(par[rb + 3], par[rb + 4], par[rb + 5])
                                    ax = ax - n * wp.dot(ax, n)
                                    la = wp.length(ax)
                                    if la > 1.0e-6:
                                        ax = ax / la
                                        bx = wp.cross(n, ax)
                                        x = wp.dot(dv, ax) / par[rb + 6]
                                        y = wp.dot(dv, bx) / par[rb + 7]
                                        u2 = x * x + y * y
                                        if u2 < 1.0:
                                            w = wp.pow(1.0 - wp.pow(u2, 0.5 * flat), prof) * par[rb + 8]
                                            hb = wp.max(hb, w)
    return hb


@wp.func
def relief_grad(q: wp.vec3, n: wp.vec3, m: wp.vec4, d: wp.vec3, par: wp.array(dtype=wp.float32), o: int, eps: float):
    """the relief's surface gradient at q (central differences along two tangents) and the relief itself"""
    a = wp.vec3(0.0, 0.0, 1.0)
    if wp.abs(n[2]) > 0.9:
        a = wp.vec3(1.0, 0.0, 0.0)
    t1 = wp.normalize(wp.cross(n, a))
    t2 = wp.cross(n, t1)
    # (10-30, B8) the packed grain reads the sheet coordinates in d, which do not move with q: the steps go to them, each
    # tangent's share along the sheet's two directions on this surface (et the body's axis in the tangent plane, es across it)
    d1 = wp.vec3(0.0, 0.0, 0.0)
    d2 = wp.vec3(0.0, 0.0, 0.0)
    if int(par[o + 16] + 0.5) == 4:
        ez = wp.vec3(0.0, 0.0, 1.0)
        et = ez - n * wp.dot(ez, n)
        if wp.length(et) < 1.0e-6:
            et = t1
        et = wp.normalize(et)
        es = wp.cross(n, et)
        d1 = wp.vec3(eps * wp.dot(t1, es), eps * wp.dot(t1, et), 0.0)
        d2 = wp.vec3(eps * wp.dot(t2, es), eps * wp.dot(t2, et), 0.0)
    r0 = relief(q, n, m, d, par, o)
    h1p = relief(q + t1 * eps, n, m, d + d1, par, o)[0]
    h1m = relief(q - t1 * eps, n, m, d - d1, par, o)[0]
    h2p = relief(q + t2 * eps, n, m, d + d2, par, o)[0]
    h2m = relief(q - t2 * eps, n, m, d - d2, par, o)[0]
    g = t1 * ((h1p - h1m) / (2.0 * eps)) + t2 * ((h2p - h2m) / (2.0 * eps))
    if par[o + 26] > 0.0:
        # (10-30, B8) the mentum's dome, into the normal only (mentum_dome), its step wider than the relief's: a smooth form
        e = wp.max(eps, 0.02)
        hd = par[o + 26]
        g = g + t1 * ((mentum_dome(q + t1 * e, n, hd) - mentum_dome(q - t1 * e, n, hd)) / (2.0 * e)) + \
            t2 * ((mentum_dome(q + t2 * e, n, hd) - mentum_dome(q - t2 * e, n, hd)) / (2.0 * e))
    if par[o + 27] > 0.5 and m[3] > 0.0:
        # (10-31, B9) the granules (grain_granules), their height into h (the cavity and the crevices read it) and their slopes
        # into the normal, by the same steps along the tangents as the rest of the relief
        ga = m[3] * par[o + 28]
        g = g + t1 * (ga * (grain_granules(q + t1 * eps, n, par, o) - grain_granules(q - t1 * eps, n, par, o)) / (2.0 * eps)) + \
            t2 * (ga * (grain_granules(q + t2 * eps, n, par, o) - grain_granules(q - t2 * eps, n, par, o)) / (2.0 * eps))
        r0 = wp.vec4(r0[0] + ga * (grain_granules(q, n, par, o) - par[o + 29]), r0[1], r0[2], r0[3])
    return r0, g


# ============================================================================================ the macro field
@wp.kernel
def k_mesh_sdf(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, open_: int, half: float,
               out: wp.array(dtype=wp.float32)):
    i = wp.tid()
    p = pts[i]
    if open_ == 1:
        q = wp.mesh_query_point_no_sign(mesh, p, maxd)
        if q.result:
            cp = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[i] = wp.length(p - cp) - half
        else:
            out[i] = maxd
        return
    q = wp.mesh_query_point_sign_normal(mesh, p, maxd)
    if q.result:
        cp = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        out[i] = wp.length(p - cp) * q.sign
    else:
        out[i] = maxd


class MeshProg:
    """the macro high as a 'program' for voxel.SparseSDF: eval = the exact signed distance to the closed limit mesh (an
    open sleeve: the unsigned distance less its half thickness: the house SHELL); _args = an sdf.Program holding the same
    mesh as a SHELL (the hybrid sampler's field outside the band: exact, unsigned)"""

    def __init__(self, V, F, open_=False, half=0.0, maxd=0.05):
        self.V = np.asarray(V, np.float32)
        self.F = np.asarray(F, np.int32)
        self.mesh = wp.Mesh(points=wp.array(self.V, dtype=wp.vec3), indices=wp.array(self.F.ravel(), dtype=wp.int32))
        self.open = int(bool(open_))
        self.half = float(half)
        self.maxd = float(maxd)
        self.prog = S_.Program()
        self.prog.shell(self.V, self.F, half, maxd=maxd, name='limit (unsigned, outside the band)')

    def eval(self, pts):
        P = wp.array(np.asarray(pts, np.float32).reshape(-1, 3), dtype=wp.vec3)
        out = wp.zeros(len(P), dtype=wp.float32)
        wp.launch(k_mesh_sdf, dim=len(P), inputs=[self.mesh.id, P, self.maxd, self.open, self.half, out])
        return out.numpy()

    def _args(self):
        return self.prog._args()


def macro_field(V_m, F, open_=False, half=0.0, voxel=0.00012, band=0.0004, log=print):
    """the macro high's SparseSDF (metres, x10): its box the mesh's + 1.5 mm"""
    from .. import voxel as VX
    prog = MeshProg(V_m, F, open_, half)
    lo = V_m.min(0) - 0.0015
    hi = V_m.max(0) + 0.0015
    G = VX.SparseSDF(prog, lo, hi, voxel=voxel, band=band, log=log)
    G._prog_keep = prog
    return G


# ============================================================================================ the masks per limit vertex
# (10-30, B8) THE PACKED GRAIN'S SHEET (cell_mode 4): M1d's elytral granules lie in rows that bend over a millimetre or so,
# packed tight at an even density. b8/p01 + p02, flat patches beside M1d at its pixel: B7b's beads leave 36 % open ground (the
# dark blotches every crevice occlusion drew); one angle field over near-Poisson sites read as flowing fur, an anisotropic
# Voronoi as crazed polygons, a regular lattice under a plain warp as halftone with its density swinging, and a 3D lattice drew
# faults where the surface crossed its layers. So: a 2D lattice in coordinates of the surface itself, the rows bent by a
# DIVERGENCE-FREE flow (it turns the rows, it can't crowd them). yc: the section's centre for the angle round it; na, nz:
# the coordinate net; blur: its smoothing in net cells; feature (mm) the flow's size, rot (radians rms) how far it turns the rows
GRAIN_MASK = dict(yc=9.0, na=260, nz=460, blur=2.0, feature=1.6, rot=0.25, seed=23, res=0.02)


def grain_sheet(V, N, outer):
    """(10-30, B8) per limit vertex of the (left) elytron: d = (u, v, 0), mm: the sheet's coordinates, arc length across (from the
    suture, along each section) and along (each column of equal angle round the section's centre, toward +z), with the flow's
    displacement added; relief reads them for the packed grain (the right elytron is the mirror, as its maps are). A coordinate
    net over the outer face: vertices binned by (angle, z), the net's arc lengths summed, read back bilinearly. The stream
    function is noise in (s, t), scaled so its rotation -1/2 lap(psi) has rms GRAIN_MASK rot"""
    from scipy import ndimage as nd
    g = GRAIN_MASK
    V = np.asarray(V, np.float64)
    ang = np.arctan2(V[:, 0], V[:, 1] - g['yc'])
    sel = outer > 0.5
    a0, a1 = ang[sel].min(), ang[sel].max()
    z0, z1 = V[sel, 2].min(), V[sel, 2].max()
    ia = (ang - a0) / (a1 - a0) * (g['na'] - 1)
    iz = (V[:, 2] - z0) / (z1 - z0) * (g['nz'] - 1)
    ka = np.clip(np.round(ia[sel]).astype(np.int64), 0, g['na'] - 1)
    kz = np.clip(np.round(iz[sel]).astype(np.int64), 0, g['nz'] - 1)
    W = np.zeros((g['na'], g['nz']))
    np.add.at(W, (ka, kz), 1.0)
    P = np.zeros((g['na'], g['nz'], 3))
    for c in range(3):
        np.add.at(P[..., c], (ka, kz), V[sel, c])
    hole = W == 0.0
    P = P / np.maximum(W, 1.0)[..., None]
    # the empty cells (past the outline at the net's corners) take the nearest filled cell's point
    ind = nd.distance_transform_edt(hole, return_distances=False, return_indices=True)
    P = P[ind[0], ind[1]]
    P = np.stack([nd.gaussian_filter(P[..., c], g['blur'], mode='nearest') for c in range(3)], -1)
    ds = np.linalg.norm(P[1:, :] - P[:-1, :], axis=2)
    dt = np.linalg.norm(P[:, 1:] - P[:, :-1], axis=2)
    s = np.concatenate([np.zeros((1, g['nz'])), np.cumsum(ds, axis=0)], axis=0)
    t = np.concatenate([np.zeros((g['na'], 1)), np.cumsum(dt, axis=1)], axis=1)
    coord = np.stack([np.clip(ia, 0, g['na'] - 1), np.clip(iz, 0, g['nz'] - 1)])
    su = nd.map_coordinates(s, coord, order=1, mode='nearest')
    tu = nd.map_coordinates(t, coord, order=1, mode='nearest')
    # the flow: a stream function on the sheet, its displacement (d psi / dt, -d psi / ds) added to (s, t)
    res = g['res']
    ns, nt = int(s.max() / res) + 4, int(t.max() / res) + 4
    psi = np.random.default_rng(g['seed']).standard_normal((ns, nt))
    psi = nd.gaussian_filter(psi, g['feature'] / (2.0 * res), mode='wrap')
    lap = nd.laplace(psi, mode='wrap') / (res * res)
    psi = psi * (g['rot'] / max(float((0.5 * lap).std()), 1e-12))
    dsf = np.gradient(psi, res, axis=1)
    dtf = -np.gradient(psi, res, axis=0)
    c2 = np.stack([su / res, tu / res])
    u = su + nd.map_coordinates(dsf, c2, order=1, mode='nearest')
    v = tu + nd.map_coordinates(dtf, c2, order=1, mode='nearest')
    return np.stack([u, v, np.zeros_like(u)], 1).astype(np.float32)


# (10-31, B9) THE GRANULES' SITES (cell_mode 5): M1d's elytral granules are packed tight at an even density with local order and
# defects, elongated a little along a faint flow (b9/out/photo, b9/p01: a relaxed Poisson set; B8's lattice rows curled into whorls).
# density per mm^2 of the surface; aniso the granules' long to short axis (and the packing's metric: the sites lie further apart
# along the long axis), along the body's axis turned by flow_rot (rad rms) x a smooth field of flow_feature mm, each granule turned
# again by rot_jit (rad rms) in its own frame; iters / step the relaxation (a repulsion whose kernel reaches past the spacing, so
# voids close; few steps keep it irregular, many grow hexagonal domains, i.e. rows); kappa the granule's size against half the mean
# metric distance to its three nearest sites (the packing tight, small gaps where three meet), size_jit / ht_jit lognormal / normal
# jitters, mod_amp x a field of mod_feature mm the granules' heights drifting in patches (M1d's spectrum carries energy at 0.2-0.6
# mm); pole: the granules round off where the surface faces along the body's axis (|N.z| between the two: the apex, where the axis
# has no direction on the surface); cell the table's least grid cell (mm); seed the layout's
# (11-01, B9, chosen in the engine on the B8 bake: b9/trials g1-g5, the ely_mid_L box under the comparison dome beside M1d at its
# pixel, gated by t09's in-band shape, bar 0.15) density 120 (at 165 the spectrum sat short of M1d's: a deficit at 0.11-0.17 mm, an
# excess at 0.067-0.085), no height modulation (any drift of the granules' heights at 0.1-0.35 mm put energy at 0.2-0.6 mm, where
# M1d has little), aniso 1.5, kappa 1.05: t09 shape 0.140 / 0.140 / 0.163 over three seeds (B8's lattice 0.198), peak 0.091-0.099,
# median 0.104-0.106 (M1d 0.091 / 0.107), L 0.035, contrast 0.37-0.38 (B8 0.29, M1d 0.56). Elongated 2.0-2.2 in a 0.4-0.6 mm flow
# the granules read as swirled fur and t09 rose to 0.33
# (11-01, B9, the bake: the elytron re-baked alone with these sites (37,010 granules, 308.4 mm2) and merged into B8's pages, b9/m01_merge)
# MEASURED ON THE BAKE (b9/k04b9_grain_census.py, 794 windows of 0.5 mm on the dorsal disc): the beads' elongation p50 / p90 1.38 / 1.65
# against the design's 1.5, i.e. OVER THE DESIGN p50 0.92 / p90 1.10 (B8's sheet 1.17 / 1.77; 28 % of its disc over 2x, here 0.25 %);
# t09 on the whole animal's ely_mid_L still (5.5 s) 0.138 PASS (B8 0.194); in the dorsal still the disc read 0.0324 against B8's 0.0364
# with B8's skin tables (the heights sit lower, mean hc -0.13 against B8's +0.15, so the cavity term darkens more): stag_beetle_skin's
# elytron albedo carries the difference
GRAIN_SITES = dict(density=120.0, aniso=1.5, flow_rot=0.30, flow_feature=1.0, rot_jit=0.25, iters=12, step=0.5, kappa=1.05,
                   size_jit=0.10, ht_jit=0.15, mod_amp=0.0, mod_feature=0.35, pole=(0.75, 0.95), cell=0.10, seed=29)
_GRAIN_CACHE = {}


def _field3(P, feature, seed, n_waves=48):
    """a smooth random field of the point (life mm), ~unit variance, blobs of ~`feature` mm: n_waves plane waves in random 3D
    directions (a solid function of the point: no sheet, nothing to step at a seam)"""
    rng = np.random.default_rng(seed)
    k = rng.standard_normal((n_waves, 3))
    k /= np.linalg.norm(k, axis=1, keepdims=True)
    k *= (np.pi / feature) * rng.uniform(0.7, 1.3, (n_waves, 1))
    ph = rng.uniform(0.0, 2.0 * np.pi, n_waves)
    return np.sqrt(2.0 / n_waves) * np.cos(np.asarray(P, np.float64) @ k.T + ph).sum(1)


def _grain_frames(P, Nv, cfg):
    """per site: the unit normal, the long axis (the body's axis on the surface turned by the flow), the metric's sqrt(aniso)
    (rounded off toward the pole)"""
    n = Nv / np.maximum(np.linalg.norm(Nv, axis=1, keepdims=True), 1e-12)
    ez = np.array([0.0, 0.0, 1.0])
    et = ez[None, :] - n * n[:, 2:3]
    alt = np.array([1.0, 0.0, 0.0])[None, :] - n * n[:, 0:1]
    ln = np.linalg.norm(et, axis=1, keepdims=True)
    et = np.where(ln > 1e-3, et / np.maximum(ln, 1e-12), alt / np.maximum(np.linalg.norm(alt, axis=1, keepdims=True), 1e-12))
    es = np.cross(n, et)
    th = cfg['flow_rot'] * _field3(P, cfg['flow_feature'], cfg['seed'] + 1)
    ea = et * np.cos(th)[:, None] + es * np.sin(th)[:, None]
    az = np.abs(n[:, 2])
    lo, hi = cfg['pole']
    t = np.clip((az - lo) / (hi - lo), 0.0, 1.0)
    an = 1.0 + (cfg['aniso'] - 1.0) * (1.0 - t * t * (3.0 - 2.0 * t))
    return n, ea, np.sqrt(an)


def grain_sites(V, F, N, w, cfg=None, log=None):
    """(10-31, B9) the granules' sites on a part's limit (life mm: V vertices, F triangles, N vertex normals, w the cells mask per
    vertex): random darts by area over the triangles the mask reaches, relaxed `iters` times in the tangent planes by a repulsion
    in the granules' anisotropic metric (each move projected back onto the limit by the nearest vertex's tangent plane; a move
    that leaves the mask's reach is refused), then each site's granule: its long axis (the flow's, turned by its own jitter), its
    semi-axes (kappa x half the mean metric distance to its three nearest sites, x sqrt(aniso) along and over it across) and its
    height. Returns per-site arrays and the census"""
    from scipy.spatial import cKDTree
    cfg = dict(GRAIN_SITES, **(cfg or {}))
    V = np.asarray(V, np.float64)
    N = np.asarray(N, np.float64)
    F = np.asarray(F, np.int64)
    w = np.asarray(w, np.float64)
    rng = np.random.default_rng(cfg['seed'])
    tri = F[w[F].max(1) > 0.005]
    a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    area = float(ar.sum())
    ns = int(round(cfg['density'] * area))
    k = rng.choice(len(tri), ns, p=ar / ar.sum())
    r1, r2 = np.sqrt(rng.random(ns)), rng.random(ns)
    P = a[k] * (1.0 - r1)[:, None] + b[k] * (r1 * (1.0 - r2))[:, None] + c[k] * (r1 * r2)[:, None]
    vid = np.unique(tri)
    Vr, Nr, wr = V[vid], N[vid], w[vid]
    tv = cKDTree(Vr)
    d0 = np.sqrt(2.0 / (np.sqrt(3.0) * cfg['density']))
    refused = 0
    for it in range(cfg['iters']):
        _, iv = tv.query(P)
        n, ea, sa = _grain_frames(P, Nr[iv], cfg)
        eb = np.cross(n, ea)
        _, J = cKDTree(P).query(P, k=21)
        J = J[:, 1:]
        D = P[:, None, :] - P[J]
        D = D - n[:, None, :] * (D * n[:, None, :]).sum(-1, keepdims=True)
        da = (D * ea[:, None, :]).sum(-1) / sa[:, None]
        db = (D * eb[:, None, :]).sum(-1) * sa[:, None]
        r = np.sqrt(da * da + db * db) / d0
        wg = np.exp(-r * r / 0.5)
        ua = cfg['step'] * (wg * da).sum(1)
        ub = cfg['step'] * (wg * db).sum(1)
        mag = np.sqrt(ua * ua + ub * ub)
        s = np.minimum(1.0, 0.3 * d0 / np.maximum(mag, 1e-12))
        Pn = P + ea * (ua * s * sa)[:, None] + eb * (ub * s / sa)[:, None]
        _, iv2 = tv.query(Pn)
        Pn = Pn - Nr[iv2] * ((Pn - Vr[iv2]) * Nr[iv2]).sum(1, keepdims=True)
        ok = wr[iv2] > 0.002
        refused += int((~ok).sum())
        P = np.where(ok[:, None], Pn, P)
    _, iv = tv.query(P)
    n, ea, sa = _grain_frames(P, Nr[iv], cfg)
    ang = cfg['rot_jit'] * rng.standard_normal(len(P))
    es = np.cross(n, ea)
    ea = ea * np.cos(ang)[:, None] + es * np.sin(ang)[:, None]
    eb = np.cross(n, ea)
    _, J = cKDTree(P).query(P, k=4)
    D = P[:, None, :] - P[J[:, 1:]]
    D = D - n[:, None, :] * (D * n[:, None, :]).sum(-1, keepdims=True)
    da = (D * ea[:, None, :]).sum(-1) / sa[:, None]
    db = (D * eb[:, None, :]).sum(-1) * sa[:, None]
    dm = np.sqrt(da * da + db * db).mean(1)
    # (the size held within 0.7-1.3 of the spacing and its jitter within two sigmas: the table's grid cell is twice the largest
    # semi-axis, and one outlier granule would double every cell's population)
    rr = cfg['kappa'] * 0.5 * np.clip(dm, 0.7 * d0, 1.3 * d0) * \
        np.exp(cfg['size_jit'] * np.clip(rng.standard_normal(len(P)), -2.0, 2.0))
    ht = np.clip(1.0 + cfg['ht_jit'] * rng.standard_normal(len(P)), 0.6, 1.4) * \
        (1.0 + cfg['mod_amp'] * _field3(P, cfg['mod_feature'], cfg['seed'] + 3))
    dn = np.sqrt(da * da + db * db).min(1) / d0
    census = dict(sites=int(len(P)), area_mm2=round(area, 2), d0_mm=round(float(d0), 4),
                  nn_metric_over_d0_p5_p50_p95=[round(float(x), 3) for x in np.percentile(dn, (5, 50, 95))],
                  mean3_over_d0_p5_p50_p95=[round(float(x), 3) for x in np.percentile(dm / d0, (5, 50, 95))],
                  semi_axes_mm_p50=[round(float(np.median(rr * sa)), 4), round(float(np.median(rr / sa)), 4)],
                  semi_axis_max_mm=round(float((rr * sa).max()), 4), aniso_p50=round(float(np.median(sa * sa)), 3),
                  refused_moves=refused)
    if log:
        log(f'[grain_sites] {census}')
    return dict(P=P, ea=ea, ra=rr * sa, rb=rr / sa, ht=ht, n=n, census=census)


def grain_table(S, cell=None):
    """the sites as the Warp side reads them (grain_granules): a dense grid of cells (at least twice the largest semi-axis) whose
    site offsets (nx ny nz + 1 floats, exact integers) are followed by the sites' records (x, y, z, long axis, ra, rb, height),
    sorted by cell. Returns ({origin, cell, dims}, the float32 tail)"""
    P = S['P']
    rmax = float(max(S['ra'].max(), S['rb'].max()))
    c = max(float(cell or GRAIN_SITES['cell']), 2.05 * rmax)
    org = P.min(0) - c
    dims = (np.ceil((P.max(0) + c - org) / c).astype(np.int64) + 1)
    ci = np.floor((P - org) / c).astype(np.int64)
    cid = (ci[:, 0] * dims[1] + ci[:, 1]) * dims[2] + ci[:, 2]
    o = np.argsort(cid, kind='stable')
    ncell = int(np.prod(dims))
    off = np.zeros(ncell + 1, np.float64)
    off[1:] = np.cumsum(np.bincount(cid, minlength=ncell))
    assert off[-1] < 2 ** 24 and ncell < 2 ** 26, 'the grain table outgrew float32 indices'
    rec = np.concatenate([P[o], S['ea'][o], S['ra'][o, None], S['rb'][o, None], S['ht'][o, None]], 1)
    tail = np.concatenate([off, rec.ravel()]).astype(np.float32)
    return dict(origin=org, cell=c, dims=dims, cells=ncell), tail


def params_full(region, seed, V, F, N, M4, log=None):
    """params() and, for a region that draws granules (its recipe's grain with cell_mode 5), the sites' table after them: the
    whole par array the bake and its trials pass (the sites built on this limit, cached per limit and settings in-process)"""
    p = params(region, seed, grain_ok=True)
    r = RECIPE[region]
    if not r.get('grain') or r.get('cell_mode') != 5.0:
        return p
    key = _grain_key(V, F)
    if key not in _GRAIN_CACHE:
        S = grain_sites(V, F, N, np.asarray(M4)[:, 3], log=log)
        _GRAIN_CACHE[key] = (S, grain_table(S))
    S, (hdr, tail) = _GRAIN_CACHE[key]
    p[27] = 1.0
    p[30:33] = hdr['origin']
    p[33] = hdr['cell']
    p[34:37] = hdr['dims']
    if log:
        log(f'[params_full] {region}: {S["census"]["sites"]:,} granules, grid {tuple(int(x) for x in hdr["dims"])} of '
            f'{hdr["cell"]:.4f} mm, par {NPAR + len(tail):,} floats')
    return np.concatenate([p, tail]).astype(np.float32)


def _grain_key(V, F):
    """the in-process cache's key: the limit (every 97th vertex, the counts) and the settings"""
    import hashlib
    Va = np.ascontiguousarray(np.asarray(V, np.float64)[::97])
    return hashlib.sha1(Va.tobytes() + repr((len(V), np.shape(F), sorted(GRAIN_SITES.items()))).encode()).hexdigest()


def grain_cached(V, F):
    """the sites params_full built for this limit and these settings in this process, or None"""
    v = _GRAIN_CACHE.get(_grain_key(V, F))
    return None if v is None else v[0]


def micro_masks(region, name, V, N, center=None, axis=None, side_sign=1.0, sutures=None, spine=None, occluder=None):
    """per limit vertex (life mm, world): m = (pit density, setae amount, groove profile, cells amount) and the setae's
    direction d. The rules per region (b06b's readings): the pronotum's disc dense (87 / mm^2) and its sides sparse (39),
    its front and hind margins' setal fringes; the elytra's microsculpture on the outer face, the inner face smooth; the
    tarsi's golden brushes on their ventral face; the tibiae's setae on the inner (medial-ventral) edge; the venter's pits
    and pubescence on its ventral face, the ventrites' sutures as grooves. (B6) occluder: plan_cover's f over the head,
    for the pronotum's fringes (fringe_mask's over)"""
    V = np.asarray(V, np.float64)
    N = np.asarray(N, np.float64)
    n = len(V)
    m = np.zeros((n, 4), np.float32)
    d = np.zeros((n, 3), np.float32)
    down = -N[:, 1]
    sm = lambda a, b, x: np.clip((x - a) / (b - a), 0.0, 1.0) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0.0, 1.0))  # noqa
    if axis is None:
        c0 = V.mean(0)
        w, U = np.linalg.eigh(np.cov((V - c0).T))
        axis = U[:, 2]
    axis = np.asarray(axis, np.float64) / np.linalg.norm(axis)
    d[:] = axis
    if region == 'head':
        m[:, 3] = 1.0
        m[:, 0] = 0.5                                   # pits in the network's cells
        m[:, 1] = 0.15 * sm(0.2, 0.7, down)             # sparse setae on the underside
        d[:] = np.array([0.0, 0.0, -1.0])
        # (10-29, B5) the MENTUM's suture as a groove (out of the head's cage since insect_cage b3h-2): M3v's trapezoid
        # (MENTUM trap, the smoothing B3f gave it), a gaussian of FWHM 0.10 mm about its outline in plan, on the
        # downward-facing underside only (the head's world y under 14.9: h 9.8)
        m[:, 2] = (mentum_groove(V) * sm(0.30, 0.60, down) * (V[:, 1] < 14.9)).astype(np.float32)
        # (10-29, B7b) and the maroon plate's own suture (M3v: a crisp edge round the raised plate in front of the
        # prosternal fringe; MENTUM_PLATE)
        m[:, 2] = np.maximum(m[:, 2], (mentum_plate_groove(V) * sm(0.30, 0.60, down) * (V[:, 1] < 14.9))
                             .astype(np.float32))
        # (10-30, B8) the plate POLISHED (M3v: a glossy cushion, no worms, no hairs, a few fine punctures): the head's relief
        # held off it when its dome is on
        if RECIPE['head'].get('dome', 0.0) > 0.0:
            # (only the vertices over the plate's box and under the head: the outline's polygon test on the L6 limit's 12.5 M
            # vertices would take minutes)
            mp = MENTUM_PLATE
            near = np.nonzero((V[:, 1] < 14.9) & (down > 0.30) & (np.abs(V[:, 0]) < mp['half'][0] * 1.2) &
                              (np.abs(V[:, 2] - mp['center'][1]) < mp['half'][1] * 1.2))[0]
            plate = (sm(0.0, 0.12, mentum_plate_inside(V[near])) * sm(0.30, 0.60, down[near])).astype(np.float32)
            m[near, 3] *= 1.0 - plate
            m[near, 1] *= 1.0 - plate
            m[near, 0] *= 1.0 - 0.8 * plate
    elif region == 'pronotum':
        x = np.abs(V[:, 0])
        half = np.maximum(np.interp(V[:, 2], *_half_width(V)), 1e-6)
        r = x / half
        m[:, 0] = 1.0 - 0.55 * sm(0.45, 0.85, r)           # disc 1 -> sides 0.45 (b06: at 0.45 (39 / 87) the side's
        #                                                    ring-light contrast was 0.50 against the photo's 0.97;
        #                                                    10-28 with the deeper punctures: 0.70 overshot the side;
        #                                                    the one-size punctures (t5) at 0.55: 1.37, back to M1d's
        #                                                    measured 39 / 87)
        if PIT_CLUSTER.get('amount', 0.0) > 0.0:
            # (10-29, B7) M1d's punctures CROWD IN CLUSTERS with black chitin between (B6's notes, the photo at its own
            # pixel): the density thinned where a plan noise of `feature` mm falls low, so the pits keep their size and
            # their crowding inside a cluster (B6's uniform field of one-size pits read as an even grey stipple)
            pc = PIT_CLUSTER
            nzc = _plan_noise(pc['seed'], pc['feature'], lo=(-9.0, -20.0), hi=(9.0, -8.0), mirror=False)(V[:, 0], V[:, 2])
            m[:, 0] *= 1.0 - pc['amount'] * (1.0 - sm(pc['edge'][0], pc['edge'][1], nzc))
        m[:, 3] = 1.0
        # the front and hind margins' fringes (0.3-0.5 mm bands, [M-an]). (10-29, B6) ON THE DORSAL MARGINS ONLY: B5's
        # rule (every point within 0.45 mm of the z extremes) took the whole collar face under the head and the hind
        # face (265 K / 526 K L6 vertices facing +-z against ~25 K on the dorsal margin): the "orange disc" under the head,
        # dimmed in the skin, which took M1d's two orange fringe lines with it. Now per 0.1 mm column of x: the dorsal
        # surface's front and hind EDGES (its points facing up, N_y > FRINGE_MASK up: the margin's turn included), the
        # band behind the front edge / ahead of the hind edge `depth` deep on the dorsal side (M1d's lines 0.25-0.35 mm
        # in plan), and the faces' top `face` below each edge (the hairs leave the margin itself)
        zf, zb = V[:, 2].max(), V[:, 2].min()
        if FRINGE_MASK.get('b5_rule'):           # B5's rule, kept for the B6 trials' reproduction of B5's bake
            fr = np.maximum(1.0 - (zf - V[:, 2]) / 0.45, 0.0) + np.maximum(1.0 - (V[:, 2] - zb) / 0.45, 0.0)
            m[:, 1] = np.clip(fr, 0.0, 1.0) * 0.9
        else:
            m[:, 1] = fringe_mask(V, N, over=occluder) * FRINGE_MASK['amount']
        d[:] = np.where((V[:, 2] > 0.5 * (zf + zb))[:, None], np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0]))
    elif region == 'elytron':
        up = N @ np.array([np.sign(side_sign) * 0.35, 0.94, 0.0])
        outer = sm(-0.25, 0.15, up)
        m[:, 3] = outer
        m[:, 0] = 0.6 * outer
        m[:, 1] = 0.0
        if RECIPE['elytron'].get('cell_mode', 0.0) == 4.0:      # (10-30, B8) the packed grain's sheet (no setae here)
            d[:] = grain_sheet(V, N, outer)
    elif region == 'scutellum':
        m[:, 0] = 0.8
        m[:, 3] = 1.0
    elif region == 'mandible':
        m[:, 0] = 1.0
        m[:, 3] = 0.0
        # the mandible's underside setae near the base: sparse (10-28 restart: at 0.25 the engine's ventral still showed
        # a brown speckled underside where M3v's mandibles are black and glossy with fine bright punctures)
        m[:, 1] = 0.10 * sm(0.3, 0.8, down)
    elif region == 'venter':
        ven = sm(0.0, 0.5, down)
        # the punctures densest on the metaventrite (M3v: 82 / mm^2 of bright specks), a little sparser under the
        # abdomen's setae
        m[:, 0] = ven * np.where(V[:, 2] < -31.5, 0.8, 1.0)
        m[:, 3] = ven
        abd = V[:, 2] < -31.5
        if VENTER_MASK.get('mode') == 'patches':
            # (10-29, B7) M3v's DISTINCT golden hair patches over glossy black chitin (venter_hair: the layout read on M3v,
            # keyed to this model's own sutures), and the side wall under the elytral edge no longer a bare mirror (the
            # B6 check's pale band in the lateral still: ven 0 there gave it no punctures and no cells): its punctures and
            # cells at a share of the ventral face's (its darkness is the elytra's shadow, the material pass's cross AO)
            wall = VENTER_MASK['wall']
            m[:, 0] = np.maximum(m[:, 0], wall[0] * (1.0 - ven))
            m[:, 3] = np.maximum(m[:, 3], wall[1] * (1.0 - ven))
            m[:, 1] = ven * venter_hair(V, sutures)
            if VENTER_MASK.get('side') is not None:
                # (10-29, B7b) THE FLANK BLACK WITH SPARSE GOLD (M1l, M1d's own specimen; the B7 check: the hero's band
                # under the elytral edge read tan, the ventral face's lateral patches seen from the side): the patches
                # keep M3v's layout where the venter faces down (the ventral face M3v shows) and thin to `sparse` of
                # their hairs where it turns to the side, between down lo and hi (the hero sees the venter where it
                # faces more than ~30 deg off straight down)
                lo, hi, sparse = VENTER_MASK['side']
                m[:, 1] *= sparse + (1.0 - sparse) * sm(lo, hi, down)
        else:
            # the pubescence where M3v shows it (10-28): golden on the sides and along each ventrite's hind margin (just
            # in front of the suture behind it), sparse in the dark glabrous middle; the metaventrite sparse but for its
            # sides
            lat = sm(1.6, 5.0, np.abs(V[:, 0]))
            marg = np.zeros(n)
            for z_k, fw in (sutures or ()):
                marg = np.maximum(marg, np.exp(-0.5 * ((V[:, 2] - (z_k + 0.45)) / 0.40) ** 2))
            # (10-28, the engine's ventral still beside M3v: floors of 0.18 / 0.12 still speckled the glabrous middle gold
            # all over, a sandy brown plate; M3v's middle is dark and bare)
            m[:, 1] = 0.60 * ven * np.where(abd, np.maximum(0.05, np.maximum(lat, 0.85 * marg)),
                                            np.maximum(0.04, 0.7 * lat))
        d[:] = np.array([0.0, 0.0, -1.0])
        if sutures:
            g = np.zeros(n)
            for z_k, fw in sutures:
                sig = fw / 2.3548
                g = np.maximum(g, np.exp(-0.5 * ((V[:, 2] - z_k) / sig) ** 2))
            m[:, 2] = (g * ven * (V[:, 2] < -24.0)).astype(np.float32)
        # the metaventral midline groove (M3v): x ~ 0 on the metaventrite, width 0.06 mm
        mv = np.exp(-0.5 * (V[:, 0] / (0.06 / 2.3548)) ** 2) * ven * ((V[:, 2] < -19.0) & (V[:, 2] > -24.0))
        m[:, 2] = np.maximum(m[:, 2], 0.6 * mv)
    # (10-28 restart, the engine's stills beside M3v: the legs read as tan wood grain, golden streaks over half of each
    # femur and the whole inner tibia (coverage ~0.5 and ~2: m x the seta's mean length x width / spacing^2), where M3v's
    # legs are glossy black-brown with sparse setae and a fringe on the tibia's inner edge: both narrowed to the inner
    # edge (med 0.45-0.9), the femur's sparse)
    elif region in ('coxa', 'trochanter', 'femur'):
        m[:, 0] = 0.7
        m[:, 3] = 1.0
        med = N @ np.array([-np.sign(side_sign) * 0.7, -0.7, 0.0])
        m[:, 1] = 0.15 * sm(0.45, 0.9, med)
    elif region == 'tibia':
        m[:, 0] = 0.7
        m[:, 3] = 1.0
        med = N @ np.array([-np.sign(side_sign) * 0.7, -0.7, 0.0])
        m[:, 1] = 0.55 * sm(0.45, 0.9, med)              # the inner edge's fringe (12.5 % of the hind leg's plan)
    elif region == 'tarsus':
        m[:, 0] = 0.5
        m[:, 3] = 1.0
        m[:, 1] = 1.0 * sm(-0.1, 0.5, down)              # the golden ventral brushes (20-24 % of the leg's plan)
    elif region in ('antenna', 'mouthparts'):
        m[:, 0] = 0.5
        m[:, 3] = 1.0
        # (10-28, the first engine look: at 0.5 everywhere the antennae read as tan fuzzy ropes) L. cervus's antennae are
        # dark and sparsely setose; the palps hairier (the orange maxillary brushes, BEETLE_PLAN §5.4). (10-28 restart: at
        # 0.12 the scape still read as a barked twig in the close stills) the scape and funicle nearly glabrous, the
        # club's lamellae velvety (their sensory pubescence)
        if region == 'antenna':
            m[:, 1] = 0.30 if name.startswith('lamella') else 0.03
            # (10-29, B5: the funicle read as twisted rope, the club as a dried mushroom) the scape and funicle glabrous
            # and glossy (no setae, a whisper of cells), the club's pubescence the chitin pass's velvet sheen
            if not name.startswith('lamella'):
                m[:, 1] = 0.0
                m[:, 0] = 0.3
        else:
            m[:, 1] = 0.40
    elif region == 'membrane':
        m[:, 3] = 1.0
    # the setae lie distally: the part's axis pointing away from the body's centre line
    if region in ('coxa', 'trochanter', 'femur', 'tibia', 'tarsus', 'antenna', 'mouthparts', 'mandible'):
        if spine is not None:
            dd = np.asarray(spine[1], np.float64) - np.asarray(spine[0], np.float64)
            d[:] = dd / max(np.linalg.norm(dd), 1e-9)
        elif center is not None:
            if axis @ (V.mean(0) - np.asarray(center)) < 0:
                d[:] = -axis
    return m, d


# (10-29, B7) the VENTER's golden pubescence as M3v shows it: glossy black chitin with DISTINCT golden hair patches (B6's
# rule, mode 'b6', laid a thin even gold on the sides and the ventrites' margins, which the material dimmed until the venter
# read as one flat olive-grey). Read on M3v (b7 notes; the other specimen's plan frame, so the layout is keyed to this
# model's own sutures and coxae): the metaventrite golden over most of it but a bare midline groove, two black glabrous
# ovals either side of its middle and the mesoventral process's black front; each abdominal ventrite golden on its sides
# with a black middle (the second's gold reaching further in), its hind margin a bare reddish band just in front of the
# suture behind it; edges wandering (a smoothed noise in plan, mirrored in x). Each patch dense (`dense`: the hairs cover
# the chitin), the black between bare. wall: the side wall's puncture and cell shares (pits, cells)
VENTER_MASK = dict(mode='patches', dense=0.85, edge=0.30, noise=(0.80, 0.6, 97), fine=(0.35, 0.22, 98),
                   tuft=(0.25, 0.30, 99), midline=(0.55, 0.90), ovals=((4.4, -25.6, 1.55, 1.20),), meso=(-22.4, 2.2, 3.0),
                   metaventrite=(-22.4, -30.6), ventrite_x=(3.8, 1.6, 3.2, 3.6, 4.2), margin=0.35, wall=(0.5, 0.6),
                   side=(0.62, 0.88, 0.15))
#                                     ((10-29, B7b) side: the flank's fade (down lo, hi, the sparse share), micro_masks)
#                                     (edges: a 0.6 mm wander of 0.8 mm plus a 0.22 mm one of 0.35 mm, the hair tufts'
#                                     ragged rims; inside a patch the density varies +-25 % at 0.3 mm, M3v's tufts)


def _plan_noise(seed, sigma, lo=(-10.0, -46.0), hi=(10.0, -14.0), cell=0.05, mirror=True):
    """a smoothed gaussian random field over a plan box (life mm; the venter's by default), unit std, mirrored in x
    (sampled at |x|) unless mirror is False: f(x, z) by bilinear interpolation"""
    from scipy import ndimage as nd_
    rng = np.random.default_rng(seed)
    x0 = 0.0 if mirror else lo[0]
    nx, nz = int((hi[0] - x0) / cell) + 2, int((hi[1] - lo[1]) / cell) + 2
    g = nd_.gaussian_filter(rng.standard_normal((nx, nz)), sigma / cell, mode='reflect')
    g /= max(float(g.std()), 1e-12)

    def f(x, z):
        xx = np.abs(x) if mirror else x - x0
        return nd_.map_coordinates(g, [xx / cell, (z - lo[1]) / cell], order=1, mode='nearest')
    return f


# (10-29, B7) the pronotal punctures' CLUSTERS (micro_masks, pronotum): the share of the density taken where the plan noise
# (feature mm) falls under edge[0] .. edge[1] (in its std); 0: B6's even field. The trials: 0.65-0.75 left black voids
# among isolated rings (g2), 0.30 keeps M1d's crowding with sparser patches between (g3b)
PIT_CLUSTER = dict(amount=0.30, feature=0.25, edge=(-0.6, 0.0), seed=71)


def venter_hair(V, sutures):
    """(10-29, B7) the venter's setae amount per point (life mm, world) from VENTER_MASK's layout (before the ventral-face
    weight): `dense` inside the golden patches, 0 on the black chitin between, the edges soft over `edge` mm and moved by
    the plan noise (amplitude noise[0] mm, feature noise[1] mm)"""
    vm = VENTER_MASK
    sm = lambda a, b, x: np.clip((x - a) / (b - a), 0.0, 1.0) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0.0, 1.0))  # noqa
    x, z = np.asarray(V[:, 0], np.float64), np.asarray(V[:, 2], np.float64)
    ax = np.abs(x)
    nz_ = _plan_noise(vm['noise'][2], vm['noise'][1])(x, z) * vm['noise'][0] + \
        _plan_noise(vm['fine'][2], vm['fine'][1])(x, z) * vm['fine'][0]
    tuft = 1.0 + vm['tuft'][0] * np.clip(_plan_noise(vm['tuft'][2], vm['tuft'][1])(x, z), -1.0, 1.0)
    e = vm['edge']
    inside = lambda dist: sm(-0.5 * e, 0.5 * e, dist)            # noqa: E731  (dist > 0 inside a patch)
    out = np.zeros(len(V))
    zf, zb = vm['metaventrite']
    # the mesoventrite and the metaventrite's front (between the mid coxae): golden sides, the process's black middle
    meso = z > vm['meso'][0]
    out = np.where(meso, inside(ax - vm['meso'][1] - 0.5 * nz_), out)
    # the metaventrite: golden but the midline groove and the two glabrous ovals
    mv = (z <= zf) & (z > zb)
    g = inside(ax - vm['midline'][0] - 0.3 * np.abs(nz_))
    for ox, oz, rx, rz in vm['ovals']:
        r = np.sqrt(((ax - ox) / rx) ** 2 + ((z - oz) / rz) ** 2)
        g = np.minimum(g, inside((r - 1.0) * min(rx, rz) + 0.4 * nz_))
    out = np.where(mv, g, out)
    # the abdomen: per ventrite (from the metaventrite's back to the first suture, then between the sutures) golden on the
    # sides outside ventrite_x[k] (wandering), black in the middle; each ventrite's hind margin bare
    zs = [zb] + sorted((s[0] for s in (sutures or ())), reverse=True) + [-1e9]
    for k in range(len(zs) - 1):
        a, b = zs[k], zs[k + 1]
        sel = (z <= a) & (z > b)
        xk = vm['ventrite_x'][min(k, len(vm['ventrite_x']) - 1)]
        gk = inside(ax - xk - nz_)
        if b > -1e8:
            gk = gk * (1.0 - sm(-0.5 * e, 0.5 * e, vm['margin'] - (z - b)))     # the bare hind margin
        out = np.where(sel, gk, out)
    return np.clip(vm['dense'] * np.clip(out, 0.0, 1.0) * tuft, 0.0, 1.0).astype(np.float32)


MENTUM_GROOVE = dict(fwhm=0.10, n=400, smooth=3.0)   # (10-29, B5) the suture's width [E: M3v's suture line, 1-3 px at
#                                                      42.85 px/mm]; the outline's resampling and smoothing as B3f's
#                                                      (insect_hull smooth_closed(..., 400, 3.0) on the same trapezoid)


def mentum_outline():
    """the mentum's outline in plan (x, z life mm): M3v's trapezoid (heads/insect_cage MENTUM trap, mirrored, resampled and
    smoothed as B3f smoothed it), as (the smoothed polygon R, its densified samples D: steps under 2 um)"""
    from scipy.ndimage import gaussian_filter1d
    from ..heads import insect_cage as IC
    tr = np.asarray(IC.MENTUM['trap'], np.float64)
    P = np.vstack([tr, tr[::-1] * np.array([-1.0, 1.0])])
    Q = np.vstack([P, P[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], MENTUM_GROOVE['n'], endpoint=False)
    R = np.column_stack([np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])])
    R = np.column_stack([gaussian_filter1d(R[:, k], MENTUM_GROOVE['smooth'], mode='wrap') for k in range(2)])
    seg = np.linalg.norm(np.roll(R, -1, axis=0) - R, axis=1)
    k = int(np.ceil(seg.max() / 0.002))
    D = np.concatenate([R + (np.roll(R, -1, axis=0) - R) * (j / k) for j in range(k)])
    return R, D


def mentum_groove(V):
    """(10-29, B5) the mentum's suture profile per point (world life mm; plan x, z = world x, z): exp(-d^2 / 2 sigma^2) of the
    plan distance d to the mentum's outline (mentum_outline), sigma from MENTUM_GROOVE fwhm"""
    from scipy.spatial import cKDTree
    _, D = mentum_outline()
    d, _ = cKDTree(D).query(np.asarray(V, np.float64)[:, [0, 2]])
    sig = MENTUM_GROOVE['fwhm'] / 2.3548
    return np.exp(-0.5 * (d / sig) ** 2)


def mentum_inside(P):
    """(10-29, B7) the plan distance (life mm) of points P (world life mm) to the mentum's outline, positive INSIDE it (the
    material pass's maroon mentum, M3v; the head's underside only: the caller's y test, as micro_masks' groove)"""
    from matplotlib.path import Path
    from scipy.spatial import cKDTree
    R, D = mentum_outline()
    xz = np.asarray(P, np.float64)[:, [0, 2]]
    d, _ = cKDTree(D).query(xz)
    ins = Path(R).contains_points(xz)
    return np.where(ins, d, -d)


# (10-29, B7b) THE MAROON PLATE WHERE M3v SHOWS IT (the lead's B7b item 3; the B7 check: B7's maroon sat on the front
# trapezoid, M3v's deep-maroon raised plate lies directly in front of the prosternal fringe, ~5 mm further back). Read on
# M3v at 60 px / mm (b7b_trials/out/m01/m3v_plate_grid.png): a rounded barrel x -2.70 .. 2.42, z -1.08 .. -5.42 in M3v's
# plan frame, 4.3 mm wide at its front, 5.1 at its middle, 4.9 at its back, its back edge on the fringe (M3v's at z
# -5.5); registered on this model by the fringe (the pronotum's ventral front edge at z -9.0, the head's underside seen from
# below reaching -8.9: b7b_trials m01), centred on the midline. A superellipse |x / a|^n + |z / b|^n = 1 about `center`,
# its half-width narrowed toward the front by `taper` (x scaled by 1 - taper x (z - zc) / b). The trapezoid keeps its
# suture (the grey plate behind the brush, M3v); the plate gets its own (MENTUM_GROOVE's width)
MENTUM_PLATE = dict(center=(0.0, -6.72), half=(2.55, 2.18), n=3.5, taper=0.04, n_pts=400)
assert (MENTUM_PLATE['center'], MENTUM_PLATE['half'], MENTUM_PLATE['n'], MENTUM_PLATE['taper']) == \
    ((0.0, -6.72), (2.55, 2.18), 3.5, 0.04), 'mentum_dome (Warp) holds these numbers as literals: change them together'


def mentum_plate_outline():
    """(10-29, B7b) the maroon plate's outline in plan (x, z life mm): (the polygon R, its densified samples D)"""
    mp = MENTUM_PLATE
    xc, zc = mp['center']
    a, b = mp['half']
    t = np.linspace(0.0, 2.0 * np.pi, mp['n_pts'], endpoint=False)
    c, s = np.cos(t), np.sin(t)
    e = 2.0 / mp['n']
    zz = zc + b * np.sign(s) * np.abs(s) ** e
    xx = xc + a * np.sign(c) * np.abs(c) ** e * (1.0 - mp['taper'] * (zz - zc) / b)
    R = np.column_stack([xx, zz])
    seg = np.linalg.norm(np.roll(R, -1, axis=0) - R, axis=1)
    k = int(np.ceil(seg.max() / 0.002))
    D = np.concatenate([R + (np.roll(R, -1, axis=0) - R) * (j / k) for j in range(k)])
    return R, D


def mentum_plate_inside(P):
    """(10-29, B7b) the plan distance (life mm) of points P (world life mm) to the maroon plate's outline, positive INSIDE
    it (the material pass's maroon, stag_beetle_skin.zone_paint; the head's underside only: the caller's y test)"""
    from matplotlib.path import Path
    from scipy.spatial import cKDTree
    R, D = mentum_plate_outline()
    xz = np.asarray(P, np.float64)[:, [0, 2]]
    d, _ = cKDTree(D).query(xz)
    ins = Path(R).contains_points(xz)
    return np.where(ins, d, -d)


def mentum_plate_groove(V):
    """(10-29, B7b) the plate's suture profile per point (as mentum_groove: a gaussian of MENTUM_GROOVE's FWHM about the
    plate's outline in plan)"""
    from scipy.spatial import cKDTree
    _, D = mentum_plate_outline()
    d, _ = cKDTree(D).query(np.asarray(V, np.float64)[:, [0, 2]])
    sig = MENTUM_GROOVE['fwhm'] / 2.3548
    return np.exp(-0.5 * (d / sig) ** 2)


FRINGE_MASK = dict(up=0.25, sheet=0.3, top=3.0, depth=0.30, face=0.12, col=0.10, amount=0.9,   # (10-29, B6) the
                   slope=(2.0, 4.0), mode='loop', axis_y=None, hind_phi=(112.0, 128.0), across=True)
#                                     pronotum's fringes: the dorsal side's N_y floor, its top sheet per plan cell and its
#                                     band under each column's top (mm), the band's depth behind / ahead of the edge and
#                                     down the face (life mm), the plan cells' width, the setae amount (B5's 0.9); (the B6
#                                     check) the edge's plan slope |dz / dx| over which a column's edge fades out (full to
#                                     1.0 = 45 deg, none past 2.0 = 63 deg: past the angles the run's end is the lateral
#                                     margin, not the front / hind one). (10-29, B7) mode 'loop' (fringe_mask_loop): the
#                                     margins followed ROUND the body's axis (at height axis_y; None: the limit's mid
#                                     height), so the front fringe runs down the sides and across the prosternum's front
#                                     and the hind one down the sides (M1l, M3v), the hind band full to hind_phi[0] deg
#                                     from the top and none past hind_phi[1] (the prosternum's hind edge bare, M3v); 'dorsal'
#                                     is B6's rule (the dorsal margins per x column). (10-29, B7b) slope (1, 2) -> (2, 4):
#                                     round the loop the weight cut nothing but the anterior angles, where the front margin
#                                     swings 1.4 mm forward to the angle's tip (|dz / ds| to 2.0; b7b_trials f03): the gap
#                                     and the ~0.7 mm step there (M1l's fringe runs on round its angle); across: the band's
#                                     depth measured across the margin (B7: along z; False reproduces B7's mask)


def plan_cover(Vo, cell=0.05):
    """(10-29, B6) whether another part's surface lies ABOVE a point: the occluder's vertices (life mm, world; dense: a
    limit) rasterised in plan into `cell` mm cells (their highest y, dilated one cell); returns f(P) -> bool per point, True
    where the occluder stands over P by more than 0.02 mm (the pronotum's front margin under the head's back, unseen from
    above)"""
    from scipy import ndimage as nd_
    Vo = np.asarray(Vo, np.float64)
    lo = Vo[:, [0, 2]].min(0) - 2 * cell
    ij = np.floor((Vo[:, [0, 2]] - lo) / cell).astype(np.int64)
    shp = tuple(ij.max(0) + 3)
    top = np.full(shp, -np.inf)
    np.maximum.at(top, (ij[:, 0], ij[:, 1]), Vo[:, 1])
    top = nd_.grey_dilation(top, size=(3, 3))

    def f(P):
        P = np.asarray(P, np.float64)
        q = np.floor((P[:, [0, 2]] - lo) / cell).astype(np.int64)
        ok = (q[:, 0] >= 0) & (q[:, 1] >= 0) & (q[:, 0] < shp[0]) & (q[:, 1] < shp[1])
        out = np.zeros(len(P), bool)
        out[ok] = top[q[ok, 0], q[ok, 1]] > P[ok, 1] + 0.02
        return out
    return f


def _loop_axis_y(V):
    fa = FRINGE_MASK.get('axis_y')
    return float(fa) if fa is not None else 0.5 * (float(V[:, 1].min()) + float(V[:, 1].max()))


def radial_cover(Vo, axis_y, cell=0.05):
    """(10-29, B7) plan_cover's test ROUND the body's axis (the line x = 0, y = axis_y along z): the occluder's vertices
    (life mm, world; dense: a limit) rasterised in (arc, z) cells, arc = the angle about the axis x a 6 mm radius, `cell`
    mm each (their largest distance from the axis, dilated one cell); returns f(P) -> bool per point, True where the
    occluder stands farther out than P by more than 0.02 mm at P's cell (above the axis this is plan_cover's test: the
    pronotum's front margin under the head's back)"""
    from scipy import ndimage as nd_
    Vo = np.asarray(Vo, np.float64)
    R0 = 6.0
    ang = lambda P: np.arctan2(P[:, 0], P[:, 1] - axis_y) * R0                                       # noqa: E731
    rad = lambda P: np.hypot(P[:, 0], P[:, 1] - axis_y)                                                # noqa: E731
    na = int(np.ceil(2 * np.pi * R0 / cell)) + 1
    z0 = Vo[:, 2].min() - 2 * cell
    nz = int(np.ceil((Vo[:, 2].max() - z0) / cell)) + 3
    ia = np.floor((ang(Vo) + np.pi * R0) / cell).astype(np.int64) % na
    iz = np.floor((Vo[:, 2] - z0) / cell).astype(np.int64)
    top = np.full((na, nz), -np.inf)
    np.maximum.at(top, (ia, iz), rad(Vo))
    top = nd_.grey_dilation(top, size=(3, 3), mode='wrap')

    def f(P):
        P = np.asarray(P, np.float64)
        qa = np.floor((ang(P) + np.pi * R0) / cell).astype(np.int64) % na
        qz = np.floor((P[:, 2] - z0) / cell).astype(np.int64)
        ok = (qz >= 0) & (qz < nz)
        out = np.zeros(len(P), bool)
        out[ok] = top[qa[ok], qz[ok]] > rad(P[ok]) + 0.02
        return out
    return f


def fringe_occluder(Vo, V=None):
    """(10-29, B7) the occluder test fringe_mask wants for its mode: radial_cover about the loop's axis (the pronotum's own
    mid height when V, its limit, is given; FRINGE_MASK axis_y otherwise) or B6's plan_cover"""
    if FRINGE_MASK.get('mode', 'dorsal') == 'loop':
        ay = FRINGE_MASK.get('axis_y')
        if ay is None:
            if V is None:
                raise ValueError('fringe_occluder: the loop mode needs the pronotum limit V or FRINGE_MASK axis_y')
            ay = _loop_axis_y(np.asarray(V, np.float64))
        return radial_cover(Vo, float(ay))
    return plan_cover(Vo)


def fringe_mask(V, N, over=None):
    """the pronotum's two fringe bands per point (life mm, world), 0..1, by FRINGE_MASK's mode: (10-29, B7) 'loop'
    (fringe_mask_loop: the margins round the body) or (B6) 'dorsal' (fringe_mask_dorsal: the dorsal margins only)"""
    if FRINGE_MASK.get('mode', 'dorsal') == 'loop':
        return fringe_mask_loop(V, N, over=over)
    return fringe_mask_dorsal(V, N, over=over)


def fringe_mask_loop(V, N, over=None):
    """(10-29, B7) the pronotum's fringes ROUND THE BODY: M1l shows the front and the hind fringe running down the
    pronotum's sides along its front and hind margins, and M3v the front one going on across the prosternum's front (an
    orange line between the fore coxae), where B6's rule (fringe_mask_dorsal: per x column the DORSAL surface's edges)
    found only their top parts. Per FRINGE_MASK col of arc round the body's axis (the line x = 0, y = axis_y along z; the
    angle phi from the top), the OUTER surface (facing out from the axis, N . radial > up, the outermost sheet at its
    (arc, z) cell within `sheet` and within `top` of the arc's farthest point: the collar's lip and the neck socket's
    ledges inside the front face lie nearer the axis) not covered by `over` (radial_cover over the head: the front margin
    under the head's back): its front edge (largest z) and hind edge (smallest z). Each edge weighed by its slope along
    the margin (|dz / ds|, s the arc length at the edge; full to slope[0], none past slope[1]: where the outline turns to
    run along z, the run's end is the lateral carina, not a margin), the hind edge also by phi (full to hind_phi[0] deg,
    none past hind_phi[1]); the edges, their distance from the axis and the weights interpolated round the loop. The bands
    as B6's: full within 0.6 x depth of an edge on the outer surface, fading to 0 at depth; on the faces beyond the edges
    (front N_z > 0.5, hind N_z < -0.5) full within 0.5 x face of the edge (inward from it), fading to 0 at face"""
    V = np.asarray(V, np.float64)
    N = np.asarray(N, np.float64)
    fm = FRINGE_MASK
    sm = lambda a, b, x: np.clip((x - a) / (b - a), 0.0, 1.0) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0.0, 1.0))  # noqa
    ay = _loop_axis_y(V)
    rel = V[:, 1] - ay
    rho = np.hypot(V[:, 0], rel)
    phi = np.arctan2(V[:, 0], rel)
    rr = np.maximum(rho, 1e-9)
    nout = (N[:, 0] * V[:, 0] + N[:, 1] * rel) / rr
    R0 = float(np.percentile(rho, 90))                     # the arc bins: `col` mm at the outer surface's radius
    nb = max(int(np.ceil(2 * np.pi * R0 / fm['col'])), 16)
    dphi = 2 * np.pi / nb
    b = np.floor((phi + np.pi) / dphi).astype(np.int64) % nb
    zr = np.floor((V[:, 2] - V[:, 2].min()) / fm['col']).astype(np.int64)
    cell = b * (int(zr.max()) + 1) + zr
    rcell = np.full(int(cell.max()) + 1, -np.inf)
    np.maximum.at(rcell, cell, rho)
    rbin = np.full(nb, -np.inf)
    np.maximum.at(rbin, b, rho)
    outer = (nout > fm['up']) & (rho > rcell[cell] - fm['sheet']) & (rho > rbin[b] - fm['top'])
    if over is not None:
        cand = np.nonzero(outer)[0]
        outer[cand[over(V[cand])]] = False
    zf = np.full(nb, -np.inf)
    zb = np.full(nb, np.inf)
    np.maximum.at(zf, b[outer], V[outer, 2])
    np.minimum.at(zb, b[outer], V[outer, 2])
    rf = np.full(nb, -np.inf)
    rb_ = np.full(nb, -np.inf)
    at_f = outer & (V[:, 2] > zf[b] - 0.02)
    at_b = outer & (V[:, 2] < zb[b] + 0.02)
    np.maximum.at(rf, b[at_f], rho[at_f])
    np.maximum.at(rb_, b[at_b], rho[at_b])
    pc = -np.pi + (np.arange(nb) + 0.5) * dphi             # the bins' centre angles

    def around(ze, re, hind):
        """per point: the edge's z and radius interpolated round the loop (periodic, across the bins that have it), the
        edge's weight (its slope along the margin, a 3-bin mean; the hind one also by phi) and whether the point lies
        within those bins"""
        ok = np.isfinite(ze) & np.isfinite(re)
        idx = np.nonzero(ok)[0]
        if len(idx) < 3:
            return None
        zv, rv, pv = ze[idx], re[idx], pc[idx]
        zs = np.convolve(np.pad(zv, 1, mode='wrap'), np.ones(3) / 3.0, mode='valid')
        # the arc length along the edge (its own distance from the axis between neighbouring bins)
        s = np.concatenate([[0.0], np.cumsum(0.5 * (rv[1:] + rv[:-1]) * np.diff(pv))])
        dz = np.abs(np.gradient(zs, s))
        w = np.zeros(nb)
        w[idx] = 1.0 - sm(fm['slope'][0], fm['slope'][1], dz)
        if hind:
            hp = np.radians(fm['hind_phi'])
            w *= 1.0 - sm(hp[0], hp[1], np.abs(pc))
        sl = np.zeros(nb)
        sl[idx] = dz
        inr = ok[b]
        per = 2 * np.pi
        return (np.interp(phi, pv, zv, period=per), np.interp(phi, pv, rv, period=per),
                np.interp(phi, pc, w, period=per), inr, np.interp(phi, pc, sl, period=per))

    out = np.zeros(len(V))
    for e, sgn in ((around(zf, rf, False), 1.0), (around(-zb, rb_, True), -1.0)):
        if e is None:
            continue
        ze, re, w, inr, sl = e
        d = np.where(inr, ze - sgn * V[:, 2], np.inf)
        if fm.get('across'):
            # (10-29, B7b) the band's depth ACROSS the margin, not along z: where the margin runs diagonally (the
            # anterior angle's swing, |dz / ds| up to 2) a band `depth` deep in z was a thin line, half the width it
            # has elsewhere (b7b_trials/out/f03/f03_latz.png)
            d = d / np.sqrt(1.0 + sl * sl)
        top = outer * (1.0 - sm(0.6 * fm['depth'], fm['depth'], d))
        face = (sgn * N[:, 2] > 0.5) & inr & (d < 0.25)
        ff = np.where(face, 1.0 - sm(0.5 * fm['face'], fm['face'], np.where(inr, re - rho, np.inf)), 0.0)
        out = np.maximum(out, w * np.maximum(top, ff))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def fringe_mask_dorsal(V, N, over=None):
    """(10-29, B6) the pronotum's two fringe bands per point (life mm, world), 0..1: per FRINGE_MASK col column of x, the
    dorsal surface's (N_y > up) front edge (its largest z) and hind edge (its smallest); full within 0.6 x depth of an edge
    on the dorsal side, fading to 0 at depth; on the faces below the edges (front N_z > 0.5, hind N_z < -0.5) full within
    0.5 x face of the edge's height, fading to 0 at face. over (plan_cover's f, optional): the dorsal surface counted only
    where nothing lies above it, so the front band starts where the margin comes out from under the head's back (M1d's
    hairs lie forward over the head's back; painted on the margin the head hides, the line was not seen, B6's trial t2).
    (10-29, the B6 check) each column's edge WEIGHED by the edge's plan slope across the columns (FRINGE_MASK slope), and
    the edges, their heights and the weights INTERPOLATED between the column centres: past the anterior and posterior
    angles a column's dorsal run ends on the LATERAL margin (the outline turns to run along z), and each 0.1 mm column
    marked its own short stretch of it: a dashed orange line down both lateral margins in plan, an orange sawtooth along
    the lateral carina in the hero, the stations and the lateral still, and 0.1 mm steps where the front margin turns at
    its angles (M1d and M1l: no hairs on the lateral margin; the bands end at the angles)"""
    V = np.asarray(V, np.float64)
    N = np.asarray(N, np.float64)
    fm = FRINGE_MASK
    sm = lambda a, b, x: np.clip((x - a) / (b - a), 0.0, 1.0) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0.0, 1.0))  # noqa
    col = np.round(V[:, 0] / fm['col']).astype(np.int64)
    c0 = int(col.min())
    col -= c0
    nc = int(col.max()) + 1
    # the dorsal surface: facing up, the TOP sheet at its plan position (within `sheet` of the highest point in its
    # col x col plan cell) and within `top` of its column's highest point (the collar's lower lip and the neck socket's
    # ledges inside the front face face up too, further forward and 6-7 mm lower: taken as the 'front edge' they put the
    # band on the collar's foot, B6's first trial; a column's top alone dropped the hind margin, 1.7 mm under the front)
    ytop = np.full(nc, -np.inf)
    np.maximum.at(ytop, col, V[:, 1])
    zr = np.round(V[:, 2] / fm['col']).astype(np.int64)
    zr -= zr.min()
    cell = col * (int(zr.max()) + 1) + zr
    ycell = np.full(int(cell.max()) + 1, -np.inf)
    np.maximum.at(ycell, cell, V[:, 1])
    dors = (N[:, 1] > fm['up']) & (V[:, 1] > ycell[cell] - fm['sheet']) & (V[:, 1] > ytop[col] - fm['top'])
    if over is not None:
        cand = np.nonzero(dors)[0]
        dors[cand[over(V[cand])]] = False
    zf = np.full(nc, -np.inf)
    zb = np.full(nc, np.inf)
    np.maximum.at(zf, col[dors], V[dors, 2])
    np.minimum.at(zb, col[dors], V[dors, 2])
    # the edges' heights: the dorsal points' y at (or within 0.02 mm of) each column's edge
    yf = np.full(nc, -np.inf)
    yb = np.full(nc, -np.inf)
    at_f = dors & (V[:, 2] > zf[col] - 0.02)
    at_b = dors & (V[:, 2] < zb[col] + 0.02)
    np.maximum.at(yf, col[at_f], V[at_f, 1])
    np.maximum.at(yb, col[at_b], V[at_b, 1])
    xc = (np.arange(nc) + c0) * fm['col']                  # the column centres (life mm)

    def across(ze, ye):
        """per point: the edge's z and height interpolated between the column centres, the edge's weight (by its plan
        slope, a 3-column mean, across the columns that have it) and whether the point lies within those columns"""
        ok = np.isfinite(ze) & np.isfinite(ye)
        idx = np.nonzero(ok)[0]
        if len(idx) < 3:
            return None
        zv = ze[idx]
        zs = np.convolve(np.pad(zv, 1, mode='edge'), np.ones(3) / 3.0, mode='valid')
        w = np.zeros(nc)
        w[idx] = 1.0 - sm(fm['slope'][0], fm['slope'][1], np.abs(np.gradient(zs, xc[idx])))
        inr = (V[:, 0] >= xc[idx[0]] - 0.5 * fm['col']) & (V[:, 0] <= xc[idx[-1]] + 0.5 * fm['col'])
        return np.interp(V[:, 0], xc[idx], zv), np.interp(V[:, 0], xc[idx], ye[idx]), np.interp(V[:, 0], xc, w), inr

    out = np.zeros(len(V))
    # the front edge (its largest z: behind it on the dorsal side, its face facing +z) and the hind edge (its smallest z,
    # taken as the largest -z: ahead of it, its face facing -z)
    for e, sgn in ((across(zf, yf), 1.0), (across(-zb, yb), -1.0)):
        if e is None:
            continue
        ze, ye, w, inr = e
        d = np.where(inr, ze - sgn * V[:, 2], np.inf)
        top = dors * (1.0 - sm(0.6 * fm['depth'], fm['depth'], d))
        face = (sgn * N[:, 2] > 0.5) & inr & (d < 0.25)
        ff = np.where(face, 1.0 - sm(0.5 * fm['face'], fm['face'], np.where(inr, ye - V[:, 1], np.inf)), 0.0)
        out = np.maximum(out, w * np.maximum(top, ff))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def _half_width(V):
    """the pronotum's half-width per z (its outline from the limit vertices): (z grid, half widths) for np.interp"""
    z = V[:, 2]
    zs = np.linspace(z.min(), z.max(), 40)
    hw = np.array([np.abs(V[np.abs(z - zz) < (zs[1] - zs[0]), 0]).max() if np.any(np.abs(z - zz) < (zs[1] - zs[0]))
                   else 1.0 for zz in zs])
    return zs, hw
