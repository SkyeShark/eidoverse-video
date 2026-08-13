// sunflower_gen — the sunflower (Helianthus annuus) for createFlora: cane
// stalk, spiral petioled heart-leaves, and a nodding head — seed-disc lathe
// (Skye's highpoly cut down + baked/painted into the sheet's disc circle),
// a ring of ray-petal cards, and a bract star card behind. Every part UV'd
// onto the ONE sunflower_ trim sheet; the whole plant is a single geometry +
// single material, field-instanced by createFlora exactly like corn.
//
// sunflower_ sheet regions (UV, v up, 1024²):
//   DISC   circle centre (.24,.80) r .185 — the seed disc, planar projection
//          (u tracks local +side, v tracks local +up when facing the head)
//   PETALS u .5–1, v .586–1 — 4 cols × 2 rows = 8 ray-petal variants, base at
//          each cell's low-v edge, tip at high-v; alpha carves the silhouette
//   BRACT  circle centre (.81,.35) r .137 — back-of-head bract rosette card
//   LEAF   u .004–.62, v .21–.49 — heart leaf, base left tip right, midrib at
//          v .35; alpha carves the serrated edge
//   STALK  v .005–.195 — cane, fibre runs along v
//
// The head (neck knuckle → disc → petals → bracts) is ONE RIGID ASSEMBLY in
// wind: every head vertex carries the identical aH — displacement scales by
// aH², so any variation shears the parts apart (the corn-ear law).

const T3 = globalThis.THREE;
import { Rng } from './vegetation_shrub_gen.js';

const TAU = Math.PI * 2;

// triangle wave 0→1→0…, for seam-free mirrored UVs under ClampToEdge
const tri = (s) => { const m = s % 2; return m <= 1 ? m : 2 - m; };

// disc = a simple flattened partial sphere (Skye's spec): a lens — gently
// bulged front, shallower back — and Sol's circular disc painting carries
// ALL the surface detail (seed spiral, floret ring, spiky band)
const DISC_R = 0.30;
const DISC_FRONT = [0, 0.07, 0.13, 0.19, 0.24, 0.275, 0.295, 0.300]
    .map((r) => [r, 0.045 + 0.105 * Math.pow(1 - Math.pow(r / 0.302, 2.4), 0.7)]);
const DISC_RIM_BACK = [
    [0.297, 0.020],
    [0.270, -0.010],
    [0.180, -0.030],
    [0.000, -0.038],
];

export const SUNFLOWER_GEN = {
    sunflower: {
        height: 1.9,         // stalk height (m) before per-plant jitter
        leaves: 9,
        leafLen: 0.42,       // petiole + blade (m)
        headR: 0.20,         // head radius petal-tip to axis (m)
        petals: 21,
    },
};

