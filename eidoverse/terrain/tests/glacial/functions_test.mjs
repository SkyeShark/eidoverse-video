// The glacial package's function fixtures (PORT_PLAN.md 5.1, 5.3): every GPU replacement of solvers/glacial.py's numpy
// code against that numpy function, on the fixtures tests/glacial/glacial_expected.py makes with Blender's own Python
// (the floor runs' carve inputs, alpine_valley seeds 1 and 2, and the Blender glacial tests' own synthetic inputs).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/glacial/functions_test.mjs
//         [--only carve,synthetic]                              (on a shared machine, behind $EIDO_GPU_WRAP)
//
// The grades (plan 5.3): integers (receivers, streams, labels, donors, the seed cells, the jump flood's candidates)
// bit for bit; float functions within 1e-5 of their range, with the rounding floor of the built-ins they lean on
// (tests/parity/_common.mjs); plans (the cirques, from numpy's own seeds) within 1e-12 relative, and from the port's
// own seeds within the float grade of the seeds' values. On the carve inputs the centrelines are run twice: from
// Blender's own discharge and area (the fixture's: the function alone, against numpy) and from the port's (the
// whole pipeline). Where the Blender edition runs a function on its GPU (the jump flood's eight passes, wall_flutes'
// noise, the whole carve), the reference is that GPU result (tests/glacial/gpu_fixtures.py, when it has been made)
// and numpy's twin is reported beside it: the jump flood's candidates identical but for near ties (a differing slot
// whose float64 target is within 16 float32 steps of Blender's), the flutes at the float-function grade with their
// rounding floor, the carve at the stage grade with its floor (glacial_expected.py measures both floors).
// JavaScript per cell here is test code. Writes tests/out/glacial/functions_test.json.

import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import { Fields } from '../../core/fields.js';
import { prims } from '../../core/prims.js';
import * as RUN from '../../run.js';
import * as FL from '../../solvers/fluvial.js';
import * as GL from '../../solvers/glacial.js';
import * as C from '../parity/_common.mjs';
import * as GLT from './_glacial.mjs';
import { finish } from './_glacial.mjs';

const W = C.W;
const args = [...Deno.args];
const onlyAt = args.indexOf('--only');
const ONLY = onlyAt >= 0 ? new Set(args[onlyAt + 1].split(',')) : null;
const want = (s) => !ONLY || ONLY.has(s);
const T = new C.Checks('glacial: function fixtures');
const DIR = `${W.out('glacial')}/fixtures`;
let M;
try {
    M = JSON.parse(Deno.readTextFileSync(`${DIR}/manifest.json`));
} catch (_e) {
    console.log('[skip] no glacial fixtures: make them with <Blender\'s python> -I eidoverse/terrain/tests/glacial/glacial_expected.py');
    Deno.exit(0);
}
const ON_GPU = C.readJson(`${DIR}/gpu_fixtures.json`)?.cases ?? null;   // Blender's GPU results (gpu_fixtures.py)
const R = await G.init();
const P = prims(R);
const results = {};
const arr = (c, name) => C.array(DIR, c.arrays[name]);
const up32 = (c, name) => { const a = c.arrays[name]; return R.field(a.shape[0], a.shape[1] ?? 1, a.shape[2] ?? 1, Float32Array.from(arr(c, name))); };
const upI = (c, name, n) => R.field(n, n, 1, Int32Array.from(arr(c, name)), 'i32');
const sci = C.sci;

/** Exact comparison of two arrays (first n items): { ok, diff, n }. */
function exact(got, wantA, n = wantA.length) {
    let diff = 0;
    for (let i = 0; i < n; i++) if (!Object.is(Number(got[i]), Number(wantA[i]))) diff++;
    return { ok: diff === 0, diff, n };
}

/** A float grade over the first n items: max |d| against max(k range, m ulp(amax), abs). */
function floats(got, wantA, opts = {}) {
    const n = opts.n ?? wantA.length;
    return C.gradeArray(Float64Array.from({ length: n }, (_, i) => got[i]), Float64Array.from({ length: n }, (_, i) => wantA[i]),
        { k: opts.k ?? 1e-5, uses: opts.uses ?? [], scale: opts.scale, abs: opts.abs });
}

