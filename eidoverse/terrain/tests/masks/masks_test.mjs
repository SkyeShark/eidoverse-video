// The masks package's acceptance (PORT_PLAN.md 8.2 row P7): masks.js and kernels/masks/ against the Blender
// edition's masks.py, on the cases tests/masks/masks_expected.py made with Blender's own Python.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/masks/masks_test.mjs
//         [--only api,shifts,synthetic,refs,hero,scale,slope_json,floor] [--refs lauterbrunnen,...] [--runs a,b]
//         [--fixtures <dir>]                    (on a shared machine, behind $EIDO_GPU_WRAP)
//
// The grades (plan 5.3, the masks' function grade: within 1e-4 of each mask's range, on masks.py's own floor):
//   f64      every mask within max(1e-4 of its range, 1.25 x its one-step floor) of masks.py run with its Gaussian
//            blur's FFT in float64 (the port's blur is a direct convolution: core/prims.js); aspect compared round
//            the circle. The one-step floor (masks_expected.py ulp_floor) is masks.py's own precision, measured per
//            case, level and mask: the largest change of the mask when each blurred field it keeps in float32 moves
//            by one float32 step on a random half of its cells (three patterns). It is 0 for every mask that does not
//            read a blur, so those are held to 1e-4 of their range; the curvature masks and what reads them stand on
//            it (one step of the blur moves convex and concave by about 1e-3 of their range)
//   as is    every mask within max(1e-4 of its range, 1.25 x (the spread masks.py's own float32 FFT gives it + the
//            one-step floor)) of masks.py as it is (the spread: |as is - float64 FFT|, per case, level and mask)
//   floor    the masks of every base save of the chaos floor's runs (Blender's Terrain.save) made again by the port
//            from the save's fields with the run's mask parameters: within the as-is grade plus the save's own
//            rounding (one float16 step for the bounded masks, as api.py caches them)
// and test_masks.py's own checks on the port's masks, with its bars: the curvatures' formulas, the scale pick, the
// curvature on the references, the sky view's analytic cases and the far field, the wetness, scale independence on
// 2 x resampled fields, no frame at a stacked border, every mask meeting its parent at the seams of a hero stack, a
// periodic tile's roll, the api; and slope equal to the references' JSON (all of them, with their contexts).
// JavaScript per cell here is test code (the edition's rule allows it in tests only). Writes
// tests/out/masks/masks_test.json.

import * as G from '../../core/gpu.js';
import * as Gd from '../../core/grid.js';
import * as Io from '../../core/io.js';
import { prims } from '../../core/prims.js';
import * as M from '../../masks.js';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const arg = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : null;
};
const ONLY = arg('--only') ? new Set(arg('--only').split(',')) : null;
const want = (s) => !ONLY || ONLY.has(s);
const FIX = arg('--fixtures') ?? `${W.TESTS}/out/masks/fixtures`;
const REFS = arg('--refs') ? new Set(arg('--refs').split(',')) : null;
const RUNS = arg('--runs') ? new Set(arg('--runs').split(',')) : null;
const SHEETS = args.includes('--sheets');           // refs: write the main tiles' masks for tests/masks/sheets_port.py

const T = new C.Checks('masks: masks.js against masks.py');
const R = await G.init();
const P1 = prims(R);
const results = { grades: {}, checks: {}, seconds: {} };
const t00 = performance.now();

let manifest = null;
try {
    manifest = JSON.parse(Deno.readTextFileSync(`${FIX}/manifest.json`));
} catch (_e) {
    console.log(`[skip] no masks fixtures at ${FIX}: make them with <Blender's python> -I ` +
        'eidoverse/terrain/tests/masks/masks_expected.py (Blender\'s python: tests/_where.mjs blenderPython())');
}
const cases = new Map((manifest?.cases ?? []).map((c) => [c.name, c]));


// ------------------------------------------------------------------------------------------------- helpers ---

const f32 = (a) => (a instanceof Float32Array ? a : Float32Array.from(a));
const up = (a, ny, nx) => R.field(ny, nx, 1, f32(a));

async function load(meta, names = null) {
    const raw = await Io.readNpz(`${FIX}/${meta.file}`, names ? { names } : {});
    const out = {};
    for (const [k, v] of Object.entries(raw)) out[k] = v.data instanceof Float32Array ? v.data : Float32Array.from(v.data);
    return out;
}

function rangeOf(a) {
    let lo = Infinity, hi = -Infinity, amax = 0;
    for (let i = 0; i < a.length; i++) {
        const v = a[i];
        if (!Number.isFinite(v)) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
        if (Math.abs(v) > amax) amax = Math.abs(v);
    }
    return { lo, hi, range: hi >= lo ? hi - lo : 0, amax };
}

/** got against want: { err, span, over (err / span), at, bad (cells over tol), tol, ok }. circ: angles in degrees
 * compared round the circle. extra(i): a per-cell allowance added to tol (a save's own rounding). */
function grade(got, want, tol, opts = {}) {
    const { range, amax } = rangeOf(want);
    const span = Math.max(range, 1e-6 * amax, 1e-20);
    let err = 0, at = -1, bad = 0, nonFinite = 0;
    for (let i = 0; i < want.length; i++) {
        const w = want[i], g = got[i];
        if (!Number.isFinite(g) || !Number.isFinite(w)) {
            if (!(Number.isNaN(g) && Number.isNaN(w)) && g !== w) nonFinite++;
            continue;
        }
        let e = Math.abs(g - w);
        if (opts.circ) e = Math.min(e % 360, 360 - (e % 360));
        const t = tol + (opts.extra ? opts.extra(i) : 0);
        if (e > t) bad++;
        if (e > err) { err = e; at = i; }
    }
    return { err, span, over: err / span, at, bad, tol, ok: bad === 0 && nonFinite === 0, nonFinite };
}

const r3 = (x) => (typeof x === 'number' ? Number(x.toPrecision(3)) : x);

/** Grade one level's masks: got {name: Float32Array}, the fixture arrays under `prefix` (L<i>), the case's spread
 * and one-step floor for the level. Returns a row per mask and records the worst. */
