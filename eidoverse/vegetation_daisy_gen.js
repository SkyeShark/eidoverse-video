// daisy_gen — the daisy (Leucanthemum: oxeye / Shasta) for createFlora: one
// CLUMP per instance — a basal rosette of spatulate lobed leaves on tube
// petioles, 1-4 ribbed flowering stems with clasping toothed stem leaves, and
// on each stem a head: involucre cup of imbricate bracts, domed disc of
// phyllotaxis florets, a whorl of 24-30 notched ray florets (sometimes a bud
// instead), plus a far-LOD impostor card per head. One geometry on the ONE
// daisy_ trim sheet.
//
// Craft rules baked in:
//   - MATERIALS FIRST: the sheet was modelled and rendered in Blender
//     (eidoverse/assets/grass/daisy_src/daisy_art.py) before any card existed;
//     petal and leaf cards are planes whose station widths AND uv windows
//     follow daisy_fit.json — the measured alpha envelope of that art.
//   - STRUCTURE IS TUBES: stems, necks and petioles are parallel-transported
//     swept tubes, one continuous sweep per stem (base -> neck -> into the
//     involucre), never ribbons.
//   - The head is ONE rigid assembly in wind (identical aH on every head
//     vertex — the corn-ear law), welded to its stem top.
//   - The gen OWNS its normals (createFlora must not re-blend them).
//   - Petals CLOSE about real hinges: every head vertex carries a record
//     (head centre, hinge point + axis, close angle, LOD class) in a storage
//     buffer read by vertexIndex — no extra vertex buffer (the stack's
//     8-buffer ceiling is already full on large instanced fields). The same
//     record drives the distance LOD: detail collapses as the camera-facing
//     impostor card grows, so a far stand keeps its colour.
//
// daisy_ sheet (1024², v up) — layout owned by daisy_art.py:
//   DISC    circle c(212,812) r207 px ↔ 9.54 mm (planar projection, s1 = +u)
//   PETALS  8 x 2 cells of 74 x 207 px from (428,605); 18 mm = 200 px — cell 7
//           (row 0, col 7) holds the far-LOD impostor instead of a ray
//   BASAL   two windows 635 x 178 px, leaf base left, midrib centred
//   STEM    two windows 635 x 106 px, auricles left
//   INVOL   circle c(832,400) r184 px ↔ 9.4 mm, the cup seen from below
//   STALK   u 652-1012 px (half circumference, 5 ribs), v 16-104 px base->top
//   IMP     72 px whole-head impostor at (947,739) — the far LOD card

const T3 = globalThis.THREE;
import { Rng } from './vegetation_shrub_gen.js';

const TAU = Math.PI * 2;
const PX = 1 / 1024;
const tri = (s) => { const m = s % 2; return m <= 1 ? m : 2 - m; };

export const DAISY_SHEET = {
    disc: { cu: 212 * PX, cv: 812 * PX, r: 207 * PX, mm: 9.54 },
    petals: { x0: 428, y0: 605, cw: 74, ch: 207, mmPerPx: 0.09 },
    basal: [{ x0: 5, y0: 418, x1: 640, y1: 596, L: 64 }, { x0: 5, y0: 236, x1: 640, y1: 414, L: 60 }],
    stemLeaf: [{ x0: 5, y0: 124, x1: 640, y1: 230, L: 44 }, { x0: 5, y0: 12, x1: 640, y1: 118, L: 40 }],
    invol: { cu: 832 * PX, cv: 400 * PX, r: 184 * PX, mm: 9.4 },
    stalk: { u0: 652 * PX, u1: 1012 * PX, v0: 16 * PX, v1: 104 * PX },
    // far-LOD impostor: the whole head from the front, a 72 px tile in ray
    // cell 7 (white neighbours: the tiny mips far cards sample stay white)
    imp: { cu: 983 * PX, cv: 775 * PX, h: 35.5 * PX, discR: 14.1 * PX,
        u0: 947 * PX, u1: 1019 * PX, v0: 739 * PX, v1: 811 * PX },
};

// petal colours (sRGB hex; base -> tip along the ray). 'white' keeps the
// modelled art; the rest recolor the petal region only (disc stays gold).
export const DAISY_COLORS = {
    white:  null,
    orange: { base: 0xc75a36, tip: 0xe68b6b },     // Claude orange, #D97757 mid-ray
    pink:   { base: 0xd24f87, tip: 0xf2a3c4 },     // painted daisy
    yellow: { base: 0xe8a413, tip: 0xf7d24a },
    cream:  { base: 0xe9dcb0, tip: 0xf8f1dc },
};

// mm design units for a 50 mm head (scaled per head)
const RD = 9.0, DOME_H = 2.2;
const domeZ = (rho) => {
    const r2 = Math.min(1, rho) ** 2;
    return rho > 1 ? -3 * (rho - 1) : DOME_H * Math.pow(1 - r2, 0.85) - 0.25 * Math.exp(-((rho / 0.12) ** 2));
};
const cupZ = (r) => -0.8 - 4.6 * Math.pow(Math.max(0, 1 - (r / 8.7) ** 2), 1.35);

