// Port of blender/eidoblend/terrain/run.py at f90c6fc, with the stage context run.py makes, from
// blender/eidoblend/terrain/solvers/fluvial.py (StageContext, window_relief, _main_window) at f90c6fc.
//
// The level runner (design sections 2.2-2.6, 4.1-4.3): every level of a plan, coarsest first.
//
//     import * as RUN from './run.js';
//     const fields = await RUN.runLevels(plan, recipe, values, stages, { seed: 7, flatten: [...], seaLevel: null,
//         baseElevationM: 800.0, log: console.log, cache: true, info: {} });    // [Fields], one per level (api.js)
//
// Per level:
//   1. its start: the coarsest level from nothing (h = bed = 0); every other level its parent's fields upsampled x2
//      (core/fields.js inherit: h and bed Catmull-Rom, the rest bilinear; U, K, Sc, G, K_factor, Sc_factor and the
//      pins are per-level inputs and never inherited);
//   2. pins: the coarsest level's outer ring is base level (the fluvial stage holds it); a child's border band (16
//      cells) ramps from its parent's surface at the edge to free at 16 cells in, and the parent's drainage area and
//      sediment flux that cross the window edge enter on the child's edge cells (solvers/hydro.js inflow);
//   3. the stages that select the level, in recipe order. The coarsest level first grows coarse-to-fine through its
//      pre-passes (256, 512 ... cells, each upsampled into the next) when an evolving stage (fluvial, creep, talus,
//      threshold, uplift - any op whose function has evolves = true) selects it; a constructional op (a cone, a DEM,
//      a crater) runs once, on the first pass; a post op (post = true: valley floors, soil hillslopes - shaping what
//      the erosion made) runs once, on the last pass. The first defaults.grow_levels levels (default 1, the coarsest
//      only) GROW (role 'grow': uplift and the full physics); the rest refine. A recipe with a wide context grows its
//      outer levels coarse (the far ranges or hills to the horizon) and its inner context levels at their own cells,
//      each starting from its parent and pinned to it at the border, so the landform near the tile is still grown at
//      the cell it was tuned at. Ops that take ctx get a StageContext (below); the wave-1 convention
//      op(fields, level, params, seed) is called as is, and on a child level its height is then pulled to the
//      parent's in the border band. A stage's `where` limits it: the fields it changed are blended with what they
//      were by the mask (masks.js names, or field names);
//   4. the end stages: on a level a process evolved, closed depressions become lakes (or sediment, with the recipe's
//      defaults.lakes = 'sediment'; false skips them), keeping the parent's lakes; a depression reaching into a
//      child's border band, or into a flatten area (a rigid block during erosion, which can lag its surroundings into
//      a hollow; api.js levels it afterwards), fills with sediment instead; then on every level the drainage area A
//      is routed to convergence across the lakes (the masks read it).
//
// The cache: each level's fields are written under the terrain cache (core/cache.js root) as lv_<key>/, the key
// covering everything that decides levels 0..i (stages, knob values, seed, the plan up to i, flatten, sea level, the
// code that makes fields). Moving only the focus re-runs only the hero levels; api.js caches the finished terrain on
// top.
//
// The stage context. StageContext is the counterpart of solvers/fluvial.py's (Blender defines it there because the
// fluvial package wrote the runner's first ops); here it lives with the runner that makes it, and solvers/fluvial.js
// re-exports it, so every op module imports one class without a cycle through the recipes. Its members keep
// Blender's names (ctx.sea_level, ctx.base_elevation_m, ctx.grow_levels, ctx.last_grow, ctx.main, ctx.depth), the
// names tests/parity/replay.mjs's dumped contexts carry. ctx.device is the GPU runner (core/gpu.js); the port has no
// twin device (the numpy twins stay the oracles, in Python). windowRelief and mainWindow (fluvial.py window_relief
// and _main_window, which the runner calls for the relief) are here for the same reason.
//
// The dispatch log (PORT_PLAN.md 5.7). The runner names its work in core/gpu.js's context, as the Blender parity
// hooks name Blender's (tests/parity/_hooks.py): op '<runner>' between ops and the op's name inside one; call, the op
// call's index in the run (0, 1, ...); level and pass, set as each pass's StageContext is made; prepass; end, 'lakes'
// and 'route' around the end stages' lakes and drainage routing. After the run op is '<after>'.
//
// Where this differs from run.py, and why:
//   - runLevels is async (GPU readbacks and file reading are) and takes one options object: seed, flatten, seaLevel,
//     baseElevationM, log, cache, info, runner (the core/gpu.js runner; default G.init()), and two the parity tests
//     use, where Blender's hooks wrap module attributes from outside (an ES module's bindings cannot be replaced):
//     getOp, the op lookup (default the registry's, recipes/index.js), and trace(event, payload), awaited with a
//     stage's where mask ('where'), at the end stages ('lakes_before', 'lakes_after', 'route_before', 'route_after',
//     with the level's fields, the fill, the routing surface, the inflow and the area) and when a level is done
//     ('level').
//   - Ops may be async (the port's file reading and readbacks are): the runner awaits each. An op takes a StageContext
//     when its function declares a parameter named `ctx` (or a rest parameter), Blender's inspect.signature test, or
//     sets fn.takesCtx; it receives it as a fifth argument (Python passes ctx=...).
//   - Every per-cell step is a GPU kernel (PORT_PLAN.md 3.2): the pin weights (their band ramp computed once in doubles
//     as numpy does), the inflow, the band pull, the where blend (kernels/hydro/); the end stages are solvers/hydro.js.
//     The fields stay on the GPU (core/fields.js); a pass's fields are released when the next pass inherits them, a
//     level's pins after its end stages, and a level's routing surface once its child has its inflow.
//   - window_relief's percentiles are core/prims.js exact selections on the main window's cells (numpy 2.3.4's float64
//     arithmetic for float64 data, as window_relief's np.asarray(h, np.float64) is).
//   - The routing-surface inputs h + water and max(filled, h + water) are float32 (kernels/hydro/surface_in.wgsl:
//     numpy's exact float64 sum rounded once; solvers/hydro.js names where that can differ).
//   - The level key's JSON is JavaScript's sorted JSON over the port's own code hash (core/cache.js), as core/cache.js
//     keys are: the two editions' keys are never compared.
//   - A `where` that names a mask (not a field) needs masks.js (the masks package); until it is in the checkout the
//     stage raises naming it. The recipes' `where`s so far name fields an earlier op wrote (volcano_far, trough_rho).

