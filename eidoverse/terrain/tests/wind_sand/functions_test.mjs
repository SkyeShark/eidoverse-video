// The numpy functions of solvers/aeolian.py that the port runs as GPU kernels, against the Blender edition's own on
// recorded inputs (PORT_PLAN.md 5.1 "function fixtures", 5.3), and the slab model's GPU loop against the numpy twin
// loop (TwinSim) for 40 iterations.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/wind_sand/functions_test.mjs
//
// (from the repository root; behind $EIDO_GPU_WRAP on a shared machine). Fixtures: tests/out/wind_sand/fixtures/
// (<Blender's python> -I eidoverse/terrain/tests/wind_sand/aeolian_expected.py). Grades (plan 5.3, the function float
// kind: f32 against numpy's float64; tests/parity/_common.mjs gradeArray):
//   start_fields, stretch_periodic, the steering, denoise, smooth_sheet, sample_periodic    within 1e-5 of range
//   the steering's least and most turn                       within 1e-5 rad (hop_box adds 1e-3 cells either way)
//   dune_height                                              bit-equal (numpy's float64 percentiles of the same
//                                                            float32 sand, from exact order statistics)
//   slip_fraction                                            within 1e-4 (a slope a float32 step either side of 27
//                                                            degrees moves one cell of 262,144)
//   spacing_peak                                             equal, or the next bin (64 log bins of the spectrum)
//   the twin loop                                            the sand within 1e-4 m of the twin's at every one of 40
//                                                            iterations (test_gpu.py's own bound), unturned and steered
// JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as A from '../../solvers/aeolian.js';
import { Level } from '../../core/levels.js';
import * as C from '../parity/_common.mjs';
import * as S from './_common.mjs';

const T = new S.Checks('wind and sand: the aeolian functions on the GPU against numpy, and the GPU loop against the twin');
const FX = `${S.OUT}/fixtures`;
const man = C.readJson(`${FX}/manifest.json`);
if (!man) {
    S.W.skip('the aeolian function cases', "make them with <Blender's python> -I eidoverse/terrain/tests/wind_sand/aeolian_expected.py");
    Deno.exit(0);
}
const R = await G.init();
const arr = (a) => C.array(FX, a);
const field = (a) => R.field(a.shape[0], a.shape[1], a.shape[2] ?? 1, Float32Array.from(arr(a)));
const level = (d) => Level.fromDict(d);
const grades = {};

function grade(name, label, got, want, k = 1e-5, extra = {}) {
    const g = C.gradeArray(got, want, { k, uses: ['arithmetic'], ...extra });
    (grades[name] ??= []).push({ label, ok: g.ok, over: g.over, err: g.err });
    return g;
}

function report(name, what) {
    const rows = grades[name] ?? [];
    const worst = rows.reduce((m, r) => Math.max(m, r.over), 0);
    const bad = rows.filter((r) => !r.ok);
    T.ok(`${name}: ${rows.length} cases ${what}`, rows.length > 0 && !bad.length,
        `worst ${S.sci(worst)} of range` + (bad.length ? `; over: ${bad.map((r) => `${r.label} ${S.sci(r.over)}`).join(', ')}` : ''));
}

const by = {};
for (const c of man.functions) (by[c.function] ??= []).push(c);

// ---- start_fields
for (const c of by.start_fields ?? []) {
    const { bed, sand } = await A.startFields(R, level(c.level), c.params, c.seed, c.period_m);
    const [b, s] = await R.readAll([bed, sand]);
    grade('start_fields', `${c.label} bed`, b, arr(c.outputs.bed));
    grade('start_fields', `${c.label} sand`, s, arr(c.outputs.sand));
    bed.destroy();
    sand.destroy();
}
report('start_fields', 'within 1e-5 of range (bed and sand; star stretched, unstretched, open and rotated, transverse)');

// ---- the steering
let worstTurn = 0;
for (const c of by.steering_for ?? []) {
    const st = A.steeringFor(R, level(c.level), c.params, c.seed, c.period_m);
    const n = await R.read(st.n);
    const want = arr(c.outputs.n);                       // (3, H, W) float64
    const hw = c.outputs.n.shape[1] * c.outputs.n.shape[2];
    for (let k = 0; k < 3; k++) {
        const got = new Float32Array(hw);
        for (let i = 0; i < hw; i++) got[i] = n[4 * i + k];
        grade('steering', `${c.label} n${k + 1}`, got, want.subarray(k * hw, (k + 1) * hw));
    }
    for (const [theta, turn] of Object.entries(c.turns)) {
        const { cs, turn: mine } = await st.forWind(Number(theta));
        grade('steering', `${c.label} wind ${theta} cos, sin`, await R.read(cs), arr(c.outputs[`cs_${theta}`]), 1e-5, { abs: C.trigAbs(2.0) });
        worstTurn = Math.max(worstTurn, Math.abs(mine[0] - turn[0]), Math.abs(mine[1] - turn[1]));
    }
    st.dispose();
}
report('steering', 'within 1e-5 of range (n1, n2, n3 and the wind fields of four directions)');
T.ok('steering: the least and the most turn of each wind within 1e-5 rad of numpy\'s', worstTurn <= 1e-5, `worst ${S.sci(worstTurn)} rad`);

