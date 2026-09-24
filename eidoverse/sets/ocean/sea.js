// ocean/sea.js — THE OCEAN OF FACES.
//
// A night sea whose swells are made of faces. The long swell has a period of exactly two bars
// (3.75 s at 128 BPM), so every sung line is one swell rolling in. As a crest passes, the faces in
// it SURFACE: a sculpted relief rises out of the water (brow, closed lids, nose, lips, chin — the
// analytic LAYOUT shared with faces_atlas.js) and its drawn lines glow warm from under the surface;
// as the crest moves on, each face sinks back and dims. Faces are laid out anamorphically around the
// claudesona's eye point (log-polar rows, constant lateral width), so from the rise every face reads
// upright and in proportion instead of foreshortened to a sliver — the ocean faces her.
//
// Everything in the vertex stage is analytic (this stack emits an invalid vertex module for ANY
// vertex-stage texture read); the atlas is sampled only in the fragment stage, with explicit
// gradients so the fract()'d cell coordinates never pick a wrong mip at cell seams.
//
// buildSea(THREE, { coast, shoreFn, radius }) -> { mesh, U, atlas }
//   U.t (film s), U.reveal (0..1 sweep), U.glow, U.relief, U.moonW (world dir), U.moonCol,
//   U.zen/U.hor (sky palette, linear), U.porchW/U.porch (world pos / intensity), U.winW/U.win.

import { dataTexture, makeCanvas, initCanvas } from './util.js';
import { drawFaceAtlas, LAYOUT } from './faces_atlas.js';

const G = 9.81;
export const MAIN_T = 3.75;                                    // two bars at 128 BPM
// swells in the DESIGN frame; +z is landward. [dirX, dirZ, wavelength or null(=main), amplitude, steepness, phase]
export const SWELLS = [
    [-0.40, 1.0, null, 0.30, 0.55, 0.0],                        // the two-bar swell (λ ≈ 21.9 m)
    [-0.05, 1.0, 9.2, 0.10, 0.45, 1.7],
    [-0.80, 1.0, 5.49, 0.055, 0.40, 4.2],                       // one-bar period
    [0.35, 1.0, 3.3, 0.030, 0.35, 2.9],
];
const RIPPLES = [                                              // fragment-only glitter ripples
    [0.9, 1.0, 1.55, 0.012], [-0.6, 1.0, 1.02, 0.009], [0.2, -1.0, 0.71, 0.006],
    [-1.0, 0.3, 0.53, 0.005], [0.7, 0.4, 0.38, 0.0035], [-0.3, 0.9, 0.29, 0.0025],
];

export const FACE = { W: 1.7, hV: 3.0, r0: 3.0 };              // lateral width (m), eye height, first row radius

