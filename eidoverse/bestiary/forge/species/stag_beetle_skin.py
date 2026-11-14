"""B8 THE CHITIN MATERIAL for the beetle (the Bestiary lead's round 10-28): the material pass over b07's baked pages, and the
runtime contract it ships for three r184's MeshPhysicalNodeMaterial.

THE LAYER MODEL (physically plausible, three's lobes):
  * the COAT is the epicuticle's outer surface, the one strong specular interface of insect cuticle (air -> wax / chitin,
    n ~1.55, F0 0.046: BEETLE_PLAN §5.1): three's clear coat (its fixed F0 0.04) at clearcoat 1, its ROUGHNESS VARYING BY
    FORM (the pack's ORM B): polished on the high points (convexity), duller in the punctures and the grooves, and where
    dust lies;
  * the BASE is the pigmented exo- / endocuticle under it: melanin absorbs within a few um, so its colour is a SURFACE
    albedo; its index contrast with the epicuticle is tiny (1.55 -> ~1.60: F0 0.0003), so it adds almost no specular of
    its own: specularIntensity 0.2 at ior 1.56 puts the total at normal incidence at ~0.049 (0.040 + 0.2 x 0.048 through
    the coat), inside the measured chitin's 0.046-0.062 (the plan's one-lobe rule kept in energy: the lead's clear coat
    is that lobe, never a second one on top: the octopus's r4 lesson);
  * a SOFT DIRT term: earth-coloured dust settling in the crevices and the punctures (cavity, the micro pits), dulling
    the coat there;
  * the IRIDESCENT OPTION (remix palette data, staged): three's thin-film iridescence on the base specular (the
    multilayer reflector of a jewel beetle sits under the epicuticle). In three r184 the film's Fresnel
    (PhysicalLightingModel's evalIridescence, the Belcour-Barla airy reflectance, direct and image-based light alike)
    REPLACES the base lobe's Schlick term by the iridescence weight, whatever the specularIntensity, so the base's small
    0.2 lobe becomes the film's full reflectance where the option acts; the option darkens the albedo toward the melanin
    backing, keeps a thinner coat, and drives the film thickness from the baked thickness map (the IRID pack's G:
    low-frequency drift in BASE coordinates, the form's convexity, a per-cell jitter from the microsculpture's cells)
    between the family's [lo, hi] nm at its film ior (IRID_FAMILIES below).

THE PACKS (per texture page, the octopus's slots so loaders bind them; the runtime reads every channel itself):
  albedo   sRGB (exact OETF: INFRA-1's curve, three decodes it exactly)
  normal   glTF +Y, the macro bake with the micro relief composed
  ORM      R ambient occlusion, G base roughness, B COAT roughness (metallicFactor 0: B is data, a plain viewer reads
           metalness 0)
  MASKS    KHR_materials_volume's thickness slot: R soft / thin (membranes, setae, thin edges), G setae (pubescence),
           B accent (claws, the mandible's edges, keels), A the chestnut pattern zone (elytra, mandibles)
  DISPLAY  the emissive slot at factor 0: R part id (stag_beetle REGIONS index / 255), G iridophore mask (where the
           iridescent option may act), B per-cell random (the microsculpture's cells), OPAQUE (B8, below)
  IRID     KHR_materials_iridescence's texture slot at factor 0: R (B5, 10-29) the setae's SHEEN amount (the runtime's
           Charlie sheen lobe: the hairs' gold over a kept coat), G film thickness (0..1 -> the family's range), B coat
           amount, OPAQUE (B8, below)
(10-30, B8) THE PACKS CARRY NO PARTIAL ALPHA. The engine's image path (Deno 2.8.1's createImageBitmap under three's
ImageBitmapLoader) hands the GPU c x 255 / a wherever 0 < a < 255 (b8/d03_decode_compare.py): B7b's DISPLAY (the cell
random in A, partial on 87 / 68 % of texels) and IRID (the sheen in A, 13 / 10 %) arrived with the iridophore mask, the
film and the COAT AMOUNT divided by them. So the data left the alpha: DISPLAY's cell random took B (the wax bloom's
channel, 0 on every texel: that knob is a runtime uniform), IRID's sheen took R (the film mask there was DISPLAY's G
texel for texel; the runtime squares DISPLAY's G as it multiplied the two), and both packs ship as RGB. MASKS keeps its A:
the chestnut zone is 0 or 255 only, which every decode passes unchanged. The glb's material extras say 'pack_layout':
'b8_opaque'; beetle_cuticle.js reads either layout by it
(10-29, B5) the ORM's roughness channels carry the bake's sub-texel normal spread (b07's sub-samples' mean resultant length,
as a vMF variance added to alpha^2); the runtime adds every mip's own spread from the filtered normal's length (Toksvig)
"""
import numpy as np
import warp as wp

from .. import proc as PR
from . import stag_beetle as SB

wp.set_module_options({'enable_backward': False})