import { createHash } from 'node:crypto';
import * as Ch from './core/cache.js';
import * as CO from './core/compose.js';
import * as E from './core/expr.js';
import { Fields } from './core/fields.js';
import * as G from './core/gpu.js';
import * as Gd from './core/grid.js';
import { KeyError, pyReprValue, pyStr } from './core/levels.js';
import { prims } from './core/prims.js';
import * as HY from './solvers/hydro.js';

export const LEVEL_INPUTS = Object.freeze(['U', 'K', 'Sc', 'G', 'K_factor', 'Sc_factor', 'pin_w', 'pin_h']);
export const SKIP = Object.freeze(Object.fromEntries(LEVEL_INPUTS.map((k) => [k, 'skip'])));
export const EVOLVING = Object.freeze(new Set(['uplift', 'fluvial', 'creep', 'talus', 'threshold']));
export const RUN_VERSION = 1;
export const SEAM_HOLD = 2;                // cells at a child's edge held exactly on its parent's surface
const SHAREABLE = ['uplift', 'U_factor', 'relief', 'fluvial_log', 'lake_modes'];

const HERE = new URL('./', import.meta.url);
const now = () => performance.now() / 1000;
const round2 = (s) => Math.round(s * 100) / 100;
const round3 = (s) => Math.round(s * 1000) / 1000;


// ---------------------------------------------------------------------------------------------------- ops ---

let REGISTRY = null;

async function registry() {
    REGISTRY = REGISTRY ?? await import(new URL('recipes/index.js', HERE).href);
    return REGISTRY;
}

/** The function behind stage op `name` (recipes/index.js getOp); a KeyError when it is not registered. */
export async function getOp(name) {
    return (await registry()).getOp(name);
}

