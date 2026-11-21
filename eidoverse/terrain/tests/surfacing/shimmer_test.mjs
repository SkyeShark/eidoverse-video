// The material's check 4 (SURFACING_DESIGN.md 5.4 package 2; PORT_PLAN.md 8.2 row P17: "the shimmer probe"):
// blender/tests/terrain/surfacing/check_shimmer.py's measure on the port's renders. views.mjs --variants
// built,turn1,turn2,dist0,dist10,dist40,dist400 renders a judge view (by default the canyon's approach_walk: the
// plateau from 1.7 m, ground from the camera's feet to the horizon) with the camera turned about the vertical by 0,
// 0.5 and 1 pixel, and the view distance's bands as masks. Each frame's luminance (Rec. 709 weights on the PNG's
// values), blurred (Gaussian, sigma 1.5 px, edges clamped); per band of view distance on the ground, near (under
// 10 m), middle (10-40 m), distant (40-400 m) and far (past 400 m), the half-pixel frame against the average of its
// neighbours as a share of the real one-pixel change:
//     mean |f1 - (f0 + f2) / 2| / mean |f2 - f0|
// Smooth motion scores near 0, aliasing that reshuffles with every sub-pixel offset near 1. Blender's gate puts its
// per-texel material against its old one + 0.02; the port's is Blender's per-texel material + 0.02 on each band
// (out/surfacing/material/shimmer_<case>.json, its record of the same view). Reads the PNGs only.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surfacing/shimmer_test.mjs
//         [--case canyon] [--view approach_walk] [--label shimmer] [--dir <views out>]
//
// Writes tests/out/surfacing/shimmer_test_<case>.json.

import * as M from './_material.mjs';
import { readImage } from '../../build/surfacing.js';

const A = M.argsOf();
const name = A.opt('--case', 'canyon');
const view = A.opt('--view', 'approach_walk');
const label = A.opt('--label', 'shimmer');
const dir = A.opt('--dir', M.out('views'));
const BANDS = [['near', 0, 10], ['middle', 10, 40], ['distant', 40, 400], ['far', 400, null]];
const TOLERANCE = 0.02;
const T = new M.C.Checks(`surfacing: the shimmer probe on ${name} ${view} (check 4)`);

const file = (v) => `${dir}/${name}_${view}_${label}_${v}.png`;
const need = ['built', 'turn1', 'turn2', 'dist0', 'dist10', 'dist40', 'dist400'];
const missing = need.filter((v) => !M.W.exists(file(v)));
if (missing.length) {
    T.ok('the seven renders are there', false, `missing ${missing.join(', ')}: run views.mjs --case ${name} --views ${view} ` +
        `--label ${label} --variants ${need.join(',')}`);
    Deno.exit(M.finish(T, `shimmer_test_${name}`));
}

// check_shimmer.blur: a separable Gaussian, radius ceil(3 sigma), the image's edge rows and columns repeated
function blur(a, w, h, sigma = 1.5) {
    const r = Math.ceil(3 * sigma);
    const k = Array.from({ length: 2 * r + 1 }, (_, i) => Math.exp(-0.5 * ((i - r) / sigma) ** 2));
    const ks = k.reduce((s, v) => s + v, 0);
    for (let i = 0; i < k.length; i++) k[i] /= ks;
    const tmp = new Float64Array(w * h), out = new Float64Array(w * h);
    for (let j = 0; j < h; j++) {
        for (let i = 0; i < w; i++) {
            let s = 0;
            for (let q = -r; q <= r; q++) s += k[q + r] * a[Math.min(h - 1, Math.max(0, j + q)) * w + i];
            tmp[j * w + i] = s;
        }
    }
    for (let j = 0; j < h; j++) {
        for (let i = 0; i < w; i++) {
            let s = 0;
            for (let q = -r; q <= r; q++) s += k[q + r] * tmp[j * w + Math.min(w - 1, Math.max(0, i + q))];
            out[j * w + i] = s;
        }
    }
    return out;
}

const im = {};
for (const v of need) im[v] = await readImage(file(v));
const w = im.built.width, h = im.built.height, n = w * h;
const lum = (img) => {
    const a = new Float64Array(n), c = img.channels, s = img.data;
    for (let q = 0; q < n; q++) a[q] = (0.2126 * s[q * c] + 0.7152 * s[q * c + 1] + 0.0722 * s[q * c + 2]) / 255.0;
    return blur(a, w, h);
};
const frames = ['built', 'turn1', 'turn2'].map((v) => lum(im[v]));
const on = (v, q) => im[v].data[q * im[v].channels] > 127;
const atLeast = { 0: 'dist0', 10: 'dist10', 40: 'dist40', 400: 'dist400' };
const rec = { case: name, view, bands: BANDS, tolerance: TOLERANCE, port: {}, parts: {} };
for (const [band, d0, d1] of BANDS) {
    let e = 0, m = 0, k = 0;
    for (let q = 0; q < n; q++) {
        if (!on('dist0', q) || !on(atLeast[d0], q) || (d1 !== null && on(atLeast[d1], q))) continue;
        e += Math.abs(frames[1][q] - 0.5 * (frames[0][q] + frames[2][q]));
        m += Math.abs(frames[2][q] - frames[0][q]);
        k++;
    }
    rec.port[band] = k < 200 ? null : +(e / Math.max(m, 1e-9)).toFixed(3);
    rec.parts[band] = { pixels: k, crawl_1e4: k ? +(1e4 * e / k).toFixed(2) : null, motion_1e4: k ? +(1e4 * m / k).toFixed(2) : null };
}
const brec = M.W.blenderEdition() ? `${M.W.blenderTests()}/out/surfacing/material/shimmer_${name}.json` : null;
const b = brec && M.W.exists(brec) ? JSON.parse(Deno.readTextFileSync(brec)) : null;
if (b && b.view === view) rec.blender = { today: b.today, per_texel: b.per_texel };
const lines = BANDS.map(([band]) => `${band} ${rec.port[band] ?? '-'} (${rec.parts[band].pixels} px; crawl ${rec.parts[band].crawl_1e4 ?? '-'}, ` +
    `motion ${rec.parts[band].motion_1e4 ?? '-'} x 1e-4)` + (rec.blender ? `, Blender ${rec.blender.per_texel?.[band] ?? '-'} (old material ` +
    `${rec.blender.today?.[band] ?? '-'})` : ''));
const good = rec.blender
    ? BANDS.every(([band]) => rec.port[band] === null || rec.blender.per_texel?.[band] === null || rec.blender.per_texel?.[band] === undefined
        || rec.port[band] <= rec.blender.per_texel[band] + TOLERANCE)
    : false;
T.ok(`${view}: no band of view distance crawls more than Blender's per-texel material + ${TOLERANCE}`, good,
    (rec.blender ? '' : 'no Blender record of the view to hold it to; ') + lines.join('; '));
Deno.exit(M.finish(T, `shimmer_test_${name}`, rec));