def srgb8_lin(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_srgb(L):
    L = np.clip(np.asarray(L, np.float64), 0.0, 1.0)
    return np.where(L <= 0.0031308, 12.92 * L, 1.055 * L ** (1.0 / 2.4) - 0.055)


# ZONE colours, linear (BEETLE_PLAN §5.2 [M-an], the ETH male medians at the plan's absolute scale; M1 = B1's own raw
# elytra (55, 34, 29) shares their hue; M3v's ventral readings by b08's notes). The COAT roughness (10-28, the continuing
# builder): BEETLE_PLAN §5.3's ranges at their glossy ends (elytra 0.25-0.35 "shining and smooth", mandibles 0.2-0.3 the
# shiniest, head and pronotum 0.45-0.6 granulate), lower on the head and pronotum because the micro normal now carries
# the granulate's broken highlights the plan's single roughness had to fake; the draft's 0.07-0.16 read as wet lacquer.
# (b08's first pass: the polish term (polished on the high points) pulls each zone's p50 ~20 % under its value, so the
# values sit ~1.25x the ranges' ends for the p50 to land in them. The head and the elytra came out over their L bars,
# 0.0339 against 0.020-0.030 and 0.0275 against 0.023-0.026: the convexity terms brighten the domed parts, so their
# albedo is scaled x0.87 and x0.90. The membranes: M3v's dark red-brown intersegmental bands, not the draft's pale
# amber, which read as an orange plate behind the head in the first engine still. The MANDIBLES (10-28, the engine
# stills beside M1d / M3v): the plan's ETH medians (L 0.040-0.050) made them the palest part of the animal, a mauve-grey
# beside this specimen's dark chestnut-to-black mandibles (M1d's mandible box 0.010 against its pronotum's 0.032; M3v
# black); they take the elytra's chestnut a shade darker, black toward the tips as before, and so sit under the plan's
# bar on purpose: b08 reports it OFF)
# (10-28 restart: b11's dorsal still beside M1d, the regions' mean sRGB under the stills' light) the HUES by the photo's
# own ratios (linear R : G : B): the pronotum's draft (G over R) read olive, M1d's disc is neutral with a lower blue
# (1 : 1.00 : 0.84); the head 1 : 0.86 : 0.68; the elytra M1d's chestnut 1 : 0.44 : 0.31 (the draft's 0.40 blue read
# desaturated, 1.70 chroma against the photo's 2.03); the mandibles darker again (still 4x the photo's box luminance,
# M1d's mandible box 1 : 0.68 : 0.54 at L ~0.008)
# (10-29, B5: the close-range round. The look check beside M1d: a lacquered toy, the head and pronotum mid-grey satin
# where M1d's are near-black with light only on the relief, the elytra mauve-grey brown against M1d's deep red chestnut, the
# mandibles still ~4x the photo's box, the venter matte cork, the club pale, the neck sleeve an orange disc.) The COAT
# glossier on the head, the pronotum and the venter (0.20-0.24: a flat facet then mirrors the dark room and reads black,
# only the relief's tilted facets catch a light; the runtime's Toksvig term widens the lobe again at distance by the relief's
# own variance per mip, so the head reads as a soft sheen there rather than a mirror); the albedo near-black on the head
# and the pronotum (their mean in the photo is the relief's highlights over black); the elytra a deeper, redder chestnut
# (linear 1 : 0.38 : 0.25: the photo's mean carries the coat's grey highlights, the pigment is redder than the mean); the
# mandibles reddish chestnut at the base (M1d: dark red-brown, black toward the tips: the lnL term); the venter and legs
# black-brown under glossy coats (their hairs' gold is a SHEEN now, below); the antennae black and glossy; the membranes
# M3v's dark red-brown, not amber
# (10-29, B5, B5's first stills beside M1d / M3v) the elytra redder still (linear 1 : 0.30 : 0.20: under the Toksvig satin
# they read brown beside M1d's port-wine disc), the mandibles more polished, the legs a glossy red-brown (M3v; they read
# as grey tubes)
ZONE = dict(
    elytron=dict(albedo=(0.0420, 0.0128, 0.0082), coat_r=0.24, base_r=0.50, ior=1.56, chestnut=1.0, irid=1.0),
    # (10-29, B5, M1d's mandible at its own pixel: a deep MAROON red, mirror-glossy, black along the inner edge and the
    # teeth, sparse bright-lipped punctures on smooth chitin) redder than the elytra's chestnut (linear 1 : 0.27 : 0.19)
    # (the final stills: at 0.032 red the mandibles read a lighter, redder maroon than M1d's, near-black with the red in
    # the light) darker, the hue kept
    mandible=dict(albedo=(0.0240, 0.0066, 0.0047), coat_r=0.14, base_r=0.45, ior=1.58, chestnut=1.0, irid=1.0),
    head=dict(albedo=(0.0160, 0.0145, 0.0125), coat_r=0.20, base_r=0.50, ior=1.62, chestnut=0.0, irid=1.0),
    # (10-29, B6) the pronotum's ground darker, toward the L floor (M1d's disc black between its pits; B6's trials under the
    # dome: with the crowded pits and their occluded walls its ratio to the elytral disc 0.656 against M1d's 0.639; the
    # whole model after the bake 0.694: 0.0120 -> 0.0110)
    pronotum=dict(albedo=(0.0110, 0.0108, 0.0096), coat_r=0.20, base_r=0.50, ior=1.62, chestnut=0.0, irid=1.0),
    scutellum=dict(albedo=(0.0150, 0.0148, 0.0130), coat_r=0.22, base_r=0.50, ior=1.62, chestnut=0.0, irid=1.0),
    venter=dict(albedo=(0.0160, 0.0135, 0.0110), coat_r=0.24, base_r=0.50, ior=1.62, chestnut=0.0, irid=0.6),
    coxa=dict(albedo=(0.0185, 0.0108, 0.0082), coat_r=0.24, base_r=0.55, ior=1.62, chestnut=0.0, irid=0.8),
    trochanter=dict(albedo=(0.0185, 0.0108, 0.0082), coat_r=0.24, base_r=0.55, ior=1.62, chestnut=0.0, irid=0.8),
    femur=dict(albedo=(0.0185, 0.0108, 0.0082), coat_r=0.24, base_r=0.55, ior=1.62, chestnut=0.0, irid=0.8),
    tibia=dict(albedo=(0.0192, 0.0110, 0.0084), coat_r=0.26, base_r=0.55, ior=1.62, chestnut=0.0, irid=0.8),
    tarsus=dict(albedo=(0.0215, 0.0130, 0.0098), coat_r=0.32, base_r=0.58, ior=1.62, chestnut=0.0, irid=0.7),
    claw=dict(albedo=(0.0300, 0.0180, 0.0120), coat_r=0.22, base_r=0.45, ior=1.60, chestnut=0.0, irid=0.5),
    antenna=dict(albedo=(0.0150, 0.0126, 0.0106), coat_r=0.26, base_r=0.55, ior=1.62, chestnut=0.0, irid=0.6),
    mouthparts=dict(albedo=(0.0300, 0.0230, 0.0180), coat_r=0.45, base_r=0.60, ior=1.60, chestnut=0.0, irid=0.4),
    eye=dict(albedo=(0.0180, 0.0160, 0.0150), coat_r=0.10, base_r=0.40, ior=1.55, chestnut=0.0, irid=0.0),
    membrane=dict(albedo=(0.0210, 0.0098, 0.0068), coat_r=0.45, base_r=0.55, ior=1.45, chestnut=0.0, irid=0.0),
)
# setae (M3v, b08: the golden pixels' medians): the tarsal brushes (149, 125, 96), the ventrites' pubescence (135, 105, 69);
# the pronotal margins' fringes orange (hue 20-50 deg, the photo strand's B3h reading)
SETAE = dict(tarsus=tuple(srgb8_lin((149, 125, 96))), venter=tuple(srgb8_lin((135, 105, 69))),
             pronotum=tuple(srgb8_lin((150, 98, 52))), default=tuple(srgb8_lin((140, 110, 75))))
# (10-29, B6) the pronotal fringes' orange more saturated: M1d's fringe pixels (hue 18-50 deg, S > 0.45) read median sRGB
# (112, 79, 31) at the front margin and (104, 69, 31) at the hind; B6's first dorsal still under the dome drew them
# (101, 73, 54) / (105, 79, 60): as bright, but grey-orange
SETAE.update(pronotum=tuple(srgb8_lin((160, 100, 28))))
# (10-28 restart, the engine's ventral and lateral stills beside M3v / M1l) the setae's COLOUR weight per zone: the golden
# colour where the photos show golden pubescence (the tarsal brushes, the palps' orange brushes, the pronotal fringes,
# the venter's sides and margins: its midline fades in k_skin), the fine sparse setae of the legs, the mandibles' underside
# and the antennal club dark-golden over the cuticle (at full gold the femora and tibiae read as tan wood grain from
# below, the club as a rope; at 0.30 the femur's inner edge and the palps at full gold still read as wood grain in the
# head station's close frames). The hairs' relief, roughness and missing coat keep their full coverage
SETAE_W = dict(head=0.6, mandible=0.35, antenna=0.45, mouthparts=0.5, coxa=0.25, trochanter=0.25, femur=0.20, tibia=0.55)
# (10-29, B5: B5's first ventral still beside M3v: the venter's sides still read as speckled tan sandpaper; it had no row
# here, so its hair colour weighed 1.0 in the albedo) the venter's gold mostly in the sheen; the palps' orange brushes
# (M3v's tuft at the mouth) fuller
SETAE_W.update(venter=0.35, mouthparts=0.9)
# (10-29, B5) the PRONOTUM's fringes: stag_beetle_sculpt's mask takes every point within 0.45 mm of the front / hind z
# extreme, which is the whole collar FACE under the head (265 K front limit vertices face forward, |N_z| > 0.8, against
# ~25 K on the dorsal margin itself): in full gold it was the "orange disc" under the head in the hero view, read as the
# neck sleeve. Until the mask takes the margin only (a bake: NEXT), the fringe's gold is dimmed here
# (10-29, B6) the mask now takes the dorsal margins only (sculpt fringe_mask: the band where the margin comes out from
# under the head's back, and the hind margin), so the fringes take their full colour: 2.5 x SETAE_ALB 0.40 = the hairs'
# orange in full where they cover (M1d's two lines are the brightest colour accents of its dorsal view)
SETAE_W.update(pronotum=2.5)
# (the final hero still: the collar and the antennal club still read beige, seen grazing, where the sheen is strongest)
SETAE_W.update(antenna=0.25)
# (10-29, B6) the mandibles' underside setae fainter: against B6's darker mandible (black toward the tips) their gold
# streaks stood out in the ventral still (M3v: the mandibles black beneath, finely speckled)
SETAE_W.update(mandible=0.15)
# (10-29, B5) THE SETAE AS A SHEEN. The hairs are 1-2 texels wide: painted into the albedo at their coverage and with the
# coat removed under them (up to 75 %), the venter's golden sides read as matte speckled cork where M3v shows glossy black
# chitin with the gold as a sheen over it. Now the coat stays (a quarter lost under full coverage), the albedo takes
# SETAE_ALB of the zone's golden weight, and the hairs' forward-scattered gold is the runtime's SHEEN lobe (three's Charlie
# sheen): its amount per texel the IRID pack's A (the coverage x SHEEN_W), its colour beetle_cuticle.js SETAE_SHEEN. The
# club's sensory pubescence a dark velvet (low weight), the tarsal brushes and the venter's sides the strongest
SETAE_ALB = wp.constant(0.40)
SHEEN_W = dict(venter=0.90, tarsus=0.70, tibia=0.55, femur=0.35, coxa=0.35, trochanter=0.35, pronotum=0.15, head=0.30,
               antenna=0.12, mouthparts=0.90, mandible=0.25, scutellum=0.5)
# (10-29, B6) the VENTER's golden sheen lower (0.90 over ~27 % of it read as olive-tan sandpaper at grazing, the B5 check;
# M3v: glossy black chitin with golden hair patches); the pronotum's back to the fringes' own (the margins only now)
SHEEN_W.update(venter=0.30, pronotum=0.60, mandible=0.10)
# (10-29, B5) the MICRO CAVITY's weight per zone (the relief height into the albedo, k_skin's hc term; 0.35 elsewhere as
# before): M1d's head reads as bright wormy crests over near-black hollows, ~3x apart at the photo's pixel, where 0.35 on
# the worms' +-0.7 normalised height gave 1.6x; the pronotum's punctures black inside their bright lips; the elytra's beads
# bright over darker gaps
CAVITY_W = dict(head=0.80, pronotum=0.55, scutellum=0.55, elytron=0.60, mandible=0.10)
# (10-29, B5, the first engine stills on B5's bake beside M1d) the CRESTS' ROUGHNESS per zone, added to the coat as CREST_R x
# the relief's normalised height above its mean (k_skin's hc, 0..1): the relief's crests are FLAT (the worms' plateaus, the
# beads' dome tops, the punctures' lips), so on a glossy coat they mirrored the ring light's dark lens and every worm and
# bead drew as a bright outline round a dark top (a bead read as a pit); M1d's crests are rounded and scatter at its pixel.
# A rougher crest stands in for that curvature (the bake's sub-texel spread already roughens the flanks): the worms and the
# beads light as wholes over a glossy black ground, the light only on the relief. The mandible's sparse punctures stay
# glossy (M1d: polished maroon with bright specks)
CREST_R = dict(head=0.20, pronotum=0.22, scutellum=0.20, elytron=0.30)
# (the head at 0.35 greyed its dish under the whole-animal key again: its crests are 64 % of the surface; 0.20 keeps the
# close-range worms lit and the dish dark at distance)
# (10-29, B6) the relief's crests are ROUNDED now (the head's ridges, the elytral beads: stag_beetle_sculpt's B6 recipe),
# so they light as wholes by their own curvature: no crest roughness on the head, the pronotum or the elytra (with it the
# trials' worms and beads read as matte grey; the bake's sub-texel spread already roughens what the texels cannot hold).
# The micro cavity stronger on the head and the elytra (the thin ridges and the beads over darker ground, M1d)
CREST_R.update(head=0.0, pronotum=0.0, elytron=0.0)
CAVITY_W.update(head=1.0, elytron=0.8)
# (10-29, B7) the elytral beads dense at M1d's scale: the crevices between them darker (M1d's granules bright over dark gaps)
CAVITY_W.update(elytron=1.1)
# (10-29, B6) THE PITS' WALLS OCCLUDED: the share of the COAT AMOUNT (the IRID pack's B, the runtime's clear coat) taken
# inside a puncture (k_skin: x sstep(0.0, 0.08, pit), the pit weight (1 - u^2)^2, so the inner ~85 % of its radius: the
# walls and the floor; the rim and the lip keep their coat. A first window, sstep(0.02, 0.35), took only the inner ~65 %
# and the trial's distant pronotum did not darken). A pit's walls face each other: what they reflect goes into the pit and dies on black chitin
# (M1d's punctures are black inside their bright rims at every distance). Without it the runtime's Toksvig term, which
# reads the walls' slopes as ONE broadened lobe, lit the walls' energy in the 10-20 deg band where the key and the dome's
# inner rings sit: the pronotum 20-25 % too bright under every light (the B5 check's k07). The mip chain averages the
# coat amount with the normals, so at distance the pitted surface's lobe is that much weaker, as real pits are
PIT_OCC = dict(pronotum=0.90, head=0.85, scutellum=0.85, mandible=0.70, venter=0.80, elytron=0.60)
# (10-29, B7b) THE CREVICES' COAT OCCLUDED (the lead's B7b call: the elytral beads at M1d's scale, lower and flatter-topped,
# so the distant gloss returns, and up close elongated granules over DARK crevices, M1d): the share of the coat amount taken
# where the relief stands low, (amount, hc_lo, hc_hi): full under hc_lo, none over hc_hi, hc = k_skin's normalised height
# h / 0.003 mm. The crevices' walls face each other, as a puncture's do (PIT_OCC above): what they reflect dies on the
# black chitin between the granules. With the beads lower the relief's own slopes can no longer darken the crevices without
# the slope variance the distant gloss cannot afford; the mip chain averages the coat amount, so at distance the elytra's
# coat is that much weaker, as real crevices make it. 0: none (B7)
# (10-30, B8) ON, on the packed grain (stag_beetle_sculpt's cell_mode 4): B7b left it off because on its random beads it blackened
# the wide gaps (a stipple at distance); the lattice's ground is a thin even network, so it darkens the lines and no blotch
# (b8/trials g4a). The beads 3 um high: hc -0.34 at the ground, so the window takes the ground and the feet of the domes. The
# cavity's weight up with it: the crevices dark in the albedo as well, under any light
CREVICE_OCC = dict(elytron=(0.70, -0.34, -0.12))
CAVITY_W.update(elytron=1.4)
# (11-01, B9) THE ELYTRA'S GRANULES (stag_beetle_sculpt cell_mode 5) sit lower than B8's beads (their ground at 0.60 of the 4 um
# amplitude: the relief's mean hc -0.13 against B8's +0.15), so this cavity term and the crevices' window darkened the disc: the
# dorsal still's disc read L 0.0324 against B8's 0.0364 and M1d's 0.0367 (b8/c02_regions.py), at the photo's pixel the pattern
# right (t09 0.137-0.138, contrast 0.54 against M1d's 0.56). The pattern's own contrast kept, the albedo carries the tone: x1.40
# (x1.30 read 0.0356; the L floor lifts fewer texels as the albedo rises) -> 0.0366 (b9/trials/h2 h9s18, t09 0.137)
ZONE['elytron'] = dict(ZONE['elytron'], albedo=(0.0588, 0.01792, 0.01148))
# (11-01, B9) THE HEAD'S BACK AT GRAZING (the lead's B9 call: B8's read as sparkly hammered silver at the 5.2 s station, a low warm
# key in the plateau's mirror direction). B5's glossy head coat (0.20) let the flat ground mirror the dark room in the dome stills, but
# at grazing every worm crest glinted crisply over a plateau-wide glare (b9/h04: sparkle share 0.13, p99 0.72). The head's coat
# to the plan's granulate satin (BEETLE_PLAN 5.3: head 0.45-0.6): at 5.2 s a soft sheen with the worms as darker lines inside it
# (sparkle 0.04, p99 0.50), what chitin does at grazing in P2l (a soft blue-grey sheen over the head's back and the pronotum) and
# M1l (a soft sheen with the dark features inside it); the dorsal still's head ratio 0.89 (M1d 0.938, B8 0.812). The satin ground
# greys the dish under the dome a little, so the worms' cavity weight up (1.0 -> 1.8): their albedo carries their light there
# (at the photo's pixel p90 0.054, p99 0.077 against B8's 0.048 / 0.054; M1d 0.070 / 0.153), not a glint at grazing. Tried and
# left (b9/trials/h2, b9/eng/h2 + h5 + h7): the crevices' coat occluded on the head (0.6-0.9, the ground or the ground and the
# worms' feet): a darker head at grazing, but the dorsal ratio fell to 0.52-0.62 (the ground's own reflection is half the
# head's tone under the dome) and with a glossy coat the worms sparkled the more on the darker ground
ZONE['head'] = dict(ZONE['head'], coat_r=0.50)
CAVITY_W.update(head=1.8)
# (11-01, B10, the lead's B9 calls) THE ELYTRA'S HUE AND CHROMA, at the tone B9 matched: at the turntable's scale B9's elytra read a
# rosy brick-red where M1l's are a deep maroon-brown. Measured (work/bestiary/beetle/b10/m01_color.py, m02_tops.py): under neutral light
# M1l's pigment pixels sit at sRGB hue 12.8 (its flank box mean 17.9) and M1d's dorsal disc at 16.2, S 0.32, while B9 rendered its disc
# at hue 10.8 and the turntable's flank at 6.2-6.6: the coat's reflection of the sky pulls a 1 : 0.305 : 0.195 albedo pink. The albedo's
# GREEN up and its BLUE down at the same luminance (0.02615): 1 : 0.345 : 0.150. Read through the test runtime's per-channel switch
# (b10/test_runtime, b10/eng/h01b: er95 eg107 eb73): the dorsal disc hue 15.6, S 0.319, L 0.0365 (M1d 16.2 / 0.32 / 0.0367); at M1d's
# pixel the box's hue 15.0, S 0.317 (M1d 15.8 / 0.311); the turntable's pigment hue 12.3 (M1l 12.8), its saturation 0.403 -> 0.430.
# Tried: M1l's pigment ratio itself (1 : 0.266 : 0.153) and deeper chroma at the same hue raised the saturation but left the hue pink
# (6.1-6.6 at the turntable); green alone (+13 / +26 %) moved the hue (14.1 / 16.7 at the disc) and greyed it (S 0.298 / 0.291)
ZONE['elytron'] = dict(ZONE['elytron'], albedo=(0.05562, 0.01919, 0.00834))
# (11-01, B10, the lead's call) THE HEAD'S GROUND OFF THE ALBEDO FLOOR: at 1.8 the worms' flat ground (hc -0.35, 59-64 % of the head)
# fell under k_skin's L floor and was lifted to it, one value (the B9 check: L p5 = p50 = 0.0101, 40 % of the head within 2 levels of
# one colour on the shipped JPEG, B8 21 %). k_skin on the head's texels with the weight changed in-process (b10/s01_skin_stats.py,
# page 0): the share at the floor 1.8: 63.9 %, 1.4: 23.0 %, 1.2: 4.0 %, 1.0 (B8): 1.3 %; the albedo's p90 / p50 4.94 / 3.95 / 3.35 /
# 2.82. 1.2 is the largest weight that keeps the ground's own mottle (96 % of the head off the floor) with more of the worms' lift than
# B8's; the coat's 0.50 and its satin at grazing are B9's, untouched
CAVITY_W.update(head=1.2)
# (11-02, B10b, the lead's call after the B10 check) THE HEAD AT B8's 1.0: at 1.2 the clamp was off (4 % of the head at the floor)
# but the shipped JPEG still held 35.0 % of the head (page 0; 29.9 % page 1) within 2 levels of one value, the ground's mean one
# level over the floor (b10/m03_head_floor.py, the check's k09); at 1.0 B8's 21.5 % (1.3 % at the floor in-process: s01). Seen from
# above the head at 1.2 read smoother than M1d's rugose black head. Skin only, no bake; the coat's 0.50 stays
CAVITY_W.update(head=1.0)
# (10-29, B6) BELOW THE L FLOOR, TOWARD NEUTRAL: the share of the floor (L 0.0101) under it at which a colour is fully
# neutral (k_skin). B5's floor scaled every darker colour UP to the floor with its hue kept, so the mandible's base (L
# 0.0102, on the floor) took no darkening at all: 'black toward the tips' came back as the base's maroon. Now a colour
# under the floor rises to it toward the floor's neutral grey, fully neutral at FLOOR_DESAT x the floor under it: the tips
# (lnL -0.8: L 0.0046) read black, the base stays maroon
FLOOR_DESAT = dict(default=0.5)       # (0: B5's floor, the hue kept)
# (10-29, B7) THE VENTER AS M3v: glossy black chitin with DISTINCT golden hair patches (stag_beetle_sculpt VENTER_MASK's
# layout, baked into the setae coverage). B5 / B6 faded the venter's hair colour and sheen toward the midline in k_skin
# (their mask laid thin gold everywhere); the layout now carries the black middle itself, so the fade is off (MIDFADE 0;
# 1 = B6's), and the patches take the gold at full weight: the albedo's share 1.6 x SETAE_ALB (a dense patch reads golden
# tan, M3v's median (135, 105, 69)), the sheen 0.55 (the hairs' forward scatter at grazing)
MIDFADE = dict(venter=0.0)
SETAE_W.update(venter=1.6)
SHEEN_W.update(venter=0.55)
# (the first B7 ventral still beside M3v: at 1.6 the patches read as an opaque flat tan paint; M3v's are golden hairs over
# black chitin, the black showing through)
SETAE_W.update(venter=1.1)
# (10-29, B7) THE MENTUM MAROON (M3v: the glossy plate on the head's underside reads as bright as the black underside
# around it but red, linear R / G 4.5 against 1.15): zone_paint scales the head's albedo inside the plate's outline
# (stag_beetle_sculpt.mentum_plate_inside since B7b: the plate in front of the prosternal fringe; B7's mentum_inside was the
# front trapezoid; the underside only) toward MENTUM_ALB, the head's own luminance kept. (the first B7
# ventral still: (0.038, 0.0084, 0.0071) over a 0.06 mm edge read as a pale pink tint, M3v's plate is a deep saturated
# maroon with a crisp edge at its suture)
# (10-31, B8, M3v beside a lamp-lit preview, b8/out/t_mt_sheet.png) x2: under the coat's sheen the first value left no red to read
MENTUM_ALB = (0.0680, 0.0110, 0.0080)
MENTUM_EDGE = 0.03                    # mm: the colour's soft edge across the suture
# (10-31, B8) THE PLATE'S COAT, read from M3v at 3x (b8/out/fr/m3v_mentum_x3.png): the glint is BROAD, a white core with a pale lavender
# halo over half the plate and fine sparkle in it, not tight. A polished coat (0.11) mirrored the comparison dome's band edges as a
# sharp hourglass on any profile; at 0.25 they soften to a sheen. Its coat amount at 0.6: at the full amount the mirrored dome laid
# a pale grey over the maroon, and a lamp's glint saturates either way. zone_paint's `orm` and `irid`
MENTUM_COAT_R = 0.25
MENTUM_COAT = 0.6
# (10-31, B8) M3v's plate is mottled, rust patches on deep maroon: the albedo's log scale over two sizes of smooth noise, per channel
# (the rust redder than it is pale). Plane waves in plan: a solid function of the point, so nothing can step across a UV seam
MENTUM_MOTTLE = dict(sizes=(2.2, 0.9), mix=(0.8, 0.2), rgb=(0.45, 0.30, 0.25), seed=2711)
# (10-31, B8) THE SUTURE round the plate: M3v's plate ends in a dark line, where the first build's maroon paint lay on the head's worm crests
# at the outline as red dashes. The albedo and coat amount taken over a band of `sigma` mm about `at` mm inside the outline
MENTUM_RIM = dict(at=0.03, sigma=0.07, dark=0.70, coat=0.75)
# (10-31, B8) THE PLATE'S NORMALS AUTHORED. The head's underside is no dome: along the midline it is an S-curve through the plate, a
# bulge at z -8.3, a 30 deg ramp through the plate's middle, a shoulder (b8 notes: the base's fit), so the sculpt's dome over it (1 -
# u^4, flat-topped, its slope all in the rim) gave a pill with two pale lobes, and no height added on top could give M3v's one
# central glint. So inside the outline the shading normal is written outright, in b08's skin pass (the texels, no geometry and no
# silhouette, as the sculpt's dome): a cushion about one axis (0, -1, tan tilt), its tilt growing with the plate's radius to `edge`
# deg, rolling harder at the rim (`roll`, u^6), blended back to the baked normal over `blend` of u; `pebble` the fine sparkle in the
# glint, small slopes of band-limited plane waves at `size` mm. Chosen in the engine under M3v's own light, one lamp near the lens
# (b8/out/t_mt_sheet.png, beetle_scene's 'mentum' still), where the comparison dome's dark lens can't draw a central glint
MENTUM_CUSHION = dict(tilt=12.0, edge=26.0, roll=1.2, blend=(0.90, 1.0), pebble=dict(size=0.065, slope=0.018, waves=24, seed=2712))
# (10-29, B7) THE VENTER'S SIDE WALL DULL AND DARK (M1l: black under the elytral edge): the model's abdominal wall stands
# flush with the elytral edge rather than tucked under it, so the elytra's shadow (CROSS_AO) barely reaches it and its
# glossy coat kept mirroring the dome (the first B7 lateral still); the wall above the ventral face is the softer pleural
# cuticle: venter_wall_paint takes `coat` of its coat amount, raises its coat roughness to `rough` and darkens its albedo
# by `dark`, by the wall share (1 - the sculpt's ventral weight sm(0, 0.5, down) at the texel's limit normal)
VENTER_WALL = dict(coat=0.85, rough=0.55, dark=0.55)
# (10-29, B7) THE ELYTRA'S SHADOW ON THE VENTER'S SIDE WALL (the B6 check: a pale glossy segmented band under the elytral
# edge in the lateral still, black in M1l). The bake's AO is cast on each master's own limit, so nothing shaded the wall
# from the elytra overhanging it, and under the comparison dome (light from the environment) its coat mirrored the band
# of the dome the overhang hides. cross_ao: cosine rays from each venter texel's limit point against the elytra's lows,
# the hit share taken from the AO channel (three's AO scales the environment's diffuse, specular and clear coat alike)
CROSS_AO = dict(rays=32, dist=3.0, strength=1.0, lift=0.004)
DIRT = (0.090, 0.075, 0.058)          # [E] dry soil dust, linear (sRGB ~ (84, 77, 67))
REGION_ORDER = SB.REGIONS
# THE IRIDESCENT OPTION'S REMIX FAMILIES (palette data; ONE table: b10 writes it into the glb's extras.bestiary
# .iridophore_families, the runtime builders read it from there, the staged recipe doc carries the same rows). Each: the
# film's strength, its IOR, its thickness range in nm (the IRID pack's G picks within it per texel), the albedo's darkening
# toward the melanin backing (a structural colour reads over dark pigment), the coat's thinning. three r184's thin film
# (PhysicalLightingModel.evalIridescence) is ONE film over the base, its colour by thickness read off three's own
# function: (10-28 restart) a numpy replica of evalIridescence / evalSensitivity at this base (F0 0.0096: the cuticle's
# specularColor) drew the film's RGB over 60-960 nm at view cosines 1.0 / 0.7 / 0.4 (out_b58/film_strips.png). At n 1.9,
# normal incidence: 130-200 nm violet-blue to cyan, 200-245 cyan-green, green, yellow, gold, 245-300 orange-red-magenta-
# violet, 300-420 teal, green and pink again in paler orders. The first draft's jewel (290-420) straddled violet, teal,
# green and pink and rendered as a magenta beetle with olive patches. The IRID pack's G spreads the texels over most of a
# range (p5-p95 0.31-0.90 of it since the restart widened its 4 mm drift; the form and a per-cell jitter on top), so:
#   jewel     n 1.9, 202-238 nm: the GOLDEN JEWEL SCARAB (Chrysina-like): polished gold drifting to green-gold across the
#             body and turning steel-blue at grazing, over a near-black melanin backing under a thin epicuticle (a real one
#             is a chitin multilayer, which one film with a high index stands in for; b13_film.py prints each family's
#             colours under a neutral light). At 184-228 the widened drift reached the blue end and laid blue blotches over
#             the gold, a tarnish: the blue belongs to the angle, not to the place.
#             It was to be an emerald (Chrysochroa), but one film's pure green is PASTEL in three (d 205 face-on: 0.13 / 0.24
#             / 0.15, saturation 0.45; equal interfaces only brighten it), between a saturated teal and yellow, and the
#             turntable's warm key and beach sky warm it: bracketed in the engine, 172-212 rendered gunmetal blue, 200-250
#             polished gold, 188-236 gold to olive to blue-grey, never a vivid green (192-238 over the chestnut darkened to
#             0.35 read brass in the plan stills, 182-222 khaki). A true emerald wants a coloured metallic backing standing
#             in for the multilayer's band (a family field the runtime does not have yet)
#   sapphire  n 1.9, 150-190 nm: deep blue to azure at normal incidence, indigo to violet-blue toward grazing (Hoplia)
#   oilslick  n 1.6, 180-700 nm: a thick film varying across the body: its orders cycle gold, red, magenta, blue, green,
#             pink (n 1.5 was too pale: a maroon-purple tint on the base)
#   none      L. cervus itself: no structural colour (BEETLE_PLAN §5.5); the realistic base
# (the runtime gives the film the COAT's roughness where it acts: the multilayer is as smooth as the epicuticle; on the
# base's 0.55-0.6 the film's colour spread as a broad wash, a painted look)
# (10-29, the look check) THE EMERALD IS REACHABLE at this same film's HIGHER order: a search of the replica over film n,
# thickness and the base under the film (work/bestiary/beetle/scratch_check_material_look/m09_search.py, m08_film.py)
# found the best green face-on at n 1.9, ~350 nm over the cuticle's own base: H 126, peak reflectance 0.24, walking to
# turquoise (H 166) at 37 deg and cyan-blue (H 193) at 60 deg, the colour bands following the form as a jewel beetle's
# do (the bracketing above stopped at 250 nm). Rendered in the engine beside the gold it reads as a metallic emerald
# beetle (Chrysochroa, Lamprima), so:
#   jewel     n 1.9, 338-362 nm: the EMERALD jewel beetle, green face-on, turquoise to cyan-blue toward the edges
#   gold      n 1.9, 214-232 nm: the golden jewel scarab the jewel row was, its range kept inside the gold (202-238's thin
#             end turned the elytra's low-G patches blue-grey: the tarnish)
# and the runtime polishes the film's lobe (beetle_cuticle.js FILM_POLISH: 0.45 x the coat's roughness)
IRID_FAMILIES = dict(
    none=dict(strength=0.0, ior=1.6, thickness=[250.0, 650.0], darken=1.0, coat=1.0),
    jewel=dict(strength=1.0, ior=1.9, thickness=[338.0, 362.0], darken=0.10, coat=0.25),
    sapphire=dict(strength=1.0, ior=1.9, thickness=[150.0, 190.0], darken=0.35, coat=0.50),
    oilslick=dict(strength=0.85, ior=1.6, thickness=[180.0, 700.0], darken=0.60, coat=0.80),
    gold=dict(strength=1.0, ior=1.9, thickness=[214.0, 232.0], darken=0.10, coat=0.25),
)


def zone_table(regions):
    """per master index: a row of floats for the kernel (albedo rgb, coat r, base r, chestnut, irid, setae rgb, region id,
    is membrane, is claw, is eye, the setae's colour weight, (B5) the setae's sheen weight, the micro cavity's weight, the
    crests' roughness, (B6) the pits' coat occlusion, the floor's desaturation share, (B7) the venter's midline fade
    share, (B7b) the crevices' coat occlusion: its amount, hc_lo, hc_hi)"""
    rows = []
    for reg in regions:
        z = ZONE[reg]
        s = SETAE.get(reg, SETAE['default'])
        co = CREVICE_OCC.get(reg, (0.0, -1.0, 0.0))
        rows.append(list(z['albedo']) + [z['coat_r'], z['base_r'], z['chestnut'], z['irid']] + list(s) +
                    [float(REGION_ORDER.index(reg)), float(reg == 'membrane'), float(reg == 'claw'), float(reg == 'eye'),
                     float(SETAE_W.get(reg, 1.0)), float(SHEEN_W.get(reg, 0.5)), float(CAVITY_W.get(reg, 0.35)),
                     float(CREST_R.get(reg, 0.0)), float(PIT_OCC.get(reg, 0.0)),
                     float(FLOOR_DESAT.get(reg, FLOOR_DESAT['default'])), float(MIDFADE.get(reg, 1.0)),
                     float(co[0]), float(co[1]), float(co[2])])
    return np.asarray(rows, np.float32)


NZ = 24
NZ_K = wp.constant(NZ)


@wp.func
def sstep(a: float, b: float, x: float):
    t = wp.clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@wp.kernel
def k_skin(cov: wp.array(dtype=wp.float32), region: wp.array(dtype=wp.int32), vis: wp.array(dtype=wp.int32),
           ao: wp.array(dtype=wp.float32), cavity: wp.array(dtype=wp.float32), thk: wp.array(dtype=wp.float32),
           ao_local: wp.array(dtype=wp.float32), conv: wp.array(dtype=wp.float32), conv_mid: wp.array(dtype=wp.float32),
           base: wp.array(dtype=wp.vec4), micro: wp.array(dtype=wp.vec4), zt: wp.array(dtype=wp.float32),
           mreg: wp.array(dtype=wp.int32), seed: int, nlen: wp.array(dtype=wp.float32),
           o_alb: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3), o_masks: wp.array(dtype=wp.vec4),
           o_disp: wp.array(dtype=wp.vec4), o_irid: wp.array(dtype=wp.vec4)):
    i = wp.tid()
    if cov[i] <= 0.0:
        return
    m = region[i]
    o = m * NZ_K                                  # NZ floats per master (zone_table)
    alb = wp.vec3(zt[o], zt[o + 1], zt[o + 2])
    coat_r = zt[o + 3]
    base_r = zt[o + 4]
    chest = zt[o + 5]
    irid = zt[o + 6]
    seta_c = wp.vec3(zt[o + 7], zt[o + 8], zt[o + 9])
    rid = zt[o + 10]
    memb = zt[o + 11]
    claw = zt[o + 12]
    eye = zt[o + 13]
    reg = mreg[m]                                 # stag_beetle REGIONS index of the master
    b = base[i]
    q = wp.vec3(b[0], b[1], b[2]) * 100.0         # the limit point, life mm
    mi = micro[i]
    h = mi[0]
    pit = mi[1]
    seta = mi[2]
    groove = mi[3]
    # low-frequency mottling in BASE coordinates (3 mm and 0.8 mm octaves, life), +-12 % of L on the cuticle
    n1 = PR.fbm3(q * (1.0 / 3.0), 3, 2.0, 0.5, seed)
    n2 = PR.noise3(q * (1.0 / 0.8), seed + 7)
    lnL = 0.12 * n1 + 0.05 * n2
    # the relief terms (REF R4, chitin): cavities darker, the convex edges a touch paler
    lnL = lnL + 0.8 * ao_local[i] + 0.10 * wp.clamp(conv[i], -2.0, 2.0) + 0.06 * wp.clamp(conv_mid[i], -2.0, 2.0)
    # the elytra: darker along the suture and the lateral margin (M1d: the chestnut brightest on the disc); (10-28) also
    # at the base by the scutellum and the pronotum, and toward the epipleural margin, as M1d shows
    if reg == 7:
        ax = wp.abs(q[0])
        # ((10-29, B5) the margins darker: M1d's elytra go near-black at the lateral margin and along the suture, red only
        # on the disc; the engine's read evenly brown)
        lnL = lnL - 0.40 * (1.0 - sstep(0.15, 1.2, ax))
        lnL = lnL - 0.30 * sstep(-22.5, -19.0, q[2]) - 0.55 * sstep(6.5, 9.0, ax)
    # (10-28) the mandibles: chestnut at the base, black toward the tips and the teeth (M1d)
    if reg == 2:
        lnL = lnL - 0.8 * sstep(6.0, 14.5, q[2])
    lnL = lnL - 0.25 * pit - 0.45 * groove
    # (10-28 restart) the MICRO CAVITY: the relief's own height into the albedo (a texturing pass's high-to-albedo cavity:
    # wax and fine dust settle in the cell floors and the punctures, the crests stay clean), so the head's rugose network
    # reads as M1d's bright wormy ridges over dark hollows under any light, not only where the normal map's walls face the
    # key; normalised by a 0.003 mm (life) relief and clamped (the elytra's 0.0005 mm granules move it by under 6 %)
    hc = wp.clamp(h / 0.003, -1.0, 1.0)
    lnL = lnL + zt[o + 16] * hc                   # (10-29, B5) the weight per zone (CAVITY_W; 0.35 before everywhere)
    col = alb * wp.exp(lnL)
    # cavities toward red-purple, edges toward amber (REF R4)
    cv = wp.clamp(-ao_local[i] * 4.0, 0.0, 1.0)
    col = wp.cw_mul(col, wp.vec3(1.0 + 0.06 * cv, 1.0 - 0.05 * cv, 1.0 + 0.02 * cv))
    # the soft dirt: dust in the crevices and the punctures ((10-28 restart) the punctures' share 0.35 -> 0.15: at 0.35
    # the pronotum's dense punctures laid a grey-tan veil over its disc, where M1d's punctures are black). (10-29, B5) half
    # again, and only in real crevices (the 0.25 mm cavity under 0.65): the head's dish took dust over its whole floor,
    # raising its coat to 0.38-0.5 and greying it; M1d's head and pronotum are clean black chitin
    dirt = wp.clamp(0.25 * sstep(0.35, 0.85, 1.0 - cavity[i]) + 0.08 * pit + 0.20 * groove, 0.0, 0.4) * (1.0 - eye)
    dirt = dirt * (1.0 - memb)
    col = col * (1.0 - 0.5 * dirt) + wp.vec3(0.090, 0.075, 0.058) * (0.5 * dirt)
    # setae: golden hairs over the cuticle (their coverage), their colour weighted per zone (SETAE_W); the venter golden on
    # its sides and fading toward the midline (M3v: a dark glabrous middle about a third of the abdomen's width). (10-29,
    # B5) only SETAE_ALB of it in the albedo: the rest is the runtime's sheen (SHEEN_W, the IRID pack's A below)
    sc = wp.clamp(seta * 0.85, 0.0, 1.0)
    sw = zt[o + 14]
    # ((10-29, B7) the venter's midline fade by its share, MIDFADE: 0 since the mask's own layout keeps the middle black)
    mfade = 1.0 - zt[o + 20] * (1.0 - (0.2 + 0.8 * sstep(2.5, 5.0, wp.abs(q[0]))))
    if reg == 8:
        sw = sw * mfade
    col = col * (1.0 - sc * sw * SETAE_ALB) + seta_c * (sc * sw * SETAE_ALB)
    # (10-29, B5) the L ENVELOPE's floor (BARS L_envelope 0.010): a colour darker than it scaled up to it, its hue kept
    # (B5's near-black head and pronotum and the maroon mandibles put 4-6 % of the texels under it; the old per-channel
    # clamp at 0.008 let L fall to 0.008 and greyed the mandibles' dark red tips)
    lum = 0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2]
    if lum < 0.0101:
        # ((10-29, B6) and toward NEUTRAL the further under it: fully the floor's grey at FLOOR_DESAT x the floor under
        # it; the hue kept at the floor itself, so a dark zone's own colour holds where it is not darkened further)
        up = col * (0.0101 / wp.max(lum, 1.0e-6))
        sd = float(0.0)
        if zt[o + 19] > 0.0:                      # (FLOOR_DESAT 0: B5's floor, the hue kept)
            sd = sstep(0.0, 1.0, (0.0101 - lum) / (0.0101 * zt[o + 19]))
        col = up * (1.0 - sd) + wp.vec3(0.0101, 0.0101, 0.0101) * sd
    col = wp.vec3(wp.clamp(col[0], 0.002, 0.65), wp.clamp(col[1], 0.002, 0.65), wp.clamp(col[2], 0.002, 0.65))
    o_alb[i] = col
    # roughness: the base under the coat; the COAT by form (polished on the high points, duller in pits / grooves / dust).
    # (10-29, B5) the pits' and the dust's dulling lower (a puncture's floor reads black in M1d: dulled to 0.5 it spread
    # the ring light into a grey disc), and the bake's SUB-TEXEL normal spread (its sub-samples' mean resultant length:
    # the relief finer than a texel, the puncture rims, the hairs) folded in as a variance (LEAN / Toksvig at mip 0: alpha^2
    # + 2 / kappa, kappa the von Mises-Fisher concentration of the mean length); the runtime adds each mip's own spread
    hi = wp.clamp(conv_mid[i], 0.0, 1.5) / 1.5
    # ((10-29, B5) the relief's hollows no longer dulled on their own (0.06 x -hc): M1d's hollows read black, the dust term
    # already dulls the real crevices)
    cr = coat_r * (1.0 - 0.30 * hi) + 0.10 * pit + 0.10 * groove + 0.15 * dirt + 0.05 * (1.0 - ao[i]) \
        + zt[o + 17] * wp.clamp(hc, 0.0, 1.0)     # (10-29, B5) the crests' roughness (CREST_R)
    cr = wp.clamp(cr, 0.03, 0.85)
    br = wp.clamp(base_r + 0.10 * pit + 0.10 * dirt, 0.2, 1.0)
    if seta > 0.0:
        br = br * (1.0 - sc) + 0.62 * sc
    # (no floor under r: 2 (1 - r^2) / (3r - r^3) is finite at r = 1, where it is 0; a clamp at 0.9995 gave every flat texel
    # a variance of ~0.001, a 0.20 coat read as 0.226)
    rl = wp.clamp(nlen[i], 0.0, 1.0)
    v0 = 2.0 * (1.0 - rl * rl) / wp.max(3.0 * rl - rl * rl * rl, 1.0e-4)
    v0 = wp.clamp(v0, 0.0, 0.5)
    cr = wp.min(wp.pow(cr * cr * cr * cr + v0, 0.25), 0.9)
    br = wp.min(wp.pow(br * br * br * br + v0, 0.25), 1.0)
    o_orm[i] = wp.vec3(ao[i], br, cr)
    coat = (1.0 - memb) * (1.0 - 0.25 * sc) * (1.0 - 0.25 * dirt)
    # (10-29, B6) the pits' walls OCCLUDED (PIT_OCC): their coat amount taken inside the puncture (the pit weight (1 - u^2)^2
    # past 0.08: u under ~0.85, the walls and the floor), the rim and the lip kept
    coat = coat * (1.0 - zt[o + 18] * sstep(0.0, 0.08, pit))
    # (10-29, B7b) the crevices' walls OCCLUDED (CREVICE_OCC): the coat amount taken where the relief stands low
    if zt[o + 21] > 0.0:
        coat = coat * (1.0 - zt[o + 21] * (1.0 - sstep(zt[o + 22], zt[o + 23], hc)))
    # masks: soft / thin, setae, accent, the chestnut pattern
    thin = 1.0 - sstep(0.06, 0.25, thk[i])
    soft = wp.max(memb, wp.max(0.6 * sc, 0.5 * thin * (1.0 - eye)))
    acc = wp.max(claw, wp.clamp(wp.abs(conv[i]) - 1.2, 0.0, 1.0))
    o_masks[i] = wp.vec4(soft, sc, acc, chest)
    # display: part id, the iridophore mask, the cell random (the microsculpture's cells at 0.09 mm), opaque ((10-30, B8)
    # the random left the alpha: the header's 'no partial alpha')
    c = PR.cellular3(q * (1.0 / 0.09), 0.85, seed + 3)
    im = irid * (1.0 - sc) * (1.0 - memb)
    o_disp[i] = wp.vec4(rid / 255.0, im, c.rand, 1.0)
    # the film thickness for the iridescent option: a drift in BASE coordinates (4 mm), the form, a per-cell jitter.
    # (10-28 restart) the spread widened: at 0.30 / 0.10 / 0.10 the baked G spanned only 0.47-0.69 (p5-p95) of a family's
    # range, one colour over the whole body; real structural colour drifts across a beetle (the jewel's gold to green to
    # teal, the oil slick's every order)
    t01 = 0.5 + 0.90 * PR.fbm3(q * (1.0 / 4.0), 2, 2.0, 0.5, seed + 11) + 0.15 * wp.clamp(conv_mid[i], -1.5, 1.5) \
        + 0.15 * (c.rand - 0.5)
    # (10-29, B5) the setae's SHEEN amount (their coverage x the zone's SHEEN_W, the venter's midline fade as the colour
    # weight's); (10-30, B8) in R, opaque (the header's 'no partial alpha': R held the film mask, DISPLAY's G exactly)
    shw = zt[o + 15]
    if reg == 8:
        shw = shw * mfade
    o_irid[i] = wp.vec4(wp.clamp(sc * shw, 0.0, 1.0), wp.clamp(t01, 0.0, 1.0), coat, 1.0)


