// surface/noise.js against surface/noise.py and Blender's own nodes (PORT_PLAN.md 8.2 row P14; SURFACING_DESIGN.md
// 5.4, package 1, item 2: "the noise port equals Blender's Noise Texture node within 1e-3"):
//   1. the float32 oracle (build/ops.js NUM32, JavaScript on the CPU: test code) against noise.py at the fixture's
//      points: the uint32 hashes (lookup3 hash2/3/4 and the Voronoi's PCG hashes) bit for bit, Perlin, the safe noise,
//      the node's fBM (whole, fractional, zero and clamped detail, zero roughness) and the Voronoi colour;
//   2. the WGSL instantiation (build/ops.js WGSL, a compute kernel through core/gpu.js, what the surface bake runs):
//      the hashes bit for bit and every value within 1e-6 of noise.py, and the Blender test's six variants at its
//      128 x 96 points;
//   3. that WGSL noise against Blender's renders of the Noise Texture and Voronoi nodes (blender/tests/terrain/
//      surface_data/test_noise.py's 256 x 256 EXRs of 2 m pixels on a plane at (3000, -2000, 37.5), read by
//      surface_fixtures.py): the 99.9th percentile within 1e-3, the Voronoi colour away from cell edges, as the
//      Blender test grades its GLSL.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/noise_test.mjs
//     (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/surface_data/noise_test.json.

import * as ops from '../../build/ops.js';
import { noise } from '../../surface/noise.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const { C } = S;
const T = new C.Checks('surface_data: Blender\'s shader noise');
const fx = S.fixture('noise');
if (!fx) {
    T.ok('noise fixtures present', false, 'make them: tests/surface_data/surface_fixtures.py --noise');
    Deno.exit(S.finish(T, 'noise_test'));
}
const cases = Object.fromEntries(fx.manifest.cases.map((c) => [c.function, c]));
const arr = (c, side, name) => C.array(fx.dir, c[side][name]);
const out = {};
const N = noise(ops.NUM32);

// ---------------------------------------------------------------------------------- 1. the float32 oracle ---

