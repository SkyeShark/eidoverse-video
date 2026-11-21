// build/dressing.js's rock placement (dressing.py place_rocks' rules; PORT_PLAN.md 3.5 row dressing.js: a hash per
// candidate, mask densities, power-law sizes, the toe bias), on a fixture case's terrain and Blender bake:
//
//     <the GPU queue> deno run --config deno.json --frozen --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/plants/dressing_test.mjs [--case canyon]
//
//   sizes      every rock within size_m
//   disc       every rock within radius_m of the focus, none in an excluded disc
//   ground     every rock's centre over the ground by (0.5 - bury) x its height x its up axis' z (heightAt, test code)
//   bytes      the same inputs give the same matrices, byte for byte

import * as S from './_plants.mjs';
import * as D from '../../build/dressing.js';

const A = S.argsOf();
const T = new S.C.Checks('plants: the rocks (dressing.js)');
const root = S.fixtureRoot('the spots fixtures');
const man = root && S.W.exists(`${root}/spots/manifest.json`) ? JSON.parse(Deno.readTextFileSync(`${root}/spots/manifest.json`)) : null;
if (!man) {
    S.W.skip('dressing', 'run tests/plants/plants_fixtures.py --spots');
    Deno.exit(0);
}
const name = A.opt('--case', 'canyon');
const info = JSON.parse(Deno.readTextFileSync(`${root}/spots/${name}/info.json`));
const { Terrain } = await import('../../api.js');
const SI = await import('../../surface/index.js');
const B = await import('../../surface/bake.js');
const G = await import('../../core/gpu.js');
const R = await G.init();
const snap = info.args.snap ?? name;
const t = await Terrain.load(`${man.snaps}/${snap}.npz`, { build: false, log: null });
const hit = await SI.loadCached(`${man.bakes}/${snap}`, info.bake_key, t.levels.length);
const sd = new SI.SurfaceData(t, hit[0], { ...hit[1], cache_hit: true }, hit[1].options ?? {}, info.bake_key, null, null, `${man.bakes}/${snap}`);
const pal = await B.resolvePalette(t, t.info?.palette && t.info.palette !== 'auto' ? t.info.palette : 'auto');
const spec = { ...D.DEFAULT_SPEC, ...(pal.dressing ?? {}) };
const focus = info.focus[0];
const models = await D.loadModels(spec.models, spec.colour ?? null, spec.model_res, { R, log: null }).catch((e) => {
    console.log(`[skip] the rock models: ${e.message}`);
    return null;
});
if (!models) Deno.exit(0);
const exclude = [[focus[0] + 20, focus[1], 8.0]];
const run = () => D.placeRocks(spec, { terrain: t, data: sd, focus, seed: 7, models, exclude, R });
const a = await run(), b = await run();
T.ok('bytes: the same inputs give the same rocks', a.n === b.n && a.matrices.every((v, i) => Object.is(v, b.matrices[i])),
    `${a.n} rocks of ${models.length} meshes (${a.counts.join(', ')})`);
T.ok('the palette scatters rocks here', a.n > 0, `density ${spec.density}`);
// the rocks' numbers back from their matrices (test code): position (three.js x, y, z) and the scale's columns
const s0 = Number(spec.size_m[0]), s1 = Number(spec.size_m[1]);
let inDisc = true, offExcl = true, worstGround = 0;
let first = 0;
models.forEach((m, k) => {
    for (let j = 0; j < a.counts[k]; j++) {
        const o = 16 * (first + j);
        const M = a.matrices;
        const x = M[o + 12], y = -M[o + 14], zc = M[o + 13];
        const d = Math.hypot(x - focus[0], y - focus[1]);
        if (d > Number(spec.radius_m) + 1e-3) inDisc = false;
        if (Math.hypot(x - exclude[0][0], y - exclude[0][1]) <= exclude[0][2]) offExcl = false;
        const g = t.ring.heightAt(x, y);
        const up = M[o + 5] / Math.max(Math.hypot(M[o + 4], M[o + 5], M[o + 6]), 1e-12);    // three's y column: Blender's z axis
        const hgt = m.dims[2] * Math.hypot(M[o + 4], M[o + 5], M[o + 6]);
        worstGround = Math.max(worstGround, Math.abs(zc - (g + (0.5 - Number(spec.bury)) * hgt * up)));
    }
    first += a.counts[k];
});
T.ok('disc: every rock within radius_m of the focus', inDisc, `${spec.radius_m} m`);
T.ok('disc: none in the excluded disc', offExcl, JSON.stringify(exclude));
T.ok('sizes: within size_m', a.sizes[0] >= s0 * 0.999 && a.sizes[1] <= s1 * 1.001,
    `${a.sizes[0].toFixed(3)}-${a.sizes[1].toFixed(3)} m (spec ${s0}-${s1})`);
T.ok('ground: every rock\'s centre (0.5 - bury) of its height over the ground along its up axis', worstGround < 0.05,
    `worst ${worstGround.toFixed(4)} m`);
Deno.exit(S.finish(T, 'dressing_test', { case: name, n: a.n, counts: a.counts }));
