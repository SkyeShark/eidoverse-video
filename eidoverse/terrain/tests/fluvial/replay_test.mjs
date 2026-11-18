// Stage replay of the fluvial package's ops (PORT_PLAN.md 8.2 row P6, 5.3, 5.7): each op call of a Blender floor
// run, from Blender's own dumped input, through the port's op, against Blender's dumped output, with the call's
// dispatch log and step snapshots beside Blender's.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/replay_test.mjs
//         [--recipes rolling_hills,fluvial_range,meadow] [--seeds 1,2] [--ops uplift,fluvial,...]
//         [--levels all | main | 0,3] [--max-calls N]          (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Per stage (tests/parity/replay.mjs replayStage does the work):
//   fields     every field after the op within max(1e-4 x its range, 1.25 x the stage's floor sample, 16 float32
//              steps) of Blender's (blender_stage_dump.py --floor measured the floors of the main level's stages; a
//              level without a floor gets the kernel grade)
//   dispatches the call's Blender kernels, counts, uniforms and bound images against Blender's log of the same call
//   snapshots  the images and inputs of each Blender kernel after its 1st, 10th and 100th dispatch in the call (main
//              level), and after its 1st, 10th ... dispatch of the run where the replayed call is the run's first
//              to dispatch that kernel, against Blender's, at max(1e-4 x range, 1.25 x the floor's sample there).
//              replay.mjs's own snapshot comparison pairs the replay's counts (which start at 1 in the call) with
//              Blender's counts over the whole run, which name other dispatches after a kernel's first call; this
//              test pairs only the counts that mean the same dispatch (reported to the lead for replay.mjs).
// Beside the plan's grades, which take each field's (and snapshot channel's) single worst cell, the test reports the
// same comparison by the field's RMS and 99th percentile of |d| (the floor samples record all three: [max, RMS, p99]
// of the stage floor, [max, RMS] of the snapshots), each within max(1e-4, 1.25 x the largest sample): on the routed
// quantities of a chaotic op (A and qs one step lagged, the deposit of pinned and filled cells) one cell's jump
// decides the worst-cell number, and five samples bound it loosely. A stage passes the plan's grade (`ok`); `ok_rms`
// says whether it passes by RMS and p99 instead.
// JavaScript per cell here is test code. Writes tests/out/fluvial/replay_<recipe>_s<seed>.json.

import * as G from '../../core/gpu.js';
import * as RP from '../parity/replay.mjs';
import * as DP from '../parity/dispatch_parity.mjs';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const RECIPES = opt('--recipes', 'rolling_hills').split(',');
const SEEDS = opt('--seeds', '1').split(',').map(Number);
const MINE = ['uplift', 'fluvial', 'valley_floor', 'incise', 'creep', 'talus', 'threshold', 'soil_hills', 'hummocks'];
const OPS = opt('--ops', MINE.join(',')).split(',');
const LEVELS = opt('--levels', 'all');
const MAX_CALLS = Number(opt('--max-calls', '100000'));

// the largest RMS / range the perturbed runs show at each snapshot, per image and channel (their sample.json)
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

