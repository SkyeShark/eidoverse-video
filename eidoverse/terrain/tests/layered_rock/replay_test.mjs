// The layered-rock package's ops by stage replay (PORT_PLAN.md 8.1, 8.2 row P10: "stage replay, dispatch-log parity
// and step snapshots of strata, plateau, river_path, strata_fluvial"): every call of the four ops in the chaos floor's
// base runs of canyon, incised_meanders, mesas_buttes and badlands (seeds 1-2, draft), each run once from the Blender
// edition's own input (the stage dump of its fields, pins and context), through tests/parity/replay.mjs replayStage:
//   fields      every field after the op against Blender's, max |d| within max(1e-4 x range, 1.25 x the stage's floor)
//               (the floor: blender_stage_dump.py --floor, every level the floor was measured on)
//   dispatches  the call's dispatch log against Blender's (the Blender kernels in order, their counts and uniforms;
//               the port's own kernels set aside); the caprock check's loop may move by whole check intervals
//   snapshots   each Blender kernel's images after its 1st, 10th and 100th dispatch in the call (main level)
// and, beside them:
//   pins        river_path's pins (ctx.pins, the channel at its final bed) against the pins the next stage received
//               in Blender's run (its `before` dump): the weight exactly, the height within 1e-5 of its range
//   control     strata_fluvial's record (ctx.shared.fluvial_log): role, steps, dt, years, D, valley spacing, creep
//               sub-steps, the lock's block and length, the caprock checks, the dry basins filled
// A River in a dumped context is rebuilt from its dump (tests/layered_rock/_layered.mjs reviveRiver), as Blender's
// replays unpickle it. Run-wide snapshot keys (world_noise_field#10: the run's 10th dispatch of the kernel) are
// aligned: Blender's log says how many dispatches of the kernel the call had made by then, and the port's log
// snapshots its own dispatch of that count under Blender's key (a hook on the parity tool's PortLog, in this test
// only); a run-wide key of another call is not the port's to compare. op_seconds is the op alone (the test's reads
// of the dumps are inside replay.mjs's `seconds`).
// Beside the plan's grades (each field's and snapshot channel's single worst cell: `ok`), the second grade of the
// fluvial package's replay (tests/fluvial/replay_test.mjs): the fields' RMS and 99th percentile of |d|, and each
// compared snapshot channel's RMS, against the floor samples' own (they record [max, RMS, p99] of the stage floor and
// [max, RMS] of the snapshots), each within max(1e-4, 1.25 x the largest sample): `ok_rms`. On the routed and
// stepped quantities of a chaotic op (A and qs, the talus and deposit of a few cells, Sc where a cell's height
// crosses a bed's contact) one cell decides the worst-cell number, and five samples bound it loosely.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/layered_rock/replay_test.mjs
//         [--recipes canyon,...] [--seeds 1,2] [--ops strata,plateau,river_path,strata_fluvial] [--levels all|main|0,1]
//         [--max N] [--tag name]                       (on a shared machine, behind $EIDO_GPU_WRAP)
//     ... replay_test.mjs --regrade [--tag name]       (the second grade added to a finished run's JSON; no GPU)
// Writes tests/out/layered_rock/replay<tag>.json and the port's logs under tests/out/layered_rock/replay<tag>/.
// JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as RP from '../parity/replay.mjs';
import * as RUN from '../../run.js';
import * as S from '../../solvers/strata.js';
import { C, RECIPES, W, argsOf, finish, floorRun, reviveRiver } from './_layered.mjs';

const A = argsOf();
const recipes = A.recipes ? String(A.recipes).split(',') : RECIPES;
const seeds = A.seeds ? String(A.seeds).split(',').map(Number) : [1, 2];
const ops = A.ops ? String(A.ops).split(',') : ['strata', 'plateau', 'river_path', 'strata_fluvial'];
const LEVELS = A.levels ?? 'all';
const MAX = A.max ? Number(A.max) : Infinity;
const TAG = A.tag ? `_${A.tag}` : '';

