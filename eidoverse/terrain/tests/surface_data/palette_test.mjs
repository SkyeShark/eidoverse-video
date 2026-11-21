// C and P against Blender's palette bake (PORT_PLAN.md 8.2 row P14: "C and P within 1/255"; SURFACING_DESIGN.md
// 5.4, package 1): on each bake case, the port's palette bake (surface/palette_bake.js: the far colour C, then the
// provenance colour P always) runs on Blender's own stored bake of the case and is compared, map by map and level by
// level, with Blender's palette bake of the same stored bake at the pinned commit (tests/surface_data/
// blender_bakes.py: the same bytes in, both palette bakes read them as a cache hit), both as the cache keeps them
// (float16, linear).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/palette_test.mjs
//         [--case toroweap,canyon,...]
//     (on a shared machine, behind $EIDO_GPU_WRAP; $EIDO_BLENDER_EDITION: the Blender edition, for the snapshots and
//     the packed scan sets' stats.json, which far_colour reads: $EIDO_SURFACE_SETS is pointed there)
//
// The grade: every texel of every map within 1/255 of Blender's but for a share of at most SHARE (a cell whose
// formation sits within float32's rounding of a top, a routing flip), the largest difference reported. Records the
// seconds beside Blender's (the cost, design section 7). Writes tests/out/surface_data/palette_test.json. JavaScript
// per texel here is test code.

import * as SI from '../../surface/index.js';
import * as B from '../../surface/bake.js';
import * as PB from '../../surface/palette_bake.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const A = S.argsOf();
const T = new S.C.Checks('surface_data: C and P against Blender\'s palette bake');
const CASES = ['toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon', 'alpine_valley',
    'fluvial_range'];
const TOL = 1 / 255;
const SHARE = 0.005;
const cases = A.list('--case', CASES);
const edition = S.W.needBlenderEdition('the bake cases\' snapshots');
const root = S.fixtureRoot();
const recFile = root ? `${root}/bakes/palette_bake.json` : null;
if (!recFile || !S.W.exists(recFile)) {
    T.ok('Blender palette bakes present', false, 'make them: tests/surface_data/blender_bakes.py (in Blender)');
    Deno.exit(S.finish(T, 'palette_test'));
}
if (edition && !Deno.env.get('EIDO_SURFACE_SETS')) Deno.env.set('EIDO_SURFACE_SETS', `${edition}/eidoverse/assets/cache/terrain_surface_sets`);
const recs = JSON.parse(Deno.readTextFileSync(recFile)).cases;
const results = {};
const { Terrain, NpzFile } = await import('../../api.js');
const R = await G.init();

const val = (a, k) => Number(a.data[k]);

for (const name of cases) {
    const rec = recs[name];
    const dir = `${root}/bakes/${name}`;
    const snap = edition ? `${S.W.blenderTests()}/out/surface_data/snap/${name}.npz` : null;
    if (!rec || rec.error || !snap || !S.W.exists(snap)) {
        T.ok(`${name}: Blender's palette bake and the snapshot present`, false, rec?.error ?? `snapshot ${snap}`);
        continue;
    }
    const t = await Terrain.load(snap, { build: false, log: null });
    const hit = await SI.loadCached(dir, rec.key, t.levels.length);
    if (!hit) {
        T.ok(`${name}: Blender's stored bake loads`, false, dir);
        continue;
    }
    const [baked, info] = hit;
    const pal = await B.resolvePalette(t, rec.palette);
    const sd = new SI.SurfaceData(t, baked, { ...info, cache_hit: true }, info.options, rec.key, pal, null, null);
    sd._palettes = await B.palettesModule();
    const t0 = performance.now();
    const out = await PB.bake(sd, pal, { cache: null, pMode: true, log: null, R });
    const seconds = (performance.now() - t0) / 1000;
    const row = { case: name, palette: pal.name ?? rec.palette, blender_tag: rec.tag, port_tag: sd._colourTag,
        port_seconds: +seconds.toFixed(2), port: sd.info.palette_bake, blender_seconds: rec.seconds, blender: rec.palette_bake,
        levels: [] };
    const bad = [];
    let worst = 0, worstAt = '', worstShare = 0, n = 0;
    for (let i = 0; i < t.levels.length; i++) {
        const bz = await NpzFile.open(`${dir}/surface_${rec.key}_${rec.tag}_L${i}.npz`);
        const lrow = { level: i, role: t.levels[i].role, maps: {} };
        for (const nm of bz.names) {
            const b = bz.read(nm), p = out[i].get(nm);
            if (!p) {
                bad.push(`L${i} ${nm}: not made by the port`);
                continue;
            }
            if (p.data.length !== b.data.length) {
                bad.push(`L${i} ${nm}: ${p.shape} against ${b.shape}`);
                continue;
            }
            let mx = 0, at = -1, past = 0;
            for (let k = 0; k < b.data.length; k++) {
                const d = Math.abs(val(p, k) - val(b, k));
                if (d > mx || Number.isNaN(d)) { mx = Number.isNaN(d) ? Infinity : d; at = k; }
                if (!(d <= TOL)) past++;
            }
            const share = past / b.data.length;
            lrow.maps[nm] = { max: mx, at, share, texels: b.data.length };
            n++;
            if (mx > worst) { worst = mx; worstAt = `L${i} ${nm}`; }
            if (share > worstShare) worstShare = share;
            if (share > SHARE) bad.push(`L${i} ${nm}: ${(100 * share).toFixed(2)} % past 1/255 (max ${mx.toFixed(4)})`);
        }
        const extra = [...out[i].keys()].filter((k) => !bz.names.includes(k));
        if (extra.length) bad.push(`L${i}: the port made ${extra.join(', ')}, Blender did not`);
        row.levels.push(lrow);
    }
    row.bad = bad;
    T.ok(`${name}: C and P (${n} maps on ${t.levels.length} levels) within 1/255 of Blender's (share past it <= ${SHARE})`,
        bad.length === 0, bad.length ? bad.slice(0, 4).join('; ')
            : `largest ${(worst * 255).toFixed(2)}/255 (${worstAt}), worst share past ${(100 * worstShare).toFixed(3)} %; ` +
            `${seconds.toFixed(1)} s against Blender's ${rec.seconds} s`);
    results[name] = row;
    t.dispose?.();
}

G.shutdown();
Deno.exit(S.finish(T, 'palette_test', { results }));
