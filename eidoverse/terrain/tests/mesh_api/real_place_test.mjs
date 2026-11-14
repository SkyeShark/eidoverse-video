// recipes/real_place.js against Blender's (PORT_PLAN.md 3.2, 8.2 P4): the recipe as data, the DEM lookup, the
// defaults a DEM gives, and the `dem` op on the GPU against real_place.py's op_dem on the same levels
// (real_place_expected.py, run by Blender's Python on the reference DEMs).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/real_place_test.mjs [case ...]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front; the reference DEMs are found through
// $EIDO_TERRAIN_DEMS or $EIDO_BLENDER_EDITION). Checks
//   recipe      REAL_PLACE.toDict() JSON-equal to Blender's; describe() equal; the registry lists it with its op
//   DEMs        demNames() equal; an unknown name raises Blender's sentence, then says where the references are
//               looked for and that a path always works; a path to a reference JSON and to its PNG load
//   defaults    defaultsFor(values) equal to Blender's (the place's palette, mask parameters and strata aside: they
//               come with build/palettes.js, the surfacing wave)
//   dem         per case and level: h within 1e-5 of the range (a level that holds the DEM's own pixels: to the
//               bit), water within 1e-5 of its range with the same wet cells, bed equal to h
//   taps        axisTaps equal to real_place.py's _axis_weights rows on the cases' own axes (through the fields)

import * as G from '../../core/gpu.js';
import { Fields } from '../../core/fields.js';
import { planLevels, QUALITY, pyRound } from '../../core/levels.js';
import * as RP from '../../recipes/real_place.js';
import * as registry from '../../recipes/index.js';
import * as C from './_common.mjs';

const BASE = new URL('real_place_fixtures/', C.OUT);
const args = Deno.args.filter((a) => !a.startsWith('--'));
let top;
try {
    top = JSON.parse(Deno.readTextFileSync(new URL('recipe.json', BASE)));
} catch (_e) {
    console.log("SKIP: no real_place fixtures. Make them with Blender's Python:\n    <blender>/<version>/python/bin/python -I -B " +
        'eidoverse/terrain/tests/mesh_api/real_place_expected.py\n(the Blender edition is found beside eidoverse/ or at $EIDO_BLENDER_EDITION)');
    Deno.exit(0);
}
const cases = C.fixtureCases(args.length ? args : null, BASE) ?? [];
const R = await G.init();
const T = new C.Checks('mesh and API: recipes/real_place.js against real_place.py');
T.extra.cases = {};

// the recipe, as data
const d = RP.REAL_PLACE.toDict();
T.ok('recipe: REAL_PLACE.toDict() JSON-equal to Blender\'s to_dict()', C.sameJson(d, top.recipe), C.jsonDiff(d, top.recipe) ?? `${Object.keys(d.knobs).length} knobs, ${d.stages.length} stages`);
const norm = (s) => s.replace(/(\d)\.0\b/g, '$1');
T.ok('recipe: describe() equal (integral floats print without .0 here)', norm(RP.REAL_PLACE.describe()) === norm(top.describe),
    RP.REAL_PLACE.describe() === top.describe ? 'identical' : 'equal once 2000.0 is read as 2000');
T.ok('recipe: the registry lists real_place and finds its op', registry.names().includes('real_place') && (await registry.getOp('dem')) === RP.opDem &&
    registry.resolve(top.recipe).defaultsFor === RP.defaultsFor, registry.names().join(', '));

// the DEMs
const names = RP.demNames();
T.ok('DEMs: demNames() equal to Blender\'s dem_names()', C.sameJson(names, top.dem_names), `${names.length} DEMs`);
let msg = '';
try {
    await RP.load(R, 'lauterbrunen');
} catch (e) {
    msg = `${e.name}: ${e.message}`;
}
T.ok('DEMs: an unknown name raises Blender\'s sentence, then where the references are looked for and that a path always works',
    msg.startsWith('KeyError: ' + top.unknown_dem_error) && msg.includes('EIDO_TERRAIN_DEMS') && msg.includes('always works'), msg);
if (names.includes('lauterbrunnen')) {
    const js = RP.find('lauterbrunnen');
    const byJson = await RP.load(R, js), byPng = await RP.load(R, js.replace(/\.json$/, '.png'));
    T.ok('DEMs: a path to a reference JSON, or to its PNG, loads the same DEM', byJson.name === 'lauterbrunnen' && byPng.name === 'lauterbrunnen' &&
        byJson.n === byPng.n && byJson.hMin === byPng.hMin, `${js.split('/').pop()}: ${byJson.n} px of ${byJson.pixel} m`);
}

