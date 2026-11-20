// The volcanoes and craters package's plans and its numpy-made functions against the Blender edition's own results
// (PORT_PLAN.md 8.2 row P9: "cone and vent plans equal; lava walkers' visits equal to numpy's for the same height
// field"; 5.3's grades), from the plan fixtures (tests/parity/fixtures.py --plans: every call the floor's base runs
// made, by Blender's Python 3.13 with numpy 2.3.4):
//   plans (1e-12 relative, numpy's draws bit for bit)   rift_cones, cinder_field, lava_vents, ravines_of; the
//                         azimuth tables read where numpy read them (azimuth_noise, embayment_outline); _face_table's
//                         run U and its foot slopes S0 (JavaScript doubles)
//   walkers (exact)       lava_walkers: the passage fraction of every cell equal to numpy's, from the same float64
//                         heights (solvers/volcanic.js lavaWalkers: JavaScript over the walkers, the slope at the
//                         cells they visit)
//   GPU                   _face_table's Z and S (kernels/volcanic/face_table.wgsl; 5.3's function grade, <= 1e-5 x
//                         range); lava_surface (both margins, the lobes and the rough top: numpy's standard normals
//                         drawn on the GPU) at the kernel grade, <= 1e-4 x range, with the count within 1e-5 reported:
//                         its footprint is smoothstep(0.5 p_edge, 2 p_edge) of the blurred passage, whose slope 1 /
//                         p_edge (33-100 in the recipes) carries the float32 blur's 1e-7 into the margins and on
//                         through the margin blurs (measured worst 2.2e-5 of range); and the GPU's standard normals
//                         themselves against core/np_random.js draw for draw (within 4 float32 steps of numpy's
//                         double: the value is made in float32) with the generator left where numpy leaves it
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/volcanoes_craters/plans_test.mjs
//         [--only rift_cones,lava_walkers,...] [--max N] (cases per function)   (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/volcanoes_craters/plans_test.json. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import { defaultRng } from '../../core/np_random.js';
import * as VO from '../../solvers/volcanic.js';
import * as V from './_vc.mjs';

const { C } = V;
const A = V.argsOf();
const ONLY = A.list('--only');
const MAX = Number(A.opt('--max', '0')) || Infinity;
const want = (name) => !ONLY || ONLY.includes(name);

const T = new C.Checks('volcanoes_craters: plans and functions against the plan fixtures');
const fx = V.loadFixtureOfCode('plans');
const summary = {};

/** got against want, walked together: numbers within tol of the largest |number| of the case (relative), integers,
 * strings, booleans and null equal. { ok, worst, why }. */
function compareValues(got, wantV, tol = 1e-12) {
    let scale = 1e-300;
    const walkScale = (w) => {
        if (typeof w === 'number') { if (Number.isFinite(w)) scale = Math.max(scale, Math.abs(w)); } else if (Array.isArray(w)) w.forEach(walkScale);
        else if (w && typeof w === 'object') Object.values(w).forEach(walkScale);
    };
    walkScale(wantV);
    let worst = 0, why = null;
    const walk = (g, w, path) => {
        if (why) return;
        if (w === null || w === undefined) { if (!(g === null || g === undefined)) why = `${path}: ${JSON.stringify(g)} for None`; return; }
        if (typeof w === 'number') {
            const gv = typeof g === 'boolean' ? Number(g) : g;
            if (typeof gv !== 'number') { why = `${path}: ${JSON.stringify(g)} for ${w}`; return; }
            if (Number.isNaN(w) && Number.isNaN(gv)) return;
            if (gv === w) return;
            const d = Math.abs(gv - w) / scale;
            worst = Math.max(worst, d);
            if (!(d <= tol)) why = `${path}: ${gv} for ${w}`;
            return;
        }
        if (typeof w === 'string' || typeof w === 'boolean') { if (g !== w) why = `${path}: ${JSON.stringify(g)} for ${JSON.stringify(w)}`; return; }
        if (Array.isArray(w)) {
            const ga = ArrayBuffer.isView(g) ? Array.from(g) : g;
            if (!Array.isArray(ga) || ga.length !== w.length) { why = `${path}: ${ga?.length} items for ${w.length}`; return; }
            w.forEach((x, i) => walk(ga[i], x, `${path}[${i}]`));
            return;
        }
        if (typeof w === 'object') {
            if (!g || typeof g !== 'object') { why = `${path}: ${JSON.stringify(g)} for an object`; return; }
            const extra = Object.keys(g).filter((k) => !(k in w) && g[k] !== null && g[k] !== undefined);
            if (extra.length) { why = `${path}: extra keys ${extra}`; return; }
            for (const k of Object.keys(w)) walk(g[k], w[k], `${path}.${k}`);
        }
    };
    walk(got, wantV, 'result');
    return { ok: !why, worst, why };
}

