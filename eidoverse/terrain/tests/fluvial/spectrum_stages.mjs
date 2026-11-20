// Where the main level's spectrum slope is made (a diagnostic of the distribution-class verdict, PORT_PLAN.md 5.3):
// for each op call on the main level of a Blender floor run (fluvial_range: fluvial, valley_floor, breakup,
// hydraulic), the judge's spectrum slope and slope numbers (core/metrics.js, the judge's numbers on the main level at
// its own cell, as judge/run.py --field takes a generated terrain) of Blender's dumped input, Blender's dumped output
// and the port's output of the same op replayed from Blender's input. Each op's change of the spectrum slope in the
// port beside its change in Blender tells which op, if any, moves the spectrum differently; the main level's input
// (inherited from the levels above) carries the chaotic part.
// Also the same numbers on every level's end state of the port's and Blender's saves (bake.mjs --save; the floor
// runs' terrain.npz or base saves), seed by seed, to see on which level the two editions' slopes part.
// JavaScript per cell here is test code.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/spectrum_stages.mjs
//         [--recipe fluvial_range] [--seeds 1,2] [--saves <dir>] [--levels main | all]
//                                                                   (on a shared machine, behind $EIDO_GPU_WRAP)
// --levels all replays every level's op calls (the context levels' numbers at their own cells).
//
// Writes tests/out/fluvial/spectrum_stages_<recipe>.json.

import * as G from '../../core/gpu.js';
import * as IO from '../../core/io.js';
import * as M from '../../core/metrics.js';
import * as RP from '../parity/replay.mjs';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const RECIPE = opt('--recipe', 'fluvial_range');
const SEEDS = opt('--seeds', '1,2').split(',').map(Number);
const SAVES = opt('--saves', `${W.out('fluvial')}/saves`);
const ALL_LEVELS = opt('--levels', 'main') === 'all';
const KEYS = ['spectrum_slope', 'spectrum_slope_short', 'spectrum_slope_long', 'spectrum_knee_m', 'slope_p50', 'slope_p99',
    'frac_slope_lt5', 'hypsometric_integral', 'relief_m'];

const R = await G.init();
const registry = await import('../../recipes/index.js');

async function numbers(data, n, cell) {
    const f = R.field(n, n, 1, data);
    const m = await M.metrics(f, cell, { withDepressions: false });
    f.destroy();
    return Object.fromEntries(KEYS.map((k) => [k, m[k]]));
}

// the save's h of every level: { index: { n, cell, role, h } }
async function saveLevels(npzPath) {
    const info = C.readJson(npzPath.replace(/\.npz$/, '.json'));
    const arrays = await IO.readNpz(npzPath);
    const out = {};
    for (const lv of info?.plan ?? []) {
        const a = arrays[`L${lv.index}__f__h`] ?? arrays[`L${lv.index}__f__h.npy`];
        if (a) out[lv.index] = { n: lv.n, cell: lv.cell, role: lv.role, h: a.data };
    }
    return out;
}

const result = { recipe: RECIPE, key: W.parityKeyDir()?.split('/').pop(), seeds: {} };
for (const seed of SEEDS) {
    const dir = W.floorRun(RECIPE, seed);
    if (!dir) { console.log(`[skip] ${RECIPE} s${seed}: no floor run`); continue; }
    const run = await RP.loadRun(dir);                  // null for a run without stage dumps (seeds 3-4: saves only)
    const main = run?.header.main_index ?? null;
    const rows = [];
    for (const st of (run?.stages ?? []).filter((s) => ALL_LEVELS || s.level === main)) {
        if (!(await registry.hasOp(st.op))) continue;
        const before = await RP.stageBefore(R, run, st);
        const ctx = RP.stageContext(run, st, before);
        const n = before.level.n, cell = before.level.cell;
        const bIn = await numbers(before.arrays.h.data, n, cell);
        const want = await RP.npz(`${run.dir}/stages/${st.after}`);
        const bOut = await numbers(want.h.data, n, cell);
        await (await registry.getOp(st.op))(before.fields, before.level, structuredClone(st.params), st.seed, ctx);
        const pOut = await numbers(await R.read(before.fields.h), n, cell);
        for (const f of Object.values(before.pins)) f.destroy?.();
        for (const name of Object.keys(before.fields)) before.fields[name]?.destroy?.();
        rows.push({ call: st.call, level: st.level, pass: st.pass_index, op: st.op, blender_in: bIn, blender_out: bOut, port_out: pOut });
        console.log(`${RECIPE} s${seed} L${st.level} p${st.pass_index} ${st.op.padEnd(12)} spectrum slope: Blender in ${bIn.spectrum_slope.toFixed(4)} -> out ` +
            `${bOut.spectrum_slope.toFixed(4)} (${(bOut.spectrum_slope - bIn.spectrum_slope).toFixed(4)}); port out ` +
            `${pOut.spectrum_slope.toFixed(4)} (${(pOut.spectrum_slope - bIn.spectrum_slope).toFixed(4)})`);
    }
    // every level's end state: the port's save of this seed, and Blender's run (its save when the floor run kept one,
    // else the level's last end-stage dump, which is what the save holds)
    const levels = {};
    const bSave = `${dir}/terrain.npz`;
    const pSave = `${SAVES}/${RECIPE}_s${seed}.npz`;
    const pl = W.exists(pSave) ? await saveLevels(pSave) : null;
    let bl = W.exists(bSave) ? await saveLevels(bSave) : null;
    if (!bl && run) {
        bl = {};
        for (const [i, lv] of run.levels.entries()) {
            const p = `${run.dir}/stages/L${i}_end_route_after.npz`;
            if (W.exists(p)) bl[i] = { n: lv.n, cell: lv.cell, role: lv.role, h: (await RP.npz(p)).h.data };
        }
    }
    for (const idx of Object.keys(pl ?? {})) {
        const p = pl[idx], b = bl?.[idx];
        levels[idx] = { role: p.role, cell: p.cell, port: await numbers(p.h, p.n, p.cell), blender: b ? await numbers(b.h, b.n, b.cell) : null };
        console.log(`${RECIPE} s${seed} save L${idx} (${p.role}, ${p.cell} m): spectrum slope port ${levels[idx].port.spectrum_slope.toFixed(4)}` +
            (levels[idx].blender ? `, Blender ${levels[idx].blender.spectrum_slope.toFixed(4)}` : ', no Blender save here'));
    }
    result.seeds[seed] = { main, stages: rows, levels };
}
Deno.writeTextFileSync(`${W.out('fluvial')}/spectrum_stages_${RECIPE}${ALL_LEVELS ? '_all' : ''}.json`, JSON.stringify(result, null, 1));
G.shutdown();
