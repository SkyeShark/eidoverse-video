// The level runner against the Blender edition's own runs (PORT_PLAN.md 8.2 row P5, 5.1, 5.3, 5.7): run.js runLevels
// over a floor run's plan and stages (tests/parity/blender_chaos_floor.py's base runs), with every op replaced by
// Blender's own result for that call (the call's `after` dump), so that what happens between and after the ops is
// the port's alone, and is compared with Blender's at every step:
//   calls      the sequence of op calls (op, level, pass, the window, params, seed) equal to Blender's: the stage
//              selection, the coarse-to-fine pre-passes, post and evolving ops, the skipped stages
//   context    every StageContext a ctx op receives (index, prepass, fresh, role, sea level, base, flatten,
//              grow_levels, values, shared) equal to the one Blender's op received
//   inputs     the fields each op receives against its `before` dump: the inheritance (Catmull-Rom and bilinear x2),
//              the pins (pin_w bit for bit, pin_h, the inflow A_in and qs_in), the band pull after a legacy op, the
//              where blend; grade max(1e-5 of the field's range, 16 float32 steps of its largest value); the inflow
//              at the drainage area's 1e-4 of its range: it is made from the parent's routed area and surface, which
//              carry the route's own difference (tests/hydro/hydro_test.mjs holds inflow itself to 1e-6 on Blender's
//              inputs)
//   end stages the fields before and after lakes (h, water, deposit and the fill bit for bit, the lake count), the
//              routing surface (within 3 float32 steps of Blender's float32 surface: 2 from numpy's float64, C11, and
//              Blender's own rounding), the area's start and inflow, the drainage area after convergence (1e-4 of its
//              range) and its iterations (equal, or one test interval apart)
//   dispatches the runner's own dispatch log (op '<runner>': the end stages' flow_weights and route_area) against
//              Blender's (tests/parity/dispatch_parity.mjs), level by level
//   seams      every child against its parent (the Blender fluvial package's judge_fields.seams): |dh| on the edge
//              ring <= 0.05 m, the slope jump on the two outer rings <= 3 degrees
//   twice      (--twice) the whole run again: every field of every level bit for bit, the dispatch logs equal
//   cache      (--cache) the run with the level cache on, into tests/out/hydro/cache_test/ (EIDO_TERRAIN_THREEJS_CACHE),
//              then again: every level a hit, no op called, every field bit for bit the first run's
// Blender's op attributes (evolves, post, takes ctx) and each recipe's resolved stages come from
// tests/hydro/blender_ops.py (run it first with Blender's Python).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/hydro/runner_test.mjs
//         [--recipes rolling_hills,real_place,...] [--seeds 1,2] [--twice] [--real dem] [--out <name>]
//     (on a shared machine, behind $EIDO_GPU_WRAP; --real <ops> runs the port's own op for those names instead)
//
// Writes tests/out/hydro/<out | runner_test>.json. JavaScript per cell here is test code.

import { Fields } from '../../core/fields.js';
import * as G from '../../core/gpu.js';
import * as Gd from '../../core/grid.js';
import { KeyError } from '../../core/levels.js';
import { Stage } from '../../core/recipe.js';
import * as RUN from '../../run.js';
import * as HY from '../../solvers/hydro.js';
import * as C from '../parity/_common.mjs';
import * as DP from '../parity/dispatch_parity.mjs';
import * as RP from '../parity/replay.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const flag = (n) => args.includes(n);
const RECIPES = (opt('--recipes') ?? 'rolling_hills,real_place,canyon,stratovolcano,sea_cliffs,dunes').split(',');
const SEEDS = (opt('--seeds') ?? '1').split(',').map(Number);
const TWICE = flag('--twice');
const CACHE = flag('--cache');
const REAL = new Set((opt('--real') ?? '').split(',').filter(Boolean));
const OUT = opt('--out') ?? 'runner_test';

