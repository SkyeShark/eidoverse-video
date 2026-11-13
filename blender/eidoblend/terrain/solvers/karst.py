"""Karst towers: fenglin (towers and peak massifs on a river plain, Guilin) and fengcong (peaks packed on a common
base over closed, flat-floored cockpits). Design section 4.10.

Every input is a function of world position in metres. One global plan, built once on the CPU over the outermost
level's window, holds the tower centres, each tower's shape numbers and the river course. Every level evaluates that
plan at its own cells, so:
  - the walls stay sharp on a 0.5 m hero level (they are never upsampled from a coarser level);
  - a 31 m horizon level shows the same massifs, anti-aliased by 2 x 2 supersampling;
  - a child level matches its parent where they overlap, up to the octaves only the child resolves.

Frames and units (design 2.1): metres and degrees; arrays [row j, column i] with row 0 the south edge; a cell centre
is at x = x0 + (i + 0.5) cell, y = y0 + (j + 0.5) cell.

    plan = plan_karst(seed=7, domain=(-16000.0, -16000.0, 32000.0), params={'kind': 'fenglin'}, via=(0.0, 0.0),
                      main=(-4000.0, -4000.0, 8000.0))
    out = evaluate(plan, x0=-4000.0, y0=-4000.0, cell=7.8125, n=1024)
    out['h'], out['bed'], out['deposit'], out['talus'], out['water'], out['Sc']      # float32 (n, n)

What Guilin's towers are, from the Li River photographs (the 30 m radar reference rounds them): steep peaks and
towers rise abruptly from a flat alluvial plain, their bases cliffed (76-88 degrees, the limestone's bedding
breaking them with ledges), their summits pointed, ridged or knobby, never smooth domes; sizes vary from slim
spires to massifs 400 m across; inside a cluster they stand close, joined at saddles, in rows along the joints.
Each tower here is the intersection of two surfaces:
  - its WALL, rising from the footprint's edge: a table of bands up the height (wall_table: a foot notch at 89
    degrees, then wall bands at the tower's wall angle, 76-88, between ledges of 0.6-1.8 m at 40-60 degrees every
    10-30 m, the ledges holding along 55 % of the wall and breaking off elsewhere), read at the distance inside the
    footprint (the footprint: elongated along the joint strike, leaning, spurred and lobed by world noise; on levels
    with cells of 2 m or less, fluted: grooves straight down the wall, and on up the peaks' flanks);
  - its SUMMIT: the highest of its peak cones, each z = h (1 - x + b x (1 - x)), x the (elongated) distance from the
    peak over h / tan(angle), b the convexity: a spire's cone straight to steepening (b 0-0.3), a peak's from
    easing toward its foot (b to -0.2: a steep pointed top whose flanks run on to the saddles) to steepening (a
    sugarloaf, to 0.3); the distance scaled by the cone's ribs (rib_harmonics: azimuthal harmonics 2-7, so ribs and
    gullies radiate from the apex without ever folding the cone) and bent by a gentle 90 m world-noise jitter, the
    upper flanks lumpy and knobbed (peak_rough: the caps' roughness); on a block, over its cap: a rough cone from its
    cliff top (the rim, 30-52 % of its height) to 92 % at the centre, lumpy, with knobs over half of it.
  z = smooth-min(wall, summit) over brow_m: the wall stands until it meets the summit, then the summit rises.
The kinds of tower: a spire (one cone at 70-80 degrees, its footprint 70-92 % of the cone's foot: a short cliff
under a needle); a peak (one cone at 58-70 degrees, or two or three strung along a ridge; on the plain its footprint
35-65 % of the cone's foot, a cliff 35-65 % of its height; inside a cluster 60-85 %, its flanks running on to meet
its neighbours'); a block (a cliffed cap carrying two to four peaks: 8-10 % of the towers, and most of the towers
taller than 1.4-2.4 times the median: the massive towers of the river's bends). One or two collapse scarps pull a
sector of a tower's footprint in (scarp_sectors), so the wall stands high there under a concave sheer face; the
summit cones carry bedding benches (ledges and risers) on the levels that resolve them.
The plan: a cluster field (broad noise mixed with ridged noise, stretched along the joint strike): the peak clusters,
the rest plain; its threshold makes cluster_cover the main tile's share in clusters. Centres by variable-radius
Poisson-disc (poisson_disc): spacing_m apart inside the clusters, plain_spacing times that on the plain, the plain's
then thinned to plain_density (isolated towers). Heights lognormal around median_height_m, times a world-space trend
so neighbours are alike. The towers inside a cluster are drawn out along the strike (their peaks string into rows).
The ground between a cluster's inner towers is raised: a base (base_m, undulating by base_rough_m at 300 m and
120 m) that is nothing at a cluster's edge and toward the river, so the outer towers rise straight from the plain;
every tower rises from the base under each of its cells. Deep inside a cluster a peak is the fengcong cone: broad
(its foot cluster_reach of the median distance to its three nearest neighbours, 48-62 degrees on average) and
concave (cluster_convexity: 60-70 degrees at the top easing to 30-40 at the foot), so neighbours' flanks meet at cols
about half their height up; a cluster's edge towers keep the steep cliffed peaks of the plain, so the massif meets
the plain with sheer faces. Each cluster tower also stands on a massif BODY: the same wall table at a wider
footprint (body_reach), its brow body x the tower's height up, a rough skirt rising inward from it at body_deg (to
at most body_top of the height); neighbours' bodies join into ridges with cols, leave cockpits where three or more
meet, and two that would stand a slot apart (body_gap_m) are drawn on until they meet. So a cluster is a massif with
its peaks on it, walled where it meets the plain (Guilin's clusters at 30 m: 44 % of the tile 50 m and more over
the plain).
Composition: every tower by max over the plain, a talus cone at the foot under some of its azimuths (apron); the
plain is flat alluvium that rises gently away from a river winding through it (a least-cost course around the
clusters, with meanders). The river is a broad water surface at plain level: a flat water level river_bank_m under
the plain, a channel river_width_m wide (+- river_width_var along its course) and river_depth_m deep, its deepest
line swung toward the outer bank of each bend, a cut bank there and a gravel point bar on the inner bank standing
bar_m above the water at the sharpest bends. Where towers ring a gap, the gap is a closed depression (a cockpit, or
a polje where a cluster encloses a patch of plain) and soil fills its bottom flat (cockpit_fill of its depth, a
small pit nearly to its spill), found once per plan on the main tile so every level fills it alike: the one family
where closed depressions are correct. fengcong raises the clusters on a common plinth (plinth_m).

The stage op `karst` (op_karst) writes h, bed (the rock: towers, and the buried rock under the alluvium and the
cockpit soil), deposit (h - bed), talus (the talus cones), water (the river's depth: flat at one level, so the lake
builder draws it as the water surface it is) and Sc (the wall's own angle, 87.5 degrees: the recipe's threshold pass
only trims texel spikes) on a level. Needs numpy only, so it runs in Blender's Python and in plain Python tests.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import numpy as np

__all__ = ['DEFAULTS', 'KIND_PRESETS', 'KarstPlan', 'params_for', 'cone_profile', 'wall_table', 'pinnacles',
           'rib_harmonics', 'poisson_disc', 'plan_karst', 'cached_plan', 'evaluate', 'op_karst', 'noise2', 'fbm2',
           'supersampling_for', 'OPS']

# ---------------------------------------------------------------- parameters (metres, degrees)
DEFAULTS = dict(
    kind='fenglin',              # 'fenglin' (towers on a river plain) | 'fengcong' (peaks over dolines)
    spacing_m=210.0,             # Poisson-disc spacing of the towers inside the clusters (about their neighbour gap)
    median_height_m=150.0,       # median summit height above the plain
    height_sigma=0.38,           # lognormal spread of the heights (natural log)
    height_trend=0.30,           # world-space height trend (2 km scale, natural-log amplitude): neighbours alike
    wall_deg=82.0,               # the walls' angle (median; per tower +- wall_spread_deg, held to 70-89)
    wall_spread_deg=4.0,
    ledge_every_m=(10.0, 30.0),  # the walls' ledges (bedding benches): one every this many metres of height ...
    ledge_deg=(40.0, 60.0),      # ... at this angle ...
    ledge_m=(0.6, 1.8),          # ... this tall (so 0.4-1.5 m wide) ...
    ledge_cover=0.55,            # ... along this share of the wall (world noise at 30 m: ledges break off and resume)
    notch_m=(2.0, 6.0),          # the foot notch's height (89 degrees: the undercut's stand-in)
    slim_share=(0.35, 0.20),     # the share of slim spires among the towers (on the plain, inside the clusters)
    block_share=(0.08, 0.10),    # the share of blocks and massifs (a cliffed cap with knobs) among them
    spire_deg=(70.0, 80.0),      # a spire's cone angle (its mean slope, apex to foot)
    spire_girth=(0.70, 0.92),    # a spire's footprint, a share of its cone's foot radius (a short steep wall below)
    peak_deg=(58.0, 70.0),       # a peak's cone angle (on the plain)
    peak_girth=(0.55, 0.85),     # a peak's footprint on the plain, a share of its cone's foot radius: a wall
                                 # 15-45 % of its height (the photographs' cliffed towers, 0.7-1.3 x as wide as
                                 # tall at the foot; at 0.35-0.65 they stood as needles, 2 x taller than wide)
    cluster_girth=(0.60, 0.85),  # ... at a cluster's edge: the wall facing the plain
    cluster_reach=(0.75, 0.95),  # a cluster peak's cone reaches this share of the median distance to its 3 nearest
                                 # neighbours: the cones meet at saddles, so a cluster is one massif with its peaks
                                 # on it (Guilin's peak clusters at 30 m: 23 % of the ground 100-200 m up; separate
                                 # towers on a low base held 8 %, the clusters a plain strewn with pebbles)
    cluster_peak_deg=(48.0, 62.0),  # ... its cone angle follows from its height over that reach, held to this, ...
    cluster_convexity=(-0.55, -0.15),  # ... and its profile concave: the fengcong cone, steep at the top (60-70
                                       # degrees) easing to 30-40 at its foot where it meets its neighbours at cols.
                                       # (Narrow 58-70 degree cones over the massif bodies stood as candles on cakes)
    inner_girth=(1.0, 1.08),     # deep inside a cluster the footprint takes the whole cone (no wall: its flanks run
                                 # down into the saddles and cockpits), but for its collapse scarps
    edge_scarp=(0.45, 0.65),     # a cluster's edge tower turns a collapse scarp of this depth toward the plain: the
                                 # massif meets the plain with sheer faces
    body=(0.12, 0.25),           # a cluster tower's massif body: its wall at the body's edge this share of the
                                 # tower's height (at 0.25-0.45 under a gentle top they stood as cakes), ...
    body_reach=(0.50, 0.70),     # ... its footprint this share of the median distance to its 3 nearest neighbours
                                 # (neighbours' bodies join along the rows into ridges with cols between them and
                                 # leave star-shaped cockpits where three or more meet), ...
    body_deg=(12.0, 22.0),       # ... its top a skirt rising inward at this angle from the wall's brow until the
                                 # peak's steeper cone takes over: the broad lower flanks of a peak cluster
    body_gap_m=45.0,             # two neighbours' bodies closer than this are drawn on until they meet (no slots)
    body_top=0.6,                # the skirt reaches at most this share of the tower's height at its centre
    block_girth=(0.70, 1.10),    # a block's footprint radius over its height (on the plain)
    massif_reach=(0.46, 0.64),   # a massif's footprint radius over the median distance to its 3 nearest neighbours
                                 # (in the clusters: neighbours overlap into massifs, the gaps left are cockpits)
    peak_convexity=(-0.2, 0.3),  # b of z = h (1 - x + b x (1 - x)): below 0 a peak's flanks ease toward its foot
                                 # (steep pointed tops, flanks running into the saddles), above 0 they steepen (a
                                 # sugarloaf); their straight sides broken by the knobs (peak_rough) and the
                                 # bedding benches. (Mostly convex, -0.1..0.4, rounded the tops: the upper sixth of
                                 # the towers stood at 45 degrees, the review's domes)
    spire_convexity=(0.0, 0.3),    # a spire's: straight to steepening (a needle, never a flared foot)
    peak_spacing_m=70.0,         # the least spacing of a tower's own peaks
    peaks_max=4,
    floor=(0.30, 0.52),          # a block's cliff top (its cap's rim), a share of its height
    cap_top=0.92,                # its cap rises from the rim to this share of the height at the centre (a rough cone)
    floor_rough=0.035,           # the caps' lumps, a share of the height (45 m world noise)
    crown=0.06,                  # knobs on the caps, in patches: their height, a share of the tower's ...
    crown_spacing_m=60.0,        # ... and spacing (pointed knobs on a jittered world lattice)
    crown_cover=0.5,             # ... over this share of a cap
    scarps=(0.25, 0.5, 0.25),    # the chances of 0, 1 and 2 collapse scarps on a tower: on each, a sector of the
    scarp_deg=(25.0, 60.0),      # footprint (this half-width) is pulled in by ...
    scarp_depth=(0.35, 0.6),     # ... this share of its radius, so the wall rises high there: a concave sheer face
    ribs=0.45,                   # the summit cones' ribs and gullies: azimuthal harmonics 2-7 of each cone's distance
                                 # from its apex, sum of m |a_m| (under 1 the distance never folds: ribs radiate from
                                 # the apex and the flanks stand between 0.7 and 1.4 of the cone's slope)
    jag=0.05,                    # a gentle world-noise jitter of that distance (relative std, 90 m and 40 m): the
                                 # ribs bend and the feet bulge; 0.2 at 45-6 m folded the cones into blade fences
    brow_m=2.0,                  # the rounding where a wall meets the summit, metres (at most 2 % of the height)
    peak_rough=0.6,              # the summits' lumps and knobs (the caps' roughness, this share of it) over a peak's
                                 # upper flanks: jagged, knobbed tops (smooth cones read as geometric pyramids)
    apron=0.05,                  # a talus cone's height at the foot, a share of the tower's height ...
    apron_cover=0.35,            # ... under this share of the foot's azimuths
    apron_deg=33.0,              # its slope
    elongation=0.35,             # max footprint elongation along the strike, on the plain
    cluster_elong=(0.10, 0.55),  # the elongation inside the clusters (their peaks string into rows along the strike)
    ridge_share=0.12,            # the share of towers drawn out into ridges (elongation 0.6-1.1, 2-3 peaks)
    benches=0.6,                 # the summit cones' bedding benches: z - k B / 2 pi sin(2 pi z / B) (k this; under 1
    bench_m=13.0,                # it never folds): ledges at (1 - k) and risers at (1 + k) of the cone's slope, every B
                                 # metres of height (undulating +-3 m over 160 m), fading out over the top quarter
    tall_massif=0.85,            # towers from 1.4 to 2.4 x the median height become massifs: up to this share of
                                 # the peaks turn blocks, and of the rest ridges (no single 400 m cone)
    lean=0.20,                   # max footprint offset (one wall higher than the other)
    spurs=0.10,                  # radial spurs: the largest amplitude of azimuthal harmonics 2-5 of the footprint
    lobes_m=6.0,                 # footprint lobing: radial displacement by world noise (130 m and 60 m), std metres
    plinth_m=0.0,                # the clusters' common base (fengcong 50-150): the cockpit floors between the peaks
    base_m=45.0,                 # fenglin: the ground between the inner towers of a cluster, rising from its edge
                                 # (the towers' bodies cover most of it: it shows as the cockpits' floors; at 50 m
                                 # under thin towers with no bodies it showed as a lumpy plateau between them)
    base_rough_m=6.0,            # the base's undulation (std, metres at 300 m and 120 m): rises, saddles, hollows
    cockpit_fill=0.85,           # soil filling each cockpit (closed depression between towers) flat: share of its depth
                                 # (a small pit, 1 ha, nearly to its spill: its soil floor, not a round bowl)
    cluster_cover=0.80,          # fraction of the main tile inside peak clusters (the rest is plain)
    cluster_scale_m=2600.0,      # wavelength of the cluster / plain pattern
    cluster_ridges=0.65,         # share of ridged noise in it: massifs as elongated ridges with peaks along them
    ridge_scale_m=1500.0,        # the ridges' wavelength (about twice their spacing)
    cluster_stretch=2.2,         # the pattern's elongation along the joint strike
    strike_deg=115.0,            # joint strike, compass degrees: clusters, towers and plains elongate along it
    plain_density=0.30,          # share of the plain's blue-noise points kept as isolated towers
    plain_spacing=1.6,           # their Poisson radius, a multiple of the clusters' radius
    river=True,                  # a river winding through the plain
    river_width_m=130.0,         # the channel's mean width (the Li River at Yangshuo: 100-200 m)
    river_width_var=0.25,        # its relative change along the course (1.8 km world noise)
    river_depth_m=3.5,           # the deepest water
    river_bank_m=2.2,            # the plain's height above the water at the bank
    river_meander=2.4,           # meander amplitude, a multiple of the width
    river_azimuth_deg=None,      # flow direction, compass degrees (None: from the seed)
    bar_m=0.8,                   # a point bar's top above the water on the inner bank of a sharp bend
    plain_tilt_m_per_km=0.0,     # the plain's fall along the river (0: the water is one flat surface everywhere)
    plain_rise_m=4.0,            # the plain rises this much away from the river, over 1.5 km
    plain_micro_m=0.3,           # alluvial micro-relief (std)
    alluvium_m=12.0,             # alluvium over the buried rock of the plain
    fluting_m=0.9,               # vertical fluting depth on the walls (levels with cells <= 2 m)
    sc_deg=87.5,                 # the threshold slope written to Sc: the recipe's pass trims only texel spikes
)

KIND_PRESETS = {
    'fenglin': dict(),
    'fengcong': dict(spacing_m=210.0, median_height_m=190.0, height_sigma=0.28, height_trend=0.2,
                     slim_share=(0.3, 0.3), block_share=(0.1, 0.1), peak_girth=(0.75, 0.95), plinth_m=60.0,
                     base_m=0.0, base_rough_m=10.0,
                     cluster_cover=0.97, cluster_ridges=0.3, cluster_elong=(0.0, 0.5), plain_density=0.0,
                     elongation=0.25, ridge_share=0.1, lean=0.10, river=False),
}

_PAIRS = ('ledge_every_m', 'ledge_deg', 'ledge_m', 'notch_m', 'slim_share', 'block_share', 'spire_deg',
          'spire_girth', 'peak_deg', 'peak_girth', 'cluster_girth', 'cluster_reach', 'cluster_peak_deg',
          'inner_girth', 'edge_scarp', 'block_girth', 'massif_reach', 'peak_convexity', 'spire_convexity', 'floor',
          'body', 'body_reach', 'body_deg', 'cluster_convexity',
          'cluster_elong', 'scarp_deg', 'scarp_depth')


def params_for(params=None):
    """The full parameter dict: DEFAULTS, then the kind's preset, then the caller's values."""
    params = dict(params or {})
    kind = params.get('kind', DEFAULTS['kind'])
    if kind not in KIND_PRESETS:
        raise ValueError(f"karst kind {kind!r}: use one of {sorted(KIND_PRESETS)}")
    unknown = sorted(set(params) - set(DEFAULTS))
    if unknown:
        import difflib
        near = sorted({m for k in unknown for m in difflib.get_close_matches(k, list(DEFAULTS), n=2)})
        raise ValueError(f'unknown karst parameter(s) {unknown}' + (f'; nearest: {near}' if near else '')
                         + f'; known: {sorted(DEFAULTS)}')
    out = dict(DEFAULTS)
    out.update(KIND_PRESETS[kind])
    out.update(params)
    for k in _PAIRS:
        v = out[k]
        out[k] = (float(v[0]), float(v[1])) if isinstance(v, (list, tuple)) else (float(v), float(v))
    return out


# ---------------------------------------------------------------- world-space gradient noise
_GX16 = np.cos(np.arange(16) * (2 * math.pi / 16))
_GY16 = np.sin(np.arange(16) * (2 * math.pi / 16))


def _pcg(v):
    """32-bit PCG hash (Jarzynski & Olano 2020) on uint32 arrays (the multiplies wrap mod 2^32)."""
    s = v * np.uint32(747796405) + np.uint32(2891336453)
    w = ((s >> ((s >> np.uint32(28)) + np.uint32(4))) ^ s) * np.uint32(277803737)
    return (w >> np.uint32(22)) ^ w


def _hash2(ix, iy, salt):
    """uint32 hash of integer lattice coordinates (any sign) and a salt."""
    a = (np.asarray(ix, np.int64) & 0xFFFFFFFF).astype(np.uint32)
    b = (np.asarray(iy, np.int64) & 0xFFFFFFFF).astype(np.uint32)
    return _pcg(a + _pcg(b + np.uint32(salt & 0xFFFFFFFF)))


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def noise2(x, y, wavelength, salt):
    """2-D gradient noise of world metres x, y at a wavelength in metres: about -1..1, std about 0.3. The corner
    gradients are hashed once per lattice point of the block the samples cover, then gathered."""
    gx = np.asarray(x, np.float64) / wavelength
    gy = np.asarray(y, np.float64) / wavelength
    if gx.ndim == 2 and gy.ndim == 2 and gx.shape[0] == 1 and gy.shape[1] == 1:
        return _noise2_separable(gx[0], gy[:, 0], salt)
    gx, gy = np.broadcast_arrays(gx, gy)
    fx0, fy0 = np.floor(gx), np.floor(gy)
    fx, fy = gx - fx0, gy - fy0
    ix, iy = fx0.astype(np.int64), fy0.astype(np.int64)
    if ix.size == 0:
        return np.zeros(ix.shape)
    ix0, iy0 = int(ix.min()), int(iy.min())
    bw, bh = int(ix.max()) - ix0 + 2, int(iy.max()) - iy0 + 2
    if bw * bh <= max(4 * ix.size, 4096):
        lat = _hash2(np.arange(ix0, ix0 + bw)[None, :], np.arange(iy0, iy0 + bh)[:, None], salt) & np.uint32(15)
        gxl, gyl = _GX16[lat], _GY16[lat]
        li, lj = ix - ix0, iy - iy0

        def corner(di, dj):
            return gxl[lj + dj, li + di] * (fx - di) + gyl[lj + dj, li + di] * (fy - dj)
    else:
        def corner(di, dj):
            k = _hash2(ix + di, iy + dj, salt) & np.uint32(15)
            return _GX16[k] * (fx - di) + _GY16[k] * (fy - dj)
    ux, uy = _fade(fx), _fade(fy)
    n00, n10, n01, n11 = corner(0, 0), corner(1, 0), corner(0, 1), corner(1, 1)
    a = n00 + (n10 - n00) * ux
    b = n01 + (n11 - n01) * ux
    return (a + (b - a) * uy) * 1.41


def _noise2_separable(gx, gy, salt):
    """noise2 on the grid of lattice coordinates gx (columns) x gy (rows): row and column gathers only."""
    fx0, fy0 = np.floor(gx), np.floor(gy)
    fx, fy = gx - fx0, gy - fy0
    ix, iy = fx0.astype(np.int64), fy0.astype(np.int64)
    ix0, iy0 = int(ix.min()), int(iy.min())
    bw, bh = int(ix.max()) - ix0 + 2, int(iy.max()) - iy0 + 2
    lat = _hash2(np.arange(ix0, ix0 + bw)[None, :], np.arange(iy0, iy0 + bh)[:, None], salt) & np.uint32(15)
    gxl, gyl = _GX16[lat], _GY16[lat]
    li, lj = ix - ix0, iy - iy0

    def corner(di, dj):
        a = np.take(np.take(gxl, lj + dj, axis=0), li + di, axis=1)
        b = np.take(np.take(gyl, lj + dj, axis=0), li + di, axis=1)
        return a * (fx - di)[None, :] + b * (fy - dj)[:, None]
    ux, uy = _fade(fx)[None, :], _fade(fy)[:, None]
    n00, n10, n01, n11 = corner(0, 0), corner(1, 0), corner(0, 1), corner(1, 1)
    a = n00 + (n10 - n00) * ux
    b = n01 + (n11 - n01) * ux
    return (a + (b - a) * uy) * 1.41


def _noise1_periodic(s, period, salt):
    """1-D gradient noise of lattice coordinate s, periodic with `period` lattice cells (an integer): about -1..1."""
    i = np.floor(s)
    f = s - i
    i = i.astype(np.int64)
    P = max(int(period), 1)
    g = _hash2(np.arange(P), np.zeros(P, np.int64), salt).astype(np.float64) / 2147483648.0 - 1.0
    d0 = g[np.mod(i, P)] * f
    d1 = g[np.mod(i + 1, P)] * (f - 1.0)
    return 2.0 * (d0 + (d1 - d0) * _fade(f))


def fbm2(x, y, wavelength, octaves, salt, gain=0.5, min_wavelength=0.0):
    """Octaves of noise2, halving the wavelength each time; octaves shorter than min_wavelength (the level's
    resolution limit) are left out, so a coarse level gets the band-limited version of the same field."""
    out = np.zeros(np.broadcast(np.asarray(x), np.asarray(y)).shape, np.float64)
    a, lam = 1.0, float(wavelength)
    for k in range(octaves):
        if lam >= min_wavelength:
            out += a * noise2(x, y, lam, salt + 7919 * k)
        a *= gain
        lam *= 0.5
    return out


def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def pinnacles(x, y, spacing, salt):
    """A field of pointed knobs in world metres: one knob per cell of a lattice of `spacing`, jittered inside its
    cell, its apex 0.55-1 high (by its own hash), falling linearly to 0 at 0.75 spacing from it (the highest knob
    wins: Worley's F1 cone). 0..1."""
    gx = np.asarray(x, np.float64) / spacing
    gy = np.asarray(y, np.float64) / spacing
    ix, iy = np.floor(gx).astype(np.int64), np.floor(gy).astype(np.int64)
    best = None
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            cx, cy = ix + di, iy + dj
            hsh = _hash2(cx, cy, salt)
            jx = (hsh & np.uint32(0xFFFF)).astype(np.float64) / 65535.0
            jy = ((hsh >> np.uint32(16)) & np.uint32(0xFFFF)).astype(np.float64) / 65535.0
            top = 0.55 + 0.45 * ((_pcg(hsh) & np.uint32(0xFFFF)).astype(np.float64) / 65535.0)
            d = np.hypot(gx - (cx + 0.1 + 0.8 * jx), gy - (cy + 0.1 + 0.8 * jy))
            v = top * np.clip(1.0 - d / 0.75, 0.0, 1.0)
            best = v if best is None else np.maximum(best, v)
    return best


def _smin(a, b, k):
    """Smooth minimum of a and b over a width k (metres): min(a, b) where they differ by more than k."""
    if k <= 0:
        return np.minimum(a, b)
    hh = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - hh * hh * (k * 0.25)


# ---------------------------------------------------------------- the tower's two surfaces
def cone_profile(x, b):
    """A summit cone's height over its apex height at x = distance / foot radius: 1 - x + b x (1 - x). Pointed at
    the apex (slope 1 - b times the mean), steepening to the foot (1 + b times the mean) at x = 1, and falling on
    below the foot at the foot's slope, straight (it is cut there by the wall and the plain). (The parabola itself
    turns up again past x = (b - 1) / 2b for a concave cone, b < 0: at b = -0.53 it rose to 1.2 x the apex 3 foot
    radii out, a wall 125 m over the tallest tower.)"""
    x = np.maximum(np.asarray(x, np.float64), 0.0)
    return np.where(x <= 1.0, 1.0 - x + b * x * (1.0 - x), -(1.0 + b) * (x - 1.0))


def wall_table(rng, height_m, wall_deg, p):
    """A tower's wall as tables of (distance inside the footprint's edge, metres; height, metres): from the plain
    up, a foot notch at 89 degrees (notch_m tall), then wall bands at wall_deg between ledges (ledge_m tall at
    ledge_deg, one every ledge_every_m), each band's angle jittered +-2 degrees, up past the tower's height. The
    distance is the integral of dz / tan(angle): the wall's height at a distance d is np.interp(d, D, Z). Returns
    (D, Z, D0): D0 the same wall with every ledge at the wall's angle (where a ledge has broken off)."""
    top = 1.3 * float(height_m) + 5.0
    zs, ang, flat = [0.0], [], []
    z = float(rng.uniform(*p['notch_m']))
    zs.append(z)
    ang.append(89.0)
    flat.append(89.0)
    while z < top:
        a = float(np.clip(wall_deg + rng.uniform(-2.0, 2.0), 70.0, 89.0))
        z += float(rng.uniform(*p['ledge_every_m']))
        zs.append(z)
        ang.append(a)
        flat.append(a)
        z += float(rng.uniform(*p['ledge_m']))
        zs.append(z)
        ang.append(float(rng.uniform(*p['ledge_deg'])))
        flat.append(a)
    Z = np.asarray(zs)
    D = np.concatenate([[0.0], np.cumsum(np.diff(Z) / np.tan(np.radians(np.asarray(ang))))])
    D0 = np.concatenate([[0.0], np.cumsum(np.diff(Z) / np.tan(np.radians(np.asarray(flat))))])
    return D, Z, D0


# ---------------------------------------------------------------- blue noise
def poisson_disc(seed, x0, y0, width, height, radius_fn, r_min, r_max, tries=8, throw=0.3):
    """Variable-radius Poisson-disc points in [x0, x0 + width) x [y0, y0 + height) metres, by phase-group parallel
    dart throwing on a background grid of cell r_min / sqrt(2) (one point per cell at most). Cells of one phase are
    more than r_max apart, so their darts never conflict and each phase is one vectorised step. In each phase a live
    cell throws only with probability `throw`: were every cell of the first phase to throw, its points would be a
    jittered lattice that the later phases fill around, and the set would keep the grid's axes (a 4-fold bias in the
    directions between neighbours). Two points conflict when closer than the larger of their radii; a cell retires
    after `tries` rejected darts (Bridson's k), so the set is near-maximal. radius_fn(x, y) -> metres, between r_min
    and r_max. Returns (x, y, r) float64 arrays; deterministic for a seed and window."""
    rng = np.random.default_rng(seed)
    g = r_min / math.sqrt(2.0)
    nx, ny = int(math.ceil(width / g)), int(math.ceil(height / g))
    k = int(math.ceil(r_max / g))
    P = k + 1
    pad = k
    GX = np.full((ny + 2 * pad, nx + 2 * pad), np.nan)
    GY = np.full_like(GX, np.nan)
    GR = np.full_like(GX, np.nan)
    fails = np.zeros((ny, nx), np.int32)
    off = np.arange(-k, k + 1)
    oj, oi = np.meshgrid(off, off, indexing='ij')
    near = (np.maximum(np.abs(oj), np.abs(oi)) - 1) * g < r_max        # neighbour cells that can hold a conflict
    oj, oi = oj[near], oi[near]
    jj, ii = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij')
    phases = [(jj[a::P, b::P].ravel(), ii[a::P, b::P].ravel()) for a in range(P) for b in range(P)]
    for _ in range(int(math.ceil((tries + 2) / throw)) + 4):
        added = 0
        for n_, (pj, pi) in enumerate(phases):
            live = np.isnan(GX[pj + pad, pi + pad]) & (fails[pj, pi] < tries)
            pj, pi = pj[live], pi[live]
            phases[n_] = (pj, pi)
            pick = rng.random(pj.size) < throw
            cj, ci = pj[pick], pi[pick]
            added += int(pj.size)
            if cj.size == 0:
                continue
            dx = x0 + (ci + rng.random(ci.size)) * g
            dy = y0 + (cj + rng.random(cj.size)) * g
            inside = (dx < x0 + width) & (dy < y0 + height)
            rd = np.asarray(radius_fn(dx, dy), np.float64)
            nj = cj[:, None] + pad + oj[None, :]
            ni = ci[:, None] + pad + oi[None, :]
            qx, qy, qr = GX[nj, ni], GY[nj, ni], GR[nj, ni]
            d2 = (qx - dx[:, None]) ** 2 + (qy - dy[:, None]) ** 2
            lim = np.maximum(qr, rd[:, None])
            clash = np.any(d2 < lim * lim, axis=1)                      # NaN (an empty cell) compares False
            ok = inside & ~clash
            GX[cj[ok] + pad, ci[ok] + pad] = dx[ok]
            GY[cj[ok] + pad, ci[ok] + pad] = dy[ok]
            GR[cj[ok] + pad, ci[ok] + pad] = rd[ok]
            fails[cj[~ok], ci[~ok]] += 1
        if added == 0:                                                   # no live cell left
            break
    m = ~np.isnan(GX)
    return GX[m], GY[m], GR[m]


# ---------------------------------------------------------------- the plan
@dataclass
class KarstPlan:
    """Everything global about one karst terrain: the parameters, the cluster field, the towers and the river.
    Tower arrays are float64, one entry per tower (peaks: (N, peaks_max), NaN where a tower has fewer); angles in
    radians from +x, counter-clockwise; peak offsets in metres from the tower's centre."""
    seed: int
    domain: tuple
    params: dict
    salt: int
    strike: float
    cluster_threshold: float
    cluster_band: float
    cluster_std: float = 1.0
    x: np.ndarray = None
    y: np.ndarray = None
    H: np.ndarray = None              # summit height above the tower's foot, metres
    F: np.ndarray = None              # the common base's height under the tower's foot, metres (fengcong)
    R: np.ndarray = None              # the footprint radius, metres (the wall's foot line)
    wall: np.ndarray = None           # the walls' angle, degrees
    kind: np.ndarray = None           # 0 a slim spire, 1 a peak, 2 a block (a floor with knobs)
    floor: np.ndarray = None          # the top's floor, metres above the foot (-inf: none)
    B: np.ndarray = None              # the talus cones' height at the foot, metres
    reach: np.ndarray = None          # their reach out from the foot, metres
    elong: np.ndarray = None
    axis: np.ndarray = None
    lean: np.ndarray = None
    lean_dir: np.ndarray = None
    cluster: np.ndarray = None        # cluster membership at the centre, 0..1
    interior: np.ndarray = None       # how deep inside its cluster, 0..1
    spur: np.ndarray = None           # (N, 4) complex: amplitude and phase of footprint harmonics 2, 3, 4, 5
    npk: np.ndarray = None            # the number of summit peaks
    pk_dx: np.ndarray = None          # (N, K) the peaks' offsets from the centre, metres
    pk_dy: np.ndarray = None
    pk_h: np.ndarray = None           # (N, K) apex heights above the foot, metres
    pk_r0: np.ndarray = None          # (N, K) foot radius h / tan(angle), metres
    pk_b: np.ndarray = None           # (N, K) convexity
    pk_e: np.ndarray = None           # (N, K) elongation of the peak's footprint (ridges)
    pk_axis: np.ndarray = None        # (N, K) its axis
    pk_rib: np.ndarray = None         # (N, K, 6) complex: the cone's ribs, harmonics 2-7 of its distance (None: none)
    scarp: np.ndarray = None          # (N, 2, 3): each collapse scarp's (direction, radians; cos of its half-width;
                                      # depth, a share of the footprint radius; 0: none). None: no scarps
    body_h: np.ndarray = None         # the massif body's wall height at its edge, metres above the foot (0: none)
    body_R: np.ndarray = None         # its footprint radius, metres
    body_tan: np.ndarray = None       # the tangent of its skirt's angle
    wall_D: list = None               # per tower: the wall table's distances inside the edge, metres
    wall_Z: list = None               # ... and heights, metres
    wall_D0: list = None              # ... and the distances with no ledges (where a ledge has broken off)
    river: np.ndarray = None          # (N, 2) polyline in metres, upstream first; None without a river
    river_coarse: np.ndarray = None   # the same, resampled at 40 m (the plain's far field, tower clearance)
    river_mid: np.ndarray = None      # the same, resampled at 30 m (the channel; chord error < 0.6 m on its bends)
    river_s: np.ndarray = None        # arc length of river_mid's vertices, metres
    river_kappa: np.ndarray = None    # its signed curvature (1/m, + turning left), smoothed over 150 m
    river_hw: np.ndarray = None       # its half-width at each vertex, metres
    water_level: float = -1e9         # the river's flat water surface, metres above the plain's base level
    river_dir: tuple = (1.0, 0.0)
    main: tuple = None                # the main tile (x0, y0, side): the cockpit floor map covers it
    floors: tuple = None              # (x0, y0, cell, floor levels (n, n), -inf off the basins), made on first use
    stats: dict = field(default_factory=dict)

    @property
    def count(self):
        return 0 if self.x is None else int(self.x.size)


def _cluster_raw(salt, pr, strike, x, y):
    """The un-thresholded cluster field, stretched along the strike: broad noise (where the massifs and the plains
    are) mixed with ridged noise (the massifs as elongated ridges, peaks strung along their crests)."""
    c, s = math.cos(strike), math.sin(strike)
    u = (x * c + y * s) / pr['cluster_stretch']
    v = -x * s + y * c
    broad = fbm2(u, v, pr['cluster_scale_m'], 3, salt + 11, gain=0.5) / 0.3
    a = pr['cluster_ridges']
    if a <= 0:
        return broad
    n = noise2(u, v, pr['ridge_scale_m'], salt + 13) + 0.35 * noise2(u, v, 0.5 * pr['ridge_scale_m'], salt + 17)
    ridged = (1.0 - np.abs(n) / 0.45) * 1.6               # about unit std, high along the zero lines of n
    return (1.0 - a) * broad + a * ridged


def _cluster(plan, x, y):
    """(membership 0..1, raw field) at world points: 1 inside the clusters, 0 on the plain."""
    raw = _cluster_raw(plan.salt, plan.params, plan.strike, x, y)
    return _smoothstep(plan.cluster_threshold - plan.cluster_band, plan.cluster_threshold + plan.cluster_band, raw), raw


def _plinth_of(plan, x, y):
    """The clusters' common base at full height (metres above the plain): plinth_m, varying +-25 % at 1.5 km, and
    undulating by base_rough_m (std) at 300 m and 120 m (the ground between the peaks: rises, saddles and the
    hollows the cockpits fill)."""
    pr = plan.params
    out = (pr['plinth_m'] + pr['base_m']) * np.maximum(1.0 + 0.25 * fbm2(x, y, 1500.0, 2, plan.salt + 31) / 0.3, 0.3)
    if pr['base_rough_m'] > 0:
        out = out + pr['base_rough_m'] * (fbm2(x, y, 300.0, 1, plan.salt + 33)
                                          + 0.8 * fbm2(x, y, 120.0, 1, plan.salt + 37)) / 0.38
    return np.maximum(out, 0.0)


def _base_membership(plan, x, y):
    """How much of the common base a point carries. fenglin: none at a cluster's edge, rising toward its interior
    (the outer towers stand on the plain with their own walls; the base, hidden among the towers, carries the
    inner ones: no rampart round the clusters). fengcong (a plinth): the cluster field's step over a third of its
    band, so the plinth meets the plain at a steep edge, not a ramp."""
    raw = _cluster_raw(plan.salt, plan.params, plan.strike, x, y)
    if plan.params['plinth_m'] <= 0:
        out = _interior_of(plan, raw)
        if plan.river is not None:
            # the river's corridor is kept clear of towers, so the base fades out before it too (bare, it read as
            # smooth rolling hills beside the river)
            X, Y = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(y, np.float64))
            pr = plan.params
            d0 = pr['river_width_m'] * (1.0 + pr['river_width_var']) + 80.0
            d = _river_distance(plan.river_coarse, X, Y, d0 + 450.0).reshape(X.shape)
            out = out * _smoothstep(d0, d0 + 450.0, d)
        return out
    b = 0.3 * plan.cluster_band
    return _smoothstep(plan.cluster_threshold - b, plan.cluster_threshold + b, raw)


