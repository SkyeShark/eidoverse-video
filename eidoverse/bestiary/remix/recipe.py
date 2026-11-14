"""REMIX RECIPES: Claude's Creatures as plain data (DESIGN.md "Claude's Creatures"; a study note §8).

A creature is a RECIPE: JSON-able data. A remix is an edit or a merge of recipes, and every creature rebuilds from its
recipe. The sections, and which tier of the pipeline consumes each (DESIGN.md "two speeds of remix"):

  OFFLINE (the forge, minutes: anything that changes the surface)
    base, family   the realistic base species preset (the vocabulary) and its body-plan family generator
    spec           overrides of the base species' generator proportions (octopus: forge/species/octopus.py SPEC)
    sculpt         ordered LAYER recipes in anatomical coordinates: kind, sites, mask, density, size, seed, material id
    skin           the skin recipe: material class, patch network, paint passes, offline palette, baked overlay
    parts          {socket: part}: study G slot rows with level bands, each naming the material slot it renders with
    cyborg         the CYBORG mutation (research/CYBORG_PLAN.md §6.1): kind-keyed part tables and limb replacements,
                   seated by remix/slots.py's closed table on the manifest's TYPED sockets and chains (resolve_cyborg);
                   its glow and affixes are runtime
  RUNTIME (the engine, instant, per instance: runtime/remix.js)
    palette        zone recolour from the mask packs (primary / soft / accent / pattern), fixed pigment kept
    display        the colour-change recipe: mood, mood cycle, passing clouds, iridophores, photophores, leucophores
    element        one row of the global element table (elements.py): zones, glow, surface, growth by tier
    affixes        study G's six affixes (shader looks; the FX ones need the FX contract's sockets)
    accessories    [{item, socket | bone, fit}]: hats, glasses, ties, seated by the socket's fit data
    bones          proportion tweaks through joint scales
  and seed, level, tier, role, lineage, notes.

OPERATORS make remixes: make(), merge(), normalise(), crossbreed(), swap_layer(), add_layer(), remove_layer(),
growth(), roll_element(), roll_affixes(), resolve_auto(), resolve_parts() (study G slot tables by level band and weight),
mutate(). resolve_runtime() turns a recipe into the block runtime/remix.js applies; apply_jitter() is the per-instance
variation, twinned in remix.js. Every random choice goes through roll(seed, key), the same bits as runtime/remix.js
(FNV-1a on the key, then bestiary.js's lowbias32 mix), so a recipe resolves identically in Python and in the engine.
recipe_hash(r, 'offline' | 'runtime') says which edits need a forge rebuild.

THE BUILD VALIDATOR (validate(recipe, manifest)) checks a recipe against a BUILT creature's manifest and reports EVERY
problem, because study G shipped without one (study G §4.6: parts on sockets their meshes lack, class defaults naming
bones that do not exist, three part rows whose texture family does not match their UVs, left/right sockets swapped,
a creature-hat path that never shipped). Severities: 'error' (wrong data: the build must not run), 'missing' (needs
something the forge or the library does not have yet), 'warning' (builds, but suspicious). Codes:
  recipe.*     schema: unknown base/family/tier/role, unknown keys, bad seed or level
  spec.*       unknown or unsupported generator keys, values outside the species' ranges, keys coupled to ML (the
               neck), the end taper's slope (t18's terraces), ML moving parts the block-out keeps absolute
  palette.*    unknown roles, colours that are not sRGB #rrggbb, strengths outside 0-1
  sculpt.*     unknown kinds, locked layers removed, duplicate ids, unknown material ids, sites or regions the family
               lacks, two adding layers on one site set that were not planned together (cosite)
  skin.*       paint keys the species' skin pass does not read, a skin class foreign to the base
  element.*    unknown element, policy or affix
  display.*    unknown moods or weights, malformed mood cycles (a mood must last > 0 s: a zero-length cycle is NaN in
               remix.js), photophore keys bestiary.js does not drive, procedural displays evaluated in posed space
               (display.posed_space)
  manifest.*   the manifest itself: species/family mismatch, sockets on missing bones, _L/_R on the wrong side
  socket.*     a socket the recipe uses does not exist
  bone.*       a bone the recipe names does not exist (bone ops, part 'replaces', accessory 'bone'); scales that
               compound down a chain or shear it (a non-uniform scale on a joint with children)
  part.*       unknown or unbuilt parts, missing material slots, the part's UV family against its material slot's
               (declared, and MEASURED as in study G: UV-raster precision and recall)
  accessory.*  unknown items, no seat, no fit data for the item's archetype, malformed fits, out-of-range scales,
               lens yaw beyond the item's hinge, two items of one archetype on one seat. Fit data is read from the
               socket's extras (fit[archetype]) or from a seat_<archetype> child node (the accessories fit system,
               work/bestiary/patches/accessories_fit.md: hat seat tables convert; glasses rig fits do not)
  packs.*      the runtime layers need the masks / display packs on every skin material
  fx.*         affixes that need the FX contract's sockets
  budget.*     triangles over DESIGN.md's budget (the 'hero' tier: 150,000, the lead 10-21): the recipe's tier, or the
               base species' own budget tier where it has one (the octopus: hero, the lead's C0b call)
  cyborg.*     the slot rule (remix/slots.py): unknown names, a row whose part does not fit its kind, interfaces,
               untyped sockets, typed seats and validated entries, cuts, requires, sides, Skye's never-list, G5's hat
               probe, a seat shared with any accessory (its seat group, the sockets an enclosing item encloses), a
               covering layer left on flesh a part replaces or covers (cyborg.covered, C0b)
  manifest.slot* / seat_kind / chain*   the manifest's typing: kinds on their base's joints, seats under their kinds,
               every socket's frame and its interface's dims (manifest.slot_frame, manifest.slot_dims: C0b)
  needs.*      forge capabilities the recipe needs that are not built (FORGE_CAPS)

    r = make('octopus', name='crystal_octopus', seed=7, element='crystal', tier='large')
    r = swap_layer(r, 'head_papillae', growth('metal_chrome'))
    man = manifest_from_glb('work/bestiary/octopus/octopus.glb')
    print(report(validate(r, man)))
    block = resolve_runtime(r, man)            # the JSON runtime/remix.js applies

Self-test (CPU, fake manifests):      python eidoverse/bestiary/remix/recipe.py
Against the shipped octopus glb:      python eidoverse/bestiary/remix/recipe.py --glb [path]
Parity vectors for remix.js:          python eidoverse/bestiary/remix/recipe.py --vectors
Fallback copies vs the forge:         python eidoverse/bestiary/remix/recipe.py --sync [--import]
"""
import copy
import hashlib
import json
import math
import os
import re
import sys

import numpy as np

if __package__ in (None, ''):
    # run as a script (the self-test): make the repo root importable
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
    from eidoverse.bestiary.remix import elements as EL
    from eidoverse.bestiary.remix import slots as SL
else:
    from . import elements as EL
    from . import slots as SL

RECIPE_VERSION = 1
FAMILIES = ('radial', 'limbed', 'axial', 'arthropod', 'mollusc', 'hominid')     # hominid: HUMAN H4 (HUMAN_PLAN §6.1)
# the HERO tier (the lead, 10-21): a budget class beside 'large' for showcase creatures (the octopus is 122,560
# triangles before any cyborg part). elements.py's tables read it as 'elite' (its stack, its affix roll, its growths)
TIERS = EL.TIERS + ('hero',)
TIER_AS = dict(hero='elite')


def el_tier(tier):
    """the tier elements.py's tables read for a recipe tier (hero reads as elite)"""
    return TIER_AS.get(tier, tier)


ROLES = ('fauna', 'foe')
SEVERITIES = ('error', 'missing', 'warning')
M32 = 0xFFFFFFFF
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


# ============================================================================================ deterministic rolls
def key_id(key):
    """FNV-1a 32 over the key's ASCII bytes (runtime/remix.js keyId: the same bits)"""
    h = 0x811C9DC5
    for b in str(key).encode('ascii'):
        h ^= b
        h = (h * 0x01000193) & M32
    return h


def hash01(i, seed):
    """bestiary.js's hash01 (lowbias32 over i and seed) to [0, 1), bit for bit"""
    x = ((int(i) * 0x9E3779B1) & M32) ^ ((int(seed) * 0x85EBCA77) & M32)
    x ^= x >> 16
    x = (x * 0x7FEB352D) & M32
    x ^= x >> 15
    x = (x * 0x846CA68B) & M32
    x ^= x >> 16
    return (x >> 8) / 16777216.0


def roll(seed, key, i=0):
    """a deterministic uniform in [0, 1) for (seed, key, i)"""
    return hash01((key_id(key) + int(i)) & M32, seed)


def pick_weighted(seed, key, weights):
    """a name from {name: weight} (insertion order matters: the JS twin walks the same order)"""
    items = [(k, float(w)) for k, w in weights.items() if float(w) > 0.0]
    total = sum(w for _, w in items)
    u = roll(seed, key) * total
    acc = 0.0
    for k, w in items:
        acc += w
        if u < acc:
            return k
    return items[-1][0]


def derive_seed(*parts):
    """a child seed from parent seeds or keys (31 bits, so JS's `seed | 0` keeps it positive)"""
    h = 0x811C9DC5
    for p in parts:
        h = (key_id(str(p)) ^ ((h * 0x01000193) & M32)) & M32
    return int(hash01(h, 0x5EED) * 2147483647.0)


def jitter_rgb(rgb, seed, key, hue_deg, val):
    """a linear colour rotated about the grey axis by +-hue_deg and scaled by 1 +- val, from (seed, key): the
    per-instance palette jitter (study G §8.4: "palette jitter within an element family"). remix.js jitterRGB twins
    it bit for bit up to float rounding"""
    u1 = roll(seed, key + '.h')
    u2 = roll(seed, key + '.v')
    a = math.radians((2.0 * u1 - 1.0) * hue_deg)
    k = 1.0 / math.sqrt(3.0)
    c, s = math.cos(a), math.sin(a)
    r, g, b = (float(x) for x in rgb)
    dot = k * (r + g + b)
    # Rodrigues about (1, 1, 1) / sqrt(3): v cos + (k x v) sin + k (k . v)(1 - cos)
    cx = k * (b - g)
    cy = k * (r - b)
    cz = k * (g - r)
    out = [r * c + cx * s + k * dot * (1 - c), g * c + cy * s + k * dot * (1 - c), b * c + cz * s + k * dot * (1 - c)]
    f = 1.0 + (2.0 * u2 - 1.0) * val
    return tuple(max(0.0, x * f) for x in out)


HEX_RE = re.compile(r'^#?[0-9a-fA-F]{6}$')


def hex_to_lin(h):
    """an sRGB '#rrggbb' to linear rgb; anything else raises (a 5-digit '#12345' used to parse to a wrong colour)"""
    if not isinstance(h, str) or not HEX_RE.match(h):
        raise ValueError(f'colour {h!r} is not an sRGB hex #rrggbb')
    h = h.lstrip('#')
    return EL.srgb8(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ============================================================================================ species presets
# The realistic bases. The octopus's SPEC, PATCH and SKIN_RECIPE are READ FROM THE FORGE SOURCES (ast, no import: the
# species modules import warp) at import time, so the recipe always speaks the generator's current keys; the copies
# below are the fallback when the sources cannot be read, and check_species_sync() reports how far they have drifted.
FORGE_SPECIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'forge', 'species')


def dict_from_source(path, name):
    """a module-level `NAME = dict(...)` or `NAME = {...}` read from a Python source without importing it (literal
    values, and dict(...) calls of literals at any depth: v4's SPEC nests funnel=dict(...)); None if absent or not
    literal"""
    import ast

    def lit(v):
        if isinstance(v, ast.Call) and getattr(v.func, 'id', None) == 'dict' and not v.args:
            return {kw.arg: lit(kw.value) for kw in v.keywords}
        return ast.literal_eval(v)
    try:
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return dict(lit(node.value))
    except (OSError, ValueError, SyntaxError, TypeError):
        return None
    return None


def _live(module, name, fallback):
    got = dict_from_source(os.path.join(FORGE_SPECIES, module), name)
    return (got, 'forge source') if got else (dict(fallback), 'mirror')


# the fallback copy of octopus.SPEC as of block-out v4 (10-21: the mantle lying back, the turrets standing clear of
# the head mass, the proud eyes, the funnel turned up on the left flank, the free margin, the webs by sector, the
# thicker arms standing on their suckers)
OCTOPUS_SPEC = dict(ML=0.20, crown_y=0.088, arm_len=0.82, arm_pair_len=(1.0, 1.0, 1.0, 1.0), arm_r0=0.026,
                    arm_tip_r=0.0011, sucker_d=0.0175, crown_r0=0.050, oral_disc=(0.085, 0.026, 0.085),
                    web_sector=(0.49, 0.76, 0.89, 0.78, 0.56), web_side=1.65, web_half=(0.0075, 0.0009),
                    web_reach=(1.80, 1.55, 1.55, 1.55, 1.80), web_wall=(3.0, 3.0, 3.0, 3.0, 3.0),   # (crown v5's webs)
                    web_fold=(0.40, 0.72, 0.0042),
                    arm_round=(0.016, 0.006, 0.090, 0.125, 0.0),   # (crown v6b: the arms' round union, the webs'
                    web_tent=(0.27, 0.27, 0.27, 0.27, 0.27),       # tent down to their margins, the body sweep's
                    body_bound=(0.46, 0.002),                      # distance bound behind the apex)
                    eye_r=0.0215, eye_theta=55.0, eye_x=0.018, eye_h=0.46, eyeball_r=0.0150, eye_ap=(50.0, 50.0),
                    eye_proud=0.0012, mantle_aspect=1.20, mantle_tilt=15.0, head_mass=(0.048, 0.040, 0.048, 0.014),
                    head_mass_at=(-1.10, 0.55),
                    taper_s0=0.90, taper_k=0.25, funnel=dict(r_exit=0.0125, r_tip=0.0080), funnel_lumen=0.50,
                    mantle_margin=dict(lip_r=0.0050, lip_h=0.0025, groove_r=0.0035, groove_d=0.0012),
                    mouth_open=(0.33, 0.21))
# the ranges a remix may move each key in [D]: anatomically plausible stretches (the live ranges in
# work/bestiary/research/BLOCKOUT_V4_SPEC.md where it measured them); the forge's cage and bake gates are the real test
# of any value (a spec change re-runs cage, UVs, plan, voxel high, bake and skin). From octopus.SPEC's own notes:
# funnel_lumen 0.72 read as a rigid exhaust pipe; the END TAPER failed both ways: begun early (taper_s0 0.88 at the old
# k 0.55) it pinched a waist under the eyes, steep (0.93 / 0.55) it made terraces and a ledge (t18), so its range is
# wide and the joint test is the slope (taper_slope below); taper_k must stay large enough to keep the sweep's end cap
# inside the oral disc. eye_h under ~0.40 buries the funnel in the arm bases (t24); mantle_tilt: live -10 to -24 deg.
# mouth_open: the opening's semi-axes in lip radii, the long axis lateral, matched to the beak's face (ORAL_REFERENCE
# §3, §7: 0.69 x 0.41 lip radii); the round 0.46 hole was too big; the beak is fitted to prog.mouth, so it follows.
# The nested funnel and mantle_margin dicts carry no range: a remix leaves them as the forge has them
OCTOPUS_SPEC_RANGES = dict(ML=(0.12, 0.32), crown_y=(0.06, 0.12), arm_len=(0.50, 1.20),
                           arm_pair_len=((0.70, 1.0),) * 4, arm_r0=(0.016, 0.034), arm_tip_r=(0.0008, 0.0020),
                           sucker_d=(0.010, 0.022),
                           crown_r0=(0.040, 0.065), oral_disc=((0.065, 0.10), (0.020, 0.032), (0.065, 0.10)),
                           web_sector=((0.35, 1.0),) * 5, web_side=(1.3, 2.4),
                           # web_half[0] to 9 mm: covers crown v5d's 7.5 (6.0 clipped it; v4 measured 8.4); crown v6b
                           # keeps v5d's webs and this range
                           web_half=((0.0030, 0.0090), (0.0006, 0.0013)),
                           # (crown v6b) the webs' tent: the least slope (rise per metre in from the margin) the sheet
                           # holds as it climbs from the margin toward the crown, and the fall of the strips beside the
                           # arms to their free edges, by sector; 0 is crown v5d's level sheet, 0.40 ~ 22 deg (the A / E
                           # webs already fall 31-36 deg from the crown); the margins' middle thirds stay where they are,
                           # their ends come down toward the arms. arm_round and body_bound carry none: a remix leaves
                           # them as the forge has them
                           web_tent=((0.0, 0.40),) * 5,
                           eye_r=(0.015, 0.028),
                           eye_theta=(45.0, 65.0), eye_x=(0.012, 0.030), eye_h=(0.40, 0.55),
                           eyeball_r=(0.011, 0.019), eye_ap=((40.0, 60.0), (40.0, 60.0)), eye_proud=(0.0, 0.002),
                           mantle_aspect=(1.0, 1.35), mantle_tilt=(8.0, 26.0),
                           head_mass=((0.040, 0.056), (0.035, 0.049), (0.040, 0.056), (0.010, 0.024)),
                           head_mass_at=((-1.25, -0.95), (0.40, 0.70)),
                           taper_s0=(0.86, 0.95), taper_k=(0.15, 0.40), funnel_lumen=(0.35, 0.65),
                           mouth_open=((0.22, 0.44), (0.14, 0.32)))
# keys whose components scale with another key: the head mass fills the head under the eyes, whose place and the
# mantle's section scale with ML (octopus.eye_level, collar, body_radius x ML / 0.20); the range is checked on
# value / (ML / forge ML)
OCTOPUS_SPEC_COUPLED = dict(head_mass=('ML', (0, 1, 2)))
# the end taper's steepest slope (radius per axis length) scales as taper_k / (1 - taper_s0): the smoothstep's peak is
# 1.5 k R / ((1 - s0) L), and R / L is fixed by the profile (both scale with ML). Calibrated on t18's measurement
# (octopus.SPEC note: 0.93 / 0.55, "a slope of ~1.6, terraces and a ledge"); above 1 the sweep's radius falls faster
# than its axis advances. The forge's 0.90 / 0.25 is 0.51
TAPER_T18 = dict(s0=0.93, k=0.55, slope=1.6)
# parts of the octopus block-out that do NOT scale with ML (octopus.build_sdf / arm_centreline / eye_geom /
# funnel_geom, read 2026-10-21): an ML remix moves the body against them
OCTOPUS_ML_ABSOLUTE = ('the arm roots (crown_r0 m off the axis)', 'the oral disc (oral_disc m)',
                       'the eye mounds and eyeballs (eye_r, eyeball_r m)', "the funnel's radii (funnel m)",
                       "the mantle margin's lip and crease (mantle_margin m)")


def taper_slope(s0, k):
    """the end taper's estimated peak slope (t18-calibrated; > 1 terraces)"""
    if s0 >= 0.999:
        return float('inf')
    return TAPER_T18['slope'] * (k / (1.0 - s0)) / (TAPER_T18['k'] / (1.0 - TAPER_T18['s0']))
OCTOPUS_PATCH = dict(head=0.0028, arm=0.0018, disorder=0.9, seed_head=101, seed_arm=202)
OCTOPUS_PAINT = dict(oct_a10=0.075, mottle=1.0, speck=0.30, vein=None, vein_w=0.001, vein_scale=6.0)
OCTOPUS_SPEC_MIRROR, OCTOPUS_PATCH_MIRROR, OCTOPUS_PAINT_MIRROR = OCTOPUS_SPEC, OCTOPUS_PATCH, OCTOPUS_PAINT
OCTOPUS_SPEC, _SPEC_SRC = _live('octopus.py', 'SPEC', OCTOPUS_SPEC_MIRROR)
OCTOPUS_PATCH, _PATCH_SRC = _live('octopus_sculpt.py', 'PATCH', OCTOPUS_PATCH_MIRROR)
OCTOPUS_PAINT, _PAINT_SRC = _live('octopus_skin.py', 'SKIN_RECIPE', OCTOPUS_PAINT_MIRROR)
# the offline palette the octopus kernel hard-codes today (octopus_skin.k_skin, sRGB 0..1); remixes need it as data
OCTOPUS_PALETTE_SRGB = dict(dark=(0.40, 0.19, 0.14), brick=(0.57, 0.29, 0.20), ochre=(0.70, 0.48, 0.28),
                            cream=(0.88, 0.80, 0.71), disc=(0.77, 0.69, 0.63), cup=(0.55, 0.43, 0.42),
                            lip=(0.76, 0.60, 0.56), lining=(0.38, 0.19, 0.21))


def _octopus_layers():
    """the octopus's sculpt plan (octopus_sculpt.plan_octopus) as layer recipes, in its order. LOCKED layers are carves
    the meshed topology follows (DESIGN.md: "subtractive carves only where meshed topology follows them"): a remix
    cannot remove or swap them"""
    return [
        dict(id='eye_socket', kind='eye_socket', sites='anatomy:eyes', locked=True, material='skin', seed=0,
             src='octopus_sculpt.eye_socket: socket, lid bowl at eye_ap, lid-margin roll, eyeball occluder'),
        dict(id='suckers', kind='suckers', sites='anatomy:arm_oral_rows', mask=dict(regions=['arm']), density=1.0,
             size=dict(d_max_mm=17.5), material='skin', seed=0,
             src='octopus_sculpt.sucker_layout + sucker_strokes: sessile, biserial, ~209 per arm and 4 across the oral '
                 'disc, 1.4-17.8 mm (octopus.sucker_size; the arms stand on their rims)'),
        dict(id='arm_papillae', kind='papillae', sites='patch:arm',
             mask=dict(regions=['arm'], alpha_cos_min=-0.25, s=[0.0, 0.97]), density=0.55,
             size=dict(rb_mm=[0.30, 0.80], h_frac=[0.35, 0.90]), material='skin', seed=202,
             src='octopus_sculpt.plan_octopus: arm patch sites, aboral and lateral'),
        # warts and head papillae are CO-PLANNED on one site set (cosite): the papillae skip the warts' footprints
        dict(id='warts', kind='warts', sites='patch:head', cosite='head_patch_sites', mask=dict(regions=['body']),
             density=0.035, size=dict(rb_mm=[1.2, 2.2], nodes=[3, 6]), material='skin', seed=101,
             src='octopus_sculpt.plan_octopus: compound warts on the mantle and head (Allen 2014)'),
        dict(id='head_papillae', kind='papillae', sites='patch:head', cosite='head_patch_sites',
             mask=dict(regions=['body', 'crown_top', 'crown_oral'], weights=[0.62, 0.38, 0.04],
                       exclude=['eyes', 'funnel', 'lip']), density=1.0,
             size=dict(rb_mm=[0.32, 0.90], h_frac=[0.5, 1.3]), material='skin', seed=101,
             src='octopus_sculpt.plan_octopus: head patch sites (none within a wart\'s footprint)'),
        dict(id='eye_papillae', kind='eye_papillae', sites='anatomy:eyes',
             size=dict(supraocular=2, rim=7, ventral=3), material='skin', seed=0,
             src='octopus_sculpt.eye_papillae'),
        dict(id='lip_folds', kind='lip_folds', sites='anatomy:mouth', size=dict(folds=26), material='skin', seed=0,
             src='octopus_sculpt.mouth_lip'),
        dict(id='funnel_lumen', kind='funnel_lumen', sites='anatomy:funnel', locked=True, material='skin', seed=0,
             src='octopus_sculpt.funnel_lumen: carved LAST (craft guide sec. 9)'),
    ]


# the runtime ZONE map: each zone the max of weighted linear ramps over mask-pack channels; lref = the zone's measured
# albedo L p50 on the shipped T_head_albedo (work/bestiary/remix_scratch/zone_stats.py, the 12:35 export). primary is
# 1 - soft
OCTOPUS_ZONES = dict(
    primary=dict(one_minus='soft', lref=0.108),
    soft=dict(max=[['masks.g', 1.0, 0.0, 1.0], ['masks.b', 1.0, 0.2, 0.5]], lref=0.297),
    accent=dict(max=[['masks.b', 1.0, 0.85, 0.97]], lref=0.505),
    pattern=dict(max=[['display.b', 1.0, 0.0, 1.0]], lref=0.088),
    spots=dict(max=[['display.r', 1.0, 0.0, 1.0]]),
    eyering=dict(max=[['display.g', 1.0, 0.0, 1.0]]),
    thin=dict(max=[['masks.r', 1.0, 0.0, 1.0]]),
    glow=dict(max=[['masks.b', 1.0, 0.85, 0.97], ['masks.r', 0.6, 0.55, 0.9], ['display.g', 0.5, 0.3, 0.8]]),
    cells='masks.a', mottle='display.a',
    src='measured on T_head_albedo (12:35 export): primary L p50 0.108 (75 % of the set), soft 0.297 (25 %; x2.75 '
        'countershading), accent 0.505 (sucker rims, 0.7 %), pattern 0.088 (8 %); the arms set agrees within 0.01; the '
        'derived glow mask covers 3.6 % (head) and 2.5 % (arms)')

# Accessory FIT PROPOSALS for the octopus, RE-MEASURED on block-out v4 (10-21) by
# work/bestiary/patches/scratch_remix_v4/fit_v4.py: on the block-out SDF the forge builds now
# (octopus.build_sdf(low_spec(SPEC)), Warp on the CPU) and in the 05:58 glb's socket and joint frames (its node TRS
# composed). The skin distances below are that script's (+ outside the skin). A proposal is the FALLBACK where the
# creature has no seat data: resolve_accessory takes a socket's fit, then its seat_<archetype> node, then the recipe's
# own fit, and a proposal only for fit: 'proposal' on the seat SPECIES names (on the shipped glb seat_hat seats the hat;
# seat_glasses holds a rig fit, so remix glasses take theirs and the validator says the seat was bypassed). Lengths in
# metres, rotations (x, y, z, w) in the seat's local frame mapping the item's frame (+Y up, +Z its front, +X its left)
# onto the anatomy.
FIT_PROPOSALS = {
    'octopus': {
        # seat_hat's frame on socket_head_top (the mantle's crest, up its dorsal normal, 5.7 deg back of world up), the
        # section 10 mm down (t13's HAT_DEPTH, where the forge validated top_hat): equal-area radius 40.74 mm (semi-axes
        # 34.05 lateral, 50.33 fore-aft: a long oval), its extents' centre 5.3 mm forward: the seat table's own numbers
        # to 0.01 mm (fit_from_seat's offset within 0.04 mm of this 4-place one). SDF: the round 40.7 mm opening ring
        # reads +0.59 mm on average (-3.0 front and back, +3.7 at the sides), the proxy brim's underside -2.45 mm at
        # worst (14 % of its probes inside, at the oval's ends). r4's apex fit is gone: v4's socket_mantle_apex points
        # 99.8 deg off world up, back along the lying mantle
        'hat': dict(seat='socket_head_top', offset=[-0.0053, -0.0100, 0.0], rotation=[0.0, -0.7071, 0.0, 0.7071],
                    radius=0.0407),
        # the hat's seat, 15 mm down (5 mm under the hat, as r4's helmet sat under its hat); radius the smallest whose
        # 1.2 x radius hemisphere (remix.js's proxy) clears the skin by 1.0 mm (SDF +1.01 at the mantle behind, +1.04 at
        # the head's rise to the turrets in front). The section's own r_mean there (49.6 mm) cut 1.1 mm in: the section
        # is a long oval (41.4 x 62.2 mm)
        'helmet': dict(seat='socket_head_top', offset=[-0.0051, -0.0150, 0.0], rotation=[0.0, -0.7071, 0.0, 0.7071],
                       radius=0.0539),
        # on socket_eyes (the forge's bridge on the skin, on the head joint): each lens 4 mm proud of its mound on its
        # eye's axis (SDF +4.00; 17.8 mm from the eyeball's centre, where the forge's round_glasses sit at 18.0), 79.8 mm
        # apart lens to lens; the frame's +Z the eyes' mean axis (17.4 deg above forward), so each lens turned by
        # lens_yaw faces its eye's axis (0.03 deg after rounding; a level frame left the eyes' 10.2 deg pitch unfitted).
        # The bridge 6 mm ahead of the skin along +Z from the lens line (SDF +4.69 mm), the lens line bridge_arch 9.6 mm
        # behind it. The fit puts both lens centres within 0.05 mm of the measured ones (SDF +3.98 mm); the proxy's
        # 28.7 mm lens rings clear the skin by 2.90 mm
        'glasses': dict(seat='socket_eyes', offset=[0.0, -0.0116, 0.0031], rotation=[0.2606, 0.0, 0.0, 0.9654],
                        spacing=0.0798, lens_yaw=53.7, bridge_arch=0.0096),
        # 3 mm proud of the mound on the eye's axis (SDF +3.00 mm; 1.8 mm off the eyeball's front), its face on the eye
        # joint's axis (0.000 deg), radius 1.15 eyeball radii; the proxy's ring clears the skin by 6.22 mm
        'monocle': dict(seat='socket_eye_L', offset=[0.0168, 0.0, 0.0], rotation=[0.0, 0.7071, 0.0, 0.7071],
                        radius=0.0172),
        # the knot 2 mm off the head's front at y 122 mm (crown_y + 0.17 ML), the front met LEVEL from the body axis
        # there (s 0.859): v4's axis runs down the back of the head, and its dorsal normal (52.4 deg above level) met the
        # skin on the forehead at y 166 mm. The knot faces the skin's normal (23.3 deg above level); width the head's
        # half-width at the knot's height, at its widest (50.3 mm; the bow tie is authored for a 60 mm neck
        # half-width), where r4's axis-to-front distance (its head's radius) reads 68.2 mm on v4. SDF: the knot
        # +1.87 mm, the proxy's wing tips +10.7 mm
        'tie': dict(seat='bone:head', offset=[-0.0741, 0.0380, 0.0], rotation=[-0.3329, -0.6238, -0.3329, 0.6238],
                    width=0.0503),
        # [D] a flat disc facing forward from the glasses' bridge, moved along its +Z to where its closest rim point
        # stands 2 mm off the skin (the rim's bottom, on the head's front at y 128 mm; SDF: centre +34.7 mm): v4's head
        # bulges forward under the eyes, so the disc stands 65.7 mm ahead of the lens centres
        'mask': dict(seat='socket_eyes', offset=[0.0, -0.0534, 0.0412], rotation=[0.4038, 0.0, 0.0, 0.9148],
                     radius=0.0600),
    },
}

