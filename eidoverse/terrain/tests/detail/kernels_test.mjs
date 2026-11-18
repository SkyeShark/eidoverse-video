// The detail package's kernel fixtures (PORT_PLAN.md 8.2 row P12, 5.1, 5.3): every case the Blender edition's own
// Python made of its five kernels (tests/parity/fixtures.py --kernels: the Blender detail package's parity cases,
// blender/tests/terrain/detail/test_detail_gpu.py, through the numpy twins) dispatched once through the port's
// kernels on the production runner, each output channel within 1e-4 of its range (the Blender edition's own grade):
//   pipes_flux, pipes_water, pipes_transport, pipes_thermal   open, periodic and pinned, random rain (the PCG hash)
//                                                            and edge outflow on, the ground 500 cells up plus a change
//   breakup                                                  0.5 m and 4 m cells, 40 km from the origin (the plan's
//                                                            "breakup at 40 km from the origin")
// And the GLSL's `precise` lines, which WGSL cannot mark (kernels/detail/exact.wgsl keeps them as written):
//   in the kernels themselves   pipes_water's erosion and deposition hand the sediment exactly what the rounded
//                               ground changed (took = dl - (dl - e)), cell by cell on the fixture inputs; and
//                               pipes_thermal's ground and Kahan carry follow its pass's exchange exactly
//   compiled alone              the Kahan step (carry = dbc - ((c + dbc) - c)) on 65,536 sums through exact(), and
//                               written plainly: a measurement of this machine's shader compiler, which folds it
// The mass these keep is tests/detail/conservation_test.mjs's question (ground + sediment over 3,000 steps, the
// Blender test's bound).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/detail/kernels_test.mjs
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/detail/kernels_test.json. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as D from './_detail.mjs';

const { C } = D;
const T = new C.Checks('detail: kernel fixtures');
const R = await G.init();
const out = { kernels: {}, precise: {} };

// ------------------------------------------------------------------------------------------- the fixtures ---

const KERNELS = [
    ['pipes_flux', ['divide']],
    ['pipes_water', ['sqrt', 'divide']],
    ['pipes_transport', ['divide']],
    ['pipes_thermal', []],
    ['breakup', ['tan', 'exp', 'divide']],
];
for (const [name, uses] of KERNELS) {
    const r = await C.kernelCases(R, name, { uses });
    if (!r) {
        T.ok(`${name}: kernel fixtures`, false, 'no kernel fixtures: run tests/parity/fixtures.py --kernels in Blender\'s Python');
        continue;
    }
    out.kernels[name] = { n: r.n, worst: r.worst, failed: r.failed,
        cases: r.cases.map((c) => ({ label: c.label, worst: c.worst, channels: c.channels.map((x) => [x.image, x.channel, +x.over.toPrecision(4)]) })) };
    T.ok(`${name}: ${r.n} kernel fixture cases within 1e-4 of each channel's range`, r.ok && r.n > 0, r.detail);
}

// ------------------------------------------------------------- `precise` in the kernels: pipes_water's exchange ---

