"""RED-TAILED HAWK (Buteo jamaicensis), H1: the Bestiary's first AVIAN base (work/bestiary/research/HAWK_PLAN.md, D1).

H1 is a COMPOSITE (the lead's call, 11-07; plan §0.2, §2.10 item 1), one coherent animal by one rule:
  - the skeleton = USNM 553822, an adult female (NJ), every bone measured in two views on its 2 cm bar;
  - the wing planform = the Beaty series (8 wings, dorsal and ventral), as their mean OUTLINE (D1.0's
    research/../hawk/d1_work/wing/outlines.json, the mean of the dorsal and ventral means: plan §2.3's rule);
  - the colour = the Beaty adult B015440 (calibrated on its ColorChecker), in colour.json, read at D1.8;
  - ratios from the live photos (c049 glide, c018 head, c022 perch).
D1.0 measured B015328 (one bird with a partial skeleton and a wing): its bones read 1.05-1.12x S1's and its wing is
shorter than the mean (484.5 / 509.0 mm), so the naive wing / skeleton ratio sits about 20 % under the composite's.
The prep's cut and arm lay are unknown, so this is not a clean closure test; the composite stands on the lead's call
and the number is reported (hawk/d1_notes/NOTES.md).

UNITS: LIFE MILLIMETRES and degrees. Built and exported at life (plan §4.3: the smallest modelled feature is 0.3-1 mm,
so the forge's metric constants do not bite): author_scale 1, scale_m = 1e-3.
THE PLAN FRAME: +z forward along the body axis, +y up, +x the bird's LEFT; the origin at the hip joints' midpoint.
Every sided value is the LEFT side's; the right is its mirror (x -> -x).

TAGS holds each leaf's source in the plan's legend: [P] primary, [C] compiled secondary, [R] reference asset, [H]
house rule / prior finding / the lead's call, [E] estimate with its gate, [S] search summary only, [M] measured, [D]
derived. [M] and [D] carry a maker: -pl the plan's scripts (research/hawk_scripts), -d0 D1.0's scripts
(hawk/scripts/wing_outlines.py, look.py reads). d1_00_spec.py checks every sourced leaf against its file.
"""
import copy
import re

SPEC = dict(
    family='avian', head_archetype='raptor', author_scale=1.0,
    # ---- S1 = USNM 553822: greatest lengths (mean of the views) and widths, plan §2.2
    bones=dict(humerus=92.3, ulna=110.6, radius=102.0, carpometacarpus=54.4, digit2=33.7, femur=76.0,
               tibiotarsus=98.4, tarsometatarsus=71.9, coracoid=43.8, scapula=53.6, furcula=39.1, sternum=64.1,
               pelvis=67.0, skull=70.3, mandible=51.2),
    bone_width=dict(humerus=21.6, ulna=12.3, radius=7.7, carpometacarpus=12.8, femur=18.1, tibiotarsus=15.1,
                    tarsometatarsus=15.1, coracoid=19.5, sternum=35.3, pelvis=34.1, skull=38.5, mandible=21.7),
    # ---- the wing: the Beaty mean outline and the feather counts, plan §2.3, §5.2
    wing=dict(semispan=525.2, semispan_dorsal=515.3, semispan_ventral=535.1, area_one_cm2=939.8,
              n_primary=10, n_secondary=13, n_tertial=3, n_alula=4, emarginated_first=6, longest_primary=8,
              wrist_to_tip=326.0, slotted_tips=5),
    # ---- the tail, plan §2.6
    tail=dict(length=190.0, fan_glide=236.0, spread_glide=44.9, spread_land=120.0, n_rectrix=12),
    # ---- the head (c018, scaled by S1's skull), plan §2.4
    head=dict(culmen=23.0, cere=9.5, gape=39.8, hook_drop=9.6, hook_overhang=7.2, iris=11.7, pupil_ratio=0.395,
              eye=22.5, nostril=(3.7, 2.1), brow_overhang=3.5, plumage=4.0),
    # ---- legs and feet, plan §2.5
    feet=dict(middle_toe=46.0, hallux_claw=28.0, phalanges=(2, 3, 4, 5), claw_arc=135.0),
    # ---- the trunk block-out, plan §4.5
    body=dict(trunk_len=150.0, trunk_w=130.0, trunk_h=150.0, neck_joints=8, neck_vertebrae=13.5, mass_g=1040.7),
    # ---- the rest poses, plan §2.7
    rest=dict(perch_axis=60.0, c022_axis=76.3, primary_tip_share=0.893, tail_below_perch=0.443),
    # ---- the texture sets (the lead, 11-07: one density, HEAD its own 1024 set)
    texture=dict(px_per_m=6000.0, BODY=4096, FLIGHT=4096, HEAD=1024, COAT=2048, EYE=1024),
    # ---- the graft rings, plan §8.1 (K = vertex count per loop)
    rings=dict(beak_upper=24, beak_lower=16, wing=24, foot=16, ankle=16, tail=16, head=32),
)