SPECIES = {
    'octopus': dict(
        family='radial', status='built', glb='work/bestiary/octopus/octopus.glb', spec=OCTOPUS_SPEC,
        spec_ranges=OCTOPUS_SPEC_RANGES, spec_coupled=OCTOPUS_SPEC_COUPLED, ml_absolute=OCTOPUS_ML_ABSOLUTE,
        patch=OCTOPUS_PATCH, paint=OCTOPUS_PAINT,
        palette_srgb=OCTOPUS_PALETTE_SRGB, skin_class='wet_cephalopod', layers=_octopus_layers(),
        zones=OCTOPUS_ZONES, extent_m=0.318,
        # its BUDGET tier (the lead's C0b call): a showcase base at 122,560 triangles before any part, so its budget is
        # hero's 150,000 whatever the recipe's tier (which keeps choosing the element stack and the affix roll)
        budget_tier='hero',
        # its own TRIANGLE BUDGET RECORD (the lead's L1 call, 11-08): the suckers are ONE primitive of SIZE CLASSES
        # (octopus_suckers.LOD_TIERS / lod_of give each of the 784 suckers one LOD by its diameter, all drawn at once:
        # 191,584 triangles), accepted at t26 B's own bar, forge/species/octopus_suckers.py TRI_BUDGET 192,000. The
        # validator counts what is drawn: a material of a kind listed here is held to its own budget and counted out of
        # the tier's cap (the body, its parts and attachments stay under hero's 150,000)
        budget_kinds=dict(sucker=192000),
        # joint chain arm<j>_kk and socket_arm<j>_tip are the cage's column order (theta = -azimuth increasing from +Z),
        # not the anatomical arm: j 0-3 are R1-R4 (on -X, front to back), j 4-7 are L4-L1. Measured on the 05:58 glb's
        # tip sockets (azimuths -22.5, -67.5, -112.5, -157.5, 157.5, 112.5, 67.5, 22.5 deg); `--glb` re-derives it
        arm_labels=('R1', 'R2', 'R3', 'R4', 'L4', 'L3', 'L2', 'L1'),
        # the 16 sockets t13 writes (the 05:58 glb, `--glb` lists them): socket_eyes is the glasses' bridge on the head
        # joint, socket_head_top the mantle's crest on the collar joint mantle_0, each carrying a seat node
        sockets=['socket_eye_L', 'socket_eye_R', 'socket_eyes', 'socket_crown', 'socket_funnel', 'socket_mantle_apex',
                 'socket_head_top', 'socket_mouth'] + [f'socket_arm{j}_tip' for j in range(8)],
        regions=['body', 'crown_top', 'crown_oral', 'arm'],
        anatomy=['eyes', 'arm_oral_rows', 'mouth', 'funnel', 'mantle_apex', 'arm_tips'],
        patch_sets=['head', 'arm'],
        parts={'socket_mouth': dict(part='octopus_beak', material='octopus_beak'),
               'socket_eye_L': dict(part='octopus_eye', material='octopus_eye'),
               'socket_eye_R': dict(part='octopus_eye', material='octopus_eye')},
        seats=dict(hat='socket_head_top', helmet='socket_head_top', glasses='socket_eyes',
                   monocle='socket_eye_L', tie='bone:head', mask='socket_eyes'),
        notes=['socket_crown is the ARM crown centre at world y 0.088, inside the body (t13: body joint, zero offset); '
               'DESIGN.md names socket_crown the hat seat, the octopus\'s is socket_head_top: rename it '
               '(socket_arm_crown) before anything seats by DESIGN.md\'s name',
               'the hat seats on seat_hat under socket_head_top (the forge validated top_hat 10 mm down); the helmet '
               'shares that seat (socket_mantle_apex points 99.8 deg off world up, back along the lying mantle); '
               'glasses and mask ride the face socket socket_eyes: remix glasses resolve from FIT_PROPOSALS past its '
               'seat_glasses, a rig fit they cannot seat by (accessory.seat_format says so), the mask from its '
               'proposal (no seat_mask there: needs.socket_fits); the tie rides the head joint (no socket at the '
               'head\'s front below the eyes)']),
    # planned bases: enough data to exercise the operators and to say what a crossbreed needs
    'wolf': dict(
        family='limbed', status='planned', spec={}, spec_ranges={}, skin_class='fur',
        layers=[dict(id='fur_groom', kind='groom_cards', sites='scatter', mask=dict(regions=['torso', 'neck', 'head',
                                                                                             'limb', 'tail']),
                     density=2400.0, material='skin', seed=11, src='REF sec. 10b: ~2,400 cards per m2'),
                dict(id='paw_pads', kind='pads', sites='anatomy:paws', material='keratin', seed=12)],
        zones={}, extent_m=1.3,
        sockets=['socket_head_crown', 'socket_eye_L', 'socket_eye_R', 'socket_face_bridge', 'socket_jaw',
                 'socket_neck_collar', 'socket_tail_tip', 'socket_horn_L', 'socket_horn_R'],
        regions=['torso', 'neck', 'head', 'limb', 'tail'], anatomy=['eyes', 'jaw', 'paws', 'ears'],
        patch_sets=['body'],
        parts={'socket_jaw': dict(part='canid_jaw', material='wolf_head')},
        seats=dict(hat='socket_head_crown', glasses='socket_face_bridge', tie='socket_neck_collar'),
        notes=['PLAN.md phase 2: no generator yet']),
    # (B10, the beetle builder, 11-01: BEETLE_PLAN §6.8 on the built glb, work/bestiary/beetle/b10/r01_rig.py's sockets and seats)
    'beetle': dict(
        family='arthropod', status='built', glb='work/bestiary/beetle/out_b58/stag_beetle_rig.glb', spec={}, spec_ranges={},
        skin_class='chitin',
        # (the remix's own layer vocabulary: the coarse regions below are the layer masks', not the forge's REGIONS; B1's
        # sclerites are parts of the base, so chitin_plates stays a remix layer for other species' armour, §6.8: the crossbreed
        # self-test takes it and elytra_ridges as the beetle's donor layers. Both kinds are 'planned' (plate_generator,
        # ridge_curves), so validate reports them 'missing' on every beetle recipe until those generators exist)
        layers=[dict(id='chitin_plates', kind='plates', sites='patch:body', mask=dict(generic=['dorsal']),
                     density=1.0, size=dict(plate_mm=[6.0, 18.0]), material='chitin', seed=31,
                     src='study G sec. 3.3: sclerite plates with raised rims'),
                dict(id='elytra_ridges', kind='ridges', sites='scatter', mask=dict(regions=['elytra']),
                     density=0.4, material='chitin', seed=32)],
        # the zones (BEETLE_PLAN §5.5, the glb's extras.bestiary.zones): primary = 1 - soft, soft = masks.r, accent = masks.b,
        # pattern = masks.a (the chestnut zone); lref the zones' albedo L p50 on the B10 skin (b10/out/s01: the cuticle's
        # dark ground, the soft membranes and setae, the claws' and keels' accent, the elytra's and mandibles' chestnut)
        zones=dict(primary=dict(one_minus='soft', lref=0.012), soft=dict(max=[['masks.r', 1.0, 0.0, 1.0]], lref=0.015),
                   accent=dict(max=[['masks.b', 1.0, 0.0, 1.0]], lref=0.02),
                   pattern=dict(max=[['masks.a', 1.0, 0.0, 1.0]], lref=0.019),
                   src='BEETLE_PLAN 5.5 (B10: lrefs rounded from the k_skin stats)'),
        # the BODY's extent at x10 by elements.py's rule (BL, mandibles out: 0.436 m), life_scale 0.1 (the glb is authored x10)
        extent_m=0.436, life_scale=0.1,
        # its BUDGET tier (§6.8: tier large): 49,568 triangles before any part, over small's 50,000 with a hat
        budget_tier='large',
        sockets=['socket_crown', 'socket_pronotum_top', 'socket_pronotum_horn', 'socket_horn_mid', 'socket_horn_L',
                 'socket_horn_R', 'socket_eye_L', 'socket_eye_R', 'socket_eyes', 'socket_mandible_L', 'socket_mandible_R',
                 'socket_antenna_L', 'socket_antenna_R', 'socket_mouth', 'socket_chest']
                + [f'socket_{k}_{c}_{s}' for k in ('claw', 'foot') for c in 'fmh' for s in 'LR']
                + [f'socket_back_{s}_{i}' for s in 'LR' for i in range(3)] + ['socket_back_mid', 'socket_wing_L', 'socket_wing_R',
                                                                             'socket_abdomen_tip']
                + ['socket_fx_death', 'socket_fx_light', 'socket_affix_0', 'socket_affix_1', 'socket_affix_2',
                   'socket_fx_element_body', 'socket_fx_element_head'] + [f'socket_fx_foot_{c}_{s}' for c in 'fmh' for s in 'LR'],
        regions=['head', 'thorax', 'abdomen', 'leg', 'elytra'], anatomy=['eyes', 'mandibles', 'antennae'],
        patch_sets=['body'],
        # (the mandibles are the base's own pieces: a mandible swap on socket_mandible_* is B12's morph round)
        parts={},
        # the iridescent OPTION (the beetle-to-material round, 10-28; BEETLE_PLAN §5.5; patches/beetle_b58_recipe.md): L. cervus
        # has no structural colour, so the realistic base's film is OFF; the jewel-beetle looks are remix PALETTE DATA, one family
        # per row (forge/species/stag_beetle_skin.IRID_FAMILIES; the glb's extras.bestiary.iridophore_families): the film's
        # strength, IOR and thickness range in nm (the forge's baked IRID pack G picks within it per texel), the albedo's darkening
        # toward the melanin backing, the clear coat's thinning. A remix names one: display=dict(iridophores=dict(family='jewel'));
        # resolve_display fills the row in
        display=dict(iridophores=dict(zone='primary', strength=0.0, ior=1.6, thickness=[250.0, 650.0], family='none'),
                     iridophore_families=dict(
                         none=dict(strength=0.0, ior=1.6, thickness=[250.0, 650.0], darken=1.0, coat=1.0),
                         jewel=dict(strength=1.0, ior=1.9, thickness=[338.0, 362.0], darken=0.10, coat=0.25),
                         sapphire=dict(strength=1.0, ior=1.9, thickness=[150.0, 190.0], darken=0.35, coat=0.50),
                         oilslick=dict(strength=0.85, ior=1.6, thickness=[180.0, 700.0], darken=0.60, coat=0.80),
                         gold=dict(strength=1.0, ior=1.9, thickness=[214.0, 232.0], darken=0.10, coat=0.25))),
        # the seats (§6.6): the hat on seat_hat under socket_crown (socket_pronotum_top carries a second for small-headed morphs),
        # glasses on socket_eyes (their fit carries the eyes' splay: every glasses item is refused, §6.6), the monocle on the left
        # compound eye (its fit in socket_eye_L's extras)
        seats=dict(hat='socket_crown', glasses='socket_eyes', monocle='socket_eye_L'),
        notes=['B10 (11-01): built; the glb is authored at x10 (life_scale 0.1); the remix\'s coarse layer regions map onto the '
               'forge\'s REGIONS (head: head, eye, mandible, antenna, mouthparts; thorax: pronotum, scutellum, venter; leg: coxa '
               'to claw; elytra: elytron, hindwing)',
               'no tie seat yet (socket_chest carries none); no glasses item seats (the eyes face ~102 deg off forward)']),
    # HUMAN H4 (the rig builder's staged patch, 11-01; HUMAN_PLAN §6.1): the baseline woman (the man's glb the same
    # contract); the generator's spec and identity space land at H5, so no spec keys yet. The glb: the
    # canonical human base, H4d's (the lead's L1 call, 11-08)
    'human': dict(
        family='hominid', status='built', glb='work/bestiary/human/h4d/build/glb/human_F.glb', spec={}, spec_ranges={},
        skin_class='dry_skin', layers=[], zones={}, extent_m=1.74,
        budget_tier='hero',
        sockets=['socket_head_top', 'socket_eyes', 'socket_eye_L', 'socket_eye_R', 'socket_mouth', 'socket_chest',
                 'socket_neck_collar'] + [f'socket_back_{i}' for i in range(5)] +
                ['socket_back_upper_L', 'socket_back_upper_R', 'socket_back_lower_L', 'socket_back_lower_R',
                 'socket_back_shell', 'socket_tail_base', 'socket_wrist_L', 'socket_wrist_R', 'socket_ankle_L',
                 'socket_ankle_R', 'socket_ear_L', 'socket_ear_R', 'socket_horn_L', 'socket_horn_R', 'socket_horn_mid'],
        regions=['head', 'torso', 'arm', 'leg'], anatomy=['eyes', 'mouth', 'ears', 'nails'], patch_sets=['head', 'body'],
        parts={},                  # the eyes and the mouth are the base's own (no swappable library part yet)
        seats=dict(hat='socket_head_top', helmet='socket_head_top', glasses='socket_eyes', mask='socket_eyes',
                   tie='socket_chest', monocle='socket_eye_L'),
        notes=['the rings, chains and regions ride the scene extras (h4/rig/r11_sockets.py): the back-limb ports are '
               'kind back_limb, the waist ring a body_region record, the neck ring the head_region\'s']),
}
assert all(sp.get('budget_tier') in (None,) + TIERS for sp in SPECIES.values()), 'a species budget tier is a tier'
GENERIC_MASKS = ('dorsal', 'ventral', 'lateral', 'world_up')
GENERIC_SITES = ('patch:body', 'scatter')
# AXOLOTL AX11 + AX12 (AXOLOTL_PLAN §10, §11's AX11 and AX12 rows; the AX11 builder's staged patch, 11-01, ax10_notes/
# patches/remix_axolotl.md, folded into AX12's, 11-02: patches/axolotl_ax12_recipe.md). Its own statement after the table
# (the beetle's B10 patch rewrites the table's last entry). The runtime ZONES (AX12, work/bestiary/axolotl/ax12/
# m01_zones.py): on AX11's BODY set, the wild type composed as runtime/axolotl.js composes it (the unpigmented ground
# under the melanophore cover, the xanthophores, the iridophores' gold), each zone's linear-L median weighted by its mask:
# primary 0.049 (51 % of the set), soft 0.177 (49 %: the ventral gradient, masks G), accent 0.054 (the gill stalks and
# filaments, masks B 0.9-1: 1.5 %), pattern 0.136 (the iridophores' gold patches, display R: 0.08 %); the glow mask 4.7 %
# (the gills, the thin margins, the gold patches); the pulses' phase the ventral gradient, the surface's break the
# xanthophores' mottle (masks A and display A are opaque in the glb)
AXOLOTL_ZONES = dict(
    primary=dict(one_minus='soft', lref=0.049),
    soft=dict(max=[['masks.g', 1.0, 0.25, 0.75]], lref=0.177),
    accent=dict(max=[['masks.b', 1.0, 0.75, 0.95]], lref=0.054),
    pattern=dict(max=[['display.r', 1.0, 0.0, 1.0]], lref=0.136),
    thin=dict(max=[['masks.r', 1.0, 0.0, 1.0]]),
    glow=dict(max=[['masks.b', 1.0, 0.75, 0.95], ['masks.r', 0.5, 0.5, 0.9], ['display.r', 0.6, 0.2, 0.8]]),
    cells='masks.g', mottle='display.g',
    src='AX12 m01_zones.py on AX11\'s BODY set (the wild type composed): primary L p50 0.049 (51 %), soft 0.177 (49 %), '
        'accent 0.054 (1.5 %), pattern 0.136 (0.08 %); glow 4.7 %')
SPECIES['axolotl'] = dict(
    family='limbed', status='built', glb='work/bestiary/axolotl/ax11/axolotl.glb', spec={}, spec_ranges={},
    skin_class='wet_skin', layers=[], zones=AXOLOTL_ZONES, extent_m=0.966, life_scale=0.25,
    # 74.6 k triangles with the hero's 684 filaments (the lead's AX10 call: the LOD tiers thin them at AX14): the large
    # tier's 100 k holds it with an accessory
    budget_tier='large',
    sockets=['socket_crown', 'socket_eyes', 'socket_eye_L', 'socket_eye_R', 'socket_mouth', 'socket_jaw', 'socket_horn_L',
             'socket_horn_R', 'socket_horn_mid'] +
            [f'socket_gill_{r}_{s}' for r in (1, 2, 3) for s in 'LR'] + [f'socket_back_{i}' for i in range(3)] +
            ['socket_wing_L', 'socket_wing_R', 'socket_forepaw_L', 'socket_forepaw_R', 'socket_hindpaw_L',
             'socket_hindpaw_R', 'socket_wrist_L', 'socket_wrist_R', 'socket_ankle_L', 'socket_ankle_R', 'socket_chest',
             'socket_hips', 'socket_tail_base', 'socket_tail_tip'],
    regions=['head', 'trunk', 'tail', 'limb', 'gill', 'fin'], anatomy=['eyes', 'mouth', 'gills', 'fins', 'digits'],
    patch_sets=['body'],
    parts={},                  # the eyes, the gills and the fins are the base's own (no library part yet)
    seats=dict(hat='socket_crown', glasses='socket_eyes', tie='socket_chest', monocle='socket_eye_L'),
    notes=['the rings, chains and native groups ride the scene extras (tests/ax11_glb.py); the gills hang under neck_0 '
           'ahead of no head joint (a head swap at the poll keeps them); seat_hat carries the hats the gill fan refuses '
           '(the study-G frog lesson as data)',
           'AX12: the runtime (bestiary.js SPECIES.axolotl, runtime/axolotl.js) composes its pigment layers and takes the '
           'palette and element remaps on its own skin by these zones; the glb is authored at x4 (life_scale 0.25)'])
assert SPECIES['axolotl']['budget_tier'] in TIERS, 'a species budget tier is a tier'


def arms_regex(labels, joints=r'\d+', base='octopus'):
    """a bone-op regex for anatomical arms: arms_regex(['L1', 'R1'], '00') -> '^arm(7|0)_00$' (the joint chains are
    numbered in the cage's column order: SPECIES[base]['arm_labels'])"""
    names = SPECIES[base]['arm_labels']
    js = []
    for lab in labels:
        if lab not in names:
            raise KeyError(f'no arm {lab!r} on a {base} (have: {", ".join(names)})')
        js.append(str(names.index(lab)))
    return f'^arm({"|".join(js)})_{joints}$'

# ============================================================================================ catalogs
# PARTS: meshes that seat on sockets. uv_family = the texture set its UVs were unwrapped for; the material slot a recipe
# renders it with must carry the same family (study G §4.6: every elemental medium bug-dog creature wears a mis-mapped horn).
PARTS = {
    'octopus_eye': dict(archetype='eye', status='built', species='octopus', uv_family='octopus_eye',
                        seats=['socket_eye_L', 'socket_eye_R'], tris=1200, rigid=True,
                        src='octopus_eye.eye_mesh: cube-sphere eyeball, painted iris, level horizontal pupil'),
    'octopus_beak': dict(archetype='beak', status='built', species='octopus', uv_family='octopus_beak',
                         seats=['socket_mouth'], tris=1920, rigid=True,
                         src='octopus_beak.beak_meshes: two keratinised mandibles (tris: the 12:36 export; a built '
                             'creature\'s manifest is authoritative)'),
    'nautilus_shell': dict(archetype='shell', status='planned', uv_family='nautilus_shell',
                           seats=['socket_mantle_apex'], tris=6000, rigid=True,
                           src='DESIGN.md ATTACHMENTS: shells (not built)'),
    'ram_horns': dict(archetype='horn', status='planned', uv_family='horn_ram', seats=['socket_horn_L',
                                                                                     'socket_horn_R'],
                      tris=3000, rigid=True, src='DESIGN.md horns: spike, ram, antler, moose, narwhal (not built)'),
    'canid_jaw': dict(archetype='jaw', status='planned', uv_family='wolf_head', seats=['socket_jaw'], tris=4000,
                      rigid=False, src='PLAN.md phase 2'),
    # (B10: the tris the built glb's mandible carries, 2,952: BEETLE_PLAN §6.8 estimated the cage's 2,930)
    'beetle_mandible': dict(archetype='mandible', status='planned', uv_family='beetle_head',
                            seats=['socket_mandible_L', 'socket_mandible_R'], tris=2952, rigid=True,
                            src='PLAN.md phase 3; the base\'s own mandible is a piece of its glb (B12 makes the swappable part)'),
}
# CYBORG_PARTS: the cyborg families' catalog (research/CYBORG_PLAN.md §4, §8). Slot-strict: they seat by KIND through
# recipe['cyborg'] on remix/slots.py's closed table (kinds, interfaces, fits, seats), never on a socket named in parts.
# needs = the FORGE_CAPS each waits on; tris = the NET triangles one placement adds, (low, high), where the plan
# estimates them (the first target, §8's costs: the implant 1,600 against the eye's 1,200 [E-fo]; the mech arm at cut 8
# 7-9k [E-fo] less 1,560 skin [D-fo] and 3,494 sucker [D-check] triangles; the dome 2-2.5k [E-fo]); None = no estimate
CYBORG_PARTS = {
    'eye_implant': dict(status='planned', needs=['slot_kinds', 'eye_implant'], tris=(400, 400)),
    'sensor_module': dict(status='planned', needs=['slot_kinds', 'module_seats'], tris=(2000, 2500)),
    'antenna_probe': dict(status='planned', needs=['slot_kinds', 'module_seats'], tris=None),
    'visor': dict(status='planned', needs=['slot_kinds', 'module_seats'], tris=None),
    'back_mount': dict(status='planned', needs=['slot_kinds', 'module_seats', 'back_mounts', 'cyborg_ids', 'plate_op'],
                       tris=None),
    'thruster_nozzle': dict(status='planned', needs=['slot_kinds', 'module_seats'], tris=None),
    'gripper': dict(status='planned', needs=['slot_kinds', 'module_seats', 'chain_cut'], tris=None),
    'mech_tentacle': dict(status='planned', needs=['slot_kinds', 'chain_cut', 'mech_tentacle'], tris=(1946, 3946)),
    'mech_leg': dict(status='planned', needs=['slot_kinds', 'chain_cut', 'mech_leg'], tris=None),
    # (C3) the robot hand at the human's wrist: built in work/bestiary/cyborg_robot/c3 through forge/assemble.py's part
    # path, not yet by the cyborg forge's own stages (so it waits on the same caps as the other rigid chains)
    'mech_arm': dict(status='planned', needs=['slot_kinds', 'chain_cut', 'mech_leg'], tris=None),
    'mech_tail': dict(status='planned', needs=['slot_kinds', 'chain_cut', 'mech_leg'], tris=None),
    'mech_antenna': dict(status='planned', needs=['slot_kinds', 'chain_cut', 'mech_leg'], tris=None),
    'machine_head': dict(status='planned', needs=['slot_kinds', 'machine_head'], tris=None),
}
assert set(CYBORG_PARTS) == set(SL.CYBORG_FAMILIES), 'CYBORG_PARTS and remix/slots.py\'s cyborg families must agree'
# GRAFT_PARTS: the ORGAN families' catalog (research/CROSSBREED_DESIGN.md §6.1; the lead's decision 6: a graft seats by
# KIND on slots.py's one closed table through the recipe's graft section, never as a cyborg row). tris = the NET
# triangles a placement adds, (low, high): M2's part (the collar from the ring, the shells, the sleeves: 2,416) and its
# re-made suckers (188) less the native group it drops (arm 0 past cut 8: 1,568 skin and 3,588 sucker triangles)
GRAFT_PARTS = {
    'leg_graft': dict(status='M2 (staged)', needs=['ring_records', 'assemble'], tris=(-2552, -2552)),
}
assert set(GRAFT_PARTS) == set(SL.ORGAN_FAMILIES), 'GRAFT_PARTS and remix/slots.py\'s organ families must agree'
CYBORG_RUNTIME = ('glow', 'affixes')     # the cyborg section's runtime keys (CYBORG_PLAN §6.1); the rest is offline
ELEMENT_POLICIES = ('inherit', 'own', 'element_only')

# ACCESSORY ARCHETYPES: the fit fields each needs from its seat (DESIGN.md Accessories: socket_crown with a crown
# radius and a fit cage; the eyes' bridge point, spacing and ear-hook points; the chest for a tie) and the field the
# item's scale comes from (fit[field] / item.authored[field])
ARCHETYPES = {
    'hat': dict(required=('offset', 'rotation', 'radius'), scale_by='radius'),
    'helmet': dict(required=('offset', 'rotation', 'radius'), scale_by='radius'),
    'glasses': dict(required=('offset', 'rotation', 'spacing', 'lens_yaw'), scale_by='spacing'),
    'monocle': dict(required=('offset', 'rotation', 'radius'), scale_by='radius'),
    'tie': dict(required=('offset', 'rotation', 'width'), scale_by='width'),
    'mask': dict(required=('offset', 'rotation', 'radius'), scale_by='radius'),
}
# ACCESSORIES: none is built yet (the AAA props come from the robot body's craft). authored = the size the item is
# modelled at (a human head: crown radius 0.091 m from a 57 cm circumference; IPD 64 mm); max_lens_yaw = how far a
# glasses item's lenses can turn (a flat frame ~8 degrees of wrap; a hinged bridge more); tris from DESIGN.md's
# attachment budget (0.5-6k each)
ACCESSORIES = {
    'top_hat': dict(archetype='hat', status='planned', authored=dict(radius=0.091), tris=3000,
                    materials=['felt', 'silk_band'], src='creature_builder.js hat "top" (primitive proxy only)'),
    'cap': dict(archetype='hat', status='planned', authored=dict(radius=0.091), tris=2500, materials=['cotton']),
    'beanie': dict(archetype='hat', status='planned', authored=dict(radius=0.091), tris=2000, materials=['knit']),
    'cowboy_hat': dict(archetype='hat', status='planned', authored=dict(radius=0.091), tris=3500,
                       materials=['felt', 'leather_band']),
    'officer_cap': dict(archetype='hat', status='planned', authored=dict(radius=0.091), tris=3500,
                        materials=['wool', 'patent_visor', 'brass']),
    'peaked_cap': dict(archetype='hat', status='planned', authored=dict(radius=0.0907), tris=5956,
                       materials=['worsted', 'felt', 'velvet', 'anodised_cord', 'gilt', 'enamel', 'lacquer', 'leather',
                                  'linen'],
                       src='forge/props/peaked_cap.py -> work/bestiary/props/peaked_cap.glb: the GDR general\'s '
                           'Schirmmuetze as Skye\'s references show it (research/CAP_REFERENCE.md, CAP_GDR.md): the '
                           'crown\'s top rolled over its piping, the gilt oak wreath on its velvet backing and the '
                           'state cockade, two-ply ropes at one height to the slide knots at the band\'s sides, a '
                           'plain visor; on the octopus seat_hat perched in its own proportions, the band\'s give and '
                           'the visor\'s hinge in the glb\'s conform morph (patches/peaked_cap.md)'),
    'space_helmet': dict(archetype='helmet', status='planned', authored=dict(radius=0.095), tris=4000,
                         materials=['glass', 'metal']),
    'hardhat': dict(archetype='helmet', status='planned', authored=dict(radius=0.095), tris=3000,
                    materials=['abs_plastic']),
    'round_glasses': dict(archetype='glasses', status='planned', authored=dict(spacing=0.064), max_lens_yaw=8.0,
                          tris=1500, materials=['acetate', 'glass']),
    'sunglasses': dict(archetype='glasses', status='planned', authored=dict(spacing=0.064), max_lens_yaw=12.0,
                       tris=1500, materials=['acetate', 'tinted_glass']),
    'wrap_goggles': dict(archetype='glasses', status='planned', authored=dict(spacing=0.064), max_lens_yaw=60.0,
                         tris=2200, materials=['brass', 'glass', 'leather'],
                         src='[D] a hinged bridge for side-facing eyes (the octopus: +-54 degrees)'),
    'monocle': dict(archetype='monocle', status='planned', authored=dict(radius=0.016), tris=600,
                    materials=['gold', 'glass']),
    'bow_tie': dict(archetype='tie', status='planned', authored=dict(width=0.060), tris=1000, materials=['silk']),
    'necktie': dict(archetype='tie', status='planned', authored=dict(width=0.060), tris=1200, materials=['silk']),
    'mask_smile': dict(archetype='mask', status='planned', authored=dict(radius=0.105), tris=1000,
                       materials=['painted_card']),
}

