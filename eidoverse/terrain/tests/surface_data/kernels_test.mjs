// The surface data package's kernel fixtures (PORT_PLAN.md 8.2 row P14, 5.1, 5.3; SURFACING_DESIGN.md 5.4, package 1,
// item 2): every case the Blender edition's own Python made of its eleven bake kernels (tests/surface_data/
// surface_fixtures.py --kernels: blender/tests/terrain/surface_data/test_kernels.py's cases through surface/twins.py,
// the 96 x 80 terrain-like field with a cliff band, a valley, loose cover, sand, snow and catchments from 2 m to
// 2 km) dispatched once through the port's kernels (surface/kernels/*.wgsl) on the production runner, each output
// channel within 1e-4 of its range (the Blender edition's own grade, and its kernels' own result: 16 of 16).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/kernels_test.mjs
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/surface_data/kernels_test.json. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as SB from '../../surface/bake.js';
import * as S from './_surface.mjs';

const { C } = S;
const T = new C.Checks('surface_data: kernel fixtures');
const R = await G.init();
const out = { kernels: {} };

// the built-ins each kernel leans on (tests/parity/_common.mjs M and ABS): what a correct port's rounding may move
const USES = {
    blur: { uses: ['exp', 'divide'] },
    upsample2: { uses: [] },
    field_normal: { uses: ['sqrt', 'divide'] },
    crest: { uses: ['exp', 'pow', 'sqrt', 'divide'] },          // tanh is two exps
    // the stripes' wave reaches about 30 radians: sin and cos by their absolute bound there
    phacelle: { uses: ['exp', 'pow', 'atan', 'sqrt', 'divide', 'sin', 'cos'], abs: C.trigAbs(32) },
    cavity: { uses: ['exp', 'sqrt', 'divide', 'sin', 'cos'], abs: C.trigAbs(6.3) },
    carry_src: { uses: ['atan', 'sqrt', 'divide'], exact: { outS: [2] } },   // valid: a decision
    streak: { uses: ['exp', 'divide'] },
    fill: { uses: [] },
    pin_inflow: { uses: ['divide', 'pow'] },
    route_colour: { uses: ['divide', 'pow'] },
};

const fx = S.fixture('kernels');
if (!fx) {
    T.ok('kernel fixtures present', false, 'make them: tests/surface_data/surface_fixtures.py --kernels');
} else {
    T.extra.fixture_key = fx.key;
    for (const name of SB.KERNELS) {
        const k = SB.kernel(R, name);
        const r = await C.kernelCases(R, SB.PREFIX + name, { fixture: fx, kernel: k, ...USES[name] });
        out.kernels[name] = { n: r.n, worst: r.worst, failed: r.failed,
            cases: r.cases.map((c) => ({ label: c.label, worst: c.worst,
                channels: c.channels.map((x) => [x.image, x.channel, +x.over.toPrecision(4), x.ok]) })) };
        T.ok(`${name}: ${r.n} kernel fixture case(s) within 1e-4 of each channel's range`, r.ok && r.n > 0, r.detail);
    }
    const n = Object.values(out.kernels).reduce((s, r) => s + r.n, 0);
    T.ok(`every one of the ${fx.manifest.cases.length} Blender cases was run`, n === fx.manifest.cases.length, `${n} run`);
}

G.shutdown();
Deno.exit(S.finish(T, 'kernels_test', out));
