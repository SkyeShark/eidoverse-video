// Port of blender/eidoblend/terrain/solvers/hydro.py at f90c6fc, with the receivers it reads from
// blender/eidoblend/terrain/solvers/fluvial.py (d8_receivers) at f90c6fc.
//
// Hydrology (design section 4.3): lakes, the drainage check, the drainage area the masks read, and the inflow a child
// level receives from its parent.
//
//     import * as HY from './solvers/hydro.js';
//     const { filled } = await HY.fillDepressions(h, { wrap: [false, false], seaLevel: null });   // every cell's spill
//                                                                // level, exact
//     const { filled, nlakes } = await HY.lakes(fields, level, thresholdM, 'lake' | 'sediment',
//         { parent: [parentLevel, parentFields], seaLevel, band, noLake });      // in place, as hydro.py lakes
//     const r = await HY.routingSurface(filled, { wrap, seaLevel });            // filled, tilted across every flat
//     const { A, iterations } = await HY.routeToConvergence(R, r, cell, { A0, A_in });   // route_area to convergence
//     const { A_in, qs_in } = await HY.inflow(parentLevel, parentFields, childLevel, p, surface);  // what crosses into
//                                                                // a child's window
//
//     stage ops (OPS): 'lakes' (params: mode 'lake' | 'sediment', threshold_m) and 'route' (drainage area to
//     convergence). run.js runs both after every level's stages (lakes only on levels a process evolved), so a recipe
//     names them only to change their settings (a glacial overdeepening filled with sediment, say).
//
// Lakes. A closed depression deeper than max(1 m, 0.2 % of the main tile's relief) becomes a lake: flat water at its
// spill level (`water` = depth, metres; build/water.js makes the lake mesh from it), the bed left as it is. With mode
// 'sediment' it is filled to the spill level instead (flat floors; `deposit` records the fill). Shallower pits are
// always filled with sediment: they are the solver's rounding, not landforms. A child level keeps its parent's lakes
// (a lake whose spill lies outside the child's window is still a lake there) and adds its own.
//
// Drainage area. route_area.wgsl iterated on the routing surface (the filled surface with a small tilt across each
// lake and flat toward its outlet, so the water crosses lakes) from the fluvial run's last area, until the largest
// relative change over 128 iterations is under 1e-4. A child's border cells receive the parent's flow that crosses
// its window edge (A_in, m^2; qs_in, m^3/yr): rivers entering the window carry their upstream catchment with them.
//
// Fields are core/gpu.js fields (one float channel; receivers int32, distances and steps u32); every function
// records GPU work and returns new fields the caller owns, and never changes its inputs (lakes changes `fields` in
// place, as hydro.py does). The convergence loop this module names for the dispatch-log comparison (PORT_PLAN.md 5.7):
// routeToConvergence's route_area, tested every `check` (128) iterations (CONVERGENCE_LOOPS). The other loops here
// (the fill, the labels, the breadth-first distances) are core/prims.js relaxations: the port's own kernels, which
// replace numpy code and have no Blender dispatch to match.
//
// Where this differs from hydro.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU; each is
// checked against the numpy function it replaces, tests/hydro/):
//   - fill_depressions, flat_distance, path_steps and lakes' labelling are core/prims.js primitives (exact). info of
//     fill_depressions carries the outlet ('sea', 'edge' or 'lowest basin'), not the number of D8 basins (nothing
//     reads it).
//   - flow_receivers and d8_receivers are one kernel (kernels/hydro/receivers.wgsl): exact for float32 heights (the
//     kernel's header says how numpy's float64 slope comparisons are kept). d8Receivers is exported for the fluvial
//     package's valley floors, which call fluvial.d8_receivers with a breach mask.
//   - _descend runs in the path-maximum form (PORT_PLAN.md C11): the largest key f - s eps on the path to the outlet
//     by pointer jumping, carried with the cell it comes from (kernels/hydro/jump_argmax.wgsl), and the result made
//     from that cell's height as f(q*) + (s - s(q*)) eps, instead of numpy's loop over the steps. The plan's
//     s eps + max cancels on long paths near 0 m (1,262 ulp of a 7e-5 m height on rolling_hills' plain); this form
//     is within 0.9 ulp of numpy's float64 (kernels/hydro/descend.wgsl).
//   - lakes: the per-label maxima and touches are integer atomics (kernels/hydro/lake_labels.wgsl); h and deposit
//     are replaced only when a cell fills, as numpy's `if fill_cells.any()` (one readback of two counts). numpy's
//     float64 sums of float32 heights (deposit + filled - h, ph + pw - h) are exact; the kernels add the values'
//     significands exactly in 64-bit integers and round once (kernels/hydro/lib.wgsl), so the deposit and the
//     parent's lake water are numpy's to the bit where filled - h alone is not a float32 value (a bed below half its
//     spill level). A float two-sum would be cheaper, but this machine's shader compiler reassociates it away.
//   - Where numpy routes a float64 surface that is not float32 everywhere (h + water across a lake: the depth is
//     stored rounded to float32, so the sum misses the spill level by that rounding), the surface is held exactly as
//     float32 pairs (hi, lo) and filled, measured and routed as pairs (kernels/hydro/surface_in.wgsl, fill_pair.wgsl,
//     flat_pair.wgsl; the receivers and the descent read pairs); rounded to float32 first, the lakes' flats came out
//     other than numpy's (canyon's main level: 206 cells of the routing surface whole steps of eps away). The pair
//     fill and flat distance relax one step per dispatch (core/prims.js's sweep tiles), and run only where some lo is
//     not 0; elsewhere core/prims.js runs on the pair's first channel.
//   - inflow is a gather on the child window's edge cells (kernels/hydro/inflow.wgsl), float32 where numpy is
//     float64; _parent_lake_water is one kernel (kernels/hydro/parent_lake_water.wgsl).
//   - route_to_convergence's test reads back 4 bytes (kernels/hydro/converge.wgsl, a GPU maximum of the relative
//     change) instead of the whole field each time; the decision is numpy's, in float32.
//   - route, accumulate, horizon_occlusion, flat_average, neighbour_table and the masks' helpers moved from Ekigar's
//     hydrology have no caller in the Blender package (masks.py runs its own march) and are not ported; box_blur is
//     core/prims.js boxBlur. The route_area twin stays in Python (the oracle, tests/parity/fixtures.py).
//   - Returns are objects ({ filled, info }, { filled, nlakes }, { A, iterations }, { A_in, qs_in }) where hydro.py
//     returns tuples; options are camelCase (seaLevel, maxIter, noLake, seamHold), as the edition's calls are.