// ---- stretch_periodic
for (const c of by.stretch_periodic ?? []) {
    const a = field(c.inputs.a);
    const out = await A.stretchPeriodic(a, c.cell, c.sigma_m, c.axis_deg);
    grade('stretch_periodic', c.label, await R.read(out), arr(c.outputs.out));
    a.destroy();
    out.destroy();
}
report('stretch_periodic', 'within 1e-5 of range (axes 90, 30, 155 on 512 x 512; 90 and 63 on a 240 x 200 tile)');

// ---- denoise and smooth_sheet
for (const c of by.denoise ?? []) {
    const sand = field(c.inputs.sand);
    const pw = c.inputs.pin_w ? field(c.inputs.pin_w) : null, ps = c.inputs.pin_sand ? field(c.inputs.pin_sand) : null;
    const out = A.denoise(sand, c.sigma, { periodic: c.periodic, pinW: pw, pinSand: ps });
    grade('denoise', c.label, await R.read(out), arr(c.outputs.out));
    for (const f of [sand, pw, ps, out]) f?.destroy();
}
report('denoise', 'within 1e-5 of range (periodic, mirrored with the border band\'s pins, sigma 0 to 2)');
for (const c of by.smooth_sheet ?? []) {
    const sand = field(c.inputs.sand);
    const pw = c.inputs.pin_w ? field(c.inputs.pin_w) : null, ps = c.inputs.pin_sand ? field(c.inputs.pin_sand) : null;
    const out = A.smoothSheet(sand, c.params, { periodic: c.periodic, pinW: pw, pinSand: ps });
    grade('smooth_sheet', c.label, await R.read(out), arr(c.outputs.out));
    for (const f of [sand, pw, ps, out]) f?.destroy();
}
report('smooth_sheet', 'within 1e-5 of range (star, star with sheet_top_m, transverse: periodic and pinned)');

// ---- sample_periodic
for (const c of by.sample_periodic ?? []) {
    const a = field(c.inputs.a);
    const out = A.samplePeriodic(a, level(c.src), level(c.level));
    grade('sample_periodic', c.label, await R.read(out), arr(c.outputs.out));
    a.destroy();
    out.destroy();
}
report('sample_periodic', 'within 1e-5 of range (the dunes run\'s tile averaged to its two context levels, 2 x 2 and 4 x 4 cells)');

// ---- the measures
for (const c of by.measures ?? []) {
    const h = field(c.inputs.h), sand = field(c.inputs.sand);
    const sp = await A.spacingPeak(h, c.cell), dh = await A.duneHeight(sand), sf = await A.slipFraction(h, c.cell, 31.0);
    const want = c.result;
    const bins = Math.abs(Math.log(sp / want.spacing_peak)) / Math.log(Math.pow(0.5 * Math.max(h.h, h.w), 1 / 64));
    T.ok(`dune_height (${c.label}): numpy's float64 percentiles, bit for bit`, dh === want.dune_height, `${dh} vs ${want.dune_height} m`);
    T.ok(`slip_fraction (${c.label}): within 1e-4`, Math.abs(sf - want.slip_fraction) <= 1e-4, `${sf} vs ${want.slip_fraction}`);
    T.ok(`spacing_peak (${c.label}): the same bin of the spectrum, or the next`, bins <= 1.0 + 1e-6,
        `${sp.toFixed(2)} vs ${want.spacing_peak.toFixed(2)} m (${bins.toFixed(2)} bins apart)`);
    h.destroy();
    sand.destroy();
}

// ---- the GPU loop against the twin loop
for (const c of by.twin_loop ?? []) {
    const bed = field(c.inputs.bed), sand = field(c.inputs.sand);
    let steer = null;
    if (c.inputs.n) {
        const n = arr(c.inputs.n), [k, h, w] = c.inputs.n.shape;
        const pack = new Float32Array(h * w * 4);
        for (let i = 0; i < h * w; i++) for (let q = 0; q < k; q++) pack[4 * i + q] = n[q * h * w + i];
        steer = new A.Steering(R.field(h, w, 4, pack), c.steer_deg, c.turn_deg);
    }
    const sim = new A.SandSim(bed, sand, c.cell, { bound: c.bound, params: c.params, seed: c.seed, steer });
    const want = arr(c.outputs.sand), hw = bed.h * bed.w;
    let worst = 0, first = null;
    for (let it = 0; it < c.steps.length; it++) {
        const [d, w] = c.steps[it];
        await sim.step(d, w);
        const [, s] = await sim.read();
        let e = 0;
        for (let i = 0; i < hw; i++) e = Math.max(e, Math.abs(s[i] - want[it * hw + i]));
        worst = Math.max(worst, e);
        if (e > 0 && first === null) first = it;
    }
    T.ok(`the GPU loop and the twin loop (${c.label}) agree for ${c.steps.length} iterations: the sand within 1e-4 m`,
        c.steps.length === 40 && worst <= 1e-4, `max |gpu - twin| ${S.sci(worst)} m; first iteration that differs: ${first}`);
    sim.dispose();
    steer?.dispose();
    bed.destroy();
    sand.destroy();
}

G.shutdown();
Deno.exit(S.finish(T, 'functions_test', { fixture_versions: man.versions, grades }));
