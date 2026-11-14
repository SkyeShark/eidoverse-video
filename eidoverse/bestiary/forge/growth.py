"""GROWTHS: element growth layers that grow out of a creature's own skin (DESIGN.md "GROWTH families"; the measured
rules are research/REF_SKIN_STUDY.md §7, §8 and §9 R11; the plumbing is work/bestiary/patches/material_ids.md).

Crystal clusters, ice shards, metal crystals, bismuth hoppers, nodules and spikes are SCULPT LAYERS: planned on the
block-out like every stroke (octopus_sculpt.Plan), emitted as stroke batches that carry a MATERIAL ID (the voxel grid's
per-voxel label: the stroke writes its id wherever it wins), and recorded as INSTANCE data for the material pass
(facet, height, edge, the crystal's own random) and for the GROWTHS MESH (study T ships growths as their own mesh in
their own material: DESIGN.md "Budgets"; a crystal standing 1-3 cm proud cannot bake into the skin's normal map, whose
bar is p95 3 mm).

THE STROKE (voxel.sd_stroke kinds 4 and 5): an N-gonal prism with a pyramidal termination, EXACT distance (not a bound):
  a = the base centre (buried), b = the apex, ra = R the polygon's circumradius, rb = h the tip's height along the axis
  (0: a flat top), rc = spin (the polygon's turn about the axis, radians, in prism_frame's basis). N = 6 (kind 4:
  quartz-like crystals, ice) or 4 (kind 5: bismuth's square terraces, pyrite-like cubes). In the polygon's fundamental
  wedge (face normal along y, the vertex at angle pi / N) the solid is convex, so: inside, the largest plane distance
  (exact for a convex polytope); below the base, the distance to the base polygon; outside above it, the nearer of the
  half prism face (a rectangle) and the half tip face (a triangle). sd_prism_np (numpy, float64) and sd_prism (Warp)
  are twins; test_growth_cpu checks them against each other and against brute force.

MEASURED, NEVER COPIED (study T growth meshes, REF §7 "Where growths sit" = research/ref_study/*/growth_placement.json; a
piece = a connected component of the growth mesh, its size = the world AABB diagonal of its vertices, its height = the
largest vertex distance to the skin, its foot = the vertex nearest the skin):

  preset      reference                   skin m2  pieces  size p10/50/90 m     height p10/50/90 m   dorsal feet (skin)  area
  ice_shards  ice-crab ice shards        61.81    129    .131 / .233 / .478   .040 / .075 / .227   .682 (.265) 2.57x   .064
  ice_cold    mantis-wasp cold ice            3.34     27    .192 / .255 / .389   .062 / .090 / .157   .778 (.311) 2.50x   .239
  crystal     squid-creature crystals             18.14    269    .088 / .157 / .318   .036 / .080 / .156   .368 (.168) 2.19x   .403
  metal_nodules    mantis-wasp metal nodules    3.23    100    .047 / .074 / .209   .010 / .019 / .060   .600 (.307) 1.95x   .153
  ("area" = growth-mesh area / skin area; it counts the buried parts and every face, so it is not a footprint coverage)

SCALING to a creature of skin area A (S = sqrt(A), S_ref = sqrt(A_ref)): sizes x (S / S_ref)^gamma, counts x
(S / S_ref)^(2 (1 - gamma)), so the growth-to-skin area ratio is the reference's for ANY gamma. gamma = 1 (default) is
geometric similarity: the reference's piece count, sizes in proportion. gamma = 0 keeps the reference's physical sizes.
study T's own two ice variants sit near gamma = 0 between its 1.9 m and 5.5 m creatures (pieces 0.23-0.26 m on both), but
across a 0.2-5 m roster only similarity keeps a crystal octopus reading as a small crystal squider. Three clamps act
after the scaling: a piece no larger than k_local x 2 x the local part radius (an arm tip cannot carry a mantle's
crystal), a crystal radius no larger than r_part x the local part radius, and a crystal radius no smaller than the
RESOLUTION FLOOR (a facet at least 4 voxels and 6 texels across: CG 03.47 features >= 2-3 voxels, CG 00.13 shapes need
> 8 px). A floored piece keeps its count, so the area ratio rises a little; the report prints it beside the bar. The
LOCAL PART RADIUS is a site's scale: an octopus arm's radius at the site (octopus.arm_radius), elsewhere the body's
half-thickness under the site measured with the block-out (half_thickness: half the chord along -n).

r_part MEASURED (work/bestiary/patches/growth_run/measure_part_radius.py -> part_radius.json): a reference piece's
half-width w (half its middle principal extent: between a lone prism's apothem and circumradius, a cluster's
half-width, so never below its largest crystal's radius) over the half-thickness t of the reference body under its
foot (half the chord along -n to where the ray leaves the union of the base mesh's shells):
  reference          feet   t p10/50/90 mm     w/t p50 / p90 / p95 / max    r_part = w/t p95
  ice-crab ice      115    599 / 872 / 1146   .060 / .119 / .140 / 8.5     0.14
  mantis-wasp cold ice   19    163 / 228 / 380    .289 / .492 / .524 / .656    0.52
  squid-creature crystals    267     32 / 155 / 437    .274 / 1.08 / 1.86 / 10.8    1.86 (its limb crusts: pieces wider than the
                                                                             limb; the buried-base rule binds first)
  mantis-wasp metal-nodule  100     85 / 210 / 295    .100 / .221 / .462 / .681    0.46
The p95 caps only the reference's own tail (w >= R makes w/t a generous bound on R/t). The derived presets borrow
[I]: bismuth and nodule: the metal nodules' (bismuth's hoppers have its aspect 0.9), spike ice shards'.

PLACEMENT: candidate roots (patch sites or area samples, with an area weight each, a local part radius and a
multiplicity: 8 for the octopus's reference arm, whose plan is replicated onto all eight) are drawn in a weighted
random order, weight = area x mask x exp(beta n_y) x crust. beta is solved so the feet's dorsal share (n_y > 0.5) is
the reference's bias times this creature's own dorsal skin share (REF R11: "feet on up-facing skin at 2-2.6x its
share"); crust is a low-frequency density field (patchy crusts, structure first: the bias and masks place, the field
only thins). A root is kept when its cluster's footprint clears every kept cluster's (pieces stay separate
components, as the reference counted them).

STABLE ROOTS (an option for new bases; the crystal beetle's round, 10-29): the draw order above is one stream of the
creature's rng, so the crystals follow the cage's SITE COUNT and every cage change re-rolls all of them (the crown v6b
landing: a crown edit moved every head crystal). Sites that carry 'key' (stable_sites: forge/groom/roots.py's scheme,
a slot = (seed, triangle, index on it), its point at an R2 low-discrepancy spot warped onto the triangle) are visited
in an EXPONENTIAL RACE keyed by each site's own hash (E_i / W_i, E_i ~ Exp(1) from (seed, key, slot): the same
weighted random order, now a pure function of the site), and each piece draws its size, its cluster and its crystals'
randoms from a generator seeded by its site alone; the creature's rng draws nothing there. A cage edit then moves only
the crystals whose triangles it touches (or whose neighbours it frees or blocks, and the count's last few: n_target
follows the eligible area). Sites without 'key' take the path above exactly (the octopus's looks unchanged).

CLUSTERS: a dominant crystal and Poisson satellites ringing its root (their roots 0.6-1.0 x root_off x (R0 + Ri) from
it, so the bases crowd and interpenetrate: SELF-OCCLUDING ROOTS, REF R11 "roots self-occlude (AO p50 0.61-0.77)"),
fanned away from the dominant's lean; each crystal's base is SUNK below the skin plane far enough that its whole base
polygon is buried (R sin(tilt) + margin R, at least 1.25 x the inside margin when the body is tested, plus the drop of a
convex part R^2 / 2 r_local), its axis emerging at its root point (REF §7: the reference pieces "penetrate or touch the
skin"). Tip height: quartz's rhombohedral faces stand
51.8 deg off the base, h = A / tan(38.2 deg) = 1.27 A [I: mineralogy textbook value, not re-checked here].
Three rules hold for EVERY crystal once its root is settled (the first growth run, work/bestiary/octopus_growth: a
satellite 83 deg off its own normal at the arm / web / crown saddle, its base buried 82 mm along the axis, out through
the arm's oral side and under the creature, where no voxel grid held it: 59,372 texels missed):
  * ITS OWN NORMAL: an axis leaning more than tilt_max off its root's normal turns toward it (aim_within), and the
    depth follows the true angle (no clip);
  * INSIDE THE BODY (make_cluster with sdf): the base polygon lies inside the block-out by a few voxels, the axis from
    the root down to the base inside it, the lateral edges and the axis cross the skin once (no exit and re-entry
    through a thin part), and nothing lies below the ground; with replicated arms every copy must fit. A crystal that
    fails shrinks (R and length together) until it fits; below the floor it is dropped, and a dropped dominant drops
    its piece;
  * THE PART: R <= r_part x the local part radius (above).

MATERIAL FAMILIES (fixed ids; RECIPES carries every number with its source tag; family_table() packs them for the GPU):
[M] measured on study T (REF §7/§8), [S] read from cooked data or a published table, [C] computed here from published
optical constants, [I] inferred or chosen (no measurement behind it), [P] / [D] remix/elements.py's tags (a physical
reference / its design choice). FAMILY_ID is THE ONE id table (work/bestiary/patches/material_ids_v2.md): the voxels,
the bake, family_table() and the runtime read it, and remix/elements.py reads these names and ids from this source.
New families are APPENDED to FAMILIES (an id, once written into a voxel grid or a glb, never moves). glow (linear RGB)
and film_ior are the runtime's per-family defaults (t13 writes them into the glb's extras). External tables used (no
file was downloaded):
  physicallybased.info (CC0 1.0; api.physicallybased.info/v2/materials, colour space "srgb-linear", fetched 2026-10-20)
  refractiveindex.info Bi (Hagemann, Gudat, Kunz, J. Opt. Soc. Am. 65, 742 (1975); database CC0 1.0)

THE LOOK (work/bestiary/patches/growth_look.md; measured on the study-T growth sets' textures, REF §7 / §8 and
research/ref_study/*/stats.json texture_space, never copied): each facet draws its ln L, chroma and roughness once,
seeded by its CRYSTAL (a rotated copy shades as its original), and a TARNISH varies them below the facet scale (jit_M:
the sets' ln L octaves stay flat down to 2 mm, which one draw per facet cannot give); the roughness follows ln L
(rough_L, from each set's six palette clusters: metal_nodules -0.135, squid-creature crystal -0.50, ice 0), which carries the
facet-to-facet roughness octave (metal_nodules 0.016, crystal 0.045 at the facets' scale) and the edges' gloss; EDGE WEAR on
the facet edges (edge_L, edge_S: the set's top 5 % convex texels at sigma 1 px, metal_nodules L x2.19, S x0.50; weaker on a
crystal whose facets are only a few texels across, so the worn line keeps its share of the area); SELF-OCCLUDING ROOTS
(the bake's AO times a root gradient, ROOT_AO over ROOT_Z radii above the skin line, for the sets' AO p50 0.61-0.77; the
albedo follows the AO by aol_L, the set's hp16 slope); IRREGULAR GROWTH-STEP BANDING as relief in the normal map
(growth_steps); no micro normal. THE SKIN'S RESPONSE (halo*): the family's element infusion as a LOCAL halo round each
root, in the skin pass (growth_halo; metal_nodules = the mantis-wasp metal-nodule repaint: metal 0.16 -> 0.71-0.81, S 0.65 -> 0.23,
its median L held, the texels' L spread x0.19-x3.8 over its body and x0.59-x1.63 within a halo's span, its spatial
split per octave in units of its crystals' R (halo_tarnish), transmission 0.06 -> 0.29), written into the SKIN's own
channels (the albedo, the ORM's B, the thin mask; the GROWTH pack's R stays the growth share), so the runtime's skin
terms act on it as on the skin round it (work/bestiary/patches/halo_v2.md); the full-creature infusion stays the remix
element's
"""
import numpy as np
import warp as wp

