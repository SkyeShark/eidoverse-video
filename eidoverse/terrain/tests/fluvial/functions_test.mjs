// The fluvial package's GPU replacements of numpy code against the numpy functions themselves (PORT_PLAN.md 5.1
// "function fixtures", 5.3 "function" grades), on the cases tests/fluvial/fluvial_expected.py made with the Blender
// edition's own Python: erodibility (roughness, k_breakup at scales a 2 m level resolves, k_contrast, faults with
// wander and length), fault_zones, threshold (noise, breakup, outcrops, the gain below the main level),
// composite_uplift and composite_start (a shape with a cut background and a tilt; a ridged background alone),
// edge_pins with a sea, _sea_flat with flatten areas, the lock's offset_block_means (blocks 2-32 at their four
// offsets), and the driver's numbers (diffusivity, lock_block, creep_substeps, soil_convexity, soft_cap).
//
//     <Blender's python> -I eidoverse/terrain/tests/fluvial/fluvial_expected.py
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/functions_test.mjs
//
// Grades: the float functions within 1e-5 of the output's range (plan 5.3; numpy evaluates them in float64 from its
// own world noise, the port in float32 from the GPU's, which P2 holds to 9.2e-7 of range), with the rounding floor of
// the built-ins they lean on (tests/parity/_common.mjs); pins and the rigid mask exact; the lock's targets bit for bit
// (numpy's float64 block means rounded to float32; a block numpy's summed-area table rounds the other way across a
// float32 tie is counted, and none is allowed off by more than one float32 step); the numbers within 1e-12 relative.
// JavaScript per cell here is test code. Writes tests/out/fluvial/functions_test.json.

import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import * as FL from '../../solvers/fluvial.js';
import * as HS from '../../solvers/hillslope.js';
import * as C from '../parity/_common.mjs';

const W = C.W;
const DIR = Deno.args[0] ?? `${W.out('fluvial')}/fixtures`;
const M = C.readJson(`${DIR}/manifest.json`);
const T = new C.Checks('fluvial: the GPU replacements of numpy code against the numpy functions');
if (!M) {
    console.log(`[skip] no fixtures in ${DIR}: make them with <Blender's python> -I eidoverse/terrain/tests/fluvial/fluvial_expected.py`);
    Deno.exit(0);
}
const R = await G.init();
const load = (a) => C.array(DIR, a);
const f32 = (a) => (a instanceof Float32Array ? a : Float32Array.from(a));
const results = [];

function grade(got, want, uses = ['exp']) {
    return C.gradeArray(got, want, { k: 1e-5, uses });
}