async function opAttr(getOpFn, name, attr) {
    try {
        return Boolean((await getOpFn(name))?.[attr] ?? false);
    } catch (e) {
        if (e instanceof KeyError) return false;
        throw e;
    }
}

/** Whether a stage's op evolves the level (EVOLVING, or its function's `evolves`). */
export async function evolves(opName, getOpFn = getOp) {
    if (EVOLVING.has(opName)) return true;
    return opAttr(getOpFn, opName, 'evolves');
}

/** A post op shapes what the level's erosion made (valley floors, soil hillslopes): once, on the last pass. */
export async function post(opName, getOpFn = getOp) {
    return opAttr(getOpFn, opName, 'post');
}

/** The stage labels a run skipped because their op is not registered (from runLevels' info record). */
export function skippedStages(info) {
    const out = [];
    for (const rec of (info ?? {}).levels ?? []) for (const s of rec.skipped ?? []) if (!out.includes(s)) out.push(s);
    return out;
}

// the parameter names of a function, from its source text (inspect.signature's job); null when it has no text
function paramNames(fn) {
    let s;
    try {
        s = Function.prototype.toString.call(fn);
    } catch (_e) {
        return null;
    }
    if (/^\s*class\b/.test(s)) return null;
    const bare = /^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*=>/.exec(s);
    if (bare) return [bare[1]];
    const open = s.indexOf('(');
    if (open < 0) return null;
    const names = [];
    let depth = 0, item = '', quote = null;
    for (let i = open + 1; i < s.length; i++) {
        const c = s[i];
        if (quote) {
            if (c === '\\') { item += c + s[++i]; continue; }
            if (c === quote) quote = null;
            item += c;
            continue;
        }
        if (c === '"' || c === "'" || c === '`') { quote = c; item += c; continue; }
        if (c === '(' || c === '[' || c === '{') depth++;
        if (c === ')' || c === ']' || c === '}') {
            if (depth === 0) { names.push(item); break; }
            depth--;
        }
        if (c === ',' && depth === 0) { names.push(item); item = ''; continue; }
        item += c;
    }
    return names.map((x) => x.trim().split('=')[0].trim()).filter(Boolean);
}

/** Whether an op takes a StageContext (run.py _takes_ctx): fn.takesCtx when it is set, else a parameter named ctx
 * or a rest parameter in its declaration. */
export function takesCtx(fn) {
    if (typeof fn?.takesCtx === 'boolean') return fn.takesCtx;
    const names = paramNames(fn);
    if (names === null) return false;
    return names.includes('ctx') || names.some((n) => n.startsWith('...'));
}


// ------------------------------------------------------------------------------------------- the context ---

/** What the runner tells a stage about where it runs (solvers/fluvial.py StageContext; ops called without one get
 * standalone defaults from the fluvial package).
 *
 *     plan, index      the level stack and this level's index; level is the grid being run (a pre-pass of the
 *                      coarsest level is that level at fewer cells)
 *     prepass          the pre-pass number (0, 1, ...) or null for the level's own cells
 *     fresh            true when nothing was inherited: the stage makes the start (the coarsest level's first pass)
 *     role             'grow' on the coarsest level and its pre-passes (and on the next grow_levels - 1 levels),
 *                      'refine' below
 *     pins             { pin_w, pin_h, A_in, qs_in }: GPU fields of the level's shape, the border band and the
 *                      parent's inflow
 *     shared           an object carried from level to level (the uplift shape and its peak, the controller's U
 *                      factor, the relief)
 *     grow_levels      how many levels, from the coarsest, grow (the recipe's defaults.grow_levels, default 1)
 *     device           the GPU runner (core/gpu.js)
 *     evolved          false; a stage that moves material sets it: the runner then fills lakes
 *
 * new StageContext({ plan, index, level, prepass, fresh, role, pins, shared, seed, sea_level, base_elevation_m,
 * flatten, device, log, values, grow_levels }): Blender's keyword names; a missing one takes Blender's default. */
