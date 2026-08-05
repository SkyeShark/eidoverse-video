// corn_gen — the corn plant (Zea mays) for makeVegetation: cane stalk, ranked
// arching leaves, a husked ear (peel option stands the baked cob up bare),
// silk, tassel — every part UV'd onto the ONE corn_ trim sheet, so a whole
// plant (cob included) is a single geometry + single material, field-
// instanced by grass2 exactly like the shrubs.
//
// corn_ sheet regions (UV, v up — measured off the delivered 1024² sheet):
//   COB    u 0–.5, v .701–1   — her highpoly's bake: shell island u .015–.46
//          (length ALONG u), circumference along v .706–.994; flat cap discs
//          at (.478,.93) r.017 (butt) and (.478,.97) r.010 (tip)
//   PLUME  u .5–1, v .701–1   — alpha'd tassel/silk strand art
//   HUSK   v .499–.700        — dry sheath, fibre runs along u
//   LEAF   u .004–.998, v .2139–.4922 — one full blade, base left, tip right,
//          midrib (the fold line) at v .3496; alpha carves the silhouette
//   STALK  v .005–.195        — cane, fibre runs along v
//
// Mirror-mapping note: the sheet loads ClampToEdge (no tiling), so every
// wrapped surface ping-pongs its UVs (triangle wave) instead of repeating —
// fibre stays continuous across each mirror and there is no wrap seam.

const T3 = globalThis.THREE;
import { Rng } from './vegetation_shrub_gen.js';

const TAU = Math.PI * 2;

// the cob's measured radial profile (t along ear, r at unit length) — the
// SAME table the Blender LP bakes from, so this JS rebuild lands on the bake's
// texels exactly; stations 13-15 are the tip-break recess at the colour change
const COB_PROF = [
    [0.000, 0.051], [0.025, 0.0856], [0.050, 0.1069], [0.100, 0.1241],
    [0.150, 0.1317], [0.225, 0.1345], [0.300, 0.1337], [0.400, 0.1304],
    [0.500, 0.1269], [0.600, 0.1221], [0.700, 0.1149], [0.800, 0.1028],
    [0.875, 0.0857], [0.9440, 0.0452], [0.9470, 0.0375], [0.965, 0.032],
    [0.985, 0.0240],
];
const COB_STA = [0, 1, 2, 3, 5, 7, 9, 11, 12, 13, 14, 16];   // lean in-plant subset

// triangle wave 0→1→0…, for seam-free mirrored UVs under ClampToEdge
const tri = (s) => { const m = s % 2; return m <= 1 ? m : 2 - m; };

export const CORN_GEN = {
    corn: {
        height: 2.15,        // cane height (m) before per-plant jitter
        leaves: 10,
        leafLen: 0.85,
        ears: 1,             // +1 sometimes, below
        peel: false,         // true: husk pulled open, the baked cob standing bare
    },
};

