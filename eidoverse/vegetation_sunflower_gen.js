// sunflower_gen — the sunflower (Helianthus annuus) for createFlora: one
// continuous parallel-transported cane (base → neck arc → head), spiral
// petioled heart-leaves, and a nodding head — thin-plate seed disc, dense
// fitted ray-petal whorl, a 3D bract cup of wedge cards behind. One geometry
// on the ONE sunflower_ trim sheet, field-instanced like corn.
//
// Craft laws baked in (memory + Skye's corrections):
//   - MATERIALS FIRST: petal + leaf cards are planes whose loop widths AND
//     per-band UV windows follow sunflower_fit.json — the measured alpha
//     envelope of the art. Geometry AND texture narrow together; mapping a
//     full art window onto a fitted card is how UVs warp.
//   - STRUCTURE IS TUBES, and a tube run that continues (stalk → neck) is
//     ONE swept tube with a parallel-transported frame and monotonic
//     fibre-v — two independently framed tubes meet in a cracked seam.
//   - FOLIAGE NORMALS (the 07-31 law): the head shades as one soft volume —
//     spherical bent normals from the head centre for every head part (the
//     shrub-canopy treatment); leaf blades blend strongly toward up (turf
//     treatment); tubes keep their geometric normals. The gen OWNS its
//     normals — no generic post blend.
//   - The head is ONE rigid assembly in wind: every head vertex carries the
//     identical aH (the corn-ear law).
//
// sunflower_ sheet regions (UV, v up, 1024²) — layout v2:
//   DISC   circle centre (.2405,.780) r .2053 (planar projection)
//   PETALS u .5–1, v .586–1 — 4 cols × 2 rows = 8 fitted variants
//   BRACT  circle centre (.826,.3793) r .1701 (radial rosette art)
//   LEAF   u .004–.6305, v .2102–.5396 — heart leaf, base left, midrib v .3743
//   STALK  v .005–.195 — cane, fibre along v

const T3 = globalThis.THREE;
import { Rng } from './vegetation_shrub_gen.js';

const TAU = Math.PI * 2;
const tri = (s) => { const m = s % 2; return m <= 1 ? m : 2 - m; };

// thin plate: gentle front bulge, shallow back cup into the neck. The plate
// stays a touch SMALLER than the petal attachment ring — a disc edge wider
// than the whorl overhangs the petals and reads as poking through them
const DISC_R = 0.30;
const DISC_K = 0.97;
const DISC_FRONT = [0, 0.09, 0.16, 0.22, 0.265, 0.29, 0.300]
    .map((r) => [r * DISC_K, 0.012 + 0.052 * Math.pow(1 - Math.pow(r / 0.302, 2.2), 0.8)]);
const DISC_RIM_BACK = [
    [0.302 * DISC_K, 0.002],
    [0.290 * DISC_K, -0.014],
    [0.170 * DISC_K, -0.036],
    [0.000, -0.046],
];

// stand-in envelopes if sunflower_fit.json is missing
const FIT_FALLBACK = {
    petals: Array(8).fill([[0.5, 0.20], [0.5, 0.31], [0.5, 0.34], [0.5, 0.34], [0.5, 0.32], [0.5, 0.19]]),
    leaf: [[0.5, 0.47], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.39], [0.5, 0.22]],
    bractR: 1.0,
};

export const SUNFLOWER_GEN = {
    sunflower: {
        height: 1.9,
        leaves: 11,
        leafLen: 0.62,
        headR: 0.20,
        petals: 34,
    },
};