def _interior_of(plan, raw):
    """How deep inside its cluster a point is (0 at the edge, 1 well inside), from the raw cluster field."""
    t0 = plan.cluster_threshold + plan.cluster_band
    return _smoothstep(t0, t0 + 0.9 * plan.cluster_std, raw)


def _compass_to_rad(deg):
    """Compass degrees (0 north, clockwise) to radians from +x, counter-clockwise."""
    return math.radians(90.0 - deg)


def _uni(rng, pair, n):
    return rng.uniform(pair[0], pair[1], n)


def _place_peaks(rng, pr, R, H, elong, axis, kind, npk, floor, main_ang):
    """The summit peaks of every tower: (dx, dy, h, r0, b, e, axis), each (N, K), NaN past a tower's count, and the
    count placed. The first peak is the tower's summit (height H) near the centre, at the tower's own cone angle
    (main_ang). The others: on a ridge tower (elongation over 0.6) strung along its long axis, 0.35-0.6 of its
    half-length out on alternate sides; on a block, darted inside 0.6 of the footprint at least peak_spacing_m apart.
    They stand lower (0.6-0.92 H, less 25 % toward the edge, never under the floor), at the peak angle, drawn out
    along the tower's axis (ridged crests)."""
    N = R.size
    K = int(pr['peaks_max'])
    nan = np.full((N, K), np.nan)
    dx, dy, h, r0, b, e, ax = (nan.copy() for _ in range(7))
    ca, sa = np.cos(axis), np.sin(axis)
    el = 1.0 + elong

    def world(along, across):
        return along * ca[:, None] - across * sa[:, None], along * sa[:, None] + across * ca[:, None]

    r_first = rng.uniform(0.0, 0.12, N) * R
    phi = rng.uniform(0.0, 2 * math.pi, N)
    fx, fy = world((r_first * np.cos(phi) * el)[:, None], (r_first * np.sin(phi) / el)[:, None])
    dx[:, 0], dy[:, 0] = fx[:, 0], fy[:, 0]
    h[:, 0] = H
    ang = np.full((N, K), np.nan)
    ang[:, 0] = main_ang
    ridge = elong > 0.6
    sep = np.maximum(pr['peak_spacing_m'], 0.3 * R)
    T = 14
    for k in range(1, K):
        want = k < npk
        if not want.any():
            break
        # ridge towers: along the axis, alternate sides; blocks: anywhere inside 0.6 of the footprint
        side = 1.0 if k % 2 else -1.0
        a_r = side * rng.uniform(0.35, 0.6, (N, T)) * (R * el)[:, None]
        c_r = rng.uniform(-0.12, 0.12, (N, T)) * R[:, None]
        rho = 0.6 * R[:, None] * np.sqrt(rng.uniform(0.04, 1.0, (N, T)))
        th = rng.uniform(0.0, 2 * math.pi, (N, T))
        along = np.where(ridge[:, None], a_r, rho * np.cos(th) * el[:, None])
        across = np.where(ridge[:, None], c_r, rho * np.sin(th) / el[:, None])
        cx, cy = world(along, across)
        dmin = np.full((N, T), np.inf)
        for j in range(k):
            d = np.hypot(cx - np.nan_to_num(dx[:, j, None], nan=1e9), cy - np.nan_to_num(dy[:, j, None], nan=1e9))
            dmin = np.minimum(dmin, d)
        ok = dmin >= sep[:, None]
        first = np.argmax(ok, axis=1)
        got = ok[np.arange(N), first] & want
        sel = np.nonzero(got)[0]
        dx[sel, k] = cx[sel, first[sel]]
        dy[sel, k] = cy[sel, first[sel]]
        u = np.hypot(along[sel, first[sel]] / el[sel], across[sel, first[sel]] * el[sel]) / np.maximum(R[sel], 1e-6)
        h[sel, k] = H[sel] * rng.uniform(0.6, 0.92, sel.size) * (1.0 - 0.25 * np.clip(u, 0.0, 1.0) ** 2)
        ang[sel, k] = rng.uniform(*pr['peak_deg'], sel.size)
    # the placed peaks first in every row (a dart that failed leaves a gap)
    order = np.argsort(np.isnan(h), axis=1, kind='stable')
    dx, dy, h, ang = (np.take_along_axis(a, order, 1) for a in (dx, dy, h, ang))
    has = ~np.isnan(h)
    count = has.sum(1).astype(np.int64)
    h = np.where(has & np.isfinite(floor)[:, None], np.maximum(h, floor[:, None] + 0.15 * H[:, None]), h)
    r0 = np.where(has, h / np.tan(np.radians(ang)), np.nan)
    b = np.where(has, np.where((kind == 0)[:, None], rng.uniform(*pr['spire_convexity'], (N, K)),
                               rng.uniform(*pr['peak_convexity'], (N, K))), np.nan)
    e = np.where(has, np.where(ridge[:, None], rng.uniform(0.3, 0.8, (N, K)), rng.uniform(0.0, 0.4, (N, K))), np.nan)
    ax = np.where(has, axis[:, None] + np.radians(rng.normal(0.0, 12.0, (N, K))), np.nan)
    return (dx, dy, h, r0, b, e, ax), count