const argOf = (c, v) => (v && typeof v === 'object' && !Array.isArray(v) && typeof v.__array__ === 'string'
    ? C.array(fx.dir, c.inputs[v.__array__]) : v);

/** A Python call's positional and keyword arguments as one object, by the function's parameter names. */
function named(c, names) {
    const o = {};
    (c.call.args ?? []).forEach((v, i) => { o[names[i]] = v; });
    return { ...o, ...(c.call.kwargs ?? {}) };
}

const casesOf = (fn) => (fx ? fx.manifest.cases.filter((c) => c.function === `solvers.volcanic.${fn}` && !c.error) : []).slice(0, MAX);

function tally(name, rows, grade) {
    const n = rows.length, ok = rows.filter((r) => r.ok).length;
    const worst = Math.max(0, ...rows.map((r) => r.worst ?? 0));
    summary[name] = { cases: n, ok, worst, grade, failed: rows.filter((r) => !r.ok).slice(0, 6).map((r) => `${r.label}: ${r.why}`) };
    T.ok(`${name}: ${ok} of ${n} cases ${grade} (worst ${C.sci(worst)})`, n > 0 && ok === n, summary[name].failed.join('; '));
}

const RIFT = ['centre', 'rift_azimuth_deg', 'count', 'distance_m', 'spread_m', 'width_median_m', 'width_m', 'hw_ratio',
    'crater_ratio', 'crater_depth_frac', 'flank_deg', 'breach_fraction', 'outline_noise', 'seed'];
const FIELD = ['window', 'count', 'width_m', 'hw_ratio', 'crater_ratio', 'flank_deg', 'vent_lines', 'line_trend_deg',
    'line_spread_m', 'age_yr', 'breach_fraction', 'outline_noise', 'avoid', 'elongation', 'overlap', 'breach_toward_deg',
    'breach_spread_deg', 'seed'];