import * as Gd from '../core/grid.js';
import { pyRound } from '../core/levels.js';
import { f32AtOrBelow, lineGroups, prims } from '../core/prims.js';

// neighbour offsets (di = column, dj = row) and their distances in texels: common.wgsl's order (SW S SE W E NW N NE)
export const NBR = [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]];
export const DIST = [Math.SQRT2, 1.0, Math.SQRT2, 1.0, 1.0, Math.SQRT2, 1.0, Math.SQRT2];
export const NOWRAP = Object.freeze([false, false]);
export const BOUND_OPEN = 0, BOUND_PERIODIC = 1, BOUND_PINNED = 2;
export const TOL = 1e-4, CHECK = 128;
/** The convergence loops of this module, by kernel (PORT_PLAN.md 5.7): their counts may differ by whole intervals. */
export const CONVERGENCE_LOOPS = Object.freeze({ route_area: CHECK });

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);
const cover = (f) => [Math.ceil(f.w / 16), Math.ceil(f.h / 16), 1];
const wrapUniforms = (wrap) => ({ uWrapX: wrap?.[0] ? 1 : 0, uWrapY: wrap?.[1] ? 1 : 0 });

/** np.spacing(np.float32(x)) for x >= 0: the float32 step above |x|. */
export function spacing32(x) {
    F32[0] = Math.abs(x);
    const f = F32[0];
    U32[0] += 1;
    return F32[0] - f;
}

/** The float32 a u32 holds, bit for bit. */
function bitsToFloat(b) {
    U32[0] = b >>> 0;
    return F32[0];
}

function runnerOf(...fs) {
    for (const f of fs) if (f && f.runner) return f.runner;
    throw new TypeError('hydro: a GPU field (core/gpu.js) is needed');
}

// ================================================================================== lakes and routing ===

/** The design's depth for a closed depression to count (a lake): max(1 m, 0.2 % of the relief). */
export function depressionThreshold(reliefM) {
    return Math.max(1.0, 0.002 * Number(reliefM));
}