def plane_waves(x, z, size, n, seed):
    """(10-31, B8) band-limited noise as a solid function of the plan point (life mm): n plane waves of wavelength ~`size` mm in random
    directions, unit variance. Returns (value, d/dx, d/dz) (nothing to step at a UV seam: no texture space in it)"""
    rng = np.random.default_rng(seed)
    th = rng.uniform(0.0, 2.0 * np.pi, n)
    k = 2.0 * np.pi / size * rng.uniform(0.75, 1.25, n)
    ph = rng.uniform(0.0, 2.0 * np.pi, n)
    a = np.sqrt(2.0 / n)
    v, dx, dz = np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)
    for t_, k_, p_ in zip(th, k, ph):
        cx, cz = k_ * np.cos(t_), k_ * np.sin(t_)
        s = cx * x + cz * z + p_
        v += a * np.cos(s)
        dx -= a * cx * np.sin(s)
        dz -= a * cz * np.sin(s)
    return v, dx, dz


def plate_coords(q):
    """(10-31, B8) MENTUM_PLATE's normalized plan coordinates at points q (..., 3, life mm): (xr, zr, u), u = 1 on the outline (the
    outline's own superellipse radius, taper included: the sculpt's mentum_dome and mentum_plate_outline)"""
    from . import stag_beetle_sculpt as SC
    mp = SC.MENTUM_PLATE
    zr = (q[..., 2] - mp['center'][1]) / mp['half'][1]
    xr = (q[..., 0] - mp['center'][0]) / (mp['half'][0] * (1.0 - mp['taper'] * zr))
    return xr, zr, (np.abs(xr) ** mp['n'] + np.abs(zr) ** mp['n']) ** (1.0 / mp['n'])