function bits(got, want) {
    let n = 0;
    for (let k = 0; k < want.length; k++) if ((got[k] >>> 0) !== (want[k] >>> 0)) n++;
    return n;
}
function f32diff(got, want, stride = 1, off = 0) {
    let worst = 0, exact = 0, n = 0;
    for (let k = off; k < want.length; k += stride) {
        const d = Math.abs(got[(k - off) / stride] - want[k]);
        if (d > worst) worst = d;
        if (got[(k - off) / stride] === want[k]) exact++;
        n++;
    }
    return { worst, exact, n };
}
{
    const c = cases['noise.hash'];
    const kx = arr(c, 'inputs', 'kx'), ky = arr(c, 'inputs', 'ky'), kz = arr(c, 'inputs', 'kz'), kw = arr(c, 'inputs', 'kw');
    const h2 = new Uint32Array(kx.length), h3 = new Uint32Array(kx.length), h4 = new Uint32Array(kx.length);
    for (let k = 0; k < kx.length; k++) {
        h2[k] = N.hash2(kx[k], ky[k]);
        h3[k] = N.hash3(kx[k], ky[k], kz[k]);
        h4[k] = N.hash4(kx[k], ky[k], kz[k], kw[k]);
    }
    const bad = bits(h2, arr(c, 'outputs', 'h2')) + bits(h3, arr(c, 'outputs', 'h3')) + bits(h4, arr(c, 'outputs', 'h4'));
    T.ok(`oracle: lookup3 hash2, hash3 and hash4 bit for bit with noise.py on ${3 * kx.length} lattice points`, bad === 0, `${bad} differ`);
    const c2 = cases['noise.pcg'];
    const px = arr(c2, 'inputs', 'kx'), py = arr(c2, 'inputs', 'ky'), pz = arr(c2, 'inputs', 'kz');
    let pbad = 0;
    const names = ['pcg2x', 'pcg2y', 'pcg3x', 'pcg3y', 'pcg3z'];
    const want = names.map((n) => arr(c2, 'outputs', n));
    for (let k = 0; k < px.length; k++) {
        const a = N.pcg2d(px[k] | 0, py[k] | 0), b = N.pcg3d(px[k] | 0, py[k] | 0, pz[k] | 0);
        [...a, ...b].forEach((v, q) => { if ((v >>> 0) !== want[q][k]) pbad++; });
    }
    T.ok(`oracle: the Voronoi's PCG hashes (pcg2d, pcg3d) bit for bit on ${px.length} cells`, pbad === 0, `${pbad} differ`);
}
{
    const c = cases['noise.perlin'];
    const p = arr(c, 'inputs', 'p');
    const n = p.length / 4;
    const fns = { perlin3: (k) => N.perlin3(p[4 * k], p[4 * k + 1], p[4 * k + 2]),
        perlin4: (k) => N.perlin4(p[4 * k], p[4 * k + 1], p[4 * k + 2], p[4 * k + 3]),
        snoise3: (k) => N.snoise3(p[4 * k], p[4 * k + 1], p[4 * k + 2]),
        snoise4: (k) => N.snoise4(p[4 * k], p[4 * k + 1], p[4 * k + 2], p[4 * k + 3]) };
    const rows = {};
    for (const [nm, f] of Object.entries(fns)) {
        const got = new Float64Array(n);
        for (let k = 0; k < n; k++) got[k] = f(k);
        rows[nm] = f32diff(got, arr(c, 'outputs', nm));
    }
    out.oracle_perlin = rows;
    const worst = Math.max(...Object.values(rows).map((r) => r.worst));
    T.ok(`oracle: Perlin 3D and 4D and the safe noise within 1e-6 of noise.py at ${n} points to 3e6 m`, worst <= 1e-6,
        Object.entries(rows).map(([k, r]) => `${k} ${S.sci(r.worst, 1)} (${r.exact} of ${r.n} bit-equal)`).join('; '));
}
{
    const c = cases['noise.nodes'];
    const co = arr(c, 'inputs', 'co');
    const n = co.length / 3;
    const rows = {};
    for (const a of c.args.nodes) {
        const g3 = new Float64Array(n), g4 = new Float64Array(n);
        for (let k = 0; k < n; k++) {
            g3[k] = N.noiseNode3(co[3 * k], co[3 * k + 1], co[3 * k + 2], Math.fround(a.scale3), a.detail, a.roughness);
            g4[k] = N.noiseNode4(co[3 * k], co[3 * k + 1], co[3 * k + 2], a.w, Math.fround(a.scale4), a.detail, a.roughness);
        }
        rows[`node3_${a.tag}`] = f32diff(g3, arr(c, 'outputs', `node3_${a.tag}`));
        rows[`node4_${a.tag}`] = f32diff(g4, arr(c, 'outputs', `node4_${a.tag}`));
    }
    for (const [tag, sc, r, three] of [['vor2', c.args.voronoi.scale2, 1.0, false], ['vor2_r05', c.args.voronoi.scale2, 0.5, false],
        ['vor3', c.args.voronoi.scale3, 1.0, true], ['vor3_r05', c.args.voronoi.scale3, 0.5, true]]) {
        const want = arr(c, 'outputs', tag);
        const got = new Float64Array(want.length);
        for (let k = 0; k < n; k++) {
            const v = three ? N.voronoiF1Colour3(co[3 * k], co[3 * k + 1], co[3 * k + 2], Math.fround(sc), r)
                : N.voronoiF1Colour2(co[3 * k], co[3 * k + 1], Math.fround(sc), r);
            got[3 * k] = v[0]; got[3 * k + 1] = v[1]; got[3 * k + 2] = v[2];
        }
        rows[tag] = f32diff(got, want);
    }
    out.oracle_nodes = rows;
    const worst = Math.max(...Object.values(rows).map((r) => r.worst));
    T.ok(`oracle: the Noise Texture's Fac (3D, 4D; detail 0 to 16, fractional, roughness 0) and the Voronoi colour within 1e-6 of noise.py`,
        worst <= 1e-6, `worst ${S.sci(worst, 2)}; ` + Object.entries(rows).filter(([, r]) => r.worst > 0).slice(0, 4)
            .map(([k, r]) => `${k} ${S.sci(r.worst, 1)}`).join(', '));
}

// --------------------------------------------------------------------------- 2. the WGSL instantiation, GPU ---

const R = await G.init();

/** A kernel over an rgba32f field of points: `make(W, q)` returns up to four f32 values (or u32 with `uint`), the
 * results' field read back. */
