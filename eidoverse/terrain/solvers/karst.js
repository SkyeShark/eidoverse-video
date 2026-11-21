// Port of blender/eidoblend/terrain/solvers/karst.py at f90c6fc.
//
// Karst towers: fenglin (towers and peak massifs on a river plain, Guilin) and fengcong (peaks packed on a common
// base over closed, flat-floored cockpits). Design section 4.10.
//
// Every input is a function of world position in metres. One global plan, built once on the CPU over the outermost
// level's window, holds the tower centres, each tower's shape numbers and the river course. Every level evaluates that
// plan at its own cells, so:
//   - the walls stay sharp on a 0.5 m hero level (they are never upsampled from a coarser level);
//   - a 31 m horizon level shows the same massifs, anti-aliased by 2 x 2 supersampling;
//   - a child level matches its parent where they overlap, up to the octaves only the child resolves.
//
// Frames and units (design 2.1): metres and degrees; arrays [row j, column i] with row 0 the south edge; a cell
// centre is at x = x0 + (i + 0.5) cell, y = y0 + (j + 0.5) cell.
//
//     const plan = planKarst(7, [-16000, -16000, 32000], { kind: 'fenglin' }, [0, 0], [-4000, -4000, 8000]);
//     const out = await evaluate(R, plan, -4000, -4000, 7.8125, 1024);
//     out.h, out.bed, out.deposit, out.talus, out.water, out.Sc        // GPU fields (n, n), float32
//
// What Guilin's towers are, from the Li River photographs (the 30 m radar reference rounds them): steep peaks and
// towers rise abruptly from a flat alluvial plain, their bases cliffed (76-88 degrees, the limestone's bedding
// breaking them with ledges), their summits pointed, ridged or knobby, never smooth domes; sizes vary from slim
// spires to massifs 400 m across; inside a cluster they stand close, joined at saddles, in rows along the joints.
// Each tower here is the intersection of two surfaces:
//   - its WALL, rising from the footprint's edge: a table of bands up the height (wallTable: a foot notch at 89
//     degrees, then wall bands at the tower's wall angle, 76-88, between ledges of 0.6-1.8 m at 40-60 degrees every
//     10-30 m, the ledges holding along 55 % of the wall and breaking off elsewhere), read at the distance inside the
//     footprint (the footprint: elongated along the joint strike, leaning, spurred and lobed by world noise; on levels
//     with cells of 2 m or less, fluted: grooves straight down the wall, and on up the peaks' flanks);
//   - its SUMMIT: the highest of its peak cones, each z = h (1 - x + b x (1 - x)), x the (elongated) distance from the
//     peak over h / tan(angle), b the convexity: a spire's cone straight to steepening (b 0-0.3), a peak's from
//     easing toward its foot (b to -0.2: a steep pointed top whose flanks run on to the saddles) to steepening (a
//     sugarloaf, to 0.3); the distance scaled by the cone's ribs (ribHarmonics: azimuthal harmonics 2-7, so ribs and
//     gullies radiate from the apex without ever folding the cone) and bent by a gentle 90 m world-noise jitter, the
//     upper flanks lumpy and knobbed (peak_rough: the caps' roughness); on a block, over its cap: a rough cone from its
//     cliff top (the rim, 30-52 % of its height) to 92 % at the centre, lumpy, with knobs over half of it.
//   z = smooth-min(wall, summit) over brow_m: the wall stands until it meets the summit, then the summit rises.
// The kinds of tower: a spire (one cone at 70-80 degrees, its footprint 70-92 % of the cone's foot: a short cliff
// under a needle); a peak (one cone at 58-70 degrees, or two or three strung along a ridge; on the plain its footprint
// 35-65 % of the cone's foot, a cliff 35-65 % of its height; inside a cluster 60-85 %, its flanks running on to meet
// its neighbours'); a block (a cliffed cap carrying two to four peaks: 8-10 % of the towers, and most of the towers
// taller than 1.4-2.4 times the median: the massive towers of the river's bends). One or two collapse scarps pull a
// sector of a tower's footprint in (scarpSectors), so the wall stands high there under a concave sheer face; the
// summit cones carry bedding benches (ledges and risers) on the levels that resolve them.
// The plan: a cluster field (broad noise mixed with ridged noise, stretched along the joint strike): the peak clusters,
// the rest plain; its threshold makes cluster_cover the main tile's share in clusters. Centres by variable-radius
// Poisson-disc (poissonDisc): spacing_m apart inside the clusters, plain_spacing times that on the plain, the plain's
// then thinned to plain_density (isolated towers). Heights lognormal around median_height_m, times a world-space trend
// so neighbours are alike. The towers inside a cluster are drawn out along the strike (their peaks string into rows).
// The ground between a cluster's inner towers is raised: a base (base_m, undulating by base_rough_m at 300 m and
// 120 m) that is nothing at a cluster's edge and toward the river, so the outer towers rise straight from the plain;
// every tower rises from the base under each of its cells. Deep inside a cluster a peak is the fengcong cone: broad
// (its foot cluster_reach of the median distance to its three nearest neighbours, 48-62 degrees on average) and
// concave (cluster_convexity: 60-70 degrees at the top easing to 30-40 at the foot), so neighbours' flanks meet at cols
// about half their height up; a cluster's edge towers keep the steep cliffed peaks of the plain, so the massif meets
// the plain with sheer faces. Each cluster tower also stands on a massif BODY: the same wall table at a wider
// footprint (body_reach), its brow body x the tower's height up, a rough skirt rising inward from it at body_deg (to
// at most body_top of the height); neighbours' bodies join into ridges with cols, leave cockpits where three or more
// meet, and two that would stand a slot apart (body_gap_m) are drawn on until they meet. So a cluster is a massif with
// its peaks on it, walled where it meets the plain (Guilin's clusters at 30 m: 44 % of the tile 50 m and more over
// the plain).
// Composition: every tower by max over the plain, a talus cone at the foot under some of its azimuths (apron); the
// plain is flat alluvium that rises gently away from a river winding through it (a least-cost course around the
// clusters, with meanders). The river is a broad water surface at plain level: a flat water level river_bank_m under
// the plain, a channel river_width_m wide (+- river_width_var along its course) and river_depth_m deep, its deepest
// line swung toward the outer bank of each bend, a cut bank there and a gravel point bar on the inner bank standing
// bar_m above the water at the sharpest bends. Where towers ring a gap, the gap is a closed depression (a cockpit, or
// a polje where a cluster encloses a patch of plain) and soil fills its bottom flat (cockpit_fill of its depth, a
// small pit nearly to its spill), found once per plan on the main tile so every level fills it alike: the one family
// where closed depressions are correct. fengcong raises the clusters on a common plinth (plinth_m).
//
// The stage op `karst` (opKarst) writes h, bed (the rock: towers, and the buried rock under the alluvium and the
// cockpit soil), deposit (h - bed), talus (the talus cones), water (the river's depth: flat at one level, so the lake
// builder draws it as the water surface it is) and Sc (the wall's own angle, 87.5 degrees: the recipe's threshold pass
// only trims texel spikes) on a level.
//
// Where this differs from karst.py, and why (PORT_PLAN.md 2.4, 3.2):
//   - The plan stays JavaScript on the CPU, in doubles, as numpy computes it: the cluster field's threshold over its
//     192^2 grid (numpy 2.3.4's quantile, float64), the Poisson disc, the peaks, ribs, scarps, bodies and wall tables,
//     the k-nearest towers, the river's 160^2 least-cost course (a binary heap ordered as Python's heapq orders its
//     (cost, j, i) tuples), its Chaikin smoothing, resampling and curvature. Draws come from core/np_random.js
//     (numpy's Generator, draw for draw). Plan floats agree with numpy's to the last ulps V8's Math and the C library
//     differ by (plan 2.3); np.std and np.sum are numpy's pairwise sums (pairwiseSum), np.interp is numpy's
//     (npInterp), np.convolve's dot products are summed in order (OpenBLAS's ddot sums in another order: the last
//     ulps of the river's curvature).
//   - evaluate runs on the GPU (kernels/karst/): the level's smooth world fields on their world-anchored lattices
//     (karst/world.wgsl) and bilinear onto the subsamples (karst/bilinear.wgsl); the river's frame (karst/river.wgsl:
//     the distance to the course and the signed distance and arc length near it, the course's segments binned per
//     tile); the plain and its channel (karst/plain.wgsl); every tower over the subsamples its box covers
//     (karst/towers.wgsl: the plan's towers in tables, binned per 16 x 16 tile in the order numpy visits them, so a
//     subsample takes the same winner and owner); the composition and the cell means (karst/compose.wgsl); the
//     cockpit floors (karst/cockpit_*.wgsl over core/prims.js fillDepressions and label: per-basin numbers by integer
//     atomics, each basin's level in doubles on the CPU from them (one number per basin, not per cell), then gathered).
//     numpy's float64 there is float32 here, but in the tower loop. Noise lattice coordinates are split on the CPU in
//     doubles into an integer cell and a float32 fraction per lattice line (the world functions are evaluated on
//     separable grids: G.smooth's lattices and the subsample rows), so a lattice 40 km from the origin is as exact as
//     one at the origin.
//   - The tower loop (karst/towers.wgsl) rounds as numpy does (karst/precise.wgsl): its float32 lines one rounding per
//     operation, division, sqrt and arctan2 correctly rounded, its float64 lines (np.interp of the wall tables, the
//     fluting's and the talus gate's noise, the smoothsteps) in double-float, rounded once. The loop amplifies its
//     last bit (a wall table rises up to 57 m per metre at a foot's notch, the buried rock dips at tan 85 degrees,
//     the talus gate turns 140 m of cone per radian), so numpy's own float32 lands up to 7e-5 of the bed's range from
//     the same lines in float64; a port that rounded its own way landed as far (tests/karst_coast/evaluate_test.mjs,
//     karst_window_floor.py). Where the source decides on a threshold its float64 noise sits on (the common base's
//     rock where PM > 0.5 m, a step of the bed by the alluvium's 12 m), the float32 noise can fall the other side on a
//     subsample in a million.
//   - Blender's memos (_PLANS, _DOMAINS) are module Maps here, cleared by clearMemos() (the floor protocol's
//     memos-cleared rule, plan 5.4).
// The convergence loops this module names for the dispatch-log comparison (PORT_PLAN.md 5.7): none; it dispatches no
// Blender kernel (fillDepressions' and label's relaxations are core/prims.js's own, set aside by the comparison).

import * as Cm from '../core/compose.js';
import * as Gd from '../core/grid.js';
import { ValueError, closeMatches, pyFormat, pyRound } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { keyToFloat, prims } from '../core/prims.js';

const DEG = Math.PI / 180.0;                    // math.radians / np.radians: x * (pi / 180)
const radians = (d) => d * DEG;
const degrees = (r) => r * (180.0 / Math.PI);
const TWO_PI = 2 * Math.PI;

// ---------------------------------------------------------------- parameters (metres, degrees)
export const DEFAULTS = Object.freeze({
    kind: 'fenglin',              // 'fenglin' (towers on a river plain) | 'fengcong' (peaks over dolines)
    spacing_m: 210.0,             // Poisson-disc spacing of the towers inside the clusters (about their neighbour gap)
    median_height_m: 150.0,       // median summit height above the plain
    height_sigma: 0.38,           // lognormal spread of the heights (natural log)
    height_trend: 0.30,           // world-space height trend (2 km scale, natural-log amplitude): neighbours alike
    wall_deg: 82.0,               // the walls' angle (median; per tower +- wall_spread_deg, held to 70-89)
    wall_spread_deg: 4.0,
    ledge_every_m: [10.0, 30.0],  // the walls' ledges (bedding benches): one every this many metres of height ...
    ledge_deg: [40.0, 60.0],      // ... at this angle ...
    ledge_m: [0.6, 1.8],          // ... this tall (so 0.4-1.5 m wide) ...
    ledge_cover: 0.55,            // ... along this share of the wall (world noise at 30 m: ledges break off and resume)
    notch_m: [2.0, 6.0],          // the foot notch's height (89 degrees: the undercut's stand-in)
    slim_share: [0.35, 0.20],     // the share of slim spires among the towers (on the plain, inside the clusters)
    block_share: [0.08, 0.10],    // the share of blocks and massifs (a cliffed cap with knobs) among them
    spire_deg: [70.0, 80.0],      // a spire's cone angle (its mean slope, apex to foot)
    spire_girth: [0.70, 0.92],    // a spire's footprint, a share of its cone's foot radius (a short steep wall below)
    peak_deg: [58.0, 70.0],       // a peak's cone angle (on the plain)
    peak_girth: [0.55, 0.85],     // a peak's footprint on the plain, a share of its cone's foot radius: a wall
                                  // 15-45 % of its height (the photographs' cliffed towers, 0.7-1.3 x as wide as
                                  // tall at the foot; at 0.35-0.65 they stood as needles, 2 x taller than wide)
    cluster_girth: [0.60, 0.85],  // ... at a cluster's edge: the wall facing the plain
    cluster_reach: [0.75, 0.95],  // a cluster peak's cone reaches this share of the median distance to its 3 nearest
                                  // neighbours: the cones meet at saddles, so a cluster is one massif with its peaks
                                  // on it (Guilin's peak clusters at 30 m: 23 % of the ground 100-200 m up; separate
                                  // towers on a low base held 8 %, the clusters a plain strewn with pebbles)
    cluster_peak_deg: [48.0, 62.0],   // ... its cone angle follows from its height over that reach, held to this, ...
    cluster_convexity: [-0.55, -0.15],    // ... and its profile concave: the fengcong cone, steep at the top (60-70
                                          // degrees) easing to 30-40 at its foot where it meets its neighbours at
                                          // cols. (Narrow 58-70 degree cones over the massif bodies stood as candles
                                          // on cakes)
    inner_girth: [1.0, 1.08],     // deep inside a cluster the footprint takes the whole cone (no wall: its flanks run
                                  // down into the saddles and cockpits), but for its collapse scarps
    edge_scarp: [0.45, 0.65],     // a cluster's edge tower turns a collapse scarp of this depth toward the plain: the
                                  // massif meets the plain with sheer faces
    body: [0.12, 0.25],           // a cluster tower's massif body: its wall at the body's edge this share of the
                                  // tower's height (at 0.25-0.45 under a gentle top they stood as cakes), ...
    body_reach: [0.50, 0.70],     // ... its footprint this share of the median distance to its 3 nearest neighbours
                                  // (neighbours' bodies join along the rows into ridges with cols between them and
                                  // leave star-shaped cockpits where three or more meet), ...
    body_deg: [12.0, 22.0],       // ... its top a skirt rising inward at this angle from the wall's brow until the
                                  // peak's steeper cone takes over: the broad lower flanks of a peak cluster
    body_gap_m: 45.0,             // two neighbours' bodies closer than this are drawn on until they meet (no slots)
    body_top: 0.6,                // the skirt reaches at most this share of the tower's height at its centre
    block_girth: [0.70, 1.10],    // a block's footprint radius over its height (on the plain)
    massif_reach: [0.46, 0.64],   // a massif's footprint radius over the median distance to its 3 nearest neighbours
                                  // (in the clusters: neighbours overlap into massifs, the gaps left are cockpits)
    peak_convexity: [-0.2, 0.3],  // b of z = h (1 - x + b x (1 - x)): below 0 a peak's flanks ease toward its foot
                                  // (steep pointed tops, flanks running into the saddles), above 0 they steepen (a
                                  // sugarloaf); their straight sides broken by the knobs (peak_rough) and the
                                  // bedding benches. (Mostly convex, -0.1..0.4, rounded the tops: the upper sixth of
                                  // the towers stood at 45 degrees, the review's domes)
    spire_convexity: [0.0, 0.3],  // a spire's: straight to steepening (a needle, never a flared foot)
    peak_spacing_m: 70.0,         // the least spacing of a tower's own peaks
    peaks_max: 4,
    floor: [0.30, 0.52],          // a block's cliff top (its cap's rim), a share of its height
    cap_top: 0.92,                // its cap rises from the rim to this share of the height at the centre (a rough cone)
    floor_rough: 0.035,           // the caps' lumps, a share of the height (45 m world noise)
    crown: 0.06,                  // knobs on the caps, in patches: their height, a share of the tower's ...
    crown_spacing_m: 60.0,        // ... and spacing (pointed knobs on a jittered world lattice)
    crown_cover: 0.5,             // ... over this share of a cap
    scarps: [0.25, 0.5, 0.25],    // the chances of 0, 1 and 2 collapse scarps on a tower: on each, a sector of the
    scarp_deg: [25.0, 60.0],      // footprint (this half-width) is pulled in by ...
    scarp_depth: [0.35, 0.6],     // ... this share of its radius, so the wall rises high there: a concave sheer face
    ribs: 0.45,                   // the summit cones' ribs and gullies: azimuthal harmonics 2-7 of each cone's distance
                                  // from its apex, sum of m |a_m| (under 1 the distance never folds: ribs radiate from
                                  // the apex and the flanks stand between 0.7 and 1.4 of the cone's slope)
    jag: 0.05,                    // a gentle world-noise jitter of that distance (relative std, 90 m and 40 m): the
                                  // ribs bend and the feet bulge; 0.2 at 45-6 m folded the cones into blade fences
    brow_m: 2.0,                  // the rounding where a wall meets the summit, metres (at most 2 % of the height)
    peak_rough: 0.6,              // the summits' lumps and knobs (the caps' roughness, this share of it) over a peak's
                                  // upper flanks: jagged, knobbed tops (smooth cones read as geometric pyramids)
    apron: 0.05,                  // a talus cone's height at the foot, a share of the tower's height ...
    apron_cover: 0.35,            // ... under this share of the foot's azimuths
    apron_deg: 33.0,              // its slope
    elongation: 0.35,             // max footprint elongation along the strike, on the plain
    cluster_elong: [0.10, 0.55],  // the elongation inside the clusters (their peaks string into rows along the strike)
    ridge_share: 0.12,            // the share of towers drawn out into ridges (elongation 0.6-1.1, 2-3 peaks)
    benches: 0.6,                 // the summit cones' bedding benches: z - k B / 2 pi sin(2 pi z / B) (k this; under 1
    bench_m: 13.0,                // it never folds): ledges at (1 - k) and risers at (1 + k) of the cone's slope, every
                                  // B metres of height (undulating +-3 m over 160 m), fading out over the top quarter
    tall_massif: 0.85,            // towers from 1.4 to 2.4 x the median height become massifs: up to this share of
                                  // the peaks turn blocks, and of the rest ridges (no single 400 m cone)
    lean: 0.20,                   // max footprint offset (one wall higher than the other)
    spurs: 0.10,                  // radial spurs: the largest amplitude of azimuthal harmonics 2-5 of the footprint
    lobes_m: 6.0,                 // footprint lobing: radial displacement by world noise (130 m and 60 m), std metres
    plinth_m: 0.0,                // the clusters' common base (fengcong 50-150): the cockpit floors between the peaks
    base_m: 45.0,                 // fenglin: the ground between the inner towers of a cluster, rising from its edge
                                  // (the towers' bodies cover most of it: it shows as the cockpits' floors; at 50 m
                                  // under thin towers with no bodies it showed as a lumpy plateau between them)
    base_rough_m: 6.0,            // the base's undulation (std, metres at 300 m and 120 m): rises, saddles, hollows
    cockpit_fill: 0.85,           // soil filling each cockpit (closed depression between towers) flat: share of its
                                  // depth (a small pit, 1 ha, nearly to its spill: its soil floor, not a round bowl)
    cluster_cover: 0.80,          // fraction of the main tile inside peak clusters (the rest is plain)
    cluster_scale_m: 2600.0,      // wavelength of the cluster / plain pattern
    cluster_ridges: 0.65,         // share of ridged noise in it: massifs as elongated ridges with peaks along them
    ridge_scale_m: 1500.0,        // the ridges' wavelength (about twice their spacing)
    cluster_stretch: 2.2,         // the pattern's elongation along the joint strike
    strike_deg: 115.0,            // joint strike, compass degrees: clusters, towers and plains elongate along it
    plain_density: 0.30,          // share of the plain's blue-noise points kept as isolated towers
    plain_spacing: 1.6,           // their Poisson radius, a multiple of the clusters' radius
    river: true,                  // a river winding through the plain
    river_width_m: 130.0,         // the channel's mean width (the Li River at Yangshuo: 100-200 m)
    river_width_var: 0.25,        // its relative change along the course (1.8 km world noise)
    river_depth_m: 3.5,           // the deepest water
    river_bank_m: 2.2,            // the plain's height above the water at the bank
    river_meander: 2.4,           // meander amplitude, a multiple of the width
    river_azimuth_deg: null,      // flow direction, compass degrees (null: from the seed)
    bar_m: 0.8,                   // a point bar's top above the water on the inner bank of a sharp bend
    plain_tilt_m_per_km: 0.0,     // the plain's fall along the river (0: the water is one flat surface everywhere)
    plain_rise_m: 4.0,            // the plain rises this much away from the river, over 1.5 km
    plain_micro_m: 0.3,           // alluvial micro-relief (std)
    alluvium_m: 12.0,             // alluvium over the buried rock of the plain
    fluting_m: 0.9,               // vertical fluting depth on the walls (levels with cells <= 2 m)
    sc_deg: 87.5,                 // the threshold slope written to Sc: the recipe's pass trims only texel spikes
});

