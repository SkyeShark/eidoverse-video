// surface/mask_expr.js against palettes.py's evaluate (PORT_PLAN.md 8.2 row P14: "mask_expr.js equal to
// palettes.evaluate within 1e-5 on every palette's noise-free expressions"; Blender's test_expr.py, its package-1
// item 2). Every palette's expressions (layer weights, patch and ledge `where`, streaks_where, ramp and satmap `t`,
// tone, damp_where), and those of each recipe's 'auto' palette (its RECIPE_LOOKS) that no palette has (the fixture's
// auto:<recipe> cases), with every noise at its mean, compiled through build/ops.js and evaluated
//   1. by the float32 oracle (ops.NUM32, JavaScript on the CPU: test code), and
//   2. on the GPU (ops.WGSL: one compute kernel per palette through core/gpu.js, as the palette bake runs them),
// at the fixture's 4096 points of random maps in their units (tests/surface_data/surface_fixtures.py --expr: Blender's
// test_expr.py's sample_maps and the numpy evaluation in float64), within 1e-5 absolute;
//   3. the same expressions with their noise terms (noise(), fbm(), cells(); Blender's fixture has none: they reach
//      Blender only through the palette bake, whose C parity grades them), the GPU against the float32 oracle at the
//      same points placed over a 10 km window, with the footprint off, at 3 m and as the uniform uFoot = 0.75 m. The
//      seeds' offsets put the noise at large coordinates (fbm(80, 5) reads Perlin near 570 to 18,000 lattice units),
//      where an operand's last bit (the shader compiler fuses and reorders float operations; WGSL allows it) moves the
//      noise by up to about 1e-3 through an expression's gain: so the grade is float32's own band, measured by the
//      same oracle in float64 (ops.NUM): per expression, the GPU's p99.9 distance from the float32 oracle within twice
//      the float32 oracle's p99.9 distance from float64, plus 1e-4.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/mask_expr_test.mjs
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/surface_data/mask_expr_test.json.

import * as ops from '../../build/ops.js';
import * as P from '../../build/palettes.js';
import { Compiler } from '../../surface/mask_expr.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const { C } = S;
const T = new C.Checks('surface_data: the mask language compiled (mask_expr.js)');
const fx = S.fixture('expr');
if (!fx) {
    T.ok('expr fixtures present', false, 'make them: tests/surface_data/surface_fixtures.py --expr');
    Deno.exit(S.finish(T, 'mask_expr_test'));
}
const NOISE_TOL = 1e-4;
const cases = fx.manifest.cases;
const R = await G.init();

/** The palette's maps (name -> Float64Array of the fixture's float32 values) and the expressions. */
function caseData(c) {
    const maps = {};
    for (const k of Object.keys(c.inputs)) maps[k.slice(2)] = C.array(fx.dir, c.inputs[k]);
    const want = c.args.exprs.map((_e, k) => C.array(fx.dir, c.outputs[`e${String(k).padStart(3, '0')}`]));
    return { maps, want, exprs: c.args.exprs, consts: c.args.constants, tol: c.args.tol };
}

/** Points over a 10 km window (x, y) at the height map's z, a fixed sequence (an LCG: test data). */
function positions(n, height) {
    let s = 0x2545F491;
    const rnd = () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
    const pos = new Float32Array(4 * n);
    for (let k = 0; k < n; k++) {
        pos[4 * k] = -5000 + 10000 * rnd();
        pos[4 * k + 1] = -5000 + 10000 * rnd();
        pos[4 * k + 2] = height ? height[k] : 2000 * rnd();
        pos[4 * k + 3] = 0;
    }
    return pos;
}