function rowsClose(got, wantRows, rel) {
    if (got.length !== wantRows.length) return { ok: false, detail: `${got.length} rows, Blender ${wantRows.length}` };
    let worst = 0;
    got.forEach((r, i) => r.forEach((v, j) => {
        const w = wantRows[i][j];
        worst = Math.max(worst, Math.abs(v - w) / Math.max(Math.abs(w), 1.0));
    }));
    return { ok: worst <= rel, worst, detail: `${got.length} rows, worst ${sci(worst)} relative` };
}

// ------------------------------------------------------------------------------------------------- the carve ---

if (want('carve')) {
    for (const c of M.cases.filter((x) => x.function === 'carve')) {
        const lv = Level.fromDict(c.level), n = lv.n, main = Level.fromDict(c.args.main), v = c.values;
        const params = c.args.params, base = c.args.base_elevation_m, seed = c.args.seed;
        const tag = c.label.replace(/^carve input, /, '');
        const row = (results[tag] = {});
        const h = up32(c, 'h');
        // 1. drainage_receivers: the receivers and the filled surface, exactly
        const { recv, filled } = await GL.drainageReceivers(h, lv.cell, c.args.sea_level);
        const [rg, fg] = await R.readAll([recv, filled]);
        const er = exact(rg, arr(c, 'recv')), ef = exact(fg, arr(c, 'filled'));
        row.receivers = { recv_diff: er.diff, filled_diff: ef.diff };
        T.ok(`${tag}: drainage_receivers bit for bit (the receivers' k and the filled surface)`, er.ok && ef.ok,
            `${er.diff} receivers and ${ef.diff} filled heights of ${n * n} differ`);
        // 2. the mass balance
        const b = GL.massBalance(h, base, params, c.args.sea_level);
        const gb = floats(await R.read(b), arr(c, 'b'), { uses: ['arithmetic'] });
        T.ok(`${tag}: mass_balance within 1e-5 of its range`, gb.ok, `worst ${sci(gb.over)} of range`);
        // 3. the discharge and the area against Blender's GPU discharge and the twin's area, the iterations equal
        const ones = R.field(n, n, 1, new Float32Array(n * n).fill(1));
        const Qr = await GL.iceFluxConverge(R, filled, b, lv.cell, { recv, params });
        const Ar = await GL.iceFluxConverge(R, filled, ones, lv.cell, { recv, params: { ...params, ice_width_m: 0.0 } });
        const [qg, ag] = await R.readAll([Qr.Q, Ar.Q]);
        const gq = floats(qg, arr(c, 'Q_gpu'), { k: 1e-5, uses: ['pow'] }), ga = exact(ag, arr(c, 'A'));
        row.discharge = { q_over: gq.over, q_err: gq.err, a_diff: ga.diff, it_q: Qr.iterations, it_a: Ar.iterations };
        T.ok(`${tag}: the ice discharge within 1e-5 of its range of Blender's GPU discharge, ${v.it_q} iterations as Blender's`,
            gq.ok && Qr.iterations === v.it_q, `worst ${sci(gq.over)} of range (${sci(gq.err)} m3/yr), ${Qr.iterations} iterations`);
        T.ok(`${tag}: the D8 drainage area bit for bit, ${v.it_a} iterations as Blender's`, ga.ok && Ar.iterations === v.it_a,
            `${ga.diff} cells differ, ${Ar.iterations} iterations`);
        // 4. best_donor, exactly
        const upF = GL.bestDonor(recv, Ar.Q);
        const eu = exact(await R.read(upF), arr(c, 'up'));
        T.ok(`${tag}: best_donor bit for bit`, eu.ok, `${eu.diff} of ${n * n} cells differ`);
        // 5. the centrelines, from Blender's own discharge and area (the function), then from the port's (the pipeline)
        const Qb = up32(c, 'Q_gpu'), Ab = up32(c, 'A');
        for (const [which, Qx, Ax] of [['from Blender\'s discharge', Qb, Ab], ['from the port\'s discharge', Qr.Q, Ar.Q]]) {
            const cl = await GL.centrelines(R, h, Qx, Ax, recv, lv, main, params, base, seed);
            if (!cl) { T.ok(`${tag}: centrelines ${which}`, false, 'none'); continue; }
            const hc = await GL.centrelinesToHost(R, cl, lv);
            const S = hc.S, wS = arr(c, 'idx').length;
            const ints = {};
            for (const k of ['idx', 'rcv', 'main', 'sid', 'head', 'cont']) ints[k] = S === wS ? exact(hc[k], arr(c, k)).diff : 'count';
            const intOk = S === wS && Object.values(ints).every((d) => d === 0);
            T.ok(`${tag}: streams ${which}: the seeds, receivers, main donors, stream ids, heads and links equal numpy's (lexsort)`,
                intOk, `${S} seeds (numpy ${wS}), ${cl.st.nstreams} streams (numpy ${v.streams}); differing ${JSON.stringify(ints)}`);
            T.ok(`${tag}: Q_ref ${which} ${cl.Q_ref === v.Q_ref ? 'equal to numpy\'s' : 'differs'}`, which.includes('Blender') ? cl.Q_ref === v.Q_ref : true,
                `${cl.Q_ref} (numpy ${v.Q_ref})`);
            if (S === wS) {
                const gr = {};
                // the smoothed positions, heights and sizes, and what is made of them (float32 here, float64 in numpy)
                const specs = { x: ['sqrt'], y: ['sqrt'], zc: [], f: ['pow'], W: ['pow'], H: ['pow'], d: ['pow'], zf: ['pow'],
                    fill: ['sqrt'], moraine: [], floor_f: ['pow'], rise_f: [] };
                let allOk = true;
                for (const [k, uses] of Object.entries(specs)) {
                    const g = floats(hc[k], arr(c, k), { uses, scale: k === 'zf' || k === 'fill' ? 4000 : undefined });
                    gr[k] = { over: g.over, err: g.err, ok: g.ok };
                    if (!g.ok) allOk = false;
                }
                row[`centrelines ${which}`] = gr;
                T.ok(`${tag}: centrelines ${which}: x, y, zc, f, W, H, d, zf, fill, moraine, floor_f, rise_f within 1e-5 of their range`,
                    allOk, Object.entries(gr).map(([k, g]) => `${k} ${sci(g.over, 1)}`).join(', '));
            }
            // the cirque plan: from these seeds at the recipe's ELA (none) and at cirque_ela_m 1800
            const upf = GL.bestDonor(recv, Ax);
            for (const [lab, pp, key] of [['the recipe\'s', params, 'cirques'], ['cirque_ela_m 1800', { ...params, cirque_ela_m: 1800.0 }, 'cirques_low']]) {
                const got = await GL.cirques(R, cl, pp, base, lv, h, upf, seed, hc);
                const wantRows = [];
                const wa = arr(c, key);
                for (let i = 0; i < wa.length / 11; i++) wantRows.push(Array.from(wa.slice(11 * i, 11 * i + 11)));
                const rc = rowsClose(got, wantRows, 1e-5);
                T.ok(`${tag}: the cirques ${which}, ${lab}: the same bowls (within the seeds' float grade)`, rc.ok, rc.detail);
            }
            upf.destroy();
            cl.dispose();
        }
        // 6. the cirque plan alone: numpy's own seeds (float64) through the port's plan code, within 1e-12
        {
            const host = { S: arr(c, 'idx').length };
            for (const k of ['idx', 'rcv', 'main', 'sid']) host[k] = Int32Array.from(arr(c, k));
            for (const k of ['head', 'cont']) host[k] = Uint8Array.from(arr(c, k));
            for (const k of ['x', 'y', 'zc', 'q', 'f', 'W', 'H', 'd', 'zf', 'fill', 'moraine', 'floor_f', 'rise_f']) host[k] = Float64Array.from(arr(c, k));
            const upb = upI(c, 'up', n);
            const got = await GL.cirques(R, { S: host.S }, { ...params, cirque_ela_m: 1800.0 }, base, lv, h, upb, seed, host);
            const wa = arr(c, 'cirques_low'), wantRows = [];
            for (let i = 0; i < wa.length / 11; i++) wantRows.push(Array.from(wa.slice(11 * i, 11 * i + 11)));
            const rc = rowsClose(got, wantRows, 1e-12);
            T.ok(`${tag}: the cirque plan on numpy's own seeds (cirque_ela_m 1800): the rows within 1e-12 relative`, rc.ok, rc.detail);
            upb.destroy();
        }
        // 7. the jump flood on numpy's own seed textures, every pass: the candidates identical to the Blender kernel's
        // own on its GPU (tests/glacial/gpu_fixtures.py), and how many differ from the twin's (numpy's float32
        // emulation of the kernel, whose pow and exp round as numpy's do: a near tie of two seeds' metrics can fall
        // the other way)
        {
            const sA = up32(c, 'seedA'), sB = up32(c, 'seedB'), sC = up32(c, 'seedC'), c0 = up32(c, 'cand0');
            const cand = GL.jumpFloodRun(R, c0, sA, sB, lv.cell, v.profile_uniforms, v.steps, 0, sC);
            const got = await R.read(cand);
            const et = exact(got, arr(c, 'cand_twin'));
            const gpu = ON_GPU?.[c.label];
            if (gpu) {
                const want = C.array(DIR, gpu.cand_gpu);
                const eg = exact(got, want);
                // where a slot differs: is it a near tie? Each slot's target in float64 (glacial.py decode_best) on
                // both lists: the same four targets within 16 float32 steps means the two kernels ranked candidates
                // whose float32 targets round to within an ulp or two of each other (pow and exp round differently in
                // the two shader compilers); a larger difference is a real one
                let real = 0, cells = 0;
                if (!eg.ok) {
                    const sA = arr(c, 'seedA'), sB = arr(c, 'seedB'), sC = arr(c, 'seedC');
                    const mp = GLT.decodeBest(got, sA, sB, sC, n, n, lv.cell, v.profile_uniforms, 0);
                    const mb = GLT.decodeBest(want, sA, sB, sC, n, n, lv.cell, v.profile_uniforms, 0);
                    const ulp = (x) => 2 ** (Math.floor(Math.log2(Math.max(Math.abs(x), 1e-30))) - 23);
                    for (let p = 0; p < n * n; p++) {
                        let differs = false, near = true;
                        for (let s = 0; s < 4; s++) {
                            if (got[4 * p + s] === want[4 * p + s]) continue;
                            differs = true;
                            const a = mp[4 * p + s], b = mb[4 * p + s];
                            if (!(a === b || Math.abs(a - b) <= 16 * ulp(Math.max(Math.abs(a), Math.abs(b))))) near = false;
                        }
                        if (differs) { cells++; if (!near) real++; }
                    }
                }
                T.ok(`${tag}: the jump flood (${v.steps.length} passes at ${n}^2) on numpy's seed textures: the candidates identical ` +
                    'to the Blender kernel\'s on its GPU, but for near ties (each differing slot\'s target in float64 within 16 float32 steps of ' +
                    'Blender\'s)', eg.ok || real === 0, `${eg.diff} of ${4 * n * n} slots differ, on ${cells} cells, ${real} of them more than ` +
                    `a near tie (from the twin's: the port ${et.diff}, Blender's GPU ${gpu.slots_differing_from_twin})`);
                results[`${tag} jump flood`] = { vs_gpu: eg.diff, cells, real, vs_twin: et.diff, gpu_vs_twin: gpu.slots_differing_from_twin };
            } else {
                T.ok(`${tag}: the jump flood (${v.steps.length} passes at ${n}^2) on numpy's seed textures: the candidates identical to the twin's ` +
                    '(no GPU candidates: tests/glacial/gpu_fixtures.py)', et.ok, `${et.diff} of ${4 * n * n} slots differ`);
            }
            for (const f of [sA, sB, sC, c0, cand]) f.destroy();
        }
        for (const f of [h, recv, filled, b, ones, Qr.Q, Ar.Q, upF, Qb, Ab]) f.destroy();
    }
}