# SCULPT LAYER KINDS: what the forge can build today (status built: the octopus plan's functions) and what a remix may
# ask for that needs new forge work (status planned + needs = FORGE_CAPS keys)
SCULPT_KINDS = {
    'eye_socket': dict(status='built', mode='carve', domain='species'),
    'funnel_lumen': dict(status='built', mode='carve', domain='species'),
    'suckers': dict(status='built', mode='add', domain='radial'),
    'papillae': dict(status='built', mode='add', domain='generic'),
    'warts': dict(status='built', mode='add', domain='generic'),
    'eye_papillae': dict(status='built', mode='add', domain='species'),
    'lip_folds': dict(status='built', mode='carve', domain='species'),
    'nodules': dict(status='built', mode='add', domain='generic',
                    note='papilla_strokes with tip = 1 (round cones): no new stroke needed'),
    'growth': dict(status='planned', mode='add', domain='generic', needs=['material_ids']),
    'plates': dict(status='planned', mode='add', domain='generic', needs=['plate_generator', 'material_ids']),
    'ridges': dict(status='planned', mode='add', domain='generic', needs=['ridge_curves']),
    'spines': dict(status='planned', mode='add', domain='generic', needs=['ridge_curves']),
    'scales': dict(status='planned', mode='add', domain='generic', needs=['scale_generator']),
    'crack_network': dict(status='planned', mode='carve', domain='generic', needs=['crack_generator']),
    'pustules': dict(status='planned', mode='add', domain='generic', needs=['material_ids']),
    'groom_cards': dict(status='planned', mode='mesh', domain='generic', needs=['groom_cards']),
    'pads': dict(status='planned', mode='add', domain='species', needs=['second_family']),
}
LAYER_KEYS = {'id', 'kind', 'sites', 'cosite', 'mask', 'density', 'size', 'material', 'seed', 'locked', 'src',
              'mode', 'origin'}

# FORGE CAPABILITIES (what is built today, 2026-10-20). The validator turns every recipe requirement that is False here
# into a 'missing' problem; flip a cap (or have the forge export its caps) when the work lands
FORGE_CAPS = dict(
    layer_list_plan=False,       # the plan consumes a layer list (plan_octopus is code today)
    # (the three below landed 10-21 with patches/material_ids_v2.md and ran end to end on the GPU: t10 -> t11 -> t13 ->
    # the engine, BESTIARY_GROWTH=metal_crystal, the growths set 0.000 % missed)
    material_ids=True,           # sculpt strokes write material ids; the bake samples them (DESIGN.md growth families)
    growth_mesh=True,            # separate growth meshes with their own material (study T element variants)
    hexprism_stroke=True,        # faceted crystal strokes (growth.sd_prism, stroke kinds 4 / 5 in voxel.sd_stroke)
    skin_palette_params=False,   # octopus_skin.k_skin's palette constants as parameters
    skin_pattern_params=False,   # paint passes chosen by data (rings instead of bands and blotches)
    socket_fits=False,           # sockets carry fit data per accessory archetype
    fx_sockets=False,            # the FX contract (socket_affix_0..2, fx_death, fx_light) on every creature
    glow_channel=False,          # a baked glow mask (the runtime derives one from the masks and display packs)
    papillae_normal_pair=False,  # a smooth + raised normal pair for the runtime's papillae display
    display_coords=True,         # rest-pose coordinates for the procedural displays (bestiary.js reads positionGeometry)
    flow_map=False,              # a flow map for liquid metal and cellular pulses
    second_family=False,         # only the radial octopus is built
    accessory_assets=False,      # the AAA hats, glasses and ties
    plate_generator=False, ridge_curves=False, scale_generator=False, crack_generator=False, groom_cards=False,
    arm_count_param=False,       # octopus.N_ARMS and arm_azimuths() fix eight arms
    # the CYBORG family (research/CYBORG_PLAN.md §6.6). C0 built the slot table (remix/slots.py); the forge writes no
    # slot extras until t13's staged patch lands (work/bestiary/patches/cyborg_c0_t13.md, C7). cyborg_ids LANDED 10-22
    # (work/bestiary/patches/cyborg_c1_ranges.md: growth.py 41c98a5c, bake.py bceb7270, cyborg OFF byte-identical)
    slot_kinds=False, cyborg_ids=True, plate_op=False, eye_implant=False, module_seats=False, chain_cut=False,
    mech_tentacle=False, mech_leg=False, back_mounts=False, machine_head=False,
)
CAP_TEXT = dict(
    layer_list_plan='plan_octopus driven by the recipe\'s layer list (it is code today)',
    material_ids='sculpt MATERIAL IDS: strokes write an id, the bake samples it, the material pass builds the family',
    growth_mesh='growth MESHES with their own material (study T element variants; DESIGN.md budget 5-15k triangles)',
    hexprism_stroke='a faceted crystal stroke (hexagonal prism + pyramid) in voxel.sd_stroke',
    skin_palette_params='octopus_skin.k_skin palette constants as parameters (offline recolour)',
    skin_pattern_params='octopus_skin paint passes selectable by data (e.g. rings instead of bands)',
    socket_fits='socket FIT data per accessory archetype, emitted by the species generator',
    fx_sockets='the FX contract sockets (socket_affix_0..2, fx_death, fx_light)',
    glow_channel='a baked glow mask channel (from the plan\'s feature tags + curvature)',
    papillae_normal_pair='a smooth + raised normal map pair (runtime papillae)',
    display_coords='rest-pose coordinates for the procedural displays: positionGeometry, or the anatomical s and '
                   'patch-cell id in a display channel',
    flow_map='a flow map (liquid metal flow, cellular pulse phase)',
    second_family='a second built body-plan family (wolf / beetle generators)',
    accessory_assets='the AAA accessory props (hats, glasses, ties)',
    plate_generator='an armour / sclerite plate generator', ridge_curves='ridge and spine curves on the anatomy',
    scale_generator='a scale / scute generator', crack_generator='a crack-network skin generator',
    groom_cards='groom cards (fur)', arm_count_param='a variable arm count (octopus N_ARMS = 8 is a constant)',
    slot_kinds='typed sockets as ports and chains: extras.slot (its kind, frame and dims) on every socket, '
               'bestiary.chains in the scene (t13: staged, patches/cyborg_c0_t13.md)',
    cyborg_ids='the cyborg id range 64-95 and its two range gates (growth.unpack_ids, the bake\'s occlusion test; C1)',
    plate_op='the voxel PLATE op with its seams, fasteners, crease and gasket (C2)',
    eye_implant='the eye implant part (REVOLVE rings on a cube-sphere back, its own set; C4)',
    module_seats='typed seat_* nodes for cyborg mounts with validated entries (fit.fit_module; C6)',
    chain_cut='a chain cut at a listed joint: the ring pinned to joint k - 1, the skin and suckers beyond dropped (C5)',
    mech_tentacle='the mech tentacle: rigid knuckled segments, the flange, the hoses (C5)',
    mech_leg='mech legs, tails and antennae: rigid pieces on a limbed or arthropod chain (C11, C12)',
    back_mounts='back mounts (turret, folded arm, mast) on mount plates, G5 cleared (C10)',
    machine_head='a machine head: a head-region swap that keeps the jaw (C13)')

# Moods are presets of bestiary.js's display weights (setDisplay: dark, eyering, spots, mottle, clouds, rings, glow) plus
# the remix's leucophore scatter. A key a mood leaves out keeps the creature's RESTING value (the recipe's weights, and
# its photophore strength for glow), so the photophores of an abyssal remix stay lit through a cycle of moods
MOODS = dict(
    rest=dict(dark=0.0, eyering=0.0, spots=0.0, mottle=0.0, clouds=0.0, rings=0.0, leuco=0.0),
    blanch=dict(dark=0.0, eyering=0.0, spots=1.0, mottle=0.0, clouds=0.0, rings=0.0, leuco=0.65),
    flush=dict(dark=0.85, eyering=0.5, spots=0.0, mottle=0.3, clouds=0.0, rings=0.0, leuco=0.0),
    mottle=dict(dark=0.35, eyering=0.2, spots=0.4, mottle=1.0, clouds=0.0, rings=0.0, leuco=0.0),
    eyebar=dict(dark=0.2, eyering=1.0, spots=0.2, mottle=0.2, clouds=0.0, rings=0.0, leuco=0.1),
    clouds=dict(dark=0.1, eyering=0.0, spots=0.0, mottle=0.3, clouds=1.0, rings=0.0, leuco=0.0),
    deimatic=dict(dark=0.0, eyering=1.0, spots=1.0, mottle=0.0, clouds=0.0, rings=0.0, leuco=0.5),
    alarm_rings=dict(dark=0.0, eyering=0.3, spots=0.0, mottle=0.0, clouds=0.0, rings=1.0, leuco=0.0),
    glow=dict(dark=0.3, eyering=0.0, spots=0.0, mottle=0.0, clouds=0.0, rings=0.0, leuco=0.0, glow=1.0),
)
MOOD_SRC = ('DESIGN.md skin display families: blanch (alarm, near white), flush (dark red-brown), mottle '
            '(camouflage), eye bar (threat); passing clouds (cuttlefish, octopus); blue rings (bestiary.js); '
            'deimatic and the glow flash [D]')
DISPLAY_KEYS = ('dark', 'eyering', 'spots', 'mottle', 'clouds', 'rings', 'glow', 'leuco')

# budgets (DESIGN.md: a medium creature 25-50k triangles with its attachments, a large one up to ~100k; growths 5-15k;
# the hero tier 150k, the lead 10-21: the octopus is 122,560 before any cyborg part)
BUDGET_TRIS = dict(small=50000, medium=50000, large=100000, elite=100000, hero=150000)
GROWTH_MESH_TRIS = 10000

RECIPE_KEYS = ('version', 'name', 'base', 'family', 'seed', 'level', 'tier', 'role', 'spec', 'sculpt', 'skin',
               'palette', 'display', 'parts', 'accessories', 'element', 'element_policy', 'affixes', 'bones',
               'lineage', 'notes', 'cyborg')
OFFLINE_KEYS = ('base', 'family', 'spec', 'sculpt', 'skin', 'parts', 'cyborg')
RUNTIME_KEYS = ('seed', 'tier', 'palette', 'display', 'element', 'element_policy', 'affixes', 'accessories', 'bones')


# ============================================================================================ the data model
def default_display():
    """the display recipe: the resting mood and weight overrides, a mood cycle [[mood, seconds], ...] with its
    crossfade, and the parameters of bestiary.js's display uniforms (its defaults as of 2026-10-21, after the r4
    review): passing clouds (cloudK rad/m: ~20 cm between fronts; cloudW rad/s; their origin the creature's own
    mantle apex, or clouds.apex [x, y, z] in the bind pose), blue rings (ringScale cells/m, ringR in cell units: 0.24
    keeps neighbours' borders clear at the network's jitter 0.35, 0.27 met them), photophores (strength = the resting
    glow weight, colour sRGB hex, glowScale cells/m, glowRate rad/s); the remix's own iridophores (a zone-masked thin
    film) and papillae (needs a normal pair)"""
    return dict(mood='rest', weights={}, cycle=[], crossfade=0.4,
                clouds=dict(k=32.0, w=4.8), rings=dict(scale=22.0, r=0.24),
                iridophores=None, photophores=None, papillae=None)


def make(base='octopus', **over):
    """a full recipe for a base species with every default filled, then the overrides merged (merge() rules)"""
    if base not in SPECIES:
        raise KeyError(f'unknown base {base!r} (have: {", ".join(SPECIES)})')
    sp = SPECIES[base]
    r = dict(
        version=RECIPE_VERSION, name=base, base=base, family=sp['family'], seed=1, level=1, tier='small',
        role='fauna', spec={}, sculpt=copy.deepcopy(sp['layers']),
        skin={'class': sp['skin_class'], 'patch': {}, 'paint': {}, 'palette_srgb': {}, 'pattern': None,
              'overlay': None},
        palette={}, display=default_display(), parts=copy.deepcopy(sp.get('parts', {})), accessories=[],
        element='normal', element_policy='inherit', affixes=[], bones=[], lineage=[], notes=[])
    if sp.get('display'):
        r['display'] = merge(r['display'], sp['display'])
    return merge(r, over)


def merge(a, b):
    """b over a, returning a new recipe: dicts merge key by key; lists, scalars and nulls in b replace a's (a layer
    list is complete in itself; a null turns a feature off, e.g. display.iridophores)"""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return copy.deepcopy(b)
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalise(r):
    """a possibly partial recipe (hand-written JSON) completed with its base's defaults; a null top-level section means
    the default (normalise(make(...)) is make(...) itself)"""
    base = make(r.get('base', 'octopus'))
    out = merge(base, r)
    for k, v in base.items():
        if out.get(k) is None and v is not None:
            out[k] = copy.deepcopy(v)
    return out


def canonical(r, keys=None):
    sub = {k: r[k] for k in (keys or r.keys()) if k in r}
    return json.dumps(sub, sort_keys=True, separators=(',', ':'), default=_jsonable)


# documentation and provenance keys of a layer: they change nothing the forge builds, so layer comparisons (the plan
# check, crossbreed's picks) and the offline hash ignore them (a hand-written recipe that copies the layers without
# their 'src' strings, as REMIX_EXAMPLES.md prints them, is the base plan, not a new one)
LAYER_DOC_KEYS = ('src', 'origin')


def doc_free(layers):
    return [{k: v for k, v in L.items() if k not in LAYER_DOC_KEYS} if isinstance(L, dict) else L for L in layers]


def layers_sig(layers):
    return canonical({'s': doc_free(layers)})