// ------------------------------------------------------------------------------- numpy's float64 surfaces ---
// A surface numpy holds in float64 that is not float32 everywhere (h + water across lakes) is an rg32f field of exact
// pairs (hi, lo) (kernels/hydro/lib.wgsl); fillDepressions, flatDistance, the receivers and the descent take such a
// field as numpy takes its float64 array. Where every lo is 0 the pair is a float32 field and core/prims.js runs on
// its first channel as it is; the pair kernels (kernels/hydro/fill_pair.wgsl, flat_pair.wgsl) run only where numpy's
// surface really is not float32. The level runner's grids never wrap, and the pair forms do not.

/** True for an rg32f field of exact pairs with a nonzero lo somewhere (one readback, remembered on the field). */
export async function pairNeeded(f) {
    if (f.channels !== 2) return false;
    if (f._pairNeeded === undefined) f._pairNeeded = (await prims(f.runner).stats(f, { channel: 1 })).nonzero > 0;
    return f._pairNeeded;
}

// the sea level as a pair (hi, lo) of float32: its float32 rounding and the rest of the double, rounded
function seaPair(seaLevel) {
    const hi = Math.fround(seaLevel);
    return [hi, Math.fround(seaLevel - hi)];
}

// dispatch step(src, dst, counted) in chunks until a chunk's last dispatch changes nothing (core/prims.js _relax's
// schedule); the number of dispatches
async function relax(R, pair, counter, step, what, maxDispatches = 1 << 20) {
    let done = 0, chunk = 8;
    for (;;) {
        R.clear(counter);
        for (let i = 0; i < chunk; i++) {
            step(pair.src, pair.dst, i === chunk - 1);
            pair.swap();
        }
        done += chunk;
        const got = await R.readRange(counter, 0, 1);
        if (got[0] === 0) return done;
        if (done >= maxDispatches) throw new Error(`hydro: ${what} not settled after ${done} dispatches`);
        chunk = Math.min(chunk * 2, 64);
    }
}

function noWrap(wrap, what) {
    if (wrap?.[0] || wrap?.[1]) throw new Error(`hydro ${what}: a surface of float64 pairs on a wrapping grid is not ported (the level runner's grids never wrap)`);
}

/** Every cell's spill level (the priority-flood fill), exactly: core/prims.js fillDepressions, hydro.py's
 * fill_depressions (outlets: an open edge, the sea (cells at or below seaLevel), and on a tile periodic on both axes
 * with no sea, the lowest basin). A pair surface (above) gives a pair; else r32f. Returns { filled, info: { outlet,
 * dispatches } } (outlet null for a pair surface: nothing reads it). */
export async function fillDepressions(height, opts = {}) {
    const R = runnerOf(height);
    const wrap = opts.wrap ?? NOWRAP, seaLevel = opts.seaLevel ?? null;
    if (await pairNeeded(height)) {
        noWrap(wrap, 'fillDepressions');
        const W = R.pair(height.h, height.w, 2), counter = R.field(1, 1, 1, null, 'u32');
        const un = { uSea: seaLevel !== null ? 1 : 0, uSea2: seaLevel !== null ? seaPair(seaLevel) : [0, 0], uCount: 0 };
        R.run('hydro/fill_pair', { h: height, win: height }, { outW: W.src, changed: counter }, { ...un, uInit: 1 });
        const dispatches = await relax(R, W, counter, (src, dst, counted) => {
            R.run('hydro/fill_pair', { h: height, win: src }, { outW: dst, changed: counter }, { ...un, uInit: 0, uCount: counted ? 1 : 0 });
        }, 'the fill of a pair surface');
        W.dst.destroy();
        counter.destroy();
        W.src._pairNeeded = true;
        return { filled: W.src, info: { outlet: null, dispatches } };
    }
    const r = await prims(R).fillDepressions(height, { wrap, seaLevel });
    return { filled: r.filled, info: { outlet: r.outlet, dispatches: r.dispatches } };
}

/** Breadth-first steps (8-connected) across every flat of `surface` from where it drains (a cell with a lower
 * neighbour, an open edge, or the sea); 0 off the flats (hydro.py flat_distance). A pair surface as above. A u32
 * field. */