export const KIND_PRESETS = Object.freeze({
    fenglin: {},
    fengcong: { spacing_m: 210.0, median_height_m: 190.0, height_sigma: 0.28, height_trend: 0.2,
        slim_share: [0.3, 0.3], block_share: [0.1, 0.1], peak_girth: [0.75, 0.95], plinth_m: 60.0,
        base_m: 0.0, base_rough_m: 10.0,
        cluster_cover: 0.97, cluster_ridges: 0.3, cluster_elong: [0.0, 0.5], plain_density: 0.0,
        elongation: 0.25, ridge_share: 0.1, lean: 0.10, river: false },
});

const PAIRS = ['ledge_every_m', 'ledge_deg', 'ledge_m', 'notch_m', 'slim_share', 'block_share', 'spire_deg',
    'spire_girth', 'peak_deg', 'peak_girth', 'cluster_girth', 'cluster_reach', 'cluster_peak_deg',
    'inner_girth', 'edge_scarp', 'block_girth', 'massif_reach', 'peak_convexity', 'spire_convexity', 'floor',
    'body', 'body_reach', 'body_deg', 'cluster_convexity',
    'cluster_elong', 'scarp_deg', 'scarp_depth'];

/** The full parameter dict: DEFAULTS, then the kind's preset, then the caller's values (params_for). */
export function paramsFor(params = null) {
    params = { ...(params ?? {}) };
    const kind = params.kind ?? DEFAULTS.kind;
    if (!(kind in KIND_PRESETS)) {
        throw new ValueError(`karst kind '${kind}': use one of ${JSON.stringify(Object.keys(KIND_PRESETS).sort())}`);
    }
    const unknown = Object.keys(params).filter((k) => !(k in DEFAULTS)).sort();
    if (unknown.length) {
        const near = [...new Set(unknown.flatMap((k) => closeMatches(k, Object.keys(DEFAULTS), 2)))].sort();
        throw new ValueError(`unknown karst parameter(s) ${JSON.stringify(unknown)}` +
            (near.length ? `; nearest: ${JSON.stringify(near)}` : '') + `; known: ${JSON.stringify(Object.keys(DEFAULTS).sort())}`);
    }
    const out = structuredClone({ ...DEFAULTS, ...KIND_PRESETS[kind], ...params });
    for (const k of PAIRS) {
        const v = out[k];
        out[k] = Array.isArray(v) ? [Number(v[0]), Number(v[1])] : [Number(v), Number(v)];
    }
    return out;
}


// ---------------------------------------------------------------- numpy's arithmetic, in doubles
/** numpy's pairwise summation of a float64 reduction (loops_utils.h pairwise_sum: 8 accumulators up to 128, halves
 * above), as np.sum and np.mean reduce a contiguous array: a[off .. off + n). */
export function pairwiseSum(a, off = 0, n = a.length - off) {
    if (n < 8) {
        let res = 0.0;
        for (let i = 0; i < n; i++) res += a[off + i];
        return res;
    }
    if (n <= 128) {
        const r = [a[off], a[off + 1], a[off + 2], a[off + 3], a[off + 4], a[off + 5], a[off + 6], a[off + 7]];
        let i = 8;
        for (; i < n - (n % 8); i += 8) for (let j = 0; j < 8; j++) r[j] += a[off + i + j];
        let res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; i++) res += a[off + i];
        return res;
    }
    let n2 = Math.floor(n / 2);
    n2 -= n2 % 8;
    return pairwiseSum(a, off, n2) + pairwiseSum(a, off + n2, n - n2);
}

/** np.std(a) (ddof 0) of a float64 array, numpy's way: the pairwise mean, the squared deviations, their pairwise
 * mean, its square root. */
export function npStd(a) {
    const n = a.length;
    const mean = (0.0 + pairwiseSum(a)) / n;
    const d = new Float64Array(n);
    for (let i = 0; i < n; i++) { const x = a[i] - mean; d[i] = x * x; }
    return Math.sqrt((0.0 + pairwiseSum(d)) / n);
}

/** numpy 2.3.4's 'linear' quantile of float64 data (q a float, or a list: float64 throughout for float64 data),
 * from the sorted values: virtual index (n - 1) q, numpy's _lerp. */
export function npQuantile(sorted, q) {
    const n = sorted.length;
    const virt = (n - 1) * q;
    let prev = Math.floor(virt), next = prev + 1;
    if (virt >= n - 1) prev = next = n - 1;
    const gamma = virt - Math.floor(virt);
    const a = sorted[prev], b = sorted[next];
    const diff = b - a;
    return gamma >= 0.5 ? b - diff * (1 - gamma) : a + diff * gamma;
}

/** np.percentile(a, q) of float64 data (q in [0, 100]; float64 throughout). */
export const npPercentile = (sorted, q) => npQuantile(sorted, q / 100);

/** np.median of float64 data: the middle value, or the mean of the two middle values. */
export function npMedian(a) {
    const s = Float64Array.from(a).sort();
    const n = s.length;
    return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

/** np.interp(x, xp, fp) (numpy's arr_interp: slopes precomputed, the left and right ends held, a NaN slope's
 * fallback), for one x. xp increasing. */
export function npInterp(x, xp, fp, slopes = null) {
    const n = xp.length;
    if (!(x >= xp[0])) return x < xp[0] ? fp[0] : NaN;
    if (x > xp[n - 1]) return fp[n - 1];
    if (x === xp[n - 1]) return fp[n - 1];
    let lo = 0, hi = n - 1;                              // xp[lo] <= x < xp[hi]
    while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (xp[mid] <= x) lo = mid; else hi = mid;
    }
    const j = lo;
    const slope = slopes ? slopes[j] : (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    let r = slope * (x - xp[j]) + fp[j];
    if (Number.isNaN(r)) {
        r = slope * (x - xp[j + 1]) + fp[j + 1];
        if (Number.isNaN(r) && fp[j] === fp[j + 1]) r = fp[j];
    }
    return r;
}

/** numpy's slopes for npInterp: (fp[i + 1] - fp[i]) / (xp[i + 1] - xp[i]). */
export function interpSlopes(xp, fp) {
    const out = new Float64Array(Math.max(xp.length - 1, 0));
    for (let i = 0; i < out.length; i++) out[i] = (fp[i + 1] - fp[i]) / (xp[i + 1] - xp[i]);
    return out;
}

/** Python's float floor division a // b (CPython's _float_div_mod). */
export function pyFloorDiv(vx, wx) {
    let mod = vx % wx;
    let div = (vx - mod) / wx;
    if (mod) {
        if ((wx < 0) !== (mod < 0)) {
            mod += wx;
            div -= 1.0;
        }
    }
    if (div) {
        let fd = Math.floor(div);
        if (div - fd > 0.5) fd += 1.0;
        return fd;
    }
    return Math.sign(vx / wx) < 0 || Object.is(vx / wx, -0) ? -0 : 0;
}

/** np.mod for floats (the result takes the divisor's sign). */
export function npMod(a, b) {
    let m = a % b;
    if (m) {
        if ((b < 0) !== (m < 0)) m += b;
    } else {
        m = b < 0 ? -0 : 0;
    }
    return m;
}

const hypot = (a, b) => Math.sqrt(a * a + b * b);
const clip = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);


// ---------------------------------------------------------------- world-space gradient noise (doubles)
// np.cos(np.arange(16) * (2 pi / 16)) and np.sin(...) as numpy 2.3.4 computes them (karst.py _GX16, _GY16), written
// out: V8's Math.sin gives 0.7071067811865475 for the third sine, numpy 0.7071067811865476
// (tests/karst_coast/plan_test.mjs checks the table against numpy's).
const GX16 = Float64Array.from([1, 0.9238795325112867, 0.7071067811865476, 0.38268343236508984, 6.123233995736766e-17,
    -0.3826834323650897, -0.7071067811865475, -0.9238795325112867, -1, -0.9238795325112868, -0.7071067811865477,
    -0.38268343236509034, -1.8369701987210297e-16, 0.38268343236509, 0.7071067811865474, 0.9238795325112865]);
const GY16 = Float64Array.from([0, 0.3826834323650898, 0.7071067811865476, 0.9238795325112867, 1, 0.9238795325112867,
    0.7071067811865476, 0.3826834323650899, 1.2246467991473532e-16, -0.38268343236508967, -0.7071067811865475,
    -0.9238795325112865, -1, -0.9238795325112866, -0.7071067811865477, -0.3826834323650904]);
export { GX16, GY16 };

/** The 32-bit PCG hash (Jarzynski & Olano 2020) of a uint32 (karst.py _pcg; the multiplies wrap mod 2^32). */
export function pcg(v) {
    const s = (Math.imul(v, 747796405) + 2891336453) >>> 0;
    const w = Math.imul(((s >>> ((s >>> 28) + 4)) ^ s) >>> 0, 277803737) >>> 0;
    return ((w >>> 22) ^ w) >>> 0;
}

/** uint32 hash of integer lattice coordinates (any sign) and a salt (karst.py _hash2). */
export function hash2(ix, iy, salt) {
    const a = ix >>> 0, b = iy >>> 0;
    return pcg((a + pcg((b + (salt >>> 0)) >>> 0)) >>> 0);
}

const fade = (t) => t * t * t * (t * (t * 6.0 - 15.0) + 10.0);

/** 2-D gradient noise of world metres x, y at a wavelength in metres: about -1..1, std about 0.3 (karst.py noise2,
 * one point; numpy's block and separable paths compute the same expression per point). */
export function noise2(x, y, wavelength, salt) {
    const gx = x / wavelength, gy = y / wavelength;
    const ix = Math.floor(gx), iy = Math.floor(gy);
    const fx = gx - ix, fy = gy - iy;
    const corner = (di, dj) => {
        const k = hash2(ix + di, iy + dj, salt) & 15;
        return GX16[k] * (fx - di) + GY16[k] * (fy - dj);
    };
    const ux = fade(fx), uy = fade(fy);
    const n00 = corner(0, 0), n10 = corner(1, 0), n01 = corner(0, 1), n11 = corner(1, 1);
    const a = n00 + (n10 - n00) * ux;
    const b = n01 + (n11 - n01) * ux;
    return (a + (b - a) * uy) * 1.41;
}

/** Octaves of noise2, halving the wavelength each time; octaves shorter than minWavelength are left out
 * (karst.py fbm2, one point). */
export function fbm2(x, y, wavelength, octaves, salt, gain = 0.5, minWavelength = 0.0) {
    let out = 0.0, a = 1.0, lam = Number(wavelength);
    for (let k = 0; k < octaves; k++) {
        if (lam >= minWavelength) out += a * noise2(x, y, lam, salt + 7919 * k);
        a *= gain;
        lam *= 0.5;
    }
    return out;
}