// pipes_water on its fixture inputs: on every cell that eroded (the ground went down) the sediment gained exactly
// fround(s + (dl - dl')), the ground's own loss; on every cell that took a deposit, it lost exactly
// fround(s - (dl' - dl)). A compiler that folded took = dl - (dl - e) back to e would break this on cells where the
// rounding of dl - e is not exact.
{
    const fx = C.loadFixture('kernels');
    const cases = fx ? fx.manifest.cases.filter((c) => c.kernel === 'pipes_water') : [];
    let eroded = 0, deposited = 0, exactE = 0, exactD = 0, folded = 0, rounded = 0;
    for (const c of cases) {
        const samplers = {};
        for (const [s, a] of Object.entries(c.inputs)) samplers[s] = R.field(a.shape[0], a.shape[1], a.shape[2], C.array(fx.dir, a));
        const o = R.field(80, 96, 4), v = R.field(80, 96, 4);
        R.run('pipes_water', samplers, { outS: o, outV: v }, c.uniforms);
        const st = C.array(fx.dir, c.inputs.st), pin = C.array(fx.dir, c.inputs.pin);
        const got = await R.read(o);
        for (let i = 0; i < got.length / 4; i++) {
            const dl0 = st[4 * i], s0 = st[4 * i + 2], dl1 = got[4 * i], s1 = got[4 * i + 2];
            // in pinned mode a cell with a pin weight moves again after the exchange: only free cells compare
            if (c.uniforms.uBound === 2 && pin[4 * i] !== 0) continue;
            // took = dl - lowered and gave = raised - dl in float32, as the GLSL computes them (dl0 - dl1 is exact in
            // doubles: two float32 values)
            if (dl1 < dl0) {
                eroded++;
                if (s1 === Math.fround(s0 + Math.fround(dl0 - dl1))) exactE++;
                else folded++;
            } else if (dl1 > dl0) {
                deposited++;
                if (s1 === Math.fround(s0 - Math.fround(dl1 - dl0))) exactD++;
                else rounded++;
            }
        }
        for (const f of [...Object.values(samplers), o, v]) f.destroy();
    }
    out.precise.pipes_water = { cases: cases.length, eroded, exact_eroded: exactE, deposited, exact_deposited: exactD };
    T.ok(`pipes_water: the sediment takes exactly what the rounded ground lost (the GLSL's precise lines) on every ` +
        `eroding and depositing cell of the ${cases.length} fixture cases`,
        cases.length > 0 && eroded > 0 && deposited > 0 && folded === 0 && rounded === 0,
        `eroding cells ${exactE} of ${eroded} exact, depositing cells ${exactD} of ${deposited} exact`);
}

// ------------------------------------------------------------- `precise` compiled alone: the Kahan carry ---

// pipes_thermal's three lines on their own, on sums whose rounding is not exact: carry must be the rounding error
// fround(dbc - fround(fround(c + dbc) - c)), never 0 where that error is not 0. Written plainly (a measurement of
// this machine's compiler, the reason for kernels/detail/exact.wgsl) and through exact() (a check).
{
    const N = 65536, data = new Float32Array(N * 4);
    let s = 987654321;
    const rnd = () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
    for (let i = 0; i < N; i++) {
        const c = Math.fround((rnd() - 0.5) * 8);                 // a change of a few cells
        const db = Math.fround((rnd() - 0.5) * 1e-3 * 10 ** (-4 * rnd()));    // an exchange of 1e-7 .. 1e-3 cells
        const ta = Math.fround((rnd() - 0.5) * 1e-7);             // the carry from the last pass
        data.set([c, db, ta, 0], 4 * i);
    }
    const body = (ex) => ex
        ? '  let z = exact_zero(outC_size());\n  let dbc = exact(x.y + x.z, z);\n  let dl = exact(x.x + dbc, z);\n' +
          '  let carry = exact(dbc - exact(dl - x.x, z), z);\n'
        : '  let dbc = x.y + x.z;\n  let dl = x.x + dbc;\n  let carry = dbc - (dl - x.x);\n';
    for (const ex of [false, true]) {
        const k = R.kernel(ex ? 'detail_kahan_exact' : 'detail_kahan_plain', { source: (ex ? '//! include detail/exact\n' : '') +
            '//! sampler v\n//! image outC rgba32f\nfn kmain(p: vec2<i32>) {\n  if (!inside(p, outC_size())) { return; }\n' +
            '  let x = v_at(p);\n' + body(ex) + '  outC_store(p, vec4<f32>(dbc, dl, carry, 0.0));\n}\n' });
        const v = R.field(256, 256, 4, data), o = R.field(256, 256, 4);
        R.run(k, { v }, { outC: o }, {});
        const got = await R.read(o);
        let nonzero = 0, exact = 0, zeroWhereNot = 0;
        for (let i = 0; i < N; i++) {
            const [c, db, ta] = [data[4 * i], data[4 * i + 1], data[4 * i + 2]];
            const dbc = Math.fround(db + ta), dl = Math.fround(c + dbc), carry = Math.fround(dbc - Math.fround(dl - c));
            if (carry !== 0) nonzero++;
            if (got[4 * i + 2] === carry && got[4 * i] === dbc && got[4 * i + 1] === dl) exact++;
            if (carry !== 0 && got[4 * i + 2] === 0) zeroWhereNot++;
        }
        out.precise[ex ? 'kahan_exact' : 'kahan_plain'] = { sums: N, carry_nonzero: nonzero, exact, folded_to_zero: zeroWhereNot };
        if (ex) {
            T.ok('the Kahan carry through exact() (kernels/detail/exact.wgsl): every sum\'s carry exact', exact === N && zeroWhereNot === 0,
                `${exact} of ${N} exact; ${nonzero} sums have a nonzero carry, ${zeroWhereNot} of them came out 0`);
        } else {
            console.log(`     (measured: the same three lines written plainly: ${exact} of ${N} exact, ${zeroWhereNot} of the ` +
                `${nonzero} nonzero carries folded to 0 by this machine's shader compiler)`);
        }
        v.destroy();
        o.destroy();
    }
}