function gradeLevel(label, got, arrays, prefix, spread, ulp, opts = {}) {
    const rows = {};
    let ok = true, worstF64 = 0, worstAsIs = 0;
    const names = Object.keys(arrays).filter((k) => k.startsWith(`${prefix}__out__`)).map((k) => k.slice(prefix.length + 7));
    for (const nm of names) {
        const g = got[nm];
        if (!g) {
            rows[nm] = { missing: true };
            ok = false;
            continue;
        }
        const asis = arrays[`${prefix}__out__${nm}`];
        const f64 = arrays[`${prefix}__f64__${nm}`] ?? asis;
        const circ = nm === 'aspect';
        const span = Math.max(rangeOf(f64).range, 1e-6 * rangeOf(f64).amax, 1e-20);
        const sp = spread?.[nm] ?? 0, fl = ulp?.[nm] ?? 0;
        const a = grade(g, f64, Math.max(1e-4 * span, 1.25 * fl), { circ });
        const b = grade(g, asis, Math.max(1e-4 * span, 1.25 * (sp + fl)), { circ });
        rows[nm] = { f64: r3(a.over), f64_bad: a.bad, as_is: r3(b.over), as_is_bad: b.bad, spread: r3(sp / span),
            floor: r3(fl / span) };
        if (!a.ok || !b.ok) {
            ok = false;
            rows[nm].fail = true;
            rows[nm].at = a.at;
        }
        worstF64 = Math.max(worstF64, a.over);
        worstAsIs = Math.max(worstAsIs, b.over);
    }
    const extra = Object.keys(got).filter((k) => !names.includes(k));
    if (extra.length && !opts.extraOk) {
        ok = false;
        rows['<extra>'] = extra;
    }
    results.grades[label] = rows;
    const fails = Object.entries(rows).filter(([, r]) => r.fail || r.missing).map(([k, r]) => `${k} ${r.missing ? 'missing' : `${r.f64}/${r.as_is} (bad ${r.f64_bad}/${r.as_is_bad}; floor ${r.floor})`}`);
    const exact = Object.values(rows).filter((r) => r.floor === 0).length;
    T.ok(`${label}: ${names.length} masks within their grades of masks.py (${exact} held to 1e-4 of range, the rest to their one-step floor)`, ok,
        `worst ${r3(worstF64)} of range (f64), ${r3(worstAsIs)} (as is)` + (fails.length ? `; FAIL ${fails.join(', ')}` : ''));
    return ok;
}

function sel(a, mask) {
    const out = [];
    for (let i = 0; i < a.length; i++) if (mask[i]) out.push(a[i]);
    return out;
}
const mean = (a) => a.reduce((s, v) => s + v, 0) / Math.max(a.length, 1);
function percentile(a, q) {                                  // numpy's linear method, float64 (test code)
    const s = Float64Array.from(a).sort();
    const v = (s.length - 1) * q / 100, lo = Math.floor(v), hi = Math.min(lo + 1, s.length - 1);
    return s[lo] + (s[hi] - s[lo]) * (v - lo);
}

async function hostMasks(m) {
    await m.toHost();
    return Object.fromEntries(Object.entries(m));
}

function paramsOf(d) {
    return new M.MaskParams(d ?? {});
}

function fieldsOf(arrays, prefix, ny, nx, made) {
    const f = {};
    for (const [k, v] of Object.entries(arrays)) {
        if (!k.startsWith(`${prefix}__in__`)) continue;
        const nm = k.slice(prefix.length + 6);
        f[nm] = up(v, ny, nx);
        made.push(f[nm]);
    }
    return f;
}


// ------------------------------------------------------------------------------------------------------ api ---

if (manifest && want('api')) {
    const A = manifest.api;
    T.eq('MASKS equal masks.py MASKS (units and meanings)', Object.fromEntries(Object.entries(M.MASKS).map(([k, v]) => [k, [...v]])), A.MASKS);
    T.eq('DEFAULT_NAMES, SCALED and PASS_THROUGH equal', [M.DEFAULT_NAMES, M.SCALED, M.PASS_THROUGH], [A.DEFAULT_NAMES, A.SCALED, A.PASS_THROUGH]);
    T.eq('MaskParams() equals MaskParams().to_dict()', new M.MaskParams().toDict(), A.params);
    T.ok('describeMasks() equals describe_masks()', M.describeMasks() === A.describe);
    T.ok("attributeName('slope') is eido_slope", M.attributeName('slope') === A.attribute_name);
    let worst = 0;
    for (const [c, v] of Object.entries(A.channel_area)) worst = Math.max(worst, Math.abs(M.channelAreaForCell(Number(c)) - v) / v);
    T.ok('channelAreaForCell equals channel_area_for_cell (1e-12 relative)', worst <= 1e-12, `worst ${worst}`);
    T.eq('scaleSuffix equals scale_suffix', Object.fromEntries(Object.keys(A.scale_suffix).map((s) => [s, M.scaleSuffix(Number(s))])), A.scale_suffix);
    const pn = {};
    for (const n of Object.keys(A.parse_name)) {
        try {
            pn[n] = { value: M.parseName(n) };
        } catch (e) {
            pn[n] = { error: e.name, message: `"${e.message}"` };
        }
    }
    const pyKeyMsg = (r) => (r.error ? { error: r.error, message: r.message.startsWith("'") ? `"${r.message.slice(1, -1)}"` : r.message } : r);
    T.eq('parseName equals parse_name (values; KeyError naming the nearest)', pn, Object.fromEntries(Object.entries(A.parse_name).map(([k, r]) => [k, pyKeyMsg(r)])));
    T.eq('goodSize equals _good_size', Object.fromEntries(Object.keys(A.good_size).map((n) => [n, M.goodSize(Number(n))])), A.good_size);
    T.eq('the decimation factors equal _decimation', A.decimation.map(([s, n, w]) => M._internal.decimation(s, n, w)), A.decimation.map((r) => r[3]));
    T.eq('smoothstep equals masks.py smoothstep (float32, bit for bit)', A.smoothstep.map(([a, b, x]) => M.smoothstep(a, b, x)), A.smoothstep.map((r) => r[3]));
    T.throws('MaskParams refuses an unknown field, naming the nearest', () => new M.MaskParams({ snowline: 1 }), 'snowline_m');
    const P = new M.MaskParams({ strata: { dip_deg: 1, warp: () => 0 } });
    T.ok('MaskParams.toDict() writes a callable warp as <callable>', P.toDict().strata.warp === '<callable>');
}


// ---------------------------------------------------------------------------------------------- march shifts ---

