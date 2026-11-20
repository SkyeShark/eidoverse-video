// The U-shape fit (PORT_PLAN.md 8.2 row P13; blender/tests/terrain/glacial/test_gpu.py test_u_fit, ported): a river
// valley 8 km long draining north (the trunk at x = 0 on a 1.2 % grade, 600 m over the fill's grade line as the
// recipe's trunk river stands bench_m over it, falling to its outlet over the last 2 km; 30-degree V sides up to
// ridges 2.4 km high; three V tributaries a side, graded to the trunk), at 512^2 and 15.6 m cells, carved by the port's
// carveLevel with alpine_valley's glacial stage (ela 600 m, the trough 600 m deep, no cirques, channels from 1 km2), as
// the Blender test carves it. Judged by the Blender judge's own family numbers (judge/family.alpine_valley, run by
// Blender's Python: tests/glacial/u_fit_judge.py) and the test's four sections across the trunk, with the Blender
// test's own thresholds:
//   the V is no U before the carve (the judge's U exponent b under 1.5)
//   the carved trunk is a box trough: a level floor 200-1000 m wide, 300 m or more of wall within 250 m of it, half
//   or more of the walls' height at 60 degrees or more
//   tributaries hang 100 m or more over the trunk's floor
//   the trough near its 950 m width (half to twice: the judge measures to the walls' shoulders)
// Blender's own numbers on the same test (its out/glacial/gpu_tests.json) are recorded beside the port's.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/glacial/u_fit_test.mjs
//                                                                   (on a shared machine, behind $EIDO_GPU_WRAP)
//
// The valley is numpy's construction in doubles (test code: JavaScript per cell is allowed in tests only), with
// core/twins.py's random_field (tests/fluvial/_common.mjs). Writes tests/out/glacial/u_fit/ and u_fit_test.json.

import * as G from '../../core/gpu.js';
import { Fields } from '../../core/fields.js';
import { planLevels } from '../../core/levels.js';
import * as RUN from '../../run.js';
import * as FL from '../../solvers/fluvial.js';
import * as GL from '../../solvers/glacial.js';
import * as AV from '../../recipes/alpine_valley.js';
import * as C from '../parity/_common.mjs';
import { randomField } from '../fluvial/_common.mjs';
import { finish } from './_glacial.mjs';

const W = C.W;
const T = new C.Checks('glacial: the U-shape fit on a synthetic valley');
const n = 512, cell = 15.625, bench = 600.0;
const lv = planLevels(n * cell, n)[0];
// test_gpu.py synthetic_valley(n=512, cell=15.625, bench=600)
const tan30 = Math.tan(30.0 * (Math.PI / 180.0));
const rf = randomField(n, n, 0, 1, 3, 2);
const h0 = new Float32Array(n * n);
for (let j = 0; j < n; j++) {
    for (let i = 0; i < n; i++) {
        const X = lv.x0 + (i + 0.5) * cell, Y = lv.y0 + (j + 0.5) * cell;
        const left = lv.side / 2 - Y;
        const q = Math.min(Math.max(left / 2000.0, 0.0), 1.0);
        const river = 200.0 + 0.012 * left + bench * q * q * (3.0 - 2.0 * q);
        let h = river + tan30 * Math.abs(X);
        for (const side of [-1.0, 1.0]) {
            for (const yt of [-2500.0, 0.0, 2500.0]) {
                const d = Math.abs(Y - yt), along = Math.max(side * X, 0.0);
                const trib = river + 0.08 * along + 0.7 * tan30 * d;
                if (side * X > 300.0) h = Math.min(h, Math.max(trib, river + tan30 * 300.0));
            }
        }
        h0[j * n + i] = Math.min(h, 2600.0) + 2.0 * rf[j * n + i];
    }
}
const R = await G.init();
const fields = new Fields(lv, { h: R.field(n, n, 1, h0), bed: R.field(n, n, 1, h0) }, R);
const ctx = new RUN.StageContext({ plan: [lv], index: 0, level: lv, prepass: null, fresh: false, role: 'grow',
    pins: FL.edgePins(R, n, fields.h), shared: {}, seed: 1, base_elevation_m: 0.0, device: R, log: (m) => console.log(m) });
