// The detail package's function fixtures (PORT_PLAN.md 8.2 row P12, 5.1, 5.3): the Blender edition's numpy code of
// solvers/hydraulic.py and solvers/detail.py on recorded inputs (tests/detail/blender_detail_fixtures.py, run with
// Blender's own Python), against the port's GPU replacements on the same inputs. Every output of every case is
// graded at max(the plan's grade for its kind, 1.25 x the case's own floor) of its range (the floor: Blender's own
// function under one-ulp nudges of its float32 inputs and its world noise, five patterns, as the plan's stage replay
// is graded, 5.3), with the rounding floor of the built-ins leaned on (tests/parity/_common.mjs: m float32 steps of
// the largest value). The kinds (plan 5.3):
//   plans             the term tables bit for bit (float32 as numpy stores them, both made in doubles), the uniforms
//                     and the anchor's scale within 1e-12 relative
//   function, float   1e-5: anchor (blurs), micro_relief and phacelle_noise (noise), strength (noise), finish (the
//                     blend and the record fields), rockness, flow_direction, gully_relief and op_gully (slope masks
//                     and noise steered by the slope: masks, which the plan allows 1e-4, held to 1e-5 since the
//                     smoothed slope is the box mean of height differences, kernels/detail/box_gradient.wgsl)
//   function, masks   1e-4: op_planation (a mask of world noise through a steep smoothstep: the noise's own float32
//                     grade, 1e-6 of its range, times the smoothstep's slope and the relief it cuts)
//   evolving          1e-4: relax, op_breakup, op_hydraulic (one call from Blender's input: the stage-replay grade)
//   bedding           strength with bedding planes resolved, 40 km from the origin: the kernel's dip plane uDipX x +
//                     uDipY y is float32 at world coordinates (about 1,800 m there), so one rounding of it, fused or
//                     not, moves the bed lines by an ulp of that height; the allowance is that ulp's effect, analytic
//                     (bedAllowance below). A defect of the Blender kernel, reported, reproduced here as it is
// The worst of each function is reported.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/detail/functions_test.mjs
//         [--only hydraulic.op_hydraulic,detail.strength,...]          (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/detail/functions_test.json. JavaScript per cell here is test code.

import { Fields } from '../../core/fields.js';
import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import * as DT from '../../solvers/detail.js';
import * as HY from '../../solvers/hydraulic.js';
import * as D from './_detail.mjs';

const { C } = D;
const A = D.argsOf();
const ONLY = A.list('--only');
const T = new C.Checks('detail: function fixtures');
const R = await G.init();
const fx = C.loadFixture('functions/detail');
if (!fx) {
    T.ok('detail function fixtures', false, 'none: run tests/detail/blender_detail_fixtures.py with Blender\'s Python');
    Deno.exit(D.finish(T, 'functions_test'));
}
const results = {};

// ------------------------------------------------------------------------------------------------- helpers ---

const arr = (c, name, where = 'inputs') => C.array(fx.dir, c[where][name]);
const f32 = (a) => (a instanceof Float32Array ? a : Float32Array.from(a, (x) => Math.fround(x)));
const shapeOf = (c, name, where = 'inputs') => c[where][name].shape;
const fieldOf = (c, name, where = 'inputs') => {
    const s = shapeOf(c, name, where);
    return R.field(s[0], s[1], s.length > 2 ? s[2] : 1, f32(arr(c, name, where)));
};
const rec = (fn) => (results[fn] ??= { cases: 0, failed: [], worst: 0, rows: [] });

let CASE = null;                                        // the case being graded (its floor)

/** Grade a field read back against a fixture output at max(k, 1.25 x the case's floor for it) of its range (opts:
 * uses, abs); returns whether it passed (and records it). */