export function buildSunflowerGeometry(name, seed, over = {}) {
    const cfg = { ...(SUNFLOWER_GEN[name] ?? SUNFLOWER_GEN.sunflower), ...over };
    const rng = new Rng(seed);
    const R = () => rng.next();

    const pos = [], uv = [], aH = [], idx = [];
    let vb = 0;
    const V = (x, y, z, u, vv, a) => { pos.push(x, y, z); uv.push(u, vv); aH.push(a); return vb++; };
    const quad = (a, b, c, d) => idx.push(a, b, c, a, c, d);

    // ── stalk: a near-vertical cane ─────────────────────────────────────────
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
            const vband = 0.012 + 0.176 * tri(t * 2.4);          // fibre along v, mirrored
            for (let j = 0; j <= RADS; j++) {
                const a = (j / RADS) * TAU;
                const u = 0.03 + 0.94 * tri((j / RADS) * 2);     // mirrored wrap, no seam
                row.push(V(cx + Math.cos(a) * r, t === 0 ? -0.04 : cy, cz + Math.sin(a) * r,
                    u, vband, t * 0.8));
            }
            rows.push(row);
        }
        for (let i = 0; i < rows.length - 1; i++) for (let j = 0; j < RADS; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
    }

    // ── leaves: spiral phyllotaxis, petiole + drooping heart blade ──────────
    const LEAF = { u0: 0.010, u1: 0.615, v0: 0.215, vm: 0.350, v1: 0.485 };
    const B = (p0, p1, p2, t) => {
        const s = 1 - t;
        return [s * s * p0[0] + 2 * s * t * p1[0] + t * t * p2[0],
                s * s * p0[1] + 2 * s * t * p1[1] + t * t * p2[1],
                s * s * p0[2] + 2 * s * t * p1[2] + t * t * p2[2]];
    };
    const nL = Math.round(cfg.leaves * rng.range(0.9, 1.15));
    const rank = cfg.rank ?? R() * TAU;
    for (let i = 0; i < nL; i++) {
        const f = 0.15 + 0.70 * ((i + R() * 0.4) / nL);          // foliage runs high
        const yaw = rank + i * 2.3998 + rng.vary(0, 0.3);        // golden-angle spiral
        const size = (0.55 + 0.5 * Math.sin(Math.PI * Math.min(1, 0.2 + f * 0.9))) * rng.range(0.85, 1.15);
        const petL = cfg.leafLen * 0.38 * size;
        const bladeL = cfg.leafLen * 0.62 * size;
        const [sx, sy, sz] = P(f);
        const dirX = Math.cos(yaw), dirZ = Math.sin(yaw);
        const sideX = -Math.sin(yaw), sideZ = Math.cos(yaw);
        const aL = f * 0.8;
        // petiole: thin strip arcing out and slightly up, stalk-band art
        // (fibre along its length = along v)
        const r0 = stalkR(f);
        const q0 = [sx + dirX * r0 * 0.5, sy, sz + dirZ * r0 * 0.5];
        const q1 = [q0[0] + dirX * petL * 0.6, q0[1] + petL * 0.42, q0[2] + dirZ * petL * 0.6];
        const q2 = [q0[0] + dirX * petL * 1.05, q0[1] + petL * rng.range(0.3, 0.5), q0[2] + dirZ * petL * 1.05];
        {
            const sA = vb, SEG = 3;
            const uc = 0.36, hw = 0.006 + 0.004 * size;
            for (let sg = 0; sg <= SEG; sg++) {
                const t = sg / SEG;
                const c = B(q0, q1, q2, t);
                const vband = 0.03 + t * 0.15;
                const a = aL + t * 0.04;
                V(c[0] - sideX * hw, c[1], c[2] - sideZ * hw, uc - 0.04, vband, a);
                V(c[0] + sideX * hw, c[1] + hw * 0.5, c[2] + sideZ * hw, uc + 0.04, vband, a);
            }
            for (let sg = 0; sg < SEG; sg++) {
                const a2 = sA + sg * 2;
                quad(a2, a2 + 1, a2 + 3, a2 + 2);
            }
        }
        // blade: 3-col folded strip on a drooping bezier — wide heart base,
        // tapering tip, edges cupped down; alpha carves the serration
        const b0 = q2;
        const b1 = [b0[0] + dirX * bladeL * 0.5, b0[1] + bladeL * 0.18, b0[2] + dirZ * bladeL * 0.5];
        const b2 = [b0[0] + dirX * bladeL * 0.95, b0[1] - bladeL * rng.range(0.18, 0.38), b0[2] + dirZ * bladeL * 0.95];
        const wHalf = bladeL * 0.52;
        const sB = vb, SEGB = 4;
        for (let sg = 0; sg <= SEGB; sg++) {
            const t = sg / SEGB;
            const c = B(b0, b1, b2, t);
            const hw = wHalf * (0.35 + 0.95 * Math.pow(Math.sin(Math.min(Math.PI, (0.18 + t) * Math.PI * 0.92)), 0.8));
            const sag = hw * (0.28 + 0.3 * t);                    // edges droop below midrib
            const a = Math.min(1, aL + t * t * 0.18);
            const u = LEAF.u0 + t * (LEAF.u1 - LEAF.u0);
            V(c[0] - sideX * hw, c[1] - sag, c[2] - sideZ * hw, u, LEAF.v0, a);
            V(c[0], c[1], c[2], u, LEAF.vm, a);
            V(c[0] + sideX * hw, c[1] - sag, c[2] + sideZ * hw, u, LEAF.v1, a);
        }
        for (let sg = 0; sg < SEGB; sg++) {
            const a2 = sB + sg * 3, b3 = a2 + 3;
            quad(a2, a2 + 1, b3 + 1, b3); quad(a2 + 1, a2 + 2, b3 + 2, b3 + 1);
        }
    }

    // ── the head: ONE rigid assembly (constant aH) ──────────────────────────
    const aHead = 0.82;
    const s = (cfg.headR ?? 0.20) / 0.48;      // head units → metres (petal reach .48u)
    const pitch = cfg.pitch ?? rng.range(0.6, 1.05);   // nod from vertical (rad)
    const headYaw = cfg.headYaw ?? (leanA + rng.vary(0, 0.6));  // nods the way it leans
    const [tx, ty, tz] = P(1);
    // head axis A (faces outward/down-ish), frame (S1,S2) spans the disc plane
    const ax = Math.cos(headYaw) * Math.sin(pitch), ay = Math.cos(pitch), az = Math.sin(headYaw) * Math.sin(pitch);
    let s1x = -az, s1y = 0, s1z = ax;
    { const l = Math.hypot(s1x, s1y, s1z) || 1; s1x /= l; s1z /= l; }
    const s2x = ay * s1z - az * s1y, s2y = az * s1x - ax * s1z, s2z = ax * s1y - ay * s1x;
    // head centre: a short neck arcs from the stalk tip into the disc's back
    const neckL = 0.10 * s;
    const hx = tx + ax * neckL * 0.85, hy = ty + ay * neckL * 0.85 + neckL * 0.25, hz = tz + az * neckL * 0.85;
    const radial = (th) => [s1x * Math.cos(th) + s2x * Math.sin(th),
                            s1y * Math.cos(th) + s2y * Math.sin(th),
                            s1z * Math.cos(th) + s2z * Math.sin(th)];
    // neck: stalk-band cane from the stalk tip to the disc back boss
    {
        const RADS = 6, rows = [];
        const n0 = [tx, ty, tz];
        const n1 = [tx, ty + neckL * 0.5, tz];
        const n2 = [hx - ax * 0.02 * s, hy - ay * 0.02 * s, hz - az * 0.02 * s];
        for (let g = 0; g <= 3; g++) {
            const t = g / 3;
            const c = B(n0, n1, n2, t);
            const r = stalkR(1) * (1 - t * 0.25);
            const row = [];
            const vband = 0.012 + 0.14 * tri(0.9 + t * 0.7);
            for (let j = 0; j <= RADS; j++) {
                const a = (j / RADS) * TAU;
                const [ox, oy, oz] = radial(a);
                row.push(V(c[0] + ox * r, c[1] + oy * r, c[2] + oz * r,
                    0.03 + 0.94 * tri((j / RADS) * 2), vband, t < 0.34 ? 0.8 : aHead));
            }
            rows.push(row);
        }
        for (let i = 0; i < rows.length - 1; i++) for (let j = 0; j < RADS; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
    }
    // disc lathe on the sheet's planar circle: u tracks S1, v tracks S2.
    // The BACK cone samples the BRACT circle instead — a head's back is green
    // receptacle/bracts, not seed art (the bract card in front of it mostly
    // hides it, but it peeks at grazing angles)
    const discUV = (rr, th) => [0.24 + 0.185 * (rr / DISC_R) * Math.cos(th),
                                0.80 + 0.185 * (rr / DISC_R) * Math.sin(th)];
    const backUV = (rr, th) => [0.81 + 0.10 * (rr / DISC_R) * Math.cos(th),
                                0.35 + 0.10 * (rr / DISC_R) * Math.sin(th)];
    {
        const RADD = 12;
        const front = DISC_FRONT.map((p) => [...p, discUV]);
        const back = DISC_RIM_BACK.map((p, i) => [...p, i === 0 ? discUV : backUV]);
        const prof = [...front, ...back];
        const rings = [];
        for (let k = 0; k < prof.length; k++) {
            const [r, x, uvFn] = prof[k];
            if (r < 1e-6) {
                // centre pole (front boss / back cone apex): a single vertex
                const [uu, vv2] = uvFn(0, 0);
                rings.push([V(hx + ax * x * s, hy + ay * x * s, hz + az * x * s,
                    uu, vv2, aHead)]);
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
    // ray petals: staggered double ring around the rim, 8 art variants
    {
        const N = cfg.petals ?? 21;
        const cells = [];
        for (let cx2 = 0; cx2 < 4; cx2++) for (let ry = 0; ry < 2; ry++)
            cells.push({ u0: 0.5 + 0.125 * cx2 + 0.008, u1: 0.5 + 0.125 * (cx2 + 1) - 0.008,
                         v0: ry === 0 ? 0.7937 : 0.5879, v1: ry === 0 ? 0.9995 : 0.7927 });
        for (let k = 0; k < N; k++) {
            const ringB = k % 3 === 2;                        // every 3rd petal sits behind
            const th = (k / N) * TAU + (ringB ? 0.14 : 0) + rng.vary(0, 0.05);
            const cell = cells[Math.floor(R() * cells.length)];
            const [ox, oy, oz] = radial(th);
            // tangent in the disc plane for petal width
            const txp = s2x * Math.cos(th) - s1x * Math.sin(th),
                  typ = s2y * Math.cos(th) - s1y * Math.sin(th),
                  tzp = s2z * Math.cos(th) - s1z * Math.sin(th);
            const rA = (ringB ? 0.262 : 0.272) * s;
            const xA = (ringB ? -0.002 : 0.012) * s;
            const L = 0.21 * s * rng.range(0.85, 1.12) * (ringB ? 0.92 : 1);
            const hw0 = L * 0.30;
            // petal sweeps outward in the disc plane, cupping slightly forward
            // then relaxing back at the tip
            const fwd = ringB ? -0.05 : 0.06;
            const sA = vb, SEG = 3;
            for (let sg = 0; sg <= SEG; sg++) {
                const t = sg / SEG;
                const rr = rA + L * t;
                const lift = (fwd * Math.sin(t * Math.PI) - 0.06 * t * t * (pitch > 0.9 ? 1 : 0.4)) * s;
                const hw = hw0 * (0.55 + 0.75 * Math.sin(Math.min(Math.PI, (0.25 + t) * Math.PI * 0.8)));
                const cup = hw * 0.22 * (1 - t * 0.6);
                const vv2 = cell.v0 + (cell.v1 - cell.v0) * t;
                const cx3 = hx + ax * (xA + lift) + ox * rr, cy3 = hy + ay * (xA + lift) + oy * rr, cz3 = hz + az * (xA + lift) + oz * rr;
                V(cx3 - txp * hw + ax * cup, cy3 - typ * hw + ay * cup, cz3 - tzp * hw + az * cup, cell.u0, vv2, aHead);
                V(cx3, cy3, cz3, (cell.u0 + cell.u1) / 2, vv2, aHead);
                V(cx3 + txp * hw + ax * cup, cy3 + typ * hw + ay * cup, cz3 + tzp * hw + az * cup, cell.u1, vv2, aHead);
            }
            for (let sg = 0; sg < SEG; sg++) {
                const a2 = sA + sg * 3, b3 = a2 + 3;
                quad(a2, a2 + 1, b3 + 1, b3); quad(a2 + 1, a2 + 2, b3 + 2, b3 + 1);
            }
        }
    }
    // bract star: one flat card just behind the disc + a smaller rotated
    // second for depth — the back of the head
    {
        const BR = { cu: 0.81, cv: 0.35, r: 0.137 };
        for (const [off, sc, rot] of [[0.012, 1.0, 0], [0.030, 0.72, 0.45]]) {
            const bs = 0.34 * sc * s;
            const bxc = hx - ax * off * s, byc = hy - ay * off * s, bzc = hz - az * off * s;
            const sA = vb;
            for (const [k1, k2] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
                const cr = Math.cos(rot), sr = Math.sin(rot);
                const rx = k1 * cr - k2 * sr, rz = k1 * sr + k2 * cr;
                const [o1x, o1y, o1z] = [s1x * rx + s2x * rz, s1y * rx + s2y * rz, s1z * rx + s2z * rz];
                V(bxc + o1x * bs, byc + o1y * bs, bzc + o1z * bs,
                    BR.cu + BR.r * rx, BR.cv + BR.r * rz, aHead);
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
