// Stage replay, dispatch-log parity and step snapshots of the op dune_field on the Blender edition's own dumps
// (PORT_PLAN.md 5.3, 5.7, 8.1: "every op a package ports is accepted by four checks"; 8.2 P8).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/wind_sand/replay_test.mjs [seeds]
//          [--run <base dir>] ...
//
// (from the repository root; behind $EIDO_GPU_WRAP on a shared machine; seeds default 1,2: the floor's dunes runs,
// tests/parity/floor_runs.sh; --run adds a run in the floor's format, such as tests/wind_sand/blender_refine.py's
// linear run, whose finer levels refine). A dunes run calls dune_field once per level (three at draft quality): the coarsest
// level's call grows the tile on the growth level (the main level here: 512 cells of 15.6 m resolve the 1.4 km spacing
// with 90 cells) and the other two find it in the solver's memo (aeolian._TILES; the port's growTile memo), so the
// replay runs the run's three calls in order in one process, as the run did: the recipe's prepare hook first (the
// level stack), the memo cleared before the first call (plan 5.4), each call from its own `before` dump, through
// tests/parity/replay.mjs's pieces. Per call:
//   fields      every field of the `after` dump (h, bed, sand; A and qs pass through), max |d| within max(1e-4 x range,
//               1.25 x the stage floor, 16 float32 steps): the floor is blender_stage_dump.py --floor's for the main
//               level's call (stage_floors.json: the op replayed five times with the op-entry and first-dispatch
//               perturbations of 5.4). The context levels' fields are 2 x 2 and 4 x 4 averages of the same tile
//               (sample_periodic), whose differences an average cannot make larger than the tile's: they take the
//               main level's floor (the floor measured them only on the main level)
//   dispatches  the call's lines of Blender's dispatch log against the port's (dispatch_parity.mjs: the Blender
//               kernels' sequence and counts, every uniform, the bound images; the port's own kernels set aside):
//               the growth call holds the 6 world_noise_field dispatches and the 26,991 iterations' 458,847 dune
//               dispatches, the memo calls none
//   snapshots   each kernel's images and inputs after its 1st, 10th, 100th, 1,000th and 10,000th dispatch, against
//               Blender's, at max(1e-4 x range, 1.25 x the largest floor sample at that dispatch) (compareSnapshots)
// Also recorded: the growth call's seconds beside Blender's. JavaScript per cell and per dispatch here is test code.

import * as G from '../../core/gpu.js';
import * as A from '../../solvers/aeolian.js';
import { DUNES } from '../../recipes/dunes.js';
import * as C from '../parity/_common.mjs';
import * as DP from '../parity/dispatch_parity.mjs';
import * as RP from '../parity/replay.mjs';
import * as S from './_common.mjs';

const argv = [...Deno.args];
const extraRuns = [];
for (let i = argv.indexOf('--run'); i >= 0; i = argv.indexOf('--run')) extraRuns.push(S.W.absPath(argv.splice(i, 2)[1]));
const seeds = argv.length ? argv[0].split(',').filter(Boolean).map(Number) : (extraRuns.length ? [] : [1, 2]);

