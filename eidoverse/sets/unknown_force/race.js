// race.js — UNKNOWN FORCE, VERSES 3+4 (sung 142.48–162.76 s): "the race".
//
// An elevated wet highway at night between dark towers. Two giant billboards face each other across the road,
// $100,000,000 (gold, worship) and $20,000,000 (red, fear), both showing the SAME machine-god face. Marinetti's
// 1908-pattern racing car tears past with two goggled cosplayers, smashes through the roadworks that close the right
// carriageway and flies off the broken end of the deck into the factory drain below, wheels in the air (the 1909
// manifesto's ditch). On "black shirts" the shadows of a marching column, cast by a roadworks floodlight, cross the
// tower wall; on "heel" a boot comes down on the manifesto lying in a puddle.
//
//   const R = await import(new URL('sets/unknown_force/race.js', EIDOVERSE_DIR).href);
//   const race = await R.build(THREE, {});          // → { group, parts, update(t, state), dispose(), cams,
//                                                   //     camAt(name, t, state), focal(name), setActive(on) }
//   scene.add(race.group);
//   race.update(t, { carT, crash, march, heel, ... });   // see RACE.md for every key
//
// Set-local metres, +Y up. The DECK SURFACE is y = 0 (the singer's mark is the origin on the right shoulder, facing
// +Z, down the road toward the roadworks); the ground under the viaduct is y = -6 and the drain's water y = -9.05.
// Everything is deterministic in (t, state). Docs: RACE.md beside this file.

const D = {
    ground: -6.0, deckT: 1.4,
    xR: -2.2, xL: 20.2, xMed: 9.6,                   // deck outer edges and median centre
    zFar: -470, zNear: 270,
    gap0: 92, gap1: 140,                             // the right half of the deck is missing between these (bridge works)
    lanes: [3.6, 7.2, 11.85, 15.45],                 // lane centres (1, 2 = +Z carriageway; 3, 4 = -Z carriageway)
    lampR: { x: -1.9, head: [1.4, 10.15], dz: 34, z0: 0 },
    lampL: { x: 19.9, head: [16.6, 10.15], dz: 34, z0: 17 },
    ch: { z0: 108, z1: 130, b0: 113, b1: 125, bottom: -9.6, water: -9.05 },   // the drain (runs along X)
    billA: { x: 33.5, z: -64, yaw: -0.96, w: 24, h: 16, y: 16 },              // $100,000,000 gold (left of the road, +X)
    billB: { x: -14.5, z: -64, yaw: 0.96, w: 24, h: 16, y: 16 },              // $20,000,000 red (right of the road, -X)
    wall: { x: -22, z0: -6, z1: 76, top: 66 },                                // the shadow wall (faces +X)
    flood: [18.6, 0.12, 40.0],                                                // roadworks floodlight on the deck (casts the march)
    marchX: 13.4,                                                             // the (absent) column walks lane 3
    heel: [-0.55, 0, 9.6],                                                    // the puddle where the boot comes down
    works: { taper0: [-1.3, 28], taper1: [8.7, 58], board: [0.2, 63.5], barrier: 67 },
};
export const LAYOUT = D;
const CAR_LEN = 390.45;               // the car path's length (checked against carPath.getLength() in build)

// ----------------------------------------------------------------------------- suggested choreography (sung times)
// The conductor owns the timeline; this is the cue sheet the probes use, keyed to the vocal stem's word times.
export const CUES = {
    v3: 142.48, race: 143.52, prevent: 146.42, machineGod: 148.64, ends: 151.68,
    v4: 152.18, marinetti: 153.98, speed: 156.10, steel: 156.94, manifesto: 157.46, bow: 159.56,
    lastTime: 160.16, blackShirts: 161.42, heel: 162.42, end: 162.80,
};
const ease = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
const lin = (t, a, b) => Math.min(1, Math.max(0, (t - a) / (b - a)));
// suggest(t) -> { state, cam }: a working cut of the two verses on the song clock (film seconds)
export function suggest(t) {
    const C = CUES;
    const st = { rain: 1, billboards: 1, lamps: 1, gaze: 0, carT: 0, crash: 0, march: 0, heel: 0 };
    // the billboards power up on "hundred million" / "twenty million"
    st.billA = ease(lin(t, C.v3 - 0.4, C.v3 + 0.5));
    st.billB = ease(lin(t, C.prevent - 2.4, C.prevent - 1.6));
    st.gaze = Math.sin(Math.max(0, t - C.machineGod) * 1.3) * ease(lin(t, C.machineGod, C.machineGod + 1));
    // the car runs at a steady 22 m/s and leaves the broken edge just before "bow": it comes out between the
    // billboards on "Down the timeline", passes the singer on "struggle", and is in the drain by "black shirts"
    const tLaunch = C.bow - 0.12;
    // (carT only: update() prefers carS when both are given, so a conductor overriding carT must not meet a carS here)
    st.carT = Math.min(1, Math.max(0, CAR_LEN - 22 * (tLaunch - t)) / CAR_LEN);
    if (t >= tLaunch) st.crash = Math.min(1, (t - tLaunch) / 3.0);
    st.march = ease(lin(t, C.lastTime + 0.5, C.blackShirts - 0.1));        // fully on before its shot cuts in
    st.heel = Math.min(1, Math.max(0, (t - (C.heel - 1.5)) / 2.2));
    // the cut: each amount on its own line, the two faces together on "the same machine god", the car out of the
    // billboards on "Down the timeline", the chase through the works (the barricades go on "make the unknown bow"),
    // off the edge and over into the drain, the march on "black shirts", the heel on "heel"
    let cam = 'billA';
    if (t >= C.v3 + 1.85) cam = 'billB';
    if (t >= C.machineGod - 1.5) cam = 'billboards';
    if (t >= C.ends - 1.85) cam = 'singer';
    if (t >= C.v4) cam = 'carPass';
    if (t >= C.marinetti + 0.9) cam = 'carTrack';
    if (t >= C.speed + 0.1) cam = 'carChase';
    if (t >= tLaunch - 0.15) cam = 'crashLow';         // off the edge on "bow", nose in on "poem", on its back on "ended in"
    if (t >= C.blackShirts - 0.02) cam = 'shadows';    // 161.40: "black shirts and" (0.75 s on the wall)
    if (t >= C.heel - 0.27) cam = 'heel';              // 162.15: the boot hovers; the strike lands on "heel" (162.42)
    if (cam !== 'heel') st.heel = 0;                   // the boot exists only in its own shot (it descends off-screen)
    return { state: st, cam };
}