/** The expressions on the GPU: one kernel, a row of outV per expression. */
async function gpuEval(tag, names, maps, exprs, consts, { flat, noise3 = true, texelM = null, pos = null }) {
    const W = ops.WGSL();
    const slot = Object.fromEntries(names.map((nm, k) => [nm, [k >> 2, k & 3]]));
    const ns = Math.max(1, (names.length + 3) >> 2);
    const npts = maps[names[0]]?.length ?? 4096;
    const read = (nm) => ({ code: `m${slot[nm][0]}.${'xyzw'[slot[nm][1]]}`, type: 'f32', wgsl: true });
    const posv = ['x', 'y', 'z'].map((c) => ({ code: `uPos.${c}`, type: 'f32', wgsl: true }));
    const foot = { code: 'u.uFoot', type: 'f32', wgsl: true };
    const blocks = exprs.map(([_label, e], k) => {
        W.reset();
        const c = new Compiler({ ops: W, read, pos: posv, constants: consts, noise3, texelM, flat, foot });
        const v = c.expr(e);
        return `    case ${k}i: {\n${W.body('      ')}\n      v = ${W.code(v)};\n    }`;
    });
    const head = Array.from({ length: ns }, (_x, s) => `//! sampler maps${s}\n`).join('') + '//! sampler posT\n' +
        '//! image outV r32f\n//! uniform float uFoot\n';
    const src = head + W.module() + '\n\nfn kmain(p: vec2<i32>) {\n  if (!inside(p, outV_size())) { return; }\n' +
        Array.from({ length: ns }, (_x, s) => `  let m${s} = maps${s}_at(vec2<i32>(p.x, 0));\n`).join('') +
        '  let uPos = posT_at(vec2<i32>(p.x, 0)).xyz;\n  var v = 0.0;\n  switch (p.y) {\n' + blocks.join('\n') +
        '\n    default: {}\n  }\n  outV_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));\n}\n';
    const k = R.kernel(`mask_expr_test_${tag}`, { source: src });
    const fields = {};
    for (let s = 0; s < ns; s++) {
        const a = new Float32Array(4 * npts);
        names.forEach((nm, q) => {
            if (q >> 2 !== s) return;
            for (let i = 0; i < npts; i++) a[4 * i + (q & 3)] = maps[nm][i];
        });
        fields[`maps${s}`] = R.field(1, npts, 4, a);
    }
    fields.posT = R.field(1, npts, 4, pos ?? new Float32Array(4 * npts));
    const out = R.field(exprs.length, npts, 1, null, 'f32');
    R.run(k, fields, { outV: out }, { uFoot: 0.75 });
    const got = await R.read(out);
    for (const f of Object.values(fields)) f.destroy();
    out.destroy();
    return got;
}

/** The oracle: ops.NUM32 per point (test code); ops.NUM (float64) with f64. */
function oracle(names, maps, exprs, consts, { flat, noise3 = true, texelM = null, pos = null, f64 = false }) {
    const npts = maps[names[0]]?.length ?? 4096;
    const out = exprs.map(() => new Float64Array(npts));
    let K = 0;
    const trees = exprs.map(([_l, e]) => P.parse(e));
    for (K = 0; K < npts; K++) {
        const p = pos ? [pos[4 * K], pos[4 * K + 1], pos[4 * K + 2]] : null;
        const c = new Compiler({ ops: f64 ? ops.NUM : ops.NUM32, read: (nm) => maps[nm][K], pos: p, constants: consts, noise3,
            texelM, flat, foot: Math.fround(0.75) });
        trees.forEach((t, q) => { out[q][K] = c.expr(t); });
    }
    return out;
}

/** The p99.9 and the largest of |a - b| (b a GPU result laid out by expression rows), and the count past tol. */
function spread(a, b, q, npts, tol) {
    const d = new Float64Array(npts);
    for (let i = 0; i < npts; i++) {
        const x = a[i], y = b === null ? 0 : (b.length === npts ? b[i] : b[q * npts + i]);
        d[i] = Number.isNaN(x) !== Number.isNaN(y) ? Infinity : Number.isNaN(x) ? 0 : Math.abs(x - y);
    }
    const past = d.filter((x) => x > tol).length;
    d.sort();
    return { max: d[npts - 1], p999: d[Math.floor(0.999 * (npts - 1))], past };
}