const FIT_FALLBACK = {
    petals: Array(16).fill([[0.5, 0.2], [0.5, 0.3], [0.5, 0.31], [0.5, 0.31], [0.5, 0.3]]),
    petalV: Array(16).fill([0.02, 0.98]),
    leaves: {
        basalA: { u: [0.013, 0.986], bands: [[0.5, 0.07], [0.5, 0.13], [0.5, 0.27], [0.5, 0.45], [0.5, 0.49], [0.5, 0.48], [0.5, 0.3]] },
        basalB: { u: [0.013, 0.986], bands: [[0.5, 0.07], [0.5, 0.13], [0.5, 0.27], [0.5, 0.45], [0.5, 0.49], [0.5, 0.48], [0.5, 0.3]] },
        stemA: { u: [0.013, 0.986], bands: [[0.5, 0.4], [0.5, 0.38], [0.5, 0.45], [0.5, 0.43], [0.5, 0.36], [0.5, 0.22], [0.5, 0.05]] },
        stemB: { u: [0.013, 0.986], bands: [[0.5, 0.4], [0.5, 0.38], [0.5, 0.45], [0.5, 0.43], [0.5, 0.36], [0.5, 0.22], [0.5, 0.05]] },
    },
};

export const DAISY_GEN = {
    daisy: {
        height: 0.45,        // flowering stem height (m) of the tallest stem
        headD: 0.05,         // head diameter (m) before headScale
        headScale: 1,        // stylized big heads: 2-4
        stems: [1, 4],
        petals: [24, 30],
        rosette: [5, 8],
        stemLeaves: [3, 5],
        budChance: 0.12,
        lod: [10, 18],       // m: detailed head -> impostor card fade (x headScale); false = never
        facing: null,        // null = wild; { el } = every head faces local +X at elevation el
    },
};

// ── small vector helpers ────────────────────────────────────────────────────
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
const lerp3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const bez3 = (p0, p1, p2, p3, t) => {
    const s = 1 - t;
    return [0, 1, 2].map((k) => s * s * s * p0[k] + 3 * s * s * t * p1[k] + 3 * s * t * t * p2[k] + t * t * t * p3[k]);
};
const rotAxis = (v, k, ang) => {     // Rodrigues
    const c = Math.cos(ang), s = Math.sin(ang), kv = cross(k, v), kd = dot(k, v) * (1 - c);
    return [v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd];
};
const UP = [0, 1, 0];

