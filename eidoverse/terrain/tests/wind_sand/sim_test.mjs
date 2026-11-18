// The slab model on the GPU as the Blender package's own GPU tests run it (blender/tests/terrain/wind_sand/test_gpu.py,
// PORT_PLAN.md 8.2 P8: "sand mass conserved"; "all four kinds the family test tells apart"), and determinism.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/wind_sand/sim_test.mjs
//
// (from the repository root; behind $EIDO_GPU_WRAP on a shared machine). Checked:
//   mass         test_mass_gpu's case: a periodic 512 x 512 field (the star kind's model with 8 m of sand at 200 m
//                spacing, its start from start_fields) under the three winds for 3000 iterations (whole cycles: 5,998):
//                the total sand within 1e-5 relative (Blender's GPU: 1.4e-6); on an open grid without avalanches the
//                total falls by exactly the slabs the plans send off the edge (test_twins.py's bookkeeping, on the GPU)
//   rock         the bed never moves (the avalanche moves only sand; no abrasion)
//   determinism  one seed gives the same field bit for bit run after run; another seed another field
//   families     test_families: each kind on a periodic 256 x 256 box of 4 m (its BOX sand and spacing, a flat bed),
//                18,000 iterations, then one more cycle block by block keeping each block's surface; the fields go to
//                tests/out/wind_sand/families/ and tests/wind_sand/families.py (Blender's Python) measures them with
//                the Blender package's own dune_measures.py and applies test_families' four criteria (barchans: separate
//                crescents with horns downwind; transverse: a continuous sheet of ridges across the wind, lee faces
//                only; linear: coherent ridges along the resultant, two lee directions; star: no ridge direction, slip
//                faces three or more ways), beside Blender's own measures of its runs (out/wind_sand/gpu_tests.json)
// JavaScript per cell here is test code (the sums and the fields' writing).

import * as G from '../../core/gpu.js';
import * as Gd from '../../core/grid.js';
import * as IO from '../../core/io.js';
import * as A from '../../solvers/aeolian.js';
import { Level, pyInt } from '../../core/levels.js';
import * as C from '../parity/_common.mjs';
import * as S from './_common.mjs';

const T = new S.Checks('wind and sand: mass, rock, determinism and the four dune families on the GPU');
const R = await G.init();
const sum64 = (a, ch = 1, c = 0) => { let s = 0; for (let i = c; i < a.length; i += ch) s += a[i]; return s; };

// ---- mass on a periodic grid (test_mass_gpu)
{
    const n = 512, cell = 4.0;
    const lv = new Level(0, 'main', 0.0, 0.0, n * cell, cell, n);
    const p = A.resolveParams({ kind: 'star', sand_m: 8.0, spacing_m: 200.0 });
    const { bed, sand } = await A.startFields(R, lv, p, 2, lv.side);
    const tot0 = sum64(await R.read(sand));
    const sim = new A.SandSim(bed, sand, cell, { bound: A.BOUND_PERIODIC, params: p, seed: 3 });
    const t0 = performance.now();
    const it = await sim.run(p.winds, 3000);
    const [b1, s1] = await sim.read();
    const secs = (performance.now() - t0) / 1000;
    const rel = sum64(s1) / tot0 - 1.0;
    T.ok('sand mass conserved on the GPU: a periodic 512 x 512 field under three winds', Math.abs(rel) <= 1e-5 && it === 5998,
        `${it} iterations, relative change of the total ${S.sci(rel)} (Blender's GPU: 1.4e-6), ${secs.toFixed(2)} s (Blender 2.18 s)`);
    const b0 = await R.read(bed);
    let moved = 0;
    for (let i = 0; i < b0.length; i++) if (b0[i] !== b1[i]) moved++;
    T.ok('the bed never moves (only sand is carried and avalanches)', moved === 0, `${moved} cells of ${b0.length} changed`);
    sim.dispose();
    bed.destroy();
    sand.destroy();
}

// ---- mass on an open grid: what leaves is what the plans send off the edge (aval_passes 0)
{
    const n = 96, cell = 4.0;
    const lv = new Level(0, 'main', 0.0, 0.0, n * cell, cell, n);
    const p = A.resolveParams({ kind: 'transverse', sand_m: 3.0, spacing_m: 60.0, hop_cells: 3.3, aval_passes: 0 });
    const { bed, sand } = await A.startFields(R, lv, p, 5, null);
    const tot0 = sum64(await R.read(sand));
    const sim = new A.SandSim(bed, sand, cell, { bound: A.BOUND_OPEN, params: p, seed: 21 });
    let lost = 0;
    for (let k = 0; k < 20; k++) {
        await sim.step(225.0);
        const plan = await R.read(sim.plan);
        for (let i = 0; i < plan.length; i += 4) if (plan[i + 3] < 0) lost += plan[i];
    }
    const [, s] = await sim.read();
    const after = sum64(s);
    T.ok('on an open grid the sand falls by exactly the slabs blown off the edge (20 iterations, no avalanche)',
        Math.abs(tot0 - lost - after) <= 1e-5 * tot0 && lost > 0, `start ${tot0.toFixed(3)} m, blown off ${lost.toFixed(3)} m, end ${after.toFixed(3)} m`);
    sim.dispose();
    bed.destroy();
    sand.destroy();
}