from . import material as M
from . import proc
from . import sdf as S_

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile (as the forge's)

# ----------------------------------------------------------------------------------------------------- stroke kinds
STROKE_PRISM6 = 4          # voxel.sd_stroke kind: hexagonal prism with a pyramidal tip (a, b, R, h, spin)
STROKE_PRISM4 = 5          # the same with a square section (rb = 0: flat top terraces)
STROKE_BALL = 0            # voxel.STROKE_CONE with A == B: a ball (nodules, blobs, drops)
STROKE_CONE = 0            # voxel.STROKE_CONE (spikes, horns, drips)
SIDES = {STROKE_PRISM6: 6, STROKE_PRISM4: 4}

# ----------------------------------------------------------------------------------------------------- material ids
MAT_SKIN = 0               # the creature's own skin (every voxel starts here; every 'add' without an id writes it)
MAT_KEEP = 255             # a stroke that writes no id (a carve's default: it exposes what is under it)
FAMILIES = ('ice', 'ice_clear', 'crystal', 'metal_crystal', 'metal_gold', 'metal_chrome', 'metal_gunmetal',
            'metal_silver', 'metal_copper', 'bismuth', 'liquid_metal', 'verdigris', 'rust', 'bone', 'chitin',
            'keratin', 'flesh', 'ember', 'arc',
            'obsidian', 'quartz_arc', 'spore', 'moonstone', 'void_glass')     # (20-24: remix/elements.py's, 10-21)
FAMILY_ID = {f: i + 1 for i, f in enumerate(FAMILIES)}
N_IDS = 256
# THE ONE ID SPACE's two ranges (research/CYBORG_PLAN.md §4.2.5; work/bestiary/patches/cyborg_c1_ranges.md): growth
# families take 1-63, the cyborg family's plates, seams, fasteners and glow strips 64-95 (forge/cyborg.py names them).
# unpack_ids gives no growth family outside 1-63, and the bake's growth-occlusion test drops growth ids only
ID_RANGES = dict(growth=(1, 63), cyborg=(64, 95))
GROWTH_ID_MAX = wp.constant(ID_RANGES['growth'][1])
assert max(FAMILY_ID.values()) <= ID_RANGES['growth'][1], 'a growth family past id 63 would read as a cyborg id'


def srgb8(r, g, b):
    """an sRGB 8-bit colour to linear (the exact sRGB transfer, IEC 61966-2-1: the house helper, material.srgb_eotf)"""
    return tuple(M.srgb_eotf(np.asarray([r, g, b], np.float64) / 255.0).round(4).tolist())


def fresnel0(n, k):
    """normal-incidence reflectance of a metal from its complex index n + ik (air outside)"""
    return ((n - 1.0) ** 2 + k ** 2) / ((n + 1.0) ** 2 + k ** 2)


def _bismuth_f0():
    """bismuth's F0 at 620 / 550 / 455 nm (an R, G, B point sample, not a CIE integration) from Hagemann et al. 1975
    (refractiveindex.info main/Bi/Hagemann: 413.3 nm n 1.556 k 2.27; 495.9 nm 1.865 2.67; 619.9 nm 2.244 3.10)"""
    lam = np.array([0.4133, 0.4959, 0.6199])
    n = np.array([1.556, 1.865, 2.244])
    k = np.array([2.27, 2.67, 3.10])
    out = [fresnel0(np.interp(w, lam, n), np.interp(w, lam, k)) for w in (0.620, 0.550, 0.455)]
    return tuple(np.round(out, 4).tolist())


# ----------------------------------------------------------------------------------------------------- recipes
# The table row each family id carries to the material pass (family_table): see ROW for the layout. study T's numbers are
# the calibration (Skye: the study-T numbers are proper PBR); where study T has no growth of that kind the source is named.
# sss = the study-T subsurface-opacity channel (the study-T creature skin material, REF §1), not refractive transmission; trans = three's
# refractive transmission (a transmission pass per frame: opt-in, 0 by default).
_GOLD = (1.0, 0.773, 0.307)            # physicallybased.info Gold srgb-linear (1.059, 0.773, 0.307), red clamped to 1
RECIPES = {
    'ice': dict(            # ice-crab ice shards [M]: median sRGB8 (167,219,231), L .642 (p5 .536, p95 .689)
        c0=srgb8(167, 219, 231), c1=(0.46, 0.72, 0.83),          # c1: the frost layer #B5DDEB (REF R11) [M]
        rough=0.06, rough_facet=0.0, rough_cav=0.0, rough1=0.35,  # .06/.06/.06 [M]; frost rougher (cold ice .17) [I]
        metal=0.13, metal1=0.0, sss=0.89, ior=1.31, trans=0.0,    # metal .13, sss .89 [M]; ice n 1.3098 [S]
        irid=0.0, emis=1.0, emis_tip=0.3, layer=2, layer_amt=0.35,  # M.b 1.0 [M]; exposed frost (R11 formula) [I amt]
        jit_L=0.02, jit_S=0.05, stri_amp=0.0, stri_lambda=0.25, edge_L=0.06, aol_L=0.33, fuzz=0.0, smooth=0.0,
        rough_L=0.0, edge_S=0.84,       # ln L / S octaves .019-.024 / .011-.015 at 12.8-51 mm, convex +6 % L, S -.044, AO
        jit_M=0.008,                    # hp16 slope .33, rough flat .063 (no ln L coupling), below 13 mm ln L .004-.011
        glow=(0.0, 0.90, 1.0),          # [M]
        src='REF §7/§8 ice-crab growth [M]; ior physicallybased.info Ice 1.3098 [S]; glow study G ice emissive (0 .90 1) '
            'via remix/elements.py [S]; facet jitter, edge, AO link: its texture_space stats [M]'),
    'ice_clear': dict(      # a refractive variant of the same ice (DESIGN: "clear shards ... transmission")
        c0=srgb8(167, 219, 231), c1=(0.46, 0.72, 0.83), rough=0.06, rough_facet=0.0, rough_cav=0.0, rough1=0.35,
        metal=0.0, metal1=0.0, sss=0.30, ior=1.31, trans=0.90, irid=0.0, emis=0.75, emis_tip=0.3, layer=2,
        layer_amt=0.25, jit_L=0.03, jit_S=0.08, stri_amp=0.0, stri_lambda=0.25, edge_L=0.15, aol_L=0.0, fuzz=0.0,
        smooth=0.0, glow=(0.0, 0.90, 1.0),
        src='colour/rough as ice [M]; metal 0 + ior 1.31 physical [S]; trans .90 [I]; emis = cold ice .75 [M]; glow as '
            'ice [S]'),
    'crystal': dict(        # squid-creature crystals [M]: median sRGB8 (181,124,197), L .293, rough .12/.27/.73, metal .52
        c0=srgb8(181, 124, 197), c1=srgb8(181, 124, 197),
        rough=0.27, rough_facet=0.06, rough_cav=0.0, rough1=0.27,     # facet-to-facet: octave RMS .045 at 14.5-58 mm,
        metal=0.52, metal1=0.52, sss=0.94, ior=1.54, trans=0.0,       # carried by rough_L, the residual for r(rough,
        irid=0.0, emis=0.71, emis_tip=0.3, layer=0, layer_amt=0.0,    # ln L) -.66 [M]; sss .94 [M]; quartz n 1.54 [S];
        jit_L=0.16, jit_S=0.40, stri_amp=0.02, stri_lambda=0.5, edge_L=0.245, aol_L=2.4, fuzz=0.0, smooth=0.0,
        rough_L=-0.50, edge_S=0.99,     # M.b .71 [M]; jit_L / jit_S calibrated to its ln L / S octaves .089-.107 /
        # .023-.030 at 14.5-58 mm (S .13-.63: lavender to near-grey facets), convex +28 % L, S -.004, AO
        jit_M=0.04,                     # hp16 slope 2.42, rough per ln L of its six palette clusters -.50, below its facets
        glow=(0.62, 0.40, 1.0),         # ln L .02-.06 (0-14 mm: clean faces) [M]
        rough_lo=0.12,                  # the set's roughness p5 .12: its brightest clusters stay at .17-.22, so its ln L
        # coupling saturates where ours ran on to the 0.02 clamp (the maps' p5 .020: growth_look.md §2.1 / §4) [M]
        src='REF §7/§8 squid-creature crystals [M]; facet jitter, edge, AO link, rough_L: its texture_space stats and palette '
            '[M]; rough_lo: its roughness p5 [M]; step banding depth and pitch [I]; glow colour remix/elements.py [D]'),
    'metal_crystal': dict(  # mantis-wasp metal-nodule growths [M]: median sRGB8 (140,134,117), L .241 (p5 .085, p95 .576),
        c0=srgb8(140, 134, 117), c1=srgb8(140, 134, 117),            # rough .23/.36/.49, AO p50 .77
        rough=0.36, rough_facet=0.035, rough_cav=0.0, rough1=0.36,    # facet-to-facet octave .016 through rough_L, the
        metal=0.94, metal1=0.94, sss=0.12, ior=0.0, trans=0.0,        # residual for r(rough, ln L) ~ -.80 [M]; metal .94
        # (.84-1), sss .12 [M]
        irid=0.0, emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0,
        jit_L=0.26, jit_S=0.26, stri_amp=0.02, stri_lambda=0.5, edge_L=0.78, aol_L=0.67, fuzz=0.10, smooth=0.0,
        rough_L=-0.135, edge_S=0.50, jit_M=0.38,   # jit_L / jit_S / jit_M: calibrated so the maps' ln L / S octaves
        # meet the set's .09-.13 / .012-.013 from 2 to 35 mm (x.508, this creature's scale); convex L x2.19 (ln .78), S
        # -.072 of .144, AO hp16 slope .67 (occluded x.815), rough per ln L of its six palette clusters -.135 [M];
        # THE HALO (v2, halo_v2.md): the mantis-wasp metal-nodule body repaint at the root (metal .16 -> .71-.81 p50, S x.354
        # = .65 -> .23, median L x1.00 with the texels' L ratio spread p10 / p90 x.186 / x3.77 over its body, x.59 /
        # x1.63 within 4.9 of its crystals' radii, transmission .063 -> .29) [M], gone by .8-1.6 crystal radii [the
        # lead's call]; halo_S is the chroma scale that gives the sRGB S x.354 on the octopus skin (calibrated: lsh
        # scales linear chroma); halo_L the ln L spread per unit of the skin pass's driver term, whose tarnish is the
        # reference's split in the crystal's R (halo_tarnish; research/ref_study/mantiwasp_zyr/halo_scale.json): 1.1,
        # the core's L ratio box-filtered to the reference's texel p10 / p90 x.46-.48 / x2.8-3.1, and in the engine the
        # ring renders x1.01 of the same pixels with the halo off (x.88-1.11 by frame); halo_T the thin mask that brings
        # the runtime's subsurface (.85 thin + the .06 floor) to .29. Written into the skin's own channels (v1 rode the
        # pack's R, so the runtime's tint and display held off it; at metal .6-.8 with each texel's own L it read as a
        # dark ring)
        halo=0.0, halo_metal=0.78, halo_S=0.27, halo_r0=0.8, halo_r1=1.6, halo_L=1.1, halo_T=0.27,
        src='REF §7/§8 metal-nodule [M]; RoughEdge 0.1 from the metal-nodule MI [S]; facet jitter, edge, AO link, rough_L: its '
            'texture_space stats and palette [M]; halo: variant_mantiwasp_vs_mantiwasp_zyr.json [M]; step banding [I]'),
    'metal_gold': dict(c0=_GOLD, c1=_GOLD, rough=0.18, rough_facet=0.05, rough_cav=-0.15, rough1=0.18, metal=1.0,
                       metal1=1.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0, layer=0,
                       layer_amt=0.0, jit_L=0.04, jit_S=0.06, stri_amp=0.015, stri_lambda=0.25, edge_L=0.0, aol_L=0.0,
                       fuzz=0.0, smooth=0.0,
                       src='physicallybased.info Gold srgb-linear [S]; rough in DESIGN 0.08-0.3 [I]'),
    'metal_chrome': dict(c0=(0.654, 0.685, 0.701), c1=(0.654, 0.685, 0.701), rough=0.08, rough_facet=0.03,
                         rough_cav=-0.10, rough1=0.08, metal=1.0, metal1=1.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0,
                         emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0, jit_L=0.03, jit_S=0.04, stri_amp=0.01,
                         stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=0.0,
                         src='physicallybased.info Chromium srgb-linear [S]; rough DESIGN low end [I]'),
    'metal_gunmetal': dict(c0=(0.441, 0.400, 0.361), c1=(0.441, 0.400, 0.361), rough=0.28, rough_facet=0.06,
                           rough_cav=-0.20, rough1=0.28, metal=1.0, metal1=1.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0,
                           emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0, jit_L=0.05, jit_S=0.05, stri_amp=0.015,
                           stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=0.0,
                           src='physicallybased.info Titanium srgb-linear as the gunmetal base [S/I]; rough [I]'),
    'metal_silver': dict(c0=(0.991, 0.985, 0.974), c1=(0.991, 0.985, 0.974), rough=0.12, rough_facet=0.04,
                         rough_cav=-0.15, rough1=0.12, metal=1.0, metal1=1.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0,
                         emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0, jit_L=0.03, jit_S=0.04, stri_amp=0.01,
                         stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=0.0,
                         src='physicallybased.info Silver srgb-linear [S]; rough [I]'),
    'metal_copper': dict(c0=(0.932, 0.623, 0.522), c1=(0.932, 0.623, 0.522), rough=0.22, rough_facet=0.05,
                         rough_cav=-0.15, rough1=0.22, metal=1.0, metal1=1.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0,
                         emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0, jit_L=0.04, jit_S=0.06, stri_amp=0.015,
                         stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=0.0,
                         src='physicallybased.info Copper srgb-linear [S]; rough [I]'),
    'bismuth': dict(        # bismuth metal under a thin oxide film (the colours are thin-film interference)
        c0=_bismuth_f0(), c1=_bismuth_f0(), rough=0.08, rough_facet=0.03, rough_cav=-0.10, rough1=0.08,
        metal=1.0, metal1=1.0, sss=0.0, ior=0.0, trans=0.0,
        irid=1.0, irid_lo=100.0, irid_hi=400.0,                       # three's KHR_materials_iridescence default range
        emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0, jit_L=0.02, jit_S=0.02, stri_amp=0.0, stri_lambda=0.25,
        edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=0.0, film_ior=2.0,
        src='F0 [C] from Hagemann 1975 n,k; iridescence range = GLTFLoader default [S]; film IOR ~2.0-2.3 [I, '
            'Bi2O3 index not verified]; rough [I]'),
    'liquid_metal': dict(c0=(0.781, 0.780, 0.778), c1=(0.781, 0.780, 0.778), rough=0.03, rough_facet=0.0,
                         rough_cav=0.0, rough1=0.03, metal=1.0, metal1=1.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0,
                         emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0, jit_L=0.0, jit_S=0.0, stri_amp=0.0,
                         stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=1.0,
                         src='physicallybased.info Mercury srgb-linear [S]; rough .03 (a liquid surface) [I]'),
    'verdigris': dict(      # copper going green in its cavities (DESIGN)
        c0=(0.932, 0.623, 0.522), c1=srgb8(67, 179, 174),            # c1 = the named colour verdigris #43B3AE [I]
        rough=0.30, rough_facet=0.05, rough_cav=-0.15, rough1=0.85, metal=1.0, metal1=0.0, sss=0.0, ior=0.0,
        trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0, layer=1, layer_amt=0.85, jit_L=0.04, jit_S=0.06,
        stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0, smooth=0.0,
        src='copper physicallybased.info [S]; patina colour and roughness [I, unmeasured]'),
    'rust': dict(           # iron spines rusting on the exposed side
        c0=(0.530, 0.513, 0.494), c1=srgb8(124, 58, 36), rough=0.40, rough_facet=0.06, rough_cav=-0.15,
        rough1=0.90, metal=1.0, metal1=0.0, sss=0.0, ior=0.0, trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0,
        layer=2, layer_amt=0.75, jit_L=0.05, jit_S=0.08, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=0.0,
        fuzz=0.0, smooth=0.0, src='iron physicallybased.info [S]; rust colour sRGB8 (124,58,36) and rough [I]'),
    'bone': dict(           # bone scaled into the skin envelope (REF R2: L <= 0.65; clean dry bone is L .78)
        c0=(0.556, 0.556, 0.466), c1=(0.556, 0.556, 0.466), rough=0.60, rough_facet=0.05, rough_cav=-0.20,
        rough1=0.60, metal=0.0, metal1=0.0, sss=0.30, ior=1.5, trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0,
        layer=0, layer_amt=0.0, jit_L=0.05, jit_S=0.05, stri_amp=0.0, stri_lambda=0.25, edge_L=0.20, aol_L=1.0,
        fuzz=0.0, smooth=0.5,
        src='physicallybased.info Bone (0.793,0.793,0.664) x0.70 [S scaled]; aol_L chitin row R4 [M]; rough [I]'),
    'chitin': dict(         # mantis-wasp body, dorsal [M]: median sRGB8 (101,79,33), L .085, rough .17/.45/.64, metal .16
        c0=srgb8(101, 79, 33), c1=srgb8(101, 79, 33), rough=0.45, rough_facet=0.06, rough_cav=-0.20, rough1=0.45,
        metal=0.16, metal1=0.16, sss=0.10, ior=1.5, trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0, layer=0,
        layer_amt=0.0, jit_L=0.08, jit_S=0.06, stri_amp=0.0, stri_lambda=0.25, edge_L=0.30, aol_L=1.2, fuzz=0.05,
        smooth=0.3, src='REF §5/§8 mantis-wasp [M]; R4 chitin relief row [M]; shell sss .06-.12 [M]'),
    'keratin': dict(        # REF R3 "eye socket and keratin": #A5864D, L .29, S .53, rough .60, AO .22 [M]
        c0=srgb8(165, 134, 77), c1=srgb8(165, 134, 77), rough=0.60, rough_facet=0.05, rough_cav=-0.20, rough1=0.60,
        metal=0.0, metal1=0.0, sss=0.20, ior=1.55, trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0, layer=0,
        layer_amt=0.0, jit_L=0.06, jit_S=0.06, stri_amp=0.0, stri_lambda=0.25, edge_L=0.20, aol_L=1.0, fuzz=0.03,
        smooth=0.5, src='REF R3 [M]; keratin n ~1.55 as octopus_beak [I]'),
    'flesh': dict(          # the creature's own skin re-shaded as a taut blister (flesh=1: c0 is a tint)
        c0=(1.0, 1.0, 1.0), c1=(1.0, 1.0, 1.0), rough=0.12, rough_facet=0.0, rough_cav=-0.30, rough1=0.12, metal=0.0,
        metal1=0.0, sss=0.95, ior=1.33, trans=0.0, irid=0.0, emis=0.0, emis_tip=0.0, layer=0, layer_amt=0.0,
        jit_L=0.0, jit_S=0.0, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=1.5, fuzz=0.10, smooth=1.0, flesh=1.0,
        src='rough: salamander creature wet skin p50 .14-.20 [M]; sss: the transmission curve cap .95 (R8) [M]'),
    'ember': dict(          # fire: charred crust, emissive cores
        c0=(0.025, 0.020, 0.018), c1=(0.025, 0.020, 0.018), rough=0.75, rough_facet=0.05, rough_cav=0.0, rough1=0.75,
        metal=0.0, metal1=0.0, sss=0.0, ior=1.5, trans=0.0, irid=0.0, emis=1.0, emis_tip=0.0, layer=0,
        layer_amt=0.0, jit_L=0.10, jit_S=0.05, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0,
        smooth=1.0, glow=(1.0, 0.14, 0.0),
        src='char L .02 within the R2 floor .010 [I]; pulse = R10 (the study-T salamander creature material instance) [S]; glow the study-G bug-dog creature fire '
            'emissive (1 .14 0), remix/elements.py fire [S]'),
    'arc': dict(            # electric: dark slate, blue emissive
        c0=(0.045, 0.055, 0.065), c1=(0.045, 0.055, 0.065), rough=0.45, rough_facet=0.05, rough_cav=0.0, rough1=0.45,
        metal=0.0, metal1=0.0, sss=0.0, ior=1.5, trans=0.0, irid=0.0, emis=1.0, emis_tip=0.0, layer=0,
        layer_amt=0.0, jit_L=0.05, jit_S=0.05, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0,
        smooth=1.0, glow=(0.0, 0.06, 1.0),
        src='slate after an electric variant material (study G) (non-PBR, structure only) darkened [I]; glow the study-G bug-dog creature electric '
            'emissive (0 .06 1), remix/elements.py electric [S]'),
    # remix/elements.py's growth families that this table lacked (10-21, material_ids_v2.md): its numbers and tags; its
    # the subsurface-opacity channel ("trans") is sss here, its F0 an ior, its rough p50 the rough and its p5-p95 spread / 3.29 the facet jitter
    'obsidian': dict(       # volcanic glass shards, near-black, glowing (fire's growth)
        c0=(0.022, 0.020, 0.022), c1=(0.022, 0.020, 0.022), rough=0.08, rough_facet=0.05, rough_cav=-0.10,
        rough1=0.08, metal=0.0, metal1=0.0, sss=0.0, ior=1.49, trans=0.0, irid=0.0, emis=1.0, emis_tip=0.3, layer=0,
        layer_amt=0.0, jit_L=0.04, jit_S=0.04, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0,
        smooth=0.0, glow=(1.0, 0.25, 0.02),
        src='elements.py: volcanic glass n ~1.49 (F0 .039), near-black [P]; rough .04/.08/.20, glow (1 .25 .02) at mask '
            '1 [D]; emis_tip, jitter [I]'),
    'quartz_arc': dict(     # milky quartz carrying arc light (electric's growth)
        c0=(0.60, 0.63, 0.68), c1=(0.60, 0.63, 0.68), rough=0.12, rough_facet=0.075, rough_cav=-0.20, rough1=0.12,
        metal=0.0, metal1=0.0, sss=0.85, ior=1.544, trans=0.0, irid=0.0, emis=1.0, emis_tip=0.3, layer=0,
        layer_amt=0.0, jit_L=0.06, jit_S=0.10, stri_amp=0.02, stri_lambda=0.25, edge_L=0.10, aol_L=0.5, fuzz=0.0,
        smooth=0.0, glow=(0.25, 0.45, 1.0),
        src='elements.py: quartz n 1.544, milky, L .63 under the .69 ice ceiling [P]; sss .85, rough .05/.12/.30, '
            'glow [D]; striations, edge and AO terms as crystal [I]'),
    'spore': dict(          # fungal blisters and caps, translucent, glowing gills (poison's growth)
        c0=(0.40, 0.42, 0.12), c1=(0.40, 0.42, 0.12), rough=0.45, rough_facet=0.10, rough_cav=-0.20, rough1=0.45,
        metal=0.0, metal1=0.0, sss=0.80, ior=1.4, trans=0.0, irid=0.0, emis=0.6, emis_tip=0.0, layer=0,
        layer_amt=0.0, jit_L=0.08, jit_S=0.08, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=1.0, fuzz=0.10,
        smooth=1.0, glow=(0.26, 1.0, 0.0),
        src='elements.py: albedo, rough .25/.45/.60, sss .80, mask .6 [D]; glow study G poison hue (.26 1 0) [S]; ior '
            '1.4 (hydrated tissue), organic smoothing, AO and fuzz terms [I]; no micro normal (REF R7)'),
    'moonstone': dict(      # feldspar with adularescence (moonlight's growth)
        c0=(0.62, 0.64, 0.72), c1=(0.62, 0.64, 0.72), rough=0.10, rough_facet=0.035, rough_cav=-0.10, rough1=0.10,
        metal=0.0, metal1=0.0, sss=0.70, ior=1.54, trans=0.0, irid=0.8, irid_lo=200.0, irid_hi=380.0, emis=0.4,
        emis_tip=0.3, layer=0, layer_amt=0.0, jit_L=0.04, jit_S=0.06, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0,
        aol_L=0.0, fuzz=0.0, smooth=0.0, glow=(0.81, 0.54, 1.0), film_ior=1.55,
        src='elements.py: feldspar n 1.52-1.58 [P] (1.54: its F0 .045); adularescence as a thin film .8 at ior 1.55, '
            '200-380 nm, sss .70, rough .06/.10/.18, mask .4 [D]; glow study G moonlight hue (.81 .54 1) [S]'),
    'void_glass': dict(     # dark glass shards (dark gaia's growth)
        c0=(0.010, 0.008, 0.014), c1=(0.010, 0.008, 0.014), rough=0.04, rough_facet=0.025, rough_cav=-0.10,
        rough1=0.04, metal=0.0, metal1=0.0, sss=0.0, ior=1.54, trans=0.0, irid=0.0, emis=1.0, emis_tip=0.3, layer=0,
        layer_amt=0.0, jit_L=0.03, jit_S=0.04, stri_amp=0.0, stri_lambda=0.25, edge_L=0.0, aol_L=0.0, fuzz=0.0,
        smooth=0.0, glow=(0.90, 0.05, 0.40),
        src='elements.py: albedo, rough .02/.04/.10, glow and mask [D]; F0 .045 -> n 1.54; L .009 meets the R2 floor '
            '.010 in growth_material'),
}
# the family-table row layout (NP floats per id; material.py-style GPU table, read by growth_material)
ROW = ('c0r', 'c0g', 'c0b', 'c1r', 'c1g', 'c1b', 'rough', 'rough_facet', 'rough_cav', 'rough1', 'metal', 'metal1',
       'sss', 'ior', 'trans', 'irid', 'irid_lo', 'irid_hi', 'emis', 'emis_tip', 'layer', 'layer_amt', 'jit_L',
       'jit_S', 'stri_amp', 'stri_lambda', 'edge_L', 'aol_L', 'fuzz', 'smooth', 'micro', 'flesh',
       'rough_L', 'edge_S', 'halo', 'halo_metal', 'halo_S', 'halo_r0', 'halo_r1', 'jit_M', 'halo_L', 'halo_T',
       'rough_lo')
NP = len(ROW)
assert NP == 43                 # the row stride of growth_material, growth_texel, vein_texel, growth_halo, k_growths
# the look terms' neutral values (the module notes' THE LOOK), set on every recipe so no row key is ever missing: no ln L
# coupling of the roughness, the edges' chroma kept, no halo (a family without a measured skin response), no tarnish,
# and the roughness floor at the 0.02 every family had (rough_lo: a family whose measured set holds a higher p5 sets its
# own: crystal)
LOOK_DEFAULTS = dict(rough_L=0.0, edge_S=1.0, halo=0.0, halo_metal=0.0, halo_S=1.0, halo_r0=1.0, halo_r1=2.5, jit_M=0.0,
                     halo_L=0.0, halo_T=0.0, rough_lo=0.02)
for _r in RECIPES.values():
    for _k, _v in LOOK_DEFAULTS.items():
        _r.setdefault(_k, _v)
# THE ROOT (growth_material): the bake's AO times 1 - ROOT_AO (1 - smoothstep(0, ROOT_Z, the height above the skin line
# in crystal radii)), so a cluster's roots read self-occluded (REF §7: the growth sets' AO p50 0.61-0.77); calibrated on
# the metal_nodules run to its AO p50 0.77 (growth_look.md)
ROOT_AO = wp.constant(0.15)
ROOT_Z = wp.constant(1.5)


def family_table():
    """(N_IDS * NP,) float32: row id = the family's parameters (row 0 = skin: all zero, the skin pass owns it)"""
    T = np.zeros((N_IDS, NP), np.float32)
    for name, fid in FAMILY_ID.items():
        r = RECIPES[name]
        vals = dict(r)
        vals.setdefault('irid_lo', 100.0)
        vals.setdefault('irid_hi', 400.0)
        vals.setdefault('micro', 0.0)               # REF R7: no micro normal on growths
        vals.setdefault('flesh', 0.0)
        row = list(vals['c0']) + list(vals['c1']) + [vals[k] for k in ROW[6:]]
        T[fid] = np.asarray(row, np.float32)
    return T.reshape(-1)


def smooth_table():
    """(N_IDS,) float32: the sculpt's smoothing weight per material id (voxel.SparseSDF.smooth(id_weights=)): crystal
    facets 0 (they stay crisp), organic growths their recipe's, the skin and unused ids 1 (smoothed as before)"""
    w = np.ones(N_IDS, np.float32)
    for name, fid in FAMILY_ID.items():
        w[fid] = RECIPES[name]['smooth']
    return w


def relevel_table():
    """(N_IDS,) float32: the relevel's weight per material id (voxel.SparseSDF.redistance(id_weights=)): 0 for the crisp
    families (smooth 0: a prism stroke wrote EXACT distances there, and the upwind relevel only rounds their edges), 1
    elsewhere"""
    return (smooth_table() > 0.0).astype(np.float32)


def smooth_weights(mid):
    """the smoothing weight per voxel from its id: mid (n,) uint8 -> (n,) float32 (host-side; the GPU reads
    smooth_table() by id)"""
    return smooth_table()[np.asarray(mid, np.int64)]


# ----------------------------------------------------------------------------------------------------- presets
# Measured statistics (REF §7 / growth_placement.json) and the cluster model calibrated against them by
# work/bestiary/patches/scratch_growth/test_growth_cpu.py (c_L, the tilt and the satellites; see the report there).
# r_part: the crystal radius over the local part radius (the module notes: growth_run/part_radius.json, w/t p95 [M];
# the derived presets borrow their reference's [I])
PLACEMENT = {
    'ice_shards': dict(ref='ice-crab ice shards', A_ref=61.806, N=129, size=(0.131, 0.233, 0.478),
                       height=(0.040, 0.075, 0.227), dorsal=0.682, skin_dorsal=0.265, area=0.0638, tris=3197,
                       shape='prism6', tip=2.6, aspect=(3.6, 0.25), aspect_min=1.6, tilt0=0.55, tilt_max=1.05,
                       k_mean=0.5, k_max=3, spread=(0.30, 0.65), sat_len=(0.40, 0.80), sat_r=(0.55, 0.90),
                       root_off=0.85, c_L=0.62, margin=0.35, fillet=0.12, r_part=0.14),
    'ice_cold': dict(ref='mantis-wasp cold ice', A_ref=3.341, N=27, size=(0.192, 0.255, 0.389),
                     height=(0.062, 0.090, 0.157), dorsal=0.778, skin_dorsal=0.311, area=0.239, tris=5226,
                     shape='prism6', tip=2.2, aspect=(2.8, 0.25), aspect_min=1.5, tilt0=0.50, tilt_max=1.05,
                     k_mean=4.0, k_max=8, spread=(0.35, 0.80), sat_len=(0.35, 0.80), sat_r=(0.50, 0.85),
                     root_off=0.80, c_L=0.40, margin=0.35, fillet=0.12, r_part=0.52),
    'crystal': dict(ref='squid-creature crystals', A_ref=18.144, N=269, size=(0.088, 0.157, 0.318),
                    height=(0.036, 0.080, 0.156), dorsal=0.368, skin_dorsal=0.168, area=0.403, tris=12502,
                    shape='prism6', tip=1.27, aspect=(2.6, 0.30), aspect_min=1.3, tilt0=0.35, tilt_max=0.95,
                    k_mean=1.5, k_max=5, spread=(0.30, 0.70), sat_len=(0.40, 0.85), sat_r=(0.55, 0.90),
                    root_off=0.80, c_L=0.55, margin=0.35, fillet=0.20, r_part=1.86),
    'metal_nodules': dict(ref='mantis-wasp metal nodules', A_ref=3.234, N=100, size=(0.047, 0.074, 0.209),
                     height=(0.010, 0.019, 0.060), dorsal=0.600, skin_dorsal=0.307, area=0.153, tris=11157,
                     shape='prism6', tip=0.8, aspect=(0.9, 0.25), aspect_min=0.6, tilt0=0.45, tilt_max=1.0,
                     k_mean=2.5, k_max=6, spread=(0.30, 0.80), sat_len=(0.45, 0.85), sat_r=(0.55, 0.90),
                     root_off=0.70, c_L=0.30, margin=0.35, fillet=0.15, r_part=0.46),
    # derived presets: sizes and counts from the nearest measured reference [I]
    'bismuth': dict(ref='squid-creature crystals (counts, sizes) [I]', A_ref=18.144, N=269, size=(0.088, 0.157, 0.318),
                    height=(0.036, 0.080, 0.156), dorsal=0.368, skin_dorsal=0.168, area=0.403, tris=12502,
                    shape='hopper', tip=0.0, aspect=(0.9, 0.15), aspect_min=0.6, tilt0=0.25, tilt_max=0.7,
                    k_mean=1.0, k_max=3, spread=(0.20, 0.50), sat_len=(0.45, 0.80), sat_r=(0.50, 0.80),
                    root_off=0.90, c_L=0.40, margin=0.35, fillet=0.0, steps=4, r_part=0.46),
    'nodule': dict(ref='mantis-wasp metal nodules (counts, sizes) [I]', A_ref=3.234, N=100,
                   size=(0.047, 0.074, 0.209), height=(0.010, 0.019, 0.060), dorsal=0.600, skin_dorsal=0.307,
                   area=0.153, tris=11157, shape='ball', k_mean=2.0, k_max=6, root_off=0.9, c_L=0.40, sink=0.35,
                   fillet=0.6, tilt0=0.0, tilt_max=0.0, spread=(0.0, 0.0), sat_len=(0.4, 0.8), sat_r=(0.40, 0.75),
                   aspect=(1.0, 0.0), aspect_min=1.0, tip=0.0, margin=0.35, drip=0.0, r_part=0.46),
    'spike': dict(ref='ice-crab ice shards (counts, sizes) [I]', A_ref=61.806, N=129, size=(0.131, 0.233, 0.478),
                  height=(0.040, 0.075, 0.227), dorsal=0.682, skin_dorsal=0.265, area=0.0638, tris=3197,
                  shape='cone', tip=0.12, aspect=(3.2, 0.25), aspect_min=1.5, tilt0=0.55, tilt_max=1.05,
                  k_mean=0.5, k_max=3, spread=(0.30, 0.65), sat_len=(0.40, 0.80), sat_r=(0.55, 0.90),
                  root_off=0.85, c_L=0.62, margin=0.35, fillet=0.40, bend=0.35, r_part=0.14),
}
PAIRING = dict(ice='ice_shards', ice_clear='ice_shards', crystal='crystal', metal_crystal='metal_nodules',
               metal_gold='crystal', metal_chrome='crystal', metal_gunmetal='crystal', metal_silver='crystal',
               metal_copper='crystal', bismuth='bismuth', liquid_metal='nodule', verdigris='spike', rust='spike',
               bone='spike', chitin='spike', keratin='spike', flesh='nodule',
               # elements.py's (10-21): shards as ice's (its feet .68 dorsal), quartz and feldspar as the crystals,
               # caps and blisters as nodules [I]
               obsidian='ice_shards', quartz_arc='crystal', spore='nodule', moonstone='crystal', void_glass='ice_shards')
# ember and arc: VEINS along the skin's own patch grooves (the texture tier already draws the groove distance:
# proc.cellular3 edge in the anatomical coordinate), an emissive id painted by the material pass, no strokes needed


def lognormal_q(q10, q50, q90):
    """(mu, sigma) of a lognormal through the quantiles (sigma from the p10-p90 span)"""
    return float(np.log(q50)), float((np.log(q90) - np.log(q10)) / (2.0 * 1.2815516))


# ----------------------------------------------------------------------------------------------------- frames
def onb(n):
    """Duff et al. 2017 (JCGT 6(1)) branchless orthonormal basis (e1, e2) of unit normals n (k, 3); the Warp twin is
    onb_e1 / onb_e2. The sign rule (n_z < 0 -> -1, else +1, also for -0.0) is shared exactly"""
    n = np.atleast_2d(np.asarray(n, np.float64))
    s = np.where(n[:, 2] < 0.0, -1.0, 1.0)
    a = -1.0 / (s + n[:, 2])
    b = n[:, 0] * n[:, 1] * a
    e1 = np.stack([1.0 + s * n[:, 0] ** 2 * a, s * b, -s * n[:, 0]], -1)
    e2 = np.stack([b, s + n[:, 1] ** 2 * a, -n[:, 1]], -1)
    return e1, e2


def prism_frame(a, b, spin):
    """the prism's axis n (base -> apex), its face-0 normal direction u (onb e1 turned by spin about n), v = n x u, and
    its length L; arrays (k, 3) / (k,)"""
    a = np.atleast_2d(np.asarray(a, np.float64))
    b = np.atleast_2d(np.asarray(b, np.float64))
    ax = b - a
    L = np.linalg.norm(ax, axis=1)
    n = ax / np.maximum(L, 1e-30)[:, None]
    e1, e2 = onb(n)
    sp = np.broadcast_to(np.asarray(spin, np.float64), L.shape)
    u = np.cos(sp)[:, None] * e1 + np.sin(sp)[:, None] * e2
    v = np.cross(n, u)
    return n, u, v, L


def spin_for(n, u):
    """the spin that makes prism_frame's u equal the given direction u (projected off n): rotated copies of a crystal
    (the octopus's replicated arms) must carry the ROTATED frame, which onb alone does not give"""
    e1, e2 = onb(n)
    u = np.atleast_2d(np.asarray(u, np.float64))
    return np.arctan2((u * e2).sum(1), (u * e1).sum(1))


# ----------------------------------------------------------------------------------------------------- the SDF
def _closest_on_tri_np(p, a, b, c):
    """Ericson's closest point on triangle (a, b, c) to p, vectorised over rows (k, 3)"""
    ab, ac, ap = b - a, c - a, p - a
    d1 = (ab * ap).sum(1)
    d2 = (ac * ap).sum(1)
    bp = p - b
    d3 = (ab * bp).sum(1)
    d4 = (ac * bp).sum(1)
    cp = p - c
    d5 = (ab * cp).sum(1)
    d6 = (ac * cp).sum(1)
    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    den = 1.0 / np.where(np.abs(va + vb + vc) < 1e-300, 1e-300, va + vb + vc)
    out = a + ab * (vb * den)[:, None] + ac * (vc * den)[:, None]
    done = np.zeros(len(p), bool)

    def put(mask, val):
        nonlocal out, done
        m = mask & ~done
        out = np.where(m[:, None], val, out)
        done |= m
    put((d1 <= 0) & (d2 <= 0), a)
    put((d3 >= 0) & (d4 <= d3), b)
    put((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + ab * (d1 / np.maximum(d1 - d3, 1e-300))[:, None])
    put((d6 >= 0) & (d5 <= d6), c)
    put((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + ac * (d2 / np.maximum(d2 - d6, 1e-300))[:, None])
    put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0),
        b + (c - b) * ((d4 - d3) / np.maximum((d4 - d3) + (d5 - d6), 1e-300))[:, None])
    return out


def prism_local_np(p, a, b, R, h, spin, sides):
    """p's coordinates in the prism's fundamental wedge: (x along the face from its centre line, y along the face
    normal, z along the axis), the facet index and the prism's measures (A apothem, w0 half edge, zs shoulder, L)"""
    p = np.atleast_2d(np.asarray(p, np.float64))
    n, u, v, L = prism_frame(a, b, spin)
    q = p - np.atleast_2d(np.asarray(a, np.float64))
    z = (q * n).sum(1)
    x0 = (q * u).sum(1)
    y0 = (q * v).sum(1)
    sector = 2.0 * np.pi / sides
    th = np.arctan2(y0, x0)
    k = np.floor(th / sector + 0.5)
    tp = th - k * sector
    r = np.hypot(x0, y0)
    y = r * np.cos(tp)
    x = r * np.abs(np.sin(tp))
    facet = np.mod(k.astype(np.int64), sides)
    bc = lambda t: np.broadcast_to(np.asarray(t, np.float64), z.shape)
    L = bc(L)
    R = bc(R)
    A = R * np.cos(np.pi / sides)
    w0 = R * np.sin(np.pi / sides)
    hh = np.clip(bc(h), 0.0, L)
    return x, y, z, facet, A, w0, L - hh, L, hh


def sd_prism_np(p, a, b, R, h, spin, sides=6):
    """EXACT signed distance to the N-gonal prism with a pyramidal (h > 0) or flat (h = 0) termination; p (k, 3) and
    per-row or broadcast prism parameters. The numpy twin of sd_prism"""
    x, y, z, facet, A, w0, zs, L, h = prism_local_np(p, a, b, R, h, spin, sides)
    hn = np.sqrt(h * h + A * A)
    tipf = h * y + A * (z - L)
    inside = (z >= 0.0) & (y <= A) & (tipf <= 0.0)
    d_in = np.maximum(np.maximum(-z, y - A), tipf / hn)
    d2b = np.where(y > A, np.hypot(x - np.minimum(x, w0), y - A), 0.0)
    d_below = np.hypot(d2b, z)
    cx = np.clip(x, 0.0, w0)
    cz = np.clip(z, 0.0, zs)
    d_rect = np.sqrt((x - cx) ** 2 + (y - A) ** 2 + (z - cz) ** 2)
    P = np.stack([x, y, z], -1)
    zero = np.zeros_like(x)
    M = np.stack([zero, A, zs], -1)
    C = np.stack([w0, A, zs], -1)
    T = np.stack([zero, zero, L], -1)
    d_tri = np.linalg.norm(P - _closest_on_tri_np(P, M, C, T), axis=1)
    d_out = np.minimum(d_rect, d_tri)
    return np.where(inside, d_in, np.where(z < 0.0, d_below, d_out))


@wp.func
def onb_e1(n: wp.vec3):
    s = float(1.0)
    if n[2] < 0.0:
        s = -1.0
    a = -1.0 / (s + n[2])
    b = n[0] * n[1] * a
    return wp.vec3(1.0 + s * n[0] * n[0] * a, s * b, -s * n[0])


@wp.func
def onb_e2(n: wp.vec3):
    s = float(1.0)
    if n[2] < 0.0:
        s = -1.0
    a = -1.0 / (s + n[2])
    b = n[0] * n[1] * a
    return wp.vec3(b, s + n[1] * n[1] * a, -n[1])


@wp.func
def closest_on_tri(p: wp.vec3, a: wp.vec3, b: wp.vec3, c: wp.vec3):
    """Ericson, Real-Time Collision Detection 5.1.5"""
    ab = b - a
    ac = c - a
    ap = p - a
    d1 = wp.dot(ab, ap)
    d2 = wp.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = p - b
    d3 = wp.dot(ab, bp)
    d4 = wp.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        return a + ab * (d1 / wp.max(d1 - d3, 1.0e-30))
    cp = p - c
    d5 = wp.dot(ab, cp)
    d6 = wp.dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        return a + ac * (d2 / wp.max(d2 - d6, 1.0e-30))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        return b + (c - b) * ((d4 - d3) / wp.max((d4 - d3) + (d5 - d6), 1.0e-30))
    den = va + vb + vc
    if wp.abs(den) < 1.0e-30:
        return a
    return a + ab * (vb / den) + ac * (vc / den)


@wp.struct
class PrismLocal:
    x: float             # along the face, from its centre line (>= 0: the fundamental wedge)
    y: float             # along the face normal (the polygon's gauge)
    z: float             # along the axis from the base
    facet: int           # the face index 0..N-1 (round(angle / sector) from prism_frame's u)
    A: float             # apothem
    w0: float            # half edge length
    zs: float            # the shoulder (where the tip starts)
    L: float             # the axis length
    h: float             # the tip height (clamped to L)


@wp.func
def prism_local(p: wp.vec3, a: wp.vec3, b: wp.vec3, R: float, h: float, spin: float, sides: int):
    out = PrismLocal()
    ax = b - a
    L = wp.length(ax)
    n = ax / wp.max(L, 1.0e-30)
    e1 = onb_e1(n)
    e2 = onb_e2(n)
    u = e1 * wp.cos(spin) + e2 * wp.sin(spin)
    v = wp.cross(n, u)
    q = p - a
    z = wp.dot(q, n)
    x0 = wp.dot(q, u)
    y0 = wp.dot(q, v)
    sector = 6.283185307179586 / float(sides)
    th = wp.atan2(y0, x0)
    k = wp.floor(th / sector + 0.5)
    tp = th - k * sector
    r = wp.sqrt(x0 * x0 + y0 * y0)
    out.y = r * wp.cos(tp)
    out.x = r * wp.abs(wp.sin(tp))
    out.z = z
    ki = int(k)
    out.facet = ((ki % sides) + sides) % sides
    out.A = R * wp.cos(3.141592653589793 / float(sides))
    out.w0 = R * wp.sin(3.141592653589793 / float(sides))
    hh = wp.clamp(h, 0.0, L)
    out.h = hh
    out.L = L
    out.zs = L - hh
    return out


@wp.func
def sd_prism(p: wp.vec3, a: wp.vec3, b: wp.vec3, R: float, h: float, spin: float, sides: int):
    """voxel.sd_stroke kinds 4 (sides 6) and 5 (sides 4): EXACT signed distance to the N-gonal prism from base a to
    apex b, circumradius R, a pyramidal tip of height h (0: flat), turned by spin about the axis"""
    if wp.length(b - a) < 1.0e-9:
        return wp.length(p - a) - R
    pl = prism_local(p, a, b, R, h, spin, sides)
    x = pl.x
    y = pl.y
    z = pl.z
    A = pl.A
    w0 = pl.w0
    zs = pl.zs
    L = pl.L
    hh = pl.h
    tipf = hh * y + A * (z - L)
    if z >= 0.0 and y <= A and tipf <= 0.0:
        return wp.max(wp.max(-z, y - A), tipf / wp.sqrt(hh * hh + A * A))
    if z < 0.0:
        d2b = float(0.0)
        if y > A:
            dx = x - wp.min(x, w0)
            d2b = wp.sqrt(dx * dx + (y - A) * (y - A))
        return wp.sqrt(d2b * d2b + z * z)
    cx = wp.clamp(x, 0.0, w0)
    cz = wp.clamp(z, 0.0, zs)
    d_rect = wp.length(wp.vec3(x - cx, y - A, z - cz))
    P = wp.vec3(x, y, z)
    d_tri = wp.length(P - closest_on_tri(P, wp.vec3(0.0, A, zs), wp.vec3(w0, A, zs), wp.vec3(0.0, 0.0, L)))
    return wp.min(d_rect, d_tri)


# ----------------------------------------------------------------------------------------------------- clusters
def _dir(n, t1, t2, th, ph):
    return np.cos(th) * n + np.sin(th) * (np.cos(ph) * t1 + np.sin(ph) * t2)


def aim_within(d, n, tilt_max):
    """the unit axis d turned toward the unit normal n, in the plane of the two, until it leans tilt_max off n; d itself
    (and False) when it already leans no more. An axis straight into the skin turns toward onb's e1 of n"""
    c = float(d @ n)
    if c >= np.cos(tilt_max) - 1e-12:
        return d, False
    t = d - c * n
    lt = float(np.linalg.norm(t))
    t = t / lt if lt > 1e-9 else onb(n[None])[0][0]
    return np.cos(tilt_max) * n + np.sin(tilt_max) * t, True


def crystal_strokes(shape, G, root, n, d, R, Lv, r_loc, r_min, spin, m_floor=0.0):
    """ONE crystal's stroke dicts once aimed and sized: its unit axis d (base -> apex) leaves the skin at root (normal
    n), R its radius, Lv its visible length. Its base is SUNK so the whole base polygon lies below the skin plane
    (depth R sin(tilt) + max(margin R, m_floor), plus the drop of a convex part R^2 / 2 r_loc), along the axis at the
    TRUE angle (tb = depth / cos(tilt): aim_within keeps tilt <= tilt_max). m_floor: the least depth of the base's top
    corner (make_cluster: 1.25 x its inside margin when it tests the body; 0.35 R alone leaves a 1.9 mm crystal's
    corner 0.66 mm deep, never inside by 3 voxels). Shapes: a hexagonal prism with a pyramidal tip, a bismuth hopper
    (terraces and its pit), a round cone (spikes), a ball (nodules)"""
    ct = float(np.clip(d @ n, -1.0, 1.0))
    st = float(np.sqrt(max(0.0, 1.0 - ct * ct)))
    drop = R * R / (2.0 * r_loc) if np.isfinite(r_loc) and r_loc > R else 0.0
    if shape == 'ball':
        sink = G['sink'] * R
        c = root - n * sink
        return [dict(kind=STROKE_BALL, a=c, b=c, R=R, h=R, spin=0.0, root=root, n=n, zskin=sink, vis=R - sink)]
    depth = R * st + max(G['margin'] * R, m_floor) + drop    # the base polygon's top corner below the skin plane
    tb = depth / max(ct, 1e-6)                       # along the axis to the base centre
    T = tb + Lv
    base = root - d * tb
    apex = base + d * T
    if shape == 'cone':
        return [dict(kind=STROKE_CONE, a=base, b=apex, R=R, h=G['tip'] * R, spin=0.0, root=root, n=n, zskin=tb,
                     vis=Lv)]
    if shape == 'hopper':
        # bismuth: a stepped HOPPER: square terraces stacked on one axis and one spin (each sunk 2 % of the height
        # into the one below, so no coplanar caps), each narrower by 18 %, and a square pit carved into the top
        # (a carve that writes no id: its walls show the bismuth it cuts into). The resolution floor holds for
        # every terrace and the pit, not only the base (test_material_ids_cpu: at 0.5 mm voxels a 3 mm hopper's
        # pit, 0.25 R, was sub-voxel): fewer terraces on a small hopper, and no pit below the floor
        m = max(1, min(int(G.get('steps', 4)), 1 + int((1.0 - r_min / R) / 0.18 + 1e-9)))
        out = []
        for j in range(m):
            z0 = max(0.0, j / m * T - 0.02 * T)
            z1 = (j + 1) / m * T
            Rj = R * (1.0 - 0.18 * j)
            out.append(dict(kind=STROKE_PRISM4, a=base + d * z0, b=base + d * z1, R=Rj, h=0.0, spin=spin,
                            root=root, n=n, zskin=tb - z0, vis=Lv, carve=False))
        Rt = R * (1.0 - 0.18 * (m - 1))
        if 0.55 * Rt >= r_min:
            out.append(dict(kind=STROKE_PRISM4, a=base + d * (T - 0.6 * T / m), b=base + d * (T + 0.05 * T),
                            R=0.55 * Rt, h=0.0, spin=spin, root=root, n=n, zskin=tb, vis=0.0, carve=True))
        return out
    A = R * np.cos(np.pi / 6)
    h = min(G['tip'] * A, 0.7 * T)
    return [dict(kind=STROKE_PRISM6, a=base, b=apex, R=R, h=h, spin=spin, root=root, n=n, zskin=tb, vis=Lv)]


def _polyline(P, spacing):
    """a polyline's points about `spacing` apart (its corners kept)"""
    seg = []
    for p, q in zip(P[:-1], P[1:]):
        m = max(2, int(np.ceil(np.linalg.norm(q - p) / spacing)) + 1)
        seg.append(p[None] + np.linspace(0.0, 1.0, m)[:, None] * (q - p)[None])
    return np.vstack(seg)


def crystal_probe(strokes, d, margin, spacing):
    """one crystal's INSIDE-THE-BODY test geometry (its stroke dicts, its unit axis d):
      inside (k, 3) + thr (k,): points whose block-out distance must fall below thr: the base polygon's vertices, edge
        midpoints and centre (thr -margin) and the axis from the root down to the base (thr -min(margin, t cos / 2) at
        the depth t along it: the point stays inside, by the margin once deeper than it);
      lines: polylines from the base up (every lateral edge and face midline over each terrace or prism to its apex,
        the axis from the base to the top), each of which may cross the skin once (out by more than the margin, then
        in again by more than the margin: an exit and re-entry through a thin part);
      verts (j, 3): points that bound the crystal from below (the ground test)"""
    body = [s for s in strokes if not s.get('carve', False)]
    s0 = body[0]
    root, n = s0['root'], s0['n']
    ct = float(np.clip(d @ n, 1e-6, 1.0))
    tb = float(np.linalg.norm(root - s0['a']))       # the axis from the root down to the base centre
    ax_dir = d
    k0 = int(s0['kind'])
    if k0 in SIDES:
        rings = [prism_vertices(s['a'], s['b'], s['R'], s['h'], s['spin'], SIDES[int(s['kind'])]) for s in body]
        lines = []
        for base_r, sh_r, ap in rings:
            mb = 0.5 * (base_r + np.roll(base_r, 1, axis=0))
            ms = 0.5 * (sh_r + np.roll(sh_r, 1, axis=0))
            lines += [np.vstack([base_r[k], sh_r[k], ap]) for k in range(len(base_r))]
            lines += [np.vstack([mb[k], ms[k], ap]) for k in range(len(base_r))]
        b0 = rings[0][0]
        base = np.vstack([b0, 0.5 * (b0 + np.roll(b0, 1, axis=0)), s0['a'][None]])
        lines.append(np.vstack([s0['a'], body[-1]['b']]))
        verts = np.vstack([np.vstack([r[0], r[1], r[2][None]]) for r in rings])
    elif np.linalg.norm(s0['b'] - s0['a']) < 1e-12:
        # a ball: its lowest point under the skin, and the axis along n through it
        c, r = s0['a'], float(s0['R'])
        base = (c - n * r)[None]
        tb = float(np.linalg.norm(root - base[0]))
        ax_dir, ct = n, 1.0
        lines = [np.vstack([c - n * r, c + n * r])]
        verts = (c - np.array([0.0, r, 0.0]))[None]
    else:
        # a round cone (voxel.STROKE_CONE: radius R at a, h at b): its end circles, eight lines between them
        a, b, ra, rb = s0['a'], s0['b'], float(s0['R']), float(s0['h'])
        e1, e2 = onb(d[None])
        ang = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
        cs = np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2
        ra_, rb_ = a + ra * cs, b + rb * cs
        base = np.vstack([ra_, a[None]])
        lines = [np.vstack([ra_[k], rb_[k]]) for k in range(8)] + [np.vstack([a, b])]
        verts = np.vstack([a - np.array([0.0, ra, 0.0]), b - np.array([0.0, rb, 0.0])])
    m_ax = max(2, int(np.ceil(tb / spacing)) + 1) if tb > 0 else 0
    t_ax = np.linspace(tb, 0.0, m_ax)[:-1] if m_ax else np.zeros(0)       # (the root itself left out: it is skin)
    axis = root[None] - t_ax[:, None] * ax_dir[None]
    inside = np.vstack([base, axis]) if len(axis) else base
    thr = np.concatenate([np.full(len(base), -margin), -np.minimum(margin, 0.5 * t_ax * ct)])
    return inside, thr, [_polyline(L, spacing) for L in lines], verts


def _fit_ok(vals_in, thr, vals_lines, verts, margin, ground):
    """crystal_probe's verdict: every inside point below its threshold, no line out and back in by more than the
    margin, nothing under the ground"""
    if vals_in is not None:
        if not np.all(vals_in < thr):
            return False
        for v in vals_lines:
            seen = np.maximum.accumulate(v > margin)
            if np.any(seen[:-1] & (v[1:] < -margin)):
                return False
    return ground is None or float(verts[:, 1].min()) >= ground


def make_cluster(p, nrm, s_target, G, rng, r_min, r_loc=np.inf, settle=None, sdf=None, ground=None, margin=0.0,
                 stats=None, rots=None, shrink=0.85):
    """one piece at root p (normal nrm) of target size s_target (m, an AABB diagonal): a list of crystal dicts, EMPTY
    when its dominant cannot stand there. The dominant's VISIBLE length is c_L x s_target; satellites ring its root,
    fanned away from its lean. The draws are the same as ever (the same rng gives the same plan); then the rules of the
    module notes hold for every crystal:
      * THE PART: R0 <= G['r_part'] x r_loc (the length scales with it, so the aspect holds; the satellites follow the
        dominant's size); no piece where even the floor exceeds it;
      * ITS OWN NORMAL: after the satellites settle, an axis more than tilt_max off its root's own normal turns toward
        it (aim_within), and the base depth follows the true angle (crystal_strokes);
      * INSIDE THE BODY (sdf: the block-out's signed distance, e.g. prog.eval; ground: the plane y the creature stands
        on): crystal_probe's tests, for the crystal and, with rots (3 x 3 rotations: the replicated arms), every
        rotated copy. A crystal that fails shrinks (R and its visible length together, x shrink a step, the last step
        to the floor) until it passes; at the floor it is dropped; a dropped dominant drops the piece.
    margin: the inside margin (m: a few voxels). stats: a dict of counters (turned, capped, shrunk, dropped,
    pieces_dropped) to add to"""
    shape = G['shape']
    cap = G.get('r_part', np.inf) * r_loc
    if cap < r_min * (1.0 - 1e-9):
        if stats is not None:
            stats['pieces_dropped'] = stats.get('pieces_dropped', 0) + 1
        return []                                      # the part is too thin for a crystal above the floor
    e1, e2 = onb(nrm[None])
    t1, t2 = e1[0], e2[0]
    asp0 = float(np.exp(rng.normal(np.log(G['aspect'][0]), G['aspect'][1])))
    L0 = G['c_L'] * s_target
    R0 = L0 / (2.0 * asp0)
    if R0 > cap:                                       # the radius follows the part (its shape kept)
        L0 *= cap / R0
        R0 = cap
        if stats is not None:
            stats['capped'] = stats.get('capped', 0) + 1
    if R0 < r_min:
        R0 = r_min
        L0 = max(L0, 2.0 * G['aspect_min'] * R0)
    th0 = min(abs(rng.normal(0.0, G['tilt0'])) if G['tilt0'] > 0 else 0.0, G['tilt_max'])
    ph0 = rng.uniform(0.0, 2.0 * np.pi)
    roots = [np.asarray(p, np.float64)]
    dirs = [_dir(nrm, t1, t2, th0, ph0)]
    lens = [L0]
    rads = [R0]
    k = int(min(rng.poisson(G['k_mean']), G['k_max']))
    for i in range(k):
        psi = ph0 + np.pi + 2.0 * np.pi * (i + rng.uniform(-0.3, 0.3)) / max(k, 1)
        Li = L0 * rng.uniform(*G['sat_len'])
        Ri = max(R0 * rng.uniform(*G['sat_r']), r_min)
        Li = max(Li, 2.0 * G['aspect_min'] * Ri)
        thi = min(0.4 * th0 + rng.uniform(*G['spread']), G['tilt_max'])
        off = G['root_off'] * (R0 + Ri) * rng.uniform(0.6, 1.0)
        roots.append(p + off * (np.cos(psi) * t1 + np.sin(psi) * t2))
        dirs.append(_dir(nrm, t1, t2, thi, psi))
        lens.append(Li)
        rads.append(Ri)
    roots = np.asarray(roots)
    nr = np.tile(nrm, (len(roots), 1))
    if settle is not None and len(roots) > 1:
        rp, rn = settle(roots[1:])
        roots[1:] = rp
        nr[1:] = rn / np.linalg.norm(rn, axis=1, keepdims=True)
    nc = len(roots)
    # the spins, drawn as they always were (one per prism or hopper, in crystal order), before any crystal can drop
    spins = [rng.uniform(0.0, 2.0 * np.pi / (4 if shape == 'hopper' else 6)) if shape not in ('ball', 'cone') else 0.0
             for _ in range(nc)]
    strokes, alive, f, turned = fit_crystals(shape, G, roots, nr, dirs, rads, lens, spins, r_loc, r_min, sdf, ground,
                                             margin, rots, shrink)
    if stats is not None:
        stats['turned'] = stats.get('turned', 0) + turned
        if alive[0]:
            stats['shrunk'] = stats.get('shrunk', 0) + int((alive & (f < 1.0)).sum())
            stats['dropped'] = stats.get('dropped', 0) + int((~alive[1:]).sum())
        else:
            stats['pieces_dropped'] = stats.get('pieces_dropped', 0) + 1
    if not alive[0]:
        return []                                         # the dominant cannot stand here: no piece
    out = []
    for i in range(nc):
        if alive[i]:
            out += strokes[i]
    return out


def fit_crystals(shape, G, roots, nr, dirs, rads, lens, spins, r_loc, r_min, sdf=None, ground=None, margin=0.0,
                 rots=None, shrink=0.85):
    """a piece's crystals once drawn (crystal 0 its dominant): every axis turned within tilt_max of ITS OWN root normal
    (aim_within), the strokes built (crystal_strokes), and with sdf or ground the INSIDE-THE-BODY fit (crystal_probe on
    the crystal and, with rots, every rotated copy; a failing crystal shrinks, R and length together, until it passes
    or drops at the floor; the search stops once the dominant drops). Returns (strokes per crystal, alive (bool),
    the scale each kept, the number of axes turned)"""
    nc = len(roots)
    D = np.zeros((nc, 3))
    turned = 0
    for i in range(nc):
        d = np.asarray(dirs[i], np.float64) / np.linalg.norm(dirs[i])
        if shape != 'ball':
            d, tr = aim_within(d, nr[i], G['tilt_max'])
            turned += int(tr)
        D[i] = d
    R_i = np.asarray(rads, np.float64)
    L_i = np.asarray(lens, np.float64)
    f = np.ones(nc)
    m_floor = 1.25 * margin if sdf is not None else 0.0

    def build(i):
        return crystal_strokes(shape, G, roots[i], nr[i], D[i], f[i] * R_i[i], f[i] * L_i[i], r_loc, r_min, spins[i],
                               m_floor)
    strokes = [build(i) for i in range(nc)]
    alive = np.ones(nc, bool)
    if sdf is not None or ground is not None:
        # inside the body: test, shrink the failing ones a step (the last step lands on the floor), test again
        ok = np.zeros(nc, bool)
        R3 = [np.eye(3)] if rots is None else [np.asarray(Rm, np.float64) for Rm in rots]
        for _ in range(64):
            pend = np.nonzero(alive & ~ok)[0]
            if not len(pend) or not alive[0]:
                break
            probes = [crystal_probe(strokes[i], D[i], margin, max(margin, 0.25 * f[i] * R_i[i], 1e-5)) for i in pend]
            vals = None
            if sdf is not None:
                pts = np.vstack([np.vstack([pb[0]] + pb[2]) for pb in probes])
                vals = np.stack([np.asarray(sdf(pts @ Rm.T), np.float64) for Rm in R3])     # (copies, points)
            o = 0
            for j, i in enumerate(pend):
                inside, thr, lines, verts = probes[j]
                good = True
                for c in range(len(R3)):
                    vi = vals[c, o:o + len(inside)] if vals is not None else None
                    oo = o + len(inside)
                    vl = []
                    for L in lines:
                        vl.append(vals[c, oo:oo + len(L)] if vals is not None else None)
                        oo += len(L)
                    vy = verts @ R3[c].T
                    good &= _fit_ok(vi, thr, vl, vy, margin, ground)
                o += len(inside) + sum(len(L) for L in lines)
                if good:
                    ok[i] = True
                    continue
                fi = max(f[i] * shrink, r_min / R_i[i])
                if fi >= f[i] * (1.0 - 1e-12):
                    alive[i] = False                       # it failed at the floor: dropped
                else:
                    f[i] = fi
                    strokes[i] = build(i)
        alive &= ok
    return strokes, alive, f, turned


def cluster_reach(cl, p, nrm):
    """the piece's footprint radius about its root (the clearance the next piece needs)"""
    r = 0.0
    for c in cl:
        if c.get('carve', False):
            continue
        d = c['b'] - c['a']
        L = np.linalg.norm(d)
        lat = 0.0 if L < 1e-12 else np.linalg.norm(np.cross(d / L, nrm)) * L
        r = max(r, np.linalg.norm(c['root'] - p) + lat + c['R'])
    return r


def crust_field(P, S, rng, n_waves=6):
    """a smooth density in [0, 1] over the creature (random plane waves at ~S/3 wavelengths, tanh-shaped): crusts"""
    k = rng.normal(size=(n_waves, 3))
    k = k / np.linalg.norm(k, axis=1, keepdims=True) * (2.0 * np.pi / (0.33 * S))
    ph = rng.uniform(0.0, 2.0 * np.pi, n_waves)
    f = np.cos(P @ k.T + ph).sum(1) / np.sqrt(n_waves / 2.0)
    return 0.5 + 0.5 * np.tanh(1.2 * f)


def solve_beta(ny, w, target, lo=-10.0, hi=60.0):
    """beta such that sum(w e^(beta ny) [ny > 0.5]) / sum(w e^(beta ny)) = target (monotone in beta: bisection)"""
    up = ny > 0.5
    ref = float(ny.max()) if len(ny) else 0.0

    def share(b):
        e = w * np.exp(b * (ny - ref))
        return float(e[up].sum() / max(e.sum(), 1e-300))
    if share(hi) < target:
        return hi
    if share(lo) > target:
        return lo
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if share(m) < target:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def stable_hash(seed, key, slot, ch):
    """STABLE ROOTS' integer hash: forge/groom/roots.py's lowbias32 chain (its hkey before the [0, 1) map), vectorised
    over per-site seeds; a uint64 array of uint32 values that depends on nothing but (seed, key, slot, ch)"""
    from .groom import roots as RT
    a = RT.h32((np.asarray(key, np.int64) & 0xFFFFFFFF).astype(np.uint64) * np.uint64(2654435761) +
               (np.asarray(seed, np.int64) & 0xFFFFFFFF).astype(np.uint64) * np.uint64(97))
    return RT.h32(a ^ (np.asarray(slot, np.int64).astype(np.uint64) * np.uint64(0x27D4EB2F) +
                       np.uint64(ch) * np.uint64(0x165667B1)))


def stable_sites(V, F, d_max, seed, oversample=1.0, tris=None):
    """STABLE candidate roots on a base's low (the module notes' STABLE ROOTS): forge/groom/roots.py's per-triangle
    hashed slots on (V (m, 3) metres, F (k, 3)): n_t = floor(area_t x d_max x oversample + h(t)) slots on triangle t,
    slot j at an R2 point warped onto it, so a slot is a pure function of (seed, t, j). d_max: slots per m^2 (the
    candidates' density: grow() thins them by its weights; a few per piece footprint is plenty). A base of several placed
    pieces calls this once per piece with its own seed (and keeps the pieces' triangle numbering). Returns grow()'s
    site keys: p (n, 3) on the low, w (n,) the skin area a slot stands for (1 / (d_max oversample)), tri, bary (n, 3),
    key (= tri), slot, seed (n,); the caller adds n, mask, scale, mult (and projects p onto its high)"""
    import types
    from .groom import roots as RT
    V = np.asarray(V, np.float64)
    F = np.asarray(F, np.int64)
    area = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    tri, k, bary = RT.candidates(types.SimpleNamespace(F=F, area=area), d_max * 1.0e-4, int(seed), oversample, tris)
    p = bary[:, 0, None] * V[F[tri, 0]] + bary[:, 1, None] * V[F[tri, 1]] + bary[:, 2, None] * V[F[tri, 2]]
    return dict(p=p, w=np.full(len(tri), 1.0 / (d_max * oversample)), tri=tri, bary=bary, key=tri.copy(), slot=k,
                seed=np.full(len(tri), int(seed) & 0xFFFFFFFF, np.int64))


def stable_draws(sites, n):
    """the STABLE ROOTS' per-site draws (sites with 'key'): E (n,) the exponential race's variates (the visiting order
    is argsort(E / W)), seeds (n,) each site's own generator seed (64 bits), and the keys they came from"""
    key = np.broadcast_to(np.asarray(sites['key'], np.int64), (n,))
    slot = np.broadcast_to(np.asarray(sites.get('slot', 0), np.int64), (n,))
    seed = np.broadcast_to(np.asarray(sites.get('seed', 0), np.int64), (n,))
    u = (stable_hash(seed, key, slot, 11) >> np.uint64(8)).astype(np.float64) / 16777216.0
    seeds = (stable_hash(seed, key, slot, 12) << np.uint64(32)) | stable_hash(seed, key, slot, 13)
    return dict(E=-np.log1p(-u), seeds=seeds, key=key, slot=slot, seed=seed)


def half_thickness(sdf, P, N, t_max=0.30, eps=2.0e-5, iters=96):
    """the body's HALF-THICKNESS under skin points: half the chord from P along -N (N the outward unit normals) to
    where the signed distance turns non-negative again. Sphere tracing from the inside: |sd| is the distance to the
    NEAREST surface, never more than the distance to the exit along the ray, so a step of 0.9 |sd| cannot pass it.
    sdf(points (k, 3)) -> (k,) signed distances (prog.eval). Returns (n,) metres; t_max / 2 where no exit is found"""
    P = np.atleast_2d(np.asarray(P, np.float64))
    N = np.atleast_2d(np.asarray(N, np.float64))
    t = np.full(len(P), 2.0e-4)
    live = np.ones(len(P), bool)
    for _ in range(iters):
        idx = np.nonzero(live)[0]
        if not len(idx):
            break
        f = np.asarray(sdf(P[idx] - N[idx] * t[idx, None]), np.float64)
        gone = f >= -eps
        live[idx[gone]] = False
        t[idx[~gone]] += np.maximum(-0.9 * f[~gone], eps)
        live &= t < t_max
    return 0.5 * np.minimum(t, t_max)


def grow(sites, preset, family, skin_area, rng, gamma=1.0, voxel=0.0003, texel=1.0 / 4590.0, bias=None,
         crust=0.5, count_scale=1.0, size_scale=1.0, k_local=2.0, spacing=1.0, settle=None, sdf=None, ground=None,
         margin=None, rots=None, log=print):
    """plan the growth pieces of one family over a creature.

    sites: dict(p (n, 3) candidate roots on the block-out, n (n, 3) their normals, w (n,) the skin area each stands
    for (m^2), optional scale (n,) the local part radius (m), mult (n,) how many copies a root stands for (8 on the
    octopus's reference arm), mask (n,) eligibility 0..1, arm (n,) bool: the roots whose plan is replicated by rots).
    STABLE ROOTS (the module notes): sites carrying key (n,) (with slot and seed (n,): stable_sites gives all three)
    are visited in their own hashed order and each piece draws from its site's own generator; optional crust_seed (int)
    and crust_S (m) fix the crust field's waves and wavelength (default: a hash of the smallest seed, and S below).
    skin_area: the creature's whole skin (m^2). With sdf (the block-out's signed distance, prog.eval), every site's part
    radius is the smaller of its scale and the body's half-thickness under it (half_thickness, measured when the site
    is first tried) and every crystal must lie inside the body (make_cluster: margin, default 3 voxels; ground: the
    plane y the creature stands on; rots: the replicated arms' rotations, every copy tested).
    Returns a dict of per-crystal arrays (kind, a, b, R, h, spin, root, n, zskin, vis, piece, fam, rnd) plus the
    piece list and a report dict"""
    G = PLACEMENT[preset]
    fam = FAMILY_ID[family]
    P = np.asarray(sites['p'], np.float64)
    Nn = np.asarray(sites['n'], np.float64)
    Nn = Nn / np.linalg.norm(Nn, axis=1, keepdims=True)
    n = len(P)
    w = np.broadcast_to(np.asarray(sites.get('w', 1.0), np.float64), (n,)).copy()
    mult = np.broadcast_to(np.asarray(sites.get('mult', 1.0), np.float64), (n,)).copy()
    mask = np.broadcast_to(np.asarray(sites.get('mask', 1.0), np.float64), (n,)).copy()
    loc = np.broadcast_to(np.asarray(sites.get('scale', np.inf), np.float64), (n,)).copy()
    loc0 = loc.copy()                       # the sites' own part radii (an arm site's: its tube's)
    seen = np.zeros(n, bool)                # the sites whose half-thickness was measured (over every round)
    arm = np.broadcast_to(np.asarray(sites.get('arm', False), bool), (n,)).copy()
    margin = 3.0 * voxel if margin is None else float(margin)
    st_draw = stable_draws(sites, n) if sites.get('key') is not None else None      # STABLE ROOTS (else None)
    S = float(np.sqrt(skin_area))
    S_ref = float(np.sqrt(G['A_ref']))
    k_size = (S / S_ref) ** gamma * size_scale
    eligible = float((w * mult * mask).sum() / skin_area)
    n_target = G['N'] * (S / S_ref) ** (2.0 * (1.0 - gamma)) * min(eligible, 1.0) * count_scale
    mu, sig = lognormal_q(*G['size'])
    mu = mu + np.log(k_size)
    sides = 4 if G['shape'] == 'hopper' else 6
    r_min = max(4.0 * voxel, 6.0 * texel) / (np.sin(np.pi / sides) * 2.0) if G['shape'] != 'ball' else \
        max(3.0 * voxel, 4.0 * texel)
    # the dorsal target: the reference's bias over this creature's WHOLE-skin dorsal share (R11 measured the feet against
    # the whole skin; a mask that already removes the underside must not get the bias a second time: the first octopus
    # run, biased over its masked share, put 95 % of the feet dorsal = 3.2x). Pass the masked-out candidates with
    # mask 0, so this share sees them
    wm = w * mult * mask
    wa = w * mult
    skin_d = float(wa[Nn[:, 1] > 0.5].sum() / max(wa.sum(), 1e-300))
    b_ref = G['dorsal'] / G['skin_dorsal'] if bias is None else bias
    target = min(b_ref * skin_d, 0.97)
    if st_draw is None:
        cr_field = crust_field(P, S, np.random.default_rng(rng.integers(1 << 31))) if crust > 0 else np.ones(n)
    else:
        # (the stable path's crust: its waves from the sites' own seed, never the creature's rng)
        c_seed = int(sites.get('crust_seed', int(stable_hash(int(st_draw['seed'].min()), 0, 0, 14))))
        cr_field = crust_field(P, float(sites.get('crust_S', S)), np.random.default_rng(c_seed)) if crust > 0 else \
            np.ones(n)
    dens = (1.0 - crust) + crust * cr_field
    # the feet's dorsal share moves in steps of mult / n_target (an octopus arm piece stands for 8 of ~78: one unlucky
    # draw is 0.10), so each round is a fresh draw: keep the CLOSEST, and move the goal by a damped step (test_growth_cpu
    # run 1: the old goal x target / got jumped to 0.99 and the LAST round was kept: ice shards 1.30x for 2.57x)
    goal = target
    best, best_err, best_beta = None, np.inf, 0.0
    for it in range(6):
        beta = solve_beta(Nn[:, 1], wm * dens, goal)
        W = wm * dens * np.exp(beta * (Nn[:, 1] - Nn[:, 1].max()))
        res = _select(P, Nn, W, mult, loc, n_target, mu, sig, G, rng, r_min, k_local, spacing, settle, sdf, ground,
                      margin, rots, arm, seen, loc0, stable=st_draw)
        got = res['dorsal']
        if abs(got - target) < best_err:
            best, best_err, best_beta = res, abs(got - target), beta
        if got <= 0 or abs(got - target) < 0.02:
            break
        goal = float(np.clip(goal + 0.7 * (target - got), 0.02, 0.97))
    res, beta = best, best_beta
    cr = res['crystals']
    out = {}
    for k, shp in (('kind', ()), ('a', (3,)), ('b', (3,)), ('R', ()), ('h', ()), ('spin', ()), ('root', (3,)),
                   ('n', (3,)), ('zskin', ()), ('vis', ())):
        out[k] = np.asarray([c[k] for c in cr], np.float64).reshape((len(cr),) + shp)
    out['kind'] = out['kind'].astype(np.int32)
    out['carve'] = np.asarray([bool(c.get('carve', False)) for c in cr], bool)
    out['piece'] = np.asarray([c['piece'] for c in cr], np.int64)
    out['fam'] = np.full(len(cr), fam, np.int32)
    if st_draw is None:
        out['rnd'] = rng.random(len(cr))
    else:
        # each crystal entry's random from its piece's site and its index in the piece (the material's facet seeds)
        site = np.asarray([res['pieces'][c['piece']]['site'] for c in cr], np.int64)
        idx = np.zeros(len(cr), np.int64)
        for k in range(1, len(cr)):
            idx[k] = idx[k - 1] + 1 if cr[k]['piece'] == cr[k - 1]['piece'] else 0
        h = stable_hash(st_draw['seed'][site], st_draw['key'][site], st_draw['slot'][site], 0) if len(cr) else \
            np.zeros(0, np.uint64)
        h = stable_hash(h, idx, 0, 15) if len(cr) else h
        out['rnd'] = (h >> np.uint64(8)).astype(np.float64) / 16777216.0
    out['pieces'] = res['pieces']
    out['report'] = dict(preset=preset, family=family, fam=fam, S=S, k_size=k_size, n_target=n_target,
                         pieces=float(sum(pc['mult'] for pc in res['pieces'])), crystals=len(cr),
                         skin_dorsal=skin_d, target_dorsal=target, dorsal=res['dorsal'], beta=beta, r_min=r_min,
                         eligible=eligible, floored=res['floored'], fit=res['stats'], margin=margin,
                         r_part=G.get('r_part', np.inf))
    if st_draw is not None:
        out['report']['stable'] = True                    # (the default path's report keeps its keys)
    log(f'[growth] {family}/{preset}: {out["report"]["pieces"]:.0f} pieces (target {n_target:.0f}), '
        f'{len(cr)} crystals, sizes x{k_size:.4f}, dorsal feet {res["dorsal"]:.2f} (target {target:.2f} = '
        f'{b_ref:.2f} x {skin_d:.2f}), floor R {r_min*1000:.2f} mm ({res["floored"]} floored)')
    st = res['stats']
    st['measured'] = int(seen.sum())                                 # (over every round: seen and loc keep them)
    thin = seen & np.isfinite(loc0) & (loc < loc0)
    st['thin'] = int(thin.sum())
    pc_thin = [pc for pc in res['pieces'] if thin[pc['site']]]
    st['thin_pieces'] = len(pc_thin)
    st['thin_R_max'] = float(max((max(c['R'] for c in cr if c['piece'] == k) for k, pc in enumerate(res['pieces'])
                                  if thin[pc['site']]), default=0.0))
    log(f'[growth]   every crystal on its own normal, inside the body, sized by its part (r_part '
        f'{G.get("r_part", np.inf):.2f}, margin {margin*1000:.2f} mm{"" if sdf is not None else ", no body given"}'
        f'{"" if ground is None else f", ground y {ground:.3f}"}): re-aimed {st["turned"]}, dominants capped by the '
        f'part {st["capped"]}, shrunk to fit {st["shrunk"]}, satellites dropped {st["dropped"]}, pieces dropped '
        f'{st["pieces_dropped"]}; half-thickness measured under {st["measured"]} sites')
    log(f'[growth]   the part radius = min(arm radius, half-thickness): {st["thin"]} arm sites thinner than their arm '
        f'(webs, the crown), {st["thin_skipped"]} of them too thin for a crystal above the floor (skipped); '
        f'{st["thin_pieces"]} pieces stand on one (largest crystal R {st["thin_R_max"]*1000:.2f} mm)')
    return out


def _select(P, Nn, W, mult, loc, n_target, mu, sig, G, rng, r_min, k_local, spacing, settle, sdf=None, ground=None,
            margin=0.0, rots=None, arm=None, seen=None, loc0=None, stable=None):
    # stable (STABLE ROOTS: stable_draws): the race's variates and each site's generator seed; None: the creature's rng
    order = np.argsort(rng.exponential(size=len(W)) / np.maximum(W, 1e-300)) if stable is None else \
        np.argsort(stable['E'] / np.maximum(W, 1e-300), kind='stable')
    acc_p, acc_r, pieces, crystals = [], [], [], []
    total = 0.0
    floored = 0
    tried = 0
    st = dict(turned=0, capped=0, shrunk=0, dropped=0, pieces_dropped=0, measured=0, thin_skipped=0)
    r_part = G.get('r_part', np.inf)
    seen = np.zeros(len(W), bool) if seen is None else seen
    loc0 = loc.copy() if loc0 is None else loc0
    too_thin = lambda r: k_local * 2.0 * r < 2.5 * r_min * 2.0 or r_part * r < r_min
    for i in order:
        if W[i] <= 0.0 or total >= n_target - 0.5:
            break
        tried += 1
        if tried > 50 * max(n_target, 1) + 1000:
            break
        ri = rng if stable is None else np.random.default_rng(int(stable['seeds'][i]))     # (the site's own stream)
        s_t = float(np.exp(ri.normal(mu, sig)))
        if sdf is not None and not seen[i]:
            # the part under it, at EVERY site: the body's half-thickness by a chord along -n; an arm site keeps the
            # smaller of it and its tube's radius (the crown's arm sites stand on the 2.5 mm webs, where the arm radius,
            # 24 mm, still allowed R 11 mm); measured once, kept for later rounds
            loc[i] = min(loc[i], half_thickness(sdf, P[i:i + 1], Nn[i:i + 1])[0])
            seen[i] = True
            st['measured'] += 1
        if np.isfinite(loc[i]):
            s_t = min(s_t, k_local * 2.0 * loc[i])
            if too_thin(loc[i]):
                if np.isfinite(loc0[i]) and not too_thin(loc0[i]):
                    st['thin_skipped'] += 1               # an arm site the half-thickness now rules out
                continue                                  # the part is too thin to carry a crystal above the floor
        cl = make_cluster(P[i], Nn[i], s_t, G, ri, r_min, loc[i], settle, sdf, ground, margin, st,
                          rots if (arm is not None and arm[i]) else None)
        if not cl:
            continue                                      # its dominant cannot stand here
        rho = cluster_reach(cl, P[i], Nn[i])
        if acc_p:
            d = np.linalg.norm(np.asarray(acc_p) - P[i], axis=1)
            if np.any(d < (np.asarray(acc_r) + rho) * spacing):
                continue
        pid = len(pieces)
        floored += int(any(abs(c['R'] - r_min) < 1e-12 for c in cl))
        for c in cl:
            c['piece'] = pid
            crystals.append(c)
        acc_p.append(P[i])
        acc_r.append(rho)
        pieces.append(dict(root=P[i], n=Nn[i], s=s_t, mult=mult[i], rho=rho, site=int(i)))
        total += mult[i]
    m = np.asarray([pc['mult'] for pc in pieces]) if pieces else np.zeros(0)
    up = np.asarray([pc['n'][1] > 0.5 for pc in pieces]) if pieces else np.zeros(0, bool)
    dors = float((m * up).sum() / max(m.sum(), 1e-300))
    return dict(crystals=crystals, pieces=pieces, dorsal=dors, floored=floored, stats=st)


def replicate(cr, rots, which):
    """copies of the crystals `which` (bool) under each rotation (3 x 3) after the first (the identity's copy is the
    original): positions and normals rotated, spins re-derived so each copy is the exact rotated crystal; returns the
    concatenated arrays and stack_of (each crystal's original index: the growths mesh stacks the copies' UVs)"""
    idx = np.nonzero(which)[0]
    out = {k: [v] for k, v in cr.items() if isinstance(v, np.ndarray) and len(v) == len(cr['a'])}
    stack = [np.arange(len(cr['a']))]
    n0, u0, v0, L0 = prism_frame(cr['a'][idx], cr['b'][idx], cr['spin'][idx])
    pmax = cr['piece'].max() + 1 if len(cr['piece']) else 0
    for j, Rm in enumerate(rots[1:], 1):
        a = cr['a'][idx] @ Rm.T
        b = cr['b'][idx] @ Rm.T
        nn = (b - a) / np.linalg.norm(b - a, axis=1, keepdims=True)
        spin = spin_for(nn, u0 @ Rm.T)
        cp = {k: v[0][idx].copy() for k, v in out.items()}
        cp['a'], cp['b'], cp['spin'] = a, b, spin
        cp['root'] = cr['root'][idx] @ Rm.T
        cp['n'] = cr['n'][idx] @ Rm.T
        cp['piece'] = cr['piece'][idx] + j * pmax
        for k in out:
            out[k].append(cp[k])
        stack.append(idx)
    res = dict(cr)
    for k, v in out.items():
        res[k] = np.concatenate(v)
    res['stack_of'] = np.concatenate(stack)
    return res


# ----------------------------------------------------------------------------------------------------- the plan
def emit(plan, cr, tag='growth', fillet=None):
    """the crystals as stroke batches: one 'add' batch per (family, kind) carrying the family's material id and the
    spins in rc, then the carves (bismuth's pits: no id, MAT_KEEP). Root fillet = the preset's fraction of the median
    radius (crisp crystals 0.12-0.2 R: a slight weld into the flesh, "details blend into the forms"); rb = h (a
    prism's tip, a cone's tip radius, a ball's own radius). Needs the material-ids Plan (Plan.add(..., mat=, rc=))"""
    if not len(cr['a']):
        return
    G = PLACEMENT.get(cr.get('report', {}).get('preset', ''), {})
    fr = G.get('fillet', 0.15) if fillet is None else fillet
    carve = cr.get('carve', np.zeros(len(cr['a']), bool))
    for mode in ('add', 'carve'):
        for fam in np.unique(cr['fam']):
            for kind in np.unique(cr['kind']):
                s = (cr['fam'] == fam) & (cr['kind'] == kind) & (carve == (mode == 'carve'))
                if not s.any():
                    continue
                k = float(np.median(fr * cr['R'][s])) if mode == 'add' else float(np.median(0.05 * cr['R'][s]))
                plan.add(int(kind), cr['a'][s], cr['b'][s], cr['R'][s], cr['h'][s], mode, k,
                         f'{tag} {FAMILIES[int(fam) - 1]}{" pit" if mode == "carve" else ""}',
                         mat=int(fam) if mode == 'add' else MAT_KEEP, rc=cr['spin'][s])


def prism_spheres(A, B, R, h, spin, sides, band, k=0.0):
    """the grid's extra activation for prism strokes (octopus_sculpt.Plan.bounds): thin crystals (R <= 2 band) get
    spheres along the AXIS that cover radius R + band + 2k (centres every r_c, radius 1.118 r_c); thick ones spheres on
    the WALL (faces sampled every band, radius band / sqrt 2 + band + 2k), never one sphere round the whole crystal
    (the eye cone's lesson: one sphere woke 26M voxels)"""
    A = np.atleast_2d(A)
    B = np.atleast_2d(B)
    R = np.broadcast_to(np.asarray(R, np.float64), (len(A),))
    h = np.broadcast_to(np.asarray(h, np.float64), (len(A),))
    spin = np.broadcast_to(np.asarray(spin, np.float64), (len(A),))
    sides = np.broadcast_to(np.asarray(sides, np.int64), (len(A),))
    C, Rs = [], []
    for i in range(len(A)):
        L = float(np.linalg.norm(B[i] - A[i]))
        rc = R[i] + band + 2.0 * k
        if R[i] <= 2.0 * band:
            m = max(2, int(np.ceil(L / rc)) + 1)
            t = np.linspace(0.0, 1.0, m)
            C.append(A[i][None] + t[:, None] * (B[i] - A[i])[None])
            Rs.append(np.full(m, 1.118 * rc))
        else:
            pts = prism_surface_points(A[i], B[i], R[i], h[i], spin[i], int(sides[i]), band)
            C.append(pts)
            Rs.append(np.full(len(pts), band / np.sqrt(2.0) + band + 2.0 * k))
    if not C:
        return np.zeros((0, 3)), np.zeros(0)
    return np.concatenate(C), np.concatenate(Rs)


def prism_vertices(a, b, R, h, spin, sides):
    """(base ring (N, 3), shoulder ring (N, 3), apex (3,)) of one prism: the ring's vertex i sits at angle
    (i + 0.5) sector from prism_frame's u (facet i spans vertices i - 1 .. i, its normal at angle i sector)"""
    n, u, v, L = prism_frame(a, b, spin)
    n, u, v, L = n[0], u[0], v[0], float(L[0])
    hh = float(np.clip(h, 0.0, L))
    sector = 2.0 * np.pi / sides
    ang = (np.arange(sides) + 0.5) * sector
    ring = R * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
    a = np.asarray(a, np.float64)
    return a + ring, a + n * (L - hh) + ring, a + n * L


def prism_surface_points(a, b, R, h, spin, sides, spacing):
    """points on the prism's lateral and tip faces, about `spacing` apart"""
    base, sh, apex = prism_vertices(a, b, R, h, spin, sides)
    out = []
    for i in range(sides):
        p0, p1 = base[i - 1], base[i]
        q0, q1 = sh[i - 1], sh[i]
        nu = max(2, int(np.ceil(np.linalg.norm(p1 - p0) / spacing)) + 1)
        nv = max(2, int(np.ceil(np.linalg.norm(q0 - p0) / spacing)) + 1)
        s, t = np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv), indexing='ij')
        s, t = s.ravel()[:, None], t.ravel()[:, None]
        out.append((1 - t) * ((1 - s) * p0 + s * p1) + t * ((1 - s) * q0 + s * q1))
        nt = max(2, int(np.ceil(np.linalg.norm(apex - 0.5 * (q0 + q1)) / spacing)) + 1)
        for tt in np.linspace(0, 1, nt):
            e0, e1_ = q0 + tt * (apex - q0), q1 + tt * (apex - q1)
            m = max(1, int(np.ceil(np.linalg.norm(e1_ - e0) / spacing)) + 1)
            out.append(e0[None] + np.linspace(0, 1, m)[:, None] * (e1_ - e0)[None])
    return np.concatenate(out)


