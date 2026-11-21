// The shader nodes the material transcribes, against EEVEE (tests/surfacing/blender_probe_nodes.py's renders): the
// Image Texture node's Cubic read (which cubic it is), the White Noise Texture's colour (hex tiling's offsets and
// turns) and the Voronoi F1 distance and colour (the canopy), evaluated here per pixel with build/ops.js's NUM32
// backend (the float32 oracle of the same source the material compiles to TSL). Test code: JavaScript per pixel.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surfacing/probe_nodes_test.mjs [<dir>]
//     (no GPU; <dir>: the probe's output, default tests/out/surfacing/probe_nodes)

import * as M from './_material.mjs';
import * as ops from '../../build/ops.js';
import { noise } from '../../surface/noise.js';
import { readNpySync } from '../../core/io.js';

const dir = Deno.args[0] ?? M.out('probe_nodes');
const T = new M.C.Checks('surfacing: EEVEE\'s nodes against their transcriptions');
const npy = (n) => readNpySync(`${dir}/${n}.npy`);
const FILM = 2 ** -11;                       // EEVEE's film is half float: half a step of a value under 1, rounded up
const info = JSON.parse(Deno.readTextFileSync(`${dir}/probe_nodes.json`));
const f32 = Math.fround;

// ---- 1. the Image Texture node: Cubic, Linear, Closest over a 16 x 16 image at 4 pixels a texel
{
    const img = npy('cubic_image');
    const N = 16, PX = info.cases.image_cubic.px / N;             // pixels a texel
    const at = (i, j, c) => img.data[((Math.min(Math.max(j, 0), N - 1)) * N + Math.min(Math.max(i, 0), N - 1)) * 4 + c];
    const bspline = (a) => [(1 - a) ** 3 / 6, (3 * a ** 3 - 6 * a ** 2 + 4) / 6, (-3 * a ** 3 + 3 * a ** 2 + 3 * a + 1) / 6, a ** 3 / 6];
    const catmull = (a) => [(-(a ** 3) + 2 * a ** 2 - a) / 2, (3 * a ** 3 - 5 * a ** 2 + 2) / 2, (-3 * a ** 3 + 4 * a ** 2 + a) / 2, (a ** 3 - a ** 2) / 2];
    const cubicAt = (wf, x, y, c) => {
        const tx = Math.floor(x - 0.5) + 0.5, ty = Math.floor(y - 0.5) + 0.5;
        const wx = wf(x - tx), wy = wf(y - ty);
        let s = 0;
        for (let q = 0; q < 4; q++) for (let p = 0; p < 4; p++) s += wx[p] * wy[q] * at(Math.floor(tx - 0.5) - 1 + p, Math.floor(ty - 0.5) - 1 + q, c);
        return s;
    };
    const linearAt = (x, y, c) => {
        const fx = x - 0.5, fy = y - 0.5, i = Math.floor(fx), j = Math.floor(fy), a = fx - i, b = fy - j;
        return (at(i, j, c) * (1 - a) + at(i + 1, j, c) * a) * (1 - b) + (at(i, j + 1, c) * (1 - a) + at(i + 1, j + 1, c) * a) * b;
    };
    const grade = (name, render, fn) => {
        let mx = 0;
        for (let py = PX; py < (N - 1) * PX; py++) {
            for (let px = PX; px < (N - 1) * PX; px++) {
                const x = (px + 0.5) / PX, y = (py + 0.5) / PX;
                for (let c = 0; c < 3; c++) mx = Math.max(mx, Math.abs(render.data[(py * N * PX + px) * 4 + c] - fn(x, y, c)));
            }
        }
        return mx;
    };
    const cub = npy('image_cubic'), lin = npy('image_linear');
    const eB = grade('cubic', cub, (x, y, c) => cubicAt(bspline, x, y, c));
    const eC = grade('cubic', cub, (x, y, c) => cubicAt(catmull, x, y, c));
    const eL = grade('cubic', cub, linearAt);
    const eLin = grade('linear', lin, linearAt);
    T.ok('EEVEE\'s Linear read is bilinear at mip 0 over a magnified image', eLin < 2e-3, `max ${M.C.sci(eLin, 2)}`);
    console.log(`[probe] Cubic against a B-spline ${M.C.sci(eB, 3)}, Catmull-Rom ${M.C.sci(eC, 3)}, bilinear ${M.C.sci(eL, 3)}`);
    // (the four taps are bilinear reads: the hardware's sub-texel weights carry 8 bits)
    T.ok('EEVEE\'s Cubic read is the cubic B-spline of four bilinear taps (node_tex_image_cubic), as the port reads it',
        eB < 5e-3 && eC > 10 * eB, `max error: B-spline ${M.C.sci(eB, 2)}, Catmull-Rom ${M.C.sci(eC, 2)}, bilinear ${M.C.sci(eL, 2)}`);
}

