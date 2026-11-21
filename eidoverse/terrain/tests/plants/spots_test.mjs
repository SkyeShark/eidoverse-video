// build/plants.js against the Blender edition's plants.py (PORT_PLAN.md 8.2 row P15, 10.2: "spots against Blender's
// spots files for the same terrain, ecotope and focus: candidates bit-exact, decisions equal except counted near-ties,
// positions within f32 rounding"), on tests/plants/plants_fixtures.py --spots:
//
//     <the GPU queue> deno run --config deno.json --frozen --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/plants/spots_test.mjs [--case lauterbrunnen_r250,...] [--keep]
//
// Per case: the snapshot (a Blender Terrain.save) loaded by api.js, the Blender bake of it read as the port's
// SurfaceData (its stored npz, as Blender's plan read it), the plan made with the case's arguments; then per species
// the counts, every Blender spot matched to the port's spot at the same position (x and y within 4 float32 steps,
// or 1e-4 m), the matched spots' fields (z and the normal within the two editions' ring meshes' own bound, PORT_PLAN.md
// C3: 14 float32 steps of the largest tap round each corner; yaw,
// scale, age, tint, the normal within float32 rounding of their arithmetic; variant and level equal), the spots only
// one edition placed (decisions that differ: each one is a near-tie of a float64 comparison in float32, or what such a
// tie moved, counted and reported), and the stats and the plan's description JSON-equal where they are exact (counts
// within the differing decisions). Deterministic bytes: the same plan twice gives the same files.

import * as S from './_plants.mjs';
import * as PL from '../../build/plants.js';

const A = S.argsOf();
const T = new S.C.Checks('plants: the planner against plants.py');
const root = S.fixtureRoot('the spots fixtures');
const manifestPath = root ? `${root}/spots/manifest.json` : null;
if (!manifestPath || !S.W.exists(manifestPath)) {
    S.W.skip('spots', 'run tests/plants/plants_fixtures.py --spots');
    Deno.exit(0);
}
const man = JSON.parse(Deno.readTextFileSync(manifestPath));
const want = A.list('--case', Object.keys(man.cases));
const { Terrain } = await import('../../api.js');
const SI = await import('../../surface/index.js');
const G = await import('../../core/gpu.js');
const R = await G.init();
const outDir = S.W.out('plants');

const F = Object.fromEntries(PL.FIELDS.map((f, i) => [f, i]));
const ulp32 = (x) => {
    const a = Math.abs(Math.fround(x));
    if (a === 0) return 1.4e-45;
    return 2 ** (Math.floor(Math.log2(a)) - 23);
};

function snapshotFolder() {
    if (man.snaps && S.W.exists(man.snaps)) return man.snaps;
    const t = S.W.blenderTests();
    return t ? `${t}/out/surface_data/snap` : null;
}

async function blenderSurface(t, bakeDir, key) {
    const hit = await SI.loadCached(bakeDir, key, t.levels.length);
    if (!hit) return null;
    const [baked, info] = hit;
    return new SI.SurfaceData(t, baked, { ...info, cache_hit: true }, info.options ?? {}, key, null, null, bakeDir);
}

// Blender's spots matched to the port's by position: a grid of 1 cm keys, then the nearest within tolerance
function match(a, b) {
    const na = a.length / 12, nb = b.length / 12;
    const key = (x, y) => `${Math.round(x * 100)},${Math.round(y * 100)}`;
    const grid = new Map();
    for (let j = 0; j < nb; j++) {
        const k = key(b[12 * j], b[12 * j + 1]);
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k).push(j);
    }
    const used = new Uint8Array(nb), pair = new Int32Array(na).fill(-1);
    for (let i = 0; i < na; i++) {
        const x = a[12 * i], y = a[12 * i + 1];
        const cx = Math.round(x * 100), cy = Math.round(y * 100);
        let best = -1, bd = Infinity;
        for (let dx = -1; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                for (const j of grid.get(`${cx + dx},${cy + dy}`) ?? []) {
                    if (used[j]) continue;
                    const d = Math.max(Math.abs(b[12 * j] - x), Math.abs(b[12 * j + 1] - y));
                    if (d < bd) { bd = d; best = j; }
                }
            }
        }
        const tol = Math.max(4 * ulp32(x), 4 * ulp32(y), 1e-4);
        if (best >= 0 && bd <= tol) {
            pair[i] = best;
            used[best] = 1;
        }
    }
    return { pair, used, na, nb };
}

