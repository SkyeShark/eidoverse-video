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

/** The step snapshots of a replay against Blender's: only the keys that name the same dispatch (see the top). */
export async function compareSnapshots(run, st, portDir) {
    const mine = C.readJson(`${portDir}/snap/index.json`, { snapshots: {} }).snapshots;
    run._log ??= await DP.loadRun(run.dir);
    if (!run._first) {
        run._first = {};                                    // kernel -> the op call of its first dispatch in the run
        for (const d of run._log.dispatches) if (!(d[1] in run._first)) run._first[d[1]] = d[5]?.call ?? null;
    }
    const out = { ok: true, compared: 0, keys: 0, worst: 0, failures: [], skipped: [], shapes: [] };
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
                let lo = Infinity, hi = -Infinity, amax = 0, err = 0;
                for (let i = 0; i < n; i++) {
                    const w = want.data[i * ch + c], g = got.data[i * ch + c];
                    if (!Number.isFinite(w) || !Number.isFinite(g)) { if (!(w === g || (w !== w && g !== g))) err = Infinity; continue; }
                    if (w < lo) lo = w;
                    if (w > hi) hi = w;
                    amax = Math.max(amax, Math.abs(w));
                    err = Math.max(err, Math.abs(g - w));
                }
                const range = (hi - lo) || amax || 1.0;
                const fl = run.snapFloor[key]?.[im]?.[c] ?? 0;
                const tol = Math.max(1e-4, 1.25 * fl) * range + 16 * C.ulp32(amax);
                out.compared++;
                out.worst = Math.max(out.worst, err / range);
                if (!(err <= tol)) {
                    out.ok = false;
                    if (out.failures.length < 40) out.failures.push({ key, image: im, channel: c, over: err / range, tol: tol / range, floor: fl });
                }
            }
        }
    }
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
            const r = await RP.replayStage(R, G, run, st, await registry.getOp(st.op), { logDir });
            if (!r.error) {
                r.snapshots_replay_mjs = { ok: r.snapshots.ok, compared: r.snapshots.compared };
                r.snapshots = await compareSnapshots(run, st, logDir);
                r.ok = r.fields.ok && r.dispatch.ok && r.snapshots.ok;
            }
            const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
            const line = `${recipe} s${seed} L${st.level} p${st.pass_index} ${st.op} (call ${st.call}): ` + (r.error ? r.error :
                `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, floor ${C.sci(worst[1].floor)}` : 'none'}` +
                `${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}), dispatch log ${r.dispatch.ok ? 'equal' : 'DIFFERS'}, ` +
                `${r.snapshots.compared} snapshot channels ${r.snapshots.ok ? 'within tolerance' : 'OVER'} (worst ${C.sci(r.snapshots.worst)}); ` +
                `${r.seconds} s (Blender ${st.seconds} s)`);
            console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${line}`);
            if (!r.ok && !r.error) {
                for (const [k, g] of Object.entries(r.fields.fields)) if (!g.ok) console.log(`       field ${k}: ${C.sci(g.over)} of range (tol ${C.sci(g.tol / (g.range || 1))}, floor ${C.sci(g.floor)})`);
                for (const s of (r.dispatch.structure_differences ?? []).slice(0, 4)) console.log(`       shape: ${s.slice(0, 400)}`);
                for (const s of (r.dispatch.counts_that_differ ?? []).slice(0, 4)) console.log(`       count: ${JSON.stringify(s)}`);
                for (const s of (r.dispatch.uniform_failures ?? []).slice(0, 4)) console.log(`       uniform: ${s.kernel}.${s.uniform} ${JSON.stringify(s.a)} vs ${JSON.stringify(s.b)} (${C.sci(s.rel)} rel)`);
                for (const s of (r.dispatch.image_differences ?? []).slice(0, 4)) console.log(`       image: ${s.slice(0, 300)}`);
                for (const s of r.snapshots.failures.slice(0, 6)) console.log(`       snapshot ${s.key} ${s.image}[${s.channel}]: ${C.sci(s.over)} of range (tol ${C.sci(s.tol)}, floor ${C.sci(s.floor)})`);
                for (const s of r.snapshots.shapes.slice(0, 4)) console.log(`       snapshot shape: ${s}`);
            }
            results.push(r);
            T.ok(line.split(':')[0], r.ok, r.error ?? '');
        }
        all.push({ recipe, seed, results });
        Deno.writeTextFileSync(`${W.out('fluvial')}/replay_${recipe}_s${seed}.json`, JSON.stringify({ recipe, seed, date: new Date().toISOString(),
            replayed: results.length, passed: results.filter((r) => r.ok).length, results }, null, 1));
    }
}
const n = T.rows.length, pass = T.rows.filter((r) => r.passed).length;
console.log(`${pass} of ${n} stages pass`);
G.shutdown();
Deno.exit(pass === n && n > 0 ? 0 : 1);