// ---- determinism
{
    const n = 128, cell = 4.0;
    const lv = new Level(0, 'main', 0.0, 0.0, n * cell, cell, n);
    const p = A.resolveParams({ kind: 'star', sand_m: 8.0, spacing_m: 100.0, steer_deg: 25.0, steer_wavelength_m: 300.0 });
    const runOnce = async (seed) => {
        const { bed, sand } = await A.startFields(R, lv, p, 4, lv.side);
        const steer = A.steeringFor(R, lv, p, 4, lv.side);
        const sim = new A.SandSim(bed, sand, cell, { bound: A.BOUND_PERIODIC, params: p, seed, steer });
        await sim.run(p.winds, 600, { block: 100 });
        const [, s] = await sim.read();
        sim.dispose();
        steer.dispose();
        bed.destroy();
        sand.destroy();
        return s;
    };
    const a = await runOnce(3), b = await runOnce(3), c = await runOnce(4);
    T.ok('one seed gives the same field bit for bit (600 steered iterations, twice)', a.every((v, i) => v === b[i]));
    T.ok('another seed gives another field', a.some((v, i) => v !== c[i]));
}

// ---- the four families (test_families' run_kind)
const BOX = { barchan: { sand_m: 1.0, spacing_m: 150.0, supply_var: 0.5 }, transverse: { sand_m: 6.0, spacing_m: 150.0 },
    linear: { sand_m: 6.0, spacing_m: 200.0 }, star: { sand_m: 8.0, spacing_m: 200.0 } };
const famDir = `${S.OUT}/families`;
Deno.mkdirSync(famDir, { recursive: true });
const runs = {};
for (const kind of ['barchan', 'transverse', 'linear', 'star']) {
    const n = 256, cell = 4.0;
    const lv = new Level(0, 'main', 0.0, 0.0, n * cell, cell, n);
    const p = A.resolveParams({ ...BOX[kind], kind });
    const t0 = performance.now();
    const { bed, sand } = await A.startFields(R, lv, p, 3, lv.side);
    bed.destroy();
    const flat = Gd.fill(R, [n, n], 0.0);                   // bed[:] = 0.0
    const sim = new A.SandSim(flat, sand, cell, { bound: A.BOUND_PERIODIC, params: p, seed: 11 });
    let done = await sim.run(p.winds, 18000);
    const blocks = [];
    for (const [d, b] of A.cycleBlocks(p.winds, pyInt(p.block))) {
        for (let i = 0; i < b; i++) await sim.step(d);
        done += b;
        const [bb, ss] = await sim.read();
        blocks.push(Float32Array.from(bb, (v, i) => v + ss[i]));
    }
    const { bed: b, sand: s } = sim.fields();
    const sd = A.denoise(s, Number(p.smooth_cells), { periodic: true });
    const h = Gd.arith(R, 'add', b, sd);
    const [hh, sh] = await R.readAll([h, sd]);
    const stack = new Float32Array(blocks.length * n * n);
    blocks.forEach((x, k) => stack.set(x, k * n * n));
    await IO.writeNpz(`${famDir}/${kind}.npz`, { h: IO.npArray(hh, [n, n]), sand: IO.npArray(sh, [n, n]),
        blocks: IO.npArray(stack, [blocks.length, n, n]) });
    runs[kind] = { iters: done, seconds: +((performance.now() - t0) / 1000).toFixed(2), cell, winds: p.winds,
        slab_cells: p.slab_cells, smooth_cells: p.smooth_cells };
    Deno.writeTextFileSync(`${famDir}/${kind}.json`, JSON.stringify({ kind, params: p, ...runs[kind] }, null, 1));
    for (const f of [flat, sand, b, s, sd, h]) f.destroy();
    sim.dispose();
}
G.shutdown();

const py = S.W.pythonCmd(`${S.W.TESTS}/wind_sand/families.py`, famDir);
if (!py) {
    S.W.skip('the four families\' measures', "set EIDO_BLENDER_PYTHON (the judge's dune_measures.py runs in Blender's Python)");
} else {
    const code = await S.W.run(py, { log: `${famDir}/families.log`, env: { ...Deno.env.toObject(), PYTHONDONTWRITEBYTECODE: '1' } });
    const res = C.readJson(`${famDir}/families.json`);
    if (code !== 0 || !res) {
        T.ok('the four families measured by dune_measures.py', false, `exit ${code}: see ${famDir}/families.log`);
    } else {
        for (const [name, ok] of Object.entries(res.families)) T.ok(`families: ${name}`, ok, JSON.stringify(res.port[name.split(':')[0]] ?? {}).slice(0, 400));
        T.ok('four regimes, four families (test_families\' verdict on the port\'s fields)', res.all, JSON.stringify(res.side_by_side).slice(0, 1200));
        T.extra.families = res;
    }
}
T.extra.family_runs = runs;
Deno.exit(S.finish(T, 'sim_test'));