if (manifest && want('shifts')) {
    let n = 0, bad = 0, first = null;
    for (const c of manifest.cases) {
        for (const mr of c.marches ?? []) {
            n++;
            const got = M.marchShifts(mr.dists, mr.cell, mr.m, mr.directions).map(([k, di, dj]) => [k, di, dj]);
            if (JSON.stringify(got) !== JSON.stringify(mr.shifts)) {
                bad++;
                first = first ?? `${c.name}: m ${mr.m} cell ${mr.cell}`;
            }
        }
    }
    T.ok(`the march shifts equal _march's on every recorded march (${n})`, n > 0 && bad === 0, bad ? `${bad} differ, first ${first}` : '');
}


// ------------------------------------------------------------------------------------------- the synthetic ---

// the strata warps of the cases whose masks.py params hold a callable (to_dict writes '<callable>'): the same function
// over GPU fields of the cells' world x and y (masks.js's form of masks.py's callable(x, y) over numpy arrays)
const WARPS = { api_strata_warp: (X) => Gd.arith(R, 'affine', X, null, { amp: 0.001, off: 3.0 }) };

async function computeCase(meta) {
    const arrays = await load(meta);
    const lv = meta.levels[0];
    const made = [];
    const fields = fieldsOf(arrays, 'L0', lv.ny, lv.nx, made);
    const params = { ...meta.params };
    if (params.strata?.warp === '<callable>') params.strata = { ...params.strata, warp: WARPS[meta.name] };
    const o = { cell: lv.cell, x0: lv.x0, y0: lv.y0, params: paramsOf(params) };
    if (meta.names) o.names = meta.names;
    if (meta.norms_given) o.norms = new M.Norms(meta.norms_given);
    const m = await M.compute(fields, o);
    const skipped = { ...m.skipped };
    const got = await hostMasks(m);
    for (const f of made) f.destroy();
    return { arrays, got, skipped, lv };
}