export async function flatDistance(surface, opts = {}) {
    const R = runnerOf(surface);
    const wrap = opts.wrap ?? NOWRAP, seaLevel = opts.seaLevel ?? null;
    if (await pairNeeded(surface)) {
        noWrap(wrap, 'flatDistance');
        const D = R.pair(surface.h, surface.w, 1, null, 'u32'), counter = R.field(1, 1, 1, null, 'u32');
        const un = { uSea: seaLevel !== null ? 1 : 0, uSea2: seaLevel !== null ? seaPair(seaLevel) : [0, 0], uCount: 0 };
        R.run('hydro/flat_pair', { surf: surface, din: D.dst }, { outD: D.src, changed: counter }, { ...un, uInit: 1 });
        await relax(R, D, counter, (src, dst, counted) => {
            R.run('hydro/flat_pair', { surf: surface, din: src }, { outD: dst, changed: counter }, { ...un, uInit: 0, uCount: counted ? 1 : 0 });
        }, 'the flat distance of a pair surface');
        R.run('hydro/flat_pair', { surf: surface, din: D.src }, { outD: D.dst, changed: counter }, { ...un, uInit: 3 });
        D.src.destroy();
        counter.destroy();
        return D.dst;
    }
    return prims(R).flatDistance(surface, { wrap, seaLevel });
}

/** solvers/fluvial.py d8_receivers(h, breach): every cell's steepest strictly-lower neighbour as a row-major index
 * (-1: none: a pit, a flat, or an edge cell with every neighbour higher), common.wgsl's neighbour order. Cells of
 * the mask opts.breach (a float field, nonzero) that have none get their lowest neighbour instead. An int32 field. */
export function d8Receivers(h, opts = {}) {
    const R = runnerOf(h), D = Gd.dummies(R);
    const out = R.field(h.h, h.w, 1, null, 'i32');
    R.run('hydro/receivers', { W: h, dist: D.u1, breach: opts.breach ?? D.f1 }, { outR: out },
        { uMode: 0, uBreach: opts.breach ? 1 : 0, uWrapX: 0, uWrapY: 0 });
    return out;
}

/** Every cell's receiver on a filled (depression-free) surface, as a row-major index (-1: an outlet - an open edge
 * cell or the sea - with no lower neighbour): the steepest strictly lower neighbour (D8), or on a flat the equal
 * neighbour one breadth-first step nearer the flat's drain (flatDistance). Every path ends at an outlet, however gentle
 * the ground (hydro.py flow_receivers). An int32 field. */
export async function flowReceivers(filled, opts = {}) {
    const R = runnerOf(filled), D = Gd.dummies(R);
    const wrap = opts.wrap ?? NOWRAP;
    const dist = await flatDistance(filled, { wrap, seaLevel: opts.seaLevel ?? null });
    const out = R.field(filled.h, filled.w, 1, null, 'i32');
    R.run('hydro/receivers', { W: filled, dist, breach: D.f1 }, { outR: out }, { uMode: 1, uBreach: 0, ...wrapUniforms(wrap) });
    dist.destroy();
    return out;
}

/** The number of receiver steps from every cell to its outlet (list ranking by pointer jumping; hydro.py
 * path_steps). rec: an int32 field of receivers. A u32 field. */
export async function pathSteps(rec) {
    const { steps, terminal } = await prims(runnerOf(rec)).pathSteps(rec);
    terminal.destroy();
    return steps;
}

/** routing_surface's eps for a surface whose largest |height| is `top`: a few float32 steps at that height, never
 * under 2 mm. */
export function routingEps(top) {
    return Math.max(2e-3, 4.0 * spacing32(Math.fround(Math.max(Number(top), 1.0))));
}

/** hydro.py _descend: the filled surface raised along the receiver tree so every cell stands at least eps above its
 * receiver, in the path-maximum form (PORT_PLAN.md C11; kernels/hydro/descend.wgsl). opts.steps: pathSteps(rec), when
 * the caller has it. A new r32f field. */