/** karst.py _smoothstep (one value). */
export function smoothstep(a, b, x) {
    const t = clip((x - a) / (b - a), 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}


// ---------------------------------------------------------------- the tower's two surfaces
/** A summit cone's height over its apex height at x = distance / foot radius: 1 - x + b x (1 - x), falling on below
 * the foot at the foot's slope, straight (karst.py cone_profile, one value). */
export function coneProfile(x, b) {
    x = Math.max(x, 0.0);
    return x <= 1.0 ? 1.0 - x + b * x * (1.0 - x) : -(1.0 + b) * (x - 1.0);
}

/** A tower's wall as tables of (distance inside the footprint's edge, metres; height, metres): from the plain up, a
 * foot notch at 89 degrees (notch_m tall), then wall bands at wallDeg between ledges (ledge_m tall at ledge_deg, one
 * every ledge_every_m), each band's angle jittered +-2 degrees, up past the tower's height. The distance is the
 * integral of dz / tan(angle): the wall's height at a distance d is np.interp(d, D, Z). Returns { D, Z, D0 }: D0 the
 * same wall with every ledge at the wall's angle (where a ledge has broken off) (karst.py wall_table). */
export function wallTable(rng, heightM, wallDeg, p) {
    const top = 1.3 * Number(heightM) + 5.0;
    const zs = [0.0], ang = [], flat = [];
    let z = rng.uniform(p.notch_m[0], p.notch_m[1]);
    zs.push(z);
    ang.push(89.0);
    flat.push(89.0);
    while (z < top) {
        const a = clip(wallDeg + rng.uniform(-2.0, 2.0), 70.0, 89.0);
        z += rng.uniform(p.ledge_every_m[0], p.ledge_every_m[1]);
        zs.push(z);
        ang.push(a);
        flat.push(a);
        z += rng.uniform(p.ledge_m[0], p.ledge_m[1]);
        zs.push(z);
        ang.push(rng.uniform(p.ledge_deg[0], p.ledge_deg[1]));
        flat.push(a);
    }
    const Z = Float64Array.from(zs);
    const D = new Float64Array(Z.length), D0 = new Float64Array(Z.length);
    for (let i = 1; i < Z.length; i++) {
        const dz = Z[i] - Z[i - 1];
        D[i] = D[i - 1] + dz / Math.tan(radians(ang[i - 1]));
        D0[i] = D0[i - 1] + dz / Math.tan(radians(flat[i - 1]));
    }
    return { D, Z, D0 };
}


// ---------------------------------------------------------------- blue noise
/** Variable-radius Poisson-disc points in [x0, x0 + width) x [y0, y0 + height) metres, by phase-group parallel dart
 * throwing on a background grid of cell rMin / sqrt(2) (karst.py poisson_disc: its module doc). radiusFn(xs, ys)
 * (Float64Arrays) -> metres, between rMin and rMax. Returns { x, y, r } Float64Arrays in numpy's order (row-major over
 * the grid); deterministic for a seed and window. */
export function poissonDisc(seed, x0, y0, width, height, radiusFn, rMin, rMax, tries = 8, throwP = 0.3) {
    const rng = defaultRng(seed);
    const g = rMin / Math.sqrt(2.0);
    const nx = Math.trunc(Math.ceil(width / g)), ny = Math.trunc(Math.ceil(height / g));
    const k = Math.trunc(Math.ceil(rMax / g));
    const P = k + 1, pad = k;
    const W = nx + 2 * pad, H = ny + 2 * pad;
    const GX = new Float64Array(W * H).fill(NaN), GY = new Float64Array(W * H).fill(NaN), GR = new Float64Array(W * H).fill(NaN);
    const fails = new Int32Array(nx * ny);
    const oj = [], oi = [];
    for (let a = -k; a <= k; a++) {
        for (let b = -k; b <= k; b++) {
            if ((Math.max(Math.abs(a), Math.abs(b)) - 1) * g < rMax) { oj.push(a); oi.push(b); }
        }
    }
    const phases = [];
    for (let a = 0; a < P; a++) {
        for (let b = 0; b < P; b++) {
            const pj = [], pi = [];
            for (let j = a; j < ny; j += P) for (let i = b; i < nx; i += P) { pj.push(j); pi.push(i); }
            phases.push([pj, pi]);
        }
    }
    const rounds = Math.trunc(Math.ceil((tries + 2) / throwP)) + 4;
    for (let round = 0; round < rounds; round++) {
        let added = 0;
        for (let ph = 0; ph < phases.length; ph++) {
            let [pj, pi] = phases[ph];
            const lj = [], li = [];
            for (let t = 0; t < pj.length; t++) {
                const j = pj[t], i = pi[t];
                if (Number.isNaN(GX[(j + pad) * W + i + pad]) && fails[j * nx + i] < tries) { lj.push(j); li.push(i); }
            }
            pj = lj;
            pi = li;
            phases[ph] = [pj, pi];
            const pickU = rng.random(pj.length);
            const cj = [], ci = [];
            for (let t = 0; t < pj.length; t++) if (pickU[t] < throwP) { cj.push(pj[t]); ci.push(pi[t]); }
            added += pj.length;
            if (!cj.length) continue;
            const m = cj.length;
            const ux = rng.random(m), uy = rng.random(m);
            const dx = new Float64Array(m), dy = new Float64Array(m);
            for (let t = 0; t < m; t++) {
                dx[t] = x0 + (ci[t] + ux[t]) * g;
                dy[t] = y0 + (cj[t] + uy[t]) * g;
            }
            const rd = radiusFn(dx, dy);
            const okList = new Uint8Array(m);
            for (let t = 0; t < m; t++) {
                const inside = dx[t] < x0 + width && dy[t] < y0 + height;
                let clash = false;
                for (let q = 0; q < oj.length && !clash; q++) {
                    const idx = (cj[t] + pad + oj[q]) * W + ci[t] + pad + oi[q];
                    const ex = GX[idx] - dx[t], ey = GY[idx] - dy[t], qr = GR[idx];
                    const d2 = ex * ex + ey * ey;
                    const lim = Math.max(qr, rd[t]);                      // NaN where the cell is empty
                    if (d2 < lim * lim) clash = true;
                }
                okList[t] = inside && !clash ? 1 : 0;
            }
            for (let t = 0; t < m; t++) {
                if (okList[t]) {
                    const idx = (cj[t] + pad) * W + ci[t] + pad;
                    GX[idx] = dx[t];
                    GY[idx] = dy[t];
                    GR[idx] = rd[t];
                } else {
                    fails[cj[t] * nx + ci[t]] += 1;
                }
            }
        }
        if (added === 0) break;
    }
    const xs = [], ys = [], rs = [];
    for (let i = 0; i < W * H; i++) if (!Number.isNaN(GX[i])) { xs.push(GX[i]); ys.push(GY[i]); rs.push(GR[i]); }
    return { x: Float64Array.from(xs), y: Float64Array.from(ys), r: Float64Array.from(rs) };
}


// ---------------------------------------------------------------- the plan
/** Everything global about one karst terrain: the parameters, the cluster field, the towers and the river (karst.py
 * KarstPlan; its attribute names, as data). Tower arrays are Float64Arrays, one entry per tower (peaks: N x K row by
 * row, NaN where a tower has fewer; spur N x 4 and pk_rib N x K x 6 complex as (re, im) pairs; scarp N x 2 x 3);
 * kind Int8Array, npk Int32Array; angles in radians from +x, counter-clockwise; peak offsets in metres from the
 * tower's centre; polylines (river, river_coarse, river_mid) as (x, y) pairs. */
export class KarstPlan {
    constructor(o) {
        this.seed = o.seed;
        this.domain = o.domain;
        this.params = o.params;
        this.salt = o.salt;
        this.strike = o.strike;
        this.cluster_threshold = o.cluster_threshold;
        this.cluster_band = o.cluster_band;
        this.cluster_std = o.cluster_std ?? 1.0;
        for (const k of ['x', 'y', 'H', 'F', 'R', 'wall', 'kind', 'floor', 'B', 'reach', 'elong', 'axis', 'lean',
            'lean_dir', 'cluster', 'interior', 'spur', 'npk', 'pk_dx', 'pk_dy', 'pk_h', 'pk_r0', 'pk_b', 'pk_e',
            'pk_axis', 'pk_rib', 'scarp', 'body_h', 'body_R', 'body_tan', 'wall_D', 'wall_Z', 'wall_D0', 'river',
            'river_coarse', 'river_mid', 'river_s', 'river_kappa', 'river_hw']) this[k] = null;
        this.water_level = -1e9;
        this.river_dir = [1.0, 0.0];
        this.main = o.main ?? null;
        this.floors = null;
        this.stats = {};
        // the cluster field's rotation, once (karst.py takes math.cos / math.sin of the strike at every call)
        this._cs = [Math.cos(this.strike), Math.sin(this.strike)];
    }

    get count() { return this.x === null ? 0 : this.x.length; }
    get K() { return Math.trunc(this.params.peaks_max); }
}

/** The un-thresholded cluster field at a world point, stretched along the strike: broad noise (where the massifs and
 * the plains are) mixed with ridged noise (the massifs as elongated ridges, peaks strung along their crests)
 * (karst.py _cluster_raw). cs: [cos, sin] of the strike. */
export function clusterRaw(salt, pr, cs, x, y) {
    const [c, s] = cs;
    const u = (x * c + y * s) / pr.cluster_stretch;
    const v = -x * s + y * c;
    const broad = fbm2(u, v, pr.cluster_scale_m, 3, salt + 11, 0.5) / 0.3;
    const a = pr.cluster_ridges;
    if (a <= 0) return broad;
    const n = noise2(u, v, pr.ridge_scale_m, salt + 13) + 0.35 * noise2(u, v, 0.5 * pr.ridge_scale_m, salt + 17);
    const ridged = (1.0 - Math.abs(n) / 0.45) * 1.6;               // about unit std, high along the zero lines of n
    return (1.0 - a) * broad + a * ridged;
}

/** [membership 0..1, raw field] at a world point: 1 inside the clusters, 0 on the plain (karst.py _cluster). */
export function cluster(plan, x, y) {
    const raw = clusterRaw(plan.salt, plan.params, plan._cs, x, y);
    return [smoothstep(plan.cluster_threshold - plan.cluster_band, plan.cluster_threshold + plan.cluster_band, raw), raw];
}

/** The clusters' common base at full height (metres above the plain) at a world point (karst.py _plinth_of). */
export function plinthOf(plan, x, y) {
    const pr = plan.params;
    let out = (pr.plinth_m + pr.base_m) * Math.max(1.0 + 0.25 * fbm2(x, y, 1500.0, 2, plan.salt + 31) / 0.3, 0.3);
    if (pr.base_rough_m > 0) {
        out = out + pr.base_rough_m * (fbm2(x, y, 300.0, 1, plan.salt + 33) + 0.8 * fbm2(x, y, 120.0, 1, plan.salt + 37)) / 0.38;
    }
    return Math.max(out, 0.0);
}

/** How deep inside its cluster a point is (0 at the edge, 1 well inside), from the raw cluster field. */
export function interiorOf(plan, raw) {
    const t0 = plan.cluster_threshold + plan.cluster_band;
    return smoothstep(t0, t0 + 0.9 * plan.cluster_std, raw);
}

/** How much of the common base the points (xs, ys) carry (karst.py _base_membership, on the CPU: the plan's tower
 * centres). Float64Array. */
export function baseMembership(plan, xs, ys) {
    const pr = plan.params, n = xs.length;
    const out = new Float64Array(n);
    if (pr.plinth_m <= 0) {
        for (let i = 0; i < n; i++) out[i] = interiorOf(plan, clusterRaw(plan.salt, pr, plan._cs, xs[i], ys[i]));
        if (plan.river !== null) {
            // the river's corridor is kept clear of towers, so the base fades out before it too
            const d0 = pr.river_width_m * (1.0 + pr.river_width_var) + 80.0;
            const d = riverDistance(plan.river_coarse, xs, ys, d0 + 450.0);
            for (let i = 0; i < n; i++) out[i] = out[i] * smoothstep(d0, d0 + 450.0, d[i]);
        }
        return out;
    }
    const b = 0.3 * plan.cluster_band;
    for (let i = 0; i < n; i++) {
        out[i] = smoothstep(plan.cluster_threshold - b, plan.cluster_threshold + b, clusterRaw(plan.salt, pr, plan._cs, xs[i], ys[i]));
    }
    return out;
}

/** Compass degrees (0 north, clockwise) to radians from +x, counter-clockwise. */
export const compassToRad = (deg) => radians(90.0 - deg);

const uni = (rng, pair, n) => rng.uniform(pair[0], pair[1], n);
const nanTo = (v, x) => (Number.isNaN(v) ? x : v);

/** The summit peaks of every tower (karst.py _place_peaks): [[dx, dy, h, r0, b, e, axis], count], each N x K row by
 * row, NaN past a tower's count. The first peak is the tower's summit (height H) near the centre, at the tower's own
 * cone angle (mainAng). The others: on a ridge tower (elongation over 0.6) strung along its long axis, 0.35-0.6 of its
 * half-length out on alternate sides; on a block, darted inside 0.6 of the footprint at least peak_spacing_m apart.
 * They stand lower (0.6-0.92 H, less 25 % toward the edge, never under the floor), at the peak angle, drawn out along
 * the tower's axis (ridged crests). */
export function placePeaks(rng, pr, R, H, elong, axis, kind, npk, floor, mainAng) {
    const N = R.length, K = Math.trunc(pr.peaks_max), T = 14;
    const nan = () => new Float64Array(N * K).fill(NaN);
    const dx = nan(), dy = nan(), h = nan(), ang = nan();
    const ca = axis.map(Math.cos), sa = axis.map(Math.sin);
    const el = elong.map((e) => 1.0 + e);
    const rFirst = rng.uniform(0.0, 0.12, N);
    for (let t = 0; t < N; t++) rFirst[t] *= R[t];
    const phi = rng.uniform(0.0, TWO_PI, N);
    for (let t = 0; t < N; t++) {
        const along = rFirst[t] * Math.cos(phi[t]) * el[t], across = rFirst[t] * Math.sin(phi[t]) / el[t];
        dx[t * K] = along * ca[t] - across * sa[t];
        dy[t * K] = along * sa[t] + across * ca[t];
        h[t * K] = H[t];
        ang[t * K] = mainAng[t];
    }
    const ridge = elong.map((e) => (e > 0.6 ? 1 : 0));
    const sep = R.map((r) => Math.max(pr.peak_spacing_m, 0.3 * r));
    for (let k = 1; k < K; k++) {
        let any = false;
        for (let t = 0; t < N && !any; t++) if (k < npk[t]) any = true;
        if (!any) break;
        // ridge towers: along the axis, alternate sides; blocks: anywhere inside 0.6 of the footprint
        const side = k % 2 ? 1.0 : -1.0;
        const aR = rng.uniform(0.35, 0.6, N * T), cR = rng.uniform(-0.12, 0.12, N * T);
        const rhoU = rng.uniform(0.04, 1.0, N * T), th = rng.uniform(0.0, TWO_PI, N * T);
        const along = new Float64Array(N * T), across = new Float64Array(N * T);
        const cx = new Float64Array(N * T), cy = new Float64Array(N * T);
        for (let t = 0; t < N; t++) {
            for (let q = 0; q < T; q++) {
                const i = t * T + q;
                if (ridge[t]) {
                    along[i] = side * aR[i] * (R[t] * el[t]);
                    across[i] = cR[i] * R[t];
                } else {
                    const rho = 0.6 * R[t] * Math.sqrt(rhoU[i]);
                    along[i] = rho * Math.cos(th[i]) * el[t];
                    across[i] = rho * Math.sin(th[i]) / el[t];
                }
                cx[i] = along[i] * ca[t] - across[i] * sa[t];
                cy[i] = along[i] * sa[t] + across[i] * ca[t];
            }
        }
        const sel = [], first = [];
        for (let t = 0; t < N; t++) {
            let f = 0, okAny = false;
            for (let q = 0; q < T; q++) {
                const i = t * T + q;
                let dmin = Infinity;
                for (let j = 0; j < k; j++) {
                    const d = hypot(cx[i] - nanTo(dx[t * K + j], 1e9), cy[i] - nanTo(dy[t * K + j], 1e9));
                    dmin = Math.min(dmin, d);
                }
                if (dmin >= sep[t]) { f = q; okAny = true; break; }
            }
            if (okAny && k < npk[t]) { sel.push(t); first.push(f); }
        }
        const hu = rng.uniform(0.6, 0.92, sel.length);
        const au = uni(rng, pr.peak_deg, sel.length);
        sel.forEach((t, s) => {
            const i = t * T + first[s];
            dx[t * K + k] = cx[i];
            dy[t * K + k] = cy[i];
            const u = hypot(along[i] / el[t], across[i] * el[t]) / Math.max(R[t], 1e-6);
            const c = clip(u, 0.0, 1.0);
            h[t * K + k] = H[t] * hu[s] * (1.0 - 0.25 * (c * c));
            ang[t * K + k] = au[s];
        });
    }
    // the placed peaks first in every row (a dart that failed leaves a gap): a stable sort on isnan(h)
    const count = new Int32Array(N);
    for (let t = 0; t < N; t++) {
        const order = [];
        for (let q = 0; q < K; q++) if (!Number.isNaN(h[t * K + q])) order.push(q);
        count[t] = order.length;
        for (let q = 0; q < K; q++) if (Number.isNaN(h[t * K + q])) order.push(q);
        for (const a of [dx, dy, h, ang]) {
            const row = order.map((q) => a[t * K + q]);
            for (let q = 0; q < K; q++) a[t * K + q] = row[q];
        }
    }
    const r0 = nan();
    for (let t = 0; t < N; t++) {
        for (let q = 0; q < K; q++) {
            const i = t * K + q;
            if (Number.isNaN(h[i])) continue;
            if (Number.isFinite(floor[t])) h[i] = Math.max(h[i], floor[t] + 0.15 * H[t]);
            r0[i] = h[i] / Math.tan(radians(ang[i]));
        }
    }
    const bS = uni(rng, pr.spire_convexity, N * K), bP = uni(rng, pr.peak_convexity, N * K);
    const eR = rng.uniform(0.3, 0.8, N * K), eN = rng.uniform(0.0, 0.4, N * K);
    const axN = rng.normal(0.0, 12.0, N * K);
    const b = nan(), e = nan(), ax = nan();
    for (let t = 0; t < N; t++) {
        for (let q = 0; q < K; q++) {
            const i = t * K + q;
            if (Number.isNaN(h[i])) continue;
            b[i] = kind[t] === 0 ? bS[i] : bP[i];
            e[i] = ridge[t] ? eR[i] : eN[i];
            ax[i] = axis[t] + radians(axN[i]);
        }
    }
    return [[dx, dy, h, r0, b, e, ax], count];
}

export const RIB_ORDERS = Object.freeze([2, 3, 4, 5, 6, 7]);         // the ribs' azimuthal harmonics

/** (n, k, 6) complex amplitudes of harmonics 2-7 of each summit cone's distance from its apex, as (re, im) pairs
 * (karst.py rib_harmonics: its doc). Each cone takes s = budget x U(0.5, 1); budget 0 gives zeros. */
export function ribHarmonics(rng, n, k, budget) {
    const M = RIB_ORDERS.length;
    const out = new Float64Array(n * k * M * 2);
    if (budget <= 0 || n === 0) return out;
    const pw = RIB_ORDERS.map((m) => m ** -1.3);
    const w = rng.uniform(0.3, 1.0, n * k * M);
    for (let i = 0; i < n * k; i++) for (let m = 0; m < M; m++) w[i * M + m] = w[i * M + m] * pw[m];
    const s = rng.uniform(0.5, 1.0, n * k);
    for (let i = 0; i < n * k; i++) s[i] = budget * s[i];
    const ph = rng.uniform(0.0, TWO_PI, n * k * M);
    for (let i = 0; i < n * k; i++) {
        let sum = 0.0;
        for (let m = 0; m < M; m++) sum += w[i * M + m] * RIB_ORDERS[m];
        const f = s[i] / sum;
        for (let m = 0; m < M; m++) {
            const a = w[i * M + m] * f;
            out[2 * (i * M + m)] = a * Math.cos(ph[i * M + m]);
            out[2 * (i * M + m) + 1] = a * Math.sin(ph[i * M + m]);
        }
    }
    return out;
}

/** (n, 2, 3) collapse scarps: per tower 0, 1 or 2 (chances pr.scarps), each (direction in radians, cos of its
 * half-width scarp_deg, depth scarp_depth: the share of the footprint radius pulled in at its centre; 0 where a tower
 * has none) (karst.py scarp_sectors). */
export function scarpSectors(rng, n, pr) {
    const out = new Float64Array(n * 6);
    if (n === 0) return out;
    const p = pr.scarps.map(Number);
    const tot = p.reduce((a, b) => a + b, 0);
    const cum = [];
    let c = 0;
    for (const v of p) { c += v / tot; cum.push(c); }
    const r = rng.random(n);
    const count = Array.from(r, (v) => cum.filter((x) => x <= v).length);      // searchsorted(side='right')
    const d0 = rng.uniform(0.0, TWO_PI, n);
    for (let s = 0; s < 2; s++) {
        // a second scarp faces away from the first (100-260 degrees round): two sides shed, not one widened
        const d = s === 0 ? d0 : Float64Array.from(rng.uniform(radians(100.0), radians(260.0), n), (v, i) => d0[i] + v);
        const half = uni(rng, pr.scarp_deg, n);
        const depth = uni(rng, pr.scarp_depth, n);
        for (let t = 0; t < n; t++) {
            out[t * 6 + s * 3] = d[t];
            out[t * 6 + s * 3 + 1] = Math.cos(radians(half[t]));
            out[t * 6 + s * 3 + 2] = count[t] > s ? depth[t] : 0.0;
        }
    }
    return out;
}

/** The plan over domain = [x0, y0, side] metres (the outermost level's window): the cluster field's threshold, the
 * river course (passing near `via`, default the domain's centre), the blue-noise tower centres and every tower's
 * shape numbers (module doc). main = [x0, y0, side], the main tile: cluster_cover is then the share of the main tile
 * in clusters (else of the domain). Deterministic for (seed, domain, params, via, main) (karst.py plan_karst). */
export function planKarst(seed, domain, params = null, via = null, main = null) {
    const pr = paramsFor(params);
    const [x0, y0, side] = domain.map(Number);
    seed = Math.trunc(Number(seed));
    const s32 = seed >>> 0;
    const salt = Number((BigInt(seed) * 2654435761n + 97n) & 0xFFFFFFFn);
    const rng = defaultRng([s32, 0x4B41525354]);                                     // 'KARST'
    const strike = compassToRad(pr.strike_deg);
    const plan = new KarstPlan({ seed, domain: [x0, y0, side], params: pr, salt, strike, cluster_threshold: 0.0,
        cluster_band: 1.0, main: (main ?? domain).map(Number) });

    // the cluster field's threshold: the (1 - cover) quantile over the main tile (or the domain)
    const n = 192;
    const [mx0, my0, mside] = (main ?? domain).map(Number);
    const raw = new Float64Array(n * n);
    for (let j = 0; j < n; j++) {
        const gy = my0 + ((j + 0.5) * mside) / n;
        for (let i = 0; i < n; i++) raw[j * n + i] = clusterRaw(salt, pr, plan._cs, mx0 + ((i + 0.5) * mside) / n, gy);
    }
    const cover = clip(Number(pr.cluster_cover), 0.0, 1.0);
    const sorted = Float64Array.from(raw).sort();
    if (cover >= 1.0) plan.cluster_threshold = sorted[0] - 1.0;
    else if (cover <= 0.0) plan.cluster_threshold = sorted[sorted.length - 1] + 1.0;
    else plan.cluster_threshold = npQuantile(sorted, 1.0 - cover);
    plan.cluster_std = npStd(raw);
    plan.cluster_band = 0.12 * plan.cluster_std;

    // the river: a least-cost course through the plain, then meanders; its flat water level, width and bends
    if (pr.river) {
        [plan.river, plan.river_dir] = riverCourse(plan, rng, via);
        plan.river_coarse = resample(plan.river, 40.0)[0];
        [plan.river_mid, plan.river_s] = resample(plan.river, 30.0);
        plan.river_kappa = curvature(plan.river_mid, 150.0);
        const s = plan.river_s;
        plan.river_hw = Float64Array.from(s, (v) => 0.5 * pr.river_width_m *
            clip(1.0 + pr.river_width_var * (noise2(v, 0.5, 1800.0, salt + 61) / 0.3), 0.5, 1.6));
        plan.water_level = -pr.river_bank_m;
    }

    // tower centres: Poisson-disc at spacing_m in the clusters and plain_spacing times that on the plain, the plain's
    // then thinned to plain_density
    const rCl = pr.spacing_m / 1.12;              // a maximal Poisson-disc set's nearest-neighbour median ~ 1.12 r
    const rPl = rCl * Math.max(pr.plain_spacing, 1.0);
    const radiusFn = (xs, ys) => Float64Array.from(xs, (x, i) => rPl + (rCl - rPl) * cluster(plan, x, ys[i])[0]);
    const margin = 0.5 * rPl;
    const pd = poissonDisc(rng.integers(2 ** 31), x0 - margin, y0 - margin, side + 2 * margin, side + 2 * margin,
        radiusFn, rCl, rPl);
    const m0 = new Float64Array(pd.x.length), raw0 = new Float64Array(pd.x.length);
    for (let i = 0; i < pd.x.length; i++) [m0[i], raw0[i]] = cluster(plan, pd.x[i], pd.y[i]);
    const keepU = rng.random(pd.x.length);
    const kept = [];
    for (let i = 0; i < pd.x.length; i++) if (keepU[i] < m0[i] + (1.0 - m0[i]) * pr.plain_density) kept.push(i);
    let tx = Float64Array.from(kept, (i) => pd.x[i]), ty = Float64Array.from(kept, (i) => pd.y[i]);
    let m = Float64Array.from(kept, (i) => m0[i]);
    const rawT = Float64Array.from(kept, (i) => raw0[i]);
    let N = tx.length;

    // heights; the kind of tower; its footprint
    let interior = Float64Array.from(rawT, (r) => interiorOf(plan, r));
    const w = Float64Array.from(m, (v, i) => clip(0.5 * v + 0.5 * Math.sqrt(interior[i]), 0.0, 1.0));
    const trend = Float64Array.from(tx, (x, i) => Math.exp(pr.height_trend * fbm2(x, ty[i], 2000.0, 2, salt + 23) / 0.3));
    const sn = rng.standard_normal(N);
    let H = Float64Array.from(sn, (z, i) => Math.exp(pr.height_sigma * z) * trend[i] * (0.85 + 0.3 * w[i]));
    if (N) {
        const f = pr.median_height_m / Math.max(npMedian(H), 1e-6);
        for (let i = 0; i < N; i++) H[i] *= f;
    }
    for (let i = 0; i < N; i++) H[i] = clip(H[i], 0.25 * pr.median_height_m, 2.8 * pr.median_height_m);   // 100-300 m
    const bm = baseMembership(plan, tx, ty);
    let F = Float64Array.from(tx, (x, i) => Math.min(plinthOf(plan, x, ty[i]) * bm[i], 0.6 * H[i]));   // under the foot
    for (let i = 0; i < N; i++) H[i] = H[i] - F[i];
    // the kind: a spire, a peak (most), a block; inside the clusters drawn out along the strike
    const inCl = Float64Array.from(m, (v) => smoothstep(0.3, 0.7, v));
    const uK = rng.random(N);
    let kind = new Int8Array(N);
    const tall = new Float64Array(N);
    for (let i = 0; i < N; i++) {
        let slimP = pr.slim_share[0] * (1.0 - inCl[i]) + pr.slim_share[1] * inCl[i];
        let blockP = pr.block_share[0] * (1.0 - inCl[i]) + pr.block_share[1] * inCl[i];
        // the tallest towers are massifs, not single cones: from 1.4 x the median height up, the chance of a slim
        // spire falls and half the rest become blocks (thresholds on the same draw)
        tall[i] = smoothstep(1.4, 2.4, (H[i] + F[i]) / Math.max(pr.median_height_m, 1e-6));
        slimP = slimP * (1.0 - tall[i]);
        blockP = blockP + (1.0 - slimP - blockP) * pr.tall_massif * tall[i];
        kind[i] = uK[i] < slimP ? 0 : (uK[i] < slimP + blockP ? 2 : 1);
    }
    const angS = uni(rng, pr.spire_deg, N), angP = uni(rng, pr.peak_deg, N);
    let ang = Float64Array.from(kind, (k, i) => (k === 0 ? angS[i] : angP[i]));
    const nn3 = knnMedian(tx, ty, 3, 3.0 * pr.spacing_m);
    // inside a cluster a peak's cone reaches toward its neighbours' (cluster_reach of the median distance to its three
    // nearest), so the cones meet at saddles; the cone's angle follows from the peak's height over that reach, held to
    // cluster_peak_deg (a short peak among far neighbours keeps a steep cone and leaves a cockpit beside it)
    const reachU = uni(rng, pr.cluster_reach, N);
    const angCl = Float64Array.from(H, (h, i) =>
        clip(degrees(Math.atan(h / Math.max(reachU[i] * nn3[i], 1.0))), pr.cluster_peak_deg[0], pr.cluster_peak_deg[1]));
    // (by how deep inside: a cluster's edge towers keep the steep peaks of the plain)
    const deep = Float64Array.from(inCl, (v, i) => v * smoothstep(0.0, 0.6, interior[i]));
    ang = Float64Array.from(ang, (a, i) => (kind[i] === 1 ? a + (angCl[i] - a) * deep[i] : a));
    const r0Main = Float64Array.from(H, (h, i) => h / Math.tan(radians(ang[i])));      // the main cone's foot radius
    const massifU = uni(rng, pr.massif_reach, N), blockU = uni(rng, pr.block_girth, N);
    const RBlock = Float64Array.from(inCl, (v, i) => (v > 0.5 ? massifU[i] * nn3[i] : blockU[i] * H[i]));
    // a peak's footprint: on the plain its wall cuts the cone inside its foot; at a cluster's edge cluster_girth of it;
    // deep inside a cluster the whole cone (inner_girth: no wall; its collapse scarps still stand sheer)
    const gClA = uni(rng, pr.cluster_girth, N), gClB = uni(rng, pr.inner_girth, N);
    const gCl = Float64Array.from(gClA, (a, i) => a * (1.0 - interior[i]) + gClB[i] * interior[i]);
    const gPeakU = uni(rng, pr.peak_girth, N);
    const gPeak = Float64Array.from(gPeakU, (a, i) => a * (1.0 - inCl[i]) + gCl[i] * inCl[i]);
    const spireU = uni(rng, pr.spire_girth, N);
    let R = Float64Array.from(kind, (k, i) => Math.max(k === 0 ? spireU[i] * r0Main[i] : (k === 1 ? gPeak[i] * r0Main[i] : RBlock[i]), 12.0));
    const wallN = rng.normal(0.0, pr.wall_spread_deg, N);
    let wall = Float64Array.from(wallN, (v) => clip(pr.wall_deg + v, 70.0, 89.0));
    const floorU = uni(rng, pr.floor, N);
    let floor = Float64Array.from(kind, (k, i) => (k === 2 ? floorU[i] * H[i] : -Infinity));
    const ridgeU = rng.random(N);
    const ridge = Uint8Array.from(kind, (k, i) => (ridgeU[i] < pr.ridge_share + (1.0 - pr.ridge_share) * pr.tall_massif * tall[i] && k !== 0 ? 1 : 0));
    const eCl = uni(rng, pr.cluster_elong, N);
    const elR = rng.uniform(0.6, 1.1, N), elP = rng.uniform(0.0, pr.elongation, N);
    let elong = Float64Array.from(ridge, (r, i) => {
        const e = r ? elR[i] : elP[i] * (1.0 - inCl[i]) + eCl[i] * inCl[i];
        return kind[i] === 0 ? Math.min(e, 0.35) : e;
    });
    const axN = rng.normal(0.0, 1.0, N);
    let axis = Float64Array.from(axN, (v, i) => strike + radians(v * (32.0 - 10.0 * inCl[i])));
    let lean = rng.uniform(0.0, pr.lean, N);
    let leanDir = rng.uniform(0.0, TWO_PI, N);
    // radial spurs: harmonics 2-5 of the footprint radius, weaker with order (buttresses and re-entrants)
    const spurA = rng.uniform(0.0, 1.0, N * 4), spurP = rng.uniform(0.0, TWO_PI, N * 4);
    const SPUR_W = [1.0, 0.75, 0.55, 0.4];
    let spur = new Float64Array(N * 8);
    for (let i = 0; i < N * 4; i++) {
        const a = spurA[i] * pr.spurs * SPUR_W[i % 4];
        spur[2 * i] = a * Math.cos(spurP[i]);
        spur[2 * i + 1] = a * Math.sin(spurP[i]);
    }
    const BU = rng.uniform(0.5, 1.5, N);
    let B = Float64Array.from(H, (h, i) => pr.apron * h * BU[i]);
    let reach = Float64Array.from(B, (b) => 1.6 * b / Math.tan(radians(pr.apron_deg)));
    const npkBlock = rng.integers(2, Math.trunc(pr.peaks_max) + 1, N), npkRidge = rng.integers(2, 4, N);
    const npkIn = Int32Array.from(kind, (k, i) => Math.min(k === 2 ? npkBlock[i] : (elong[i] > 0.6 ? npkRidge[i] : 1), Math.trunc(pr.peaks_max)));
    let [pk, npk] = placePeaks(rng, pr, R, H, elong, axis, kind, npkIn, floor, ang);
    // a cluster peak's profile toward the fengcong cone (concave) by how far inside the cluster it stands (its own
    // stream, so the plain's towers keep theirs)
    const K = Math.trunc(pr.peaks_max);
    const crng = defaultRng([s32, 0x434F4E45]);                                       // 'CONE'
    const bCl = uni(crng, pr.cluster_convexity, N * K);
    for (let t = 0; t < N; t++) {
        const wc = kind[t] === 1 ? deep[t] : 0.0;
        for (let q = 0; q < K; q++) {
            const i = t * K + q;
            if (!Number.isNaN(pk[4][i])) pk[4][i] = pk[4][i] + (bCl[i] - pk[4][i]) * wc;
        }
    }
    let rib = ribHarmonics(defaultRng([s32, 0x52494253]), N, K, pr.ribs);            // 'RIBS'
    let scarp = scarpSectors(defaultRng([s32, 0x53434152]), N, pr);                  // 'SCAR'
    // a cluster's edge towers turn their first scarp toward the plain (down the cluster field's gradient), broad and
    // deep: the massif meets the plain with sheer faces
    const edge = Uint8Array.from(kind, (k, i) => (inCl[i] > 0.3 && interior[i] < 0.6 && k !== 0 ? 1 : 0));
    if (edge.some((v) => v)) {
        const e_ = 25.0;
        const erng = defaultRng([s32, 0x45444745]);                                   // 'EDGE'
        const dirN = erng.normal(0.0, 18.0, N), halfU = erng.uniform(50.0, 80.0, N), depthU = uni(erng, pr.edge_scarp, N);
        for (let t = 0; t < N; t++) {
            if (!edge[t]) continue;
            const rx = clusterRaw(salt, pr, plan._cs, tx[t] + e_, ty[t]) - clusterRaw(salt, pr, plan._cs, tx[t] - e_, ty[t]);
            const ry = clusterRaw(salt, pr, plan._cs, tx[t], ty[t] + e_) - clusterRaw(salt, pr, plan._cs, tx[t], ty[t] - e_);
            scarp[t * 6] = Math.atan2(-ry, -rx) + radians(dirN[t]);
            scarp[t * 6 + 1] = Math.cos(radians(halfU[t]));
            scarp[t * 6 + 2] = Math.max(scarp[t * 6 + 2], depthU[t] * smoothstep(0.6, 0.2, interior[t]));
        }
    }
    // the massif body under a cluster's towers (its own stream): a walled pedestal reaching toward the neighbours
    const brng = defaultRng([s32, 0x424F4459]);                                       // 'BODY'
    const bodyU = uni(brng, pr.body, N), reachB = uni(brng, pr.body_reach, N), degB = uni(brng, pr.body_deg, N);
    let bodyH = Float64Array.from(H, (h, i) => bodyU[i] * h * smoothstep(0.35, 0.85, inCl[i]));
    let bodyR = Float64Array.from(nn3, (v, i) => reachB[i] * v);
    let bodyTan = Float64Array.from(degB, (d) => Math.tan(radians(d)));
    for (let i = 0; i < N; i++) if (!(bodyR[i] > 1.1 * R[i])) bodyH[i] = 0.0;
    // neighbours' bodies that would stand a slot apart (under body_gap_m) are drawn on until they meet
    if (N > 1 && pr.body_gap_m > 0) {
        const outer = Float64Array.from(bodyH, (bh, i) => (bh > 0 ? bodyR[i] : R[i]) * (1.0 + 0.5 * elong[i]));
        const { idx: nb, dist } = knn(tx, ty, 4, 3.0 * pr.spacing_m);
        for (let c = 0; c < 4; c++) {
            const next = Float64Array.from(bodyR);
            for (let i = 0; i < N; i++) {
                const j = nb[i * 4 + c];
                if (j < 0) continue;
                const gap = dist[i * 4 + c] - outer[i] - outer[Math.max(j, 0)];
                if (gap > -5.0 && gap < pr.body_gap_m && bodyH[i] > 0) {
                    next[i] = Math.max(bodyR[i], bodyR[i] + gap / (1.0 + 0.5 * elong[i]) * 0.6 + 8.0);
                }
            }
            bodyR = next;
        }
    }

    // no tower in the river's corridor: its foot, its talus and the river's banks stay clear (a body that would reach
    // it is cut back to the corridor's edge, or dropped)
    if (plan.river !== null && N) {
        const grow = new Float64Array(N), clear = new Float64Array(N);
        const bank = 0.5 * pr.river_width_m * (1.0 + pr.river_width_var) + 2.5 * pr.river_bank_m + 40.0;
        let far = -Infinity;
        for (let i = 0; i < N; i++) {
            let sp = 0.0;
            for (let q = 0; q < 4; q++) sp += hypot(spur[2 * (i * 4 + q)], spur[2 * (i * 4 + q) + 1]);
            grow[i] = (1.0 + elong[i]) * (1.0 + lean[i] + sp);
            clear[i] = R[i] * grow[i] + reach[i] + 2.5 * pr.lobes_m + bank;
            far = Math.max(far, Math.max(clear[i], bodyR[i] * grow[i]));
        }
        const d = riverDistance(plan.river_coarse, tx, ty, far + bank + 50.0);
        const ok = [];
        for (let i = 0; i < N; i++) {
            if (d[i] > clear[i]) ok.push(i);
            bodyR[i] = Math.min(bodyR[i], Math.max(d[i] - bank - 2.5 * pr.lobes_m, 0.0) / grow[i]);
            if (!(bodyR[i] > 1.1 * R[i])) bodyH[i] = 0.0;
        }
        const pick = (a, per = 1) => {
            const o = new a.constructor(ok.length * per);
            ok.forEach((i, s) => { for (let q = 0; q < per; q++) o[s * per + q] = a[i * per + q]; });
            return o;
        };
        [tx, ty, H, F, R, wall, kind, floor, B, reach, elong, axis, lean, leanDir, m, interior, bodyH, bodyR, bodyTan] =
            [tx, ty, H, F, R, wall, kind, floor, B, reach, elong, axis, lean, leanDir, m, interior, bodyH, bodyR, bodyTan].map((a) => pick(a));
        spur = pick(spur, 8);
        npk = pick(npk);
        rib = pick(rib, K * RIB_ORDERS.length * 2);
        scarp = pick(scarp, 6);
        pk = pk.map((a) => pick(a, K));
        N = ok.length;
    }
    // the skirt never climbs past body_top of the tower's height at its centre
    for (let i = 0; i < N; i++) bodyTan[i] = Math.min(bodyTan[i], Math.max(pr.body_top * H[i] - bodyH[i], 0.0) / Math.max(bodyR[i], 1.0));
    Object.assign(plan, { body_h: bodyH, body_R: bodyR, body_tan: bodyTan, pk_rib: rib, scarp, x: tx, y: ty, H, F, R,
        wall, kind, floor, B, reach, spur, elong, axis, lean, lean_dir: leanDir, cluster: m, interior, npk });
    [plan.pk_dx, plan.pk_dy, plan.pk_h, plan.pk_r0, plan.pk_b, plan.pk_e, plan.pk_axis] = pk;
    // every tower's wall table (its ledges), from its own stream: a tower keeps its wall whatever else changes
    plan.wall_D = [];
    plan.wall_Z = [];
    plan.wall_D0 = [];
    for (let t = 0; t < N; t++) {
        const wt = wallTable(defaultRng([s32, 0x57414C4C, t]), H[t], wall[t], pr);
        plan.wall_D.push(wt.D);
        plan.wall_Z.push(wt.Z);
        plan.wall_D0.push(wt.D0);
    }
    if (N) {
        const pct = (a) => { const s = Float64Array.from(a).sort(); return [10, 50, 90].map((q) => pyRound1(npPercentile(s, q))); };
        let spire = 0, peak = 0, block = 0, ridgeN = 0;
        for (let i = 0; i < N; i++) {
            if (kind[i] === 0) spire++; else if (kind[i] === 1) peak++; else block++;
            if (elong[i] > 0.6) ridgeN++;
        }
        plan.stats = { towers: N, density_per_km2: N / (side / 1000.0) ** 2, H_p10_p50_p90: pct(Float64Array.from(H, (h, i) => h + F[i])),
            R_p10_p50_p90: pct(R), kinds: { spire, peak, block, ridge: ridgeN }, wall_p10_p50_p90: pct(wall) };
    }
    return plan;
}

// Python's round(x, 1) for the plan's stats (the exact decimal rounding Python's format makes)
const pyRound1 = (x) => Number(pyFormat(x, '.1f'));

/** For every point, its k nearest other points within maxD: { idx (N x k, -1 where fewer), dist (N x k, Infinity
 * there) }, nearest first (karst.py _knn). */
export function knn(x, y, k, maxD) {
    const n = x.length;
    const idx = new Int32Array(n * k).fill(-1), dist = new Float64Array(n * k).fill(Infinity);
    if (n < 2) return { idx, dist };
    const bins = binPoints(x, y, maxD);
    for (const [key, members] of bins.map) {
        const cand = neighbourCands(bins, key);
        for (const q of members) {
            const ds = cand.map((j) => {
                let d = j === q ? Infinity : Math.sqrt((x[q] - x[j]) * (x[q] - x[j]) + (y[q] - y[j]) * (y[q] - y[j]));
                if (d > maxD) d = Infinity;
                return [d, j];
            });
            const kk = Math.min(k, ds.length);
            ds.sort((a, b) => a[0] - b[0]);
            for (let c = 0; c < kk; c++) {
                dist[q * k + c] = ds[c][0];
                idx[q * k + c] = Number.isFinite(ds[c][0]) ? ds[c][1] : -1;
            }
        }
    }
    return { idx, dist };
}

/** For every point, the median of its distances to its k nearest other points (metres; at most maxD) (karst.py
 * _knn_median). */
export function knnMedian(x, y, k, maxD) {
    const n = x.length;
    const out = new Float64Array(n).fill(Number(maxD));
    if (n < 2) return out;
    const bins = binPoints(x, y, maxD);
    for (const [key, members] of bins.map) {
        const cand = neighbourCands(bins, key);
        const kk = Math.min(k, cand.length - 1);
        if (kk < 1) continue;
        for (const q of members) {
            const ds = cand.map((j) => (j === q ? Infinity : Math.sqrt((x[q] - x[j]) * (x[q] - x[j]) + (y[q] - y[j]) * (y[q] - y[j]))));
            ds.sort((a, b) => a - b);
            const part = ds.slice(0, kk);
            const med = kk % 2 ? part[(kk - 1) / 2] : (part[kk / 2 - 1] + part[kk / 2]) / 2;
            out[q] = Math.min(med, maxD);
        }
    }
    return out;
}

// points binned by floor(x / size), floor(y / size): a Map in the order numpy's dict fills (first appearance)
function binPoints(x, y, size) {
    const map = new Map();
    for (let i = 0; i < x.length; i++) {
        const key = `${Math.floor(x[i] / size)},${Math.floor(y[i] / size)}`;
        let a = map.get(key);
        if (!a) map.set(key, (a = []));
        a.push(i);
    }
    return { map };
}

function neighbourCands(bins, key) {
    const [cx, cy] = key.split(',').map(Number);
    const out = [];
    for (const ddx of [-1, 0, 1]) for (const ddy of [-1, 0, 1]) for (const j of bins.map.get(`${cx + ddx},${cy + ddy}`) ?? []) out.push(j);
    return out;
}


// ---------------------------------------------------------------- the river course
/** Least-cost 8-connected path on a grid of cell costs (ny x nx, float64 row by row); [[j, i], ...] from start to
 * goal. A binary heap ordered as Python's heapq orders its (cost, j, i) tuples (karst.py _dijkstra). */
export function dijkstra(cost, ny, nx, start, goal) {
    const dist = new Float64Array(ny * nx).fill(Infinity);
    const prev = new Int32Array(ny * nx).fill(-1);
    dist[start[0] * nx + start[1]] = 0.0;
    const heap = new MinHeap();
    heap.push([0.0, start[0], start[1]]);
    const steps = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
    while (heap.size) {
        const [d, j, i] = heap.pop();
        if (d > dist[j * nx + i]) continue;
        if (j === goal[0] && i === goal[1]) break;
        for (const [dj, di] of steps) {
            const jj = j + dj, ii = i + di;
            if (jj >= 0 && jj < ny && ii >= 0 && ii < nx) {
                const nd = d + 0.5 * (cost[j * nx + i] + cost[jj * nx + ii]) * (dj && di ? 1.4142135 : 1.0);
                if (nd < dist[jj * nx + ii]) {
                    dist[jj * nx + ii] = nd;
                    prev[jj * nx + ii] = j * nx + i;
                    heap.push([nd, jj, ii]);
                }
            }
        }
    }
    const path = [goal];
    while (!(path[path.length - 1][0] === start[0] && path[path.length - 1][1] === start[1])) {
        const last = path[path.length - 1];
        const k = prev[last[0] * nx + last[1]];
        if (k < 0) break;
        path.push([Math.floor(k / nx), k % nx]);
    }
    return path.reverse();
}

// a binary min-heap of (cost, j, i) tuples compared as Python compares tuples
class MinHeap {
    constructor() { this.a = []; }
    get size() { return this.a.length; }
    static less(p, q) { return p[0] < q[0] || (p[0] === q[0] && (p[1] < q[1] || (p[1] === q[1] && p[2] < q[2]))); }
    push(v) {
        const a = this.a;
        a.push(v);
        let i = a.length - 1;
        while (i > 0) {
            const p = (i - 1) >> 1;
            if (!MinHeap.less(a[i], a[p])) break;
            [a[i], a[p]] = [a[p], a[i]];
            i = p;
        }
    }
    pop() {
        const a = this.a, top = a[0], last = a.pop();
        if (a.length) {
            a[0] = last;
            let i = 0;
            for (;;) {
                const l = 2 * i + 1, r = l + 1;
                let s = i;
                if (l < a.length && MinHeap.less(a[l], a[s])) s = l;
                if (r < a.length && MinHeap.less(a[r], a[s])) s = r;
                if (s === i) break;
                [a[i], a[s]] = [a[s], a[i]];
                i = s;
            }
        }
        return top;
    }
}

/** Chaikin's corner cutting, `times` passes (karst.py _chaikin). pts: (x, y) pairs. */
export function chaikin(pts, times) {
    for (let t = 0; t < times; t++) {
        const n = pts.length / 2;
        const out = new Float64Array(2 * (2 * (n - 1) + 2));
        out[0] = pts[0];
        out[1] = pts[1];
        for (let i = 0; i < n - 1; i++) {
            for (let c = 0; c < 2; c++) {
                out[2 * (1 + 2 * i) + c] = 0.75 * pts[2 * i + c] + 0.25 * pts[2 * (i + 1) + c];
                out[2 * (2 + 2 * i) + c] = 0.25 * pts[2 * i + c] + 0.75 * pts[2 * (i + 1) + c];
            }
        }
        out[out.length - 2] = pts[pts.length - 2];
        out[out.length - 1] = pts[pts.length - 1];
        pts = out;
    }
    return pts;
}

/** The polyline resampled every `step` metres of arc length (and its end): [points, arc lengths] (karst.py
 * _resample). */
export function resample(pts, step) {
    const n = pts.length / 2;
    const s = new Float64Array(n);
    for (let i = 1; i < n; i++) {
        s[i] = s[i - 1] + hypotC(pts[2 * i] - pts[2 * (i - 1)], pts[2 * i + 1] - pts[2 * (i - 1) + 1]);
    }
    const end = s[n - 1];
    const m = Math.max(Math.trunc(Math.ceil(end / step)), 0);
    const t = new Float64Array(m + 1);
    for (let i = 0; i < m; i++) t[i] = i * step;
    t[m] = end;
    const xs = Float64Array.from({ length: n }, (_, i) => pts[2 * i]), ys = Float64Array.from({ length: n }, (_, i) => pts[2 * i + 1]);
    const sx = interpSlopes(s, xs), sy = interpSlopes(s, ys);
    const out = new Float64Array(2 * t.length);
    for (let i = 0; i < t.length; i++) {
        out[2 * i] = npInterp(t[i], s, xs, sx);
        out[2 * i + 1] = npInterp(t[i], s, ys, sy);
    }
    return [out, t];
}

// np.hypot as Blender's numpy computes it on float64: sqrt(a * a + b * b), bit for bit on the river's resamplings of
// seeds 1, 6 and 8 (V8's Math.hypot rounds differently on a fifth of them; measured)
const hypotC = hypot;

/** Signed curvature (1/m, + turning left) at each vertex of an evenly resampled polyline, from the turning angle of
 * its neighbouring segments, smoothed by a Gaussian of smoothM along the line (karst.py _curvature). */
export function curvature(pts, smoothM) {
    const n = pts.length / 2;
    const tx = new Float64Array(n - 1), ty = new Float64Array(n - 1);
    for (let i = 0; i < n - 1; i++) { tx[i] = pts[2 * (i + 1)] - pts[2 * i]; ty[i] = pts[2 * (i + 1) + 1] - pts[2 * i + 1]; }
    const ang = unwrap(Float64Array.from(tx, (x, i) => Math.atan2(ty[i], x)));
    const seg = Float64Array.from(tx, (x, i) => Math.max(hypotC(x, ty[i]), 1e-9));
    const k = new Float64Array(n);
    for (let i = 1; i < n - 1; i++) k[i] = (ang[i] - ang[i - 1]) / (0.5 * (seg[i] + seg[i - 1]));
    const step = npMedian(seg);
    const sig = Math.max(smoothM / step, 0.5);
    const r = Math.trunc(Math.ceil(3 * sig));
    const w = new Float64Array(2 * r + 1);
    for (let i = -r; i <= r; i++) { const q = i / sig; w[i + r] = Math.exp(-0.5 * (q * q)); }
    const ws = 0.0 + pairwiseSum(w);
    for (let i = 0; i < w.length; i++) w[i] = w[i] / ws;
    // np.convolve(np.pad(k, r, mode='edge'), w, mode='valid'): out[i] = sum_m pad[i + m] w[2r - m]
    const pad = (i) => k[clip(i - r, 0, n - 1)];
    const out = new Float64Array(n);
    for (let i = 0; i < n; i++) {
        let acc = 0.0;
        for (let mm = 0; mm < 2 * r + 1; mm++) acc += pad(i + mm) * w[2 * r - mm];
        out[i] = acc;
    }
    return out;
}

/** np.unwrap (period 2 pi, discont pi). */
export function unwrap(p) {
    const n = p.length;
    const up = Float64Array.from(p);
    let cum = 0.0;
    for (let i = 1; i < n; i++) {
        const dd = p[i] - p[i - 1];
        let ddmod = npMod(dd - -Math.PI, TWO_PI) + -Math.PI;
        if (ddmod === -Math.PI && dd > 0) ddmod = Math.PI;
        let corr = ddmod - dd;
        if (Math.abs(dd) < Math.PI) corr = 0;
        cum += corr;
        up[i] = p[i] + cum;
    }
    return up;
}

/** A river across the domain: a least-cost course through the plain (low cluster membership) from the upstream edge,
 * near `via`, to the downstream edge; smoothed, then given meanders by a lateral offset of smooth 1-D noise along its
 * length (karst.py _river_course). Returns [polyline (x, y) pairs, upstream first at 10 m steps, [dx, dy] the flow
 * direction]. */
export function riverCourse(plan, rng, via) {
    const pr = plan.params;
    const [x0, y0, side] = plan.domain;
    const n = 160;
    const cs = side / n;
    let az = pr.river_azimuth_deg;
    if (az === null || az === undefined) az = rng.uniform(0.0, 360.0);
    const a = compassToRad(az);
    const d = [Math.cos(a), Math.sin(a)];
    const [vx, vy] = via === null || via === undefined ? [x0 + side / 2, y0 + side / 2] : [Number(via[0]), Number(via[1])];
    // the cost: clusters are expensive (the river finds the plain), and a soft pull toward the line through `via`
    // along the flow direction keeps the course passing the main tile without a forced waypoint (no doubling back)
    const cost = new Float64Array(n * n);
    const lineScale = Math.max(0.12 * side, 1.0);
    for (let j = 0; j < n; j++) {
        const gy = y0 + (j + 0.5) * cs;
        for (let i = 0; i < n; i++) {
            const gx = x0 + (i + 0.5) * cs;
            const mm = cluster(plan, gx, gy)[0];
            const offLine = Math.abs(-(gx - vx) * d[1] + (gy - vy) * d[0]);
            const ol = offLine / lineScale;
            cost[j * n + i] = 1.0 + 60.0 * (mm * mm) + 0.6 * (fbm2(gx, gy, 1200.0, 2, plan.salt + 41) + 1.0) + 3.0 * (ol * ol);
        }
    }
    const edgeCell = (sign) => {
        let px = vx + sign * d[0] * side * 1.5, py = vy + sign * d[1] * side * 1.5;
        px = clip(px, x0 + 0.5 * cs, x0 + side - 0.5 * cs);
        py = clip(py, y0 + 0.5 * cs, y0 + side - 0.5 * cs);
        return [Math.trunc(pyFloorDiv(py - y0, cs)), Math.trunc(pyFloorDiv(px - x0, cs))];
    };
    const up = edgeCell(-1.0), down = edgeCell(+1.0);
    const cells = dijkstra(cost, n, n, up, down);
    let pts = new Float64Array(2 * cells.length);
    cells.forEach(([j, i], k) => { pts[2 * k] = x0 + (i + 0.5) * cs; pts[2 * k + 1] = y0 + (j + 0.5) * cs; });
    pts = chaikin(pts, 4);
    let s;
    [pts, s] = resample(pts, 20.0);
    const w = pr.river_width_m;
    const m = pts.length / 2;
    // np.gradient along the points (central differences, one-sided at the ends), normalised; the normal to its left
    const tg = new Float64Array(2 * m);
    for (let i = 0; i < m; i++) {
        for (let c = 0; c < 2; c++) {
            tg[2 * i + c] = i === 0 ? (pts[2 + c] - pts[c]) / 1.0 : i === m - 1 ? (pts[2 * i + c] - pts[2 * (i - 1) + c]) / 1.0
                : (pts[2 * (i + 1) + c] - pts[2 * (i - 1) + c]) / 2.0;
        }
        const l = Math.max(hypotC(tg[2 * i], tg[2 * i + 1]), 1e-9);
        tg[2 * i] /= l;
        tg[2 * i + 1] /= l;
    }
    const lam = 13.0 * w;                                     // meander wavelength ~ 13 channel widths
    const moved = new Float64Array(2 * m);
    for (let i = 0; i < m; i++) {
        const off = pr.river_meander * w * (1.6 * noise2(s[i], 0.5, lam, plan.salt + 53) + 0.55 * noise2(s[i], 0.5, 0.45 * lam, plan.salt + 59));
        moved[2 * i] = pts[2 * i] + -tg[2 * i + 1] * off;
        moved[2 * i + 1] = pts[2 * i + 1] + tg[2 * i] * off;
    }
    pts = chaikin(moved, 2);
    [pts] = resample(pts, 10.0);
    const k = pts.length / 2;
    let fx = pts[2 * (k - 1)] - pts[0], fy = pts[2 * (k - 1) + 1] - pts[1];
    const fl = Math.max(hypotC(fx, fy), 1e-9);
    fx /= fl;
    fy /= fl;
    return [pts, [fx, fy]];
}

/** The distance (metres) from points xs, ys to a polyline ((x, y) pairs), capped at maxD (karst.py _river_distance:
 * numpy measures only the segments its bins can bring within maxD, which is every segment that is; the minimum is the
 * same). On the CPU: the plan's tower centres. */
export function riverDistance(poly, xs, ys, maxD) {
    const n = xs.length;
    const out = new Float64Array(n).fill(Number(maxD));
    if (poly === null || n === 0) return out;
    const ns = poly.length / 2 - 1;
    // segments binned by their midpoint on a grid of B = maxD + 20 m plus the longest segment: a point looks in the
    // 3 x 3 bins around its own
    let longest = 0;
    for (let s = 0; s < ns; s++) longest = Math.max(longest, hypotC(poly[2 * s + 2] - poly[2 * s], poly[2 * s + 3] - poly[2 * s + 1]));
    const Bs = Number(maxD) + 20.0 + longest;
    const bins = new Map();
    for (let s = 0; s < ns; s++) {
        const mx = poly[2 * s] + 0.5 * (poly[2 * s + 2] - poly[2 * s]), my = poly[2 * s + 1] + 0.5 * (poly[2 * s + 3] - poly[2 * s + 1]);
        const key = `${Math.floor(mx / Bs)},${Math.floor(my / Bs)}`;
        let a = bins.get(key);
        if (!a) bins.set(key, (a = []));
        a.push(s);
    }
    for (let p = 0; p < n; p++) {
        const bx = Math.floor(xs[p] / Bs), by = Math.floor(ys[p] / Bs);
        let best = out[p];
        for (let ddx = -1; ddx <= 1; ddx++) {
            for (let ddy = -1; ddy <= 1; ddy++) {
                for (const s of bins.get(`${bx + ddx},${by + ddy}`) ?? []) {
                    const ax = poly[2 * s], ay = poly[2 * s + 1];
                    const abx = poly[2 * s + 2] - ax, aby = poly[2 * s + 3] - ay;
                    const L2 = Math.max(abx * abx + aby * aby, 1e-12);
                    const t = clip(((xs[p] - ax) * abx + (ys[p] - ay) * aby) / L2, 0, 1);
                    const ddx2 = ax + t * abx - xs[p], ddy2 = ay + t * aby - ys[p];
                    const dd = Math.sqrt(ddx2 * ddx2 + ddy2 * ddy2);
                    if (dd < best) best = dd;
                }
            }
        }
        out[p] = Math.min(best, maxD);
    }
    return out;
}


// ---------------------------------------------------------------- evaluation on a level (the GPU)
/** Subsamples per cell axis: a wall spans a few metres, so levels coarser than 2.5 m average 2 x 2 subsamples per cell
 * (the horizon levels are drawn at a 2-cell vertex stride: more would buy nothing visible). */
export const supersamplingFor = (cell) => (cell <= 2.5 ? 1 : 2);

/** A level's subsample grid (karst.py _Grid): xs, ys the subsamples' world coordinates (doubles), and G.smooth's
 * world-anchored lattices (lattice()). */
export class Grid {
    constructor(x0, y0, cell, n, ss) {
        Object.assign(this, { x0, y0, cell, n, ss });
        this.sub = cell / ss;
        this.N = n * ss;
        this.xs = Float64Array.from({ length: this.N }, (_, i) => x0 + (i + 0.5) * this.sub);
        this.ys = Float64Array.from({ length: this.N }, (_, j) => y0 + (j + 0.5) * this.sub);
    }

    /** The lattice G.smooth samples a field of shortest wavelength shortestM on: { k, step, m, lx, ly, crop }. */
    lattice(shortestM) {
        const k = Math.max(1, Math.trunc(shortestM / (8.0 * this.cell)));
        const step = k * this.cell;
        let m = Math.trunc(Math.ceil(this.n / k)) + 3;
        let lx, ly;
        if (k === 1) {
            lx = Float64Array.from({ length: m }, (_, i) => this.x0 + 0.5 * this.cell + (i - 1) * step);
            ly = Float64Array.from({ length: m }, (_, i) => this.y0 + 0.5 * this.cell + (i - 1) * step);
        } else {
            const jx = Math.floor((this.x0 - 0.5 * this.cell) / step) - 1;
            const jy = Math.floor((this.y0 - 0.5 * this.cell) / step) - 1;
            lx = Float64Array.from({ length: m + 1 }, (_, i) => 0.5 * this.cell + (jx + i) * step);
            ly = Float64Array.from({ length: m + 1 }, (_, i) => 0.5 * this.cell + (jy + i) * step);
            m += 1;
        }
        return { k, step, m, lx, ly, crop: k === 1 && this.ss === 1 };
    }
}

// G.smooth's bilinear tables for one axis: per subsample (i0, fx), fx not clipped; the crop when crop
function smoothAxis(qs, lat, crop) {
    const out = new Float32Array(2 * qs.length);
    for (let i = 0; i < qs.length; i++) {
        if (crop) { out[2 * i] = i + 1; out[2 * i + 1] = 0; continue; }
        const t = (qs[i] - lat[0]) / lat.step;
        const i0 = clip(Math.floor(t), 0, lat.m - 2);
        out[2 * i] = i0;
        out[2 * i + 1] = t - i0;
    }
    return out;
}

// _bilinear_sep's tables for one axis: per query (i0, fx), fx clipped to [0, 1]
function sepAxis(lx, qs) {
    const out = new Float32Array(2 * qs.length);
    const d = lx[1] - lx[0];
    for (let i = 0; i < qs.length; i++) {
        const t = (qs[i] - lx[0]) / d;
        const i0 = clip(Math.floor(t), 0, lx.length - 2);
        out[2 * i] = i0;
        out[2 * i + 1] = clip(t - i0, 0.0, 1.0);
    }
    return out;
}

// a crop table: output i reads lattice i + 1 exactly
const cropAxis = (n) => Float32Array.from({ length: 2 * n }, (_, k) => (k % 2 ? 0 : k / 2 + 1));

const KERNELS = new WeakMap();
function kernelOf(R, name) {
    let m = KERNELS.get(R);
    if (!m) KERNELS.set(R, (m = new Map()));
    let k = m.get(name);
    if (!k) m.set(name, (k = R.kernel(name)));
    return k;
}
const groupsOf = (h, w) => [Math.ceil(w / 16), Math.ceil(h / 16), 1];

/** A noise term: noise2 at wavelength lam with a salt and an octave weight; rot { c, s, st } for the cluster field's
 * rotated, stretched coordinates (u = (x c + y s) / st, v = -x s + y c). */
const term = (lam, salt, amp = 1.0, rot = null) => ({ lam: Number(lam), salt: salt >>> 0, amp, rot });

/** fbm2's terms: octaves of halving wavelength and gain^k weight, those under minWavelength left out. */
function fbmTerms(lam, octaves, salt, gain = 0.5, minWavelength = 0.0, rot = null) {
    const out = [];
    let a = 1.0;
    for (let k = 0; k < octaves; k++) {
        if (lam >= minWavelength) out.push(term(lam, salt + 7919 * k, a, rot));
        a *= gain;
        lam *= 0.5;
    }
    return out;
}

// (integer cell, float32 fraction) of a lattice coordinate g, in doubles
const split = (g, out, k) => { const i = Math.floor(g); out[k] = i; out[k + 1] = g - i; };

/** The split lattice coordinates of terms on a separable grid (world columns xs, rows ys): { tx (2T rows x xs, rg),
 * ty (2T rows x ys, rg) } as kernels/karst/world.wgsl reads them. */
export function latticeTables(terms, xs, ys) {
    const T = terms.length, M = xs.length, Mr = ys.length;
    const tx = new Float32Array(2 * T * M * 2), ty = new Float32Array(2 * T * Mr * 2);
    terms.forEach((t, k) => {
        const gxRow = 2 * k * M * 2, gyRow = (2 * k + 1) * M * 2, hxRow = 2 * k * Mr * 2, hyRow = (2 * k + 1) * Mr * 2;
        for (let i = 0; i < M; i++) {
            if (t.rot) {
                split((xs[i] * t.rot.c) / t.rot.st / t.lam, tx, gxRow + 2 * i);
                split((-xs[i] * t.rot.s) / t.lam, tx, gyRow + 2 * i);
            } else {
                split(xs[i] / t.lam, tx, gxRow + 2 * i);
            }
        }
        for (let j = 0; j < Mr; j++) {
            if (t.rot) {
                split((ys[j] * t.rot.s) / t.rot.st / t.lam, ty, hxRow + 2 * j);
                split((ys[j] * t.rot.c) / t.lam, ty, hyRow + 2 * j);
            } else {
                split(ys[j] / t.lam, ty, hyRow + 2 * j);
            }
        }
    });
    return { tx, ty };
}

/** A world function (kernels/karst/world.wgsl, mode and its uniforms) on the separable grid xs x ys: a new r32f field
 * of ys.length rows. */
function worldGrid(R, xs, ys, terms, mode, un = {}, rd = null) {
    const { tx, ty } = latticeTables(terms, xs, ys);
    const T = Math.max(terms.length, 1);
    const ftx = R.field(2 * T, xs.length, 2, terms.length ? tx : new Float32Array(2 * T * xs.length * 2));
    const fty = R.field(2 * T, ys.length, 2, terms.length ? ty : new Float32Array(2 * T * ys.length * 2));
    const salts = R.field(1, T, 1, Uint32Array.from({ length: T }, (_, k) => terms[k]?.salt ?? 0), 'u32');
    const amps = R.field(1, T, 1, Float32Array.from({ length: T }, (_, k) => terms[k]?.amp ?? 0));
    const out = R.field(ys.length, xs.length, 1);
    const D = Gd.dummies(R);
    R.run(kernelOf(R, 'karst/world'), { tx: ftx, ty: fty, salts, amps, rd: rd ?? D.f1 }, { outV: out },
        { uMode: mode, uNT: terms.length, uFlags: un.flags ?? 0, uA: un.A ?? 1.0, uB: un.B ?? 1.0, uC: un.C ?? 0.0,
            uD: un.D ?? 0.0, uE: un.E ?? 0.0, uF: un.F ?? 0.0, uG: un.G ?? 0.0 });
    for (const f of [ftx, fty, salts, amps]) f.destroy();
    return out;
}

/** A field on the separable lattice (xs, ys) read at the queries: kernels/karst/bilinear.wgsl with the axis tables
 * ax, ay ((i0, f) pairs). A new r32f field ay rows x ax columns. */
function bilinear(R, v, ax, ay, mode = 0, channel = 0) {
    const w = ax.length / 2, h = ay.length / 2;
    const fax = R.field(1, w, 2, ax), fay = R.field(1, h, 2, ay);
    const out = R.field(h, w, 1);
    R.run(kernelOf(R, 'karst/bilinear'), { v, ax: fax, ay: fay }, { outF: out }, { uMode: mode, uChannel: channel });
    fax.destroy();
    fay.destroy();
    return out;
}

/** _Grid.smooth: fn's world function (terms, mode, uniforms) on the lattice of its shortest wavelength, then bilinear
 * onto the level's subsamples. opts.rd(lat) gives a field on the lattice the function reads (the river's distance).
 * A new N x N field. */
function smoothField(R, G, shortestM, terms, mode, un = {}, opts = {}) {
    const lat = G.lattice(shortestM);
    lat.lx.step = lat.step;
    lat.lx.m = lat.m;
    lat.ly.step = lat.step;
    lat.ly.m = lat.m;
    const rd = opts.rd ? opts.rd(lat) : null;
    const v = worldGrid(R, lat.lx, lat.ly, terms, mode, un, rd);
    if (rd) rd.destroy();
    const out = bilinear(R, v, smoothAxis(G.xs, lat.lx, lat.crop), smoothAxis(G.ys, lat.ly, lat.crop));
    v.destroy();
    return out;
}

/** The course's segments within maxD of every 16 x 16 tile of a uniform grid of points (first point (x0, y0), spacing
 * step, w x h points), in ascending order, their ends in metres from the tile's first point (doubles, rounded once):
 * kernels/karst/river.wgsl's tables { segs, sarc, bins, tilesX } (karst.py _river_bins' job). */
export function riverBins(poly, sv, x0, y0, step, w, h, maxD) {
    const tilesX = Math.ceil(w / 16), tilesY = Math.ceil(h / 16);
    const lists = Array.from({ length: tilesX * tilesY }, () => []);
    const ns = poly.length / 2 - 1;
    const span = 15 * step;
    for (let s = 0; s < ns; s++) {
        const ax = poly[2 * s], ay = poly[2 * s + 1], bx = poly[2 * s + 2], by = poly[2 * s + 3];
        const lo = [Math.min(ax, bx) - maxD, Math.min(ay, by) - maxD], hi = [Math.max(ax, bx) + maxD, Math.max(ay, by) + maxD];
        // tiles whose box [ox, ox + span] meets [lo, hi]
        const t0x = Math.max(0, Math.floor((lo[0] - x0 - span) / (16 * step))), t1x = Math.min(tilesX - 1, Math.floor((hi[0] - x0) / (16 * step)));
        const t0y = Math.max(0, Math.floor((lo[1] - y0 - span) / (16 * step))), t1y = Math.min(tilesY - 1, Math.floor((hi[1] - y0) / (16 * step)));
        for (let ty = t0y; ty <= t1y; ty++) {
            const oy = y0 + 16 * ty * step;
            if (oy > hi[1] || oy + span < lo[1]) continue;
            for (let tx = t0x; tx <= t1x; tx++) {
                const ox = x0 + 16 * tx * step;
                if (ox > hi[0] || ox + span < lo[0]) continue;
                lists[ty * tilesX + tx].push(s);
            }
        }
    }
    let E = 0;
    for (const l of lists) E += l.length;
    const segs = new Float32Array(Math.max(E, 1) * 4), sarc = new Float32Array(Math.max(E, 1) * 2);
    const bins = new Uint32Array(2 * lists.length);
    let e = 0;
    lists.forEach((l, t) => {
        bins[t] = e;
        bins[lists.length + t] = l.length;
        const ox = x0 + 16 * (t % tilesX) * step, oy = y0 + 16 * Math.floor(t / tilesX) * step;
        for (const s of l) {
            segs[4 * e] = poly[2 * s] - ox;
            segs[4 * e + 1] = poly[2 * s + 1] - oy;
            segs[4 * e + 2] = poly[2 * s + 2] - ox;
            segs[4 * e + 3] = poly[2 * s + 3] - oy;
            if (sv) { sarc[2 * e] = sv[s]; sarc[2 * e + 1] = sv[s + 1]; }
            e++;
        }
    });
    return { segs, sarc, bins, tilesX, entries: E };
}

/** The river's distance (mode 0, capped at maxD) or frame (mode 1: the signed distance and arc length where the far
 * field dc < near) at the points of a uniform grid (xs, ys: doubles): a new rg32f field (kernels/karst/river.wgsl). */
function riverGrid(R, poly, sv, xs, ys, maxD, mode, opts = {}) {
    const step = xs.length > 1 ? xs[1] - xs[0] : 1.0;
    const b = riverBins(poly, sv, xs[0], ys[0], step, xs.length, ys.length, maxD);
    const segs = R.field(1, Math.max(b.entries, 1), 4, b.segs), sarc = R.field(1, Math.max(b.entries, 1), 2, b.sarc);
    const bins = R.field(2, b.bins.length / 2, 1, b.bins, 'u32');
    const out = R.field(ys.length, xs.length, 2);
    R.run(kernelOf(R, 'karst/river'), { segs, sarc, bins, dc: opts.dc ?? Gd.dummies(R).f1 }, { outF: out },
        { uMode: mode, uStepX: step, uStepY: ys.length > 1 ? ys[1] - ys[0] : step, uMax: Number(maxD),
            uNear: Number(opts.near ?? 0.0), uTilesX: b.tilesX });
    for (const f of [segs, sarc, bins]) f.destroy();
    return out;
}

/** The river's frame on a level's subsample grid (karst.py _river_frame_level): { d, s, far } N x N fields (see its
 * doc). */
function riverFrameLevel(R, plan, G, band) {
    let stepf = clip(8.0 * G.cell, Math.max(G.cell, 20.0), Math.max(80.0, G.cell));
    const kf = Math.max(1, pyRound(stepf / G.cell));
    stepf = kf * G.cell;
    const mf = Math.trunc(Math.ceil(G.n / kf)) + 4;
    const jx = Math.floor((G.x0 - 0.5 * G.cell) / stepf) - 1;
    const jy = Math.floor((G.y0 - 0.5 * G.cell) / stepf) - 1;
    const lxf = Float64Array.from({ length: mf }, (_, i) => 0.5 * G.cell + (jx + i) * stepf);
    const lyf = Float64Array.from({ length: mf }, (_, i) => 0.5 * G.cell + (jy + i) * stepf);
    const df = riverGrid(R, plan.river_coarse, null, lxf, lyf, 1500.0, 0);
    const lxc = Float64Array.from({ length: G.n + 2 }, (_, i) => G.x0 + (i - 1 + 0.5) * G.cell);
    const lyc = Float64Array.from({ length: G.n + 2 }, (_, i) => G.y0 + (i - 1 + 0.5) * G.cell);
    const dc = bilinear(R, df, sepAxis(lxf, lxc), sepAxis(lyf, lyc));
    df.destroy();
    const margin = 0.75 * stepf + 2.0 * G.cell;
    const fr = riverGrid(R, plan.river_mid, plan.river_s, lxc, lyc, band + margin + 10.0, 1, { dc, near: band + margin });
    let out;
    if (G.ss === 1) {
        const c = cropAxis(G.n);
        out = { d: bilinear(R, fr, c, c, 0, 0), s: bilinear(R, fr, c, c, 0, 1), far: bilinear(R, dc, c, c) };
    } else {
        const ax = sepAxis(lxc, G.xs), ay = sepAxis(lyc, G.ys);
        out = { d: bilinear(R, fr, ax, ay, 3, 0), s: bilinear(R, fr, ax, ay, 0, 1), far: bilinear(R, dc, ax, ay) };
    }
    fr.destroy();
    dc.destroy();
    return out;
}

/** kernels/karst/towers.wgsl's scalars that numpy keeps in float64 or as float32 scalars of its own rounding: the
 * fluting's depth and 0.55 x its weight sum (Python floats: double-floats, hi and lo), and the talus gate's smoothstep
 * edges as numpy's float32 scalar arithmetic makes them (0.55 * c and 0.55 * c + 0.35 of c = f32(1 - 2 apron_cover)
 * are float32 under NEP 50, and so is their difference, the smoothstep's denominator). */
function towerScalars(pr, cell) {
    const f = Math.fround;
    let wsum = 0.0;
    if (cell <= 2.0 && pr.fluting_m > 0) {
        if (7.0 >= 4.0 * cell) wsum += 0.7;
        if (2.9 >= 4.0 * cell) wsum += 0.3;
    }
    const off = 0.55 * wsum;
    const c = f(1.0 - 2.0 * pr.apron_cover), e0 = f(f(0.55) * c), e1 = f(e0 + f(0.35));
    return { uFluteM: pr.fluting_m, uFluteMl: pr.fluting_m - f(pr.fluting_m), uFluteOff: off, uFluteOffl: off - f(off),
        uGateA: e0, uGateDen: f(e1 - e0) };
}

/** The tables and tile lists kernels/karst/towers.wgsl reads, for the towers whose box meets the level's window
 * (karst.py evaluate's `hit` and boxes, in index order). null when none does. */
export function towerTables(plan, G) {
    const pr = plan.params, N = G.N, sub = G.sub, cell = G.cell, K = plan.K;
    const xe = G.x0 + N * sub, ye = G.y0 + N * sub;
    const hits = [];
    for (let t = 0; t < plan.count; t++) {
        const bodyR = plan.body_h[t] > 0 ? plan.body_R[t] : 0.0;
        let sp = 0.0;
        for (let q = 0; q < 4; q++) sp += hypot(plan.spur[2 * (t * 4 + q)], plan.spur[2 * (t * 4 + q) + 1]);
        const ext = Math.max(plan.R[t], bodyR) * (1.0 + plan.elong[t]) * (1.0 + plan.lean[t] + sp) + plan.reach[t] +
            4.0 * pr.lobes_m + pr.fluting_m + 2.0 * cell;
        const cx = plan.x[t], cy = plan.y[t];
        if (!(cx + ext > G.x0 && cx - ext < xe && cy + ext > G.y0 && cy - ext < ye)) continue;
        const i0 = Math.max(Math.trunc((cx - ext - G.x0) / sub), 0);
        const i1 = Math.min(Math.trunc(Math.ceil((cx + ext - G.x0) / sub)) + 1, N);
        const j0 = Math.max(Math.trunc((cy - ext - G.y0) / sub), 0);
        const j1 = Math.min(Math.trunc(Math.ceil((cy + ext - G.y0) / sub)) + 1, N);
        if (i1 <= i0 || j1 <= j0) continue;
        hits.push([t, i0, i1, j0, j1]);
    }
    if (!hits.length) return null;
    const TW = 13, M = hits.length;
    const tw = new Float32Array(M * TW * 4), ts = new Uint32Array(M * 4), pk = new Float32Array(M * K * 5 * 4);
    let rows = 0;
    for (const [t] of hits) rows += plan.wall_D[t].length;
    // the wall tables in float64 as double-floats, 3 vec4 rows per entry: (D, D0) (Z, numpy's slope over D)
    // (its slope over D0, 0)
    const wt = new Float32Array(rows * 12);
    const ddTo = (a, o, v) => { a[o] = v; a[o + 1] = v - a[o]; };
    const fluteOn = cell <= 2.0 && pr.fluting_m > 0;
    let wr = 0, anyBlock = false, anyRough = false;
    hits.forEach(([t, i0, i1, j0, j1], m) => {
        const o = m * TW * 4, set = (r, a, b, c, d) => { tw[o + 4 * r] = a; tw[o + 4 * r + 1] = b; tw[o + 4 * r + 2] = c; tw[o + 4 * r + 3] = d; };
        const H = plan.H[t], fl = plan.floor[t];
        set(0, plan.x[t] - G.x0, plan.y[t] - G.y0, plan.R[t], H);
        set(1, Math.cos(plan.axis[t]), Math.sin(plan.axis[t]), 1.0 + plan.elong[t], plan.lean[t]);
        set(2, Math.cos(plan.lean_dir[t]), Math.sin(plan.lean_dir[t]), Number.isFinite(fl) ? fl : -1e30, plan.npk[t]);
        const sp = (q) => [plan.spur[2 * (t * 4 + q)], plan.spur[2 * (t * 4 + q) + 1]];
        set(3, ...sp(0), ...sp(1));
        set(4, ...sp(2), ...sp(3));
        const sc = (s) => plan.scarp.subarray(t * 6 + 3 * s, t * 6 + 3 * s + 3);
        const [d0, c0, p0] = sc(0), [d1, c1, p1] = sc(1);
        set(5, Math.cos(d0), Math.sin(d0), c0, Math.max(1.0 - c0, 1e-3));
        set(6, p0 > 0 ? p0 : 0, Math.cos(d1), Math.sin(d1), c1);
        set(7, Math.max(1.0 - c1, 1e-3), p1 > 0 ? p1 : 0, plan.body_h[t] > 0 ? plan.body_h[t] : 0, plan.body_R[t]);
        set(8, plan.body_tan[t], plan.B[t], plan.reach[t], Math.min(pr.brow_m, 0.02 * H));
        let per1 = 0, per2 = 0;
        if (fluteOn) {
            if (7.0 >= 4.0 * cell) per1 = Math.max(pyRound((2 * Math.PI * plan.R[t]) / 7.0), 3);
            if (2.9 >= 4.0 * cell) per2 = Math.max(pyRound((2 * Math.PI * plan.R[t]) / 2.9), 3);
        }
        set(9, wr, plan.wall_D[t].length, per1, per2);
        set(10, i0, i1, j0, j1);
        const talus = plan.B[t] > 0.05 && plan.B[t] > 0.5 * cell;
        set(11, Number.isFinite(fl) ? pr.cap_top * H - fl : 0, pr.floor_rough * H, pr.crown * H, talus ? 1 : 0);
        set(12, pr.floor_rough * plan.body_h[t], pr.crown * plan.body_h[t], t, 0);
        ts[4 * m] = (plan.salt + 401 + 7 * t) >>> 0;
        ts[4 * m + 1] = (plan.salt + 211 + t) >>> 0;
        ts[4 * m + 2] = (plan.salt + 223 + t) >>> 0;
        for (let k = 0; k < K; k++) {
            const i = t * K + k, q = ((m * K + k) * 5) * 4;
            if (k >= plan.npk[t]) continue;
            const pa = plan.pk_axis[i];
            pk.set([plan.pk_dx[i], plan.pk_dy[i], Math.cos(pa), Math.sin(pa), 1.0 + plan.pk_e[i], plan.pk_h[i],
                plan.pk_r0[i], plan.pk_b[i]], q);
            for (let r = 0; r < 6; r++) {
                pk[q + 8 + 2 * r] = plan.pk_rib[2 * (i * 6 + r)];
                pk[q + 8 + 2 * r + 1] = plan.pk_rib[2 * (i * 6 + r) + 1];
            }
        }
        const D = plan.wall_D[t], Z = plan.wall_Z[t], D0 = plan.wall_D0[t];
        const sD = interpSlopes(D, Z), sD0 = interpSlopes(D0, Z);
        for (let r = 0; r < D.length; r++) {
            const o = 12 * wr;
            ddTo(wt, o, D[r]);
            ddTo(wt, o + 2, D0[r]);
            ddTo(wt, o + 4, Z[r]);
            if (r < D.length - 1) {                      // (a zero-width step's slope is never read: numpy's
                ddTo(wt, o + 6, sD[r]);                  // search takes the interval with D[r + 1] > d >= D[r])
                ddTo(wt, o + 8, sD0[r]);
            }
            wr++;
        }
        if (Number.isFinite(fl)) anyBlock = true;
        else if (pr.peak_rough > 0) anyRough = true;
        if (plan.body_h[t] > 0) anyRough = true;
    });
    // the tiles' lists: every hit tower whose box meets the tile, in index order
    const tilesX = Math.ceil(N / 16), tilesY = Math.ceil(N / 16);
    const counts = new Uint32Array(tilesX * tilesY);
    for (const [, i0, i1, j0, j1] of hits) {
        for (let ty = j0 >> 4; ty <= (j1 - 1) >> 4; ty++) for (let tx = i0 >> 4; tx <= (i1 - 1) >> 4; tx++) counts[ty * tilesX + tx]++;
    }
    const bins = new Uint32Array(2 * tilesX * tilesY);
    let e = 0;
    for (let k = 0; k < counts.length; k++) { bins[k] = e; bins[counts.length + k] = counts[k]; e += counts[k]; }
    const list = new Uint32Array(Math.max(e, 1)), fillAt = Uint32Array.from(bins.subarray(0, counts.length));
    hits.forEach(([, i0, i1, j0, j1], m) => {
        for (let ty = j0 >> 4; ty <= (j1 - 1) >> 4; ty++) for (let tx = i0 >> 4; tx <= (i1 - 1) >> 4; tx++) list[fillAt[ty * tilesX + tx]++] = m;
    });
    return { tw, ts, pk, wt, bins, list, tilesX, hits: M, entries: e, anyBlock, anyRough };
}

/** The karst surface on one level (karst.py evaluate): an (n, n) window of `cell`-metre cells whose south-west corner
 * is (x0, y0); each cell the mean of ss x ss subsamples (opts.ss, default supersamplingFor(cell)); opts.fill false
 * leaves the cockpits unfilled. Returns new GPU fields (the caller's): h, bed, deposit (h - bed), talus, water (the
 * river's depth; river is the same field), plain, Sc, and tower_id (r32i: the tower whose wall or summit is the
 * surface at the cell's centre subsample, its body's wall included, a cockpit's soil floor not; -1 elsewhere). */
export async function evaluate(R, plan, x0, y0, cell, n, opts = {}) {
    const pr = plan.params;
    x0 = Number(x0); y0 = Number(y0); cell = Number(cell); n = Math.trunc(n);
    const G = new Grid(x0, y0, cell, n, Math.trunc(opts.ss ?? supersamplingFor(cell)));
    const N = G.N, lim = 2.5 * cell, salt = plan.salt;
    const D = Gd.dummies(R);
    const own = [];                                       // fields to release before returning
    const keep = (f) => { own.push(f); return f; };
    // lobes: a radial displacement in metres (spurs and re-entrants of every footprint)
    const LOB = keep(smoothField(R, G, Math.max(60.0, lim), [term(130.0, salt + 101, 1.0), term(60.0, salt + 102, 0.45)],
        0, { A: pr.lobes_m, B: 0.33 }));
    // the beds' undulation for the summits' benches; a level coarser than a bench takes none
    const BENCH = pr.benches > 0 && pr.bench_m >= 4.0 * cell ?
        keep(smoothField(R, G, Math.max(60.0, lim), fbmTerms(160.0, 2, salt + 161, 0.5), 0, { A: 3.0, B: 0.33 })) : null;
    // the summit cones' gentle distance jitter
    const JAG = keep(smoothField(R, G, Math.max(40.0, lim), fbmTerms(90.0, 2, salt + 131, 0.45, lim), 0, { A: pr.jag, B: 0.3 }));
    // where the walls' ledges hold (1) and where they have broken off (0); a level coarser than 2.5 m takes the mean
    const LEDGE = cell <= 2.5 ? keep(smoothField(R, G, Math.max(8.0, lim), fbmTerms(30.0, 2, salt + 141, 0.5, lim), 1,
        { A: 0.5 - pr.ledge_cover - 0.12, B: 0.5 - pr.ledge_cover + 0.12 })) : null;
    // the knobs' patches: the noise below has a std of about 0.56, so its crown_cover quantile centres the edge
    const cCov = 0.56 * normInvCdf(clip(1.0 - pr.crown_cover, 0.02, 0.98));
    const knobTerms = () => [...fbmTerms(180.0, 2, salt + 151), ...(pr.crown_spacing_m >= 3.0 * cell ? [term(pr.crown_spacing_m, salt + 149)] : [])];
    const knobUn = { A: cCov - 0.3, B: cCov + 0.3, flags: pr.crown_spacing_m >= 3.0 * cell ? 1 : 0 };

    // ---- the plain and the river
    const plain = plainFields(R, plan, G, keep);

    // ---- the common base
    let PM = null;
    if ((pr.plinth_m > 0 || pr.base_m > 0) && plan.count) {
        const rot = { c: plan._cs[0], s: plan._cs[1], st: pr.cluster_stretch };
        const terms = [...fbmTerms(1500.0, 2, salt + 31), ...fbmTerms(300.0, 1, salt + 33), ...fbmTerms(120.0, 1, salt + 37),
            ...fbmTerms(pr.cluster_scale_m, 3, salt + 11, 0.5, 0.0, rot), term(pr.ridge_scale_m, salt + 13, 1.0, rot),
            term(0.5 * pr.ridge_scale_m, salt + 17, 1.0, rot)];
        const river = pr.plinth_m <= 0 && plan.river !== null;
        const d0 = pr.river_width_m * (1.0 + pr.river_width_var) + 80.0;
        PM = keep(smoothField(R, G, pr.plinth_m > 0 ? 8.0 * cell : Math.max(240.0, 8.0 * cell), terms, 3,
            { A: pr.plinth_m + pr.base_m, B: pr.base_rough_m, C: pr.cluster_ridges, D: plan.cluster_threshold,
                E: plan.cluster_band, F: plan.cluster_std, G: d0, flags: (pr.plinth_m > 0 ? 1 : 0) | (river ? 2 : 0) },
            { rd: river ? (lat) => riverGrid(R, plan.river_coarse, null, lat.lx, lat.ly, d0 + 450.0, 0) : null }));
    }

    // ---- towers on the common base (rock heights relative to the plain's level)
    const tt = plan.count ? towerTables(plan, G) : null;
    const RS = keep(R.field(N, N, 2)), OW = keep(R.field(N, N, 1, null, 'i32'));
    if (tt) {
        const rough = tt.anyRough ? [keep(smoothField(R, G, Math.max(22.5, lim), fbmTerms(45.0, 2, salt + 137, 0.5, lim), 0, { A: 1.0, B: 0.3 })),
            keep(smoothField(R, G, Math.max(0.5 * pr.crown_spacing_m, lim), knobTerms(), 2, knobUn))] : [D.f1, D.f1];
        // the blocks' caps: lumps and knobs evaluated at the subsamples themselves (cap_rough)
        const cap = tt.anyBlock ? [keep(worldGrid(R, G.xs, G.ys, fbmTerms(45.0, 2, salt + 137, 0.5, lim), 0, { A: 1.0, B: 0.3 })),
            keep(worldGrid(R, G.xs, G.ys, knobTerms(), 2, knobUn))] : [D.f1, D.f1];
        const axes = new Float32Array(2 * N * 2);
        for (let i = 0; i < N; i++) { axes[2 * i] = G.xs[i] - G.x0; axes[2 * (N + i)] = G.ys[i] - G.y0; }
        const f = { tw: R.field(1, tt.tw.length / 4, 4, tt.tw), ts: R.field(1, tt.ts.length, 1, tt.ts, 'u32'),
            pk: R.field(1, tt.pk.length / 4, 4, tt.pk), wt: R.field(1, Math.max(tt.wt.length / 4, 1), 4, tt.wt.length ? tt.wt : new Float32Array(4)),
            bins: R.field(2, tt.bins.length / 2, 1, tt.bins, 'u32'), list: R.field(1, tt.list.length, 1, tt.list, 'u32'),
            axes: R.field(2, N, 2, axes) };
        R.run(kernelOf(R, 'karst/towers'), { ...f, lob: LOB, jag: JAG, ledge: LEDGE ?? D.f1, bench: BENCH ?? D.f1,
            pm: PM ?? D.f1, rlump: rough[0], rknob: rough[1], clump: cap[0], cknob: cap[1] }, { outR: RS, outO: OW },
        { uTilesX: tt.tilesX, uK: plan.K, uLedge: LEDGE ? 1 : 0, uBench: BENCH ? 1 : 0, uPM: PM ? 1 : 0, uLedgeK: pr.ledge_cover,
            uTanUnder: Math.tan(radians(85.0)), uTanApron: Math.tan(radians(pr.apron_deg)), uPeakRough: pr.peak_rough,
            uBenchK: pr.benches, uBenchM: pr.bench_m, ...towerScalars(pr, cell) });
        for (const x of Object.values(f)) x.destroy();
    } else {
        R.run(kernelOf(R, 'karst/towers'), { tw: rgba1(R), ts: D.u1, pk: rgba1(R), wt: rgba1(R), bins: zeroBins(R, N), list: D.u1,
            axes: D.f2, lob: LOB, jag: JAG, ledge: D.f1, bench: D.f1, pm: PM ?? D.f1, rlump: D.f1, rknob: D.f1, clump: D.f1, cknob: D.f1 },
        { outR: RS, outO: OW }, { uTilesX: Math.ceil(N / 16), uK: plan.K, uLedge: 0, uBench: 0, uPM: PM ? 1 : 0, uLedgeK: pr.ledge_cover,
            uTanUnder: 0, uTanApron: 0, uPeakRough: 0, uBenchK: 0, uBenchM: 1, uFluteM: 0, uFluteMl: 0, uFluteOff: 0,
            uFluteOffl: 0, uGateA: 0, uGateDen: 1 });
    }

    // ---- the composition and the cell means
    const A = keep(R.field(n, n, 4)), B = keep(R.field(n, n, 4)), OC = keep(R.field(n, n, 1, null, 'i32'));
    R.run(kernelOf(R, 'karst/compose'), { plain: plain.P, rs: RS, own: OW }, { outA: A, outB: B, outO: OC },
        { uSS: G.ss, uAlluvium: pr.alluvium_m });

    // ---- the cockpits (any closed basin outside the river; the plan's one floor map inside the main tile)
    const fill = pr.cockpit_fill > 0 && plan.count && (opts.fill ?? true);
    const cells = R.unpack(A, ['h', 'bed', 'talus', 'plain']);
    keep(cells.h);
    let fm = null, fidx = null, lvl = null;
    if (fill) {
        fm = await floorMap(R, plan);
        const fi = new Int32Array(2 * n);
        let all = true;
        for (let i = 0; i < n; i++) {
            const a = Math.floor((x0 + (i + 0.5) * cell - fm.x0) / fm.cell);
            const b = Math.floor((y0 + (i + 0.5) * cell - fm.y0) / fm.cell);
            fi[i] = a >= 0 && a < fm.n ? a : -1;
            fi[n + i] = b >= 0 && b < fm.n ? b : -1;
            if (fi[i] < 0 || fi[n + i] < 0) all = false;
        }
        fidx = keep(R.field(2, n, 1, fi, 'i32'));
        if (!all) {
            const dry = keep(R.field(n, n, 1));
            R.run(kernelOf(R, 'karst/cockpit_dry'), { h: D.f1, water: D.f1, plain: D.f1, B }, { outA: dry }, { uMode: 1 });
            lvl = keep(await cockpitFloors(R, cells.h, cell, pr.cockpit_fill, dry));
        }
    }
    const out = { h: R.field(n, n, 1), water: R.field(n, n, 1), deposit: R.field(n, n, 1), tower_id: R.field(n, n, 1, null, 'i32') };
    R.run(kernelOf(R, 'karst/finish'), { A, B, own: OC, fmap: fm?.field ?? D.f1, fidx: fidx ?? zeroI(R), lvl: lvl ?? D.f1 },
        { outH: out.h, outW: out.water, outD: out.deposit, outT: out.tower_id }, { uFill: fill ? 1 : 0, uOwn: lvl ? 1 : 0 });
    out.bed = cells.bed;
    out.talus = cells.talus;
    out.plain = cells.plain;
    out.river = out.water;
    out.Sc = Gd.fill(R, [n, n], Math.fround(Math.tan(radians(Math.min(pr.sc_deg, 89.5)))));
    for (const f of own) if (!f.destroyed && !Object.values(out).includes(f)) f.destroy();
    return out;
}

// a 1 x 1 rgba32f stand-in, for an rgba32f sampler a dispatch's mode does not read
const RGBA = new WeakMap();
function rgba1(R) {
    let f = RGBA.get(R);
    if (!f) RGBA.set(R, (f = R.field(1, 1, 4)));
    return f;
}

const ZERO_BINS = new WeakMap();
function zeroBins(R, N) {
    const tiles = Math.ceil(N / 16) ** 2;
    let f = ZERO_BINS.get(R);
    if (!f || f.w < tiles) {
        f?.destroy();
        f = R.field(2, tiles, 1, new Uint32Array(2 * tiles), 'u32');
        ZERO_BINS.set(R, f);
    }
    return f;
}
const ZERO_I = new WeakMap();
function zeroI(R) {
    let f = ZERO_I.get(R);
    if (!f) ZERO_I.set(R, (f = R.field(2, 1, 1, new Int32Array([-1, -1]), 'i32')));
    return f;
}

/** The plain and its river on the level's subsamples (karst.py _plain): { P } an N x N rgba32f field of (level,
 * surface, water level, in_channel) (kernels/karst/plain.wgsl). */
function plainFields(R, plan, G, keep) {
    const pr = plan.params, lim = 2.5 * G.cell, N = G.N;
    const [dx0, dy0, side] = plan.domain;
    const cx = dx0 + side / 2, cy = dy0 + side / 2;
    const micro = keep(smoothField(R, G, Math.max(40.0, lim), fbmTerms(160.0, 3, plan.salt + 401, 0.45, lim), 0,
        { A: pr.plain_micro_m, B: 0.3 }));
    const axes = new Float32Array(2 * N * 2);
    for (let i = 0; i < N; i++) { axes[2 * i] = G.xs[i] - cx; axes[2 * (N + i)] = G.ys[i] - cy; }
    const fax = R.field(2, N, 2, axes);
    const P = keep(R.field(N, N, 4));
    const D = Gd.dummies(R);
    if (plan.river === null) {
        R.run(kernelOf(R, 'karst/plain'), { micro, fd: D.f1, fs: D.f1, far: D.f1, rk: rgba1(R), axes: fax }, { outP: P },
            { uRiver: 0, uNK: 1, uTiltK: -pr.plain_tilt_m_per_km / 1000.0, uFx: plan.river_dir[0], uFy: plan.river_dir[1],
                uWater: plan.water_level, uRise: pr.plain_rise_m, uHwMax: 0, uBankH: pr.river_bank_m, uDepth: pr.river_depth_m,
                uBar: pr.bar_m, uCell: G.cell });
        fax.destroy();
        return { P };
    }
    let hwMax = -Infinity;
    for (const v of plan.river_hw) hwMax = Math.max(hwMax, v);
    const band = hwMax + 6.0 * pr.river_bank_m + 60.0;
    const fr = riverFrameLevel(R, plan, G, band);
    const K = plan.river_s.length;
    const rkA = new Float32Array(4 * K);
    for (let k = 0; k < K; k++) { rkA[4 * k] = plan.river_s[k]; rkA[4 * k + 1] = plan.river_hw[k]; rkA[4 * k + 2] = plan.river_kappa[k]; }
    const rk = R.field(1, K, 4, rkA);
    R.run(kernelOf(R, 'karst/plain'), { micro, fd: fr.d, fs: fr.s, far: fr.far, rk, axes: fax }, { outP: P },
        { uRiver: 1, uNK: K, uTiltK: -pr.plain_tilt_m_per_km / 1000.0, uFx: plan.river_dir[0], uFy: plan.river_dir[1],
            uWater: plan.water_level, uRise: pr.plain_rise_m, uHwMax: hwMax, uBankH: pr.river_bank_m, uDepth: pr.river_depth_m,
            uBar: pr.bar_m, uCell: G.cell });
    for (const f of [fr.d, fr.s, fr.far, rk, fax]) f.destroy();
    return { P };
}

/** statistics.NormalDist().inv_cdf(p) (Python's: Wichura's AS241, the same algorithm and coefficients), for the knobs'
 * patch threshold. */
export function normInvCdf(p) {
    const q = p - 0.5;
    if (Math.abs(q) <= 0.425) {
        const r = 0.180625 - q * q;
        const num = (((((((2.5090809287301226727e+3 * r + 3.3430575583588128105e+4) * r + 6.7265770927008700853e+4) * r +
            4.5921953931549871457e+4) * r + 1.3731693765509461125e+4) * r + 1.9715909503065514427e+3) * r +
            1.3314166789178437745e+2) * r + 3.3871328727963666080e+0) * q;
        const den = (((((((5.2264952788528545610e+3 * r + 2.8729085735721942674e+4) * r + 3.9307895800092710610e+4) * r +
            2.1213794301586595867e+4) * r + 5.3941960214247511077e+3) * r + 6.8718700749205790830e+2) * r +
            4.2313330701600911252e+1) * r + 1.0);
        return num / den;
    }
    let r = q <= 0.0 ? p : 1.0 - p;
    r = Math.sqrt(-Math.log(r));
    let x;
    if (r <= 5.0) {
        r = r - 1.6;
        const num = (((((((7.74545014278341407640e-4 * r + 2.27238449892691845833e-2) * r + 2.41780725177450611770e-1) * r +
            1.27045825245236838258e+0) * r + 3.64784832476320460504e+0) * r + 5.76949722146069140550e+0) * r +
            4.63033784615654529590e+0) * r + 1.42343711074968357734e+0);
        const den = (((((((1.05075007164441684324e-9 * r + 5.47593808499534494600e-4) * r + 1.51986665636164571966e-2) * r +
            1.48103976427480074590e-1) * r + 6.89767334985100004550e-1) * r + 1.67638483018380384940e+0) * r +
            2.05319162663775882187e+0) * r + 1.0);
        x = num / den;
    } else {
        r = r - 5.0;
        const num = (((((((2.01033439929228813265e-7 * r + 2.71155556874348757815e-5) * r + 1.24266094738807843860e-3) * r +
            2.65321895265761230930e-2) * r + 2.96560571828504891230e-1) * r + 1.78482653991729133580e+0) * r +
            5.46378491116411436990e+0) * r + 6.65790464350110377720e+0);
        const den = (((((((2.04426310338993978564e-15 * r + 1.42151175831644588870e-7) * r + 1.84631831751005468180e-5) * r +
            7.86869131145613259100e-4) * r + 1.48753612908506148525e-2) * r + 1.36929880922735805310e-1) * r +
            5.99832206555887937690e-1) * r + 1.0);
        x = num / den;
    }
    return q < 0.0 ? -x : x;
}

export const FLOOR_MAP_CELL_M = 10.0;           // the plan's cockpit floor map: the main tile at this cell
export const SLOT_CLOSE_M = 40.0;               // ... its basins found again on the map box-averaged to this ...
export const SLOT_MAX_AREA_M2 = 1.2e5;          // ... and no larger than this

/** The plan's cockpit and polje floors over the main tile, made once per plan and device (karst.py _floor_map):
 * { x0, y0, cell, n, field }. */
export async function floorMap(R, plan) {
    plan._floors ??= new WeakMap();
    let fm = plan._floors.get(R);
    if (fm) return fm;
    const [mx0, my0, ms] = plan.main;
    const n = Math.max(8, pyRound(ms / FLOOR_MAP_CELL_M));
    const cell = ms / n;
    const out = await evaluate(R, plan, mx0, my0, cell, n, { ss: 1, fill: false });
    const dry = R.field(n, n, 1);
    R.run(kernelOf(R, 'karst/cockpit_dry'), { h: out.h, water: out.water, plain: out.plain, B: rgba1(R) }, { outA: dry }, { uMode: 0 });
    const fl = await cockpitFloors(R, out.h, cell, plan.params.cockpit_fill, dry, n);
    const nc = Math.max(8, pyRound(ms / SLOT_CLOSE_M));
    const fl2 = await cockpitFloors(R, out.h, cell, plan.params.cockpit_fill, dry, nc, SLOT_MAX_AREA_M2);
    const field = Cm.stamp(fl, fl2, 'max');
    for (const f of [fl, fl2, dry, ...Object.values(out)]) if (!f.destroyed) f.destroy();
    fm = { x0: mx0, y0: my0, cell, n, field };
    plan._floors.set(R, fm);
    return fm;
}

/** The soil floor of every closed depression deeper than 1 m whose bottom lies where `allowed` (karst.py
 * _cockpit_floors: its doc): a new field of floor levels, -inf elsewhere (apply as max(h, floor)). The depressions are
 * core/prims.js fillDepressions and label on h box-averaged to at most maxCells; the per-basin numbers are integer
 * atomics (kernels/karst/cockpit_stats.wgsl), each basin's level is computed from them on the CPU in doubles (one
 * number per basin), gathered, widened by one coarse cell and spread back over the fine cells. */
export async function cockpitFloors(R, h, cell, share, allowed, maxCells = 320, maxAreaM2 = null) {
    const n = h.h;
    const f = Math.max(1, Math.trunc(Math.ceil(n / maxCells)));
    const m = Math.floor(n / f);
    const P = prims(R), D = Gd.dummies(R);
    if (m < 8) return Gd.fill(R, [n, n], -Infinity);
    const hc = R.field(m, m, 1), al = R.field(m, m, 1);
    R.run(kernelOf(R, 'karst/cockpit_block'), { h, allowed }, { outH: hc, outA: al }, { uF: f });
    const { filled } = await P.fillDepressions(hc);
    const mask = R.field(m, m, 1, null, 'u32');
    const A1 = () => R.field(1, 1, 1, null, 'u32');
    const stats = kernelOf(R, 'karst/cockpit_stats');
    const d1 = [A1(), A1(), A1(), A1(), A1()];
    R.run(stats, { hc, filled, al, lab: D.u1 }, { outM: mask, bot: d1[0], spl: d1[1], area: d1[2], rim: d1[3], atb: d1[4] },
        { uPass: 0, uW: m }, groupsOf(m, m));
    for (const x of d1) x.destroy();
    const { labels, count: k } = await P.label(mask);
    mask.destroy();
    if (k === 0) {
        for (const x of [hc, al, filled, labels]) x.destroy();
        return Gd.fill(R, [n, n], -Infinity);
    }
    const L = k + 1;
    const bot = R.field(1, L, 1, new Uint32Array(L).fill(0xFFFFFFFF), 'u32');
    const spl = R.field(1, L, 1, null, 'u32'), area = R.field(1, L, 1, null, 'u32');
    const rim = R.field(1, L, 1, null, 'u32'), atb = R.field(1, L, 1, null, 'u32');
    const dm = R.field(1, 1, 1, null, 'u32');
    for (const pass of [1, 2]) {
        R.run(stats, { hc, filled, al, lab: labels }, { outM: dm, bot, spl, area, rim, atb }, { uPass: pass, uW: m }, groupsOf(m, m));
    }
    const [b, s, a, r, t] = await R.readAll([bot, spl, area, rim, atb]);
    const cf = cell * f, cf2 = cf * cf;
    const lev = new Float32Array(L).fill(-Infinity);
    for (let l = 1; l < L; l++) {
        const bottom = keyToFloat(b[l]), spill = keyToFloat(s[l]);
        let keep = spill - bottom > 1.0 && t[l] > 0;
        // a basin's soil: share of its depth, and a small one nearly to its spill, easing to `share` at 20 ha
        const ar = a[l] * cf2;
        let sh = share + (0.97 - share) * clip((2e5 - ar) / 1.8e5, 0.0, 1.0);
        // and a narrow one (a slot between two towers' bodies) to its spill, easing to `share` at 150 m
        const width = (2.0 * ar) / Math.max(r[l] * cf, 1e-6);
        sh = Math.max(sh, share + (1.0 - share) * clip((150.0 - width) / 90.0, 0.0, 1.0));
        if (maxAreaM2 !== null) keep = keep && ar <= maxAreaM2;
        if (keep) lev[l] = bottom + Math.max(sh, share) * (spill - bottom);
    }
    const flev = R.field(1, L, 1, lev);
    const fl = R.field(m, m, 1);
    const floor = kernelOf(R, 'karst/cockpit_floor');
    R.run(floor, { lab: labels, lev: flev, fl: D.f1 }, { outF: fl }, { uMode: 0, uF: f, uM: m });
    const wide = P.dilate(fl, 1);                                         // one coarse cell wider
    const out = R.field(n, n, 1);
    R.run(floor, { lab: D.u1, lev: D.f1, fl: wide }, { outF: out }, { uMode: 1, uF: f, uM: m });
    for (const x of [hc, al, filled, labels, bot, spl, area, rim, atb, dm, flev, fl, wide]) x.destroy();
    return out;
}


// ---------------------------------------------------------------- the stage op
const PLANS = new Map();
const DOMAINS = new Map();

/** Clear the per-process memos (karst.py _PLANS and _DOMAINS): the floor protocol's clean start (plan 5.4). */
export function clearMemos() {
    PLANS.clear();
    DOMAINS.clear();
}

const freeze = (v) => (Array.isArray(v) ? v.map(freeze) : v);
/** karst.py _plan_key: (seed, domain to 6 decimals, the full parameters sorted, via and main to 3 decimals). */
export function planKey(seed, domain, params, via, main = null) {
    const full = paramsFor(params);
    const win = (w) => (w === null || w === undefined ? null : w.map((v) => Number(Number(v).toFixed(3))));
    return [Math.trunc(Number(seed)), domain.map((v) => Number(Number(v).toFixed(6))),
        Object.keys(full).sort().map((k) => [k, freeze(full[k])]), win(via), win(main)];
}

/** planKarst, cached per process: every level of one terrain shares one plan (karst.py cached_plan). */
export function cachedPlan(seed, domain, params = null, via = null, main = null) {
    const key = JSON.stringify(planKey(seed, domain, params, via, main));
    if (!PLANS.has(key)) {
        if (PLANS.size >= 8) PLANS.clear();
        PLANS.set(key, planKarst(seed, domain, params, via, main));
    }
    return PLANS.get(key);
}

/** Stage op 'karst' (karst.py op_karst: its doc): writes h, bed, deposit, talus, water (the river) and Sc of one level
 * from the world-space plan. params: the karst parameters, plus optionally domain [x0, y0, side], via [x, y] and main
 * [x0, y0, side]; by default the domain is the window of the coarsest level the op runs on (parent null: levels run
 * coarsest first), via its centre and main its central window of side / 2^depth. Blender's convention
 * op(fields, level, params, seed), with no stage context (opKarst.takesCtx false: the level runner then pulls a child's
 * border band to its parent after the op, as run.py does for op_karst); the runner comes from the fields. */
export async function opKarst(fields, level, params, seed = 0) {
    const get = (k, d = null) => (level[k] ?? d);
    const R = fields.R;
    const x0 = Number(get('x0')), y0 = Number(get('y0')), cell = Number(get('cell')), n = Math.trunc(get('n'));
    const p = { ...params };
    let { domain = null, via = null, main = null } = p;
    delete p.domain;
    delete p.via;
    delete p.main;
    const key = JSON.stringify([Math.trunc(Number(seed)), planKey(seed, [0.0, 0.0, 1.0], p, null)[2]]);
    if (domain === null) {
        if (get('parent') === null || !DOMAINS.has(key)) {
            const side = n * cell;
            const ms = side / 2 ** Math.max(Math.trunc(get('depth', 0) || 0), 0);
            const cx = x0 + 0.5 * side, cy = y0 + 0.5 * side;
            DOMAINS.set(key, [[x0, y0, side], [cx, cy], [cx - 0.5 * ms, cy - 0.5 * ms, ms]]);
        }
        const [d0, via0, main0] = DOMAINS.get(key);
        domain = d0;
        via = via ?? via0;
        main = main ?? main0;
    }
    const plan = cachedPlan(seed, domain, p, via, main);
    const out = await evaluate(R, plan, x0, y0, cell, n);
    // the level is rebuilt, so its own alluvium, cockpit soil, talus and river replace what it inherited
    for (const k of ['h', 'bed', 'deposit', 'talus', 'water', 'Sc']) fields[k] = out[k];
    for (const k of ['plain', 'tower_id']) out[k].destroy();
    return fields;
}

opKarst.takesCtx = false;
export const OPS = { karst: opKarst };
export {
    paramsFor as params_for, coneProfile as cone_profile, wallTable as wall_table, ribHarmonics as rib_harmonics,
    poissonDisc as poisson_disc, planKarst as plan_karst, cachedPlan as cached_plan, opKarst as op_karst,
    supersamplingFor as supersampling_for, scarpSectors as scarp_sectors,
};