if (manifest && want('synthetic')) {
    const ts = performance.now();
    // pad_level + curvatures of a dome and a ridge
    for (const name of ['curv_dome', 'curv_ridge']) {
        const meta = cases.get(name);
        const a = await load(meta);
        const n = 96;
        const h = up(a.in__h, n, n);
        const hp = M.padLevel(h, 1, meta.cell);
        const { prof, plan } = M.curvatures(hp, meta.cell);
        const [hpg, kp, kt] = await R.readAll([hp, prof, plan]);
        for (const f of [h, hp, prof, plan]) f.destroy();
        // the edge cells (2 a0 - a1: one rounding) bit for bit; the four corners (an odd extrapolation of one) within
        // one float32 step of numpy's float64 value rounded once
        let padBits = 0, cornerUlps = 0;
        const wp = n + 2;
        for (let k = 0; k < hpg.length; k++) {
            const j = Math.floor(k / wp), i = k % wp;
            const corner = (j === 0 || j === wp - 1) && (i === 0 || i === wp - 1);
            const d = Math.abs(hpg[k] - a.out__hp[k]);
            if (corner) cornerUlps = Math.max(cornerUlps, d / C.ulp32(a.out__hp[k]));
            else if (hpg[k] !== a.out__hp[k]) padBits++;
        }
        T.ok(`${name}: pad_level's odd margin equals numpy's float64 value rounded once (bit for bit; the corners within one step)`,
            padBits === 0 && cornerUlps <= 1, `${padBits} edge cells differ; corners ${cornerUlps} steps`);
        const gp = grade(kp, a.out__prof, 1e-4 * rangeOf(a.out__prof).range), gt = grade(kt, a.out__plan, 1e-4 * rangeOf(a.out__plan).range);
        T.ok(`${name}: curvatures within 1e-4 of range of masks.py`, gp.ok && gt.ok, `profile ${r3(gp.over)}, plan ${r3(gt.over)} of range`);
        // test_curvature_curvatures_exact on the port's own numbers
        const aa = 0.004, w = n + 2;
        let eP = 0, eT = 0, eRp = 0, eRt = 0;
        for (let j = 1; j < n + 1; j++) {
            for (let i = 1; i < n + 1; i++) {
                const k = j * w + i;
                if (name === 'curv_dome') {
                    if (j - 1 >= 4 && j - 1 < n - 4 && i - 1 >= 4 && i - 1 < n - 4) {
                        eP = Math.max(eP, Math.abs(kp[k] - 2 * aa));
                        eT = Math.max(eT, Math.abs(kt[k] - 2 * aa));
                    }
                } else {
                    const X = (i - 1 + 0.5 - n / 2) * 2.0;
                    if (Math.abs(X) < 6.0) {
                        eRt = Math.max(eRt, Math.abs(kt[k] - 2 * aa));
                        eRp = Math.max(eRp, Math.abs(kp[k]));
                    }
                }
            }
        }
        if (name === 'curv_dome') T.ok('test_curvature_curvatures_exact: the dome +2a within 1e-5 (port)', Math.max(eP, eT) < 1e-5, `err ${r3(Math.max(eP, eT))}`);
        else T.ok('test_curvature_curvatures_exact: the ridge plan +2a and profile 0 within 2e-4 (port)', eRt < 2e-4 && eRp < 2e-4, `plan ${r3(eRt)}, profile ${r3(eRp)}`);
    }
    // the compute cases
    for (const name of ['v_valley_20', 'v_valley_200', 'scale_pick', 'wetness_mono', 'periodic', 'api_defaults', 'api_strata',
        'api_strata_warp']) {
        const meta = cases.get(name);
        if (!meta) continue;
        const { arrays, got, skipped, lv } = await computeCase(meta);
        gradeLevel(name, got, arrays, 'L0', meta.fft_spread?.L0, meta.ulp_floor?.L0);
        T.eq(`${name}: skipped equals masks.py's`, skipped, meta.masks[0].skipped);
        const n = lv.ny, nx = lv.nx;
        if (name.startsWith('v_valley')) {
            const sigma = Number(name.split('_')[2]);
            const s = M.scaleSuffix(sigma);
            const k = (j, i) => got[`curv_plan_${s}`][j * nx + i] + got[`curv_profile_${s}`][j * nx + i];
            const bend = -((k(n / 2, n / 2 - 1) + k(n / 2, n / 2)) / 2) * sigma;
            const formula = 2.0 * Math.tan(30 * Math.PI / 180) / Math.sqrt(2.0 * Math.PI);
            T.ok(`test_curvature_curvatures_exact: the V-valley's bend at ${sigma} m is 0.8 tan 30 within 0.03 (port)`,
                Math.abs(bend - formula) < 0.03, `${r3(bend)} vs ${r3(formula)}`);
        }
        if (name === 'scale_pick') {
            const cell = 4.0, X = (i) => (i + 0.5 - 400) * cell, Y = X;
            const c20 = got.concave_20m, c200 = got.concave_200m, v200 = got.convex_200m;
            const r = { concave20_in_gullies: [], concave20_on_gully_crests: [], concave200_in_valleys: [], concave200_on_ridges: [],
                convex200_on_ridges: [], c200_gully: [], c200_crest: [] };
            for (let j = 60; j < 740; j++) {
                for (let i = 60; i < 740; i++) {
                    const g = Math.cos(2 * Math.PI * (X(i) + 0.6 * Y(j)) / 160.0), v = Math.cos(2 * Math.PI * X(i) / 1600.0);
                    const q = j * 800 + i;
                    if (g < -0.7) { r.concave20_in_gullies.push(c20[q]); r.c200_gully.push(c200[q]); }
                    if (g > 0.7) { r.concave20_on_gully_crests.push(c20[q]); r.c200_crest.push(c200[q]); }
                    if (v < -0.9) r.concave200_in_valleys.push(c200[q]);
                    if (v > 0.9) { r.concave200_on_ridges.push(c200[q]); r.convex200_on_ridges.push(v200[q]); }
                }
            }
            const m = Object.fromEntries(Object.entries(r).map(([k, v]) => [k, mean(v)]));
            results.checks.scale_pick = m;
            T.ok('test_curvature_picks_its_scale: concave_20m finds the gullies, concave_200m the valleys (port)',
                m.concave20_in_gullies > 0.6 && m.concave20_on_gully_crests < 0.05 && m.concave200_in_valleys > 0.6 &&
                m.concave200_on_ridges < 0.05 && m.convex200_on_ridges > 0.6 && Math.abs(m.c200_gully - m.c200_crest) < 0.05,
                Object.entries(m).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(', '));
        }
        if (name === 'wetness_mono') {
            const row = got.wetness.subarray(32 * 64, 33 * 64);
            let mono = true;
            for (let i = 1; i < 64; i++) if (row[i] - row[i - 1] < -1e-6) mono = false;
            T.ok('test_wetness_sane: wetness rises with the area at a fixed slope (port)', mono);
        }
        if (name === 'api_defaults') {
            T.ok('test_api: absent inputs skipped and said why (flow, wear), slope made', 'flow' in skipped && 'wear' in skipped && 'slope' in got);
            T.ok('test_api: every mask a Float32Array of the level', Object.values(got).every((v) => v instanceof Float32Array && v.length === n * nx));
        }
        if (name === 'api_strata') {
            let worst = 0;
            for (let j = 0; j < n; j++) {
                for (let i = 0; i < nx; i++) {
                    const h = arrays.L0__in__h[j * nx + i];
                    const zs = h - Math.tan(Math.PI / 180) * (-50.0 + (j + 0.5) * 4.0);
                    worst = Math.max(worst, Math.abs(got.strata[j * nx + i] - zs));
                }
            }
            T.ok('test_api: strata from params.strata equals the design formula within 1e-3 m (port)', worst < 1e-3, `worst ${r3(worst)} m`);
        }
        if (name === 'periodic') {
            const made = [];
            const fr = fieldsOf({ R0__in__h: rollArr(arrays.L0__in__h, n, nx, meta.roll) }, 'R0', n, nx, made);
            const m0 = await M.compute(fieldsOf(arrays, 'L0', n, nx, made), { cell: lv.cell, names: meta.names, params: paramsOf(meta.params) });
            const norms = m0.norms;
            m0.dispose();
            const m1 = await M.compute(fr, { cell: lv.cell, names: meta.names, params: paramsOf(meta.params), norms });
            const gotR = await hostMasks(m1);
            for (const f of made) f.destroy();
            gradeLevel('periodic (rolled)', gotR, arrays, 'R0', meta.fft_spread?.L0, meta.ulp_floor?.R0);
            let worst = 0;
            for (const nm of meta.names) {
                const a = rollArr(got[nm], n, nx, meta.roll), b = gotR[nm];
                for (let i = 0; i < a.length; i++) worst = Math.max(worst, Math.abs(a[i] - b[i]));
            }
            T.ok('test_periodic_tile: every mask moves with a roll of the field, within 1e-3 (port)', worst < 1e-3, `worst ${r3(worst)}`);
        }
    }
    // the sky view's analytic cases
    for (const name of ['sky_flat', 'sky_v', 'sky_plane']) {
        const meta = cases.get(name);
        const a = await load(meta);
        const h = up(a.in__h, 200, 200);
        const o = M.skyView(h, meta.cell, meta.radius);
        const got = await R.read(o);
        h.destroy();
        o.destroy();
        const g = grade(got, a.out__sky, 1e-4 * Math.max(rangeOf(a.out__sky).range, 1e-6));
        T.ok(`${name}: sky_view within 1e-4 of masks.py`, g.ok, `err ${r3(g.err)}`);
        const az = Array.from({ length: 3600 }, (_, k) => (2 * Math.PI * k) / 3600);
        if (name === 'sky_flat') T.ok('test_occlusion_sane: a plane is open sky (port)', rangeOf(got).lo > 0.999, `min ${rangeOf(got).lo}`);
        if (name === 'sky_v') {
            const th = Math.PI / 6;
            const floor = (got[99 * 200 + 100] + got[100 * 200 + 100]) / 2;
            const wantV = 1 - mean(az.map((x) => Math.sin(Math.atan(Math.tan(th) * Math.abs(Math.cos(x))))));
            T.ok("test_occlusion_sane: a V-valley's floor matches its analytic sky view within 0.01 (port)", Math.abs(floor - wantV) < 0.01,
                `${floor.toFixed(4)} vs ${wantV.toFixed(4)}`);
        }
        if (name === 'sky_plane') {
            const b = Math.atan(Math.hypot(0.2, 0.1));
            const wantP = 1 - mean(az.map((x) => Math.sin(Math.max(0, Math.atan(Math.tan(b) * Math.cos(x))))));
            const mid = [];
            for (let j = 60; j < 140; j++) for (let i = 60; i < 140; i++) mid.push(got[j * 200 + i]);
            T.ok("test_occlusion_sane: a tilted plane's sky view matches its analytic one within 0.01 (port)",
                Math.abs(mean(mid) - wantP) < 0.01, `${mean(mid).toFixed(4)} vs ${wantP.toFixed(4)}`);
        }
    }
    results.seconds.synthetic = Math.round(performance.now() - ts) / 1000;
}