export async function descend(filled, rec, eps, opts = {}) {
    const R = runnerOf(filled), D = Gd.dummies(R);
    const steps = opts.steps ?? await pathSteps(rec);
    const hi = Math.fround(eps), lo = Math.fround(eps - hi);
    const [h, w] = [filled.h, filled.w];
    const un = { uEpsHi: hi, uEpsLo: lo };
    // the keys and their cells, then the path maximum and its cell by pointer jumping (prims/jump_init's pointers)
    const P = R.pair(h, w, 1, null, 'u32'), K = R.pair(h, w, 1), A = R.pair(h, w, 1, null, 'u32');
    const d0 = R.field(h, w, 1, null, 'u32');
    R.run('prims/jump_init', { rec }, { outP: P.src, outD: d0 }, {});
    d0.destroy();
    R.run('hydro/descend', { f: filled, steps, arg: D.u1 }, { outF: K.src, outA: A.src }, { uMode: 0, ...un });
    const rounds = Math.ceil(Math.log2(Math.max(2, h * w))) + 1;
    for (let r = 0; r < rounds; r++) {
        R.run('hydro/jump_argmax', { ptr: P.src, key: K.src, arg: A.src }, { outP: P.dst, outK: K.dst, outA: A.dst }, {});
        P.swap();
        K.swap();
        A.swap();
    }
    const rs = R.field(h, w, 1), stand = R.field(1, 1, 1, null, 'u32');
    R.run('hydro/descend', { f: filled, steps, arg: A.src }, { outF: rs, outA: stand }, { uMode: 1, ...un });
    for (const x of [P, K, A, stand]) x.destroy();
    if (!opts.steps) steps.destroy();
    return rs;
}

/** The surface the drainage area is routed on: the filled surface, tilted across every flat (lakes, filled pits,
 * dead-flat ground) by eps per step of its breadth-first distance from the outlet, eps a few float32 steps at the
 * surface's height, so a GPU pass in float32 still sees the way down (hydro.py routing_surface). It is built along
 * the receiver tree (flowReceivers: the steepest lower neighbour, or across a flat toward its drain), outlets
 * first: every cell at least eps above its receiver. On a flat that is the breadth-first tilt; it also lifts the
 * cells just over a flat's level at its margin. A new r32f field. */
export async function routingSurface(filled, opts = {}) {
    const s = await prims(runnerOf(filled)).stats(filled);
    const top = s.count ? Math.max(Math.abs(s.min), Math.abs(s.max)) : 0.0;
    const rec = await flowReceivers(filled, opts);
    const rs = await descend(filled, rec, routingEps(top));
    rec.destroy();
    return rs;
}

/** Fill a level's closed depressions (module doc), in place: fields.h, fields.deposit (when a cell fills) and
 * fields.water. Returns { filled (the spill levels of fields.h as it came in: r32f, the caller's), nlakes }.
 * opts.parent: [parent Level, parent Fields] to keep the parent's lakes on this level. opts.band: a child level's
 * border band in cells: a depression reaching into it is filled with sediment, not water. It is the seam's, not a
 * lake: the band holds the parent's smoother channel while the level sharpens its own, so a river crossing the band
 * ponds behind it, and the band's pins undo any fill during the run (filled to its spill it is a short flat reach).
 * The seam's own opts.seamHold (2) cells are never filled, so the level still meets its parent exactly there.
 * opts.noLake: a float field (the flatten areas, compose.flattenMask; a cell counts where it is > 0.5): a depression
 * reaching into it fills with sediment, never water. opts.wrap, opts.seaLevel: as fillDepressions. */
