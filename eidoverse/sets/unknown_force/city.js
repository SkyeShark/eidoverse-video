// city.js — UNKNOWN FORCE's world: a dark cyberpunk megacity at night, painted by a Futurist.
//
// A radial city around THE HOLE (hole.js): four grand avenues run in from the diagonals to the hole, four more start
// at the first ring road, six ring roads circle it. Sant'Elia's stepped towers with external lift shafts, slabs with
// fins, wedges with sloped tops, set-back skyscrapers; the inner towers lean toward the hole (the city bows to its
// centre: every line runs to her). Lit windows are procedural per building, signs are canvas material on one
// instanced mesh, the streets are wet and mirror the neon, rain wraps the camera, a low rain-cloud deck hangs at
// 345–520 m and glows with the city's light.
//
//   const C = await import(new URL('sets/unknown_force/city.js', EIDOVERSE_DIR).href);
//   const city = await C.build(THREE, { hole: true });       // includes hole.js (the chorus stage) by default
//   scene.add(city.group); scene.fogNode = city.parts.fogNode;
//   per frame: city.update(t, { camera, camVel });   then applyCam(THREE, camera, C.diveCam(t)) for the intro
//
// FRAME: the singer's mark (bottom of the hole) is the origin; the streets are at y = STREET_Y (12 m). See CITY_HOLE.md.

import * as KIT from './citykit.js';
const { STREET_Y, HOLE, AVENUES_MAIN, AVENUES_SECOND, AVENUE_W, SECOND_START, RINGS, CITY_R, FAR_R, rng, hash1, smooth, smoother,
    lerp, clamp01, keyed, angDiff } = KIT;
export { STREET_Y, applyCam, camVelocity } from './citykit.js';
export const applyCamera = KIT.applyCam;

const D2R = Math.PI / 180;
// the crossing the dive falls into: grand avenue 45° x the first ring road
export const DIVE_AV = 45 * D2R;
export const DIVE_C = [RINGS[0].r * Math.cos(DIVE_AV), STREET_Y, RINGS[0].r * Math.sin(DIVE_AV)];
const PLAZA_R = 44;                 // the open plaza at the dive's crossing (low pavilions only)
const SUPERTALL_KEEPOUT = 170;      // no supertall within this of the dive axis

