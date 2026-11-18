// The port's fluvial step, timed as the Blender edition's test_kernels.py test_cost times it (the port's side of
// tests/fluvial/bench_interleaved.sh; PORT_PLAN.md 8.2 row P6: the step within 1.25 x Blender's measured cost).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/bench_step.mjs
//          --out <json> [--sizes 1024,2048] [--steps 200]
//
// The same step, inputs and sequence as bench_blender.py: solvers/fluvial.js FluvialRun.step (flow_weights,
// route_incise, h_keep, creep x1, creep_layers, (threshold_excess, threshold) x2) on twins.random_field(n, 0, 2000, 1,
// smooth 2) at 10 m cells, U 2e-3, K 1.5e-5, Sc 0.7, G 0.5, the outer ring pinned; without and with the lock (64-cell
// blocks); 5 steps and a read of the whole state (Blender's height() reads its whole texture), then `steps` steps and
// a read, timed. Also the GPU's own time of the steps (timestamp queries), for the record.

import * as G from '../../core/gpu.js';
import * as FL from '../../solvers/fluvial.js';
import { randomField, rgba } from './_common.mjs';

const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const out = opt('--out', null);
const SIZES = opt('--sizes', '1024,2048').split(',').map(Number);
const STEPS = Number(opt('--steps', '200'));

const R = await G.init();
const rec = { edition: 'threejs', deno: Deno.version.deno, adapter: R.info?.description ?? null, steps: STEPS, sizes: {} };
const iters = FL.DEFAULTS.threshold_iters, rate = FL.THRESHOLD_RATE.iso;
for (const n of SIZES) {
    const N = n * n;
    const h = randomField(n, n, 0, 2000, 1, 2);
    const fields = { h: R.field(n, n, 1, h) };
    const pins = FL.edgePins(R, n, fields.h);
    const res = {};
    for (const [label, lock] of [['step_ms', null], ['step_with_lock_ms', fields.h]]) {
        const par = R.field(n, n, 4, rgba(N, 2e-3, 1.5e-5, 0.7, 0.5));
        const run = new FL.FluvialRun(R, 10.0, fields, par, pins, FL.PINNED, null, lock, lock ? 64 : 2);
        for (let i = 0; i < 5; i++) run.step(130.0, 0.05, 1, iters, rate, 5.0);
        await R.read(run.height());
        const t0 = performance.now();
        for (let i = 0; i < STEPS; i++) run.step(130.0, 0.05, 1, iters, rate, 5.0);
        await R.read(run.height());
        res[label] = +((performance.now() - t0) / STEPS).toFixed(4);
        const gpu = await R.timed(() => { for (let i = 0; i < 20; i++) run.step(130.0, 0.05, 1, iters, rate, 5.0); });
        if (gpu !== null) res[label.replace('_ms', '_gpu_ms')] = +(gpu / 20).toFixed(4);
        run.destroy();
    }
    for (const f of [fields.h, ...Object.values(pins)]) f.destroy();
    rec.sizes[String(n)] = res;
    console.log(`[bench] port ${n}^2: ${JSON.stringify(res)}`);
}
if (out) Deno.writeTextFileSync(out, JSON.stringify(rec, null, 1));
G.shutdown();
