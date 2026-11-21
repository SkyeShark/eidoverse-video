// Every map of Blender-made terrains against Blender's own bake (PORT_PLAN.md 8.2 row P14; SURFACING_DESIGN.md 5.4,
// package 1): the Blender surface_data package's bake cases (its snapshots, blender/tests/terrain/out/surface_data/
// snap/<case>.npz, Terrain.save files read by api.js), baked by the port with the options Blender's bake of the same
// snapshot recorded, every stored map of every level compared with Blender's, decoded from both caches' files.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/bake_test.mjs
//         [--case toroweap,canyon,...] [--blender <folder of Blender bakes: <folder>/<case>/surface_<key>*.npz>]
//         [--keep]
//     (on a shared machine, behind $EIDO_GPU_WRAP; $EIDO_BLENDER_EDITION: the Blender edition, for the snapshots)
//
// The Blender bakes: --blender, else tests/out/surface_data/fixtures/<key>/bakes (tests/surface_data/blender_bakes.py:
// Blender's bake_surface at the pinned commit on the same snapshots), else the Blender package's own cache
// (blender/tests/terrain/out/surface_data/cache/<case>). The options come from that bake's json, so the comparison
// is of the bake, not of the palettes that set its options (build/palettes.js has its own test).
//
// The grade (the twin grade, 1e-4 of each map's range, on the maps as the cache stores them): a map kept in 8 bits
// (E, M) may differ by one step of its encoding where the two editions' float32 values sit either side of a
// rounding (a correct port's 1e-4 crosses one on about 2.5 % of the texels), never by more; a half-float map (D, F)
// within max(1e-4 of its range, two half-float steps of the value). Discrete decisions that turn on a last bit
// (provenance's neighbour draws, a convergence chunk) can move a few texels further: each map reports the share of
// its texels past the grade, which the check holds under GRADE_SHARE.
//
// Writes tests/out/surface_data/bake_test.json (per case, level and map: the largest difference, its share past the
// grade, the range) and keeps the port's bakes in tests/out/surface_data/bakes/<case>/ (--keep: across runs, as a
// cache). JavaScript per texel here is test code.

import * as SI from '../../surface/index.js';
import * as MP from '../../surface/maps.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const A = S.argsOf();
const T = new S.C.Checks('surface_data: maps against Blender\'s bake');
const CASES = ['toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon', 'alpine_valley',
    'fluvial_range'];
const GRADE_SHARE = 0.005;                // at most this share of a map's texels past its grade
const cases = A.list('--case', CASES);
const edition = S.W.needBlenderEdition('the bake cases\' snapshots');
const results = {};

function blenderBakeDir(name) {
    const given = A.opt('--blender');
    if (given) return `${given}/${name}`;
    const root = S.fixtureRoot();
    if (root && S.W.exists(`${root}/bakes/${name}`)) return `${root}/bakes/${name}`;
    return edition ? `${S.W.blenderTests()}/out/surface_data/cache/${name}` : null;
}

function bakeInfo(dir) {
    for (const e of Deno.readDirSync(dir)) {
        if (e.isFile && e.name.startsWith('surface_') && e.name.endsWith('.json') && !e.name.includes('_pal')) {
            return { key: e.name.slice('surface_'.length, -'.json'.length), info: JSON.parse(Deno.readTextFileSync(`${dir}/${e.name}`)) };
        }
    }
    return null;
}

const f16step = (v) => {                  // the float16 spacing at |v|
    const a = Math.abs(v);
    if (a < 6.103515625e-5) return 2 ** -24;
    return 2 ** (Math.floor(Math.log2(a)) - 10);
};

// one stored map: its decoded values and how it is stored ('u8' with the decode step, 'f16', 'f32')
function decoded(a, name, cell, ref) {
    const out = new Float64Array(a.data.length);
    if (a.dtype === '|u1') {
        const s = MP.spec(name);
        for (let k = 0; k < out.length; k++) out[k] = MP.decode1(s, a.data[k] / 255, cell);
        return { v: out, kind: 'u8', raw: a.data };
    }
    for (let k = 0; k < out.length; k++) out[k] = Number(a.data[k]) + ref;
    return { v: out, kind: a.dtype === '<f2' ? 'f16' : 'f32', raw: null };
}

function compare(port, blender, name) {
    const p = port.v, b = blender.v;
    let lo = Infinity, hi = -Infinity;
    for (let k = 0; k < b.length; k++) { if (b[k] < lo) lo = b[k]; if (b[k] > hi) hi = b[k]; }
    const range = Math.max(hi - lo, 1e-12);
    let worst = 0, past = 0, steps = 0, bigStep = 0, at = -1;
    for (let k = 0; k < b.length; k++) {
        const d = Math.abs(p[k] - b[k]);
        if (port.kind === 'u8') {
            const st = Math.abs(port.raw[k] - blender.raw[k]);
            if (st > 0) steps++;
            if (st > 1) { past++; bigStep = Math.max(bigStep, st); }
        } else {
            const tol = Math.max(1e-4 * range, 2 * f16step(b[k]));
            if (d > tol) past++;
        }
        if (d > worst) { worst = d; at = k; }
    }
    return { name, kind: port.kind, range, worst, over: worst / range, past, share: past / b.length,
        steps: port.kind === 'u8' ? steps / b.length : undefined, bigStep, at };
}

