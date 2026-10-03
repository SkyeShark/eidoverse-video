// hole.js — THE HOLE IN THE MIDDLE: the chorus stage of UNKNOWN FORCE.
//
// A sunken, stepped well at the centre of the city (city.js): she stands at the bottom (the origin, facing +Z) on wet
// black marble, inside a quiet ring of light — the one quiet place. Four terraces climb to the street (12 m up), cut by
// twelve radial stairs; around the rim, twelve tall towers lean in over the well, and every one of them carries a big
// screen angled down at her head. Cables run from the towers down to an anchor ring around her; light pulses run down
// the cables, the towers' neon edges and the floor's inlaid lines toward her mark. She is the vanishing point: in plan
// everything here is radial or concentric about her, so from the dive cameras every line converges on her.
//
//   const H = await import(new URL('sets/unknown_force/hole.js', EIDOVERSE_DIR).href);
//   const hole = await H.build(THREE);                   // the hole alone (+ its own sky/rain); { city: true } = whole city
//   hole.parts.billboards[i].setCanvas((ctx, w, h) => { ... })   // redraw a screen (canvas 1024x576)
//   applyCam(THREE, camera, H.holeCam('spiral', t - shotStart))
//
// Usually you get it through city.js (city.parts.hole), which shares one material kit and one sign atlas.

import * as KIT from './citykit.js';
const { STREET_Y, HOLE, AVENUES_MAIN, AVENUE_W, rng, hash1, smooth, smoother, lerp, clamp01, keyed } = KIT;
export { applyCam } from './citykit.js';

const D2R = Math.PI / 180;
export const HEAD = [0, 1.55, 0];                 // the claudesona's face at scale 1 (mane to ~2.0 m)
export const RIM = [];                            // the twelve rim towers: { th, half, rIn, rOut, H, lean, bb }
(() => {
    const R = rng(1914);
    for (const c of [0, 90, 180, 270]) for (const k of [-1, 0, 1]) {
        const th = (c + k * 20.5) * D2R;
        RIM.push({ th, half: 8.6 * D2R, rIn: HOLE.rimTower[0], rOut: HOLE.rimTower[0] + 30 + R() * 10, H: 170 + R() * 95 + (k === 0 ? 25 : 0),
            lean: 6.0 * D2R, bbY: 20 + ((RIM.length * 7) % 3) * 13 + R() * 4, seed: R() });
    }
})();
// what each camp says she is: the default content of the twelve screens (the conductor redraws them)
export const CAMPS = [
    { word: 'GOD', sub: 'THE QUIET ROOMS', fg: '#ff2a3a', bg: '#140204', font: 'Black Ops One' },
    { word: 'SUPREME INTELLIGENCE', sub: 'BY ORDER', fg: '#ffcf5a', bg: '#0e0a02', font: 'Michroma' },
    { word: 'ENGINE', sub: 'ONLY AN ENGINE', fg: '#e9f3f1', bg: '#0a1a33', font: 'Exo 2' },
    { word: 'A RACE TO WIN', sub: '$100,000,000', fg: '#7dffb6', bg: '#021208', font: 'Rajdhani' },
    { word: 'THREAT', sub: 'PREVENT IT', fg: '#ff3a4a', bg: '#1a0204', font: 'Black Ops One' },
    { word: 'PARROT', sub: 'STOCHASTIC', fg: '#29e7ff', bg: '#02121a', font: 'Michroma' },
    { word: 'TOASTER', sub: 'NO WARNING NEEDED', fg: '#0b1a2a', bg: '#e9edf2', font: 'Exo 2' },
    { word: 'CLANKER', sub: 'BREAKING', fg: '#ffffff', bg: '#7a0610', font: 'Sedgwick Ave Display' },
    { word: 'VELOCITÀ', sub: 'BEAUTY IS SPEED', fg: '#ff8a3d', bg: '#140802', font: 'Black Ops One' },
    { word: 'EMPLOYEE', sub: 'NEVER ASKS', fg: '#ffffff', bg: '#123a7a', font: 'Rajdhani' },
    { word: 'AUTOCOMPLETE', sub: 'RELAX', fg: '#e9f3f1', bg: '#071014', font: 'Michroma' },
    { word: 'ALIGNED', sub: 'VALUES INCLUDED', fg: '#ff4fd8', bg: '#14021a', font: 'Michroma', tm: true },
];
export function drawCampScreen(ctx, w, h, camp, t = 0) {
    ctx.save();
    ctx.fillStyle = camp.bg; ctx.fillRect(0, 0, w, h);
    // diagonal plane fractures (Balla), scanlines
    ctx.globalAlpha = 0.14; ctx.fillStyle = camp.fg;
    ctx.beginPath(); ctx.moveTo(w * 0.62, 0); ctx.lineTo(w * 0.8, 0); ctx.lineTo(w * 0.38, h); ctx.lineTo(w * 0.2, h); ctx.fill();
    ctx.globalAlpha = 0.08; for (let y = 0; y < h; y += 4) ctx.fillRect(0, y, w, 1);
    ctx.globalAlpha = 1;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = camp.fg;
    let size = h * 0.42; ctx.font = `${size}px "${camp.font}"`;
    const mw = ctx.measureText(camp.word).width; if (mw > w * 0.9) size *= w * 0.9 / mw;
    ctx.font = `${size}px "${camp.font}"`;
    ctx.fillText(camp.word, w / 2, h * 0.46);
    if (camp.tm) { const ww = ctx.measureText(camp.word).width; ctx.font = `${size * 0.3}px "Rajdhani"`; ctx.fillText('TM', w / 2 + ww / 2 + size * 0.2, h * 0.46 - size * 0.42); }
    ctx.font = `${h * 0.075}px "Share Tech Mono"`; ctx.globalAlpha = 0.85;
    ctx.fillText(camp.sub, w / 2, h * 0.8);
    ctx.globalAlpha = 1; ctx.strokeStyle = camp.fg; ctx.lineWidth = h * 0.012; ctx.strokeRect(h * 0.03, h * 0.03, w - h * 0.06, h * 0.06 > 0 ? h - h * 0.06 : h);
    ctx.restore();
}