// ===================================================================================================================
export async function build(THREE, opts = {}) {
    const T = await import('npm:three@0.184.0/tsl');
    const { Fn, If, Loop, uniform, float, int, vec2, vec3, vec4, mix, clamp, smoothstep, step, abs, fract, floor,
        sin, cos, atan, sqrt, pow, exp, max, min, dot, cross, normalize, length, texture, uv, positionWorld,
        positionLocal, positionView, normalWorld, normalView, normalLocal, cameraPosition, attribute, hash, mrt,
        modelViewMatrix, cameraProjectionMatrix, cameraWorldMatrix, dFdx, dFdy, faceDirection, sign, log2,
        reflector, select, inverseSqrt, varying, fwidth, mat3 } = T;

    const group = new THREE.Group();
    group.name = 'set:race';
    const disposables = [];
    const own = (x) => { disposables.push(x); return x; };
    const parts = {};

    // ------------------------------------------------------------------------------------------- tiny helpers
    const rng = (seed) => { let s = (seed >>> 0) || 1; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); };
    const linC = (hex) => { const c = new THREE.Color(hex); return vec3(c.r, c.g, c.b); };   // sRGB hex -> linear vec3
    const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
    const fsPath = (u) => { const p = decodeURIComponent(new URL(u).pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
    const EIDO = globalThis.EIDOVERSE_DIR;
    try {
        const napi = await import('npm:@napi-rs/canvas@0.1.69');
        napi.GlobalFonts.registerFromPath(fsPath(new URL('assets/fonts/Rajdhani-Bold.ttf', EIDO)), 'Rajdhani');
    } catch (e) { console.warn('[race] font registration:', e.message); }
    const cv = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; };
    const canvasTex = (c, { srgb = true, mips = true } = {}) => {
        const t = own(new THREE.CanvasTexture(c));
        t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        if (mips) { t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; }
        t.anisotropy = 8;
        t.needsUpdate = true;
        return t;
    };
    // transparent effect quads keep the scene pass's normal / metal-rough targets untouched (stack-notes.md). Such a
    // material has no colour output of its own once MRT is off, so these are hidden from the reflection pass (noRefl).
    const noRefl = [];
    const noMrt = (m) => { m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) }); return m; };

    // A geometry accumulator: merge many pieces (boxes, three geometries, quads) into one BufferGeometry with
    // position / normal / uv and one vec4 'aux' channel per piece (material variation without extra draw calls).
    class GB {
        constructor() { this.p = []; this.n = []; this.u = []; this.a = []; this.i = []; this.v = 0; }
        add(geo, m = null, aux = [0, 0, 0, 0], uvFn = null) {
            const g = geo.index ? geo : geo;
            const P = g.attributes.position, N = g.attributes.normal, UV = g.attributes.uv;
            const nm = m ? new THREE.Matrix3().getNormalMatrix(m) : null;
            const v = new THREE.Vector3(), w = new THREE.Vector3();
            for (let k = 0; k < P.count; k++) {
                v.fromBufferAttribute(P, k); if (m) v.applyMatrix4(m);
                this.p.push(v.x, v.y, v.z);
                if (N) { w.fromBufferAttribute(N, k); if (nm) w.applyMatrix3(nm).normalize(); this.n.push(w.x, w.y, w.z); } else this.n.push(0, 1, 0);
                if (uvFn) { const q = uvFn(v, w, k); this.u.push(q[0], q[1]); } else if (UV) this.u.push(UV.getX(k), UV.getY(k)); else this.u.push(0, 0);
                this.a.push(aux[0], aux[1], aux[2], aux[3]);
            }
            if (g.index) for (let k = 0; k < g.index.count; k++) this.i.push(this.v + g.index.getX(k));
            else for (let k = 0; k < P.count; k++) this.i.push(this.v + k);
            this.v += P.count;
            geo.dispose();
            return this;
        }
        // a quad p0..p3 (counter-clockwise seen from the front), uv in metres along (p0->p1, p0->p3)
        quad(p0, p1, p2, p3, aux = [0, 0, 0, 0], uv0 = [0, 0], uvScale = 1) {
            const e1 = p1.clone().sub(p0), e2 = p3.clone().sub(p0);
            const n = e1.clone().cross(e2).normalize();
            const L1 = e1.length() * uvScale, L2 = e2.length() * uvScale;
            const uvs = [[uv0[0], uv0[1]], [uv0[0] + L1, uv0[1]], [uv0[0] + L1, uv0[1] + L2], [uv0[0], uv0[1] + L2]];
            [p0, p1, p2, p3].forEach((p, k) => { this.p.push(p.x, p.y, p.z); this.n.push(n.x, n.y, n.z); this.u.push(uvs[k][0], uvs[k][1]); this.a.push(...aux); });
            this.i.push(this.v, this.v + 1, this.v + 2, this.v, this.v + 2, this.v + 3);
            this.v += 4;
            return this;
        }
        build() {
            const g = new THREE.BufferGeometry();
            g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3));
            g.setAttribute('normal', new THREE.Float32BufferAttribute(this.n, 3));
            g.setAttribute('uv', new THREE.Float32BufferAttribute(this.u, 2));
            g.setAttribute('aux', new THREE.Float32BufferAttribute(this.a, 4));
            g.setIndex(this.v > 65535 ? new THREE.Uint32BufferAttribute(this.i, 1) : new THREE.Uint16BufferAttribute(this.i, 1));
            g.computeBoundingSphere(); g.computeBoundingBox();
            return own(g);
        }
    }
    const M4 = (x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1) =>
        new THREE.Matrix4().compose(V3(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz)), V3(sx, sy, sz));
    // a box from min/max corners, uv in metres per face (u along the face's horizontal, v = height)
    const boxQuads = (gb, x0, y0, z0, x1, y1, z1, aux, { top = true, bottom = false, sides = [1, 1, 1, 1] } = {}) => {
        const p = (x, y, z) => V3(x, y, z);
        if (sides[0]) gb.quad(p(x1, y0, z1), p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), aux, [-z1, y0]);   // +X face
        if (sides[1]) gb.quad(p(x0, y0, z0), p(x0, y0, z1), p(x0, y1, z1), p(x0, y1, z0), aux, [z0, y0]);    // -X face
        if (sides[2]) gb.quad(p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1), aux, [x0, y0]);    // +Z face
        if (sides[3]) gb.quad(p(x1, y0, z0), p(x0, y0, z0), p(x0, y1, z0), p(x1, y1, z0), aux, [-x1, y0]);   // -Z face
        if (top) gb.quad(p(x0, y1, z1), p(x1, y1, z1), p(x1, y1, z0), p(x0, y1, z0), aux, [x0, -z1]);
        if (bottom) gb.quad(p(x0, y0, z0), p(x1, y0, z0), p(x1, y0, z1), p(x0, y0, z1), aux, [x0, z0]);
    };

    // ------------------------------------------------------------------------------------------- uniforms
    const U = {
        time: uniform(0), setInv: uniform(new THREE.Matrix4()),
        rain: uniform(1), wet: uniform(1), lamps: uniform(1),
        billA: uniform(1), billB: uniform(1), gaze: uniform(0),
        march: uniform(0), marchT: uniform(0),
        crashAge: uniform(-10), crashP: uniform(new THREE.Vector3(1.6, D.ch.water, 121)),
        flipAge: uniform(-10), flipP: uniform(new THREE.Vector3(1.6, D.ch.water, 124)),
        heelAge: uniform(-10), works: uniform(1),
        smear: uniform(0), chainRun: uniform(0), scarfSpeed: uniform(0), carShadow: uniform(0),
        steam: uniform(0), steamP: uniform(new THREE.Vector3(1.6, D.ch.water, 120)), headlamps: uniform(1), heelKey: uniform(0),
    };
    // set-local position / normal / camera (the conductor may park the group anywhere)
    const PL = U.setInv.mul(vec4(positionWorld, 1.0)).xyz;
    const NL = normalize(U.setInv.mul(vec4(normalWorld, 0.0)).xyz);
    const CL = U.setInv.mul(vec4(cameraPosition, 1.0)).xyz;

    // screen-space bump from a procedural height in metres (Mikkelsen's surface-gradient method, unnormalised so the
    // relief is physically scaled) -> a VIEW-space normal for material.normalNode
    const bumpN = (h, scale = 1) => {
        const dhx = dFdx(h).mul(scale), dhy = dFdy(h).mul(scale);
        const sx = dFdx(positionView), sy = dFdy(positionView);
        const R1 = cross(sy, normalView), R2 = cross(normalView, sx);
        const det = dot(sx, R1).mul(faceDirection);
        const grad = sign(det).mul(dhx.mul(R1).add(dhy.mul(R2)));
        return normalize(abs(det).mul(normalView).sub(grad));
    };

    // ------------------------------------------------------------------------------------------- noise atlas
    // 256² tiling value-noise atlas, built once: R fbm (breakup), G ridged (cracks/streaks), B fine grain, A blotches
    const noiseTex = (() => {
        const N = 256, data = new Uint8Array(N * N * 4);
        const latCache = new Map();
        const lat = (seed, P) => {
            const k = seed + ':' + P; if (latCache.has(k)) return latCache.get(k);
            const r = rng(seed * 7919 + P), a = new Float32Array(P * P); for (let i = 0; i < P * P; i++) a[i] = r();
            latCache.set(k, a); return a;
        };
        const vn = (a, P, x, y) => {
            const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
            const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
            const g = (i, j) => a[(((j % P) + P) % P) * P + (((i % P) + P) % P)];
            return (g(xi, yi) * (1 - sx) + g(xi + 1, yi) * sx) * (1 - sy) + (g(xi, yi + 1) * (1 - sx) + g(xi + 1, yi + 1) * sx) * sy;
        };
        const fbm = (seed, base, oct, x, y) => {
            let s = 0, w = 0.5, tot = 0;
            for (let o = 0; o < oct; o++) { const P = base << o; s += w * vn(lat(seed + o, P), P, (x * P) / N, (y * P) / N); tot += w; w *= 0.5; }
            return s / tot;
        };
        for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
            const i = (y * N + x) * 4;
            const r = fbm(11, 4, 5, x, y);
            const g = 1 - Math.abs(2 * fbm(23, 8, 4, x, y) - 1);
            const b = fbm(37, 64, 2, x, y);
            const a = fbm(51, 2, 4, x, y);
            const c = (v) => Math.max(0, Math.min(255, Math.round(((v - 0.5) * 1.6 + 0.5) * 255)));
            data[i] = c(r); data[i + 1] = c(g); data[i + 2] = c(b); data[i + 3] = c(a);
        }
        const t = own(new THREE.DataTexture(data, N, N, THREE.RGBAFormat, THREE.UnsignedByteType));
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true;
        t.colorSpace = THREE.NoColorSpace;
        t.needsUpdate = true;
        return t;
    })();
    const nz = (p2, scale = 1) => texture(noiseTex, p2.mul(scale));      // vec4 noise at a 2D coordinate (tiles)

    // ------------------------------------------------------------------------------------------- night environment
    // A procedural night-city equirect (Uint8, sRGB; the safe IBL path on this stack): navy zenith, sodium haze at the
    // horizon, a skyline band of dark towers with lit windows and a few neon blooms, a dark wet ground. Every lit
    // material in the set reflects THIS, never the conductor's daylight.
    const envTex = (() => {
        const W = 512, H = 256, data = new Uint8Array(W * H * 4), r = rng(4242);
        const sky = [];                                   // skyline heights per azimuth column
        let h = 0.05;
        for (let x = 0; x < W; x++) { if (r() < 0.12) h = 0.02 + Math.pow(r(), 1.6) * 0.22; sky.push(h); }
        const neon = Array.from({ length: 22 }, () => ({ x: r() * W, y: 0.02 + r() * 0.14, s: 2 + r() * 5, c: r() < 0.5 ? [1.0, 0.25, 0.75] : [0.15, 0.85, 1.0] }));
        const enc = (v) => Math.round(255 * Math.min(1, Math.max(0, v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055)));
        for (let y = 0; y < H; y++) {
            const el = ((y + 0.5) / H - 0.5) * Math.PI;           // row 0 = straight down (DataTexture rows are bottom-up)
            const s = Math.sin(el);
            for (let x = 0; x < W; x++) {
                let c;
                if (s > 0) {
                    const k = Math.pow(s, 0.45);
                    c = [0.075 * (1 - k) + 0.004 * k, 0.040 * (1 - k) + 0.006 * k, 0.045 * (1 - k) + 0.014 * k];
                    const cl = Math.max(0, Math.sin(x * 0.05 + Math.sin(x * 0.013) * 3) * 0.5 + 0.5) * Math.exp(-s * 6) * 0.05;
                    c = [c[0] + cl * 0.9, c[1] + cl * 0.45, c[2] + cl * 0.35];
                    if (s < sky[x]) {                                  // towers against the haze
                        const lit = r() < 0.18 ? 1 : 0;
                        const warm = r() < 0.6;
                        c = [0.008 + lit * (warm ? 0.55 : 0.25), 0.009 + lit * (warm ? 0.32 : 0.40), 0.012 + lit * (warm ? 0.16 : 0.55)];
                    }
                } else {
                    const k = Math.pow(-s, 0.6);
                    c = [0.035 * (1 - k) + 0.006 * k, 0.020 * (1 - k) + 0.006 * k, 0.018 * (1 - k) + 0.008 * k];
                    if (-s < 0.12 && r() < 0.02) c = [0.5, 0.26, 0.09];   // street lights below
                }
                for (const n of neon) {
                    const dx = Math.min(Math.abs(x - n.x), W - Math.abs(x - n.x)), dy = (s - n.y) * H / Math.PI;
                    const g = Math.exp(-(dx * dx + dy * dy) / (n.s * n.s));
                    c = [c[0] + n.c[0] * g * 0.9, c[1] + n.c[1] * g * 0.9, c[2] + n.c[2] * g * 0.9];
                }
                const i = (y * W + x) * 4;
                data[i] = enc(c[0]); data[i + 1] = enc(c[1]); data[i + 2] = enc(c[2]); data[i + 3] = 255;
            }
        }
        const t = own(new THREE.DataTexture(data, W, H, THREE.RGBAFormat, THREE.UnsignedByteType));
        t.mapping = THREE.EquirectangularReflectionMapping;
        t.colorSpace = THREE.SRGBColorSpace;
        t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter; t.generateMipmaps = true;
        t.needsUpdate = true;
        return t;
    })();
    const ENV = texture(envTex);
    const lit = (m, envI = 1) => { m.envNode = ENV; m.envMapIntensity = envI; m.fog = true; return own(m); };

    // ------------------------------------------------------------------------------------------- light field
    // The highway's sodium lamps, evaluated analytically (no light objects: two staggered rows of 30-odd heads would
    // cost every material in the film). Lamps are occluded by the deck slab for anything below it.
    const SODIUM = linC('#ffab5c');
    const LAMP_I = opts.lampI ?? 140.0;          // a 250 W sodium head, in this renderer's units (E ~ 1.4 under it)
    const lampOne = (P, N, L) => {
        const d = L.sub(P);
        const d2 = max(dot(d, d), 0.25);
        const l = d.mul(inverseSqrt(d2));
        const ndl = max(dot(N, l), 0.0).mul(0.85).add(0.15);           // a little wrap: rain haze softens the terminator
        const cone = smoothstep(0.18, 0.72, l.y);                       // cobra heads throw light down and out
        // the deck slab shadows the ground and the tower bases below it
        const tY = clamp(float(-0.7).sub(P.y).div(L.y.sub(P.y).max(1e-3)), 0.0, 1.0);
        const xc = P.x.add(L.x.sub(P.x).mul(tY));
        const zc = P.z.add(L.z.sub(P.z).mul(tY));
        const under = step(P.y, -0.8).mul(step(D.xR, xc)).mul(step(xc, D.xL)).mul(step(D.zFar, zc))
            .mul(float(1.0).sub(step(D.gap0, zc).mul(step(zc, D.gap1)).mul(step(xc, D.xMed - 0.6))));
        return ndl.mul(cone).mul(float(1.0).sub(under)).div(d2);
    };
    const lampField = Fn(([P, N]) => {
        const acc = float(0).toVar();
        const kR = floor(P.z.div(D.lampR.dz).add(0.5));
        for (const o of [-1, 0, 1]) {
            const k = kR.add(o), z = k.mul(D.lampR.dz);
            const on = step(z, D.gap0 + 0.5).mul(step(D.zFar + 10, z));
            acc.addAssign(lampOne(P, N, vec3(D.lampR.head[0], D.lampR.head[1], z)).mul(on));
        }
        const kL = floor(P.z.sub(D.lampL.z0).div(D.lampL.dz).add(0.5));
        for (const o of [-1, 0, 1]) {
            const z = kL.add(o).mul(D.lampL.dz).add(D.lampL.z0);
            acc.addAssign(lampOne(P, N, vec3(D.lampL.head[0], D.lampL.head[1], z)).mul(step(D.zFar + 10, z)));
        }
        return acc.mul(U.lamps).mul(LAMP_I);
    });
    // the roadworks floodlight that throws the march onto the wall: a low, wide beam aimed across the road
    const FLOOD = vec3(...D.flood);
    const FLOOD_AXIS = normalize(vec3(D.wall.x - D.flood[0], 10.0 - D.flood[1], 38.0 - D.flood[2]));
    const floodField = Fn(([P, N]) => {
        const d = FLOOD.sub(P);
        const d2 = max(dot(d, d), 1.0);
        const l = d.mul(inverseSqrt(d2));
        const ndl = max(dot(N, l), 0.0);
        const cosA = dot(l.negate(), FLOOD_AXIS);
        const cone = smoothstep(0.66, 0.93, cosA);
        return ndl.mul(cone).div(d2).mul(7600.0);
    });

    // ------------------------------------------------------------------------------------------- the march
    // On "black shirts": the shadows of a marching column cross the tower wall. There are no bodies: the column is a
    // walk-cycle atlas on a vertical plane in lane 3, and every wall the floodlight reaches looks up that plane along
    // the light ray (a true projection, so the shadows grow with distance and soften with it). Lockstep, rifles and
    // banners (blank: no symbols), peaked caps, breeches and tall boots: the 1922 silhouette, not a costume.
    const MARCH = { sp: 1.05, speed: 1.5, light: 0.06, frames: 8 };
    const marchTex = (() => {
        const FW = 128, FH = 256, NF = MARCH.frames;
        const [c, g] = cv(FW * NF, FH * 2);
        g.fillStyle = '#000'; g.fillRect(0, 0, FW * NF, FH * 2);
        g.fillStyle = '#fff'; g.strokeStyle = '#fff'; g.lineCap = 'round'; g.lineJoin = 'round';
        const seg = (ax, ay, bx, by, w) => { g.lineWidth = w; g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke(); };
        // one marcher facing LEFT (the column walks toward -Z, which is -u on the plane); ground at row 248
        const fig = (ox, oy, f, kind) => {
            const ph = (f / NF) * Math.PI * 2;
            const bob = -3 * Math.abs(Math.sin(ph));
            const hipX = ox + 64, hipY = oy + 128 + bob;
            const lean = 0.08;
            const shX = hipX - Math.sin(lean) * 62, shY = hipY - 62;
            // legs: thigh swing, knee flex on the forward swing; breeches flare at the thigh, boots to the knee
            for (const [s, far] of [[0, 1], [Math.PI, 0]]) {
                const a = Math.sin(ph + s) * 0.48;
                const k = Math.max(0, Math.sin(ph + s + 0.9)) * 0.75;
                const kx = hipX - Math.sin(a) * 54, ky = hipY + Math.cos(a) * 54;
                const fx = kx - Math.sin(a - k) * 56, fy = ky + Math.cos(a - k) * 56;
                g.globalAlpha = far ? 0.92 : 1;
                seg(hipX, hipY, kx, ky, 24);                       // breeches
                seg(hipX - 4, hipY + 18, (hipX + kx) / 2 + 6, (hipY + ky) / 2, 30);   // the flare
                seg(kx, ky, fx, fy, 17);                           // boot shaft
                seg(fx + 6, fy + 2, fx - 18, fy + 4, 9);           // the foot, toe forward (left)
                g.globalAlpha = 1;
            }
            // torso: a belted tunic, chest out
            g.beginPath(); g.moveTo(hipX - 16, hipY + 6); g.lineTo(hipX + 14, hipY + 4); g.lineTo(shX + 15, shY - 2); g.lineTo(shX - 17, shY + 2); g.closePath(); g.fill();
            // head, cap with a peak
            const hx = shX - 4, hy = shY - 24;
            g.beginPath(); g.arc(hx, hy, 13, 0, Math.PI * 2); g.fill();
            seg(hx - 2, shY - 2, hx, hy + 8, 12);                // neck
            if (kind === 0) { g.fillRect(hx - 14, hy - 17, 26, 9); seg(hx - 13, hy - 8, hx - 25, hy - 6, 4); }   // peaked cap
            else { g.fillRect(hx - 11, hy - 21, 21, 12); seg(hx + 9, hy - 19, hx + 15, hy - 6, 3); }               // tall cap, tassel
            // arms: stiff swing; the far shoulder carries a rifle or a banner pole
            const aA = -Math.sin(ph) * 0.5;
            const ex = shX - Math.sin(aA) * 34, ey = shY + 6 + Math.cos(aA) * 34;
            seg(shX, shY + 6, ex, ey, 11); seg(ex, ey, ex - Math.sin(aA - 0.25) * 30, ey + Math.cos(aA - 0.25) * 30, 9);
            if (kind === 0) { seg(shX + 6, shY + 2, shX + 34, shY + 52, 7); seg(shX + 8, shY + 4, shX - 40, shY - 70, 5); }   // rifle on the shoulder
            else {                                                                                                           // a blank banner
                seg(shX + 2, shY + 30, shX - 6, shY - 105, 5);
                g.beginPath(); g.moveTo(shX - 6, shY - 104); g.lineTo(shX + 46, shY - 92); g.lineTo(shX + 40, shY - 64); g.lineTo(shX - 4, shY - 70); g.closePath(); g.fill();
            }
        };
        for (let row = 0; row < 2; row++) for (let f = 0; f < NF; f++) fig(f * FW, row * FH, f, row);
        return canvasTex(c, { srgb: false, mips: true });
    })();
    const marchAt = (P, xm, zOff) => {
        const L = FLOOD;
        const denom = P.x.sub(L.x);
        const tP = float(xm - D.flood[0]).div(denom.add(select(denom.abs().lessThan(1e-4), float(1e-4), float(0.0))));
        const valid = step(0.02, tP).mul(step(tP, 0.985));
        const Q = L.add(P.sub(L).mul(tP));
        const cz = Q.z.add(U.marchT.mul(MARCH.speed)).add(zOff).div(MARCH.sp);
        const idx = floor(cz), fx = fract(cz);
        const frame = floor(fract(U.marchT).mul(MARCH.frames));               // lockstep: everyone on the same foot
        const row = step(0.72, hash(idx.abs().add(11.0)));                      // one in four carries a banner
        const sv = Q.y.div(2.0);
        const inS = step(0.0, sv).mul(step(sv, 0.999));
        const su = frame.add(clamp(fx, 0.02, 0.98)).div(MARCH.frames);
        const cvv = float(1.0).sub(sv).add(row).mul(0.5);
        const pen = float(MARCH.light).mul(float(1.0).sub(tP));                 // penumbra (m) on the marchers' plane
        const lod = log2(max(pen.mul(128.0), 1.0));
        return texture(marchTex, vec2(su, cvv)).level(lod).r.mul(valid).mul(inS);
    };
    const marchShadowFn = Fn(([P]) => max(marchAt(P, D.marchX, 0.0), marchAt(P, D.marchX - 1.3, 0.52)).mul(U.march));
    parts.march = { texture: marchTex, plane: D.marchX, flood: D.flood };

    // ------------------------------------------------------------------------------------------- work lights
    // The bridge works light the gap and the drain below it (and so the crash): two masts of LED floods and one on
    // the far bank, evaluated analytically like the street lamps. [position, aim, cos(inner), cos(outer), intensity]
    const WORK = [
        [[-0.8, 7.5, 86.0], [0.12, -0.62, 0.78], 0.80, 0.45, 1500.0],
        [[7.6, 7.5, 86.5], [-0.25, -0.66, 0.70], 0.80, 0.45, 1200.0],
        [[-6.0, -1.5, 133.5], [0.35, -0.42, -0.84], 0.82, 0.50, 900.0],
        // the heel's close key: low from behind-left, a hard rim on wet leather (on only for the stamp)
        [[D.heel[0] - 1.9, 1.15, D.heel[2] - 1.7], [0.69, -0.42, 0.59], 0.93, 0.78, 15.0, 'heelKey'],
    ];
    const WORK_COL = linC('#dfe9ff');
    const workField = Fn(([P, N]) => {
        const acc = float(0).toVar();
        for (const [p, a, ci, co, I, key] of WORK) {
            const L = vec3(...p);
            const d = L.sub(P);
            const d2 = max(dot(d, d), 1.0);
            const l = d.mul(inverseSqrt(d2));
            const ndl = max(dot(N, l), 0.0).mul(0.8).add(0.2);
            const cone = smoothstep(co, ci, dot(l.negate(), normalize(vec3(...a))));
            acc.addAssign(ndl.mul(cone).mul(I).div(d2).mul(key ? U[key] : U.works));
        }
        return acc;
    });
    // everything lit in this set answers to the same analytic fields
    const fieldLight = (P, N) => lampField(P, N).mul(SODIUM).add(workField(P, N).mul(WORK_COL));
    // a glossy surface's highlight from the nearest lamps (cheap Blinn lobe): moving cars and wet metal catch the row
    const lampGlint = Fn(([P, N, V, shin]) => {
        const acc = float(0).toVar();
        const H = (L) => {
            const dv = L.sub(P); const l = normalize(dv); const h = normalize(l.add(V)); const d2 = max(dot(dv, dv), 1.0);
            return pow(max(dot(N, h), 0.0), shin).mul(max(dot(N, l), 0.0)).div(d2);
        };
        const kR = floor(P.z.div(D.lampR.dz).add(0.5));
        for (const o of [-1, 0, 1]) { const z = kR.add(o).mul(D.lampR.dz); acc.addAssign(H(vec3(D.lampR.head[0], D.lampR.head[1], z)).mul(step(z, D.gap0 + 0.5))); }
        const kL = floor(P.z.sub(D.lampL.z0).div(D.lampL.dz).add(0.5));
        for (const o of [-1, 0, 1]) { const z = kL.add(o).mul(D.lampL.dz).add(D.lampL.z0); acc.addAssign(H(vec3(D.lampL.head[0], D.lampL.head[1], z))); }
        return acc.mul(U.lamps).mul(shin.mul(0.04).add(2.0)).mul(LAMP_I);
    });

    // ------------------------------------------------------------------------------------------- materials
    // concrete: board-marked, rain-streaked, wet; triplanar from set-local position
    const tri = (P, N, s) => {
        const w = abs(N).pow(vec3(4.0)); const ws = w.div(w.x.add(w.y).add(w.z));
        return nz(P.zy, s).mul(ws.x).add(nz(P.xz, s).mul(ws.y)).add(nz(P.xy, s).mul(ws.z));
    };
    function concreteMat({ tint = '#7d7f80', dark = 0.75, streak = 1.0, drain = false } = {}) {
        const m = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        const P = PL, N = NL;
        const n1 = tri(P, N, 0.11), n2 = tri(P, N, 0.9);
        const vert = smoothstep(0.75, 0.95, float(1.0).sub(abs(N.y)));
        // rain streaks run down vertical faces only: noise stretched vertically
        const st = nz(vec2(P.x.add(P.z).mul(0.22), P.y.mul(0.03)), 1.0).r;
        const streaks = smoothstep(0.55, 0.95, st).mul(vert).mul(streak);
        let base = linC(tint).mul(dark).mul(n1.r.mul(0.45).add(0.75)).mul(n2.b.mul(0.25).add(0.85));
        let wetness = U.wet.mul(0.6).add(streaks.mul(0.4));
        if (drain) {
            // the drain: a dark algae band at the waterline, silt above it, wet all the way down
            const above = P.y.sub(D.ch.water);
            const algae = smoothstep(0.9, 0.1, above).mul(n1.g.mul(0.5).add(0.6));
            const silt = smoothstep(2.6, 0.6, above).mul(n2.r.mul(0.6).add(0.4));
            base = mix(mix(base, linC('#4a4230').mul(0.5), silt.mul(0.6)), linC('#1d2416').mul(0.6), clamp(algae, 0.0, 1.0));
            wetness = wetness.add(smoothstep(3.0, 0.0, above).mul(0.6));
        }
        const wet = clamp(wetness, 0.0, 1.0);
        const albedo = base.mul(float(1.0).sub(wet.mul(0.45))).mul(float(1.0).sub(streaks.mul(0.35)));
        m.colorNode = albedo;
        m.roughnessNode = mix(float(0.86), float(0.36), wet).add(n2.b.sub(0.5).mul(0.15));
        m.normalNode = bumpN(n2.b.mul(0.004).add(n1.g.mul(0.006)), 1.0);
        m.emissiveNode = albedo.mul(fieldLight(P, N)).mul(1 / Math.PI);
        return lit(m, 0.9);
    }
    function steelMat({ tint = '#2a2d31', rough = 0.5, metal = 0.75, rust = 0.25 } = {}) {
        const m = new THREE.MeshStandardNodeMaterial();
        const n = tri(PL, NL, 0.6);
        const r = smoothstep(0.62, 0.9, n.r).mul(rust);
        const albedo = mix(linC(tint), linC('#4a2a16'), r).mul(n.b.mul(0.3).add(0.85));
        m.colorNode = albedo;
        m.metalnessNode = mix(float(metal), float(0.1), r);
        m.roughnessNode = mix(float(rough), float(0.85), r).sub(U.wet.mul(0.12));
        m.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI).mul(0.6);
        return lit(m, 1.2);
    }

    const mats = {};
    mats.concrete = concreteMat();
    mats.concreteDark = concreteMat({ tint: '#5d6062', dark: 0.7 });
    mats.steel = steelMat();
    mats.steelLight = steelMat({ tint: '#6b6f73', rough: 0.42, metal: 0.85, rust: 0.15 });

    // ------------------------------------------------------------------------------------------- sky
    if (opts.sky !== false) {
        const m = own(new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide, depthWrite: false }));
        m.fog = false;
        m.colorNode = Fn(() => {
            const d = normalize(positionWorld.sub(cameraPosition));
            const h = d.y;
            const k = pow(clamp(h, 0.0, 1.0), 0.45);
            const base = mix(linC('#2a1d1c').mul(0.5), linC('#05070d'), k);
            // low rain clouds lit from below by the city: noise in direction space, drifting
            const cp = d.xz.div(max(h, 0.04).add(0.15)).mul(0.22).add(vec2(U.time.mul(0.004), 0.0));
            const c = nz(cp, 1.0);
            const cloud = smoothstep(0.35, 0.8, c.r.mul(0.7).add(c.a.mul(0.5))).mul(smoothstep(0.0, 0.12, h)).mul(float(1.0).sub(k.mul(0.7)));
            const glowH = exp(abs(h).mul(-9.0)).mul(0.6);
            return base.add(linC('#ff7a3c').mul(cloud).mul(0.06)).add(linC('#8e3b46').mul(glowH).mul(0.045))
                .add(linC('#ff8a3d').mul(exp(abs(h).mul(-30.0))).mul(0.10));
        })();
        const sky = new THREE.Mesh(own(new THREE.SphereGeometry(2400, 48, 24)), m);
        sky.name = 'race:sky'; sky.frustumCulled = false; sky.renderOrder = -10;
        sky.userData.noSupportCheck = sky.userData.noClippingCheck = true;
        group.add(sky);
        parts.sky = sky;
    }

    // ------------------------------------------------------------------------------------------- the deck
    // Road surface: one material for every carriageway piece. Wet asphalt with lane paint, wheel-path ruts that hold
    // water, gutter puddles at the barriers, rain rings, and a planar reflection of the whole set (the wet look).
    const roadG = new GB();
    const jagF = (x, s) => (Math.sin(x * 2.3 + s) * 0.35 + Math.sin(x * 5.7 + s * 2) * 0.22 + Math.sin(x * 11.1 + s) * 0.1);
    const roadPiece = (x0, x1, z0, z1, jagEnd = 0, jagStart = 0) => {
        // a strip with 28 columns so the broken ends can be jagged; triangles wound to face +Y
        const nx = 28, pos = [], idx = [];
        for (let i = 0; i <= nx; i++) {
            const x = x0 + ((x1 - x0) * i) / nx;
            const za = jagStart ? z0 - (jagF(x, 4.1) - 0.6) : z0;
            const zb = jagEnd ? z1 + (jagF(x, 1.3) - 0.6) : z1;
            pos.push(x, 0, za, x, 0, zb);
        }
        for (let i = 0; i < nx; i++) { const a = 2 * i, b = a + 1, c = a + 2, d = a + 3; idx.push(a, b, c, b, d, c); }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        g.setAttribute('normal', new THREE.Float32BufferAttribute(pos.map((_, k) => (k % 3 === 1 ? 1 : 0)), 3));
        g.setIndex(idx);
        roadG.add(g, null, [0, 0, 0, 0], (v) => [v.x, v.z]);
    };
    roadPiece(D.xR, D.xMed - 0.6, D.zFar, D.gap0, 1, 0);           // right half to the broken edge
    roadPiece(D.xR, D.xMed - 0.6, D.gap1, D.zNear, 0, 1);          // right half beyond the gap
    roadPiece(D.xMed - 0.6, D.xL, D.zFar, D.zNear);                // left half, continuous over the drain
    const roadGeo = roadG.build();

    // The planar reflection (emissive) IS the road's mirror. Real lights must not add their own GGX spike on top:
    // three r184 hard-codes f90 = 1 in direct specular, so even zero specular intensity flares at grazing angles (a
    // headlamp or a screen's point light printed as a blown star into every puddle). So the PBR roughness the real
    // lights see is pinned to 1 (a faint broad sheen); the wet roughness only steers the reflection taps below.
    const roadMat = new THREE.MeshStandardNodeMaterial({ metalness: 0, roughness: 1 });
    let refl = null;
    if (opts.reflect !== false) {
        refl = reflector({ resolutionScale: opts.reflectScale ?? 0.5, generateMipmaps: true, bounces: false });
        refl.target.rotateX(-Math.PI / 2);
        refl.target.position.y = 0.0;
        group.add(refl.target);
        parts.reflector = refl;
        const base0 = refl.reflector;
        const ub = base0.updateBefore.bind(base0);
        base0.updateBefore = (frame) => {
            const was = noRefl.map((o) => o.visible);
            for (const o of noRefl) o.visible = false;
            try { return ub(frame); } finally { noRefl.forEach((o, i) => { o.visible = was[i]; }); }
        };
    }
    // rain rings: one ring per cell, random phase; returns (height, ring strength)
    const ripples = (p, cell, rate, salt) => {
        const c = floor(p.div(cell));
        const hs = c.x.mul(73.0).add(c.y.mul(9157.0)).add(salt).abs();
        const h1 = hash(hs), h2 = hash(hs.add(17.0)), h3 = hash(hs.add(41.0));
        const ctr = c.add(vec2(h1.mul(0.6).add(0.2), h2.mul(0.6).add(0.2))).mul(cell);
        const age = fract(U.time.mul(rate).add(h3));
        const r = length(p.sub(ctr));
        const R = age.mul(cell).mul(0.48);
        const ring = sin(r.sub(R).mul(42.0)).mul(exp(r.sub(R).abs().mul(-28.0))).mul(float(1.0).sub(age)).mul(step(r, cell.mul(0.5)));
        return ring;
    };
    {
        const P = PL;
        const x = P.x, z = P.z;
        const n1 = nz(vec2(x, z), 0.031);       // big blotches (A) + breakup (R)
        const n2 = nz(vec2(x, z), 0.45);        // aggregate
        const n3 = nz(vec2(x, z), 2.2);
        // --- lane paint (white), with wear
        const band = (c, w) => smoothstep(w, w - 0.012, abs(x.sub(c)));
        const dash = (ph) => step(fract(z.add(ph).div(12.0)), 0.25);
        const inWorksRight = step(D.works.taper0[1], z).mul(step(x, D.xMed - 0.6));      // past the taper: the closed lanes
        let paint = band(1.8, 0.075).add(band(D.xMed - 0.75, 0.075)).add(band(D.xMed + 0.75, 0.075)).add(band(17.45, 0.075));
        paint = paint.add(band(5.4, 0.07).mul(dash(0))).add(band(13.65, 0.07).mul(dash(5.0)));
        // the closure: yellow temporary diagonal lines across the closed lanes (the works' hatching)
        const hatch = step(0.5, fract(x.mul(0.7071).add(z.mul(0.7071)).div(2.4))).mul(step(D.works.taper1[1] + 2, z)).mul(step(z, D.gap0 - 4))
            .mul(step(2.2, x)).mul(step(x, 8.6)).mul(0.0);   // kept as an option: off (the painting already has diagonals)
        const wear = smoothstep(0.25, 0.65, n3.b.add(n2.r.mul(0.5)));
        const paintM = clamp(paint, 0.0, 1.0).mul(wear.mul(0.7).add(0.3)).toVar();
        const yellowM = hatch;
        // --- water: gutters at the barriers, ruts in each lane's wheel paths, blotches
        const gutter = smoothstep(1.4, 0.2, x.sub(D.xR + 0.6)).add(smoothstep(1.4, 0.2, float(D.xL - 0.6).sub(x)))
            .add(smoothstep(1.0, 0.1, abs(x.sub(D.xMed)).sub(0.6)));
        const rut = (c) => exp(abs(x.sub(c - 0.85)).mul(-5.0)).add(exp(abs(x.sub(c + 0.85)).mul(-5.0)));
        const ruts = rut(D.lanes[0]).add(rut(D.lanes[1])).add(rut(D.lanes[2])).add(rut(D.lanes[3]));
        const puddle = smoothstep(0.58, 0.66, n1.a.mul(0.7).add(n1.r.mul(0.3)).add(ruts.mul(0.16)).add(gutter.mul(0.28)))
            .mul(U.wet).toVar();
        // the heel's puddle, always there
        const hp = vec2(x.sub(D.heel[0]), z.sub(D.heel[2]));
        const heelPud = smoothstep(0.95, 0.55, length(hp.mul(vec2(1.0, 0.75))).add(n3.r.sub(0.5).mul(0.25)));
        puddle.assign(max(puddle, heelPud));
        const mark = smoothstep(2.2, 1.0, length(vec2(x, z)));
        puddle.assign(puddle.mul(float(1.0).sub(mark.mul(0.9))));
        // --- albedo / roughness
        const asphalt = linC('#24262a').mul(n2.r.mul(0.5).add(0.62)).mul(n3.b.mul(0.35).add(0.8));
        const wetA = asphalt.mul(mix(1.0, 0.5, U.wet));
        const albedo = mix(mix(wetA, linC('#c9c7bd').mul(0.62), paintM), linC('#c9a227').mul(0.5), yellowM).mul(float(1.0).sub(puddle.mul(0.65)));
        roadMat.colorNode = albedo;
        roadMat.roughnessNode = float(1.0);
        // --- relief: aggregate on asphalt, flat in puddles, rings where it rains
        const rp = vec2(x, z);
        const rings = ripples(rp, float(0.55), 1.3, 0.0).add(ripples(rp.add(0.27), float(0.37), 1.7, 31.0)).mul(U.rain);
        const hAgg = n3.b.mul(0.0035).add(n2.g.mul(0.002));
        // the heel's impact rings
        const hr = length(hp);
        const hAge = U.heelAge;
        const heelRing = sin(hr.sub(hAge.mul(0.55)).mul(55.0)).mul(exp(hr.sub(hAge.mul(0.55)).abs().mul(-18.0)))
            .mul(exp(hAge.mul(-1.6))).mul(step(0.0, hAge)).mul(heelPud);
        const height = mix(hAgg, rings.mul(0.0011).add(heelRing.mul(0.002)), puddle);
        roadMat.normalNode = bumpN(height, 1.0);
        // --- light: the lamp pools, plus the reflection of the world in the water film
        const N = vec3(0, 1, 0);
        const E = lampField(P, N);
        let emiss = albedo.mul(E).mul(SODIUM).mul(1 / Math.PI);
        if (refl) {
            const V = normalize(CL.sub(P));
            const cosT = max(V.y, 0.0);
            const F = float(0.02).add(float(0.98).mul(pow(float(1.0).sub(cosT), 5.0)));
            // disturb the mirror with the rings and the aggregate, smear it down the screen like a wet road does
            const dist = vec2(rings.mul(0.010), rings.mul(0.006))
                .add(vec2(n3.b.sub(0.5).mul(0.006), n2.r.sub(0.5).mul(0.004)).mul(float(1.0).sub(puddle)));
            const base = refl.uvNode;
            // wet asphalt stretches every light into a vertical streak (rough microfacets along the view); puddles
            // stay mirrors. One sample of the reflector node itself (in three r184 its sample()/level() clones read
            // an empty target): its uv is jittered down the screen by a noise that varies fast across the road and
            // slowly along it, so the jitter lines up into streaks; the ripples and the aggregate bend it.
            const streakN = nz(vec2(x.mul(9.0), z.mul(0.12)), 1.0).r.sub(0.5).add(nz(vec2(x.mul(31.0), z.mul(0.4)), 1.0).b.sub(0.5).mul(0.6));
            const spread = mix(float(0.16), float(0.004), puddle);
            refl.uvNode = base.add(dist).add(vec2(0.0, streakN.mul(spread)));
            const acc = refl.rgb;
            const wetK = mix(U.wet.mul(0.38), float(0.95), puddle).mul(float(1.0).sub(paintM.mul(0.6)));
            // soft-clamp the mirror: an HDR screen reflected at grazing incidence would otherwise print a blown flare
            const rc = acc.mul(F).mul(wetK);
            const pk = max(rc.r, max(rc.g, rc.b));
            emiss = emiss.add(rc.div(pk.mul(1.25).add(1.0)));
        }
        roadMat.emissiveNode = emiss;
    }
    lit(roadMat, 0.35);
    const road = new THREE.Mesh(roadGeo, roadMat);
    road.name = 'race:road';
    road.userData.assembly = 'race:viaduct';
    group.add(road);
    parts.road = road;

    // slab body (fascia, soffit, broken ends), barriers, piers: concrete
    const slabG = new GB();
    const fascia = (x, z0, z1, side) => {          // the slab edge with a drip groove line (side = +1 faces +X)
        const p = (zz, y) => V3(x, y, zz);
        if (side > 0) slabG.quad(p(z1, -D.deckT), p(z0, -D.deckT), p(z0, 0.0), p(z1, 0.0), [1, 0, 0, 0], [-z1, -D.deckT]);
        else slabG.quad(p(z0, -D.deckT), p(z1, -D.deckT), p(z1, 0.0), p(z0, 0.0), [1, 0, 0, 0], [z0, -D.deckT]);
    };
    fascia(D.xR, D.zFar, D.gap0 - 0.6, -1); fascia(D.xR, D.gap1 + 0.6, D.zNear, -1); fascia(D.xL, D.zFar, D.zNear, 1);
    fascia(D.xMed - 0.6, D.gap0, D.gap1, -1);            // the left half's exposed inner edge over the gap
    // soffits (underside), facing down
    const soffit = (x0, x1, z0, z1) => slabG.quad(V3(x0, -D.deckT, z1), V3(x0, -D.deckT, z0), V3(x1, -D.deckT, z0), V3(x1, -D.deckT, z1), [2, 0, 0, 0], [x0, z0]);
    soffit(D.xR, D.xMed - 0.6, D.zFar, D.gap0); soffit(D.xR, D.xMed - 0.6, D.gap1, D.zNear); soffit(D.xMed - 0.6, D.xL, D.zFar, D.zNear);
    // the broken end faces: jagged, with a chunk hanging on its rebar
    {
        const jag = jagF;
        const nx = 28;
        for (const [zEdge, s, dir] of [[D.gap0, 1.3, 1], [D.gap1, 4.1, -1]]) {
            for (let i = 0; i < nx; i++) {
                const xa = D.xR + (D.xMed - 0.6 - D.xR) * (i / nx), xb = D.xR + (D.xMed - 0.6 - D.xR) * ((i + 1) / nx);
                const za = zEdge + dir * (jag(xa, s) - 0.6), zb = zEdge + dir * (jag(xb, s) - 0.6);
                const zaB = za - dir * (0.3 + 0.25 * Math.sin(xa * 3.1)), zbB = zb - dir * (0.3 + 0.25 * Math.sin(xb * 3.1));   // the bottom broke back further
                if (dir > 0) slabG.quad(V3(xa, -D.deckT, zaB), V3(xb, -D.deckT, zbB), V3(xb, 0, zb), V3(xa, 0, za), [3, 0, 0, 0], [xa, -D.deckT]);
                else slabG.quad(V3(xb, -D.deckT, zbB), V3(xa, -D.deckT, zaB), V3(xa, 0, za), V3(xb, 0, zb), [3, 0, 0, 0], [xb, -D.deckT]);
            }
        }
    }
    const slab = new THREE.Mesh(slabG.build(), mats.concreteDark);
    slab.name = 'race:slab'; slab.userData.assembly = 'race:viaduct';
    group.add(slab);

    // Jersey barriers (outer edges, median), with a steel rail and a neon strip along the top
    const barG = new GB();
    const neonG = new GB();
    const jersey = [[-0.30, 0], [-0.27, 0.075], [-0.14, 0.33], [-0.09, 0.84], [0.09, 0.84], [0.14, 0.33], [0.27, 0.075], [0.30, 0]];
    const barrier = (x, z0, z1, neonHex = null, neonSide = 0) => {
        const sh = new THREE.Shape(jersey.map(([a, b]) => new THREE.Vector2(a, b)));
        const g = own(new THREE.ExtrudeGeometry(sh, { depth: z1 - z0, bevelEnabled: false, steps: 1 }));
        barG.add(g, M4(x, 0, z0), [0, 0, 0, 0], (v) => [v.z, v.y]);
        if (neonHex) {
            // the neon tube rides the barrier top in long dashes: speed lines the painting can pull on
            for (let z = z0; z < z1; z += 9) {
                const len = Math.min(6.5, z1 - z);
                const tg = own(new THREE.BoxGeometry(0.05, 0.05, len));
                neonG.add(tg, M4(x + neonSide * 0.06, 0.875, z + len / 2), neonHex);
            }
        }
    };
    barrier(D.xR + 0.3, D.zFar, D.gap0 - 0.9, [0.16, 0.9, 1.0, 1], -1);
    barrier(D.xR + 0.3, D.gap1 + 0.9, D.zNear, [0.16, 0.9, 1.0, 1], -1);
    barrier(D.xL - 0.3, D.zFar, D.zNear, [1.0, 0.25, 0.8, 1], 1);
    barrier(D.xMed, D.zFar, D.zNear);
    const barriers = new THREE.Mesh(barG.build(), mats.concrete);
    barriers.name = 'race:barriers'; barriers.userData.assembly = 'race:viaduct';
    group.add(barriers);
    const neonMat = own(new THREE.MeshBasicNodeMaterial());
    {
        const a = attribute('aux', 'vec4');
        // a slow travelling flicker along the tubes (old neon), never off
        const fl = sin(PL.z.mul(0.21).add(U.time.mul(1.7))).mul(0.08).add(0.92);
        neonMat.colorNode = a.xyz.mul(a.w).mul(fl).mul(5.5);
    }
    const neon = new THREE.Mesh(neonG.build(), neonMat);
    neon.name = 'race:neon'; neon.userData.assembly = 'race:viaduct';
    group.add(neon);

    // piers: hammerhead caps on paired columns every 36 m (the right half has none in the gap)
    const pierG = new GB();
    for (let z = D.zFar + 18; z < D.zNear; z += 36) {
        const inGap = z > D.gap0 - 4 && z < D.gap1 + 4;
        const inDrain = z > D.ch.z0 - 2 && z < D.ch.z1 + 2;
        if (inDrain) continue;
        const cols = inGap ? [15.0] : [2.6, 15.0];
        for (const x of cols) pierG.add(own(new THREE.CylinderGeometry(0.85, 0.95, -D.deckT - D.ground, 18)), M4(x, (D.ground - D.deckT) / 2, z));
        const x0 = inGap ? D.xMed - 0.6 : D.xR + 0.4;
        boxQuads(pierG, x0, -D.deckT - 1.3, z - 1.1, D.xL - 0.4, -D.deckT, z + 1.1, [0, 0, 0, 0], { bottom: true });
    }
    // the bridge piers either side of the drain (left half only)
    for (const z of [D.ch.z0 - 2.5, D.ch.z1 + 2.5]) {
        for (const x of [11.5, 18.0]) pierG.add(own(new THREE.CylinderGeometry(0.85, 1.0, -D.deckT - D.ground, 18)), M4(x, (D.ground - D.deckT) / 2, z));
        boxQuads(pierG, D.xMed - 0.4, -D.deckT - 1.3, z - 1.1, D.xL - 0.4, -D.deckT, z + 1.1, [0, 0, 0, 0], { bottom: true });
    }
    const piers = new THREE.Mesh(pierG.build(), mats.concreteDark);
    piers.name = 'race:piers'; piers.userData.assembly = 'race:viaduct';
    group.add(piers);

    // ------------------------------------------------------------------------------------------- ground + the drain
    {
        const gm = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        const P = PL;
        const n1 = nz(P.xz, 0.02), n2 = nz(P.xz, 0.3);
        const albedo = linC('#1d1f22').mul(n1.r.mul(0.6).add(0.6)).mul(n2.b.mul(0.3).add(0.8));
        const pud = smoothstep(0.55, 0.7, n1.a.add(n2.r.mul(0.2)));
        gm.colorNode = albedo.mul(float(1.0).sub(pud.mul(0.6)));
        gm.roughnessNode = mix(float(0.7), float(0.06), pud);
        // street lamps down here: a sparse grid of sodium pools
        const cell = floor(P.xz.div(38.0));
        const hs = cell.x.mul(31.0).add(cell.y.mul(977.0)).abs().add(5.0);
        const on = step(hash(hs), 0.55);
        const lp = cell.add(0.5).mul(38.0);
        const d = vec3(lp.x, D.ground + 5.5, lp.y).sub(P);
        const pool = on.mul(max(dot(normalize(d), vec3(0, 1, 0)), 0.0)).div(max(dot(d, d), 1.0)).mul(140.0);
        gm.emissiveNode = gm.colorNode.mul(SODIUM.mul(pool).add(fieldLight(P, vec3(0, 1, 0)))).mul(1 / Math.PI);
        lit(gm, 0.8);
        mats.ground = gm;
        const gg = new GB();
        const S = 1400;
        gg.quad(V3(-S, D.ground, D.ch.z0), V3(S, D.ground, D.ch.z0), V3(S, D.ground, -S), V3(-S, D.ground, -S));
        gg.quad(V3(-S, D.ground, S), V3(S, D.ground, S), V3(S, D.ground, D.ch.z1), V3(-S, D.ground, D.ch.z1));
        const ground = new THREE.Mesh(gg.build(), gm);
        ground.name = 'race:ground';
        group.add(ground);
        parts.ground = ground;
        // the drain: a trapezoid concrete channel along X
        const cg = new GB();
        const C = D.ch, L = 1400;
        cg.quad(V3(L, D.ground, C.z0), V3(-L, D.ground, C.z0), V3(-L, C.bottom, C.b0), V3(L, C.bottom, C.b0), [0, 0, 0, 0]);
        cg.quad(V3(-L, D.ground, C.z1), V3(L, D.ground, C.z1), V3(L, C.bottom, C.b1), V3(-L, C.bottom, C.b1), [0, 0, 0, 0]);
        cg.quad(V3(-L, C.bottom, C.b1), V3(L, C.bottom, C.b1), V3(L, C.bottom, C.b0), V3(-L, C.bottom, C.b0), [0, 0, 0, 0]);
        const drain = new THREE.Mesh(cg.build(), concreteMat({ tint: '#6e706a', dark: 0.7, drain: true }));
        drain.name = 'race:drain';
        group.add(drain);
    }

    // ------------------------------------------------------------------------------------------- street lamps
    const lampHeads = [];
    {
        const poleG = new GB(), lensG = new GB();
        const one = (bx, z, flip) => {
            const s = flip ? -1 : 1;
            const m = M4(bx, 0.84, z, 0, flip ? Math.PI : 0, 0);
            poleG.add(own(new THREE.CylinderGeometry(0.11, 0.16, 10.0, 10)), m.clone().multiply(M4(0, 5.0, 0)));
            const arm = new THREE.CatmullRomCurve3([V3(0, 9.6, 0), V3(0.35, 10.15, 0), V3(1.6, 10.42, 0), V3(3.15, 10.32, 0)]);
            poleG.add(own(new THREE.TubeGeometry(arm, 12, 0.07, 8, false)), m);
            poleG.add(own(new THREE.BoxGeometry(1.05, 0.2, 0.46)), m.clone().multiply(M4(3.3, 10.3, 0, 0, 0, -0.06)));
            lensG.add(own(new THREE.PlaneGeometry(0.82, 0.32)), m.clone().multiply(M4(3.32, 10.19, 0, Math.PI / 2, 0, -0.06)));
            lampHeads.push(V3(bx + s * 3.3, 10.15, z));
        };
        for (let z = D.zFar + 10; z <= D.gap0; z += D.lampR.dz) {
            const zz = Math.round(z / D.lampR.dz) * D.lampR.dz;
            if (zz < D.zFar + 10 || zz > D.gap0) continue;
            one(D.lampR.x, zz, false);
        }
        for (let k = Math.ceil((D.zFar + 10 - D.lampL.z0) / D.lampL.dz); ; k++) {
            const z = D.lampL.z0 + k * D.lampL.dz; if (z > D.zNear - 5) break;
            one(D.lampL.x, z, true);
        }
        const poles = new THREE.Mesh(poleG.build(), mats.steel);
        poles.name = 'race:lampPoles'; poles.userData.assembly = 'race:viaduct';
        group.add(poles);
        const lensMat = own(new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide }));
        lensMat.colorNode = SODIUM.mul(U.lamps.mul(14.0));
        const lenses = new THREE.Mesh(lensG.build(), lensMat);
        lenses.name = 'race:lampLenses'; lenses.userData.assembly = 'race:viaduct';
        group.add(lenses);
        // light cones in the rain: open cones, brightest along the axis where the path through the beam is longest
        const coneG = new GB();
        for (const h of lampHeads) {
            const cg = own(new THREE.ConeGeometry(5.2, 10.0, 28, 1, true));
            coneG.add(cg, M4(h.x, h.y - 5.0, h.z));
        }
        const cm = noMrt(own(new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide })));
        {
            const V = normalize(CL.sub(PL));
            const facing = abs(dot(NL, V));
            const yN = clamp(PL.y.div(10.0), 0.0, 1.0);
            const fall = pow(yN, 1.6).mul(0.85).add(0.15);
            const rainSpark = nz(vec2(PL.x.add(PL.z).mul(0.6), PL.y.mul(0.08).add(U.time.mul(1.4))), 1.0).g;
            cm.colorNode = SODIUM.mul(pow(facing, 1.8)).mul(fall).mul(rainSpark.mul(0.6).add(0.55)).mul(U.lamps).mul(0.055).mul(U.rain.mul(0.5).add(0.5));
        }
        own(cm);
        const cones = new THREE.Mesh(coneG.build(), cm);
        cones.name = 'race:lampCones'; cones.renderOrder = 5;
        noRefl.push(cones);
        cones.userData.noSupportCheck = cones.userData.noClippingCheck = true;
        group.add(cones);
        parts.lamps = { poles, lenses, cones, heads: lampHeads };
    }

    // ------------------------------------------------------------------------------------------- towers
    // Dark towers in Sant'Elia's stepped massing: setbacks, service shafts, masts. One merged mesh; the facade
    // (punched windows / curtain glass / blank concrete) comes from the per-face aux channel and the face uv (metres).
    if (opts.towers !== false) {
        const tg = new GB(), ng = new GB();
        const R = rng(9091);
        const blocked = (x0, x1, z0, z1) => {
            const no = [[D.xR - 6, D.xL + 6, -2000, 2000],                 // the viaduct corridor
                [-30, -4, -84, -44], [22, 48, -84, -44],                     // the billboards
                [-2000, 2000, D.ch.z0 - 6, D.ch.z1 + 6],                    // the drain
                [D.wall.x - 26, D.wall.x + 1, D.wall.z0 - 4, D.wall.z1 + 4]]; // the shadow wall's tower (built below)
            return no.some(([a, b, c, d]) => x1 > a && x0 < b && z1 > c && z0 < d);
        };
        const tower = (cx, cz, w, d, h, style, seed, opt = {}) => {
            const x0 = cx - w / 2, x1 = cx + w / 2, z0 = cz - d / 2, z1 = cz + d / 2;
            const lit = 0.06 + R() * 0.22;
            const tiers = opt.tiers ?? (h > 70 ? 1 + Math.floor(R() * 3) : 1);
            let y0 = D.ground, ww = w, dd = d, hh = h;
            for (let k = 0; k < tiers; k++) {
                const top = k === tiers - 1 ? D.ground + h : y0 + h * (0.45 + R() * 0.25) / (k + 1);
                const sx0 = cx - ww / 2, sx1 = cx + ww / 2, sz0 = cz - dd / 2, sz1 = cz + dd / 2;
                boxQuads(tg, sx0, y0, sz0, sx1, top, sz1, [seed, style, 0, lit], { top: true, sides: [opt.blankFace && k === 0 ? 0 : 1, 1, 1, 1] });
                if (opt.blankFace && k === 0) {
                    // the windowless +X face (aux.z = 1): the march's screen
                    tg.quad(V3(sx1, y0, sz1), V3(sx1, y0, sz0), V3(sx1, top, sz0), V3(sx1, top, sz1), [seed, style, 1, 0], [-sz1, y0]);
                }
                // a service shaft on one side for some towers
                if (k === 0 && R() < 0.35) {
                    const sw = 3 + R() * 3;
                    const side = R() < 0.5 ? -1 : 1;
                    const sx = side < 0 ? sx0 - sw * 0.6 : sx1 - sw * 0.4;
                    boxQuads(tg, sx, y0, cz - sw / 2, sx + sw, top + 6 + R() * 10, cz + sw / 2, [seed + 1, 3, 0, 0.0], {});
                }
                // neon edge strips on some tiers
                if (R() < 0.28) {
                    const c = R() < 0.5 ? [0.16, 0.9, 1.0, 1] : (R() < 0.6 ? [1.0, 0.25, 0.8, 1] : [1.0, 0.48, 0.2, 1]);
                    for (const [ex, ez] of [[sx0, sz0], [sx1, sz1], [sx0, sz1], [sx1, sz0]].slice(0, 2 + Math.floor(R() * 3))) {
                        ng.add(own(new THREE.BoxGeometry(0.22, top - y0, 0.22)), M4(ex, (top + y0) / 2, ez), c);
                    }
                }
                // aviation lights on the roof corners
                for (const [ex, ez] of [[sx0, sz0], [sx1, sz1]]) ng.add(own(new THREE.BoxGeometry(0.5, 0.5, 0.5)), M4(ex, top + 0.3, ez), [1.0, 0.06, 0.03, 2]);
                y0 = top; ww *= 0.62 + R() * 0.2; dd *= 0.62 + R() * 0.2;
            }
            if (R() < 0.4) tg.add(own(new THREE.CylinderGeometry(0.25, 0.4, 16 + R() * 20, 6)), M4(cx, D.ground + h + 9, cz), [seed, 4, 0, 0]);
        };
        // the shadow wall: a deep windowless face toward the road (the march's screen), windows on its other sides
        tower(D.wall.x - 11, (D.wall.z0 + D.wall.z1) / 2, 22, D.wall.z1 - D.wall.z0, D.wall.top - D.ground, 1, 777, { tiers: 1, blankFace: true });
        // rows of towers either side, thinning with distance; a few close ones make the canyon
        let placed = 0;
        for (let i = 0; i < 520 && placed < 150; i++) {
            const side = R() < 0.5 ? -1 : 1;
            const dist = 14 + Math.pow(R(), 1.5) * 230;
            const cx = side < 0 ? D.xR - dist : D.xL + dist;
            const cz = -520 + R() * 860;
            const w = 12 + R() * 22, d = 12 + R() * 26;
            const h = 26 + Math.pow(R(), 1.3) * (dist < 60 ? 150 : 230);
            if (blocked(cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2)) continue;
            tower(cx, cz, w, d, h, R() < 0.45 ? 2 : (R() < 0.6 ? 0 : 1), 1000 + i);
            placed++;
        }
        // the factory on the drain's far bank (Marinetti's "fair factory drain"): long sawtooth sheds and two stacks
        for (let k = 0; k < 6; k++) {
            const x0 = -110 + k * 22;
            boxQuads(tg, x0, D.ground, D.ch.z1 + 8, x0 + 20, D.ground + 9, D.ch.z1 + 40, [3000 + k, 0, 0, 0.35], {});
        }
        tg.add(own(new THREE.CylinderGeometry(2.2, 3.0, 42, 14, 1, true)), M4(-40, D.ground + 21, D.ch.z1 + 30), [3100, 3, 0, 0]);
        tg.add(own(new THREE.CylinderGeometry(1.8, 2.6, 36, 14, 1, true)), M4(-78, D.ground + 18, D.ch.z1 + 24), [3101, 3, 0, 0]);

        const tm = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        {
            const a = attribute('aux', 'vec4');
            const seed = a.x, style = a.y, blank = a.z, litF = a.w;
            const fu = uv().x, fv = uv().y;
            const P = PL, N = NL;
            const vert = float(1.0).sub(abs(N.y)).toVar();
            const modW = select(style.lessThan(0.5), float(1.55), select(style.lessThan(1.5), float(2.2), float(1.8)));
            const floorH = select(style.lessThan(1.5), float(3.6), float(3.3));
            const cu = fract(fu.div(modW)), cvv = fract(fv.div(floorH));
            const col = floor(fu.div(modW)), row = floor(fv.div(floorH));
            const punched = step(0.14, cu).mul(step(cu, 0.86)).mul(step(0.22, cvv)).mul(step(cvv, 0.84));
            const curtain = step(0.035, cu).mul(step(cu, 0.965)).mul(step(0.12, cvv)).mul(step(cvv, 0.93));
            const isGlass = select(style.greaterThan(1.5), curtain, punched).mul(vert).mul(float(1.0).sub(blank)).mul(step(style, 2.5))
                .mul(step(D.ground + 4.0, P.y)).toVar();
            const hs = seed.mul(131.0).add(row.mul(17.0)).add(col.mul(3.0)).abs();
            const cluster = nz(vec2(seed.mul(0.37).add(col.mul(0.031)), row.mul(0.045)), 1.0).r;
            const on = step(hash(hs), litF.mul(cluster.mul(1.4).add(0.2)));
            const warm = hash(hs.add(7.0));
            const wcol = mix(linC('#9cc8ff'), mix(linC('#ffb26b'), linC('#ffd9a0'), hash(hs.add(13.0))), step(0.35, warm));
            const wI = hash(hs.add(3.0)).mul(0.9).add(0.35);
            const n1 = tri(P, N, 0.07), n2 = tri(P, N, 0.6);
            const st = nz(vec2(P.x.add(P.z).mul(0.07), P.y.mul(0.012)), 1.0).r;
            const streak = smoothstep(0.5, 0.85, st).mul(vert).mul(0.7);
            // board-marked formwork on the blank wall: 2.4 x 1.2 m panels, tie holes, the joints holding water
            const pu = fract(fu.div(2.4)), pv = fract(fv.div(1.2));
            const joint = max(smoothstep(0.012, 0.0, min(pu, float(1.0).sub(pu))), smoothstep(0.02, 0.0, min(pv, float(1.0).sub(pv))));
            const tie = smoothstep(0.035, 0.02, length(vec2(fract(fu.div(0.6)).sub(0.5).mul(0.6), fract(fv.div(0.6)).sub(0.5).mul(0.6))));
            const board = nz(vec2(fu.mul(0.05), fv.mul(4.0)), 1.0).b;
            const conc = linC('#3e4246').mul(n1.r.mul(0.5).add(0.6)).mul(n2.b.mul(0.3).add(0.8)).mul(float(1.0).sub(streak.mul(0.35)));
            const glass = linC('#06080b');
            const blankC = linC('#8a8c8a').mul(n1.r.mul(0.4).add(0.72)).mul(board.mul(0.18).add(0.9)).mul(float(1.0).sub(streak.mul(0.4)))
                .mul(float(1.0).sub(joint.mul(0.45).add(tie.mul(0.6)).mul(blank)));
            const albedo = mix(mix(conc, blankC, blank), glass, isGlass);
            tm.colorNode = albedo;
            tm.roughnessNode = mix(mix(float(0.82), float(0.6), blank), float(0.08), isGlass).sub(U.wet.mul(0.15).mul(float(1.0).sub(isGlass)));
            tm.metalnessNode = isGlass.mul(0.6);
            // the march: shadows of an absent column, thrown by the floodlight onto every wall it reaches
            const Pf = P;
            const fl = floodField(Pf, N).mul(U.march.mul(0.92).add(0.08));
            const sh = marchShadowFn(Pf);
            const E = fieldLight(P, N).add(linC('#ffe2b8').mul(fl).mul(float(1.0).sub(sh.mul(0.93))));
            tm.emissiveNode = albedo.mul(E).mul(1 / Math.PI).add(wcol.mul(on).mul(isGlass).mul(wI).mul(1.6));
            tm.normalNode = bumpN(n2.b.mul(0.01).mul(float(1.0).sub(isGlass)).sub(joint.add(tie).mul(blank).mul(0.008)), 1.0);
        }
        lit(tm, 1.0);
        const towers = new THREE.Mesh(tg.build(), tm);
        towers.name = 'race:towers';
        towers.userData.noSupportCheck = towers.userData.noClippingCheck = true;
        group.add(towers);
        const nm = own(new THREE.MeshBasicNodeMaterial());
        {
            const a = attribute('aux', 'vec4');
            const isAv = step(1.5, a.w);
            const blink = step(0.55, fract(U.time.mul(0.75).add(PL.x.mul(0.013))));
            nm.colorNode = a.xyz.mul(mix(float(2.2), blink.mul(9.0), isAv));
        }
        const tneon = new THREE.Mesh(ng.build(), nm);
        tneon.name = 'race:towerNeon';
        tneon.userData.noSupportCheck = tneon.userData.noClippingCheck = true;
        group.add(tneon);
        parts.towers = { towers, neon: tneon };
    }

    // ------------------------------------------------------------------------------------------- the billboards
    // Both screens draw the SAME face (one drawing function): a monumental machine-god made of light and circuitry,
    // with a halo of Balla's sun rays. Canvas channels: R = traces and outline, G = phase along the traces (data
    // flowing outward from the mind), B = the face's planes (dim fills) and, in the bottom band, the amount.
    const FACE = { W: 1024, H: 683, cx: 512, cy: 238, s: 0.6 };     // face centre and scale on the 3:2 canvas
    const BAND_V = 0.66;                                              // the amount band below this (canvas rows)
    const EYE = [[415, 470], [609, 470]].map(([x, y]) => [FACE.cx + (x - 512) * FACE.s, FACE.cy + (y - 540) * FACE.s]);
    function drawFace(g) {
        const S = FACE.s, ox = FACE.cx, oy = FACE.cy;
        const X = (x) => ox + (x - 512) * S, Y = (y) => oy + (y - 540) * S;
        const ph = (x, y) => Math.min(1, Math.hypot(x - 512, y - 470) / 560);
        const col = (r, gph, b) => `rgb(${Math.round(r * 255)},${Math.round(gph * 255)},${Math.round(b * 255)})`;
        const line = (pts, w, r = 1, glowPx = 6) => {
            const mx = pts.reduce((a, p) => a + p[0], 0) / pts.length, my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
            g.strokeStyle = col(r, ph(mx, my), 0); g.lineWidth = w * S; g.lineCap = 'round'; g.lineJoin = 'round';
            g.shadowColor = col(r * 0.8, ph(mx, my), 0); g.shadowBlur = glowPx * S;
            g.beginPath(); g.moveTo(X(pts[0][0]), Y(pts[0][1])); for (const p of pts.slice(1)) g.lineTo(X(p[0]), Y(p[1])); g.stroke();
            g.shadowBlur = 0;
        };
        const pad = (x, y, r) => { g.fillStyle = col(1, ph(x, y), 0); g.beginPath(); g.arc(X(x), Y(y), r * S, 0, Math.PI * 2); g.fill(); };
        const mir = (pts) => pts.map(([x, y]) => [1024 - x, y]);
        g.globalCompositeOperation = 'lighter';
        // halo: Balla's sun behind the head — rays and broken rings
        for (let k = 0; k < 64; k++) {
            const a = (k / 64) * Math.PI * 2, long = k % 2 === 0;
            const r0 = 430, r1 = long ? 560 : 500;
            line([[512 + Math.cos(a) * r0, 470 + Math.sin(a) * r0], [512 + Math.cos(a) * r1, 470 + Math.sin(a) * r1]], long ? 5 : 3, 0.45, 4);
        }
        for (const [r, a0, a1] of [[455, 0.2, 2.9], [455, 3.4, 6.0], [485, -0.5, 1.4], [485, 1.9, 4.4], [515, 0.9, 5.2]]) {
            g.strokeStyle = col(0.5, ph(512 + r, 470), 0); g.lineWidth = 3 * S;
            g.beginPath(); g.arc(X(512), Y(470), r * S, a0, a1); g.stroke();
        }
        // the face's planes (dim fills), lit from the viewer's left like a cast bronze head
        const planes = [
            [[[512, 205], [600, 215], [690, 260], [512, 395]], 0.20], [[[690, 260], [745, 340], [760, 440], [700, 420], [512, 395]], 0.13],
            [[[512, 395], [724, 420], [760, 440], [765, 520], [609, 520], [529, 430]], 0.10], [[[529, 430], [539, 650], [554, 655], [694, 720], [745, 610], [765, 520], [609, 520]], 0.16],
            [[[554, 655], [694, 720], [630, 810], [560, 870], [512, 880], [512, 760]], 0.12], [[[700, 720], [745, 610], [694, 720]], 0.08],
        ];
        for (const [poly, v] of planes) {
            for (const [pp, vv] of [[poly, v], [mir(poly), v * 1.6]]) {
                g.fillStyle = col(0, 0, vv); g.beginPath(); g.moveTo(X(pp[0][0]), Y(pp[0][1])); for (const p of pp.slice(1)) g.lineTo(X(p[0]), Y(p[1])); g.closePath(); g.fill();
            }
        }
        // outline: faceted, monumental
        const outline = [[512, 205], [600, 215], [690, 260], [745, 340], [760, 440], [765, 520], [745, 610], [700, 720], [630, 810], [560, 870], [512, 880]];
        line(outline, 9, 1, 10); line(mir(outline), 9, 1, 10);
        // neck: two columns down out of frame, and the collar line
        line([[600, 845], [612, 1100]], 7, 0.9); line([[424, 845], [412, 1100]], 7, 0.9);
        line([[330, 1010], [512, 960], [694, 1010]], 5, 0.7);
        // brow: one heavy arc
        line([[300, 425], [360, 405], [440, 396], [512, 394], [584, 396], [664, 405], [724, 425]], 10, 1, 12);
        // eyes: almond lids (the irises are drawn live by the screen shader)
        for (const ex of [415, 609]) {
            const lid = []; for (let k = 0; k <= 16; k++) { const a = Math.PI * (k / 16); lid.push([ex - 72 * Math.cos(a), 470 - 30 * Math.sin(a)]); }
            const low = []; for (let k = 0; k <= 16; k++) { const a = Math.PI * (k / 16); low.push([ex - 72 * Math.cos(a), 470 + 24 * Math.sin(a)]); }
            line(lid, 6, 1, 8); line(low, 4, 0.8, 6);
        }
        // nose: twin traces down the bridge, a base bar with nostril arcs
        line([[497, 420], [488, 640]], 5); line([[527, 420], [536, 640]], 5);
        line([[468, 655], [556, 655]], 5);
        // mouth: closed and level
        line([[432, 735], [480, 728], [512, 733], [544, 728], [592, 735]], 7, 1, 8);
        line([[456, 764], [512, 770], [568, 764]], 4, 0.7);
        // cheek and jaw planes as traces
        line([[468, 660], [330, 720]], 4, 0.8); line(mir([[468, 660], [330, 720]]), 4, 0.8);
        line([[345, 485], [300, 600], [330, 720], [392, 812]], 4, 0.75); line(mir([[345, 485], [300, 600], [330, 720], [392, 812]]), 4, 0.75);
        // circuitry: 45-degree routed traces with pads, symmetric
        const traces = [
            [[512, 394], [512, 330], [470, 288], [470, 230]], [[480, 394], [480, 350], [430, 300], [430, 250]], [[450, 397], [450, 365], [390, 305], [360, 305]],
            [[420, 400], [380, 360], [330, 360], [300, 330]], [[350, 520], [320, 550], [320, 640]], [[380, 560], [360, 580], [360, 680], [400, 720]],
            [[440, 600], [420, 620], [420, 700]], [[470, 790], [470, 830], [500, 860]], [[400, 760], [430, 790], [430, 840]],
            [[300, 470], [260, 470], [240, 450], [210, 450]], [[300, 560], [250, 560], [220, 590], [190, 590]], [[330, 680], [290, 720], [250, 720]],
        ];
        for (const tr of traces) {
            for (const t2 of [tr, mir(tr)]) { line(t2, 3.2, 0.85, 5); pad(t2[t2.length - 1][0], t2[t2.length - 1][1], 6); }
        }
        pad(512, 300, 9);
        g.strokeStyle = col(1, ph(512, 300), 0); g.lineWidth = 3 * S; g.beginPath(); g.arc(X(512), Y(300), 20 * S, 0, Math.PI * 2); g.stroke();
        g.globalCompositeOperation = 'source-over';
    }
    function billboardCanvas(amount) {
        const [c, g] = cv(FACE.W, FACE.H);
        g.fillStyle = 'rgb(0,0,0)'; g.fillRect(0, 0, FACE.W, FACE.H);
        g.save(); g.beginPath(); g.rect(0, 0, FACE.W, FACE.H * BAND_V); g.clip();
        drawFace(g);
        g.restore();
        // the band: the amount, as big as the band allows, in the blue channel (the shader lights it in the screen's
        // own saturated hue: the painting keeps saturated light and smears white)
        const bandY = FACE.H * BAND_V;
        g.fillStyle = 'rgb(0,0,0)'; g.fillRect(0, bandY, FACE.W, FACE.H - bandY);
        const bandH = FACE.H - bandY;
        // Impact: the heaviest strokes per width on the machine, so the digits survive the painting's brush
        const fam = (n) => `${n}px Impact, "Arial Black", Rajdhani, sans-serif`;
        let px = Math.round(bandH * 1.0);
        g.font = fam(px);
        const w = g.measureText(amount).width;
        if (w > FACE.W * 0.96) { px = Math.floor(px * (FACE.W * 0.96) / w); g.font = fam(px); }
        g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillStyle = 'rgb(0,0,255)';
        g.fillText(amount, FACE.W / 2, bandY + bandH * 0.54);
        // band rules (dim, in the trace channel)
        g.fillStyle = 'rgb(150,0,0)'; g.fillRect(16, bandY + 3, FACE.W - 32, 4); g.fillRect(16, FACE.H - 7, FACE.W - 32, 4);
        return canvasTex(c, { srgb: false, mips: true });
    }
    const bbTex = { a: billboardCanvas('$100,000,000'), b: billboardCanvas('$20,000,000') };
    function screenMat(texA, tintHex, mode, power) {
        const m = own(new THREE.MeshBasicNodeMaterial());
        m.fog = true;
        m.colorNode = Fn(() => {
            const q = uv().toVar();                 // PlaneGeometry uv: (0,0) bottom-left
            const t = U.time;
            // fear: the picture tears in horizontal bands; worship: it breathes
            const band = floor(q.y.mul(46.0));
            const tear = step(0.9, hash(band.add(floor(t.mul(11.0)).mul(57.0)).abs())).mul(hash(band.add(3.0)).sub(0.5)).mul(0.035);
            const qx = mode === 'fear' ? q.x.add(tear) : q.x;
            const cuv = vec2(qx, float(1.0).sub(q.y));    // canvas row 0 = top
            const s = texture(texA, cuv);
            const lines = s.r, phase = s.g, fillB = s.b;
            const inBand = step(q.y, float(1.0 - BAND_V + 0.004));
            // data flowing outward along the traces
            const flow = smoothstep(0.75, 1.0, sin(phase.mul(26.0).sub(t.mul(3.2)))).mul(0.8).add(0.55);
            const faceI = lines.mul(flow).add(fillB.mul(1.0 - 0.0).mul(float(1.0).sub(inBand)).mul(0.55));
            // the eyes: live irises (aperture rings) that glance toward the other screen
            const eyeI = float(0).toVar();
            for (const [ex, ey] of EYE) {
                const c = vec2(ex / FACE.W, ey / FACE.H);
                const gz = vec2(U.gaze.mul(mode === 'fear' ? 0.010 : -0.010), 0.0);
                const d = cuv.sub(c.add(gz)).mul(vec2(FACE.W / FACE.H, 1.0));
                const r = length(d);
                const a = atan(d.y, d.x);
                const blades = sin(a.mul(9.0).add(t.mul(mode === 'fear' ? 2.6 : 0.8))).mul(0.5).add(0.5);
                const ring = smoothstep(0.034, 0.030, r).mul(smoothstep(0.020, 0.024, r)).mul(blades.mul(0.6).add(0.4));
                const pupil = smoothstep(0.012, 0.004, r).mul(2.2);
                const lidMask = smoothstep(0.042, 0.03, abs(d.y.mul(1.6))).mul(smoothstep(0.075, 0.05, r));
                eyeI.addAssign(ring.add(pupil).mul(lidMask));
            }
            const text = fillB.mul(inBand);
            const tint = linC(tintHex);
            // gold clips to white far sooner than red: each screen's text sits just under its own clip point
            const textK = mode === 'fear' ? 2.1 : 1.15;
            let col = tint.mul(faceI.mul(mode === 'fear' ? 2.0 : 1.5).add(eyeI.mul(4.2))).add(mix(tint, vec3(1.0, 0.95, 0.85), 0.08).mul(text).mul(textK));
            // worship: a slow breathing halo; fear: an alarm pulse
            const pulse = mode === 'fear' ? smoothstep(0.6, 1.0, sin(t.mul(5.2))).mul(0.35).add(0.85) : sin(t.mul(1.1)).mul(0.12).add(1.0);
            col = col.mul(pulse);
            // LED cells (fade out when they are smaller than a pixel) and a rolling scan
            const cells = q.mul(vec2(320.0, 213.0));
            const fw = fwidth(cells.x);
            const led = smoothstep(0.5, 0.25, length(fract(cells).sub(0.5))).mul(0.6).add(0.4);
            const ledK = mix(led, float(0.75), smoothstep(0.25, 0.6, fw));
            const scan = sin(q.y.mul(9.0).sub(t.mul(1.7))).mul(0.06).add(0.94);
            const base = tint.mul(0.035);                       // the panel's own black level, never dead
            return base.add(col.mul(ledK).mul(scan)).mul(power);
        })();
        return m;
    }
    const billboards = {};
    for (const [key, B, tex, tintHex, mode, pu] of [['a', D.billA, bbTex.a, '#ffb43c', 'worship', U.billA], ['b', D.billB, bbTex.b, '#ff2a1a', 'fear', U.billB]]) {
        const g = new THREE.Group();
        g.name = 'race:billboard_' + key;
        g.position.set(B.x, 0, B.z); g.rotation.y = B.yaw;
        const sm = screenMat(tex, tintHex, mode, pu);
        const scr = new THREE.Mesh(own(new THREE.PlaneGeometry(B.w, B.h)), sm);
        scr.position.set(0, B.y, 0.35);
        scr.name = 'race:screen_' + key;
        g.add(scr);
        // the steel: a back frame with X-bracing (Balla's crisscross), two legs to the ground, a catwalk, lamps
        const fg = new GB();
        const hw = B.w / 2, hh = B.h / 2;
        boxQuads(fg, -hw - 0.4, B.y - hh - 0.4, -0.6, hw + 0.4, B.y + hh + 0.4, 0.3, [0, 0, 0, 0], { bottom: true });
        for (let k = 0; k <= 6; k++) { const x = -hw + (B.w * k) / 6; fg.add(own(new THREE.BoxGeometry(0.35, B.h + 0.8, 0.35)), M4(x, B.y, -1.1)); }
        for (let k = 0; k < 6; k++) {
            const xa = -hw + (B.w * k) / 6, xb = xa + B.w / 6;
            for (const [y0, y1] of [[B.y - hh, B.y + hh], [B.y + hh, B.y - hh]]) {
                const L = Math.hypot(xb - xa, y1 - y0);
                fg.add(own(new THREE.BoxGeometry(0.18, L, 0.18)), M4((xa + xb) / 2, (y0 + y1) / 2, -1.1, 0, 0, Math.atan2(-(xb - xa), y1 - y0)));
            }
        }
        for (const x of [-hw * 0.55, hw * 0.55]) fg.add(own(new THREE.CylinderGeometry(0.75, 0.9, B.y - hh - D.ground, 16)), M4(x, (B.y - hh + D.ground) / 2, -1.0));
        fg.add(own(new THREE.BoxGeometry(B.w + 1.0, 0.12, 1.4)), M4(0, B.y - hh - 0.6, 0.5));
        for (let k = 0; k < 6; k++) fg.add(own(new THREE.BoxGeometry(0.5, 0.35, 0.4)), M4(-hw + 2 + k * (B.w - 4) / 5, B.y - hh - 0.35, 1.0, -0.5, 0, 0));
        const frame = new THREE.Mesh(fg.build(), mats.steel);
        frame.name = 'race:billboardFrame_' + key;
        g.add(frame);
        g.userData.assembly = 'race:billboard_' + key;
        group.add(g);
        billboards[key] = { group: g, screen: scr, material: sm, texture: tex, amount: key === 'a' ? '$100,000,000' : '$20,000,000', mode, tint: tintHex };
    }
    parts.billboards = billboards;

    // ------------------------------------------------------------------------------------------- the car
    // A 1908-pattern Italian Grand Prix racer (the Fiat / Itala / Isotta type: a long louvred bonnet strapped down,
    // a flat brass-shelled honeycomb radiator, an outside exhaust, chain drive, wooden artillery wheels on pale
    // period tyres, a bolster tank and a spare behind two buttoned seats). A period pattern, no maker's badge.
    // Car space: +Z forward, +Y up, origin on the ground between the axles. Wheelbase 2.76 m, track 1.40 m.
    const CAR = { wb: 2.76, track: 1.40, R: 0.45, com: [0, 0.62, 0.1], nose: [0, 0.55, 2.05], top: 1.32 };
    const car = { group: new THREE.Group(), wheels: [], riders: null };
    car.group.name = 'race:car';
    car.group.userData.assembly = 'race:car';
    car.group.userData.noSupportCheck = true;
    {
        const P0 = positionLocal;               // car-space for patterns (every body mesh is built in car space)
        const PW = PL, NW = NL;
        const Vw = normalize(CL.sub(PL));
        const carLight = (albedo, k = 1) => albedo.mul(fieldLight(PW, NW)).mul((1.7 * k) / Math.PI);   // the hero catches more of the row
        // RED ENAMEL: deep rosso, clearcoat, orange peel, road filth low down, rain beading on the upper surfaces
        const paint = new THREE.MeshPhysicalNodeMaterial({ metalness: 0, clearcoat: 1.0 });
        {
            const n = nz(vec2(P0.x.add(P0.z), P0.y.add(P0.z.mul(0.3))), 1.7), n2 = nz(vec2(P0.x.mul(1.3).add(P0.z), P0.y), 9.0);
            const low = smoothstep(0.95, 0.5, P0.y);
            const filth = smoothstep(0.45, 0.8, n.r.add(low.mul(0.45))).mul(low);
            // bonnet louvres: vertical slots on both sides of the bonnet
            const louv = step(0.3, abs(P0.x)).mul(step(1.0, P0.z)).mul(step(P0.z, 1.72)).mul(step(0.76, P0.y)).mul(step(P0.y, 1.04)).mul(step(P0.y, 1.1));
            const slot = smoothstep(0.30, 0.22, fract(P0.z.div(0.07))).mul(louv);
            const red = linC('#bd1b12').mul(n2.b.mul(0.12).add(0.94));
            const albedo = mix(mix(red, linC('#2b1a12'), filth.mul(0.85)), linC('#090303'), slot).toVar();
            paint.colorNode = albedo;
            paint.roughnessNode = mix(float(0.32), float(0.75), filth).add(n2.b.sub(0.5).mul(0.06));
            paint.clearcoatNode = float(1.0).sub(filth.mul(0.8));
            paint.clearcoatRoughnessNode = float(0.07).add(n2.g.mul(0.06));
            const up = smoothstep(0.4, 0.9, normalLocal.y);
            const bead = smoothstep(0.72, 0.9, nz(P0.xz, 14.0).b).mul(up).mul(U.wet);
            paint.normalNode = bumpN(bead.mul(0.0012).add(n.b.mul(0.0004)).sub(slot.mul(0.004)), 1.0);
            paint.emissiveNode = carLight(albedo).add(linC('#ffd2a0').mul(lampGlint(PW, NW, Vw, float(180.0))).mul(0.05).mul(float(1.0).sub(filth)));
        }
        lit(paint, 1.4);
        // BRASS: polished where hands go, tarnished in the recesses
        const brass = new THREE.MeshStandardNodeMaterial({ metalness: 1.0 });
        {
            const n = nz(vec2(P0.x.add(P0.y), P0.z.add(P0.y)), 6.0);
            const tarn = smoothstep(0.55, 0.85, n.r);
            const albedo = mix(linC('#e0b158'), linC('#6b5a2c'), tarn.mul(0.75));
            brass.colorNode = albedo;
            brass.roughnessNode = mix(float(0.22), float(0.55), tarn);
            brass.emissiveNode = albedo.mul(lampGlint(PW, NW, Vw, float(90.0))).mul(0.05).add(carLight(albedo, 0.25));
        }
        lit(brass, 1.6);
        // DARK STEEL: chassis underside, springs, axles; oily, rusting at the edges
        const steel = steelMat({ tint: '#1c1d1f', rough: 0.45, metal: 0.8, rust: 0.35 });
        // EXHAUST: heat-blued near the headers, rust brown along the run
        const exh = new THREE.MeshStandardNodeMaterial({ metalness: 0.85 });
        {
            const heat = smoothstep(0.6, 1.5, P0.z);
            const n = nz(vec2(P0.z, P0.y.add(P0.x)), 5.0);
            const albedo = mix(mix(linC('#4a2a17'), linC('#2d2f3a'), heat), linC('#3d2a4a'), heat.mul(n.r));
            exh.colorNode = albedo.mul(n.b.mul(0.4).add(0.75));
            exh.roughnessNode = mix(float(0.7), float(0.4), heat);
            exh.emissiveNode = carLight(albedo, 0.5);
        }
        lit(exh, 1.0);
        // BLACK LEATHER (buttoned seats, aux.x = 1 where tufted), BROWN LEATHER (straps, helmets, gloves)
        const leatherK = new THREE.MeshStandardNodeMaterial({ metalness: 0, side: THREE.DoubleSide });
        {
            const a = attribute('aux', 'vec4');
            const q = uv().mul(vec2(7.0, 4.0));
            const dia = vec2(q.x.add(q.y), q.x.sub(q.y));
            const cell = abs(fract(dia).sub(0.5));
            const tuft = a.x.mul(smoothstep(0.08, 0.0, min(cell.x, cell.y)));
            const n = nz(uv().mul(3.0), 1.0);
            const albedo = linC('#14090a').mul(n.r.mul(0.4).add(0.8));
            leatherK.colorNode = albedo;
            leatherK.roughnessNode = float(0.42).add(n.b.mul(0.2)).add(tuft.mul(0.2));
            leatherK.normalNode = bumpN(tuft.mul(-0.006).add(n.b.mul(0.0006)), 1.0);
            leatherK.emissiveNode = carLight(albedo).add(lampGlint(PW, NW, Vw, float(40.0)).mul(0.02));
        }
        lit(leatherK, 1.0);
        const leatherB = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        {
            const n = nz(vec2(P0.x.add(P0.z), P0.y).mul(4.0), 1.0);
            const albedo = linC('#4a2814').mul(n.r.mul(0.5).add(0.7));
            leatherB.colorNode = albedo;
            leatherB.roughnessNode = float(0.5).add(n.g.mul(0.25));
            leatherB.normalNode = bumpN(n.g.mul(0.0015), 1.0);
            leatherB.emissiveNode = carLight(albedo);
        }
        lit(leatherB, 0.9);
        // VARNISHED ASH (wheel spokes and felloes, steering rim, dash)
        const woodMat = (smear = false) => {
            const m = new THREE.MeshStandardNodeMaterial({ metalness: 0, side: smear ? THREE.DoubleSide : THREE.FrontSide });
            const p = positionLocal;
            const r = length(p.yz), a = atan(p.z, p.y);
            const grainC = smear ? vec2(r.mul(40.0), a.mul(3.0)) : vec2(p.x.add(p.z).mul(30.0), p.y.mul(3.0));
            const grain = nz(grainC, 0.05).g;
            const albedo = mix(linC('#7a4a20'), linC('#b37a3c'), grain).toVar();
            m.colorNode = albedo;
            m.roughnessNode = float(0.32).add(grain.mul(0.15));
            let h = grain.mul(0.0005);
            if (smear) {
                // ARTILLERY SPOKES under the camera's shutter: each spoke is box-blurred by the wheel's turn during the
                // exposure (U.smear radians), so slow wheels show spokes and fast ones a translucent blur, never strobing.
                const NS = 12, SP = (2 * Math.PI) / NS;
                const halfW = mix(float(0.030), float(0.021), clamp(r.sub(0.09).div(0.21), 0.0, 1.0)).div(max(r, 0.05));
                const w = halfW.mul(2.0);
                const dl = max(U.smear, 1e-4);
                const ac = a.add(U.smear.mul(0.5));
                const d = abs(fract(ac.div(SP).add(0.5)).sub(0.5)).mul(SP);
                const ov = max(min(halfW, d.add(dl.mul(0.5))).sub(max(halfW.negate(), d.sub(dl.mul(0.5)))), 0.0);
                const cov = clamp(ov.div(dl), 0.0, 1.0).mul(step(0.075, r)).mul(step(r, 0.315));
                const hub = step(r, 0.105);
                m.opacityNode = max(cov, hub);
                m.alphaHash = true;
                const u = clamp(d.div(halfW), 0.0, 1.0);
                h = h.add(sqrt(max(float(1.0).sub(u.mul(u)), 0.0)).mul(0.01).mul(float(1.0).sub(clamp(dl.div(w), 0.0, 1.0))));
            }
            m.normalNode = bumpN(h, 1.0);
            m.emissiveNode = carLight(albedo, 0.9).add(lampGlint(PW, NW, Vw, float(60.0)).mul(0.02));
            return lit(m, 0.9);
        };
        const wood = woodMat(false), spokes = woodMat(true);
        // PALE PERIOD RUBBER (natural rubber, before carbon black): ribbed tread, road grime and wet
        const rubber = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        {
            const p = positionLocal;
            const r = length(p.yz);
            const tread = smoothstep(0.43, 0.445, r);
            const rib = sin(p.x.mul(160.0)).mul(0.5).add(0.5).mul(tread);
            const n = nz(vec2(atan(p.z, p.y).mul(3.0), p.x.mul(8.0)), 1.0);
            const grime = smoothstep(0.35, 0.75, n.r.add(tread.mul(0.35)));
            const albedo = mix(linC('#b8b09c'), linC('#3a3128'), grime.mul(0.75));
            rubber.colorNode = albedo;
            rubber.roughnessNode = mix(float(0.75), float(0.45), U.wet.mul(tread));
            rubber.normalNode = bumpN(rib.mul(0.0015), 1.0);
            rubber.emissiveNode = carLight(albedo, 0.9);
        }
        lit(rubber, 0.7);
        // HONEYCOMB radiator core (black, a white racing number painted on it)
        const numTex = (() => {
            const [c, g] = cv(256, 256);
            g.fillStyle = '#000'; g.fillRect(0, 0, 256, 256);
            g.fillStyle = '#fff'; g.font = 'bold 210px Georgia, "Times New Roman", serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
            g.fillText('7', 128, 140);
            return canvasTex(c, { srgb: false, mips: true });
        })();
        const core = new THREE.MeshStandardNodeMaterial({ metalness: 0.5 });
        {
            const p = positionLocal;
            const q = vec2(p.x.mul(115.0), p.y.mul(100.0));
            const hx = abs(fract(q.x.add(step(0.5, fract(q.y.mul(0.5))).mul(0.5))).sub(0.5));
            const hy = abs(fract(q.y).sub(0.5));
            const cell = max(hx, hy);
            const num = texture(numTex, vec2(p.x.div(0.6).add(0.5), float(1.0).sub(p.y.sub(0.56).div(0.62)))).r.mul(step(1.95, p.z));
            const albedo = mix(linC('#0a0a0a'), linC('#d8d4c8'), num);
            core.colorNode = albedo;
            core.roughnessNode = float(0.55);
            core.normalNode = bumpN(smoothstep(0.38, 0.5, cell).mul(-0.004), 1.0);
            core.emissiveNode = carLight(albedo, 0.8);
        }
        lit(core, 0.6);
        const glass = new THREE.MeshStandardNodeMaterial({ color: 0x050608, roughness: 0.05, metalness: 0.2 });
        lit(glass, 2.0);
        car.mats = { paint, brass, steel, exh, leatherK, leatherB, wood, spokes, rubber, core, glass };

        // ---------- geometry helpers in car space
        const B = { paint: new GB(), brass: new GB(), steel: new GB(), exh: new GB(), leatherK: new GB(), leatherB: new GB(), wood: new GB(), core: new GB(), glass: new GB() };
        // a rectangular-section bar swept along points in a plane containing +X as the 'side' (springs, rails,
        // straps): w across (x), h in the sweep plane
        const bar = (gb, pts, w, h, aux) => {
            const pos = [], idx = [];
            for (let i = 0; i < pts.length; i++) {
                const p = pts[i], q = pts[Math.min(pts.length - 1, i + 1)], o = pts[Math.max(0, i - 1)];
                const tng = q.clone().sub(o).normalize();
                const side = V3(1, 0, 0);
                const up = tng.clone().cross(side).negate().normalize();
                for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
                    const v = p.clone().addScaledVector(side, (sx * w) / 2).addScaledVector(up, (sy * h) / 2);
                    pos.push(v.x, v.y, v.z);
                }
            }
            for (let i = 0; i < pts.length - 1; i++) for (let k = 0; k < 4; k++) {
                const a = i * 4 + k, b = i * 4 + ((k + 1) % 4), c = a + 4, d = b + 4;
                idx.push(a, c, b, b, c, d);
            }
            const g = new THREE.BufferGeometry();
            g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
            g.setIndex(idx); g.computeVertexNormals();
            gb.add(g, null, aux);
        };
        const tube = (gb, pts, r, seg = 24, rad = 8, closed = false, aux) =>
            gb.add(own(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, closed), seg, r, rad, closed)), null, aux);
        // closed loft through rings of points (rings ordered along +Z, each ring CCW seen from +Z)
        const loft = (gb, rings, aux, capEnds = true) => {
            const n = rings[0].length, pos = [], idx = [], uvs = [];
            rings.forEach((ring, i) => ring.forEach((p, j) => { pos.push(p.x, p.y, p.z); uvs.push(i / (rings.length - 1), j / n); }));
            for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < n; j++) {
                const a = i * n + j, b = i * n + ((j + 1) % n), c = a + n, d = b + n;
                idx.push(a, b, c, b, d, c);
            }
            if (capEnds) {
                for (const [ri, flip] of [[0, true], [rings.length - 1, false]]) {
                    const ctr = rings[ri].reduce((s, p) => s.add(p), V3(0, 0, 0)).multiplyScalar(1 / n);
                    const ci = pos.length / 3; pos.push(ctr.x, ctr.y, ctr.z); uvs.push(0, 0);
                    for (let j = 0; j < n; j++) { const a = ri * n + j, b = ri * n + ((j + 1) % n); if (flip) idx.push(ci, b, a); else idx.push(ci, a, b); }
                }
            }
            const g = new THREE.BufferGeometry();
            g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
            g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
            g.setIndex(idx); g.computeVertexNormals();
            gb.add(g, null, aux);
        };
        // the bonnet section: flat sides, rounded top corners, flat top; CCW seen from the front
        const bonnetRing = (z, hw, top, bot, rr) => {
            const pts = [];
            const arc = (cx, cy, a0, a1, k) => { for (let i = 0; i <= k; i++) { const a = a0 + ((a1 - a0) * i) / k; pts.push(V3(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, z)); } };
            pts.push(V3(hw, bot, z));
            arc(hw - rr, top - rr, 0, Math.PI / 2, 5);
            arc(-hw + rr, top - rr, Math.PI / 2, Math.PI, 5);
            pts.push(V3(-hw, bot, z));
            return pts;
        };
        // ---------- chassis: pressed-steel rails with dumb irons, cross members, leaf springs, axles
        for (const s of [-1, 1]) {
            bar(B.paint, [V3(s * 0.40, 0.42, 2.12), V3(s * 0.40, 0.56, 1.95), V3(s * 0.40, 0.59, 1.2), V3(s * 0.40, 0.59, -1.0), V3(s * 0.40, 0.58, -2.05)], 0.07, 0.17);
            for (const [zc, yc] of [[CAR.wb / 2, 0.5], [-CAR.wb / 2, 0.49]]) {
                for (let k = 0; k < 5; k++) {
                    const L = 0.5 - k * 0.075, y = yc + 0.012 * k;
                    const pts = []; for (let i = 0; i <= 10; i++) { const u = -1 + (2 * i) / 10; pts.push(V3(s * 0.40, y + 0.055 * u * u, zc + u * L)); }
                    bar(B.steel, pts, 0.055, 0.011);
                }
            }
        }
        for (const z of [1.92, 0.55, -0.55, -1.95]) boxQuads(B.paint, -0.40, 0.55, z - 0.04, 0.40, 0.62, z + 0.04, [0, 0, 0, 0], { bottom: true });
        boxQuads(B.paint, -0.66, 0.41, CAR.wb / 2 - 0.035, 0.66, 0.48, CAR.wb / 2 + 0.035, [0, 0, 0, 0], { bottom: true });
        tube(B.steel, [V3(-0.62, 0.44, CAR.wb / 2 - 0.16), V3(0, 0.43, CAR.wb / 2 - 0.17), V3(0.62, 0.44, CAR.wb / 2 - 0.16)], 0.014, 12, 6);
        boxQuads(B.steel, -0.66, 0.41, -CAR.wb / 2 - 0.04, 0.66, 0.49, -CAR.wb / 2 + 0.04, [0, 0, 0, 0], { bottom: true });
        // countershaft with the differential and the two driving sprockets
        B.steel.add(own(new THREE.CylinderGeometry(0.07, 0.07, 1.12, 14)), M4(0, 0.5, -0.45, 0, 0, Math.PI / 2));
        B.steel.add(own(new THREE.SphereGeometry(0.16, 16, 12)), M4(0, 0.5, -0.45, 0, 0, 0, 1, 0.9, 0.9));
        for (const s of [-1, 1]) B.steel.add(own(new THREE.CylinderGeometry(0.09, 0.09, 0.03, 18)), M4(s * 0.58, 0.5, -0.45, 0, 0, Math.PI / 2));
        // the chains: round the front sprocket's forward half, back along the top run, round the wheel sprocket
        const chainG = new GB();
        for (const s of [-1, 1]) {
            const c1y = 0.5, c1z = -0.45, r1 = 0.09, c2y = 0.45, c2z = -CAR.wb / 2, r2 = 0.24;
            const pts = [];
            for (let i = 0; i <= 10; i++) { const ph = -Math.PI / 2 + (Math.PI * i) / 10; pts.push(V3(s * 0.58, c1y + r1 * Math.sin(ph), c1z + r1 * Math.cos(ph))); }
            for (let i = 0; i <= 16; i++) { const ph = Math.PI / 2 + (Math.PI * i) / 16; pts.push(V3(s * 0.58, c2y + r2 * Math.sin(ph), c2z + r2 * Math.cos(ph))); }
            chainG.add(own(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 90, 0.013, 6, true)), null, [0, 0, 0, 0]);
        }
        // ---------- exhaust: four headers out of the left bonnet side into a fat pipe along the side
        for (let k = 0; k < 4; k++) {
            const z = 1.62 - k * 0.2;
            tube(B.exh, [V3(-0.33, 0.95, z), V3(-0.43, 0.94, z - 0.02), V3(-0.51, 0.82, z - 0.08), V3(-0.53, 0.66, z - 0.16 - k * 0.02)], 0.032, 10, 8);
        }
        tube(B.exh, [V3(-0.53, 0.66, 1.5), V3(-0.53, 0.63, 1.0), V3(-0.52, 0.6, 0.0), V3(-0.52, 0.58, -1.2), V3(-0.5, 0.6, -2.05), V3(-0.48, 0.66, -2.3)], 0.056, 40, 10);
        // ---------- radiator: brass shell around a honeycomb core, filler cap; the number on the core
        boxQuads(B.core, -0.30, 0.56, 1.93, 0.30, 1.18, 2.02, [0, 0, 0, 0], {});
        {
            const sh = new THREE.Shape();
            const ow = 0.35, ot = 1.235, ob = 0.52, rr = 0.07;
            sh.moveTo(-ow, ob); sh.lineTo(ow, ob); sh.lineTo(ow, ot - rr); sh.quadraticCurveTo(ow, ot, ow - rr, ot); sh.lineTo(-ow + rr, ot); sh.quadraticCurveTo(-ow, ot, -ow, ot - rr); sh.closePath();
            const hole = new THREE.Path(); hole.moveTo(-0.30, 0.56); hole.lineTo(-0.30, 1.18); hole.lineTo(0.30, 1.18); hole.lineTo(0.30, 0.56); hole.closePath();
            sh.holes.push(hole);
            B.brass.add(own(new THREE.ExtrudeGeometry(sh, { depth: 0.14, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.01, bevelSegments: 2, curveSegments: 6 })), M4(0, 0, 1.9));
            B.brass.add(own(new THREE.CylinderGeometry(0.042, 0.048, 0.08, 16)), M4(0, 1.28, 1.97));
            B.brass.add(own(new THREE.CylinderGeometry(0.055, 0.055, 0.025, 16)), M4(0, 1.33, 1.97));
        }
        // ---------- bonnet, straps, scuttle
        {
            const rings = [];
            for (let i = 0; i <= 10; i++) { const u = i / 10, z = 1.9 - u * 1.6; rings.push(bonnetRing(z, 0.33 + u * 0.03, 1.18 + u * 0.02, 0.6, 0.075)); }
            loft(B.paint, rings.reverse(), [0, 0, 0, 0]);
            for (const zc of [1.48, 0.82]) {
                const sc = (r, z) => r.map((p) => V3(p.x * 1.03, 0.6 + (p.y - 0.6) * 1.02 + 0.004, z));
                const u = (1.9 - zc) / 1.6;
                const base = bonnetRing(zc, 0.33 + u * 0.03, 1.18 + u * 0.02, 0.6, 0.075);
                loft(B.leatherB, [sc(base, zc - 0.025), sc(base, zc + 0.025)], [0, 0, 0, 0], false);
            }
            const srings = [];
            for (let i = 0; i <= 6; i++) { const u = i / 6, z = 0.3 - u * 0.3; srings.push(bonnetRing(z, 0.36 + u * 0.09, 1.2 + Math.sin(u * Math.PI * 0.5) * 0.12, 0.6, 0.075 + u * 0.08)); }
            loft(B.paint, srings.reverse(), [0, 0, 0, 0]);
        }
        // ---------- cockpit: sides, rear bulkhead, a leather roll round the rim, wooden floor and dash
        for (const s of [-1, 1]) boxQuads(B.paint, s > 0 ? 0.43 : -0.46, 0.6, -1.18, s > 0 ? 0.46 : -0.43, 0.97, 0.0, [0, 0, 0, 0], { bottom: false });
        boxQuads(B.paint, -0.46, 0.6, -1.22, 0.46, 1.02, -1.16, [0, 0, 0, 0], {});
        tube(B.leatherK, [V3(0.45, 0.99, 0.0), V3(0.45, 0.99, -1.18), V3(0.0, 1.03, -1.2), V3(-0.45, 0.99, -1.18), V3(-0.45, 0.99, 0.0)], 0.032, 40, 8);
        boxQuads(B.wood, -0.43, 0.6, -1.16, 0.43, 0.63, 0.0, [0, 0, 0, 0], {});
        boxQuads(B.wood, -0.44, 0.97, -0.01, 0.44, 1.26, 0.03, [0, 0, 0, 0], {});
        for (const [x, r] of [[-0.25, 0.045], [-0.08, 0.035], [0.08, 0.035]]) {
            B.brass.add(own(new THREE.CylinderGeometry(r, r, 0.03, 18)), M4(x, 1.14, -0.02, Math.PI / 2, 0, 0));
            B.glass.add(own(new THREE.CircleGeometry(r * 0.8, 18)), M4(x, 1.14, -0.04, 0, Math.PI, 0));
        }
        // the riding mechanic's oil pump and grab rail
        B.brass.add(own(new THREE.CylinderGeometry(0.03, 0.03, 0.22, 12)), M4(-0.3, 1.12, -0.08));
        tube(B.brass, [V3(-0.43, 1.05, -0.05), V3(-0.43, 1.16, -0.1), V3(-0.43, 1.16, -0.32), V3(-0.43, 1.03, -0.36)], 0.012, 12, 6);
        // ---------- seats: buttoned leather buckets (the backs open forward)
        for (const sx of [-0.24, 0.24]) {
            const cg = own(new THREE.BoxGeometry(0.42, 0.13, 0.46, 2, 1, 2));
            B.leatherK.add(cg, M4(sx, 0.7, -0.72), [1, 0, 0, 0]);
            const th0 = Math.PI - 1.75;
            B.leatherK.add(own(new THREE.CylinderGeometry(0.235, 0.22, 0.52, 22, 1, true, th0, 3.5)), M4(sx, 0.98, -0.78), [1, 0, 0, 0]);
            B.leatherK.add(own(new THREE.CylinderGeometry(0.258, 0.243, 0.52, 22, 1, true, th0, 3.5)), M4(sx, 0.98, -0.78), [0, 0, 0, 0]);
            const rim = []; for (let i = 0; i <= 14; i++) { const a = th0 + (3.5 * i) / 14; rim.push(V3(sx + Math.sin(a) * 0.247, 1.24, -0.78 + Math.cos(a) * 0.247)); }
            tube(B.leatherK, rim, 0.022, 20, 6, false, [0, 0, 0, 0]);
        }
        // ---------- steering: a raked column, a wooden rim on brass spokes (right-hand drive, as the Italians raced)
        const WHL = { c: V3(0.24, 1.3, -0.3), n: V3(0, 0.62, -0.78).normalize(), r: 0.22 };
        {
            const colBase = V3(0.24, 0.66, 0.36);
            tube(B.steel, [colBase, colBase.clone().lerp(WHL.c, 0.5), WHL.c.clone().addScaledVector(WHL.n, -0.02)], 0.022, 6, 8);
            const q = new THREE.Quaternion().setFromUnitVectors(V3(0, 0, 1), WHL.n);
            const m = new THREE.Matrix4().compose(WHL.c, q, V3(1, 1, 1));
            B.wood.add(own(new THREE.TorusGeometry(WHL.r, 0.018, 8, 40)), m);
            for (let k = 0; k < 4; k++) B.brass.add(own(new THREE.BoxGeometry(0.012, WHL.r * 2, 0.008)), m.clone().multiply(M4(0, 0, 0, 0, 0, (k * Math.PI) / 4 + Math.PI / 8)));
            B.brass.add(own(new THREE.CylinderGeometry(0.035, 0.035, 0.04, 14)), m.clone().multiply(M4(0, 0, 0, Math.PI / 2, 0, 0)));
        }
        // ---------- outside levers (gear, brake) with the quadrant, and the bulb horn
        for (const [z, h] of [[-0.36, 0.62], [-0.56, 0.66]]) {
            tube(B.steel, [V3(0.53, 0.6, z - 0.06), V3(0.535, 0.6 + h * 0.5, z - 0.02), V3(0.53, 0.6 + h, z + 0.04)], 0.012, 8, 6);
            B.brass.add(own(new THREE.SphereGeometry(0.028, 12, 10)), M4(0.53, 0.6 + h + 0.02, z + 0.04));
        }
        bar(B.steel, Array.from({ length: 9 }, (_, i) => { const a = -0.5 + i * 0.125; return V3(0.51, 0.62 + Math.cos(a) * 0.3, -0.42 + Math.sin(a) * 0.3); }), 0.01, 0.025);
        tube(B.brass, [V3(0.42, 1.16, -0.05), V3(0.46, 1.1, 0.25), V3(0.43, 1.08, 0.55), V3(0.4, 1.09, 0.72)], 0.014, 16, 6);
        B.brass.add(own(new THREE.LatheGeometry([new THREE.Vector2(0.014, 0), new THREE.Vector2(0.03, 0.08), new THREE.Vector2(0.075, 0.14)], 16)), M4(0.4, 1.09, 0.72, Math.PI / 2, 0, 0));
        B.leatherK.add(own(new THREE.SphereGeometry(0.048, 12, 10)), M4(0.42, 1.17, -0.1, 0, 0, 0, 1, 1.15, 1));
        // ---------- tail: the bolster tank (red, brass bands, cap) and a spare strapped behind it
        B.paint.add(own(new THREE.CylinderGeometry(0.23, 0.23, 0.96, 26)), M4(0, 0.93, -1.46, 0, 0, Math.PI / 2));
        for (const s of [-1, 1]) B.paint.add(own(new THREE.SphereGeometry(0.23, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2)), M4(s * 0.48, 0.93, -1.46, 0, 0, -s * Math.PI / 2, 1, 0.35, 1));
        for (const x of [-0.3, 0.3]) B.brass.add(own(new THREE.TorusGeometry(0.236, 0.011, 8, 32)), M4(x, 0.93, -1.46, 0, Math.PI / 2, 0));
        B.brass.add(own(new THREE.CylinderGeometry(0.05, 0.05, 0.07, 16)), M4(0.22, 1.18, -1.46));
        const spareM = M4(0, 0.74, -1.83);
        for (const x of [-0.18, 0.18]) bar(B.leatherB, Array.from({ length: 12 }, (_, i) => { const a = Math.PI * 0.15 + (i / 11) * Math.PI * 0.7; return V3(x, 0.74 + Math.sin(a) * 0.45, -1.83 + Math.cos(a) * 0.02); }), 0.04, 0.006);
        for (const x of [-0.25, 0.25]) bar(B.leatherB, Array.from({ length: 10 }, (_, i) => { const a = (i / 9) * Math.PI; return V3(x, 0.93 + Math.sin(a) * 0.245, -1.46 + Math.cos(a) * 0.245); }), 0.035, 0.006);

        // ---------- two brass acetylene headlamps on forks either side of the radiator (night running)
        car.lampLens = new GB();
        for (const s of [-1, 1]) {
            const lx = s * 0.47, ly = 0.97, lz = 2.0;
            B.brass.add(own(new THREE.CylinderGeometry(0.105, 0.11, 0.2, 22, 1, false)), M4(lx, ly, lz - 0.02, Math.PI / 2, 0, 0));
            B.brass.add(own(new THREE.TorusGeometry(0.106, 0.014, 8, 26)), M4(lx, ly, lz + 0.085));
            B.brass.add(own(new THREE.CylinderGeometry(0.025, 0.03, 0.09, 10)), M4(lx, ly + 0.14, lz - 0.05));
            B.brass.add(own(new THREE.ConeGeometry(0.045, 0.04, 10)), M4(lx, ly + 0.2, lz - 0.05));
            bar(B.steel, [V3(lx - s * 0.02, 0.6, 1.97), V3(lx, 0.75, 1.98), V3(lx, 0.86, 1.98)], 0.03, 0.03);
            car.lampLens.add(own(new THREE.CircleGeometry(0.094, 24)), M4(lx, ly, lz + 0.082));
        }
        const body = new THREE.Group(); body.name = 'race:carBody';
        car.body = body;
        car.group.add(body);
        for (const [k, gb] of Object.entries(B)) {
            if (!gb.v) continue;
            const mesh = new THREE.Mesh(gb.build(), car.mats[k]);
            mesh.name = 'race:car_' + k;
            body.add(mesh);
        }
        // the chains' links run with the wheels (the material scrolls the link pattern)
        const chainMat = new THREE.MeshStandardNodeMaterial({ metalness: 0.9 });
        {
            const linkU = uv().x.mul(114.0).add(U.chainRun);
            const link = smoothstep(0.2, 0.5, abs(fract(linkU).sub(0.5)).mul(2.0));
            const albedo = mix(linC('#141414'), linC('#4a4642'), link);
            chainMat.colorNode = albedo;
            chainMat.roughnessNode = float(0.4).add(link.mul(0.2));
            chainMat.normalNode = bumpN(link.mul(0.003), 1.0);
            chainMat.emissiveNode = carLight(albedo, 0.5);
        }
        lit(chainMat, 1.0);
        const chains = new THREE.Mesh(chainG.build(), chainMat);
        chains.name = 'race:car_chains';
        body.add(chains);
        const lensMat = own(new THREE.MeshBasicNodeMaterial());
        {
            // a hot white-yellow core with a warm rim (acetylene flame behind a mangin mirror)
            const r = length(uv().sub(0.5)).mul(2.0);
            lensMat.colorNode = mix(linC('#fff0c8'), linC('#ffad55'), smoothstep(0.15, 0.95, r)).mul(U.headlamps.mul(3.2));
        }
        const lensMesh = new THREE.Mesh(car.lampLens.build(), lensMat);
        lensMesh.name = 'race:car_lamps';
        body.add(lensMesh);
        const rubG = new GB();
        rubG.add(own(new THREE.TorusGeometry(0.39, 0.058, 12, 40)), spareM);
        const spare = new THREE.Mesh(rubG.build(), rubber);
        spare.name = 'race:car_spare';
        body.add(spare);

        // ---------- wheels: pale tyre, wooden felloe on a steel band, the smeared spokes, brass hub; the rear
        // wheels carry the chain sprocket ring. Wheel space: axle along X.
        const wheelAt = [[CAR.track / 2, CAR.wb / 2, false], [-CAR.track / 2, CAR.wb / 2, false], [CAR.track / 2, -CAR.wb / 2, true], [-CAR.track / 2, -CAR.wb / 2, true]];
        for (const [x, z, rear] of wheelAt) {
            const pivot = new THREE.Group();
            pivot.position.set(x, CAR.R, z);
            const spin = new THREE.Group();
            pivot.add(spin);
            const s = Math.sign(x);
            const tG = new GB(), wG = new GB(), sG = new GB(), bG = new GB(), stG = new GB();
            tG.add(own(new THREE.TorusGeometry(0.39, 0.06, 12, 44)), M4(0, 0, 0, 0, Math.PI / 2, 0));
            wG.add(own(new THREE.TorusGeometry(0.318, 0.026, 8, 40)), M4(0, 0, 0, 0, Math.PI / 2, 0));
            stG.add(own(new THREE.TorusGeometry(0.337, 0.013, 6, 40)), M4(0, 0, 0, 0, Math.PI / 2, 0));
            sG.add(own(new THREE.CircleGeometry(0.33, 48)), M4(s * 0.005, 0, 0, 0, Math.PI / 2, 0));
            bG.add(own(new THREE.CylinderGeometry(0.075, 0.095, 0.2, 18)), M4(0, 0, 0, 0, 0, Math.PI / 2));
            bG.add(own(new THREE.CylinderGeometry(0.06, 0.07, 0.06, 18)), M4(s * 0.12, 0, 0, 0, 0, Math.PI / 2));
            if (rear) stG.add(own(new THREE.TorusGeometry(0.24, 0.018, 6, 40)), M4(-s * 0.12, 0, 0, 0, Math.PI / 2, 0));
            for (const [gb, mat, nm] of [[tG, rubber, 'tyre'], [wG, wood, 'felloe'], [sG, spokes, 'spokes'], [bG, brass, 'hub'], [stG, steel, 'band']]) {
                const mesh = new THREE.Mesh(gb.build(), mat);
                mesh.name = 'race:wheel_' + nm;
                spin.add(mesh);
            }
            car.group.add(pivot);
            car.wheels.push({ pivot, spin, front: !rear });
        }
    }

    // ---------- the cosplayers: driver (right) and riding mechanic (left) in dusters, leather helmets, brass goggles
    // and white silk scarves pulled up over the face. Stylised figures; no faces show.
    {
        const coat = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        {
            const a = attribute('aux', 'vec4');
            const p = positionLocal;
            const n = nz(vec2(p.x.add(p.z).mul(3.0), p.y.mul(3.0)), 1.0);
            const folds = nz(vec2(p.x.mul(2.0).add(p.z), p.y.mul(9.0)), 1.0).g;
            const albedo = mix(linC('#8b7451'), linC('#4c4e44'), a.x).mul(n.r.mul(0.35).add(0.75));
            coat.colorNode = albedo;
            coat.roughnessNode = float(0.78);
            coat.normalNode = bumpN(folds.mul(0.006), 1.0);
            coat.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI);
        }
        lit(coat, 0.8);
        const silk = new THREE.MeshStandardNodeMaterial({ metalness: 0, side: THREE.DoubleSide });
        silk.colorNode = linC('#ece6d8');
        silk.roughnessNode = float(0.38);
        silk.emissiveNode = linC('#ece6d8').mul(fieldLight(PL, NL)).mul(2.0 / Math.PI);
        lit(silk, 1.0);
        const silkTail = new THREE.MeshStandardNodeMaterial({ metalness: 0, side: THREE.DoubleSide });
        {
            // the scarf tails stream back and flutter: amplitude grows down the tail; speed lifts them level
            const a = attribute('aux', 'vec4');
            const d = a.x;                                    // 0 at the neck .. 1 at the tip
            const ph = a.y;
            const f1 = sin(d.mul(9.0).sub(U.time.mul(17.0)).add(ph)).mul(0.07);
            const f2 = sin(d.mul(5.0).sub(U.time.mul(11.0)).add(ph.mul(2.0))).mul(0.05);
            const droop = float(1.0).sub(U.scarfSpeed).mul(d).mul(d).mul(0.55);
            silkTail.positionNode = positionLocal.add(vec3(f2.mul(d), f1.mul(d).mul(U.scarfSpeed.mul(0.8).add(0.2)).sub(droop), 0.0));
            silkTail.colorNode = linC('#ece6d8');
            silkTail.roughnessNode = float(0.38);
            // white silk catches every lamp it streams through (a sheen on both faces): the riders' signature at speed
            silkTail.emissiveNode = linC('#ece6d8').mul(fieldLight(PL, NL).mul(2.4).add(fieldLight(PL, NL.negate()).mul(1.2))).mul(1 / Math.PI);
        }
        lit(silkTail, 1.0);
        const RB = { coat: new GB(), helmet: new GB(), silk: new GB(), tail: new GB(), brass: new GB(), glass: new GB() };
        const tubeR = (gb, pts, r, aux) => gb.add(own(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 16, r, 8, false)), null, aux);
        const ellRing = (cx, cy, cz, w, d, n = 18) => Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2; return V3(cx + Math.cos(a) * w / 2, cy, cz + Math.sin(a) * d / 2); });
        const rider = (sx, role, tint) => {
            const zc = -0.74, lean = 0.30;            // m forward per m up
            const zAt = (y) => zc + (y - 0.74) * lean;
            const rings = [[0.74, 0.36, 0.25], [0.9, 0.33, 0.23], [1.06, 0.37, 0.25], [1.2, 0.43, 0.25], [1.3, 0.40, 0.21], [1.355, 0.15, 0.14]]
                .map(([y, w, d]) => ellRing(sx, y, zAt(y), w, d));
            const n = rings[0].length, pos = [], idx = [];
            rings.forEach((r) => r.forEach((p) => pos.push(p.x, p.y, p.z)));
            for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < n; j++) { const a = i * n + j, b = i * n + ((j + 1) % n); idx.push(a, a + n, b, b, a + n, b + n); }
            const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
            RB.coat.add(g, null, [tint, 0, 0, 0]);
            RB.coat.add(own(new THREE.TorusGeometry(0.085, 0.032, 8, 18)), M4(sx, 1.35, zAt(1.35), Math.PI / 2, 0, 0), [tint, 0, 0, 0]);
            // head: helmet, the scarf over the face, goggles and strap
            const hz = zAt(1.49) + 0.02;
            RB.helmet.add(own(new THREE.SphereGeometry(0.108, 20, 14)), M4(sx, 1.495, hz, 0, 0, 0, 0.92, 1.06, 1.1));
            for (const s of [-1, 1]) RB.helmet.add(own(new THREE.BoxGeometry(0.02, 0.07, 0.06)), M4(sx + s * 0.098, 1.45, hz - 0.005));
            RB.silk.add(own(new THREE.CylinderGeometry(0.098, 0.104, 0.12, 18)), M4(sx, 1.415, hz + 0.008));
            const gq = M4(sx, 1.515, hz + 0.105);
            for (const s of [-1, 1]) {
                RB.brass.add(own(new THREE.TorusGeometry(0.031, 0.008, 8, 18)), gq.clone().multiply(M4(s * 0.04, 0, 0, 0, s * 0.22, 0)));
                RB.brass.add(own(new THREE.CylinderGeometry(0.03, 0.033, 0.03, 18, 1, true)), gq.clone().multiply(M4(s * 0.04, 0, -0.012, Math.PI / 2, 0, 0)));
                RB.glass.add(own(new THREE.CircleGeometry(0.029, 18)), gq.clone().multiply(M4(s * 0.04, 0, 0.004, 0, s * 0.22, 0)));
            }
            RB.helmet.add(own(new THREE.TorusGeometry(0.104, 0.008, 6, 26)), M4(sx, 1.515, hz, Math.PI / 2, 0, 0, 0.94, 1.12, 1));
            // arms and gauntlets
            const shY = 1.26, shZ = zAt(1.26);
            let hands;
            if (role === 'driver') {
                const c = V3(0.24, 1.3, -0.3), nW = V3(0, 0.62, -0.78).normalize(), right = V3(1, 0, 0), upW = nW.clone().cross(right).negate().normalize();
                hands = [c.clone().addScaledVector(right, -0.19).addScaledVector(upW, 0.1), c.clone().addScaledVector(right, 0.19).addScaledVector(upW, 0.1)];
            } else hands = [V3(-0.43, 1.16, -0.2), V3(-0.3, 1.18, -0.08)];
            [-1, 1].forEach((s, i) => {
                const sh = V3(sx + s * 0.2, shY, shZ);
                const hd = hands[i];
                const el = sh.clone().lerp(hd, 0.5).add(V3(s * 0.08, -0.12, -0.04));
                tubeR(RB.coat, [sh, el, hd.clone().add(V3(0, 0, -0.06))], 0.05, [tint, 0, 0, 0]);
                const dir = hd.clone().sub(el).normalize();
                const gm = new THREE.Matrix4().compose(hd.clone().addScaledVector(dir, -0.07), new THREE.Quaternion().setFromUnitVectors(V3(0, 1, 0), dir), V3(1, 1, 1));
                RB.helmet.add(own(new THREE.CylinderGeometry(0.045, 0.062, 0.11, 12)), gm);
                RB.helmet.add(own(new THREE.SphereGeometry(0.045, 10, 8)), M4(hd.x, hd.y, hd.z, 0, 0, 0, 1, 0.8, 1.3));
            });
            // the scarf tail: from the nape, streaming back; aux.x = distance down the tail, aux.y = flutter phase
            const tg = own(new THREE.PlaneGeometry(0.15, 1.25, 1, 18));
            const P = tg.attributes.position;
            const dd = [];
            for (let k = 0; k < P.count; k++) {
                const d = (0.625 - P.getY(k)) / 1.25;
                dd.push(d);
                P.setXYZ(k, sx + P.getX(k) * (1 - 0.5 * d) + (role === 'driver' ? 0.04 : -0.04) * d, 1.42 + 0.08 * d, hz - 0.09 - d * 1.25);
            }
            tg.computeVertexNormals();
            const start = RB.tail.a.length;
            RB.tail.add(tg, null, [0, role === 'driver' ? 0.0 : 2.1, 0, 0]);
            for (let j = 0; j < dd.length; j++) RB.tail.a[start + j * 4] = dd[j];
        };
        rider(0.24, 'driver', 0);
        rider(-0.24, 'mechanic', 1);
        const rg = new THREE.Group(); rg.name = 'race:riders';
        for (const [gb, mat, nm] of [[RB.coat, coat, 'coats'], [RB.helmet, car.mats.leatherB, 'helmets'], [RB.silk, silk, 'scarves'], [RB.tail, silkTail, 'scarfTails'], [RB.brass, car.mats.brass, 'goggles'], [RB.glass, car.mats.glass, 'lenses']]) {
            const mesh = new THREE.Mesh(gb.build(), mat);
            mesh.name = 'race:rider_' + nm;
            if (nm === 'scarfTails') mesh.frustumCulled = false;
            rg.add(mesh);
        }
        car.body.add(rg);
        car.riders = rg;
    }
    // contact shadow: a soft dark pad under the car while it is on the deck
    {
        const m = noMrt(own(new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false })));
        const q = uv().sub(0.5).mul(2.0);
        m.colorNode = vec3(0.0);
        m.opacityNode = smoothstep(1.0, 0.25, length(q)).mul(0.8).mul(U.carShadow);
        const pad = new THREE.Mesh(own(new THREE.PlaneGeometry(1.9, 4.6)), m);
        pad.rotation.x = -Math.PI / 2;
        pad.position.y = 0.012;
        pad.renderOrder = 2;
        pad.name = 'race:carShadow';
        noRefl.push(pad);
        car.shadow = pad;
        group.add(pad);
    }
    group.add(car.group);
    parts.car = car.group;
    parts.riders = car.riders;
    parts.carRig = car;

    // the car's path: lane 1, a drift right through the works onto the closed lanes, to the broken edge
    // (carT = 1: the front wheels at the edge)
    const carPath = new THREE.CatmullRomCurve3([V3(3.6, 0, -300), V3(3.6, 0, -120), V3(3.6, 0, 20), V3(3.1, 0, 50), V3(2.2, 0, 72), V3(1.8, 0, D.gap0 - CAR.wb / 2 - 0.2)], false, 'centripetal');
    const carLen = carPath.getLength();
    car.path = carPath; car.length = carLen;
    if (Math.abs(carLen - CAR_LEN) > 0.5) console.warn(`[race] car path is ${carLen.toFixed(2)} m; update CAR_LEN`);

    // ---------- the crash: off the broken edge at 22 m/s; the nose drops, digs into the drain and the car goes over
    // onto its back, wheels in the air (Marinetti, 1909: "...rolled over into a ditch with my wheels in the air").
    const CR = { v: 22, tImp: 1.31, tFlip: 1.95, tEnd: 3.0, restY: D.ch.bottom + (CAR.top - CAR.com[1]) };
    const comLocal = V3(...CAR.com), noseLocal = V3(...CAR.nose);
    const qTmp = new THREE.Quaternion(), eTmp = new THREE.Euler();
    const smooth01 = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
    function crashPose(tc, start, yaw0) {
        const x0 = start.x, z0 = start.z + comLocal.z;
        const flight = (t) => ({
            com: V3(x0 - 0.25 * t, CAR.com[1] - 4.905 * t * t, z0 + CR.v * t - 0.9 * t * t),
            pitch: 0.2 * Math.min(1, t / 0.15) + 0.3 * Math.max(0, t - 0.15), roll: 0.1 * t, yaw: yaw0 - 0.04 * t,
        });
        const out = { spin: CR.v / CAR.R };
        if (tc <= CR.tImp) return Object.assign(out, flight(Math.max(0, tc)));
        const f = flight(CR.tImp);
        eTmp.set(f.pitch, f.yaw, f.roll, 'YXZ'); qTmp.setFromEuler(eTmp);
        const noseRel = noseLocal.clone().sub(comLocal);
        const pivot0 = f.com.clone().add(noseRel.clone().applyQuaternion(qTmp));
        const s = Math.min(1, (tc - CR.tImp) / (CR.tFlip - CR.tImp));
        const fs = s < 0.5 ? 2 * s * s : 1 - Math.pow(-2 * s + 2, 2) / 2;      // over the top, then the slam
        const pitch = f.pitch + (Math.PI - f.pitch) * fs;
        const roll = f.roll * (1 - fs) + 0.05 * fs, yaw = f.yaw - 0.12 * fs;
        eTmp.set(pitch, yaw, roll, 'YXZ'); qTmp.setFromEuler(eTmp);
        const pivot = pivot0.clone().add(V3(0, 0, 0.7 * fs));
        const com = pivot.clone().sub(noseRel.clone().applyQuaternion(qTmp));
        const settle = smooth01((tc - CR.tFlip + 0.25) / 0.5);
        com.y = com.y * (1 - settle) + CR.restY * settle;
        Object.assign(out, { com, pitch, roll, yaw });
        if (tc > CR.tFlip) {
            const u = tc - CR.tFlip;
            out.pitch += 0.05 * Math.exp(-3.5 * u) * Math.sin(10 * u);
            out.roll += 0.035 * Math.exp(-3.0 * u) * Math.sin(8 * u + 1);
            out.com.y += 0.06 * Math.exp(-4 * u) * Math.sin(12 * u);
        }
        out.spin = (CR.v / CAR.R) * Math.exp(-Math.max(0, tc - CR.tImp) / 1.4);
        return out;
    }
    car.crashPose = crashPose;
    car.CR = CR;

    // ------------------------------------------------------------------------------------------- the roadworks
    // The right carriageway is closed for the bridge works: a diagonal taper of drums with sequential amber lamps,
    // an LED arrow board running its chevrons, sawhorse barricades across the closed lanes, two light-tower trailers
    // at the broken edge (the crash's key light), the low floodlight that throws the march, and a tower crane over
    // the gap. The car hits one drum and the middle barricade: every hit is a closed-form function of the car's
    // distance along its path, so it seeks.
    const works = { debris: [] };
    {
        const paintW = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        {
            // orange / white retro-reflective bands (aux.x selects: 0 drum, 1 barricade board, 2 trailer/board body)
            const a = attribute('aux', 'vec4');
            const p = positionLocal;
            const bandsD = step(0.5, fract(p.y.mul(3.4)));                         // drums: horizontal bands
            const bandsB = step(0.5, fract(p.x.add(p.y).mul(2.6)));                // boards: diagonal stripes
            const isD = step(a.x, 0.5), isB = step(0.5, a.x).mul(step(a.x, 1.5)), isBody = step(1.5, a.x);
            const band = bandsD.mul(isD).add(bandsB.mul(isB));
            const n = nz(vec2(p.x.add(p.z), p.y).mul(3.0), 1.0);
            const col = mix(mix(linC('#e8501c'), linC('#e9e6dc'), band), linC('#2b2d30'), isBody).mul(n.r.mul(0.3).add(0.8));
            const grime = smoothstep(0.35, 0.0, p.y).mul(0.5).add(smoothstep(0.6, 0.9, n.g).mul(0.3));
            const albedo = col.mul(float(1.0).sub(grime));
            paintW.colorNode = albedo;
            paintW.roughnessNode = float(0.5).add(grime.mul(0.3));
            // retro-reflective white catches every lamp and headlamp (a glow of the light field, a touch of the beam)
            const retro = band.mul(float(1.0).sub(isBody));
            paintW.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI).add(albedo.mul(retro).mul(U.headlamps).mul(0.25));
        }
        lit(paintW, 0.8);
        works.mat = paintW;
        const wG = new GB(), wSteel = new GB(), wGlow = new GB();
        // the drum taper
        const [t0, t1] = [D.works.taper0, D.works.taper1];
        const NDR = 12;
        const pathAtZ = (z) => {            // path distance of the car at a given z (straight bits are close enough)
            let lo = 0, hi = 1; for (let i = 0; i < 30; i++) { const m = (lo + hi) / 2; if (car.path.getPointAt(m).z < z) lo = m; else hi = m; }
            return lo * car.length;
        };
        for (let k = 0; k < NDR; k++) {
            const u = k / (NDR - 1);
            const x = t0[0] + (t1[0] - t0[0]) * u, z = t0[1] + (t1[1] - t0[1]) * u;
            const hit = Math.abs(x - 3.5) < 0.95;
            const drumG = new GB();
            drumG.add(own(new THREE.CylinderGeometry(0.28, 0.3, 0.9, 16)), M4(0, 0.45, 0), [0, 0, 0, 0]);
            drumG.add(own(new THREE.CylinderGeometry(0.42, 0.42, 0.08, 16)), M4(0, 0.04, 0), [2, 0, 0, 0]);
            const lampP = V3(0, 1.0, 0);
            if (hit) {
                const g = new THREE.Group(); g.position.set(x, 0, z);
                const mesh = new THREE.Mesh(drumG.build(), paintW); mesh.name = 'race:drum_hit';
                g.add(mesh);
                group.add(g);
                works.debris.push({ obj: g, s0: pathAtZ(z), home: V3(x, 0, z), v: V3(1.8, 4.2, 13.0), w: V3(7.0, 2.0, 4.0), r: 0.35 });
            } else {
                for (let i = 0; i < drumG.v; i++) { drumG.p[i * 3] += x; drumG.p[i * 3 + 2] += z; }
                wG.p.push(...drumG.p); wG.n.push(...drumG.n); wG.u.push(...drumG.u); wG.a.push(...drumG.a);
                wG.i.push(...drumG.i.map((v) => v + wG.v)); wG.v += drumG.v;
                // its amber lamp (sequential: the flash runs down the taper toward the closure)
                wGlow.add(own(new THREE.SphereGeometry(0.075, 10, 8)), M4(x, 1.0, z), [1.0, 0.62, 0.12, u]);
                wSteel.add(own(new THREE.CylinderGeometry(0.02, 0.02, 0.12, 6)), M4(x, 0.94, z));
            }
        }
        // sawhorse barricades across the closed lanes; the middle one is in the car's way
        const bz = D.works.barrier;
        const barricade = (cx, hit) => {
            const legs = new GB(), boards = new GB();
            for (const sx of [-1.05, 1.05]) for (const sz of [-1, 1]) legs.add(own(new THREE.BoxGeometry(0.06, 1.15, 0.06)), M4(sx, 0.55, sz * 0.22, sz * 0.2, 0, 0), [2, 0, 0, 0]);
            for (const [y, h] of [[1.0, 0.24], [0.6, 0.2]]) boards.add(own(new THREE.BoxGeometry(2.4, h, 0.035)), M4(0, y, 0), [1, 0, 0, 0]);
            if (hit) {
                const parts2 = [];
                const lm = new THREE.Mesh(legs.build(), paintW); lm.name = 'race:barricade_legs';
                const bm = new THREE.Mesh(boards.build(), paintW); bm.name = 'race:barricade_boards';
                for (const [m, v, w] of [[lm, V3(-2.2, 3.0, 9.0), V3(3.0, 6.0, 1.0)], [bm, V3(1.4, 5.5, 15.0), V3(9.0, 3.0, 6.0)]]) {
                    const g = new THREE.Group(); g.position.set(cx, 0, bz); g.add(m); group.add(g);
                    works.debris.push({ obj: g, s0: pathAtZ(bz), home: V3(cx, 0, bz), v, w, r: 0.3 });
                }
            } else {
                for (const gb of [legs, boards]) { for (let i = 0; i < gb.v; i++) { gb.p[i * 3] += cx; gb.p[i * 3 + 2] += bz; } wG.p.push(...gb.p); wG.n.push(...gb.n); wG.u.push(...gb.u); wG.a.push(...gb.a); wG.i.push(...gb.i.map((v) => v + wG.v)); wG.v += gb.v; }
            }
        };
        barricade(-0.2, false); barricade(2.3, true); barricade(4.8, false); barricade(7.3, false);
        // the arrow board trailer on the closed shoulder, facing the oncoming traffic
        const AB = { x: D.works.board[0], z: D.works.board[1] };
        boxQuads(wG, AB.x - 0.8, 0.35, AB.z - 1.2, AB.x + 0.8, 0.85, AB.z + 1.2, [2, 0, 0, 0], { bottom: true });
        wSteel.add(own(new THREE.BoxGeometry(0.12, 2.4, 0.12)), M4(AB.x, 1.6, AB.z));
        boxQuads(wG, AB.x - 1.25, 2.1, AB.z - 0.12, AB.x + 1.25, 3.5, AB.z - 0.02, [2, 0, 0, 0], { bottom: true });
        for (const s of [-1, 1]) wSteel.add(own(new THREE.CylinderGeometry(0.3, 0.3, 0.2, 14)), M4(AB.x + s * 0.85, 0.3, AB.z, 0, 0, Math.PI / 2));
        // light-tower trailers at the broken edge (the WORK lights' bodies)
        for (const [lp] of WORK.slice(0, 2)) {
            const [lx, ly, lz] = lp;
            boxQuads(wG, lx - 0.7, 0.3, lz - 1.6, lx + 0.7, 1.4, lz + 1.6, [2, 0, 0, 0], { bottom: true });
            wSteel.add(own(new THREE.BoxGeometry(0.16, ly - 1.4, 0.16)), M4(lx, (ly + 1.4) / 2, lz));
            wSteel.add(own(new THREE.BoxGeometry(1.6, 0.1, 0.1)), M4(lx, ly + 0.35, lz));
            for (const s of [-0.55, -0.18, 0.18, 0.55]) {
                wSteel.add(own(new THREE.BoxGeometry(0.34, 0.26, 0.1)), M4(lx + s, ly, lz + 0.06, -0.85, 0, 0));
                wGlow.add(own(new THREE.PlaneGeometry(0.28, 0.2)), M4(lx + s, ly - 0.05, lz + 0.12, Math.PI / 2 + 0.72, 0, 0), [0.88, 0.92, 1.0, 3]);
            }
        }
        // the march's floodlight: a low LED flood on a stand, on the far shoulder, aimed across at the wall
        {
            const [fx, fy, fz] = D.flood;
            const yaw = Math.atan2(D.wall.x - fx, 38.0 - fz);
            const m = M4(fx, fy + 0.25, fz, -0.25, yaw, 0);
            for (const s of [-1, 1]) wSteel.add(own(new THREE.BoxGeometry(0.04, 0.5, 0.04)), M4(fx + s * 0.25, 0.25, fz, 0, 0, s * 0.3));
            wSteel.add(own(new THREE.BoxGeometry(0.7, 0.45, 0.16)), m);
            wGlow.add(own(new THREE.PlaneGeometry(0.62, 0.38)), m.clone().multiply(M4(0, 0, 0.085)), [1.0, 0.93, 0.82, 4]);
        }
        // the tower crane over the gap: an X-braced lattice mast and jib (Balla's crisscross against the sky)
        {
            const cx = -11.5, cz = 101.0, top = 48.0, w = 1.8;
            const lattice = (p0, p1, wid) => {
                const L = p0.distanceTo(p1), dir = p1.clone().sub(p0).normalize();
                const q = new THREE.Quaternion().setFromUnitVectors(V3(0, 1, 0), dir);
                const base = new THREE.Matrix4().compose(p0, q, V3(1, 1, 1));
                const nSeg = Math.max(1, Math.round(L / wid));
                for (const [ox, oz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) wSteel.add(own(new THREE.BoxGeometry(0.14, L, 0.14)), base.clone().multiply(M4((ox * wid) / 2, L / 2, (oz * wid) / 2)));
                for (let i = 0; i < nSeg; i++) {
                    const y0 = (i * L) / nSeg, y1 = ((i + 1) * L) / nSeg, dl = Math.hypot(wid, y1 - y0), ang = Math.atan2(wid, y1 - y0);
                    for (const [face, rx] of [[0, 1], [1, -1]]) {
                        const off = face ? M4(0, (y0 + y1) / 2, wid / 2, 0, 0, ((i % 2) * 2 - 1) * ang) : M4(wid / 2, (y0 + y1) / 2, 0, ((i % 2) * 2 - 1) * ang * rx, 0, 0);
                        wSteel.add(own(new THREE.BoxGeometry(0.07, dl, 0.07)), base.clone().multiply(off));
                    }
                }
            };
            lattice(V3(cx, D.ground, cz), V3(cx, top, cz), w);
            lattice(V3(cx - 12, top + 1.0, cz), V3(cx + 34, top + 1.0, cz), 1.2);
            wSteel.add(own(new THREE.BoxGeometry(5, 3, 3)), M4(cx - 8, top + 0.2, cz));
            wSteel.add(own(new THREE.CylinderGeometry(0.03, 0.03, 18, 6)), M4(cx + 22, top - 8.0, cz));
            wSteel.add(own(new THREE.BoxGeometry(0.5, 0.7, 0.3)), M4(cx + 22, top - 17.2, cz));
            wGlow.add(own(new THREE.SphereGeometry(0.25, 10, 8)), M4(cx + 34, top + 1.6, cz), [1.0, 0.05, 0.03, 2]);
            wGlow.add(own(new THREE.SphereGeometry(0.25, 10, 8)), M4(cx, top + 4.5, cz), [1.0, 0.05, 0.03, 2]);
        }
        const wm = new THREE.Mesh(wG.build(), paintW); wm.name = 'race:works';
        const ws = new THREE.Mesh(wSteel.build(), mats.steel); ws.name = 'race:worksSteel';
        for (const m of [wm, ws]) { m.userData.noSupportCheck = true; group.add(m); }
        // the lamps: sequential amber flashers, the LED panels, the crane's red lights (aux.w selects the behaviour)
        const gm = own(new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide }));
        {
            const a = attribute('aux', 'vec4');
            const k = a.w;
            const seq = step(0.82, fract(U.time.mul(1.6).sub(k.mul(0.9)))).mul(step(k, 1.0));     // drums: a running flash
            const crane = step(1.5, k).mul(step(k, 2.5)).mul(step(0.5, fract(U.time.mul(0.8))));
            const led = step(2.5, k).mul(step(k, 3.5)).mul(U.works);
            const flood = step(3.5, k).mul(U.march.mul(0.92).add(0.08));
            gm.colorNode = a.xyz.mul(seq.mul(9.0).add(step(k, 1.0).mul(0.35)).add(crane.mul(10.0)).add(led.mul(14.0)).add(flood.mul(22.0)));
        }
        const glowM = new THREE.Mesh(wGlow.build(), gm); glowM.name = 'race:worksLamps';
        glowM.userData.noSupportCheck = true;
        group.add(glowM);
        // the arrow board's LED face: three amber chevrons running toward the open lanes (world +X)
        const am = own(new THREE.MeshBasicNodeMaterial());
        {
            const q = uv();
            // the board faces -Z (toward the traffic); seen from there +X is on the viewer's right... so the
            // chevrons point to uv -x after the 180 degree turn below
            const x = float(1.0).sub(q.x).mul(3.0), y = q.y.sub(0.5);
            const cell = floor(x), f = fract(x);
            const chev = smoothstep(0.1, 0.04, abs(f.sub(0.65).add(abs(y).mul(0.9)))).mul(step(abs(y), 0.36));
            const on = step(cell, floor(fract(U.time.mul(1.25)).mul(4.0)).sub(0.5));
            const dots = smoothstep(0.42, 0.2, length(fract(q.mul(vec2(48.0, 22.0))).sub(0.5)));
            am.colorNode = linC('#ffa31a').mul(chev.mul(on).mul(dots).mul(11.0).add(0.02));
        }
        const arrow = new THREE.Mesh(own(new THREE.PlaneGeometry(2.4, 1.3)), am);
        arrow.position.set(AB.x, 2.8, AB.z - 0.13); arrow.rotation.y = Math.PI;
        arrow.name = 'race:arrowBoard';
        group.add(arrow);
        parts.works = { drums: wm, steel: ws, lamps: glowM, arrow, debris: works.debris };
    }

    // ------------------------------------------------------------------------------------------- the heel
    // "...black shirts and a heel": one jackboot comes down on the manifesto lying in the puddle. A close prop, built
    // here: a knee-high riding boot (polished black leather, ankle creases, a stacked leather heel with a steel tap
    // and hobnails), black wool breeches tucked in, and the 1909 manifesto's page soaking in the water. state.heel
    // 0..1 runs the stamp (descend, hover, slam at 0.68, the toe slaps down, planted).
    const HEEL = { dur: 2.2, strike: 0.68 };
    const heel = { root: new THREE.Group(), pivot: new THREE.Group() };
    {
        const loftR = (rings, { caps = true, open = false } = {}) => {
            const n = rings[0].length, pos = [], idx = [], uvs = [];
            rings.forEach((ring, i) => ring.forEach((p, j) => { pos.push(p.x, p.y, p.z); uvs.push(j / n, i / (rings.length - 1)); }));
            for (let i = 0; i < rings.length - 1; i++) for (let j = 0; j < n; j++) {
                const a = i * n + j, b = i * n + ((j + 1) % n), c = a + n, d = b + n;
                idx.push(a, b, c, b, d, c);
            }
            if (caps) for (const [ri, flip] of [[0, true], [rings.length - 1, false]]) {
                if (open && ri === rings.length - 1) continue;
                const ctr = rings[ri].reduce((s2, p) => s2.add(p), V3(0, 0, 0)).multiplyScalar(1 / n);
                const ci = pos.length / 3; pos.push(ctr.x, ctr.y, ctr.z); uvs.push(0.5, ri ? 1 : 0);
                for (let j = 0; j < n; j++) { const a = ri * n + j, b = ri * n + ((j + 1) % n); if (flip) idx.push(ci, b, a); else idx.push(ci, a, b); }
            }
            const g = new THREE.BufferGeometry();
            g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
            g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
            g.setIndex(idx); g.computeVertexNormals();
            return g;
        };
        const lerpT = (tab, z) => {     // piecewise-linear table lookup [[z, v], ...]
            if (z <= tab[0][0]) return tab[0][1];
            for (let i = 1; i < tab.length; i++) if (z <= tab[i][0]) { const [a, va] = tab[i - 1], [b, vb] = tab[i]; return va + (vb - va) * (z - a) / (b - a); }
            return tab[tab.length - 1][1];
        };
        const sm = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
        const W = [[-0.046, 0.026], [-0.036, 0.035], [0.0, 0.038], [0.04, 0.036], [0.1, 0.033], [0.17, 0.047], [0.22, 0.046], [0.255, 0.034], [0.278, 0.01]];
        const TOP = [[-0.046, 0.09], [-0.035, 0.125], [-0.02, 0.142], [0.0, 0.152], [0.03, 0.166], [0.07, 0.158], [0.11, 0.128], [0.15, 0.1], [0.19, 0.078], [0.225, 0.064], [0.25, 0.05], [0.272, 0.03]];
        const soleBot = (z) => (z < 0.04 ? 0.038 : z < 0.16 ? 0.038 * (1 - sm((z - 0.04) / 0.12)) : 0.012 * sm((z - 0.2) / 0.075));
        const ZS = [-0.046, -0.04, -0.03, -0.015, 0.0, 0.03, 0.06, 0.09, 0.12, 0.15, 0.18, 0.21, 0.235, 0.255, 0.268, 0.278];
        // the upper: D-shaped sections (flat on the sole, a domed top), toe capped
        const upper = loftR(ZS.map((z) => {
            const w = lerpT(W, z) - 0.0015, b = soleBot(z) + 0.012, t = Math.max(b + 0.008, lerpT(TOP, z));
            const yc = (b + t) / 2, h = (t - b) / 2, pts = [];
            for (let k = 0; k < 28; k++) {
                const a = (k / 28) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
                const x = w * Math.sign(c) * Math.pow(Math.abs(c), 0.7);
                const y = Math.max(b + 0.003, yc + h * Math.sign(s) * Math.pow(Math.abs(s), 0.8));
                pts.push(V3(-x, y, z));
            }
            return pts;
        }));
        // the shaft: an elliptic tube from the ankle to below the knee, a slight forward rake, open at the top
        const SY = [0.11, 0.15, 0.2, 0.26, 0.32, 0.38, 0.43, 0.47];
        const HW = [0.04, 0.041, 0.045, 0.051, 0.055, 0.054, 0.055, 0.058], HD = [0.05, 0.052, 0.055, 0.06, 0.064, 0.062, 0.063, 0.066];
        const shaft = loftR(SY.map((y, i) => {
            const zc = 0.004 + (y - 0.11) * 0.05, pts = [];
            for (let k = 0; k < 28; k++) { const a = (k / 28) * Math.PI * 2; pts.push(V3(Math.cos(a) * HW[i], y, zc + Math.sin(a) * HD[i])); }
            return pts;
        }), { caps: false });
        // the sole: a slab following the outline, its bottom on the heel then the ground
        const sole = loftR(ZS.map((z) => {
            const w = lerpT(W, z) + 0.002, b = soleBot(z), t = b + 0.013, pts = [];
            for (const [x, y] of [[-w, b], [w, b], [w, t], [-w, t]]) pts.push(V3(x, y, z));
            return pts;
        }));
        // the heel block (stacked leather) and its steel tap
        const heelRing = (y) => { const pts = []; for (let k = 0; k <= 16; k++) { const a = Math.PI * (k / 16); pts.push(V3(-0.034 * Math.cos(a), y, -0.004 - 0.042 * Math.sin(a))); } pts.push(V3(0.034, y, 0.042)); pts.push(V3(-0.034, y, 0.042)); return pts; };
        const heelBlock = loftR([heelRing(0.0), heelRing(0.039)]);
        const tap = own(new THREE.TorusGeometry(0.03, 0.003, 4, 20, Math.PI));
        // breeches: black wool from inside the boot top, flaring up out of frame
        const BY = [0.42, 0.5, 0.62, 0.78, 0.95, 1.1];
        const breech = loftR(BY.map((y, i) => {
            const r = [0.05, 0.056, 0.066, 0.078, 0.082, 0.08][i], zc = 0.016 + (y - 0.42) * 0.04, pts = [];
            for (let k = 0; k < 24; k++) { const a = (k / 24) * Math.PI * 2; pts.push(V3(Math.cos(a) * r, y, zc + Math.sin(a) * r * 1.1)); }
            return pts;
        }), { caps: false });

        // materials
        const leather = new THREE.MeshPhysicalNodeMaterial({ metalness: 0, clearcoat: 0.8, side: THREE.DoubleSide });
        {
            const p = positionLocal;
            const n = nz(vec2(p.x.add(p.z).mul(9.0), p.y.mul(9.0)), 1.0);
            const ankle = smoothstep(0.08, 0.12, p.y).mul(smoothstep(0.24, 0.15, p.y));
            const crease = sin(p.y.mul(260.0).add(n.r.mul(9.0))).mul(0.5).add(0.5).mul(ankle);
            const scuff = smoothstep(0.6, 0.85, n.g).mul(smoothstep(0.17, 0.25, p.z)).mul(step(p.y, 0.09));
            const seam = smoothstep(0.004, 0.0, abs(p.x)).mul(step(p.z, 0.0)).mul(step(0.16, p.y));
            const albedo = mix(linC('#0b0807'), linC('#3a332c'), scuff.mul(0.6)).mul(float(1.0).sub(seam.mul(0.5)));
            leather.colorNode = albedo;
            leather.roughnessNode = float(0.2).add(crease.mul(0.25)).add(scuff.mul(0.4));
            leather.clearcoatNode = float(0.85).sub(scuff.mul(0.6));
            leather.clearcoatRoughnessNode = float(0.1).add(crease.mul(0.1));
            const bead = smoothstep(0.78, 0.92, nz(vec2(p.x.add(p.z), p.y).mul(60.0), 1.0).b).mul(U.wet);
            leather.normalNode = bumpN(crease.mul(0.0009).add(bead.mul(0.0004)).add(n.b.mul(0.0002)), 1.0);
            // the close key's highlight on polished, wet leather (a hard rim that cuts the boot out of the dark)
            const Lh = vec3(...WORK[3][0]);
            const lh = normalize(Lh.sub(PL)), vh = normalize(CL.sub(PL));
            const dh = max(dot(Lh.sub(PL), Lh.sub(PL)), 0.5);
            const rimSpec = pow(max(dot(NL, normalize(lh.add(vh))), 0.0), 70.0).mul(max(dot(NL, lh), 0.0)).mul(WORK[3][4] * 2.2).div(dh).mul(U.heelKey);
            // and the fear screen behind it outlines the silhouette in red (a backlit edge on the polished leather)
            const fres = pow(float(1.0).sub(max(dot(NL, vh), 0.0)), 3.0).mul(U.heelKey).mul(U.billB);
            leather.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI).add(lampGlint(PL, NL, vh, float(120.0)).mul(0.04))
                .add(linC('#fff1dc').mul(rimSpec.mul(2.5)).mul(float(1.0).sub(scuff.mul(0.7))))
                .add(linC('#ff3a24').mul(fres.mul(0.55)));
        }
        lit(leather, 1.8);
        const stack = new THREE.MeshStandardNodeMaterial({ metalness: 0, side: THREE.DoubleSide });
        {
            const p = positionLocal;
            const layers = sin(p.y.mul((2 * Math.PI) / 0.0065)).mul(0.5).add(0.5);
            const albedo = mix(linC('#2a1a10'), linC('#4d3220'), layers).mul(nz(p.xz.mul(30.0), 1.0).r.mul(0.4).add(0.75));
            stack.colorNode = albedo;
            stack.roughnessNode = float(0.7);
            stack.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI);
        }
        lit(stack, 0.8);
        const wool = new THREE.MeshPhysicalNodeMaterial({ metalness: 0, sheen: 0.6, sheenRoughness: 0.5, side: THREE.DoubleSide });
        {
            const p = positionLocal;
            const n = nz(vec2(p.x.add(p.z).mul(40.0), p.y.mul(40.0)), 1.0);
            const albedo = linC('#121212').mul(n.b.mul(0.4).add(0.8));
            wool.colorNode = albedo;
            wool.roughnessNode = float(0.92);
            wool.sheenColorNode = linC('#3a3a3a');
            wool.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI);
        }
        lit(wool, 0.6);

        const HG = { leather: new GB(), stack: new GB(), wool: new GB(), steel: new GB() };
        HG.leather.add(upper); HG.leather.add(shaft);
        HG.leather.add(own(new THREE.TorusGeometry(1, 0.06, 6, 28)), M4(0, 0.47, 0.004 + 0.36 * 0.05, Math.PI / 2, 0, 0, 0.058, 0.066, 0.06));
        HG.stack.add(sole); HG.stack.add(heelBlock);
        HG.wool.add(breech);
        HG.steel.add(tap, M4(0, 0.0015, -0.004, Math.PI / 2, 0, Math.PI));
        const R2 = rng(77);
        for (let k = 0; k < 14; k++) { const z = 0.13 + R2() * 0.13, x = (R2() - 0.5) * 2 * (lerpT(W, z) - 0.008); HG.steel.add(own(new THREE.SphereGeometry(0.0035, 6, 4)), M4(x, soleBot(z) - 0.0005, z)); }
        for (const [k, mat] of [['leather', leather], ['stack', stack], ['wool', wool], ['steel', mats.steelLight]]) {
            const mesh = new THREE.Mesh(HG[k].build(), mat);
            mesh.name = 'race:boot_' + k;
            heel.pivot.add(mesh);
        }
        heel.root.add(heel.pivot);
        heel.root.position.set(D.heel[0], 0, D.heel[2]);
        heel.root.rotation.y = Math.PI / 2 - 0.3;                  // toe toward +X, a little toward the heel camera
        heel.root.name = 'race:heel';
        heel.root.visible = false;
        heel.root.userData.noSupportCheck = true;
        group.add(heel.root);

        // the page: Marinetti's 1909 manifesto (the 1914 Italian text), soaked, lying in the puddle
        const PW = 768, PH = 1086;
        const [pc, pg] = cv(PW, PH);
        {
            pg.fillStyle = '#e6dfcc'; pg.fillRect(0, 0, PW, PH);
            const R3 = rng(1909);
            for (let i = 0; i < 1400; i++) { pg.fillStyle = `rgba(120,96,60,${0.02 + R3() * 0.05})`; pg.fillRect(R3() * PW, R3() * PH, 1 + R3() * 3, 1 + R3() * 3); }
            pg.fillStyle = '#1b1712'; pg.textBaseline = 'alphabetic';
            pg.font = 'bold 26px Georgia, "Times New Roman", serif'; pg.textAlign = 'center';
            pg.fillText('FONDAZIONE E', PW / 2, 70);
            pg.font = 'bold 66px Georgia, "Times New Roman", serif';
            pg.fillText('MANIFESTO DEL', PW / 2, 140);
            pg.fillText('FUTURISMO', PW / 2, 208);
            pg.fillRect(40, 228, PW - 80, 4); pg.fillRect(40, 236, PW - 80, 1.5);
            pg.font = 'italic 20px Georgia, "Times New Roman", serif';
            pg.fillText('F. T. Marinetti — 1909', PW / 2, 262);
            const pts = [
                '1. Noi vogliamo cantare l’amor del pericolo, l’abitudine all’energia e alla temerità.',
                '2. Il coraggio, l’audacia, la ribellione, saranno elementi essenziali della nostra poesia.',
                '4. Noi affermiamo che la magnificenza del mondo si è arricchita di una bellezza nuova: la bellezza della velocità. Un automobile da corsa col suo cofano adorno di grossi tubi simili a serpenti dall’alito esplosivo.... un automobile ruggente, che sembra correre sulla mitraglia, è più bello della Vittoria di Samotracia.',
                '9. Noi vogliamo glorificare la guerra — sola igiene del mondo — il militarismo, il patriottismo, il gesto distruttore dei libertarî, le belle idee per cui si muore e il disprezzo della donna.',
            ];
            pg.textAlign = 'left';
            pg.font = '21px Georgia, "Times New Roman", serif';
            const colW = (PW - 120) / 2, lead = 27;
            let col = 0, y = 310;
            const xs = [44, 44 + colW + 32];
            for (const para of pts) {
                const words = para.split(' ');
                let line = '';
                const flush = () => { pg.fillText(line, xs[col], y); y += lead; if (y > PH - 50) { col++; y = 310; } line = ''; };
                for (const w of words) { const test = line ? line + ' ' + w : w; if (pg.measureText(test).width > colW && line) flush(); line = line ? line + ' ' + w : w; }
                if (line) flush();
                y += lead * 0.6;
            }
            pg.fillRect(PW / 2 + 6, 300, 1.2, PH - 340);
        }
        const pageTex = canvasTex(pc, { srgb: true, mips: true });
        const pgeo = new THREE.PlaneGeometry(0.297, 0.42, 24, 34);
        pgeo.rotateX(-Math.PI / 2);
        {
            const P = pgeo.attributes.position;
            for (let k = 0; k < P.count; k++) {
                const x = P.getX(k), z = P.getZ(k);
                const crumple = Math.sin(x * 61 + z * 17) * 0.0016 + Math.sin(x * 23 - z * 41) * 0.0012 + Math.max(0, x + z - 0.25) * 0.05;
                P.setY(k, 0.0035 + crumple);
            }
            pgeo.computeVertexNormals();
        }
        const pageAt = { x: D.heel[0] - 0.05, z: D.heel[2] + 0.06, yaw: 0.42 };
        // the heel strike point in page space (for the print)
        {
            const v = V3(D.heel[0] - pageAt.x, 0, D.heel[2] - pageAt.z).applyAxisAngle(V3(0, 1, 0), -pageAt.yaw);
            HEEL.print = [v.x, v.z];
        }
        const pmat = new THREE.MeshStandardNodeMaterial({ metalness: 0, side: THREE.DoubleSide });
        {
            const p = positionLocal;
            const q = uv();
            const ink = texture(pageTex, vec2(q.x, float(1.0).sub(q.y))).rgb;
            const soak = smoothstep(0.3, 0.55, nz(p.xz.mul(14.0), 1.0).r.add(0.25)).mul(0.6).add(0.4).mul(U.wet);
            // the heel print (a U of mud and the pressed ball of the sole) appears when the heel lands
            const hp = vec2(p.x.sub(HEEL.print[0]), p.z.sub(HEEL.print[1]));
            const ring = smoothstep(0.012, 0.004, abs(length(hp.mul(vec2(1.0, 0.85))).sub(0.03)));
            const plate = smoothstep(0.036, 0.026, length(hp));
            const printK = clamp(ring.mul(0.8).add(plate.mul(0.35)), 0.0, 1.0).mul(step(0.0, U.heelAge)).mul(smoothstep(0.0, 0.08, U.heelAge));
            const paper = mix(float(0.62), float(0.3), soak);
            const albedo = mix(ink.mul(paper).add(linC('#2a2418').mul(soak.mul(0.08))), linC('#1e170f'), printK);
            pmat.colorNode = albedo;
            pmat.roughnessNode = mix(float(0.7), float(0.25), soak.add(printK).clamp(0, 1));
            pmat.emissiveNode = albedo.mul(fieldLight(PL, NL)).mul(1 / Math.PI);
        }
        lit(pmat, 0.7);
        const page = new THREE.Mesh(pgeo, pmat);
        own(pgeo);
        page.name = 'race:manifesto';
        page.position.set(pageAt.x, 0, pageAt.z); page.rotation.y = pageAt.yaw;
        group.add(page);
        heel.page = page;
        parts.heel = { root: heel.root, pivot: heel.pivot, page, dur: HEEL.dur, strike: HEEL.strike };
    }

    // ------------------------------------------------------------------------------------------- rain
    // Slanted streaks in a box that travels with the camera (wrapped, so it never runs out), each lit by the lamp
    // field at its own position: they glint inside the light cones and vanish in the dark between them.
    if (opts.rain !== false) {
        const N = opts.rainCount ?? 5200;
        const BOX = [34, 22, 34];
        const pos = new Float32Array(N * 12), cor = new Float32Array(N * 8), sd = new Float32Array(N * 16), idx = [];
        const R = rng(4711);
        for (let q = 0; q < N; q++) {
            const s4 = [R(), R(), R(), R()];
            [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([cx, cy], k) => { cor.set([cx, cy], (q * 4 + k) * 2); sd.set(s4, (q * 4 + k) * 4); });
            idx.push(q * 4, q * 4 + 1, q * 4 + 2, q * 4, q * 4 + 2, q * 4 + 3);
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        g.setAttribute('corner', new THREE.BufferAttribute(cor, 2));
        g.setAttribute('seed', new THREE.BufferAttribute(sd, 4));
        g.setIndex(N * 4 > 65535 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
        own(g);
        const m = noMrt(own(new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));
        const s = attribute('seed', 'vec4'), c = attribute('corner', 'vec2');
        const speed = mix(8.0, 11.0, s.w);
        const fall = normalize(vec3(-0.26, -1.0, 0.1));                  // the wind leans the rain: a diagonal
        const box = vec3(...BOX);
        // drop centre: seeded in the box, falling along `fall`, wrapped round the camera
        const travel = U.time.mul(speed);
        const raw = vec3(s.x, s.y, s.z).mul(box).add(fall.mul(travel));
        const rel = raw.sub(CL).div(box).add(0.5);
        const ctr = fract(rel).sub(0.5).mul(box).add(CL);
        const toCam = normalize(CL.sub(ctr));
        const side = normalize(cross(fall, toCam));
        const L = 0.6, Wd = 0.009;
        m.positionNode = ctr.add(fall.mul(c.y.mul(L * 0.5))).add(side.mul(c.x.mul(Wd)));
        const dist = length(CL.sub(ctr));
        const fade = smoothstep(0.8, 2.0, dist).mul(smoothstep(19.0, 9.0, dist));
        // weighted to the sodium row: the works' LED floods are close and hot, and would turn the drain shots to static
        const vL = varying(lampField(ctr, toCam).mul(SODIUM).mul(0.6).add(lampField(ctr, vec3(0, 1, 0)).mul(SODIUM).mul(0.5))
            .add(workField(ctr, toCam).mul(WORK_COL).mul(0.12)).add(vec3(0.02, 0.03, 0.045)).mul(fade), 'vRainLight');
        const along = float(1.0).sub(abs(c.y));
        const across = float(1.0).sub(abs(c.x));
        m.colorNode = vL.mul(along.mul(across).mul(1.35)).mul(U.rain);
        const rain = new THREE.Mesh(g, m);
        rain.name = 'race:rain';
        noRefl.push(rain);
        rain.frustumCulled = false;
        rain.renderOrder = 9;
        rain.userData.noSupportCheck = rain.userData.noClippingCheck = true;
        group.add(rain);
        parts.rain = rain;
    }

    // ------------------------------------------------------------------------------------------- the drain's water
    // Muddy factory run-off, flowing slowly to -X. Ring waves from the two impacts lift the surface (vertex) and
    // ripple its light (normal); foam gathers round the wreck; the work lights glint in it.
    {
        const wm = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
        const C = D.ch;
        const waveH = (P2) => {
            const flow = nz(P2.add(vec2(U.time.mul(0.35), 0.0)), 0.18).r.sub(0.5).mul(0.03)
                .add(nz(P2.add(vec2(U.time.mul(0.5), U.time.mul(0.1))), 0.9).b.sub(0.5).mul(0.012));
            const ring = (age, cp, amp) => {
                const r = length(P2.sub(cp.xz));
                const front = age.mul(4.2);
                return sin(r.sub(front).mul(5.0)).mul(exp(r.sub(front).abs().mul(-1.6))).mul(exp(age.mul(-0.9))).mul(step(0.0, age)).mul(amp)
                    .mul(smoothstep(0.0, 0.6, r));
            };
            return flow.add(ring(U.crashAge, U.crashP, 0.22)).add(ring(U.flipAge, U.flipP, 0.16));
        };
        wm.positionNode = Fn(() => {
            const p = positionLocal;
            return vec3(p.x, p.y.add(waveH(PL.xz)), p.z);
        })();
        const h = waveH(PL.xz);
        const fq = vec2(PL.x.add(U.time.mul(0.35)).mul(0.06), PL.z.mul(0.55));
        const foam = smoothstep(0.66, 0.8, nz(fq, 1.0).r).mul(0.45)
            .add(smoothstep(0.6, 0.85, nz(PL.xz.mul(0.8).add(vec2(U.time.mul(0.25), 0.0)), 1.0).r)
                .mul(smoothstep(4.0, 0.6, length(PL.xz.sub(U.steamP.xz)))).mul(U.steam).mul(0.8));
        const albedo = mix(linC('#1b1810'), linC('#6f6a5e'), clamp(foam, 0.0, 1.0));
        wm.colorNode = albedo;
        wm.roughnessNode = mix(float(0.07), float(0.6), clamp(foam, 0.0, 1.0));
        const nV = bumpN(h, 1.0);
        wm.normalNode = nV;
        // the work lights' glints: a sharp lobe on the rippled normal
        const nW = normalize(U.setInv.mul(cameraWorldMatrix.mul(vec4(nV, 0.0))).xyz);
        const V = normalize(CL.sub(PL));
        const glint = float(0).toVar();
        for (const [lp] of WORK.slice(0, 3)) {
            const l = normalize(vec3(...lp).sub(PL));
            glint.addAssign(pow(max(dot(nW, normalize(l.add(V))), 0.0), 700.0));
        }
        wm.emissiveNode = albedo.mul(fieldLight(PL, vec3(0, 1, 0))).mul(1 / Math.PI).add(WORK_COL.mul(glint.mul(U.works).mul(0.45)));
        lit(wm, 1.0);
        const wg = new GB();
        const x0 = -14, x1 = 18, nxs = 64, nzs = 28, zA = C.b0 - 1.0, zB = C.b1 + 1.0;
        const grid = new THREE.PlaneGeometry(x1 - x0, zB - zA, nxs, nzs);
        grid.rotateX(-Math.PI / 2);
        wg.add(grid, M4((x0 + x1) / 2, C.water, (zA + zB) / 2));
        wg.quad(V3(-260, C.water, zB), V3(x0, C.water, zB), V3(x0, C.water, zA), V3(-260, C.water, zA));
        wg.quad(V3(x1, C.water, zB), V3(260, C.water, zB), V3(260, C.water, zA), V3(x1, C.water, zA));
        const water = new THREE.Mesh(wg.build(), wm);
        water.name = 'race:water';
        water.frustumCulled = false;
        group.add(water);
        parts.water = water;
    }

    // ------------------------------------------------------------------------------------------- splash, steam
    // One sprite mesh; every particle is a closed-form function of its seed and the impact clocks (deterministic,
    // seekable): the crown of mud thrown up by the nose, a mist sheet, the slam when the car lands on its back,
    // steam off the drowned engine, and the droplets from the boot heel.
    {
        const KINDS = [[0, 520], [1, 60], [2, 360], [3, 90], [4, 90]];
        const n = KINDS.reduce((a, [, c]) => a + c, 0);
        const pos = new Float32Array(n * 12), cor = new Float32Array(n * 8), seed = new Float32Array(n * 16), idx = [];
        const R = rng(31337);
        let q = 0;
        for (const [kind, count] of KINDS) for (let i = 0; i < count; i++, q++) {
            const sd = [kind, R(), R(), R()];
            [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([cx, cy], k) => { cor.set([cx, cy], (q * 4 + k) * 2); seed.set(sd, (q * 4 + k) * 4); });
            idx.push(q * 4, q * 4 + 1, q * 4 + 2, q * 4, q * 4 + 2, q * 4 + 3);
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        g.setAttribute('corner', new THREE.BufferAttribute(cor, 2));
        g.setAttribute('seed', new THREE.BufferAttribute(seed, 4));
        g.setIndex(idx);
        own(g);
        const m = noMrt(own(new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false })));
        const sd = attribute('seed', 'vec4');
        const kind = sd.x, r1 = sd.y, r2 = sd.z, r3 = sd.w;
        const is = (k) => step(k - 0.5, kind).mul(step(kind, k + 0.5));
        const TAU = Math.PI * 2;
        const ballistic = (age, o, out, up, a) => vec3(cos(a).mul(out).mul(age), up.mul(age).sub(age.mul(age).mul(4.905)), sin(a).mul(out).mul(age)).add(o);
        // kind 0: the crown
        const a0 = U.crashAge;
        const p0 = ballistic(a0, U.crashP, mix(1.0, 6.0, r2), mix(3.5, 10.0, r3), r1.mul(TAU));
        const al0 = step(0.0, a0).mul(step(a0, 2.6)).mul(step(D.ch.water - 0.02, p0.y));
        // kind 1: the mist sheet
        const a1 = U.crashAge;
        const rr1 = mix(0.6, 3.8, r2).mul(float(1.0).sub(exp(a1.mul(-3.0))));
        const p1 = vec3(cos(r1.mul(TAU)).mul(rr1), mix(0.3, 2.6, r3).mul(float(1.0).sub(exp(a1.mul(-2.2)))), sin(r1.mul(TAU)).mul(rr1)).add(U.crashP);
        const al1 = step(0.0, a1).mul(exp(a1.mul(-1.3)));
        // kind 2: the slam
        const a2 = U.flipAge;
        const p2 = ballistic(a2, U.flipP, mix(2.5, 7.0, r2), mix(1.0, 4.2, r3), r1.mul(TAU));
        const al2 = step(0.0, a2).mul(step(a2, 2.0)).mul(step(D.ch.water - 0.02, p2.y));
        // kind 3: steam, looping puffs while the engine is hot
        const cyc = fract(U.time.mul(0.34).add(r1));
        const a3 = cyc.mul(2.9);
        const p3 = U.steamP.add(vec3(r2.sub(0.5).mul(0.9).add(sin(a3.mul(1.5).add(r1.mul(6.0))).mul(0.35).mul(a3)), a3.mul(mix(0.7, 1.5, r3)).add(0.1),
            r3.sub(0.5).mul(1.2).add(cos(a3.mul(1.3).add(r2.mul(6.0))).mul(0.3).mul(a3))));
        const al3 = U.steam.mul(smoothstep(0.0, 0.35, a3)).mul(float(1.0).sub(cyc)).mul(0.55);
        // kind 4: the heel's droplets
        const a4 = U.heelAge;
        const p4 = ballistic(a4, vec3(D.heel[0], 0.0, D.heel[2]), mix(0.25, 1.4, r2), mix(0.5, 2.3, r3), r1.mul(TAU));
        const al4 = step(0.0, a4).mul(step(a4, 1.0)).mul(step(-0.005, p4.y));
        const P = p0.mul(is(0)).add(p1.mul(is(1))).add(p2.mul(is(2))).add(p3.mul(is(3))).add(p4.mul(is(4)));
        const alive = al0.mul(is(0)).add(al1.mul(is(1))).add(al2.mul(is(2))).add(al3.mul(is(3))).add(al4.mul(is(4)));
        const size = mix(0.035, 0.11, r2).mul(is(0).add(is(2))).add(mix(0.4, 1.0, r2).mul(float(0.5).add(a1)).mul(is(1)))
            .add(mix(0.3, 0.6, r2).add(a3.mul(0.9)).mul(is(3))).add(mix(0.0018, 0.005, r1).mul(is(4)));
        // vertical speed of the ballistic kinds (for the motion stretch)
        const vy = mix(3.5, 10.0, r3).sub(a0.mul(9.81)).mul(is(0)).add(mix(1.0, 4.2, r3).sub(a2.mul(9.81)).mul(is(2)))
            .add(mix(0.5, 2.3, r3).sub(a4.mul(9.81)).mul(is(4)));
        const stretch = float(1.0).add(abs(vy).mul(0.11));
        const vLight = varying(fieldLight(P, vec3(0, 1, 0)).add(vec3(0.02)), 'vSplashLight');
        const vAlpha = varying(alive, 'vSplashAlpha');
        const vSoft = varying(is(1).add(is(3)), 'vSplashSoft');
        m.vertexNode = Fn(() => {
            const mv = modelViewMatrix.mul(vec4(P, 1.0));
            const sz = size.mul(step(0.001, alive));
            const c = attribute('corner', 'vec2');
            return cameraProjectionMatrix.mul(vec4(mv.xyz.add(vec3(c.x.mul(sz), c.y.mul(sz).mul(stretch), 0.0)), 1.0));
        })();
        const cq = attribute('corner', 'vec2');
        const d = length(cq);
        const drop = smoothstep(1.0, 0.55, d);
        const soft = pow(smoothstep(1.0, 0.0, d), 1.6);
        const shape = mix(drop, soft, vSoft);
        const tint = mix(linC('#4f4230'), mix(linC('#7a6e5c'), linC('#b9b2a6'), is(3)), vSoft);
        // heel droplets catch the key as bright beads; the rest is mud and steam lit by the field
        m.colorNode = tint.mul(vLight).mul(0.45).add(tint.mul(0.025)).add(vec3(1.6, 1.5, 1.35).mul(is(4)).mul(U.heelKey));
        m.opacityNode = shape.mul(vAlpha).mul(mix(float(0.95), mix(float(0.22), float(0.32), is(3)), vSoft));
        const fx = new THREE.Mesh(g, m);
        fx.name = 'race:splash';
        noRefl.push(fx);
        fx.frustumCulled = false;
        fx.renderOrder = 8;
        fx.userData.noSupportCheck = fx.userData.noClippingCheck = true;
        group.add(fx);
        parts.splash = fx;
    }

    // ------------------------------------------------------------------------------------------- real lights
    // Few and always present (a light that appears recompiles every material): the singer's lamp, the two screens'
    // glow, a cold rim from up the road, a dim sky fill. Everything else in the set is lit analytically.
    const lights = new THREE.Group(); lights.name = 'race:lights';
    const key = new THREE.SpotLight(0xffa04e, 190, 34, 0.62, 0.65, 2.0);
    key.position.set(D.lampR.head[0], D.lampR.head[1] - 0.15, 0.0);
    key.target.position.set(0.3, 0, 0.6);
    lights.add(key, key.target);
    const glowA = new THREE.PointLight(0xffb040, 0, 140, 2.0);
    const glowB = new THREE.PointLight(0xff2418, 0, 140, 2.0);
    for (const [L, B] of [[glowA, D.billA], [glowB, D.billB]]) {
        L.position.set(B.x + Math.sin(B.yaw) * 6, B.y - 2, B.z + Math.cos(B.yaw) * 6);
        lights.add(L);
    }
    const rim = new THREE.DirectionalLight(0x5fd2ff, 0.8);
    rim.position.set(-3, 8, -30); rim.target.position.set(0, 0.8, 0);
    lights.add(rim, rim.target);
    // the two screens behind her, as a warm backlight on her silhouette: black techwear needs its edges (red-gold, the
    // colour the two machine-gods make together), low behind her mark so it rims shoulders, arms and legs
    const backRim = new THREE.SpotLight(0xff6a38, 110, 14, 0.5, 0.7, 1.8);
    backRim.position.set(0.9, 2.6, -4.6); backRim.target.position.set(0.0, 1.0, 0.2);
    lights.add(backRim, backRim.target);
    // the barrier's cyan neon tube beside her mark, as a small fill on her left side
    const neonFill = new THREE.PointLight(0x2fe0ff, 7, 4.5, 2.0);
    neonFill.position.set(-1.5, 0.95, -0.5);
    lights.add(neonFill);
    const hemi = new THREE.HemisphereLight(0x1a2438, 0x120c0a, 0.35);
    lights.add(hemi);
    // the car's headlamp beam lives here (always present) and is carried by update() to the car's nose
    const beam = new THREE.SpotLight(0xffdca8, 0, 70, 0.42, 0.55, 1.6);
    lights.add(beam, beam.target);
    car.beam = beam;
    group.add(lights);
    parts.lights = { key, glowA, glowB, rim, backRim, neonFill, hemi, group: lights };
    const LIGHT_BASE = { key: key.intensity, glow: 1300, rim: rim.intensity, hemi: hemi.intensity, backRim: backRim.intensity, neonFill: neonFill.intensity };

    // ------------------------------------------------------------------------------------------- cameras
    const cams = {
        singer: { pos: [1.35, 1.5, 5.4], target: [0.15, 1.38, 0.0], fov: 36 },
        billboards: { pos: [8.2, 1.3, -20.0], target: [8.6, 13.5, -64.0], fov: 52 },
        billA: { pos: [12.0, 7.2, -41.5], target: [33.5, 15.2, -64.0], fov: 34, roll: 0.05 },
        billB: { pos: [7.0, 7.2, -41.5], target: [-14.5, 15.2, -64.0], fov: 34, roll: -0.05 },
        carPass: { pos: [-0.9, 0.55, 12.0], target: [3.8, 1.0, -40.0], fov: 48 },
        carChase: { pos: [6.4, 1.6, 30.0], target: [2.4, 0.4, 92.0], fov: 46 },
        crash: { pos: [-17.0, -4.4, 104.5], target: [1.5, -4.6, 107.5], fov: 60, roll: 0.05 },
        // static stand-ins for the moving cameras (camAt gives the real ones)
        crashLow: { pos: [-7.5, -7.1, 112.6], target: [1.6, -6.4, 114.0], fov: 54, roll: -0.08 },
        carTrack: { pos: [-1.4, 1.25, 1.0], target: [3.6, 0.85, 0.5], fov: 44, roll: 0.07 },
        shadows: { pos: [12.0, 1.7, 6.0], target: [-22.0, 11.0, 40.0], fov: 52 },
        // low on the road looking up the wall: the column high across the frame, the wet road and its neon below
        // (room for a caption in the lower third)
        shadowsWide: { pos: [3.4, 0.95, 9.0], target: [-22.0, 3.2, 39.0], fov: 56, roll: -0.03 },
        heel: { pos: [-0.36, 0.13, 10.42], target: [-0.5, 0.2, 9.6], fov: 44, roll: 0.06 },
        heelTop: { pos: [-0.18, 0.78, 10.12], target: [-0.6, 0.03, 9.62], fov: 42, roll: -0.12 },
    };

    // Park the set outside its section without recompiling the film: meshes hidden, lights kept present at 0.
    let active = true;
    function setActive(on) {
        active = !!on;
        for (const ch of group.children) if (ch !== lights) ch.visible = active;
        if (!active) { key.intensity = 0; glowA.intensity = 0; glowB.intensity = 0; rim.intensity = 0; hemi.intensity = 0; car.beam.intensity = 0; backRim.intensity = 0; neonFill.intensity = 0; }
        else { rim.intensity = LIGHT_BASE.rim; hemi.intensity = LIGHT_BASE.hemi; }
    }

    // Moving cameras that follow the car (set-local {pos, target, fov, roll}); call after update(t, state).
    //   carChase  behind and left of the car, low, the road and the works ahead (Russolo's chevrons)
    //   carSide   a studio three-quarter on the car (craft checks)        carFront  the radiator coming at you
    function camAt(name, t, state = {}) {
        const g = car.group;
        if (name === 'crashLow') {
            // low on the near bank by the water, panning with the car as it comes over and into the drain
            const tgt = g.visible && (state.crash ?? 0) > 0 ? g.localToWorld(V3(0, 0.7, 0.3)).applyMatrix4(U.setInv.value) : V3(1.6, -7.5, 116);
            return { pos: [-7.5, -7.1, 112.6], target: tgt.toArray(), fov: 54, roll: -0.08 };
        }
        if (!['carChase', 'carTrack', 'carSide', 'carFront', 'carRear'].includes(name) || !g.visible) return null;
        const p = g.position.clone();
        const tg = car.path.getTangentAt(Math.min(1, Math.max(0, (state.carS ?? (state.carT ?? 0) * car.length) / car.length)));
        const yaw = Math.atan2(tg.x, tg.z);
        const rot = (x, y, z) => V3(x, y, z).applyAxisAngle(V3(0, 1, 0), yaw).add(p);
        if ((state.crash ?? 0) > 0) return null;
        const shake = (k) => [Math.sin(t * 31) * k, Math.sin(t * 27 + 1) * k];
        if (name === 'carChase') { const [a, b] = shake(0.015); return { pos: rot(2.1 + a, 1.15 + b, -6.2).toArray(), target: rot(-0.4, 0.75, 9.0).toArray(), fov: 52, roll: -0.06 }; }
        // tracking alongside on the shoulder side, in profile: the riders, the scarves, the smeared spokes, the city
        // (and the singer) streaming past behind them: Russolo's car, Balla's speed
        if (name === 'carTrack') { const [a, b] = shake(0.01); return { pos: rot(-5.0 + a, 1.25 + b, 0.7).toArray(), target: rot(0, 0.85, 0.25).toArray(), fov: 44, roll: 0.07 }; }
        if (name === 'carSide') return { pos: rot(4.6, 1.05, 2.2).toArray(), target: rot(0, 0.75, 0.2).toArray(), fov: 34 };
        if (name === 'carFront') return { pos: rot(1.6, 0.9, 5.5).toArray(), target: rot(0, 0.85, 0.8).toArray(), fov: 36 };
        return { pos: rot(-2.2, 1.6, -4.6).toArray(), target: rot(0, 1.0, 0.0).toArray(), fov: 38 };
    }

    // where each shot's idol sits (set-local), for the painting's sun cones (aeropittura's focal). The march's idol is
    // its floodlight, just off the right of both shadow shots (in front of the lens): the cones fan in along its beam.
    const FOCAL = {
        singer: [0.0, 1.45, 0.0], billboards: [9.6, 16.0, -64.0], billA: [D.billA.x, D.billA.y + 2, D.billA.z],
        billB: [D.billB.x, D.billB.y + 2, D.billB.z], carPass: [3.6, 1.0, -30.0], carTrack: [3.6, 1.0, 40.0], carChase: [2.0, 0.0, D.gap0],
        crash: [1.6, -8.5, 121.0], crashLow: [1.6, -6.0, 112.0], shadowsWide: [D.flood[0], 0.6, D.flood[2]], heelTop: [D.heel[0], 0.0, D.heel[2]], shadows: [D.flood[0], 0.6, D.flood[2]], heel: [D.heel[0] + 0.05, 0.75, D.heel[2] - 0.2],
    };
    const focal = (name) => FOCAL[name] || FOCAL.singer;

    // ------------------------------------------------------------------------------------------- update
    function update(t, state = {}) {
        group.updateMatrixWorld();
        U.setInv.value.copy(group.matrixWorld).invert();
        U.time.value = t;
        U.rain.value = state.rain ?? 1;
        U.wet.value = state.wet ?? 1;
        U.lamps.value = state.lamps ?? 1;
        const bb = state.billboards ?? 1;
        U.billA.value = (state.billA ?? 1) * bb;
        U.billB.value = (state.billB ?? 1) * bb;
        U.gaze.value = state.gaze ?? 0;
        U.march.value = state.march ?? 0;
        U.marchT.value = state.marchT ?? t;
        // ---- the car: on the path (carT / carS), or in the crash (crash 0..1 = 3 s from the broken edge)
        const crash = Math.min(1, Math.max(0, state.crash ?? 0));
        car.group.visible = state.car !== false;
        const R = CAR.R;
        let sDist = state.carS ?? (state.carT ?? 0) * car.length;
        sDist = Math.min(car.length, Math.max(0, sDist));
        const v = state.carV ?? (sDist > 0 && sDist < car.length ? CR.v : 0);
        const shutter = 1 / 120;                         // half a 60 fps frame
        let wheelAng, spinRate;
        if (crash <= 0) {
            const u = sDist / car.length;
            const p = car.path.getPointAt(u), tg = car.path.getTangentAt(u);
            const yaw = Math.atan2(tg.x, tg.z);
            car.group.position.copy(p);
            car.group.rotation.set(0, yaw, 0, 'YXZ');
            // the road: an expansion joint every 36 m kicks the body; the engine shakes it; speed squats the tail
            const joint = Math.exp(-Math.pow(((sDist % 36) + 36) % 36 - 3, 2) * 1.5);
            car.body.position.y = 0.004 * Math.sin(t * 61) * (v > 0 ? 1 : 0.3) + 0.012 * joint;
            car.body.rotation.x = -0.006 * Math.min(1, v / 20) + 0.004 * joint;
            car.body.rotation.z = 0.003 * Math.sin(t * 23);
            wheelAng = sDist / R;
            spinRate = v / R;
            car.shadow.visible = true;
            car.shadow.position.set(p.x, 0.012, p.z); car.shadow.rotation.set(-Math.PI / 2, 0, yaw);
            U.carShadow.value = car.group.visible ? 1 : 0;
            U.crashAge.value = -10; U.flipAge.value = -10; U.steam.value = 0;
        } else {
            const start = car.path.getPointAt(1), tg = car.path.getTangentAt(1);
            const tc = crash * CR.tEnd;
            const pose = car.crashPose(tc, start, Math.atan2(tg.x, tg.z));
            eTmp.set(pose.pitch, pose.yaw, pose.roll, 'YXZ'); qTmp.setFromEuler(eTmp);
            car.group.quaternion.copy(qTmp);
            car.group.position.copy(pose.com).sub(comLocal.clone().applyQuaternion(qTmp));
            car.body.position.set(0, 0, 0); car.body.rotation.set(0, 0, 0);
            const w0 = CR.v / R, tau = 1.4;
            wheelAng = car.length / R + w0 * Math.min(tc, CR.tImp) + (tc > CR.tImp ? w0 * tau * (1 - Math.exp(-(tc - CR.tImp) / tau)) : 0);
            spinRate = pose.spin;
            U.carShadow.value = Math.max(0, 1 - tc * 6);
            car.shadow.position.set(start.x, 0.012, start.z + CR.v * tc);
            // impacts for the splash and the water rings
            const f = car.crashPose(CR.tImp, start, 0);
            U.crashAge.value = tc - CR.tImp;
            U.crashP.value.set(f.com.x, D.ch.water, f.com.z + 1.7);
            U.flipAge.value = tc - CR.tFlip;
            U.flipP.value.copy(car.crashPose(CR.tFlip, start, 0).com).setY(D.ch.water);
            U.steam.value = smooth01((tc - CR.tImp) / 0.6);
            // steam rises from the drowned engine: the bonnet's middle in world... set-local
            U.steamP.value.copy(V3(0, 0.9, 1.1).applyQuaternion(qTmp).add(car.group.position)).setY(D.ch.water + 0.1);
        }
        for (const w of car.wheels) w.spin.rotation.x = wheelAng;
        // the drum and the barricade the car goes through: ballistic, a skid on the deck, off the edge if past it
        const sCar = crash > 0 ? car.length + CR.v * crash * CR.tEnd : sDist;
        for (const d of works.debris) {
            const age = car.group.visible ? (sCar + 2.0 - d.s0) / CR.v : -1;
            if (age <= 0) { d.obj.position.copy(d.home); d.obj.rotation.set(0, 0, 0); continue; }
            const tLand = (2 * d.v.y) / 9.81;
            const ta = Math.min(age, tLand);
            const slide = age > tLand ? (1 - Math.exp(-(age - tLand) * 2.2)) / 2.2 : 0;
            const pos = d.home.clone().add(V3(d.v.x * (ta + slide), d.v.y * ta - 4.905 * ta * ta, d.v.z * (ta + slide)));
            if (pos.x < D.xR) pos.y = Math.max(D.ground, d.v.y * age - 4.905 * age * age);
            d.obj.position.copy(pos);
            const spinT = ta + slide * 0.3;
            d.obj.rotation.set(d.w.x * spinT, d.w.y * spinT, d.w.z * spinT);
            if (age > tLand && pos.x >= D.xR) {           // landed: settle onto its side
                const k = Math.min(1, (age - tLand) / 0.15);
                d.obj.rotation.x = d.obj.rotation.x * (1 - k) + (Math.PI / 2) * k;
                d.obj.rotation.z *= 1 - k;
                d.obj.position.y = d.r * k;
            }
        }
        // the headlamps: on while running, drowned a moment after the nose goes in
        U.headlamps.value = (state.headlamps ?? 1) * (crash > 0 ? Math.max(0, 1 - Math.max(0, crash * CR.tEnd - CR.tImp) / 0.35) * (0.8 + 0.2 * Math.sin(t * 90)) : 1) * (car.group.visible ? 1 : 0);
        car.beam.intensity = 300 * U.headlamps.value;
        car.group.updateMatrixWorld();
        car.beam.position.copy(car.body.localToWorld(V3(0, 0.97, 2.15))).applyMatrix4(U.setInv.value);
        car.beam.target.position.copy(car.body.localToWorld(V3(0, 0.1, 14.0))).applyMatrix4(U.setInv.value);
        U.smear.value = Math.min(2.5, spinRate * shutter);
        U.chainRun.value = (wheelAng * 0.24) / 0.0254;
        U.scarfSpeed.value = crash > 0 ? Math.max(0.15, 1 - crash * 1.4) : Math.min(1, v / 20);
        // ---- the heel: descend, hover, slam (strike at 0.68), the toe slaps down, planted
        const hv = Math.min(1, Math.max(0, state.heel ?? 0));
        heel.root.visible = hv > 0;
        if (hv > 0) {
            const eo = (x) => 1 - (1 - x) * (1 - x);
            let y = 0, pitch = 0;
            if (hv < 0.45) { const k = eo(hv / 0.45); y = 0.95 + (0.22 - 0.95) * k; pitch = -0.35 + 0.1 * k; }
            else if (hv < 0.62) { const k = (hv - 0.45) / 0.17; y = 0.22 - 0.04 * k + 0.003 * Math.sin(t * 38); pitch = -0.25 - 0.07 * k; }
            else if (hv < HEEL.strike) { const k = (hv - 0.62) / (HEEL.strike - 0.62); y = 0.18 * (1 - k * k); pitch = -0.32; }
            else if (hv < 0.74) { const k = (hv - HEEL.strike) / (0.74 - HEEL.strike); y = 0.005 * Math.sin(k * Math.PI); pitch = -0.32 * (1 - k) * (1 - k); }
            heel.root.position.y = y;
            heel.pivot.rotation.x = pitch;
        }
        U.heelAge.value = hv > 0 ? (hv - HEEL.strike) * HEEL.dur : -10;
        U.heelKey.value = hv > 0 ? 1 : 0;
        const on = active ? 1 : 0;
        key.intensity = LIGHT_BASE.key * U.lamps.value * on;
        glowA.intensity = LIGHT_BASE.glow * U.billA.value * on;
        glowB.intensity = LIGHT_BASE.glow * U.billB.value * on;
        car.beam.intensity *= on;
        neonFill.intensity = LIGHT_BASE.neonFill * on;
        backRim.intensity = LIGHT_BASE.backRim * on * (state.backRim ?? 1) * (0.35 + 0.65 * Math.max(U.billA.value, U.billB.value));
    }
    update(0, {});

    function dispose() {
        group.removeFromParent();
        if (refl) refl.dispose?.();
        for (const d of disposables) d.dispose?.();
    }
    return { group, parts, update, dispose, setActive, cams, camAt, focal, LAYOUT: D, uniforms: U };
}