RIB_ORDERS = np.arange(2, 8)          # the ribs' azimuthal harmonics


def rib_harmonics(rng, n, k, budget):
    """(n, k, 6) complex amplitudes of harmonics 2-7 of each summit cone's distance from its apex: the cone's
    distance is multiplied by g(theta) = 1 + sum_m Re(a_m e^{i m theta}). Along each ray from the apex the distance
    still grows (g >= 1 - s / 2 > 0), and across the rays the gradient of the scaled distance is sqrt(g^2 + g'^2),
    so with sum m |a_m| = s the flanks stand between 1 - s / 2 and sqrt((1 + s / 2)^2 + s^2) times the cone's slope
    (0.75-1.35 at s = 0.5) and never fold: ribs and gullies radiating from the apex, a few broad ones strongest
    (|a_m| ~ m^-1.3 x U(0.3, 1)). Each cone takes s = budget x U(0.5, 1); budget 0 gives zeros."""
    out = np.zeros((n, k, RIB_ORDERS.size), complex)
    if budget <= 0 or n == 0:
        return out
    w = rng.uniform(0.3, 1.0, (n, k, RIB_ORDERS.size)) * RIB_ORDERS[None, None, :] ** -1.3
    s = budget * rng.uniform(0.5, 1.0, (n, k))
    a = w * (s / (w * RIB_ORDERS[None, None, :]).sum(-1))[..., None]
    return a * np.exp(1j * rng.uniform(0.0, 2 * math.pi, (n, k, RIB_ORDERS.size)))


