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
//               level only; on a run made for this test (tests/detail/blender_detail_runs.py) every level's calls
//               carry them. A run-wide key (pipes_thermal#1000: the run's 1,000th dispatch of the kernel) belongs to
//               the call that made that dispatch, and the port's counts start at the replayed call (setting the
//               dispatch hook starts them again: core/gpu.js onDispatch), so a run-wide key is compared only where it
//               is also the call's own n-th dispatch of its kernel; one whose kernel ran in an earlier call too (a
//               hydraulic call's pipes_thermal#1000 after breakup's 400 relaxation passes is the call's 600th) is set
//               aside and named (snapshots_set_aside).
//               One channel is graded another way: pipes_thermal's carry (outT.y, and tacc.y, the carry it reads
//               from the pass before) is the rounding residue of the delta's update dl = c.x + dbc (Kahan's
//               compensation, in the GLSL's Fast2Sum form carry = dbc - (dl - c.x): the exact rounding error, at most
//               ulp(dl) / 2, where |c.x| >= |dbc|, and up to one ulp of dl where the pass's update is the larger term,
//               as in the first passes, whose delta starts at 0), so any last-bit difference in the inputs gives
//               another residue, and it differs by about its own range in Blender against itself (the floor samples:
//               0.56 to 1.15 of range), against which the snapshot grade above is a coin toss. Where that channel is
//               over, it is graded in ulps of the delta it compensates instead: per cell |carry_port -
//               carry_blender| <= 2 ulp(the largest |delta| of the two runs there: in__st.x, and outS.x after the
//               pass), the most two such residues of the same sum can differ (measured: Blender +1 ulp and the port
//               -1 ulp on a few cells where |dbc| > |c.x|) (carry_regraded). That bound says only that the residue is
//               residue-sized; that it is computed as written (not folded to 0) is the kernel test's, bit for bit on
//               equal inputs (tests/detail/kernels_test.mjs), and that it keeps the mass is the conservation test's
// The runs: the floor's draft base runs whose stages call these ops (alpine_valley and fluvial_range: breakup on the
// main level; meadow: hydraulic on the last), seeds 1 and 2, and the detail package's own Blender runs where they are
// made (blender_detail_runs.py: real_place Lauterbrunnen's hero levels, the gully and planation ops). A floor run that
// is missing under the parity key ($EIDO_PARITY_KEY, else the newest) is taken from another key of the same Blender
// terrain code (equal field and terrain hashes in the keys' manifests), as tests/fluvial/judge_test.mjs takes it, and
// the key it came from is recorded.
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
import * as DP from '../parity/dispatch_parity.mjs';
import * as RP from '../parity/replay.mjs';
import * as D from './_detail.mjs';

const { C, W } = D;
const A = D.argsOf();
const OPS = { breakup: DT.opBreakup, hydraulic: HY.opHydraulic, gully: DT.opGully, planation: DT.opPlanation };
const WANT_OPS = A.list('--ops') ?? Object.keys(OPS);
const LEVELS = A.list('--levels')?.map(Number) ?? null;
const FLOOR_RUNS = ['alpine_valley_s1', 'alpine_valley_s2', 'fluvial_range_s1', 'fluvial_range_s2', 'meadow_s1', 'meadow_s2'];
const RUNS = A.list('--runs') ?? [...FLOOR_RUNS, 'detail:lauterbrunnen_film', 'detail:gully_planation'];

/** A run's base folder and the parity key it came from: a floor run (<recipe>_s<seed>) or one of
 * blender_detail_runs.py's (detail:<name>, key null). [dir, key] or null. */
function runDir(name) {
    if (name.startsWith('detail:')) {
        const d = `${W.out('detail')}/runs/${name.slice(7)}/base`;
        return W.exists(`${d}/stages/stages.json`) ? [d, null] : null;
    }
    const m = /^(.*)_s(\d+)$/.exec(name);
    return m ? floorRunOfCode(m[1], Number(m[2])) : null;
}