def mentum_normals(nrm, q, region_of, regions, cov, page, pg, V, F, UV, N, low_frames):
    """(10-31, B8) MENTUM_CUSHION (the header) into the tangent-space normal map `nrm` (H, W, 3 or 4, in place), page pg. q: each
    texel's limit point (H, W, 3, life mm); V, F, UV, N: the head master's low (life mm, forge UV), page per face; low_frames: bake.
    low_frames. A texel's frame is the shader's (b07b's frame_at: barycentric in its UV triangle, T, B = cross(N, T) w, N), so the cushion
    decodes to the same world normal on both sides of any UV seam (the plate crosses four islands, a seam on its midline). A covered
    texel at an island's edge whose centre lies just outside every triangle takes its nearest neighbour's frame (left baked, they drew a
    line). Returns (texels written, how many of them took a neighbour's frame)"""
    heads = [k for k, r in enumerate(regions) if r == 'head']
    sel = cov & np.isin(region_of, heads) & (q[..., 1] < 14.9)
    if not sel.any():
        return 0, 0
    xr, zr, u = plate_coords(q)
    sel = sel & (u < 1.0)
    rr, cc = np.nonzero(sel)
    if not len(rr):
        return 0, 0
    S = nrm.shape[0]
    p = np.column_stack([(cc + 0.5) / S, 1.0 - (rr + 0.5) / S])
    Nl, TAN = low_frames(np.asarray(V, np.float64) * 0.01, F.astype(np.int32), UV, N)
    fT, fB, fN = np.zeros((len(rr), 3)), np.zeros((len(rr), 3)), np.zeros((len(rr), 3))
    done = np.zeros(len(rr), bool)
    lo, hi = p.min(0), p.max(0)
    for f in np.nonzero(page == pg)[0]:
        i, j, k = F[f]
        tri = UV[[i, j, k]]
        if (tri.max(0) < lo).any() or (tri.min(0) > hi).any():
            continue
        m = np.array([[tri[1, 0] - tri[0, 0], tri[2, 0] - tri[0, 0]], [tri[1, 1] - tri[0, 1], tri[2, 1] - tri[0, 1]]])
        if abs(np.linalg.det(m)) < 1e-14:
            continue
        w12 = (np.linalg.inv(m) @ (p - tri[0]).T).T
        w = np.column_stack([1.0 - w12.sum(1), w12])
        ins = (w >= -1e-6).all(1) & ~done
        if not ins.any():
            continue
        n_ = w[ins] @ Nl[[i, j, k]]
        t4 = w[ins] @ TAN[[i, j, k]]
        n_ /= np.maximum(np.linalg.norm(n_, axis=1, keepdims=True), 1e-20)
        t_ = t4[:, :3] - (t4[:, :3] * n_).sum(1, keepdims=True) * n_
        t_ /= np.maximum(np.linalg.norm(t_, axis=1, keepdims=True), 1e-20)
        fT[ins], fN[ins], fB[ins] = t_, n_, np.cross(n_, t_) * np.sign(t4[:, 3:4])
        done |= ins
    nfb = int((~done).sum())
    if nfb:
        from scipy.spatial import cKDTree
        near = cKDTree(np.column_stack([rr[done], cc[done]])).query(np.column_stack([rr[~done], cc[~done]]))[1]
        for a_ in (fT, fB, fN):
            a_[~done] = a_[done][near]
    c = MENTUM_CUSHION
    xrs, zrs, us = xr[rr, cc], zr[rr, cc], u[rr, cc]
    te = np.tan(np.radians(c['edge']))
    roll = 1.0 + c['roll'] * us ** 6
    pb = c['pebble']
    _, gx, gz = plane_waves(q[rr, cc, 0].astype(np.float64), q[rr, cc, 2].astype(np.float64), pb['size'], pb['waves'], pb['seed'])
    gl = np.sqrt(np.mean(gx ** 2 + gz ** 2))
    nt = np.column_stack([xrs * te * roll + pb['slope'] * gx / gl, -np.ones_like(xrs),
                          np.tan(np.radians(c['tilt'])) + zrs * te * roll + pb['slope'] * gz / gl])
    nt /= np.linalg.norm(nt, axis=1, keepdims=True)
    ts = np.column_stack([(nt * fT).sum(1), (nt * fB).sum(1), (nt * fN).sum(1)])
    t = np.clip((us - c['blend'][0]) / (c['blend'][1] - c['blend'][0]), 0.0, 1.0)
    w2 = (1.0 - t * t * (3.0 - 2.0 * t))[:, None]
    old = np.asarray(nrm[rr, cc, :3], np.float64)
    new = old * (1.0 - w2) + ts * w2
    new /= np.maximum(np.linalg.norm(new, axis=1, keepdims=True), 1e-20)
    nrm[rr, cc, :3] = new.astype(nrm.dtype)
    return int(len(rr)), nfb