/** The step snapshots of a replay against Blender's: only the keys that name the same dispatch (see the top). */
export async function compareSnapshots(run, st, portDir) {
    const mine = C.readJson(`${portDir}/snap/index.json`, { snapshots: {} }).snapshots;
    run._log ??= await DP.loadRun(run.dir);
    if (!run._first) {
        run._first = {};                                    // kernel -> the op call of its first dispatch in the run
        for (const d of run._log.dispatches) if (!(d[1] in run._first)) run._first[d[1]] = d[5]?.call ?? null;
    }
    const rmsFloor = snapFloorRms(run);
    const out = { ok: true, ok_rms: true, compared: 0, keys: 0, worst: 0, failures: [], rms_failures: [], skipped: [], shapes: [] };
    for (const [key, ent] of Object.entries(mine)) {
        const base = run.snapIndex[key];
        if (!base) continue;
        const perCall = /^L\d+_c\d+_/.test(key);
        if (!perCall && !(base.call === st.call && run._first[ent.kernel] === st.call)) { out.skipped.push(key); continue; }
        out.keys++;
        const a = await RP.npz(`${run.dir}/snap/${base.file}`), b = await RP.npz(`${portDir}/snap/${ent.file}`);
        for (const [im, want] of Object.entries(a)) {
            const got = b[im];
            if (!got) continue;
            if (want.data.length !== got.data.length) { out.shapes.push(`${key} ${im}: ${want.shape} in Blender, ${got.shape} here`); out.ok = false; continue; }
            const ch = want.shape[2] ?? 1, n = want.data.length / ch;
            for (let c = 0; c < ch; c++) {
                let lo = Infinity, hi = -Infinity, amax = 0, err = 0, sq = 0, cnt = 0;
                for (let i = 0; i < n; i++) {
                    const w = want.data[i * ch + c], g = got.data[i * ch + c];
                    if (!Number.isFinite(w) || !Number.isFinite(g)) { if (!(w === g || (w !== w && g !== g))) err = Infinity; continue; }
                    if (w < lo) lo = w;
                    if (w > hi) hi = w;
                    amax = Math.max(amax, Math.abs(w));
                    const e = Math.abs(g - w);
                    err = Math.max(err, e);
                    sq += e * e;
                    cnt++;
                }
                const range = (hi - lo) || amax || 1.0;
                const fl = run.snapFloor[key]?.[im]?.[c] ?? 0;
                const tol = Math.max(1e-4, 1.25 * fl) * range + 16 * C.ulp32(amax);
                const rms = Math.sqrt(sq / Math.max(cnt, 1));
                const flr = rmsFloor[key]?.[im]?.[c] ?? 0;
                const tolr = Math.max(1e-4, 1.25 * flr) * range + 16 * C.ulp32(amax);
                out.compared++;
                out.worst = Math.max(out.worst, err / range);
                if (!(err <= tol)) {
                    out.ok = false;
                    if (out.failures.length < 40) out.failures.push({ key, image: im, channel: c, over: err / range, tol: tol / range, floor: fl,
                        rms: rms / range, rms_floor: flr });
                }
                if (!(rms <= tolr)) {
                    out.ok_rms = false;
                    if (out.rms_failures.length < 40) out.rms_failures.push({ key, image: im, channel: c, rms: rms / range, tol: tolr / range, floor: flr });
                }
            }
        }
    }
    return out;
}

/** RMS, 99th percentile and max of |got - want| over want's range: [max, rms, p99] / range (the floor's form). */
function rmsP99(got, want) {
    let lo = Infinity, hi = -Infinity;
    for (const w of want) { if (Number.isFinite(w)) { if (w < lo) lo = w; if (w > hi) hi = w; } }
    const range = (hi - lo) || 1.0;
    const e = new Float64Array(want.length);
    let sq = 0, mx = 0;
    for (let i = 0; i < want.length; i++) {
        const d = Number.isFinite(want[i]) && Number.isFinite(got[i]) ? Math.abs(got[i] - want[i]) : (want[i] === got[i] ? 0 : Infinity);
        e[i] = d;
        sq += d * d;
        if (d > mx) mx = d;
    }
    e.sort();
    const pos = 0.99 * (e.length - 1), k = Math.floor(pos);
    const p99 = e[k] + (pos - k) * ((e[Math.min(k + 1, e.length - 1)]) - e[k]);
    return { max: mx / range, rms: Math.sqrt(sq / e.length) / range, p99: p99 / range, range };
}

/** The fields' RMS and p99 against the stage floor's samples: each within max(1e-4, 1.25 x the largest sample). */
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

/** The fluvial stage's control record (fluvial.py's info, ctx.shared.fluvial_log) against Blender's: the role, step
 * count, dt, years, diffusivity, valley spacing, creep sub-steps and the lock's block and length equal (computed from
 * the parameters and the level alone); the relief controller's U factor and its last entries reported beside
 * Blender's (they follow the relief the run measures, which is chaotic on these recipes). */