// ---- 2. the White Noise Texture (3D) Color at lattice points: lookup3 of the float bits (hash_vec3_to_vec3)
{
    const N = noise(ops.NUM32);
    const bits = (x) => {
        const b = new DataView(new ArrayBuffer(4));
        b.setFloat32(0, x);
        return b.getUint32(0);
    };
    const u2f = (h) => f32(f32(h) / f32(4294967295.0));
    const r = npy('white_noise');
    const n = info.cases.white_noise.px, z = f32(info.cases.white_noise.z);
    let mx = 0;
    for (let py = 0; py < n; py++) {
        for (let px = 0; px < n; px++) {
            const k = [bits(f32(px)), bits(f32(py)), bits(z)];
            const want = [u2f(N.hash3(k[0], k[1], k[2])), u2f(N.hash4(k[0], k[1], k[2], bits(1.0))), u2f(N.hash4(k[0], k[1], k[2], bits(2.0)))];
            for (let c = 0; c < 3; c++) mx = Math.max(mx, Math.abs(r.data[(py * n + px) * 4 + c] - want[c]));
        }
    }
    T.ok('the White Noise Texture\'s colour is lookup3 of the float bits (k, (k, 1), (k, 2)), as the hex grid reads it',
        mx <= FILM, `max ${M.C.sci(mx, 2)} over ${n * n} lattice points (EEVEE's film holds halves: ${M.C.sci(FILM, 2)})`);
}

// ---- 3. the Voronoi texture F1 (3D, Euclidean): distance and colour, the PCG hashes of the cells
{
    const o = ops.NUM32;
    const N = noise(o);
    const c = info.cases.voronoi_distance;
    const n = c.px, side = c.side_m, sc = f32(c.scale), rnd = f32(c.randomness);
    const INV31 = 1.0 / 2147483648.0;
    const vor = (x, y, z) => {
        const co = [f32(x * sc), f32(y * sc), f32(z * sc)];
        const fl = co.map(Math.floor), cell = fl.map((v) => v | 0), loc = co.map((v, q) => f32(v - fl[q]));
        let best = 3.4e38, tt = [0, 0, 0];
        for (let k = -1; k <= 1; k++) for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
            const off = [i, j, k];
            const h = N.pcg3d(cell[0] + i | 0, cell[1] + j | 0, cell[2] + k | 0).map((v) => f32(f32(v) * INV31));
            const d2 = [0, 1, 2].map((q) => { const dd = f32(f32(off[q] + f32(h[q] * rnd)) - loc[q]); return f32(dd * dd); });
            const d = f32(Math.sqrt(f32(f32(d2[0] + d2[1]) + d2[2])));
            if (d < best) { best = d; tt = off; }
        }
        const col = N.pcg3d(cell[0] + tt[0] | 0, cell[1] + tt[1] | 0, cell[2] + tt[2] | 0).map((v) => f32(f32(v) * INV31));
        return [best, ...col];
    };
    const rd = npy('voronoi_distance'), rc = npy('voronoi_color');
    let md = 0, mc = 0, nd = 0;
    for (let py = 0; py < n; py++) {
        for (let px = 0; px < n; px++) {
            const x = f32(f32((px + 0.5) * side / n) + f32(c.offset[0])), y = f32(f32((py + 0.5) * side / n) + f32(c.offset[1]));
            const [d, r1, g1, b1] = vor(x, y, f32(c.offset[2]));
            const ed = Math.abs(rd.data[(py * n + px) * 4] - d) / Math.max(1, d);
            md = Math.max(md, ed);
            const ec = Math.max(...[r1, g1, b1].map((v, q) => Math.abs(rc.data[(py * n + px) * 4 + q] - v)));
            if (ec > FILM) nd++;
            else mc = Math.max(mc, ec);
        }
    }
    T.ok('the Voronoi F1 distance (3D) is the port\'s (noise.js\'s PCG cell hashes), as the canopy reads it', md <= FILM,
        `max ${M.C.sci(md, 2)} over ${n * n} pixels`);
    T.ok('the Voronoi F1 colour (3D) is the port\'s', nd <= Math.max(2, 0.002 * n * n),
        `${nd} pixels on a cell border differ (a near tie), elsewhere max ${M.C.sci(mc, 2)}`);
}
Deno.exit(M.finish(T, 'probe_nodes_test', { blender: info.blender }));
