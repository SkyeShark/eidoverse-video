// Stage replay of the glacial ops on the Blender edition's own dumps (PORT_PLAN.md 8.2 row P13, 5.1, 5.3, 5.7): each
// call of valley_uplift and glacial in the floor runs of alpine_valley (seeds 1 and 2, every level: the coarsest
// level's passes, where the uplift grows and the carve runs, and the finer levels, where the walls are refined),
// replayed by the port's op from that call's own input through tests/parity/replay.mjs replayStage:
//   fields      every field after the op against Blender's: max |d| <= max(1e-4 x range, 1.25 x the stage's floor,
//               16 float32 steps) (the floor: tests/parity/blender_stage_dump.py --floor, five patterns; a call with
//               no recorded floor gets the kernel grade; the coarsest level's carve calls take the floor
//               tests/glacial/carve_floor.py measures the same way but for the jump flood's images, which hold packed
//               cell indices that the in-op nudge turns into other seeds', and both floors are named). On a carve
//               call the per-seed profile fields (trough_zf, _H, _ff, _fill, _rise, _sharp, trough_rho: each cell's
//               winning seed's values) are graded as labels: the stage grade on every cell whose winner is Blender's,
//               and a different winner on at most 0.1 % of the level's cells (a near tie of two seeds' targets, which
//               the seeds' float32 rounding settles either way: Blender's GPU and its float32 twin differ on 0.13 %
//               of the candidate slots of seed 2's carve, tests/glacial/gpu_fixtures.py)
//   dispatches  the call's Blender kernels in order and number (ice_flux in loops of 128 that stop on a convergence
//               test, solvers/glacial.js CONVERGENCE_LOOPS; jump_flood; u_carve; world_noise_field; the threshold
//               pass), every uniform within 4 float32 steps, the bound images' names, sizes and formats
//   snapshots   each kernel's images and inputs after its 1st, 10th, 100th, 1,000th and 10,000th dispatch, and its
//               1st, 10th and 100th within the call (main level), against Blender's, at max(1e-4 x range, 1.25 x the
//               floor runs' largest change there). A run-wide key (ice_flux#1000: the run's 1,000th dispatch of the
//               kernel) is compared only where it is the call's own n-th dispatch of that kernel (the port's counts
//               start at the replayed call), else set aside and named
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/glacial/replay_test.mjs
//         [--runs alpine_valley_s1,alpine_valley_s2] [--ops glacial,valley_uplift] [--levels 0,1,2] [--calls 5,8]
//         [--run-dir <name>=<a run's base folder>]
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// --run-dir replays a run that is not a floor run, from its folder (tests/glacial/blender_runs.py --dump: the
// yosemite preset's dumps): no floor samples it, so every call takes the kernel grade (and 16 float32 steps); a
// diagnosis of the op on that run's inputs, written to replay_test_<name>.json so the floor runs' record stays.
//
// Writes tests/out/glacial/replay_test.json and the port's logs under tests/out/glacial/replay/. JavaScript per cell
// here is test code.

import * as G from '../../core/gpu.js';
import * as GL from '../../solvers/glacial.js';
import * as DP from '../parity/dispatch_parity.mjs';
import * as RP from '../parity/replay.mjs';
import * as C from '../parity/_common.mjs';
import { finish } from './_glacial.mjs';

const W = C.W;
const args = [...Deno.args];
const list = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1].split(',') : null; };
const OPS = { glacial: GL.opGlacial, valley_uplift: GL.opValleyUplift };
const WANT_OPS = list('--ops') ?? Object.keys(OPS);
const LEVELS = list('--levels')?.map(Number) ?? null;
const CALLS = list('--calls')?.map(Number) ?? null;
const RUN_DIRS = Object.fromEntries((list('--run-dir') ?? []).map((s) => [s.slice(0, s.indexOf('=')), s.slice(s.indexOf('=') + 1)]));
const RUNS = list('--runs') ?? (Object.keys(RUN_DIRS).length ? Object.keys(RUN_DIRS) : ['alpine_valley_s1', 'alpine_valley_s2']);