const rows = [];
let worstOracle = 0, worstGpu = 0, nexpr = 0, nnoise = 0, worstNoise = 0, worstNoiseAt = '';
for (const c of cases) {
    const { maps, want, exprs, consts, tol } = caseData(c);
    const names = Object.keys(maps).sort();
    nexpr += exprs.length;
    const orc = oracle(names, maps, exprs, consts, { flat: true });
    const tag = c.label.replace(/[^A-Za-z0-9_]/g, '_');
    const gpu = await gpuEval(tag, names, maps, exprs, consts, { flat: true });
    const npts = want[0].length;
    const bad = [];
    let wo = 0, wg = 0;
    exprs.forEach(([label], q) => {
        let eo = 0, eg = 0;
        for (let i = 0; i < npts; i++) {
            eo = Math.max(eo, Math.abs(orc[q][i] - want[q][i]));
            eg = Math.max(eg, Math.abs(gpu[q * npts + i] - want[q][i]));
            if (Number.isNaN(orc[q][i]) !== Number.isNaN(want[q][i]) || Number.isNaN(gpu[q * npts + i]) !== Number.isNaN(want[q][i])) {
                eo = Infinity;
            }
        }
        if (!(eo <= tol && eg <= tol)) bad.push(`${label} (oracle ${S.sci(eo, 1)}, GPU ${S.sci(eg, 1)})`);
        wo = Math.max(wo, eo);
        wg = Math.max(wg, eg);
    });
    worstOracle = Math.max(worstOracle, wo);
    worstGpu = Math.max(worstGpu, wg);
    // 3. the noise terms: the expressions that have one, both backends, three footprints
    const noisy = exprs.filter(([, e]) => /\b(noise|fbm|cells)\s*\(/.test(e));
    let wn = 0;
    const noiseRows = [];
    if (noisy.length) {
        const pal = c.args.recipe ? P.get('auto', c.args.recipe) : P.get(c.label);
        const noise3 = (pal.options ?? {}).detile === 'rotate';
        const pos = positions(npts, maps.height ?? null);
        for (const texelM of [null, 3.0, 'uniform']) {
            const o = oracle(names, maps, noisy, consts, { flat: false, noise3, texelM, pos });
            const o64 = oracle(names, maps, noisy, consts, { flat: false, noise3, texelM, pos, f64: true });
            const g = await gpuEval(`${tag}_noise_${texelM}`, names, maps, noisy, consts, { flat: false, noise3, texelM, pos });
            noisy.forEach(([label, e], q) => {
                const gd = spread(o[q], g, q, npts, NOISE_TOL), fd = spread(o[q], o64[q], 0, npts, NOISE_TOL);
                const allow = 2 * fd.p999 + NOISE_TOL;
                const r = { expr: label, footprint: texelM, gpu_p999: gd.p999, gpu_max: gd.max, gpu_past: gd.past,
                    f32_vs_f64_p999: fd.p999, f32_vs_f64_max: fd.max, allow, ok: gd.p999 <= allow,
                    src: e.length > 160 ? e.slice(0, 160) + '...' : e };
                noiseRows.push(r);
                if (gd.p999 / allow > wn) wn = gd.p999 / allow;
                if (gd.p999 / allow > worstNoise) { worstNoise = gd.p999 / allow; worstNoiseAt = `${c.label} ${label} (footprint ${texelM})`; }
            });
        }
        nnoise += noisy.length;
        for (const r of noiseRows.filter((x) => x.gpu_max > NOISE_TOL).sort((a, b) => b.gpu_p999 - a.gpu_p999).slice(0, 3)) {
            console.log(`   ${r.expr} (footprint ${r.footprint}): GPU p99.9 ${S.sci(r.gpu_p999, 2)} (max ${S.sci(r.gpu_max, 2)}), ` +
                `float32 against float64 p99.9 ${S.sci(r.f32_vs_f64_p999, 2)} (max ${S.sci(r.f32_vs_f64_max, 2)})${r.ok ? '' : ' FAIL'}`);
        }
    }
    rows.push({ palette: c.label, expressions: exprs.length, worst_oracle: wo, worst_gpu: wg, with_noise: noisy.length,
        worst_noise_gpu_vs_oracle: wn, noise: noiseRows, failed: bad });
    console.log(`[mask_expr] ${c.label}: ${exprs.length} expressions, oracle ${S.sci(wo, 2)}, GPU ${S.sci(wg, 2)}` +
        (noisy.length ? `; ${noisy.length} with noise, GPU against oracle at ${wn.toFixed(2)} of its allowance` : '') +
        (bad.length ? `; FAIL ${bad.slice(0, 3).join(', ')}` : ''));
}
const failed = rows.filter((r) => r.failed.length);
const nlooks = cases.filter((c) => c.args.recipe).length;
T.ok(`the float32 oracle (ops.NUM32) equals palettes.evaluate within 1e-5 on every palette's noise-free expressions ` +
    `(${nexpr} over ${cases.length - nlooks} palettes and ${nlooks} recipes' 'auto' palettes, 4096 points each)`,
    failed.every((r) => r.worst_oracle <= 1e-5) && worstOracle <= 1e-5,
    `worst ${S.sci(worstOracle, 2)}`);
T.ok(`the GPU (ops.WGSL through core/gpu.js) equals palettes.evaluate within 1e-5 on the same expressions`,
    worstGpu <= 1e-5 && failed.length === 0, `worst ${S.sci(worstGpu, 2)}` +
    (failed.length ? `; ${failed.map((r) => `${r.palette}: ${r.failed.slice(0, 2).join(', ')}`).join('; ')}` : ''));
T.ok(`with their noise terms (${nnoise} expressions; footprint off, 3 m, uniform) the GPU stays in float32's band about the ` +
    `oracle (p99.9 within twice the float32 oracle's p99.9 from float64, plus ${NOISE_TOL})`, worstNoise <= 1,
    `worst at ${worstNoise.toFixed(2)} of its allowance${worstNoiseAt ? ', ' + worstNoiseAt : ''}`);
G.shutdown();
Deno.exit(S.finish(T, 'mask_expr_test', { palettes: rows }));