const R = await G.init();
for (const name of cases) {
    const snap = edition ? `${S.W.blenderTests()}/out/surface_data/snap/${name}.npz` : null;
    const bdir = blenderBakeDir(name);
    if (!snap || !S.W.exists(snap) || !bdir || !S.W.exists(bdir)) {
        T.ok(`${name}: snapshot and Blender bake present`, false, `snapshot ${snap}, bake ${bdir}`);
        continue;
    }
    const bi = bakeInfo(bdir);
    const { Terrain } = await import('../../api.js');
    const t = await Terrain.load(snap, { build: false, log: null });
    const portDir = `${S.W.out('surface_data')}/bakes/${name}`;
    if (!A.flag('--keep')) {
        try { Deno.removeSync(portDir, { recursive: true }); } catch (_e) { /* none yet */ }
    }
    const options = { ...bi.info.options };
    const t0 = performance.now();
    const sd = await SI.bakeSurface(t, { palette: null, options, cache: portDir, log: null });
    const seconds = (performance.now() - t0) / 1000;
    const rec = { case: name, blender_key: bi.key, port_key: sd.key, seconds: +seconds.toFixed(2), levels: [],
        blender_seconds: bi.info.seconds, port_levels: sd.info.levels };
    // the octaves and the norms first: they set every level's relief and spi
    T.ok(`${name}: the gully octaves per level equal Blender's`, JSON.stringify(sd.info.relief_octaves) === JSON.stringify(bi.info.relief_octaves),
        `${JSON.stringify(sd.info.relief_octaves).slice(0, 120)}`);
    const nb = bi.info.norms.spi, np_ = sd.info.norms.spi;
    T.ok(`${name}: spi's norms within 1e-5 of Blender's`, nb && np_ && Math.abs(nb[0] - np_[0]) <= 1e-5 * Math.abs(nb[1] - nb[0]) + 1e-6 &&
        Math.abs(nb[1] - np_[1]) <= 1e-5 * Math.abs(nb[1] - nb[0]) + 1e-6, `port ${JSON.stringify(np_)}, Blender ${JSON.stringify(nb)}`);
    const { NpzFile } = await import('../../api.js');
    let worstShare = 0, worstMap = '', mapsN = 0, bad = [];
    for (let i = 0; i < t.levels.length; i++) {
        const lv = t.levels[i], cell = Number(lv.cell);
        const bz = await NpzFile.open(`${bdir}/surface_${bi.key}_L${i}.npz`);
        const row = { level: i, role: lv.role, cell, maps: [] };
        for (const nm of bz.names) {
            if (nm.startsWith('_')) continue;
            const a = bz.read(nm);
            const pa = sd._stored(i, nm);
            if (!pa) { bad.push(`L${i} ${nm}: missing in the port`); continue; }
            const bref = bz.has(`_ref_${nm}`) ? bz.read(`_ref_${nm}`).data[0] : 0;
            const pref = sd._stored(i, `_ref_${nm}`)?.data[0] ?? 0;
            const c = compare(decoded(pa, nm, cell, pref), decoded(a, nm, cell, bref), nm);
            row.maps.push(c);
            mapsN++;
            if (c.share > worstShare) { worstShare = c.share; worstMap = `L${i} ${nm}`; }
            if (c.share > GRADE_SHARE) bad.push(`L${i} ${nm} ${(100 * c.share).toFixed(2)} % past (worst ${S.sci(c.over, 2)} of range)`);
        }
        const fz = bz.has('_fill') ? bz.read('_fill') : null;
        const pf = sd._stored(i, '_fill');
        if (fz && pf) row.maps.push(compare(decoded(pf, '_fill', cell, 0), decoded(fz, '_fill', cell, 0), '_fill'));
        rec.levels.push(row);
    }
    rec.bad = bad;
    T.ok(`${name}: ${mapsN} maps on ${t.levels.length} levels within the grade (share past it <= ${GRADE_SHARE})`, bad.length === 0,
        bad.length ? bad.slice(0, 5).join('; ') : `worst share ${(100 * worstShare).toFixed(3)} % (${worstMap}); ${seconds.toFixed(1)} s`);
    results[name] = rec;
    t.dispose?.();
}

G.shutdown();
Deno.exit(S.finish(T, 'bake_test', { results }));