export function buildSunflowerGeometry(name, seed, over = {}) {
    const cfg = { ...(SUNFLOWER_GEN[name] ?? SUNFLOWER_GEN.sunflower), ...over };
    const fit = cfg.fit ?? FIT_FALLBACK;
    const rng = new Rng(seed);
    const R = () => rng.next();

    const pos = [], uv = [], aH = [], idx = [];
    let vb = 0;
    const V = (x, y, z, u, vv, a) => { pos.push(x, y, z); uv.push(u, vv); aH.push(a); return vb++; };
    const quad = (a, b, c, d) => idx.push(a, b, c, a, c, d);
    const B = (p0, p1, p2, t) => {
        const s = 1 - t;
        return [s * s * p0[0] + 2 * s * t * p1[0] + t * t * p2[0],
                s * s * p0[1] + 2 * s * t * p1[1] + t * t * p2[1],
                s * s * p0[2] + 2 * s * t * p1[2] + t * t * p2[2]];
    };

    // swept tube over a sampled centreline with a PARALLEL-TRANSPORTED frame
    // (no per-ring world-up guessing — that twists at steep tangents) and
    // fibre-v continuous along the run (mirrored triangle tiling)
    function sweepTube(pts, radii, weights, RADS, vStart = 0.012) {
        const n = pts.length;
        // tangents
        const tans = [];
        for (let i = 0; i < n; i++) {
            const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
            let t = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
            const l = Math.hypot(...t) || 1;
            tans.push([t[0] / l, t[1] / l, t[2] / l]);
        }
        // initial side frame ⟂ tangent
        let t0 = tans[0];
        let s1 = Math.abs(t0[1]) < 0.95 ? [t0[2], 0, -t0[0]] : [1, 0, 0];
        {
            const d = s1[0] * t0[0] + s1[1] * t0[1] + s1[2] * t0[2];
            s1 = [s1[0] - t0[0] * d, s1[1] - t0[1] * d, s1[2] - t0[2] * d];
            const l = Math.hypot(...s1) || 1; s1 = [s1[0] / l, s1[1] / l, s1[2] / l];
        }
        const rows = [];
        let arc = 0;
        for (let i = 0; i < n; i++) {
            if (i > 0) {
                arc += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]);
                // transport s1: strip the new tangent's component
                const t = tans[i];
                const d = s1[0] * t[0] + s1[1] * t[1] + s1[2] * t[2];
                s1 = [s1[0] - t[0] * d, s1[1] - t[1] * d, s1[2] - t[2] * d];
                const l = Math.hypot(...s1) || 1; s1 = [s1[0] / l, s1[1] / l, s1[2] / l];
            }
            const t = tans[i];
            const s2 = [t[1] * s1[2] - t[2] * s1[1], t[2] * s1[0] - t[0] * s1[2], t[0] * s1[1] - t[1] * s1[0]];
            const r = radii[i], row = [];
            const vband = vStart + 0.176 * tri(vStart / 0.18 + arc * 1.15);
            for (let j = 0; j <= RADS; j++) {
                const an = (j / RADS) * TAU;
                const ox = s1[0] * Math.cos(an) + s2[0] * Math.sin(an),
                      oy = s1[1] * Math.cos(an) + s2[1] * Math.sin(an),
                      oz = s1[2] * Math.cos(an) + s2[2] * Math.sin(an);
                row.push(V(pts[i][0] + ox * r, pts[i][1] + oy * r, pts[i][2] + oz * r,
                    0.03 + 0.94 * tri((j / RADS) * 2), vband, weights[i]));
            }
            rows.push(row);
        }
        for (let i = 0; i < rows.length - 1; i++) for (let j = 0; j < RADS; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
    }

    // ── head placement first (the cane sweeps INTO it) ──────────────────────
    const H = cfg.height * (cfg.heightJitter ?? rng.range(0.9, 1.1));
    const leanA = R() * TAU, leanAmt = (cfg.stalkLean ?? rng.range(0.02, 0.08)) * H;
    const lx = Math.cos(leanA) * leanAmt, lz = Math.sin(leanA) * leanAmt;
    const P = (t) => [lx * t * t, t * H, lz * t * t];
    const stalkR = (t) => 0.019 * (1 - t) + 0.008 * t;
    const aHead = 0.82;
    const s = (cfg.headR ?? 0.20) / 0.50;
    const pitch = cfg.pitch ?? rng.range(0.6, 1.05);
    const headYaw = cfg.headYaw ?? (leanA + rng.vary(0, 0.6));
    const ax = Math.cos(headYaw) * Math.sin(pitch), ay = Math.cos(pitch), az = Math.sin(headYaw) * Math.sin(pitch);
    let s1x = -az, s1y = 0, s1z = ax;
    { const l = Math.hypot(s1x, s1y, s1z) || 1; s1x /= l; s1z /= l; }
    const s2x = ay * s1z - az * s1y, s2y = az * s1x - ax * s1z, s2z = ax * s1y - ay * s1x;
    const neckL = 0.10 * s;
    const [tx, ty, tz] = P(1);
    const hx = tx + ax * neckL * 0.85, hy = ty + ay * neckL * 0.85 + neckL * 0.25, hz = tz + az * neckL * 0.85;
    const radial = (th) => [s1x * Math.cos(th) + s2x * Math.sin(th),
                            s1y * Math.cos(th) + s2y * Math.sin(th),
                            s1z * Math.cos(th) + s2z * Math.sin(th)];

    // ── the cane: ONE sweep, base → stalk → neck arc → buried in the head ──
    {
        const pts = [], radii = [], weights = [];
        for (const t of [0, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 1]) {
            const p = P(t);
            pts.push([p[0], t === 0 ? -0.04 : p[1], p[2]]);
            radii.push(stalkR(t));
            weights.push(t * 0.8);
        }
        // neck arc into the head's back cup
        const n0 = [tx, ty, tz];
        const n1 = [tx, ty + neckL * 0.55, tz];
        const n2 = [hx - ax * 0.040 * s, hy - ay * 0.040 * s, hz - az * 0.040 * s];
        for (const t of [0.35, 0.7, 1]) {
            pts.push(B(n0, n1, n2, t));
            radii.push(stalkR(1) * (1 - t * 0.2));
            weights.push(0.8 + t * (aHead - 0.8));
        }
        sweepTube(pts, radii, weights, 6);
    }

    // ── leaves: petiole tubes + fitted drooping heart blades ────────────────
    const LEAF = { u0: 0.004, u1: 0.6305, v0: 0.2102, vm: 0.3743, v1: 0.5396 };
    const LEAF_ACROSS = (LEAF.v1 - LEAF.v0) / (LEAF.u1 - LEAF.u0);
    const nL = Math.round(cfg.leaves * rng.range(0.9, 1.15));
    const rank = cfg.rank ?? R() * TAU;
    const leafBladeStart = [];
    for (let i = 0; i < nL; i++) {
        const f = 0.14 + 0.63 * ((i + R() * 0.4) / nL);
        const yaw = rank + i * 2.3998 + rng.vary(0, 0.3);
        const size = (0.6 + 0.45 * Math.sin(Math.PI * Math.min(1, 0.2 + f * 0.9)))
            * (1 - Math.max(0, f - 0.6) * 0.9) * rng.range(0.85, 1.15);
        const petL = cfg.leafLen * 0.34 * size;
        const bladeL = cfg.leafLen * 0.66 * size;
        const [sx, sy, sz] = P(f);
        const dirX = Math.cos(yaw), dirZ = Math.sin(yaw);
        const sideX = -Math.sin(yaw), sideZ = Math.cos(yaw);
        const aL = f * 0.8;
        const r0 = stalkR(f);
        // petiole: swept tube, base buried in the cane, arcing out and up
        const q0 = [sx + dirX * r0 * 0.2, sy, sz + dirZ * r0 * 0.2];
        const q1 = [q0[0] + dirX * petL * 0.55, q0[1] + petL * 0.38, q0[2] + dirZ * petL * 0.55];
        const q2 = [q0[0] + dirX * petL * 1.02, q0[1] + petL * rng.range(0.32, 0.5), q0[2] + dirZ * petL * 1.02];
        {
            const pts = [], radii = [], weights = [];
            for (const t of [0, 0.34, 0.67, 1]) {
                pts.push(B(q0, q1, q2, t));
                radii.push((0.0062 - 0.0024 * t) * size);
                weights.push(aL + t * 0.05);
            }
            sweepTube(pts, radii, weights, 4, 0.03);
        }
        // blade: 5-column strip continuing the petiole — geometry width AND
        // uv v-window both follow the measured envelope band (unwarped fit),
        // cross-section is a real leaf surface: parabolic cup off the
        // midrib, a travelling edge RUFFLE (real blades undulate — a single
        // hard V-fold reads as folded paper), and a decurving tip
        const petT = [q2[0] - q1[0], q2[1] - q1[1], q2[2] - q1[2]];
        const ptl = Math.hypot(...petT) || 1;
        const b0 = q2;
        const b1 = [b0[0] + (petT[0] / ptl) * bladeL * 0.42, b0[1] + (petT[1] / ptl) * bladeL * 0.42, b0[2] + (petT[2] / ptl) * bladeL * 0.42];
        const b2 = [b0[0] + dirX * bladeL * 0.82, b0[1] - bladeL * rng.range(0.3, 0.55), b0[2] + dirZ * bladeL * 0.82];
        const bands = fit.leaf;
        const NB = bands.length;
        const rufPhase = R() * TAU, rufFreq = rng.range(5.5, 7.5);
        const COLS = [-1, -0.5, 0, 0.5, 1];
        const sB = vb;
        leafBladeStart.push(sB);
        for (let g = 0; g < NB; g++) {
            const t = g / (NB - 1);
            const c = B(b0, b1, b2, t);
            const [cFrac, hwFrac] = bands[g];
            const hw = hwFrac * LEAF_ACROSS * bladeL / 0.5;
            const a = Math.min(1, aL + t * t * 0.16);
            const u = LEAF.u0 + t * (LEAF.u1 - LEAF.u0);
            const vC = LEAF.v0 + cFrac * (LEAF.v1 - LEAF.v0);
            const vHw = hwFrac * (LEAF.v1 - LEAF.v0);
            const sink = g === 0 ? -0.006 : 0;
            const tipDrop = Math.max(0, t - 0.72) * bladeL * 0.35;   // decurving tip
            for (const k of COLS) {
                const cup = hw * 0.34 * k * k;                        // parabolic cup
                const ruffle = hw * 0.09 * Math.abs(k) * Math.sin(rufPhase + t * rufFreq + k * 2.4);
                V(c[0] + sideX * hw * k + dirX * sink,
                  c[1] - cup + ruffle - tipDrop,
                  c[2] + sideZ * hw * k + dirZ * sink,
                  u, vC + vHw * k, a);
            }
        }
        for (let g = 0; g < NB - 1; g++) {
            const a2 = sB + g * 5, b3 = a2 + 5;
            for (let cq = 0; cq < 4; cq++) quad(a2 + cq, a2 + cq + 1, b3 + cq + 1, b3 + cq);
        }
    }
    const headStart = vb;   // every vertex from here on is head assembly
    let petalStart = vb;    // set after the disc lathe — bent normals apply
                            // to the CARD parts only (petals + bract cup);
                            // the disc plate keeps geometric normals and its
                            // normal MAP carries the seed relief

    // ── disc plate ──────────────────────────────────────────────────────────
    const discUV = (rr, th) => [0.2405 + 0.2053 * (rr / DISC_R) * Math.cos(th),
                                0.780 + 0.2053 * (rr / DISC_R) * Math.sin(th)];
    const backUV = (rr, th) => [0.826 + 0.16 * (rr / DISC_R) * Math.cos(th),
                                0.3793 + 0.16 * (rr / DISC_R) * Math.sin(th)];
    {
        const RADD = 12;
        const front = DISC_FRONT.map((p) => [...p, discUV]);
        const back = DISC_RIM_BACK.map((p, i) => [...p, i === 0 ? discUV : backUV]);
        const prof = [...front, ...back];
        const rings = [];
        for (let k = 0; k < prof.length; k++) {
            const [r, x, uvFn] = prof[k];
            if (r < 1e-6) {
                const [uu2, vv2] = uvFn(0, 0);
                rings.push([V(hx + ax * x * s, hy + ay * x * s, hz + az * x * s, uu2, vv2, aHead)]);
                continue;
            }
            const row = [];
            for (let j = 0; j < RADD; j++) {
                const th = (j / RADD) * TAU;
                const [ox, oy, oz] = radial(th);
                const [uu2, vv2] = uvFn(r, th);
                row.push(V(hx + ax * x * s + ox * r * s, hy + ay * x * s + oy * r * s,
                    hz + az * x * s + oz * r * s, uu2, vv2, aHead));
            }
            rings.push(row);
        }
        for (let i = 0; i < rings.length - 1; i++) {
            const A = rings[i], Bb = rings[i + 1];
            if (A.length === 1) {
                for (let j = 0; j < RADD; j++) idx.push(A[0], Bb[(j + 1) % RADD], Bb[j]);
            } else if (Bb.length === 1) {
                for (let j = 0; j < RADD; j++) idx.push(A[j], A[(j + 1) % RADD], Bb[0]);
            } else {
                for (let j = 0; j < RADD; j++)
                    quad(A[j], A[(j + 1) % RADD], Bb[(j + 1) % RADD], Bb[j]);
            }
        }
    }
    petalStart = vb;
    // ── ray petals: dense whorl, per-band envelope in geometry AND uv ───────
    {
        const N = cfg.petals ?? 34;
        const cells = [];
        for (let cx2 = 0; cx2 < 4; cx2++) for (let ry = 0; ry < 2; ry++)
            cells.push({ u0: 0.5 + 0.125 * cx2 + 0.006, u1: 0.5 + 0.125 * (cx2 + 1) - 0.006,
                         v0: ry === 0 ? 0.7937 : 0.5879, v1: ry === 0 ? 0.9995 : 0.7927,
                         fit: fit.petals[cx2 * 2 + ry] });
        const rimR = 0.285;
        const needHW = (TAU * rimR / N) * 0.5 * 1.25;
        // LAYERED whorls — real heads stack ray florets, so background never
        // shows between petal bases and the disc: a main outer whorl plus a
        // shorter inner layer, phase-offset half a spacing, tucked deeper
        // under the rim and tilted slightly forward (young florets angle up)
        const layers = [
            { n: N, rIn: 0.020, lenK: 1.0, phase: 0, droopLo: -0.22, droopHi: 0.10 },
            { n: Math.round(N * 0.7), rIn: 0.042, lenK: 0.55, phase: Math.PI / N,
              droopLo: -0.02, droopHi: 0.30 },
        ];
        for (const LY of layers) for (let k = 0; k < LY.n; k++) {
            const th = (k / LY.n) * TAU + LY.phase + rng.vary(0, 0.04);
            const cell = cells[Math.floor(R() * cells.length)];
            const maxEnv = Math.max(...cell.fit.map((b) => b[1]));
            const cardHW = needHW / maxEnv;
            const L = cardHW * 2 * (0.207 / 0.125) * LY.lenK * rng.range(0.94, 1.06);
            const [ox, oy, oz] = radial(th);
            const txp = s2x * Math.cos(th) - s1x * Math.sin(th),
                  typ = s2y * Math.cos(th) - s1y * Math.sin(th),
                  tzp = s2z * Math.cos(th) - s1z * Math.sin(th);
            const droop = rng.range(LY.droopLo, LY.droopHi) - (LY.lenK === 1 && k % 5 === 0 ? 0.18 : 0);
            const roll = rng.vary(0, 0.35);
            const wx = txp * Math.cos(roll) + ax * Math.sin(roll),
                  wy = typ * Math.cos(roll) + ay * Math.sin(roll),
                  wz = tzp * Math.cos(roll) + az * Math.sin(roll);
            // base sits just behind the disc's FRONT edge plane — petals
            // leave the rim IN the disc plane (covering the band edge) and
            // only then take their droop (progressive per band, below)
            const bxp = hx + ox * (rimR - LY.rIn) * s + ax * 0.008 * s,
                  byp = hy + oy * (rimR - LY.rIn) * s + ay * 0.008 * s,
                  bzp = hz + oz * (rimR - LY.rIn) * s + az * 0.008 * s;
            const bands = cell.fit;
            const NBp = bands.length;
            const uMid = (cell.u0 + cell.u1) / 2, uSpan = (cell.u1 - cell.u0);
            const sA = vb;
            for (let g = 0; g < NBp; g++) {
                const t = g / (NBp - 1);
                const [cFrac, hwFrac] = bands[g];
                const hw = hwFrac * cardHW * 2;
                // droop fades in over the first third — the base band exits
                // flat across the rim, the tip carries the full angle
                const dk = droop * Math.min(1, t / 0.35);
                const cd = Math.cos(dk), sd = Math.sin(dk);
                const dx = ox * cd + ax * sd, dy = oy * cd + ay * sd, dz = oz * cd + az * sd;
                const cup = Math.sin(t * Math.PI) * L * 0.05;
                const cx3 = bxp + dx * L * t * s + ax * cup * s,
                      cy3 = byp + dy * L * t * s + ay * cup * s,
                      cz3 = bzp + dz * L * t * s + az * cup * s;
                const vv2 = cell.v0 + (cell.v1 - cell.v0) * t;
                // uv follows the band: centre offset + half width in CELL space
                const uC = cell.u0 + cFrac * uSpan;
                const uHw = hwFrac * uSpan;
                V(cx3 - wx * hw * s, cy3 - wy * hw * s, cz3 - wz * hw * s, uC - uHw, vv2, aHead);
                V(cx3 + wx * hw * s, cy3 + wy * hw * s, cz3 + wz * hw * s, uC + uHw, vv2, aHead);
            }
            for (let g = 0; g < NBp - 1; g++) {
                const a2 = sA + g * 2;
                quad(a2, a2 + 1, a2 + 3, a2 + 2);
            }
        }
    }
    // ── bract cup: tilted wedge cards sampling radial slices of the rosette ─
    {
        const BR = { cu: 0.826, cv: 0.3793, r: 0.1701 };
        const bR = Math.min(fit.bractR ?? 1.0, 1.05);
        const uvR = BR.r * bR * 0.97;
        const NB2 = 10;
        for (let k = 0; k < NB2; k++) {
            const phi = (k / NB2) * TAU + rng.vary(0, 0.12);
            const deep = k % 2 === 0;
            const [ox, oy, oz] = radial(phi);
            const txp = s2x * Math.cos(phi) - s1x * Math.sin(phi),
                  typ = s2y * Math.cos(phi) - s1y * Math.sin(phi),
                  tzp = s2z * Math.cos(phi) - s1z * Math.sin(phi);
            const xBase = (deep ? -0.040 : -0.030) * s, rBase = 0.06 * s;
            const xTip = (deep ? -0.012 : -0.004) * s;
            const rTip = (0.315 + rng.vary(0.02, 0.015)) * s * (deep ? 0.94 : 1);
            const halfWedge = (TAU / NB2) * 0.5 * 1.3;
            const sA = vb;
            for (let g = 0; g <= 2; g++) {
                const t = g / 2;
                const rr = rBase + (rTip - rBase) * t;
                const xx2 = xBase + (xTip - xBase) * (t * t * 0.4 + t * 0.6);
                const hwW = rr * Math.sin(halfWedge);
                const cup = hwW * 0.3 * (1 - t * 0.5);
                const uvr = (0.2 + 0.8 * t) * uvR;
                const uvHw = uvr * Math.tan(halfWedge) * 0.92;
                const cx3 = hx + ax * xx2 + ox * rr, cy3 = hy + ay * xx2 + oy * rr, cz3 = hz + az * xx2 + oz * rr;
                const cU = BR.cu + uvr * Math.cos(phi), cV = BR.cv + uvr * Math.sin(phi);
                const pU = -Math.sin(phi) * uvHw, pV = Math.cos(phi) * uvHw;
                V(cx3 - txp * hwW - ax * cup, cy3 - typ * hwW - ay * cup, cz3 - tzp * hwW - az * cup,
                    cU - pU, cV - pV, aHead);
                V(cx3, cy3, cz3, cU, cV, aHead);
                V(cx3 + txp * hwW - ax * cup, cy3 + typ * hwW - ay * cup, cz3 + tzp * hwW - az * cup,
                    cU + pU, cV + pV, aHead);
            }
            for (let g = 0; g < 2; g++) {
                const a2 = sA + g * 3, b3 = a2 + 3;
                quad(a2, a2 + 1, b3 + 1, b3); quad(a2 + 1, a2 + 2, b3 + 2, b3 + 1);
            }
        }
    }

    console.log(`[sunflower] head centre local (${hx.toFixed(3)}, ${hy.toFixed(3)}, ${hz.toFixed(3)}) axis (${ax.toFixed(2)}, ${ay.toFixed(2)}, ${az.toFixed(2)})`);
    const g = new T3.BufferGeometry();
    g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2));
    g.setAttribute('aH', new T3.Float32BufferAttribute(aH, 1));
    g.setIndex(idx);
    g.computeVertexNormals();
    // ── normal treatment (the gen owns it — createFlora must NOT re-blend):
    // head parts = spherical bent normals from a centre sunk behind the disc
    // (one soft lit volume, the shrub-canopy law); leaf blades blend toward
    // up (the turf law); tubes keep geometric normals.
    {
        const nrm = g.attributes.normal;
        const px2 = g.attributes.position;
        const ncx = hx - ax * 0.05 * s, ncy = hy - ay * 0.05 * s, ncz = hz - az * 0.05 * s;
        for (let i = petalStart; i < vb; i++) {
            let dx2 = px2.getX(i) - ncx, dy2 = px2.getY(i) - ncy, dz2 = px2.getZ(i) - ncz;
            const l = Math.hypot(dx2, dy2, dz2) || 1;
            nrm.setXYZ(i, dx2 / l, dy2 / l, dz2 / l);
        }
        const UPK = 0.65;
        for (const sB of leafBladeStart) {
            for (let i = sB; i < sB + 30 && i < headStart; i++) {
                const nx2 = nrm.getX(i) * (1 - UPK), ny2 = nrm.getY(i) * (1 - UPK) + UPK, nz2 = nrm.getZ(i) * (1 - UPK);
                const l = Math.hypot(nx2, ny2, nz2) || 1;
                nrm.setXYZ(i, nx2 / l, ny2 / l, nz2 / l);
            }
        }
        nrm.needsUpdate = true;
    }
    return { geo: g, stats: { verts: vb, tris: idx.length / 3 }, ownNormals: true };
}