if (!fx) {
    T.ok('the plan fixtures are there (tests/parity/fixtures.py --plans)', false, 'no fixtures');
} else {
    // ------------------------------------------------------------------------------------ the cone and vent plans
    const plan = (name, run) => {
        if (!want(name)) return;
        const rows = [];
        for (const c of casesOf(name)) {
            let r;
            try {
                r = compareValues(run(c), c.result);
            } catch (e) {
                r = { ok: false, worst: Infinity, why: `${e.name}: ${e.message}` };
            }
            rows.push({ label: c.label, ...r });
        }
        tally(name, rows, 'equal within 1e-12 relative');
    };
    plan('rift_cones', (c) => {
        const a = named(c, RIFT);
        const { centre, rift_azimuth_deg: az, ...o } = a;
        return VO.riftCones(centre, az, o);
    });
    plan('cinder_field', (c) => VO.cinderField(named(c, FIELD)));
    plan('lava_vents', (c) => VO.lavaVents(c.call.args[0], c.call.args[1]));
    plan('ravines_of', (c) => VO.ravinesOf(c.call.args[0], c.call.args[1]));

    // ------------------------------------------------------------------------------- the azimuth tables, read
    const sampled = (name, table) => {
        if (!want(name)) return;
        const rows = [];
        for (const c of casesOf(name)) {
            // the azimuths as numpy took them: an AzimuthSampler (its i and f as arrays or inline lists), or radians
            // (an array, a list or a number: AzimuthSampler(az) made here, as numpy makes it)
            const s = c.call.args[0];
            const list = (v) => (Array.isArray(v) ? v : typeof v === 'number' ? [v] : Array.from(argOf(c, v)));
            let I, F;
            if (s && typeof s === 'object' && 'i' in s && 'f' in s) {
                I = list(s.i);
                F = list(s.f);
            } else {
                const az = list(s);
                I = [];
                F = [];
                for (const a of az) { const [i, f] = VO.azSampler(a); I.push(i); F.push(f); }
            }
            const wantA = c.outputs.result ? C.array(fx.dir, c.outputs.result) : list(c.result);
            const t = table(c);
            let worst = 0, scale = 0;
            for (const v of wantA) scale = Math.max(scale, Math.abs(v));
            for (let k = 0; k < wantA.length; k++) {
                const g = VO.azRead(t, [I[k], F[k]]);
                if (g !== wantA[k]) worst = Math.max(worst, Math.abs(g - wantA[k]) / (scale || 1));
            }
            rows.push({ label: c.label, ok: worst <= 1e-12, worst, why: `worst ${C.sci(worst)}` });
        }
        tally(name, rows, 'equal within 1e-12 relative at numpy\'s sample points');
    };
    sampled('azimuth_noise', (c) => {
        const [, seed, salt, kMin = 1, kMax = 6, decay = 1.5] = c.call.args;
        const kw = c.call.kwargs ?? {};
        return VO.azimuthNoiseTable(seed, salt, kw.k_min ?? kMin, kw.k_max ?? kMax, kw.decay ?? decay);
    });
    sampled('embayment_outline', (c) => {
        const [, count, amp, widthDeg, seed, salt = 55] = c.call.args;
        return VO.embaymentTable(count, amp, widthDeg, seed, c.call.kwargs?.salt ?? salt);
    });

    // --------------------------------------------------------------------------------------- the lava walkers
    if (want('lava_walkers')) {
        const rows = [];
        for (const c of casesOf('lava_walkers')) {
            const [h0, cell, start, walkers, length, dh, seed, salt, dhRel, pond, stopSpread, frontSpread] = c.call.args;
            const h = argOf(c, h0);
            const [ny, nx] = c.inputs[h0.__array__].shape;
            const wantP = C.array(fx.dir, c.outputs.result);
            const t0 = performance.now();
            const w = VO.lavaWalkers(h, ny, nx, cell, start, walkers ?? 400, length ?? 6000.0, dh ?? 3.0, seed ?? 0, salt ?? 0,
                dhRel ?? null, pond ?? null, stopSpread ?? 0.0, frontSpread ?? 0.0);
            const ms = performance.now() - t0;
            let diff = 0, visited = 0;
            for (let k = 0; k < wantP.length; k++) {
                const g = Math.min(w.visits[k] / w.N, 1.0);
                if (g !== wantP[k]) diff++;
                if (wantP[k] > 0) visited++;
            }
            rows.push({ label: c.label, ok: diff === 0, worst: diff, why: `${diff} of ${wantP.length} cells differ (${visited} visited; ${ms.toFixed(0)} ms)` });
        }
        tally('lava_walkers', rows, 'bit-equal passage at every cell');
    }

    // ------------------------------------------------------------------------------------------ on the GPU
    const gpuWanted = ['_face_table', 'lava_surface', 'standard_normal'].some(want);
    const R = gpuWanted ? await G.init() : null;
    const fieldGrade = (got, wantA, k = 1e-5) => {
        let lo = Infinity, hi = -Infinity, err = 0;
        for (let i = 0; i < wantA.length; i++) {
            const w = wantA[i];
            if (!Number.isFinite(w)) continue;
            lo = Math.min(lo, w);
            hi = Math.max(hi, w);
            err = Math.max(err, Math.abs(got[i] - w));
        }
        const range = (hi - lo) || Math.max(Math.abs(lo), 1e-30);
        return { ok: err <= k * range + 16 * C.ulp32(Math.max(Math.abs(lo), Math.abs(hi))), worst: err / range };
    };

    if (R && want('standard_normal')) {
        const rows = [];
        for (const [seed, rows_, cols, count] of [[1, 64, 64, 1], [2, 337, 301, 2], [3, 512, 512, 1], [4, 1, 5000, 1],
            [5, 700, 650, 2], [6, 129, 257, 1], [7, 512, 512, 2], [8, 3, 3, 1]]) {
            const a = defaultRng([seed, 9097]), b = defaultRng([seed, 9097]);
            const fs = await VO.standardNormalGpu(R, a, rows_, cols, count);
            const parts = Array.isArray(fs) ? fs : [fs];
            let ulps = 0, n = 0;
            for (const f of parts) {
                const got = await R.read(f);
                const ref = b.standard_normal([rows_, cols]);
                for (let i = 0; i < ref.length; i++) {
                    const u = C.ulp32(ref[i]) || 1e-45;
                    ulps = Math.max(ulps, Math.abs(got[i] - ref[i]) / u);
                }
                n += ref.length;
                f.destroy();
            }
            const same = ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7'].every((k) => a[k] === b[k]);
            const next = a.nextDouble() === b.nextDouble();
            rows.push({ label: `seed ${seed} (${rows_} x ${cols}) x ${count}`, ok: ulps <= 4 && same && next, worst: ulps,
                why: `${n} draws, worst ${ulps.toFixed(2)} float32 steps, generator ${same && next ? 'where numpy leaves it' : 'ELSEWHERE'}` });
        }
        tally('standard_normal (GPU)', rows, 'within 4 float32 steps of numpy\'s draws, the stream position equal');
    }

    if (R && want('_face_table')) {
        const rows = [];
        for (const c of casesOf('_face_table')) {
            const [H, wall, spec, seed] = c.call.args;
            VO.clearMemos();
            const ft = VO.faceTable(R, H, wall, spec, seed);
            const zs = await R.read(ft.zst);
            const Zw = C.array(fx.dir, c.outputs['result[1]']), Sw = C.array(fx.dir, c.outputs['result[2]']);
            const S0w = C.array(fx.dir, c.outputs['result[3]']);
            const Zg = new Float32Array(Zw.length), Sg = new Float32Array(Sw.length);
            for (let i = 0; i < Zw.length; i++) { Zg[i] = zs[2 * i]; Sg[i] = zs[2 * i + 1]; }
            const z = fieldGrade(Zg, Zw), s = fieldGrade(Sg, Sw);
            const u = compareValues(ft.U, c.result[0]), s0 = compareValues(Array.from(ft.S0), Array.from(S0w));
            rows.push({ label: c.label, ok: z.ok && s.ok && u.ok && s0.ok, worst: Math.max(z.worst, s.worst),
                why: `U ${u.ok ? 'equal' : u.why}, S0 ${s0.ok ? 'equal' : s0.why}, Z ${C.sci(z.worst)}, S ${C.sci(s.worst)} of range` });
        }
        tally('_face_table', rows, 'U and S0 within 1e-12, Z and S within 1e-5 of range');
    }

    if (R && want('lava_surface')) {
        const rows = [];
        for (const c of casesOf('lava_surface')) {
            const [P0, cell, th, , , pEdge = 0.04, margin = null, levee = 0.3, rough = 0.12, age = 0.0, seed = 0,
                widthM = null, frontDeg = null, leveeFrac = 0.1, ws0 = null] = c.call.args;
            const kw = c.call.kwargs ?? {};
            const [ny, nx] = c.inputs[P0.__array__].shape;
            const P = R.field(ny, nx, 1, Float32Array.from(argOf(c, P0)));
            const wsA = kw.width_scale ?? ws0;
            const ws = wsA ? R.field(ny, nx, 1, Float32Array.from(argOf(c, wsA))) : null;
            const [Tf, Ff] = await VO.lavaSurface(R, P, cell, th, { p_edge: kw.p_edge ?? pEdge, margin_m: kw.margin_m ?? margin,
                levee: kw.levee ?? levee, rough: kw.rough ?? rough, age: kw.age ?? age, seed: kw.seed ?? seed,
                width_m: kw.width_m ?? widthM, front_deg: kw.front_deg ?? frontDeg, levee_frac: kw.levee_frac ?? leveeFrac,
                width_scale: ws });
            const [tg, fg] = await R.readAll([Tf, Ff]);
            for (const f of [P, ws, Tf, Ff]) if (f && !f.destroyed) f.destroy();
            const tw = C.array(fx.dir, c.outputs['result[0]']), fw = C.array(fx.dir, c.outputs['result[1]']);
            const t = fieldGrade(tg, tw, 1e-4), f = fieldGrade(fg, fw, 1e-4);
            const fine = fieldGrade(tg, tw, 1e-5).ok && fieldGrade(fg, fw, 1e-5).ok;
            rows.push({ label: c.label, ok: t.ok && f.ok, fine, worst: Math.max(t.worst, f.worst),
                why: `T ${C.sci(t.worst)}, footprint ${C.sci(f.worst)} of range (${ny} x ${nx}${frontDeg !== null ? ', aa' : ''})` });
        }
        tally('lava_surface (GPU)', rows, `T and the footprint within 1e-4 of range (${rows.filter((r) => r.fine).length} ` +
            'within 1e-5)');
    }
    if (R) G.shutdown();
}

T.extra.summary = summary;
Deno.exit(V.finish(T, 'plans_test'));