def _jsonable(x):
    if isinstance(x, (tuple, set)):
        return list(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    raise TypeError(f'not JSON-able: {type(x)}')


def recipe_hash(r, which='all'):
    """a stable hash of the recipe ('all'), of what the forge consumes ('offline': a change there means a rebuild,
    minutes) or of what the runtime applies ('runtime': instant). An element whose tier carries growth geometry joins
    the offline key. The offline key ignores the layers' documentation (LAYER_DOC_KEYS). It hashes the RECIPE: a
    change of the forge's own defaults (octopus.SPEC) is a forge change and rebuilds every creature"""
    r = normalise(r)
    cyb = r.get('cyborg') if isinstance(r.get('cyborg'), dict) else None
    if which == 'offline':
        keys = list(OFFLINE_KEYS)
        el = r['element']
        if el in EL.ELEMENTS and 'growth' in EL.layers_for(el, el_tier(r['tier'])):
            keys += ['element', 'tier']
        # the cyborg section's glow and affixes are runtime (CYBORG_PLAN §6.1): each hash takes its own keys, if any
        rr = dict(r, sculpt=doc_free(r['sculpt']), cyborg={k: v for k, v in (cyb or {}).items()
                                                           if k not in CYBORG_RUNTIME})
        if not rr['cyborg']:
            rr.pop('cyborg')
        s = canonical(rr, keys)
    elif which == 'runtime':
        rr = dict(r, cyborg={k: v for k, v in (cyb or {}).items() if k in CYBORG_RUNTIME})
        if not rr['cyborg']:
            rr.pop('cyborg')
        s = canonical(rr, RUNTIME_KEYS + ('cyborg',))
    else:
        s = canonical(r)
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def layer(r, layer_id):
    for L in r['sculpt']:
        if L['id'] == layer_id:
            return L
    raise KeyError(f'no layer {layer_id!r} in {r.get("name")} (have: {", ".join(L["id"] for L in r["sculpt"])})')


# ============================================================================================ operators
def growth(family, mode='sculpt', size_mm=(4.0, 12.0), proud_mm=None, density=0.1, sites=None, mask=None, seed=None,
           layer_id=None):
    """a GROWTH layer (DESIGN.md growth families): a family from elements.GROWTH_FAMILIES (forge/growth.py's names and
    ids) grown from sites. mode 'sculpt' bakes into the low's maps (features up to a few mm: no silhouette change),
    'mesh' makes growth geometry with its own material (study T's element variants; large and elite tiers)"""
    if family not in EL.GROWTH_FAMILIES:
        raise KeyError(f'unknown growth family {family!r}')
    L = dict(id=layer_id or f'growth_{family}', kind='growth', material=family, mode=mode,
             size=dict(size_mm=list(size_mm)), density=float(density))
    if proud_mm is not None:
        L['size']['proud_mm'] = list(proud_mm)
    if sites:
        L['sites'] = sites
    if mask:
        L['mask'] = mask
    if seed is not None:
        L['seed'] = int(seed)
    return L


def swap_layer(r, layer_id, new, keep_sites=True):
    """a new recipe with layer layer_id replaced by `new` (a layer dict, or a kind name). keep_sites carries the old
    layer's sites, mask and seed, so the new layer grows exactly where the old one did (DESIGN.md: papillae replaced by
    crystal growths at the same patch sites). Locked layers refuse"""
    r = copy.deepcopy(r)
    i = next((k for k, L in enumerate(r['sculpt']) if L['id'] == layer_id), None)
    if i is None:
        raise KeyError(f'no layer {layer_id!r}')
    old = r['sculpt'][i]
    if old.get('locked'):
        raise ValueError(f'layer {layer_id!r} is locked (a carve the meshed topology follows)')
    new = dict(kind=new) if isinstance(new, str) else copy.deepcopy(new)
    if keep_sites:
        for k in ('sites', 'cosite', 'mask', 'seed'):
            if k in old and k not in new:
                new[k] = copy.deepcopy(old[k])
    new.setdefault('id', f'{layer_id}>{new["kind"]}')
    new.setdefault('material', 'skin')
    new['origin'] = f'swap of {layer_id} ({old["kind"]})'
    r['sculpt'][i] = new
    r['notes'] = r.get('notes', []) + [f'swap_layer: {layer_id} ({old["kind"]}) -> {new["id"]} ({new["kind"]})']
    return r


def add_layer(r, new, after=None):
    r = copy.deepcopy(r)
    L = copy.deepcopy(new)
    ids = [x['id'] for x in r['sculpt']]
    if L['id'] in ids:
        raise ValueError(f'duplicate layer id {L["id"]!r}')
    # before the locked carves that must run last (the funnel lumen: craft guide sec. 9)
    if after is not None:
        k = ids.index(after) + 1
    else:
        k = next((i for i, x in enumerate(r['sculpt']) if x['kind'] == 'funnel_lumen'), len(ids))
    r['sculpt'].insert(k, L)
    return r


def remove_layer(r, layer_id):
    r = copy.deepcopy(r)
    L = layer(r, layer_id)
    if L.get('locked'):
        raise ValueError(f'layer {layer_id!r} is locked')
    r['sculpt'] = [x for x in r['sculpt'] if x['id'] != layer_id]
    return r


ELEMENT_POOLS = {
    # study G's random-world helper excludes Player Soul, Moonlight and Dark Gaia unless a planet lists them (study G
    # §4.1) [S]; the weights are [D]
    'study_g': dict(normal=0.40, fire=0.15, ice=0.15, electric=0.15, poison=0.15),
    'special': dict(player_soul=1.0, moonlight=1.0, dark_gaia=1.0),
    'remix': dict(normal=0.20, rust=0.14, verdigris=0.12, crystal=0.14, bismuth=0.12, liquid_metal=0.12,
                  abyssal=0.16),
    'all': dict(normal=0.20, fire=0.08, ice=0.08, electric=0.08, poison=0.08, player_soul=0.02, moonlight=0.04,
                dark_gaia=0.02, rust=0.07, verdigris=0.06, crystal=0.07, bismuth=0.06, liquid_metal=0.06,
                abyssal=0.08),
}


def roll_element(seed, pool='study_g', weights=None):
    """an element name from a pool, deterministic in the seed"""
    return pick_weighted(seed, 'element', weights or ELEMENT_POOLS[pool])


def roll_affixes(seed, role='fauna', tier='small'):
    """study G's affix roll [S]: one affix at 5 % for foes, 1 % for fauna, 5 % for large fauna; else none"""
    cls = role if role == 'foe' else ('fauna_large' if el_tier(tier) in ('large', 'elite') else 'fauna')
    if roll(seed, 'affix.chance') >= EL.AFFIX_CHANCE[cls]:
        return []
    names = list(EL.AFFIXES)
    return [names[min(int(roll(seed, 'affix.pick') * len(names)), len(names) - 1)]]


def resolve_auto(r):
    """element 'auto' / 'auto:<pool>' and affixes 'auto' resolved from the recipe's seed"""
    r = copy.deepcopy(r)
    el = r.get('element', 'normal')
    if isinstance(el, str) and el.startswith('auto'):
        pool = el.split(':', 1)[1] if ':' in el else 'study_g'
        r['element'] = roll_element(r['seed'], pool)
        r['notes'] = r.get('notes', []) + [f'element rolled from seed {r["seed"]} ({pool}): {r["element"]}']
    if r.get('affixes') == 'auto':
        r['affixes'] = roll_affixes(r['seed'], r.get('role', 'fauna'), r.get('tier', 'small'))
        r['notes'] = r.get('notes', []) + [f'affixes rolled from seed {r["seed"]}: {r["affixes"] or "none"}']
    return r


def mutate(r, seed, amount=0.15, sections=('spec', 'palette', 'display')):
    """a deterministic variation: spec numbers x (1 +- amount) inside the species' ranges (coupled keys follow their
    driver: the neck scales with the mutated ML; the end taper stays under t18's slope limit), palette colours jittered
    (hue +-30 x amount degrees, value +-amount), the passing clouds' wavenumber and speed x (1 +- amount)"""
    r = normalise(r)
    out = copy.deepcopy(r)
    sp = SPECIES[r['base']]
    coupled = sp.get('spec_coupled') or {}
    if 'spec' in sections:
        for k, v0 in sp['spec'].items():
            v = r['spec'].get(k, v0)
            rng = sp['spec_ranges'].get(k)
            if rng is None or k in coupled:
                continue
            if isinstance(v, (tuple, list)):
                nv = []
                for i, (vi, ri) in enumerate(zip(v, rng)):
                    f = 1.0 + amount * (2.0 * roll(seed, f'mut.spec.{k}.{i}') - 1.0)
                    nv.append(float(np.clip(vi * f, ri[0], ri[1])))
                out['spec'][k] = nv
            else:
                f = 1.0 + amount * (2.0 * roll(seed, f'mut.spec.{k}') - 1.0)
                out['spec'][k] = float(np.clip(v * f, rng[0], rng[1]))
        # coupled keys: jittered at the forge's scale of their driver, then carried to the mutated driver's
        for k, (drv, comps) in coupled.items():
            if k not in sp['spec'] or sp['spec_ranges'].get(k) is None:
                continue
            k_in = _driver_ratio(r['spec'], sp, drv)
            k_out = _driver_ratio(out['spec'], sp, drv)
            v = list(r['spec'].get(k, sp['spec'][k]))
            nv = []
            for i, (vi, ri) in enumerate(zip(v, sp['spec_ranges'][k])):
                s_in, s_out = (k_in, k_out) if i in comps else (1.0, 1.0)
                f = 1.0 + amount * (2.0 * roll(seed, f'mut.spec.{k}.{i}') - 1.0)
                nv.append(float(np.clip(vi / s_in * f, ri[0], ri[1]) * s_out))
            out['spec'][k] = nv
        # the end taper's joint limit (t18): pull taper_k down inside a slope of 1 (to 0.98) if the two draws crossed it
        if 'taper_s0' in sp['spec'] and 'taper_k' in sp['spec']:
            s0 = out['spec'].get('taper_s0', sp['spec']['taper_s0'])
            kk = out['spec'].get('taper_k', sp['spec']['taper_k'])
            if taper_slope(s0, kk) > 0.98:
                out['spec']['taper_k'] = float(kk * 0.98 / taper_slope(s0, kk))
    if 'palette' in sections:
        for role, e in out['palette'].items():
            c = jitter_rgb(hex_to_lin(e['colour']), seed, f'mut.pal.{role}', 30.0 * amount, amount)
            e['colour'] = EL.hexcode(c)
    if 'display' in sections:
        cl = out['display']['clouds']
        cl['k'] = cl['k'] * (1.0 + amount * (2.0 * roll(seed, 'mut.clouds.k') - 1.0))
        cl['w'] = cl['w'] * (1.0 + amount * (2.0 * roll(seed, 'mut.clouds.w') - 1.0))
    out['notes'] = out.get('notes', []) + [f'mutate(seed {seed}, amount {amount}, {list(sections)})']
    return out


def _driver_ratio(spec_over, sp, drv):
    """a coupled key's scale: the driver's value (the recipe's override, else the forge's) over the forge's"""
    base = float(sp['spec'][drv])
    return float(spec_over.get(drv, base)) / base if base else 1.0


def _transferable(L, family, sp_body, sockets, same_base):
    """can a donor layer grow on the body's family? a species-specific kind only on the same species, a family kind
    only on that family; its regions must exist there (or be generic masks); its sites must be generic, a patch set or
    anatomy the body has, or a socket the body has"""
    dom = SCULPT_KINDS.get(L.get('kind'), {}).get('domain', 'generic')
    if dom == 'species' and not same_base:
        return False, f'{L.get("kind")} is built by the donor species\' own code'
    if dom not in ('generic', 'species') and dom != family:
        return False, f'{L.get("kind")} needs a {dom} body'
    regs = (L.get('mask') or {}).get('regions') or []
    if any(x not in sp_body['regions'] for x in regs):
        return False, f'regions {regs} not on a {family} body'
    sites = L.get('sites', 'scatter')
    if sites in GENERIC_SITES:
        return True, ''
    if sites.startswith('patch:') and sites.split(':', 1)[1] in sp_body['patch_sets']:
        return True, ''
    if sites.startswith('socket:') and sites.split(':', 1)[1] in sockets:
        return True, ''
    if sites.startswith('anatomy:') and sites.split(':', 1)[1] in sp_body['anatomy']:
        return True, ''
    return False, f'sites {sites!r} do not exist on a {family} body'


def crossbreed(a, b, seed=None, name=None):
    """a child of BODY parent a and DONOR parent b. The body plan stays a's (a family generator cannot take another
    family's spec; DESIGN.md: "Remixes swap slots across presets"). Same base: spec numbers blend. Sculpt layers: both
    parents' layers by id, each picked from either parent; donor-only layers join where they can grow on a's family;
    locked layers stay a's. Skin sections, the display, palette zones, part sockets, the accessory set and the element
    are each picked from one parent; affixes unite (at most two). Every choice is roll(child seed, key). The child's
    notes list what was dropped and why"""
    a, b = normalise(a), normalise(b)
    seed = derive_seed(a['seed'], b['seed'], 'cross') if seed is None else int(seed)
    sp_a = SPECIES[a['base']]
    child = copy.deepcopy(a)
    child['name'] = name or f'{a["name"]}_x_{b["name"]}'
    child['seed'] = seed
    child['lineage'] = [a['name'], b['name']]
    notes = []
    pick = lambda key: roll(seed, 'cross.' + key) >= 0.5          # True -> take the donor's
    # spec: same base blends, else the body's
    if a['base'] == b['base']:
        base_spec = sp_a['spec']
        spec = {}
        for k in sorted(set(a['spec']) | set(b['spec'])):
            va, vb = a['spec'].get(k, base_spec.get(k)), b['spec'].get(k, base_spec.get(k))
            t = roll(seed, 'cross.spec.' + k)
            if isinstance(va, (list, tuple)):
                spec[k] = [float(x + (y - x) * t) for x, y in zip(va, vb)]
            elif isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                spec[k] = float(va + (vb - va) * t)
            else:
                spec[k] = copy.deepcopy(vb if t >= 0.5 else va)
        child['spec'] = spec
    elif b['spec']:
        notes.append(f'spec from {b["name"]} ({b["base"]}) dropped: the {a["family"]} generator keeps its own')
    # sculpt layers
    by_a = {L['id']: L for L in a['sculpt']}
    by_b = {L['id']: L for L in b['sculpt']}
    out_layers = []
    for L in a['sculpt']:
        donor = by_b.get(L['id'])
        if donor is not None and not L.get('locked') and layers_sig([donor]) != layers_sig([L]) and \
                pick('layer.' + L['id']):
            M = copy.deepcopy(donor)
            M['origin'] = f'from {b["name"]}'
            out_layers.append(M)
        else:
            out_layers.append(copy.deepcopy(L))
    sockets_a = set(sp_a['sockets'])
    for L in b['sculpt']:
        if L['id'] in by_a or L.get('locked'):
            continue
        ok, why = _transferable(L, a['family'], sp_a, sockets_a, a['base'] == b['base'])
        if not ok:
            notes.append(f'layer {L["id"]} ({L["kind"]}) from {b["name"]} dropped: {why}')
            continue
        M = copy.deepcopy(L)
        M['origin'] = f'from {b["name"]}'
        k = next((i for i, x in enumerate(out_layers) if x['kind'] == 'funnel_lumen'), len(out_layers))
        out_layers.insert(k, M)
    child['sculpt'] = out_layers
    # skin: the patch network stays the body's (the sculpt sites are planned on it); the rest per section
    for sec in ('class', 'paint', 'palette_srgb', 'pattern', 'overlay'):
        if pick('skin.' + sec):
            child['skin'][sec] = copy.deepcopy(b['skin'].get(sec))
    if child['skin']['class'] != a['skin']['class'] and a['base'] != b['base']:
        notes.append(f'skin class {child["skin"]["class"]} from {b["name"]} on a {a["base"]} body')
    # runtime sections
    child['display'] = copy.deepcopy(b['display'] if pick('display') else a['display'])
    zones = sorted(set(a['palette']) | set(b['palette']))
    child['palette'] = {}
    for z in zones:
        src = b if (z in b['palette'] and (z not in a['palette'] or pick('palette.' + z))) else a
        child['palette'][z] = copy.deepcopy(src['palette'][z])
    parts = {}
    for s in sorted(set(a['parts']) | set(b['parts'])):
        take_b = s in b['parts'] and (s not in a['parts'] or pick('part.' + s))
        if take_b and s not in sockets_a:
            notes.append(f'part {b["parts"][s].get("part")} on {s} from {b["name"]} dropped: no {s} on a '
                         f'{a["base"]}')
            take_b = False
        if take_b:
            parts[s] = copy.deepcopy(b['parts'][s])
        elif s in a['parts']:
            parts[s] = copy.deepcopy(a['parts'][s])
    child['parts'] = parts
    child['accessories'] = copy.deepcopy(b['accessories'] if pick('accessories') else a['accessories'])
    child['element'] = b['element'] if pick('element') else a['element']
    aff = list(dict.fromkeys(list(a['affixes'] if isinstance(a['affixes'], list) else []) +
                             list(b['affixes'] if isinstance(b['affixes'], list) else [])))
    child['affixes'] = aff[:2]
    child['notes'] = a.get('notes', []) + [f'crossbreed {a["name"]} (body) x {b["name"]} (donor), seed {seed}'] + notes
    return child


def resolve_parts(r):
    """{socket: row} with every study G slot table resolved for the recipe's level: the rows whose inclusive level band holds
    the level, a weighted pick by roll(seed, 'part.<socket>') (study G §8.2: weighted, seeded picks instead of study G's
    first match, which gave zero variety within a band). A plain entry is its own row; a table with no row for the
    level resolves to None"""
    r = normalise(r)
    out = {}
    for s, entry in r['parts'].items():
        if 'table' not in entry:
            out[s] = copy.deepcopy(entry)
            continue
        rows = [row for row in entry['table'] if row['level'][0] <= r['level'] <= row['level'][1]]
        if not rows:
            out[s] = None
            continue
        w = {str(i): float(row.get('weight', 1.0)) for i, row in enumerate(rows)}
        out[s] = copy.deepcopy(rows[int(pick_weighted(r['seed'], 'part.' + s, w))])
    return out


# ============================================================================================ the runtime block
def _palette_zone(entry, lref):
    """a palette entry {colour: '#rrggbb' (sRGB), strength: 0..1, keep_value: bool} to a zone remap: the zone's hue
    moves to the colour's and, unless keep_value, its mean luminance (lref) to the colour's, the painted variation kept"""
    T = hex_to_lin(entry['colour'])
    LT = float(EL.lum(T))
    val = 1.0 if entry.get('keep_value') else LT / max(lref, 1e-4)
    z = EL.Z(T, entry.get('strength', 1.0), sat=entry.get('sat', 1.0), val=val, rough=entry.get('rough', 0.0))
    return {k: v for k, v in z.items() if k != 'src'}


def resolve_display(d, el_block):
    """the display recipe resolved: the RESTING weights (the mood's, the recipe's overrides, the photophores' strength
    as the glow weight), the cycle and the moods it uses, clouds, rings, iridophores (the recipe's, else the element's),
    photophores (the recipe's, else the element's) with their colour as linear rgb"""
    out = copy.deepcopy(d)
    if out.get('photophores') is None and el_block and el_block.get('photophores'):
        out['photophores'] = copy.deepcopy(el_block['photophores'])
    w = dict(MOODS.get(d.get('mood', 'rest'), MOODS['rest']))
    if out.get('photophores'):
        p = out['photophores']
        w.setdefault('glow', float(p.get('strength', 1.0)))
        if isinstance(p.get('colour'), str):
            p['colour'] = list(hex_to_lin(p['colour']))
    w.update(d.get('weights') or {})
    out['weights'] = w
    out['base'] = dict(w)
    out['cycle'] = [[m, float(s)] for m, s in (d.get('cycle') or [])]
    out['moods'] = copy.deepcopy(MOODS)                  # all of them (tiny), so the runtime's setMood takes any
    out.setdefault('rings', dict(scale=22.0, r=0.24))
    if out.get('iridophores') is None and el_block and el_block.get('irid'):
        out['iridophores'] = copy.deepcopy(el_block['irid'])
    # a named iridophore FAMILY (the beetle's palette data, display.iridophore_families) fills its row in
    ir = out.get('iridophores')
    fam = (out.get('iridophore_families') or {}).get(ir.get('family')) if ir else None
    if fam:
        out['iridophores'] = dict(ir, **copy.deepcopy(fam))
    return out


def fit_from_seat(arch, seat, item_name=None):
    """a remix fit from an accessories SEAT node (work/bestiary/patches/accessories_fit.md §1: a seat_<archetype> child
    of a socket, its TRS the seat frame in the socket's space, extras.fit its data). A hat or helmet seat TABLE
    converts: the row at the depth the forge validated for this item (fit.validated[item].depth), else the table's
    default depth, gives the opening's centre (cx, -depth, cz in the seat frame) and r_mean, the radius of the circle
    with the section's area (the remix seats a round item uniformly; the accessories runtime fits rx and rz apart). A
    glasses seat holds a rig fit (eye centres, standoff, hooks) without the lens points remix.js seats glasses by.
    Returns (fit or None, why not)"""
    f = (seat or {}).get('fit') or {}
    if f.get('archetype') not in (None, arch):
        return None, f'seat_{arch} says archetype {f.get("archetype")!r}'
    if arch in ('hat', 'helmet'):
        rows = f.get('table')
        if not rows:
            return None, f'seat_{arch} carries no seat table'
        cols = list(f.get('table_columns') or ['depth', 'rx', 'rz', 'cx', 'cz', 'r_mean'])
        need = [c for c in ('depth', 'cx', 'cz', 'r_mean') if c not in cols]
        if need:
            return None, f'seat_{arch} table lacks columns {need}'
        T = np.asarray(rows, np.float64)
        ci = {c: i for i, c in enumerate(cols)}
        dep = T[:, ci['depth']]
        d = ((f.get('validated') or {}).get(item_name) or {}).get('depth')
        how = f'validated for {item_name}'
        # (B11) a seat whose forge fit REFUSED this item (the beetle's pronotum seat on the major: the top hat's brim inside the
        # head's crest, b10/r01_rig.py) gives no fit: the table's default depth would seat it anyway
        rf = (f.get('refused') or {}).get(item_name)
        if d is None and rf is not None:
            return None, (f'seat_{arch} refuses {item_name} (its forge fit: the brim {rf.get("brim_min")} m clear, '
                          f'{rf.get("brim_inside")} brim probes inside the creature)')
        if d is None:
            d, how = (f.get('default') or {}).get('depth'), 'the table default'
        if d is None:
            d, how = float(np.median(dep)), 'the table median'
        at = lambda c: float(np.interp(float(d), dep, T[:, ci[c]]))
        q = list(seat.get('rotation') or [0.0, 0.0, 0.0, 1.0])
        off = np.asarray(seat.get('local') or [0.0, 0.0, 0.0], np.float64) + \
            _qmat(q) @ np.array([at('cx'), -float(d), at('cz')])
        return dict(offset=off.round(6).tolist(), rotation=q, radius=at('r_mean'), seat_depth=float(d),
                    seat_depth_from=how), ''
    return None, (f'seat_{arch} holds the accessories rig fit (accessories_fit.md §4: eye centres, standoff, hooks), '
                  f'not the lens points remix.js seats a {arch} by: accessories.js wear() seats it')


def resolve_accessory(a, r, manifest=None):
    """an accessory entry with its archetype, seat and fit resolved: fit from the socket's manifest data (its extras'
    fit[archetype], else its seat_<archetype> node), else the entry's override, else (fit: 'proposal') the species'
    FIT_PROPOSALS; scale = fit[scale_by] / authored[scale_by] x size. The item's authored sizes ride along, so the
    runtime block is complete without the catalog (remix.js sizes its fit proxies from them)"""
    item = ACCESSORIES.get(a['item'])
    out = copy.deepcopy(a)
    if item is None:
        return out
    arch = item['archetype']
    out['archetype'] = arch
    out['authored'] = copy.deepcopy(item.get('authored', {}))
    seat = a.get('socket') or (('bone:' + a['bone']) if a.get('bone') else None)
    prop = FIT_PROPOSALS.get(r['base'], {}).get(arch)
    if seat is None:
        seat = SPECIES[r['base']].get('seats', {}).get(arch)
    out['seat'] = seat
    fit = None
    src = None
    if manifest is not None and seat and not seat.startswith('bone:'):
        sd = (manifest.get('sockets') or {}).get(seat) or {}
        fit = (sd.get('fit') or {}).get(arch)
        src = 'socket' if fit else None
        if fit is None and arch in (sd.get('seats') or {}):
            fit, why = fit_from_seat(arch, sd['seats'][arch], a['item'])
            src = 'seat' if fit else None
            if why:
                out['seat_note'] = why
    if fit is None and isinstance(a.get('fit'), dict):
        fit, src = a['fit'], 'override'
    if fit is None and a.get('fit') == 'proposal' and prop is not None and prop['seat'] == seat:
        fit, src = {k: v for k, v in prop.items() if k != 'seat'}, 'proposal'
    out['fit'] = copy.deepcopy(fit)
    out['fit_source'] = src
    if fit:
        key = ARCHETYPES[arch]['scale_by']
        if key in fit and key in item['authored']:
            out['scale'] = float(fit[key]) / float(item['authored'][key]) * float(a.get('size', 1.0))
    return out


def resolve_runtime(r, manifest=None):
    """the JSON block runtime/remix.js applies: zones (the species' mask map with reference luminances), palette and
    element zone remaps, glow (with its gain), surface, display (moods, cycle, clouds, iridophores, photophores),
    accessories with fits, affixes, bone ops, the jitter amounts and the seed. Per-instance jitter is applied in the
    engine (remix.js applyJitter; apply_jitter here is its twin)"""
    r = resolve_auto(normalise(r))
    sp = SPECIES[r['base']]
    zones = copy.deepcopy((manifest or {}).get('zones') or sp['zones'])
    palette = {}
    for role, e in r['palette'].items():
        if role in EL.ROLES:
            palette[role] = _palette_zone(e, zones.get(role, {}).get('lref', 0.2))
        elif role in ('eye', 'part'):
            palette[role] = _palette_zone(e, e.get('lref', 0.25))
    el = EL.runtime_block(r['element'], el_tier(r['tier'])) if r['element'] in EL.ELEMENTS else None
    block = dict(
        version=RECIPE_VERSION, name=r['name'], base=r['base'], family=r['family'], seed=int(r['seed']),
        tier=r['tier'], glow_scale=EL.GLOW_SCALE, envelope=list(EL.ENVELOPE), zones=zones, palette=palette,
        element=el, element_policy=r['element_policy'], display=resolve_display(r['display'], el),
        accessories=[resolve_accessory(a, r, manifest) for a in r['accessories']],
        parts=resolve_parts(r),
        affixes=[dict(name=a, **{k: v for k, v in EL.AFFIXES[a].items()}) for a in r['affixes']
                 if a in EL.AFFIXES],
        bones=copy.deepcopy(r['bones']),
        jitter=dict(palette=dict(hue_deg=6.0, val=0.06), element=dict(hue_deg=3.0, val=0.04),
                    clouds=dict(k=0.15, w=0.20), glow=dict(rate=0.15)),
        recipe_hash=dict(offline=recipe_hash(r, 'offline'), runtime=recipe_hash(r, 'runtime')))
    if r.get('cyborg') and manifest is not None:
        block['cyborg'] = resolve_cyborg_runtime(r, manifest)        # (C5b: the parts bestiary.js mounts)
    return block


def runtime_assets(block, assets=None, out_dir=None, log=print, feed_dir=None):
    """ASSEMBLY (C5e, the lead's C5e call 4): the engine's asset map for a runtime block (resolve_runtime's).
    `assets` holds what is prebuilt (asset name -> path: the base's glb, the eye implant, the mech tentacle); every
    cyborg HOSE part is built ON DEMAND for its seed by the forge (forge/cyborg_cable.py assemble_assets: through
    cyborg_hose.hose_for_seed, the hose drawn in that seed's rest pose with the cable's data in its extras, cached
    by seed and its inputs' sha1s, so a seed no build holds is built once and then read), into out_dir (default
    cyborg_hose.HOSE_DIR). Every cyborg FEED part (C3e: feed_parts) is mapped to its look's prebuilt glb in feed_dir
    (default cyborg_feed.FEED_DIR) by forge/cyborg_feed.py feed_assets, which checks the build's record against the
    part's look and rebuilds a stale build from its run. The forge (warp, on the CPU) is imported here only, so a
    recipe without a hose or a feed never loads it. Returns the map with every hose's and feed part's name"""
    cparts = (block.get('cyborg') or {}).get('parts', [])
    out = dict(assets or {})
    if any(p.get('kind') == 'feed' for p in cparts):
        from eidoverse.bestiary.forge import cyborg_feed as CF
        out = CF.feed_assets(block, out, log=log, **({} if feed_dir is None else dict(out_dir=feed_dir)))
    if not any(p.get('kind') == 'hose' for p in cparts):
        return out
    from eidoverse.bestiary.forge import cyborg_cable as CC
    return CC.assemble_assets(block, out, out_dir=out_dir, log=log)


def apply_jitter(block, seed):
    """the per-instance variation (remix.js applyJitter twins it): palette and element zone targets jittered, the
    clouds' wavenumber and speed and the glow's rate scaled; every draw is roll(seed, key)"""
    b = copy.deepcopy(block)
    J = b['jitter']
    for role in sorted(b['palette']):
        z = b['palette'][role]
        if z.get('target') is not None:
            z['target'] = list(jitter_rgb(z['target'], seed, 'pal.' + role, J['palette']['hue_deg'],
                                          J['palette']['val']))
    if b.get('element'):
        for role in sorted(b['element']['zones']):
            z = b['element']['zones'][role]
            if z.get('target') is not None and z.get('absolute', 0.0) < 0.5:
                z['target'] = list(jitter_rgb(z['target'], seed, 'el.' + role, J['element']['hue_deg'],
                                              J['element']['val']))
        g = b['element'].get('glow')
        if g:
            g['rate'] = g['rate'] * (1.0 + J['glow']['rate'] * (2.0 * roll(seed, 'glow.rate') - 1.0))
    cl = b['display']['clouds']
    cl['k'] = cl['k'] * (1.0 + J['clouds']['k'] * (2.0 * roll(seed, 'clouds.k') - 1.0))
    cl['w'] = cl['w'] * (1.0 + J['clouds']['w'] * (2.0 * roll(seed, 'clouds.w') - 1.0))
    b['display']['cycle_offset'] = roll(seed, 'display.cycle')
    return b


# ============================================================================================ manifests
def _qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def uv_raster(uv, tris, res=256):
    """a boolean raster of the triangles' UV footprint (glTF UV space: v runs down the image)"""
    from PIL import Image, ImageDraw
    img = Image.new('L', (res, res), 0)
    d = ImageDraw.Draw(img)
    P = np.asarray(uv, np.float64) * res
    for t in np.asarray(tris).reshape(-1, 3):
        d.polygon([tuple(P[t[0]]), tuple(P[t[1]]), tuple(P[t[2]])], fill=1, outline=1)
    return np.asarray(img, bool)


def uv_match(part, family):
    """study-G precision and recall of a part's UV raster on a family's coverage raster"""
    inter = float((part & family).sum())
    return inter / max(float(part.sum()), 1.0), inter / max(float(family.sum()), 1.0)


def _channels(text):
    """'R thin, G ventral, B sucker (...), A patch random' -> {'r': 'thin', ...}"""
    out = {}
    for item in (text or '').split(','):
        m = re.match(r'\s*([RGBA])\s+(.+)', item)
        if m:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def manifest_from_glb(path, uv_res=256):
    """a build MANIFEST read from a forge glb: bones, sockets (parent joint, local and world transforms, fit data from
    node extras), materials (kind, UV family, mask packs, channel meanings, triangles), parts (non-skin materials and
    the socket each seats on), UV rasters per material (for the measured UV check), budget. A structured manifest in
    the scene extras (extras.bestiary.manifest) wins where present; otherwise what t13 writes today is read and the
    inferred fields are listed in 'inferred'"""
    if __package__ in (None, ''):
        from eidoverse.bestiary.forge import gltf as G
    else:
        from ..forge import gltf as G
    R = G.read(path)
    j = R['json']
    nodes = j['nodes']
    parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    world = {}

    def wm(i):
        if i in world:
            return world[i]
        n = nodes[i]
        M = np.eye(4)
        if 'rotation' in n:
            M[:3, :3] = _qmat(n['rotation'])
        if 'translation' in n:
            M[:3, 3] = n['translation']
        if 'scale' in n:
            M[:3, :3] = M[:3, :3] @ np.diag(n['scale'])
        world[i] = M if i not in parent else wm(parent[i]) @ M
        return world[i]

    ex = (j.get('extras') or {}).get('bestiary') or {}
    inferred = []
    skin = j['skins'][0] if j.get('skins') else {'joints': []}
    bones = [nodes[k]['name'] for k in skin['joints']]
    joint_set = set(skin['joints'])
    bone_parent = {nodes[k]['name']: (nodes[parent[k]]['name'] if k in parent and parent[k] in joint_set else None)
                   for k in skin['joints']}
    sockets = {}
    for i, n in enumerate(nodes):
        if not n.get('name', '').startswith('socket_'):
            continue
        p = parent.get(i)
        W = wm(i)
        sockets[n['name']] = dict(bone=nodes[p].get('name') if p is not None else None,
                                  local=list(n.get('translation', [0.0, 0.0, 0.0])),
                                  rotation=list(n.get('rotation', [0.0, 0.0, 0.0, 1.0])),
                                  world=W[:3, 3].round(6).tolist(), frame=W[:3, :3].round(6).tolist(),
                                  fit=((n.get('extras') or {}).get('fit') or {}), seats={},
                                  # the socket's KIND (remix/slots.py), written by its generator; None on an old glb
                                  slot=(n.get('extras') or {}).get('slot'))
    # SEAT nodes (the accessories fit system, work/bestiary/patches/accessories_fit.md §1): seat_<archetype> children of
    # a socket, their TRS the seat frame in the socket's space, extras.fit the seat's data (resolve_accessory reads them)
    for i, n in enumerate(nodes):
        m = re.match(r'^seat_(\w+)$', n.get('name', ''))
        if not m:
            continue
        p = parent.get(i)
        pname = nodes[p].get('name') if p is not None else None
        if pname not in sockets:
            inferred.append(f'{n["name"]}: not under a socket_* node (parent {pname!r}); ignored')
            continue
        sockets[pname]['seats'][m.group(1)] = dict(local=list(n.get('translation', [0.0, 0.0, 0.0])),
                                                   rotation=list(n.get('rotation', [0.0, 0.0, 0.0, 1.0])),
                                                   fit=((n.get('extras') or {}).get('fit') or {}))
    materials = {}
    for mi, m in enumerate(j['materials']):
        mx = m.get('extras') or {}
        kind = mx.get('bestiary') if isinstance(mx.get('bestiary'), str) else 'unknown'
        packs = []
        if 'KHR_materials_volume' in (m.get('extensions') or {}):
            packs.append('masks')
        if 'emissiveTexture' in m:
            packs.append('display')
        if 'uv_family' not in mx:
            inferred.append(f'material {m["name"]}: uv_family = its own name (one texture set per material)')
        materials[m['name']] = dict(index=mi, kind=kind, uv_family=mx.get('uv_family', m['name']), packs=packs,
                                    channels=dict(masks=_channels(mx.get('masks_channels')),
                                                  display=_channels(mx.get('display_channels'))),
                                    tris=0, extras=mx)
    uv = {}
    tris_total = 0
    for mesh in j['meshes']:
        for prim in mesh['primitives']:
            mname = j['materials'][prim['material']]['name']
            F = R['accessor'](prim['indices']).reshape(-1, 3)
            materials[mname]['tris'] += len(F)
            tris_total += len(F)
            if uv_res and 'TEXCOORD_0' in prim['attributes']:
                UV = R['accessor'](prim['attributes']['TEXCOORD_0'])
                ras = uv_raster(UV, F, uv_res)
                uv[mname] = ras if mname not in uv else (uv[mname] | ras)
    parts = {}
    for name, m in materials.items():
        if m['kind'] in ('skin', 'unknown'):
            continue
        seats = re.findall(r'socket_\w+', str(m['extras'].get('part', '')))
        if not seats:
            # rigid parts sit on the sockets of the joint they are bound to (the eyes: eye_L / eye_R)
            if m['kind'] == 'eye':
                seats = [s for s in sockets if s.startswith('socket_eye_')]
            inferred.append(f'part {name}: seats {seats} inferred from its kind')
        else:
            inferred.append(f'part {name}: seat parsed from the material extras text')
        parts[name] = dict(kind=m['kind'], material=name, uv_family=m['uv_family'], seats=seats, tris=m['tris'])
    try:
        src = os.path.relpath(path, REPO).replace('\\', '/')
    except ValueError:                       # another drive
        src = path
    # the CYBORG slot data (remix/slots.py): the scene's chain and region records by name, and the joints' bind-pose
    # positions (G5's head region)
    recs = lambda key: {c['name']: {k: v for k, v in c.items() if k != 'name'} for c in (ex.get(key) or [])
                        if isinstance(c, dict) and 'name' in c}
    man = dict(manifest=1, source=src, species=ex.get('species'), family=ex.get('family'), units=ex.get('units'), up=ex.get('up'),
               forward=ex.get('forward'), bones=bones, bone_parent=bone_parent, sockets=sockets,
               materials={k: {kk: vv for kk, vv in v.items() if kk != 'extras'} for k, v in materials.items()},
               parts=parts, uv=uv, uv_res=uv_res, budget=dict(tris=tris_total, joints=len(bones)),
               chains=recs('chains'), regions=recs('regions'),
               bone_world={nodes[k]['name']: wm(k)[:3, 3].round(6).tolist() for k in skin['joints']},
               inferred=inferred)
    if isinstance(ex.get('manifest'), dict):
        man = merge(man, ex['manifest'])
    return man


# ============================================================================================ the validator
def P(severity, code, where, message):
    return dict(severity=severity, code=code, where=where, message=message)


def _seed_ok(v):
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 2147483647


def _check_schema(r, out):
    for k in r:
        if k not in RECIPE_KEYS:
            out.append(P('warning', 'recipe.unknown_key', k, f'unknown top-level key {k!r} (ignored by the build)'))
    if r['base'] not in SPECIES:
        out.append(P('error', 'recipe.base', 'base', f'unknown base species {r["base"]!r}'))
        return False
    sp = SPECIES[r['base']]
    if sp['status'] != 'built':
        out.append(P('missing', 'recipe.base_unbuilt', 'base',
                     f'base {r["base"]!r} ({sp["family"]}) has no generator yet: ' + '; '.join(sp.get('notes', []))))
    if r['family'] not in FAMILIES:
        out.append(P('error', 'recipe.family', 'family', f'unknown family {r["family"]!r}'))
    elif r['family'] != sp['family']:
        out.append(P('error', 'recipe.family', 'family', f'family {r["family"]!r} but base {r["base"]!r} is '
                                                           f'{sp["family"]!r}'))
    if not _seed_ok(r['seed']):
        out.append(P('error', 'recipe.seed', 'seed', f'seed must be an int in [0, 2^31): {r["seed"]!r}'))
    if not (isinstance(r['level'], int) and 0 <= r['level'] <= 200):
        out.append(P('error', 'recipe.level', 'level', f'level must be an int 0-200 (study G bands): {r["level"]!r}'))
    if r['tier'] not in TIERS:
        out.append(P('error', 'recipe.tier', 'tier', f'unknown tier {r["tier"]!r} (have {TIERS})'))
    if r['role'] not in ROLES:
        out.append(P('error', 'recipe.role', 'role', f'unknown role {r["role"]!r} (have {ROLES})'))
    return True


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_spec(r, out, caps):
    sp = SPECIES[r['base']]
    coupled = sp.get('spec_coupled') or {}
    for k, v in r['spec'].items():
        where = f'spec.{k}'
        if k == 'arm_count' and r['base'] == 'octopus':
            if not caps.get('arm_count_param') and v != 8:
                out.append(P('missing', 'needs.arm_count_param', where,
                             f'arm_count {v}: ' + CAP_TEXT['arm_count_param']))
            continue
        if k not in sp['spec']:
            out.append(P('error', 'spec.unknown', where, f'{k!r} is not a {r["base"]} generator key '
                                                        f'(have: {", ".join(sp["spec"])})'))
            continue
        rng = sp['spec_ranges'].get(k)
        if rng is None or k in coupled:          # coupled keys: checked below, against their driver
            continue
        vals = v if isinstance(v, (list, tuple)) else [v]
        rngs = rng if isinstance(rng[0], (list, tuple)) else [rng]
        if len(vals) != len(rngs):
            out.append(P('error', 'spec.shape', where, f'{k} expects {len(rngs)} values, got {len(vals)}'))
            continue
        for x, (lo, hi) in zip(vals, rngs):
            if not _num(x) or not (lo <= x <= hi):
                out.append(P('warning', 'spec.range', where, f'{k} = {x} outside the remix range [{lo}, {hi}]: the '
                                                             f'forge gates decide'))
    # COUPLED keys (the octopus's neck scales with ML): the effective value, the recipe's or else the forge default,
    # judged at the forge's scale of its driver
    for k, (drv, comps) in coupled.items():
        if k not in sp['spec'] or (k not in r['spec'] and drv not in r['spec']) or not _num(r['spec'].get(drv, 1.0)):
            continue
        rng = sp['spec_ranges'].get(k)
        v = r['spec'].get(k, sp['spec'][k])
        ratio = _driver_ratio(r['spec'], sp, drv)
        vals = v if isinstance(v, (list, tuple)) else [v]
        rngs = rng if isinstance(rng[0], (list, tuple)) else [rng]
        if len(vals) != len(rngs):
            out.append(P('error', 'spec.shape', f'spec.{k}', f'{k} expects {len(rngs)} values, got {len(vals)}'))
            continue
        src = 'the recipe\'s' if k in r['spec'] else f'the forge default, not scaled with {drv}'
        for i, (x, (lo, hi)) in enumerate(zip(vals, rngs)):
            xn = x / ratio if (i in comps and _num(x)) else x
            if not _num(x) or not (lo <= xn <= hi):
                out.append(P('warning', 'spec.coupled', f'spec.{k}',
                             f'{k}[{i}] = {x} ({src}) must scale with {drv} (x{ratio:.3f}): at the forge {drv} it is '
                             f'{xn if not _num(xn) else round(xn, 5)}, outside [{lo}, {hi}] (the neck fills the waist to '
                             'the head\'s section, which scales with ML)'))
    # the END TAPER's slope (t18): taper_s0 and taper_k act together
    if 'taper_s0' in sp['spec'] and 'taper_k' in sp['spec'] and ('taper_s0' in r['spec'] or 'taper_k' in r['spec']):
        s0 = r['spec'].get('taper_s0', sp['spec']['taper_s0'])
        kk = r['spec'].get('taper_k', sp['spec']['taper_k'])
        if _num(s0) and _num(kk) and taper_slope(s0, kk) > 1.0 + 1e-9:
            out.append(P('warning', 'spec.taper_slope', 'spec.taper_s0+taper_k',
                         f'the end taper {s0} / {kk} peaks at a slope of ~{taper_slope(s0, kk):.2f} (above 1 the sweep\'s '
                         'radius falls faster than its axis advances; t18 measured ~1.6 at 0.93 / 0.55: terraces and a '
                         f'ledge). Keep taper_k <= {(1.0 - s0) * TAPER_T18["k"] / (1.0 - TAPER_T18["s0"]) / TAPER_T18["slope"]:.3f} '
                         f'at taper_s0 {s0}'))
    # ML against the block-out's absolute parts
    if 'ML' in r['spec'] and sp.get('ml_absolute') and _num(r['spec']['ML']):
        ratio = _driver_ratio(r['spec'], sp, 'ML')
        if abs(ratio - 1.0) > 0.10:
            out.append(P('warning', 'spec.ml_absolute', 'spec.ML',
                         f'ML x{ratio:.2f} scales the body radius, the body axis and the eye mounds, not '
                         + ', '.join(sp['ml_absolute']) + ' (octopus.build_sdf): the body moves against them; the cage '
                         'and bake gates decide'))


def _check_layers(r, out, caps):
    sp = SPECIES[r['base']]
    ids = [L.get('id') for L in r['sculpt']]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        out.append(P('error', 'sculpt.duplicate_id', f'sculpt.{d}', f'layer id {d!r} appears {ids.count(d)} times'))
    for L in sp['layers']:
        if L.get('locked') and L['id'] not in ids:
            out.append(P('error', 'sculpt.locked_removed', f'sculpt.{L["id"]}',
                         f'locked layer {L["id"]!r} ({L["kind"]}) is missing: it is a carve the meshed topology follows'))
    site_users = {}
    for i, L in enumerate(r['sculpt']):
        where = f'sculpt.{L.get("id", i)}'
        for k in L:
            if k not in LAYER_KEYS:
                out.append(P('warning', 'sculpt.unknown_key', where, f'unknown layer key {k!r}'))
        kind = SCULPT_KINDS.get(L.get('kind'))
        if kind is None:
            out.append(P('error', 'sculpt.kind', where, f'unknown layer kind {L.get("kind")!r}'))
            continue
        if kind['domain'] not in ('generic', 'species') and kind['domain'] != r['family']:
            out.append(P('error', 'sculpt.domain', where, f'{L["kind"]} layers need a {kind["domain"]} body, this is '
                                                          f'{r["family"]}'))
        for need in kind.get('needs', []):
            if not caps.get(need):
                out.append(P('missing', f'needs.{need}', where, f'{L["kind"]} layer: ' + CAP_TEXT[need]))
        mat = L.get('material', 'skin')
        if mat not in EL.GROWTH_FAMILIES:
            out.append(P('error', 'sculpt.material', where, f'unknown material id {mat!r}'))
        elif mat != 'skin' and not caps.get('material_ids') and 'material_ids' not in kind.get('needs', []):
            out.append(P('missing', 'needs.material_ids', where, f'material {mat!r}: ' + CAP_TEXT['material_ids']))
        if L.get('kind') == 'growth':
            if L.get('mode', 'sculpt') == 'mesh':
                if not caps.get('growth_mesh'):
                    out.append(P('missing', 'needs.growth_mesh', where, CAP_TEXT['growth_mesh']))
                if el_tier(r['tier']) not in ('large', 'elite'):
                    out.append(P('warning', 'sculpt.growth_tier', where, f'growth meshes are a large / elite reward '
                                                                         f'(study G sec. 8.3); tier is {r["tier"]}'))
            # the faceted families: growth.py pairs them with a prism or hopper preset (elements reads it); an unknown
            # material is reported above (sculpt.material), not raised here
            if EL.GROWTH_FAMILIES.get(mat, {}).get('shape') in ('prism6', 'hopper') and not caps.get('hexprism_stroke'):
                out.append(P('missing', 'needs.hexprism_stroke', where,
                             f'{mat} facets: ' + CAP_TEXT['hexprism_stroke']))
        regs = (L.get('mask') or {}).get('regions') or []
        for g in regs:
            if g not in sp['regions']:
                out.append(P('error', 'sculpt.region', where, f'region {g!r} does not exist on a {r["base"]} '
                                                              f'(have: {", ".join(sp["regions"])})'))
        sites = L.get('sites', 'scatter')
        ok = sites in GENERIC_SITES or (sites.startswith('patch:') and sites[6:] in sp['patch_sets']) or \
            (sites.startswith('anatomy:') and sites[8:] in sp['anatomy']) or sites.startswith('socket:')
        if not ok:
            out.append(P('error', 'sculpt.sites', where, f'sites {sites!r} do not exist on a {r["base"]}'))
        if kind['mode'] == 'add' and L.get('density', 1.0) > 0 and sites.startswith('patch:'):
            site_users.setdefault(sites, []).append((L['id'], L.get('cosite') or L['id']))
    for sites, users in site_users.items():
        groups = {g for _, g in users}
        if len(groups) > 1:
            ids = [i for i, _ in users]
            out.append(P('warning', 'sculpt.site_collision', f'sculpt.{"+".join(ids)}',
                         f'{len(ids)} adding layers on {sites} that were not planned together ({sorted(groups)}): they '
                         'land on the same patch centres (thin one out, give them disjoint masks, or co-plan them)'))
    if layers_sig(r['sculpt']) != layers_sig(sp['layers']) and not caps.get('layer_list_plan'):
        out.append(P('missing', 'needs.layer_list_plan', 'sculpt', 'the layer list differs from the base\'s plan: '
                     + CAP_TEXT['layer_list_plan']))


def _check_skin(r, out, caps):
    sk = r['skin']
    if sk.get('palette_srgb') and not caps.get('skin_palette_params'):
        out.append(P('missing', 'needs.skin_palette_params', 'skin.palette_srgb', CAP_TEXT['skin_palette_params']))
    if sk.get('pattern') and not caps.get('skin_pattern_params'):
        out.append(P('missing', 'needs.skin_pattern_params', 'skin.pattern',
                     f'pattern {sk["pattern"]!r}: ' + CAP_TEXT['skin_pattern_params']))
    for k in (sk.get('paint') or {}):
        if k not in OCTOPUS_PAINT and r['base'] == 'octopus':
            out.append(P('error', 'skin.paint', f'skin.paint.{k}', f'octopus_skin.run reads {list(OCTOPUS_PAINT)} '
                                                                   f'only, not {k!r}'))
    if sk.get('class') != SPECIES[r['base']]['skin_class']:
        out.append(P('warning', 'skin.class', 'skin.class', f'skin class {sk.get("class")!r} on a {r["base"]} built '
                                                            f'with {SPECIES[r["base"]]["skin_class"]!r}: the material '
                                                            f'pass is the base\'s'))


def _check_element(r, out, caps):
    el = r['element']
    if not (isinstance(el, str) and (el in EL.ELEMENTS or el.startswith('auto'))):
        out.append(P('error', 'element.unknown', 'element', f'unknown element {el!r} (have: {", ".join(EL.ELEMENTS)})'))
    elif el in EL.ELEMENTS:
        lay = EL.layers_for(el, el_tier(r['tier']))
        e = EL.ELEMENTS[el]
        if 'growth' in lay and not caps.get('growth_mesh'):
            out.append(P('missing', 'needs.growth_mesh', 'element',
                         f'{el} at tier {r["tier"]} grows {e["growth"]["family"]}: ' + CAP_TEXT['growth_mesh']))
        if e.get('glow') and not caps.get('glow_channel'):
            out.append(P('warning', 'element.glow_mask', 'element', 'the glow mask is DERIVED at runtime from the '
                                                                    'masks and display packs (no baked glow channel)'))
    if r['element_policy'] not in ELEMENT_POLICIES:
        out.append(P('error', 'element.policy', 'element_policy', f'{r["element_policy"]!r} not in {ELEMENT_POLICIES}'))
    if r['affixes'] != 'auto':
        for a in r['affixes']:
            if a not in EL.AFFIXES:
                out.append(P('error', 'element.affix', f'affixes.{a}', f'unknown affix {a!r} '
                                                                       f'(have: {", ".join(EL.AFFIXES)})'))
        if len(r['affixes']) > 2:
            out.append(P('warning', 'element.affix_count', 'affixes', f'{len(r["affixes"])} affixes (study G rolls one)'))


def _check_display(r, out, caps):
    d = r['display']
    # the mood cycle: [[mood, seconds > 0], ...] (remix.js moodWeights divides by the cycle's total: zero is NaN)
    cyc = d.get('cycle') or []
    if not isinstance(cyc, (list, tuple)):
        out.append(P('error', 'display.cycle', 'display.cycle', f'cycle must be [[mood, seconds], ...], got {cyc!r}'))
        cyc = []
    good = []
    for i, c in enumerate(cyc):
        if not (isinstance(c, (list, tuple)) and len(c) == 2 and isinstance(c[0], str) and _num(c[1])):
            out.append(P('error', 'display.cycle', f'display.cycle[{i}]', f'{c!r} is not [mood, seconds]'))
            continue
        if c[1] <= 0:
            out.append(P('error', 'display.cycle', f'display.cycle[{i}]', f'{c[0]} lasts {c[1]} s: every mood in a '
                                                                          'cycle must last > 0 s'))
        good.append(c)
    cf = d.get('crossfade', 0.4)
    if not (_num(cf) and cf >= 0.0):
        out.append(P('error', 'display.crossfade', 'display.crossfade', f'crossfade {cf!r} must be >= 0 s'))
    cl, rg = d.get('clouds') or {}, d.get('rings') or {}
    for name, val, ok, why in (('clouds.k', cl.get('k', 32.0), lambda x: x > 0, 'a wavenumber > 0 rad/m'),
                               ('clouds.w', cl.get('w', 4.8), lambda x: True, 'a speed in rad/s'),
                               ('rings.scale', rg.get('scale', 22.0), lambda x: x > 0, 'cells per metre > 0'),
                               ('rings.r', rg.get('r', 0.24), lambda x: 0.0 < x < 0.5,
                                'a ring radius in cell units, 0-0.5')):
        if not (_num(val) and ok(val)):
            out.append(P('error', 'display.param', f'display.{name}', f'{name} = {val!r}: {why}'))
    ap = cl.get('apex')
    if ap is not None and not (isinstance(ap, (list, tuple)) and len(ap) == 3 and all(_num(x) for x in ap)):
        out.append(P('error', 'display.param', 'display.clouds.apex',
                     f'clouds.apex = {ap!r}: a bind-pose point [x, y, z] in m (default: the creature\'s mantle apex)'))
    if 'y' in cl:
        out.append(P('error', 'display.param', 'display.clouds.y',
                     'clouds.y (a crown height) is gone: the fronts start at the mantle apex (clouds.apex)'))
    for m in [d.get('mood', 'rest')] + [c[0] for c in good]:
        if m not in MOODS:
            out.append(P('error', 'display.mood', 'display', f'unknown mood {m!r} (have: {", ".join(MOODS)})'))
    for k in (d.get('weights') or {}):
        if k not in DISPLAY_KEYS:
            out.append(P('error', 'display.weight', f'display.weights.{k}', f'unknown display weight {k!r}'))
    if d.get('papillae') and not caps.get('papillae_normal_pair'):
        out.append(P('missing', 'needs.papillae_normal_pair', 'display.papillae', CAP_TEXT['papillae_normal_pair']))
    # the passing clouds, the blue rings and the photophores need the bind-pose position (three r184's SkinningNode
    # overwrites positionLocal with the SKINNED one: patterns read there slide through the skin in motion); bestiary.js
    # reads positionGeometry (display_coords), and a runtime without it gets this warning
    el = EL.ELEMENTS.get(r['element']) if isinstance(r['element'], str) else None
    moods = [d.get('mood', 'rest')] + [c[0] for c in good]
    weights = dict(d.get('weights') or {})
    procedural = [k for k in ('clouds', 'rings', 'glow') if weights.get(k) or any(MOODS.get(m, {}).get(k)
                                                                                for m in moods)]
    if d.get('photophores') or (el and el.get('photophores')):
        procedural.append('photophores')
    if procedural and not caps.get('display_coords'):
        out.append(P('warning', 'display.posed_space', 'display',
                     f'{sorted(set(procedural))} are evaluated in positionLocal (skinned in three r184): they slide '
                     'through the skin as the arms move; ' + CAP_TEXT['display_coords']))
    if d.get('photophores') and set(d['photophores']) - {'strength', 'colour', 'scale', 'rate'}:
        out.append(P('error', 'display.photophores', 'display.photophores',
                     f'unknown photophore keys {sorted(set(d["photophores"]) - {"strength", "colour", "scale", "rate"})}'
                     ' (bestiary.js drives strength, colour, glowScale and glowRate)'))
    ir = d.get('iridophores')
    if ir and ir.get('zone') not in EL.ROLES + ('eyering', 'spots'):
        out.append(P('error', 'display.iridophores', 'display.iridophores', f'zone {ir.get("zone")!r}'))
    if ir and ir.get('family') is not None and ir['family'] not in (d.get('iridophore_families') or {}):
        out.append(P('error', 'display.iridophores', 'display.iridophores.family',
                     f'family {ir["family"]!r} (have: {sorted(d.get("iridophore_families") or {})})'))


PALETTE_ROLES = EL.ROLES + ('eye', 'part')
PALETTE_KEYS = ('colour', 'strength', 'sat', 'keep_value', 'rough', 'lref')


def _check_palette(r, out):
    """palette entries: {role: {colour: '#rrggbb' (sRGB), strength 0-1, sat, keep_value, rough, lref}} on the zone roles
    or the eye / part materials (resolve_runtime drops any other role; remix.js ctl.palette takes the same entries)"""
    pal = r.get('palette')
    if not pal:
        return
    if not isinstance(pal, dict):
        out.append(P('error', 'palette.entry', 'palette', f'palette must be {{role: entry}}, got {type(pal).__name__}'))
        return
    for role, e in pal.items():
        where = f'palette.{role}'
        if role not in PALETTE_ROLES:
            out.append(P('error', 'palette.role', where, f'unknown palette role {role!r} (have: '
                                                         f'{", ".join(PALETTE_ROLES)}): the runtime would drop it'))
        if not isinstance(e, dict) or 'colour' not in e:
            out.append(P('error', 'palette.entry', where, 'a palette entry is {colour: "#rrggbb", strength, sat, '
                                                          'keep_value, rough}'))
            continue
        if not (isinstance(e['colour'], str) and HEX_RE.match(e['colour'])):
            out.append(P('error', 'palette.colour', where, f'colour {e["colour"]!r} is not an sRGB hex #rrggbb'))
        for k, lo, hi in (('strength', 0.0, 1.0), ('sat', 0.0, 4.0), ('lref', 1e-3, 1.0), ('rough', -1.0, 1.0)):
            if k in e and not (_num(e[k]) and lo <= e[k] <= hi):
                out.append(P('error', 'palette.value', where, f'{k} {e[k]!r} outside [{lo}, {hi}]'))
        for k in e:
            if k not in PALETTE_KEYS:
                out.append(P('warning', 'palette.unknown_key', where, f'unknown palette key {k!r} (ignored)'))


def _check_manifest(r, man, out):
    sp = SPECIES[r['base']]
    if man.get('species') and man['species'] != r['base']:
        out.append(P('error', 'manifest.species', 'manifest', f'the manifest is a {man["species"]!r}, the recipe '
                                                              f'builds on {r["base"]!r}'))
    if man.get('family') and man['family'] != r['family']:
        out.append(P('error', 'manifest.family', 'manifest', f'the manifest is {man["family"]!r}, the recipe '
                                                             f'{r["family"]!r}'))
    bones = set(man.get('bones', []))
    for s, d in man.get('sockets', {}).items():
        if d.get('bone') not in bones:
            out.append(P('error', 'manifest.socket_bone', s, f'{s} hangs on {d.get("bone")!r}, which is not a joint '
                                                             f'of the skin'))
        w = d.get('world')
        if w is not None:
            if re.search(r'_L$|_L_|_l$', s) and w[0] < -1e-4:
                out.append(P('error', 'manifest.side', s, f'{s} is at x {w[0]:+.4f}: the creature\'s LEFT is +X '
                                                          '(study G sec. 4.6: its left horn socket sat on the right)'))
            if re.search(r'_R$|_R_|_r$', s) and w[0] > 1e-4:
                out.append(P('error', 'manifest.side', s, f'{s} is at x {w[0]:+.4f}: the creature\'s RIGHT is -X'))
    for s in sp.get('sockets', []):
        if s not in man.get('sockets', {}):
            out.append(P('warning', 'manifest.socket_expected', s, f'the {r["base"]} preset expects {s}; the manifest '
                                                                   'lacks it'))
    # the typing (amendment 2): kinds on their base's joints, seats under their kinds, the chain records
    out += SL.check_manifest(man, r['base'])


def _check_parts(r, man, out, library):
    socks = man.get('sockets', {}) if man else None
    mats = man.get('materials', {}) if man else None
    bones = set(man.get('bones', [])) if man else None
    uvr = (man or {}).get('uv') or {}
    for s, entry in r['parts'].items():
        rows = entry['table'] if 'table' in entry else [entry]
        if 'table' in entry and rows and all(isinstance(x.get('level'), (list, tuple)) and len(x['level']) == 2
                                             for x in rows):
            if not any(x['level'][0] <= r['level'] <= x['level'][1] for x in rows):
                out.append(P('warning', 'part.no_row', f'parts.{s}', f'no row covers level {r["level"]}: the socket '
                                                                    'stays empty (study G tables covered 0-200)'))
        for k, row in enumerate(rows):
            where = f'parts.{s}' + (f'[{k}]' if 'table' in entry else '')
            if 'table' in entry:
                lv = row.get('level')
                if not (isinstance(lv, (list, tuple)) and len(lv) == 2 and lv[0] <= lv[1]):
                    out.append(P('error', 'part.level', where, f'level band {lv!r} must be [lo, hi]'))
            name = row.get('part')
            if name in CYBORG_PARTS:
                out.append(P('error', 'part.seat', where, f'{name} is a cyborg family: slot-strict, it seats by KIND '
                                                          'through recipe["cyborg"] (remix/slots.py), never on a socket '
                                                          f'named in parts ({s})'))
                continue
            part = PARTS.get(name) or (library or {}).get(name)
            if part is None:
                out.append(P('error', 'part.unknown', where, f'unknown part {name!r}'))
                continue
            if part.get('status', 'built') != 'built':
                out.append(P('missing', 'part.not_built', where, f'part {name!r} is planned, not built: '
                                                                 f'{part.get("src", "")}'))
            if part.get('seats') and s not in part['seats']:
                # slot-strict parts (CYBORG_PLAN §7.1 #5): an error; any other part only warns
                out.append(P('error' if part.get('slot_strict') else 'warning', 'part.seat', where,
                             f'{name} is made for {part["seats"]}, seated on {s}'))
            pol = row.get('element_policy', 'inherit')
            if pol not in ELEMENT_POLICIES:
                out.append(P('error', 'part.element_policy', where, f'{pol!r} not in {ELEMENT_POLICIES}'))
            if man is None:
                continue
            if s not in socks:
                out.append(P('error', 'socket.missing', where, f'part {name} seats on {s}, which the built creature '
                                                               f'lacks (have: {", ".join(sorted(socks))})'))
            rep = row.get('replaces')
            if rep and rep not in bones:
                out.append(P('error', 'bone.missing', where, f'{name} replaces bone {rep!r}, which does not exist'))
            mat = row.get('material')
            if mat is None:
                out.append(P('error', 'part.material_missing', where, f'{name}: no material slot named'))
                continue
            if mat not in mats:
                out.append(P('error', 'part.material_missing', where, f'{name} renders with material {mat!r}, which '
                                                                      f'the built creature lacks'))
                continue
            fam = mats[mat]['uv_family']
            if part['uv_family'] != fam:
                out.append(P('error', 'part.uv_family', where,
                             f'{name} is UV\'d for {part["uv_family"]!r} but material {mat!r} carries family {fam!r}: '
                             'the mis-mapped-horn defect (study G sec. 4.6)'))
            # MEASURED (the study-G method): the part's ACTUAL UV raster (its own primitive in this glb, or the
            # library's raster) against the coverage of the material slot it renders with. Precision alone is fooled
            # by a densely packed atlas (on the shipped octopus the head's UVs land 98 % inside the beak atlas), so a
            # family with one owner, whose islands a correct part fills, is gated on min(precision, recall); a shared
            # family on precision. study G: correct row 0.90 / 0.93, mis-mapped rows 0.78-0.85
            mp = ((man.get('parts') or {}).get(name) or {})
            A = uvr.get(mp.get('material')) if mp else part.get('uv_raster')
            B = uvr.get(mat)
            if A is not None and B is not None:
                prec, rec = uv_match(A, B)
                single = sum(1 for d in mats.values() if d['uv_family'] == fam) <= 1
                score = min(prec, rec) if single else prec
                msg = (f'{name} UVs on {mat}\'s coverage: precision {prec:.2f}, recall {rec:.2f} (gate on '
                       f'{"min of both: one-owner family" if single else "precision: shared family"} = {score:.2f})')
                if score < 0.85:
                    out.append(P('error', 'part.uv_measured', where, msg + '; study G mis-mapped rows measured 0.78-0.85'))
                elif score < 0.95:
                    out.append(P('warning', 'part.uv_measured', where, msg + '; its own family measures >= 0.95'))


def _seat_of(a, r):
    item = ACCESSORIES.get(a['item'], {})
    seat = a.get('socket') or (('bone:' + a['bone']) if a.get('bone') else None)
    return seat or SPECIES[r['base']].get('seats', {}).get(item.get('archetype'))


def _check_accessories(r, man, out, caps):
    users = {}
    for i, a in enumerate(r['accessories']):
        where = f'accessories[{i}].{a.get("item")}'
        item = ACCESSORIES.get(a.get('item'))
        if item is None:
            out.append(P('error', 'accessory.unknown', where, f'unknown accessory {a.get("item")!r}'))
            continue
        if item['status'] != 'built' and not caps.get('accessory_assets'):
            out.append(P('missing', 'needs.accessory_assets', where, f'{a["item"]}: ' + CAP_TEXT['accessory_assets']))
        arch = item['archetype']
        seat = _seat_of(a, r)
        if seat is None:
            out.append(P('error', 'accessory.no_seat', where, f'no seat for a {arch} on a {r["base"]}'))
            continue
        users.setdefault((seat, arch), []).append(f'[{i}] {a["item"]}')
        if man is None:
            continue
        if seat.startswith('bone:'):
            if seat[5:] not in man.get('bones', []):
                out.append(P('error', 'bone.missing', where, f'{a["item"]} seats on bone {seat[5:]!r}, which does not '
                                                             'exist'))
                continue
        elif seat not in man.get('sockets', {}):
            out.append(P('error', 'socket.missing', where, f'{a["item"]} seats on {seat}, which the built creature '
                                                           f'lacks'))
            continue
        res = resolve_accessory(a, r, man)
        # AXOLOTL AX11 (the staged patch; AXOLOTL_PLAN §10, the study-G frog lesson as data): a seat that refused this item
        # when the forge validated it (seat_<arch>.fit.refused_for_caudate: the axolotl's top hat, its brim inside the
        # gill fan's swept band) refuses it here
        seat_fit = {} if seat.startswith('bone:') else \
            ((((man.get('sockets') or {}).get(seat) or {}).get('seats') or {}).get(arch) or {}).get('fit') or {}
        if a['item'] in (seat_fit.get('refused_for_caudate') or []):
            val_ = ((seat_fit.get('validated') or {}).get(a['item']) or {}).get('gill_fan') or {}
            out.append(P('error', 'accessory.refused', where,
                         f'{a["item"]} ({arch}) on {seat}: the seat refused it when the forge validated it ('
                         f'{val_.get("points_inside", "?")} gill fan points inside it at worst, {val_.get("worst", "?")}): '
                         'a brimless item may pass'))
            continue
        if not res.get('fit'):
            why = 'a bone seat carries no fit data' if seat.startswith('bone:') else \
                (res['seat_note'] if res.get('seat_note') else f'{seat} has no {arch!r} fit')
            out.append(P('error', 'accessory.fit_missing', where,
                         f'{a["item"]} ({arch}) on {seat}: {why} and the recipe gives none (study G\'s creature-hat path '
                         'never shipped for this; ' + CAP_TEXT['socket_fits'] + ')'))
            continue
        if res['fit_source'] not in ('socket', 'seat'):
            out.append(P('warning', 'accessory.fit_override', where,
                         f'{a["item"]} fit comes from the recipe ({res["fit_source"]}), not measured socket data'))
            if res.get('seat_note'):
                out.append(P('warning', 'accessory.seat_format', where, f'the creature\'s own seat is bypassed: '
                                                                        f'{res["seat_note"]}'))
            elif not caps.get('socket_fits'):
                out.append(P('missing', 'needs.socket_fits', where, CAP_TEXT['socket_fits']))
        fit = res['fit']
        for fld in ARCHETYPES[arch]['required']:
            if fld not in fit:
                out.append(P('error', 'accessory.fit_invalid', where, f'{arch} fit lacks {fld!r}'))
        if 'rotation' in fit:
            q = np.asarray(fit['rotation'], np.float64)
            if q.shape != (4,) or abs(float(np.linalg.norm(q)) - 1.0) > 1e-3:
                out.append(P('error', 'accessory.fit_invalid', where, f'rotation {fit["rotation"]} is not a unit '
                                                                      'quaternion (x, y, z, w)'))
        if 'offset' in fit and np.asarray(fit['offset']).shape != (3,):
            out.append(P('error', 'accessory.fit_invalid', where, f'offset {fit["offset"]} is not 3 numbers'))
        key = ARCHETYPES[arch]['scale_by']
        if key in fit and not (isinstance(fit[key], (int, float)) and fit[key] > 0):
            out.append(P('error', 'accessory.fit_invalid', where, f'{key} must be > 0: {fit[key]!r}'))
        sc = res.get('scale')
        if sc is not None:
            if not 0.2 <= sc <= 5.0:
                out.append(P('error', 'accessory.scale', where, f'scale {sc:.2f} (fit {key} {fit[key]} / authored '
                                                                f'{item["authored"][key]})'))
            elif not 0.33 <= sc <= 3.0:
                out.append(P('warning', 'accessory.scale', where, f'scale {sc:.2f}: far from the authored size; the '
                                                                  'item\'s detail and texel density change with it'))
        if arch == 'glasses' and 'lens_yaw' in fit and fit['lens_yaw'] > item.get('max_lens_yaw', 8.0):
            out.append(P('error', 'accessory.lens_yaw', where,
                         f'the eyes face +-{fit["lens_yaw"]:.0f} deg off forward; {a["item"]} wraps '
                         f'{item.get("max_lens_yaw", 8.0):.0f} deg at most (a hinged bridge: wrap_goggles)'))
    for (seat, arch), who in users.items():
        if len(who) > 1:
            out.append(P('warning', 'accessory.seat_shared', f'accessories@{seat}',
                         f'{len(who)} {arch} items on {seat} ({", ".join(who)}): they seat on the same fit and '
                         'interpenetrate'))


# ENCLOSING accessories (the lead's C0b call): an item that closes over more of the head than its seat claims every
# typed socket of these kinds for cyborg.seat_shared. The space helmet's bubble closes over the whole head: the face
# (a visor's seat), any other head seat, the horns and antennae (an antenna probe's), the eyes and ears; a ball eye
# implant takes no seat and stays allowed under it. The hardhat closes over the crown only, its own seat. Kept apart
# from the ACCESSORIES catalog, on the item names it lists
ACCESSORY_ENCLOSES = dict(space_helmet=('head', 'face', 'eye', 'horn', 'antenna', 'ear'))
assert set(ACCESSORY_ENCLOSES) <= set(ACCESSORIES), 'an enclosing item is a catalog item'
assert all(k in SL.SOCKET_KINDS for ks in ACCESSORY_ENCLOSES.values() for k in ks), 'enclosed kinds are socket kinds'


def _accessory_seats(r, man=None):
    """[(socket, item, archetype, how)] for every socket an accessory holds: cyborg.seat_shared's other half (amendment
    4: a cyborg part shares its socket with NO accessory, the hat, the helmet, the glasses, the mask alike). An
    accessory seated by BONE holds the manifest's typed sockets whose kind its archetype seats under
    (slots.SEAT_KINDS) or shares a seat group with such a kind, when they ride that joint or the joint is one a
    socket of their kind may ride on this base (slots.BASES joints): a hat on bone:mantle_0 is on socket_head_top's
    seat (the C0 check: it passed beside a head module), one on bone:mantle_3 on the apex, one on bone:mantle_1 or
    bone:mantle_2 on the dome between them (no socket rides those) and one on bone:head on the head seat (the C0b
    check), the octopus's head too (the lead's C0b call), while the octopus's bow tie on bone:head holds no cyborg
    seat (a tie seats under chest kinds only). An ENCLOSING item (ACCESSORY_ENCLOSES) also holds every typed socket
    of the kinds it encloses: the space helmet on socket_head_top holds socket_eyes (C0b)"""
    out = []
    typed = {s: d for s, d in ((man or {}).get('sockets') or {}).items() if isinstance(d.get('slot'), dict)}
    for a in r.get('accessories') or []:
        item = ACCESSORIES.get(a.get('item')) if isinstance(a, dict) else None
        if item is None:
            continue
        seat = _seat_of(a, r)
        if not seat:
            continue
        arch = item['archetype']
        held = []
        if not seat.startswith('bone:'):
            held.append((seat, ''))
        else:
            kinds = SL.group_kinds(SL.SEAT_KINDS.get(arch, ()), r['base'])
            # the joints a socket of those kinds may hang on, per base (slots.BASES joints): an accessory seated by a
            # bone there stands on that seat whether or not a socket rides the bone itself (the C0b check: a hat by
            # bone:mantle_1 or bone:mantle_2, on the octopus's dome, or by bone:head, passed beside a head module)
            jt = (SL.BASES.get(r['base']) or {}).get('joints') or {}
            stands = {k for k in kinds if isinstance(jt.get(k), str) and re.fullmatch(jt[k], seat[5:])}
            held += [(s, f'seated by {seat}') for s, d in sorted(typed.items()) if d['slot'].get('kind') in kinds and
                     (d.get('bone') == seat[5:] or d['slot'].get('kind') in stands)]
        enc = ACCESSORY_ENCLOSES.get(a['item'], ())
        held += [(s, f'it encloses {s}') for s, d in sorted(typed.items()) if d['slot'].get('kind') in enc and
                 s not in {h for h, _ in held}]
        out += [(s, a['item'], arch, how) for s, how in held]
    return out


# COVERING LAYERS (cyborg.covered: CYBORG_PLAN A.6; the lead's A.9 decision 4, an error): what a recipe stands on the
# flesh beyond the base's own skin. A sculpt layer the recipe ADDS or SWAPS IN covers when it carries its own material
# id or its own mesh (a growth or a vein in any mode, plates, pustules, coat cards: SCULPT_KINDS' material_ids need or
# mesh mode, or a material that is not skin); so do the element's growth at a tier that grows it, every cyborg surface
# row (plates), the organic parts and the accessories, on the sockets and joints they hold. The base species' OWN layers
# (the same id and kind as its plan's: the octopus's suckers, papillae, warts, eye papillae, lip folds and carves, the
# wolf's coat, the beetle's chitin plates) are its skin and go with the flesh by construction: the cut drops the skin
# beyond its ring with its texels and its geometric suckers (C5), and the coat parts over the flange (C11). SITE_REACH:
# where each sites name stands on a base, as layer masks name it (regions None: everywhere; s: a share range along the
# chains it reaches; sockets: what it seats on)
SITE_REACH = dict(
    octopus={'scatter': dict(regions=None), 'patch:body': dict(regions=None),
             'patch:head': dict(regions={'body', 'crown_top', 'crown_oral'}), 'patch:arm': dict(regions={'arm'}),
             'anatomy:arm_oral_rows': dict(regions={'arm'}), 'anatomy:arm_tips': dict(regions={'arm'}, s=(0.9, 1.0)),
             'anatomy:eyes': dict(regions={'body'}), 'anatomy:mouth': dict(regions=set(), sockets={'socket_mouth'}),
             'anatomy:funnel': dict(regions=set(), sockets={'socket_funnel'}),
             'anatomy:mantle_apex': dict(regions=set(), sockets={'socket_mantle_apex'})},
    wolf={'scatter': dict(regions=None), 'patch:body': dict(regions=None), 'anatomy:eyes': dict(regions={'head'}),
          'anatomy:jaw': dict(regions={'head'}), 'anatomy:ears': dict(regions={'head'}),
          'anatomy:paws': dict(regions={'limb'}, s=(0.85, 1.0))},
    beetle={'scatter': dict(regions=None), 'patch:body': dict(regions=None), 'anatomy:eyes': dict(regions={'head'}),
            'anatomy:mandibles': dict(regions={'head'}), 'anatomy:antennae': dict(regions={'antenna'})})


def _share_range(v):
    return (float(v[0]), float(v[1])) if (isinstance(v, (list, tuple)) and len(v) == 2 and all(_num(x) for x in v)
                                          and v[0] <= v[1]) else None


def _layer_reach(r, sites, mask, growth):
    """a sculpt layer's reach (slots.check_covered): its sites' (SITE_REACH, 'socket:<name>' on that socket; an unknown
    name everywhere), narrowed by its mask's regions; its share range from its mask's s (one that is no range: the whole
    chain), else, for a growth, the forge's own growth footprint along each chain (slots.BASES growth_s)"""
    if isinstance(sites, str) and sites.startswith('socket:'):
        rc = dict(regions=set(), sockets={sites[7:]})
    else:
        rc = SITE_REACH.get(r['base'], {}).get(sites if isinstance(sites, str) else 'scatter', dict(regions=None))
    regs = None if rc.get('regions') is None else set(rc['regions'])
    mreg = mask.get('regions') if isinstance(mask, dict) else None
    if isinstance(mreg, list) and mreg:
        regs = {g for g in mreg if isinstance(g, str)} if regs is None else regs & set(mreg)
    s = rc.get('s')
    if isinstance(mask, dict) and mask.get('s') is not None:
        # a mask s that is no share range (reversed, not two numbers) is judged over the whole chain, never replaced by
        # the forge's default footprint (the C0b check: s [0.97, 0.0] beside cut 14 passed as the footprint's s < 0.75)
        s = _share_range(mask['s']) or (0.0, 1.0)
    return dict(regions=regs, s=s, growth=bool(growth) and s is None, sockets=set(rc.get('sockets') or ()),
                bones=set())


def _covering_layers(r):
    """[(where, what, reach)]: every covering layer of the recipe, for slots.check_covered"""
    out = []
    own = {(L.get('id'), L.get('kind')) for L in SPECIES.get(r.get('base'), {}).get('layers') or []}
    for i, L in enumerate(r.get('sculpt') or []):
        if not isinstance(L, dict) or (L.get('id'), L.get('kind')) in own:
            continue
        kind = SCULPT_KINDS.get(L.get('kind')) or {}
        mat = L.get('material', 'skin')
        if not (kind.get('mode') == 'mesh' or 'material_ids' in kind.get('needs', []) or mat != 'skin'):
            continue
        what = f'sculpt layer {L.get("id", i)} ({L.get("kind")}' + (f', {mat}' if mat != 'skin' else '') + ')'
        ms = L['mask'].get('s') if isinstance(L.get('mask'), dict) else None
        if ms is not None and _share_range(ms) is None:
            what += f' (its mask s {ms!r} is no share range: judged over the whole chain)'
        out.append((f'sculpt.{L.get("id", i)}', what, _layer_reach(r, L.get('sites', 'scatter'), L.get('mask'),
                                                                   L.get('kind') == 'growth')))
    el = r.get('element')
    if el in EL.ELEMENTS and 'growth' in EL.layers_for(el, el_tier(r['tier'])):
        fam = (EL.ELEMENTS[el].get('growth') or {}).get('family')
        out.append(('element', f'the {el} element\'s growth ({fam}) at tier {r["tier"]}',
                    dict(regions=None, s=None, growth=True, sockets=set(), bones=set())))
    cyb = r.get('cyborg') if isinstance(r.get('cyborg'), dict) else {}
    for i, row in enumerate(cyb.get('surface') if isinstance(cyb.get('surface'), list) else []):
        if not isinstance(row, dict):
            continue
        reg = row.get('region')
        out.append((f'cyborg.surface[{i}]', f'cyborg surface row {i} (plates on {reg or "every region"})',
                    dict(regions={reg} if isinstance(reg, str) else None, s=_share_range(row.get('s')), growth=False,
                         sockets=set(), bones=set())))
    for sock, entry in sorted((r.get('parts') or {}).items()):
        name = entry.get('part') if isinstance(entry, dict) else None
        out.append((f'parts.{sock}', f'the part {name or "table"} on {sock}',
                    dict(regions=set(), s=None, growth=False, sockets={sock}, bones=set())))
    for i, a in enumerate(r.get('accessories') or []):
        if not isinstance(a, dict) or a.get('item') not in ACCESSORIES:
            continue
        seat = _seat_of(a, r)
        if not seat:
            continue
        on_bone = seat.startswith('bone:')
        out.append((f'accessories[{i}].{a["item"]}', f'the accessory {a["item"]} on {seat}',
                    dict(regions=set(), s=None, growth=False, sockets=set() if on_bone else {seat},
                         bones={seat[5:]} if on_bone else set(), mounts=False)))
    return out


def _cyborg_plan(r, man, check_man):
    """slots.plan() on the recipe: the section's own level and seed (else the recipe's; a malformed one is reported by
    slots.check_recipe and the recipe's is used for the rest), the recipe's seeded pick, its accessories' seats; then
    cyborg.covered over the placements (slots.check_covered on the recipe's covering layers: C0b)"""
    cyb = r['cyborg']
    ok = lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0
    level = cyb.get('level') if isinstance(cyb, dict) and ok(cyb.get('level')) else r['level']
    seed = cyb.get('seed') if isinstance(cyb, dict) and ok(cyb.get('seed')) else r['seed']
    placements, probs = SL.plan(cyb, man, r['base'], level=level, seed=seed, pick=pick_weighted,
                                accessories=_accessory_seats(r, man), check_man=check_man)
    if man is not None and placements:
        probs = probs + SL.check_covered(placements, man, r['base'], _covering_layers(r))
    return placements, probs


def _check_cyborg(r, man, out, caps):
    """the cyborg section (CYBORG_PLAN §7.3): every kind-keyed row against the closed table at validate time (amendment
    1), and on a manifest the whole resolution on its typed sockets and chains, each placement checked (remix/slots.py
    plan()); then what the forge still lacks (needs.*). Returns the placements (the budget counts them)"""
    cyb = r.get('cyborg')
    if not cyb:
        return []
    if isinstance(cyb, dict) and cyb.get('size') is not None and cyb['size'] not in TIERS:
        out.append(P('error', 'cyborg.unknown', 'cyborg.size', f'unknown size class {cyb["size"]!r} (have {TIERS})'))
    placements = []
    if man is None:
        out += SL.check_recipe(cyb, base=r.get('base'))       # (the surface rows by the base's plate regions: C1)
    else:
        placements, probs = _cyborg_plan(r, man, check_man=False)       # _check_manifest checks the typing
        out += probs
    used = set()
    if isinstance(cyb, dict):
        for rows in (cyb.get('parts') or {}).values() if isinstance(cyb.get('parts'), dict) else []:
            used |= {x['part'] for x in (rows if isinstance(rows, list) else []) if isinstance(x, dict) and
                     isinstance(x.get('part'), str) and x['part'] in CYBORG_PARTS}
        used |= {x['part'] for x in (cyb.get('limbs') if isinstance(cyb.get('limbs'), list) else [])
                 if isinstance(x, dict) and isinstance(x.get('part'), str) and x['part'] in CYBORG_PARTS}
        if cyb.get('surface'):
            for need in ('cyborg_ids', 'plate_op'):
                if not caps.get(need):
                    out.append(P('missing', f'needs.{need}', 'cyborg.surface', 'cyborg plates: ' + CAP_TEXT[need]))
    for F in sorted(used):
        for need in CYBORG_PARTS[F]['needs']:
            if not caps.get(need):
                out.append(P('missing', f'needs.{need}', f'cyborg.{F}', f'{F}: ' + CAP_TEXT[need]))
    return placements


def resolve_cyborg(r, manifest):
    """the cyborg section's PLACEMENTS on a built creature (CYBORG_PLAN §7.1 #4): each built only from (kind, site,
    row) by remix/slots.py plan() on the manifest's typed sockets and chains, the manifest's typing checked too. Raises
    slots.SlotError naming every refused slot and part on any error: a row whose part does not fit its kind is never
    placed. [] for a recipe without a cyborg section"""
    r = normalise(r)
    if not r.get('cyborg'):
        return []
    placements, probs = _cyborg_plan(r, manifest, check_man=True)
    errs = [p for p in probs if p['severity'] == 'error']
    if errs:
        raise SL.SlotError(errs)
    return placements


def resolve_cyborg_runtime(r, manifest):
    """the cyborg section's RUNTIME block (runtime/bestiary.js create({ cyborg }), patches/cyborg_c5b_bestiary.md):
    every placement resolve_cyborg makes on the built creature as bestiary.js mounts it (an eye implant on its socket,
    a chain part on its chain from its cut) and, after a limb whose row says hose='plates', its hose; each with the
    asset name its glb ships under (the forge's outputs: cyborg_eye_implant_<variant>, cyborg_mech_tentacle,
    cyborg_hose_<chain>_s<seed>: C5c, the hose drawn for the recipe seed's own rest pose, built and cached by seed at
    assembly by forge/cyborg_hose.py hose_for_seed); after them a FEED row's lines and their hardware (C3e: one
    'feed' part per line and one for the collars and clamps, each carrying the look it serves: feed_parts); the
    section's glow and affixes as it gives them. Raises slots.SlotError as resolve_cyborg"""
    r = normalise(r)
    cyb = r.get('cyborg') or {}
    parts = []
    for pl in resolve_cyborg(r, manifest):
        F, v = pl['part'], pl['variant']
        if pl['interface'] == 'chain':
            parts.append(dict(kind=F, variant=v, chain=pl['chain'], cut=pl['cut'], asset=f'cyborg_{F}'))
            if (pl.get('row') or {}).get('hose') == 'plates':
                parts.append(dict(kind='hose', chain=pl['chain'], source='plates', seed=int(r['seed']),
                                  asset=f'cyborg_hose_{pl["chain"]}_s{int(r["seed"])}'))
        elif pl['interface'] in ('ball', 'dome'):
            parts.append(dict(kind=F, variant=v, socket=pl['site'], asset=f'cyborg_{F}_{v}'))
        else:
            parts.append(dict(kind=F, variant=v, site=pl['site'], seat=pl.get('seat'), asset=f'cyborg_{F}_{v}'))
    parts += feed_parts(cyb, r['base'], int(r['seed']))
    return dict(parts=parts, glow=copy.deepcopy(cyb.get('glow')), affixes=list(cyb.get('affixes') or []))


def feed_parts(cyb, base, seed):
    """THE FEED'S PARTS (C3e; the C3d check: "a look with a feed row must mount its feed parts";
    patches/cyborg_c3e_recipe.md): a feed row lays its lines as GEOMETRY over its region's plates (forge/cyborg_feed.py:
    the cables on the hose's runtime path, bestiary.js kind 'feed'), and the head set of such a look is baked with those
    cables as AO occluders: without them the skin shows dark lines under cables that are not there and the plates grey
    stripes. Per feed row: one part per line (links + dives, the row's or slots.FEED_DEFAULTS'; cyborg_feed_<line>)
    and one for the look's collars and clamps (cyborg_feed_hardware), each carrying the LOOK it serves: the plates row
    of its region without kind and note (its seed the section's when the row gives none), and the feed row as
    forge/cyborg.py feed_layout resolves it (its region, else the base's feed region; links, dives, sleeve; its seed,
    else the plates'). The assembly checks that look against the built one (runtime_assets -> forge/cyborg_feed.py
    feed_assets). [] without a feed row"""
    surf = cyb.get('surface') if isinstance(cyb.get('surface'), list) else []
    out = []
    for fr in surf:
        if not (isinstance(fr, dict) and fr.get('kind') == 'feed'):
            continue
        region = fr.get('region') or SL.FEED_REGIONS[base][0]
        pr = next((s for s in surf if isinstance(s, dict) and s.get('kind', 'plates') == 'plates'
                   and s.get('region') == region), {})
        plates = {k: v for k, v in pr.items() if k not in ('kind', 'note')}
        plates.setdefault('seed', int(cyb.get('seed', seed)))
        D = SL.FEED_DEFAULTS
        feed = dict(region=region, links=int(fr.get('links', D['links'])), dives=int(fr.get('dives', D['dives'])),
                    sleeve=fr.get('sleeve') or D['sleeve'],
                    seed=int(fr['seed'] if fr.get('seed') is not None else plates['seed']))
        look = dict(plates=plates, feed=feed)
        out += [dict(kind='feed', line=li, asset=f'cyborg_feed_{li}', look=copy.deepcopy(look))
                for li in range(feed['links'] + feed['dives'])]
        out.append(dict(kind='feed', asset='cyborg_feed_hardware', look=copy.deepcopy(look)))
    return out


# THE FIRST FULL CYBORG OCTOPUS (C5b, the lead's decision 5): the C3 default plates on the mantle with the C3b feed
# lines, the C4 eye implant ('lens') on the left eye, the C5a mech tentacle on L1 (the left front arm) from cut 8
# with its hose from the plates; the glow the C4 implant's (its cyb_glow row) as bestiary.js's create() takes it
CYBORG_OCTOPUS = dict(
    level=0, seed=5,
    surface=[dict(kind='plates', region='body', seed=5), dict(kind='feed', region='body')],
    parts=dict(eye=[dict(part='eye_implant', variant='lens', side='L')]),
    limbs=[dict(kind='tentacle', chain='L1', cut_joint=8, part='mech_tentacle', variant='knuckled', hose='plates')],
    glow=dict(glow=[0.0, 0.5, 1.0], intensity=2.0, rate=1.0, pulse=0.25), affixes=[])


def _check_bones(r, man, out):
    names = man.get('bones', [])
    parents = man.get('bone_parent', {})
    for i, op in enumerate(r['bones']):
        where = f'bones[{i}]'
        pat = op.get('match') or op.get('bone')
        if not pat:
            out.append(P('error', 'bone.op', where, 'a bone op needs match (regex) or bone (name)'))
            continue
        try:
            rx = re.compile(pat if op.get('match') else '^' + re.escape(pat) + '$')
        except re.error as e:
            out.append(P('error', 'bone.op', where, f'bad regex {pat!r}: {e}'))
            continue
        hit = [b for b in names if rx.search(b)]
        if not hit:
            out.append(P('error', 'bone.missing', where, f'{pat!r} matches no bone of the built creature'))
            continue
        hs = set(hit)
        chained = [b for b in hit if parents.get(b) in hs]
        if chained:
            out.append(P('warning', 'bone.compound', where, f'{pat!r} matches {len(chained)} joints whose parents it '
                                                            f'also matches: their scales compound down the chain '
                                                            f'(scale the chain roots only)'))
        s = op.get('scale', [1, 1, 1])
        s = [s] * 3 if _num(s) else s
        if not (isinstance(s, (list, tuple)) and len(s) == 3 and all(_num(x) for x in s)):
            out.append(P('error', 'bone.op', where, f'scale {op.get("scale")!r} must be a number or [x, y, z]'))
            continue
        if any(not (0.0 <= x <= 4.0) for x in s):
            out.append(P('warning', 'bone.scale', where, f'scale {s} outside 0-4'))
        if any(b.startswith('eye_') for b in hit) and max(s) > 1.1:
            out.append(P('warning', 'bone.eye_scale', where, 'eyeballs scaled > 1.1 poke through the lids (the lid '
                                                             'skin is weighted to head, not to the eye joints)'))
        kids = {p for p in parents.values() if p}
        if min(s) > 0 and max(s) / min(s) > 1.02 and any(b in kids for b in hit):
            out.append(P('warning', 'bone.nonuniform', where,
                         f'{pat!r}: the non-uniform scale {list(s)} on joints with children scales their whole '
                         'sub-chain\'s POSED shape in those axes (a curl\'s lift and sweep grow by the same factors) and '
                         'shears the children as they rotate (three.js composes scale without compensation)'))


def _check_packs(r, man, out):
    needs_packs = bool(r['palette']) or (r['element'] not in ('normal',) and r['element'] in EL.ELEMENTS) or \
        any(v for v in (r['display'].get('weights') or {}).values()) or r['display'].get('mood', 'rest') != 'rest'
    if not needs_packs:
        return
    zones = SPECIES[r['base']]['zones']
    chans = set()
    for z in zones.values():
        if isinstance(z, dict):
            for term in z.get('max', []):
                chans.add(term[0].split('.')[0])
    for name, m in man.get('materials', {}).items():
        if m['kind'] != 'skin':
            continue
        for pack in sorted(chans):
            if pack not in m['packs']:
                out.append(P('error', 'packs.missing', f'materials.{name}',
                             f'skin material {name} lacks the {pack!r} pack the runtime zones read'))


def _check_fx(r, man, out):
    affs = r['affixes'] if isinstance(r['affixes'], list) else []
    fx = [s for s in man.get('sockets', {}) if re.match(r'^socket_(fx_)?affix_\d+$', s)]
    for a in affs:
        if EL.AFFIXES.get(a, {}).get('needs_fx') and not fx:
            out.append(P('missing', 'fx.contract', f'affixes.{a}',
                         f'{a} ({EL.AFFIXES[a]["fx"]}) needs FX sockets: ' + CAP_TEXT['fx_sockets']))


def _refused(r, pl, bad):
    """(stage 4) is this cyborg placement's ROW, or its site, named by an error (bad: the error problems' wheres)? Such a
    row is refused: resolve_cyborg raises on it, the runtime never places it. A limb row is cyborg.limbs[i], a kind
    table's row cyborg.parts.<K>[i] (check_recipe's and plan()'s wheres), a placed site cyborg.parts.<K>@<site>"""
    cyb = r.get('cyborg') if isinstance(r.get('cyborg'), dict) else {}
    K = pl.get('kind')
    if str(pl.get('key', '')).startswith('cyborg.limbs.'):
        rows, at = cyb.get('limbs'), 'cyborg.limbs'
    else:
        parts = cyb.get('parts') if isinstance(cyb.get('parts'), dict) else {}
        rows, at = parts.get(K), f'cyborg.parts.{K}'
    wh = {f'cyborg.parts.{K}@{pl.get("site")}'}
    if isinstance(rows, list):
        wh |= {f'{at}[{i}]' for i, row in enumerate(rows) if row == pl.get('row')}
    return bool(wh & bad)


def _check_budget(r, man, out, cyborg=()):
    tris = man.get('budget', {}).get('tris', 0)
    extra = sum(ACCESSORIES.get(a.get('item'), {}).get('tris', 0) for a in r['accessories'])
    for L in r['sculpt']:
        if L.get('kind') == 'growth' and L.get('mode') == 'mesh':
            extra += GROWTH_MESH_TRIS
    el = r['element'] if r['element'] in EL.ELEMENTS else 'normal'
    if 'growth' in EL.layers_for(el, el_tier(r['tier'])):
        extra += GROWTH_MESH_TRIS
    # (stage 4, the lead's call after the stage-3 check's probe4) a placement whose row drew an error is REFUSED, never
    # placed, so it costs nothing: the sum leaves it out. plan() still lists such a placement: an organ family written as
    # a cyborg limb row (cyborg.organ) reached CYBORG_PARTS below and raised KeyError 'leg_graft' (GRAFT_PARTS holds it)
    bad = {p['where'] for p in out if p['severity'] == 'error'}
    cyborg = [pl for pl in cyborg if not _refused(r, pl, bad)]
    # the cyborg placements' NET triangles at their high estimate (CYBORG_PARTS)
    unknown = sorted({pl['part'] for pl in cyborg if CYBORG_PARTS[pl['part']]['tris'] is None})
    extra += sum(CYBORG_PARTS[pl['part']]['tris'][1] for pl in cyborg if CYBORG_PARTS[pl['part']]['tris'] is not None)
    if unknown:
        out.append(P('warning', 'budget.cyborg_unknown', 'budget', f'the triangle budget leaves out {unknown}: no '
                                                                   'estimate yet (CYBORG_PARTS)'))
    # the cap: the recipe's tier, or the base species' own BUDGET tier where it is higher (the lead's C0b call: the
    # octopus is hero-class, 150,000, at any recipe tier; the recipe's tier keeps choosing its element stack and affixes)
    # a species' own budget record (budget_kinds, the lead's L1 call: the octopus's suckers at t26's 192,000): a material
    # of a listed kind is held to its own accepted budget and leaves the tier's sum; every drawn triangle is counted once
    held = []
    for kind_, cap_k in (SPECIES[r['base']].get('budget_kinds') or {}).items():
        t_k = sum(int(m.get('tris') or 0) for m in (man.get('materials') or {}).values() if m.get('kind') == kind_)
        if t_k > cap_k:
            out.append(P('warning', 'budget.kind', 'budget', f'{t_k} {kind_} triangles > {cap_k} (the '
                                                             f'{r["base"]}\'s own budget record for {kind_})'))
        tris -= t_k
        held.append(f'{t_k} {kind_} held to their own {cap_k}')
    cap = BUDGET_TRIS[r['tier']] if r['tier'] in BUDGET_TRIS else 50000
    bt = SPECIES[r['base']].get('budget_tier')
    by = f'{r["tier"]} tier'
    if bt in BUDGET_TRIS and BUDGET_TRIS[bt] > cap:
        cap, by = BUDGET_TRIS[bt], f'the {r["base"]}\'s budget tier {bt}; the recipe\'s tier is {r["tier"]}'
    if tris + extra > cap:
        out.append(P('warning', 'budget.tris', 'budget', f'{tris} body + {extra} attachments / growths = '
                                                         f'{tris + extra} triangles > {cap} ({by}, DESIGN.md budgets'
                                                         + ''.join(f'; {h}' for h in held) + ')'))


def validate(recipe, manifest=None, library=None, caps=None):
    """every problem the recipe has, alone and against a built creature's manifest. Returns a list of
    dict(severity, code, where, message), errors first"""
    caps = dict(FORGE_CAPS, **(caps or {}))
    out = []
    try:
        r = normalise(recipe)
    except KeyError as e:
        return [P('error', 'recipe.base', 'base', str(e))]
    if _check_schema(r, out):
        _check_spec(r, out, caps)
        _check_layers(r, out, caps)
        _check_skin(r, out, caps)
        _check_element(r, out, caps)
        _check_display(r, out, caps)
        _check_palette(r, out)
        _check_parts(r, manifest, out, library)
        _check_accessories(r, manifest, out, caps)
        placed = _check_cyborg(r, manifest, out, caps)
        if manifest is not None:
            _check_manifest(r, manifest, out)
            _check_bones(r, manifest, out)
            _check_packs(r, manifest, out)
            _check_fx(r, manifest, out)
            _check_budget(r, manifest, out, placed)
    # one line per distinct problem
    seen, uniq = set(), []
    for p in out:
        k = (p['severity'], p['code'], p['where'], p['message'])
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    order = {s: i for i, s in enumerate(SEVERITIES)}
    return sorted(uniq, key=lambda p: (order[p['severity']], p['code'], p['where']))


def report(problems, title=''):
    if not problems:
        return f'[validate] {title} clean'.strip()
    n = {s: sum(p['severity'] == s for p in problems) for s in SEVERITIES}
    lines = [f'[validate] {title} {n["error"]} error(s), {n["missing"]} missing, {n["warning"]} warning(s)'.strip()]
    for p in problems:
        lines.append(f'  {p["severity"]:7s} {p["code"]:26s} {p["where"]}: {p["message"]}')
    return '\n'.join(lines)


def buildable(problems):
    return not any(p['severity'] in ('error', 'missing') for p in problems)


def check_species_sync(imported=False):
    """the fallback copies of the octopus's SPEC / PATCH / SKIN_RECIPE against the forge. Default: the sources read by
    ast (no import, no warp). imported=True compares against the imported modules instead (imports warp through
    sdf.py: run with CUDA_VISIBLE_DEVICES=-1 to keep a GPU untouched; no kernel launches here)"""
    if imported:
        from eidoverse.bestiary.forge.species import octopus, octopus_skin, octopus_sculpt
        live = dict(SPEC=dict(octopus.SPEC), PATCH=dict(octopus_sculpt.PATCH), SKIN_RECIPE=dict(octopus_skin.SKIN_RECIPE))
    else:
        live = dict(SPEC=dict_from_source(os.path.join(FORGE_SPECIES, 'octopus.py'), 'SPEC'),
                    PATCH=dict_from_source(os.path.join(FORGE_SPECIES, 'octopus_sculpt.py'), 'PATCH'),
                    SKIN_RECIPE=dict_from_source(os.path.join(FORGE_SPECIES, 'octopus_skin.py'), 'SKIN_RECIPE'))
    mirror = dict(SPEC=OCTOPUS_SPEC_MIRROR, PATCH=OCTOPUS_PATCH_MIRROR, SKIN_RECIPE=OCTOPUS_PAINT_MIRROR)
    norm = lambda v: tuple(v) if isinstance(v, (list, tuple)) else v
    bad = []
    for name, L in live.items():
        if L is None:
            bad.append(f'{name}: could not be read from the forge')
            continue
        M = mirror[name]
        for k in sorted(set(L) | set(M)):
            if norm(L.get(k)) != norm(M.get(k)):
                bad.append(f'{name}.{k}: forge {L.get(k)} vs fallback copy {M.get(k)}')
    return bad


# ============================================================================================ self-test (CPU)
def fake_manifest(**over):
    """an octopus-like manifest built in code (the unit tests' fixture). It mirrors the 05:58 export, block-out v4
    (recipe.py --glb prints fixture_drift() against the shipped glb): the 203 joint names and parents of octopus_rig,
    the 16 sockets t13 writes on their joints at their world positions (the arm tips in the cage's column order;
    socket_eyes on the head joint, socket_head_top on the collar joint mantle_0), the four materials with their packs
    and triangle counts (the eye's masks pack), the budget. Synthetic: the UV rasters (head: the left half, arms: the
    right half's top, eye: a corner block, beak: a small block); no fits, no seat nodes (the tests seat their own), no
    FX sockets"""
    res = 64
    bones = ['root', 'body', 'head', 'mantle_0', 'mantle_1', 'mantle_2', 'mantle_3', 'eye_L', 'eye_R', 'funnel_0',
             'funnel_1'] + [f'arm{j}_{k:02d}' for j in range(8) for k in range(24)]
    bp = dict(root=None, body='root', head='body', mantle_0='head', mantle_1='mantle_0', mantle_2='mantle_1',
              mantle_3='mantle_2', eye_L='head', eye_R='head', funnel_0='head', funnel_1='funnel_0')
    for j in range(8):
        for k in range(24):
            bp[f'arm{j}_{k:02d}'] = 'body' if k == 0 else f'arm{j}_{k - 1:02d}'
    sockets = {
        'socket_eye_L': dict(bone='eye_L', world=[0.025546, 0.181658, -0.034716], fit={}),
        'socket_eye_R': dict(bone='eye_R', world=[-0.025546, 0.181658, -0.034716], fit={}),
        'socket_eyes': dict(bone='head', world=[0.0, 0.193236, -0.026216], fit={}),
        'socket_crown': dict(bone='body', world=[0.0, 0.088, 0.0], fit={}),
        'socket_funnel': dict(bone='funnel_1', world=[0.060372, 0.140526, -0.053932], fit={}),
        'socket_mantle_apex': dict(bone='mantle_3', world=[0.0, 0.128236, -0.233185], fit={}),
        'socket_head_top': dict(bone='mantle_0', world=[-3.9e-05, 0.202071, -0.140494], fit={}),
        'socket_mouth': dict(bone='body', world=[0.0, 0.047159, 0.0], fit={}),
    }
    # the arm tips as the 05:58 export has them: 0.844301 m out at y 0.0191, in the cage's column order (R1-R4, L4-L1)
    for j, az in enumerate((-22.5, -67.5, -112.5, -157.5, 157.5, 112.5, 67.5, 22.5)):
        a_ = math.radians(az)
        sockets[f'socket_arm{j}_tip'] = dict(bone=f'arm{j}_23', world=[round(0.844301 * math.sin(a_), 6), 0.0191,
                                                                       round(0.844301 * math.cos(a_), 6)], fit={})
    blk = lambda y0, y1, x0, x1: np.pad(np.ones((y1 - y0, x1 - x0), bool), ((y0, res - y1), (x0, res - x1)))
    uv = dict(octopus_head=blk(0, 64, 0, 32), octopus_arms=blk(0, 32, 32, 64), octopus_eye=blk(40, 52, 40, 52),
              octopus_beak=blk(56, 62, 56, 62))
    mats = dict(
        octopus_head=dict(kind='skin', uv_family='octopus_head', packs=['masks', 'display'], tris=22040),
        octopus_arms=dict(kind='skin', uv_family='octopus_arms', packs=['masks', 'display'], tris=16640),
        octopus_eye=dict(kind='eye', uv_family='octopus_eye', packs=['masks'], tris=2400),
        octopus_beak=dict(kind='beak', uv_family='octopus_beak', packs=[], tris=1920))
    man = dict(manifest=1, source='fake', species='octopus', family='radial', bones=bones, bone_parent=bp,
               sockets=sockets, materials=mats,
               parts=dict(octopus_eye=dict(kind='eye', material='octopus_eye', uv_family='octopus_eye',
                                           seats=['socket_eye_L', 'socket_eye_R'], tris=2400),
                          octopus_beak=dict(kind='beak', material='octopus_beak', uv_family='octopus_beak',
                                            seats=['socket_mouth'], tris=1920)),
               uv=uv, uv_res=res, budget=dict(tris=43000, joints=len(bones)), inferred=[])
    return merge(man, over) if over else man


def fixture_drift(real, fixture=None, tol=1e-3):
    """how far the unit tests' fixture (fake_manifest) has drifted from a REAL manifest (manifest_from_glb): the joint
    names and parents, the sockets' joints and world positions (tol, metres), the materials' kind, UV family, packs and
    triangles, the parts' seats and triangles, the budget. [] = the fixture still mirrors the build"""
    fx = fixture if fixture is not None else fake_manifest()
    bad = []
    rb, fb = list(real.get('bones', [])), list(fx.get('bones', []))
    if rb != fb:
        bad.append(f'joints: {len(rb)} built vs {len(fb)} in the fixture; only built {[b for b in rb if b not in fb][:6]}, '
                   f'only in the fixture {[b for b in fb if b not in rb][:6]}'
                   + (' (the same names in another order)' if set(rb) == set(fb) else ''))
    else:
        rp_, fp_ = real.get('bone_parent', {}), fx.get('bone_parent', {})
        moved = [b for b in rb if rp_.get(b) != fp_.get(b)]
        if moved:
            bad.append('joint parents differ: ' + ', '.join(f'{b} ({rp_.get(b)} built vs {fp_.get(b)})'
                                                           for b in moved[:6]))
    rs, fs = real.get('sockets', {}), fx.get('sockets', {})
    for s in sorted(set(rs) | set(fs)):
        if s not in fs or s not in rs:
            bad.append(f'socket {s}: {"built, not in the fixture" if s in rs else "in the fixture, not built"}')
            continue
        if rs[s].get('bone') != fs[s].get('bone'):
            bad.append(f'socket {s}: on {rs[s].get("bone")} built vs {fs[s].get("bone")} in the fixture')
        if rs[s].get('slot') != fs[s].get('slot'):
            bad.append(f'socket {s}: slot {rs[s].get("slot")} built vs {fs[s].get("slot")} in the fixture')
        w1, w2 = rs[s].get('world'), fs[s].get('world')
        if w1 is not None and w2 is not None:
            d = max(abs(a - b) for a, b in zip(w1, w2))
            if d > tol:
                bad.append(f'socket {s}: world {w1} built vs {w2} in the fixture ({d * 1000:.1f} mm)')
    for what, rd, fd, keys in (('material', real.get('materials', {}), fx.get('materials', {}),
                                ('kind', 'uv_family', 'packs', 'tris')),
                               ('part', real.get('parts', {}), fx.get('parts', {}), ('seats', 'tris', 'uv_family'))):
        for m in sorted(set(rd) | set(fd)):
            if m not in fd or m not in rd:
                bad.append(f'{what} {m}: {"built, not in the fixture" if m in rd else "in the fixture, not built"}')
                continue
            for k in keys:
                if rd[m].get(k) != fd[m].get(k):
                    bad.append(f'{what} {m}.{k}: {rd[m].get(k)!r} built vs {fd[m].get(k)!r} in the fixture')
    if real.get('budget') != fx.get('budget'):
        bad.append(f'budget {real.get("budget")} built vs {fx.get("budget")} in the fixture')
    return bad


def arm_labels_from(man):
    """each arm chain's anatomical label from its tip socket's world position: L on +X (the creature's left), numbered
    1-4 from the front (+Z) by |azimuth|; [] if the manifest has no arm tips"""
    tips = {}
    for s, d in (man.get('sockets') or {}).items():
        m = re.match(r'^socket_arm(\d+)_tip$', s)
        if m and d.get('world') is not None:
            x, _, z = d['world']
            tips[int(m.group(1))] = (abs(math.degrees(math.atan2(x, z))), 'L' if x > 0 else 'R')
    lab = {}
    for side in 'LR':
        for n, j in enumerate(sorted((j for j in tips if tips[j][1] == side), key=lambda j: tips[j][0])):
            lab[j] = f'{side}{n + 1}'
    return [lab[j] for j in sorted(lab)]


# what t13 writes on the octopus's sockets once work/bestiary/patches/cyborg_c0_t13.md lands: {socket: (kind,
# interface, paired)}. The FIXTURE's typing only: the validator takes kinds from the glb, never from this table
T13_SLOTS = dict(socket_eye_L=('eye', 'ball', True), socket_eye_R=('eye', 'ball', True),
                 socket_eyes=('face', 'mount', False), socket_crown=('crown_centre', 'none', False),
                 socket_funnel=('siphon', 'mount', False), socket_mantle_apex=('mantle', 'mount', False),
                 socket_head_top=('head', 'mount', False), socket_mouth=('mouth', 'mount', False),
                 **{f'socket_arm{j}_tip': ('limb_tip', 'mount', True) for j in range(8)})
T13_CUTS = (6, 8, 10, 12, 14)        # CYBORG_PLAN §4.4.1's listed cuts
# the PORTS the re-staged t13 patch writes on the v5 octopus (work/bestiary/patches/cyborg_c0_t13.md, its CPU run):
# {socket: (its outward normal in the creature's bind pose, its dims radius (m))}. Each normal is an axis of the socket
# node's own frame: its joint's +X for the eyes, the funnel's opening and the mantle apex (the arm tips' too: below,
# from each tip's azimuth and the arms' 6.7 deg rise there), the hat seat's up on the head top, the node's +Z on the
# glasses' bridge, the body's -X (down) at the mouth and its +X (up) at the crown centre. Radii: the eyeball; the
# skin's section 2 mm under the head top and under the apex (fit.section, its smaller half-width); half the bridge's
# gap between the eyeballs; the funnel's opening; the mouth's; the arm at its last joint. The fixture's joints carry no
# rotations, so typed_fixture writes these frames in the creature's frame (t13 writes them in each joint's)
T13_PORTS = dict(socket_eye_L=((0.8062, 0.1772, 0.5645), 0.015), socket_eye_R=((-0.8062, 0.1772, 0.5645), 0.015),
                 socket_eyes=((0.0, 0.7388, 0.674), 0.010546), socket_crown=((0.0, 1.0, 0.0), None),
                 socket_funnel=((0.7645, 0.2039, 0.6116), 0.008), socket_mantle_apex=((0.0, -0.1701, -0.9854), 0.01103),
                 socket_head_top=((0.0, 0.995, -0.0997), 0.015337), socket_mouth=((0.0, -1.0, 0.0), 0.002352))
# the arm chains' joint shares and radii (m) as t13 writes them (octopus_rig.arm_joint_s, octopus.arm_radius: the same
# CPU run); a listed cut sits at the midpoint of its two joints' shares (cut 14 at 0.7545)
T13_ARM_S = (0.0, 0.076738, 0.150093, 0.220239, 0.287333, 0.351323, 0.412162, 0.46977, 0.523994, 0.57466, 0.621659,
             0.664983, 0.704433, 0.739378, 0.76956, 0.796159, 0.820188, 0.843733, 0.867277, 0.890822, 0.914366,
             0.937911, 0.961455, 0.985)
T13_ARM_R = (0.026, 0.024854, 0.023758, 0.02273, 0.02172, 0.020679, 0.019627, 0.018535, 0.017383, 0.01618, 0.014965,
             0.013729, 0.012385, 0.010746, 0.009335, 0.008328, 0.007498, 0.006724, 0.005955, 0.005159, 0.004316,
             0.003451, 0.002571, 0.001677)
T13_TIP = dict(rise_deg=6.68, radius=T13_ARM_R[-1])


def typed_fixture(man=None, seats=True):
    """a manifest (fake_manifest by default) TYPED as t13 types the octopus: T13_SLOTS on its sockets (sides from x)
    with their PORTS (T13_PORTS: each frame from its normal by slots.port_frame, the dims of its interface), the eight
    arm chain records (kind tentacle, the listed cuts, the tip, the label from the tip's azimuth). With seats: the
    cyborg seats C5 / C6 will write (seat_module on the head seat, seat_visor on the face seat, seat_nozzle on the
    funnel, seat_tip on every arm tip), each with a validated entry for every variant of its families"""
    m = copy.deepcopy(man if man is not None else fake_manifest())
    for s, (kind, iface, paired) in T13_SLOTS.items():
        d = m['sockets'].get(s)
        if d is None:
            continue
        side = ('L' if d['world'][0] > 0 else 'R') if paired else ''
        if s in T13_PORTS:
            n, rad = T13_PORTS[s]
        else:                        # an arm tip: along its arm's azimuth, risen as the arms rise there
            az, ri = math.atan2(d['world'][0], d['world'][2]), math.radians(T13_TIP['rise_deg'])
            n, rad = (math.cos(ri) * math.sin(az), math.sin(ri), math.cos(ri) * math.cos(az)), T13_TIP['radius']
        fr = SL.port_frame(n, side)
        dims = SL.eye_dims(rad, fr['normal']) if iface in ('ball', 'dome') else (SL.mount_dims(rad) if iface ==
                                                                                 'mount' else None)
        d['slot'] = SL.slot_extras(kind, side, iface, d['bone'], frame=fr, dims=dims)
    labels = arm_labels_from(m)
    m['chains'] = {}
    for j in range(8):
        js = [f'arm{j}_{k:02d}' for k in range(24)]
        if not all(b in m['bones'] for b in js):
            continue
        rec = SL.chain_record(f'arm{j}', 'tentacle', js, T13_ARM_S, T13_ARM_R,
                              [dict(joint=k, s=round(0.5 * (T13_ARM_S[k - 1] + T13_ARM_S[k]), 6)) for k in T13_CUTS],
                              tip=f'socket_arm{j}_tip', side=labels[j][0] if labels else '',
                              label=labels[j] if labels else None)
        m['chains'][rec.pop('name')] = rec
    if seats:
        val = lambda arch: {f'{f}.{v}': dict(ok=True) for f, d in SL.FAMILIES.items() if d['seat'] == arch
                            for v in d['variants']}
        for s, arch in [('socket_head_top', 'module'), ('socket_eyes', 'visor'), ('socket_funnel', 'nozzle')] + \
                [(f'socket_arm{j}_tip', 'tip') for j in range(8)]:
            if s in m['sockets']:
                m['sockets'][s].setdefault('seats', {})[arch] = dict(
                    local=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0, 1.0], fit=dict(archetype=arch, validated=val(arch)))
    return m