function grade(fn, label, name, got, want, k, uses = [], opts = {}) {
    const floor = CASE?.values?.floor?.[opts.floorKey ?? name] ?? 0;
    const kk = Math.max(k, 1.25 * floor);
    const g = C.gradeArray(got, want, { k: kk, uses, abs: opts.abs ?? 0 });
    const r = rec(fn);
    r.worst = Math.max(r.worst, g.over);
    r.rows.push({ label, output: name, ok: g.ok, over: +g.over.toPrecision(4), k: kk, floor, err: g.err, tol: g.tol, range: g.range });
    if (!g.ok) console.log(`  FAIL ${fn}: ${label}: ${name}: err ${C.sci(g.err)}, ${C.sci(g.over)} of range (grade ${C.sci(kk)}, tol ${C.sci(g.tol)})`);
    return g.ok;
}

/** The bedding term's float32 allowance (functions_test's header): the dip plane's height h_d = |uDipX x| + |uDipY y|
 * at the level's far corner, one rounding of each product and of their sum (3 ulp of it, fused or not) moves the bed
 * line by that much, and a line l = max(1 - dist / (w / 2), 0)^2 changes by 2 dist_error / (w / 2); R and D take amp
 * times that, kfac and Sc the derivative of their function of R. { R, D, kfac, sc_abs } absolute. */
function bedAllowance(u, lv, kfacMax, scMax) {
    if (!(u.uBedAmpS > 0 || u.uBedAmpD > 0)) return { R: 0, D: 0, kfac: 0, sc_abs: 0 };
    const x = Math.max(Math.abs(lv.x0), Math.abs(lv.x0 + lv.side)), y = Math.max(Math.abs(lv.y0), Math.abs(lv.y0 + lv.side));
    const hd = Math.abs(u.uDipX) * x + Math.abs(u.uDipY) * y;
    const dl = 2 * (3 * C.ulp32(hd)) / (0.5 * u.uBedWidth);
    const dR = u.uBedAmpS * dl;
    return { R: dR, D: u.uBedAmpD * dl, kfac: Math.LN2 * u.uKOct * kfacMax * dR,
        sc_abs: (1 + scMax * scMax) * (u.uSpreadDeg * Math.PI / 180) * dR };
}
function finishCase(fn, label, oks) {
    const r = rec(fn);
    r.cases++;
    if (!oks.every(Boolean)) r.failed.push(label);
}
async function readField(f) { return await R.read(f); }
const pinsCtx = (c) => {
    if (!c.args.ctx_pins) return null;
    return { pins: { pin_w: fieldOf(c, 'pin__pin_w'), pin_h: fieldOf(c, 'pin__pin_h') }, log: () => {} };
};

/** An op case: Fields from the f__ inputs, the port's op, every f__ output graded. */
async function opCase(c, op, k, uses) {
    const lv = Level.fromDict(c.args.level);
    const fields = new Fields(lv, null, R);
    for (const name of Object.keys(c.inputs)) if (name.startsWith('f__')) fields.set(name.slice(3), f32(arr(c, name)));
    const ctx = pinsCtx(c) ?? { log: () => {} };
    await op(fields, lv, structuredClone(c.args.params), c.args.seed, ctx);
    const oks = [];
    for (const name of Object.keys(c.outputs)) {
        const key = name.slice(3);
        if (!(key in fields)) {
            rec(c.function).rows.push({ label: c.label, output: key, ok: false, missing: true });
            console.log(`  FAIL ${c.function}: ${c.label}: no field ${key} after the op`);
            oks.push(false);
            continue;
        }
        oks.push(grade(c.function, c.label, key, await readField(fields[key]), arr(c, name, 'outputs'), k, uses, { floorKey: name }));
    }
    for (const name of Object.keys(fields)) if (!(`f__${name}` in c.outputs)) {
        oks.push(false);
        console.log(`  FAIL ${c.function}: ${c.label}: the port made a field ${name} Blender did not`);
    }
    if (ctx?.pins) for (const f of Object.values(ctx.pins)) f.destroy();
    fields.dispose();
    finishCase(c.function, c.label, oks);
}