def instances(cr):
    """the material pass's instance arrays (plan.inst['growths']; t10 saves them as growths_* in instances.npz):
    a/b (n, 3) base and apex, q (n, 4) = (R, h, spin, sides; 0 = not a prism), z (n, 4) = (zskin, rnd, piece, fam),
    root and n (the skin point and normal the crystal grows from), stack_of (the original of a replicated copy)"""
    keep = ~np.asarray(cr.get('carve', np.zeros(len(cr['a']), bool)), bool)
    if not keep.any():
        return empty_instances()
    sides = np.asarray([SIDES.get(int(k), 0) for k in cr['kind']], np.float64)
    stack = np.asarray(cr.get('stack_of', np.arange(len(cr['a']))))
    remap = -np.ones(len(cr['a']), np.int64)
    remap[keep] = np.arange(keep.sum())
    return dict(a=np.asarray(cr['a'])[keep], b=np.asarray(cr['b'])[keep],
                q=np.column_stack([cr['R'], cr['h'], cr['spin'], sides])[keep],
                z=np.column_stack([cr['zskin'], cr['rnd'], cr['piece'], cr['fam']]).astype(np.float64)[keep],
                root=np.asarray(cr['root'])[keep], n=np.asarray(cr['n'])[keep], stack_of=remap[stack[keep]])


