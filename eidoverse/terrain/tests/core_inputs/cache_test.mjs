// core/cache.js (PORT_PLAN.md 8.2, P2; C4, C8): the two code hashes over exactly the globs of C8 (on a tree with a
// file in every place the package has, each edit changing exactly the hash it should), the keys stable and
// sensitive, entries saved atomically and complete only after meta.json, loaded back bit for bit (float16 too),
// prune and clear counting and removing the files other layers keep in an entry (the surface bake's surface_*, the
// plant spots), least recently used first, reads counting as uses.
//
//     $EIDO_GPU_WRAP deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/core_inputs/cache_test.mjs

import * as G from '../../core/gpu.js';
import * as CA from '../../core/cache.js';
import * as L from '../../core/levels.js';
import { Fields } from '../../core/fields.js';
import { Recipe, Stage } from '../../core/recipe.js';
import { npArray } from '../../core/io.js';
import { Checks, bitsEqual, finish, sameJson, scratch } from './_common.mjs';

const T = new Checks('core_inputs/cache');
const TMP = scratch('eido_cache_test_');

// ---- the hashes' file sets, on a tree with a file in every place
const tree = `${TMP}/tree`;
const FILES = {
    field: ['core/a.js', 'core/levels.js', 'kernels/common.wgsl', 'kernels/route_area.wgsl', 'kernels/prims/p.wgsl',
        'kernels/grid/g.wgsl', 'kernels/compose/c.wgsl', 'kernels/hydro/h.wgsl', 'kernels/volcanic/v.wgsl',
        'kernels/impact/i.wgsl', 'kernels/strata/s.wgsl', 'kernels/karst/k.wgsl', 'kernels/glacial/g.wgsl',
        'kernels/detail/d.wgsl', 'solvers/fluvial.js', 'run.js'],
    terrain: ['recipes/canyon.js', 'recipes/index.js', 'masks.js', 'kernels/masks/slope.wgsl'],
    neither: ['api.js', 'index.js', 'bake.mjs', 'build/mesh.js', 'build/water.js', 'surface/bake.js', 'surface/kernels/blur.wgsl',
        'kernels/mesh/m.wgsl', 'kernels/water/w.wgsl', 'kernels/metrics/q.wgsl', 'tests/core_inputs/x.mjs', 'core/notes.md',
        'solvers/README.md', 'kernels/grid/g.glsl', 'PORT_PLAN.md'],
};
for (const f of [...FILES.field, ...FILES.terrain, ...FILES.neither]) {
    Deno.mkdirSync(`${tree}/${f.split('/').slice(0, -1).join('/')}`, { recursive: true });
    Deno.writeTextFileSync(`${tree}/${f}`, `// ${f}\n`);
}
T.ok('the field hash covers exactly core/*.js, kernels/*.wgsl, the solver kernels\' folders, solvers/*.js and run.js',
    sameJson(CA.codeFiles(CA.FIELD_GLOBS, tree), [...FILES.field].sort()), CA.codeFiles(CA.FIELD_GLOBS, tree).join(', '));
T.ok('the terrain hash covers exactly recipes/*.js, masks.js and kernels/masks/*.wgsl',
    sameJson(CA.codeFiles(CA.TERRAIN_GLOBS, tree), [...FILES.terrain].sort()), CA.codeFiles(CA.TERRAIN_GLOBS, tree).join(', '));
const h0 = [CA.codeHash(CA.FIELD_GLOBS, tree), CA.terrainCodeHash(CA.TERRAIN_GLOBS, tree)];
const moved = { field: 0, terrain: 0, neither: 0 }, wrong = [];
for (const [kind, list] of Object.entries(FILES)) {
    for (const f of list) {
        Deno.writeTextFileSync(`${tree}/${f}`, `// ${f} edited\n`);
        const h = [CA.codeHash(CA.FIELD_GLOBS, tree), CA.terrainCodeHash(CA.TERRAIN_GLOBS, tree)];
        const want = kind === 'field' ? [true, false] : kind === 'terrain' ? [false, true] : [false, false];
        if ((h[0] !== h0[0]) === want[0] && (h[1] !== h0[1]) === want[1]) moved[kind]++;
        else wrong.push(f);
        Deno.writeTextFileSync(`${tree}/${f}`, `// ${f}\n`);
    }
}
T.ok(`each edit moves exactly its hash: ${moved.field} field files, ${moved.terrain} terrain files, ${moved.neither} others ` +
    '(build/, api.js, index.js, bake.mjs, surface/, kernels/{mesh,water,metrics}/, tests, docs) move neither',
    !wrong.length, wrong.join(', '));
Deno.renameSync(`${tree}/core/a.js`, `${tree}/core/b.js`);
T.ok('a renamed field file moves the field hash (paths are hashed with the bytes, as cache.py does)', CA.codeHash(CA.FIELD_GLOBS, tree) !== h0[0]);
Deno.renameSync(`${tree}/core/b.js`, `${tree}/core/a.js`);

// ---- the real package
const files = CA.codeFiles();
const need = ['core/levels.js', 'core/gpu.js', 'kernels/common.wgsl', 'kernels/noise.wgsl', 'kernels/world_noise_field.wgsl',
    'kernels/grid/upsample2.wgsl', 'kernels/compose/uplift.wgsl', 'kernels/prims/lib.wgsl'];
T.ok(`the package's field hash: ${files.length} files, every core module and kernel of the wave in it, no test or probe`,
    need.every((f) => files.includes(f)) && !files.some((f) => f.startsWith('tests/')) && /^[0-9a-f]{40}$/.test(CA.codeHash()),
    `${CA.codeHash().slice(0, 12)}...`);
