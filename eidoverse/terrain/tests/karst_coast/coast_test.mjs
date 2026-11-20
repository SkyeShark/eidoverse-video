// The coast ops on the GPU against coast.py on the twin device (PORT_PLAN.md 8.2 row P11, 5.1 function fixtures):
// solvers/coast.js opCoast on blender/tests/terrain/coast/test_coast_gpu.py's synthetic downland coast (256^2 at 4 m)
// with that test's parameters (stacks, sheltered beaches) and with the chalk's (its bedded column, scars, a shingle beach
// of varying width), and opCoastLand on a fresh level, against the same calls made by tests/karst_coast/
// karst_coast_expected.py on the twin device (numpy's world noise, Blender's Python).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/karst_coast/coast_test.mjs
//         (on a shared machine, behind $EIDO_GPU_WRAP)
//
// The grade is the Blender GPU test's own for its GPU against this twin (test_coast_gpu.py test_op): the surface within
// 0.05 m on 99.9 % of cells. The GPU's world noise agrees with numpy's to 5e-6 of its range, and a cell whose level set
// sits within that of zero may fall either side of the cut, so a few cells along the cliff foot move a whole cell's
// height; every other field is reported (its share within 0.05 m, its 99th percentile and worst difference). The fresh
// land: s0, U, h and bed within 1e-5 of their ranges. JavaScript per cell here is test code. Writes
// tests/out/karst_coast/coast_test.json.

import { Fields } from '../../core/fields.js';
import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import { StageContext } from '../../run.js';
import * as CO from '../../solvers/coast.js';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const T = new C.Checks('karst and coast: the coast ops against the twin device');
const fx = KC.loadFixtures();
const R = await G.init();
const results = {};

function compare(got, want) {
    const d = new Float64Array(want.length);
    let over = 0;
    for (let i = 0; i < want.length; i++) {
        d[i] = Math.abs(got[i] - want[i]);
        if (!(d[i] <= 0.05)) over++;
    }
    const s = Float64Array.from(d).sort();
    return { within_005: 1 - over / want.length, p99: s[Math.floor(0.99 * (s.length - 1))], max: s[s.length - 1] };
}

for (const c of fx ? KC.findCases(fx, 'coast.op_coast') : []) {
    const lv = Level.fromDict(c.args.level);
    const land = C.array(fx.dir, c.inputs.land);
    const f = new Fields(lv, { h: Float32Array.from(land), bed: Float32Array.from(land) }, R);
    const logs = [];
    const ctx = new StageContext({ plan: [lv], index: 0, level: lv, fresh: false, role: 'grow', pins: null, shared: {},
        sea_level: c.args.sea_level, device: R, log: (m) => logs.push(m) });
    const t0 = performance.now();
    try {
        await CO.opCoast(f, lv, structuredClone(c.args.params), c.args.seed, ctx);
        await R.idle();
    } catch (e) {
        T.ok(`${c.label}: runs`, false, `${e.name}: ${e.message}`.slice(0, 800));
        continue;
    }
    const sec = (performance.now() - t0) / 1000;
    const row = { seconds: +sec.toFixed(2), numpy_seconds: c.args.seconds, fields: {}, log: logs, twin_log: c.args.log,
        port_log: ctx.shared.coast_log };
    const names = Object.keys(c.outputs);
    const missing = names.filter((k) => !(k in f));
    const got = await R.readAll(names.filter((k) => k in f).map((k) => f[k]));
    names.filter((k) => k in f).forEach((k, i) => { row.fields[k] = compare(got[i], C.array(fx.dir, c.outputs[k])); });
    results[c.label] = row;
    const h = row.fields.h;
    T.ok(`${c.label}: the surface within 0.05 m on ${(100 * h.within_005).toFixed(3)} % of cells (the Blender GPU test's ` +
        `99.9 %); ${sec.toFixed(2)} s (numpy ${c.args.seconds} s)`, h.within_005 >= 0.999 && !missing.length,
    `p99 ${C.sci(h.p99)} m, worst ${C.sci(h.max)} m; ` + Object.entries(row.fields).filter(([k]) => k !== 'h')
        .map(([k, g]) => `${k} ${(100 * g.within_005).toFixed(2)} %`).join(', ') + (missing.length ? `; missing ${missing}` : ''));
    f.dispose?.();
}

for (const c of fx ? KC.findCases(fx, 'coast.op_coast_land') : []) {
    const lv = Level.fromDict(c.args.level);
    const f = new Fields(lv, {}, R);
    const ctx = new StageContext({ plan: [lv], index: 0, level: lv, fresh: true, role: 'grow', pins: null, shared: {},
        sea_level: 0.0, device: R, log: () => {} });
    await CO.opCoastLand(f, lv, structuredClone(c.args.params), c.args.seed, ctx);
    const names = Object.keys(c.outputs);
    const got = await R.readAll(names.map((k) => f[k]));
    const fails = [], worst = {};
    names.forEach((k, i) => {
        const g = C.gradeArray(got[i], C.array(fx.dir, c.outputs[k]), { k: 1e-5, uses: ['exp'] });
        worst[k] = g.over;
        if (!g.ok) fails.push(`${k} ${C.sci(g.over)}`);
    });
    results[c.label] = worst;
    T.ok(`${c.label}: ${names.join(', ')} within 1e-5 of their ranges`, !fails.length,
        fails.join('; ') || Object.entries(worst).map(([k, v]) => `${k} ${C.sci(v)}`).join(', '));
}
if (!fx) T.ok('coast fixtures', false, KC.NO_FIXTURES);
Deno.exit(KC.finish(T, 'coast_test', { results }));
