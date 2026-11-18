// A cache hit at film quality (PORT_PLAN.md 8.2 P4: "a cache hit at film quality in under 5 s"), and bake.mjs on it.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/cache_hit_test.mjs [case ...]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). The level runner (run.js) is another
// package's, so nothing here fills the cache by generating: each case's entry is written from a Blender save
// (bake.py --save) as makeTerrain writes one (every level's fields as f__<name> and masks as m__<name>, in the
// dtypes the save holds, then meta.json last), under the key resolveCall() gives for the call the save records, in
// the test's own cache root (out/mesh_api/cache/, through $EIDO_TERRAIN_THREEJS_CACHE). Per case:
//   key     resolveCall() of the save's call gives the save's level plan and knobs: the entry is that call's
//   hit     makeTerrain finds it (info.cache_hit) and returns the Terrain with its mesh, collider proxy and water in
//           under 5 s from the call; its heights are the save's (heightAt equal to Terrain.load's at 2,000 points)
//   miss    the same call with another seed does not hit; while run.js is not in the checkout, the miss says so,
//           naming the module and Terrain.load
//   bake    bake.mjs on the same call (in this process): a cache hit, the preview PNGs and <name>_bake.json written

import * as G from '../../core/gpu.js';
import * as A from '../../api.js';
import * as Ch from '../../core/cache.js';
import { Terrain, makeTerrain } from '../../index.js';
import { main as bakeMain } from '../../bake.mjs';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const cases = C.fixtureCases(args.length ? args : ['lauterbrunnen_film'], C.API_FIXTURES);
if (!cases) Deno.exit(0);
const ROOT = C.urlPath(C.outUrl('cache/.keep')).replace(/\/\.keep$/, '');
Deno.env.set('EIDO_TERRAIN_THREEJS_CACHE', ROOT);
await G.init();
const T = new C.Checks('mesh and API: a cache hit at film quality, and bake.mjs');
T.extra.cases = {};
const quiet = () => {};
const runJs = (() => {
    try {
        Deno.statSync(new URL('run.js', C.TERRAIN));
        return true;
    } catch (_e) {
        return false;
    }
})();

// the makeTerrain call a Blender save records (three.js frame: focus [x, -y])
function callOf(meta) {
    return { recipe: meta.recipe, params: meta.knobs, seed: meta.seed, quality: meta.quality, size: meta.size,
        resolution: meta.resolution, heroCell: meta.hero_cell, context: meta.context,
        focus: meta.focus ? meta.focus.map(([x, y]) => [x, -y]) : null, seaLevel: meta.sea_level,
        baseElevationM: meta.base_elevation_m, name: 'ground', log: quiet };
}

