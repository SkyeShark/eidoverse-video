// Map sheets of the surface data (PORT_PLAN.md 8.2 row P14: "map sheets beside the hillshade, looked at";
// SURFACING_DESIGN.md 5.4, package 1, item 1): Blender's blender/tests/terrain/surface_data/sheets.py on the port's
// bakes: each map beside the hillshade at the main level and one hero level of a case, north up, the panels in
// sheets.py's order and colours (signed maps blue (-) to red (+) over a light hillshade, 0-1 maps in a sequential
// ramp over it, src_offset the debris' source height above the ground's own bed, n20 the 20 m normal's azimuth (hue)
// by its dip, 'relief' D's normal with the sub-cell gradient added, the palette's colours as they are).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/sheets.mjs
//         [--case toroweap,canyon,...] [--panel 256]
//
// Writes tests/out/surface_data/sheets/<case>.png and <case>.json (the panels' order, rows of 7, and each map's 1st,
// 50th and 99th percentiles). No labels are drawn (no font here): the JSON names the panels. JavaScript per texel
// here is test code.

import * as Io from '../../core/io.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const A = S.argsOf();
const cases = A.list('--case', ['toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon', 'alpine_valley']);
const PANEL = Number(A.opt('--panel', 256));
const PANELS = ['hillshade', 'relief', 'crest', 'crest_fine', 'crease', 'cavity', 'settle', 'valley', 'fresh', 'spi', 'grain',
    'src_offset', 'streak', 'snowpack', 'n20', 'flow', 'wetness', 'channels', 'down_colour', 'down_share', 'far_colour'];
const SIGNED = ['crest', 'crest_fine', 'crease'];
const SEQ = [[0.0, [0.05, 0.05, 0.2]], [0.25, [0.2, 0.25, 0.6]], [0.5, [0.2, 0.6, 0.55]], [0.75, [0.85, 0.8, 0.25]], [1.0, [1.0, 1.0, 0.85]]];
const DIV = [[0.0, [0.1, 0.25, 0.85]], [0.5, [0.95, 0.95, 0.95]], [1.0, [0.85, 0.15, 0.1]]];
const COLS = 7;

const clamp = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
function ramp(t, stops) {
    t = clamp(t);
    for (let k = 1; k < stops.length; k++) {
        if (t <= stops[k][0]) {
            const [t0, c0] = stops[k - 1], [t1, c1] = stops[k];
            const u = (t - t0) / (t1 - t0);
            return c0.map((v, q) => v + (c1[q] - v) * u);
        }
    }
    return stops[stops.length - 1][1];
}
function hsv(h, s, v) {
    const i = Math.floor(h * 6), f = h * 6 - i, p = v * (1 - s), q = v * (1 - s * f), t = v * (1 - s * (1 - f));
    return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][((i % 6) + 6) % 6];
}
function shade(nx, ny, nz, az = 315, alt = 45) {
    const L = Math.hypot(nx, ny, nz), a = (az * Math.PI) / 180, e = (alt * Math.PI) / 180;
    return clamp((nx * Math.sin(a) * Math.cos(e) + ny * Math.cos(a) * Math.cos(e) + nz * Math.sin(e)) / L);
}
// np.gradient's hillshade (sheets.hillshade)
function hillshade(h, n, cell) {
    const out = new Float64Array(n * n);
    const at = (i, j) => h[j * n + i];
    for (let j = 0; j < n; j++) {
        for (let i = 0; i < n; i++) {
            const gx = i === 0 ? (at(1, j) - at(0, j)) / cell : i === n - 1 ? (at(n - 1, j) - at(n - 2, j)) / cell : (at(i + 1, j) - at(i - 1, j)) / (2 * cell);
            const gy = j === 0 ? (at(i, 1) - at(i, 0)) / cell : j === n - 1 ? (at(i, n - 1) - at(i, n - 2)) / cell : (at(i, j + 1) - at(i, j - 1)) / (2 * cell);
            out[j * n + i] = shade(-gx, -gy, 1);
        }
    }
    return out;
}
// a map (m x m, or its channel of an (m, m, 3) colour) at texel (i, j) of an n grid (nearest)
const sample = (a, m, n, i, j, ch = null, three = false) => {
    const ii = Math.min(m - 1, Math.floor(((i + 0.5) * m) / n)), jj = Math.min(m - 1, Math.floor(((j + 0.5) * m) / n));
    return three ? a[3 * (jj * m + ii) + ch] : a[jj * m + ii];
};

