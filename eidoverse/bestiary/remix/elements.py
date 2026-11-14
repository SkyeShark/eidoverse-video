"""ELEMENTS: the one global element table of Claude's Creatures (DESIGN.md "Claude's Creatures" and its GROWTH families;
a study note §8.3, "how element families should layer over a base").

study G wired an element as a per-creature palette over grey value maps, and every part inherited the night creature's
palettes, so parts drifted from the creature wearing them (study G §0.7, §4.4). Here ONE table holds every element.
The body and every part reference the same entry. Each entry is a PBR stack, cheapest layer first (study G §8.3):

  1. ZONES (every tier). A remap per zone ROLE, toward a target hue at the pixel's own luminance, so the painted
     structure (mottling, cavities, countershading) survives. The roles:
       primary  the pigment-bearing skin or shell that carries the species' identity (the study-G shell mask),
       soft     soft tissue: membranes, the ventral skin, suckers (the study-G soft mask),
       accent   rims and tips (sucker rims on the octopus),
       pattern  the species' bands and blotches (the display pack's B channel on the octopus).
     study G's best finding is kept: the element shows in the soft tissue and the glow, while the shell goes neutral
     (study G §4.4). Poison is the exception there too: it colours the shell.
  2. GLOW (every elemental tier). An emissive colour on the species' glow mask (rims, tips, thin margins), pulsing
     with the creature skin material's travelling pulse (REF §1, R10).
  3. SURFACE (medium tier and up). A procedural overlay driven by AO and world-up: frost, char, rust bloom, patina,
     pustules. The runtime draws it (runtime/remix.js). The forge bakes it wherever it changes the relief.
  4. GROWTH (large and elite tiers). A growth family: geometry with its own full PBR material, as on study T's element
     variants (REF §7, R11).
  5. LIGHT, UI and BANE: one global row per element, like the study-G global element data object (study G §4.4).

Provenance tags on the numbers:
  [M]  measured study T PBR (REF_SKIN_STUDY §7-§8);
  [S]  read from study G data (study G is legacy and non-PBR, so only its HUES and RATIOS are used, study G §4.4), or from
       a published table (physicallybased.info, srgb-linear: forge/growth.py's source);
  [P]  a physical reference. Metal F0 values come from Real-Time Rendering 4th ed., Table 9.2 (linear RGB);
  [C]  computed from published optical constants (forge/growth.py);
  [I]  inferred or chosen, no measurement behind it (forge/growth.py's tag);
  [D]  my design choice, unverified until the engine probe renders it.
All colours are LINEAR RGB with Rec.709 primaries. Luminance L = 0.2126 R + 0.7152 G + 0.0722 B (the study's L).

The zone remap is ONE blend with three twins, which must agree (craft guide §6: "one blend implementation for the bake
and the TSL runtime, with a per-pixel parity test"):
  zone_remap()       here (numpy, the reference);
  zoneRemapRGB()     in runtime/remix.js (scalar JS, checked by selfTest() against vectors printed from here);
  remapN()           in runtime/remix.js (the TSL node graph, written term by term from the scalar twin).

    python eidoverse/bestiary/remix/elements.py        prints the table's own checks (CPU)
"""
import copy
import os

import numpy as np

LUMA = (0.2126, 0.7152, 0.0722)
ENVELOPE = (0.010, 0.65)        # REF R2: final skin and shell albedo, linear L (sRGB8 26-210)
ROLES = ('primary', 'soft', 'accent', 'pattern')
TIERS = ('small', 'medium', 'large', 'elite')
# which stack layers each tier carries (study G §8.3; the study-G growth tiers were never used, study T has them)
TIER_LAYERS = {
    'small': ('zones', 'glow'),
    'medium': ('zones', 'glow', 'surface'),
    'large': ('zones', 'glow', 'surface', 'growth'),
    'elite': ('zones', 'glow', 'surface', 'growth'),
}
# Runtime emissive radiance per unit of glow luminance [D]. study G's six element MICs set emissive colour x intensity
# so that lum(colour) x intensity lands at 0.61-0.77, with Moonlight at 1.26 (study G §4.4 table; computed below in
# STUDY_G_GLOW_L). The designers equalised perceived glow, so a glow here is specified by its LUMINANCE, and this one
# scale maps it onto the engine. At 1.6, fire's tips emit about 1.0 against a sunlit mid skin of about 0.1-0.15 under
# the engine test's 2.2 sun (work/bestiary/engine_test/scene.js). Unverified: set it in the engine probe.
GLOW_SCALE = 1.6
STUDY_G_GLOW_L = dict(fire=0.63, ice=0.72, electric=0.61, poison=0.77, moonlight=1.26)   # [S] lum(rgb) x A per MIC


def lum(c):
    c = np.asarray(c, np.float64)
    return c[..., 0] * LUMA[0] + c[..., 1] * LUMA[1] + c[..., 2] * LUMA[2]


