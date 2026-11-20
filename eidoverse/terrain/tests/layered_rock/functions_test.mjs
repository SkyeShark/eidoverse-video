// The layered-rock package's GPU replacements of numpy code against the numpy functions (PORT_PLAN.md 5.1 "function
// fixtures", 5.3: the exact kind bit for bit, the float kind within 1e-5 of range): tests/layered_rock/
// layered_expected.py's cases, made by Blender's Python from solvers/strata.py and solvers/rivers.py, on the levels and
// options the draft floor runs never reach (module doc there).
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/layered_rock/functions_test.mjs
//                                                          (on a shared machine, behind $EIDO_GPU_WRAP)
//   offset, zs_field, plateau_surface, joint_field, rock_mass, rock_cores   float kind: within 1e-5 of range (with the
//              rounding floor of the built-ins each leans on; the noise is numpy's own world-noise field, the oracle the
//              port's GPU noise is held to within 1e-6 of range by the core inputs package)
//   fill_dry_basins   the filled cells' count equal, h and deposit bit for bit
//   caprock_fraction  within one cell of the window (the comparison of a float32 zs with the caprock's base)
//   river channel and pins   the channel's cells bit for bit (the near-ties decided in doubles), the arc length and
//              distance on them within 1e-5 of range, pin_w bit for bit, pin_h within 1e-5 of its range
// JavaScript per cell here is test code. Writes tests/out/layered_rock/functions_test.json.

import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import * as RV from '../../solvers/rivers.js';
import * as S from '../../solvers/strata.js';
import { C, W, finish } from './_layered.mjs';

const T = new C.Checks('layered_rock: GPU replacements against the numpy functions');
const R = await G.init();
const dir = `${W.out('layered_rock')}/fixtures`;
const M = C.readJson(`${dir}/manifest.json`);
const rows = [];
const arr = (a) => C.array(dir, a);
const f32 = (a) => Float32Array.from(arr(a));
const field = (lv, a) => R.field(lv.n, lv.n, 1, f32(a));

