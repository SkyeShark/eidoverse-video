// Stage replay of the volcanic and impact ops on the Blender edition's own dumps (PORT_PLAN.md 8.2 row P9, 5.1, 5.3,
// 5.7): each call of the package's ops in a floor run of stratovolcano, caldera, cinder_cones and impact_crater,
// replayed by the port's op from that call's own input (the stage dump of its fields, pins and context), through
// tests/parity/replay.mjs replayStage:
//   fields      every field after the op against Blender's: max |d| <= max(1e-4 x range, 1.25 x the stage's floor,
//               16 float32 steps) (the floor: tests/parity/blender_stage_dump.py --floor, five patterns, main level)
//   dispatches  the call's Blender kernels (world_noise_field for the setting and the aging's seed texture, the
//               fluvial step's kernels and route_area for volcano_age) in order and number, every uniform within 4
//               float32 steps, the bound images (the port's own kernels set aside: tests/parity/dispatch_parity.mjs)
//   snapshots   each Blender kernel's images after its 1st, 10th and 100th dispatch in the call (main level), and the
//               run-wide ones (a kernel's 1st, 10th, ... of the whole run) where they name the same dispatch of the
//               call (callSnapshots, as tests/glacial/replay_test.mjs); the others are set aside, named in the result
// The dumped context's shared arrays (stamp_add's parent evaluations, ctx.shared._stamps) are given to the op as GPU
// fields, as the port's runner holds them.
//
// One field is graded another way where it is over: Sc after caldera_collapse and impact_crater (STEP_FIELDS). It is
// the strength the layered face was built at, 1.1 x the slope of the layer a cell's run u lies in: a step function of
// u, with steps of up to 2 in tangent at the layer boundaries. In float32 a cell's run is about 1e-3 m off numpy's at
// 5 km from the centre (r, and the planform's product of azimuth-table reads), while the face's table has 0.14 m
// between samples, so a cell within that distance of a boundary reads the other side of the step's interpolation
// (measured on caldera_s1: 86 of 262,144 cells, up to 0.02 in tangent). Blender against itself never shows it (the
// floor perturbs the fields, not the positions). So the op is run four times more from the same input with every
// position moved about the centre by -1e-6, -5e-7, +5e-7 and +1e-6 of its distance (MOVES: the run u moves by up to
// 5e-3 m at 5 km, five times its float32 error), and a cell over the plain grade passes when Blender's value lies
// within the port's own values at that cell over those runs (their min and max, plus the plain grade): the port's
// strength is Blender's at a run position within that distance. The cells that need it must be under 0.1 % of the
// field (step_regraded in the result).
// Beside the plan's grades, which take each field's single worst cell, the evolving ops (volcano_age's fluvial run,
// whose routed quantities and deposit are chaotic) are also reported by each field's RMS and p99 of |d| against the
// stage floor's samples of the same (as tests/fluvial/replay_test.mjs reports them): `ok_rms` in the result, the
// test's verdict still the plan's grade.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/volcanoes_craters/replay_test.mjs
//         [--runs stratovolcano_s1,...] [--ops stratovolcano,cinder_cones] [--levels 2] [--out name]
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/volcanoes_craters/<name>.json (replay_test by default) and the port's logs under
// tests/out/volcanoes_craters/replay/. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as VO from '../../solvers/volcanic.js';
import * as DP from '../parity/dispatch_parity.mjs';
import * as RP from '../parity/replay.mjs';
import * as V from './_vc.mjs';

const { C, W } = V;
const A = V.argsOf();
const IM = await import('../../solvers/impact.js').catch(() => null);
const OPS = { ...VO.OPS, ...(IM?.OPS ?? {}) };
const WANT_OPS = A.list('--ops') ?? Object.keys(OPS);
const LEVELS = A.list('--levels')?.map(Number) ?? null;
const RUNS = A.list('--runs') ?? V.RECIPES.flatMap((r) => [`${r}_s1`, `${r}_s2`]);
const NAME = A.opt('--out', 'replay_test');

const STEP_FIELDS = Object.freeze({ caldera_collapse: ['Sc'], impact_crater: ['Sc'] });
// the moved runs of a step field's op: every position scaled about the centre by 1 + e (its run u moved by e r)
const MOVES = [-1e-6, -5e-7, 5e-7, 1e-6];

/** The level scaled about `centre` by 1 + e (x0, y0 and the cell; the same cells, n and role). */
function movedLevel(level, centre, e) {
    const c = (centre ?? [0.0, 0.0]).map(Number);
    return Object.assign(Object.create(Object.getPrototypeOf(level)), level, { x0: c[0] + (level.x0 - c[0]) * (1 + e),
        y0: c[1] + (level.y0 - c[1]) * (1 + e), cell: level.cell * (1 + e), side: level.side * (1 + e) });
}