def inside_any(pts, inst, pad=0.0):
    """True where a point lies inside a growth prism (+ pad): the skin bake's texels HIDDEN under a growth (the growths
    mesh covers them; bake.bake(exclude=...) keeps them out of the miss bar)"""
    from scipy.spatial import cKDTree
    pts = np.asarray(pts, np.float64).reshape(-1, 3)
    out = np.zeros(len(pts), bool)
    q = inst['q']
    pr = q[:, 3] > 0
    if not pr.any() or not len(pts):
        return out
    A, B = inst['a'][pr], inst['b'][pr]
    R, h, sp, sd = q[pr, 0], q[pr, 1], q[pr, 2], q[pr, 3].astype(int)
    mid = 0.5 * (A + B)
    rad = 0.5 * np.linalg.norm(B - A, axis=1) + R + pad
    tree = cKDTree(pts)
    for i in range(len(A)):
        idx = tree.query_ball_point(mid[i], rad[i])
        if idx:
            idx = np.asarray(idx)
            d = sd_prism_np(pts[idx], A[i], B[i], R[i], h[i], sp[i], sd[i])
            out[idx[d < pad]] = True
    return out


# ----------------------------------------------------------------------------------------------------- the low mesh
def _clip_poly(P, U, hv, cut):
    """the part of a convex polygon (vertices P (k, 3), their UVs U (k, 2), their heights hv (k,)) at or above the
    height cut (Sutherland-Hodgman against one plane; the UVs follow, exact for an affine development); None when
    nothing is left. Unclipped polygons come back as they were (the same vertex order)"""
    keep = hv >= cut
    if keep.all():
        return P, U
    if not keep.any():
        return None
    oP, oU = [], []
    k = len(P)
    for j in range(k):
        a, b = j, (j + 1) % k
        if keep[a]:
            oP.append(P[a])
            oU.append(U[a])
        if keep[a] != keep[b]:
            t = (cut - hv[a]) / (hv[b] - hv[a])
            oP.append(P[a] + t * (P[b] - P[a]))
            oU.append(U[a] + t * (U[b] - U[a]))
    return (np.asarray(oP), np.asarray(oU)) if len(oP) >= 3 else None