export function buildDaisyGeometry(name, seed, over = {}) {
    const cfg = { ...(DAISY_GEN[name] ?? DAISY_GEN.daisy), ...over };
    const fit = cfg.fit ?? FIT_FALLBACK;
    const rng = new Rng(seed);
    const R = () => rng.next();
    const irange = (a, b) => Math.floor(rng.range(a, b + 0.999));

    const pos = [], uv = [], aH = [], idx = [], nrm = [];
    const rec = [];                      // 12 floats per vertex (close records)
    const fold = new Map();              // ray-card vertex -> direction its normal tilts (trough fold)
    let vb = 0;
    let curRec = null;                   // record applied to vertices being emitted
    const V = (p, u, v, a, n = [0, 1, 0]) => {
        pos.push(p[0], p[1], p[2]); uv.push(u, v); aH.push(a); nrm.push(n[0], n[1], n[2]);
        if (curRec) rec.push(...curRec); else rec.push(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
        return vb++;
    };
    const tri3 = (a, b, c) => idx.push(a, b, c);
    const quad = (a, b, c, d) => idx.push(a, b, c, a, c, d);

    // swept tube over a centreline with a parallel-transported frame and
    // continuous fibre-v (the sunflower sweep), radial normals
    const tubeRanges = [];
    function sweepTube(pts, radii, weights, RADS, vA, vB) {
        const n = pts.length;
        const start = vb;
        const tans = pts.map((_, i) => norm(sub(pts[Math.min(n - 1, i + 1)], pts[Math.max(0, i - 1)])));
        let s1 = Math.abs(tans[0][1]) < 0.95 ? [tans[0][2], 0, -tans[0][0]] : [1, 0, 0];
        s1 = norm(sub(s1, mul(tans[0], dot(s1, tans[0]))));
        let arcTot = 0;
        for (let i = 1; i < n; i++) arcTot += Math.hypot(...sub(pts[i], pts[i - 1]));
        const rows = [];
        let arc = 0;
        const { u0, u1 } = DAISY_SHEET.stalk;
        for (let i = 0; i < n; i++) {
            if (i > 0) {
                arc += Math.hypot(...sub(pts[i], pts[i - 1]));
                s1 = norm(sub(s1, mul(tans[i], dot(s1, tans[i]))));
            }
            const t = tans[i], s2 = cross(t, s1);
            const vv = vA + (vB - vA) * (arc / (arcTot || 1));
            const row = [];
            for (let j = 0; j <= RADS; j++) {
                const an = (j / RADS) * TAU;
                const o = add(mul(s1, Math.cos(an)), mul(s2, Math.sin(an)));
                row.push(V(add(pts[i], mul(o, radii[i])), u0 + (u1 - u0) * tri((j / RADS) * 2), vv, weights[i], o));
            }
            rows.push(row);
        }
        for (let i = 0; i < n - 1; i++) for (let j = 0; j < RADS; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
        tubeRanges.push([start, vb]);
    }

    // a fitted leaf card along a centreline; stations follow the measured
    // envelope (7 stations over the art's u range), 2 or 3 columns across
    function leafCard(win, key, pts, sideDirs, sizeMM, a0, a1, t0 = 0, cols = 2, upK = 0.4) {
        const f = fit.leaves?.[key] ?? FIT_FALLBACK.leaves[key];
        const bands = f.bands;
        const NB = bands.length;
        const winW = (win.x1 - win.x0) * PX, winH = (win.y1 - win.y0) * PX;
        const mmPerPx = win.L / (win.x1 - win.x0 - 16);
        const acrossMM = (win.y1 - win.y0) * mmPerPx;          // window height in mm
        const g0 = Math.round(t0 * (NB - 1));
        const sB = vb;
        const nSt = NB - g0;
        const sc = (sizeMM * 0.001) / win.L;                    // metres per art-mm
        for (let g = g0; g < NB; g++) {
            const tt = g / (NB - 1);
            const k = (g - g0) / (nSt - 1);
            const c = pts(k), side = sideDirs(k);
            const [cF, hwF] = bands[g];
            const hw = hwF * acrossMM * sc;
            const off = (cF - 0.5) * acrossMM * sc;
            const u = win.x0 * PX + (f.u[0] + tt * (f.u[1] - f.u[0])) * winW;
            const vC = win.y0 * PX + cF * winH, vHw = hwF * winH;
            const a = a0 + (a1 - a0) * k;
            const nUp = norm(cross(sub(pts(Math.min(1, k + 0.02)), pts(Math.max(0, k - 0.02))), side));   // card front
            const cc = add(c, mul(side, off));
            if (cols === 2) {
                V(sub(cc, mul(side, hw)), u, vC - vHw, a, nUp);
                V(add(cc, mul(side, hw)), u, vC + vHw, a, nUp);
            } else {
                const trough = mul(nUp, -hw * 0.22);           // midrib valley
                V(sub(cc, mul(side, hw)), u, vC - vHw, a, nUp);
                V(add(cc, trough), u, vC, a, nUp);
                V(add(cc, mul(side, hw)), u, vC + vHw, a, nUp);
            }
        }
        for (let g = 0; g < nSt - 1; g++) {
            const A = sB + g * cols, B = A + cols;
            for (let q = 0; q < cols - 1; q++) quad(A + q, B + q, B + q + 1, A + q + 1);
        }
        return { start: sB, end: vb, upK };
    }

    const H0 = cfg.height;
    const mm = 0.001;
    const leafBlocks = [];
    const headInfo = [];

    // ── basal rosette ────────────────────────────────────────────────────
    const nRos = irange(cfg.rosette[0], cfg.rosette[1]);
    const rosRot = R() * TAU;
    for (let i = 0; i < nRos; i++) {
        const az = rosRot + i * 2.39996 + rng.vary(0, 0.25);
        const d = [Math.cos(az), 0, Math.sin(az)];
        const sz = rng.range(0.75, 1.1) * (1 - 0.25 * (i / nRos));
        const petL = rng.range(0.022, 0.034) * sz, rise = rng.range(0.28, 0.5);
        const p0 = [d[0] * 0.004, -0.012, d[2] * 0.004];
        const p1 = add(p0, add(mul(d, petL * 0.55), [0, petL * rise * 0.9 + 0.01, 0]));
        const p2 = add(p0, add(mul(d, petL), [0, petL * rise + 0.008, 0]));
        const ptsP = [0, 0.4, 0.75, 1].map((t) => {
            const s = 1 - t;
            return [0, 1, 2].map((k) => s * s * p0[k] + 2 * s * t * p1[k] + t * t * p2[k]);
        });
        const aL = 0.02 + 0.03 * sz;
        sweepTube(ptsP, [1.15, 1.0, 0.85, 0.72].map((r) => r * mm * Math.sqrt(sz)), ptsP.map((_, k) => aL * k / 3),
            4, DAISY_SHEET.stalk.v0, DAISY_SHEET.stalk.v0 + 0.04);
        // blade continues the petiole tangent, arches and lays its tip down
        const win = DAISY_SHEET.basal[i % 2], key = i % 2 ? 'basalB' : 'basalA';
        const bladeL = win.L * mm * sz * rng.range(0.9, 1.15);
        const tan = norm(sub(p2, p1));
        const b0 = sub(p2, mul(tan, 0.0015));
        const b1 = add(b0, mul(tan, bladeL * 0.35));
        const tipH = rng.range(-0.004, 0.012);
        const b3 = [b0[0] + d[0] * bladeL * 0.92, Math.max(0.004, tipH + 0.004), b0[2] + d[2] * bladeL * 0.92];
        const b2 = [b0[0] + d[0] * bladeL * 0.62, b0[1] + 0.012 * sz, b0[2] + d[2] * bladeL * 0.62];
        const twist = rng.vary(0, 0.35);
        const side0 = norm(cross(UP, d));
        const pts = (k) => bez3(b0, b1, b2, b3, k);
        const sides = (k) => {
            const tg = norm(sub(pts(Math.min(1, k + 0.02)), pts(Math.max(0, k - 0.02))));
            return norm(rotAxis(side0, tg, twist * k));
        };
        leafBlocks.push(leafCard(win, key, pts, sides, bladeL / mm / 0.82, aL, aL + 0.03, 1 / 6, 3, 0.55));
    }

    // ── flowering stems + heads ─────────────────────────────────────────
    const nStems = Math.max(cfg.stems[0], Math.min(cfg.stems[1],
        Math.round((rng.range(cfg.stems[0], cfg.stems[1]) + rng.range(cfg.stems[0], cfg.stems[1])) / 2)));
    const leanRot = R() * TAU;
    const placedHeads = [];
    for (let si = 0; si < nStems; si++) {
        const hk = H0 * (si === 0 ? rng.range(0.92, 1.05) : rng.range(0.62, 0.98));
        const bud = si > 0 && R() < cfg.budChance;
        const dHead = cfg.headD * (cfg.headScale ?? 1) * rng.range(0.86, 1.14) * (bud ? 0.5 : 1);   // metres
        let leanAz = leanRot + si * (TAU / nStems) + rng.vary(0, 0.35);
        let leanAng = nStems === 1 ? rng.range(0.02, 0.1) : rng.range(0.1, 0.22);
        // facing: one direction for the stroke (heading) or wild
        let az, el;
        if (cfg.facing) {
            az = rng.vary(0, 0.32);
            el = Math.max(0.35, Math.min(1.5, cfg.facing.el + rng.vary(0, 0.14)));
        } else {
            az = R() * TAU;
            el = rng.range(0.6, 1.45);
        }
        const ax = [Math.cos(el) * Math.cos(az), Math.sin(el), Math.cos(el) * Math.sin(az)];
        const s = dHead / 0.05;                                   // head scale vs the 50 mm design
        const base = [Math.cos(leanAz) * 0.012 * (si ? 1 : 0.3), -0.02, Math.sin(leanAz) * 0.012 * (si ? 1 : 0.3)];
        let C;
        for (let tries = 0; tries < 6; tries++) {
            const top = [base[0] + Math.cos(leanAz) * Math.sin(leanAng) * hk, hk * Math.cos(leanAng * 0.8),
                base[2] + Math.sin(leanAz) * Math.sin(leanAng) * hk];
            C = add(top, mul(ax, 5.6 * mm * s));
            const clash = placedHeads.some((q) => Math.hypot(...sub(q.c, C)) < 0.55 * (q.d + dHead));
            if (!clash) break;
            leanAng += 0.07; leanAz += 0.5;
        }
        placedHeads.push({ c: C, d: dHead });
        const neck = sub(C, mul(ax, 5.6 * mm * s));              // involucre bottom
        const stemLen = Math.hypot(...sub(neck, base));
        const lean = norm([Math.cos(leanAz) * Math.sin(leanAng), Math.cos(leanAng), Math.sin(leanAz) * Math.sin(leanAng)]);
        const q1 = add(base, mul(lean, stemLen * 0.45));
        const q2 = sub(neck, mul(ax, stemLen * 0.16));
        const aTop = Math.min(1.1, 0.35 + 0.65 * (hk / H0));
        const NS = 14;
        const spts = [], srad = [], swt = [];
        const rS = Math.sqrt(Math.max(1, s)) * mm;
        for (let k = 0; k <= NS; k++) {
            const t = 1 - Math.pow(1 - k / NS, 1.5);           // rings crowd into the neck bend
            spts.push(bez3(base, q1, q2, neck, t));
            srad.push((1.55 - 0.45 * t + 0.35 * Math.max(0, (t - 0.88) / 0.12) ** 2) * rS);
            swt.push(aTop * Math.pow(t, 1.25));
        }
        // push the last ring INTO the involucre so the junction is buried
        spts.push(add(neck, mul(ax, 1.4 * mm * s))); srad.push(1.3 * rS); swt.push(aTop);
        sweepTube(spts, srad, swt, 5, DAISY_SHEET.stalk.v0 + 0.01, DAISY_SHEET.stalk.v1);
        const stemAt = (t) => bez3(base, q1, q2, neck, t);
        // stem leaves: sessile, clasping, alternate, smaller upward
        const nSL = bud ? 1 : irange(cfg.stemLeaves[0], cfg.stemLeaves[1]);
        for (let li = 0; li < nSL; li++) {
            const f = 0.08 + 0.6 * ((li + rng.range(0.1, 0.8)) / nSL);
            const p = stemAt(f);
            const tg = norm(sub(stemAt(f + 0.02), stemAt(f - 0.02)));
            const azL = leanAz + Math.PI * 0.5 + li * 2.4 + rng.vary(0, 0.4);
            let out = [Math.cos(azL), 0, Math.sin(azL)];
            out = norm(sub(out, mul(tg, dot(out, tg))));
            const leafL = rng.range(0.032, 0.048) * (1.15 - 0.6 * f) * Math.max(1, Math.sqrt(s) * 0.8);
            const ang = rng.range(0.5, 0.85);                     // from the stem axis
            const d0 = norm(add(mul(tg, Math.cos(ang)), mul(out, Math.sin(ang))));
            const l0 = add(p, mul(out, 0.0009));
            const l1 = add(l0, mul(d0, leafL * 0.45));
            const l3 = add(add(l0, mul(d0, leafL * 0.95)), [0, -leafL * rng.range(0.12, 0.3), 0]);
            const l2 = add(lerp3(l1, l3, 0.5), [0, leafL * 0.05, 0]);
            const pts = (k) => bez3(l0, l1, l2, l3, k);
            const side0 = norm(cross(tg, out));
            const sides = (k) => {
                const tgl = norm(sub(pts(Math.min(1, k + 0.02)), pts(Math.max(0, k - 0.02))));
                return norm(sub(side0, mul(tgl, dot(side0, tgl))));
            };
            const win = DAISY_SHEET.stemLeaf[li % 2], key = li % 2 ? 'stemB' : 'stemA';
            const aAt = aTop * Math.pow(f, 1.25);
            leafBlocks.push(leafCard(win, key, pts, sides, leafL / mm, aAt, aAt + 0.05, 0, 2, 0.3));
        }
        const petals = buildHead(C, ax, s, aTop, bud);
        headInfo.push({ c: C, a: ax, d: dHead, bud, petals, aH: aTop });
    }

    // ── one head: involucre cup, disc dome, ray whorl ───────────────────
    function buildHead(C, a, s, aHead, bud) {
        let s1 = norm(cross(a, [0, 1, 0]));
        if (!isFinite(s1[0]) || Math.hypot(...cross(a, [0, 1, 0])) < 1e-3) s1 = [1, 0, 0];
        const s2 = cross(a, s1);                                   // cross(s1, s2) = a
        const radial = (th) => add(mul(s1, Math.cos(th)), mul(s2, Math.sin(th)));
        const P = (r, x, th) => add(C, add(mul(a, x * mm * s), mul(radial(th), r * mm * s)));
        const lodC = bud ? 0 : 1;                                   // 1 = near-only detail
        const recHead = [...C, 1, 0, 0, 0, 0, 0, 0, 0, lodC];
        curRec = recHead;
        // involucre cup (outer surface faces away from the head)
        {
            const RADS = 12;
            const prof = [[1.25, cupZ(1.25) - 0.35], [2.6, cupZ(2.6) - 0.32], [4.4, cupZ(4.4) - 0.28],
                [6.2, cupZ(6.2) - 0.22], [7.8, cupZ(7.8) - 0.15], [9.05, -0.62]];
            const I = DAISY_SHEET.invol;
            const rings = prof.map(([r, x]) => {
                const row = [];
                for (let j = 0; j <= RADS; j++) {
                    const th = (j / RADS) * TAU;
                    const k = (r / I.mm) * I.r;
                    row.push(V(P(r, x, th), I.cu + k * Math.cos(th), I.cv + k * Math.sin(th), aHead));
                }
                return row;
            });
            for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < RADS; j++) {
                const A = rings[i], B = rings[i + 1];
                idx.push(A[j], A[j + 1], B[j + 1], A[j], B[j + 1], B[j]);
            }
        }
        // disc dome (front normal = a): planar uv, u along s1 — 16 sides so
        // the rim silhouette stays round in close-ups
        {
            const RADS = 16;
            const D = DAISY_SHEET.disc;
            const prof = [0.35, 0.65, 0.86, 1.0].map((rho) => [rho * RD, domeZ(rho) + 0.55]);
            prof.push([RD * 1.06, 0.25], [RD * 1.0, -0.6]);
            const c0 = V(P(0, domeZ(0) + 0.55, 0), D.cu, D.cv, aHead);
            const rings = prof.map(([r, x]) => {
                const row = [];
                for (let j = 0; j <= RADS; j++) {
                    const th = (j / RADS) * TAU;
                    const k = (Math.min(r, D.mm) / D.mm) * D.r * 0.965;
                    row.push(V(P(r, x, th), D.cu + k * Math.cos(th), D.cv + k * Math.sin(th), aHead));
                }
                return row;
            });
            for (let j = 0; j < RADS; j++) tri3(c0, rings[0][j], rings[0][j + 1]);
            for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < RADS; j++) {
                const A = rings[i], B = rings[i + 1];
                idx.push(A[j], B[j], B[j + 1], A[j], B[j + 1], A[j + 1]);
            }
        }
        // ray florets: fitted cards, bases tucked under the disc rim, two
        // alternating layers; each petal hinges just outside the rim
        const petalStart = vb;
        {
            const N = bud ? 13 : irange(cfg.petals[0], cfg.petals[1]);
            const PT = DAISY_SHEET.petals;
            const ph0 = R() * TAU;
            const lenK = bud ? 0.42 : 1;
            for (let k = 0; k < N; k++) {
                const th = ph0 + (k / N) * TAU + rng.vary(0, 0.05);
                const rh = radial(th);
                const Kx = cross(rh, a);                          // hinge axis; also the card's +u side
                let cell = Math.floor(R() * 15); if (cell >= 7) cell++;   // 15 rays (cell 7 = impostor)
                const cx = cell % 8, cy = Math.floor(cell / 8);
                const bands = fit.petals[cell] ?? FIT_FALLBACK.petals[0];
                const pv = fit.petalV?.[cell] ?? [0.02, 0.98];
                // 16 mm rays on the 18 mm art: disc ~0.4 of the head, as measured
                const L = 16 * rng.range(0.86, 1.1) * lenK;       // mm
                const layer = k % 2 ? -0.13 : 0.13;
                const pitch = bud ? rng.range(1.25, 1.45) : rng.range(-0.1, 0.24) + (k % 2 ? -0.05 : 0.05);
                const droop = bud ? -0.1 : rng.range(-0.62, 0.02);
                const roll = rng.vary(0, 0.26);
                const bowK = bud ? 0 : rng.vary(0, 0.075);         // sideways sweep of the ray
                const sideW = norm(rotAxis(Kx, rh, roll));
                const hingeR = 9.4, hingeX = -0.5;
                // close record: hinge point + axis + angle (0 for buds: they stay shut)
                const closeA = bud ? 0 : 1.32 + (k % 2 ? 0.14 : -0.02) + rng.vary(0, 0.06);
                const Hp = P(hingeR, hingeX, th);
                const NBp = bands.length;
                const sA = vb;
                const clear = 3.2 / L;                            // arc fraction spent under the disc
                let px = 7.0, pxx = -0.6 + layer;                 // polar walk (r, x) in mm
                const u0c = (PT.x0 + PT.cw * cx) * PX, v0c = (PT.y0 + PT.ch * cy) * PX;
                const cellW = PT.cw * PX, cellH = PT.ch * PX;
                let prevT = 0;
                for (let g = 0; g < NBp; g++) {
                    const t = g / (NBp - 1);
                    // integrate the centreline: flat under the rim, then pitch + droop
                    const steps = 6;
                    for (let q = 0; q < steps && g > 0; q++) {
                        const tm = prevT + (t - prevT) * (q + 0.5) / steps;
                        const phi = tm < clear ? 0.02 : pitch + droop * ((tm - clear) / (1 - clear)) ** 1.6;
                        const ds = L * (t - prevT) / steps;
                        px += Math.cos(phi) * ds; pxx += Math.sin(phi) * ds;
                    }
                    prevT = t;
                    const ctr = P(px, pxx, th);
                    const [cF, hwF] = bands[g];
                    const hw = hwF * PT.cw * PT.mmPerPx * mm * s;
                    const off = (cF - 0.5) * PT.cw * PT.mmPerPx * mm * s;
                    const vv = v0c + (pv[0] + t * (pv[1] - pv[0])) * cellH;
                    const uC = u0c + cF * cellW, uHw = hwF * cellW;
                    const cc = add(ctr, mul(sideW, off + bowK * L * t * t * mm * s));
                    const tc = Math.min(1, Math.max(0, (Math.hypot(...sub(cc, Hp)) / (L * mm * s))));
                    curRec = [...C, 1, ...Hp, closeA * (1 + 0.3 * tc), ...Kx, lodC];
                    fold.set(V(sub(cc, mul(sideW, hw)), uC - uHw, vv, aHead), mul(sideW, 1));
                    fold.set(V(add(cc, mul(sideW, hw)), uC + uHw, vv, aHead), mul(sideW, -1));
                }
                for (let g = 0; g < NBp - 1; g++) {
                    const A = sA + g * 2;
                    idx.push(A, A + 1, A + 3, A, A + 3, A + 2);
                }
            }
        }
        const petalEnd = vb;
        // far card: one quad of the impostor tile (lod class 2). It grows in
        // as the detail collapses and turns to face the CAMERA in the vertex
        // stage — a field seen at a grazing angle is mostly sky-facing heads
        // edge-on, so an axis-facing card would vanish exactly where the rays
        // do. Its record carries (corner u, corner v, half size) in the hinge
        // slots (unused: its close angle is 0).
        if (!bud) {
            const IM = DAISY_SHEET.imp;
            // 0.75: a billboard shows every head full-face; real heads (mostly
            // sky-facing, seen at grazing angles) average about half their
            // disc — full size read as a denser band where the LOD switched
            const half = 23 * mm * s * 0.75;
            const cc = add(C, mul(a, 0.8 * mm * s));
            const q0 = vb;
            for (const [cu, cv] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
                curRec = [...C, 1, cu, cv, half, 0, 0, 0, 0, 2];
                V(add(cc, add(mul(s1, cu * half), mul(s2, cv * half))), IM.cu + cu * IM.h, IM.cv + cv * IM.h, aHead, a);
            }
            quad(q0, q0 + 1, q0 + 2, q0 + 3);                     // CCW seen from +a
        }
        curRec = null;
        return [petalStart, petalEnd];
    }

    // ── assemble, then the gen-owned normal treatment ───────────────────
    const g = new T3.BufferGeometry();
    g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2));
    g.setAttribute('aH', new T3.Float32BufferAttribute(aH, 1));
    g.setIndex(idx);
    g.computeVertexNormals();
    const nA = g.attributes.normal, pA = g.attributes.position;
    const recArr = new Float32Array(rec);
    // tubes keep their exact radial normals (smooth, seam-free)
    // leaf cards lean toward up (the turf law) so rosettes light like ground
    for (const lb of leafBlocks) {
        for (let i = lb.start; i < lb.end; i++) {
            const k = lb.upK;
            const nx = nA.getX(i) * (1 - k), ny = nA.getY(i) * (1 - k) + k, nz = nA.getZ(i) * (1 - k);
            const l = Math.hypot(nx, ny, nz) || 1;
            nA.setXYZ(i, nx / l, ny / l, nz / l);
        }
    }
    // head cards (ray florets): half geometric, half bent from a centre sunk
    // behind the disc — the whorl shades as one soft plate, the V-crease and
    // veins come from the normal map; disc dome + cup keep geometric normals
    for (const h of headInfo) {
        const back = sub(h.c, mul(h.a, h.d * 1.3));
        for (let i = h.petals[0]; i < h.petals[1]; i++) {
            const p = [pA.getX(i), pA.getY(i), pA.getZ(i)];
            const bent = norm(sub(p, back));
            let n = [nA.getX(i), nA.getY(i), nA.getZ(i)];
            if (dot(n, h.a) < 0) n = mul(n, -1);
            const kb = cfg.petalBend ?? 0.5;
            let m = norm(add(mul(n, 1 - kb), mul(bent, kb)));
            const fd = fold.get(i);
            if (fd) m = norm(add(m, mul(fd, 0.36)));         // trough: halves tilt ~20° inward
            nA.setXYZ(i, m[0], m[1], m[2]);
        }
    }
    // tubes: the analytic radial normals captured at emission (seam-free)
    for (const [a0, a1] of tubeRanges) {
        for (let i = a0; i < a1; i++) nA.setXYZ(i, nrm[i * 3], nrm[i * 3 + 1], nrm[i * 3 + 2]);
    }
    nA.needsUpdate = true;
    const tris = idx.length / 3;
    return {
        geo: g, closeData: recArr, heads: headInfo, lod: cfg.lod === false ? null : cfg.lod.map((d) => d * (cfg.headScale ?? 1)),
        stats: { verts: vb, tris, heads: headInfo.filter((h) => !h.bud).length, buds: headInfo.filter((h) => h.bud).length },
        ownNormals: true,
    };
}