REGIONS = ('trunk', 'neck', 'head', 'beak', 'eye', 'wing', 'leg', 'foot', 'talon', 'tail')
REGION_ID = {name: i for i, name in enumerate(REGIONS)}

_S1 = ('[M-pl]', 'USNM 553822 (S1), the mean over its views on the 2 cm bar; plan §2.2')
_S1W = ('[M-pl]', 'USNM 553822 (S1), the silhouette\'s width; plan §2.2')
TAGS = {
    'family': ('[H]', 'plan §4.1: forge/families/avian.py'),
    'head_archetype': ('[H]', 'plan §4.1: forge/heads/raptor.py'),
    'author_scale': ('[H]', 'plan §4.3: built at life'),
    'bones.digit2': ('[E]', '0.62 x the carpometacarpus (the accipitrid hand); gate D1.1: the arm + primaries close '
                            'the semispan'),
    'wing.semispan': ('[M-d0]', 'outlines.json mean_both: the mean of the dorsal and ventral prep means (§2.3 rule)'),
    'wing.semispan_dorsal': ('[M-d0]', 'outlines.json mean_dorsal (n 8; plan_numbers 515.8 by bbm.json)'),
    'wing.semispan_ventral': ('[M-d0]', 'outlines.json mean_ventral (n 8)'),
    'wing.area_one_cm2': ('[M-d0]', 'mean of outlines.json\'s dorsal and ventral mean areas (910.7, 968.9)'),
    'wing.n_primary': ('[S]', 'USFWS Feather Atlas: 10 primaries'),
    'wing.n_secondary': ('[E]', '13; the Feather Atlas gives 10-12+; not countable on B015440c at this resolution'),
    'wing.n_tertial': ('[E]', 'plan §5.2'),
    'wing.n_alula': ('[E]', 'plan §5.2'),
    'wing.emarginated_first': ('[M-pl]', 'c049: five slotted tips, so P6-P10 emarginated (plan §2.3)'),
    'wing.longest_primary': ('[M-d0]', 'B015440 dorsal: the 3rd of the five slotted tips is longest (P10 short, P8 '
                                       'longest), look/B015440_hand.png'),
    'wing.wrist_to_tip': ('[M-d0 from E]', 'B015440: wrist placed by eye at (372, 103) mm on the mat, P8 tip (668, 236)'),
    'wing.slotted_tips': ('[M-pl]', 'c049 left wing (landmarks.json c049.slotted_tips_left)'),
    'tail.length': ('[E]', 'plan §2.6: between c049 177 and [C] 188-259; gate D1.3: tail / span in the photos\' spread'),
    'tail.fan_glide': ('[M-pl from E]', 'c049 tail_fan_over_span x the span 1.151 m (plan_numbers c049_scaled_by_span)'),
    'tail.spread_glide': ('[M-pl]', 'c049 (landmarks.json c049.tail_spread_deg)'),
    'tail.spread_land': ('[E]', 'c158 by eye (plan §2.6)'),
    'tail.n_rectrix': ('[S]', 'USFWS Feather Atlas: 6 per side'),
    'head.culmen': ('[M-pl from E]', 'c018, cere front to tip (landmarks.json c018.culmen_from_cere_mm_E)'),
    'head.cere': ('[M-pl from E]', 'c018 (c018.cere_length_mm_E)'),
    'head.gape': ('[M-pl from E]', 'c018, rictus to tip (c018.gape_mm_E)'),
    'head.hook_drop': ('[M-pl from E]', 'c018 (c018.hook_drop_below_tomium_mm_E)'),
    'head.hook_overhang': ('[M-pl from E]', 'c018 (c018.upper_past_lower_mm_E)'),
    'head.iris': ('[M-pl from E]', 'c018 visible iris (c018.iris_d_mm_E)'),
    'head.pupil_ratio': ('[M-pl]', 'c018 (c018.pupil_over_iris)'),
    'head.eye': ('[E]', 'S1 orbit about 23 mm by eye (plan §2.4)'),
    'head.nostril': ('[M-pl from E]', 'c018 oval, plan §2.4'),
    'head.brow_overhang': ('[E]', 'c018, c019 (plan §2.4); gate D1.3 head outline vs c018'),
    'head.plumage': ('[E]', 'plan §4.5: plumage depth 3-5 mm over the skull'),
    'feet.middle_toe': ('[E]', '[C] 38.3-53.8; the Beaty ventral skins hold their feet curled (B015440d seen): unmeasurable'),
    'feet.hallux_claw': ('[E]', '[C] 24.1-33.6'),
    'feet.phalanges': ('[P]', 'avian anatomy: hallux 2, II 3, III 4, IV 5'),
    'feet.claw_arc': ('[E]', 'c003: 120-150 deg'),
    'body.trunk_len': ('[E]', 'plan §4.5: the coracoid head to the pelvis tail; gate D1.3 vs c040 / c029'),
    'body.trunk_w': ('[E]', 'plan §4.5 (with plumage), c040, c043'),
    'body.trunk_h': ('[E]', 'plan §4.5 (with plumage)'),
    'body.neck_joints': ('[H]', 'plan §7.1: 8 neck joints'),
    'body.neck_vertebrae': ('[E]', '13-14 cervicals in accipitrids (plan §2.2)'),
    'body.mass_g': ('[C]', 'female mean 1,040.7 g (Hull et al. 2008, via Wikipedia)'),
    'rest.perch_axis': ('[E]', 'the relaxed adult perch, plan §2.7; gate D1.3 silhouette vs c029 / c022'),
    'rest.c022_axis': ('[M-pl]', 'c022 juvenile alert perch (landmarks.json c022.body_axis_deg_from_horizontal)'),
    'rest.primary_tip_share': ('[M-pl]', 'c022 (c022.primary_tip_share_of_nape_to_tailtip)'),
    'rest.tail_below_perch': ('[M-pl]', 'c022 (c022.tail_below_perch_over_nape_to_perch)'),
    'texture.px_per_m': ('[H]', 'the lead 11-07: one density on every set (plan §4.7\'s 6,000 px/m)'),
    'texture.BODY': ('[H]', 'plan §4.7'),
    'texture.FLIGHT': ('[H]', 'plan §4.7'),
    'texture.HEAD': ('[H]', 'the lead 11-07: HEAD its own 1024 set at the one density (plan §4.7 fallback)'),
    'texture.COAT': ('[H]', 'plan §4.7, F10\'s shared page'),
    'texture.EYE': ('[H]', 'plan §4.7'),
}
for _k in SPEC['bones']:
    TAGS.setdefault(f'bones.{_k}', _S1)