def scarp_sectors(rng, n, pr):
    """(n, 2, 3) collapse scarps: per tower 0, 1 or 2 (chances pr['scarps']), each (direction in radians, cos of its
    half-width scarp_deg, depth scarp_depth: the share of the footprint radius pulled in at its centre; 0 where a
    tower has none). The footprint's radius is multiplied by 1 - depth x smoothstep over the sector, so the wall
    stands high there under a concave face (the fresh faces where Guilin's towers shed their walls)."""
    out = np.zeros((n, 2, 3))
    if n == 0:
        return out
    p = np.asarray(pr['scarps'], np.float64)
    count = np.searchsorted(np.cumsum(p / p.sum()), rng.random(n), side='right')
    d0 = rng.uniform(0.0, 2 * math.pi, n)
    for s in range(2):
        on = count > s
        # a second scarp faces away from the first (100-260 degrees round): two sides shed, not one widened
        d = d0 if s == 0 else d0 + rng.uniform(math.radians(100.0), math.radians(260.0), n)
        out[:, s, 0] = d
        out[:, s, 1] = np.cos(np.radians(rng.uniform(*pr['scarp_deg'], n)))
        out[:, s, 2] = np.where(on, rng.uniform(*pr['scarp_depth'], n), 0.0)
    return out


def plan_karst(seed, domain, params=None, via=None, main=None):
    """The global plan over domain = (x0, y0, side) metres (the outermost level's window): the cluster field's
    threshold, the river course (passing near `via`, default the domain's centre), the blue-noise tower centres and
    every tower's shape numbers (module doc). main = (x0, y0, side), the main tile: cluster_cover is then the share
    of the main tile in clusters (else of the domain; a 2.6 km pattern puts few clusters in one tile, so a tile's own
    share would wander by seed). Deterministic for (seed, domain, params, via, main)."""
    pr = params_for(params)
    x0, y0, side = (float(v) for v in domain)
    salt = (int(seed) * 2654435761 + 97) & 0xFFFFFFF
    rng = np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x4B41525354])     # 'KARST'
    strike = _compass_to_rad(pr['strike_deg'])
    plan = KarstPlan(seed=int(seed), domain=(x0, y0, side), params=pr, salt=salt, strike=strike,
                     cluster_threshold=0.0, cluster_band=1.0,
                     main=tuple(float(v) for v in (main if main is not None else domain)))

    # the cluster field's threshold: the (1 - cover) quantile over the main tile (or the domain)
    n = 192
    mx0, my0, mside = (float(v) for v in (main if main is not None else domain))
    g = mx0 + (np.arange(n) + 0.5) * mside / n
    GX, GY = np.meshgrid(g, my0 + (np.arange(n) + 0.5) * mside / n)
    raw = _cluster_raw(salt, pr, strike, GX, GY)
    cover = float(np.clip(pr['cluster_cover'], 0.0, 1.0))
    if cover >= 1.0:
        plan.cluster_threshold = float(raw.min()) - 1.0
    elif cover <= 0.0:
        plan.cluster_threshold = float(raw.max()) + 1.0
    else:
        plan.cluster_threshold = float(np.quantile(raw, 1.0 - cover))
    plan.cluster_std = float(raw.std())
    plan.cluster_band = 0.12 * plan.cluster_std

    # the river: a least-cost course through the plain, then meanders; its flat water level, width and bends
    if pr['river']:
        plan.river, plan.river_dir = _river_course(plan, rng, via)
        plan.river_coarse, _ = _resample(plan.river, 40.0)
        plan.river_mid, plan.river_s = _resample(plan.river, 30.0)
        plan.river_kappa = _curvature(plan.river_mid, 150.0)
        s = plan.river_s
        wn = noise2(s, np.full_like(s, 0.5), 1800.0, salt + 61) / 0.3
        plan.river_hw = 0.5 * pr['river_width_m'] * np.clip(1.0 + pr['river_width_var'] * wn, 0.5, 1.6)
        plan.water_level = -pr['river_bank_m']

    # tower centres: Poisson-disc at spacing_m in the clusters and plain_spacing times that on the plain, the
    # plain's then thinned to plain_density
    r_cl = pr['spacing_m'] / 1.12                 # a maximal Poisson-disc set's nearest-neighbour median ~ 1.12 r
    r_pl = r_cl * max(pr['plain_spacing'], 1.0)

    def radius(x, y):
        m, _ = _cluster(plan, x, y)
        return r_pl + (r_cl - r_pl) * m

    margin = 0.5 * r_pl
    tx, ty, _tr = poisson_disc(int(rng.integers(1 << 31)), x0 - margin, y0 - margin, side + 2 * margin,
                               side + 2 * margin, radius, r_cl, r_pl)
    m, raw_t = _cluster(plan, tx, ty)
    keep = rng.random(tx.size) < (m + (1.0 - m) * pr['plain_density'])
    tx, ty, m, raw_t = tx[keep], ty[keep], m[keep], raw_t[keep]
    N = tx.size

    # heights; the kind of tower; its footprint
    interior = _interior_of(plan, raw_t)
    w = np.clip(0.5 * m + 0.5 * np.sqrt(interior), 0.0, 1.0)
    trend = np.exp(pr['height_trend'] * fbm2(tx, ty, 2000.0, 2, salt + 23) / 0.3)
    H = np.exp(pr['height_sigma'] * rng.standard_normal(N)) * trend * (0.85 + 0.3 * w)
    if N:
        H *= pr['median_height_m'] / max(float(np.median(H)), 1e-6)
    H = np.clip(H, 0.25 * pr['median_height_m'], 2.8 * pr['median_height_m'])    # Guilin's towers: 100-300 m
    F = np.minimum(_plinth_of(plan, tx, ty) * _base_membership(plan, tx, ty), 0.6 * H)   # the base under the foot
    H = H - F
    # the kind: a spire, a peak (most), a block; inside the clusters drawn out along the strike, so neighbours'
    # peaks string into rows with saddles between and flat corridors across
    in_cl = _smoothstep(0.3, 0.7, m)
    u_k = rng.random(N)
    slim_p = pr['slim_share'][0] * (1.0 - in_cl) + pr['slim_share'][1] * in_cl
    block_p = pr['block_share'][0] * (1.0 - in_cl) + pr['block_share'][1] * in_cl
    # the tallest towers are massifs, not single cones (a 400 m cone read as a pyramid): from 1.4 x the median height
    # up, the chance of a slim spire falls and half the rest become blocks (thresholds on the same draw)
    tall = _smoothstep(1.4, 2.4, (H + F) / max(pr['median_height_m'], 1e-6))
    slim_p = slim_p * (1.0 - tall)
    block_p = block_p + (1.0 - slim_p - block_p) * pr['tall_massif'] * tall
    kind = np.where(u_k < slim_p, 0, np.where(u_k < slim_p + block_p, 2, 1)).astype(np.int8)
    ang = np.where(kind == 0, _uni(rng, pr['spire_deg'], N), _uni(rng, pr['peak_deg'], N))
    nn3 = _knn_median(tx, ty, 3, 3.0 * pr['spacing_m'])
    # inside a cluster a peak's cone reaches toward its neighbours' (cluster_reach of the median distance to its three
    # nearest), so the cones meet at saddles and the cluster stands as one massif with its peaks on it; the cone's
    # angle follows from the peak's height over that reach, held to cluster_peak_deg (a short peak among far
    # neighbours keeps a steep cone and leaves a cockpit beside it)
    ang_cl = np.degrees(np.arctan(H / np.maximum(_uni(rng, pr['cluster_reach'], N) * nn3, 1.0)))
    ang_cl = np.clip(ang_cl, *pr['cluster_peak_deg'])
    # (by how deep inside: a cluster's edge towers keep the steep peaks of the plain, so the massif meets the plain
    # with sheer faces and its broad cones stand behind them)
    deep = in_cl * _smoothstep(0.0, 0.6, interior)
    ang = np.where(kind == 1, ang + (ang_cl - ang) * deep, ang)
    r0_main = H / np.tan(np.radians(ang))                 # the main cone's foot radius
    R_block = np.where(in_cl > 0.5, _uni(rng, pr['massif_reach'], N) * nn3, _uni(rng, pr['block_girth'], N) * H)
    # a peak's footprint: on the plain its wall cuts the cone inside its foot (a cliff 15-45 % of H); at a cluster's
    # edge cluster_girth of it (the wall facing the plain); deep inside a cluster the whole cone (inner_girth: no wall,
    # the flanks run down into the saddles and cockpits; its collapse scarps still stand sheer)
    g_cl = _uni(rng, pr['cluster_girth'], N) * (1.0 - interior) + _uni(rng, pr['inner_girth'], N) * interior
    g_peak = _uni(rng, pr['peak_girth'], N) * (1.0 - in_cl) + g_cl * in_cl
    R = np.select([kind == 0, kind == 1], [_uni(rng, pr['spire_girth'], N) * r0_main, g_peak * r0_main], R_block)
    R = np.maximum(R, 12.0)
    wall = np.clip(pr['wall_deg'] + rng.normal(0.0, pr['wall_spread_deg'], N), 70.0, 89.0)
    floor = np.full(N, -np.inf)
    floor[kind == 2] = (_uni(rng, pr['floor'], N) * H)[kind == 2]
    ridge = (rng.random(N) < pr['ridge_share'] + (1.0 - pr['ridge_share']) * pr['tall_massif'] * tall) & (kind != 0)
    e_cl = _uni(rng, pr['cluster_elong'], N)
    elong = np.where(ridge, rng.uniform(0.6, 1.1, N),
                     rng.uniform(0.0, pr['elongation'], N) * (1.0 - in_cl) + e_cl * in_cl)
    elong = np.where(kind == 0, np.minimum(elong, 0.35), elong)
    axis = strike + np.radians(rng.normal(0.0, 1.0, N) * (32.0 - 10.0 * in_cl))
    lean = rng.uniform(0.0, pr['lean'], N)
    lean_dir = rng.uniform(0.0, 2 * math.pi, N)
    # radial spurs: harmonics 2-5 of the footprint radius, weaker with order (buttresses and re-entrants)
    spur = (rng.uniform(0.0, 1.0, (N, 4)) * pr['spurs'] * np.array([1.0, 0.75, 0.55, 0.4])[None, :]) * \
        np.exp(1j * rng.uniform(0.0, 2 * math.pi, (N, 4)))
    B = pr['apron'] * H * rng.uniform(0.5, 1.5, N)
    reach = 1.6 * B / math.tan(math.radians(pr['apron_deg']))
    npk = np.where(kind == 2, rng.integers(2, int(pr['peaks_max']) + 1, N),
                   np.where(elong > 0.6, rng.integers(2, 4, N), 1)).astype(np.int64)
    pk, npk = _place_peaks(rng, pr, R, H, elong, axis, kind, np.minimum(npk, int(pr['peaks_max'])), floor, ang)
    # a cluster peak's profile toward the fengcong cone (concave) by how far inside the cluster it stands (its own
    # stream, so the plain's towers keep theirs)
    crng = np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x434F4E45])                        # 'CONE'
    b_cl = crng.uniform(*pr['cluster_convexity'], pk[4].shape)
    w_cl = np.where(kind == 1, deep, 0.0)[:, None]
    pk = pk[:4] + (np.where(np.isnan(pk[4]), np.nan, pk[4] + (b_cl - pk[4]) * w_cl),) + pk[5:]
    rib = rib_harmonics(np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x52494253]), N, int(pr['peaks_max']),
                        pr['ribs'])                                                               # 'RIBS'
    scarp = scarp_sectors(np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x53434152]), N, pr)   # 'SCAR'
    # a cluster's edge towers turn their first scarp toward the plain (down the cluster field's gradient), broad and
    # deep: the massif meets the plain with sheer faces (Guilin's towers are undercut where the floodplain meets them)
    edge = (in_cl > 0.3) & (interior < 0.6) & (kind != 0)
    if edge.any():
        e_ = 25.0
        rx = _cluster_raw(salt, pr, strike, tx + e_, ty) - _cluster_raw(salt, pr, strike, tx - e_, ty)
        ry = _cluster_raw(salt, pr, strike, tx, ty + e_) - _cluster_raw(salt, pr, strike, tx, ty - e_)
        erng = np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x45444745])                     # 'EDGE'
        out_dir = np.arctan2(-ry, -rx) + np.radians(erng.normal(0.0, 18.0, N))
        half = np.cos(np.radians(erng.uniform(50.0, 80.0, N)))
        depth = erng.uniform(*pr['edge_scarp'], N) * _smoothstep(0.6, 0.2, interior)
        scarp[edge, 0, 0] = out_dir[edge]
        scarp[edge, 0, 1] = half[edge]
        scarp[edge, 0, 2] = np.maximum(scarp[edge, 0, 2], depth[edge])
    # the massif body under a cluster's towers (its own stream): a walled pedestal reaching toward the neighbours, so
    # a cluster stands as one massif with its peaks on it, cols between them and cockpits where three or more bodies
    # leave a gap (Guilin's peak clusters at 30 m: 44 % of the tile 50 m and more over the plain; separate cones on a
    # low base held 29 %, a plain strewn with mounds)
    brng = np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x424F4459])                        # 'BODY'
    b_w = _smoothstep(0.35, 0.85, in_cl)
    body_h = _uni(brng, pr['body'], N) * H * b_w
    body_R = _uni(brng, pr['body_reach'], N) * nn3
    body_tan = np.tan(np.radians(_uni(brng, pr['body_deg'], N)))
    body_h = np.where(body_R > 1.1 * R, body_h, 0.0)
    # neighbours' bodies that would stand a slot apart (under body_gap_m) are drawn on until they meet: two walls a
    # few tens of metres apart leave no slot of plain between them, the gap fills with their rockfall (the col
    # between two peaks), so a cluster's plains are poljes and corridors wide open to the plain, or cockpits
    if N > 1 and pr['body_gap_m'] > 0:
        outer = np.where(body_h > 0, body_R, R) * (1.0 + 0.5 * elong)
        nb, dist = _knn(tx, ty, 4, 3.0 * pr['spacing_m'])
        for c in range(nb.shape[1]):
            j = nb[:, c]
            ok_j = j >= 0
            gap = np.where(ok_j, dist[:, c] - outer - outer[np.maximum(j, 0)], np.inf)
            close = ok_j & (gap > -5.0) & (gap < pr['body_gap_m']) & (body_h > 0)
            body_R = np.where(close, np.maximum(body_R, body_R + gap / (1.0 + 0.5 * elong) * 0.6 + 8.0), body_R)

    # no tower in the river's corridor: its foot, its talus and the river's banks stay clear (a body that would
    # reach it is cut back to the corridor's edge, or dropped)
    if plan.river is not None and N:
        grow = (1.0 + elong) * (1.0 + lean + np.abs(spur).sum(1))
        foot = R * grow + reach + 2.5 * pr['lobes_m']
        bank = 0.5 * pr['river_width_m'] * (1.0 + pr['river_width_var']) + 2.5 * pr['river_bank_m'] + 40.0
        clear = foot + bank
        d = _river_distance(plan.river_coarse, tx, ty, float(np.maximum(clear, body_R * grow).max()) + bank + 50.0)
        ok = d > clear
        body_R = np.minimum(body_R, np.maximum(d - bank - 2.5 * pr['lobes_m'], 0.0) / grow)
        body_h = np.where(body_R > 1.1 * R, body_h, 0.0)
        arrays = [tx, ty, H, F, R, wall, kind, floor, B, reach, elong, axis, lean, lean_dir, m, interior, spur, npk,
                  rib, scarp, body_h, body_R, body_tan]
        (tx, ty, H, F, R, wall, kind, floor, B, reach, elong, axis, lean, lean_dir, m, interior, spur, npk, rib,
         scarp, body_h, body_R, body_tan) = (a[ok] for a in arrays)
        pk = tuple(a[ok] for a in pk)
    # the skirt never climbs past body_top of the tower's height at its centre (a wide body round a narrow peak
    # otherwise rose over its own summit: 100 m onto the tile's relief)
    body_tan = np.minimum(body_tan, np.maximum(pr['body_top'] * H - body_h, 0.0) / np.maximum(body_R, 1.0))
    plan.body_h, plan.body_R, plan.body_tan = body_h, body_R, body_tan
    plan.pk_rib, plan.scarp = rib, scarp
    plan.x, plan.y, plan.H, plan.F, plan.R, plan.wall, plan.kind = tx, ty, H, F, R, wall, kind
    plan.floor, plan.B, plan.reach, plan.spur = floor, B, reach, spur
    plan.elong, plan.axis, plan.lean, plan.lean_dir = elong, axis, lean, lean_dir
    plan.cluster, plan.interior, plan.npk = m, interior, npk
    plan.pk_dx, plan.pk_dy, plan.pk_h, plan.pk_r0, plan.pk_b, plan.pk_e, plan.pk_axis = pk
    # every tower's wall table (its ledges), from its own stream: a tower keeps its wall whatever else changes
    plan.wall_D, plan.wall_Z, plan.wall_D0 = [], [], []
    for t in range(tx.size):
        D, Z, D0 = wall_table(np.random.default_rng([int(seed) & 0xFFFFFFFF, 0x57414C4C, t]), H[t], wall[t], pr)
        plan.wall_D.append(D)
        plan.wall_Z.append(Z)
        plan.wall_D0.append(D0)
    if tx.size:
        plan.stats = dict(towers=int(tx.size), density_per_km2=float(tx.size / (side / 1000.0) ** 2),
                          H_p10_p50_p90=[round(float(v), 1) for v in np.percentile(H + F, [10, 50, 90])],
                          R_p10_p50_p90=[round(float(v), 1) for v in np.percentile(R, [10, 50, 90])],
                          kinds=dict(spire=int((kind == 0).sum()), peak=int((kind == 1).sum()),
                                     block=int((kind == 2).sum()), ridge=int((elong > 0.6).sum())),
                          wall_p10_p50_p90=[round(float(v), 1) for v in np.percentile(wall, [10, 50, 90])])
    return plan