function compareFluvialLog(mine, theirs, ufMine, ufTheirs) {
    if (!mine || !theirs) return { ok: false, why: 'no fluvial_log record' };
    const EXACT = ['role', 'steps', 'dt_yr', 'years', 'spacing_m', 'creep_sub', 'lock_block_cells', 'lock_m', 'prepass'];
    const diffs = [];
    for (const k of EXACT) if (JSON.stringify(mine[k] ?? null) !== JSON.stringify(theirs[k] ?? null)) diffs.push(`${k}: ${mine[k]} / ${theirs[k]}`);
    const relD = Math.abs(mine.D - theirs.D) / Math.max(Math.abs(theirs.D), 1e-300);
    if (relD > 1e-12) diffs.push(`D: ${mine.D} / ${theirs.D}`);
    const out = { ok: diffs.length === 0, diffs, D_rel: relD, U_factor: [ufMine, ufTheirs],
        U_factor_rel: ufMine !== null && ufTheirs !== null ? Math.abs(ufMine - ufTheirs) / Math.abs(ufTheirs) : null,
        controller: { port: mine.controller ?? [], blender: theirs.controller ?? [] } };
    return out;
}

const T = new C.Checks('fluvial: stage replay on the Blender floor runs');
const R = await G.init();
const registry = await import('../../recipes/index.js');
const all = [];
for (const recipe of RECIPES) {
    for (const seed of SEEDS) {
        const dir = W.floorRun(recipe, seed);
        if (!dir) { T.ok(`${recipe} s${seed}: a floor run`, false, `no floor run (tests/parity/floor_runs.sh --recipes ${recipe} --seeds ${seed})`); continue; }
        const run = await RP.loadRun(dir);
        const main = run.header.main_index;
        const want = LEVELS === 'all' ? null : LEVELS === 'main' ? [main] : LEVELS.split(',').map(Number);
        const results = [];
        let calls = 0;
        for (const st of run.stages) {
            if (!OPS.includes(st.op) || (want && !want.includes(st.level))) continue;
            if (calls++ >= MAX_CALLS) break;
            if (!(await registry.hasOp(st.op))) { results.push({ stage: { call: st.call, op: st.op, level: st.level }, error: 'op not registered' }); continue; }
            const logDir = `${W.out('fluvial')}/replay/${recipe}_s${seed}/c${st.call}_${st.op}`;
            // the fields' RMS and p99 of |d| against Blender's after dump, read before replayStage releases them
            const dist = {};
            let record = null;
            const invoke = async (op, a) => {
                await op(a.fields, a.level, a.params, a.seed, a.ctx);
                record = a.ctx?.shared ?? null;
                const want = await RP.npz(`${run.dir}/stages/${st.after}`);
                for (const [name, w] of Object.entries(want)) {
                    if (name.startsWith('shared__') || w.shape.length !== 2 || w.dtype !== '<f4' || !(name in a.fields)) continue;
                    const g = await R.read(a.fields[name]);
                    dist[name] = rmsP99(g, w.data);
                }
            };
            const r = await RP.replayStage(R, G, run, st, await registry.getOp(st.op), { logDir, invoke });
            if (!r.error) {
                r.snapshots_replay_mjs = { ok: r.snapshots.ok, compared: r.snapshots.compared };
                r.snapshots = await compareSnapshots(run, st, logDir);
                r.ok = r.fields.ok && r.dispatch.ok && r.snapshots.ok;
                r.fields_rms = gradeRms(run, st, dist);
                r.ok_rms = r.fields_rms.ok && r.dispatch.ok && r.snapshots.ok_rms;
                if (st.op === 'fluvial') {
                    r.control = compareFluvialLog(record?.fluvial_log?.at(-1) ?? null, st.shared_after?.fluvial_log?.at(-1) ?? null,
                        record?.U_factor ?? null, st.shared_after?.U_factor ?? null);
                    r.ok = r.ok && r.control.ok;
                    r.ok_rms = r.ok_rms && r.control.ok;
                }
            }
            const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
            const line = `${recipe} s${seed} L${st.level} p${st.pass_index} ${st.op} (call ${st.call}): ` + (r.error ? r.error :
                `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, floor ${C.sci(worst[1].floor)}` : 'none'}` +
                `${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}), dispatch log ${r.dispatch.ok ? 'equal' : 'DIFFERS'}, ` +
                `${r.snapshots.compared} snapshot channels ${r.snapshots.ok ? 'within tolerance' : 'OVER'} (worst ${C.sci(r.snapshots.worst)}); ` +
                `${r.seconds} s (Blender ${st.seconds} s)`);
            console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${line}` + (r.error ? '' : `; by RMS and p99 ${r.ok_rms ? 'within' : 'OVER'}`) +
                (r.control ? `; control record ${r.control.ok ? 'equal' : 'DIFFERS: ' + r.control.diffs.join(', ')}` +
                    (r.control.U_factor_rel !== null ? ` (U factor ${r.control.U_factor[0]?.toFixed(4)} / ${r.control.U_factor[1]?.toFixed(4)})` : '') : ''));
            if (!r.ok && !r.error) {
                for (const [k, g] of Object.entries(r.fields.fields)) {
                    if (g.ok) continue;
                    const q = r.fields_rms.fields[k];
                    console.log(`       field ${k}: ${C.sci(g.over)} of range (tol ${C.sci(g.tol / (g.range || 1))}, floor ${C.sci(g.floor)}); ` +
                        `RMS ${C.sci(q?.rms)} (floor ${C.sci(q?.floor_rms)}), p99 ${C.sci(q?.p99)} (floor ${C.sci(q?.floor_p99)})`);
                }
                for (const s of (r.dispatch.structure_differences ?? []).slice(0, 4)) console.log(`       shape: ${s.slice(0, 400)}`);
                for (const s of (r.dispatch.counts_that_differ ?? []).slice(0, 4)) console.log(`       count: ${JSON.stringify(s)}`);
                for (const s of (r.dispatch.uniform_failures ?? []).slice(0, 4)) console.log(`       uniform: ${s.kernel}.${s.uniform} ${JSON.stringify(s.a)} vs ${JSON.stringify(s.b)} (${C.sci(s.rel)} rel)`);
                for (const s of (r.dispatch.image_differences ?? []).slice(0, 4)) console.log(`       image: ${s.slice(0, 300)}`);
                for (const s of r.snapshots.failures.slice(0, 6)) console.log(`       snapshot ${s.key} ${s.image}[${s.channel}]: ${C.sci(s.over)} of range (tol ${C.sci(s.tol)}, floor ${C.sci(s.floor)}); RMS ${C.sci(s.rms)} (floor ${C.sci(s.rms_floor)})`);
                for (const s of r.snapshots.shapes.slice(0, 4)) console.log(`       snapshot shape: ${s}`);
            }
            results.push(r);
            T.ok(line.split(':')[0], r.ok, r.error ?? (r.ok ? '' : `by RMS and p99: ${r.ok_rms ? 'within' : 'over'}`));
        }
        all.push({ recipe, seed, results });
        Deno.writeTextFileSync(`${W.out('fluvial')}/replay_${recipe}_s${seed}.json`, JSON.stringify({ recipe, seed, date: new Date().toISOString(),
            replayed: results.length, passed: results.filter((r) => r.ok).length,
            passed_rms: results.filter((r) => r.ok_rms).length, results }, null, 1));
    }
}
const n = T.rows.length, pass = T.rows.filter((r) => r.passed).length;
console.log(`${pass} of ${n} stages pass`);
G.shutdown();
Deno.exit(pass === n && n > 0 ? 0 : 1);
