// alpine_valley's 'yosemite' preset judged against Yosemite Valley (PORT_PLAN.md 8.2 row P13: "the bands against
// Lauterbrunnen and Yosemite"): the port's draft runs of the preset (recipes/alpine_valley.js preset('yosemite'): a 12
// km tile at 1100 m, the upland horseshoe draining west, a 1.8 km trough with 950 m walls, no cirques) and the Blender
// edition's own runs of it (tests/glacial/blender_runs.py), judged by the Blender judge against the yosemite_valley
// reference (tests/judge/judge.mjs judgeSave). The class rule of plan 5.3 over the seeds run (alpine_valley is of the
// distribution class): each banded number's mean within half its band's tolerance of Blender's, every band Blender
// passes on 3 of 4 seeds passed by the port as often.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/glacial/yosemite_test.mjs
//          --bake [--seeds 1,2,3,4]      the port's saves (api.js generate + save; a GPU job, behind $EIDO_GPU_WRAP)
//     bash run_blender.sh eidoverse/terrain/tests/glacial/blender_runs.py -- eidoverse/terrain/tests/out/glacial/yosemite
//          --seeds 1,2,3,4
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/glacial/yosemite_test.mjs [--seeds 1,2,3,4]
//
// Writes tests/out/glacial/yosemite/ (the saves, the verdicts) and yosemite_test.json.

import * as AV from '../../recipes/alpine_valley.js';
import * as J from '../judge/judge.mjs';
import * as C from '../parity/_common.mjs';
import { finish } from './_glacial.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const SEEDS = opt('--seeds', '1,2,3,4').split(',').map(Number);
const DIR = `${W.out('glacial')}/yosemite`;
Deno.mkdirSync(DIR, { recursive: true });

if (args.includes('--bake')) {
    const A = await import('../../api.js');
    const G = await import('../../core/gpu.js');
    const p = AV.preset('yosemite');
    for (const s of SEEDS) {
        const t0 = performance.now();
        const t = await A.generate({ recipe: 'alpine_valley', size: p.size, seed: s, params: p.params, baseElevationM: p.base_elevation_m,
            quality: 'draft', cache: false });
        await t.save(`${DIR}/alpine_valley_yosemite_s${s}_port`);
        console.log(`[glacial] yosemite s${s}: ${((performance.now() - t0) / 1000).toFixed(1)} s`);
        t.dispose?.();
    }
    G.shutdown();
    Deno.exit(0);
}

const T = new C.Checks('glacial: the yosemite preset judged against Yosemite Valley, beside the Blender edition');
const out = { seeds: {} };
const port = [], blender = [];
for (const s of SEEDS) {
    const ps = `${DIR}/alpine_valley_yosemite_s${s}_port.npz`, bs = `${DIR}/alpine_valley_yosemite_s${s}.npz`;
    if (!W.exists(ps) || !W.exists(bs)) {
        out.seeds[s] = { missing: [!W.exists(ps) ? 'the port save' : null, !W.exists(bs) ? 'the Blender save' : null].filter(Boolean) };
        console.log(`yosemite s${s}: missing ${out.seeds[s].missing.join(', ')}`);
        continue;
    }
    const pv = await J.judgeSave(ps, { recipe: 'alpine_valley', reference: 'yosemite_valley', label: `yosemite_port_s${s}`, outDir: `${DIR}/judge_port_s${s}` });
    const bv = await J.judgeSave(bs, { recipe: 'alpine_valley', reference: 'yosemite_valley', label: `yosemite_blender_s${s}`, outDir: `${DIR}/judge_blender_s${s}` });
    if (!pv || !bv) { out.seeds[s] = { missing: 'a verdict (see the judge.log beside it)' }; continue; }
    port.push(pv);
    blender.push(bv);
    const rows = (v) => Object.fromEntries(v.rows.filter((r) => r.passed !== null).map((r) => [r.metric, { gen: r.gen, passed: r.passed }]));
    out.seeds[s] = { port: rows(pv), blender: rows(bv), port_passed: pv.rows.filter((r) => r.passed).length,
        blender_passed: bv.rows.filter((r) => r.passed).length, bands: pv.rows.filter((r) => r.passed !== null).length };
    console.log(`yosemite s${s}: bands passed: port ${out.seeds[s].port_passed}, Blender ${out.seeds[s].blender_passed} of ` +
        `${out.seeds[s].bands}: ` + Object.entries(out.seeds[s].port).map(([m, r]) => `${m} ${Number(r.gen).toPrecision(4)} ` +
        `(Blender ${Number(out.seeds[s].blender[m]?.gen).toPrecision(4)})${r.passed ? '' : ' x'}`).join(', '));
}
if (port.length) {
    const d = J.compareDistribution(port, blender);
    out.distribution = d;
    T.ok(`yosemite preset over ${port.length} seeds: every banded number's mean within half its band's tolerance of Blender's, ` +
        'every band Blender passes on 3 of 4 seeds passed by the port as often', d.ok,
    d.means.filter((m) => !m.ok).map((m) => `${m.metric} port ${m.port.toPrecision(4)} Blender ${m.blender.toPrecision(4)} (tol ` +
        `${m.tol?.toPrecision(3)})`).concat(d.bands.filter((b) => !b.ok).map((b) => `${b.metric}: Blender passes ${b.blender_passes}, ` +
        `port ${b.port_passes}`)).join('; '));
} else {
    T.ok('yosemite preset judged', false, 'no seed has both saves');
}
Deno.exit(finish(T, 'yosemite_test', out));