def _knn(x, y, k, max_d):
    """For every point, its k nearest other points within max_d: (indices (N, k), -1 where fewer; distances (N, k),
    inf there), nearest first."""
    n = x.size
    idx = np.full((n, k), -1, np.int64)
    dist = np.full((n, k), np.inf)
    if n < 2:
        return idx, dist
    bx = np.floor(x / max_d).astype(np.int64)
    by = np.floor(y / max_d).astype(np.int64)
    bins = {}
    for i, key in enumerate(zip(bx.tolist(), by.tolist())):
        bins.setdefault(key, []).append(i)
    for (cx, cy), members in bins.items():
        cand = np.asarray([j for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) for j in bins.get((cx + ddx, cy + ddy), ())])
        q = np.asarray(members)
        d = np.sqrt((x[q, None] - x[cand][None, :]) ** 2 + (y[q, None] - y[cand][None, :]) ** 2)
        d[q[:, None] == cand[None, :]] = np.inf
        d[d > max_d] = np.inf
        kk = min(k, d.shape[1])
        order = np.argsort(d, axis=1)[:, :kk]
        dd = np.take_along_axis(d, order, 1)
        ii = np.where(np.isfinite(dd), cand[order], -1)
        idx[q, :kk] = ii
        dist[q, :kk] = dd
    return idx, dist


def _knn_median(x, y, k, max_d):
    """For every point, the median of its distances to its k nearest other points (metres; at most max_d)."""
    out = np.full(x.shape, float(max_d))
    if x.size < 2:
        return out
    bx = np.floor(x / max_d).astype(np.int64)
    by = np.floor(y / max_d).astype(np.int64)
    bins = {}
    for i, key in enumerate(zip(bx.tolist(), by.tolist())):
        bins.setdefault(key, []).append(i)
    for (cx, cy), idx in bins.items():
        cand = np.asarray([j for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) for j in bins.get((cx + ddx, cy + ddy), ())])
        q = np.asarray(idx)
        d = np.sqrt((x[q, None] - x[cand][None, :]) ** 2 + (y[q, None] - y[cand][None, :]) ** 2)
        d[q[:, None] == cand[None, :]] = np.inf
        kk = min(k, d.shape[1] - 1)
        if kk < 1:
            continue
        part = np.sort(d, axis=1)[:, :kk]
        out[q] = np.minimum(np.median(part, axis=1), max_d)
    return out


# ---------------------------------------------------------------- the river course
def _dijkstra(cost, start, goal):
    """Least-cost 8-connected path on a grid of cell costs; [(j, i), ...] from start to goal."""
    ny, nx = cost.shape
    dist = np.full(cost.shape, np.inf)
    prev = -np.ones(cost.shape, np.int64)
    dist[start] = 0.0
    heap = [(0.0, start[0], start[1])]
    steps = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while heap:
        d, j, i = heapq.heappop(heap)
        if d > dist[j, i]:
            continue
        if (j, i) == goal:
            break
        for dj, di in steps:
            jj, ii = j + dj, i + di
            if 0 <= jj < ny and 0 <= ii < nx:
                nd = d + 0.5 * (cost[j, i] + cost[jj, ii]) * (1.4142135 if dj and di else 1.0)
                if nd < dist[jj, ii]:
                    dist[jj, ii] = nd
                    prev[jj, ii] = j * nx + i
                    heapq.heappush(heap, (nd, jj, ii))
    path = [goal]
    while path[-1] != start:
        k = prev[path[-1]]
        if k < 0:
            break
        path.append((int(k // nx), int(k % nx)))
    return path[::-1]


def _chaikin(pts, times):
    for _ in range(times):
        q = 0.75 * pts[:-1] + 0.25 * pts[1:]
        r = 0.25 * pts[:-1] + 0.75 * pts[1:]
        mid = np.empty((2 * len(q), 2))
        mid[0::2], mid[1::2] = q, r
        pts = np.vstack([pts[:1], mid, pts[-1:]])
    return pts


def _resample(pts, step):
    seg = np.hypot(*(pts[1:] - pts[:-1]).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.append(np.arange(0.0, s[-1], step), s[-1])
    return np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], 1), t


def _curvature(pts, smooth_m):
    """Signed curvature (1/m, + turning left) at each vertex of an evenly resampled polyline, from the turning angle
    of its neighbouring segments, smoothed by a Gaussian of smooth_m along the line."""
    t = np.diff(pts, axis=0)
    ang = np.unwrap(np.arctan2(t[:, 1], t[:, 0]))
    seg = np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)
    k = np.zeros(len(pts))
    k[1:-1] = np.diff(ang) / (0.5 * (seg[1:] + seg[:-1]))
    step = float(np.median(seg))
    sig = max(smooth_m / step, 0.5)
    r = int(math.ceil(3 * sig))
    w = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    w /= w.sum()
    return np.convolve(np.pad(k, r, mode='edge'), w, mode='valid')


def _river_course(plan, rng, via):
    """A river across the domain: a least-cost course through the plain (low cluster membership) from the upstream
    edge, near `via`, to the downstream edge; smoothed, then given meanders by a lateral offset of smooth 1-D noise
    along its length. Returns (polyline (N, 2) metres upstream first at 10 m steps, flow direction (dx, dy))."""
    pr = plan.params
    x0, y0, side = plan.domain
    n = 160
    cs = side / n
    g = x0 + (np.arange(n) + 0.5) * cs
    GX, GY = np.meshgrid(g, y0 + (np.arange(n) + 0.5) * cs)
    m, _ = _cluster(plan, GX, GY)
    az = pr['river_azimuth_deg']
    if az is None:
        az = float(rng.uniform(0.0, 360.0))
    a = _compass_to_rad(az)
    d = np.array([math.cos(a), math.sin(a)])
    vx, vy = (x0 + side / 2, y0 + side / 2) if via is None else (float(via[0]), float(via[1]))
    # the cost: clusters are expensive (the river finds the plain), and a soft pull toward the line through `via`
    # along the flow direction keeps the course passing the main tile without a forced waypoint (no doubling back)
    off_line = np.abs(-(GX - vx) * d[1] + (GY - vy) * d[0])
    cost = 1.0 + 60.0 * m ** 2 + 0.6 * (fbm2(GX, GY, 1200.0, 2, plan.salt + 41) + 1.0) + \
        3.0 * (off_line / max(0.12 * side, 1.0)) ** 2

    def edge_cell(sign):
        p = np.array([vx, vy]) + sign * d * side * 1.5
        p = np.clip(p, [x0 + 0.5 * cs, y0 + 0.5 * cs], [x0 + side - 0.5 * cs, y0 + side - 0.5 * cs])
        return int((p[1] - y0) // cs), int((p[0] - x0) // cs)

    up, down = edge_cell(-1.0), edge_cell(+1.0)
    cells = _dijkstra(cost, up, down)
    pts = np.array([[x0 + (i + 0.5) * cs, y0 + (j + 0.5) * cs] for j, i in cells], np.float64)
    pts = _chaikin(pts, 4)
    pts, s = _resample(pts, 20.0)
    w = pr['river_width_m']
    t = np.gradient(pts, axis=0)
    t /= np.maximum(np.hypot(t[:, 0], t[:, 1])[:, None], 1e-9)
    nrm = np.stack([-t[:, 1], t[:, 0]], 1)
    lam = 13.0 * w                                       # meander wavelength ~ 13 channel widths
    off = pr['river_meander'] * w * (1.6 * noise2(s, np.full_like(s, 0.5), lam, plan.salt + 53)
                                     + 0.55 * noise2(s, np.full_like(s, 0.5), 0.45 * lam, plan.salt + 59))
    pts = _chaikin(pts + nrm * off[:, None], 2)
    pts, _ = _resample(pts, 10.0)
    flow = pts[-1] - pts[0]
    flow = flow / max(float(np.hypot(*flow)), 1e-9)
    return pts, (float(flow[0]), float(flow[1]))


def _river_bins(poly, X, Y, max_d):
    """Shared binning of _river_distance and _river_frame: yields (point indices, segment indices) of each bin of
    segments against the points in the 3 x 3 bins around it (bins of max_d + 20 m plus the longest segment)."""
    B = float(max_d) + 20.0
    a = poly[:-1]
    ab = poly[1:] - a
    mid = a + 0.5 * ab
    reach = B + float(np.hypot(*ab.T).max())                 # only the segments that can be within max_d
    keep = ((mid[:, 0] > X.min() - reach) & (mid[:, 0] < X.max() + reach) &
            (mid[:, 1] > Y.min() - reach) & (mid[:, 1] < Y.max() + reach))
    if not keep.any():
        return
    seg_ids = np.nonzero(keep)[0]
    mid = mid[keep]
    sbx = np.floor(mid[:, 0] / B).astype(np.int64)
    sby = np.floor(mid[:, 1] / B).astype(np.int64)
    pbx = np.floor(X / B).astype(np.int64)
    pby = np.floor(Y / B).astype(np.int64)
    ox, oy = int(pbx.min()), int(pby.min())
    W = int(pbx.max()) - ox + 1
    Hh = int(pby.max()) - oy + 1
    key = (pby - oy) * W + (pbx - ox)
    order = np.argsort(key, kind='stable')
    sk = key[order]
    uk, st = np.unique(sk, return_index=True)
    en = np.append(st[1:], sk.size)
    span = {int(k): (int(s), int(e)) for k, s, e in zip(uk, st, en)}
    segs = {}
    for s, k in enumerate(zip(sbx.tolist(), sby.tolist())):
        segs.setdefault(k, []).append(int(seg_ids[s]))
    for (bx, by), sl in segs.items():
        parts = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                cx, cy = bx + dx - ox, by + dy - oy
                if 0 <= cx < W and 0 <= cy < Hh:
                    se = span.get(cy * W + cx)
                    if se is not None:
                        parts.append(order[se[0]:se[1]])
        if parts:
            yield np.concatenate(parts), np.asarray(sl)


def _river_distance(poly, X, Y, max_d):
    """Distance (metres) from points X, Y to a polyline, capped at max_d: segments and points are binned on a grid
    of max_d + 20 m, and each bin of segments is measured only against the points in the 3 x 3 bins around it."""
    X = np.asarray(X, np.float64).ravel()
    Y = np.asarray(Y, np.float64).ravel()
    out = np.full(X.shape, float(max_d))
    if poly is None or X.size == 0:
        return out
    a = poly[:-1]
    ab = poly[1:] - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-12)
    for idx, sg in _river_bins(poly, X, Y, max_d):
        px, py = X[idx], Y[idx]
        best = out[idx]
        for c0 in range(0, idx.size, 32768):
            xx = px[c0:c0 + 32768, None]
            yy = py[c0:c0 + 32768, None]
            t = np.clip(((xx - a[sg, 0]) * ab[sg, 0] + (yy - a[sg, 1]) * ab[sg, 1]) / L2[sg], 0, 1)
            ddx = a[sg, 0] + t * ab[sg, 0] - xx
            ddy = a[sg, 1] + t * ab[sg, 1] - yy
            best[c0:c0 + 32768] = np.minimum(best[c0:c0 + 32768], np.sqrt((ddx * ddx + ddy * ddy).min(1)))
        out[idx] = best
    return np.minimum(out, max_d)


def _river_frame(poly, s_vert, X, Y, max_d):
    """(signed distance, arc length): for points X, Y within max_d of the polyline (whose vertices sit at arc
    lengths s_vert), the distance to its nearest point, positive on the left of the flow, and that point's arc
    length; points farther away get +max_d and the arc length of the nearest vertex found (or 0)."""
    X = np.asarray(X, np.float64).ravel()
    Y = np.asarray(Y, np.float64).ravel()
    dist = np.full(X.shape, float(max_d))
    sgn = np.ones(X.shape)
    sa = np.zeros(X.shape)
    if poly is None or X.size == 0:
        return dist, sa
    a = poly[:-1]
    ab = poly[1:] - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-12)
    for idx, sg in _river_bins(poly, X, Y, max_d):
        px, py = X[idx], Y[idx]
        for c0 in range(0, idx.size, 16384):
            xx = px[c0:c0 + 16384, None]
            yy = py[c0:c0 + 16384, None]
            t = np.clip(((xx - a[sg, 0]) * ab[sg, 0] + (yy - a[sg, 1]) * ab[sg, 1]) / L2[sg], 0, 1)
            ddx = xx - (a[sg, 0] + t * ab[sg, 0])
            ddy = yy - (a[sg, 1] + t * ab[sg, 1])
            d2 = ddx * ddx + ddy * ddy
            k = np.argmin(d2, axis=1)
            r = np.arange(k.size)
            d = np.sqrt(d2[r, k])
            sel = idx[c0:c0 + 16384]
            better = d < dist[sel]
            sel_b = sel[better]
            kk = sg[k[better]]
            tt = t[r, k][better]
            dist[sel_b] = d[better]
            cross = ab[kk, 0] * ddy[r, k][better] - ab[kk, 1] * ddx[r, k][better]
            sgn[sel_b] = np.where(cross >= 0.0, 1.0, -1.0)
            sa[sel_b] = s_vert[kk] + tt * (s_vert[kk + 1] - s_vert[kk])
    return np.minimum(dist, max_d) * sgn, sa