export function buildCornGeometry(name, seed, over = {}) {
    const cfg = { ...(CORN_GEN[name] ?? CORN_GEN.corn), ...over };
    const rng = new Rng(seed);
    const R = () => rng.next();

    const pos = [], uv = [], aH = [], idx = [];
    let vb = 0;
    const V = (x, y, z, u, vv, a) => { pos.push(x, y, z); uv.push(u, vv); aH.push(a); return vb++; };
    const quad = (a, b, c, d) => idx.push(a, b, c, a, c, d);

    // ── stalk: a leaning cane ────────────────────────────────────────────────
    const H = cfg.height * (cfg.heightJitter ?? rng.range(0.92, 1.08));
    const leanA = R() * TAU, leanAmt = (cfg.stalkLean ?? rng.range(0.04, 0.13)) * H;
    const lx = Math.cos(leanA) * leanAmt, lz = Math.sin(leanA) * leanAmt;
    const P = (t) => [lx * t * t, t * H, lz * t * t];
    const stalkR = (t) => 0.023 * (1 - t) + 0.010 * t;
    {
        const STA = [0, 0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 1], RADS = 6;
        const rows = [];
        for (const t of STA) {
            const [cx, cy, cz] = P(t);
            const r = stalkR(t), row = [];
            const vband = 0.012 + 0.176 * tri(t * 2.2);          // fibre along v, mirrored
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

    // ── leaves: distichous ranks, arching blades on the leaf band ────────────
    const LEAF = { v0: 0.2139, vm: 0.3496, v1: 0.4922, u0: 0.004, u1: 0.998 };
    const nL = Math.round(cfg.leaves * rng.range(0.9, 1.1));
    const rank = cfg.rank ?? R() * TAU;      // rank/earF/earYaw: lookdev overrides
    const B = (p0, p1, p2, t) => {                                // quadratic bezier
        const s = 1 - t;
        return [s * s * p0[0] + 2 * s * t * p1[0] + t * t * p2[0],
                s * s * p0[1] + 2 * s * t * p1[1] + t * t * p2[1],
                s * s * p0[2] + 2 * s * t * p1[2] + t * t * p2[2]];
    };
    function leaf(f, yaw, L, wHalf, up, reach, tipY) {
        const [sx, sy, sz] = P(f);
        const dirX = Math.cos(yaw), dirZ = Math.sin(yaw);
        const sideX = -Math.sin(yaw), sideZ = Math.cos(yaw);
        const r = stalkR(f);
        const p0 = [sx + dirX * r * 0.6, sy, sz + dirZ * r * 0.6];
        const p1 = [p0[0] + dirX * L * 0.45, p0[1] + L * up, p0[2] + dirZ * L * 0.45];
        const p2 = [p0[0] + dirX * L * reach, p0[1] + L * tipY, p0[2] + dirZ * L * reach];
        const rollK = rng.vary(0, 0.7);                           // cumulative twist
        const aH0 = f * 0.8;
        const SEG = 8, s0 = vb;
        for (let sg = 0; sg <= SEG; sg++) {
            const t = sg / SEG;
            const c = B(p0, p1, p2, t);
            // tangent → a stable near-up cross vector for fold/roll
            const d = B(p0, p1, p2, Math.min(1, t + 0.01));
            const tx = d[0] - c[0], ty = d[1] - c[1], tz = d[2] - c[2];
            const tl = Math.hypot(tx, ty, tz) || 1;
            // crossV = normalize(tangent × side): the blade's local "up"
            let ux = (ty / tl) * sideZ,
                uy = (tz / tl) * sideX - (tx / tl) * sideZ,
                uz = -(ty / tl) * sideX;
            const ul = Math.hypot(ux, uy, uz) || 1; ux /= ul; uy /= ul; uz /= ul;
            if (uy < 0) { ux = -ux; uy = -uy; uz = -uz; }
            const rA = rollK * t;
            const cr = Math.cos(rA), sr = Math.sin(rA);
            const csx = sideX * cr + ux * sr, csy = uy * sr, csz = sideZ * cr + uz * sr;
            const hw = wHalf * (0.30 + 1.15 * Math.pow(Math.sin(Math.min(Math.PI, t * Math.PI * 1.05)), 0.65));
            const fold = hw * (0.55 * (1 - t) - 0.25 * t);        // V at base, edges sag at tip
            const a = Math.min(1, aH0 + t * t * (1 - aH0) * 0.85);
            const u = LEAF.u0 + t * (LEAF.u1 - LEAF.u0);
            V(c[0] - csx * hw + ux * fold, c[1] - csy * hw + uy * fold, c[2] - csz * hw + uz * fold, u, LEAF.v0, a);
            V(c[0], c[1], c[2], u, LEAF.vm, a);
            V(c[0] + csx * hw + ux * fold, c[1] + csy * hw + uy * fold, c[2] + csz * hw + uz * fold, u, LEAF.v1, a);
        }
        for (let sg = 0; sg < SEG; sg++) {
            const a = s0 + sg * 3, b = a + 3;
            quad(a, a + 1, b + 1, b); quad(a + 1, a + 2, b + 2, b + 1);
        }
    }
    // ears are FULLY drawn first — geometry params included — so leaves get
    // exact collision capsules to steer around
    const earSpecs = [];
    {
        // variety: 1-3 ears, each independently peeled — mixed open and
        // closed cobs on one stalk (cfg.peel pins the FIRST ear open for
        // lookdev; peelChance rolls the rest)
        const maxE = cfg.ears ?? 1;
        const nE = 1 + (maxE >= 2 && R() < 0.4 ? 1 : 0) + (maxE >= 3 && R() < 0.22 ? 1 : 0);
        const pc = cfg.peelChance ?? (cfg.peel ? 0.5 : 0);
        for (let k = 0; k < nE; k++)
            earSpecs.push({ f: (cfg.earF ?? rng.range(0.33, 0.4)) + k * rng.range(0.12, 0.16),
                yaw: cfg.earYaw != null ? cfg.earYaw + Math.PI * k : rank + Math.PI * k + rng.vary(0.8, 0.5),
                lean: rng.range(0.4, 0.58), len: rng.range(0.24, 0.29) * (1 - k * 0.12),
                peel: (cfg.peel && k === 0) || R() < pc });
    }
    // world-space keep-out: a capsule down the ear body (+ husk margin) and,
    // on peeled ears, a sphere over the curl zone. REAL geometry tests —
    // base-azimuth heuristics let broad mid-blades sweep straight through
    // the cob, and husk-curl tips punch through blades
    const earCaps = earSpecs.map((e) => {
        const [sx, sy, sz] = P(e.f);
        const dirX = Math.cos(e.yaw), dirZ = Math.sin(e.yaw);
        const ax = dirX * Math.sin(e.lean), ay = Math.cos(e.lean), az = dirZ * Math.sin(e.lean);
        const r = stalkR(e.f);
        const bx = sx + dirX * r * 0.35, by = sy - 0.02, bz = sz + dirZ * r * 0.35;
        const cobLen = e.len * 0.95;
        return { ax, ay, az, bx, by, bz, segL: cobLen * (e.peel ? 1.0 : 1.25),
            r: cobLen * 0.135 + 0.025,
            cx: bx + ax * cobLen * 0.45, cy: by + ay * cobLen * 0.45, cz: bz + az * cobLen * 0.45,
            cr: e.peel ? e.len * 0.5 : 0 };
    });
    const distPtSeg = (px, py, pz, c) => {
        const dx = px - c.bx, dy = py - c.by, dz = pz - c.bz;
        const t = Math.max(0, Math.min(c.segL, dx * c.ax + dy * c.ay + dz * c.az));
        return Math.hypot(px - (c.bx + c.ax * t), py - (c.by + c.ay * t), pz - (c.bz + c.az * t));
    };
    const placedLeaves = [];
    for (let i = 0; i < nL; i++) {
        const f = 0.14 + 0.74 * ((i + R() * 0.5) / nL);
        let L0 = cfg.leafLen * (0.62 + 0.55 * Math.sin(Math.PI * Math.min(1, f * 1.4))) * rng.range(0.85, 1.15);
        // top leaves shorten and stand up along the peduncle
        if (f > 0.7) L0 *= 1 - (f - 0.7) * 1.6;
        // candidate blades are COLLISION-TESTED as swept centrelines against
        // the ear capsules and every placed blade, then rebuilt with the
        // accepted arc. Failed rounds redraw yaw AND droop; the last resort
        // is a shorter, higher blade (short upright leaves always clear).
        let best = null;
        for (let tries = 0; tries < 8 && !best; tries++) {
            const yaw = rank + i * Math.PI + i * 0.55 + rng.vary(0, 0.85);
            const up = rng.range(0.5, 0.64), reach = rng.range(1.0, 1.18);
            const tipY = tries < 6 ? rng.range(-0.26, 0.0) : rng.range(0.0, 0.12);
            const L = tries < 6 ? L0 : L0 * 0.6;
            const [sx, sy, sz] = P(f);
            const dirX = Math.cos(yaw), dirZ = Math.sin(yaw);
            const r0 = stalkR(f);
            const q0 = [sx + dirX * r0 * 0.6, sy, sz + dirZ * r0 * 0.6];
            const q1 = [q0[0] + dirX * L * 0.45, q0[1] + L * up, q0[2] + dirZ * L * 0.45];
            const q2 = [q0[0] + dirX * L * reach, q0[1] + L * tipY, q0[2] + dirZ * L * reach];
            const pts = [];
            let ok = true;
            for (let sg = 1; sg <= 8 && ok; sg++) {
                const t = sg / 8, s2 = 1 - t;
                const px = s2 * s2 * q0[0] + 2 * s2 * t * q1[0] + t * t * q2[0];
                const py = s2 * s2 * q0[1] + 2 * s2 * t * q1[1] + t * t * q2[1];
                const pz = s2 * s2 * q0[2] + 2 * s2 * t * q1[2] + t * t * q2[2];
                const hw = (L * 0.092) * (0.30 + 1.15 * Math.pow(Math.sin(Math.min(Math.PI, t * Math.PI * 1.05)), 0.65));
                for (const c of earCaps) {
                    if (distPtSeg(px, py, pz, c) < c.r + hw * 0.5) { ok = false; break; }
                    if (c.cr && Math.hypot(px - c.cx, py - c.cy, pz - c.cz) < c.cr + hw * 0.4) { ok = false; break; }
                }
                if (!ok) break;
                for (const pl of placedLeaves) {
                    for (const q of pl) {
                        const dy = py - q[1];
                        if (dy > 0.28 || dy < -0.28) continue;
                        if (Math.hypot(px - q[0], dy, pz - q[2]) < (hw + q[3]) * 0.55) { ok = false; break; }
                    }
                    if (!ok) break;
                }
                pts.push([px, py, pz, hw]);
            }
            if (ok || tries === 7) best = { yaw, up, reach, tipY, L, pts };
        }
        placedLeaves.push(best.pts);
        leaf(f, best.yaw, best.L, best.L * 0.092 * rng.range(0.9, 1.1), best.up, best.reach, best.tipY);
    }

    // ── ear(s): husked spindle at a mid node; peel stands the cob up bare ────
    const HUSK = { v0: 0.505, v1: 0.693, u0: 0.03, u1: 0.97 };
    function basisFrom(ax, ay, az) {
        // orthonormal frame around an axis
        let s1x = -az, s1y = 0, s1z = ax;
        const l = Math.hypot(s1x, s1y, s1z) || 1; s1x /= l; s1z /= l;
        const s2x = ay * s1z - az * s1y, s2y = az * s1x - ax * s1z, s2z = ax * s1y - ay * s1x;
        return [s1x, s1y, s1z, s2x, s2y, s2z];
    }
    function cob(bx, by, bz, ax, ay, az, len, aE) {
        const [s1x, s1y, s1z, s2x, s2y, s2z] = basisFrom(ax, ay, az);
        const RADC = 10, t1 = 0.985;
        const rows = [];
        for (const si of COB_STA) {
            const [t, r0] = COB_PROF[si];
            const r = r0 * len, row = [];
            const cx = bx + ax * t * len, cy = by + ay * t * len, cz = bz + az * t * len;
            const u = 0.015 + (t / t1) * (0.46 - 0.015);
            for (let j = 0; j <= RADC; j++) {
                const a = (j / RADC) * TAU;
                const ox = s1x * Math.cos(a) + s2x * Math.sin(a),
                      oy = s1y * Math.cos(a) + s2y * Math.sin(a),
                      oz = s1z * Math.cos(a) + s2z * Math.sin(a);
                row.push(V(cx + ox * r, cy + oy * r, cz + oz * r,
                    u, 0.710 + (j / RADC) * (0.990 - 0.710), aE + t * 0.08));
            }
            rows.push(row);
        }
        for (let i = 0; i < rows.length - 1; i++) for (let j = 0; j < RADC; j++)
            quad(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]);
        // flat caps on their own disc islands (matching the bake)
        for (const [si, cu, cv, cr, flip] of [[0, 0.478, 0.93, 0.017, true], [COB_STA.length - 1, 0.478, 0.97, 0.010, false]]) {
            const row = rows[si === 0 ? 0 : rows.length - 1];
            const t = COB_PROF[COB_STA[si === 0 ? 0 : COB_STA.length - 1]][0];
            const c = V(bx + ax * t * len, by + ay * t * len, bz + az * t * len, cu, cv, aE + t * 0.08);
            for (let j = 0; j < 10; j++) {
                if (flip) idx.push(row[j + 1], row[j], c);
                else idx.push(row[j], row[j + 1], c);
            }
        }
    }
    function ear(e) {
        const { f, yaw, peel } = e;
        const [sx, sy, sz] = P(f);
        const dirX = Math.cos(yaw), dirZ = Math.sin(yaw);
        const lean = e.lean;                                      // drawn at spec time (collision capsules)
        const ax = dirX * Math.sin(lean), ay = Math.cos(lean), az = dirZ * Math.sin(lean);
        const r = stalkR(f);
        // base SUNK into the cane — the junction law: buried reads attached
        const bx = sx + dirX * r * 0.35, by = sy - 0.02, bz = sz + dirZ * r * 0.35;
        const len = e.len;
        const [s1x, s1y, s1z, s2x, s2y, s2z] = basisFrom(ax, ay, az);
        const aE = f * 0.8;
        const cobLen = len * 0.95;
        const cobR = (t) => {
            const tc = Math.min(0.985, Math.max(0, t));
            for (let i = 1; i < COB_PROF.length; i++) {
                if (COB_PROF[i][0] >= tc) {
                    const [ta, ra] = COB_PROF[i - 1], [tb, rb] = COB_PROF[i];
                    return (ra + (rb - ra) * ((tc - ta) / ((tb - ta) || 1))) * cobLen;
                }
            }
            return COB_PROF[COB_PROF.length - 1][1] * cobLen;
        };
        const radial = (th) => [s1x * Math.cos(th) + s2x * Math.sin(th),
                                s1y * Math.cos(th) + s2y * Math.sin(th),
                                s1z * Math.cos(th) + s2z * Math.sin(th)];
        // ── the husk IS leaves: overlapping curved strips WRAPPED around the
        // cob's own profile, like the real thing. Closed: they converge past
        // the tip in staggered points. Peeled: each wraps the lower half then
        // CURLS outward and down, the bare cob standing above.
        // closed: five strips ring the ear. Peeled: a FEW leaves at uneven
        // azimuths (a symmetric ring of many read as a machine part)
        const nH = peel ? 3 : 5;
        // leaf azimuths drawn first, then each arc width computed from the
        // ACTUAL gaps to its neighbours (+15% overlap) — coverage of the
        // circumference is guaranteed by construction. Independent random
        // widths left wedge gaps that bared the cob at the ear's base.
        const th0s = [];
        if (peel) { let acc = R() * TAU; for (let k2 = 0; k2 < nH; k2++) { th0s.push(acc); acc += rng.range(1.6, 2.6); } }
        else for (let k2 = 0; k2 < nH; k2++) th0s.push((k2 / nH) * TAU + R() * 0.5);
        const norm = (a) => ((a % TAU) + TAU) % TAU;
        const sorted = th0s.map(norm).sort((a, b) => a - b);
        const arcFor = (th) => {
            const i = sorted.indexOf(norm(th));
            const nxt = sorted[(i + 1) % sorted.length], prv = sorted[(i - 1 + sorted.length) % sorted.length];
            const gN = norm(nxt - sorted[i]) || TAU, gP = norm(sorted[i] - prv) || TAU;
            return Math.min(1.95, Math.max(0.9, 0.65 * Math.max(gN, gP)));
        };
        for (let k = 0; k < nH; k++) {
            const th0 = th0s[k];
            const twist = rng.vary(0.35, 0.1);                    // slight spiral (tame: drift eats the seam margin)
            const halfArc = arcFor(th0);
            const wrapTop = peel ? rng.range(0.4, 0.5) : rng.range(0.98, 1.04);
            const lift = 0.004 + k * 0.0016;                      // layered shells, no z-fight
            const sA = vb;
            let rows2 = 0;
            const vMidH = (HUSK.v0 + HUSK.v1) / 2, vSpanH = (HUSK.v1 - HUSK.v0) / 2 - 0.02;
            const COLS = [[-1, -vSpanH], [-0.5, -vSpanH * 0.5], [0, 0], [0.5, vSpanH * 0.5], [1, vSpanH]];
            const emitWrapRow = (t, uFrac, pad = 0) => {
                const th = th0 + twist * Math.max(0, t);
                const u = HUSK.u0 + uFrac * (HUSK.u1 - HUSK.u0);
                for (const [kk, dv] of COLS) {
                    const [ox, oy, oz] = radial(th + kk * halfArc);
                    const rr = Math.max(0.004, cobR(t)) + lift + pad + (1 - Math.abs(kk)) * 0.003;
                    V(bx + ax * t * cobLen + ox * rr, by + ay * t * cobLen + oy * rr,
                      bz + az * t * cobLen + oz * rr, u, vMidH + dv, aE + Math.max(0, t) * 0.08);
                }
                rows2++;
            };
            // rows dense enough that straight spans clear the cob's CONVEX
            // butt flare, plus per-segment sagitta padding — 4 rows left the
            // cone chord cutting inside the flare and kernels showed at the
            // base (the column-chord bug's twin, along the length axis)
            const wrapSegs = 5;
            const rowTs = [];
            for (let sg = 0; sg <= wrapSegs; sg++) rowTs.push(-0.03 + (wrapTop + 0.03) * (sg / wrapSegs));
            const segPad = (ta, tb) => {
                let d = 0;
                for (let m = 1; m < 5; m++) {
                    const tm = ta + (tb - ta) * (m / 5);
                    d = Math.max(d, cobR(tm) - (cobR(ta) + (cobR(tb) - cobR(ta)) * (m / 5)));
                }
                return d;
            };
            for (let sg = 0; sg <= wrapSegs; sg++) {
                const t = rowTs[sg];
                const padA = sg > 0 ? segPad(rowTs[sg - 1], t) : 0;
                const padB = sg < wrapSegs ? segPad(t, rowTs[sg + 1]) : 0;
                emitWrapRow(t, 0.05 + 0.5 * (sg / wrapSegs), Math.max(padA, padB));
            }
            if (peel) {
                // the curl: off the wrap rim, outward then down beside the ear
                const thR = th0 + twist * wrapTop;
                const [ox, oy, oz] = radial(thR);
                const rimR = cobR(wrapTop) + lift;
                const px = bx + ax * wrapTop * cobLen + ox * rimR,
                      py = by + ay * wrapTop * cobLen + oy * rimR,
                      pz = bz + az * wrapTop * cobLen + oz * rimR;
                // CUBIC bend, tangent-continuous with the wrap: it keeps going
                // UP off the rim, then turns out and over in one smooth arc —
                // the quadratic version snapped direction at the rim (a 90°
                // crink at one loop, not a bend)
                const cL = len * rng.range(0.38, 0.55);
                const c1 = [px + ax * cL * 0.38 + ox * cL * 0.06,
                            py + ay * cL * 0.38 + oy * cL * 0.06,
                            pz + az * cL * 0.38 + oz * cL * 0.06];
                const c2 = [px + ox * cL * 0.62 + ax * cL * 0.1,
                            py + oy * cL * 0.62 + ay * cL * 0.1,
                            pz + oz * cL * 0.62 + az * cL * 0.1];
                const ce = [px + ox * cL * 0.6 - ax * cL * 0.55,
                            py + oy * cL * 0.6 - ay * cL * 0.55 - cL * rng.range(0.1, 0.3),
                            pz + oz * cL * 0.6 - az * cL * 0.55];
                const tx2 = s2x * Math.cos(thR) - s1x * Math.sin(thR),
                      ty2 = s2y * Math.cos(thR) - s1y * Math.sin(thR),
                      tz2 = s2z * Math.cos(thR) - s1z * Math.sin(thR);
                const w0 = halfArc * rimR;                        // continues the wrap's width
                for (let sg2 = 1; sg2 <= 7; sg2++) {
                    const t2 = sg2 / 7, s0b = 1 - t2;
                    const c = [
                        s0b * s0b * s0b * px + 3 * s0b * s0b * t2 * c1[0] + 3 * s0b * t2 * t2 * c2[0] + t2 * t2 * t2 * ce[0],
                        s0b * s0b * s0b * py + 3 * s0b * s0b * t2 * c1[1] + 3 * s0b * t2 * t2 * c2[1] + t2 * t2 * t2 * ce[1],
                        s0b * s0b * s0b * pz + 3 * s0b * s0b * t2 * c1[2] + 3 * s0b * t2 * t2 * c2[2] + t2 * t2 * t2 * ce[2]];
                    // gentle taper: 0.85 left thin straight straps that read
                    // as bent paper ribbons; a husk leaf keeps its width
                    const w = w0 * (1 - t2 * 0.55) * (1 + 0.1 * Math.sin(t2 * 7.0 + k * 2.1)) * (1 - Math.pow(t2, 5) * 0.85);   // pinch to a point — the band has no alpha to carve tips
                    const cup = w * 0.55 * (0.3 + t2 * 0.7);      // curved sheet along the whole curl
                    const u = HUSK.u0 + (0.55 + 0.42 * t2) * (HUSK.u1 - HUSK.u0);
                    for (const [kk, dv] of COLS) {
                        const bend = (1 - kk * kk) * cup;         // parabolic cross-curve
                        V(c[0] + tx2 * w * kk + ox * bend, c[1] + ty2 * w * kk + oy * bend, c[2] + tz2 * w * kk + oz * bend,
                          u, vMidH + dv, aE + 0.12);
                    }
                    rows2++;
                }
            }
            for (let sg = 0; sg < rows2 - 1; sg++) {
                const a2 = sA + sg * 5, b2 = a2 + 5;
                for (let cq = 0; cq < 4; cq++) quad(a2 + cq, a2 + cq + 1, b2 + cq + 1, b2 + cq);
            }
            if (!peel) {
                // staggered point past the tip
                const tipT = 1.08 + R() * 0.12;
                const th = th0 + twist * tipT;
                const [ox, oy, oz] = radial(th);
                const apex = V(bx + ax * tipT * cobLen + ox * 0.004, by + ay * tipT * cobLen + oy * 0.004,
                    bz + az * tipT * cobLen + oz * 0.004,
                    HUSK.u0 + 0.97 * (HUSK.u1 - HUSK.u0), (HUSK.v0 + HUSK.v1) / 2, aE + 0.12);
                const lastRow = sA + (rows2 - 1) * 5;
                for (let cq = 0; cq < 4; cq++) idx.push(lastRow + cq, lastRow + cq + 1, apex);
            }
        }
        if (peel) cob(bx, by, bz, ax, ay, az, cobLen, aE);
        // silk: thin strand slivers hanging by the tip's side (never draped
        // across the kernel face). Closed: bursting OUT past the husk points.
        const st = peel ? 1.02 : 1.16;                    // ABOVE the tip cap / past the husk apex
        const stx = bx + ax * st * cobLen, sty = by + ay * st * cobLen, stz = bz + az * st * cobLen;
        for (let k = 0; k < 4; k++) {
            const a0 = R() * TAU;
            const hw2 = rng.range(0.004, 0.007);
            const bX = Math.cos(a0), bZ = Math.sin(a0);   // bend-over direction
            const sL = rng.range(0.05, 0.085);
            const vMid = 0.875 + R() * 0.1;
            // X-cross pair — a single flat strip vanishes edge-on
            for (const [wx, wy, wz] of [[-Math.sin(a0) * hw2, 0, Math.cos(a0) * hw2],
                                        [Math.cos(a0) * hw2 * 0.5, hw2 * 0.85, Math.sin(a0) * hw2 * 0.5]]) {
                const sA = vb;
                for (let sg = 0; sg <= 3; sg++) {
                    const t = sg / 3;
                    const rise = sL * 0.6 * t;             // up the axis first...
                    const out = sL * 0.95 * t * t;         // ...then arcs outward
                    const drop = sL * 0.7 * t * t * t;     // ...and over
                    const cx2 = stx + ax * rise + bX * out, cy2 = sty + ay * rise - drop, cz2 = stz + az * rise + bZ * out;
                    const u = 0.72 + t * 0.275;    // sparse tip corner: card edges cross mostly-empty alpha
                    V(cx2 - wx, cy2 - wy, cz2 - wz, u, vMid - 0.025, aE + 0.18);
                    V(cx2 + wx, cy2 + wy, cz2 + wz, u, vMid + 0.025, aE + 0.18);
                }
                for (let sg = 0; sg < 3; sg++) {
                    const a2 = sA + sg * 2;
                    quad(a2, a2 + 1, a2 + 3, a2 + 2);
                }
            }
        }
    }
    for (const e of earSpecs) ear(e);

    // ── tassel: sparse strand-branch crown over a short spike ────────────────
    {
        const [tx, ty, tz] = P(1);
        const spikeH = rng.range(0.09, 0.13), s0 = vb, RADS = 4;
        for (let g = 0; g <= 2; g++) {
            const t = g / 2, r = 0.006 * (1 - t * 0.7);
            for (let j = 0; j <= RADS; j++) {
                const a = (j / RADS) * TAU;
                V(tx + Math.cos(a) * r, ty + spikeH * t, tz + Math.sin(a) * r,
                    0.03 + 0.94 * tri((j / RADS) * 2), 0.19 - t * 0.05, 0.82 + t * 0.1);
            }
        }
        for (let g = 0; g < 2; g++) for (let j = 0; j < RADS; j++)
            quad(s0 + g * (RADS + 1) + j, s0 + g * (RADS + 1) + j + 1, s0 + (g + 1) * (RADS + 1) + j + 1, s0 + (g + 1) * (RADS + 1) + j);
        // sparse crown per the reference diagram: thin arcing branch strands
        // around a central spike, mostly AIR — each branch is a narrow strip
        // sampling a thin v-slice of the plume art (the silk trick: strands
        // run along u, so a sliver reads as one seed-strand branch). Full-art
        // cards made a dense plume mass no real tassel has.
        const nB = 6;
        for (let k = 0; k < nB; k++) {
            const t01 = k / (nB - 1);
            const yaw = k * 2.4 + R() * 0.5;
            const pitch = 0.12 + t01 * 0.75 + R() * 0.1;            // centre near-vertical → rim ~50°
            const bl = rng.range(0.16, 0.26) * (1 - t01 * 0.25);
            const hw = rng.range(0.011, 0.02);
            const dx = Math.cos(yaw) * Math.sin(pitch), dyy = Math.cos(pitch), dz = Math.sin(yaw) * Math.sin(pitch);
            const px2 = -Math.sin(yaw), pz2 = Math.cos(yaw);
            const by2 = ty + spikeH * rng.range(0.35, 0.95);
            const vMid = 0.725 + R() * 0.22;
            // X-cross pair, art-edge-to-art-edge u — flat strips vanished
            // edge-on and mid-art windows cut painted strands with hard edges
            for (const [wxx, wyy, wzz] of [[px2 * hw, 0, pz2 * hw],
                                           [dx * 0, hw * 0.9, dz * 0]]) {
                const sA = vb;
                for (let sg = 0; sg <= 3; sg++) {
                    const t = sg / 3;
                    const arc = t * t * bl * 0.55;                  // strand arcs over
                    const cx2 = tx + dx * bl * t + dx * arc * 0.4, cy2 = by2 + dyy * bl * t - arc, cz2 = tz + dz * bl * t + dz * arc * 0.4;
                    const u = 0.7 + t * 0.295;
                    const a = 0.88 + t * 0.12;
                    V(cx2 - wxx, cy2 - wyy, cz2 - wzz, u, vMid - 0.025, a);
                    V(cx2 + wxx, cy2 + wyy, cz2 + wzz, u, vMid + 0.025, a);
                }
                for (let sg = 0; sg < 3; sg++) {
                    const a = sA + sg * 2;
                    quad(a, a + 1, a + 3, a + 2);
                }
            }
        }
    }

    const g = new T3.BufferGeometry();
    g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2));
    g.setAttribute('aH', new T3.Float32BufferAttribute(aH, 1));
    g.setIndex(idx);
    g.computeVertexNormals();
    return { geo: g, stats: { verts: vb, tris: idx.length / 3 } };
}