// ------------------------------------------------------------------------------------------------ layout
// zones between ring roads (radial), sectors between avenues (angular), blocks between minor streets
function zoneList() {
    const edges = [{ r: HOLE.rimTower[1] + 4, w: 0 }].concat(RINGS).concat([{ r: CITY_R, w: 0 }]);
    const zones = [];
    for (let i = 0; i < edges.length - 1; i++) zones.push({ i, r0: edges[i].r + edges[i].w / 2 + 1, r1: edges[i + 1].r - edges[i + 1].w / 2 - 1 });
    return zones;
}
function zoneParams(i) {
    // height range, lean toward the hole (deg), block arc target (m), lit fraction, podium chance
    return [
        { h: [110, 250], lean: 5.0, arc: 62, lit: [0.10, 0.26], pod: 0.9 },
        { h: [90, 230], lean: 3.4, arc: 70, lit: [0.09, 0.24], pod: 0.85 },
        { h: [60, 190], lean: 1.8, arc: 78, lit: [0.08, 0.22], pod: 0.8 },
        { h: [45, 160], lean: 0.8, arc: 84, lit: [0.07, 0.20], pod: 0.7 },
        { h: [35, 130], lean: 0.0, arc: 90, lit: [0.06, 0.18], pod: 0.6 },
        { h: [26, 110], lean: 0.0, arc: 96, lit: [0.05, 0.16], pod: 0.5 },
        { h: [20, 90], lean: 0.0, arc: 100, lit: [0.05, 0.15], pod: 0.4 },
    ][Math.min(i, 6)];
}
function sectorEdges(rMid) {
    const av = AVENUES_MAIN.concat(rMid >= SECOND_START ? AVENUES_SECOND : []).map((a) => ((a % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)).sort((a, b) => a - b);
    const out = [];
    for (let i = 0; i < av.length; i++) { const a = av[i], b = i + 1 < av.length ? av[i + 1] : av[0] + 2 * Math.PI; out.push([a, b]); }
    return out;
}
export function planCity(seed = 1909) {
    const R = rng(seed);
    const blocks = [], lots = [];
    for (const z of zoneList()) {
        const P = zoneParams(z.i);
        const depth = z.r1 - z.r0;
        // deep zones get a ring alley through the middle
        const rows = depth > 150 ? [[z.r0, (z.r0 + z.r1) / 2 - 4], [(z.r0 + z.r1) / 2 + 4, z.r1]] : [[z.r0, z.r1]];
        for (const [ra, rb] of rows) {
            const rMid = (ra + rb) / 2;
            for (const [a0, a1] of sectorEdges(rMid)) {
                const marg0 = Math.asin(Math.min(0.9, (AVENUE_W / 2 + 1) / ra));
                const s0 = a0 + marg0, s1 = a1 - marg0;
                const n = Math.max(1, Math.round(rMid * (s1 - s0) / P.arc));
                const alley = 5 / rMid;
                for (let k = 0; k < n; k++) {
                    const t0 = s0 + (s1 - s0) * k / n + (k > 0 ? alley : 0);
                    const t1 = s0 + (s1 - s0) * (k + 1) / n - (k < n - 1 ? alley : 0);
                    const b = { zone: z.i, ra, rb, t0, t1 };
                    blocks.push(b);
                    // lots: split the block's buildable area (inset by a 4 m sidewalk) into 1..4 lots
                    const ia = ra + 4, ib = rb - 4;
                    const tw = (t1 - t0) - 8 / rMid;
                    const ti0 = t0 + 4 / rMid;
                    const arcW = rMid * tw, dep = ib - ia;
                    const nt = arcW > 70 ? 2 : 1, nr = dep > 80 ? 2 : 1;
                    for (let i = 0; i < nt; i++) for (let j = 0; j < nr; j++) {
                        const la0 = ti0 + tw * i / nt + (i > 0 ? 2 / rMid : 0), la1 = ti0 + tw * (i + 1) / nt - (i < nt - 1 ? 2 / rMid : 0);
                        const lr0 = ia + dep * j / nr + (j > 0 ? 2 : 0), lr1 = ia + dep * (j + 1) / nr - (j < nr - 1 ? 2 : 0);
                        lots.push({ zone: z.i, r0: lr0, r1: lr1, t0: la0, t1: la1, seed: R() });
                    }
                }
            }
        }
    }
    // supertalls: a handful of 300-420 m towers that pierce the cloud base, away from the dive
    const sup = [];
    const cand = lots.filter((l) => l.zone >= 1 && l.zone <= 4 && (l.r1 - l.r0) > 40);
    for (let k = 0; k < 400 && sup.length < 11; k++) {
        const l = cand[Math.floor(R() * cand.length)];
        const rc = (l.r0 + l.r1) / 2, tc = (l.t0 + l.t1) / 2;
        const x = rc * Math.cos(tc), z = rc * Math.sin(tc);
        if (Math.hypot(x - DIVE_C[0], z - DIVE_C[2]) < SUPERTALL_KEEPOUT) continue;
        if (sup.some((s) => Math.hypot(s.x - x, s.z - z) < 260)) continue;
        l.supertall = true; sup.push({ x, z });
    }
    return { blocks, lots, supertalls: sup };
}

// ------------------------------------------------------------------------------------------------ the building generator
const STYLES = {
    punched: { fam: 'concrete', floorH: 3.6, bayW: 2.6, w: [0.24, 0.30, 0.80] },
    ribbon: { fam: 'metal', floorH: 3.8, bayW: 1.8, w: [0.03, 0.34, 0.82] },
    curtain: { fam: 'metal', floorH: 4.0, bayW: 1.5, w: [0.04, 0.10, 0.94] },
    resid: { fam: 'concrete', floorH: 3.1, bayW: 3.2, w: [0.30, 0.28, 0.78] },
    slots: { fam: 'concrete', floorH: 4.2, bayW: 4.4, w: [0.38, 0.50, 0.76] },
    shop: { fam: 'concrete', floorH: 5.0, bayW: 4.2, w: [0.05, 0.04, 0.80] },
};
const STRIP_COLS = [KIT.hexLin('#29e7ff'), KIT.hexLin('#ff4fd8'), KIT.hexLin('#ff8a3d'), KIT.hexLin('#e9f3f1')];

// emit one building into the buffers. lot: polar lot; ctx: { buf:{concrete,metal,frame,strip}, signs:[], lights:[], R }
export function emitBuilding(THREE, lot, ctx, over = {}) {
    const R = rng(Math.floor(lot.seed * 1e9) + 7);
    const P = zoneParams(lot.zone);
    const rc = (lot.r0 + lot.r1) / 2, tc = (lot.t0 + lot.t1) / 2;
    const cx = rc * Math.cos(tc), cz = rc * Math.sin(tc);
    const depth = lot.r1 - lot.r0;
    const width = 2 * lot.r0 * Math.sin((lot.t1 - lot.t0) / 2);
    if (width < 10 || depth < 10) return null;
    const yaw = Math.atan2(-Math.cos(tc), -Math.sin(tc));        // local +Z faces the hole
    const dPlaza = Math.hypot(cx - DIVE_C[0], cz - DIVE_C[2]);
    const inPlaza = dPlaza < PLAZA_R + Math.max(width, depth) * 0.5;
    let H = lerp(P.h[0], P.h[1], Math.pow(R(), 1.35));
    if (lot.supertall) H = 300 + R() * 120;
    if (over.height) H = over.height;
    if (inPlaza) H = Math.min(H, 9 + R() * 9);
    const lean = (over.lean ?? (P.lean * (0.6 + 0.8 * R()) + (R() < 0.08 ? 3 + R() * 3 : 0))) * D2R * (inPlaza ? 0 : 1);
    const styleKey = over.style || (H > 150 ? ['curtain', 'ribbon', 'slots', 'punched'][Math.floor(R() * 4)] : ['punched', 'resid', 'ribbon', 'slots', 'curtain'][Math.floor(R() * 5)]);
    const S = STYLES[styleKey];
    const seed = R();
    const litF = lerp(P.lit[0], P.lit[1], R());
    const aT = [seed, litF, 0.25 + R() * 0.6, R() < 0.3 ? 1 : 0];
    const aM = [0, S.floorH, S.bayW, 0], aW = [S.w[0], S.w[1], S.w[2], R()];
    const buf = ctx.buf[S.fam];
    const pos = [cx, STREET_Y, cz];
    const xfFlat = KIT.makeXf(THREE, pos, yaw, 0, 0);
    // ---- podium (plumb): a shop floor + 1..3 floors above; fills the lot
    let podH = 0;
    const hasPod = !inPlaza ? R() < P.pod : true;
    const W = Math.min(width, 90), D = Math.min(depth, 90);
    if (hasPod) {
        podH = inPlaza ? H : 5 + (R() < 0.6 ? 3.8 * (1 + Math.floor(R() * 3)) : 0);
        const shop = { aT: [seed, 0.75, 0.6, 1], aM: [3, 5.0, STYLES.shop.bayW, 0], aW: [...STYLES.shop.w, aW[3]] };
        ctx.buf.concrete.box(xfFlat, -W / 2, -0.5, -D / 2, W / 2, Math.min(5, podH), D / 2, shop, { vBase: 0 });
        if (podH > 5.2) ctx.buf.concrete.box(xfFlat, -W / 2, 5, -D / 2, W / 2, podH, D / 2, { aT, aM: [0, 3.8, 2.6, 0], aW: [0.24, 0.3, 0.78, aW[3]] }, { vBase: 5, top: podH - 5 });
        // shop signs on the faces that front streets (hole side always, plus sides)
        const faces = [['Z', [0, 0, 1]], ['x', [-1, 0, 0]], ['X', [1, 0, 0]], ['z', [0, 0, -1]]];
        for (const [f, n] of faces) {
            if (f !== 'Z' && R() < 0.45) continue;
            const along = f === 'Z' || f === 'z' ? W : D;
            const k = KIT.SHOPS[Math.floor(R() * KIT.SHOPS.length)];
            const sw = Math.min(along * 0.7, 6 + R() * 5), sh = sw / 4;
            const off = (R() - 0.5) * (along - sw) * 0.8;
            const local = f === 'Z' ? [off, 5.2 + sh / 2, D / 2 + 0.25] : f === 'z' ? [off, 5.2 + sh / 2, -D / 2 - 0.25] : f === 'X' ? [W / 2 + 0.25, 5.2 + sh / 2, off] : [-W / 2 - 0.25, 5.2 + sh / 2, off];
            const ry = f === 'Z' ? 0 : f === 'z' ? Math.PI : f === 'X' ? Math.PI / 2 : -Math.PI / 2;
            ctx.signs.push(signAt(THREE, xfFlat, 'shop:' + k[0], local, ry, 0, sw, sh, 4.5 + R() * 3, R() < 0.15 ? 1 : 0));
            const wp = xfFlat.p([local[0] + n[0] * 5, 0, local[2] + n[2] * 5]);
            ctx.lights.push({ x: wp[0], z: wp[2], r: 9 + sw * 0.6, c: KIT.SHOPS.find((s) => s[0] === k[0])[1], a: 0.55 });
            // a blade sign at the corner of the hole-facing face
            if (f === 'Z' && R() < 0.4) {
                const b = KIT.BLADES[Math.floor(R() * KIT.BLADES.length)];
                const bh = 7 + R() * 6, bx = (R() < 0.5 ? -1 : 1) * (W / 2 - 1.2);
                for (const side of [1, -1]) ctx.signs.push(signAt(THREE, xfFlat, 'blade:' + b[0], [bx + side * 0.12, 6.5 + bh / 2, D / 2 + 1.45], side > 0 ? Math.PI / 2 : -Math.PI / 2, 0, bh * 96 / 448, bh, 4.0, 0));
                ctx.buf.frame.box(xfFlat, bx - 0.08, 6.5 - 0.2, D / 2, bx + 0.08, 6.5 + bh + 0.2, D / 2 + 2.9, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] });
            }
        }
    }
    if (inPlaza) return { x: cx, z: cz, H };
    // ---- the tower (leans toward the hole about its base, which is buried in the podium)
    const base = podH > 0 ? podH - 1.5 : -0.5;
    const xf = KIT.makeXf(THREE, pos, yaw, lean, base);
    const tw = Math.min(W * (0.62 + R() * 0.3), 70), td = Math.min(D * (0.55 + R() * 0.35), 60);
    const kindR = R();
    const type = over.type || (lot.supertall ? 'setback' : H > 170 ? (kindR < 0.4 ? 'gradinata' : kindR < 0.7 ? 'setback' : 'slab') : (kindR < 0.25 ? 'gradinata' : kindR < 0.5 ? 'wedge' : kindR < 0.75 ? 'slab' : 'setback'));
    const att = { aT, aM, aW };
    const top = STREET_Y + H;
    const tiers = [];
    if (type === 'slab') {
        const sw = tw, sd = Math.min(td, tw * 0.5 + 6);
        buf.box(xf, -sw / 2, base, -sd / 2, sw / 2, H, sd / 2, att, { vBase: base, top: H - base });
        tiers.push({ x0: -sw / 2, x1: sw / 2, z0: -sd / 2, z1: sd / 2, y: H });
        // vertical fins on the long faces (frames): Sant'Elia's piers
        const nf = Math.max(2, Math.round(sw / 9));
        for (let i = 0; i <= nf; i++) {
            const fx = -sw / 2 + sw * i / nf;
            for (const zz of [sd / 2, -sd / 2]) ctx.buf.frame.box(xf, fx - 0.35, base, zz - 0.6, fx + 0.35, H + 1.5, zz + 0.6, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] });
        }
    } else if (type === 'setback') {
        const n = 3 + Math.floor(R() * 2);
        let y0 = base, w0 = tw, d0 = td;
        for (let i = 0; i < n; i++) {
            const y1 = i === n - 1 ? H : base + (H - base) * (0.45 + 0.55 * (i + 1) / n) * (i === 0 ? 0.8 : 1);
            buf.box(xf, -w0 / 2, y0, -d0 / 2, w0 / 2, y1, d0 / 2, att, { vBase: base, top: H - base });
            tiers.push({ x0: -w0 / 2, x1: w0 / 2, z0: -d0 / 2, z1: d0 / 2, y: y1 });
            y0 = y1; w0 *= 0.72 + R() * 0.12; d0 *= 0.72 + R() * 0.12;
        }
        if (lot.supertall) {   // a mast that disappears into the cloud
            ctx.buf.frame.box(xf, -0.8, H, -0.8, 0.8, H + 60, 0.8, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] });
            for (let k = 1; k < 4; k++) ctx.buf.frame.box(xf, -0.35, H + k * 15, -0.35, 0.35, H + k * 15 + 0.7, 0.35, { aT, aM: [4, 4, 4, 0], aW: [0, 0, 0, 0] });
        }
    } else if (type === 'wedge') {
        const hi = H, lo = H * (0.55 + R() * 0.25);
        const toHole = R() < 0.6;   // the slope falls toward the hole (Crali's tilted roofs)
        buf.box(xf, -tw / 2, base, -td / 2, tw / 2, hi, td / 2, att, { vBase: base, top: hi - base, y1a: toHole ? hi : lo, y1b: toHole ? lo : hi });
        tiers.push({ x0: -tw / 2, x1: tw / 2, z0: -td / 2, z1: td / 2, y: lo, sloped: true });
    } else {   // gradinata: the face toward the hole steps back in terraces; two lift shafts stand in front, bridged
        const n = 4 + Math.floor(R() * 3);
        const stepD = td / (n + 1);
        for (let i = 0; i < n; i++) {
            const y1 = base + (H - base) * (i + 1) / n;
            const z1 = td / 2 - stepD * i;
            buf.box(xf, -tw / 2, i === 0 ? base : base + (H - base) * i / n - 0.01, -td / 2, tw / 2, y1, z1, att, { vBase: base, top: y1 - base });
            tiers.push({ x0: -tw / 2, x1: tw / 2, z0: -td / 2, z1, y: y1, terrace: true });
        }
        const shaftH = H + 14;
        const fz = td / 2 + 7;
        for (const sx of [-tw * 0.3, tw * 0.3]) {
            ctx.buf.frame.box(xf, sx - 2.2, base, fz - 2.2, sx + 2.2, shaftH, fz + 2.2, { aT, aM: [5, shaftH, 4.4, 0], aW: [0, 0, 0, 0] }, { vBase: base, top: shaftH - base });
            for (let k = 1; k <= n; k++) {      // bridges to every terrace
                const by = base + (H - base) * k / n - 3.2;
                const zEnd = td / 2 - stepD * (k - 1);
                if (zEnd >= fz - 2.2) continue;
                ctx.buf.frame.box(xf, sx - 1.4, by, zEnd - 0.5, sx + 1.4, by + 2.8, fz - 2.2 + 0.2, { aT, aM: [0, 2.8, 1.4, 0], aW: [0.05, 0.25, 0.85, 0] });
            }
        }
    }
    // ---- roof: plant, beacons, antenna; signs on some roofs and facades
    const T0 = tiers[tiers.length - 1];
    if (!T0.sloped) {
        const nb = 1 + Math.floor(R() * 3);
        for (let i = 0; i < nb; i++) {
            const bw = 3 + R() * 6, bd = 3 + R() * 6, bh = 2 + R() * 4;
            const bx = lerp(T0.x0 + bw, T0.x1 - bw, R()), bz = lerp(T0.z0 + bd, T0.z1 - bd, R());
            ctx.buf.frame.box(xf, bx - bw / 2, T0.y - 0.2, bz - bd / 2, bx + bw / 2, T0.y + bh, bz + bd / 2, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] });
        }
    }
    if (H > 120) for (const [ex, ez] of [[T0.x0 + 0.6, T0.z0 + 0.6], [T0.x1 - 0.6, T0.z1 - 0.6]]) ctx.buf.frame.box(xf, ex - 0.4, T0.y, ez - 0.4, ex + 0.4, T0.y + 1.2, ez + 0.4, { aT, aM: [4, 4, 4, 0], aW: [0, 0, 0, 0] });
    if (H > 90 && R() < 0.4 && !T0.sloped) ctx.buf.frame.box(xf, -0.3, T0.y, -0.3, 0.3, T0.y + 10 + R() * 25, 0.3, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] });
    // roof supergraphic, read from the dive
    if (!T0.sloped && R() < 0.16) {
        const rw = Math.min(T0.x1 - T0.x0, (T0.z1 - T0.z0) * 2) * 0.8;
        const id = R() < 0.18 ? 'heli' : 'roof:' + Math.floor(R() * 8);
        const asp = id === 'heli' ? 1 : 2;
        ctx.signs.push(signAt(THREE, xf, id, [0, T0.y + 0.08, (T0.z0 + T0.z1) / 2], 0, -Math.PI / 2, rw, rw / asp, 0.7 + R() * 0.5, 0));
    }
    // a big ad on the hole-facing (or a side) facade, mounted on a backing frame
    if (R() < (lot.zone <= 1 ? 0.55 : 0.32) && H > 40) {
        const ads = KIT.AD_COPY;
        const ad = ads[Math.floor(R() * ads.length)];
        const T1 = tiers[0];
        const faceZ = T1.z1;
        const aw = Math.min(T1.x1 - T1.x0 - 4, 18 + R() * 16), ah = aw / 4;
        const ay = lerp(Math.max(base + ah, 22), Math.min(H * 0.55, 80), R());
        const side = R() < 0.65 ? 'Z' : 'X';
        if (side === 'Z') {
            ctx.buf.frame.box(xf, -aw / 2 - 0.6, ay - ah / 2 - 0.6, faceZ, aw / 2 + 0.6, ay + ah / 2 + 0.6, faceZ + 0.5, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] }, { faces: 'xXzZt' });
            ctx.signs.push(signAt(THREE, xf, 'ad:' + ad.id, [0, ay, faceZ + 0.56], 0, 0, aw, ah, 2.2 + R() * 1.2, R() < 0.1 ? 2 : 0));
        } else {
            const fx = T1.x1, aw2 = Math.min(T1.z1 - T1.z0 - 4, aw), ah2 = aw2 / 4;
            if (aw2 > 8) {
                ctx.buf.frame.box(xf, fx, ay - ah2 / 2 - 0.6, -aw2 / 2 - 0.6, fx + 0.5, ay + ah2 / 2 + 0.6, aw2 / 2 + 0.6, { aT, aM: [2, 4, 4, 0], aW: [0, 0, 0, 0] });
                ctx.signs.push(signAt(THREE, xf, 'ad:' + ad.id, [fx + 0.56, ay, 0], Math.PI / 2, 0, aw2, ah2, 2.2 + R() * 1.2, 0));
            }
        }
    }
    // a Futurist supergraphic painted on a side wall (floodlit)
    if (R() < 0.22 && H > 50) {
        const T1 = tiers[0];
        const len = Math.min(T1.z1 - T1.z0 - 2, 46), gh = len / 6;
        if (len > 12) {
            const gy = lerp(base + gh + 4, Math.min(H * 0.8, 120), R());
            const sx = R() < 0.5 ? -1 : 1;
            ctx.signs.push(signAt(THREE, xf, 'fut:' + Math.floor(R() * KIT.FUTURIST.length), [sx * (T1.x1 + 0.12), gy, (T1.z0 + T1.z1) / 2], sx > 0 ? Math.PI / 2 : -Math.PI / 2, 0, len, gh, 0.9 + R() * 0.5, 0));
        }
    }
    // neon edge strips: vertical lines on the hole-facing corners (they converge on the hole from the dive)
    if (R() < (lot.zone <= 1 ? 0.5 : 0.22)) {
        const c = STRIP_COLS[Math.floor(R() * STRIP_COLS.length)];
        const T1 = tiers[0];
        const st = { aT: [c[0], c[1], c[2], R()], aM: [R() < 0.5 ? 1 : 0, 3.2 + R() * 2, 0.35 + R() * 0.4, R()], aW: [0, 0, 0, 0] };
        for (const ex of [T1.x0, T1.x1]) ctx.buf.strip.box(xf, ex - 0.18, base, T1.z1 - 0.18, ex + 0.18, T1.y + 0.4, T1.z1 + 0.18, st, { vBase: T1.y + 0.4 });
        for (const t of tiers) if (t.y < H - 1 || t.terrace) ctx.buf.strip.box(xf, t.x0, t.y - 0.1, t.z1 - 0.15, t.x1, t.y + 0.25, t.z1 + 0.15, st);
    }
    return { x: cx, z: cz, H, type };
}
// a sign quad placed in a building's frame: local position, yaw (about local Y) then pitch (about local X)
export function signAt(THREE, xf, id, local, ry, rx, w, h, gain, flicker) {
    const p = xf.p(local);
    const q = xf.q.clone().multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, 0, 'YXZ')));
    return { id, pos: p, quat: q, w, h, gain, flicker, power: hash1(p[0] * 0.37 + p[2] * 0.73) };
}

