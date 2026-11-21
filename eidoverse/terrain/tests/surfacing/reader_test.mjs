// The material's check 1, its parity part (SURFACING_DESIGN.md 5.4 package 2; PORT_PLAN.md 8.2 row P17: "the
// reader's top-down emission render equal to the bake's arrays within 1/255 (RGBA8) and 1e-3 relative (16F) on every
// level"): blender/tests/terrain/surfacing/check_reader.py's parity, on the port. On every level of a case, a 64 x 64
// texel patch deep inside its own ring (no window edge within 40 of its cells) is rendered top-down, orthographic,
// one texel a pixel, as an unlit emission of maps read through build/surfacing.js terrainMap (eido_terrain_map: the
// material's two-slot reader): an 8-bit mask (flow, M), the stratigraphic height (strata, F, half float, decoded on
// the mesh's own z) or a second mask, an 8-bit detail map (cavity, E) and the field normal's x (D, half float).
// Against the bake's arrays at the texel centres: p99 within 1/255 for the 8-bit maps (2/255 signed), within 1e-3
// of the patch's range for the half-float ones, as check_reader.py grades them.
// The D family is read bicubic where its texel is magnified (surfacing.py CUBIC_FAMILIES, since 11-18; EEVEE's Cubic
// is the cubic B-spline, tests/surfacing/probe_nodes_test.mjs), which smooths a texel centre by design: so the parity
// reads D linear (the reader's levels, slots, coordinates and decoding), and a second render with the material's own
// cubic reads checks normal_x on the levels whose texels span more than 3 pixels (a weight of exactly 1 on the bicubic
// read) against the B-spline of the bake's array there, within CUBIC_TOL of the range: the four taps are bilinear
// reads, whose sub-texel weights the hardware holds in 8 bits (EEVEE's own Cubic, the same four taps, is off its
// B-spline by up to 3.1e-3 of a random image's range: probe_nodes_test.mjs). (Blender's own parity record,
// out/surfacing/material/reader_<case>.json of 11-14, predates the bicubic D read.)
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surfacing/reader_test.mjs
//         [--cases canyon,alpine_valley]
//     (a GPU job: behind $EIDO_GPU_WRAP on a shared machine; $EIDO_BLENDER_EDITION for the snapshots)
//
// Writes tests/out/surfacing/reader_test.json.

import * as M from './_material.mjs';
import * as MP from '../../surface/maps.js';
import * as P from '../../build/palettes.js';
import * as Sf from '../../build/surfacing.js';

const A = M.argsOf();
const cases = A.list('--cases', ['canyon', 'alpine_valley']);
const T = new M.C.Checks('surfacing: the two-slot reader against the bake (check 1, parity)');
const G = await M.gpu();
const { THREE, TSL } = G;
await Sf.tslModule({ TSL });
const N = 64;
const CUBIC_TOL = 4e-3;

// np.linspace(a, b, n): a + k step, the last exactly b
const linspace = (a, b, n) => Array.from({ length: n }, (_, k) => (k === n - 1 ? b : a + k * ((b - a) / (n - 1))));
const pyRound = (x) => {
    const r = Math.round(x);
    return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r;
};

// check_reader.patch_origin: [i0, j0, texel] of a patch inside level i's own ring, 40 cells from every window edge
function patchOrigin(sd, i, n, grid) {
    const lv = sd.levels[i];
    const tex = sd.readerConstants()[grid][i].texel;
    const m = 40.0 * lv.cell;
    const child = i + 1 < sd.levels.length ? sd.levels[i + 1] : null;
    const cand = [];
    for (const fx of linspace(0.12, 0.88, 13)) {
        for (const fy of linspace(0.12, 0.88, 13)) {
            const x = lv.x0 + fx * lv.side, y = lv.y0 + fy * lv.side, half = 0.5 * n * tex;
            if (i > 0 && !(lv.x0 + m + half < x && x < lv.x0 + lv.side - m - half && lv.y0 + m + half < y && y < lv.y0 + lv.side - m - half)) continue;
            if (child && (child.x0 - m - half < x && x < child.x0 + child.side + m + half && child.y0 - m - half < y && y < child.y0 + child.side + m + half)) continue;
            cand.push([Math.abs(fx - 0.5) + Math.abs(fy - 0.5), x, y]);
        }
    }
    if (!cand.length) return null;
    cand.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
    const [, x, y] = cand[0];
    return [pyRound((x - lv.x0) / tex - 0.5 * n), pyRound((y - lv.y0) / tex - 0.5 * n), tex];
}