const R = await G.init();
const outDir = `${S.W.out('surface_data')}/sheets`;
Deno.mkdirSync(outDir, { recursive: true });
for (const name of cases) {
    const got = await S.portSurface(name, { palette: true });
    if (!got) continue;
    const { t, sd } = got;
    const roles = t.levels.map((lv) => lv.role);
    const main = roles.indexOf('main');
    const heroes = roles.map((r, i) => [r, i]).filter(([r]) => r === 'hero').map(([, i]) => i);
    const hi = heroes.length ? heroes[Math.min(1, heroes.length - 1)] : null;
    const levels = [main, ...(hi !== null ? [hi] : [])];
    const rows = [], stats = {};
    for (const i of levels) {
        const lv = t.levels[i], n = lv.n, cell = Number(lv.cell);
        const m = await sd.maps(i);
        const h = t.fields(i).h;
        const hs = hillshade(h, n, cell);
        const panels = {};
        const has = (k) => m[k] !== undefined && m[k] !== null;
        const side = (a) => Math.round(Math.sqrt(a.shape3 ? a.length / 3 : a.length));
        for (const k of PANELS) {
            let f = null;
            if (k === 'hillshade') f = (i_, j_) => { const v = hs[j_ * n + i_]; return [v, v, v]; };
            else if (k === 'relief' && has('normal_x')) {
                const md = side(m.normal_x);
                f = (i_, j_) => {
                    const nx = sample(m.normal_x, md, n, i_, j_), ny = sample(m.normal_y, md, n, i_, j_);
                    const nz = Math.sqrt(clamp(1 - nx * nx - ny * ny, 1e-6, 1));
                    const gx = has('detail_gx') ? sample(m.detail_gx, md, n, i_, j_) : 0, gy = has('detail_gy') ? sample(m.detail_gy, md, n, i_, j_) : 0;
                    const v = shade(-(-nx / nz + 0.5 * gx), -(-ny / nz + 0.5 * gy), 1);
                    return [v, v, v];
                };
            } else if (k === 'n20' && has('n20_x')) {
                const md = side(m.n20_x);
                f = (i_, j_) => {
                    const x = sample(m.n20_x, md, n, i_, j_), y = sample(m.n20_y, md, n, i_, j_);
                    const dip = clamp(Math.hypot(x, y) / 0.7), hue = ((((Math.atan2(x, y) * 180) / Math.PI) % 360) + 360) % 360 / 360;
                    const b = 0.55 + 0.45 * hs[j_ * n + i_];
                    return hsv(hue, dip, 1).map((v) => v * b);
                };
            } else if (k === 'src_offset' && has('src_dz')) {
                const md = side(m.src_dz);
                const st = has('strata') ? m.strata : h;
                f = (i_, j_) => {
                    const v = (h[j_ * n + i_] + sample(m.src_dz, md, n, i_, j_)) - st[j_ * n + i_];
                    const b = 0.55 + 0.45 * hs[j_ * n + i_];
                    return ramp(0.5 + 0.5 * Math.tanh(v / 60), DIV).map((c) => c * b);
                };
            } else if ((k === 'down_colour' || k === 'far_colour') && has(k)) {
                const md = side(m[k]);
                f = (i_, j_) => {
                    const b = 0.55 + 0.45 * hs[j_ * n + i_];
                    return [0, 1, 2].map((c) => clamp(clamp(sample(m[k], md, n, i_, j_, c, true)) ** (1 / 2.2) * b * 1.1));
                };
            } else if (has(k) && !m[k].shape3) {
                const md = side(m[k]);
                f = (i_, j_) => {
                    const v = sample(m[k], md, n, i_, j_);
                    const b = 0.55 + 0.45 * hs[j_ * n + i_];
                    const c = SIGNED.includes(k) ? ramp(0.5 + 0.5 * v, DIV) : k === 'snowpack' ? ramp(Math.sqrt(clamp(v / 4)), SEQ) : ramp(v, SEQ);
                    return c.map((x) => x * b);
                };
            }
            if (f) panels[k] = f;
        }
        rows.push({ i, n, panels });
        stats[`L${i}`] = {};
        for (const k of Object.keys(m).sort()) {
            const a = m[k];
            if (a.shape3 || !(PANELS.includes(k) || ['src_dz', 'detail_gx', 'normal_x'].includes(k))) continue;
            const s = Float64Array.from(a).sort();
            stats[`L${i}`][k] = [1, 50, 99].map((q) => +s[Math.min(s.length - 1, Math.floor((q / 100) * (s.length - 1)))].toFixed(4));
        }
    }
    const names = PANELS.filter((k) => rows.some((r) => k in r.panels));
    const nrow = Math.ceil(names.length / COLS);
    const gap = 6;
    const W = COLS * (PANEL + gap), H = rows.length * (nrow * (PANEL + gap) + 12);
    const img = new Uint32Array(W * H * 3).fill(24);
    let y0 = 0;
    for (const r of rows) {
        y0 += 12;
        names.forEach((k, q) => {
            const f = r.panels[k];
            if (!f) return;
            const ox = (q % COLS) * (PANEL + gap), oy = y0 + Math.floor(q / COLS) * (PANEL + gap);
            for (let py = 0; py < PANEL; py++) {
                const j = Math.min(r.n - 1, Math.floor(((PANEL - 1 - py + 0.5) * r.n) / PANEL));      // north up
                for (let px = 0; px < PANEL; px++) {
                    const i = Math.min(r.n - 1, Math.floor(((px + 0.5) * r.n) / PANEL));
                    const c = f(i, j);
                    const o = ((oy + py) * W + ox + px) * 3;
                    for (let q2 = 0; q2 < 3; q2++) img[o + q2] = Math.round(clamp(c[q2]) * 255);
                }
            }
        });
        y0 += nrow * (PANEL + gap);
    }
    const field = R.field(H, W * 3, 1, img, 'u32');
    await Io.writePng(`${outDir}/${name}.png`, { field, width: W, height: H, channels: 3, bitDepth: 8 });
    field.destroy();
    Deno.writeTextFileSync(`${outDir}/${name}.json`, JSON.stringify({ case: name, levels: rows.map((r) => r.i), columns: COLS,
        panels: names, stats }, null, 1));
    console.log(`[sheets] ${name}: levels ${rows.map((r) => r.i).join(', ')}; panels ${names.join(', ')} -> ${outDir}/${name}.png`);
    t.dispose?.();
}
G.shutdown();