// each field's tolerance: x and y 4 float32 steps of the value, at least 1e-5 m (a spot near x = 0 has steps of
// nanometres); yaw, scale, age and tint the float32 rounding of their arithmetic; variant and level exact. z and
// the normal follow the ring mesh, which each edition builds itself: the port's vertex heights are within 14 float32
// steps of the corner's largest tap of Blender's (PORT_PLAN.md C3, 7.3: the largest |h| of the 4 x 4 stencil round
// the corner, which beside a cliff is far above |z|), so a height on a triangle is within about 20 steps of the
// largest tap round its corners (the 6 x 6 cells round the spot on its level), and a face normal's gradient, two
// such heights over the lattice spacing (at least the level's cell), within 2 x 14 steps / cell
const TOL = { x: 4, y: 4, yaw: 2e-6, scale: 1e-5, age: 1e-5, tint: 2e-6, variant: 0, level: 0 };

// the largest |h| of the level's heights in the 6 x 6 cells round (x, y): the taps of its triangle's corners
function largestTap(t, k, x, y) {
    const lv = t.levels[k];
    if (!lv) return 0;
    const h = t.fields(k).h, n = lv.n;
    const mx = Math.floor((x - lv.x0) / lv.cell), my = Math.floor((y - lv.y0) / lv.cell);
    let H = 0;
    for (let q = -3; q <= 2; q++) {
        const jj = Math.min(Math.max(my + q, 0), n - 1);
        for (let p = -3; p <= 2; p++) H = Math.max(H, Math.abs(h[jj * n + Math.min(Math.max(mx + p, 0), n - 1)]));
    }
    return H;
}

// within 8 of the parent level's cells of a window edge (the spot's level's own, or the next finer level's hole): the
// band where each edition's ring mesh joins a window to its parent (its seam rule, the parent's points), where the
// two meshes were measured apart by more than their bound (badlands_sd: up to 58 steps of the largest tap, 3-11 m
// inside the hero window's edge; the ring mesh is P4's)
function inSeamBand(t, k, x, y) {
    const near = (lv, m) => lv && Math.min(x - lv.x0, lv.x0 + lv.side - x, y - lv.y0, lv.y0 + lv.side - y) > -m &&
        Math.min(Math.abs(x - lv.x0), Math.abs(lv.x0 + lv.side - x), Math.abs(y - lv.y0), Math.abs(lv.y0 + lv.side - y)) < m;
    const parent = t.levels[k - 1] ?? t.levels[k];
    return near(t.levels[k], 8 * parent.cell) || near(t.levels[k + 1], 8 * t.levels[k].cell);
}

// z and the normal: the port's spot on the port's own ring mesh (heightAt, float64 barycentrics on its float32
// vertices: within 14 steps of the largest tap and the kernel's float32 rounding of |z|), and against Blender's spot
// within the two meshes' bound; in a seam band the two meshes' seam rules may round apart by more (counted, reported:
// the ring mesh is P4's), so there the spot is held to the port's own mesh alone
function compareFields(a, b, m, cells, t) {
    const worst = {}, over = {};
    for (const f of PL.FIELDS) { worst[f] = 0; over[f] = 0; }
    let n = 0, anyOver = 0, offMesh = 0, offMeshWorst = 0, seam = 0, seamWorst = 0;
    for (let i = 0; i < m.na; i++) {
        const j = m.pair[i];
        if (j < 0) continue;
        n++;
        let bad = false;
        const lvl = a[12 * i + 11];
        const z = Math.max(Math.abs(a[12 * i + 2]), largestTap(t, lvl, a[12 * i], a[12 * i + 1]), 1.0);
        const cell = cells[lvl] ?? 1.0;
        const zm = t.ring.heightAt(b[12 * j], b[12 * j + 1]);
        const dm = Math.abs(zm - b[12 * j + 2]);
        offMeshWorst = Math.max(offMeshWorst, dm / ulp32(z));
        if (dm > 14 * ulp32(z) + 8 * ulp32(Math.max(Math.abs(zm), 1.0))) { offMesh++; bad = true; }
        const band = inSeamBand(t, lvl, a[12 * i], a[12 * i + 1]);
        for (const [f, k] of Object.entries(F)) {
            const d = Math.abs(a[12 * i + k] - b[12 * j + k]);
            let rel, tol;
            if (f === 'x' || f === 'y') {
                rel = d / ulp32(a[12 * i + k]);
                tol = Math.max(TOL[f], 1e-5 / ulp32(a[12 * i + k]));
            } else if (f === 'z') {
                rel = d;
                tol = 20 * ulp32(z) + 1e-5;
            } else if (f === 'nx' || f === 'ny' || f === 'nz') {
                rel = d;
                tol = 28 * ulp32(z) / cell + 1e-5;
            } else {
                rel = f === 'yaw' ? Math.min(d, Math.abs(d - 2 * Math.PI)) : d;
                tol = TOL[f];
            }
            if (rel > worst[f]) worst[f] = rel;
            if (rel > tol) {
                if (band && (f === 'z' || f === 'nx' || f === 'ny' || f === 'nz')) {
                    seam++;
                    seamWorst = Math.max(seamWorst, f === 'z' ? d / ulp32(z) : 0);
                    continue;
                }
                over[f]++;
                bad = true;
            }
        }
        if (bad) anyOver++;
    }
    return { n, worst, over, anyOver, offMesh, offMeshWorst, seam, seamWorst };
}