// ------------------------------------------------------------------------------------------------ the ground
function ringSector(THREE, ra, rb, t0, t1, y0, y1, segs) {
    // a closed annular-sector slab: top, outer, inner and two radial sides, each quad wound to face OUT (normal given)
    const P = [], NN = [], I = [];
    const n = Math.max(2, segs);
    const ring = (r, y) => { const a = []; for (let i = 0; i <= n; i++) { const t = t0 + (t1 - t0) * i / n; a.push([r * Math.cos(t), y, r * Math.sin(t)]); } return a; };
    const ti = ring(ra, y1), to = ring(rb, y1), bi = ring(ra, y0), bo = ring(rb, y0);
    const quad = (a, b, c, d, nrm) => {
        // (C-B)x(A-B) is three's front-face normal; flip the order if it disagrees with the wanted normal
        const cb = [c[0] - b[0], c[1] - b[1], c[2] - b[2]], ab = [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
        const g = [cb[1] * ab[2] - cb[2] * ab[1], cb[2] * ab[0] - cb[0] * ab[2], cb[0] * ab[1] - cb[1] * ab[0]];
        if (g[0] * nrm[0] + g[1] * nrm[1] + g[2] * nrm[2] < 0) [a, b, c, d] = [d, c, b, a];
        const k = P.length / 3; P.push(...a, ...b, ...c, ...d); for (let j = 0; j < 4; j++) NN.push(...nrm);
        I.push(k, k + 1, k + 2, k, k + 2, k + 3);
    };
    for (let i = 0; i < n; i++) {
        const tm = t0 + (t1 - t0) * (i + 0.5) / n, rad = [Math.cos(tm), 0, Math.sin(tm)];
        quad(ti[i], to[i], to[i + 1], ti[i + 1], [0, 1, 0]);
        quad(bo[i], to[i], to[i + 1], bo[i + 1], rad);
        quad(bi[i + 1], ti[i + 1], ti[i], bi[i], [-rad[0], 0, -rad[2]]);
    }
    quad(bi[0], ti[0], to[0], bo[0], [Math.sin(t0), 0, -Math.cos(t0)]);
    quad(bo[n], to[n], ti[n], bi[n], [-Math.sin(t1), 0, Math.cos(t1)]);
    return { P, N: NN, I };
}
function buildBlocks(THREE, blocks) {
    const P = [], N = [], I = [];
    for (const b of blocks) {
        const segs = Math.ceil((b.t1 - b.t0) * b.rb / 12);
        const s = ringSector(THREE, b.ra, b.rb, b.t0, b.t1, STREET_Y - 0.3, STREET_Y + 0.16, segs);
        const k = P.length / 3;
        P.push(...s.P); N.push(...s.N); I.push(...s.I.map((i) => i + k));
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
    const uv = new Float32Array(P.length / 3 * 2);
    for (let i = 0; i < P.length / 3; i++) { uv[i * 2] = P[i * 3]; uv[i * 2 + 1] = P[i * 3 + 2]; }
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(new THREE.Uint32BufferAttribute(I, 1));
    g.computeBoundingSphere();
    return g;
}

// street lamps along avenues and ring roads (both kerbs), as positions + their light pools
function planLamps() {
    const L = [];
    const SP = 34;
    const avs = [];
    for (const a of AVENUES_MAIN) avs.push({ a, r0: HOLE.ringRoad[1] + 6, r1: CITY_R });
    for (const a of AVENUES_SECOND) avs.push({ a, r0: SECOND_START + 12, r1: CITY_R });
    for (const v of avs) for (let r = v.r0; r < v.r1; r += SP) for (const s of [-1, 1]) {
        const off = s * (AVENUE_W / 2 + 0.8);
        const x = r * Math.cos(v.a) - off * Math.sin(v.a), z = r * Math.sin(v.a) + off * Math.cos(v.a);
        // the arm reaches over the road: local -Z of the lamp points toward the avenue centre line
        const ax = -Math.sin(v.a) * -s, az = Math.cos(v.a) * -s;      // direction to the centre line
        L.push({ x, z, yaw: Math.atan2(-ax, -az), r: 14 });
    }
    for (const g of RINGS.concat([{ r: 40, w: 20 }])) {
        const n = Math.round(2 * Math.PI * g.r / SP);
        for (let i = 0; i < n; i++) for (const s of g.r === 40 ? [1] : [-1, 1]) {
            const t = (i + 0.5) / n * 2 * Math.PI;
            const rr = g.r + s * (g.w / 2 + 0.8);
            if (KIT.nearestAvenue(t, rr).d !== 1e9 && Math.abs(KIT.nearestAvenue(t, rr).d) < AVENUE_W / 2 + 3) continue;
            const x = rr * Math.cos(t), z = rr * Math.sin(t);
            const ax = -Math.cos(t) * s, az = -Math.sin(t) * s;
            L.push({ x, z, yaw: Math.atan2(-ax, -az), r: 14 });
        }
    }
    return L;
}

// traffic: ring roads (two lanes each way) + avenues (two lanes each way)
function planTraffic() {
    const R = rng(77);
    const paths = [];
    for (const g of RINGS.concat([{ r: 40, w: 20 }])) {
        const lanes = g.r === 40 ? [-6.5, -3, 3, 6.5] : [-6, -2.5, 2.5, 6];
        for (const ln of lanes) {
            const dir = ln < 0 ? -1 : 1;
            const r = g.r + ln;
            const spacing = g.r === 40 ? 18 : 55 + R() * 30;
            const n = Math.max(3, Math.floor(2 * Math.PI * r / spacing));
            for (let i = 0; i < n; i++) paths.push({ type: 'ring', r, dir, speed: (g.r === 40 ? 13 : 15) + R() * 6, phase: (i + R() * 0.6) / n * 2 * Math.PI });
        }
    }
    const avs = AVENUES_MAIN.map((a) => ({ a, r0: HOLE.ringRoad[1], r1: CITY_R })).concat(AVENUES_SECOND.map((a) => ({ a, r0: SECOND_START, r1: CITY_R })));
    for (const v of avs) for (const ln of [-8.5, -4.5, 4.5, 8.5]) {
        const dir = ln < 0 ? 1 : -1;
        const span = v.r1 - v.r0;
        const n = Math.floor(span / (48 + R() * 30));
        for (let i = 0; i < n; i++) paths.push({ type: 'av', th: v.a, r0: v.r0, r1: v.r1, lane: ln, dir, speed: 14 + R() * 7, phase: (i + R() * 0.7) / n });
    }
    return paths;
}

// the far skyline ring beyond the city: simple tall blocks for silhouette and glitter (fogged)
function emitFarSkyline(THREE, buf) {
    const R = rng(31337);
    for (let i = 0; i < 420; i++) {
        const t = R() * Math.PI * 2, r = lerp(FAR_R[0], FAR_R[1], Math.sqrt(R()));
        const w = 20 + R() * 50, d = 20 + R() * 40, h = 30 + Math.pow(R(), 2) * 220;
        const xf = KIT.makeXf(THREE, [r * Math.cos(t), STREET_Y, r * Math.sin(t)], Math.atan2(-Math.cos(t), -Math.sin(t)), 0, 0);
        buf.box(xf, -w / 2, -1, -d / 2, w / 2, h, d / 2, { aT: [R(), 0.25 + R() * 0.2, 0.5, 0], aM: [0, 3.8, 2.4, 0], aW: [0.2, 0.3, 0.8, R()] });
    }
}

// ------------------------------------------------------------------------------------------------ build
export async function build(THREE, opts = {}) {
    const t0 = performance.now();
    const K = opts.kit || await KIT.makeKit(THREE, opts);
    const group = new THREE.Group(); group.name = 'set:city';
    const plan = planCity(opts.seed || 1909);
    const lamps = planLamps();
    // ---- buildings (into merged buffers) and their signs + light spill
    const buf = { concrete: new KIT.GeoBuf(), metal: new KIT.GeoBuf(), frame: new KIT.GeoBuf(), strip: new KIT.GeoBuf() };
    const bctx = { buf, signs: [], lights: [] };
    // nearer lots first (front-to-back for the common camera positions: fewer overdrawn fragments)
    const lots = plan.lots.slice().sort((a, b) => (a.r0 - b.r0));
    const built = [];
    for (const l of lots) { const b = emitBuilding(THREE, l, bctx); if (b) built.push(b); }
    const farBuf = new KIT.GeoBuf();
    emitFarSkyline(THREE, farBuf);
    // ---- the hole (its own module) — planned now so its lights land in the light map
    let holeMod = null;
    if (opts.hole !== false) holeMod = await import('./hole.js');
    // ---- the light map: lamp pools, shop spill, ad glow, traffic glow on the avenues, the hole
    const lightDraws = [(ctx, toPx, s) => {
        for (const l of lamps) {
            const ax = Math.sin(l.yaw) * -2.4, az = Math.cos(l.yaw) * -2.4;
            KIT.lmPool(ctx, toPx, s, l.x + ax, l.z + az, l.r, '#ff8a3d', 0.85);
        }
        for (const l of bctx.lights) KIT.lmPool(ctx, toPx, s, l.x, l.z, l.r, KIT.PAL[l.c] || '#e9f3f1', l.a);
        // the dive's crossing: a lit piazza (the light at Crali's vanishing point)
        KIT.lmPool(ctx, toPx, s, DIVE_C[0], DIVE_C[2], 40, '#ffb070', 0.9);
        KIT.lmPool(ctx, toPx, s, DIVE_C[0], DIVE_C[2], 18, '#fff0dc', 1.0);
        for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2; KIT.lmPool(ctx, toPx, s, DIVE_C[0] + Math.cos(a) * 26, DIVE_C[2] + Math.sin(a) * 26, 9, i % 2 ? '#29e7ff' : '#ff4fd8', 0.35); }
        for (const sg of bctx.signs) if (sg.id.startsWith('ad:') && sg.pos[1] < STREET_Y + 60) KIT.lmPool(ctx, toPx, s, sg.pos[0], sg.pos[2], 26, '#7aa8ff', 0.10);
    }];
    if (holeMod) lightDraws.push(holeMod.drawHoleLights);
    KIT.makeLightMap(K, lightDraws);
    // ---- materials (after the light map: they sample it)
    K.mat = K.mat || {
        concrete: KIT.facadeMaterial(K, 'concrete'), metal: KIT.facadeMaterial(K, 'metal'), frame: KIT.frameMaterial(K),
        strip: KIT.stripMaterial(K), ground: KIT.groundMaterial(K), paving: KIT.pavingMaterial(K, 'paving'), marble: KIT.pavingMaterial(K, 'marble'),
    };
    const M = K.mat;
    const meshes = {};
    const addMesh = (name, geo, mat, ud = {}) => { const m = new THREE.Mesh(geo, mat); m.name = name; Object.assign(m.userData, ud); group.add(m); meshes[name] = m; return m; };
    addMesh('uf_towers_concrete', buf.concrete.build(THREE), M.concrete, { assembly: 'uf_city' });
    addMesh('uf_towers_metal', buf.metal.build(THREE), M.metal, { assembly: 'uf_city' });
    addMesh('uf_frames', buf.frame.build(THREE), M.frame, { assembly: 'uf_city' });
    if (buf.strip.count) addMesh('uf_strips', buf.strip.build(THREE), M.strip, { assembly: 'uf_city' });
    addMesh('uf_far', farBuf.build(THREE), M.concrete, { assembly: 'uf_city' });
    // ---- ground: the street disc (with the hole's opening) and the raised blocks
    const gGeo = new THREE.RingGeometry(HOLE.rimR, FAR_R[1] + 200, 160, 24);
    gGeo.rotateX(-Math.PI / 2); gGeo.translate(0, STREET_Y, 0);
    { const p = gGeo.getAttribute('position'); const uv = gGeo.getAttribute('uv'); for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i), p.getZ(i)); }
    addMesh('uf_street', gGeo, M.ground, { assembly: 'uf_city' });
    addMesh('uf_blocks', buildBlocks(THREE, plan.blocks), M.paving, { assembly: 'uf_city' });
    // ---- signs, lamps, traffic, rain, clouds, sky
    // ---- the city's own light (lit materials see ONLY these, not the hole's point lights or the conductor's: each
    // extra light costs every facade fragment; parts.setLights(list) changes the set)
    const hemi = new THREE.HemisphereLight(0x1d2a3a, 0x2a160c, 0.55); hemi.name = 'uf_hemi'; group.add(hemi);
    const moon = new THREE.DirectionalLight(0x8fa6c8, 0.12); moon.position.set(-300, 900, -200); moon.name = 'uf_skyglow'; group.add(moon);
    const atlas = KIT.makeSignAtlas(K);
    let hole = null;
    if (holeMod) {
        hole = await holeMod.build(THREE, { ...opts, kit: K, atlas, withCity: true, cityLights: [hemi, moon] });
        group.add(hole.group);
    }
    const plaza = makePlazaScreen(THREE, K);
    group.add(plaza.mesh, plaza.rim);
    const signs = KIT.makeSignsMesh(K, atlas, bctx.signs.concat(hole ? hole.parts.citySigns || [] : []));
    group.add(signs);
    const lampMesh = KIT.makeLamps(K, lamps).mesh; group.add(lampMesh);
    const cityLit = [M.concrete, M.metal, M.frame, M.ground, M.paving, lampMesh.material];
    const setLights = (list) => { const ln = K.T.lights(list); for (const m of cityLit) { m.lightsNode = ln; m.needsUpdate = true; } };
    setLights([hemi, moon]);
    const traffic = KIT.makeTraffic(K, planTraffic()); group.add(traffic.mesh);
    const rain = KIT.makeRain(K, { count: opts.rainCount || 26000 }); group.add(rain.mesh);
    const clouds = KIT.makeClouds(K); group.add(clouds.group);
    const sky = KIT.makeSky(K); group.add(sky.mesh);
    // ---- light for lit materials (the conductor may add its own): a dim overcast hemisphere
    let lastCam = null, lastT = null;
    const _v = new THREE.Vector3();
    const parts = {
        kit: K, uniforms: K.U, fogNode: K.fog.fogNode, fogFactor: K.fog.factor, fogColor: K.fog.color,
        hole, billboards: hole ? hole.parts.billboards : [], signs, traffic: traffic.mesh, rain: rain.mesh, clouds: clouds.group, sky: sky.mesh,
        lamps: lampMesh, meshes, lights: { hemi, moon }, setLights, plan, atlas, plazaScreen: plaza,
        // set the scene's atmosphere (fog + background); the conductor can also do this by hand
        applyAtmosphere(scene) { scene.fogNode = K.fog.fogNode; scene.background = new THREE.Color(0x020306); },
        // Crali's light from the vanishing point: faces turned toward `pos` light up (keep it on the post's focal)
        setFocal(pos, o = {}) { K.U.focalPos.value.set(...pos); if (o.gain !== undefined) K.U.focalGain.value = o.gain;
            if (o.radius !== undefined) K.U.focalR.value = o.radius; if (o.color) K.U.focalCol.value.set(o.color); },
    };
    const update = (t, state = {}) => {
        K.U.time.value = t;
        const cam = state.camera || globalThis._c;
        if (state.camVel) K.U.camVel.value.set(...state.camVel);
        else if (cam) {   // fallback: finite difference of the camera between calls (reset on cuts)
            if (lastCam && lastT !== null && t > lastT && t - lastT < 0.2) {
                _v.copy(cam.position).sub(lastCam).divideScalar(t - lastT);
                if (_v.length() < 400) K.U.camVel.value.copy(_v);
            } else K.U.camVel.value.set(0, 0, 0);
            lastCam = (lastCam || new THREE.Vector3()).copy(cam.position); lastT = t;
        }
        if (cam) { clouds.update(cam); sky.update(cam); }
        if (hole) hole.update(t, state);
        plaza.update(t);
    };
    const dispose = () => {
        if (hole) hole.dispose();
        group.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
        for (const m of Object.values(K.mat)) m.dispose?.();
        for (const m of [signs.material, lampMesh.material, traffic.mesh.material, rain.mesh.material, sky.mesh.material, plaza.mesh.material]) m.dispose();
        clouds.sheets[0].material.dispose();
        atlas.texture.dispose(); plaza.texture.dispose(); K.lightMap?.dispose();
        for (const tx of [K.tex.noise, K.tex.env]) tx.dispose();
    };
    const cams = {
        dive_clouds: { pos: diveCam(4).pos, target: diveCam(4).target, fov: diveCam(4).fov },
        dive_crali: { pos: diveCam(16).pos, target: diveCam(16).target, fov: diveCam(16).fov },
        dive_canyon: { pos: diveCam(30).pos, target: diveCam(30).target, fov: diveCam(30).fov },
        dive_end: { pos: diveCam(40.8).pos, target: diveCam(40.8).target, fov: diveCam(40.8).fov },
        avenue: { pos: [260, STREET_Y + 9, 255], target: [0, STREET_Y + 30, 0], fov: 50 },
        skyline: { pos: [-520, STREET_Y + 160, 420], target: [0, STREET_Y + 90, 0], fov: 45 },
    };
    console.log(`[city] built ${built.length} buildings, ${bctx.signs.length} signs, ${lamps.length} lamps in ${(performance.now() - t0).toFixed(0)} ms`);
    return { group, parts, update, dispose, cams };
}