for _k in SPEC['bone_width']:
    TAGS[f'bone_width.{_k}'] = _S1W
for _k in SPEC['rings']:
    TAGS[f'rings.{_k}'] = ('[H]', 'plan §8.1, CROSSBREED §2 (K = 0 mod 4)')

TAG_RE = re.compile(r'\[(P|C|R|H|D|E|S|M)(?:-(?:pl|d0))?(?: from [^\]]+)?\]')
MAKER_RE = re.compile(r'\[(M|D)(-(?:pl|d0))?[ \]]')

UNIT_GROUP = dict(family='text', head_archetype='text', author_scale='1', bones='mm', bone_width='mm', wing='mm',
                  tail='mm', head='mm', feet='mm', body='mm', rest='deg', texture='px', rings='count')
UNIT_KEY = {'wing.area_one_cm2': 'cm2', 'wing.n_primary': 'count', 'wing.n_secondary': 'count',
            'wing.n_tertial': 'count', 'wing.n_alula': 'count', 'wing.emarginated_first': 'index',
            'wing.longest_primary': 'index', 'wing.slotted_tips': 'count', 'tail.spread_glide': 'deg',
            'tail.spread_land': 'deg', 'tail.n_rectrix': 'count', 'head.pupil_ratio': 'frac', 'feet.phalanges': 'count',
            'feet.claw_arc': 'deg', 'body.neck_joints': 'count', 'body.neck_vertebrae': 'count', 'body.mass_g': 'g',
            'rest.primary_tip_share': 'frac', 'rest.tail_below_perch': 'frac', 'texture.px_per_m': 'px/m'}