const T = new C.Checks('hydro: the level runner on the Blender floor runs');
const R = await G.init();
const opsFile = `${W.TESTS}/out/hydro/blender_ops.json`;
const BOPS = C.readJson(opsFile);
if (!BOPS) {
    console.log(`[skip] no ${opsFile}: make it with <Blender's python> -I eidoverse/terrain/tests/hydro/blender_ops.py`);
    Deno.exit(2);
}
const registry = REAL.size ? await import('../../recipes/index.js') : null;
const results = { runs: [] };

// ------------------------------------------------------------------------------------------------- helpers ---

const sameJson = (a, b) => JSON.stringify(sortKeys(a)) === JSON.stringify(sortKeys(b));
function sortKeys(v) {
    if (Array.isArray(v)) return v.map(sortKeys);
    if (v && typeof v === 'object' && !ArrayBuffer.isView(v)) return Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])]));
    return v;
}
function bitsEqual(a, b) {
    if (a.length !== b.length) return false;
    const x = new Uint32Array(a.buffer, a.byteOffset, a.length), y = new Uint32Array(b.buffer, b.byteOffset, b.length);
    for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return false;
    return true;
}
function ulps(got, want) {
    let worst = 0, over = 0;
    for (let i = 0; i < want.length; i++) {
        const e = Math.abs(got[i] - want[i]) / (C.ulp32(want[i]) || 1e-45);
        if (e > worst) worst = e;
        if (e > 3) over++;
    }
    return { worst, over };
}
// 2-D float32 arrays of a level's shape in a dump: { name: Float32Array }
function levelArrays(arrays, n, prefix = '') {
    const out = {};
    for (const [k, a] of Object.entries(arrays)) {
        if (prefix && !k.startsWith(prefix)) continue;
        if (!prefix && (k.startsWith('pin__') || k.startsWith('shared__'))) continue;
        if (a.dtype === '<f4' && a.shape.length === 2 && a.shape[0] === n && a.shape[1] === n) out[k.slice(prefix.length)] = a.data;
    }
    return out;
}
// the port's fields (GPU) against Blender's arrays: { ok, names, fields: { name: { exact, over, ok } } }
async function compareFields(fields, want, opts = {}) {
    const mine = Object.keys(fields).filter((k) => fields[k] && fields[k].kind === 'f32').sort();
    const theirs = Object.keys(want).sort();
    const out = { ok: true, names: sameJson(mine, theirs), mine: mine.join(','), theirs: theirs.join(','), fields: {} };
    if (!out.names) out.ok = false;
    const both = theirs.filter((k) => mine.includes(k));
    const got = await R.readAll(both.map((k) => fields[k]));
    both.forEach((k, i) => {
        const exact = bitsEqual(got[i], want[k]);
        const g = C.gradeArray(got[i], want[k], { k: opts.k?.[k] ?? opts.kAll ?? 1e-5, m: 16, uses: opts.uses?.[k] });
        const ok = exact || (opts.exact?.includes(k) ? false : g.ok);
        out.fields[k] = { exact, over: +g.over.toPrecision(3), ok };
        if (!ok) out.ok = false;
    });
    return out;
}
const summary = (cmp) => Object.entries(cmp.fields).filter(([, f]) => !f.exact).map(([k, f]) => `${k} ${C.sci(f.over, 2)}`).join(', ');

// ------------------------------------------------------------------------------------------------ one run ---