async function checkCase(name) {
    const man = JSON.parse(Deno.readTextFileSync(new URL(`${name}/manifest.json`, BASE)));
    const rec = {};
    T.extra.cases[name] = rec;
    const tag = (s) => `${name}: ${s}`;
    const bin = (f) => {
        const b = Deno.readFileSync(new URL(`${name}/${f}`, BASE));
        return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4);
    };
    const [values, stages] = RP.REAL_PLACE.resolve({ dem: man.dem });
    T.ok(tag('resolved knobs and the dem stage\'s parameters equal'), C.sameJson(values, man.values) && C.sameJson(stages[0].params, man.stage_params),
        C.jsonDiff(stages[0].params, man.stage_params) ?? JSON.stringify(values));
    const dfl = await RP.defaultsFor(values, { R, log: () => {} });
    const want = { ...man.defaults_for };
    const waiting = ['palette', 'place', 'mask_params'].filter((k) => k in want && !(k in dfl));
    for (const k of waiting) delete want[k];
    T.ok(tag('defaultsFor equal to Blender\'s defaults_for' + (waiting.length ? ` (${waiting.join(', ')} come with build/palettes.js)` : '')),
        C.sameJson(dfl, want), C.jsonDiff(dfl, want) ?? JSON.stringify(dfl));
    const dem = await RP.load(R, man.dem);
    T.ok(tag('the base (the datum of y = 0) is Blender\'s float64'), dem.base(values.base) === man.base, `${dem.base(values.base)} vs ${man.base}`);
    // the plan as api.js lays it out
    const Q = QUALITY[man.quality];
    const scaled = Math.trunc(Math.max(64, pyRound(dfl.resolution * { draft: 0.5, film: 1.0, hero: 2.0 }[man.quality] / 8.0) * 8));
    const plan = planLevels(dfl.size, scaled || Q.resolution, { centre: dfl.centre, context: dfl.context, warn: () => {} });
    T.ok(tag('the level plan equal'), C.sameJson(plan.map((lv) => lv.toDict()), man.plan), C.jsonDiff(plan.map((lv) => lv.toDict()), man.plan) ?? `${plan.length} levels of ${scaled} cells`);
    rec.levels = [];
    const t0 = performance.now();
    for (const L of man.levels) {
        const lv = plan[L.index];
        const f = new Fields(lv, null, R);
        await RP.opDem(f, lv, stages[0].params, 0);
        const got = await f.toHost();
        const wantH = bin(`h_${L.index}.bin`);
        const range = L.h_max - L.h_min;
        let worst = 0, differ = 0, at = -1;
        for (let q = 0; q < wantH.length; q++) {
            const e = Math.abs(got.h[q] - wantH[q]);
            if (e) differ++;
            if (e > worst) { worst = e; at = q; }
        }
        const own = lv.role === 'main' && Math.abs(lv.cell - man.dem_pixel) < 1e-9 * lv.cell && !('water' in got);
        const names2 = Object.keys(got).sort();
        let bedOk = true;
        for (let q = 0; q < got.h.length && bedOk; q++) if (got.bed[q] !== got.h[q]) bedOk = false;
        const r = { level: L.index, role: lv.role, cell: lv.cell, h_worst_m: worst, h_worst_over_range: worst / range, cells_differing: differ, own_pixels: own };
        let ok = C.sameJson(names2, L.fields) && bedOk && worst / range <= 1e-5 && (!own || worst === 0);
        let detail = `fields ${names2.join(', ')}; h worst ${worst.toExponential(2)} m (${(worst / range).toExponential(2)} of the range), ` +
            `${differ} of ${wantH.length} cells differ` + (own ? " (the DEM's own pixels: to the bit)" : '');
        if ('water' in got) {
            const wantW = bin(`water_${L.index}.bin`);
            let ww = 0, wet = 0, wetDiff = 0;
            for (let q = 0; q < wantW.length; q++) {
                ww = Math.max(ww, Math.abs(got.water[q] - wantW[q]));
                if (got.water[q] > 0) wet++;
                if ((got.water[q] > 0) !== (wantW[q] > 0)) wetDiff++;
            }
            r.water_worst_m = ww;
            r.wet_cells = wet;
            r.wet_cells_differing = wetDiff;
            ok = ok && ww <= 1e-5 * Math.max(L.water_max, 1) + 1e-4 && wetDiff === 0 && wet === L.water_cells;
            detail += `; water worst ${ww.toExponential(2)} m, ${wet} wet cells (Blender ${L.water_cells}), ${wetDiff} differ in wet / dry`;
        }
        if (!ok && at >= 0) detail += `; h[${at}] ${got.h[at]} vs ${wantH[at]}`;
        T.ok(tag(`dem op on level ${L.index} (${lv.role}, ${lv.cell} m): h within 1e-5 of the range${'water' in got ? ', the water equal' : ''}, bed = h`), ok, detail);
        rec.levels.push(r);
        f.dispose();
    }
    await R.idle();
    rec.seconds = +((performance.now() - t0) / 1000).toFixed(3);
    rec.blender_seconds = man.seconds;
}

for (const name of cases) {
    try {
        await checkCase(name);
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 8).join('\n')}`);
    }
}
await RP.clearCache(R);
G.shutdown();
Deno.exit(C.finish(T, 'real_place_test.json'));
