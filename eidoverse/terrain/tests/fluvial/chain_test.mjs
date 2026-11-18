// The fluvial package's recipes run end to end through the port's level runner (run.js), level by level against the
// Blender floor run of the same recipe and seed (PORT_PLAN.md 5.3 "recipe" grades, 5.4). The detail package's ops
// (P12: breakup, hydraulic) run when they are registered; while one is not, the runner skips it, and each level is
// compared where the two runs have done the same work:
//   - a level whose ops are all registered: its fields as the runner's end stages receive them (run.js trace
//     'lakes_before') against Blender's dump of the same point (L<i>_end_lakes_before.npz), and its routed drainage
//     area (trace 'route_after') against Blender's (L<i>_end_route_after.npz);
//   - a level an unregistered P12 op runs on (the main level: fluvial_range's breakup, meadow's hydraulic): its
//     fields before the end stages against Blender's input of the first such op (its stage dump `before`), with the
//     ops after it on that level (meadow's hummocks) left out on both sides.
// Per level: RMS(dh) / relief, p99 |dh| / relief and the channel overlap (cells over max(1 km^2, 400 cells) of
// drainage area: intersection over union), beside the tolerances floor.json gives that recipe, seed and level (1.25 x
// the largest of the five samples, never below 1e-4; overlap at least the smallest sample minus the spread). The
// floor's samples are of the finished fields, which the end stages and P12's ops have touched: the tolerances are
// those of the plan, applied a stage earlier. These recipes are of the distribution class (floor.json), whose gate is
// the judge's numbers over seeds: the levels' numbers are reported, and judged only as the evidence they are.
// rolling_hills is not run: its `incise` stage needs the river module (solvers/rivers.js, the layered-rock
// package's), and every level after it depends on it.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/chain_test.mjs
//          [--recipes fluvial_range,meadow] [--seeds 1,2]                (behind $EIDO_GPU_WRAP on a shared machine)
//
// JavaScript per cell here is test code. Writes tests/out/fluvial/chain_<recipe>_s<seed>.json.

import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import * as RUN from '../../run.js';
import * as RP from '../parity/replay.mjs';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const RECIPES = opt('--recipes', 'fluvial_range,meadow').split(',');
const SEEDS = opt('--seeds', '1,2').split(',').map(Number);
const P12 = new Set(['breakup', 'hydraulic', 'gully', 'planation']);

function diffStats(a, b, relief) {
    const e = new Float64Array(a.length);
    let sq = 0;
    for (let i = 0; i < a.length; i++) {
        const d = Math.abs(a[i] - b[i]);
        e[i] = d;
        sq += d * d;
    }
    e.sort();
    const pos = 0.99 * (e.length - 1), k = Math.floor(pos);
    const p99 = e[k] + (pos - k) * (e[Math.min(k + 1, e.length - 1)] - e[k]);
    return { rms: Math.sqrt(sq / a.length) / relief, p99: p99 / relief, max: e[e.length - 1] / relief };
}

function overlap(A1, A2, cell) {
    const thr = Math.max(1e6, 400 * cell * cell);
    let inter = 0, uni = 0;
    for (let i = 0; i < A1.length; i++) {
        const a = A1[i] > thr, b = A2[i] > thr;
        if (a && b) inter++;
        if (a || b) uni++;
    }
    return uni ? inter / uni : 1.0;
}

const T = new C.Checks('fluvial: the recipes end to end through run.js, against the Blender floor runs');
const R = await G.init();
const registry = await import('../../recipes/index.js');
const floorAll = C.readJson(`${W.parityKeyDir()}/floor.json`, { recipes: {} });