// --------------------------------------------------------------------------------------------- synthetic ---

if (want('synthetic')) {
    const cs = (fn) => M.cases.filter((x) => x.function === fn);
    // the discharge on the dome, with and without inflow: iterations, Q, and its budget (glacial.py flux_budget)
    for (const c of cs('ice_flux_converge')) {
        const surf = up32(c, 'surf'), recv = up32(c, 'recv'), b = up32(c, 'b'), qin = up32(c, 'Q_in');
        const anyIn = arr(c, 'Q_in').some((x) => x !== 0);
        const r = await GL.iceFluxConverge(R, surf, b, c.args.cell, { recv, params: c.args.params, check: c.args.check, Qin: anyIn ? qin : null });
        const q = await R.read(r.Q);
        const g = floats(q, arr(c, 'Q'), { uses: ['pow'] });
        const bud = fluxBudget(q, arr(c, 'b'), arr(c, 'recv'), surf.h, surf.w, c.args.cell, c.args.params, anyIn ? arr(c, 'Q_in') : null);
        T.ok(`${c.label}: the discharge within 1e-5 of its range, ${c.values.iterations} iterations, the budget closes within 1e-5`,
            g.ok && r.iterations === c.values.iterations && Math.abs(bud.rel_residual) <= 1e-5,
            `worst ${sci(g.over)} of range, ${r.iterations} iterations; accumulation ${bud.accumulation.toPrecision(4)} + inflow ` +
            `${bud.inflow.toPrecision(4)} - ablation ${bud.ablation.toPrecision(4)} = outflow ${bud.outflow.toPrecision(4)} ` +
            `(residual ${sci(bud.rel_residual)}; Blender's twin ${sci(c.values.budget.rel_residual)})`);
        for (const f of [surf, recv, b, qin, r.Q]) f.destroy();
    }
    // streams, graded_fill and head_distance on the 80^2 dome's seeds
    for (const c of cs('streams')) {
        const recv = up32(c, 'recv'), A = up32(c, 'A');
        const mask = arr(c, 'mask');
        const flags = R.field(recv.h, recv.w, 1, Uint32Array.from(mask), 'u32');
        const st = await GL.streams(R, flags, recv, A);
        const S = st.S, got = {};
        const [idx, rcv, mainA, sid, fl] = await R.readAll([st.idx, st.rcv, st.main, st.sid, st.flags]);
        got.idx = exact(idx, arr(c, 'idx'), S).diff;
        got.rcv = exact(rcv, arr(c, 'rcv'), S).diff;
        got.main = exact(mainA, arr(c, 'main'), S).diff;
        got.sid = exact(sid, arr(c, 'sid'), S).diff;
        got.head = exact(Array.from(fl.slice(0, S), (x) => (x >> 1) & 1), arr(c, 'head'), S).diff;
        got.cont = exact(Array.from(fl.slice(0, S), (x) => x & 1), arr(c, 'cont'), S).diff;
        T.ok(`${c.label}: streams equal numpy's (seeds, receivers, main donors, ids, heads, links)`, S === arr(c, 'idx').length &&
            Object.values(got).every((d) => d === 0), `${S} seeds; differing ${JSON.stringify(got)}`);
        // the fill and the head distance from numpy's own per-seed values
        const x = arr(c, 'x'), y = arr(c, 'y'), zc = arr(c, 'zc'), zf = arr(c, 'zf');
        const vv = new Float32Array(st.idx.h * st.idx.w * 4), pz = new Float32Array(st.idx.h * st.idx.w * 4);
        for (let i = 0; i < S; i++) {
            vv.set([x[i], y[i], zc[i], 0], 4 * i);
            pz.set([0, 0, 0, zf[i]], 4 * i);
        }
        const Vf = R.field(st.idx.h, st.idx.w, 4, vv), Pf = R.field(st.idx.h, st.idx.w, 4, pz);
        const gf = await GL.gradedFill(R, st, Vf, Pf, c.args.grade);
        const hd = await GL.headDistance(R, st, Vf);
        const [fill, dist] = await R.readAll([gf.fill, hd.dist]);
        const g1 = floats(fill, arr(c, 'fill'), { n: S, uses: ['sqrt'], scale: 4000 }), g2 = floats(dist, arr(c, 'head_dist'), { n: S, uses: ['sqrt'] });
        T.ok(`${c.label}: graded_fill within 1e-5 of its range (${gf.sweeps} sweeps)`, g1.ok, `worst ${sci(g1.over)} of range (${sci(g1.err)} m)`);
        T.ok(`${c.label}: head_distance within 1e-5 of its range (${hd.sweeps} sweeps)`, g2.ok, `worst ${sci(g2.over)} of range (${sci(g2.err)} m)`);
        let tpw = 0;
        const tp = arr(c, 'taper');
        for (let i = 0; i < S; i++) tpw = Math.max(tpw, Math.abs(GL.headTaperFactor(arr(c, 'head_dist')[i], 300.0, 2.0) - tp[i]));
        T.ok(`${c.label}: head_taper_factor (doubles) equal to numpy's within 1e-12`, tpw <= 1e-12, `worst ${sci(tpw)}`);
        GL.disposeStreams(st);
        for (const f of [recv, A, flags, Vf, Pf, gf.fill, hd.dist]) f.destroy();
    }
    for (const c of cs('best_donor')) {
        const recv = up32(c, 'recv'), A = up32(c, 'A');
        const u = GL.bestDonor(recv, A);
        const e = exact(await R.read(u), arr(c, 'up'));
        T.ok(`${c.label}: best_donor bit for bit`, e.ok, `${e.diff} differ`);
        for (const f of [recv, A, u]) f.destroy();
    }
    for (const c of cs('drainage_receivers')) {
        const h = up32(c, 'h');
        const { recv, filled } = await GL.drainageReceivers(h, c.args.cell, null);
        const [rg, fg] = await R.readAll([recv, filled]);
        const er = exact(rg, arr(c, 'recv')), ef = exact(fg, arr(c, 'filled'));
        T.ok(`${c.label}: drainage_receivers bit for bit`, er.ok && ef.ok, `${er.diff} receivers, ${ef.diff} filled heights differ`);
        for (const f of [h, recv, filled]) f.destroy();
    }
    // wall_flutes: a smoothstep of gain 1 / 0.12 over the noise total, whose weights turn with the fall direction.
    // Blender's own flutes (refine_level and carve_level pass the GPU device) take their noise from the
    // world_noise_field kernel in float32; the fixture's numpy twin evaluates it in float64, whose difference from
    // float32 world coordinates alone moves the folded slope's flutes by 4.8e-5 of range. So the reference is
    // Blender's GPU result (tests/glacial/gpu_fixtures.py), at the float-function grade: max(1e-5 of range, 1.25 x
    // the function's rounding floor (glacial_expected.py: h and the first noise field moved by one ulp, five
    // patterns)); the distance from numpy's twin is reported beside it, for the port and for Blender's GPU alike
    for (const c of cs('wall_flutes')) {
        const lv = Level.fromDict(c.level), h = up32(c, 'h');
        const f = await GL.wallFlutes(h, lv, c.args.params, c.args.seed, R);
        const got = await R.read(f), twin = arr(c, 'flutes');
        const floor = Number(c.values?.floor ?? 0), k = Math.max(1e-5, 1.25 * floor);
        const gpu = ON_GPU?.[c.label];
        const ref = gpu ? C.array(DIR, gpu.flutes_gpu) : twin;
        const g = floats(got, ref, { k, uses: ['atan2', 'divide'] });
        const gt = floats(got, twin, { k });
        T.ok(`${c.label}: wall_flutes within max(1e-5 of range, 1.25 x its floor ${sci(floor)}) of ` +
            (gpu ? 'Blender\'s on its GPU' : 'numpy\'s twin (no GPU result: tests/glacial/gpu_fixtures.py)'), g.ok,
        `worst ${sci(g.over)} of range; from numpy's twin: the port ${sci(gt.over)}` + (gpu ? `, Blender's GPU ${sci(gpu.gpu_vs_twin_over_range)}` : ''));
        results[c.label] = { over_range: g.over, vs: gpu ? 'gpu' : 'twin', vs_twin: gt.over, gpu_vs_twin: gpu?.gpu_vs_twin_over_range ?? null, floor };
        for (const x of [h, f]) x.destroy();
    }
    for (const c of cs('lip_open')) {
        const sh = c.arrays.h.shape;
        const lv = { cell: c.args.cell, n: sh[1] };
        // a 16 x 1200 section: a plain record of fields (a level's Fields are square)
        const fields = { h: R.field(sh[0], sh[1], 1, Float32Array.from(arr(c, 'h'))),
            trough_rho: R.field(sh[0], sh[1], 1, Float32Array.from(arr(c, 'rho'))) };
        const h0 = fields.h;
        const r = await GL.lipOpen(fields, lv, c.args.radius_m, null);
        const g = floats(await R.read(fields.h), arr(c, 'h1'), { k: 1e-5, uses: ['arithmetic'] });
        let wantDrop = 0;
        for (const x of arr(c, 'drop')) wantDrop = Math.max(wantDrop, x);
        T.ok(`${c.label}: lip_open within 1e-5 of the range of numpy's (largest drop ${wantDrop.toFixed(2)} m)`, g.ok &&
            Math.abs(r.rim - wantDrop) <= 1e-3 * Math.max(1, wantDrop), `worst ${sci(g.over)} of range, drop ${r.rim.toFixed(3)} m`);
        for (const f of new Set([h0, fields.h, fields.trough_rho])) f.destroy();
    }
    for (const c of cs('sharpen_walls')) {
        const sh = c.arrays.h.shape;
        const fields = new Fields({ n: sh[0], toString: () => 'sharpen' }, null, R);
        for (const k of ['h', 'bed', 'trough_rho', 'trough_zf', 'trough_H', 'trough_ff', 'trough_fill', 'trough_rise', 'trough_sharp', 'carve']) {
            fields[k] = R.field(sh[0], sh[1], 1, Float32Array.from(arr(c, `in_${k}`)));
        }
        const pw = up32(c, 'pin_w');
        const mx = await GL.sharpenWalls(fields, null, c.args.params, pw);
        const [hh, bb] = await R.readAll([fields.h, fields.bed]);
        const g1 = floats(hh, arr(c, 'h'), { k: 1e-5, uses: ['pow', 'divide'] }), g2 = floats(bb, arr(c, 'bed'), { k: 1e-5, uses: ['pow', 'divide'] });
        T.ok(`${c.label}: sharpen_walls' h and bed within 1e-5 of their range (largest change ${mx.toFixed(1)} m, numpy ` +
            `${c.values.sharpened_max_m.toFixed(1)})`, g1.ok && g2.ok && Math.abs(mx - c.values.sharpened_max_m) <= 1e-4 * Math.max(1, mx),
        `h ${sci(g1.over)}, bed ${sci(g2.over)} of range`);
        fields.dispose();
        pw.destroy();
    }
    for (const c of cs('carve_level')) {
        const lv = Level.fromDict(c.level);
        const h = up32(c, 'h_in');
        const fields = new Fields(lv, { h, bed: R.field(lv.n, lv.n, 1, Float32Array.from(arr(c, 'h_in'))) }, R);
        const ctx = new RUN.StageContext({ plan: [lv], index: 0, level: lv, prepass: null, fresh: false, role: 'grow',
            pins: FL.edgePins(R, lv.n, fields.h), shared: {}, seed: 1, base_elevation_m: 0.0, device: R, log: () => {} });
        const rec = await GL.carveLevel(fields, lv, c.args.params, c.args.seed, ctx, R);
        const want = c.values.record, fl = c.values.floor ?? {};
        const gpu = ON_GPU?.[c.label];
        const worst = {}, vsTwin = {};
        let ok = true;
        // an evolving op (the walls' 64 threshold passes): plan 5.3's stage grade, max(1e-4 of range, 1.25 x the carve's
        // own floor, measured by glacial_expected.py as the stage floors are, five patterns), against the Blender
        // carve on its GPU (tests/glacial/gpu_fixtures.py: the kernels' float32 rounding as a Blender run has it), or
        // the twin device's when that is not there; the distance from the twin's is reported beside
        for (const [k, a] of Object.entries(c.arrays)) {
            if (!k.startsWith('out_')) continue;
            const name = k.slice(4);
            if (!(name in fields)) { worst[name] = 'missing'; ok = false; continue; }
            const got = await R.read(fields[name]);
            const ref = gpu?.fields?.[name] ? C.array(DIR, gpu.fields[name]) : arr(c, k);
            const g = floats(got, ref, { k: Math.max(1e-4, 1.25 * (fl[name] ?? 0)), uses: ['pow', 'exp', 'sqrt', 'divide'] });
            worst[name] = sci(g.over, 1);
            vsTwin[name] = sci(floats(got, arr(c, k)).over, 1);
            if (!g.ok) ok = false;
        }
        results[c.label] = { worst, vs: gpu ? 'gpu' : 'twin', vs_twin: vsTwin, gpu_vs_twin: gpu?.gpu_vs_twin_over_range ?? null, floor: fl };
        const ref = gpu ? gpu.record : want;
        T.ok(`${c.label}: every field within max(1e-4 of range, 1.25 x its floor) of the ${gpu ? 'Blender carve\'s on its GPU' : 'twin carve\'s'}; ` +
            `seeds ${rec.seeds} (Blender ${ref.seeds}), streams ${rec.streams} (${ref.streams}), steps ${JSON.stringify(rec.jfa_steps)} ` +
            `(${JSON.stringify(ref.jfa_steps)})`,
        ok && rec.seeds === ref.seeds && rec.streams === ref.streams && JSON.stringify(rec.jfa_steps) === JSON.stringify(ref.jfa_steps),
        JSON.stringify(worst) + (gpu ? `; from the twin's: the port ${JSON.stringify(vsTwin)}, Blender's GPU ` +
            JSON.stringify(Object.fromEntries(Object.entries(gpu.gpu_vs_twin_over_range).map(([k, v]) => [k, sci(v, 1)]))) : ''));
        fields.dispose();
    }
    for (const c of cs('valley_uplift')) {
        const lv = Level.fromDict(c.level);
        const u = GL.upliftShape(R, c.args.shape, lv, c.args.seed);
        const g = floats(await R.read(u), arr(c, 'u'), { k: 1e-5, uses: ['exp', 'sqrt', 'divide', 'sin', 'cos'] });
        T.ok(`${c.label}: the horseshoe uplift within 1e-5 of its range of numpy's (float64 noise)`, g.ok, `worst ${sci(g.over)} of range`);
        u.destroy();
        let RV = null;
        try { RV = await import('../../solvers/rivers.js'); } catch (_e) { /* not in the checkout yet */ }
        if (!RV) {
            T.ok(`${c.label}: the trunk river (needs solvers/rivers.js, the layered-rock and rivers package's): skipped`, true, 'not in the checkout');
            continue;
        }
        const top = lv;
        const course = await GL.trunkCourse(c.args.shape, [top.x0, top.y0, top.side], c.args.seed);
        const gp = floats(course.points.flat(), arr(c, 'points'), { k: 1e-12, double: true }), gb = floats(course.bed, arr(c, 'bed'), { k: 1e-12, double: true });
        T.ok(`${c.label}: the trunk course (points, bed) within 1e-12 of numpy's`, gp.ok && gb.ok, `points ${sci(gp.over)}, bed ${sci(gb.over)}`);
        const base = FL.edgePins(R, lv.n, R.field(lv.n, lv.n, 1));
        const [pins, m] = await GL.trunkPins(R, course, lv, base);
        const [mw, ph] = await R.readAll([m, pins.pin_h]);
        const em = exact(mw, Array.from(arr(c, 'trunk'), Number));
        const gph = floats(ph, arr(c, 'pin_h'), { k: 1e-6 });
        T.ok(`${c.label}: the trunk's channel cells and their pinned bed`, em.ok && gph.ok, `${em.diff} channel cells differ, bed ${sci(gph.over)} of range`);
    }
}