# ---------------------------------------------------------------- evaluation on a level
def supersampling_for(cell):
    """Subsamples per cell axis: a wall spans a few metres, so levels coarser than 2.5 m average 2 x 2 subsamples
    per cell (the horizon levels are drawn at a 2-cell vertex stride: more would buy nothing visible)."""
    return 1 if cell <= 2.5 else 2


class _Grid:
    """A level's subsample grid and a way to put smooth world fields on it: a field is evaluated on a lattice of
    `stride` cells (aligned with the level's cell centres, one sample of rim) and bilinearly interpolated."""

    def __init__(self, x0, y0, cell, n, ss):
        self.x0, self.y0, self.cell, self.n, self.ss = x0, y0, cell, n, ss
        self.sub = cell / ss
        self.N = n * ss
        self.xs = x0 + (np.arange(self.N) + 0.5) * self.sub
        self.ys = y0 + (np.arange(self.N) + 0.5) * self.sub

    def smooth(self, fn, shortest_m):
        """fn(X, Y) of world metres, on the subsample grid; sampled every max(1, shortest_m / 8 / cell) cells. A
        lattice coarser than one cell is anchored to world coordinates (its nodes at 0.5 cell + j step), so two
        windows of one cell size sample a field at the same nodes and agree where they overlap."""
        k = max(1, int(shortest_m / (8.0 * self.cell)))
        step = k * self.cell
        m = int(math.ceil(self.n / k)) + 3
        if k == 1:
            lx = self.x0 + 0.5 * self.cell + (np.arange(m) - 1) * step
            ly = self.y0 + 0.5 * self.cell + (np.arange(m) - 1) * step
        else:
            jx = math.floor((self.x0 - 0.5 * self.cell) / step) - 1
            jy = math.floor((self.y0 - 0.5 * self.cell) / step) - 1
            lx = 0.5 * self.cell + (jx + np.arange(m + 1)) * step
            ly = 0.5 * self.cell + (jy + np.arange(m + 1)) * step
            m = m + 1
        v = np.broadcast_to(np.asarray(fn(lx[None, :], ly[:, None]), np.float64), (m, m))   # separable lattice
        if k == 1 and self.ss == 1:
            return v[1:self.n + 1, 1:self.n + 1]
        tx = (self.xs - lx[0]) / step
        ty = (self.ys - ly[0]) / step
        i0 = np.clip(np.floor(tx).astype(np.intp), 0, m - 2)
        j0 = np.clip(np.floor(ty).astype(np.intp), 0, m - 2)
        fx = tx - i0
        fy = ty - j0
        rows = v[j0] * (1 - fy)[:, None] + v[j0 + 1] * fy[:, None]
        return rows[:, i0] * (1 - fx)[None, :] + rows[:, i0 + 1] * fx[None, :]

    def down(self, a):
        """Subsamples to cells: the mean of each cell's ss x ss subsamples."""
        if self.ss == 1:
            return a
        return a.reshape(self.n, self.ss, self.n, self.ss).mean(axis=(1, 3))


def _bilinear_sep(v, lx, ly, qx, qy):
    """Values v on a separable lattice (rows ly, columns lx, evenly spaced), bilinear at query columns qx, rows qy."""
    tx = (qx - lx[0]) / (lx[1] - lx[0])
    ty = (qy - ly[0]) / (ly[1] - ly[0])
    i0 = np.clip(np.floor(tx).astype(np.intp), 0, len(lx) - 2)
    j0 = np.clip(np.floor(ty).astype(np.intp), 0, len(ly) - 2)
    fx = np.clip(tx - i0, 0.0, 1.0)
    fy = np.clip(ty - j0, 0.0, 1.0)
    rows = v[j0] * (1 - fy)[:, None] + v[j0 + 1] * fy[:, None]
    return rows[:, i0] * (1 - fx)[None, :] + rows[:, i0 + 1] * fx[None, :]


def _river_frame_level(plan, G, band):
    """The river's frame on a level's subsample grid: (d, s, far). far: the unsigned distance on a lattice of
    20-80 m, bilinear, smooth everywhere (the plain's gentle rise reads it, so it has no seam). Near the channel
    (within `band` metres, with a margin for the bilinear far field's overestimate), d is the exact signed distance
    (+ left of the flow) and s the arc length along river_mid, at the cell centres, then bilinear to the subsamples;
    elsewhere d = far and s = 0."""
    # the far field's lattice: its step set by the cell alone and its nodes anchored to world coordinates, so every
    # window of one cell size reads the same far field
    stepf = float(np.clip(8.0 * G.cell, max(G.cell, 20.0), max(80.0, G.cell)))
    kf = max(1, int(round(stepf / G.cell)))
    stepf = kf * G.cell
    mf = int(math.ceil(G.n / kf)) + 4
    jx = math.floor((G.x0 - 0.5 * G.cell) / stepf) - 1
    jy = math.floor((G.y0 - 0.5 * G.cell) / stepf) - 1
    lxf = 0.5 * G.cell + (jx + np.arange(mf)) * stepf
    lyf = 0.5 * G.cell + (jy + np.arange(mf)) * stepf
    XF, YF = np.meshgrid(lxf, lyf)
    df = _river_distance(plan.river_coarse, XF, YF, 1500.0).reshape(XF.shape)
    lxc = G.x0 + (np.arange(-1, G.n + 1) + 0.5) * G.cell
    lyc = G.y0 + (np.arange(-1, G.n + 1) + 0.5) * G.cell
    dc = _bilinear_sep(df, lxf, lyf, lxc, lyc)
    far = dc.copy()
    sc = np.zeros_like(dc)
    margin = 0.75 * stepf + 2.0 * G.cell
    near = dc < band + margin
    if near.any():
        jj, ii = np.nonzero(near)
        d_s, s_a = _river_frame(plan.river_mid, plan.river_s, lxc[ii], lyc[jj], band + margin + 10.0)
        dc[near] = d_s
        sc[near] = s_a
    if G.ss == 1:
        return dc[1:-1, 1:-1], sc[1:-1, 1:-1], far[1:-1, 1:-1]
    # the magnitude and the side are interpolated apart: the signed value jumps where the exact band meets the
    # unsigned far field, and interpolated across that jump it passed through 0 (a false channel along the band)
    mag = _bilinear_sep(np.abs(dc), lxc, lyc, G.xs, G.ys)
    side = np.where(_bilinear_sep(np.sign(dc), lxc, lyc, G.xs, G.ys) >= 0.0, 1.0, -1.0)
    return mag * side, _bilinear_sep(sc, lxc, lyc, G.xs, G.ys), _bilinear_sep(far, lxc, lyc, G.xs, G.ys)


