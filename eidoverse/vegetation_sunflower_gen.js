// sunflower_gen — the sunflower (Helianthus annuus) for createFlora: cane
// stalk, spiral petioled heart-leaves, and a nodding head — thin-plate seed
// disc, a dense fitted ray-petal whorl, bract star behind. One geometry on
// the ONE sunflower_ trim sheet, field-instanced like corn.
//
// Reference laws baked in (work/sunflower/ref/, Skye's corrections):
//   - MATERIALS FIRST: petal + leaf cards are simple planes whose loop
//     widths follow sunflower_fit.json — the measured alpha envelope of
//     Sol's art (overdraw pull-in). Geometry invents no silhouettes.
//   - STRUCTURE IS TUBES: petioles and the neck are real tubes; flat
//     ribbons vanish edge-on and read as broken hovering pieces.
//   - The head is a THIN PLATE (rim depth ~13% of diameter), petals emerge
//     tucked under the rim in one dense whorl, coverage of the circumference
//     guaranteed by construction; the leaf canopy is most of the plant.
//   - The whole head is ONE RIGID ASSEMBLY in wind: every head vertex
//     carries the identical aH (the corn-ear law).
//
// sunflower_ sheet regions (UV, v up, 1024²) — layout v2, dead space spent:
//   DISC   circle centre (.2405,.780) r .2053 (planar projection)
//   PETALS u .5–1, v .586–1 — 4 cols × 2 rows = 8 fitted variants
//   BRACT  circle centre (.826,.3793) r .1701 (art may reach ×1.05)
//   LEAF   u .004–.6305, v .2102–.5396 — heart leaf, base left, midrib v .3743
//   STALK  v .005–.195 — cane, fibre along v

const T3 = globalThis.THREE;
import { Rng } from './vegetation_shrub_gen.js';

const TAU = Math.PI * 2;
const tri = (s) => { const m = s % 2; return m <= 1 ? m : 2 - m; };

// thin plate: gentle front bulge, near-flat back, knife rim
const DISC_R = 0.30;
const DISC_FRONT = [0, 0.09, 0.16, 0.22, 0.265, 0.29, 0.300]
    .map((r) => [r, 0.012 + 0.052 * Math.pow(1 - Math.pow(r / 0.302, 2.2), 0.8)]);
const DISC_RIM_BACK = [
    [0.302, 0.002],
    [0.290, -0.012],
    [0.170, -0.024],
    [0.000, -0.030],
];

// stand-in envelopes if sunflower_fit.json is missing (regenerate with
// work/sunflower/measure_fit.py whenever new art lands)
const FIT_FALLBACK = {
    petals: Array(8).fill([[0.5, 0.20], [0.5, 0.31], [0.5, 0.34], [0.5, 0.34], [0.5, 0.32], [0.5, 0.19]]),
    leaf: [[0.5, 0.47], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.39], [0.5, 0.22]],
    bractR: 1.05,
};