def _codes(problems, severity=None):
    return {p['code'] for p in problems if severity is None or p['severity'] == severity}


def _self_test(verbose=True):
    n_ok = 0

    def check(cond, what):
        nonlocal n_ok
        if not cond:
            raise AssertionError(what)
        n_ok += 1
        if verbose:
            print(f'  ok  {what}')

    print('[recipe] self-test (CPU, fake manifests)')
    # ---- rolls: bit-identical vectors (runtime/remix.js selfTest asserts the same numbers) and their distribution
    check(key_id('') == 0x811C9DC5 and key_id('a') == 0xE40C292C, 'FNV-1a 32 vectors ("" and "a")')
    check(abs(hash01(0, 0) - 0.0) < 1e-12, 'hash01(0, 0) = 0 (lowbias32 of 0)')
    us = np.array([roll(s, 'dist') for s in range(20000)])
    check(abs(us.mean() - 0.5) < 0.01 and us.min() >= 0.0 and us.max() < 1.0, f'roll is uniform: mean {us.mean():.4f}')
    check(roll(7, 'element') == roll(7, 'element') and roll(7, 'element') != roll(8, 'element'), 'roll is deterministic')
    # ---- the data model
    r = make('octopus', name='plain', seed=3)
    man = fake_manifest()
    probs = validate(r, man)
    check(buildable(probs), 'the default octopus recipe builds on its manifest:\n' + report(probs))
    check(recipe_hash(r, 'offline') == recipe_hash(merge(r, dict(palette={'primary': dict(colour='#3060A0')})),
                                                   'offline'), 'a palette edit leaves the offline hash alone')
    check(recipe_hash(r, 'offline') != recipe_hash(merge(r, dict(spec=dict(arm_len=0.9))), 'offline'),
          'a spec edit changes the offline hash (a forge rebuild)')
    json.loads(canonical(r))
    check(True, 'recipes are JSON-able')
    check(canonical(normalise(r)) == canonical(r) and canonical(normalise(json.loads(canonical(r)))) == canonical(r),
          'normalise is idempotent on a full recipe and survives a JSON round trip')
    # ---- sockets, bones, parts, UV families
    bad = merge(r, dict(accessories=[dict(item='top_hat', socket='socket_head_crown', fit='proposal')]))
    check('socket.missing' in _codes(validate(bad, man), 'error'), 'an accessory on a missing socket is an error')
    bad = merge(r, dict(bones=[dict(match=r'^tentacle_\d+$', scale=[1, 1.2, 1.2])]))
    check('bone.missing' in _codes(validate(bad, man), 'error'), 'a bone op matching no bone is an error')
    m2 = fake_manifest(sockets=dict(socket_funnel=dict(bone='siphon_9', world=[0.0, 0.1, -0.1], fit={})))
    check('manifest.socket_bone' in _codes(validate(r, m2), 'error'), 'a socket on a missing joint is an error '
                                                                      '(study G: its spine and head-end sockets)')
    m3 = fake_manifest(sockets=dict(socket_eye_L=dict(bone='eye_L', world=[-0.025546, 0.181658, -0.034716], fit={})))
    check('manifest.side' in _codes(validate(r, m3), 'error'), '_L on the -X side is an error (study G: its left horn socket)')
    bad = merge(r, dict(parts={'socket_mouth': dict(part='octopus_beak', material='octopus_head')}))
    pr = validate(bad, man)
    check({'part.uv_family', 'part.uv_measured'} <= _codes(pr, 'error'),
          'a beak rendered with the head\'s material: declared AND measured UV-family errors')
    prec, rec = uv_match(man['uv']['octopus_beak'], man['uv']['octopus_head'])
    check(prec < 0.88, f'the measured check sees it: precision {prec:.2f}')
    bad = merge(r, dict(parts={'socket_mouth': dict(part='octopus_beak', material='octopus_teeth')}))
    check('part.material_missing' in _codes(validate(bad, man), 'error'), 'a missing material slot is an error')
    bad = merge(r, dict(parts={'socket_horn_L': dict(part='ram_horns', material='horn_ram')}))
    pr = validate(bad, man)
    check('socket.missing' in _codes(pr, 'error') and 'part.not_built' in _codes(pr, 'missing'),
          'a planned part on a socket the octopus lacks: socket error + part missing')
    tab = merge(r, dict(parts={'socket_mouth': dict(table=[
        dict(level=[0, 9], part='octopus_beak', material='octopus_beak'),
        dict(level=[10, 200], part='octopus_beak', material='octopus_arms')])}))
    pr = validate(tab, man)
    check(any(p['code'] == 'part.uv_family' and p['where'] == 'parts.socket_mouth[1]' for p in pr),
          'slot tables: every row is checked, not only the one the level picks')
    tab2 = merge(r, dict(level=7, parts={'socket_mouth': dict(table=[
        dict(level=[0, 9], part='octopus_beak', material='octopus_beak', weight=1.0, variant='a'),
        dict(level=[5, 20], part='octopus_beak', material='octopus_beak', weight=3.0, variant='b'),
        dict(level=[21, 200], part='octopus_beak', material='octopus_beak', variant='c')])}))
    picks = [resolve_parts(merge(tab2, dict(seed=s)))['socket_mouth']['variant'] for s in range(4000)]
    check(set(picks) == {'a', 'b'} and abs(picks.count('b') / 4000 - 0.75) < 0.03,
          f'slot tables resolve by level band and weight (b {picks.count("b") / 4000:.3f}, expected 0.75)')
    check('part.no_row' in _codes(validate(merge(tab2, dict(level=0, parts={'socket_mouth': dict(table=[
        dict(level=[5, 9], part='octopus_beak', material='octopus_beak')])})), man), 'warning'),
        'a level no row covers warns')
    # ---- accessories and fits
    hat = merge(r, dict(accessories=[dict(item='top_hat')]))
    check('accessory.fit_missing' in _codes(validate(hat, man), 'error'), 'a hat with no fit anywhere is an error')
    hat = merge(r, dict(accessories=[dict(item='top_hat', fit='proposal')]))
    pr = validate(hat, man)
    check('accessory.fit_missing' not in _codes(pr) and 'accessory.fit_override' in _codes(pr, 'warning') and
          'needs.socket_fits' in _codes(pr, 'missing'), 'a proposal fit seats it, flagged as not socket data')
    fitted = fake_manifest(sockets=dict(socket_head_top=dict(
        fit=dict(hat={k: v for k, v in FIT_PROPOSALS['octopus']['hat'].items() if k != 'seat'}))))
    pr = validate(merge(r, dict(accessories=[dict(item='top_hat')])), fitted)
    check('accessory.fit_override' not in _codes(pr) and 'accessory.fit_missing' not in _codes(pr),
          'socket fit data seats the hat with no override')
    badfit = merge(r, dict(accessories=[dict(item='top_hat', socket='socket_head_top',
                                             fit=dict(offset=[0, 0, 0], rotation=[0, 0, 0, 2], radius=0.05))]))
    check('accessory.fit_invalid' in _codes(validate(badfit, man), 'error'), 'a non-unit fit rotation is an error')
    tiny = merge(r, dict(accessories=[dict(item='top_hat', socket='socket_head_top',
                                           fit=dict(offset=[0, 0, 0], rotation=[0, 0, 0, 1], radius=0.01))]))
    check('accessory.scale' in _codes(validate(tiny, man), 'error'), 'a scale under 0.2 is an error')
    gl = merge(r, dict(accessories=[dict(item='round_glasses', fit='proposal')]))
    pr = validate(gl, man)
    check('accessory.lens_yaw' in _codes(pr, 'error'),
          f'flat glasses on +-{FIT_PROPOSALS["octopus"]["glasses"]["lens_yaw"]:.0f} degree eyes are an error')
    gl = merge(r, dict(accessories=[dict(item='wrap_goggles', fit='proposal')]))
    check('accessory.lens_yaw' not in _codes(validate(gl, man)), 'hinged goggles take the octopus eyes')
    sp_o = SPECIES['octopus']
    check(all(p['seat'] == sp_o['seats'][a] for a, p in FIT_PROPOSALS['octopus'].items()) and
          all(s.startswith('bone:') or s in man['sockets'] for s in sp_o['seats'].values()),
          'every proposal sits on the seat SPECIES names for its archetype (a proposal on another seat never '
          'resolves), and every socket seat is on the fixture')
    # ---- layers
    nolid = merge(r, dict(sculpt=[L for L in r['sculpt'] if L['id'] != 'funnel_lumen']))
    check('sculpt.locked_removed' in _codes(validate(nolid, man), 'error'), 'removing a locked carve is an error')
    try:
        swap_layer(r, 'eye_socket', 'growth')
        check(False, 'swap_layer must refuse a locked layer')
    except ValueError:
        check(True, 'swap_layer refuses a locked layer')
    cr = swap_layer(r, 'head_papillae', growth('metal_chrome', density=0.08))
    L0, L1 = layer(r, 'head_papillae'), layer(cr, 'growth_metal_chrome')
    check(L1['sites'] == L0['sites'] and L1['mask'] == L0['mask'] and L1['seed'] == L0['seed'],
          'swap_layer keeps the sites, mask and seed (crystals at the papillae\'s patch centres)')
    pr = validate(merge(cr, dict(tier='large')), man)
    miss = _codes(pr, 'missing')
    check('needs.layer_list_plan' in miss and not ({'needs.material_ids', 'needs.hexprism_stroke'} & miss),
          'a crystal growth layer says what the forge still lacks (the layer list) and not what landed (ids, prisms)')
    col = add_layer(r, dict(id='extra_pap', kind='papillae', sites='patch:head', density=0.3, material='skin',
                            seed=5))
    check('sculpt.site_collision' in _codes(validate(col, man), 'warning'), 'two adders on one site set warn')
    check(add_layer(r, growth('ice'))['sculpt'][-1]['kind'] == 'funnel_lumen', 'added layers go before the last '
                                                                              'carve')
    bad = add_layer(r, dict(id='fur', kind='groom_cards', sites='scatter', mask=dict(regions=['torso']),
                            material='skin', seed=1))
    check('sculpt.region' in _codes(validate(bad, man), 'error'), 'a region the family lacks is an error')
    # ---- elements, affixes, rolls
    check('element.unknown' in _codes(validate(merge(r, dict(element='plasma')), man), 'error'),
          'an unknown element is an error')
    check('element.affix' in _codes(validate(merge(r, dict(affixes=['vampiric'])), man), 'error'),
          'an unknown affix is an error')
    check('fx.contract' in _codes(validate(merge(r, dict(affixes=['explosive'])), man), 'missing'),
          'an FX affix on a creature without FX sockets is missing the FX contract')
    els = [roll_element(s, 'study_g') for s in range(20000)]
    fr = {e: els.count(e) / len(els) for e in ELEMENT_POOLS['study_g']}
    check(all(abs(fr[e] - w) < 0.015 for e, w in ELEMENT_POOLS['study_g'].items()), f'element rolls follow the pool: '
                                                                                 f'{ {k: round(v, 3) for k, v in fr.items()} }')
    check(all(roll_element(s) == roll_element(s) for s in range(50)), 'element rolls are deterministic')
    aff = [roll_affixes(s, 'fauna', 'small') for s in range(20000)]
    rate = sum(1 for a in aff if a) / len(aff)
    check(abs(rate - 0.01) < 0.003, f'fauna affix rate {rate:.4f} (study G 1 %)')
    rate = sum(1 for s in range(20000) if roll_affixes(s, 'foe')) / 20000
    check(abs(rate - 0.05) < 0.006, f'foe affix rate {rate:.4f} (study G 5 %)')
    au = resolve_auto(merge(r, dict(element='auto:remix', affixes='auto', seed=11)))
    check(au['element'] in EL.ELEMENTS and isinstance(au['affixes'], list), f'auto resolves: {au["element"]}, '
                                                                            f'{au["affixes"]}')
    # ---- crossbreed
    a = merge(r, dict(name='abyss', element='abyssal', spec=dict(eye_r=0.026), palette={'primary': dict(
        colour='#5A0F1A')}))
    b = merge(r, dict(name='dapper', accessories=[dict(item='top_hat', fit='proposal')], spec=dict(arm_len=0.9)))
    c1, c2 = crossbreed(a, b, seed=42), crossbreed(a, b, seed=42)
    check(canonical(c1) == canonical(c2), 'crossbreed is deterministic in its seed')
    check(c1['family'] == 'radial' and c1['lineage'] == ['abyss', 'dapper'], 'the child keeps the body\'s family')
    check(0.0215 <= c1['spec']['eye_r'] <= 0.026 and 0.78 <= c1['spec']['arm_len'] <= 0.9,
          f'same-base spec blends: eye_r {c1["spec"]["eye_r"]:.4f}, arm_len {c1["spec"]["arm_len"]:.3f}')
    beetle = make('beetle', name='beetle')
    ob = crossbreed(r, beetle, seed=9)
    check(any('dropped' in n and 'elytra' in n for n in ob['notes']), 'a beetle layer on regions a radial body lacks '
                                                                    'is dropped, with a note')
    check(any(L['id'] == 'chitin_plates' for L in ob['sculpt']) and ob['sculpt'][-1]['kind'] == 'funnel_lumen',
          'a generic beetle layer transfers, before the last carve')
    check(all(s in SPECIES['octopus']['sockets'] for s in ob['parts']), 'donor parts on sockets the body lacks drop')
    wolfy = crossbreed(make('wolf'), r, seed=3)
    pr = validate(wolfy, None)
    check('recipe.base_unbuilt' in _codes(pr, 'missing'), 'a crossbreed on an unbuilt base reports it')
    # ---- the runtime block and jitter
    rb = resolve_runtime(merge(r, dict(element='fire', tier='medium', palette={'soft': dict(colour='#E0B090')},
                                       accessories=[dict(item='top_hat', fit='proposal')])), man)
    json.dumps(rb, default=_jsonable)
    check(rb['element']['glow']['gain'] > 0 and rb['element']['surface']['kind'] == 'char',
          'resolve_runtime: fire at the medium tier has its glow gain and the char surface')
    LT = float(EL.lum(hex_to_lin('#E0B090')))
    check(abs(rb['palette']['soft']['val'] - LT / OCTOPUS_ZONES['soft']['lref']) < 1e-9,
          'palette val moves the zone\'s lref to the colour\'s L')
    ab = resolve_runtime(merge(r, dict(element='abyssal', display=dict(cycle=[['clouds', 2.0], ['flush', 1.0]]))), man)
    check(ab['display']['base']['glow'] == 1.0 and 'glow' not in MOODS['flush'],
          'an element\'s photophores set the resting glow weight, which moods without a glow key keep')
    pr = validate(merge(r, dict(display=dict(mood='alarm_rings'))), man)
    check('display.posed_space' not in _codes(pr, 'warning'),
          'procedural displays read the bind pose (display_coords): no posed-space warning')
    check('display.posed_space' in _codes(validate(merge(r, dict(display=dict(mood='alarm_rings'))), man,
                                                   caps=dict(FORGE_CAPS, display_coords=False)), 'warning'),
          'without bind-pose coordinates the procedural displays warn that they are in posed space')
    acc = rb['accessories'][0]
    check(acc['fit_source'] == 'proposal' and abs(acc['scale'] - FIT_PROPOSALS['octopus']['hat']['radius'] / 0.091)
          < 1e-9, f'the hat resolves its proposal fit: scale {acc["scale"]:.3f}')
    j1, j2 = apply_jitter(rb, 77), apply_jitter(rb, 77)
    check(json.dumps(j1, default=_jsonable) == json.dumps(j2, default=_jsonable), 'apply_jitter is deterministic')
    d = np.array(j1['palette']['soft']['target']) / np.array(rb['palette']['soft']['target'])
    check(np.all(np.abs(d - 1.0) < 0.25), f'the jitter is small: ratios {np.round(d, 3).tolist()}')
    # ---- the fixture's arm map; documentation-free layers
    check(arm_labels_from(man) == list(SPECIES['octopus']['arm_labels']),
          f'the fixture\'s arm tips give the arm map {arm_labels_from(man)}')
    check(arms_regex(['L1', 'R1'], '00') == '^arm(7|0)_00$', 'arms_regex names anatomical arms (L1 = arm7, R1 = arm0)')
    nosrc = copy.deepcopy(r)
    for L in nosrc['sculpt']:
        L.pop('src', None)
    check('needs.layer_list_plan' not in _codes(validate(nosrc, man)) and
          recipe_hash(nosrc, 'offline') == recipe_hash(r, 'offline'),
          'the base layers without their src strings are the base plan (no rebuild, no layer-list need)')
    # ---- palette
    try:
        hex_to_lin('#12345')
        check(False, 'hex_to_lin must refuse a 5-digit colour')
    except ValueError:
        check(True, 'hex_to_lin refuses a 5-digit colour (it used to parse to a wrong one)')
    pr = validate(merge(r, dict(palette={'primary': dict(colour='red'), 'shell': dict(colour='#123456'),
                                         'soft': dict(colour='#123456', strength=1.5)})), man)
    check({'palette.colour', 'palette.role', 'palette.value'} <= _codes(pr, 'error'),
          'bad palette colours, roles and strengths are errors')
    # ---- the mood cycle
    for cyc in ([['clouds', 0.0], ['flush', 0.0]], [['clouds']], 'clouds'):
        pr = validate(merge(r, dict(display=dict(cycle=cyc))), man)
        check('display.cycle' in _codes(pr, 'error'), f'a malformed or zero-length mood cycle is an error: {cyc!r}')
    # ---- spec couplings (the head mass on ML), the end taper's slope, ML against the absolute parts
    pr = validate(merge(r, dict(spec=dict(ML=0.30))), man)
    check({'spec.coupled', 'spec.ml_absolute'} <= _codes(pr, 'warning'),
          'ML x1.5 without the head mass: it must scale with ML, and the block-out\'s absolute parts are named')
    hm = [x * 1.5 for x in OCTOPUS_SPEC['head_mass'][:3]] + [OCTOPUS_SPEC['head_mass'][3]]
    check('spec.coupled' not in _codes(validate(merge(r, dict(spec=dict(ML=0.30, head_mass=hm))), man)),
          'ML x1.5 with the head mass scaled x1.5 is in range')
    check('spec.taper_slope' in _codes(validate(merge(r, dict(spec=dict(taper_s0=0.93, taper_k=0.55))), man),
                                       'warning') and abs(taper_slope(0.93, 0.55) - 1.6) < 1e-9 and
          taper_slope(0.90, 0.25) < 1.0,
          f't18\'s 0.93 / 0.55 taper warns (slope 1.6); the forge\'s 0.90 / 0.25 is {taper_slope(0.90, 0.25):.2f}')
    bad_m = [s for s in range(300) if {'spec.coupled', 'spec.taper_slope', 'spec.range'} &
             _codes(validate(mutate(r, s, amount=0.15), man))]
    check(not bad_m, f'300 mutations keep the head mass on ML, the taper under its slope and every key in range '
                     f'(bad seeds {bad_m[:5]})')
    # ---- accessories: a shared seat; seat nodes (the accessories fit system)
    two = merge(r, dict(accessories=[dict(item='top_hat', fit='proposal'), dict(item='cowboy_hat', fit='proposal')]))
    check('accessory.seat_shared' in _codes(validate(two, man), 'warning'), 'two hats on one seat warn')
    table = [[0.002 * (k + 1), 0.012 + 0.002 * k, 0.014 + 0.002 * k, 0.0, 0.0005 * k, 0.013 + 0.002 * k]
             for k in range(12)]
    seat_hat = dict(local=[0.01, 0.02, 0.0], rotation=[0.0, 0.0, 0.0, 1.0],
                    fit=dict(archetype='hat', table_columns=['depth', 'rx', 'rz', 'cx', 'cz', 'r_mean'], table=table,
                             default=dict(depth=0.011), validated=dict(top_hat=dict(depth=0.016))))
    seated = fake_manifest(sockets=dict(socket_head_top=dict(seats=dict(hat=seat_hat))))
    res = resolve_accessory(dict(item='top_hat'), r, seated)
    check(res['fit_source'] == 'seat' and abs(res['fit']['radius'] - 0.027) < 1e-9 and
          np.allclose(res['fit']['offset'], [0.01, 0.004, 0.0035]) and abs(res['scale'] - 0.027 / 0.091) < 1e-9,
          f'a seat_hat table seats the hat at its validated depth: offset {res["fit"]["offset"]}, radius '
          f'{res["fit"]["radius"]:.3f}')
    check(not ({'accessory.fit_missing', 'accessory.fit_override'} &
               _codes(validate(merge(r, dict(accessories=[dict(item='top_hat')])), seated))),
          'a seat node is socket data (nothing flagged)')
    res2 = resolve_accessory(dict(item='cowboy_hat'), r, seated)
    check(res2['fit']['seat_depth_from'] == 'the table default' and abs(res2['fit']['seat_depth'] - 0.011) < 1e-12,
          'an item the forge did not validate seats at the table default')
    eyes = fake_manifest(sockets=dict(socket_eyes=dict(seats=dict(
        glasses=dict(local=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0, 1.0],
                     fit=dict(archetype='glasses', spacing=0.0715, standoff=0.003, eyes=[]))))))
    pr = validate(merge(r, dict(accessories=[dict(item='wrap_goggles')])), eyes)
    check(any(p['code'] == 'accessory.fit_missing' and 'rig fit' in p['message'] for p in pr),
          'a glasses seat (a rig fit) cannot seat remix glasses, and the error says why')
    pr = validate(merge(r, dict(accessories=[dict(item='wrap_goggles', fit='proposal')])), eyes)
    check(resolve_accessory(dict(item='wrap_goggles', fit='proposal'), r, eyes)['fit_source'] == 'proposal' and
          {'accessory.fit_override', 'accessory.seat_format'} <= _codes(pr, 'warning') and
          'needs.socket_fits' not in _codes(pr),
          'past a glasses rig seat the proposal seats them, and the validator says the creature\'s seat was bypassed')
    check(rb['accessories'][0].get('authored') == {'radius': 0.091},
          'the runtime block carries the item\'s authored size (proxies need no catalog)')
    # ---- bones: non-uniform chain roots; malformed scales
    pr = validate(merge(r, dict(bones=[dict(match=r'^arm\d+_00$', scale=[1.0, 1.12, 1.12])])), man)
    check('bone.nonuniform' in _codes(pr, 'warning'), 'a non-uniform scale on chain roots warns (posed shape, shear)')
    check('bone.nonuniform' not in _codes(validate(merge(r, dict(bones=[dict(match=r'^arm\d+_00$', scale=1.1)])),
                                                   man)), 'a uniform scale on chain roots does not')
    check('bone.op' in _codes(validate(merge(r, dict(bones=[dict(bone='head', scale='big')])), man), 'error'),
          'a malformed bone scale is an error, not a crash')
    # ---- the zone remap reference
    c = np.array([0.292, 0.074, 0.037])
    o = EL.zone_remap(c, EL.ELEMENTS['fire']['zones']['soft'], 0.308)
    check(np.all(o >= 0) and np.all(o <= 1) and EL.ENVELOPE[0] - 1e-9 <= float(EL.lum(o)) <= EL.ENVELOPE[1] + 1e-9,
          'zone_remap stays in gamut and in the skin envelope')
    o = EL.zone_remap(c, EL.ELEMENTS['liquid_metal']['zones']['primary'], 0.118)
    check(abs(float(EL.lum(o)) - 0.78) < 0.01, f'absolute mode gives a metal its F0 (mercury L {float(EL.lum(o)):.3f})')
    check(np.allclose(EL.zone_remap(c, EL.IDENTITY, 0.1), c), 'the identity zone is the identity')
    check(EL.check_table() == [], 'the element table is self-consistent')
    # ---- the CYBORG slot rule (C0: remix/slots.py; work/bestiary/tests/c00_slots.py prints every gate)
    check(SL.check_table() == [] and len(SL.allowed_pairs()) == 18 and len(SL.CYBORG_FAMILIES) == 13   # (C3) mech_arm
          and SL.ORGAN_FAMILIES == ('leg_graft',),
          f'the closed table checks itself: {len(SL.CYBORG_FAMILIES)} cyborg + {len(SL.ORGAN_FAMILIES)} organ families x '
          f'{len(SL.KINDS)} kinds, '
          f'{len(SL.allowed_pairs())} allowed pairs, none against Skye\'s never-list')
    tm = typed_fixture()
    check(SL.check_manifest(tm, 'octopus') == [], 'the octopus typed as t13\'s patch types it passes the manifest '
                                                  'checks (kinds on their joints, seats under their kinds, chains)')
    first = dict(parts={'eye': [dict(part='eye_implant', variant='lens', side='L')],
                        'head': [dict(part='sensor_module', variant='dome')]},
                 limbs=[dict(kind='tentacle', chain='R1', cut_joint=8, part='mech_tentacle')])
    cy = merge(r, dict(cyborg=first))
    pl = resolve_cyborg(cy, tm)
    check(sorted((p['part'], p['site']) for p in pl) == [('eye_implant', 'socket_eye_L'), ('mech_tentacle', 'arm0'),
                                                         ('sensor_module', 'socket_head_top')] and
          not _codes(validate(cy, tm), 'error'),
          'the first target resolves by kind (implant L, dome on the head seat, R1 = arm0 cut at 8), no error')
    check('cyborg.untyped' in _codes(validate(cy, man), 'error'), 'on an untyped glb every cyborg part is refused '
                                                                  '(cyborg.untyped)')
    try:
        resolve_cyborg(cy, man)
        check(False, 'resolve_cyborg must refuse an untyped glb')
    except SL.SlotError as e:
        check('cyborg.untyped' in str(e), 'resolve_cyborg raises SlotError on an untyped glb')
    arm_head = merge(r, dict(cyborg=dict(parts={'head': [dict(part='back_mount', variant='folded_arm')]})))
    check('cyborg.kind' in _codes(validate(arm_head), 'error') and 'cyborg.never' in _codes(validate(arm_head), 'error'),
          'a robot arm in the head table: cyborg.kind (each row tested against its kind) and Skye\'s cyborg.never')
    try:
        resolve_cyborg(arm_head, tm)
        check(False, 'resolve_cyborg must refuse a back mount in the head table')
    except SL.SlotError as e:
        check('back_mount' in str(e) and 'socket_head_top' in str(e), 'resolve_cyborg refuses it, naming the part and '
                                                                      'the slot')
    tent = merge(r, dict(cyborg=dict(parts={'head': [dict(part='mech_tentacle')]})))
    check('cyborg.interface' in _codes(validate(tent, tm), 'error'), 'a chain part in a socket table: cyborg.interface')
    grip = merge(r, dict(cyborg=dict(parts={'limb_tip': [dict(part='gripper')]})))
    check('cyborg.requires' in _codes(validate(grip, tm), 'error'), 'a gripper on an organic tip: cyborg.requires')
    cut9 = merge(r, dict(cyborg=dict(limbs=[dict(kind='tentacle', chain='arm3', cut_joint=9, part='mech_tentacle')])))
    check('cyborg.cut' in _codes(validate(cut9, tm), 'error'), 'a cut that is not listed: cyborg.cut')
    hat = dict(parts={'head': [dict(part='sensor_module')]})
    check(all('cyborg.seat_shared' in _codes(validate(merge(r, dict(cyborg=hat, accessories=[dict(item=it, fit='proposal')])),
                                                      tm), 'error') for it in ('top_hat', 'space_helmet')) and
          'cyborg.seat_shared' in _codes(validate(merge(r, dict(cyborg=dict(parts={'face': [dict(part='visor')]}),
                                                             accessories=[dict(item='mask_smile', fit='proposal')])), tm),
                                         'error'),
          'a module XOR a hat or a helmet, a visor XOR a mask (seat_shared covers every accessory on the seat)')
    back = merge(r, dict(cyborg=dict(parts={'back': [dict(part='back_mount', variant='turret')]})))
    check('cyborg.no_site' in _codes(validate(back, tm), 'error'), 'the octopus has no back slot (its mantle reads as '
                                                                   'its head): a back table finds no site, an error')
    bad_t = typed_fixture()
    bad_t['sockets']['socket_mantle_apex']['slot'] = SL.slot_extras(
        'back', '', 'mount', 'mantle_3', frame=bad_t['sockets']['socket_mantle_apex']['slot']['frame'],
        dims=SL.mount_dims(0.014))
    bad_t['sockets']['socket_head_top']['seats']['mount'] = dict(fit=dict(archetype='mount'))
    codes = _codes(SL.check_manifest(bad_t, 'octopus'), 'error')
    check({'manifest.slot_joint', 'manifest.seat_kind'} <= codes, 'a back slot typed on the mantle and a seat_mount '
                                                                  'under the head seat are manifest errors')
    check('part.seat' in _codes(validate(merge(r, dict(parts={'socket_head_top': dict(part='sensor_module',
                                                                                        material='octopus_head')})), tm),
                                'error'), 'a cyborg family named in the organic parts section is a part.seat error')
    # ---- C0b (the lead's calls, 10-21; work/bestiary/tests/c00_slots.py G10 prints every case)
    port = copy.deepcopy(tm)
    port['sockets']['socket_head_top']['slot']['frame']['tangent'] = list(
        port['sockets']['socket_head_top']['slot']['frame']['normal'])
    port['sockets']['socket_funnel']['slot'].pop('dims')
    codes = _codes(SL.check_manifest(port, 'octopus'), 'error')
    check({'manifest.slot_frame', 'manifest.slot_dims'} <= codes, 'a socket is a port: a degenerate frame (its tangent '
                                                                  'along its normal) and a mount without dims are errors')
    try:
        SL.slot_extras('head', '', 'mount', 'mantle_0', frame=tm['sockets']['socket_head_top']['slot']['frame'])
        check(False, 'slot_extras must refuse a mount without dims')
    except ValueError:
        check(True, 'slot_extras refuses a mount without dims at export')
    grown = swap_layer(cy, 'arm_papillae', growth('ice'))
    pv = validate(grown, tm)
    check('cyborg.covered' in _codes(pv, 'error') and not _codes(validate(cy, tm), 'error'),
          'cyborg.covered: an ice growth on the arms (to share 0.97) beside R1 cut at 8 is an error; the first target '
          'without it stays clean')
    nn = merge(r, dict(cyborg=dict(parts={'head': [dict(part='none', weight=1.0), dict(part='sensor_module')]})))
    got = {len(resolve_cyborg(merge(nn, dict(seed=s)), tm)) for s in range(40)}
    check(got == {0, 1} and not _codes(validate(nn, tm), 'error'), 'a none row: the seeded pick leaves the head seat '
                                                                   'empty on some seeds, seats the module on others')
    check(all(SL.never(f, 'back') for f in SL.FAMILIES if SL.PART_CLASS[f] != 'mount') and
          not SL.never('back_mount', 'back'), 'a back takes only mounts (Skye\'s rule, its third clause)')
    vh = lambda it: _codes(validate(merge(r, dict(cyborg=dict(parts={'face': [dict(part='visor')]}),
                                                  accessories=[dict(item=it, fit='proposal')])), tm), 'error')
    check('cyborg.seat_shared' in vh('space_helmet') and 'cyborg.seat_shared' not in vh('hardhat'),
          'the space helmet encloses the face: a visor under it is refused; under a hardhat it is not')
    ap = merge(r, dict(cyborg=dict(parts={'head': [dict(part='sensor_module')]}), accessories=[dict(
        item='top_hat', socket='socket_mantle_apex', fit=dict(offset=[0.0, 0.0, 0.0], rotation=[0.0, 0.0, 0.0, 1.0],
                                                              radius=0.04))]))
    check('cyborg.seat_shared' in _codes(validate(ap, tm), 'error'), 'the octopus\'s head top and mantle apex are one '
                                                                     'seat group: a hat on the apex beside a module')
    # ---- the HERO tier (the lead, 10-21: 150,000 triangles beside large's 100,000), the octopus's budget tier (C0b)
    big = typed_fixture(fake_manifest(budget=dict(tris=122560, joints=203)))
    at = lambda t: _codes(validate(merge(cy, dict(tier=t)), big), 'warning')
    check(SPECIES['octopus']['budget_tier'] == 'hero' and not any('budget.tris' in at(t) for t in TIERS) and
          'recipe.tier' not in _codes(validate(merge(r, dict(tier='hero')), man)),
          'the first target on the 122,560-triangle octopus (+6,846): inside its budget tier hero\'s 150,000 at every '
          'recipe tier')
    # ---- the octopus's own budget record (the lead's L1 call): its suckers, one primitive of size classes all drawn,
    # held to t26's 192,000 (= the forge's TRI_BUDGET, read from its source), the rest to hero's 150,000
    import ast as _ast
    _src = open(os.path.join(FORGE_SPECIES, 'octopus_suckers.py'), encoding='utf-8').read()
    _tb = [_ast.literal_eval(n.value) for n in _ast.parse(_src).body if isinstance(n, _ast.Assign) and
           any(getattr(t, 'id', None) == 'TRI_BUDGET' for t in n.targets)]
    _om = lambda suck, body: dict(budget=dict(tris=suck + body, joints=203), sockets={}, bones=[], materials=dict(
        octopus_head=dict(kind='skin', tris=body), octopus_suckers=dict(kind='sucker', tris=suck)))
    _bw = lambda man_: _codes(validate(make('octopus'), man_), 'warning')
    check(_tb == [SPECIES['octopus']['budget_kinds']['sucker']] and
          not {'budget.tris', 'budget.kind'} & set(_bw(_om(191584, 46296))) and
          'budget.kind' in _bw(_om(192001, 46296)) and 'budget.tris' not in _bw(_om(192001, 46296)) and
          'budget.tris' in _bw(_om(191584, 150001)) and 'budget.kind' not in _bw(_om(191584, 150001)),
          'the octopus\'s own budget record: its 191,584 drawn sucker triangles held to t26\'s 192,000 (the forge\'s '
          'TRI_BUDGET), its 46,296 body to hero\'s 150,000: no warning; either over its own bar warns alone')
    wolf_big = dict(budget=dict(tris=122560, joints=118), sockets={}, bones=[])
    check('budget.tris' in _codes(validate(make('wolf', tier='large'), wolf_big), 'warning') and
          'budget.tris' not in _codes(validate(make('wolf', tier='hero'), wolf_big), 'warning'),
          'a base without a budget tier is capped by its recipe\'s: 122,560 triangles over large, inside hero')
    check(EL.layers_for('fire', el_tier('hero')) == EL.layers_for('fire', 'elite') and
          resolve_runtime(merge(r, dict(tier='hero', element='fire')), man)['element']['layers'] ==
          list(EL.layers_for('fire', 'elite')), 'elements.py reads the hero tier as elite')
    cg = merge(cy, dict(cyborg=dict(glow=dict(colour='#0080ff'))))
    check(recipe_hash(cg, 'offline') == recipe_hash(cy, 'offline') and recipe_hash(cg, 'runtime') !=
          recipe_hash(cy, 'runtime') and recipe_hash(cy, 'offline') != recipe_hash(r, 'offline') and
          recipe_hash(cy, 'runtime') == recipe_hash(r, 'runtime') and 'cyborg' not in r,
          'the cyborg glow is runtime, its parts offline; a recipe without the section hashes as before')
    check(_SPEC_SRC == 'forge source' and 'ML' in OCTOPUS_SPEC, f'the octopus SPEC is read from the forge source '
                                                                f'({len(OCTOPUS_SPEC)} keys)')
    drift = check_species_sync()
    print(f'  info: fallback copies vs the forge: {"in sync" if not drift else drift}')
    print(f'[recipe] self-test: {n_ok} checks passed')
    return n_ok