/** The floor run of (recipe, seed) under the parity key, else under another key of the same Blender terrain code. */
function floorRunOfCode(recipe, seed) {
    const key = W.parityKeyDir();
    if (!key) return null;
    const own = W.floorRun(recipe, seed, 'base');
    if (own) return [own, key.split('/').pop()];
    const code = (dir) => { const k = C.readJson(`${dir}/manifest.json`)?.key; return k ? `${k.field_hash}|${k.terrain_hash}` : null; };
    const mine = code(key);
    for (const k of W.parityKeys()) {
        const dir = `${k.dir}/${recipe}_s${seed}_draft/base`;
        if (mine && k.dir !== key && code(k.dir) === mine && W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

/** Blender's snapshots of one call that the port's replay of it can match: { snapIndex, aside }. */
async function callSnapshots(run, call) {
    run._log ??= await DP.loadRun(run.dir);
    let nth = null;
    const snapIndex = {}, aside = [];
    for (const [key, e] of Object.entries(run.snapIndex)) {
        if (e.call !== call) continue;
        const m = /^(.+)#(\d+)$/.exec(key);
        if (m && !/^L\d+_c\d+_/.test(key)) {
            if (!nth) {
                nth = {};
                run._log.dispatches.forEach((d, i) => { if (d[5]?.call === call) (nth[d[1]] ??= []).push(i); });
            }
            const k = (nth[m[1]] ?? []).indexOf(e.d) + 1;
            if (k !== Number(m[2])) { aside.push(`${key} (the call's dispatch ${k} of ${m[1]})`); continue; }
        }
        snapIndex[key] = e;
    }
    return { snapIndex, aside };
}

const CARVE_FLOORS = C.readJson(`${W.out('glacial')}/carve_floors.json`);
const PROFILE = ['trough_zf', 'trough_H', 'trough_ff', 'trough_fill', 'trough_rise', 'trough_sharp', 'trough_rho'];
const MAX_WINNER_FLIPS = 1e-3;                 // of the level's cells (see the carve calls' verdict below)

/** The cells of a carve call whose winning seed differs from Blender's (test code, per cell): a cell where the winner's
 * own values (trough_zf, trough_H, trough_ff, trough_fill, trough_rise: per-seed values, which the seed textures carry
 * within 1e-5 of their range) are not all within the stage grade of Blender's. {cells,
 * of (the level's), trough_cells (Blender's trough_rho under 1.5, the trough and its lip band), flips, flips_in_trough,
 * outside: per profile field the worst |d| / range on the cells whose winner is the same}. */
async function winnerFlips(run, st, kept) {
    const want = await RP.npz(`${run.dir}/stages/${st.after}`);
    const floor = run.floors[st.call]?.floor ?? {};
    const n = kept.trough_zf.length;
    const tolOf = (k) => {
        const a = want[k].data;
        let lo = Infinity, hi = -Infinity, amax = 0;
        for (let i = 0; i < n; i++) { lo = Math.min(lo, a[i]); hi = Math.max(hi, a[i]); amax = Math.max(amax, Math.abs(a[i])); }
        const range = hi - lo || amax || 1;
        return { range, tol: Math.max(Math.max(1e-4, 1.25 * (floor[k]?.max_over_range ?? 0)) * range, 16 * 2 ** (Math.floor(Math.log2(amax || 1)) - 23)) };
    };
    const own = ['trough_zf', 'trough_H', 'trough_ff', 'trough_fill', 'trough_rise'].filter((k) => k in kept && k in want);
    const tol = Object.fromEntries(PROFILE.filter((k) => k in kept && k in want).map((k) => [k, tolOf(k)]));
    const flip = new Uint8Array(n);
    let flips = 0, inTrough = 0, troughCells = 0;
    const rho = want.trough_rho?.data;
    for (let i = 0; i < n; i++) {
        const t = rho ? rho[i] < 1.5 : true;
        if (t) troughCells++;
        if (own.some((k) => Math.abs(kept[k][i] - want[k].data[i]) > tol[k].tol)) {
            flip[i] = 1;
            flips++;
            if (t) inTrough++;
        }
    }
    const outside = {};
    for (const k of Object.keys(tol)) {
        let w = 0;
        for (let i = 0; i < n; i++) if (!flip[i]) w = Math.max(w, Math.abs(kept[k][i] - want[k].data[i]));
        outside[k] = { over: w / tol[k].range, ok: w <= tol[k].tol };
    }
    return { cells: n, trough_cells: troughCells, flips, flips_in_trough: inTrough, outside_ok: Object.values(outside).every((o) => o.ok),
        outside: Object.fromEntries(Object.entries(outside).map(([k, o]) => [k, C.sci(o.over)])) };
}
const T = new C.Checks('glacial: stage replay on the Blender dumps');
const R = await G.init();
const results = [];
for (const name of RUNS) {
    const m = /^(.*)_s(\d+)$/.exec(name);
    const found = RUN_DIRS[name] ? [W.absPath(RUN_DIRS[name]), null] : m ? floorRunOfCode(m[1], Number(m[2])) : null;
    if (!found || (RUN_DIRS[name] && !W.exists(`${found[0]}/done.json`))) {
        console.log(`[skip] ${name}: no floor run with stage dumps (tests/parity/floor_runs.sh)`);
        continue;
    }
    const [dir, key] = found;
    const run = await RP.loadRun(dir);
    // the carve calls' floors as tests/glacial/carve_floor.py measures them (the jump flood's packed indices left
    // whole by the in-op nudge); every other call's from the run's stage_floors.json
    const carveFloors = CARVE_FLOORS?.key === key ? CARVE_FLOORS.runs?.[name] ?? {} : {};
    for (const st of run.stages) {
        if (!(st.op in OPS) || !WANT_OPS.includes(st.op)) continue;
        if (LEVELS && !LEVELS.includes(st.level)) continue;
        if (CALLS && !CALLS.includes(st.call)) continue;
        const { snapIndex, aside } = await callSnapshots(run, st.call);
        const own = carveFloors[String(st.call)];
        const floorUsed = own ? 'carve_floor.py' : run.floors[st.call]?.floor ? 'stage_floors.json' : 'none (the kernel grade)';
        const floorNote = own ? { carve_floor_h: own.floor?.h?.max_over_range ?? null,
            stage_floors_h: run.floors[st.call]?.floor?.h?.max_over_range ?? null } : null;
        const view = { ...run, snapIndex, floors: own ? { ...run.floors, [st.call]: own } : run.floors };
        const logDir = `${W.out('glacial')}/replay/${name}/c${st.call}_${st.op}_L${st.level}_p${st.pass_index}`;
        // the carve's per-seed profile fields (each cell's winning seed's values, trough_zf .. trough_sharp) step where
        // the jump flood's winner changes: kept to count the cells whose winner differs from Blender's
        // (and graded by the run's own stage_floors.json as well, the plan's protocol as tests/parity measured it)
        // (a --run-dir run has no carve floor: its carve call, the coarsest level's grown pass, is graded so too)
        let kept = null, byStageFloors = null;
        const carveCall = st.op === 'glacial' && st.context?.role === 'grow' && (st.context?.prepass ?? null) === null;
        const invoke = async (op, a) => {
            await op(a.fields, a.level, a.params, a.seed, a.ctx);
            if (st.op === 'glacial' && 'trough_zf' in a.fields && (own || (RUN_DIRS[name] && carveCall))) {
                kept = {};
                for (const k of PROFILE) if (k in a.fields) kept[k] = await R.read(a.fields[k]);
                if (own) byStageFloors = (await RP.compareAfter(run, st, a.fields)).ok;
            }
        };
        const r = await RP.replayStage(R, G, view, st, OPS[st.op], { logDir, intervals: GL.CONVERGENCE_LOOPS, invoke });
        const winners = kept ? await winnerFlips(view, st, kept) : null;
        if (winners) console.log(`     winners: ${JSON.stringify(winners)}`);
        run._log ??= view._log;
        run._known ??= view._known;
        // a carve call: the per-seed profile fields are graded as the labels of each cell's winning seed: the stage grade
        // on every cell whose winner is Blender's, and the winner may differ on at most MAX_WINNER_FLIPS of the level's
        // cells (near ties of two seeds' targets: Blender's own GPU and its float32 twin, the same kernel on the same
        // seeds, differ on 0.13 % of the candidate slots of seed 2's carve, tests/glacial/gpu_fixtures.py)
        let fieldsOk = r.fields?.ok ?? false, winnerNote = '';
        if (winners && r.fields) {
            const others = Object.entries(r.fields.fields).filter(([k]) => !PROFILE.includes(k)).every(([, g]) => g.ok);
            const flipsOk = winners.flips <= MAX_WINNER_FLIPS * winners.cells && winners.outside_ok;
            fieldsOk = others && flipsOk && !r.fields.missing.length;
            winnerNote = `; the profile fields: the winning seed differs on ${winners.flips} of ${winners.cells} cells ` +
                `(${winners.flips_in_trough} in the trough and its lip band), the rest within the stage grade` +
                `${winners.outside_ok ? '' : ' NOT'} (${JSON.stringify(winners.outside)})`;
        }
        const ok = !r.error && fieldsOk && r.dispatch?.ok && r.snapshots?.ok;
        const worst = Object.entries(r.fields?.fields ?? {}).filter(([k]) => !winners || !PROFILE.includes(k))
            .sort((a, b) => b[1].over - a[1].over)[0];
        const d = r.dispatch ?? {};
        const lvd = run.header.plan?.[st.level];
        const line = `${name} L${st.level} p${st.pass_index}${lvd ? ` (${lvd.role} ${st.window.cell} m x${st.window.n})` : ''} ${st.op} ` +
            `(call ${st.call}): ` + (r.error ? r.error :
            `fields ${fieldsOk ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, ` +
                `grade ${C.sci(worst[1].tol / (worst[1].range || 1))}` : 'none'}${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}` +
            `${r.fields.extra.length ? `; extra ${r.fields.extra}` : ''}${winnerNote}), dispatch log ${d.ok ? 'equal' : 'DIFFERS'} ` +
            `(${d.compared_dispatches} Blender dispatches compared, ${d.uniforms_over_4_steps} uniforms over 4 steps), ` +
            `${r.snapshots.keys} snapshots (${r.snapshots.compared} channels) ${r.snapshots.ok ? 'within tolerance' : 'OVER'} ` +
            `worst ${C.sci(r.snapshots.worst)}${aside.length ? `, ${aside.length} run-wide set aside` : ''}; floor: ${floorUsed}` +
            (floorNote ? ` (h ${C.sci(floorNote.carve_floor_h)}; stage_floors.json's, the jump flood's candidates nudged: ` +
                `${floorNote.stage_floors_h === null ? 'none' : C.sci(floorNote.stage_floors_h)}, by which every field is ` +
                `${byStageFloors ? 'within tolerance' : 'NOT within tolerance'})` : '') + `; ${r.seconds} s ` +
            `(Blender ${st.seconds} s)${key && key !== W.parityKeyDir()?.split('/').pop() ? ` [floor run of key ${key}]` : ''}`);
        T.ok(line, ok, '');
        if (!ok && !r.error) {
            if (!fieldsOk) console.log('     fields over:', JSON.stringify(Object.entries(r.fields.fields).filter(([, g]) => !g.ok).map(([k, g]) => [k, C.sci(g.over), C.sci(g.floor)])));
            if (!d.ok) console.log('     dispatch:', JSON.stringify({ structure: d.structure_differences, counts: d.counts_that_differ?.slice(0, 5), uniforms: d.uniform_failures?.slice(0, 5), images: d.image_differences }).slice(0, 2000));
            if (!r.snapshots.ok) console.log('     snapshots:', JSON.stringify(r.snapshots.failures.slice(0, 8)), JSON.stringify(r.snapshots.shapes));
        }
        results.push({ run: name, key, ...r, verdict: ok, floor_used: floorUsed, floor_note: floorNote, by_stage_floors: byStageFloors, winners, snapshots_set_aside: aside, fields: r.fields ? { ok: r.fields.ok, missing: r.fields.missing,
            extra: r.fields.extra, worst: worst ? { field: worst[0], ...worst[1] } : null, all: r.fields.fields } : null });
    }
}
T.ok(`${results.length} replays ran`, results.length > 0, '');
const code = finish(T, Object.keys(RUN_DIRS).length ? `replay_test_${RUNS.join('_')}` : 'replay_test', { results });
G.shutdown();
Deno.exit(code);
