// core/metrics.js against the Blender edition's core/metrics.py on reference DEMs (PORT_PLAN.md 8.2, P3): five
// real DEMs (an alpine valley, a stratovolcano, a caldera with its lake, star dunes, loess hills) and one field that
// is not square, each held as float32, with metrics.py's own numbers recorded by tests/parity/fixtures.py
// (--functions --only metrics, run by Blender's Python).
//
//     <Blender's python> -I eidoverse/terrain/tests/parity/fixtures.py --functions --only metrics
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/parity/metrics_test.mjs
//
// (on a shared machine put $EIDO_GPU_WRAP in front of the deno command). The grades, per number:
//   exact      relief, the height percentiles (relief_robust_m), the depression threshold, pixel and extent: the same
//              float32 values, order statistics and numpy 2.3.4's float64 arithmetic for the call form
//   float      means, the hypsometric integral, the slope percentiles and the anisotropy: max(1e-6 x the quantity's
//              range, 16 float32 steps of the value); the slopes are float32 here and float64 in numpy
//   counts     the slope fractions, the cliff pairs, the depressions: equal counts, give or take the cells that
//              metrics.py itself finds within 16 float32 steps of the limit (recorded per limit, usually none)
//   spectrum   every band's power within 1e-4 relative; the slopes of the fits within 1e-4; the knee and the peak
//              the same band
// Writes tests/out/parity/metrics_test.json.

import * as G from '../../core/gpu.js';
import * as M from '../../core/metrics.js';
import * as C from './_common.mjs';

const T = new C.Checks('parity/metrics');
const fx = C.loadFixture('functions/metrics');
if (!fx) Deno.exit(0);
T.extra.versions = fx.manifest.versions;
T.extra.blender_commit = fx.manifest.key?.commit ?? null;

const R = await G.init();
T.extra.adapter = R.info?.description ?? null;
const worst = {};
const note = (key, v) => { worst[key] = Math.max(worst[key] ?? 0, v); };