const [, stages] = AV.ALPINE_VALLEY.resolve({});
const params = { ...stages.find((s) => s.op === 'glacial').params, ela_m: 600.0, trough_depth_m: 600.0, cirques: false, channel_area_m2: 1.0e6 };
const t0 = performance.now();
const rec = await GL.carveLevel(fields, lv, params, 1, ctx, R);
const seconds = (performance.now() - t0) / 1000;
const after = await R.read(fields.h);
const dir = `${W.out('glacial')}/u_fit`;
Deno.mkdirSync(dir, { recursive: true });
Deno.writeFileSync(`${dir}/before.f32`, new Uint8Array(h0.buffer));
Deno.writeFileSync(`${dir}/after.f32`, new Uint8Array(after.buffer));
Deno.writeTextFileSync(`${dir}/meta.json`, JSON.stringify({ n, cell, x0: lv.x0, y0: lv.y0 }));
const py = W.pythonCmd(`${W.TESTS}/glacial/u_fit_judge.py`, dir);
if (!py) { T.ok('the judge (Blender\'s Python)', false, 'set EIDO_BLENDER_PYTHON'); Deno.exit(finish(T, 'u_fit_test')); }
const code = await W.run(py, { log: `${dir}/judge.log` });
const J = C.readJson(`${dir}/judge.json`);
if (code !== 0 || !J) {
    T.ok('the judge ran', false, `exit ${code}: see ${dir}/judge.log`);
} else {
    const b0 = J.before.u_exponent ?? 9, a = J.after, sec = J.sections;
    const med = (k) => { const v = sec.map((s) => s[k]).sort((x, y) => x - y); return 0.5 * (v[1] + v[2]); };
    const floor = med('floor_m'), rise = med('rise_250_m'), steep = med('steep');
    const blender = C.readJson(`${W.blenderTests() ?? ''}/out/glacial/gpu_tests.json`)?.results ?? {};
    const bnote = (k) => blender[k]?.detail ? `; Blender: ${blender[k].detail}` : '';
    T.ok('the V is no U before the carve (b under 1.5)', b0 < 1.5, `b ${b0.toFixed(2)}${bnote('trough on a synthetic valley: the V is no U before the carve (b under 1.5)')}`);
    T.ok('the carved trunk is a box trough (a level floor, walls at 60 degrees or more over most of their height, 300 m or more within 250 m of the floor)',
        floor >= 200 && floor <= 1000 && rise >= 300 && steep >= 0.5,
        `median floor ${floor.toFixed(0)} m wide, ${rise.toFixed(0)} m at 250 m from it, ${(steep * 100).toFixed(0)} % of the walls' height at ` +
        `60 deg or more (${JSON.stringify(sec.map((s) => [Math.round(s.floor_m), Math.round(s.rise_250_m), +s.steep.toFixed(2)]))}); the judge's U ` +
        `exponent ${a.u_exponent?.toFixed(2)} (sections ${JSON.stringify(a.u_exponents)}), depth ${a.trough_depth_m?.toFixed(0)} m; carve ` +
        `${rec.seeds} seeds, ${rec.streams} streams, ${seconds.toFixed(1)} s` +
        bnote('trough on a synthetic valley: the carved trunk is a box trough (a level floor, walls at 60 degrees or more over most of their height, 300 m or more within 250 m of the floor)'));
    T.ok('tributaries hang 100 m or more', (a.hanging_step_m ?? 0) >= 100,
        `largest step ${(a.hanging_step_m ?? 0).toFixed(0)} m, ${a.hanging_count} of 100 m or more; notches ${JSON.stringify(a.notch_heights_m)}` +
        bnote('trough on a synthetic valley: tributaries hang >= 100 m'));
    const tw = Number(params.trough_width_m);
    T.ok(`the trough near its ${tw} m width (half to twice: the judge measures to the walls' shoulders)`,
        (a.trough_width_m ?? 0) >= 0.5 * tw && (a.trough_width_m ?? 0) <= 2.0 * tw, `${(a.trough_width_m ?? 0).toFixed(0)} m` +
        bnote(`trough on a synthetic valley: the trough near its ${tw.toFixed(0)} m width (half to twice: the judge measures to the walls' shoulders)`));
    T.extra.judge = J;
}
T.extra.record = rec;
fields.dispose();
const c = finish(T, 'u_fit_test');
G.shutdown();
Deno.exit(c);
