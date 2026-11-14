"""The axolotl's WET SKIN (work/bestiary/research/AXOLOTL_PLAN.md §5.11; AX7's pilot runs it on the 2048 bake, AX9 on
the 4096): the material pass, per texel from the bake's drivers, on the GPU in seconds, so the look iterates without a
re-bake. The plan's contract:

  * the baked BASE COLOUR is the UNPIGMENTED GROUND: the skin with no pigment cells, pink-white (p03's leucistic body
    #D7B3B4, head #E8CAC3; p08's white albino #EFEDEB brackets it), a red BLUSH where blood shows through thin tissue
    (the gill rami and their filaments, the digit webs and tips, the fins' margins, the throat), cream digit tips, the
    crevices' cavity and relief tints. A plain glb viewer shows a leucistic-looking axolotl, a real and popular morph;
  * the PIGMENT MASKS ride in the house's packs, no new texture:
      MASKS (KHR_materials_volume's thickness slot, as the octopus's): R thin tissue (transmission), G ventral, B the
        zone (0 body, 0.12 limbs and hands, 0.6 fins, 0.9 stalks, 1 filaments), A the MELANOPHORE COVER (the mottle);
      DISPLAY (the emissive slot at factor 0, as the octopus's): R IRIDOPHORE fields (p06's gold field on the head,
        p01's silver flecks low on the tail), G XANTHOPHORE wash, B LEUCISTIC SPECKLES (the sparse dark speckles a
        white morph keeps), A the mottle's random (per blob);
    and the runtime composes each morph (the study-B larva-creature model): base = mix(ground, melanin, cover x M) tinted by the
    xanthophores x X, the iridophores' glint view-dependent x I, the speckles on the white morph, the thin-tissue colour
    mix(blood red, melanin brown, cover) through the thickness;
  * ORM: R the baked AO, G the roughness per zone (§2.9, the study-T salamander creature's wet calibration: head p50 0.14, body
    0.20 with the dorsum glossier 0.17 and the venter 0.24, limbs 0.17, fins 0.16), darker paint a little rougher,
    B 0 (no metal);
  * the NORMAL is the bake's (the costal pillows, the gular fold, the lip lobes, the vent, the folds are the high's);
    the Leydig cells and the mucus micro-relief are the runtime's tiled micro-normal (plan §2.9, R tier).

THE COORDINATE every pattern reads is the texel's BASE point (the bake's point on the unsculpted block-out), in life
mm: a solid coordinate, continuous across every seam, isometric by construction (forge/audit_streaks' check 1 measures
its differential). The stacked parts take their primary's texels (the left limbs for both, r1's stalk for all six rami,
the fin faces each other's): the mottle repeats there, as the plan accepts (a runtime variation term later), and the
filament templates (baked at D_REF) take no mottle: their pigment is the zone's.

THE FRECKLES (AX7b, 10-30; RECIPE freckles' note has the measures): small SEPARATE dark freckles on a continuous ground,
as every wild-type photo shows (p01's head, p13, p14, p22): freckle3's cellular field (separate soft spots with a
log-normal size spread, merging where two meet), a fine layer and a coarser one through one domain warp, the head's
field denser and finer than the trunk's, thinned toward the venter, the fins also carrying the sweep's 1.2 mm spots
4.1 mm apart. Round 6 thresholded a warped gradient noise at p01's "58 % dark" (a colour-cluster share of p01's backlit,
lumpy skin, where the gland bumps' shading counts as dark: measured against the local median, p01's distinct freckles
cover 22 % of its head): above half the dark phase joined up and the light tone broke into islands, camouflage.
BOTH of p01's tones are melanised (Ylin 0.05 and 0.023 against the ground's ~0.49): through the runtime's linear
mix(ground, melanin, cover) the light tone is a cover of ~0.93 and the dark one ~0.985, so the pale ground barely shows
on a wild type's flank (the AX7 look round, 10-29: the first recipe's cover p50 0.70 composed a cream animal with black
blotches, where p01 / p02 / p06 / p07 / p13 / p22 are dark olive-grey to grey-brown with darker mottling). Each zone's
cover below is its LIGHT tone; the mottle closes m_amp of what that leaves open, the spots s_amp.
"""
import numpy as np
import warp as wp

from .. import proc

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})


@wp.func
def _gauss3(h1: float, h2: float, h3: float):
    """about N(0, 1) from three uniforms (Irwin-Hall)"""
    return (h1 + h2 + h3 - 1.5) * 2.0


@wp.func
def freckle3(p: wp.vec3, sp: float, r_med: float, r_spread: float, presence: float, soft: float, seed: int):
    """THE FRECKLES (AX7b): a CELLULAR field of separate soft dark spots. Sites on a jittered lattice of spacing sp (life
    mm), each present with probability `presence`, its radius r_med x exp(r_spread x N(0, 1)) (a log-normal size spread),
    capped under one lattice step (the 27-site search stays exact); the mask is the MAX over the 27 neighbouring sites of
    a soft disc (soft: the edge's half width in life mm, the same on every spot as on the photos), so a big spot covers
    its neighbours' points and two near spots merge; each spot's own strength 0.55 .. 1 (the photos' freckles run faint
    to dark). Returns vec2(mask 0 .. 1, the covering site's random)"""
    q = p / sp
    e = soft / sp
    ci = int(wp.floor(q[0]))
    cj = int(wp.floor(q[1]))
    ck = int(wp.floor(q[2]))
    m = float(0.0)
    rnd = float(0.0)
    for a in range(-1, 2):
        for b in range(-1, 2):
            for c in range(-1, 2):
                i = ci + a
                j = cj + b
                k = ck + c
                if proc.u01(proc.hash3i(i, j, k, seed + 5)) < presence:
                    s = wp.vec3(float(i), float(j), float(k)) + wp.vec3(0.5, 0.5, 0.5) + \
                        (proc.rnd3(proc.hash3i(i, j, k, seed)) - wp.vec3(0.5, 0.5, 0.5)) * 0.95
                    g = _gauss3(proc.u01(proc.hash3i(i, j, k, seed + 11)), proc.u01(proc.hash3i(i, j, k, seed + 13)),
                                proc.u01(proc.hash3i(i, j, k, seed + 17)))
                    r = wp.min(r_med * wp.exp(r_spread * g) / sp, 0.95)
                    d = wp.length(q - s)
                    w = (1.0 - proc.smoothstep(r - e, r + e, d)) * (0.55 + 0.45 * proc.u01(proc.hash3i(i, j, k,
                                                                                                         seed + 19)))
                    if w > m:
                        m = w
                        rnd = proc.u01(proc.hash3i(i, j, k, seed + 977))
    return wp.vec2(m, rnd)


