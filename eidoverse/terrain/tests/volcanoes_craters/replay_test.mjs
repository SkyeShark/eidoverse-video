// Stage replay of the volcanic and impact ops on the Blender edition's own dumps (PORT_PLAN.md 8.2 row P9, 5.1, 5.3,
// 5.7): each call of the package's ops in a floor run of stratovolcano, caldera, cinder_cones and impact_crater,
// replayed by the port's op from that call's own input (the stage dump of its fields, pins and context), through
// tests/parity/replay.mjs replayStage:
//   fields      every field after the op against Blender's: max |d| <= max(1e-4 x range, 1.25 x the stage's floor,
//               16 float32 steps) (the floor: tests/parity/blender_stage_dump.py --floor, five patterns, main level)
//   dispatches  the call's Blender kernels (world_noise_field for the setting and the aging's seed texture, the
//               fluvial step's kernels and route_area for volcano_age) in order and number, every uniform within 4
//               float32 steps, the bound images (the port's own kernels set aside: tests/parity/dispatch_parity.mjs)
//   snapshots   each Blender kernel's images after its 1st, 10th and 100th dispatch in the call (main level)
// The dumped context's shared arrays (stamp_add's parent evaluations, ctx.shared._stamps) are given to the op as GPU
// fields, as the port's runner holds them.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/volcanoes_craters/replay_test.mjs
//         [--runs stratovolcano_s1,...] [--ops stratovolcano,cinder_cones] [--levels 2] [--out name]
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/volcanoes_craters/<name>.json (replay_test by default) and the port's logs under
// tests/out/volcanoes_craters/replay/. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as VO from '../../solvers/volcanic.js';
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
        const made = [];
        const invoke = async (op, { fields, level, params, seed, ctx }) => {
            made.push(...V.sharedToGpu(R, ctx));
            if (ctx) ctx.device = R;
            await op(fields, level, params, seed, ctx);
        };
        const r = await RP.replayStage(R, G, run, st, OPS[st.op], { logDir, invoke });
        for (const f of made) if (!f.destroyed) f.destroy();
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
            `${r.seconds} s (Blender ${st.seconds} s)`);
        T.ok(line, r.ok, '');
        if (!r.ok && !r.error) {
            if (!r.fields.ok) console.log('     fields over:', JSON.stringify(Object.entries(r.fields.fields).filter(([, g]) => !g.ok).map(([k, g]) => [k, C.sci(g.over), C.sci(g.tol / (g.range || 1)), C.sci(g.floor)])));
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