for (const name of RECIPES) {
    for (const seed of SEEDS) {
        const dir = W.floorRun(name, seed);
        if (!dir) { T.ok(`${name} s${seed}: a floor run`, false, 'none'); continue; }
        const run = await RP.loadRun(dir);
        const hd = run.header;
        const plan = hd.plan.map((d) => Level.fromDict(d));
        const recipe = registry.get(name);
        const [values, stages] = recipe.resolve(hd.values);
        const fl = floorAll.recipes?.[name]?.seeds?.[String(seed)] ?? null;
        // the levels an op of another package that is not registered yet runs on (P12's, until they land), and
        // Blender's input of the first such op there; a level whose ops are all registered is compared whole
        const p12At = {};
        for (const st of run.stages) {
            if (P12.has(st.op) && !(await registry.hasOp(st.op)) && !(st.level in p12At)) p12At[st.level] = st;
        }
        const later = new Set();
        for (const st of run.stages) if (st.level in p12At && st.call > p12At[st.level].call) later.add(`${st.level}|${st.op}`);
        const noop = async (fields) => fields;
        noop.takesCtx = true;                               // (a ctx-less op would get run.js's band pull afterwards)
        const getOp = async (op) => {
            const fn = await registry.getOp(op);
            // an op after a P12 op on that level is left out (it would act on another state than Blender's)
            return fn;
        };
        let curLevel = null;
        const wrapped = async (op) => {
            if (curLevel !== null && later.has(`${curLevel}|${op}`)) return noop;
            return getOp(op);
        };
        const rows = [];
        const t0 = performance.now();
        const info = {};
        const trace = async (ev, pl) => {
            if (ev === 'lakes_before' || (ev === 'route_before' && !rows[pl.index]?.h)) {
                const i = pl.index;
                const ref = p12At[i] ? `${run.dir}/stages/${p12At[i].before}` : `${run.dir}/stages/L${i}_end_lakes_before.npz`;
                const want = await RP.npz(ref);
                const got = await R.read(pl.fields.h);
                const relief = fl?.levels?.[i]?.relief_m ?? 1.0;
                (rows[i] ??= { index: i, level: String(plan[i]), compared_to: ref.split('/').pop() }).h = diffStats(got, want.h.data, relief);
            }
            if (ev === 'route_after' && !p12At[pl.index]) {
                const i = pl.index;
                const want = await RP.npz(`${run.dir}/stages/L${i}_end_route_after.npz`);
                const got = await R.read(pl.A);
                (rows[i] ??= { index: i }).overlap = overlap(got, want.A.data, plan[i].cell);
            }
        };
        // run.js calls getOp(op) per stage; it sets G.context.level as each level starts, which the wrapper reads
        const getOpLevel = async (op) => { curLevel = G.context.level; return wrapped(op); };
        try {
            await RUN.runLevels(plan, recipe, values, stages, { seed: hd.seed, flatten: hd.flatten ?? [], seaLevel: hd.sea_level ?? null,
                baseElevationM: hd.base_elevation_m ?? 0.0, cache: false, info, getOp: getOpLevel, trace, log: () => {} });
        } catch (e) {
            T.ok(`${name} s${seed}: runs end to end`, false, `${e.name}: ${e.message}`);
            continue;
        }
        const secs = (performance.now() - t0) / 1000;
        T.ok(`${name} s${seed}: runs end to end through run.js (${RUN.skippedStages(info).join(', ') || 'nothing'} skipped)`, true,
            `${secs.toFixed(1)} s (Blender's run ${run.info?.seconds ?? '?'} s)`);
        for (const r of rows.filter(Boolean)) {
            const f = fl?.levels?.[r.index];
            const okR = f ? r.h.rms <= Math.max(1e-4, f.tol_rms) : null;
            const okP = f ? r.h.p99 <= Math.max(1e-4, f.tol_p99) : null;
            const okO = f && r.overlap !== undefined ? r.overlap >= f.overlap_min : null;
            r.tol = f ? { rms: f.tol_rms, p99: f.tol_p99, overlap_min: f.overlap_min, floor_rms: f.rms, floor_p99: f.p99, floor_overlap: f.overlap } : null;
            r.ok = okR !== false && okP !== false && okO !== false;
            T.ok(`${name} s${seed} L${r.index} (${r.compared_to}): RMS ${C.sci(r.h.rms, 2)} (tol ${C.sci(f?.tol_rms, 2)}), p99 ${C.sci(r.h.p99, 2)} ` +
                `(tol ${C.sci(f?.tol_p99, 2)})` + (r.overlap !== undefined ? `, overlap ${r.overlap.toFixed(3)} (min ${f?.overlap_min?.toFixed(3)})` : ''),
            r.ok, '');
        }
        Deno.writeTextFileSync(`${W.out('fluvial')}/chain_${name}_s${seed}.json`, JSON.stringify({ recipe: name, seed,
            class: floorAll.recipes?.[name]?.class ?? null, seconds: secs, skipped: RUN.skippedStages(info), levels: rows.filter(Boolean),
            record: info }, null, 1));
    }
}
Deno.exit(C.finish(T, '../fluvial/chain_test'));