def low_mesh(cr, px_per_m, gutter_px=4, size=None, stack_of=None, trim=True):
    """the GROWTHS MESH: every prism crystal exactly (its facets ARE the shape; the bake adds the root fillets, the edge
    bevels and the AO), hard-edged (vertices split per face), one UV island per crystal: its faces unrolled in a strip
    (side quads, their tip triangles standing on them: an isometric development, zero distortion), islands shelf-packed
    at ONE texel density (px_per_m; size forces the atlas side and scales the density down to fit). Crystals with
    stack_of[i] != i reuse their original's island (rotated copies).
    TRIMMED (trim and cr['cut'], trim_planes): each prism's faces are cut by planes normal to its root's skin normal n
    at the heights cut[i, face] (or cut[i] for every face) along n from the root: what lies under them goes, a face a
    plane crosses is clipped (fan-triangulated, its UVs following), the section is left open (it lies inside the skin),
    and the island is packed from its kept part only, so the atlas holds what can show. A copy shares its original's
    cuts and island. Returns dict(V, F, UV (forge convention, v up), N (flat), face_crystal, px_per_m, size, fill: the
    share of the atlas the unique islands' triangles cover)"""
    carve = np.asarray(cr.get('carve', np.zeros(len(cr['a']), bool)), bool)
    idx = np.nonzero((np.asarray([SIDES.get(int(k), 0) for k in cr['kind']]) > 0) & ~carve)[0]
    stack_of = np.arange(len(cr['a'])) if stack_of is None else np.asarray(stack_of)
    cut = np.asarray(cr['cut'], np.float64) if trim and cr.get('cut') is not None else None
    V, F, UVl, Nf, fc = [], [], [], [], []
    isl = {}
    for i in idx:
        sides = SIDES[int(cr['kind'][i])]
        base, sh, apex = prism_vertices(cr['a'][i], cr['b'][i], cr['R'][i], cr['h'][i], cr['spin'][i], sides)
        e = np.linalg.norm(base[0] - base[-1])
        zs = np.linalg.norm(sh[0] - base[0])
        slant = np.linalg.norm(apex - 0.5 * (sh[0] + sh[-1]))
        polys = []
        for f in range(sides):
            p0, p1, q0, q1 = base[f - 1], base[f], sh[f - 1], sh[f]
            x0 = f * e
            fn = np.cross(p1 - p0, q0 - p0)
            fn /= np.linalg.norm(fn)
            polys.append((np.asarray([p0, p1, q1, q0]),
                          np.asarray([(x0, 0.0), (x0 + e, 0.0), (x0 + e, zs), (x0, zs)]), fn))
            tn = np.cross(q1 - q0, apex - q0)
            ln = np.linalg.norm(tn)
            tn = tn / ln if ln > 1e-20 else fn
            polys.append((np.asarray([q0, q1, apex]), np.asarray([(x0, zs), (x0 + e, zs), (x0 + 0.5 * e, zs + slant)]),
                          tn))
        clipped = False
        cut_i = None if cut is None else (cut[i] if cut.ndim == 2 else np.full(len(polys), cut[i]))
        if cut_i is not None and np.any(cut_i[:len(polys)] > -np.inf):     # (+inf: that face does not show)
            kept = []
            for j, (P_, U_, n_) in enumerate(polys):
                c_ = _clip_poly(P_, U_, (P_ - cr['root'][i]) @ cr['n'][i], cut_i[j])
                if c_ is None or len(c_[0]) != len(P_) or not np.array_equal(c_[0], P_):
                    clipped = True
                if c_ is not None:
                    kept.append((c_[0], c_[1], n_))
            polys = kept
        if not polys:
            continue                                  # nothing of it shows: no faces, no island
        verts, uvs, tris, nrm = [], [], [], []
        for P_, U_, n_ in polys:
            o = len(verts)
            verts += list(P_)
            uvs += list(U_)
            tris += [(o, o + j, o + j + 1) for j in range(1, len(P_) - 1)]
            nrm += [n_] * len(P_)
        uvs = np.asarray(uvs)
        if clipped:                                    # (the island packed from its kept part: shifted to 0, 0)
            lo_uv = uvs.min(0)
            isl[i] = (uvs, float(uvs[:, 0].max() - lo_uv[0]), float(uvs[:, 1].max() - lo_uv[1]), lo_uv)
        else:
            isl[i] = (uvs, sides * e, zs + slant, np.zeros(2))
        V.append(np.asarray(verts))
        F.append(np.asarray(tris))
        UVl.append(i)
        Nf.append(np.asarray(nrm))
        fc.append(np.full(len(tris), i))
    if not V:
        return dict(V=np.zeros((0, 3)), F=np.zeros((0, 3), np.int64), UV=np.zeros((0, 2)), N=np.zeros((0, 3)),
                    face_crystal=np.zeros(0, np.int64), px_per_m=px_per_m, size=0, fill=0.0)
    # shelf packing of the unique islands (metres -> pixels at px_per_m), tallest first (a trimmed crystal none of
    # whose faces shows has no island)
    uniq = [i for i in idx if i in isl and (stack_of[i] == i or stack_of[i] not in isl)]
    g = gutter_px

    def pack(scale, side):
        W_px = [isl[i][1] * px_per_m * scale + 2 * g for i in uniq]
        H_px = [isl[i][2] * px_per_m * scale + 2 * g for i in uniq]
        order = np.argsort(-np.asarray(H_px))
        pos = {}
        x = y = row_h = 0.0
        for o in order:
            if x + W_px[o] > side:
                x, y, row_h = 0.0, y + row_h, 0.0
            pos[uniq[o]] = (x + g, y + g)
            x += W_px[o]
            row_h = max(row_h, H_px[o])
        return pos, y + row_h
    scale = 1.0
    area = float(sum((isl[i][1] * px_per_m + 2 * g) * (isl[i][2] * px_per_m + 2 * g) for i in uniq))
    if cut is None:
        side = size or int(2 ** np.ceil(np.log2(max(64.0, np.sqrt(area / 0.72)))))
    else:
        # trimmed: the smallest side the shelf packer fills (from the islands' own area up, never under the widest or
        # tallest island), so what the trim frees shrinks the atlas instead of the 72 % guess holding it
        big = max(max(isl[i][1], isl[i][2]) * px_per_m + 2 * g for i in uniq)
        side = size or int(2 ** np.ceil(np.log2(max(64.0, np.sqrt(area), big))))
    pos, used = pack(scale, side)
    while used > side:
        if size is None:
            side *= 2
        else:
            scale *= 0.97
        pos, used = pack(scale, side)
    UV = []
    fill = 0.0
    for k, i in enumerate(UVl):
        src = i if i in pos else stack_of[i]
        ox, oy = pos[src]
        uv = (isl[i][0] - isl[src][3]) * px_per_m * scale + np.array([ox, oy])    # (a copy: its original's shift)
        UV.append(uv / side)
        if src == i:
            t = UV[-1][F[k]]
            fill += 0.5 * float(np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) -
                                       (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1])).sum())
    offs = np.cumsum([0] + [len(v) for v in V[:-1]])
    return dict(V=np.concatenate(V), F=np.concatenate([f + o for f, o in zip(F, offs)]), UV=np.concatenate(UV),
                N=np.concatenate(Nf), face_crystal=np.concatenate(fc), px_per_m=px_per_m * scale, size=side,
                fill=fill)