for (const c of fx.manifest.cases) {
    const name = c.label.replace('metrics ', '');
    const a = c.inputs.h, V = c.values, want = V.metrics, cell = V.cell;
    const h = R.field(a.shape[0], a.shape[1], 1, C.array(fx.dir, a));
    const n = a.shape[0] * a.shape[1];
    const t0 = performance.now();
    const got = await M.metrics(h, cell);
    const secs = (performance.now() - t0) / 1000;

    // exact
    const exact = ['pixel_m', 'relief_m', 'relief_robust_m', 'depression_threshold_m'];
    const bad = exact.filter((k) => got[k] !== want[k]);
    T.ok(`${name}: relief, the robust relief (height percentiles) and the depression threshold equal metrics.py's bit for bit`,
        !bad.length && got.extent_m[0] === want.extent_m[0] && got.extent_m[1] === want.extent_m[1],
        bad.map((k) => `${k} ${got[k]} vs ${want[k]}`).join('; ') || `relief ${got.relief_m} m, robust ${got.relief_robust_m} m`);

    // floats
    const relief = want.relief_m;
    const floats = [['mean_m', relief], ['hypsometric_integral', 1], ['slope_mean', 90], ['slope_p10', 90],
        ['slope_p50', 90], ['slope_p90', 90], ['slope_p99', 90], ['anisotropy_2', 1], ['anisotropy_4', 1],
        ['anisotropy_8', 1], ['anisotropy', 1]];
    const fails = [];
    let wr = 0;
    for (const [k, range] of floats) {
        const g = C.grade(got[k], want[k], { k: 1e-6, range, m: V.ulps });
        wr = Math.max(wr, g.err / range);
        note(`float ${k}`, g.err / range);
        if (!g.ok) fails.push(`${k}: ${got[k]} vs ${want[k]} (|d| ${C.sci(g.err)}, tolerance ${C.sci(g.tol)})`);
    }
    T.ok(`${name}: the mean, the hypsometric integral, the slope percentiles and mean, the anisotropy within max(1e-6 of range, ${V.ulps} float32 steps)`,
        !fails.length, fails.join('; ') || `worst ${C.sci(wr)} of its range`);

    // counts against a limit
    const cf = [];
    const counts = [['frac_slope_lt5', '5'], ['frac_slope_gt30', '30'], ['frac_slope_gt40', '40'], ['frac_slope_gt50', '50']];
    let flips = 0;
    for (const [k, lim] of counts) {
        const d = Math.round(Math.abs(got[k] - want[k]) * n), allow = V.slope_cells_within_rounding[lim];
        flips += d;
        if (d > allow) cf.push(`${k}: ${d} cells differ, ${allow} are within rounding of ${lim} degrees`);
    }
    const H = a.shape[0], Wd = a.shape[1], pairs = H * (Wd - 1) + (H - 1) * Wd + 2 * (H - 1) * (Wd - 1);
    const dp = Math.round(Math.abs(got.cliff_pair_frac - want.cliff_pair_frac) * pairs);
    if (dp > V.cliff_pairs.pairs_within_rounding_of_limit) cf.push(`cliff_pair_frac: ${dp} pairs differ, ${V.cliff_pairs.pairs_within_rounding_of_limit} within rounding`);
    const dc = Math.abs(got.depression_count - want.depression_count);
    if (dc > V.depressions.labels_within_rounding_of_threshold) cf.push(`depression_count ${got.depression_count} vs ${want.depression_count}`);
    const da = Math.round(Math.abs(got.depression_area_frac - want.depression_area_frac) * n);
    if (da > V.depressions.their_cells + V.depressions.depth_cells_within_rounding_of_1e_6) cf.push(`depression_area_frac: ${da} cells differ`);
    T.ok(`${name}: the slope fractions, the cliff pairs and the depressions (count ${want.depression_count}, area ${C.sci(want.depression_area_frac, 2)}) equal metrics.py's counts`,
        !cf.length, cf.join('; ') || `${flips} slope cells, ${dp} pairs, ${dc} depressions, ${da} depression cells differ`);

    // the spectrum
    const [wl, pw] = await M.radialSpectrum(h, cell);
    const wwl = C.array(fx.dir, c.outputs.spectrum_wavelength_m), wpw = C.array(fx.dir, c.outputs.spectrum_power);
    const extent = Math.min(H, Wd) * cell;
    let worstBand = 0, worstAll = 0, sameBands = wl.length === wwl.length, inBand = 0;
    for (let i = 0; i < Math.min(wl.length, wwl.length); i++) {
        if (Math.abs(wl[i] - wwl[i]) > 1e-9 * wwl[i]) sameBands = false;
        const e = Math.abs(pw[i] - wpw[i]) / wpw[i];
        worstAll = Math.max(worstAll, e);
        if (wwl[i] >= 4 * cell && wwl[i] <= extent / 4) { worstBand = Math.max(worstBand, e); inBand++; }
    }
    note('spectrum band power (relative, in the fitted wavelengths)', worstBand);
    T.ok(`${name}: radial_spectrum: the ${inBand} bands the summary reads within 1e-4 relative`, worstBand <= 1e-4,
        `worst ${C.sci(worstBand)} (all ${wwl.length} bands: ${C.sci(worstAll)}; the same bands: ${sameBands}, ${wl.length} here)`);
    const sk = ['spectrum_slope', 'spectrum_slope_long', 'spectrum_slope_short'];
    const sf = sk.filter((k) => !(Math.abs(got[k] - want[k]) <= 1e-4));
    const binEq = (x, y) => Math.abs(x - y) <= 1e-9 * Math.abs(y);
    const knee = binEq(got.spectrum_knee_m, want.spectrum_knee_m), peak = binEq(got.spectrum_peak_m, want.spectrum_peak_m);
    for (const k of sk) note(`${k} (absolute)`, Math.abs(got[k] - want[k]));
    T.ok(`${name}: the spectrum's summary: slopes within 1e-4, the knee (${want.spectrum_knee_m.toFixed(0)} m) and the peak (${want.spectrum_peak_m.toFixed(0)} m) in metrics.py's bands`,
        !sf.length && knee && peak,
        sf.map((k) => `${k} ${got[k]} vs ${want[k]}`).concat(knee ? [] : [`knee ${got.spectrum_knee_m} vs ${want.spectrum_knee_m}`],
            peak ? [] : [`peak ${got.spectrum_peak_m} vs ${want.spectrum_peak_m}`]).join('; ') ||
        `slope ${got.spectrum_slope.toFixed(5)} (|d| ${C.sci(Math.abs(got.spectrum_slope - want.spectrum_slope))})`);

    // slope_stats (the reference JSONs' keys) and every key present
    const ss = await M.slopeStats(h, cell);
    const sbad = Object.keys(V.slope_stats).filter((k) => {
        const range = k.startsWith('slope') ? 90 : (k === 'hypsometric_integral' ? 1 : relief);
        const exactKey = k === 'relief_m';
        return exactKey ? ss[k] !== V.slope_stats[k] : !C.grade(ss[k], V.slope_stats[k], { k: 1e-6, range, m: V.ulps }).ok;
    });
    const missing = Object.keys(want).filter((k) => !(k in got)), extra = Object.keys(got).filter((k) => !(k in want));
    T.ok(`${name}: slope_stats equal; metrics() has metrics.py's keys`, !sbad.length && !missing.length && !extra.length,
        [...sbad.map((k) => `${k} ${ss[k]} vs ${V.slope_stats[k]}`), ...missing.map((k) => `missing ${k}`), ...extra.map((k) => `extra ${k}`)].join('; ') ||
        `${Object.keys(want).length} keys; metrics() took ${secs.toFixed(2)} s at ${H} x ${Wd}`);
    h.destroy();
}
T.extra.worst = Object.fromEntries(Object.entries(worst).map(([k, v]) => [k, +v.toExponential(3)]));
const code = C.finish(T, 'metrics_test');
G.shutdown();
Deno.exit(code);