/** glacial.py flux_budget in doubles (a check): accumulation, realised ablation, inflow, outflow, the residual. */
function fluxBudget(Q, b, recv, ny, nx, cell, params, Qin) {
    const p = (k) => GL._p(params, k);
    const qin = new Float64Array(ny * nx);
    if (Qin) for (let i = 0; i < qin.length; i++) qin[i] = Qin[i];
    const hasOut = new Uint8Array(ny * nx);
    const OFF = [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]];
    for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
            const k = recv[j * nx + i];
            if (k < 0) continue;
            const [di, dj] = OFF[k];
            const i2 = i + di, j2 = j + dj;
            if (i2 < 0 || j2 < 0 || i2 >= nx || j2 >= ny) continue;
            qin[j2 * nx + i2] += Q[j * nx + i];
            hasOut[j * nx + i] = 1;
        }
    }
    let acc = 0, abl = 0, out = 0, inflow = 0;
    for (let c = 0; c < ny * nx; c++) {
        const Wd = Math.min(Math.max(2.0 * p('ice_width_m') * (Math.max(qin[c], 0) / p('ice_width_q')) ** p('ice_width_exp'), cell),
            Math.max(p('ice_width_max_m'), cell));
        const a = b[c] >= 0 ? b[c] * cell * cell : b[c] * cell * Wd;
        if (a > 0) acc += a;
        if (a < 0) abl += Math.min(-a, qin[c]);
        if (!hasOut[c]) out += Q[c];
        if (Qin) inflow += Qin[c];
    }
    const resid = acc + inflow - abl - out;
    return { accumulation: acc, inflow, ablation: abl, outflow: out, residual: resid, rel_residual: resid / Math.max(acc + inflow, 1e-30) };
}

const code = finish(T, 'functions_test', { results });
G.shutdown();
Deno.exit(code);