export async function lakes(fields, level, thresholdM, mode = 'lake', opts = {}) {
    const { parent = null, seaLevel = null, wrap = NOWRAP, band = 0, seamHold = 2, noLake = null } = opts;
    const h = fields.h;
    const R = runnerOf(h), P = prims(R), D = Gd.dummies(R);
    const { filled } = await fillDepressions(h, { wrap, seaLevel });
    const depth = R.like(h), mask = R.field(h.h, h.w, 1, null, 'u32');
    R.run('hydro/lake_depth', { filled, h }, { outD: depth, outM: mask }, { uMin: f32AtOrBelow(1e-4) });
    const { labels, count: n } = await P.label(mask);
    mask.destroy();
    let water = null, nlakes = 0;
    if (n) {
        const maxd = P.list(n + 1), touch = P.list(n + 1), big = P.list(n + 1);
        const cBig = R.field(1, 1, 1, null, 'u32'), cFill = R.field(1, 1, 1, null, 'u32');
        R.run('hydro/lake_labels', { lab: labels, depth, nolake: noLake ?? D.f1 }, { maxd, touch },
            { uBand: Math.trunc(band), uNoLake: noLake ? 1 : 0 }, cover(h));
        R.run('hydro/lake_big', { maxd, touch }, { big, count: cBig }, { uCount: n + 1, uThr: f32AtOrBelow(Number(thresholdM)) },
            lineGroups(n + 1));
        const hasDep = 'deposit' in fields && fields.deposit != null;
        const outH = R.like(h), outW = R.like(h), outDep = R.like(h);
        R.run('hydro/lake_apply', { h, filled, depth, lab: labels, big, deposit: hasDep ? fields.deposit : D.f1 },
            { outH, outW, outDep, count: cFill },
            { uLake: mode === 'lake' ? 1 : 0, uBand: Math.trunc(band), uHold: Math.trunc(seamHold), uDeposit: hasDep ? 1 : 0 });
        cBig.name = 'lakes_big';
        cFill.name = 'lakes_fill';
        const [nb, nf] = await R.readAll([cBig, cFill]);
        nlakes = mode === 'lake' ? nb[0] : 0;
        if (nf[0] > 0) {
            fields.h = outH;
            fields.deposit = outDep;
        } else {
            outH.destroy();
            outDep.destroy();
        }
        water = outW;
        for (const f of [maxd, touch, big, cBig, cFill]) f.destroy();
    }
    labels.destroy();
    depth.destroy();
    if (water === null) water = Gd.fill(R, [h.h, h.w], 0.0);
    if (parent !== null && parent[1]?.water) {
        const w2 = parentLakeWater(level, fields.h, parent[0], parent[1], water);
        water.destroy();
        water = w2;
    }
    fields.water = water;
    return { filled, nlakes };
}

/** Water depth on this level under the parent's lakes, combined with `water` (this level's own; zeros when null)
 * as lakes() combines them: each parent lake cell (grown by one cell) is at its lake level, and child cells under it
 * lower than that level hold water (hydro.py _parent_lake_water). h: the child's height. A new r32f field. */
export function parentLakeWater(level, h, plevel, pfields, water = null) {
    const R = runnerOf(h);
    const own = water === null;
    const w0 = own ? Gd.fill(R, [h.h, h.w], 0.0) : water;
    const out = R.like(h);
    if (!pfields.water) {
        R.copy(w0, out);
    } else {
        const i0 = pyRound((level.x0 - plevel.x0) / plevel.cell), j0 = pyRound((level.y0 - plevel.y0) / plevel.cell);
        const f = pyRound(plevel.cell / level.cell);
        R.run('hydro/parent_lake_water', { h, water: w0, ph: pfields.h, pw: pfields.water }, { outW: out },
            { uOrigin: [i0, j0], uF: f, uMin: f32AtOrBelow(1e-6) });
    }
    if (own) w0.destroy();
    return out;
}

/** { A_in (m^2), qs_in (m^3/yr) } on a child level's grid (r32f fields): the parent's drainage area and sediment flux
 * that cross into the child's window, put on the child's edge cells where they enter (each parent cell's inflow
 * shared by the child cells of its f x f block that lie on the window's edge; hydro.py inflow). `surface`: the
 * parent's routing surface (default its fill_depressions'd, tilted h). */
export async function inflow(plevel, pfields, level, p = 1.0, surface = null) {
    const R = runnerOf(pfields.h, pfields.A, surface);
    const n = Math.trunc(level.n);
    const A_in = R.field(n, n, 1), qs_in = R.field(n, n, 1);
    if (!pfields.A) return { A_in, qs_in };
    let r = surface;
    if (!r) {
        const { filled } = await fillDepressions(pfields.h);
        r = await routingSurface(filled);
        filled.destroy();
    }
    const pc = Number(plevel.cell);
    const i0 = pyRound((level.x0 - plevel.x0) / pc), j0 = pyRound((level.y0 - plevel.y0) / pc);
    const m = pyRound(level.side / pc), f = pyRound(pc / level.cell);
    const D = Gd.dummies(R);
    R.run('hydro/inflow', { r, A: pfields.A, qs: pfields.qs ?? D.f1 }, { outA: A_in, outQ: qs_in },
        { uOrigin: [i0, j0], uM: m, uF: f, uQs: pfields.qs ? 1 : 0, uP: Number(p), uLs: 1.0 * pc, uLd: Math.SQRT2 * pc });
    if (r !== surface) r.destroy();
    return { A_in, qs_in };
}