// ── material hooks for createFlora ───────────────────────────────────────
// Plant-local deformation run BEFORE the instance transform: petals rotate
// about their hinges by close × angle (Rodrigues; the angle grows toward the
// tip so shut petals curl in over the disc), and head vertices undo the
// instance's non-uniform y-scale around their own centre (heads stay round
// while stems still vary in height). Normals rotate with the petals and ride
// a varying out of the vertex stage (vertexIndex is vertex-only).
export function daisyLocalNodes(build, { aSV, aPR, close = 0 }) {
    const { storage, vertexIndex, uniform, vec3, float, cos, sin, cross: tCross, dot: tDot, mix, positionLocal,
        normalLocal, cameraPosition, smoothstep, step, normalize } = T3;
    const attr = new T3.StorageBufferAttribute(build.closeData, 4);
    const buf = storage(attr, 'vec4', attr.count).toReadOnly();
    const uClose = uniform(close);
    const i3 = vertexIndex.mul(3);
    const d0 = buf.element(i3), d1 = buf.element(i3.add(1)), d2 = buf.element(i3.add(2));
    const Cn = d0.xyz, isHead = d0.w, Hn = d1.xyz, K = d2.xyz;
    const ang = d1.w.mul(uClose);
    const c = cos(ang), s = sin(ang);
    const rot = (v) => v.mul(c).add(tCross(K, v).mul(s)).add(K.mul(tDot(K, v).mul(float(1).sub(c))));
    const pr = rot(positionLocal.sub(Hn)).add(Hn);
    const ph = Cn.add(pr.sub(Cn).mul(vec3(1, aSV.x.div(aSV.y), 1)));
    // distance LOD, per plant: detail (class 1) collapses onto the head
    // centre as the impostor card (class 2) grows out of it — degenerate
    // triangles rasterize nothing, so far heads cost no ray fragments. The
    // far card also shrinks as the flowers close (a shut head is a small bud)
    const lod = build.lod ?? [1e6, 2e6];
    const uLodNear = uniform(lod[0]), uLodFar = uniform(lod[1]);
    const cls = d2.w;
    const fade = smoothstep(uLodNear, uLodFar, cameraPosition.sub(aPR.xyz).length());
    const nearOnly = step(0.5, cls).mul(step(cls, 1.5)), farOnly = step(1.5, cls);
    const kL = float(1).sub(nearOnly.mul(fade))
        .sub(farOnly.mul(float(1).sub(fade.mul(float(1).sub(uClose.mul(0.6))))));
    let position = Cn.add(mix(pr, ph, isHead).sub(Cn).mul(kL));
    // class 2: billboard the far card toward the camera, in plant-local
    // space (camera direction un-yawed by the instance's yaw; heads stay
    // round because the card is built around its own centre)
    const toCamW = cameraPosition.sub(aPR.xyz.add(vec3(0, Cn.y.mul(aSV.y), 0)));
    const cR = cos(aPR.w), sR = sin(aPR.w);
    const vL = normalize(vec3(toCamW.x.mul(cR).add(toCamW.z.mul(sR)), toCamW.y, toCamW.z.mul(cR).sub(toCamW.x.mul(sR))));
    const rightL = normalize(tCross(vec3(0, 1, 0), vL).add(vec3(1e-4, 0, 0)));
    const upL = tCross(vL, rightL);
    const bill = Cn.add(vL.mul(0.001)).add(rightL.mul(d1.x).add(upL.mul(d1.y)).mul(d1.z)
        .mul(fade.mul(float(1).sub(uClose.mul(0.6)))).mul(vec3(1, aSV.x.div(aSV.y), 1)));
    position = mix(position, bill, farOnly);
    const normal = mix(rot(normalLocal), vL, farOnly).toVarying('vDaisyNormal');
    return { position, normal, uClose, uLodNear, uLodFar, storageAttr: attr };
}

