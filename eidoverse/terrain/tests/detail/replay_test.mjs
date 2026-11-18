// Stage replay of the detail ops on the Blender edition's own dumps (PORT_PLAN.md 8.2 row P12, 5.1, 5.3, 5.7): each
// call of breakup, hydraulic, gully and planation in a Blender run, replayed by the port's op from that call's own
// input (the stage dump of its fields, pins and context), through tests/parity/replay.mjs replayStage:
//   fields      every field after the op against Blender's: max |d| <= max(1e-4 x range, 1.25 x the stage's floor,
//               16 float32 steps) (the floor: tests/parity/blender_stage_dump.py --floor, five patterns)
//   dispatches  the call's Blender kernels (breakup and pipes_thermal x iterations; world_noise_field and the four
//               pipe passes x steps; world_noise_field twice for planation; none for gully) in order and number, every
//               uniform within 4 float32 steps, the bound images' names, sizes and formats (the port's own kernels
//               set aside: tests/parity/dispatch_parity.mjs)
//   snapshots   each kernel's images and inputs after its 1st, 10th, 100th, 1,000th and 10,000th dispatch, and after
//               its 1st, 10th and 100th within the call, against Blender's snapshots of the same call, at max(1e-4 x
//               range, 1.25 x the floor runs' largest change there). Blender takes the in-call ones on its runs' main
//               level only; a run-wide key (pipes_thermal#1) belongs to whichever call made that dispatch, so a replay
//               of a later call (which starts the port's counts again) compares only Blender's snapshots of the same
//               call, and on a run made for this test (tests/detail/blender_detail_runs.py) every level's calls carry
//               their in-call snapshots
// The runs: the floor's draft base runs whose stages call these ops (alpine_valley and fluvial_range: breakup on the
// main level; meadow: hydraulic on the last), seeds 1 and 2, and the detail package's own Blender runs where they are
// made (blender_detail_runs.py: real_place Lauterbrunnen's hero levels, the gully and planation ops).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/detail/replay_test.mjs
//         [--runs alpine_valley_s1,meadow_s2,detail:lauterbrunnen_film,...] [--ops breakup,hydraulic] [--levels 4,5]
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/detail/replay_test.json and the port's logs under tests/out/detail/replay/. JavaScript per cell
// here is test code.

import * as G from '../../core/gpu.js';
import * as DT from '../../solvers/detail.js';
import * as HY from '../../solvers/hydraulic.js';
import * as RP from '../parity/replay.mjs';
import * as D from './_detail.mjs';

const { C, W } = D;
const A = D.argsOf();
const OPS = { breakup: DT.opBreakup, hydraulic: HY.opHydraulic, gully: DT.opGully, planation: DT.opPlanation };
const WANT_OPS = A.list('--ops') ?? Object.keys(OPS);
const LEVELS = A.list('--levels')?.map(Number) ?? null;
const FLOOR_RUNS = ['alpine_valley_s1', 'alpine_valley_s2', 'fluvial_range_s1', 'fluvial_range_s2', 'meadow_s1', 'meadow_s2'];
const RUNS = A.list('--runs') ?? [...FLOOR_RUNS, 'detail:lauterbrunnen_film', 'detail:gully_planation'];

/** A run's base folder: a floor run (<recipe>_s<seed>) or one of blender_detail_runs.py's (detail:<name>). */
function runDir(name) {
    if (name.startsWith('detail:')) {
        const d = `${W.out('detail')}/runs/${name.slice(7)}/base`;
        return W.exists(`${d}/stages/stages.json`) ? d : null;
    }
    const m = /^(.*)_s(\d+)$/.exec(name);
    return m ? W.floorRun(m[1], Number(m[2]), 'base') : null;
}

const T = new C.Checks('detail: stage replay on the Blender dumps');
const R = await G.init();
const results = [];
for (const name of RUNS) {
    const dir = runDir(name);
    if (!dir) {
        console.log(`[skip] ${name}: no run with stage dumps` + (name.startsWith('detail:') ? ' (tests/detail/blender_detail_runs.py makes it)' :
            ' (tests/parity/floor_runs.sh)'));
        continue;
    }
    const run = await RP.loadRun(dir);
    const own = name.startsWith('detail:');
    for (const st of run.stages) {
        if (!(st.op in OPS) || !WANT_OPS.includes(st.op)) continue;
        if (LEVELS && !LEVELS.includes(st.level)) continue;
        // snapshots: Blender's of this call only; on the detail runs every level's calls are snapshotted (the run's
        // header names the levels it snapshotted as main), so the port snapshots the call's level as its main level
        const snapIndex = Object.fromEntries(Object.entries(run.snapIndex).filter(([, e]) => e.call === st.call));
        const view = { ...run, snapIndex, header: { ...run.header, main_index: own ? st.level : run.header.main_index } };
        const logDir = `${W.out('detail')}/replay/${name.replace(':', '_')}/c${st.call}_${st.op}_L${st.level}`;
        const r = await RP.replayStage(R, G, view, st, OPS[st.op], { logDir });
        run._log ??= view._log;
        run._known ??= view._known;
        const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
        const d = r.dispatch ?? {};
        const line = `${name} L${st.level} ${st.op} (call ${st.call}, ${st.n} cells): ` + (r.error ? r.error :
            `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, ` +
                `grade ${C.sci(worst[1].tol / (worst[1].range || 1))}` : 'none'}${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}` +
            `${r.fields.extra.length ? `; extra ${r.fields.extra}` : ''}), dispatch log ${d.ok ? 'equal' : 'DIFFERS'} ` +
            `(${d.compared_dispatches} Blender dispatches compared, ${d.uniforms_over_4_steps} uniforms over 4 steps), ` +
            `${r.snapshots.keys} snapshots (${r.snapshots.compared} channels) ${r.snapshots.ok ? 'within tolerance' : 'OVER'} ` +
            `worst ${C.sci(r.snapshots.worst)}; ${r.seconds} s (Blender ${st.seconds} s)`);
        T.ok(line, r.ok, '');
        if (!r.ok && !r.error) {
            if (!r.fields.ok) console.log('     fields over:', JSON.stringify(Object.entries(r.fields.fields).filter(([, g]) => !g.ok).map(([k, g]) => [k, C.sci(g.over), C.sci(g.floor)])));
            if (!d.ok) console.log('     dispatch:', JSON.stringify({ structure: d.structure_differences, counts: d.counts_that_differ?.slice(0, 5), uniforms: d.uniform_failures?.slice(0, 5), images: d.image_differences }).slice(0, 1500));
            if (!r.snapshots.ok) console.log('     snapshots:', JSON.stringify(r.snapshots.failures.slice(0, 8)), JSON.stringify(r.snapshots.shapes));
        }
        results.push({ run: name, ...r, fields: r.fields ? { ok: r.fields.ok, missing: r.fields.missing, extra: r.fields.extra,
            worst: worst ? { field: worst[0], ...worst[1] } : null, all: r.fields.fields } : null });
    }
}
T.ok(`${results.length} replays ran`, results.length > 0, '');
T.extra.results = results;
const code = D.finish(T, 'replay_test');
G.shutdown();
Deno.exit(code);
