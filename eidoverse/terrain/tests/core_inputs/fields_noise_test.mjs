// core/grid.js, fields.js, world_noise.js, compose.js and expr.js's GPU evaluation against the Blender edition's own
// functions (PORT_PLAN.md 8.2, P2), on the inputs core_inputs_expected.py recorded with Blender's Python:
//   resampling (upsample2 in every kind, crop_upsample2 at the edges, box_down, resample_box at integer and other
//   ratios) within float32 rounding: the analytic bound of a float32 evaluation of the stencil, 13.5 ulp of the
//   largest input (the plan's 7.3 bound for the same 4 x 4 Catmull-Rom stencil), measured in ulp
//   the border ramp, edge distance and the derivatives (np.gradient, slope, aspect) within 1e-5 of the range
//   Fields.inherit along a plan and a pre-pass, its rules, thickness bit for bit
//   world noise (sums, products, warps, periodic tiles, 40 and 200 km out, a displacement) within 1e-6 of the range
//   of numpy's float64 field(), or, where the Blender edition's own GLSL kernel (field_gpu, run by
//   blender_field_gpu.py) is further than that from float64 on the same case, within 1.25 x its error; the term
//   tables, lattice offsets and snaps exact
//   every shape and stamp, uplift of every kind, start_surface, smooth min / max, flatten weight / mask / exact
//   within 1e-5 of the range; the hard edges and resolve_flat_heights' medians exact
//   expressions over fields within 1e-6 of the range of numpy's float64 values
//
//     <Blender's python> -I eidoverse/terrain/tests/core_inputs/core_inputs_expected.py
//     $EIDO_GPU_WRAP deno run --no-config --no-lock --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/core_inputs/fields_noise_test.mjs [fixtures]

import * as G from '../../core/gpu.js';
import * as Gd from '../../core/grid.js';
import { Fields } from '../../core/fields.js';
import * as N from '../../core/world_noise.js';
import * as C from '../../core/compose.js';
import * as L from '../../core/levels.js';
import { parse } from '../../core/expr.js';
import { defaultRng } from '../../core/np_random.js';
import { Checks, bitsEqual, finish, fixtures, loadBin, manifest, maxErr, sameJson, ulp32 } from './_common.mjs';

const T = new Checks('core_inputs/fields_noise');
const FIX = fixtures();
if (!FIX) Deno.exit(0);
const M = manifest(FIX);
Object.assign(T.extra, { numpy: M.numpy, python: M.python, blender_commit: M.blender_commit });
const R = await G.init();
T.extra.adapter = R.info?.description ?? null;

const arr = (a) => loadBin(FIX, a);
const f32 = (a) => (a instanceof Float32Array ? a : Float32Array.from(a));
const up = (a) => R.field(a.shape[0], a.shape[1], 1, f32(arr(a)));
const read = async (f, keep = false) => {
    const v = await R.read(f);
    if (!keep) f.destroy();
    return v;
};
const fmt = (x) => (x === 0 ? '0' : Math.abs(x) < 1e-3 || Math.abs(x) >= 1e4 ? x.toExponential(2) : x.toFixed(4));
const maxAbs = (a) => a.reduce((m, v) => Math.max(m, Math.abs(v)), 0);
// the worst error in ulp of the largest |input|
const ulps = (got, want, input) => maxErr(got, want).abs / ulp32(maxAbs(input));

// a grade over cases: the worst relative error and where
function grade(name, rows, tol, unit = 'of the range') {
    const worst = rows.reduce((w, r) => (r.err > w.err ? r : w), { err: -1 });
    const bad = rows.filter((r) => !(r.err <= tol));
    T.ok(`${name}: ${rows.length - bad.length} of ${rows.length} within ${tol} ${unit}`, !bad.length,
        `worst ${fmt(worst.err)} (${worst.label})` + (bad.length ? `; failing: ${bad.slice(0, 3).map((r) => `${r.label} ${fmt(r.err)}`).join(', ')}` : ''));
    return worst.err;
}


// --------------------------------------------------------------------------------------------------- grid ---