async function runOnce(dir, recipeName, logDir, cache = false) {
    const run = await RP.loadRun(dir);
    const res = BOPS.recipes[recipeName];
    const stages = res.stages.map((d) => Stage.fromDict(d));
    const plan = run.levels;
    const n0 = (i) => plan[i].n;
    const rec = { recipe: recipeName, dir, calls: [], ends: [], problems: [] };
    const problem = (m) => { if (rec.problems.length < 60) rec.problems.push(m); };
    let next = 0;
    const fns = new Map();
    const replay = async (name, fields, level, params, seed, ctx) => {
        const st = run.stages[next++];
        const row = { call: G.context.call, op: name };
        rec.calls.push(row);
        if (!st) { problem(`call ${G.context.call}: ${name} is one call more than Blender's ${run.stages.length}`); return; }
        // the call itself
        const where = { op: st.op, level: st.level, pass: st.pass_index, call: st.call, n: st.window.n, x0: st.window.x0, y0: st.window.y0, cell: st.window.cell };
        const mine = { op: name, level: G.context.level, pass: G.context.pass, call: G.context.call, n: level.n, x0: level.x0, y0: level.y0, cell: level.cell };
        row.same_call = sameJson(where, mine);
        if (!row.same_call) problem(`call ${st.call}: Blender ran ${JSON.stringify(where)}, the port ${JSON.stringify(mine)}`);
        row.same_params = sameJson(st.params, params) && st.seed === seed;
        if (!row.same_params) problem(`call ${st.call} ${name}: params or seed differ`);
        row.same_ctx = true;
        if (st.takes_ctx !== (ctx !== undefined && ctx !== null)) { row.same_ctx = false; problem(`call ${st.call} ${name}: takes_ctx ${st.takes_ctx}, the port passed ${ctx ? 'one' : 'none'}`); }
        if (ctx && st.context) {
            const c = st.context;
            const a = { index: c.index, prepass: c.prepass, fresh: c.fresh, role: c.role, sea_level: c.sea_level, base_elevation_m: c.base_elevation_m,
                flatten: c.flatten, grow_levels: c.grow_levels, values: c.values, shared: c.shared };
            const b = { index: ctx.index, prepass: ctx.prepass, fresh: ctx.fresh, role: ctx.role, sea_level: ctx.sea_level,
                base_elevation_m: ctx.base_elevation_m, flatten: ctx.flatten, grow_levels: ctx.grow_levels, values: ctx.values,
                shared: JSON.parse(JSON.stringify(ctx.shared)) };
            row.same_ctx = sameJson(a, b);
            if (!row.same_ctx) {
                const diff = Object.keys(a).filter((k) => !sameJson(a[k], b[k]));
                problem(`call ${st.call} ${name}: the context differs in ${diff.join(', ')}: ${diff.map((k) => `${JSON.stringify(a[k]).slice(0, 120)} vs ${JSON.stringify(b[k]).slice(0, 120)}`).join(' | ')}`);
            }
        }
        // the fields it receives: inherited, pinned, pulled, blended by the port
        const before = await RP.npz(`${run.dir}/stages/${st.before}`);
        const cmp = await compareFields(fields, levelArrays(before, level.n));
        row.inputs = { ok: cmp.ok, inexact: summary(cmp) };
        if (!cmp.ok) problem(`call ${st.call} ${name} L${st.level} p${st.pass_index}: inputs ${cmp.names ? '' : `names ${cmp.mine} vs ${cmp.theirs}; `}${summary(cmp)}`);
        if (ctx && ctx.pins) {
            const pw = levelArrays(before, level.n, 'pin__');
            const pins = {};
            for (const k of Object.keys(pw)) pins[k] = ctx.pins[k];
            const pc = await compareFields(pins, pw, { k: { A_in: 1e-4, qs_in: 1e-4 }, uses: { A_in: ['divide'], qs_in: ['divide'] }, exact: ['pin_w'] });
            row.pins = { ok: pc.ok, inexact: summary(pc) };
            if (!pc.ok) problem(`call ${st.call} ${name} L${st.level}: pins ${pc.names ? '' : `names ${pc.mine} vs ${pc.theirs}; `}${summary(pc)}`);
        }
        // the op's result: Blender's (or the port's own op with --real)
        if (REAL.has(name)) {
            const fn = await registry.getOp(name);
            if (RUN.takesCtx(fn)) await fn(fields, level, params, seed, ctx);
            else await fn(fields, level, params, seed);
            const after = await RP.npz(`${run.dir}/stages/${st.after}`);
            const ac = await compareFields(fields, levelArrays(after, level.n), { kAll: 1e-4 });
            row.real = { ok: ac.ok, inexact: summary(ac) };
            if (!ac.ok) problem(`call ${st.call} ${name}: the port's op against Blender's result: ${summary(ac)}`);
        } else {
            const after = levelArrays(await RP.npz(`${run.dir}/stages/${st.after}`), level.n);
            for (const k of Object.keys(fields)) if (!(k in after)) delete fields[k];
            for (const [k, a] of Object.entries(after)) fields[k] = a;
        }
        if (ctx) {
            ctx.evolved = Boolean(st.evolved);
            for (const k of Object.keys(ctx.shared)) delete ctx.shared[k];
            Object.assign(ctx.shared, structuredClone(st.shared_after ?? {}));
        }
    };
    const getOp = async (name) => {
        const a = BOPS.ops[name];
        if (!a) throw new KeyError(`no op '${name}' in the Blender edition's registry`);
        if (!fns.has(name)) {
            const fn = async (fields, level, params, seed, ctx) => replay(name, fields, level, params, seed, ctx);
            fn.evolves = a.evolves;
            fn.post = a.post;
            fn.takesCtx = a.takes_ctx;
            fns.set(name, fn);
        }
        return fns.get(name);
    };
    // the end stages, against Blender's dumps of the same level
    const ends = Object.fromEntries(run.endStages.map((e) => [`${e.level} ${e.stage}`, e]));
    const trace = async (event, p) => {
        const n = n0(p.index);
        const e = { event, level: p.index };
        rec.ends.push(e);
        if (event === 'lakes_before' || event === 'lakes_after') {
            const d = ends[`${p.index} lakes`];
            if (!d) { e.ok = false; problem(`L${p.index}: the port ran lakes, Blender did not`); return; }
            const arrays = await RP.npz(`${run.dir}/stages/${event === 'lakes_before' ? d.before : d.after}`);
            const want = levelArrays(arrays, n);
            delete want.filled;
            const cmp = await compareFields(p.fields, want, event === 'lakes_after' ? { exact: ['h', 'water', 'deposit'] } : {});
            e.ok = cmp.ok;
            e.inexact = summary(cmp);
            if (event === 'lakes_after') {
                const f = await R.read(p.filled);
                const f64 = arrays.filled.data;
                let differ = 0;
                for (let i = 0; i < f64.length; i++) if (f[i] !== f64[i]) differ++;
                e.filled_differ = differ;
                e.nlakes = [p.nlakes, d.nlakes];
                e.threshold = d.thr;
                if (differ || p.nlakes !== d.nlakes) e.ok = false;
            } else {
                e.threshold = [p.threshold, d.thr];
                if (Math.abs(p.threshold - d.thr) > 1e-12 * Math.abs(d.thr)) { e.ok = false; problem(`L${p.index}: the lakes threshold ${p.threshold} against Blender's ${d.thr}`); }
            }
            if (!e.ok) problem(`L${p.index} ${event}: ${cmp.names ? '' : `names ${cmp.mine} vs ${cmp.theirs}; `}${e.inexact} ${e.filled_differ ? `fill ${e.filled_differ} cells` : ''} ${JSON.stringify(e.nlakes ?? '')}`);
        } else if (event === 'route_before') {
            const d = ends[`${p.index} route`];
            if (!d) { e.ok = false; problem(`L${p.index}: no route dump`); return; }
            const arrays = await RP.npz(`${run.dir}/stages/${d.before}`);
            const s = await R.read(p.surface);
            const u = ulps(s, arrays.surf.data);
            e.surface_worst_ulp = +u.worst.toFixed(3);
            e.surface_cells_over_3_ulp = u.over;
            e.surface_bit_equal = bitsEqual(s, arrays.surf.data);
            const pa = {};
            if (p.A0) pa.A0 = p.A0;
            if (p.A_in) pa.A_in = p.A_in;
            const want = {};
            for (const k of ['A0', 'A_in']) if (arrays[k]) want[k] = arrays[k].data;
            const cmp = await compareFields(pa, want, { k: { A_in: 1e-4 }, uses: { A_in: ['divide'] } });
            e.inputs = summary(cmp);
            e.ok = u.over === 0 && cmp.ok;
            if (!e.ok) problem(`L${p.index} route_before: surface worst ${u.worst.toFixed(2)} ulp, ${u.over} cells over 3; ${cmp.names ? '' : `names ${cmp.mine} vs ${cmp.theirs}; `}${e.inputs}`);
        } else if (event === 'route_after') {
            const d = ends[`${p.index} route`];
            const arrays = await RP.npz(`${run.dir}/stages/${d.after}`);
            const a = await R.read(p.A);
            const g = C.gradeArray(a, arrays.A.data, { k: 1e-4, uses: ['pow', 'divide'] });
            e.A_over = +g.over.toPrecision(3);
            e.iterations = [p.iterations, d.iterations];
            e.ok = g.ok && Math.abs(p.iterations - d.iterations) <= HY.CHECK && (p.iterations - d.iterations) % HY.CHECK === 0;
            if (!e.ok) problem(`L${p.index} route_after: A ${C.sci(g.over)} of range, iterations ${p.iterations} against ${d.iterations}`);
        } else if (event === 'where') {
            const st = run.stages[p.call];
            if (!st?.where_mask) { e.ok = false; problem(`call ${p.call}: the port made a where mask, Blender did not`); return; }
            const want = (await RP.npz(`${run.dir}/stages/${st.where_mask}`)).where.data;
            const got = typeof p.mask === 'number' ? new Float32Array(want.length).fill(p.mask) : await R.read(p.mask);
            let worst = 0;
            for (let i = 0; i < want.length; i++) worst = Math.max(worst, Math.abs(got[i] - want[i]));
            e.call = p.call;
            e.worst = worst;
            e.ok = worst <= 1e-5;
            if (!e.ok) problem(`call ${p.call}: the where mask ${C.sci(worst)} from Blender's`);
        } else if (event === 'level') {
            e.ok = true;
        }
    };
    let log = null;
    if (logDir) log = new RP.PortLog(G, logDir, { snapshots: false, mainLevel: run.header.main_index }).start();
    const info = {};
    const lines = [];
    const t0 = performance.now();
    let fields, error = null;
    try {
        fields = await RUN.runLevels(plan, { defaults: run.header.defaults }, run.header.values, stages,
            { seed: run.header.seed, flatten: run.header.flatten, seaLevel: run.header.sea_level, baseElevationM: run.header.base_elevation_m,
                log: (m) => lines.push(m), cache, info, runner: R, getOp, trace });
    } catch (e) {
        error = `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 4).join('\n')}`;
    }
    if (log) await log.stop();
    rec.seconds = +((performance.now() - t0) / 1000).toFixed(2);
    rec.error = error;
    if (next !== run.stages.length && !error) problem(`the port made ${next} op calls, Blender ${run.stages.length}`);
    rec.op_calls = [next, run.stages.length];
    rec.info = info;
    rec.log = lines;
    return { run, rec, fields };
}