export class StageContext {
    constructor(o = {}) {
        this.plan = o.plan ?? null;
        this.index = o.index ?? 0;
        this.level = o.level ?? null;
        this.prepass = o.prepass ?? null;
        this.fresh = o.fresh ?? true;
        this.role = o.role ?? 'grow';
        this.pins = o.pins ?? null;
        this.shared = o.shared ?? {};
        this.seed = o.seed ?? 0;
        this.sea_level = o.sea_level ?? null;
        this.base_elevation_m = o.base_elevation_m ?? 0.0;
        this.flatten = o.flatten || [];
        this.device = o.device ?? null;
        this.log = o.log || ((m) => console.log(m));
        this.values = o.values || {};
        this.grow_levels = Math.max(1, Math.trunc(Number(o.grow_levels || 1)));
        this.evolved = false;
    }

    /** True on the finest growing level (after it the levels refine), on its own cells (not a pre-pass). */
    get last_grow() {
        return this.role === 'grow' && this.prepass === null &&
            this.index === Math.min(this.grow_levels, (this.plan || [0]).length) - 1;
    }

    get main() {
        if (this.plan && this.plan.length) for (const lv of this.plan) if (lv.role === 'main') return lv;
        return this.level;
    }

    /** Levels below the main level count negative (hero), above positive (context): Level.depth. */
    get depth() {
        return this.plan && this.plan.length ? (this.plan[this.index]?.depth ?? 0) : 0;
    }
}


// ------------------------------------------------------------------------------------------- the relief ---

/** [j0, j1, i0, i1]: the cells of `level` inside the main tile's window (all of it when there is none)
 * (fluvial.py _main_window). */
export function mainWindow(level, main) {
    if (!main) return [0, level.n, 0, level.n];
    const i0 = Math.trunc(Math.max(0, Math.floor((main.x0 - level.x0) / level.cell)));
    const j0 = Math.trunc(Math.max(0, Math.floor((main.y0 - level.y0) / level.cell)));
    const i1 = Math.trunc(Math.min(level.n, Math.ceil((main.x0 + main.side - level.x0) / level.cell)));
    const j1 = Math.trunc(Math.min(level.n, Math.ceil((main.y0 + main.side - level.y0) / level.cell)));
    return [j0, j1, i0, i1];
}

/** The relief of the main tile's cells of a level: percentile 99.9 minus percentile 0.1 (fluvial.py window_relief:
 * numpy's float64 percentiles of the float32 heights, from exact order statistics). */
export async function windowRelief(h, level, main) {
    const [j0, j1, i0, i1] = mainWindow(level, main);
    const R = h.runner, P = prims(R);
    const win = R.field(j1 - j0, i1 - i0, 1);
    R.run('hydro/crop', { src: h }, { outF: win }, { uOrigin: [i0, j0] });
    const hi = await P.percentile(win, 99.9, { dtype: 'float64' });
    const lo = await P.percentile(win, 0.1, { dtype: 'float64' });
    win.destroy();
    return hi - lo;
}

function mainOf(plan) {
    for (const lv of plan) if (lv.role === 'main') return lv;
    return plan[plan.length - 1];
}


// --------------------------------------------------------------------------------------------------- pins ---

/** A child level's pins: the border band holding the inherited surface, weight 1 on the outer SEAM_HOLD cells (so
 * the slopes either side of the seam are the parent's: a river crossing the edge otherwise cut its sharper channel up
 * to the edge, a 6-8 degree jump in single cells), easing to 0 at band cells in (C1); and the parent's inflow on the
 * edge cells. { pin_w, pin_h, A_in, qs_in }: new r32f fields the caller owns (run.py child_pins). */