const GI = M.grid.inputs;
const inputs = Object.fromEntries(Object.entries(GI).map(([k, a]) => [k, { a, data: arr(a) }]));
{
    const rows = [], rows32 = [];
    for (const c of M.grid.up) {
        const src = up(inputs[c.input].a);
        const got = await read(Gd.upsample2(src, c.kind));
        src.destroy();
        const want64 = arr(c.want64), want = arr(c.want);
        rows.push({ label: `${c.input} ${c.kind}`, err: ulps(got, want64, inputs[c.input].data) });
        rows32.push({ label: `${c.input} ${c.kind}`, err: ulps(got, want, inputs[c.input].data) });
    }
    T.extra.upsample_ulps = grade('upsample2 against numpy float64 (catmull, bilinear, nearest)', rows, 13.5, 'ulp of the largest input');
    grade('upsample2 against Blender\'s float32 result', rows32, 13.5, 'ulp of the largest input');
    const crop = [];
    for (const c of M.grid.crop) {
        const src = up(inputs[c.input].a);
        const got = await read(Gd.cropUpsample2(src, c.i0, c.j0, c.m, c.kind, c.mj));
        src.destroy();
        crop.push({ label: `${c.input} (${c.i0}, ${c.j0}) m ${c.m} mj ${c.mj} ${c.kind}`, err: ulps(got, arr(c.want), inputs[c.input].data) });
    }
    grade('crop_upsample2 (windows at the edges, negative starts, mj != m)', crop, 13.5, 'ulp of the largest input');
    const box = [];
    for (const c of M.grid.box) {
        const src = up(inputs[c.input].a);
        const got = await read(Gd.boxDown(src, c.f));
        src.destroy();
        box.push({ label: `${c.input} f ${c.f}`, err: ulps(got, arr(c.want), inputs[c.input].data) });
    }
    grade('box_down (f = 2, 4, 8)', box, 2 * 8, 'ulp of the largest input');
    const rs = [];
    for (const c of M.grid.resample) {
        const src = up(inputs[c.input].a);
        const nOut = c.n_out === null ? null : c.n_out;
        const out = Gd.resampleBox(src, c.src, c.dst, nOut);
        const got = await read(out, true);
        const want = arr(c.want);
        const shapeOk = out.h === c.want.shape[0] && out.w === c.want.shape[1];
        out.destroy();
        src.destroy();
        rs.push({ label: `${c.input} ${c.src} -> ${c.dst} m${nOut !== null ? ` n_out ${JSON.stringify(nOut)}` : ''}${shapeOk ? '' : ' WRONG SHAPE'}`,
            err: shapeOk ? ulps(got, want, inputs[c.input].data) : Infinity });
    }
    grade('resample_box (ratios 1, 2, 2.5, 3.7, a default and given n_out)', rs, 16, 'ulp of the largest input');
    const g = M.grid.bilinear;
    const want = g.want;
    const got = Gd.sampleBilinear(inputs.gw.data, GI.gw.shape, g.x0, g.y0, g.cell, g.x, g.y);
    T.ok(`sample_bilinear (per query, doubles): ${got.length} points incl. outside the grid, bit for bit`,
        got.every((v, i) => Object.is(v, want[i]) || v === want[i]), `worst ${fmt(maxErr(got, want).abs)}`);
    // the GPU form at a window's cells, against the per-query form at the same points
    {
        const src = up(GI.gw);
        const win = { x0: -9.0, y0: 5.5, cell: 2.25, h: 70, w: 60 };
        const gpu = await read(Gd.sampleWindow(src, { x0: g.x0, y0: g.y0, cell: g.cell }, win));
        src.destroy();
        const xs = [], ys = [];
        for (let j = 0; j < win.h; j++) for (let i = 0; i < win.w; i++) {
            xs.push(win.x0 + (i + 0.5) * win.cell);
            ys.push(win.y0 + (j + 0.5) * win.cell);
        }
        const host = Gd.sampleBilinear(inputs.gw.data, GI.gw.shape, g.x0, g.y0, g.cell, xs, ys);
        const e = maxErr(gpu, host);
        T.ok('sampleWindow (the GPU sample_bilinear at a window\'s cells) within 1e-5 of the range of the per-query values',
            e.rel <= 1e-5, `${fmt(e.rel)} of the range`);
    }
    const ramp = [];
    for (const c of M.grid.ramp) {
        const got = await read(Gd.borderRamp(R, c.n, c.band, c.kind));
        ramp.push({ label: `${JSON.stringify(c.n)} band ${c.band} ${c.kind}`, err: maxErr(got, arr(c.want), 1).abs });
    }
    grade('border_ramp (smooth, linear, non-square, a band wider than the window)', ramp, 2 ** -23, '(absolute; 1 ulp of 1)');
    let edges = 0;
    for (const c of M.grid.edge) {
        const got = await read(Gd.edgeDistance(R, c.n));
        const want = arr(c.want);
        if (got.every((v, i) => v === want[i])) edges++;
    }
    T.ok(`edge_distance exact on ${edges} of ${M.grid.edge.length} shapes`, edges === M.grid.edge.length);
    const der = [];
    for (const c of M.grid.deriv) {
        const src = up(c.data);
        const { gx, gy } = Gd.gradient(src, c.cell);
        const [ax, ay] = [await read(gx), await read(gy)];
        const sl = await read(Gd.slopeDeg(src, c.cell));
        const asp = await read(Gd.aspectDeg(src, c.cell));
        src.destroy();
        const wx = arr(c.gx), wy = arr(c.gy), ws = arr(c.slope), wa = arr(c.aspect);
        const scale = Math.max(maxAbs(wx), maxAbs(wy), 1e-30);
        der.push({ label: `${c.input} gx`, err: maxErr(ax, wx, scale).rel }, { label: `${c.input} gy`, err: maxErr(ay, wy, scale).rel });
        der.push({ label: `${c.input} slope`, err: maxErr(sl, ws, 90).rel });
        // aspect: the angle between the two directions, where the slope is not flat (aspect is undefined there)
        let ea = 0;
        for (let i = 0; i < wa.length; i++) {
            if (ws[i] < 1e-3) continue;
            const d = Math.abs(asp[i] - wa[i]) % 360;
            ea = Math.max(ea, Math.min(d, 360 - d));
        }
        der.push({ label: `${c.input} aspect`, err: ea / 360 });
    }
    grade('gradient, slope_deg, aspect_deg (np.gradient\'s central and one-sided differences)', der, 1e-5, 'of the range (gx, gy: of their largest; degrees: of 90 or 360)');
    {
        const src = up(M.grid.north_up.data);
        const got = await read(Gd.fromNorthUp(src));
        src.destroy();
        T.ok('from_north_up bit for bit', bitsEqual(got, arr(M.grid.north_up.want)));
    }
    const S = M.grid.scalars;
    T.ok('tan_deg, deg_of_tan and index_of (doubles) within 1e-12 relative of numpy',
        S.tan_deg.every(([d, t]) => Math.abs(Gd.tanDeg(d) - t) <= 1e-12 * Math.max(1, Math.abs(t))) &&
        S.deg_of_tan.every(([t, d]) => Math.abs(Gd.degOfTan(t) - d) <= 1e-12 * Math.max(1, Math.abs(d))) &&
        S.index_of.every(([x, y, w]) => Gd.indexOf(x, y, -12.0, 3.0, 5.0).every((v, i) => v === w[i])));
}