// each snapshot key's largest |port - Blender| over its images and channels, as a share of the channel's range, and
// whether every integer channel of a plan record is equal (the record for the summary: what the first dispatches show)
async function snapshotTable(run, portDir) {
    const mine = C.readJson(`${portDir}/snap/index.json`, { snapshots: {} }).snapshots;
    const out = {};
    for (const [key, ent] of Object.entries(mine)) {
        const base = run.snapIndex[key];
        if (!base) continue;
        const a = await RP.npz(`${run.dir}/snap/${base.file}`), b = await RP.npz(`${portDir}/snap/${ent.file}`);
        let worst = 0, where = '', cellsDiffer = 0;
        for (const [im, want] of Object.entries(a)) {
            const got = b[im];
            if (!got || got.data.length !== want.data.length) continue;
            const ch = want.shape[2] ?? 1, n = want.data.length / ch;
            for (let c = 0; c < ch; c++) {
                let lo = Infinity, hi = -Infinity, err = 0;
                for (let i = 0; i < n; i++) {
                    const w = want.data[i * ch + c];
                    if (w < lo) lo = w;
                    if (w > hi) hi = w;
                    err = Math.max(err, Math.abs(got.data[i * ch + c] - w));
                }
                const over = err / ((hi - lo) || Math.abs(hi) || 1);
                if (over > worst) { worst = over; where = `${im}[${c}]`; }
            }
            // a decision: whether the cell lifts, its integer hop and its landing hop (the lifted amount itself is
            // min(sand, slab), a float the port's sand carries to its last bits)
            if (im === 'outPlan') {
                for (let i = 0; i < n; i++) {
                    const o = 4 * i;
                    if ((want.data[o] > 0) !== (got.data[o] > 0) || want.data[o + 1] !== got.data[o + 1] ||
                        want.data[o + 2] !== got.data[o + 2] || want.data[o + 3] !== got.data[o + 3]) cellsDiffer++;
                }
            }
        }
        out[key] = { worst_over_range: +worst.toPrecision(3), where, ...(key.includes('dune_activate') ? { decisions_that_differ: cellsDiffer } : {}) };
    }
    return out;
}
const T = new S.Checks('wind and sand: stage replay, dispatch log and step snapshots of dune_field');
const R = await G.init();
const quiet = [];
const log = (m) => quiet.push(m);
const results = [];