if (!M) {
    T.ok('function fixtures', false, '<Blender\'s python> -I eidoverse/terrain/tests/layered_rock/layered_expected.py');
} else {
    for (const c of M.cases) {
        const lv = Level.fromDict(c.level);
        const row = { label: c.label, function: c.function, ok: true, checks: {} };
        const grade = (name, got, want, opts) => {
            const g = C.gradeArray(got, want, opts);
            row.checks[name] = { ok: g.ok, over: g.over, err: g.err, tol: g.tol };
            if (!g.ok) row.ok = false;
        };
        const exact = (name, got, want) => {
            let d = 0;
            for (let i = 0; i < want.length; i++) if (got[i] !== want[i] && !(Number.isNaN(got[i]) && Number.isNaN(want[i]))) d++;
            row.checks[name] = { ok: d === 0, differ: d };
            if (d) row.ok = false;
        };
        const a = c.args;
        if (c.function === 'offset') {
            const z = S.offset(a.spec, lv, a.seed, R);
            grade('zoff', await R.read(z), arr(c.outputs.zoff), { k: 1e-5, uses: ['exp'] });
            z.destroy();
        } else if (c.function === 'zs_field') {
            const h = field(lv, c.inputs.h);
            const z = S.zsField(h, a.spec, lv, a.seed, R);
            grade('zs', await R.read(z), arr(c.outputs.zs), { k: 1e-5 });
            h.destroy();
            z.destroy();
        } else if (c.function === 'plateau_surface') {
            const h = S.plateauSurface(lv, a.params, a.seed, R, a.strata);
            grade('h', await R.read(h), arr(c.outputs.h), { k: 1e-5 });
            h.destroy();
        } else if (c.function === 'joint_field') {
            const j = S.jointField(lv, a.sets, a.seed, R);
            grade('j', await R.read(j), arr(c.outputs.j), { k: 1e-5, uses: ['exp'] });
            j.destroy();
        } else if (c.function === 'rock_mass') {
            const n = S.rockMass(lv, a.scales, a.seed, R);
            grade('n', await R.read(n), arr(c.outputs.n), { k: 1e-5 });
            n.destroy();
        } else if (c.function === 'rock_cores') {
            const k = S.rockCores(lv, a.spec, a.seed, R);
            grade('c', await R.read(k), arr(c.outputs.c), { k: 1e-5, uses: ['pow', 'exp', 'sin'] });
            k.destroy();
        } else if (c.function === 'fill_dry_basins') {
            const fields = { h: field(lv, c.inputs.h), deposit: field(lv, c.inputs.deposit) };
            const chan = a.has_keep ? field(lv, c.inputs.chan) : null;
            const n = await S.fillDryBasins(fields, chan, a.hold, R);
            row.checks.filled = { ok: n === c.values.filled, port: n, blender: c.values.filled };
            if (n !== c.values.filled) row.ok = false;
            exact('h', await R.read(fields.h), arr(c.outputs.h));
            exact('deposit', await R.read(fields.deposit), arr(c.outputs.deposit));
            for (const f of [fields.h, fields.deposit, chan]) if (f && !f.destroyed) f.destroy();
        } else if (c.function === 'caprock_fraction') {
            const h = field(lv, c.inputs.h);
            const z = S.offset(a.spec, lv, a.seed, R);
            const frac = await S.caprockFraction(h, z, lv, Level.fromDict(a.main), a.cap_zs, R);
            const main = Level.fromDict(a.main), cells = (main.n * main.cell / lv.cell) ** 2;
            const d = Math.abs(frac - c.values.frac) * cells;
            row.checks.frac = { ok: d <= 1.0 + 1e-9, port: frac, blender: c.values.frac, cells_apart: d };
            if (!(d <= 1.0 + 1e-9)) row.ok = false;
            h.destroy();
            z.destroy();
        } else if (c.function === 'river_pins' || c.function === 'river_pins_replaced_final') {
            const rv = RV.makeRiver(a.river, a.seed, a.extent);
            if (c.function === 'river_pins_replaced_final') {
                const sIn = arr(c.inputs.sIn), zg = arr(c.inputs.zg);
                const L = sIn.length;
                rv.final = (s) => {
                    const one = (x) => (x < sIn[0] ? zg[0] + a.g0 * (sIn[0] - x) : x > sIn[L - 1] ? zg[L - 1] - a.g1 * (x - sIn[L - 1])
                        : RV.npInterp(x, sIn, zg));
                    return typeof s === 'number' ? one(s) : Float64Array.from(s, one);
                };
            }
            const tl = Level.fromDict(a.top_level);
            await rv.sampleTop(tl, f32(c.inputs.top_h));
            const base = { pin_w: field(lv, c.inputs.pin_w), pin_h: field(lv, c.inputs.pin_h), A_in: R.field(lv.n, lv.n, 1),
                qs_in: R.field(lv.n, lv.n, 1) };
            const hold = a.hold ? field(lv, c.inputs.hold) : null;
            const [pins, m] = await rv.pins(lv, base, a.f, { hold });
            exact('mask', await R.read(m), Float32Array.from(arr(c.outputs.mask)));
            exact('pin_w', await R.read(pins.pin_w), arr(c.outputs.pin_w));
            const wantH = arr(c.outputs.pin_h);
            grade('pin_h', await R.read(pins.pin_h), wantH, { k: 1e-5, uses: ['pow', 'sin'] });
            if (c.outputs.s) {
                // the arc length and distance on the channel's cells: s = s_k + t L_k from the GPU's segment and parameter
                const ch = await RV.channel(lv, rv.points, rv.width_m, RV.MIN_CELLS, R);
                const [mk, kk, tt, dd] = await R.readAll([ch.mask, ch.seg, ch.t, ch.d]);
                const ws = arr(c.outputs.s), wd = arr(c.outputs.d), wm = arr(c.outputs.mask);
                const gs = new Float64Array(ws.length), gd = new Float64Array(ws.length), es = new Float64Array(ws.length), ed = new Float64Array(ws.length);
                for (let i = 0; i < ws.length; i++) {
                    if (!wm[i]) continue;
                    const k = kk[i];
                    const L = Math.hypot(rv.points[k + 1][0] - rv.points[k][0], rv.points[k + 1][1] - rv.points[k][1]);
                    gs[i] = rv.s[k] + tt[i] * L;
                    es[i] = ws[i];
                    gd[i] = dd[i];
                    ed[i] = wd[i];
                }
                grade('s on the channel', gs, es, { k: 1e-5, double: true });
                grade('distance on the channel', gd, ed, { k: 1e-5 });
                row.checks.decided_in_doubles = ch.decided;
                row.checks.cells = { ok: ch.cells === c.values.cells, port: ch.cells, blender: c.values.cells };
                if (ch.cells !== c.values.cells) row.ok = false;
                RV.releaseChannel(ch);
            }
            for (const f of [pins.pin_w, pins.pin_h, m, base.pin_w, base.pin_h, base.A_in, base.qs_in, hold]) if (f && !f.destroyed) f.destroy();
        } else {
            row.ok = false;
            row.checks.unknown = { ok: false };
        }
        rows.push(row);
        const worst = Object.entries(row.checks).map(([k, v]) => `${k} ${v.over !== undefined ? C.sci(v.over) + ' of range' : v.differ !== undefined ? v.differ + ' cells differ' : JSON.stringify(v).slice(0, 80)}`);
        console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${c.label}: ${worst.join(', ')}`);
    }
    const byFn = {};
    for (const r of rows) { const b = (byFn[r.function] ??= [0, 0]); b[1]++; if (r.ok) b[0]++; }
    for (const [fn, [ok, n]] of Object.entries(byFn)) T.ok(`${fn}: ${ok} of ${n} cases within their grades`, ok === n);
}
G.shutdown();
Deno.exit(finish(T, 'functions_test', { cases: rows }));