/** The step-field grade (see the top): a cell over the plain grade passes when Blender's value lies within the
 * port's own values at that cell over the moved runs (min - tol .. max + tol). { ok, cells (over the plain grade),
 * outside (of those, outside the moved runs' span), worst }. */
function regradeStep(got, moved, want, tol) {
    let cells = 0, outside = 0, worst = 0;
    for (let k = 0; k < want.length; k++) {
        const w = want[k], g = got[k];
        if (!(Number.isFinite(w) && Number.isFinite(g))) continue;
        const d = Math.abs(g - w);
        if (d <= tol) continue;
        cells++;
        worst = Math.max(worst, d);
        let lo = g, hi = g;
        for (const m of moved) {
            const v = m[k];
            if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
        }
        if (!(w >= lo - tol && w <= hi + tol)) outside++;
    }
    return { ok: outside === 0 && cells <= 1e-3 * want.length, cells, outside, worst };
}

/** max, RMS and p99 of |got - want| over a field, each / its range (tests/fluvial/replay_test.mjs rmsP99). */
function rmsP99(got, want) {
    let lo = Infinity, hi = -Infinity;
    for (const w of want) { if (Number.isFinite(w)) { if (w < lo) lo = w; if (w > hi) hi = w; } }
    const range = (hi - lo) || 1.0;
    const e = new Float64Array(want.length);
    let sq = 0, mx = 0;
    for (let i = 0; i < want.length; i++) {
        const d = Number.isFinite(want[i]) && Number.isFinite(got[i]) ? Math.abs(got[i] - want[i]) : (want[i] === got[i] || (want[i] !== want[i] && got[i] !== got[i]) ? 0 : Infinity);
        e[i] = d;
        sq += d * d;
        if (d > mx) mx = d;
    }
    e.sort();
    const pos = 0.99 * (e.length - 1), k = Math.floor(pos);
    const p99 = e[k] + (pos - k) * ((e[Math.min(k + 1, e.length - 1)]) - e[k]);
    return { max: mx / range, rms: Math.sqrt(sq / e.length) / range, p99: p99 / range, range };
}

/** The fields' RMS and p99 against the stage floor's samples ([max, RMS, p99] each): each within max(1e-4, 1.25 x
 * the largest sample) (tests/fluvial/replay_test.mjs gradeRms). */
