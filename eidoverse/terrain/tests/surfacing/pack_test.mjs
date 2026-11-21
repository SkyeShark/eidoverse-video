// The packed scans (build/surfacing.js packSet, scanNormalVariance; surfacing.py pack_set, scan_normal_variance): each
// CC0 set a palette reads packed from the shared texture library into this package's own cache
// (tests/out/surfacing/sets, or $EIDO_SURFACE_SETS), then beside the Blender edition's pack of the same set
// ($EIDO_BLENDER_EDITION's eidoverse/assets/cache/terrain_surface_sets: read, never written):
//   - the packed images' pixels: the albedo's RGB, the normal's x, y, the roughness and the AO are the source maps'
//     bytes as each edition's JPEG decoder gives them (Deno's against Blender's: a few levels apart on a JPEG, reported,
//     within 3 levels on the mean); the height byte by the normalisation, within 2 levels at p99;
//   - the stats: the mean linear albedo, roughness and AO within 2e-3 (both means over the same texels), the height's
//     mean and spread within 1e-3 of the spread, has_height and has_normal equal, the size equal;
//   - the normal variance: its total within 3 % and the loss curve's edges within 0.25 mip levels (one grid step is 0.1).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surfacing/pack_test.mjs
//         [--sets Rock019,Grass004] [--palettes desert_sandstone,alpine] [--no-force]
//     (a GPU job, behind $EIDO_GPU_WRAP on a shared machine)
//
// Writes tests/out/surfacing/pack_test.json. JavaScript per pixel here is test code.

import * as M from './_material.mjs';
import * as Sf from '../../build/surfacing.js';
import * as P from '../../build/palettes.js';

const A = M.argsOf();
const T = new M.C.Checks('surfacing: the packed scans against the Blender edition\'s');
const sets = M.useSets();
const pals = A.list('--palettes', null);
let names = A.list('--sets', null);
if (!names) {
    const want = new Set();
    for (const p of pals ?? Object.keys(P.PALETTES)) for (const L of P.get(p).layers) want.add(L.set);
    names = [...want].sort();
}
const G = await import('../../core/gpu.js');
const R = await G.init();
const blenderSets = M.W.blenderEdition() ? `${M.W.blenderEdition()}/eidoverse/assets/cache/terrain_surface_sets` : null;
const rec = {};
let worst = { lvl: 0, height: 0, stats: 0, total: 0, edge: 0 };
let allOk = true, compared = 0;
for (const name of names) {
    const t0 = performance.now();
    let dir;
    try {
        dir = await Sf.packSet(name, '2k', { force: !A.flag('--no-force'), R, log: null });
    } catch (e) {
        rec[name] = { error: String(e.message ?? e) };
        T.ok(`${name}: packed`, false, rec[name].error);
        allOk = false;
        continue;
    }
    const stats = (await Sf.packedSet(name, '2k', { R, log: null })).stats;
    const secs = (performance.now() - t0) / 1000;
    const r = { dir: dir.split('/').pop(), seconds: +secs.toFixed(2), size: stats.size };
    const bdir = blenderSets ? `${blenderSets}/${dir.split('/').pop()}` : null;
    if (!bdir || !M.W.exists(`${bdir}/stats.json`)) {
        r.blender = 'no Blender pack of this set';
        rec[name] = r;
        console.log(`[pack] ${name}: ${JSON.stringify(r)}`);
        continue;
    }
    compared++;
    const bs = JSON.parse(Deno.readTextFileSync(`${bdir}/stats.json`));
    // pixels
    const diffs = {};
    for (const img of ['albedo_height', 'normal_rough_ao']) {
        const a = await Sf.readImage(`${dir}/${img}.png`), b = await Sf.readImage(`${bdir}/${img}.png`);
        if (a.width !== b.width || a.height !== b.height) {
            diffs[img] = `sizes ${a.width}x${a.height} against ${b.width}x${b.height}`;
            continue;
        }
        const n = a.width * a.height;
        const per = [[], [], [], []];
        const sum = [0, 0, 0, 0], mx = [0, 0, 0, 0];
        for (let q = 0; q < n; q += 7) {
            for (let c = 0; c < 4; c++) {
                const d = Math.abs(a.data[4 * q + c] - b.data[4 * q + c]);
                per[c].push(d);
                sum[c] += d;
                mx[c] = Math.max(mx[c], d);
            }
        }
        diffs[img] = per.map((v, c) => ({ mean: +(sum[c] / v.length).toFixed(3), p99: M.percentile(v, 99), max: mx[c] }));
    }
    r.pixels = diffs;
    const ah = diffs.albedo_height, nr = diffs.normal_rough_ao;
    const meanLvl = typeof ah === 'string' ? Infinity : Math.max(...ah.slice(0, 3).map((d) => d.mean), ...(typeof nr === 'string' ? [Infinity] : nr.map((d) => d.mean)));
    const heightP99 = typeof ah === 'string' ? Infinity : ah[3].p99;
    // stats
    const sd = [
        ...stats.mean_albedo_linear.map((v, c) => Math.abs(v - bs.mean_albedo_linear[c])),
        Math.abs(stats.mean_roughness - bs.mean_roughness), Math.abs(stats.mean_ao - bs.mean_ao)];
    const hsd = Math.max(Math.abs(stats.height_mean - bs.height_mean), Math.abs(stats.height_std - bs.height_std)) / Math.max(bs.height_std, 1e-3);
    const nv = stats.normal_var, bnv = bs.normal_var ?? {};
    const totalRel = Math.abs(nv.total - bnv.total) / Math.max(bnv.total, 1e-9);
    const edge = Math.max(Math.abs(nv.a - bnv.a), Math.abs(nv.b - bnv.b));
    r.stats = { albedo_roughness_ao: sd.map((v) => M.C.sci(v, 2)), height: M.C.sci(hsd, 2), normal_total: M.C.sci(totalRel, 2),
        edges: [nv.a, nv.b, bnv.a, bnv.b], same_flags: stats.has_height === bs.has_height && stats.has_normal === bs.has_normal };
    const ok = meanLvl <= 3 && heightP99 <= 2 && Math.max(...sd) <= 2e-3 && hsd <= 1e-3 && totalRel <= 0.03 && edge <= 0.25
        && r.stats.same_flags && stats.size[0] === bs.size[0] && stats.size[1] === bs.size[1];
    if (!ok) allOk = false;
    worst = { lvl: Math.max(worst.lvl, meanLvl), height: Math.max(worst.height, heightP99), stats: Math.max(worst.stats, ...sd),
        total: Math.max(worst.total, totalRel), edge: Math.max(worst.edge, edge) };
    r.ok = ok;
    rec[name] = r;
    console.log(`[pack] ${name}: ${JSON.stringify(r)}`);
}
T.ok(`every set the palettes read packs from the CC0 library (${names.length} sets into ${sets})`,
    Object.values(rec).every((r) => !r.error), `${names.length} sets`);
T.ok('the packs equal the Blender edition\'s: pixels (the JPEG decoders\' few levels), stats, normal variance', allOk && compared > 0,
    `${compared} compared; worst mean pixel difference ${worst.lvl.toFixed(2)} levels, height p99 ${worst.height} levels, ` +
    `means ${M.C.sci(worst.stats, 2)}, normal variance total ${M.C.sci(worst.total, 2)} relative, loss-curve edges ${worst.edge.toFixed(2)} mip levels`);
G.shutdown();
Deno.exit(M.finish(T, 'pack_test', { sets: rec }));
