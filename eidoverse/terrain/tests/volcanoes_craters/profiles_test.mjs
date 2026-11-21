// The volcanoes and craters package's profiles against numpy (PORT_PLAN.md 8.2 row P9: "profiles against numpy
// (Fuji's slopes at 0, 10, 15 km; Pike's and Wood's ratios)", "quantile per numpy 2.3.4 at volcanic.py:2865 (C6)";
// 5.3's grades), on the function fixtures volcanic_expected.py makes with Blender's Python:
//   exp_cone            expCone and expConeSlopeDeg (JavaScript doubles) at the rim, 5, 10, 15 km and the foot, for
//                       the design's Fuji numbers and the FUJI preset: 1e-12 relative (the plan grade)
//   stratovolcano       the GPU's stratovolcano (stratoPlan, evaluateStrato) along rays east and north, 25 km at 5 m:
//                       within 1e-5 of range (the function grade); its slope at the rim, 10 and 15 km within 0.05 deg
//                       of numpy's (both by central differences of the ray)
//   cinder_cone         the GPU's cone (cinderConesGrid) along rays, Wood's fresh cone and the SP_CRATER preset:
//                       within 1e-5 of range; Wood's ratios read off the port's ray (H/W, crater/W) equal to the
//                       ones read off numpy's within 1e-4 (Wood 1980: 0.18 and 0.40)
//   crater_dimensions   craterDimensions (Pike's numbers, simple and complex, Earth and Moon): 1e-12 relative
//   impact_crater       the GPU's crater (impactCrater) along rays, the METEOR_CRATER preset plain and with its
//                       cliffs: its delta within 1e-5 of range
//   quantile            prims.quantile(h, q, { mask, dtype: 'float64' }), as op_volcano_lakes takes a playa's top:
//                       bit-equal to numpy's np.quantile of the float32 heights as float64
//   hero levels' ops    lava_rubble, cone_rills and crater_blocks, which run on levels finer than any draft floor
//                       run's (so no stage replay reaches them): each op on the fixture's level and synthetic fields,
//                       every field after it within 1e-4 of range (the stage replay's grade)
//   preset surfaces     fujiSurface and craterLakeSurface (volcanic.py fuji_surface, crater_lake_surface) on their
//                       fixtures' grids: within 1e-5 of range
//
//     <Blender's python> -I eidoverse/terrain/tests/volcanoes_craters/volcanic_expected.py
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/volcanoes_craters/profiles_test.mjs
//         [fixtures folder]       (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/volcanoes_craters/profiles_test.json. JavaScript per cell here is test code.

import { Fields } from '../../core/fields.js';
import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import { prims } from '../../core/prims.js';
import * as IM from '../../solvers/impact.js';
import * as VO from '../../solvers/volcanic.js';
import * as V from './_vc.mjs';

const { C, W } = V;
const DIR = Deno.args[0] ?? `${W.out('volcanoes_craters')}/fixtures`;
const M = C.readJson(`${DIR}/manifest.json`);
const T = new C.Checks('volcanoes_craters: the profiles against numpy');
const summary = {};

const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1e-300);
/** |got - want| / the range of want, at its worst cell. */
function gradeOf(got, want) {
    let lo = Infinity, hi = -Infinity, err = 0;
    for (let i = 0; i < want.length; i++) {
        lo = Math.min(lo, want[i]);
        hi = Math.max(hi, want[i]);
        err = Math.max(err, Math.abs(got[i] - want[i]));
    }
    const range = (hi - lo) || 1.0;
    return { over: err / range, err, range };
}
const gridOf = (ray) => new VO.Grid(ray.origin[0], ray.origin[1], ray.step, ray.direction === 'east' ? ray.count : 1,
    ray.direction === 'east' ? 1 : ray.count);
/** The slope (degrees) of a ray's profile at distance q, by central differences. */
function slopeAt(z, step, q) {
    const i = Math.round(q / step - 0.5);
    return Math.atan(Math.abs(z[i + 1] - z[i - 1]) / (2 * step)) * 180 / Math.PI;
}

function tally(name, rows, grade) {
    const ok = rows.filter((r) => r.ok).length;
    summary[name] = { cases: rows.length, ok, rows };
    T.ok(`${name}: ${ok} of ${rows.length} cases ${grade}`, rows.length > 0 && ok === rows.length,
        rows.filter((r) => !r.ok).slice(0, 4).map((r) => `${r.label}: ${r.why}`).join('; ') || rows.map((r) => r.why).slice(0, 3).join('; '));
}

