// The material's check 6 (SURFACING_DESIGN.md 5.4 package 2; PORT_PLAN.md 8.2 row P17: "C and the near material
// matching across the 64-cell cross-fade"): blender/tests/terrain/surfacing/check_far.py's measure on the port. Per
// view, views.mjs --variants built,near,far,allow,band renders the per-texel material with only its hand-off distance
// moved (setFarDistance: nothing recompiles): near only (D0 past everything) and far only (D0 at 1 cm: C wherever the
// hand-off allows it), and two masks (where the far colour may draw: more than 64 main cells outside the outermost hero
// window; the band D0..1.5 D0). The same pixels drawn by the near material and by C are the hand-off's two sides:
//   - over the ground the far colour may draw: the CIELAB difference of the two renders' mean colours (gates at 2),
//     and per pixel its median and 90th percentile;
//   - the same over the band, where the hand-off happens as built;
//   - the share of the frame the far colour takes as built.
// Beside Blender's own numbers for the same views (out/surfacing/material/far_<case>.json). Reads the PNGs only.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surfacing/far_test.mjs --case canyon
//         --views aerial_down_canyon,low_oblique [--label far] [--dir <views out>]

import * as M from './_material.mjs';
import { readImage } from '../../build/surfacing.js';

const A = M.argsOf();
const name = A.opt('--case', 'canyon');
const views = A.list('--views', ['aerial_down_canyon', 'low_oblique']);
const label = A.opt('--label', 'far');
const dir = A.opt('--dir', M.out('views'));
const T = new M.C.Checks(`surfacing: the far hand-off on ${name} (check 6)`);

const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
function lab(r, g, b) {
    const [R, G, B] = [r, g, b].map((v) => lin(v / 255));
    const X = (0.4124 * R + 0.3576 * G + 0.1805 * B) / 0.95047, Y = 0.2126 * R + 0.7152 * G + 0.0722 * B, Z = (0.0193 * R + 0.1192 * G + 0.9505 * B) / 1.08883;
    const f = (t) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
    const fx = f(X), fy = f(Y), fz = f(Z);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}
const dE = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

const brec = M.W.blenderEdition() ? `${M.W.blenderTests()}/out/surfacing/material/far_${name}.json` : null;
const b = brec && M.W.exists(brec) ? JSON.parse(Deno.readTextFileSync(brec)) : null;
const rec = {};
let ok = true;
for (const v of views) {
    const f = (variant) => `${dir}/${name}_${v}_${label}_${variant}.png`;
    if (!['built', 'near', 'far', 'allow', 'band'].every((x) => M.W.exists(f(x)))) {
        T.ok(`${v}: the five renders are there`, false, `run views.mjs --case ${name} --views ${v} --label ${label} --variants built,near,far,allow,band`);
        ok = false;
        continue;
    }
    const im = {};
    for (const x of ['built', 'near', 'far', 'allow', 'band']) im[x] = await readImage(f(x));
    const n = im.near.width * im.near.height, c = im.near.channels;
    const px = (img, q) => [img.data[q * img.channels], img.data[q * img.channels + 1], img.data[q * img.channels + 2]];
    const stats = (mask) => {
        const sN = [0, 0, 0], sF = [0, 0, 0], d = [];
        let k = 0;
        for (let q = 0; q < n; q++) {
            if (!mask(q)) continue;
            const a = px(im.near, q), bb = px(im.far, q);
            for (let ch = 0; ch < 3; ch++) { sN[ch] += a[ch]; sF[ch] += bb[ch]; }
            d.push(dE(lab(...a), lab(...bb)));
            k++;
        }
        if (!k) return { pixels: 0 };
        const mN = lab(...sN.map((s) => s / k)), mF = lab(...sF.map((s) => s / k));
        return { pixels: k, mean_colour_dE: +dE(mN, mF).toFixed(2), pixel_dE_median: +M.percentile(d, 50).toFixed(2),
            pixel_dE_p90: +M.percentile(d, 90).toFixed(2), near_mean_lab: mN.map((x) => +x.toFixed(1)), far_mean_lab: mF.map((x) => +x.toFixed(1)) };
    };
    const allow = (q) => im.allow.data[q * im.allow.channels] > 127;
    const band = (q) => im.band.data[q * im.band.channels] > 127 && allow(q);
    const ground = (q) => im.allow.data[q * im.allow.channels] > 127 || px(im.near, q).some((x, ch) => Math.abs(x - px(im.built, q)[ch]) >= 0);
    let asBuilt = 0;
    for (let q = 0; q < n; q++) {
        const a = px(im.built, q), bb = px(im.near, q);
        if (allow(q) && (Math.abs(a[0] - bb[0]) > 2 || Math.abs(a[1] - bb[1]) > 2 || Math.abs(a[2] - bb[2]) > 2)) asBuilt++;
    }
    void ground;
    const r = { where_far_may_draw: stats(allow), in_the_band: stats(band), far_as_built_share: +(asBuilt / n).toFixed(3) };
    const bv = b?.views?.[v];
    if (bv) r.blender = { where_far_may_draw: bv.where_far_may_draw, in_the_band: bv.in_the_band, far_as_built_share: bv.far_as_built_share };
    rec[v] = r;
    const good = (r.where_far_may_draw.pixels === 0 || r.where_far_may_draw.mean_colour_dE <= 2.0)
        && (r.in_the_band.pixels === 0 || r.in_the_band.mean_colour_dE <= 2.0);
    if (!good) ok = false;
    T.ok(`${v}: C and the near material agree where the far colour may draw and across the band (mean colour within dE 2)`, good,
        `may draw: dE ${r.where_far_may_draw.mean_colour_dE ?? '-'} (px median ${r.where_far_may_draw.pixel_dE_median ?? '-'}, p90 ` +
        `${r.where_far_may_draw.pixel_dE_p90 ?? '-'}) over ${r.where_far_may_draw.pixels} px; band: dE ${r.in_the_band.mean_colour_dE ?? '-'} ` +
        `over ${r.in_the_band.pixels} px; C as built ${(100 * r.far_as_built_share).toFixed(1)} % of the frame` +
        (bv ? `; Blender: dE ${bv.where_far_may_draw?.mean_colour_dE} / ${bv.in_the_band?.mean_colour_dE}, ${(100 * bv.far_as_built_share).toFixed(1)} %` : ''));
}
void ok;
Deno.exit(M.finish(T, `far_test_${name}`, { case: name, views: rec }));