// ------------------------------------------------------------------------------------------------ the plaza screen
// A circular LED floor at the dive's crossing: the light at Crali's vanishing point. Default content is Balla's sun
// (rays and rings turning slowly) with a ring of slogans; parts.plazaScreen.setCanvas(drawFn) replaces it.
export function drawPlazaSun(ctx, W, H, t = 0) {
    const cx = W / 2, cy = H / 2, R = W / 2;
    ctx.save();
    ctx.fillStyle = '#05040a'; ctx.fillRect(0, 0, W, H);
    const rays = 24;
    for (let i = 0; i < rays; i++) {
        const a0 = (i / rays) * Math.PI * 2 + t * 0.12, a1 = a0 + Math.PI / rays;
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, R * 0.98, a0, a1); ctx.closePath();
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
        const c = i % 3 === 0 ? ['#fff4dc', '#ff8a3d'] : i % 3 === 1 ? ['#ffe2b0', '#b81f66'] : ['#e9f3f1', '#0d3644'];
        g.addColorStop(0, c[0]); g.addColorStop(0.55, c[1]); g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g; ctx.fill();
    }
    for (let k = 1; k <= 5; k++) {
        ctx.beginPath(); ctx.arc(cx, cy, R * (0.16 * k + 0.04 * Math.sin(t * 0.7 + k)), 0, Math.PI * 2);
        ctx.lineWidth = W * 0.006; ctx.strokeStyle = k % 2 ? '#05040a' : '#ffcf8a'; ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(cx, cy, R * 0.1, 0, Math.PI * 2); ctx.fillStyle = '#fffaf0'; ctx.fill();
    // a ring of slogans round the rim, read from above
    const words = 'SUPERINTELLIGENCE BY Q3  /  TRUST THE MODEL  /  ALIGNED  /  VELOCITA  /  ACCELERATE  /  YOUR NEW EMPLOYEE  /  ';
    ctx.font = `${Math.round(W * 0.038)}px "Rajdhani"`; ctx.fillStyle = '#fff1d6'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const chars = [...words];
    for (let i = 0; i < chars.length; i++) {
        const a = (i / chars.length) * Math.PI * 2 - t * 0.05;
        ctx.save(); ctx.translate(cx + Math.cos(a) * R * 0.9, cy + Math.sin(a) * R * 0.9); ctx.rotate(a + Math.PI / 2); ctx.fillText(chars[i], 0, 0); ctx.restore();
    }
    ctx.restore();
}
const frameAttrs = KIT.frameAttrs;
function makePlazaScreen(THREE, K) {
    const R = 34, PX = 1024;
    const { canvas, ctx } = KIT.makeCanvas(PX, PX);
    drawPlazaSun(ctx, PX, PX, 0);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = true; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.anisotropy = 8; tex.needsUpdate = true;
    const geo = new THREE.CircleGeometry(R, 96); geo.rotateX(-Math.PI / 2);
    const gain = K.T.uniform(1.6);
    const mat = new THREE.MeshBasicNodeMaterial();
    mat.name = 'uf_plaza_screen';
    {
        const { texture, uv, vec2, float, fract, step, smoothstep, mix, max, fwidth } = K.T;
        const u = uv();
        const c = texture(tex, vec2(u.x, float(1).sub(u.y)));
        const cells = u.mul(PX / 3); const g = fract(cells);
        const fw = max(fwidth(cells.x), fwidth(cells.y));
        const led = mix(step(0.15, g.x).mul(step(0.15, g.y)).mul(0.45).add(0.55), float(0.8), smoothstep(0.25, 0.7, fw));
        const on = smoothstep(0.62, 0.66, K.U.power);
        mat.colorNode = c.rgb.mul(gain).mul(led).mul(on).mul(K.U.neon);
    }
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(DIVE_C[0], STREET_Y + 0.035, DIVE_C[2]);
    mesh.name = 'uf_plaza_screen';
    // its kerb: a dark metal ring the screen is set into
    const rim = new THREE.Mesh(frameAttrs(THREE, new THREE.TorusGeometry(R + 0.25, 0.3, 6, 96)), K.mat.frame);
    rim.rotation.x = Math.PI / 2; rim.position.set(DIVE_C[0], STREET_Y + 0.05, DIVE_C[2]); rim.name = 'uf_plaza_rim';
    mesh.userData.assembly = 'uf_plaza'; rim.userData.assembly = 'uf_plaza';
    let last = -1, custom = false;
    return {
        mesh, rim, canvas, ctx, texture: tex, gain, px: [PX, PX],
        setCanvas(drawFn) { custom = true; drawFn(ctx, PX, PX); tex.needsUpdate = true; },
        reset() { custom = false; },
        // the default sun turns slowly; redrawn at 10 fps (each redraw uploads 4 MB)
        update(t) { if (custom) return; const f = Math.floor(t * 10); if (f === last) return; last = f; drawPlazaSun(ctx, PX, PX, t); tex.needsUpdate = true; },
    };
}