def zone_paint(alb, region_of, regions, q, cov, orm=None, irid=None):
    """(10-29, B7) the per-texel zone colours after k_skin (linear albedo (H, W, 3), in place): the MENTUM maroon, ((10-30, B8) and
    its coat: roughness in orm's B, given the ORM (H, W, 3), amount in irid's B, given the IRID pack (H, W, 4)). region_of:
    each texel's master index (H, W); regions: the masters' region names; q: each texel's limit point (H, W, 3, life mm);
    cov: the covered texels. Inside the maroon plate's outline on the head's underside (y under 14.9, as the sculpt's
    groove; (10-29, B7b) the plate M3v shows in front of the prosternal fringe, stag_beetle_sculpt.MENTUM_PLATE: B7 painted
    the front trapezoid) the head's albedo is scaled channel by channel to MENTUM_ALB / the head zone's albedo (its own
    mottling, cavity and suture kept), the weight soft over MENTUM_EDGE across the outline. Returns the weight map (H, W)"""
    from . import stag_beetle_sculpt as SC
    w = np.zeros(cov.shape, np.float32)
    heads = [k for k, r in enumerate(regions) if r == 'head']
    sel = cov & np.isin(region_of, heads) & (q[..., 1] < 14.9)
    if sel.any():
        d = SC.mentum_plate_inside(q[sel])
        t = np.clip((d + 0.5 * MENTUM_EDGE) / MENTUM_EDGE, 0.0, 1.0)
        w[sel] = (t * t * (3.0 - 2.0 * t)).astype(np.float32)
        mul = np.asarray(MENTUM_ALB) / np.asarray(ZONE['head']['albedo'])
        # (10-31, B8) M3v's rust patches (MENTUM_MOTTLE), a solid function of the plan point
        mm = MENTUM_MOTTLE
        x_, z_ = q[..., 0][sel].astype(np.float64), q[..., 2][sel].astype(np.float64)
        n_ = sum(m_ * plane_waves(x_, z_, s_, 12, mm['seed'] + k)[0] for k, (s_, m_) in enumerate(zip(mm['sizes'], mm['mix'])))
        mul = mul[None, :] * np.exp(n_[:, None] * np.asarray(mm['rgb'])[None, :])
        c = alb[sel] * (1.0 + w[sel][:, None] * (mul - 1.0))
        mr = MENTUM_RIM
        rim = np.exp(-((d - mr['at']) / mr['sigma']) ** 2)            # (10-31, B8) the suture (the note at MENTUM_RIM)
        c *= (1.0 - mr['dark'] * rim)[:, None]
        # the L floor (k_skin's 0.0101) kept: a texel the scaling took under it rises back to it, its hue kept
        lum = c @ np.array([0.2126, 0.7152, 0.0722])
        c *= np.maximum(0.0101 / np.maximum(lum, 1e-6), 1.0)[:, None]
        alb[sel] = c
        if orm is not None:
            cr = orm[..., 2][sel]
            orm[..., 2][sel] = cr + (MENTUM_COAT_R - cr) * w[sel]
        if irid is not None:
            irid[..., 2][sel] = irid[..., 2][sel] * (1.0 - (1.0 - MENTUM_COAT) * w[sel]) * (1.0 - mr['coat'] * rim)
    return w