function rollArr(a, ny, nx, [dy, dx]) {
    const out = new Float32Array(a.length);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) out[((j + dy) % ny) * nx + ((i + dx) % nx)] = a[j * nx + i];
    return out;
}


// --------------------------------------------------------------------------------------------- the stacks ---

/** computeStack on a stack case: { arrays, got: [{name: Float32Array}], masks: [Masks] }. */
async function stackCase(meta, names = meta.names) {
    const arrays = await load(meta);
    const made = [];
    const fields = meta.levels.map((lv, i) => fieldsOf(arrays, `L${i}`, lv.ny, lv.nx, made));
    const t0 = performance.now();
    const ms = await M.computeStack(fields, meta.levels, { names: names ?? null, params: paramsOf(meta.params),
        strict: meta.strict ?? null });
    const secs = (performance.now() - t0) / 1000;
    for (const f of made) f.destroy();
    return { arrays, got: ms.map((m) => Object.fromEntries(Object.entries(m))), masks: ms, secs, fields: null };
}

// fixtures.py _valley_ridge_cells: valley floors (A >= 0.1 km^2) and divides (A <= 1.5 cell^2)
function valleyRidge(A, cell) {
    const valley = new Uint8Array(A.length), divide = new Uint8Array(A.length);
    for (let i = 0; i < A.length; i++) {
        valley[i] = A[i] >= 1.0e5 ? 1 : 0;
        divide[i] = A[i] <= 1.5 * cell * cell ? 1 : 0;
    }
    return { valley, divide };
}

if (manifest && want('refs')) {
    const ts = performance.now();
    const rows = {};
    for (const meta of manifest.cases.filter((c) => c.name.startsWith('ref_'))) {
        const name = meta.reference;
        if (REFS && !REFS.has(name)) continue;
        const { arrays, got, masks, secs } = await stackCase(meta);
        results.seconds[`stack ${name}`] = Math.round(secs * 100) / 100;
        for (let i = 0; i < got.length; i++) gradeLevel(`${name} L${i}`, got[i], arrays, `L${i}`, meta.fft_spread?.[`L${i}`], meta.ulp_floor?.[`L${i}`]);
        for (let i = 0; i < got.length; i++) T.eq(`${name} L${i}: skipped equals masks.py's`, { ...masks[i].skipped }, meta.masks[i].skipped);
        const lv = meta.levels[1], n = lv.ny * lv.nx;
        const m = got[1];
        if (SHEETS) {                       // the main tile's masks for tests/masks/sheets_port.py (float32, as made)
            const dir = W.out('masks/sheets');
            await Io.writeNpz(`${dir}/${name}_port_masks.npz`,
                Object.entries(m).map(([k, v]) => [k, () => Io.npArray(v, [lv.ny, lv.nx])]));
            Deno.writeTextFileSync(`${dir}/${name}_port_masks.json`, JSON.stringify({ reference: name, level: lv,
                skipped: { ...masks[1].skipped }, seconds: results.seconds[`stack ${name}`] }, null, 1));
        }
        const { valley, divide } = valleyRidge(arrays.L1__in__A, lv.cell);
        // test_curvature_on_references
        const row = {};
        for (const s of ['20m', '200m']) {
            const cc = m[`concave_${s}`], cv = m[`convex_${s}`];
            const r = { concave_valley: mean(sel(cc, valley)), concave_all: mean(cc), convex_divide: mean(sel(cv, divide)),
                convex_all: mean(cv), concave_divide: mean(sel(cc, divide)), convex_valley: mean(sel(cv, valley)) };
            r.signed_gap = (r.concave_valley - r.convex_valley) - (r.concave_divide - r.convex_divide);
            r.no_content = r.concave_all < 0.02 && r.convex_all < 0.02;
            row[s] = r;
        }
        const curvOk = Object.values(row).every((r) => r.no_content || r.signed_gap > 0.2);
        T.ok(`test_curvature_on_references ${name}: concave - convex separates valleys and divides by > 0.2 (port)`, curvOk,
            Object.entries(row).map(([s, r]) => `${s} ${r.no_content ? 'no content' : r.signed_gap.toFixed(3)}`).join(', '));
        // test_occlusion_sane (references): valleys darker than divides; the far field against a full march
        const o = m.occlusion;
        const ov = mean(sel(o, valley)), od = mean(sel(o, divide));
        const margin = ['lauterbrunnen', 'grand_canyon_toroweap'].includes(name) ? 0.1 : 0.01;
        T.ok(`test_occlusion_sane ${name}: valleys under less sky than divides by ${margin} (port)`, ov < od - margin, `valley ${ov.toFixed(3)}, divide ${od.toFixed(3)}`);
        const made = [];
        const l0 = meta.levels[0];
        const h0 = up(arrays.L0__in__h, l0.ny, l0.nx), h1 = up(arrays.L1__in__h, lv.ny, lv.nx);
        made.push(h0, h1);
        const S = new M.StackSampler([{ x0: l0.x0, y0: l0.y0, cell: l0.cell, field: h0 }]);
        const oNear = M.skyView(h1, lv.cell, 500.0, { x0: lv.x0, y0: lv.y0, outside: S });
        const oFull = M.skyView(h1, lv.cell, 500.0, { x0: lv.x0, y0: lv.y0, outside: S, nearCells: 100000 });
        const [an, af] = await R.readAll([oNear, oFull]);
        for (const f of [...made, oNear, oFull]) f.destroy();
        const d = an.map((v, i) => Math.abs(v - af[i]));
        const p99 = percentile(d, 99);
        T.ok(`test_occlusion_sane ${name}: the 2 x 2 far field within 0.03 (99th percentile) of a full march (port)`, p99 < 0.03 && rangeOf(an).lo >= 0 && rangeOf(an).hi <= 1,
            `p99 ${p99.toFixed(4)}, mean ${mean(d).toFixed(4)}`);
        if (name === 'grand_canyon_toroweap') {
            const gorge = Uint8Array.from(arrays.L1__in__h, (v) => (v < 600.0 ? 1 : 0));
            const g = mean(sel(o, gorge));
            T.ok("test_occlusion_sane: Toroweap's inner gorge floor under 0.6 of the sky (port)", g < 0.6, g.toFixed(3));
        }
        // test_wetness_sane
        const w = m.wetness;
        const wv = mean(sel(w, valley)), wd = mean(sel(w, divide));
        let wetOk = wv > wd + 0.3 && rangeOf(w).lo >= 0 && rangeOf(w).hi <= 1;
        let waterMin = null;
        if (arrays.L1__in__water) {
            const inner = [];
            for (let j = 16; j < lv.ny - 16; j++) for (let i = 16; i < lv.nx - 16; i++) if (arrays.L1__in__water[j * lv.nx + i] >= 0.3) inner.push(w[j * lv.nx + i]);
            waterMin = inner.length ? Math.min(...inner) : null;
            if (waterMin !== null && waterMin !== 1.0) wetOk = false;
        }
        T.ok(`test_wetness_sane ${name}: valleys wetter than divides by 0.3, water 1 (port)`, wetOk,
            `valley ${wv.toFixed(2)}, divide ${wd.toFixed(2)}${waterMin !== null ? `, water ${waterMin}` : ''}`);
        // test_stack_no_frame
        const frame = {};
        let frameOk = true;
        for (const nm of ['convex_20m', 'concave_20m', 'convex', 'concave', 'occlusion']) {
            const v = m[nm], edge = [], inner = [];
            for (let j = 0; j < lv.ny; j++) {
                for (let i = 0; i < lv.nx; i++) {
                    const x = v[j * lv.nx + i];
                    if (j < 3 || j >= lv.ny - 3 || i < 3 || i >= lv.nx - 3) edge.push(x);
                    if (j >= 40 && j < lv.ny - 40 && i >= 40 && i < lv.nx - 40) inner.push(x);
                }
            }
            const e = mean(edge), q = mean(inner);
            frame[nm] = [e, q];
            if (nm === 'occlusion' ? Math.abs(e - q) >= 0.15 : e >= 2.0 * q + 0.02) frameOk = false;
        }
        T.ok(`test_stack_no_frame ${name}: no frame of curvature or occlusion at the stacked border (port)`, frameOk,
            Object.entries(frame).map(([k, [e, q]]) => `${k} ${e.toFixed(3)}/${q.toFixed(3)}`).join(', '));
        rows[name] = { curvature: row, occlusion: { valley: ov, divide: od, far_p99: p99 }, wetness: { valley: wv, divide: wd, water_min: waterMin }, frame };
        T.ok(`${name}: ${n} cells a level, ${got.length} levels, ${Object.keys(got[1]).length} masks`, true);
    }
    results.checks.refs = rows;
    results.seconds.refs = Math.round(performance.now() - ts) / 1000;
}

