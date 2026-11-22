// Seams and gutters of the surface data (PORT_PLAN.md 8.2 row P14: "seams within 1 % of range"; SURFACING_DESIGN.md
// 5.4, package 1, item 3), Blender's blender/tests/terrain/surface_data/test_seams.py on the port's bakes of the bake
// cases (each with its palette bake, provenance always):
//   1. at every window edge, every map's child equals its parent (the level before it) within 1 % of the map's range,
//      plus the rounding of the 8-bit encodings the cache keeps E and M in (half a step at each level), and C and P's
//      8 bits: the child's outermost texel centres (its pinned border) against the parent bilinear at the same points;
//   2. every texture tile's gutter holds the parent's maps at the gutter's own positions, encoded as the tile is: the
//      D, E and M tiles' outer gutter ring (surface/layers.js) against the parent's encoded values there, within one
//      8-bit step (RGBA8) or 1e-3 (16F).
// The Blender edition's own result at d67f19e (its fix-round report): seven of the eight cases pass, badlands_sd's
// src_strata at level 2 is 1.03 % of its range. When Blender's own seams run of the case's bake is there (the fixtures'
// seams/seams_<case>.json, tests/surface_data/blender_seams.py, else blender/tests/terrain/out/surface_data/
// seams_<case>.json), a third check per case holds every edge's pass or fail and the case's worst seam to it.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/seams_test.mjs
//         [--case toroweap,canyon,...]
//     (on a shared machine, behind $EIDO_GPU_WRAP; $EIDO_BLENDER_EDITION: the Blender edition, for the snapshots)
//
// Writes tests/out/surface_data/seams_test.json. JavaScript per texel here is test code.

import * as MP from '../../surface/maps.js';
import * as L from '../../surface/layers.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const A = S.argsOf();
const T = new S.C.Checks('surface_data: seams and gutters');
const cases = A.list('--case', S.CASES);
const SKIP = ['aspect', 'height', 'strata', 'insolation', 'area', 'slope_20m'];
const TOL = 0.01;
const R = await G.init();

function encStep(nm, cell) {
    let s;
    try {
        s = MP.spec(nm);
    } catch (_e) {
        return 0.0;
    }
    if (s.family === 'C' || s.family === 'P') return 1.0 / 255.0;
    if (s.family !== 'E' && s.family !== 'M') return 0.0;
    if (s.encoding === 'unit') return 1.0 / 255.0;
    if (s.encoding === 'signed') return 2.0 / 255.0;
    if (s.encoding === 'bend') return 2.0 / (255.0 * MP.bendScale(s, cell));
    if (s.encoding === 'thick') return (2.0 * Number(s.t_max)) / 255.0;
    return 0.0;
}

function bilinear(b, m, lv, x, y) {
    const texel = Number(lv.side) / m;
    const fi = Math.min(Math.max((x - Number(lv.x0)) / texel - 0.5, 0), m - 1), fj = Math.min(Math.max((y - Number(lv.y0)) / texel - 0.5, 0), m - 1);
    const i0 = Math.min(Math.floor(fi), Math.max(m - 2, 0)), j0 = Math.min(Math.floor(fj), Math.max(m - 2, 0));
    const ti = Math.fround(fi - i0), tj = Math.fround(fj - j0), i1 = Math.min(i0 + 1, m - 1), j1 = Math.min(j0 + 1, m - 1);
    return (b[j0 * m + i0] * (1 - ti) + b[j0 * m + i1] * ti) * (1 - tj) + (b[j1 * m + i0] * (1 - ti) + b[j1 * m + i1] * ti) * tj;
}

const ptp = (a) => {
    let lo = Infinity, hi = -Infinity;
    for (const v of a) {
        if (v < lo) lo = v;
        if (v > hi) hi = v;
    }
    return hi - lo;
};