// ---------------------------------------------------------------------------------------------- the seams ---

/** The Blender fluvial package's judge_fields.seams on the port's levels: each child against its parent. */
async function seams(plan, fields) {
    const rows = [];
    for (let i = 1; i < plan.length; i++) {
        const c = plan[i], p = plan[c.parent];
        const i0 = Math.round((c.x0 - p.x0) / p.cell), j0 = Math.round((c.y0 - p.y0) / p.cell), m = Math.round(c.side / p.cell);
        const up = Gd.cropUpsample2(fields[c.parent].h, i0, j0, m, 'catmull');
        const sc = Gd.slopeDeg(fields[i].h, c.cell), sp = Gd.slopeDeg(up, c.cell);
        const [hc, hu, a, b] = await R.readAll([fields[i].h, up, sc, sp]);
        const n = c.n;
        let dh = 0, jump = 0;
        for (let j = 0; j < n; j++) {
            for (let q = 0; q < n; q++) {
                const e = Math.min(q, n - 1 - q, j, n - 1 - j);
                const k = j * n + q;
                if (e === 0) dh = Math.max(dh, Math.abs(hc[k] - hu[k]));
                const ring2 = (j === 1 || j === n - 2) && q >= 1 && q <= n - 2 || (q === 1 || q === n - 2) && j >= 1 && j <= n - 2;
                if (e === 0 || ring2) jump = Math.max(jump, Math.abs(a[k] - b[k]));
            }
        }
        for (const f of [up, sc, sp]) f.destroy();
        rows.push({ child: i, child_cell_m: c.cell, edge_max_dh_m: +dh.toPrecision(4), edge_slope_jump_deg: +jump.toPrecision(4), ok: dh <= 0.05 && jump <= 3.0 });
    }
    return rows;
}