export const SUNFLOWER_GEN = {
    sunflower: {
        height: 1.9,
        leaves: 11,
        leafLen: 0.62,       // petiole + blade (m) at full size
        headR: 0.20,         // head radius petal-tip to axis (m)
        petals: 26,
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
    // tube along a bezier: RADS-gon rings, stalk-band art (fibre along v)
    function tube(p0, p1, p2, r0, r1, rings, RADS, a0, a1, vOff = 0.02) {
        const rows = [];
        for (let g = 0; g <= rings; g++) {
            const t = g / rings;
            const c = B(p0, p1, p2, t);
            const d = B(p0, p1, p2, Math.min(1, t + 0.01));
            let tx = d[0] - c[0], ty = d[1] - c[1], tz = d[2] - c[2];
            const tl = Math.hypot(tx, ty, tz) || 1; tx /= tl; ty /= tl; tz /= tl;
            let s1x = -tz, s1y = 0, s1z = tx;
            const sl = Math.hypot(s1x, s1y, s1z) || 1e-6; s1x /= sl; s1z /= sl;
            const s2x = ty * s1z - tz * s1y, s2y = tz * s1x - tx * s1z, s2z = tx * s1y - ty * s1x;
            const r = r0 + (r1 - r0) * t;
            const row = [];
            const vband = vOff + 0.15 * tri(0.3 + t * 0.9);
            for (let j = 0; j <= RADS; j++) {
                const an = (j / RADS) * TAU;
                const ox = s1x * Math.cos(an) + s2x * Math.sin(an),
                      oy = s1y * Math.cos(an) + s2y * Math.sin(an),
                      oz = s1z * Math.cos(an) + s2z * Math.sin(an);
                row.push(V(c[0] + ox * r, c[1] + oy * r, c[2] + oz * r,
                    0.03 + 0.94 * tri((j / RADS) * 2), vband, a0 + (a1 - a0) * t));
            }
            rows.push(row);
        }
        for (let i = 0; i < rows.length - 1; i++) for (let j = 0; j < RADS; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
        return rows;
    }

    // ── stalk ───────────────────────────────────────────────────────────────
    const H = cfg.height * (cfg.heightJitter ?? rng.range(0.9, 1.1));
    const leanA = R() * TAU, leanAmt = (cfg.stalkLean ?? rng.range(0.02, 0.08)) * H;
    const lx = Math.cos(leanA) * leanAmt, lz = Math.sin(leanA) * leanAmt;
    const P = (t) => [lx * t * t, t * H, lz * t * t];
    const stalkR = (t) => 0.019 * (1 - t) + 0.008 * t;
    {
        const STA = [0, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 1], RADS = 6;
        const rows = [];
        for (const t of STA) {
            const [cx, cy, cz] = P(t);
            const r = stalkR(t), row = [];
            const vband = 0.012 + 0.176 * tri(t * 2.4);
            for (let j = 0; j <= RADS; j++) {
                const a = (j / RADS) * TAU;
                const u = 0.03 + 0.94 * tri((j / RADS) * 2);
                row.push(V(cx + Math.cos(a) * r, t === 0 ? -0.04 : cy, cz + Math.sin(a) * r,
                    u, vband, t * 0.8));
            }
            rows.push(row);
        }
        for (let i = 0; i < rows.length - 1; i++) for (let j = 0; j < RADS; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
    }

    // ── leaves: tube petiole + fitted drooping heart blade ──────────────────
    const LEAF = { u0: 0.004, u1: 0.6305, v0: 0.2102, vm: 0.3743, v1: 0.5396 };
    // art aspect: window u-span long × v-span across
    const LEAF_ACROSS = (LEAF.v1 - LEAF.v0) / (LEAF.u1 - LEAF.u0);
    const nL = Math.round(cfg.leaves * rng.range(0.9, 1.15));
    const rank = cfg.rank ?? R() * TAU;
    for (let i = 0; i < nL; i++) {
        // canopy stops short of the head — a top leaf at the head's height
        // slices across the petals as a bar in head-on views
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
        // petiole TUBE, base buried in the cane (junction law), arcing out
        // and slightly up before the blade takes over and droops
        const q0 = [sx + dirX * r0 * 0.2, sy, sz + dirZ * r0 * 0.2];
        const q1 = [q0[0] + dirX * petL * 0.55, q0[1] + petL * 0.38, q0[2] + dirZ * petL * 0.55];
        const q2 = [q0[0] + dirX * petL * 1.02, q0[1] + petL * rng.range(0.32, 0.5), q0[2] + dirZ * petL * 1.02];
        tube(q0, q1, q2, 0.0062 * size, 0.0038 * size, 3, 4, aL, aL + 0.05);
        // blade: plane strip continuing the petiole tangent, drooping to a
        // hanging tip; widths from the measured art envelope
        const petT = [q2[0] - q1[0], q2[1] - q1[1], q2[2] - q1[2]];
        const ptl = Math.hypot(...petT) || 1;
        const b0 = q2;
        const b1 = [b0[0] + (petT[0] / ptl) * bladeL * 0.42, b0[1] + (petT[1] / ptl) * bladeL * 0.42, b0[2] + (petT[2] / ptl) * bladeL * 0.42];
        const b2 = [b0[0] + dirX * bladeL * 0.82, b0[1] - bladeL * rng.range(0.3, 0.55), b0[2] + dirZ * bladeL * 0.82];
        const bands = fit.leaf;
        const NB = bands.length;
        const sB = vb;
        for (let g = 0; g < NB; g++) {
            const t = g / (NB - 1);
            const c = B(b0, b1, b2, t);
            const hw = bands[g][1] * LEAF_ACROSS * bladeL / 0.5;   // env frac -> metres
            const fold = hw * 0.34;                                 // V-fold, edges below midrib
            const a = Math.min(1, aL + t * t * 0.16);
            const u = LEAF.u0 + t * (LEAF.u1 - LEAF.u0);
            // sink the first band into the petiole tip so the junction is
            // covered from every angle
            const sink = g === 0 ? -0.006 : 0;
            V(c[0] - sideX * hw + dirX * sink, c[1] - fold, c[2] - sideZ * hw + dirZ * sink, u, LEAF.v0, a);
            V(c[0] + dirX * sink, c[1], c[2] + dirZ * sink, u, LEAF.vm, a);
            V(c[0] + sideX * hw + dirX * sink, c[1] - fold, c[2] + sideZ * hw + dirZ * sink, u, LEAF.v1, a);
        }
        for (let g = 0; g < NB - 1; g++) {
            const a2 = sB + g * 3, b3 = a2 + 3;
            quad(a2, a2 + 1, b3 + 1, b3); quad(a2 + 1, a2 + 2, b3 + 2, b3 + 1);
        }
    }

    // ── the head: ONE rigid assembly ────────────────────────────────────────
    const aHead = 0.82;
    const s = (cfg.headR ?? 0.20) / 0.50;      // head units -> metres (petal reach ~.50u)
    const pitch = cfg.pitch ?? rng.range(0.6, 1.05);
    const headYaw = cfg.headYaw ?? (leanA + rng.vary(0, 0.6));
    const [tx, ty, tz] = P(1);
    const ax = Math.cos(headYaw) * Math.sin(pitch), ay = Math.cos(pitch), az = Math.sin(headYaw) * Math.sin(pitch);
    let s1x = -az, s1y = 0, s1z = ax;
    { const l = Math.hypot(s1x, s1y, s1z) || 1; s1x /= l; s1z /= l; }
    const s2x = ay * s1z - az * s1y, s2y = az * s1x - ax * s1z, s2z = ax * s1y - ay * s1x;
    const neckL = 0.10 * s;
    const hx = tx + ax * neckL * 0.85, hy = ty + ay * neckL * 0.85 + neckL * 0.25, hz = tz + az * neckL * 0.85;
    const radial = (th) => [s1x * Math.cos(th) + s2x * Math.sin(th),
                            s1y * Math.cos(th) + s2y * Math.sin(th),
                            s1z * Math.cos(th) + s2z * Math.sin(th)];
    // neck TUBE from the stalk tip, burying into the head's back
    tube([tx, ty, tz], [tx, ty + neckL * 0.5, tz],
        [hx - ax * 0.024 * s, hy - ay * 0.024 * s, hz - az * 0.024 * s],
        stalkR(1), stalkR(1) * 0.8, 3, 5, 0.8, aHead, 0.03);

    // disc plate on the sheet's planar circle; back cone samples the BRACT
    // circle (a head's back is green, not seed art)
    const discUV = (rr, th) => [0.2405 + 0.2053 * (rr / DISC_R) * Math.cos(th),
                                0.780 + 0.2053 * (rr / DISC_R) * Math.sin(th)];
    const backUV = (rr, th) => [0.826 + 0.12 * (rr / DISC_R) * Math.cos(th),
                                0.3793 + 0.12 * (rr / DISC_R) * Math.sin(th)];
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
                const [uu, vv2] = uvFn(r, th);
                row.push(V(hx + ax * x * s + ox * r * s, hy + ay * x * s + oy * r * s,
                    hz + az * x * s + oz * r * s, uu, vv2, aHead));
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
    // ray petals: ONE dense whorl, coverage by construction — base arc width
    // computed from the actual petal count (+15% overlap), card widths follow
    // each variant's measured envelope; bases tuck UNDER the rim
    {
        const N = cfg.petals ?? 26;
        const cells = [];
        for (let cx2 = 0; cx2 < 4; cx2++) for (let ry = 0; ry < 2; ry++)
            cells.push({ u0: 0.5 + 0.125 * cx2 + 0.006, u1: 0.5 + 0.125 * (cx2 + 1) - 0.006,
                         v0: ry === 0 ? 0.7937 : 0.5879, v1: ry === 0 ? 0.9995 : 0.7927,
                         fit: fit.petals[cx2 * 2 + ry] });
        // required half-width at the widest band so neighbours overlap
        const rimR = 0.285;
        const needHW = (TAU * rimR / N) * 0.5 * 1.15;
        for (let k = 0; k < N; k++) {
            const th = (k / N) * TAU + rng.vary(0, 0.04);
            const ci = Math.floor(R() * cells.length);
            const cell = cells[ci];
            const maxEnv = Math.max(...cell.fit.map((b) => b[1]));
            const cardHW = needHW / maxEnv;                 // env frac -> world
            const L = cardHW * 2 * (0.207 / 0.125) * rng.range(0.92, 1.1); // cell aspect
            const [ox, oy, oz] = radial(th);
            const txp = s2x * Math.cos(th) - s1x * Math.sin(th),
                  typ = s2y * Math.cos(th) - s1y * Math.sin(th),
                  tzp = s2z * Math.cos(th) - s1z * Math.sin(th);
            // droop: most petals near the disc plane, some relaxed back
            const droop = rng.range(-0.30, 0.10) - (k % 5 === 0 ? 0.18 : 0);
            const cd = Math.cos(droop), sd = Math.sin(droop);
            const dx = ox * cd + ax * sd, dy = oy * cd + ay * sd, dz = oz * cd + az * sd;
            // enough roll spread that edge-on heads keep petal presence —
            // perfectly disc-plane petals vanish to lines in side views
            const roll = rng.vary(0, 0.35);
            const wx = txp * Math.cos(roll) + ax * Math.sin(roll),
                  wy = typ * Math.cos(roll) + ay * Math.sin(roll),
                  wz = tzp * Math.cos(roll) + az * Math.sin(roll);
            // base tucked under the rim: start inside and slightly behind
            const bxp = hx + ox * (rimR - 0.012) * s - ax * 0.004 * s,
                  byp = hy + oy * (rimR - 0.012) * s - ay * 0.004 * s,
                  bzp = hz + oz * (rimR - 0.012) * s - az * 0.004 * s;
            const bands = cell.fit;
            const NBp = bands.length;
            const sA = vb;
            for (let g = 0; g < NBp; g++) {
                const t = g / (NBp - 1);
                const hw = bands[g][1] * cardHW * 2;        // env frac of full card
                const cup = Math.sin(t * Math.PI) * L * 0.05;  // gentle forward cup
                const cx3 = bxp + dx * L * t * s + ax * cup * s,
                      cy3 = byp + dy * L * t * s + ay * cup * s,
                      cz3 = bzp + dz * L * t * s + az * cup * s;
                const u = cell.u0 + (cell.u1 - cell.u0) * 0.5;
                const vv2 = cell.v0 + (cell.v1 - cell.v0) * t;
                V(cx3 - wx * hw * s, cy3 - wy * hw * s, cz3 - wz * hw * s, cell.u0, vv2, aHead);
                V(cx3 + wx * hw * s, cy3 + wy * hw * s, cz3 + wz * hw * s, cell.u1, vv2, aHead);
            }
            for (let g = 0; g < NBp - 1; g++) {
                const a2 = sA + g * 2;
                quad(a2, a2 + 1, a2 + 3, a2 + 2);
            }
        }
    }
    // bract star cards behind the disc, sized by the art's real reach
    {
        const BR = { cu: 0.826, cv: 0.3793, r: 0.1701 };
        // clamp hard: past 1.05 the card's UV corners leave the bract
        // circle's black margin and dip into the opaque stalk band
        const bR = Math.min(fit.bractR ?? 1.05, 1.05);
        for (const [off, sc, rot] of [[0.014, 1.0, 0], [0.032, 0.74, 0.45]]) {
            const bs = 0.30 * bR * sc * s;
            const bxc = hx - ax * off * s, byc = hy - ay * off * s, bzc = hz - az * off * s;
            const sA = vb;
            for (const [k1, k2] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
                const cr = Math.cos(rot), sr = Math.sin(rot);
                const rx = k1 * cr - k2 * sr, rz = k1 * sr + k2 * cr;
                const [o1x, o1y, o1z] = [s1x * rx + s2x * rz, s1y * rx + s2y * rz, s1z * rx + s2z * rz];
                V(bxc + o1x * bs, byc + o1y * bs, bzc + o1z * bs,
                    BR.cu + BR.r * bR * rx, BR.cv + BR.r * bR * rz, aHead);
            }
            quad(sA, sA + 1, sA + 2, sA + 3);
        }
    }

    console.log(`[sunflower] head centre local (${hx.toFixed(3)}, ${hy.toFixed(3)}, ${hz.toFixed(3)}) axis (${ax.toFixed(2)}, ${ay.toFixed(2)}, ${az.toFixed(2)})`);
    const g = new T3.BufferGeometry();
    g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2));
    g.setAttribute('aH', new T3.Float32BufferAttribute(aH, 1));
    g.setIndex(idx);
    g.computeVertexNormals();
    return { geo: g, stats: { verts: vb, tris: idx.length / 3 } };
}