def _surface_samples(a, b, q, spacing):
    """points on one instance's surface (q = (R, h, spin, sides)): a prism's faces and vertices; a ball's or a round
    cone's end spheres along the six axes"""
    if q[3] > 0.5:
        base, sh, apex = prism_vertices(a, b, q[0], q[1], q[2], int(q[3]))
        return np.vstack([prism_surface_points(a, b, q[0], q[1], q[2], int(q[3]), spacing), base, sh, apex[None]])
    d = np.vstack([np.eye(3), -np.eye(3)])
    return np.vstack([a + d * q[0], b + d * (q[0] if np.linalg.norm(b - a) < 1e-12 else q[1])])


def _face_samples(base, sh, apex, f, quad, spacing):
    """points on face f of a prism (prism_vertices' rings): its side quad (quad True) or its tip triangle, about
    `spacing` apart, their edges and corners included"""
    p0, p1, q0, q1 = base[f - 1], base[f], sh[f - 1], sh[f]
    if quad:
        nu = max(2, int(np.ceil(np.linalg.norm(p1 - p0) / spacing)) + 1)
        nv = max(2, int(np.ceil(np.linalg.norm(q0 - p0) / spacing)) + 1)
        s, t = np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv), indexing='ij')
        s, t = s.ravel()[:, None], t.ravel()[:, None]
        return (1 - t) * ((1 - s) * p0 + s * p1) + t * ((1 - s) * q0 + s * q1)
    m = max(2, int(np.ceil(max(np.linalg.norm(q1 - q0), np.linalg.norm(apex - q0)) / spacing)) + 1)
    i, j = np.meshgrid(np.arange(m), np.arange(m), indexing='ij')
    ok = i + j <= m - 1
    a, b = (i[ok] / (m - 1))[:, None], (j[ok] / (m - 1))[:, None]
    return q0 + a * (q1 - q0) + b * (apex - q0)


@wp.kernel
def k_outside(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.int32)):
    i = wp.tid()
    q = wp.mesh_query_point_sign_winding_number(mesh, pts[i], 10.0)
    out[i] = 0
    if not q.result or q.sign >= 0.0:
        out[i] = 1


def outside_mesh(pts, V, F, chunk=4_000_000):
    """True where points lie OUTSIDE the triangle mesh (V, F), by its winding number (Warp: robust where the mesh has
    small openings, the octopus low's eye sockets and mouth)"""
    pts = np.asarray(pts, np.float32).reshape(-1, 3)
    out = np.zeros(len(pts), bool)
    if not len(pts):
        return out
    mesh = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3),
                   indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32), support_winding_number=True)
    for s in range(0, len(pts), chunk):
        p = wp.array(pts[s:s + chunk], dtype=wp.vec3)
        o = wp.zeros(len(p), dtype=wp.int32)
        wp.launch(k_outside, dim=len(p), inputs=[mesh.id, p, o])
        out[s:s + chunk] = o.numpy() > 0
    return out


def _trim_samples(cr, voxel):
    """the trim's face samples: per prism crystal and FACE (side quad f at column 2f, tip triangle f at 2f + 1), points
    step = clip(R / 4, voxel, 4 voxels) apart. Returns (the prism crystals, step, points, their crystal, their face)"""
    n_c = len(cr['a'])
    carve = np.asarray(cr.get('carve', np.zeros(n_c, bool)), bool)
    kinds = np.asarray(cr['kind'])
    pr = np.nonzero(np.isin(kinds, list(SIDES)) & ~carve)[0]
    step = np.clip(0.25 * cr['R'], voxel, 4.0 * voxel)
    pts, own, face = [np.zeros((0, 3))], [np.zeros(0, np.int64)], [np.zeros(0, np.int64)]
    for i in pr:
        sides = SIDES[int(kinds[i])]
        base, sh, apex = prism_vertices(cr['a'][i], cr['b'][i], cr['R'][i], cr['h'][i], cr['spin'][i], sides)
        for j in range(2 * sides):
            p_ = _face_samples(base, sh, apex, j // 2, j % 2 == 0, step[i])
            pts.append(p_)
            own.append(np.full(len(p_), i))
            face.append(np.full(len(p_), j))
    return pr, step, np.vstack(pts), np.concatenate(own), np.concatenate(face)


def trim_planes(cr, sdf, voxel, margin_vox=3.0, chunk=2_000_000, skin_low=None):
    """THE CUT of the trimmed growths low (low_mesh): per prism crystal and per FACE (side quad f at column 2f, tip
    triangle f at 2f + 1) a plane normal to the crystal's root normal n, at the height (m, along n from the root) of
    the lowest point of that face that shows (outside the block-out: sdf > 0, or outside the skin LOW: skin_low =
    (V, F), the cage the runtime draws, whose flat faces cut chords inside convex skin, so a point within the block-out
    can show there; counting the block-out alone left slits between a crystal and the low: growth_look.md) minus a
    margin that still welds under the fillet (the larger of margin_vox voxels and the fillet emit gives its batch) and
    minus the sampling step. Normal to n, not to the axis: a crystal leaning by tilt shows its back face from R
    tan(tilt) below zskin, so a cut across the axis at zskin minus a margin would open the mesh there. Per face: on a
    convex arm the far faces show lower down the curving skin than the faces at the root, so one plane per crystal kept
    a buried band round the root. A face with no point that shows: dropped when every sample lies deeper than the
    margin and the step, else cut at its crystal's lowest. A stack (an original and its rotated copies) shares the
    lowest cut of its members face by face (the webs differ between the arms), so every copy stays its original's exact
    rotated twin and keeps stacking on its island. Returns (n, 12) heights: -inf keeps everything (carves, balls,
    cones), +inf drops a face"""
    n_c = len(cr['a'])
    NF = 2 * max(SIDES.values())
    cut = np.full((n_c, NF), -np.inf)
    carve = np.asarray(cr.get('carve', np.zeros(n_c, bool)), bool)
    kinds = np.asarray(cr['kind'])
    pr = np.nonzero(np.isin(kinds, list(SIDES)) & ~carve)[0]
    if not len(pr):
        return cut
    G = PLACEMENT.get(cr.get('report', {}).get('preset', ''), {})
    fr = G.get('fillet', 0.15)
    k_fil = np.zeros(n_c)
    for fam in np.unique(cr['fam']):
        for kind in np.unique(kinds):
            s = (cr['fam'] == fam) & (kinds == kind) & ~carve
            if s.any():
                k_fil[s] = float(np.median(fr * cr['R'][s]))          # emit's fillet for that batch
    pr, step, pts, own, face = _trim_samples(cr, voxel)
    vals = np.concatenate([np.asarray(sdf(pts[s:s + chunk]), np.float64) for s in range(0, len(pts), chunk)])
    h = np.einsum('ij,ij->i', pts - cr['root'][own], cr['n'][own])
    vis = vals > 0.0
    if skin_low is not None:
        vis |= outside_mesh(pts, *skin_low)
    low = np.full((n_c, NF), np.inf)                   # each face's lowest showing point
    np.minimum.at(low, (own[vis], face[vis]), h[vis])
    top = np.full((n_c, NF), -np.inf)                  # each face's highest distance (all samples): deep = buried
    np.maximum.at(top, (own, face), vals)
    margin = np.maximum(margin_vox * voxel, k_fil) + step
    low_c = low.min(1)                                 # the crystal's lowest showing point
    fallback = np.where(np.isfinite(low_c), low_c, np.inf)[:, None] * np.ones((1, NF))
    deep = top < -margin[:, None]
    face_low = np.where(np.isfinite(low), low, np.where(deep, np.inf, fallback))
    stack = np.asarray(cr.get('stack_of', np.arange(n_c)))
    for o in np.unique(stack[pr]):
        grp = pr[stack[pr] == o]
        lo_g = face_low[grp].min(0)
        cut[grp] = np.where(np.isfinite(lo_g), lo_g - margin[grp].max(), np.inf)[None, :]
        nf = 2 * SIDES[int(kinds[grp[0]])]
        cut[grp, nf:] = -np.inf
    return cut


def trim_slits(cr, cut, sdf, voxel, skin_low=None, chunk=2_000_000):
    """THE TRIM'S CHECK: the face samples that SHOW (outside the block-out, or outside the skin low when it is given)
    yet lie under their face's cut (trim_planes' heights): each is a SLIT, the skin seen past the trimmed growths low's
    open edge. Returns dict(points, showing, by_low: those showing only outside the low, slits, slit_crystals)"""
    pr, step, pts, own, face = _trim_samples(cr, voxel)
    if not len(pts):
        return dict(points=0, showing=0, by_low=0, slits=0, slit_crystals=0)
    vals = np.concatenate([np.asarray(sdf(pts[s:s + chunk]), np.float64) for s in range(0, len(pts), chunk)])
    out_b = vals > 0.0
    out_l = outside_mesh(pts, *skin_low) if skin_low is not None else np.zeros(len(pts), bool)
    show = out_b | out_l
    h = np.einsum('ij,ij->i', pts - cr['root'][own], cr['n'][own])
    sl = show & (h < np.asarray(cut, np.float64)[own, face])
    return dict(points=int(len(pts)), showing=int(show.sum()), by_low=int((out_l & ~out_b).sum()), slits=int(sl.sum()),
                slit_crystals=int(len(np.unique(own[sl]))))


def _seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-30), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def keep_growths(keep, inst, sdf, lo, hi, voxel, band, log=print):
    """THE VOXEL GRID'S REGION round the growths (t10: voxel.SparseSDF(keep=)): keep(points) -> bool filters the coarse
    cells (64 voxels); this wraps it so every cell within reach of a crystal it cuts is kept too. A crystal is CUT when
    a sample of its visible part (its surface where the block-out's distance exceeds -band, and those samples moved a
    band along each axis) falls in a cell keep drops; within reach = its axis capsule grown by Plan.bounds' prism
    spheres (1.2 x (R + fillet + band)), the grid's activation pad (1.5 mm), a cell's half diagonal and a voxel.
    Crystals keep holds already add nothing (the grid round them is unchanged), and neither do rotated copies whose root
    keep drops (the other arms past the webs: the stacked arms set and the growths atlas bake from the originals).
    Asserts that no crystal's visible part leaves the grid's box [lo, hi]. Returns (keep2, report dict)"""
    lo = np.asarray(lo, np.float64)
    hi = np.asarray(hi, np.float64)
    C = 64.0 * voxel
    A, B, q = np.asarray(inst['a'], np.float64), np.asarray(inst['b'], np.float64), np.asarray(inst['q'], np.float64)
    n = len(A)
    if n == 1 and np.array_equal(A, empty_instances()['a']):
        n = 0                       # (instances() of a plan without crystals: the kernels' one far-away dummy)
    if not n:
        log('[growth] grid region: no crystals; keep unchanged')
        return keep, dict(crystals=0, cut=0, wrapped=0, cut_copies_left=0, cells=0, cells_added=0, outside_box=0)
    stack = np.asarray(inst.get('stack_of', np.arange(n)))
    held_root = np.asarray(keep(np.asarray(inst['root'], np.float64)), bool)
    pts, own = [], []
    for i in range(n):
        p_ = _surface_samples(A[i], B[i], q[i], float(np.clip(0.5 * q[i, 0], voxel, 0.25 * C)))
        pts.append(p_)
        own.append(np.full(len(p_), i))
    pts, own = np.vstack(pts), np.concatenate(own)
    vis = np.asarray(sdf(pts), np.float64) > -band
    pv, ov = pts[vis], own[vis]
    out_box = np.zeros(n, bool)
    np.logical_or.at(out_box, ov, np.any((pv < lo) | (pv > hi), axis=1))
    cut = np.zeros(n, bool)
    for dlt in [np.zeros(3)] + [s * band * e for e in np.eye(3) for s in (-1.0, 1.0)]:
        cells = lo + (np.floor((pv + dlt - lo) / C) + 0.5) * C
        np.logical_or.at(cut, ov, ~np.asarray(keep(cells), bool))
    need = np.nonzero(cut & ((stack == np.arange(n)) | held_root))[0]
    Rr = np.where(q[need, 3] > 0.5, q[need, 0], np.maximum(q[need, 0], q[need, 1]))
    reach = 1.2 * (2.2 * Rr + band) + 0.0015 + 0.8661 * C + voxel
    Aa, Bb = A[need], B[need]
    box_lo, box_hi = np.minimum(Aa, Bb) - reach[:, None], np.maximum(Aa, Bb) + reach[:, None]

    def keep2(points):
        points = np.asarray(points, np.float64)
        m = np.asarray(keep(points), bool).copy()
        for j in range(len(need)):
            sel = np.nonzero(~m & np.all((points >= box_lo[j]) & (points <= box_hi[j]), axis=1))[0]
            if len(sel):
                m[sel[_seg_dist(points[sel], Aa[j], Bb[j]) < reach[j]]] = True
        return m
    # the cells it adds over t10's box (the same coarse grid as SparseSDF)
    nC = np.ceil((hi - lo) / C).astype(int)
    g = np.stack(np.meshgrid(*[np.arange(k) for k in nC], indexing='ij'), -1).reshape(-1, 3)
    cc = lo + (g + 0.5) * C
    k0 = np.asarray(keep(cc), bool)
    added = int((keep2(cc) & ~k0).sum()) if len(need) else 0
    rep = dict(crystals=n, cut=int(cut.sum()), wrapped=int(len(need)), cut_copies_left=int(cut.sum() - len(need)),
               cells=int(k0.sum()), cells_added=added, outside_box=int(out_box.sum()))
    log(f'[growth] grid region: {n} crystals, {rep["cut"]} with a visible part in a cell keep drops ({len(need)} wrapped, '
        f'{rep["cut_copies_left"]} rotated copies past the webs left out); +{added} coarse cells on keep\'s '
        f'{rep["cells"]}; visible parts outside the box: {rep["outside_box"]}')
    assert not out_box.any(), f'growth crystals {np.nonzero(out_box)[0][:20].tolist()} reach outside the grid box ' \
                              f'{lo.tolist()}..{hi.tolist()}'
    return (keep2 if len(need) else keep), rep


# ----------------------------------------------------------------------------------------------------- measuring
def piece_points(cr, i):
    """points that measure crystal i the way the reference study measured its growth meshes (their vertices)"""
    k = int(cr['kind'][i])
    if k in SIDES:
        base, sh, apex = prism_vertices(cr['a'][i], cr['b'][i], cr['R'][i], cr['h'][i], cr['spin'][i], SIDES[k])
        return np.vstack([base, sh, apex[None]])
    # balls and cones: a few points on their end spheres
    d = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], np.float64)
    r_b = cr['R'][i] if k == STROKE_BALL else cr['h'][i]
    return np.vstack([cr['a'][i] + d * cr['R'][i], cr['b'][i] + d * r_b])


def report(cr, sd_body, skin_area, sites_n=None, sites_w=None, ref=None, log=print):
    """the R11 comparison: pieces, size and height percentiles (absolute and over S), the feet's dorsal / flank /
    ventral shares and bias, the growth-mesh area ratio, triangles per piece; sd_body(points) -> signed distance to
    the creature's skin (the block-out)"""
    G = PLACEMENT[cr['report']['preset']] if ref is None else ref
    pid = cr['piece']
    carve = np.asarray(cr.get('carve', np.zeros(len(pid), bool)), bool)
    S = np.sqrt(skin_area)
    sizes, heights, feet_y, gaps = [], [], [], []
    for p in np.unique(pid[~carve]):
        sel = np.nonzero((pid == p) & ~carve)[0]
        pts = np.vstack([piece_points(cr, i) for i in sel])
        dist = np.abs(sd_body(pts))
        sizes.append(np.linalg.norm(pts.max(0) - pts.min(0)))
        heights.append(dist.max())
        gaps.append(dist.min())
        feet_y.append(cr['n'][sel[0]][1])
    sizes, heights, feet_y = np.asarray(sizes), np.asarray(heights), np.asarray(feet_y)
    lm = low_mesh(cr, 1000.0, trim=False)             # (the reference's area counts the buried parts: untrimmed)
    tri = lm['V'][lm['F']]
    ta = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    Lc = np.linalg.norm(cr['b'] - cr['a'], axis=1)
    k0 = (cr['kind'] == STROKE_BALL) & ~carve
    balls = k0 & (Lc < 1e-12)
    cones = k0 & ~balls
    R1, R2 = cr['R'][cones], cr['h'][cones]
    area = ta.sum() + float((4.0 * np.pi * cr['R'][balls] ** 2).sum()) + float(
        (np.pi * (R1 + R2) * np.sqrt(Lc[cones] ** 2 + (R1 - R2) ** 2) + 2.0 * np.pi * (R1 ** 2 + R2 ** 2)).sum())
    q = lambda x, ps: np.percentile(x, ps) if len(x) else np.full(len(ps), np.nan)
    sk = None
    if sites_n is not None:
        w = np.ones(len(sites_n)) if sites_w is None else sites_w
        sk = float(w[sites_n[:, 1] > 0.5].sum() / w.sum())
    out = dict(pieces=len(sizes), crystals=len(cr['a']), size=q(sizes, (10, 50, 90)),
               height=q(heights, (10, 50, 90)), size_S=q(sizes, (10, 50, 90)) / S,
               height_S=q(heights, (10, 50, 90)) / S, dorsal=float((feet_y > 0.5).mean()) if len(feet_y) else 0.0,
               flank=float((np.abs(feet_y) <= 0.5).mean()) if len(feet_y) else 0.0,
               ventral=float((feet_y < -0.5).mean()) if len(feet_y) else 0.0, area_ratio=area / skin_area,
               tris_per_piece=len(lm['F']) / max(len(sizes), 1), skin_dorsal=sk, gap_p50=float(np.median(gaps)))
    S_ref = np.sqrt(G['A_ref'])
    ref_s = np.asarray(G['size']) / S_ref
    ref_h = np.asarray(G['height']) / S_ref
    log(f'[growth report] {cr["report"]["family"]}/{cr["report"]["preset"]} on S = {S:.3f} m: {out["pieces"]} pieces '
        f'(ref {G["N"]}), {out["crystals"]} crystals, {out["tris_per_piece"]:.0f} tris/piece (ref '
        f'{G["tris"] / G["N"]:.0f})')
    log('   size/S p10/50/90  ' + ' / '.join(f'{v:.4f}' for v in out['size_S']) + '   ref ' +
        ' / '.join(f'{v:.4f}' for v in ref_s) + f'   ({" / ".join(f"{v*1000:.1f}" for v in out["size"])} mm)')
    log('   height/S          ' + ' / '.join(f'{v:.4f}' for v in out['height_S']) + '   ref ' +
        ' / '.join(f'{v:.4f}' for v in ref_h) + f'   ({" / ".join(f"{v*1000:.1f}" for v in out["height"])} mm)')
    bias = out['dorsal'] / sk if sk else float('nan')
    log(f'   feet dorsal/flank/ventral {out["dorsal"]:.3f} / {out["flank"]:.3f} / {out["ventral"]:.3f}, skin dorsal '
        f'{sk if sk is not None else float("nan"):.3f}, bias {bias:.2f}x (ref {G["dorsal"] / G["skin_dorsal"]:.2f}x); '
        f'area ratio {out["area_ratio"]:.3f} (ref {G["area"]:.3f}); foot gap p50 {out["gap_p50"]*1000:.2f} mm')
    out['bias'] = bias
    return out