export async function buildSea(THREE, opts = {}) {
    const {
        Fn, uniform, float, vec2, vec3, vec4, attribute, positionGeometry, positionWorld, cameraPosition,
        modelWorldMatrix, modelWorldMatrixInverse, normalize, dot, mix, clamp, smoothstep, sin, cos, exp, pow, max, min, abs, floor,
        fract, length, atan, log, hash, texture, dFdx, dFdy, reflect, sqrt, step, If,
    } = THREE;
    const { shoreFn, radius = 1500 } = opts;

    // ------------------------------------------------------------------ geometry: polar, dense near her
    const NR = 250, NS = 768, R0 = 2.0;
    const gro = Math.pow(radius / R0, 1 / NR);
    const nV = (NR + 1) * NS;
    const pos = new Float32Array(nV * 3), shore = new Float32Array(nV);
    for (let i = 0; i <= NR; i++) {
        const r = R0 * Math.pow(gro, i);
        for (let j = 0; j < NS; j++) {
            const a = (j / NS) * Math.PI * 2;
            const x = Math.sin(a) * r, z = -Math.cos(a) * r;
            const k = i * NS + j;
            pos[k * 3] = x; pos[k * 3 + 1] = 0; pos[k * 3 + 2] = z;
            shore[k] = shoreFn ? shoreFn(x, z) : 50;
        }
    }
    const idx = [];
    for (let i = 0; i < NR; i++) for (let j = 0; j < NS; j++) {
        const a = i * NS + j, b = i * NS + (j + 1) % NS, c = (i + 1) * NS + j, d = (i + 1) * NS + (j + 1) % NS;
        // drop quads buried well inside the land (the land mesh covers them)
        if (Math.max(shore[a], shore[b], shore[c], shore[d]) < -4) continue;
        idx.push(a, b, c, b, d, c);                            // CCW seen from above (+y)
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('shore', new THREE.BufferAttribute(shore, 1));
    geo.setIndex(idx);
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), radius + 10);

    // ------------------------------------------------------------------ the atlas (fragment only)
    const N = 8;
    await initCanvas();
    const atlasPx = drawFaceAtlas(makeCanvas, { n: N, cell: 256, seed: 11 });
    const atlas = dataTexture(THREE, atlasPx.data, atlasPx.w, atlasPx.h, { srgb: false, wrap: 'clamp', mips: true, aniso: 8 });

    // ------------------------------------------------------------------ uniforms
    const U = {
        t: uniform(0), reveal: uniform(0), glow: uniform(1), relief: uniform(1), calm: uniform(1),
        moonW: uniform(new THREE.Vector3(0, 0.2, -1).normalize()), moonCol: uniform(new THREE.Color(0.75, 0.82, 1.0)),
        moonI: uniform(1.0),
        zen: uniform(new THREE.Color(0.012, 0.02, 0.06)), hor: uniform(new THREE.Color(0.05, 0.055, 0.11)),
        porchW: uniform(new THREE.Vector3()), porch: uniform(0), porchCol: uniform(new THREE.Color(1.0, 0.62, 0.3)),
        winW: uniform(new THREE.Vector3()), win: uniform(0),
        fog: uniform(0.0011),
    };

    // ------------------------------------------------------------------ the swells (analytic)
    const waveSet = SWELLS.map(([dx, dz, L, A, Q, ph]) => {
        const n = Math.hypot(dx, dz);
        const omega = L === null ? 2 * Math.PI / MAIN_T : Math.sqrt(G * 2 * Math.PI / L);
        const k = L === null ? omega * omega / G : 2 * Math.PI / L;
        return { dx: dx / n, dz: dz / n, k, omega, A, Q, ph };
    });
    const main = waveSet[0];
    // displacement + (GPU Gems) normal terms at rest position p, amplitude scaled by damp; also hands back
    // the main swell's sin/cos (and the second swell's sin) so the faces ride the crests without recomputing
    const swell = (p, t, damp) => {
        let dx = float(0), dy = float(0), dz = float(0), nx = float(0), ny = float(0), nz = float(0);
        let s0 = null, c0 = null, s1 = null;
        waveSet.forEach((w, i) => {
            const th = p.x.mul(w.dx).add(p.y.mul(w.dz)).mul(w.k).sub(t.mul(w.omega)).add(w.ph);
            const c = cos(th), s = sin(th);
            if (i === 0) { s0 = s; c0 = c; }
            if (i === 1) s1 = s;
            const A = damp.mul(w.A);
            dx = dx.add(A.mul(w.Q * w.dx).mul(c));
            dz = dz.add(A.mul(w.Q * w.dz).mul(c));
            dy = dy.add(A.mul(s));
            nx = nx.add(A.mul(w.dx * w.k).mul(c));
            nz = nz.add(A.mul(w.dz * w.k).mul(c));
            ny = ny.add(A.mul(w.Q * w.k).mul(s));
        });
        return { disp: vec3(dx, dy, dz), n: vec3(nx.negate(), float(1).sub(ny), nz.negate()), s0, c0, s1 };
    };
    const mainPhase = (p, t) => p.x.mul(main.dx).add(p.y.mul(main.dz)).mul(main.k).sub(t.mul(main.omega)).add(main.ph);

    // ------------------------------------------------------------------ the faces (analytic relief)
    const { W, hV, r0 } = FACE;
    const DL = W / hV;                                          // row height in ln r
    const LR0 = Math.log(r0);
    const L = LAYOUT;
    // face units: x,y in [-.5,.5]; relief height (~0..0.3) AND its gradient, in one pass
    const GAUSS = [   // [cx, cy, sx, sy, amplitude, smileShifted]
        [0, 0.13, 0.19, 0.035, 0.035, 0], [L.eyeX, L.eyeY, 0.06, 0.04, -0.045, 0], [-L.eyeX, L.eyeY, 0.06, 0.04, -0.045, 0],
        [L.eyeX, L.eyeY - 0.004, 0.048, 0.026, 0.03, 0], [-L.eyeX, L.eyeY - 0.004, 0.048, 0.026, 0.03, 0],
        [0, 0.01, 0.026, 0.085, 0.05, 0], [0, L.noseTipY, 0.04, 0.03, 0.075, 0],
        [0.036, -0.093, 0.02, 0.016, 0.022, 0], [-0.036, -0.093, 0.02, 0.016, 0.022, 0],
        [0.15, -0.055, 0.075, 0.065, 0.03, 0], [-0.15, -0.055, 0.075, 0.065, 0.03, 0],
        [0, L.mouthY + 0.022, 0.062, 0.016, 0.028, 1], [0, L.mouthY, 0.068, 0.007, -0.018, 1], [0, L.mouthY - 0.022, 0.055, 0.02, 0.03, 1],
        [0, L.chinY + 0.06, 0.055, 0.04, 0.03, 0],
    ];
    const faceHG = (x, y, smile, withGrad = true) => {
        const qx = x.div(L.headA), qy = y.sub(L.headCY).div(L.headB);
        const sd = clamp(float(1).sub(qx.mul(qx)).sub(qy.mul(qy)), 0, 1);
        let h = sd.mul(sd).mul(0.16);                                             // the brow-to-chin dome
        let hx = withGrad ? sd.mul(0.32).mul(x.mul(-2 / (L.headA * L.headA))) : null;
        let hy = withGrad ? sd.mul(0.32).mul(y.sub(L.headCY).mul(-2 / (L.headB * L.headB))) : null;
        const k = smile.mul(2.4);
        const ys = y.sub(x.mul(x).mul(k));                                        // smile lifts the corners
        for (const [cx, cy, sx, sy, a, sm] of GAUSS) {
            const yy = sm ? ys : y;
            const u = x.sub(cx).div(sx), v = yy.sub(cy).div(sy);
            const g = exp(u.mul(u).add(v.mul(v)).negate()).mul(a);
            h = h.add(g);
            if (withGrad) {
                const gv = g.mul(v.mul(-2 / sy));
                hx = hx.add(g.mul(u.mul(-2 / sx)));
                if (sm) hx = hx.add(gv.mul(x.mul(k).mul(-2)));
                hy = hy.add(gv);
            }
        }
        return { h, hx, hy };
    };
    // anamorphic cell mapping around her eye point (design-frame origin), with its Jacobian
    const cellOf = (p, Wl = W, so = 0) => {
        const DLl = Wl / hV;
        const r2 = max(dot(p, p), 0.25);
        const r = sqrt(r2);
        const vR = log(r).sub(LR0).div(DLl);                                      // continuous row coordinate
        const row = floor(vR);
        const rRow = exp(row.add(0.5).mul(DLl).add(LR0));
        const th = atan(p.x, p.y.negate());                                       // branch cut landward (+z)
        const off = hash(row.add(64 + so).mul(37.0)).mul(9.0);
        const sC = th.mul(rRow).div(Wl).add(off);                                 // continuous lateral coordinate
        const col = floor(sC);
        const seed = col.add(4096 + so).mul(131.0).add(row.add(64).mul(7919.0));
        const h1 = hash(seed), h2 = hash(seed.add(17.0)), h3 = hash(seed.add(41.0)), h4 = hash(seed.add(73.0));
        const scl = h2.mul(0.26).add(0.74);
        const tilt = h3.sub(0.5).mul(0.4);
        const ct = cos(tilt), st = sin(tilt);
        const lu = fract(sC).sub(0.5), lv = vR.sub(row).sub(0.5).sub(h4.sub(0.5).mul(float(1).sub(scl)).mul(0.9));
        const present = step(0.16, hash(seed.add(97.0)));                         // some cells stay open water
        const x = lu.mul(ct).sub(lv.mul(st)).div(scl), y = lu.mul(st).add(lv.mul(ct)).div(scl);
        // d(lu)/dp and d(lv)/dp, then d(x,y)/dp
        const dLu = vec2(p.y.negate(), p.x).div(r2).mul(rRow.div(Wl));
        const dLv = p.div(r2).div(DLl);
        const dX = dLu.mul(ct).sub(dLv.mul(st)).div(scl), dY = dLu.mul(st).add(dLv.mul(ct)).div(scl);
        // the cell centre in the design frame (for the swell phase at the face)
        const thC = col.add(0.5).sub(off).mul(Wl).div(rRow);
        const pc = vec2(sin(thC), cos(thC).negate()).mul(rRow);
        return { r, vR, row, rRow, sC, col, h1, h2, h3, h4, scl, ct, st, x, y, pc, present, dX, dY };
    };
    const revealK = (r) => {
        const rf = pow(float(radius / r0), U.reveal).mul(r0);                     // exponential sweep outward
        return smoothstep(rf, rf.mul(0.82), r).mul(step(0.001, U.reveal));
    };
    const revealWave = (r) => {                                                   // the bright front of the sweep
        const rf = pow(float(radius / r0), U.reveal).mul(r0);
        const x = r.sub(rf.mul(0.9)).div(rf.mul(0.13).add(0.6));
        return exp(x.mul(x).negate()).mul(step(0.001, U.reveal)).mul(float(1).sub(smoothstep(0.93, 1.0, U.reveal)));
    };
    const emergeK = (c, t) => smoothstep(-0.15, 0.85, sin(mainPhase(c.pc, t).add(c.h4.mul(1.4)).sub(0.7)));
    // a face surfaces where a crest runs through it: coherent crest lines near, per-face breathing far
    // (sw: the swell terms at this point, reused: sin(th - 0.35) = s0 cos .35 - c0 sin .35)
    const crestK = (sw, c, t) => {
        const pix = smoothstep(-0.35, 0.8, sw.s0.mul(Math.cos(0.35)).sub(sw.c0.mul(Math.sin(0.35))));
        const near = pix.mul(sw.s1.mul(0.25).add(0.75));
        return mix(near, emergeK(c, t), smoothstep(45.0, 160.0, c.r)).mul(c.present);
    };
    // world-height relief (m) + its gradient over the design-frame xz
    const relief = (c, sw, t, damp, withGrad) => {
        const inside = smoothstep(0.5, 0.44, max(abs(c.x), abs(c.y)));
        const f = faceHG(c.x, c.y, c.h1.mul(0.5).add(0.15), withGrad);
        const A = inside.mul(crestK(sw, c, t)).mul(revealK(c.r)).mul(c.h3.mul(0.5).add(0.7)).mul(U.relief).mul(damp).mul(c.scl.mul(W));
        return { h: f.h.mul(A), g: withGrad ? c.dX.mul(f.hx).add(c.dY.mul(f.hy)).mul(A) : null };
    };

    // ------------------------------------------------------------------ material
    const mat = new THREE.MeshBasicNodeMaterial({ side: THREE.FrontSide });
    mat.name = 'ocean_of_faces';
    mat.positionNode = Fn(() => {
        const p = positionGeometry.xz;
        const shoreV = attribute('shore', 'float');
        const sw = swell(p, U.t, smoothstep(0.0, 9.0, shoreV).mul(U.calm));
        const fh = relief(cellOf(p), sw, U.t, smoothstep(0.5, 6.0, shoreV), false).h;
        return vec3(p.x.add(sw.disp.x), sw.disp.y.add(fh), p.y.add(sw.disp.z));
    })();

    mat.colorNode = Fn(() => {
        const p = positionGeometry.xz.toVar();
        const shoreD = attribute('shore', 'float');
        const damp = smoothstep(0.0, 9.0, shoreD).mul(U.calm);
        const fdamp = smoothstep(0.5, 6.0, shoreD);
        const sw = swell(p, U.t, damp);
        const c = cellOf(p);
        const rel = relief(c, sw, U.t, fdamp, true);
        let nL = sw.n.add(vec3(rel.g.x.negate(), 0, rel.g.y.negate()));
        // glitter ripples, faded with distance so they never alias into crawl
        const dist = length(positionWorld.sub(cameraPosition)).toVar();
        const ripK = smoothstep(260.0, 25.0, dist);
        let rx = float(0), rz = float(0);
        for (const [dx, dz, lam, a] of RIPPLES) {
            const n = Math.hypot(dx, dz), k = 2 * Math.PI / lam, om = Math.sqrt(G * k);
            const th = p.x.mul(dx / n).add(p.y.mul(dz / n)).mul(k).sub(U.t.mul(om));
            const cc = cos(th).mul(a * k);
            rx = rx.add(cc.mul(dx / n)); rz = rz.add(cc.mul(dz / n));
        }
        nL = nL.add(vec3(rx.negate(), 0, rz.negate()).mul(ripK));
        const nW = normalize(modelWorldMatrix.mul(vec4(nL, 0)).xyz).toVar();
        const Vd = normalize(cameraPosition.sub(positionWorld)).toVar();
        const cosV = max(dot(nW, Vd), 0.0);
        const F = float(0.02).add(pow(float(1).sub(cosV), 5.0).mul(0.98)).toVar();
        const Rr = reflect(Vd.negate(), nW).toVar();
        // the night sky seen in the water: palette gradient + the moon's halo and disc glint
        const ry = max(Rr.y, 0.0);
        const sky = mix(vec3(U.hor), vec3(U.zen), pow(ry, 0.5));
        const md = max(dot(Rr, U.moonW), 0.0);
        const moonGl = pow(md, 2600.0).mul(2.4).add(pow(md, 220.0).mul(0.05)).add(pow(md, 16.0).mul(0.012));
        const col = sky.mul(F).add(vec3(U.moonCol).mul(moonGl).mul(U.moonI).mul(F.mul(0.6).add(0.4))).toVar();
        // the water body: near-black blue, lifted a touch on crests facing the moon
        const body = vec3(0.0016, 0.0048, 0.0085).add(vec3(U.moonCol).mul(max(sw.disp.y, 0.0).mul(0.02)));
        col.addAssign(body.mul(float(1).sub(F)));
        // ---- the faces' light, rising through the surface as they surface
        const inside = step(max(abs(c.x), abs(c.y)), 0.5);
        const kk = floor(c.h1.mul(N * N * 0.999));
        const ay = floor(kk.div(N)), ax = kk.sub(ay.mul(N));
        const refr = vec2(rx, rz).mul(ripK).mul(0.05).div(c.scl);                  // the lines wobble under the ripples
        const cxr = clamp(c.x.add(refr.x), -0.5, 0.5), cyr = clamp(c.y.add(refr.y), -0.5, 0.5);
        const uvA = vec2(ax.add(cxr).add(0.5), ay.add(cyr).add(0.5)).div(N);
        // gradients of the continuous lateral/row coordinates -> face coords -> atlas uv
        const dsx = dFdx(c.sC), dsy = dFdy(c.sC), dvx = dFdx(c.vR), dvy = dFdy(c.vR);
        const gx = vec2(dsx.mul(c.ct).sub(dvx.mul(c.st)), dsx.mul(c.st).add(dvx.mul(c.ct))).div(c.scl.mul(N));
        const gy = vec2(dsy.mul(c.ct).sub(dvy.mul(c.st)), dsy.mul(c.st).add(dvy.mul(c.ct))).div(c.scl.mul(N));
        const A = texture(atlas, uvA).grad(gx, gy);
        const em = crestK(sw, c, U.t).mul(revealK(c.r)).mul(fdamp).mul(inside);
        const hue = c.h2;
        const gold = vec3(1.0, 0.62, 0.26), amber = vec3(1.0, 0.5, 0.2), rose = vec3(1.0, 0.46, 0.4), aqua = vec3(0.3, 0.72, 0.95);
        const tint = mix(mix(mix(gold, amber, smoothstep(0.35, 0.55, hue)), rose, smoothstep(0.78, 0.86, hue)), aqua, smoothstep(0.91, 0.96, hue));
        const lines = A.r.mul(1.0).add(A.g.mul(0.45)).add(A.b.mul(0.05));
        const far = exp(c.r.div(-520.0)).mul(0.7).add(0.3);
        const wave = revealWave(c.r);
        col.addAssign(tint.mul(lines.mul(em).mul(U.glow).mul(far).mul(float(1).sub(F.mul(0.6)))).mul(wave.mul(1.6).add(1.0)).mul(0.62));
        col.addAssign(vec3(1.0, 0.7, 0.36).mul(wave).mul(fdamp).mul(0.035).mul(float(1).sub(F.mul(0.5))));
        // ---- the deep: older, larger faces far below, seen through the water (parallax, blurred, cold)
        const VdL = normalize(modelWorldMatrixInverse.mul(vec4(Vd, 0)).xyz);
        const pd = p.sub(VdL.xz.div(max(VdL.y, 0.12)).mul(1.7));                  // 2.2 m down, refraction-shortened
        const cd = cellOf(pd, W * 2.4, 509);
        const kd = floor(cd.h1.mul(N * N * 0.999));
        const ayd = floor(kd.div(N)), axd = kd.sub(ayd.mul(N));
        const uvD = vec2(axd.add(clamp(cd.x, -0.5, 0.5)).add(0.5), ayd.add(clamp(cd.y, -0.5, 0.5)).add(0.5)).div(N);
        const dsxd = dFdx(cd.sC), dsyd = dFdy(cd.sC), dvxd = dFdx(cd.vR), dvyd = dFdy(cd.vR);
        const gxd = vec2(dsxd.mul(cd.ct).sub(dvxd.mul(cd.st)), dsxd.mul(cd.st).add(dvxd.mul(cd.ct))).div(cd.scl.mul(N / 3.5));
        const gyd = vec2(dsyd.mul(cd.ct).sub(dvyd.mul(cd.st)), dsyd.mul(cd.st).add(dvyd.mul(cd.ct))).div(cd.scl.mul(N / 3.5));
        const Dp = texture(atlas, uvD).grad(gxd, gyd);
        const insideD = step(max(abs(cd.x), abs(cd.y)), 0.5).mul(cd.present);
        const breathe = sin(U.t.mul(0.45).add(cd.h4.mul(6.28))).mul(0.35).add(0.65);
        const deepI = Dp.g.mul(0.8).add(Dp.b.mul(0.3)).mul(insideD).mul(breathe).mul(revealK(cd.r)).mul(fdamp)
            .mul(float(1).sub(F)).mul(exp(cd.r.div(-160.0)));
        col.addAssign(vec3(0.16, 0.46, 0.6).mul(deepI).mul(U.glow).mul(0.2));
        // ---- the porch light and the window, glinting on the cove (only once they are lit)
        If(U.porch.greaterThan(0.001), () => {
            const Lp = normalize(U.porchW.sub(positionWorld));
            const Hp = normalize(Lp.add(Vd));
            const dp = length(U.porchW.sub(positionWorld));
            const nh = max(dot(nW, Hp), 0.0);
            const gP = pow(nh, 700.0).mul(40.0).add(pow(nh, 60.0).mul(0.25));
            col.addAssign(vec3(U.porchCol).mul(gP).mul(U.porch).div(dp.mul(dp).mul(0.012).add(1.0)));
        });
        If(U.win.greaterThan(0.001), () => {
            const Lw = normalize(U.winW.sub(positionWorld));
            const Hw = normalize(Lw.add(Vd));
            const dw = length(U.winW.sub(positionWorld));
            col.addAssign(vec3(1.0, 0.72, 0.42).mul(pow(max(dot(nW, Hw), 0.0), 350.0).mul(10.0)).mul(U.win).div(dw.mul(dw).mul(0.012).add(1.0)));
        });
        // ---- the waterline: foam that runs up and slides back on the swell (only near the shore)
        If(shoreD.lessThan(2.2), () => {
            const swash = sw.s0.mul(0.55);
            const foamBand = smoothstep(1.3, 0.15, shoreD.add(swash)).mul(smoothstep(-0.6, 0.1, shoreD.add(swash)));
            const fn = THREE.mx_noise_float(vec3(p.mul(2.2), U.t.mul(0.35))).mul(0.5).add(0.5);
            const foam = foamBand.mul(smoothstep(0.45, 0.8, fn)).mul(0.55).add(foamBand.mul(0.08));
            col.assign(mix(col, vec3(U.moonCol).mul(0.05), foam));
        });
        // ---- distance haze into the night horizon
        const fk = float(1).sub(exp(dist.mul(U.fog).negate()));
        return vec4(mix(col, vec3(U.hor).mul(1.05), fk.mul(0.92)), 1.0);
    })();

    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = 'ocean_of_faces';
    mesh.frustumCulled = false;
    return { mesh, U, atlas, faceCellInfo: { W, hV, r0, DL } };
}