# sources: plan_numbers.json paths, landmarks.json results, outlines.json (d1_00_spec.py checks each)
PLAN_JSON = {f'bones.{k}': f'bones_usnm553822.{k}.length_mm' for k in SPEC['bones'] if k != 'digit2'}
PLAN_JSON.update({f'bone_width.{k}': f'bones_usnm553822.{k}.width_mm' for k in SPEC['bone_width']})
PLAN_JSON.update({'bones.digit2': 'wing_skeleton_mm.digitII_E', 'tail.fan_glide': 'c049_scaled_by_span.tail_fan_mm',
                  'body.mass_g': 'lit_C.mass_female_g'})
LM_JSON = {'head.culmen': 'c018.culmen_from_cere_mm_E', 'head.cere': 'c018.cere_length_mm_E',
           'head.gape': 'c018.gape_mm_E', 'head.hook_drop': 'c018.hook_drop_below_tomium_mm_E',
           'head.hook_overhang': 'c018.upper_past_lower_mm_E', 'head.iris': 'c018.iris_d_mm_E',
           'head.pupil_ratio': 'c018.pupil_over_iris', 'tail.spread_glide': 'c049.tail_spread_deg',
           'wing.slotted_tips': 'c049.slotted_tips_left', 'rest.c022_axis': 'c022.body_axis_deg_from_horizontal',
           'rest.primary_tip_share': 'c022.primary_tip_share_of_nape_to_tailtip',
           'rest.tail_below_perch': 'c022.tail_below_perch_over_nape_to_perch'}
OUTLINE_JSON = {'wing.semispan': 'mean_both.L_mm', 'wing.semispan_dorsal': 'mean_dorsal.L_mm',
                'wing.semispan_ventral': 'mean_ventral.L_mm'}


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
    tags = TAGS if tags is None else tags
    keys = [k for k, _ in leaves(spec)]
    missing = [k for k in keys if k not in tags or not TAG_RE.search(tags[k][0])]
    stale = sorted(set(tags) - set(keys))
    return missing, stale


def makerless(tags=None):
    tags = TAGS if tags is None else tags
    return sorted(k for k, (t, _) in tags.items() for m in MAKER_RE.finditer(t + ' ') if not m.group(2))


def unit(key):
    return UNIT_KEY.get(key, UNIT_GROUP[key.split('.')[0]])


def get(spec, key):
    v = spec
    for k in key.split('.'):
        v = v[k]
    return v


# ---- morphs (plan §2.8): only the size morphs change geometry here; plumage morphs are E2 pattern fields
MORPHS = dict(female=1.0, male=0.93)


def morph(name):
    """a SPEC copy at the morph's linear scale (S1 IS the female: the male is 0.93x, mass ratio 1.24 cube-rooted)"""
    s = MORPHS[name]
    sp = copy.deepcopy(SPEC)
    for k, v in leaves(sp):
        if unit(k) == 'mm':
            g, leaf = k.split('.')
            sp[g][leaf] = tuple(x * s for x in v) if isinstance(v, tuple) else v * s
    sp['body']['mass_g'] = SPEC['body']['mass_g'] * s ** 3
    return sp