if (!M) {
    T.ok('the function fixtures are there (volcanic_expected.py)', false, `none at ${DIR}`);
} else {
    const R = await G.init();
    const P = prims(R);
    const cases = (fn) => M.cases.filter((c) => c.function === fn);
    const arr = (a) => C.array(DIR, a);

    {
        const rows = [];
        for (const c of cases('exp_cone')) {
            const { H, R: Rr, upper_slope_deg: up, rc, r } = c.args;
            const lam = VO.coneDecayM(H, up);
            const z = r.map((q) => VO.expCone(q, H, Rr, lam, rc)), s = r.map((q) => VO.expConeSlopeDeg(q, H, Rr, lam, rc));
            const worst = Math.max(rel(lam, c.values.lambda), ...s.map((v, i) => rel(v, c.values.slope_deg[i])),
                ...z.map((v, i) => Math.abs(v - c.values.z[i]) / H));
            rows.push({ label: c.label, ok: worst <= 1e-12, worst, why: `slopes at the rim, 5, 10, 15 km and the foot ` +
                `${s.map((v) => v.toFixed(2)).join(' / ')} deg (numpy ${c.values.slope_deg.map((v) => v.toFixed(2)).join(' / ')}), worst ${C.sci(worst)}` });
        }
        tally('exp_cone', rows, 'equal within 1e-12 relative');
    }
    {
        const rows = [];
        for (const c of cases('stratovolcano')) {
            const grid = gridOf(c.ray);
            const plan = VO.stratoPlan({ ...c.args });
            const out = await VO.evaluateStrato(R, plan, grid, VO.gridBlocks(grid, 1));
            const z = await R.read(out.h);
            VO.release(out);
            const want = arr(c.outputs.z);
            const g = gradeOf(z, want);
            const rc = Number(c.args.crater_radius_m);
            const sl = [rc + 60.0, 10000.0, 15000.0].map((q) => [slopeAt(z, c.ray.step, q), slopeAt(want, c.ray.step, q)]);
            const ds = Math.max(...sl.map(([a, b]) => Math.abs(a - b)));
            rows.push({ label: c.label, ok: g.over <= 1e-5 && ds <= 0.05, worst: g.over, why: `${C.sci(g.over)} of range; ` +
                `slopes at the rim + 60 m, 10 and 15 km ${sl.map(([a]) => a.toFixed(2)).join(' / ')} deg (numpy ` +
                `${sl.map(([, b]) => b.toFixed(2)).join(' / ')})` });
        }
        tally('stratovolcano rays (GPU)', rows, 'within 1e-5 of range, slopes within 0.05 deg');
    }
    {
        const rows = [];
        for (const c of cases('cinder_cone')) {
            const grid = gridOf(c.ray);
            const f = await VO.cinderConesGrid(R, grid, VO.gridBlocks(grid, 1), [{ ...c.args }]);
            const z = await R.read(f);
            f.destroy();
            const want = arr(c.outputs.z);
            const g = gradeOf(z, want);
            const Wd = Number(c.args.width_m);
            let im = 0;
            for (let i = 1; i < z.length; i++) if (z[i] > z[im]) im = i;
            // (the ray's cell i lies i steps from the vent: its grid starts half a step before it)
            const hw = (z[im] - z[z.length - 1]) / Wd, cw = 2.0 * (im * c.ray.step) / Wd;
            const ok = g.over <= 1e-5 && Math.abs(hw - c.values.H_over_W) <= 1e-4 && Math.abs(cw - c.values.crater_over_W) <= 1e-4;
            rows.push({ label: c.label, ok, worst: g.over, why: `${C.sci(g.over)} of range; H/W ${hw.toFixed(4)} (numpy ` +
                `${c.values.H_over_W.toFixed(4)}), crater/W ${cw.toFixed(4)} (numpy ${c.values.crater_over_W.toFixed(4)})` });
        }
        tally('cinder_cone rays (GPU), Wood\'s ratios', rows, 'within 1e-5 of range, the ratios within 1e-4 of numpy\'s');
    }
    {
        const rows = [];
        for (const c of cases('crater_dimensions')) {
            const got = IM.craterDimensions(c.args.diameter_m, c.args.gravity);
            const keys = Object.keys(c.values);
            const bad = keys.filter((k) => (typeof c.values[k] === 'number' ? rel(got[k], c.values[k]) > 1e-12 && Math.abs(got[k] - c.values[k]) > 1e-12
                : got[k] !== c.values[k]));
            rows.push({ label: c.label, ok: !bad.length && Object.keys(got).length === keys.length, why: bad.length ?
                `differ: ${bad.map((k) => `${k} ${got[k]} / ${c.values[k]}`).join(', ')}` : `${got.kind}: depth ${got.depth_m.toFixed(1)} m, rim ${got.rim_m.toFixed(1)} m` });
        }
        tally('crater_dimensions (Pike)', rows, 'equal within 1e-12 relative');
    }
    {
        const rows = [];
        for (const c of cases('impact_crater')) {
            const grid = gridOf(c.ray);
            const out = await IM.impactCrater(R, grid, { ...c.args });
            const z = await R.read(out.delta);
            for (const f of Object.values(out)) if (f && typeof f.destroy === 'function' && !f.destroyed) f.destroy();
            const g = gradeOf(z, arr(c.outputs.delta));
            rows.push({ label: c.label, ok: g.over <= 1e-5, worst: g.over, why: `${C.sci(g.over)} of range (${g.range.toFixed(1)} m)` });
        }
        tally('impact_crater rays (GPU)', rows, 'within 1e-5 of range');
    }
    {
        const rows = [];
        for (const c of cases('quantile')) {
            const h = arr(c.inputs.h), cells = arr(c.inputs.cells);
            const [n] = c.inputs.h.shape;
            const hf = R.field(n, n, 1, Float32Array.from(h)), mf = R.field(n, n, 1, Float32Array.from(cells));
            const top = await P.quantile(hf, c.args.q, { mask: mf, dtype: 'float64' });
            hf.destroy();
            mf.destroy();
            rows.push({ label: c.label, ok: top === c.values.top, why: `${top} / ${c.values.top}` });
        }
        tally('quantile at volcanic.py:2865 (C6)', rows, 'bit-equal to numpy 2.3.4');
    }
    {
        // the hero levels' ops, which no draft floor run reaches: run as ops on the fixture's level and fields, every
        // field after the op graded as a stage replay is (<= 1e-4 x range + 16 float32 steps)
        const OPS = { op_lava_rubble: VO.opLavaRubble, op_cone_rills: VO.opConeRills, op_crater_blocks: IM.opCraterBlocks };
        const rows = [];
        for (const c of M.cases.filter((x) => x.function in OPS)) {
            const level = Level.fromDict(c.args.level);
            const fields = new Fields(level, null, R);
            for (const [k, a] of Object.entries(c.inputs)) fields[k] = R.field(a.shape[0], a.shape[1], 1, Float32Array.from(arr(a)));
            await OPS[c.function](fields, level, structuredClone(c.args.params), c.args.seed, null);
            const worst = [], missing = [];
            for (const [k, a] of Object.entries(c.outputs)) {
                if (!(k in fields)) { missing.push(k); continue; }
                const want = arr(a);
                const g = gradeOf(await R.read(fields[k]), want);
                let amax = 0;
                for (const v of want) amax = Math.max(amax, Math.abs(v));
                const ok = g.err <= 1e-4 * g.range + 16 * C.ulp32(amax);
                worst.push([k, g.over, ok]);
            }
            fields.dispose();
            const bad = worst.filter(([, , ok]) => !ok);
            rows.push({ label: c.label, ok: !bad.length && !missing.length, worst: Math.max(0, ...worst.map(([, o]) => o)),
                why: `${worst.map(([k, o]) => `${k} ${C.sci(o)}`).join(', ')} of range${missing.length ? `; missing ${missing}` : ''}` });
        }
        tally('the hero levels\' ops (lava_rubble, cone_rills, crater_blocks)', rows, 'every field within 1e-4 of range');
    }
    {
        // the preset surfaces on their fixtures' levels
        const rows = [];
        for (const c of M.cases.filter((x) => x.function === 'fuji_surface' || x.function === 'crater_lake_surface')) {
            const level = Level.fromDict(c.args.level);
            const f = c.function === 'fuji_surface' ? await VO.fujiSurface(R, VO.levelGrid(level)) : await VO.craterLakeSurface(R, level);
            const g = gradeOf(await R.read(f), arr(c.outputs.z));
            f.destroy();
            rows.push({ label: c.label, ok: g.over <= 1e-5, worst: g.over, why: `${C.sci(g.over)} of range (${g.range.toFixed(0)} m)` });
        }
        tally('the preset surfaces (fuji_surface, crater_lake_surface)', rows, 'within 1e-5 of range');
    }
    G.shutdown();
}

T.extra.summary = summary;
T.extra.fixtures = { dir: DIR, versions: M?.versions ?? null };
Deno.exit(V.finish(T, 'profiles_test'));