T.ok('the cache root is the package\'s eidoverse/assets/cache/terrain_threejs (Blender\'s terrain/ kept apart), or $EIDO_TERRAIN_THREEJS_CACHE',
    CA.root().endsWith('/eidoverse/assets/cache/terrain_threejs') || Deno.env.get('EIDO_TERRAIN_THREEJS_CACHE'), CA.root().split('/').slice(-4).join('/'));

// ---- keys (test_core.py's check)
const plan = L.planLevels(4000, 128, { context: 2, focus: [100, 100], hero: 4.0, warn: () => {} });
const rec = new Recipe('k', 't', [], {}, {}, [new Stage('fluvial', { K: 1e-5 })]);
const k1 = CA.makeKey(rec, { relief_m: 100 }, 4000, 128, 7, plan, [[100, 100]]);
const k2 = CA.makeKey(rec.toDict(), { relief_m: 100 }, 4000, 128, 7, plan.map((lv) => lv.toDict()), [[100, 100]]);
const k3 = CA.makeKey(rec, { relief_m: 100 }, 4000, 128, 8, plan, [[100, 100]]);
const k4 = CA.makeKey(rec, { relief_m: 100 }, 4000, 128, 7, plan, [[100, 100]], { sea_level: 0 });
T.ok('cache keys stable (a Recipe or its dict, Levels or their dicts) and sensitive (seed, extra), SHA-1 hex',
    k1 === k2 && k1 !== k3 && k1 !== k4 && /^[0-9a-f]{40}$/.test(k1));

// ---- entries
const R = await G.init();
const base = `${TMP}/cache`;
const c = new CA.Cache(k1, base);
const n0 = plan[0].n;
const h = new Float32Array(n0 * n0);
for (let i = 0; i < h.length; i++) h[i] = Math.sin(i * 0.37) * 100 + (i % 7) * 1e-3;   // test data
const f0 = new Fields(plan[0], { h, A: 1.0 }, R);
await c.saveLevel(0, f0);
T.ok('an entry is not complete before meta.json', !c.complete());
const m16 = new Float16Array(plan[1].n * plan[1].n).map((_, i) => (i % 1000) / 999);
await c.saveLevel(1, { f__h: npArray(new Float32Array(plan[1].n * plan[1].n), plan[1].shape), m__slope: npArray(m16, plan[1].shape) });
c.writeMeta({ levels: 2, plan });
const left = [...Deno.readDirSync(c.path)].map((e) => e.name).filter((n) => n.includes('.tmp'));
T.ok('complete() after meta.json; no temporary files left (written to a temporary name, renamed into place)', c.complete() && !left.length, left.join(', '));
const g = await c.loadLevel(0, plan[0], R);
const back = await g.toHost();
T.ok('a level loads back as a Fields on its level, bit for bit', g.level === plan[0] && bitsEqual(back.h, h) && back.A.every((v) => v === 1));
const arrays = await c.loadLevel(1);
const g1 = await c.loadLevel(1, plan[1], R);
const s16 = await R.read(g1.m__slope);
T.ok('float16 arrays load as float16 arrays, and onto the GPU exactly', arrays.m__slope.dtype === '<f2' &&
    s16.every((v, i) => v === m16[i]));
g.dispose();
g1.dispose();
f0.dispose();
const meta = c.readMeta();
T.ok('meta.json carries the key, version, code hash and time', meta.key === k1 && meta.version === CA.TERRAIN_CODE_VERSION &&
    meta.code === CA.codeHash() && /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/.test(meta.written) && meta.levels === 2);

// ---- prune and clear, with the files other layers keep in an entry
const a = new CA.Cache('a'.repeat(40), base);
await a.saveLevel(0, { f__h: npArray(new Float32Array(64 * 64), [64, 64]) });
a.writeMeta({ levels: 1 });
Deno.writeFileSync(`${a.path}/surface_${'c'.repeat(16)}_L0.npz`, new Uint8Array(300000));
Deno.writeTextFileSync(`${a.path}/plants_${'d'.repeat(16)}.plants.json`, '{"format": "eidoverse-terrain-plants/1"}');
Deno.writeFileSync(`${a.path}/plants_${'d'.repeat(16)}.plants.spruce.f32`, new Uint8Array(48 * 1000));
const sizeA = a.sizeBytes();
const listed = [...Deno.readDirSync(a.path)].filter((e) => e.isFile).reduce((s, e) => s + Deno.statSync(`${a.path}/${e.name}`).size, 0);
T.ok('an entry\'s size counts every file at its top level: levels, meta, surface_*.npz and the plant spots', sizeA === listed && sizeA > 348000,
    `${sizeA} bytes`);
const old = new Date(Date.now() - 3600e3);
Deno.utimeSync(a.metaPath, old, old);
const sizeC = c.sizeBytes();
const es = CA.entries(base);
T.ok('entries() oldest first', es.length === 2 && es[0].cache.key === a.key && es[1].cache.key === k1);
let freed = CA.prune({ keepGb: (sizeC + 1000) / 1e9, base });
const after = CA.entries(base).map((e) => e.cache.key);
T.ok('prune removes the least recently used entries, with their surface and plant files, until the cache fits',
    freed === sizeA && sameJson(after, [k1]), `freed ${freed} of ${sizeA}`);
Deno.utimeSync(c.metaPath, old, old);
c.readMeta();
T.ok('a read counts as a use (meta.json touched)', Date.now() - Deno.statSync(c.metaPath).mtime.getTime() < 60e3);
freed = CA.clear({ base });
T.ok('clear() removes every entry', freed === sizeC && CA.entries(base).length === 0);

try {
    if (!Deno.env.get('EIDO_TEST_SCRATCH')) Deno.removeSync(TMP, { recursive: true });
} catch (_e) { /* fine */ }
G.shutdown();
Deno.exit(finish(T, 'cache_test.json'));