// a kernel that evaluates the Phacelle include alone for one octave row (the function test of phacelle_noise)
const PHACELLE_PROBE = R.kernel('detail_phacelle_probe', { source: '//! include noise\n//! include detail/phacelle\n' +
    '//! sampler dx\n//! sampler dy\n//! sampler oct\n//! image outP rgba32f\n//! uniform int uRow\n//! uniform float uNorm\n' +
    'fn kmain(p: vec2<i32>) {\n  if (!inside(p, outP_size())) { return; }\n' +
    '  let a = oct_at(vec2<i32>(2 * u.uRow, 0));\n  let b = oct_at(vec2<i32>(2 * u.uRow + 1, 0));\n' +
    '  let at = phacelle_coord(p, vec2<i32>(b.xy), a.zw, i32(b.z), b.w);\n' +
    '  outP_store(p, phacelle_noise(at.c, at.f, vec2<f32>(dx_at(p).x, dy_at(p).x), 1.0, 0.25, u.uNorm, vec2<i32>(0, 0)));\n}\n' });

// ---------------------------------------------------------------------------------------------- the cases ---

const want = (fn) => !ONLY || ONLY.includes(fn);
for (const c of fx.manifest.cases) {
    if (!want(c.function)) continue;
    const fn = c.function, a = c.args;
    CASE = c;
    try {
        if (fn === 'hydraulic.rockness') {
            const h = fieldOf(c, 'h');
            const rk = HY.rockness(h, a.cell, a.slope_deg);
            finishCase(fn, c.label, [grade(fn, c.label, 'rk', await readField(rk), arr(c, 'rk', 'outputs'), 1e-5, ['sqrt', 'atan'])]);
            h.destroy();
            rk.destroy();
        } else if (fn === 'hydraulic.anchor') {
            const ch = fieldOf(c, 'change');
            const out = HY.anchor(ch, a.scale_cells);
            finishCase(fn, c.label, [grade(fn, c.label, 'a', await readField(out), arr(c, 'a', 'outputs'), 1e-5)]);
            ch.destroy();
            out.destroy();
        } else if (fn === 'hydraulic.anchor_scale_m') {
            const lvs = a.levels.map((d) => Level.fromDict(d));
            const got = lvs.map((lv) => HY.anchorScaleM(lv));
            const same = got.every((v, i) => v === c.values.scales[i]) && HY.anchorScaleM(lvs[0], 20.0) === c.values.given;
            rec(fn).rows.push({ label: c.label, ok: same, got, want: c.values.scales });
            finishCase(fn, c.label, [same]);
        } else if (fn === 'hydraulic.micro_relief') {
            const lv = Level.fromDict(a.level);
            const r = HY.microRelief(R, lv, a.seed, a.amp_m, a.wavelength_m);
            finishCase(fn, c.label, [grade(fn, c.label, 'r', await readField(r), arr(c, 'r', 'outputs'), 1e-5)]);
            r.destroy();
        } else if (fn === 'hydraulic.finish') {
            const lv = Level.fromDict(a.level);
            const fields = new Fields(lv, null, R);
            fields.set('h', f32(arr(c, 'h_in')));
            for (const k of ['wear', 'deposit', 'talus']) if (c.inputs[`old_${k}`]) fields.set(k, f32(arr(c, `old_${k}`)));
            const inp = {};
            for (const k of ['bump', 'dH', 'dB', 'pw', 'ph', 'talus', 'wet']) if (c.inputs[k]) inp[k] = fieldOf(c, k);
            const res = HY.finish(fields, { hIn: fields.h, seed: inp.bump, seedK: a.seed_k, change: inp.dH, bed: inp.dB, bedMode: 0,
                pinW: inp.pw ?? null, pinH: inp.ph ?? null, talus: inp.talus, wet: inp.wet, level: lv, anchorM: a.anchor_m });
            res.apply();
            const oks = [];
            for (const k of Object.keys(c.outputs)) oks.push(grade(fn, c.label, k, await readField(fields[k]), arr(c, k, 'outputs'), 1e-5));
            for (const f of Object.values(inp)) f.destroy();
            fields.dispose();
            finishCase(fn, c.label, oks);
        } else if (fn === 'hydraulic.op_hydraulic') {
            await opCase(c, HY.opHydraulic, 1e-4, ['sqrt', 'divide']);
        } else if (fn === 'detail.breakup_terms') {
            const lv = Level.fromDict(a.level);
            const p = DT.paramsOf(DT.BREAKUP, a.params, 'breakup');
            const { terms, n, bed } = DT.breakupTerms(p, lv, a.seed);
            const u = DT.breakupUniforms(p, lv, n, bed);
            const wantT = arr(c, 'terms', 'outputs');
            const bits = D.bitsDiff(terms, f32(wantT));
            let urel = 0;
            for (const [k, v] of Object.entries(c.values.uniforms)) urel = Math.max(urel, Math.abs(u[k] - v) / Math.max(Math.abs(v), 1e-300));
            const ok = bits.n === 0 && n === c.values.n_terms && urel <= 1e-12 &&
                Object.keys(u).length === Object.keys(c.values.uniforms).length;
            rec(fn).rows.push({ label: c.label, ok, bits_differ: bits.n, uniforms_rel: urel, n });
            if (!ok) console.log(`  FAIL ${fn}: ${c.label}: ${bits.n} table values differ (first ${bits.first}), uniforms ${C.sci(urel)}`);
            finishCase(fn, c.label, [ok]);
        } else if (fn === 'detail.strength') {
            const lv = Level.fromDict(a.level);
            const p = DT.paramsOf(DT.BREAKUP, a.params, 'breakup');
            const h = fieldOf(c, 'h');
            const out = DT.strength(p, lv, h, a.seed);
            const got = await readField(out);
            const { n, bed } = DT.breakupTerms(p, lv, a.seed);
            const amax = (k) => arr(c, k, 'outputs').reduce((m, v) => Math.max(m, Math.abs(v)), 0);
            const allow = bedAllowance(DT.breakupUniforms(p, lv, n, bed), lv, amax('kfac'), amax('sc_abs'));
            const oks = ['R', 'kfac', 'sc_abs', 'D'].map((k, ch) =>
                grade(fn, c.label, k, D.channel(got, 4, ch), arr(c, k, 'outputs'), 1e-5, ['tan', 'exp', 'divide'], { abs: allow[k] }));
            finishCase(fn, c.label, oks);
            h.destroy();
            out.destroy();
        } else if (fn === 'detail.relax') {
            const b0c = fieldOf(c, 'b0'), bed = fieldOf(c, 'bed'), sc = fieldOf(c, 'sc');
            const b0 = R.pack({ b0c }, ['b0c', null, null, null]);
            const { state, accum } = DT.relax(b0, bed, sc, Math.tan(a.repose_deg * Math.PI / 180), a.iterations, a.rate,
                HY.BOUND_OPEN, a.floor);
            const [st, ta] = await R.readAll([state, accum]);
            const oks = [grade(fn, c.label, 'dl', D.channel(st, 4, 0), arr(c, 'dl', 'outputs'), 1e-4),
                grade(fn, c.label, 'bed_rel', D.channel(st, 4, 3), arr(c, 'bed_rel', 'outputs'), 1e-4),
                grade(fn, c.label, 'net', D.channel(ta, 4, 0), arr(c, 'net', 'outputs'), 1e-4)];
            finishCase(fn, c.label, oks);
            for (const f of [b0c, bed, sc, b0, state, accum]) f.destroy();
        } else if (fn === 'detail.op_breakup') {
            await opCase(c, DT.opBreakup, 1e-4, ['tan', 'atan', 'sqrt', 'exp', 'divide']);
        } else if (fn === 'detail.phacelle_noise') {
            const lv = Level.fromDict(a.level);
            // the octave row the gully kernel would use for this wavelength and lattice offset
            const lam0 = a.wavelength_m === 12.0 ? 12.0 : 12.0;
            const row = a.wavelength_m === 12.0 ? 0 : 1;
            const { table } = DT.gullyTable({ wavelength_m: lam0, amp_m: 1.0, octaves: 2, gain: 0.5 }, lv, 1);
            const oct = R.field(1, 4, 4, table);
            const dx = fieldOf(c, 'dx'), dy = fieldOf(c, 'dy');
            const o = R.field(lv.n, lv.n, 4);
            R.run(PHACELLE_PROBE, { dx, dy, oct }, { outP: o }, { uRow: row, uNorm: a.normalization });
            const got = await readField(o);
            const oks = ['c', 's', 'sdx', 'sdy'].map((k, ch) =>
                grade(fn, c.label, k, D.channel(got, 4, ch), arr(c, k, 'outputs'), 1e-5, ['exp', 'cos', 'sin', 'sqrt', 'divide']));
            finishCase(fn, c.label, oks);
            for (const f of [oct, dx, dy, o]) f.destroy();
        } else if (fn === 'detail.flow_direction') {
            const h = fieldOf(c, 'h');
            const flow = a.flow ? { x: fieldOf(c, 'flow_x'), y: fieldOf(c, 'flow_y') } : null;
            const { dx, dy } = DT.flowDirection(h, a.cell, a.smooth_m, flow);
            const oks = [grade(fn, c.label, 'dx', await readField(dx), arr(c, 'dx', 'outputs'), 1e-5, ['sqrt', 'divide']),
                grade(fn, c.label, 'dy', await readField(dy), arr(c, 'dy', 'outputs'), 1e-5, ['sqrt', 'divide'])];
            finishCase(fn, c.label, oks);
            for (const f of [h, dx, dy, ...(flow ? [flow.x, flow.y] : [])]) f.destroy();
        } else if (fn === 'detail.gully_relief') {
            const lv = Level.fromDict(a.level);
            const h = fieldOf(c, 'h');
            const flow = a.flow ? { x: fieldOf(c, 'flow_x'), y: fieldOf(c, 'flow_y') } : null;
            const p = DT.paramsOf(DT.GULLY, a.params, 'gully');
            const { g, mask, gm } = DT.gullyRelief(lv, h, p, a.seed, flow);
            const oks = [grade(fn, c.label, 'g', await readField(g), arr(c, 'g', 'outputs'), 1e-5, ['exp', 'cos', 'sin', 'sqrt', 'divide']),
                grade(fn, c.label, 'mask', await readField(mask), arr(c, 'mask', 'outputs'), 1e-5, ['sqrt', 'atan'])];
            finishCase(fn, c.label, oks);
            for (const f of [h, g, mask, gm, ...(flow ? [flow.x, flow.y] : [])]) f.destroy();
        } else if (fn === 'detail.op_gully') {
            await opCase(c, DT.opGully, 1e-5, ['exp', 'cos', 'sin', 'sqrt', 'atan', 'divide']);
        } else if (fn === 'detail.op_planation') {
            await opCase(c, DT.opPlanation, 1e-4, ['pow', 'divide']);
        } else if (fn.startsWith('model.')) {
            continue;                                     // tests/detail/conservation_test.mjs
        } else {
            T.ok(`${fn}: a case this test does not know`, false, c.label);
        }
    } catch (e) {
        console.log(`  FAIL ${fn}: ${c.label}: ${e.stack ?? e}`);
        rec(fn).failed.push(`${c.label}: ${e.message}`);
        rec(fn).cases++;
    }
}

for (const [fn, r] of Object.entries(results)) {
    T.ok(`${fn}: ${r.cases - r.failed.length} of ${r.cases} cases within their grade`, r.cases > 0 && !r.failed.length,
        `worst ${C.sci(r.worst)} of range` + (r.failed.length ? `; failed: ${r.failed.slice(0, 3).join(' | ')}` : ''));
}
T.extra.results = Object.fromEntries(Object.entries(results).map(([k, v]) => [k, { cases: v.cases, failed: v.failed,
    worst: v.worst, rows: v.rows }]));
T.extra.fixture = fx.manifest.key;
const code = D.finish(T, 'functions_test');
G.shutdown();
Deno.exit(code);