// ------------------------------------------------------------------------------------------------- fields ---

{
    const F = M.fields;
    const plan = F.plan.map((d) => L.Level.fromDict(d));
    const start = {};
    for (const [k, a] of Object.entries(F.start)) start[k] = up(a);
    let f = new Fields(plan[0], start, R);
    const rows = [];
    let names = true;
    for (const lv of F.levels) {
        const child = f.inherit(plan[lv.index]);
        names = names && sameJson([...child.names()].sort(), lv.names);
        for (const k of lv.names) {
            const got = await R.read(child[k]);
            rows.push({ label: `level ${lv.index} ${k}`, err: ulps(got, arr(lv[k]), arr(F.start[k])) });
        }
        f.dispose();
        f = child;
    }
    f.dispose();
    T.ok('Fields.inherit carries h, bed (Catmull-Rom), A, wear (bilinear) and skips U and pin_w at every level', names);
    grade(`Fields.inherit along a ${plan.length}-level plan`, rows, 13.5, 'ulp of the start field\'s largest value');
    const f0 = new Fields(plan[0], Object.fromEntries(Object.entries(F.start).map(([k, a]) => [k, up(a)])), R);
    const g = f0.inherit(plan[1], { rules: { A: 'nearest', wear: 'skip', U: 'bilinear' }, names: ['h', 'A', 'wear', 'U'] });
    const ok = sameJson([...g.names()].sort(), F.rules.names);
    const rr = [];
    for (const k of F.rules.names) rr.push({ label: k, err: ulps(await R.read(g[k]), arr(F.rules[k]), arr(F.start[k])) });
    grade('Fields.inherit with rules (nearest, skip, bilinear for U) and names', rr, 13.5, 'ulp of the input\'s largest value');
    T.ok('Fields.inherit rules and names select exactly Blender\'s fields', ok, `${[...g.names()].sort()} vs ${F.rules.names}`);
    g.dispose();
    const th = await read(f0.thickness());
    T.ok('Fields.thickness (h - bed) bit for bit', bitsEqual(th, arr(F.thickness)));
    let msg = '';
    try {
        new Fields(plan[1], { h: R.field(5, 5, 1) }, R);
    } catch (e) {
        msg = e.message;
    }
    T.ok('Fields refuses a field of the wrong shape, naming it', /shape \(5, 5\)/.test(msg) && msg.includes("'h'"), msg);
    let msg2 = '';
    try {
        f0.inherit(plan[2]);
    } catch (e) {
        msg2 = `${e.name}: ${e.message}`;
    }
    T.ok('Fields.inherit refuses a level that is not its child, as Blender', msg2.startsWith('ValueError: inherit: the child cell'), msg2);
    // the pre-pass: the same window at twice the cells
    const P = F.prepass;
    const pre = L.Level.fromDict(P.level);
    const p0 = new Fields(pre, { h: up(P.start_h), qs: up(P.start_qs) }, R);
    const upd = p0.inherit(plan[0].withCells(128));
    const eh = ulps(await R.read(upd.h), arr(P.h), arr(P.start_h)), eq = ulps(await R.read(upd.qs), arr(P.qs), arr(P.start_qs));
    T.ok('Fields.inherit of a pre-pass (the same window, twice the cells) within 13.5 ulp', eh <= 13.5 && eq <= 13.5, `h ${fmt(eh)}, qs ${fmt(eq)} ulp`);
    // a Fields acts as a dict: keys, in, delete, set by property, numbers filled on the GPU
    const d = new Fields(plan[1], null, R);
    d.h = 3.0;
    d.ensure('h', 9.0);
    d.bed = 1.0;
    const tk = await read(d.thickness());
    const keys = Object.keys(d).join(',');
    delete d.bed;
    T.ok('Fields as a dict: f.h = 3 fills on the GPU, ensure keeps it, keys, delete, thickness', tk.every((v) => v === 2) &&
        keys === 'h,bed' && !('bed' in d) && 'h' in d, `keys ${keys}`);
    d.dispose();
    p0.dispose();
    upd.dispose();
    f0.dispose();
}