async function gpuEval(name, points, h, w, make, uint = false) {
    const W = ops.WGSL();
    const q = { x: { code: 'q.x', type: 'f32' }, y: { code: 'q.y', type: 'f32' }, z: { code: 'q.z', type: 'f32' }, w: { code: 'q.w', type: 'f32' } };
    const vals = make(W, q, noise(W));
    const res = vals.map((v) => W.code(v));
    while (res.length < 4) res.push(uint ? '0u' : '0.0');
    const src = `//! sampler pts\n//! image outV ${uint ? 'r32ui' : 'rgba32f'}\n${W.module()}\n\nfn kmain(p: vec2<i32>) {\n` +
        `  if (!inside(p, outV_size())) { return; }\n  let q = pts_at(p);\n${W.body()}\n` +
        (uint ? `  outV_store(p, ${res[0]});\n}\n` : `  outV_store(p, vec4<f32>(${res.join(', ')}));\n}\n`);
    const k = R.kernel(`noise_test_${name}`, { source: src });
    const pf = R.field(h, w, 4, points);
    const of = R.field(h, w, uint ? 1 : 4, null, uint ? 'u32' : 'f32');
    R.run(k, { pts: pf }, { outV: of }, {});
    const got = await R.read(of);
    pf.destroy();
    of.destroy();
    return got;
}
{
    // the hashes: u32 inputs as float bits (bitcast back in the kernel)
    const c = cases['noise.hash'];
    const kx = arr(c, 'inputs', 'kx'), ky = arr(c, 'inputs', 'ky'), kz = arr(c, 'inputs', 'kz'), kw = arr(c, 'inputs', 'kw');
    const n = kx.length;
    const pts = new Float32Array(4 * n);
    const u = new Uint32Array(pts.buffer);
    for (let k = 0; k < n; k++) { u[4 * k] = kx[k]; u[4 * k + 1] = ky[k]; u[4 * k + 2] = kz[k]; u[4 * k + 3] = kw[k]; }
    const bc = (v) => ({ code: `bitcast<u32>(${v.code})`, type: 'u32' });
    let bad = 0;
    for (const [nm, f] of [['h2', (N2, q) => N2.hash2(bc(q.x), bc(q.y))], ['h3', (N2, q) => N2.hash3(bc(q.x), bc(q.y), bc(q.z))],
        ['h4', (N2, q) => N2.hash4(bc(q.x), bc(q.y), bc(q.z), bc(q.w))]]) {
        const got = await gpuEval(nm, pts, 1, n, (W, q, N2) => [f(N2, q)], true);
        bad += bits(got, arr(c, 'outputs', nm));
    }
    T.ok(`GPU (WGSL): lookup3 hash2, hash3 and hash4 bit for bit with noise.py on ${3 * n} points`, bad === 0, `${bad} differ`);
}
{
    const c = cases['noise.perlin'];
    const p = arr(c, 'inputs', 'p');
    const n = p.length / 4;
    const got = await gpuEval('perlin', p, 1, n, (W, q, N2) => [N2.perlin3(q.x, q.y, q.z), N2.perlin4(q.x, q.y, q.z, q.w),
        N2.snoise3(q.x, q.y, q.z), N2.snoise4(q.x, q.y, q.z, q.w)]);
    // Perlin is evaluated by the safe noise at coordinates under 1e5 (its fmod wrap): graded there; at the fixture's
    // raw points to 3e6 m (four units a float32 step) the fused multiply-adds of a GPU's compiler move it a little
    // more, reported
    const near = [];
    for (let k = 0; k < n; k++) if (Math.max(Math.abs(p[4 * k]), Math.abs(p[4 * k + 1]), Math.abs(p[4 * k + 2]), Math.abs(p[4 * k + 3])) < 1e5) near.push(k);
    const rows = {};
    ['perlin3', 'perlin4', 'snoise3', 'snoise4'].forEach((nm, ch) => {
        const want = arr(c, 'outputs', nm);
        const all = new Float64Array(n);
        for (let k = 0; k < n; k++) all[k] = got[4 * k + ch];
        rows[nm] = f32diff(all, want);
        if (nm.startsWith('perlin')) {
            const g = Float64Array.from(near, (k) => got[4 * k + ch]);
            rows[`${nm}_under_1e5`] = f32diff(g, Float64Array.from(near, (k) => want[k]));
        }
    });
    out.gpu_perlin = rows;
    // the GPU's grade: 2e-6, about 16 float32 steps at 1. The shader compiler fuses multiply-adds (WGSL allows it, and
    // Blender's GLSL is compiled the same way), and over Perlin 4D's sixteen gradients and three nested lerps that
    // moves the last bits by up to about 8 steps (measured 1.0e-6); the oracle above, which rounds every step as numpy
    // does, is bit for bit on Perlin and held to 1e-6
    const graded = ['perlin3_under_1e5', 'perlin4_under_1e5', 'snoise3', 'snoise4'];
    const worst = Math.max(...graded.map((k) => rows[k].worst));
    T.ok(`GPU (WGSL): Perlin 3D and 4D (at the ${near.length} points under 1e5 m, the range the safe noise feeds it) and ` +
        `the safe noise (all ${n} points, to 3e6 m) within 2e-6 of noise.py (fused multiply-adds)`, worst <= 2e-6,
        graded.map((k) => `${k} ${S.sci(rows[k].worst, 1)}`).join('; ') +
        `; raw Perlin to 3e6 m (not graded): ${S.sci(rows.perlin3.worst, 1)}, ${S.sci(rows.perlin4.worst, 1)}`);
}
{
    const c = cases['noise.nodes'];
    const co = arr(c, 'inputs', 'co');
    const n = co.length / 3;
    const pts = new Float32Array(4 * n);
    for (let k = 0; k < n; k++) pts.set([co[3 * k], co[3 * k + 1], co[3 * k + 2], 0], 4 * k);
    const rows = {};
    for (const a of c.args.nodes) {
        const got = await gpuEval(`nodes_${a.tag}`, pts, 1, n, (W, q, N2) => [
            N2.noiseNode3(q.x, q.y, q.z, a.scale3, a.detail, a.roughness), N2.noiseNode4(q.x, q.y, q.z, a.w, a.scale4, a.detail, a.roughness)]);
        for (const [nm, ch] of [[`node3_${a.tag}`, 0], [`node4_${a.tag}`, 1]]) {
            const g = new Float64Array(n);
            for (let k = 0; k < n; k++) g[k] = got[4 * k + ch];
            rows[nm] = f32diff(g, arr(c, 'outputs', nm));
        }
    }
    for (const [tag, sc, r, three] of [['vor2', c.args.voronoi.scale2, 1.0, false], ['vor2_r05', c.args.voronoi.scale2, 0.5, false],
        ['vor3', c.args.voronoi.scale3, 1.0, true], ['vor3_r05', c.args.voronoi.scale3, 0.5, true]]) {
        const got = await gpuEval(`vor_${tag}`, pts, 1, n, (W, q, N2) => {
            const v = three ? N2.voronoiF1Colour3(q.x, q.y, q.z, sc, r) : N2.voronoiF1Colour2(q.x, q.y, sc, r);
            return [W.vx(v), W.vy(v), W.vz(v)];
        });
        const g = new Float64Array(3 * n);
        for (let k = 0; k < n; k++) { g[3 * k] = got[4 * k]; g[3 * k + 1] = got[4 * k + 1]; g[3 * k + 2] = got[4 * k + 2]; }
        rows[tag] = f32diff(g, arr(c, 'outputs', tag));
    }
    out.gpu_nodes = rows;
    // detail 16 (clamped to 15) at points to 3e4 m: its last octaves sample at 2^15 x 3e4, past float32's integers
    // (2^24), where the safe noise's fmod and the GPU's fused multiply-adds round differently from numpy's separate
    // steps; that octave's amplitude is 2^-15. Reported, not graded (the palettes' fbm() is detail 5)
    const graded = Object.keys(rows).filter((k) => !k.endsWith('_d16'));
    const worst = Math.max(...graded.map((k) => rows[k].worst));
    T.ok('GPU (WGSL): the Noise Texture\'s Fac (detail 0 to 5, fractional, roughness 0) and the Voronoi colour within 1e-6 of noise.py',
        worst <= 1e-6, `worst ${S.sci(worst, 2)}; ` + graded.sort((x, y) => rows[y].worst - rows[x].worst).slice(0, 3)
            .map((k) => `${k} ${S.sci(rows[k].worst, 1)}`).join(', ') +
        `; detail 16 (not graded): ${S.sci(rows.node3_d16.worst, 1)}, ${S.sci(rows.node4_d16.worst, 1)}`);
}
{
    const c = cases['noise.variants'];
    const co = arr(c, 'inputs', 'co');
    const [H, Wd] = c.inputs.co.shape;
    const n = H * Wd;
    const pts = new Float32Array(4 * n);
    for (let k = 0; k < n; k++) pts.set([co[3 * k], co[3 * k + 1], co[3 * k + 2], 0], 4 * k);
    const rows = {};
    for (const [nm, kind, args] of c.args.variants) {
        const got = await gpuEval(`var_${nm}`, pts, H, Wd, (W, q, N2) => [variant(W, N2, kind, args, q.x, q.y, q.z)]);
        const g = new Float64Array(n);
        for (let k = 0; k < n; k++) g[k] = got[4 * k];
        rows[nm] = f32diff(g, arr(c, 'outputs', nm));
    }
    out.gpu_variants = rows;
    const worst = Math.max(...Object.values(rows).map((r) => r.worst));
    T.ok(`GPU (WGSL): test_noise.py's six variants at its ${n} points within 1e-6 of noise.py (its GLSL: 4.2e-7)`, worst <= 1e-6,
        Object.entries(rows).map(([k, r]) => `${k} ${S.sci(r.worst, 1)}`).join('; '));
}