if (manifest && want('hero')) {
    const meta = cases.get('hero_lauterbrunnen');
    if (meta) {
        const ts = performance.now();
        const { arrays, got, secs } = await stackCase(meta);
        results.seconds['stack hero'] = Math.round(secs * 100) / 100;
        for (let i = 0; i < got.length; i++) gradeLevel(`hero L${i} (${meta.levels[i].cell} m)`, got[i], arrays, `L${i}`, meta.fft_spread?.[`L${i}`], meta.ulp_floor?.[`L${i}`]);
        // test_stack_rings: every mask but aspect meets its parent at the seam (the outermost two cells)
        const seams = {};
        let ok = true;
        const metres = ['height', 'wear', 'deposit', 'talus', 'sand', 'water', 'strata'];
        for (let i = 1; i < got.length; i++) {
            const c = got[i], p = got[i - 1], lc = meta.levels[i], lp = meta.levels[i - 1];
            const worst = {};
            for (const nm of Object.keys(c)) {
                if (nm === 'aspect' || !(nm in p)) continue;
                const pa = p[nm];
                let sum = 0, cnt = 0, amax = 0;
                for (let k = 0; k < pa.length; k++) amax = Math.max(amax, Math.abs(pa[k]));
                const scale = nm === 'slope' ? 90.0 : (metres.includes(nm) ? Math.max(1.0, amax) : 1.0);
                for (let j = 0; j < lc.ny; j++) {
                    for (let q = 0; q < lc.nx; q++) {
                        if (!(j < 2 || j >= lc.ny - 2 || q < 2 || q >= lc.nx - 2)) continue;
                        const x = lc.x0 + (q + 0.5) * lc.cell, y = lc.y0 + (j + 0.5) * lc.cell;
                        const fx = (x - lp.x0) / lp.cell - 0.5, fy = (y - lp.y0) / lp.cell - 0.5;
                        if (!(fx >= 0 && fx <= lp.nx - 1 && fy >= 0 && fy <= lp.ny - 1)) continue;
                        const x0 = Math.min(Math.max(Math.floor(fx), 0), lp.nx - 2), y0 = Math.min(Math.max(Math.floor(fy), 0), lp.ny - 2);
                        const tx = fx - x0, ty = fy - y0;
                        const at = (a, b) => pa[b * lp.nx + a];
                        const pv = (at(x0, y0) * (1 - tx) + at(x0 + 1, y0) * tx) * (1 - ty) + (at(x0, y0 + 1) * (1 - tx) + at(x0 + 1, y0 + 1) * tx) * ty;
                        sum += Math.abs(pv - c[nm][j * lc.nx + q]);
                        cnt++;
                    }
                }
                worst[nm] = sum / Math.max(cnt, 1) / scale;
            }
            const bad = Object.entries(worst).filter(([, v]) => v > 0.005);
            if (bad.length) ok = false;
            seams[`${lc.cell} m in ${lp.cell} m`] = Math.max(...Object.values(worst));
        }
        T.ok('test_stack_rings: every mask but aspect meets its parent at the seams within 0.005 (port)', ok,
            Object.entries(seams).map(([k, v]) => `${k}: ${v.toFixed(5)}`).join(', '));
        let range = true;
        for (const m of got.slice(2)) {
            for (const nm of ['slope', 'occlusion', 'rock', 'rock_toe', 'vegetation', 'wetness', 'flow']) {
                const r = rangeOf(m[nm]);
                if (!(r.lo >= 0 && r.hi <= (nm === 'slope' ? 90 : 1)) || m[nm].some((v) => !Number.isFinite(v))) range = false;
            }
        }
        T.ok('test_stack_rings: the hero levels\' masks finite and in range (port)', range);
        results.checks.hero = { seams };
        results.seconds.hero = Math.round(performance.now() - ts) / 1000;
    }
}


// -------------------------------------------------------------------------------------- scale independence ---

const SCALE_BARS = { geometry: [0.03, 0.95], northness: [0.05, 0.95], eastness: [0.05, 0.95], flow: [0.08, 0.85],
    wetness: [0.08, 0.9], rock_toe: [0.08, 0.85], vegetation: [0.08, 0.85] };