// ------------------------------------------------------------- `precise` in the kernels: pipes_thermal's carry ---

// pipes_thermal on its open fixture case, with the accumulator's x set to 0 so that outT.x is the pass's exchange
// db exactly: then every cell's ground and carry follow from db as the GLSL's three precise lines say.
{
    const fx = C.loadFixture('kernels');
    const c = fx ? fx.manifest.cases.find((x) => x.kernel === 'pipes_thermal' && x.uniforms.uBound === 0) : null;
    if (c) {
        const ta = Float32Array.from(C.array(fx.dir, c.inputs.tacc));
        let s = 13579;
        const rnd = () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
        for (let i = 0; i < ta.length / 4; i++) { ta[4 * i] = 0; ta[4 * i + 1] = Math.fround((rnd() - 0.5) * 2e-7); }
        const samplers = {};
        for (const [n, a] of Object.entries(c.inputs)) {
            samplers[n] = R.field(a.shape[0], a.shape[1], a.shape[2], n === 'tacc' ? ta : C.array(fx.dir, a));
        }
        const oS = R.field(80, 96, 4), oT = R.field(80, 96, 4);
        R.run('pipes_thermal', samplers, { outS: oS, outT: oT }, c.uniforms);
        const [gs, gt] = await R.readAll([oS, oT]);
        const st = C.array(fx.dir, c.inputs.st);
        let exact = 0, moved = 0, carries = 0;
        for (let i = 0; i < gs.length / 4; i++) {
            const db = gt[4 * i], cx = st[4 * i];
            const dbc = Math.fround(db + ta[4 * i + 1]), dl = Math.fround(cx + dbc), carry = Math.fround(dbc - Math.fround(dl - cx));
            if (db !== 0) moved++;
            if (carry !== 0) carries++;
            if (gs[4 * i] === dl && gt[4 * i + 1] === carry) exact++;
        }
        out.precise.pipes_thermal = { cells: gs.length / 4, moved, carries, exact };
        T.ok('pipes_thermal: every cell\'s ground and Kahan carry exactly as the GLSL\'s precise lines give them',
            exact === gs.length / 4 && carries > 0, `${exact} of ${gs.length / 4} cells exact (${moved} moved, ${carries} with a carry)`);
        for (const f of [...Object.values(samplers), oS, oT]) f.destroy();
    } else {
        T.ok('pipes_thermal: the carry in the kernel', false, 'no open pipes_thermal fixture case');
    }
}

T.extra.adapter = R.info?.description ?? null;
T.extra.results = out;
const code = D.finish(T, 'kernels_test');
G.shutdown();
Deno.exit(code);