export async function childPins(lv, hStart, parentLevel, parentFields, parentSurface, seaLevel = null, p = 1.0) {
    const R = hStart.runner;
    const band = Math.trunc(lv.band);
    // the ramp by edge distance d, as numpy computes it per cell (float64, then float32), until it reaches 0
    const span = Math.max(band - SEAM_HOLD, 1);
    const ramp = [];
    for (let d = 0; d <= SEAM_HOLD + span; d++) {
        const t = Math.min(Math.max((d - SEAM_HOLD) / span, 0.0), 1.0);
        ramp.push(Math.fround(1.0 - t * t * (3.0 - 2.0 * t)));
    }
    const table = R.field(1, ramp.length, 1, Float32Array.from(ramp));
    const n = Math.trunc(lv.n);
    const pin_w = R.field(n, n, 1), pin_h = R.field(n, n, 1);
    R.run('hydro/child_pins', { h: hStart, ramp: table }, { outW: pin_w, outH: pin_h },
        { uRamp: ramp.length, uSea: seaLevel !== null ? 1 : 0, uSea32: seaLevel !== null ? Math.fround(seaLevel) : 0.0 });
    table.destroy();
    const { A_in, qs_in } = await HY.inflow(parentLevel, parentFields, lv, p, parentSurface);
    return { pin_w, pin_h, A_in, qs_in };
}

/** A legacy op's height pulled to the parent's in the border band (what the GPU stages do every step), in place
 * (run.py _band_pull). */
export function bandPull(fields, pins) {
    if (pins === null || pins === undefined || !('h' in fields)) return;
    const R = fields.h.runner, D = Gd.dummies(R);
    const hasBed = 'bed' in fields;
    const outH = R.like(fields.h), outB = hasBed ? R.like(fields.bed) : R.field(1, 1, 1);
    R.run('hydro/band_pull', { h: fields.h, bed: hasBed ? fields.bed : D.f1, pinW: pins.pin_w, pinH: pins.pin_h },
        { outH, outB }, { uBed: hasBed ? 1 : 0 });
    fields.h = outH;
    if (hasBed) fields.bed = outB;
    else outB.destroy();
}


// ------------------------------------------------------------------------------------------------- where ---

async function optionalModule(rel) {
    const url = new URL(rel, HERE);
    try {
        Deno.statSync(url);
    } catch (_e) {
        return null;
    }
    return await import(url.href);
}

/** A stage's `where` expression evaluated on a level: field names read the fields, anything else is a mask
 * (masks.js, computed from the current fields). clip(..., 0, 1): a new r32f field, or a number for an expression of
 * numbers alone (run.py where_mask returns a 0-d array then, which no field's shape matches). */
export async function whereMask(expr, fields, level, maskParams = null) {
    const names = [...expr.names()];
    const need = names.filter((n) => !(n in fields));
    let got = {};
    if (need.length) {
        const M = await optionalModule('masks.js');
        if (!M) {
            throw new KeyError(`where ${expr}: no field ${pyStr(need)} on ${level}, and the masks package of the port ` +
                '(eidoverse/terrain/masks.js) is not in this checkout yet');
        }
        got = await M.compute(fields, { cell: level.cell, x0: level.x0, y0: level.y0, names: need, params: maskParams });
        const missing = need.filter((n) => !(n in got));
        if (missing.length) throw new KeyError(`where ${expr}: no field or mask ${pyStr(missing)} on ${level}`);
    }
    const env = Object.fromEntries(names.map((n) => [n, n in fields ? fields[n] : got[n]]));
    const clipped = E.parse(`clamp(${expr}, 0, 1)`);
    let m;
    try {
        m = await clipped.eval(env, { kernelName: 'where' });
    } finally {
        for (const v of Object.values(got)) if (v && typeof v === 'object' && v.runner && !v.destroyed) v.destroy();
    }
    return typeof m === 'number' ? Math.min(Math.max(m, 0.0), 1.0) : m;
}

/** run.py _blend: every field of `fields` of the mask's shape blended with what it was (`before`; 0 for a field
 * the stage made) by the mask, in place. */
export function blend(before, fields, m) {
    if (typeof m === 'number') return;
    const R = m.runner, D = Gd.dummies(R);
    for (const k of Object.keys(fields)) {
        const cur = fields[k];
        if (!cur || cur.h !== m.h || cur.w !== m.w) continue;
        const old = k in before ? before[k] : null;
        const out = R.like(cur);
        R.run('hydro/blend', { old: old ?? D.f1, cur, m }, { outF: out }, { uOld: old ? 1 : 0 });
        fields[k] = out;
    }
}