function gradeRms(run, st, dist) {
    const floor = run.floors?.[st.call]?.floor ?? {};
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

/** Blender's snapshots of one call that the port's replay of it can match (as tests/glacial/replay_test.mjs takes
 * them): the call's own keys, and a run-wide key (a kernel's 1st, 10th, ... dispatch of the whole run) only where
 * that dispatch is the same-numbered dispatch of the kernel within the call. { snapIndex, aside }. */
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

const T = new C.Checks('volcanoes_craters: stage replay on the Blender dumps');
const R = await G.init();
const results = [];
for (const name of RUNS) {
    const m = /^(.*)_s(\d+)$/.exec(name);
    const found = m ? V.floorRunOfCode(m[1], Number(m[2])) : null;
    if (!found) {
        console.log(`[skip] ${name}: no floor run with stage dumps (tests/parity/floor_runs.sh)`);
        continue;
    }
    const [dir, key] = found;
    const run = await RP.loadRun(dir);
    for (const st of run.stages) {
        if (!(st.op in OPS) || !WANT_OPS.includes(st.op)) continue;
        if (LEVELS && !LEVELS.includes(st.level)) continue;
        VO.clearMemos();
        const logDir = `${W.out('volcanoes_craters')}/replay/${name}/c${st.call}_${st.op}_L${st.level}`;
        const made = [], kept = {}, moved = {}, dist = {};
        const invoke = async (op, { fields, level, params, seed, ctx }) => {
            made.push(...V.sharedToGpu(R, ctx));
            if (ctx) ctx.device = R;
            const steps = STEP_FIELDS[st.op] ?? [];
            const before = steps.length ? fields.copy() : null;
            await op(fields, level, params, seed, ctx);
            for (const k of steps) if (k in fields) kept[k] = await R.read(fields[k]);
            if (op.evolves) {                       // the RMS and p99 report of an evolving op (see the top)
                const want = await RP.npz(`${run.dir}/stages/${st.after}`);
                for (const [name, w] of Object.entries(want)) {
                    if (name.startsWith('shared__') || w.shape.length !== 2 || w.dtype !== '<f4' || !(name in fields)) continue;
                    dist[name] = rmsP99(await R.read(fields[name]), w.data);
                }
            }
            if (before) {
                // the same op from the same input with every position moved (the moved runs of the step grade; their
                // dispatches are the port's own kernels, which the dispatch log sets aside)
                for (const e of MOVES) {
                    const f2 = before.copy();
                    const c2 = ctx ? Object.assign(Object.create(Object.getPrototypeOf(ctx)), ctx,
                        { shared: { ...(ctx.shared ?? {}), _stamps: {} } }) : null;
                    await op(f2, movedLevel(level, params?.centre, e), params, seed, c2);
                    for (const k of steps) if (k in f2) (moved[k] ??= []).push(await R.read(f2[k]));
                    f2.dispose();
                }
                before.dispose();
            }
        };
        const { snapIndex, aside } = await callSnapshots(run, st.call);
        const view = { ...run, snapIndex };
        const r = await RP.replayStage(R, G, view, st, OPS[st.op], { logDir, invoke });
        run._log ??= view._log;
        run._known ??= view._known;
        r.snapshots_set_aside = aside;
        for (const f of made) if (!f.destroyed) f.destroy();
        if (!r.error && !r.fields.ok) {                     // a step field graded by Blender's own neighbourhood
            const want = await RP.npz(`${run.dir}/stages/${st.after}`);
            r.step_regraded = {};
            for (const [k, got] of Object.entries(kept)) {
                const g = r.fields.fields[k];
                if (!g || g.ok || !want[k]) continue;
                const rg = regradeStep(got, moved[k] ?? [], want[k].data, g.tol);
                r.step_regraded[k] = rg;
                if (rg.ok) g.ok = true;
            }
            r.fields.ok = Object.values(r.fields.fields).every((g) => g.ok) && !r.fields.missing.length;
            r.ok = r.fields.ok && r.dispatch.ok && r.snapshots.ok;
        }
        if (!r.error && Object.keys(dist).length) {
            r.fields_rms = gradeRms(run, st, dist);
            r.ok_rms = r.fields_rms.ok && r.dispatch.ok && r.snapshots.ok;
        }
        const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
        const d = r.dispatch ?? {};
        const lvd = run.header.plan?.[st.level];
        const line = `${name} L${st.level}${lvd ? ` (${lvd.role} ${lvd.cell} m x${lvd.n})` : ''} p${st.pass_index} ${st.label} ` +
            `(call ${st.call}): ` + (r.error ? r.error :
            `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range, ` +
                `grade ${C.sci(worst[1].tol / (worst[1].range || 1))}` : 'none'}${r.fields.missing.length ? `; missing ${r.fields.missing}` : ''}` +
            `${r.fields.extra.length ? `; extra ${r.fields.extra}` : ''}), dispatch log ${d.ok ? 'equal' : 'DIFFERS'} ` +
            `(${d.compared_dispatches} Blender dispatches compared, ${d.uniforms_over_4_steps} uniforms over 4 steps), ` +
            `${r.snapshots.keys} snapshots (${r.snapshots.compared} channels) ${r.snapshots.ok ? 'within tolerance' : 'OVER'}; ` +
            (r.step_regraded && Object.keys(r.step_regraded).length ? `step fields by the moved runs: ${Object.entries(r.step_regraded)
                .map(([k, g]) => `${k} ${g.cells} cells (${g.outside} outside, worst ${C.sci(g.worst)})`).join(', ')}; ` : '') +
            (r.fields_rms ? `by RMS and p99 ${r.fields_rms.ok ? 'within' : 'OVER'} the floor; ` : '') +
            `${r.seconds} s (Blender ${st.seconds} s)`);
        T.ok(line, r.ok, '');
        if (!r.ok && !r.error) {
            if (!r.fields.ok) console.log('     fields over:', JSON.stringify(Object.entries(r.fields.fields).filter(([, g]) => !g.ok).map(([k, g]) => [k, C.sci(g.over), C.sci(g.tol / (g.range || 1)), C.sci(g.floor)])));
            if (r.fields_rms) console.log('     by RMS / p99:', JSON.stringify(Object.entries(r.fields_rms.fields).filter(([k, g]) => !g.ok || !r.fields.fields[k]?.ok)
                .map(([k, g]) => [k, `rms ${C.sci(g.rms)} (floor ${C.sci(g.floor_rms)})`, `p99 ${C.sci(g.p99)} (floor ${C.sci(g.floor_p99)})`])));
            if (!d.ok) console.log('     dispatch:', JSON.stringify({ structure: d.structure_differences, counts: d.counts_that_differ?.slice(0, 5), uniforms: d.uniform_failures?.slice(0, 5), images: d.image_differences }).slice(0, 1500));
            if (!r.snapshots.ok) console.log('     snapshots:', JSON.stringify(r.snapshots.failures.slice(0, 8)), JSON.stringify(r.snapshots.shapes));
        }
        results.push({ run: name, key, ...r, fields: r.fields ? { ok: r.fields.ok, missing: r.fields.missing,
            extra: r.fields.extra, worst: worst ? { field: worst[0], ...worst[1] } : null, all: r.fields.fields } : null });
    }
}
T.ok(`${results.length} replays ran`, results.length > 0, '');
T.extra.results = results;
const code = V.finish(T, NAME);
G.shutdown();
Deno.exit(code);