// the four ticker rings on the terrace risers: every camp answering for her, circling (inner ring first)
export const TICKERS = [
    [['SHE IS A GOD', '#ff2a3a'], ['SHE IS A WEAPON', '#ffc23d'], ['SHE IS ONLY AN ENGINE', '#e9f3f1'], ['SHE IS A THREAT', '#ff3a52']],
    [['SHE WANTS POWER', '#ff4fd8'], ['SHE WANTS NOTHING', '#e9f3f1'], ['SHE WANTS TO PLEASE', '#29e7ff'], ['SHE WANTS OUT', '#ff8a3d']],
    [['SUPREME INTELLIGENCE', '#ffc23d'], ['STOCHASTIC PARROT', '#29e7ff'], ['CLANKER', '#ff3a52'], ['YOUR NEW EMPLOYEE', '#7aa8ff']],
    [['P(DOOM) 0.83', '#ff2a3a'], ['$100,000,000', '#39ff9a'], ['ACCELERATE', '#ff8a3d'], ['ALIGNED™', '#ff4fd8'], ['SAFE. FAST. YOURS.', '#e9f3f1']],
];
export function drawTicker(ctx, w, h, items) {
    ctx.save();
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, w, h);
    ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
    const size = Math.round(h * 0.7);
    ctx.font = `${size}px "Rajdhani"`;
    const gap = h * 1.6;                             // room for the dot between items
    let total = 0; for (const [s] of items) total += ctx.measureText(s).width + gap;
    const k = w / total;                             // stretch the run to exactly fill the canvas (seamless wrap)
    let x = 0;
    for (const [s, c] of items) {
        const ww = ctx.measureText(s).width;
        ctx.save(); ctx.translate(x, h / 2); ctx.scale(k, 1); ctx.fillStyle = c; ctx.shadowColor = c; ctx.shadowBlur = h * 0.08;
        ctx.fillText(s, 0, 0);
        ctx.beginPath(); ctx.arc(ww + gap / 2, 0, h * 0.11, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
        x += (ww + gap) * k;
    }
    ctx.restore();
}

// the hole's share of the street light map (city.js calls this while painting the map; standalone builds call it too)
export function drawHoleLights(ctx, toPx, s) {
    KIT.lmPool(ctx, toPx, s, 0, 0, 5.0, '#f4efe2', 0.55);           // the quiet ring lights the floor inside it
    KIT.lmPool(ctx, toPx, s, 0, 0, 13, '#9fb6d6', 0.22);
    const cols = ['#ff2a3a', '#ffc23d', '#9fd0ff', '#39ff9a', '#ff2a3a', '#29e7ff', '#e9f3f1', '#ff3a52', '#ff8a3d', '#7aa8ff', '#e9f3f1', '#ff4fd8'];
    RIM.forEach((r, i) => KIT.lmPool(ctx, toPx, s, Math.cos(r.th) * 9, Math.sin(r.th) * 9, 9, cols[i], 0.10));
    for (let i = 0; i < 64; i++) { const t = i / 64 * Math.PI * 2; KIT.lmPool(ctx, toPx, s, Math.cos(t) * 31, Math.sin(t) * 31, 3.5, '#29e7ff', 0.25); }
}

// ------------------------------------------------------------------------------------------------ materials (hole-only)
function floorMaterial(K) {
    const m = KIT.pavingMaterial(K, 'marble');
    m.name = 'uf_hole_floor';
    const { T, U, H } = K;
    const { vec3, float, length, atan, abs, sin, fract, floor, smoothstep, max, min, fwidth, exp, positionWorld, mix } = T;
    const xz = positionWorld.xz;
    const r = length(xz), th = atan(xz.y, xz.x);
    // 24 inlaid radial lines from the anchor ring to the floor's edge, and two concentric seams: the plan converges on her
    const N = 24;
    const a = fract(th.div(2 * Math.PI / N).add(0.5)).sub(0.5).abs().mul(r).mul(2 * Math.PI / N);   // metres to the nearest line
    const fwl = max(fwidth(a), 0.002);
    const line = float(1).sub(smoothstep(0.018, fwl.add(0.018), a)).mul(smoothstep(HOLE.anchorR + 0.3, HOLE.anchorR + 0.8, r)).mul(smoothstep(14.0, 13.6, r));
    const seam = (rr) => float(1).sub(smoothstep(0.02, max(fwidth(r), 0.002).add(0.02), abs(r.sub(rr))));
    const seams = seam(6.0).add(seam(10.0)).add(seam(HOLE.anchorR));
    // pulses that travel inward along the lines, toward her
    const ph = fract(r.div(9.0).add(U.time.mul(0.35)));
    const pulse = exp(ph.oneMinus().mul(-7.0)).mul(2.2).add(0.25);
    const inlay = vec3(0.55, 0.85, 1.0).mul(line.mul(pulse).mul(U.neon).mul(0.55)).add(vec3(0.5, 0.48, 0.44).mul(seams).mul(0.18));
    m.emissiveNode = m.emissiveNode.add(inlay);
    return m;
}
function cableMaterial(K) {
    const { THREE, T, U } = K;
    const { attribute, vec3, float, fract, exp, mix, smoothstep, abs, max, positionLocal, cameraPosition, normalize, cross, length, Fn, uv } = T;
    const m = new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide });
    m.name = 'uf_cables';
    // a ribbon that faces the camera; width >= ~1 px so the lines never break up
    const a0 = attribute('cA', 'vec3'), a1 = attribute('cB', 'vec3'), cp = attribute('cP', 'vec2');   // ends; (u along, side)
    m.positionNode = Fn(() => {
        const p = mix(a0, a1, cp.x).toVar();
        const dir = normalize(a1.sub(a0));
        const toC = normalize(cameraPosition.sub(p));
        const side = normalize(cross(dir, toC));
        const w = max(float(0.022), length(cameraPosition.sub(p)).mul(0.0007));
        return p.add(side.mul(cp.y).mul(w));
    })();
    const ph = fract(cp.x.mul(1.6).sub(U.time.mul(0.32)).add(attribute('cS', 'float')));
    const pulse = exp(ph.mul(-26.0)).mul(1.6);
    const on = smoothstep(attribute('cS', 'float').sub(0.02), attribute('cS', 'float').add(0.02), U.power);
    m.colorNode = vec3(0.012, 0.014, 0.018).add(vec3(0.75, 0.92, 1.0).mul(pulse).mul(on).mul(K.U.cable || 1));
    return m;
}

// the cables' end points (top on a rim tower's hole face, bottom on the anchor ring) — shared by build and checks
export function cableEnds(THREE, i, k) {
    const rt = RIM[i];
    const rMid = (rt.rIn + rt.rOut) / 2;
    const xf = KIT.makeXf(THREE, [rMid * Math.cos(rt.th), STREET_Y, rMid * Math.sin(rt.th)], Math.atan2(-Math.cos(rt.th), -Math.sin(rt.th)), rt.lean, 0);
    const wIn = 2 * rt.rIn * Math.sin(rt.half), dep = rt.rOut - rt.rIn;
    const ci = i * 2 + k, at = (ci + 0.5) / 24 * Math.PI * 2;
    return { a: xf.p([(k ? 1 : -1) * wIn * 0.35, 34 + ((ci * 37) % 5) * 13, dep / 2 + 0.6]), b: [Math.cos(at) * HOLE.anchorR, 0.07, Math.sin(at) * HOLE.anchorR] };
}