// ------------------------------------------------------------------------------------------------- cache ---

/** The cache key of level i (run.py _level_key): 'lv_' + SHA-1 of everything that decides levels 0..i. */
export function levelKey(plan, i, stages, values, seed, flatten, seaLevel, baseElevationM, lakesMode, device = 'gpu', growN = 1) {
    const payload = { v: RUN_VERSION, plan: plan.slice(0, i + 1).map((lv) => lv.toDict()), stages: stages.map((s) => s.toDict()),
        values, seed: Math.trunc(seed), flatten, sea: seaLevel, base: baseElevationM, lakes: lakesMode, device,
        code: Ch.codeHash(), grow: Math.trunc(growN) };
    return 'lv_' + createHash('sha1').update(Ch.sortedJson(Ch.plain(payload))).digest('hex');
}

function shareable(shared) {
    return Object.fromEntries(Object.entries(shared).filter(([k]) => SHAREABLE.includes(k)));
}


// ------------------------------------------------------------------------------------- routing surfaces ---

// kernels/hydro/surface_in.wgsl: h + water (filled null), or max(filled, h + water); a new field
function surfaceInput(h, water, filled = null) {
    const R = h.runner, D = Gd.dummies(R);
    const out = R.like(h);
    R.run('hydro/surface_in', { h, water: water ?? D.f1, filled: filled ?? D.f1 }, { outF: out },
        { uMode: filled ? 1 : 0, uWater: water ? 1 : 0 });
    return out;
}

/** The routing surface of a level: its lakes as their flat water, every depression filled, flats tilted (run.py
 * _surface). A new r32f field. */
export async function levelSurface(fields, seaLevel) {
    const water = 'water' in fields ? fields.water : null;
    const h = water ? surfaceInput(fields.h, water) : fields.h;
    const { filled } = await HY.fillDepressions(h, { seaLevel });
    if (h !== fields.h) h.destroy();
    const rs = await HY.routingSurface(filled, { seaLevel });
    filled.destroy();
    return rs;
}

async function ptp(f) {
    const s = await prims(f.runner).stats(f);
    return s.max - s.min;
}


// --------------------------------------------------------------------------------------------- the runner ---

/** Every level's Fields, coarsest first (module doc). opts: seed (0), flatten ([]), seaLevel (null), baseElevationM
 * (0), log (console.log), cache (true), info (an object to receive the run's record: per level seconds, stages,
 * passes, lakes, route iterations), runner (core/gpu.js; default G.init()), getOp (the op lookup; default the
 * registry's). */