const record = {};
for (const name of cases) {
    const got = await M.caseData(name, G);
    if (!got) {
        T.ok(`${name}: the case's snapshot and bake are there`, false, 'see the skip line');
        continue;
    }
    const { t, sd } = got;
    const packed = new Set(sd.packing().flat());
    const need = ['flow', 'wetness'];
    const tm = await Sf.terrainMap(sd, need.every((n) => packed.has(n)) ? null : [...new Set([...packed, ...need])].sort(),
        { THREE, R: G.R, TSL, cubic: false });
    const tmCubic = await Sf.terrainMap(sd, null, { THREE, R: G.R, TSL, cubic: true });
    const cellNames = sd.has('strata') ? ['flow', 'strata'] : ['flow', 'wetness'];
    record[name] = {};
    let worst = { bytes: 0, rel: 0, cubic: 0 };
    let allOk = true, cubicOk = true, cubicLevels = 0;
    for (let i = 0; i < sd.levels.length; i++) {
        const lv = sd.levels[i];
        const maps = await sd.maps(i);
        const h = t.fields(i).h;
        const res = {};
        for (const [grid, names] of [['cell', cellNames], ['detail', ['cavity', 'normal_x']]]) {
            const po = patchOrigin(sd, i, N, grid);
            if (!po) {
                res[grid] = 'no patch';
                continue;
            }
            const [i0, j0, tex] = po;
            const n = Math.round(lv.side / tex);
            // the oracle: the bake's arrays at the patch's texel centres (rows south to north); strata on the mesh's z
            const subs = names.map((nm) => {
                const a = maps[nm];
                const sub = new Float64Array(N * N);
                for (let j = 0; j < N; j++) {
                    for (let q = 0; q < N; q++) {
                        let v = Number(a[(j0 + j) * n + (i0 + q)]);
                        if (nm === 'strata') {
                            const x = lv.x0 + (i0 + q + 0.5) * tex, y = lv.y0 + (j0 + j + 0.5) * tex;
                            v = v - Number(h[(j0 + j) * n + (i0 + q)]) + t.ring.heightAt(x, y);
                        }
                        sub[j * N + q] = v;
                    }
                }
                let lo = Infinity, hi = -Infinity;
                for (const v of sub) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
                if (hi - lo < 1e-6) hi = lo + 1.0;
                return { nm, sub, lo, hi };
            });
            // the emission: each map remapped to its patch's range (check_reader.remap), one channel each
            const ch = subs.map(({ nm, lo, hi }) => tm[nm].sub(lo).div(hi - lo));
            const mat = new THREE.MeshBasicNodeMaterial();
            mat.colorNode = TSL.vec4(ch[0], ch[1] ?? TSL.float(0), TSL.float(0), TSL.float(1));
            mat.toneMapped = false;
            t.mesh.material = [mat, mat];
            let ztop = -Infinity, zbot = Infinity;
            for (let j = 0; j < N; j += 4) {
                for (let q = 0; q < N; q += 4) {
                    const z = t.ring.heightAt(lv.x0 + (i0 + q + 0.5) * tex, lv.y0 + (j0 + j + 0.5) * tex);
                    ztop = Math.max(ztop, z);
                    zbot = Math.min(zbot, z);
                }
            }
            const { px } = await M.renderTop(G, t.mesh, { cx: lv.x0 + (i0 + 0.5 * N) * tex, cy: lv.y0 + (j0 + 0.5 * N) * tex,
                side: N * tex, n: N, top: ztop + 500.0 });
            mat.dispose();
            const r = {};
            subs.forEach(({ nm, sub, lo, hi }, c) => {
                // render row 0 is north: the patch's row N - 1
                const errs = new Float64Array(N * N);
                for (let j = 0; j < N; j++) {
                    for (let q = 0; q < N; q++) {
                        const g = lo + px[((N - 1 - j) * N + q) * 4 + c] * (hi - lo);
                        errs[j * N + q] = Math.abs(g - sub[j * N + q]);
                    }
                }
                const spec = MP.spec(nm);
                const enc = spec.encoding;
                if (['unit', 'signed', 'bend', 'thick'].includes(enc)) {
                    let tol = (1.0 / 255.0) * (enc === 'signed' ? 2.0 : 1.0);
                    if (enc === 'thick') tol = 2.0 * Math.sqrt(Math.max(hi, 1e-6) / spec.t_max) / 255.0 * spec.t_max;
                    const p99 = M.percentile(errs, 99);
                    r[nm] = { p99, max: Math.max(...errs), tol, ok: p99 <= tol };
                    worst.bytes = Math.max(worst.bytes, p99 / tol);
                } else {
                    const rng = Math.max(hi - lo, 1e-6);
                    const rel = errs.map((e) => e / rng);
                    const p99 = M.percentile(rel, 99);
                    r[nm] = { p99_rel: p99, max_rel: Math.max(...rel), range: rng, ok: p99 <= 1e-3 };
                    worst.rel = Math.max(worst.rel, p99);
                }
                if (!r[nm].ok) allOk = false;
            });
            // the bicubic D read, where the pixel spans under CUBIC_PX[0] of a texel everywhere on the patch (the
            // footprint is about the camera's distance x the pixel angle): EEVEE's B-spline of the array
            const half = 0.5 * N * tex;
            const fpMax = Math.hypot(ztop + 500.0 - zbot, half * Math.SQRT2) * Number(P.CONSTANTS.pixel_angle);
            if (grid === 'detail' && fpMax / tex < Sf.CUBIC_PX[0] * 0.9) {
                const a = maps.normal_x;
                const { lo, hi } = subs[1];
                const m2 = new THREE.MeshBasicNodeMaterial();
                m2.colorNode = TSL.vec4(tmCubic.normal_x.sub(lo).div(hi - lo), TSL.float(0), TSL.float(0), TSL.float(1));
                m2.toneMapped = false;
                t.mesh.material = [m2, m2];
                const { px: pc } = await M.renderTop(G, t.mesh, { cx: lv.x0 + (i0 + 0.5 * N) * tex, cy: lv.y0 + (j0 + 0.5 * N) * tex,
                    side: N * tex, n: N, top: ztop + 500.0 });
                m2.dispose();
                const w = [1 / 6, 4 / 6, 1 / 6];
                let mx = 0;
                const errs = [];
                for (let j = 0; j < N; j++) {
                    for (let q = 0; q < N; q++) {
                        let want = 0;
                        for (let b = 0; b < 3; b++) for (let c2 = 0; c2 < 3; c2++) want += w[b] * w[c2] * Number(a[(j0 + j - 1 + b) * n + (i0 + q - 1 + c2)]);
                        const g = lo + pc[((N - 1 - j) * N + q) * 4] * (hi - lo);
                        const e = Math.abs(g - want) / Math.max(hi - lo, 1e-6);
                        errs.push(e);
                        mx = Math.max(mx, e);
                    }
                }
                const p99 = M.percentile(errs, 99);
                r.normal_x_cubic = { p99_rel: p99, max_rel: mx, ok: p99 <= CUBIC_TOL };
                worst.cubic = Math.max(worst.cubic, p99);
                cubicLevels++;
                if (p99 > CUBIC_TOL) cubicOk = false;
            }
            res[grid] = { texel: tex, origin: [i0, j0], maps: r };
        }
        record[name][`L${i}`] = res;
        console.log(`[reader] ${name} L${i}: ${JSON.stringify(res)}`);
    }
    T.ok(`${name}: on every level the reader's top-down emission equals the bake's arrays (8-bit maps within one step at ` +
        'p99, half-float within 1e-3 of the patch range)', allOk,
        `worst 8-bit p99 ${worst.bytes.toFixed(3)} of its step, worst half-float p99 ${M.C.sci(worst.rel, 2)} of range; ${sd.levels.length} levels`);
    T.ok(`${name}: the material's bicubic D read is EEVEE's B-spline of the bake's array where a texel is magnified`,
        cubicOk && cubicLevels > 0, `${cubicLevels} levels checked, worst p99 ${M.C.sci(worst.cubic, 2)} of range`);
}
G.renderer.dispose();
Deno.exit(M.finish(T, 'reader_test', { cases: record }));