# ----------------------------------------------------------------------------------------------------- material pass
@wp.struct
class GrowthSurf:
    ok: int              # a growth crystal lies under the point
    c: int               # its index (the instance arrays)
    fam: int             # its family id
    facet: int           # face 0..N-1, tip faces N..2N-1
    x: float
    y: float
    z: float             # the wedge coordinates (prism_local)
    L: float
    zs: float
    A: float
    w0: float
    R: float
    sd: float            # the point's distance to that crystal (|sd| small on its surface)
    edge: float          # distance to the nearest facet edge (m)
    depth: float         # the crystal's thickness across at this height (m): 2 x the apothem there
    rnd: float           # the facet's random [0, 1)
    crnd: float          # the crystal's random [0, 1)
    zrel: float          # height above the skin line along the axis, in radii
    xs: float            # the signed coordinate across the face (x unfolded, along the facet's tangent; prisms only)
    seed: int            # the crystal's own seed (its random x 2^24: a rotated copy shares its original's)
    lp: wp.vec3          # the point in the crystal's own frame (u, v, axis from the base; p - a for balls and cones):
                         # patterns that turn with a rotated copy


@wp.func
def growth_surface(p: wp.vec3, grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3),
                   gQ: wp.array(dtype=wp.vec4), gZ: wp.array(dtype=wp.vec4)):
    """the growth piece whose surface is nearest p (a hash grid over the pieces' midpoints, query radius rq = the
    largest half length + radius) and p's coordinates on it. Prisms (q[3] = sides) give their facet, edge distance and
    wedge coordinates; balls and round cones (q[3] = 0: nodules, spikes, drips) one facet, no edges and the axis
    coordinate. ok = 0 (edge 1e9) when no piece lies within rq"""
    out = GrowthSurf()
    out.ok = 0
    out.edge = 1.0e9
    best = float(1.0e9)
    bi = int(-1)
    qy = wp.hash_grid_query(grid, p, rq)
    i = int(0)
    while wp.hash_grid_query_next(qy, i):
        q = gQ[i]
        d = float(0.0)
        if q[3] > 0.5:
            d = sd_prism(p, gA[i], gB[i], q[0], q[1], q[2], int(q[3]))
        else:
            d = S_.sd_roundcone(p, gA[i], gB[i], q[0], q[1])
        if wp.abs(d) < best:
            best = wp.abs(d)
            bi = i
    if bi < 0:
        return out
    q = gQ[bi]
    zz = gZ[bi]
    if q[3] < 0.5:
        # a ball or a round cone (voxel.STROKE_CONE: radii q[0] at a, q[1] at b)
        ax = gB[bi] - gA[bi]
        Lr = wp.length(ax)
        zr = float(0.0)
        if Lr > 1.0e-12:
            zr = wp.dot(p - gA[bi], ax / Lr)
        out.ok = 1
        out.c = bi
        out.fam = int(zz[3])
        out.facet = 0
        out.z = zr
        out.L = Lr
        out.zs = Lr
        out.A = q[0]
        out.R = q[0]
        out.sd = S_.sd_roundcone(p, gA[bi], gB[bi], q[0], q[1])
        out.edge = 1.0e9
        out.depth = 2.0 * q[0]
        out.seed = int(zz[1] * 16777216.0)
        out.rnd = proc.u01(proc.hash3i(out.seed, 0, 1, 977))
        out.crnd = zz[1]
        out.zrel = (zr - zz[0]) / wp.max(q[0], 1.0e-9)
        if Lr <= 1.0e-12:
            out.zrel = 1.0e9             # a ball has no axis to measure its height on: no root gradient (its skin
                                         # normal is not in the instance data)
        out.lp = p - gA[bi]
        return out
    sides = int(q[3])
    pl = prism_local(p, gA[bi], gB[bi], q[0], q[1], q[2], sides)
    out.ok = 1
    out.c = bi
    out.fam = int(zz[3])
    out.x = pl.x
    out.y = pl.y
    out.z = pl.z
    out.L = pl.L
    out.zs = pl.zs
    out.A = pl.A
    out.w0 = pl.w0
    out.R = q[0]
    out.sd = sd_prism(p, gA[bi], gB[bi], q[0], q[1], q[2], sides)
    # the face it lies on: the tip plane farther out than the prism face (both distances signed)
    tipd = (pl.h * pl.y + pl.A * (pl.z - pl.L)) / wp.sqrt(pl.h * pl.h + pl.A * pl.A)
    tip = int(0)
    if pl.h > 1.0e-9 and tipd > pl.y - pl.A:
        tip = 1
    if pl.h <= 1.0e-9 and pl.z - pl.L > pl.y - pl.A:
        tip = 1
    out.facet = pl.facet + tip * sides
    if tip == 0:
        out.edge = wp.min(pl.w0 - wp.min(pl.x, pl.w0), wp.abs(pl.zs - pl.z))
        out.depth = 2.0 * pl.A
    else:
        # the shoulder edge and the ridge from the shoulder corner to the apex
        Pw = wp.vec3(pl.x, pl.y, pl.z)
        c0 = wp.vec3(pl.w0, pl.A, pl.zs)
        ap = wp.vec3(0.0, 0.0, pl.L)
        e_r = ap - c0
        t_r = wp.clamp(wp.dot(Pw - c0, e_r) / wp.max(wp.dot(e_r, e_r), 1.0e-30), 0.0, 1.0)
        out.edge = wp.min(wp.length(Pw - (c0 + e_r * t_r)), wp.max(pl.z - pl.zs, 0.0))
        out.depth = 2.0 * pl.A * wp.clamp((pl.L - pl.z) / wp.max(pl.h, 1.0e-9), 0.0, 1.0)
    # the facet's draws seeded by its CRYSTAL (its own random, which its rotated copies share), not by the instance
    # index: a copy's foot texels in the skin set shade as its original's island in the growths set
    out.seed = int(zz[1] * 16777216.0)
    out.rnd = proc.u01(proc.hash3i(out.seed, out.facet, 1, 977))      # the forge's one hash (lowbias32: TSL agrees)
    out.crnd = zz[1]
    out.zrel = (pl.z - zz[0]) / wp.max(q[0], 1.0e-9)
    # the signed coordinate across the face (prism_local folds x into the wedge): along the facet's tangent
    nax = wp.normalize(gB[bi] - gA[bi])
    u = onb_e1(nax) * wp.cos(q[2]) + onb_e2(nax) * wp.sin(q[2])
    ang = float(pl.facet) * 6.283185307179586 / float(sides)
    out.xs = wp.dot(p - gA[bi], wp.cross(nax, u) * wp.cos(ang) - u * wp.sin(ang))
    out.lp = wp.vec3(wp.dot(p - gA[bi], u), wp.dot(p - gA[bi], wp.cross(nax, u)), pl.z)
    return out


@wp.struct
class GrowthMat:
    col: wp.vec3         # linear albedo (dielectrics) or F0 (metals)
    rough: float
    metal: float
    sss: float           # subsurface opacity (the masks pack's R for growth texels)
    irid: float          # thin-film weight (the growth pack's G)
    emis: float          # emissive mask (the growth pack's B; colour and pulse are the element's uniforms)
    phase: float         # the emissive pulse's phase (the growth pack's A: per crystal, so the pulse goes cell by cell)
    h: float             # texture-tier height (m): the growth-step banding on the prism faces (growth_steps)
    ao: float            # the self-occluding root: the factor the AO channel takes (1 up the crystal, 1 - ROOT_AO at the
                         # skin line)
    trans: float         # refractive transmission (opt-in families)
    layer: float         # the frost / patina / rust layer's weight (the growths masks pack's B)
    film: float          # thin-film thickness 0..1 between the family's irid_lo and irid_hi: one per facet (bismuth's
                         # terraces each their own colour; the growths masks pack's G)


@wp.func
def _lum(c: wp.vec3):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


@wp.func
def _lsh(c: wp.vec3, k_l: float, k_s: float):
    L = wp.max(_lum(c), 1.0e-6)
    g = wp.vec3(L, L, L)
    return (g + (c - g) * k_s) * k_l


@wp.func
def _ss(a: float, b: float, x: float):
    t = wp.clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@wp.func
def _step_z(seed: int, facet: int, j: int, ph: float, lam: float):
    """growth step j's height along the axis on one facet: its cell's centre, jittered +-0.35 of the pitch"""
    return (float(j) + 0.5 + 0.7 * (proc.u01(proc.hash3i(seed, facet * 65536 + j, 6, 977)) - 0.5) - ph) * lam


@wp.func
def growth_steps(gs: GrowthSurf, amp: float, lam_r: float, texel: float):
    """IRREGULAR GROWTH-STEP BANDING on a prism's side faces: vicinal treads, each rising across a narrow riser (its
    depth amp R x 0.25-1.75) and sinking back over its tread to the next step, so the face keeps its plane; a HEIGHT (m)
    that the growths pass turns into the baked normal (relief, never paint). The pitch varies (cells of lam = lam_r R, a
    step jittered +-0.35 lam inside its cell, 28 % of the cells empty), every facet has its own phase (the steps break
    at each facet edge) and half the steps die out partway across the face (from one side, at a random point); none on
    the tip faces, within a riser of the shoulder or near a facet edge (the next face stands at another phase: no jump
    between faces); band-limited (gone below ~4 texels). It replaces the regular sine striations, which read as stripes
    painted round every crystal (the growth run of 10-21)"""
    h = float(0.0)
    if amp <= 0.0 or gs.w0 <= 0.0 or gs.z >= gs.zs:
        return h
    lam = wp.max(lam_r * gs.R, 1.0e-6)
    fade = _ss(4.0, 7.0, lam / texel)
    if fade <= 0.0:
        return h
    w0 = wp.max(1.2 * texel, 0.10 * lam)                       # the riser's width (at most 0.45 of its tread)
    ph = proc.u01(proc.hash3i(gs.seed, gs.facet, 5, 977))      # the facet's own phase
    j0 = int(wp.floor(gs.z / lam + ph))
    for k in range(3):
        j = j0 - 1 + k
        zj = _step_z(gs.seed, gs.facet, j, ph, lam)
        P = _step_z(gs.seed, gs.facet, j + 1, ph, lam) - zj     # its tread runs to the next cell's step
        w = wp.min(w0, 0.45 * P)
        t = gs.z - zj
        if t > -0.5 * w and t < P - 0.5 * w:
            hj = gs.facet * 65536 + j
            if proc.u01(proc.hash3i(gs.seed, hj, 7, 977)) < 0.72:
                d = amp * gs.R * (0.25 + 1.5 * proc.u01(proc.hash3i(gs.seed, hj, 8, 977)))
                acr = float(1.0)
                cut = proc.u01(proc.hash3i(gs.seed, hj, 9, 977))
                if cut < 0.5:
                    sgn = float(1.0)
                    if cut < 0.25:
                        sgn = -1.0
                    xe = 1.2 * (proc.u01(proc.hash3i(gs.seed, hj, 10, 977)) - 0.5) * gs.w0
                    acr = _ss(-0.2 * gs.w0, 0.2 * gs.w0, sgn * (gs.xs - xe))
                h = h + d * acr * (_ss(-0.5 * w, 0.5 * w, t) - (t + 0.5 * w) / P)
    eb = wp.max(1.5 * texel, 0.12 * gs.w0)
    return h * fade * _ss(0.0, eb, gs.w0 - wp.abs(gs.xs)) * _ss(0.0, w0, gs.zs - gs.z)


@wp.func
def growth_material(gs: GrowthSurf, fam: int, FT: wp.array(dtype=wp.float32), ao: float, aol: float, conv: float,
                    ny: float, texel: float, skin: wp.vec3):
    """the family's surface at a growth texel: the table row (RECIPES) shaped by the crystal's own data, the bake's
    drivers (the layer masks: R11's frost formulas, patina in cavities) and the texture tier, after the module notes'
    THE LOOK: one draw per facet (seeded by its crystal) of ln L, chroma and roughness (REF §7 "large mid-scale
    roughness and saturation variation") and a tarnish below the facet scale, edge wear on the facet edges, the
    self-occluding root (m.ao: the root gradient the AO channel takes; the albedo follows the AO by aol_L), the
    roughness following ln L, the growth-step banding (m.h). skin = the creature's colour here (the flesh family
    re-shades it)"""
    o = fam * 43
    m = GrowthMat()
    c0 = wp.vec3(FT[o + 0], FT[o + 1], FT[o + 2])
    c1 = wp.vec3(FT[o + 3], FT[o + 4], FT[o + 5])
    r1 = gs.rnd
    r2 = proc.u01(proc.hash3i(gs.seed, gs.facet, 2, 977))
    r3 = proc.u01(proc.hash3i(gs.seed, gs.facet, 3, 977))
    # the layer weight (0 none, 1 cavities, 2 exposed: R11 mantis-wasp / runtime frost, 3 recesses: R11 ice-crab)
    mode = int(FT[o + 20] + 0.5)
    lw = float(0.0)
    if mode == 1:
        lw = _ss(0.01, 0.10, -aol) + 0.6 * (1.0 - _ss(0.35, 0.85, ao))
    elif mode == 2:
        lw = _ss(0.3, 1.0, ao) * (0.55 + 0.15 * ny) + 0.1 * conv
    elif mode == 3:
        lw = 0.75 * (1.0 - _ss(0.4, 0.95, ao)) + 0.2
    lw = wp.clamp(lw * FT[o + 21], 0.0, 1.0)
    col = c0
    if FT[o + 31] > 0.5:
        col = _lsh(skin, 1.15, 0.85)                       # flesh: stretched pigment, paler and greyer
    # the self-occluding root: the AO channel's gradient over ROOT_Z radii above the skin line
    g = 1.0 - ROOT_AO * (1.0 - _ss(0.0, ROOT_Z, gs.zrel))
    # ln L: the facet's draw (RMS jit_L; x sqrt 12 for a uniform variate), the TARNISH below the facet scale (RMS
    # 0.71 jit_M: 3 octaves at 0.2-0.8 R in the crystal's own frame, x4 on fbm3's RMS 0.177; the reference sets'
    # ln L octaves stay flat down to 2 mm, so one draw per facet alone leaves every facet a flat card), edge wear on the
    # facet edges (edge_L: the convex line, ~2 texels; on a small crystal, whose facets are a few texels across, its
    # strength scaled down by the band's share of the face, so the worn line keeps the reference's few per cent of the
    # area and the median stays the set's), and the AO link (aol_L, the set's hp16 slope) on the local AO and on the
    # root's own darkening
    we = wp.max(1.75 * texel, 0.035 * gs.R)
    em = (1.0 - _ss(0.0, we, gs.edge)) * wp.min(1.0, 0.12 * wp.max(gs.w0, 0.5 * gs.R) / we)
    tl = gs.lp / (0.8 * wp.max(gs.R, 1.0e-6)) + wp.vec3(float(gs.seed % 977) * 1.37, 0.0, 0.0)
    tn = FT[o + 39] * 4.0 * proc.fbm3(tl, 3, 2.0, 0.5, 4251)
    lnl = FT[o + 22] * (r1 - 0.5) * 3.464 + tn + FT[o + 26] * em + FT[o + 27] * (aol + ao * (g - 1.0))
    # chroma: the facet's draw (RMS jit_S), the worn edges' (edge_S) and the tarnish's (darker is richer: the metal_nodules
    # set's concave texels, S +.036 of .144 at L x.72, S ~ L^-0.67)
    col = _lsh(col, wp.exp(lnl), (1.0 + FT[o + 23] * (r2 - 0.5) * 3.464) * (1.0 + (FT[o + 33] - 1.0) * em) *
               wp.exp(-0.67 * tn))
    col = col + (c1 - col) * lw
    metal = FT[o + 10] + (FT[o + 11] - FT[o + 10]) * lw
    # the dielectric envelope (REF R2: only ice and crystal reach linear L 0.69); a metal's F0 is not an albedo
    if metal < 0.5:
        lc = _lum(col)
        col = col * (wp.clamp(lc, 0.010, 0.69) / wp.max(lc, 1.0e-6))
    # roughness: the facet's own residual draw, the cavities, and ln L's (rough_L: darker is rougher, so the worn edges
    # gloss and the roots go matte; it carries the facet-to-facet roughness octave the reference sets show), held at the
    # family's floor (rough_lo: its measured set's p5 where that saturates the coupling, else 0.02)
    rough = FT[o + 6] + FT[o + 7] * (r3 - 0.5) * 3.464 + FT[o + 8] * aol + FT[o + 32] * lnl
    rough = rough + (FT[o + 9] - rough) * lw
    m.col = col
    m.rough = wp.clamp(rough, FT[o + 42], 1.0)
    m.metal = wp.clamp(metal, 0.0, 1.0)
    m.sss = FT[o + 12] * (1.0 - lw)
    m.irid = FT[o + 15] * (1.0 - lw)
    zr = wp.clamp(gs.z / wp.max(gs.L, 1.0e-9), 0.0, 1.0)
    m.emis = wp.clamp(FT[o + 18] * (1.0 + FT[o + 19] * (zr - 0.5)) * (1.0 - lw), 0.0, 1.0)
    m.phase = gs.crnd
    m.trans = FT[o + 14] * (1.0 - lw)
    m.layer = lw
    m.film = r1
    m.ao = g
    m.h = growth_steps(gs, FT[o + 24], FT[o + 25], texel)
    return m


@wp.struct
class GrowthTexel:
    f: float             # the growth's share of the texel (0: all skin); the caller blends its skin result toward this
    share: float         # the runtime's id mask (the growth pack's R): f, but 0 for the flesh family (re-shaded skin
                         # keeps the skin's runtime terms: subsurface, fuzz, wetness, display)
    fam: int             # the growth family id (0: none)
    col: wp.vec3
    rough: float
    metal: float
    sss: float
    irid: float
    emis: float
    phase: float
    ao: float            # the growth's root gradient on the AO (GrowthMat.ao; 1 where no growth)


@wp.func
def unpack_ids(code: int):
    """the bake's packed ids (voxel.lab_pack: id0 | id1 << 8 | round(255 w0 / (w0 + w1)) << 16; id 0 = skin) -> (the
    growth family, its share of the texel) as a vec2; two growth families on one texel keep the heavier. Only 1-63 are
    growth families (ID_RANGES): an id past them (a cyborg plate's, 64-95, which forge/cyborg.py unpack takes) reads
    as skin here, so a growth beside a plate keeps its own weight and a plate alone gives no family"""
    id0 = code & 255
    id1 = (code >> 8) & 255
    w0 = float((code >> 16) & 255) / 255.0
    if id0 > GROWTH_ID_MAX:
        id0 = 0
    if id1 > GROWTH_ID_MAX:
        id1 = 0
    fam = id0
    f = w0
    if id0 == 0:
        fam = id1
        f = 1.0 - w0
    elif id1 != 0:
        f = 1.0
    if fam == 0 or fam >= 255:
        return wp.vec2(0.0, 0.0)
    return wp.vec2(float(fam), f)


@wp.func
def growth_texel(code: int, p: wp.vec3, grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3),
                 gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4), gZ: wp.array(dtype=wp.vec4),
                 FT: wp.array(dtype=wp.float32), ao: float, aol: float, conv: float, ny: float, texel: float,
                 skin: wp.vec3):
    """the material pass's per-id branch (work/bestiary/patches/material_ids.md): the texel's packed ids -> its growth
    family and share, and that family's surface at the high's point p (growth_surface + growth_material). skin = the
    skin pass's own colour here (the flesh family re-shades it)"""
    out = GrowthTexel()
    out.f = 0.0
    out.share = 0.0
    out.fam = 0
    out.ao = 1.0
    u = unpack_ids(code)
    fam = int(u[0] + 0.5)
    if fam == 0 or u[1] <= 0.0:
        return out
    gs = growth_surface(p, grid, rq, gA, gB, gQ, gZ)
    m = growth_material(gs, fam, FT, ao, aol, conv, ny, texel, skin)
    out.f = u[1]
    out.fam = fam
    out.share = u[1] * (1.0 - FT[fam * 43 + 31])
    out.ao = m.ao
    out.col = m.col
    out.rough = m.rough
    out.metal = m.metal
    out.sss = m.sss
    out.irid = m.irid
    out.emis = m.emis
    out.phase = m.phase
    return out


@wp.func
def vein_texel(fam: int, v: float, core: float, phase: float, FT: wp.array(dtype=wp.float32), aol: float):
    """the VEIN families (ember, arc): no strokes and no voxel ids; the skin pass paints them along a coarse cellular
    network in the anatomical coordinate (octopus_skin.skin_at's vein mask): v = the charred / slate crust's weight
    (the share), core = the glowing centre line, phase = the vein cell's random (R10: the pulse goes cell by cell)"""
    out = GrowthTexel()
    out.f = 0.0
    out.share = 0.0
    out.fam = 0
    if fam <= 0 or fam >= 255 or v <= 0.0:
        return out
    o = fam * 43
    c0 = wp.vec3(FT[o + 0], FT[o + 1], FT[o + 2])
    out.f = v
    out.share = v
    out.fam = fam
    out.col = _lsh(c0, wp.exp(FT[o + 22] * (phase - 0.5) * 3.464), 1.0) * wp.exp(FT[o + 27] * aol)
    out.rough = wp.clamp(FT[o + 6] + FT[o + 8] * aol, FT[o + 42], 1.0)
    out.metal = FT[o + 10]
    out.sss = 0.0
    out.irid = 0.0
    out.emis = wp.clamp(FT[o + 18] * core, 0.0, 1.0)
    out.phase = phase
    return out