// ---------------------------------------------------------------------------------------------- the runs ---

for (const name of RECIPES) {
    for (const seed of SEEDS) {
        const dir = W.floorRun(name, seed, 'base');
        if (!dir) { T.ok(`${name} s${seed}: a floor run`, false, 'no base run (tests/parity/floor_runs.sh)'); continue; }
        if (!BOPS.recipes[name]) { T.ok(`${name}: the resolved stages`, false, 'not in blender_ops.json'); continue; }
        const logDir = `${W.out('hydro')}/runner_logs/${name}_s${seed}`;
        const { run, rec, fields } = await runOnce(dir, name, logDir);
        const tag = `${name} s${seed}`;
        console.log(`${tag}: ${rec.seconds} s, ${rec.op_calls[0]} of ${rec.op_calls[1]} op calls` + (rec.error ? `; ERROR ${rec.error}` : ''));
        const callsOk = !rec.error && rec.calls.length === run.stages.length && rec.calls.every((c) => c.same_call && c.same_params && c.same_ctx);
        T.ok(`${tag}: the runner made Blender's op calls (op, level, pass, window, params, seed, context)`, callsOk,
            rec.error ?? rec.problems.filter((p) => /Blender ran|params|context|takes_ctx|one call more|op calls/.test(p)).slice(0, 3).join(' | '));
        const inputsOk = !rec.error && rec.calls.every((c) => c.inputs?.ok !== false && c.pins?.ok !== false);
        T.ok(`${tag}: every op's inputs equal Blender's (inherit, pins and inflow, band pull, where)`, inputsOk,
            rec.problems.filter((p) => /inputs|pins/.test(p)).slice(0, 3).join(' | ') ||
            `${rec.calls.filter((c) => !c.inputs?.inexact).length} of ${rec.calls.length} calls bit for bit`);
        const wheres = rec.ends.filter((e) => e.event === 'where');
        if (wheres.length || run.stages.some((s) => s.where_mask)) {
            T.ok(`${tag}: ${wheres.length} where masks within 1e-5 of Blender's (of ${run.stages.filter((s) => s.where_mask).length})`,
                !rec.error && wheres.length === run.stages.filter((s) => s.where_mask).length && wheres.every((e) => e.ok),
                `worst ${C.sci(Math.max(0, ...wheres.map((e) => e.worst ?? Infinity)))}`);
        }
        const endsOk = !rec.error && rec.ends.length > 0 && rec.ends.filter((e) => e.event !== 'where').every((e) => e.ok !== false) &&
            rec.ends.filter((e) => e.event === 'route_after').length === run.levels.length;
        const worstUlp = Math.max(0, ...rec.ends.filter((e) => e.event === 'route_before').map((e) => e.surface_worst_ulp));
        T.ok(`${tag}: the end stages equal Blender's (lakes exact, routing surface, drainage area, iterations)`, endsOk,
            rec.problems.filter((p) => /lakes|route/.test(p)).slice(0, 3).join(' | ') || `routing surface worst ${worstUlp} ulp`);
        // the runner's own dispatch log against Blender's
        if (!rec.error) {
            const A = await DP.loadRun(dir), B = await DP.loadRun(logDir);
            const only = (x) => ({ ...x, dispatches: x.dispatches.filter((d) => d[0] === '<runner>') });
            const known = DP.knownIntervals(W.norm(`${dir}/../..`));
            const d = DP.compareLogs(only(A), only(B), { floor: C.readJson(`${dir}/dispatch_floor.json`), known, intervals: HY.CONVERGENCE_LOOPS });
            rec.dispatch = { ok: d.ok, dispatches: [only(A).dispatches.length, only(B).dispatches.length], structure: d.structure_differences.slice(0, 6),
                counts: d.counts_that_differ.slice(0, 10), uniforms_over_4_steps: d.uniforms_over_4_steps, images: d.image_differences.slice(0, 4) };
            T.ok(`${tag}: the runner's dispatch log equals Blender's (flow_weights, route_area per level; counts within a test interval)`, d.ok,
                `${rec.dispatch.dispatches[0]} and ${rec.dispatch.dispatches[1]} dispatches; ${d.counts_that_differ.length} counts differ` +
                (d.structure_differences.length ? `; ${d.structure_differences[0]}` : ''));
            // the seams
            rec.seams = await seams(run.levels, fields);
            T.ok(`${tag}: the level seams (|dh| <= 0.05 m at the border, slope jump <= 3 degrees)`, rec.seams.every((s) => s.ok),
                rec.seams.map((s) => `L${s.child} ${s.edge_max_dh_m} m ${s.edge_slope_jump_deg} deg`).join(', '));
            if (TWICE) {
                const again = await runOnce(dir, name, `${logDir}_again`);
                let same = !again.rec.error && again.fields.length === fields.length;
                let compared = 0;
                for (let i = 0; same && i < fields.length; i++) {
                    const names = Object.keys(fields[i]).sort();
                    if (!sameJson(names, Object.keys(again.fields[i]).sort())) { same = false; break; }
                    const a = await R.readAll(names.map((k) => fields[i][k])), b = await R.readAll(names.map((k) => again.fields[i][k]));
                    for (let q = 0; q < names.length; q++) { compared++; if (!bitsEqual(a[q], b[q])) same = false; }
                }
                const la = await DP.loadRun(logDir), lb = await DP.loadRun(`${logDir}_again`);
                const dd = DP.compareLogs(la, lb);
                T.ok(`${tag}: deterministic: a second run's ${compared} fields bit for bit, its dispatch log equal`, same && dd.ok && dd.counts_that_differ.length === 0,
                    `${la.dispatches.length} and ${lb.dispatches.length} dispatches`);
                for (const f of again.fields ?? []) f.dispose?.();
            }
            if (CACHE) {
                const croot = `${W.out('hydro')}/cache_test`;
                try { Deno.removeSync(croot, { recursive: true }); } catch (_e) { /* none yet */ }
                Deno.env.set('EIDO_TERRAIN_THREEJS_CACHE', croot);
                const first = await runOnce(dir, name, null, true);
                const second = await runOnce(dir, name, null, true);
                Deno.env.delete('EIDO_TERRAIN_THREEJS_CACHE');
                const hits = (second.rec.info.levels ?? []).filter((l) => l.cache === 'hit').length;
                let same = !first.rec.error && !second.rec.error && second.fields.length === first.fields.length;
                for (let i = 0; same && i < first.fields.length; i++) {
                    const names = Object.keys(first.fields[i]).sort();
                    if (!sameJson(names, Object.keys(second.fields[i]).sort())) { same = false; break; }
                    const a = await R.readAll(names.map((k) => first.fields[i][k])), b = await R.readAll(names.map((k) => second.fields[i][k]));
                    for (let q = 0; q < names.length; q++) if (!bitsEqual(a[q], b[q])) same = false;
                }
                T.ok(`${tag}: the level cache: a second run hits every level, calls no op, and gives the fields bit for bit`,
                    same && hits === run.levels.length && second.rec.calls.length === 0,
                    `${hits} of ${run.levels.length} levels hit, ${second.rec.calls.length} op calls; ${first.rec.error ?? second.rec.error ?? ''}`);
                for (const f of [...(first.fields ?? []), ...(second.fields ?? [])]) f.dispose?.();
            }
        }
        for (const f of fields ?? []) f.dispose?.();
        results.runs.push(rec);
    }
}

const code = T.done(null);
const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(), seconds: +((performance.now() - T.t0) / 1000).toFixed(2),
    checks: T.rows.length, failed: T.rows.filter((r) => !r.passed).map((r) => r.check), ...results, rows: T.rows };
Deno.writeTextFileSync(`${W.out('hydro')}/${OUT}.json`, JSON.stringify(res, null, 1));
G.shutdown();
Deno.exit(code);