def srgb8(r, g, b):
    """an sRGB 8-bit colour to linear (the exact sRGB curve, as forge/calib.srgb_to_lin)"""
    c = np.array([r, g, b], np.float64) / 255.0
    return tuple(float(x) for x in np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def to_srgb8(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    s = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    return tuple(int(round(float(x) * 255.0)) for x in s)


def hexcode(c):
    return '#%02X%02X%02X' % to_srgb8(c)


# --------------------------------------------------------------------------------------------- zone remaps
def Z(target=None, w=0.0, sat=1.0, val=1.0, absolute=0.0, detail=1.0, rough=0.0, rough_to=None, rough_w=0.0,
      metal=None, src=''):
    """one zone's remap. target: linear rgb (None = no hue move); w: how far the hue and chroma move toward the target
    at the pixel's own luminance; sat: chroma x; val: luminance x (relative mode); absolute: weight of the ABSOLUTE
    mode (the target's own luminance, carrying the painted variation (L / lref)^detail: metals, whose F0 cannot keep
    a skin's L); rough: an offset; rough_to / rough_w: pull toward an absolute roughness; metal: target metalness
    (None = leave it)"""
    return dict(target=None if target is None else tuple(float(x) for x in target), w=float(w), sat=float(sat),
                val=float(val), absolute=float(absolute), detail=float(detail), rough=float(rough),
                rough_to=None if rough_to is None else float(rough_to), rough_w=float(rough_w),
                metal=None if metal is None else float(metal), src=src)


IDENTITY = Z()


def is_identity(z):
    return (z is None or (z['w'] == 0.0 and z['sat'] == 1.0 and z['val'] == 1.0 and z['absolute'] == 0.0
                          and z['rough'] == 0.0 and z['rough_w'] == 0.0 and z['metal'] is None))


def _envelope(c, lo=ENVELOPE[0], hi=ENVELOPE[1]):
    L = lum(c)
    return c * (np.clip(L, lo, hi) / np.maximum(L, 1e-6))[..., None]


def _gamut(c):
    """luminance-preserving chroma compression into [0, 1] per channel (L itself must already be in [0, 1])"""
    L = lum(c)[..., None]
    mx = c.max(-1, keepdims=True)
    mn = c.min(-1, keepdims=True)
    k_hi = (1.0 - L) / np.maximum(mx - L, 1e-6)
    k_lo = L / np.maximum(L - mn, 1e-6)
    k = np.minimum(1.0, np.minimum(k_hi, k_lo))
    return L + (c - L) * k


def zone_remap(c, z, lref, m=1.0):
    """THE zone blend (numpy reference; remix.js twins it). c: (..., 3) linear albedo; z: a Z() dict; lref: the zone's
    reference luminance (species data: the zone's measured L p50); m: the zone mask, broadcastable to c[..., 0].
    Steps (identical in remix.js):
      rel = the luminance-matched target, the hue/chroma move, chroma x sat, luminance x val, then the SKIN envelope
            (L 0.010-0.65) and the gamut compression;
      abs = the target x (L / lref)^detail clamped to x0.25-4, held to L <= 1 and the gamut (a metal's F0 is not skin:
            no skin envelope, mercury keeps its 0.78);
      out = rel + (abs - rel) x absolute, mixed in by the mask"""
    c = np.asarray(c, np.float64)
    m = np.asarray(m, np.float64)
    if is_identity(z):
        return c.copy()
    L = lum(c)[..., None]
    if z['target'] is not None:
        T = np.asarray(z['target'], np.float64)
        Tn = T * (L / max(float(lum(T)), 1e-4))
    else:
        T = None
        Tn = c
    c1 = c + (Tn - c) * z['w']
    c2 = L + (c1 - L) * z['sat']
    out = _gamut(_envelope(c2 * z['val']))
    if z['absolute'] > 0.0 and T is not None:
        ratio = np.clip(np.exp(z['detail'] * np.log(np.maximum(L / lref, 1e-4))), 0.25, 4.0)
        ab = _gamut(_envelope(T * ratio, 0.0, 1.0))
        out = out + (ab - out) * z['absolute']
    return c + (out - c) * m[..., None]


def zone_material(rough, metal, z, m=1.0):
    """the zone's roughness and metalness moves (the same order as remix.js): offset, pull toward rough_to, metal"""
    m = np.asarray(m, np.float64)
    if is_identity(z):
        return rough, metal
    rough = rough + z['rough'] * m
    if z['rough_to'] is not None:
        rough = rough + (z['rough_to'] - rough) * (z['rough_w'] * m)
    if z['metal'] is not None:
        metal = metal + (z['metal'] - metal) * m
    return rough, metal


# --------------------------------------------------------------------------------------------- growth families
# Material ids for the sculpt's material-id channel (DESIGN.md: "every stroke batch writes its material id into the
# voxels it wins, the bake samples the id under each texel"). THE ONE ID TABLE is forge/growth.py's FAMILY_ID
# (work/bestiary/patches/material_ids_v2.md): the voxels, the bake, the material pass and the runtime read it. The
# family names, their ids and the placement presets they pair with are READ FROM growth.py's SOURCE (growth_source:
# ast, no import, since growth.py imports warp) and never written in this file, so a family growth.py lacks cannot be
# named here. 0 is the creature's own skin. Each entry SUMMARISES its full PBR row in growth.RECIPES (the numbers the
# forge bakes; check_growth_sync(imported=True) compares the two) and adds what only the remix layer needs. albedo is
# the base colour (for metals: the F0 colour); rough = (p5, p50, p95) (p50 = growth.py's; where no measured spread
# exists, p50 +- 1.645 x its facet jitter); trans = the subsurface-opacity channel (growth.py's sss, the subsurface opacity); f0 from its ior;
# emissive = (mask level, glow colour (linear), glow luminance); irid = (strength, film ior, thickness nm min, max);
# coat = its frost / patina / rust layer (c1, rough1, metal1, layer amount, where). placement: the study T
# growth-placement stats (REF §7, growth_placement.json) where measured, as sizes on their creature and as a share of
# that creature's extent; at octopus scale use the ratio, see place_scale(). 'id' and 'shape' (the stroke family:
# prism6, hopper, ball, cone; vein = painted, no strokes) are filled from growth.py below.
FORGE_GROWTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'forge', 'growth.py')


def growth_source(path=FORGE_GROWTH):
    """growth.py's FAMILIES (tuple), PAIRING ({family: placement preset}) and each PLACEMENT preset's shape, read from
    its source without importing it (literals, and dict(...) calls and {...} displays of literals). Raises ImportError
    when the source cannot be read: the ids come from the one table, so there is no fallback copy"""
    import ast

    def lit(v):
        if isinstance(v, ast.Call) and getattr(v.func, 'id', None) == 'dict' and not v.args:
            return {kw.arg: lit(kw.value) for kw in v.keywords}
        if isinstance(v, ast.Dict):
            return {lit(k): lit(x) for k, x in zip(v.keys, v.values)}
        return ast.literal_eval(v)
    try:
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        got = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id in ('FAMILIES', 'PAIRING', 'PLACEMENT'):
                got[node.targets[0].id] = lit(node.value)
        fam, pair, plc = tuple(got['FAMILIES']), dict(got['PAIRING']), dict(got['PLACEMENT'])
    except (OSError, KeyError, ValueError, SyntaxError, TypeError) as e:
        raise ImportError(f'remix/elements.py reads the growth families from {path}: {e!r}') from e
    return fam, pair, {k: v.get('shape') for k, v in plc.items()}


GROWTH_NAMES, GROWTH_PAIRING, _PRESET_SHAPE = growth_source()
FAMILY_ID = dict(skin=0, **{f: i + 1 for i, f in enumerate(GROWTH_NAMES)})       # growth.FAMILY_ID's own rule
# the placement stats two presets share (growth.PAIRING: ice_clear grows as ice, the metal_* families as the crystals)
_PLACE_ICE = dict(pieces=129, size_m=(0.13, 0.23, 0.48), proud_m=(0.04, 0.075, 0.23), creature_m=5.5,
                  feet=(0.68, 0.30, 0.02), cover=0.06)
_PLACE_CRYSTAL = dict(pieces=269, size_m=(0.09, 0.16, 0.32), proud_m=(0.04, 0.08, 0.16), creature_m=3.3,
                      feet=(0.37, 0.55, 0.09), cover=0.40)
GROWTH_FAMILIES = {
    'skin': dict(kind='organic', albedo=None, src='the creature skin material pass (species *_skin.py)'),
    'ice': dict(
        kind='dielectric', albedo=(0.386, 0.708, 0.799), rough=(0.06, 0.06, 0.06), metal=0.13, trans=0.89,
        f0=0.018, emissive=(1.0, (0.0, 0.90, 1.0), 0.72), irid=None, micro=False, ao_p50=0.68,
        placement=dict(_PLACE_ICE),
        src='[M] ice-crab ice shards (#A7DBE7; metal 0.13 kept as measured, physically ice is a dielectric with F0 '
            '0.018 [P]); glow colour from study G ice [S]'),
    'ice_clear': dict(
        kind='dielectric', albedo=(0.386, 0.708, 0.799), rough=(0.06, 0.06, 0.06), metal=0.0, trans=0.30,
        f0=0.018, emissive=(0.75, (0.0, 0.90, 1.0), 0.72), irid=None, micro=False, ao_p50=0.68,
        placement=dict(_PLACE_ICE),
        src='growth.py ice_clear (new here): ice\'s colour and roughness [M], metal 0 and n 1.31 [S], refractive '
            'transmission .90 at runtime on request [I], mask .75 = cold ice [M]; glow and placement as ice'),
    'crystal': dict(
        kind='dielectric', albedo=(0.462, 0.202, 0.558), rough=(0.12, 0.27, 0.73), metal=0.52, trans=0.94,
        emissive=(0.71, (0.62, 0.40, 1.0), 0.45), irid=None, micro=False, ao_p50=0.61,
        placement=dict(_PLACE_CRYSTAL),
        src='[M] squid-creature crystals (#B57BC5); they also crust distal limbs (55 % of feet on flanks)'),
    'metal_crystal': dict(
        kind='metal', albedo=(0.262, 0.238, 0.178), rough=(0.23, 0.36, 0.49), metal=0.94, trans=0.12,
        emissive=None, irid=None, micro=False, ao_p50=0.77,
        placement=dict(pieces=100, size_m=(0.05, 0.07, 0.21), proud_m=(0.01, 0.02, 0.06), creature_m=1.9,
                       feet=(0.60, 0.34, 0.06), cover=0.15),
        src='[M] mantis-wasp metal-nodule (metal 0.94, 0.84-1.0); its chrome / gold / gunmetal variants are the metal_chrome '
            '/ metal_gold / metal_gunmetal families (DESIGN.md: metalness 0.85-1.0, roughness 0.08-0.3)'),
    'metal_gold': dict(
        kind='metal', albedo=(1.0, 0.773, 0.307), rough=(0.10, 0.18, 0.26), metal=1.0, trans=0.0, emissive=None,
        irid=None, micro=False, ao_p50=0.61, placement=dict(_PLACE_CRYSTAL),
        src='was metal_crystal\'s gold variant: physicallybased.info Gold srgb-linear, red clamped [S] (was RTR4 '
            '(1.000 .782 .344) [P]); rough .18 [I] (was .06/.12/.22); placed as the crystals (growth.PAIRING)'),
    'metal_chrome': dict(
        kind='metal', albedo=(0.654, 0.685, 0.701), rough=(0.04, 0.08, 0.16), metal=1.0, trans=0.0, emissive=None,
        irid=None, micro=False, ao_p50=0.61, placement=dict(_PLACE_CRYSTAL),
        src='was metal_crystal\'s chrome variant: physicallybased.info Chromium srgb-linear [S] (was RTR4 (.549 .556 '
            '.554) [P]); rough .04/.08/.16 kept, p50 growth.py\'s .08 (DESIGN\'s low end) [I]; placed as the crystals'),
    'metal_gunmetal': dict(
        kind='metal', albedo=(0.441, 0.400, 0.361), rough=(0.18, 0.28, 0.38), metal=1.0, trans=0.0, emissive=None,
        irid=None, micro=False, ao_p50=0.61, placement=dict(_PLACE_CRYSTAL),
        src='was metal_crystal\'s gunmetal variant: physicallybased.info Titanium as the base [S/I] (was (.33 .34 .37) '
            '[D]); rough .28 [I] (was .15/.25/.35); placed as the crystals'),
    'metal_silver': dict(
        kind='metal', albedo=(0.991, 0.985, 0.974), rough=(0.05, 0.12, 0.19), metal=1.0, trans=0.0, emissive=None,
        irid=None, micro=False, ao_p50=0.61, placement=dict(_PLACE_CRYSTAL),
        src='growth.py metal_silver (new here): physicallybased.info Silver srgb-linear [S]; rough .12 [I]'),
    'metal_copper': dict(
        kind='metal', albedo=(0.932, 0.623, 0.522), rough=(0.14, 0.22, 0.30), metal=1.0, trans=0.0, emissive=None,
        irid=None, micro=False, ao_p50=0.61, placement=dict(_PLACE_CRYSTAL),
        src='growth.py metal_copper (new here): physicallybased.info Copper srgb-linear [S]; rough .22 [I]'),
    'bismuth': dict(
        kind='metal', albedo=(0.5542, 0.5319, 0.4914), rough=(0.03, 0.08, 0.13), metal=1.0, trans=0.0,
        emissive=None, irid=(1.0, 2.0, 100.0, 400.0), micro=False, ao_p50=0.7,
        placement=dict(size_rel=(0.03, 0.06, 0.12), proud_rel=(0.01, 0.03, 0.05), feet=(0.6, 0.35, 0.05),
                       cover=0.10),
        src='[D] stepped hopper crystals; F0 [C] from Hagemann et al. 1975 n, k (was an estimate (.65 .60 .62)); the '
            'oxide film (n ~2.4-2.6 for Bi2O3) as thin-film iridescence at ior 2.0 [I] over 100-400 nm, three\'s '
            'KHR_materials_iridescence default range [S] (was 180-460 nm [D]); rough .08 [I] (was .05/.10/.20)'),
    'liquid_metal': dict(
        kind='metal', albedo=(0.781, 0.780, 0.778), rough=(0.03, 0.03, 0.03), metal=1.0, trans=0.0,
        emissive=None, irid=None, micro=False, ao_p50=0.8,
        placement=dict(size_rel=(0.02, 0.05, 0.10), proud_rel=(0.005, 0.015, 0.03), feet=(0.35, 0.45, 0.20),
                       cover=0.12),
        src='[P] mercury F0 (physicallybased.info Mercury [S]); rough .03, a liquid surface [I] (was .02/.04/.08); blobs '
            'and drips settle downward (more ventral feet than the crystals) [D]'),
    'verdigris': dict(
        kind='metal', albedo=(0.932, 0.623, 0.522), rough=(0.20, 0.30, 0.45), metal=1.0, trans=0.0,
        emissive=None, irid=None, micro=False, ao_p50=0.72,
        coat=dict(albedo=(0.0561, 0.4508, 0.4233), rough=0.85, metal=0.0, cover=0.85, where='cavities'),
        placement=dict(size_rel=(0.02, 0.05, 0.12), proud_rel=(0.01, 0.04, 0.09), feet=(0.62, 0.33, 0.05),
                       cover=0.10),
        src='was verdigris_copper: physicallybased.info Copper srgb-linear [S] (was RTR4 (.955 .638 .538) [P]); the '
            'verdigris coat #43B3AE gathering in cavities [D], rough .85 (was .90), layer amount .85 (was a .3-.8 '
            'cover range) [I]'),
    'rust': dict(
        kind='metal', albedo=(0.530, 0.513, 0.494), rough=(0.30, 0.40, 0.50), metal=1.0, trans=0.0,
        emissive=None, irid=None, micro=False, ao_p50=0.72,
        coat=dict(albedo=(0.2016, 0.0423, 0.0176), rough=0.90, metal=0.0, cover=0.75, where='exposed'),
        placement=dict(size_rel=(0.02, 0.05, 0.12), proud_rel=(0.01, 0.03, 0.08), feet=(0.62, 0.33, 0.05),
                       cover=0.10),
        src='was rust_iron: physicallybased.info Iron srgb-linear [S] (was RTR4 (.562 .565 .578) [P]); rough .40 [I] '
            '(was .30/.42/.55); the oxide coat sRGB8 (124 58 36) [I] (was (150 72 38) [D]), rough .90 (was .85), on '
            'the exposed side at layer amount .75 (was a .4-.7 cover range)'),
    'bone': dict(
        kind='dielectric', albedo=(0.556, 0.556, 0.466), rough=(0.52, 0.60, 0.68), metal=0.0, trans=0.30,
        f0=0.04, emissive=None, irid=None, micro=False, ao_p50=0.75,
        placement=dict(size_rel=(0.02, 0.06, 0.15), proud_rel=(0.01, 0.04, 0.12), feet=(0.65, 0.30, 0.05),
                       cover=0.06),
        src='physicallybased.info Bone (.793 .793 .664) x0.70 into the REF R2 envelope [S scaled] (was (.62 .56 .45) '
            '[D]); rough .60 [I] (was .40/.55/.70); sss .30 (was .15)'),
    'chitin': dict(
        kind='dielectric', albedo=(0.130, 0.078, 0.015), rough=(0.17, 0.45, 0.64), metal=0.16, trans=0.10,
        f0=0.04, emissive=None, irid=None, micro=False, ao_p50=0.87,
        placement=dict(size_rel=(0.04, 0.10, 0.25), proud_rel=(0.005, 0.01, 0.02), feet=(0.80, 0.20, 0.0),
                       cover=0.30),
        src='[M] mantis-wasp body chitin (dorsal median, metal 0.16 at p50; rough .17/.45/.64 and sss .10 as growth.py, '
            'were .10/.44/.62 and .08); F0 from n 1.5 (was .028); plates are surface layers, not spikes'),
    'keratin': dict(
        kind='dielectric', albedo=(0.3763, 0.2384, 0.0742), rough=(0.52, 0.60, 0.68), metal=0.0, trans=0.20,
        f0=0.0465, emissive=None, irid=None, micro=False, ao_p50=0.8,
        placement=dict(size_rel=(0.02, 0.05, 0.12), proud_rel=(0.01, 0.04, 0.10), feet=(0.65, 0.30, 0.05),
                       cover=0.05),
        src='REF R3 "eye socket and keratin" #A5864D, rough .60 [M] (were the beak\'s near-black (.030 .024 .018) [S/D] '
            'and .15/.25/.40); sss .20 (was .05), n ~1.55 as octopus_beak [I]'),
    'flesh': dict(
        kind='organic', albedo=None, rough=(0.12, 0.12, 0.12), metal=0.0, trans=0.95, f0=0.0201, emissive=None,
        irid=None, micro=False, ao_p50=0.8,
        placement=dict(size_rel=(0.005, 0.015, 0.04), proud_rel=(0.003, 0.008, 0.02), feet=(0.55, 0.40, 0.05),
                       cover=0.12),
        src='[D] nodules and blisters in the skin\'s own soft-zone palette (albedo None = the skin); rough .12 and sss '
            '.95 (the R8 transmission cap [M]) as growth.py (were .12/.20/.35 and .85); no micro normal (REF R7; was '
            'micro)'),
    'ember': dict(
        kind='vein', albedo=(0.025, 0.020, 0.018), rough=(0.67, 0.75, 0.83), metal=0.0, trans=0.0, f0=0.04,
        emissive=(1.0, (1.0, 0.14, 0.0), STUDY_G_GLOW_L['fire']), irid=None, micro=False, ao_p50=None, placement=None,
        src='growth.py ember (new here): VEINS the material pass paints along the skin\'s patch network (no strokes); '
            'char L .02 [I]; glow study G fire (1 .14 0) at its luminance [S]'),
    'arc': dict(
        kind='vein', albedo=(0.045, 0.055, 0.065), rough=(0.37, 0.45, 0.53), metal=0.0, trans=0.0, f0=0.04,
        emissive=(1.0, (0.0, 0.06, 1.0), STUDY_G_GLOW_L['electric']), irid=None, micro=False, ao_p50=None,
        placement=None,
        src='growth.py arc (new here): VEINS (no strokes); slate after an electric variant material (study G) [I]; glow study G electric '
            '(0 .06 1) at its luminance [S]'),
    'obsidian': dict(
        kind='dielectric', albedo=(0.022, 0.020, 0.022), rough=(0.04, 0.08, 0.20), metal=0.0, trans=0.0,
        f0=0.039, emissive=(1.0, (1.0, 0.25, 0.02), 0.90), irid=None, micro=False, ao_p50=0.7,
        placement=dict(size_rel=(0.03, 0.07, 0.15), proud_rel=(0.01, 0.04, 0.09), feet=(0.68, 0.30, 0.02),
                       cover=0.08),
        src='[P] volcanic glass n ~1.49 (F0 0.039), near-black; [D] ember veins (in growth.py: the shard glows at '
            'mask 1)'),
    'quartz_arc': dict(
        kind='dielectric', albedo=(0.60, 0.63, 0.68), rough=(0.05, 0.12, 0.30), metal=0.0, trans=0.85,
        f0=0.046, emissive=(1.0, (0.25, 0.45, 1.0), 0.80), irid=None, micro=False, ao_p50=0.65,
        placement=dict(size_rel=(0.03, 0.06, 0.14), proud_rel=(0.01, 0.04, 0.10), feet=(0.68, 0.30, 0.02),
                       cover=0.08),
        src='[P] quartz n 1.544 (F0 0.046), milky, kept under the 0.69 ice ceiling (REF sec. 8: L 0.63); '
            '[D] arc veins, flickering (in growth.py: the crystal glows at mask 1)'),
    'spore': dict(
        kind='organic', albedo=(0.40, 0.42, 0.12), rough=(0.25, 0.45, 0.60), metal=0.0, trans=0.80,
        emissive=(0.6, (0.26, 1.0, 0.0), 0.50), irid=None, micro=False, ao_p50=0.7,
        placement=dict(size_rel=(0.01, 0.03, 0.07), proud_rel=(0.005, 0.015, 0.04), feet=(0.50, 0.42, 0.08),
                       cover=0.15),
        src='[D] fungal blisters and caps, translucent, glowing gills (poison); no micro normal (REF R7, as growth.py; '
            'was micro)'),
    'moonstone': dict(
        kind='dielectric', albedo=(0.62, 0.64, 0.72), rough=(0.06, 0.10, 0.18), metal=0.0, trans=0.70,
        f0=0.045, emissive=(0.4, (0.81, 0.54, 1.0), 0.40), irid=(0.8, 1.55, 200.0, 380.0), micro=False,
        ao_p50=0.68,
        placement=dict(size_rel=(0.03, 0.06, 0.12), proud_rel=(0.01, 0.03, 0.07), feet=(0.60, 0.35, 0.05),
                       cover=0.08),
        src='[P] feldspar n 1.52-1.58; [D] adularescence approximated by a thin film; study G moonlight hue [S]'),
    'void_glass': dict(
        kind='dielectric', albedo=(0.010, 0.008, 0.014), rough=(0.02, 0.04, 0.10), metal=0.0, trans=0.0,
        f0=0.045, emissive=(1.0, (0.90, 0.05, 0.40), 0.65), irid=None, micro=False, ao_p50=0.7,
        placement=dict(size_rel=(0.03, 0.07, 0.15), proud_rel=(0.01, 0.04, 0.09), feet=(0.68, 0.30, 0.02),
                       cover=0.08),
        src='[D] (dark gaia)'),
}
for _f, _g in GROWTH_FAMILIES.items():
    _g['id'] = FAMILY_ID[_f]                    # (a family growth.py lacks fails here, at import: one table)
    _g['shape'] = 'skin' if _f == 'skin' else _PRESET_SHAPE.get(GROWTH_PAIRING.get(_f), 'vein')


def check_growth_sync(imported=False):
    """GROWTH_FAMILIES against forge/growth.py, the one table: the family names (always; their ids are growth.py's by
    construction) and, imported=True, every summary number against growth.RECIPES (imports growth.py and warp: run
    with CUDA_VISIBLE_DEVICES=-1; no kernel is launched). Returns a list of problem strings (empty = in sync)"""
    bad = []
    names = set(GROWTH_FAMILIES) - {'skin'}
    if names != set(GROWTH_NAMES):
        bad.append(f'growth families: elements lacks {sorted(set(GROWTH_NAMES) - names)}, growth.py lacks '
                   f'{sorted(names - set(GROWTH_NAMES))}')
    if not imported:
        return bad
    try:
        from ..forge import growth as GR
    except ImportError:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
        from eidoverse.bestiary.forge import growth as GR
    if FAMILY_ID != dict(skin=0, **GR.FAMILY_ID):
        bad.append('FAMILY_ID differs from growth.FAMILY_ID')
    near = lambda a, b, tol=6e-4: np.allclose(np.asarray(a, np.float64), np.asarray(b, np.float64), atol=tol)
    for f in GR.FAMILIES:
        g, r = GROWTH_FAMILIES.get(f), GR.RECIPES[f]
        if g is None:
            continue
        if r.get('flesh', 0.0) > 0.5:
            if g['albedo'] is not None:
                bad.append(f'{f}: the flesh family re-shades the skin (albedo None)')
        elif g['albedo'] is None or not near(g['albedo'], r['c0']):
            bad.append(f'{f}: albedo {g["albedo"]} vs growth.py c0 {r["c0"]}')
        for k, rk in (('metal', 'metal'), ('trans', 'sss')):
            if abs(g[k] - r[rk]) > 1e-9:
                bad.append(f'{f}: {k} {g[k]} vs growth.py {rk} {r[rk]}')
        if abs(g['rough'][1] - r['rough']) > 1e-9:
            bad.append(f'{f}: rough p50 {g["rough"][1]} vs growth.py {r["rough"]}')
        if g.get('f0') is not None and r['ior'] > 0.0 and abs(g['f0'] - ((r['ior'] - 1) / (r['ior'] + 1)) ** 2) > 6e-4:
            bad.append(f'{f}: f0 {g["f0"]} vs growth.py ior {r["ior"]}')
        em = g.get('emissive')
        if (em is None) != (r['emis'] == 0.0):
            bad.append(f'{f}: emissive {em} vs growth.py emis {r["emis"]}')
        elif em is not None and (abs(em[0] - r['emis']) > 1e-9 or r.get('glow') is None or not near(em[1], r['glow'])):
            bad.append(f'{f}: emissive {em[:2]} vs growth.py emis {r["emis"]}, glow {r.get("glow")}')
        ir = g.get('irid')
        if (ir is None) != (r['irid'] == 0.0):
            bad.append(f'{f}: irid {ir} vs growth.py irid {r["irid"]}')
        elif ir is not None and not near(ir, (r['irid'], r.get('film_ior', 0.0), r.get('irid_lo', 100.0),
                                              r.get('irid_hi', 400.0)), 1e-9):
            bad.append(f'{f}: irid {ir} vs growth.py ({r["irid"]}, film_ior {r.get("film_ior")}, {r.get("irid_lo")}, '
                       f'{r.get("irid_hi")})')
        co = g.get('coat')
        if co is not None and not (near(co['albedo'], r['c1']) and abs(co['rough'] - r['rough1']) < 1e-9 and
                                   abs(co['metal'] - r['metal1']) < 1e-9 and abs(co['cover'] - r['layer_amt']) < 1e-9):
            bad.append(f'{f}: coat {co} vs growth.py c1 {r["c1"]}, rough1 {r["rough1"]}, metal1 {r["metal1"]}, '
                       f'layer_amt {r["layer_amt"]}')
    return bad


def place_scale(family, extent_m):
    """a growth family's piece size and height off the skin (m) for a creature of the given extent. study T measured
    absolute sizes on 1.9-5.5 m creatures (game readability). Their ratio to the creature's extent is 0.042-0.048 on
    the 3.3-5.5 m creatures and 0.137 on the 1.9 m mantis-wasp; it is the transferable number. For a radial creature,
    pass the BODY's extent (the octopus: mantle apex to oral face, ~0.31 m), since its arm span is not body.
    Returns ((p10, p50, p90) size, (p10, p50, p90) proud) in metres. [M] ratios, [D] the body-extent rule"""
    g = GROWTH_FAMILIES[family]
    pl = g.get('placement') or {}
    if 'creature_m' in pl:
        k = extent_m / pl['creature_m']
        return tuple(s * k for s in pl['size_m']), tuple(s * k for s in pl['proud_m'])
    return tuple(s * extent_m for s in pl.get('size_rel', (0, 0, 0))), \
        tuple(s * extent_m for s in pl.get('proud_rel', (0, 0, 0)))


# --------------------------------------------------------------------------------------------- surface layers
# Runtime surface overlays (remix.js draws them; the forge bakes the ones that change relief). Coverage w is driven by
# the ORM's AO (1 = open) and the world-space normal's y, broken up by the display mottle (structure places, noise only
# shapes the edge: craft guide 10.14). The overlay sets albedo, roughness and metalness by w. [S]/[M] REF §1 and R11;
# [D] the others. The rust and verdigris elements' metals and coats ARE their growth families' (one source:
# forge/growth.py's rows through the summaries above, which check_growth_sync(imported=True) holds to them)
_RUST, _VERDIGRIS = GROWTH_FAMILIES['rust'], GROWTH_FAMILIES['verdigris']
SURFACES = {
    'frost_exposed': dict(
        coverage='amount * smoothstep(0.3, 1.0, ao) * (0.55 + 0.15 * ny)', albedo=(0.46, 0.72, 0.83),
        rough_add=0.10, metal_mul=0.5, fuzz=1.0, amount=(0.3, 0.6),
        src='[S] the study-T runtime frost on exposed surface (its creature skin material, custom primitive data 25) and '
            '[M] mantis-wasp Cold; frost #B5DDEB, w 0.3-0.6 (REF R11)'),
    'frost_recess': dict(
        coverage='amount * (0.75 * (1 - smoothstep(0.4, 0.95, ao)) + 0.2)', albedo=(0.46, 0.72, 0.83),
        rough_add=-0.15, spec_mul=0.5, fuzz=1.0, glow=0.5, amount=(0.3, 0.6),
        src='[M] ice-crab: frost fills recesses, glazed (rough -0.04 to -0.15, spec x0.5), emissive in the frost'),
    'char': dict(
        coverage='amount * smoothstep(0.55, 0.95, ao) * (0.4 + 0.6 * smoothstep(-0.2, 0.8, ny))',
        albedo=(0.035, 0.030, 0.028), rough_to=0.85, ember='(1 - smoothstep(0.2, 0.55, ao)) * amount',
        amount=(0.3, 0.6),
        src='[D] scorched exposed tops (charcoal reflectance ~0.03-0.05), embers glowing in the cracks'),
    'rust': dict(
        coverage='amount * ((1 - smoothstep(0.45, 0.95, ao)) * 0.65 + 0.35 * smoothstep(0.1, 0.9, ny))',
        albedo=_RUST['coat']['albedo'], rough_to=_RUST['coat']['rough'], metal_to=_RUST['coat']['metal'],
        amount=(0.4, 0.7),
        src='[D] iron oxide blooming where water sits: crevices and upward faces; the oxide is the rust growth '
            'family\'s coat (growth.py c1 sRGB8 (124 58 36), rough1 .90 [I]; was sRGB8 (150 72 38), rough .85 [D])'),
    'patina': dict(
        coverage='amount * ((1 - smoothstep(0.35, 0.9, ao)) * 0.85 + 0.15 * smoothstep(0.3, 0.9, ny))',
        albedo=_VERDIGRIS['coat']['albedo'], rough_to=_VERDIGRIS['coat']['rough'],
        metal_to=_VERDIGRIS['coat']['metal'], amount=(0.4, 0.8),
        src='[D] verdigris gathering in cavities; the patina is the verdigris growth family\'s coat (growth.py c1 '
            '#43B3AE, rough1 .85 [I]; was (.056 .451 .423), the same colour to three places, rough .90 [D])'),
    'pustules': dict(
        coverage='amount * ramp(cells, 1 - 0.15 * amount, 1 - 0.15 * amount + 0.004)',
        albedo=(0.70, 0.80, 0.18), rough_to=0.08, glow=0.6, amount=(0.3, 0.8),
        src='[D] glossy spore pustules on a share of the patch cells (masks.A)'),
    'rim_arc': dict(
        coverage='0 (emissive only)', rim_power=4.0, flicker_hz=9.0, amount=(0.3, 1.0),
        src='[D] an ionised fresnel rim flickering (electric)'),
}


# --------------------------------------------------------------------------------------------- the elements
def _glow(colour, L, bands=2.0, rate=0.2, fade=0.2, phase='cells', travel_k=40.0, src=''):
    """the glow: colour (linear, any scale), its luminance L (study-G-equalised; runtime radiance = L x GLOW_SCALE),
    the creature skin material's pulse saturate(0.5 + 0.5 sin(2 pi (bands * phase + rate * t)) + fade) (REF R10: temporal
    frequency = Banding x Freq, e.g. the salamander creature 2 x 0.05 = 0.1 Hz, Canid 3 x 0.1 = 0.3 Hz), phase from the patch
    cells (masks.A: a cellular phase field like the study-T mask channel) or travelling outward (the anatomical distance x travel_k,
    rad/m, like the passing clouds)"""
    return dict(colour=tuple(float(x) for x in colour), L=float(L), bands=float(bands), rate=float(rate),
                fade=float(fade), phase=phase, travel_k=float(travel_k), src=src)


ELEMENTS = {
    # ---------------------------------------------------------------- study G's eight (its element enum order, study G §4.4)
    'normal': dict(
        label='Normal', study_g_index=0, pool='study_g', zones={}, thin=None, wet=None, fuzz=None, glow=None, surface=None,
        growth=None, irid=None, light=None, ui='#B8B0A0', beats=(), loses_to=(),
        src='[S] row None: the creature keeps its own material (the realistic base)'),
    'fire': dict(
        label='Fire', study_g_index=1, pool='study_g',
        zones=dict(
            primary=Z(None, 0.0, sat=0.30, val=0.80, rough=0.12, src='[S] shell goes neutral grey (.48); [D] scorched'),
            soft=Z((1.00, 0.30, 0.03), 0.85, sat=1.15, val=1.10,
                   src='[S] hue between the bug-dog creature colour 2A (1 .76 0) and the night creature (1 .42 0)'),
            accent=Z((1.00, 0.55, 0.10), 0.90),
            pattern=Z((0.45, 0.04, 0.01), 0.80, val=0.85, src='[S] the bug-dog creature colour 2B (.44 .02 0), the ramp\'s dark end')),
        thin=dict(colour=(1.00, 0.32, 0.06), w=0.9), wet=0.35, fuzz=0.6,
        glow=_glow((1.0, 0.14, 0.0), STUDY_G_GLOW_L['fire'], bands=2, rate=0.35, fade=0.25, phase='cells',
                   src='[S] bug-dog creature fire emissive (1 .14 0) x2'),
        surface=dict(kind='char', amount=0.45), growth=dict(family='obsidian'), irid=None,
        light=dict(colour=(1.0, 0.45, 0.12), intensity=1.5), ui='#FF6A1A', beats=('ice', 'moonlight'),
        loses_to=('electric',), src='study G fire family; PBR values [D] inside the REF envelope'),
    'ice': dict(
        label='Ice', study_g_index=2, pool='study_g',
        zones=dict(
            primary=Z((0.46, 0.72, 0.83), 0.85, sat=0.50, val=2.40, rough=-0.06,
                      src='[S] the shell goes white for Ice (colour 1A 1 1 1); [M] frost hue #B5DDEB; the octopus '
                          'aboral L 0.118 -> 0.28, a pale cool grey (the frost surface whitens it further)'),
            soft=Z((0.15, 0.55, 0.65), 0.80, val=1.05,
                   src='[S] hue between the bug-dog creature colour 2A (.19 .43 .38) and the night creature (.37 .79 1)'),
            accent=Z((0.55, 0.85, 0.95), 0.90),
            pattern=Z((0.06, 0.08, 0.24), 0.80, val=0.85, src='[S] colour 1B navy (.03 .02 .06), the night creature (.10 .10 .24)')),
        thin=dict(colour=(0.35, 0.75, 0.95), w=0.9), wet=1.0, fuzz=1.0,
        glow=_glow((0.0, 0.90, 1.0), STUDY_G_GLOW_L['ice'], bands=1, rate=0.08, fade=0.40, phase='travel',
                   src='[S] bug-dog creature ice emissive (0 .90 1) x1'),
        surface=dict(kind='frost_exposed', amount=0.55), growth=dict(family='ice'), irid=None,
        light=dict(colour=(0.55, 0.85, 1.0), intensity=1.2), ui='#7FD8F0', beats=('poison',),
        loses_to=('fire', 'moonlight'), src='study G ice family; [M] study T ice for the surface and growth'),
    'electric': dict(
        label='Electric', study_g_index=3, pool='study_g',
        zones=dict(
            primary=Z((0.25, 0.32, 0.34), 0.40, sat=0.25, val=0.85, src='[S] shell grey .44; the night creature slate'),
            soft=Z((1.00, 0.92, 0.08), 0.80, val=1.15, src='[S] the bug-dog creature colour 2A (1 .96 0)'),
            accent=Z((0.60, 0.80, 1.00), 0.90),
            pattern=Z((0.08, 0.15, 0.70), 0.80, val=0.90)),
        thin=dict(colour=(0.65, 0.80, 1.0), w=0.8), wet=0.8, fuzz=1.0,
        glow=_glow((0.0, 0.06, 1.0), STUDY_G_GLOW_L['electric'], bands=4, rate=2.5, fade=-0.2, phase='cells',
                   src='[S] bug-dog creature electric emissive (0 .06 1) x5; [D] a fast crackle, off part of the cycle'),
        surface=dict(kind='rim_arc', amount=0.6), growth=dict(family='quartz_arc'), irid=None,
        light=dict(colour=(0.55, 0.65, 1.0), intensity=1.4), ui='#5A8CFF', beats=('fire',), loses_to=('poison',),
        src='study G electric family'),
    'poison': dict(
        label='Poison', study_g_index=4, pool='study_g',
        zones=dict(
            primary=Z((0.55, 0.85, 0.05), 0.75, sat=1.10, val=1.60,
                      src='[S] Poison colours the shell (the bug-dog creature colour 1A .85 1 .07), the one exception; [D] brighter '
                          '(aposematic)'),
            soft=Z((0.85, 0.80, 0.45), 0.60, sat=0.80, val=1.15, src='[S] Color2 white to cream (1 .94 .52)'),
            accent=Z((0.30, 1.00, 0.05), 0.90),
            pattern=Z((0.015, 0.03, 0.005), 0.90, val=0.55, rough=-0.03, src='[D] warning bands, near black')),
        thin=dict(colour=(0.55, 0.95, 0.25), w=0.8), wet=1.0, fuzz=1.0,
        glow=_glow((0.26, 1.0, 0.0), STUDY_G_GLOW_L['poison'], bands=2, rate=0.5, fade=0.1, phase='cells',
                   src='[S] bug-dog creature poison emissive (.26 1 0) x1'),
        surface=dict(kind='pustules', amount=0.5), growth=dict(family='spore'), irid=None,
        light=dict(colour=(0.45, 1.0, 0.2), intensity=1.2), ui='#8CE01E', beats=('electric',), loses_to=('ice',),
        src='study G poison family'),
    'player_soul': dict(
        label='Player Soul', study_g_index=5, pool='special', zones={}, thin=None, wet=None, fuzz=None,
        glow=_glow((0.55, 0.85, 1.0), 0.50, bands=1, rate=0.1, fade=0.3, phase='travel',
                   src='[D] study G ships None here (keeps the base); a spectral glow so FX and light have a colour'),
        surface=None, growth=None, irid=None, light=dict(colour=(0.7, 0.9, 1.0), intensity=1.0), ui='#BFE6FF',
        beats=('dark_gaia',), loses_to=('dark_gaia',),
        src='[S] None in every study G table; excluded from random worlds unless a planet lists it'),
    'moonlight': dict(
        label='Moonlight', study_g_index=6, pool='special',
        zones=dict(
            primary=Z((0.31, 0.31, 0.36), 0.30, sat=0.25, val=0.95, src='[S] shell grey .31'),
            soft=Z((0.48, 0.47, 1.00), 0.80, val=1.10, src='[S] the moon variant colour 2A (.48 .47 1)'),
            accent=Z((0.81, 0.54, 1.00), 0.90),
            pattern=Z((0.68, 0.45, 0.90), 0.70, src='[S] the moon variant colour 2B (.68 .45 .90)')),
        thin=dict(colour=(0.70, 0.62, 1.0), w=0.8), wet=1.0, fuzz=1.0,
        glow=_glow((0.81, 0.54, 1.0), STUDY_G_GLOW_L['moonlight'], bands=1, rate=0.05, fade=0.45, phase='travel',
                   src='[S] _Moon emissive (.81 .54 1) x2'),
        surface=None, growth=dict(family='moonstone'), irid=dict(zone='accent', strength=0.5, ior=1.5,
                                                                  thickness=(250.0, 420.0)),
        light=dict(colour=(0.75, 0.70, 1.0), intensity=1.1), ui='#B79CFF', beats=('ice',), loses_to=('fire',),
        src='study G moonlight (authored once on the bug-dog creature moon variant, inherited by the night creature)'),
    'dark_gaia': dict(
        label='Dark Gaia', study_g_index=7, pool='special',
        zones=dict(
            primary=Z((0.10, 0.04, 0.12), 0.50, sat=0.60, val=0.45),
            soft=Z((0.45, 0.02, 0.10), 0.80, val=0.80),
            accent=Z((0.90, 0.10, 0.35), 0.90),
            pattern=Z((0.02, 0.00, 0.03), 0.90, val=0.50)),
        thin=dict(colour=(0.80, 0.05, 0.25), w=0.8), wet=0.8, fuzz=1.0,
        glow=_glow((0.90, 0.05, 0.40), 0.65, bands=3, rate=0.15, fade=0.0, phase='cells'),
        surface=None, growth=dict(family='void_glass'), irid=None,
        light=dict(colour=(0.9, 0.2, 0.5), intensity=1.0), ui='#9E1F5C', beats=('player_soul',),
        loses_to=('player_soul',),
        src='[S] the bug-dog creature table has 7 rows, so Dark Gaia keeps the base there; this look is [D]'),
    # ---------------------------------------------------------------- Claude's Creatures (DESIGN.md growth families)
    'rust': dict(
        label='Rusted Iron', study_g_index=None, pool='remix',
        zones=dict(
            primary=Z(_RUST['albedo'], 1.0, absolute=1.0, detail=0.35, rough_to=_RUST['rough'][1], rough_w=1.0,
                      metal=_RUST['metal'],
                      src='the rust growth family\'s iron: growth.py c0, physicallybased.info Iron [S], rough .40 [I], '
                          'metal 1 (was RTR4 (.562 .565 .578) [P], rough .45, metal .90); the painted pattern survives '
                          'as +-25 % F0 variation (detail 0.35)'),
            soft=Z((0.30, 0.09, 0.04), 0.55, sat=0.90, val=0.90, src='[D] soft tissue stained with oxide'),
            accent=Z(_RUST['albedo'], 1.0, absolute=1.0, detail=0.2, rough_to=0.30, rough_w=1.0, metal=_RUST['metal'],
                     src='[D] worn bright iron on the rims: the family\'s iron F0 [S], polished (rough .30) (was '
                         '(.60 .60 .62) [D])'),
            pattern=Z((0.12, 0.035, 0.015), 0.70, val=0.9)),
        thin=dict(colour=(0.60, 0.25, 0.10), w=0.7), wet=0.0, fuzz=0.0, glow=None,
        surface=dict(kind='rust', amount=0.55), growth=dict(family='rust'), irid=None, light=None,
        ui='#B5532A', beats=(), loses_to=(), src='DESIGN.md RUST-iron spines; [D]'),
    'verdigris': dict(
        label='Verdigris', study_g_index=None, pool='remix',
        zones=dict(
            primary=Z(_VERDIGRIS['albedo'], 1.0, absolute=1.0, detail=0.30, rough_to=_VERDIGRIS['rough'][1],
                      rough_w=1.0, metal=_VERDIGRIS['metal'],
                      src='the verdigris growth family\'s copper: growth.py c0, physicallybased.info Copper [S], rough '
                          '.30 [I], metal 1 (was RTR4 (.955 .638 .538) [P], rough .35, metal .95)'),
            soft=Z((0.20, 0.55, 0.45), 0.50, src='[D] patina-stained soft tissue'),
            accent=Z(_VERDIGRIS['albedo'], 1.0, absolute=1.0, detail=0.2, rough_to=0.22, rough_w=1.0,
                     metal=_VERDIGRIS['metal'],
                     src='[D] worn bright copper on the rims: the family\'s copper F0 [S], polished (rough .22) (was '
                         '(.96 .64 .54))'),
            pattern=Z((0.03, 0.20, 0.16), 0.70)),
        thin=dict(colour=(0.30, 0.70, 0.60), w=0.6), wet=0.0, fuzz=0.0, glow=None,
        surface=dict(kind='patina', amount=0.6), growth=dict(family='verdigris'), irid=None, light=None,
        ui='#43B3AE', beats=(), loses_to=(), src='DESIGN.md OXIDE / VERDIGRIS; [D]'),
    'crystal': dict(
        label='Crystal', study_g_index=None, pool='remix',
        zones=dict(
            primary=Z(None, 0.0, sat=0.85, val=0.95),
            accent=Z((0.80, 0.80, 0.85), 0.50)),
        thin=None, wet=1.0, fuzz=1.0, glow=None, surface=None,
        growth=dict(family='metal_chrome'), irid=None, light=None, ui='#C8CCD8',
        tiers=dict(small=('zones',), medium=('zones', 'growth'), large=('zones', 'growth'),
                   elite=('zones', 'growth')),
        beats=(), loses_to=(),
        src='[S] the study-T crystal squid creature: "the base skin is UNCHANGED; the element is only an added growth mesh" '
            '(REF sec. 3, 7c); growth from the medium tier because the growth IS this element'),
    'bismuth': dict(
        label='Bismuth', study_g_index=None, pool='remix',
        zones=dict(primary=Z(None, 0.0, sat=0.80, val=0.95), accent=Z((0.70, 0.55, 0.85), 0.6)),
        thin=None, wet=1.0, fuzz=1.0, glow=None, surface=None, growth=dict(family='bismuth'),
        irid=dict(zone='accent', strength=0.7, ior=2.0, thickness=(180.0, 460.0)), light=None, ui='#C77DFF',
        tiers=dict(small=('zones',), medium=('zones', 'growth'), large=('zones', 'growth'),
                   elite=('zones', 'growth')),
        beats=(), loses_to=(), src='DESIGN.md BISMUTH: stepped hoppers, thin-film iridescence at runtime; [D]'),
    'liquid_metal': dict(
        label='Liquid Metal', study_g_index=None, pool='remix',
        zones=dict(
            primary=Z((0.781, 0.780, 0.778), 1.0, absolute=1.0, detail=0.15, rough_to=0.04, rough_w=1.0, metal=1.0,
                      src='[P] mercury F0'),
            soft=Z((0.781, 0.780, 0.778), 1.0, absolute=0.9, detail=0.15, rough_to=0.06, rough_w=1.0, metal=1.0),
            accent=Z((0.80, 0.80, 0.80), 1.0, absolute=1.0, detail=0.0, rough_to=0.03, rough_w=1.0, metal=1.0),
            pattern=Z((0.62, 0.62, 0.62), 1.0, absolute=1.0, detail=0.1, rough_to=0.08, rough_w=1.0, metal=1.0)),
        thin=None, wet=1.0, fuzz=0.0, glow=None, surface=None, growth=dict(family='liquid_metal'), irid=None,
        light=None, ui='#D9D9DE', beats=(), loses_to=(),
        src='DESIGN.md LIQUID METAL: mirror-rough; the runtime flow needs a flow map (not built)'),
    'abyssal': dict(
        label='Abyssal', study_g_index=None, pool='remix',
        zones=dict(
            primary=Z((0.22, 0.015, 0.03), 0.75, val=0.55,
                      src='[D] deep-sea red-black (red light does not reach depth, so red pigment reads black)'),
            soft=Z((0.75, 0.62, 0.70), 0.40, sat=0.50, val=1.15, src='[D] gelatinous pale'),
            accent=Z((0.60, 0.85, 1.00), 0.70),
            pattern=Z((0.20, 0.01, 0.03), 0.80, val=0.45, src='[D] near-black wine bands')),
        thin=dict(colour=(0.25, 0.35, 0.95), w=0.9), wet=1.0, fuzz=1.0,
        glow=_glow((0.05, 0.55, 1.0), 0.80, bands=3, rate=0.3, fade=0.0, phase='cells',
                   src='[P] marine bioluminescence peaks near 470-490 nm (blue-cyan); [M] Canid banding 3'),
        # bestiary.js's procedural photophores (setDisplay glow): strength = the resting glow weight, colour linear,
        # scale cells per metre (45 = its default, ~2 cm cells), rate rad/s (its default 3.0 = 0.48 Hz); bestiary.js
        # places them: about a third of the cells, ventral (masks.G: counter-illumination)
        photophores=dict(strength=1.0, colour=(0.05, 0.60, 1.0), scale=45.0, rate=3.0),
        surface=None, growth=None, irid=None, light=dict(colour=(0.2, 0.6, 1.0), intensity=0.8), ui='#1C6BFF',
        beats=(), loses_to=(), src='DESIGN.md PHOTOPHORES (firefly squid, deep-sea fish); [D]'),
}

# --------------------------------------------------------------------------------------------- affixes
# study G's six affixes, their roll chances [S] (study G §4.1: 5 % foes, 1 % fauna, 5 % large fauna; one affix) and the
# Bestiary's runtime look for each (DESIGN.md Remix: affixes). 'shader' effects remix.js draws; 'fx' ones need the
# FX contract's sockets (fx_affix_0..2) and a particle system, which do not exist yet.
AFFIX_CHANCE = dict(foe=0.05, fauna=0.01, fauna_large=0.05)
AFFIXES = {
    'dangerous': dict(study_g='DoubleDamage', kind='shader', effect='rim_pulse', colour=(1.0, 0.05, 0.02), L=0.8,
                      rate=1.2, power=3.0, needs_fx=False),
    'explosive': dict(study_g='ExplosiveEnemy', kind='shader+fx', effect='ticking_pustules', colour=(1.0, 0.35, 0.05),
                      L=1.0, density=0.05, rate=2.0, needs_fx=True, fx='end burst at fx_affix_*'),
    'swift': dict(study_g='DoubleSpeed', kind='fx', effect='speed_streaks', needs_fx=True, fx='streaks at fx_affix_*'),
    'experienced': dict(study_g='DoubleEXP', kind='shader', effect='sparkle', colour=(1.0, 0.782, 0.344), L=1.5,
                        density=0.015, rate=6.0, needs_fx=False),
    'wealthy': dict(study_g='DoubleLoot', kind='shader', effect='glint', colour=(1.0, 0.95, 0.80), L=1.2, period=3.0,
                    width=0.04, needs_fx=False),
    'stealthy': dict(study_g='Invis', kind='shader', effect='cloak', opacity=0.25, edge=0.9, needs_fx=False,
                     note='study G: the only affix that also swaps a MIC; transparent sorting with SSS is unverified'),
}


# --------------------------------------------------------------------------------------------- API
def element(name):
    if name not in ELEMENTS:
        raise KeyError(f'unknown element {name!r} (have: {", ".join(ELEMENTS)})')
    return copy.deepcopy(ELEMENTS[name])


def layers_for(name, tier):
    """the stack layers this element shows at this tier (its own tier override, else TIER_LAYERS)"""
    e = ELEMENTS[name]
    t = (e.get('tiers') or TIER_LAYERS)[tier]
    present = dict(zones=bool(e['zones']) or e['thin'] is not None, glow=e['glow'] is not None,
                   surface=e['surface'] is not None, growth=e['growth'] is not None)
    return tuple(k for k in t if present.get(k, False))


def glow_gain(glow):
    """the emissive multiplier for the glow colour: L / lum(colour) x GLOW_SCALE (so every glow lands on its luminance)"""
    return glow['L'] / max(float(lum(glow['colour'])), 1e-4) * GLOW_SCALE


def runtime_block(name, tier='small'):
    """the element as remix.js consumes it: zones per role (identity where the element leaves a role alone), the
    thin-tissue tint, wet and fuzz, the glow with its gain, the surface layer, iridescence, photophores, light; only
    the layers this tier shows"""
    e = element(name)
    lay = layers_for(name, tier)
    out = dict(name=name, label=e['label'], tier=tier, layers=list(lay), zones={}, thin=None, wet=e['wet'],
               fuzz=e['fuzz'], glow=None, surface=None, irid=e.get('irid'), photophores=e.get('photophores'),
               growth=e['growth'] if 'growth' in lay else None, light=e['light'])
    if 'zones' in lay:
        for role in ROLES:
            z = e['zones'].get(role)
            if z is not None and not is_identity(z):
                out['zones'][role] = {k: v for k, v in z.items() if k != 'src'}
        out['thin'] = e['thin']
    if 'glow' in lay:
        g = dict(e['glow'])
        g.pop('src', None)
        g['gain'] = glow_gain(e['glow'])
        out['glow'] = g
    if 'surface' in lay:
        s = dict(e['surface'])
        s.update({k: v for k, v in SURFACES[s['kind']].items() if k not in ('src', 'coverage', 'amount')})
        out['surface'] = s
    return out


def check_table():
    """the table's own consistency: every number in range, targets inside the gamut, glows equalised, the bane wheel
    symmetric, growth families known. Returns a list of problem strings (empty = consistent)"""
    bad = []
    names = set(ELEMENTS)
    idx = sorted(e['study_g_index'] for e in ELEMENTS.values() if e['study_g_index'] is not None)
    if idx != list(range(8)):
        bad.append(f'study G indices must be 0..7 once each (its element enum order): {idx}')
    for n, e in ELEMENTS.items():
        for role, z in e['zones'].items():
            if role not in ROLES:
                bad.append(f'{n}: unknown zone role {role!r}')
            if z['target'] is not None and (min(z['target']) < 0.0 or max(z['target']) > 1.0):
                bad.append(f'{n}.{role}: target outside [0, 1]: {z["target"]}')
            if z['target'] is None and z['w'] > 0.0:
                bad.append(f'{n}.{role}: w {z["w"]} without a target moves nothing (zone_remap and remix.js both treat a '
                           'target-less zone as no hue move): drop w or give a target')
            if not (0.0 <= z['w'] <= 1.0 and 0.0 <= z['absolute'] <= 1.0 and 0.0 <= z['detail'] <= 1.0):
                bad.append(f'{n}.{role}: w / absolute / detail outside [0, 1]')
            if z['metal'] is not None and z['absolute'] < 0.5:
                bad.append(f'{n}.{role}: metal set without absolute mode (a metal cannot keep a skin\'s L)')
            if z['metal'] is not None and z['metal'] > 0.5 and float(lum(z['target'])) < 0.30:
                bad.append(f'{n}.{role}: metal F0 L {float(lum(z["target"])):.2f} < 0.30 is not a metal')
        if e['glow'] is not None:
            g = e['glow']
            if lum(g['colour']) <= 0.0:
                bad.append(f'{n}: glow colour black')
            if not 0.3 <= g['L'] <= 1.5:
                bad.append(f'{n}: glow L {g["L"]} outside the study-G-equalised 0.3-1.5')
            if g['phase'] not in ('cells', 'travel'):
                bad.append(f'{n}: glow phase {g["phase"]!r}')
        if e['surface'] is not None and e['surface']['kind'] not in SURFACES:
            bad.append(f'{n}: unknown surface {e["surface"]["kind"]!r}')
        if e['growth'] is not None and e['growth']['family'] not in GROWTH_FAMILIES:
            bad.append(f'{n}: unknown growth family {e["growth"]["family"]!r}')
        for other in e['beats']:
            if other not in names:
                bad.append(f'{n}: beats unknown {other!r}')
            elif n not in ELEMENTS[other]['loses_to']:
                bad.append(f'bane wheel: {n} beats {other} but {other} does not lose to {n}')
        if e['irid'] is not None and e['irid']['zone'] not in ROLES:
            bad.append(f'{n}: iridescence zone {e["irid"]["zone"]!r}')
    ids = sorted(g['id'] for g in GROWTH_FAMILIES.values())
    if ids != list(range(len(ids))):
        bad.append(f'growth family ids must be 0..n-1: {ids}')
    bad += check_growth_sync()                   # the names against growth.py's (the one id table)
    for f, g in GROWTH_FAMILIES.items():
        if g.get('albedo') is not None and g['kind'] != 'metal' and float(lum(g['albedo'])) > 0.70:
            bad.append(f'growth {f}: albedo L {float(lum(g["albedo"])):.2f} above the 0.69 ice ceiling (REF sec. 8)')
        if g['kind'] == 'metal' and g.get('metal', 1.0) > 0.8 and float(lum(g['albedo'])) < 0.2 and f != 'metal_crystal':
            bad.append(f'growth {f}: a metal with F0 L {float(lum(g["albedo"])):.2f}')
    for a, d in AFFIXES.items():
        if d['kind'] not in ('shader', 'fx', 'shader+fx'):
            bad.append(f'affix {a}: kind {d["kind"]!r}')
    return bad


if __name__ == '__main__':
    import sys
    probs = check_table()
    print(f'[elements] {len(ELEMENTS)} elements, {len(GROWTH_FAMILIES)} growth families, {len(SURFACES)} surfaces, '
          f'{len(AFFIXES)} affixes; table checks: {"ok" if not probs else probs}')
    if '--import' in sys.argv:                   # the summary numbers against growth.RECIPES (imports warp)
        sync = check_growth_sync(imported=True)
        print(f'[elements] growth families vs forge/growth.py RECIPES: {"in sync" if not sync else sync}')
    for n, e in ELEMENTS.items():
        g = e['glow']
        gl = f'glow {hexcode(g["colour"])} L {g["L"]:.2f} gain {glow_gain(g):.2f}' if g else 'no glow'
        print(f'  {n:13s} study_g {str(e["study_g_index"]):4s} layers small {layers_for(n, "small")} large '
              f'{layers_for(n, "large")}; {gl}')
    # the remap on the octopus's measured zone medians (work/bestiary/remix_scratch/zone_stats.py, head set)
    oct_ = dict(primary=((0.292, 0.074, 0.037), 0.118), soft=((0.571, 0.242, 0.184), 0.308),
                accent=((0.776, 0.617, 0.515), 0.644), pattern=((0.235, 0.060, 0.031), 0.095))
    print('  octopus zone medians through each element (linear L before -> after):')
    for n in ('fire', 'ice', 'electric', 'poison', 'moonlight', 'rust', 'liquid_metal', 'abyssal'):
        row = []
        for role, (c, lref) in oct_.items():
            z = ELEMENTS[n]['zones'].get(role)
            o = zone_remap(np.array(c), z, lref) if z is not None else np.array(c)
            row.append(f'{role} {float(lum(c)):.3f}->{float(lum(o)):.3f} {hexcode(o)}')
        print(f'    {n:12s} ' + '; '.join(row))
