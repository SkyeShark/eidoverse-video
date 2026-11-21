// What the surface data package's tests share (PORT_PLAN.md 8.2 row P14): where its fixtures are, the result file,
// and a few array helpers. Paths come from tests/_where.mjs.
//
//     import * as S from './_surface.mjs';
//     const fx = S.fixture('kernels');                 // { dir, manifest } of tests/surface_data/surface_fixtures.py's
//                                                      // output, or null (a line says how to make it)
//     const T = new S.C.Checks('surface_data: ...');   ...   Deno.exit(S.finish(T, 'kernels_test'));
//
// The fixtures are keyed by the Blender commit they were made from (blender_<commit>, the surface code hash and the
// palettes' in key.json): $EIDO_SURFACE_FIXTURES names the folder (tests/out/surface_data/fixtures/<name>), else the
// newest. JavaScript per cell here is test code (the edition's rule allows it in tests only).

import * as C from '../parity/_common.mjs';

export { C };
export const W = C.W;

/** tests/out/surface_data/fixtures/<key>: $EIDO_SURFACE_FIXTURES, else the newest folder by its key.json. */
export function fixtureRoot() {
    const root = `${W.out('surface_data')}/fixtures`;
    const want = Deno.env.get('EIDO_SURFACE_FIXTURES');
    if (want) return W.exists(`${root}/${want}/key.json`) ? `${root}/${want}` : null;
    let best = null, t = -1;
    try {
        for (const e of Deno.readDirSync(root)) {
            const k = `${root}/${e.name}/key.json`;
            if (!e.isDirectory || !W.exists(k)) continue;
            const m = Deno.statSync(k).mtime?.getTime() ?? 0;
            if (m > t) { t = m; best = `${root}/${e.name}`; }
        }
    } catch (_e) { /* no fixtures yet */ }
    return best;
}

/** { dir, manifest, key } of a fixture kind ('kernels', 'noise', 'expr'), or null after saying how to make it. */
export function fixture(kind) {
    const root = fixtureRoot();
    const dir = root ? `${root}/${kind}` : null;
    if (dir && W.exists(`${dir}/manifest.json`)) {
        return { dir, manifest: JSON.parse(Deno.readTextFileSync(`${dir}/manifest.json`)),
            key: JSON.parse(Deno.readTextFileSync(`${root}/key.json`)) };
    }
    console.log(`[skip] no surface ${kind} fixtures: make them with EIDO_BLENDER_EDITION=<a checkout or an export of the ` +
        `blender branch> <Blender's python> -I eidoverse/terrain/tests/surface_data/surface_fixtures.py --${kind}`);
    return null;
}

/** The key record of the fixtures (key.json: commit, surface code hash, palettes hash, versions), or null. */
export function fixtureKey() {
    const root = fixtureRoot();
    return root ? JSON.parse(Deno.readTextFileSync(`${root}/key.json`)) : null;
}

/** Write a test's result to tests/out/surface_data/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), fixtures: fixtureKey(), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('surface_data')}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

/** The arguments of a test: opt('--x', dflt), flag('--y'), list('--z'). */
export function argsOf(argv = Deno.args) {
    const args = [...argv];
    return {
        opt: (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; },
        flag: (n) => args.includes(n),
        list: (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1].split(',') : d; },
    };
}

/** The bake cases (Blender's surface_data package's, _cases.py): their snapshots are Terrain.save files. */
export const CASES = ['toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon', 'alpine_valley',
    'fluvial_range'];

/** The Blender bake of a case the tests compare with: the fixtures' copy (blender_bakes.py), else the Blender package's
 * own cache. { dir, key, info } or null. */
export function blenderBake(name) {
    const root = fixtureRoot();
    const dirs = [root ? `${root}/bakes/${name}` : null, W.blenderEdition() ? `${W.blenderTests()}/out/surface_data/cache/${name}` : null];
    for (const dir of dirs) {
        if (!dir || !W.exists(dir)) continue;
        for (const e of Deno.readDirSync(dir)) {
            if (e.isFile && e.name.startsWith('surface_') && e.name.endsWith('.json') && !e.name.includes('_pal')) {
                return { dir, key: e.name.slice('surface_'.length, -'.json'.length), info: JSON.parse(Deno.readTextFileSync(`${dir}/${e.name}`)) };
            }
        }
    }
    return null;
}

/** A case's terrain (its snapshot) and the port's SurfaceData of it: baked with the options Blender's bake recorded
 * (a cache hit on bake_test.mjs's bakes in tests/out/surface_data/bakes/<case>), with palette: its palette bake
 * ('auto', as bakeSurface resolves it; provenance always) beside it. { t, sd } or null (a line says why). */
export async function portSurface(name, { palette = false, log = null } = {}) {
    const snap = W.blenderEdition() ? `${W.blenderTests()}/out/surface_data/snap/${name}.npz` : null;
    const bb = blenderBake(name);
    if (!snap || !W.exists(snap) || !bb) {
        console.log(`[skip] ${name}: no snapshot or Blender bake (EIDO_BLENDER_EDITION, tests/surface_data/blender_bakes.py)`);
        return null;
    }
    const SI = await import('../../surface/index.js');
    const B = await import('../../surface/bake.js');
    const { Terrain } = await import('../../api.js');
    const t = await Terrain.load(snap, { build: false, log: null });
    const dir = `${W.out('surface_data')}/bakes/${name}`;
    const sd = await SI.bakeSurface(t, { palette: null, options: { ...bb.info.options }, cache: dir, log });
    if (palette) {
        if (!Deno.env.get('EIDO_SURFACE_SETS') && W.blenderEdition()) {
            Deno.env.set('EIDO_SURFACE_SETS', `${W.blenderEdition()}/eidoverse/assets/cache/terrain_surface_sets`);
        }
        let p = 'auto';
        if (t.info?.palette && t.info.palette !== 'auto') p = t.info.palette;
        const pal = await B.resolvePalette(t, p);
        sd.palette = pal;
        sd._palettes = await B.palettesModule();
        await sd.bakePalette(pal, { cache: dir, log, provenance: true });
    }
    return { t, sd };
}

/** The largest |a - b| of two arrays (as numbers), its index, and the range of b. */
export function maxDiff(a, b, stride = 1, offset = 0) {
    let err = 0, at = -1, lo = Infinity, hi = -Infinity;
    for (let i = offset; i < b.length; i += stride) {
        const d = Math.abs(Number(a[i]) - Number(b[i]));
        if (d > err || Number.isNaN(d)) { err = d; at = i; }
        if (b[i] < lo) lo = b[i];
        if (b[i] > hi) hi = b[i];
    }
    return { err, at, range: hi - lo };
}

export const sci = C.sci;