def parity_vectors():
    """the numbers runtime/remix.js selfTest() asserts (keyId, roll, jitterRGB, zoneRemapRGB)"""
    out = dict(keyId={k: key_id(k) for k in ('', 'a', 'element', 'pal.primary', 'clouds.k')},
               roll=[[s, k, roll(s, k)] for s, k in ((1, 'element'), (7, 'affix.chance'), (123456, 'pal.soft.h'),
                                                     (2147483646, 'clouds.w'), (0, 'display.cycle'))],
               jitter=[[list(c), s, k, h, v, list(jitter_rgb(c, s, k, h, v))]
                       for c, s, k, h, v in (((0.46, 0.72, 0.83), 5, 'pal.primary', 6.0, 0.06),
                                             ((1.0, 0.30, 0.03), 99, 'el.soft', 3.0, 0.04))],
               remap=[])
    cases = [((0.292, 0.074, 0.037), 'fire', 'soft', 0.308), ((0.292, 0.074, 0.037), 'fire', 'primary', 0.118),
             ((0.571, 0.242, 0.184), 'ice', 'soft', 0.308), ((0.292, 0.074, 0.037), 'rust', 'primary', 0.118),
             ((0.776, 0.617, 0.515), 'liquid_metal', 'accent', 0.644), ((0.05, 0.02, 0.6), 'electric', 'soft', 0.308),
             ((0.235, 0.060, 0.031), 'abyssal', 'pattern', 0.095)]
    for c, el, role, lref in cases:
        z = {k: v for k, v in EL.ELEMENTS[el]['zones'][role].items() if k != 'src'}
        o = EL.zone_remap(np.array(c), z, lref, 0.8)
        out['remap'].append([list(c), z, lref, 0.8, [float(x) for x in o]])
    return out


