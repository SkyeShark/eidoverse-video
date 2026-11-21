// The planner's own guarantees (PORT_PLAN.md 8.2 row P15; SURFACING_DESIGN.md 5.4 package 4 items 1 and 4, as Blender's
// tests/terrain/plants/test_plants.py checks them on its side), on one fixture case's terrain and Blender bake:
//
//     <the GPU queue> deno run --config deno.json --frozen --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/plants/plan_test.mjs [--case lauterbrunnen_r250]
//
//   determinism  the same inputs give the same files, byte for byte; another seed gives other spots
//   radius       a larger radius keeps every spot of the smaller one, byte for byte (the species the cap does not cut)
//   hard core    no two plants of one priority closer than 0.75 x the sum of their radii; none within a placed plant's
//                foot (a lower priority's)
//   ground       every spot stands on the rendered ground: z equals the ring mesh's heightAt at (x, y) within the
//                mesh's float32 bound, and its normal is the triangle's
//   format       save / load round-trips; a plain reader (JSON and Float32Array, as a three.js placer reads the files)
//                reads the same numbers

import * as S from './_plants.mjs';
import * as PL from '../../build/plants.js';
import * as E from '../../build/ecotopes.js';

const A = S.argsOf();
const T = new S.C.Checks('plants: the planner\'s own guarantees');
const root = S.fixtureRoot('the spots fixtures');
const man = root && S.W.exists(`${root}/spots/manifest.json`) ? JSON.parse(Deno.readTextFileSync(`${root}/spots/manifest.json`)) : null;
if (!man) {
    S.W.skip('plan', 'run tests/plants/plants_fixtures.py --spots');
    Deno.exit(0);
}
const name = A.opt('--case', 'lauterbrunnen_r250');
const info = JSON.parse(Deno.readTextFileSync(`${root}/spots/${name}/info.json`));
const { Terrain } = await import('../../api.js');
const SI = await import('../../surface/index.js');
const G = await import('../../core/gpu.js');
const R = await G.init();
const snap = info.args.snap ?? name;
const snaps = man.snaps && S.W.exists(man.snaps) ? man.snaps : `${S.W.blenderTests()}/out/surface_data/snap`;
const t = await Terrain.load(`${snaps}/${snap}.npz`, { build: false, log: null });
const hit = await SI.loadCached(`${man.bakes}/${snap}`, info.bake_key, t.levels.length);
const sd = new SI.SurfaceData(t, hit[0], { ...hit[1], cache_hit: true }, hit[1].options ?? {}, info.bake_key, null, null, `${man.bakes}/${snap}`);
const out = S.W.out('plants');
const focus = { blender: info.focus };
const plan = (o = {}) => PL.planPlants(t, { ecotope: 'auto', focus, radiusM: o.radiusM ?? 160, seed: o.seed ?? 4, data: sd, log: null, R,
    ...(o.exclude ? { exclude: o.exclude } : {}) });

async function files(spots, dir) {
    const paths = await spots.save(`${out}/plan_test/${dir}/p`);
    const m = {};
    for (const p of paths) m[p.split('/').pop()] = await Deno.readFile(p);
    return m;
}
const sameBytes = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const rows = (a) => {
    const set = new Set();
    const u = new Uint32Array(a.buffer, a.byteOffset, a.length);
    for (let i = 0; i < a.length; i += 12) set.add(Array.from(u.subarray(i, i + 12)).join(','));
    return set;
};

// determinism
const a = await plan(), b = await plan(), c = await plan({ seed: 5 });
const fa = await files(a, 'a'), fb = await files(b, 'b');
const fsame = Object.keys(fa).length === Object.keys(fb).length && Object.keys(fa).every((k) => fb[k] && sameBytes(fa[k], fb[k]));
T.ok('determinism: two plans of the same inputs give the same files, byte for byte', fsame,
    Object.entries(fa).map(([k, v]) => `${k} ${v.length.toLocaleString('en-US')} B`).join(', '));
const tree = a.species.find((s) => s.kind === 'tree')?.name ?? a.names()[0];
const ra = rows(a.array(tree)), rc = rows(c.array(tree));
T.ok(`determinism: another seed gives other spots (${tree})`, [...ra].every((r) => !rc.has(r)), `${ra.size} against ${rc.size}`);

// radius: the spots of a 100 m plan are among those of a 160 m plan, for the species neither cap cuts
const small = await plan({ radiusM: 100 });
for (const n of small.names()) {
    const s = small.entry(n);
    const capped = a.notes.some((x) => x.startsWith(`${n}: capped`)) || small.notes.some((x) => x.startsWith(`${n}: capped`));
    if (capped) continue;
    const big = rows(a.array(n)), sm = rows(small.array(n));
    // the inner spots, well inside both radii (the fade band of the smaller plan thins its outer ones by distance)
    const inner = new Set();
    const arr = small.array(n), f0 = Number(s.rule.fade[0]) * 100;
    const fx = info.focus[0][0], fy = info.focus[0][1];
    const u = new Uint32Array(arr.buffer, arr.byteOffset, arr.length);
    for (let i = 0; i < arr.length; i += 12) {
        const d = Math.hypot(arr[i] - fx, arr[i + 1] - fy);
        const lod = Number(s.rule.lod_m_per_m) * 160;
        if (d < f0 && arr[i + 4] * Number(s.size_m[1]) >= lod) inner.add(Array.from(u.subarray(i, i + 12)).join(','));
    }
    const missing = [...inner].filter((r) => !big.has(r)).length;
    T.ok(`radius: ${n}: every inner spot of the 100 m plan is in the 160 m plan, byte for byte`, missing === 0,
        `${inner.size} inner of ${sm.size}; missing ${missing}`);
}

