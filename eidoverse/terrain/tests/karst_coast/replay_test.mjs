// Stage replay of the karst and coast ops on the Blender edition's own dumps (PORT_PLAN.md 8.2 row P11, 5.1, 5.3,
// 5.7): each call of karst, coast_land and coast in the tower_karst and sea_cliffs floor runs, replayed by the port's
// op from that call's own input (its stage dump: fields, pins, context), through tests/parity/replay.mjs replayStage:
//   fields      every field after the op against Blender's: max |d| <= max(1e-4 x range, 1.25 x the stage's floor,
//               16 float32 steps) (the floor: tests/parity/blender_stage_dump.py --floor, five patterns; karst's is 0:
//               it reads none of its input and is deterministic, so its grade is the kernel grade)
//   dispatches  the call's Blender kernels in order and number (karst: none; coast: coast_fetch_16, coast_seed and the
//               jump flood's coast_jfa steps, world_noise_field for the retreat's, face's, talus', platform's and
//               shingle's noise; coast_land: world_noise_field, and on the finer levels the fluvial backbone's
//               refine), every uniform within 4 float32 steps, the bound images' names, sizes and formats (the port's
//               own kernels set aside: tests/parity/dispatch_parity.mjs)
//   snapshots   each Blender kernel's images and inputs after its 1st, 10th, 100th ... dispatch, against Blender's
//               snapshots of the same call (the main level's in-call keys, and the run-wide keys that are also the
//               call's own n-th dispatch of their kernel: the port's counts start at the replayed call; the others
//               are set aside and named, as tests/detail/replay_test.mjs rules)
//   warm-up     a replay of karst on a finer level first runs the run's earlier karst calls (replay.mjs WARM: the
//               plan's domain is set by the coarsest level's call)
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/karst_coast/replay_test.mjs
//         [--runs tower_karst_s1,sea_cliffs_s2] [--ops karst,coast] [--levels 0,2]   (behind $EIDO_GPU_WRAP)
//
// A floor run missing under the parity key is taken from another key of the same Blender terrain code. Writes
// tests/out/karst_coast/replay_test.json and the port's logs under tests/out/karst_coast/replay/. JavaScript per cell
// here is test code.

import * as G from '../../core/gpu.js';
import * as IO from '../../core/io.js';
import * as CO from '../../solvers/coast.js';
import * as K from '../../solvers/karst.js';
import * as DP from '../parity/dispatch_parity.mjs';
import * as RP from '../parity/replay.mjs';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const W = C.W;
const args = [...Deno.args];
const list = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1].split(',') : null; };
const OPS = { karst: K.opKarst, coast_land: CO.opCoastLand, coast: CO.opCoast };
const WANT_OPS = list('--ops') ?? Object.keys(OPS);
const LEVELS = list('--levels')?.map(Number) ?? null;
const RUNS = list('--runs') ?? ['tower_karst_s1', 'tower_karst_s2', 'sea_cliffs_s1', 'sea_cliffs_s2'];
const DUMP = args.includes('--dump');       // also write each replayed call's fields after the op (<logDir>/after.npz)

/** With --dump: the op called as replayStage would, then the level's 2-D float fields written to `file` (the warm-up's
 * calls write it too; the replayed call's own comes last). */
const dumper = (file) => async (op, a) => {
    await op(a.fields, a.level, a.params, a.seed, a.ctx);
    const names = Object.keys(a.fields).filter((k) => a.fields[k]?.kind === 'f32' && a.fields[k]?.channels === 1);
    const data = await a.fields.R.readAll(names.map((k) => a.fields[k]));
    const n = a.level.n;
    await IO.writeNpz(file, Object.fromEntries(names.map((k, i) => [k, IO.npArray(data[i], [n, n])])));
};

/** Blender's snapshots of one call that the port's replay of it can match (see the top): { snapIndex, aside }. */
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

const T = new C.Checks('karst and coast: stage replay on the Blender dumps');
const R = await G.init();
const results = [];
for (const name of RUNS) {
    const m = /^(.*)_s(\d+)$/.exec(name);
    const found = m ? KC.floorRunOfCode(m[1], Number(m[2])) : null;
    if (!found) { console.log(`[skip] ${name}: no floor run with stage dumps (tests/parity/floor_runs.sh)`); continue; }
    const [dir, key] = found;
    const run = await RP.loadRun(dir);
    K.clearMemos();
    for (const st of run.stages) {
        if (!(st.op in OPS) || !WANT_OPS.includes(st.op)) continue;
        if (LEVELS && !LEVELS.includes(st.level)) continue;
        const { snapIndex, aside } = await callSnapshots(run, st.call);
        const view = { ...run, snapIndex };
        const logDir = `${W.out('karst_coast')}/replay/${name}/c${st.call}_${st.op}_L${st.level}`;
        if (DUMP) Deno.mkdirSync(logDir, { recursive: true });
        const r = await RP.replayStage(R, G, view, st, OPS[st.op], { logDir, invoke: DUMP ? dumper(`${logDir}/after.npz`) : undefined });
        run._log ??= view._log;
        run._known ??= view._known;
        const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
        const d = r.dispatch ?? {};
        const lvd = run.header.plan?.[st.level];
        const line = `${name} L${st.level}${lvd ? ` (${lvd.role} ${lvd.cell} m x${st.window?.n ?? lvd.n})` : ''} p${st.pass_index} ${st.op} ` +
            `(call ${st.call}): ` + (r.error ? r.error :
            `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, ` +
                `grade ${C.sci(worst[1].tol / (worst[1].range || 1))}` : 'none'}${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}` +
            `${r.fields.extra.length ? `; extra ${r.fields.extra}` : ''}), dispatch log ${d.ok ? 'equal' : 'DIFFERS'} ` +
            `(${d.compared_dispatches} Blender dispatches compared, ${d.uniforms_over_4_steps} uniforms over 4 steps), ` +
            `${r.snapshots.keys} snapshots (${r.snapshots.compared} channels) ${r.snapshots.ok ? 'within tolerance' : 'OVER'} ` +
            `worst ${C.sci(r.snapshots.worst)}${aside.length ? `, ${aside.length} run-wide set aside` : ''}; ${r.seconds} s ` +
            `(Blender ${st.seconds} s)${key && key !== W.parityKeyDir()?.split('/').pop() ? ` [floor run of key ${key}]` : ''}`);
        T.ok(line, r.ok, '');
        if (!r.ok && !r.error) {
            if (!r.fields.ok) console.log('     fields over:', JSON.stringify(Object.entries(r.fields.fields).filter(([, g]) => !g.ok).map(([k, g]) => [k, C.sci(g.over), C.sci(g.floor)])));
            if (!d.ok) console.log('     dispatch:', JSON.stringify({ structure: d.structure_differences, counts: d.counts_that_differ?.slice(0, 5), uniforms: d.uniform_failures?.slice(0, 5), images: d.image_differences }).slice(0, 2000));
            if (!r.snapshots.ok) console.log('     snapshots:', JSON.stringify(r.snapshots.failures.slice(0, 8)), JSON.stringify(r.snapshots.shapes));
        }
        results.push({ run: name, key, ...r, snapshots_set_aside: aside, fields: r.fields ? { ok: r.fields.ok, missing: r.fields.missing,
            extra: r.fields.extra, worst: worst ? { field: worst[0], ...worst[1] } : null, all: r.fields.fields } : null });
    }
}
T.ok(`${results.length} replays ran`, results.length > 0, '');
const code = KC.finish(T, 'replay_test', { results });
G.shutdown();
Deno.exit(code);