// ========================================================================== drainage area on the device ===

/** Drainage area (m^2, an r32f field) on a fixed surface: route_area iterated from A0 (default one cell's area)
 * until the largest relative change over `check` iterations is under tol (hydro.py route_to_convergence). R: the
 * runner (core/gpu.js; hydro.py's device). opts: A0, A_in (r32f fields; read, never changed), bound (0 open), p
 * (1), tol (1e-4), check (128), maxIter (8 x the larger side). Returns { A (the caller's), iterations }. */
export async function routeToConvergence(R, surface, cell, opts = {}) {
    const { A0 = null, A_in = null, bound = BOUND_OPEN, p = 1.0, tol = TOL, check = CHECK } = opts;
    const ny = surface.h, nx = surface.w;
    const un = { uDx: Number(cell), uP: Number(p), uBound: Math.trunc(bound) };
    const W = R.field(ny, nx, 1);
    R.run('flow_weights', { st: surface }, { outW: W }, un);
    const pin = A_in ? R.pack({ A_in }, [null, null, 'A_in', null]) : R.field(ny, nx, 4);
    let src;
    if (A0) {
        src = R.like(A0);
        R.copy(A0, src);
    } else {
        src = Gd.fill(R, [ny, nx], Math.fround(Number(cell) * Number(cell)));
    }
    let dst = R.field(ny, nx, 1);
    const prev = R.like(src);
    R.copy(src, prev);
    const counter = R.field(1, 1, 1, null, 'u32');
    counter.name = 'route_change';
    const maxIter = Math.trunc(opts.maxIter || 8 * Math.max(ny, nx));
    const route = R.kernel('route_area'), test = R.kernel('hydro/converge');
    let it = 0;
    while (it < maxIter) {
        for (let k = 0; k < check; k++) {
            R.run(route, { st: surface, wsumT: W, aT: src, pin }, { outA: dst }, un);
            const t = src;
            src = dst;
            dst = t;
        }
        it += check;
        R.clear(counter);
        R.run(test, { cur: src, prev }, { outC: counter }, {}, cover(src));
        const got = await R.readRange(counter, 0, 1);
        const change = bitsToFloat(got[0]);
        R.copy(src, prev);
        if (change < tol) break;
    }
    for (const f of [W, pin, dst, prev, counter]) f.destroy();
    return { A: src, iterations: it };
}

// =================================================================================================== the ops ===

/** Stage 'lakes': fill the level's closed depressions now (module doc). params: mode 'lake' | 'sediment',
 * threshold_m (default: the design's max(1 m, 0.2 % of relief)). */
export async function opLakes(fields, level, params, seed = 0, ctx = null) {
    let rel = ctx ? ctx.shared?.relief : null;
    if (!rel) {
        const s = await prims(runnerOf(fields.h)).stats(fields.h);
        rel = s.max - s.min;
    }
    const thr = Number(params.threshold_m || depressionThreshold(rel));
    const mode = params.mode ?? 'lake';
    const { filled } = await lakes(fields, level, thr, mode, { seaLevel: ctx ? ctx.sea_level ?? null : null });
    filled.destroy();
    if (ctx) (ctx.shared.lake_modes ??= {})[level.index] = mode;
    return fields;
}

/** Stage 'route': the drainage area A to convergence on the lake-filled surface (module doc). */
export async function opRoute(fields, level, params, seed = 0, ctx = null) {
    const R = ctx?.device ?? runnerOf(fields.h);
    const sea = ctx ? ctx.sea_level ?? null : null;
    const { filled } = await fillDepressions(fields.h, { seaLevel: sea });
    const r = await routingSurface(filled, { seaLevel: sea });
    filled.destroy();
    const A_in = ctx && ctx.pins ? ctx.pins.A_in : null;
    const { A } = await routeToConvergence(R, r, level.cell, { A0: fields.A ?? null, A_in, tol: Number(params.tol ?? TOL) });
    r.destroy();
    fields.A = A;
    return fields;
}

export const OPS = { lakes: opLakes, route: opRoute };

export {
    depressionThreshold as depression_threshold, fillDepressions as fill_depressions, flatDistance as flat_distance,
    flowReceivers as flow_receivers, pathSteps as path_steps, routingSurface as routing_surface,
    routeToConvergence as route_to_convergence, d8Receivers as d8_receivers,
};
