// Costs of the core inputs on this machine's GPU (PORT_PLAN.md 8.2, P2): world noise, an uplift shape and the start
// surface (the design's budget: all inputs of a level within 1 s; numpy needs about 1.2 s per lattice at 1024),
// the x2 inheritance, the PNG16 export and its quantisation table, a level's npz. Wall times include one readback
// (about 16 ms a wait here, plan 4.5). Writes out/core_inputs/bench_inputs.json.
//
//     $EIDO_GPU_WRAP deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/core_inputs/bench_inputs.mjs

import * as G from '../../core/gpu.js';
import * as Gd from '../../core/grid.js';
import * as N from '../../core/world_noise.js';
import * as C from '../../core/compose.js';
import * as IO from '../../core/io.js';
import { outUrl, scratch } from './_common.mjs';

const R = await G.init();
const out = { adapter: R.info?.description ?? null, deno: Deno.version.deno, date: new Date().toISOString(), rows: [] };
const TMP = scratch('eido_bench_inputs_');

async function time(label, fn, reps = 3) {
    const ms = [];
    for (let r = 0; r < reps; r++) {
        const t0 = performance.now();
        const f = await fn();
        if (f && f.runner) {
            await R.readRange(f, 0, 1);                    // the work done
            f.destroy();
        } else {
            await R.idle();
        }
        ms.push(performance.now() - t0);
    }
    ms.sort((a, b) => a - b);
    const row = { label, ms_median: +ms[Math.floor(ms.length / 2)].toFixed(2), ms_min: +ms[0].toFixed(2) };
    out.rows.push(row);
    console.log(`${label.padEnd(64)} ${row.ms_median.toFixed(1).padStart(8)} ms (min ${row.ms_min.toFixed(1)})`);
}

for (const n of [1024, 2048]) {
    const lv = { x0: -4000, y0: -4000, cell: 8000 / n, n };
    await time(`fieldGpu fbm 5 octaves at ${n}`, () => N.fieldGpu(R, { kind: 'fbm', wavelength_m: 2000, octaves: 5 }, lv, 3));
    await time(`fieldGpu warp of a sum (4 dispatches + combines) at ${n}`, () => N.fieldGpu(R, { kind: 'warp', amp_m: 200,
        wavelength_m: 1500, of: { kind: 'sum', terms: [{ kind: 'fbm', wavelength_m: 900 }, { kind: 'ridged', wavelength_m: 300 }] } }, lv, 3));
    await time(`uplift ridge with 6 spurs (warp, texture) at ${n}`, () => C.uplift(R, { kind: 'ridge', azimuth_deg: 30, length_m: 12000,
        width_m: 5000, spurs: 6 }, lv, 3));
    await time(`startSurface ridge (its peak read back) at ${n}`, () => C.startSurface(R, { kind: 'ridge', length_m: 12000, width_m: 5000 }, lv, 3));
    const h = N.fieldGpu(R, { kind: 'fbm', wavelength_m: 2000, octaves: 5, amp: 1000 }, lv, 3);
    await time(`upsample2 catmull ${n} -> ${2 * n}`, () => Gd.upsample2(h, 'catmull'));
    await time(`exportHeightmap png16 + r32 at ${n} (GPU quantise and filter, CompressionStream)`, async () => {
        await IO.exportHeightmap(h, TMP, 8000 / n, { name: `bench_${n}`, formats: ['png16', 'r32'] });
        return null;
    }, 2);
    await time(`a level's npz (12 float32 fields) written at ${n}`, async () => {
        const a = await IO.arrayFromField(h);
        await IO.writeNpz(`${TMP}/bench_${n}.npz`, Array.from({ length: 12 }, (_, i) => [`L0__f__f${i}`, a]));
        return null;
    }, 2);
    await time(`the same npz read back (CRC-32 checked) at ${n}`, async () => {
        await IO.readNpz(`${TMP}/bench_${n}.npz`);
        return null;
    }, 2);
    h.destroy();
}
{
    const t0 = performance.now();
    IO.quantiseSteps(-312.25, 4321.5, 65535);
    const ms = performance.now() - t0;
    out.rows.push({ label: 'quantiseSteps, the 65535 steps of a png16 export (JavaScript, numpy\'s float64)', ms_median: +ms.toFixed(2) });
    console.log(`quantiseSteps (65535 steps, JavaScript)${' '.repeat(25)} ${ms.toFixed(1).padStart(8)} ms`);
}
try {
    if (!Deno.env.get('EIDO_TEST_SCRATCH')) Deno.removeSync(TMP, { recursive: true });
} catch (_e) { /* fine */ }
Deno.writeTextFileSync(outUrl('bench_inputs.json'), JSON.stringify(out, null, 1));
G.shutdown();