// --------------------------------------------------------------------------------------------------- noise ---

{
    const NZ = M.noise;
    const win = (n) => {
        const [x0, y0, cell, h, w] = NZ.windows[n];
        return { x0, y0, cell, h, w };
    };
    // the Blender edition's own GPU path (field_gpu's GLSL) on the same cases, when blender_field_gpu.py has run
    let BG = null;
    try {
        BG = JSON.parse(Deno.readTextFileSync(new URL('blender_gpu/manifest.json', FIX)));
    } catch (_e) { /* not run */ }
    const rows = [], rowsBlender = [], rowsVsBlender = [];
    let within = 0, asBlender = 0;
    for (const [k, c] of NZ.cases.entries()) {
        const w = win(c.window);
        let disp = null;
        if (c.disp) {
            const dx = arr(c.disp[0]), dy = arr(c.disp[1]);
            const d = new Float32Array(2 * dx.length);
            for (let i = 0; i < dx.length; i++) {                  // test data: the fixture's displacement, interleaved
                d[2 * i] = dx[i];
                d[2 * i + 1] = dy[i];
            }
            disp = R.field(w.h, w.w, 2, d);
        }
        const got = await read(N.fieldGpu(R, c.spec, w, c.seed, { disp }));
        if (disp) disp.destroy();
        const want = arr(c.want);
        const e = maxErr(got, want);
        const label = `${c.label} @ ${c.window} seed ${c.seed}`;
        const err = e.range > 0 ? e.rel : e.abs;
        rows.push({ label, err });
        if (BG) {
            const b = BG.cases[k];
            const bl = loadBin(new URL('blender_gpu/', FIX), { file: b.file, shape: b.shape, dtype: 'f32' });
            const eb = maxErr(bl, want), ev = maxErr(got, bl, e.range || 1);
            const errB = eb.range > 0 ? eb.rel : eb.abs;
            rowsBlender.push({ label, err: errB });
            rowsVsBlender.push({ label, err: ev.rel });
            if (err > 1e-6 && err <= 1.25 * errB) asBlender++;
        }
        if (err <= 1e-6) within++;
    }
    T.extra.noise = { within_1e6: within, cases: NZ.cases.length, no_worse_than_blender: asBlender };
    const worstPort = Math.max(...rows.map((r) => r.err));
    if (BG) {
        const worstB = Math.max(...rowsBlender.map((r) => r.err));
        const passing = rows.filter((r, i) => r.err <= 1e-6 || r.err <= 1.25 * rowsBlender[i].err).length;
        T.ok(`world noise (fieldGpu) against numpy's float64 field(), every kind, sums, products, warps, periodic, 200 km out, a ` +
            `displacement: ${passing} of ${rows.length} within 1e-6 of the range or within 1.25 x the Blender edition's own GLSL ` +
            `field_gpu error on the same case`, passing === rows.length,
            `${within} within 1e-6 of the range; worst ${fmt(worstPort)} (the GLSL's own worst ${fmt(worstB)}); ` +
            `${asBlender} where both editions' float32 kernels sit above 1e-6`);
        // a measure, not a check: two float32 evaluations of the same lattice sums, each within its own error of float64
        const wv = rowsVsBlender.reduce((w, r) => (r.err > w.err ? r : w), { err: -1 });
        T.extra.noise_vs_blender_gpu = { worst: wv.err, at: wv.label, within_1e6: rowsVsBlender.filter((r) => r.err <= 1e-6).length };
        T.extra.noise_blender_worst = worstB;
        console.log(`     the port's WGSL against Blender's GLSL field_gpu: ${T.extra.noise_vs_blender_gpu.within_1e6} of ${rows.length} ` +
            `within 1e-6 of the range, worst ${fmt(wv.err)} (${wv.label})`);
    } else {
        grade('world noise (fieldGpu) against numpy\'s float64 field() (no Blender GPU run: blender_field_gpu.py)', rows, 1e-6);
    }
    T.extra.noise_worst = worstPort;
    let same = 0;
    const bad = [];
    for (const t of NZ.terms) {
        const [terms, constant] = N.leafTerms(t.spec, t.seed, t.x0, t.y0);
        if (sameJson(terms, t.terms) && constant === t.const) same++;
        else bad.push(`${JSON.stringify(t.spec).slice(0, 60)} seed ${t.seed}: ${JSON.stringify(terms[0])} vs ${JSON.stringify(t.terms[0])}`);
    }
    T.ok(`world noise term tables (_leaf_terms) bit for bit: ${same} of ${NZ.terms.length}`, same === NZ.terms.length, bad.slice(0, 2).join(' | '));
    const off = NZ.offsets.filter(([s, o, want]) => !sameJson(N.latticeOffset(s, o), want));
    T.ok(`lattice_offset exact for ${NZ.offsets.length - off.length} of ${NZ.offsets.length} seeds and octaves (big and negative seeds too)`,
        !off.length, off.slice(0, 3).map(([s, o, w]) => `${s}/${o}: ${N.latticeOffset(s, o)} vs ${w}`).join(', '));
    T.ok('snap_wavelength and snap_freq exact', NZ.snaps.every(([w, p, v]) => N.snapWavelength(w, p) === v) &&
        NZ.snap_freq.every(([f, t, v]) => N.snapFreq(f, t) === v));
    const errOf = (fn) => {
        try {
            fn();
            return null;
        } catch (e) {
            return `${e.name}: ${e.message}`;
        }
    };
    T.ok('noise errors equal to Blender\'s (period, lacunarity, kind)',
        errOf(() => N.periodCells(8000.0, 900.0)) === NZ.period_error && errOf(() => N.octaveList(900.0, 3, 2.5, 0.5, 8000.0)) === NZ.lacunarity_error &&
        errOf(() => N.fieldGpu(R, { kind: 'perlin' }, { x0: 0, y0: 0, cell: 1, n: 8 })) === NZ.kind_error,
        `${errOf(() => N.octaveList(900.0, 3, 2.5, 0.5, 8000.0))} | ${NZ.lacunarity_error}`);
}