function corrcoef(a, b) {
    const ma = mean(a), mb = mean(b);
    let sab = 0, saa = 0, sbb = 0;
    for (let i = 0; i < a.length; i++) {
        const x = a[i] - ma, y = b[i] - mb;
        sab += x * y;
        saa += x * x;
        sbb += y * y;
    }
    return sab / Math.sqrt(saa * sbb);
}
const std = (a) => {
    const m = mean(a);
    return Math.sqrt(mean(a.map((v) => (v - m) * (v - m))));
};

if (manifest && want('scale')) {
    const ts = performance.now();
    const rows = {};
    const bad = [];
    for (const meta of manifest.cases.filter((c) => c.kind === 'scale')) {
        const name = meta.reference;
        const arrays = await load(meta);
        const n = 360, c = meta.cell;
        const made = [];
        const base = fieldsOf(arrays, 'C', n, n, made), fine = fieldsOf(arrays, 'F', 2 * n, 2 * n, made);
        const P = paramsOf(meta.params);
        const norms = await M.normsFrom(base, { cell: c, params: P });
        const nk = Object.keys(meta.norms);
        let normWorst = 0;
        for (const k of nk) normWorst = Math.max(normWorst, Math.abs(norms[k] - meta.norms[k]) / Math.max(1, Math.abs(meta.norms[k])));
        T.ok(`scale ${name}: normsFrom equals norms_from within 1e-5`, normWorst < 1e-5, `worst ${r3(normWorst)}`);
        const mc = await hostMasks(await M.compute(base, { cell: c, names: meta.names, norms, params: P, strict: false }));
        const mf = await hostMasks(await M.compute(fine, { cell: c / 2, names: meta.names, norms, params: P, strict: false }));
        for (const f of made) f.destroy();
        gradeLevel(`scale ${name} coarse`, mc, arrays, 'C', meta.fft_spread?.C, meta.ulp_floor?.C);
        gradeLevel(`scale ${name} fine`, mf, arrays, 'F', meta.fft_spread?.F, meta.ulp_floor?.F);
        // test_scale_independence's statistics, on the port's masks
        const row = {};
        const crop = (a, w) => {                                    // [12:-12] of an n x n array
            const out = [];
            for (let j = 12; j < n - 12; j++) for (let i = 12; i < n - 12; i++) out.push(a[j * w + i]);
            return out;
        };
        const box2 = (a) => {
            const out = new Float64Array(n * n);
            for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) out[j * n + i] = (a[(2 * j) * 2 * n + 2 * i] + a[(2 * j) * 2 * n + 2 * i + 1] + a[(2 * j + 1) * 2 * n + 2 * i] + a[(2 * j + 1) * 2 * n + 2 * i + 1]) / 4;
            return out;
        };
        const bmax = (a) => {
            const out = new Float64Array(n * n);
            for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) out[j * n + i] = Math.max(a[(2 * j) * 2 * n + 2 * i], a[(2 * j) * 2 * n + 2 * i + 1], a[(2 * j + 1) * 2 * n + 2 * i], a[(2 * j + 1) * 2 * n + 2 * i + 1]);
            return out;
        };
        const thr = P.channel_area_m2;
        const river = crop(arrays.C__in__A, n).map((v) => v >= 10 * thr);
        const chC = crop(mc.channels, n), chF = crop(bmax(mf.channels), n);
        row.channels_on_rivers = { coarse: mean(sel(chC, river)), fine_block_max: mean(sel(chF, river)), cells: river.filter(Boolean).length };
        for (const nm of meta.names) {
            if (!(nm in mc)) continue;
            let a = crop(mc[nm], n), b = crop(box2(mf[nm]), n);
            if (nm.startsWith('curv_')) {
                const sc = parseFloat(nm.split('_').pop());
                a = a.map((v) => v * sc);
                b = b.map((v) => v * sc);
            }
            if (nm === 'slope') {
                const sa = [...a].sort((x, y) => x - y), sb = [...b].sort((x, y) => x - y);
                row[nm] = { p50: percentile(sb, 50) - percentile(sa, 50), p90: percentile(sb, 90) - percentile(sa, 90),
                    mean_abs: mean(a.map((v, i) => Math.abs(v - b[i]))) };
                continue;
            }
            const corr = std(a) > 1e-9 && std(b) > 1e-9 ? corrcoef(a, b) : 1.0;
            row[nm] = { mean_abs: mean(a.map((v, i) => Math.abs(v - b[i]))), mean_a: mean(a), mean_b: mean(b), corr };
        }
        for (const [nm, r] of Object.entries(row)) {
            if (nm === 'slope') {
                if (Math.abs(r.p50) > 1.0 || Math.abs(r.p90) > 1.5) bad.push(`${name} slope`);
                continue;
            }
            if (nm === 'channels_on_rivers') {
                if (r.cells && meta.sand == null && Math.min(r.coarse, r.fine_block_max) < 0.9) bad.push(`${name} rivers`);
                continue;
            }
            if (nm === 'channels') continue;
            const [mb, cb] = SCALE_BARS[nm] ?? SCALE_BARS.geometry;
            if (r.mean_abs > mb || (r.corr < cb && Math.max(Math.abs(r.mean_a), Math.abs(r.mean_b)) > 0.01)) bad.push(`${name} ${nm}`);
        }
        rows[name] = row;
    }
    results.checks.scale_independence = rows;
    T.ok('test_scale_independence: each mask means the same on the field upsampled 2 x, within the Blender bars (port)',
        Object.keys(rows).length > 0 && bad.length === 0, bad.length ? `FAIL ${bad.join(', ')}` : `${Object.keys(rows).length} references`);
    results.seconds.scale = Math.round(performance.now() - ts) / 1000;
}


// --------------------------------------------------------------------------------------- slope and the JSON ---