const T = new C.Checks('layered_rock: stage replay on the Blender floor runs');
const R = A.regrade ? null : await G.init();
const registry = await import('../../recipes/index.js');
const DP = await import('../parity/dispatch_parity.mjs');

// the run-wide snapshot alignment (see the top): ALIGN.map holds 'kernel#n' (the call's n-th dispatch) -> Blender's
// run-wide key; the hook takes those snapshots besides the parity tool's own
let ALIGN = null;
const RUN_WIDE = /^[^#]+#\d+$/;
const isCallKey = (k) => /^L\d+_c\d+_/.test(k);
const baseDispatch = RP.PortLog.prototype._dispatch;
RP.PortLog.prototype._dispatch = function (r) {
    const before = this.pending.length;
    baseDispatch.call(this, r);
    if (!ALIGN) return;
    const std = `${r.kernel}#${r.count}`;
    // the tool's own run-wide key for this dispatch (the call's count) names Blender's snapshot of that name only
    // where the alignment says it is the same dispatch; otherwise it is dropped, so the aligned one keeps the name
    if (this.pending.length > before && ALIGN.map.get(std) !== std) {
        const p = this.pending[this.pending.length - 1];
        const keep = p.keys.filter((k) => k !== std);
        if (keep.length !== p.keys.length) {
            if (keep.length) p.keys = keep;
            else {
                this.pending.pop();
                for (const f of p.copies) f.destroy();
            }
        }
    }
    if (!r.blender || !r.images || !Object.keys(r.images).length) return;
    const bk = ALIGN.map.get(std);
    if (!bk) return;
    ALIGN.taken.add(bk);
    if (bk === std && RP.SNAP_AT.includes(r.count)) return;   // the tool's own key is that dispatch
    const ctx = this.G.context;
    const names = Object.keys(r.samplers ?? {}).sort();
    const fields = Object.entries(r.images);
    if (this.opts.inputs) for (const nm of names) fields.push([`in__${nm}`, r.samplers[nm]]);
    const copies = r.runner.snapshot(fields.map(([, f]) => f));
    this.pending.push({ keys: [bk], d: r.index - 1 - this.base, kernel: r.kernel, op: ctx.op, call: ctx.call, level: ctx.level,
        runner: r.runner, names: fields.map(([nm]) => nm), copies });
};

/** Blender's run-wide snapshot keys of a call, as the call's own counts: Map('kernel#n' -> 'kernel#N'). */
async function alignment(run, call) {
    run._log ??= await DP.loadRun(run.dir);
    const lines = run._log.dispatches;
    const first = lines.findIndex((d) => d[5]?.call === call);
    const map = new Map();
    if (first < 0) return map;
    for (const [key, ent] of Object.entries(run.snapIndex)) {
        if (!RUN_WIDE.test(key) || isCallKey(key) || ent.call !== call) continue;
        let n = 0;
        for (let i = first; i <= ent.d && i < lines.length; i++) if (lines[i][1] === ent.kernel) n++;
        if (n > 0) map.set(`${ent.kernel}#${n}`, key);
    }
    return map;
}

/** Keep in the port's snapshot index only the run-wide keys that are aligned (and every per-call key). */
function pruneIndex(logDir, taken) {
    const path = `${logDir}/snap/index.json`;
    const idx = C.readJson(path);
    if (!idx) return [];
    const dropped = [];
    for (const k of Object.keys(idx.snapshots)) {
        if (RUN_WIDE.test(k) && !isCallKey(k) && !taken.has(k)) {
            delete idx.snapshots[k];
            dropped.push(k);
        }
    }
    Deno.writeTextFileSync(path, JSON.stringify(idx, null, 1));
    return dropped;
}

// [max, RMS, p99] of |got - want| over want's range, as the floor records them (p99 numpy's linear percentile)
function rmsP99(g, w) {
    let lo = Infinity, hi = -Infinity, amax = 0, s = 0, n = 0;
    const d = new Float64Array(w.length);
    for (let i = 0; i < w.length; i++) {
        if (!Number.isFinite(w[i]) || !Number.isFinite(g[i])) continue;
        lo = Math.min(lo, w[i]);
        hi = Math.max(hi, w[i]);
        amax = Math.max(amax, Math.abs(w[i]));
        d[n++] = Math.abs(g[i] - w[i]);
        s += (g[i] - w[i]) ** 2;
    }
    const r = (hi - lo) || amax || 1;
    const e = d.slice(0, n).sort();
    const pos = 0.99 * Math.max(n - 1, 0), k = Math.floor(pos);
    const p99 = n ? e[k] + (pos - k) * (e[Math.min(k + 1, n - 1)] - e[k]) : 0;
    return { rms: Math.sqrt(s / Math.max(n, 1)) / r, p99: p99 / r, max: (n ? e[n - 1] : 0) / r };
}

function compareControl(mine, theirs) {
    if (!mine || !theirs) return { ok: false, diffs: ['no fluvial_log record'] };
    const EXACT = ['role', 'steps', 'dt_yr', 'years', 'spacing_m', 'creep_sub', 'lock_block_cells', 'lock_m', 'prepass'];
    const diffs = [];
    for (const k of EXACT) if (JSON.stringify(mine[k] ?? null) !== JSON.stringify(theirs[k] ?? null)) diffs.push(`${k}: ${mine[k]} / ${theirs[k]}`);
    const dRel = Math.abs(mine.D - theirs.D) / Math.max(Math.abs(theirs.D), 1e-300);
    if (dRel > 1e-12) diffs.push(`D: ${mine.D} / ${theirs.D}`);
    return { ok: diffs.length === 0, diffs, caprock: { port: mine.caprock, blender: theirs.caprock },
        caprock_frac: [mine.caprock_frac ?? null, theirs.caprock_frac ?? null],
        dry_basin_cells: [mine.dry_basin_cells, theirs.dry_basin_cells] };
}

/** The fields by RMS and p99 of |d| against the stage floor's samples ([max, RMS, p99] each): each within
 * max(1e-4, 1.25 x the largest sample), the fluvial package's second grade (tests/fluvial/replay_test.mjs gradeRms). */
function gradeRms(run, st, dist) {
    const floor = run.floors[st.call]?.floor ?? {};
    const out = { ok: true, fields: {} };
    for (const [name, d] of Object.entries(dist)) {
        const s = floor[name]?.samples ?? [];
        const frms = Math.max(0, ...s.map((x) => x[1] ?? 0)), fp99 = Math.max(0, ...s.map((x) => x[2] ?? 0));
        const ok = d.rms <= Math.max(1e-4, 1.25 * frms) && d.p99 <= Math.max(1e-4, 1.25 * fp99);
        out.fields[name] = { ...d, floor_rms: frms, floor_p99: fp99, ok };
        if (!ok) out.ok = false;
    }
    return out;
}

// the largest RMS / range the perturbed floor runs show at each snapshot, per image and channel (their sample.json)
function snapFloorRms(run) {
    if (run._snapRms) return run._snapRms;
    const out = {};
    for (let p = 1; p <= 9; p++) {
        const s = C.readJson(`${run.dir}/../p${p}/sample.json`);
        for (const [key, rec] of Object.entries(s?.snapshots ?? {})) {
            for (const [im, chans] of Object.entries(rec)) {
                if (!Array.isArray(chans)) continue;
                const cur = (out[key] ??= {})[im] ??= chans.map(() => 0);
                chans.forEach((v, c) => { if (v && v[1] != null) cur[c] = Math.max(cur[c], v[1]); });
            }
        }
    }
    return (run._snapRms = out);
}

/** The compared snapshots (the port's index after the alignment) by RMS of |d| / range against the floor's RMS at
 * that snapshot: within max(1e-4, 1.25 x the largest sample), as the fluvial package grades them. */
async function snapshotRms(run, logDir) {
    const mine = C.readJson(`${logDir}/snap/index.json`, { snapshots: {} }).snapshots;
    const floor = snapFloorRms(run);
    const out = { ok: true, compared: 0, worst_ratio: 0, failures: [] };
    for (const [key, ent] of Object.entries(mine)) {
        const base = run.snapIndex[key];
        if (!base) continue;
        const a = await RP.npz(`${run.dir}/snap/${base.file}`), b = await RP.npz(`${logDir}/snap/${ent.file}`);
        for (const [im, want] of Object.entries(a)) {
            const got = b[im];
            if (!got || got.data.length !== want.data.length) continue;
            const ch = want.shape[2] ?? 1, n = want.data.length / ch;
            for (let c = 0; c < ch; c++) {
                let lo = Infinity, hi = -Infinity, amax = 0, sq = 0, cnt = 0;
                for (let i = 0; i < n; i++) {
                    const w = want.data[i * ch + c], g = got.data[i * ch + c];
                    if (!Number.isFinite(w) || !Number.isFinite(g)) continue;
                    if (w < lo) lo = w;
                    if (w > hi) hi = w;
                    amax = Math.max(amax, Math.abs(w));
                    sq += (g - w) ** 2;
                    cnt++;
                }
                const range = (hi - lo) || amax || 1.0;
                const rms = Math.sqrt(sq / Math.max(cnt, 1)) / range;
                const flr = floor[key]?.[im]?.[c] ?? 0;
                const tol = Math.max(1e-4, 1.25 * flr) + 16 * C.ulp32(amax) / range;
                out.compared++;
                out.worst_ratio = Math.max(out.worst_ratio, rms / tol);
                if (!(rms <= tol)) {
                    out.ok = false;
                    if (out.failures.length < 40) out.failures.push({ key, image: im, channel: c, rms, tol, floor: flr });
                }
            }
        }
    }
    return out;
}

if (A.regrade) {
    // --regrade: the second grade added to a finished replay<tag>.json from what it kept (each field's [max, RMS,
    // p99] and the port's snapshots under replay<tag>/), without the GPU
    const path = `${W.out('layered_rock')}/replay${TAG}.json`;
    const old = C.readJson(path);
    if (!old) { console.log(`no ${path}`); Deno.exit(2); }
    const runs = {};
    for (const r of old.results) {
        if (r.error || !r.stage) continue;
        const key = `${r.recipe}_s${r.seed}`;
        runs[key] ??= await RP.loadRun(floorRun(r.recipe, r.seed));
        const run = runs[key], st = run.stages.find((x) => x.call === r.stage.call);
        const logDir = `${W.out('layered_rock')}/replay${TAG}/${key}/c${st.call}_${st.op}`;
        const dist = r.fields_rms?.fields ?? r.fields_rms ?? {};
        r.fields_rms = gradeRms(run, st, Object.fromEntries(Object.entries(dist).map(([k, v]) => [k, { rms: v.rms, p99: v.p99, max: v.max }])));
        r.snapshots_rms = await snapshotRms(run, logDir);
        r.ok_rms = r.fields_rms.ok && !!r.dispatch?.ok && r.snapshots_rms.ok && (r.pins ? r.pins.ok : true) && (r.control ? r.control.ok : true);
        const bad = Object.entries(r.fields_rms.fields).filter(([, q]) => !q.ok).map(([k, q]) => `${k} RMS ${C.sci(q.rms)} (floor ${C.sci(q.floor_rms)}), p99 ${C.sci(q.p99)} (floor ${C.sci(q.floor_p99)})`);
        console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${key} L${st.level} p${st.pass_index} ${st.op} (call ${st.call}): by RMS and p99 ${r.ok_rms ? 'within' : 'OVER'}` +
            ` (${r.snapshots_rms.compared} snapshot channels, worst RMS ${C.sci(r.snapshots_rms.worst_ratio)} of its tolerance)` + (bad.length ? `; ${bad.join('; ')}` : '') +
            (r.snapshots_rms.failures.length ? `; snapshots ${r.snapshots_rms.failures.slice(0, 3).map((s) => `${s.key} ${s.image}[${s.channel}] ${C.sci(s.rms)} (tol ${C.sci(s.tol)})`).join(', ')}` : ''));
    }
    const by = {};
    for (const r of old.results) {
        const k = r.stage?.op ?? 'error';
        by[k] ??= { calls: 0, ok: 0, ok_rms: 0 };
        by[k].calls++;
        if (r.ok) by[k].ok++;
        if (r.ok_rms) by[k].ok_rms++;
    }
    for (const [op, b] of Object.entries(by)) {
        console.log(`${op}: ${b.ok} of ${b.calls} calls within the stage grades, ${b.ok_rms} of ${b.calls} by RMS and p99`);
        if (old.by_op?.[op]) old.by_op[op].ok_rms = b.ok_rms;
    }
    old.regraded = new Date().toISOString();
    Deno.writeTextFileSync(path, JSON.stringify(old, null, 1));
    Deno.exit(0);
}

const results = [];
for (const recipe of recipes) {
    for (const seed of seeds) {
        const dir = floorRun(recipe, seed);
        if (!dir) { T.ok(`${recipe} s${seed}: a floor run`, false, 'no floor run (tests/parity/floor_runs.sh)'); continue; }
        const run = await RP.loadRun(dir);
        const main = run.header.main_index;
        const want = LEVELS === 'all' ? null : LEVELS === 'main' ? [main] : String(LEVELS).split(',').map(Number);
        let calls = 0;
        for (const st of run.stages) {
            if (!ops.includes(st.op) || (want && !want.includes(st.level))) continue;
            if (calls++ >= MAX) break;
            const logDir = `${W.out('layered_rock')}/replay${TAG}/${recipe}_s${seed}/c${st.call}_${st.op}`;
            const dist = {};
            let shared = null, pinsCheck = null, opSeconds = null;
            ALIGN = { map: await alignment(run, st.call), taken: new Set() };
            const invoke = async (op, a) => {
                const c = a.ctx;
                if (c?.shared?.river?.__class__) c.shared.river = reviveRiver(c.shared.river, c.sharedArrays);
                const sc = new RUN.StageContext({ ...c, device: R });
                const t0 = performance.now();
                await op(a.fields, a.level, a.params, a.seed, sc);
                await R.idle();
                opSeconds = +((performance.now() - t0) / 1000).toFixed(3);
                shared = sc.shared;
                const after = await RP.npz(`${run.dir}/stages/${st.after}`);
                for (const [name, w] of Object.entries(after)) {
                    if (name.startsWith('shared__') || w.shape.length !== 2 || w.dtype !== '<f4' || !(name in a.fields)) continue;
                    dist[name] = rmsP99(await R.read(a.fields[name]), w.data);
                }
                if (st.op === 'river_path') {
                    // the pins the next stage of the same pass received in Blender's run
                    const nxt = run.stages.find((x) => x.call === st.call + 1 && x.level === st.level && x.pass_index === st.pass_index);
                    if (nxt) {
                        const b = await RP.npz(`${run.dir}/stages/${nxt.before}`);
                        const gw = await R.read(sc.pins.pin_w), gh = await R.read(sc.pins.pin_h);
                        const ww = b.pin__pin_w.data, wh = b.pin__pin_h.data;
                        let wDiff = 0;
                        for (let i = 0; i < ww.length; i++) if (gw[i] !== ww[i]) wDiff++;
                        const gH = C.gradeArray(gh, wh, { k: 1e-5, uses: ['sqrt', 'divide', 'pow', 'sin'] });
                        pinsCheck = { ok: wDiff === 0 && gH.ok, weight_cells_differ: wDiff, height_over: gH.over, height_err_m: gH.err,
                            height_tol_m: gH.tol };
                    }
                }
            };
            // the caprock check (strata.js CONVERGENCE_LOOPS) stops the whole step loop, so every kernel of the step may
            // run fewer or more times by whole check intervals: a lookup that answers for any of this op's kernels
            const capped = st.op === 'strata_fluvial' && st.params.caprock_target != null && st.params.caprock_zs_m != null;
            const every = Math.max(Math.trunc(Number(S._q(st.params, 'check_every'))), 1);
            const intervals = capped ? new Proxy({}, { get: (_t, k) => (typeof k === 'string' && k.startsWith('strata_fluvial|') ? every : undefined) }) : {};
            const r = await RP.replayStage(R, G, run, st, await registry.getOp(st.op), { logDir, invoke, intervals });
            r.op_seconds = opSeconds;
            if (!r.error) {
                // the snapshots again, with the run-wide keys aligned (see the top)
                r.snapshots_set_aside = pruneIndex(logDir, ALIGN.taken);
                r.snapshots = await RP.compareSnapshots(run, logDir);
                r.ok = r.fields.ok && r.dispatch.ok && r.snapshots.ok;
                r.fields_rms = gradeRms(run, st, dist);
                r.snapshots_rms = await snapshotRms(run, logDir);
                r.ok_rms = r.fields_rms.ok && r.dispatch.ok && r.snapshots_rms.ok;
                if (pinsCheck) {
                    r.pins = pinsCheck;
                    r.ok = r.ok && pinsCheck.ok;
                    r.ok_rms = r.ok_rms && pinsCheck.ok;
                }
                if (st.op === 'strata_fluvial') {
                    r.control = compareControl(shared?.fluvial_log?.at(-1) ?? null, st.shared_after?.fluvial_log?.at(-1) ?? null);
                    r.ok = r.ok && r.control.ok;
                    r.ok_rms = r.ok_rms && r.control.ok;
                }
            }
            const worst = Object.entries(r.fields?.fields ?? {}).sort((x, y) => y[1].over - x[1].over)[0];
            const line = `${recipe} s${seed} L${st.level} p${st.pass_index} ${st.op} (call ${st.call}): ` + (r.error ? r.error :
                `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, ` +
                `floor ${C.sci(worst[1].floor)}` : 'none'}${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}` +
                `${r.fields.extra.length ? `; extra ${r.fields.extra}` : ''}), dispatch log ${r.dispatch.ok ? 'equal' : 'DIFFERS'}, ` +
                `${r.snapshots.compared} snapshot channels ${r.snapshots.ok ? 'within tolerance' : 'OVER'} ` +
                `(worst ${C.sci(r.snapshots.worst)}); op ${r.op_seconds} s (Blender ${st.seconds} s)` +
                (r.pins ? `; pins ${r.pins.ok ? 'equal' : 'DIFFER'} (weights differ on ${r.pins.weight_cells_differ} cells, ` +
                    `height ${C.sci(r.pins.height_over)} of range)` : '') +
                (r.control ? `; control ${r.control.ok ? 'equal' : 'DIFFERS: ' + r.control.diffs.join(', ')} (dry basins ` +
                    `${r.control.dry_basin_cells.join(' / ')}, caprock ${JSON.stringify(r.control.caprock_frac)})` : ''));
            console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${line}` + (r.error ? '' : `; by RMS and p99 ${r.ok_rms ? 'within' : 'OVER'}`));
            if (!r.ok && !r.error) {
                for (const [k, g] of Object.entries(r.fields.fields)) {
                    const q = r.fields_rms.fields[k];
                    if (g.ok && q?.ok !== false) continue;
                    console.log(`       field ${k}: ${C.sci(g.over)} of range (tol ${C.sci(g.tol / (g.range || 1))}, floor ${C.sci(g.floor)}); ` +
                        `RMS ${C.sci(q?.rms)} (floor ${C.sci(q?.floor_rms)}), p99 ${C.sci(q?.p99)} (floor ${C.sci(q?.floor_p99)})`);
                }
                for (const s of r.snapshots_rms.failures.slice(0, 4)) console.log(`       snapshot RMS ${s.key} ${s.image}[${s.channel}]: ${C.sci(s.rms)} of range (tol ${C.sci(s.tol)}, floor ${C.sci(s.floor)})`);
                for (const s of (r.dispatch.structure_differences ?? []).slice(0, 4)) console.log(`       shape: ${s.slice(0, 500)}`);
                for (const s of (r.dispatch.counts_that_differ ?? []).slice(0, 4)) console.log(`       count: ${JSON.stringify(s)}`);
                for (const s of (r.dispatch.uniform_failures ?? []).slice(0, 4)) console.log(`       uniform: ${s.kernel}.${s.uniform} ${JSON.stringify(s.a)} vs ${JSON.stringify(s.b)} (${C.sci(s.rel)} rel)`);
                for (const s of (r.dispatch.image_differences ?? []).slice(0, 4)) console.log(`       image: ${String(s).slice(0, 300)}`);
                for (const s of r.snapshots.failures.slice(0, 6)) console.log(`       snapshot ${s.key} ${s.image}[${s.channel}]: ${C.sci(s.over)} of range (tol ${C.sci(s.tol)}, floor ${C.sci(s.floor)})`);
            }
            results.push({ recipe, seed, ...r });
        }
    }
}

const byOp = {};
for (const r of results) {
    const k = r.stage?.op ?? 'error';
    byOp[k] ??= { calls: 0, ok: 0, ok_rms: 0, fields_ok: 0, dispatch_ok: 0, snapshots_ok: 0 };
    byOp[k].calls++;
    if (r.ok) byOp[k].ok++;
    if (r.ok_rms) byOp[k].ok_rms++;
    if (r.fields?.ok) byOp[k].fields_ok++;
    if (r.dispatch?.ok) byOp[k].dispatch_ok++;
    if (r.snapshots?.ok) byOp[k].snapshots_ok++;
}
for (const [op, b] of Object.entries(byOp)) {
    T.ok(`${op}: ${b.ok} of ${b.calls} calls replayed within the stage grades (fields ${b.fields_ok}, dispatch logs ${b.dispatch_ok}, ` +
        `snapshots ${b.snapshots_ok}; by RMS and p99 ${b.ok_rms} of ${b.calls})`, b.ok === b.calls && b.calls > 0);
}
Deno.exit(finish(T, `replay${TAG}`, { by_op: byOp, results: results.map((r) => ({ recipe: r.recipe, seed: r.seed, stage: r.stage,
    ok: r.ok, ok_rms: r.ok_rms ?? false, error: r.error ?? null, seconds: r.seconds, blender_seconds: r.blender_seconds,
    op_seconds: r.op_seconds, fields: r.fields, fields_rms: r.fields_rms, snapshots_rms: r.snapshots_rms ?? null,
    pins: r.pins ?? null, control: r.control ?? null, dispatch: r.dispatch ? { ok: r.dispatch.ok,
        structure: r.dispatch.structure_differences, counts: r.dispatch.counts_that_differ?.slice(0, 20),
        uniform_failures: r.dispatch.uniform_failures, images: r.dispatch.image_differences,
        worst_uniforms: r.dispatch.worst_uniforms } : null, snapshots: r.snapshots ? { ok: r.snapshots.ok,
        compared: r.snapshots.compared, worst: r.snapshots.worst, failures: r.snapshots.failures } : null })) }));