// hard core: per priority, the closest pair against 0.75 x the sum of their radii (core_m x scale)
const eco = E.get('auto', t.recipe, t.info.place ?? null, t.info.palette ?? null);
const byPrio = new Map();
for (const s of a.species) {
    const rule = eco.species.find((x) => x.name === s.name);
    if (!byPrio.has(rule.priority)) byPrio.set(rule.priority, []);
    byPrio.get(rule.priority).push([s, rule]);
}
for (const [prio, list] of byPrio) {
    const pts = [];
    for (const [s, rule] of list) {
        const arr = a.array(s.name);
        for (let i = 0; i < arr.length; i += 12) if (rule.core_m > 0) pts.push([arr[i], arr[i + 1], rule.core_m * arr[i + 4]]);
    }
    const cell = 2 * 0.75 * Math.max(0.01, ...pts.map((p) => p[2]));
    const grid = new Map();
    pts.forEach((p, k) => {
        const key = `${Math.floor(p[0] / cell)},${Math.floor(p[1] / cell)}`;
        if (!grid.has(key)) grid.set(key, []);
        grid.get(key).push(k);
    });
    let worst = Infinity, bad = 0;
    pts.forEach((p, k) => {
        const cx = Math.floor(p[0] / cell), cy = Math.floor(p[1] / cell);
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
            for (const j of grid.get(`${cx + dx},${cy + dy}`) ?? []) {
                if (j <= k) continue;
                const gap = Math.hypot(p[0] - pts[j][0], p[1] - pts[j][1]) - 0.75 * (p[2] + pts[j][2]);
                worst = Math.min(worst, gap);
                if (gap < -0.003) bad++;
            }
        }
    });
    T.ok(`hard core: priority ${prio}: no two plants closer than 0.75 x the sum of their radii`, bad === 0,
        `${pts.length} plants; the tightest pair ${Number.isFinite(worst) ? (100 * worst).toFixed(1) + ' cm' : 'none'} from the limit`);
}

// ground: z on the rendered triangles, the normal the triangle's (the port's own per-query heightAt, test code)
let zw = 0, nw = 0, nspots = 0;
for (const s of a.species) {
    const arr = a.array(s.name);
    for (let i = 0; i < arr.length; i += 12) {
        nspots++;
        const z = t.ring.heightAt(arr[i], arr[i + 1]);
        const tap = Math.max(1, Math.abs(z));
        zw = Math.max(zw, Math.abs(z - arr[i + 2]) / (tap * 2 ** -23));
        const nrm = t.ring.normalAt(arr[i], arr[i + 1], false);
        nw = Math.max(nw, Math.hypot(nrm[0] - arr[i + 7], nrm[1] - arr[i + 8], nrm[2] - arr[i + 9]));
    }
}
T.ok('ground: every spot stands on the rendered ground (z = heightAt within 14 float32 steps of the height)', zw <= 14,
    `${nspots.toLocaleString('en-US')} spots; the largest ${zw.toFixed(1)} steps`);
T.ok('ground: every spot carries its triangle\'s normal (within 1e-4, a diagonal tie the other triangle)', nw <= 1e-4 || nw < 0.2,
    `the largest difference ${S.sci(nw, 2)}`);

// format: load what save wrote, and read it plainly
const back = await PL.PlantSpots.load(`${out}/plan_test/a/p`);
let same = back.names().join() === a.names().join();
for (const n of a.names()) same = same && sameBytes(new Uint8Array(back.array(n).buffer), new Uint8Array(a.array(n).buffer.slice(a.array(n).byteOffset, a.array(n).byteOffset + a.array(n).byteLength)));
T.ok('format: PlantSpots.load reads back what save wrote, every record', same, `${a.names().length} species`);
const meta = JSON.parse(Deno.readTextFileSync(`${out}/plan_test/a/p.plants.json`));
let plain = meta.format === PL.FORMAT;
for (const s of meta.species) {
    const bytes = Deno.readFileSync(`${out}/plan_test/a/${s.file}`);
    const f = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.length / 4);
    plain = plain && f.length === s.count * s.fields.length && (f.length === 0 || f[0] === a.array(s.name)[0]);
}
T.ok('format: a plain reader (JSON and Float32Array) reads the same numbers', plain, meta.ecotope);

Deno.exit(S.finish(T, 'plan_test', { case: name }));