function variant(W, N2, kind, args, x, y, z) {
    if (kind === 'n3') return N2.noiseNode3(x, y, z, args[0], args[1], args[2]);
    if (kind === 'n4') return N2.noiseNode4(x, y, z, args[0], args[1], args[2], args[3]);
    if (kind === 'v2') return W.vx(N2.voronoiF1Colour2(x, y, args[0], 1.0));
    return W.vx(N2.voronoiF1Colour3(x, y, z, args[0], 1.0));
}

// --------------------------------------------------------------------- 3. against Blender's node renders ---

{
    const c = cases['noise.render'];
    if (!c) {
        T.ok('Blender\'s node renders in the fixtures', false, 'make them in Blender: blender/tests/terrain/surface_data/test_noise.py, then surface_fixtures.py --noise');
    } else {
        const co = arr(c, 'inputs', 'co');
        const [H, Wd] = c.inputs.co.shape;
        const n = H * Wd;
        const pts = new Float32Array(4 * n);
        for (let k = 0; k < n; k++) pts.set([co[3 * k], co[3 * k + 1], co[3 * k + 2], 0], 4 * k);
        const rows = {};
        for (const [nm, kind, args] of c.args.variants) {
            if (!c.outputs[nm]) continue;
            const img = arr(c, 'outputs', nm);
            const got = await gpuEval(`render_${nm}`, pts, H, Wd, (W, q, N2) => [variant(W, N2, kind, args, q.x, q.y, q.z)]);
            const d = [];
            const twin = arr(c, 'outputs', `${nm}_twin`);
            for (let j = 0; j < H; j++) {
                for (let i = 0; i < Wd; i++) {
                    const k = j * Wd + i;
                    if (kind === 'v2' || kind === 'v3') {
                        // away from cell edges: the twin's value equal over the 3 x 3 neighbourhood (test_noise.py)
                        let same = true;
                        for (let dj = -1; dj <= 1 && same; dj++) {
                            for (let di = -1; di <= 1 && same; di++) {
                                const jj = Math.min(Math.max(j + dj, 0), H - 1), ii = Math.min(Math.max(i + di, 0), Wd - 1);
                                if (twin[jj * Wd + ii] !== twin[k]) same = false;
                            }
                        }
                        if (!same) continue;
                    }
                    d.push(Math.abs(got[4 * k] - img[k]));
                }
            }
            d.sort((a, b) => a - b);
            rows[nm] = { n: d.length, max: d[d.length - 1], p999: d[Math.floor(0.999 * (d.length - 1))], mean: d.reduce((s, x) => s + x, 0) / d.length,
                rendered: c.args.rendered?.[nm] };
        }
        out.render = rows;
        const worst = Math.max(...Object.values(rows).map((r) => r.p999));
        T.ok('GPU (WGSL) against Blender\'s own Noise Texture and Voronoi nodes (EEVEE renders): p99.9 within 1e-3',
            worst <= 1e-3 && Object.keys(rows).length === 6,
            Object.entries(rows).map(([k, r]) => `${k} p99.9 ${S.sci(r.p999, 1)} max ${S.sci(r.max, 1)}`).join('; '));
    }
}

G.shutdown();
Deno.exit(S.finish(T, 'noise_test', out));