async function checkCase(name) {
    const man = C.manifest(name, C.API_FIXTURES);
    const base = C.blenderPath(man.save);
    const meta = JSON.parse(Deno.readTextFileSync(base + '.json'));
    const tag = (s) => `${name}: ${s}`;
    const rec = {};
    T.extra.cases[name] = rec;
    const call = callOf(meta);

    // the key: the save's call resolves to the save's plan
    const rc = await A.resolveCall(call);
    const planOk = C.sameJson(JSON.parse(JSON.stringify(rc.plan.map((lv) => lv.toDict()))), meta.plan);
    T.ok(tag('key: resolveCall() of the save\'s call gives the save\'s level plan and knobs'),
        planOk && C.sameJson(JSON.parse(JSON.stringify(rc.values)), meta.knobs),
        `${rc.plan.length} levels; key ${rc.key}`);
    rec.key = rc.key;

    // the entry, written from the save as makeTerrain writes one (the arrays copied through, entry by entry)
    Ch.clear({ base: ROOT });
    const t0 = performance.now();
    const npz = await A.NpzFile.open(base + '.npz');
    const entry = new Ch.Cache(rc.key);
    let arraysN = 0;
    for (let i = 0; i < rc.plan.length; i++) {
        const arrays = {};
        for (const k of npz.names) {
            const a = k.indexOf('__'), b = k.indexOf('__', a + 2);
            if (parseInt(k.slice(1, a), 10) !== i) continue;
            arrays[`${k.slice(a + 2, b)}__${k.slice(b + 2)}`] = npz.read(k);
            arraysN++;
        }
        await entry.saveLevel(i, arrays);
    }
    entry.writeMeta({ recipe: meta.recipe_name ?? meta.recipe.name, knobs: meta.knobs, size: meta.size,
        resolution: meta.resolution, seed: meta.seed, levels: rc.plan.length, plan: rc.plan, focus: rc.focusList,
        flats: meta.flats ?? [], skipped: meta.skipped_stages ?? [] });
    rec.seed_entry_s = +((performance.now() - t0) / 1000).toFixed(2);
    rec.entry_gb = +(entry.sizeBytes() / 1e9).toFixed(3);

    // the hit
    const t1 = performance.now();
    const t = await makeTerrain(call);
    const secs = (performance.now() - t1) / 1000;
    rec.hit_s = +secs.toFixed(3);
    rec.seconds = t.info.seconds;
    T.ok(tag('hit: makeTerrain reads the entry and returns the Terrain (mesh, collider proxy, water) in under 5 s'),
        t.info.cache_hit === true && t.info.cache_key === rc.key && secs < 5.0 && t.mesh?.isMesh === true && t.collider?.isMesh === true,
        `${secs.toFixed(2)} s (${Object.entries(t.info.seconds).map(([k, v]) => `${k} ${v}`).join(', ')}); ${arraysN} arrays, ` +
        `${rec.entry_gb} GB entry; ${t.ring.triangleCount.toLocaleString('en-US')} triangles`);
    const ref = await Terrain.load(base, { build: false, plants: false });
    const rnd = C.lcg(5);
    const [xmin, ymin, xmax, ymax] = ref.ring.bounds();
    let same = true, worst = 0;
    for (let q = 0; q < 2000; q++) {
        const x = xmin + rnd() * (xmax - xmin), z = -(ymin + rnd() * (ymax - ymin));
        const a = t.heightAt(x, z), b = ref.heightAt(x, z);
        if (a !== b) same = false;
        worst = Math.max(worst, Math.abs(a - b));
    }
    T.ok(tag('hit: the heights are the save\'s (heightAt equal to Terrain.load\'s at 2,000 points)'), same, `worst ${worst} m`);
    ref.dispose();
    t.dispose();

    // a miss
    const r = await C.throwsWith(() => makeTerrain({ ...call, seed: meta.seed + 1 }), runJs ? [] : ['run.js', 'Terrain.load'], runJs ? null : 'NotPortedError');
    T.ok(tag(runJs ? 'miss: another seed does not hit the entry' : 'miss: another seed misses, and without run.js the miss names it and Terrain.load'),
        runJs ? true : r.ok, runJs ? 'run.js is in the checkout: not tried (it would generate)' : r.message.slice(0, 200));

    // bake.mjs on the same call
    const out = C.urlPath(C.outUrl(`bake/${name}/.keep`)).replace(/\/\.keep$/, '');
    const recipeFile = `${out}/recipe.json`;
    await Deno.mkdir(out, { recursive: true });
    await Deno.writeTextFile(recipeFile, JSON.stringify(meta.recipe));
    const argv = ['--recipe', recipeFile, '--seed', String(meta.seed), '--quality', meta.quality, '--size', String(meta.size),
        '--resolution', String(meta.resolution), '--hero-cell', String(meta.hero_cell), '--context', String(meta.context),
        '--params', JSON.stringify(meta.knobs), '--out', out, '--name', name];
    if (call.focus) argv.push('--focus', call.focus.map((p) => p.join(',')).join(';'));
    const tb = performance.now();
    const code = await bakeMain(argv);
    rec.bake_s = +((performance.now() - tb) / 1000).toFixed(2);
    let bake = null;
    try {
        bake = JSON.parse(Deno.readTextFileSync(`${out}/${name}_bake.json`));
    } catch (_e) { /* not written */ }
    const pngs = bake?.files?.filter((f) => f.endsWith('.png')) ?? [];
    T.ok(tag('bake: bake.mjs on the save\'s call hits the cache and writes the preview PNGs and <name>_bake.json'),
        code === 0 && bake?.cache_hit === true && bake.cache_key === rc.key && pngs.length >= 2 && pngs.every((f) => C.W.exists(f)) &&
        bake.levels.length === rc.plan.length && bake.triangles > 0,
        bake ? `exit ${code} in ${rec.bake_s} s; ${pngs.length} PNGs; metrics ${bake.metrics?.error ?? Object.keys(bake.metrics ?? {}).length + ' numbers'}` : `exit ${code}, no record`);
    rec.bake = bake ? { cache_hit: bake.cache_hit, files: bake.files.map((f) => f.split('/').pop()), metrics: bake.metrics } : null;
    Ch.clear({ base: ROOT });
}

for (const name of cases) {
    try {
        await checkCase(name);
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 8).join('\n')}`);
    }
}
G.shutdown();
Deno.exit(C.finish(T, 'cache_hit_test.json'));