def evaluate(plan, x0, y0, cell, n, ss=None, fill=True):
    """The karst surface on one level: an (n, n) window of `cell`-metre cells whose south-west corner is (x0, y0).
    Each cell is the mean of ss x ss subsamples (default supersampling_for(cell)); fill=False leaves the cockpits
    unfilled. Returns float32 arrays:
      h        the surface;
      bed      the top of rock: towers, and the buried rock under the alluvium and the cockpit soil;
      deposit  soil, alluvium and talus thickness, h - bed;
      talus    the talus cones' thickness at the towers' feet;
      water    the river's depth (its surface flat at the plan's water level: the lake builder draws it);
      river    the same (the older name);
      Sc       the threshold slope (tangent) for the recipe's threshold pass;
      plain    the plain's level (no towers, no channel);
    and tower_id (int32: the tower whose wall or summit is the surface at the cell's centre subsample, its massif
    body's wall included, its body's skirt and a cockpit's soil floor not; -1 elsewhere)."""
    pr = plan.params
    G = _Grid(float(x0), float(y0), float(cell), int(n), int(ss or supersampling_for(cell)))
    N, sub = G.N, G.sub
    lim = 2.5 * cell
    f32 = np.float32
    # lobes: a radial displacement in metres (spurs and re-entrants of every footprint); each octave's amplitude
    # stays near a tenth of its wavelength, so the displaced contours never fold
    LOB = G.smooth(lambda X, Y: pr['lobes_m'] * (noise2(X, Y, 130.0, plan.salt + 101)
                                                 + 0.45 * noise2(X, Y, 60.0, plan.salt + 102)) / 0.33,
                   max(60.0, lim)).astype(f32)
    # the beds' undulation for the summits' benches (+-3 m over 160 m); a level whose cells are coarser than a bench
    # takes none (the benches would alias)
    if pr['benches'] > 0 and pr['bench_m'] >= 4.0 * cell:
        BENCH = G.smooth(lambda X, Y: 3.0 * fbm2(X, Y, 160.0, 2, plan.salt + 161, 0.5) / 0.33,
                         max(60.0, lim)).astype(f32)
    else:
        BENCH = None
    # the summit cones' gentle distance jitter (the ribs bend, the feet bulge): long wavelengths only, so the
    # jittered distance's gradient stays near 1 even 150 m from an apex (at 45 m down to 6 m it folded the cones into
    # fences of blades)
    JAG = G.smooth(lambda X, Y: pr['jag'] * fbm2(X, Y, 90.0, 2, plan.salt + 131, 0.45, lim) / 0.3,
                   max(40.0, lim)).astype(f32)
    # where the walls' ledges hold (1) and where they have broken off (0); a ledge is under 1.5 m wide, so a level
    # coarser than 2.5 m takes the mean (the share of the wall they hold along)
    if cell <= 2.5:
        LEDGE = G.smooth(lambda X, Y: _smoothstep(0.5 - pr['ledge_cover'] - 0.12, 0.5 - pr['ledge_cover'] + 0.12,
                                                  0.5 + fbm2(X, Y, 30.0, 2, plan.salt + 141, 0.5, lim) / 0.6),
                         max(8.0, lim)).astype(f32)
    else:
        LEDGE = None

    # the blocks' caps: lumps and knobs in patches, evaluated on each block's own box (blocks are few)
    # (the knobs' patches: the noise below has a std of about 0.56, so its crown_cover quantile centres the edge)
    from statistics import NormalDist
    c_cov = 0.56 * NormalDist().inv_cdf(float(np.clip(1.0 - pr['crown_cover'], 0.02, 0.98)))

    def cap_rough(X, Y, H):
        lump = pr['floor_rough'] * H * fbm2(X, Y, 45.0, 2, plan.salt + 137, 0.5, lim) / 0.3
        # knobs over crown_cover of a cap, in patches (all over, they serrated every massif's crest into a comb); a
        # level too coarse for them takes their mean height (0.35 of their apexes) under the same patches, so its
        # parent and child carry the same cap on average
        patch = _smoothstep(c_cov - 0.3, c_cov + 0.3, fbm2(X, Y, 180.0, 2, plan.salt + 151) / 0.3 * 0.5)
        if pr['crown_spacing_m'] >= 3.0 * cell:
            knob = pinnacles(X, Y, pr['crown_spacing_m'], plan.salt + 149) * patch
        else:
            knob = 0.35 * patch
        return (lump + pr['crown'] * H * knob).astype(f32)

    # the same lumps and knobs as level-wide fields (made on first use, on G.smooth's world-anchored lattice), for
    # the peaks' upper flanks and the massif bodies: every tower's box reads them instead of evaluating the noise
    rough = {}

    def rough_box(j0, j1, i0, i1, H):
        if not rough:
            rough['lump'] = G.smooth(lambda X, Y: fbm2(X, Y, 45.0, 2, plan.salt + 137, 0.5, lim) / 0.3,
                                     max(22.5, lim)).astype(f32)

            def knobs(X, Y):
                patch = _smoothstep(c_cov - 0.3, c_cov + 0.3, fbm2(X, Y, 180.0, 2, plan.salt + 151) / 0.3 * 0.5)
                if pr['crown_spacing_m'] >= 3.0 * cell:
                    return pinnacles(X, Y, pr['crown_spacing_m'], plan.salt + 149) * patch
                return 0.35 * patch
            rough['knob'] = G.smooth(knobs, max(0.5 * pr['crown_spacing_m'], lim)).astype(f32)
        return (f32(pr['floor_rough'] * H) * rough['lump'][j0:j1, i0:i1]
                + f32(pr['crown'] * H) * rough['knob'][j0:j1, i0:i1])

    # ---- the plain and the river
    plain = _plain(plan, G)

    # ---- the common base (fengcong's plinth; fenglin's ground between a cluster's inner towers): every tower rises
    # from the base under each of its cells, so none stands on a pedestal where the base thins out
    if (pr['plinth_m'] > 0 or pr['base_m'] > 0) and plan.count:
        # fengcong's plinth edge is a step: sampled at cell resolution, or it aliases into a dashed line along every
        # edge; fenglin's base varies at 120 m and up
        PM = G.smooth(lambda X, Y: _plinth_of(plan, X, Y) * _base_membership(plan, X, Y),
                      8.0 * cell if pr['plinth_m'] > 0 else max(240.0, 8.0 * cell)).astype(f32)
    else:
        PM = None

    # ---- towers on the common base (rock heights relative to the plain's level)
    NEG = f32(-1.0e9)
    rock = np.full((N, N), NEG, f32)        # rock, each tower's wall continuing steeply below its foot
    scree = np.zeros((N, N), f32)           # the talus cones' surface over the rock (0 where none)
    owner = np.full((N, N), -1, np.int32)
    flute_on = cell <= 2.0 and pr['fluting_m'] > 0
    tan_under = f32(math.tan(math.radians(85.0)))     # the rock under the alluvium, past the foot
    tan_apron = f32(math.tan(math.radians(pr['apron_deg'])))
    if plan.count:
        # each tower's box holds everything it shapes: its footprint, spurs, lobes, talus and peaks
        body_on = plan.body_h is not None
        R_out = np.maximum(plan.R, np.where(plan.body_h > 0, plan.body_R, 0.0)) if body_on else plan.R
        ext = R_out * (1.0 + plan.elong) * (1.0 + plan.lean + np.abs(plan.spur).sum(1)) + plan.reach + \
            4.0 * pr['lobes_m'] + pr['fluting_m'] + 2.0 * cell
        xe, ye = G.x0 + N * sub, G.y0 + N * sub
        hit = (plan.x + ext > G.x0) & (plan.x - ext < xe) & (plan.y + ext > G.y0) & (plan.y - ext < ye)
        xs_l = (G.xs - G.x0).astype(f32)                # window-local metres: float32 keeps millimetres here
        ys_l = (G.ys - G.y0).astype(f32)
        for t in np.nonzero(hit)[0]:
            cx, cy, e_ = plan.x[t], plan.y[t], ext[t]
            i0 = max(int((cx - e_ - G.x0) / sub), 0)
            i1 = min(int(math.ceil((cx + e_ - G.x0) / sub)) + 1, N)
            j0 = max(int((cy - e_ - G.y0) / sub), 0)
            j1 = min(int(math.ceil((cy + e_ - G.y0) / sub)) + 1, N)
            if i1 <= i0 or j1 <= j0:
                continue
            dx = xs_l[i0:i1][None, :] - f32(cx - G.x0)
            dy = ys_l[j0:j1][:, None] - f32(cy - G.y0)
            r = np.sqrt(dx * dx + dy * dy)
            ca, sa = f32(math.cos(plan.axis[t])), f32(math.sin(plan.axis[t]))
            el = f32(1.0 + plan.elong[t])
            re = np.sqrt(((dx * ca + dy * sa) / el) ** 2 + ((dy * ca - dx * sa) * el) ** 2)
            rinv = f32(1.0) / np.maximum(r, f32(1e-3))
            c1, s1 = dx * rinv, dy * rinv                    # cos and sin of the direction from the axis
            stretch = f32(1.0) + f32(plan.lean[t]) * (c1 * f32(math.cos(plan.lean_dir[t]))
                                                      + s1 * f32(math.sin(plan.lean_dir[t])))
            if pr['spurs'] > 0:
                # harmonics 2-5 by the angle-addition recurrences (no trigonometry per sample)
                c2, s2 = c1 * c1 - s1 * s1, f32(2.0) * c1 * s1
                c3, s3 = c2 * c1 - s2 * s1, s2 * c1 + c2 * s1
                c4, s4 = c2 * c2 - s2 * s2, f32(2.0) * c2 * s2
                c5, s5 = c4 * c1 - s4 * s1, s4 * c1 + c4 * s1
                sp = plan.spur[t]
                for ck, sk, a in ((c2, s2, sp[0]), (c3, s3, sp[1]), (c4, s4, sp[2]), (c5, s5, sp[3])):
                    stretch = stretch + f32(a.real) * ck - f32(a.imag) * sk
            if plan.scarp is not None:
                # collapse scarps: the footprint pulled in over a sector, so the wall stands high there
                for sc_dir, sc_cos, sc_depth in plan.scarp[t]:
                    if sc_depth <= 0:
                        continue
                    cosd = c1 * f32(math.cos(sc_dir)) + s1 * f32(math.sin(sc_dir))
                    u_ = np.clip((cosd - f32(sc_cos)) / f32(max(1.0 - sc_cos, 1e-3)), f32(0.0), f32(1.0))
                    stretch = stretch * (f32(1.0) - f32(sc_depth) * u_ * u_ * (f32(3.0) - f32(2.0) * u_))
            R = float(plan.R[t])
            # metres inside the footprint's edge (negative outside), the lobes moving the edge
            d_in = f32(R) - (re / stretch - LOB[j0:j1, i0:i1])
            flo = None
            if flute_on:
                # vertical flutes: a periodic noise of the direction from the axis only, so every groove runs
                # straight down the wall (the same offset at every height). Each octave only where the level holds
                # its spacing in 4 cells or more (7 m flutes from 1.75 m cells, 2.9 m from 0.72 m): sampled coarser
                # they alias into random vertical streaks
                theta = np.arctan2(dy, dx).astype(np.float64)
                fl, wsum = 0.0, 0.0
                for k_, (spacing, wgt, salt_) in enumerate(((7.0, 0.7, 211), (2.9, 0.3, 223))):
                    if spacing < 4.0 * cell:
                        continue
                    per = max(int(round(2 * math.pi * R / spacing)), 3)
                    g_ = (theta + math.pi) / (2 * math.pi) * per
                    fl = fl + wgt * (1.0 - np.abs(_noise1_periodic(g_, per, plan.salt + salt_ + t)))
                    wsum += wgt
                if wsum > 0:
                    flo = (pr['fluting_m'] * (fl - 0.55 * wsum)).astype(f32)
                    d_in = d_in - flo
            # the wall: its table (notch, bands, ledges) read at the distance inside the edge, the ledges where they
            # hold; past the foot the rock dips steeply under the alluvium
            wl = np.interp(d_in, plan.wall_D[t], plan.wall_Z[t]).astype(f32)
            w0 = np.interp(d_in, plan.wall_D0[t], plan.wall_Z[t]).astype(f32)
            lg = LEDGE[j0:j1, i0:i1] if LEDGE is not None else f32(pr['ledge_cover'])
            wallz = w0 + (wl - w0) * lg
            wallz = np.where(d_in < 0, d_in * tan_under, wallz)
            # the summit: the highest of the tower's peak cones (elongated, their distance jittered), over its floor
            H = float(plan.H[t])
            fl_t = float(plan.floor[t])
            jag = f32(1.0) + JAG[j0:j1, i0:i1]
            if np.isfinite(fl_t):
                # a block's cap: from its cliff top (the floor, at the footprint's edge) a rough cone rising to
                # cap_top of its height at the centre (its distance jittered like the peaks'), lumpy, with knobs in
                # patches; its peaks (the summit and the lower knobs) stand on it
                frac = np.clip(d_in / f32(R) / jag, f32(0.0), f32(1.0))
                summit = (f32(fl_t) + f32(pr['cap_top'] * H - fl_t) * frac
                          + cap_rough(G.xs[i0:i1][None, :], G.ys[j0:j1][:, None], H))
            else:
                summit = np.full(d_in.shape, NEG, f32)
            for k in range(int(plan.npk[t])):
                pdx = dx - f32(plan.pk_dx[t, k])
                pdy = dy - f32(plan.pk_dy[t, k])
                pa = float(plan.pk_axis[t, k])
                pc, ps = f32(math.cos(pa)), f32(math.sin(pa))
                pe = f32(1.0 + plan.pk_e[t, k])
                pu = (pdx * pc + pdy * ps) / pe
                pv = (pdy * pc - pdx * ps) * pe
                rho = np.sqrt(pu * pu + pv * pv)
                if plan.pk_rib is not None and np.any(plan.pk_rib[t, k] != 0):
                    # the cone's ribs: its distance x g(theta), harmonics 2-7 by the angle-addition recurrences
                    rinv_k = f32(1.0) / np.maximum(rho, f32(1e-3))
                    c1, s1 = pu * rinv_k, pv * rinv_k
                    cm, sm = c1, s1
                    g_rib = np.ones_like(rho)
                    for m_ in range(2, 8):
                        cm, sm = cm * c1 - sm * s1, sm * c1 + cm * s1
                        a_ = plan.pk_rib[t, k, m_ - 2]
                        g_rib = g_rib + f32(a_.real) * cm - f32(a_.imag) * sm
                    rho = rho * g_rib
                rho = rho * jag
                if flo is not None:
                    rho = rho + flo                      # the flutes run on up the peak's flanks
                x = rho / f32(plan.pk_r0[t, k])
                b = f32(plan.pk_b[t, k])
                z = f32(plan.pk_h[t, k]) * np.where(x <= f32(1.0), f32(1.0) - x + b * x * (f32(1.0) - x),
                                                    -(f32(1.0) + b) * (x - f32(1.0)))   # (cone_profile)
                np.maximum(summit, z, out=summit)
            if pr['peak_rough'] > 0 and not np.isfinite(fl_t):
                # lumps and knobs over the peak's upper flanks (a block's cap has its own): fading in from 35 % of
                # the height up, so the wall below stays clean
                up = _smoothstep(0.35, 0.75, summit / f32(H)).astype(f32)
                summit = summit + f32(pr['peak_rough']) * up * rough_box(j0, j1, i0, i1, H)
            if BENCH is not None:
                # the beds' benches across the summit's flanks: ledges and risers, horizontal but for the beds'
                # undulation, fading out over the top quarter so the summit stays pointed
                bm = f32(pr['bench_m'])
                kb = f32(pr['benches']) * _smoothstep(0.93, 0.72, summit / f32(H)).astype(f32)
                ph = (summit + BENCH[j0:j1, i0:i1] + (PM[j0:j1, i0:i1] if PM is not None else f32(0.0))) / bm
                summit = summit - kb * bm / f32(2 * math.pi) * np.sin(f32(2 * math.pi) * ph)
            brow = f32(min(pr['brow_m'], 0.02 * H))
            z = _smin(wallz, summit, brow) if brow > 0 else np.minimum(wallz, summit)
            d_out_edge = d_in
            own = d_in > 0                      # the tower's own wall or summit is its surface here (tower_id)
            if body_on and plan.body_h[t] > 0:
                # the massif body: the tower's own wall table at its wider footprint (same lobes, spurs and scarps),
                # meeting a rough skirt that rises inward from the wall's brow until the peak's cone stands above it
                Hb, Rb = float(plan.body_h[t]), float(plan.body_R[t])
                d_b = f32(Rb) - (re / stretch - LOB[j0:j1, i0:i1])
                if flo is not None:
                    d_b = d_b - flo
                wb = np.interp(d_b, plan.wall_D[t], plan.wall_Z[t]).astype(f32)
                wb0 = np.interp(d_b, plan.wall_D0[t], plan.wall_Z[t]).astype(f32)
                wb = wb0 + (wb - wb0) * lg
                wb = np.where(d_b < 0, d_b * tan_under, wb)
                top_b = (f32(Hb) + np.maximum(d_b, f32(0.0)) * f32(plan.body_tan[t])
                         + rough_box(j0, j1, i0, i1, Hb))
                zb = _smin(wb, top_b, brow) if brow > 0 else np.minimum(wb, top_b)
                # (the body's wall is the tower's too: the cliff the massif meets the plain and the cockpits with)
                own = (own & (z >= zb)) | ((d_b > 0) & (wb < top_b - brow) & (zb > z))
                z = np.maximum(z, zb)
                d_out_edge = np.maximum(d_in, d_b)
            base = PM[j0:j1, i0:i1] if PM is not None else f32(0.0)
            z = z + base
            blk = rock[j0:j1, i0:i1]
            win = z > blk
            rock[j0:j1, i0:i1] = np.where(win, z, blk)
            owner[j0:j1, i0:i1] = np.where(win & own, t, owner[j0:j1, i0:i1])
            # a talus cone at the foot under some of the tower's azimuths (its gullies' rockfall), 33 degrees (a few
            # metres high: sub-cell on the horizon levels, which skip it)
            if plan.B[t] > 0.05 and plan.B[t] > 0.5 * cell:
                theta = np.arctan2(dy, dx)
                per = 7
                g = (theta + f32(math.pi)) / f32(2 * math.pi) * per
                az = _noise1_periodic(g.astype(np.float64), per, plan.salt + 401 + 7 * t)
                c = f32(1.0 - 2.0 * pr['apron_cover'])
                gate = _smoothstep(0.55 * c, 0.55 * c + 0.35, az).astype(f32)
                Bt = f32(plan.B[t]) * gate
                d_out = np.maximum(-d_out_edge, f32(0.0))          # at the body's foot where it has one
                cone = Bt - d_out * tan_apron
                cone = np.where(d_out <= f32(plan.reach[t]), cone, NEG) + base
                sb = scree[j0:j1, i0:i1]
                scree[j0:j1, i0:i1] = np.where(cone > sb, cone, sb)

    # the clusters' common base (fengcong): flat at plinth_m inside a cluster, under the peaks; it shows only between
    # them, as the cockpits' floors
    if PM is not None:
        rock = np.maximum(rock, np.where(PM > 0.5, PM, NEG).astype(f32))

    level = plain['level']
    rock_h = level + rock
    talus_ss = np.maximum(level + scree - np.maximum(rock_h, plain['surface']), 0.0) * (scree > 0)
    h_ss = np.maximum(plain['surface'], rock_h) + talus_ss
    bed_ss = np.minimum(h_ss, np.maximum(rock_h, level - pr['alluvium_m']))

    h = G.down(h_ss).astype(np.float64)
    bed = G.down(bed_ss).astype(np.float32)
    # the cockpits: where towers meet around a gap, the gap is a closed depression (star-shaped, its arms the slots
    # between the walls). Soil fills its bottom flat, cockpit_fill of its depth (bottom to spill): the farmed floors
    # of Guilin's cockpits. Inside the clusters only, never in the river; the bed stays the rock (the soil is deposit).
    if pr['cockpit_fill'] > 0 and plan.count and fill:
        # (any closed basin outside the river: a hole of plain enclosed by a cluster is a polje, flat-floored too).
        # Inside the main tile every level reads the plan's one floor map, so a basin is filled alike on every level
        # (found per window, a polje closed in one window drained out through a smaller one's edge: steps of 20-30 m
        # between the levels); outside it a context level finds its own
        fx0, fy0, fcell, fmap = _floor_map(plan)
        xc = G.x0 + (np.arange(G.n) + 0.5) * cell
        yc = G.y0 + (np.arange(G.n) + 0.5) * cell
        fi = np.floor((xc - fx0) / fcell).astype(np.int64)
        fj = np.floor((yc - fy0) / fcell).astype(np.int64)
        nf = fmap.shape[0]
        inx = (fi >= 0) & (fi < nf)
        iny = (fj >= 0) & (fj < nf)
        floor = fmap[np.clip(fj, 0, nf - 1)][:, np.clip(fi, 0, nf - 1)]
        inside = iny[:, None] & inx[None, :]
        floor = np.where(inside, floor, -np.inf)
        if not inside.all():
            dry = G.down((plain['surface'] >= level - 0.25).astype(np.float64)) > 0.999
            own = _cockpit_floors(h, cell, pr['cockpit_fill'], dry)
            floor = np.where(inside, floor, own)
        soil = floor > h + 0.05                  # the soil floor is the surface there, not a tower's rock
        h = np.maximum(h, floor)
    else:
        soil = None
    h = h.astype(np.float32)
    # the river's water, per cell on the final surface: wherever there is water, h + water is the one level (the
    # mean of a partly wet cell's subsamples' depths would lift its level above the river's at every waterline)
    ws = G.down(np.broadcast_to(plain['water_level'], h_ss.shape))
    wet = (G.down(plain['in_channel']) > 0.5) & (h < ws)
    water = np.where(wet, ws - h, 0.0).astype(np.float32)
    out = dict(h=h, bed=bed, deposit=np.maximum(h - bed, 0.0).astype(np.float32),
               talus=G.down(talus_ss).astype(np.float32), water=water, river=water,
               plain=G.down(level).astype(np.float32))
    out['Sc'] = np.full((G.n, G.n), math.tan(math.radians(min(pr['sc_deg'], 89.5))), np.float32)
    mid = G.ss // 2
    out['tower_id'] = owner[mid::G.ss, mid::G.ss].copy()
    if soil is not None:
        out['tower_id'][soil] = -1
    return out