if (want('slope_json')) {
    const ts = performance.now();
    const RP = await import('../../recipes/real_place.js');
    const names = W.demNames();
    let worst = 0, n = 0;
    const bad = [], rows = {};
    for (const name of names) {
        const d = W.dem(name);
        const dem = await RP.load(R, name);
        const { h, ctx } = dem.heights(R, 0.0);
        for (const [tag, field, json, pixel] of [['', h, d.json, dem.pixel], ['_context', ctx, d.contextJson, dem.ctx?.pixel]]) {
            if (!field || !json) continue;
            const meta = JSON.parse(Deno.readTextFileSync(json));
            const ss = meta.shape_stats;
            const m = await M.compute({ h: field }, { cell: pixel, x0: -field.w * pixel / 2, y0: -field.h * pixel / 2, names: ['slope'] });
            const got = await P1.percentile(m.slope, [10, 50, 90, 99], { dtype: 'float64' });
            m.dispose();
            const wantP = [ss.slope_deg_p10, ss.slope_deg_p50, ss.slope_deg_p90, ss.slope_deg_p99];
            const dd = Math.max(...got.map((v, i) => Math.abs(v - wantP[i])));
            worst = Math.max(worst, dd);
            n++;
            rows[name + tag] = { got: got.map((v) => Math.round(v * 100) / 100), json: wantP, max_diff: Math.round(dd * 1000) / 1000 };
            if (dd > 0.1) bad.push(name + tag);
        }
        dem.dispose();
    }
    await RP.clearCache(R);
    results.checks.slope_json = rows;
    T.ok(`test_slope_matches_reference_json: slope p10/p50/p90/p99 of ${n} DEMs within 0.1 deg of their JSON (port)`, n > 0 && !bad.length,
        `worst ${worst.toFixed(3)} deg` + (bad.length ? `; FAIL ${bad.join(', ')}` : ''));
    results.seconds.slope_json = Math.round(performance.now() - ts) / 1000;
}


// ---------------------------------------------------------------------------------------- the floor's saves ---

const MASK_INPUTS = ['h', 'A', 'water', 'wear', 'deposit', 'talus', 'sand', 'lava', 'zs'];
function ulp16(x) {
    const a = Math.abs(x);
    if (a < 2 ** -14) return 2 ** -24;
    return 2 ** (Math.floor(Math.log2(a)) - 10);
}

if (want('floor')) {
    let floor = null;
    try {
        floor = JSON.parse(Deno.readTextFileSync(`${FIX}/floor.json`));
    } catch (_e) {
        console.log('[skip] floor: no floor.json (masks_expected.py --only floor)');
    }
    if (floor) {
        const ts = performance.now();
        const root = `${W.parityOut()}/${floor.folder}`;
        const summary = {};
        let allOk = true, nRuns = 0;
        for (const run of floor.runs) {
            if (RUNS && !RUNS.has(run.run)) continue;
            if (run.error) {
                T.ok(`floor ${run.run}: masks.py recomputed`, false, run.error);
                allOk = false;
                continue;
            }
            const info = JSON.parse(Deno.readTextFileSync(`${root}/${run.run}/base/terrain.json`));
            const plan = info.plan;
            const keys = [];
            for (let i = 0; i < plan.length; i++) for (const k of MASK_INPUTS) keys.push(`L${i}__f__${k}`);
            const raw = await Io.readNpz(`${root}/${run.save}`);
            const made = [];
            const fields = plan.map((lv, i) => {
                const f = {};
                for (const k of MASK_INPUTS) {
                    const a = raw[`L${i}__f__${k}`];
                    if (a) made.push(f[k] = up(a.data, lv.n, lv.n));
                }
                return f;
            });
            const t0 = performance.now();
            const ms = await M.computeStack(fields, plan, { params: paramsOf(run.mask_params) });
            const secs = (performance.now() - t0) / 1000;
            for (const f of made) f.destroy();
            let ok = true, worst = 0, worstName = '';
            const fails = [];
            ms.forEach((m, i) => {
                for (const [nm, g] of Object.entries(m)) {
                    const s = raw[`L${i}__m__${nm}`];
                    if (!s) {
                        fails.push(`L${i} ${nm}: not in the save`);
                        ok = false;
                        continue;
                    }
                    const w = s.data instanceof Float32Array ? s.data : Float32Array.from(s.data);
                    const half = s.dtype === '<f2';
                    const { range, amax } = rangeOf(w);
                    const span = Math.max(range, 1e-6 * amax, 1e-20);
                    const sp = run.fft_spread?.[`L${i}`]?.[nm] ?? 0, fl = run.ulp_floor?.[`L${i}`]?.[nm] ?? 0;
                    const gr = grade(g, w, Math.max(1e-4 * span, 1.25 * (sp + fl)), { circ: nm === 'aspect',
                        extra: half ? (k) => ulp16(w[k]) : null });
                    if (gr.over > worst) { worst = gr.over; worstName = `L${i} ${nm}`; }
                    if (!gr.ok) {
                        ok = false;
                        fails.push(`L${i} ${nm} ${r3(gr.over)} (${gr.bad} cells)`);
                    }
                }
                const saved = Object.keys(raw).filter((k) => k.startsWith(`L${i}__m__`)).map((k) => k.slice(`L${i}__m__`.length));
                const extra = saved.filter((k) => !(k in m));
                if (extra.length) {
                    ok = false;
                    fails.push(`L${i} not made: ${extra.join(', ')}`);
                }
            });
            nRuns++;
            allOk = allOk && ok;
            summary[run.run] = { ok, worst: r3(worst), worst_mask: worstName, seconds: Math.round(secs * 100) / 100,
                blender_masks_seconds: info.seconds?.masks ?? null, levels: plan.map((l) => [l.n, l.cell]),
                blender_recompute_equal: run.all_equal, fails };
            T.ok(`floor ${run.run}: every mask of the save made again within its grade`, ok,
                `worst ${r3(worst)} of range (${worstName}); ${Math.round(secs * 10) / 10} s` + (fails.length ? `; FAIL ${fails.slice(0, 6).join(', ')}` : ''));
        }
        results.floor = summary;
        T.ok(`floor: ${nRuns} saves`, nRuns > 0 && allOk);
        results.seconds.floor = Math.round(performance.now() - ts) / 1000;
    }
}

results.seconds.total = Math.round(performance.now() - t00) / 1000;
T.extra = results;
G.shutdown();
const code = T.done(null);
const failed = T.rows.filter((r) => !r.passed);
const outName = ONLY ? `masks_test_${[...ONLY].sort().join('_')}.json` : 'masks_test.json';
Deno.writeTextFileSync(`${W.out('masks')}/${outName}`, JSON.stringify({ test: T.title, deno: Deno.version.deno,
    date: new Date().toISOString(), fixtures: manifest ? { key: manifest.key, versions: manifest.versions } : null,
    checks: T.rows.length, failed: failed.map((r) => r.check), ...results, rows: T.rows }, null, 1));
Deno.exit(code);