@wp.struct
class GrowthHalo:
    w: float             # the infusion's weight on the skin here (0 none, the family's halo at a root); the skin pass
                         # writes it into the skin's own channels (the GROWTH pack's R stays the growth share alone)
    ks: float            # the skin's chroma scale
    kl: float            # the ln L spread's amplitude here: the skin pass multiplies its driver term by it (the skin's
                         # relief and the tarnish below, about the skin's own median: octopus_skin.k_skin)
    tar: float           # the TARNISH here (halo_tarnish): unit-RMS noise in units of the crystal's R, blended across
                         # the crystals whose halos reach p
    metal: float         # the infused skin's metalness (the ORM's B on skin), at most w
    trans: float         # the thin mask the infused skin reaches (the runtime's subsurface: 0.85 thin + its 0.06 floor)


@wp.func
def _tar_oct(p: wp.vec3, c: wp.vec3, lam: float, amp: float, seed: int):
    # one tarnish octave: lattice lam, its effective wavelength 2.1 lam faded out from 2.74 to 1.37 mm about the
    # floor, 1.94 mm (two of the reference's 0.968 mm texels)
    fo = _ss(0.7071, 1.4142, 2.1 * lam / 0.001937)
    if fo <= 0.0:
        return 0.0
    return fo * amp * proc.noise3((p - c) / lam, seed)


@wp.func
def halo_tarnish(p: wp.vec3, c: wp.vec3, R: float, seed: int):
    """THE TARNISH of one crystal's halo (halo_v2.md v2c): the mantis-wasp metal-nodule repaint's ln-L ratio split per
    octave (research/ref_study/mantiwasp_zyr/halo_scale.json) in units of the crystal's radius R. The reference spreads
    its variance evenly over the octaves from 0.15 to 4.9 R (its body zoning above that is the halo's own falloff
    here): five gradient-noise octaves, lattice 0.119 R x 2 per octave (effective wavelengths 0.23-3.9 R), variances
    fitted to that split, unit RMS together, anchored at the crystal (c). Each octave fades out as its wavelength nears
    two of the reference's texels (1.94 mm), so a small crystal never grains finer than the reference can show"""
    return (_tar_oct(p, c, 0.1189 * R, 1.9126, seed) + _tar_oct(p, c, 0.2378 * R, 1.4308, seed + 131) +
            _tar_oct(p, c, 0.4757 * R, 1.6095, seed + 262) + _tar_oct(p, c, 0.9514 * R, 1.4708, seed + 393) +
            _tar_oct(p, c, 1.9027 * R, 1.7674, seed + 524))


@wp.func
def growth_halo(p: wp.vec3, grid: wp.uint64, rq: float, gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3),
                gQ: wp.array(dtype=wp.vec4), gZ: wp.array(dtype=wp.vec4), FT: wp.array(dtype=wp.float32)):
    """THE SKIN'S RESPONSE round the roots (REF §7 (b); the module notes' THE LOOK; work/bestiary/patches/halo_v2.md):
    the family's element infusion as a LOCAL halo on the skin at p (the high's point; the skin pass applies it before
    the growth blend, into the skin's own channels). Per crystal of a family with a halo: its exact distance d
    (sd_prism, or the round cone's), a reach between halo_r0 and halo_r1 of its radii picked by a noise at ~1.5 R (the
    falloff wanders, never a ring), a finer noise breaking the edge; w = halo x (1 - smoothstep(0.15, 1, d / reach +
    edge noise)), a cluster taking its strongest. With k = w / halo, the skin there: chroma x 1 - (1 - halo_S) k, its
    ln L spread halo_L k x the skin pass's driver term, metalness halo_metal k x 0.8-1.2 (a 4 mm mottle) at most w, the
    thin mask at least halo_T k. The tarnish (one of the driver term's parts): each crystal's own (halo_tarnish, in
    its R), blended by the crystals' weights over the root of their sum of squares (unit RMS where they overlap, no
    seam between a cluster's crystals). rq: halo_query() (0: no family here has a halo, and nothing is read)"""
    out = GrowthHalo()
    out.w = 0.0
    out.ks = 1.0
    out.kl = 0.0
    out.tar = 0.0
    out.metal = 0.0
    out.trans = 0.0
    if rq <= 0.0:
        return out
    best = float(0.0)
    bo = int(-1)
    tw = float(0.0)
    ww = float(0.0)
    qy = wp.hash_grid_query(grid, p, rq)
    i = int(0)
    while wp.hash_grid_query_next(qy, i):
        o = int(gZ[i][3] + 0.5) * 43
        amt = FT[o + 34]
        if amt > 0.0:
            q = gQ[i]
            d = float(0.0)
            if q[3] > 0.5:
                d = sd_prism(p, gA[i], gB[i], q[0], q[1], q[2], int(q[3]))
            else:
                d = S_.sd_roundcone(p, gA[i], gB[i], q[0], q[1])
            R = wp.max(q[0], 1.0e-6)
            nr = wp.clamp(0.5 + 0.9 * proc.fbm3(p / (1.5 * R), 2, 2.0, 0.5, 4241), 0.0, 1.0)
            reach = R * (FT[o + 37] + (FT[o + 38] - FT[o + 37]) * nr)
            t = wp.max(d, 0.0) / reach + 0.22 * proc.fbm3(p / (0.35 * R), 2, 2.0, 0.5, 4243)
            w = amt * (1.0 - _ss(0.15, 1.0, t))         # (a plateau at the root: the variant's full infusion there)
            if w > best:
                best = w
                bo = o
            if w > 0.0:
                tw = tw + w * halo_tarnish(p, gA[i], R, 4249 + 977 * i)
                ww = ww + w * w
    if bo < 0:
        return out
    k = best / FT[bo + 34]
    out.w = best
    out.ks = 1.0 - (1.0 - FT[bo + 36]) * k
    out.kl = FT[bo + 40] * k
    out.tar = tw / wp.sqrt(ww)
    nm = wp.clamp(0.5 + 0.9 * proc.fbm3(p / 0.004, 2, 2.0, 0.5, 4247), 0.0, 1.0)
    out.metal = wp.min(FT[bo + 35] * k * (0.8 + 0.4 * nm), best)
    out.trans = FT[bo + 41] * k
    return out


def halo_query(inst):
    """growth_halo's query radius for these instances (m): from a piece's midpoint (the hash grid's points) out to the
    farthest skin its halo can reach (half its length, its radius, 1.22 x halo_r1 radii: the edge noise's reach); 0
    when no family among them has a halo (the skin pass then reads nothing)"""
    a, b, q = (np.asarray(inst[k], np.float64) for k in ('a', 'b', 'q'))
    fam = np.asarray(inst['z'], np.float64)[:, 3].round().astype(int)
    rr = 0.0
    for f in np.unique(fam):
        name = FAMILIES[f - 1] if 1 <= f <= len(FAMILIES) else None
        if name is None or RECIPES[name]['halo'] <= 0.0:
            continue
        s = fam == f
        Rr = np.where(q[s, 3] > 0.5, q[s, 0], np.maximum(q[s, 0], q[s, 1]))
        rr = max(rr, float((0.5 * np.linalg.norm(b[s] - a[s], axis=1) + Rr +
                            1.22 * RECIPES[name]['halo_r1'] * q[s, 0]).max()))
    return rr


def gpu_instances(inst):
    """the instance arrays as Warp arrays plus the hash grid and its query radius (material pass inputs)"""
    gA = wp.array(np.asarray(inst['a'], np.float32), dtype=wp.vec3)
    gB = wp.array(np.asarray(inst['b'], np.float32), dtype=wp.vec3)
    gQ = wp.array(np.asarray(inst['q'], np.float32), dtype=wp.vec4)
    gZ = wp.array(np.asarray(inst['z'], np.float32), dtype=wp.vec4)
    mid = 0.5 * (np.asarray(inst['a']) + np.asarray(inst['b']))
    rq = float((0.5 * np.linalg.norm(np.asarray(inst['b']) - np.asarray(inst['a']), axis=1) +
                np.asarray(inst['q'])[:, 0]).max()) if len(mid) else 1e-3
    grid = wp.HashGrid(64, 64, 64)
    grid.build(wp.array(mid.astype(np.float32), dtype=wp.vec3), rq)
    return grid, rq, gA, gB, gQ, gZ


def empty_instances():
    """one dummy far-away crystal (kernels need non-empty arrays): a creature without growths"""
    return dict(a=np.array([[1e3, 1e3, 1e3]]), b=np.array([[1e3, 1e3 + 1e-3, 1e3]]), q=np.array([[1e-4, 0, 0, 6]]),
                z=np.zeros((1, 4)), root=np.zeros((1, 3)), n=np.array([[0.0, 1.0, 0.0]]), stack_of=np.zeros(1, int))


def saved_instances(inst):
    """the growth instances from a saved instances.npz dict (t10 writes plan.inst['growths'] as growths_*), or the
    dummy when the creature has none"""
    g = {k[len('growths_'):]: v for k, v in inst.items() if k.startswith('growths_')}
    return g if g.get('a') is not None and len(g['a']) else empty_instances()


# ----------------------------------------------------------------------------------------------------- growths mesh
@wp.kernel
def k_growths(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
              ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), d_nrm: wp.array(dtype=wp.vec4),
              d_ao: wp.array(dtype=wp.float32), d_hgt: wp.array(dtype=wp.float32), d_aol: wp.array(dtype=wp.float32),
              d_conv: wp.array(dtype=wp.float32), d_mat: wp.array(dtype=wp.int32), grid: wp.uint64, rq: float,
              gA: wp.array(dtype=wp.vec3), gB: wp.array(dtype=wp.vec3), gQ: wp.array(dtype=wp.vec4),
              gZ: wp.array(dtype=wp.vec4), FT: wp.array(dtype=wp.float32), texel: float, skin: wp.vec3,
              o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3),
              o_mask: wp.array(dtype=wp.vec4), o_grow: wp.array(dtype=wp.vec4)):
    """the GROWTHS mesh's material pass (its own texture set; study T ships growths in their own material): per sub-sample
    the low under it (material.low_at), the high's point (the bake's HEIGHT along the low's normal), the piece there
    (growth_surface) and its family's surface (growth_material). The family is the bake's id; where the bake's rays met
    skin (the buried ring at a root) the piece's own family. The growth steps tilt the baked normal (the height's
    surface gradient from two neighbouring sub-samples, as octopus_skin.k_skin does); the AO takes the root gradient"""
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    hgt = d_hgt[tid]
    u = unpack_ids(d_mat[tid])
    fam_b = int(u[0] + 0.5)
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_m = float(0.0)
    acc_k = wp.vec4(0.0)
    acc_g = wp.vec4(0.0)
    acc_o = float(0.0)
    hits = int(0)
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            nw = M.to_world(lo, tn_b)
            ph = lo.p + lo.n * hgt
            gs = growth_surface(ph, grid, rq, gA, gB, gQ, gZ)
            fam = gs.fam
            if fam_b != 0:
                fam = fam_b
            if fam <= 0:
                continue
            gm = growth_material(gs, fam, FT, d_ao[tid], d_aol[tid], d_conv[tid], nw[1], texel, skin)
            # the growth steps' surface gradient from the two neighbours (toward -x / -y off the island); wherever the
            # family carries steps (a riser can start at a neighbour while the centre's height is still 0)
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1 and FT[fam * 43 + 24] > 0.0:
                px = lx.p + lx.n * hgt
                py = ly.p + ly.n * hgt
                hx = growth_material(growth_surface(px, grid, rq, gA, gB, gQ, gZ), fam, FT, d_ao[tid], d_aol[tid],
                                     d_conv[tid], nw[1], texel, skin).h
                hy = growth_material(growth_surface(py, grid, rq, gA, gB, gQ, gZ), fam, FT, d_ao[tid], d_aol[tid],
                                     d_conv[tid], nw[1], texel, skin).h
                g = M.surface_grad(ph, px, py, gm.h, hx, hy)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + gm.col
            acc_r = acc_r + gm.rough
            acc_m = acc_m + gm.metal
            acc_k = acc_k + wp.vec4(gm.sss, gm.film, gm.layer, gs.crnd)
            acc_g = acc_g + wp.vec4(1.0, gm.irid, gm.emis, gm.phase)
            acc_o = acc_o + gm.ao
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    # Toksvig (as k_skin): the averaged normal's lost length widens the highlight
    ln = wp.length(acc_n) / fh
    var = 0.5 * wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    r = acc_r / fh
    r = wp.sqrt(wp.sqrt(r * r * r * r + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(d_ao[tid] * acc_o / fh, wp.clamp(r, 0.0, 1.0), acc_m / fh)
    o_mask[tid] = acc_k / fh
    o_grow[tid] = acc_g / fh


def run_growths(low, drivers, size, inst, texel, ss=2, skin=(0.18, 0.12, 0.10), log=print):
    """the growths mesh's maps from its bake (bake.bake on growth.low_mesh's V, F, UV with low_frames; the same
    SparseSDF high). Returns image-order uint8 maps: albedo (sRGB), normal (GL), orm (AO with the root gradient,
    roughness, metalness), masks (R subsurface, G film thickness, B frost / patina layer, A crystal random) and growth
    (R share = 1, G iridescence, B emissive mask, A pulse phase)"""
    import time
    from . import calib
    from .bake import dilate_all
    t0 = time.time()
    uvm = M.uv_bvh(low['F'], low['UV'], size)
    attr = np.zeros((len(low['V']), 4))
    lpos, lnrm, ltan, lattr = M.corner_arrays(low['V'], low['F'], low['N'], low['TAN'], attr)
    dr = dict(drivers)
    if 'mat' not in dr:
        dr['mat'] = np.zeros((size, size), np.int32)
    D = M.driver_arrays({**dr, **calib.relief_drivers(dr, 1.0 / texel)})
    grid, rq, gA, gB, gQ, gZ = gpu_instances(inst)
    FT = wp.array(family_table(), dtype=wp.float32)
    n = size * size
    outs = [wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3), wp.zeros(n, dtype=wp.vec3),
            wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)]
    wp.launch(k_growths, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr, D['normal'], D['ao'], D['height'],
                                        D['ao_local'], D['conv'], D['mat'], grid.id, float(rq), gA, gB, gQ, gZ, FT,
                                        float(texel), wp.vec3(*skin)] + outs)
    wp.synchronize()
    cov = np.asarray(drivers['normal'])[..., 3] > 0
    alb, nrm, orm = (np.asarray(o.numpy()).reshape(size, size, 3)[::-1] for o in outs[:3])
    msk, grw = (np.asarray(o.numpy()).reshape(size, size, 4)[::-1] for o in outs[3:])
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb, orm=orm,
                                 msk=msk, grw=grw), 8)
    q8 = lambda a: np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    out = dict(albedo=q8(M.srgb_oetf(np.where(grown[..., None], dil['alb'], 0.5))),
               normal=q8(np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0]) * 0.5 + 0.5),
               orm=q8(np.where(grown[..., None], dil['orm'], [1.0, 0.5, 0.0])),
               masks=q8(np.where(grown[..., None], dil['msk'], 0.0)),
               growth=q8(np.where(grown[..., None], dil['grw'], 0.0)))
    log(f'[growths] {size}^2 x ss {ss}: {time.time()-t0:.1f}s')
    return out


# ----------------------------------------------------------------------------------------------------- the octopus
def octopus_sites(prog, cage, arms, info, spec, rng, n_head=150_000, s_max=0.75, log=print):
    """candidate roots on the octopus's block-out [GPU: prog.project / normals; unverified on CPU]:
      * the head set: area samples of the cage's body and crown-top regions (octopus_sculpt.sample_cage), projected
        onto the block-out, minus the eyes (1.6 eye radii and the lid bowls), the funnel, the mouth and the arm tubes;
      * the reference arm: a grid in (s, alpha) over its aboral and lateral skin (cos alpha > -0.2, no suckers), s up to
        s_max, each sample's area from the grid step, mult = the arm count (its plan is replicated onto all arms).
    Returns dict(p, n, w, scale, mult, arm (bool)) and the creature's skin area estimate"""
    from .species import octopus_sculpt as SC
    from .species.octopus import arm_azimuths, arm_length, arm_radius, eye_geom
    # the head set: body, crown top and oral face (cage regions 0, 1, 2); the arm tubes dropped (the reference arm's
    # samples own them), the eyes, the funnel, the mouth and the oral face kept with mask 0 (present for the dorsal
    # share, never rooted on)
    P, N, fp = SC.sample_cage(cage, n_head, rng, lambda fp, fst: fp[:, 0] + fp[:, 1] + fp[:, 2])
    F = cage.tris()
    V = cage.V
    tri_area = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    part = cage.attrs['part'][F].mean(1)
    a_head = float((tri_area * (part[:, 0] + part[:, 1] + part[:, 2])).sum())
    a_all = float(tri_area.sum())
    p, st = prog.project(P + N * 0.006, N, maxd=0.02)
    ok = st == 0
    p, fp = p[ok], fp[ok]
    nrm = prog.normals(p)
    keep = ~SC.arm_owner(p, arms, spec)
    p, nrm, fp = p[keep], nrm[keep], fp[keep]
    m_head = np.clip(1.0 - fp[:, 2], 0.0, 1.0)
    for side in (+1, -1):
        c, out, E, Re = eye_geom(spec, side)
        # (and none in the eye's lid bowl, which takes the cheek down to 26.5 mm from the v4 eyeball's centre:
        # octopus_sculpt.eye_lid)
        m_head *= (np.linalg.norm(p - E, axis=1) > 1.6 * Re) & (SC.eye_clear(p, spec, side) > 0.0)
    m_head *= SC.funnel_mask(p, spec) < 0.01
    m_head *= np.linalg.norm(p - prog.mouth['c'], axis=1) > 1.6 * (prog.mouth['R'] + prog.mouth['r'])
    w_head = np.full(len(p), a_head / max(ok.sum(), 1))
    # the reference arm, all the way round (the oral side and the tip masked out, but present: grow() measures the
    # whole skin's dorsal share for the R11 bias)
    ref = arms[info['order'][0]]
    s = np.linspace(0.04, 0.97, 600)
    al = np.linspace(-np.pi, np.pi, 72, endpoint=False)
    ss, aa = np.meshgrid(s, al, indexing='ij')
    ss, aa = ss.ravel(), aa.ravel()
    pa, na, sta = SC.arm_surface(prog, ref, ss, aa, spec)
    oka = sta == 0
    r = arm_radius(ss[oka], spec)
    # (the step along the arm by the reference arm's OWN length: octopus.arm_length)
    da = (s[1] - s[0]) * arm_length(spec, arm_azimuths()[info['order'][0]]) * (2.0 * np.pi / len(al)) * r
    m_arm = ((np.cos(aa[oka]) > -0.2) & (ss[oka] < s_max)).astype(np.float64)
    n_arms = len(info['order'])
    sites = dict(p=np.vstack([p, pa[oka]]), n=np.vstack([nrm, na[oka]]), w=np.concatenate([w_head, da]),
                 scale=np.concatenate([np.full(len(p), np.inf), r]),
                 mult=np.concatenate([np.ones(len(p)), np.full(oka.sum(), float(n_arms))]),
                 mask=np.concatenate([m_head, m_arm]),
                 arm=np.concatenate([np.zeros(len(p), bool), np.ones(oka.sum(), bool)]))
    log(f'[growth] octopus sites: head {len(p)}, reference arm {oka.sum()} (x{n_arms}); cage area {a_all:.3f} m2')
    return sites, a_all


def plan_octopus_growths(plan, prog, cage, arms, info, spec, rng, family='metal_crystal', preset=None,
                         voxel=0.0003, texel=1.0 / 4590.0, gamma=1.0, ground=0.0, low=None, log=print, **kw):
    """the growth layer on the octopus [GPU through octopus_sites and settle; the CPU checks run it on Warp's CPU
    device]: sites, pieces (every crystal on its own normal, sized by its part, inside the block-out and above the
    ground at y = ground, on every arm it is copied to), the arm pieces replicated onto all eight arms with exact
    rotated frames (the stacked arms set bakes from arm 0), each crystal's cut for the trimmed growths low
    (trim_planes: cr['cut']; low = the skin low (V, F) as t10 bakes it: a point outside it shows too, and the slits left
    against it are counted: cr['report']['trim']), the strokes emitted into the plan (after the skin features: a crystal
    wins over a papilla it overlaps) and the instance data in plan.inst['growths']. Returns the crystal arrays (growths
    mesh: low_mesh(cr, ..., stack_of=cr['stack_of']))"""
    from .species import octopus_sculpt as SC
    preset = preset or PAIRING.get(family, 'crystal')
    sites, area = octopus_sites(prog, cage, arms, info, spec, rng, log=log)
    rots = SC.arm_rotations(info['order'], spec)                          # (identical arms only: arm_rotations)
    cr = grow(sites, preset, family, area, rng, gamma=gamma, voxel=voxel, texel=texel,
              settle=lambda pts: SC.settle(prog, pts), sdf=prog.eval, ground=ground, rots=rots, log=log, **kw)
    on_arm = sites['arm'][[pc['site'] for pc in cr['pieces']]][cr['piece']] if len(cr['a']) else np.zeros(0, bool)
    cr = replicate(cr, rots, on_arm)
    cr['cut'] = trim_planes(cr, prog.eval, voxel, skin_low=low)
    ts = trim_slits(cr, cr['cut'], prog.eval, voxel, skin_low=low)
    cr['report']['trim'] = ts
    log(f'[growth] trim: {ts["showing"]} of {ts["points"]} face samples show ({ts["by_low"]} only outside the skin low'
        f'{"" if low is not None else ", none given"}); slits under the cut: {ts["slits"]} samples on '
        f'{ts["slit_crystals"]} crystals')
    emit(plan, cr)
    plan.inst['growths'] = instances(cr)
    return cr