export async function runLevels(plan, recipe, values, stages, opts = {}) {
    const seed = opts.seed ?? 0, seaLevel = opts.seaLevel ?? null, baseElevationM = opts.baseElevationM ?? 0.0;
    const log = opts.log ?? ((m) => console.log(m));
    const cache = opts.cache ?? true;
    const getOpFn = opts.getOp ?? getOp;
    const trace = opts.trace ?? null;
    const R = opts.runner ?? await G.init();
    const flatten = [...(opts.flatten ?? [])];
    const defaults = { ...(recipe?.defaults ?? {}) };
    const lakesMode = 'lakes' in defaults ? defaults.lakes : 'lake';
    const growN = Math.max(1, Math.trunc(Number(defaults.grow_levels ?? 1) || 1));
    const maskParams = null;
    let shared = {};
    const out = [];
    const record = opts.info ?? {};
    record.levels = [];
    const surfaces = {};
    const tAll = now();
    const ctxG = G.context;
    Object.assign(ctxG, { op: '<runner>', call: null, level: null, pass: null, prepass: null, end: null });
    let call = -1;
    try {
        const sel = stages.map((st) => st.select(plan, log));
        for (let i = 0; i < plan.length; i++) {
            const lv = plan[i];
            const t0 = now();
            const mine = stages.filter((_st, s) => sel[s].includes(i));
            let key = null, C = null;
            if (cache) {
                key = levelKey(plan, i, stages, values, seed, flatten, seaLevel, baseElevationM, lakesMode, 'gpu', growN);
                C = new Ch.Cache(key);
                if (C.complete()) {
                    const f = await C.loadLevel(0, lv, R);
                    const meta = C.readMeta() ?? {};
                    shared = { ...(meta.shared ?? {}) };
                    out.push(f);
                    surfaces[i] = await levelSurface(f, seaLevel);
                    const rec = { ...(meta.record ?? {}), cache: 'hit', seconds: round2(now() - t0) };
                    record.levels.push(rec);
                    log(`[terrain.run] level ${i} ${lv}: cache hit (${rec.seconds} s)`);
                    if (lv.parent !== null && lv.parent !== undefined && surfaces[lv.parent]) {
                        surfaces[lv.parent].destroy();
                        delete surfaces[lv.parent];
                    }
                    continue;
                }
            }
            let evolving = false;
            for (const st of mine) {
                if (await evolves(st.op, getOpFn)) {
                    evolving = true;
                    break;
                }
            }
            const subs = i === 0 && lv.prepass.length && evolving ? [...lv.prepass.map((m) => lv.withCells(m)), lv] : [lv];
            const parent = lv.parent !== null && lv.parent !== undefined ? out[lv.parent] : null;
            let fields, pins;
            if (parent === null) {
                fields = new Fields(subs[0], { h: 0.0, bed: 0.0 }, R);
                pins = null;
            } else {
                fields = parent.inherit(lv, { rules: SKIP });
                pins = await childPins(lv, fields.h, plan[lv.parent], parent, surfaces[lv.parent] ?? null, seaLevel);
                // only this level (its parent's one child) reads the parent's routing surface
                if (surfaces[lv.parent]) {
                    surfaces[lv.parent].destroy();
                    delete surfaces[lv.parent];
                }
            }
            let evolved = false;
            const stageRec = [], skipped = [];
            for (let k = 0; k < subs.length; k++) {
                const sub = subs[k];
                if (k > 0) {
                    const next = fields.inherit(sub, { rules: SKIP });
                    fields.dispose();
                    fields = next;
                }
                const ctx = new StageContext({ plan, index: i, level: sub,
                    prepass: subs.length > 1 && k < subs.length - 1 ? k : null, fresh: parent === null && k === 0,
                    role: parent === null || i < growN ? 'grow' : 'refine', pins, shared, seed, sea_level: seaLevel,
                    base_elevation_m: baseElevationM, flatten, device: R, log, values, grow_levels: growN });
                Object.assign(ctxG, { level: i, pass: k, prepass: ctx.prepass });
                for (const st of mine) {
                    const isPost = await post(st.op, getOpFn);
                    if (isPost && k < subs.length - 1) continue;
                    if (k > 0 && !(await evolves(st.op, getOpFn)) && !isPost) continue;
                    if (st.params.enabled === false) continue;
                    let fn;
                    try {
                        fn = await getOpFn(st.op);
                    } catch (e) {
                        if (!(e instanceof KeyError)) throw e;
                        if (k === 0) {
                            skipped.push(st.label);
                            log(`[terrain.run] level ${i}: stage ${pyReprValue(st.label)} skipped: op ${pyReprValue(st.op)} is not ` +
                                'registered (its package has not landed)');
                        }
                        continue;
                    }
                    const ts = now();
                    const before = st.whereExpr !== null && st.whereExpr !== undefined ? fields.copy() : null;
                    const withCtx = takesCtx(fn);
                    call += 1;
                    Object.assign(ctxG, { op: st.op, call, end: null });
                    try {
                        if (withCtx) await fn(fields, sub, st.params, seed, ctx);
                        else await fn(fields, sub, st.params, seed);
                    } finally {
                        ctxG.op = '<runner>';
                    }
                    if (!withCtx && parent !== null) bandPull(fields, pins);
                    if (before !== null) {
                        const m = await whereMask(st.whereExpr, fields, sub, maskParams);
                        if (trace) await trace('where', { index: i, level: sub, call, mask: m });
                        blend(before, fields, m);
                        if (typeof m !== 'number') m.destroy();
                        before.dispose();
                    }
                    stageRec.push({ stage: st.label, cells: sub.n, seconds: round3(now() - ts) });
                }
                evolved = evolved || ctx.evolved;
            }
            if (!('h' in fields)) throw new Error(`level ${i} (${lv}) has no height after its stages`);
            if (parent === null && !('relief' in shared)) shared.relief = await windowRelief(fields.h, lv, mainOf(plan));
            // the end stages: lakes on evolved levels, then the drainage area to convergence on every level
            const te = now();
            let nlakes = 0, surf;
            if (evolved && lakesMode) {
                const thr = HY.depressionThreshold(shared.relief || await ptp(fields.h));
                let noLake = null;
                if (flatten.length) {
                    const areas = flatten.filter((f) => f.radius !== null && f.radius !== undefined)
                        .map((f) => ({ at: f.at, radius: f.radius ?? 10.0, falloff: f.falloff ?? 0.0 }));
                    if (areas.length) noLake = CO.flattenMask(R, areas, lv);
                }
                if (trace) await trace('lakes_before', { index: i, level: lv, fields, threshold: thr });
                ctxG.end = 'lakes';
                let res;
                try {
                    res = await HY.lakes(fields, lv, thr, lakesMode === 'sediment' ? 'sediment' : 'lake',
                        { parent: parent !== null ? [plan[lv.parent], parent] : null, seaLevel, band: parent !== null ? lv.band : 0, noLake });
                } finally {
                    ctxG.end = null;
                }
                nlakes = res.nlakes;
                if (trace) await trace('lakes_after', { index: i, level: lv, fields, filled: res.filled, nlakes });
                if (noLake) noLake.destroy();
                const top = surfaceInput(fields.h, fields.water, res.filled);
                res.filled.destroy();
                surf = await HY.routingSurface(top, { seaLevel });
                top.destroy();
            } else {
                surf = await levelSurface(fields, seaLevel);
            }
            const A0 = 'A' in fields ? fields.A : null, A_in = pins !== null ? pins.A_in : null;
            if (trace) await trace('route_before', { index: i, level: lv, fields, surface: surf, A0, A_in });
            ctxG.end = 'route';
            let routed;
            try {
                routed = await HY.routeToConvergence(R, surf, lv.cell, { A0, A_in });
            } finally {
                ctxG.end = null;
            }
            if (trace) await trace('route_after', { index: i, level: lv, A: routed.A, iterations: routed.iterations });
            fields.A = routed.A;
            surfaces[i] = surf;
            if (!('qs' in fields)) fields.new('qs');
            if (trace) await trace('level', { index: i, level: lv, fields });
            const rec = { level: String(lv), role: lv.role, passes: subs.length, stages: stageRec, skipped, lakes: nlakes,
                route_iterations: routed.iterations, end_seconds: round2(now() - te), seconds: round2(now() - t0),
                cache: cache ? 'miss' : 'off' };
            record.levels.push(rec);
            log(`[terrain.run] level ${i} ${lv}: ${mine.length} stages` + (subs.length > 1 ? ` over ${subs.length} passes` : '') +
                `, lakes ${nlakes}, route ${routed.iterations} it, ${rec.seconds} s`);
            out.push(fields);
            if (pins !== null) {                        // released, unless an op keeps one among the level's fields
                const held = new Set(Object.values(fields));
                for (const f of Object.values(pins)) if (!f.destroyed && !held.has(f)) f.destroy();
            }
            if (cache && key !== null) {
                await C.saveLevel(0, fields);
                C.writeMeta({ levels: 1, level: lv.toDict(), shared: Ch.plain(shareable(shared)), record: Ch.plain(rec) });
            }
        }
        record.seconds = round2(now() - tAll);
        record.shared = Ch.plain(shareable(shared));
        return out;
    } finally {
        for (const s of Object.values(surfaces)) if (!s.destroyed) s.destroy();
        Object.assign(ctxG, { op: '<after>', call: null, level: null, pass: null, prepass: null, end: null });
    }
}

export {
    runLevels as run_levels, skippedStages as skipped_stages, getOp as get_op, childPins as child_pins,
    bandPull as band_pull, whereMask as where_mask, windowRelief as window_relief, levelKey as level_key,
};