def lin(h):
    """sRGB8 hex (int or '#RRGGBB') -> linear RGB"""
    if isinstance(h, str):
        h = int(h.lstrip('#'), 16)
    c = np.array([(h >> 16) & 255, (h >> 8) & 255, h & 255], np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb8(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    s = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)
    return np.clip(s * 255.0 + 0.5, 0, 255).astype(np.uint8)


# zones (the kernel's int per texel; zones() derives them from the bake's region and the base point)
Z_BODY, Z_HEAD, Z_MOUTH, Z_LIMB, Z_PALM, Z_DIGIT, Z_RAMUS, Z_FILAMENT, Z_FIN, Z_HIDDEN = range(10)
ZONE_NAMES = ('body', 'head', 'mouth', 'limb', 'palm', 'digit', 'ramus', 'filament', 'fin', 'hidden')

# the recipe: every number with its source ([P] a photo or the SPEC's palette rows, [D] my design call, [E] an estimate
# for the look round)
RECIPE = dict(
    ground_body='#D7B3B4',         # [P p03] leucistic body
    ground_head='#E8CAC3',         # [P p03] leucistic head
    ground_venter='#EAD9C8',       # [E] the venter cream (plan §2.10: "cream or yellow" [L]) under no pigment
    blood='#C9787E',               # [P p03] the leucistic gills: blood through thin tissue
    tip='#F0E2CC',                 # [L] the digit tips cream (SEMARNAT)
    mouth='#3A2A2C',               # [D from P p13 p14 p15] the mouth's inside DARK (AX13; was the lining's pink #D9989A)
    # (AX13, the lead's call: the pale lining between the lips read as a row of teeth in the pale lookdev, a pink ribbon
    # between the lips (ax13_notes/try/before_face_maps.png); every closed mouth in the photos is a thin dark line, the
    # inside in its own shadow. A deep shadowed red-brown, so an opening jaw shows a dark mouth, not a pale one; the
    # faces at the lips still continue the skin either side (RECIPE lip mouth_pale / mouth_skin))
    blush=dict(thin=0.50, ramus=0.35, filament=0.90, throat=0.25),
    # [D] how far thin tissue / the stalks / the filaments / the throat go to blood. AX7b: the stalks 0.35 (round 6 0.85
    # for stalks and filaments alike): the photos' stalks are body-coloured or pale (p13 blue-grey, p14 tan, p17
    # whitish, the leucistic p04 / p05 pale pink) and the red is the filaments' (p04 / p05 / p18) [P]. AX7c, 10-31: thin
    # 0.75 -> 0.50: p04's sRGB G / R falls 0.916 (leg) -> 0.897 -> 0.864 (foot), -0.052, where the map fell -0.088: a pink
    # sock [P p04] (the runtime's BLUSH_THIN must equal this)
    limb_cream=0.5,                # [D from P p04] the limbs', hands' and digits' least share of the venter's cream
    # (AX7c, 10-31: the ground's cream follows the ventral value, and on a limb that value is the world normal's: 0.5 on the
    # vertical leg, 0 on the foot's top, across a 2 mm bend, so the foot went pink-white at exactly the wrist whatever the
    # thin mask's ramp: the map's top and side faces of one palm read (210, 162, 163) and (217, 178, 172). Held at this
    # floor nothing flips at the bend; the soles keep their cream, and it blends to the body's at the limb's root)
    cavity=(0.78, 0.30),           # [E] the crevices: albedo x (a + (1 - a) cavity), and their red shift
    # the melanophore COVER per zone, its LIGHT tone before the mottle (the wild type's look: the runtime's linear
    # mix(ground, melanin, cover)): p01's flank light tone #443D41 = cover 0.93 [P]; the dorsum darker, the head and
    # limbs as p13 / p06 [E]; the venter a light grey-cream (p13's chin, [L] "cream or yellow") [E]; the palms and digit
    # tips paler [L] (palm: the target of the limbs', hands' and digits' undersides by the ventral value, run()); the gill
    # stalks dark (p13 / p06), the filaments p01's #544346 = 0.91 [P]; the fin a little paler,
    # its spots carrying it (p01's backlit tail) [E]
    cover=dict(dorsum=0.95, flank=0.93, venter=0.70, head=0.92, limb=0.90, palm=0.62, tip=0.30, ramus=0.93,
               filament=0.90, fin=0.85, mouth=0.20),
    # (AX7b: the stalks' light tone 0.90 -> 0.93, the flank's: with the blush they read pinker than the body, where
    # p13's are blue-grey and p14's the head's tan)
    # (the fin's light tone a little more open than the flank's: a backlit fin passes light between its melanophores and
    # prints its mottle and spots, p01) [E]; the mouth zone (the inner lips and the bag) unpigmented, AX7b: round 6's 0.75
    # painted the inner lip ring a maroon ribbon between the lips, where p13 / p14 / p15's closed mouths are a thin dark
    # line (AX4's V-groove, its occlusion) between pale lip margins [P]
    # THE LIP MARGINS (AX7b; run()'s lip input): a pale band along each lip, the melanophores parted to `cover` within
    # `upper` / `lower` mm (life; full .. none) of the mouth's own skin [P p13 p14 p15: the lower lip a pale grey-white
    # rim ~1 mm, the upper lip's edge paler]
    lip=dict(cover=0.38, upper=(0.0, 0.2), lower=(1.6, 2.2), edge=0.25, xantho=0.10, ground='#CBCBC6', ground_w=0.7,
             corner=0.0, corner_at=(-1.0, 3.0), lobe_h=(1.35, 2.1), lobe_soft=0.35,
             slit=dict(k=0.05, at=(0.55, 0.80), at_U=(0.30, 0.55), depth=(1.2, 2.2), rough=0.65),
             bead_h=(1.25, 1.3), bead_rough=0.10,
             pearl=dict(h=(1.30, 1.30), skin=1.0, tone=0.92, rough=0.10,
                        rim=dict(at=0.91, w=0.07, part=0.35, lift=0.25, rough=0.05),
                        geo=dict(bulge=(0.10, 0.35), depth=(0.10, 0.40), x=(4.0, 15.0), full=0.5, rim=(0.25, 0.10)))),
    # (AX10b, 11-02, geo: THE MASK FROM THE LOW'S OWN LOBES (tests/ax07_skin.py, life mm): each welded vertex of the lower
    # lip's skin under the lip loop's lower run by `depth`, within |x| `x`, its bulge (its distance along its normal
    # from its 2-ring's mean) smoothstepped over `bulge`, a ring of half weight round it, splat over the low's
    # triangles; `rim` (the mask's value at the lobe's outline, the ring's width). Every paint before it went on
    # ellipses about the clay's margin points, which missed the cage's lobes (a debug pass: the inner lobe of each pair
    # all band, the outer crossed by a band stripe), so all of them, chalk, glass and lip alike, left the lobes the band's
    # pale: the white teeth. rough back to 0.10 / rim 0.05 (0.35 changed nothing there either))
    # (AX10b, 11-02: THE PEARLS PAINTED AS THE LIP, NOT AS GLASS. Every glass profile so far (chalk white, then the grey
    # core under a pale rim) left them the palest things on the face, and from the front the pale lobes hanging into the
    # dark slit read as a row of teeth, a grin where p13 has a soft closed smile; through p14 / p15's clear droplets one
    # sees the lip itself, its tone and its spots. A first AX10b pass kept the lip BAND's pale cover and grey ground on
    # them with the skin's freckles through: no visible change (the uw face_front's pearls L 148-158 against 153-166, the
    # band under them L 63-90): the pale band paint lit from the front IS the white lobe, the dome facing the key and the
    # camera where the band faces down. So the pearl now takes `skin` of the way from the band's cover, ground and wash
    # back to the LIP SKIN's own (its melanophore cover with the freckles, the head's ground, the olive wash), a fleshy
    # lobe of the lip in its tone; no fill of its own, no forced transmission (the skin's thin mask as baked). 0.75 of the
    # way (cover p50 0.69) still drew them L 131 (the maps: cover 0.70-0.74 on the pearls' vertices, thin 0.05, AO 0.9):
    # under the runtime's linear mix(ground, melanin, cover) the skin's own cover there (0.81, the head's 0.92 opened by
    # the ventral value of the dome's down-facing normal) is still ~2x the head's albedo, and the dome faces the key. So
    # `tone` is the lip's light tone (the head's cover, 0.92) with each texel's freckle share kept on it. Only a THIN
    # RIM at its outline (run()'s lip rim: a ring at `at` of the footprint ellipse, `w` wide) parts the cover by `part`,
    # lifts the colour `lift` of the way to the band's grey and takes `rough`; the whole pearl `rough`, so the wet
    # highlight sits small and sharp on it as on p15's)
    # (AX10 successor, 11-02: the first 4096 engine stills (axolotl_stills_wild_uw_a10 at 3.5 / 8.5 / 9.5 s) drew the
    # pearls CHALK WHITE, opaque, reading as teeth beside p14 / p15's beads: clear GREY glass, darker where the skin shows
    # through the middle, a bright rim round the outline, sharp highlights. A first try (the pale ground #BCBFBA at 0.60,
    # see 0.35) changed nothing visible: the pearls sit in the lip band's low cover, so the ground filled them. Now the
    # ground is the glass's grey CORE and `rim` the outline's pale ring, painted from the ellipse mask itself (the rim
    # where it crosses half: 4 m (1 - m), the pearl's outline; the core where it is whole); see: the share of the skin's
    # own melanophore cover left under the glass (cover + see x the skin's); thin 0.45 (was 0.60))
    # (AX10, THE PEARLS (caudate's pearl record): their own ellipse (pearl h: the centre under the margin, the half
    # height, mm; along the line the pearl's half-length) and GLASS: p14 / p15's beads are clear grey-white whatever the
    # skin round them (no melanophores, no wash: pearl cover / xantho), with a bright small highlight (pearl rough) and the
    # light passing through them (pearl thin: MASKS R, the runtime's transmission of the pale membrane colour through
    # what the cover leaves open, so they glow when lit from behind or across, as the photos' do); the ground a paler
    # neutral than the lip band's)
    # (AX8, the BEADS (caudate's lobe record's beads, two a side): each its own ellipse in the lobe mask, bead_h (its
    # centre under the margin, its half height) mm (ax8_notes/measure_beads.py: their lowest points 2.4-2.65 mm under the
    # margin), along the line its own half-length; GLASSY: the mask also takes the roughness to bead_rough, so each
    # bead carries its own wet highlight as p15 / p14's do (pale grey, a bright spot and rim on each))
    # (AX7b's first o3 render: cover 0.20 over (0.35, 0.9) / (0.6, 1.5) drew a bright cream lower lip ~2 mm wide with a
    # white spot where the bands meet at the front; p13 / p14's lower lip is a paler GREY rim. AX7c, 10-30: AX7b's cover
    # 0.45 over (0.35, 0.9) then read as a thin tan wire laid on the head, the mouth's strongest feature in the photos
    # gone: p15's band measures 1.0-1.4 mm wide (y 526-535 at the midline, 520-535 at 0.1 HW, 402 px per HW) and a neutral
    # grey, #A6A7A5 / #97988F, its lobes the same grey #7D7D77-#9D9D92 [P p15; ax7c_notes/NOTES.md]. So under the line the
    # band is wider (`lower`, mm from the upper lip's own line, its V-groove taking the first ~0.9 of them; `edge` mm of
    # noise on its lower edge: a smooth arc read as paint), the wash parts in it (`xantho`) and its ground goes `ground_w`
    # of the way to a neutral grey `ground`; it fades to `corner` over corner_at mm about the U's end, so it stops at the
    # lobes as p15's does and only the crease runs on to the commissure (a band to the corner read as a paper strip; one
    # narrowing there as a diagonal cut); the LOBES take the band's colour, an ellipse lobe_h (height under the margin,
    # half height) mm with lobe_soft of it the soft edge, along the line the lobe's width. THE SLIT: x k at the V's apex
    # (`at` mm from the lips), back to the bag's own pink over slit depth mm, rough so no wet glint sits in it: the
    # faces nearer the lips continue the skin either side (run()'s mouth_pale, mouth_skin; the masks from the cage))
    # THE FRECKLES (AX7b, 10-30; the round-6 look: a warped fbm thresholded at 58 % dark joined up into camouflage, where
    # every wild-type photo shows small separate dark freckles on a continuous ground): freckle3's cellular field, two
    # layers (fine freckles, coarser spots) through one domain warp, measured the photos' way (ax7b_notes/freckles.py on
    # the photo, the same script on the field sliced by ax7b_notes/freckle_calib.py):
    #   head:  p01 22 % dark, 0.79 / mm2, diameters p10 / p50 / p90 0.13 / 0.32 / 1.07 mm, nearest 0.58 mm; p14 34 %,
    #          0.36 / mm2, 0.22 / 0.91 / 1.77; p13 6 % of specks 0.15 mm (its grain hides the faint ones) [P]
    #          -> the field 26 %, 0.98 / mm2, 0.16 / 0.37 / 0.91, nearest 0.64 [D from P]
    #   trunk: p22's flank sparse larger spots (0.6-0.74 mm median, p90 1.5; its blur hides the faint ones), p01's fin
    #          the sweep's 1.2 mm spots 4.1 mm apart [P] -> the field 13 %, 0.41 / mm2, 0.19 / 0.41 / 1.09, nearest 0.92
    # each layer (spacing, median radius, its log spread, presence) in life mm; soft the edges' half width (the same on
    # every spot, as the photos'); amp: how much of the light tone's opening a freckle closes (p01: a freckle at 0.38 of
    # its ground's luminance through the runtime's mix = 0.95 [D from P p01]); venter: the freckles thin to this share at
    # the ventral midline (p13's chin, p16's pale venter [P]); the head's field takes over across head_blend
    freckles=dict(head=dict(fine=(0.58, 0.15, 0.6, 0.9), coarse=(2.0, 0.44, 0.35, 0.55)),
                  trunk=dict(fine=(0.85, 0.17, 0.6, 0.75), coarse=(2.6, 0.60, 0.35, 0.60)),
                  soft=0.07, warp=(0.7, 0.15), amp=0.95, venter=0.25, venter_head=0.85,
                  fin_coarse=(2.65, 0.95, 0.40, 0.90)),
    # (AX7c, 10-31: venter_head: the jaw and chin keep the head's freckles, the head's station weight taking `venter` to
    # this: p14 / p15's chin under the band is as freckled as the snout, where a thinned chin read as a bare pale bowl from
    # the new front station; the belly stays thinned, p16)
    # (round 6: mottle=dict(spacing=2.6, warp=1.0, dark_share=0.583, amp=0.80, soft=0.14), spots=dict(spacing=4.1,
    # r_med=0.62, r_spread=0.45, amp=0.90, edge=0.18); fin_coarse kept the sweep's fin spots, 1.2 mm 4.1 mm apart.
    # AX7b restart 2: p01's backlit fin measured (freckles.py, two boxes at 19 px / mm, k 0.70): 39-42 % dark, the soft
    # blotches 2-4 mm across about 5 mm apart over a finer mottle (ref/freckles/p01_fin.png), where the o3 fin carried
    # ~7 % in 1.2 mm spots. The sites fill a 3D lattice and the skin is a slice through it, so a layer's dark share is
    # the spheres' volume share, 1 - exp(-presence x 4/3 pi E[r^3] / spacing^3) with E[r^3] = r_med^3 exp(4.5 s^2) (my
    # first fin layer, 4.0 mm apart, sized by area, gave ~13 %): 0.95 mm blotches 2.65 mm apart, nine in ten sites =
    # ~30 %, with the trunk's field ~39 % [P p01, the measure's 39-42 %])
    # the iridophores (AX7b): ONE OR TWO GOLD PATCHES on the head as p14 (behind the eye, ~3 x 2 mm) and p15 (between
    # the eyes, elongated) show, not a field over the head (round 6's 25 % of the head's fbm added tan bits that fed the
    # camouflage): each (station s, its offset off the dorsal midline in mm (+ the left), half axes along / across in
    # mm), on the head's dorsal skin (run() finds the point), an irregular outline (soft, edge noise), the melanophores
    # parted over it (cover x (1 - part)) [P p14 p15; D]; p01's silver flecks low on the tail from fleck_from [P p01]
    irid=dict(patches=((0.050, 6.0, 2.2, 1.4), (0.045, -5.5, 0.9, 2.3)), soft=0.25, noise=0.30, part=0.85,
              thru=1.8, fleck_spacing=2.6, fleck_r=0.22, fleck_from=0.42),
    # (AX7c, 10-31: thru: the freckles cut through the gold, the patch x (1 - min(1, thru x freckle)): p14 / p15's patches
    # carry dark freckles, where the clean ones read as cream stickers on the head from the front)
    # (AX7b restart 2: both patches moved up beside the eyes (the eyes at s 0.0387, ~10 mm off the midline): p14's lies
    # dorsomedial of the eye and a little behind it, p15's (frontal, 10.5 px / mm) between its right eye and the midline,
    # ~5 mm off it, ~6 x 1.5 mm, elongated across the head [P p14 p15]; the first o3 renders had them at s 0.066 / 0.098,
    # 3.6 / -4.4 mm: two cream blots on the crown behind the eyes)
    # the head's ground, cover and roughness take over from the trunk's across these body stations (the poll ring at
    # s 0.125, the gill bases at 0.177): a blend in the solid coordinate, so no region boundary prints [D]
    head_blend=(0.10, 0.17),
    throat=(0.10, 0.13, 0.17, 0.21),                                               # [D] the gular blush's stations
    root_blend=1.5,                # [D] life mm: the appendages' cover and roughness reach the body's at their roots
    thin_blur=3.0,                 # [D] life mm: the limbs', hands' and digits' thin mask averaged in 3D over this sigma
    # (AX7c, 10-30; the AX7b check: a hard pink "glove" line round every wrist and ankle of the leucistic, the hand pink
    # below it: the blush (blush thin x the thin mask, a smoothstep of the baked thickness 0.6 -> 3.2 mm) switched on
    # within a millimetre where the 0.9 mm palm slab meets the 3.2 mm forearm. The leucistic photos' hands (p04, p05)
    # pinken gradually toward the digits. run()'s _thin_blur: the mask splatted into a 3D grid, Gaussian-blurred,
    # read back, on those zones only, the hidden texels out [D from P p04 p05]. 10-31: sigma 0.75 and 1.5 left a ramp of
    # 1-3 mm, still a line on a 20 mm hand: 3.0, about half the forearm to mid palm. MOST OF THE LINE WAS NOT HERE: the
    # engine's AO radius, axolotl_scene.js setup's note; and the wild type's mauve hands were the blush seen through its
    # melanophores (skinMaterial's THE BLUSH note), not the transmission as I first thought: the hands' lower
    # transmission thin_hand (it was 0.35 here, cutting MASKS R) moved to the runtime as THIN_HAND, so MASKS R is the thin
    # mask everywhere and the runtime can read the blush back out of it)
    xantho=dict(dorsal=0.75, venter=0.55, scale=9.0, var=0.25),                   # [E] the olive wash
    speckle=dict(spacing=5.5, r=0.20, share=0.22),                                # [P p03] a few dark speckles
    # [R] the salamander creature's p50s; the gills [E]: its set has none, and p13 / p17's filament fringe reads velvety, not
    # glossy (each filament carries fine lamellae): the first pilot's 0.20 drew every filament as a bright wet line
    rough=dict(head=0.14, dorsum=0.17, venter=0.24, limb=0.17, hand=0.34, fin=0.16, ramus=0.34, filament=0.42, mouth=0.30,
               var=0.035, dark=0.05),
    # (AX7c, 10-31: hand: the hind foot's dorsum, even with its rays, still lit as one silver sheet at the hero's range
    # under the studio key, where the micro-relief has faded; the limb's 0.17 is the salamander creature's wet flank value, its
    # hands' thick matt skin rougher [E]. run() ramps it in on the blurred thin mask, so no line prints at the wrist)
    # (AX7b restart 2: the stalks 0.24 -> 0.34 [E from P p13 p17]: the o3 renders drew each stalk as a glossy tube with one
    # long highlight down it, where p13's and p17's stalks are satin with a fine grain; they also take the runtime's
    # micro-normal now at the fins' share: k_skin's gill_fin mask 0.9 on the stalks, 1 on the filaments)
    seed=20261029,
)


@wp.kernel
def k_skin(P: wp.array(dtype=wp.vec3), zone: wp.array(dtype=wp.int32), vent: wp.array(dtype=wp.float32),
           thin: wp.array(dtype=wp.float32), cav: wp.array(dtype=wp.float32), dist: wp.array(dtype=wp.float32),
           s_st: wp.array(dtype=wp.float32), cov_base: wp.array(dtype=wp.float32), rough_base: wp.array(dtype=wp.float32),
           w_head: wp.array(dtype=wp.float32), w_irid: wp.array(dtype=wp.float32), w_throat: wp.array(dtype=wp.float32),
           w_root: wp.array(dtype=wp.float32),
           g_body: wp.vec3, g_head: wp.vec3, g_ven: wp.vec3, g_blood: wp.vec3, g_tip: wp.vec3, g_mouth: wp.vec3,
           blush_thin: float, blush_ramus: float, blush_fil: float, blush_throat: float, limb_cream: float, cav_a: float,
           cav_red: float, hf: wp.vec4, hc: wp.vec4, tf: wp.vec4, tc: wp.vec4, fc: wp.vec4, fr_soft: float, w_sc: float, w_amp: float,
           fr_amp: float, fr_ven: float, fr_ven_h: float, i_part: float, i_thru: float, f_sp: float, f_r: float,
           f_from: float,
           x_dor: float, x_ven: float, x_scale: float, x_var: float,
           k_sp: float, k_r: float, k_share: float, r_var: float, r_dark: float, seed: int,
           o_col: wp.array(dtype=wp.vec3), o_masks: wp.array(dtype=wp.vec4), o_disp: wp.array(dtype=wp.vec4),
           o_rough: wp.array(dtype=wp.float32)):
    t = wp.tid()
    z = zone[t]
    p = P[t]
    v = vent[t]
    th = thin[t]
    # ---- the ground (the unpigmented skin): the head's by its station weight (no region switch), the venter's by v
    col = g_body + (g_head - g_body) * w_head[t]
    vg = v
    if z == 3 or z == 4 or z == 5:
        vg = wp.max(v, limb_cream * (1.0 - w_root[t]))      # (AX7c: RECIPE limb_cream's note)
    col = col + (g_ven - col) * vg
    bl = blush_thin * th
    if z == 6:
        bl = wp.max(bl, blush_ramus * (1.0 - w_root[t]))  # the stalks' blood, fading into the head's skin at the sockets
    if z == 7:
        bl = wp.max(bl, blush_fil)                         # the filaments' (AX7b: the red is theirs)
    bl = wp.max(bl, blush_throat * v * w_throat[t])  # the throat: the gular region's blush (p03's red throat)
    col = col + (g_blood - col) * wp.clamp(bl, 0.0, 1.0)
    if z == 5:
        col = col + (g_tip - col) * wp.clamp(dist[t], 0.0, 1.0)      # the digit tips cream (dist: 0 base .. 1 tip)
    if z == 2:
        col = g_mouth
    c_ = cav[t]
    col = col * (cav_a + (1.0 - cav_a) * c_)
    col = wp.vec3(col[0], col[1] * (1.0 - cav_red * (1.0 - c_)), col[2] * (1.0 - cav_red * (1.0 - c_)))
    # ---- the melanophore cover: the zone's light tone, then THE FRECKLES (AX7b: RECIPE freckles' note): the head's
    # field and the trunk's through one domain warp, the head's by its station weight (no region switch), thinned toward
    # the venter; the fins also carry the sweep's 1.2 mm spots; the gold patches part the melanophores over them
    keep = 1.0 - (1.0 - (fr_ven + (fr_ven_h - fr_ven) * w_head[t])) * v
    pw = proc.warp3(p, w_sc, w_amp, seed + 3)
    a1 = freckle3(pw, hf[0], hf[1], hf[2], hf[3] * keep, fr_soft, seed + 101)
    a2 = freckle3(pw, hc[0], hc[1], hc[2], hc[3] * keep, fr_soft, seed + 202)
    b1 = freckle3(pw, tf[0], tf[1], tf[2], tf[3] * keep, fr_soft, seed + 101)
    b2 = freckle3(pw, tc[0], tc[1], tc[2], tc[3] * keep, fr_soft, seed + 202)
    wh = w_head[t]
    fm = wp.max(a1[0], a2[0]) * wh + wp.max(b1[0], b2[0]) * (1.0 - wh)
    frnd = b1[1]
    if b2[0] > b1[0]:
        frnd = b2[1]
    if z == 8:
        # the fin's blotches (AX7b restart 2): p01's backlit blotches are uniformly dark (sRGB ~(76, 50, 42) against the
        # ground's (205, 190, 175)), where freckle3's own strength runs 0.55 .. 1 a spot: lifted x1.4 (most reach full)
        f3 = freckle3(pw, fc[0], fc[1], fc[2], fc[3], fr_soft, seed + 303)
        fm = wp.max(fm, wp.min(1.0, f3[0] * 1.4))
    patch = w_irid[t] * (1.0 - wp.min(1.0, i_thru * fm))
    cov = cov_base[t] * (1.0 - i_part * patch)
    if z != 7 and z != 2 and z != 9:
        cov = cov + (1.0 - cov) * fr_amp * fm * (1.0 - patch)
    cov = wp.clamp(cov, 0.0, 1.0)
    # ---- the iridophores: the head's gold patches (run() draws them), p01's silver flecks low on the rear trunk and tail
    irid = patch * (1.0 - v)
    if (z == 0 or z == 8) and s_st[t] > f_from:
        cf = proc.cellular3(p / f_sp, 0.9, seed + 37)
        fl = 1.0 - proc.smoothstep(f_r * 0.6, f_r, cf.f1 * f_sp)
        fl = fl * proc.smoothstep(f_from, f_from + 0.08, s_st[t])      # the flecks fade in (no station line)
        irid = wp.max(irid, fl * proc.smoothstep(0.25, 0.65, v) * wp.where(cf.rand < 0.55, 1.0, 0.0))
    # ---- the xanthophore wash (olive-yellow, riboflavin): broad, its strength varying slowly
    xn = proc.fbm3(p / x_scale, 2, 2.0, 0.5, seed + 41)
    xa = (x_dor + (x_ven - x_dor) * v) * (1.0 + x_var * xn)
    xa = wp.max(xa, patch)                      # the gold patches yellow (p14's, p15's)
    if z == 7 or z == 2 or z == 9:
        xa = 0.0
    # ---- the leucistic speckles: sparse dark specks on the head and back (p03)
    ck = proc.cellular3(p / k_sp, 0.9, seed + 53)
    sk = (1.0 - proc.smoothstep(k_r * 0.5, k_r, ck.f1 * k_sp)) * wp.where(ck.rand < k_share, 1.0, 0.0) * (1.0 - v)
    if z != 0 and z != 1:
        sk = 0.0
    # ---- out
    zb = float(0.0)
    if z == 7:
        zb = 1.0
    elif z == 6:
        zb = 0.9                                    # the stalks (AX7b: the runtime's micro-normal at the fins' share)
    elif z == 8:
        zb = 0.6
    elif z == 3 or z == 4 or z == 5:
        zb = 0.12                                   # the limbs and hands (AX7c: the runtime's THIN_HAND reads it)
    o_col[t] = col
    o_masks[t] = wp.vec4(th, v, zb, cov)
    o_disp[t] = wp.vec4(wp.clamp(irid, 0.0, 1.0), wp.clamp(xa, 0.0, 1.0), sk, frnd)
    # darker paint a little rougher, about the wild type's flank (cover 0.93: the zones' p50s stay the salamander creature's)
    o_rough[t] = wp.clamp(rough_base[t] + r_var * proc.fbm3(p / 2.0, 2, 2.0, 0.5, seed + 61) + r_dark * (cov - 0.93),
                          0.02, 0.6)


def zones(region, region_names, base_mm, body, km=None):
    """per texel: the zone (Z_*), the ventral value (0 dorsal .. 1 the ventral midline), the body station s (nan off the
    body) and the digit's distal share (0 .. 1), from the bake's region and the base point (life mm)"""
    names = {int(k): v for k, v in region_names.items()}
    rn = np.array([names.get(int(r), '') for r in range(max(names) + 1)] + [''])
    nm = rn[np.where(region >= 0, region, len(rn) - 1)]
    z = np.full(region.shape, Z_BODY, np.int32)
    z[np.isin(nm, ('body_head', 'body_eye', 'body_cap'))] = Z_HEAD
    z[nm == 'body_mouth'] = Z_MOUTH
    z[np.isin(nm, ('root', 'arm'))] = Z_LIMB
    z[nm == 'palm'] = Z_PALM
    z[np.isin(nm, ('digit', 'web'))] = Z_DIGIT
    z[np.isin(nm, ('ramus', 'cap'))] = Z_RAMUS
    z[nm == 'filament'] = Z_FILAMENT
    z[nm == 'fin'] = Z_FIN
    z[np.isin(nm, ('eyeball', ''))] = Z_HIDDEN          # (body_socket is the GILL sockets' skin: AX5's visible class)
    s = body.s_of(base_mm[..., 2])
    tb = np.array([body.top_bot(float(v)) for v in np.linspace(0.0, 1.0, 1001)])
    top = np.interp(s, np.linspace(0.0, 1.0, 1001), tb[:, 0])
    bot = np.interp(s, np.linspace(0.0, 1.0, 1001), tb[:, 1])
    mid = 0.5 * (top + bot)
    half = np.maximum(0.5 * (top - bot), 1e-6)
    # the ventral value: the section angle from the dorsal midline (0) round to the ventral (1), smoothed toward the
    # sides (the flank's 90 deg reads 0.5); x over the section's half depth, so a wide head reads by its own shape
    ang = np.arctan2(np.abs(base_mm[..., 0]) / half, (base_mm[..., 1] - mid) / half)
    v = np.clip(ang / np.pi, 0.0, 1.0)
    v = v * v * (3.0 - 2.0 * v)
    on_body = np.isin(z, (Z_BODY, Z_HEAD, Z_MOUTH))
    # limbs: the palm and sole face down, the rest by height under the limb's own middle (a soft 0.3 .. 0.6)
    v = np.where(on_body, v, np.where(z == Z_PALM, 0.55, np.where(z == Z_FIN, 0.25, 0.35)))
    v = np.where(z == Z_HIDDEN, 0.5, v)
    return z, v.astype(np.float32), np.where(on_body | (z == Z_FIN), s, np.nan).astype(np.float32)


def _smooth(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _thin_blur(P, thin, mask, sigma, vox=None):
    """AX7c: the thin mask averaged in 3D over a Gaussian of `sigma` (life mm) among the `mask` texels (P (H, W, 3) life
    mm): their values and a unit weight splatted into a voxel grid round them, both blurred, read back (trilinear) as
    their ratio, so a texel takes its neighbours' thinness whatever its UV island (the wrist's arm and palm texels share
    one island, AX7b's check: probe_wrist.png). Other texels keep theirs. Returns the new (H, W) mask"""
    from scipy import ndimage as nd
    vox = 0.4 * sigma if vox is None else vox
    pts = np.asarray(P, np.float64)[mask]
    val = np.asarray(thin, np.float64)[mask]
    if len(pts) == 0:
        return thin
    lo = pts.min(0) - 3.0 * sigma
    shape = tuple(int(np.ceil((pts.max(0)[a] + 3.0 * sigma - lo[a]) / vox)) + 1 for a in range(3))
    idx = np.clip(np.round((pts - lo) / vox).astype(np.int64), 0, np.array(shape) - 1)
    acc = np.zeros(shape, np.float32)
    wgt = np.zeros(shape, np.float32)
    np.add.at(acc, (idx[:, 0], idx[:, 1], idx[:, 2]), val.astype(np.float32))
    np.add.at(wgt, (idx[:, 0], idx[:, 1], idx[:, 2]), 1.0)
    acc = nd.gaussian_filter(acc, sigma / vox, mode='constant')
    wgt = nd.gaussian_filter(wgt, sigma / vox, mode='constant')
    c = ((pts - lo) / vox).T
    a_ = nd.map_coordinates(acc, c, order=1)
    w_ = nd.map_coordinates(wgt, c, order=1)
    out = np.array(thin, np.float64, copy=True)
    out[mask] = np.where(w_ > 1e-6, a_ / np.maximum(w_, 1e-6), val)
    return out


def gold_patches(P, s_all, v, on_body, body, ir, seed=20261030):
    """AX7b: the iridophore mask, ONE OR TWO GOLD PATCHES on the head's dorsal skin (RECIPE irid's note: p14's behind
    the eye, p15's between the eyes). Each patch an ellipse in the head's dorsal tangent plane (along the body axis z,
    across x) about the skin point at its station and lateral offset, its outline made irregular by a smooth noise of
    the solid coordinate (a few random sinusoids) and soft; only the upper half of the section takes it (v < 0.45).
    P (.., 3) the texels' base points, life mm. Returns the mask (..), 0 .. 1"""
    P = np.asarray(P, np.float64)
    rng = np.random.default_rng(seed)
    K_ = rng.normal(0.0, 1.0, (6, 3)) * 1.1                     # wave vectors (rad / mm): features ~1-3 mm
    ph = rng.uniform(0.0, 2 * np.pi, 6)
    noise = sum(np.cos(P @ K_[i] + ph[i]) for i in range(6)) / np.sqrt(3.0)          # about [-1.7, 1.7]
    out = np.zeros(P.shape[:-1])
    for s_c, x_off, a_al, a_ac in ir['patches']:
        z_c = float(body.z(s_c))
        d = np.sqrt(((P[..., 2] - z_c) / a_al) ** 2 + ((P[..., 0] - x_off) / a_ac) ** 2)
        d = d + ir['noise'] * noise
        m = 1.0 - _smooth(1.0 - ir['soft'], 1.0 + ir['soft'], d)
        out = np.maximum(out, m)
    return np.where(on_body & (np.asarray(v) < 0.45), out, 0.0) * (1.0 - _smooth(0.30, 0.45, np.asarray(v)))


def run(drivers, region_names, body, km, log=print, recipe=None, digit_tip=None, normal_world=None, body_dist=None,
        lip=None):
    """the material pass on one set's drivers (the bake's dict, rows top-down). Returns dict(col (H, W, 3) linear,
    masks (H, W, 4), disp (H, W, 4), rough (H, W), zone (H, W), cov (H, W) bool covered); km: x4 m per life mm.
    digit_tip: per texel 0 .. 1 the distal share on the digits (None: from the base point's distance to the low's digit
    ends is not known here: 0).
    NO REGION BOUNDARY PRINTS (the AX7 look round, 10-29: the first pass switched the ground, cover, roughness and the
    iridophores by region and station and printed a line round the neck): every zone value that differs between
    neighbouring regions blends in a continuous coordinate:
      normal_world: (H, W, 3) per texel the LOW's world normal (interpolated over its triangle; the low's normals are
        continuous across its UV seams): the ventral value v = smoothstep((1 - n_y) / 2) for every zone (None: the
        section-angle v of zones(), with constants on the appendages);
      the head: its ground, cover and roughness over the body stations R['head_blend'], the iridophore field over
        R['irid']['reach'], the throat's blush over R['throat'];
      body_dist: (H, W) per texel the life-mm distance of its point to the low's BODY skin: the appendages' (limbs,
        rami, fins) cover and roughness blend into the body's at their roots over R['root_blend'] mm (None: no blend);
      lip: the pale lip margins (RECIPE lip; AX7b, AX7c), a dict of (H, W) arrays: dist life mm to the upper lip's line,
        below (bool) under it, taper the band's strength there (1 inside the U, RECIPE corner past it), lobe 0 .. 1 the
        lobes' mask, slit 0 .. 1 the groove's apex, mouth_pale / mouth_skin 0 .. 1 its faces taking the band / the head;
        pearl (AX10, a flag): the lobe mask is the pearls', painted as RECIPE lip pearl says"""
    R = dict(RECIPE, **(recipe or {}))
    nrm = drivers['normal']
    H, W = nrm.shape[:2]
    cov = nrm[..., 3] > 0
    base = np.asarray(drivers['base'], np.float64)
    found = base[..., 3] > 0.5
    pos = np.asarray(drivers['position'], np.float64) if 'position' in drivers else base
    P = np.where(found[..., None], base[..., :3], pos[..., :3]) / km                 # life mm
    z, v, s = zones(drivers['region'], region_names, P, body)
    if normal_world is not None:
        ny = np.asarray(normal_world, np.float64)[..., 1]
        vn = np.clip(0.5 - 0.5 * np.nan_to_num(ny, nan=0.0), 0.0, 1.0)
        vn = vn * vn * (3.0 - 2.0 * vn)
        v = np.where(z == Z_HIDDEN, 0.5, np.where(np.isfinite(ny), vn, v)).astype(np.float32)   # NaN: no low normal
    thk = np.asarray(drivers['thickness'], np.float64) / km                         # life mm
    thin = np.clip(1.0 - (thk - 0.6) / (3.2 - 0.6), 0.0, 1.0)                        # [E] 0.6 mm thin .. 3.2 mm thick
    thin = thin * thin * (3.0 - 2.0 * thin)
    if R.get('thin_blur'):
        # AX7c: no glove line at the wrists and ankles (RECIPE thin_blur's note)
        hz = cov & np.isin(z, (Z_LIMB, Z_PALM, Z_DIGIT))
        thin = _thin_blur(P, thin, hz, float(R['thin_blur']))
        log(f'[skin] the thin mask on the limbs, hands and digits averaged in 3D over sigma {R["thin_blur"]} mm '
            f'({int(hz.sum()):,} texels)')
    cavity = np.clip(np.asarray(drivers['cavity'], np.float64), 0.0, 1.0)
    cb, rb = R['cover'], R['rough']
    s_all = body.s_of(P[..., 2])                       # every texel's body station (the appendages' roots read it)
    on_body = np.isin(z, (Z_BODY, Z_HEAD))
    wh_all = 1.0 - _smooth(R['head_blend'][0], R['head_blend'][1], s_all)
    wh = np.where(on_body, wh_all, 0.0)
    wi = gold_patches(P, s_all, v, on_body, body, R['irid'])          # AX7b: the head's gold patches (p14, p15)
    t0, t1, t2, t3 = R['throat']
    wt = np.where(on_body, _smooth(t0, t1, s_all) * (1.0 - _smooth(t2, t3, s_all)), 0.0)
    under = np.clip(2.0 * v - 1.0, 0, 1) * 0.6
    cov_trunk = (cb['dorsum'] + (cb['flank'] - cb['dorsum']) * np.clip(2.0 * v, 0, 1)
                 + (cb['venter'] - cb['flank']) * np.clip(2.0 * v - 1.0, 0, 1))
    cov_head = cb['head'] - (cb['head'] - cb['venter']) * under
    cov_bl = cov_trunk + (cov_head - cov_trunk) * wh_all          # the body's cover at any station
    r_trunk = rb['dorsum'] + (rb['venter'] - rb['dorsum']) * v
    r_bl = r_trunk + (rb['head'] - r_trunk) * wh_all
    # the limb, the hand plate and the digits share ONE cover: the limb's on top, going toward the palm's [L] underneath
    # by the ventral value (p16 from below: the limbs' and hands' undersides pale). The AX7 check, 10-30: the palm zone's
    # constant 0.62 on BOTH faces of the hand plate drew a zigzag line at the wrist and another at the knuckles (the wild
    # type's luminance x3.1 across those seams) and a pale cow-print hand back between a dark forearm and dark digits,
    # where p13 / p14 / p22's hands are as dark as their limbs
    hand = np.isin(z, (Z_LIMB, Z_PALM, Z_DIGIT))
    cov_zone = np.select([z == Z_MOUTH, hand, z == Z_RAMUS, z == Z_FILAMENT, z == Z_FIN, z == Z_HIDDEN],
                         [cb['mouth'], cb['limb'], cb['ramus'], cb['filament'], cb['fin'], 0.0], 0.0)
    tipd = np.zeros_like(v) if digit_tip is None else digit_tip
    cov_zone = np.where(z == Z_DIGIT, cov_zone + (cb['tip'] - cov_zone) * tipd, cov_zone)
    cov_zone = np.where(hand, cov_zone - (cov_zone - cb['palm']) * under, cov_zone)
    cov_zone = np.where(z == Z_RAMUS, cov_zone - (cov_zone - cb['venter']) * under, cov_zone)
    cov_base = np.where(on_body, cov_bl, cov_zone)
    r_zone = np.select([z == Z_MOUTH, np.isin(z, (Z_LIMB, Z_PALM, Z_DIGIT)), z == Z_RAMUS, z == Z_FILAMENT,
                        z == Z_FIN], [rb['mouth'], rb['limb'], rb['ramus'], rb['filament'], rb['fin']], rb['limb'])
    r_zone = np.where(hand, r_zone + (rb['hand'] - r_zone) * np.clip(thin / 0.35, 0.0, 1.0), r_zone)   # (RECIPE rough's note)
    r_base = np.where(on_body, r_bl, r_zone)
    wb = np.zeros(z.shape, np.float64)
    if body_dist is not None:
        app = np.isin(z, (Z_LIMB, Z_PALM, Z_DIGIT, Z_RAMUS, Z_FIN))
        wb = np.where(app, 1.0 - _smooth(0.0, R['root_blend'], np.asarray(body_dist, np.float64)), 0.0)
        cov_base = cov_base + (cov_bl - cov_base) * wb
        r_base = r_base + (r_bl - r_base) * wb
    sel = np.nonzero(cov.ravel())[0]
    n = len(sel)

    def arr(x, dt=np.float32, k=None):
        a = np.asarray(x).reshape((H * W,) + ((k,) if k else ()))[sel].astype(dt)
        return wp.array(a, dtype=wp.vec3 if k == 3 else (wp.int32 if dt == np.int32 else wp.float32))
    o_col, o_m, o_d = wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_r = wp.zeros(n, dtype=wp.float32)
    fr, ir, xa, sk = R['freckles'], R['irid'], R['xantho'], R['speckle']
    v4 = lambda t: wp.vec4(*[float(x) for x in t])                    # noqa: E731
    wp.launch(k_skin, dim=n, inputs=[
        arr(P, np.float32, 3), arr(z, np.int32), arr(v), arr(thin), arr(cavity), arr(tipd), arr(np.nan_to_num(s, nan=-1)),
        arr(cov_base), arr(r_base), arr(wh), arr(wi), arr(wt), arr(wb),
        wp.vec3(*lin(R['ground_body'])), wp.vec3(*lin(R['ground_head'])), wp.vec3(*lin(R['ground_venter'])),
        wp.vec3(*lin(R['blood'])), wp.vec3(*lin(R['tip'])), wp.vec3(*lin(R['mouth'])),
        float(R['blush']['thin']), float(R['blush']['ramus']), float(R['blush']['filament']), float(R['blush']['throat']),
        float(R['limb_cream']), float(R['cavity'][0]), float(R['cavity'][1]),
        v4(fr['head']['fine']), v4(fr['head']['coarse']), v4(fr['trunk']['fine']), v4(fr['trunk']['coarse']),
        v4(fr['fin_coarse']), float(fr['soft']), float(fr['warp'][0]), float(fr['warp'][1]), float(fr['amp']),
        float(fr['venter']), float(fr['venter_head']), float(ir['part']), float(ir['thru']), float(ir['fleck_spacing']),
        float(ir['fleck_r']),
        float(ir['fleck_from']), float(xa['dorsal']), float(xa['venter']), float(xa['scale']), float(xa['var']),
        float(sk['spacing']), float(sk['r']), float(sk['share']), float(rb['var']), float(rb['dark']), int(R['seed'])],
        outputs=[o_col, o_m, o_d, o_r])
    col = np.zeros((H * W, 3), np.float32)
    msk = np.zeros((H * W, 4), np.float32)
    dsp = np.zeros((H * W, 4), np.float32)
    rgh = np.full(H * W, 0.5, np.float32)
    col[sel], msk[sel], dsp[sel], rgh[sel] = o_col.numpy(), o_m.numpy(), o_d.numpy(), o_r.numpy()
    if lip is not None:
        # the pale lip margins (RECIPE lip): the freckles and the light tone parted to the lip's cover in a band along
        # each lip, wider on the lower, the lobes in it; AX7c: the wash parted there too and the ground toward its grey;
        # the head's skin only
        ld, below = np.asarray(lip['dist'], np.float64).ravel(), np.asarray(lip['below'], bool).ravel()
        tp = np.asarray(lip['taper'], np.float64).ravel()
        lp = R['lip']
        # the lip skin's own paint before the band parts it (AX10b's pearls: RECIPE lip pearl's note)
        cov_skin, xa_skin, col_skin = msk[:, 3].copy(), dsp[:, 1].copy(), col.copy()
        rng_l = np.random.default_rng(int(R['seed']) + 7)
        K_l = rng_l.normal(0.0, 1.0, (6, 3)) * 1.6                  # wave vectors (rad / mm): features ~1-2 mm
        ph_l = rng_l.uniform(0.0, 2.0 * np.pi, 6)
        n_l = (sum(np.cos(P @ K_l[i] + ph_l[i]) for i in range(6)) / np.sqrt(3.0)).ravel()
        e_l = lp['edge'] * n_l
        up_w = 1.0 - _smooth(lp['upper'][0], lp['upper'][1], ld)
        lo_w = 1.0 - _smooth(lp['lower'][0] + e_l, lp['lower'][1] + e_l, ld)
        pale = np.maximum(np.where(below, lo_w, up_w) * tp, np.asarray(lip['lobe'], np.float64).ravel())
        pale = np.maximum(pale * np.isin(z.ravel(), (Z_HEAD, Z_BODY)), np.asarray(lip['mouth_pale'], np.float64).ravel())
        msk[:, 3] = msk[:, 3] * (1.0 - pale) + lp['cover'] * pale
        dsp[:, 1] = dsp[:, 1] * (1.0 - pale) + lp['xantho'] * pale
        gw = (lp['ground_w'] * pale)[:, None].astype(np.float32)
        col = col * (1.0 - gw) + lin(lp['ground']).astype(np.float32)[None, :] * gw
        hl = np.asarray(lip['mouth_skin'], np.float64).ravel()      # the groove's faces that continue the head's skin
        msk[:, 3] = msk[:, 3] * (1.0 - hl) + cb['head'] * hl
        dsp[:, 1] = dsp[:, 1] * (1.0 - hl) + R['xantho']['dorsal'] * hl
        hl32 = hl[:, None].astype(np.float32)
        col = col * (1.0 - hl32) + lin(R['ground_head']).astype(np.float32)[None, :] * hl32
        sl = np.asarray(lip['slit'], np.float64).ravel().astype(np.float32)
        col = col * (1.0 - sl * (1.0 - lp['slit']['k']))[:, None]
        rgh = rgh * (1.0 - sl) + lp['slit']['rough'] * sl
        if lip.get('pearl') and 'pearl' in lp:
            # AX10b: the pearls painted as the lip (RECIPE lip pearl's note): `skin` of the way from the band's paint (the
            # lobe mask is in the band's pale) back to the lip skin's own cover, wash and ground; a thin glossy rim
            pp = lp['pearl']
            lb_ = np.asarray(lip['lobe'], np.float64).ravel().astype(np.float32)
            ks = (np.float32(pp['skin']) * lb_).astype(np.float32)
            cov_lip = cov_skin
            if pp.get('tone') is not None:
                # the lip's TONE (RECIPE lip pearl's note): the given light tone, each texel's freckle share kept on it
                cb0 = np.asarray(cov_base, np.float64).ravel()
                f_ = np.clip((cov_skin - cb0) / np.maximum(1.0 - cb0, 1e-3), 0.0, 1.0)
                cov_lip = (pp['tone'] + (1.0 - pp['tone']) * f_).astype(np.float32)
            msk[:, 3] = msk[:, 3] * (1.0 - ks) + cov_lip * ks
            dsp[:, 1] = dsp[:, 1] * (1.0 - ks) + xa_skin * ks
            col = col * (1.0 - ks[:, None]) + col_skin * ks[:, None]
            rgh = rgh * (1.0 - lb_) + np.float32(pp['rough']) * lb_
            rm = pp.get('rim')
            n_rim = 0
            if rm is not None and lip.get('rim') is not None:
                rr = (np.asarray(lip['rim'], np.float64).ravel() * lb_).astype(np.float32)
                msk[:, 3] = msk[:, 3] * (1.0 - np.float32(rm['part']) * rr)
                lr = (np.float32(rm['lift']) * rr)[:, None]
                col = col * (1.0 - lr) + lin(lp['ground']).astype(np.float32)[None, :] * lr
                rgh = rgh * (1.0 - rr) + np.float32(rm['rough']) * rr
                n_rim = int((rr > 0.5).sum())
            on_p = lb_ > 0.5
            log(f'[skin] the pearls painted as the lip: {int(on_p.sum()):,} texels, their cover p50 '
                f'{float(np.median(msk[on_p, 3])) if on_p.any() else 0.0:.2f} (the band {lp["cover"]:g}, the lip skin '
                f'{float(np.median(cov_skin[on_p])) if on_p.any() else 0.0:.2f}, {pp["skin"]:g} of the way), the rim on '
                f'{n_rim:,}')
        elif 'bead_rough' in lp:                                     # AX8: the beads glassy (RECIPE lip's note)
            lb_ = np.asarray(lip['lobe'], np.float64).ravel().astype(np.float32)
            rgh = rgh * (1.0 - lb_) + np.float32(lp['bead_rough']) * lb_
        log(f'[skin] the lip margins pale on {int((pale > 0.5).sum()):,} texels, the slit dark on {int((sl > 0.5).sum()):,}')
    log(f'[skin] {n:,} texels: zones ' + ', '.join(f'{ZONE_NAMES[k]} {int((z[cov] == k).sum()):,}'
                                                   for k in range(len(ZONE_NAMES)) if (z[cov] == k).any())
        + f'; cover p50 {np.median(msk[sel, 3]):.2f}; the gold patches on {int((wi > 0.5).sum()):,} texels')
    return dict(col=col.reshape(H, W, 3), masks=msk.reshape(H, W, 4), disp=dsp.reshape(H, W, 4),
                rough=rgh.reshape(H, W), zone=z, cov=cov)


def eye_paint(drivers, centre, axis, r_e, r_ball, size_note=''):
    """the EYE set's maps (the axolotl's eye: plan §2.4 and §15 item 9: wild type a dark pupil in a gold ring; AX7b
    read p01's eye at 8x: the pupil ~0.42 of the visible eye's radius, the ring a thin gold-brown band ~0.06 of it, the
    iris dark (the body's note below)): base colour linear, ORM, a mask pack
    (R the iris's gold ring, G the pupil, B the iris's dark outer field, A the visible cap), from each texel's angle off
    the eye's axis (the bake's position, x4 m)"""
    pos = np.asarray(drivers['position'], np.float64)[..., :3]
    cov = drivers['normal'][..., 3] > 0
    d = pos - np.asarray(centre, np.float64)
    ax = np.asarray(axis, np.float64) / np.linalg.norm(axis)
    cth = np.clip((d @ ax) / np.maximum(np.linalg.norm(d, axis=-1), 1e-12), -1.0, 1.0)
    rho = np.sqrt(np.clip(1.0 - cth ** 2, 0.0, 1.0)) * r_ball / r_e          # 1 at the edge ring
    rho = np.where(cth < 0, 2.0 - rho, rho)                                   # the back hemisphere past 1
    # AX7b (10-30; the round-6 check: "up close the iris flecks read as large leopard spots; p01's iris is a thin
    # gold-brown ring"): p01's eye at 8x (ax7b_notes/ref/p01_eye.png): a dark iris, a black pupil of ~0.42 of the
    # visible eye's radius, edged by a THIN gold-brown ring 2-3 px of its 39 px radius (~0.06 of it), a few brown flecks
    # in it; p14's a dark iris with a few gold flecks at the pupil's margin [P p01 p14]. The ring's band, the pupil, the
    # iris's dark field (the masks' R, G, B as before)
    P_R, RING_W = 0.42, 0.065
    pupil = 1.0 - np.clip((rho - (P_R - 0.01)) / 0.02, 0.0, 1.0)
    ring = np.clip((rho - (P_R - 0.01)) / 0.02, 0, 1) * (1.0 - np.clip((rho - (P_R + RING_W)) / 0.025, 0, 1))
    outer = np.clip((rho - (P_R + RING_W)) / 0.025, 0, 1)
    rng = np.random.default_rng(7)
    # a few flecks IN the ring only (small soft blobs: white noise blurred over ~1.2 texels, its top 30 %), and the dark
    # field's faint radial grain (blurred along the angle, very low contrast)
    from scipy import ndimage
    nz = ndimage.gaussian_filter(rng.random(rho.shape), 1.2)
    fleck = np.clip((nz - np.quantile(nz, 0.70)) / 0.02, 0.0, 1.0) * ring
    grain = ndimage.gaussian_filter(rng.random(rho.shape), 0.8)
    grain = (grain - grain.mean()) / max(grain.std(), 1e-6)
    gold, brown, dark, black = lin('#B9A366'), lin('#7A5A34'), lin('#2E2A26'), lin('#060608')
    ring_col = brown * 0.55 * (1.0 - fleck[..., None]) + gold * 0.55 * fleck[..., None]
    col = (black[None, None] * pupil[..., None] + ring_col * ring[..., None]
           + (dark * 0.62)[None, None] * (1.0 + 0.08 * grain[..., None]) * outer[..., None])
    col = np.where(cov[..., None], col, 0.0)
    orm = np.stack([np.where(cov, drivers['ao'], 1.0), np.full(rho.shape, 0.06), np.zeros(rho.shape)], -1)
    masks = np.stack([ring, pupil, outer, (rho <= 1.0).astype(np.float64)], -1)
    return dict(col=col.astype(np.float32), orm=orm.astype(np.float32), masks=masks.astype(np.float32), cov=cov)