const runDirs = seeds.map((s) => [S.W.floorRun('dunes', s, 'base'), s]);
for (const d of extraRuns) runDirs.push([d, C.readJson(`${d}/run.json`)?.seed ?? null]);
for (const [dir, seedOf] of runDirs) {
    if (!dir || !S.W.exists(`${dir}/stages/stages.json`)) {
        S.W.skip(`dunes seed ${seedOf}`, 'tests/parity/floor_runs.sh --recipes dunes (or tests/wind_sand/blender_refine.py) makes the run');
        continue;
    }
    const run = await RP.loadRun(dir);
    const kind = run.header.values?.kind ?? 'star';
    const seed = kind === 'star' ? run.header.seed : `${run.header.seed} (${kind})`;
    const main = run.header.main_index;
    const mainCall = run.stages.find((s) => s.level === main)?.call;
    const mainFloor = run.floors[mainCall];
    // the context levels' calls take the main level's floor (their fields are averages of its tile: see the top)
    for (const st of run.stages) if (!run.floors[st.call] && mainFloor) run.floors[st.call] = { ...mainFloor, borrowed_from_call: mainCall };
    const floor = C.readJson(`${dir}/dispatch_floor.json`);
    run._known ??= DP.knownIntervals(S.W.norm(`${dir}/../..`));
    A.clearTiles();
    A.prepare(run.header.values, run.levels);              // what the recipe's prepare hook does before the levels run
    T.ok(`dunes seed ${seed}: the recipe's prepare hook is the solver's (it records the level stack)`, typeof DUNES.prepare === 'function');
    const runTag = kind === 'star' ? `dunes_s${run.header.seed}` : `dunes_${kind}_s${run.header.seed}`;
    for (const st of run.stages) {
        const before = await RP.stageBefore(R, run, st);
        const logDir = `${S.OUT}/replay/${runTag}/c${st.call}_${st.op}`;
        const pl = new RP.PortLog(G, logDir, { mainLevel: main }).start();
        Object.assign(G.context, { op: st.op, call: st.call, level: st.level, pass: st.pass_index, prepass: null, end: null });
        const t0 = performance.now();
        let error = null;
        try {
            await A.opDuneField(before.fields, before.level, structuredClone(st.params), st.seed, log);
            await R.idle();
        } catch (e) {
            error = `${e.name}: ${e.message}`;
        }
        const seconds = +((performance.now() - t0) / 1000).toFixed(2);
        Object.assign(G.context, { op: null, call: null, level: null, pass: null, prepass: null, end: null });
        const summary = await pl.stop();
        const tag = `dunes seed ${seed}, level ${st.level} (call ${st.call})`;
        if (error) {
            T.ok(`${tag}: the op runs`, false, error);
            continue;
        }
        const f = await RP.compareAfter(run, st, before.fields);
        const worst = Object.entries(f.fields).sort((a, b) => b[1].over - a[1].over);
        const borrowed = run.floors[st.call]?.borrowed_from_call !== undefined;
        T.ok(`${tag}: every field of the op's result against Blender's from the same input, within the stage floor` +
            (borrowed ? ' (the main level\'s, borrowed: an average of the same tile)' : ''), f.ok,
            worst.map(([k, g]) => `${k} ${S.sci(g.over)} of range (tol ${S.sci(g.tol / (g.range || 1))}, floor ${S.sci(g.floor)})`).join('; ') +
            (f.missing.length ? `; missing ${f.missing}` : '') + (f.extra.length ? `; extra ${f.extra}` : ''));
        const mine = await DP.loadRun(logDir);
        const d = DP.compareLogs(await RP.blenderCall(run, st.call), mine, { floor, known: run._known });
        T.ok(`${tag}: the dispatch log equals Blender's (the Blender kernels in order and number, every uniform, the bound images)`, d.ok,
            `${d.dispatches[0]} and ${d.dispatches[1]} dispatches (Blender, the port's incl. its own kernels), ${d.compared_dispatches} paired; ` +
            `${d.counts_that_differ.length} counts differ; ${d.uniforms_over_4_steps} uniforms over 4 float32 steps; ` +
            `${d.image_differences.length} image differences` + (d.structure_differences.length ? `; ${d.structure_differences.slice(0, 2).join(' | ')}` : '') +
            (d.first_uniform_over_4_steps ? `; first uniform over: ${JSON.stringify(d.first_uniform_over_4_steps).slice(0, 300)}` : ''));
        const sn = await RP.compareSnapshots(run, logDir);
        T.ok(`${tag}: the step snapshots within max(1e-4 x range, 1.25 x the floor at that dispatch)`, sn.ok,
            `${sn.keys} snapshots, ${sn.compared} channels compared, worst ${S.sci(sn.worst)} of range` +
            (sn.failures.length ? `; over: ${sn.failures.slice(0, 4).map((x) => `${x.key} ${x.image}[${x.channel}] ${S.sci(x.over)} > ${S.sci(x.tol)}`).join(', ')}` : '') +
            (sn.shapes.length ? `; shapes: ${sn.shapes.slice(0, 2).join(' | ')}` : ''));
        results.push({ seed, call: st.call, level: st.level, seconds, blender_seconds: st.seconds, log: summary,
            fields: f.fields, dispatch: { ok: d.ok, dispatches: d.dispatches, compared: d.compared_dispatches,
                counts_that_differ: d.counts_that_differ.slice(0, 10), uniforms_over_4_steps: d.uniforms_over_4_steps,
                worst_uniforms: d.worst_uniforms, readbacks: d.readbacks }, snapshots: { ok: sn.ok, keys: sn.keys, compared: sn.compared,
                worst: sn.worst, failures: sn.failures.slice(0, 20), only_port: sn.only_port } });
        if (summary.dispatches > 10) {
            T.ok(`${tag}: the call's time beside Blender's (recorded, not graded)`, true, `${seconds} s against Blender's ${st.seconds} s`);
            const table = await snapshotTable(run, logDir);
            results[results.length - 1].snapshot_table = table;
            const first = Object.entries(table).filter(([k]) => k.endsWith('#1'));
            if (first.length) {
                T.ok(`${tag}: at each kernel's first dispatch the snapshots are within the kernel grade, and dune_activate's decisions are Blender's (recorded)`,
                    first.every(([k, v]) => v.worst_over_range <= 1e-4 || k.startsWith('route')),
                    first.map(([k, v]) => `${k} ${S.sci(v.worst_over_range, 2)}${v.decisions_that_differ !== undefined ? ` (${v.decisions_that_differ} decisions differ)` : ''}`).join('; '));
            }
        }
        for (const name of Object.keys(before.fields)) before.fields[name]?.destroy?.();
        for (const p of Object.values(before.pins)) p.destroy?.();
    }
    A.clearTiles();
}

G.shutdown();
Deno.exit(S.finish(T, 'replay_test', { results, log: quiet.slice(0, 40) }));