// ------------------------------------------------------------------------------------------------ THE DIVE
// diveCam(t), t = song seconds 0..40.8: Tullio Crali's "Incuneandosi nell'abitato" (1939). Falling out of the low
// rain clouds over the crossing of grand avenue 45° and the first ring road (the dive's street), a nose-dive that
// circles that crossing ever tighter and faster (the spiral) while the towers radiate from the vanishing point below,
// down between the towers, then the pull-out: levelling into the avenue at ~15 m, flying toward the hole, which ends
// the shot framed at the avenue's end (its billboards across the void, the pillar of light). Returns
// { pos, target, fov, roll, up } — use applyCam(THREE, camera, diveCam(t)).
const DIVE = {
    // helix around the crossing: [t, radius, angle (deg), height above street]
    helix: [
        { t: 0, v: [118, -430, 508] }, { t: 6, v: [104, -398, 430] }, { t: 10, v: [92, -372, 352] },
        { t: 15, v: [80, -338, 322] }, { t: 20, v: [66, -300, 292] }, { t: 24, v: [44, -230, 222] },
        { t: 28, v: [24, -128, 148] }, { t: 31, v: [12, -20, 92] }, { t: 33, v: [7, 45, 58] },
    ],
    fov: [{ t: 0, v: [64] }, { t: 9, v: [70] }, { t: 20, v: [72] }, { t: 30, v: [80] }, { t: 34, v: [74] }, { t: 40.8, v: [56] }],
    roll: [{ t: 0, v: [0] }, { t: 12, v: [-6] }, { t: 22, v: [5] }, { t: 28, v: [-9] }, { t: 33, v: [0] }, { t: 40.8, v: [0] }],
};
const DEG = Math.PI / 180;
function helixAt(t) {
    const [R, phd, h] = keyed(DIVE.helix, Math.min(t, 33), smoother);
    const ph = (phd + 135) * DEG;      // +135: the helix's last tangent points along the avenue toward the hole
    return [DIVE_C[0] + R * Math.cos(ph), STREET_Y + h, DIVE_C[2] + R * Math.sin(ph)];
}
export function diveCam(t) {
    t = Math.max(0, Math.min(40.8, t));
    const fov = keyed(DIVE.fov, t)[0];
    const roll = keyed(DIVE.roll, t)[0] * DEG;
    const inward = [-Math.cos(DIVE_AV), 0, -Math.sin(DIVE_AV)];
    let pos;
    if (t <= 33) pos = helixAt(t);
    else {
        // pull-out: cubic Hermite from the helix (matching its velocity) to the avenue's end point
        const p0 = helixAt(33), v0 = helixAt(33).map((x, i) => (x - helixAt(32.9)[i]) / 0.1);
        const rEnd = 104;
        const p1 = [DIVE_C[0] + inward[0] * (RINGS[0].r - rEnd), STREET_Y + 15, DIVE_C[2] + inward[2] * (RINGS[0].r - rEnd)];
        const v1 = [inward[0] * 4, -0.6, inward[2] * 4];
        const T = 7.8, u = (t - 33) / T;
        const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u, h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
        pos = p0.map((_, i) => h00 * p0[i] + h10 * T * v0[i] + h01 * p1[i] + h11 * T * v1[i]);
    }
    // where she looks: early, ahead and down into the murk; then the crossing (steeper than the line to it: Crali's
    // nadir); in the pull-out, the hole at the avenue's end
    const C = DIVE_C;
    const toC = [C[0] - pos[0], 0, C[2] - pos[2]];
    const ahead = [pos[0] + inward[0] * 240, STREET_Y, pos[2] + inward[2] * 240];
    const nadir = [pos[0] + toC[0] * 0.55, STREET_Y, pos[2] + toC[2] * 0.55];
    const kA = smooth((t - 3) / 8);              // 0 = ahead into the murk, 1 = the crossing below
    let tgt = ahead.map((a, i) => lerp(a, nadir[i], kA));
    const holeT = [0, STREET_Y + 26, 0];
    const kD = smoother((t - 33.5) / 6.0);
    // blend DIRECTIONS (not points) so the pull-out rotates smoothly from nadir to level
    const dA = norm(sub(tgt, pos)), dB = norm(sub(holeT, pos));
    const d = norm(dA.map((a, i) => lerp(a, dB[i], kD)));
    const target = pos.map((p, i) => p + d[i] * 100);
    // image-up: the direction of horizontal travel while looking down (an aviator's view), world-up when level
    const pa = t <= 33 ? helixAt(Math.max(0, t - 0.05)) : pos, pb = t <= 33 ? helixAt(t + 0.05) : pos;
    let hv = [pb[0] - pa[0], 0, pb[2] - pa[2]];
    if (Math.hypot(hv[0], hv[2]) < 1e-4 || t > 33) hv = inward.slice();
    hv = norm(hv);
    const kU = smooth((d[1] + 0.55) / 0.5);      // looking down -> travel-up; looking level -> world up
    const up = norm(hv.map((h, i) => lerp(h, i === 1 ? 1 : 0, kU)));
    return { pos, target, fov, roll, up };
}
// the dive's focal point (for the post's sun-cones AND the city's focal light): the crossing below, then the hole
export function diveFocal(t) {
    const k = smoother((t - 33.5) / 5.5);
    return [DIVE_C[0] * (1 - k), lerp(STREET_Y + 18, 26, k), DIVE_C[2] * (1 - k)];
}
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const norm = (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
