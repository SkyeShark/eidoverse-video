"""CYBORG, the forge side (work/bestiary/research/CYBORG_PLAN.md §4.2, §5, §8 C1; its addendum A.2, A.5, A.8; the lead's
A.9 decisions, PLAN.md 10-21): the reserved material-id range and its rows, the anatomical CHARTS, the PANEL LAYOUT in
R and texel units, and the MOUNT PLATES. Everything is planned on the creature's own surface coordinates; the voxel
PLATE op (C2), the material pass's cyborg_texel (C3) and the parts (C4-C6, C10) read it.

SKYE'S STANDING RULE (said twice): cyborg parts MATCH THE BODY SLOT ("a robot arm for a head? an antenna probe for a
hand?? doesn't make sense"). The surface layer keeps it by REGION: a surface row names one of its base's plate regions
(remix/slots.py PLATE_REGIONS), each tied to its chart, its texture set and the low's own region ids, and a mount plate
exists only under a part whose family requires one (slots.FAMILIES: the back mount, on a real back; the octopus has
none). Plates go on UNIQUE texels: a STACKED set (the octopus's arms set, all eight arms on one arm's texels) takes
plates on every arm or none (arms='all', else cyborg.stacked), and nothing is clipped silently: a region that leaves
its texels is refused.

THE IDS (§4.2.5, §5.1; A.5.1; the lead's A.9 decisions 1-3): growth.py stays the owner of the ONE id space (PLAN.md:
399-400). Growth families take 1-63; this family takes 64-95, its names here (never appended to growth.FAMILIES, where
remix/elements.py would read them as growth families):
   64 cyb_titanium      bare or bead-blasted plate (paint wears to it)
   65 cyb_paint         the painted plate, the recipe's colour (the primary tint region)
   66 cyb_steel         fasteners (black oxide by default: metal 0, a dielectric film)
   67 cyb_gasket        the rubber bead seated in the junction's crease
   68 cyb_scar          the skin re-shaded over the junction's ramp: paler, glossier, no tile field
   69 cyb_glow          emissive inlay strips in the seams (glazed by default)
   70 cyb_paint_accent  the SECOND tint region (A.9 decision 3: recolour goes through the ids, no second pack)
THE TWO RANGE GATES are staged patches on shared files (work/bestiary/patches/cyborg_c1_ranges.md): growth.unpack_ids
reads an id past 63 as skin (live it reads a plate as growth family 64-70: a zero row, the black crystal) and the bake's
growth-occlusion test drops growth ids only (live it drops a plate texel standing over 1.5 mm). require_gates() refuses
plates on a forge without them; unpack() below is the material pass's twin for 64-95.

THE ROWS (cyborg_table(), in growth.family_table()'s row layout, growth.ROW: 40 floats now, 42 once halo v2 lands; the
material pass indexes one table, full_table()): A.5.1's numbers with the lead's decisions. CYBORG_ROWS keeps every
range and its source; a row's rough is the range's middle and rough_facet its half width (each plate draws inside it).

CHARTS (§4.2.2): a centreline (the octopus's body loft axis, forge/species/octopus.body_axis; an arm's centreline,
octopus.arm_centreline) with its frames (n: theta 0, the dorsal or aboral side; b = t x n), its share s, and the
surface's radius r(s, theta) TABLED BY RAYS from the centreline against the canonical low (work/bestiary/octopus/
low.npz), each ray's first hit with its face and region. u = s L (the centreline's arc length); w = the SURFACE arc
length round the section from theta 0 (+ toward b). to_uw / from_uw round-trip on the low within the gate (0.1 mm).

THE PANEL LAYOUT (§4.2.3; A.2.1, A.2.2, A.8): a region of a chart (an s range, |theta| <= theta_max, its low regions
only), plates in rows along u, staggered seams in a brick bond (a seam of constant v = w / w_half(u) is a meridian
converging with the taper, a ring seam a contour of constant u; on an arm the ring seams also fall at its joints:
"plates follow segments"). Sizes in R units: a plate's equal-area diameter over the local radius (plate_R, default the
plan's 0.45-0.70: 13 plates on the mantle; study G's median 0.91 the large look). Seams and fasteners in TEXELS of the
low's own UV map, measured where they lie (the octopus mantle's local density runs 2,948-3,393 px/m against the head
set's 3,164 mean, so a seam sized from the mean would fall under 3 texels there) AS THE BAKE READS THEM: the plate stands
plate_t (+ the block-out's lift) over the low and the bake maps it back along the low's normals, so on a convex low a
width up there covers 1 / (1 + h k) of the texels it would on the low (the C1 check: unscaled, the arm's seams baked
2.73 texels and its heads 9.1). seam_tx 3 (4 'chunky'), the width the widest the local densities need, at least 3
voxels; depth 0.5 x the width (a round tube on the plate's surface); fasteners 10 texels, 'ends' (2-4 heads per plate at
its fastened ends, a group pitch of 1.8-3.5 D, 2 D from every edge's LIP, the plate's own edge; a plate that cannot hold
its least heads refuses the layout; 'riveted' the plan's corners and edges at 3.4 D), each 0.5 mm clear of every seam
(SCREW_LAND).

MOUNT PLATES (§4.2.3, K11; A.6 the socket's port): a round plate under a mount, from its SOCKET'S FRAME (C0b's slot
frame: Z the outward normal, X the tangent) and dims (radius, bolt circle, bolts, pilot): centred where the socket's
radial line meets the surface, its rim the mount's radius plus a 2 D land, its heads clocked from the frame's tangent.
Never from a bounding box (N5).

FEED LINES (C3b, C3c, C3d; A.2.2, the lead's A.9 decision 6; the section "C3b: the FEED LINES" below): a surface row of
kind 'feed' over a plated region lays cables, LINKS between two of its plates (each seam crossed under a clamp) and DIVES
from a plate into the skin through a SOCKET; both ends land on a plate or a mount, never free. feed_layout routes them
on the chart. The cables, their collars and clamps are GEOMETRY (C3d: forge/cyborg_feed.py builds them as C5d's cable
data, re-made by the runtime on the rendered skin), so the high keeps none of them: surface_plan carries their shapes as
the bake's AO occluders and the sockets' soft-tissue collars (feed_plan), apply_surface sculpts the sockets
(apply_feed), t10 folds the occluders into the AO / cavity rays (feed_occluders) and the material pass paints the
sockets' scar bands (feed_texel).

Read with numpy, scipy and warp (the ray and closest-point queries run on warp's default device: the CPU when CUDA is
hidden, as every C1 test runs).
"""
import math

import numpy as np
import warp as wp

from . import growth as GR

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile


class CyborgError(ValueError):
    """a cyborg surface request the forge refuses; .code names the rule (cyborg.stacked, cyborg.region, ...)"""

    def __init__(self, code, message):
        self.code = code
        super().__init__(f'{code}: {message}')


# ============================================================================================ the ids
GROWTH_RANGE = (1, 63)
CYBORG_RANGE = (64, 95)
CYBORG_NAMES = ('cyb_titanium', 'cyb_paint', 'cyb_steel', 'cyb_gasket', 'cyb_scar', 'cyb_glow', 'cyb_paint_accent')
CYBORG_ID = {n: CYBORG_RANGE[0] + i for i, n in enumerate(CYBORG_NAMES)}     # ids never move once written
assert max(CYBORG_ID.values()) <= CYBORG_RANGE[1] and len(set(CYBORG_ID.values())) == len(CYBORG_ID)
assert max(GR.FAMILY_ID.values()) <= GROWTH_RANGE[1], 'growth families must stay inside 1-63 (64-95 are cyborg ids)'
assert not set(CYBORG_ID) & set(GR.FAMILY_ID), 'a cyborg name is a growth family'
assert (GR.MAT_SKIN, GR.MAT_KEEP, GR.N_IDS) == (0, 255, 256)
if hasattr(GR, 'ID_RANGES'):                          # the growth patch landed: the two must agree
    assert {k: tuple(v) for k, v in GR.ID_RANGES.items()} == dict(growth=GROWTH_RANGE, cyborg=CYBORG_RANGE), \
        GR.ID_RANGES


def gates_landed():
    """(landed, what is missing): the live forge carries the two range gates (cyborg_c1_ranges.md)"""
    from . import bake as BK
    miss = []
    if not hasattr(GR, 'ID_RANGES') or getattr(GR, 'GROWTH_ID_MAX', None) != GROWTH_RANGE[1]:
        miss.append('forge/growth.py: ID_RANGES and unpack_ids\'s range gate (a plate reads as growth family 64-70)')
    if getattr(BK, 'GROWTH_ID_MAX', None) != GROWTH_RANGE[1]:
        miss.append('forge/bake.py: the growth-occlusion test gated to 1-63 (a plate over 1.5 mm is dropped)')
    return not miss, miss


def require_gates():
    """refuse to plan or bake plates on a forge without the two range gates (a plate would bake black or vanish)"""
    ok, miss = gates_landed()
    if not ok:
        raise CyborgError('cyborg.gates', 'land work/bestiary/patches/cyborg_c1_ranges.md first: ' + '; '.join(miss))


@wp.func
def unpack(code: int):
    """the bake's packed ids (voxel.lab_pack: id0 | id1 << 8 | round(255 w0 / (w0 + w1)) << 16) -> the CYBORG ids
    among them and their shares, vec4(id_a, share_a, id_b, share_b): the twin of growth.unpack_ids for 64-95 (0, 0
    where none). Two cyborg ids keep both (a paint / fastener rim: the material pass blends them, A.7 U10); a cyborg id
    beside the skin or a growth keeps its own weight, so the growth, cyborg and skin shares sum to 1"""
    id0 = code & 255
    id1 = (code >> 8) & 255
    w0 = float((code >> 16) & 255) / 255.0
    c0 = int(0)
    if id0 >= 64:
        if id0 <= 95:
            c0 = 1
    c1 = int(0)
    if id1 >= 64:
        if id1 <= 95:
            c1 = 1
    out = wp.vec4(0.0, 0.0, 0.0, 0.0)
    if c0 == 1:
        out = wp.vec4(float(id0), w0, 0.0, 0.0)
        if c1 == 1:
            out = wp.vec4(float(id0), w0, float(id1), 1.0 - w0)
    elif c1 == 1:
        out = wp.vec4(float(id1), 1.0 - w0, 0.0, 0.0)
    return out


def unpack_np(code):
    """unpack()'s numpy twin (float32 shares, as the GPU computes them): (n, 4) id_a, share_a, id_b, share_b"""
    code = np.asarray(code, np.int64)
    id0, id1 = code & 255, (code >> 8) & 255
    w0 = ((code >> 16) & 255).astype(np.float32) / np.float32(255.0)
    c0 = (id0 >= CYBORG_RANGE[0]) & (id0 <= CYBORG_RANGE[1])
    c1 = (id1 >= CYBORG_RANGE[0]) & (id1 <= CYBORG_RANGE[1])
    one = np.float32(1.0)
    out = np.zeros(code.shape + (4,), np.float32)
    out[..., 0] = np.where(c0, id0, np.where(c1, id1, 0))
    out[..., 1] = np.where(c0, w0, np.where(c1, one - w0, 0.0))
    out[..., 2] = np.where(c0 & c1, id1, 0)
    out[..., 3] = np.where(c0 & c1, one - w0, 0.0)
    return out


def growth_unpack_np(code, gated=True):
    """growth.unpack_ids's numpy twin, with the C1 range gate (gated) or as it is live (gated=False): (n, 2) family,
    share (float32)"""
    code = np.asarray(code, np.int64)
    id0, id1 = code & 255, (code >> 8) & 255
    w0 = ((code >> 16) & 255).astype(np.float32) / np.float32(255.0)
    if gated:
        id0 = np.where(id0 > GROWTH_RANGE[1], 0, id0)
        id1 = np.where(id1 > GROWTH_RANGE[1], 0, id1)
    fam = np.where(id0 == 0, id1, id0)
    f = np.where(id0 == 0, np.float32(1.0) - w0, np.where(id1 != 0, np.float32(1.0), w0))
    none = (fam == 0) | (fam >= 255)
    return np.stack([np.where(none, 0, fam).astype(np.float32), np.where(none, np.float32(0.0), f)], -1)


# ============================================================================================ the rows
def srgb_hex(h):
    """'#rrggbb' -> linear RGB (growth.srgb8's exact transfer)"""
    h = str(h).lstrip('#')
    if len(h) != 6:
        raise CyborgError('cyborg.surface', f'a colour is #rrggbb, not {h!r}')
    return GR.srgb8(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# the paint's roughness by type (A.5.1 row 65; the lead's A.9 call on the check: white at the house's 0.36-0.46, the
# MERL white 0.198 sat below every measured paint): white = the body's ceramic paint 0.357-0.384 and the kit's paint
# 0.431-0.463 [R-kb]; metallic and colour paints the MERL fits 0.45-0.51 and 0.56-0.62 [D-rf from P], which study R's
# dielectrics (0.58-0.74 [R-tt]) bracket
PAINT_TYPES = dict(white=(0.36, 0.46), metallic=(0.45, 0.51), colour=(0.56, 0.62))
# the house's white: the robot body's ceramic paint, sRGB (232, 228, 220) at 0.36 [H via kb]
HOUSE_WHITE = '#e8e4dc'
# the accent's default: the kit's dark machined tier, sRGB (88, 92, 94) [R-kb] (a second tint region, A.9 decision 3)
ACCENT_DEFAULT = '#585c5e'
# the cyborg glow: cyan-blue the common machine glow, orange the second (study G [R-rf]; A.5.3: the references agree)
GLOW_COLOURS = dict(cyan=(0.0, 0.5, 1.0), orange=(1.0, 0.35, 0.0))
FINISH_OPTIONS = dict(fastener=('black_oxide', 'bare'), glow=('glazed', 'bare'), paint=tuple(PAINT_TYPES))

# every id's row as numbers with their ranges and sources (CYBORG_PLAN §5.1, A.5.1; tags as the plan's): base = linear
# RGB, rough = (lo, hi), metal, ior (0: a metal, its F0 is the base; else a dielectric's n: 1.5 gives F0 0.040, the
# skin's 1.33 gives 0.020), worn = the layer wear exposes (its base, rough, metal)
CYBORG_ROWS = {
    'cyb_titanium': dict(
        role='bare or bead-blasted plate; the layer paint wears to',
        base=(0.441, 0.400, 0.361), rough=(0.30, 0.45), metal=1.0, ior=0.0, jit_L=0.02,
        src='base physicallybased.info Titanium [C] (F0 from n, k (0.451, 0.399, 0.336) [D-rf]); rough 0.30-0.45 [E-fo] '
            'matches every clean metal measured, the kit 0.29 / 0.345, the body 0.341-0.384, study R 0.32-0.45 '
            '[R-kb, R-tt]; no titanium was measured: C3\'s look'),
    'cyb_paint': dict(
        role='the painted plate: the recipe\'s colour (the primary tint region)',
        base='paint', rough='paint_type', metal=0.0, ior=1.5, jit_L=0.03,
        worn=dict(base=(0.441, 0.400, 0.361), rough=0.375, metal=1.0),
        src='paint F0 0.040 [C] (ior 1.5); rough by PAINT_TYPES (white 0.36-0.46: the lead, A.9); wears to titanium '
            '(§5.2)'),
    'cyb_steel': dict(
        role='fasteners',
        finishes=dict(
            black_oxide=dict(base=(0.021, 0.021, 0.023), rough=(0.40, 0.53), metal=0.0, ior=1.5,
                             worn=dict(base=(0.530, 0.513, 0.494), rough=0.098, metal=1.0)),
            bare=dict(base=(0.530, 0.513, 0.494), rough=(0.098, 0.098), metal=1.0, ior=0.0)),
        finish='black_oxide', jit_L=0.02,
        src='black oxide = the body\'s blackoxide: sRGB (40, 40, 42) = linear (0.021, 0.021, 0.023), roughness p50 '
            '0.404-0.486 [R-kb], MERL 0.534 [D-rf from P]; METAL 0 (the lead, A.9 decision 1: a dielectric film; at '
            'metal 1 that base is F0 0.02, a dark hole); bare = iron (0.530, 0.513, 0.494) [C] at MERL steel 0.098'),
    'cyb_gasket': dict(
        role='the rubber bead seated in the junction\'s crease',
        base=(0.023, 0.023, 0.023), rough=(0.69, 0.77), metal=0.0, ior=1.5, jit_L=0.0,
        src='tyre rubber albedo 0.023 [C] (the body\'s rubber 0.025-0.027 agrees [R-kb]); roughness the house\'s '
            '0.69-0.77 (the lead, A.9 decision 2: the body\'s rubber p50 0.757-0.773, the kit\'s elastomer 0.678-0.694 '
            '[R-kb]; MERL\'s 0.45-0.54 are clean lab samples)'),
    'cyb_scar': dict(
        role='the skin re-shaded over the junction\'s ramp: paler, glossier, no tile field (a tint on the skin)',
        base=(1.55, 1.42, 1.36), rough=(0.08, 0.08), metal=0.0, ior=1.33, sss=0.95, flesh=1.0, jit_L=0.0,
        src='rough 0.08: study T\'s flesh beside machine 0.08-0.17, a character\'s organs p50 0.08 [R-tt], under the octopus\'s '
            'wet skin as shipped (0.12-0.18, its floor 0.12); the tint lifts the skin colour desaturated to 0.45 of its '
            'chroma (SCAR_KEEP) into a pale pink-cream (flesh = 1, as growth.py\'s flesh). The lead\'s C3b call: the band '
            'made to read, its albedo and roughness apart from the wet skin\'s (the C3 check: at 0.12 and x1.10 it sat '
            'inside the skin\'s range and read 0.96 of its luminance); sss and ior the skin\'s (flesh)'),
    'cyb_glow': dict(
        role='emissive inlay strips in the seams',
        finishes=dict(glazed=dict(base=(0.005, 0.005, 0.005), rough=(0.03, 0.15), metal=0.0, ior=1.5),
                      bare=dict(base=(0.03, 0.03, 0.03), rough=(0.30, 0.30), metal=0.0, ior=1.5)),
        finish='glazed', emis=1.0, glow=GLOW_COLOURS['cyan'], jit_L=0.0,
        src='glazed = the kit\'s display glass linear 0.0054 at 0.145-0.149, the body\'s glass 0.005 at 0.03 [R-kb, H via '
            'kb] (the lead: base 0.005, rough 0.03-0.15); bare = the plan\'s 0.03 at 0.3 [E-fo]; cyan-blue (0, 0.5, 1) '
            'by default, orange the second [R-rf]'),
    'cyb_paint_accent': dict(
        role='the accent paint: the second tint region (A.9 decision 3)',
        base='accent', rough='paint_type', metal=0.0, ior=1.5, jit_L=0.03,
        worn=dict(base=(0.441, 0.400, 0.361), rough=0.375, metal=1.0),
        src='as cyb_paint, in the accent colour (the runtime colours each id from the palette)'),
}
assert set(CYBORG_ROWS) == set(CYBORG_NAMES)


def row_values(name, paint=HOUSE_WHITE, accent=ACCENT_DEFAULT, paint_type='white', fastener_finish='black_oxide',
               glow_finish='glazed'):
    """one id's row as {ROW column: value} (growth.ROW's names; every column present, the look terms neutral)"""
    if paint_type not in PAINT_TYPES:
        raise CyborgError('cyborg.surface', f'paint_type {paint_type!r} not in {tuple(PAINT_TYPES)}')
    d = dict(CYBORG_ROWS[name])
    if 'finishes' in d:
        fin = fastener_finish if name == 'cyb_steel' else glow_finish
        if fin not in d['finishes']:
            raise CyborgError('cyborg.surface', f'{name} has no finish {fin!r} (have {tuple(d["finishes"])})')
        d.update(d['finishes'][fin])
    base = d['base']
    if base == 'paint':
        base = srgb_hex(paint)
    elif base == 'accent':
        base = srgb_hex(accent)
    rough = PAINT_TYPES[paint_type] if d['rough'] == 'paint_type' else d['rough']
    worn = d.get('worn') or dict(base=base, rough=0.5 * (rough[0] + rough[1]), metal=d['metal'])
    v = {k: 0.0 for k in GR.ROW}
    v.update(dict(GR.LOOK_DEFAULTS))
    v.update(c0r=base[0], c0g=base[1], c0b=base[2], c1r=worn['base'][0], c1g=worn['base'][1], c1b=worn['base'][2],
             rough=0.5 * (rough[0] + rough[1]), rough_facet=0.5 * (rough[1] - rough[0]), rough1=worn['rough'],
             metal=d['metal'], metal1=worn['metal'], sss=d.get('sss', 0.0), ior=d['ior'], irid_lo=100.0, irid_hi=400.0,
             emis=d.get('emis', 0.0), jit_L=d.get('jit_L', 0.0), smooth=1.0, flesh=d.get('flesh', 0.0))
    return {k: float(v[k]) for k in GR.ROW}


def cyborg_table(**finish):
    """(growth.N_IDS * NP,) float32 in growth.family_table()'s layout: the cyborg rows at ids 64-70, every other row 0.
    finish: row_values()'s paint, accent, paint_type, fastener_finish, glow_finish"""
    T = np.zeros((GR.N_IDS, GR.NP), np.float32)
    for name, i in CYBORG_ID.items():
        vals = row_values(name, **finish)
        T[i] = np.asarray([vals[k] for k in GR.ROW], np.float32)
    return T.reshape(-1)


def full_table(**finish):
    """the ONE table the material pass and the runtime index: growth.family_table() with the cyborg rows written into
    its unused ids 64-70 (refused if growth ever used them)"""
    G = GR.family_table().reshape(GR.N_IDS, GR.NP).copy()
    C = cyborg_table(**finish).reshape(GR.N_IDS, GR.NP)
    ids = list(CYBORG_ID.values())
    assert not np.any(G[ids]), 'growth.family_table() holds rows at the cyborg ids'
    G[ids] = C[ids]
    return G.reshape(-1)


# ============================================================================================ warp queries
@wp.kernel
def k_rays(mesh: wp.uint64, org: wp.array(dtype=wp.vec3), dirs: wp.array(dtype=wp.vec3), tmax: wp.array(dtype=float),
           out_t: wp.array(dtype=float), out_f: wp.array(dtype=wp.int32)):
    i = wp.tid()
    q = wp.mesh_query_ray(mesh, org[i], dirs[i], tmax[i])
    if q.result:
        out_t[i] = q.t
        out_f[i] = q.face
    else:
        out_t[i] = -1.0
        out_f[i] = -1


@wp.kernel
def k_closest(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, face: wp.array(dtype=wp.int32),
              bary: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    q = wp.mesh_query_point_no_sign(mesh, pts[i], maxd)
    if q.result:
        face[i] = q.face
        bary[i] = wp.vec3(q.u, q.v, 1.0 - q.u - q.v)
    else:
        face[i] = -1
        bary[i] = wp.vec3(0.0, 0.0, 0.0)


@wp.kernel
def k_uv_point(uv_mesh: wp.uint64, xs: wp.array(dtype=float), ys: wp.array(dtype=float), lpos: wp.array(dtype=wp.vec3),
               out: wp.array(dtype=wp.vec4), face: wp.array(dtype=wp.int32)):
    """the low's point under a texel-space point (x, y = u, v times the set's size), as material.low_at finds it"""
    i = wp.tid()
    q = wp.mesh_query_ray(uv_mesh, wp.vec3(xs[i], ys[i], 1.0), wp.vec3(0.0, 0.0, -1.0), 2.0)
    if q.result:
        c0 = 3 * q.face
        p = lpos[c0] * q.u + lpos[c0 + 1] * q.v + lpos[c0 + 2] * (1.0 - q.u - q.v)
        out[i] = wp.vec4(p[0], p[1], p[2], 1.0)
        face[i] = q.face
    else:
        out[i] = wp.vec4(0.0, 0.0, 0.0, 0.0)
        face[i] = -1


def _mesh(V, F, device=None):
    return wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=device),
                   indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=device))


def load_low(path):
    """the canonical low (t10's low.npz): V, F, UV, N, TAN, region, face_set, order"""
    L = dict(np.load(path, allow_pickle=True))
    L['face_set'] = np.asarray(L['face_set']).astype(str)
    return L


# ============================================================================================ texel density
SET_SIZES = dict(head=4096, arms=1280)       # t10's sets (the arms set 0.3125 of the head's, rounded to 64)


class UVDensity:
    """the low's UV map as texels per metre where a point lies: each triangle's Jacobian d(uv x its set's size)/d(x) in
    its plane; the closest point of the low (warp) gives a point's triangle, barycentrics and texel coordinates"""

    def __init__(self, low, sizes=None, device=None):
        sizes = dict(SET_SIZES, **(sizes or {}))
        self.V = np.asarray(low['V'], np.float64)
        self.F = np.asarray(low['F'], np.int64)
        self.UV = np.asarray(low['UV'], np.float64)
        self.region = np.asarray(low['region'], np.int64)
        self.face_set = np.asarray(low['face_set']).astype(str)
        self.size_f = np.array([sizes[s] for s in self.face_set], np.float64)
        A, B, C = (self.V[self.F[:, k]] for k in range(3))
        a, b, c = (self.UV[self.F[:, k]] * self.size_f[:, None] for k in range(3))
        M3 = np.stack([B - A, C - A], 2)                                     # (m, 3, 2)
        M2 = np.stack([b - a, c - a], 2)                                     # (m, 2, 2) px
        G = np.einsum('mki,mkj->mij', M3, M3)                                # (m, 2, 2)
        self.J = np.einsum('mij,mjk,mlk->mil', M2, np.linalg.inv(G), M3)     # (m, 2, 3): px per metre in the plane
        sv = np.linalg.svd(self.J, compute_uv=False)
        self.px_iso_f = np.sqrt(sv[:, 0] * sv[:, 1])
        self.aniso_f = sv[:, 0] / np.maximum(sv[:, 1], 1e-12)
        # the low's smooth vertex normals: the bake's rays leave the low along them (forge/bake.py), so they decide how
        # a feature raised off the low maps back onto its texels (curvature below)
        self.N = np.asarray(low['N'], np.float64) if 'N' in low else None
        self.device = device
        self._mesh = _mesh(self.V, self.F, device)

    def locate(self, pts, maxd=0.05):
        """closest point on the low: (faces, barycentrics (n, 3) over the face's corners 0, 1, 2, the points)"""
        pts = np.atleast_2d(np.asarray(pts, np.float64))
        n = len(pts)
        f = wp.zeros(n, dtype=wp.int32, device=self.device)
        bc = wp.zeros(n, dtype=wp.vec3, device=self.device)
        wp.launch(k_closest, dim=n, inputs=[self._mesh.id, wp.array(pts.astype(np.float32), dtype=wp.vec3,
                                                                     device=self.device), float(maxd), f, bc],
                  device=self.device)
        f, bc = f.numpy().astype(np.int64), bc.numpy().astype(np.float64)
        if np.any(f < 0):
            raise CyborgError('cyborg.chart', f'{int((f < 0).sum())} points lie farther than {maxd} m from the low')
        q = np.einsum('nk,nkd->nd', bc, self.V[self.F[f]])
        return f, bc, q

    def texel(self, pts):
        """texel coordinates (px, x = u size, y = v size) of the low's closest point, and its set's size"""
        f, bc, _ = self.locate(pts)
        uv = np.einsum('nk,nkd->nd', bc, self.UV[self.F[f]])
        return uv * self.size_f[f][:, None], self.size_f[f], f

    def px_along(self, pts, dirs):
        """texels per metre along each direction (projected into the triangle's plane)"""
        f, _, _ = self.locate(pts)
        d = np.atleast_2d(np.asarray(dirs, np.float64))
        return np.linalg.norm(np.einsum('nij,nj->ni', self.J[f], d), axis=1)

    def px_iso(self, pts):
        """the isotropic texel density (texels per metre: the square root of the area scale)"""
        f, _, _ = self.locate(pts)
        return self.px_iso_f[f]

    def normal(self, pts):
        """the low's smooth (interpolated vertex) normal at each point's closest point: the bake's ray direction"""
        if self.N is None:
            raise CyborgError('cyborg.chart', 'the low carries no vertex normals (N): the bake\'s rays are unknown')
        f, bc, _ = self.locate(pts)
        n = np.einsum('nk,nkd->nd', bc, self.N[self.F[f]])
        return n / np.linalg.norm(n, axis=1, keepdims=True)

    def curvature(self, pts, dirs, eps=1.5e-3):
        """the low's normal curvature (1/m, + convex) along each tangent direction, from its smooth normals 2 eps apart.
        The bake reads a surface raised h off the low through those normals, so a width there covers 1 / (1 + h k) of
        its texels here (the rays spread over a convex low): what panel_layout sizes seams and heads against"""
        pts = np.atleast_2d(np.asarray(pts, np.float64))
        d = np.atleast_2d(np.asarray(dirs, np.float64))
        d = d / np.linalg.norm(d, axis=1, keepdims=True)
        return np.einsum('nd,nd->n', self.normal(pts + eps * d) - self.normal(pts - eps * d), d) / (2.0 * eps)

    def head_texels(self, pts, normals, D):
        """what a round head of diameter D standing at each point reads ON THE LOW, in texels: its rim (32 points in the
        plane square to the normal) mapped through the UV map, the polygon's equal-area diameter (where the rim crosses
        into another UV island, the centre triangle's Jacobian instead, as the bake cannot join islands). Divided by
        the bake's growth (1 + h H) it is the head as baked: what the one physical head size is solved against"""
        pts = np.atleast_2d(np.asarray(pts, np.float64))
        Nn = np.atleast_2d(np.asarray(normals, np.float64))
        if getattr(self, '_isl', None) is None:
            from . import bake as BK
            self._isl = np.asarray(BK.islands(self.F, self.UV))
        t1 = np.cross(Nn, [0.0, 0.0, 1.0])
        t1[np.linalg.norm(t1, axis=1) < 1e-6] = [1.0, 0.0, 0.0]
        t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
        t2 = np.cross(Nn, t1)
        phi = np.linspace(0.0, 2.0 * np.pi, 33)[:-1]
        Dv = np.broadcast_to(np.asarray(D, np.float64), (len(pts),))
        rim = pts[:, None] + 0.5 * Dv[:, None, None] * (np.cos(phi)[None, :, None] * t1[:, None] +
                                                         np.sin(phi)[None, :, None] * t2[:, None])
        tx, _, fr = self.texel(rim.reshape(-1, 3))
        tx = tx.reshape(len(pts), len(phi), 2)
        _, _, fc = self.texel(pts)
        cross = (self._isl[fr].reshape(len(pts), len(phi)) != self._isl[fc][:, None]).any(1)
        x, y = tx[..., 0], tx[..., 1]
        deq = 2.0 * np.sqrt(0.5 * np.abs((x * np.roll(y, -1, 1) - np.roll(x, -1, 1) * y).sum(1)) / np.pi)
        rimJ = np.einsum('nij,nkj->nki', self.J[fc], rim - pts[:, None])
        aJ = 0.5 * np.abs((rimJ[..., 0] * np.roll(rimJ[..., 1], -1, 1) - np.roll(rimJ[..., 0], -1, 1) *
                           rimJ[..., 1]).sum(1))
        return np.where(cross, 2.0 * np.sqrt(aJ / np.pi), deq), cross

    def mean_curvature(self, pts):
        """the mean of the normal curvatures along two orthogonal tangents (1/m): a round head's growth"""
        pts = np.atleast_2d(np.asarray(pts, np.float64))
        n = self.normal(pts)
        t1 = np.cross(n, [0.0, 0.0, 1.0])
        flat = np.linalg.norm(t1, axis=1) < 1e-6
        t1[flat] = np.cross(n[flat], [1.0, 0.0, 0.0])
        t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
        t2 = np.cross(n, t1)
        return 0.5 * (self.curvature(pts, t1) + self.curvature(pts, t2))


def blockout_lift(prog, density, maxd=0.01):
    """panel_layout(lift=): the block-out's height over the low along the low's smooth normals (+ outward), a callable
    of points. The PLATE op raises a plate plate_t off the UNSCULPTED block-out (CYBORG_PLAN §4.2.4), so its top stands
    lift + plate_t over the low the bake reads it from. prog: the high's block-out, octopus.build_sdf(SPEC)[0] as t10
    builds it (the C1 check: +0.01-0.06 mm on the mantle, -0.67 to +0.58 mm on the crown top's strip)"""
    def lift(pts):
        pts = np.atleast_2d(np.asarray(pts, np.float64))
        n = density.normal(pts)
        q = density.locate(pts)[2]
        proj, st = prog.project(q, n, maxd=maxd)
        if np.any(st >= 2):
            raise CyborgError('cyborg.chart', f'{int((st >= 2).sum())} points met no block-out along the low\'s normal '
                                              f'within {maxd} m')
        return np.einsum('nd,nd->n', np.asarray(proj, np.float64) - q, n)
    lift.prog = prog                  # (panel_layout's plate metric reads the block-out through it: plate_top)
    return lift


def plate_top(prog, X, t, density=None):
    """THE PLATE'S TOP over points X of the low (the lead's C3 call 3: the 2 D inset is measured where the heads and the
    lips physically are): the block-out's CLOSEST point F (blockout_foot: a smooth map, so a plate's raster of it
    interpolates to ~0.1 um) raised t along the block-out's normal there, where the PLATE op puts the flat top
    (surface_plan places the outline, the seams and the heads by the same foot). prog None (no block-out given): the
    low itself raised t along its smooth normals"""
    X = np.atleast_2d(np.asarray(X, np.float64))
    if prog is None:
        return X + t * density.normal(X)
    F, z = blockout_foot(prog, X)
    if np.any(np.abs(z) > 0.01):
        raise CyborgError('cyborg.chart', f'{int((np.abs(z) > 0.01).sum())} layout points lie over 10 mm off the '
                                          'block-out')
    return F + t * np.asarray(prog.normals(F, h=FOOT_H), np.float64)


# ============================================================================================ charts
class Chart:
    """an anatomical CHART (§4.2.2). P (n, 3) the centreline, n / b / t its frames (n: theta 0; b = t x n); s its share
    (the arc length's, or the generator's own per node: s_nodes). The surface is tabled by rays from P(s_i) along
    cos(theta_j) n + sin(theta_j) b against a mesh (the canonical low): R[i, j] the first hit's distance (nan: none
    within max_r), FACE / REG its face and region. W[i, j] the arc length round the section from theta 0 (the hit
    polyline's chords, signed), valid only along the contiguous run of hits through theta 0. u = s L, w = W(s, theta).
    from_st / from_uw cast the EXACT ray (the table's bilinear radius rounds the low's vertices by a few um); a surface
    point hidden from the centreline (behind a fold) is no chart point"""

    def __init__(self, name, P, n, b, t, low, s_range=(0.0, 1.0), ns=621, nth=721, max_r=0.12, min_r=0.0005,
                 device=None, meta=None, s_nodes=None):
        self.name = name
        self.P = np.asarray(P, np.float64)
        self.n = np.asarray(n, np.float64)
        self.b = np.asarray(b, np.float64)
        self.t = np.asarray(t, np.float64)
        seg = np.linalg.norm(np.diff(self.P, axis=0), axis=1)
        self.L = float(seg.sum())
        # the nodes' shares: the polyline's arc length (the body axis, as octopus.axis_s and the rig's body joints), or
        # the generator's own (an arm: its rig places joints at linspace shares of its evenly resampled nodes)
        self.sP = (np.concatenate([[0.0], np.cumsum(seg)]) / self.L if s_nodes is None else
                   np.asarray(s_nodes, np.float64))
        self.meta = dict(meta or {})
        # dense samples for the projection's first guess
        from scipy.spatial import cKDTree
        self._sd = np.linspace(0.0, 1.0, max(8001, 8 * len(self.P)))
        self._tree = cKDTree(self.frame_at(self._sd)[0])
        # the table: rays from the centreline in the section planes
        assert nth % 2 == 1, 'nth odd: theta 0 is a grid column'
        self.s_grid = np.linspace(s_range[0], s_range[1], ns)
        self.th_grid = np.linspace(-np.pi, np.pi, nth)
        self.ds = float(self.s_grid[1] - self.s_grid[0])
        self.dth = float(self.th_grid[1] - self.th_grid[0])
        self.j0 = nth // 2
        p0, n0, b0, _ = self.frame_at(self.s_grid)
        D = (np.cos(self.th_grid)[None, :, None] * n0[:, None, :] + np.sin(self.th_grid)[None, :, None] * b0[:, None, :])
        tmax = (np.asarray(max_r(self.s_grid), np.float64) if callable(max_r) else
                np.full(ns, float(max_r)))
        org = np.repeat(p0, nth, axis=0)
        mesh = _mesh(low['V'], low['F'], device)
        self._ray_mesh, self._device, self._max_r, self._min_r = mesh, device, max_r, float(min_r)
        self._region_of_face = np.asarray(low['region'], np.int64)
        m = ns * nth
        out_t = wp.zeros(m, dtype=float, device=device)
        out_f = wp.zeros(m, dtype=wp.int32, device=device)
        wp.launch(k_rays, dim=m, inputs=[mesh.id, wp.array(org.astype(np.float32), dtype=wp.vec3, device=device),
                                         wp.array(D.reshape(-1, 3).astype(np.float32), dtype=wp.vec3, device=device),
                                         wp.array(np.repeat(tmax, nth).astype(np.float32), dtype=float, device=device),
                                         out_t, out_f], device=device)
        R = out_t.numpy().astype(np.float64).reshape(ns, nth)
        FACE = out_f.numpy().astype(np.int64).reshape(ns, nth)
        ok = (FACE >= 0) & (R > min_r)
        self.R = np.where(ok, R, np.nan)
        self.FACE = np.where(ok, FACE, -1)
        reg = np.asarray(low['region'], np.int64)
        self.REG = np.where(ok, reg[np.maximum(FACE, 0)], -1)
        # the arc length round each section from theta 0, along the contiguous run of hits through it
        X = p0[:, None, :] + self.R[..., None] * D
        ch = np.linalg.norm(np.diff(X, axis=1), axis=2)                     # (ns, nth - 1); nan where a cell is out
        W = np.full((ns, nth), np.nan)
        W[:, self.j0] = np.where(ok[:, self.j0], 0.0, np.nan)
        for k in range(self.j0 + 1, nth):
            W[:, k] = W[:, k - 1] + ch[:, k - 1]
        for k in range(self.j0 - 1, -1, -1):
            W[:, k] = W[:, k + 1] - ch[:, k]
        self.W = W
        # for the inverse: invalid cells outside the run as -inf / +inf, so every row is monotone
        Wb = W.copy()
        lo = np.arange(nth)[None, :] < self.j0
        Wb[np.isnan(Wb) & lo] = -np.inf
        Wb[np.isnan(Wb) & ~lo] = np.inf
        self._Wb = Wb

    # ----------------------------------------------------------------------------------------- frames, projection
    def frame_at(self, s):
        """the centreline's point and orthonormal frame (n, b, t) at shares s: linear along the polyline, the frames
        interpolated and re-orthonormalised (n off t, b off t and n: b keeps its side)"""
        s = np.clip(np.atleast_1d(np.asarray(s, np.float64)), 0.0, 1.0)
        i = np.clip(np.searchsorted(self.sP, s, side='right') - 1, 0, len(self.sP) - 2)
        a = ((s - self.sP[i]) / (self.sP[i + 1] - self.sP[i]))[:, None]
        p = self.P[i] + a * (self.P[i + 1] - self.P[i])
        t = self.t[i] + a * (self.t[i + 1] - self.t[i])
        t /= np.linalg.norm(t, axis=1, keepdims=True)
        n = self.n[i] + a * (self.n[i + 1] - self.n[i])
        n -= np.einsum('ij,ij->i', n, t)[:, None] * t
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        b = self.b[i] + a * (self.b[i + 1] - self.b[i])
        b -= np.einsum('ij,ij->i', b, t)[:, None] * t + np.einsum('ij,ij->i', b, n)[:, None] * n
        b /= np.linalg.norm(b, axis=1, keepdims=True)
        return p, n, b, t

    def to_st(self, pts, iters=36):
        """(s, theta, r): the share whose section plane holds each point ((p - P(s)) . t(s) = 0, bisected from the
        nearest dense sample), its angle from n toward b and its distance from the centreline"""
        pts = np.atleast_2d(np.asarray(pts, np.float64))
        _, k = self._tree.query(pts)
        nd = len(self._sd)
        lo = self._sd[np.maximum(k - 3, 0)]
        hi = self._sd[np.minimum(k + 3, nd - 1)]

        def f(s, q):
            p, _, _, t = self.frame_at(s)
            return np.einsum('ij,ij->i', q - p, t)
        flo, fhi = f(lo, pts), f(hi, pts)
        for wide in (12, 48, 200):                    # rare: the foot beyond the first bracket
            bad = np.sign(flo) == np.sign(fhi)
            if not bad.any():
                break
            lo[bad] = self._sd[np.maximum(k[bad] - wide, 0)]
            hi[bad] = self._sd[np.minimum(k[bad] + wide, nd - 1)]
            flo[bad], fhi[bad] = f(lo[bad], pts[bad]), f(hi[bad], pts[bad])
        bad = np.sign(flo) == np.sign(fhi)            # beyond an end: clamp to it
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            fm = f(mid, pts)
            left = np.sign(fm) == np.sign(flo)
            lo = np.where(left, mid, lo)
            flo = np.where(left, fm, flo)
            hi = np.where(left, hi, mid)
        s = np.where(bad, np.where(np.abs(flo) < np.abs(fhi), lo, hi), 0.5 * (lo + hi))
        p, n, b, _ = self.frame_at(s)
        d = pts - p
        th = np.arctan2(np.einsum('ij,ij->i', d, b), np.einsum('ij,ij->i', d, n))
        return s, th, np.linalg.norm(d, axis=1)

    # ----------------------------------------------------------------------------------------- the table
    def _cell(self, s, th):
        fi = (np.asarray(s, np.float64) - self.s_grid[0]) / self.ds
        fj = (np.asarray(th, np.float64) - self.th_grid[0]) / self.dth
        bad = ~(np.isfinite(fi) & np.isfinite(fj))
        fi = np.where(bad, 0.0, fi)
        fj = np.where(bad, 0.0, fj)
        i = np.clip(np.floor(fi).astype(np.int64), 0, len(self.s_grid) - 2)
        j = np.clip(np.floor(fj).astype(np.int64), 0, len(self.th_grid) - 2)
        a = np.where(bad, np.nan, fi - i)
        c = np.where(bad, np.nan, fj - j)
        return i, a, j, c

    def _bilinear(self, T, s, th):
        i, a, j, c = self._cell(s, th)
        return ((1 - a) * ((1 - c) * T[i, j] + c * T[i, j + 1]) + a * ((1 - c) * T[i + 1, j] + c * T[i + 1, j + 1]))

    def radius(self, s, th):
        """the TABLE's radius (bilinear between the rays: within a few um on the mantle, but it rounds the low's
        vertices; from_st casts the exact ray instead)"""
        return self._bilinear(self.R, s, th)

    def ray(self, s, th):
        """the exact first hit along (s, theta)'s ray: (distance, face, region); nan / -1 where none within max_r"""
        s = np.atleast_1d(np.asarray(s, np.float64))
        th = np.broadcast_to(np.atleast_1d(np.asarray(th, np.float64)), s.shape)
        ok = np.isfinite(s) & np.isfinite(th)
        out_r = np.full(len(s), np.nan)
        out_f = np.full(len(s), -1, np.int64)
        idx = np.nonzero(ok)[0]
        if len(idx):
            p, n, b, _ = self.frame_at(s[idx])
            d = np.cos(th[idx])[:, None] * n + np.sin(th[idx])[:, None] * b
            tmax = (np.asarray(self._max_r(s[idx]), np.float64) if callable(self._max_r) else
                    np.full(len(idx), float(self._max_r)))
            m = len(idx)
            dev = self._device
            ot = wp.zeros(m, dtype=float, device=dev)
            of = wp.zeros(m, dtype=wp.int32, device=dev)
            wp.launch(k_rays, dim=m, inputs=[self._ray_mesh.id, wp.array(p.astype(np.float32), dtype=wp.vec3, device=dev),
                                             wp.array(d.astype(np.float32), dtype=wp.vec3, device=dev),
                                             wp.array(tmax.astype(np.float32), dtype=float, device=dev), ot, of],
                      device=dev)
            t_, f_ = ot.numpy().astype(np.float64), of.numpy().astype(np.int64)
            hit = (f_ >= 0) & (t_ > self._min_r)
            out_r[idx[hit]] = t_[hit]
            out_f[idx[hit]] = f_[hit]
        reg = np.where(out_f >= 0, self._region_of_face[np.maximum(out_f, 0)], -1)
        return out_r, out_f, reg

    def cast(self, org, dirs, tmax):
        """rays against the chart's mesh (the canonical low): the first hits (n, 3) (nan where none) and their faces"""
        org = np.atleast_2d(np.asarray(org, np.float64))
        dirs = np.atleast_2d(np.asarray(dirs, np.float64))
        m = len(org)
        dev = self._device
        ot = wp.zeros(m, dtype=float, device=dev)
        of = wp.zeros(m, dtype=wp.int32, device=dev)
        wp.launch(k_rays, dim=m, inputs=[self._ray_mesh.id, wp.array(org.astype(np.float32), dtype=wp.vec3, device=dev),
                                         wp.array(dirs.astype(np.float32), dtype=wp.vec3, device=dev),
                                         wp.array(np.full(m, float(tmax), np.float32), dtype=float, device=dev), ot, of],
                  device=dev)
        t_, f_ = ot.numpy().astype(np.float64), of.numpy().astype(np.int64)
        hit = f_ >= 0
        out = np.where(hit[:, None], org + t_[:, None] * dirs, np.nan)
        return out, np.where(hit, f_, -1)

    def w_of(self, s, th):
        return self._bilinear(self.W, s, th)

    def th_of(self, s, w):
        """the angle at share s whose arc length from theta 0 is w (the exact inverse of w_of's piecewise-linear row)"""
        s = np.atleast_1d(np.asarray(s, np.float64))
        w = np.atleast_1d(np.asarray(w, np.float64))
        i, a, _, _ = self._cell(s, np.zeros_like(s))
        Wb = self._Wb

        def row(j):
            # an invalid cell is -inf / +inf; on a table row exactly a is 0 or 1, and (1 - a) * inf would be nan, which
            # breaks the bisection's monotone row (the C1 check: arm 2's and arm 5's outlines went nan at s 0.19)
            A_, B_ = Wb[i, j], Wb[i + 1, j]
            with np.errstate(invalid='ignore'):
                mix = (1 - a) * A_ + a * B_
            return np.where(a <= 0.0, A_, np.where(a >= 1.0, B_, mix))
        lo = np.zeros(len(s), np.int64)
        hi = np.full(len(s), len(self.th_grid) - 1, np.int64)
        while np.any(hi - lo > 1):
            mid = (lo + hi) // 2
            go = row(mid) <= w
            lo = np.where(go, mid, lo)
            hi = np.where(go, hi, mid)
        wl, wh = row(lo), row(hi)
        tol = 1e-9                                    # (a point on the section's ends, theta +-pi, in float64)
        ok = np.isfinite(wl) & np.isfinite(wh) & (wh > wl) & (w >= wl - tol) & (w <= wh + tol)
        c = np.where(ok, (w - np.where(ok, wl, 0.0)) / np.where(ok, wh - wl, 1.0), np.nan)
        return self.th_grid[lo] + np.clip(c, 0.0, 1.0) * self.dth

    # ----------------------------------------------------------------------------------------- the coordinates
    def from_st(self, s, th, r=None):
        """the surface point at (s, theta): the exact ray's first hit (r None), or at the radius given"""
        s = np.atleast_1d(np.asarray(s, np.float64))
        th = np.broadcast_to(np.atleast_1d(np.asarray(th, np.float64)), s.shape)
        r = self.ray(s, th)[0] if r is None else np.broadcast_to(np.asarray(r, np.float64), s.shape)
        p, n, b, _ = self.frame_at(np.where(np.isfinite(s), s, 0.0))
        return p + r[:, None] * (np.cos(th)[:, None] * n + np.sin(th)[:, None] * b)

    def to_uw(self, pts):
        s, th, _ = self.to_st(pts)
        return np.column_stack([s * self.L, self.w_of(s, th)])

    def from_uw(self, uw):
        uw = np.atleast_2d(np.asarray(uw, np.float64))
        s = uw[:, 0] / self.L
        return self.from_st(s, self.th_of(s, uw[:, 1]))

    def tangents(self, uw, h=2.0e-4):
        """the surface's unit tangents along u and w at chart points, its outward normal, and the metric |dp/du|"""
        uw = np.atleast_2d(np.asarray(uw, np.float64))
        du = np.array([h, 0.0])
        dw = np.array([0.0, h])
        pu = (self.from_uw(uw + du) - self.from_uw(uw - du)) / (2 * h)
        pw = (self.from_uw(uw + dw) - self.from_uw(uw - dw)) / (2 * h)
        nrm = np.cross(pu, pw)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        s = uw[:, 0] / self.L
        p, _, _, _ = self.frame_at(s)
        out = self.from_uw(uw) - p
        nrm *= np.where(np.einsum('ij,ij->i', nrm, out) < 0, -1.0, 1.0)[:, None]
        gu = np.linalg.norm(pu, axis=1)
        return pu / gu[:, None], pw / np.linalg.norm(pw, axis=1, keepdims=True), nrm, gu

    def local_radius(self, s, th_max):
        """the section's mean radius over |theta| <= th_max at shares s (the R of 'plate size in R units', §4.2.3)"""
        s = np.atleast_1d(np.asarray(s, np.float64))
        th = np.linspace(-th_max, th_max, 61)
        return np.nanmean(self.radius(np.repeat(s, len(th)), np.tile(th, len(s))).reshape(len(s), len(th)), axis=1)

    def run_bounds(self, s, th_max, allowed):
        """per share: the largest +theta and -theta (up to th_max) over which every cell from theta 0 is valid and hit
        one of the allowed low regions"""
        s = np.atleast_1d(np.asarray(s, np.float64))
        i = np.clip(np.rint((s - self.s_grid[0]) / self.ds).astype(np.int64), 0, len(self.s_grid) - 1)
        A = np.isin(self.REG, list(allowed)) & np.isfinite(self.W)
        nth = len(self.th_grid)
        kmax = int(np.floor(th_max / self.dth + 1e-9))
        tp = np.zeros(len(s))
        tm = np.zeros(len(s))
        for q in range(len(s)):
            row = A[i[q]]
            if not row[self.j0]:
                tp[q] = tm[q] = 0.0
                continue
            k = 0
            while k < kmax and self.j0 + k + 1 < nth and row[self.j0 + k + 1]:
                k += 1
            tp[q] = th_max if k == kmax else k * self.dth
            k = 0
            while k < kmax and self.j0 - k - 1 >= 0 and row[self.j0 - k - 1]:
                k += 1
            tm[q] = th_max if k == kmax else k * self.dth
        return tp, tm


def body_chart(low, spec=None, device=None, ns=621, nth=721):
    """the octopus's body loft chart (the mantle and the collar: s 0-0.62 of the axis, apex to crown), its rays against
    every triangle of the canonical low"""
    from .species import octopus as O
    spec = O.low_spec(spec or O.SPEC)
    P, n, b, t = O.body_axis(spec)
    return Chart('mantle', P, n, b, t, low, s_range=(0.0, 0.62), ns=ns, nth=nth, max_r=0.12, device=device,
                 meta=dict(src='forge/species/octopus.py body_axis (the body loft\'s centreline; n dorsal)'))


def arm_chart(low, j=0, spec=None, device=None, ns=1241, nth=361, s_max=0.62):
    """octopus arm j's chart (the glb's arm<j>: octopus.arm_centreline at the azimuth of the low's order[j]; n aboral),
    s 0-s_max; a ray longer than 1.6 x the arm's radius there is no hit (the web, a neighbour)"""
    from .species import octopus as O
    from .species import octopus_rig as ORIG
    spec = O.low_spec(spec or O.SPEC)
    order = np.asarray(low['order'])
    az = float(O.arm_azimuths()[order[j]])
    Pa, na, ba, ta = O.arm_centreline(spec, az)
    ch = Chart(f'arm{j}', Pa, na, ba, ta, low, s_range=(0.0, s_max), ns=ns, nth=nth,
               max_r=lambda s: 1.6 * O.arm_radius(s, spec), device=device, s_nodes=np.linspace(0.0, 1.0, len(Pa)),
               meta=dict(src=f'forge/species/octopus.py arm_centreline (azimuth {np.degrees(az):.1f} deg; n aboral; '
                             's by node as forge/species/octopus_rig.py places the joints)', arm=j, azimuth=az))
    ch.joints_s = np.asarray(ORIG.arm_joint_s(spec), np.float64)
    ch.radius_s = lambda s: O.arm_radius(s, spec)
    return ch


# ============================================================================================ the junction's section
# THE JUNCTION (CYBORG_PLAN §3.5, §3.9 row 3, §4.2.4 item 4; A.2.2; the lead's C2 brief: "TechnoHunter's crease, not a
# lip"): where the plates meet the skin, ONE designed cross-section in (d, z): d the signed surface distance from the
# region's outline (+ into the plates), z the height over the UNSCULPTED block-out. From the skin to the plate:
#   the skin's level (0) FALLS over `fall` into the CREASE, `crease` under it (a smoothstep: the TechnoHunter's skin
#   "falls gently toward the junction over its last ~10 px", 3.2 mm here; the paler SCAR band rides that fall); a FLOOR
#   strip `floor` wide (the dark line, where the skin tucks: 0.56 mm of it shows beside the bead's overhang at these
#   numbers, about two voxels and two of the head set's texels, so the bake resolves it); the GASKET, a rubber bead of
#   radius gasket_r SEATED on the crease's floor on the outline (its foot 0.1 mm into it) and standing to `gasket_top`
#   over the skin's level (0.75 mm under the plate's top: the plan's "at least 0.2 under"), so the seal reads (seated at
#   the skin's level only its 0.7 mm flank showed, lost in the crease's shadow: C2's look);
#   the plate's ROLLED RIM, a quarter sine from the bead's top to the plate's top t, as wide as makes the junction's
#   10-90 % rise `ramp` AS c_grav READS IT (from the first 10 % crossing, here on the bead's skin-side flank, to the
#   rim's 90 %); the flat top. Nothing outside the plate stands above both sides: no lip (the TechnoHunter's 313
#   profiles: 74 % creased, 0 % lipped; the bead stands 0.75 mm under the plate's level).
# The measured junction (c_grav.py boundary on the TechnoHunter, transferred by texels and by R, §3.5): the plate proud
# 1.19-1.27, the crease 0.82-0.88, the 10-90 % ramp 3.03-3.24 mm (the plan's ranges 1.2-1.3 / 0.8-0.9 / 3.0-3.2).
# The 'ridge' variant (§3.9 row 3: the forge strand's raised scar ridge, kept for Skye's look): no crease; the gasket
# r 0.7 mm 0.2 mm up on the outline (0.9 mm proud), the rim from the skin's level, and a scar RIDGE r 1.4 mm 0.8 mm
# under the skin 2.0 mm outside the outline (0.6 mm proud, 2.3 mm wide) [E-fo]
# THE TROUGH'S TOP (C3: the octopus's close-ups): the carved space is closed from above by a smooth rise from the fall's
# start, trough_top over trough_top_w (a smoothstep, tangent there to the fall's own smoothstep), never by a vertical
# wall: with a wall the air just over the skin at the fall's start read its distance to the wall, the field's gradient
# turned sideways in a one-voxel band along the fall's edge, and every normal computed from the field (the traces',
# the bake's) printed a saw-tooth there at the voxel pitch (the zero set itself is unchanged: the solid is z < 0)
JUNCTION = dict(crease=0.85e-3, fall=3.1e-3, floor=0.9e-3, gasket_r=0.7e-3, gasket_top=0.45e-3, ramp=3.1e-3,
                ridge_gasket_z=0.2e-3, ridge_r=1.4e-3, ridge_depth=0.8e-3, ridge_out=2.0e-3,
                k_trough=0.1e-3, k_plate=0.1e-3, k_gasket=0.1e-3, k_ridge=0.15e-3,
                trough_top=0.5e-3, trough_top_w=1.6e-3)


def junction_design(t, kind='crease', J=None):
    """the junction's cross-section for a plate t over the block-out (the notes above, JUNCTION), every number in (d,
    z) metres: the rim (z = z0 + (t - z0) sin(pi/2 (d - d0) / W) from d0 to its flat at d0 + W), the gasket (its tube's
    centre and radius), the trough (the skin's fall from d_lo to d_c, then the floor to d_hi), the scar band, the ridge
    (the variant), the op's reach (d_out .. d_in) and the DESIGNED measures (step, crease, ramp, as c_grav.py reads a
    profile whose far windows lie flat)"""
    if kind not in ('crease', 'ridge'):
        raise CyborgError('cyborg.surface', f'junction {kind!r}: crease or ridge')
    J = dict(JUNCTION, **(J or {}))
    r_g = J['gasket_r']
    if kind == 'crease':
        floor_z = -J['crease']
        z_g = J['gasket_top'] - r_g                              # the bead's centre (its foot seated in the floor)
        if z_g - r_g > floor_z:
            raise CyborgError('cyborg.surface', 'the gasket would float over the crease\'s floor')
        dz = floor_z - z_g
        foot = math.sqrt(max(r_g * r_g - dz * dz, 0.0))         # the bead's footprint on the floor
        x_vis = -(r_g if z_g > floor_z else foot)               # its skin-side edge seen from over the skin
        d_c = -foot - J['floor']                                # the fall's foot: the crease's outer edge
        d_lo = d_c - J['fall']                                  # where the skin starts to fall
        z0 = z_g + r_g                                          # the rim rises from the bead's top
        scar = (d_lo, d_c)
        ridge = None
    else:
        floor_z = 0.0
        z_g = J['ridge_gasket_z']
        d_c = d_lo = -r_g
        x_vis = -r_g
        z0 = 0.0
        rr = J['ridge_r']
        d_r = -r_g - J['ridge_out']                             # the ridge's centre line, outside the gasket
        ridge = dict(d=d_r, z=-J['ridge_depth'], r=rr, proud=rr - J['ridge_depth'],
                     width=2.0 * math.sqrt(rr * rr - J['ridge_depth'] ** 2))
        scar = (d_r - 0.5 * ridge['width'], d_r + 0.5 * ridge['width'])
    # the rim: a quarter sine from (0, z0) to (W, t). Its width makes the junction's 10-90 % rise (of the step over the
    # skin's level 0, c_grav's definition) `ramp`: the 10 % line crossed first on the bead's skin-side flank when the
    # bead stands over it, else on the rim; the 90 % on the rim
    lv10, lv90 = 0.1 * t, 0.9 * t
    s90 = 2.0 / math.pi * math.asin(min(1.0, max(0.0, (lv90 - z0) / (t - z0))))
    top_g = z_g + r_g
    if kind == 'crease' and top_g > lv10:
        x10 = -math.sqrt(max(r_g * r_g - (lv10 - z_g) ** 2, 0.0))
        W = (x10 + J['ramp']) / s90
    else:
        s10 = 2.0 / math.pi * math.asin(min(1.0, max(0.0, (lv10 - z0) / (t - z0))))
        x10 = None
        W = J['ramp'] / (s90 - s10)
    if W <= 0.0:
        raise CyborgError('cyborg.surface', f'no rim gives a {J["ramp"]*1e3:.2f} mm ramp from this gasket')
    ramp = (W * s90 - x10) if x10 is not None else J['ramp']
    d_out = (ridge['d'] - ridge['r'] if ridge else d_lo) - 1.0e-3
    return dict(kind=kind, t=t, J=J, rim=dict(d0=0.0, z0=z0, W=W, flat=W),
                gasket=dict(d=0.0, z=z_g, r=r_g, top=top_g, x_vis=x_vis),
                trough=None if kind == 'ridge' else dict(d_lo=d_lo, d_c=d_c, z=floor_z, d_hi=0.5e-3,
                                                          top=J['trough_top'], top_w=J['trough_top_w']),
                scar=scar, ridge=ridge, reach=(d_out, W + 1.0e-3),
                designed=dict(step=t, crease=(-floor_z if kind == 'crease' else 0.0), ramp=ramp,
                              gasket_under_top=t - top_g, gasket_proud=top_g))


def junction_reach(t, kind='crease'):
    """how far into the plates the junction's rim runs before the flat top (m): the region outline's corners take at
    least this radius (+ 0.5 mm), so the rim's contours stay round at a corner instead of mitring"""
    return junction_design(t, kind)['rim']['flat']


# ============================================================================================ the panel layout
CORNER_R = 0.13          # the region outline's corner radius in local radii (the prototype's 8 mm on the mantle [E-fo])
SCREW_LAND = 0.5e-3      # a seam stops this short of a fastener's mouth (the body's SCREW_LAND, A.2.2 [H via kb])
RIVET_MIN_D = 3.0        # the least rivet spacing in head diameters (the FAA's rule, CYBORG_PLAN §3.4 [P])
EXACT = 1.0e-8           # the 2 D inset is SOLVED to this (m): every head 2 D from its own edge's lip and at least 2 D from
                         # every other lip and the outline (the lead's C2 call 3; c01 gates 1 um)
EDGE_N = 129             # the least samples along a plate edge's polyline
EDGE_STEP = 4.0e-5       # the outline's and the plate edges' polylines are sampled this fine (m): their chords' sag
                         # stays near 1e-8 m on the octopus's curvatures, so an exact inset reads exact on either
# ONE PHYSICAL HEAD SIZE, its spread INSIDE the acceptance band (the lead's C3 call 2): the band of the heads as baked,
# in texels at fastener_tx 10 (scaled by fastener_tx / 10), and the one D solved so the spread sits CENTRED on the
# TARGET (its geometric middle sqrt(min x max) = 10.13 at 10, C3's band 9.5-10.8's middle: "the range is the acceptance
# band, the 10 a target"); a spread wider than the band refuses. THE LEAD'S C3b CALL: the band widened to 9.4-10.9 so
# arms 3 / 4 plate (their one-size spreads x1.138-1.147 against C3's x1.1368); the target stays where it was, so every
# layout C3 laid is laid again byte for byte (the mantle's t10 outputs stand)
HEAD_TX_BAND = (9.4, 10.9)
HEAD_TX_C3 = (9.5, 10.8)                 # C3's band: its geometric middle is the target (computed as C3 computed it)
HEAD_TX_TARGET = math.sqrt(HEAD_TX_C3[0] * HEAD_TX_C3[1])
HEAD_CENTRE_TOL = 2.0e-4 # the centring's tolerance (relative): the mantle's spreads leave ~0.1 % each side
# the 2 D inset ON THE PLATE (the lead's C3 call 3): each plate's raster of its top's points (plate_top) over its (u, v),
# this fine on the surface, padded round the plate (the solve's Newton steps reach past its edges), read bilinearly
RASTER_STEP = 5.0e-4
RASTER_PAD = 2.5e-3
# a plate region given directly (panel_layout(region_spec=)): a PLATE_REGIONS entry's keys
REGION_KEYS = ('chart', 'set', 'stacked', 'low_regions', 's', 'theta_deg', 'rows', 'plate_R', 's_max')


def _surface_spec(row, base, region, region_spec=None):
    """the row resolved: remix/slots.py check_surface (any error refuses), then SURFACE_DEFAULTS, the region's extent,
    the row's own values. region_spec: the region given directly (REGION_KEYS: a test fixture, or a base whose
    PLATE_REGIONS entry is not written yet): the row is checked for its keys and values alone, its s against the
    region's s_max, and rows against a region whose rows follow its joints"""
    from ..remix import slots as SL
    if (row or {}).get('kind', 'plates') != 'plates':
        raise CyborgError('cyborg.surface', f'a {(row or {}).get("kind")!r} row lays no plates (panel_layout takes a plates '
                                            'row; feed_layout routes a feed row\'s lines over a layout)')
    if region_spec is None:
        probs = SL.check_surface([dict(row or {}, region=region)], base)
        R = SL.PLATE_REGIONS[base][region] if not [p for p in probs if p['severity'] == 'error'] else None
    else:
        miss = [k for k in REGION_KEYS if k not in region_spec]
        if miss:
            raise CyborgError('cyborg.surface', f'region_spec lacks {miss} (a plate region carries {REGION_KEYS})')
        R = dict(region_spec)
        probs = SL.check_surface([{k: v for k, v in (row or {}).items() if k != 'region'}], None)
        s_row = (row or {}).get('s')
        if s_row is not None and float(s_row[1]) > float(R['s_max']) + 1e-9:
            probs.append(dict(severity='error', code='cyborg.surface', where='cyborg.surface[0]',
                              message=f's {list(s_row)} runs past the region\'s own texels at s {R["s_max"]}'))
        if R.get('rows') == SL.JOINT_ROWS and (row or {}).get('rows') is not None:
            probs.append(dict(severity='error', code='cyborg.surface', where='cyborg.surface[0]',
                              message='rows on a region whose rows follow its joints'))
    errs = [p for p in probs if p['severity'] == 'error']
    if errs:
        raise CyborgError(errs[0]['code'], '; '.join(f'{p["where"]}: {p["message"]}' for p in errs))
    spec = dict(SL.SURFACE_DEFAULTS)
    spec.update({k: R[k] for k in ('s', 'theta_deg', 'rows', 'plate_R') if k in R})
    spec.update({k: v for k, v in (row or {}).items() if v is not None})
    spec['seam_tx'] = int(spec.get('seam_tx') or SL.SEAM_TX[spec['seams']])
    if spec['fasteners'] == 'riveted' and (row or {}).get('pitch_D') is None:
        spec['pitch_D'] = SL.RIVET_PITCH_D                 # the plan's riveted edges: 3.4 D
    return spec, R


def _rounded_inside(u, w, u0, u1, wh, rc):
    """the region outline's signed distance (+ inside, mm-like chart units): a rounded rectangle in the local (u, w)
    frame, w measured against the half width wh(u) at each point"""
    a = np.minimum(u - u0, u1 - u)
    b = wh - np.abs(w)
    corner = (a < rc) & (b < rc)
    return np.where(corner, rc - np.hypot(rc - np.minimum(a, rc), rc - np.minimum(b, rc)), np.minimum(a, b))


def _polyline_dist(points, lines):
    """the distance from each point to the nearest of the polylines (3D): exact to the 8 segments whose middles lie
    nearest it"""
    from scipy.spatial import cKDTree
    segs = [np.stack([L[:-1], L[1:]], 1) for L in lines if len(L) > 1]
    if not segs:
        return np.full(len(points), np.inf)
    S = np.concatenate(segs)
    mid = 0.5 * (S[:, 0] + S[:, 1])
    tree = cKDTree(mid)
    k = min(8, len(S))
    _, idx = tree.query(points, k=k)
    idx = np.atleast_2d(idx).reshape(len(points), k)
    a, b = S[idx, 0], S[idx, 1]
    ab = b - a
    tt = np.clip(np.einsum('nkd,nkd->nk', points[:, None] - a, ab) / np.maximum(np.einsum('nkd,nkd->nk', ab, ab),
                                                                               1e-30), 0.0, 1.0)
    d = np.linalg.norm(points[:, None] - (a + tt[..., None] * ab), axis=2)
    return d.min(1)


def _polyline_closest(points, line, k=8):
    """the closest point of ONE polyline (3D) to each point: (distance, the point, its segment index, the parameter
    along that segment); exact over the k segments whose middles lie nearest (dense polylines: every outline here)"""
    from scipy.spatial import cKDTree
    S = np.stack([line[:-1], line[1:]], 1)
    k = min(k, len(S))
    _, idx = cKDTree(0.5 * (S[:, 0] + S[:, 1])).query(points, k=k)
    idx = np.atleast_2d(idx).reshape(len(points), k)
    a, b = S[idx, 0], S[idx, 1]
    ab = b - a
    tt = np.clip(np.einsum('nkd,nkd->nk', points[:, None] - a, ab) / np.maximum(np.einsum('nkd,nkd->nk', ab, ab),
                                                                               1e-30), 0.0, 1.0)
    q = a + tt[..., None] * ab
    d = np.linalg.norm(points[:, None] - q, axis=2)
    j = d.argmin(1)
    r = np.arange(len(points))
    return d[r, j], q[r, j], idx[r, j], tt[r, j]


def _plate_raster(p, Xof, up_, wh, gu):
    """a plate's raster of its TOP (the lead's C3 call 3): plate_top's points (up_) over a grid of the plate's (u, v),
    RASTER_STEP apart on the surface and RASTER_PAD past its edges (u by the chart's |dp/du| gu at its centre, v by its
    narrowest half width); a node with no chart point takes its nearest node's. dict(U, V, P (nu, nv, 3))"""
    from scipy import ndimage
    whs = np.array([float(wh(u)) for u in np.linspace(p['ua'], p['ub'], 9)])
    mu, mv = RASTER_PAD / gu, RASTER_PAD / float(whs.min())
    nu = max(9, int(math.ceil((p['ub'] - p['ua'] + 2.0 * mu) * gu / RASTER_STEP)) + 1)
    nv = max(9, int(math.ceil((p['vb'] - p['va'] + 2.0 * mv) * float(whs.max()) / RASTER_STEP)) + 1)
    U = np.linspace(p['ua'] - mu, p['ub'] + mu, nu)
    V = np.linspace(p['va'] - mv, p['vb'] + mv, nv)
    UU, VV = np.meshgrid(U, V, indexing='ij')
    X = Xof(np.column_stack([UU.ravel(), VV.ravel()])).reshape(nu, nv, 3)
    bad = ~np.all(np.isfinite(X), axis=2)
    if bad.all():
        raise CyborgError('cyborg.chart', f'plate {p.get("index")}: its raster finds no surface on the chart')
    if bad.any():
        _, (ii, jj) = ndimage.distance_transform_edt(bad, return_indices=True)
        X = X[ii, jj]
    return dict(U=U, V=V, P=up_(X.reshape(-1, 3)).reshape(nu, nv, 3))


def _raster_at(ras, UV):
    """a plate raster read bilinearly at (u, v) points (held at its border past it): their points on the plate's top"""
    UV = np.atleast_2d(np.asarray(UV, np.float64))
    U, V, P = ras['U'], ras['V'], ras['P']
    fu = np.clip((UV[:, 0] - U[0]) / (U[1] - U[0]), 0.0, len(U) - 1.0)
    fv = np.clip((UV[:, 1] - V[0]) / (V[1] - V[0]), 0.0, len(V) - 1.0)
    i = np.minimum(np.floor(fu).astype(np.int64), len(U) - 2)
    j = np.minimum(np.floor(fv).astype(np.int64), len(V) - 2)
    a = (fu - i)[:, None]
    c = (fv - j)[:, None]
    return (1.0 - a) * ((1.0 - c) * P[i, j] + c * P[i, j + 1]) + a * ((1.0 - c) * P[i + 1, j] + c * P[i + 1, j + 1])


def _box_sum(a, lo, hi, total, iters=400):
    """a vector moved inside [lo, hi] keeping its sum `total` (n lo <= total <= n hi): clipped, then the remainder
    spread over the entries still free to take it, until it is spent"""
    a = np.clip(np.asarray(a, np.float64), lo, hi)
    for _ in range(iters):
        r = total - float(a.sum())
        if abs(r) <= 1e-12 * max(abs(total), 1e-30):
            break
        free = (a < hi) if r > 0 else (a > lo)
        if not free.any():
            break
        a = np.clip(np.where(free, a + r / free.sum(), a), lo, hi)
    return a


def panel_layout(chart, density, row=None, base='octopus', region='body', seed=0, voxel=0.0003, joints_s=None,
                 lift=None, region_spec=None, _plan=None):
    """the PANEL LAYOUT of one surface row on one chart (module notes). row: the recipe's surface row (keys of
    remix/slots.py SURFACE_KEYS; defaults SURFACE_DEFAULTS and the region's). lift: the block-out's height over the low
    (a callable of points, blockout_lift(); None = 0): seams and heads are sized for the RAISED plate the bake reads.
    region_spec: the plate region given directly (REGION_KEYS; a test fixture, or a base whose PLATE_REGIONS entry is
    not written yet) instead of slots.PLATE_REGIONS[base][region].
    THE LEAD'S C2 AND C3 CALLS, by construction: (1) every plate's equal-area diameter inside its region's plate_R (a
    row's plates share the row's area: no sliver at its end); the ARM one plate per joint segment across its strip
    (per_row 1: the armour lames' read, the joints the seams; its band the rows' own size, ~2.2-2.5 R), 'ends' heads at
    both ends; (2) ONE physical head size per layout, its spread as baked INSIDE the acceptance band (HEAD_TX_BAND,
    9.5-10.8 texels at fastener_tx 10) and centred in it (a spread wider than the band refuses); (3) every head exactly
    2 D from its own edge's lip and at least 2 D from every other lip and the outline, ON THE PLATE (plate_top: where
    the heads and the lips physically are; solved, not settled).
    Returns a dict: params (every size resolved, in mm and texels), region (its u range, half widths, R), plates,
    seams, outline, fasteners, stats. Raises CyborgError: a stacked region without arms='all' (cyborg.stacked), a region
    whose s range leaves its own texels or a chart point off the surface (cyborg.region), a row whose area cannot split
    into plates inside plate_R wide enough for their heads, a fastener closer to a seam than SCREW_LAND or an 'ends'
    plate that cannot hold its least heads (cyborg.layout)"""
    from ..remix import slots as SL
    region = (row or {}).get('region') or region
    spec, R = _surface_spec(row, base, region, region_spec)
    joint_rows = R.get('rows') == SL.JOINT_ROWS
    per_row = R.get('per_row')                 # plates across each row, by the region's rule (the arm: 1); None: by area
    if joint_rows and joints_s is None:
        joints_s = getattr(chart, 'joints_s', None)       # an arm's rings fall at its joints
        if joints_s is None:
            raise CyborgError('cyborg.region', f'{region}\'s rows follow its joints, and chart {chart.name} carries '
                                               'no joints')
    if R['stacked'] and spec.get('arms') != 'all':
        raise CyborgError('cyborg.stacked', f'{region} is a STACKED set ({R["set"]}): plates there print on every arm '
                                            'that shares its texels; say arms=\'all\' (or keep to a unique region)')
    seed_ = int(spec.get('seed') if spec.get('seed') is not None else seed)
    rng = np.random.default_rng(seed_)
    L = chart.L
    s0, s1 = float(spec['s'][0]), float(spec['s'][1])
    th_max = math.radians(float(spec['theta_deg']))
    allowed = tuple(R['low_regions'])
    # ------------------------------------------------------------------------- the region on the chart
    us = np.linspace(s0, s1, 241)
    tp, tm = chart.run_bounds(us, th_max, allowed)
    wp_ = chart.w_of(us, tp)
    wm_ = -chart.w_of(us, -tm)
    whs = np.minimum(wp_, wm_)
    full = (tp >= th_max - 1e-9) & (tm >= th_max - 1e-9)
    if not np.all(np.isfinite(whs)) or not full.all():
        bad = us[~(np.isfinite(whs) & full)]
        raise CyborgError('cyborg.region', f'{region} on chart {chart.name}: s {s0:.3f}-{s1:.3f}, |theta| <= '
                                           f'{spec["theta_deg"]} leaves the low regions {allowed} (its own texels) at s '
                                           f'{bad.min():.3f}-{bad.max():.3f}: keep the row inside them')
    u_s = us * L
    wh = lambda u: np.interp(u, u_s, whs)
    Rl_s = chart.local_radius(us, th_max)
    Rl = lambda u: np.interp(u, u_s, Rl_s)
    u0, u1 = s0 * L, s1 * L
    R_mean = float(np.mean(Rl_s))
    plo, phi = float(spec['plate_R'][0]), float(spec['plate_R'][1])
    # rows sized for square-ish plates of the middle size: the region's width over the plates that fit across it, and
    # the row's height that gives such a plate the middle area (a region whose rows follow its joints takes theirs)
    A_mid = math.pi * (0.5 * (plo + phi) * R_mean) ** 2 / 4.0
    W_med = 2.0 * float(np.median(whs))
    w_exp = W_med / max(1, int(round(W_med / math.sqrt(A_mid))))
    h_target = A_mid / w_exp
    # THE BAKE'S VIEW (the C1 check): the PLATE op raises the plate plate_t off the block-out (+ the block-out's lift
    # over the low) and the bake reads that raised surface back through the low's smooth normals, so on a convex low a
    # seam or a head up there covers 1 / (1 + h k) of the texels the same width would on the low (the mantle k ~13-25
    # /m, the arm's strip up to ~70 /m). Every width is sized to hold its texels AS BAKED: grow = max(1, 1 + h k), k the
    # low's curvature across a seam, its mean under a head
    plate_t = float(spec['plate_t_mm']) * 1e-3
    hgt = lambda X: plate_t + (np.asarray(lift(X), np.float64) if lift is not None else 0.0)
    head_grow = lambda X: np.maximum(1.0, 1.0 + hgt(X) * density.mean_curvature(X))
    fastened = spec['fasteners'] != 'none'
    ftx = float(spec['fastener_tx'])
    # ONE PHYSICAL HEAD SIZE (the lead's C2 call 2): every head of the layout one diameter, the D whose median reads
    # fastener_tx texels as baked on the heads' own places (below). The plates' least widths are cut for a planned D
    # and seam lip: first the region's own medians, then (a monotone re-cut, _plan) the values the layout found, so
    # no margin stands between a row and the rule
    gs, gt = np.meshgrid(np.linspace(s0, s1, 9), np.linspace(-0.9 * th_max, 0.9 * th_max, 5), indexing='ij')
    Xg = chart.from_st(gs.ravel(), gt.ravel())
    px_reg = density.px_iso(Xg)
    grow_reg = head_grow(Xg)
    if _plan is None:
        D_plan = ftx * float(np.median(grow_reg / px_reg))
        # a seam's half width: a head stands 2 D from the seam's LIP, the plate's own edge, not from its centreline
        lip_est = 0.5 * float(spec['seam_tx']) * float(np.median(grow_reg / px_reg))
    else:
        D_plan, lip_est = float(_plan[0]), float(_plan[1])
    inset_plan = float(spec['inset_D']) * D_plan
    # an 'ends' plate holds a group 2 D in from each of two opposite edges, a group pitch apart
    plo_pitch = float(spec['pitch_D'][0] if isinstance(spec['pitch_D'], (list, tuple)) else spec['pitch_D'])
    plen = lambda X: float(np.linalg.norm(np.diff(X, axis=0), axis=1).sum())
    surf = lambda a, b: plen(chart.from_uw(np.column_stack([np.linspace(a, b, 17), np.zeros(17)])))
    # the junction's rim runs this far into the plates before their flat top (junction_design)
    rim_reach = junction_reach(plate_t, str(spec['junction']))
    # ------------------------------------------------------------------------- rows (ring seams)
    bare = []
    if joint_rows:
        # ONE ROW PER JOINT SEGMENT (the lead's C2 call 1; A.2.2 "plates follow segments": no plate spans a bend): a ring
        # at every joint inside the region. A partial segment at either end too short ON THE SURFACE for one row of heads
        # 2 D from both its ring edges' lips stays BARE (the plated extent starts or ends at the joint, stats['bare']):
        # merged into its neighbour it would put a plate across a joint (the C1 layout merged arm 0's 13 mm stub)
        js = [float(x) * L for x in joints_s if u0 + 1e-9 < float(x) * L < u1 - 1e-9]
        bnd = [u0] + js + [u1]
        need = (2.0 * (inset_plan + lip_est) + 0.5e-3) if fastened else 0.25 * h_target
        if per_row:
            # ONE PLATE PER JOINT SEGMENT (the lead's C3 call 1): only WHOLE segments are plated; a partial one at either
            # end of the region (its s range cuts it) stays bare, as a joint's lame ends at the joint
            on_j = lambda u_: any(abs(u_ - float(x) * L) < 1e-9 for x in joints_s)
            if len(bnd) > 2 and not on_j(bnd[0]):
                bare.append((bnd[0] / L, bnd[1] / L))
                bnd = bnd[1:]
            if len(bnd) > 2 and not on_j(bnd[-1]):
                bare.append((bnd[-2] / L, bnd[-1] / L))
                bnd = bnd[:-1]
        while len(bnd) > 2 and surf(bnd[0], bnd[1]) < need:
            bare.append((bnd[0] / L, bnd[1] / L))
            bnd = bnd[1:]
        while len(bnd) > 2 and surf(bnd[-2], bnd[-1]) < need:
            bare.append((bnd[-2] / L, bnd[-1] / L))
            bnd = bnd[:-1]
        if surf(bnd[0], bnd[-1]) < need:
            raise CyborgError('cyborg.layout', f'{region} on chart {chart.name}: s {s0:.3f}-{s1:.3f} holds no joint '
                                               f'segment tall enough for a row of heads ({surf(bnd[0], bnd[-1])*1e3:.1f} '
                                               f'mm on the surface, {need*1e3:.1f} needed)')
        rows = list(zip(bnd[:-1], bnd[1:]))
    else:
        nr = int(spec['rows']) if spec.get('rows') else max(1, int(round((u1 - u0) / h_target)))
        hh = 1.0 + 0.24 * (rng.random(nr) - 0.5)
        cut = u0 + (u1 - u0) * np.concatenate([[0.0], np.cumsum(hh) / hh.sum()])
        rows = list(zip(cut[:-1], cut[1:]))
    u0, u1 = float(rows[0][0]), float(rows[-1][1])          # the plated extent (a bare stub left out)
    # ------------------------------------------------------------------------- the outline (rounded corners)
    # the corners at least as round as the junction's rim is wide (a smaller radius would mitre the rim's contours),
    # and no rounder than 2 D (in u: the chart's u runs up to gu_max of the surface) where heads stand: a head 2 D from a
    # straight side then never stands in a corner's square, so the arc costs a corner plate no width
    uw_g = np.column_stack([np.repeat(np.linspace(u0, u1, 9), 5), (np.tile(np.linspace(-0.8, 0.8, 5), 9) *
                                                                    wh(np.repeat(np.linspace(u0, u1, 9), 5)))])
    gu_max = float(max(1.0, np.max(chart.tangents(uw_g)[3])))
    rc = max(CORNER_R * R_mean, rim_reach + 0.5e-3)
    if fastened:
        rc = min(rc, max(rim_reach + 0.5e-3, inset_plan / gu_max))
    rc = min(rc, 0.45 * (u1 - u0), 0.45 * float(whs.min()))
    outline_uw = _outline(u0, u1, wh, rc, step=EDGE_STEP)
    inside = lambda uw: _rounded_inside(uw[:, 0], uw[:, 1], u0, u1, wh(uw[:, 0]), rc)

    def area_table(ua, ub, nu=13, nv=321):
        """the row's 3D surface area left of each v (cumulative over v -1..1; a cell at the outline's corner counts
        by the share of its corners inside): (v, A). Every plate's area is a difference of it, so its size in R is the
        rule's by construction (the final d_eq / R reads the same table)"""
        Uu = np.linspace(ua, ub, nu)
        Vv = np.linspace(-1.0, 1.0, nv)
        UU, VV = np.meshgrid(Uu, Vv, indexing='ij')
        uw = np.column_stack([UU.ravel(), (VV * wh(UU)).ravel()])
        X = chart.from_uw(uw).reshape(nu, nv, 3)
        ins = (inside(uw) >= 0).reshape(nu, nv).astype(np.float64)
        e1 = X[1:, :-1] - X[:-1, :-1]
        e2 = X[:-1, 1:] - X[:-1, :-1]
        e3 = X[1:, 1:] - X[1:, :-1]
        e4 = X[1:, 1:] - X[:-1, 1:]
        qa = 0.5 * (np.linalg.norm(np.cross(e1, e2), axis=2) + np.linalg.norm(np.cross(e3, e4), axis=2))
        share = 0.25 * (ins[:-1, :-1] + ins[1:, :-1] + ins[:-1, 1:] + ins[1:, 1:])
        if not np.all(np.isfinite(qa)):
            raise CyborgError('cyborg.region', f'{region} on chart {chart.name}: a row at u {ua*1e3:.1f}-{ub*1e3:.1f} mm '
                                               'finds no surface under some of its points: refused, never clipped')
        return Vv, np.concatenate([[0.0], np.cumsum((qa * share).sum(0))])
    # ------------------------------------------------------------------------- plates in each row (brick bond)
    # NO SLIVER END PLATES (the lead's C2 call 1): each row's 3D area is split among n plates whose areas all lie inside
    # the R rule's band (plate_R x the row's local radius) and whose widths hold a head 2 D from both side lips: the
    # row's remainder spreads over all its plates instead of landing on the last. Sizes are drawn (seeded) about the
    # middle and projected into the band with their sum kept; then the brick bond: no seam within 0.3 of the rule's
    # least width of the last row's seams at the ring between them, each seam nudged inside its two plates' bounds
    plates = []
    prev_v = []
    stagger_short = 0
    for r, (ua, ub) in enumerate(rows):
        um = 0.5 * (ua + ub)
        whm = float(wh(um))
        whr = float(wh(ua))
        Rm = float(Rl(um))
        A_lo, A_hi = math.pi * (plo * Rm) ** 2 / 4.0, math.pi * (phi * Rm) ** 2 / 4.0
        A_md = math.pi * (0.5 * (plo + phi) * Rm) ** 2 / 4.0
        lo_m, hi_m = A_lo * (1.0 + 1e-3), A_hi * (1.0 - 1e-3)
        Vt, At = area_table(ua, ub)
        A_tot = float(At[-1])
        h3 = surf(ua, ub)
        w_lo = A_lo / h3                                          # the rule's least width on the surface
        # every plate wide enough, at BOTH of its ring edges' head lines (2 D in from each ring edge's lip), for one head
        # 2 D from both its side lips measured SQUARE to each side: a meridian seam (w = v wh(u)) tilts by atan(v wh'(u) /
        # |dp/du|), and 2 D square to a tilted side costs 1 / cos of that along the line (the tapering mantle's apex row:
        # an interior plate there needs ~16 mm, not 14.5); the outline's sides carry no lip; a plate at a region corner
        # also clears the arc (corner_x). A row too short ON THE SURFACE for two ring-edge groups takes its 'ends' across
        # the width instead, the two side lines a group pitch apart (the C1 check: arm 0's seeds 3 and 17 cut 18 x 18.6
        # mm plates that no pair of ends could hold)
        short_row = spec['fasteners'] == 'ends' and h3 < 2.0 * (inset_plan + lip_est) + plo_pitch * D_plan
        d_in = (inset_plan + lip_est) * (ub - ua) / max(h3, 1e-9)        # the head lines' depth, in u
        lines_u = (ua + d_in, ub - d_in) if fastened else (um,)
        gu_r = float(chart.tangents(np.array([[um, 0.0]]))[3][0])
        dwh = [(float(wh(u_ + 1e-4)) - float(wh(u_ - 1e-4))) / 2e-4 for u_ in lines_u]
        whm = min(float(wh(u_)) for u_ in lines_u)
        corner_x = (1.1 * max(0.0, rc - inset_plan / gu_max) if (fastened and r in (0, len(rows) - 1)) else 0.0)

        def width_need(va, vb, k, n_):
            """[(the width plate k has, the width its head needs)] at each head line (m)"""
            out = []
            for u_, dw in zip(lines_u, dwh):
                req = sum((inset_plan + (0.0 if abs(abs(v_) - 1.0) < 1e-12 else lip_est)) *
                          math.sqrt(1.0 + (v_ * dw / gu_r) ** 2) for v_ in (va, vb))
                req += (plo_pitch * D_plan if short_row else 0.0) + (corner_x if k in (0, n_ - 1) else 0.0)
                out.append(((vb - va) * float(wh(u_)), req + 2.0e-6))
            return out
        fits = (lambda va, vb, k, n_: all(have >= req for have, req in width_need(va, vb, k, n_))) if fastened else \
            (lambda va, vb, k, n_: True)
        min_w = (2.0 * (inset_plan + lip_est) + (plo_pitch * D_plan if short_row else 0.0)) if fastened else 0.0
        n_lo = max(1, int(math.ceil(A_tot / hi_m - 1e-9)))
        n_hi = int(math.floor(A_tot / lo_m + 1e-9))
        if min_w > 0:
            n_hi = min(n_hi, int(math.floor((2.0 * whm - 2.0 * corner_x) / min_w + 1e-9)))
        if per_row:
            # ONE PLATE PER JOINT SEGMENT (the lead's C3 call 1: the armour lames' read, each rigid segment one plate
            # across its strip, the joints the seams): the row IS the plate, so the region's band is the rows' own
            # size (C2's band, 0.8-1.4 R, cut a segment into staves of 3.7-11.5 : 1 that held no 'ends' heads)
            if not n_lo <= int(per_row) <= n_hi:
                raise CyborgError('cyborg.layout', f'{region} row {r} ({h3*1e3:.1f} mm tall on the surface, '
                                                   f'{A_tot*1e6:.0f} mm2: d_eq {math.sqrt(4.0*A_tot/math.pi)/Rm:.3f} R of '
                                                   f'{Rm*1e3:.1f} mm, {2*whm*1e3:.1f} mm wide): {int(per_row)} plate(s) '
                                                   f'across it fall outside {plo}-{phi} R or under the width its heads '
                                                   f'need ({min_w*1e3:.1f} mm each)')
            n_lo = n_hi = int(per_row)
        if n_lo > n_hi:
            raise CyborgError('cyborg.layout', f'{region} row {r} ({h3*1e3:.1f} mm tall on the surface, '
                                               f'{A_tot*1e6:.0f} mm2) splits into no plates of {plo}-{phi} R (R '
                                               f'{Rm*1e3:.1f} mm: {A_lo*1e6:.0f}-{A_hi*1e6:.0f} mm2 each) at least '
                                               f'{min_w*1e3:.1f} mm wide (a head 2 D from both side lips): {n_lo} plates '
                                               f'are needed for the band, {n_hi} fit the width ({2*whm*1e3:.1f} mm)')
        n_md = int(np.clip(int(round(A_tot / A_md)), n_lo, n_hi))
        choices = [n_md] + [n for n in (n_md - 1, n_md + 1) if n_lo <= n <= n_hi]
        vA = lambda A: np.interp(A, At, Vt)
        Av = lambda v_: np.interp(v_, Vt, At)
        dz = 0.3 * w_lo / max(whr, 1e-9)                          # the brick bond's clearance in v at the ring
        best, tight = None, None
        for attempt in range(160):
            n = choices[0] if (len(choices) == 1 or rng.random() < 0.6) else choices[int(rng.integers(1, len(choices)))]
            x = rng.uniform(0.7, 1.3, n)
            a = _box_sum(A_tot * x / x.sum(), lo_m, hi_m, A_tot)
            v = vA(np.concatenate([[0.0], np.cumsum(a)]))
            v[0], v[-1] = -1.0, 1.0
            bad_k = [k for k in range(n) if not fits(v[k], v[k + 1], k, n)]
            if bad_k:
                k = bad_k[0]
                tight = (n, k, min(h - q for h, q in width_need(v[k], v[k + 1], k, n)))
                continue
            short = 0
            for k in range(1, len(v) - 1):
                if all(abs(v[k] - pv) >= dz for pv in prev_v):
                    continue
                # the seam's room: both its plates inside the band and wide enough
                lo_k = max(float(vA(Av(v[k - 1]) + lo_m)), float(vA(Av(v[k + 1]) - hi_m)))
                hi_k = min(float(vA(Av(v[k - 1]) + hi_m)), float(vA(Av(v[k + 1]) - lo_m)))
                cands = sorted({c for pv in prev_v for c in (pv - dz - 1e-7, pv + dz + 1e-7)}, key=lambda c: abs(c - v[k]))
                for c in cands:
                    if lo_k <= c <= hi_k and all(abs(c - pv) >= dz for pv in prev_v) and \
                            fits(v[k - 1], c, k - 1, n) and fits(c, v[k + 1], k, n):
                        v[k] = c
                        break
                else:
                    short += 1
            if best is None or short < best[1]:
                best = (v.copy(), short)
            if short == 0:
                break
        if best is None:
            raise CyborgError('cyborg.layout', f'{region} row {r}: no split into {choices} plates of {plo}-{phi} R gives '
                                               f'every plate the width its heads need (2 D square to each side lip; the '
                                               f'tightest of {tight[0]}: plate {tight[1]} short by {-tight[2]*1e3:.2f} mm)')
        v, short = best
        stagger_short += short
        for a, b in zip(v[:-1], v[1:]):
            plates.append(dict(row=r, ua=ua, ub=ub, va=float(a), vb=float(b), area=float(Av(b) - Av(a)), R=Rm,
                               w_head=float((b - a) * whm)))
        prev_v = list(v[1:-1])
    # ------------------------------------------------------------------------- seams (centrelines in u, w)
    seams = []
    for r, (ua, ub) in enumerate(rows):
        for p in [q for q in plates if q['row'] == r][1:]:        # the meridians between this row's plates
            uu = np.linspace(ua, ub, max(3, int((ub - ua) / 0.001) + 1))
            seams.append(dict(kind='meridian', row=r, uw=np.column_stack([uu, p['va'] * wh(uu)])))
        if r > 0:                                                 # the ring between this row and the last
            whr = float(wh(ua))
            ww = np.linspace(-whr, whr, max(3, int(2 * whr / 0.001) + 1))
            seams.append(dict(kind='ring', row=r, uw=np.column_stack([np.full_like(ww, ua), ww])))
    for sm in seams:
        keep = inside(sm['uw']) >= -1e-9
        sm['uw'] = sm['uw'][keep]
    seams = [sm for sm in seams if len(sm['uw']) >= 2]
    # ------------------------------------------------------------------------- 3D, normals, the seam width in texels
    for sm in seams:
        sm['p'] = chart.from_uw(sm['uw'])
    out_p = chart.from_uw(outline_uw)
    off_chart = [k for k, sm in enumerate(seams) if not np.all(np.isfinite(sm['p']))]
    if off_chart or not np.all(np.isfinite(out_p)):
        raise CyborgError('cyborg.region', f'{region} on chart {chart.name}: {len(off_chart)} seams and '
                                           f'{int((~np.all(np.isfinite(out_p), axis=1)).sum())} outline points find no '
                                           'surface point on the chart: refused, never clipped')
    allp = np.concatenate([sm['p'] for sm in seams]) if seams else np.zeros((0, 3))
    if seams:
        tng, across = [], []
        for sm in seams:
            d = np.gradient(sm['p'], axis=0)
            d /= np.linalg.norm(d, axis=1, keepdims=True)
            _, _, nrm, _ = chart.tangents(sm['uw'])
            q = np.cross(nrm, d)
            q /= np.linalg.norm(q, axis=1, keepdims=True)
            sm['across'], sm['normal'] = q, nrm
            tng.append(d)
            across.append(q)
        px_across = density.px_along(allp, np.concatenate(across))
        # as baked: the groove is carved on the raised plate, h = plate_t + lift over the low (THE BAKE'S VIEW above)
        seam_grow = np.maximum(1.0, 1.0 + hgt(allp) * density.curvature(allp, np.concatenate(across)))
        o_ = 0
        for sm in seams:
            sm['grow'] = seam_grow[o_:o_ + len(sm['p'])]
            o_ += len(sm['p'])
        w_req = spec['seam_tx'] * seam_grow / px_across
        seam_w = float(max(w_req.max(), 3.0 * voxel))
    else:
        px_across = np.zeros(0)
        seam_grow = np.ones(0)
        seam_w = 3.0 * voxel
    seam_depth = float(spec['seam_depth']) * seam_w
    # ------------------------------------------------------------------------- plates: area, size in R, centroid
    for i, p in enumerate(plates):
        p['index'] = i
        gu, gv = np.meshgrid(np.linspace(0, 1, 13), np.linspace(0, 1, 13), indexing='ij')
        U = p['ua'] + (p['ub'] - p['ua']) * gu
        Vn = p['va'] + (p['vb'] - p['va']) * gv
        uw = np.column_stack([U.ravel(), (Vn * wh(U)).ravel()])
        ins = (inside(uw) >= 0).reshape(13, 13)
        # the area is its row's table's (the partition's own measure: the plate's size in R is the rule's)
        cu = 0.5 * (p['ua'] + p['ub'])
        cv = 0.5 * (p['va'] + p['vb'])
        p['centre_uw'] = np.array([cu, cv * float(wh(cu))])
        p['centre'] = chart.from_uw(p['centre_uw'])[0]
        p['d_eq'] = math.sqrt(4.0 * p['area'] / math.pi)
        p['d_eq_R'] = p['d_eq'] / p['R']
        bu = np.concatenate([np.linspace(p['va'], p['vb'], 9), np.full(9, p['vb']), np.linspace(p['vb'], p['va'], 9),
                             np.full(9, p['va'])])
        uu = np.concatenate([np.full(9, p['ua']), np.linspace(p['ua'], p['ub'], 9), np.full(9, p['ub']),
                             np.linspace(p['ub'], p['ua'], 9)])
        p['poly_uw'] = np.column_stack([uu, bu * wh(uu)])
        # unique texels by construction: every sample of the plate hit the allowed low regions
        reg = chart.ray(uw[:, 0] / L, chart.th_of(uw[:, 0] / L, uw[:, 1]))[2]      # each sample's own texels
        if not np.all(np.isin(reg[ins.ravel()], allowed)):
            raise CyborgError('cyborg.region', f'plate {i} covers low regions {sorted(set(reg.tolist()))}, not only '
                                               f'{allowed}')
    # accent plates (the second tint region): a seeded share of the plates
    acc = float(spec.get('accent_share') or 0.0)
    for p in plates:
        p['paint'] = 'accent' if (spec.get('accent') and rng.random() < acc) else 'paint'
    # ------------------------------------------------------------------------- fasteners: ONE size, the 2 D inset EXACT
    # (the lead's C2 calls 2 and 3) Every head of the layout ONE diameter D (a screw is a real size; the eye compares
    # sizes in 3D, not texels): the D whose MEDIAN reads fastener_tx texels as baked (the spread is printed; the C1
    # check's 9.5-10.8 accepted). Every head exactly 2 D from its own edge's LIP (the plate's edge: half a seam inside a
    # seam's centreline; the region's outline itself where the plate meets it) and at least 2 D from every other lip and
    # the outline, SOLVED (Newton and regula falsi to EXACT), never settled to a tolerance:
    #   'ends': a group stands on its end's HEAD LINE (the curve exactly 2 D in from that end's lip), centred in the
    #   STRETCH of it that keeps 2 D from every other lip and the outline (the stretch's ends are roots: a group that
    #   fills it has its outer heads exactly 2 D from the side lips); the fastened ends are the edges across the plate's
    #   longer dimension when both groups fit, else the other pair; neither holding the least heads refuses the layout
    #   (never a 1-head plate);
    #   'riveted': a head at every CORNER, slid along the corner's bisector (equal distances to its two edges' lips) to
    #   2 D from both, and on while the outline's rounded corner is nearer; between corners, heads along each edge's
    #   head line at most 3.4 D apart (at least 3 D, the FAA's least rivet spacing: two corners nearer than that merge
    #   into one head at the middle of their edge's stretch)
    land = SCREW_LAND
    to_uw_ = lambda UV: np.column_stack([UV[:, 0], UV[:, 1] * wh(UV[:, 0])])
    Xof = lambda UV: chart.from_uw(to_uw_(np.atleast_2d(np.asarray(UV, np.float64))))
    out_arcs = [chart.from_uw(a) for a in _outline_arcs(u0, u1, wh, rc, step=EDGE_STEP)]
    # THE PLATE'S METRIC (the lead's C3 call 3): the inset is measured ON THE PLATE, where the heads and the lips are:
    # every edge's polyline and the outline's arcs raised exactly to the plate's top (plate_top: the block-out's closest
    # point raised plate_t, where surface_plan puts the op's seams and heads), the heads through their plate's raster
    # of it. On the low the same 2 D read 1 / (1 + h k) shorter (the C2 check: 2.007-2.054 D on the mantle's plate)
    prog_b = getattr(lift, 'prog', None) if lift is not None else None
    up_ = lambda X: plate_top(prog_b, X, plate_t, density)
    out_arcs_P = [up_(a) for a in out_arcs]
    geo = []
    for p in plates:
        p['fastened'] = None
        vv_ = np.linspace(p['va'], p['vb'], EDGE_N)
        uu_ = np.linspace(p['ua'], p['ub'], EDGE_N)
        edge = dict(u0=Xof(np.column_stack([np.full(EDGE_N, p['ua']), vv_])),
                    u1=Xof(np.column_stack([np.full(EDGE_N, p['ub']), vv_])),
                    v0=Xof(np.column_stack([uu_, np.full(EDGE_N, p['va'])])),
                    v1=Xof(np.column_stack([uu_, np.full(EDGE_N, p['vb'])])))
        # each edge's lip: half a seam inside a seam's centreline; none where the edge is the region's outline
        lip = dict(u0=0.0 if abs(p['ua'] - u0) < 1e-12 else 0.5 * seam_w,
                   u1=0.0 if abs(p['ub'] - u1) < 1e-12 else 0.5 * seam_w,
                   v0=0.0 if p['va'] <= -1.0 + 1e-12 else 0.5 * seam_w,
                   v1=0.0 if p['vb'] >= 1.0 - 1e-12 else 0.5 * seam_w)
        p['Lw'] = 0.5 * (plen(edge['u0']) + plen(edge['u1']))      # its extent round (its ring edges' length)
        p['Lu'] = 0.5 * (plen(edge['v0']) + plen(edge['v1']))      # its extent along (its meridian edges' length)
        # the edges resampled at EDGE_STEP, as the outline is: two polylines of one curve (a plate's edge on the region's
        # outline and the outline itself) then differ by their chords' sag, ~1e-8 m (at 0.5 mm steps ~0.1 um: enough to
        # break an exact inset)
        for e, Le in (('u0', plen(edge['u0'])), ('u1', plen(edge['u1'])), ('v0', plen(edge['v0'])),
                      ('v1', plen(edge['v1']))):
            ne_ = max(EDGE_N, int(math.ceil(Le / EDGE_STEP)) + 1)
            t_ = np.linspace(0.0, 1.0, ne_)
            if e in ('u0', 'u1'):
                edge[e] = Xof(np.column_stack([np.full(ne_, p['ua'] if e == 'u0' else p['ub']),
                                               p['va'] + t_ * (p['vb'] - p['va'])]))
            else:
                edge[e] = Xof(np.column_stack([p['ua'] + t_ * (p['ub'] - p['ua']),
                                               np.full(ne_, p['va'] if e == 'v0' else p['vb'])]))
        gu_p = float(chart.tangents(p['centre_uw'][None])[3][0])
        geo.append(dict(edge=edge, edgeP={e: up_(X_) for e, X_ in edge.items()}, lip=lip, gu=gu_p,
                        ras=_plate_raster(p, Xof, up_, wh, gu_p)))

    def plate_heads(p, g, D):
        """one plate's heads at diameter D: [dict(plate, end, uv, X (on the low), P (on the plate's top), pitch_D,
        edge_clear)], or raises cyborg.layout. Every distance ON THE PLATE (the lead's C3 call 3): a head's top point
        (its plate's raster) to each edge's raised polyline, less the edge's lip (a seam's half width: the lip is on the
        plate, the seam carved there)"""
        edgeP, lip, gu, ras = g['edgeP'], g['lip'], g['gu'], g['ras']
        inset = float(spec['inset_D']) * D
        rng_p = np.random.default_rng([seed_, 7907, p['index']])   # the plate's own draws: the same at every D
        PR = lambda UV: _raster_at(ras, UV)
        dist = lambda P_, e: _polyline_dist(P_, [edgeP[e]]) - lip[e]

        def clear(P_, own=()):
            """the least lip distance of the edges not in own, and of the outline's corner arcs (lip 0: everywhere else
            the outline IS a plate's edge, measured as that edge; counted again it would read as the own edge), all
            on the plate"""
            return np.min(np.stack([dist(P_, e) for e in edgeP if e not in own] + [_polyline_dist(P_, out_arcs_P)]),
                          axis=0)

        def settle(UV, e):
            """points moved along e's axis (u for a ring edge, v for a meridian) to EXACTLY the inset from e's lip"""
            UV = np.array(UV, np.float64).reshape(-1, 2).copy()
            k_ = 0 if e in ('u0', 'u1') else 1
            sg = 1.0 if e in ('u0', 'v0') else -1.0
            for _ in range(50):
                d0 = dist(PR(UV), e) - inset
                if np.all(np.abs(d0) < EXACT):
                    break
                hs = np.full(len(UV), 2e-5 / gu) if k_ == 0 else 2e-5 / wh(UV[:, 0])
                UVp = UV.copy()
                UVp[:, k_] += sg * hs
                rate = np.maximum((dist(PR(UVp), e) - inset - d0) / hs, 0.2 * (gu if k_ == 0 else wh(UV[:, 0])))
                # (a step at most 1 mm on the surface: the distance's slope is about 1 there, never 0)
                cap = 1.0e-3 / (gu if k_ == 0 else wh(UV[:, 0]))
                UV[:, k_] -= sg * np.clip(d0 / rate, -cap, cap)
            return UV

        def line(e, lam):
            """e's head line at parameters lam (0..1 along the edge): settled points (UV, their points on the plate)"""
            lam = np.atleast_1d(np.asarray(lam, np.float64))
            if e in ('u0', 'u1'):
                uq = p['ua'] + (inset + lip['u0']) / gu if e == 'u0' else p['ub'] - (inset + lip['u1']) / gu
                UV = np.column_stack([np.full(len(lam), uq), p['va'] + lam * (p['vb'] - p['va'])])
            else:
                uq = p['ua'] + lam * (p['ub'] - p['ua'])
                vq = (p['va'] + (inset + lip['v0']) / wh(uq)) if e == 'v0' else (p['vb'] - (inset + lip['v1']) / wh(uq))
                UV = np.column_stack([uq, vq])
            UV = settle(UV, e)
            return UV, PR(UV)

        def stretch(e):
            """the stretch of e's head line that keeps 2 D from every other lip and the outline: (lam_a, lam_b), its
            ends ROOTS of that clearance (Illinois' regula falsi, kept on the feasible side, to EXACT); None if none"""
            lam = np.linspace(0.0, 1.0, 65)
            c = clear(line(e, lam)[1], (e,)) - inset
            ok = c >= 0.0
            if not ok.any():
                return None
            runs, k = [], 0
            while k < len(ok):
                if ok[k]:
                    j = k
                    while j + 1 < len(ok) and ok[j + 1]:
                        j += 1
                    runs.append((k, j))
                    k = j + 1
                else:
                    k += 1
            ka, kb = max(runs, key=lambda r_: r_[1] - r_[0])

            def root(k_in, k_out):
                a, fa, b, fb = lam[k_in], c[k_in], lam[k_out], c[k_out]
                ta, last = fa, 0
                for _ in range(120):
                    if ta < EXACT or abs(b - a) < 1e-15:
                        break
                    m = (a * fb - b * fa) / (fb - fa)
                    if not min(a, b) < m < max(a, b):
                        m = 0.5 * (a + b)
                    cm = float(clear(line(e, m)[1], (e,))[0] - inset)
                    if cm >= 0.0:
                        if last == 1:
                            fb *= 0.5
                        a, fa, ta, last = m, cm, cm, 1
                    else:
                        if last == -1:
                            fa *= 0.5
                        b, fb, last = m, cm, -1
                return float(a)
            return (0.0 if ka == 0 else root(ka, ka - 1)), (1.0 if kb == len(lam) - 1 else root(kb, kb + 1))

        def along(e, la, lb, n=41):
            """e's head line between lam la and lb: (lam samples, the cumulative arc length on the plate: pitches are
            physical sizes, as the inset is)"""
            ls = np.linspace(la, lb, n)
            X = line(e, ls)[1]
            return ls, np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))])
        if spec['fasteners'] == 'ends':
            plo_d, phi_d = float(spec['pitch_D'][0]), float(spec['pitch_D'][1])
            n = int(rng_p.integers(int(spec['heads'][0]), int(spec['heads'][1]) + 1))
            na = (n + 1) // 2 if rng_p.random() < 0.5 else n // 2
            draws = (float(rng_p.uniform(plo_d, phi_d)), float(rng_p.uniform(plo_d, phi_d)))
            order = ((('v0', 'v1'), p['Lw'], p['Lu']), (('u0', 'u1'), p['Lu'], p['Lw']))
            order = order if p['Lw'] > p['Lu'] else order[::-1]
            fits = [es for es, sp_, el_ in order if sp_ - 2 * inset - lip[es[0]] - lip[es[1]] >= plo_d * D and
                    el_ >= 2 * inset]
            best, why = None, []
            for es in fits:
                kept, note = [], []
                for e, ne, pd in zip(es, (na, n - na), draws):
                    st = stretch(e)
                    if st is None or ne <= 0:
                        note.append(f'{e} no stretch 2 D from every other lip')
                        continue
                    ls, sc = along(e, *st)
                    span = float(sc[-1])
                    note.append(f'{e} stretch {span*1e3:.2f} mm')
                    ne = min(ne, 1 + int(math.floor(span / (plo_d * D) + 1e-9)))
                    if ne == 1:
                        lam_h, pitch = np.array([float(np.interp(0.5 * span, sc, ls))]), None
                    else:
                        pitch = min(pd, span / ((ne - 1) * D))
                        s_h = 0.5 * span + (np.arange(ne) - 0.5 * (ne - 1)) * pitch * D
                        lam_h = np.interp(s_h, sc, ls)
                        if s_h[0] <= 1e-12:                 # a group that fills its stretch: its outer heads exactly
                            lam_h[0] = st[0]                 # on the stretch's ends, 2 D from the side lips
                        if s_h[-1] >= span - 1e-12:
                            lam_h[-1] = st[1]
                    UVh, Ph = line(e, lam_h)
                    Xh = Xof(UVh)
                    kept += [dict(plate=p['index'], end=e, uv=UVh[q], X=Xh[q], P=Ph[q], pitch_D=pitch)
                             for q in range(len(UVh))]
                why.append(f'{"/".join(es)}: kept {len(kept)} ({", ".join(note)})')
                if best is None or len(kept) > len(best[1]):
                    best = (es, kept)
                if len(kept) >= int(spec['heads'][0]):
                    break
            if best is None or len(best[1]) < int(spec['heads'][0]):
                raise CyborgError('cyborg.layout', f'plate {p["index"]} (row {p["row"]}, {p["Lw"]*1e3:.1f} x '
                                                   f'{p["Lu"]*1e3:.1f} mm) holds {len(best[1]) if best else 0} heads of '
                                                   f'{D*1e3:.2f} mm at its ends 2 D from every lip; \'ends\' wants '
                                                   f'{spec["heads"][0]}-{spec["heads"][1]} '
                                                   f'({" | ".join(why) or "no pair of ends fits"})')
            p['fastened'] = 'meridian edges' if best[0][0] == 'v0' else 'ring edges'
            out = best[1]
        else:
            pitch = float(spec['pitch_D'][0] if isinstance(spec['pitch_D'], (list, tuple)) else spec['pitch_D'])
            p['fastened'] = 'every edge'

            def corner(eu, ev):
                """the corner head: on the bisector of eu and ev (equal distances to their lips), the inset from both,
                or further in while another lip or the outline is nearer (bisection on that distance, to EXACT)"""
                F = lambda UV, sig: np.array([dist(PR(UV), eu)[0], dist(PR(UV), ev)[0]]) - sig

                def at(sig, UV):
                    UV = np.array(UV, np.float64).reshape(1, 2).copy()
                    for _ in range(50):
                        f0 = F(UV, sig)
                        if np.all(np.abs(f0) < EXACT):
                            break
                        hu, hv = 2e-5 / gu, 2e-5 / float(wh(UV[0, 0]))
                        Jm = np.column_stack([(F(UV + np.array([[hu, 0.0]]), sig) - f0) / hu,
                                              (F(UV + np.array([[0.0, hv]]), sig) - f0) / hv])
                        UV = UV + np.linalg.solve(Jm, -f0)[None]
                    return UV
                ue = p['ua'] + (inset + lip['u0']) / gu if eu == 'u0' else p['ub'] - (inset + lip['u1']) / gu
                ve = (p['va'] + (inset + lip['v0']) / wh(ue)) if ev == 'v0' else (p['vb'] - (inset + lip['v1']) / wh(ue))
                UV = at(inset, [ue, ve])
                c_of = lambda UV_: float(clear(PR(UV_), (eu, ev))[0] - inset)
                if c_of(UV) >= 0.0:
                    return UV[0]
                lo_s, hi_s, UVf = inset, inset, None
                for _ in range(24):
                    hi_s += 0.25 * inset
                    UVf = at(hi_s, UV)
                    if c_of(UVf) >= 0.0:
                        break
                else:
                    return None
                for _ in range(80):
                    mid = 0.5 * (lo_s + hi_s)
                    UVm = at(mid, UVf)
                    cm = c_of(UVm)
                    if cm >= 0.0:
                        hi_s, UVf = mid, UVm
                        if cm < EXACT:
                            break
                    else:
                        lo_s = mid
                return UVf[0]
            C = {}
            for eu in ('u0', 'u1'):
                for ev in ('v0', 'v1'):
                    uvc = corner(eu, ev)
                    if uvc is not None:
                        C[(eu, ev)] = uvc
            Xc = {k: PR(v[None])[0] for k, v in C.items()}
            heads = [dict(end=f'{k[0]}+{k[1]}', uv=v) for k, v in C.items()]
            # an edge whose two corners stand nearer than 3 D: one head at the middle of its stretch instead
            for e, pair in (('u0', (('u0', 'v0'), ('u0', 'v1'))), ('u1', (('u1', 'v0'), ('u1', 'v1'))),
                            ('v0', (('u0', 'v0'), ('u1', 'v0'))), ('v1', (('u0', 'v1'), ('u1', 'v1')))):
                if all(k in Xc for k in pair) and np.linalg.norm(Xc[pair[0]] - Xc[pair[1]]) < RIVET_MIN_D * D:
                    names = {f'{k[0]}+{k[1]}' for k in pair}
                    heads = [h for h in heads if h['end'] not in names]
                    st = stretch(e)
                    if st is not None:
                        ls, sc = along(e, *st)
                        heads.append(dict(end=e, uv=line(e, float(np.interp(0.5 * sc[-1], sc, ls)))[0][0]))
            # between each edge's end heads: heads along its head line at most `pitch` D apart (at least 3 D)
            H0 = list(heads)
            X0 = PR(np.array([h['uv'] for h in H0])) if H0 else np.zeros((0, 3))
            for e in ('u0', 'u1', 'v0', 'v1'):
                if len(H0) < 2:
                    break
                ls = np.linspace(0.0, 1.0, 129)
                Xl = line(e, ls)[1]
                k_end = [int(np.argmin(np.linalg.norm(X0 - q, axis=1))) for q in (Xl[0], Xl[-1])]
                if k_end[0] == k_end[1]:
                    continue
                lam_e = sorted(float(ls[int(np.argmin(np.linalg.norm(Xl - X0[k], axis=1)))]) for k in k_end)
                ls2, sc = along(e, lam_e[0], lam_e[1])
                span = float(sc[-1])
                m = max(1, int(math.ceil(span / (pitch * D) - 1e-9)))
                if m > 1 and span / m < RIVET_MIN_D * D:
                    m -= 1
                if m > 1:
                    UVh = line(e, np.interp(span * np.arange(1, m) / m, sc, ls2))[0]
                    heads += [dict(end=e, uv=UVh[q]) for q in range(len(UVh))]
            out = [dict(plate=p['index'], end=h['end'], uv=np.asarray(h['uv'], np.float64), X=Xof(h['uv'])[0],
                        P=PR(np.asarray(h['uv'], np.float64)[None])[0], pitch_D=pitch) for h in heads]
        # every head: exactly 2 D from its own edge, at least 2 D from every lip and the outline, ON THE PLATE (the
        # solve's check)
        for h in out:
            h['edge_clear'] = float(clear(h['P'][None])[0])
            if h['edge_clear'] < inset - 1e-7:
                raise CyborgError('cyborg.layout', f'plate {p["index"]}: a {h["end"]} head stands '
                                                   f'{h["edge_clear"] / D:.5f} D from a lip (the 2 D inset solve failed)')
        return out
    def polish(g, hs, D):
        """one plate's heads moved by Newton on EXACT plate points (plate_top of the chart's own point at each head's
        (u, v); the solve above reads the plate's raster, which rounds the chart's piecewise-linear parameterisation by
        1-5 um): each back to exactly 2 D from its own edge (a corner from both, or on the bisector), and from every
        other lip it touches; in place, the heads' X, P and edge_clear recomputed"""
        if not hs:
            return
        edgeP, lip, gu = g['edgeP'], g['lip'], g['gu']
        inset = float(spec['inset_D']) * D
        names = list(edgeP) + ['arcs']
        Pex = lambda UV: up_(Xof(UV))

        def dists(P_):
            return np.column_stack([_polyline_dist(P_, [edgeP[e]]) - lip[e] for e in edgeP] +
                                   [_polyline_dist(P_, out_arcs_P)])
        UV = np.array([h['uv'] for h in hs], np.float64)
        d0 = dists(np.array([h['P'] for h in hs]))
        eqs = []
        for k, h in enumerate(hs):
            o = [names.index(e) for e in h['end'].split('+')]
            near = [i for i in np.argsort(d0[k]) if i not in o and abs(d0[k, i] - inset) < 1e-6]
            if len(o) == 2 and abs(d0[k, o[0]] - inset) >= 1e-6 and near:
                eqs.append([('eq', o[0], o[1]), ('d', near[0])])         # a corner pushed in along its bisector
            elif len(o) == 2:
                eqs.append([('d', o[0]), ('d', o[1])])                   # a corner: 2 D from both of its edges
            else:
                eqs.append([('d', o[0])] + ([('d', near[0])] if near else []))
        for _pass in range(3):
            for _ in range(16):
                hu = np.full(len(UV), 2e-5 / gu)
                hv = 2e-5 / wh(UV[:, 0])
                dd = [dists(Pex(UV)), dists(Pex(UV + np.column_stack([hu, 0 * hu]))),
                      dists(Pex(UV + np.column_stack([0 * hv, hv])))]
                worst = 0.0
                for k in range(len(UV)):
                    fk = lambda d_: np.array([(d_[k, q[1]] - inset) if q[0] == 'd' else (d_[k, q[1]] - d_[k, q[2]])
                                              for q in eqs[k]])
                    f0 = fk(dd[0])
                    worst = max(worst, float(np.abs(f0).max()))
                    if np.abs(f0).max() < EXACT:
                        continue
                    Ju, Jv = (fk(dd[1]) - f0) / hu[k], (fk(dd[2]) - f0) / hv[k]
                    if len(f0) == 2:
                        step = np.linalg.solve(np.column_stack([Ju, Jv]), -f0)
                    else:                                                # along its own edge's axis, as settle does
                        ax = 0 if hs[k]['end'] in ('u0', 'u1') else 1
                        r_ = (Ju if ax == 0 else Jv)[0]
                        step = np.zeros(2)
                        step[ax] = -f0[0] / r_ if abs(r_) > 1e-12 else 0.0
                    UV[k] += step
                if worst < EXACT:
                    break
            # a head the polish moved under 2 D from another lip: that lip joins its constraints, and again
            dn = dists(Pex(UV))
            again = False
            for k in range(len(UV)):
                used = {q[1] for q in eqs[k]} | {q[2] for q in eqs[k] if q[0] == 'eq'}
                bad = [i for i in np.argsort(dn[k]) if i not in used and dn[k, i] < inset - 1e-9]
                if bad and len(eqs[k]) < 2:
                    eqs[k] = eqs[k] + [('d', bad[0])]
                    again = True
            if not again:
                break
        dn = dists(Pex(UV))
        # A HEAD HELD BY THREE LIPS (the lead's C3b call; the default look's mantle seeds 0 and 14 refused here): a corner
        # plate's head on its outline end binds its own edge, the outline's side AND the corner arc at 2 D at once (a
        # corner radius of 2 D in u puts the arc 2 D from a head 2 D in from both straight edges), and the two equations
        # above hold only two of them: the third ended a hair under 2 D (1.3 / 0.6 um on those seeds). Such an 'ends'
        # head SLIDES along its own head line (its own edge's distance held EXACT at 2 D by a secant across the edge at
        # every step) away from the lips that bind it, to the root where the least of every other lip and the outline
        # stands exactly 2 D (bisection, 1e-10 m): the stretch's end that stretch() finds on the raster, found here on
        # exact plate points. Only a head the check below would REFUSE is touched (the same 0.1 um), and its new place is
        # kept only where it stands farther from its nearest lip than the polish left it: every layout that passed is
        # laid again bit for bit (c01 / c02 / C3's seed 5 on both looks); a riveted corner keeps the bisector solve
        def settle_own(uv, oi, ax):
            """uv moved along axis ax until its distance to lip oi is exactly the inset (secant on exact points)"""
            uv = uv.copy()
            for _ in range(40):
                d0 = dists(Pex(uv[None]))[0][oi] - inset
                if abs(d0) < EXACT:
                    break
                h = 2e-6 / (gu if ax == 0 else float(wh(uv[0])))
                uvh = uv.copy()
                uvh[ax] += h
                slope = (dists(Pex(uvh[None]))[0][oi] - inset - d0) / h
                if abs(slope) < 1e-12:
                    break
                uv[ax] -= d0 / slope
            return uv
        for k in [k for k in range(len(UV)) if dn[k].min() < inset - 1e-7]:
            o = [names.index(e) for e in hs[k]['end'].split('+')]
            if len(o) != 1:
                continue
            oi = o[0]
            ax = 0 if names[oi] in ('u0', 'u1') else 1           # the axis that settles the own edge
            sl_ax = 1 - ax                                      # the head line's own direction
            others = [i for i in range(len(names)) if i != oi]
            unit_ = (1.0 / float(wh(UV[k][0]))) if sl_ax == 1 else (1.0 / gu)
            g = lambda tt: (lambda uv_: (float(min(dists(Pex(uv_[None]))[0][others])) - inset, uv_))(
                settle_own(UV[k] + tt * unit_ * np.eye(2)[sl_ax], oi, ax))
            g0, _ = g(0.0)
            dlt = 0.02 * D
            gp, gm = g(dlt)[0], g(-dlt)[0]
            sg_ = 1.0 if gp >= gm else -1.0                       # away from the binding lips
            lo_t, hi_t = 0.0, None
            for mul in (1, 2, 4, 8, 16, 25):
                if g(sg_ * mul * dlt)[0] >= 0.0:
                    hi_t = sg_ * mul * dlt
                    break
                lo_t = sg_ * mul * dlt
            if hi_t is None:
                continue
            for _ in range(60):
                mid = 0.5 * (lo_t + hi_t)
                gm_, _ = g(mid)
                if gm_ >= 0.0:
                    hi_t = mid
                else:
                    lo_t = mid
                if abs(hi_t - lo_t) < 1e-10:
                    break
            _, uv_new = g(hi_t)
            if dists(Pex(uv_new[None]))[0].min() > dn[k].min():
                UV[k] = uv_new
        X_, P_ = Xof(UV), Pex(UV)
        dn = dists(P_)
        for k, h in enumerate(hs):
            h['uv'], h['X'], h['P'] = UV[k].copy(), X_[k], P_[k]
            h['edge_clear'] = float(dn[k].min())
            if h['edge_clear'] < inset - 1e-7:
                raise CyborgError('cyborg.layout', f'plate {h["plate"]}: a {h["end"]} head stands '
                                                   f'{h["edge_clear"] / D:.5f} D from a lip on the plate after the '
                                                   'exact polish (the 2 D inset solve failed)')
    fasteners, D_lay, head_tx = [], None, None
    # the acceptance band of the heads as baked (the lead's C3 call 2, widened at C3b) and the target the spread is centred
    # on, at this row's fastener_tx
    band_tx = (HEAD_TX_BAND[0] * ftx / 10.0, HEAD_TX_BAND[1] * ftx / 10.0)
    target_tx = math.sqrt((HEAD_TX_C3[0] * ftx / 10.0) * (HEAD_TX_C3[1] * ftx / 10.0))    # (C3's own arithmetic, bit for bit)
    if fastened:
        D = D_plan
        try:
            # ONE PHYSICAL HEAD SIZE, ITS SPREAD CENTRED IN THE BAND (the lead's C3 call 2): the heads placed at D, each
            # read AS BAKED (its rim through the UV map, UVDensity.head_texels, over the bake's growth), D scaled until
            # the spread's geometric middle sqrt(min x max) sits on the band's (10.13 texels at fastener_tx 10). A head's
            # place moves with D (2 D in), so the extremes can step between heads: late updates are damped, and the
            # solve ends on its best placement, the heads placed AT the D reported (the 2 D inset exact for it)
            best = None
            for it in range(30):
                heads = [h for p, g in zip(plates, geo) for h in plate_heads(p, g, D)]
                XH = np.array([h['X'] for h in heads])
                NH = chart.tangents(to_uw_(np.array([h['uv'] for h in heads])))[2]
                txi = density.head_texels(XH, NH, D)[0] / head_grow(XH)
                cen = math.sqrt(float(txi.min()) * float(txi.max()))
                err = abs(cen / target_tx - 1.0)
                if best is None or err < best[0]:
                    best = (err, D, heads, XH)
                if err <= HEAD_CENTRE_TOL:
                    break
                D *= (target_tx / cen) if it < 8 else math.sqrt(target_tx / cen)
            _, D, heads, XH = best
            for p, g in zip(plates, geo):                         # the inset made exact on the plate itself
                polish(g, [h for h in heads if h['plate'] == p['index']], D)
            XH = np.array([h['X'] for h in heads])
        except CyborgError as e:
            # heads (or seams) grown past the sizes the plates were cut for: cut them again for the sizes found
            depth = 0 if _plan is None else int(_plan[2])
            if e.code == 'cyborg.layout' and depth < 2 and (D > D_plan * (1.0 + 1e-9) or
                                                            0.5 * seam_w > lip_est * (1.0 + 1e-9)):
                return panel_layout(chart, density, row, base, region, seed, voxel, joints_s, lift, region_spec,
                                    _plan=(max(D, D_plan), max(0.5 * seam_w, lip_est), depth + 1))
            raise
        D_lay = D
        HUV = np.array([h['uv'] for h in heads])
        UW = to_uw_(HUV)
        _, _, FN, _ = chart.tangents(UW)
        grow = head_grow(XH)
        tx = density.head_texels(XH, FN, D_lay)[0] / grow
        dseam = _polyline_dist(XH, [sm['p'] for sm in seams]) if seams else np.full(len(XH), np.inf)
        for k, h in enumerate(heads):
            f = dict(plate=h['plate'], end=h['end'], uw=UW[k].copy(), D=D_lay, grow=float(grow[k]), pitch_D=h['pitch_D'],
                     edge_clear=h['edge_clear'], p=XH[k], p_plate=np.asarray(h['P'], np.float64), normal=FN[k],
                     tx=float(tx[k]), seam_clear=float(dseam[k] - D_lay / 2 - seam_w / 2))
            if f['seam_clear'] < land - 1e-6:
                raise CyborgError('cyborg.layout', f'a fastener on plate {f["plate"]} stands {f["seam_clear"]*1e3:.2f} '
                                                   f'mm from a seam (SCREW_LAND {land*1e3:.1f} mm)')
            fasteners.append(f)
        head_tx = (float(tx.min()), float(np.median(tx)), float(tx.max()))
        if head_tx[0] < band_tx[0] - 1e-9 or head_tx[2] > band_tx[1] + 1e-9:
            raise CyborgError('cyborg.layout', f'{region} on chart {chart.name}: one head size ({D_lay*1e3:.3f} mm) reads '
                                               f'{head_tx[0]:.3f}-{head_tx[2]:.3f} texels as baked (x'
                                               f'{head_tx[2]/head_tx[0]:.4f}), outside the acceptance band '
                                               f'{band_tx[0]:g}-{band_tx[1]:g} (x{band_tx[1]/band_tx[0]:.4f}): the '
                                               'densities under its heads differ more than one physical size can hold')
    for p in plates:
        p['heads'] = sum(1 for f in fasteners if f['plate'] == p['index'])
        p['D'] = D_lay
    # ------------------------------------------------------------------------- stats
    seam_len_uw = float(sum(np.linalg.norm(np.diff(sm['uw'], axis=0), axis=1).sum() for sm in seams))
    seam_len_3d = float(sum(np.linalg.norm(np.diff(sm['p'], axis=0), axis=1).sum() for sm in seams))
    area = float(sum(p['area'] for p in plates))
    in_u = (u_s >= u0 - 1e-9) & (u_s <= u1 + 1e-9)
    stats = dict(plates=len(plates), rows=len(rows), area_cm2=area * 1e4, seam_len_mm=seam_len_3d * 1e3,
                 seam_len_chart_mm=seam_len_uw * 1e3, outline_len_mm=float(np.linalg.norm(np.diff(out_p, axis=0),
                                                                                          axis=1).sum()) * 1e3,
                 fasteners=len(fasteners), fasteners_per_100cm2=len(fasteners) / max(area * 1e4 / 100.0, 1e-9),
                 heads_per_plate=sorted(p['heads'] for p in plates),
                 d_eq_R=[round(p['d_eq_R'], 3) for p in plates], d_eq_mm=[round(p['d_eq'] * 1e3, 1) for p in plates],
                 R_mm=(float(Rl_s[in_u].min()) * 1e3, float(np.median(Rl_s[in_u])) * 1e3, float(Rl_s[in_u].max()) * 1e3),
                 wh_mm=(float(whs[in_u].min()) * 1e3, float(np.median(whs[in_u])) * 1e3, float(whs[in_u].max()) * 1e3),
                 seam_px_across=(float(px_across.min()) if len(px_across) else 0.0,
                                 float(np.median(px_across)) if len(px_across) else 0.0),
                 # ONE head size per layout (the lead's call 2): its diameter and what its heads read as baked
                 D_mm=(D_lay * 1e3, D_lay * 1e3) if D_lay else (0.0, 0.0),
                 head_tx=head_tx,
                 # its acceptance band and the spread's geometric middle, solved onto the band's (the lead's C3 call 2)
                 head_tx_band=band_tx,
                 head_tx_centre=(math.sqrt(head_tx[0] * head_tx[2]) if head_tx else 0.0),
                 # the bake's view: how much wider than on the low each seam / head is laid out (1 + h k, THE BAKE'S VIEW)
                 seam_grow=(float(seam_grow.min()), float(seam_grow.max())) if len(seam_grow) else (1.0, 1.0),
                 head_grow=((min(f['grow'] for f in fasteners), max(f['grow'] for f in fasteners)) if fasteners else
                            (1.0, 1.0)),
                 lift=lift is not None,
                 accent_plates=sum(1 for p in plates if p['paint'] == 'accent'),
                 unfastened=[p['index'] for p in plates if spec['fasteners'] != 'none' and not p['heads']],
                 bare=[(round(a, 4), round(b, 4)) for a, b in bare], stagger_short=stagger_short)
    params = dict(base=base, region=region, chart=chart.name, set=R['set'], stacked=R['stacked'],
                  arms=spec.get('arms'), low_regions=allowed, s=(s0, s1), s_plated=(u0 / L, u1 / L),
                  theta_deg=float(spec['theta_deg']), rows_rule=SL.JOINT_ROWS if joint_rows else len(rows),
                  plate_R=(plo, phi), seam_tx=spec['seam_tx'], seams=spec['seams'], seam_w=seam_w,
                  seam_depth=seam_depth, capsule_r=0.5 * seam_w, fastener_tx=float(spec['fastener_tx']), D=D_lay,
                  fasteners=spec['fasteners'], heads=tuple(spec['heads']), pitch_D=spec['pitch_D'],
                  inset_D=float(spec['inset_D']), screw_land=land, voxel=voxel, corner=rc, rim_reach=rim_reach,
                  plate_t=plate_t, head_h_D=0.31,
                  junction=dict(kind=spec['junction'], proud=(1.2e-3, 1.3e-3), crease=(0.8e-3, 0.9e-3),
                                ramp=(3.0e-3, 3.2e-3), gasket='seated in the crease (junction_design)',
                                scar=spec['scar']),
                  lip_round=0.5 * seam_depth, finish=spec['finish'], paint=spec['paint'],
                  paint_type=spec['paint_type'], accent=spec.get('accent'),
                  fastener_finish=spec['fastener_finish'], glow_seams=bool(spec['glow_seams']),
                  glow_finish=spec['glow_finish'], seed=seed_)
    return dict(params=params, region=dict(u0=u0, u1=u1, u=u_s, wh=whs, R=Rl_s, rows=rows), plates=plates, seams=seams,
                outline=dict(uw=outline_uw, p=out_p), fasteners=fasteners, stats=stats, mount_plates=[])


def _outline_arcs(u0, u1, wh, rc, step=0.0005):
    """the outline's four corner arcs in (u, w), in the outline's order: (u0, +w), (u1, +w), (u1, -w), (u0, -w). Each is
    EXACTLY the zero set of _rounded_inside there: (rc - a)^2 + (rc - b)^2 = rc^2, a the distance in u from the
    region's end, b = wh(u) - |w| (so on a tapering region the arc follows wh, as the inside test does)"""
    n = max(12, int(math.ceil(0.5 * math.pi * rc / step)) + 1)
    t = np.linspace(0.0, 0.5 * math.pi, n)
    a, b = rc * (1.0 - np.sin(t)), rc * (1.0 - np.cos(t))         # (rc, 0) on the w side .. (0, rc) on the u end
    whv = lambda u: np.array([float(wh(x)) for x in np.atleast_1d(u)])
    out = []
    for ue, sg_u, sg_w, rev in ((u0, 1.0, 1.0, True), (u1, -1.0, 1.0, False), (u1, -1.0, -1.0, True),
                                (u0, 1.0, -1.0, False)):
        u = ue + sg_u * a
        P = np.column_stack([u, sg_w * (whv(u) - b)])
        out.append(P[::-1] if rev else P)
    return out


def _outline(u0, u1, wh, rc, step=0.0005):
    """the region's outline in (u, w), closed: its four edges (u0, u1 and w = +-wh(u)) joined by the corner arcs,
    EXACTLY the zero set of _rounded_inside (the inside test the area table, the seams' clip and the texel raster use);
    every piece sampled at `step`"""
    n_e = lambda a, b: max(2, int(abs(b - a) / step) + 1)
    w0, w1 = float(wh(u0)), float(wh(u1))
    arcs = _outline_arcs(u0, u1, wh, rc, step)
    uu = np.linspace(u0 + rc, u1 - rc, n_e(u0, u1))
    whu = np.array([float(wh(x)) for x in uu])
    # the u0 edge (from -w to +w), the corner, the +w side, the corner, the u1 edge, the corner, the -w side, the corner
    pts = [np.column_stack([np.full(n_e(-w0, w0), u0), np.linspace(-(w0 - rc), w0 - rc, n_e(-w0, w0))]), arcs[0][1:-1],
           np.column_stack([uu, whu]), arcs[1][1:-1],
           np.column_stack([np.full(n_e(-w1, w1), u1), np.linspace(w1 - rc, -(w1 - rc), n_e(-w1, w1))]), arcs[2][1:-1],
           np.column_stack([uu[::-1], -whu[::-1]]), arcs[3][1:-1]]
    P = np.concatenate(pts)
    return np.vstack([P, P[:1]])


def layout_summary(lay):
    """one line per fact, for the logs"""
    p, s = lay['params'], lay['stats']
    heads = (f'ONE size {p["D"]*1e3:.3f} mm, as baked {s["head_tx"][0]:.2f} / {s["head_tx"][1]:.2f} / '
             f'{s["head_tx"][2]:.2f} texels' if p.get('D') else 'none')
    return (f'{p["region"]} on {p["chart"]} ({p["set"]} set{", STACKED: all eight arms" if p["stacked"] else ", unique"}'
            f'): s {p["s_plated"][0]:.3f}-{p["s_plated"][1]:.3f} plated (row s {p["s"][0]:.3f}-{p["s"][1]:.3f}'
            f'{", bare " + str(s["bare"]) if s["bare"] else ""}), |theta| <= {p["theta_deg"]:.0f}; {s["plates"]} plates '
            f'in {s["rows"]} rows ({p["rows_rule"]}), {s["area_cm2"]:.1f} cm2, d_eq/R {min(s["d_eq_R"]):.3f}-'
            f'{max(s["d_eq_R"]):.3f} of {p["plate_R"][0]}-{p["plate_R"][1]} (R {s["R_mm"][1]:.1f} mm); seams '
            f'{p["seam_tx"]} texels = {p["seam_w"]*1e3:.3f} mm wide x {p["seam_depth"]*1e3:.3f} deep, '
            f'{s["seam_len_mm"]:.0f} mm; {s["fasteners"]} fasteners ({p["fasteners"]}, {s["fasteners_per_100cm2"]:.1f} '
            f'per 100 cm2): {heads}' + (f'; FEED: {feed_summary(lay["feed"])}' if lay.get('feed') else ''))


# ============================================================================================ the surface sculpt (C2)
# THE VOXEL HIGH (CYBORG_PLAN §4.2.4, §8 C2; A.2; the lead's C2 brief): a layout raised into the sculpt's SparseSDF
# (forge/voxel.py), on any grid, by this module alone (voxel.py, sdf.py and bake.py stay as they are), after the skin's
# own Plan.apply:
#   1. THE PLATE OP: the junction's cross-section (junction_design) as two 2D PROGRAMS over (d, z): d the signed surface
#      distance of a voxel's FOOT on the UNSCULPTED block-out to the region's outline (+ into the plates), z its height
#      over the block-out. The TROUGH (the carved space over the skin's fall and the crease's floor; carved by smooth
#      max) and the PLATE (the solid under the rolled rim and the flat top t; added by smooth min, its plate's paint id
#      written where it wins: k_apply's rule). Raised off the block-out, the plate is the skin's smooth offset: no
#      papilla prints through it, and inside the trough the skin's sculpt is cut away (it is stretched there).
#   2. SEAMS: capsule chains of radius w/2 centred on the plate's own surface (A.2.1: a round tube, depth w/2), the rim
#      included (a seam runs through the rolled rim down to the gasket), carved with no id (the walls keep their plate's;
#      glow_seams: the cyb_glow inlay instead), their lips rounded by a smooth max of half the depth (the half-depth
#      chord stays the circle's, which C2 gates; the body's "no knife edge for the mesh step to alias", A.2.2).
#   3. THE GASKET: a capsule chain of radius gasket_r along the outline, seated in the crease (cyb_gasket), its union's
#      fillet k_gasket but never under GRID_ROUND voxels (the bead's foot meets the floor at a sharp concave corner: at
#      0.1 mm, a third of a 0.3 mm voxel, its edge printed the lattice as a saw-tooth along the outline; at 1.2 voxels
#      it is a smooth line and the junction's numbers move by under 0.002 mm, C2's look).
#   4. FASTENERS: STROKE_CYL heads of the layout's ONE size D, 0.31 D proud of the plate (study G [R-rf]), their top edge
#      rounded by a quarter of that but never under GRID_ROUND voxels (a round finer than the grid prints the lattice's
#      facets on the edge), seated 0.3 mm into the plate (cyb_steel).
#   5. THE SCAR: cyb_scar written on the skin voxels at the surface over the skin's fall (a material band, no relief:
#      §3.9 row 3); the 'ridge' junction raises the forge strand's capsule ridge there instead.
# Then a relevel by id (relevel_table: the cyborg voxels restored to true distances from the zero set the op placed;
# growth's crisp facets held as before), KEPT on the op's voxels and a RELEVEL_MARGIN round them (the rest of the band
# handed back as Plan.apply left it: C3), and no smoothing of them (smooth_table: the rim, the lips' round and the heads
# are designed, not smoothed).
# THE BOUND (the lead's Lipschitz probe): each 2D program is a Euclidean distance in (d, z) (|grad| <= 1 there); z is
# the block-out's own distance (|grad z| = 1 for an exact block-out), d the outline's distance from the foot, constant
# along the block-out's normal (grad d square to grad z), and the foot map stretches tangential steps by at most
# 1 / (1 - zeta kappa) at a depth zeta under the surface (kappa the block-out's largest principal curvature): so
# |grad f| <= L = max(1, 1 / (1 - zeta kappa)) with zeta the band's floor. The op stores f / L, a distance bound (as
# sdf.py's PSWEEP divides by its own). On the test ball (a sphere: kappa = 1 / R, its distance exact) L is proven; on a
# smooth-union block-out kappa is measured (x 1.25) and the bound rests on that measure
HEAD_H_D = 0.31          # a head's height over the plate in its diameters (study G's 0.31 D [R-rf])
HEAD_SEAT = 0.3e-3       # a head's foot below the plate's top: the union is solid, never a floating disc
HEAD_K = 0.1e-3          # the head's root fillet
LIP_ROUND = 0.5          # the seam lips' smooth max, in the seam's depths (a half depth: the half-depth chord is exact)
GRID_ROUND = 1.2         # the finest round or edge fillet the op asks of the grid, in voxels (a finer one prints the
                         # lattice's facets along its edge): the heads' top edge, the gasket's union


def smooth_table():
    """(N_IDS,) float32: the sculpt's smoothing weight per material id: growth.smooth_table() with the cyborg ids at 0
    (their shapes are designed; a smoothing pass would soften what C2 gates)"""
    w = np.asarray(GR.smooth_table(), np.float32).copy()
    w[CYBORG_RANGE[0]:CYBORG_RANGE[1] + 1] = 0.0
    return w


def relevel_table():
    """(N_IDS,) float32: the relevel's weight per id: growth.relevel_table() (its crisp crystal families held) with the
    cyborg ids RELEVELLED (1): the op stores distance BOUNDS (f / L, under-reading by up to L, and smooth blends), so its
    voxels are restored to the distance from the zero set it placed. The relevel's interface layer divides by |grad|
    (exact for the plate's flat and the strokes' exact distances) and every cyborg shape is rounded at a voxel or more
    (the rim, the lips' round, the heads' edges), so the zero set holds (C2 measures it after the relevel). Held instead,
    the band over the plates kept the 12 % under-read: an SDF AO darkened it, and the bake's curvature (a Laplacian of
    the field) would read it too"""
    w = np.asarray(GR.relevel_table(), np.float32).copy()
    w[CYBORG_RANGE[0]:CYBORG_RANGE[1] + 1] = 1.0
    return w


def _smin_np(a, b, k):
    """sdf.smin in numpy (float64)"""
    if k <= 0.0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def _smax_np(a, b, k):
    return -_smin_np(-a, -b, k)


def junction_curves(des, n=601):
    """the junction's 2D boundary curves, sampled in (d, z): the rim from its foot to its flat, and the trough's floor
    from the fall's start to d_hi (None for the 'ridge' variant)"""
    r, t = des['rim'], des['t']
    s = np.linspace(0.0, 1.0, n)
    rim = np.column_stack([r['d0'] + r['W'] * s, r['z0'] + (t - r['z0']) * np.sin(0.5 * np.pi * s)])
    tr = des['trough']
    if tr is None:
        return rim, None
    d = np.linspace(tr['d_lo'], tr['d_hi'], n)
    sf = np.clip((d - tr['d_lo']) / (tr['d_c'] - tr['d_lo']), 0.0, 1.0)
    return rim, np.column_stack([d, tr['z'] * (3.0 * sf ** 2 - 2.0 * sf ** 3)])


def trough_top_curve(des, n=601):
    """the trough's TOP (JUNCTION's notes): from the fall's start (d_lo, 0) a smoothstep rise to `top` over `top_w`, then
    flat to d_hi, sampled in (d, z); None for the 'ridge' variant"""
    tr = des['trough']
    if tr is None:
        return None
    d = np.linspace(tr['d_lo'], tr['d_hi'], n)
    s = np.clip((d - tr['d_lo']) / tr['top_w'], 0.0, 1.0)
    return np.column_stack([d, tr['top'] * (3.0 * s ** 2 - 2.0 * s ** 3)])


def junction_top(des, d):
    """the junction's designed surface height z at d (m): the skin, its fall and the crease's floor outside the
    gasket, the rim and the flat top inside it (the gasket bead itself left out)"""
    rim, tro = junction_curves(des)
    d = np.asarray(d, np.float64)
    z = np.interp(d, rim[:, 0], rim[:, 1], left=-np.inf, right=des['t'])
    if tro is not None:
        z = np.maximum(z, np.where((d >= tro[0, 0]) & (d <= tro[-1, 0]), np.interp(d, tro[:, 0], tro[:, 1]), 0.0))
        z = np.where(d < tro[0, 0], 0.0, z)
    else:
        z = np.maximum(z, 0.0)
    return z


def junction_fields(des, d, z, chunk=131072):
    """the junction's two PROGRAMS at (d, z) (m), unscaled: the TROUGH's carved space and the PLATE's solid, each a
    signed Euclidean distance in (d, z) (- inside); the trough +inf for the 'ridge' variant (in chunks: memory)"""
    d = np.asarray(d, np.float64)
    z = np.asarray(z, np.float64)
    if len(d) > chunk:
        parts = [junction_fields(des, d[i:i + chunk], z[i:i + chunk]) for i in range(0, len(d), chunk)]
        return np.concatenate([p_[0] for p_ in parts]), np.concatenate([p_[1] for p_ in parts])
    rim, tro = junction_curves(des)
    r, t = des['rim'], des['t']
    P = np.column_stack([d, z])
    # the plate: d >= d0 and z under the rim / the top; its boundary the wall (a ray down from the rim's foot), the rim,
    # the flat top (a ray on from the rim's end)
    Jd = np.interp(d, rim[:, 0], rim[:, 1], left=-np.inf, right=t)
    inside = (d >= r['d0']) & (z <= Jd)
    dw = np.hypot(d - r['d0'], np.maximum(z - r['z0'], 0.0))
    df = np.hypot(z - t, np.maximum(r['d0'] + r['W'] - d, 0.0))
    fP = np.where(inside, -1.0, 1.0) * np.minimum(np.minimum(dw, df), _polyline_dist(P, [rim]))
    if tro is None:
        return np.full(len(d), np.inf), fP
    tr = des['trough']
    # the trough's carved space: d_lo <= d <= d_hi, z between the fall / the floor and the TOP (trough_top_curve: a
    # smooth rise from the fall's start, never a wall); its boundary the floor curve, the top curve (the two meet,
    # tangent, at (d_lo, 0)) and the segment closing them at d_hi (under the plate's rim)
    top = trough_top_curve(des)
    Zt = np.interp(d, tro[:, 0], tro[:, 1])
    Zp = np.interp(d, top[:, 0], top[:, 1])
    insideT = (d >= tr['d_lo']) & (d <= tr['d_hi']) & (z >= Zt) & (z <= Zp)
    dhi = np.hypot(d - tr['d_hi'], np.maximum(np.maximum(tr['z'] - z, z - tr['top']), 0.0))
    fT = np.where(insideT, -1.0, 1.0) * np.minimum(np.minimum(_polyline_dist(P, [top]), dhi), _polyline_dist(P, [tro]))
    return fT, fP


def _resample(C, step, closed=False):
    """a polyline's points kept about `step` apart along it (its ends kept)"""
    C = np.asarray(C, np.float64)
    if closed:
        C = np.vstack([C, C[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    si = np.linspace(0.0, s[-1], n)
    out = np.column_stack([np.interp(si, s, C[:, k]) for k in range(C.shape[1])])
    return out[:-1] if closed else out


def surface_plan(layout, chart, prog, density, J=None, kappa=None, band=0.003, voxel=0.0003):
    """the C2 sculpt of one layout (the notes above), planned in 3D on the UNSCULPTED block-out `prog` (an sdf.Program:
    the high's block-out, octopus.build_sdf(SPEC)[0] as t10 builds it, or a test ball's ellipsoid). kappa: the
    block-out's largest principal curvature over the region (1/m; a ball: 1 / R exactly, the bound then proven); None
    measures it from the block-out's normals (x 1.25). band / voxel: the grid's (the bound's floor: band + 2 voxels).
    Returns the plan apply_surface reads: the junction's design and the bound L, the outline on the block-out with its
    signed distance, the plate ids, the stroke chains (seams, gasket, heads, ridge), the scar band, the voxels' box,
    the activation spheres (surface_bounds)"""
    P = layout['params']
    des = junction_design(P['plate_t'], P['junction']['kind'], J)

    def onto(X):
        """points of the low onto the block-out: their CLOSEST points (blockout_foot; the lead's C3 call 3: the layout
        solves its 2 D inset on the plate over these same feet, plate_top, so where the op puts a head or a lip is where
        the layout measured it), and the block-out's normals there"""
        X = np.atleast_2d(np.asarray(X, np.float64))
        Q, z = blockout_foot(prog, X)
        if np.any(np.abs(z) > 0.01):
            raise CyborgError('cyborg.chart', f'{int((np.abs(z) > 0.01).sum())} layout points lie over 10 mm off the '
                                              'block-out')
        return Q, np.asarray(prog.normals(Q, h=FOOT_H), np.float64)
    # the outline on the block-out: d = 0 there; the inward side from a plate's centre
    out_b, nb = onto(layout['outline']['p'][:-1])
    out_cl, nb_cl = np.vstack([out_b, out_b[:1]]), np.vstack([nb, nb[:1]])
    cen_b, _ = onto(np.array([p['centre'] for p in layout['plates']]))

    def sdist_raw(F):
        dist, q, seg, tt = _polyline_closest(F, out_cl)
        T = out_cl[seg + 1] - out_cl[seg]
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-30)
        n = nb_cl[seg] * (1.0 - tt)[:, None] + nb_cl[seg + 1] * tt[:, None]
        sg = np.sign(np.einsum('nd,nd->n', F - q, np.cross(n, T)))
        return np.where(sg == 0, 1.0, sg) * dist
    orient = 1.0 if float(np.median(sdist_raw(cen_b))) > 0 else -1.0

    def sdist(F, chunk=65536):
        """the signed surface distance of block-out points F to the outline (+ into the plates; the 3D distance to the
        outline's polyline on the block-out, signed by its local inward side); in chunks (memory)"""
        F = np.atleast_2d(np.asarray(F, np.float64))
        return orient * np.concatenate([sdist_raw(F[i:i + chunk]) for i in range(0, len(F), chunk)] or [np.zeros(0)])
    if np.any(sdist(cen_b) <= 0.0):
        raise CyborgError('cyborg.chart', 'a plate\'s centre reads outside its own outline on the block-out')
    # the plate under a foot: the chart's (u, w) -> the row by u, the plate by v = w / wh(u) (clamped into the region)
    rg = layout['region']
    rows_ub = np.array([r_[1] for r_ in rg['rows']])
    finish = P['finish']
    pid = np.array([CYBORG_ID['cyb_titanium'] if finish in ('titanium', 'anodised') else
                    CYBORG_ID['cyb_paint_accent'] if p['paint'] == 'accent' else CYBORG_ID['cyb_paint']
                    for p in layout['plates']], np.uint8)
    by_row = [[p for p in layout['plates'] if p['row'] == r_] for r_ in range(len(rg['rows']))]

    def plate_of(F, chunk=65536):
        """the plate index under block-out points F (in chunks)"""
        F = np.atleast_2d(F)
        if len(F) > chunk:
            return np.concatenate([plate_of(F[i:i + chunk]) for i in range(0, len(F), chunk)])
        uw = chart.to_uw(F)
        u = np.clip(uw[:, 0], rg['u0'], rg['u1'])
        v = np.clip(uw[:, 1] / np.maximum(np.interp(u, rg['u'], rg['wh']), 1e-9), -1.0, 1.0)
        v = np.where(np.isfinite(v), v, 0.0)
        r_ = np.clip(np.searchsorted(rows_ub, u, side='left'), 0, len(by_row) - 1)
        out = np.zeros(len(u), np.int64)
        for k in range(len(by_row)):
            m = r_ == k
            if m.any():
                vb = np.array([p['vb'] for p in by_row[k]])
                j = np.clip(np.searchsorted(vb, v[m], side='left'), 0, len(vb) - 1)
                out[m] = np.array([p['index'] for p in by_row[k]])[j]
        return out
    # SEAMS: centred on the plate's own surface (its rim included), ending at the gasket's inner edge
    rs = 0.5 * P['seam_w']
    k_lip = LIP_ROUND * P['seam_depth']
    d_end = des['gasket']['r'] + rs
    sA, sB = [], []
    for sm in layout['seams']:
        Q, Nq = onto(sm['p'])
        ds = sdist(Q)
        keep = ds >= d_end
        if keep.sum() < 2:
            continue
        C = Q + junction_top(des, ds)[:, None] * Nq
        C = C[keep]
        sA.append(C[:-1])
        sB.append(C[1:])
    seams = (np.concatenate(sA), np.concatenate(sB)) if sA else (np.zeros((0, 3)), np.zeros((0, 3)))
    # THE GASKET: the outline at the bead's centre height, a closed chain about 0.5 mm per capsule
    g = des['gasket']
    Cg = _resample(out_b + g['z'] * nb, 0.5e-3, closed=True)
    gasket = (Cg, np.roll(Cg, -1, axis=0))
    k_gasket = max(des['J']['k_gasket'], GRID_ROUND * voxel)
    # FASTENERS: on the plate's top (its local height: the flat, the rim's last tenths at most)
    D = P.get('D')
    heads = None
    if layout['fasteners']:
        Fp = np.array([f['p'] for f in layout['fasteners']])
        Q, Nq = onto(Fp)
        dq = sdist(Q)
        C = Q + junction_top(des, dq)[:, None] * Nq
        hh = HEAD_H_D * D
        heads = dict(A=C - HEAD_SEAT * Nq, B=C + hh * Nq, ra=0.5 * D,
                     rb=min(max(0.25 * hh, GRID_ROUND * voxel), 0.45 * hh), centre=C, normal=Nq, d=dq, D=D, h=hh)
    # THE RIDGE (the variant): the outline offset outward along the surface, at the ridge's centre depth
    ridge = None
    if des['ridge'] is not None:
        dist, q, seg, tt = _polyline_closest(out_b, out_cl)
        T = np.roll(out_b, -1, axis=0) - np.roll(out_b, 1, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        inward = orient * np.cross(nb, T)
        Qr, Nr = onto(out_b + des['ridge']['d'] * inward)
        Cr = _resample(Qr + des['ridge']['z'] * Nr, 0.5e-3, closed=True)
        ridge = (Cr, np.roll(Cr, -1, axis=0))
    # the voxels the op reads: the plates' and the outline's box, + the junction's outer reach and the band
    pts = np.vstack([out_b, cen_b] + ([seams[0]] if len(seams[0]) else []))
    pad = abs(des['reach'][0]) + band + 2.0e-3
    aabb = (pts.min(0) - pad, pts.max(0) + pad)
    # THE BOUND
    if kappa is None:
        # measured: the block-out's normals' turn over a step along two tangents, at the outline and the centres
        Xk = np.vstack([out_b[::max(1, len(out_b) // 200)], cen_b])
        Nk = np.asarray(prog.normals(Xk), np.float64)
        e1 = np.cross(Nk, [0.0, 0.0, 1.0])
        e1[np.linalg.norm(e1, axis=1) < 1e-6] = [1.0, 0.0, 0.0]
        e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
        e2 = np.cross(Nk, e1)
        h = 1.0e-3
        kap = [np.linalg.norm(np.asarray(prog.normals(Xk + h * e), np.float64) - Nk, axis=1) / h for e in (e1, e2)]
        kappa = 1.25 * float(np.max(kap))
        kappa_src = 'measured x 1.25'
    else:
        kappa_src = 'given (exact)'
    zeta = band + 2.0 * voxel
    if zeta * kappa >= 1.0:
        raise CyborgError('cyborg.chart', f'the band ({zeta*1e3:.1f} mm) passes the block-out\'s radius of curvature '
                                          f'({1e3/kappa:.1f} mm): the foot map folds')
    L = max(1.0, 1.0 / (1.0 - zeta * kappa))
    sp = dict(layout=layout, chart=chart, prog=prog, design=des, L=L, kappa=kappa, kappa_src=kappa_src, zeta=zeta,
              outline=out_b, outline_n=nb, sdist=sdist, plate_of=plate_of, plate_id=pid, seams=seams, seam_r=rs,
              k_lip=k_lip, glow=bool(P['glow_seams']), gasket=gasket, k_gasket=k_gasket, heads=heads, ridge=ridge,
              scar=(des['scar'] if (P['junction']['scar'] == 'band' and des['kind'] == 'crease') else None),
              aabb=aabb, band=band, voxel=voxel)
    # THE FEED (C3d): its cables' occluders and its sockets from the layout's routes (feed_layout), on this block-out
    sp['feed'] = feed_plan(layout['feed'], sp) if layout.get('feed') else None
    return sp


def surface_bounds(sp, band=None):
    """the planned strokes' activation spheres the band cannot hold (voxel.SparseSDF(extra=)), on octopus_sculpt.
    Plan.bounds' rule: an add reaching past 0.8 of the band off the block-out (the heads: plate_t + 0.31 D over it); and
    the PLATE SHELL where the band cannot hold the field the bake reads over the plates (plate_shell). None (the layer
    OFF): none"""
    if sp is None:
        return np.zeros((0, 3)), np.zeros(0)
    band = sp['band'] if band is None else band
    Cs, Rs = plate_shell(sp, band)
    Cb, Rb = _stroke_bounds(sp, band)
    if sp.get('feed') is None:
        return np.concatenate([Cb, Cs]), np.concatenate([Rb, Rs])
    Cf, Rf = feed_bounds(sp['feed'])           # C3d: the occluders' voxels stand up to the collars' tops over the band
    return np.concatenate([Cb, Cs, Cf]), np.concatenate([Rb, Rs, Rf])


# THE PLATE SHELL (the C2 check): the PLATE op raises the surface plate_t off the block-out INSIDE the band, and the
# voxels end about SPLINE_VOX short of the band (voxel.vsample's cubic B-spline reads voxel centres up to 2 voxels past
# its point); past them voxel.hybrid falls back to the analytic block-out, which knows nothing of the plate and
# over-reads its distance by plate_t. The bake's CURVATURE is the field's Laplacian with arms of 4 x h_grad = 4 x 0.9
# voxels ALONG THE AXES (bake.py k_bake): on t10's 2.5 mm band the plate's top keeps ~0.85 mm of voxels, under that
# 1.08 mm arm, and the curvature driver printed the band's staircase as ripples over every plate whose normal lies
# within ~38 deg of an axis (0.5 % of the flat texels off by over 1000 /m; normals, AO, cavity, thickness and height
# unchanged); on c02's 3.0 mm band the arm stays inside the voxels. So where plate_t + the arm + the spline's reach
# passes the band, a lattice of activation spheres on the plates' top (the rim included) wakes the voxels the bake reads
# (c02 B9; the ball's 29.7 cm2 of plates: +0.39 M voxels on 2.5 mm)
BAKE_LAP_VOX = 3.6       # bake.py's curvature arm in voxels (h_grad = 0.9 voxel, the Laplacian at 4 h_grad)
SPLINE_VOX = 2.0         # voxel.vsample's support past its point, in voxels
SHELL_STEP_VOX = 6.0     # the shell lattice's spacing on the surface, in voxels
SHELL_R_VOX = 7.6        # its spheres' radius: sqrt(7.6^2 - (6 / sqrt 2)^2) = 6.3 > 3.6 + 2 voxels up at the lattice's
                         # farthest point from every centre (voxel.SparseSDF pads each radius by its act_pad as well)


def plate_shell(sp, band):
    """the plate shell's activation spheres (the notes above): (centres, radii), none where the band holds the bake's
    reach over the plates (plate_t + (BAKE_LAP_VOX + SPLINE_VOX) voxels < band) or the layer is OFF"""
    if sp is None:
        return np.zeros((0, 3)), np.zeros(0)
    vs = float(sp['voxel'])
    top = float(sp['design']['t'])
    if top + (BAKE_LAP_VOX + SPLINE_VOX) * vs < band:
        return np.zeros((0, 3)), np.zeros(0)
    lay, ch, prog, des = sp['layout'], sp['chart'], sp['prog'], sp['design']
    rg = lay['region']
    wh = lambda u: np.interp(u, rg['u'], rg['wh'])
    step = SHELL_STEP_VOX * vs
    ug = np.repeat(np.linspace(rg['u0'], rg['u1'], 9), 5)
    uw_g = np.column_stack([ug, np.tile(np.linspace(-0.9, 0.9, 5), 9) * wh(ug)])
    gu = float(max(1.0, np.nanmax(ch.tangents(uw_g)[3])))
    U = np.arange(rg['u0'] - step / gu, rg['u1'] + step / gu + 1e-12, step / gu)
    uw = np.concatenate([np.column_stack([np.full(len(W), u), W]) for u in U
                         for W in [np.arange(-float(wh(u)) - step, float(wh(u)) + step + 1e-12, step)]])
    uw[:, 0] = np.clip(uw[:, 0], rg['u0'], rg['u1'])
    uw[:, 1] = np.clip(uw[:, 1], -wh(uw[:, 0]), wh(uw[:, 0]))
    X = ch.from_uw(uw)
    X = X[np.all(np.isfinite(X), axis=1)]
    F, _ = blockout_foot(prog, X)
    d = sp['sdist'](F)
    F, d = F[d >= -step], d[d >= -step]
    N = np.asarray(prog.normals(F, h=FOOT_H), np.float64)
    C = F + junction_top(des, np.maximum(d, 0.0))[:, None] * N
    return C, np.full(len(C), SHELL_R_VOX * vs)


def _stroke_bounds(sp, band):
    """surface_bounds' strokes (the heads, the gasket, the ridge) reaching past 0.8 of the band"""
    C, R = [], []
    if sp['heads'] is not None:
        H = sp['heads']
        C.append(0.5 * (H['A'] + H['B']))
        R.append(np.full(len(H['A']), 0.5 * np.linalg.norm(H['B'][0] - H['A'][0]) + H['ra'] + 2.0 * HEAD_K))
    for chain, r_, k_ in ((sp['gasket'], sp['design']['gasket']['r'], sp['k_gasket']),
                          (sp['ridge'], sp['design']['ridge']['r'] if sp['ridge'] is not None else 0.0,
                           sp['design']['J']['k_ridge'])):
        if chain is not None:
            C.append(0.5 * (chain[0] + chain[1]))
            R.append(np.full(len(chain[0]), 0.5 * float(np.max(np.linalg.norm(chain[1] - chain[0], axis=1))) + r_ +
                             2.0 * k_))
    if not C:
        return np.zeros((0, 3)), np.zeros(0)
    C, R = np.concatenate(C), np.concatenate(R)
    f = np.asarray(sp['prog'].eval(C), np.float64)
    need = f + R > 0.8 * band
    return C[need], R[need]


FOOT_H = 2.0e-4          # the block-out normals' difference step (m): float32 programs at 20 um leave the normal ~1.5e-4
                         # rad of noise, the foot ~0.5 um at the band's depth (B5's probe read it as gradient)


def blockout_foot(prog, X, iters=4):
    """the CLOSEST point of the block-out to each point and the point's signed height over it: the fixed point of
    F = X - z n(F) (a contraction while z kappa < 1), the normals by differences of FOOT_H"""
    X = np.atleast_2d(np.asarray(X, np.float64))
    z = np.asarray(prog.eval(X), np.float64)
    F = X - z[:, None] * np.asarray(prog.normals(X, h=FOOT_H), np.float64)
    for _ in range(iters):
        F = X - z[:, None] * np.asarray(prog.normals(F, h=FOOT_H), np.float64)
        F = F - np.asarray(prog.eval(F), np.float64)[:, None] * np.asarray(prog.normals(F, h=FOOT_H), np.float64)
    return F, z


RELEVEL_MARGIN = 1.5e-3      # apply_surface keeps its relevel within the op's reach + this (the rest handed back)


def surface_voxels(G, sp, margin=0.0):
    """the op's voxels: (their grid indices, their feet on the block-out, d, z): the voxels in the plan's box whose
    feet lie within the junction's outer reach (+ margin) of the outline or inside it"""
    # the box tested on the voxels' integer coordinates (t10's grid holds ~220 M voxels: its float64 positions alone
    # would take 5.3 GB), then the positions of the voxels inside it only
    lo, hi = sp['aabb']
    ijk = G.ijk.numpy()
    a = np.floor((np.asarray(lo) - G.origin) / G.vs).astype(np.int64)
    b = np.ceil((np.asarray(hi) - G.origin) / G.vs).astype(np.int64)
    inb = np.ones(len(ijk), bool)
    for k in range(3):
        inb &= (ijk[:, k] >= a[k]) & (ijk[:, k] <= b[k])
    sel = np.nonzero(inb)[0]
    del inb
    Pv = G.origin + ijk[sel].astype(np.float64) * G.vs
    del ijk
    keep = np.all((Pv >= lo) & (Pv <= hi), axis=1)
    sel, Pv = sel[keep], Pv[keep]
    F, z = blockout_foot(sp['prog'], Pv)
    d = sp['sdist'](F)
    act = d >= sp['design']['reach'][0] - margin
    return sel[act], F[act], d[act], z[act]


def surface_fields(sp, X):
    """the op's two programs at arbitrary points X (3D): (f_T / L, f_P / L, d, z), the distance bounds the op blends
    into the grid (the Lipschitz probe reads them)"""
    F, z = blockout_foot(sp['prog'], X)
    d = sp['sdist'](F)
    fT, fP = junction_fields(sp['design'], d, z)
    return fT / sp['L'], fP / sp['L'], d, z


def apply_surface(G, sp, relevel=True, log=print):
    """the C2 sculpt on a SparseSDF G (the notes above), after the skin's Plan.apply. sp None: the layer OFF, nothing is
    read or written (cyborg OFF, every array as the forge alone makes it). Returns its counts"""
    if sp is None:
        return None
    import time
    from .voxel import STROKE_CONE, STROKE_CYL
    t0 = time.time()
    des, L = sp['design'], sp['L']
    # the op's voxels (the junction's reach and in) and, a margin wider, the voxels its relevel is kept on
    idx_all, F_all, d_all, z_all = surface_voxels(G, sp, margin=RELEVEL_MARGIN)
    op = d_all >= des['reach'][0]
    idx, F, d, z = idx_all[op], F_all[op], d_all[op], z_all[op]
    fT, fP = junction_fields(des, d, z)
    v = G.val.numpy()
    m = G.mat.numpy()
    vs = v[idx].astype(np.float64)
    if des['trough'] is not None:
        vs = _smax_np(vs, -fT / L, des['J']['k_trough'])   # 1. the trough, carved (no id: the walls keep the skin's)
    # the plate's id where it WINS: its own (true, unscaled) distance below the field's (the owner of the nearest
    # surface, k_apply's rule; the stored bound f / L reads nearer than it is and would claim the skin's air)
    win = fP < vs
    vs = _smin_np(vs, fP / L, des['J']['k_plate'])         # 1. the plate, added (its bound, f / L)
    v[idx] = vs.astype(np.float32)
    mi = m[idx]
    if win.any():
        mi[win] = sp['plate_id'][sp['plate_of'](F[win])]
    m[idx] = mi
    G.val.assign(v)
    G.mat.assign(m)
    rs = sp['seam_r']
    if len(sp['seams'][0]):                                 # 2. the seams (one batch: their exact union)
        G.strokes(STROKE_CONE, sp['seams'][0], sp['seams'][1], rs, rs, 'carve', sp['k_lip'],
                  mat=CYBORG_ID['cyb_glow'] if sp['glow'] else None)
    g = des['gasket']                                       # 3. the gasket, seated in the crease
    G.strokes(STROKE_CONE, sp['gasket'][0], sp['gasket'][1], g['r'], g['r'], 'add', sp['k_gasket'],
              mat=CYBORG_ID['cyb_gasket'])
    if sp['heads'] is not None:                             # 4. the fasteners, one size
        H = sp['heads']
        G.strokes(STROKE_CYL, H['A'], H['B'], H['ra'], H['rb'], 'add', HEAD_K, mat=CYBORG_ID['cyb_steel'])
    if sp['ridge'] is not None:                             # 5. the 'ridge' variant's scar ridge
        rr = des['ridge']['r']
        G.strokes(STROKE_CONE, sp['ridge'][0], sp['ridge'][1], rr, rr, 'add', des['J']['k_ridge'],
                  mat=CYBORG_ID['cyb_scar'])
    n_scar = 0
    if sp['scar'] is not None:                              # 5. the scar band: skin voxels at the surface over the fall
        v = G.val.numpy()
        m = G.mat.numpy()
        band_ = (d >= sp['scar'][0]) & (d <= sp['scar'][1])
        j = idx[band_]
        j = j[(m[j] == 0) & (np.abs(v[j]) < 1.5 * G.vs)]
        m[j] = CYBORG_ID['cyb_scar']
        n_scar = len(j)
        G.mat.assign(m)
    fout, idx_feed = None, None
    if sp.get('feed') is not None:                          # 6. C3d: the feed's sockets (its cables are geometry)
        fout, idx_feed = apply_feed(G, sp['feed'], log=log)
    if relevel:
        # the relevel KEPT ON THE OP'S VOXELS (+ RELEVEL_MARGIN): elsewhere the field is handed back exactly as Plan.apply
        # left it. A second relevel of the whole band moved the skin's field far from the plates by up to ~1e-4 m at
        # sharp features (the C3 bake against the plain octopus's: ~6,000 head texels' normals off by over 0.02, in
        # 830 small clusters all over the set): the layer writes nothing outside its own reach (the feed lines' own
        # voxels and their margin join it: C3b)
        v0 = G.val.numpy().copy()
        G.redistance(id_weights=relevel_table())
        v1 = G.val.numpy()
        keep = np.zeros(G.n, bool)
        keep[idx_all] = True
        if idx_feed is not None:
            keep[idx_feed] = True
        v1[~keep] = v0[~keep]
        G.val.assign(v1)
        del v0, v1, keep
    out = dict(voxels=len(idx), plate_won=int(win.sum()), seams=len(sp['seams'][0]), gasket=len(sp['gasket'][0]),
               heads=0 if sp['heads'] is None else len(sp['heads']['A']), scar_voxels=n_scar, L=L,
               seconds=time.time() - t0)
    if fout is not None:
        out['feed'] = fout
    log(f'[cyborg] surface sculpt: {out["voxels"]:,} voxels read, the plate won {out["plate_won"]:,}; '
        f'{out["seams"]} seam capsules, {out["gasket"]} gasket, {out["heads"]} heads, {n_scar:,} scar voxels; L '
        f'{L:.4f}; {out["seconds"]:.1f}s')
    return out


# ============================================================================================ mount plates
def socket_ports(gltf_json):
    """every typed socket node of a glb as a PORT in the creature's frame: {name: dict(pos, normal, tangent, kind,
    interface, side, joint, dims)}; the slot's frame is written in its joint's frame (A.6), turned here by the joint's
    bind-pose world rotation"""
    nodes = gltf_json['nodes']
    parent = {c: i for i, nd in enumerate(nodes) for c in nd.get('children', [])}
    W = {}

    def world(i):
        if i in W:
            return W[i]
        nd = nodes[i]
        M = np.eye(4)
        if 'rotation' in nd:
            x, y, z, w = nd['rotation']
            M[:3, :3] = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        if 'scale' in nd:
            M[:3, :3] = M[:3, :3] @ np.diag(nd['scale'])
        if 'translation' in nd:
            M[:3, 3] = nd['translation']
        W[i] = M if i not in parent else world(parent[i]) @ M
        return W[i]
    name_of = {i: nd.get('name', str(i)) for i, nd in enumerate(nodes)}
    idx = {v: k for k, v in name_of.items()}
    out = {}
    for i, nd in enumerate(nodes):
        sl = (nd.get('extras') or {}).get('slot')
        if not isinstance(sl, dict):
            continue
        jn = sl.get('joint')
        Rj = world(idx[jn])[:3, :3] if jn in idx else np.eye(3)
        fr = sl.get('frame') or {}
        out[name_of[i]] = dict(pos=world(i)[:3, 3].copy(), kind=sl.get('kind'), interface=sl.get('interface'),
                               side=sl.get('side'), joint=jn, dims=sl.get('dims'), frame=fr,
                               normal=(Rj @ np.asarray(fr['normal'], np.float64)) if 'normal' in fr else None,
                               tangent=(Rj @ np.asarray(fr['tangent'], np.float64)) if 'tangent' in fr else None)
    return out


def mount_plate(chart, density, port, fastener_tx=10.0, land_D=2.0, heads=4, n_rim=96, name=None, reach=0.03):
    """a MOUNT PLATE under a mount (module notes): port = socket_ports()'s record (a mount socket with its frame and
    dims). Everything is laid out in the PORT'S PLANE (Z the frame's normal, X its tangent: the mount's own flange
    plane) and projected along -Z onto the surface, so the plate is the mount's footprint seen down its axis: its
    centre where the socket's normal line meets the surface; its rim the mount's radius plus land_D head diameters;
    the mount's own bolts on the dims' bolt circle, clocked from the tangent (C10's flange seats on them); `heads`
    plate fasteners at 45 deg off the tangent in the land, each 10 texels; the rim (in u, w and 3D) is the gasket and
    scar ring. Raises CyborgError on a socket that is no mount, a degenerate frame, missing dims, or a footprint off
    the surface"""
    from ..remix import slots as SL
    nm = name or port.get('name', '?')
    if port.get('interface') != 'mount':
        raise CyborgError('cyborg.mount_plate', f'{nm}: a {port.get("interface")!r} socket takes no mount plate')
    if port.get('normal') is None or port.get('tangent') is None:
        raise CyborgError('cyborg.mount_plate', f'{nm}: no frame (an untyped or C0 socket: a plate is clocked by its '
                                                'port, never by a box)')
    n_ = np.asarray(port['normal'], np.float64)
    t_ = np.asarray(port['tangent'], np.float64)
    bad = SL.frame_problems(dict(normal=n_.tolist(), tangent=t_.tolist())) + SL.dims_problems('mount', port.get('dims'))
    if bad:
        raise CyborgError('cyborg.mount_plate', f'{nm}: ' + '; '.join(bad))
    dims = port['dims']
    n_ = n_ / np.linalg.norm(n_)
    t_ = t_ - (t_ @ n_) * n_
    t_ /= np.linalg.norm(t_)
    o_ = np.cross(n_, t_)
    pos = np.asarray(port['pos'], np.float64)

    def onto(Q):
        """points of the port's plane projected along -Z onto the surface (the first hit within reach above it)"""
        X, f = chart.cast(Q + reach * n_[None], np.repeat(-n_[None], len(Q), 0), 2.0 * reach)
        if np.any(f < 0):
            raise CyborgError('cyborg.mount_plate', f'{nm}: {int((f < 0).sum())} of its footprint\'s points meet no '
                                                    f'surface along the port\'s normal within {reach} m')
        return X
    c = onto(pos[None])[0]
    D = float(fastener_tx) / float(density.px_iso(c[None])[0])
    Rp = float(dims['radius']) + land_D * D

    def ring(radius, phis):
        return onto(c[None] + radius * (np.cos(phis)[:, None] * t_[None] + np.sin(phis)[:, None] * o_[None]))
    phi = np.linspace(0.0, 2 * np.pi, n_rim + 1)
    rim = ring(Rp, phi)
    nb = int(dims['bolts'])
    bolts = ring(float(dims['bolt_circle']), 2 * np.pi * np.arange(nb) / nb)
    hp = ring(float(dims['radius']) + 0.5 * land_D * D, np.pi / 4 + np.pi / 2 * np.arange(heads))
    uw_c = chart.to_uw(c[None])[0]
    _, _, nrm, _ = chart.tangents(uw_c[None])
    sag = float(np.abs((rim - c) @ n_).max())
    surf_r = np.linalg.norm(rim - c, axis=1)
    return dict(name=nm, kind=port.get('kind'), centre=c, centre_uw=uw_c, normal=n_, tangent=t_, radius=Rp,
                mount_radius=float(dims['radius']), bolt_circle=float(dims['bolt_circle']), bolts=bolts,
                pilot=float(dims['pilot']), heads=hp, D=D, rim=rim, rim_uw=chart.to_uw(rim),
                normal_vs_surface_deg=float(np.degrees(np.arccos(np.clip(abs(float(nrm[0] @ n_)), -1.0, 1.0)))),
                socket_off_mm=float(np.linalg.norm(pos - c) * 1e3), sagitta=sag,
                rim_chord=(float(surf_r.min()), float(surf_r.max())))


def mount_plates(placements, ports, chart_for, density, **kw):
    """the mount plates a resolution needs: one under each placement whose family requires 'mount_plate' (remix/slots.py
    FAMILIES: the back mount), on the chart that covers its socket (chart_for(site) -> Chart). A family that does not
    require one gets none, whatever its socket (the slot rule: a plate stands only under a back mount)"""
    from ..remix import slots as SL
    out = []
    for pl in placements:
        fam = SL.FAMILIES.get(pl.get('part'), {})
        if 'mount_plate' not in fam.get('requires', ()):
            continue
        site = pl.get('site')
        if site not in ports:
            raise CyborgError('cyborg.unknown', f'{pl.get("part")}: no typed port {site!r} on this creature')
        port = dict(ports[site], name=site)
        # the slot rule on the forge side too (the C1 check: a back_mount placement on socket_head_top built a plate on
        # the octopus's head): a mount plate stands only where its family fits, by the PORT's own kind from anatomy
        if port.get('kind') not in fam.get('fits', ()):
            raise CyborgError('cyborg.kind', f'{pl.get("part")} on {site}: a {port.get("kind")!r} socket, and it fits '
                                             f'{list(fam.get("fits", ()))} only (Skye\'s rule: a mount plate stands only '
                                             'under a back mount on a real back)')
        out.append(mount_plate(chart_for(site), density, port, **kw))
    return out


# ============================================================================================ the texel raster
def layout_texels(layouts, charts, low, set_name='head', size=None, margin_px=24, device=None):
    """what each texel of a set shows of the layouts (the C3 material pass's classification, for previews and gates):
    every texel in the layouts' UV footprint (+ margin) gets the low's point under it (the bake's own query), then on
    its layout's chart: inside the region outline or not (and the signed distance), its plate, the 3D distance to the
    nearest seam centreline and fastener centre. layouts / charts: parallel lists. Returns dict(x0, y0, w, h (texel
    box, y up from v = 0), and (h, w) arrays: lay (layout index, -1 none), plate, inside (mm), seam_d (m), fast_d (m),
    fast_D (m), p (3D))"""
    size = size or SET_SIZES[set_name]
    dens = UVDensity(low, device=device)
    fs = np.asarray(low['face_set']).astype(str)
    sel = np.nonzero(fs == set_name)[0]
    F = np.asarray(low['F'], np.int64)[sel]
    corner = F.ravel()
    UV = np.asarray(low['UV'], np.float64)
    V = np.asarray(low['V'], np.float64)
    uvm = _mesh(np.column_stack([UV[corner] * size, np.zeros(len(corner))]), np.arange(len(corner)).reshape(-1, 3),
                device)
    lpos = wp.array(V[corner].astype(np.float32), dtype=wp.vec3, device=device)
    # the footprint: every outline's texels
    foot = np.concatenate([dens.texel(lay['outline']['p'])[0] for lay in layouts])
    x0, y0 = np.floor(foot.min(0) - margin_px).astype(int)
    x1, y1 = np.ceil(foot.max(0) + margin_px).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, size), min(y1, size)
    w, h = x1 - x0, y1 - y0
    xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    n = xs.size
    out = wp.zeros(n, dtype=wp.vec4, device=device)
    fc = wp.zeros(n, dtype=wp.int32, device=device)
    wp.launch(k_uv_point, dim=n, inputs=[uvm.id, wp.array(xs.ravel().astype(np.float32), dtype=float, device=device),
                                         wp.array(ys.ravel().astype(np.float32), dtype=float, device=device), lpos, out,
                                         fc], device=device)
    P4 = out.numpy().astype(np.float64)
    face = fc.numpy().astype(np.int64)
    hit = face >= 0
    reg = np.full(n, -1)
    reg[hit] = np.asarray(low['region'], np.int64)[sel][face[hit]]
    res = dict(x0=int(x0), y0=int(y0), w=int(w), h=int(h), p=P4[:, :3].reshape(h, w, 3), hit=hit.reshape(h, w))
    lay_i = np.full(n, -1)
    plate = np.full(n, -1)
    ins = np.full(n, -np.inf)
    seam_d = np.full(n, np.inf)
    fast_d = np.full(n, np.inf)
    fast_D = np.zeros(n)
    from scipy.spatial import cKDTree
    for li, (lay, ch) in enumerate(zip(layouts, charts)):
        m = hit & np.isin(reg, list(lay['params']['low_regions']))
        idx = np.nonzero(m)[0]
        if not len(idx):
            continue
        # only texels ON the chart's own surface: a texel of another surface (another arm's crown top, a fold the
        # centreline cannot see) projects to some (u, w) too, but its distance from the centreline is not the chart's
        s_, th_, r_ = ch.to_st(P4[idx, :3])
        on = np.abs(r_ - ch.radius(s_, th_)) < 2.0e-3
        idx, s_, th_ = idx[on], s_[on], th_[on]
        if not len(idx):
            continue
        pts = P4[idx, :3]
        uw = np.column_stack([s_ * ch.L, ch.w_of(s_, th_)])
        rg = lay['region']
        wh = np.interp(uw[:, 0], rg['u'], rg['wh'])
        # the PLATED extent (rg u0 / u1: a bare stub at a region's end is no plate, and its outline does not run round it)
        d = _rounded_inside(uw[:, 0], uw[:, 1], rg['u0'], rg['u1'], wh, lay['params']['corner'])
        near = d > -0.006                                          # the junction band and in
        better = near & (d > ins[idx])
        j = idx[better]
        lay_i[j] = li
        ins[j] = d[better]
        # plates: the row by u, the plate by v
        v = uw[better, 1] / np.maximum(wh[better], 1e-9)
        uu = uw[better, 0]
        pl = np.full(len(j), -1)
        for p in lay['plates']:
            mm = (uu >= p['ua']) & (uu <= p['ub']) & (v >= p['va']) & (v <= p['vb'])
            pl[mm] = p['index']
        plate[j] = np.where(d[better] >= 0, pl, -1)
        if lay['seams']:
            seam_d[j] = _polyline_dist(pts[better], [sm['p'] for sm in lay['seams']])
        if lay['fasteners']:
            FP = np.array([f['p'] for f in lay['fasteners']])
            FD = np.array([f['D'] for f in lay['fasteners']])
            dd, k = cKDTree(FP).query(pts[better])
            fast_d[j] = dd
            fast_D[j] = FD[k]
    res.update(lay=lay_i.reshape(h, w), plate=plate.reshape(h, w), inside=ins.reshape(h, w),
               seam_d=seam_d.reshape(h, w), fast_d=fast_d.reshape(h, w), fast_D=fast_D.reshape(h, w),
               region=reg.reshape(h, w))
    return res


# ============================================================================================ C3: the octopus with plates
# (CYBORG_PLAN §8 C3; the lead's C3 brief, PLAN.md 10-22): the mantle plated on the canonical octopus, through t10 / t11
# / t13 ONLY behind BESTIARY_CYBORG (unset: the scripts run exactly as before). BESTIARY_CYBORG = 'mantle' (the region's
# own look) or 'mantle:large' (§4.2.3's second look, slots.PLATE_LOOKS). t10: octopus_plates() lays the plates on the
# low it builds and plans the sculpt on its block-out; drop_skin_features() takes the papillae and warts out of the
# junction's reach (+ 2 mm) and from under the plates (a wart standing 2 mm off the block-out would poke 0.8 mm through
# a 1.2 mm plate; one straddling the fall's edge would be sliced into a cliff); surface_bounds() joins the grid's extra
# (the heads' activation and the plate shell over t10's 2.5 mm band, the C2 check); apply_surface() after Plan.apply
# (no smoothing follows it in t10, so smooth_table is not needed); save_plates() for t11 / t13. t11: cyborg_texel(),
# the material pass over the skin's maps.
C3_BAND = 0.0025            # t10's band (SparseSDF(band=0.0025))
C3_SEED = 5                 # the mantle layout's seed (c01's)
SKIN_FEATURE_TAGS = ('papilla', 'wart', 'wart node')       # octopus_sculpt.plan_octopus's head-set papillae and warts
SKIN_FEATURE_MARGIN = 2.0e-3                               # their footprint kept this far outside the junction's reach


def c3_row(cyb):
    """BESTIARY_CYBORG's value -> (region, look, the surface row, the feed row or None): 'mantle' or 'mantle:<look>'
    (slots.PLATE_LOOKS), each with '+feed' for the feed lines over its plates (C3b: slots.FEED_DEFAULTS, the plates'
    seed); anything else refuses (G2: never a silent default)"""
    from ..remix import slots as SL
    txt = str(cyb).strip()
    plus = txt.split('+')
    parts = plus[0].split(':')
    region, look = parts[0], (parts[1] if len(parts) > 1 else 'default')
    if region != 'mantle' or look not in SL.PLATE_LOOKS or len(parts) > 2 or len(plus) > 2 or \
            (len(plus) == 2 and plus[1] != 'feed'):
        raise CyborgError('cyborg.surface', f'BESTIARY_CYBORG={cyb!r}: C3 plates the octopus mantle only: \'mantle\' or '
                                            f'\'mantle:<look>\' with a look of {sorted(SL.PLATE_LOOKS)}, each with '
                                            '\'+feed\' for its feed lines (C3b)')
    row = dict(region='body', seed=C3_SEED, **{k: (list(v) if isinstance(v, tuple) else v)
                                               for k, v in SL.PLATE_LOOKS[look].items()})
    feed = dict(kind='feed', region='body', seed=C3_SEED) if len(plus) == 2 else None
    errs = [p for p in SL.check_surface([row] + ([feed] if feed else []), 'octopus') if p['severity'] == 'error']
    if errs:
        raise CyborgError(errs[0]['code'], '; '.join(f'{p["where"]}: {p["message"]}' for p in errs))
    return region, look, row, feed


def octopus_plates(cyb, low, prog, voxel=0.0003, band=C3_BAND, log=print):
    """t10's plates: the layout on the mantle's chart of THIS low (t10's own arrays: V, F, UV, N, region, face_set,
    order) and its sculpt planned on the high's block-out prog; with '+feed' the feed lines routed over the layout
    (feed_layout: the layout carries them as lay['feed'], so surface_plan, save_plates and the material pass all see
    them). Returns dict(cyb, region, look, row, feed_row, layout, sp, chart, density)"""
    import time
    require_gates()
    t0 = time.time()
    region, look, row, feed_row = c3_row(cyb)
    dens = UVDensity(low)
    bc = body_chart(low)
    lift = blockout_lift(prog, dens)
    lay = panel_layout(bc, dens, row, base='octopus', region='body', lift=lift, voxel=voxel)
    if feed_row is not None:
        lay['feed'] = feed_layout(lay, bc, dens, prog, feed_row, base='octopus', log=log)
    sp = surface_plan(lay, bc, prog, dens, band=band, voxel=voxel)
    log(f'[cyborg] {cyb} ({look} look): ' + layout_summary(lay))
    log(f'[cyborg] the sculpt planned: L {sp["L"]:.4f} (kappa {sp["kappa"]:.1f} /m, {sp["kappa_src"]}), '
        f'{len(sp["seams"][0])} seam capsules, {len(sp["gasket"][0])} gasket capsules, '
        f'{0 if sp["heads"] is None else len(sp["heads"]["A"])} heads; {time.time()-t0:.1f}s')
    return dict(cyb=cyb, region=region, look=look, row=row, feed_row=feed_row, layout=lay, sp=sp, chart=bc,
                density=dens)


def drop_skin_features(plan, sp, tags=SKIN_FEATURE_TAGS, margin=SKIN_FEATURE_MARGIN, log=print):
    """the head set's papillae and warts out of the plates and the junction (the notes above; CYBORG_PLAN §4.2.4: "not
    planned" there): every stroke of those batches whose footprint (its base radius + fillet, from its foot on the
    block-out) reaches within `margin` of the junction's outer reach (where the skin starts to fall; the ridge
    variant's outer edge) is removed, and the plan's instance tables with it. Returns {tag: removed}"""
    des = sp['design']
    reach = des['trough']['d_lo'] if des['trough'] is not None else (des['ridge']['d'] - des['ridge']['r'])
    fp = sp.get('feed')
    out = {}
    keep_sites = {}
    for o in plan.ops:
        if o['tag'] not in tags or not len(o['A']):
            continue
        F, _ = blockout_foot(sp['prog'], o['A'])
        d = sp['sdist'](F)
        keep = d + o['ra'] + o['k'] < reach - margin
        if fp is not None:
            # C3b: none under a dive's cable on the skin, round its socket or in its scar band (feed_skin_mask)
            keep &= ~feed_skin_mask(fp, F, np.asarray(o['ra'], np.float64) + np.asarray(o['k'], np.float64), margin)
        out[o['tag']] = out.get(o['tag'], 0) + int((~keep).sum())
        keep_sites.setdefault(o['tag'], []).append((o['A'], keep))
        for k in ('kind', 'A', 'B', 'ra', 'rb', 'rc'):
            o[k] = o[k][keep]
    # the instance tables (t10 saves them; nothing downstream may read a papilla that is not in the high)
    for key, tag in (('head_papillae', 'papilla'), ('warts', 'wart')):
        if key in plan.inst and len(plan.inst[key].get('p', [])):
            F, _ = blockout_foot(sp['prog'], plan.inst[key]['p'])
            d = sp['sdist'](F)
            rb = np.asarray(plan.inst[key]['rb'], np.float64)
            keep = d + 2.0 * rb < reach - margin
            if fp is not None:
                keep &= ~feed_skin_mask(fp, F, 2.0 * rb, margin)
            plan.inst[key] = {k: np.asarray(v)[keep] for k, v in plan.inst[key].items()}
    plan.ops = [o for o in plan.ops if len(o['A'])]
    log(f'[cyborg] skin features out of the plates and the junction (+ {margin*1e3:.1f} mm past its reach at d '
        f'{reach*1e3:.2f} mm): ' + ', '.join(f'{k} {v}' for k, v in out.items()))
    return out


def c3_closeups(P):
    """the plates' close-ups (CYBORG_PLAN §8 C3: "close-ups beside the high"; the lead: "a seam, a head group, the
    junction and the gasket at the bake's density"): [(tag, centre, span, views)] from the layout, each view a direction
    toward the camera (voxel.trace_views / lookdev.render: world up kept up): the plated mantle head-on, a seam T (a
    meridian meeting a ring), the largest head group, the junction on the region's side (head-on, and along the
    outline so its profile shows), the gasket closer"""
    lay, ch = P['layout'], P['chart']
    rg = lay['region']
    wh = lambda u: float(np.interp(u, rg['u'], rg['wh']))
    rows = rg['rows']
    unit = lambda v: np.asarray(v, np.float64) / np.linalg.norm(v)

    def frame(uw):
        uw = np.atleast_2d(np.asarray(uw, np.float64))
        tu, tw, n, _ = ch.tangents(uw)
        return ch.from_uw(uw)[0], tu[0], tw[0], n[0]
    out = []
    um = 0.5 * (rg['u0'] + rg['u1'])
    X, tu, tw, n = frame([um, 0.0])
    out.append(('plates', X, 1.15 * max(rg['u1'] - rg['u0'], 2.0 * float(np.max(rg['wh']))), (n, unit(n + 0.8 * tw))))
    r1 = sorted([p for p in lay['plates'] if p['row'] == 1], key=lambda p: p['va'])
    if len(rows) > 1 and len(r1) > 1:
        ua = rows[1][0]
        X, tu, tw, n = frame([ua, r1[1]['va'] * wh(ua)])
        out.append(('seam', X, 0.014, (n, unit(n * 0.45 + tw * 0.9))))
    groups = {}
    for f in lay['fasteners']:
        groups.setdefault((f['plate'], f['end']), []).append(f)
    if groups:
        g = max(groups.values(), key=len)
        X, tu, tw, n = frame(np.mean([f['uw'] for f in g], axis=0))
        out.append(('heads', X, 0.018, (n, unit(n * 0.5 + tu * 0.85))))
    rm = rows[len(rows) // 2]
    um = 0.5 * (rm[0] + rm[1])
    X, tu, tw, n = frame([um, wh(um)])
    out.append(('junction', X, 0.016, (n, unit(n * 0.35 + tu * 0.94))))
    out.append(('gasket', X, 0.007, (unit(n * 0.8 + tw * 0.6), unit(n * 0.35 + tu * 0.94))))
    if lay.get('feed'):
        out += feed_closeups(lay['feed'], ch)        # C3b: the lines, a clamp on its seam, a port, a dive, a socket
    return out


def vector_views():
    """let lookdev.render take c3_closeups' view DIRECTIONS as voxel.trace_views does (a direction toward the camera,
    world up kept up): lookdev reads render.basis at each shot, which knows named views only; this wraps it (named
    views unchanged). t10 / t11 call it behind BESTIARY_CYBORG, before their close-ups"""
    from . import render as RD
    if getattr(RD.basis, '_c3_vectors', False):
        return
    named = RD.basis

    def basis(view, fwd=np.array([0.0, 0.0, 1.0])):
        if isinstance(view, str):
            return named(view, fwd)
        cam = np.asarray(view, np.float64) / np.linalg.norm(view)
        right = np.cross(np.array([0.0, 1.0, 0.0]), cam)
        right /= np.linalg.norm(right)
        return right, np.cross(cam, right), cam
    basis._c3_vectors = True
    RD.basis = basis


def merge_bounds(a, b):
    """two activation sets (centres (n, 3), radii (n,)) joined, as float64"""
    return (np.concatenate([np.asarray(a[0], np.float64).reshape(-1, 3), np.asarray(b[0], np.float64).reshape(-1, 3)]),
            np.concatenate([np.asarray(a[1], np.float64).reshape(-1), np.asarray(b[1], np.float64).reshape(-1)]))


def save_plates(out_dir, P):
    """t10's plates for t11 / t13: <out>/cyborg_plates.pkl (the layout, the row, the look) and a readable summary
    cyborg_plates.json (the tool's own outputs, as its maps are)"""
    import json
    import os
    import pickle
    lay = P['layout']
    with open(os.path.join(out_dir, 'cyborg_plates.pkl'), 'wb') as f:
        pickle.dump(dict(cyb=P['cyb'], region=P['region'], look=P['look'], row=P['row'], layout=lay), f)
    s, p = lay['stats'], lay['params']
    summ = dict(cyb=P['cyb'], look=P['look'], row=P['row'], summary=layout_summary(lay), plates=s['plates'],
                rows=s['rows'], area_cm2=s['area_cm2'], d_eq_R=s['d_eq_R'], d_eq_mm=s['d_eq_mm'], R_mm=s['R_mm'],
                seam_w_mm=p['seam_w'] * 1e3, seam_depth_mm=p['seam_depth'] * 1e3, seam_len_mm=s['seam_len_mm'],
                fasteners=s['fasteners'], heads_per_plate=s['heads_per_plate'], D_mm=(p['D'] or 0.0) * 1e3,
                head_tx=s['head_tx'], head_tx_band=s['head_tx_band'], plate_t_mm=p['plate_t'] * 1e3,
                L=P['sp']['L'], kappa=P['sp']['kappa'])
    if lay.get('feed'):
        summ['feed'] = feed_record(lay['feed'])                   # C3b: the lines, their ends, clamps and sizes
    with open(os.path.join(out_dir, 'cyborg_plates.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(summ, f, indent=1, default=float)


def load_plates(out_dir):
    """save_plates' record (None if t10 laid no plates in this folder)"""
    import os
    import pickle
    path = os.path.join(out_dir, 'cyborg_plates.pkl')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return pickle.load(f)


# ============================================================================================ C3b: the FEED LINES
# (the lead's C3b brief, PLAN.md 10-22; CYBORG_PLAN A.2.2 "feed lines", the lead's A.9 decision 6; Skye 10-22: "add more
# than just that, like robotic joints, wires, etc."): cables over the plated mantle (t10 BESTIARY_CYBORG=mantle+feed).
#   LINKS lie on the plates' flat between a PORT on one plate and a PORT on another, crossing the seams between them,
#   each crossing under a CLAMP. DIVES run from a PORT on an edge plate over the junction, lie on the skin and plunge into
#   the body through a SOCKET (the layout records that end as type 'grommet', its C3b name: the site).
#   BOTH ENDS LAND ON A PLATE OR A MOUNT (A.9 decision 6, the contact gate: never a free end). An end is a PORT (the
#   cable's collar on its plate's flat) or a SOCKET (the line's own way into the skin, the skin wrapping it). Every line
#   has a port (a feed line feeds from an implant).
# THE LAYOUT'S NUMBERS (FEED, measured, never copied: they place the routes, C3b's and C3c's, unchanged by C3d):
#   D, the cable: 0.099 of its HUB (the study-M cyborg creature: 13.6 mm cables on its 137 mm hub [D-ad A6 from R-mb]; A.2.2's 40 mm mount
#     plate gives 4.0 mm [D-ad B5]); the hub here is the layout's median plate (its equal-area diameter), the plates the
#     lines run between. The C3b bake's two caps stay in the rule (a port's top under t10's cage, cage_top with can_h; at
#     least D_min_tx head-set texels): neither binds on the default look (D_rule 'hub');
#   THE FOOTPRINTS every route clears (feed_layout's need), C3b's measured parts: a port's 0.95 D round its point (can_r)
#     and its strain relief 1.3 D along the cable (boot_len: the robot body's cable gland at study M's cable-end plug, 1.49 D
#     [R-mb]); a clamp 0.65 D in radius and 0.54 D long (clamp_r, clamp_len: p02's collar, 1.30 D across [M-rf, REFS
#     §4.1]) centred on the seam it crosses, and a dive's EDGE clamp on its plate's flat where it leaves for the rim (its
#     last fixing before the skin); a dive's end 0.95 + 0.25 + 0.85 D round its point (ring_R, ring_r, scar_w: between
#     study M's cable-end plug, 2.1 D, and the house gland's 2.9 D [R-mb, H via kb], and its scar band). C3d's collars,
#     clamps and sockets lie inside them (FEED_C3D below);
#   A DIVE settles onto the skin over the junction's reach and `settle` D more, its skin run 5-7 D (run);
#   THE LINKS' SLACK (the lead's C3c call 2, 10-27; the C3b check's look note): a link laid as a ruler-straight chart line
#     between its two ports read as a handle, not a cable. Every link now lies on the plates' flat as a gentle ARC
#     between the same two ports (feed_route_uw): a parabola over the chart chord, offset square to the chord in the
#     surface's own metric at mid-span (_bow_dir), its SAGITTA (the arc's greatest distance from the straight chart
#     route between the ports, in 3D on the surface: bow_sagitta) bow k of its SPAN (the ports' 3D distance), k inside
#     FEED['bow'] (6-12 %), tried per link from FEED['bow_try'] (a neighbour's own k last) and calibrated to it (bow_fit);
#     its SIDE chosen per link so that no two neighbouring links (routes within bow_near) MIRROR each other (_bows_mirror,
#     read on the chart where the links lie: the reflection that maps one's chord onto the other's maps its bow onto the
#     other's bow; two parallel links bowing apart or together, two at an angle bowing both out of or both into their
#     corner, each chord taken from the corner the two lines make). When every bow of a link that holds its clearances
#     mirrors a laid neighbour, that neighbour lies on its other side instead if it holds there (the C3c check: the
#     default look's two links, an L 14.7 mm apart, both bowed into their corner). A seam clamp sits where the ARC
#     crosses its seam, its collar along the arc's tangent there. The candidates, their scores and the pick stay C3b's
#     straight ones, so the same ports are joined; a picked link no bow of which holds every clearance (or every bow of
#     which clashes or mirrors) gives way to the next candidate. The dives keep their straight chart routes.
# THE CABLES ARE GEOMETRY (C3d: the lead's C3d calls, PLAN.md 10-27; Skye 10-27: "i'm not sure baking down those wires on
# the plate addition to flat looks great when you actually have geo wires on other parts of the cyborg mutation"; next
# to the hose a baked cable has no silhouette at grazing angles and no contact). ONE CABLE SYSTEM with the hose: every
# line is C5d's cable data (forge/cyborg_feed.py), re-made every frame on the rendered skin by runtime/cyborg_cable.js.
# The HIGH keeps nothing of a line but the skin's own relief at its socket: the PLATES stay baked (flush armour); the
# cables, their collars and clamps leave the bake, and their shapes as the runtime draws them, resting on the surface the
# viewer sees, stay in the bake's AO and cavity rays as OCCLUDERS (feed_occluders: bake.py's val_occ, the geometric
# suckers' rule), so the plates and the skin darken under them. The parts (FEED_C3D, measured, never copied):
#   THE CABLE at its built radius D / 2 (no ribs, no boots: the hose's braided sleeve, its TILING set, at the cable's
#     own radius), lying LIE_CLEAR over that surface (C5d's contact clearance, cyborg_cable.LIE_CLEAR): at runtime the
#     low (the plates are flush there), here the high's (the plate's top, the rim; past the outline C3b's drape from the
#     rim's foot over the crease down to the skin over the junction's reach and `settle` D);
#   THE COLLAR at every port: the hose's plate fitting (cyborg_hose: the mech tentacle's own boss and ferrule, the ferrule
#     turned to lean FERRULE_LEAN 70 deg off the boss's axis about its base E), scaled so its ferrule's bore is the
#     cable: its copies keep the tentacle's texels (a repeated piece on one set of shells, no new set). Its envelope as
#     measured on the tentacle's islands (work/bestiary/patches/scratch_cyborg_c3d/p01_hardware.py, in units of the
#     bore): the boss 1.550 in radius and 0.856 tall, its axis 0.163 ahead of E, E 0.071 over its top; the ferrule 1.180
#     in radius, -0.900..+0.720 along its axis from E. E stands over the port's point, the boss's foot COLLAR_SINK under
#     the surface (no daylight: C5c's 0.3 mm seat bar), the ferrule toward the route. The cable runs inside it from
#     -0.6 to +0.95 bores along the ferrule (the hose's run), leaves it rising 20 deg off the plate and comes down onto the
#     plate in two parts: the first an arc of DESCENT_R in the collar's own plane, RIGID with the collar (the runtime
#     carries it in the collar's frame, on the skin's weights leaning to the arc's joint with the landing: its tight
#     bend never meets the skin's moves; its rings read ~7.9 mm against gate 9's 7.3 mm bar, as the plunge's), turning
#     it over and down; the second the LANDING, an arc of LAND_R lifted over the surface (the mantle's own turn opens it
#     to ~15 mm) down to the lying height, level there, anchored to the skin ring by ring and drawn toward the collar's
#     frame by the arc, FAIRED where it is a whole run between the arc and a clamp (the links: the runtime's relay draws
#     it as the Hermite between the two, never under the skin; cyborg_feed.py, 10-28: line 4 crosses from mantle_2 to
#     mantle_1 and its landings folded to 5.4 mm in the swim). A whole descent anchored (at 0.8 mm rings) turned
#     10.6 deg at its first ring in the film and, blended toward the collar, shortened with the skin to a 7.1 mm bend;
#     the landing as C5d's inextensible free span buckled 0.5 mm where the skin under it shortened 16 % in the swim
#     (c03d K6). The descent lands no further out than
#     C3c's two arcs of 8.8 mm (the layout's clamps by the ports sit just past that landing; a 9 mm arc would push the
#     landing past line 0's and line 2's). The plunge, a true arc, PLUNGE_R: the rings' chords read a true arc ~3 %
#     tighter;
#   THE CLAMP at every clamp of the layout: the tentacle's segment-8 clamp (the largest: its copies' primary), its band
#     and its lug, scaled so the band's bore is the cable (the band 1.120 in radius, 0.521 half long; the lug 1.019-1.461
#     off the axis, 0.581 half wide, 0.435 half long, in bores), its lug on top (C3b's screw boss), its saddle left out
#     (it would stand in the plate), the band's foot 0.12 bores less LIE_CLEAR into the surface;
#   THE SOCKET at a dive's end: the lying cable bends down at PLUNGE_R into the skin (the axis crosses it at the C3b
#     grommet's centre), turns on to PLUNGE_BETA and runs a stub of PLUNGE_STUB D under it; its mouth wrapped by a
#     SOFT-TISSUE COLLAR, the skin's own relief sculpted into the high (the C3b grommet's measured ring as flesh
#     hugging the cable: its crest 0.20 D over the skin, its wall 0.35 D off the cable (the ring's 0.25 D tube widened to
#     the head set's 3-texel floor: at 0.25 D the wall read 2.3 texels, c03b F1, 10-27); the skin creased against it,
#     0.71 of the crest deep over 2.6 crests: the TechnoHunter's 0.85 / 1.2 and 3.1 / 1.2 [D-pl from R-rf]), the SCAR
#     BAND (cyb_scar) over the collar, the crease and 0.85 D past the collar, painted from the cable's distance
#     (feed_texel).
FEED = dict(hub=0.099, D_min_tx=7.0, cage_top=5.5e-3, can_h=1.35,
            can_r=0.95, boot_len=1.3, clamp_r=0.65, clamp_len=0.54, ring_R=0.95, ring_r=0.25, scar_w=0.85,
            settle=2.5, run=(5.0, 7.0), gap=3.0e-3, link_len=(18e-3, 75e-3), angle_min=55.0,
            bow=(0.06, 0.12), bow_try=(0.0625, 0.075, 0.0875, 0.10, 0.1125), bow_near=30e-3, bow_margin=0.05e-3)
FEED_C3D = dict(lie_clear=0.04e-3, bend=7.6e-3, descent_R=8.0e-3, land_R=12e-3, fit_lean=70.0, fit_run=(-0.6, 0.95),
                collar_sink=0.3e-3,
                boss_r=1.550, boss_h=0.8556, e_top=0.0711, e_off=0.1627, fer_r=1.180, fer_a=(-0.900, 0.720),
                band_r=1.120, band_hl=0.5212, lug=(1.0188, 1.4612, 0.5812, 0.4348),
                plunge_R=8.0e-3, plunge_beta=70.0, plunge_stub=1.0,
                crest=0.20, wall=0.35, crease=0.71, crease_fall=2.6, scar_w=0.85, k_flesh=0.15e-3)
FEED_ACT_VOX = BAKE_LAP_VOX + SPLINE_VOX + 1.0      # the feed's activation past its surface, in voxels (the bake's reach)
# THE PARTS' OWN NEIGHBOURHOOD (the C3b check, 10-26): a texel's low point lies within ~3 mm of the parts over it, and
# the material pass's texel box holds other UV islands' texels too, so a part's paint is read only near it (c03's O5
# leaves the feed's own ids within this of its parts to c03b)
FEED_REACH = 3.0e-3


def _seg_crossings(r0, r1, lines):
    """where the chart segment r0 -> r1 crosses each polyline of lines (all in (u, w)): [(the polyline's index, lam along
    the segment, the crossing point, the polyline's unit tangent there)], each crossing once"""
    out = []
    r0, r1 = np.asarray(r0, np.float64), np.asarray(r1, np.float64)
    dv = r1 - r0
    for k, Lp in enumerate(lines):
        Lp = np.asarray(Lp, np.float64)
        if len(Lp) < 2:
            continue
        a, e = Lp[:-1], np.diff(Lp, axis=0)
        den = dv[0] * e[:, 1] - dv[1] * e[:, 0]
        ok = np.abs(den) > 1e-18
        sd = np.where(ok, den, 1.0)
        w0 = a - r0
        lam = (w0[:, 0] * e[:, 1] - w0[:, 1] * e[:, 0]) / sd
        mu = (w0[:, 0] * dv[1] - w0[:, 1] * dv[0]) / sd
        got = []
        for i in np.nonzero(ok & (lam >= 0.0) & (lam <= 1.0) & (mu >= 0.0) & (mu <= 1.0))[0]:
            if any(abs(lam[i] - g) < 1e-9 for g in got):
                continue
            got.append(float(lam[i]))
            out.append((k, float(lam[i]), r0 + lam[i] * dv, e[i] / np.linalg.norm(e[i])))
    return out


def _multi_closest(points, lines, k=8):
    """the closest point of SEVERAL polylines (3D) to each point: (distance, the line's index, its segment's index, the
    parameter along that segment); exact over the k segments whose middles lie nearest (dense polylines)"""
    from scipy.spatial import cKDTree
    S = np.concatenate([np.stack([L[:-1], L[1:]], 1) for L in lines])
    li = np.concatenate([np.full(len(L) - 1, i) for i, L in enumerate(lines)])
    si = np.concatenate([np.arange(len(L) - 1) for L in lines])
    k = min(k, len(S))
    _, idx = cKDTree(0.5 * (S[:, 0] + S[:, 1])).query(points, k=k)
    idx = np.atleast_2d(idx).reshape(len(points), k)
    a, b = S[idx, 0], S[idx, 1]
    ab = b - a
    tt = np.clip(np.einsum('nkd,nkd->nk', points[:, None] - a, ab) / np.maximum(np.einsum('nkd,nkd->nk', ab, ab),
                                                                               1e-30), 0.0, 1.0)
    d = np.linalg.norm(points[:, None] - (a + tt[..., None] * ab), axis=2)
    j = d.argmin(1)
    r_ = np.arange(len(points))
    g = idx[r_, j]
    return d[r_, j], li[g], si[g], tt[r_, j]


def _poly_crossings(UW, lam, lines):
    """where a chart POLYLINE UW (n, 2), its route shares lam (n,), crosses each polyline of lines (all in (u, w)): [(the
    polyline's index, lam along the route, the crossing point, the polyline's unit tangent there)], each crossing once,
    per polyline in the order of its segments (_seg_crossings' order; C3c: a link's arc)"""
    UW, lam = np.asarray(UW, np.float64), np.asarray(lam, np.float64)
    A0, dA = UW[:-1], np.diff(UW, axis=0)
    out = []
    for k, Lp in enumerate(lines):
        Lp = np.asarray(Lp, np.float64)
        if len(Lp) < 2:
            continue
        B0, dB = Lp[:-1], np.diff(Lp, axis=0)
        den = dA[:, None, 0] * dB[None, :, 1] - dA[:, None, 1] * dB[None, :, 0]
        ok = np.abs(den) > 1e-18
        sd = np.where(ok, den, 1.0)
        w0 = B0[None] - A0[:, None]
        tr = (w0[..., 0] * dB[None, :, 1] - w0[..., 1] * dB[None, :, 0]) / sd        # along the route's segment
        ts = (w0[..., 0] * dA[:, None, 1] - w0[..., 1] * dA[:, None, 0]) / sd        # along the polyline's
        hit = ok & (tr >= 0.0) & (tr <= 1.0) & (ts >= 0.0) & (ts <= 1.0)
        got = []
        for j in range(len(B0)):
            for i in np.nonzero(hit[:, j])[0]:
                lg = float(lam[i] + tr[i, j] * (lam[i + 1] - lam[i]))
                if any(abs(lg - g) < 1e-9 for g in got):
                    continue
                got.append(lg)
                out.append((k, lg, A0[i] + tr[i, j] * dA[i], dB[j] / np.linalg.norm(dB[j])))
    return out


def feed_route_uw(ln, lam):
    """a feed line's ROUTE on its chart at shares lam of it (C3c): the straight chart segment between its two ends (a
    dive, or a C3b record), and for a link its BOW (ln['bow']: the notes over FEED, THE LINKS' SLACK) a parabola over that
    chord, the chart vector p (3D length 1, square to the chord on the surface at mid-span) times side 4 h lam (1 - lam)"""
    a, b = np.asarray(ln['uw'][0], np.float64), np.asarray(ln['uw'][1], np.float64)
    lam = np.atleast_1d(np.asarray(lam, np.float64))
    UW = a[None] + lam[:, None] * (b - a)[None]
    bw = ln.get('bow')
    if bw:
        UW = UW + (4.0 * float(bw['side']) * float(bw['h']) * lam * (1.0 - lam))[:, None] * \
            np.asarray(bw['p'], np.float64)[None]
    return UW


def _bow_dir(chart, a, b, h=2.0e-4):
    """the bow's chart direction p for the chord a -> b: its surface image at the chord's middle 3D length 1 and square to
    the chord in the surface (side +1: the outward normal x the chord), with that 3D direction and the chord's"""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    m = 0.5 * (a + b)
    X = chart.from_uw(np.array([m - [h, 0.0], m + [h, 0.0], m - [0.0, h], m + [0.0, h], m]))
    pu, pw = (X[1] - X[0]) / (2.0 * h), (X[3] - X[2]) / (2.0 * h)
    nrm = np.cross(pu, pw)
    nrm /= np.linalg.norm(nrm)
    if float(nrm @ (X[4] - chart.frame_at(m[0] / chart.L)[0][0])) < 0.0:
        nrm = -nrm
    c3 = (b - a)[0] * pu + (b - a)[1] * pw
    c3 /= np.linalg.norm(c3)
    q = np.cross(nrm, c3)
    q /= np.linalg.norm(q)
    p = np.linalg.lstsq(np.column_stack([pu, pw]), q, rcond=None)[0]
    return p, q, c3


def bow_sagitta(chart, ln, n=129, n_ref=513):
    """a link's bow as built (C3c): (span, sagitta, the share where it peaks): the span the 3D distance of its route's two
    ends (its ports), the sagitta the route's greatest 3D distance from the straight chart route between them (both on
    the surface: the lateral bow, the surface's own curvature in neither)"""
    lam = np.linspace(0.0, 1.0, n)
    Xa = chart.from_uw(feed_route_uw(ln, lam))
    Xs = chart.from_uw(feed_route_uw(dict(uw=ln['uw']), np.linspace(0.0, 1.0, n_ref)))
    d = _polyline_dist(Xa, [Xs])
    j = int(np.argmax(d))
    return float(np.linalg.norm(Xa[-1] - Xa[0])), float(d[j]), float(lam[j])


def bow_fit(chart, a, b, k, side, iters=4):
    """THE BOW of a link a -> b on the chart (the notes over FEED): its sagitta calibrated to k of its span on the
    surface (a few secant steps on the amplitude h), on side +1 or -1. Returns dict(k, side, h, p, span, sag, ratio,
    o (the bow's 3D direction at mid-span), c (the chord's), m (the arc's middle))"""
    p, q, c3 = _bow_dir(chart, a, b)
    ln = dict(uw=np.array([a, b], np.float64), bow=dict(k=float(k), side=int(side), h=0.0, p=p))
    span = float(np.linalg.norm(chart.from_uw(np.asarray(b, np.float64)[None])[0] -
                                chart.from_uw(np.asarray(a, np.float64)[None])[0]))
    h = float(k) * span
    for _ in range(iters):
        ln['bow']['h'] = h
        span, sag, _ = bow_sagitta(chart, ln)
        h *= float(k) * span / max(sag, 1e-12)
    ln['bow']['h'] = h
    span, sag, _ = bow_sagitta(chart, ln)
    m = chart.from_uw(feed_route_uw(ln, [0.5]))[0]
    return dict(ln['bow'], span=span, sag=sag, ratio=sag / span, o=int(side) * q, c=c3, m=m)


def _bows_mirror(a1, b1, d1, a2, b2, d2):
    """do two links' bows MIRROR each other (the notes over FEED)? Read in the CHART's own (u, w) plane, where both
    links lie: each link's chord a -> b (its ports' chart points) and d, its bow's chart direction (side x p: where its
    arc bulges). Nearly parallel chords (within ~20 deg): mirrored when the bows point opposite ways across the line
    between their middles (')(' or '()'). At an angle: each chord oriented AWAY from the two lines' crossing (the
    corner the two links make), mirrored when the reflection that maps one oriented chord onto the other maps one bow's
    direction near the other's (cos > 0.5): both bowing into, or both out of, their corner.
    (The C3c check: read in 3D, one chord oriented by the other's direction alone picked either diagonal of a
    near-square corner by a degree or two and passed the default look's two links bowing both into their corner; and
    3D chords turn with the curved mantle, two links parallel on the plates a row apart lying 20-30 deg apart there)"""
    a1, b1, a2, b2 = (np.asarray(x, np.float64) for x in (a1, b1, a2, b2))
    o1, o2 = np.asarray(d1, np.float64), np.asarray(d2, np.float64)
    o1, o2 = o1 / np.linalg.norm(o1), o2 / np.linalg.norm(o2)
    c1, c2 = (b1 - a1) / np.linalg.norm(b1 - a1), (b2 - a2) / np.linalg.norm(b2 - a2)
    m1, m2 = 0.5 * (a1 + b1), 0.5 * (a2 + b2)
    if c1 @ c2 < 0.0:
        c2 = -c2
    if np.linalg.norm(c1 - c2) < 0.35:
        cb = (c1 + c2) / np.linalg.norm(c1 + c2)
        e = m2 - m1
        e = e - (e @ cb) * cb
        if np.linalg.norm(e) < 1e-9:
            return bool(o1 @ o2 < 0.0)
        e = e / np.linalg.norm(e)
        return bool((o1 @ e) * (o2 @ e) < 0.0)
    t_, _ = np.linalg.solve(np.column_stack([c1, -c2]), a2 - a1)
    X = a1 + t_ * c1                                          # the corner: the two chords' lines cross here
    e1 = c1 if float((m1 - X) @ c1) >= 0.0 else -c1
    e2 = c2 if float((m2 - X) @ c2) >= 0.0 else -c2
    dd = e1 - e2
    if np.linalg.norm(dd) < 1e-9:
        return bool(o1 @ o2 > 0.5)
    nR = dd / np.linalg.norm(dd)
    return bool((o1 - 2.0 * (o1 @ nR) * nR) @ o2 > 0.5)


def _sd_cyl_np(X, A, B, ra, rb):
    """voxel.sd_stroke's STROKE_CYL in numpy: the capped cylinder A-B of radius ra, its edges rounded by rb (X (n, 3),
    one stroke)"""
    ax = np.asarray(B, np.float64) - np.asarray(A, np.float64)
    h = 0.5 * float(np.linalg.norm(ax))
    n = ax / max(2.0 * h, 1e-12)
    q = np.asarray(X, np.float64) - 0.5 * (np.asarray(A, np.float64) + np.asarray(B, np.float64))
    y = q @ n
    x = np.linalg.norm(q - y[:, None] * n[None], axis=1)
    dx, dy = x - (ra - rb), np.abs(y) - (h - rb)
    return np.minimum(np.maximum(dx, dy), 0.0) + np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0)) - rb


def _sd_torus_np(X, a, n, R, r):
    """voxel.sd_stroke's STROKE_TORUS in numpy: centred at a, its axis n (unit), major radius R, minor r"""
    q = np.asarray(X, np.float64) - np.asarray(a, np.float64)
    y = q @ np.asarray(n, np.float64)
    x = np.linalg.norm(q - y[:, None] * np.asarray(n, np.float64)[None], axis=1)
    return np.hypot(x - R, y) - r


def feed_layout(lay, chart, density, prog, row=None, base='octopus', log=print):
    """the FEED LINES' routes over a plate layout (the notes above). The feed row is checked (slots.check_surface: its
    keys, its region a feed region and the layout's), the cable's diameter set by the hub rule, then LINKS and DIVES are
    chosen among straight chart routes (each along u or along w, so it crosses seams and the outline square), every
    clearance measured on the low: a cable beside a head or along a seam, a port's housing on its plate's flat, a clamp
    clear of every other seam and head, a boot clear of its clamps, a grommet's ring and scar band on the skin of the
    region, lines apart; dives spread over the apex and both flanks. Each picked LINK is then laid as its BOW (C3c: the
    notes over FEED, THE LINKS' SLACK), every clearance measured again on the arc, its clamps where the arc crosses its
    seams. Raises CyborgError (cyborg.feed) when the row's lines cannot all be laid by the rules (never fewer silently).
    Returns dict(params, lines, stats)"""
    import time
    from scipy.spatial import cKDTree
    from ..remix import slots as SL
    t0 = time.time()
    row = dict(row or {})
    if row.get('kind') != 'feed':
        raise CyborgError('cyborg.feed', f'feed_layout takes a feed row (kind=\'feed\'), not {row.get("kind")!r}')
    P = lay['params']
    # the row with the layout's own plates row standing for its section (the landing is this layout's plates)
    errs = [p for p in SL.check_surface([dict(region=P['region']), row], base) if p['severity'] == 'error']
    if errs:
        raise CyborgError(errs[0]['code'], '; '.join(f'{p["where"]}: {p["message"]}' for p in errs))
    spec = dict(SL.FEED_DEFAULTS)
    spec.update({k: v for k, v in row.items() if v is not None})
    spec['region'] = row.get('region') or SL.FEED_REGIONS[base][0]
    if P['region'] != spec['region'] or not lay['plates']:
        raise CyborgError('cyborg.feed', f'feed lines on {spec["region"]!r} land on that region\'s plates: this layout '
                                         f'plates {P["region"]!r} ({len(lay["plates"])} plates)')
    seed_ = int(spec['seed'] if spec.get('seed') is not None else P['seed'])
    rng = np.random.default_rng([seed_, 4711])
    t = float(P['plate_t'])
    des = junction_design(t, P['junction']['kind'])
    W = des['rim']['W']
    j_out = des['trough']['d_lo'] if des['trough'] is not None else des['ridge']['d'] - des['ridge']['r']
    reach_out = -des['reach'][0]
    rg = lay['region']
    wh = lambda u: float(np.interp(u, rg['u'], rg['wh']))
    seam_hw = 0.5 * P['seam_w']
    Dh = float(P['D'] or 0.0)
    land = SCREW_LAND
    # ------------------------------------------------------------------------- the cable's diameter (the hub rule)
    Xc = np.array([p['centre'] for p in lay['plates']])
    hub = float(np.median([p['d_eq'] for p in lay['plates']]))
    lift_max = max(0.0, float(np.max(blockout_lift(prog, density)(Xc))))
    D = FEED['hub'] * hub
    D_cage = (FEED['cage_top'] - t - lift_max) / FEED['can_h']
    rule = 'hub'
    if D > D_cage:
        D, rule = D_cage, 'cage'
    r = 0.5 * D
    px = float(np.median(density.px_iso(Xc)))
    grow = max(1.0, 1.0 + (t + r) * float(np.median(density.mean_curvature(Xc))))
    D_tx = D * px / grow
    if D_tx < FEED['D_min_tx']:
        raise CyborgError('cyborg.feed', f'a {D*1e3:.2f} mm cable reads {D_tx:.1f} texels as baked here, under the '
                                         f'{FEED["D_min_tx"]:g} its ribbed sleeve needs')
    need = dict(head=r + 0.5 * Dh + land,                                 # the cable beside a head
                seam=r + seam_hw + 0.3e-3,                                # the cable along a seam (off its crossings)
                can_lip=FEED['can_r'] * D + 1.0e-3,                       # a housing inside its plate's lips
                can_out=W + FEED['can_r'] * D + 0.5e-3,                   # a housing on the flat, past the rim
                can_head=FEED['can_r'] * D + 0.5 * Dh + land,
                clamp_head=FEED['clamp_r'] * D + 0.5 * Dh + land,
                clamp_seam=FEED['clamp_r'] * D + seam_hw + 0.5e-3,        # a clamp clear of every other seam (a T)
                boot=FEED['can_r'] * D + FEED['boot_len'] * D + 0.5 * FEED['clamp_len'] * D + 0.5e-3,
                flat=W + r + 0.5e-3,                                      # a link stays on the plates' flat
                line=D + FEED['gap'])
    heads = np.array([f['p'] for f in lay['fasteners']]) if lay['fasteners'] else np.zeros((0, 3))
    head_tree = cKDTree(heads) if len(heads) else None
    seams3 = [sm['p'] for sm in lay['seams']]
    seams_uw = [sm['uw'] for sm in lay['seams']]
    out3 = lay['outline']['p']
    out_uw = lay['outline']['uw']
    plates = lay['plates']
    rows = rg['rows']
    u0, u1, rc = rg['u0'], rg['u1'], P['corner']
    R_g = (FEED['ring_R'] + FEED['ring_r'] + FEED['scar_w']) * D           # a grommet's footprint: ring, crease, band
    allowed = tuple(P['low_regions'])

    def plate_at(u, w):
        v = w / wh(u)
        for p in plates:
            if p['ua'] - 1e-12 <= u <= p['ub'] + 1e-12 and p['va'] - 1e-12 <= v <= p['vb'] + 1e-12:
                return p
        return None

    def sample(a, b, step=0.25e-3):
        a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
        q = chart.from_uw(a[None] + np.linspace(0.0, 1.0, 17)[:, None] * (b - a)[None])
        if not np.all(np.isfinite(q)):
            return None
        n = max(33, int(math.ceil(float(np.linalg.norm(np.diff(q, axis=0), axis=1).sum()) / step)) + 1)
        lam = np.linspace(0.0, 1.0, n)
        UW = a[None] + lam[:, None] * (b - a)[None]
        X = chart.from_uw(UW)
        if not np.all(np.isfinite(X)):
            return None
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))])
        return dict(lam=lam, UW=UW, X=X, s=s, L=float(s[-1]))

    def sample_bow(a, b, bow, step=0.25e-3):
        """sample()'s twin along a link's bow (C3c: feed_route_uw), every `step` of its 3D length"""
        ln_ = dict(uw=np.array([a, b], np.float64), bow=bow)
        q = chart.from_uw(feed_route_uw(ln_, np.linspace(0.0, 1.0, 33)))
        if not np.all(np.isfinite(q)):
            return None
        n = max(33, int(math.ceil(float(np.linalg.norm(np.diff(q, axis=0), axis=1).sum()) / step)) + 1)
        lam = np.linspace(0.0, 1.0, n)
        UW = feed_route_uw(ln_, lam)
        X = chart.from_uw(UW)
        if not np.all(np.isfinite(X)):
            return None
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))])
        return dict(lam=lam, UW=UW, X=X, s=s, L=float(s[-1]))

    def seam_d(X, skip=()):
        L_ = [S_ for k, S_ in enumerate(seams3) if k not in skip]
        return _polyline_dist(np.atleast_2d(X), L_) if L_ else np.full(len(np.atleast_2d(X)), np.inf)

    def head_d(X):
        return head_tree.query(np.atleast_2d(X))[0] if head_tree is not None else np.full(len(np.atleast_2d(X)), np.inf)

    def port_slack(X, p_uw, p):
        if plate_at(*p_uw) is not p:
            return -1.0, 'port off its plate'
        return min((float(seam_d(X)[0] - seam_hw - need['can_lip']), 'port by a seam'),
                   (float(_polyline_dist(X[None], [out3])[0] - need['can_out']), 'port on the rim'),
                   (float(head_d(X)[0] - need['can_head']), 'port by a head'))
    why = {}

    def evaluate(kind, side, a_uw, b_uw, pa, pb, bow=None):
        """one straight route (or, C3c, a link's bow: bow_fit's record): its clearances (the least, in metres: >= 0 when
        every rule holds; rec['binds'] names the rule) and its records; None (its reason counted in why) when the route
        cannot be laid at all"""
        def no(reason):
            why[(kind, side, reason)] = why.get((kind, side, reason), 0) + 1
            return None
        R = sample(a_uw, b_uw) if bow is None else sample_bow(a_uw, b_uw, bow)
        if R is None:
            return no('off the chart')
        X, s, Lr = R['X'], R['s'], R['L']
        sl = []
        # the ports: the start (and a link's end) on their plates' flat
        sl.append(port_slack(X[0], a_uw, pa))
        if kind == 'link':
            sl.append(port_slack(X[-1], b_uw, pb))
            if not FEED['link_len'][0] <= Lr <= FEED['link_len'][1]:
                return no('length')
        # the seams it crosses (square, each under a clamp), and the outline (a dive's, once); a bow's crossings where
        # its arc meets them (C3c)
        cross = []
        xs_ = _seg_crossings(a_uw, b_uw, seams_uw) if bow is None else _poly_crossings(R['UW'], R['lam'], seams_uw)
        for k, lam, puw, _ in xs_:
            sx = float(np.interp(lam, R['lam'], s))
            i = int(np.clip(np.searchsorted(s, sx), 1, len(X) - 2))
            tr = X[i + 1] - X[i - 1]
            Xk = chart.from_uw(puw[None])[0]
            j = int(np.argmin(np.linalg.norm(seams3[k] - Xk, axis=1)))
            ts = seams3[k][min(j + 1, len(seams3[k]) - 1)] - seams3[k][max(j - 1, 0)]
            ang = math.degrees(math.acos(min(1.0, abs(float(ts @ tr)) / (np.linalg.norm(ts) * np.linalg.norm(tr)))))
            cross.append(dict(seam=k, seam_kind=lay['seams'][k]['kind'], lam=lam, s=sx, uw=puw, X=Xk, angle=ang))
        if kind == 'link' and not cross:
            return no('no seam')                                  # a link joins two plates over a seam
        oc = _seg_crossings(a_uw, b_uw, [out_uw]) if kind == 'dive' else []
        if kind == 'dive' and len(oc) != 1:
            return no(f'{len(oc)} outline crossings')
        clamps = [dict(s=c['s'], uw=c['uw'], X=c['X'], seam=c['seam'], why='seam') for c in cross]
        if bow is not None:
            for cl_, c in zip(clamps, cross):
                cl_['lam'] = c['lam']                             # its place on the arc (feed_plan reads it)
        for c in cross:
            sl.append(((c['angle'] - FEED['angle_min']) * 1e-4, 'crossing angle'))     # (degrees, scaled to metres)
            sl.append((float(seam_d(c['X'], skip=(c['seam'],))[0] - need['clamp_seam']), 'clamp by a seam'))
            sl.append((float(head_d(c['X'])[0] - need['clamp_head']), 'clamp by a head'))
            sl.append((c['s'] - need['boot'], 'clamp on a boot'))
            if kind == 'link':
                sl.append((Lr - c['s'] - need['boot'], 'clamp on a boot'))
        dout = _polyline_dist(X, [out3])
        rec = dict(kind=kind, side=side, a=np.asarray(a_uw, np.float64), b=np.asarray(b_uw, np.float64), pa=pa, pb=pb,
                   X=X, s=s, L=Lr, cross=cross, clamps=clamps)
        if bow is not None:
            rec['bow'] = bow
        if kind == 'link':
            on = np.ones(len(X), bool)
            sl.append((float(dout.min() - need['flat']), 'off the flat'))
        else:
            # the outline's crossing on a straight edge, the edge clamp on the flat before the rim, the grommet on skin
            _, lam_o, puw_o, _ = oc[0]
            s_o = float(np.interp(lam_o, R['lam'], s))
            on = s <= s_o
            if side == 'apex':
                sl.append((wh(u0) - rc - abs(puw_o[1]) - (r + 1.0e-3), 'outline corner'))
            else:
                sl.append((min(puw_o[0] - (u0 + rc), (u1 - rc) - puw_o[0]) - (r + 1.0e-3), 'outline corner'))
            # the edge clamp, the cable's last fixing on the flat before the rim: the place nearest the rim (from 0.6 D to
            # 3 D past where it starts) clear of every head, seam and the port's boot; none where no place is clear (the
            # port and its boot hold the cable: a seam crossing is the only clamp the rule asks)
            j_e = np.nonzero(on & (dout >= W + 0.6 * D) & (dout <= W + 3.0 * D))[0]
            if len(j_e):
                ok_e = ((head_d(X[j_e]) - need['clamp_head'] >= 0.0) & (seam_d(X[j_e]) - need['clamp_seam'] >= 0.0) &
                        (s[j_e] - need['boot'] >= 0.0))
                if ok_e.any():
                    je = int(j_e[ok_e][np.argmin(dout[j_e][ok_e])])
                    clamps.append(dict(s=float(s[je]), uw=R['UW'][je], X=X[je], seam=None, why='edge'))
            # the grommet: its footprint (ring, crease, scar band) past the junction's reach, on the region's skin
            XE = X[-1]
            sl.append((float(_polyline_dist(XE[None], [out3])[0] - (reach_out + R_g + 1.0e-3)), 'grommet by the plates'))
            sl.append((float(Lr - s_o - (abs(j_out) + (FEED['settle'] + 2.2) * D)), 'skin run short'))
            tu, tw, nE, _ = chart.tangents(np.asarray(b_uw, np.float64)[None])
            phi = np.linspace(0.0, 2.0 * np.pi, 13)[:-1]
            ring = XE[None] + R_g * (np.cos(phi)[:, None] * tu[0][None] + np.sin(phi)[:, None] * tw[0][None])
            st_ = chart.to_st(np.vstack([XE[None], ring]))
            reg = chart.ray(st_[0], st_[1])[2]
            if not np.all(np.isin(reg, allowed)):
                return no('grommet off the region')
            rec.update(s_out=s_o, uw_out=puw_o, X_out=chart.from_uw(puw_o[None])[0])
        # the cable beside every head; along no seam off its crossings
        hd = head_d(X[on])
        sl.append((float(hd.min() - need['head']) if len(hd) else 1.0, 'cable by a head'))
        far = np.ones(len(X), bool)
        for c in cross:
            far &= np.abs(s - c['s']) > need['seam'] + 1.0e-3
        far &= on
        if far.any():
            sl.append((float(seam_d(X[far]).min() - need['seam']), 'cable along a seam'))
        rec['slack'], rec['binds'] = min(sl)
        rec['slack'] = float(rec['slack'])
        return rec
    # ------------------------------------------------------------------------- the candidates
    cands = []
    for ri, (ua, ub) in enumerate(rows):                          # LINKS along w: a row's meridian seams crossed square
        rp = sorted([p for p in plates if p['row'] == ri], key=lambda p: p['va'])
        for fu in np.linspace(0.3, 0.7, 9):
            u = ua + fu * (ub - ua)
            for ia in range(len(rp)):
                for ib in (ia + 1, ia + 2):
                    if ib >= len(rp):
                        continue
                    A, B = rp[ia], rp[ib]
                    for fa in (0.4, 0.6):
                        for fb in (0.4, 0.6):
                            cands.append(('link', 'w', (u, (A['va'] + fa * (A['vb'] - A['va'])) * wh(u)),
                                          (u, (B['va'] + fb * (B['vb'] - B['va'])) * wh(u)), A, B))
    for ri in range(len(rows) - 1):                               # LINKS along u: a ring seam crossed square
        ur = rows[ri][1]
        for A in [p for p in plates if p['row'] == ri]:
            for B in [p for p in plates if p['row'] == ri + 1]:
                lo, hi = max(A['va'], B['va']), min(A['vb'], B['vb'])
                if hi <= lo:
                    continue
                for fv in (0.25, 0.5, 0.75):
                    w = (lo + fv * (hi - lo)) * wh(ur)
                    for fa in (0.45, 0.6):
                        cands.append(('link', 'u', (A['ub'] - fa * (A['ub'] - A['ua']), w),
                                      (B['ua'] + fa * (B['ub'] - B['ua']), w), A, B))
    runs = np.linspace(FEED['run'][0], FEED['run'][1], 3)
    for A in plates:                                              # DIVES: toward the apex and down both flanks
        if abs(A['ua'] - u0) < 1e-9:
            for fv in (0.3, 0.5, 0.7):
                for fu in (0.5, 0.65):
                    ua_ = A['ua'] + fu * (A['ub'] - A['ua'])
                    w = (A['va'] + fv * (A['vb'] - A['va'])) * wh(ua_)
                    gu = float(chart.tangents(np.array([[u0, w]]))[3][0])
                    for run in runs:
                        cands.append(('dive', 'apex', (ua_, w), (u0 - (abs(j_out) + run * D) / gu, w), A, None))
        for sg, side in ((-1.0, 'flank-'), (1.0, 'flank+')):
            if (sg < 0 and A['va'] <= -1.0 + 1e-12) or (sg > 0 and A['vb'] >= 1.0 - 1e-12):
                for fu in (0.35, 0.5, 0.65):
                    u = A['ua'] + fu * (A['ub'] - A['ua'])
                    for fv in (0.45, 0.6):
                        v = (A['vb'] - fv * (A['vb'] - A['va'])) if sg < 0 else (A['va'] + fv * (A['vb'] - A['va']))
                        for run in runs:
                            cands.append(('dive', side, (u, v * wh(u)), (u, sg * (wh(u) + abs(j_out) + run * D)), A,
                                          None))
    ev = [evaluate(*c) for c in cands]
    feas = [e for e in ev if e is not None and e['slack'] >= 0.0]
    # what refuses the routes that fail (the binding rule of each, and the routes that cannot be laid at all)
    for e in ev:
        if e is not None and e['slack'] < 0.0:
            why[(e['kind'], e['side'], e['binds'])] = why.get((e['kind'], e['side'], e['binds']), 0) + 1
    why_txt = lambda kind: ', '.join(f'{sd} {rs}: {n_}' for (kd, sd, rs), n_ in sorted(why.items()) if kd == kind)
    for e in feas:
        e['score'] = min(e['slack'] / D, 1.5) + 0.6 * float(rng.random())
    # ------------------------------------------------------------------------- the choice: dives round the sides, links
    chosen = []

    def clash(e, among=None):
        for c in (chosen if among is None else among):
            if _polyline_dist(e['X'], [c['X']]).min() < need['line']:
                return True
            ends_e = [e['X'][0]] + [e['X'][-1]]
            ends_c = [c['X'][0]] + [c['X'][-1]]
            for qe, te in zip(ends_e, ('port', 'port' if e['kind'] == 'link' else 'grommet')):
                for qc, tc in zip(ends_c, ('port', 'port' if c['kind'] == 'link' else 'grommet')):
                    lim = ((2.0 * FEED['can_r'] * D if te == 'port' else R_g) +
                           (2.0 * FEED['can_r'] * D if tc == 'port' else R_g) - (FEED['can_r'] * D if te == tc == 'port'
                                                                                 else 0.0) + 2.0e-3)
                    if np.linalg.norm(qe - qc) < lim:
                        return True
        return False
    picked = dict(dive=[], link=[])
    rng_b = np.random.default_rng([seed_, 4712])                  # the bows' own draws (the scores' stay C3b's)

    def bow_link(e):
        """C3c: a picked link's BOW (the notes over FEED, THE LINKS' SLACK): its two sides in a seeded order, its k's
        (FEED['bow_try']) in a seeded order with a neighbouring link's own k last, every bow tried; the first that holds
        every clearance with bow_margin to spare (the devices' query noise is ~5 um: t10 lays on the GPU, c03b re-lays on
        the CPU, and a bow on a clearance's edge could fall either way), clashes with no chosen line and mirrors no
        neighbouring link (routes within bow_near). Its record carries every bow tried. None (each refusal counted in
        why) when none holds"""
        ks = [FEED['bow_try'][i] for i in rng_b.permutation(len(FEED['bow_try']))]
        used = {round(c['bow']['k'], 9) for c in picked['link']
                if _polyline_dist(e['X'], [c['X']]).min() < FEED['bow_near']}
        ks = [k_ for k_ in ks if round(k_, 9) not in used] + [k_ for k_ in ks if round(k_, 9) in used]
        sides = (1, -1) if rng_b.random() < 0.5 else (-1, 1)
        tried, best = [], None
        # two links' bows mirrored? (_bows_mirror: on the chart, each chord its ports' chart points, each bow side x p)
        mir = lambda x, bx, y: _bows_mirror(x['a'], x['b'], bx['side'] * np.asarray(bx['p'], np.float64),
                                            y['a'], y['b'], y['bow']['side'] * np.asarray(y['bow']['p'], np.float64))
        for sd_ in sides:
            for k_ in ks:
                bw = bow_fit(chart, e['a'], e['b'], k_, sd_)
                rec = evaluate('link', e['side'], e['a'], e['b'], e['pa'], e['pb'], bow=bw)
                if rec is None:
                    tried.append((sd_, k_, math.nan, 'off the chart or its length'))
                    continue
                if rec['slack'] < FEED['bow_margin']:
                    verdict = f'bow: {rec["binds"]}' + (' (inside the margin)' if rec['slack'] >= 0.0 else '')
                elif clash(rec):
                    verdict = 'bow: lines apart'
                elif any(mir(e, bw, c) for c in picked['link']
                         if _polyline_dist(rec['X'], [c['X']]).min() < FEED['bow_near']):
                    verdict = 'bow: mirrors a neighbour'
                else:
                    verdict = 'laid' if best is None else 'holds'
                    if best is None:
                        best = rec
                tried.append((sd_, k_, float(rec['slack']), verdict))
                if verdict.startswith('bow:'):
                    key = ('link', e['side'], verdict)
                    why[key] = why.get(key, 0) + 1
        if best is None:
            # THE NEIGHBOUR'S OTHER SIDE (the C3c check): a bow of this link that holds every clearance and clashes with
            # nothing but MIRRORS laid neighbours takes its place when each of those neighbours can lie on its other side
            # instead: the same ports, its own k's in its own order there, every clearance with the margin, clashing with
            # no line (this bow included) and mirroring no link (this bow included). The neighbour's record keeps every
            # bow it tried and notes the swap. No new draws: a layout that needs no swap is laid as before
            for j_, (sd_, k_, _, verdict) in enumerate(tried):
                if verdict != 'bow: mirrors a neighbour':
                    continue
                bw = bow_fit(chart, e['a'], e['b'], k_, sd_)
                rec = evaluate('link', e['side'], e['a'], e['b'], e['pa'], e['pb'], bow=bw)
                near_ = lambda q, c: _polyline_dist(q['X'], [c['X']]).min() < FEED['bow_near']
                nbrs = [c for c in picked['link'] if near_(rec, c) and mir(e, bw, c)]
                swap = []
                for c in nbrs:
                    got = None
                    for sdc, kc, _, _ in c['bow']['tried']:
                        if sdc == c['bow']['side']:
                            continue
                        bwc = bow_fit(chart, c['a'], c['b'], kc, sdc)
                        rc = evaluate('link', c['side'], c['a'], c['b'], c['pa'], c['pb'], bow=bwc)
                        if rc is None or rc['slack'] < FEED['bow_margin']:
                            continue
                        rest = [x for x in chosen if x is not c] + [rec]
                        if clash(rc, rest):
                            continue
                        if any(mir(c, bwc, x) for x in rest if x.get('bow') is not None and near_(rc, x)):
                            continue
                        got = rc
                        break
                    if got is None:
                        break
                    swap.append((c, got))
                if not nbrs or len(swap) < len(nbrs):
                    continue
                for c, got in swap:
                    got['score'] = c['score']
                    got['bow'] = dict(got['bow'], tried=list(c['bow']['tried']) + [
                        (got['bow']['side'], got['bow']['k'], float(got['slack']),
                         f'laid on its other side: its side {c["bow"]["side"]:+d} k {c["bow"]["k"]} mirrored the '
                         f'{e["side"]} link')])
                    chosen[[id(x) for x in chosen].index(id(c))] = got
                    picked['link'][[id(x) for x in picked['link']].index(id(c))] = got
                tried[j_] = (sd_, k_, float(rec['slack']), 'laid (a neighbour on its other side)')
                best = rec
                break
        if best is None:
            return None
        best['score'] = e['score']
        best['bow'] = dict(best['bow'], tried=tried)
        return best
    for kind, want, order in (('dive', int(spec['dives']), ('apex', 'flank-', 'flank+')),
                              ('link', int(spec['links']), ('w', 'u'))):
        pools = {sd: sorted([e for e in feas if e['kind'] == kind and e['side'] == sd], key=lambda e: -e['score'])
                 for sd in order}
        k = 0
        while len(picked[kind]) < want and any(pools.values()):
            sd = order[k % len(order)]
            k += 1
            while pools[sd]:
                e = pools[sd].pop(0)
                if kind == 'link':
                    e = bow_link(e)                               # C3c: the link's bow, or the next candidate
                    if e is None:
                        continue
                    chosen.append(e)
                    picked[kind].append(e)
                    break
                if not clash(e):
                    chosen.append(e)
                    picked[kind].append(e)
                    break
        if len(picked[kind]) < want:
            raise CyborgError('cyborg.feed', f'{len(picked[kind])} of {want} {kind}s fit the rules on this layout '
                                             f'({sum(1 for e in feas if e["kind"] == kind)} of '
                                             f'{sum(1 for c in cands if c[0] == kind)} routes hold every clearance before '
                                             f'the lines\' own spacing; the rest refused by {why_txt(kind)}): never fewer '
                                             'silently')
    # ------------------------------------------------------------------------- the records (the contact gate on each)
    lines = []
    for e in picked['dive'] + picked['link']:
        ends = [dict(type='port', plate=int(e['pa']['index']), uw=e['a'], X=e['X'][0])]
        if e['kind'] == 'link':
            ends.append(dict(type='port', plate=int(e['pb']['index']), uw=e['b'], X=e['X'][-1]))
        else:
            ends.append(dict(type='grommet', plate=None, uw=e['b'], X=e['X'][-1]))
        ln = dict(kind=e['kind'], side=e['side'], uw=np.array([e['a'], e['b']]), length=e['L'], ends=ends,
                  crossings=[{k: v for k, v in c.items()} for c in e['cross']],
                  clamps=sorted(e['clamps'], key=lambda c: c['s']), slack=e['slack'])
        if e['kind'] == 'dive':
            ln['outline'] = dict(s=e['s_out'], uw=e['uw_out'], X=e['X_out'])
        if e.get('bow') is not None:
            ln['bow'] = dict(e['bow'])                            # C3c: the link's arc (feed_route_uw reads it)
        lines.append(ln)
    params = dict(region=spec['region'], set=P['set'], chart=P['chart'], base=base, D=D, D_rule=rule, D_hub=FEED['hub'] * hub,
                  D_cage=D_cage, hub=hub, r=r, D_tx=D_tx, px=px, grow=grow, sleeve=spec['sleeve'],
                  links=int(spec['links']), dives=int(spec['dives']), seed=seed_, plate_t=t, W=W, j_out=j_out,
                  reach_out=reach_out, R_g=R_g, need=need, FEED=dict(FEED))
    stats = dict(lines=len(lines), links=len(picked['link']), dives=len(picked['dive']),
                 clamps=sum(len(l_['clamps']) for l_ in lines), seam_clamps=sum(len(l_['crossings']) for l_ in lines),
                 ports=sum(1 for l_ in lines for e_ in l_['ends'] if e_['type'] == 'port'),
                 grommets=sum(1 for l_ in lines for e_ in l_['ends'] if e_['type'] == 'grommet'),
                 length_mm=float(sum(l_['length'] for l_ in lines)) * 1e3, candidates=len(cands), feasible=len(feas),
                 least_slack_mm=float(min(l_['slack'] for l_ in lines)) * 1e3 if lines else 0.0,
                 seconds=time.time() - t0)
    fd = dict(params=params, lines=lines, stats=stats)
    gate = feed_gate(fd, lay, chart)
    if gate['bad']:
        raise CyborgError('cyborg.feed', 'the contact gate refuses: ' + '; '.join(gate['bad']))
    stats['gate'] = gate['summary']
    log(f'[cyborg] feed lines: {feed_summary(fd)}; {len(feas)} of {len(cands)} routes hold every clearance; '
        f'{stats["seconds"]:.1f}s')
    return fd


def feed_gate(fd, lay, chart):
    """THE CONTACT GATE (A.9 decision 6: both ends land on a plate or a mount, never free): every line has two ends, each
    a PORT on a plate of the layout (its point inside that plate, (u, v)) or a GROMMET (outside the plates, past the
    junction's reach on the chart's skin); a port at least; a link's ends on two different plates; a dive crosses the
    outline once. Returns dict(bad: [reasons], summary)"""
    bad = []
    rg = lay['region']
    wh = lambda u: float(np.interp(u, rg['u'], rg['wh']))
    for i, ln in enumerate(fd['lines']):
        ends = ln.get('ends') or []
        if len(ends) != 2:
            bad.append(f'line {i} has {len(ends)} ends (a free end: a line has two, each seated)')
            continue
        kinds = [e.get('type') for e in ends]
        if 'port' not in kinds:
            bad.append(f'line {i} has no port (a feed line feeds from an implant)')
        for j, e in enumerate(ends):
            u, w = float(e['uw'][0]), float(e['uw'][1])
            if e.get('type') == 'port':
                p = lay['plates'][e['plate']] if e.get('plate') is not None and e['plate'] < len(lay['plates']) else None
                v = w / wh(u)
                if p is None or not (p['ua'] <= u <= p['ub'] and p['va'] <= v <= p['vb']):
                    bad.append(f'line {i} end {j}: a port off its plate {e.get("plate")}')
            elif e.get('type') == 'grommet':
                d = _rounded_inside(np.array([u]), np.array([w]), rg['u0'], rg['u1'], np.array([wh(u)]),
                                    lay['params']['corner'])[0]
                if d > -fd['params']['reach_out']:
                    bad.append(f'line {i} end {j}: a grommet inside the junction\'s reach ({d*1e3:.1f} mm)')
            else:
                bad.append(f'line {i} end {j}: an end of type {e.get("type")!r} (a port or a grommet, never free)')
        if ln['kind'] == 'link' and ends[0].get('plate') == ends[1].get('plate'):
            bad.append(f'line {i}: a link on one plate')
    n = len(fd['lines'])
    return dict(bad=bad, summary=f'{n} lines, {2 * n} ends: every end a port on a plate or a grommet in the skin: '
                                 f'{not bad}')


def feed_summary(fd):
    """one line: the lines, their ends and clamps, the cable"""
    P, s = fd['params'], fd['stats']
    bows = [ln['bow'] for ln in fd['lines'] if ln.get('bow')]
    return (f'{s["links"]} links + {s["dives"]} dives ({s["ports"]} ports, {s["grommets"]} sockets, {s["clamps"]} clamps, '
            f'{s["seam_clamps"]} on seams), {s["length_mm"]:.0f} mm of cable D {P["D"]*1e3:.2f} mm '
            f'({P["D_rule"]}: {FEED["hub"]} x the {P["hub"]*1e3:.1f} mm hub = {P["D_hub"]*1e3:.2f} mm; '
            f'{P["D_tx"]:.1f} head-set texels across)'
            + ('; the links bowed ' + ', '.join(f'{b["sag"]*1e3:.2f} on {b["span"]*1e3:.1f} mm ({b["ratio"]*100:.1f} %, '
                                                 f'side {b["side"]:+d})' for b in bows) if bows else ''))


def feed_record(fd):
    """the readable record of a feed layout (save_plates' json)"""
    P = fd['params']
    out = dict(summary=feed_summary(fd), D_mm=P['D'] * 1e3, D_rule=P['D_rule'], D_tx=P['D_tx'], hub_mm=P['hub'] * 1e3,
               sleeve=P['sleeve'], stats={k: v for k, v in fd['stats'].items()}, lines=[])
    for ln in fd['lines']:
        out['lines'].append(dict(kind=ln['kind'], side=ln['side'], length_mm=ln['length'] * 1e3,
                                 ends=[dict(type=e['type'], plate=e['plate']) for e in ln['ends']],
                                 crossings=[dict(seam=c['seam'], kind=c['seam_kind'], angle_deg=c['angle'])
                                            for c in ln['crossings']],
                                 clamps=[c['why'] for c in ln['clamps']], slack_mm=ln['slack'] * 1e3))
        if ln.get('bow'):
            b = ln['bow']
            out['lines'][-1]['bow'] = dict(k=b['k'], side=b['side'], span_mm=b['span'] * 1e3, sagitta_mm=b['sag'] * 1e3,
                                           ratio=b['ratio'])
    return out


def _hermite(p0, t0, p1, t1, n):
    """a cubic Hermite from p0 (unit tangent t0) to p1 (t1), its tangents scaled by the chord: (n, 3)"""
    p0, t0, p1, t1 = (np.asarray(x, np.float64) for x in (p0, t0, p1, t1))
    c = float(np.linalg.norm(p1 - p0))
    u = np.linspace(0.0, 1.0, n)[:, None]
    return ((2 * u ** 3 - 3 * u ** 2 + 1) * p0 + (u ** 3 - 2 * u ** 2 + u) * c * t0 + (-2 * u ** 3 + 3 * u ** 2) * p1 +
            (u ** 3 - u ** 2) * c * t1)


def feed_bends(P):
    """a polyline's smoothness (gate 9's measures): (its least bend radius over its interior points, m: the mean of a
    point's two steps over its turn; its largest turn per step, deg)"""
    d = np.diff(np.asarray(P, np.float64), axis=0)
    sg = np.linalg.norm(d, axis=1)
    keep = sg > 1e-12
    d, sg = d[keep], sg[keep]
    if len(sg) < 2:
        return math.inf, 0.0
    tt = d / sg[:, None]
    ang = np.arccos(np.clip((tt[1:] * tt[:-1]).sum(1), -1.0, 1.0))
    return float(np.min(0.5 * (sg[1:] + sg[:-1]) / np.maximum(ang, 1e-12))), float(np.degrees(ang.max()))


def _sd_box_np(X, c, ax, h):
    """an oriented box's signed distance at points X (n, 3): centre c, axes ax (3, 3: rows), half sizes h (3,)"""
    q = np.abs((np.asarray(X, np.float64) - np.asarray(c, np.float64)) @ np.asarray(ax, np.float64).T) - np.asarray(h)
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(q.max(1), 0.0)


def feed_samples(ln, ch, step):
    """a line's route on the low (the chart's exact rays: a dive's straight chart segment, a link's bow, feed_route_uw)
    every ~`step` of its length: (lam (n,), the points (n, 3))"""
    n = max(65, int(math.ceil(ln['length'] / step)) + 1)
    lam = np.linspace(0.0, 1.0, n)
    return lam, ch.from_uw(feed_route_uw(ln, lam))


def feed_collar(S, n, x, r):
    """A PORT'S COLLAR (FEED_C3D: the hose's plate fitting scaled so its ferrule's bore is the cable's radius r) at the
    surface point S (its normal n), its ferrule toward x (the route's way from the port): its frame (x along the route on
    the surface, y the normal, z = x cross y), the ferrule's base E (over S, the boss's foot collar_sink under the
    surface) and axis d (fit_lean off y toward x), the boss's and the ferrule's cylinders (A, B, radius: the envelopes the
    occluders and the gates read) and the cable's run inside the ferrule (its two ends)"""
    C = FEED_C3D
    y = np.asarray(n, np.float64) / np.linalg.norm(n)
    x = np.asarray(x, np.float64) - (np.asarray(x, np.float64) @ y) * y
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    S = np.asarray(S, np.float64)
    foot = S - C['collar_sink'] * y
    E = foot + (C['boss_h'] + C['e_top']) * r * y
    lean = math.radians(C['fit_lean'])
    d = math.sin(lean) * x + math.cos(lean) * y
    bc = foot + C['e_off'] * r * x
    return dict(S=S, x=x, y=y, z=z, E=E, d=d, foot=foot, r=r,
                boss=(bc, bc + C['boss_h'] * r * y, C['boss_r'] * r),
                fer=(E + C['fer_a'][0] * r * d, E + C['fer_a'][1] * r * d, C['fer_r'] * r),
                run=(E + C['fit_run'][0] * r * d, E + C['fit_run'][1] * r * d))


def feed_clamp(Cc, T, n, r):
    """A CLAMP (FEED_C3D: the tentacle's segment-8 clamp scaled so its band's bore is the cable's radius r) centred at
    Cc on the cable (its tangent T), its lug toward n (on top): its frame (x = T, y the normal made square to it, z),
    the band's cylinder (A, B, radius) and the lug's box (centre, half sizes along x, y, z)"""
    C = FEED_C3D
    x = np.asarray(T, np.float64) / np.linalg.norm(T)
    y = np.asarray(n, np.float64) - (np.asarray(n, np.float64) @ x) * x
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    Cc = np.asarray(Cc, np.float64)
    hl = C['band_hl'] * r
    l0, l1, lw, ll = C['lug']
    return dict(C=Cc, x=x, y=y, z=z, r=r, A=Cc - hl * x, B=Cc + hl * x, ra=C['band_r'] * r, hl=hl,
                lug_c=Cc + 0.5 * (l0 + l1) * r * y, lug_h=np.array([ll * r, 0.5 * (l1 - l0) * r, lw * r]))


def feed_plunge(Pb, Tb, Nb, D):
    """THE PLUNGE (C3d) from the lying cable's point Pb (its tangent Tb, the surface's normal Nb there) into the body: an
    arc of PLUNGE_R turning it down to PLUNGE_BETA, then its stub (PLUNGE_STUB D) straight on: (k, 3), ~0.25 mm apart"""
    C = FEED_C3D
    R, beta = C['plunge_R'], math.radians(C['plunge_beta'])
    Nb = np.asarray(Nb, np.float64) / np.linalg.norm(Nb)
    T = np.asarray(Tb, np.float64) - (np.asarray(Tb, np.float64) @ Nb) * Nb
    T /= np.linalg.norm(T)
    th = np.linspace(0.0, beta, max(9, int(math.ceil(beta * R / 0.25e-3))) + 1)
    arc = np.asarray(Pb, np.float64)[None] + R * np.sin(th)[:, None] * T[None] - R * (1.0 - np.cos(th))[:, None] * Nb[None]
    dirn = math.cos(beta) * T - math.sin(beta) * Nb
    L = C['plunge_stub'] * D
    stub = arc[-1][None] + np.linspace(0.0, L, max(3, int(math.ceil(L / 0.25e-3))) + 1)[1:, None] * dirn[None]
    return np.vstack([arc, stub])


def feed_line(ln, F, N, s, z_lie, z_srf, r, lam):
    """ONE LINE'S CABLE (C3d; FEED_C3D) over its sampled route: F (n, 3) the route's feet on the surface it is built over
    (the block-out for the high's occluders, the low itself for the runtime), N their normals, s their arc lengths, lam
    their shares of the route, z_lie the lying axis's height over F along N, z_srf the height there of the surface the
    viewer sees. From its first port's COLLAR (its cable's run inside the ferrule, then the descent onto the surface) along
    the lying axis, through each CLAMP's band, to the far port's collar (a link) or the PLUNGE into the skin (a dive).
    Returns dict(P (m, 3) the centreline, piece (m,) per point: 'fitA' (the ferrule's run), 'arcA' (the descent's rigid
    arc), 'humpA' (its landing arc), 'lie', 'clamp<k>', 'humpB', 'arcB', 'fitB', 'plunge', s (m,) the route's arc length
    under each lying or landing point (nan on the rigid runs and arcs), collars, clamps (their s and their place on the
    route), socket (the plunge: P, its start on the route, the surface's point E at the route's end and its normal) or
    None)"""
    C3 = FEED_C3D
    D = 2.0 * r
    n = len(F)
    F, N, s = np.asarray(F, np.float64), np.asarray(N, np.float64), np.asarray(s, np.float64)
    N = N / np.linalg.norm(N, axis=1, keepdims=True)
    S_tot = float(s[-1])
    z_lie, z_srf = np.asarray(z_lie, np.float64), np.asarray(z_srf, np.float64)

    def at(arr, sq):
        sq = np.atleast_1d(np.asarray(sq, np.float64))
        if arr.ndim == 1:
            return np.interp(sq, s, arr)
        return np.column_stack([np.interp(sq, s, arr[:, k]) for k in range(arr.shape[1])])

    def lift(sq, y):
        """points over the route at arc lengths sq, y over the surface the viewer sees"""
        Nq = at(N, sq)
        Nq /= np.linalg.norm(Nq, axis=1, keepdims=True)
        return at(F, sq) + (at(z_srf, sq) + np.asarray(y, np.float64))[:, None] * Nq
    P_lie = F + z_lie[:, None] * N
    T_lie = np.gradient(P_lie, s, axis=0)
    T_lie /= np.linalg.norm(T_lie, axis=1, keepdims=True)
    lean = math.radians(C3['fit_lean'])
    x_run = C3['fit_run'][1] * r * math.sin(lean)                 # the ferrule's run's end, along the surface
    head, tail, collars = [], [], []
    s_lo, s_hi = 0.0, S_tot
    ends = [(0, 1.0)] + ([(n - 1, -1.0)] if ln['kind'] == 'link' else [])
    for end, sgn in ends:
        s_e = float(s[end])
        S_ = F[end] + z_srf[end] * N[end]
        h1 = float(z_lie[end] - z_srf[end])           # the lying height on the port's plate (where the descent lands)
        R1, R2, h_ = C3['descent_R'], C3['land_R'], 0.02e-3

        def foot(P, s0):
            """P's foot on the route (P - F square to the route there), from s0"""
            sq_ = s0
            for _ in range(6):
                Tq = at(F, sq_ + 0.05e-3)[0] - at(F, sq_ - 0.05e-3)[0]
                Tq /= np.linalg.norm(Tq)
                sq_ = float(np.clip(sq_ + float((P - at(F, sq_)[0]) @ Tq), 0.0, S_tot))
            return sq_

        def descent(col):
            """THE DESCENT from a collar (the notes over FEED_C3D): its first arc (descent_R) rigid with the collar in the
            collar's plane, the ferrule's axis d turned toward the surface (m); its landing arc (land_R) lifted over the
            surface from where the first ends, at the first's slope there, down to h1, level. The first arc's sweep b by
            bisection: the landing arc from its end lands at h1. Returns (arc1, the run's end's foot s1 on the route, b,
            the first arc's end E1 and way T1, E1's foot sE and height yE, the landing arc's start slope ph down)"""
            q1_, d_ = col['run'][1], col['d']
            m_ = math.cos(lean) * col['x'] - math.sin(lean) * col['y']
            s1_ = foot(q1_, s_e + sgn * x_run)

            def arc1(b):
                return q1_ + R1 * (math.sin(b) * d_ + (1.0 - math.cos(b)) * m_), math.cos(b) * d_ + math.sin(b) * m_

            def landing(b):
                """the first arc swept by b, and how far over h1 the landing arc from its end would come to rest (> 0:
                sweep further); the landing arc's start slope such that, lifted, it leaves along the first's way"""
                E1_, T1_ = arc1(b)
                sE_ = foot(E1_, s1_)
                NE = at(N, sE_)[0]
                NE /= np.linalg.norm(NE)
                yE_ = float((E1_ - at(F, sE_)[0]) @ NE) - float(at(z_srf, sE_)[0])
                e1 = math.asin(float(np.clip(T1_ @ NE, -1.0, 1.0)))
                ph_ = -e1
                for _ in range(3):
                    p_ = lift(np.array([sE_, sE_ + sgn * h_]), np.array([yE_, yE_ - math.tan(ph_) * h_]))
                    t_ = (p_[1] - p_[0]) / np.linalg.norm(p_[1] - p_[0])
                    ph_ += math.asin(float(np.clip(t_ @ NE, -1.0, 1.0))) - e1
                return E1_, T1_, sE_, yE_, ph_, (yE_ - h1) - R2 * (1.0 - math.cos(ph_))
            b_lo, b_hi = 0.5 * math.pi - lean, 0.5 * math.pi - lean + 0.8
            if landing(b_lo)[5] <= 0.0 or landing(b_hi)[5] >= 0.0:
                raise CyborgError('cyborg.feed', f'a collar\'s cable cannot come down to lie at {h1 * 1e3:.3f} mm in an '
                                                 f'arc of {R1 * 1e3:.1f} mm and one of {R2 * 1e3:.1f} mm')
            for _ in range(40):
                b_m = 0.5 * (b_lo + b_hi)
                if landing(b_m)[5] > 0.0:
                    b_lo = b_m
                else:
                    b_hi = b_m
            b_m = 0.5 * (b_lo + b_hi)
            return (arc1, s1_, b_m) + landing(b_m)[:5]
        # the collar's ferrule along the route's chord from the port to its descent's first arc's end (so that end stands
        # over the route; the route's own turn under the descent, a link's bow, split either side of that chord), from
        # the route's way at the run's end; three rounds
        s_g = s_e + sgn * x_run
        col = feed_collar(S_, N[end], sgn * (at(F, s_g + 0.05e-3)[0] - at(F, s_g - 0.05e-3)[0]), r)
        for _ in range(3):
            sE = descent(col)[5]
            col = feed_collar(S_, N[end], at(F, sE)[0] - F[end], r)
        arc1, s1, b_, E1, T1, sE, yE, ph = descent(col)
        q0, q1 = col['run']
        run = q0[None] + np.linspace(0.0, 1.0, 6)[:, None] * (q1 - q0)[None]
        x0 = float((q1 - S_) @ col['x'])
        N1 = at(N, s1)[0]
        N1 /= np.linalg.norm(N1)
        # the run's end over the surface under it, and the ferrule's rise off that surface
        y0 = float((q1 - at(F, s1)[0]) @ N1) - float(at(z_srf, s1)[0])
        a0 = math.asin(float(np.clip(col['d'] @ N1, -1.0, 1.0)))
        arc = np.array([arc1(x_)[0] for x_ in np.linspace(0.0, b_, max(4, int(math.ceil(b_ * 40.0)) + 1))])
        th2 = np.linspace(-ph, 0.0, max(4, int(math.ceil(ph * R2 * 40.0 / R1)) + 1))
        x2 = R2 * (np.sin(th2) + math.sin(ph))
        sq = sE + sgn * x2
        land = lift(sq, yE - R2 * (np.cos(th2) - math.cos(ph)))
        # what is left of E1 off the landing arc's start (um) taken out over the landing arc with no turn at either end.
        # Its way there keeps the route's: a link's bow turns the route under the descent and the rigid arc cannot follow
        # (its plane is the collar's), so the joint turns by half the route's turn over the first arc (~4 deg on the
        # bowed link); taken out over the landing's ~3 mm instead, that turn bent its rings to ~9 mm, 0.8 mm apart, where
        # the skin's moves against the collar act. (Drawn instead as a 3D cubic Hermite between the same ends and ways,
        # the landing bent line 3's far joint to 6.4 mm at rest; taken out over the landing and 4 mm of the lying run
        # after it, line 4's far joint still bent to 6.9 mm in the rest motion and 5.4 mm in the swim: c03d K6, 10-27)
        L2 = float(x2[-1])
        t2 = (x2 / L2)[:, None]
        land = land + (2.0 * t2 ** 3 - 3.0 * t2 ** 2 + 1.0) * (E1 - land[0])[None]
        col.update(end=int(end), s_land=float(sq[-1]), x0=x0, y0=y0, a0=a0, h1=h1, arc_b=b_, land_ph=ph,
                   hump_len=float(abs(sq[-1] - s1)))
        collars.append(col)
        if sgn > 0:
            head = [('fitA', run, np.full(len(run), np.nan)), ('arcA', arc[1:], np.full(len(arc) - 1, np.nan)),
                    ('humpA', land[1:], sq[1:])]
            s_lo = float(sq[-1])
        else:
            tail = [('humpB', land[1:][::-1], sq[1:][::-1]), ('arcB', arc[1:][::-1], np.full(len(arc) - 1, np.nan)),
                    ('fitB', run[::-1], np.full(len(run), np.nan))]
            s_hi = float(sq[-1])
    socket = None
    if ln['kind'] == 'dive':
        # the plunge: from the lying axis where its arc must start for the axis to cross the surface at the route's end
        h_l = float(z_lie[-1] - z_srf[-1])
        th0 = math.acos(max(-1.0, min(1.0, 1.0 - h_l / C3['plunge_R'])))
        s_b = S_tot - C3['plunge_R'] * math.sin(th0)
        if s_b <= s_lo + 2.0 * r:
            raise CyborgError('cyborg.feed', f'a dive\'s skin run is too short for its plunge ({s_b*1e3:.1f} mm, its '
                                             f'descent landing at {s_lo*1e3:.1f} mm)')
        Pb = at(P_lie, s_b)[0]
        Tb = at(T_lie, s_b)[0]
        Nb = at(N, s_b)[0]
        Pp = feed_plunge(Pb, Tb, Nb, D)
        socket = dict(P=Pp, s_b=float(s_b), E=F[-1] + z_srf[-1] * N[-1], n=N[-1].copy(), th0=th0, r=r)
        tail = [('plunge', Pp[1:], np.full(len(Pp) - 1, np.nan))]
        s_hi = float(s_b)
    # the lying run between: the route's own samples, each clamp's band on it
    clamps = []
    a_uw, b_uw = np.asarray(ln['uw'][0], np.float64), np.asarray(ln['uw'][1], np.float64)
    for k_, c in enumerate(ln['clamps']):
        if ln.get('bow') and c.get('lam') is not None:
            lam_c = float(c['lam'])
        else:
            lam_c = float(np.dot(np.asarray(c['uw'], np.float64) - a_uw, b_uw - a_uw) / np.dot(b_uw - a_uw, b_uw - a_uw))
        s_c = float(np.interp(lam_c, lam, s))
        cl = feed_clamp(at(P_lie, s_c)[0], at(T_lie, s_c)[0], at(N, s_c)[0], r)
        # (its band on the lying run, or over the last of a landing or the first of a plunge where the cable stands
        # within 0.02 mm of the lying height: u^2 / 2 R at the plunge's 8 mm, the tighter)
        tail_ = math.sqrt(2.0 * min(C3['land_R'], C3['plunge_R']) * 0.02e-3)
        if not s_lo - tail_ + cl['hl'] <= s_c <= s_hi + tail_ - cl['hl']:
            raise CyborgError('cyborg.feed', f'a clamp at {s_c * 1e3:.2f} mm along its line is off the lying run '
                                             f'({s_lo * 1e3:.2f}-{s_hi * 1e3:.2f} mm): its band would not sit on the plate')
        cl.update(s=s_c, seam=c['seam'], why=c['why'], k=k_)
        clamps.append(cl)
    # (the route's samples nearer than 0.06 mm to a landing's or the plunge's end left to them: a sample a few um off
    # that end, not on its arc, read a 39 deg jog in the dense line)
    m = (s > s_lo + 0.06e-3) & (s < s_hi - 0.06e-3)
    Pm, sm = P_lie[m], s[m]
    pc = np.array(['lie'] * len(sm), dtype=object)
    for cl in clamps:
        pc[np.abs(sm - cl['s']) <= cl['hl']] = f'clamp{cl["k"]}'
    pieces = head + [(None, Pm, sm)] + tail
    P_all, piece, s_all = [], [], []
    for nm, Q, sq in pieces:
        P_all.append(Q)
        piece += (list(pc) if nm is None else [nm] * len(Q))
        s_all.append(sq)
    return dict(P=np.vstack(P_all), piece=np.array(piece, dtype=object), s=np.concatenate(s_all), collars=collars,
                clamps=clamps, socket=socket, s_lo=s_lo, s_hi=s_hi, r=r)


def feed_plan(fd, sp):
    """THE FEED IN THE HIGH (C3d; the notes over FEED) on a surface plan sp (its block-out, chart, outline distance and
    the junction's design), from the layout's routes: per line its CABLE as feed_line builds it over the high's surface
    (the block-out's feet, the surface the viewer sees: the plate's top, the rim, the gasket's bead, the crease, the skin;
    the cable lying lie_clear + r over it, past the outline on C3b's drape from the rim's foot over the crease down to the
    skin), its collars, clamps and socket: the OCCLUDERS the bake's AO and cavity rays read (feed_occluders); each
    socket's soft-tissue COLLAR and CREASE (apply_feed sculpts them) and SCAR BAND (feed_texel paints it). Returns the
    plan (None: no feed)"""
    if not fd or not fd.get('lines'):
        return None
    P = fd['params']
    D = P['D']
    r = 0.5 * D
    C3 = FEED_C3D
    prog, ch, des, sdist = sp['prog'], sp['chart'], sp['design'], sp['sdist']
    t = des['t']
    W, z0 = des['rim']['W'], des['rim']['z0']
    g = des['gasket']
    c = C3['lie_clear']
    X1 = abs(P['j_out']) + FEED['settle'] * D
    m0 = -(t - z0) * 0.5 * np.pi / W                              # the rim's slope at its foot (x = -d, outward)
    vs = sp['voxel']
    lines, collars, clamps, sockets, scars = [], [], [], [], []
    crest, wall = C3['crest'] * D, C3['wall'] * D
    dg, wg = C3['crease'] * crest, C3['crease_fall'] * crest
    r_cr = (0.25 * wg * wg + dg * dg) / (2.0 * dg)
    for li, ln in enumerate(fd['lines']):
        lam, X = feed_samples(ln, ch, 0.5 * vs)
        F, _ = blockout_foot(prog, X)
        N = np.asarray(prog.normals(F, h=FOOT_H), np.float64)
        d = sdist(F)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(F, axis=0), axis=1))])
        bead = np.where(np.abs(d - g['d']) < g['r'], g['z'] + np.sqrt(np.maximum(g['r'] ** 2 - (d - g['d']) ** 2, 0.0)),
                        -np.inf)
        z_srf = np.maximum(junction_top(des, d), bead)
        uu = np.clip(-d / X1, 0.0, 1.0)
        h00, h10, h01 = 2 * uu ** 3 - 3 * uu ** 2 + 1, uu ** 3 - 2 * uu ** 2 + uu, -2 * uu ** 3 + 3 * uu ** 2
        z_lie = np.where(d < 0.0, h00 * (z0 + c) + h10 * X1 * m0 + h01 * c + r, z_srf + r + c)
        geo = feed_line(ln, F, N, s, z_lie, z_srf, r, lam)
        on_skin = np.zeros(len(geo['P']), bool)
        lying = np.isfinite(geo['s'])
        on_skin[lying] = np.interp(geo['s'][lying], s, d) < -X1
        lines.append(dict(kind=ln['kind'], C=geo['P'], piece=geo['piece'], s=geo['s'], on_skin=on_skin, r=r,
                          s_lo=geo['s_lo'], s_hi=geo['s_hi'], route=dict(F=F, N=N, s=s, d=d, z_lie=z_lie, z_srf=z_srf)))
        for col in geo['collars']:
            col['line'] = li
            col['plate'] = int(ln['ends'][0 if col['end'] == 0 else 1]['plate'])
            collars.append(col)
        for cl in geo['clamps']:
            cl['line'] = li
            clamps.append(cl)
        sk = geo['socket']
        if sk is not None:
            # the socket in the skin's terms: the plunge from where the cable's underside meets the skin (theta_u on its
            # arc: R cos = (R - h) / (R - r), h the axis's height there), the collar's wall and crest, the crease against
            # it (a groove round the collar's foot, its centre a quarter of its width past the wall, C3b's), the scar
            # band from the cable's surface to the collar's wall + scar_w D
            Rp = C3['plunge_R']
            h_l = float(z_lie[-1] - z_srf[-1])
            th_u = math.acos(max(-1.0, min(1.0, (Rp - h_l) / (Rp - r))))
            Pp = sk['P']
            sg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))])
            sk.update(line=li, Pm=Pp[max(0, int(np.searchsorted(sg, Rp * th_u)) - 1):], th_u=th_u, R_wall=r + wall,
                      crest=crest, R_cr=r + wall + 0.25 * wg, r_cr=r_cr, z_cr=r_cr - dg, depth=dg, width=wg,
                      R_band=r + wall + C3['scar_w'] * D)
            sockets.append(sk)
            scars.append(dict(F=sk['E'], n=sk['n'], r0=r, r1=sk['R_band'], line=li))
    r_max = max([C3['lug'][1] * r] * len(clamps) + [math.hypot(c_['boss'][2], C3['boss_h'] * r) for c_ in collars] + [r])
    return dict(params=P, lines=lines, collars=collars, clamps=clamps, sockets=sockets, scars=scars, r=r, D=D,
                r_max=r_max, vs=vs, band=sp['band'], k_flesh=max(C3['k_flesh'], 0.5 * GRID_ROUND * vs), prog=prog)


def _resample_by(P, step):
    """a polyline resampled every ~step of its length (its ends kept)"""
    P = np.asarray(P, np.float64)
    sg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    q = np.linspace(0.0, sg[-1], max(2, int(math.ceil(sg[-1] / step)) + 1))
    return np.column_stack([np.interp(q, sg, P[:, k]) for k in range(3)])


def feed_bounds(fp):
    """the feed's activation spheres (voxel.SparseSDF(extra=)): along every cable (each 1 mm, its radius + the bake's
    reach: the occluders' voxels), round every collar's boss and ferrule and every clamp, along every socket's plunge
    (its scar band's reach) and round its centre; all of them (the cable on the plates stands past the band)"""
    if fp is None:
        return np.zeros((0, 3)), np.zeros(0)
    pad = FEED_ACT_VOX * fp['vs']
    C, R = [], []
    for ln in fp['lines']:
        Q = _resample_by(ln['C'], 1.0e-3)
        C.append(Q)
        R.append(np.full(len(Q), ln['r'] + pad))
    for c in fp['collars']:
        for A, B, ra in (c['boss'], c['fer']):
            C.append(0.5 * (A + B)[None])
            R.append(np.array([math.hypot(ra, 0.5 * float(np.linalg.norm(B - A))) + pad]))
    for c in fp['clamps']:
        C.append(c['C'][None])
        R.append(np.array([float(np.linalg.norm(c['lug_h'])) + float(np.linalg.norm(c['lug_c'] - c['C'])) + pad]))
    for sk in fp['sockets']:
        Q = _resample_by(sk['P'], 1.0e-3)
        C += [Q, sk['E'][None]]
        R += [np.full(len(Q), sk['R_band'] + pad), np.array([sk['R_band'] + sk['width'] + pad])]
    return np.concatenate(C), np.concatenate(R)


def feed_fields(fp, X):
    """the feed's components at points X (3D; C3d): dict(sweep (the cables: the distance to the nearest centreline less
    r), line (its index), can (the collars: boss and ferrule), clamp (the clamps: band and lug), ring (each socket's
    soft-tissue collar: apply_feed adds it), crease (the groove round it: apply_feed carves it), rho (the distance to the
    nearest socket's plunge, from where the cable's underside meets the skin), scar (the socket's band weight 0-1 by rho,
    on the skin's own neighbourhood), socket (its index, -1: none)); +inf where a kind is absent. The cables, collars and
    clamps are the bake's occluders (feed_occluders), the sockets' collars and creases the skin's relief"""
    X = np.atleast_2d(np.asarray(X, np.float64))
    n = len(X)
    out = dict(sweep=np.full(n, np.inf), line=np.full(n, -1), can=np.full(n, np.inf), clamp=np.full(n, np.inf),
               ring=np.full(n, np.inf), crease=np.full(n, np.inf), rho=np.full(n, np.inf), scar=np.zeros(n),
               socket=np.full(n, -1))
    if fp is None or not n:
        return out
    dist, li, _, _ = _multi_closest(X, [ln['C'] for ln in fp['lines']])
    out['sweep'], out['line'] = dist - fp['r'], li
    for c in fp['collars']:
        for A, B, ra in (c['boss'], c['fer']):
            out['can'] = np.minimum(out['can'], _sd_cyl_np(X, A, B, ra, min(0.12e-3, 0.3 * ra)))
    for c in fp['clamps']:
        out['clamp'] = np.minimum(out['clamp'], np.minimum(
            _sd_cyl_np(X, c['A'], c['B'], c['ra'], min(0.05e-3, 0.3 * c['hl'])),
            _sd_box_np(X, c['lug_c'], np.stack([c['x'], c['y'], c['z']]), c['lug_h'])))
    if fp['sockets']:
        zs = np.asarray(fp['prog'].eval(X), np.float64)          # the height over the skin (the block-out's distance)
        w0 = 0.35e-3
        for k, sk in enumerate(fp['sockets']):
            rho = _polyline_dist(X, [sk['Pm']])
            out['ring'] = np.minimum(out['ring'], np.maximum(rho - sk['R_wall'], zs - sk['crest']))
            out['crease'] = np.minimum(out['crease'], np.hypot(rho - sk['R_cr'], zs - sk['z_cr']) - sk['r_cr'])
            nearer = rho < out['rho']
            out['socket'] = np.where(nearer, k, out['socket'])
            out['rho'] = np.minimum(out['rho'], rho)
            band = _smooth(rho, fp['r'] - w0, fp['r'] + w0) * (1.0 - _smooth(rho, sk['R_band'] - w0, sk['R_band'] + w0))
            out['scar'] = np.maximum(out['scar'], np.where(np.abs(zs) <= FEED_REACH, band, 0.0))
    return out


def feed_voxels(G, fp, margin=0.0, which='socket'):
    """the voxels of G near the feed (C3d): which 'socket', round the sockets (their collars added, their creases carved,
    their scar ids: within the band + 2 voxels + margin of a collar or a crease, or inside a scar band's reach), or
    'occluder', round the cables, collars and clamps (within the band + 2 voxels + margin of their surfaces). Returns
    (indices, positions, feed_fields there)"""
    from scipy.spatial import cKDTree
    reach = fp['band'] + 2.0 * G.vs + margin
    if which == 'socket':
        if not fp['sockets']:
            return np.zeros(0, np.int64), np.zeros((0, 3)), feed_fields(fp, np.zeros((0, 3)))
        pts = np.concatenate([_resample_by(sk['P'], 0.5e-3) for sk in fp['sockets']])
        big = max(sk['R_band'] + sk['width'] for sk in fp['sockets']) + reach
    else:
        pts = np.concatenate([_resample_by(ln['C'], 0.5e-3) for ln in fp['lines']] +
                             [c['C'][None] for c in fp['clamps']] + [c['E'][None] for c in fp['collars']])
        big = fp['r_max'] + 3.0 * fp['r'] + reach
    lo, hi = pts.min(0) - big, pts.max(0) + big
    ijk = G.ijk.numpy()
    a = np.floor((lo - G.origin) / G.vs).astype(np.int64)
    b = np.ceil((hi - G.origin) / G.vs).astype(np.int64)
    inb = np.ones(len(ijk), bool)
    for k in range(3):
        inb &= (ijk[:, k] >= a[k]) & (ijk[:, k] <= b[k])
    sel = np.nonzero(inb)[0]
    Pv = G.origin + ijk[sel].astype(np.float64) * G.vs
    del ijk, inb
    close = cKDTree(pts).query(Pv, distance_upper_bound=big)[0] < big        # (the box's far voxels out first)
    sel, Pv = sel[close], Pv[close]
    f = feed_fields(fp, Pv)
    if which == 'socket':
        near = (f['ring'] < reach) | (f['crease'] < reach) | \
            (f['rho'] < max(sk['R_band'] for sk in fp['sockets']) + reach)
    else:
        near = np.minimum.reduce([f['sweep'], f['can'], f['clamp']]) < reach
    return sel[near], Pv[near], {k: v[near] for k, v in f.items()}


def apply_feed(G, fp, log=print):
    """THE FEED IN THE HIGH (C3d), on a SparseSDF G after the plates (apply_surface): only the skin's own relief at each
    socket, its crease carved (the walls keep the skin's id) and its soft-tissue collar added by a smooth union (flesh:
    the skin's id where it wins), then its scar band (cyb_scar on the skin voxels at the surface over the band). The
    cables, collars and clamps stand out of the high: they are the AO / cavity rays' occluders (feed_occluders). Returns
    (counts, the voxels it reads, for the relevel to keep)"""
    import time
    t0 = time.time()
    idx, Pv, f = feed_voxels(G, fp, margin=RELEVEL_MARGIN, which='socket')
    if not len(idx):
        out = dict(voxels=0, sockets=0, collar_won=0, scar_voxels=0, seconds=time.time() - t0)
        log('[cyborg] feed in the high (C3d): no socket; the cables, collars and clamps are the occluders')
        return out, idx
    v = G.val.numpy()
    m = G.mat.numpy()
    vj = v[idx].astype(np.float64)
    vj = _smax_np(vj, -f['crease'], fp['k_flesh'])          # 1. the creases, carved
    win = f['ring'] < vj
    vj = _smin_np(vj, f['ring'], fp['k_flesh'])             # 2. the soft-tissue collars, added (flesh)
    v[idx] = vj.astype(np.float32)
    mj = m[idx]
    mj[win] = 0
    m[idx] = mj
    G.val.assign(v)
    G.mat.assign(m)
    v = G.val.numpy()                                       # 3. the scar bands: skin voxels at the surface
    m = G.mat.numpy()
    band = (f['scar'] > 0.5) & (m[idx] == 0) & (np.abs(v[idx]) < 1.5 * G.vs)
    m[idx[band]] = CYBORG_ID['cyb_scar']
    G.mat.assign(m)
    out = dict(voxels=len(idx), sockets=len(fp['sockets']), collar_won=int(win.sum()), scar_voxels=int(band.sum()),
               seconds=time.time() - t0)
    log(f'[cyborg] feed in the high (C3d): {out["sockets"]} sockets sculpted over {out["voxels"]:,} voxels (the collars '
        f'won {out["collar_won"]:,}, {out["scar_voxels"]:,} scar voxels); the {len(fp["lines"])} cables, '
        f'{len(fp["collars"])} collars and {len(fp["clamps"])} clamps stand out of the high (the occluders); '
        f'{out["seconds"]:.1f}s')
    return out, idx


def feed_occluders(G, fp, log=print):
    """THE FEED'S OCCLUDERS (C3d; the notes over FEED): the AO / cavity rays' field (bake.py reads field.val_occ) with the
    cables, collars and clamps in it, as the runtime draws them resting on the surface the viewer sees: G.val_occ when
    set (the geometric suckers', octopus_suckers.occluder_values), else G.val, and in every voxel near the feed the union
    with their true distances (|grad| <= 1). t10 calls it after the suckers' occluders (BESTIARY_CYBORG). Returns a
    wp.array on G's device; fp None: the field as it was"""
    import time
    t0 = time.time()
    base = getattr(G, 'val_occ', None)
    base = G.val if base is None else base
    if fp is None:
        return base
    idx, _, f = feed_voxels(G, fp, which='occluder')
    a = base.numpy().copy()
    fo = np.minimum.reduce([f['sweep'], f['can'], f['clamp']])
    took = fo < a[idx]
    a[idx] = np.minimum(a[idx], fo).astype(np.float32)
    log(f'[cyborg] feed occluders (C3d): {len(idx):,} voxels near the {len(fp["lines"])} cables, {len(fp["collars"])} '
        f'collars and {len(fp["clamps"])} clamps, {int(took.sum()):,} of them take a part; {time.time() - t0:.1f}s')
    return wp.array(a, dtype=wp.float32, device=base.device)


def feed_skin_mask(fp, F, rad, margin):
    """drop_skin_features' feed rule: the skin features (feet F on the block-out, footprint radii rad) that intrude on a
    dive's cable lying on the skin (its half width there + 1 mm + margin) or on a socket's collar, crease and scar band
    (+ margin)"""
    F = np.atleast_2d(np.asarray(F, np.float64))
    rad = np.broadcast_to(np.asarray(rad, np.float64), (len(F),))
    out = np.zeros(len(F), bool)
    if fp is None or not len(F):
        return out
    for ln in fp['lines']:
        if ln['kind'] == 'dive' and ln['on_skin'].sum() > 1:
            out |= _polyline_dist(F, [ln['C'][ln['on_skin']]]) < fp['r'] + 1.0e-3 + rad + margin
    for sk in fp['sockets']:
        out |= _polyline_dist(F, [sk['Pm']]) < sk['R_band'] + rad + margin
    return out


def feed_closeups(fd, ch):
    """the feed's close-ups for c3_closeups ([(tag, centre, span, views)]): the lines over the mantle, a clamp on its seam,
    a port, a dive leaving its plate, a socket"""
    out = []
    lines = fd['lines']
    if not lines:
        return out
    unit = lambda v: np.asarray(v, np.float64) / np.linalg.norm(v)

    def frame(uw):
        tu, tw, n, _ = ch.tangents(np.atleast_2d(np.asarray(uw, np.float64)))
        return tu[0], tw[0], n[0]
    pts = np.array([e['X'] for ln in lines for e in ln['ends']])
    ctr = 0.5 * (pts.min(0) + pts.max(0))
    uw_c = ch.to_uw(ctr[None])[0]
    tu, tw, n = frame(uw_c)
    out.append(('feed', ch.from_uw(uw_c[None])[0], 1.25 * float(np.max(pts.max(0) - pts.min(0))),
                (n, unit(n + 0.9 * tu))))
    seam_c = [(ln, c) for ln in lines for c in ln['clamps'] if c['why'] == 'seam']
    if seam_c:
        ln, c = seam_c[0]
        tu, tw, n = frame(c['uw'])
        ax = unit(np.asarray(ln['ends'][-1]['X']) - np.asarray(ln['ends'][0]['X']))
        side = unit(np.cross(n, ax))
        out.append(('feed_clamp', c['X'], 0.012, (unit(n + 0.25 * side), unit(n * 0.55 + side * 0.85))))
    e = lines[0]['ends'][0]
    tu, tw, n = frame(e['uw'])
    ln = lines[0]
    ax = unit(np.asarray(ln['ends'][-1]['X']) - np.asarray(ln['ends'][0]['X']))
    side = unit(np.cross(n, ax))
    out.append(('feed_port', e['X'], 0.016, (unit(n * 0.8 + ax * 0.6), unit(n * 0.5 + side * 0.86))))
    dives = [ln for ln in lines if ln['kind'] == 'dive']
    if dives:
        ln = dives[0]
        tu, tw, n = frame(ln['outline']['uw'])
        ax = unit(np.asarray(ln['ends'][-1]['X']) - np.asarray(ln['ends'][0]['X']))
        side = unit(np.cross(n, ax))
        out.append(('feed_dive', ln['outline']['X'], 0.024, (unit(n + 0.3 * side), unit(n * 0.35 + side * 0.94))))
        g = ln['ends'][-1]
        tu, tw, n = frame(g['uw'])
        out.append(('feed_socket', g['X'], 0.016, (unit(n + 0.3 * ax), unit(n * 0.55 - ax * 0.8 + side * 0.25))))
    return out


# ---------------------------------------------------------------------------------------------- the material pass
# CYBORG_TEXEL (CYBORG_PLAN §5.2, A.5.2, A.7 U8 / U10; the lead's C3 brief: "the cyborg rows' materials: house white
# paint, black oxide fasteners, the gasket, the scar"): a pass over the skin's finished maps (octopus_skin.run's), so
# the skin pass stays as it is. Every texel of the layout's footprint gets the low's point under it (layout_texels),
# its foot on the block-out and so its SIGNED DISTANCE d to the outline there (the surface plan's own sdist), and the
# nearest head as the bake reads it (D / 2 / grow). The layers are PAINTED FROM d, not from the voxels' ids (the C2
# check: the gasket's and the scar's ids comb at the voxel pitch; U10's id-edge blend by construction): the scar band
# over the skin's fall (d_lo..d_c), the crease's floor left skin (the AO darkens it), the gasket's visible flank
# (x_vis..0), the plate from 0 (its rolled rim and flat; the seams keep the plate's paint, dark by the cavity's dirt),
# the heads where the bake shows them; each edge soft over 0.6 texel. The stack in study T's order: the layer by row
# (row_values: the house white at its paint roughness, black oxide metal 0, the gasket at the house's rubber, the scar a
# paler glossier tint of the skin); per plate and per head a value and roughness draw inside the row's range; WEAR, an
# EDGE rule (A.2.1): paint to titanium on the rolled rim's convex top in worn STRETCHES broken into chips (low-frequency
# stretch x mid-frequency chip noise), a few scuffs on the flats, none within 0.3 mm of a head, and THE LIP GUARD (A.5.2:
# wear stands down within 0.6-1.2 mm of a crease or recess; A.2.3: without it every seam lip chips as a dash): none
# within 0.6 mm of a seam's lip, all of it past 1.2 mm, as the mech tentacle's pass guards its seams (cyborg_limb.py);
# its level the share of plate texels it bares (WEAR_LEVEL: 6 %, inside G9's 5-15 % with the flats under A.2.1's 4.4 %:
# at 9 % the guarded field puts 4.9 % on the default look's flats; the level itself is Skye's call, A.9); the heads'
# black oxide worn to bare steel on stretches of their top edge; a dark hex socket in each
# head (texture tier, ~4 texels); DIRT by multiply in the seams and cavities (never add-then-threshold); no world-up
# stain (A.2.3: the octopus moves). The skin's own terms fade by the cyborg share: its texture-tier relief (the plate
# texels take the BAKED normal and AO), its subsurface, its display masks; the GROWTH pack's R carries the share, so
# every skin-only runtime term holds off the plates (bestiary.js displayGrowth), and the ORM ships lossless (t13).
# THE LEAD'S C3b CALLS: (1) the chips are a COVERAGE: the wear field is read on WEAR_SS x WEAR_SS sub-samples per texel
# (their low points through the texel's own UV Jacobian; d, the seam and the head distances carried across the texel by
# its gradients) and each texel takes the share of them worn, so a chip's edge falls inside its texels instead of on
# their grid (no per-texel stairs; its metal the coverage's, so G9 reads the worn metal on FULLY worn texels); (2) the
# rim's straight dashes broken up: the exposure about the rim's convex shoulder is a Gaussian whose centre and width
# wander along the edge (7 / 5 mm fields), cut into separate chips by a 2.6 mm gate and a domain-warped chip field, so
# no chip is clipped straight by a band's edge; (3) the scar band made to read: the skin desaturated to SCAR_KEEP of its
# chroma and lifted into the row's pale pink-cream (palest at the crease), its roughness the row's 0.08 under the wet
# skin's; the level stays 6 % (Skye's call, A.9). (4) the FEED's own pass follows the plates' (feed_texel: C3d, the
# sockets' scar bands; the cables are geometry)
WEAR_LEVEL = 0.06
WEAR_SOFT = 0.15           # the chips' edge: this share of the wear field's threshold either side of it (per sub-sample
                           # now: WEAR_SUB_SOFT, the coverage carries the edge)
WEAR_SS = 4                # sub-samples per texel edge for the chips' coverage (16 per texel)
WEAR_SUB_SOFT = 0.02       # a sub-sample's own chip edge, in shares of the threshold (crisp: the coverage blends)
SCAR_KEEP = 0.45           # the scar band keeps this share of the skin's chroma (the rest its luminance)
SCAR_FLAT = 0.5            # ... and moves its luminance this share (in log) from its own skin toward the skin BESIDE it
SCAR_REF = 4.0e-3          # that reference: the skin past the band, a masked Gaussian of this sigma (m) over the texels
LUM_W = np.array([0.2126, 0.7152, 0.0722])
EDGE_SOFT_TX = 0.6          # every layer's edge, in texels


def _hash01(ix, iy, iz, seed):
    """lattice values in [0, 1) (int64 wrap-around hashing)"""
    k = (ix * np.int64(73856093)) ^ (iy * np.int64(19349663)) ^ (iz * np.int64(83492791)) ^ np.int64(seed * 2654435761 % (1 << 31))
    k = (k ^ (k >> 13)) * np.int64(1274126177)
    k = k ^ (k >> 16)
    return (k & np.int64(0xFFFFFF)).astype(np.float64) / float(0x1000000)


def _vnoise(P, cell, seed):
    """3D value noise in [0, 1] at points P (n, 3), lattice spacing `cell` (m), smoothstep-weighted"""
    Q = np.asarray(P, np.float64) / cell
    i0 = np.floor(Q).astype(np.int64)
    f = Q - i0
    w = f * f * (3.0 - 2.0 * f)
    out = np.zeros(len(Q))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wt = (w[:, 0] if dx else 1 - w[:, 0]) * (w[:, 1] if dy else 1 - w[:, 1]) * (w[:, 2] if dz else 1 - w[:, 2])
                out += wt * _hash01(i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz, seed)
    return out


def _fbm(P, cell, seed, octaves=3):
    a, s, n = 1.0, 0.0, 0.0
    for o in range(octaves):
        s += a * _vnoise(P, cell / (2 ** o), seed + 101 * o)
        n += a
        a *= 0.5
    return s / n


def _smooth(x, a, b):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _tex_grad(v, ys, xs, h, w):
    """a field known at texels (ys, xs) of an (h, w) box: its texel gradients (per texel along x and along y) at those
    texels, central where both neighbours are known, one-sided where one is, 0 where none (the wear's sub-samples carry
    d and the seam and head distances across a texel by them)"""
    G = np.full((h + 2, w + 2), np.nan)
    G[ys + 1, xs + 1] = v
    c = G[ys + 1, xs + 1]

    def one(p, m):
        fp_, fm_ = np.isfinite(p), np.isfinite(m)
        return np.where(fp_ & fm_, 0.5 * (p - m), np.where(fp_, p - c, np.where(fm_, c - m, 0.0)))
    return one(G[ys + 1, xs + 2], G[ys + 1, xs]), one(G[ys + 2, xs + 1], G[ys, xs + 1])


def cyborg_texel(maps, drivers, low, plates, prog, size, set_name='head', wear_level=WEAR_LEVEL, log=print):
    """the C3 material pass (the notes above) over one texture set's skin maps (octopus_skin.run's dict: image order,
    uint8: albedo, normal, orm, masks, display, growth). plates: load_plates' record (None: the layer OFF, the maps
    returned untouched, the same objects). drivers: the set's bake (bake.py's image order: normal, ao, cavity, mat; the
    stats' arrays are texel order, ys / xs the texel's row and column with v up). Returns
    (maps, stats): only texels of the footprint the layer covers change (and the gutter texels copied from them)"""
    import time
    from scipy import ndimage
    from scipy.spatial import cKDTree
    if plates is None:
        return maps, None
    t0 = time.time()
    lay = plates['layout']
    P_ = lay['params']
    if P_['set'] != set_name:
        return maps, None
    dens = UVDensity(low)
    chart = body_chart(low)
    sp = surface_plan(lay, chart, prog, dens, band=C3_BAND, voxel=P_['voxel'])
    des = sp['design']
    res = layout_texels([lay], [chart], low, set_name, size=size)
    x0, y0, w, h = res['x0'], res['y0'], res['w'], res['h']
    # the bake's arrays are IMAGE order (forge/bake.py: row 0 is v = 1); layout_texels' are TEXEL order (row y up from
    # v = 0): the drivers read in texel order through these
    cov_all = (np.asarray(drivers['normal'])[..., 3] > 0)[::-1]
    tbox = lambda a: np.asarray(a)[size - y0 - h:size - y0][::-1][:, x0:x0 + w]
    bx = (slice(y0, y0 + h), slice(x0, x0 + w))               # texel order (row = y, up from v = 0)
    cov = cov_all[bx]
    m = cov & (res['lay'] == 0) & np.all(np.isfinite(res['p']), axis=-1)
    ys, xs = np.nonzero(m)
    Pt = res['p'][ys, xs]
    F, _ = blockout_foot(prog, Pt)
    d = sp['sdist'](F)
    tex = 1.0 / float(np.median(dens.px_iso(Pt[::max(1, len(Pt) // 4000)])))   # the texel's size here (m)
    sg = EDGE_SOFT_TX * tex
    sstep = lambda x, x0_: _smooth(x, x0_ - sg, x0_ + sg)
    # the heads where the bake shows them: radius D / 2 / grow on the low
    FP = np.array([f['p'] for f in lay['fasteners']]) if lay['fasteners'] else np.zeros((0, 3))
    if len(FP):
        fd, fk = cKDTree(FP).query(Pt)
        rD = np.array([0.5 * f['D'] / f['grow'] for f in lay['fasteners']])[fk]
        fN = np.array([f['normal'] for f in lay['fasteners']])[fk]
    else:
        fd, fk, rD, fN = np.full(len(Pt), np.inf), np.zeros(len(Pt), int), np.ones(len(Pt)), np.zeros((len(Pt), 3))
    # the layers' weights (soft over 0.6 texel), from d and the heads
    w_plate = sstep(d, 0.0)
    w_gask = sstep(d, des['gasket']['x_vis']) * (1.0 - w_plate)
    if des['trough'] is not None:
        w_scar = sstep(d, des['trough']['d_lo']) * (1.0 - sstep(d, des['trough']['d_c']))
    else:
        w_scar = sstep(d, des['scar'][0]) * (1.0 - sstep(d, des['scar'][1])) * (1.0 - w_plate - w_gask)
    w_steel = (1.0 - sstep(fd, rD)) * w_plate
    w_paint = w_plate - w_steel
    share = np.clip(w_plate + w_gask + w_scar, 0.0, 1.0)
    # rows (row_values: the house white, black oxide, the gasket, the scar)
    fin = dict(paint=P_['paint'], accent=P_['accent'] or ACCENT_DEFAULT, paint_type=P_['paint_type'],
               fastener_finish=P_['fastener_finish'], glow_finish=P_['glow_finish'])
    rv = {nm: row_values(nm, **fin) for nm in CYBORG_NAMES}
    c0 = lambda nm: np.array([rv[nm]['c0r'], rv[nm]['c0g'], rv[nm]['c0b']])
    c1 = lambda nm: np.array([rv[nm]['c1r'], rv[nm]['c1g'], rv[nm]['c1b']])
    seed = int(P_['seed'])
    rng = np.random.default_rng([seed, 4242])
    npl = len(lay['plates'])
    pl_L = 1.0 + rv['cyb_paint']['jit_L'] * rng.standard_normal(npl)
    pl_r = rng.uniform(-1.0, 1.0, npl)
    plate_i = np.clip(res['plate'][ys, xs], 0, max(npl - 1, 0))
    accent = np.array([p['paint'] == 'accent' for p in lay['plates']] or [False])[plate_i]
    paint_nm = np.where(accent, 'cyb_paint_accent', 'cyb_paint')
    base_p = np.where(accent[:, None], c0('cyb_paint_accent')[None], c0('cyb_paint')[None]) * pl_L[plate_i][:, None]
    rough_p = rv['cyb_paint']['rough'] + rv['cyb_paint']['rough_facet'] * pl_r[plate_i]
    # WEAR: an edge rule, in worn stretches (the notes above)
    W_rim = des['rim']['W']
    seam_hw = 0.5 * P_['seam_w']
    sd = res['seam_d'][ys, xs]
    # the rolled rim's convex SHOULDER (its quarter sine turns over onto the flat at d = W); inside worn STRETCHES (a 12 mm
    # field, about half the edges) the paint goes in ragged CHIPS; on the flats sparse scuffs. The seam lips carry NO
    # exposure: A.5.2's lip guard (the C3 check, 10-22: as built they took a third of the rim's weight and 54 % of the lip
    # texels wore, a grey dash down both sides of every seam). THE LEAD'S C3b CALLS (the notes above): the exposure a
    # Gaussian about the shoulder whose centre and width wander along the edge (C3's flat-topped band clipped every chip
    # into a straight dash parallel to the outline), cut into separate chips by a 2.6 mm gate, the chip field domain-
    # warped; the whole field read on WEAR_SS x WEAR_SS sub-samples per texel and averaged into a coverage
    paint_any = w_paint > 1e-6
    paint_m = w_paint > 0.5
    stretch = _smooth(_fbm(Pt, 12.0e-3, seed + 11, 2), 0.46, 0.58)
    gate_c = _smooth(_fbm(Pt, 2.6e-3, seed + 13, 2), 0.36, 0.52)
    d_c = W_rim * (0.93 + 0.20 * (_fbm(Pt, 7.0e-3, seed + 17, 2) - 0.5))
    s_w = W_rim * (0.20 + 0.16 * _fbm(Pt, 5.0e-3, seed + 19, 2))
    warp = 0.55e-3 * (np.column_stack([_fbm(Pt, 1.8e-3, seed + 29 + 7 * k, 2) for k in range(3)]) - 0.5)
    # the sub-samples: each texel's own UV Jacobian (texels per metre in its triangle's plane) inverted, its offsets in
    # [-0.5, 0.5) texel; d, the seam's and the head's distances carried across the texel by their texel gradients
    f_t, _, _ = dens.locate(Pt)
    J = dens.J[f_t]
    Jp = np.einsum('nji,njk->nik', J, np.linalg.inv(np.einsum('nij,nkj->nik', J, J)))      # (n, 3, 2): J^T (J J^T)^-1
    o1 = (np.arange(WEAR_SS) + 0.5) / WEAR_SS - 0.5
    ox, oy = (a_.ravel() for a_ in np.meshgrid(o1, o1, indexing='xy'))
    ip = np.nonzero(paint_any)[0]
    Wf = np.zeros(len(Pt))
    wear = np.zeros(len(Pt))
    tau = 1.0
    if len(ip):
        g_d, g_s, g_f = (_tex_grad(a_, ys, xs, h, w) for a_ in (d, sd, fd - rD))
        lin_ = lambda a_, g_: a_[ip, None] + g_[0][ip, None] * ox[None] + g_[1][ip, None] * oy[None]
        ds, sds, fds = lin_(d, g_d), lin_(sd, g_s), lin_(fd - rD, g_f)
        Ps = Pt[ip, None, :] + np.einsum('nij,sj->nsi', Jp[ip], np.column_stack([ox, oy]))
        Q = (Ps + warp[ip, None, :]).reshape(-1, 3)
        chip_s = _fbm(Q, 0.9e-3, seed + 23, 3).reshape(len(ip), -1)
        scuff_s = _fbm(Ps.reshape(-1, 3), 1.6e-3, seed + 37, 3).reshape(len(ip), -1)
        expo_s = np.exp(-((ds - d_c[ip, None]) / s_w[ip, None]) ** 2)
        Wf_s = (expo_s * (stretch * gate_c)[ip, None] * chip_s ** 1.5 +
                0.45 * _smooth(scuff_s, 0.70, 0.92) * (1.0 - expo_s))
        Wf_s *= _smooth(fds, 0.3e-3, 0.6e-3) * _smooth(sds - seam_hw, 0.6e-3, 1.2e-3)     # the head and lip guards
        sel_ = paint_m[ip]
        tau = float(np.quantile(Wf_s[sel_], 1.0 - wear_level)) if sel_.any() else 1.0
        soft = max(WEAR_SUB_SOFT * tau, 1e-5)
        wear[ip] = _smooth(Wf_s, tau - soft, tau + soft).mean(1)
        Wf[ip] = Wf_s.mean(1)
        expo = np.zeros(len(Pt))
        expo[ip] = expo_s.mean(1)
    else:
        expo = np.zeros(len(Pt))
    wear = wear * paint_any
    streak = 0.03 * (2.0 * _fbm(Pt * np.array([1.0, 1.0, 1.0]), 1.2e-3, seed + 51, 2) - 1.0)
    alb_paint = (1.0 - wear)[:, None] * base_p + wear[:, None] * c1('cyb_paint')[None]
    rgh_paint = (1.0 - wear) * rough_p + wear * (rv['cyb_paint']['rough1'] + streak)
    met_paint = wear * rv['cyb_paint']['metal1']
    # the heads: black oxide, each its own draw; worn to bare steel on stretches of the top edge; the hex socket
    hd_r = rng.uniform(-1.0, 1.0, max(len(FP), 1))[fk]
    hd_L = (1.0 + rv['cyb_steel']['jit_L'] * rng.standard_normal(max(len(FP), 1)))[fk]
    rr = fd / np.maximum(rD, 1e-9)
    hwear = _smooth(rr, 0.70, 0.82) * (1.0 - _smooth(rr, 0.97, 1.05)) * _smooth(_fbm(Pt, 1.0e-3, seed + 61, 2), 0.50,
                                                                                    0.62)
    # the socket: a hexagon of circumradius 0.26 D / grow in the head's plane (its x from the head's normal)
    if len(FP):
        e1 = np.cross(fN, [0.0, 0.0, 1.0])
        e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
        e2 = np.cross(fN, e1)
        v_ = Pt - FP[fk]
        a_, b_ = np.einsum('nd,nd->n', v_, e1), np.einsum('nd,nd->n', v_, e2)
        hexd = np.maximum(np.abs(a_) * 0.8660254 + np.abs(b_) * 0.5, np.abs(b_))
        sock = 1.0 - _smooth(hexd / np.maximum(rD, 1e-9), 0.44, 0.52)
    else:
        sock = np.zeros(len(Pt))
    alb_steel = ((1.0 - hwear)[:, None] * (c0('cyb_steel')[None] * hd_L[:, None]) +
                 hwear[:, None] * c1('cyb_steel')[None]) * (1.0 - 0.6 * sock)[:, None]
    rgh_steel = ((1.0 - hwear) * (rv['cyb_steel']['rough'] + rv['cyb_steel']['rough_facet'] * hd_r) +
                 hwear * rv['cyb_steel']['rough1'] + 0.15 * sock)
    met_steel = hwear * rv['cyb_steel']['metal1'] + (1.0 - hwear) * rv['cyb_steel']['metal']
    # the skin's own result (the scar re-shades it) and the bake's drivers at these texels
    rows_img = size - 1 - (y0 + ys)                            # image rows (row 0 is v = 1)
    cols = x0 + xs
    a8 = maps['albedo'][rows_img, cols, :3].astype(np.float64) / 255.0
    skin_lin = a8 ** 2.2
    # the band's reference tone (scar_colour): the skin past it, 1-9 mm out from its skin side, off the feed lines
    dlo = des['trough']['d_lo'] if des['trough'] is not None else des['scar'][0]
    bes = (d < dlo - 1.0e-3) & (d > dlo - 9.0e-3)
    if sp.get('feed') is not None and bes.any():
        ib = np.nonzero(bes)[0]
        f_ = feed_fields(sp['feed'], Pt[ib])
        bes[ib] = ((np.minimum.reduce([f_['sweep'], f_['can'], f_['clamp'], f_['ring']]) > 2.0e-3) &
                   (f_['rho'] > max([sc['r1'] for sc in sp['feed']['scars']] + [0.0]) + 0.3e-3))
    ref_scar = beside_tone(skin_lin @ LUM_W, bes, ys, xs, h, w, SCAR_REF / tex)
    scar_col = scar_colour(skin_lin, c0('cyb_scar'), _smooth(d, des['scar'][0], des['scar'][1]), ref_scar)
    alb_gask = np.broadcast_to(c0('cyb_gasket'), skin_lin.shape)
    cav = tbox(drivers['cavity'])[ys, xs].astype(np.float64)
    ao_d = tbox(drivers['ao'])[ys, xs].astype(np.float64)
    dirt = (1.0 - _smooth(cav, 0.55, 0.92)) * (0.75 + 0.25 * _fbm(Pt, 3.0e-3, seed + 71, 2))
    grime = (1.0 - 0.42 * dirt)[:, None]
    cyb_alb = (w_paint[:, None] * alb_paint * grime + w_steel[:, None] * alb_steel * grime +
               w_gask[:, None] * alb_gask * grime + w_scar[:, None] * scar_col)
    cyb_rgh = (w_paint * (rgh_paint + 0.12 * dirt) + w_steel * (rgh_steel + 0.08 * dirt) +
               w_gask * (rv['cyb_gasket']['rough'] + 0.05 * dirt) + w_scar * rv['cyb_scar']['rough'])
    cyb_met = w_paint * met_paint + w_steel * met_steel
    # blend into the skin's maps: albedo (linear), roughness / metal / AO (the baked AO on cyborg texels), the BAKED
    # normal (the skin's texture tier off the plates)
    lin = np.clip((1.0 - share)[:, None] * skin_lin + cyb_alb, 0.013, 0.87)
    lin = np.where(share[:, None] > 0.0, lin, skin_lin)
    orm = maps['orm'][rows_img, cols, :3].astype(np.float64) / 255.0
    o_ao = (1.0 - share) * orm[:, 0] + share * ao_d
    o_r = np.clip((1.0 - share) * orm[:, 1] + cyb_rgh, 0.0, 1.0)
    o_m = np.clip((1.0 - share) * orm[:, 2] + cyb_met, 0.0, 1.0)
    n_sk = maps['normal'][rows_img, cols, :3].astype(np.float64) / 255.0 * 2.0 - 1.0
    n_bk = tbox(drivers['normal'])[ys, xs, :3].astype(np.float64)
    n_bk /= np.maximum(np.linalg.norm(n_bk, axis=1, keepdims=True), 1e-9)
    n_o = (1.0 - share)[:, None] * n_sk + share[:, None] * n_bk
    n_o /= np.maximum(np.linalg.norm(n_o, axis=1, keepdims=True), 1e-9)
    msk = maps['masks'][rows_img, cols].astype(np.float64) / 255.0
    hard = np.clip(w_plate + w_gask, 0.0, 1.0)
    msk[:, 0] *= 1.0 - hard                                    # no subsurface through a plate (the scar keeps its own)
    msk[:, 2] *= 1.0 - share
    dsp = maps['display'][rows_img, cols].astype(np.float64) / 255.0
    dsp[:, :3] *= (1.0 - share)[:, None]
    dsp[:, 3] = 0.5 + (dsp[:, 3] - 0.5) * (1.0 - share)
    grw = maps['growth'][rows_img, cols].astype(np.float64) / 255.0
    grw[:, 0] = np.maximum(grw[:, 0], share)
    grw[:, 1:3] *= (1.0 - share)[:, None]
    chg = share > 0.0
    out = {k: v.copy() for k, v in maps.items()}
    enc = lambda x: np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8)
    ri, ci = rows_img[chg], cols[chg]
    out['albedo'][ri, ci, :3] = enc(lin[chg] ** (1.0 / 2.2))
    out['orm'][ri, ci, :3] = enc(np.column_stack([o_ao, o_r, o_m])[chg])
    out['normal'][ri, ci, :3] = enc(n_o[chg] * 0.5 + 0.5)
    out['masks'][ri, ci] = enc(msk[chg])
    out['display'][ri, ci] = enc(dsp[chg])
    out['growth'][ri, ci] = enc(grw[chg])
    # the gutter: a gutter texel whose nearest covered texel changed takes its new value (octopus_skin.run's dilation:
    # nearest covered texel within 24 texels), over the footprint's box grown by 64 (its own distance transform there)
    pad = 64
    ya, yb = max(0, y0 - pad), min(size, y0 + h + pad)
    xa, xb = max(0, x0 - pad), min(size, x0 + w + pad)
    # the island's own texels are the CENTRE hits: the bake's half-covered edge texels (its 2 x 2 sub-samples reached
    # into a triangle, the texel's centre lies in none: alpha > 0 but no point of their own here) are gutter for this
    # pass (C3b: a feed line crossing a UV seam left them the skin's, and they stopped the copy beyond)
    cov_b = cov_all[ya:yb, xa:xb].copy()
    cov_b[y0 - ya:y0 - ya + h, x0 - xa:x0 - xa + w] &= res['hit']
    changed = np.zeros_like(cov_b)
    changed[(y0 + ys[chg]) - ya, (x0 + xs[chg]) - xa] = True
    dist, (iy, ix) = ndimage.distance_transform_edt(~cov_b, return_indices=True)
    inner = np.zeros_like(cov_b)
    inner[max(0, y0 - 24 - ya):min(yb - ya, y0 + h + 24 - ya), max(0, x0 - 24 - xa):min(xb - xa, x0 + w + 24 - xa)] = True
    gut = inner & ~cov_b & (dist <= 24) & changed[iy, ix]
    gy, gx = np.nonzero(gut)
    sy, sx_ = iy[gy, gx], ix[gy, gx]
    dst_r, src_r = size - 1 - (ya + gy), size - 1 - (ya + sy)
    for k in out:
        out[k][dst_r, xa + gx] = out[k][src_r, xa + sx_]
    # the gates' measures (G9 reads them; c03 checks them on the maps too). The wear is a COVERAGE now (the lead's C3b
    # call): its shares are coverage-weighted, the worn metal read on FULLY worn texels (coverage >= 0.99)
    ids = unpack_np(tbox(drivers['mat'])[ys, xs])
    lead_cyb = ids[:, 1] >= 0.5
    cw = lambda m_: float(wear[m_].sum() / max(int(m_.sum()), 1))
    full = (wear >= 0.99) & paint_m
    st = dict(texels=int(len(Pt)), changed=int(chg.sum()), gutter=int(len(gy)), texel_mm=tex * 1e3,
              plate=int((w_plate > 0.5).sum()), paint=int(paint_m.sum()), steel=int((w_steel > 0.5).sum()),
              gasket=int((w_gask > 0.5).sum()), scar=int((w_scar > 0.5).sum()),
              wear_share=cw(paint_m), wear_edge_share=cw(paint_m & (expo > 0.3)),
              wear_flat_share=cw(paint_m & (expo <= 0.05)),
              wear_fractional=int(((wear > 0.02) & (wear < 0.98) & paint_m).sum()), wear_full=int(full.sum()),
              head_worn_share=float(((hwear > 0.5) & (w_steel > 0.5)).sum() / max((w_steel > 0.5).sum(), 1)),
              titanium_metal_p50=float(np.median(o_m[full])) if full.any() else 0.0,
              ids_agree=float(np.mean(lead_cyb[w_plate > 0.5])) if (w_plate > 0.5).any() else 0.0,
              ids_outside=float(np.mean(lead_cyb[(share < 0.02)])) if (share < 0.02).any() else 0.0,
              wear_tau=tau, wear_ss=WEAR_SS, seconds=time.time() - t0)
    log(f'[cyborg] material pass ({set_name} {size}^2): {st["texels"]:,} footprint texels, {st["changed"]:,} changed '
        f'(+ {st["gutter"]:,} gutter); plate {st["plate"]:,} (paint {st["paint"]:,}, heads {st["steel"]:,}), gasket '
        f'{st["gasket"]:,}, scar {st["scar"]:,}; wear (a coverage of {WEAR_SS}x{WEAR_SS} sub-samples) on '
        f'{st["wear_share"]*100:.1f} % of the paint (edges {st["wear_edge_share"]*100:.1f} %, flats '
        f'{st["wear_flat_share"]*100:.1f} %; {st["wear_fractional"]:,} texels fractional, {st["wear_full"]:,} fully worn), '
        f'the heads\' rims {st["head_worn_share"]*100:.1f} %; fully worn titanium metal p50 {st["titanium_metal_p50"]:.3f}; '
        f'the bake\'s ids lead cyborg on {st["ids_agree"]*100:.1f} % of the painted plate, {st["ids_outside"]*100:.2f} % '
        f'outside the layer; {st["seconds"]:.1f}s')
    st['arrays'] = dict(ys=ys + y0, xs=xs + x0, d=d, share=share, w_plate=w_plate, w_paint=w_paint, w_steel=w_steel,
                        w_gask=w_gask, w_scar=w_scar, wear=wear, expo=expo, fd=fd, rD=rD)
    if sp.get('feed') is not None:
        # the feed's own pass over the plates' result (feed_texel: C3d, the sockets' scar bands); its share joins the arrays
        out, stf = feed_texel(out, drivers, low, sp['feed'], size, set_name, dens=dens, seed=seed, fin=fin, log=log)
        fa = stf.pop('arrays')
        key = lambda y_, x_: y_.astype(np.int64) * size + x_.astype(np.int64)
        kf = key(fa['ys'], fa['xs'])
        o_ = np.argsort(kf)
        kp = key(st['arrays']['ys'], st['arrays']['xs'])
        j_ = np.clip(np.searchsorted(kf[o_], kp), 0, len(kf) - 1)
        hit = kf[o_][j_] == kp
        st['arrays']['w_feed'] = np.where(hit, fa['share'][o_][j_], 0.0)
        st['arrays']['feed'] = fa                # (under 'arrays': t11 writes every other key to cyborg_material.json)
        st['feed'] = stf
    return out, st


def beside_tone(lum, mask, ys, xs, h, w, sigma_tx):
    """the skin's tone BESIDE a band, at every texel (ys, xs in an (h, w) box): the masked Gaussian (sigma_tx texels)
    of ln(luminance) over the texels flagged `mask`, as a luminance; nan where too little of the mask lies within
    reach (its weight under 0.02)"""
    from scipy import ndimage
    num = np.zeros((h, w))
    den = np.zeros((h, w))
    num[ys[mask], xs[mask]] = np.log(np.maximum(lum[mask], 1.0e-4))
    den[ys[mask], xs[mask]] = 1.0
    num = ndimage.gaussian_filter(num, sigma_tx, mode='constant', truncate=3.0)
    den = ndimage.gaussian_filter(den, sigma_tx, mode='constant', truncate=3.0)
    dd = den[ys, xs]
    return np.where(dd > 0.02, np.exp(num[ys, xs] / np.maximum(dd, 1.0e-12)), np.nan)


def scar_colour(skin_lin, tint, across, ref_lum=None):
    """THE SCAR BAND'S COLOUR (the lead's C3b call: made to read): the skin under it (linear, (n, 3)), its luminance
    moved SCAR_FLAT of the way (in log) toward ref_lum (beside_tone: the skin past the band; nan or None: its own),
    desaturated to SCAR_KEEP of its chroma and lifted by the cyb_scar row's tint, fully at the crease's edge (across 1)
    and to 0.7 of it at the band's skin side (across 0); kept inside the albedo range. The reference: the skin pass
    darkens the albedo in the junction's crease and fall (octopus_skin step 5: ln L from the local AO in crevices),
    which the band inherited (on the shipped default its skin x0.90 of the skin beside, x0.97 on the canonical's plain
    skin: the band read x1.245, not the x1.341 it reads on plain skin); a scar keeps half the skin's mottling (no
    chromatophores in scar tissue) and half the crease's grime"""
    lum = skin_lin @ LUM_W
    if ref_lum is not None:
        ok = np.isfinite(ref_lum) & (lum > 1.0e-6)
        s = np.ones(len(lum))
        s[ok] = (np.asarray(ref_lum)[ok] / lum[ok]) ** SCAR_FLAT
        skin_lin = skin_lin * s[:, None]
        lum = lum * s
    base = SCAR_KEEP * skin_lin + (1.0 - SCAR_KEEP) * lum[:, None]
    k = (0.7 + 0.3 * np.asarray(across, np.float64))[:, None]
    return np.minimum(base * (1.0 + (np.asarray(tint, np.float64)[None] - 1.0) * k), 0.87)


def feed_texel(maps, drivers, low, fp, size, set_name='head', dens=None, seed=0, fin=None, log=print, device=None):
    """THE FEED'S MATERIAL PASS (C3d) over a set's maps (after the plates'): the cables, collars and clamps are geometry
    (forge/cyborg_feed.py) and their shade on the plates and the skin is the bake's AO and cavity (feed_occluders), so
    this pass paints only the skin's own at each SOCKET: its SCAR BAND (scar_colour: the skin under it moved toward the
    skin beside it, desaturated and lifted by the row's tint, palest at the cable; the row's 0.08 roughness) over the
    soft-tissue collar, the crease and 0.85 D past the collar, read at the bake's hit (the low point raised the bake's
    HEIGHT along the low's normal: the sculpted collar's skin) by the cable's distance there; the skin's own terms faded
    by the band's share, which joins the GROWTH pack's R. Returns (maps, stats with its arrays)"""
    import time
    from scipy import ndimage
    t0 = time.time()
    dens = dens or UVDensity(low)
    fin = fin or {}
    rv = {nm: row_values(nm, **fin) for nm in CYBORG_NAMES}
    c0 = lambda nm: np.array([rv[nm]['c0r'], rv[nm]['c0g'], rv[nm]['c0b']])
    P = fp['params']
    none = lambda: (maps, dict(texels=0, changed=0, gutter=0, scar=0, sockets=0, seconds=time.time() - t0,
                               arrays=dict(ys=np.zeros(0, int), xs=np.zeros(0, int), share=np.zeros(0),
                                           w_feed=np.zeros(0), w_scar=np.zeros(0))))
    fs = np.asarray(low['face_set']).astype(str)
    sel = np.nonzero(fs == set_name)[0]
    if not len(sel) or not fp['sockets']:
        return none()
    # the sockets' texel box: their mouths on the low, grown by the scar band's reach and its reference ring
    pts = np.concatenate([sk['Pm'] for sk in fp['sockets']] + [sk['E'][None] for sk in fp['sockets']])
    tx, sz, fpts = dens.texel(pts)
    tx = tx[fs[fpts] == set_name]
    if not len(tx):
        return none()
    r1g = max([sc['r1'] for sc in fp['scars']] + [0.0])
    mg = int(math.ceil((r1g + 3.5e-3) * P['px'] * 1.15)) + 6
    x0, y0 = np.maximum(np.floor(tx.min(0)).astype(int) - mg, 0)
    x1, y1 = np.minimum(np.ceil(tx.max(0)).astype(int) + mg, size)
    w_, h_ = x1 - x0, y1 - y0
    F = np.asarray(low['F'], np.int64)[sel]
    corner = F.ravel()
    UV = np.asarray(low['UV'], np.float64)
    V = np.asarray(low['V'], np.float64)
    uvm = _mesh(np.column_stack([UV[corner] * size, np.zeros(len(corner))]), np.arange(len(corner)).reshape(-1, 3),
                device)
    lpos = wp.array(V[corner].astype(np.float32), dtype=wp.vec3, device=device)
    xs_g, ys_g = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    n = xs_g.size
    o4 = wp.zeros(n, dtype=wp.vec4, device=device)
    fc = wp.zeros(n, dtype=wp.int32, device=device)
    wp.launch(k_uv_point, dim=n, inputs=[uvm.id, wp.array(xs_g.ravel().astype(np.float32), dtype=float, device=device),
                                         wp.array(ys_g.ravel().astype(np.float32), dtype=float, device=device), lpos, o4,
                                         fc], device=device)
    P4 = o4.numpy().astype(np.float64)
    hit = fc.numpy() >= 0
    cov_all = (np.asarray(drivers['normal'])[..., 3] > 0)[::-1]           # texel order (row = y, v up)
    yy, xx = np.nonzero(hit.reshape(h_, w_))
    ok = cov_all[y0 + yy, x0 + xx]
    yy, xx = yy[ok], xx[ok]
    Pt = P4.reshape(h_, w_, 4)[yy, xx, :3]
    f0 = feed_fields(fp, Pt)
    near = f0['rho'] < r1g + 3.5e-3
    # the band's reference tone (scar_colour): the skin 0.3-3 mm past each band, off the cables and their parts (3 mm
    # keeps it off the junction's own band)
    lum0 = ((maps['albedo'][size - 1 - (y0 + yy), x0 + xx, :3].astype(np.float64) / 255.0) ** 2.2) @ LUM_W
    bes = ((f0['rho'] > r1g + 0.3e-3) & (f0['rho'] < r1g + 3.0e-3) &
           (np.minimum.reduce([f0['sweep'], f0['can'], f0['clamp'], f0['ring']]) > 2.0e-3))
    ref_all = beside_tone(lum0, bes, yy, xx, h_, w_, SCAR_REF * P['px'])
    yy, xx, Pt = yy[near], xx[near], Pt[near]
    ref_gs = ref_all[near]
    rows_img = size - 1 - (y0 + yy)
    cols = x0 + xx
    # the bake's hit: the low point raised its HEIGHT along the low's normal (the bake's own search)
    hgt = np.asarray(drivers['height'])[rows_img, cols].astype(np.float64)
    nP = dens.normal(Pt)
    X = Pt + hgt[:, None] * nP
    ff = feed_fields(fp, X)
    w_gs = np.clip(ff['scar'], 0.0, 1.0)
    share = w_gs
    # the scar band over the skin there (the current maps: the skin pass's)
    a8 = maps['albedo'][rows_img, cols, :3].astype(np.float64) / 255.0
    cur_lin = a8 ** 2.2
    rho_n = 1.0 - _smooth(ff['rho'], fp['r'], r1g)
    alb_gs = scar_colour(cur_lin, c0('cyb_scar'), rho_n, ref_gs)
    lin = np.clip((1.0 - share)[:, None] * cur_lin + share[:, None] * alb_gs, 0.013, 0.87)
    lin = np.where(share[:, None] > 0.0, lin, cur_lin)
    orm = maps['orm'][rows_img, cols, :3].astype(np.float64) / 255.0
    o_ao, o_m = orm[:, 0], orm[:, 2]
    o_r = np.clip((1.0 - share) * orm[:, 1] + share * rv['cyb_scar']['rough'], 0.0, 1.0)
    msk = maps['masks'][rows_img, cols].astype(np.float64) / 255.0
    msk[:, 2] *= 1.0 - share
    dsp = maps['display'][rows_img, cols].astype(np.float64) / 255.0
    dsp[:, :3] *= (1.0 - share)[:, None]
    dsp[:, 3] = 0.5 + (dsp[:, 3] - 0.5) * (1.0 - share)
    grw = maps['growth'][rows_img, cols].astype(np.float64) / 255.0
    grw[:, 0] = np.maximum(grw[:, 0], share)
    grw[:, 1:3] *= (1.0 - share)[:, None]
    chg = share > 0.0
    out = {k: v.copy() for k, v in maps.items()}
    enc = lambda x: np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8)
    ri, ci2 = rows_img[chg], cols[chg]
    out['albedo'][ri, ci2, :3] = enc(lin[chg] ** (1.0 / 2.2))
    out['orm'][ri, ci2, :3] = enc(np.column_stack([o_ao, o_r, o_m])[chg])
    out['masks'][ri, ci2] = enc(msk[chg])
    out['display'][ri, ci2] = enc(dsp[chg])
    out['growth'][ri, ci2] = enc(grw[chg])
    # the gutter, as the plates' pass: a gutter texel whose nearest covered texel changed takes its new value
    pad = 64
    ya, yb = max(0, y0 - pad), min(size, y1 + pad)
    xa, xb = max(0, x0 - pad), min(size, x1 + pad)
    cov_b = cov_all[ya:yb, xa:xb].copy()                 # the island's own texels: the centre hits (the plates' notes)
    cov_b[y0 - ya:y0 - ya + h_, x0 - xa:x0 - xa + w_] &= hit.reshape(h_, w_)
    changed = np.zeros_like(cov_b)
    changed[(y0 + yy[chg]) - ya, (x0 + xx[chg]) - xa] = True
    dist, (iy, ix) = ndimage.distance_transform_edt(~cov_b, return_indices=True)
    inner = np.zeros_like(cov_b)
    inner[max(0, y0 - 24 - ya):min(yb - ya, y1 + 24 - ya), max(0, x0 - 24 - xa):min(xb - xa, x1 + 24 - xa)] = True
    gut = inner & ~cov_b & (dist <= 24) & changed[iy, ix]
    gy, gx = np.nonzero(gut)
    sy, sx_ = iy[gy, gx], ix[gy, gx]
    dst_r, src_r = size - 1 - (ya + gy), size - 1 - (ya + sy)
    for k in out:
        out[k][dst_r, xa + gx] = out[k][src_r, xa + sx_]
    st = dict(texels=int(len(X)), changed=int(chg.sum()), gutter=int(len(gy)), scar=int((w_gs > 0.5).sum()),
              sockets=len(fp['sockets']), seconds=time.time() - t0)
    log(f'[cyborg] feed material pass (C3d, {set_name} {size}^2): {st["texels"]:,} texels round the {st["sockets"]} '
        f'sockets, {st["changed"]:,} changed (+ {st["gutter"]:,} gutter): the scar bands, {st["scar"]:,} texels over '
        f'half; the cables, collars and clamps are geometry (their shade the bake\'s AO); {st["seconds"]:.1f}s')
    st['arrays'] = dict(ys=y0 + yy, xs=x0 + xx, share=share, w_feed=np.zeros(len(X)), w_scar=w_gs, X=X, hgt=hgt, Pt=Pt,
                        nP=nP, rho=ff['rho'], socket=ff['socket'])
    return out, st