// ------------------------------------------------------------------------------------------------- compose ---

{
    const CM = M.compose;
    const win = (n) => {
        const [x0, y0, cell, h, w] = CM.windows[n];
        return { x0, y0, cell, h, w };
    };
    const sh = [];
    for (const c of CM.shapes) {
        const got = await read(C.shape(R, c.spec, win(c.window), c.seed));
        const e = maxErr(got, arr(c.want));
        sh.push({ label: `${c.label} seed ${c.seed}`, err: e.range > 0 ? e.rel : e.abs });
    }
    T.extra.shape_worst = grade('shape(): cone (linear, cosine, exp, crater), bowl, profile, array, field, dome, ridge, plateau, massif', sh, 1e-5);
    const ul = [];
    for (const c of CM.uplift) {
        const got = await read(C.uplift(R, c.spec, win(c.window), c.seed));
        const e = maxErr(got, arr(c.want));
        ul.push({ label: `${c.label} @ ${c.window} seed ${c.seed}`, err: e.range > 0 ? e.rel : e.abs });
    }
    T.extra.uplift_worst = grade('uplift(): every kind, spurs and peaks, warps and textures, seeds (numpy\'s float64 noise path)', ul, 1e-5);
    let draws = 0;
    for (const p of CM.plan_draws) {
        const s = p.seed + (CM.uplift.find((u) => u.label === p.label)?.spec.seed ?? 0);
        const rng = defaultRng(Math.abs(s) * 7919 + 17);
        if (p.first_draws.every((v) => rng.uniform(0, 1) === v)) draws++;
    }
    T.ok(`the spur and peak plans' numpy Generator (default_rng(|s| 7919 + 17)) draw for draw: ${draws} of ${CM.plan_draws.length}`, draws === CM.plan_draws.length);
    const st = [];
    for (const c of CM.start) {
        const kw = c.kw;
        const got = await read(await C.startSurface(R, c.spec, win(c.window), c.seed,
            { heightM: kw.height_m, roughness: kw.roughness ?? 0.4, peak: kw.peak ?? null }));
        const e = maxErr(got, arr(c.want));
        st.push({ label: `${c.label} seed ${c.seed}`, err: e.rel });
    }
    grade('start_surface (ridge, a given peak, a cone through shape())', st, 1e-5);
    const SI = CM.stamp_inputs;
    const [hh, ss, mm] = [up(SI.h), up(SI.s), up(SI.mask)];
    const sp = [];
    let exact = 0;
    for (const c of CM.stamp) {
        const got = await read(C.stamp(hh, ss, c.mode, c.width_m, c.mode === 'blend' ? mm : null));
        const want = arr(c.want);
        sp.push({ label: `${c.mode} ${c.width_m}`, err: maxErr(got, want).rel });
        if (['add', 'max', 'min'].includes(c.mode) && bitsEqual(got, want)) exact++;
    }
    grade('stamp() in every mode', sp, 1e-5);
    T.ok(`stamp add, max and min bit for bit (${exact} of 3)`, exact === 3);
    const sm = [];
    for (const c of CM.smooth) {
        sm.push({ label: `smooth_min k ${c.k}`, err: maxErr(await read(C.smoothMin(hh, ss, c.k)), arr(c.min)).rel });
        sm.push({ label: `smooth_max k ${c.k}`, err: maxErr(await read(C.smoothMax(hh, ss, c.k)), arr(c.max)).rel });
    }
    grade('smooth_min / smooth_max over fields', sm, 1e-5);
    T.ok('smoothMin / smoothMax of numbers in doubles', C.smoothMin(1, 2, 2) === 1 - 0.25 * 0.25 * 2 && C.smoothMax(1, 2, 0) === 2);
    for (const f of [hh, ss, mm]) f.destroy();
    const errOf = async (fn) => {
        try {
            await fn();
            return null;
        } catch (e) {
            return `${e.name}: ${e.message}`;
        }
    };
    T.ok('stamp errors equal to Blender\'s', (await errOf(() => C.stamp(R.field(2, 2, 1), R.field(2, 2, 1), 'mix'))) === CM.stamp_error &&
        (await errOf(() => C.stamp(R.field(2, 2, 1), R.field(2, 2, 1), 'blend'))) === CM.stamp_blend_error);

    // flatten
    const FL = CM.flatten_levels;
    const lvA = L.Level.fromDict(FL.a), lvB = L.Level.fromDict(FL.b);
    const hA = up(FL.ha), hB = up(FL.hb);
    const fw = [], fx = [];
    let masks = 0, nmask = 0, heights = 0, nheights = 0, hardOk = true;
    for (const row of CM.flatten) {
        const areas = row.areas;
        for (const [nm, lv] of [['a', lvA], ['b', lvB]]) {
            const norm = C.normaliseAreas(areas);
            norm.forEach((a, k) => {
                fw.push({ label: `${nm} area ${k} r ${a.radius} f ${a.falloff}`, area: a, lv, want: row['weight_' + nm][k] });
            });
            nmask++;
            const got = await read(C.flattenMask(R, areas, lv));
            if (bitsEqual(got, arr(row['mask_' + nm]))) masks++;
        }
        if (row.error) {
            const e = await errOf(() => C.resolveFlatHeights(areas, [[lvA, hA], [lvB, hB]]));
            nheights++;
            if (e === row.error) heights++;
            else T.extra.flatten_error = `${e} vs ${row.error}`;
            continue;
        }
        nheights++;
        const z = await C.resolveFlatHeights(areas, [[lvA, hA], [lvB, hB]]);
        if (sameJson(z, row.heights)) heights++;
        else T.extra.flatten_heights = { got: z, want: row.heights };
        for (const [nm, lv, h] of [['a', lvA, hA], ['b', lvB, hB]]) {
            const got = await read(C.flattenExact(h, lv, areas, z));
            const want = arr(row['exact_' + nm]);
            fx.push({ label: `${nm} ${areas.length} areas`, err: maxErr(got, want).rel });
        }
    }
    const fwr = [];
    for (const r of fw) {
        const got = await read(C.flattenWeight(R, r.area, r.lv));
        const want = arr(r.want);
        fwr.push({ label: r.label, err: maxErr(got, want, 1).abs });
        if (r.area.falloff <= 0 && !got.every((v, i) => v === want[i])) hardOk = false;
    }
    grade('flatten_weight (the C1 falloff, absolute)', fwr, 1e-5, '(absolute, weights 0..1)');
    T.ok('flatten_weight with no falloff exact (cells on the circle included)', hardOk);
    T.ok(`flatten_mask bit for bit: ${masks} of ${nmask} (radius plus falloff, every area)`, masks === nmask);
    T.ok(`resolve_flat_heights: ${heights} of ${nheights} area sets equal to Blender's medians (or its error)`, heights === nheights,
        JSON.stringify(T.extra.flatten_heights ?? T.extra.flatten_error ?? ''));
    grade('flatten_exact', fx, 1e-5);
    hA.destroy();
    hB.destroy();
}


// ------------------------------------------------------------------------------------------- expr on fields ---

{
    const env = {};
    for (const [k, a] of Object.entries(M.expr.env)) env[k] = up(a);
    const rows = [];
    for (const c of M.expr.cases) {
        if (!c.value) continue;
        const e = parse(c.text);
        const scalars = { a: 1, b: 2, c: 3, d: 4, e: 5 };
        const got = await read(await e.eval({ ...env, ...scalars }));
        const want = arr(c.value);
        const er = maxErr(got, want);
        rows.push({ label: c.text, err: er.range > 0 ? er.rel : er.abs / Math.max(1, maxAbs(want)) });
    }
    grade('expressions over fields (one compiled kernel each) against numpy\'s float64 values', rows, 1e-6);
    for (const f of Object.values(env)) f.destroy();
}

G.shutdown();
Deno.exit(finish(T, 'fields_noise_test.json'));