for (const c of M.cases) {
    const lv = Level.fromDict(c.level);
    const a = c.args;
    let got = {}, own = [];
    const field = (arr) => { const f = R.field(lv.n, lv.n, 1, f32(arr)); own.push(f); return f; };
    switch (c.function) {
        case 'erodibility': got.K = FL.erodibility(lv, a.params, a.seed, R); break;
        case 'fault_zones': got.F = FL.faultZones(a.faults, lv, a.seed, R); break;
        case 'threshold': got.Sc = FL.threshold(lv, a.params, a.seed, R, a.below_main); break;
        case 'composite_uplift': got.u = FL.compositeUplift(a.params, lv, a.seed, R); break;
        case 'composite_start': {
            // the start of Blender's own uplift (uploaded), so the comparison is of composite_start alone
            const prev = M.cases[M.cases.indexOf(c) - 1];
            const u = field(load(prev.outputs.u));
            got.h = FL.compositeStart(a.params, u, lv, a.seed, R, a.height_m, a.roughness, a.peak);
            break;
        }
        case 'edge_pins': {
            const p = FL.edgePins(R, lv.n, field(load(a.h)), a.sea_level);
            got = { pin_w: p.pin_w, pin_h: p.pin_h };
            own.push(p.A_in, p.qs_in);
            break;
        }
        case 'sea_flat': {
            const ctx = new FL.StageContext({ plan: [lv], index: 0, level: lv, sea_level: a.sea_level, flatten: a.flatten });
            const rig = await FL.seaFlat({ h: field(load(a.h)) }, ctx, lv, R);
            got.rigid = rig ?? R.field(lv.n, lv.n, 1);
            break;
        }
        case 'offset_block_means': {
            const h = R.field(lv.n, lv.n, 1, f32(load(a.h)));
            own.push(h);
            got.tgt = FL.offsetBlockMeans(R, h, a.b, a.off, a.shape);
            break;
        }
        default: throw new Error(`no port function for ${c.function}`);
    }
    const row = { label: c.label, ok: true, outputs: {} };
    for (const [name, spec] of Object.entries(c.outputs)) {
        const want = load(spec), g = await R.read(got[name]);
        if (c.function === 'offset_block_means') {
            const w32 = f32(want);
            let diff = 0, worstSteps = 0;
            for (let i = 0; i < w32.length; i++) {
                if (g[i] !== w32[i]) {
                    diff++;
                    worstSteps = Math.max(worstSteps, Math.abs(g[i] - w32[i]) / C.ulp32(w32[i]));
                }
            }
            row.outputs[name] = { blocks: w32.length, differ: diff, worst_steps: worstSteps };
            row.ok = row.ok && worstSteps <= 1.0 && diff <= Math.max(1, Math.ceil(0.01 * w32.length));
        } else if (['edge_pins', 'sea_flat'].includes(c.function)) {
            let diff = 0;
            for (let i = 0; i < want.length; i++) if (g[i] !== Math.fround(want[i])) diff++;
            row.outputs[name] = { cells: want.length, differ: diff };
            row.ok = row.ok && diff === 0;
        } else {
            const r = grade(g, want, c.function === 'threshold' ? ['exp', 'log'] : ['exp']);
            row.outputs[name] = { err_over_range: r.over, ok: r.ok, range: r.range };
            row.ok = row.ok && r.ok;
        }
        got[name].destroy();
    }
    for (const f of own) if (!f.destroyed) f.destroy();
    results.push(row);
    T.ok(`${c.label}`, row.ok, JSON.stringify(row.outputs));
}

// the driver's numbers
const rel = (x, y) => Math.abs(x - y) / Math.max(Math.abs(y), 1e-300);
const N = M.numbers;
for (const [p, c, d, m, want] of N.diffusivity) {
    const got = FL.diffusivity(p, c, d, m);
    T.ok(`diffusivity(${JSON.stringify(p)}, cell ${c}, depth ${d}) = [D, spacing]`, rel(got[0], want[0]) <= 1e-12 && rel(got[1], want[1]) <= 1e-12,
        `${got} / ${want}`);
}
for (const [t, c, n, f, want] of N.lock_block) T.ok(`lock_block(${t}, ${c}, ${n}, ${f}) = ${want}`, FL.lockBlock(t, c, n, f) === want, `${FL.lockBlock(t, c, n, f)}`);
for (const [dt, c, D, cap, ms, want] of N.creep_substeps) {
    const got = FL.creepSubsteps(dt, c, D, cap, ms);
    T.ok(`creep_substeps(${dt}, ${c}, ${D}) = ${JSON.stringify(want)}`, got[0] === want[0] && rel(got[1], want[1]) <= 1e-12, JSON.stringify(got));
}
for (const [r, s, want] of N.soil_convexity) T.ok(`soil_convexity(${r}, ${s})`, rel(HS.soilConvexity(r, s), want) <= 1e-12, `${HS.soilConvexity(r, s)}`);
for (const [r, c, want] of N.soft_cap) T.ok(`soft_cap(${r}, ${c})`, rel(HS.softCap(r, c), want) <= 1e-12 || HS.softCap(r, c) === want, `${HS.softCap(r, c)}`);

Deno.writeTextFileSync(`${W.out('fluvial')}/functions_test.json`, JSON.stringify({ test: T.title, date: new Date().toISOString(),
    fixtures: DIR, versions: M.versions, results, rows: T.rows }, null, 1));
console.log(`${T.rows.filter((r) => r.passed).length} of ${T.rows.length} checks pass`);
G.shutdown();
Deno.exit(T.rows.every((r) => r.passed) ? 0 : 1);