/** The floor run of (recipe, seed) under the parity key, else under another key of the same Blender terrain code (its
 * manifest's field_hash and terrain_hash equal the key's: a later commit that changed no terrain file). */
function floorRunOfCode(recipe, seed) {
    const key = W.parityKeyDir();
    if (!key) return null;
    const own = W.floorRun(recipe, seed, 'base');
    if (own) return [own, key.split('/').pop()];
    const code = (dir) => { const k = C.readJson(`${dir}/manifest.json`)?.key; return k ? `${k.field_hash}|${k.terrain_hash}` : null; };
    const mine = code(key);
    if (!mine) return null;
    for (const k of W.parityKeys()) {
        const dir = `${k.dir}/${recipe}_s${seed}_draft/base`;
        if (k.dir !== key && code(k.dir) === mine && W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

/** Blender's snapshots of one call that the port's replay of it can match (see the top): { snapIndex, aside }. */
async function callSnapshots(run, call) {
    run._log ??= await DP.loadRun(run.dir);
    let nth = null;                                     // kernel -> the dispatch indices of this call, in order
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

// pipes_thermal's carry channel and the deltas it is the residue of (see the top)
const CARRY = { outT: ['in__st', 'outS'], in__tacc: ['in__st'] };

/** Grade the carry channel's snapshot failures in ulps of the delta (see the top): { rest (the failures that stay),
 * regraded ([{ key, image, cells_over_two_ulps, worst_ulps }]) }. A list cut at compareSnapshots' 40 keeps them all. */
async function regradeCarry(run, logDir, snaps) {
    if (snaps.failures.length >= 40 || snaps.shapes.length) return { rest: snaps.failures, regraded: [] };
    const mine = C.readJson(`${logDir}/snap/index.json`, { snapshots: {} }).snapshots;
    const rest = [], regraded = [];
    for (const f of snaps.failures) {
        const kernel = run.snapIndex[f.key]?.kernel;
        if (!(kernel === 'pipes_thermal' && f.channel === 1 && f.image in CARRY && mine[f.key])) { rest.push(f); continue; }
        const a = await RP.npz(`${run.dir}/snap/${run.snapIndex[f.key].file}`), b = await RP.npz(`${logDir}/snap/${mine[f.key].file}`);
        const ca = a[f.image], cb = b[f.image], dels = CARRY[f.image].filter((nm) => a[nm] && b[nm]);
        const ch = ca.shape[2] ?? 1, cells = ca.data.length / ch;
        let over = 0, worst = 0;
        for (let i = 0; i < cells; i++) {
            let m = 0;
            for (const nm of dels) {
                const k = a[nm].shape[2] ?? 1;
                m = Math.max(m, Math.abs(a[nm].data[i * k]), Math.abs(b[nm].data[i * k]));
            }
            const u = C.ulp32(m), d = Math.abs(ca.data[i * ch + 1] - cb.data[i * ch + 1]);
            if (!(d <= 2 * u)) over++;
            if (u > 0) worst = Math.max(worst, d / u);
        }
        regraded.push({ key: f.key, image: f.image, over_range: f.over, cells_over_two_ulps: over, worst_ulps: +worst.toFixed(3),
            cells, deltas: dels });
        if (over || !dels.length) rest.push(f);
    }
    return { rest, regraded };
}

const T = new C.Checks('detail: stage replay on the Blender dumps');
const R = await G.init();
const results = [];
for (const name of RUNS) {
    const found = runDir(name);
    if (!found) {
        console.log(`[skip] ${name}: no run with stage dumps` + (name.startsWith('detail:') ? ' (tests/detail/blender_detail_runs.py makes it)' :
            ' (tests/parity/floor_runs.sh)'));
        continue;
    }
    const [dir, key] = found;
    const run = await RP.loadRun(dir);
    const own = name.startsWith('detail:');
    for (const st of run.stages) {
        if (!(st.op in OPS) || !WANT_OPS.includes(st.op)) continue;
        if (LEVELS && !LEVELS.includes(st.level)) continue;
        // snapshots: Blender's of this call that the replay can match; on the detail runs every level's calls are
        // snapshotted (the run's header names the levels it snapshotted as main), so the port snapshots the call's
        // level as its main level
        const { snapIndex, aside } = await callSnapshots(run, st.call);
        const view = { ...run, snapIndex, header: { ...run.header, main_index: own ? st.level : run.header.main_index } };
        const logDir = `${W.out('detail')}/replay/${name.replace(':', '_')}/c${st.call}_${st.op}_L${st.level}`;
        const r = await RP.replayStage(R, G, view, st, OPS[st.op], { logDir });
        run._log ??= view._log;
        run._known ??= view._known;
        if (!r.error && !r.snapshots.ok) {                  // the carry channel, graded in ulps of its delta
            const { rest, regraded } = await regradeCarry(view, logDir, r.snapshots);
            r.snapshots.carry_regraded = regraded;
            if (regraded.length && !rest.length) r.snapshots.ok = true;
            r.snapshots.failures = rest;
            r.ok = r.fields.ok && r.dispatch.ok && r.snapshots.ok;
        }
        const carry = r.snapshots?.carry_regraded?.length ? `, carry graded in ulps of its delta on ${r.snapshots.carry_regraded.length} ` +
            `(worst ${Math.max(...r.snapshots.carry_regraded.map((x) => x.worst_ulps))} ulp)` : '';
        const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
        const d = r.dispatch ?? {};
        const lvd = run.header.plan?.[st.level];
        const line = `${name} L${st.level}${lvd ? ` (${lvd.role} ${lvd.cell} m x${lvd.n})` : ''} ${st.op} (call ${st.call}, ` +
            `stage ${st.n} of its level): ` + (r.error ? r.error :
            `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, ` +
                `grade ${C.sci(worst[1].tol / (worst[1].range || 1))}` : 'none'}${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}` +
            `${r.fields.extra.length ? `; extra ${r.fields.extra}` : ''}), dispatch log ${d.ok ? 'equal' : 'DIFFERS'} ` +
            `(${d.compared_dispatches} Blender dispatches compared, ${d.uniforms_over_4_steps} uniforms over 4 steps), ` +
            `${r.snapshots.keys} snapshots (${r.snapshots.compared} channels) ${r.snapshots.ok ? 'within tolerance' : 'OVER'} ` +
            `worst ${C.sci(r.snapshots.worst)}${carry}${aside.length ? `, ${aside.length} run-wide set aside` : ''}; ${r.seconds} s ` +
            `(Blender ${st.seconds} s)${key && key !== W.parityKeyDir()?.split('/').pop() ? ` [floor run of key ${key}]` : ''}`);
        T.ok(line, r.ok, '');
        if (!r.ok && !r.error) {
            if (!r.fields.ok) console.log('     fields over:', JSON.stringify(Object.entries(r.fields.fields).filter(([, g]) => !g.ok).map(([k, g]) => [k, C.sci(g.over), C.sci(g.floor)])));
            if (!d.ok) console.log('     dispatch:', JSON.stringify({ structure: d.structure_differences, counts: d.counts_that_differ?.slice(0, 5), uniforms: d.uniform_failures?.slice(0, 5), images: d.image_differences }).slice(0, 1500));
            if (!r.snapshots.ok) console.log('     snapshots:', JSON.stringify(r.snapshots.failures.slice(0, 8)), JSON.stringify(r.snapshots.shapes));
        }
        results.push({ run: name, key, ...r, snapshots_set_aside: aside, fields: r.fields ? { ok: r.fields.ok, missing: r.fields.missing,
            extra: r.fields.extra, worst: worst ? { field: worst[0], ...worst[1] } : null, all: r.fields.fields } : null });
    }
}
T.ok(`${results.length} replays ran`, results.length > 0, '');
T.extra.results = results;
const code = D.finish(T, 'replay_test');
G.shutdown();
Deno.exit(code);