// petal palette recolor: luminance of the modelled white ray art times a
// base->tip tint, chosen per plant from the palette by the instance's colour
// variable (every head of a plant shares its colour, like a real plant)
const LUM_WHITE = 0.74;          // measured mean luminance of the white ray art (linear)
const PET = { u0: 428 * PX, v0: 605 * PX, rowH: 207 * PX };
const hexLin = (h) => {
    const c = new T3.Color().setHex(h, T3.SRGBColorSpace);
    return [c.r, c.g, c.b];
};
export function resolveDaisyPalette(color) {
    if (color == null) return null;
    const one = (c) => {
        if (Array.isArray(c)) {                                       // custom sRGB 0..1 (or 0..255)
            const k = c.some((x) => x > 1) ? 1 / 255 : 1;
            const col = new T3.Color().setRGB(c[0] * k, c[1] * k, c[2] * k, T3.SRGBColorSpace);
            return { base: [col.r * 0.85, col.g * 0.85, col.b * 0.85], tip: [col.r, col.g, col.b] };
        }
        if (!(c in DAISY_COLORS)) throw new Error(`[daisy] unknown color '${c}' — have: ${Object.keys(DAISY_COLORS).join(', ')} (or [r,g,b], or a { name: weight } mix)`);
        const e = DAISY_COLORS[c];
        return e ? { base: hexLin(e.base), tip: hexLin(e.tip) } : { white: true };
    };
    if (typeof color === 'string' || Array.isArray(color)) {
        const e = one(color);
        return e.white ? null : [{ w: 1, ...e }];
    }
    const entries = Object.entries(color).filter(([, w]) => w > 0);
    const tot = entries.reduce((s, [, w]) => s + w, 0) || 1;
    let acc = 0;
    return entries.map(([k, w]) => { acc += w / tot; return { cum: acc, ...one(k) }; });
}
export function daisyColorNode(albRGB, { aSV, palette }) {
    if (!palette || !palette.length) return albRGB;
    const { uv, step, fract, vec2, vec3, luminance, mix, float, smoothstep } = T3;
    const u = uv();
    const IM = DAISY_SHEET.imp;
    const inPetCells = step(PET.u0, u.x).mul(step(PET.v0, u.y));
    const dI = u.sub(vec2(IM.cu, IM.cv)).length();
    const inImp = step(IM.u0, u.x).mul(step(u.x, IM.u1)).mul(step(IM.v0, u.y)).mul(step(u.y, IM.v1));
    // inside the impostor tile (it sits in the ray block) only its ray ring
    // takes the tint — its gold disc stays gold, like the near heads'
    const inPet = mix(inPetCells, step(IM.discR * 1.08, dI), inImp);
    const t = mix(fract(u.y.sub(PET.v0).div(PET.rowH)), smoothstep(IM.discR, IM.h, dI), inImp);
    const tt = smoothstep(0.05, 0.75, t);
    const lum = luminance(albRGB).div(LUM_WHITE);
    const colOf = (e) => (e.white ? albRGB : mix(vec3(...e.base), vec3(...e.tip), tt).mul(lum));
    let pick = null;
    let col;
    if (palette.length === 1 && palette[0].cum == null) {
        col = colOf(palette[0]);
    } else {
        pick = fract(aSV.w.mul(7.919).add(0.137));
        col = colOf(palette[0]);
        for (let k = 1; k < palette.length; k++) {
            col = mix(col, colOf(palette[k]), step(float(palette[k - 1].cum), pick));
        }
    }
    return mix(albRGB, col, inPet);
}