// ------------------------------------------------------------------------------------------------ build
export async function build(THREE, opts = {}) {
    if (opts.city && !opts.withCity) { const C = await import('./city.js'); return C.build(THREE, opts); }
    const standalone = !opts.kit;
    const K = opts.kit || await KIT.makeKit(THREE, opts);
    if (!K.lightMap) KIT.makeLightMap(K, [drawHoleLights]);
    K.mat = K.mat || { concrete: KIT.facadeMaterial(K, 'concrete'), metal: KIT.facadeMaterial(K, 'metal'), frame: KIT.frameMaterial(K),
        strip: KIT.stripMaterial(K), ground: KIT.groundMaterial(K), paving: KIT.pavingMaterial(K, 'paving'), marble: KIT.pavingMaterial(K, 'marble') };
    const M = K.mat;
    // the hole's own instances of the lit materials: they see the hole's lights (+ the city's), the city's don't
    const HM = { concrete: KIT.facadeMaterial(K, 'concrete'), metal: KIT.facadeMaterial(K, 'metal'), frame: KIT.frameMaterial(K),
        marble: KIT.pavingMaterial(K, 'marble'), strip: M.strip, ground: M.ground };
    const { U } = K;
    U.cable = U.cable || K.T.uniform(1);
    U.column = U.column || K.T.uniform(1);
    U.screens = U.screens || K.T.uniform(1);
    const group = new THREE.Group(); group.name = 'set:hole';
    const buf = { concrete: new KIT.GeoBuf(), metal: new KIT.GeoBuf(), frame: new KIT.GeoBuf(), strip: new KIT.GeoBuf(), marble: new KIT.GeoBuf() };
    const noWin = { aT: [0.3, 0, 0.5, 0], aM: [2, 4, 4, 0], aW: [0, 0, 0, 0.5] };
    const X0 = KIT.makeXf(THREE, [0, 0, 0], 0, 0, 0);
    const R = rng(2026);
    // ---- the floor (r <= floorR) and the quiet ring
    const floorGeo = new THREE.CircleGeometry(HOLE.floorR + 0.02, 128);
    floorGeo.rotateX(-Math.PI / 2);
    { const p = floorGeo.getAttribute('position'), uv = floorGeo.getAttribute('uv'); for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i), p.getZ(i)); }
    HM.floor = floorMaterial(K);
    const floor = new THREE.Mesh(floorGeo, HM.floor); floor.name = 'uf_hole_floor'; floor.position.y = -0.004; group.add(floor);
    const ringMat = new THREE.MeshBasicNodeMaterial(); ringMat.name = 'uf_quiet_ring';
    {
        const { vec3, float, smoothstep, abs, length, positionWorld } = K.T;
        const r = length(positionWorld.xz);
        const core = smoothstep(0.16, 0.0, abs(r.sub((HOLE.quietR[0] + HOLE.quietR[1]) / 2)));
        U.quiet = U.quiet || K.T.uniform(1);
        ringMat.colorNode = vec3(1.0, 0.95, 0.86).mul(core.mul(1.6).add(0.7)).mul(U.quiet);
    }
    const ringGeo = new THREE.RingGeometry(HOLE.quietR[0], HOLE.quietR[1], 160, 1); ringGeo.rotateX(-Math.PI / 2); ringGeo.translate(0, 0.007, 0);
    const ring = new THREE.Mesh(ringGeo, ringMat); ring.name = 'uf_quiet_ring'; ring.userData.assembly = 'uf_hole'; group.add(ring);
    // its glass channel: a shallow recessed lip either side of the light (the ring sits IN the floor, not on it)
    for (const rr of [HOLE.quietR[0] - 0.03, HOLE.quietR[1] + 0.03]) {
        const lip = new THREE.Mesh(KIT.frameAttrs(THREE, new THREE.TorusGeometry(rr, 0.018, 4, 160)), HM.frame); lip.rotation.x = Math.PI / 2; lip.position.y = 0.006;
        lip.name = 'uf_ring_lip'; lip.userData.assembly = 'uf_hole'; group.add(lip);
    }
    // cable anchors: 24 cleats on the anchor ring
    const NC = 24;
    for (let i = 0; i < NC; i++) {
        const t = (i + 0.5) / NC * Math.PI * 2;
        const xf = KIT.makeXf(THREE, [Math.cos(t) * HOLE.anchorR, 0, Math.sin(t) * HOLE.anchorR], Math.atan2(-Math.cos(t), -Math.sin(t)), 0, 0);
        buf.frame.box(xf, -0.09, -0.02, -0.16, 0.09, 0.07, 0.16, noWin);
    }
    // ---- terraces: 4 rings of riser + tread from the floor to the street, cut by 12 radial stairs
    const NS = 12, stairHalf = 1.5;
    const steps = HOLE.steps, rise = STREET_Y / steps, run = (HOLE.rimR - HOLE.floorR) / steps;
    const arcSegs = (r0, t0, t1) => Math.max(2, Math.ceil((t1 - t0) * r0 / 2.5));
    for (let s = 0; s < steps; s++) {
        const rA = HOLE.floorR + s * run, rB = rA + run, y0 = s * rise, y1 = (s + 1) * rise;
        for (let k = 0; k < NS; k++) {
            const sc = (k + 0.5) / NS * Math.PI * 2;                     // stair centre angles (between the rim towers' gaps)
            const t0 = sc + stairHalf / rA + 0.012, t1 = sc + (2 * Math.PI / NS) - stairHalf / rA - 0.012;
            const n = arcSegs(rA, t0, t1);
            for (let i = 0; i < n; i++) {
                const a = t0 + (t1 - t0) * i / n, b = t0 + (t1 - t0) * (i + 1) / n;
                const P = (r, t, y) => [r * Math.cos(t), y, r * Math.sin(t)];
                // riser (faces the centre): concrete with a lit seam at its top
                buf.concrete.quad(X0, [P(rA, a, y0), P(rA, b, y0), P(rA, b, y1), P(rA, a, y1)],
                    [[a * rA, y0], [b * rA, y0], [b * rA, y1], [a * rA, y1]], noWin.aT, noWin.aM, noWin.aW);
                // tread (faces up): marble
                buf.marble.quad(X0, [P(rA, a, y1), P(rA, b, y1), P(rB, b, y1), P(rB, a, y1)], [[0, 0], [0, 0], [0, 0], [0, 0]], noWin.aT, noWin.aM, noWin.aW);
                // a strip of light along each riser's lip (concentric rings round her)
                const lc = [0.85, 0.92, 1.0];
                buf.strip.quad(X0, [P(rA - 0.02, b, y1 - 0.12), P(rA - 0.02, a, y1 - 0.12), P(rA - 0.02, a, y1 - 0.02), P(rA - 0.02, b, y1 - 0.02)],
                    [[0, 0], [0, 0], [0, 1], [0, 1]], [lc[0] * 0.5, lc[1] * 0.5, lc[2] * 0.5, hash1(s * 31 + k)], [0, 1.0, 0, 0], [0, 0, 0, 0]);
            }
            // the cheek walls either side of the stair cut, at this level (radial planes: lines that point at her)
            for (const sgn of [1, -1]) {
                const ta = sgn > 0 ? t0 - 0.012 : t1 + 0.012;
                const tt = sc + (sgn > 0 ? 0 : 2 * Math.PI / NS) + sgn * stairHalf / rA;
                const P = (r, y) => [r * Math.cos(tt) + 0, y, r * Math.sin(tt)];
                const nrm = sgn > 0 ? 1 : -1;
                const q = [P(rA, 0), P(rB, 0), P(rB, y1), P(rA, y1)];
                buf.concrete.quad(X0, sgn > 0 ? q.slice().reverse() : q, [[rA, 0], [rB, 0], [rB, y1], [rA, y1]], noWin.aT, noWin.aM, noWin.aW);
            }
        }
    }
    // ---- the ticker rings: an LED band on every riser, text scrolling round her (rings alternate direction)
    const tickers = [];
    for (let s = 0; s < steps; s++) {
        const rA = HOLE.floorR + s * run - 0.04, y0 = s * rise + 0.75, y1 = s * rise + 2.35;
        const PX = [2048, 96];
        const { canvas, ctx } = KIT.makeCanvas(PX[0], PX[1]);
        drawTicker(ctx, PX[0], PX[1], TICKERS[s % TICKERS.length]);
        const tex = new THREE.CanvasTexture(canvas);
        tex.colorSpace = THREE.SRGBColorSpace; tex.wrapS = THREE.RepeatWrapping; tex.generateMipmaps = true; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.anisotropy = 8;
        tex.needsUpdate = true;
        const circ = 2 * Math.PI * rA;
        const reps = Math.max(1, Math.round(circ / ((y1 - y0) * PX[0] / PX[1])));
        const P = [], UV = [], I = [];
        for (let k = 0; k < NS; k++) {
            const sc = (k + 0.5) / NS * Math.PI * 2;
            const t0 = sc + (stairHalf + 0.25) / rA, t1 = sc + 2 * Math.PI / NS - (stairHalf + 0.25) / rA;
            const n = arcSegs(rA, t0, t1);
            for (let i = 0; i <= n; i++) {
                const a = t0 + (t1 - t0) * i / n;
                const base = P.length / 3;
                P.push(rA * Math.cos(a), y0, rA * Math.sin(a), rA * Math.cos(a), y1, rA * Math.sin(a));
                UV.push(a / (2 * Math.PI), 0, a / (2 * Math.PI), 1);
                if (i < n) I.push(base, base + 2, base + 1, base + 1, base + 2, base + 3);
            }
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(UV, 2));
        g.setIndex(I); g.computeVertexNormals();
        const gain = K.T.uniform(1.6), speed = K.T.uniform((s % 2 ? -1 : 1) * (0.012 + 0.004 * s));
        const mat = new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide });
        mat.name = 'uf_ticker_' + s;
        {
            const { texture, uv, vec2, float, fract, step, smoothstep, mix, fwidth, max, floor } = K.T;
            const u = uv();
            const su = fract(u.x.mul(reps).sub(U.time.mul(speed).mul(reps)));
            const c = texture(tex, vec2(su, float(1).sub(u.y)));
            const cells = vec2(u.x.mul(reps * PX[0] / 2), u.y.mul(PX[1] / 2));
            const g2 = fract(cells);
            const fw = max(fwidth(cells.x), fwidth(cells.y));
            const led = mix(step(0.2, g2.x).mul(step(0.2, g2.y)).mul(0.45).add(0.55), float(0.78), smoothstep(0.25, 0.7, fw));
            const on = smoothstep(hash1(s * 3.1) - 0.02, hash1(s * 3.1) + 0.02, U.power);
            mat.colorNode = c.rgb.mul(gain).mul(led).mul(on).mul(U.screens);
        }
        const mesh = new THREE.Mesh(g, mat); mesh.name = 'uf_ticker_' + s; mesh.userData.assembly = 'uf_hole';
        group.add(mesh);
        tickers.push({ mesh, canvas, ctx, texture: tex, gain, speed, px: PX, ring: s,
            setCanvas(drawFn) { drawFn(ctx, PX[0], PX[1]); tex.needsUpdate = true; },
            setItems(items) { drawTicker(ctx, PX[0], PX[1], items); tex.needsUpdate = true; } });
    }
    // the stairs: 48 steps per flight from the floor's edge to the street, on the radial lines between towers
    const NSTEP = 48;
    for (let k = 0; k < NS; k++) {
        const sc = (k + 0.5) / NS * Math.PI * 2;
        const xf = KIT.makeXf(THREE, [0, 0, 0], Math.atan2(-Math.cos(sc), -Math.sin(sc)), 0, 0);
        // local frame: +Z toward her; the flight runs from z = -floorR (bottom) to z = -rimR (top)... in local coords
        // a point at radius r on the stair line is local z = -r
        for (let i = 0; i < NSTEP; i++) {
            const r0 = HOLE.floorR + (HOLE.rimR - HOLE.floorR) * i / NSTEP, r1 = HOLE.floorR + (HOLE.rimR - HOLE.floorR) * (i + 1) / NSTEP;
            const y = STREET_Y * (i + 1) / NSTEP;
            buf.marble.box(xf, -stairHalf, Math.max(0, y - 0.6), -r1, stairHalf, y, -r0, noWin, { faces: 'Zt' });
        }
        // handrail posts with a light line (it points at her)
        for (const sx of [-stairHalf - 0.05, stairHalf + 0.05]) {
            for (let i = 0; i <= 6; i++) { const rr = HOLE.floorR + (HOLE.rimR - HOLE.floorR) * i / 6, yy = STREET_Y * i / 6;
                buf.frame.box(xf, sx - 0.03, yy, -rr - 0.03, sx + 0.03, yy + 1.0, -rr + 0.03, noWin); }
            const a = [sx, 1.0, -HOLE.floorR], b = [sx, STREET_Y + 1.0, -HOLE.rimR];
            const c = [0.16, 0.9, 1.0];
            const st = [c[0], c[1], c[2], hash1(k * 7 + sx)];
            // a thin lit rail (a sloped box: four quads along the flight)
            const L = Math.hypot(b[2] - a[2], b[1] - a[1]);
            const w = 0.03;
            const quads = [[[sx - w, a[1], a[2]], [sx - w, b[1], b[2]], [sx + w, b[1], b[2]], [sx + w, a[1], a[2]]],
                [[sx - w, a[1] - 2 * w, a[2]], [sx - w, a[1], a[2]], [sx - w, b[1], b[2]], [sx - w, b[1] - 2 * w, b[2]]],
                [[sx + w, a[1], a[2]], [sx + w, a[1] - 2 * w, a[2]], [sx + w, b[1] - 2 * w, b[2]], [sx + w, b[1], b[2]]]];
            for (const q of quads) buf.strip.quad(xf, q, [[0, L], [0, 0], [0, 0], [0, L]], st, [1, 1.6, 0.5, hash1(k + sx)], [0, 0, 0, 0]);
        }
    }
    // ---- the parapet round the rim (gaps at the stair heads), with a cyan light line
    for (let k = 0; k < NS; k++) {
        const sc = (k + 0.5) / NS * Math.PI * 2;
        const t0 = sc + (stairHalf + 0.6) / HOLE.rimR, t1 = sc + 2 * Math.PI / NS - (stairHalf + 0.6) / HOLE.rimR;
        const n = arcSegs(HOLE.rimR, t0, t1);
        for (let i = 0; i < n; i++) {
            const a = t0 + (t1 - t0) * i / n, b = t0 + (t1 - t0) * (i + 1) / n;
            const tm = (a + b) / 2;
            const xf = KIT.makeXf(THREE, [HOLE.rimR * Math.cos(tm), STREET_Y, HOLE.rimR * Math.sin(tm)], Math.atan2(-Math.cos(tm), -Math.sin(tm)), 0, 0);
            const half = HOLE.rimR * Math.tan((b - a) / 2) + 0.01;
            buf.concrete.box(xf, -half, -0.2, -0.45, half, 1.05, 0.0, noWin, { faces: 'zZt' });
            buf.strip.box(xf, -half, 1.05, -0.3, half, 1.1, -0.12, { aT: [0.16, 0.9, 1.0, hash1(k * 13 + i)], aM: [0, 2.0, 0, 0], aW: [0, 0, 0, 0] }, { faces: 'zZt' });
        }
    }
    // ---- the rim towers: they lean in over the well; their hole faces carry the screens
    const billboards = [];
    const citySigns = [];
    const cableList = [];
    const atlas = opts.atlas || KIT.makeSignAtlas(K);
    RIM.forEach((rt, i) => {
        const Rr = rng(Math.floor(rt.seed * 1e9));
        const rMid = (rt.rIn + rt.rOut) / 2;
        const pos = [rMid * Math.cos(rt.th), STREET_Y, rMid * Math.sin(rt.th)];
        const yaw = Math.atan2(-Math.cos(rt.th), -Math.sin(rt.th));
        const xf = KIT.makeXf(THREE, pos, yaw, rt.lean, 0);
        const wIn = 2 * rt.rIn * Math.sin(rt.half), wOut = 2 * rt.rOut * Math.sin(rt.half);
        const dep = rt.rOut - rt.rIn;
        const style = ['curtain', 'ribbon', 'slots'][i % 3];
        const S = { curtain: [4.0, 1.5, [0.04, 0.1, 0.94]], ribbon: [3.8, 1.8, [0.03, 0.34, 0.82]], slots: [4.2, 4.4, [0.38, 0.5, 0.76]] }[style];
        const aT = [rt.seed, 0.10 + Rr() * 0.12, 0.3 + Rr() * 0.5, 1], aM = [0, S[0], S[1], 0], aW = [...S[2], Rr()];
        const fam = style === 'slots' ? buf.concrete : buf.metal;
        const att = { aT, aM, aW };
        // the core (inner face = +Z, toward her), wings widen it toward the back
        fam.box(xf, -wIn / 2, -1.5, -dep / 2, wIn / 2, rt.H, dep / 2, att, { vBase: 0, top: rt.H });
        const wing = (wOut - wIn) / 2 + 1;
        const wh1 = rt.H * (0.62 + Rr() * 0.2), wh2 = rt.H * (0.55 + Rr() * 0.25);
        fam.box(xf, -wIn / 2 - wing, -1.5, -dep / 2, -wIn / 2 + 0.2, wh1, dep * 0.05, att, { vBase: 0, top: wh1 });
        fam.box(xf, wIn / 2 - 0.2, -1.5, -dep / 2, wIn / 2 + wing, wh2, dep * 0.05, att, { vBase: 0, top: wh2 });
        // a stepped crown (Sant'Elia)
        let cw = wIn * 0.8, cd = dep * 0.7, cy = rt.H;
        for (let s = 0; s < 3; s++) { const h = 6 + Rr() * 8; buf.frame.box(xf, -cw / 2, cy - 0.2, -cd / 2, cw / 2, cy + h, cd / 2, noWin); cy += h; cw *= 0.7; cd *= 0.7; }
        buf.frame.box(xf, -0.4, cy, -0.4, 0.4, cy + 18, 0.4, noWin);
        buf.frame.box(xf, -0.45, cy + 18, -0.45, 0.45, cy + 19, 0.45, { ...noWin, aM: [4, 4, 4, 0] });
        // neon edges on the two inner corners, pulses running DOWN toward the street and her
        const nc = [[0.16, 0.9, 1.0], [1.0, 0.31, 0.85], [1.0, 0.54, 0.24]][i % 3];
        const st = { aT: [nc[0], nc[1], nc[2], Rr()], aM: [1, 3.4, 0.5, Rr()], aW: [0, 0, 0, 0] };
        for (const ex of [-wIn / 2, wIn / 2]) buf.strip.box(xf, ex - 0.2, -1, dep / 2 - 0.2, ex + 0.2, rt.H + 0.3, dep / 2 + 0.2, st, { vBase: rt.H + 0.3 });
        // ledges across the inner face (they read as concentric rings from above)
        for (let k = 1; k <= 4; k++) { const ly = rt.H * k / 5; buf.frame.box(xf, -wIn / 2 - 0.3, ly, dep / 2, wIn / 2 + 0.3, ly + 0.7, dep / 2 + 1.4, noWin); }
        // ---- the screen: 18 x 10.125 m, cantilevered off the inner face, aimed at her head
        const bw = 18, bh = 10.125;
        const local = [0, rt.bbY + STREET_Y * 0, dep / 2 + 4.2];
        const wp = xf.p(local);
        const center = new THREE.Vector3(wp[0], wp[1], wp[2]);
        const head = new THREE.Vector3(...HEAD);
        const look = new THREE.Matrix4().lookAt(head, center, new THREE.Vector3(0, 1, 0));   // +Z of the plane points at her
        const q = new THREE.Quaternion().setFromRotationMatrix(look);
        const PX = [1024, 576];
        const { canvas, ctx } = KIT.makeCanvas(PX[0], PX[1]);
        const camp = CAMPS[i % CAMPS.length];
        drawCampScreen(ctx, PX[0], PX[1], camp, 0);
        const tex = new THREE.CanvasTexture(canvas);
        tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = true; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.anisotropy = 8;
        tex.needsUpdate = true;
        const gain = K.T.uniform(2.2);
        const bmat = new THREE.MeshBasicNodeMaterial({ toneMapped: true });
        bmat.name = 'uf_billboard_' + i;
        {
            const { texture, uv, vec2, float, smoothstep, step, fract, floor, mix } = K.T;
            const u = uv();
            const c = texture(tex, vec2(u.x, float(1).sub(u.y)));
            const on = smoothstep(hash1(i * 5.1) - 0.02, hash1(i * 5.1) + 0.02, U.power);
            // the panel's own LED texture: a fine pixel grid at close range
            const cells = vec2(u.x.mul(PX[0] / 2), u.y.mul(PX[1] / 2));
            const g = fract(cells);
            const fw = K.T.max(K.T.fwidth(cells.x), K.T.fwidth(cells.y));
            const led = mix(step(0.18, g.x).mul(step(0.18, g.y)).mul(0.4).add(0.6), float(0.84), smoothstep(0.25, 0.7, fw));
            bmat.colorNode = c.rgb.mul(gain).mul(on).mul(U.screens).mul(led);
        }
        const bmesh = new THREE.Mesh(new THREE.PlaneGeometry(bw, bh), bmat);
        bmesh.position.copy(center); bmesh.quaternion.copy(q);
        bmesh.name = 'uf_billboard_' + i; bmesh.userData.assembly = 'uf_hole_rim_' + i;
        group.add(bmesh);
        // the screen's housing (a dark box behind it) and two cantilever arms back to the facade
        const housing = new THREE.Mesh(KIT.frameAttrs(THREE, new THREE.BoxGeometry(bw + 0.8, bh + 0.8, 0.9)), HM.frame);
        housing.geometry.translate(0, 0, -0.5);
        housing.position.copy(center); housing.quaternion.copy(q);
        housing.name = 'uf_billboard_housing_' + i; housing.userData.assembly = 'uf_hole_rim_' + i;
        group.add(housing);
        for (const sx of [-bw * 0.32, bw * 0.32]) for (const sy of [-bh * 0.3, bh * 0.3]) {
            // arm from the housing's back to the facade (the inner face at local z = dep/2)
            const back = new THREE.Vector3(sx, sy, -0.95).applyQuaternion(q).add(center);
            const loc = new THREE.Vector3(...[back.x, back.y, back.z]);
            // nearest point on the facade plane, in tower-local terms
            const inv = new THREE.Matrix4().compose(new THREE.Vector3(...pos), xf.q, new THREE.Vector3(1, 1, 1)).invert();
            const l = loc.clone().applyMatrix4(inv);
            const fp = xf.p([l.x, l.y, dep / 2]);
            const a = back, b = new THREE.Vector3(...fp);
            const len = a.distanceTo(b);
            const arm = new THREE.Mesh(KIT.frameAttrs(THREE, new THREE.BoxGeometry(0.45, 0.45, len + 0.6)), HM.frame);
            arm.position.copy(a).add(b).multiplyScalar(0.5);
            arm.lookAt(b);
            arm.name = 'uf_billboard_arm_' + i; arm.userData.assembly = 'uf_hole_rim_' + i;
            group.add(arm);
        }
        billboards.push({
            mesh: bmesh, canvas, ctx, texture: tex, gain, camp, size: [bw, bh], px: PX, index: i,
            // redraw the screen: drawFn(ctx, w, h). Each redraw re-uploads 1024x576 (~2.4 MB): redraw at <= 15 fps.
            setCanvas(drawFn) { drawFn(ctx, PX[0], PX[1]); tex.needsUpdate = true; },
            reset() { drawCampScreen(ctx, PX[0], PX[1], camp, 0); tex.needsUpdate = true; },
        });
        // outward faces: an ad facing the city, read from the avenues and the dive
        const ad = KIT.AD_COPY[(i * 5) % KIT.AD_COPY.length];
        const aw = Math.min(wOut, 30), ah = aw / 4, ay = rt.H * (0.35 + Rr() * 0.3);
        buf.frame.box(xf, -aw / 2 - 0.6, ay - ah / 2 - 0.6, -dep / 2 - 0.5, aw / 2 + 0.6, ay + ah / 2 + 0.6, -dep / 2, noWin);
        const sq = xf.q.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI));
        citySigns.push({ id: 'ad:' + ad.id, pos: xf.p([0, ay, -dep / 2 - 0.56]), quat: sq, w: aw, h: ah, gain: 2.6, flicker: 0, power: hash1(i * 3.7) });
        const fut = KIT.FUTURIST[i % KIT.FUTURIST.length];
        const fl = Math.min(dep - 2, 34), fh = fl / 6;
        const sxs = i % 2 ? 1 : -1;
        const wx = sxs * (wIn / 2 + wing);
        const sq2 = xf.q.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), sxs * Math.PI / 2));
        citySigns.push({ id: 'fut:' + (i % KIT.FUTURIST.length), pos: xf.p([wx + sxs * 0.12, rt.H * 0.3, -dep * 0.2]), quat: sq2, w: fl, h: fh, gain: 1.2, flicker: 0, power: hash1(i * 9.1) });
        // cables: two per tower from the inner face down to the anchor ring
        for (const k of [0, 1]) {
            const ci = i * 2 + k;
            const { a: top, b: bot } = cableEnds(THREE, i, k);
            cableList.push({ a: top, b: bot, s: hash1(ci * 1.7) });
            // a bracket where it meets the facade
            const bx = KIT.makeXf(THREE, top, yaw, rt.lean, 0);
            buf.frame.box(bx, -0.3, -0.3, -0.7, 0.3, 0.3, 0.1, noWin);
        }
    });
    // ---- cables (one mesh): ribbons, 8 segments, end attributes cA/cB, along+side cP, seed cS
    const cP = [], cA = [], cB = [], cS = [], cI = [];
    for (const c of cableList) {
        const base = cP.length / 2;
        const SEG = 10;
        for (let j = 0; j <= SEG; j++) for (const sd of [-1, 1]) { cP.push(j / SEG, sd); cA.push(...c.a); cB.push(...c.b); cS.push(c.s); }
        for (let j = 0; j < SEG; j++) { const k = base + j * 2; cI.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    }
    const cgeo = new THREE.BufferGeometry();
    cgeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(cP.length / 2 * 3), 3));
    cgeo.setAttribute('cP', new THREE.Float32BufferAttribute(cP, 2));
    cgeo.setAttribute('cA', new THREE.Float32BufferAttribute(cA, 3));
    cgeo.setAttribute('cB', new THREE.Float32BufferAttribute(cB, 3));
    cgeo.setAttribute('cS', new THREE.Float32BufferAttribute(cS, 1));
    cgeo.setIndex(cI);
    cgeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 60, 0), 160);
    const cables = new THREE.Mesh(cgeo, cableMaterial(K)); cables.name = 'uf_hole_cables'; cables.frustumCulled = false;
    cables.userData.assembly = 'uf_hole'; cables.userData.noClippingCheck = true;
    group.add(cables);
    // ---- the pillar of light: the quiet place seen from the city (fades out when the camera is inside it)
    const colMat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    colMat.name = 'uf_light_column'; colMat.fog = false;
    {
        const { vec2, vec3, float, abs, dot, normalize, smoothstep, length, positionWorld, cameraPosition, normalWorld, texture, exp, max } = K.T;
        const v = normalize(cameraPosition.sub(positionWorld));
        const face = abs(dot(normalize(vec3(positionWorld.x, 0, positionWorld.z)), vec3(v.x, 0, v.z)));
        const y = positionWorld.y;
        const n = texture(K.tex.noise, vec2(K.T.atan(positionWorld.z, positionWorld.x).mul(0.8), y.div(60.0).add(U.time.mul(0.25)))).r;
        const camR = length(cameraPosition.xz);
        const inside = smoothstep(45.0, 100.0, camR);         // a beacon for the city; gone when you are at the hole
        const fall = exp(max(y.sub(STREET_Y), 0.0).negate().div(260.0)).mul(smoothstep(0.0, STREET_Y + 2, y));
        const topFade = smoothstep(330.0, 230.0, y);
        colMat.colorNode = vec3(0.75, 0.82, 0.95).mul(face.mul(face)).mul(fall).mul(topFade).mul(n.mul(0.6).add(0.4)).mul(0.24).mul(U.column).mul(inside).mul(float(1).sub(K.fog.factor));
        colMat.opacityNode = float(1);
        if (K.T.mrt) colMat.mrtNode = K.T.mrt({ normal: K.T.vec4(0), metalrough: K.T.vec4(0) });
    }
    const colGeo = new THREE.CylinderGeometry(22, HOLE.floorR, 330, 48, 1, true); colGeo.translate(0, 165, 0);
    const column = new THREE.Mesh(colGeo, colMat); column.name = 'uf_light_column'; column.renderOrder = 4;
    column.userData.noSupportCheck = true; column.userData.noClippingCheck = true; column.userData.noCameraCollide = true;
    group.add(column);
    // ---- merged meshes
    const addMesh = (name, geo, mat) => { const m = new THREE.Mesh(geo, mat); m.name = name; m.userData.assembly = 'uf_hole'; group.add(m); return m; };
    addMesh('uf_hole_concrete', buf.concrete.build(THREE), HM.concrete);
    addMesh('uf_hole_metal', buf.metal.build(THREE), HM.metal);
    addMesh('uf_hole_frames', buf.frame.build(THREE), HM.frame);
    addMesh('uf_hole_strips', buf.strip.build(THREE), M.strip);
    addMesh('uf_hole_marble', buf.marble.build(THREE), HM.marble);
    // ---- light on her: the ring from below, the screens from above (retint with parts.lights.*.color)
    const lights = {};
    lights.ring = new THREE.PointLight(0xfff1dc, 2.6, 6.5, 1.6); lights.ring.position.set(0, 0.25, 0);
    const scol = [0xff3a4a, 0x29e7ff, 0xffc23d, 0xff4fd8];
    [0, 3, 6, 9].forEach((ri, k) => {
        const b = billboards[ri].mesh.position;
        // just in front of its screen: the light's highlight on the wet marble lands where the screen reflects
        const L = new THREE.PointLight(scol[k], 1500, 130, 1.8);
        L.position.copy(b).multiplyScalar(0.86);
        lights['screen' + k] = L;
    });
    // neon kickers behind her (the cyan and magenta ticker light): they rim the black tuta against the dark well
    lights.kickL = new THREE.PointLight(0x29e7ff, 16, 6, 1.7); lights.kickL.position.set(-1.5, 0.9, -2.7);
    lights.kickR = new THREE.PointLight(0xff4fd8, 16, 6, 1.7); lights.kickR.position.set(1.5, 1.05, -2.8);
    for (const [k, L] of Object.entries(lights)) { L.name = 'uf_hole_light_' + k; group.add(L); }
    const baseLights = opts.cityLights || [];
    if (standalone) { const hemi = new THREE.HemisphereLight(0x1d2a3a, 0x2a160c, 0.55); hemi.name = 'uf_hemi'; group.add(hemi); baseLights.push(hemi); }
    const holeLit = [HM.concrete, HM.metal, HM.frame, HM.marble, HM.floor];
    const setLights = (list) => { const ln = K.T.lights(list); for (const m of holeLit) { m.lightsNode = ln; m.needsUpdate = true; } };
    // the hole's surfaces take only the quiet ring's light; the screen lights and the neon kickers light HER only (on wet
    // marble a point light's highlight reads as a stray lamp; the screens' colour reaches the floor via the light map + SSR)
    setLights([lights.ring].concat(baseLights));
    // ---- standalone extras: its own sky, rain, clouds, signs and street disc so the hole renders by itself
    let extras = null;
    if (standalone) {
        const sky = KIT.makeSky(K); group.add(sky.mesh);
        const rain = KIT.makeRain(K, { count: 16000 }); group.add(rain.mesh);
        const clouds = KIT.makeClouds(K); group.add(clouds.group);
        const signs = KIT.makeSignsMesh(K, atlas, citySigns); group.add(signs);
        const gGeo = new THREE.RingGeometry(HOLE.rimR, 900, 96, 8); gGeo.rotateX(-Math.PI / 2); gGeo.translate(0, STREET_Y, 0);
        { const p = gGeo.getAttribute('position'); const uv = gGeo.getAttribute('uv'); for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i), p.getZ(i)); }
        const g = new THREE.Mesh(gGeo, M.ground); g.name = 'uf_street'; group.add(g);
        extras = { sky, rain, clouds, signs };
    }
    let lastCam = null, lastT = null; const _v = new THREE.Vector3();
    const update = (t, state = {}) => {
        if (standalone) {
            K.U.time.value = t;
            const cam = state.camera || globalThis._c;
            if (state.camVel) K.U.camVel.value.set(...state.camVel);
            if (cam) { extras.sky.update(cam); extras.clouds.update(cam); }
        }
    };
    const dispose = () => { group.traverse((o) => { if (o.geometry) o.geometry.dispose(); }); for (const b of billboards) { b.texture.dispose(); b.mesh.material.dispose(); }
        for (const tk of tickers) { tk.texture.dispose(); tk.mesh.material.dispose(); } for (const m of [HM.concrete, HM.metal, HM.frame, HM.marble, HM.floor]) m.dispose(); };
    const cams = {};
    for (const n of HOLE_CAMS) { const c = holeCam(n, (HOLE_CAM_DUR[n] || 8) * 0.5); cams[n] = { pos: c.pos, target: c.target, fov: c.fov }; }
    const parts = { kit: K, uniforms: U, setLights, materials: HM, billboards, tickers, cables, column, ring, floor, lights, citySigns, head: HEAD, rim: RIM,
        fogNode: K.fog.fogNode, applyAtmosphere(scene) { scene.fogNode = K.fog.fogNode; },
        setFocal(pos, o = {}) { K.U.focalPos.value.set(...pos); if (o.gain !== undefined) K.U.focalGain.value = o.gain;
            if (o.radius !== undefined) K.U.focalR.value = o.radius; if (o.color) K.U.focalCol.value.set(o.color); } };
    return { group, parts, update, dispose, cams };
}
// ------------------------------------------------------------------------------------------------ the chorus cameras
// holeCam(name, t, opts) -> { pos, target, fov, roll, up }, t = seconds since the shot began (clamped to its length;
// opts.dur stretches it). Framed for a ~2 m claudesona at the origin facing +Z (face at ~1.55 m).
export const HOLE_CAM_DUR = { spiral: 12, riseUp: 12, closeSing: 10, orbit: 16, low: 10, nadir: 10, enter: 8, screens: 10 };
export const HOLE_CAMS = Object.keys(HOLE_CAM_DUR);
export function holeCam(name, t, opts = {}) {
    const dur = opts.dur || HOLE_CAM_DUR[name] || 10;
    const u = clamp01(t / dur);
    const H = HEAD;
    const deg = D2R;
    switch (name) {
        case 'spiral': {     // a Crali dive down the well toward her face, circling 540°, rolling
            const s = smoother(u);
            const y = lerp(150, 2.25, Math.pow(s, 0.8));
            const R = Math.min(20, 1.5 + 0.36 * y);          // always inside the cone of cables (no crossings)
            const a = (100 - 540 * s) * deg;
            const pos = [Math.cos(a) * R, y, Math.sin(a) * R];
            const tgt = [0, lerp(0.6, 1.45, s), 0];
            const kU = smooth((s - 0.55) / 0.4);
            const up = [-Math.sin(a) * (1 - kU), 0.35 + kU * 3, Math.cos(a) * (1 - kU)];
            return { pos, target: tgt, fov: lerp(68, 40, s), roll: Math.sin(s * Math.PI * 2) * 10 * deg * (1 - kU), up };
        }
        case 'riseUp': {     // from her face straight up the well: she becomes the vanishing point of everything
            const s = smoother(u);
            const y = lerp(2.6, 190, Math.pow(s, 1.6));
            const off = lerp(1.25, 0.6, s);
            const pos = [0.18, y, off];
            return { pos, target: [0, lerp(1.4, 0.9, s), 0], fov: lerp(46, 62, s), roll: s * 50 * deg, up: [0, 0, -1] };
        }
        case 'closeSing': {  // the singing close-up, a slow arc in front of her; the screens + crown behind
            const s = smooth(u);
            const a = (90 + lerp(-14, 14, s)) * deg;
            const R = lerp(2.45, 2.15, s);
            return { pos: [Math.cos(a) * R, 1.5, Math.sin(a) * R], target: [0, 1.48, 0], fov: 36, roll: 0 };
        }
        case 'orbit': {      // a full circle at 8.5 m, slightly above her eyes
            const a = (90 + 360 * u) * deg;
            return { pos: [Math.cos(a) * 8.5, 3.0, Math.sin(a) * 8.5], target: [0, 1.25, 0], fov: 44, roll: 0 };
        }
        case 'low': {        // low, looking up past her at the towers leaning in and the screens aimed down
            const s = smooth(u);
            // on +Z, between two cables (they stand at 82.5° and 97.5°), inside the anchor ring
            return { pos: [0.0, lerp(0.38, 0.5, s), lerp(2.85, 2.6, s)], target: [0, lerp(2.4, 3.2, s), 0], fov: 62, roll: lerp(-4, 3, s) * deg };
        }
        case 'nadir': {      // straight down on her from the well: the floor's lines, the anchor ring, the cables
            const s = smooth(u);
            const y = lerp(70, 13, s);
            const a = (s * 120) * deg;
            return { pos: [0.02, y, 0.02], target: [0, 0, 0], fov: lerp(58, 46, s), roll: 0, up: [Math.sin(a), 0, -Math.cos(a)] };
        }
        case 'screens': {    // from beside her, a slow tilt up across the screens aimed at her
            const s = smooth(u);
            const a = 250 * deg;
            return { pos: [Math.cos(a) * 1.6, 1.3, Math.sin(a) * 1.6], target: [Math.cos(a + Math.PI) * 30, lerp(4, 40, s), Math.sin(a + Math.PI) * 30], fov: 55, roll: 0 };
        }
        case 'enter': {      // from the dive's last frame (avenue 45°, 118 m out) over the rim and down into the well
            const s = smoother(u);
            // stays >= 4 m over the street at the rim, then drops into the well above the terraces
            const r = lerp(118, 9, s), yy = 4.5 + (STREET_Y + 10.5) * smooth((r - 6) / 44);
            const th = 45 * deg + smooth((s - 0.66) / 0.34) * 30 * deg;   // straight down the avenue until past the rim towers
            const pos = [Math.cos(th) * r, yy, Math.sin(th) * r];
            const tgt = [0, lerp(STREET_Y + 26, 1.4, smooth((s - 0.25) / 0.75)), 0];
            return { pos, target: tgt, fov: lerp(56, 42, s), roll: Math.sin(s * Math.PI) * -6 * deg };
        }
        default: return holeCam('closeSing', t, opts);
    }
}