if __name__ == '__main__':
    if '--vectors' in sys.argv:
        print(json.dumps(parity_vectors(), default=_jsonable))
        sys.exit(0)
    if '--sync' in sys.argv:
        bad = check_species_sync(imported='--import' in sys.argv)
        print('[recipe] octopus fallback copies vs forge:', 'in sync' if not bad else bad)
        sys.exit(1 if bad else 0)
    _self_test(verbose='-q' not in sys.argv)
    if '--glb' in sys.argv:
        k = sys.argv.index('--glb')
        path = sys.argv[k + 1] if len(sys.argv) > k + 1 and not sys.argv[k + 1].startswith('-') else \
            os.path.join(REPO, SPECIES['octopus']['glb'])
        man = manifest_from_glb(path)
        print(f'[recipe] manifest from {man["source"]}: {man["species"]} ({man["family"]}), {len(man["bones"])} '
              f'bones, {len(man["sockets"])} sockets, materials {list(man["materials"])}, parts '
              f'{ {k: v["seats"] for k, v in man["parts"].items()} }, {man["budget"]["tris"]} triangles')
        for note in man['inferred']:
            print(f'  inferred: {note}')
        drift = fixture_drift(man)
        print('  the self-test fixture vs this glb: ' + ('it mirrors it' if not drift else
                                                         f'{len(drift)} difference(s) (update fake_manifest)'))
        for d in drift:
            print(f'    {d}')
        labs, want = arm_labels_from(man), list(SPECIES['octopus']['arm_labels'])
        print(f'  arm map from the tip sockets: {labs} ' + ('(= SPECIES arm_labels)' if labs == want else
                                                           f'(SPECIES says {want}: update it)'))
        seats = {s: sorted(d.get('seats') or {}) for s, d in man['sockets'].items() if d.get('seats')}
        print(f'  seat nodes: {seats or "none (t13 writes no seat_* nodes yet)"}')
        typed = {s: d['slot'].get('kind') for s, d in man['sockets'].items() if isinstance(d.get('slot'), dict)}
        print(f'  slot kinds: {typed or "none (an untyped glb: no cyborg part seats on it)"}; chains '
              f'{sorted(man.get("chains") or {}) or "none"}; {report(SL.check_manifest(man, "octopus"), "typing:")}')
        names = list(man['uv'])
        for a in names:
            row = ', '.join('%s %.2f/%.2f' % ((b,) + uv_match(man['uv'][a], man['uv'][b])) for b in names)
            print(f'  UV precision/recall of {a} on: {row}')
        for a in names:
            for b in names:
                if a != b and a in man['parts'] and man['parts'][a]['seats']:   # the suckers seat on no socket
                    bad = merge(make('octopus'), dict(parts={man['parts'][a]['seats'][0]: dict(
                        part=a, material=b)}))
                    pm = [p for p in validate(bad, man) if p['code'] == 'part.uv_measured']
                    print(f'  re-table {a} onto {b}: ' + (pm[0]['severity'] + ' ' + pm[0]['message'] if pm else
                                                         'NOT caught by the measured check'))
        print(report(validate(make('octopus'), man), 'default octopus vs the shipped glb:'))