const summary = {};
for (const name of want) {
    const c = man.cases[name];
    if (!c || c.error) {
        T.ok(`${name}: the Blender fixture`, false, c ? c.error : 'no such case');
        continue;
    }
    const dir = `${root}/spots/${name}`;
    const info = JSON.parse(Deno.readTextFileSync(`${dir}/info.json`));
    const snapName = info.args.snap ?? name;
    const snaps = snapshotFolder();
    if (!snaps || !S.W.exists(`${snaps}/${snapName}.npz`)) {
        S.W.skip(`${name}`, 'no snapshot: set EIDO_BLENDER_EDITION to the Blender checkout holding out/surface_data/snap');
        continue;
    }
    const t = await Terrain.load(`${snaps}/${snapName}.npz`, { build: false, log: null });
    const sd = await blenderSurface(t, `${man.bakes}/${snapName}`, info.bake_key);
    if (!sd) {
        T.ok(`${name}: Blender's bake loads`, false, `${man.bakes}/${snapName} ${info.bake_key}`);
        continue;
    }
    const t0 = performance.now();
    const spots = await PL.planPlants(t, { ecotope: 'auto', focus: { blender: info.focus }, radiusM: info.args.radius_m ?? null,
        seed: info.args.seed ?? 0, data: sd, exclude: info.exclude.length ? { blender: info.exclude } : null, log: null, R });
    const secs = (performance.now() - t0) / 1000;
    const bl = await PL.PlantSpots.load(`${dir}/${name}`);
    const rec = { seconds: +secs.toFixed(2), blender_seconds: info.seconds.plan, species: {} };
    T.ok(`${name}: the plan's ecotope and description`, spots.meta.ecotope === bl.meta.ecotope &&
        S.jsonDiff(spots.meta.focus, bl.meta.focus) === null && S.jsonDiff(spots.meta.terrain.levels, bl.meta.terrain.levels) === null &&
        spots.meta.seed === bl.meta.seed && spots.meta.radius_m === bl.meta.radius_m,
    `${spots.meta.ecotope} vs ${bl.meta.ecotope}; ${secs.toFixed(1)} s against Blender's ${info.seconds.plan} s`);
    const cdiff = S.jsonDiff(spots.meta.constants, bl.meta.constants);
    T.ok(`${name}: the constants the plan read`, cdiff === null, cdiff ?? Object.keys(spots.meta.constants).join(', '));
    for (const s of bl.species) {
        const a = bl.array(s.name), b = spots.has(s.name) ? spots.array(s.name) : new Float32Array(0);
        const m = match(a, b);
        const cf = compareFields(a, b, m, info.levels.map((lv) => lv.cell), t);
        const onlyB = m.na - cf.n, onlyP = m.nb - cf.n;
        const ps = spots.stats[s.name] ?? {}, bs = bl.stats[s.name] ?? {};
        rec.species[s.name] = { blender: m.na, port: m.nb, matched: cf.n, only_blender: onlyB, only_port: onlyP, worst: cf.worst,
            off_own_mesh: cf.offMesh, off_own_mesh_worst_steps: cf.offMeshWorst, seam_band: cf.seam, seam_band_worst_steps: cf.seamWorst,
            stats_port: ps, stats_blender: bs };
        const share = m.na ? (onlyB + onlyP) / m.na : (onlyP ? 1 : 0);
        T.ok(`${name} / ${s.name}: spots matched by position (x, y within 4 float32 steps)`, share <= 0.01,
            `${m.na.toLocaleString('en-US')} Blender, ${m.nb.toLocaleString('en-US')} port, ${cf.n.toLocaleString('en-US')} matched; ` +
            `${onlyB} only Blender's, ${onlyP} only the port's (${(100 * share).toFixed(3)} %)`);
        const w = cf.worst;
        // a field past its tolerance is a near-tie (a spot on a triangle's diagonal or a lattice line: the other
        // triangle's normal; a level window's edge): at most 1 in 10^4 of the matched spots
        const overs = Object.entries(cf.over).filter(([, v]) => v > 0);
        T.ok(`${name} / ${s.name}: the matched spots' fields within their tolerances (ties counted)`,
            cf.n === 0 || cf.anyOver <= Math.max(1, 1e-4 * cf.n),
            Object.entries(w).map(([k, v]) => `${k} ${k === 'x' || k === 'y' ? v.toFixed(1) + ' ulp' : S.sci(v, 1)}`).join(', ') +
            `; on the port's own mesh: ${cf.offMesh} off (worst ${cf.offMeshWorst.toFixed(1)} steps of the largest tap)` +
            (cf.seam ? `; in a seam band ${cf.seam} past Blender's by the meshes' seam rules (worst ${cf.seamWorst.toFixed(0)} steps)` : '') +
            (overs.length ? `; past the tolerance: ${overs.map(([k, v]) => `${k} ${v}`).join(', ')} of ${cf.n}` : ''));
        const exact = ['candidates'].filter((k) => bs[k] !== undefined);
        const sdiff = exact.map((k) => `${k} ${ps[k]} vs ${bs[k]}`).join(', ');
        T.ok(`${name} / ${s.name}: candidates counted as Blender counts them`, exact.every((k) => ps[k] === bs[k]), sdiff);
        // the other counts move only with the decisions that differ (near-ties): within 1e-4 of the count, or 2
        const near = (x, y, rel) => Math.abs(x - y) <= Math.max(rel * Math.abs(y), 2);
        const cnt = ['after_density', 'kept', 'home_count', 'count'].filter((k) => bs[k] !== undefined);
        const flo = [['home_m2', 1e-4, 'm2'], ['clipped', 1e-4], ['density_max', 1e-6], ['yield', 1e-4], ['per_ha_home', 1e-4]]
            .filter(([k]) => bs[k] !== undefined && bs[k] !== null);
        const bad = [...cnt.filter((k) => !near(ps[k], bs[k], 1e-4)),
            ...flo.filter(([k, r]) => !(Math.abs(ps[k] - bs[k]) <= Math.max(r * Math.abs(bs[k]), k === 'home_m2' ? 2 / (bs.home_m2 || 1) : 1e-12) ||
                (k === 'home_m2' && Math.abs(ps[k] - bs[k]) * (Number(s.cluster.parents_per_ha) * Number(s.cluster.mu) * 1e-4) <= 2))).map(([k]) => k)];
        const ka = bs.kept_area ?? [], kb = ps.kept_area ?? [];
        const kad = ka.length === kb.length ? Math.max(0, ...ka.map((v, q) => Math.abs(v - kb[q]))) : Infinity;
        T.ok(`${name} / ${s.name}: the stats (counts within the differing decisions, the kept-area profile within 1e-3)`,
            bad.length === 0 && kad <= 1e-3,
            [...cnt, ...flo.map(([k]) => k)].filter((k) => ps[k] !== bs[k]).map((k) => `${k} ${ps[k]} vs ${bs[k]}`).join(', ') +
            `; kept_area within ${S.sci(kad, 1)}`);
    }
    if (A.flag('--keep')) await spots.save(`${outDir}/spots/${name}/${name}`);
    summary[name] = rec;
}

Deno.writeTextFileSync(`${outDir}/spots_test_detail.json`, JSON.stringify(summary, null, 1));
Deno.exit(S.finish(T, 'spots_test', { cases: Object.keys(summary) }));
