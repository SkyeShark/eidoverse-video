// build/plants.js's cover rasters against plants.py's (PORT_PLAN.md 8.2 row P15; SURFACING_DESIGN.md 4.7, 5.4 package 4
// item 6), on tests/plants/plants_fixtures.py --spots (cover.npz: a plan's cover_extra(); expected.npz: expected_cover
// with no plan):
//
//     <the GPU queue> deno run --config deno.json --frozen --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/plants/cover_test.mjs [--case canyon,...]
//
// Per case and level, every raster the surface data's registry knows (canopy, canopy_expected, canopy_far, shrubs,
// shrubs_far): the port's plan on the same snapshot and Blender bake, its coverExtra() and expectedCover(), against
// Blender's, graded where the material reads them: the M family stores a unit map in 8 bits, so a texel differs
// when it differs by more than 1/255; at most 0.1 % of a level's texels may (the spots one edition placed and the
// other did not, the densities' near-ties), with the mean difference under 1e-4. Also the design's checks on the
// port alone: canopy_far is 0 where the instances carry the whole canopy (within the instanced radius' inner band),
// and expectedCover's canopy_expected equals a plan's (the one rule).

import * as S from './_plants.mjs';
import * as PL from '../../build/plants.js';

const A = S.argsOf();
const T = new S.C.Checks('plants: the cover rasters against plants.py');
const root = S.fixtureRoot('the spots fixtures');
const manifestPath = root ? `${root}/spots/manifest.json` : null;
if (!manifestPath || !S.W.exists(manifestPath)) {
    S.W.skip('cover', 'run tests/plants/plants_fixtures.py --spots');
    Deno.exit(0);
}
const man = JSON.parse(Deno.readTextFileSync(manifestPath));
const want = A.list('--case', ['lauterbrunnen_r250', 'canyon', 'fluvial_range', 'great_sand_dunes']);
const { Terrain, NpzFile } = await import('../../api.js');
const SI = await import('../../surface/index.js');
const G = await import('../../core/gpu.js');
const R = await G.init();

function snapshotFolder() {
    if (man.snaps && S.W.exists(man.snaps)) return man.snaps;
    const t = S.W.blenderTests();
    return t ? `${t}/out/surface_data/snap` : null;
}

function grade(a, b) {
    let over = 0, sum = 0, worst = 0;
    for (let i = 0; i < b.length; i++) {
        const d = Math.abs(a[i] - b[i]);
        sum += d;
        if (d > worst) worst = d;
        if (d > 1 / 255) over++;
    }
    return { share: over / b.length, mean: sum / b.length, worst };
}

const detail = {};
for (const name of want) {
    const c = man.cases[name];
    if (!c || c.error) continue;
    const dir = `${root}/spots/${name}`;
    const info = JSON.parse(Deno.readTextFileSync(`${dir}/info.json`));
    const snap = info.args.snap ?? name;
    const snaps = snapshotFolder();
    if (!snaps || !S.W.exists(`${snaps}/${snap}.npz`)) continue;
    const t = await Terrain.load(`${snaps}/${snap}.npz`, { build: false, log: null });
    const hit = await SI.loadCached(`${man.bakes}/${snap}`, info.bake_key, t.levels.length);
    const sd = new SI.SurfaceData(t, hit[0], { ...hit[1], cache_hit: true }, hit[1].options ?? {}, info.bake_key, null, null, `${man.bakes}/${snap}`);
    const spots = await PL.planPlants(t, { ecotope: 'auto', focus: { blender: info.focus }, radiusM: info.args.radius_m ?? null,
        seed: info.args.seed ?? 0, data: sd, exclude: info.exclude.length ? { blender: info.exclude } : null, log: null, R });
    const t0 = performance.now();
    const extra = await spots.coverExtra();
    const coverS = (performance.now() - t0) / 1000;
    const t1 = performance.now();
    const expd = await PL.expectedCover(t, { data: sd, R });
    const expS = (performance.now() - t1) / 1000;
    const bc = await NpzFile.open(`${dir}/cover.npz`), be = await NpzFile.open(`${dir}/expected.npz`);
    detail[name] = { cover_seconds: +coverS.toFixed(1), expected_seconds: +expS.toFixed(1), blender: info.seconds, maps: {} };
    for (const [what, mine, file] of [['cover', extra, bc], ['expected', expd, be]]) {
        for (const [k, per] of Object.entries(mine)) {
            let worstShare = 0, worstMean = 0, worstAbs = 0, at = -1, missing = 0;
            per.forEach((a, i) => {
                const key = `${k}_L${i}`;
                if (!file.has(key)) { missing++; return; }
                const b = file.read(key).data;
                if (b.length !== a.length) { missing++; return; }
                const g = grade(a, b);
                if (g.share > worstShare) { worstShare = g.share; at = i; }
                worstMean = Math.max(worstMean, g.mean);
                worstAbs = Math.max(worstAbs, g.worst);
            });
            detail[name].maps[`${what}:${k}`] = { worstShare, worstMean, worstAbs, at, missing };
            T.ok(`${name} ${what} ${k}: every level within 1/255 but at most 0.1 % of its texels, mean under 1e-4`,
                missing === 0 && worstShare <= 1e-3 && worstMean <= 1e-4,
                `${(100 * worstShare).toFixed(4)} % past 1/255 (level ${at}), mean ${S.sci(worstMean, 1)}, worst ${S.sci(worstAbs, 2)}` +
                (missing ? `; ${missing} levels missing or of another size` : ''));
        }
    }
    // the one rule: a plan's canopy_expected is expectedCover's (the same densities, nothing sampled)
    let same = 0;
    extra.canopy_expected.forEach((a, i) => { same = Math.max(same, grade(a, expd.canopy_expected[i]).worst); });
    T.ok(`${name}: a plan's canopy_expected equals expectedCover's (one rule for the instances and the material)`, same <= 1e-6,
        `largest difference ${S.sci(same, 2)}`);
}

Deno.writeTextFileSync(`${S.W.out('plants')}/cover_test_detail.json`, JSON.stringify(detail, null, 1));
Deno.exit(S.finish(T, 'cover_test', { cases: Object.keys(detail) }));