const results = {};
for (const name of cases) {
    const got = await S.portSurface(name, { palette: true });
    if (!got) {
        T.ok(`${name}: the case is there`, false, S.skipped[name] ?? 'no snapshot or Blender bake');
        continue;
    }
    const { t, sd } = got;
    const rows = [];
    for (let i = 1; i < t.levels.length; i++) {
        const lv = t.levels[i], plv = t.levels[i - 1];
        const mc = await sd.maps(i), mp = await sd.maps(i - 1);
        for (const nm of Object.keys(mc).sort()) {
            if (SKIP.includes(nm) || !(nm in mp)) continue;
            const a = mc[nm], b = mp[nm];
            if (a.shape3 || b.shape3) continue;
            const m = Math.round(Math.sqrt(a.length)), mb = Math.round(Math.sqrt(b.length));
            const tx = Number(lv.side) / m;
            let d = 0;
            const at = (k) => (Number(lv.x0) + (k + 0.5) * tx);
            const aty = (k) => (Number(lv.y0) + (k + 0.5) * tx);
            for (let k = 0; k < m; k++) {
                const pts = [[k, 0, at(k), aty(0)], [k, m - 1, at(k), aty(m - 1)], [0, k, at(0), aty(k)], [m - 1, k, at(m - 1), aty(k)]];
                for (const [ii, jj, x, y] of pts) {
                    const dv = Math.abs(a[jj * m + ii] - bilinear(b, mb, plv, x, y));
                    if (dv > d) d = dv;
                }
            }
            const rng = Math.max(ptp(b), ptp(a), 1e-6);
            const rounding = 0.5 * (encStep(nm, Number(lv.side) / m) + encStep(nm, Number(plv.side) / mb));
            rows.push({ level: i, map: nm, err: +(d / rng).toFixed(5), rounding: +(rounding / rng).toFixed(5), ok: d <= TOL * rng + rounding + 1e-9 });
        }
    }
    const bad = rows.filter((r) => !r.ok);
    // the gutters: D, E and M tiles' outermost ring against the parent's encoded values there
    const grows = [];
    for (const fam of sd.families().filter((f) => f === 'D' || f === 'E' || f.startsWith('M'))) {
        const lay = sd.layouts[fam];
        const base = fam.startsWith('M') ? 'M' : fam;
        const isFloat = MP.FAMILIES[base].is_float;
        const step = isFloat ? 1e-3 : 1.0 / 255.0 + 1e-6;
        const LA = await L.layerArrays(sd, fam, { R });
        const Sz = LA.size;
        const half2num = (h) => {
            const s = h >> 15 ? -1 : 1, e = (h >> 10) & 31, mm = h & 1023;
            return e === 0 ? s * mm * 2 ** -24 : s * (1 + mm / 1024) * 2 ** (e - 15);
        };
        for (let i = 1; i < t.levels.length; i++) {
            const tl = lay.tiles[i], plv = t.levels[i - 1];
            const size = tl.size;
            const ring = [];
            for (let k = 0; k < size; k++) ring.push([k, 0], [k, size - 1], [0, k], [size - 1, k]);
            let worst = 0;
            const names = sd.familyMaps(fam);
            const pm = await sd.maps(i - 1);
            for (let c = 0; c < 4; c++) {
                const nm = names[c];
                if (nm === null) continue;
                const src = pm[nm];
                if (!src) {
                    grows.push({ family: fam, level: i, map: nm, note: 'parent lacks the map', ok: true });
                    continue;
                }
                const mb = Math.round(Math.sqrt(src.length));
                const s = MP.spec(nm);
                for (const [x, y] of ring) {
                    const wx = tl.x0 + (x - tl.gutter + 0.5) * tl.texel, wy = tl.y0 + (y - tl.gutter + 0.5) * tl.texel;
                    const want = bilinear(src, mb, plv, wx, wy);
                    const enc = s.encoding === 'float' ? want : MP.encode1(s, want, Number(t.levels[i].cell));
                    const raw = LA.data[((i * Sz + y) * Sz + x) * 4 + c];
                    const v = isFloat ? half2num(raw) : raw / 255;
                    const w8 = isFloat ? enc : Math.round(enc * 255) / 255;
                    worst = Math.max(worst, Math.abs(v - w8));
                }
            }
            grows.push({ family: fam, level: i, worst, ok: worst <= step });
        }
    }
    const gbad = grows.filter((r) => !r.ok);
    const worstRow = rows.reduce((w, r) => (r.err > (w?.err ?? -1) ? r : w), null);
    T.ok(`${name}: every map's child within 1 % of its range of the parent at every window edge (${rows.length} map edges)`, bad.length === 0,
        bad.length ? bad.slice(0, 5).map((r) => `${r.map} L${r.level} ${(100 * r.err).toFixed(2)} %`).join('; ')
            : `worst ${worstRow?.map} L${worstRow?.level} ${(100 * (worstRow?.err ?? 0)).toFixed(3)} % of its range`);
    T.ok(`${name}: every D, E and M tile's gutter ring holds the parent's encoded maps (${grows.length})`, gbad.length === 0,
        gbad.slice(0, 4).map((r) => `${r.family} L${r.level} ${S.sci(r.worst, 2)}`).join('; '));
    // beside the Blender edition's own seams of the same case (test_seams.py's check(), whose maps the port's equal
    // within the bake's grade: an edge's error can move by that grade, so what is held equal is each edge's pass or
    // fail and the case's worst seam): the fixtures' record of it (tests/surface_data/blender_seams.py: on the very
    // bytes these tests read), else the Blender edition's own out/surface_data/seams_<case>.json (of whatever its
    // cache held when it ran); a record of another bake than the case's is not compared
    const root = S.fixtureRoot();
    const fxs = root ? `${root}/seams/seams_${name}.json` : null;
    const bj = fxs && S.W.exists(fxs) ? fxs : S.W.blenderEdition() ? `${S.W.blenderTests()}/out/surface_data/seams_${name}.json` : null;
    const brec = bj && S.W.exists(bj) ? JSON.parse(Deno.readTextFileSync(bj)) : null;
    const bbake = S.blenderBake(name);
    if (brec && brec.key && bbake && brec.key !== bbake.key) {
        T.ok(`${name}: Blender's own seams run is of the case's bake`, false, `${bj} is of bake ${brec.key.slice(0, 10)}, the case's ` +
            `is ${bbake.key.slice(0, 10)}: make it on the fixtures (tests/surface_data/blender_seams.py)`);
    } else if (brec) {
        const want = brec.seams;
        const key = (r) => `${r.map} L${r.level}`;
        const mine = new Map(rows.map((r) => [key(r), r]));
        const both = want.filter((w) => mine.has(key(w)));
        const okSame = both.filter((w) => mine.get(key(w)).ok !== w.ok).map(key);
        const wb = both.reduce((w, r) => (r.err > (w?.err ?? -1) ? r : w), null);
        const wp = both.map((w) => mine.get(key(w))).reduce((w, r) => (r.err > (w?.err ?? -1) ? r : w), null);
        const sameWorst = wb && wp && key(wb) === key(wp) && Math.abs(wb.err - wp.err) <= 5e-4;
        T.ok(`${name}: every map edge passes or fails as in Blender's own seams run (test_seams.py), and the worst seam is ` +
            `Blender's within 0.05 % of its range (${both.length} edges both have)`, okSame.length === 0 && sameWorst,
            `${okSame.slice(0, 3).map((k) => `${k} passes in one edition only`).join('; ')}${okSame.length ? '; ' : ''}worst ` +
            `${wp ? `${key(wp)} ${(100 * wp.err).toFixed(3)} %` : '-'}, Blender's ${wb ? `${key(wb)} ${(100 * wb.err).toFixed(3)} %` : '-'}`);
    }
    results[name] = { seams: rows, gutters: grows };
    t.dispose?.();
}
G.shutdown();
Deno.exit(S.finish(T, 'seams_test', { results }));