FLOOR_MAP_CELL_M = 10.0          # the plan's cockpit floor map: the main tile at this cell (cockpits are 50-150 m;
                                 # at 16 m the smallest went unfilled)
SLOT_CLOSE_M = 40.0              # ... and its basins found again on the map box-averaged to this: closed but for a
                                 # slot narrower than about this between two towers ...
SLOT_MAX_AREA_M2 = 1.2e5         # ... and no larger than this (a cockpit; a polje's alluvium runs on out through its
                                 # slots at the plain's level)


def _floor_map(plan):
    """(x0, y0, cell, floors): the plan's cockpit and polje floors over the main tile, made once (on the main tile at
    FLOOR_MAP_CELL_M, without floors, by _cockpit_floors at that cell) and kept on the plan."""
    if plan.floors is None:
        mx0, my0, ms = plan.main
        n = max(8, int(round(ms / FLOOR_MAP_CELL_M)))
        cell = ms / n
        out = evaluate(plan, mx0, my0, cell, n, ss=1, fill=False)
        h = out['h'].astype(np.float64)
        dry = (out['water'] <= 0.0) & (h >= out['plain'] - 0.25)
        fl = _cockpit_floors(h, cell, plan.params['cockpit_fill'], dry, max_cells=n)
        # and the basins that close at SLOT_CLOSE_M: a hollow between towers that drains only through a slot
        # narrower than that fills with soil and rockfall up to where the slot's floor is (the slot itself too)
        nc = max(8, int(round(ms / SLOT_CLOSE_M)))
        fl = np.maximum(fl, _cockpit_floors(h, cell, plan.params['cockpit_fill'], dry, max_cells=nc,
                                            max_area_m2=SLOT_MAX_AREA_M2))
        plan.floors = (mx0, my0, cell, fl)
    return plan.floors


def _cockpit_floors(h, cell, share, allowed, max_cells=320, max_area_m2=None):
    """The soil floor of every closed depression deeper than 1 m whose bottom lies where `allowed`: a flat level at
    its bottom + share x (spill - bottom), -inf elsewhere (apply as max(h, floor)). The depressions are found on h
    box-averaged to at most max_cells (core.metrics' fill: the moved Ekigar priority-flood), and each one's floor
    level is spread over its footprint, one coarse cell wider; the fine surface's own contours then outline the
    floor, so the coarse grid never shows, and a floor never reaches a col (it stays below its spill)."""
    from ..core import metrics as M
    n = h.shape[0]
    f = max(1, int(math.ceil(n / max_cells)))
    m = n // f
    if m < 8:
        return np.full_like(h, -np.inf)
    hc = h[:m * f, :m * f].reshape(m, f, m, f).mean(axis=(1, 3))
    filled, _ = M.fill_depressions(hc)
    depth = filled - hc
    lab, k = M.label(depth > 1e-6)
    if k == 0:
        return np.full_like(h, -np.inf)
    flat = lab.ravel()
    bottom = np.full(k + 1, np.inf)
    np.minimum.at(bottom, flat, hc.ravel())
    spill = np.full(k + 1, -np.inf)
    np.maximum.at(spill, flat, filled.ravel())
    al = allowed[:m * f, :m * f].reshape(m, f, m, f).all(axis=(1, 3))
    at_bottom = np.zeros(k + 1, bool)
    is_bottom = (hc <= bottom[lab]) & (lab > 0)
    at_bottom[np.unique(lab[is_bottom & al])] = True
    keep = (spill - bottom > 1.0) & at_bottom
    keep[0] = False
    # a basin's soil: share of its depth, and a small one (2 ha and under, a pit between tower feet or a hollow of
    # the clusters' base) nearly to its spill, easing to `share` at 20 ha (a pit left 30 % deep reads as a round
    # bowl, not a soil floor)
    area = np.bincount(flat, minlength=k + 1) * (cell * f) ** 2
    sh = share + (0.97 - share) * np.clip((2e5 - area) / 1.8e5, 0.0, 1.0)
    # and a narrow one (a slot between two towers' bodies, under 60 m across: its width twice its area over its
    # rim's length) to its spill, easing to `share` at 150 m: rockfall and soil fill a slot to its outlet, the col
    # between the two (left 3-15 % deep, a slot read as a pit, and the 30 m radar reference as a bowl)
    inner = lab > 0
    lab_o = np.where(inner, lab, -1)
    rim = inner & ~((_rolling_min_1(lab_o) == lab) & (_rolling_max_1(lab_o) == lab))
    n_rim = np.bincount(flat[rim.ravel()], minlength=k + 1)
    width = 2.0 * area / np.maximum(n_rim * (cell * f), 1e-6)
    sh = np.maximum(sh, share + (1.0 - share) * np.clip((150.0 - width) / 90.0, 0.0, 1.0))
    if max_area_m2 is not None:
        keep = keep & (area <= max_area_m2)
    level = np.where(keep, bottom + np.maximum(sh, share) * (spill - bottom), -np.inf)
    fl = level[lab]
    fl = np.maximum(fl, _rolling_max_1(fl))                          # one coarse cell wider
    out = np.repeat(np.repeat(fl, f, 0), f, 1)
    if out.shape[0] < n:
        out = np.pad(out, ((0, n - out.shape[0]), (0, n - out.shape[1])), mode='edge')
    return out


def _rolling_min_1(a):
    """The minimum over each cell's 3 x 3 neighbourhood (edges clamped)."""
    p = np.pad(a, 1, mode='edge')
    out = a.copy()
    for dj in (0, 1, 2):
        for di in (0, 1, 2):
            np.minimum(out, p[dj:dj + a.shape[0], di:di + a.shape[1]], out=out)
    return out


def _rolling_max_1(a):
    """The maximum over each cell's 3 x 3 neighbourhood (edges clamped)."""
    p = np.pad(a, 1, mode='edge')
    out = a.copy()
    for dj in (0, 1, 2):
        for di in (0, 1, 2):
            np.maximum(out, p[dj:dj + a.shape[0], di:di + a.shape[1]], out=out)
    return out


def _plain(plan, G):
    """The alluvial plain and its river on a level's subsample grid: level (the plain without the channel), surface
    (with the channel cut in), water_level (the river's flat surface) and in_channel (1 inside the wetted channel).
    The channel: n = the signed distance over the half-width (+ left of the flow), the bend's sharpness from the
    curvature (1 at a radius of curvature of 2 half-widths... 4 or less), its inner side q = n sign(curvature). The
    bed is deepest on a line swung toward the outer bank by the bend; the point bar on the inner side rises to bar_m
    above the water at its bank, then a gentle gravel slope (4 degrees) up to the plain; the outer bank is a cut
    bank (about 30 degrees); a straight reach has two moderate banks."""
    pr = plan.params
    fx, fy = plan.river_dir
    x0, y0, side = plan.domain
    cx, cy = x0 + side / 2, y0 + side / 2
    lim = 2.5 * G.cell
    xs, ys = G.xs, G.ys
    along = ((xs[None, :] - cx) * fx + (ys[:, None] - cy) * fy)          # metres along the river's direction
    tilt = -pr['plain_tilt_m_per_km'] * along / 1000.0
    micro = G.smooth(lambda X, Y: pr['plain_micro_m'] * fbm2(X, Y, 160.0, 3, plan.salt + 401, 0.45, lim) / 0.3,
                     max(40.0, lim))
    level = tilt + micro
    if plan.river is None:
        return dict(level=level, surface=level, water_level=np.full_like(level, -1e9), in_channel=np.zeros_like(level))
    hw_max = float(np.max(plan.river_hw))
    bank_h = pr['river_bank_m']
    band = hw_max + 6.0 * bank_h + 60.0
    d, s, d_far = _river_frame_level(plan, G, band)
    level = level + pr['plain_rise_m'] * _smoothstep(hw_max + 3.0 * bank_h, 1500.0, d_far)
    ws = plan.water_level + tilt
    hw = np.interp(s, plan.river_s, plan.river_hw)
    kap = np.interp(s, plan.river_s, plan.river_kappa)
    ad = np.abs(d)
    near = ad < band
    nrm = d / hw
    bend = np.clip(np.abs(kap) * hw / 0.25, 0.0, 1.0) * near
    sgk = np.where(kap >= 0.0, 1.0, -1.0)
    q = nrm * sgk                                                       # +1 at the inner bank
    # the bed: deepest on a line swung 0.45 x bend toward the outer bank
    nt = -0.45 * bend * sgk
    xr = np.where(nrm >= nt, (nrm - nt) / np.maximum(1.0 - nt, 1e-3), (nrm - nt) / np.maximum(1.0 + nt, 1e-3))
    depth = pr['river_depth_m'] * (1.0 + 0.3 * bend) * np.clip(1.0 - xr * xr, 0.0, 1.0)
    bed = ws - depth
    # the point bar: the inner side's bed raised toward a gravel top bar_m above the water at the inner bank (only
    # the inner side, and by the bend's sharpness: a straight reach keeps its full section)
    lift = _smoothstep(0.15, 1.0, q) * bend
    bed = bed + (ws + pr['bar_m'] * _smoothstep(0.55, 1.0, q) - bed) * lift
    # the banks: a cut bank on the outer side (30 degrees), on the inner side the bar's gravel rising at 4 degrees
    out_m = np.maximum(ad - hw, 0.0)
    rise = np.maximum(level - ws, 0.05)
    cut = ws + rise * _smoothstep(0.0, np.maximum(rise / math.tan(math.radians(30.0)), 2.0 * G.cell), out_m)
    soft = ws + rise * _smoothstep(0.0, np.maximum(2.5 * rise, 2.0 * G.cell), out_m)
    gravel = np.minimum(level, ws + pr['bar_m'] * bend + out_m * math.tan(math.radians(4.0)))
    inner = _smoothstep(0.0, 0.3, q)
    bankz = soft + (cut - soft) * bend * (1.0 - inner) + (gravel - soft) * bend * inner
    channel = ad < hw
    surface = np.where(channel, bed, np.minimum(level, bankz))
    surface = np.where(near, surface, level)
    return dict(level=level, surface=surface, water_level=ws, in_channel=(ad < hw * 1.08).astype(np.float64))


# ---------------------------------------------------------------- the stage op
_PLANS = {}


def _plan_key(seed, domain, params, via, main=None):
    def freeze(v):
        return tuple(freeze(x) for x in v) if isinstance(v, (list, tuple)) else v

    def window(w):
        return None if w is None else tuple(round(float(v), 3) for v in w)
    full = params_for(params)
    return (int(seed), tuple(round(float(v), 6) for v in domain), tuple(sorted((k, freeze(v)) for k, v in full.items())),
            window(via), window(main))


def cached_plan(seed, domain, params=None, via=None, main=None):
    """plan_karst, cached per process: every level of one terrain shares one plan."""
    key = _plan_key(seed, domain, params, via, main)
    if key not in _PLANS:
        if len(_PLANS) >= 8:
            _PLANS.clear()
        _PLANS[key] = plan_karst(seed, domain, params, via, main)
    return _PLANS[key]


_DOMAINS = {}


def op_karst(fields, level, params, seed=0):
    """Stage op 'karst' (the wave-1 convention op(fields, level, params, seed)): writes h, bed, deposit, talus,
    water (the river) and Sc of one level from the world-space plan, in place.

    level: a core.levels.Level (or anything with x0, y0, cell, n, parent (None on the coarsest level) and depth (the
    context levels' count of doublings above the main tile)). params: the karst parameters (DEFAULTS; an unknown one
    raises naming the known ones), plus optionally domain=(x0, y0, side), the plan's extent, via=(x, y), a point the
    river passes near, and main=(x0, y0, side), the main tile (the window cluster_cover is the share of).

    The plan covers the outermost window, so every level sees the same towers: by default the domain is the window
    of the coarsest level the op runs on (parent None: levels run coarsest first), via its centre and main its
    central window of side / 2^depth: the main tile (the context levels are centred on it). So run it on 'all'
    levels: the fields are rebuilt from world functions at each level's cells (the walls are never upsampled), and
    the runner's border band pins a child to its parent."""
    def get(k, default=None):
        if isinstance(level, dict):
            return level.get(k, default)
        return getattr(level, k, default)
    x0, y0, cell, n = float(get('x0')), float(get('y0')), float(get('cell')), int(get('n'))
    p = dict(params)
    domain, via, main = p.pop('domain', None), p.pop('via', None), p.pop('main', None)
    key = (int(seed), _plan_key(seed, (0.0, 0.0, 1.0), p, None)[2])
    if domain is None:
        if get('parent') is None or key not in _DOMAINS:
            side = n * cell
            ms = side / 2.0 ** max(int(get('depth', 0) or 0), 0)
            cx, cy = x0 + 0.5 * side, y0 + 0.5 * side
            _DOMAINS[key] = ((x0, y0, side), (cx, cy), (cx - 0.5 * ms, cy - 0.5 * ms, ms))
        domain, via0, main0 = _DOMAINS[key]
        via = via0 if via is None else via
        main = main0 if main is None else main
    plan = cached_plan(seed, domain, p, via, main)
    out = evaluate(plan, x0, y0, cell, n)
    # the level is rebuilt, so its own alluvium, cockpit soil, talus and river replace what it inherited (a parent's
    # coarse alluvium would otherwise bleed onto rock this level resolves)
    for k in ('h', 'bed', 'deposit', 'talus', 'water', 'Sc'):
        fields[k] = out[k]
    return fields


OPS = {'karst': op_karst}