def venter_wall_paint(alb, orm, irid, sel, Nq):
    """(10-29, B7) VENTER_WALL on the venter texels `sel` (in place) by their limit normals Nq (len(sel.sum()), 3): the wall
    share w = 1 - sm(0, 0.5, -N_y); returns w"""
    t = np.clip(-Nq[:, 1] / 0.5, 0.0, 1.0)
    w = (1.0 - t * t * (3.0 - 2.0 * t)).astype(np.float32)
    vw = VENTER_WALL
    alb[sel] = alb[sel] * (1.0 - vw['dark'] * w)[:, None]
    lum = alb[sel] @ np.array([0.2126, 0.7152, 0.0722])          # the L floor kept, the hue with it
    alb[sel] = alb[sel] * np.maximum(0.0101 / np.maximum(lum, 1e-6), 1.0)[:, None]
    irid[..., 2][sel] = irid[..., 2][sel] * (1.0 - vw['coat'] * w)
    cr = orm[..., 2][sel]
    orm[..., 2][sel] = cr + np.maximum(vw['rough'] - cr, 0.0) * w
    return w


@wp.kernel
def k_cross_ao(q: wp.array(dtype=wp.vec3), n: wp.array(dtype=wp.vec3), mesh: wp.uint64, rays: int, dist: float,
               lift: float, out: wp.array(dtype=wp.float32)):
    """per point (life mm): the share of `rays` cosine-distributed rays about n (a stratified spiral, turned per point)
    that meet the occluder within dist"""
    i = wp.tid()
    nn = wp.normalize(n[i])
    a = wp.vec3(0.0, 0.0, 1.0)
    if wp.abs(nn[2]) > 0.9:
        a = wp.vec3(1.0, 0.0, 0.0)
    e1 = wp.normalize(wp.cross(nn, a))
    e2 = wp.cross(nn, e1)
    o = q[i] + nn * lift
    rot = PR.u01(PR.hash3i(i, 17, 29, 3)) * 6.2831853
    hit = float(0.0)
    for k in range(rays):
        u = (float(k) + 0.5) / float(rays)
        r = wp.sqrt(u)
        ph = float(k) * 2.3999632 + rot
        dvec = e1 * (r * wp.cos(ph)) + e2 * (r * wp.sin(ph)) + nn * wp.sqrt(wp.max(0.0, 1.0 - u))
        qr = wp.mesh_query_ray(mesh, o, wp.normalize(dvec), dist)
        if qr.result:
            hit = hit + 1.0
    out[i] = hit / float(rays)


def cross_ao(Q, Nq, V, F):
    """(10-29, B7) CROSS_AO's hit share per point Q (life mm) with normal Nq against the occluder mesh (V life mm, F)"""
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32))
    out = wp.zeros(len(Q), dtype=wp.float32)
    wp.launch(k_cross_ao, dim=len(Q), inputs=[wp.array(np.asarray(Q, np.float32), dtype=wp.vec3),
                                               wp.array(np.asarray(Nq, np.float32), dtype=wp.vec3), m.id,
                                               int(CROSS_AO['rays']), float(CROSS_AO['dist']), float(CROSS_AO['lift']),
                                               out])
    return out.numpy()


# BEETLE_BARS (BEETLE_PLAN §5.5) per zone: L p50 and S p50 of the albedo (sRGB S), the coat's roughness p50
BARS = dict(
    L_envelope=(0.010, 0.65),
    elytron=dict(L=(0.023, 0.026), S=(0.35, 0.45)),
    head=dict(L=(0.020, 0.030), S=(0.0, 0.30)),
    pronotum=dict(L=(0.020, 0.030), S=(0.0, 0.30)),
    mandible=dict(L=(0.040, 0.050), S=(0.10, 0.40)),
)
